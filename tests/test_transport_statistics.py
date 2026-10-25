"""Production-engine checks for scan-global, bounded transport/PID counters."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core,CoreError

def packet(pid=0x100):
    return bytes([0x47,(pid>>8)&31,pid&255,0x10])+b'\xff'*184
def framed(packets,width):
    if width==188:return b''.join(packets)
    if width==192:return b''.join(i.to_bytes(4,'big')+p for i,p in enumerate(packets))
    return b''.join(p+b'\0'*16 for p in packets)

class TransportStatisticsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.core=Core();self.addCleanup(self.core.close)
        self.input_sequence=0
    def analyze(self,packets,width=188,**options):
        path=Path(self.temp.name)/'transport.ts';path.write_bytes(framed(packets,width))
        self.input_path=path
        self.original_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        result=self.core.call('analyze',{'path':str(path),'standards':'dvb','response_mode':'compact',**options})
        self.revision=result['analysis_revision']
        self.input_sequence+=1
        evidence=os.environ.get('SHOWPSISI_TRANSPORT_EVIDENCE_DIR')
        if evidence:
            inputs=Path(evidence)/'inputs';inputs.mkdir(parents=True,exist_ok=True)
            stem=self._testMethodName+'-'+str(self.input_sequence)
            (inputs/(stem+'.ts')).write_bytes(path.read_bytes())
            (inputs/(stem+'.json')).write_text(__import__('json').dumps({
                'file':stem+'.ts','sha256':self.original_hash,'bytes':path.stat().st_size,
                'analysis_revision':self.revision,'framing_bytes':width,'options':options},indent=2),encoding='utf-8')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),self.original_hash)
        return result
    def page(self,**options):
        return self.core.call('query_transport',{'analysis_revision':self.revision,**options})
    def test_framing_packet_share_and_missing_clock(self):
        for width in (188,192,204):
            with self.subTest(width=width):
                state=self.analyze([packet(0x100),packet(8191),packet(0x100),packet(0x101)]*8,width)
                self.assertEqual(state['packet_size'],width)
                summary=state['transport_summary']
                self.assertEqual(summary['observed_packets'],32)
                self.assertEqual(summary['pid_count'],3)
                self.assertFalse(summary['pcr_derived'])
                self.assertIsNone(summary['configured_bitrate_bps'])
                self.assertIsNone(summary['observed_duration_seconds'])
                page=self.page()
                self.assertEqual([(r['pid'],r['packets']) for r in page['items']],[(256,16),(257,8),(8191,8)])
                self.assertEqual(page['items'][0]['packet_fraction'],.5)
                self.assertIsNone(page['items'][0]['bitrate_bps'])
                self.assertIsNone(page['items'][0]['packets_per_second'])
    def test_supplied_rate_is_normalized_and_explicit(self):
        state=self.analyze([packet(0x100),packet(8191)]*16,204,bitrate=1504000)
        self.assertEqual(state['transport_summary']['rate_basis'],'user supplied normalized 188-byte TS bitrate')
        self.assertAlmostEqual(state['transport_summary']['observed_duration_seconds'],.032)
        row=self.page()['items'][0]
        self.assertEqual(row['bitrate_bps'],752000)
        self.assertEqual(row['packets_per_second'],500)
    def test_unique_error_packets_and_scrambling_is_not_an_error(self):
        packets=[packet(0x100),packet(8191),packet(0x100),packet(0x101)]*8
        bad=bytearray(packets[0]);bad[1]|=0x80;packets[0]=bytes(bad)
        bad=bytearray(packets[1]);bad[3]|=0x80;packets[1]=bytes(bad)
        bad=bytearray(packets[2]);bad[3]=0;packets[2]=bytes(bad)
        bad=bytearray(packets[7]);bad[0]=0x46;packets[7]=bytes(bad)
        state=self.analyze(packets)
        summary=state['transport_summary']
        self.assertEqual((summary['error_packets'],summary['tei_packets'],summary['malformed_header_packets'],summary['bad_sync_packets'],summary['scrambled_packets']),(3,1,1,1,1))
        page=self.page(errors_only=True)
        self.assertEqual(page['total'],1)
        self.assertEqual(page['items'][0]['pid'],256)
        self.assertEqual(sum(r['packets'] for r in self.page()['items']),31)
    def test_paging_sort_and_revision_schema_guards(self):
        self.analyze([packet(0x100),packet(0x101),packet(8191),packet(8191)]*8)
        first=self.page(limit=1,sort='packets',descending=True)
        self.assertEqual(first['items'][0]['pid'],8191)
        second=self.page(limit=1,sort='packets',descending=True,offset=first['next_offset'])
        self.assertEqual(second['items'][0]['pid'],256)
        for params in ({'analysis_revision':self.revision+1},{'analysis_revision':self.revision,'limit':101},{'analysis_revision':self.revision,'offset':8193},{'analysis_revision':self.revision,'at_packet':0}):
            with self.subTest(params=params),self.assertRaises(CoreError):self.core.call('query_transport',params)
    def test_distributed_observed_scope_and_historical_selection(self):
        state=self.analyze([packet(256),packet(257)]*32,scan_mode='distributed',max_packets=16,window_count=2)
        self.assertTrue(state['coverage']['partial'])
        self.assertEqual(state['transport_summary']['observed_packets'],16)
        before=self.page()
        historical=self.core.call('query',{'at_packet':3,'response_mode':'compact'})
        self.assertEqual(historical['transport_summary']['observed_packets'],16)
        self.assertEqual(self.page(),before)
        self.assertEqual(sum(r['packets'] for r in before['items']),16)
        self.assertIn('not the selected historical cutoff',before['summary']['scope'])
    def test_failed_and_new_analysis_do_not_retain_old_pid_rows(self):
        self.analyze([packet(256)]*16)
        old=self.revision
        with self.assertRaises(CoreError):self.core.call('analyze',{'path':str(Path(self.temp.name)/'missing.ts')})
        with self.assertRaises(CoreError):self.core.call('query_transport',{'analysis_revision':old})
        self.analyze([packet(257)]*8)
        self.assertEqual([(r['pid'],r['packets']) for r in self.page()['items']],[(257,8)])
    def test_bad_sync_error_has_unattributed_aggregate(self):
        packets=[packet(256)]*32
        bad=bytearray(packets[7]);bad[0]=0x46;packets[7]=bytes(bad)
        self.analyze(packets)
        page=self.page(errors_only=True)
        self.assertEqual(page['total'],0)
        self.assertEqual(page['aggregate_errors'][0]['count'],1)
        self.assertIsNone(page['aggregate_errors'][0]['pid'])
        self.assertIsNone(page['aggregate_errors'][0]['id'])
        self.assertTrue(page['aggregate_errors'][0]['aggregate'])
    def test_real_engine_component_evidence(self):
        packets=[packet(256),packet(257),packet(8191),packet(256)]*8
        bad=bytearray(packets[0]);bad[1]|=0x80;packets[0]=bytes(bad)
        state=self.analyze(packets)
        state['diagnostics']=[]
        evidence={'state':state,'summary':self.page(),'errors':self.page(errors_only=True),
                  'sorted':self.page(sort='packets',descending=True)}
        evidence['rateState']=self.analyze([packet(256),packet(8191)]*16,bitrate=1504000)
        evidence['ratePage']=self.page()
        evidence['partialState']=self.analyze([packet(pid) for pid in range(256,391)],scan_mode='distributed',max_packets=16,window_count=2)
        evidence['partialPage']=self.page()
        evidence['emptyState']=self.analyze([packet(256)]*32)
        evidence['emptyErrors']=self.page(errors_only=True,sort='packets',descending=True)
        evidence['pagingState']=self.analyze([packet(pid) for pid in range(256,391)])
        evidence['pagingSecond']=self.page(offset=100)
        packets=[packet(256)]*32
        bad=bytearray(packets[7]);bad[0]=0x46;packets[7]=bytes(bad)
        self.analyze(packets)
        evidence['syncState']=self.core.call('query')
        evidence['syncErrors']=self.page(errors_only=True)
        from make_fixture import section,word
        raw=section(0,0x1001,1,word(101)+word(0xe100))
        corrupt=bytearray(raw);corrupt[-1]^=1
        def psi(data,cc):
            return bytes([0x47,0x40,0,0x10|cc,0])+data+b'\xff'*(183-len(data))
        self.analyze([psi(raw,0),psi(bytes(corrupt),3)]+[packet(256)]*30)
        evidence['diagnosticState']=self.core.call('query')
        evidence['diagnosticErrors']=self.page(errors_only=True)
        self.assertTrue(any(row.get('id') and not row.get('aggregate') for row in evidence['diagnosticState']['diagnostics']))
        self.assertTrue(any(row.get('aggregate') for row in evidence['diagnosticState']['diagnostics']))
        directory=Path(os.environ.get('SHOWPSISI_TRANSPORT_EVIDENCE_DIR',ROOT/'artifacts/transport-summary'));directory.mkdir(parents=True,exist_ok=True)
        (directory/'engine-evidence.json').write_text(__import__('json').dumps(evidence,indent=2),encoding='utf-8')
if __name__=='__main__':unittest.main()
