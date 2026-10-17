"""Service metadata is derived from scoped descriptor/PMT wire evidence."""
import test_section_evidence as evidence
from make_fixture import section, descriptor, word
import unittest

class ServiceMetadataTests(unittest.TestCase):
    setUp=evidence.SectionEvidenceTests.setUp
    tearDown=evidence.SectionEvidenceTests.tearDown
    sdt=evidence.SectionEvidenceTests.sdt
    scan=evidence.SectionEvidenceTests.scan
    # Reuse fixture transport helpers without inheriting the evidence test cases.
    def pat(self):
        return (0,section(0,1,1,word(100)+word(0xe100)))
    def pmt(self):
        def stream(kind,pid,desc=b''):
            return bytes([kind])+word(0xe000|pid)+word(0xf000|len(desc))+desc
        payload=word(0xe200)+word(0xf000)
        payload+=stream(0x1b,0x200)+stream(0x0f,0x201)+stream(0x06,0x202,descriptor(0x6a,b'\x00'))+stream(0x06,0x203)
        return (0x100,section(2,100,1,payload))
    def nit(self,pds=0x28,lcn=7,visible=True,onid=2,tsid=1,version=1):
        desc=descriptor(0x5f,pds.to_bytes(4,'big'))+descriptor(0x83,word(100)+word((0x8000 if visible else 0)|0x7c00|lcn))
        transport=word(tsid)+word(onid)+word(0xf000|len(desc))+desc
        return (0x10,section(0x40,10,version,word(0xf000)+word(0xf000|len(transport))+transport))
    def test_service_type_and_media_follow_actual_pmt(self):
        state=self.scan([self.pat(),self.pmt(),self.sdt(last=0)])
        s=state['services'][0]
        self.assertEqual(s['service_type_name'],'Digital television service');self.assertEqual(s['service_type'],1);self.assertEqual(s['pmt_pid'],0x100)
        self.assertEqual(s['video_pids'],[0x200]);self.assertEqual(s['audio_pids'],[0x201,0x202])
        self.assertEqual(s['media_status'],'decoded PMT')
        self.assertFalse(s['components']['streams'][-1]['is_audio'])
        early=self.core.call('query',{'at_packet':0});self.assertEqual(early['services'],[])
    def test_absent_pmt_is_explicit_unknown(self):
        s=self.scan([self.pat(),self.sdt(last=0)])['services'][0]
        self.assertEqual(s['audio_pids'],[]);self.assertEqual(s['video_pids'],[])
        self.assertEqual(s['media_status'],'PMT unavailable');self.assertEqual(s['lcn_status'],'unknown')
        self.assertIsNone(s['logical_channel_number'])
    def test_scoped_native_lcn_preserves_visibility_and_source(self):
        state=self.scan([self.nit(visible=False),self.sdt(last=0)])
        s=state['services'][0];self.assertEqual(s['logical_channel_number'],7)
        self.assertEqual(s['lcn_status'],'known');c=s['lcn_candidates'][0]
        self.assertFalse(c['visible']);self.assertIsNone(c['region']);self.assertEqual(c['pds'],0x28)
        source=next(t for t in state['tables'] if t['id']==c['source_id']);self.assertEqual(source['pid'],0x10)
    def test_lcn_unknown_pds_and_wrong_triplet_are_not_guessed(self):
        for nit in [self.nit(pds=0x12345678),self.nit(onid=9),self.nit(tsid=9)]:
            with self.subTest(nit=nit):
                s=self.scan([nit,self.sdt(last=0)])['services'][0]
                self.assertEqual(s['lcn_status'],'unknown');self.assertIsNone(s['logical_channel_number'])
    def test_lcn_conflicts_are_retained_not_arbitrarily_selected(self):
        first=self.nit();second=list(self.nit(lcn=9));raw=bytearray(second[1]);raw[3:5]=word(11)
        from make_fixture import crc
        raw[-4:]=crc(raw[:-4]).to_bytes(4,'big');second[1]=bytes(raw)
        s=self.scan([first,tuple(second),self.sdt(last=0)])['services'][0]
        self.assertEqual(s['lcn_status'],'conflict');self.assertIsNone(s['logical_channel_number'])
        self.assertEqual({c['number'] for c in s['lcn_candidates']},{7,9})
    def test_lcn_history_uses_selected_version_not_future_mapping(self):
        state=self.scan([self.nit(lcn=7),self.sdt(last=0),self.nit(lcn=9,version=2)])
        self.assertEqual(state['services'][0]['logical_channel_number'],9)
        old=self.core.call('query',{'at_packet':1})['services'][0]
        self.assertEqual(old['logical_channel_number'],7)
        self.assertEqual(len(old['lcn_candidates']),1)
    def test_visibility_conflict_is_not_flattened(self):
        first=self.nit();second=list(self.nit(visible=False));raw=bytearray(second[1]);raw[3:5]=word(11)
        from make_fixture import crc
        raw[-4:]=crc(raw[:-4]).to_bytes(4,'big');second[1]=bytes(raw)
        s=self.scan([first,tuple(second),self.sdt(last=0)])['services'][0]
        self.assertEqual(s['lcn_status'],'conflict');self.assertIsNone(s['logical_channel_number'])
        self.assertEqual({c['visible'] for c in s['lcn_candidates']},{True,False})
    def test_missing_service_descriptor_has_unknown_service_type(self):
        raw=section(0x42,1,1,word(2)+b'\xff'+word(100)+b'\xff'+word(0x8000))
        s=self.scan([raw])['services'][0]
        self.assertIsNone(s['service_type']);self.assertIsNone(s['service_type_name'])
    def test_unregistered_private_stream_types_are_not_media(self):
        for kind in [0x81,0x87,0xd2,0xd3,0xd4,0xd5]:
            with self.subTest(kind=kind):
                pmt=(0x100,section(2,100,1,word(0xe200)+word(0xf000)+bytes([kind])+word(0xe201)+word(0xf000)))
                s=self.scan([self.pat(),pmt,self.sdt(last=0)],standards='dvb')['services'][0]
                self.assertEqual(s['audio_pids'],[]);self.assertEqual(s['video_pids'],[])
    def test_malformed_audio_descriptor_does_not_classify_private_pes(self):
        desc=descriptor(0x6a,b'')
        pmt=(0x100,section(2,100,1,word(0xe200)+word(0xf000)+b'\x06'+word(0xe201)+word(0xf000|len(desc))+desc))
        s=self.scan([self.pat(),pmt,self.sdt(last=0)],standards='dvb')['services'][0]
        self.assertEqual(s['audio_pids'],[])
    def test_explicit_atsc_private_ac3_retains_classification(self):
        pmt=(0x100,section(2,100,1,word(0xe200)+word(0xf000)+b'\x81'+word(0xe201)+word(0xf000)))
        state=self.scan([self.pat(),pmt],standards='atsc')
        row=next(t for t in state['tables'] if t['table_id']==2)
        detail=self.core.call('inspect',{'id':row['id']})
        self.assertTrue(detail['fields']['streams'][0]['is_audio'])
    def test_registered_hdmv_and_avs_classification_is_scoped(self):
        for reg,kind,audio,video in [(b'HDMV',0x80,True,False),(b'HDMV',0x91,False,False),(b'AVSV',0xd2,False,True),(b'AVSA',0xd3,True,False)]:
            with self.subTest(reg=reg,kind=kind):
                desc=descriptor(0x05,reg)
                pmt=(0x100,section(2,100,1,word(0xe200)+word(0xf000|len(desc))+desc+bytes([kind])+word(0xe201)+word(0xf000)))
                s=self.scan([self.pat(),pmt,self.sdt(last=0)],standards='dvb')['services'][0]
                self.assertEqual(s['audio_pids'],[0x201] if audio else [])
                self.assertEqual(s['video_pids'],[0x201] if video else [])
    def test_dtmb_without_avs_registration_does_not_invent_codec(self):
        pmt=(0x100,section(2,100,1,word(0xe200)+word(0xf000)+b'\xd2'+word(0xe201)+word(0xf000)))
        state=self.scan([self.pat(),pmt],standards='dtmb')
        row=next(t for t in state['tables'] if t['table_id']==2)
        stream=self.core.call('inspect',{'id':row['id']})['fields']['streams'][0]
        self.assertFalse(stream['is_video']);self.assertFalse(stream['is_audio'])
    def test_redundant_lcn_sources_do_not_change_service_semantics(self):
        first=self.nit();second=list(self.nit());raw=bytearray(second[1]);raw[3:5]=word(11)
        from make_fixture import crc
        raw[-4:]=crc(raw[:-4]).to_bytes(4,'big');second[1]=bytes(raw)
        state=self.scan([first,self.sdt(last=0),tuple(second)])
        self.assertEqual(len(state['services'][0]['lcn_candidates']),2)
        diff=self.core.call('diff_snapshots',{'from_packet':1,'to_packet':2})
        self.assertEqual(diff['summary']['services']['changed'],0)
    def test_table_groups_numeric_pid_order_and_timing_units(self):
        state=self.scan([self.pat(),self.pmt(),self.sdt(last=0),self.nit()])
        self.assertEqual([g['pid'] for g in state['table_groups']],[0,0x10,0x11,0x100])
        self.assertIsNone(state['timing']['seconds_per_packet']);self.assertFalse(state['timing']['pcr_derived'])
        state=self.scan([self.sdt(last=0)],bitrate=1504)
        self.assertEqual(state['timing']['seconds_per_packet'],1)

if __name__=='__main__': unittest.main()
