"""Identify the loaded Inno compiler engine, without producing an installer.

ISCC.exe is a driver and its PE FileVersion can be 0.0.0.0. The official
compiler reports the loaded ISCmplr.dll version when compiling a script.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


PROBE = '''#if Ver < 0x06030000 || Ver >= 0x07000000
  #error Unsupported Inno Setup version; require 6.3+ and below 7.
#endif
[Setup]
AppName=ShowPsiSi compiler probe
AppVersion=0.0.0
DefaultDirName={tmp}\\ShowPsiSi-Compiler-Probe
CreateAppDir=no
Uninstallable=no
Output=no
'''


def parse_version(output):
    versions = re.findall(r'^Compiler engine version: Inno Setup ([0-9]+\.[0-9]+\.[0-9]+)\s*$',
                          output, re.MULTILINE)
    if len(versions) != 1:
        raise RuntimeError('Inno compiler did not report one stable engine version')
    numbers = tuple(map(int, versions[0].split('.')))
    if not (6, 3, 0) <= numbers < (7, 0, 0):
        raise RuntimeError(f'Unverified Inno compiler version: {versions[0]}')
    return versions[0]


def identity(compiler):
    compiler = compiler.resolve()
    # These are the actual driver, compiler and preprocessor used by ISCC.
    files = [compiler, compiler.parent / 'ISCmplr.dll', compiler.parent / 'ISPP.dll']
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    result = subprocess.run([str(compiler), '/O-', '-'], input=PROBE, text=True,
                            encoding='utf-8-sig', stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=60, check=False)
    if result.returncode != 0:
        raise RuntimeError(f'Inno engine probe failed ({result.returncode}):\n{result.stdout}')
    return {'version': parse_version(result.stdout), 'version_source': 'loaded compiler engine probe',
            'files_sha256': hashes, 'probe_output': result.stdout}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(identity(args.compiler)))
