import os,sys,json,time,subprocess,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
from ui_agent import request
out=root/('artifacts/unified-inspector/full-app-keyboard-'+str(time.time_ns()))
out.mkdir(exist_ok=True)
session=out/'session'
sdk=Path(r'C:\Users\hentai\Documents\ShowPsiSi\.deps\Qt\6.7.3\msvc2019_64')
env=os.environ.copy()
env.update(PATH=str(sdk/'bin')+os.pathsep+env['PATH'],QT_QPA_PLATFORM_PLUGIN_PATH=str(sdk/'plugins/platforms'),QML_IMPORT_PATH=str(sdk/'qml'),QT_QUICK_BACKEND='software',QT_SCALE_FACTOR='1.5',QT_ENABLE_HIGHDPI_SCALING='0',QT_FORCE_STDERR_LOGGING='1',SHOWPSISI_ROOT=str(root),SHOWPSISI_CORE=str(root/'build/bin/showpsisi-core.exe'),SHOWPSISI_SAMPLE=str(root/'artifacts/unified-inspector/fixture.ts'),SHOWPSISI_SETTINGS_PATH=str(out/'settings.ini'),SHOWPSISI_AGENT_DIR=str(session),SHOWPSISI_AUTO='1',SHOWPSISI_SCRIPT='',SHOWPSISI_THEME='light')
report={'checks':{},'captures':{},'kind':'full native application with real backend and synthetic fixture','dpi_scale':1.5}
def wait_state(predicate,timeout=40):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if proc.poll() is not None:raise RuntimeError('Application exited '+str(proc.returncode))
        if (session/'session.json').exists():
            s=request(session,'snapshot')
            if predicate(s):return s
        time.sleep(.1)
    raise TimeoutError('App state timeout')
def settled():return wait_state(lambda s:s.get('settled') and s.get('analysis_status')=='complete')
def action(name,**kw):return request(session,'action',dict(name=name,**kw))
log=(out/'application.log').open('w')
proc=subprocess.Popen([str(root/'build/bin/showpsisi-qt.exe')],cwd=root,env=env,stdout=log,stderr=log)
try:
    s=settled();report['checks']['opened']=s['unified']['visible'] and not s['diagnostics']['error']
    action('window_size',width=1280,height=800)
    rows=s['unified']['records'];pat=next(r for r in rows if r['name']=='PAT')
    for name in ['PAT','PMT','BAT','TDT','TOT']:
        row=next(r for r in rows if r['name']==name)
        action('unified_select',id=row['id']);s=settled()
        if name=='PMT':
            paths=[n['path'] for n in s['unified']['nodes'] if 'descriptors/0/decoded' in n['path']]
            if paths:action('unified_path',path=paths[0])
        action('unified_hex',value=name=='BAT');time.sleep(.3)
        report['captures'][name]=request(session,'capture')
        report['checks'][name+'_selected']=s['inspection']['id']==row['id']
    action('unified_select',id=pat['id']);settled();action('unified_path',path='section/decoded')
    pmt=next(r for r in rows if r['name']=='PMT');action('unified_select',id=pmt['id']);settled();action('topology_key',value='Alt+Left');s=settled()
    report['checks']['back_preserves_path']=s['inspection']['id']==pat['id'] and s['unified']['path']=='section/decoded'
    action('rescan');s=settled();report['checks']['repeat_open']=len(s['unified']['records'])==len(rows)
    action('topology_key',value='F6');action('topology_key',value='Home');action('topology_key',value='Return');s=settled()
    report['checks']['keyboard_home_enter']=s['inspection']['id']==pat['id']
    large=out/'cancel-fixture.ts'
    chunk=(bytes([0x47,0x1f,0xff,0x10])+b'\xff'*184)*8192
    with large.open('wb') as f:
        for _ in range(512):f.write(chunk)
    action('open_source',path=str(large));wait_state(lambda s:s['scan']['busy'] and not s['scan']['presentation'])
    report['checks']['pause_click']=action('scan_control',value='pauseAnalysis')['accepted']
    s=wait_state(lambda s:s['scan']['paused']);frozen=s['scan']['progress'].get('packets')
    time.sleep(1);s=request(session,'snapshot')
    report['checks']['paused_frozen']=s['scan']['paused'] and s['scan']['progress'].get('packets')==frozen
    report['checks']['resume_click']=action('scan_control',value='pauseAnalysis')['accepted']
    s=wait_state(lambda s:not s['scan']['paused'] and not s['scan']['pause_pending'])
    report['checks']['resumed']=not s['scan']['paused'] and not s['scan']['pause_pending']
    action('scan_control',value='pauseAnalysis');wait_state(lambda s:s['scan']['paused'])
    action('cancel_scan');s=wait_state(lambda s:s['analysis_status']=='cancelled' and s['settled'])
    report['checks']['cancel']=s['analysis_status']=='cancelled'
    action('open_source',path=str(root/'artifacts/unified-inspector/fixture.ts'));s=settled()
    report['checks']['reopen_after_cancel']=len(s['unified']['records'])==len(rows)
    for mode in ['prefix','range','distributed']:
        action('scan_mode',value=mode);action('rescan');s=settled();coverage=s['scan']['coverage']
        report['checks'][mode+'_coverage']=coverage['scanned_packets']==(6 if mode=='range' else 1)
    action('scan_mode',value='full')
    from make_fixture import section,word,crc
    packets=[]
    for i in range(101):
        raw=section(0,i+1,1,word(100)+word(0xe100))
        packets.append(bytes([0x47,0x40,0,0x10+(i%16),0])+raw+b'\xff'*(183-len(raw)))
    pages=out/'pages.ts';pages.write_bytes(b''.join(packets));action('open_source',path=str(pages));s=settled()
    report['checks']['all_101_hydrated']=len(s['unified']['records'])==101
    report['checks']['next_page_click']=action('scan_control',value='unifiedNext')['accepted']
    action('topology_key',value='F6');action('topology_key',value='Home');action('topology_key',value='Return');s=settled()
    report['checks']['page2_select']=s['inspection']['id']==s['unified']['records'][100]['id']
    report['captures']['page2']=request(session,'capture')
    packets=[]
    for i in [0,8]:
        raw=bytearray(section(0x50,1,1,word(1)+word(2)+bytes([i,0x50])))
        raw[6]=i;raw[7]=8;raw[-4:]=crc(raw[:-4]).to_bytes(4,'big')
        packets.append(bytes([0x47,0x40,0x12,0x10+(i%16),0])+raw+b'\xff'*(183-len(raw)))
    eit=out/'eit.ts';eit.write_bytes(b''.join(packets));action('open_source',path=str(eit));s=settled()
    report['checks']['eit_two_sections']=len(s['unified']['records'])==2 and {r['section'] for r in s['unified']['records']}=={0,8}
    for row in s['unified']['records']:
        action('unified_select',id=row['id']);ss=settled()
        report['checks']['eit_section_'+str(row['section'])]=ss['inspection']['id']==row['id']
    action('unified_hex',value=True);report['captures']['EIT']=request(session,'capture')
except Exception as e:report['error']=repr(e)
finally:
    proc.terminate()
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
    log.close()
    (out/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
sys.exit(0 if 'error' not in report and report['checks'] and all(report['checks'].values()) else 1)
