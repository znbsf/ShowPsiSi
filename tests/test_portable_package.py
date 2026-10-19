"""Platform-independent checks for fail-closed portable manifest/archive gates."""
import importlib.util
import json
from pathlib import Path
import tempfile
import struct
import shutil
from types import SimpleNamespace
import unittest
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('portable_checks', ROOT / 'scripts/ci/portable_checks.py')
portable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(portable)
sys.path.insert(0, str(ROOT / 'scripts/ci'))
import portable_launcher_checks
import static_dependencies


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
                     'THIRD_PARTY_NOTICES.txt', 'SOURCE_INFORMATION.txt', 'Launch Qt.cmd', 'README-portable.txt',
                     'assets/icons/showpsisi.svg', 'assets/icons/showpsisi-256.png', 'assets/icons/showpsisi.ico']:
            path = self.package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture', encoding='utf-8')
        (self.package / 'build-information.json').write_text(json.dumps({
            'source_commit': 'fixture', 'application_version': '0.1.0',
            'static_dependencies': static_dependencies.DEPENDENCIES}))
        bundle = ROOT / 'scripts/portable-licenses'
        for name in ('THIRD_PARTY_NOTICES.txt', 'SOURCE_INFORMATION.txt', 'source-index.json',
                     *static_dependencies.EXPAT['notice_files']):
            path = self.package / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(bundle / name, path)
        (self.package / 'redistribution-review.json').write_text('{"review_complete":false}')
        self.artifacts = self.root / 'evidence'
        self.artifacts.mkdir()
        self.zip = self.root / 'ShowPsiSi-0.1.0-windows-x64-portable.zip'

    def test_versioned_portable_asset_contract(self):
        self.assertEqual(portable.portable_asset_name('0.1.0'), self.zip.name)
        for version in (None, 'v0.1.0', '0.1', '0.1.0-beta', '00.1.0', '0.1.0/other'):
            with self.subTest(version=version), self.assertRaises(RuntimeError):
                portable.portable_asset_name(version)

    def test_archive_cannot_mislabel_package_version(self):
        self.approve_fixture()
        with self.assertRaisesRegex(RuntimeError, 'asset name'):
            portable.archive(self.package, self.artifacts, self.root / 'ShowPsiSi-0.2.0-windows-x64-portable.zip')

    def test_launcher_preflight_is_read_only_and_blocks_before_qt(self):
        launcher = ROOT / 'scripts/portable/Launch Qt.cmd'
        text = launcher.read_text()
        command = portable_launcher_checks.command(launcher)
        for name in ('vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll'):
            self.assertIn(name, command)
        self.assertIn('14.51.36231.0', command)
        self.assertIn('10.0.17763.0', command)
        self.assertIn('[Console]::Error.WriteLine', command)
        for forbidden in ('ExecutionPolicy', 'Invoke-WebRequest', 'Start-Process', 'runas', 'Set-ItemProperty'):
            self.assertNotIn(forbidden, command)
        self.assertLess(text.index('if errorlevel 1 goto runtime_not_ready'), text.index('start "" /wait'))
        self.assertIn('https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist', text)
        self.assertIn('exit /b 1', text)
        self.assertLess(text.index('if not errorlevel 0 goto runtime_not_ready'), text.index('start "" /wait'))

    def test_launcher_probe_requires_exact_single_production_command(self):
        launcher = self.root / 'launcher.cmd'
        launcher.write_text('start qt.exe')
        with self.assertRaisesRegex(RuntimeError, 'exactly one'):
            portable_launcher_checks.command(launcher)

    def test_preflight_fixture_changes_only_checker_root_not_powershell_environment(self):
        production = portable_launcher_checks.command(ROOT / 'scripts/portable/Launch Qt.cmd')
        fixture = portable_launcher_checks.fixture_command(production)
        self.assertEqual(fixture.replace('$env:SHOWPSISI_PREFLIGHT_FIXTURE_ROOT', '$env:SHOWPSISI_PACKAGE_ROOT'), production)
        self.assertNotIn('$env:SystemRoot', fixture)
        for bad in ('no root', '$env:SHOWPSISI_PACKAGE_ROOT; $env:SHOWPSISI_PACKAGE_ROOT'):
            with self.assertRaisesRegex(RuntimeError, 'one DLL root'):
                portable_launcher_checks.fixture_command(bad)

    def test_non_windows_preflight_probe_never_claims_windows_pass(self):
        with mock.patch.object(portable_launcher_checks.os, 'name', 'posix'), self.assertRaisesRegex(RuntimeError, 'requires Windows'):
            portable_launcher_checks.probe(self.package / 'Launch Qt.cmd', self.artifacts)

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
        with self.assertRaisesRegex(RuntimeError, 'Static dependency notice'):
            portable.archive(self.package, self.artifacts, self.zip)

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

    def test_static_dependency_omissions_cannot_be_reapproved_by_file_inventory(self):
        for name in ('source-index.json', *static_dependencies.EXPAT['notice_files']):
            with self.subTest(name=name):
                path = self.package / name
                original = path.read_bytes()
                path.unlink()
                self.approve_fixture()  # Deliberately regenerates exact manifest/review hashes.
                with self.assertRaisesRegex(RuntimeError, 'Static dependency'):
                    portable.archive(self.package, self.artifacts, self.zip)
                self.assertFalse(self.zip.exists())
                path.write_bytes(original)

    def test_static_dependency_changed_notice_cannot_be_reapproved(self):
        for name in static_dependencies.EXPAT['notice_files']:
            with self.subTest(name=name):
                path = self.package / name
                original = path.read_bytes()
                path.write_bytes(original + b'changed')
                self.approve_fixture()
                with self.assertRaisesRegex(RuntimeError, 'Static dependency notice'):
                    portable.archive(self.package, self.artifacts, self.zip)
                path.write_bytes(original)

    def test_static_dependency_build_and_source_index_are_mandatory(self):
        for name in ('build-information.json', 'source-index.json'):
            path = self.package / name
            original = path.read_bytes()
            for replacement in (None, [], [{'name': 'Expat', 'version': 'different'}]):
                with self.subTest(name=name, replacement=replacement):
                    value = json.loads(original)
                    if replacement is None:
                        del value['static_dependencies']
                    else:
                        value['static_dependencies'] = replacement
                    path.write_text(json.dumps(value))
                    self.approve_fixture()
                    with self.assertRaisesRegex(RuntimeError, 'Static dependency identity'):
                        portable.archive(self.package, self.artifacts, self.zip)
            path.write_bytes(original)

    def test_static_dependency_prominent_notice_and_source_text_are_mandatory(self):
        for name in ('THIRD_PARTY_NOTICES.txt', 'SOURCE_INFORMATION.txt'):
            path = self.package / name
            original = path.read_bytes()
            path.write_text('All other notices remain; Expat omitted.')
            self.approve_fixture()
            with self.assertRaisesRegex(RuntimeError, 'Static dependency notice'):
                portable.archive(self.package, self.artifacts, self.zip)
            path.write_bytes(original)

    def test_static_dependency_control_json_rejects_duplicate_keys(self):
        path = self.package / 'source-index.json'
        path.write_text('{"static_dependencies":[],"static_dependencies":' +
                        json.dumps(static_dependencies.DEPENDENCIES) + '}')
        self.approve_fixture()
        with self.assertRaisesRegex(RuntimeError, 'Duplicate static-dependency'):
            portable.archive(self.package, self.artifacts, self.zip)

    def test_manifest_cannot_supply_static_identity_missing_from_build_file(self):
        self.approve_fixture()
        path = self.package / 'build-information.json'
        value = json.loads(path.read_text())
        del value['static_dependencies']
        path.write_text(json.dumps(value))
        manifest = self.package / 'manifest.json'
        saved = json.loads(manifest.read_text())
        saved['files'] = portable.inventory(self.package)
        manifest.write_text(json.dumps(saved))
        self.validation()
        with self.assertRaisesRegex(RuntimeError, 'build identity differs'):
            portable.archive(self.package, self.artifacts, self.zip)

    def test_actual_static_source_inventory_and_reviewed_notices_are_pinned(self):
        self.assertEqual(static_dependencies.verify_source(ROOT), static_dependencies.DEPENDENCIES)
        bundle = ROOT / 'scripts/portable-licenses'
        review = json.loads((bundle / 'redistribution-review.json').read_text())
        for name, expected in static_dependencies.EXPAT['notice_files'].items():
            self.assertEqual(portable.digest(bundle / name), expected)
            self.assertEqual(review['reviewed_files'][name], expected)
        text = (bundle / 'licenses/expat/UPSTREAM-NOTICES.txt').read_text()
        self.assertIn('lib/xmlparse.c', text)
        self.assertIn('lib/siphash.h', text)
        self.assertIn('SPDX-License-Identifier: CC0-1.0', text)

    def test_changed_missing_or_added_static_source_is_rejected(self):
        root = self.root / 'source'
        target = root / 'third_party/expat'
        shutil.copytree(ROOT / 'third_party/expat', target)
        path = target / 'lib/xmlparse.c'
        original = path.read_bytes()
        for mode in ('change', 'missing', 'extra'):
            with self.subTest(mode=mode):
                if mode == 'change':
                    path.write_bytes(original + b'changed')
                elif mode == 'missing':
                    path.unlink()
                else:
                    (target / 'unreviewed.c').write_text('extra source')
                with self.assertRaisesRegex(RuntimeError, 'source inventory'):
                    static_dependencies.verify_source(root)
                path.write_bytes(original)

    def test_static_source_provenance_cannot_be_rewritten_to_match_changes(self):
        root = self.root / 'source'
        target = root / 'third_party/expat'
        shutil.copytree(ROOT / 'third_party/expat', target)
        path = target / 'lib/xmlparse.c'
        path.write_text('changed source')
        metadata = target / 'SHOWPSISI_SOURCE.json'
        value = json.loads(metadata.read_text())
        value['files_sha256']['lib/xmlparse.c'] = portable.digest(path)
        metadata.write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError, 'source provenance'):
            static_dependencies.verify_source(root)

    def test_windows_build_and_staging_bind_static_dependency_record(self):
        build = (ROOT / 'scripts/ci/windows.ps1').read_text()
        self.assertLess(build.index("'scripts/ci/static_dependencies.py'"),
                        build.index("'--build'"))
        self.assertGreater(build.rindex("'scripts/ci/static_dependencies.py'"),
                           build.index("'--build'"))
        self.assertIn('$BuildRecord.static_dependencies', build)
        stage = (ROOT / 'scripts/package-windows.ps1').read_text()
        self.assertIn("'--record', (Join-Path $BuildBin 'showpsisi-build.json')", stage)
        self.assertIn('static_dependencies = $Record.static_dependencies', stage)
