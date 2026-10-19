"""Publish only reviewed, explicitly requested main-push artifacts; never execute artifact code.

The sole write authority is the dedicated release job's short-lived GITHUB_TOKEN.
No credentials, arbitrary URLs, source paths or release text are accepted in the
request. All network errors are sanitized to avoid exposing signed download URLs.
"""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import installer_checks as installer
import portable_checks as portable

REPOSITORY = 'znbsf/ShowPsiSi'
REPOSITORY_ID = 1422615049


def project_version(root):
    text = (root / 'CMakeLists.txt').read_text(encoding='utf-8')
    matches = re.findall(r'^project\(ShowPsiSi VERSION ((?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)) ', text, re.M)
    if len(matches) != 1:
        raise RuntimeError('Canonical stable CMake project version is required')
    return matches[0]


# This module is loaded only from the trusted main checkout, never an artifact.
# A future version also needs new reviewed notes and its own explicit request.
VERSION = project_version(Path(__file__).resolve().parents[2])
TAG = 'v' + VERSION
API = 'https://api.github.com'
PREFIX = '/repos/' + REPOSITORY
REQUEST_PATH = '.github/release-request.json'
SETUP = f'ShowPsiSi-{VERSION}-windows-x64-setup.exe'
PORTABLE = f'ShowPsiSi-{VERSION}-windows-x64-portable.zip'
ARTIFACTS = ('ShowPsiSi-windows-x64-installer', 'ShowPsiSi-windows-x64-portable',
             'windows-installer-validation', 'windows-portable-validation')
JOBS = {'engine-web', 'qt-native', 'tauri-native-build', 'Windows MSVC engine and Qt',
        'Windows Tauri compile and Rust tests'}
WINDOWS_STEPS = {
    'Check hosted Inno compiler engine and installer contracts',
    'Qt update-client security and version tests',
    'Windows engine, protocol and transport regressions',
    'Native Qt offscreen interaction regressions',
    'Validate relocated portable candidate without SDK PATH',
    'Gate binary ZIP on exact runtime and redistribution review',
    'Verify official Microsoft runtime download without executing it',
    'Build per-user installer from exact reviewed payload',
    'Install, upgrade, repair and uninstall in a Unicode path',
    'Bind setup and no-install ZIP to common release checksums',
    'Keep verified Windows installer candidate (never publish a release)',
    'Keep cleared portable CI artifact (never publish a release)',
}
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_EXPANDED = 1024 * 1024 * 1024
MAX_JSON = 4 * 1024 * 1024
SHA = re.compile(r'[a-f0-9]{40}')
HASH = re.compile(r'[a-f0-9]{64}')


class ReleaseError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ReleaseError(message)


def positive_id(value):
    require(type(value) is int and 0 < value < 10**16, 'Invalid numeric GitHub identifier')
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON object key')
        result[key] = value
    return result


def decode_json(raw, limit=MAX_JSON):
    require(len(raw) <= limit, 'JSON exceeds bounded size')
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object)


def read_json(path):
    require(path.stat().st_size <= MAX_JSON, 'JSON file exceeds bounded size')
    return decode_json(path.read_bytes())


def sha256(path):
    return portable.digest(path)


