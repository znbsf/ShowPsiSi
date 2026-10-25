"""Real-engine source component regression with retained failure evidence.

This standalone receipt records binary/source/input hashes. It does not prove
that those binaries were built from the recorded source; CI build records and
the complete workbench/native acceptance remain separate gates.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
from qt_process import stop_qt_process

ROOT=Path(__file__).resolve().parents[2]

def atomic_json(path,value):
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')
    temporary.replace(path)

def fingerprint(path):
    path=Path(path).resolve()
    data=path.read_bytes()
    return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def text_output(value):
    if value is None:return ''
    return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else value

def stop_owned(process):
    if os.name=='nt':
        stop_qt_process(process)
    else:
        # Popen created this separate session; only its owned group is targeted.
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=5)

def execute(args,directory,name,env,timeout=90):
    atomic_json(directory/(name+'.command.json'),args)
    status={'phase':name,'started':False,'timed_out':False}
    out=err=''
    try:
        process=subprocess.Popen(args,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,encoding='utf-8',errors='replace',start_new_session=os.name!='nt',
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        status.update(started=True,owned_pid=process.pid)
        try:
            out,err=process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            out,err=text_output(error.output),text_output(error.stderr)
            status['timed_out']=True
            try:stop_owned(process)
            except Exception as cleanup_error:
                status['cleanup_error']=repr(cleanup_error)
            try:out,err=process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                status['drain_incomplete']=True
            raise
        status['returncode']=process.returncode
        if process.returncode:
            raise RuntimeError(f'{name} exited {process.returncode}\n'+(out+err)[-12000:])
        return out+'\n'+err
    except BaseException as error:
        status.update(error_type=type(error).__name__,error=str(error))
        raise
    finally:
        active_failure=sys.exc_info()[0] is not None
        try:
            (directory/(name+'.stdout.log')).write_text(text_output(out),encoding='utf-8')
            (directory/(name+'.stderr.log')).write_text(text_output(err),encoding='utf-8')
            atomic_json(directory/(name+'.status.json'),status)
        except Exception as retention_error:
            if not active_failure:raise
            print(f'{name}: evidence retention also failed: {retention_error!r}',file=sys.stderr)

def run(binary,artifacts,qt_sdk=None):
    directory=Path(artifacts).resolve()/('run-'+str(time.time_ns()))
    directory.mkdir(parents=True,exist_ok=False)
    result={'scope':'real-engine source components; not full workbench/native interaction',
        'passed':False,'stage':'validation',
        'source_to_build_binding':'not established by this standalone receipt; use separate build/CI provenance',
        'binaries':{},'source_files':[]}
    try:
        binary=Path(binary).resolve()
        result['binaries']['runner']=fingerprint(binary)
        engine=os.environ.get('SHOWPSISI_CORE')
        if not engine:raise RuntimeError('SHOWPSISI_CORE must name the matching production engine')
        result['binaries']['engine']=fingerprint(engine)
        sidecar=Path(engine).resolve().parent/'showpsisi-build.json'
        if sidecar.is_file():result['declared_build_record']=fingerprint(sidecar)
        for relative in ('core/SiWireFields.h','core/main.cpp','ui/qt/UnifiedInspector.qml','ui/qt/TransportSummary.qml','ui/qt/InspectorModel.js',
                         'tests/qml_unified/tst_unified.qml','tests/qml_transport/tst_transport.qml',
                         'tests/test_unified_inspector.py','tests/test_transport_statistics.py'):
            result['source_files'].append({'file':relative,**fingerprint(ROOT/relative)})
        env=os.environ.copy()
        env.update(QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software',
            QT_QUICK_CONTROLS_STYLE='Basic',QT_FORCE_STDERR_LOGGING='1',
            QML_XHR_ALLOW_FILE_READ='1',QML_DISABLE_DISK_CACHE='1')
        result['component_scale_factor']=env.get('QT_SCALE_FACTOR','platform default')
        if qt_sdk:
            sdk=Path(qt_sdk).resolve()
            if not sdk.is_dir():raise RuntimeError('Missing Qt SDK')
            env['PATH']=str(sdk/'bin')+os.pathsep+env.get('PATH','')
            env['QML_IMPORT_PATH']=str(sdk/'qml')
        if os.name=='nt' and not env.get('QT_QPA_FONTDIR'):
            fonts=Path(env.get('WINDIR',r'C:\Windows'))/'Fonts'
            if not fonts.is_dir():raise RuntimeError('Provide QT_QPA_FONTDIR for Windows offscreen tests')
            env['QT_QPA_FONTDIR']=str(fonts)
        unified=directory/'unified';transport=directory/'transport'
        env['SHOWPSISI_UNIFIED_EVIDENCE_DIR']=str(unified)
        env['SHOWPSISI_TRANSPORT_EVIDENCE_DIR']=str(transport)
        for pattern in ('test_unified_inspector.py','test_transport_statistics.py'):
            result['stage']='producer:'+pattern
            log=execute([sys.executable,'-X','utf8','-B','-m','unittest','discover','-s','tests','-p',pattern,'-v'],directory,pattern,env)
            if not re.search(r'Ran [1-9][0-9]* tests?',log) or not re.search(r'\bOK\b',log) or 'skipped=' in log:
                raise RuntimeError('Missing/failed real-engine evidence producer: '+pattern)
        result['stage']='prepare-qml'
        qml=directory/'qml';qml.mkdir()
        for source,fixture in (('qml_unified',unified),('qml_transport',transport)):
            text=(ROOT/'tests'/source/('tst_'+('unified' if source=='qml_unified' else 'transport')+'.qml')).read_text(encoding='utf-8')
            text=text.replace('import "../../ui/qt"','import '+json.dumps((ROOT/'ui/qt').as_uri()))
            original='../../artifacts/'+('unified-inspector' if source=='qml_unified' else 'transport-summary')
            text=text.replace(original,fixture.as_uri())
            (qml/('tst_'+source+'.qml')).write_text(text,encoding='utf-8')
        result['stage']='components'
        log=execute([str(binary),'-input',str(qml),'-o','-,txt'],directory,'qt-components',env)
        totals=re.findall(r'Totals: (\d+) passed, (\d+) failed, (\d+) skipped, (\d+) blacklisted',log)
        if not totals or any(int(v) for row in totals for v in row[1:]):
            raise RuntimeError('QtTest totals absent or include failure/skip/blacklist\n'+log[-14000:])
        counts={}
        for name,source in (('UnifiedInspectorRealEngineEvidence','qml_unified/tst_unified.qml'),('TransportSummaryRealEngineEvidence','qml_transport/tst_transport.qml')):
            expected=len(re.findall(r'function test_[A-Za-z0-9_]+\(', (ROOT/'tests'/source).read_text(encoding='utf-8')))
            if not expected:raise RuntimeError('Component suite has no test functions')
            count=len(re.findall(r'PASS\s+:[^\n]*::'+name+r'::test_[^\n]*\(\)',log))
            if count!=expected:raise RuntimeError(f'{name}: expected {expected} executed tests, got {count}\n'+log[-12000:])
            counts[name]=count
        if re.search(r'TypeError|ReferenceError|Unable to assign|Binding loop|QFATAL|FAIL!',log):
            raise RuntimeError('Qt diagnostics failed\n'+log[-14000:])
        screenshots=list(unified.glob('*.png'))+list(transport.glob('*.png'))
        if len(screenshots)!=8 or any(p.stat().st_size==0 for p in screenshots):
            raise RuntimeError('All eight component screenshots must complete')
        result.update(passed=True,stage='complete',tests=counts,totals=totals,
            screenshots=[str(p.relative_to(directory)) for p in screenshots])
    except BaseException as error:
        result.update(error_type=type(error).__name__,error=str(error))
        raise
    finally:
        active_failure=sys.exc_info()[0] is not None
        try:
            result['evidence_files']=[{'file':str(p.relative_to(directory)),**fingerprint(p)}
                for p in sorted(directory.rglob('*')) if p.is_file() and p.name!='result.json' and not p.name.endswith('.tmp')]
            atomic_json(directory/'result.json',result)
        except Exception as retention_error:
            if not active_failure:raise
            print(f'Component receipt retention also failed: {retention_error!r}',file=sys.stderr)
    return {'evidence':str(directory),**result}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--binary',required=True,type=Path)
    parser.add_argument('--artifacts',required=True,type=Path)
    parser.add_argument('--qt-sdk',type=Path)
    args=parser.parse_args()
    result=run(args.binary,args.artifacts,args.qt_sdk)
    print(json.dumps({k:result[k] for k in ('evidence','scope','passed','stage','tests','totals','screenshots')},indent=2))
if __name__=='__main__':main()
