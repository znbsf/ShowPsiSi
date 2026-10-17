"""Compiled Qt resource resolution, separate from Windows deployment acceptance."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts/ci'))
from qt_result import wait_for_qt_result
EXE = '.exe' if os.name == 'nt' else ''


class QtResourcePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = Path(os.environ.get('SHOWPSISI_QT', ROOT / ('build/cloud/bin/showpsisi-qt' + EXE)))
        if not cls.binary.is_file():
            raise unittest.SkipTest('Build the native Qt target or set SHOWPSISI_QT')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='portable Qt 空间 ')
        self.base = Path(self.tmp.name)
        self.package = self.base / 'app spaced 路径'
        bindir = self.package / 'bin'
        bindir.mkdir(parents=True)
        # Existing deployed Windows DLL/plugin/QML output is necessary here;
        # the dedicated portable CI check tests a narrower fresh staged tree.
        for source in self.binary.parent.iterdir():
            if source.is_dir() and source.name in ('platforms', 'qml', 'styles', 'imageformats', 'networkinformation', 'tls', 'iconengines', 'generic'):
                shutil.copytree(source, bindir / source.name)
            elif source.is_file() and (source.name in (self.binary.name, 'showpsisi-core' + EXE, 'qt.conf') or source.suffix.lower() in ('.dll', '.xml', '.names')):
                shutil.copy2(source, bindir / source.name)
        (bindir / 'showpsisi-portable.json').write_text('{}')
        for name in ('api/tools.json', 'extensions/demo.json', 'references/standards.json', 'samples/generated/lab.ts'):
            target = self.package / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        self.cwd = self.base / 'unrelated cwd'
        (self.cwd / 'api').mkdir(parents=True)
        (self.cwd / 'api/tools.json').write_text('misleading invalid cwd schema')

    def tearDown(self):
        self.tmp.cleanup()

    def run_qt(self, script, overrides=None):
        result = self.base / 'result.json'
        env = {k: v for k, v in os.environ.items() if not k.startswith('SHOWPSISI_')}
        env.update(SHOWPSISI_SCRIPT=script, SHOWPSISI_TEST_RESULT=str(result),
                   SHOWPSISI_AUTO='1' if script == 'smoke' else '0',
                   SHOWPSISI_ARTIFACT_DIR=str(self.base), SHOWPSISI_SCREENSHOT=str(self.base / 'screen.png'),
                   SHOWPSISI_SETTINGS_PATH=str(self.base / 'settings.ini'),
                   QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
        env.update(overrides or {})
        with (self.base / 'qt.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([str(self.package / 'bin' / self.binary.name), '--showpsisi-development'],
                                       cwd=self.cwd, env=env, stdout=log, stderr=log)
            try:
                report = wait_for_qt_result(result, process, 60)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        self.assertTrue(report['passed'], report)
        return report

    def test_direct_executable_ignores_unrelated_cwd_and_uses_own_sample(self):
        source = self.package / 'samples/generated/lab.ts'
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        report = self.run_qt('smoke')
        self.assertEqual(report['services'], 6)
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).hexdigest())

    def test_missing_packaged_schema_fails_visibly(self):
        (self.package / 'api/tools.json').unlink()
        report = self.run_qt('lifecycle-startup')
        self.assertIn('api/tools.json', report['error'])

    def test_relative_root_override_fails_visibly(self):
        report = self.run_qt('lifecycle-startup', {'SHOWPSISI_ROOT': '.'})
        self.assertIn('absolute directory', report['error'])

    def test_relative_core_override_fails_visibly(self):
        report = self.run_qt('lifecycle-startup', {'SHOWPSISI_CORE': 'showpsisi-core' + EXE})
        self.assertIn('absolute file path', report['error'])

    def test_missing_runtime_model_fails_visibly(self):
        (self.package / 'bin/tsduck.tables.model.xml').unlink()
        report = self.run_qt('lifecycle-startup')
        self.assertIn('tsduck.tables.model.xml', report['error'])

    def test_missing_packaged_core_fails_visibly(self):
        (self.package / 'bin' / ('showpsisi-core' + EXE)).unlink()
        report = self.run_qt('lifecycle-startup')
        self.assertIn('Backend executable is missing', report['error'])