def check_url(url, download=False):
    """Only GitHub API, GitHub release CDN and Actions' Azure artifact namespace.

    Azure URLs are admitted ONLY after a redirect from the exact authenticated
    GitHub artifact endpoint, never from request metadata. Their SAS query is
    neither persisted nor logged. No broad *.github.com or Azure wildcard.
    """
    part = urllib.parse.urlsplit(url)
    require(part.scheme == 'https' and part.port in (None, 443)
            and not part.username and not part.password and not part.fragment,
            'Unsafe network destination')
    hosts = {'api.github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'}
    allowed = part.hostname == 'api.github.com'
    if download:
        allowed = part.hostname in hosts or bool(re.fullmatch(
            r'productionresultssa[0-9]+\.blob\.core\.windows\.net', part.hostname or ''))
    require(allowed, 'Unrecognized GitHub download host; review required')
    return part


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class GitHub:
    def __init__(self, token):
        require(bool(token), 'GITHUB_TOKEN is required')
        self._token = token
        # Do not inherit proxy credentials or ambient URL handlers.
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def _open(self, request):
        try:
            return self._opener.open(request, timeout=120)
        except urllib.error.HTTPError as error:
            return error
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ReleaseError('GitHub network request failed; rerun to reconcile state') from None

    def headers(self):
        return {'Authorization': 'Bearer ' + self._token, 'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'ShowPsiSi-verified-publisher'}

    def api(self, path, method='GET', value=None, missing=False):
        require(path.startswith(PREFIX + '/'), 'API path is outside the fixed repository')
        headers = self.headers()
        data = None if value is None else json.dumps(value).encode()
        if data is not None:
            headers['Content-Type'] = 'application/json'
        with self._open(urllib.request.Request(API + path, headers=headers, data=data, method=method)) as response:
            if response.status == 404 and missing:
                return None
            require(200 <= response.status < 300, f'GitHub API failed (HTTP {response.status}); no automatic write retry')
            raw = response.read(MAX_JSON + 1)
        return decode_json(raw)

    def download(self, path, destination, expected_hash, expected_size):
        require(path.startswith(PREFIX + '/actions/artifacts/') or path.startswith(PREFIX + '/releases/assets/'),
                'Download must start at the fixed GitHub API artifact/asset endpoint')
        require(HASH.fullmatch(expected_hash or '') is not None, 'Download SHA-256 is required')
        require(type(expected_size) is int and 0 < expected_size <= MAX_ARCHIVE, 'Download size is out of bounds')
        url = API + path
        for hop in range(4):
            part = check_url(url, download=True)
            # The API credential is sent only on the initial fixed API request.
            headers = self.headers() if hop == 0 else {'User-Agent': 'ShowPsiSi-verified-publisher'}
            headers['Accept'] = 'application/octet-stream'
            with self._open(urllib.request.Request(url, headers=headers)) as response:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get('Location', '')
                    next_url = urllib.parse.urljoin(url, location)
                    target = check_url(next_url, download=True)
                    require(target.hostname != 'api.github.com', 'Download redirect back to API refused')
                    require(hop == 0 or target.hostname == part.hostname,
                            'Download redirect changed CDN host')
                    url = next_url
                    continue
                require(response.status == 200, f'GitHub download failed (HTTP {response.status})')
                length = response.headers.get('Content-Length')
                require(length is None or (length.isdigit() and int(length) == expected_size),
                        'Download Content-Length differs from API metadata')
                total, digest = 0, hashlib.sha256()
                with destination.open('xb') as output:
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        require(total <= expected_size, 'Download exceeded exact expected size')
                        digest.update(chunk)
                        output.write(chunk)
                require(total == expected_size and digest.hexdigest() == expected_hash,
                        'Downloaded bytes fail exact size/SHA-256 verification')
                return
        raise ReleaseError('Too many download redirects')

    def upload(self, release_id, path):
        positive_id(release_id)
        require(path.stat().st_size <= MAX_ARCHIVE, 'Upload exceeds bounded size')
        url = f'https://uploads.github.com{PREFIX}/releases/{release_id}/assets?name=' + urllib.parse.quote(path.name, safe='')
        headers = self.headers()
        headers['Content-Type'] = 'application/octet-stream'
        headers['Content-Length'] = str(path.stat().st_size)
        with self._open(urllib.request.Request(url, headers=headers, data=path.read_bytes(), method='POST')) as response:
            require(response.status == 201, f'GitHub upload failed (HTTP {response.status}); rerun to inspect existing state')
            return decode_json(response.read(MAX_JSON + 1))


def safe_member(info):
    name = info.filename
    require(name and info.orig_filename == name and '\\' not in name and not any(ord(c) < 32 for c in name), 'Unsafe archive filename')
    relative = name.rstrip('/')
    parts = relative.split('/')
    require(not name.startswith('/') and all(p and p not in ('.', '..') and ':' not in p
            and not p.endswith((' ', '.')) and not re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?', p)
            for p in parts), 'Unsafe archive path')
    mode = info.external_attr >> 16
    require(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), 'Archive links/devices are forbidden')
    require(not info.flag_bits & 1, 'Encrypted archives are forbidden')
    require(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'Unsupported archive compression')
    return PurePosixPath(relative)


