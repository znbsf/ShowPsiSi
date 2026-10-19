"""Platform-independent installer fail-closed gate/asset contract regressions."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/ci'))
import installer_checks as installer
import portable_checks as portable
import inno_compiler


class InnoCompilerTests(unittest.TestCase):
    def test_loaded_engine_version_is_independent_of_zero_driver_pe_version(self):
        for version in ('6.3.0', '6.7.1'):
            self.assertEqual(inno_compiler.parse_version(
                f'Inno Setup 6 Command-Line Compiler\nCompiler engine version: Inno Setup {version}\n'), version)

    def test_missing_ambiguous_prerelease_or_unsupported_engine_is_rejected(self):
        for value in ('', 'Inno Setup 6 Command-Line Compiler\n',
                      'Compiler engine version: Inno Setup 6.2.2\n',
                      'Compiler engine version: Inno Setup 7.0.0\n',
                      'Compiler engine version: Inno Setup 6.7.1-beta\n',
                      'Compiler engine version: Inno Setup 6.7.1\n' * 2):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                inno_compiler.parse_version(value)

    def test_probe_disables_output_and_hashes_actual_engine_components(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('ISCC.exe', 'ISCmplr.dll', 'ISPP.dll'):
                (root / name).write_bytes(b'unit fixture, not an actual Windows binary')
            result = mock.Mock(returncode=0, stdout='Compiler engine version: Inno Setup 6.7.1\n')
            with mock.patch.object(inno_compiler.subprocess, 'run', return_value=result) as run:
                record = inno_compiler.identity(root / 'ISCC.exe')
            self.assertEqual(record['version'], '6.7.1')
            self.assertEqual(set(record['files_sha256']), {'ISCC.exe', 'ISCmplr.dll', 'ISPP.dll'})
            self.assertEqual(run.call_args.args[0][1:], ['/O-', '-'])
            self.assertIn('Output=no', run.call_args.kwargs['input'])
            self.assertIn('Ver < 0x06030000 || Ver >= 0x07000000', run.call_args.kwargs['input'])

    def test_failed_probe_cannot_supply_a_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('ISCC.exe', 'ISCmplr.dll', 'ISPP.dll'):
                (root / name).write_bytes(b'unit fixture')
            result = mock.Mock(returncode=2, stdout='Compiler engine version: Inno Setup 6.7.1\nError')
            with mock.patch.object(inno_compiler.subprocess, 'run', return_value=result), self.assertRaisesRegex(RuntimeError, 'probe failed'):
                inno_compiler.identity(root / 'ISCC.exe')

    def test_missing_compiler_component_fails_before_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            compiler = Path(directory) / 'ISCC.exe'
            compiler.write_bytes(b'unit fixture')
            with mock.patch.object(inno_compiler.subprocess, 'run') as run, self.assertRaises(FileNotFoundError):
                inno_compiler.identity(compiler)
            run.assert_not_called()


class InstallerPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.package = self.root / 'payload 空间'
        self.package.mkdir()
        # Use the real manifest's required-file policy, with fake bytes only in
        # unit fixtures. This does not approve any actual Windows binaries.
        import test_portable_package
        fixture = test_portable_package.PortablePackageTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        self.package = fixture.package
        self.evidence = fixture.artifacts
        self.fixture = fixture
        (self.package / 'build-information.json').write_text(json.dumps({
            'source_commit': 'a' * 40, 'application_version': '0.1.0', 'crt_mode': 'Prerequisite',
            'crt_minimum_version': installer.MINIMUM_RUNTIME}))
        fixture.approve_fixture()
        self.prerequisite = self.root / 'vc-runtime.json'
        self.runtime = {'schema_version': 1,
                        'official_source': 'https://aka.ms/vc14/vc_redist.x64.exe',
                        'url': 'https://download.visualstudio.microsoft.com/download/pr/fixture/vc_redist.x64.exe',
                        'sha256': 'b' * 64, 'signature_status': 'Valid',
                        'signer_subject': 'CN=Microsoft Corporation, O=Microsoft Corporation, C=US',
                        'minimum_version': installer.MINIMUM_RUNTIME, 'version': '14.51.36247.0'}
        self.prerequisite.write_text(json.dumps(self.runtime))

    def tearDown(self):
        self.temporary.cleanup()

    def prepare(self, **kwargs):
        return installer.prepare(self.package, self.evidence, self.prerequisite, '0.1.0',
                                 self.root / 'generated', self.root / 'output', source_commit=kwargs.pop('source_commit', 'a' * 40), **kwargs)

    def test_exact_payload_produces_stable_asset_and_installed_marker(self):
        result = self.prepare()
        self.assertEqual(result['asset_name'], 'ShowPsiSi-0.1.0-windows-x64-setup.exe')
        generated = self.root / 'generated'
        marker = json.loads((generated / 'showpsisi-installation.json').read_text())
        self.assertEqual(marker['app_id'], installer.APP_ID)
        self.assertEqual(marker['version'], '0.1.0')
        files = (generated / 'payload-files.iss').read_text(encoding='utf-8-sig')
        self.assertIn('manifest.json', files)
        self.assertIn('showpsisi-installation.json', files)
        self.assertNotIn('vc_redist.x64.exe', files)
        self.assertNotIn('*', files)
        self.assertEqual(len(files.splitlines()), len(portable.inventory(self.package)) + 2)

    def test_old_version_fixture_cannot_have_release_asset_name(self):
        result = self.prepare(upgrade_fixture=True)
        self.assertTrue(result['test_fixture'])
        self.assertEqual(result['version'], '0.0.0')
        self.assertEqual(result['asset_name'], 'TEST-ONLY-previous-version.exe')

    def test_old_stage_cannot_be_wrapped_for_a_different_commit(self):
        with self.assertRaisesRegex(RuntimeError, 'source commit'):
            self.prepare(source_commit='b' * 40)

    def test_old_payload_cannot_be_registered_as_a_new_version(self):
        with self.assertRaisesRegex(RuntimeError, 'version does not match'):
            installer.prepare(self.package, self.evidence, self.prerequisite, '0.2.0',
                              self.root / 'generated', self.root / 'output', 'a' * 40)

    def test_incomplete_review_cannot_generate_installer(self):
        (self.package / 'redistribution-review.json').write_text('{"review_complete":false}')
        portable.manifest(self.package)
        self.fixture.validation()
        with self.assertRaisesRegex(RuntimeError, 'redistribution review'):
            self.prepare()
        self.assertFalse((self.root / 'generated').exists())

    def test_new_dll_cannot_be_smuggled_through_installer(self):
        (self.package / 'bin/unreviewed.dll').write_text('new')
        portable.manifest(self.package)
        self.fixture.validation()
        with self.assertRaisesRegex(RuntimeError, 'redistribution review'):
            self.prepare()

    def test_changed_sources_or_notices_invalidate_installer(self):
        (self.package / 'SOURCE_INFORMATION.txt').write_text('changed')
        portable.manifest(self.package)
        self.fixture.validation()
        with self.assertRaisesRegex(RuntimeError, 'redistribution review'):
            self.prepare()

    def test_new_manifest_without_matching_runtime_validation_is_rejected(self):
        (self.package / 'api/tools.json').write_text('new')
        portable.manifest(self.package)
        with self.assertRaisesRegex(RuntimeError, 'fresh portable runtime validation'):
            self.prepare()

    def test_tampered_payload_is_rejected(self):
        (self.package / 'bin/showpsisi-core.exe').write_text('modified')
        with self.assertRaisesRegex(RuntimeError, 'changed after manifest'):
            self.prepare()

    def test_too_old_validation_host_is_rejected(self):
        value = json.loads((self.evidence / 'portable-validation.json').read_text())
        value['runtime_requirement']['satisfied'] = False
        (self.evidence / 'portable-validation.json').write_text(json.dumps(value))
        with self.assertRaisesRegex(RuntimeError, 'host does not satisfy'):
            self.prepare()

    def test_prerequisite_requires_fixed_official_url(self):
        for url in ('https://aka.ms/vc14/vc_redist.x64.exe',
                    'http://download.microsoft.com/vc_redist.x64.exe',
                    'https://download.microsoft.com.attacker.invalid/vc_redist.x64.exe',
                    'https://attacker@download.microsoft.com/vc_redist.x64.exe',
                    'https://download.microsoft.com:8443/vc_redist.x64.exe',
                    'https://download.microsoft.com/other.exe'):
            with self.subTest(url=url), self.assertRaises(RuntimeError):
                installer.verify_prerequisite(dict(self.runtime, url=url))

    def test_prerequisite_requires_hash_signature_and_sufficient_version(self):
        for changed in ({'sha256': ''}, {'signature_status': 'UnknownError'},
                        {'signer_subject': 'CN=Microsoft Corporation, O=Attacker'},
                        {'version': '14.44.35211.0'}, {'minimum_version': '14.0.0.0'}):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                installer.verify_prerequisite(dict(self.runtime, **changed))

    def test_installer_input_injection_is_rejected(self):
        for text in ('file"; Flags: deleteafterinstall', 'file\n[Run]', 'path\x00name'):
            with self.assertRaises(RuntimeError):
                installer.safe_iss(text)
        self.assertEqual(installer.safe_iss('x{tmp}y', constants=True), 'x{{tmp}y')

    def test_installed_payload_is_compared_to_exact_manifest(self):
        import shutil
        installed = self.root / 'installed'
        shutil.copytree(self.package, installed)
        installer.verify_installed(self.package, installed)
        (installed / 'bin/showpsisi-core.exe').write_text('wrong')
        with self.assertRaisesRegex(RuntimeError, 'Installed payload differs'):
            installer.verify_installed(self.package, installed)

    def test_silent_install_does_not_download_or_elevate(self):
        code = (ROOT / 'scripts/installer/ShowPsiSi.iss').read_text()
        silent = code.index('if WizardSilent then begin')
        prompt = code.index('if MsgBox(')
        download = code.index('DownloadPage.Download;')
        launch = code.index("ShellExec('runas'")
        self.assertLess(silent, prompt)
        self.assertLess(prompt, download)
        self.assertLess(download, launch)
        self.assertIn("'/install /norestart'", code)
        self.assertNotIn('/quiet', code)
        self.assertNotIn('/passive', code)
        self.assertNotIn('[UninstallDelete]', code)
        self.assertIn('PrivilegesRequired=lowest', code)
        self.assertIn('ArchitecturesAllowed=x64os', code)
        self.assertIn('ArchitecturesInstallIn64BitMode=x64os', code)
        self.assertNotIn('x64compatible', code)
        self.assertIn('CloseApplications=no', code)
        self.assertIn('AppMutex=Local\\ShowPsiSi.ApplicationLifetime', code)

    def test_work_and_output_cannot_modify_reviewed_payload(self):
        for generated, output in ((self.package / 'generated', self.root / 'out'),
                                  (self.root / 'generated', self.package / 'out')):
            with self.subTest(generated=generated, output=output), self.assertRaisesRegex(RuntimeError, 'outside'):
                installer.prepare(self.package, self.evidence, self.prerequisite, '0.1.0', generated, output, 'a' * 40)

    def test_non_windows_smoke_never_claims_pass(self):
        with mock.patch.object(installer.os, 'name', 'posix'):
            with self.assertRaisesRegex(RuntimeError, 'requires Windows'):
                installer.smoke(Path('setup.exe'), Path('previous.exe'), self.package,
                                self.root / 'smoke', '0.1.0')


if __name__ == '__main__':
    unittest.main()
