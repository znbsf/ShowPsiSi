#!/usr/bin/env python3
"""Local browser validation bridge to the real JSONL engine; NOT a Tauri emulator.

Run: SHOWPSISI_CORE=/path/to/showpsisi-core python scripts/cloud_preview.py
Only loopback is bound. One browser/session per process. Exact web assets are served;
index.html alone receives a small transport adapter. Native dialogs are unsupported.
Read paths are local; export is confined to the supplied output directory. No uploads.
"""
import argparse
from collections import deque
import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'ui/tauri/web'
ADAPTER = r'''<script>
(() => {
 const token = TOKEN, listeners = new Set(); let cursor = 0, polling = false;
 async function rpc(command, args={}) {
  const response = await fetch('/__bridge/invoke', {method:'POST',headers:{'Content-Type':'application/json','X-ShowPsiSi-Token':token},body:JSON.stringify({command,args})});
  const value = await response.json(); if(!response.ok) throw new Error(value.error); return value;
 }
 async function poll() {
  if(polling) return; polling=true;
  while(listeners.size) {
   try {
    const response=await fetch('/__bridge/events?after='+cursor,{headers:{'X-ShowPsiSi-Token':token}});
    if(!response.ok) throw new Error('Browser bridge disconnected');
    const batch=await response.json();
    for(const item of batch.messages){cursor=item.seq;for(const fn of listeners)fn({payload:item.payload});}
   } catch(error){ console.error(error); break; }
  }
  polling=false;
 }
 window.__TAURI__={core:{invoke:rpc},event:{listen:async(name,fn)=>{
  if(name!=='core-message')throw new Error('Unsupported browser event: '+name);
  listeners.add(fn);poll();return ()=>listeners.delete(fn);
 }}};
})();
</script>'''

