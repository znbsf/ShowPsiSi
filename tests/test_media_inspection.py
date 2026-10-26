"""Original PES/ES fragments and bounded real decoder/output lifecycle."""
import base64,hashlib,io,json,os,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from core_client import Core,CoreError
from test_teletext_inspection import packetize

def pes(payload=b'original-es',stream=0xe0,unbounded=False,pts=None):
 stamp=b''
 if pts is not None:stamp=bytes([0x21|((pts>>29)&14),(pts>>22)&255,1|((pts>>14)&254),(pts>>7)&255,1|((pts<<1)&254)])
 body=bytes([0x80,0x80 if stamp else 0,len(stamp)])+stamp+payload
 return b'\0\0\x01'+bytes([stream])+struct.pack('>H',0 if unbounded else len(body))+body
class PesInspectionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'媒体-😀.ts';self.core=Core();self.addCleanup(self.core.close)
 def load(self,data):self.data=data;self.path.write_bytes(data);self.state=self.core.call('analyze',{'path':str(self.path),'standards':'dvb'});self.rev=self.state['revision'];return self.read()
 def read(self,**kw):return self.core.call('query_pes',{'analysis_revision':self.rev,'pid':0x202,**kw})
 def test_original_pes_es_pages_and_ts_fragments(self):
  data=bytes(range(256))*3;raw=pes(data,pts=90001);self.load(packetize([raw]));r=self.read(pes_index=0,layer='es',offset=150,limit=250);s=r['selected'];self.assertEqual(s['pts'],90001);self.assertEqual(s['content']['sha256'],hashlib.sha256(data).hexdigest());self.assertEqual(bytes.fromhex(s['content']['raw_hex']),data[150:400]);self.assertEqual(b''.join(self.data[f['file_offset']:f['file_offset']+f['length']] for f in s['source_fragments']),data[150:400]);self.assertEqual(s['content']['pes_offset'],14+150)
 def test_unbounded_video_delimiters_and_scan_cutoff(self):
  self.load(packetize([pes(b'first',unbounded=True),pes(b'second',unbounded=True)]));r=self.read(pes_limit=1);self.assertEqual(r['pes_total'],2);self.assertEqual(r['pes_next_offset'],1);self.assertIn('unbounded',r['pes'][0]['completion_basis']);self.assertEqual(self.read(pes_index=1,layer='es')['selected']['content']['raw_hex'],'7365636F6E64');self.assertEqual(self.read(scan_limit=1)['pes_total'],0)
 def test_192_204_frames_and_split_pes_header(self):
  for stride in (188,192,204):
   self.load(packetize([pes(b'mapped')],stride=stride,first_capacity=2));r=self.read(pes_index=0,layer='pes');s=r['selected'];self.assertEqual(bytes.fromhex(s['content']['raw_hex']),pes(b'mapped'));self.assertEqual(b''.join(self.data[f['file_offset']:f['file_offset']+f['length']] for f in s['source_fragments']),pes(b'mapped'));self.assertTrue(all(f['framing_stride']==stride for f in s['source_fragments']))
 def test_bad_pes_pointer_and_scrambled_transport_do_not_yield_pes(self):
  self.load(packetize([b'\0'+pes()]));self.assertEqual(self.read()['pes_total'],0)
  bad=bytearray(packetize([pes()]));bad[3]|=0x80;self.load(bytes(bad));self.assertEqual(self.read()['pes_total'],0);self.assertGreater(self.read()['scan']['errors'],0)
 def test_paging_stale_revision_offset_and_source_guards(self):
  self.load(packetize([pes()]));
  for args in ({'pes_index':1},{'pes_index':0,'offset':999},{'analysis_revision':self.rev+1},{'pid':8191}):
   with self.assertRaises(CoreError):self.read(**args)
  self.path.write_bytes(self.data+b'\0'*188)
  with self.assertRaises(CoreError):self.read()
 def test_wrong_media_cancel_cannot_affect_evidence(self):
  self.load(packetize([pes()]));r=self.core.call('cancel_media',{'analysis_revision':self.rev,'request_token':'unknown'});self.assertFalse(r['requested']);self.assertEqual(self.read()['pes_total'],1)

