"""Failure/identity contracts for the Qt component evidence harness, without GUI."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/ci'))
import qt_components as harness

class ComponentHarnessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
    def test_success_retains_command_and_output(self):
        value=harness.execute([sys.executable,'-c',"print('completed')"],self.directory,'probe',os.environ.copy())
        self.assertIn('completed',value)
        status=json.loads((self.directory/'probe.status.json').read_text(encoding='utf-8'))
        self.assertEqual(status['returncode'],0);self.assertTrue(status['started'])
        self.assertTrue((self.directory/'probe.command.json').is_file())
    def test_nonzero_retains_failure_output(self):
        with self.assertRaisesRegex(RuntimeError,'exited 3'):
            harness.execute([sys.executable,'-c',"print('failed output',flush=True);raise SystemExit(3)"],self.directory,'bad',os.environ.copy())
        self.assertIn('failed output',(self.directory/'bad.stdout.log').read_text(encoding='utf-8'))
        self.assertEqual(json.loads((self.directory/'bad.status.json').read_text(encoding='utf-8'))['returncode'],3)
    def timeout_case(self,out,err):
        process=mock.Mock(pid=12345)
        expired=subprocess.TimeoutExpired(['probe'],.1,output=out,stderr=err)
        process.communicate.side_effect=[expired,subprocess.TimeoutExpired(['probe'],5)]
        with mock.patch.object(harness.subprocess,'Popen',return_value=process),mock.patch.object(harness,'stop_owned') as stop:
            with self.assertRaises(subprocess.TimeoutExpired):
                harness.execute(['probe'],self.directory,'timeout',{},timeout=.1)
            stop.assert_called_once_with(process)
        status=json.loads((self.directory/'timeout.status.json').read_text(encoding='utf-8'))
        self.assertTrue(status['timed_out']);self.assertTrue(status['drain_incomplete'])
        self.assertTrue((self.directory/'timeout.command.json').is_file())
        self.assertEqual((self.directory/'timeout.stdout.log').read_text(encoding='utf-8'),harness.text_output(out))
        self.assertEqual((self.directory/'timeout.stderr.log').read_text(encoding='utf-8'),harness.text_output(err))
    def test_timeout_retains_partial_bytes(self):
        self.timeout_case('部分stdout'.encode(),'部分stderr'.encode())
    def test_timeout_retains_partial_text(self):
        self.timeout_case('partial stdout','partial stderr')
    def test_producer_failure_publishes_failed_receipt_and_binary_identity(self):
        with mock.patch.dict(os.environ,{'SHOWPSISI_CORE':sys.executable}),mock.patch.object(harness,'execute',side_effect=RuntimeError('producer failed')):
            with self.assertRaisesRegex(RuntimeError,'producer failed'):
                harness.run(Path(sys.executable),self.directory)
        receipt=json.loads(next(self.directory.glob('run-*/result.json')).read_text(encoding='utf-8'))
        self.assertFalse(receipt['passed']);self.assertEqual(receipt['stage'],'producer:test_unified_inspector.py')
        expected=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
        self.assertEqual(receipt['binaries']['engine']['sha256'],expected)
        self.assertEqual(receipt['binaries']['runner']['sha256'],expected)
        self.assertIn('not established',receipt['source_to_build_binding'])
        self.assertGreater(len(receipt['source_files']),0)
    def test_missing_engine_publishes_validation_failure(self):
        with mock.patch.dict(os.environ,{'SHOWPSISI_CORE':str(self.directory/'missing.exe')}):
            with self.assertRaises(FileNotFoundError):harness.run(Path(sys.executable),self.directory)
        receipt=json.loads(next(self.directory.glob('run-*/result.json')).read_text(encoding='utf-8'))
        self.assertFalse(receipt['passed']);self.assertEqual(receipt['stage'],'validation')
if __name__=='__main__':unittest.main()
