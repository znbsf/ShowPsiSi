"""Real subprocess cancellation tests; synchronization uses test-only native gates.

Build with -DSHOWPSISI_BUILD_CANCELLATION_TESTS=ON. SHOWPSISI_TEST_CORE selects
showpsisi-core-test[.exe]; SHOWPSISI_CORE remains the production binary elsewhere.
The helper includes the real engine/parser and only adds a one-shot checkpoint.
"""

import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core, CoreError
from make_fixture import descriptor, section, word


def helper_path():
    production = Path(os.environ.get('SHOWPSISI_CORE', ROOT / 'build/bin' /
                                     ('showpsisi-core.exe' if os.name == 'nt' else 'showpsisi-core')))
    return Path(os.environ.get('SHOWPSISI_TEST_CORE',
                               production.with_name('showpsisi-core-test' + production.suffix)))


class MCPProcess:
    def __init__(self, env):
        self.proc = subprocess.Popen(
            [sys.executable, str(ROOT / 'scripts/mcp_server.py')],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', env=env,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.queue = queue.Queue()
        self.messages = []
        self.stderr = []
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.errors = threading.Thread(target=lambda: self.stderr.append(self.proc.stderr.read()), daemon=True)
        self.reader.start()
        self.errors.start()

    def _read(self):
        try:
            for line in self.proc.stdout:
                self.queue.put(json.loads(line))
        except Exception as error:
            self.queue.put(error)
        finally:
            self.queue.put(None)

    def send(self, request):
        self.proc.stdin.write(json.dumps(request) + '\n')
        self.proc.stdin.flush()

    def request(self, rid, method, params=None):
        self.send({'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': params or {}})

    def tool(self, rid, name, arguments=None, token=None):
        params = {'name': name, 'arguments': arguments or {}}
        if token is not None:
            params['_meta'] = {'progressToken': token}
        self.request(rid, 'tools/call', params)

    def cancel(self, rid):
        self.send({'jsonrpc': '2.0', 'method': 'notifications/cancelled',
                   'params': {'requestId': rid, 'reason': 'integration test'}})

    def until(self, predicate, start=0, timeout=10):
        deadline = time.monotonic() + timeout
        for message in self.messages[start:]:
            if predicate(message):
                return message
        while True:
            try:
                message = self.queue.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                raise AssertionError('MCP response timed out; stderr=' + ''.join(self.stderr)) from None
            if message is None:
                raise AssertionError('MCP exited before response; stderr=' + ''.join(self.stderr))
            if isinstance(message, Exception):
                raise message
            self.messages.append(message)
            if predicate(message):
                return message

    def response(self, rid):
        return self.until(lambda m: m.get('id') == rid and type(m.get('id')) is type(rid))

    def result(self, rid):
        return self.response(rid)['result']

    def close(self):
        if self.proc.stdin and not self.proc.stdin.closed:
            self.proc.stdin.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
        self.reader.join(timeout=5)
        self.errors.join(timeout=5)
        while not self.queue.empty():
            item = self.queue.get_nowait()
            if isinstance(item, dict):
                self.messages.append(item)
        self.proc.stdout.close()
        self.proc.stderr.close()


class CancellationTestCase(unittest.TestCase):
    def setUp(self):
        self.assertTrue(helper_path().is_file(),
                        'Build showpsisi-core-test with SHOWPSISI_BUILD_CANCELLATION_TESTS=ON '
                        'or set SHOWPSISI_TEST_CORE; these required tests must not skip.')
        self.tmp = tempfile.TemporaryDirectory(prefix='showpsisi-mcp-cancel-')
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.source = self.directory / 'source.ts'
        name = b'Cancellation test'
        desc = descriptor(0x48, b'\x01\x00' + bytes([len(name)]) + name)
        sdt = section(0x42, 1, 1, word(2) + b'\xff' + word(101) + b'\xff' + word(0x8000 + len(desc)) + desc)
        packet = b'\x47\x40\x11\x10\x00' + sdt + b'\xff' * (183 - len(sdt))
        null = b'\x47\x1f\xff\x10' + b'\xff' * 184
        self.source.write_bytes(packet + null * 63)
        self.source_hash = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.gate = self.directory / 'gate'
        self.env = dict(os.environ, SHOWPSISI_CORE=str(helper_path()),
                        SHOWPSISI_TEST_GATE=str(self.gate), SHOWPSISI_TEST_STAGE='after_progress',
                        SHOWPSISI_TEST_ANALYSIS_NUMBER='1')
        self.env.pop('SHOWPSISI_TEST_FAIL_AT_GATE', None)

    def ready(self, process):
        deadline = time.monotonic() + 10
        while not Path(str(self.gate) + '.ready').exists():
            self.assertIsNone(process.poll(), 'Native helper exited before gate')
            if time.monotonic() >= deadline:
                self.fail('Test-only native gate was never reached')
            threading.Event().wait(0.005)

    def release(self):
        Path(str(self.gate) + '.release').touch()

    def core(self):
        with patch.dict(os.environ, self.env, clear=True):
            core = Core()
        self.addCleanup(core.close)
        return core

    def mcp(self):
        process = MCPProcess(self.env)
        self.addCleanup(process.close)
        process.request('initialize', 'initialize', {'protocolVersion': '2025-06-18',
                                                     'capabilities': {},
                                                     'clientInfo': {'name': 'cancel-test', 'version': '1'}})
        self.assertEqual(process.result('initialize')['protocolVersion'], '2025-06-18')
        return process

    def assert_source_preserved(self):
        self.assertEqual(hashlib.sha256(self.source.read_bytes()).hexdigest(), self.source_hash)


class CoreTransportCancellationTests(CancellationTestCase):
    def test_progress_callback_can_cancel_synchronously_and_rescan(self):
        core = self.core()
        acknowledgements = []
        request = core.submit('analyze', {'path': str(self.source)},
                              progress=lambda event: acknowledgements.append(
                                  core.cancel_analysis(event['request_id'])))
        self.ready(core.proc)
        with self.assertRaises(CoreError) as caught:
            request.result(timeout=10)
        error = caught.exception
        self.assertIsInstance(error, RuntimeError)
        self.assertEqual(error.code, 'analysis_cancelled')
        self.assertEqual(error.message, 'Analysis cancelled')
        self.assertEqual(error.request_id, request.request_id)
        self.assertEqual(error.data, error.error['data'])
        self.assertEqual(error.data['state']['analysis_status'], 'cancelled')
        self.assertFalse(error.data['state']['complete'])
        self.assertEqual(acknowledgements, [{'request_id': request.request_id, 'requested': True}])
        self.assertEqual(core.call('query')['services'], [])
        self.assertTrue(core.call('analyze', {'path': str(self.source)})['complete'])
        self.assert_source_preserved()

    def test_interleaved_responses_timeout_and_error_data_are_preserved(self):
        core = self.core()
        analysis = core.submit('analyze', {'path': str(self.source)})
        self.ready(core.proc)
        with self.assertRaises(TimeoutError):
            analysis.result(timeout=0)
        self.assertFalse(analysis.done())
        query = core.submit('query')
        cancellation = core.submit('cancel_analysis', {'request_id': analysis.request_id})
        self.assertTrue(cancellation.result(timeout=10)['requested'])
        self.assertEqual(query.result(timeout=10)['analysis_status'], 'cancelled')
        with self.assertRaises(CoreError) as caught:
            analysis.result(timeout=10)
        self.assertEqual(caught.exception.code, 'analysis_cancelled')
        self.assertTrue(analysis.done())
        with self.assertRaises(CoreError) as repeated:
            analysis.result(timeout=0)
        self.assertIs(repeated.exception, caught.exception)
        self.assertEqual(core.call('capabilities')['name'], 'ShowPsiSi')

    def test_close_settles_active_request_and_reaps_reader(self):
        core = self.core()
        analysis = core.submit('analyze', {'path': str(self.source)})
        self.ready(core.proc)
        core.close()
        self.assertEqual(core.proc.poll(), 0)
        self.assertFalse(core._reader.is_alive())
        self.assertFalse(core._stderr_reader.is_alive())
        self.assertTrue(analysis.done())
        with self.assertRaises(CoreError):
            analysis.result(timeout=1)
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            core.call('query')
        core.close()

    def test_owned_native_process_exit_settles_pending_calls(self):
        core = self.core()
        analysis = core.submit('analyze', {'path': str(self.source)})
        self.ready(core.proc)
        pending = core.submit('query')
        core.proc.kill()
        for request in (analysis, pending):
            with self.assertRaises(CoreError) as caught:
                request.result(timeout=10)
            self.assertEqual(caught.exception.code, 'transport_error')
        core.close()
        self.assertFalse(core._reader.is_alive())

    def test_synchronous_calls_from_multiple_threads_keep_their_results(self):
        core = self.core()
        analysis = core.submit('analyze', {'path': str(self.source)})
        self.ready(core.proc)
        with ThreadPoolExecutor(max_workers=8) as pool:
            requests = [(method, pool.submit(core.call, method))
                        for method in ('query', 'capabilities') * 8]
            self.assertTrue(core.cancel_analysis(analysis.request_id)['requested'])
            for method, request in requests:
                result = request.result(timeout=10)
                if method == 'query':
                    self.assertEqual(result['analysis_status'], 'cancelled')
                else:
                    self.assertEqual(result['name'], 'ShowPsiSi')
        with self.assertRaises(CoreError):
            analysis.result(timeout=10)


class MCPCancellationTests(CancellationTestCase):
    def test_stdin_eof_drains_analysis_instead_of_cancelling(self):
        mcp = self.mcp()
        mcp.tool('eof-analysis', 'analyze', {'path': str(self.source)})
        self.ready(mcp.proc)
        mcp.proc.stdin.close()
        self.release()
        terminal = mcp.result('eof-analysis')
        self.assertFalse(terminal['isError'])
        self.assertTrue(terminal['structuredContent']['complete'])
        mcp.close()
        self.assertEqual(mcp.proc.returncode, 0)
        self.assertEqual(sum(m.get('id') == 'eof-analysis' for m in mcp.messages), 1)

    def test_notification_cancels_outer_id_without_reply_and_allows_rescan(self):
        mcp = self.mcp()
        mcp.tool('outer-analysis', 'analyze', {'path': str(self.source)})
        self.ready(mcp.proc)
        # The input loop must answer while native analysis is blocked at its gate.
        mcp.request('responsive', 'ping')
        self.assertEqual(mcp.result('responsive'), {})
        mcp.cancel('outer-analysis')
        mcp.tool('cancelled-state', 'query')
        state = mcp.result('cancelled-state')['structuredContent']
        self.assertEqual(state['analysis_status'], 'cancelled')
        self.assertEqual(state['tables'], [])
        mcp.tool('rescan', 'analyze', {'path': str(self.source)})
        self.assertTrue(mcp.result('rescan')['structuredContent']['complete'])
        mcp.close()
        self.assertNotIn('outer-analysis', [m.get('id') for m in mcp.messages])
        self.assertFalse(any(m.get('method') == 'notifications/progress' for m in mcp.messages))
        self.assert_source_preserved()

    def test_original_progress_token_monotonic_and_stops_on_cancel(self):
        for index, token in enumerate(('chosen-by-client', 0, '0', 17, -3, 1.0, -0.0)):
            with self.subTest(token=token):
                self.gate = self.directory / ('valid-token-gate-' + str(index))
                self.env['SHOWPSISI_TEST_GATE'] = str(self.gate)
                mcp = self.mcp()
                mcp.tool(731, 'analyze', {'path': str(self.source)}, token=token)
                self.ready(mcp.proc)
                event = mcp.until(lambda m: m.get('method') == 'notifications/progress')
                self.assertEqual(event['params']['progressToken'], token)
                self.assertIs(type(event['params']['progressToken']), type(token))
                mcp.cancel(731)
                mcp.request('cancel-read', 'ping')
                mcp.result('cancel-read')
                boundary = len(mcp.messages)
                mcp.tool('after-cancel', 'query')
                self.assertEqual(mcp.result('after-cancel')['structuredContent']['analysis_status'], 'cancelled')
                mcp.close()
                events = [m['params'] for m in mcp.messages if m.get('method') == 'notifications/progress']
                self.assertTrue(events)
                self.assertTrue(all(p['progressToken'] == token for p in events))
                self.assertTrue(all(a['progress'] < b['progress'] for a, b in zip(events, events[1:])))
                self.assertFalse(any(m.get('method') == 'notifications/progress' for m in mcp.messages[boundary:]))
                self.assertFalse(any(m.get('id') == 731 for m in mcp.messages))

    def test_invalid_progress_tokens_are_never_forwarded(self):
        # The pinned 2025-06-18 JSON Schema and progress prose require integer
        # or string tokens. In particular bool/null and fractional numbers do
        # not become either an invented progress token or a native request ID.
        for index, token in enumerate((True, False, None, 0.5, [], {})):
            with self.subTest(token=token):
                self.gate = self.directory / ('invalid-token-gate-' + str(index))
                self.env['SHOWPSISI_TEST_GATE'] = str(self.gate)
                mcp = self.mcp()
                mcp.request('invalid-token-analysis', 'tools/call',
                            {'name': 'analyze', 'arguments': {'path': str(self.source)},
                             '_meta': {'progressToken': token}})
                self.ready(mcp.proc)
                mcp.cancel('invalid-token-analysis')
                mcp.tool('state', 'query')
                self.assertEqual(mcp.result('state')['structuredContent']['analysis_status'], 'cancelled')
                mcp.close()
                self.assertFalse(any(m.get('method') == 'notifications/progress' for m in mcp.messages))

    def test_integral_numeric_outer_id_cancels_and_preserves_original_echo(self):
        mcp = self.mcp()
        mcp.tool(1.0, 'analyze', {'path': str(self.source)})
        self.ready(mcp.proc)
        mcp.tool('cancel-float-id', 'cancel_analysis', {'request_id': 1.0})
        acknowledgement = mcp.result('cancel-float-id')['structuredContent']
        self.assertTrue(acknowledgement['requested'])
        self.assertEqual(acknowledgement['request_id'], 1.0)
        self.assertIs(type(acknowledgement['request_id']), float)
        terminal = mcp.response(1.0)
        self.assertIs(type(terminal['id']), float)
        self.assertEqual(terminal['result']['structuredContent']['error']['code'], 'analysis_cancelled')
        mcp.tool('rescan', 'analyze', {'path': str(self.source)})
        self.assertTrue(mcp.result('rescan')['structuredContent']['complete'])

    def test_numeric_outer_alias_is_duplicate_but_string_id_is_distinct(self):
        mcp = self.mcp()
        mcp.tool(1.0, 'analyze', {'path': str(self.source)})
        self.ready(mcp.proc)
        mcp.tool(1, 'query')
        duplicate = mcp.response(1)
        self.assertEqual(duplicate['error']['code'], -32600)
        self.assertIs(type(duplicate['id']), int)
        # String "1" remains a separate accepted request queued after analysis.
        mcp.tool('1', 'query')
        mcp.cancel(1)
        self.assertEqual(mcp.result('1')['structuredContent']['analysis_status'], 'cancelled')
        mcp.close()
        numeric = [m for m in mcp.messages if type(m.get('id')) in (int, float)]
        self.assertEqual(numeric, [duplicate])

    def test_invalid_outer_request_ids_do_not_submit_native_work(self):
        mcp = self.mcp()
        for rid in (True, False, None, 0.5, float('inf'), float('nan')):
            with self.subTest(rid=rid):
                boundary = len(mcp.messages)
                mcp.tool(rid, 'analyze', {'path': str(self.source)})
                reply = mcp.until(lambda m: m.get('error', {}).get('code') == -32600,
                                  start=boundary)
                self.assertIsNone(reply['id'])
        self.assertFalse(Path(str(self.gate) + '.ready').exists())
        # The first valid analysis still reaches the one-shot gate.
        mcp.tool('valid', 'analyze', {'path': str(self.source)})
        self.ready(mcp.proc)
        self.release()
        self.assertTrue(mcp.result('valid')['structuredContent']['complete'])

    def test_explicit_cancel_tool_maps_id_and_preserves_terminal_error(self):
        mcp = self.mcp()
        mcp.request('discovery', 'tools/list')
        self.assertIn('cancel_analysis', [t['name'] for t in mcp.result('discovery')['tools']])
        mcp.tool('external-id', 'analyze', {'path': str(self.source)}, token='only-this-token')
        self.ready(mcp.proc)
        mcp.tool('cancel-request', 'cancel_analysis', {'request_id': 'external-id'})
        acknowledgement = mcp.result('cancel-request')['structuredContent']
        self.assertEqual(acknowledgement, {'request_id': 'external-id', 'requested': True})
        terminal = mcp.result('external-id')
        self.assertTrue(terminal['isError'])
        error = terminal['structuredContent']['error']
        self.assertEqual(error['code'], 'analysis_cancelled')
        self.assertEqual(error['data']['state']['analysis_status'], 'cancelled')
        path = self.directory / 'cancelled.bin'
        mcp.tool('reject-export', 'export', {'path': str(path), 'format': 'bin'})
        self.assertTrue(mcp.result('reject-export')['isError'])
        self.assertFalse(path.exists())
        mcp.tool('rescan', 'analyze', {'path': str(self.source)})
        self.assertFalse(mcp.result('rescan')['isError'])
        mcp.tool('export', 'export', {'path': str(path), 'format': 'bin'})
        self.assertFalse(mcp.result('export')['isError'])
        self.assertTrue(path.is_file())
        self.assert_source_preserved()

    def test_repeated_explicit_cancel_of_queued_analysis_is_acknowledged(self):
        mcp = self.mcp()
        mcp.tool('held-analysis', 'analyze', {'path': str(self.source)})
        self.ready(mcp.proc)
        mcp.tool('queued-analysis', 'analyze', {'path': str(self.source)})
        for rid in ('first-cancel', 'second-cancel'):
            mcp.tool(rid, 'cancel_analysis', {'request_id': 'queued-analysis'})
            self.assertEqual(mcp.result(rid)['structuredContent'],
                             {'request_id': 'queued-analysis', 'requested': True})
        self.release()
        self.assertTrue(mcp.result('held-analysis')['structuredContent']['complete'])
        result = mcp.result('queued-analysis')
        self.assertTrue(result['isError'])
        self.assertEqual(result['structuredContent']['error']['code'], 'analysis_cancelled')

    def test_unknown_malformed_and_internal_ids_do_not_cancel(self):
        mcp = self.mcp()
        mcp.tool('2', 'analyze', {'path': str(self.source)})
        self.ready(mcp.proc)
        # Native ID 2 is intentionally different from outer string ID "2".
        for target in (2, 'unknown', True, None, [], {}):
            mcp.cancel(target)
        for params in ({}, [], {'requestId': '2', 'reason': 42}):
            mcp.send({'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': params})
        mcp.send({'jsonrpc': '2.0', 'id': 'malformed', 'method': 'notifications/cancelled',
                  'params': {'requestId': '2'}})
        mcp.send({'method': 'notifications/cancelled', 'params': {'requestId': '2'}})
        mcp.tool('wrong-id-tool', 'cancel_analysis', {'request_id': 2})
        self.assertFalse(mcp.result('wrong-id-tool')['structuredContent']['requested'])
        mcp.tool('invalid-tool', 'cancel_analysis', {'request_id': []})
        self.assertTrue(mcp.result('invalid-tool')['isError'])
        mcp.request('fence', 'ping')
        self.assertEqual(mcp.result('fence'), {})
        self.release()
        self.assertTrue(mcp.result('2')['structuredContent']['complete'])
        mcp.close()
        self.assertNotIn('malformed', [m.get('id') for m in mcp.messages])
        self.assertFalse(any(m.get('id') is None for m in mcp.messages))

    def test_late_cancel_and_post_terminal_progress_are_ignored(self):
        mcp = self.mcp()
        mcp.tool('done', 'analyze', {'path': str(self.source)}, token='completion-token')
        self.ready(mcp.proc)
        mcp.until(lambda m: m.get('method') == 'notifications/progress')
        self.release()
        self.assertTrue(mcp.result('done')['structuredContent']['complete'])
        boundary = len(mcp.messages)
        mcp.cancel('done')
        mcp.tool('late-tool', 'cancel_analysis', {'request_id': 'done'})
        self.assertFalse(mcp.result('late-tool')['structuredContent']['requested'])
        mcp.tool('state', 'query')
        self.assertTrue(mcp.result('state')['structuredContent']['complete'])
        mcp.close()
        self.assertFalse(any(m.get('method') == 'notifications/progress' for m in mcp.messages[boundary:]))
        self.assertEqual(sum(m.get('id') == 'done' for m in mcp.messages), 1)

    def test_cancellation_never_targets_queued_export(self):
        self.env['SHOWPSISI_TEST_ANALYSIS_NUMBER'] = '2'
        mcp = self.mcp()
        mcp.tool('first', 'analyze', {'path': str(self.source)})
        self.assertTrue(mcp.result('first')['structuredContent']['complete'])
        mcp.tool('second', 'analyze', {'path': str(self.source)})
        self.ready(mcp.proc)
        destination = self.directory / 'retained-export.bin'
        mcp.tool('export-id', 'export', {'path': str(destination), 'format': 'bin'})
        mcp.cancel('export-id')
        mcp.tool('cancel-export', 'cancel_analysis', {'request_id': 'export-id'})
        self.assertFalse(mcp.result('cancel-export')['structuredContent']['requested'])
        self.release()
        self.assertTrue(mcp.result('second')['structuredContent']['complete'])
        self.assertFalse(mcp.result('export-id')['isError'])
        self.assertTrue(destination.is_file())
        self.assertTrue(Path(str(destination) + '.manifest.json').is_file())
        self.assert_source_preserved()


if __name__ == '__main__':
    unittest.main(verbosity=2)
