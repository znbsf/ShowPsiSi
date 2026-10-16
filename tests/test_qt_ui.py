"""Native Qt Quick integration smoke against the real NDJSON C++ backend.

Build showpsisi-qt first. Optional SHOWPSISI_QT and SHOWPSISI_CORE select
binaries. A missing Qt binary skips the test; an installed but broken one fails.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def native_environment():
    env = os.environ.copy()
    libraries = [ROOT / '.deps/Qt/6.7.3/gcc_64/lib',
                 ROOT / '.deps/python/PySide6/Qt/lib',
                 ROOT / '.deps/tsduck/usr/lib',
                 ROOT / '.deps/tsduck/usr/lib/x86_64-linux-gnu']
    env['LD_LIBRARY_PATH'] = os.pathsep.join(str(p) for p in libraries if p.exists()) + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    env.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
               SHOWPSISI_ROOT=str(ROOT), SHOWPSISI_AUTO='1',
               SHOWPSISI_CORE=env.get('SHOWPSISI_CORE', str(ROOT / 'build/bin/showpsisi-core')),
               SHOWPSISI_SAMPLE=str(ROOT / 'samples/generated/lab.ts'))
    # TSDuck resolves its XML/name definitions relative to this search path.
    env['TSPLUGINS_PATH'] = str(ROOT / '.deps/tsduck/usr/lib/tsduck')
    return env


class NativeQtTests(unittest.TestCase):
    def test_native_interaction_smoke(self):
        self.run_native_smoke('auto')

    def test_explicit_dvb_context(self):
        self.run_native_smoke('dvb')

    def run_native_smoke(self, standards):
        binary = Path(os.environ.get('SHOWPSISI_QT', ROOT / 'build/cloud/bin/showpsisi-qt'))
        if not binary.exists():
            self.skipTest('Build the native Qt target or set SHOWPSISI_QT')
        with tempfile.TemporaryDirectory(prefix='showpsisi-qt-') as directory:
            temp = Path(directory)
            result, screenshot, trace = temp / 'result.json', temp / 'screen.png', temp / 'trace.jsonl'
            env = native_environment()
            env.update(SHOWPSISI_SCRIPT='smoke', SHOWPSISI_STANDARDS=standards, SHOWPSISI_TEST_RESULT=str(result),
                       SHOWPSISI_SCREENSHOT=str(screenshot), SHOWPSISI_TRACE=str(trace),
                       SHOWPSISI_ARTIFACT_DIR=str(temp))
            with (temp / 'stderr.log').open('w+') as log:
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
            self.assertTrue(result.exists(), 'Qt smoke did not finish:\n' + diagnostics + '\n' + (trace.read_text() if trace.exists() else 'No trace'))
            report = json.loads(result.read_text())
            self.assertTrue(report['passed'], report)
            self.assertEqual(report['standards_context'], standards)
            self.assertTrue(report['native_tree'])
            self.assertGreater(report['references'], 0, 'Expected verified SDT specification metadata')
            self.assertEqual(report['services'], 6)
            self.assertEqual(len(report['checks']), 5)
            self.assertEqual(screenshot.read_bytes()[:8], b'\x89PNG\r\n\x1a\n')
            self.assertTrue(list(temp.glob('qt-export-*.ts.manifest.json')))
            for error in ('ReferenceError:', 'TypeError:', 'Cannot assign', 'Unable to assign', 'QQmlApplicationEngine failed'):
                self.assertNotIn(error, diagnostics)


if __name__ == '__main__':
    unittest.main()
