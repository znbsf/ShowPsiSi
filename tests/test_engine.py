import json, sys, unittest, tempfile, hashlib, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core

class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='showpsisi-');self.core=Core();self.state=self.core.call('analyze',{'path':str(ROOT/'samples/generated/lab.ts')})
    def tearDown(self):self.core.close();self.tmp.cleanup()
    def output(self,name):return str(Path(self.tmp.name)/name)
    def test_observations_errors_and_private_data(self):
        s=self.state;self.assertEqual(len(s['services']),6);self.assertEqual(s['crc_errors'],2);self.assertEqual([h['version'] for h in s['history']],[1,2,3]);self.assertEqual(s['services'][0]['name'],'Sports UHD');self.assertEqual(s['services'][0]['logical_channel_number'],10)
        self.assertEqual({x['code'] for x in s['diagnostics']},{'crc32','descriptor_length'})
        d=self.core.call('inspect',{'id':s['services'][0]['source_id']});self.assertTrue(any(x['tag']==226 and x['raw']=='E204CAFEBABE' for x in d['descriptors']));self.assertTrue(any(x.get('extension') for x in d['descriptors']));self.assertGreater(len(d['occurrences']),10)
    def test_time_snapshot(self):
        old=self.core.call('query',{'at_packet':self.state['history'][0]['last_packet']});self.assertEqual(old['services'][0]['name'],'World News');self.assertEqual(next(x for x in old['services'] if x['id']==103)['name'],'Sports HD')
    def test_extension_scope_and_organization(self):
        ext=json.loads((ROOT/'extensions/demo.json').read_text());ext['descriptors'][0]['pds']=1
        p=self.output('extension.json');Path(p).write_text(json.dumps(ext));self.core.call('load_extension',{'path':p});s=self.core.call('analyze',{'path':str(ROOT/'samples/generated/lab.ts')});self.assertIsNone(s['services'][0]['logical_channel_number']);self.assertEqual(s['services'][0]['id'],101);self.assertEqual(s['services'][0]['group'],'Unassigned')
        ext['descriptors'][0]['pds']=0x53505349;ext['organization']['sort_by']='name';Path(p).write_text(json.dumps(ext));self.core.call('load_extension',{'path':p});s=self.core.call('analyze',{'path':str(ROOT/'samples/generated/lab.ts')});self.assertEqual(s['services'][0]['name'],'Cinema')
    def test_rename_export_reparse_and_preserve_source(self):
        before=hashlib.sha256((ROOT/'samples/generated/lab.ts').read_bytes()).hexdigest();s=self.state['services'][0]
        edit=self.core.call('preview_rename',{'id':s['source_id'],'service_id':s['id'],'name':'AI edited service'})
        r=self.core.call('export',{'path':self.output('edited.ts'),'preview_token':edit['token'],'cycles':3,'null_packets':100})
        self.assertFalse(r['has_media']);self.assertFalse(r['has_pcr']);self.assertTrue(Path(r['path']+'.manifest.json').exists())
        parsed=self.core.call('analyze',{'path':r['path']});self.assertEqual(parsed['crc_errors'],0);self.assertEqual(parsed['demux']['discontinuities'],0);self.assertEqual(parsed['services'][0]['name'],'AI edited service');self.assertEqual(parsed['history'][0]['version'],4)
        self.assertEqual(before,hashlib.sha256((ROOT/'samples/generated/lab.ts').read_bytes()).hexdigest())
    def test_bin_manifest_and_no_overwrite(self):
        r=self.core.call('export',{'path':self.output('signal.bin'),'format':'bin'});raw=Path(r['path']).read_bytes()
        for section in r['sections']:
            off=section['bin_offset'];self.assertEqual(((raw[off+1]&15)<<8|raw[off+2])+3,section['bytes'])
        with self.assertRaisesRegex(RuntimeError,'already exists'):self.core.call('export',{'path':r['path'],'format':'bin'})
    def test_stale_preview_and_invalid_target(self):
        s=self.state['services'][0];e=self.core.call('preview_rename',{'id':s['source_id'],'service_id':s['id'],'name':'Rename'})
        self.core.call('analyze',{'path':str(ROOT/'samples/generated/lab.ts')})
        with self.assertRaisesRegex(RuntimeError,'stale'):self.core.call('export',{'path':self.output('bad.ts'),'preview_token':e['token']})
        with self.assertRaises(RuntimeError):self.core.call('preview_rename',{'id':self.state['diagnostics'][0]['id'],'service_id':101,'name':'Bad'})
    def test_real_stream_baseline(self):
        p=ROOT/'samples/real/tnt-uhf22-2019.ts'
        if not p.exists():self.skipTest('Optional real sample missing')
        s=self.core.call('analyze',{'path':str(p)});self.assertEqual(s['packets'],978401);self.assertEqual(len(s['services']),12);self.assertEqual(s['services'][0]['name'],'CANAL+');self.assertGreater(len(s['events']),100);self.assertEqual(s['crc_errors'],0)
    def test_mcp_discovery_and_analysis(self):
        p=subprocess.Popen([sys.executable,str(ROOT/'scripts/mcp_server.py')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            def call(i,method,params):
                p.stdin.write(json.dumps({'jsonrpc':'2.0','id':i,'method':method,'params':params})+'\n');p.stdin.flush();return json.loads(p.stdout.readline())['result']
            self.assertEqual(call(1,'initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'test','version':'1'}})['serverInfo']['name'],'ShowPsiSi')
            self.assertEqual(len(call(2,'tools/list',{})['tools']),7)
            r=call(3,'tools/call',{'name':'analyze','arguments':{'path':str(ROOT/'samples/generated/lab.ts')}});self.assertFalse(r['isError']);self.assertEqual(len(r['structuredContent']['services']),6)
            service=r['structuredContent']['services'][0]
            d=call(4,'tools/call',{'name':'inspect','arguments':{'id':service['source_id']}});self.assertIn('raw_hex',d['structuredContent'])
            preview=call(5,'tools/call',{'name':'preview_rename','arguments':{'id':service['source_id'],'service_id':service['id'],'name':'Agent 测试频道'}})['structuredContent']
            exported=call(6,'tools/call',{'name':'export','arguments':{'path':self.output('中文 测试.ts'),'preview_token':preview['token']}})['structuredContent']
            checked=call(7,'tools/call',{'name':'analyze','arguments':{'path':exported['path']}})['structuredContent']
            self.assertEqual(checked['services'][0]['name'],'Agent 测试频道');self.assertEqual(checked['crc_errors'],0)
        finally:p.stdin.close();p.wait(timeout=5);p.stdout.close()
    def test_multisection_generation_and_completion_boundary(self):
        from make_fixture import section,descriptor,word,crc
        def sdt(v,n,name):
            desc=descriptor(0x48,b'\x01\x00'+bytes([len(name)])+name)
            raw=bytearray(section(0x42,1,v,word(2)+b'\xff'+word(100+n)+b'\xff'+word(0x8000+len(desc))+desc));raw[6]=n;raw[7]=1;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big');return bytes(raw)
        parts=[sdt(1,0,b'Old A'),sdt(1,1,b'Old B'),sdt(2,0,b'New A'),sdt(2,1,b'New B')]
        packets=[bytes([0x47,0x40,0x11,0x10+i,0])+b+b'\xff'*(183-len(b)) for i,b in enumerate(parts)]
        p=self.output('two-sections.ts');Path(p).write_bytes(b''.join(packets));self.core.call('analyze',{'path':p})
        self.assertEqual(len(self.core.call('query',{'at_packet':0})['services']),0)
        self.assertEqual([x['name'] for x in self.core.call('query',{'at_packet':1})['services']],['Old A','Old B'])
        self.assertEqual(len(self.core.call('query',{'at_packet':2})['services']),0)
        with self.assertRaisesRegex(RuntimeError,'Incomplete'):self.core.call('export',{'path':self.output('incomplete.bin'),'at_packet':2,'format':'bin'})
        self.assertEqual([x['name'] for x in self.core.call('query',{'at_packet':3})['services']],['New A','New B'])
    def test_machine_argument_validation(self):
        with self.assertRaisesRegex(RuntimeError,'Below minimum'):self.core.call('query',{'at_packet':-1})
        with self.assertRaisesRegex(RuntimeError,'Unknown argument'):self.core.call('query',{'timestamp':0})
        with self.assertRaisesRegex(RuntimeError,'Wrong type'):self.core.call('inspect',{'id':123})

if __name__=='__main__':unittest.main(verbosity=2)
