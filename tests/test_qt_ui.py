"""Native Qt Quick integration smoke against the real NDJSON C++ backend.

Build showpsisi-qt first. Optional SHOWPSISI_QT and SHOWPSISI_CORE select
binaries. A missing Qt binary skips the test; an installed but broken one fails.
"""
import hashlib
import json
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import os
from pathlib import Path
import subprocess
import signal
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
EXE = '.exe' if os.name == 'nt' else ''
sys.path.insert(0, str(ROOT / 'scripts' / 'ci'))
from qt_result import wait_for_qt_result
from qt_evidence import retain_qt_evidence


def native_environment():
    env = os.environ.copy()
    libraries = [ROOT / '.deps/Qt/6.7.3/gcc_64/lib',
                 ROOT / '.deps/python/PySide6/Qt/lib',
                 ROOT / '.deps/tsduck/usr/lib',
                 ROOT / '.deps/tsduck/usr/lib/x86_64-linux-gnu']
    env['LD_LIBRARY_PATH'] = os.pathsep.join(str(p) for p in libraries if p.exists()) + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    env.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
               SHOWPSISI_ROOT=str(ROOT), SHOWPSISI_AUTO='1',
               SHOWPSISI_CORE=env.get('SHOWPSISI_CORE', str(ROOT / ('build/bin/showpsisi-core' + EXE))),
               SHOWPSISI_SAMPLE=str(ROOT / 'samples/generated/lab.ts'))
    # TSDuck resolves its XML/name definitions relative to this search path.
    if (ROOT / '.deps/tsduck/usr/lib/tsduck').exists():
        env.setdefault('TSPLUGINS_PATH', str(ROOT / '.deps/tsduck/usr/lib/tsduck'))
    return env


