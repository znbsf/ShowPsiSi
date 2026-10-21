import os,sys,json,time,subprocess,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
from ui_agent import request
out=root/('artifacts/unified-inspector/service-visual-'+str(time.time_ns()))
out.mkdir(exist_ok=True)
session=out/'session'
common=Path(subprocess.check_output(['git','rev-parse','--git-common-dir'],cwd=root,text=True).strip())
if not common.is_absolute():common=root/common
sdk=Path(os.environ.get('SHOWPSISI_QT_ROOT',str(common.resolve().parent/'.deps/Qt/6.7.3/msvc2019_64')))
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
    from service_identity_fixture import fixture
    settled();action('window_size',width=1280,height=800)
    for ambiguous in [False,True]:
        label='ambiguous' if ambiguous else 'distinct'
        path=out/(label+'.ts');path.write_bytes(fixture(ambiguous));action('open_source',path=str(path));s=settled()
        for tsid in [0x1001,0x1002]:
            row=next(r for r in s['unified']['records'] if r['name']=='PAT' and r['extension']==tsid)
            action('unified_select',id=row['id']);s=settled()
            summary=next(c['text'] for c in s['controls'] if c['id']=='unifiedSummary')
            report.setdefault('services',{})[label]=s['unified'].get('services',[]);key=label+'-'+str(tsid);report.setdefault('summaries',{})[key]=summary
            if tsid==0x1002:passed='Other Transport' in summary and 'Alpha News' not in summary and 'Beta Music' not in summary
            else:
                passed='Beta Music' in summary and summary.count('name unknown')==2 and 'Service 103' not in summary and 'Other Transport' not in summary and 'Other Network' not in summary
                passed=passed and (('ambiguous service identity' in summary and 'Alpha News' not in summary) if ambiguous else 'Alpha News' in summary)
            report['checks'][key]=passed;report['captures'][key]=request(session,'capture')
except Exception as e:report['error']=repr(e)
finally:
    proc.terminate()
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
    log.close();(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
sys.exit(0 if 'error' not in report and len(report['checks'])==4 and all(report['checks'].values()) else 1)
