"""Independently read the latest outputs of both UI smoke checks with tstables."""
import json,subprocess,xml.etree.ElementTree as ET
from pathlib import Path
from core_client import Core,ROOT
results=[]
for ui in ['qt','tauri']:
    path=max((ROOT/'artifacts').glob(ui+'-export-*.ts'),key=lambda p:p.stat().st_mtime)
    xml=ROOT/'artifacts'/f'{ui}-export-verified.xml'
    command=['C:/Program Files/TSDuck/bin/tstables.exe',str(path),'--pid','17','--xml-output',str(xml)]
    run=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
    if run.returncode:raise RuntimeError(run.stderr)
    tree=ET.parse(xml);sdt=tree.find('.//SDT');service=tree.find('.//service[@service_id="0x0067"]/service_descriptor')
    assert service is not None and service.attrib['service_name']=='UI verified rename'
    assert sdt.attrib['version']=='4'
    with Core() as core:state=core.call('analyze',{'path':str(path)})
    assert state['crc_errors']==0 and state['demux']['discontinuities']==0 and len(state['services'])==6
    results.append({'ui':ui,'file':str(path),'command':command,'tsduck_exit':run.returncode,'service_id':103,'name':service.attrib['service_name'],'version':4,'crc_errors':0,'continuity_errors':0})
(ROOT/'artifacts/export-readback.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print('Both latest GUI exports independently decoded by TSDuck: service 103 renamed, SDT v4, valid CRC and continuity.')
