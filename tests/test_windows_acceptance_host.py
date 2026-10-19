"""Native smoke of the read-only clean-VM evidence collector; never OS acceptance.

Windows PowerShell 5.1 runs the actual helper. Linux reports these tests skipped,
not passed native coverage. No DLL, account, network, registry, or ACL is changed.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/ci/record_windows_acceptance_host.ps1'


@unittest.skipUnless(os.name == 'nt', 'Native Windows PowerShell host evidence requires Windows')
class WindowsAcceptanceHostTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='ShowPsiSi host evidence 测试 ')
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.output = self.root / 'host.json'
        self.artifact = self.root / 'acceptance input.txt'
        self.artifact.write_bytes(b'identity fixture, not executable\n')
        self.powershell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'

    def collect(self, profile='Observe', artifact=None):
        return subprocess.run(
            [str(self.powershell), '-NoLogo', '-NoProfile', '-NonInteractive',
             '-File', str(SCRIPT), '-Output', str(self.output), '-Profile', profile,
             '-Artifact', str(artifact or self.artifact)],
            capture_output=True, timeout=60,
        )

    def read_record(self):
        return json.loads(self.output.read_text(encoding='utf-8-sig'))

    def test_observe_records_real_host_without_application_claims(self):
        result = self.collect()
        self.assertEqual(result.returncode, 0, (result.stdout, result.stderr))
        record = self.read_record()
        self.assertTrue(record['collection_complete'])
        self.assertTrue(record['profile_satisfied'])
        self.assertEqual(record['profile'], 'Observe')
        self.assertEqual(record['errors'], [])
        for name in ('native_windows_desktop_verified', 'offline_verified', 'no_runtime_installer_verified'):
            self.assertIs(record[name], False, name)
        self.assertEqual(record['artifact_sha256'][0]['sha256'], hashlib.sha256(self.artifact.read_bytes()).hexdigest())
        self.assertEqual({Path(item['path']).name.lower() for item in record['shared_required_vc']}, {
            'msvcp140.dll', 'msvcp140_1.dll', 'msvcp140_2.dll', 'vcruntime140.dll', 'vcruntime140_1.dll',
        })
        self.assertEqual(record['os']['process_bits'], 64)
        self.assertNotIn('username', record['token'])
        self.assertNotIn('ip_address', str(record['network_interfaces']))

    def test_existing_evidence_is_not_overwritten(self):
        self.output.write_bytes(b'previous evidence must survive\n')
        original = self.output.read_bytes()
        result = self.collect()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.output.read_bytes(), original)

    def test_missing_input_retains_failure_evidence(self):
        result = self.collect(artifact=self.root / 'absent.txt')
        self.assertNotEqual(result.returncode, 0)
        record = self.read_record()
        self.assertFalse(record['collection_complete'])
        self.assertFalse(record['profile_satisfied'])
        self.assertTrue(any('Acceptance input missing:' in error for error in record['errors']))
        self.assertFalse(record['artifact_sha256'][0]['exists'])

    def test_clean_profile_cannot_silently_accept_equipped_or_admin_host(self):
        result = self.collect(profile='CleanNoSharedVc')
        record = self.read_record()
        self.assertTrue(record['collection_complete'], record)
        expected = (
            record['os']['native_machine'] == '0x8664'
            and record['os']['process_machine'] == '0x0000'
            and record['os']['build'] >= 17763
            and record['os']['installation_type'] == 'Client'
            and record['token']['standard_user']
            and not any(item['exists'] for item in record['shared_required_vc'])
            and not record['shared_other_vc14']
            and all(item['exists'] for item in record['windows_components'])
        )
        self.assertEqual(record['profile_satisfied'], expected, record)
        self.assertEqual(result.returncode == 0, expected, (result.stdout, result.stderr))
        self.assertEqual(bool(record['errors']), not expected, record)
        # This assertion validates the collector decision, never application boot.
        self.assertFalse(record['native_windows_desktop_verified'])


if __name__ == '__main__':
    unittest.main()
