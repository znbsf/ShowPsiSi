"""Fail-closed installer input checks and Windows install/upgrade/uninstall smoke.

The existing portable manifest and exact third-party review remain authoritative.
Generated setup files do not add Microsoft binaries to the reviewed payload.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import urlsplit

import portable_checks as portable

APP_ID = '{13C6E0A2-B226-4BAA-A218-8DD167D78D4C}'
UNINSTALL_KEY = 'Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\' + APP_ID + '_is1'
MINIMUM_RUNTIME = '14.51.36231.0'


def version_tuple(value, count=4):
    if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+){' + str(count - 1) + '}', value):
        raise RuntimeError('Invalid numeric version')
    numbers = tuple(map(int, value.split('.')))
    if any(n > 65535 for n in numbers):
        raise RuntimeError('Version component exceeds Windows version range')
    return numbers


def verify_prerequisite(value):
    if value.get('schema_version') != 1:
        raise RuntimeError('Unsupported prerequisite metadata')
    if value.get('official_source') != 'https://aka.ms/vc14/vc_redist.x64.exe':
        raise RuntimeError('Unexpected prerequisite source')
    url = urlsplit(value.get('url', ''))
    if (url.scheme != 'https' or url.hostname not in ('download.visualstudio.microsoft.com', 'download.microsoft.com')
            or url.username or url.password or url.port not in (None, 443) or url.fragment
            or not url.path.lower().endswith('/vc_redist.x64.exe')):
        raise RuntimeError('Prerequisite URL is not the fixed official Microsoft x64 download')
    if not re.fullmatch(r'[a-f0-9]{64}', value.get('sha256', '')):
        raise RuntimeError('Prerequisite SHA-256 is required')
    if value.get('signature_status') != 'Valid' or not re.search(
            r'(^|,\s*)O=Microsoft Corporation(,|$)', value.get('signer_subject', '')):
        raise RuntimeError('Verified Microsoft Authenticode signature is required')
    if (value.get('minimum_version') != MINIMUM_RUNTIME or
            version_tuple(value.get('version')) < version_tuple(MINIMUM_RUNTIME)):
        raise RuntimeError('Prerequisite runtime is older than the required minimum')
    return value


def gate(package, artifacts, source_commit, version):
    value = portable.verify_manifest(package)
    if not re.fullmatch(r'[a-f0-9]{40}', source_commit or '') or value['build'].get('source_commit') != source_commit:
        raise RuntimeError('Installer source commit does not match the validated package')
    if value['build'].get('application_version') != version:
        raise RuntimeError('Installer version does not match the validated package')
    validation = json.loads((artifacts / 'portable-validation.json').read_text(encoding='utf-8'))
    if (validation.get('passed') is not True or
            validation.get('package_manifest_sha256') != portable.digest(package / 'manifest.json')):
        raise RuntimeError('Installer requires fresh portable runtime validation bound to its exact manifest')
    if validation.get('runtime_requirement', {}).get('satisfied') is not True:
        raise RuntimeError('Installer input validation host does not satisfy the runtime requirement')
    review = json.loads((package / 'redistribution-review.json').read_text(encoding='utf-8-sig'))
    if review.get('review_complete') is not True or review.get('reviewed_files') != portable.review_inventory(value):
        raise RuntimeError('Installer blocked: exact runtime/source/notice redistribution review is incomplete')
    if value['build'].get('crt_mode') != 'Prerequisite':
        raise RuntimeError('This installer implements the reviewed prerequisite route only')
    if value['build'].get('crt_minimum_version') != MINIMUM_RUNTIME:
        raise RuntimeError('Installer minimum runtime does not match the validated payload')
    return value


def safe_iss(value, constants=False):
    value = str(value)
    if any(c in value for c in ('"', '\n', '\r', '\x00')):
        raise RuntimeError('Invalid installer input string')
    return value.replace('{', '{{') if constants else value


def prepare(package, artifacts, prerequisite, version, generated, output, source_commit, upgrade_fixture=False):
    version_tuple(version, 3)
    if generated.resolve().is_relative_to(package.resolve()) or output.resolve().is_relative_to(package.resolve()):
        raise RuntimeError('Installer work/output must be outside the immutable package tree')
    manifest = gate(package, artifacts, source_commit, version)
    runtime = verify_prerequisite(json.loads(prerequisite.read_text(encoding='utf-8-sig')))
    generated.mkdir(parents=True, exist_ok=False)
    # The former-version fixture exercises actual Inno upgrade bookkeeping; it is
    # deliberately named TEST-ONLY and never included in release upload/checksums.
    effective_version = '0.0.0' if upgrade_fixture else version
    basename = ('TEST-ONLY-previous-version' if upgrade_fixture else
                f'ShowPsiSi-{version}-windows-x64-setup')
    defines = {'AppVersion': effective_version, 'PackageRoot': package.resolve(),
               'InstallerOutput': output.resolve(), 'InstallerBaseName': basename,
               'VcMinimum': MINIMUM_RUNTIME, 'VcUrl': runtime['url'], 'VcSha256': runtime['sha256']}
    (generated / 'generated.iss').write_text('\n'.join(
        f'#define {key} "{safe_iss(value)}"' for key, value in defines.items()) + '\n', encoding='utf-8-sig')
    marker = {'schema_version': 1, 'app_id': APP_ID, 'installer': 'inno', 'frontend': 'qt',
              'channel': 'stable', 'version': effective_version,
              'source_commit': manifest['build']['source_commit'], 'test_fixture': upgrade_fixture}
    marker_path = generated / 'showpsisi-installation.json'
    marker_path.write_text(json.dumps(marker, indent=2) + '\n', encoding='utf-8')
    lines = []
    for relative in sorted([*manifest['files'], 'manifest.json']):
        path = Path(relative)
        # Generate one explicit entry per manifested file, not a stale-tree wildcard.
        parent = str(path.parent).replace('/', '\\')
        dest = '{app}' + ('\\' + safe_iss(parent, True) if parent != '.' else '')
        lines.append(f'Source: "{safe_iss(package.resolve() / path, True)}"; DestDir: "{dest}"; Flags: ignoreversion')
    lines.append(f'Source: "{safe_iss(marker_path.resolve(), True)}"; DestDir: "{{app}}"; Flags: ignoreversion')
    (generated / 'payload-files.iss').write_text('\n'.join(lines) + '\n', encoding='utf-8-sig')
    shutil.copyfile(Path(__file__).parents[1] / 'installer/ShowPsiSi.iss', generated / 'ShowPsiSi.iss')
    record = {'schema_version': 1, 'version': effective_version, 'test_fixture': upgrade_fixture,
              'asset_name': basename + '.exe', 'source_commit': manifest['build']['source_commit'],
              'package_manifest_sha256': portable.digest(package / 'manifest.json'),
              'prerequisite': runtime, 'signing': 'unsigned candidate',
              'scope': 'Windows x64 Qt/core per-user installer; Tauri excluded'}
    (generated / 'installer-inputs.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return record


def verify_installed(package, installed):
    expected = portable.verify_manifest(package)
    for relative, details in expected['files'].items():
        target = installed / relative
        if not target.is_file() or portable.digest(target) != details['sha256'] or target.stat().st_size != details['bytes']:
            raise RuntimeError(f'Installed payload differs: {relative}')
    if portable.digest(package / 'manifest.json') != portable.digest(installed / 'manifest.json'):
        raise RuntimeError('Installed manifest changed')


def smoke(installer, previous, package, artifacts, version):
    if os.name != 'nt':
        raise RuntimeError('Installer smoke requires Windows; no platform pass inferred')
    import winreg
    artifacts.mkdir(parents=True, exist_ok=False)
    access = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
    def registration():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY, 0, access) as key:
                return {name: winreg.QueryValueEx(key, name)[0] for name in ('DisplayVersion', 'InstallLocation')}
        except FileNotFoundError:
            return None
    if registration():
        raise RuntimeError('Smoke refuses to touch an existing ShowPsiSi user installation')
    # The test owns these paths only on a disposable, otherwise uninstalled runner.
    import ctypes
    def shell_folder(identifier):
        buffer = ctypes.create_unicode_buffer(32768)
        if ctypes.windll.shell32.SHGetFolderPathW(None, identifier, None, 0, buffer) != 0:
            raise RuntimeError('Unable to resolve per-user shortcut folder')
        return Path(buffer.value)
    shortcuts = [shell_folder(0x02) / 'ShowPsiSi/ShowPsiSi.lnk',
                 shell_folder(0x10) / 'ShowPsiSi.lnk']
    if any(path.exists() for path in shortcuts):
        raise RuntimeError('Smoke refuses to overwrite pre-existing ShowPsiSi shortcuts')
    def verify_shortcuts(installed):
        powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        for path in shortcuts:
            if not path.is_file():
                raise RuntimeError(f'Missing per-user shortcut: {path}')
            # Constant script; the tested path is passed as environment data.
            command = "[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false; $s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:SHOWPSISI_SMOKE_LINK); $s.TargetPath"
            target = subprocess.check_output([str(powershell), '-NoProfile', '-NonInteractive', '-Command', command],
                                             env=dict(os.environ, SHOWPSISI_SMOKE_LINK=str(path)), text=True,
                                             timeout=30).strip()
            if Path(target).resolve() != (installed / 'bin/showpsisi-qt.exe').resolve():
                raise RuntimeError(f'Unexpected shortcut target: {path}')
    settings_key = 'Software\\ShowPsiSi\\ShowPsiSi'
    sentinel_name = 'installerSmokeSentinel'
    sentinel = 'preserve-' + str(time.time_ns())
    evidence = {'passed': False, 'installer_sha256': portable.digest(installer),
                'package_manifest_sha256': portable.digest(package / 'manifest.json'),
                'clean_machine_verified': False, 'native_dialogs_verified': False,
                'runtime_bootstrap_exercised': False, 'steps': []}
    result_path = artifacts / 'installer-smoke.json'
    def checkpoint():
        temporary = result_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        temporary.replace(result_path)
    def settings_preserved():
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, settings_key) as key:
            if winreg.QueryValueEx(key, sentinel_name)[0] != sentinel:
                raise RuntimeError('Installer changed application settings')
    def run_setup(path, args, label, expect_success=True):
        result = subprocess.run([str(path), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                                 '/SP-', '/NOCLOSEAPPLICATIONS', f'/LOG={artifacts / (label + ".log")}', *args],
                                timeout=240, check=False)
        if (result.returncode == 0) != expect_success:
            raise RuntimeError(f'{label} returned unexpected code {result.returncode}')
        evidence['steps'].append({'name': label, 'exit_code': result.returncode})
        checkpoint()
    with tempfile.TemporaryDirectory(prefix='ShowPsiSi installer 测试 ') as temp:
        installed = Path(temp) / 'Application 空间'
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, settings_key) as key:
            try:
                winreg.QueryValueEx(key, sentinel_name)
            except FileNotFoundError:
                pass
            else:
                raise RuntimeError('Smoke sentinel already exists; refusing overwrite')
            winreg.SetValueEx(key, sentinel_name, 0, winreg.REG_SZ, sentinel)
        checkpoint()
        try:
            # /UPDATE must never convert an unrelated directory into an installation.
            run_setup(installer, ['/UPDATE', f'/DIR={installed}'], 'reject-uninstalled-update', False)
            if registration() or installed.exists():
                raise RuntimeError('Rejected update created files or application registration')
            run_setup(previous, [f'/DIR={installed}', '/TASKS=desktopicon'], 'install-previous')
            if registration()['DisplayVersion'] != '0.0.0':
                raise RuntimeError('Former-version fixture was not installed')
            verify_installed(package, installed)
            verify_shortcuts(installed)
            settings_preserved()
            # A live app/core, including another window, must block setup and
            # uninstall before any resource or executable file is modified.
            from ctypes import wintypes
            create_mutex = ctypes.windll.kernel32.CreateMutexW
            create_mutex.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
            create_mutex.restype = wintypes.HANDLE
            close_handle = ctypes.windll.kernel32.CloseHandle
            close_handle.argtypes = (wintypes.HANDLE,)
            close_handle.restype = wintypes.BOOL
            mutex = create_mutex(None, False, 'Local\\ShowPsiSi.ApplicationLifetime')
            if not mutex:
                raise RuntimeError('Could not create installer app-lifetime smoke mutex')
            try:
                run_setup(installer, ['/UPDATE', f'/DIR={installed}'], 'reject-live-app-update', False)
                run_setup(installed / 'unins000.exe', [], 'reject-live-app-uninstall', False)
                verify_installed(package, installed)
                settings_preserved()
                if registration()['DisplayVersion'] != '0.0.0':
                    raise RuntimeError('Live-app guard changed registration')
            finally:
                close_handle(mutex)
            for label in ('upgrade', 'reinstall'):
                run_setup(installer, ['/UPDATE', f'/DIR={installed}'], label)
                current = registration()
                if current['DisplayVersion'] != version or Path(current['InstallLocation']).resolve() != installed.resolve():
                    raise RuntimeError('Version/location registration changed unexpectedly')
                verify_installed(package, installed)
                verify_shortcuts(installed)
                settings_preserved()
            run_setup(previous, ['/UPDATE', f'/DIR={installed}'], 'reject-downgrade', False)
            verify_installed(package, installed)
            settings_preserved()
            # Exercise the installed engine and actual native Qt/core process startup
            # under a scrubbed PATH, separately from offscreen package validation.
            env, cwd = os.environ.copy(), Path.cwd()
            try:
                clean = portable.clean_environment()
                os.environ.clear()
                os.environ.update(clean, SHOWPSISI_CORE=str(installed / 'bin/showpsisi-core.exe'))
                os.chdir(temp)
                evidence['installed_core'] = portable.core_probe(installed, artifacts)
                # Verify the actual production engine creates/releases the same
                # lifetime guard, rather than testing only a synthetic mutex.
                open_mutex = ctypes.windll.kernel32.OpenMutexW
                open_mutex.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR)
                open_mutex.restype = wintypes.HANDLE
                def mutex_exists():
                    handle = open_mutex(0x00100000, False, 'Local\\ShowPsiSi.ApplicationLifetime')
                    if handle:
                        close_handle(handle)
                    return bool(handle)
                if mutex_exists():
                    raise RuntimeError('Another guarded process is already running before production mutex smoke')
                proc = subprocess.Popen([str(installed / 'bin/showpsisi-core.exe'), '--root', str(installed)],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=clean)
                try:
                    deadline = time.monotonic() + 15
                    while not mutex_exists() and proc.poll() is None and time.monotonic() < deadline:
                        time.sleep(.05)
                    if not mutex_exists() or proc.poll() is not None:
                        raise RuntimeError('Production engine did not hold the installer lifetime mutex')
                    _, stderr = proc.communicate(input=b'', timeout=15)
                    if proc.returncode != 0:
                        raise RuntimeError(f'Production engine shutdown failed: {proc.returncode}, {stderr!r}')
                    deadline = time.monotonic() + 5
                    while mutex_exists() and time.monotonic() < deadline:
                        time.sleep(.05)
                    if mutex_exists():
                        raise RuntimeError('Production lifetime mutex survived process shutdown')
                    evidence['production_core_mutex'] = {'held_while_running': True, 'released_after_exit': True}
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.communicate(timeout=10)
                evidence['installed_qt_startup'] = portable.launcher_probe(installed, artifacts, clean, direct=True)
            finally:
                os.chdir(cwd)
                os.environ.clear()
                os.environ.update(env)
            settings_preserved()
            run_setup(installed / 'unins000.exe', [], 'uninstall')
            deadline = time.monotonic() + 30
            while (registration() or (installed / 'bin/showpsisi-qt.exe').exists()) and time.monotonic() < deadline:
                time.sleep(.1)
            if registration() or (installed / 'bin/showpsisi-qt.exe').exists():
                raise RuntimeError('Uninstall left owned application/registration behind')
            if any(path.exists() for path in shortcuts):
                raise RuntimeError('Uninstall left an owned shortcut behind')
            settings_preserved()
            evidence['shortcuts_verified'] = True
            evidence['settings_preserved'] = True
            evidence['passed'] = True
            checkpoint()
        except Exception as error:
            evidence['error'] = str(error)
            checkpoint()
            raise
        finally:
            # Cleanup is scoped to this test's exact directory and never changes
            # the original failure into a pass.
            if (installed / 'unins000.exe').exists():
                try:
                    run_setup(installed / 'unins000.exe', [], 'failure-cleanup')
                except Exception as cleanup_error:
                    evidence['cleanup_error'] = str(cleanup_error)
                    checkpoint()
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, settings_key, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, sentinel_name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare', 'smoke'))
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--source-commit')
    parser.add_argument('--prerequisite', type=Path)
    parser.add_argument('--generated', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--upgrade-fixture', action='store_true')
    parser.add_argument('--installer', type=Path)
    parser.add_argument('--previous', type=Path)
    args = parser.parse_args()
    if args.mode == 'prepare':
        prepare(args.package, args.artifacts, args.prerequisite, args.version, args.generated, args.output, args.source_commit, args.upgrade_fixture)
    else:
        smoke(args.installer.resolve(), args.previous.resolve(), args.package.resolve(), args.artifacts.resolve(), args.version)


if __name__ == '__main__':
    main()
