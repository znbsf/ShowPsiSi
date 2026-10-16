"""Sequential release UI trials, complete owned process-tree accounting, no CDP."""
import argparse,hashlib,statistics,platform
import psutil
from ui_common import *

def run_trial(ui,sample,index,out):
    trace=out/f'{ui}-{index}.jsonl';trace.write_text('');env=environment(sample,trace,delay=1200)
    env.pop('WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS',None);env.pop('SHOWPSISI_SCRIPT',None);env.pop('SHOWPSISI_SCREENSHOT',None)
    env['WEBVIEW2_USER_DATA_FOLDER']=str(out/'webview-profile')
    samples=[];seen={};started=time.time()*1000;cleanup={}
    with (out/f'{ui}-{index}.log').open('w',encoding='utf-8') as log:
        proc=launch(ui,env,log);parent=psutil.Process(proc.pid)
        try:
            deadline=time.monotonic()+25;done_at=None
            while time.monotonic()<deadline:
                if proc.poll() is not None:raise RuntimeError(f'{ui} exited {proc.returncode}')
                tree=[parent]+parent.children(recursive=True);rss=private=0
                for p in tree:
                    try:
                        with p.oneshot():
                            mem=p.memory_info();cpu=p.cpu_times();identity=(p.pid,p.create_time());rss+=mem.rss;private+=mem.private
                            exe=seen.get(identity,{}).get('exe') or p.exe()
                            seen[identity]={'pid':p.pid,'name':p.name(),'exe':exe,'cpu_seconds':cpu.user+cpu.system}
                    except psutil.NoSuchProcess:pass
                samples.append({'wall_ms':time.time()*1000,'rss_mib':rss/1048576,'private_mib':private/1048576,'processes':len(tree)})
                events=marks(trace)
                if any(e['event']=='complete_paint' for e in events):
                    if done_at is None:done_at=time.monotonic()
                    if time.monotonic()-done_at>=.6:break
                time.sleep(.02)
            else:raise TimeoutError(f'{ui}: no complete paint')
            event={e['event']:e for e in events};request=event['analyze_requested'];idle=[s for s in samples if request['wall_ms']-450<s['wall_ms']<request['wall_ms']-50]
            if not idle:raise RuntimeError('Missing idle measurement window')
            result={'ui':ui,'index':index,'startup_ui_ready_ms':event['ui_ready']['wall_ms']-started,'first_paint_after_analyze_ms':event['first_paint']['ms']-request['ms'],'complete_paint_after_analyze_ms':event['complete_paint']['ms']-request['ms'],'idle_private_mib':statistics.median(s['private_mib'] for s in idle),'loaded_private_mib':samples[-1]['private_mib'],'peak_private_mib':max(s['private_mib'] for s in samples),'peak_working_set_sum_mib':max(s['rss_mib'] for s in samples),'cpu_seconds_total':sum(p['cpu_seconds'] for p in seen.values()),'process_count_peak':max(s['processes'] for s in samples),'processes':list(seen.values()),'marks':events,'resource_samples':samples}
        finally:cleanup=stop(proc)
    if not cleanup['all_exited']:raise RuntimeError('Owned process cleanup incomplete')
    result['cleanup']=cleanup;print(json.dumps({k:v for k,v in result.items() if k not in ['marks','resource_samples','processes','cleanup']}),flush=True);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--sample',default='samples/real/tnt-uhf22-2019.ts');ap.add_argument('--trials',type=int,default=3);a=ap.parse_args()
    out=ROOT/'artifacts/benchmark';out.mkdir(parents=True,exist_ok=True)
    # Populate filesystem cache equally; this is deliberately not a cold-disk test.
    with (ROOT/a.sample).open('rb') as f:
        while f.read(4*1024*1024):pass
    profile_preexisting=(out/'webview-profile').exists();results=[]
    for i in range(a.trials):
        for ui in (['qt','tauri'] if i%2==0 else ['tauri','qt']):results.append(run_trial(ui,a.sample,i+1,out))
    metrics=['startup_ui_ready_ms','first_paint_after_analyze_ms','complete_paint_after_analyze_ms','idle_private_mib','loaded_private_mib','peak_private_mib','peak_working_set_sum_mib','cpu_seconds_total','process_count_peak']
    report={'sample':a.sample,'sample_bytes':(ROOT/a.sample).stat().st_size,'sample_sha256':hashlib.sha256((ROOT/a.sample).read_bytes()).hexdigest(),'backend_sha256':hashlib.sha256((ROOT/'build/bin/showpsisi-core.exe').read_bytes()).hexdigest(),'ui_sha256':{u:hashlib.sha256(p.read_bytes()).hexdigest() for u,p in APPS.items()},'platform':platform.platform(),'cpu':platform.processor(),'logical_cpus':psutil.cpu_count(),'total_ram_gib':psutil.virtual_memory().total/1024**3,'method':'Release; warmed source filesystem cache; sequential alternating order; 20ms process tree polling; 1.2s pre-scan idle; no debugger/CDP. First paint is Qt frameSwapped / Web double requestAnimationFrame (render opportunity, not physical display proof). Working-set sum can double-count shared pages. CPU covers startup + idle + scan + 0.6s settle, not scan only. Initial WebView profile creation included in first Tauri trial.','median':{u:{m:statistics.median(r[m] for r in results if r['ui']==u) for m in metrics} for u in APPS},'trials':results}
    report['profile_preexisting']=profile_preexisting
    report['method']=report['method'].replace('Initial WebView profile creation included in first Tauri trial.','WebView profile pre-existence recorded in profile_preexisting; profile creation is included only when absent.')
    (out/'results.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report['median'],indent=2),flush=True)
if __name__=='__main__':main()
