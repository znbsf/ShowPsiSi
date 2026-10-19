"""Offline fail-closed publication tests; no tokens, network, or real release writes."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/ci'))
import release_publisher as release

SOURCE = 'a' * 40
TRIGGER = 'b' * 40
OTHER_VERSION = str(int(release.VERSION.split('.')[0]) + 1) + '.0.0'
REQUEST = {'schema_version': 1, 'version': release.VERSION, 'source_sha': SOURCE, 'ci_run_id': 123}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


def runtime_signature_fixture(metadata):
    """Synthetic native report for inert unit bytes, never a signature claim."""
    return [{'name': name, 'sha256': identity['sha256'], 'signature_status': 'Valid',
             'signer_subject': 'CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US',
             'signer_thumbprint': 'ABCDEF0123' * 4} for name, identity in metadata['files'].items()]


class TemporaryTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)


class ArchiveTests(TemporaryTest):
    def archive(self, entries):
        path = self.work / 'archive.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            for name, data in entries:
                archive.writestr(name, data)
        return path

    def test_regular_unicode_files_extract(self):
        archive = self.archive([('folder/中文 space.json', b'{}')])
        release.safe_extract(archive, self.work / 'out')
        self.assertEqual((self.work / 'out/folder/中文 space.json').read_bytes(), b'{}')

    def test_unsafe_paths_are_rejected(self):
        for name in ('../escape', '/tmp/escape', 'C:/escape', 'a\\b', 'a//b', 'a/./b', 'nul.txt',
                     'a/con', 'dir./x', 'dir /x', 'file:stream', 'a\nfile', 'nul\x00ignored'):
            with self.subTest(name=name):
                info = zipfile.ZipInfo(name)
                with self.assertRaises(release.ReleaseError):
                    release.safe_member(info)

    def test_links_and_devices_are_rejected(self):
        for mode in (stat.S_IFLNK, stat.S_IFBLK, stat.S_IFIFO, stat.S_IFSOCK):
            info = zipfile.ZipInfo('file')
            info.external_attr = (mode | 0o777) << 16
            with self.subTest(mode=mode), self.assertRaises(release.ReleaseError):
                release.safe_member(info)

    def test_duplicate_case_collisions_rejected(self):
        archive = self.archive([('a/file', b'a'), ('A/FILE', b'b')])
        with self.assertRaisesRegex(release.ReleaseError, 'colliding'):
            release.safe_extract(archive, self.work / 'out')

    def test_expansion_limit_rejected(self):
        archive = self.archive([('file', b'abc')])
        with mock.patch.object(release, 'MAX_EXPANDED', 2), self.assertRaisesRegex(release.ReleaseError, 'expansion'):
            release.safe_extract(archive, self.work / 'out')

    def test_case_colliding_parent_directories_rejected(self):
        archive = self.archive([('A/one', b'a'), ('a/two', b'b')])
        with self.assertRaisesRegex(release.ReleaseError, 'Case-colliding'):
            release.safe_extract(archive, self.work / 'out')

    def test_stale_destination_never_overwritten(self):
        archive = self.archive([('file', b'a')])
        out = self.work / 'out'
        out.mkdir()
        with self.assertRaisesRegex(release.ReleaseError, 'stale'):
            release.safe_extract(archive, out)

    def test_encryption_and_unknown_compression_rejected(self):
        info = zipfile.ZipInfo('file')
        info.flag_bits = 1
        with self.assertRaises(release.ReleaseError):
            release.safe_member(info)
        info.flag_bits = 0
        info.compress_type = zipfile.ZIP_LZMA
        with self.assertRaises(release.ReleaseError):
            release.safe_member(info)


class RequestTests(unittest.TestCase):
    def api(self, request=REQUEST, files=None, parents=None):
        raw = json.dumps(request).encode()
        def get(path, **kwargs):
            if path.endswith('/git/ref/heads/main'):
                return {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': SOURCE}}
            if '/commits/' in path:
                return {'parents': parents if parents is not None else [{'sha': SOURCE}],
                        'files': files if files is not None else [{'filename': release.REQUEST_PATH, 'status': 'added'}]}
            return {'type': 'file', 'encoding': 'base64', 'size': len(raw), 'content': base64.b64encode(raw).decode()}
        return mock.Mock(api=mock.Mock(side_effect=get))

    def context(self):
        env = {'GITHUB_REPOSITORY': release.REPOSITORY, 'GITHUB_EVENT_NAME': 'push',
               'GITHUB_REF': 'refs/heads/release-publish/' + release.TAG, 'GITHUB_SHA': TRIGGER}
        event = {'repository': {'id': release.REPOSITORY_ID}, 'ref': env['GITHUB_REF'], 'after': TRIGGER, 'deleted': False}
        return env, event

    def test_exact_dedicated_request_commit_is_accepted(self):
        self.assertEqual(release.load_request(self.api(), *self.context()), REQUEST)

    def test_additional_changed_file_rejects_branch_execution(self):
        files = [{'filename': release.REQUEST_PATH, 'status': 'added'}, {'filename': 'evil.py', 'status': 'added'}]
        with self.assertRaisesRegex(release.ReleaseError, 'only'):
            release.load_request(self.api(files=files), *self.context())

    def test_non_main_parent_or_merge_commit_rejected(self):
        for parents in ([], [{'sha': TRIGGER}], [{'sha': SOURCE}, {'sha': TRIGGER}]):
            with self.subTest(parents=parents), self.assertRaises(release.ReleaseError):
                release.load_request(self.api(parents=parents), *self.context())

    def test_pr_wrong_branch_wrong_repository_and_deleted_events_rejected(self):
        for key, value in [('GITHUB_EVENT_NAME', 'pull_request'), ('GITHUB_REF', 'refs/heads/other'),
                           ('GITHUB_REPOSITORY', 'attacker/ShowPsiSi')]:
            env, event = self.context()
            env[key] = value
            with self.subTest(key=key), self.assertRaises(release.ReleaseError):
                release.load_request(self.api(), env, event)
        env, event = self.context()
        event['deleted'] = True
        with self.assertRaises(release.ReleaseError):
            release.load_request(self.api(), env, event)

    def test_wrong_version_source_or_unknown_inputs_rejected(self):
        for key, value in [('version', OTHER_VERSION), ('source_sha', TRIGGER), ('url', 'https://evil.example'),
                           ('ci_run_id', True), ('ci_run_id', -1), ('schema_version', True)]:
            request = dict(REQUEST, **{key: value})
            with self.subTest(key=key, value=value), self.assertRaises(release.ReleaseError):
                release.load_request(self.api(request), *self.context())

    def test_dispatch_requires_current_main_and_numeric_run(self):
        env, event = self.context()
        env.update(GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_REF='refs/heads/main', GITHUB_SHA=SOURCE)
        event['inputs'] = {'source_sha': SOURCE, 'ci_run_id': '123'}
        self.assertEqual(release.load_request(self.api(), env, event), REQUEST)
        for invalid in ('123;echo', '0123', '0', '-1'):
            event['inputs']['ci_run_id'] = invalid
            with self.assertRaises(release.ReleaseError):
                release.load_request(self.api(), env, event)

    def test_wrong_versioned_trigger_branch_is_rejected(self):
        env, event = self.context()
        env['GITHUB_REF'] = event['ref'] = 'refs/heads/release-publish/v' + OTHER_VERSION
        with self.assertRaisesRegex(release.ReleaseError, 'versioned'):
            release.load_request(self.api(), env, event)

    def test_duplicate_json_keys_and_oversize_are_rejected(self):
        with self.assertRaises(release.ReleaseError):
            release.decode_json(b'{"version":"0.1.0","version":"0.2.0"}')
        with self.assertRaises(release.ReleaseError):
            release.decode_json(b'{}', limit=1)


class CITests(unittest.TestCase):
    def setUp(self):
        self.run = {'id': 123, 'workflow_id': 99, 'path': '.github/workflows/ci.yml', 'head_sha': SOURCE,
                    'head_branch': 'main', 'event': 'push', 'status': 'completed', 'conclusion': 'success', 'run_attempt': 1,
                    'repository': {'id': release.REPOSITORY_ID}, 'head_repository': {'id': release.REPOSITORY_ID}}
        self.jobs = [{'name': name, 'run_id': 123, 'head_sha': SOURCE, 'status': 'completed', 'conclusion': 'success',
                      'steps': [{'name': step, 'conclusion': 'success'} for step in (release.WINDOWS_STEPS if name == 'Windows MSVC engine and Qt' else ['Verify live read-only publisher artifact transport'] if name == 'engine-web' else [])]} for name in release.JOBS]

    def api(self):
        def get(path):
            if '/git/ref/' in path:
                return {'ref': 'refs/heads/main', 'object': {'type': 'commit', 'sha': SOURCE}}
            if '/workflows/' in path:
                return {'id': 99, 'path': '.github/workflows/ci.yml'}
            if '/jobs?' in path:
                return {'total_count': len(self.jobs), 'jobs': self.jobs}
            return self.run
        return mock.Mock(api=mock.Mock(side_effect=get))

    def test_exact_main_push_all_jobs_and_acceptance_pass(self):
        self.assertEqual(release.validate_ci(self.api(), REQUEST), self.run)

    def test_missing_skipped_or_failed_live_transport_blocks_publication(self):
        engine = next(job for job in self.jobs if job['name'] == 'engine-web')
        for conclusion in ('skipped', 'failure', None):
            engine['steps'][0]['conclusion'] = conclusion
            with self.subTest(conclusion=conclusion), self.assertRaisesRegex(release.ReleaseError, 'transport preflight'):
                release.validate_ci(self.api(), REQUEST)
        engine['steps'] = []
        with self.assertRaisesRegex(release.ReleaseError, 'transport preflight'):
            release.validate_ci(self.api(), REQUEST)

    def test_pr_wrong_source_pending_failed_or_invalid_attempt_rejected(self):
        original = copy.deepcopy(self.run)
        for key, value in [('event', 'pull_request'), ('head_sha', TRIGGER), ('head_branch', 'release-publish'),
                           ('status', 'in_progress'), ('conclusion', 'failure'), ('run_attempt', 0), ('workflow_id', 100),
                           ('head_repository', {'id': 2})]:
            self.run = dict(original, **{key: value})
            with self.subTest(key=key), self.assertRaises(release.ReleaseError):
                release.validate_ci(self.api(), REQUEST)

    def test_recoverable_failed_job_rerun_retains_prior_successes(self):
        self.run['run_attempt'] = 2
        first = copy.deepcopy(self.jobs)
        failed = next(j for j in first if j['name'] == 'engine-web')
        failed['conclusion'] = 'failure'
        second = [copy.deepcopy(next(j for j in self.jobs if j['name'] == 'engine-web'))]
        api = self.api()
        base = api.api.side_effect
        def get(path):
            if '/attempts/1/' in path:
                return {'total_count': len(first), 'jobs': first}
            if '/attempts/2/' in path:
                return {'total_count': len(second), 'jobs': second}
            return base(path)
        api.api.side_effect = get
        self.assertEqual(release.validate_ci(api, REQUEST)['run_attempt'], 2)

    def test_later_failure_cannot_reuse_an_earlier_pass(self):
        self.run['run_attempt'] = 2
        api = self.api()
        base = api.api.side_effect
        later = copy.deepcopy(self.jobs[0])
        later['conclusion'] = 'failure'
        def get(path):
            if '/attempts/2/' in path:
                return {'total_count': 1, 'jobs': [later]}
            return base(path)
        api.api.side_effect = get
        with self.assertRaisesRegex(release.ReleaseError, 'did not pass'):
            release.validate_ci(api, REQUEST)

    def test_rerun_windows_gate_cannot_reuse_earlier_success(self):
        self.run['run_attempt'] = 2
        api = self.api()
        base = api.api.side_effect
        later = copy.deepcopy(next(j for j in self.jobs if j['name'] == 'Windows MSVC engine and Qt'))
        later['steps'][0]['conclusion'] = 'skipped'
        def get(path):
            if '/attempts/2/' in path:
                return {'total_count': 1, 'jobs': [later]}
            return base(path)
        api.api.side_effect = get
        with self.assertRaisesRegex(release.ReleaseError, 'step missing, skipped'):
            release.validate_ci(api, REQUEST)

    def test_new_ci_attempt_during_publication_is_rejected(self):
        self.run['run_attempt'] = 2
        with self.assertRaisesRegex(release.ReleaseError, 'rerun during'):
            release.validate_ci(self.api(), dict(REQUEST, _ci_attempt=1))

    def test_missing_duplicate_or_failed_job_rejected(self):
        self.jobs.pop()
        with self.assertRaisesRegex(release.ReleaseError, 'job set'):
            release.validate_ci(self.api(), REQUEST)
        self.setUp()
        self.jobs[0]['conclusion'] = 'skipped'
        with self.assertRaisesRegex(release.ReleaseError, 'did not pass'):
            release.validate_ci(self.api(), REQUEST)

    def test_successful_job_cannot_hide_skipped_release_gate(self):
        windows = next(j for j in self.jobs if j['name'] == 'Windows MSVC engine and Qt')
        windows['steps'][0]['conclusion'] = 'skipped'
        with self.assertRaisesRegex(release.ReleaseError, 'step'):
            release.validate_ci(self.api(), REQUEST)


class DownloadTests(TemporaryTest):
    def response(self, status, body=b'', headers=None):
        value = io.BytesIO(body)
        value.status = status
        value.headers = headers or {}
        return value

    def test_redirect_strips_authorization_and_checks_hash(self):
        api = release.GitHub('unit-test-secret')
        payload = b'expected'
        responses = [self.response(302, headers={'Location': 'https://productionresultssa18.blob.core.windows.net/actions-results/file.zip?sig=secret'}),
                     self.response(200, payload, {'Content-Length': str(len(payload))})]
        requests = []
        def opened(request):
            requests.append(request)
            return responses.pop(0)
        with mock.patch.object(api, '_open', side_effect=opened):
            api.download(release.PREFIX + '/actions/artifacts/1/zip', self.work / 'file', hashlib.sha256(payload).hexdigest(), len(payload))
        self.assertEqual(requests[0].get_header('Authorization'), 'Bearer unit-test-secret')
        self.assertIsNone(requests[1].get_header('Authorization'))
        self.assertEqual(requests[0].get_header('Accept'), 'application/vnd.github+json')
        self.assertEqual(requests[1].get_header('Accept'), 'application/octet-stream')
        self.assertEqual((self.work / 'file').read_bytes(), payload)

    def test_release_asset_binary_accept_and_redirect_credential_removal(self):
        api = release.GitHub('unit-test-secret')
        payload = b'release-asset-bytes'
        responses = [self.response(302, headers={'Location': 'https://release-assets.githubusercontent.com/file?signature=private'}),
                     self.response(200, payload)]
        requests = []
        def opened(request):
            requests.append(request)
            return responses.pop(0)
        with mock.patch.object(api, '_open', side_effect=opened), mock.patch('builtins.print') as logged:
            api.download(release.PREFIX + '/releases/assets/1', self.work / 'asset', hashlib.sha256(payload).hexdigest(), len(payload))
        self.assertEqual([r.get_header('Accept') for r in requests], ['application/octet-stream'] * 2)
        self.assertEqual(requests[0].get_header('Authorization'), 'Bearer unit-test-secret')
        self.assertIsNone(requests[1].get_header('Authorization'))
        logged.assert_called_once_with('Verified download redirect host: release-assets.githubusercontent.com')
        self.assertEqual((self.work / 'asset').read_bytes(), payload)

    def test_artifact_media_type_error_fails_without_fallback_retry(self):
        api = release.GitHub('unit-test-secret')
        with mock.patch.object(api, '_open', return_value=self.response(415)) as opened:
            with self.assertRaisesRegex(release.ReleaseError, 'HTTP 415'):
                api.download(release.PREFIX + '/actions/artifacts/1/zip', self.work / 'file', 'a' * 64, 8)
        self.assertEqual(opened.call_count, 1)
        self.assertFalse((self.work / 'file').exists())

    def test_unrecognized_http_userinfo_port_and_spoofed_hosts_rejected(self):
        for url in ('http://api.github.com/x', 'https://api.github.com:444/x', 'https://token@api.github.com/x',
                    'https://api.github.com.evil.example/x', 'https://evil.blob.core.windows.net/x',
                    'https://github.com/attacker/file', 'https://productionresultssa18.blob.core.windows.net.evil/x'):
            with self.subTest(url=url), self.assertRaises(release.ReleaseError):
                release.check_url(url, download=True)

    def test_redirect_cannot_exfiltrate_token_or_contact_unknown_host(self):
        api = release.GitHub('unit-test-secret')
        with mock.patch.object(api, '_open', return_value=self.response(302, headers={'Location': 'https://evil.example'})) as opened:
            with self.assertRaises(release.ReleaseError):
                api.download(release.PREFIX + '/actions/artifacts/1/zip', self.work / 'file', 'a' * 64, 8)
        self.assertEqual(opened.call_count, 1)

    def test_wrong_hash_truncation_or_extra_bytes_rejected(self):
        for index, payload in enumerate((b'wrong!!!', b'short', b'too much data')):
            api = release.GitHub('unit-test-secret')
            with mock.patch.object(api, '_open', return_value=self.response(200, payload)), self.assertRaises(release.ReleaseError):
                api.download(release.PREFIX + '/actions/artifacts/1/zip', self.work / str(index), 'a' * 64, 8)

    def test_api_redirects_and_uncertain_writes_are_not_retried(self):
        api = release.GitHub('unit-test-secret')
        with mock.patch.object(api, '_open', return_value=self.response(302)) as opened, self.assertRaises(release.ReleaseError):
            api.api(release.PREFIX + '/releases', 'POST', {})
        self.assertEqual(opened.call_count, 1)


class LiveTransportProbeTests(TemporaryTest):
    def setUp(self):
        super().setUp()
        import release_transport_probe as probe
        self.probe = probe
        self.archive = self.work / 'fixture.zip'
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('probe.txt', probe.PROBE)
        self.digest = release.sha256(self.archive)
        self.run = {'id': 123, 'run_attempt': 1, 'head_sha': SOURCE,
                    'repository': {'id': release.REPOSITORY_ID}, 'head_repository': {'id': release.REPOSITORY_ID}}
        self.artifact = {'id': 456, 'expired': False, 'name': 'release-transport-probe-1',
            'workflow_run': {'id': 123, 'head_sha': SOURCE, 'repository_id': release.REPOSITORY_ID,
                             'head_repository_id': release.REPOSITORY_ID},
            'size_in_bytes': self.archive.stat().st_size, 'digest': 'sha256:' + self.digest,
            'archive_download_url': release.API + release.PREFIX + '/actions/artifacts/456/zip'}
        self.api = mock.Mock()
        def get(path):
            return {release.PREFIX + '/actions/runs/123': self.run,
                    release.PREFIX + '/actions/artifacts/456': self.artifact}[path]
        self.api.api.side_effect = get
        self.api.download.side_effect = lambda path, destination, digest, size: shutil.copyfile(self.archive, destination)

    def verify(self):
        return self.probe.verify(self.api, 456, 123, 1, self.digest, self.work)

    def test_probe_reads_only_same_run_metadata_and_exact_known_bytes(self):
        with mock.patch.object(release, 'publish', side_effect=AssertionError('No publication')):
            result = self.verify()
        self.assertTrue(result['passed'])
        self.assertEqual(result['source_sha'], SOURCE)
        self.assertEqual(self.api.api.call_args_list, [mock.call(release.PREFIX + '/actions/runs/123'),
                         mock.call(release.PREFIX + '/actions/artifacts/456')])
        self.api.download.assert_called_once_with(release.PREFIX + '/actions/artifacts/456/zip',
                                                  self.work / 'probe.zip', self.digest, self.archive.stat().st_size)

    def test_probe_foreign_artifact_is_rejected_before_download(self):
        self.artifact['workflow_run']['id'] = 124
        with self.assertRaisesRegex(release.ReleaseError, 'identity mismatch'):
            self.verify()
        self.api.download.assert_not_called()

    def test_probe_changed_run_or_attempt_is_rejected(self):
        self.run['run_attempt'] = 2
        with self.assertRaisesRegex(release.ReleaseError, 'run identity'):
            self.verify()
        self.api.download.assert_not_called()

    def test_probe_wrong_digest_or_excessive_size_is_rejected(self):
        for key, value in (('digest', 'sha256:' + 'f' * 64), ('size_in_bytes', self.probe.MAX_PROBE + 1)):
            original = self.artifact[key]
            self.artifact[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(release.ReleaseError, 'hash/size/origin'):
                self.verify()
            self.artifact[key] = original
        self.api.download.assert_not_called()

    def test_probe_extra_or_changed_payload_is_rejected(self):
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('probe.txt', b'changed')
            archive.writestr('unexpected.txt', b'extra')
        self.digest = release.sha256(self.archive)
        self.artifact.update(digest='sha256:' + self.digest, size_in_bytes=self.archive.stat().st_size)
        with self.assertRaisesRegex(release.ReleaseError, 'exact expected text'):
            self.verify()

    def test_ci_live_probe_has_no_repository_write_permission(self):
        workflow = (ROOT / '.github/workflows/ci.yml').read_text()
        engine = workflow.split('  engine-web:', 1)[1].split('  qt-native:', 1)[0]
        self.assertIn('permissions:\n      contents: read\n      actions: read', engine)
        self.assertNotIn('contents: write', engine)
        self.assertIn('release_transport_probe.py --prepare', engine)
        self.assertIn('steps.transport-probe.outputs.artifact-digest', engine)
        self.assertIn('Verify live read-only publisher artifact transport', engine)
        self.assertEqual(engine.count("if: github.event_name != 'pull_request' || github.event.pull_request.head.repo.full_name == github.repository"), 3)


class PrerequisiteTimestampTests(unittest.TestCase):
    def value(self, stamp):
        return {'retrieved_at_utc': stamp, 'sha256': 'a' * 64, 'version': '14.51.36247.0'}

    def test_fractional_zero_padding_is_equivalent_without_mutation(self):
        original = self.value('2026-10-19T09:03:28.5633900Z')
        expected = self.value('2026-10-19T09:03:28.56339Z')
        self.assertEqual(release.canonical_prerequisite(original), expected)
        self.assertEqual(original['retrieved_at_utc'], '2026-10-19T09:03:28.5633900Z')

    def test_zero_fraction_equals_integral_second(self):
        self.assertEqual(release.canonical_prerequisite(self.value('2026-10-19T09:03:28.0000000Z')),
                         self.value('2026-10-19T09:03:28Z'))

    def test_submicrosecond_differences_are_not_rounded_away(self):
        first = release.canonical_prerequisite(self.value('2026-10-19T09:03:28.5633901Z'))
        for stamp in ('2026-10-19T09:03:28.5633900Z', '2026-10-19T09:03:28.5633902Z',
                      '2026-10-19T09:03:28.563390101Z', '2026-10-19T09:03:29.5633901Z'):
            with self.subTest(stamp=stamp):
                self.assertNotEqual(first, release.canonical_prerequisite(self.value(stamp)))

    def test_invalid_dates_offsets_missing_or_excessive_fraction_fail(self):
        for stamp in (None, True, 123, '', '2026-02-30T09:03:28Z', '2026-10-19T24:03:28Z',
                      '2026-10-19T09:03:60Z', '2026-10-19T09:03:28.Z',
                      '2026-10-19T09:03:28+00:00', '2026-10-19 09:03:28Z',
                      '2026-10-19T09:03:28z', '0000-10-19T09:03:28Z', '2026-13-19T09:03:28Z',
                      '2026-10-19T09:03:28.1234567890Z', '2026-10-19T09:03:28Z\n'):
            with self.subTest(stamp=stamp), self.assertRaises(release.ReleaseError):
                release.canonical_prerequisite(self.value(stamp))
        with self.assertRaises(release.ReleaseError):
            release.canonical_prerequisite({})

    def test_provenance_must_be_an_object(self):
        for value in (None, [], True, 1, '2026-10-19T09:03:28Z'):
            with self.subTest(value=value), self.assertRaises(release.ReleaseError):
                release.canonical_prerequisite(value)

    def test_other_fields_and_extra_fields_remain_exact(self):
        first = self.value('2026-10-19T09:03:28.5633900Z')
        for changed in (dict(first, sha256='b' * 64), dict(first, version='14.51.36248.0'),
                        dict(first, extra='unreviewed')):
            self.assertNotEqual(release.canonical_prerequisite(first), release.canonical_prerequisite(changed))


class AppLocalRuntimeTests(TemporaryTest):
    """Synthetic bytes exercise the verifier, never clear the real license gate."""
    def setUp(self):
        super().setUp()
        self.package = self.work / 'package'
        self.package.mkdir()
        self.pin = copy.deepcopy(release.vc_runtime.pin())
        self.metadata = copy.deepcopy(self.pin['package_metadata'])
        for name, identity in self.metadata['files'].items():
            path = self.package / 'bin' / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b'unit fixture, not executable: ' + name.encode('ascii'))
            identity.update(sha256=release.sha256(path), bytes=path.stat().st_size)
        self.pin['package_metadata'] = copy.deepcopy(self.metadata)
        patch = mock.patch.object(release.vc_runtime, 'pin', return_value=self.pin)
        patch.start()
        self.addCleanup(patch.stop)
        self.build = {'crt_mode': 'AppLocal', 'crt_minimum_version': release.installer.MINIMUM_RUNTIME,
                      'crt_provenance': copy.deepcopy(self.metadata)}
        self.record = {'crt_mode': 'AppLocal', 'crt_provenance': copy.deepcopy(self.metadata)}
        self.prerequisite = dict(self.metadata['source'], schema_version=1,
                                minimum_version=release.installer.MINIMUM_RUNTIME,
                                signature_status='Valid',
                                signer_subject='CN=Microsoft Corporation, O=Microsoft Corporation, C=US')
        self.metadata_path = self.package / 'bin/showpsisi-vc-runtime.json'
        write_json(self.metadata_path, self.metadata)
        self.signatures = runtime_signature_fixture(self.metadata)
        self.signatures_path = self.work / 'runtime-signatures.json'
        write_json(self.signatures_path, self.signatures)

    def verify(self):
        release.installer.verify_prerequisite(self.prerequisite)
        release.check_installer_runtime(self.package, self.build, self.record, self.prerequisite)
        release.check_applocal_signatures(self.package, self.signatures_path)

    def verify_signatures(self):
        release.check_applocal_signatures(self.package, self.signatures_path)

    def test_signature_record_order_and_thumbprint_case_are_not_identity(self):
        self.signatures.reverse()
        self.signatures[0]['signer_thumbprint'] = self.signatures[0]['signer_thumbprint'].lower()
        write_json(self.signatures_path, self.signatures)
        self.verify()

    def test_signature_report_must_be_an_exact_five_record_array(self):
        for value in (None, {}, True, self.signatures[0], [], self.signatures[:-1],
                      self.signatures + [dict(self.signatures[0])], self.signatures[:-1] + [None]):
            write_json(self.signatures_path, value)
            with self.subTest(value=value), self.assertRaisesRegex(release.ReleaseError, 'signature records'):
                self.verify_signatures()

    def test_signature_record_fields_and_types_are_exact(self):
        original = copy.deepcopy(self.signatures)
        for key in original[0]:
            for value in (None, True, 1, {}, []):
                records = copy.deepcopy(original)
                records[0][key] = value
                write_json(self.signatures_path, records)
                with self.subTest(key=key, value=value), self.assertRaisesRegex(release.ReleaseError, 'signature records'):
                    self.verify_signatures()
            records = copy.deepcopy(original)
            records[0].pop(key)
            write_json(self.signatures_path, records)
            with self.subTest(missing=key), self.assertRaisesRegex(release.ReleaseError, 'signature records'):
                self.verify_signatures()
        records = copy.deepcopy(original)
        records[0]['unreviewed'] = 'extra'
        write_json(self.signatures_path, records)
        with self.assertRaisesRegex(release.ReleaseError, 'signature records'):
            self.verify_signatures()

    def test_signature_names_cannot_be_duplicate_aliases_or_unpinned(self):
        for name in (self.signatures[1]['name'], self.signatures[0]['name'].upper(),
                     '../' + self.signatures[0]['name'], 'unreviewed.dll'):
            records = copy.deepcopy(self.signatures)
            records[0]['name'] = name
            write_json(self.signatures_path, records)
            with self.subTest(name=name), self.assertRaisesRegex(release.ReleaseError, 'five unique pinned DLLs'):
                self.verify_signatures()

    def test_signature_hash_must_match_the_pin_and_actual_packaged_dll(self):
        self.signatures[0]['sha256'] = 'f' * 64
        write_json(self.signatures_path, self.signatures)
        with self.assertRaisesRegex(release.ReleaseError, 'signature hash'):
            self.verify_signatures()
        write_json(self.signatures_path, runtime_signature_fixture(self.metadata))
        (self.package / 'bin' / self.signatures[0]['name']).write_bytes(b'changed packaged DLL')
        with self.assertRaisesRegex(release.ReleaseError, 'signature hash'):
            self.verify_signatures()

    def test_signature_status_and_organization_must_be_valid_microsoft(self):
        for status in ('UnknownError', 'NotSigned', 'HashMismatch', 'NotTrusted', 'valid', ''):
            records = copy.deepcopy(self.signatures)
            records[0]['signature_status'] = status
            write_json(self.signatures_path, records)
            with self.subTest(status=status), self.assertRaisesRegex(release.ReleaseError, 'valid Microsoft evidence'):
                self.verify_signatures()
        for subject in ('CN=Microsoft Corporation', 'CN=Microsoft Corporation, O=Other Corporation',
                        'O=Microsoft Corporation Attacker', 'CN=O=Microsoft Corporation, O=Other Corporation',
                        'O=Other Corporation, O=Microsoft Corporation',
                        'CN="Attacker, O=Microsoft Corporation, C=US", O=Other Corporation',
                        r'CN=Attacker\, O=Microsoft Corporation, C=US',
                        'CN=Microsoft Corporation,\nO=Microsoft Corporation', ''):
            records = copy.deepcopy(self.signatures)
            records[0]['signer_subject'] = subject
            write_json(self.signatures_path, records)
            with self.subTest(subject=subject), self.assertRaisesRegex(release.ReleaseError, 'valid Microsoft evidence'):
                self.verify_signatures()

    def test_signature_thumbprint_requires_exact_certificate_hash_shape(self):
        for thumbprint in ('', 'a' * 39, 'a' * 41, 'a' * 64, 'g' * 40,
                           ('a' * 40) + '\n', ' ' + ('a' * 40), ':'.join(['aa'] * 20)):
            records = copy.deepcopy(self.signatures)
            records[0]['signer_thumbprint'] = thumbprint
            write_json(self.signatures_path, records)
            with self.subTest(thumbprint=thumbprint), self.assertRaisesRegex(release.ReleaseError, 'valid Microsoft evidence'):
                self.verify_signatures()

    def test_signature_report_duplicate_json_keys_are_rejected(self):
        raw = json.dumps(self.signatures).replace('"signature_status": "Valid"',
            '"signature_status": "NotSigned", "signature_status": "Valid"', 1)
        self.signatures_path.write_text(raw)
        with self.assertRaisesRegex(release.ReleaseError, 'Duplicate JSON'):
            self.verify_signatures()

    def test_exact_applocal_runtime_preserves_original_source_proof_without_execution(self):
        with mock.patch.object(release.subprocess, 'run', side_effect=AssertionError('Artifacts must not execute')):
            self.verify()

    def test_applocal_cannot_use_historical_missing_mode_default(self):
        self.record.pop('crt_mode')
        with self.assertRaisesRegex(release.ReleaseError, 'provenance differs'):
            self.verify()

    def test_missing_or_changed_complete_installer_provenance_is_rejected(self):
        for value in (None, {}, dict(self.metadata, unexpected='unreviewed')):
            self.record['crt_provenance'] = value
            with self.subTest(value=value), self.assertRaisesRegex(release.ReleaseError, 'provenance differs'):
                self.verify()

    def test_changed_source_url_hash_size_or_version_is_rejected(self):
        original = copy.deepcopy(self.prerequisite)
        for key, value in (('url', 'https://download.microsoft.com/other/vc_redist.x64.exe'),
                           ('sha256', 'c' * 64), ('bytes', self.metadata['source']['bytes'] + 1),
                           ('version', '14.51.36248.0'), ('official_source', 'https://evil.example/redist.exe')):
            self.prerequisite = dict(original, **{key: value})
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.verify()

    def test_source_byte_count_and_authenticode_cannot_be_dropped(self):
        original = copy.deepcopy(self.prerequisite)
        for key in ('bytes', 'signature_status', 'signer_subject'):
            self.prerequisite = dict(original)
            self.prerequisite.pop(key)
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.verify()

    def test_source_byte_count_type_is_exact(self):
        self.prerequisite['bytes'] = float(self.prerequisite['bytes'])
        with self.assertRaisesRegex(release.ReleaseError, 'source differs'):
            self.verify()

    def test_matching_but_unpinned_provenance_is_rejected(self):
        self.metadata['files']['msvcp140_2.dll']['version'] = '14.51.36248.0'
        self.build['crt_provenance'] = copy.deepcopy(self.metadata)
        self.record['crt_provenance'] = copy.deepcopy(self.metadata)
        write_json(self.metadata_path, self.metadata)
        with self.assertRaisesRegex(RuntimeError, 'reviewed pin'):
            self.verify()

    def test_metadata_types_cannot_change_in_installer_record(self):
        for value in (True, 1.0):
            self.record['crt_provenance']['schema_version'] = value
            with self.subTest(value=value), self.assertRaisesRegex(release.ReleaseError, 'provenance differs'):
                self.verify()

    def test_changed_or_missing_fifth_dll_is_rejected(self):
        path = self.package / 'bin/msvcp140_2.dll'
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError, 'runtime bytes'):
            self.verify()
        path.unlink()
        with self.assertRaisesRegex(RuntimeError, 'runtime bytes'):
            self.verify()

    def test_duplicate_runtime_control_metadata_is_rejected(self):
        self.metadata_path.write_bytes(b'{"schema_version":1,"schema_version":1}')
        with self.assertRaisesRegex(release.ReleaseError, 'Duplicate JSON'):
            self.verify()

    def test_prerequisite_cannot_smuggle_applocal_provenance(self):
        self.build['crt_mode'] = 'Prerequisite'
        self.record['crt_mode'] = 'Prerequisite'
        with self.assertRaisesRegex(release.ReleaseError, 'mode/provenance mismatch'):
            self.verify()


class PayloadTests(TemporaryTest):
    def configure_package(self, fixture):
        import corresponding_source
        self.source = corresponding_source
        shutil.copytree(ROOT / 'scripts/portable-licenses/licenses', fixture.package / 'licenses', dirs_exist_ok=True)
        pins = copy.deepcopy(self.source.QT_ARCHIVES)
        for pin in pins:
            path = fixture.package / 'sources' / pin['filename']
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(b'unit fixture original Qt archive: ' + pin['module'].encode('ascii'))
            pin.update(sha256=release.sha256(path), bytes=path.stat().st_size)
        patch = mock.patch.object(self.source, 'QT_ARCHIVES', pins)
        patch.start()
        self.addCleanup(patch.stop)
        records = [dict(pin, url='https://download.qt.io/archive/qt/6.7/6.7.3/submodules/' + pin['filename'],
                        publisher_checksum_verified=True) for pin in pins]
        index_path = fixture.package / 'source-index.json'
        index = release.read_json(index_path)
        index.pop('corresponding_source', None)
        index['qt_source_archives'] = copy.deepcopy(records)
        write_json(index_path, index)
        attribution_path = fixture.package / 'licenses/qt/source-attributions.json'
        attribution = release.read_json(attribution_path)
        attribution['archives'] = copy.deepcopy(records)
        write_json(attribution_path, attribution)
        qtcore = fixture.package / 'bin/Qt6Core.dll'
        qtcore.write_bytes(b'unit fixture, not executable QtCore')
        config = {
            'mkspecs/qconfig.pri': 'QT_VERSION = 6.7.3\n',
            'mkspecs/qmodule.pri': 'QT.global_private.enabled_features = relocatable\n',
            'include/QtCore/qconfig.h': '#define QT_FEATURE_shared 1\n#define QT_FEATURE_static -1\n#define QT_VERSION_STR "6.7.3"\n'}
        build_path = fixture.package / 'build-information.json'
        build = release.read_json(build_path)
        build.update(qt_version='6.7.3', qt_source_archives=records,
                     qt_build_configuration={name: {'content': text, 'sha256': hashlib.sha256(text.encode()).hexdigest()}
                                             for name, text in config.items()},
                     qt_core_relocation={'installed_kit_sha256': release.sha256(qtcore),
                                         'deployed_sha256': release.sha256(qtcore)})
        write_json(build_path, build)

    def configure_validation(self, validation):
        pass

    def configure_preflight(self, preflight):
        pass

    def configure_smoke(self, smoke):
        pass

    def finalize_artifacts(self):
        pass

    def prepare_source_artifact(self):
        return None

    def bind_checksums(self):
        zipped = self.zip_dir / release.PORTABLE
        paths = [self.setup_dir / release.SETUP, zipped]
        directories = [self.setup_dir, self.zip_dir]
        source_dir = self.work / release.SOURCE_ARTIFACT
        if source_dir.is_dir():
            paths.append(source_dir / release.CORRESPONDING_SOURCE)
            directories.append(source_dir)
        sums = ''.join(f'{release.sha256(path)}  {path.name}\n' for path in paths)
        for directory in directories:
            (directory / 'SHA256SUMS').write_text(sums)
        for path in paths[1:]:
            path.with_suffix(path.suffix + '.sha256').write_text(f'{release.sha256(path)}  {path.name}\n')

    def setUp(self):
        super().setUp()
        import test_installer_package
        fixture = test_installer_package.InstallerPackageTests()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        fixture.runtime['retrieved_at_utc'] = '2026-10-19T09:03:28.5633900Z'
        write_json(fixture.prerequisite, fixture.runtime)
        package = fixture.package
        build_path = package / 'build-information.json'
        build = release.read_json(build_path)
        build['application_version'] = release.VERSION
        write_json(build_path, build)
        for path in package.rglob('*.json'):
            if path.name not in ('build-information.json', 'redistribution-review.json', 'manifest.json', 'source-index.json', 'SOURCE-PROVENANCE.json'):
                write_json(path, {})
        write_json(package / 'bin/showpsisi-portable.json', {'schema_version': 1, 'scope': 'qt-core', 'resource_root': '..'})
        opaque = package / 'licenses/qt/upstream-attribution.json'
        opaque.parent.mkdir(parents=True)
        opaque.write_bytes(b'{"upstream":"retained","upstream":"verbatim control \x01"}')
        self.configure_package(fixture)
        fixture.fixture.approve_fixture()
        validation = json.loads((fixture.evidence / 'portable-validation.json').read_text())
        validation.update(native_windows_desktop_verified=False)
        validation['runtime_requirement']['required_minimum'] = release.installer.MINIMUM_RUNTIME
        self.configure_validation(validation)
        write_json(fixture.evidence / 'portable-validation.json', validation)
        self.setup_dir, self.zip_dir, self.ie, self.pe = [self.work / name for name in release.ARTIFACTS]
        for path in (self.setup_dir, self.zip_dir, self.ie, self.pe):
            path.mkdir()
        setup = self.setup_dir / release.SETUP
        setup.write_bytes(b'MZ unit fixture, never executable')
        source_archive = self.prepare_source_artifact()
        record = release.installer.prepare(package, fixture.evidence, fixture.prerequisite, release.VERSION,
                                           fixture.root / 'generated', fixture.root / 'output', SOURCE,
                                           source_archive=source_archive)
        record.update(installer_sha256=release.sha256(setup), installer_bytes=setup.stat().st_size)
        write_json(self.setup_dir / 'installer-build.json', record)
        write_json(self.ie / 'artifacts/installer-candidate/installer-build.json', record)
        write_json(self.ie / '.deps/installer-prerequisite/vc-runtime.json', fixture.runtime)
        release.portable.archive(package, fixture.evidence, self.zip_dir / release.PORTABLE, source_archive=source_archive)
        self.bind_checksums()
        write_json(self.pe / 'portable-validation/portable-validation.json', validation)
        if source_archive is not None:
            shutil.copyfile(fixture.evidence / 'corresponding-source-validation.json',
                            self.pe / 'portable-validation/corresponding-source-validation.json')
        (self.pe / 'portable-stage').mkdir()
        for name in ('manifest.json', 'build-information.json'):
            shutil.copyfile(package / name, self.pe / 'portable-stage' / name)
        preflight = {'passed': True,
                   'launcher_sha256': release.sha256(package / 'Launch Qt.cmd'), 'cases': [
                       {'name': name, 'exit_code': code} for name, code in
                       [('host-runtime-ready', 0), ('missing-runtime-blocked', 1), ('old-runtime-blocked', 1)]]}
        self.configure_preflight(preflight)
        write_json(self.pe / 'portable-launcher-probe/preflight.json', preflight)
        self.smoke = {'passed': True, 'installer_sha256': release.sha256(setup),
                      'package_manifest_sha256': release.sha256(package / 'manifest.json'),
                      'clean_machine_verified': False, 'native_dialogs_verified': False, 'runtime_bootstrap_exercised': False,
                      'production_core_mutex': {'held_while_running': True, 'released_after_exit': True},
                      'settings_preserved': True, 'shortcuts_verified': True, 'all_manifested_payload_removed': True,
                      'steps': [{'name': name, 'exit_code': code} for name, code in [
                          ('reject-uninstalled-update', 7), ('install-previous', 0), ('reject-live-app-update', 1),
                          ('reject-live-app-uninstall', 1), ('upgrade', 0), ('reinstall', 0), ('reject-downgrade', 7), ('uninstall', 0)]]}
        self.configure_smoke(self.smoke)
        self.smoke_path = self.ie / 'artifacts/installer-validation/installer-smoke.json'
        write_json(self.smoke_path, self.smoke)
        self.finalize_artifacts()

    def validate(self):
        return release.validate_payload(self.work, REQUEST)

    def test_full_same_source_payload_is_accepted_without_execution(self):
        with mock.patch.object(release.subprocess, 'run', side_effect=AssertionError('Artifacts must not execute')):
            files, manifest, runtime = self.validate()
        expected = {release.SETUP, release.PORTABLE, 'SHA256SUMS'}
        if (self.work / release.SOURCE_ARTIFACT).exists():
            expected.add(release.CORRESPONDING_SOURCE)
        self.assertEqual(set(files), expected)
        self.assertEqual(manifest, self.smoke['package_manifest_sha256'])
        self.assertEqual(runtime, self.fixture.runtime['sha256'])

    def test_reviewed_upstream_json_is_opaque_but_hash_bound(self):
        with zipfile.ZipFile(self.zip_dir / release.PORTABLE) as archive:
            data = archive.read('ShowPsiSi-windows-x64/licenses/qt/upstream-attribution.json')
        with self.assertRaises((release.ReleaseError, json.JSONDecodeError)):
            release.decode_json(data)
        self.validate()

    def test_equivalent_runtime_timestamp_spelling_is_accepted(self):
        path = self.ie / '.deps/installer-prerequisite/vc-runtime.json'
        value = release.read_json(path)
        value['retrieved_at_utc'] = '2026-10-19T09:03:28.56339Z'
        write_json(path, value)
        self.validate()

    def test_different_runtime_instant_is_rejected(self):
        path = self.ie / '.deps/installer-prerequisite/vc-runtime.json'
        value = release.read_json(path)
        value['retrieved_at_utc'] = '2026-10-19T09:03:28.5633901Z'
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseError, 'provenance differs'):
            self.validate()

    def test_changed_runtime_provenance_field_is_rejected(self):
        path = self.ie / '.deps/installer-prerequisite/vc-runtime.json'
        value = release.read_json(path)
        value['sha256'] = 'c' * 64
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseError, 'provenance differs'):
            self.validate()

    def test_setup_tamper_rejected(self):
        with (self.setup_dir / release.SETUP).open('ab') as output:
            output.write(b'changed')
        with self.assertRaisesRegex(release.ReleaseError, 'checksums'):
            self.validate()

    def test_missing_checksum_entry_and_common_mismatch_rejected(self):
        (self.setup_dir / 'SHA256SUMS').write_text('a' * 64 + '  ' + release.SETUP + '\n')
        with self.assertRaises(release.ReleaseError):
            self.validate()

    def test_test_only_installer_is_not_publishable(self):
        (self.setup_dir / 'TEST-ONLY-previous-version.exe').write_bytes(b'MZ')
        with self.assertRaisesRegex(release.ReleaseError, 'Unexpected files'):
            self.validate()

    def test_changed_inner_payload_cannot_pass_with_updated_outer_checksums(self):
        zipped = self.zip_dir / release.PORTABLE
        with zipfile.ZipFile(zipped) as archive:
            entries = [(item.filename, archive.read(item)) for item in archive.infolist()]
        with zipfile.ZipFile(zipped, 'w') as archive:
            for name, data in entries:
                if name.endswith('/bin/showpsisi-core.exe'):
                    data += b'changed bytes'
                archive.writestr(name, data)
        self.bind_checksums()
        with self.assertRaisesRegex(RuntimeError, 'changed after manifest|Binary package manifest/build mismatch'):
            self.validate()

    def test_installer_smoke_false_or_hash_mismatch_rejected(self):
        self.smoke['installer_sha256'] = 'f' * 64
        write_json(self.smoke_path, self.smoke)
        with self.assertRaisesRegex(release.ReleaseError, 'acceptance'):
            self.validate()

    def test_clean_machine_claim_cannot_silently_change_disclosure(self):
        self.smoke['clean_machine_verified'] = True
        write_json(self.smoke_path, self.smoke)
        with self.assertRaisesRegex(release.ReleaseError, 'boundary'):
            self.validate()

    def test_missing_installer_acceptance_step_rejected(self):
        self.smoke['steps'].pop()
        write_json(self.smoke_path, self.smoke)
        with self.assertRaisesRegex(release.ReleaseError, 'steps incomplete'):
            self.validate()

    def test_blocked_distribution_record_rejected(self):
        write_json(self.pe / 'portable-validation/distribution-gate.json', {'archive_created': False})
        with self.assertRaisesRegex(release.ReleaseError, 'blocked distribution'):
            self.validate()

    def test_preflight_failure_rejected(self):
        path = self.pe / 'portable-launcher-probe/preflight.json'
        value = json.loads(path.read_text())
        next(case for case in value['cases'] if case['name'] == 'missing-runtime-blocked')['exit_code'] = 0
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseError, 'launcher'):
            self.validate()

    def test_wrong_source_rejected_even_when_version_matches(self):
        with self.assertRaisesRegex(release.ReleaseError, 'source mismatch'):
            release.validate_payload(self.work, dict(REQUEST, source_sha=TRIGGER))

    def test_checksum_duplicate_or_unrequested_file_rejected(self):
        for raw in ((('a' * 64 + '  a.exe\n') * 2).encode(), ('a' * 64 + '  extra.exe\n').encode()):
            with self.assertRaises(release.ReleaseError):
                release.exact_checksums(raw, {'a.exe': 'a' * 64, 'b.zip': 'b' * 64})


class AppLocalPayloadTests(PayloadTests):
    """Run the complete historical publisher attacks through AppLocal too.

    Only fake byte identities and PE readers are substituted. All inventory,
    provenance, capture, licensing and publisher acceptance gates run normally.
    These synthetic reports are unit fixtures, never Windows execution evidence.
    """
    def configure_package(self, fixture):
        super().configure_package(fixture)
        import windows_runtime_modules
        self.modules = windows_runtime_modules
        self.metadata = copy.deepcopy(release.vc_runtime.pin()['package_metadata'])
        for name, identity in self.metadata['files'].items():
            path = fixture.package / 'bin' / name
            path.write_bytes(b'unit fixture, not executable: ' + name.encode('ascii'))
            identity.update(sha256=release.sha256(path), bytes=path.stat().st_size)
        pin = copy.deepcopy(release.vc_runtime.pin())
        pin['package_metadata'] = copy.deepcopy(self.metadata)
        for patch in (mock.patch.object(release.vc_runtime, 'pin', return_value=pin),
                      mock.patch.object(self.modules, 'pe_identity', return_value={
                          'machine': 'AMD64', 'version': self.metadata['version']}),
                      mock.patch.object(self.modules, 'required_crt_modules', return_value=sorted(self.metadata['files']))):
            patch.start()
            self.addCleanup(patch.stop)
        write_json(fixture.package / 'bin/showpsisi-vc-runtime.json', self.metadata)
        build = release.read_json(fixture.package / 'build-information.json')
        build.update(crt_mode='AppLocal', crt_provenance=copy.deepcopy(self.metadata))
        write_json(fixture.package / 'build-information.json', build)
        fixture.runtime.update(self.metadata['source'])
        write_json(fixture.prerequisite, fixture.runtime)
        write_json(fixture.package / release.vc_runtime.REVIEW_NAME, {
            'schema_version': 1, 'review_complete': True,
            'license_basis': {'applicable_terms_url': 'https://example.invalid/unit-fixture-terms',
                              'distribution_basis': 'Unit fixture only; never a real redistribution approval'},
            'source_sha256': self.metadata['source']['sha256'], 'runtime_version': self.metadata['version'],
            'files': copy.deepcopy(self.metadata['files'])})

    def capture(self, executable, root=r'C:\Unit fixture\Relocated app 空间'):
        paths = [root + '\\bin\\' + name for name in [executable, *sorted(self.metadata['files'])]]
        identities = {name: dict(identity, path=root + '\\bin\\' + name)
                      for name, identity in self.metadata['files'].items()}
        path_identities = {}
        for path in paths:
            local = self.fixture.package / 'bin' / path.rsplit('\\', 1)[1]
            path_identities[path] = {'raw_path': path, 'resolved_path': path,
                                     'file_id': {'device': 7, 'inode': local.stat().st_ino},
                                     'bytes': local.stat().st_size, 'sha256': release.sha256(local)}
        return {'schema_version': 2, 'passed': True, 'pid': 123, 'platform': 'Windows',
                'package_root': root, 'executable': paths[0], 'executable_name': executable,
                'executable_sha256': release.sha256(self.fixture.package / 'bin' / executable),
                'sampled_at_utc': '2026-10-19T09:00:00+00:00', 'process_created_unix': 100,
                'command_line': [paths[0]], 'path_identities': path_identities,
                'module_paths': paths, 'raw_modules': [{'path': path} for path in paths],
                'runtime': {'passed': True, 'mode': 'AppLocal',
                            'required_modules': sorted(self.metadata['files']), 'modules': identities}}

    def configure_validation(self, validation):
        validation.update(crt_mode='AppLocal', runtime_requirement=self.modules.inspect_runtime(self.fixture.package))
        validation['core'] = {'runtime_modules': self.capture('showpsisi-core.exe')}
        validation['qt_offscreen'] = {'runtime_modules': self.capture('showpsisi-qt.exe')}
        for stage in ('launcher_startup', 'direct_exe_startup'):
            validation[stage] = {'process_runtime': {name: self.capture(name)
                                for name in ('showpsisi-core.exe', 'showpsisi-qt.exe')}}

    def configure_preflight(self, preflight):
        preflight.update(schema_version=1, mode='AppLocal', clean_machine_verified=False,
                         package_manifest_sha256=release.sha256(self.fixture.package / 'manifest.json'))
        preflight['cases'] = [{'name': name, 'exit_code': code, 'fixture_root_binding': fixture,
                               'stdout': '', 'stdout_hex': '', 'stderr': diagnostic,
                               'stderr_hex': diagnostic.encode().hex()}
                              for name, (code, diagnostic, fixture) in release.portable_launcher_checks.REQUIRED_CASES.items()]

    def configure_smoke(self, smoke):
        root = r'C:\Unit fixture\Installed app 空间'
        smoke.update(crt_mode='AppLocal', installed_core={'runtime_modules': self.capture('showpsisi-core.exe', root)},
                     installed_qt_startup={'process_runtime': {name: self.capture(name, root)
                        for name in ('showpsisi-core.exe', 'showpsisi-qt.exe')}})

    def finalize_artifacts(self):
        super().finalize_artifacts()
        self.signatures_path = self.ie / '.deps/app-local-runtime-work/runtime-signatures.json'
        write_json(self.signatures_path, runtime_signature_fixture(self.metadata))

    def test_native_dll_signature_evidence_cannot_be_omitted(self):
        self.signatures_path.unlink()
        with self.assertRaisesRegex(release.ReleaseError, 'signature evidence is missing'):
            self.validate()

    def test_native_dll_signature_evidence_cannot_reference_other_bytes(self):
        records = release.read_json(self.signatures_path)
        records[0]['sha256'] = 'f' * 64
        write_json(self.signatures_path, records)
        with self.assertRaisesRegex(release.ReleaseError, 'signature hash'):
            self.validate()

    def test_native_dll_signature_evidence_cannot_duplicate_a_record(self):
        records = release.read_json(self.signatures_path)
        records[-1] = dict(records[0])
        write_json(self.signatures_path, records)
        with self.assertRaisesRegex(release.ReleaseError, 'five unique pinned DLLs'):
            self.validate()

    def test_native_dll_signature_evidence_cannot_add_a_sixth_dll(self):
        records = release.read_json(self.signatures_path)
        records.append(dict(records[0], name='unreviewed.dll'))
        write_json(self.signatures_path, records)
        with self.assertRaisesRegex(release.ReleaseError, 'signature records'):
            self.validate()

    def test_native_dll_signature_evidence_requires_valid_microsoft_signatures(self):
        records = release.read_json(self.signatures_path)
        records[-1]['signature_status'] = 'NotSigned'
        write_json(self.signatures_path, records)
        with self.assertRaisesRegex(release.ReleaseError, 'valid Microsoft evidence'):
            self.validate()

    def test_valid_dll_signatures_do_not_replace_original_exe_signature_proof(self):
        record = release.read_json(self.setup_dir / 'installer-build.json')
        record['prerequisite']['signature_status'] = 'NotSigned'
        for path in (self.setup_dir / 'installer-build.json', self.ie / 'artifacts/installer-candidate/installer-build.json'):
            write_json(path, record)
        write_json(self.ie / '.deps/installer-prerequisite/vc-runtime.json', record['prerequisite'])
        with self.assertRaisesRegex(RuntimeError, 'signature'):
            self.validate()

    def change_validation(self, change):
        path = self.pe / 'portable-validation/portable-validation.json'
        value = release.read_json(path)
        change(value)
        write_json(path, value)

    def rebind_unit_payload(self):
        """Refresh all outer identities to test the inner gate, never real assets."""
        package = self.fixture.package
        self.fixture.fixture.approve_fixture()
        manifest_hash = release.sha256(package / 'manifest.json')
        validation = release.read_json(self.pe / 'portable-validation/portable-validation.json')
        validation['package_manifest_sha256'] = manifest_hash
        write_json(self.pe / 'portable-validation/portable-validation.json', validation)
        for name in ('manifest.json', 'build-information.json'):
            shutil.copyfile(package / name, self.pe / 'portable-stage' / name)
        record = release.read_json(self.setup_dir / 'installer-build.json')
        record['package_manifest_sha256'] = manifest_hash
        for path in (self.setup_dir / 'installer-build.json', self.ie / 'artifacts/installer-candidate/installer-build.json'):
            write_json(path, record)
        self.smoke['package_manifest_sha256'] = manifest_hash
        write_json(self.smoke_path, self.smoke)
        preflight_path = self.pe / 'portable-launcher-probe/preflight.json'
        preflight = release.read_json(preflight_path)
        preflight['package_manifest_sha256'] = manifest_hash
        write_json(preflight_path, preflight)
        zipped = self.zip_dir / release.PORTABLE
        with zipfile.ZipFile(zipped, 'w') as archive:
            for path in sorted(package.rglob('*')):
                if path.is_file():
                    archive.write(path, 'ShowPsiSi-windows-x64/' + path.relative_to(package).as_posix())
        self.bind_checksums()

    def test_incomplete_microsoft_review_cannot_pass_with_refreshed_inventory(self):
        path = self.fixture.package / release.vc_runtime.REVIEW_NAME
        value = release.read_json(path)
        value['review_complete'] = False
        write_json(path, value)
        self.rebind_unit_payload()
        with self.assertRaisesRegex(RuntimeError, 'redistribution.*review is incomplete'):
            self.validate()

    def test_missing_microsoft_license_basis_cannot_pass_with_refreshed_inventory(self):
        path = self.fixture.package / release.vc_runtime.REVIEW_NAME
        value = release.read_json(path)
        value['license_basis'] = None
        write_json(path, value)
        self.rebind_unit_payload()
        with self.assertRaisesRegex(RuntimeError, 'redistribution.*review is incomplete'):
            self.validate()

    def test_installer_cannot_omit_applocal_provenance(self):
        record = release.read_json(self.setup_dir / 'installer-build.json')
        record.pop('crt_provenance')
        for path in (self.setup_dir / 'installer-build.json', self.ie / 'artifacts/installer-candidate/installer-build.json'):
            write_json(path, record)
        with self.assertRaisesRegex(release.ReleaseError, 'provenance differs from the package'):
            self.validate()

    def test_system_runtime_fallback_is_rejected_even_with_matching_hashes(self):
        def change(value):
            report = value['launcher_startup']['process_runtime']['showpsisi-qt.exe']
            old = report['runtime']['modules']['msvcp140.dll']['path']
            wrong = r'C:\Windows\System32\msvcp140.dll'
            report['module_paths'] = [wrong if path == old else path for path in report['module_paths']]
            report['raw_modules'] = [{'path': path} for path in report['module_paths']]
            report['runtime']['modules']['msvcp140.dll']['path'] = wrong
            report['path_identities'][wrong] = dict(report['path_identities'].pop(old), raw_path=wrong, resolved_path=wrong)
        self.change_validation(change)
        with self.assertRaisesRegex(RuntimeError, 'outside package bin'):
            self.validate()

    def test_missing_direct_startup_core_capture_is_rejected(self):
        self.change_validation(lambda value: value['direct_exe_startup']['process_runtime'].pop('showpsisi-core.exe'))
        with self.assertRaisesRegex(RuntimeError, 'evidence is incomplete'):
            self.validate()

    def test_changed_observed_runtime_hash_is_rejected(self):
        self.change_validation(lambda value: value['core']['runtime_modules']['runtime']['modules']['msvcp140_2.dll'].update(sha256='c' * 64))
        with self.assertRaisesRegex(RuntimeError, 'hash-bound package'):
            self.validate()

    def test_missing_raw_capture_is_rejected(self):
        self.change_validation(lambda value: value['qt_offscreen']['runtime_modules'].pop('raw_modules'))
        with self.assertRaisesRegex(RuntimeError, 'raw memory-map evidence'):
            self.validate()

    def test_installed_runtime_capture_is_required_independently(self):
        self.smoke['installed_qt_startup']['process_runtime'].pop('showpsisi-core.exe')
        write_json(self.smoke_path, self.smoke)
        with self.assertRaisesRegex(RuntimeError, 'Installed app-local process evidence'):
            self.validate()

    def test_missing_corrupted_runtime_preflight_is_rejected(self):
        path = self.pe / 'portable-launcher-probe/preflight.json'
        value = release.read_json(path)
        value['cases'] = [case for case in value['cases'] if case['name'] != 'corrupted-runtime-blocked']
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseError, 'launcher runtime acceptance'):
            self.validate()

    def test_preflight_is_bound_to_exact_package_manifest(self):
        path = self.pe / 'portable-launcher-probe/preflight.json'
        value = release.read_json(path)
        value['package_manifest_sha256'] = 'f' * 64
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseError, 'preflight identity'):
            self.validate()

    def test_preflight_raw_diagnostic_cannot_be_dropped(self):
        path = self.pe / 'portable-launcher-probe/preflight.json'
        value = release.read_json(path)
        next(case for case in value['cases'] if case['name'] == 'old-runtime-blocked')['stderr_hex'] = ''
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseError, 'subprocess evidence disagrees'):
            self.validate()

    def test_boolean_exit_status_is_not_a_success_code(self):
        path = self.pe / 'portable-launcher-probe/preflight.json'
        value = release.read_json(path)
        value['cases'][0]['exit_code'] = False
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseError, 'launcher runtime acceptance'):
            self.validate()


class SidecarPayloadTests(AppLocalPayloadTests):
    def configure_package(self, fixture):
        super().configure_package(fixture)
        self.original_sources = fixture.root / 'original-qt-sources'
        shutil.move(fixture.package / 'sources', self.original_sources)
        index_path = fixture.package / 'source-index.json'
        index = release.read_json(index_path)
        index['corresponding_source'] = dict(self.source.POLICY)
        write_json(index_path, index)
        self.source.stamp(fixture.package)
        def approve_fixture():
            value = {'build': release.read_json(fixture.package / 'build-information.json'),
                     'files': release.portable.inventory(fixture.package)}
            write_json(fixture.package / 'redistribution-review.json', {
                'schema_version': 1, 'review_complete': True, 'reviewed_files': release.portable.review_inventory(value)})
            release.portable.manifest(fixture.package)
            fixture.fixture.validation()
        fixture.fixture.approve_fixture = approve_fixture

    def prepare_source_artifact(self):
        source_dir = self.work / release.SOURCE_ARTIFACT
        source_dir.mkdir(exist_ok=True)
        self.source_zip = source_dir / release.CORRESPONDING_SOURCE
        self.source.build_archive(self.fixture.package, self.original_sources, self.source_zip)
        return self.source_zip

    def rebind_unit_payload(self):
        super().rebind_unit_payload()
        self.source_zip.unlink()
        self.source_zip.with_suffix('.zip.sha256').unlink()
        self.prepare_source_artifact()
        evidence = release.portable.verify_corresponding_source(self.fixture.package, self.source_zip)
        record = release.read_json(self.setup_dir / 'installer-build.json')
        record['corresponding_source'] = evidence
        for path in (self.setup_dir / 'installer-build.json', self.ie / 'artifacts/installer-candidate/installer-build.json'):
            write_json(path, record)
        write_json(self.pe / 'portable-validation/corresponding-source-validation.json', evidence)
        self.bind_checksums()

    def test_declared_sidecar_is_required(self):
        shutil.rmtree(self.work / release.SOURCE_ARTIFACT)
        self.bind_checksums()
        with self.assertRaisesRegex(release.ReleaseError, 'corresponding-source artifact is missing'):
            self.validate()

    def test_removed_declaration_cannot_release_stripped_sources_as_legacy(self):
        for name in ('build-information.json', 'source-index.json'):
            path = self.fixture.package / name
            value = release.read_json(path)
            value.pop('corresponding_source')
            write_json(path, value)
        shutil.rmtree(self.work / release.SOURCE_ARTIFACT)
        # Rebuild every binary identity as an attacker could, but do not restore
        # the required originals or permit the absent source ZIP to reappear.
        AppLocalPayloadTests.rebind_unit_payload(self)
        with self.assertRaisesRegex(RuntimeError, 'Invalid source/package directory'):
            self.validate()

    def test_third_checksum_entry_is_required(self):
        hashes = ''.join(f'{release.sha256(path)}  {path.name}\n'
                         for path in (self.setup_dir / release.SETUP, self.zip_dir / release.PORTABLE))
        for directory in (self.setup_dir, self.zip_dir, self.work / release.SOURCE_ARTIFACT):
            (directory / 'SHA256SUMS').write_text(hashes)
        with self.assertRaisesRegex(release.ReleaseError, 'checksum'):
            self.validate()

    def test_installer_must_bind_the_exact_source_asset(self):
        record = release.read_json(self.setup_dir / 'installer-build.json')
        record['corresponding_source']['sha256'] = 'f' * 64
        for path in (self.setup_dir / 'installer-build.json', self.ie / 'artifacts/installer-candidate/installer-build.json'):
            write_json(path, record)
        with self.assertRaisesRegex(release.ReleaseError, 'corresponding-source evidence differs'):
            self.validate()

    def test_source_must_be_bound_to_portable_validation(self):
        path = self.pe / 'portable-validation/corresponding-source-validation.json'
        value = release.read_json(path)
        value['source_commit'] = TRIGGER
        write_json(path, value)
        with self.assertRaisesRegex(release.ReleaseError, 'corresponding-source evidence differs'):
            self.validate()

    def test_changed_original_archive_fails_even_after_all_manifest_and_outer_hash_updates(self):
        with zipfile.ZipFile(self.source_zip) as archive:
            entries = {item.filename.removeprefix(self.source.ZIP_ROOT): archive.read(item) for item in archive.infolist()}
        entries['sources/' + self.source.QT_ARCHIVES[0]['filename']] += b'unreviewed changes'
        files = {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                 for name, data in entries.items() if name != self.source.MANIFEST}
        build = self.source.decode_json(entries['build-information.json'])
        entries[self.source.MANIFEST] = json.dumps(self.source._source_manifest(build, files)).encode()
        with zipfile.ZipFile(self.source_zip, 'w') as archive:
            for name, data in entries.items():
                archive.writestr(self.source.ZIP_ROOT + name, data)
        self.bind_checksums()
        with self.assertRaisesRegex(RuntimeError, 'source/notice material differs|source archive bytes/hash mismatch'):
            self.validate()


class ArtifactIdentityTests(TemporaryTest):
    def setUp(self):
        super().setUp()
        self.archive = self.work / 'source.zip'
        with zipfile.ZipFile(self.archive, 'w') as archive:
            archive.writestr('evidence.json', '{}')
        self.items = [{'id': index + 1, 'name': name, 'size_in_bytes': self.archive.stat().st_size,
                       'digest': 'sha256:' + release.sha256(self.archive), 'expired': False,
                       'archive_download_url': release.API + release.PREFIX + f'/actions/artifacts/{index + 1}/zip',
                       'workflow_run': {'id': REQUEST['ci_run_id'], 'head_sha': SOURCE, 'head_branch': 'main',
                                        'repository_id': release.REPOSITORY_ID, 'head_repository_id': release.REPOSITORY_ID}}
                      for index, name in enumerate(release.ARTIFACTS)]
        self.api = mock.Mock()
        self.api.api.side_effect = lambda path: {'total_count': len(self.items), 'artifacts': self.items}
        self.api.download.side_effect = lambda path, destination, digest, size: shutil.copyfile(self.archive, destination)

    def test_exact_run_artifacts_use_constructed_api_routes(self):
        selected = release.fetch_artifacts(self.api, REQUEST, self.work)
        self.assertEqual(len(selected), 4)
        self.assertEqual(self.api.download.call_count, 4)
        self.assertTrue(all(call.args[0].startswith(release.PREFIX + '/actions/artifacts/') for call in self.api.download.call_args_list))

    def add_source_artifact(self):
        source = copy.deepcopy(self.items[0])
        source.update(id=999, name=release.SOURCE_ARTIFACT,
                      archive_download_url=release.API + release.PREFIX + '/actions/artifacts/999/zip')
        self.items.append(source)
        return source

    def test_fifth_source_artifact_has_same_exact_identity_and_download_verification(self):
        self.add_source_artifact()
        selected = release.fetch_artifacts(self.api, REQUEST, self.work)
        self.assertEqual(len(selected), 5)
        self.assertEqual(selected[-1]['name'], release.SOURCE_ARTIFACT)
        self.assertEqual(self.api.download.call_count, 5)

    def test_foreign_source_sidecar_run_is_rejected(self):
        source = self.add_source_artifact()
        source['workflow_run']['head_sha'] = TRIGGER
        with self.assertRaisesRegex(release.ReleaseError, 'wrong source/run'):
            release.fetch_artifacts(self.api, REQUEST, self.work)

    def test_duplicate_source_sidecars_are_rejected(self):
        self.items.append(copy.deepcopy(self.add_source_artifact()))
        with self.assertRaisesRegex(release.ReleaseError, 'missing or duplicated'):
            release.fetch_artifacts(self.api, REQUEST, self.work)

    def test_foreign_run_source_or_repository_rejected_before_download(self):
        original = copy.deepcopy(self.items[0]['workflow_run'])
        for key, value in [('id', 999), ('head_sha', TRIGGER), ('head_branch', 'feature'),
                           ('repository_id', 1), ('head_repository_id', 2)]:
            self.items[0]['workflow_run'] = dict(original, **{key: value})
            with self.subTest(key=key), self.assertRaises(release.ReleaseError):
                release.fetch_artifacts(self.api, REQUEST, self.work)
        self.api.download.assert_not_called()

    def test_missing_digest_expiration_and_wrong_download_origin_rejected(self):
        original = copy.deepcopy(self.items[0])
        for key, value in [('digest', None), ('expired', True), ('archive_download_url', 'https://evil.example/file')]:
            self.items[0] = dict(original, **{key: value})
            with self.subTest(key=key), self.assertRaises(release.ReleaseError):
                release.fetch_artifacts(self.api, REQUEST, self.work)
        self.api.download.assert_not_called()

    def test_duplicate_artifacts_from_reruns_remain_ambiguous(self):
        self.items.append(copy.deepcopy(self.items[0]))
        with self.assertRaisesRegex(release.ReleaseError, 'duplicated'):
            release.fetch_artifacts(self.api, REQUEST, self.work)
        self.api.download.assert_not_called()

    def test_incomplete_listing_cannot_hide_duplicate_artifacts(self):
        self.api.api.side_effect = lambda path: {'total_count': 1000, 'artifacts': self.items}
        with self.assertRaisesRegex(release.ReleaseError, 'listing'):
            release.fetch_artifacts(self.api, REQUEST, self.work)


class ProjectVersionTests(TemporaryTest):
    def test_version_follows_only_canonical_reviewed_cmake(self):
        path = self.work / 'CMakeLists.txt'
        path.write_text('project(ShowPsiSi VERSION 1.2.3 LANGUAGES CXX)\n')
        self.assertEqual(release.project_version(self.work), '1.2.3')
        for text in ('project(ShowPsiSi VERSION 01.2.3 LANGUAGES CXX)',
                     'project(ShowPsiSi VERSION 1.2.3-beta LANGUAGES CXX)', '',
                     'project(ShowPsiSi VERSION 1.2.3 LANGUAGES CXX)\n' * 2):
            path.write_text(text)
            with self.assertRaises(RuntimeError):
                release.project_version(self.work)


class FakePublisherAPI:
    def __init__(self):
        self.tag = None
        self.release = None
        self.assets = []
        self.bytes = {}
        self.writes = []

    def api(self, path, method='GET', value=None, missing=False):
        if method != 'GET':
            self.writes.append((method, path, value))
        if '/git/ref/tags/' in path:
            return None if self.tag is None else {'ref': 'refs/tags/' + release.TAG, 'object': {'type': 'commit', 'sha': self.tag}}
        if path.endswith('/git/refs'):
            self.tag = value['sha']
            return {}
        if '/releases?' in path:
            return [] if self.release is None else [copy.deepcopy(self.release)]
        if '/assets?' in path:
            return copy.deepcopy(self.assets)
        if method == 'POST' and path.endswith('/releases'):
            self.release = dict(value, id=1)
            return copy.deepcopy(self.release)
        if method == 'PATCH':
            self.release.update(value)
        return copy.deepcopy(self.release)

    def upload(self, release_id, path):
        asset_id = len(self.assets) + 10
        self.bytes[asset_id] = path.read_bytes()
        self.assets.append({'id': asset_id, 'name': path.name, 'state': 'uploaded',
                            'size': path.stat().st_size, 'digest': 'sha256:' + release.sha256(path)})
        self.writes.append(('UPLOAD', path.name, None))

    def download(self, path, destination, expected_hash, expected_size):
        data = self.bytes[int(path.rsplit('/', 1)[-1])]
        release.require(len(data) == expected_size and hashlib.sha256(data).hexdigest() == expected_hash, 'Readback failed')
        destination.write_bytes(data)


class PublicationTests(TemporaryTest):
    def setUp(self):
        super().setUp()
        self.api = FakePublisherAPI()
        self.files = {}
        for name in (release.SETUP, release.PORTABLE, 'SHA256SUMS', 'release-provenance.json'):
            path = self.work / name
            path.write_bytes(name.encode())
            self.files[name] = path
        self.body = 'Reviewed release notes'
        self.ci = mock.patch.object(release, 'validate_ci')
        self.ci.start()
        self.addCleanup(self.ci.stop)

    def publish(self):
        return release.publish(self.api, REQUEST, self.files, self.body, self.work)

    def test_new_release_remains_draft_until_all_bytes_verified(self):
        result = self.publish()
        self.assertFalse(result['draft'])
        self.assertEqual(self.api.tag, SOURCE)
        self.assertEqual(len(self.api.assets), len(self.files))
        methods = [w[0] for w in self.api.writes]
        self.assertEqual(methods, ['POST', 'POST'] + ['UPLOAD'] * len(self.files) + ['PATCH'])

    def test_successful_rerun_has_no_mutations(self):
        self.publish()
        self.api.writes.clear()
        self.publish()
        self.assertEqual(self.api.writes, [])

    def test_partial_matching_draft_is_resumed_without_replacing_assets(self):
        original = self.api.upload
        def interrupted(release_id, path):
            original(release_id, path)
            if len(self.api.assets) == 1:
                raise release.ReleaseError('Uncertain upload response')
        with mock.patch.object(self.api, 'upload', side_effect=interrupted), self.assertRaises(release.ReleaseError):
            self.publish()
        self.assertTrue(self.api.release['draft'])
        retained = self.api.assets[0]['id']
        self.publish()
        self.assertEqual(self.api.assets[0]['id'], retained)
        self.assertEqual(len(self.api.assets), len(self.files))

    def test_mismatched_existing_tag_never_mutates(self):
        self.api.tag = TRIGGER
        with self.assertRaisesRegex(release.ReleaseError, 'different source'):
            self.publish()
        self.assertEqual(self.api.writes, [])

    def test_mismatched_existing_release_never_mutates(self):
        self.api.release = {'id': 1, 'tag_name': release.TAG, 'target_commitish': SOURCE,
                            'name': 'unreviewed release', 'body': self.body, 'draft': True, 'prerelease': False}
        with self.assertRaisesRegex(release.ReleaseError, 'metadata differs'):
            self.publish()
        self.assertEqual(self.api.writes, [])

    def test_unknown_assets_never_deleted_or_overwritten(self):
        self.publish()
        self.api.release['draft'] = True
        self.api.assets[0]['name'] = 'unknown.exe'
        self.api.writes.clear()
        with self.assertRaisesRegex(release.ReleaseError, 'Unknown'):
            self.publish()
        self.assertEqual(self.api.writes, [])

    def test_published_release_with_missing_asset_cannot_be_silently_repaired(self):
        self.publish()
        self.api.assets.pop()
        self.api.writes.clear()
        with self.assertRaisesRegex(release.ReleaseError, 'missing'):
            self.publish()
        self.assertEqual(self.api.writes, [])

    def test_corrupt_readback_blocks_publication(self):
        original = self.api.upload
        def corrupt(release_id, path):
            original(release_id, path)
            self.api.bytes[self.api.assets[-1]['id']] = b'corrupt'
        with mock.patch.object(self.api, 'upload', side_effect=corrupt), self.assertRaisesRegex(release.ReleaseError, 'Readback'):
            self.publish()
        self.assertTrue(self.api.release['draft'])
        self.assertFalse(any(w[0] == 'PATCH' for w in self.api.writes))

    def test_moved_main_before_publish_leaves_draft(self):
        with mock.patch.object(release, 'validate_ci', side_effect=[None, release.ReleaseError('Main moved')]):
            with self.assertRaisesRegex(release.ReleaseError, 'Main moved'):
                self.publish()
        self.assertTrue(self.api.release['draft'])


class SourcePublicationTests(PublicationTests):
    def setUp(self):
        super().setUp()
        path = self.work / release.CORRESPONDING_SOURCE
        path.write_bytes(b'unit fixture corresponding-source archive')
        self.files[path.name] = path

    def test_source_is_uploaded_and_read_back_before_any_binary(self):
        original = self.api.download
        sequence = []
        def download(path, destination, expected_hash, expected_size):
            name = next(asset['name'] for asset in self.api.assets if str(asset['id']) == path.rsplit('/', 1)[-1])
            sequence.append(('readback', name))
            return original(path, destination, expected_hash, expected_size)
        upload = self.api.upload
        def recorded_upload(release_id, path):
            sequence.append(('upload', path.name))
            return upload(release_id, path)
        with mock.patch.object(self.api, 'download', side_effect=download), mock.patch.object(self.api, 'upload', side_effect=recorded_upload):
            self.publish()
        self.assertEqual(sequence[:2], [('upload', release.CORRESPONDING_SOURCE), ('readback', release.CORRESPONDING_SOURCE)])

    def test_failed_source_readback_prevents_binary_uploads_and_publication(self):
        with mock.patch.object(self.api, 'download', side_effect=release.ReleaseError('Source readback failed')):
            with self.assertRaisesRegex(release.ReleaseError, 'Source readback'):
                self.publish()
        self.assertEqual([write[1] for write in self.api.writes if write[0] == 'UPLOAD'], [release.CORRESPONDING_SOURCE])
        self.assertTrue(self.api.release['draft'])
        self.assertFalse(any(write[0] == 'PATCH' for write in self.api.writes))


class WorkflowTests(unittest.TestCase):
    def test_workflow_has_no_pr_or_broad_branch_publish_trigger(self):
        workflow = (ROOT / '.github/workflows/release.yml').read_text()
        self.assertNotIn('pull_request', workflow)
        self.assertIn("branches: ['release-publish/**']", workflow)
        self.assertIn('paths: [.github/release-request.json]', workflow)
        self.assertIn('ref: refs/heads/main', workflow)
        self.assertIn('persist-credentials: false', workflow)
        self.assertIn('permissions: {}', workflow)
        self.assertIn('contents: write', workflow)
        self.assertIn('actions: read', workflow)
        self.assertNotIn('secrets.', workflow)
        self.assertNotIn('${{ inputs.', workflow)
        self.assertNotIn('pull_request_target', workflow)

    def test_notes_disclose_all_unverified_boundaries(self):
        notes = (ROOT / f'docs/releases/{release.TAG}.md').read_text()
        for phrase in ('unsigned', '1809', 'app-local', '14.51.36247.0', 'does not download',
                       'Clean-machine', 'future-version', 'manual checksum'):
            self.assertIn(phrase, notes)
        self.assertIn(f'https://github.com/{release.REPOSITORY}/releases/download/{release.TAG}/{release.CORRESPONDING_SOURCE}', notes)
        self.assertRegex(notes, r'SHA256SUMS[^\n]*all three downloads')


if __name__ == '__main__':
    unittest.main()
