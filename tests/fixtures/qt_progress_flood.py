"""Transport stress proxy: repeat one genuine core progress frame, not TS evidence.

All terminal results, pages, errors and control acknowledgements are forwarded
unchanged. The input path remains independent of the deliberately noisy stdout.
"""
import json
import os
import subprocess
import sys
import threading

child = subprocess.Popen([os.environ['SHOWPSISI_REAL_CORE'], '--root', os.environ['SHOWPSISI_ROOT']],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
                         text=True, encoding='utf-8', bufsize=1)


def relay():
    flooded = False
    for line in child.stdout:
        message = json.loads(line)
        if not flooded and message.get('event') == 'progress':
            flooded = True
            for _ in range(20000):
                sys.stdout.write(line)
            sys.stdout.flush()
        else:
            sys.stdout.write(line)
            sys.stdout.flush()


thread = threading.Thread(target=relay, daemon=True)
thread.start()
for line in sys.stdin:
    child.stdin.write(line)
    child.stdin.flush()
child.stdin.close()
child.wait()
thread.join()
