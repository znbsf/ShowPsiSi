"""Build-time portable Windows checks; never shipped as a runtime prerequisite.

Only archive() can create a distributable ZIP, and it fails closed on incomplete
license review. validate() uses a separate relocated copy including offscreen's
test plugin; its evidence cannot establish native Windows desktop acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parent))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def inventory(package):
    return {p.relative_to(package).as_posix(): {'sha256': digest(p), 'bytes': p.stat().st_size}
            for p in sorted(package.rglob('*')) if p.is_file() and p != package / 'manifest.json'}


def manifest(package):
    files = inventory(package)
    required = ['bin/showpsisi-core.exe', 'bin/showpsisi-qt.exe', 'bin/tsduck.dll',
                'bin/tscore.dll', 'bin/tsduck.tables.model.xml', 'bin/tsduck.dtv.names',
                'bin/tscore.time.xml', 'bin/tscore.ip.names', 'bin/platforms/qwindows.dll',
                'bin/qt.conf', 'bin/showpsisi-portable.json', 'api/tools.json', 'extensions/demo.json',
                'references/standards.json', 'references/satellites.json', 'samples/generated/lab.ts', 'samples/generated/lab.manifest.json', 'LICENSE',
                'THIRD_PARTY_NOTICES.txt', 'SOURCE_INFORMATION.txt', 'redistribution-review.json',
                'Launch Qt.cmd', 'README-portable.txt',
                'assets/icons/showpsisi.svg', 'assets/icons/showpsisi-256.png', 'assets/icons/showpsisi.ico']
    for name in required:
        if name not in files:
            raise RuntimeError(f'Required package file missing: {name}')
    for name in files:
        if name.lower().endswith('.exe') and name not in ('bin/showpsisi-core.exe', 'bin/showpsisi-qt.exe'):
            raise RuntimeError(f'Unexpected executable in runtime package: {name}')
        if name.lower().endswith('.dll') and not name.startswith('bin/'):
            raise RuntimeError(f'Runtime DLL outside reviewed bin directory: {name}')
        if re.search(r'core-test|qoffscreen|D3Dcompiler_47\.dll$|(^|/)qmltooling/|\.pdb$|\.lib$|\.py$|\.ps1$|(^|/)(include|tests|\.deps)/', name, re.I):
            raise RuntimeError(f'Developer/test file in runtime package: {name}')
    value = {'schema_version': 1, 'scope': 'windows-x64-qt-core',
             'build': json.loads((package / 'build-information.json').read_text(encoding='utf-8-sig')),
             'files': files, 'manifest_self_hash': 'Excluded to avoid recursive hash; ZIP has an external SHA-256.'}
    (package / 'manifest.json').write_text(json.dumps(value, indent=2), encoding='utf-8')
    return value


def verify_manifest(package):
    value = json.loads((package / 'manifest.json').read_text(encoding='utf-8'))
    if value['files'] != inventory(package):
        raise RuntimeError('Package changed after manifest generation')
    return value


def clean_environment():
    env = {k.upper(): v for k, v in os.environ.items()
           if not k.upper().startswith(('SHOWPSISI_', 'QT_', 'QML', 'TSDUCK', 'TSPLUGINS', 'TSLIB', 'TSCORE'))}
    env['PATH'] = str(Path(env['SYSTEMROOT']) / 'System32')
    return env


def pe_dependencies(package):
    import pefile  # CI tooling only, pinned by workflow
    system = Path(os.environ['SystemRoot']) / 'System32'
    prerequisite_crt = json.loads((package / 'build-information.json').read_text(encoding='utf-8-sig')).get('crt_mode') == 'Prerequisite'
    bindir = package / 'bin'
    evidence = {}
    for path in sorted(bindir.rglob('*')):
        if path.suffix.lower() not in ('.exe', '.dll'):
            continue
        pe = pefile.PE(str(path))
        try:
            if pe.FILE_HEADER.Machine != 0x8664:
                raise RuntimeError(f'Non-x64 PE file: {path}')
            imports = []
            for table in ('DIRECTORY_ENTRY_IMPORT', 'DIRECTORY_ENTRY_DELAY_IMPORT'):
                for entry in getattr(pe, table, []):
                    name = entry.dll.decode('ascii')
                    local = next((p for p in (path.parent / name, bindir / name) if p.is_file()), None)
                    crt = re.match(r'(msvcp|vcruntime|concrt|vcomp)\d', name, re.I)
                    if local:
                        source = local.relative_to(package).as_posix()
                    elif re.match(r'msvcr\d', name, re.I) and name.lower() != 'msvcrt.dll':
                        raise RuntimeError(f'Undeclared legacy CRT dependency: {path.name} -> {name}')
                    elif crt and not prerequisite_crt:
                        raise RuntimeError(f'App-local release CRT missing: {path.name} -> {name}')
                    elif name.lower().startswith(('api-ms-win-', 'ext-ms-win-')) or (system / name).is_file():
                        source = 'Windows system/API set'
                    else:
                        raise RuntimeError(f'Unresolved PE dependency: {path.name} -> {name}')
                    imports.append({'name': name, 'resolved': source})
            evidence[path.relative_to(package).as_posix()] = imports
        finally:
            pe.close()
    return evidence


def embedded_application_icon(package):
    """Resolve every Windows icon group entry to its same-language image bytes.

    Our RC emits a single original icon group. Reject malformed or unrelated
    groups too: their presence must not silently change the shell's default icon.
    """
    import pefile
    data = (package / 'assets/icons/showpsisi.ico').read_bytes()
    count = 7
    if len(data) < 6 + 16 * count or struct.unpack('<HHH', data[:6]) != (0, 1, count):
        raise RuntimeError('Application ICO must contain all seven sizes')
    expected = {}
    next_offset = 6 + 16 * count
    for index in range(count):
        fields = struct.unpack('<BBBBHHII', data[6 + 16 * index:22 + 16 * index])
        width, height, colors, reserved, planes, bits, length, offset = fields
        if (width != height or (width or 256) not in (16, 24, 32, 48, 64, 128, 256)
                or (colors, reserved, planes, bits) != (0, 0, 1, 32)
                or offset != next_offset or not length or offset + length > len(data)
                or width in expected):
            raise RuntimeError('Malformed application ICO directory')
        expected[width] = (fields[:7], data[offset:offset + length])
        next_offset += length
    if next_offset != len(data):
        raise RuntimeError('Malformed application ICO payload boundary')
    pe = pefile.PE(str(package / 'bin/showpsisi-qt.exe'))
    try:
        resources = getattr(pe, 'DIRECTORY_ENTRY_RESOURCE', None)
        if resources is None:
            raise RuntimeError('Qt executable has no embedded icon resources')
        images, groups = {}, []
        for resource in resources.entries:
            if resource.id not in (3, 14):  # RT_ICON, RT_GROUP_ICON
                continue
            for item in resource.directory.entries:
                for language in item.directory.entries:
                    entry = language.data.struct
                    payload = pe.get_data(entry.OffsetToData, entry.Size)
                    if len(payload) != entry.Size:
                        raise RuntimeError('Truncated executable icon resource')
                    if resource.id == 3:
                        key = (item.id, language.id)
                        if item.id is None or key in images:
                            raise RuntimeError('Ambiguous executable icon resource ID/language')
                        images[key] = payload
                    else:
                        groups.append((language.id, payload))
        if not groups:
            raise RuntimeError('Qt executable has no embedded icon group')
        for language, group in groups:
            if len(group) != 6 + 14 * count or struct.unpack('<HHH', group[:6]) != (0, 1, count):
                raise RuntimeError('Malformed executable icon group directory')
            seen_sizes, seen_ids = set(), set()
            for index in range(count):
                fields = struct.unpack('<BBBBHHIH', group[6 + 14 * index:20 + 14 * index])
                width, resource_id = fields[0], fields[7]
                if width not in expected or width in seen_sizes or resource_id in seen_ids:
                    raise RuntimeError('Invalid or duplicate executable icon group entry')
                metadata, payload = expected[width]
                if fields[:7] != metadata or images.get((resource_id, language)) != payload:
                    raise RuntimeError('Qt executable icon group does not match packaged original artwork')
                seen_sizes.add(width)
                seen_ids.add(resource_id)
        return {'verified': True, 'frames': count, 'groups': len(groups),
                'ico_sha256': digest(package / 'assets/icons/showpsisi.ico')}
    finally:
        pe.close()


def runtime_requirement(package):
    import pefile
    build = json.loads((package / 'build-information.json').read_text(encoding='utf-8-sig'))
    directory = package / 'bin' if build['crt_mode'] == 'AppLocal' else Path(os.environ['SystemRoot']) / 'System32'
    minimum = tuple(map(int, build['crt_minimum_version'].split('.')))
    versions = {}
    for name in ('vcruntime140.dll', 'vcruntime140_1.dll', 'msvcp140.dll', 'msvcp140_1.dll'):
        path = directory / name
        if not path.is_file():
            versions[name] = {'path': str(path), 'satisfied': False, 'error': 'missing'}
            continue
        pe = pefile.PE(str(path))
        try:
            fixed = pe.VS_FIXEDFILEINFO[0]
            version = (fixed.FileVersionMS >> 16, fixed.FileVersionMS & 65535,
                       fixed.FileVersionLS >> 16, fixed.FileVersionLS & 65535)
            versions[name] = {'path': str(path), 'version': '.'.join(map(str, version)), 'satisfied': version >= minimum}
        finally:
            pe.close()
    return {'required_minimum': build['crt_minimum_version'], 'files': versions,
            'satisfied': all(item['satisfied'] for item in versions.values())}


def system_d3d_identity():
    import pefile
    path = Path(os.environ['SystemRoot']) / 'System32/D3Dcompiler_47.dll'
    if not path.is_file():
        raise RuntimeError('Supported Windows system D3Dcompiler_47.dll is missing')
    pe = pefile.PE(str(path))
    try:
        fixed = pe.VS_FIXEDFILEINFO[0]
        version = (fixed.FileVersionMS >> 16, fixed.FileVersionMS & 65535,
                   fixed.FileVersionLS >> 16, fixed.FileVersionLS & 65535)
        return {'path': str(path), 'sha256': digest(path), 'version': '.'.join(map(str, version))}
    finally:
        pe.close()


def loaded_modules(process, package):
    import psutil
    paths = sorted({item.path for item in psutil.Process(process.pid).memory_maps()
                    if item.path.lower().endswith(('.dll', '.exe'))})
    allowed = (package.resolve(), Path(os.environ['SystemRoot']).resolve())
    for item in paths:
        path = Path(item).resolve()
        if not any(path.is_relative_to(root) for root in allowed):
            raise RuntimeError(f'Process loaded a non-package/non-Windows module: {item}')
    return paths


def core_probe(package, artifacts):
    import core_client
    core_client.ROOT = package
    source = package / 'samples/generated/lab.ts'
    before = digest(source)
    with core_client.Core() as core:
        call = lambda method, params=None: core.submit(method, params).result(timeout=30)
        capabilities = call('capabilities')
        modules = loaded_modules(core.proc, package)
        state = call('analyze', {'path': str(source)})
        assert len(state['services']) == 6, state
        assert state['crc_errors'] == 2, state
        service = state['services'][0]
        detail = call('inspect', {'id': service['source_id']})
        assert detail['raw_hex'] and detail['tsduck_xml'], detail
        comparison = call('diff_snapshots', {'from_packet': 0, 'to_packet': state['packets'] - 1})
        edit = call('preview_rename', {'id': service['source_id'], 'service_id': service['id'], 'name': 'Portable 测试'})
        exported = call('export', {'path': str(artifacts / 'portable exported.ts'), 'preview_token': edit['token'], 'cycles': 3})
        readback = call('analyze', {'path': exported['path']})
        assert readback['services'][0]['name'] == 'Portable 测试', readback
        # Production cancellation request, accepting either race outcome. The
        # deterministic gated cancellation helper is deliberately not packaged.
        pending = core.submit('analyze', {'path': str(source)})
        call('cancel_analysis', {'request_id': pending.request_id})
        try:
            pending.result(timeout=30)
            cancellation = 'completed before cancellation (allowed race)'
        except core_client.CoreError as error:
            if error.code != 'analysis_cancelled':
                raise
            cancellation = 'analysis_cancelled'
        assert len(call('analyze', {'path': str(source)})['services']) == 6
    assert core.proc.returncode == 0, core.proc.returncode
    assert digest(source) == before
    return {'capabilities': capabilities, 'modules': modules, 'comparison': comparison,
            'cancellation': cancellation, 'source_sha256_unchanged': before,
            'core_exit_code': core.proc.returncode, 'named_xml_raw_export_readback': 'passed'}


def qt_probe(package, artifacts, env):
    from qt_result import wait_for_qt_result
    result = artifacts / 'qt-result.json'
    trace = artifacts / 'qt-trace.jsonl'
    shot = artifacts / 'qt-screen.png'
    env = dict(env, SHOWPSISI_AUTO='1', SHOWPSISI_SCRIPT='smoke',
               SHOWPSISI_TEST_RESULT=str(result), SHOWPSISI_SCREENSHOT=str(shot),
               SHOWPSISI_TRACE=str(trace), SHOWPSISI_SETTINGS_PATH=str(artifacts / 'settings.ini'),
               SHOWPSISI_ARTIFACT_DIR=str(artifacts), QT_QPA_PLATFORM='offscreen',
               QT_QUICK_BACKEND='software', QT_FORCE_STDERR_LOGGING='1',
               QT_QPA_FONTDIR=str(Path(env['SYSTEMROOT']) / 'Fonts'))
    with (artifacts / 'qt.log').open('w', encoding='utf-8') as log:
        proc = subprocess.Popen([str(package / 'bin/showpsisi-qt.exe'), '--showpsisi-development'], env=env, stdout=log, stderr=log)
        try:
            report = wait_for_qt_result(result, proc, 60)
            modules = loaded_modules(proc, package)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
    assert report['passed'], report
    assert shot.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
    marks = [json.loads(line) for line in trace.read_text(encoding='utf-8').splitlines()]
    pids = {int(mark['backend_pid']) for mark in marks if mark.get('backend_pid')}
    import psutil
    for pid in pids:
        try:
            child = psutil.Process(pid)
            child.wait(timeout=10)
        except psutil.NoSuchProcess:
            pass
        except psutil.TimeoutExpired:
            # Exact launched backend only, never a name-wide process kill.
            child.kill()
            child.wait(timeout=5)
            raise RuntimeError('Qt left its packaged backend running')
    return {'report': report, 'modules': modules, 'backend_cleanup': 'passed'}


def launcher_probe(package, artifacts, env, direct=False):
    import psutil
    # Launcher must clear test/development discovery settings. Inspect its actual
    # GUI and child paths without calling this a Windows native interaction pass.
    env = dict(env, SHOWPSISI_ROOT='invalid-relative-root', SHOWPSISI_CORE='missing.exe',
               SHOWPSISI_SCRIPT='smoke', SHOWPSISI_TEST_RESULT=str(artifacts / 'must-not-exist.json'),
               QT_QPA_PLATFORM='not-a-real-platform', QT_PLUGIN_PATH='Z:/missing SDK plugins',
               QT_QPA_PLATFORM_PLUGIN_PATH='Z:/missing SDK platforms',
               QML_IMPORT_PATH='Z:/missing SDK qml', QML2_IMPORT_PATH='Z:/missing SDK qml2',
               TSPLUGINS_PATH='Z:/missing SDK tsduck', TSDUCK='Z:/missing SDK')
    cmd = Path(env['SYSTEMROOT']) / 'System32/cmd.exe'
    command = [str(package / 'bin/showpsisi-qt.exe')] if direct else [str(cmd), '/d', '/c', str(package / 'Launch Qt.cmd')]
    proc = subprocess.Popen(command, env=env)
    owned = []
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            owned = psutil.Process(proc.pid).children(recursive=True)
            if direct:
                owned = [psutil.Process(proc.pid)] + owned
            names = {p.name().lower(): p for p in owned}
            if 'showpsisi-qt.exe' in names and 'showpsisi-core.exe' in names:
                break
            if proc.poll() is not None:
                raise RuntimeError(f'CMD launcher exited early: {proc.returncode}')
            time.sleep(.1)
        else:
            raise RuntimeError('CMD launcher did not start Qt and core')
        modules = {name: loaded_modules(names[name], package)
                   for name in ('showpsisi-qt.exe', 'showpsisi-core.exe')}
        arguments = names['showpsisi-core.exe'].cmdline()[1:]
        assert len(arguments) == 2 and arguments[0] == '--root', arguments
        assert Path(arguments[1]).resolve() == package.resolve(), arguments
        assert not (artifacts / 'must-not-exist.json').exists()
        return {'process_modules': modules, 'scope': 'startup only; no native desktop interaction claimed'}
    finally:
        for child in reversed(owned):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        proc.terminate()
        proc.wait(timeout=10)
        _, alive = psutil.wait_procs(owned, timeout=10)
        for child in alive:
            child.kill()
        psutil.wait_procs(alive, timeout=5)


def validate(package, artifacts, qt):
    if artifacts.resolve().is_relative_to(package.resolve()):
        raise RuntimeError('Validation artifacts must be outside the package tree')
    if os.name != 'nt':
        raise RuntimeError('Runtime validation requires Windows; no cross-platform pass inferred')
    verify_manifest(package)
    artifacts.mkdir(parents=True, exist_ok=False)
    evidence = {'passed': False, 'native_windows_desktop_verified': False}
    def checkpoint():
        (artifacts / 'portable-validation.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    checkpoint()
    evidence['pe_dependencies'] = pe_dependencies(package)
    checkpoint()
    evidence['application_icon'] = embedded_application_icon(package)
    checkpoint()
    evidence['runtime_requirement'] = runtime_requirement(package)
    checkpoint()
    evidence['system_d3d_compiler'] = system_d3d_identity()
    checkpoint()
    # Different tree, Unicode+spaces, unrelated cwd. Nothing writes into staged ZIP inputs.
    with tempfile.TemporaryDirectory(prefix='ShowPsiSi portable 测试 ') as temporary:
        temporary = Path(temporary)
        relocated = temporary / 'Relocated app 空间'
        shutil.copytree(package, relocated)
        cwd = temporary / 'unrelated working directory'
        cwd.mkdir()
        (cwd / 'api').mkdir()
        (cwd / 'api/tools.json').write_text('misleading cwd resource, not JSON', encoding='utf-8')
        env = clean_environment()
        saved_env, saved_cwd = os.environ.copy(), Path.cwd()
        try:
            os.environ.clear()
            os.environ.update(env, SHOWPSISI_CORE=str(relocated / 'bin/showpsisi-core.exe'))
            os.chdir(cwd)
            evidence['core'] = core_probe(relocated, artifacts)
            checkpoint()
            # Offscreen is a test-only plugin injected solely into the relocated
            # copy. The manifest and final package categorically exclude it.
            shutil.copy2(qt / 'plugins/platforms/qoffscreen.dll', relocated / 'bin/platforms/qoffscreen.dll')
            evidence['qt_offscreen'] = qt_probe(relocated, artifacts, env)
            checkpoint()
            evidence['launcher_startup'] = launcher_probe(relocated, artifacts, env)
            checkpoint()
            evidence['direct_exe_startup'] = launcher_probe(relocated, artifacts, env, direct=True)
            checkpoint()
        finally:
            os.chdir(saved_cwd)
            os.environ.clear()
            os.environ.update(saved_env)
    verify_manifest(package)
    evidence['passed'] = True
    evidence['package_manifest_sha256'] = digest(package / 'manifest.json')
    (artifacts / 'portable-validation.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')


def review_inventory(value):
    # Our newly built EXEs/configuration are source-commit + test-manifest bound.
    # Review third-party libraries, QML/plugin/data, and exact notice/source bytes;
    # otherwise freshly built executable hashes would create a circular CI gate.
    own_files = {'bin/showpsisi-core.exe', 'bin/showpsisi-qt.exe', 'bin/qt.conf', 'bin/showpsisi-portable.json'}
    return {name: entry['sha256'] for name, entry in value['files'].items()
            if (name.startswith('bin/') and name not in own_files)
            or name.startswith(('licenses/', 'sources/'))
            or name in ('THIRD_PARTY_NOTICES.txt', 'SOURCE_INFORMATION.txt', 'source-index.json')}


def portable_asset_name(version):
    if not isinstance(version, str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise RuntimeError('Portable release requires a canonical application version')
    return f'ShowPsiSi-{version}-windows-x64-portable.zip'


def archive(package, artifacts, output):
    if output.resolve().is_relative_to(package.resolve()) or output.with_suffix(output.suffix + '.sha256').resolve().is_relative_to(package.resolve()):
        raise RuntimeError('Archive and checksum must be outside the package tree')
    if output.exists():
        raise RuntimeError(f'Refusing existing/stale archive: {output}')
    value = verify_manifest(package)
    if output.name != portable_asset_name(value['build'].get('application_version')):
        raise RuntimeError('Portable asset name does not match its application version')
    validation = json.loads((artifacts / 'portable-validation.json').read_text(encoding='utf-8'))
    if not validation.get('passed') or validation.get('package_manifest_sha256') != digest(package / 'manifest.json'):
        raise RuntimeError('Runtime validation has not passed')
    if not validation.get('runtime_requirement', {}).get('satisfied'):
        status = {'archive_created': False, 'runtime_gate': 'blocked',
                  'reason': 'Test host/app-local VC runtime does not satisfy the documented minimum version.'}
        (artifacts / 'distribution-gate.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
        print(status['reason'])
        return False
    review = json.loads((package / 'redistribution-review.json').read_text(encoding='utf-8-sig'))
    # Bind approval to exact runtime bytes, including plugins/data. A generic
    # review_complete=true switch cannot approve unknown dependencies or future changes.
    runtime = review_inventory(value)
    approved = review.get('review_complete') is True and review.get('reviewed_files') == runtime
    if not approved:
        status = {'archive_created': False, 'license_gate': 'blocked', 'reason': review.get('reason', 'Exact runtime review absent')}
        (artifacts / 'distribution-gate.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
        print('Binary ZIP/upload blocked: exact runtime redistribution review is incomplete.')
        return False
    if output.exists():
        raise RuntimeError(f'Refusing to replace existing archive: {output}')
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive_file:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                archive_file.write(path, 'ShowPsiSi-windows-x64/' + path.relative_to(package).as_posix())
    output.with_suffix(output.suffix + '.sha256').write_text(f'{digest(output)}  {output.name}\n', encoding='ascii')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['manifest', 'validate', 'archive'])
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path)
    parser.add_argument('--qt', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    if args.mode == 'manifest':
        manifest(package)
    elif args.mode == 'validate':
        validate(package, args.artifacts.resolve(), args.qt.resolve())
    else:
        archive(package, args.artifacts.resolve(), args.output.resolve())


if __name__ == '__main__':
    main()
