import time,json,sys
from ui_common import *
out=ROOT/'artifacts';out.mkdir(exist_ok=True);trace=out/'qt-visual.trace.jsonl';trace.write_text('')
real='--real' in sys.argv
env=environment('samples/real/tnt-uhf22-2019.ts' if real else 'samples/generated/lab.ts',trace);env['SHOWPSISI_SCREENSHOT']=str(out/('qt-real.png' if real else 'qt-quick.png'));env['SHOWPSISI_SCRIPT']='' if real else 'smoke';env['SHOWPSISI_TEST_RESULT']=str(out/'qt-ui-test.json');env['SHOWPSISI_ARTIFACT_DIR']=str(out)
with (out/'qt-runtime.log').open('w',encoding='utf-8') as log:
    proc=launch('qt',env,log)
    try:
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            if any(x['event']==('screenshot_saved' if real else 'ui_test_done') for x in marks(trace)):break
            if proc.poll() is not None:raise RuntimeError('Qt exited: '+str(proc.returncode))
            time.sleep(.1)
        else:raise TimeoutError('Qt screenshot did not complete')
        print(json.dumps(marks(trace)))
    finally:print(json.dumps(stop(proc)))
