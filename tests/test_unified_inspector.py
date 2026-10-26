"""Real-engine evidence for the unified inspector, using synthetic DVB sections."""
import datetime
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core
from make_fixture import section,descriptor,word,crc

def fixture():
    pat=section(0,0x1001,31,word(101)+word(0xe100)+word(0x100)+word(0xe102))
    pmt=section(2,101,1,word(0xe101)+word(0xf000)+bytes([0x1b])+word(0xe101)+word(0xf006)+descriptor(0x52,b'\x01')+descriptor(0xe2,b'\x42'))
    transport=word(0x1001)+word(0x2001)+word(0xf000)
    name=descriptor(0x47,b'Local fixture bouquet')
    bat=section(0x4a,88,1,word(0xf000+len(name))+name+word(0xf000+len(transport))+transport)
    mjd=(datetime.date(2026,10,21)-datetime.date(1858,11,17)).days
    next_pat=bytearray(pat);next_pat[5]&=0xfe;next_pat[-4:]=crc(next_pat[:-4]).to_bytes(4,'big')
    pairs=[(0,pat),(0x100,pmt),(0x102,section(2,0x100,1,word(0xe103)+word(0xf000)+bytes([0x1b])+word(0xe103)+word(0xf000))),(0x11,bat),(0,bytes(next_pat)),(0,section(0,0x1001,0,word(101)+word(0xe100))),(0,pat)]
    for hour in [9,10,9]:
        utc=word(mjd)+bytes([0x09 if hour==9 else 0x10,0,0])
        tdt=b'\x70\x70\x05'+utc
        tot=b'\x73\x70\x0b'+utc+word(0xf000);tot+=crc(tot).to_bytes(4,'big')
        pairs += [(0x14,tdt),(0x14,tot)]
    # Real named-network + SDT + namespaced LCN declarations for the classic tree.
    service=descriptor(0x48,b'\x01\x00\x08News One')
    pairs.append((0x11,section(0x42,0x1001,1,word(0x2001)+b'\xff'+word(101)+b'\xff'+word(0x8000+len(service))+service)))
    delivery=descriptor(0x43,bytes.fromhex('0117275001308002750003'))
    lcn=descriptor(0x5f,bytes.fromhex('00000028'))+descriptor(0x83,word(101)+word(0xfc07))
    transport=word(0x1001)+word(0x2001)+word(0xf000+len(delivery+lcn))+delivery+lcn
    netname=descriptor(0x40,b'Fixture Network')
    pairs.append((0x10,section(0x40,10,1,word(0xf000+len(netname))+netname+word(0xf000+len(transport))+transport)))
    cc={};packets=[]
    for pid,raw in pairs:
        n=cc.get(pid,0);cc[pid]=(n+1)%16
        packets.append(bytes([0x47,0x40|(pid>>8),pid&255,0x10|n,0])+raw+b'\xff'*(183-len(raw)))
    return b''.join(packets)

