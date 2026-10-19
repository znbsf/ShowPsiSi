"""Offline runtime pin, extraction, typed provenance and redistribution gates."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('vc_runtime', ROOT / 'scripts/ci/vc_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class RuntimePinTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.package = Path(self.temp.name)
        self.pin = copy.deepcopy(runtime.pin())
        for name, entry in self.pin['package_metadata']['files'].items():
            data = ('unit fixture ' + name).encode()
            path = self.package / 'bin' / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(data)
            entry.update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        self.metadata = self.pin['package_metadata']
        self.record = {'crt_mode': 'AppLocal', 'crt_provenance': self.metadata,
                       'crt_minimum_version': self.metadata['minimum_version']}
        self.write_metadata(self.metadata)
        patch = mock.patch.object(runtime, 'pin', return_value=self.pin)
        patch.start()
        self.addCleanup(patch.stop)

    def write_metadata(self, value):
        (self.package / 'bin/showpsisi-vc-runtime.json').write_text(json.dumps(value))

    def test_exact_five_file_identity(self):
        self.assertEqual(len(runtime.verify_package(self.package, self.record)['files']), 5)
        self.assertIn('msvcp140_2.dll', self.metadata['files'])

    def test_missing_local_dll_is_not_satisfied_by_system(self):
        (self.package / 'bin/msvcp140_2.dll').unlink()
        with self.assertRaisesRegex(RuntimeError, 'bytes differ'):
            runtime.verify_package(self.package, self.record)

    def test_tamper_rejected_even_if_mutable_manifest_could_be_regenerated(self):
        path = self.package / 'bin/msvcp140.dll'
        path.write_bytes(b'changed')
        with self.assertRaises(RuntimeError):
            runtime.verify_package(self.package, self.record)

    def test_metadata_types_cannot_alias_integer(self):
        for value in (True, 1.0, '1'):
            changed = copy.deepcopy(self.metadata)
            changed['schema_version'] = value
            self.write_metadata(changed)
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'provenance'):
                runtime.verify_package(self.package, dict(self.record, crt_provenance=changed))

    def test_metadata_cannot_diverge_from_build(self):
        changed = copy.deepcopy(self.metadata)
        changed['version'] = '14.51.36248.0'
        with self.assertRaisesRegex(RuntimeError, 'provenance'):
            runtime.verify_package(self.package, dict(self.record, crt_provenance=changed))

    def test_lowered_minimum_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'minimum'):
            runtime.verify_package(self.package, dict(self.record, crt_minimum_version='14.0.0.0'))

    def test_duplicate_metadata_key_is_rejected(self):
        p = self.package / 'duplicate.json'
        p.write_text('{"mode":"AppLocal","mode":"Prerequisite"}')
        with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
            runtime.read_json(p)

    def test_nonfinite_metadata_is_rejected(self):
        p = self.package / 'nonfinite.json'
        p.write_text('{"value":NaN}')
        with self.assertRaisesRegex(RuntimeError, 'Non-finite'):
            runtime.read_json(p)

    def test_technical_identity_does_not_grant_redistribution(self):
        p = self.package / runtime.REVIEW_NAME
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({'review_complete': True}))
        with self.assertRaisesRegex(RuntimeError, 'entitlement review'):
            runtime.distribution_gate(self.package)

    def test_checked_in_review_records_hosted_basis_and_inference(self):
        review = runtime.read_json(ROOT / 'scripts/portable-licenses' / runtime.REVIEW_NAME)
        self.assertTrue(review['review_complete'])
        basis = review['license_basis']
        self.assertEqual(basis['hosted_license_confirmation'],
                         'https://github.com/actions/runner-images/issues/12945#issuecomment-3348002951')
        self.assertIn('/2022/redistribution', basis['applicable_terms_url'])
        self.assertTrue(basis['downstream_hosted_redist_is_inference'])
        self.assertFalse(basis['personal_license_evidence_required'])
        self.assertFalse(basis['new_agreement_accepted'])
        self.assertTrue(basis['inference_boundary'])

    def test_retained_metadata_describes_current_runtime_and_source_delivery(self):
        materials = ROOT / 'scripts/portable-licenses'
        index = runtime.read_json(materials / 'source-index.json')
        review = runtime.read_json(materials / 'redistribution-review.json')
        self.assertIn('same-release', review['evidence']['source_delivery'])
        self.assertIn('app-locally', review['evidence']['runtime_prerequisites'])
        self.assertNotIn('No Microsoft binaries redistributed', json.dumps(review))
        self.assertNotIn('VC runtime prerequisite, not redistribution', json.dumps(index))
        self.assertEqual(review['reviewed_files']['source-index.json'],
                         hashlib.sha256((materials / 'source-index.json').read_bytes()).hexdigest())
        for name, expected in index['microsoft_runtime_terms']['files'].items():
            self.assertEqual(hashlib.sha256((materials / name).read_bytes()).hexdigest(), expected)
            self.assertEqual(review['reviewed_files'][name], expected)

    def test_cabinet_slice_is_exact_and_never_overwrites(self):
        cab = bytearray(b'MSCF' + bytes(40))
        struct.pack_into('<I', cab, 8, len(cab))
        data = b'prefix' + cab + b'tail'
        source = self.package / 'source.exe'
        source.write_bytes(data)
        self.pin['package_metadata']['source'].update(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        self.pin['cabinet'].update(offset=6, bytes=len(cab), sha256=hashlib.sha256(cab).hexdigest())
        output = self.package / 'slice.cab'
        runtime.cabinet(source, output)
        self.assertEqual(output.read_bytes(), cab)
        with self.assertRaises(FileExistsError):
            runtime.cabinet(source, output)

    def test_tampered_cabinet_or_parent_is_rejected(self):
        source = self.package / 'source.exe'
        source.write_bytes(b'MSCF' + bytes(100))
        with self.assertRaisesRegex(RuntimeError, 'bytes differ'):
            runtime.cabinet(source, self.package / 'slice.cab')

    def test_build_scripts_never_execute_redistributable(self):
        script = (ROOT / 'scripts/prepare-applocal-runtime.ps1').read_text()
        for forbidden in ('Start-Process', '/install', '/quiet', 'runas', 'msiexec', 'System32/*.dll'):
            self.assertNotIn(forbidden, script)
        self.assertIn('Get-AuthenticodeSignature', script)
        self.assertIn('System32/expand.exe', script)
        package = (ROOT / 'scripts/package-windows.ps1').read_text()
        self.assertNotIn('Microsoft.VC143.CRT', package)
        self.assertIn("$CrtMode = 'AppLocal'", package)


if __name__ == '__main__':
    unittest.main()
