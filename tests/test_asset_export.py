"""Exact source/derived exports, selection guards and no-replace publication."""
import base64,hashlib,json,os,tempfile,unittest,wave
from pathlib import Path
from core_client import Core,CoreError
from test_media_inspection import pes
from test_teletext_inspection import packetize
from test_carousel_content import carousel,file
import test_dsmcc_summaries as dsm
class AssetExportTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.core=Core();self.addCleanup(self.core.close);self.path=self.root/'source.ts';self.n=0
 def load(self,data,**kw):
  self.path.write_bytes(data);self.state=self.core.call('analyze',{'path':str(self.path),'standards':'dvb',**kw});self.rev=self.state['revision']
 def save(self,kind,**kw):
  self.n+=1;path=self.root/('输出-😀-'+str(self.n));r=self.core.call('export_asset',{'analysis_revision':self.rev,'path':str(path),'kind':kind,**kw});raw=path.read_bytes();manifest=json.loads(Path(r['manifest']).read_text());self.assertEqual(r['bytes'],len(raw));self.assertEqual(r['sha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(manifest['sha256'],r['sha256']);self.assertEqual(manifest['source'],str(self.path));self.assertEqual(manifest['analysis_revision'],self.rev);self.assertFalse(list(self.root.glob('*.tmp*')));return raw,r
 def test_pes_es_packet_frame_and_report_exact_bytes(self):
  raw=pes(bytes(range(256))*3,pts=90001);data=packetize([raw],stride=192,first_capacity=2);self.load(data)
  self.assertEqual(self.save('pes',pid=0x202,pes_index=0)[0],raw);self.assertEqual(self.save('es',pid=0x202,pes_index=0)[0],bytes(range(256))*3)
  self.assertEqual(self.save('packet',packet_index=0)[0],data[4:192]);self.assertEqual(self.save('packet_frame',packet_index=0)[0],data[:192]);report=json.loads(self.save('report')[0]);self.assertEqual(report['source'],str(self.path));self.assertIn('coverage',report)
 def test_section_module_object_empty_and_complete_bytes(self):
  content=b'config=real\n'*400;module=file(content)+file(b'',b'empty');pairs=carousel([(7,module)]);self.load(dsm.packetize(pairs),extra_pids=[0x150]);source=next(r['id'] for r in self.state['tables'] if r['table_id']==0x3b);base={'analysis_revision':self.rev,'source_id':source};r=self.core.call('query_carousel',base);m=r['modules'][0];q={'source_id':source,'module_id':7,'module_version':m['module_version'],'announcement_epoch_order':m['announcement_epoch_order']}
  self.assertEqual(self.save('section',source_id=source)[0],pairs[0][1]);self.assertEqual(self.save('module',**q)[0],module);self.assertEqual(self.save('object',object_offset=0,**q)[0],content);self.assertEqual(self.save('object',object_offset=len(file(content)),**q)[0],b'')
 def test_missing_blocks_and_wrong_epoch_no_output(self):
  self.load(dsm.packetize(carousel([(7,file(b'x'*300))],missing=((7,1),))),extra_pids=[0x150]);source=next(r['id'] for r in self.state['tables'] if r['table_id']==0x3b);r=self.core.call('query_carousel',{'analysis_revision':self.rev,'source_id':source});m=r['modules'][0]
  for epoch in (m['announcement_epoch_order'],m['announcement_epoch_order']+1):
   with self.assertRaises(CoreError):self.save('object',source_id=source,module_id=7,module_version=m['module_version'],announcement_epoch_order=epoch,object_offset=0)
  self.assertEqual(sorted(p.name for p in self.root.iterdir()),['source.ts'])
 def test_existing_output_manifest_failure_and_stale_source_preserved(self):
  self.load(packetize([pes()]));path=self.root/'existing';path.write_bytes(b'keep')
  with self.assertRaises(CoreError):self.core.call('export_asset',{'analysis_revision':self.rev,'kind':'report','path':str(path)})
  self.assertEqual(path.read_bytes(),b'keep');manifest=self.root/'blocked.manifest.json';manifest.write_text('keep');
  with self.assertRaises(CoreError):self.core.call('export_asset',{'analysis_revision':self.rev,'kind':'report','path':str(self.root/'blocked')})
  self.assertFalse((self.root/'blocked').exists());self.path.write_bytes(b'changed')
  with self.assertRaises(CoreError):self.save('report')
  self.assertFalse(list(self.root.glob('*.tmp*')))
 def test_stale_revision_bad_selection_and_missing_parent_leave_no_output(self):
  self.load(packetize([pes()]));base={'analysis_revision':self.rev,'kind':'pes','path':str(self.root/'out'),'pid':0x202,'pes_index':99}
  for q in [base,{**base,'analysis_revision':self.rev+1},{**base,'pes_index':0,'path':str(self.root/'missing'/'out')},{**base,'kind':'png','preview_token':'foreign','frame_index':0}]:
   with self.assertRaises(CoreError):self.core.call('export_asset',q)
  self.assertEqual([p.name for p in self.root.iterdir()],['source.ts'])
 @unittest.skipUnless(os.environ.get('SHOWPSISI_FFMPEG'),'External pinned decoder required')
 def test_png_and_wav_are_exact_decoded_previews_and_retire(self):
  # The shared fixture generator returns a real MPEG source, never fake frame data.
  import subprocess
  tool=os.environ['SHOWPSISI_FFMPEG']
  def create(args):
   target=self.root/'generated.ts'
   if target.exists():target.unlink()
   r=subprocess.run([tool,'-nostdin','-hide_banner','-loglevel','error','-threads','1','-filter_threads','1','-f','lavfi','-i',*args,'-f','mpegts',str(target)],capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));self.assertEqual(r.returncode,0,r.stderr);self.load(target.read_bytes());return next(s['pid'] for s in self.state['media_streams'] if s['is_video'] or s['is_audio'])
  pid=create(['color=c=blue:s=64x48:r=25:d=0.08','-frames:v','2','-c:v','mpeg2video','-g','1']);v=self.core.call('decode_media',{'analysis_revision':self.rev,'pid':pid,'kind':'video','request_token':'v'});self.assertEqual(self.save('png',preview_token=v['preview_token'],frame_index=0)[0],base64.b64decode(v['frames'][0]['data_base64']))
  pid=create(['anullsrc=r=48000:cl=mono:d=0.2','-c:a','mp2','-b:a','128k']);a=self.core.call('decode_media',{'analysis_revision':self.rev,'pid':pid,'kind':'audio','request_token':'a'});raw,r=self.save('wav',preview_token=a['preview_token']);import io
  with wave.open(io.BytesIO(raw),'rb') as w:self.assertEqual((w.getnchannels(),w.getframerate(),w.getsampwidth()),(1,48000,2));self.assertEqual(hashlib.sha256(w.readframes(w.getnframes())).hexdigest(),a['pcm']['sha256'])
  with self.assertRaises(CoreError):self.save('png',preview_token=v['preview_token'],frame_index=0)
