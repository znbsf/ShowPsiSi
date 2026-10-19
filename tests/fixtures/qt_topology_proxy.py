"""Real-engine response ordering fixture. Never fabricate semantic data."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

child = subprocess.Popen([os.environ['SHOWPSISI_REAL_CORE'], '--root', os.environ['SHOWPSISI_ROOT']],
                         stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=sys.stderr,
                         text=True,encoding='utf-8',bufsize=1)
requests, lock, output_lock = {}, threading.Lock(), threading.Lock()
held, consumed, count = None, False, 0
mode = os.environ['SHOWPSISI_TOPOLOGY_PROXY']

def send(line):
    with output_lock:
        sys.stdout.write(line);sys.stdout.flush()

def receive():
    global held, consumed, count
    for line in child.stdout:
        message=json.loads(line)
        with lock:
            request=requests.get(message.get('id'),{})
        if mode.startswith('dvbi_'):
            target='query_dvbi' if mode in ('dvbi_query_error','dvbi_delay_query') else 'inspect_dvbi'
            if request.get('method')==target and ('result' in message or 'error' in message) and not consumed:
                consumed=True
                if mode=='dvbi_delay_query':
                    gate=Path(os.environ['SHOWPSISI_TOPOLOGY_GATE']);gate.write_text(json.dumps({'held':request}),encoding='utf-8')
                    deadline=time.monotonic()+15
                    while not gate.with_suffix('.release').exists() and time.monotonic()<deadline:time.sleep(.02)
                    send(line);continue
                if mode=='dvbi_disconnect':
                    child.terminate();child.wait(5);os._exit(0)
                if mode=='dvbi_mismatch' and 'result' in message:
                    message['result']['document_revision']+=1
                    send(json.dumps(message)+'\n');continue
                send(json.dumps({'id':message['id'],'error':{'code':'fixture_read_failure','message':'Injected document read failure'}})+'\n');continue
            send(line);continue
        relevant=(request.get('method')=='query_topology' if mode in ('topology','error','disconnect') else
                  request.get('method')=='inspect' and 'analysis_revision' in request.get('params',{}))
        terminal='result' in message or 'error' in message
        if relevant and terminal and mode=='disconnect':
            child.terminate();child.wait(5);os._exit(0)
        if relevant and terminal and mode=='error':
            count+=1
            if count==2:
                send(json.dumps({'id':message['id'],'error':{'code':'fixture_read_failure','message':'Injected topology read failure'}})+'\n')
                continue
            send(line)
            continue
        if relevant and terminal and not consumed:
            held=line;consumed=True
            Path(os.environ['SHOWPSISI_TOPOLOGY_GATE']).write_text(json.dumps({'held':request}),encoding='utf-8')
            continue
        send(line)
        if relevant and terminal and held:
            send(held);held=None

reader=threading.Thread(target=receive,daemon=True);reader.start()
try:
    for line in sys.stdin:
        message=json.loads(line)
        with lock:requests[message['id']]=message
        child.stdin.write(line);child.stdin.flush()
finally:
    child.stdin.close()
    try:child.wait(5)
    except subprocess.TimeoutExpired:child.terminate();child.wait(5)
    reader.join(2)
