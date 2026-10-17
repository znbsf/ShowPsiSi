"""TSDuck 3.45 ABI identity and C++20 UTF-8 filesystem regressions."""
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
sys.path.insert(0, str(ROOT / 'scripts'))
from core_client import Core


class SdkMigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='showpsisi-sdk-')
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / '中文 café e\u0301 📡'
        self.folder.mkdir()
        self.core = Core()
        self.addCleanup(self.core.close)

    def test_runtime_headers_and_registry_identity(self):
        capability = self.core.call('capabilities')
        sdk = capability['native_sdk']
        self.assertEqual(sdk['headers'], '3.45-4798')
        self.assertEqual(sdk['headers'], sdk['tsduck_runtime'])
        self.assertEqual(sdk['headers'], sdk['tscore_runtime'])
        self.assertTrue(sdk['version_symbols_enforced'])
        self.assertEqual(sdk['cpp_standard'], 20)
        self.assertEqual(capability['engine'], 'C++ / TSDuck ' + sdk['tsduck_runtime'])
        registry = capability['native_registry']
        self.assertEqual(registry['table_count'], len(registry['table_names']))
        self.assertEqual(registry['descriptor_count'], len(registry['descriptor_names']))
        # XML aliases can outnumber concrete C++ implementations.
        self.assertGreaterEqual(registry['table_count'], 58)
        self.assertGreaterEqual(registry['descriptor_count'], 347)

    def test_unicode_input_query_diff_export_manifest_and_reparse(self):
        source = self.folder / '录制 Ω 📡.ts'
        shutil.copyfile(ROOT / 'samples/generated/lab.ts', source)
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        state = self.core.call('analyze', {'path': str(source), 'standards': 'dvb'})
        self.assertEqual(state['source'], str(source))
        self.assertEqual(state['file_name'], source.name)
        self.assertEqual(self.core.call('query')['source'], str(source))
        diff = self.core.call('diff_snapshots', {'from_packet': 0, 'to_packet': state['packets'] - 1})
        self.assertEqual(diff['source'], str(source))
        service = state['services'][0]
        preview = self.core.call('preview_rename', {'id': service['source_id'], 'service_id': service['id'], 'name': '测试频道 Ω'})
        self.assertEqual(preview['new_version'], (preview['old_version'] + 1) % 32)
        output = self.folder / '导出 📡' / '快照 é.ts'
        receipt = self.core.call('export', {'path': str(output), 'preview_token': preview['token'], 'cycles': 1, 'null_packets': 0})
        self.assertEqual(receipt['source'], str(source))
        self.assertEqual(receipt['path'], str(output))
        manifest = json.loads(Path(str(output) + '.manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest, receipt)
        reparsed = self.core.call('analyze', {'path': str(output), 'standards': 'dvb'})
        self.assertEqual(reparsed['source'], str(output))
        self.assertEqual(reparsed['file_name'], output.name)
        self.assertEqual(next(s for s in reparsed['services'] if s['id'] == service['id'])['name'], '测试频道 Ω')
        self.assertEqual(reparsed['crc_errors'], 0)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            self.core.call('export', {'path': str(output)})

    def test_unicode_extension_and_missing_file_error(self):
        extension = self.folder / '扩展 📡.json'
        shutil.copyfile(ROOT / 'extensions/demo.json', extension)
        self.assertTrue(self.core.call('load_extension', {'path': str(extension)})['requires_rescan'])
        missing = self.folder / '不存在 Ω 📡.json'
        with self.assertRaises(RuntimeError) as error:
            self.core.call('load_extension', {'path': str(missing)})
        self.assertIn(str(missing), str(error.exception))

    def test_unicode_root_argument_is_lossless(self):
        root = self.folder / '配置 根目录 📡'
        (root / 'api').mkdir(parents=True)
        shutil.copyfile(ROOT / 'api/tools.json', root / 'api/tools.json')
        request = {'id': 'unicode-root', 'method': 'capabilities'}
        run = subprocess.run([self.core.proc.args[0], '--root', str(root)], input=json.dumps(request) + '\n', text=True, encoding='utf-8', capture_output=True, timeout=10, check=True)
        response = json.loads(run.stdout)
        self.assertEqual(response['id'], request['id'])
        self.assertEqual(response['result']['native_sdk']['headers'], '3.45-4798')
        self.assertEqual(run.stderr, '')

    def test_unicode_exclusive_output_failure_reports_path(self):
        self.core.call('analyze', {'path': str(ROOT / 'samples/generated/lab.ts')})
        # A component longer than both Linux NAME_MAX and ordinary Windows
        # filenames forces the exclusive-open path without permission changes.
        output = self.folder / ('中' * 300 + '.bin')
        with self.assertRaises(RuntimeError) as error:
            self.core.call('export', {'path': str(output), 'format': 'bin'})
        # Filesystem implementations may reject it during exists() first, but
        # the error must be safely encoded JSON rather than a char8_t array.
        self.assertIsInstance(str(error.exception), str)
        self.assertNotIn('json.exception.type_error', str(error.exception))

    def test_dtmb_context_has_no_invented_regional_charset_or_time(self):
        # A PAT-only file checks configuration without introducing DVB detection.
        from make_fixture import section, word
        raw = section(0, 1, 0, word(101) + word(0xe100))
        path = self.folder / 'DTMB context.ts'
        path.write_bytes(bytes([0x47, 0x40, 0, 0x10, 0]) + raw + b'\xff' * (183 - len(raw)))
        baseline = self.core.call('analyze', {'path': str(path), 'standards': 'auto'})
        for prior in ('isdb-japan', 'isdb-brazil'):
            self.core.call('analyze', {'path': str(path), 'standards': prior})
            state = self.core.call('analyze', {'path': str(path), 'standards': 'dtmb'})
            self.assertEqual(state['standards_context'], 'dtmb')
            self.assertIn('DTMB', state['detected_standards'])
            self.assertEqual(state['text_charset'], baseline['text_charset'])
            self.assertEqual(state['time_reference'], baseline['time_reference'])
            self.assertEqual(state['services'], [])


if __name__ == '__main__':
    unittest.main()
