"""Synthetic real AIT stream discovered by its PAT/PMT, with enough cards to page."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from make_fixture import descriptor, section, word
from test_application_summaries import application, ait, packetize


def protocol_ui_fixture():
    pat = section(0, 1, 0, word(101) + word(0xe100))
    signalling = descriptor(0x6f, word(0x10) + bytes([0xe1]))
    pmt = section(2, 101, 0, word(0xe201) + word(0xf000) +
                  b'\x05' + word(0xe150) + word(0xf000 | len(signalling)) + signalling)
    table = ait([application(identifier=n) for n in range(16)])
    return packetize([(0, pat), (0x100, pmt), (0x150, table)])