def safe_extract(archive, destination):
    require(not destination.exists(), 'Refusing stale extraction destination')
    destination.mkdir()
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        require(0 < len(entries) <= 20000, 'Archive file count exceeds bounds')
        seen, components, total = set(), {}, 0
        for info in entries:
            relative = safe_member(info)
            folded = str(relative).casefold()
            require(folded not in seen, 'Duplicate/case-colliding archive entry')
            seen.add(folded)
            for count in range(1, len(relative.parts) + 1):
                component = str(PurePosixPath(*relative.parts[:count]))
                prior = components.setdefault(component.casefold(), component)
                require(prior == component, 'Case-colliding archive directory component')
            total += info.file_size
            require(0 <= info.file_size <= MAX_ARCHIVE and total <= MAX_EXPANDED, 'Archive expansion exceeds bounds')
            target = destination.joinpath(*relative.parts)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as incoming, target.open('xb') as outgoing:
                copied = 0
                while chunk := incoming.read(1024 * 1024):
                    copied += len(chunk)
                    require(copied <= info.file_size, 'Archive entry exceeded declared size')
                    outgoing.write(chunk)
            require(copied == info.file_size, 'Truncated archive entry')


def request_value(value):
    require(isinstance(value, dict) and set(value) == {'schema_version', 'version', 'source_sha', 'ci_run_id'},
            'Release request requires exactly schema_version, version, source_sha and ci_run_id')
    require(type(value['schema_version']) is int and value['schema_version'] == 1 and value['version'] == VERSION,
            'Requested version must match the reviewed CMake source version')
    require(isinstance(value['source_sha'], str) and SHA.fullmatch(value['source_sha']), 'Invalid requested source commit')
    positive_id(value['ci_run_id'])
    return value


def main_sha(api):
    value = api.api(PREFIX + '/git/ref/heads/main')
    require(value.get('ref') == 'refs/heads/main' and value.get('object', {}).get('type') == 'commit', 'Main is not a commit ref')
    value = value['object']['sha']
    require(SHA.fullmatch(value), 'Invalid main source SHA')
    return value


def load_request(api, env, event):
    require(env.get('GITHUB_REPOSITORY') == REPOSITORY and event.get('repository', {}).get('id') == REPOSITORY_ID,
            'Publisher is restricted to the fixed official repository')
    source = main_sha(api)
    trigger_sha = env.get('GITHUB_SHA', '')
    require(SHA.fullmatch(trigger_sha), 'Invalid trigger commit')
    if env.get('GITHUB_EVENT_NAME') == 'push':
        require(env.get('GITHUB_REF') == 'refs/heads/release-publish/' + TAG and event.get('ref') == env['GITHUB_REF']
                and event.get('after') == trigger_sha and not event.get('deleted'), 'Only the matching versioned release-publish request branch is supported')
        commit = api.api(PREFIX + '/commits/' + trigger_sha)
        require([p['sha'] for p in commit.get('parents', [])] == [source],
                'Release request must have current main as its sole parent')
        files = commit.get('files', [])
        require(len(files) == 1 and files[0].get('filename') == REQUEST_PATH
                and files[0].get('status') in ('added', 'modified'), 'Release request commit may change only the bounded request JSON')
        content = api.api(PREFIX + '/contents/' + REQUEST_PATH + '?ref=' + trigger_sha)
        require(content.get('type') == 'file' and content.get('encoding') == 'base64'
                and 0 < content.get('size', 0) <= 2048, 'Invalid release request file')
        raw = base64.b64decode(content['content'], validate=False)
        require(len(raw) == content['size'], 'Release request content length mismatch')
        value = request_value(decode_json(raw, 2048))
    elif env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch':
        require(env.get('GITHUB_REF') == 'refs/heads/main' and trigger_sha == source,
                'Manual publication must run from current main')
        inputs = event.get('inputs', {})
        require(set(inputs) == {'source_sha', 'ci_run_id'} and re.fullmatch(r'[1-9][0-9]{0,15}', inputs.get('ci_run_id', '')),
                'Invalid workflow dispatch inputs')
        value = request_value({'schema_version': 1, 'version': VERSION, 'source_sha': inputs['source_sha'],
                               'ci_run_id': int(inputs['ci_run_id'])})
    else:
        raise ReleaseError('Publication from PRs or other event types is forbidden')
    require(value['source_sha'] == source, 'Requested release source is not current main')
    return value


