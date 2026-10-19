"""Platform-independent contracts; synthetic PE/maps never claim Windows proof."""
import copy
from datetime import datetime, timezone
import hashlib
import json
import ntpath
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/ci'))
import portable_launcher_checks as launcher
import windows_runtime_modules as runtime


class AppLocalValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='applocal unicode 测试 ')
        self.root = Path(self.temp.name)
        self.package = self.root / 'package 空间'
        self.bindir = self.package / 'bin'
        self.bindir.mkdir(parents=True)
        files = {}
        for name in runtime.RUNTIME_NAMES:
            data = ('synthetic non-executable test data ' + name).encode()
            (self.bindir / name).write_bytes(data)
            files[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                           'version': runtime.PINNED_VERSION, 'machine': 'AMD64'}
        for name in ('showpsisi-core.exe', 'showpsisi-qt.exe'):
            (self.bindir / name).write_bytes(b'not an executable; isolated unit fixture')
        self.metadata = {'schema_version': 1, 'mode': 'AppLocal', 'version': runtime.PINNED_VERSION,
                         'minimum_version': runtime.MINIMUM_VERSION, 'files': files}
        self.write_metadata()
        self.pe_patch = mock.patch.object(runtime, 'pe_identity', side_effect=lambda path: {
            'version': runtime.PINNED_VERSION, 'machine': 'AMD64'})
        self.pe_patch.start()
        self.addCleanup(self.pe_patch.stop)
        self.addCleanup(self.temp.cleanup)

    def write_metadata(self):
        (self.bindir / runtime.METADATA_NAME).write_text(json.dumps(self.metadata), encoding='utf-8')

    def test_five_exact_names_include_transitive_qt_runtime(self):
        self.assertEqual(set(runtime.RUNTIME_NAMES), {'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
                                                     'vcruntime140.dll', 'vcruntime140_1.dll'})
        value = runtime.inspect_runtime(self.package)
        self.assertTrue(value['satisfied'])
        self.assertEqual(value['version'], '14.51.36247.0')
        self.assertEqual(value['required_minimum'], '14.51.36231.0')

    def test_missing_local_runtime_does_not_search_host(self):
        missing = self.bindir / 'msvcp140_2.dll'
        host = self.root / 'System32'
        host.mkdir()
        (host / missing.name).write_bytes(missing.read_bytes())
        missing.unlink()
        with mock.patch.dict(runtime.os.environ, {'SystemRoot': str(self.root)}), self.assertRaisesRegex(RuntimeError, 'Missing bundled'):
            runtime.inspect_runtime(self.package)

    def test_old_local_runtime_rejected_before_hash_acceptance(self):
        with mock.patch.object(runtime, 'pe_identity', return_value={'machine': 'AMD64', 'version': '14.50.0.0'}), self.assertRaisesRegex(RuntimeError, 'too old'):
            runtime.inspect_runtime(self.package)

    def test_newer_unpinned_local_runtime_rejected(self):
        with mock.patch.object(runtime, 'pe_identity', return_value={'machine': 'AMD64', 'version': '14.52.0.0'}), self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
            runtime.inspect_runtime(self.package)

    def test_corruption_with_intact_version_and_size_rejected(self):
        path = self.bindir / 'msvcp140_2.dll'
        data = bytearray(path.read_bytes())
        data[-1] ^= 1
        path.write_bytes(data)
        with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
            runtime.inspect_runtime(self.package)

    def test_metadata_mode_minimum_and_pin_fail_closed(self):
        for key, value in [('mode', 'Prerequisite'), ('mode', None), ('schema_version', True),
                           ('schema_version', 1.0), ('version', '14.52.0.0'),
                           ('minimum_version', '14.40.0.0')]:
            saved = self.metadata[key]
            self.metadata[key] = value
            self.write_metadata()
            with self.subTest(key=key, value=value), self.assertRaisesRegex(RuntimeError, 'identity/mode'):
                runtime.runtime_metadata(self.package)
            self.metadata[key] = saved

    def test_metadata_files_reject_missing_extra_and_case_aliases(self):
        for replacement in ('missing', 'concrt140.dll', 'MSVCP140.dll'):
            changed = copy.deepcopy(self.metadata)
            entry = changed['files'].pop('msvcp140.dll')
            if replacement != 'missing':
                changed['files'][replacement] = entry
            (self.bindir / runtime.METADATA_NAME).write_text(json.dumps(changed))
            with self.subTest(replacement=replacement), self.assertRaisesRegex(RuntimeError, 'exactly the five'):
                runtime.runtime_metadata(self.package)

    def test_metadata_entry_rejects_wrong_types_and_architecture(self):
        for key, value in [('bytes', True), ('bytes', 0), ('bytes', '123'), ('sha256', 'F' * 64),
                           ('sha256', 'a' * 63), ('version', runtime.MINIMUM_VERSION), ('machine', 'I386')]:
            changed = copy.deepcopy(self.metadata)
            changed['files']['msvcp140.dll'][key] = value
            (self.bindir / runtime.METADATA_NAME).write_text(json.dumps(changed))
            with self.subTest(key=key, value=value), self.assertRaisesRegex(RuntimeError, 'metadata entry'):
                runtime.runtime_metadata(self.package)

    def test_metadata_duplicate_keys_are_rejected(self):
        content = json.dumps(self.metadata).replace('"schema_version": 1', '"schema_version": 0, "schema_version": 1')
        (self.bindir / runtime.METADATA_NAME).write_text(content)
        with self.assertRaisesRegex(RuntimeError, 'invalid bundled'):
            runtime.runtime_metadata(self.package)

    def test_loaded_modules_accept_matching_per_process_subset(self):
        subset = ['msvcp140.dll', 'msvcp140_1.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']
        value = runtime.verify_loaded_modules([str(self.bindir / name) for name in subset], self.package,
                                              required_names=subset)
        self.assertTrue(value['passed'])
        self.assertNotIn('msvcp140_2.dll', value['modules'])

    def test_loaded_system_copy_rejected_even_with_identical_hash(self):
        host = self.root / 'System32'
        host.mkdir()
        path = host / 'msvcp140.dll'
        path.write_bytes((self.bindir / path.name).read_bytes())
        with self.assertRaisesRegex(RuntimeError, 'outside package bin'):
            runtime.verify_loaded_modules([str(path)], self.package, required_names=[path.name])

    def test_unobserved_required_module_rejected(self):
        paths = [str(self.bindir / 'vcruntime140.dll')]
        with self.assertRaisesRegex(RuntimeError, 'not observed'):
            runtime.verify_loaded_modules(paths, self.package, required_names=['msvcp140_2.dll'])

    def test_unknown_loaded_crt_family_rejected(self):
        for name in ('concrt140.dll', 'vcomp140.dll', 'vcamp140.dll', 'vccorlib140.dll',
                     'msvcr120.dll', 'msvcp140_atomic_wait.dll'):
            with self.subTest(name=name), self.assertRaisesRegex(RuntimeError, 'unreviewed'):
                runtime.verify_loaded_modules([str(self.bindir / name)], self.package)

    def test_empty_or_duplicate_runtime_snapshot_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'No app-local'):
            runtime.verify_loaded_modules([], self.package)
        path = str(self.bindir / 'msvcp140.dll')
        with self.assertRaisesRegex(RuntimeError, 'Duplicate'):
            runtime.verify_loaded_modules([path, path], self.package)

    def fake_pe_imports(self, imports, delayed=None):
        def parse(path, fast_load):
            name = Path(path).name.lower()
            return SimpleNamespace(
                DIRECTORY_ENTRY_IMPORT=[SimpleNamespace(dll=value.encode()) for value in imports.get(name, [])],
                DIRECTORY_ENTRY_DELAY_IMPORT=[SimpleNamespace(dll=value.encode()) for value in (delayed or {}).get(name, [])],
                parse_data_directories=lambda directories: None, close=lambda: None)
        return mock.patch.dict(sys.modules, {'pefile': SimpleNamespace(PE=parse, DIRECTORY_ENTRY={'IMAGE_DIRECTORY_ENTRY_IMPORT': 1})})

    def test_normal_import_closure_is_transitive_case_insensitive_and_cycle_safe(self):
        (self.bindir / 'Qt6Gui.dll').write_bytes(b'synthetic import graph node')
        imports = {'showpsisi-qt.exe': ['Qt6Gui.dll', 'VCRUNTIME140.dll', 'KERNEL32.dll'],
                   'qt6gui.dll': ['MSVCP140_2.dll', 'MSVCP140.dll'],
                   'msvcp140.dll': ['VCRUNTIME140_1.dll'],
                   'vcruntime140.dll': ['Qt6Gui.dll']}
        with self.fake_pe_imports(imports):
            self.assertEqual(runtime.required_crt_modules(self.package, self.bindir / 'showpsisi-qt.exe'),
                             ['msvcp140.dll', 'msvcp140_2.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'])

    def test_delay_imports_are_not_required_before_first_use(self):
        with self.fake_pe_imports({'showpsisi-core.exe': ['vcruntime140.dll']},
                                 {'showpsisi-core.exe': ['msvcp140_2.dll']}):
            self.assertEqual(runtime.required_crt_modules(self.package, self.bindir / 'showpsisi-core.exe'),
                             ['vcruntime140.dll'])

    def test_unknown_crt_import_never_resolves_from_system(self):
        with self.fake_pe_imports({'showpsisi-core.exe': ['vccorlib140.dll']}), self.assertRaisesRegex(RuntimeError, 'Unreviewed VC'):
            runtime.required_crt_modules(self.package, self.bindir / 'showpsisi-core.exe')

    def test_missing_imported_local_dll_cannot_fall_back(self):
        (self.bindir / 'vcruntime140.dll').unlink()
        with self.fake_pe_imports({'showpsisi-core.exe': ['vcruntime140.dll']}), self.assertRaisesRegex(RuntimeError, 'Missing bundled'):
            runtime.required_crt_modules(self.package, self.bindir / 'showpsisi-core.exe')

    def test_import_graph_rejects_outside_executable_and_path_import(self):
        with self.fake_pe_imports({}), self.assertRaisesRegex(RuntimeError, 'outside packaged bin'):
            runtime.required_crt_modules(self.package, self.root / 'foreign.exe')
        with self.fake_pe_imports({'showpsisi-core.exe': [r'C:\Windows\System32\msvcp140.dll']}), self.assertRaisesRegex(RuntimeError, 'Invalid PE import'):
            runtime.required_crt_modules(self.package, self.bindir / 'showpsisi-core.exe')

    def report(self):
        root = r'C:\relocated package 测试'
        name = 'showpsisi-core.exe'
        exe = ntpath.join(root, 'bin', name)
        names = ['msvcp140.dll', 'vcruntime140.dll']
        paths = [exe, r'C:\Windows\System32\ntdll.dll'] + [ntpath.join(root, 'bin', name) for name in names]
        modules = {name: dict(self.metadata['files'][name], path=ntpath.join(root, 'bin', name)) for name in names}
        return {'schema_version': 1, 'passed': True, 'pid': 1234, 'platform': 'Windows',
                'package_root': root, 'executable': exe, 'executable_name': name,
                'executable_sha256': runtime.sha256(self.bindir / name),
                'sampled_at_utc': datetime.now(timezone.utc).isoformat(),
                'process_created_unix': 1.0, 'command_line': [exe, '--root', root],
                'module_paths': paths, 'raw_modules': [{'path': path, 'rss': 1} for path in paths],
                'runtime': {'passed': True, 'mode': 'AppLocal', 'required_modules': names, 'modules': modules}}

    def verify_report(self, report):
        with mock.patch.object(runtime, 'required_crt_modules', return_value=['msvcp140.dll', 'vcruntime140.dll']):
            return runtime.verify_capture(report, self.package, 'showpsisi-core.exe')

    def test_offline_windows_capture_uses_windows_paths_on_linux(self):
        self.assertTrue(self.verify_report(self.report())['passed'])

    def test_offline_capture_rejects_missing_raw_evidence(self):
        report = self.report()
        report['raw_modules'] = []
        with self.assertRaisesRegex(RuntimeError, 'raw memory-map'):
            self.verify_report(report)

    def test_offline_capture_rejects_system_runtime_even_if_claimed_local(self):
        report = self.report()
        path = r'C:\Windows\System32\msvcp140.dll'
        report['module_paths'][2] = path
        report['raw_modules'][2]['path'] = path
        with self.assertRaisesRegex(RuntimeError, 'outside package bin'):
            self.verify_report(report)

    def test_offline_capture_rejects_wrong_executable_and_hash(self):
        for key, value in [('executable_name', 'showpsisi-qt.exe'), ('executable', r'C:\elsewhere\showpsisi-core.exe'),
                           ('executable_sha256', '0' * 64), ('schema_version', True), ('pid', True)]:
            report = self.report()
            report[key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.verify_report(report)

    def test_offline_capture_rejects_forged_runtime_hash_and_closure(self):
        report = self.report()
        report['runtime']['modules']['msvcp140.dll']['sha256'] = '0' * 64
        with self.assertRaisesRegex(RuntimeError, 'hash-bound'):
            self.verify_report(report)
        report = self.report()
        report['runtime']['required_modules'] = []
        with self.assertRaisesRegex(RuntimeError, 'closure'):
            self.verify_report(report)

    def test_offline_capture_rejects_lost_or_fabricated_module_paths(self):
        report = self.report()
        report['raw_modules'].pop()
        with self.assertRaisesRegex(RuntimeError, 'differ from raw'):
            self.verify_report(report)

    def test_offline_capture_rejects_missing_or_invalid_process_time(self):
        for key, value in [('sampled_at_utc', '2026-10-19T11:00:00'), ('sampled_at_utc', 'invalid'),
                           ('process_created_unix', True), ('process_created_unix', float('nan')),
                           ('process_created_unix', float('inf')), ('command_line', [])]:
            report = self.report()
            report[key] = value
            with self.subTest(key=key, value=value), self.assertRaisesRegex(RuntimeError, 'process/time'):
                self.verify_report(report)

    def test_capture_rejects_non_windows_before_touching_output(self):
        destination = self.root / 'should not exist.json'
        with mock.patch.object(runtime, '_windows_host', return_value=False), self.assertRaisesRegex(RuntimeError, 'requires Windows'):
            runtime.capture_loaded_modules(SimpleNamespace(pid=1), self.package, destination)
        self.assertFalse(destination.exists())

    def test_live_capture_retains_raw_maps_when_verification_fails(self):
        exe = str(self.bindir / 'showpsisi-core.exe')
        target = SimpleNamespace(exe=lambda: exe, create_time=lambda: 1.0, cmdline=lambda: [exe],
                                 memory_maps=lambda grouped: [SimpleNamespace(path=exe, _asdict=lambda: {'path': exe})])
        destination = self.root / 'failed capture.json'
        with mock.patch.object(runtime, '_windows_host', return_value=True), mock.patch.dict(sys.modules, {'psutil': SimpleNamespace(Process=lambda pid: target)}), mock.patch.object(runtime, 'verify_loaded_modules', side_effect=RuntimeError('outside package bin')):
            with self.assertRaisesRegex(RuntimeError, 'outside package bin'):
                runtime.capture_loaded_modules(SimpleNamespace(pid=1), self.package, destination)
        report = json.loads(destination.read_text())
        self.assertFalse(report['passed'])
        self.assertEqual(report['raw_modules'], [{'path': exe}])
        self.assertEqual(report['module_paths'], [exe])
        self.assertIn('outside package bin', report['error'])

    def test_capture_refuses_stale_evidence(self):
        destination = self.root / 'old.json'
        destination.write_text('previous evidence')
        with mock.patch.object(runtime, '_windows_host', return_value=True), self.assertRaisesRegex(RuntimeError, 'stale'):
            runtime.capture_loaded_modules(SimpleNamespace(pid=1), self.package, destination)
        self.assertEqual(destination.read_text(), 'previous evidence')

    def test_launcher_never_uses_system_crt_or_changes_security(self):
        path = ROOT / 'scripts/portable/Launch Qt.cmd'
        text = path.read_text()
        script = launcher.command(path)
        self.assertEqual(script.count('$env:SHOWPSISI_PACKAGE_ROOT'), 1)
        self.assertNotIn('$env:SystemRoot', script)
        for name in runtime.RUNTIME_NAMES:
            self.assertIn(name, script)
        for token in ('14.51.36231.0', '14.51.36247.0', '10.0.17763.0', 'Get-FileHash', 'ToUInt16', 'AMD64'):
            self.assertIn(token, script)
        self.assertIn('Get-CimInstance -ClassName Win32_Processor -Property Architecture -OperationTimeoutSec 5', script)
        self.assertIn('$_.Architecture -ne 9', script)
        self.assertIn('Native x64 platform check needs local Windows WMI; query unavailable:', script)
        self.assertNotIn('-ComputerName', script)
        self.assertNotIn('-CimSession', script)
        self.assertNotIn('RuntimeInformation', script)
        self.assertNotIn('PROCESSOR_ARCHITECTURE', script)
        for forbidden in ('ExecutionPolicy', 'Invoke-WebRequest', 'Start-Process', 'runas', 'Set-ItemProperty'):
            self.assertNotIn(forbidden, script)
        self.assertLess(text.index('if errorlevel 1 goto runtime_not_ready'), text.index('start "" /wait'))
        self.assertLess(text.index('if not errorlevel 0 goto runtime_not_ready'), text.index('start "" /wait'))
        self.assertLess(max(map(len, text.splitlines())), 8191)

    def test_fixture_replaces_only_one_package_binding(self):
        production = launcher.command(ROOT / 'scripts/portable/Launch Qt.cmd')
        fixture = launcher.fixture_command(production)
        self.assertEqual(fixture.replace('$env:SHOWPSISI_PREFLIGHT_FIXTURE_ROOT', '$env:SHOWPSISI_PACKAGE_ROOT'), production)
        for bad in ('missing binding', '$env:SHOWPSISI_PACKAGE_ROOT; $env:SHOWPSISI_PACKAGE_ROOT'):
            with self.assertRaisesRegex(RuntimeError, 'one DLL root'):
                launcher.fixture_command(bad)

    def test_adversarial_preflight_cases_cover_actual_applocal_defects(self):
        for name in ('missing-runtime-blocked', 'old-runtime-blocked', 'corrupted-runtime-blocked',
                     'invalid-pe-blocked', 'wrong-architecture-blocked', 'metadata-mode-blocked', 'missing-metadata-blocked'):
            code, error, fixture = launcher.REQUIRED_CASES[name]
            self.assertEqual(code, 1)
            self.assertTrue(error)
            self.assertTrue(fixture)

    def test_preflight_timeout_retains_raw_output_and_failed_case(self):
        artifacts = self.root / 'timeout evidence'
        (self.package / 'manifest.json').write_text('{}')
        failure = subprocess.TimeoutExpired(['powershell.exe'], 30, output=b'partial\xff output', stderr=b'partial error')
        with mock.patch.object(launcher, '_windows_host', return_value=True), mock.patch.object(launcher, 'host_runtime_inventory', return_value={}), mock.patch.dict(launcher.os.environ, {'SystemRoot': str(self.root)}), mock.patch.object(launcher.subprocess, 'run', side_effect=failure):
            with self.assertRaises(subprocess.TimeoutExpired):
                launcher.probe(ROOT / 'scripts/portable/Launch Qt.cmd', artifacts, self.package)
        report = json.loads((artifacts / 'preflight.json').read_text())
        self.assertFalse(report['passed'])
        self.assertEqual(report['cases'][0]['name'], 'package-runtime-ready')
        self.assertIsNone(report['cases'][0]['exit_code'])
        self.assertTrue(report['cases'][0]['timed_out'])
        self.assertEqual(report['cases'][0]['stdout_hex'], b'partial\xff output'.hex())
        self.assertEqual(report['cases'][0]['stderr_hex'], b'partial error'.hex())

    def test_old_version_patch_is_bounded_and_changes_only_fixed_file_version(self):
        data = bytearray(120)
        offset = 32
        struct.pack_into('<I', data, offset, 0xfeef04bd)
        changed = launcher.patch_fixed_version(data, offset, '14.50.0.0')
        self.assertEqual(changed[:offset + 8], data[:offset + 8])
        self.assertEqual(changed[offset + 16:], data[offset + 16:])
        self.assertEqual(struct.unpack_from('<II', changed, offset + 8), (14 << 16 | 50, 0))
        for bad_offset in (-1, 0, 100):
            with self.assertRaisesRegex(RuntimeError, 'complete VS_FIXEDFILEINFO'):
                launcher.patch_fixed_version(data, bad_offset, '14.50.0.0')


if __name__ == '__main__':
    unittest.main()