class NativeQtTests(unittest.TestCase):
    def test_signal_metadata_language_encoding_and_id_lookup(self):
        from test_signal_metadata import metadata_fixture
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'metadata.ts';path.write_bytes(metadata_fixture())
            report=self.run_script('signal-metadata',directory,overrides={'SHOWPSISI_SAMPLE':str(path),'SHOWPSISI_STANDARDS':'dvb'})
            self.assertTrue(all(report['checks'].values()),report)
            self.assertEqual(path.read_bytes(),metadata_fixture())

    def run_script(self, script, directory, settings=None, auto=True, overrides=None, on_running=None, timeout=25, after_report=None):
        binary = Path(os.environ.get('SHOWPSISI_QT', ROOT / ('build/cloud/bin/showpsisi-qt' + EXE)))
        if not binary.exists():
            self.skipTest('Build the native Qt target or set SHOWPSISI_QT')
        directory = Path(directory)
        result, screenshot = directory / (script + '.json'), directory / (script + '.png')
        env = native_environment()
        env.update(SHOWPSISI_SCRIPT='comparison' if script == 'comparison-small' else script, SHOWPSISI_TEST_RESULT=str(result),
                   SHOWPSISI_TEST_SIZE='compact' if script == 'comparison-small' else '',
                   SHOWPSISI_SCREENSHOT=str(screenshot), SHOWPSISI_AUTO='1' if auto else '0',
                   SHOWPSISI_SETTINGS_PATH=str(settings or directory / 'settings.ini'))
        env.update(overrides or {})
        evidence_root = os.environ.get('SHOWPSISI_QT_TEST_ARTIFACTS')
        destination = Path(evidence_root) / self._testMethodName / script if evidence_root else None
        if destination and script == 'refinement':
            destination = destination / (env.get('SHOWPSISI_THEME', 'dark') + '-' + env.get('SHOWPSISI_TEST_SIZE', 'normal'))
        logfile = directory / (script + '.log')
        sources = [result, screenshot, Path(str(screenshot)+'.xml.png'), logfile, Path(str(screenshot) + '.scanning.png'), Path(str(screenshot) + '.cancelled.png')]
        if env.get('SHOWPSISI_TRACE'):
            sources.append(Path(env['SHOWPSISI_TRACE']))
        with retain_qt_evidence(destination, sources):
            with logfile.open('w+', encoding='utf-8') as log:
                process = subprocess.Popen([str(binary)], env=env, cwd=ROOT, stdout=log, stderr=log)
                try:
                    report = wait_for_qt_result(result, process, timeout, on_running)
                    if script in ('layout-set', 'layout-read', 'layout-small', 'layout-reset'):
                        self.assertTrue(screenshot.is_file(), 'Layout result preceded its screenshot')
                        self.assertEqual(screenshot.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
                    if after_report:
                        after_report()
                finally:
                    if process.poll() is None:
                        process.terminate()  # Forced cleanup is not a graceful window-close test.
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                log.seek(0)
                diagnostics = log.read()
            self.assertTrue(result.exists(), diagnostics)
            self.assertTrue(report['passed'], report)
            for error in ('ReferenceError:', 'TypeError:', 'Cannot assign', 'Unable to assign', 'QQmlApplicationEngine failed'):
                self.assertNotIn(error, diagnostics)
            return report

    def cancellation_helper(self):
        """Resolve the opt-in helper; it is never substituted for production tests."""
        production = Path(native_environment()['SHOWPSISI_CORE'])
        helper = Path(os.environ.get('SHOWPSISI_TEST_CORE', production.with_name('showpsisi-core-test' + EXE)))
        self.assertTrue(helper.is_file(), 'Build with -DSHOWPSISI_BUILD_CANCELLATION_TESTS=ON or set SHOWPSISI_TEST_CORE')
        return helper

    def test_refined_themes_grouping_and_pid_columns(self):
        for theme in ('dark', 'light'):
            for size in ('normal', 'compact'):
                with self.subTest(theme=theme, size=size), tempfile.TemporaryDirectory(prefix='showpsisi-qt-refined-') as directory:
                    report = self.run_script('refinement', directory, overrides={
                        'SHOWPSISI_THEME':theme, 'SHOWPSISI_TEST_SIZE':size})
                    self.assertEqual(report['theme'], theme)
                    self.assertGreaterEqual(report['tree_height'], 90)
                    self.assertTrue(all(report['checks'].values()), report)
                    for capture in (Path(directory)/'refinement.png', Path(directory)/'refinement.png.xml.png'):
                        self.assertEqual(capture.read_bytes()[-12:], b'\x00\x00\x00\x00IEND\xaeB`\x82', 'Incomplete PNG capture')

    def test_refined_service_media_wire_evidence(self):
        from test_service_metadata import ServiceMetadataTests
        fixture = ServiceMetadataTests()
        parts = [fixture.pat(), fixture.pmt(), fixture.nit(), (0x11,fixture.sdt(last=0))]
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-media-') as directory:
            path = Path(directory)/'media.ts'
            path.write_bytes(b''.join(bytes([0x47,0x40|(pid>>8),pid&255,0x10,0])+raw+b'\xff'*(183-len(raw)) for pid,raw in parts))
            for theme in ('dark','light'):
                capture_dir=Path(directory)/theme
                capture_dir.mkdir()
                report=self.run_script('refinement', capture_dir, overrides={'SHOWPSISI_THEME':theme,
                    'SHOWPSISI_SAMPLE':str(path), 'SHOWPSISI_TEST_SIZE':'compact', 'SHOWPSISI_EXPECT_MEDIA':'1'})
                self.assertEqual(report['theme'],theme)

    def test_section_evidence_workbench(self):
        from test_section_evidence import SectionEvidenceTests
        fixture = SectionEvidenceTests()
        parts = [fixture.sdt(), fixture.sdt(number=1), fixture.sdt(number=1,bad=True), fixture.sdt()]
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-sections-') as directory:
            path = Path(directory) / 'sections.ts'
            path.write_bytes(b''.join(bytes([0x47,0x40,0x11,0x10+i,0])+raw+b'\xff'*(183-len(raw)) for i,raw in enumerate(parts)))
            report = self.run_script('section-evidence', directory, overrides={'SHOWPSISI_SAMPLE':str(path)})
            self.assertTrue(all(report['checks'].values()),report)
            self.assertEqual((Path(directory)/'section-evidence.png').read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual((Path(directory)/'section-evidence.png.xml.png').read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    def test_superseded_section_does_not_leak_merged_evidence(self):
        from test_section_evidence import SectionEvidenceTests
        fixture = SectionEvidenceTests()
        parts = [fixture.sdt(), fixture.sdt(number=1), fixture.sdt(version=2), fixture.sdt(version=2,number=1)]
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-superseded-') as directory:
            path = Path(directory) / 'sections.ts'
            path.write_bytes(b''.join(bytes([0x47,0x40,0x11,0x10+i,0])+raw+b'\xff'*(183-len(raw)) for i,raw in enumerate(parts)))
            report = self.run_script('section-superseded', directory, overrides={'SHOWPSISI_SAMPLE':str(path)})
            self.assertTrue(all(report['checks'].values()),report)
            self.assertEqual((Path(directory)/'section-superseded.png').read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    def test_all_crc_bad_sections_hidden_until_requested(self):
        from test_section_evidence import SectionEvidenceTests
        raw = SectionEvidenceTests().sdt(bad=True)
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-allbad-') as directory:
            path = Path(directory) / 'allbad.ts'
            path.write_bytes(b''.join(bytes([0x47,0x40,0x11,0x10+i,0])+raw+b'\xff'*(183-len(raw)) for i in range(2)))
            report = self.run_script('section-allbad', directory, overrides={'SHOWPSISI_SAMPLE':str(path)})
            self.assertTrue(all(report['checks'].values()),report)

    def test_cancel_active_scan_then_rescan_real_engine(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-cancel-') as directory:
            gate = Path(directory) / 'pause'
            trace = Path(directory) / 'trace.jsonl'
            report = self.run_script('lifecycle-cancel', directory, overrides={
                'SHOWPSISI_CORE': str(self.cancellation_helper()),
                'SHOWPSISI_TEST_GATE': str(gate), 'SHOWPSISI_TEST_STAGE': 'after_progress',
                'SHOWPSISI_TRACE': str(trace), 'SHOWPSISI_TEST_SIZE': 'compact'})
            self.assertTrue(gate.with_suffix('.ready').exists(), 'The real analyzer did not reach its deterministic checkpoint')
            self.assertTrue(all(report['checks'].values()), report)
            self.assertGreaterEqual(len(report['checks']), 14)
            events = [json.loads(line)['event'] for line in trace.read_text().splitlines()]
            cancelled = events.index('cancelled_state_checked')
            self.assertNotIn('complete_paint', events[:cancelled], 'Cancelled analysis painted as complete')
            self.assertEqual(events.count('analyze_requested'), 2)
            self.assertEqual(events.count('cancel_requested'), 1)

    def test_stale_progress_results_and_cancel_ack_do_not_settle_scan(self):
        # Adversarial protocol fixture: proves transport correlation, not TS parsing.
        # The explicit argv configuration is trusted local launch input, never
        # metadata from a transport stream, and QProcess does not invoke a shell.
        fixture = r'''import json, os, sys, time
from pathlib import Path

def emit(value):
    print(json.dumps(value), flush=True)

def state(source, complete=False, status='analyzing'):
    return dict(source=source, complete=complete, analysis_status=status, observations=1,
                packets=100, services=[], tables=[dict(id='section',name='SDT',pid=17,version=1,section=0,last_section=0,bytes=1,count=1)],
                diagnostics=[], events=[], history=[])

count, active, old_inspect, old_analyze = 0, None, None, None
for line in sys.stdin:
    request = json.loads(line)
    identity, method = request['id'], request['method']
    if method == 'analyze':
        count += 1
        if count == 1:
            old_analyze = identity
            emit(dict(id=identity,result=state('initial.ts',True,'complete')))
        elif count == 2:
            active = identity
            emit(dict(id=old_inspect,result=dict(id='poison',name='SDT')))
            emit(dict(id=old_analyze,result=state('poison-old-result',True,'complete')))
            emit(dict(event='progress',request_id=identity,state=state('active.ts')))
            emit(dict(event='other',request_id=identity,state=state('poison-event')))
            emit(dict(event='progress',request_id=old_analyze,state=state('poison-old-progress')))
            emit(dict(event='progress',request_id=str(identity),state=state('poison-id-type')))
        else:
            emit(dict(event='progress',request_id=active,state=state('poison-after-rescan')))
            emit(dict(id=identity,result=state('new-scan.ts',True,'complete')))
    elif method == 'inspect':
        if count == 1:
            old_inspect = identity
        else:
            emit(dict(id=identity,result=dict(id='new-section',name='SDT',version=1,valid=True)))
    elif method == 'cancel_analysis':
        assert request['params']['request_id'] == active
        emit(dict(id=identity,result=dict(request_id=active,requested=sys.argv[-1] != 'complete-race',reason='not_running')))
        emit(dict(event='progress',request_id=active,state=state('poison-while-cancelling')))
        release = Path(os.environ['SHOWPSISI_FIXTURE_RELEASE'])
        deadline = time.monotonic() + 15
        while not release.exists():
            if time.monotonic() > deadline:
                raise RuntimeError('UI did not acknowledge cancellation before terminal release')
            time.sleep(0.01)
        cancelled=state('active.ts',False,'cancelled')
        cancelled.update(observations=0,tables=[])
        if sys.argv[-1] == 'complete-race':
            emit(dict(id=active,result=state('active.ts',True,'complete')))
        else:
            emit(dict(id=active,error=dict(code='analysis_cancelled',message='Analysis cancelled',data=dict(state=cancelled))))
        emit(dict(id=active,result=state('poison-late-success',True,'complete')))
        emit(dict(event='progress',request_id=active,state=state('poison-late-progress')))
    elif method == 'fixture_late_frames':
        emit(dict(id=identity,result=dict(late_frames_sent=True)))
'''
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-stale-') as directory:
            path = Path(directory) / 'protocol_fixture.py'
            path.write_text(fixture, encoding='utf-8')
            for mode in ('stale', 'complete-race'):
                with self.subTest(mode=mode):
                    trace = Path(directory) / (mode + '.trace.jsonl')
                    release = Path(directory) / (mode + '.release')
                    def release_after_ui_ack(process):
                        if trace.exists() and 'cancel_ack_observed' in trace.read_text(encoding='utf-8'):
                            release.touch()
                    report = self.run_script('lifecycle-' + mode, directory, on_running=release_after_ui_ack, overrides={
                        'SHOWPSISI_TRACE': str(trace), 'SHOWPSISI_FIXTURE_RELEASE': str(release),
                        'SHOWPSISI_CORE': sys.executable,
                        'SHOWPSISI_CORE_ARGS_JSON': json.dumps(['-u', str(path), mode]),
                        'SHOWPSISI_TEST_SIZE': 'compact'})
                    self.assertTrue(report['checks']['pending_old_inspect'], report)
                    self.assertTrue(report['checks']['ack_did_not_settle'], report)
                    self.assertTrue(all(report['checks'].values()), report)

    def check_real_backend_death(self, directory, active=False):
        trace = Path(directory) / 'death-trace.jsonl'
        overrides = {'SHOWPSISI_TRACE': str(trace)}
        if active:
            overrides.update(SHOWPSISI_CORE=str(self.cancellation_helper()),
                             SHOWPSISI_TEST_GATE=str(Path(directory) / 'gate'),
                             SHOWPSISI_TEST_STAGE='after_progress')
        killed = []

        def kill_only_test_child(process):
            if killed or not trace.exists():
                return
            events = []
            for line in trace.read_text(encoding='utf-8').splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass  # The last line can still be in flight.
            if not any(event['event'] == 'backend_death_ready' for event in events):
                return
            child = next(event['backend_pid'] for event in events if event['event'] == 'backend_started')
            self.assertGreater(child, 0)
            self.assertIsNone(process.poll())
            os.kill(int(child), signal.SIGTERM)
            killed.append(int(child))

        report = self.run_script('lifecycle-death-active' if active else 'lifecycle-death', directory,
                                 overrides=overrides, on_running=kill_only_test_child)
        self.assertEqual(len(killed), 1)
        events = [json.loads(line)['event'] for line in trace.read_text().splitlines()]
        self.assertEqual(events.count('backend_started'), 1, 'The UI automatically restarted its backend')
        self.assertTrue(all(report['checks'].values()), report)

    def test_backend_death_clears_completed_evidence_and_edit_preview(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-death-') as directory:
            self.check_real_backend_death(directory)

    def test_backend_death_during_actual_scan(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-death-active-') as directory:
            self.check_real_backend_death(directory, active=True)

    def test_startup_failure_and_invalid_launch_arguments_are_disconnected(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-startup-') as directory:
            result = Path(directory) / 'lifecycle-startup.json'
            for arguments in (None, '{invalid', '[1]', '{}', '["\\u0000"]'):
                with self.subTest(arguments=arguments):
                    overrides = {'SHOWPSISI_CORE': str(Path(directory) / ('missing-core' + EXE))}
                    if arguments is not None:
                        overrides['SHOWPSISI_CORE_ARGS_JSON'] = arguments
                    result.unlink(missing_ok=True)
                    report = self.run_script('lifecycle-startup', directory, overrides=overrides)
                    self.assertTrue(all(report['checks'].values()), report)
                    if arguments is not None:
                        self.assertIn('Invalid SHOWPSISI_CORE_ARGS_JSON', report['error'])

    def test_snapshot_comparison_and_evidence_cutoffs(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-comparison-') as directory:
            report = self.run_script('comparison', directory)
            self.assertGreaterEqual(len(report['checks']), 25)
            self.assertTrue(all(report['checks'].values()), report)

    def test_snapshot_query_waits_for_terminal_before_rescan(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-query-gate-') as directory:
            gate, trace = Path(directory) / 'query', Path(directory) / 'trace.jsonl'
            real_core = native_environment()['SHOWPSISI_CORE']
            observed = []
            def release_after_wait(process):
                if gate.with_suffix('.held').exists() and trace.exists():
                    events = trace.read_text(encoding='utf-8')
                    if events.count('comparison_query_waiting') >= 2:
                        self.assertFalse(gate.with_suffix('.premature').exists(), 'Rescan invalidated the pending snapshot query')
                        observed.append(True)
                        gate.with_suffix('.release').touch()
            report = self.run_script('comparison', directory, on_running=release_after_wait, overrides={
                'SHOWPSISI_CORE': sys.executable,
                'SHOWPSISI_CORE_ARGS_JSON': json.dumps(['-u', str(ROOT / 'tests/fixtures/qt_delayed_query_proxy.py')]),
                'SHOWPSISI_REAL_CORE': real_core, 'SHOWPSISI_QUERY_GATE': str(gate), 'SHOWPSISI_TRACE': str(trace)})
            self.assertTrue(observed, 'The real query response was not held and acknowledged')
            self.assertFalse(gate.with_suffix('.premature').exists())
            self.assertTrue(report['checks']['explicit_use_snapshot'])

    def test_populated_compact_comparison_keyboard_and_controls(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-compact-comparison-') as directory:
            # Keep a taller persisted timeline to exercise real saved-layout pressure.
            self.run_script('layout-set', directory, auto=False)
            report = self.run_script('comparison-small', directory)
            for name in ('controls_exposed', 'inspector_controls_exposed', 'change_row_exposed',
                         'results_height', 'tree_height', 'pending_controls', 'search_to_results', 'results_to_tree',
                         'tree_search_to_tree', 'cutoff_enter_compares'):
                self.assertTrue(report['checks'][name], report)

    def test_rapid_keyboard_resize_graceful_close_persists_intent(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-layout-close-') as directory:
            closed = self.run_script('layout-close', directory, auto=False)
            reopened = self.run_script('layout-read', directory, auto=False)
            self.assertEqual(reopened['inspector'], closed['expectedInspector'])
            self.assertEqual(reopened['timeline'], closed['expectedTimeline'])

    def test_pending_keyboard_layout_yields_to_drag_reset_and_constraints(self):
        for script in ('layout-key-drag', 'layout-key-reset', 'layout-key-constrained'):
            with self.subTest(script=script), tempfile.TemporaryDirectory(prefix='showpsisi-qt-intent-') as directory:
                report = self.run_script(script, directory, auto=False)
                reopened = self.run_script('layout-read', directory, auto=False)
                self.assertEqual(reopened['saved'], report['saved'])

    def test_layout_drag_keyboard_persistence_and_reset(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-layout-') as directory:
            configured = self.run_script('layout-set', directory, auto=False,
                                         overrides={'SHOWPSISI_TEST_LAYOUT_SAVE_DELAY': '700'})
            self.assertTrue(configured['persistedAcknowledged'])
            self.assertGreater(configured['acknowledgementAttempts'], 0)
            self.assertTrue(configured['dragged'])
            self.assertTrue(configured['invalid_rejected'])
            restored = self.run_script('layout-read', directory, auto=False)
            for field in ('explorer', 'inspector', 'timeline'):
                self.assertAlmostEqual(configured[field], restored[field], delta=1)
            self.assertGreater(restored['inspector'], 580)
            self.assertGreater(restored['timeline'], 145)
            small = self.run_script('layout-small', directory, auto=False)
            self.assertLessEqual(small['workspace'], 1000)
            reset = self.run_script('layout-reset', directory, auto=False)
            self.assertAlmostEqual(reset['inspector'], 520, delta=1)
            self.assertAlmostEqual(reset['timeline'], 105, delta=1)
            self.assertEqual(reset['saved'], {'version': 1, 'explorer': 180, 'inspector': 520, 'timeline': 105})
            # Reopen after reset to verify durable defaults, not just current pixels.
            (Path(directory) / 'layout-read.json').unlink()
            reopened = self.run_script('layout-read', directory, auto=False)
            self.assertAlmostEqual(reopened['inspector'], 520, delta=1)

    def test_corrupt_layout_uses_safe_defaults(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-corrupt-layout-') as directory:
            settings = Path(directory) / 'settings.ini'
            for invalid in ('not-json', '@ByteArray({"version":1,"explorer":-2,"inspector":999999,"timeline":0})',
                            '@ByteArray({"version":8,"explorer":180,"inspector":520,"timeline":105})'):
                settings.write_text('[General]\nworkbenchLayout=' + invalid + '\n', encoding='utf-8')
                (Path(directory) / 'layout-read.json').unlink(missing_ok=True)
                report = self.run_script('layout-read', directory, settings=settings, auto=False)
                self.assertEqual(report['saved'], {'version': 1, 'explorer': 180, 'inspector': 520, 'timeline': 105})
                self.assertAlmostEqual(report['inspector'], 520, delta=1)

    def check_export_destinations(self, directory, resource_root=None):
        directory = Path(directory)
        destination = directory / 'chosen-output'
        destination.mkdir()
        existing_manifest = destination / 'manifest-only.ts.manifest.json'
        existing_manifest.write_bytes(b'preserve existing manifest')
        source = ROOT / 'samples/generated/lab.ts'
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        overrides = {'SHOWPSISI_EXPORT_TEST_DIR': str(destination), 'SHOWPSISI_TEST_SIZE': 'compact',
                     'SHOWPSISI_TEST_EXPORT_ACCEPT_DELAY': '700'}
        if resource_root:
            overrides['SHOWPSISI_ROOT'] = str(resource_root)
        preserved = {}
        def observe_first_export(process):
            output = destination / 'chosen λ.ts'
            manifest = Path(str(output) + '.manifest.json')
            if not preserved and output.exists() and manifest.exists():
                try:
                    json.loads(manifest.read_text(encoding='utf-8'))
                except (OSError, json.JSONDecodeError):
                    return
                for path in (output, manifest):
                    preserved[path] = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
        report = self.run_script('export-destination', directory, overrides=overrides, on_running=observe_first_export)
        self.assertEqual(len(preserved), 2, 'The delayed duplicate choice must allow first-export observation')
        for path, identity in preserved.items():
            self.assertEqual((hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns), identity,
                             'Repeated refused exports must not modify output or manifest')
        self.assertTrue(all(report['checks'].values()), report)
        self.assertGreaterEqual(len(report['checks']), 20)
        self.assertFalse((destination / 'cancelled.ts').exists())
        self.assertFalse((destination / 'wrong.bin').exists())
        self.assertFalse((destination / 'stale.bin').exists())
        self.assertFalse((destination / 'manifest-only.ts').exists())
        self.assertEqual(existing_manifest.read_bytes(), b'preserve existing manifest')
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        for format_, name in [('ts', 'chosen λ.ts'), ('bin', 'raw-sections.bin')]:
            path = destination / name
            data = path.read_bytes()
            manifest = json.loads(Path(str(path) + '.manifest.json').read_text(encoding='utf-8'))
            self.assertEqual(Path(manifest['path']), path)
            self.assertEqual(Path(manifest['source']), source)
            self.assertEqual(manifest['format'], format_)
            self.assertFalse(manifest['has_media'])
            self.assertFalse(manifest['has_pcr'])
            self.assertEqual(manifest['bytes'], len(data))
            self.assertEqual(manifest['edit']['after'], 'Qt destination edit')
            if format_ == 'ts':
                self.assertEqual(len(data) % 188, 0)
                self.assertTrue(all(data[index] == 0x47 for index in range(0, len(data), 188)))
            else:
                self.assertEqual(manifest['cycles'], 1)
                self.assertEqual(manifest['null_packets_per_cycle'], 0)
                self.assertEqual(len(data), sum(section['bytes'] for section in manifest['sections']))
                self.assertIn(b'Qt destination edit', data)
                for section in manifest['sections']:
                    raw = data[section['bin_offset']:section['bin_offset'] + section['bytes']]
                    self.assertEqual(((raw[1] & 15) << 8 | raw[2]) + 3, len(raw))
        env = native_environment()
        request = json.dumps({'id': 1, 'method': 'analyze', 'params': {'path': str(destination / 'chosen λ.ts')}}) + '\n'
        result = subprocess.run([env['SHOWPSISI_CORE'], '--root', str(resource_root or ROOT)],
                                input=request, text=True, encoding='utf-8', env=env,
                                capture_output=True, check=True, timeout=15)
        terminal = next(json.loads(line) for line in result.stdout.splitlines() if json.loads(line).get('id') == 1)
        self.assertNotIn('error', terminal)
        state = terminal['result']
        self.assertIn('Qt destination edit', [service['name'] for service in state['services']])
        self.assertFalse(any(issue['code'] == 'crc32' for issue in state['diagnostics']))

    def test_save_dialog_cancellation_formats_and_external_destinations(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-save-') as directory:
            self.check_export_destinations(directory)

    def test_save_uses_external_destination_with_separate_resource_root(self):
        # POSIX additionally enforces a read-only application root. Windows
        # exercises the same separate-root flow without claiming ACL coverage.
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-portable-') as directory:
            resource_root = Path(directory) / 'read-only-app'
            resource_root.mkdir()
            for name in ('api', 'extensions', 'references'):
                shutil.copytree(ROOT / name, resource_root / name)
            paths = list(resource_root.rglob('*')) + [resource_root]
            try:
                if os.name != 'nt':
                    for path in paths:
                        path.chmod(0o555 if path.is_dir() else 0o444)
                    self.assertFalse(os.access(resource_root, os.W_OK), 'Read-only test requires an unprivileged test process')
                self.check_export_destinations(directory, resource_root)
                self.assertFalse((resource_root / 'artifacts').exists())
            finally:
                for path in paths:
                    path.chmod(0o755 if path.is_dir() else 0o644)

    def test_native_interaction_smoke(self):
        self.run_native_smoke('auto')

    def test_explicit_dvb_context(self):
        self.run_native_smoke('dvb')

    def test_dtmb_and_guarded_dsmcc_native_views(self):
        """New selectors, empty projections and warnings use real SDK fixtures."""
        manifest = json.loads((ROOT / 'tests/fixtures/tsduck345/manifest.json').read_text(encoding='utf-8'))
        cases = (('DTMB_DRM_PMT', 'dtmb', 'PMT', False),
                 ('DSMCC_DII', 'auto', 'DSMCC_user_to_network_message', True))
        for name, standard, table_name, guarded in cases:
            with self.subTest(fixture=name), tempfile.TemporaryDirectory(prefix='showpsisi-qt-protocol-') as directory:
                temp = Path(directory)
                fixture = manifest['fixtures'][name]
                raw, pid = bytes.fromhex(fixture['hex']), fixture['pid']
                # Same real three-repeat 188-byte packetization as the Web
                # new-protocol UI regression; no mocked positive responses.
                packets = []
                for repeat in range(3):
                    remainder, first, counter = raw, True, len(packets) & 15
                    while remainder:
                        size = 183 if first else 184
                        payload, remainder = remainder[:size], remainder[size:]
                        packets.append(bytes([0x47, (pid >> 8) | (0x40 if first else 0), pid & 255, 0x10 | counter]) +
                                       (b'\0' if first else b'') + payload + b'\xff' * (size - len(payload)))
                        first, counter = False, (counter + 1) & 15
                source = temp / (name + '.ts')
                source.write_bytes(b''.join(packets))
                original = hashlib.sha256(source.read_bytes()).hexdigest()
                report = self.run_script('protocol-upgrade', temp, auto=False, overrides={
                    'SHOWPSISI_SAMPLE': str(source),
                    'SHOWPSISI_PROTOCOL_PID': str(pid),
                    'SHOWPSISI_PROTOCOL_STANDARD': standard,
                    'SHOWPSISI_PROTOCOL_EXPECTED_TABLE': table_name,
                    'SHOWPSISI_PROTOCOL_GUARDED': '1' if guarded else '0',
                })
                self.assertEqual(report['standards_context'], standard)
                self.assertEqual(report['table_name'], table_name)
                self.assertEqual(report['raw_hex'], fixture['hex'].upper())
                self.assertEqual(report['native_xml_guarded'], guarded)
                self.assertTrue(report['checks'])
                self.assertTrue(all(report['checks'].values()), report)
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), original)
                self.assertEqual((temp / 'protocol-upgrade.png').read_bytes()[:8], b'\x89PNG\r\n\x1a\n')

    def test_failed_inspect_clears_native_evidence(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-error-') as directory:
            report = self.run_script('inspect-error', directory, timeout=15)
            self.assertIn('Unknown section', report['error'])

    def test_stream_markup_is_literal_without_network_fetches(self):
        binary = Path(os.environ.get('SHOWPSISI_QT', ROOT / ('build/cloud/bin/showpsisi-qt' + EXE)))
        if not binary.exists():
            self.skipTest('Build the native Qt target or set SHOWPSISI_QT')
        requests = []

        class TrapHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'not an image')

            def log_message(self, *_):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), TrapHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory(prefix='showpsisi-qt-literal-') as directory:
                temp = Path(directory)
                env = native_environment()
                fixture, result = temp / 'markup.ts', temp / 'result.json'
                marker = '<b>name</b><img src="http://127.0.0.1:%d/probe">' % server.server_port
                core = subprocess.Popen([env['SHOWPSISI_CORE'], '--root', str(ROOT)], env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, encoding='utf-8')
                try:
                    sequence = 0

                    def call(method, params):
                        nonlocal sequence
                        sequence += 1
                        core.stdin.write(json.dumps(dict(id=sequence, method=method, params=params)) + '\n')
                        core.stdin.flush()
                        while True:
                            response = json.loads(core.stdout.readline())
                            if response.get('id') == sequence:
                                self.assertNotIn('error', response)
                                return response['result']

                    state = call('analyze', {'path': env['SHOWPSISI_SAMPLE']})
                    service = state['services'][0]
                    preview = call('preview_rename', {'id': service['source_id'], 'service_id': service['id'], 'name': marker})
                    call('export', {'path': str(fixture), 'preview_token': preview['token'], 'cycles': 3})
                finally:
                    core.stdin.close()
                    core.wait(timeout=5)
                    core.stdout.close()
                    core.stderr.close()
                report = self.run_script('plaintext', temp, timeout=15,
                                         overrides={'SHOWPSISI_SAMPLE': str(fixture)},
                                         after_report=lambda: time.sleep(0.6))  # Bounded negative-network observation.
                self.assertGreaterEqual(report['matched_text_items'], 3)
                self.assertTrue(report['comparison_literal'])
                self.assertEqual(report['unsafe_text_items'], 0)
                self.assertGreaterEqual(report['tooltip_text_items'], 1)
                self.assertEqual(requests, [], 'Markup caused a network image request')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def run_native_smoke(self, standards):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-') as directory:
            temp = Path(directory)
            screenshot, trace = temp / 'smoke.png', temp / 'trace.jsonl'
            report = self.run_script('smoke', temp, timeout=35, overrides={
                'SHOWPSISI_STANDARDS': standards, 'SHOWPSISI_TRACE': str(trace),
                'SHOWPSISI_ARTIFACT_DIR': str(temp)})
            self.assertEqual(report['standards_context'], standards)
            self.assertTrue(report['native_tree'])
            self.assertTrue(report['history_cutoff'])
            self.assertEqual(len(report['search']), 11)
            for check in ('tree_home_end', 'tree_expand_enter_parent', 'tree_tab_exits'):
                self.assertTrue(report['search'][check], check)
            self.assertTrue(all(report['search'].values()), report['search'])
            self.assertGreater(report['references'], 0, 'Expected verified SDT specification metadata')
            self.assertEqual(report['services'], 6)
            self.assertEqual(len(report['checks']), 5)
            self.assertEqual(screenshot.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            self.assertTrue(list(temp.glob('qt-export-*.ts.manifest.json')))


class QtResultPublicationTests(unittest.TestCase):
    def wait(self, reads, *, exit_code=None, timeout=0.3):
        path = mock.Mock()
        path.read_text.side_effect = reads
        process = mock.Mock()
        process.poll.return_value = exit_code
        now = [0.0]
        def advance(seconds):
            now[0] += seconds
        with mock.patch('qt_result.time.monotonic', side_effect=lambda: now[0]), \
             mock.patch('qt_result.time.sleep', side_effect=advance):
            return wait_for_qt_result(path, process, timeout)

    def test_empty_and_partial_publication_waits_for_complete_json(self):
        self.assertEqual(self.wait([FileNotFoundError(), '', '{"passed":',
                                    '{"passed": true}']), {"passed": True})

    def test_real_file_creation_does_not_end_wait_before_write(self):
        with tempfile.TemporaryDirectory(prefix='qt-result-publication-') as directory:
            path = Path(directory) / 'result.json'
            path.touch()  # Reproduce QFile opening an empty result before flushing.
            process = mock.Mock()
            process.poll.return_value = None
            writes = iter(['{"passed":', '{"passed": true}'])
            def publish(_):
                path.write_text(next(writes), encoding='utf-8')
            self.assertEqual(wait_for_qt_result(path, process, 2, publish), {"passed": True})
            process.terminate.assert_not_called()

    def test_complete_failure_is_returned_without_retry(self):
        self.assertEqual(self.wait(['{"passed": false}']), {"passed": False})

    def test_malformed_result_fails_at_original_deadline(self):
        with self.assertRaisesRegex(AssertionError, 'content=.*broken'):
            self.wait(['broken'] * 10)

    def test_exited_writer_with_incomplete_result_fails(self):
        with self.assertRaisesRegex(AssertionError, 'exit=1'):
            self.wait(['{"passed":'] * 2, exit_code=1)

    def test_exit_observation_rereads_final_flushed_result(self):
        self.assertEqual(self.wait(['', '{"passed": true}'], exit_code=0), {"passed": True})

    def test_nonobject_complete_result_is_rejected(self):
        with self.assertRaisesRegex(AssertionError, 'must be an object'):
            self.wait(['[]'])

    def test_missing_result_fails_at_original_deadline(self):
        with self.assertRaisesRegex(AssertionError, 'content=None'):
            self.wait([FileNotFoundError()] * 10)


class QtEvidenceRetentionTests(unittest.TestCase):
    def exercise(self, complete=False, oversize=False, script='comparison'):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run, evidence = root / 'run', root / 'evidence'
            run.mkdir()
            binary = root / ('fake-qt' + EXE)
            binary.touch()
            process = mock.MagicMock()
            process.poll.return_value = None
            process.wait.return_value = 0
            def publish(*args):
                (run / (script + '.json')).write_text('{"passed":true}' if complete else '{')
                (run / (script + '.log')).write_text('ReferenceError: injected QML failure' if complete else 'injected loader context')
                if oversize:
                    with (run / (script + '.png')).open('wb') as output:
                        output.truncate(5 * 1024 * 1024 + 1)
                if not complete:
                    raise AssertionError('injected incomplete-result failure')
                return {'passed': True}
            with mock.patch.dict(os.environ, SHOWPSISI_QT=str(binary), SHOWPSISI_QT_TEST_ARTIFACTS=str(evidence)), \
                 mock.patch('subprocess.Popen', return_value=process), \
                 mock.patch(__name__ + '.wait_for_qt_result', side_effect=publish):
                with self.assertRaisesRegex(AssertionError, 'ReferenceError' if complete else 'injected incomplete-result failure'):
                    NativeQtTests().run_script(script, run)
            retained = evidence / 'runTest' / script
            self.assertEqual((retained / (script + '.json')).read_text(), '{"passed":true}' if complete else '{')
            self.assertIn('injected', (retained / (script + '.log')).read_text())
            if oversize:
                self.assertFalse((retained / (script + '.png')).exists())
            process.terminate.assert_called_once()

    def test_partial_result_retains_original_failure_and_logs(self):
        self.exercise()

    def test_passed_report_with_qml_error_retains_evidence(self):
        self.exercise(complete=True)

    def test_oversized_evidence_is_not_copied(self):
        self.exercise(oversize=True)

    def test_standalone_modes_retain_timeout_and_diagnostic_failures(self):
        for script in ('inspect-error', 'plaintext', 'smoke'):
            for complete in (False, True):
                with self.subTest(script=script, complete=complete):
                    self.exercise(complete=complete, script=script)

    def test_retained_smoke_isolates_settings(self):
        import windows_native_checks as checks
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / ('fake-qt' + EXE)
            binary.touch()
            process = mock.MagicMock()
            process.poll.return_value = 0
            def publish(path, *args):
                path.write_text('{"passed":true}')
                (path.parent / 'screen.png').write_bytes(b'\x89PNG\r\n\x1a\n')
                return {'passed': True}
            with mock.patch.dict(os.environ, SHOWPSISI_QT=str(binary), SHOWPSISI_SETTINGS_PATH='inherited-owner-settings.ini'), \
                 mock.patch.object(checks.subprocess, 'Popen', return_value=process) as launch, \
                 mock.patch.object(checks, 'wait_for_qt_result', side_effect=publish):
                checks.qt_smoke(root)
            self.assertEqual(launch.call_args.kwargs['env']['SHOWPSISI_SETTINGS_PATH'], str(root / 'qt-smoke/settings.ini'))


if __name__ == '__main__':
    unittest.main()