def validate_ci(api, request):
    run_id, source = request['ci_run_id'], request['source_sha']
    require(main_sha(api) == source, 'Main moved; select and verify its new CI before publishing')
    workflow = api.api(PREFIX + '/actions/workflows/ci.yml')
    run = api.api(PREFIX + f'/actions/runs/{run_id}')
    require(run.get('id') == run_id and run.get('workflow_id') == workflow.get('id')
            and workflow.get('path') == '.github/workflows/ci.yml' and run.get('path') == '.github/workflows/ci.yml'
            and run.get('head_sha') == source and run.get('head_branch') == 'main' and run.get('event') == 'push'
            and run.get('status') == 'completed' and run.get('conclusion') == 'success'
            and run.get('repository', {}).get('id') == REPOSITORY_ID
            and run.get('head_repository', {}).get('id') == REPOSITORY_ID,
            'CI is not successful official main-push CI for the exact release source')
    # Reconstruct the latest execution of each named job, including successful
    # jobs retained when only failed jobs were rerun. Artifact APIs identify only
    # the run: the complete bundle is independently cross-bound by hashes below.
    attempt = run.get('run_attempt')
    require(type(attempt) is int and 1 <= attempt <= 100, 'Invalid or excessive CI attempt count')
    require(request.get('_ci_attempt', attempt) == attempt, 'CI was rerun during publication; reconcile before retry')
    latest = {}
    for number in range(1, attempt + 1):
        result = api.api(PREFIX + f'/actions/runs/{run_id}/attempts/{number}/jobs?per_page=100')
        jobs = result.get('jobs', [])
        names = {j.get('name') for j in jobs}
        require(result.get('total_count') == len(jobs) <= len(JOBS) and len(names) == len(jobs)
                and names <= JOBS, 'CI attempt job set is incomplete or changed; review required')
        for job in jobs:
            require(job.get('run_id') == run_id and job.get('head_sha') == source, 'CI attempt job source mismatch')
            latest[job['name']] = job
    require(set(latest) == JOBS, 'CI job set is incomplete or changed; review required')
    jobs = list(latest.values())
    for job in jobs:
        require(job.get('run_id') == run_id and job.get('head_sha') == source
                and job.get('status') == 'completed' and job.get('conclusion') == 'success', 'A required CI job did not pass')
        if job['name'] == 'Windows MSVC engine and Qt':
            steps = job.get('steps', [])
            require(all(sum(s.get('name') == name and s.get('conclusion') == 'success' for s in steps) == 1
                        for name in WINDOWS_STEPS), 'Windows distribution/acceptance step missing, skipped or failed')
    return run


