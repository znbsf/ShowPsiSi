"""Forward genuine core output; corrupt exactly one bounded page identity/cursor."""
import json
import os
import subprocess
import sys
import threading

child = subprocess.Popen([os.environ['SHOWPSISI_REAL_CORE'], '--root', os.environ['SHOWPSISI_ROOT']],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=sys.stderr,
                         text=True, encoding='utf-8', bufsize=1)


def relay():
    injected = False
    table_pages = 0
    for line in child.stdout:
        message = json.loads(line)
        result = message.get('result', {})
        fault = os.environ['SHOWPSISI_PAGE_FAULT']
        if result.get('collection') == 'tables' and 'items' in result:
            table_pages += 1
        if not injected and result.get('collection') == 'tables' and 'items' in result and (fault != 'error' or table_pages == 2):
            injected = True
            if fault == 'error':
                message.pop('result')
                message['error'] = {'code':'injected_failure', 'message':'Injected continuation page failure'}
            elif fault == 'cutoff':
                result['at_packet'] = 123
            else:
                result['next_offset'] = 0
            line = json.dumps(message) + '\n'
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
