"""MCP 2025-06-18 stdio adapter with cooperative analysis cancellation.

notifications/cancelled suppresses the original reply. An explicit cancel_analysis
tool call returns an acknowledgement and preserves the original analysis error.
Both use outer MCP IDs; native transport IDs never form the public cancel target.

https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/cancellation
https://modelcontextprotocol.io/specification/2025-06-18/basic/utilities/progress
"""

import json
import math
import sys
import threading

from core_client import Core, CoreError


def valid_id(value):
    # JSON Schema integer includes numeric representations such as 1.0. Exact
    # type checks exclude bool; fractional/nonfinite values are not valid IDs.
    return (type(value) in (str, int) or
            (type(value) is float and math.isfinite(value) and value.is_integer()))


def valid_progress_token(value):
    # Pinned 2025-06-18 ProgressToken is string|integer in the JSON Schema and
    # prose. JSON Schema integer includes representations such as 1.0, but not
    # fractional values. Preserve the original token instead of normalizing it.
    return valid_id(value)


def tool_result(data=None, error=None):
    if error is not None:
        result = {'content': [{'type': 'text', 'text': str(error)}], 'isError': True}
        if isinstance(error, CoreError):
            result['structuredContent'] = {'error': error.error}
        return result
    return {'content': [{'type': 'text', 'text': json.dumps(data, ensure_ascii=False)}],
            'structuredContent': data, 'isError': False}


class ToolCall:
    def __init__(self, rid, name, token):
        self.rid = rid
        self.name = name
        self.token = token
        self.request = None
        self.cancelled = False
        self.suppress_response = False
        self.progress = -1


