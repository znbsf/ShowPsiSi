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
REQUEST = {'schema_version': 1, 'version': '0.1.0', 'source_sha': SOURCE, 'ci_run_id': 123}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding='utf-8')


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
        for key, value in [('version', '0.2.0'), ('source_sha', TRIGGER), ('url', 'https://evil.example'),
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
        env['GITHUB_REF'] = event['ref'] = 'refs/heads/release-publish/v0.2.0'
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


class PayloadTests(TemporaryTest):
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
        for path in package.rglob('*.json'):
            if path.name not in ('build-information.json', 'redistribution-review.json', 'manifest.json', 'source-index.json', 'SOURCE-PROVENANCE.json'):
                write_json(path, {})
        write_json(package / 'bin/showpsisi-portable.json', {'schema_version': 1, 'scope': 'qt-core', 'resource_root': '..'})
        opaque = package / 'licenses/qt/upstream-attribution.json'
        opaque.parent.mkdir(parents=True)
        opaque.write_bytes(b'{"upstream":"retained","upstream":"verbatim control \x01"}')
        fixture.fixture.approve_fixture()
        self.setup_dir, self.zip_dir, self.ie, self.pe = [self.work / name for name in release.ARTIFACTS]
        for path in (self.setup_dir, self.zip_dir, self.ie, self.pe):
            path.mkdir()
        setup = self.setup_dir / release.SETUP
        setup.write_bytes(b'MZ unit fixture, never executable')
        record = fixture.prepare()
        record.update(installer_sha256=release.sha256(setup), installer_bytes=setup.stat().st_size)
        write_json(self.setup_dir / 'installer-build.json', record)
        write_json(self.ie / 'artifacts/installer-candidate/installer-build.json', record)
        write_json(self.ie / '.deps/installer-prerequisite/vc-runtime.json', fixture.runtime)
        validation = json.loads((fixture.evidence / 'portable-validation.json').read_text())
        validation.update(native_windows_desktop_verified=False)
        validation['runtime_requirement']['required_minimum'] = release.installer.MINIMUM_RUNTIME
        write_json(fixture.evidence / 'portable-validation.json', validation)
        release.portable.archive(package, fixture.evidence, self.zip_dir / release.PORTABLE)
        sums = ''.join(f'{release.sha256(path)}  {path.name}\n' for path in (setup, self.zip_dir / release.PORTABLE))
        (self.setup_dir / 'SHA256SUMS').write_text(sums)
        (self.zip_dir / 'SHA256SUMS').write_text(sums)
        write_json(self.pe / 'portable-validation/portable-validation.json', validation)
        (self.pe / 'portable-stage').mkdir()
        for name in ('manifest.json', 'build-information.json'):
            shutil.copyfile(package / name, self.pe / 'portable-stage' / name)
        write_json(self.pe / 'portable-launcher-probe/preflight.json', {'passed': True,
                   'launcher_sha256': release.sha256(package / 'Launch Qt.cmd'), 'cases': [
                       {'name': name, 'exit_code': code} for name, code in
                       [('host-runtime-ready', 0), ('missing-runtime-blocked', 1), ('old-runtime-blocked', 1)]]})
        self.smoke = {'passed': True, 'installer_sha256': release.sha256(setup),
                      'package_manifest_sha256': release.sha256(package / 'manifest.json'),
                      'clean_machine_verified': False, 'native_dialogs_verified': False, 'runtime_bootstrap_exercised': False,
                      'production_core_mutex': {'held_while_running': True, 'released_after_exit': True},
                      'settings_preserved': True, 'shortcuts_verified': True, 'all_manifested_payload_removed': True,
                      'steps': [{'name': name, 'exit_code': code} for name, code in [
                          ('reject-uninstalled-update', 7), ('install-previous', 0), ('reject-live-app-update', 1),
                          ('reject-live-app-uninstall', 1), ('upgrade', 0), ('reinstall', 0), ('reject-downgrade', 7), ('uninstall', 0)]]}
        self.smoke_path = self.ie / 'artifacts/installer-validation/installer-smoke.json'
        write_json(self.smoke_path, self.smoke)

    def validate(self):
        return release.validate_payload(self.work, REQUEST)

    def test_full_same_source_payload_is_accepted_without_execution(self):
        with mock.patch.object(release.subprocess, 'run', side_effect=AssertionError('Artifacts must not execute')):
            files, manifest, runtime = self.validate()
        self.assertEqual(set(files), {release.SETUP, release.PORTABLE, 'SHA256SUMS'})
        self.assertEqual(manifest, self.smoke['package_manifest_sha256'])
        self.assertEqual(runtime, 'b' * 64)

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
        setup = self.setup_dir / release.SETUP
        sums = ''.join(f'{release.sha256(path)}  {path.name}\n' for path in (setup, zipped))
        for path in (self.setup_dir / 'SHA256SUMS', self.zip_dir / 'SHA256SUMS'):
            path.write_text(sums)
        (self.zip_dir / (release.PORTABLE + '.sha256')).write_text(f'{release.sha256(zipped)}  {release.PORTABLE}\n')
        with self.assertRaisesRegex(RuntimeError, 'changed after manifest'):
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
        value['cases'][1]['exit_code'] = 0
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
        self.assertEqual(len(self.api.assets), 4)
        methods = [w[0] for w in self.api.writes]
        self.assertEqual(methods, ['POST', 'POST', 'UPLOAD', 'UPLOAD', 'UPLOAD', 'UPLOAD', 'PATCH'])

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
        self.assertEqual(len(self.api.assets), 4)

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
        notes = (ROOT / 'docs/releases/v0.1.0.md').read_text()
        for phrase in ('unsigned', '1809', 'UAC', 'Internet', 'Clean-machine', 'future-version', 'manual checksum'):
            self.assertIn(phrase, notes)


if __name__ == '__main__':
    unittest.main()
