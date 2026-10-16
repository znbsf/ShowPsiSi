"""Minimal MCP stdio adapter. No GUI automation and no model provider required."""
import json, sys
from core_client import Core,ROOT
sys.stdout.reconfigure(encoding='utf-8');sys.stdin.reconfigure(encoding='utf-8')
def send(value): print(json.dumps(value,ensure_ascii=False),flush=True)
with Core() as core:
    tools=core.call('capabilities')['tools']
    for line in sys.stdin:
        try:
            r=json.loads(line);rid=r.get('id');method=r.get('method')
            if rid is None:continue
            if method=='initialize': result={'protocolVersion':'2025-06-18','capabilities':{'tools':{}},'serverInfo':{'name':'ShowPsiSi','version':'0.1.0'},'instructions':'Analyze first. Inspect source IDs and packet provenance. Preview edits before exporting to a new path. Source bytes are never edited.'}
            elif method=='ping': result={}
            elif method=='tools/list': result={'tools':tools}
            elif method=='tools/call':
                p=r['params']
                try:
                    data=core.call(p['name'],p.get('arguments',{})); result={'content':[{'type':'text','text':json.dumps(data,ensure_ascii=False)}],'structuredContent':data,'isError':False}
                except Exception as e:result={'content':[{'type':'text','text':str(e)}],'isError':True}
            else:
                send({'jsonrpc':'2.0','id':rid,'error':{'code':-32601,'message':'Method not found'}});continue
            send({'jsonrpc':'2.0','id':rid,'result':result})
        except Exception as e: send({'jsonrpc':'2.0','id':None,'error':{'code':-32700,'message':str(e)}})
