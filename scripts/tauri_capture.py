import time,json,urllib.request,socket,subprocess,os,sys
from ui_common import *
out=ROOT/'artifacts';out.mkdir(exist_ok=True);trace=out/'tauri-visual.trace.jsonl';trace.write_text('')
with socket.socket() as s:s.bind(('127.0.0.1',9333))
real='--real' in sys.argv
env=environment('samples/real/tnt-uhf22-2019.ts' if real else 'samples/generated/lab.ts',trace);env['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS']='--remote-debugging-port=9333';env['WEBVIEW2_USER_DATA_FOLDER']=str(out/'webview-profile-smoke')
with (out/'tauri-runtime.log').open('w',encoding='utf-8') as log:
    proc=launch('tauri',env,log)
    try:
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            try:
                with urllib.request.urlopen('http://127.0.0.1:9333/json/version',timeout=1) as r:
                    if r.status==200:break
            except Exception:pass
            if proc.poll() is not None:raise RuntimeError('Tauri exited: '+str(proc.returncode))
            time.sleep(.2)
        else:raise TimeoutError('CDP unavailable')
        nodeenv=os.environ.copy();nodeenv['NODE_PATH']=str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules')
        nodeenv['SHOWPSISI_CAPTURE_REAL']='1' if real else '0'
        result=subprocess.run(['node','scripts/web_smoke.cjs'],cwd=ROOT,env=nodeenv,text=True,encoding='utf-8',timeout=60,capture_output=True)
        print(result.stdout);print(result.stderr);print(json.dumps(marks(trace)))
        if result.returncode:raise RuntimeError('Web UI checks failed')
    finally:print(json.dumps(stop(proc)))
