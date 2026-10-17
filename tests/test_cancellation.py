"""Deterministic native cancellation checks; requires the opt-in test binary.

Build with -DSHOWPSISI_BUILD_CANCELLATION_TESTS=ON. SHOWPSISI_TEST_CORE
selects the helper (including MultiConfig bin/Release paths). A missing helper
is a failure, never a skipped validation. No timing/large-file cancellation race.
"""
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SUFFIX = '.exe' if os.name == 'nt' else ''
HELPER = Path(os.environ.get('SHOWPSISI_TEST_CORE', ROOT / 'build/bin' / ('showpsisi-core-test' + SUFFIX)))
PRODUCTION = Path(os.environ.get('SHOWPSISI_CORE', ROOT / 'build/bin' / ('showpsisi-core' + SUFFIX)))


class Wire:
    def __init__(self, directory, stage='after_progress', number=1, fail=False, production=False,
                 pause_publication=False):
        self.prefix = Path(directory) / 'gate'
        env = os.environ.copy()
        for key in tuple(env):
            if key.startswith('SHOWPSISI_TEST_'):
                env.pop(key)
        if stage:
            env.update(SHOWPSISI_TEST_GATE=str(self.prefix), SHOWPSISI_TEST_STAGE=stage,
                       SHOWPSISI_TEST_ANALYSIS_NUMBER=str(number))
        if fail:
            env['SHOWPSISI_TEST_FAIL_AT_GATE'] = '1'
        if pause_publication:
            env['SHOWPSISI_TEST_PAUSE_GATE_PUBLICATION'] = '1'
        self.proc = subprocess.Popen([str(PRODUCTION if production else HELPER), '--root', str(ROOT)],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding='utf-8', env=env,
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.incoming = queue.Queue()
        self.pending = []
        self.messages = []
        def read():
            try:
                for line in self.proc.stdout:
                    self.incoming.put(json.loads(line))
            except Exception as error:
                self.incoming.put(error)
            finally:
                self.incoming.put(None)
        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def send(self, ident, method, params=None):
        self.raw(json.dumps({'id': ident, 'method': method, 'params': params or {}}))

    def raw(self, line):
        self.proc.stdin.write(line + '\n')
        self.proc.stdin.flush()

    def response(self, ident, timeout=10):
        def matches(message):
            return 'event' not in message and type(message.get('id')) is type(ident) and message.get('id') == ident
        for index, message in enumerate(self.pending):
            if matches(message):
                return self.pending.pop(index)
        deadline = time.monotonic() + timeout
        while True:
            message = self.incoming.get(timeout=max(.01, deadline - time.monotonic()))
            if message is None:
                raise AssertionError('Engine exited before response: ' + self.proc.stderr.read())
            if isinstance(message, Exception):
                raise message
            self.messages.append(message)
            if matches(message):
                return message
            if 'event' not in message:
                self.pending.append(message)

    def call(self, ident, method, params=None):
        self.send(ident, method, params)
        return self.response(ident)

    def gate(self):
        ready = Path(str(self.prefix) + '.ready')
        deadline = time.monotonic() + 10
        while not ready.exists():
            if self.proc.poll() is not None:
                raise AssertionError('Engine exited before gate: ' + self.proc.stderr.read())
            if time.monotonic() > deadline:
                raise AssertionError('Native test checkpoint was not reached')
            time.sleep(.005)

    def release(self):
        Path(str(self.prefix) + '.release').touch()

    def close(self):
        Path(str(self.prefix) + '.publish-release').touch()
        self.release()
        if not self.proc.stdin.closed:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
            raise AssertionError('Engine did not drain and exit on EOF')
        self.reader.join(timeout=2)
        self.proc.stdout.close()
        stderr = self.proc.stderr.read()
        self.proc.stderr.close()
        if self.proc.returncode != 0:
            raise AssertionError(f'Engine exited {self.proc.returncode}: {stderr}')


class CancellationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HELPER.is_file():
            raise AssertionError(f'Build the opt-in showpsisi-core-test target or set SHOWPSISI_TEST_CORE: {HELPER}')
        if not PRODUCTION.is_file():
            raise AssertionError(f'Production core missing: {PRODUCTION}')
        cls.fixture = tempfile.TemporaryDirectory(prefix='showpsisi-cancel-fixture-')
        cls.source = Path(cls.fixture.name) / 'small.ts'
        # Real fixture packets include PAT, PMT, SDT and EIT. Gating, not size,
        # makes every cancellation deterministic.
        with (ROOT / 'samples/generated/lab.ts').open('rb') as source:
            cls.source.write_bytes(source.read(188 * 4096))
        cls.digest = hashlib.sha256(cls.source.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='showpsisi-cancel-')
        self.addCleanup(self.tmp.cleanup)

    def wire(self, **kwargs):
        wire = Wire(self.tmp.name, **kwargs)
        self.addCleanup(wire.close)
        return wire

    def analyze(self, wire, ident=1, path=None, **kwargs):
        wire.send(ident, 'analyze', {'path': str(path or self.source), **kwargs})

    def assert_cleared(self, state, status='cancelled'):
        self.assertEqual(state['analysis_status'], status)
        self.assertFalse(state['complete'])
        for key in ('tables', 'services', 'events', 'history', 'diagnostics'):
            self.assertEqual(state[key], [], key)
        self.assertEqual(state['observations'], 0)
        self.assertEqual(state['crc_errors'], 0)
        self.assertEqual(state['demux'], {})
        self.assertTrue(all(item == {'count': 0, 'bad': 0} for item in state['density']))

    def assert_cancelled(self, message):
        self.assertEqual(message['error']['code'], 'analysis_cancelled')
        state = message['error']['data']['state']
        self.assert_cleared(state)
        return state

    def test_checkpoint_publishes_complete_json_atomically(self):
        wire = self.wire(pause_publication=True)
        self.analyze(wire)
        ready = Path(str(wire.prefix) + '.ready')
        temporary = Path(str(ready) + '.tmp')
        deadline = time.monotonic() + 10
        while True:
            self.assertIsNone(wire.proc.poll(), 'Helper exited before publication barrier')
            if temporary.exists() and temporary.read_bytes() == b'{':
                break
            if time.monotonic() >= deadline:
                self.fail('Helper did not reach partial-publication barrier')
            time.sleep(.005)
        self.assertFalse(ready.exists(), 'Incomplete checkpoint was publicly visible')
        Path(str(wire.prefix) + '.publish-release').touch()
        wire.gate()
        # Read immediately on existence, exactly as the browser consumer does.
        self.assertEqual(json.loads(ready.read_text()), {'stage': 'after_progress', 'analysis_number': 1})
        self.assertFalse(temporary.exists())
        wire.release()
        self.assertTrue(wire.response(1)['result']['complete'])

    def test_checkpoint_write_failure_never_publishes_ready(self):
        wire = self.wire()
        ready = Path(str(wire.prefix) + '.ready')
        temporary = Path(str(ready) + '.tmp')
        temporary.mkdir()
        # A nonempty directory makes opening the private file fail on all OSes.
        (temporary / 'sentinel').write_text('keep')
        self.analyze(wire)
        reply = wire.response(1)
        self.assertEqual(reply['error']['code'], 'request_failed')
        self.assertIn('ready-file open failed', reply['error']['message'])
        self.assertFalse(ready.exists())
        self.assertEqual((temporary / 'sentinel').read_text(), 'keep')
        self.assert_cleared(wire.call(2, 'query')['result'], 'failed')

    def test_checkpoint_rename_failure_cleans_private_file(self):
        wire = self.wire()
        ready = Path(str(wire.prefix) + '.ready')
        ready.mkdir()
        (ready / 'sentinel').write_text('keep')
        self.analyze(wire)
        self.assertEqual(wire.response(1)['error']['code'], 'request_failed')
        self.assertFalse(Path(str(ready) + '.tmp').exists())
        self.assertEqual((ready / 'sentinel').read_text(), 'keep')
        self.assert_cleared(wire.call(2, 'query')['result'], 'failed')

    def test_idle_and_failed_metrics_are_frozen(self):
        wire = self.wire(stage=None)
        idle = wire.call(1, 'query')['result']
        self.assertEqual(idle['analysis_status'], 'idle')
        self.assertEqual(idle['metrics']['scan_ms'], 0)
        self.analyze(wire, 2, Path(self.tmp.name) / 'missing.ts')
        self.assertEqual(wire.response(2)['error']['code'], 'request_failed')
        failed = wire.call(3, 'query')['result']
        self.assert_cleared(failed, 'failed')
        time.sleep(.01)
        self.assertEqual(wire.call(4, 'query')['result']['metrics'], failed['metrics'])

    def cancellation_at(self, stage):
        wire = self.wire(stage=stage)
        self.analyze(wire)
        wire.gate()
        self.assertTrue(wire.call(2, 'cancel_analysis', {'request_id': 1})['result']['requested'])
        state = self.assert_cancelled(wire.response(1))
        self.assertEqual(Path(state['source']), self.source)
        self.assertGreater(state['revision'], 0)
        if stage in ('before_analysis', 'before_read'):
            self.assertEqual(state['packets'], 0)
        else:
            self.assertGreater(state['packets'], 0)
        time.sleep(.01)
        self.assertEqual(wire.call(3, 'query')['result'], state)
        late = wire.call(4, 'cancel_analysis', {'request_id': 1})['result']
        self.assertEqual(late, {'request_id': 1, 'requested': False, 'reason': 'not_running'})
        self.analyze(wire, 5)
        resumed = wire.response(5)['result']
        self.assertTrue(resumed['complete'])
        self.assertEqual(resumed['analysis_status'], 'complete')
        self.assertGreater(resumed['revision'], state['revision'])
        self.assertTrue(resumed['services'])
        terminal = next(i for i, item in enumerate(wire.messages) if item.get('id') == 1 and 'error' in item)
        self.assertFalse(any(item.get('event') == 'progress' and item.get('request_id') == 1 for item in wire.messages[terminal+1:]))
        self.assertEqual(sum('event' not in item and item.get('id') == 1 for item in wire.messages), 1)
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.digest)

    def test_cancel_before_execution(self): self.cancellation_at('before_analysis')
    def test_cancel_before_first_packet_read(self): self.cancellation_at('before_read')
    def test_cancel_before_progress_build(self): self.cancellation_at('before_progress')
    def test_cancel_after_real_partial_evidence(self): self.cancellation_at('after_progress')
    def test_cancel_wins_at_completion_boundary(self): self.cancellation_at('before_complete')

    def test_completion_commit_wins_over_late_cancel(self):
        wire = self.wire(stage='after_complete')
        self.analyze(wire)
        wire.gate()
        self.assertEqual(wire.call(2, 'cancel_analysis', {'request_id': 1})['result']['reason'], 'not_running')
        wire.release()
        completed = wire.response(1)['result']
        self.assertTrue(completed['complete'])
        self.assertTrue(completed['services'])
        self.assertEqual(wire.call(3, 'query')['result']['tables'], completed['tables'])

    def test_completed_id_can_be_reused_immediately(self):
        # The owner is held immediately after publishing the first terminal
        # response, so this probes registry retirement without a timing race.
        wire = self.wire(stage='after_terminal')
        self.analyze(wire, 'reused')
        first = wire.response('reused')['result']
        wire.gate()
        self.analyze(wire, 'reused')
        self.assertTrue(wire.call(2, 'cancel_analysis', {'request_id': 'reused'})['result']['requested'])
        wire.release()
        second = self.assert_cancelled(wire.response('reused'))
        self.assertEqual(second['revision'], first['revision'] + 1)

    def test_queued_cancellation_duplicate_ids_and_exact_types(self):
        wire = self.wire()
        self.analyze(wire, 1)
        wire.gate()
        missing = Path(self.tmp.name) / 'never-opened.ts'
        self.analyze(wire, '1', missing)
        self.analyze(wire, '1', self.source)
        self.assertEqual(wire.response('1')['error']['code'], 'duplicate_request_id')
        for ident in (2, 3):
            self.assertTrue(wire.call(ident, 'cancel_analysis', {'request_id': '1'})['result']['requested'])
        self.assertFalse(wire.call(4, 'cancel_analysis', {'request_id': 'unknown'})['result']['requested'])
        wire.release()
        self.assertTrue(wire.response(1)['result']['complete'])
        cancelled = self.assert_cancelled(wire.response('1'))
        self.assertEqual(cancelled['packets'], 0)
        self.assertEqual(Path(cancelled['source']), missing)
        self.assertEqual(wire.call(5, 'query')['result'], cancelled)

    def test_cancel_bypasses_full_fifo_and_eof_drains_valid_work(self):
        wire = self.wire()
        self.analyze(wire)
        wire.gate()
        for ident in range(100, 164):
            wire.send(ident, 'query')
        wire.send(164, 'query')
        self.assertEqual(wire.response(164)['error']['code'], 'queue_full')
        self.assertTrue(wire.call(2, 'cancel_analysis', {'request_id': 1})['result']['requested'])
        wire.proc.stdin.close()
        self.assert_cancelled(wire.response(1))
        for ident in range(100, 164):
            self.assert_cleared(wire.response(ident)['result'])
        wire.proc.wait(timeout=5)
        terminals = [item['id'] for item in wire.messages if 'result' in item and item.get('id') in range(100, 164)]
        self.assertEqual(terminals, list(range(100, 164)))

    def test_invalid_requests_never_become_cancellable(self):
        wire = self.wire()
        self.analyze(wire)
        wire.gate()
        invalid = [{}, {'path': 4}, {'path': str(self.source), 'standards': 'bogus'},
                   {'path': str(self.source), 'extra_pids': [True]},
                   {'path': str(self.source), 'extra_pids': [8192]},
                   {'path': str(self.source), 'extra_pids': [1.5]}]
        for index, params in enumerate(invalid, 10):
            wire.send(index, 'analyze', params)
            self.assertEqual(wire.response(index)['error']['code'], 'request_failed')
            self.assertFalse(wire.call(index+100, 'cancel_analysis', {'request_id': index})['result']['requested'])
        for index, target in enumerate([None, True, 1.0, [], {}], 30):
            self.assertEqual(wire.call(index, 'cancel_analysis', {'request_id': target})['error']['code'], 'request_failed')
        wire.raw('{broken json')
        self.assertEqual(wire.response(None)['error']['code'], 'request_failed')
        self.assertTrue(wire.call(50, 'cancel_analysis', {'request_id': 1})['result']['requested'])
        self.assert_cancelled(wire.response(1))

    def test_cancel_replaces_old_source_invalidates_preview_preserves_extension(self):
        wire = self.wire(number=2)
        self.analyze(wire)
        original = wire.response(1)['result']
        service = original['services'][0]
        preview = wire.call(2, 'preview_rename', {'id': service['source_id'], 'service_id': service['id'], 'name': 'Pending'})['result']
        extension = json.loads((ROOT / 'extensions/demo.json').read_text(encoding='utf-8'))
        extension['id'] = 'cancel-preserved-extension'
        path = Path(self.tmp.name) / 'extension.json'
        path.write_text(json.dumps(extension), encoding='utf-8')
        wire.call(3, 'load_extension', {'path': str(path)})
        replacement = Path(self.tmp.name) / 'new-source.ts'
        replacement.write_bytes(self.source.read_bytes())
        self.analyze(wire, 4, replacement, standards='dvb')
        wire.gate()
        self.assertTrue(wire.call(5, 'cancel_analysis', {'request_id': 4})['result']['requested'])
        state = self.assert_cancelled(wire.response(4))
        self.assertEqual(Path(state['source']), replacement)
        self.assertEqual(state['extension_id'], extension['id'])
        self.assertEqual(state['standards_context'], 'dvb')
        output = Path(self.tmp.name) / 'must-not-exist.ts'
        self.assertIn('error', wire.call(6, 'export', {'path': str(output), 'preview_token': preview['token']}))
        self.assertFalse(output.exists())
        self.assertIn('error', wire.call(7, 'inspect', {'id': service['source_id']}))
        self.assertIn('error', wire.call(8, 'diff_snapshots', {'from_packet': 0, 'to_packet': 1}))
        self.analyze(wire, 9)
        resumed = wire.response(9)['result']
        self.assertGreater(resumed['revision'], state['revision'])
        self.assertEqual(resumed['extension_id'], extension['id'])
        self.assertIn('error', wire.call(10, 'export', {'path': str(output), 'preview_token': preview['token']}))

    def test_failure_after_real_progress_clears_partial_evidence(self):
        wire = self.wire(fail=True)
        self.analyze(wire)
        wire.gate()
        wire.release()
        self.assertEqual(wire.response(1)['error']['code'], 'request_failed')
        state = wire.call(2, 'query')['result']
        self.assert_cleared(state, 'failed')
        self.assertGreater(state['packets'], 0)
        time.sleep(.01)
        self.assertEqual(wire.call(3, 'query')['result'], state)
        self.analyze(wire, 4)
        self.assertTrue(wire.response(4)['result']['complete'])

    def test_production_ignores_test_gate_environment(self):
        wire = self.wire(production=True, pause_publication=True)
        self.analyze(wire)
        self.assertTrue(wire.response(1)['result']['complete'])
        self.assertFalse(Path(str(wire.prefix) + '.ready').exists())
        self.assertFalse(Path(str(wire.prefix) + '.ready.tmp').exists())


if __name__ == '__main__':
    unittest.main()
