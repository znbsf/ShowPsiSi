"""Real-engine test proxy: hold only the Use-snapshot query terminal for a UI handshake."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

root = Path(os.environ['SHOWPSISI_QUERY_GATE'])
trace = Path(os.environ['SHOWPSISI_TRACE'])
backend = subprocess.Popen([os.environ['SHOWPSISI_REAL_CORE'], *sys.argv[1:]],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                           encoding='utf-8', bufsize=1)
held_id = None
stopping = threading.Event()


def responses():
    for line in backend.stdout:
        message = json.loads(line)
        if message.get('id') == held_id and held_id is not None:
            root.with_suffix('.held').write_text(json.dumps(message), encoding='utf-8')
            deadline = time.monotonic() + 15
            while not root.with_suffix('.release').exists() and not stopping.is_set():
                if time.monotonic() > deadline:
                    raise RuntimeError('UI did not acknowledge the pending snapshot query')
                time.sleep(0.01)
        print(line, end='', flush=True)


threading.Thread(target=responses, daemon=True).start()
try:
    for line in sys.stdin:
        request = json.loads(line)
        if request['method'] == 'query' and trace.exists() and 'comparison_use_snapshot_requested' in trace.read_text(encoding='utf-8'):
            held_id = request['id']
        if request['method'] == 'analyze' and held_id is not None and not root.with_suffix('.release').exists():
            root.with_suffix('.premature').write_text(line, encoding='utf-8')
        backend.stdin.write(line)
        backend.stdin.flush()
finally:
    stopping.set()
    backend.terminate()
    try:
        backend.wait(timeout=5)
    except subprocess.TimeoutExpired:
        backend.kill()
        backend.wait(timeout=5)
