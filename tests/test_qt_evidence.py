"""Deterministic artifact retention tests; no Qt binary or SDK is required."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts' / 'ci'))
from qt_evidence import MAX_EVIDENCE_BYTES, retain_qt_evidence
from qt_result import wait_for_qt_result


class QtEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='qt-evidence-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.destination = self.root / 'evidence' / self._testMethodName / 'run'

    def test_incomplete_json_retained_after_timeout_and_early_exit(self):
        for exit_code in (None, 3):
            with self.subTest(exit_code=exit_code):
                destination = self.destination / str(exit_code)
                with self.assertRaisesRegex(AssertionError, 'did not publish complete JSON') as failure:
                    with tempfile.TemporaryDirectory(dir=self.root) as temporary:
                        source = Path(temporary)
                        report, log, trace = (source / name for name in ('result.json', 'ui.log', 'trace.jsonl'))
                        with retain_qt_evidence(destination, [report, log, trace, source / 'absent.png']):
                            report.write_bytes(b'{"passed":')
                            log.write_bytes(b'injected loader diagnostics\n')
                            trace.write_bytes(b'{"event":"started"}\n')
                            process = mock.Mock()
                            process.poll.return_value = exit_code
                            # A zero deadline exercises timeout deterministically
                            # without sleeping or launching a fake process.
                            wait_for_qt_result(report, process, timeout=0)
                self.assertIsInstance(failure.exception.__cause__, json.JSONDecodeError)
                self.assertFalse(source.exists())
                self.assertEqual((destination / report.name).read_bytes(), b'{"passed":')
                self.assertEqual((destination / log.name).read_bytes(), b'injected loader diagnostics\n')
                self.assertEqual((destination / trace.name).read_bytes(), b'{"event":"started"}\n')
                self.assertFalse((destination / 'absent.png').exists())

    def test_completed_failed_report_and_screenshot_are_retained(self):
        source = self.root / 'run'
        source.mkdir()
        report, screenshot = source / 'result.json', source / 'screen.png'
        content = b'{"passed":false,"checks":{"export":false}}'
        png = b'\x89PNG\r\n\x1a\nretention fixture'
        with self.assertRaisesRegex(AssertionError, 'export'):
            with retain_qt_evidence(self.destination, [report, screenshot]):
                report.write_bytes(content)
                screenshot.write_bytes(png)
                self.assertTrue(json.loads(report.read_text())['passed'], 'export failed')
        self.assertEqual((self.destination / report.name).read_bytes(), content)
        self.assertEqual((self.destination / screenshot.name).read_bytes(), png)

    def test_qml_diagnostics_retained_even_with_successful_report(self):
        report, log = self.root / 'result.json', self.root / 'ui.log'
        with self.assertRaisesRegex(AssertionError, 'ReferenceError'):
            with retain_qt_evidence(self.destination, [report, log]):
                report.write_bytes(b'{"passed":true}')
                # Close and flush the log before the retention scope exits.
                with log.open('w', encoding='utf-8') as output:
                    output.write('ReferenceError: missingModel is not defined\n')
                self.assertNotIn('ReferenceError:', log.read_text())
        self.assertEqual((self.destination / report.name).read_bytes(), b'{"passed":true}')
        self.assertIn('missingModel', (self.destination / log.name).read_text())

    def test_later_cross_run_assertion_retains_both_runs(self):
        first, second = self.root / 'first.json', self.root / 'second.json'
        with self.assertRaisesRegex(AssertionError, 'sizes differ'):
            with retain_qt_evidence(self.destination, [first, second]):
                first.write_bytes(b'{"passed":true,"size":520}')
                second.write_bytes(b'{"passed":true,"size":500}')
                self.assertEqual(json.loads(first.read_text())['size'],
                                 json.loads(second.read_text())['size'], 'sizes differ')
        self.assertEqual({path.name for path in self.destination.iterdir()}, {'first.json', 'second.json'})

    def test_cap_includes_exact_limit_and_excludes_oversized_files(self):
        exact, large, unrelated = (self.root / name for name in ('exact.log', 'large.png', 'unrelated.txt'))
        with retain_qt_evidence(self.destination, [exact, large, self.root / 'missing.json', self.root]):
            with exact.open('wb') as output:
                output.truncate(MAX_EVIDENCE_BYTES)
            with large.open('wb') as output:
                output.truncate(MAX_EVIDENCE_BYTES + 1)
            unrelated.write_text('not selected', encoding='utf-8')
        self.assertEqual((self.destination / exact.name).stat().st_size, 5 * 1024 * 1024)
        self.assertEqual([path.name for path in self.destination.iterdir()], [exact.name])

    def test_file_growth_after_stat_cannot_exceed_cap(self):
        source = self.root / 'growing.log'
        source.write_bytes(b'old')
        real_stat = Path.stat

        def stat_then_grow(path, *args, **kwargs):
            result = real_stat(path, *args, **kwargs)
            if path == source:
                with source.open('wb') as output:
                    output.truncate(MAX_EVIDENCE_BYTES + 1)
            return result

        with mock.patch.object(Path, 'stat', stat_then_grow):
            with retain_qt_evidence(self.destination, [source]):
                pass
        self.assertFalse((self.destination / source.name).exists())

    def test_retention_io_error_preserves_original_exception_and_other_files(self):
        report, log = self.root / 'result.json', self.root / 'ui.log'
        report.write_bytes(b'{"passed":')
        log.write_bytes(b'last diagnostics')
        original = subprocess.TimeoutExpired('test-qt', 2)
        real_write_bytes = Path.write_bytes

        def fail_report_copy(path, data):
            if path == self.destination / report.name:
                raise OSError('injected evidence I/O error')
            return real_write_bytes(path, data)

        with self.assertRaises(subprocess.TimeoutExpired) as failure:
            with mock.patch.object(Path, 'write_bytes', fail_report_copy):
                with retain_qt_evidence(self.destination, [report, log]):
                    raise original
        self.assertIs(failure.exception, original)
        self.assertEqual((self.destination / log.name).read_bytes(), b'last diagnostics')
        self.assertIn('injected evidence I/O error', '\n'.join(original.__notes__))

    def test_destination_error_does_not_replace_original_assertion(self):
        destination = self.root / 'not-a-directory'
        destination.write_text('block mkdir', encoding='utf-8')
        original = AssertionError('original QML failure')
        with self.assertRaises(AssertionError) as failure:
            with retain_qt_evidence(destination / 'child', []):
                raise original
        self.assertIs(failure.exception, original)

    def test_retention_error_fails_otherwise_successful_scope(self):
        self.destination.parent.mkdir(parents=True)
        self.destination.write_text('block mkdir', encoding='utf-8')
        with self.assertRaises(FileExistsError):
            with retain_qt_evidence(self.destination, []):
                pass

    def test_disabled_destination_does_not_read_or_copy_sources(self):
        source = self.root / 'result.json'
        with mock.patch.object(Path, 'stat', side_effect=AssertionError('retention disabled')):
            with retain_qt_evidence(None, [source]):
                source.write_bytes(b'{"passed":true}')
        self.assertFalse(self.destination.exists())


if __name__ == '__main__':
    unittest.main()
