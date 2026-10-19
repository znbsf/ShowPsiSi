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
            tools=call(2,'tools/list',{})['tools'];self.assertEqual(len(tools),11);self.assertTrue(next(t for t in tools if t['name']=='diff_snapshots')['annotations']['readOnlyHint'])
            self.assertTrue(next(t for t in tools if t['name']=='lookup_identifier')['annotations']['readOnlyHint'])
            r=call(3,'tools/call',{'name':'analyze','arguments':{'path':str(ROOT/'samples/generated/lab.ts')}});self.assertFalse(r['isError']);self.assertEqual(len(r['structuredContent']['services']),6)
            service=r['structuredContent']['services'][0]
            comparison=call(8,'tools/call',{'name':'diff_snapshots','arguments':{'from_packet':0,'to_packet':r['structuredContent']['packets']-1,'limit':1}})['structuredContent']
            self.assertEqual(len(comparison['changes']),1);self.assertIsNotNone(comparison['next_offset'])
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

    def rename_safety_fixture(self, provider=b'Lab', service_descriptor=True, duplicate=False):
        from make_fixture import section,descriptor,word
        def service(sid,desc,flags=0xb000):return word(sid)+b'\xfe'+word(flags+len(desc))+desc
        private=descriptor(0xe2,b'\xca\xfe\xba\xbe')
        desc=descriptor(0x5f,b'\x53\x50\x53\x49')
        if service_descriptor:desc+=descriptor(0x48,bytes([0x19,len(provider)])+provider+b'\x03Old')
        if duplicate:desc+=descriptor(0x48,b'\x01\x00\x06Second')
        desc+=private
        other=descriptor(0x48,b'\x02\x03Lab\x05Other')+private
        raw=section(0x42,1,31,word(2)+b'\xff'+service(101,desc)+service(102,other,0x4000))
        packets=[];first=True;cc=0
        while raw:
            count=183 if first else 184;part=(b'\x00' if first else b'')+raw[:count];raw=raw[count:]
            packets.append(bytes([0x47,0x40 if first else 0,0x11,0x10|cc])+part+b'\xff'*(184-len(part)))
            first=False;cc=(cc+1)&15
        path=Path(self.output('rename-safety.ts'));path.write_bytes(b''.join(packets));return path

    def test_rename_rejects_descriptor_overflow_and_invalidates_old_token(self):
        path=self.rename_safety_fixture(b'P'*100);source=path.read_bytes()
        state=self.core.call('analyze',{'path':str(path),'standards':'dvb'});service=next(s for s in state['services'] if s['id']==101)
        args={'id':service['source_id'],'service_id':101}
        # 3 descriptor fields + 100 provider bytes + 152 name bytes exactly fill 255.
        good=self.core.call('preview_rename',{**args,'name':'A'*152})
        for name in ['A'*153,'A'*180]:
            with self.subTest(length=len(name)),self.assertRaisesRegex(RuntimeError,'losslessly.*capacity'):
                self.core.call('preview_rename',{**args,'name':name})
            with self.assertRaisesRegex(RuntimeError,'stale'):
                self.core.call('export',{'path':self.output('rejected.ts'),'preview_token':good['token']})
        self.assertFalse(Path(self.output('rejected.ts')).exists())
        self.assertEqual(self.core.call('query')['services'],state['services'])
        good=self.core.call('preview_rename',{**args,'name':'A'*152})
        exported=self.core.call('export',{'path':self.output('capacity.ts'),'preview_token':good['token'],'cycles':1,'null_packets':0})
        readback=self.core.call('analyze',{'path':exported['path'],'standards':'dvb'})
        edited=next(s for s in readback['services'] if s['id']==101)
        self.assertEqual((edited['name'],edited['provider'],edited['type']),('A'*152,'P'*100,0x19))
        self.assertEqual(path.read_bytes(),source)

    def test_rename_rejects_lossy_regional_encoding(self):
        path=self.rename_safety_fixture();source=path.read_bytes()
        state=self.core.call('analyze',{'path':str(path),'standards':'isdb-brazil'});service=next(s for s in state['services'] if s['id']==101)
        args={'id':service['source_id'],'service_id':101}
        for name in ['中文服务','New 中文','😀']:
            with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'losslessly.*charset'):
                self.core.call('preview_rename',{**args,'name':name})
        self.assertEqual(self.core.call('query')['services'],state['services'])
        edit=self.core.call('preview_rename',{**args,'name':'São Paulo'})
        exported=self.core.call('export',{'path':self.output('brazil.ts'),'preview_token':edit['token'],'cycles':1,'null_packets':0})
        readback=self.core.call('analyze',{'path':exported['path'],'standards':'isdb-brazil'})
        edited=next(s for s in readback['services'] if s['id']==101)
        self.assertEqual((edited['name'],edited['provider'],edited['type']),('São Paulo','Lab',0x19))
        self.assertEqual(path.read_bytes(),source)

    def test_rename_preserves_other_services_and_descriptor_bytes(self):
        path=self.rename_safety_fixture();state=self.core.call('analyze',{'path':str(path),'standards':'dvb'})
        service=next(s for s in state['services'] if s['id']==101)
        before=self.core.call('inspect',{'id':service['source_id']})
        edit=self.core.call('preview_rename',{'id':service['source_id'],'service_id':101,'name':'Renamed'})
        self.assertEqual((edit['old_version'],edit['new_version']),(31,0))
        result=self.core.call('export',{'path':self.output('preserved.ts'),'preview_token':edit['token'],'cycles':1,'null_packets':0})
        afterstate=self.core.call('analyze',{'path':result['path'],'standards':'dvb'})
        edited=next(s for s in afterstate['services'] if s['id']==101);after=self.core.call('inspect',{'id':edited['source_id']})
        unchanged=lambda detail:[(d['service_id'],d['raw']) for d in detail['descriptors'] if not (d['service_id']==101 and d['tag']==0x48)]
        self.assertEqual(unchanged(after),unchanged(before))
        self.assertEqual((edited['name'],edited['provider'],edited['type'],edited['encrypted']),('Renamed','Lab',0x19,True))
        other=next(s for s in afterstate['services'] if s['id']==102)
        self.assertEqual((other['name'],other['provider'],other['type'],other['encrypted']),('Other','Lab',2,False))

    def test_rename_adds_missing_service_descriptor_but_rejects_duplicate(self):
        path=self.rename_safety_fixture(service_descriptor=False)
        state=self.core.call('analyze',{'path':str(path),'standards':'dvb'});service=next(s for s in state['services'] if s['id']==101)
        edit=self.core.call('preview_rename',{'id':service['source_id'],'service_id':101,'name':'Added'})
        exported=self.core.call('export',{'path':self.output('added.ts'),'preview_token':edit['token'],'cycles':1,'null_packets':0})
        readback=self.core.call('analyze',{'path':exported['path'],'standards':'dvb'})
        edited=next(s for s in readback['services'] if s['id']==101)
        self.assertEqual((edited['name'],edited['provider'],edited['type']),('Added','',1))
        path=self.rename_safety_fixture(duplicate=True)
        state=self.core.call('analyze',{'path':str(path),'standards':'dvb'});service=next(s for s in state['services'] if s['id']==101)
        with self.assertRaisesRegex(RuntimeError,'Ambiguous duplicate'):
            self.core.call('preview_rename',{'id':service['source_id'],'service_id':101,'name':'Rejected'})

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

    def test_regional_non_ascii_sdt_native_tree_matches_flat_services(self):
        # Serialized with pinned TSDuck 3.39-3956 tstabcomp --japan / --brazil:
        # <SDT transport_stream_id="1" original_network_id="2"><service service_id="101">
        # <service_descriptor service_type="1" service_provider_name="..." service_name="..."/>
        # </service></SDT>. Retain binary fixtures so normal CI needs no compiler utility.
        fixtures=[
            ('isdb-japan','日本テレビ','東京','42f0240001c100000002ff0065fc001348110104456c357e0a467c4b5c2546256c25531f7d86ed'),
            ('isdb-brazil','São Paulo','Televisão','42f0280001c100000002ff0065fc00174815010954656c65766973e36f0953e36f205061756c6f97069f86'),
        ]
        import xml.etree.ElementTree as ET
        for profile,name,provider,encoded in fixtures:
            with self.subTest(profile=profile):
                raw=bytes.fromhex(encoded);path=self.output(profile+'.ts')
                Path(path).write_bytes(bytes([0x47,0x40,0x11,0x10,0])+raw+b'\xff'*(183-len(raw)))
                state=self.core.call('analyze',{'path':path,'standards':profile});service=state['services'][0]
                self.assertEqual((service['name'],service['provider']),(name,provider))
                detail=self.core.call('inspect',{'id':service['source_id']})
                native_service=next(node for node in detail['native_table']['children'] if node['name']=='service')
                native_descriptor=next(node for node in native_service['children'] if node['name']=='service_descriptor')
                self.assertEqual(native_descriptor['attributes']['service_name'],name)
                self.assertEqual(native_descriptor['attributes']['service_provider_name'],provider)
                direct=next(d for d in detail['descriptors'] if d['tag']==0x48)['native']
                self.assertEqual(direct['attributes'],native_descriptor['attributes'])
                xml_descriptor=ET.fromstring(detail['tsduck_xml']).find('./SDT/service/service_descriptor')
                self.assertEqual(xml_descriptor.attrib['service_name'],name);self.assertEqual(xml_descriptor.attrib['service_provider_name'],provider)

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

    def test_historical_inspection_never_assembles_future_siblings(self):
        from make_fixture import section,descriptor,word,crc
        def sdt(number,name):
            desc=descriptor(0x48,b'\x01\x00'+bytes([len(name)])+name)
            raw=bytearray(section(0x42,1,1,word(2)+b'\xff'+word(100+number)+b'\xff'+word(0x8000+len(desc))+desc))
            raw[6]=number;raw[7]=1;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big');return bytes(raw)
        parts=[sdt(0,b'A'),sdt(1,b'Old B'),sdt(0,b'A'),sdt(1,b'New B'),sdt(0,b'A')]
        path=self.output('historical-inspection.ts')
        Path(path).write_bytes(b''.join(bytes([0x47,0x40,0x11,0x10+i,0])+raw+b'\xff'*(183-len(raw)) for i,raw in enumerate(parts)))
        state=self.core.call('analyze',{'path':path});old=self.core.call('query',{'at_packet':1})
        aid=next(s['source_id'] for s in old['services'] if s['name']=='A')
        def names(detail):return [node['children'][0]['attributes']['service_name'] for node in detail['native_table']['children'] if node['name']=='service']
        latest=self.core.call('inspect',{'id':aid});self.assertEqual(names(latest),['A','New B']);self.assertEqual(latest['native_table_at_packet'],4)
        historical=self.core.call('inspect',{'id':aid,'at_packet':1})
        self.assertEqual(names(historical),['A','Old B']);self.assertEqual(historical['native_table_at_packet'],1)
        self.assertEqual(historical['occurrences'],[0]);self.assertEqual(historical['count'],1);self.assertEqual(historical['last_packet'],0)
        incomplete=self.core.call('inspect',{'id':aid,'at_packet':0});self.assertFalse(incomplete['native_table_complete']);self.assertNotIn('native_table',incomplete)
        future_id=next(s['source_id'] for s in state['services'] if s['name']=='New B')
        with self.assertRaisesRegex(RuntimeError,'not observed'):self.core.call('inspect',{'id':future_id,'at_packet':1})
        with self.assertRaisesRegex(RuntimeError,'Below minimum'):self.core.call('inspect',{'id':aid,'at_packet':-1})
        old_bid=next(s['source_id'] for s in old['services'] if s['name']=='Old B')
        superseded=self.core.call('inspect',{'id':old_bid,'at_packet':4})
        self.assertFalse(superseded['native_table_complete']);self.assertIn('superseded',superseded['native_decode_status'])

    def test_nonregular_source_is_rejected_without_blocking(self):
        import os
        with self.assertRaisesRegex(RuntimeError,'regular local file'):
            self.core.call('analyze',{'path':self.tmp.name})
        state=self.core.call('query');self.assertFalse(state['complete']);self.assertEqual(state['tables'],[])
        if os.name!='nt' and hasattr(os,'mkfifo'):
            fifo=self.output('input.pipe');os.mkfifo(fifo)
            requests=[{'id':1,'method':'analyze','params':{'path':fifo}}, {'id':2,'method':'query','params':{}}]
            # The process must reject the FIFO before opening it; timeout bounds a regression.
            run=subprocess.run([self.core.proc.args[0],'--root',str(ROOT)],input=''.join(json.dumps(r)+'\n' for r in requests),capture_output=True,text=True,encoding='utf-8',timeout=5,check=True)
            responses={r['id']:r for r in map(json.loads,run.stdout.splitlines()) if 'id' in r}
            self.assertIn('regular local file',responses[1]['error']['message'])
            self.assertFalse(responses[2]['result']['complete']);self.assertEqual(responses[2]['result']['tables'],[])
            link=Path(self.output('普通 链接.ts'));link.symlink_to(ROOT/'samples/generated/lab.ts')
            result=self.core.call('analyze',{'path':str(link)});self.assertTrue(result['complete']);self.assertEqual(len(result['services']),6)

    def test_snapshot_diff_content_pagination_and_read_only(self):
        a=self.state['history'][0]['last_packet'];b=self.state['packets']-1
        params={'from_packet':a,'to_packet':b}
        service=self.state['services'][0]
        preview=self.core.call('preview_rename',{'id':service['source_id'],'service_id':service['id'],'name':'Diff preserves preview'})
        before=self.core.call('query');result=self.core.call('diff_snapshots',params)
        self.assertEqual(result['revision'],before['revision']);self.assertEqual(result['source'],before['source'])
        self.assertEqual(result['summary']['tables']['changed'],1)
        self.assertEqual(result['summary']['services']['changed'],3)
        self.assertEqual(result['summary']['events']['changed'],0)
        sports=next(c for c in result['changes'] if c['kind']=='services' and c['identity']['service_id']==103)
        self.assertEqual(sports['before']['value']['name'],'Sports HD');self.assertEqual(sports['after']['value']['name'],'Sports UHD')
        self.assertIn('name',sports['changed_fields']);self.assertIn('logical_channel_number',sports['changed_fields'])
        self.assertEqual(sports['after']['evidence'][0]['id'],sports['after']['value']['source_id'])
        self.assertEqual({e['table_id'] for e in sports['after']['evidence']},{0,2,0x42})
        self.assertNotIn('history',result);self.assertNotIn('density',result)
        for change in result['changes']:
            for side in ['before','after']:
                if change[side]:
                    self.assertTrue(all(e['last_packet']<=change[side]['at_packet'] for e in change[side]['evidence']))
        rows=[];offset=0
        while offset is not None:
            page=self.core.call('diff_snapshots',{**params,'offset':offset,'limit':1})
            self.assertEqual(page['summary'],result['summary']);self.assertEqual(page['total_changes'],result['total_changes'])
            rows+=page['changes'];offset=page['next_offset']
        self.assertEqual(rows,result['changes']);self.assertEqual(self.core.call('diff_snapshots',params),result)
        filtered=self.core.call('diff_snapshots',{**params,'kind':'services'})
        self.assertEqual(filtered['summary'],result['summary']);self.assertEqual(filtered['total_changes'],3)
        self.assertTrue(all(c['kind']=='services' for c in filtered['changes']))
        empty=self.core.call('diff_snapshots',{**params,'offset':10000})
        self.assertEqual(empty['changes'],[]);self.assertIsNone(empty['next_offset'])
        repeated=self.core.call('diff_snapshots',{'from_packet':1000,'to_packet':2000})
        self.assertEqual(repeated['total_changes'],0)
        same=self.core.call('diff_snapshots',{'from_packet':b,'to_packet':b})
        self.assertEqual(same['changes'],[]);self.assertEqual(same['total_changes'],0)
        self.assertEqual(self.core.call('query'),before)
        exported=self.core.call('export',{'path':self.output('after-diff.bin'),'format':'bin','preview_token':preview['token']})
        self.assertEqual(exported['edit']['token'],preview['token'])

    def snapshot_fixture(self):
        from make_fixture import section,descriptor,word,crc
        def sdt(version,services,onid=2,tsid=1):
            payload=word(onid)+b'\xff'
            for sid,name in services:
                name=name.encode();desc=descriptor(0x48,b'\x01\x00'+bytes([len(name)])+name)
                payload+=word(sid)+b'\xff'+word(0x8000+len(desc))+desc
            return section(0x42,tsid,version,payload)
        def eit(version,events,onid=2,tsid=1,tid=0x4e):
            payload=word(tsid)+word(onid)+bytes([0,tid])
            for eid,title in events:
                title=title.encode();desc=descriptor(0x4d,b'eng'+bytes([len(title)])+title+b'\x00')
                payload+=word(eid)+word(61000)+bytes([9,0,0,1,0,0])+word(0x8000+len(desc))+desc
            return section(tid,101,version,payload)
        pairs=[(0x1fff,None),(0,section(0,1,0,word(101)+word(0xe100))),
               (0x100,section(2,101,0,word(0xe200)+word(0xf000))),
               (0x11,sdt(0,[(101,'Alpha'),(102,'Removed')])),(0x12,eit(0,[(1,'Old event')])),
               (0x11,sdt(1,[(101,'Beta'),(103,'Added')])),
               (0x100,section(2,101,1,word(0xe201)+word(0xf000))),
               (0x12,eit(1,[(1,'New event'),(2,'Added event')])),
               (0x12,eit(0,[(1,'Different TS')],tsid=2)),
               (0x12,eit(0,[(1,'Different network')],onid=3)),
               (0x11,sdt(0,[(101,'Other network service')],onid=3)),
               (0x12,eit(0,[(1,'Schedule event')],tid=0x50))]
        bad=bytearray(sdt(2,[(101,'Bad CRC')]));bad[-1]^=1;pairs.append((0x11,bytes(bad)))
        nxt=bytearray(sdt(2,[(101,'Next only')]));nxt[5]&=254;nxt[-4:]=crc(nxt[:-4]).to_bytes(4,'big');pairs.append((0x11,bytes(nxt)))
        counters={};packets=[]
        for pid,raw in pairs:
            if raw is None:packets.append(bytes([0x47,0x1f,0xff,0x10])+b'\xff'*184);continue
            cc=counters.get(pid,0);counters[pid]=(cc+1)%16
            self.assertLessEqual(len(raw),183)
            packets.append(bytes([0x47,0x40|(pid>>8),pid&255,0x10|cc,0])+raw+b'\xff'*(183-len(raw)))
        path=self.output('snapshot-diff.ts');Path(path).write_bytes(b''.join(packets))
        return self.core.call('analyze',{'path':path,'standards':'dvb'})

    def test_snapshot_diff_added_removed_changed_and_network_identity(self):
        self.snapshot_fixture()
        result=self.core.call('diff_snapshots',{'from_packet':4,'to_packet':7})
        self.assertEqual(result['summary']['services'],{'added':1,'removed':1,'changed':1,'unchanged':0})
        self.assertEqual(result['summary']['events'],{'added':1,'removed':0,'changed':1,'unchanged':0})
        event=next(c for c in result['changes'] if c['kind']=='events' and c['change']=='changed')
        self.assertEqual(event['changed_fields'],['language_variants','title']);self.assertEqual(event['before']['value']['title'],'Old event')
        service=next(c for c in result['changes'] if c['kind']=='services' and c['change']=='changed')
        self.assertIn('components',service['changed_fields']);self.assertEqual(service['after']['value']['components']['pcr_pid'],0x201)
        reverse=self.core.call('diff_snapshots',{'from_packet':7,'to_packet':4})
        indexed={(c['kind'],c['key']):c for c in reverse['changes']}
        for forward in result['changes']:
            backward=indexed[(forward['kind'],forward['key'])]
            self.assertEqual(backward['before'],forward['after']);self.assertEqual(backward['after'],forward['before'])
            self.assertEqual(backward['change'],{'added':'removed','removed':'added','changed':'changed'}[forward['change']])
        late=self.core.call('query',{'at_packet':11})
        self.assertEqual({(s['onid'],s['id']) for s in late['services']},{(2,101),(2,103),(3,101)})
        self.assertEqual(len(late['events']),5)
        target=next(s for s in late['services'] if s['onid']==2 and s['id']==101)
        preview=self.core.call('preview_rename',{'id':target['source_id'],'service_id':101,'name':'Explicit target'})
        with self.assertRaisesRegex(RuntimeError,'Ambiguous SDT edit'):
            self.core.call('export',{'path':self.output('ambiguous.bin'),'format':'bin','at_packet':11,'preview_token':preview['token']})
        self.assertFalse(Path(self.output('ambiguous.bin')).exists())
        # Before the competing network identity appeared, the same exact target
        # and preview remain unambiguous and usable.
        self.core.call('export',{'path':self.output('unambiguous.bin'),'format':'bin','at_packet':7,'preview_token':preview['token']})
        networks=self.core.call('diff_snapshots',{'from_packet':7,'to_packet':11})
        self.assertEqual(networks['summary']['services']['added'],1);self.assertEqual(networks['summary']['services']['removed'],0)
        self.assertEqual(networks['summary']['events']['added'],3);self.assertEqual(networks['summary']['events']['removed'],0)
        self.assertEqual(len({c['key'] for c in networks['changes'] if c['kind']=='events'}),3)
        excluded=self.core.call('diff_snapshots',{'from_packet':11,'to_packet':13})
        self.assertEqual(excluded['total_changes'],0)
        earliest=self.core.call('diff_snapshots',{'from_packet':0,'to_packet':4})
        self.assertTrue(all(c['change']=='added' and c['before'] is None for c in earliest['changes']))
        for c in earliest['changes']:
            self.assertTrue(all(e['last_packet']<=4 for e in c['after']['evidence']))

    def test_snapshot_diff_generation_completion_and_version_reuse(self):
        from make_fixture import section,descriptor,word,crc
        def part(version,number,name):
            desc=descriptor(0x48,b'\x01\x00'+bytes([len(name)])+name)
            raw=bytearray(section(0x42,1,version,word(2)+b'\xff'+word(100+number)+b'\xff'+word(0x8000+len(desc))+desc))
            raw[6]=number;raw[7]=1;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big');return bytes(raw)
        # The intervening generation never observed section 1. A reused version
        # must still not resurrect that old sibling when section 0 reappears.
        parts=[part(0,0,b'Old A'),part(0,1,b'Old B'),part(31,0,b'Interim A'),part(0,0,b'New A'),part(0,1,b'New B')]
        path=self.output('version-reuse.ts');Path(path).write_bytes(b''.join(bytes([0x47,0x40,0x11,0x10+i,0])+raw+b'\xff'*(183-len(raw)) for i,raw in enumerate(parts)))
        state=self.core.call('analyze',{'path':path})
        partial=self.core.call('query',{'at_packet':3});self.assertEqual(partial['services'],[])
        rid=next(t['id'] for t in state['tables'] if t['first_packet']==3)
        detail=self.core.call('inspect',{'id':rid,'at_packet':3});self.assertFalse(detail['native_table_complete'])
        with self.assertRaisesRegex(RuntimeError,'Incomplete'):self.core.call('export',{'path':self.output('partial.bin'),'format':'bin','at_packet':3})
        changed=self.core.call('diff_snapshots',{'from_packet':1,'to_packet':3})
        self.assertEqual(changed['summary']['services']['removed'],2)
        self.assertTrue(any(c['kind']=='tables' and c['after'] and not c['after']['value']['complete_group'] for c in changed['changes']))
        completed=self.core.call('diff_snapshots',{'from_packet':3,'to_packet':4})
        self.assertEqual(completed['summary']['services']['added'],2)
        self.assertEqual([s['name'] for s in self.core.call('query',{'at_packet':4})['services']],['New A','New B'])

    def test_snapshot_diff_page_bound_and_empty_signalling(self):
        from make_fixture import section,descriptor,word
        null=bytes([0x47,0x1f,0xff,0x10])+b'\xff'*184
        path=self.output('many-networks.ts');packets=[null]
        desc=descriptor(0x48,b'\x01\x00\x04Test')
        for onid in range(230):
            raw=section(0x42,1,0,word(onid)+b'\xff'+word(101)+b'\xff'+word(0x8000+len(desc))+desc)
            packets.append(bytes([0x47,0x40,0x11,0x10|(onid%16),0])+raw+b'\xff'*(183-len(raw)))
        Path(path).write_bytes(b''.join(packets));self.core.call('analyze',{'path':path})
        first=self.core.call('diff_snapshots',{'from_packet':0,'to_packet':230,'kind':'services','limit':200})
        self.assertEqual(first['total_changes'],230);self.assertEqual(len(first['changes']),200);self.assertEqual(first['next_offset'],200)
        second=self.core.call('diff_snapshots',{'from_packet':0,'to_packet':230,'kind':'services','limit':200,'offset':200})
        self.assertEqual(len(second['changes']),30);self.assertIsNone(second['next_offset'])
        identities=[c['identity']['original_network_id'] for c in first['changes']+second['changes']]
        self.assertEqual(set(identities),set(range(230)));self.assertEqual(len(identities),len(set(identities)))
        Path(path).write_bytes(null*2);self.core.call('analyze',{'path':path})
        empty=self.core.call('diff_snapshots',{'from_packet':0,'to_packet':1})
        self.assertEqual(empty['total_changes'],0);self.assertEqual(empty['changes'],[])
        self.assertTrue(all(sum(counts.values())==0 for counts in empty['summary'].values()))

    def test_snapshot_diff_rejects_invalid_requests_and_failed_sessions(self):
        valid={'from_packet':0,'to_packet':self.state['packets']-1}
        for params,reason in [({},'Required argument'),({'from_packet':0},'Required argument'),({**valid,'from_packet':-1},'Below minimum'),({**valid,'to_packet':1.5},'Wrong type'),({**valid,'limit':0},'Below minimum'),({**valid,'limit':201},'Above maximum'),({**valid,'offset':-1},'Below minimum'),({**valid,'kind':'unknown'},'Invalid choice'),({**valid,'other':1},'Unknown argument'),({**valid,'from_packet':self.state['packets']},'packet range'),({**valid,'to_packet':9007199254740992},'Above maximum')]:
            with self.subTest(params=params),self.assertRaisesRegex(RuntimeError,reason):self.core.call('diff_snapshots',params)
        with Core() as fresh:
            with self.assertRaisesRegex(RuntimeError,'successful analysis'):fresh.call('diff_snapshots',{'from_packet':0,'to_packet':0})
        with self.assertRaises(RuntimeError):self.core.call('analyze',{'path':self.output('missing.ts')})
        with self.assertRaisesRegex(RuntimeError,'successful analysis'):self.core.call('diff_snapshots',valid)

    def test_machine_argument_validation(self):
        with self.assertRaisesRegex(RuntimeError,'Below minimum'):self.core.call('query',{'at_packet':-1})
        with self.assertRaisesRegex(RuntimeError,'Unknown argument'):self.core.call('query',{'timestamp':0})
        with self.assertRaisesRegex(RuntimeError,'Wrong type'):self.core.call('inspect',{'id':123})

if __name__=='__main__':unittest.main(verbosity=2)
