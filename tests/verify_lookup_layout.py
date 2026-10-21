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

for advanced,auto in [('0','0'),('1','0'),('0','1'),('1','1')]:
    tag='advanced'+advanced+'-auto'+auto
    session=out/tag
    env.update(SHOWPSISI_AGENT_DIR=str(session),SHOWPSISI_ADVANCED=advanced,SHOWPSISI_AUTO=auto,QT_LOGGING_RULES='qt.quick.layouts.debug=true')
    with (out/(tag+'.log')).open('w',encoding='utf-8') as log:
        proc=subprocess.Popen([str(root/'build/bin/showpsisi-qt.exe')],cwd=root,env=env,stdout=log,stderr=log)
        try:
            s=wait_state(lambda s:s.get('settled'));time.sleep(1)
        finally:
            proc.terminate();proc.wait(timeout=10)
    data=(out/(tag+'.log')).read_text(encoding='utf-8');print(tag,data.count('recursive rearrange'),len(data),out,flush=True)

assert all('recursive rearrange' not in f.read_text(encoding='utf-8') for f in out.glob('advanced*.log'))