class UnifiedInspectorEngineTests(unittest.TestCase):
    def test_reference_table_structures_from_pinned_vectors(self):
        from si_reference_fixture import collect
        out=Path(os.environ.get('SHOWPSISI_UNIFIED_EVIDENCE_DIR',ROOT/'artifacts/unified-inspector'))
        out.mkdir(parents=True,exist_ok=True)
        core=Core()
        try:
            cases=collect(core,out/'reference-inputs')
            self.assertGreaterEqual(len(cases),50)
            (out/'reference-trees.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
        finally:core.close()

    def test_short_syntax_repeats_and_program_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'inspector.ts';path.write_bytes(fixture())
            core=Core()
            try:
                state=core.call('analyze',{'path':str(path),'standards':'dvb'})
                self.assertEqual(state['crc_errors'],0)
                details=[core.call('inspect',{'id':r['id']}) for r in state['tables']]
                # Wire positions are selected-section evidence, not XML attribute guesses.
                for detail in details:
                    raw=bytes.fromhex(detail['raw_hex'])
                    def visit(node):
                        for field in node['fields']:
                            start,width=field['bit_offset'],field['bit_length']
                            self.assertGreater(width,0)
                            self.assertLessEqual(start+width,len(raw)*8)
                        for child in node['children']:visit(child)
                    visit(detail['si_structure'])
                pmt=next(d for d in details if d['name']=='PMT' and d['pid']==0x100)
                fields={f['name']:f for f in pmt['si_structure']['fields']}
                self.assertEqual((fields['PCR_PID']['bit_offset'],fields['PCR_PID']['bit_length'],fields['PCR_PID']['value']),(67,13,'0x0101 [257]'))
                self.assertEqual((fields['version_number']['bit_offset'],fields['version_number']['bit_length']),(42,5))
                stream=pmt['si_structure']['children'][0]
                es=next(f for f in stream['fields'] if f['name']=='elementary_PID')
                self.assertEqual((es['bit_offset'],es['bit_length'],es['value']),(107,13,'0x0101 [257]'))
                self.assertEqual([n['descriptor_offset'] for n in stream['children']],[17,20])
                self.assertEqual(stream['children'][1]['fields'][2]['value'],'0x42 [66]')
                for detail in details:
                    if detail['name']=='TDT':
                        names=[f['name'] for f in detail['si_structure']['fields']]
                        self.assertNotIn('version_number',names)
                        self.assertNotIn('CRC_32',names)
                times=[r for r in state['tables'] if r['table_id'] in (0x70,0x73)]
                self.assertEqual(len(times),4)
                self.assertEqual(sorted(r['count'] for r in times),[1,1,2,2])
                sequence=[r for r in state['table_history'] if r['table_id']==0x70]
                self.assertEqual(len(sequence),3)
                self.assertEqual(sequence[0]['id'],sequence[2]['id'])
                self.assertNotEqual(sequence[0]['id'],sequence[1]['id'])
                for r in sequence:
                    self.assertFalse(r['versioning_supported'])
                    for key in ('current','extension','section'):self.assertIsNone(r[key])
                for group in state['table_groups']:
                    if group['table_id'] in (0x70,0x73):
                        self.assertIn('DVB time',group['coverage_model'])
                        self.assertEqual(group['observed_section_numbers'],[])
                for r in times:
                    self.assertFalse(r['versioning_supported'])
                    self.assertIn('2026',r['utc_time'])
                    for key in ('version','current','extension','section','last_section'):self.assertIsNone(r[key])
                    self.assertIsNone(r['identity']['version'])
                    self.assertEqual(r['crc']['status'],'not_present' if r['table_id']==0x70 else 'valid')
                pats=[r for r in state['tables'] if r['name']=='PAT']
                self.assertEqual(len(pats),3)
                self.assertEqual({(r['version'],r['current']) for r in pats},{(31,True),(31,False),(0,True)})
                self.assertEqual(sum(r['count'] for r in pats),4)
                out=Path(os.environ.get('SHOWPSISI_UNIFIED_EVIDENCE_DIR',ROOT/'artifacts/unified-inspector'));out.mkdir(parents=True,exist_ok=True)
                (out/'fixture.ts').write_bytes(path.read_bytes())
                topology=core.call('query_topology',{'limit':500})
                network=next(n for n in topology['nodes'] if n['object_type']=='network')
                self.assertEqual(network['attributes']['name'],'Fixture Network')
                self.assertEqual(state['services'][0]['logical_channel_number'],7)
                (out/'engine-evidence.json').write_text(json.dumps({'state':state,'details':details,'topology':topology},indent=2),encoding='utf-8')
            finally:core.close()

    def test_si_loop_positions_and_descriptor_namespaces(self):
        service=descriptor(0x48,b'\x01\x01P\x01S')
        event=descriptor(0x4d,b'eng\x01E\x01T')
        raws=[(0,section(0,1,1,word(100)+word(0xe100))),
              (1,section(1,1,1,descriptor(9,word(0x100)+word(0xe101)))),
              (0x11,section(0x42,1,1,word(2)+b'\xff'+word(100)+b'\xff'+word(0x8000+len(service))+service)),
              (0x10,section(0x40,1,1,word(0xf000)+word(0xf006)+word(1)+word(2)+word(0xf000))),
              (0x12,section(0x4e,100,1,word(1)+word(2)+b'\x00\x4e'+word(5)+bytes.fromhex('eb96123456010000')+word(0x8000+len(event))+event))]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'si.ts'
            path.write_bytes(b''.join(bytes([0x47,0x40|(pid>>8),pid&255,0x10,0])+raw+b'\xff'*(183-len(raw)) for pid,raw in raws))
            core=Core()
            try:
                state=core.call('analyze',{'path':str(path),'standards':'dvb'})
                details={r['table_id']:core.call('inspect',{'id':r['id']}) for r in state['tables']}
                def fields(node):
                    return node['fields']+[f for child in node['children'] for f in fields(child)]
                expected={0x42:{'service_id':88,'service_type':144,'service_name':176},
                          0x40:{'transport_stream_id':96,'original_network_id':112},
                          0x4e:{'event_id':112,'start_time':128,'event_name':256},
                          1:{'CA_system_id':80,'CA_PID':99}}
                for tid,positions in expected.items():
                    detail=details[tid];self.assertTrue(detail['valid'])
                    items=fields(detail['si_structure'])
                    for name,offset in positions.items():
                        self.assertTrue(any(f['name']==name and f['bit_offset']==offset for f in items),(tid,name,offset,items))
                    raw=bytes.fromhex(detail['raw_hex']);bits=''.join(f'{b:08b}' for b in raw)
                    for f in items:
                        start,width=f['bit_offset'],f['bit_length']
                        self.assertLessEqual(start+width,len(bits))
                        if width<=48:self.assertEqual(int(f['value'].split(' [')[1][:-1]),int(bits[start:start+width],2))
            finally:core.close()

    def test_source_packet_framing_mapping_and_changed_file(self):
        base=fixture();packets=[base[i:i+188] for i in range(0,len(base),188)]
        with tempfile.TemporaryDirectory() as tmp:
            core=Core()
            try:
                for stride,prefix in [(188,0),(192,4),(204,0)]:
                    path=Path(tmp)/f'framing-{stride}.ts'
                    raw=b''.join((b'\x00'*prefix)+p+(b'\x00'*(stride-prefix-188)) for p in packets)
                    path.write_bytes(raw)
                    state=core.call('analyze',{'path':str(path),'standards':'dvb'})
                    row=next(r for r in state['tables'] if r['name']=='PMT' and r['pid']==256)
                    detail=core.call('inspect',{'id':row['id']});packet=detail['source_packet']
                    self.assertEqual(packet['status'],'available')
                    self.assertEqual(packet['framing_stride'],stride)
                    self.assertEqual(packet['file_offset'],stride+prefix)
                    self.assertEqual(packet['raw_hex'],packets[1].hex().upper())
                    self.assertEqual(packet['section_offset'],5)
                    self.assertEqual(packet['section_bytes'],detail['bytes'])
                    with path.open('ab') as f:f.write(b'changed')
                    stale=core.call('inspect',{'id':row['id']})
                    self.assertEqual(stale['raw_hex'],detail['raw_hex'])
                    self.assertEqual(stale['source_packet']['status'],'source_changed')
                    self.assertEqual(stale['source_packet']['raw_hex'],'')
                    self.assertEqual(stale['source_fragments']['status'],'source_changed')
            finally:core.close()

    def test_source_packet_multiple_sections_and_continuation(self):
        pat1=section(0,1,1,word(100)+word(0xe100))
        pat2=section(0,1,2,word(100)+word(0xe101))
        first=bytes([0x47,0x40,0,0x10,0])+pat1+pat2
        first+=b'\xff'*(188-len(first))
        large=section(0,2,1,b''.join(word(100+i)+word(0xe100+i) for i in range(60)))
        start=bytes([0x47,0x40,0,0x11,0])+large[:183]
        tail=bytes([0x47,0,0,0x12])+large[183:]
        tail+=b'\xff'*(188-len(tail))
        null=bytes([0x47,0x1f,0xff,0x10])+b'\xff'*184
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'sections.ts';path.write_bytes(first+start+tail+null*3)
            core=Core()
            try:
                state=core.call('analyze',{'path':str(path),'standards':'dvb'})
                for row in state['tables']:
                    detail=core.call('inspect',{'id':row['id']});packet=detail['source_packet']
                    if row['extension']==2:
                        self.assertEqual(packet['packet_index'],1)
                        self.assertEqual(packet['section_offset'],5)
                        self.assertEqual(packet['section_bytes'],183)
                        self.assertGreater(detail['bytes'],183)
                        fragments=detail['source_fragments'];self.assertEqual(fragments['status'],'complete');self.assertEqual(len(fragments['fragments']),2)
                        reassembled=b''
                        source=path.read_bytes()
                        for part in fragments['fragments']:
                            original=bytes.fromhex(part['raw_hex']);self.assertEqual(original,source[part['file_offset']:part['file_offset']+188])
                            self.assertEqual(part['section_begin'],len(reassembled));reassembled+=original[part['section_offset']:part['section_offset']+part['section_bytes']]
                        self.assertEqual(reassembled,bytes.fromhex(detail['raw_hex']))
                        out=Path(os.environ.get('SHOWPSISI_UNIFIED_EVIDENCE_DIR',ROOT/'artifacts/unified-inspector'));out.mkdir(parents=True,exist_ok=True)
                        (out/'cross-packet-evidence.json').write_text(json.dumps({'state':state,'detail':detail}),encoding='utf-8')
                    elif row['version']==2:self.assertEqual(packet['section_offset'],5+len(pat1))
                    else:self.assertEqual(packet['section_offset'],5)
            finally:core.close()

if __name__=='__main__':unittest.main()