def fetch_artifacts(api, request, work):
    result = api.api(PREFIX + f'/actions/runs/{request["ci_run_id"]}/artifacts?per_page=100')
    entries = result.get('artifacts', [])
    require(result.get('total_count') == len(entries) <= 100, 'Artifact listing is incomplete or excessive')
    selected = []
    for name in ARTIFACTS:
        matches = [a for a in entries if a.get('name') == name]
        require(len(matches) == 1, 'Required artifact missing or duplicated: ' + name)
        item = matches[0]
        artifact_id = positive_id(item.get('id'))
        identity = item.get('workflow_run', {})
        require(item.get('expired') is False and identity.get('id') == request['ci_run_id']
                and identity.get('head_sha') == request['source_sha'] and identity.get('head_branch') == 'main'
                and identity.get('repository_id') == REPOSITORY_ID and identity.get('head_repository_id') == REPOSITORY_ID,
                'Artifact has wrong source/run/repository identity or is expired')
        digest = item.get('digest', '')
        require(isinstance(digest, str) and digest.startswith('sha256:') and HASH.fullmatch(digest[7:]),
                'Artifact is missing its GitHub SHA-256 digest')
        path = PREFIX + f'/actions/artifacts/{artifact_id}/zip'
        require(item.get('archive_download_url') == API + path, 'Unexpected artifact API origin')
        archive = work / (name + '.zip')
        api.download(path, archive, digest[7:], item['size_in_bytes'])
        safe_extract(archive, work / name)
        selected.append({'id': artifact_id, 'name': name, 'sha256': digest[7:], 'bytes': item['size_in_bytes']})
    return selected


def exact_checksums(raw, expected):
    require(len(raw) <= 2048, 'Checksum file exceeds bounds')
    lines = raw.decode('ascii').splitlines()
    require(len(lines) == len(expected) and all(re.fullmatch(r'[a-f0-9]{64}  [A-Za-z0-9._-]+', line) for line in lines),
            'Malformed or excessive checksum entries')
    actual = {}
    for line in lines:
        digest, name = line.split('  ')
        require(name not in actual, 'Duplicate checksum filename')
        actual[name] = digest
    require(actual == expected, 'Release checksums do not bind the exact setup/portable bytes')


def check_steps(smoke):
    expected = {'reject-uninstalled-update': False, 'install-previous': True, 'reject-live-app-update': False,
                'reject-live-app-uninstall': False, 'upgrade': True, 'reinstall': True,
                'reject-downgrade': False, 'uninstall': True}
    steps = smoke.get('steps', [])
    require(len(steps) == len(expected) and {s.get('name') for s in steps} == set(expected), 'Installer acceptance steps incomplete')
    require(all(type(s.get('exit_code')) is int and (s['exit_code'] == 0) == expected[s['name']] for s in steps),
            'Installer acceptance exit status mismatch')


