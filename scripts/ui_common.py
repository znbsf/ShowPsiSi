import os, subprocess, json, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APPS={'qt':ROOT/'build/bin/showpsisi-qt.exe','tauri':ROOT/'ui/tauri/src-tauri/target/release/showpsisi-tauri.exe'}
def environment(sample,trace,auto=True,delay=0):
    env=os.environ.copy();env.update(SHOWPSISI_ROOT=str(ROOT),SHOWPSISI_CORE=str(ROOT/'build/bin/showpsisi-core.exe'),SHOWPSISI_SAMPLE=str(ROOT/sample),SHOWPSISI_AUTO='1' if auto else '0',SHOWPSISI_AUTO_DELAY_MS=str(delay),SHOWPSISI_TRACE=str(trace))
    qt=ROOT/'.deps/Qt/6.7.3/msvc2019_64';env['PATH']=str(qt/'bin')+os.pathsep+env['PATH'];env['QT_QPA_PLATFORM_PLUGIN_PATH']=str(qt/'plugins/platforms')
    return env
def launch(ui,env,log):
    return subprocess.Popen([str(APPS[ui])],cwd=ROOT,env=env,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
def marks(trace):
    if not trace.exists():return []
    result=[]
    for line in trace.read_text(encoding='utf-8').splitlines():
        try:result.append(json.loads(line))
        except json.JSONDecodeError:pass
    return result
def stop(proc):
    import psutil
    try:
        parent=psutil.Process(proc.pid);children=parent.children(recursive=True)
        parent.terminate()
        _,alive=psutil.wait_procs([parent],timeout=2)
        for p in alive:p.kill()
        # All children are captured from the exact owned root before termination.
        for child in children:
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        _,alive=psutil.wait_procs(children,timeout=3)
        for p in alive:
            try:p.kill()
            except psutil.NoSuchProcess:pass
        psutil.wait_procs(alive,timeout=2)
        proc.wait(timeout=3)
        return {'root_pid':proc.pid,'owned_pids':[c.pid for c in children],'all_exited':all(not p.is_running() for p in [parent]+children)}
    except psutil.NoSuchProcess:proc.wait(timeout=3);return {'root_pid':proc.pid,'all_exited':True}
