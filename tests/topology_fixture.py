"""Deterministic wire fixtures for the real shared topology engine; no mock graph."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from make_fixture import section, descriptor, word, crc


def versioned(raw, *, number=0, last=0, current=True, bad=False):
    raw=bytearray(raw);raw[5]=(raw[5]&254)|bool(current);raw[6]=number;raw[7]=last
    raw[-4:]=crc(raw[:-4]).to_bytes(4,'big')
    if bad: raw[-1]^=1
    return bytes(raw)


def pat(tsid=1, programs=((100,0x100),), version=1, **kwargs):
    return 0,versioned(section(0,tsid,version,b''.join(word(sid)+word(0xe000|pid) for sid,pid in programs)),**kwargs)


def pmt(sid=100,pid=0x100,streams=((0x1b,0x200,b''),(0x0f,0x201,b'')),pcr=0x200,version=1,**kwargs):
    payload=word(0xe000|pcr)+word(0xf000)
    payload+=b''.join(bytes([kind])+word(0xe000|es)+word(0xf000|len(d))+d for kind,es,d in streams)
    return pid,versioned(section(2,sid,version,payload),**kwargs)


def sdt(onid=2,tsid=1,services=((100,'Topology Lab'),),tid=0x42,version=1,pid=0x11,**kwargs):
    payload=word(onid)+b'\xff'
    for sid,name in services:
        raw=name.encode('utf8');d=descriptor(0x48,b'\x01\x00'+bytes([len(raw)])+raw)
        payload+=word(sid)+b'\xff'+word(0x8000|len(d))+d
    return pid,versioned(section(tid,tsid,version,payload),**kwargs)


def nit(network=10,transports=((2,1,b''),),tid=0x40,version=1,**kwargs):
    loop=b''.join(word(tsid)+word(onid)+word(0xf000|len(d))+d for onid,tsid,d in transports)
    return 0x10,versioned(section(tid,network,version,word(0xf000)+word(0xf000|len(loop))+loop),**kwargs)


def channel(major=7,minor=1,tsid=1,program=100,source=55,name='LAB',hidden=False,desc=b''):
    short=name.encode('utf-16-be').ljust(14,b'\0')[:14]
    numbers=(0xf00000|(major<<10)|minor).to_bytes(3,'big')
    flags=0x0dc2|(0x1000 if hidden else 0)
    return short+numbers+b'\x04'+b'\0'*4+word(tsid)+word(program)+word(flags)+word(source)+word(0xfc00|len(desc))+desc


def vct(channels=None,tid=0xc8,tsid=1,version=1,pid=0x1ffb,**kwargs):
    channels=[channel()] if channels is None else channels
    return pid,versioned(section(tid,tsid,version,b'\0'+bytes([len(channels)])+b''.join(channels)+word(0xfc00)),**kwargs)


def japan_descriptors(remote=7,sid=100):
    # ARIB STD-B10 TS information and partial reception. No RF-layer inference.
    return descriptor(0xcd,bytes([remote,1])+b'\x0f\x01'+word(sid))+descriptor(0xfb,word(sid))


def parts(profile='dvb'):
    base=[pat(),pmt()]
    if profile=='atsc':return base+[vct(),vct([channel(0x3f1,7,source=55,name='Cable')],tid=0xc9)]
    return base+[sdt(services=((100,'\x1b(JTopology Lab' if profile=='isdb-japan' else 'Topology Lab'),)),nit(transports=((2,1,japan_descriptors() if profile=='isdb-japan' else b''),(3,9,b'')))]


def delivery_parts():
    """DVB-S2/C/T declarations, with co-located nominal satellite candidates."""
    satellite=descriptor(0x43,bytes.fromhex('0115380001308602200003'))
    cable=descriptor(0x44,bytes.fromhex('04500000fff2050069000f'))
    terrestrial=descriptor(0x5a,bytes.fromhex('03dfd2401f8112ffffffff'))
    return [pat(),pmt(),sdt(),nit(transports=((2,1,satellite),(3,9,cable),(3,10,terrestrial)))]


def write_ts(path,sections):
    counters={};packets=[]
    for pid,data in sections:
        first=True
        while data:
            size=183 if first else 184;chunk=(b'\0' if first else b'')+data[:size];data=data[size:]
            cc=counters.get(pid,0);counters[pid]=(cc+1)%16
            packets.append(bytes([0x47,(0x40 if first else 0)|(pid>>8),pid&255,0x10|cc])+chunk+b'\xff'*(184-len(chunk)));first=False
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b''.join(packets));return path
