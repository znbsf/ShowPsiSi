"""CLI and automation client for the shared native engine. UTF-8 JSON Lines."""
import json, os, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Core:
    def __init__(self):
        executable=Path(os.environ.get('SHOWPSISI_CORE',str(ROOT/'build/bin'/('showpsisi-core.exe' if os.name=='nt' else 'showpsisi-core'))))
        self.proc=subprocess.Popen([str(executable),'--root',str(ROOT)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)); self.seq=0
    def call(self,method,params=None,progress=None):
        self.seq+=1; self.proc.stdin.write(json.dumps({'id':self.seq,'method':method,'params':params or {}})+'\n');self.proc.stdin.flush()
        for line in self.proc.stdout:
            msg=json.loads(line)
            if 'event' in msg:
                if progress: progress(msg)
                continue
            if msg.get('id')!=self.seq: raise RuntimeError('Response ID mismatch')
            if 'error' in msg: raise RuntimeError(msg['error']['message'])
            return msg['result']
        raise RuntimeError('Native engine exited: '+self.proc.stderr.read())
    def close(self):
        self.proc.stdin.close()
        try:self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait()
        self.proc.stdout.close();self.proc.stderr.close()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
if __name__=='__main__':
    with Core() as core:
        if len(sys.argv)>1: print(json.dumps(core.call(sys.argv[1],json.loads(sys.argv[2]) if len(sys.argv)>2 else {}),ensure_ascii=False,indent=2))
        else:
            for line in sys.stdin:
                r=json.loads(line)
                try: print(json.dumps({'id':r.get('id'),'result':core.call(r['method'],r.get('params'))},ensure_ascii=False),flush=True)
                except Exception as e: print(json.dumps({'id':r.get('id'),'error':str(e)}),flush=True)
