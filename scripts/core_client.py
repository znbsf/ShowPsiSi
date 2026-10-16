"""Thread-safe CLI/automation client for the native UTF-8 JSON Lines engine."""

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from collections import deque

ROOT = Path(__file__).resolve().parents[1]


class CoreError(RuntimeError):
    """A native error, retaining its machine-readable code and optional data."""

    def __init__(self, error, request_id=None):
        self.error = dict(error)
        self.code = error.get('code')
        self.message = error.get('message', 'Native engine error')
        self.data = error.get('data')
        self.request_id = request_id
        super().__init__(self.message)


class CoreRequest:
    """Submitted request. Waiting dispatches its progress on the waiting thread.

    The stdout reader never runs user callbacks, so a progress callback can
    synchronously cancel or query the engine without blocking response routing.
    A timeout only stops waiting; it does not cancel the native operation.
    """

    def __init__(self, request_id, method, progress):
        self.request_id = request_id
        self.method = method
        self._progress = progress
        self._messages = queue.Queue()
        self._terminal = threading.Event()
        self._result_lock = threading.Lock()
        self._resolved = False
        self._value = None
        self._error = None

    def done(self):
        return self._terminal.is_set()

    def _receive(self, message):
        self._messages.put(message)
        if 'event' not in message:
            self._terminal.set()

    def result(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        remaining = lambda: None if deadline is None else max(0, deadline - time.monotonic())
        if deadline is None:
            self._result_lock.acquire()
        elif not self._result_lock.acquire(timeout=remaining()):
            raise TimeoutError('Timed out waiting for native response')
        try:
            while not self._resolved:
                try:
                    message = self._messages.get(timeout=remaining())
                except queue.Empty:
                    raise TimeoutError('Timed out waiting for native response') from None
                if 'event' in message:
                    if self._progress:
                        self._progress(message)
                    continue
                self._resolved = True
                if 'error' in message:
                    self._error = CoreError(message['error'], self.request_id)
                else:
                    self._value = message['result']
            if self._error is not None:
                raise self._error
            return self._value
        finally:
            self._result_lock.release()


class Core:
    def __init__(self):
        executable = Path(os.environ.get(
            'SHOWPSISI_CORE', str(ROOT / 'build/bin' /
                                 ('showpsisi-core.exe' if os.name == 'nt' else 'showpsisi-core'))))
        self.proc = subprocess.Popen(
            [str(executable), '--root', str(ROOT)], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.seq = 0
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._pending = {}
        self._closed = False
        self._failure = None
        self._stderr = deque(maxlen=16)
        self._stderr_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._stderr_reader.start()
        self._reader.start()

    def _read_stderr(self):
        # Drain continuously so diagnostics cannot fill the child's pipe.
        try:
            for chunk in iter(lambda: self.proc.stderr.read(4096), ''):
                self._stderr.append(chunk)
        except (OSError, ValueError):
            pass

    def _fail_pending(self, message):
        with self._lock:
            self._failure = {'code': 'transport_error', 'message': message}
            pending, self._pending = self._pending, {}
            for request in pending.values():
                request._receive({'error': self._failure})

    def _read_stdout(self):
        try:
            for line in self.proc.stdout:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError('Native response must be an object')
                event = 'event' in message
                rid = message.get('request_id' if event else 'id')
                if type(rid) is not int:
                    raise ValueError('Native response has an invalid request ID')
                if not event and 'result' not in message and not isinstance(message.get('error'), dict):
                    raise ValueError('Native response has no result or error')
                with self._lock:
                    request = self._pending.get(rid)
                    if request is None:
                        # An obsolete/duplicate message must not corrupt another
                        # request, especially a new analysis after cancellation.
                        continue
                    request._receive(message)
                    if not event:
                        del self._pending[rid]
            self._stderr_reader.join(timeout=0.2)
            self._fail_pending('Native engine exited: ' + ''.join(self._stderr).strip())
        except (OSError, ValueError, TypeError) as error:
            self._fail_pending('Native engine transport failed: ' + str(error))

    def submit(self, method, params=None, progress=None):
        """Write one request atomically and return its ID-bearing wait handle."""
        with self._write_lock:
            with self._lock:
                if self._closed:
                    raise CoreError({'code': 'transport_error', 'message': 'Native engine is closed'})
                if self._failure is not None:
                    raise CoreError(self._failure)
                self.seq += 1
                request = CoreRequest(self.seq, method, progress)
                payload = json.dumps({'id': request.request_id, 'method': method,
                                      'params': {} if params is None else params}) + '\n'
                self._pending[request.request_id] = request
            # A full stdin pipe must not prevent the reader from draining stdout.
            try:
                self.proc.stdin.write(payload)
                self.proc.stdin.flush()
            except (OSError, ValueError) as error:
                with self._lock:
                    self._pending.pop(request.request_id, None)
                raise CoreError({'code': 'transport_error', 'message': str(error)},
                                request.request_id) from error
            return request

    def call(self, method, params=None, progress=None):
        """Backwards-compatible synchronous request, safe alongside other calls."""
        return self.submit(method, params, progress).result()

    def cancel_analysis(self, request_id):
        """Request cooperative cancellation; never terminate the child process."""
        return self.call('cancel_analysis', {'request_id': request_id})

    def close(self):
        """Cancel pending analyses, drain exports, and reap the owned process.

        An in-flight export can delay shutdown; it is never force-killed by this
        cleanup path. Callers that need EOF/drain semantics must await accepted
        requests before closing the client.
        """
        with self._write_lock:
            with self._lock:
                if self._closed:
                    return
                self._closed = True
                analyses = [rid for rid, request in self._pending.items()
                            if request.method == 'analyze']
            try:
                # EOF itself drains the native FIFO. Explicitly cancel only
                # analysis work, allowing queued exports to resolve normally.
                for rid in analyses:
                    self.seq += 1
                    self.proc.stdin.write(json.dumps({'id': self.seq, 'method': 'cancel_analysis',
                                                      'params': {'request_id': rid}}) + '\n')
                self.proc.stdin.close()
            except OSError:
                pass
        while True:
            try:
                self.proc.wait(timeout=3)
                break
            except subprocess.TimeoutExpired:
                with self._lock:
                    exporting = any(request.method == 'export' for request in self._pending.values())
                if exporting:
                    continue  # Never interrupt a write transaction to close faster.
                self.proc.kill()
                self.proc.wait()
                break
        self._reader.join()
        self._stderr_reader.join()
        self.proc.stdout.close()
        self.proc.stderr.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == '__main__':
    with Core() as core:
        if len(sys.argv) > 1:
            print(json.dumps(core.call(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}),
                             ensure_ascii=False, indent=2))
        else:
            for line in sys.stdin:
                request = json.loads(line)
                try:
                    response = {'id': request.get('id'),
                                'result': core.call(request['method'], request.get('params'))}
                except CoreError as error:
                    response = {'id': request.get('id'), 'error': error.error}
                print(json.dumps(response, ensure_ascii=False), flush=True)
