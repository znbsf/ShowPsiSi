"""Platform-independent checks for fail-closed portable manifest/archive gates."""
import importlib.util
import json
from pathlib import Path
import tempfile
import struct
from types import SimpleNamespace
import unittest
from unittest import mock

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
                     'references/standards.json', 'references/satellites.json', 'samples/generated/lab.ts', 'samples/generated/lab.manifest.json', 'LICENSE',
                     'THIRD_PARTY_NOTICES.txt', 'SOURCE_INFORMATION.txt',
                     'assets/icons/showpsisi.svg', 'assets/icons/showpsisi-256.png', 'assets/icons/showpsisi.ico']:
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

    def test_windows_environment_case_is_normalized_before_dict_lookup(self):
        for name in ('SystemRoot', 'SYSTEMROOT', 'systemroot'):
            with self.subTest(name=name), mock.patch.dict(portable.os.environ, {
                name: 'C:/Windows', 'Path': 'C:/SDK/bin', 'SHOWPSISI_ROOT': 'bad',
                'Qt_Plugin_Path': 'C:/SDK/plugins', 'TEMP': 'C:/Temp'}, clear=True):
                env = portable.clean_environment()
                self.assertEqual(env['SYSTEMROOT'], 'C:/Windows')
                self.assertEqual(env['PATH'], str(Path('C:/Windows') / 'System32'))
                self.assertNotIn('SHOWPSISI_ROOT', env)
                self.assertNotIn('QT_PLUGIN_PATH', env)
                self.assertEqual(env['TEMP'], 'C:/Temp')

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

    def test_missing_application_icon_fails(self):
        for name in ('showpsisi.svg', 'showpsisi-256.png', 'showpsisi.ico'):
            path = self.package / 'assets/icons' / name
            saved = path.read_bytes()
            path.unlink()
            with self.assertRaisesRegex(RuntimeError, name):
                portable.manifest(self.package)
            path.write_bytes(saved)

    def test_icon_change_invalidates_manifest(self):
        portable.manifest(self.package)
        (self.package / 'assets/icons/showpsisi.ico').write_bytes(b'changed icon')
        with self.assertRaisesRegex(RuntimeError, 'changed'):
            portable.verify_manifest(self.package)

    def icon_pe_fixture(self):
        icon = (ROOT / 'assets/icons/showpsisi.ico').read_bytes()
        (self.package / 'assets/icons/showpsisi.ico').write_bytes(icon)
        payloads, group = [], bytearray(struct.pack('<HHH', 0, 1, 7))
        for index in range(7):
            fields = struct.unpack('<BBBBHHII', icon[6 + 16 * index:22 + 16 * index])
            length, offset = fields[6:]
            payloads.append(icon[offset:offset + length])
            group.extend(struct.pack('<BBBBHHIH', *fields[:7], index + 1))
        payloads.append(bytes(group))
        def resource(kind, indexes):
            return SimpleNamespace(id=kind, directory=SimpleNamespace(entries=[
                SimpleNamespace(id=i + 1, directory=SimpleNamespace(entries=[SimpleNamespace(
                    id=1033, data=SimpleNamespace(struct=SimpleNamespace(
                        OffsetToData=i, Size=len(payloads[i]))))])) for i in indexes]))
        pe = mock.Mock()
        pe.DIRECTORY_ENTRY_RESOURCE.entries = [resource(3, range(7)), resource(14, [7])]
        pe.get_data.side_effect = lambda offset, length: payloads[offset]
        return pe, payloads

    def test_embedded_icon_is_bound_to_manifested_artwork(self):
        pe, payloads = self.icon_pe_fixture()
        with mock.patch.dict('sys.modules', {'pefile': SimpleNamespace(PE=lambda path: pe)}):
            self.assertTrue(portable.embedded_application_icon(self.package)['verified'])
            payloads[0] = bytes(len(payloads[0]))
            with self.assertRaisesRegex(RuntimeError, 'does not match'):
                portable.embedded_application_icon(self.package)
        self.assertEqual(pe.close.call_count, 2)

    def test_invalid_icon_group_links_are_rejected(self):
        for corruption in ('header_only', 'truncated', 'count', 'missing_id', 'duplicate_id',
                           'duplicate_size', 'wrong_size', 'wrong_length', 'wrong_planes',
                           'wrong_language', 'missing_image', 'duplicate_image_id', 'trailing_bytes'):
            with self.subTest(corruption=corruption):
                pe, payloads = self.icon_pe_fixture()
                group = bytearray(payloads[7])
                if corruption == 'header_only':
                    group = group[:6]
                elif corruption == 'truncated':
                    group = group[:-1]
                elif corruption == 'count':
                    struct.pack_into('<H', group, 4, 6)
                elif corruption == 'missing_id':
                    struct.pack_into('<H', group, 18, 99)
                elif corruption == 'duplicate_id':
                    struct.pack_into('<H', group, 32, 1)
                elif corruption == 'duplicate_size':
                    group[20] = group[6]
                elif corruption == 'wrong_size':
                    group[7] = 99
                elif corruption == 'wrong_length':
                    struct.pack_into('<I', group, 14, 1)
                elif corruption == 'wrong_planes':
                    struct.pack_into('<H', group, 10, 2)
                elif corruption == 'wrong_language':
                    pe.DIRECTORY_ENTRY_RESOURCE.entries[0].directory.entries[0].directory.entries[0].id = 0
                elif corruption == 'missing_image':
                    pe.DIRECTORY_ENTRY_RESOURCE.entries[0].directory.entries.pop(0)
                elif corruption == 'duplicate_image_id':
                    pe.DIRECTORY_ENTRY_RESOURCE.entries[0].directory.entries[1].id = 1
                elif corruption == 'trailing_bytes':
                    group += b'x'
                payloads[7] = bytes(group)
                pe.DIRECTORY_ENTRY_RESOURCE.entries[1].directory.entries[0].directory.entries[0].data.struct.Size = len(group)
                with mock.patch.dict('sys.modules', {'pefile': SimpleNamespace(PE=lambda path: pe)}):
                    with self.assertRaises(RuntimeError):
                        portable.embedded_application_icon(self.package)
                pe.close.assert_called_once()

    def test_valid_unrelated_group_cannot_mask_invalid_default(self):
        pe, payloads = self.icon_pe_fixture()
        groups = pe.DIRECTORY_ENTRY_RESOURCE.entries[1].directory.entries
        extra = SimpleNamespace(id=99, directory=SimpleNamespace(entries=[SimpleNamespace(
            id=1033, data=SimpleNamespace(struct=SimpleNamespace(OffsetToData=8, Size=len(payloads[7]))))]))
        groups.append(extra)
        payloads.append(payloads[7])  # A complete valid secondary group.
        broken = bytearray(payloads[7])
        struct.pack_into('<H', broken, 18, 99)
        payloads[7] = bytes(broken)
        with mock.patch.dict('sys.modules', {'pefile': SimpleNamespace(PE=lambda path: pe)}):
            with self.assertRaisesRegex(RuntimeError, 'does not match'):
                portable.embedded_application_icon(self.package)
        pe.close.assert_called_once()

    def test_test_helper_is_never_shipped(self):
        (self.package / 'bin/showpsisi-core-test.exe').write_text('fixture')
        with self.assertRaisesRegex(RuntimeError, 'Unexpected executable'):
            portable.manifest(self.package)

    def test_system_d3d_compiler_is_not_redistributed(self):
        (self.package / 'bin/D3Dcompiler_47.dll').write_text('system component')
        with self.assertRaisesRegex(RuntimeError, 'Developer/test'):
            portable.manifest(self.package)

    def test_qml_debug_plugins_are_not_shipped(self):
        path = self.package / 'bin/qmltooling/debug.dll'
        path.parent.mkdir()
        path.write_text('debug plugin')
        with self.assertRaisesRegex(RuntimeError, 'Developer/test'):
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
