"""Exercise the portable CMD runtime preflight without changing system DLLs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


def command(launcher):
    matches = re.findall(r'^"%SystemRoot%[^\r\n]+ -Command "([^\r\n]+)"$',
                         launcher.read_text(encoding='utf-8'), re.MULTILINE)
    if len(matches) != 1:
        raise RuntimeError('Expected exactly one portable runtime preflight command')
    return matches[0]


def fixture_command(script):
    # Do not replace the process's SystemRoot: Windows PowerShell needs it to
    # initialize the CLR. Bind only this checker's DLL lookup to the fixture.
    if script.count('$env:SystemRoot') != 1:
        raise RuntimeError('Expected one DLL root binding in the production preflight')
    return script.replace('$env:SystemRoot', '$env:SHOWPSISI_PREFLIGHT_FIXTURE_ROOT')


def probe(launcher, artifacts):
    if os.name != 'nt':
        raise RuntimeError('Portable runtime preflight probe requires Windows')
    artifacts.mkdir(parents=True, exist_ok=False)
    script = command(launcher)
    system_root = os.environ['SystemRoot']
    powershell = Path(system_root) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    record = {'passed': False, 'launcher_sha256': hashlib.sha256(launcher.read_bytes()).hexdigest(), 'cases': []}
    def run(root, name, expected_code, expected_error='', fixture=False):
        # The production command is unchanged for the real-host case. Fixtures
        # substitute just its lookup-root expression, never SystemRoot itself.
        selected = fixture_command(script) if fixture else script
        result = subprocess.run([str(powershell), '-NoLogo', '-NoProfile', '-NonInteractive', '-Command', selected],
                                env=dict(os.environ, SHOWPSISI_PREFLIGHT_FIXTURE_ROOT=str(root)),
                                capture_output=True, timeout=30)
        value = {'name': name, 'exit_code': result.returncode,
                 'fixture_root_binding': fixture,
                 'stdout_hex': result.stdout.hex(), 'stderr_hex': result.stderr.hex(),
                 'stdout': result.stdout.decode('utf-8', errors='backslashreplace'),
                 'stderr': result.stderr.decode('utf-8', errors='backslashreplace')}
        record['cases'].append(value)
        if result.returncode != expected_code or expected_error not in value['stderr']:
            raise RuntimeError(f'Portable preflight case failed: {value}')
    try:
        run(system_root, 'host-runtime-ready', 0)
        with tempfile.TemporaryDirectory(prefix='ShowPsiSi prerequisite 测试 ') as directory:
            root = Path(directory)
            (root / 'System32').mkdir()
            run(root, 'missing-runtime-blocked', 1, 'Missing runtime:', fixture=True)
            # Not executable: FileVersionInfo reads version zero from this
            # fixture, exercising the too-old path without changing the host.
            (root / 'System32/vcruntime140.dll').write_bytes(b'no version resource; test fixture')
            run(root, 'old-runtime-blocked', 1, 'Runtime too old:', fixture=True)
        record['passed'] = True
    except Exception as error:
        record['error'] = str(error)
        raise
    finally:
        (artifacts / 'preflight.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher', type=Path, required=True)
    parser.add_argument('--artifacts', type=Path, required=True)
    args = parser.parse_args()
    probe(args.launcher, args.artifacts)
