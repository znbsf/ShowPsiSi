"""Compiled Qt transport / pause / coverage regressions against the real core.

Missing binaries are not substitutes for acceptance: strict native CI provides both.
The after_progress seam is compiled only in the dedicated test engine.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import test_qt_ui as qt_tests
ROOT = qt_tests.ROOT


class QtAnalysisModes(unittest.TestCase):
    def run_script(self, script, directory, **kwargs):
        overrides=kwargs.setdefault('overrides',{})
        overrides.setdefault('SHOWPSISI_TRACE',str(Path(directory)/'trace.jsonl'))
        evidence=os.environ.get('SHOWPSISI_QT_TEST_ARTIFACTS')
        variant=overrides.get('SHOWPSISI_PAGE_FAULT') or overrides.get('SHOWPSISI_QUICK_INDEX')
        if evidence and variant:
            with mock.patch.dict(os.environ,{'SHOWPSISI_QT_TEST_ARTIFACTS':str(Path(evidence)/str(variant))}):
                report=qt_tests.NativeQtTests.run_script(self,script,directory,**kwargs)
                self.assert_busy_through_compact_terminal(overrides['SHOWPSISI_TRACE'])
                return report
        report=qt_tests.NativeQtTests.run_script(self,script,directory,**kwargs)
        self.assert_busy_through_compact_terminal(overrides['SHOWPSISI_TRACE'])
        return report
    def assert_busy_through_compact_terminal(self, trace):
        events=[json.loads(line)['event'] for line in Path(trace).read_text().splitlines() if line]
        self.assertNotIn('compact_terminal_idle_error',events)
        self.assertIn('compact_terminal_busy',events)
        limits=[int(event.rsplit('_',1)[1]) for event in events if event.startswith('page_request_limit_')]
        rows=[int(event.rsplit('_',1)[1]) for event in events if event.startswith('page_rows_')]
        self.assertTrue(limits, 'No compact page request was observed')
        self.assertTrue(rows, 'No validated compact page was observed')
        self.assertTrue(all(0 < limit <= 50 for limit in limits), limits)
        self.assertTrue(all(0 <= count <= 50 for count in rows), rows)
    cancellation_helper = qt_tests.NativeQtTests.cancellation_helper

    def pause_workflow(self, mode):
        with tempfile.TemporaryDirectory(prefix='qt-analysis-pause-') as directory:
            gate = Path(directory) / 'gate'
            trace = Path(directory) / 'trace.jsonl'
            released = False
            def advance(_):
                nonlocal released
                if not released and trace.exists():
                    events = [json.loads(line)['event'] for line in trace.read_text().splitlines() if line]
                    if 'pause_analysis_ack' in events:
                        self.assertTrue(gate.with_suffix('.ready').exists())
                        gate.with_suffix('.release').touch()
                        released = True
            report = self.run_script(mode, directory, auto=False, timeout=45, on_running=advance,
                overrides={'SHOWPSISI_CORE': str(self.cancellation_helper()),
                           'SHOWPSISI_TEST_GATE': str(gate), 'SHOWPSISI_TEST_STAGE': 'after_progress',
                           'SHOWPSISI_TRACE': str(trace)})
            self.assertTrue(released, 'The owner checkpoint was never released after the pause ACK')
            for key in ('pause_control', 'pause_pending', 'authoritative_paused', 'local_theme',
                        'no_inspection', 'frozen', 'settled', 'responsive'):
                self.assertTrue(report['checks'][key], report)
            self.assertGreaterEqual(report['ticks'], 20)
            self.assertLess(report['max_gui_gap_ms'], 500, report)
            events = [json.loads(line)['event'] for line in trace.read_text().splitlines()]
            self.assertLess(events.index('pause_analysis_ack'), events.index('paused_state_checked'))
            if mode=='analysis-pause-resume':
                self.assertIn('resume_analysis_ack',events)
                self.assertGreater(events.index('resume_analysis_ack'),events.index('paused_state_checked'))
            return report

    def test_pause_resume_preserves_session_and_responsive_local_controls(self):
        report = self.pause_workflow('analysis-pause-resume')
        self.assertTrue(report['checks']['resume_control'])
        self.assertTrue(report['checks']['resumed_complete'])

    def test_cancel_paused_scan_then_rescan(self):
        report = self.pause_workflow('analysis-pause-cancel')
        for key in ('cancel_control', 'cancelled', 'rescan_control', 'rescan_complete'):
            self.assertTrue(report['checks'][key], report)

    def test_quick_prefix_interval_and_distributed_are_inspectable_readonly(self):
        for index in (1, 2, 3):
            with self.subTest(index=index), tempfile.TemporaryDirectory(prefix='qt-analysis-preview-') as directory:
                report = self.run_script('analysis-preview', directory, auto=False, timeout=45,
                                         overrides={'SHOWPSISI_QUICK_INDEX': str(index)})
                for key in ('compact', 'full_hydration', 'partial', 'readonly', 'coverage', 'inspection'):
                    self.assertTrue(report['checks'][key], report)
                self.assertLess(report['max_gui_gap_ms'], 500, report)

    def test_ten_percent_prefix_and_distributed_use_source_coverage(self):
        for index in (1,3):
            with self.subTest(index=index), tempfile.TemporaryDirectory(prefix='qt-ten-percent-') as directory:
                report=self.run_script('analysis-preview',directory,auto=False,timeout=45,
                    overrides={'SHOWPSISI_QUICK_INDEX':str(index),'SHOWPSISI_QUICK_PERCENT':'1'})
                coverage=report['state']['coverage']
                self.assertEqual(coverage['scanned_packets'],max(1,coverage['source_packets']//10))
                self.assertTrue(report['checks']['readonly'],report)
                self.assertTrue(report['checks']['unknown_gap_blocked'],report)

    def test_cancel_result_loading_ignores_late_page_then_rescans(self):
        proxy = r'''import json, os, subprocess, sys, threading, time
from pathlib import Path
child=subprocess.Popen([os.environ['SHOWPSISI_REAL_CORE'], '--root', os.environ['SHOWPSISI_ROOT']],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=sys.stderr,text=True,encoding='utf-8',bufsize=1)
held=None
lock=threading.Lock()
def relay():
    global held
    for line in child.stdout:
        message=json.loads(line)
        with lock:
            stop=held is not None and message.get('id')==held
        if stop:
            gate=Path(os.environ['SHOWPSISI_HYDRATION_GATE'])
            gate.with_suffix('.ready').touch()
            deadline=time.monotonic()+20
            while not gate.with_suffix('.release').exists():
                if time.monotonic()>deadline: raise RuntimeError('Hydration terminal was never released')
                time.sleep(.005)
        print(line,end='',flush=True)
thread=threading.Thread(target=relay,daemon=True);thread.start()
for line in sys.stdin:
    request=json.loads(line)
    with lock:
        if request['method']=='query_result' and held is None: held=request['id']
    child.stdin.write(line);child.stdin.flush()
child.stdin.close();child.wait();thread.join()
'''
        with tempfile.TemporaryDirectory(prefix='qt-hydration-cancel-') as directory:
            path=Path(directory)/'proxy.py';path.write_text(proxy,encoding='utf-8')
            gate=Path(directory)/'gate';trace=Path(directory)/'trace.jsonl'
            def advance(_):
                if gate.with_suffix('.ready').exists() and trace.exists() and 'cancel_hydration_checked' in trace.read_text():
                    gate.with_suffix('.release').touch()
            report=self.run_script('analysis-hydration-cancel',directory,auto=False,timeout=45,on_running=advance,
                overrides={'SHOWPSISI_CORE':sys.executable,'SHOWPSISI_CORE_ARGS_JSON':json.dumps(['-u',str(path)]),
                           'SHOWPSISI_REAL_CORE':os.environ['SHOWPSISI_CORE'], 'SHOWPSISI_HYDRATION_GATE':str(gate),
                           'SHOWPSISI_TRACE':str(trace)})
            self.assertTrue(gate.with_suffix('.ready').exists())
            self.assertTrue(gate.with_suffix('.release').exists())
            for key in ('stop_loading','no_late_resurrection','rescan','new_complete'):
                self.assertTrue(report['checks'][key],report)

    def test_wrong_cutoff_and_nonadvancing_page_fail_closed_then_rescan(self):
        for fault in ('cutoff','cursor','error'):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(prefix='qt-invalid-page-') as directory:
                overrides={}
                if fault=='error':
                    sys.path.insert(0,str(ROOT/'scripts'))
                    from make_fixture import section, word
                    path=Path(directory)/'many.ts'
                    with path.open('wb') as output:
                        for i in range(450):
                            raw=section(0,i+1,1,word(100)+word(0xe100))
                            output.write(bytes([0x47,0x40,0,0x10+(i%16),0])+raw+b'\xff'*(183-len(raw)))
                    overrides['SHOWPSISI_SAMPLE']=str(path)
                report=self.run_script('analysis-invalid-page',directory,auto=False,timeout=45,
                    overrides={**overrides,'SHOWPSISI_CORE':sys.executable,
                               'SHOWPSISI_CORE_ARGS_JSON':json.dumps(['-u',str(ROOT/'tests/fixtures/qt_invalid_page.py')]),
                               'SHOWPSISI_REAL_CORE':os.environ['SHOWPSISI_CORE'],'SHOWPSISI_PAGE_FAULT':fault})
                for key in ('invalid_page_rejected','no_resurrection','recoverable','rescan_complete'):
                    self.assertTrue(report['checks'][key],report)

    def test_progress_flood_is_coalesced_without_dropping_real_terminal(self):
        with tempfile.TemporaryDirectory(prefix='qt-progress-flood-') as directory:
            report=self.run_script('analysis-responsive',directory,auto=False,timeout=60,
                overrides={'SHOWPSISI_CORE':sys.executable,
                           'SHOWPSISI_CORE_ARGS_JSON':json.dumps(['-u',str(ROOT/'tests/fixtures/qt_progress_flood.py')]),
                           'SHOWPSISI_REAL_CORE':os.environ['SHOWPSISI_CORE'],'SHOWPSISI_EXPECT_TABLES':'18'})
            self.assertTrue(report['checks']['full_hydration'],report)
            self.assertTrue(report['checks']['all_records'],report)
            self.assertLess(report['progress_updates'],2000,'20,000 telemetry frames were not bounded/coalesced')
            self.assertLess(report['max_gui_gap_ms'],500,report)

    def test_lazy_references_preserve_selection_and_invalidate_new_evidence(self):
        with tempfile.TemporaryDirectory(prefix='qt-reference-persistence-') as directory:
            report=self.run_script('reference-persistence',directory,timeout=30)
            for name in ('deferred','hidden_retained','reference_selection','reference_scroll',
                         'dialog_hidden_retained','dialog_selection','hex_selection','other_record','identity_invalidates'):
                self.assertTrue(report['checks'][name],report)

    def test_pending_presentation_cancel_and_error_invalidate_stages_then_rescan(self):
        for mode in ('analysis-presentation-cancel','analysis-presentation-error'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(prefix='qt-presentation-') as directory:
                report=self.run_script(mode,directory,auto=False,timeout=45)
                for key in ('pending_guard','action_rejected','invalidated','outcome','rescan','recovered','responsive'):
                    self.assertTrue(report['checks'][key],report)

    def test_many_unique_sections_hydrate_all_pages_without_blocking_gui(self):
        sys.path.insert(0, str(ROOT / 'scripts'))
        from make_fixture import section, word
        with tempfile.TemporaryDirectory(prefix='qt-analysis-many-') as directory:
            path = Path(directory) / 'many.ts'
            count = 2400
            with path.open('wb') as output:
                for i in range(count):
                    raw = section(0, i+1, 1, word(100)+word(0xe100))
                    output.write(bytes([0x47, 0x40, 0, 0x10+(i % 16), 0])+raw+b'\xff'*(183-len(raw)))
            report = self.run_script('analysis-responsive', directory, auto=False, timeout=60,
                                    overrides={'SHOWPSISI_SAMPLE': str(path), 'SHOWPSISI_EXPECT_TABLES': str(count)})
            for key in ('compact', 'full_hydration', 'all_records', 'bounded_view', 'responsive'):
                self.assertTrue(report['checks'][key], report)
            self.assertGreater(report['ticks'], 2)
            self.assertLess(report['max_gui_gap_ms'], 500, report)


if __name__ == '__main__':
    unittest.main()