class MediaCancellationContractTests(unittest.TestCase):
 def test_queued_decode_wrong_target_analysis_isolation_and_late_cancel(self):
  from test_cancellation import Wire,HELPER
  if not HELPER.is_file():self.fail('Matching opt-in SHOWPSISI_TEST_CORE required for deterministic media cancellation')
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory)/'queued.ts';path.write_bytes(packetize([pes()]))
   wire=Wire(directory,stage='before_complete')
   try:
    wire.send(1,'analyze',{'path':str(path),'standards':'dvb'});wire.gate()
    request={'analysis_revision':1,'pid':0x202,'kind':'video','request_token':'queued-media'};wire.send(2,'decode_media',request)
    self.assertFalse(wire.call(3,'cancel_media',{'analysis_revision':2,'request_token':'queued-media'})['result']['requested'])
    self.assertFalse(wire.call(4,'cancel_analysis',{'request_id':2})['result']['requested'])
    self.assertTrue(wire.call(5,'cancel_media',{'analysis_revision':1,'request_token':'queued-media'})['result']['requested'])
    self.assertTrue(wire.call(6,'cancel_media',{'analysis_revision':1,'request_token':'queued-media'})['result']['requested'])
    wire.release();self.assertTrue(wire.response(1)['result']['complete']);self.assertEqual(wire.response(2)['error']['code'],'media_cancelled')
    self.assertFalse(wire.call(7,'cancel_media',{'analysis_revision':1,'request_token':'queued-media'})['result']['requested'])
    self.assertEqual(wire.call(8,'query_pes',{'analysis_revision':1,'pid':0x202})['result']['pes_total'],1)
   finally:wire.close()

class DecoderInspectionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  if os.name!='nt':raise unittest.SkipTest('Pinned decode/device execution is currently Windows-only')
  cls.tool=Path(os.environ.get('SHOWPSISI_FFMPEG',''))
  if not cls.tool.is_file():raise unittest.SkipTest('External pinned SHOWPSISI_FFMPEG is required for real decode tests')
  cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup);cls.video=Path(cls.temp.name)/'video.ts';cls.audio=Path(cls.temp.name)/'audio.ts';cls.silence=Path(cls.temp.name)/'silence.ts'
  def create(path,args):
   command=[str(cls.tool),'-nostdin','-hide_banner','-loglevel','error','-threads','1','-filter_threads','1','-f','lavfi','-i',*args,'-f','mpegts',str(path)];r=subprocess.run(command,capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));assert r.returncode==0,r.stderr.decode(errors='replace')
  create(cls.video,['color=c=0x123456:s=64x48:r=25:d=0.2','-frames:v','5','-c:v','mpeg2video','-g','1','-pix_fmt','yuv420p'])
  create(cls.audio,['sine=frequency=440:sample_rate=48000:duration=0.25','-af','volume=0.05','-ac','1','-c:a','mp2','-b:a','128k'])
  create(cls.silence,['anullsrc=r=48000:cl=mono:d=0.3','-c:a','mp2','-b:a','128k'])
 def setUp(self):self.core=Core();self.addCleanup(self.core.close)
 def load(self,path,kind):
  s=self.core.call('analyze',{'path':str(path),'standards':'dvb'});self.rev=s['revision'];self.pid=next(r['pid'] for r in s['media_streams'] if r['is_video' if kind=='video' else 'is_audio']);return s
 def decode(self,kind,token='decode',**kw):return self.core.call('decode_media',{'analysis_revision':self.rev,'pid':self.pid,'kind':kind,'request_token':token,**kw})
 def test_real_video_pixels_input_hash_and_retired_request_token(self):
  from PIL import Image
  self.load(self.video,'video');v=self.decode('video',token='reusable');self.assertEqual(v['frame_count'],5);self.assertTrue(v['decoder']['verified']);self.assertTrue(v['decoder_process']['exited']);
  for frame in v['frames']:
   raw=base64.b64decode(frame['data_base64']);self.assertEqual(hashlib.sha256(raw).hexdigest(),frame['sha256']);image=Image.open(io.BytesIO(raw)).convert('RGB');pixel=image.getpixel((image.width//2,image.height//2));self.assertTrue(all(abs(a-b)<6 for a,b in zip(pixel,(0x12,0x34,0x56))),pixel)
  second=self.decode('video',token='reusable');self.assertNotEqual(v['preview_token'],second['preview_token']);self.assertFalse(self.core.call('cancel_media',{'analysis_revision':self.rev,'request_token':'reusable'})['requested'])
 def test_real_audio_pcm_and_waveform(self):
  self.load(self.audio,'audio');r=self.decode('audio');p=r['pcm'];self.assertEqual(p['sample_rate'],48000);self.assertEqual(p['channels'],1);self.assertEqual(p['bytes'],p['samples']*2);self.assertGreater(p['samples'],10000);self.assertEqual(len(p['waveform']),512);self.assertLess(min(b['min'] for b in p['waveform']),-100);self.assertGreater(max(b['max'] for b in p['waveform']),100)
 def test_silent_device_stop_and_stale_token_isolation(self):
  self.load(self.silence,'audio');r=self.decode('audio');self.assertLessEqual(max(abs(b['min'])+abs(b['max']) for b in r['pcm']['waveform']),2);base={'analysis_revision':self.rev,'preview_token':r['preview_token']}
  result=self.core.call('audio_control',{**base,'action':'play'});self.assertTrue(result['matching_preview']);self.assertTrue(result['playing']);self.assertFalse(self.core.call('audio_control',{**base,'preview_token':'foreign','action':'stop'})['matching_preview']);self.assertTrue(self.core.call('audio_control',{**base,'action':'pause'})['paused']);self.assertFalse(self.core.call('audio_control',{**base,'action':'stop'})['playing']);self.load(self.video,'video');self.assertFalse(self.core.call('audio_control',{**base,'action':'play'})['matching_preview'])
 def test_wrong_decoder_digest_is_not_executed(self):
  with patch.dict(os.environ,SHOWPSISI_FFMPEG=sys.executable):
   with Core() as wrong:
    s=wrong.call('analyze',{'path':str(self.video),'standards':'dvb'})
    with self.assertRaisesRegex(CoreError,'SHA-256'):
     wrong.call('decode_media',{'analysis_revision':s['revision'],'pid':256,'kind':'video','request_token':'bad-tool'})
 def test_accepted_cancel_owns_decoder_exit_and_preserves_analysis(self):
  self.load(self.video,'video');events=[];acks=[]
  def progress(event):
   if event.get('phase')=='decoder_started':
    events.append(event);self.assertFalse(self.core.call('cancel_media',{'analysis_revision':self.rev+1,'request_token':'cancel-me'})['requested']);acks.append(self.core.call('cancel_media',{'analysis_revision':self.rev,'request_token':'cancel-me'}))
  future=self.core.submit('decode_media',{'analysis_revision':self.rev,'pid':self.pid,'kind':'video','request_token':'cancel-me'},progress)
  try:result=future.result(timeout=12)
  except CoreError as e:
   self.assertEqual(e.code,'media_cancelled');self.assertTrue(acks[-1]['requested'])
  else:self.assertFalse(acks[-1]['requested'],'An accepted cancellation cannot publish success')
  self.assertEqual(len(events),1);self.assertGreater(events[0]['decoder_pid'],0);self.assertFalse(self.core.call('cancel_media',{'analysis_revision':self.rev,'request_token':'cancel-me'})['requested']);self.assertGreater(self.core.call('query_pes',{'analysis_revision':self.rev,'pid':self.pid})['pes_total'],0)
if __name__=='__main__':unittest.main()
