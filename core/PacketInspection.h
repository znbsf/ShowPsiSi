#pragma once
#include <algorithm>
#include <cstdint>
#include <string>
#include "nlohmann/json.hpp"
// Bounded original-packet inspection. Offsets refer to the normalized 188 bytes.
namespace packetinspect {
using J=nlohmann::json;
inline J decode(const uint8_t* b,bool psi){
 const unsigned afc=(b[3]>>4)&3;J out={{"header",{{"sync_byte",b[0]},{"transport_error_indicator",(b[1]>>7)&1},{"payload_unit_start_indicator",(b[1]>>6)&1},{"transport_priority",(b[1]>>5)&1},{"PID",((b[1]&31)<<8)|b[2]},{"transport_scrambling_control",b[3]>>6},{"adaptation_field_control",afc},{"continuity_counter",b[3]&15}}},{"regions",J::array({{{"offset",0},{"length",4},{"kind","header"}}})},{"issues",J::array()},{"payload_offset",nullptr}};
 if(b[0]!=0x47){out["issues"].push_back("Invalid sync byte; remaining header fields are uninterpreted bit values");return out;}
 if(afc==0){out["issues"].push_back("Reserved adaptation_field_control");return out;}
 size_t offset=4;
 if(afc&2){const size_t length=b[4];out["adaptation"]={{"length",length}};
  if(length>size_t((afc&1)?182:183)){out["issues"].push_back("Adaptation field overruns packet or leaves no payload");return out;}
  out["regions"].push_back({{"offset",4},{"length",length+1},{"kind","adaptation"}});offset+=length+1;
  if(length){const unsigned flags=b[5];out["adaptation"]["flags"]=flags;out["adaptation"]["discontinuity_indicator"]=(flags>>7)&1;out["adaptation"]["random_access_indicator"]=(flags>>6)&1;out["adaptation"]["PCR_flag"]=(flags>>4)&1;
   if(flags&0x10){if(length<7)out["issues"].push_back("Truncated PCR field");else{const uint64_t base=(uint64_t(b[6])<<25)|(uint64_t(b[7])<<17)|(uint64_t(b[8])<<9)|(uint64_t(b[9])<<1)|(b[10]>>7);const unsigned extension=((b[10]&1)<<8)|b[11];out["adaptation"]["pcr_base_90khz"]=base;out["adaptation"]["pcr_extension"]=extension;out["adaptation"]["pcr_27mhz"]=base*300+extension;if((b[10]&0x7e)!=0x7e||extension>=300)out["issues"].push_back("Invalid PCR reserved bits or extension");}}
  }
 }
 if(!(afc&1))return out;
 out["payload_offset"]=offset;
 if((b[1]&0x80)||(b[3]&0xc0)){out["regions"].push_back({{"offset",offset},{"length",188-offset},{"kind","payload"}});out["issues"].push_back("Payload semantic mapping unavailable for errored or scrambled packet");return out;}
 if((b[1]&0x40)&&offset<188){
  if(psi){out["pointer_field"]=b[offset];out["regions"].push_back({{"offset",offset},{"length",1},{"kind","pointer"}});if(size_t(b[offset])>187-offset)out["issues"].push_back("Pointer field overruns payload");++offset;}
  else if(offset+6<=188&&b[offset]==0&&b[offset+1]==0&&b[offset+2]==1){const auto stream=b[offset+3];const bool optional=stream!=0xbc&&stream!=0xbe&&stream!=0xbf&&stream!=0xf0&&stream!=0xf1&&stream!=0xff&&stream!=0xf2&&stream!=0xf8;size_t header=6;if(optional){if(offset+9>188)out["issues"].push_back("PES optional header continues in another packet");else{header=9+b[offset+8];if(offset+header>188)out["issues"].push_back("PES optional header continues in another packet");}}
   out["pes"]={{"stream_id",stream},{"packet_length",(b[offset+4]<<8)|b[offset+5]},{"header_bytes_in_packet",std::min(header,188-offset)}};out["regions"].push_back({{"offset",offset},{"length",std::min(header,188-offset)},{"kind","pes_header"}});offset+=std::min(header,188-offset);
  }
 }
 if(offset<188)out["regions"].push_back({{"offset",offset},{"length",188-offset},{"kind","payload"}});return out;
}
}
