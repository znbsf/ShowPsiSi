"""Read-only live exercise of the publisher's exact artifact download transport.

The CI upload step supplies a tiny known-text archive. This probe can only read
its own run's artifact through the fixed repository API; it never calls publish,
executes archive code, writes a repository ref/release, or logs credentials/URLs.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

import release_publisher as release

PROBE = b'ShowPsiSi verified artifact transport probe v1\n'
PROBE_PATH = Path('artifacts/release-transport/probe.txt')
MAX_PROBE = 64 * 1024


def verify(api, artifact_id, run_id, attempt, expected_digest, work):
    for value in (artifact_id, run_id, attempt):
        release.positive_id(value)
    release.require(release.HASH.fullmatch(expected_digest or '') is not None, 'Invalid probe upload digest')
    run = api.api(release.PREFIX + f'/actions/runs/{run_id}')
    release.require(run.get('id') == run_id and run.get('run_attempt') == attempt
                    and run.get('repository', {}).get('id') == release.REPOSITORY_ID
                    and run.get('head_repository', {}).get('id') == release.REPOSITORY_ID
                    and release.SHA.fullmatch(run.get('head_sha', '')), 'Probe run identity mismatch')
    artifact = api.api(release.PREFIX + f'/actions/artifacts/{artifact_id}')
    identity = artifact.get('workflow_run', {})
    release.require(artifact.get('id') == artifact_id and artifact.get('expired') is False
                    and artifact.get('name') == f'release-transport-probe-{attempt}'
                    and identity.get('id') == run_id and identity.get('head_sha') == run['head_sha']
                    and identity.get('repository_id') == release.REPOSITORY_ID
                    and identity.get('head_repository_id') == release.REPOSITORY_ID,
                    'Probe artifact identity mismatch')
    path = release.PREFIX + f'/actions/artifacts/{artifact_id}/zip'
    size = artifact.get('size_in_bytes')
    release.require(type(size) is int and 0 < size <= MAX_PROBE
                    and artifact.get('digest') == 'sha256:' + expected_digest
                    and artifact.get('archive_download_url') == release.API + path,
                    'Probe artifact hash/size/origin mismatch')
    archive = work / 'probe.zip'
    api.download(path, archive, expected_digest, size)
    destination = work / 'extracted'
    release.safe_extract(archive, destination)
    release.require({p.name for p in destination.iterdir()} == {'probe.txt'}
                    and (destination / 'probe.txt').read_bytes() == PROBE,
                    'Probe payload is not the exact expected text')
    return {'passed': True, 'run_id': run_id, 'run_attempt': attempt, 'source_sha': run['head_sha'],
            'artifact_id': artifact_id, 'archive_sha256': expected_digest, 'archive_bytes': size}


def main():
    if sys.argv[1:] == ['--prepare']:
        PROBE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PROBE_PATH.open('xb') as stream:
            stream.write(PROBE)
        return
    release.require(not sys.argv[1:], 'Unsupported transport probe arguments')
    release.require(os.environ.get('GITHUB_REPOSITORY') == release.REPOSITORY, 'Wrong probe repository')
    api = release.GitHub(os.environ.get('GITHUB_TOKEN', ''))
    with tempfile.TemporaryDirectory(prefix='showpsisi-transport-') as directory:
        result = verify(api, int(os.environ['PROBE_ARTIFACT_ID']), int(os.environ['GITHUB_RUN_ID']),
                        int(os.environ['GITHUB_RUN_ATTEMPT']), os.environ['PROBE_ARCHIVE_DIGEST'], Path(directory))
    print('Verified live artifact transport: ' + json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        detail = str(error) if isinstance(error, release.ReleaseError) else type(error).__name__
        print('Artifact transport probe stopped: ' + detail, file=sys.stderr)
        sys.exit(1)
