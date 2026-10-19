"""Fail-closed app-local VC runtime identity and Windows loaded-module evidence.

This is CI tooling, not a shipped dependency. Pure validation functions can be
tested on Linux; only capture_loaded_modules() observes a live Windows process.
Nothing installs, executes, modifies, or removes a host runtime.
"""
import hashlib
import json
import ntpath
import os
from pathlib import Path, PureWindowsPath
import re
from datetime import datetime, timezone


RUNTIME_NAMES = ('msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll',
                 'vcruntime140.dll', 'vcruntime140_1.dll')
MINIMUM_VERSION = '14.51.36231.0'
PINNED_VERSION = '14.51.36247.0'
METADATA_NAME = 'showpsisi-vc-runtime.json'
CRT_NAME = re.compile(r'^(?:msvcp|vcruntime|concrt|vcomp|vcamp|vccorlib|msvcr)\d[^/\\]*\.dll$', re.I)


def _windows_host():
    return os.name == 'nt'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value):
        raise RuntimeError(f'Invalid VC runtime version: {value!r}')
    return tuple(map(int, value.split('.')))


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate runtime metadata key: {key}')
        result[key] = value
    return result


def runtime_metadata(package):
    path = Path(package) / 'bin' / METADATA_NAME
    try:
        record = json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=_unique_object)
    except (OSError, ValueError) as error:
        raise RuntimeError(f'Missing or invalid bundled VC runtime metadata: {path}') from error
    if (not isinstance(record, dict) or type(record.get('schema_version')) is not int or record['schema_version'] != 1
            or record.get('mode') != 'AppLocal' or record.get('version') != PINNED_VERSION
            or record.get('minimum_version') != MINIMUM_VERSION):
        raise RuntimeError('Unsupported bundled VC runtime identity/mode')
    files = record.get('files')
    if not isinstance(files, dict) or set(files) != set(RUNTIME_NAMES):
        raise RuntimeError('Bundled VC runtime metadata must identify exactly the five reviewed DLLs')
    for name, entry in files.items():
        if (not isinstance(entry, dict) or entry.get('machine') != 'AMD64'
                or entry.get('version') != PINNED_VERSION
                or type(entry.get('bytes')) is not int or entry['bytes'] <= 0
                or not isinstance(entry.get('sha256'), str)
                or not re.fullmatch(r'[0-9a-f]{64}', entry['sha256'])):
            raise RuntimeError(f'Invalid bundled VC runtime metadata entry: {name}')
    return record


def pe_identity(path):
    import pefile  # Pinned CI dependency, never required by the application.
    try:
        pe = pefile.PE(str(path))
        try:
            if (pe.FILE_HEADER.Machine != 0x8664 or pe.OPTIONAL_HEADER.Magic != 0x20b
                    or not pe.FILE_HEADER.Characteristics & 0x2000):
                raise RuntimeError(f'Bundled VC runtime is not an x64 DLL: {path}')
            fixed = pe.VS_FIXEDFILEINFO[0]
            return {'machine': 'AMD64', 'version': '.'.join(map(str, (
                fixed.FileVersionMS >> 16, fixed.FileVersionMS & 65535,
                fixed.FileVersionLS >> 16, fixed.FileVersionLS & 65535)))}
        finally:
            pe.close()
    except (OSError, AttributeError, IndexError, pefile.PEFormatError) as error:
        raise RuntimeError(f'Corrupt bundled VC runtime PE/version resource: {path}') from error


def inspect_runtime(package):
    """Verify all staged DLLs without consulting any Windows/system directory."""
    package = Path(package)
    record = runtime_metadata(package)
    verified = {}
    for name in RUNTIME_NAMES:
        path = package / 'bin' / name
        if not path.is_file():
            raise RuntimeError(f'Missing bundled VC runtime: {path}')
        if path.resolve().parent != (package / 'bin').resolve():
            raise RuntimeError(f'Bundled VC runtime resolves outside package bin: {path}')
        identity = pe_identity(path)
        if version_tuple(identity['version']) < version_tuple(MINIMUM_VERSION):
            raise RuntimeError(f'Bundled VC runtime too old: {name} {identity["version"]}')
        identity.update(bytes=path.stat().st_size, sha256=sha256(path))
        if any(identity[key] != record['files'][name][key]
               for key in ('machine', 'version', 'bytes', 'sha256')):
            raise RuntimeError(f'Bundled VC runtime identity mismatch: {name}')
        verified[name] = dict(identity, path=str(path.resolve()))
    return {'mode': 'AppLocal', 'required_minimum': MINIMUM_VERSION,
            'version': PINNED_VERSION, 'files': verified, 'satisfied': True}


