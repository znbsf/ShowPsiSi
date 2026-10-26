#pragma once
#include <array>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <vector>
#include "nlohmann/json.hpp"
// Bounded scan-owner timing observations. No decoder, RF or conformance claims.
namespace transporttiming {
using J=nlohmann::json;
struct Clock {
 bool pcrKnown=false,ccKnown=false;unsigned cc=0,repeats=0;std::array<uint8_t,188> previous{};
 uint64_t pcr=0,index=0,first=0,last=0,samples=0,ticks=0,packets=0,wraps=0,jumps=0,discontinuities=0,invalid=0,continuity=0,duplicates=0;
};
class Timing {
 std::vector<Clock> clocks=std::vector<Clock>(8192);
 J retained=J::array();uint64_t count=0;
public:
 void clear(){std::fill(clocks.begin(),clocks.end(),Clock{});retained=J::array();count=0;}
 void boundary(){for(auto& c:clocks){c.pcrKnown=c.ccKnown=false;c.repeats=0;}}
 void observe(const uint8_t* b,uint64_t index){
  if(b[0]!=0x47){boundary();return;}
  const unsigned pid=((b[1]&31)<<8)|b[2],afc=(b[3]>>4)&3,cc=b[3]&15;auto& c=clocks[pid];
  const bool adaptation=(afc&2)!=0,payload=(afc&1)!=0;
  if(!afc||(adaptation&&b[4]>(payload?182:183))||(b[1]&0x80)||(b[3]&0xc0)){c.pcrKnown=c.ccKnown=false;return;}
  const bool discontinuity=adaptation&&b[4]&&(b[5]&0x80);if(discontinuity){++c.discontinuities;c.pcrKnown=c.ccKnown=false;}
  bool duplicatePacket=false;
  if(pid!=8191){
   if(c.ccKnown){if(payload&&cc==c.cc&&std::memcmp(c.previous.data(),b,188)==0){duplicatePacket=true;++c.duplicates;if(++c.repeats>1)++c.continuity;}else{const unsigned expected=(c.cc+(payload?1:0))&15;if(cc!=expected){++c.continuity;c.pcrKnown=false;}c.repeats=0;}}
   c.cc=cc;c.ccKnown=true;std::memcpy(c.previous.data(),b,188);
  }
  if(duplicatePacket||pid==8191)return;
  if(!adaptation||!b[4]||!(b[5]&0x10))return;
  if(b[4]<7||(b[10]&0x7e)!=0x7e){++c.invalid;c.pcrKnown=false;return;}
  const uint64_t base=(uint64_t(b[6])<<25)|(uint64_t(b[7])<<17)|(uint64_t(b[8])<<9)|(uint64_t(b[9])<<1)|(b[10]>>7);const unsigned extension=((b[10]&1)<<8)|b[11];if(extension>=300){++c.invalid;c.pcrKnown=false;return;}
  const uint64_t ticks=base*300+extension,modulus=(uint64_t(1)<<33)*300;J delta=nullptr;std::string status="first / new clock segment";
  if(c.pcrKnown){const uint64_t dt=(ticks+modulus-c.pcr)%modulus;if(dt>0&&dt<=270000000&&index>c.index){c.ticks+=dt;c.packets+=index-c.index;delta=dt;status=ticks<c.pcr?"wrap":"continuous";if(ticks<c.pcr)++c.wraps;}else{++c.jumps;status="jump / non-increasing clock; interval excluded";}}
  if(!c.samples)c.first=index;c.last=index;++c.samples;++count;
  if(retained.size()<4096)retained.push_back({{"pid",pid},{"packet_index",index},{"pcr_27mhz",ticks},{"pcr_base_90khz",base},{"pcr_extension",extension},{"delta_27mhz",delta},{"status",status},{"discontinuity_indicator",discontinuity}});
  c.pcr=ticks;c.index=index;c.pcrKnown=true;
 }
 J summary() const {
  unsigned primary=8192;uint64_t span=0,continuity=0,duplicates=0,invalid=0,discontinuities=0,jumps=0,wraps=0;
  for(unsigned pid=0;pid<clocks.size();++pid){const auto& c=clocks[pid];if(c.ticks&&c.packets>span){span=c.packets;primary=pid;}continuity+=c.continuity;duplicates+=c.duplicates;invalid+=c.invalid;discontinuities+=c.discontinuities;jumps+=c.jumps;wraps+=c.wraps;}
  J out={{"primary_pcr_pid",primary<8192?J(primary):J()},{"measured_bitrate_bps",nullptr},{"measured_duration_seconds",nullptr},{"pcr_samples",count},{"retained_samples",retained.size()},{"samples_truncated",count>retained.size()},{"continuity_error_packets",continuity},{"duplicate_payload_packets",duplicates},{"invalid_pcr_fields",invalid},{"pcr_discontinuities",discontinuities},{"pcr_jumps",jumps},{"pcr_wraps",wraps},{"measurement_scope","Captured-packet rate from consecutive PCR pairs in the same observed window and PID; intervals over 10 seconds, zero/reversed clocks, errors and declared discontinuities excluded"},{"duration_scope","Sum of trusted PCR intervals on the selected clock PID; gaps and discontinuities excluded, no extrapolation to file duration"},{"continuity_scope","Observed contiguous windows only; null PID excluded; identical payload packet may repeat once; not a complete transport conformance checker"}};
  if(primary<8192){const auto& c=clocks[primary];out["measured_bitrate_bps"]=double(c.packets)*1504.0*27000000.0/double(c.ticks);out["measured_duration_seconds"]=double(c.ticks)/27000000.0;out["clock_first_packet"]=c.first;out["clock_last_packet"]=c.last;out["trusted_packet_intervals"]=c.packets;}return out;
 }
 J page(size_t offset,size_t limit) const {J items=J::array();for(size_t i=offset;i<retained.size()&&items.size()<limit;++i)items.push_back(retained[i]);const auto next=offset+items.size();return {{"summary",summary()},{"items",items},{"offset",offset},{"total",retained.size()},{"next_offset",next<retained.size()?J(next):J()}};}
};
}