def validate_payload(work, request):
    setup_dir, zip_dir, installer_evidence, portable_evidence = [work / name for name in ARTIFACTS]
    require({p.name for p in setup_dir.iterdir()} == {SETUP, 'SHA256SUMS', 'installer-build.json'},
            'Unexpected files in setup artifact')
    require({p.name for p in zip_dir.iterdir()} == {PORTABLE, PORTABLE + '.sha256', 'SHA256SUMS'},
            'Unexpected files in portable artifact')
    setup, zipped = setup_dir / SETUP, zip_dir / PORTABLE
    with setup.open('rb') as stream:
        require(stream.read(2) == b'MZ', 'Setup is not a Windows executable')
    hashes = {SETUP: sha256(setup), PORTABLE: sha256(zipped)}
    exact_checksums((setup_dir / 'SHA256SUMS').read_bytes(), hashes)
    require((setup_dir / 'SHA256SUMS').read_bytes() == (zip_dir / 'SHA256SUMS').read_bytes(), 'Artifact checksum files disagree')
    exact_checksums((zip_dir / (PORTABLE + '.sha256')).read_bytes(), {PORTABLE: hashes[PORTABLE]})
    safe_extract(zipped, work / 'payload')
    require({p.name for p in (work / 'payload').iterdir()} == {'ShowPsiSi-windows-x64'}, 'Unexpected portable ZIP root')
    package = work / 'payload/ShowPsiSi-windows-x64'
    # Strictly parse only consumed control metadata. Upstream attribution JSON is
    # opaque licensed source/notice data (some contains duplicate keys/control
    # characters); every such byte is still bound by the exact manifest/review.
    for name in ('manifest.json', 'build-information.json', 'redistribution-review.json', 'bin/showpsisi-portable.json'):
        read_json(package / name)
    manifest = read_json(package / 'manifest.json')
    require(manifest.get('schema_version') == 1 and manifest.get('scope') == 'windows-x64-qt-core', 'Invalid package manifest scope')
    build = read_json(package / 'build-information.json')
    require(manifest.get('build') == build and build.get('source_commit') == request['source_sha']
            and build.get('application_version') == VERSION, 'Package build/version/source mismatch')
    marker = read_json(package / 'bin/showpsisi-portable.json')
    require(marker.get('schema_version') == 1 and marker.get('resource_root') == '..' and marker.get('scope') == 'qt-core',
            'Portable package marker is invalid')
    manifest_hash = sha256(package / 'manifest.json')
    for name in ('manifest.json', 'build-information.json'):
        require((package / name).read_bytes() == (portable_evidence / 'portable-stage' / name).read_bytes(),
                'Portable evidence is not for the release payload')
    validation_dir = portable_evidence / 'portable-validation'
    validation = read_json(validation_dir / 'portable-validation.json')
    require(validation.get('runtime_requirement', {}).get('required_minimum') == installer.MINIMUM_RUNTIME,
            'Portable validation runtime minimum mismatch')
    require(not list(portable_evidence.rglob('distribution-gate.json')), 'A blocked distribution gate is present')
    # These helpers only hash/read files and validate exact dependency inventories.
    installer.gate(package, validation_dir, request['source_sha'], VERSION)
    preflight = read_json(portable_evidence / 'portable-launcher-probe/preflight.json')
    expected_cases = {'host-runtime-ready': 0, 'missing-runtime-blocked': 1, 'old-runtime-blocked': 1}
    cases = preflight.get('cases', [])
    require(preflight.get('passed') is True and 'error' not in preflight
            and preflight.get('launcher_sha256') == sha256(package / 'Launch Qt.cmd')
            and len(cases) == len(expected_cases) and {c.get('name'): c.get('exit_code') for c in cases} == expected_cases,
            'Portable launcher prerequisite acceptance is incomplete')
    record = read_json(setup_dir / 'installer-build.json')
    require(record == read_json(installer_evidence / 'artifacts/installer-candidate/installer-build.json'),
            'Installer build evidence differs between artifacts')
    require(record.get('schema_version') == 1 and record.get('version') == VERSION and record.get('test_fixture') is False
            and record.get('source_commit') == request['source_sha'] and record.get('asset_name') == SETUP
            and record.get('installer_sha256') == hashes[SETUP] and record.get('installer_bytes') == setup.stat().st_size
            and record.get('package_manifest_sha256') == manifest_hash and record.get('signing') == 'unsigned candidate',
            'Installer identity is not bound to the exact approved payload')
    runtime = record.get('prerequisite', {})
    require(runtime == read_json(installer_evidence / '.deps/installer-prerequisite/vc-runtime.json'), 'Microsoft runtime provenance differs')
    installer.verify_prerequisite(runtime)
    smoke = read_json(installer_evidence / 'artifacts/installer-validation/installer-smoke.json')
    require(all(smoke.get(key) is True for key in ('passed', 'settings_preserved', 'shortcuts_verified', 'all_manifested_payload_removed'))
            and 'error' not in smoke and 'cleanup_error' not in smoke
            and smoke.get('installer_sha256') == hashes[SETUP] and smoke.get('package_manifest_sha256') == manifest_hash
            and smoke.get('production_core_mutex') == {'held_while_running': True, 'released_after_exit': True},
            'Installer acceptance failed, incomplete or bound to different bytes')
    check_steps(smoke)
    # These limitations are deliberate release disclosures, never converted to pass.
    require(all(smoke.get(key) is False for key in ('clean_machine_verified', 'native_dialogs_verified', 'runtime_bootstrap_exercised'))
            and validation.get('native_windows_desktop_verified') is False, 'Acceptance boundary changed; review release disclosures')
    return {SETUP: setup, PORTABLE: zipped, 'SHA256SUMS': setup_dir / 'SHA256SUMS'}, manifest_hash, runtime['sha256']


