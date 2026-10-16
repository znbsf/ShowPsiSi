"""Transport safety tests using a real native JSONL process, without a browser."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from cloud_preview import Bridge, Server

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='showpsisi-bridge-')
        self.addCleanup(self.tmp.cleanup)
        self.bridge=Bridge(self.tmp.name)
        self.addCleanup(self.bridge.close)
        self.server=Server(self.bridge)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
    def request(self,path,body=None,headers=None):
        headers={'X-ShowPsiSi-Token':self.bridge.token,**(headers or {})}
        request=Request(self.server.url+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        return urlopen(request,timeout=20)
    def invoke(self,command,args=None):
        with self.request('/__bridge/invoke',{'command':command,'args':args or {}}) as response:return json.load(response)
    def test_real_engine_capabilities(self):
        self.invoke('request',{'message':{'id':1,'method':'capabilities','params':{}}})
        with self.request('/__bridge/events?after=0') as response:batch=json.load(response)
        message=next(item['payload'] for item in batch['messages'] if item['payload'].get('id')==1)
        self.assertEqual(message['result']['name'],'ShowPsiSi')
        self.assertTrue(message['result']['tools'])
    def test_engine_exit_event_and_startup_state(self):
        self.assertTrue(self.invoke('environment')['backend_alive'])
        self.bridge.proc.kill()
        self.bridge.proc.wait(timeout=5)
        with self.request('/__bridge/events?after=0') as response:batch=json.load(response)
        event=next(item['payload'] for item in batch['messages'] if item['payload'].get('event')=='backend_exit')
        self.assertIn('Restart the application',event['error'])
        self.assertFalse(self.invoke('environment')['backend_alive'])
        with self.assertRaises(HTTPError) as error:self.invoke('request',{'message':{'id':1,'method':'capabilities','params':{}}})
        self.assertEqual(error.exception.code,400)

    def test_static_assets_and_environment(self):
        for name in ('app.js','style.css'):
            with self.request('/'+name) as response:self.assertEqual(response.read(),(ROOT/'ui/tauri/web'/name).read_bytes())
        with self.request('/') as response:
            index=response.read().decode();self.assertIn('window.__TAURI__',index)
        env=self.invoke('environment');self.assertEqual(env['runtime'],'cloud-browser')
        self.assertEqual(Path(env['root']),Path(self.tmp.name))
    def test_auth_origin_paths_and_dialog(self):
        for path,headers in [('/__bridge/events',{'X-ShowPsiSi-Token':'bad'}),('/',{'Host':'attacker.example'}),('/',{'Origin':'https://attacker.example'})]:
            with self.assertRaises(HTTPError) as error:self.request(path,headers=headers)
            self.assertEqual(error.exception.code,403)
        with self.assertRaises(HTTPError) as error:self.request('/../api/schema.json')
        self.assertEqual(error.exception.code,404)
        with self.assertRaises(HTTPError) as error:self.invoke('plugin:dialog|open')
        self.assertIn('Native file dialogs',error.exception.read().decode())
        with self.assertRaises(HTTPError) as error:self.invoke('request',{'message':{'id':1,'method':'export','params':{'path':str(ROOT/'samples/generated/lab.ts')}}})
        self.assertIn('validation artifacts directory',error.exception.read().decode())

if __name__=='__main__':unittest.main(verbosity=2)
