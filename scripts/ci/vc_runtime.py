"""Pinned Microsoft release CRT bytes; data extraction only, never run redist.

Technical identity and distributor permission are separate gates. This module
does not manufacture license entitlement from a successful build or hash check.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[2]
PIN_PATH = ROOT / 'scripts/portable-licenses/vc-runtime-pin.json'
REVIEW_NAME = 'licenses/microsoft/REDISTRIBUTION-REVIEW.json'


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RuntimeError(f'Duplicate Microsoft runtime metadata key: {key}')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique, parse_constant=lambda x: (_ for _ in ()).throw(RuntimeError('Non-finite runtime JSON')))


def exact_json(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin():
    return read_json(PIN_PATH)


def verify_file(path, expected):
    if (not path.is_file() or path.is_symlink() or path.stat().st_size != expected['bytes']
            or digest(path) != expected['sha256']):
        raise RuntimeError(f'Microsoft runtime bytes differ from reviewed pin: {path.name}')


def cabinet(redist, output):
    value = pin()
    verify_file(redist, value['package_metadata']['source'])
    raw = redist.read_bytes()
    item = value['cabinet']
    data = raw[item['offset']:item['offset'] + item['bytes']]
    if (data[:4] != b'MSCF' or len(data) != item['bytes']
            or struct.unpack_from('<I', data, 8)[0] != len(data)
            or hashlib.sha256(data).hexdigest() != item['sha256']):
        raise RuntimeError('Pinned Microsoft CAB slice differs')
    with output.open('xb') as stream:
        stream.write(data)


def verify_inner(path):
    item = pin()['cabinet']
    verify_file(path, {'bytes': item['member_bytes'], 'sha256': item['member_sha256']})


def verify_pe(path, expected):
    import pefile
    pe = pefile.PE(str(path))
    try:
        info = pe.VS_FIXEDFILEINFO[0]
        version = '.'.join(map(str, (info.FileVersionMS >> 16, info.FileVersionMS & 65535,
                                    info.FileVersionLS >> 16, info.FileVersionLS & 65535)))
        if pe.FILE_HEADER.Machine != 0x8664 or version != expected['version']:
            raise RuntimeError(f'Microsoft runtime architecture/version differs: {path.name}')
    finally:
        pe.close()


def stage(extracted, output):
    metadata = pin()['package_metadata']
    output.mkdir(parents=True, exist_ok=False)
    for name, expected in metadata['files'].items():
        source = extracted / (name + '_amd64')
        verify_file(source, expected)
        verify_pe(source, expected)
        (output / name).write_bytes(source.read_bytes())
    (output / 'showpsisi-vc-runtime.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    return metadata


def verify_package(package, build):
    expected = pin()['package_metadata']
    metadata = read_json(package / 'bin/showpsisi-vc-runtime.json')
    if not exact_json(metadata, expected) or not exact_json(build.get('crt_provenance'), metadata):
        raise RuntimeError('App-local runtime provenance differs from reviewed pin/build record')
    if build.get('crt_minimum_version') != expected['minimum_version']:
        raise RuntimeError('App-local runtime minimum differs from reviewed requirement')
    for name, identity in expected['files'].items():
        verify_file(package / 'bin' / name, identity)
    return metadata


def distribution_gate(package):
    review = read_json(package / REVIEW_NAME)
    metadata = pin()['package_metadata']
    if (review.get('review_complete') is not True or not isinstance(review.get('license_basis'), dict)
            or not review['license_basis'].get('applicable_terms_url')
            or not review['license_basis'].get('distribution_basis')
            or review.get('source_sha256') != metadata['source']['sha256']
            or review.get('runtime_version') != metadata['version']
            or not exact_json(review.get('files'), metadata['files'])):
        raise RuntimeError('Microsoft runtime redistribution entitlement review is incomplete')
    return review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('cabinet', 'inner', 'stage'))
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.mode == 'cabinet':
        cabinet(args.input, args.output)
    elif args.mode == 'inner':
        verify_inner(args.input)
    else:
        stage(args.input, args.output)


if __name__ == '__main__':
    main()
