"""Native Qt Quick integration smoke against the real NDJSON C++ backend.

Build showpsisi-qt first. Optional SHOWPSISI_QT and SHOWPSISI_CORE select
binaries. A missing Qt binary skips the test; an installed but broken one fails.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXE = '.exe' if os.name == 'nt' else ''


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
    def run_script(self, script, directory, settings=None, auto=True):
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
        with (directory / (script + '.log')).open('w+', encoding='utf-8') as log:
            process = subprocess.Popen([str(binary)], env=env, cwd=ROOT, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 25
                while not result.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.1)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            log.seek(0)
            diagnostics = log.read()
        self.assertTrue(result.exists(), diagnostics)
        report = json.loads(result.read_text(encoding='utf-8'))
        self.assertTrue(report['passed'], report)
        for error in ('ReferenceError:', 'TypeError:', 'Cannot assign', 'Unable to assign', 'QQmlApplicationEngine failed'):
            self.assertNotIn(error, diagnostics)
        return report

    def test_snapshot_comparison_and_evidence_cutoffs(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-comparison-') as directory:
            report = self.run_script('comparison', directory)
            self.assertGreaterEqual(len(report['checks']), 25)
            self.assertTrue(all(report['checks'].values()), report)

    def test_populated_compact_comparison_keyboard_and_controls(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-compact-comparison-') as directory:
            # Keep a taller persisted timeline to exercise real saved-layout pressure.
            self.run_script('layout-set', directory, auto=False)
            report = self.run_script('comparison-small', directory)
            for name in ('controls_exposed', 'inspector_controls_exposed', 'change_row_exposed',
                         'results_height', 'tree_height', 'pending_controls', 'search_to_results', 'results_to_tree',
                         'tree_search_to_tree', 'cutoff_enter_compares'):
                self.assertTrue(report['checks'][name], report)

    def test_layout_drag_keyboard_persistence_and_reset(self):
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-layout-') as directory:
            configured = self.run_script('layout-set', directory, auto=False)
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

    def test_native_interaction_smoke(self):
        self.run_native_smoke('auto')

    def test_explicit_dvb_context(self):
        self.run_native_smoke('dvb')

    def test_failed_inspect_clears_native_evidence(self):
        binary = Path(os.environ.get('SHOWPSISI_QT', ROOT / ('build/cloud/bin/showpsisi-qt' + EXE)))
        if not binary.exists():
            self.skipTest('Build the native Qt target or set SHOWPSISI_QT')
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-error-') as directory:
            result = Path(directory) / 'result.json'
            env = native_environment()
            env.update(SHOWPSISI_SCRIPT='inspect-error', SHOWPSISI_TEST_RESULT=str(result), SHOWPSISI_SETTINGS_PATH=str(Path(directory) / 'settings.ini'))
            with (Path(directory) / 'ui.log').open('w+', encoding='utf-8') as log:
                process = subprocess.Popen([str(binary)], env=env, cwd=ROOT, stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 15
                    while not result.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.1)
                finally:
                    process.terminate()
                    process.wait(timeout=5)
                log.seek(0)
                diagnostics = log.read()
            self.assertTrue(result.exists(), diagnostics)
            report = json.loads(result.read_text(encoding='utf-8'))
            self.assertTrue(report['passed'], report)
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
                env.update(SHOWPSISI_SAMPLE=str(fixture), SHOWPSISI_SCRIPT='plaintext',
                           SHOWPSISI_TEST_RESULT=str(result), SHOWPSISI_SCREENSHOT=str(temp / 'literal.png'), SHOWPSISI_SETTINGS_PATH=str(temp / 'settings.ini'))
                with (temp / 'ui.log').open('w+', encoding='utf-8') as log:
                    process = subprocess.Popen([str(binary)], env=env, cwd=ROOT, stdout=log, stderr=log)
                    try:
                        deadline = time.monotonic() + 15
                        while not result.exists() and process.poll() is None and time.monotonic() < deadline:
                            time.sleep(0.1)
                        time.sleep(0.6)  # Allow asynchronous image fetches, if any, to reach the trap.
                    finally:
                        process.terminate()
                        process.wait(timeout=5)
                    log.seek(0)
                    diagnostics = log.read()
                self.assertTrue(result.exists(), diagnostics)
                report = json.loads(result.read_text(encoding='utf-8'))
                self.assertTrue(report['passed'], report)
                self.assertGreaterEqual(report['matched_text_items'], 3)
                self.assertTrue(report['comparison_literal'])
                self.assertEqual(report['unsafe_text_items'], 0)
                self.assertGreaterEqual(report['tooltip_text_items'], 1)
                self.assertEqual(requests, [], 'Markup caused a network image request')
                for error in ('ReferenceError:', 'TypeError:', 'Cannot assign', 'Unable to assign'):
                    self.assertNotIn(error, diagnostics)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def run_native_smoke(self, standards):
        binary = Path(os.environ.get('SHOWPSISI_QT', ROOT / ('build/cloud/bin/showpsisi-qt' + EXE)))
        if not binary.exists():
            self.skipTest('Build the native Qt target or set SHOWPSISI_QT')
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-') as directory:
            temp = Path(directory)
            result, screenshot, trace = temp / 'result.json', temp / 'screen.png', temp / 'trace.jsonl'
            env = native_environment()
            env.update(SHOWPSISI_SCRIPT='smoke', SHOWPSISI_STANDARDS=standards, SHOWPSISI_TEST_RESULT=str(result),
                       SHOWPSISI_SCREENSHOT=str(screenshot), SHOWPSISI_TRACE=str(trace),
                       SHOWPSISI_ARTIFACT_DIR=str(temp), SHOWPSISI_SETTINGS_PATH=str(temp / 'settings.ini'))
            with (temp / 'stderr.log').open('w+', encoding='utf-8') as log:
                process = subprocess.Popen([str(binary)], cwd=ROOT, env=env, stdout=log, stderr=log)
                try:
                    deadline = time.monotonic() + 35
                    while not result.exists() and process.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.1)
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                log.seek(0)
                diagnostics = log.read()
            self.assertTrue(result.exists(), 'Qt smoke did not finish:\n' + diagnostics + '\n' + (trace.read_text(encoding='utf-8') if trace.exists() else 'No trace'))
            report = json.loads(result.read_text(encoding='utf-8'))
            self.assertTrue(report['passed'], report)
            self.assertEqual(report['standards_context'], standards)
            self.assertTrue(report['native_tree'])
            self.assertTrue(report['history_cutoff'])
            self.assertEqual(len(report['search']), 8)
            self.assertTrue(all(report['search'].values()), report['search'])
            self.assertGreater(report['references'], 0, 'Expected verified SDT specification metadata')
            self.assertEqual(report['services'], 6)
            self.assertEqual(len(report['checks']), 5)
            self.assertEqual(screenshot.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            self.assertTrue(list(temp.glob('qt-export-*.ts.manifest.json')))
            for error in ('ReferenceError:', 'TypeError:', 'Cannot assign', 'Unable to assign', 'QQmlApplicationEngine failed'):
                self.assertNotIn(error, diagnostics)


if __name__ == '__main__':
    unittest.main()
