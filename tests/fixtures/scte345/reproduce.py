"""Reproduce the pinned SCTE vectors without modifying checked-in files."""
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
    version = subprocess.check_output([args.compiler, '--version'], text=True,
                                      stderr=subprocess.STDOUT).strip()
    if version != manifest['generator']:
        raise SystemExit(f'Compiler mismatch: {version!r}')
    with tempfile.TemporaryDirectory(prefix='showpsisi-scte-reproduce-') as temp:
        for name, entry in manifest['fixtures'].items():
            source = root / entry['xml']
            normalized = source.read_text(encoding='utf-8').encode('utf-8')
            if hashlib.sha256(normalized).hexdigest() != entry['xml_sha256']:
                raise SystemExit(f'{name}: XML input hash mismatch')
            target = Path(temp) / (name + '.bin')
            subprocess.run([args.compiler, *entry['compiler_args'], str(source), '-o', str(target)], check=True)
            raw = target.read_bytes()
            if raw.hex() != entry['hex'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise SystemExit(f'{name}: compiled section differs from manifest')
            print(f'{name}: {len(raw)} exact bytes verified')
    print(f'{len(manifest["fixtures"])} SCTE vectors reproduced with {version}')


if __name__ == '__main__':
    main()
