"""Synthetic valid PAT/PMT/SDT evidence; no owner stream data."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from make_fixture import section,descriptor,word

def fixture(ambiguous=False):
    def sdt(tsid,onid,services):
        payload=word(onid)+b'\xff'
        for sid,name in services:
            desc=b'' if name is None else descriptor(0x48,b'\x01\x03Lab'+bytes([len(name)])+name.encode('ascii'))
            payload+=word(sid)+b'\xfc'+word(0x8000+len(desc))+desc
        return section(0x42,tsid,1,payload)
    pairs=[(0,section(0,0x1001,1,b''.join(word(sid)+word(0xe000+pid) for sid,pid in [(101,0x100),(102,0x110),(103,0x120),(104,0x130)]))),
           (0,section(0,0x1002,1,word(101)+word(0xe200))),
           (0x11,sdt(0x1001,0x2001,[(101,'Alpha News'),(102,'Beta Music'),(103,None)])),
           (0x11,sdt(0x1002,0x2001,[(101,'Other Transport')]))]
    for sid,pid in [(101,0x100),(102,0x110),(103,0x120),(104,0x130),(101,0x200)]:
        pairs.append((pid,section(2,sid,1,word(0xe000+pid+1)+word(0xf000)+b'\x1b'+word(0xe000+pid+1)+word(0xf000))))
    if ambiguous:pairs.append((0x11,sdt(0x1001,0x2002,[(101,'Other Network')])))
    cc={};packets=[]
    for pid,raw in pairs:
        assert len(raw)<=183
        n=cc.get(pid,0);cc[pid]=(n+1)%16
        packets.append(bytes([0x47,0x40|(pid>>8),pid&255,0x10|n,0])+raw+b'\xff'*(183-len(raw)))
    return b''.join(packets)
