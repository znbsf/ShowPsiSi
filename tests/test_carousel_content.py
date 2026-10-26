"""Actual core DSM-CC/BIOP bytes, identity and safe content interpretation."""
import hashlib,struct,tempfile,unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from core_client import Core,CoreError
import test_dsmcc_summaries as f

def biop(kind,body,key=b'',info=b''):
 payload=bytes([len(key)])+key+struct.pack('>I',4)+kind+struct.pack('>H',len(info))+info+b'\0'+struct.pack('>I',len(body))+body
 return b'BIOP\x01\0\0\0'+struct.pack('>I',len(payload))+payload
def file(content,key=b'f'):return biop(b'fil\0',struct.pack('>I',len(content))+content,key,struct.pack('>Q',len(content)))
def directory(key=b'd',target=b'f',name=b'file'):
 profile=bytes([len(target)])+target+b'fil\0\0\0'
 binding=b'\x01'+bytes([len(name)])+name+b'\0\x01'+struct.pack('>II',1,1)+struct.pack('>II',0x49534f06,len(profile))+profile+b'\0\0'
 return biop(b'dir\0',b'\0\x01'+binding,key)
def carousel(modules,missing=(),pid=0x150,download=0x10203040):
 pairs=[(pid,f.dii([f.declaration(module=m,size=len(raw)) for m,raw in modules],block_size=128,download=download))]
 for m,raw in modules:
  for block,offset in enumerate(range(0,len(raw),128)):
   if (m,block) not in missing:pairs.append((pid,f.ddb(raw[offset:offset+128],module=m,block=block,download=download)))
 return pairs
class CarouselContentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.core=Core();self.addCleanup(self.core.close);self.path=Path(self.tmp.name)/'carousel.ts'
 def load(self,pairs):
  self.path.write_bytes(f.packetize(pairs));self.state=self.core.call('analyze',{'path':str(self.path),'standards':'dvb','extra_pids':sorted({p for p,_ in pairs})});self.source=next(r['id'] for r in self.state['tables'] if r['table_id']==0x3b);self.base={'analysis_revision':self.state['revision'],'source_id':self.source};self.root=self.read();return self.root
 def read(self,**kw):return self.core.call('query_carousel',{**self.base,**kw})
 def module(self,index=0,**kw):
  m=self.root['modules'][index];return self.read(module_id=m['module_id'],module_version=m['module_version'],announcement_epoch_order=m['announcement_epoch_order'],**kw)
 def test_complete_multiple_and_empty_files_exact_offsets_hash_and_paging(self):
  raw=file(b'hello',b'a')+file(b'',b'b');self.load(carousel([(7,raw)]));r=self.module();self.assertTrue(r['biop']['complete']);self.assertEqual(len(r['biop']['objects']),2);a=self.module(object_offset=0,limit=2);self.assertEqual(a['content']['raw_hex'],'6865');self.assertEqual(a['content']['next_offset'],2);self.assertEqual(a['content']['sha256'],hashlib.sha256(b'hello').hexdigest());b=self.module(object_offset=len(file(b'hello',b'a')));self.assertEqual(b['content']['total_bytes'],0);self.assertEqual(b['content']['sha256'],hashlib.sha256(b'').hexdigest())
 def test_missing_blocks_never_fabricate_content(self):
  self.load(carousel([(7,file(b'x'*300))],missing=((7,1),)));m=self.root['modules'][0];self.assertEqual(m['status'],'incomplete');self.assertIn(1,m['missing_blocks']);self.assertIsNone(m['sha256']);self.assertNotIn('content',self.module(object_offset=0))
 def test_bad_tail_keeps_validated_prefix(self):
  self.load(carousel([(7,file(b'ok')+b'bad tail')]));r=self.module();self.assertFalse(r['biop']['complete']);self.assertEqual(r['biop']['error_offset'],len(file(b'ok')));self.assertEqual(self.module(object_offset=0)['content']['text'],'ok')
 def test_directory_exact_key_resolution_and_duplicates(self):
  self.load(carousel([(7,directory()+file(b'ok'))]));r=self.module(object_offset=0);p=r['bindings'][0]['profiles'][0];self.assertEqual(p['resolution'],'resolved');self.assertEqual(p['target']['object_offset'],len(directory()))
  self.load(carousel([(7,directory()+file(b'a')+file(b'b'))]));r=self.module(object_offset=0);self.assertEqual(r['bindings'][0]['profiles'][0]['resolution'],'ambiguous_key');self.assertNotIn('target',r['bindings'][0]['profiles'][0])
 def test_normative_object_location_cross_module_does_not_use_biop_version_as_module_version(self):
  location=bytes([0,1])+b'ISOP'+bytes([10])+struct.pack('>IHBBB',0x10203040,8,1,0,1)+b'f'
  binding=b'\x01\x04file\0\x01'+struct.pack('>II',1,1)+struct.pack('>II',0x49534f06,len(location))+location+b'\0\0'
  raw=biop(b'dir\0',b'\0\x01'+binding,b'd')
  self.load(carousel([(7,raw),(8,file(b'right'))]));r=self.module(object_offset=0);p=r['bindings'][0]['profiles'][0];self.assertTrue(p['location_parsed']);self.assertEqual(p['resolution'],'resolved');self.assertEqual(p['target']['module_id'],8);self.assertEqual(p['target']['module_version'],3)
 def test_dsi_gateway_to_exact_module_and_object(self):
  location=bytes([0,1])+b'ISOP'+bytes([10])+struct.pack('>IHBBB',0x10203040,7,1,0,1)+b'd'
  ior=struct.pack('>II',0,1)+struct.pack('>II',0x49534f06,len(location))+location
  dsi=f.message(0x3b,b'\0'*20+b'\0\0'+struct.pack('>H',len(ior))+ior,message_id=0x1006)
  self.load([(0x150,dsi)]+carousel([(7,directory()+file(b'right'))]));self.assertIn('gateway',self.root);self.assertEqual(self.root['download_id'],0x10203040);r=self.module(object_key_hex='64');self.assertEqual(r['object']['type'],'dir');self.assertEqual(r['object']['offset'],0)
 def test_dsi_multiple_downloads_require_explicit_declared_selection(self):
  profiles=[]
  for download in (0x10203040,99):
   location=bytes([0,1])+b'ISOP'+bytes([10])+struct.pack('>IHBBB',download,7,1,0,1)+b'd';profiles.append(struct.pack('>II',0x49534f06,len(location))+location)
  ior=struct.pack('>II',0,2)+b''.join(profiles);dsi=f.message(0x3b,b'\0'*20+b'\0\0'+struct.pack('>H',len(ior))+ior,message_id=0x1006)
  self.load([(0x150,dsi)]+carousel([(7,directory())]));self.assertEqual(self.root['status'],'download_selection_required');self.assertEqual(self.root['modules'],[]);self.assertTrue(self.read(download_id=0x10203040)['modules'])
  with self.assertRaises(CoreError):self.read(download_id=123)
 def test_key_never_resolves_across_download(self):
  self.load(carousel([(7,directory())])+carousel([(8,file(b'foreign'))],download=99));r=self.module(object_offset=0);self.assertEqual(r['bindings'][0]['profiles'][0]['resolution'],'missing_key')
 def test_file_inventory_retains_modules_and_excludes_incomplete_bytes(self):
  self.load(carousel([(7,file(b'a',b'a')+file(b'b',b'b')),(8,file(b'x'*300))],missing=((8,1),)));r=self.read(inventory=True);self.assertEqual(len(r['inventory']),2);self.assertEqual({o['module_id'] for o in r['inventory']},{7});self.assertEqual(len(r['modules']),2);self.assertFalse(r['inventory_limited'])
 def test_file_info_mismatch_and_short_alternate_ior_are_errors(self):
  bad=biop(b'fil\0',struct.pack('>I',1)+b'a',b'f',struct.pack('>Q',2));self.load(carousel([(7,bad)]));self.assertIn('content size mismatch',self.module()['biop']['error'])
  binding=b'\x01\x01x\0\x01'+struct.pack('>II',0,0xffffffff)
  self.load(carousel([(7,biop(b'dir\0',b'\0\x01'+binding,b'd'))]));self.assertFalse(self.module()['biop']['complete'])
 def test_stale_identity_and_invalid_offsets_rejected(self):
  self.load(carousel([(7,file(b'ok'))]));m=self.root['modules'][0]
  with self.assertRaises(CoreError):self.read(module_id=7)
  with self.assertRaises(CoreError):self.read(module_id=7,module_version=3,announcement_epoch_order=m['announcement_epoch_order']+1)
  with self.assertRaises(CoreError):self.module(object_offset=1)
  with self.assertRaises(CoreError):self.module(object_offset=0,offset=3)
 def test_configuration_unknown_encoding_retains_original(self):
  self.load(carousel([(7,file(b'\xff\xfe\0x'))]));c=self.module(object_offset=0)['content'];self.assertEqual(c['encoding'],'unknown');self.assertEqual(c['raw_hex'],'FFFE0078');self.assertNotIn('text',c);self.assertEqual(c['execution'],'not_executed')
 def test_class_names_counts_and_truncated_class_safe(self):
  def utf(s):return b'\x01'+struct.pack('>H',len(s))+s
  raw=bytes.fromhex('cafebabe000000340005')+utf(b'Example')+b'\x07\0\x01'+utf(b'java/lang/Object')+b'\x07\0\x03'+bytes.fromhex('0021000200040000000000000000')
  self.load(carousel([(7,file(raw))]));c=self.module(object_offset=0)['content']['class_info'];self.assertEqual(c['status'],'parsed');self.assertEqual(c['class_name'],'Example');self.assertEqual(c['super_name'],'java/lang/Object');self.assertEqual(c['methods_count'],0)
  self.load(carousel([(7,file(raw[:12]))]));self.assertEqual(self.module(object_offset=0)['content']['class_info']['status'],'invalid_or_unsupported')
if __name__=='__main__':unittest.main()
