"""Pinned static-library provenance and distribution obligations (build time only).

PE imports cannot identify code linked into our own executable. Keep this check
independent of the mutable package manifest/review so deleting an obligation and
regenerating their hashes cannot silently remove the static dependency.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPAT = {
    'name': 'Expat', 'version': '2.9.0', 'linkage': 'static',
    'license': 'MIT; embedded SipHash CC0-1.0',
    'source': 'https://github.com/libexpat/libexpat/releases/download/R_2_9_0/expat-2.9.0.tar.xz',
    'source_sha256': '1e6371862cc31999b368c3b89b49994f0677e1bab5f1b2b85ae3741f5d803051',
    'source_bytes': 534052,
    'vendored_manifest_sha256': '4b0f73db285c97bcfd0d6c4dab25c76ca465fa27da5d8c88ec8d2d4637275cf0',
    'notice_files': {
        'licenses/expat/COPYING.txt': '31b15de82aa19a845156169a17a5488bf597e561b2c318d159ed583139b25e87',
        'licenses/expat/UPSTREAM-NOTICES.txt': '0b2f34e75e15cd5a22f3973c27585e30dd8ee8cdb7a867bcdfbd1f2bf3368b81',
        'licenses/expat/SOURCE-PROVENANCE.json': '4b0f73db285c97bcfd0d6c4dab25c76ca465fa27da5d8c88ec8d2d4637275cf0',
    },
}
DEPENDENCIES = [EXPAT]
NOTICE = ('Expat 2.9.0 is statically linked into showpsisi-core. MIT license and\n'
          'copyright notices: licenses/expat/COPYING.txt and UPSTREAM-NOTICES.txt.\n'
          'The embedded SipHash implementation uses the CC0-1.0 dedication.')
SOURCE_NOTICE = ('Expat 2.9.0: unmodified official library sources, statically linked.\n'
                 'Exact archive URL, SHA-256 and vendored file inventory are in\n'
                 'licenses/expat/SOURCE-PROVENANCE.json and source-index.json.\n'
                 'MIT/CC0 do not require an accompanying source archive; the pinned\n'
                 'source reference is provenance, not an unfulfilled source offer.')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RuntimeError(f'Duplicate static-dependency control key: {key}')
            result[key] = value
        return result
    return json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def require_record(value, where):
    if value.get('static_dependencies') != DEPENDENCIES:
        raise RuntimeError(f'Static dependency identity missing or changed: {where}')


def verify_source(root=ROOT):
    directory = root / 'third_party/expat'
    provenance = directory / 'SHOWPSISI_SOURCE.json'
    if not provenance.is_file() or digest(provenance) != EXPAT['vendored_manifest_sha256']:
        raise RuntimeError('Static Expat source provenance differs from reviewed pin')
    metadata = read_json(provenance)
    for key in ('version', 'source', 'source_sha256', 'source_bytes'):
        if metadata.get(key) != EXPAT[key]:
            raise RuntimeError(f'Static Expat source identity differs: {key}')
    expected = metadata['files_sha256']
    files = list(directory.rglob('*'))
    if any(path.is_symlink() for path in files):
        raise RuntimeError('Static Expat source must not contain symlinks')
    actual = {path.relative_to(directory).as_posix(): digest(path)
              for path in files if path.is_file() and path != provenance}
    if actual != expected:
        raise RuntimeError('Static Expat vendored source inventory differs from reviewed archive')
    return DEPENDENCIES


def verify_package(package, build):
    require_record(build, 'build-information.json')
    index_path = package / 'source-index.json'
    if not index_path.is_file():
        raise RuntimeError('Static dependency source-index.json is missing')
    require_record(read_json(index_path), 'source-index.json')
    for name, expected in EXPAT['notice_files'].items():
        path = package / name
        if not path.is_file() or path.is_symlink() or digest(path) != expected:
            raise RuntimeError(f'Static dependency notice missing or changed: {name}')
    for name, required in (('THIRD_PARTY_NOTICES.txt', NOTICE),
                           ('SOURCE_INFORMATION.txt', SOURCE_NOTICE)):
        path = package / name
        if not path.is_file() or required not in path.read_text(encoding='utf-8-sig'):
            raise RuntimeError(f'Static dependency notice missing or changed: {name}')
    return DEPENDENCIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--record', type=Path)
    args = parser.parse_args()
    result = verify_source(args.root)
    if args.record:
        require_record(read_json(args.record), str(args.record))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
