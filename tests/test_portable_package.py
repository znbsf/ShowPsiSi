"""Platform-independent checks for fail-closed portable manifest/archive gates."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('portable_checks', ROOT / 'scripts/ci/portable_checks.py')
portable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portable)


class PortablePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.package = self.root / 'package'
        for name in ['bin/showpsisi-core.exe', 'bin/showpsisi-qt.exe', 'bin/tsduck.dll',
                     'bin/tscore.dll', 'bin/tsduck.tables.model.xml', 'bin/tsduck.dtv.names',
                     'bin/tscore.time.xml', 'bin/tscore.ip.names', 'bin/platforms/qwindows.dll',
                     'bin/qt.conf', 'bin/showpsisi-portable.json', 'api/tools.json', 'extensions/demo.json',
                     'references/standards.json', 'samples/generated/lab.ts', 'samples/generated/lab.manifest.json', 'LICENSE',
                     'THIRD_PARTY_NOTICES.txt', 'SOURCE_INFORMATION.txt']:
            path = self.package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture', encoding='utf-8')
        (self.package / 'build-information.json').write_text('{"source_commit":"fixture"}')
        (self.package / 'redistribution-review.json').write_text('{"review_complete":false}')
        self.artifacts = self.root / 'evidence'
        self.artifacts.mkdir()
        self.zip = self.root / 'app.zip'

    def tearDown(self):
        self.temp.cleanup()

    def validation(self):
        (self.artifacts / 'portable-validation.json').write_text(json.dumps({
            'passed': True, 'runtime_requirement': {'satisfied': True}, 'package_manifest_sha256': portable.digest(self.package / 'manifest.json')}))

    def approve_fixture(self):
        # Tests only: this is not approval of real runtime files.
        files = portable.review_inventory({'files': portable.inventory(self.package)})
        (self.package / 'redistribution-review.json').write_text(json.dumps({'review_complete': True, 'reviewed_files': files}))
        portable.manifest(self.package)
        self.validation()

    def test_manifest_detects_changed_file(self):
        portable.manifest(self.package)
        (self.package / 'bin/tscore.dll').write_text('modified')
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            portable.verify_manifest(self.package)

    def test_manifest_detects_added_file(self):
        portable.manifest(self.package)
        (self.package / 'surprise.dll').write_text('new')
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            portable.verify_manifest(self.package)

    def test_missing_required_resource_fails(self):
        (self.package / 'api/tools.json').unlink()
        with self.assertRaisesRegex(RuntimeError, 'api/tools.json'):
            portable.manifest(self.package)

    def test_test_helper_is_never_shipped(self):
        (self.package / 'bin/showpsisi-core-test.exe').write_text('fixture')
        with self.assertRaisesRegex(RuntimeError, 'Unexpected executable'):
            portable.manifest(self.package)

    def test_offscreen_plugin_is_never_shipped(self):
        (self.package / 'bin/platforms/qoffscreen.dll').write_text('fixture')
        with self.assertRaisesRegex(RuntimeError, 'Developer/test'):
            portable.manifest(self.package)

    def test_incomplete_review_blocks_archive(self):
        portable.manifest(self.package)
        self.validation()
        self.assertFalse(portable.archive(self.package, self.artifacts, self.zip))
        self.assertFalse(self.zip.exists())

    def test_boolean_alone_does_not_clear_inventory(self):
        (self.package / 'redistribution-review.json').write_text('{"review_complete":true}')
        portable.manifest(self.package)
        self.validation()
        self.assertFalse(portable.archive(self.package, self.artifacts, self.zip))

    def test_notice_change_invalidates_review(self):
        self.approve_fixture()
        (self.package / 'THIRD_PARTY_NOTICES.txt').write_text('changed')
        portable.manifest(self.package)
        self.validation()
        self.assertFalse(portable.archive(self.package, self.artifacts, self.zip))

    def test_stale_validation_blocks_archive(self):
        self.approve_fixture()
        (self.package / 'LICENSE').write_text('changed')
        portable.manifest(self.package)
        with self.assertRaisesRegex(RuntimeError, 'validation'):
            portable.archive(self.package, self.artifacts, self.zip)

    def test_new_own_executable_is_bound_to_new_validation_not_license_hash(self):
        self.approve_fixture()
        (self.package / 'bin/showpsisi-qt.exe').write_text('new build from recorded commit')
        portable.manifest(self.package)
        self.validation()
        self.assertTrue(portable.archive(self.package, self.artifacts, self.zip))

    def test_new_third_party_file_invalidates_review(self):
        self.approve_fixture()
        (self.package / 'bin/unknown.dll').write_text('unknown third party')
        portable.manifest(self.package)
        self.validation()
        self.assertFalse(portable.archive(self.package, self.artifacts, self.zip))

    def test_stale_archive_never_survives_blocked_gate(self):
        portable.manifest(self.package)
        self.validation()
        self.zip.write_bytes(b'stale binary archive')
        with self.assertRaisesRegex(RuntimeError, 'stale archive'):
            portable.archive(self.package, self.artifacts, self.zip)

    def test_archive_inside_package_is_rejected(self):
        self.approve_fixture()
        with self.assertRaisesRegex(RuntimeError, 'outside the package'):
            portable.archive(self.package, self.artifacts, self.package / 'self.zip')

    def test_validation_evidence_inside_package_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'outside the package'):
            portable.validate(self.package, self.package / 'evidence', self.root / 'qt')

    def test_insufficient_runtime_blocks_archive(self):
        self.approve_fixture()
        path = self.artifacts / 'portable-validation.json'
        report = json.loads(path.read_text())
        report['runtime_requirement']['satisfied'] = False
        path.write_text(json.dumps(report))
        self.assertFalse(portable.archive(self.package, self.artifacts, self.zip))
        self.assertFalse(self.zip.exists())

    def test_nested_manifest_is_hashed(self):
        path = self.package / 'bin/manifest.json'
        path.write_text('nested component metadata')
        value = portable.manifest(self.package)
        self.assertIn('bin/manifest.json', value['files'])

    def test_exact_review_and_validation_create_hashed_archive(self):
        self.approve_fixture()
        self.assertTrue(portable.archive(self.package, self.artifacts, self.zip))
        self.assertIn(portable.digest(self.zip), self.zip.with_suffix('.zip.sha256').read_text())
