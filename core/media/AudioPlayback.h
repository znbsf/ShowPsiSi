#pragma once
#ifdef _WIN32
#include <mmsystem.h>
#endif
namespace mediadecode {
class AudioPlayback {
#ifdef _WIN32
 struct State{HWAVEOUT device=nullptr;WAVEHDR header{};Bytes bytes;};std::unique_ptr<State> current;bool paused=false;
#endif
public:
 ~AudioPlayback(){
#ifdef _WIN32
  if(!stop())(void)current.release(); // Keep driver-owned storage alive until process teardown on a failed reset.
#endif
 }
 bool stop(){
#ifdef _WIN32
  if(current){if(waveOutReset(current->device)!=MMSYSERR_NOERROR)return false;MMRESULT code=waveOutUnprepareHeader(current->device,&current->header,sizeof(WAVEHDR));if(code!=MMSYSERR_NOERROR)return false;if(waveOutClose(current->device)!=MMSYSERR_NOERROR)return false;current.reset();}paused=false;
#endif
  return true;
 }
 bool playing(){
#ifdef _WIN32
  if(current&&(current->header.dwFlags&WHDR_DONE)){stop();return false;}return bool(current)&&!paused;
#else
  return false;
#endif
 }
 bool isPaused()const{
#ifdef _WIN32
  return bool(current)&&paused;
#else
  return false;
#endif
 }
 bool pause(bool value){
#ifdef _WIN32
  if(!current)return false;const auto code=value?waveOutPause(current->device):waveOutRestart(current->device);if(code!=MMSYSERR_NOERROR)return false;paused=value;return true;
#else
  return false;
#endif
 }
 void play(const Bytes& pcm){
#ifdef _WIN32
  if(!stop())throw std::runtime_error("Previous audio device buffer could not stop");if(pcm.empty()||pcm.size()%2)throw std::runtime_error("No complete signed-16-bit PCM samples");auto next=std::make_unique<State>();next->bytes=pcm;WAVEFORMATEX format{};format.wFormatTag=WAVE_FORMAT_PCM;format.nChannels=1;format.nSamplesPerSec=48000;format.wBitsPerSample=16;format.nBlockAlign=2;format.nAvgBytesPerSec=96000;MMRESULT code=waveOutOpen(&next->device,WAVE_MAPPER,&format,0,0,CALLBACK_NULL);if(code!=MMSYSERR_NOERROR)throw std::runtime_error("Audio output unavailable (Windows multimedia error "+std::to_string(code)+")");next->header.lpData=reinterpret_cast<LPSTR>(next->bytes.data());next->header.dwBufferLength=DWORD(next->bytes.size());code=waveOutPrepareHeader(next->device,&next->header,sizeof(WAVEHDR));if(code!=MMSYSERR_NOERROR){waveOutClose(next->device);throw std::runtime_error("Cannot prepare decoded PCM output");}code=waveOutWrite(next->device,&next->header,sizeof(WAVEHDR));if(code!=MMSYSERR_NOERROR){waveOutUnprepareHeader(next->device,&next->header,sizeof(WAVEHDR));waveOutClose(next->device);throw std::runtime_error("Cannot queue decoded PCM output");}current=std::move(next);paused=false;
#else
  throw std::runtime_error("PCM device output is currently implemented for Windows only");
#endif
 }
};
}
