import os,sys,json,time,subprocess,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'scripts'))
from ui_agent import request
out=root/('artifacts/unified-inspector/native-picker-'+str(time.time_ns()))
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
    import ctypes as c
    from ctypes import wintypes as w
    u=c.WinDLL('user32',use_last_error=True)
    callback=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
    u.SendMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
    u.SendMessageW.restype=w.LPARAM
    u.GetDlgItem.argtypes=[w.HWND,c.c_int];u.GetDlgItem.restype=w.HWND
    def children(hwnd):
        result=[]
        @callback
        def visit(h,p):
            cls=c.create_unicode_buffer(256);u.GetClassNameW(h,cls,256)
            result.append((h,cls.value,u.GetDlgCtrlID(h)));return True
        u.EnumChildWindows(hwnd,visit,0);return result
    s=settled();report['checks']['open_clicked']=action('scan_control',value='openSource')['accepted']
    dialogs=[]
    @callback
    def visit(h,p):
        pid=w.DWORD();u.GetWindowThreadProcessId(h,c.byref(pid));cls=c.create_unicode_buffer(256);u.GetClassNameW(h,cls,256)
        if pid.value==proc.pid and cls.value=='#32770' and u.IsWindowVisible(h):dialogs.append(h)
        return True
    for _ in range(30):
        u.EnumWindows(visit,0)
        if dialogs:break
        time.sleep(.1)
    assert len(set(dialogs))==1,dialogs
    dlg=dialogs[0];items=children(dlg);report['native_controls']=[(cls,i) for h,cls,i in items]
    combo=next(h for h,cls,i in items if i==1148 and cls=='ComboBox')
    edit=next(h for h,cls,i in children(combo) if cls=='Edit')
    target=out/'picker-selected.ts';target.write_bytes((root/'artifacts/unified-inspector/fixture.ts').read_bytes())
    path=c.create_unicode_buffer(str(target))
    u.SendMessageW(edit,0x000C,0,c.cast(path,c.c_void_p).value)
    ok=u.GetDlgItem(dlg,1);assert ok
    u.PostMessageW(ok,0x00F5,0,0)
    s=wait_state(lambda s:s.get('settled') and s.get('source')==str(target))
    report['checks']['native_picker_loaded_selected_path']=s['analysis_status']=='complete'
except Exception as e:report['error']=repr(e)
finally:
    proc.terminate()
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:proc.kill();proc.wait()
    log.close();(out/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

sys.exit(0 if 'error' not in report and all(report['checks'].values()) else 1)