def required_crt_modules(package, executable):
    """Normal transitive PE imports required at load time, excluding delay imports.

    A core need not load Qt-only msvcp140_2.dll. Runtime DLLs themselves are
    traversed as well. Unknown VC families never fall back to the host.
    """
    import pefile
    package = Path(package).resolve()
    bindir = package / 'bin'
    pending, seen, required = [Path(executable).resolve()], set(), set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        if not path.is_relative_to(bindir):
            raise RuntimeError(f'Import closure root is outside packaged bin: {path}')
        pe = pefile.PE(str(path), fast_load=True)
        try:
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
            imports = [entry.dll.decode('ascii').lower()
                       for entry in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', ())]
        finally:
            pe.close()
        for name in imports:
            if not name or ntpath.basename(name) != name or '/' in name:
                raise RuntimeError(f'Invalid PE import basename: {path.name} -> {name}')
            if CRT_NAME.fullmatch(name):
                if name not in RUNTIME_NAMES:
                    raise RuntimeError(f'Unreviewed VC runtime import: {path.name} -> {name}')
                required.add(name)
            # Explicit case folding also works for Linux fixture validation of
            # a Windows deployment; the local basename must remain unique.
            candidates = []
            for root in dict.fromkeys((path.parent, bindir)):
                candidates.extend(p for p in root.iterdir() if p.is_file() and p.name.lower() == name)
                if candidates:
                    break
            if len(candidates) > 1:
                raise RuntimeError(f'Ambiguous package dependency: {name}')
            if candidates:
                pending.append(candidates[0].resolve())
            elif name in RUNTIME_NAMES:
                raise RuntimeError(f'Missing bundled VC runtime import: {path.name} -> {name}')
    return sorted(required)


def verify_loaded_modules(paths, package, executable=None, required_names=None):
    """Validate an already retained snapshot; this function alone is no live proof."""
    package = Path(package).resolve()
    runtime = inspect_runtime(package)
    names = set(required_names if required_names is not None else
                required_crt_modules(package, executable) if executable is not None else ())
    if not names.issubset(RUNTIME_NAMES):
        raise RuntimeError(f'Unreviewed required VC runtime modules: {sorted(names)}')
    observed = {}
    for raw_path in paths:
        path = Path(raw_path)
        name = path.name.lower()
        if not CRT_NAME.fullmatch(name):
            continue
        if name not in RUNTIME_NAMES:
            raise RuntimeError(f'Loaded unreviewed VC runtime module: {raw_path}')
        expected = package / 'bin' / name
        # Both normalized location and file identity are required. A copied or
        # hard-linked System32 CRT is still outside the package contract.
        if path.resolve().parent != (package / 'bin').resolve() or path.resolve() != expected.resolve() or not path.samefile(expected):
            raise RuntimeError(f'VC runtime loaded outside package bin: {raw_path}; expected {expected}')
        if name in observed:
            raise RuntimeError(f'Duplicate VC runtime module in snapshot: {name}')
        if sha256(path) != runtime['files'][name]['sha256']:
            raise RuntimeError(f'Loaded VC runtime bytes differ from package metadata: {raw_path}')
        observed[name] = runtime['files'][name]
    missing = names - set(observed)
    if missing:
        raise RuntimeError(f'Required app-local VC runtime modules were not observed: {sorted(missing)}')
    if not observed:
        raise RuntimeError('No app-local VC runtime modules were observed')
    return {'passed': True, 'mode': 'AppLocal', 'required_modules': sorted(names),
            'modules': observed, 'scope': 'observed process module paths and package file identities'}


def _capture_path_identity(raw_path, expected):
    """Resolve an observed path on the capture host, never by alias spelling.

    File identity alone is insufficient: an outside-bin hard link is the same
    file but violates the deployment contract. Both checks precede hashing.
    """
    path, expected = Path(raw_path), Path(expected)
    resolved = path.resolve(strict=True)
    if (not path.is_absolute() or expected.resolve(strict=True) != expected
            or resolved != expected or not path.samefile(expected)):
        raise RuntimeError(f'Captured file resolves outside package bin: {raw_path}; expected {expected}')
    info = path.stat()
    if not path.is_file() or info.st_size <= 0 or info.st_ino <= 0:
        raise RuntimeError(f'Captured file has no usable filesystem identity: {raw_path}')
    return {'raw_path': raw_path, 'resolved_path': str(resolved),
            'file_id': {'device': info.st_dev, 'inode': info.st_ino},
            'bytes': info.st_size, 'sha256': sha256(path)}


def capture_loaded_modules(process, package, evidence_path):
    """Write raw Windows memory-map evidence before applying any acceptance gate."""
    if not _windows_host():
        raise RuntimeError('Live runtime module capture requires Windows')
    evidence_path = Path(evidence_path)
    if evidence_path.exists():
        raise RuntimeError(f'Refusing stale Windows module evidence: {evidence_path}')
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    record = {'schema_version': 2, 'passed': False, 'pid': process.pid,
              'platform': 'Windows', 'package_root': str(Path(package).resolve()), 'raw_modules': []}
    def checkpoint():
        temporary = evidence_path.with_name(evidence_path.name + '.tmp')
        temporary.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
        temporary.replace(evidence_path)
    checkpoint()
    try:
        import psutil
        target = psutil.Process(process.pid)
        record['executable'] = target.exe()
        record['executable_name'] = Path(record['executable']).name.lower()
        record['process_created_unix'] = target.create_time()
        record['command_line'] = target.cmdline()
        record['sampled_at_utc'] = datetime.now(timezone.utc).isoformat()
        maps = target.memory_maps(grouped=False)
        record['raw_modules'] = [item._asdict() for item in maps]
        paths = sorted({item.path for item in maps if item.path.lower().endswith(('.dll', '.exe'))})
        record['module_paths'] = paths
        checkpoint()
        # Preserve every raw string above. Windows can report a short directory
        # alias in exe(), argv[0], and memory maps while package_root is long.
        # Retain the OS's resolution and file identity only for the application
        # executable and reviewed CRT paths; never rewrite raw memory maps.
        name = record['executable_name']
        if name not in ('showpsisi-core.exe', 'showpsisi-qt.exe'):
            raise RuntimeError('Windows runtime module capture executable mismatch')
        command = record['command_line']
        if not isinstance(command, list) or not command or any(not isinstance(arg, str) for arg in command):
            raise RuntimeError('Windows capture is missing valid process/time identity')
        bindir = Path(package).resolve(strict=True) / 'bin'
        expected_exe = bindir / name
        expected_paths = {record['executable']: expected_exe, command[0]: expected_exe}
        for path in paths:
            basename = Path(path).name.lower()
            if basename == name or CRT_NAME.fullmatch(basename):
                if basename != name and basename not in RUNTIME_NAMES:
                    raise RuntimeError(f'Loaded unreviewed VC runtime module: {path}')
                # argv[0] must retain its executable expectation even when a
                # malformed command line names another observed module.
                expected_paths.setdefault(path, bindir / basename)
        record['path_identities'] = {}
        for raw_path, expected in expected_paths.items():
            record['path_identities'][raw_path] = _capture_path_identity(raw_path, expected)
        record['executable_sha256'] = record['path_identities'][record['executable']]['sha256']
        record['runtime'] = verify_loaded_modules(paths, package, record['executable'])
        record['passed'] = True
        checkpoint()
        return record
    except Exception as error:
        record['error'] = str(error)
        try:
            checkpoint()
        except OSError:
            pass  # Preserve the original assertion/capture failure.
        raise


def _windows_path(value):
    if (not isinstance(value, str) or not value or '\x00' in value
            or not PureWindowsPath(value).is_absolute()):
        raise RuntimeError(f'Module capture has a non-absolute Windows path: {value!r}')
    return ntpath.normcase(ntpath.normpath(value))


def _verify_path_identity(identity, raw_path, expected_path, package_file):
    """Check capture-host identity bindings without re-resolving remote paths.

    These records are evidence from the trusted live capture, not signatures.
    An unsigned report cannot authenticate a wholly fabricated capture. Offline
    checks reject missing/inconsistent bindings and bind bytes to this package;
    they never infer that an arbitrary ~1 spelling is an alias of another path.
    """
    _windows_path(raw_path)
    if not isinstance(identity, dict) or identity.get('raw_path') != raw_path:
        raise RuntimeError('Windows capture raw-path identity binding mismatch')
    if _windows_path(identity.get('resolved_path')) != expected_path:
        raise RuntimeError(f'Captured file resolves outside package bin: {raw_path}')
    file_id = identity.get('file_id')
    if (not isinstance(file_id, dict) or set(file_id) != {'device', 'inode'}
            or type(file_id['device']) is not int or file_id['device'] < 0
            or type(file_id['inode']) is not int or file_id['inode'] <= 0):
        raise RuntimeError('Windows capture is missing valid filesystem identity')
    if (type(identity.get('bytes')) is not int or identity['bytes'] <= 0
            or identity['bytes'] != package_file.stat().st_size
            or identity.get('sha256') != sha256(package_file)):
        raise RuntimeError('Windows captured file identity differs from the hash-bound package')
    return identity


def verify_capture(report, package, executable):
    """Recheck retained Windows evidence offline, without opening recorded paths.

    The local package's hashes/import closure are authoritative. A report from
    a relocated Windows directory is interpreted with Windows path semantics
    even when publication/archive verification runs on Linux.
    """
    if (not isinstance(report, dict) or type(report.get('schema_version')) is not int or report['schema_version'] != 2
            or report.get('passed') is not True or report.get('platform') != 'Windows'
            or type(report.get('pid')) is not int or report['pid'] <= 0):
        raise RuntimeError('Missing or unsuccessful Windows runtime module capture')
    package = Path(package)
    name = Path(executable).name.lower()
    if name not in ('showpsisi-core.exe', 'showpsisi-qt.exe') or report.get('executable_name') != name:
        raise RuntimeError('Windows runtime module capture executable mismatch')
    root = _windows_path(report.get('package_root'))
    expected_exe = ntpath.join(root, 'bin', name)
    _windows_path(report.get('executable'))
    if report.get('executable_sha256') != sha256(package / 'bin' / name):
        raise RuntimeError('Captured executable differs from the hash-bound package')
    try:
        sampled = datetime.fromisoformat(report['sampled_at_utc'])
        created = report['process_created_unix']
        if (sampled.tzinfo is None or sampled.utcoffset() != timezone.utc.utcoffset(sampled)
                or type(created) not in (int, float) or not 0 < created <= sampled.timestamp()
                or not isinstance(report.get('command_line'), list) or not report['command_line']
                or any(not isinstance(arg, str) for arg in report['command_line'])):
            raise ValueError('Invalid capture time/process identity')
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError('Windows capture is missing valid process/time identity') from error
    paths = report.get('module_paths')
    raw = report.get('raw_modules')
    if (not isinstance(paths, list) or not paths or not isinstance(raw, list) or not raw
            or any(not isinstance(item, dict) or not isinstance(item.get('path'), str) for item in raw)):
        raise RuntimeError('Windows capture is missing raw memory-map evidence')
    path_set = {_windows_path(path) for path in paths}
    executable_paths = [path for path in paths if ntpath.basename(path).lower() == name]
    if len(path_set) != len(paths) or len(executable_paths) != 1:
        raise RuntimeError('Windows module paths are duplicate or omit the executable')
    raw_paths = {_windows_path(item['path']) for item in raw
                 if item['path'].lower().endswith(('.dll', '.exe'))}
    if raw_paths != path_set:
        raise RuntimeError('Windows module paths differ from raw memory-map evidence')
    identities = report.get('path_identities')
    identity_paths = {report['executable'], report['command_line'][0], *executable_paths}
    identity_paths.update(path for path in paths if CRT_NAME.fullmatch(ntpath.basename(path)))
    if not isinstance(identities, dict) or set(identities) != identity_paths:
        raise RuntimeError('Windows capture is missing exact raw-path identities')
    executable_identity = None
    for path in (report['executable'], report['command_line'][0], *executable_paths):
        identity = _verify_path_identity(identities[path], path, expected_exe, package / 'bin' / name)
        if executable_identity is not None and identity['file_id'] != executable_identity['file_id']:
            raise RuntimeError('Windows capture executable/argv/module filesystem identities differ')
        executable_identity = identity
    runtime = inspect_runtime(package)
    required = required_crt_modules(package, package / 'bin' / name)
    proof = report.get('runtime')
    if (not isinstance(proof, dict) or proof.get('passed') is not True
            or proof.get('mode') != 'AppLocal' or proof.get('required_modules') != required
            or not isinstance(proof.get('modules'), dict)):
        raise RuntimeError('Windows capture import closure/runtime mode mismatch')
    observed = {}
    for path in paths:
        basename = ntpath.basename(path).lower()
        if not CRT_NAME.fullmatch(basename):
            continue
        if basename not in RUNTIME_NAMES:
            raise RuntimeError(f'Captured unreviewed VC runtime module: {path}')
        _verify_path_identity(identities[path], path, ntpath.join(root, 'bin', basename),
                              package / 'bin' / basename)
        if basename in observed:
            raise RuntimeError(f'Duplicate captured VC runtime module: {basename}')
        observed[basename] = path
    if not observed or not set(required).issubset(observed) or set(proof['modules']) != set(observed):
        raise RuntimeError('Windows capture is missing required or reported VC runtime modules')
    for basename, path in observed.items():
        entry = proof['modules'][basename]
        if (not isinstance(entry, dict)
                or _windows_path(entry.get('path')) != _windows_path(identities[path]['resolved_path'])):
            raise RuntimeError(f'Windows runtime identity path mismatch: {basename}')
        expected = runtime['files'][basename]
        if any(entry.get(key) != expected[key] for key in ('sha256', 'bytes', 'version', 'machine')):
            raise RuntimeError(f'Windows runtime identity differs from hash-bound package: {basename}')
    return {'passed': True, 'required_modules': required, 'observed_modules': sorted(observed)}
