"""Build/verify the same-release Qt corresponding-source asset without executing it.

This is a build/publication gate, never a runtime integrity check. The original
Qt tar.xz bytes (including their build scripts) stay unchanged. All small legal
materials remain in each binary package, and its exact build/download metadata
is copied into the source asset. No network requests, extraction or execution
are performed here. Changing Qt pins requires a fresh dependency/source review.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile
import zipfile

REPOSITORY = 'https://github.com/znbsf/ShowPsiSi'
ZIP_ROOT = 'ShowPsiSi-corresponding-source/'
MANIFEST = 'source-manifest.json'
MAX_JSON = 8 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_FILES = 2000
SHA256 = re.compile(r'[0-9a-f]{64}')
COMMIT = re.compile(r'[0-9a-f]{40}')
VERSION = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)')
POLICY = {'schema_version': 1, 'delivery': 'same-release-asset',
          'filename_pattern': 'ShowPsiSi-{version}-corresponding-source.zip',
          'download_information': 'SOURCE_DOWNLOAD.txt'}
QT_ARCHIVES = (
    {'module': 'qtbase', 'filename': 'qtbase-everywhere-src-6.7.3.tar.xz',
     'bytes': 49426156, 'sha256': '8ccbb9ab055205ac76632c9eeddd1ed6fc66936fc56afc2ed0fd5d9e23da3097'},
    {'module': 'qtdeclarative', 'filename': 'qtdeclarative-everywhere-src-6.7.3.tar.xz',
     'bytes': 35663596, 'sha256': '937b70e441abf5bc4e50d44d26610e2714a28514acf3885cd36116cd610b9875'},
    {'module': 'qtsvg', 'filename': 'qtsvg-everywhere-src-6.7.3.tar.xz',
     'bytes': 1792980, 'sha256': '40142cb71fb1e07ad612bc361b67f5d54cd9367f9979ae6b86124a064deda06b'},
)
RETAINED = frozenset(('LICENSE', 'THIRD_PARTY_NOTICES.txt', 'SOURCE_INFORMATION.txt',
                      'source-index.json', 'build-information.json',
                      'SOURCE_DOWNLOAD.txt', 'redistribution-review.json'))
LICENSE_HASHES = {
    'LGPL-3.0-only.txt': 'da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768',
    'GPL-3.0-only.txt': '8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903',
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def strict_equal(left, right):
    """JSON wire types matter: bool/float must never alias a schema integer."""
    try:
        return json.dumps(left, sort_keys=True, allow_nan=False, separators=(',', ':')) == json.dumps(
            right, sort_keys=True, allow_nan=False, separators=(',', ':'))
    except (TypeError, ValueError):
        return False


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'Duplicate JSON object key')
        value[key] = item
    return value


def decode_json(raw):
    require(len(raw) <= MAX_JSON, 'Source metadata exceeds bounded size')
    try:
        def invalid_constant(value):
            raise ValueError('Non-finite JSON number')
        value = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object,
                           parse_constant=invalid_constant)
        # JSON's finite exponent syntax can still overflow Python's float.
        json.dumps(value, allow_nan=False)
    except (ValueError, UnicodeError) as error:
        raise RuntimeError('Invalid source JSON metadata') from error
    require(isinstance(value, dict), 'Source metadata must be a JSON object')
    return value


def read_json(path):
    require(Path(path).stat().st_size <= MAX_JSON, 'Source metadata exceeds bounded size')
    return decode_json(Path(path).read_bytes())


def safe_name(name):
    require(isinstance(name, str) and bool(name) and '\\' not in name
            and ':' not in name and '\x00' not in name, 'Unsafe source path')
    path = PurePosixPath(name)
    require(not path.is_absolute() and str(path) == name
            and all(part not in ('', '.', '..') and not part.endswith((' ', '.'))
                    and not re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I)
                    and not any(ord(c) < 32 for c in part)
                    for part in path.parts), 'Unsafe source path')
    return name


def inventory(directory, exclude=()):
    directory = Path(directory)
    require(directory.is_dir() and not directory.is_symlink(), 'Invalid source/package directory')
    files, folded = {}, set()
    for path in sorted(directory.rglob('*')):
        require(not path.is_symlink(), 'Symlinks are forbidden in source/package inputs')
        name = safe_name(path.relative_to(directory).as_posix())
        require(name.casefold() not in folded, 'Case-colliding source/package paths')
        folded.add(name.casefold())
        if path.is_dir():
            continue
        require(path.is_file(), 'Nonregular source/package input')
        if name not in exclude:
            files[name] = {'bytes': path.stat().st_size, 'sha256': digest(path)}
    return files


def asset_name(version):
    require(isinstance(version, str) and VERSION.fullmatch(version),
            'Corresponding source requires a canonical application version')
    return POLICY['filename_pattern'].format(version=version)


def delivery_contract(build):
    require(isinstance(build, dict), 'Missing source build identity')
    version, commit = build.get('application_version'), build.get('source_commit')
    name = asset_name(version)
    require(isinstance(commit, str) and COMMIT.fullmatch(commit), 'Invalid corresponding source commit')
    return {'schema_version': 1, 'delivery': 'same-release-asset',
            'filename': name, 'url': f'{REPOSITORY}/releases/download/v{version}/{name}',
            'source_commit': commit, 'application_version': version}


def download_information(build):
    value = delivery_contract(build)
    return (f"SHOWPSISI {value['application_version']} - CORRESPONDING SOURCE\n"
            f"Application source commit: {value['source_commit']}\n"
            f"Application source and packaging/rebuild scripts: {REPOSITORY}/tree/{value['source_commit']}\n\n"
            'Free matching Qt corresponding source, beside this version\'s binary downloads:\n'
            f"Filename: {value['filename']}\n{value['url']}\n\n"
            'Downloading source is optional for running/installing ShowPsiSi.\n'
            'The publisher must retain the matching source while offering these binaries\n'
            'and for as long as required by GPLv3 section 6(d).\n'
            'The source ZIP preserves the three original Qt 6.7.3 source archives,\n'
            'their build scripts, licenses, source-index.json and this exact build information.\n'
            'See SOURCE_INFORMATION.txt for archive hashes, build settings and compatible\n'
            'shared-library replacement instructions. No source archive is needed to run the app.\n')


def validate_archive_records(records):
    require(isinstance(records, list) and len(records) == len(QT_ARCHIVES),
            'Expected exactly the pinned Qt source archives')
    by_module = {}
    for item in records:
        require(isinstance(item, dict), 'Invalid Qt source archive record')
        module = item.get('module')
        require(isinstance(module, str) and module not in by_module, 'Duplicate Qt source archive module')
        by_module[module] = item
    require(set(by_module) == {item['module'] for item in QT_ARCHIVES}, 'Unreviewed Qt source family')
    for pin in QT_ARCHIVES:
        item = by_module[pin['module']]
        require(all(item.get(key) == pin[key] for key in ('module', 'filename', 'sha256'))
                and item.get('url') == 'https://download.qt.io/archive/qt/6.7/6.7.3/submodules/' + pin['filename']
                and item.get('publisher_checksum_verified') is True
                and ('bytes' not in item or type(item['bytes']) is int and item['bytes'] == pin['bytes']),
                'Qt source archive identity differs from reviewed pins')


def validate_build(build):
    value = delivery_contract(build)
    require(strict_equal(build.get('corresponding_source'), value), 'Build corresponding-source declaration mismatch')
    require(build.get('qt_version') == '6.7.3', 'Unreviewed Qt version')
    validate_archive_records(build.get('qt_source_archives'))
    require(build.get('qt_source_patches', []) == [], 'Modified Qt source requires a new source review')
    config = build.get('qt_build_configuration')
    required = ('mkspecs/qconfig.pri', 'mkspecs/qmodule.pri', 'include/QtCore/qconfig.h')
    require(isinstance(config, dict) and set(required).issubset(config), 'Qt build configuration is missing')
    for name, item in config.items():
        safe_name(name)
        require(isinstance(item, dict) and isinstance(item.get('content'), str)
                and item.get('sha256') == hashlib.sha256(item['content'].encode('utf-8')).hexdigest(),
                'Qt build configuration content/hash mismatch')
    require(re.search(r'^#define QT_FEATURE_shared 1\s*$', config[required[2]]['content'], re.M)
            and re.search(r'^#define QT_FEATURE_static -1\s*$', config[required[2]]['content'], re.M)
            and re.search(r'^#define QT_VERSION_STR "6\.7\.3"\s*$', config[required[2]]['content'], re.M)
            and re.search(r'^QT\.global_private\.enabled_features\s*=.*\brelocatable\b', config[required[1]]['content'], re.M),
            'Qt must retain the reviewed shared/relocatable build configuration')
    relocation = build.get('qt_core_relocation')
    require(isinstance(relocation, dict)
            and isinstance(relocation.get('deployed_sha256'), str)
            and SHA256.fullmatch(relocation['deployed_sha256'])
            and relocation.get('installed_kit_sha256') == relocation['deployed_sha256'],
            'QtCore was modified or its unmodified deployment evidence is missing')
    return value


def _validate_metadata(build, index, info, download):
    value = validate_build(build)
    require(strict_equal(index.get('corresponding_source'), POLICY), 'Static corresponding-source policy mismatch')
    validate_archive_records(index.get('qt_source_archives'))
    require('SOURCE_DOWNLOAD.txt' in info.decode('utf-8-sig'), 'Source information lacks same-release download directions')
    require(download == download_information(build).encode('utf-8'), 'Exact source download information mismatch')
    return value


def validate_metadata(package):
    package = Path(package)
    return _validate_metadata(read_json(package / 'build-information.json'),
                              read_json(package / 'source-index.json'),
                              (package / 'SOURCE_INFORMATION.txt').read_bytes(),
                              (package / 'SOURCE_DOWNLOAD.txt').read_bytes())


def stamp(package):
    """Generate only own build/download metadata, never rewrite reviewed notices."""
    package = Path(package)
    build = read_json(package / 'build-information.json')
    build['corresponding_source'] = delivery_contract(build)
    _validate_metadata(build, read_json(package / 'source-index.json'),
                       (package / 'SOURCE_INFORMATION.txt').read_bytes(),
                       download_information(build).encode('utf-8'))
    for name, data in (('build-information.json', json.dumps(build, indent=2).encode('utf-8')),
                       ('SOURCE_DOWNLOAD.txt', download_information(build).encode('utf-8'))):
        require(not (package / name).is_symlink(), 'Refusing symlink metadata target')
        with tempfile.NamedTemporaryFile(dir=package, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        try:
            os.replace(temporary, package / name)
        finally:
            temporary.unlink(missing_ok=True)
    return build['corresponding_source']


def review_inventory(value):
    """Preserve the entire review, including source files moved to the sidecar."""
    own = {'bin/showpsisi-core.exe', 'bin/showpsisi-qt.exe', 'bin/qt.conf', 'bin/showpsisi-portable.json'}
    result = {name: item['sha256'] for name, item in value['files'].items()
              if (name.startswith('bin/') and name not in own)
              or name.startswith(('licenses/', 'sources/'))
              or name in ('THIRD_PARTY_NOTICES.txt', 'SOURCE_INFORMATION.txt', 'source-index.json')}
    build = value.get('build', {})
    if 'corresponding_source' in build:
        validate_build(build)
        require(not any(name.startswith('sources/') for name in value['files']),
                'Sidecar binary package must not embed source archives')
        result.update({'sources/' + pin['filename']: pin['sha256'] for pin in QT_ARCHIVES})
    return result


def _validate_materials(files, build, index, review, read):
    require(RETAINED.issubset(files), 'Required source/license/build material missing')
    reviewed = review.get('reviewed_files')
    require(type(review.get('schema_version')) is int and review['schema_version'] == 1
            and isinstance(reviewed, dict), 'Missing or invalid full reviewed inventory')
    for name, expected in reviewed.items():
        safe_name(name)
        require(isinstance(expected, str) and SHA256.fullmatch(expected), 'Malformed reviewed file hash')
        if name.startswith(('licenses/', 'sources/')) or name in ('THIRD_PARTY_NOTICES.txt', 'SOURCE_INFORMATION.txt', 'source-index.json'):
            require(name in files and files[name]['sha256'] == expected, 'Reviewed source/notice material differs: ' + name)
    require(reviewed.get('bin/Qt6Core.dll') == build['qt_core_relocation']['deployed_sha256'],
            'QtCore build/source identity differs from reviewed runtime')
    for pin in QT_ARCHIVES:
        name = 'sources/' + pin['filename']
        require(strict_equal(files.get(name), {'bytes': pin['bytes'], 'sha256': pin['sha256']})
                and reviewed.get(name) == pin['sha256'], 'Pinned Qt source archive bytes/hash mismatch: ' + name)
        for filename, expected in LICENSE_HASHES.items():
            name = f"licenses/qt/{pin['module']}/LICENSES/{filename}"
            require(files.get(name, {}).get('sha256') == expected, 'Required full Qt license text missing or changed')
    attributions = decode_json(read('licenses/qt/source-attributions.json'))
    validate_archive_records(attributions.get('archives'))
    require(attributions.get('version') == '6.7.3' and isinstance(attributions.get('file_sha256'), dict)
            and attributions['file_sha256'], 'Qt source-family notice inventory missing')
    for name, expected in attributions['file_sha256'].items():
        name = 'licenses/qt/' + safe_name(name)
        require(isinstance(expected, str) and SHA256.fullmatch(expected)
                and files.get(name, {}).get('sha256') == expected, 'Qt source-family notice missing or changed')
    require(isinstance(index.get('materials'), dict) and index['materials'], 'Dependency notice inventory missing')
    for name, item in index['materials'].items():
        safe_name(name)
        require(name.startswith('licenses/') and isinstance(item, dict)
                and isinstance(item.get('sha256'), str) and SHA256.fullmatch(item['sha256'])
                and files.get(name, {}).get('sha256') == item.get('sha256'), 'Indexed dependency notice missing or changed')


def validate_package(package, require_review=True):
    package = Path(package)
    files = inventory(package, exclude=('manifest.json',))
    value = read_json(package / 'manifest.json')
    build, index = read_json(package / 'build-information.json'), read_json(package / 'source-index.json')
    require(type(value.get('schema_version')) is int and value['schema_version'] == 1
            and strict_equal(value.get('files'), files) and strict_equal(value.get('build'), build),
            'Binary package manifest/build mismatch')
    validate_metadata(package)
    review = read_json(package / 'redistribution-review.json')
    combined = dict(files)
    combined.update({'sources/' + pin['filename']: {'bytes': pin['bytes'], 'sha256': pin['sha256']} for pin in QT_ARCHIVES})
    _validate_materials(combined, build, index, review, lambda name: (package / name).read_bytes())
    require(review.get('reviewed_files') == review_inventory(value), 'Full binary/source redistribution inventory mismatch')
    if require_review:
        require(review.get('review_complete') is True, 'Exact binary/source redistribution review is incomplete')
    return value


def verify_bundled_sources(package):
    """Legacy binary-only releases must still contain every pinned source byte.

    The caller must separately verify its normal binary manifest/runtime gates.
    This narrowly prevents declaring a stripped sidecar build to be legacy.
    """
    package = Path(package)
    build = read_json(package / 'build-information.json')
    index = read_json(package / 'source-index.json')
    require('corresponding_source' not in build and 'corresponding_source' not in index,
            'A declared sidecar cannot fall back to bundled-source validation')
    require(build.get('qt_version') == '6.7.3', 'Unreviewed Qt version')
    validate_archive_records(build.get('qt_source_archives'))
    validate_archive_records(index.get('qt_source_archives'))
    expected = {pin['filename']: {'bytes': pin['bytes'], 'sha256': pin['sha256']} for pin in QT_ARCHIVES}
    require(strict_equal(inventory(package / 'sources'), expected),
            'Bundled source archive set/bytes/hash differs from pinned originals')
    review = read_json(package / 'redistribution-review.json')
    require(review.get('review_complete') is True, 'Bundled source review is incomplete')
    for pin in QT_ARCHIVES:
        require(review.get('reviewed_files', {}).get('sources/' + pin['filename']) == pin['sha256'],
                'Bundled source differs from reviewed inventory')
    return expected


def _source_manifest(build, files):
    return {'schema_version': 1, 'scope': 'windows-x64-corresponding-source',
            'source_commit': build['source_commit'], 'application_version': build['application_version'],
            'corresponding_source': delivery_contract(build),
            'application_source_url': f"{REPOSITORY}/tree/{build['source_commit']}",
            'build_information_sha256': files['build-information.json']['sha256'],
            'source_index_sha256': files['source-index.json']['sha256'],
            'redistribution_review_sha256': files['redistribution-review.json']['sha256'],
            'qt_source_archives': list(QT_ARCHIVES), 'files': files}


def build_archive(package, sources_directory, output):
    package, sources_directory, output = Path(package), Path(sources_directory), Path(output)
    checksum = output.with_suffix(output.suffix + '.sha256')
    require(not output.exists() and not checksum.exists(), 'Refusing existing/stale corresponding-source output')
    require(not output.resolve().is_relative_to(package.resolve())
            and not output.resolve().is_relative_to(sources_directory.resolve()), 'Source output must be outside input trees')
    value = validate_package(package)
    require(output.name == asset_name(value['build']['application_version']), 'Source asset filename/version mismatch')
    expected = {pin['filename']: {'bytes': pin['bytes'], 'sha256': pin['sha256']} for pin in QT_ARCHIVES}
    require(strict_equal(inventory(sources_directory), expected), 'Source archive input set/bytes/hash differs from pinned originals')
    selected = {name: item for name, item in value['files'].items() if name in RETAINED or name.startswith('licenses/')}
    selected.update({'sources/' + name: item for name, item in expected.items()})
    source_manifest = _source_manifest(value['build'], selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=output.name + '.', suffix='.part', dir=output.parent, delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_STORED) as archive:
            for name in sorted(selected):
                path = sources_directory / name.removeprefix('sources/') if name.startswith('sources/') else package / name
                archive.write(path, ZIP_ROOT + name)
            archive.writestr(ZIP_ROOT + MANIFEST, json.dumps(source_manifest, indent=2).encode('utf-8'))
        # Rehash archived bytes and recheck the binary snapshot before committing.
        verify_archive(temporary, package, expected_source=value['build']['source_commit'],
                       expected_version=value['build']['application_version'], check_filename=False)
        # Exclusive destination creation preserves a concurrent writer's result.
        with temporary.open('rb') as source, output.open('xb') as target:
            import shutil
            shutil.copyfileobj(source, target)
        with checksum.open('x', encoding='ascii') as stream:
            stream.write(f'{digest(output)}  {output.name}\n')
    finally:
        temporary.unlink(missing_ok=True)
    return source_manifest


def verify_archive(archive, package=None, expected_source=None, expected_version=None, *, check_filename=True):
    """Rehash every inner file; never trust regenerated outer hashes or manifests.

    A paired binary directory adds byte-for-byte metadata/license and full runtime
    review binding. Publisher should pass its separately verified binary package.
    """
    archive = Path(archive)
    require(archive.is_file() and not archive.is_symlink() and archive.stat().st_size <= MAX_TOTAL,
            'Invalid or oversized corresponding-source ZIP')
    try:
        with zipfile.ZipFile(archive) as zipped:
            entries = zipped.infolist()
            require(0 < len(entries) <= MAX_FILES, 'Invalid corresponding-source member count')
            files, infos, folded, total = {}, {}, set(), 0
            for info in entries:
                require(info.orig_filename == info.filename and info.filename.startswith(ZIP_ROOT), 'Invalid source ZIP root/name')
                name = safe_name(info.filename[len(ZIP_ROOT):])
                require(not info.is_dir() and name.casefold() not in folded, 'Duplicate/aliased source ZIP member')
                folded.add(name.casefold())
                require(info.compress_type == zipfile.ZIP_STORED and not info.flag_bits & 1,
                        'Source ZIP must store unencrypted original bytes')
                kind = stat.S_IFMT(info.external_attr >> 16)
                require(kind in (0, stat.S_IFREG), 'Nonregular source ZIP member')
                total += info.file_size
                require(info.file_size >= 0 and total <= MAX_TOTAL, 'Expanded source ZIP exceeds bounded size')
                hasher, count = hashlib.sha256(), 0
                with zipped.open(info) as stream:
                    while chunk := stream.read(1024 * 1024):
                        count += len(chunk)
                        require(count <= info.file_size, 'Source ZIP member size mismatch')
                        hasher.update(chunk)
                require(count == info.file_size, 'Source ZIP member size mismatch')
                files[name] = {'bytes': count, 'sha256': hasher.hexdigest()}
                infos[name] = info
            def read(name):
                require(name in infos and infos[name].file_size <= MAX_JSON, 'Missing or oversized source metadata: ' + name)
                return zipped.read(infos[name])
            manifest = decode_json(read(MANIFEST))
            del files[MANIFEST]
            build, index, review = (decode_json(read(name)) for name in
                                   ('build-information.json', 'source-index.json', 'redistribution-review.json'))
            _validate_metadata(build, index, read('SOURCE_INFORMATION.txt'), read('SOURCE_DOWNLOAD.txt'))
            require(strict_equal(manifest, _source_manifest(build, files)), 'Corresponding-source manifest identity/files mismatch')
            require(expected_source is None or build['source_commit'] == expected_source, 'Source commit differs from binary/request')
            require(expected_version is None or build['application_version'] == expected_version, 'Source version differs from binary/request')
            if check_filename:
                require(archive.name == asset_name(build['application_version']), 'Source asset filename/version mismatch')
            require(review.get('review_complete') is True, 'Exact binary/source redistribution review is incomplete')
            _validate_materials(files, build, index, review, read)
            expected_files = RETAINED | {name for name in review['reviewed_files'] if name.startswith('licenses/')} | {
                'sources/' + pin['filename'] for pin in QT_ARCHIVES}
            require(set(files) == expected_files, 'Unexpected or missing source asset materials')
            if package is not None:
                package = Path(package)
                binary = validate_package(package)
                require(strict_equal(binary['build'], build), 'Paired source/binary build identity differs')
                for name, item in files.items():
                    if not name.startswith('sources/'):
                        require(strict_equal(binary['files'].get(name), item), 'Paired source/binary material differs: ' + name)
            return manifest
    except (zipfile.BadZipFile, KeyError, OSError) as error:
        raise RuntimeError('Invalid or incomplete corresponding-source ZIP') from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('stamp', 'validate', 'archive', 'verify'))
    parser.add_argument('--package', type=Path)
    parser.add_argument('--sources', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--source-commit')
    parser.add_argument('--version')
    args = parser.parse_args()
    if args.mode == 'stamp':
        require(args.package is not None, '--package is required')
        result = stamp(args.package)
    elif args.mode == 'validate':
        require(args.package is not None, '--package is required')
        result = validate_package(args.package)['build']['corresponding_source']
    elif args.mode == 'archive':
        require(all(value is not None for value in (args.package, args.sources, args.output)), '--package, --sources and --output are required')
        result = build_archive(args.package, args.sources, args.output)
    else:
        require(args.output is not None, '--output is required')
        result = verify_archive(args.output, args.package, args.source_commit, args.version)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
