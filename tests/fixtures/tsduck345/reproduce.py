"""Recompile the checked-in XML with official TSDuck 3.45-4798; compare bytes.

No generated binary is written into the checkout and no manifest is modified.
Usage: python tests/fixtures/tsduck345/reproduce.py --compiler /path/to/tstabcomp
Configure the SDK's normal runtime library path before invoking this script.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='tstabcomp')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    version = subprocess.check_output([args.compiler, '--version'], text=True, stderr=subprocess.STDOUT).strip()
    if version != manifest['generator']:
        raise SystemExit(f'Wrong compiler: {version!r}; expected {manifest["generator"]!r}')
    with tempfile.TemporaryDirectory(prefix='showpsisi-protocol-compile-') as temp:
        for name, entry in manifest['fixtures'].items():
            source = root / entry['xml']
            if hashlib.sha256(source.read_text(encoding='utf-8').encode('utf-8')).hexdigest() != entry['xml_sha256']:
                raise SystemExit(f'{name}: XML source hash differs from manifest')
            binary = Path(temp) / (name + '.bin')
            subprocess.run([args.compiler, *entry['compiler_args'], str(source), '-o', str(binary)], check=True)
            raw = binary.read_bytes()
            if raw.hex() != entry['hex'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise SystemExit(f'{name}: generated section differs from checked-in bytes')
            print(f'{name}: {len(raw)} bytes match')
    print(f'{len(manifest["fixtures"])} fixtures reproduced exactly with {version}')


if __name__ == '__main__':
    main()