def release_body(root, request):
    notes = (root / f'docs/releases/{TAG}.md').read_text(encoding='utf-8').strip()
    require(100 < len(notes) < 20000, 'Reviewed release notes are missing or excessive')
    return notes + f'\n\nSource: https://github.com/{REPOSITORY}/commit/{request["source_sha"]}\nCI: https://github.com/{REPOSITORY}/actions/runs/{request["ci_run_id"]}\n'


def tag_target(api):
    tag = api.api(PREFIX + '/git/ref/tags/' + TAG, missing=True)
    if tag is None:
        return None
    require(tag.get('ref') == 'refs/tags/' + TAG, 'Unexpected tag reference')
    obj = tag.get('object', {})
    for _ in range(4):
        require(SHA.fullmatch(obj.get('sha', '')), 'Invalid tag object')
        if obj.get('type') == 'commit':
            return obj['sha']
        require(obj.get('type') == 'tag', 'Tag does not resolve to a commit')
        obj = api.api(PREFIX + '/git/tags/' + obj['sha']).get('object', {})
    raise ReleaseError('Excessive annotated tag nesting')


def find_release(api):
    matches = []
    for page in range(1, 11):
        values = api.api(PREFIX + f'/releases?per_page=100&page={page}')
        require(isinstance(values, list), 'Invalid release listing')
        matches.extend(r for r in values if r.get('tag_name') == TAG)
        if len(values) < 100:
            break
    else:
        raise ReleaseError('Release listing exceeds reviewed pagination bound')
    require(len(matches) <= 1, 'Duplicate releases for the requested tag')
    return matches[0] if matches else None


def validate_release(release, source, body):
    positive_id(release.get('id'))
    require(release.get('tag_name') == TAG and release.get('target_commitish') == source
            and release.get('name') == 'ShowPsiSi ' + TAG and release.get('body') == body
            and release.get('prerelease') is False and type(release.get('draft')) is bool,
            'Existing release metadata differs; refusing to modify it')


def verify_assets(api, release_id, files, work, allow_missing):
    assets = api.api(PREFIX + f'/releases/{release_id}/assets?per_page=100')
    require(isinstance(assets, list) and len(assets) <= len(files)
            and len({a.get('name') for a in assets}) == len(assets)
            and all(a.get('name') in files for a in assets), 'Unknown/duplicate assets exist; nothing will be overwritten or deleted')
    found = set()
    for asset in assets:
        name = asset['name']
        asset_id = positive_id(asset.get('id'))
        local = files[name]
        expected = sha256(local)
        require(asset.get('state') == 'uploaded' and asset.get('size') == local.stat().st_size
                and asset.get('digest') == 'sha256:' + expected, 'Existing/uploaded release asset differs or is incomplete')
        # Byte-level readback is required even when GitHub supplies a matching digest.
        target = work / f'verify-{asset_id}-{len(list(work.glob("verify-*")))}'
        api.download(PREFIX + f'/releases/assets/{asset_id}', target, expected, local.stat().st_size)
        target.unlink()
        found.add(name)
    require(allow_missing or found == set(files), 'Published release is missing required assets')
    return set(files) - found


