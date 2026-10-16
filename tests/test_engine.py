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
    def test_failed_analysis_discards_evidence_and_preview(self):
        for name,raw in [('missing.ts',None),('tiny.ts',b'x'),('invalid.ts',b'x'*940)]:
            with self.subTest(name=name):
                state=self.core.call('analyze',{'path':str(ROOT/'samples/generated/lab.ts')})
                service=state['services'][0]
                edit=self.core.call('preview_rename',{'id':service['source_id'],'service_id':service['id'],'name':'Old edit'})
                path=self.output(name)
                if raw is not None:Path(path).write_bytes(raw)
                with self.assertRaises(RuntimeError):self.core.call('analyze',{'path':path})
                failed=self.core.call('query')
                self.assertFalse(failed['complete']);self.assertEqual(failed['tables'],[]);self.assertEqual(failed['services'],[])
                self.assertGreater(failed['revision'],state['revision'])
                with self.assertRaisesRegex(RuntimeError,'Unknown section'):self.core.call('inspect',{'id':service['source_id']})
                with self.assertRaisesRegex(RuntimeError,'successful analysis'):self.core.call('export',{'path':self.output(name+'.bin'),'format':'bin','preview_token':edit['token']})
                with self.assertRaisesRegex(RuntimeError,'successful analysis'):self.core.call('preview_rename',{'id':service['source_id'],'service_id':service['id'],'name':'Bad'})
                self.assertFalse(Path(self.output(name+'.bin')).exists())

    def test_pmt_binding_follows_pat_pid_and_transport_stream(self):
        from make_fixture import section,descriptor,word
        def pat(version,pid):return section(0,1,version,word(101)+word(0xe000+pid))
        def pmt(pid):return section(2,101,1,word(0xe000+pid)+word(0xf000))
        def sdt(tsid):
            desc=descriptor(0x48,b'\x01\x00\x04Test')
            return section(0x42,tsid,1,word(2)+b'\xff'+word(101)+b'\xff'+word(0x8000+len(desc))+desc)
        parts=[(0,pat(1,0x100)),(0x100,pmt(0x200)),(0x11,sdt(1)),
               (0,pat(2,0x101)),(0x101,pmt(0x201)),(0x100,pmt(0x200)),(0x11,sdt(2))]
        counters={};packets=[]
        for pid,raw in parts:
            cc=counters.get(pid,0);counters[pid]=cc+1
            packets.append(bytes([0x47,0x40|(pid>>8),pid&255,0x10|cc,0])+raw+b'\xff'*(183-len(raw)))
        path=self.output('pmt-remap.ts');Path(path).write_bytes(b''.join(packets));self.core.call('analyze',{'path':path})
        def service(at,tsid=1):return next(s for s in self.core.call('query',{'at_packet':at})['services'] if s['ts_id']==tsid)
        self.assertEqual(service(2)['components']['pcr_pid'],0x200)
        self.assertEqual(service(3)['pmt_pid'],0x101);self.assertNotIn('components',service(3))
        self.assertEqual(service(5)['components']['pcr_pid'],0x201)
        self.assertIsNone(service(6,2)['pmt_pid']);self.assertNotIn('components',service(6,2))

    def test_extension_validation_is_atomic_and_rescan_scoped(self):
        extension=json.loads((ROOT/'extensions/demo.json').read_text())
        extension['id']='next-extension';extension['organization']['sort_by']='name'
        path=self.output('next.json');Path(path).write_text(json.dumps(extension))
        self.core.call('load_extension',{'path':path})
        before=self.core.call('query');self.assertEqual(before['extension_id'],self.state['extension_id']);self.assertEqual(before['services'],self.state['services'])
        for field,value in [('extra_pids',[-1]),('extra_pids',[8192]),('descriptors',[{}]),('organization',[]),('id',7)]:
            invalid=dict(extension);invalid[field]=value;Path(path).write_text(json.dumps(invalid))
            with self.subTest(field=field,value=value),self.assertRaisesRegex(RuntimeError,'Invalid extension'):self.core.call('load_extension',{'path':path})
        parsed=self.core.call('analyze',{'path':str(ROOT/'samples/generated/lab.ts')})
        self.assertEqual(parsed['extension_id'],'next-extension');self.assertEqual(parsed['services'][0]['name'],'Cinema')

    def test_extension_rejects_reserved_fields_and_scope_conflicts(self):
        import copy
        base=json.loads((ROOT/'extensions/demo.json').read_text())
        path=self.output('invalid-fields.json')
        for name in ['id','source_id','ts_id','onid','service_id','encrypted','name','pmt_pid','components','title','start','duration_seconds']:
            invalid=copy.deepcopy(base);invalid['descriptors'][0]['fields'][0]['name']=name
            Path(path).write_text(json.dumps(invalid))
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'reserved'):
                self.core.call('load_extension',{'path':path})
        invalid=copy.deepcopy(base);invalid['descriptors'].append(copy.deepcopy(invalid['descriptors'][0]))
        invalid['descriptors'][1]['table_ids']=[0x46];invalid['descriptors'][1]['fields'][0]['offset']=2;invalid['descriptors'][1]['fields'][0]['type']='u8'
        Path(path).write_text(json.dumps(invalid))
        with self.assertRaisesRegex(RuntimeError,'conflicting descriptor'):self.core.call('load_extension',{'path':path})
        invalid=copy.deepcopy(base);invalid['descriptors'][0]['fields'][1]['name']='logical_channel_number'
        Path(path).write_text(json.dumps(invalid))
        with self.assertRaisesRegex(RuntimeError,'duplicate field'):self.core.call('load_extension',{'path':path})
        parsed=self.core.call('analyze',{'path':str(ROOT/'samples/generated/lab.ts')})
        service=parsed['services'][0];self.assertEqual(service['logical_channel_number'],10)
        self.assertIsInstance(service['source_id'],str);self.assertEqual(self.core.call('inspect',{'id':service['source_id']})['id'],service['source_id'])

    def test_rename_utf8_byte_boundaries(self):
        service=self.state['services'][0]
        def preview(name):return self.core.call('preview_rename',{'id':service['source_id'],'service_id':service['id'],'name':name})
        self.assertEqual(preview('A'*180)['after'],'A'*180)
        for name in ['A'*181,'中'*61,'😀'*46]:
            with self.subTest(bytes=len(name.encode('utf-8'))),self.assertRaisesRegex(RuntimeError,'180 UTF-8 bytes'):preview(name)
        name='中'*60;edit=preview(name)
        result=self.core.call('export',{'path':self.output('unicode-boundary.ts'),'preview_token':edit['token'],'cycles':1,'null_packets':0})
        parsed=self.core.call('analyze',{'path':result['path']});self.assertEqual(parsed['services'][0]['name'],name)
        schema=next(t for t in self.core.call('capabilities')['tools'] if t['name']=='preview_rename')['inputSchema']['properties']['name']
        self.assertEqual(schema['x-maxUtf8Bytes'],180)

    def test_empty_snapshot_export_is_rejected(self):
        from make_fixture import section,word
        null=bytes([0x47,0x1f,0xff,0x10])+b'\xff'*184
        raw=section(0,1,1,word(101)+word(0xe100))
        path=self.output('late-pat.ts');Path(path).write_bytes(null+bytes([0x47,0x40,0,0x10,0])+raw+b'\xff'*(183-len(raw)))
        self.core.call('analyze',{'path':path})
        with self.assertRaisesRegex(RuntimeError,'No valid current sections'):self.core.call('export',{'path':self.output('empty.bin'),'format':'bin','at_packet':0})
        self.assertFalse(Path(self.output('empty.bin')).exists())

    def test_additional_si_tables_have_structured_fields(self):
        from make_fixture import section,descriptor,word,crc
        import datetime
        name=descriptor(0x40,b'Lab network')
        transport=word(1)+word(2)+word(0xf000)
        nit=section(0x40,77,1,word(0xf000+len(name))+name+word(0xf000+len(transport))+transport)
        bat=section(0x4a,88,1,word(0xf000)+word(0xf000+len(transport))+transport)
        cat=section(1,1,1,descriptor(9,b'\x01\x00\xe1\x00'))
        mjd=(datetime.date(2026,10,17)-datetime.date(1858,11,17)).days
        utc=word(mjd)+bytes([0x09,0,0]);tdt=b'\x70\x70\x05'+utc
        tot=b'\x73\x70\x0b'+utc+word(0xf000);tot+=crc(tot).to_bytes(4,'big')
        pairs=[(0x10,nit),(0x11,bat),(1,cat),(0x14,tdt),(0x14,tot)];counts={};packets=[]
        for pid,raw in pairs:
            cc=counts.get(pid,0);counts[pid]=cc+1
            packets.append(bytes([0x47,0x40|(pid>>8),pid&255,0x10|cc,0])+raw+b'\xff'*(183-len(raw)))
        path=self.output('si-tables.ts');Path(path).write_bytes(b''.join(packets))
        result=self.core.call('analyze',{'path':path})
        details={t['table_id']:self.core.call('inspect',{'id':t['id']}) for t in result['tables']}
        self.assertEqual(details[0x40]['fields']['network_id'],77)
        self.assertEqual(details[0x40]['fields']['transports'][0]['transport_stream_id'],1)
        self.assertEqual(details[0x4a]['fields']['bouquet_id'],88)
        self.assertEqual(details[1]['descriptors'][0]['tag'],9)
        self.assertIn('2026',details[0x70]['fields']['utc_time']);self.assertEqual(details[0x70]['fields'],details[0x73]['fields'])
        self.assertEqual(result['diagnostics'],[])

    def test_regional_time_profiles_reset_between_scans(self):
        from make_fixture import word
        import datetime
        mjd=(datetime.date(2026,10,17)-datetime.date(1858,11,17)).days
        raw=b'\x70\x70\x05'+word(mjd)+bytes([0x09,0,0])
        path=self.output('regional-tdt.ts');Path(path).write_bytes(bytes([0x47,0x40,0x14,0x10,0])+raw+b'\xff'*(183-len(raw)))
        for profile,hour,charset in [('isdb-japan','00:00:00','ARIB'),('isdb-brazil','12:00:00','8859-15'),('dvb','09:00:00','ISO-6937')]:
            with self.subTest(profile=profile):
                state=self.core.call('analyze',{'path':path,'standards':profile})
                detail=self.core.call('inspect',{'id':state['tables'][0]['id']})
                self.assertIn(hour,detail['fields']['utc_time']);self.assertIn(hour,detail['native_table']['attributes']['utc_time']);self.assertIn(charset,state['text_charset'])

    def test_native_catalog_tree_and_verified_references(self):
        catalog=self.core.call('capabilities')['native_registry']
        self.assertEqual(catalog['table_count'],len(catalog['table_names']));self.assertEqual(catalog['descriptor_count'],len(catalog['descriptor_names']))
        self.assertIn('PAT',catalog['table_names']);self.assertIn('satellite_delivery_system_descriptor',catalog['descriptor_names'])
        state=self.core.call('analyze',{'path':str(ROOT/'samples/generated/lab.ts'),'standards':'dvb'})
        details=self.core.call('inspect',{'id':state['services'][0]['source_id']})
        self.assertTrue(details['native_table_complete']);self.assertEqual(details['native_table']['name'],'SDT')
        self.assertTrue(details['references']);self.assertEqual(details['reference_warnings'],[])
        service_descriptor=next(d for d in details['descriptors'] if d['tag']==0x48)
        self.assertEqual(service_descriptor['native']['name'],'service_descriptor');self.assertTrue(service_descriptor['references'])
        for reference in details['references']+service_descriptor['references']:
            self.assertTrue(reference['url'].startswith('https://'));self.assertEqual(reference['scope'],'standard-level')

    def test_optional_reference_index_failure_preserves_inspection(self):
        import shutil
        root=Path(self.tmp.name)/'alternate-root';(root/'api').mkdir(parents=True);(root/'references').mkdir()
        shutil.copy(ROOT/'api/tools.json',root/'api/tools.json');(root/'references/standards.json').write_text('{broken')
        requests=[{'id':1,'method':'analyze','params':{'path':str(ROOT/'samples/generated/lab.ts'),'standards':'dvb'}},
                  {'id':2,'method':'inspect','params':{'id':self.state['services'][0]['source_id']}}]
        run=subprocess.run([self.core.proc.args[0],'--root',str(root)],input=''.join(json.dumps(r)+'\n' for r in requests),capture_output=True,text=True,encoding='utf-8',check=True)
        result=next(json.loads(line)['result'] for line in run.stdout.splitlines() if json.loads(line).get('id')==2)
        self.assertTrue(result['native_table_complete']);self.assertEqual(result['references'],[]);self.assertTrue(result['reference_warnings']);self.assertIn('raw_hex',result)

    def test_competing_exports_never_overwrite(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        other=Core()
        try:
            other.call('analyze',{'path':str(ROOT/'samples/generated/lab.ts')})
            barrier=Barrier(2);path=self.output('contested.ts')
            def export(core):
                barrier.wait()
                try:return core.call('export',{'path':path,'cycles':1000,'null_packets':0})
                except RuntimeError:return None
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(export,c) for c in (self.core,other)]
                outcomes=[f.result() for f in futures]
            winners=[r for r in outcomes if r is not None];self.assertEqual(len(winners),1)
            receipt=json.loads(Path(path+'.manifest.json').read_text())
            self.assertEqual(receipt,winners[0]);self.assertEqual(Path(path).stat().st_size,receipt['bytes'])
        finally:other.close()

    def test_192_and_204_byte_framing(self):
        from make_fixture import section,word
        raw=section(0,1,1,word(101)+word(0xe100))
        packet=bytes([0x47,0x40,0,0x10,0])+raw+b'\xff'*(183-len(raw))
        for size,framed in [(192,b'\x00'*4+packet),(204,packet+b'\x00'*16)]:
            with self.subTest(size=size):
                path=self.output(str(size)+'.ts');Path(path).write_bytes(framed*6)
                result=self.core.call('analyze',{'path':path});self.assertEqual(result['packet_size'],size);self.assertEqual(result['packets'],6)
                details=self.core.call('inspect',{'id':result['tables'][0]['id']});self.assertEqual(details['first_file_offset'],4 if size==192 else 0)

    def test_machine_argument_validation(self):
        with self.assertRaisesRegex(RuntimeError,'Below minimum'):self.core.call('query',{'at_packet':-1})
        with self.assertRaisesRegex(RuntimeError,'Unknown argument'):self.core.call('query',{'timestamp':0})
        with self.assertRaisesRegex(RuntimeError,'Wrong type'):self.core.call('inspect',{'id':123})

if __name__=='__main__':unittest.main(verbosity=2)
