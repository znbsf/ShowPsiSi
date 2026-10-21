import json,sys,unittest
from pathlib import Path
from service_identity_fixture import fixture
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from core_client import Core

class ServiceIdentityTests(unittest.TestCase):
    def test_names_keep_transport_network_and_descriptor_provenance(self):
        out=ROOT/'artifacts/unified-inspector';out.mkdir(parents=True,exist_ok=True)
        evidence={};core=Core()
        try:
            for ambiguous in [False,True]:
                label='ambiguous' if ambiguous else 'distinct'
                path=out/('service-'+label+'.ts');path.write_bytes(fixture(ambiguous))
                state=core.call('analyze',{'path':str(path),'standards':'dvb'})
                self.assertEqual(state['crc_errors'],0)
                services={(s['onid'],s['ts_id'],s['id']):s for s in state['services']}
                self.assertEqual(len(services),5 if ambiguous else 4)
                for key,name in [((0x2001,0x1001,101),'Alpha News'),((0x2001,0x1001,102),'Beta Music'),((0x2001,0x1002,101),'Other Transport')]:
                    service=services[key];self.assertEqual(service['name'],name);self.assertTrue(service['name_from_descriptor'])
                    source=core.call('inspect',{'id':service['source_id']})
                    self.assertEqual(source['name'],'SDT');self.assertEqual(source['extension'],key[1]);self.assertEqual(source['fields']['original_network_id'],key[0])
                    self.assertTrue(any(d.get('fields',{}).get('name')==name for d in source['descriptors']))
                self.assertFalse(services[(0x2001,0x1001,103)]['name_from_descriptor'])
                self.assertNotIn((0x2001,0x1001,104),services)
                if ambiguous:self.assertEqual(services[(0x2002,0x1001,101)]['name'],'Other Network')
                evidence[label]={'state':state,'details':[core.call('inspect',{'id':r['id']}) for r in state['tables'] if r['name']=='PAT']}
            (out/'service-identity-evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        finally:core.close()

if __name__=='__main__':unittest.main()
