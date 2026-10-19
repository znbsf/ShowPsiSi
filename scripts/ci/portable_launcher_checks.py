"""Exercise the exact portable CMD preflight against isolated app-local fixtures.

The host's SystemRoot, shared runtime and security settings are never changed.
Corrupt/old PE fixtures are read as data only and never loaded or executed.
The exact command uses inbox Windows PowerShell 5.1 and a bounded local WMI
processor-architecture read; no CIM server/session or runtime download is used.
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
import tempfile

import windows_runtime_modules as runtime


# (expected exit status, expected stderr fragment, fixture-root substitution)
REQUIRED_CASES = {
    'package-runtime-ready': (0, '', False),
    'relocated-runtime-ready': (0, '', True),
    'missing-runtime-blocked': (1, 'Missing bundled runtime:', True),
    'old-runtime-blocked': (1, 'Bundled runtime too old:', True),
    'corrupted-runtime-blocked': (1, 'Corrupt bundled runtime (SHA-256 mismatch):', True),
    'invalid-pe-blocked': (1, 'Corrupt bundled runtime (invalid PE header):', True),
    'wrong-architecture-blocked': (1, 'Bundled runtime is not an x64 DLL:', True),
    'metadata-mode-blocked': (1, 'Invalid bundled runtime metadata', True),
    'missing-metadata-blocked': (1, 'Missing bundled runtime metadata:', True),
}


def _windows_host():
    return os.name == 'nt'


def command(launcher):
    matches = re.findall(r'^"%SystemRoot%[^\r\n]+ -Command "([^\r\n]+)"$',
                         launcher.read_text(encoding='utf-8'), re.MULTILINE)
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one portable runtime preflight command')
    return matches[0]


def fixture_command(script):
    # The PowerShell process still uses the real SystemRoot. Substitute only
    # its read-only package-root binding, never the executable or host DLLs.
    if script.count('$env:SHOWPSISI_PACKAGE_ROOT') != 1:
        raise RuntimeError('Expected one DLL root binding in the production preflight')
    return script.replace('$env:SHOWPSISI_PACKAGE_ROOT', '$env:SHOWPSISI_PREFLIGHT_FIXTURE_ROOT')


def patch_fixed_version(data, offset, version):
    """Patch an isolated VS_FIXEDFILEINFO record, not any executable on the host."""
    if offset < 0 or offset + 52 > len(data) or struct.unpack_from('<I', data, offset)[0] != 0xfeef04bd:
        raise RuntimeError('Version fixture lacks a complete VS_FIXEDFILEINFO structure')
    values = runtime.version_tuple(version)
    if any(value > 65535 for value in values):
        raise RuntimeError('Version fixture component exceeds a WORD')
    changed = bytearray(data)
    struct.pack_into('<II', changed, offset + 8, values[0] << 16 | values[1], values[2] << 16 | values[3])
    return bytes(changed)


def old_version_fixture(source):
    import pefile
    pe = pefile.PE(str(source))
    try:
        offset = pe.VS_FIXEDFILEINFO[0].get_file_offset()
    finally:
        pe.close()
    return patch_fixed_version(source.read_bytes(), offset, '14.50.0.0')


def host_runtime_inventory(system_root):
    """Read-only diagnostics, never acceptance evidence for the bundled runtime."""
    value = {}
    for name in runtime.RUNTIME_NAMES:
        path = Path(system_root) / 'System32' / name
        entry = {'path': str(path), 'exists': path.is_file()}
        if path.is_file():
            entry.update(bytes=path.stat().st_size, sha256=runtime.sha256(path))
            try:
                entry.update(runtime.pe_identity(path))
            except RuntimeError as error:
                entry['error'] = str(error)
        value[name] = entry
    return value


def probe(launcher, artifacts, package=None):
    if not _windows_host():
        raise RuntimeError('Portable runtime preflight probe requires Windows')
    launcher, artifacts = Path(launcher), Path(artifacts)
    package = Path(package) if package is not None else launcher.parent
    if artifacts.resolve().is_relative_to(package.resolve()):
        raise RuntimeError('Preflight evidence must be outside the package')
    artifacts.mkdir(parents=True, exist_ok=False)
    record = {'schema_version': 1, 'passed': False, 'mode': 'AppLocal',
              'launcher_sha256': hashlib.sha256(launcher.read_bytes()).hexdigest(),
              'package_root': str(package.resolve()), 'cases': [],
              'clean_machine_verified': False}
    def checkpoint():
        temporary = artifacts / 'preflight.json.tmp'
        temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        temporary.replace(artifacts / 'preflight.json')
    def run(root, name):
        expected_code, expected_error, fixture = REQUIRED_CASES[name]
        selected = fixture_command(script) if fixture else script
        value = {'name': name, 'exit_code': None,
                 'fixture_root_binding': fixture, 'fixture_root': str(root),
                 'stdout_hex': '', 'stderr_hex': '', 'stdout': '', 'stderr': ''}
        record['cases'].append(value)
        checkpoint()
        try:
            result = subprocess.run([str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', selected],
                                    env=dict(os.environ, SHOWPSISI_PACKAGE_ROOT=str(package.resolve()),
                                             SHOWPSISI_PREFLIGHT_FIXTURE_ROOT=str(root)),
                                    capture_output=True, timeout=30)
            value['exit_code'] = result.returncode
            stdout, stderr = result.stdout, result.stderr
        except subprocess.TimeoutExpired as error:
            stdout, stderr = error.stdout or b'', error.stderr or b''
            value.update(timed_out=True, error=str(error), stdout_hex=stdout.hex(), stderr_hex=stderr.hex(),
                         stdout=stdout.decode('utf-8', errors='backslashreplace'),
                         stderr=stderr.decode('utf-8', errors='backslashreplace'))
            checkpoint()
            raise
        value.update(stdout_hex=stdout.hex(), stderr_hex=stderr.hex(),
                     stdout=stdout.decode('utf-8', errors='backslashreplace'),
                     stderr=stderr.decode('utf-8', errors='backslashreplace'))
        # Raw subprocess evidence is durable even if its assertion then fails.
        checkpoint()
        if result.returncode != expected_code or expected_error not in value['stderr']:
            raise RuntimeError(f'Portable preflight case failed: {name}: {value}')
    checkpoint()
    try:
        script = command(launcher)
        system_root = os.environ['SystemRoot']
        powershell = Path(system_root) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        record['package_manifest_sha256'] = runtime.sha256(package / 'manifest.json')
        record['runtime'] = runtime.inspect_runtime(package)
        record['host_runtime_before'] = host_runtime_inventory(system_root)
        checkpoint()
        run(package, 'package-runtime-ready')
        with tempfile.TemporaryDirectory(prefix='ShowPsiSi bundled runtime 测试 ') as directory:
            root = Path(directory) / 'relocated package 空间'
            bindir = root / 'bin'
            bindir.mkdir(parents=True)
            metadata = bindir / runtime.METADATA_NAME
            shutil.copyfile(package / 'bin' / runtime.METADATA_NAME, metadata)
            for name in runtime.RUNTIME_NAMES:
                shutil.copyfile(package / 'bin' / name, bindir / name)
            run(root, 'relocated-runtime-ready')
            # Exercise the Qt-specific transitive dependency as well as the
            # primary runtime. No fixture inherits any system DLL fallback.
            target = bindir / 'msvcp140_2.dll'
            original = target.read_bytes()
            target.unlink()
            run(root, 'missing-runtime-blocked')
            target.write_bytes(original)
            target.write_bytes(old_version_fixture(target))
            run(root, 'old-runtime-blocked')
            target.write_bytes(original)
            corrupted = bytearray(original)
            corrupted[-1] ^= 1  # Preserve PE/version/size so only hash detects it.
            target.write_bytes(corrupted)
            run(root, 'corrupted-runtime-blocked')
            target.write_bytes(b'not a PE; data-only negative fixture')
            run(root, 'invalid-pe-blocked')
            wrong_machine = bytearray(original)
            pe_offset = struct.unpack_from('<I', wrong_machine, 60)[0]
            struct.pack_into('<H', wrong_machine, pe_offset + 4, 0x14c)
            target.write_bytes(wrong_machine)
            run(root, 'wrong-architecture-blocked')
            target.write_bytes(original)
            wrong_mode = runtime.runtime_metadata(root)
            wrong_mode['mode'] = 'Prerequisite'
            metadata.write_text(json.dumps(wrong_mode), encoding='utf-8')
            run(root, 'metadata-mode-blocked')
            metadata.unlink()
            run(root, 'missing-metadata-blocked')
        record['host_runtime_after'] = host_runtime_inventory(system_root)
        if record['host_runtime_before'] != record['host_runtime_after']:
            raise RuntimeError('Shared host runtime changed during read-only preflight fixtures')
        record['passed'] = True
        return record
    except Exception as error:
        record['error'] = str(error)
        try:
            checkpoint()
        except OSError:
            pass
        raise
    finally:
        if 'error' not in record:
            checkpoint()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    args = parser.parse_args()
    probe(args.launcher, args.artifacts, args.package)
