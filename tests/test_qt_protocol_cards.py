"""Actual compiled Qt protocol metadata, separate from Windows/native acceptance."""
import tempfile
import unittest
from pathlib import Path
import test_qt_ui as qt
from protocol_ui_fixture import protocol_ui_fixture


class QtProtocolCardTests(unittest.TestCase):
    def test_real_metadata_paging_in_both_themes(self):
        for theme in ('dark', 'light'):
            with self.subTest(theme=theme), tempfile.TemporaryDirectory() as td:
                path=Path(td)/'cards.ts';raw=protocol_ui_fixture();path.write_bytes(raw)
                helper=qt.NativeQtTests();helper._testMethodName='protocol-cards-'+theme
                report=helper.run_script('protocol-cards',td,timeout=30,overrides={
                    'SHOWPSISI_SAMPLE':str(path),'SHOWPSISI_STANDARDS':'dvb','SHOWPSISI_THEME':theme})
                self.assertTrue(all(report['checks'].values()),report)
                self.assertGreater(report['total'],40)
                self.assertEqual(path.read_bytes(),raw)


if __name__=='__main__':unittest.main()