class MCPServer:
    def __init__(self, core, output=sys.stdout):
        self.core = core
        self.output = output
        self.tools = core.call('capabilities')['tools']
        for tool in self.tools:
            if tool['name'] in {'cancel_analysis', 'pause_analysis', 'resume_analysis'}:
                tool['description'] = ('Cooperatively cancel an active analyze tool call by its outer '
                                       'MCP request ID. Returns an acknowledgement; the original '
                                       'analysis returns an analysis_cancelled tool error. '
                                       'notifications/cancelled instead suppresses that original reply.')
                if tool['name'] != 'cancel_analysis':
                    tool['description'] = ('Cooperatively ' + tool['name'].split('_')[0] +
                                           ' an active analyze tool call by its outer MCP request ID. '
                                           'Acknowledgement does not substitute for owner-thread progress status.')
                tool['inputSchema']['properties']['request_id']['description'] = (
                    'The outer MCP tools/call request ID of the active analyze call, preserving '
                    'string versus integer type. This is not an internal native request ID.')
        self._write_lock = threading.Lock()
        # Progress, cancellation intent and terminal output share this lock.
        self._lock = threading.Lock()
        self._active = {}
        self._workers = set()

    def send(self, value):
        with self._write_lock:
            self.output.write(json.dumps(value, ensure_ascii=False) + '\n')
            self.output.flush()

    def reply(self, rid, result):
        self.send({'jsonrpc': '2.0', 'id': rid, 'result': result})

    def _progress(self, call, event):
        if call.token is None or event.get('event') != 'progress':
            return
        with self._lock:
            if (self._active.get(call.rid) is not call or call.cancelled or
                    call.request.done()):
                return
            state = event.get('state', {})
            coverage = state.get('coverage', {})
            packets = coverage.get('scanned_packets', state.get('packets'))
            if type(packets) is not int or packets <= call.progress:
                return
            call.progress = packets
            params = {'progressToken': call.token, 'progress': packets,
                      'message': 'Analyzing transport-stream packets'}
            ranges = coverage.get('ranges', [])
            if ranges:
                params['total'] = sum(item['end_packet'] - item['start_packet'] for item in ranges)
            self.send({'jsonrpc': '2.0', 'method': 'notifications/progress', 'params': params})

    def _wait(self, call, translate_id=None):
        try:
            try:
                data = call.request.result()
                if translate_id is not None:
                    data = dict(data, request_id=translate_id)
                result = tool_result(data)
            except Exception as error:
                result = tool_result(error=error)
            with self._lock:
                if self._active.get(call.rid) is call:
                    del self._active[call.rid]
                    if not call.suppress_response:
                        self.reply(call.rid, result)
        finally:
            with self._lock:
                self._workers.discard(threading.current_thread())

    def _start_waiter(self, call, translate_id=None):
        worker = threading.Thread(target=self._wait, args=(call, translate_id), daemon=True)
        with self._lock:
            self._workers.add(worker)
        worker.start()

    def _cancel(self, target, suppress_response, method='cancel_analysis'):
        """Caller holds _lock. Only map active outer analysis IDs to native IDs."""
        call = self._active.get(target) if valid_id(target) else None
        if call is None or call.name != 'analyze' or call.request.done():
            return None
        if suppress_response:
            call.suppress_response = True
        if call.cancelled and suppress_response:
            return None
        if method == 'cancel_analysis':
            call.cancelled = True
        return self.core.submit(method, {'request_id': call.request.request_id})

    def _cancel_notification(self, request):
        # Notifications are fire-and-forget, including malformed/late requests.
        params = request.get('params')
        if (request.get('jsonrpc') != '2.0' or 'id' in request or not isinstance(params, dict) or
                not valid_id(params.get('requestId')) or
                ('reason' in params and not isinstance(params['reason'], str))):
            return
        try:
            with self._lock:
                self._cancel(params['requestId'], suppress_response=True)
        except CoreError:
            pass

    def _tool_call(self, rid, params):
        if not isinstance(params, dict) or not isinstance(params.get('name'), str):
            raise ValueError('tools/call requires a tool name')
        name = params['name']
        args = params.get('arguments', {})
        meta = params.get('_meta', {})
        token = meta.get('progressToken') if isinstance(meta, dict) else None
        token = token if valid_progress_token(token) else None
        call = ToolCall(rid, name, token)
        translate_id = None
        with self._lock:
            if rid in self._active:
                self.send({'jsonrpc': '2.0', 'id': rid,
                           'error': {'code': -32600, 'message': 'Request ID is already active'}})
                return
            try:
                if name in {'cancel_analysis', 'pause_analysis', 'resume_analysis'}:
                    if (not isinstance(args, dict) or set(args) != {'request_id'} or
                            not valid_id(args['request_id'])):
                        raise CoreError({'code': 'request_failed',
                                         'message': 'request_id must be an outer analysis request ID (string or integer)'})
                    translate_id = args['request_id']
                    call.request = self._cancel(translate_id, suppress_response=False, method=name)
                    if call.request is None:
                        self.reply(rid, tool_result({'request_id': translate_id,
                                                    'requested': False, 'reason': 'not_running'}))
                        return
                else:
                    call.request = self.core.submit(name, args,
                                                    progress=lambda event: self._progress(call, event))
            except CoreError as error:
                self.reply(rid, tool_result(error=error))
                return
            self._active[rid] = call
        self._start_waiter(call, translate_id)

    def handle(self, request):
        if not isinstance(request, dict):
            raise ValueError('Request must be an object')
        method = request.get('method')
        # Handle this before dropping idless messages: cancellation is a
        # notification by definition, not a tools/call request.
        if method == 'notifications/cancelled':
            self._cancel_notification(request)
            return
        if 'id' not in request:
            return
        rid = request['id']
        if not valid_id(rid):
            raise ValueError('Request ID must be a string or integer')
        if method == 'initialize':
            self.reply(rid, {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}},
                             'serverInfo': {'name': 'ShowPsiSi', 'version': '0.1.0'},
                             'instructions': 'Analyze first. Inspect source IDs and packet provenance. Preview edits before exporting to a new path. Source bytes are never edited.'})
        elif method == 'ping':
            self.reply(rid, {})
        elif method == 'tools/list':
            self.reply(rid, {'tools': self.tools})
        elif method == 'tools/call':
            self._tool_call(rid, request.get('params'))
        else:
            self.send({'jsonrpc': '2.0', 'id': rid,
                       'error': {'code': -32601, 'message': 'Method not found'}})

    def run(self, source=sys.stdin):
        for line in source:
            try:
                request = json.loads(line)
            except ValueError as error:
                self.send({'jsonrpc': '2.0', 'id': None,
                           'error': {'code': -32700, 'message': str(error)}})
                continue
            try:
                self.handle(request)
            except (ValueError, TypeError) as error:
                rid = request.get('id') if isinstance(request, dict) else None
                self.send({'jsonrpc': '2.0', 'id': rid if valid_id(rid) else None,
                           'error': {'code': -32600, 'message': str(error)}})
        # EOF is also used by one-shot/communicate clients. Drain accepted work
        # before explicit client cleanup, which may otherwise cancel analyses.
        with self._lock:
            workers = list(self._workers)
            # A paused native scan cannot finish while its stdin remains open.
            # Resume accepted analyses for passive EOF draining, not cancellation.
            for call in self._active.values():
                if call.name == 'analyze' and not call.request.done():
                    self.core.submit('resume_analysis', {'request_id': call.request.request_id})
        for worker in workers:
            worker.join()
        self.core.close()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stdin.reconfigure(encoding='utf-8')
    with Core() as core:
        MCPServer(core).run()
