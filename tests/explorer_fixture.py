"""Real wire input: shared PID types, multi-section tables, repeats and bad CRC."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from make_fixture import section, descriptor, word, crc


def explorer_fixture():
    def sdt(number=0, version=1, bad=False):
        d = descriptor(0x48, b'\x01\x00\x04Test')
        raw = bytearray(section(0x42, 1, version, word(2)+b'\xff'+word(100+number)+b'\xff'+word(0x8000+len(d))+d))
        raw[6], raw[7] = number, 1 if version == 1 else 0
        raw[-4:] = crc(raw[:-4]).to_bytes(4, 'big')
        if bad:
            raw[-1] ^= 1
        return bytes(raw)
    parts = [(0, section(0, 1, 1, word(100)+word(0xe100)+word(101)+word(0xe101))),
             (0x100, section(2, 100, 1, word(0xe200)+word(0xf000))),
             (0x101, section(2, 101, 1, word(0xe201)+word(0xf000))),
             (0x11, sdt()), (0x11, sdt(number=1)), (0x11, sdt(number=1, bad=True)),
             (0x11, sdt(version=2, bad=True)),
             (0x11, section(0x4a, 2, 1, word(0xf000)+word(0xf000))),
             (0x11, section(0x80, 3, 1, b'private-evidence')),
             (0x11, sdt()), (0x11, sdt(number=1))]
    counters, packets = {}, []
    for pid, raw in parts:
        cc = counters.get(pid, 0); counters[pid] = (cc+1) % 16
        packets.append(bytes([0x47, 0x40|(pid >> 8), pid & 255, 0x10|cc, 0])+raw+b'\xff'*(183-len(raw)))
    return b''.join(packets)
