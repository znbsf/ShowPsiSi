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
    def test_transport_query_reaches_native_engine(self):
        self.invoke('request',{'message':{'id':41,'method':'query_transport','params':{'analysis_revision':0,'offset':0,'limit':100}}})
        with self.request('/__bridge/events?after=0') as response:batch=json.load(response)
        message=next(item['payload'] for item in batch['messages'] if item['payload'].get('id')==41)
        self.assertIn('error',message) # No source loaded, but native protocol handled it.
        self.assertNotIn('Unknown engine method',str(message))
    def test_real_engine_capabilities(self):
        self.invoke('request',{'message':{'id':1,'method':'capabilities','params':{}}})
        with self.request('/__bridge/events?after=0') as response:batch=json.load(response)
        message=next(item['payload'] for item in batch['messages'] if item['payload'].get('id')==1)
        self.assertEqual(message['result']['name'],'ShowPsiSi')
        self.assertTrue(message['result']['tools'])
    def test_independent_xml_methods_reach_native_engine(self):
        from dvbi_fixture import fixture,PROFILE
        path=Path(self.tmp.name)/'input.xml';path.write_bytes(fixture())
        cursor=0
        for ident,method,params in [(71,'import_dvbi',{'path':str(path),'profile':PROFILE}),
                                    (72,'query_dvbi',{'document_revision':1,'limit':500}),
                                    (73,'inspect_dvbi',{'document_revision':1,'element_id':'e0','source_limit':40})]:
            self.invoke('request',{'message':{'id':ident,'method':method,'params':params}})
            message=None
            for _ in range(4):
                with self.request('/__bridge/events?after='+str(cursor)) as response:batch=json.load(response)
                for item in batch['messages']:
                    cursor=item['seq']
                    if item['payload'].get('id')==ident:message=item['payload']
                if message:break
            self.assertIsNotNone(message);self.assertNotIn('error',message)
            self.assertEqual(message['result']['source']['kind'],'local_dvbi_xml')

    def test_snapshot_comparison_is_forwarded_to_native_engine(self):
        # The transport must not become a second, outdated API registry.
        # A pre-analysis request should reach the engine and receive its error,
        # rather than fail the bridge's method allowlist.
        self.invoke('request', {'message': {'id': 41, 'method': 'diff_snapshots',
                    'params': {'from_packet': 0, 'to_packet': 1}}})
        cursor = 0
        for _ in range(4):
            with self.request('/__bridge/events?after=' + str(cursor)) as response:
                batch = json.load(response)
            for item in batch['messages']:
                cursor = item['seq']
                if item['payload'].get('id') == 41:
                    self.assertIn('error', item['payload'])
                    self.assertNotIn('Unknown method', item['payload']['error']['message'])
                    return
        self.fail('Native comparison response was not delivered')

    def test_cancellation_request_reaches_native_backend(self):
        self.invoke('request', {'message': {'id': 42, 'method': 'cancel_analysis',
                    'params': {'request_id': 'not-running'}}})
        cursor = 0
        for _ in range(4):
            with self.request('/__bridge/events?after=' + str(cursor)) as response:
                batch = json.load(response)
            for item in batch['messages']:
                cursor = item['seq']
                if item['payload'].get('id') == 42:
                    result = item['payload']['result']
                    self.assertFalse(result['requested'])
                    self.assertEqual(result['reason'], 'not_running')
                    self.assertEqual(result['request_id'], 'not-running')
                    return
        self.fail('Native cancellation acknowledgement was not delivered')

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
        for name in ('app.js','dvbi.js','workbench.js','style.css','inspector-model.js','unified-si.js','unified-si.css','transport-si.js'):
            with self.request('/'+name) as response:self.assertEqual(response.read(),(ROOT/'ui/tauri/web'/name).read_bytes())
        with self.request('/') as response:
            index=response.read().decode();self.assertIn('window.__TAURI__',index)
        env=self.invoke('environment');self.assertEqual(env['runtime'],'cloud-browser')
        self.assertTrue(Path(env['root']).samefile(self.tmp.name))
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
