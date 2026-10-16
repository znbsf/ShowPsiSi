"""Deterministic signalling-only DVB multiplex. No encoded audio/video or PCR."""
import argparse, hashlib, json, struct
from pathlib import Path
from collections import defaultdict

def crc(data):
    v = 0xffffffff
    for b in data:
        v ^= b << 24
        for _ in range(8): v = ((v << 1) ^ (0x04c11db7 if v & 0x80000000 else 0)) & 0xffffffff
    return v

def section(tid, ext, version, payload):
    n = len(payload) + 9
    b = bytes([tid, (0xb0 if tid in (0,2) else 0xf0) | n >> 8, n & 255]) + struct.pack('>HBBB',ext,0xc1 | version << 1,0,0) + payload
    return b + struct.pack('>I', crc(b))

def descriptor(tag, data): return bytes([tag, len(data)]) + data
def word(n): return struct.pack('>H',n)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--mib',type=int,default=32); ap.add_argument('--output',default='samples/generated/lab.ts'); a=ap.parse_args()
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    names=['World News','Culture HD','Sports HD','Cinema','Discovery','Music Live']
    pat=section(0,0x1001,1,b''.join(word(101+i)+word(0xe000+0x100+i) for i in range(6)))
    pmts=[section(2,101+i,1,word(0xffff)+word(0xf000)) for i in range(6)]
    def sdt(v, malformed=False):
        payload=word(0x2001)+b'\xff'
        for i,name in enumerate(names):
            if v>=2 and i==2: name='Sports UHD'
            provider=b'ShowPsiSi Lab'; n=name.encode()
            desc=descriptor(0x48,bytes([1,len(provider)])+provider+bytes([len(n)])+n)
            desc+=descriptor(0x5f,struct.pack('>I',0x53505349))
            lcn=(i+1)*10 if v<3 else [20,30,10,40,50,60][i]
            desc+=descriptor(0xe1,word(lcn)+bytes([1 if i==0 else 2 if i in (1,4) else 3]))
            desc+=descriptor(0xe2,b'\xca\xfe\xba\xbe')
            if malformed and i==5: desc+=b'\xe3\x08\x01'
            payload+=word(101+i)+b'\xff'+word(0x8000+len(desc))+desc
        return section(0x42,0x1001,v,payload)
    def eit(i):
        payload=word(0x1001)+word(0x2001)+b'\x00\x4e'
        for j,title in enumerate(['Morning edition','Next on '+names[i]]):
            title=title.encode(); desc=descriptor(0x4d,b'eng'+bytes([len(title)])+title+b'\x00')
            # MJD for 2026-10-17, 09:00 and 10:00 UTC, 1h duration.
            import datetime
            mjd=(datetime.date(2026,10,17)-datetime.date(1858,11,17)).days
            payload+=word(200+i*2+j)+word(mjd)+bytes([0x09 if j==0 else 0x10,0,0,1,0,0])+word(0x8000+len(desc))+desc
        return section(0x4e,101+i,1,payload)
    cc=defaultdict(int)
    def packets(pid,b):
        result=[]; first=True
        while b:
            part=(b'\x00' if first else b'')+b[:183 if first else 184]; b=b[183 if first else 184:]
            result.append(bytes([0x47,(pid>>8)|(0x40 if first else 0),pid&255,0x10|cc[pid]])+part+b'\xff'*(184-len(part)))
            cc[pid]=(cc[pid]+1)%16; first=False
        return b''.join(result)
    total=(a.mib*1024*1024//188)//1000*1000
    null=bytes([0x47,0x1f,0xff,0x10])+b'\xff'*184
    with out.open('wb') as f:
        for cycle in range(total//1000):
            v=1+min(2,cycle*3//(total//1000)); chunks=[packets(0,pat)]
            chunks += [packets(0x100+i,b) for i,b in enumerate(pmts)]
            chunks.append(packets(0x11,sdt(v)))
            chunks += [packets(0x12,eit(i)) for i in range(6)]
            if cycle in (5,40): chunks.append(packets(0x11,sdt(v)[:-1]+bytes([sdt(v)[-1]^1])))
            if cycle==20: chunks.append(packets(0x11,sdt(31,True)))
            block=b''.join(chunks); f.write(block+null*(1000-len(block)//188))
    manifest={'kind':'synthetic-signalling-only','bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'packet_size':188,'bitrate':8000000,'clock':'assumed replay bitrate; no PCR','expected_services':6,'expected_sdt_versions':[1,2,3,31],'crc_errors':2,'malformed_descriptor_sections':1,'unknown_private_tag':226}
    out.with_suffix('.manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest))

if __name__=='__main__': main()
