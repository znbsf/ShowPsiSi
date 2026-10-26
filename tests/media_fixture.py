"""Locally generated, bounded real media for UI/source tests; external tool is optional."""
import os,subprocess
from pathlib import Path

def make_media(path,kind='video',silence=False):
 tool=Path(os.environ.get('SHOWPSISI_FFMPEG',''))
 if not tool.is_file():raise RuntimeError('External pinned SHOWPSISI_FFMPEG required')
 source='color=c=0x123456:s=64x48:r=25:d=0.2' if kind=='video' else 'anullsrc=r=48000:cl=mono:d=2' if silence else 'sine=frequency=440:sample_rate=48000:duration=0.25'
 codec=['-frames:v','5','-c:v','mpeg2video','-g','1','-pix_fmt','yuv420p'] if kind=='video' else ['-ac','1','-c:a','mp2','-b:a','128k']
 args=[str(tool),'-nostdin','-hide_banner','-loglevel','error','-threads','1','-filter_threads','1','-f','lavfi','-i',source,*codec,'-f','mpegts',str(path)]
 result=subprocess.run(args,capture_output=True,timeout=20,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
 if result.returncode:raise RuntimeError(result.stderr.decode('utf-8',errors='replace'))
 return path