def publish(api, request, files, body, work):
    source = request['source_sha']
    require(tag_target(api) in (None, source), 'Existing tag points to a different source; refusing publication')
    release = find_release(api)
    if release is not None:
        validate_release(release, source, body)
        missing = verify_assets(api, release['id'], files, work, allow_missing=release['draft'])
        if not release['draft']:
            require(tag_target(api) == source, 'Published tag/source mismatch')
            return release
    else:
        missing = set(files)
    # All artifact validation and conflict checks finish before the first mutation.
    validate_ci(api, request)
    if tag_target(api) is None:
        api.api(PREFIX + '/git/refs', 'POST', {'ref': 'refs/tags/' + TAG, 'sha': source})
    require(tag_target(api) == source, 'Tag identity changed during publication')
    if release is None:
        release = api.api(PREFIX + '/releases', 'POST', {'tag_name': TAG, 'target_commitish': source,
                          'name': 'ShowPsiSi ' + TAG, 'body': body, 'draft': True, 'prerelease': False})
        validate_release(release, source, body)
        require(release['draft'], 'New release unexpectedly public')
    for name in sorted(missing):
        api.upload(release['id'], files[name])
    verify_assets(api, release['id'], files, work, allow_missing=False)
    validate_ci(api, request)
    require(tag_target(api) == source, 'Tag moved before publication')
    current = api.api(PREFIX + f'/releases/{release["id"]}')
    validate_release(current, source, body)
    if current['draft']:
        api.api(PREFIX + f'/releases/{release["id"]}', 'PATCH', {'draft': False, 'make_latest': 'true'})
    final = api.api(PREFIX + f'/releases/{release["id"]}')
    validate_release(final, source, body)
    require(final['draft'] is False and tag_target(api) == source, 'Publication could not be verified; inspect state before retry')
    verify_assets(api, release['id'], files, work, allow_missing=False)
    return final


def main():
    root = Path(__file__).resolve().parents[2]
    api = GitHub(os.environ.get('GITHUB_TOKEN', ''))
    event = read_json(Path(os.environ['GITHUB_EVENT_PATH']))
    request = load_request(api, os.environ, event)
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    require(head == request['source_sha'], 'Publisher must execute from the exact reviewed main checkout')
    require(subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--'], cwd=root).returncode == 0, 'Publisher checkout is modified')
    run = validate_ci(api, request)
    request = dict(request, _ci_attempt=run['run_attempt'])
    with tempfile.TemporaryDirectory(prefix='showpsisi-release-') as directory:
        work = Path(directory)
        artifacts = fetch_artifacts(api, request, work)
        files, manifest_hash, runtime_hash = validate_payload(work, request)
        provenance = {'schema_version': 1, 'repository': REPOSITORY, 'version': VERSION, 'source_sha': request['source_sha'],
                      'ci_run_id': request['ci_run_id'], 'ci_run_attempt': run['run_attempt'], 'artifacts': artifacts,
                      'artifact_attempt_identity': 'GitHub supplies run identity only; full bundle cross-bound by source and hashes',
                      'assets': {name: {'sha256': sha256(path), 'bytes': path.stat().st_size} for name, path in files.items()},
                      'package_manifest_sha256': manifest_hash, 'microsoft_prerequisite_sha256': runtime_hash,
                      'installer_signing': 'unsigned', 'clean_machine_verified': False, 'native_dialogs_verified': False,
                      'missing_runtime_bootstrap_verified': False, 'live_future_version_update_verified': False,
                      'portable_update': 'Browser ZIP download; manual checksum verification and new-folder replacement'}
        provenance_path = work / 'release-provenance.json'
        provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        files[provenance_path.name] = provenance_path
        publish(api, request, files, release_body(root, request), work)
    print(f'Verified publication: https://github.com/{REPOSITORY}/releases/tag/{TAG}')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Do not include exception messages from urllib/JSON/ZIP or raw responses:
        # they may contain signed URLs, credentials, or untrusted artifact text.
        detail = str(error) if isinstance(error, ReleaseError) else type(error).__name__
        print('Publication stopped: ' + detail, file=sys.stderr)
        sys.exit(1)
