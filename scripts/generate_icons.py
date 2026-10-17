#!/usr/bin/env python3
"""Regenerate original ShowPsiSi assets using Inkscape and Pillow (build-time only).

Run from any directory. Committed outputs mean application builds do not need
these tools. --check regenerates in a temporary directory and compares bytes.
"""
import argparse
from io import BytesIO
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SIZES = (16, 24, 32, 48, 64, 128, 256)


def generate(destination):
    from PIL import Image
    svg = ROOT / 'assets/icons/showpsisi.svg'
    outputs = {}
    for size in SIZES:
        target = destination / f'showpsisi-{size}.png'
        subprocess.run(['inkscape', str(svg), '--export-type=png',
                        f'--export-filename={target}', f'--export-width={size}',
                        f'--export-height={size}'], check=True, capture_output=True)
        # Normalize to RGBA without timestamps, color profiles or editor metadata.
        with Image.open(target) as source:
            normalized = source.convert('RGBA')
            stream = BytesIO()
            normalized.save(stream, format='PNG', optimize=False, compress_level=9)
        outputs[f'assets/icons/showpsisi-{size}.png'] = stream.getvalue()
    # PNG-compressed ICO entries retain every explicitly rendered small-size image.
    data = struct.pack('<HHH', 0, 1, len(SIZES))
    offset = 6 + 16 * len(SIZES)
    payloads = []
    for size in SIZES:
        payload = outputs[f'assets/icons/showpsisi-{size}.png']
        data += struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(payload), offset)
        payloads.append(payload)
        offset += len(payload)
    ico = data + b''.join(payloads)
    outputs['assets/icons/showpsisi.ico'] = ico
    outputs['ui/tauri/src-tauri/icons/icon.ico'] = ico
    outputs['ui/tauri/src-tauri/icons/icon.png'] = outputs['assets/icons/showpsisi-256.png']
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not shutil.which('inkscape'):
        parser.error('Inkscape is required only to regenerate/check icon assets')
    with tempfile.TemporaryDirectory(prefix='showpsisi-icons-') as temporary:
        outputs = generate(Path(temporary))
    for relative, data in outputs.items():
        target = ROOT / relative
        if args.check:
            if not target.is_file() or target.read_bytes() != data:
                raise SystemExit(f'Generated icon differs: {relative}')
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    print(f'{len(outputs)} icon assets {"verified" if args.check else "generated"}')


if __name__ == '__main__':
    main()