class Bridge:
    def __init__(self, output, sample=None, executable=None):
        self.output = Path(output).resolve()
        (self.output / 'artifacts').mkdir(parents=True, exist_ok=True)
        self.sample = str(Path(sample or ROOT / 'samples/generated/lab.ts').resolve())
        executable = executable or os.environ.get('SHOWPSISI_CORE') or str(ROOT / 'build/bin' / ('showpsisi-core.exe' if os.name == 'nt' else 'showpsisi-core'))
        self.proc = subprocess.Popen([executable, '--root', str(ROOT)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        self.token = secrets.token_urlsafe(32)
        self.condition = threading.Condition()
        self.write_lock = threading.Lock()
        self.messages = deque(maxlen=512)
        self.seq = 0
        self.closed = False
        self.stderr = deque(maxlen=100)
        self.milestones = []
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._errors, daemon=True).start()

    def _read(self):
        for line in self.proc.stdout:
            try: value = json.loads(line)
            except ValueError: continue
            with self.condition:
                self.seq += 1
                self.messages.append({'seq':self.seq, 'payload':value})
                self.condition.notify_all()
        with self.condition:
            self.seq += 1
            self.messages.append({'seq':self.seq,'payload':{'event':'backend_exit','error':'Native backend stopped. Restart the application.'}})
            self.closed = True
            self.condition.notify_all()

    def _errors(self):
        for line in self.proc.stderr: self.stderr.append(line.rstrip())

    def invoke(self, command, args):
        if command == 'environment':
            return dict(root=str(self.output), sample=self.sample, auto='', delay='0', runtime='cloud-browser', backend_alive=not self.closed and self.proc.poll() is None, driver='Cloud browser / native JSONL', script='')
        if command == 'milestone':
            with self.condition:
                self.milestones.append({'event':str(args.get('event',''))[:100], 'time':time.monotonic()})
                self.milestones[:] = self.milestones[-100:]
            return None
        if command.startswith('plugin:dialog'):
            raise ValueError('Native file dialogs are unavailable in cloud browser validation. Enter a local TS file path instead.')
        if command != 'request': raise ValueError('Unsupported bridge command')
        message = args.get('message')
        if not isinstance(message, dict) or set(message) - {'id','method','params'}: raise ValueError('Invalid JSONL request')
        if message.get('method') not in {'capabilities','lookup_identifier','lookup_satellite','analyze','cancel_analysis','pause_analysis','resume_analysis','query_result','query','query_service','query_carousel','query_timing','query_transport','query_packet','query_topology','query_dvbi','inspect_dvbi','import_dvbi','inspect','diff_snapshots','load_extension','preview_rename','export'}: raise ValueError('Unknown engine method')
        params = message.get('params', {})
        if not isinstance(params, dict): raise ValueError('Parameters must be an object')
        if message['method'] == 'export':
            path = Path(params.get('path','')).resolve()
            if not path.is_relative_to(self.output / 'artifacts'): raise ValueError('Browser exports must stay inside the validation artifacts directory')
        with self.write_lock:
            if self.closed or self.proc.poll() is not None: raise ValueError('Native engine exited: ' + '\n'.join(self.stderr))
            self.proc.stdin.write(json.dumps(message, ensure_ascii=False)+'\n')
            self.proc.stdin.flush()
        return None

    def close(self):
        with self.write_lock:
            self.proc.stdin.close()
        try: self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill(); self.proc.wait()
        self.proc.stdout.close(); self.proc.stderr.close()

class Server(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, bridge, port=0):
        self.bridge = bridge
        super().__init__(('127.0.0.1',port), Handler)
    @property
    def url(self): return 'http://127.0.0.1:'+str(self.server_port)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def respond(self, code, data, content_type='application/json'):
        if not isinstance(data, bytes): data=json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers()
        try: self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError): pass
    def authorized(self, token=False):
        expected = urlsplit(self.server.url).netloc
        if self.headers.get('Host') != expected: return False
        if self.headers.get('Origin') not in (None,self.server.url): return False
        if token and self.headers.get('X-ShowPsiSi-Token') != self.server.bridge.token: return False
        return True
    def do_GET(self):
        if not self.authorized(): return self.respond(403,{'error':'Local origin required'})
        url = urlsplit(self.path)
        if url.path == '/__bridge/events':
            if not self.authorized(True): return self.respond(403,{'error':'Bridge token required'})
            try: after=int(parse_qs(url.query).get('after',['0'])[0])
            except ValueError: return self.respond(400,{'error':'Invalid cursor'})
            bridge=self.server.bridge
            with bridge.condition:
                bridge.condition.wait_for(lambda: bridge.seq>after or bridge.closed,timeout=15)
                if bridge.messages and after < bridge.messages[0]['seq']-1: return self.respond(409,{'error':'Event buffer expired; reload'})
                messages=[m for m in bridge.messages if m['seq']>after]
                if bridge.closed and not messages: return self.respond(503,{'error':'Native engine exited'})
            return self.respond(200,{'messages':messages})
        name = 'index.html' if url.path == '/' else url.path.lstrip('/')
        if name not in {'index.html','app.js','dvbi.js','workbench.js','style.css','inspector-model.js','unified-si.js','unified-si.css','transport-si.js','carousel-model.js','carousel-view.js','service-model.js','service-view.js','statistics-view.js','packet-model.js','packet-explorer.js','document-model.js','document-workspace.js','classic-model.js','classic-frame.js','assets/toolbar128.bmp'}: return self.respond(404,{'error':'Not found'})
        payload = (WEB/name).read_bytes()
        if name == 'index.html':
            payload=payload.replace(b'<head>',b'<head>'+ADAPTER.replace('TOKEN',json.dumps(self.server.bridge.token)).encode(),1)
        self.respond(200,payload,mimetypes.guess_type(name)[0] or 'application/octet-stream')
    def do_POST(self):
        if not self.authorized(True): return self.respond(403,{'error':'Local origin and bridge token required'})
        if self.path != '/__bridge/invoke': return self.respond(404,{'error':'Not found'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=65536: return self.respond(413,{'error':'Request size must be 1–65536 bytes'})
            body=json.loads(self.rfile.read(size))
            if not isinstance(body,dict) or not isinstance(body.get('args',{}),dict): raise ValueError('Invalid request')
            result=self.server.bridge.invoke(body.get('command',''),body.get('args',{}))
            self.respond(200,result)
        except (ValueError,TypeError,KeyError,OSError) as error: self.respond(400,{'error':str(error)})

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--output',type=Path,default=ROOT/'artifacts/cloud-preview')
    parser.add_argument('--sample',type=Path)
    args=parser.parse_args()
    bridge=Bridge(args.output,args.sample)
    server=Server(bridge,args.port)
    print(server.url+' (browser validation, not native Tauri; Ctrl-C to stop)',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close(); bridge.close()

if __name__ == '__main__': main()
