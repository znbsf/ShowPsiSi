#pragma once
#include <algorithm>
#include <cstdint>
#include <numeric>
#include <vector>
#include "nlohmann/json.hpp"

// Scan-owner-only counters. Never retain a per-packet allocation or infer clocks.
namespace transportstats {
using J=nlohmann::json;
struct Pid {
    uint64_t packets=0,payload=0,adaptation=0,tei=0,scrambled=0,malformed=0;
    uint64_t first=0,last=0;
};
class Statistics {
    std::vector<Pid> pids=std::vector<Pid>(8192);
    uint64_t observed=0,badSync=0,errorPackets=0,tei=0,scrambled=0,malformed=0;
    size_t distinct=0;
public:
    void clear(){std::fill(pids.begin(),pids.end(),Pid{});observed=badSync=errorPackets=tei=scrambled=malformed=0;distinct=0;}
    void observe(const uint8_t* b,uint64_t index){
        ++observed;
        if(b[0]!=0x47){++badSync;++errorPackets;return;}
        const auto pid=unsigned((b[1]&0x1f)<<8)|b[2];
        auto& row=pids[pid];
        if(!row.packets++){++distinct;row.first=index;}row.last=index;
        const auto afc=(b[3]>>4)&3;
        const bool hasPayload=(afc&1)!=0,hasAdaptation=(afc&2)!=0;
        const bool bad=afc==0||(hasAdaptation&&b[4]>(hasPayload?182:183));
        row.payload+=hasPayload;row.adaptation+=hasAdaptation;
        row.tei+=(b[1]&0x80)!=0;row.scrambled+=(b[3]&0xc0)!=0;row.malformed+=bad;
        tei+=(b[1]&0x80)!=0;scrambled+=(b[3]&0xc0)!=0;malformed+=bad;
        errorPackets+=bad||(b[1]&0x80)!=0;
    }
    J summary(double bitrate) const {
        return {{"scope","all observed scan windows; not the selected historical cutoff"},
            {"observed_packets",observed},{"pid_count",distinct},{"bad_sync_packets",badSync},
            {"tei_packets",tei},{"scrambled_packets",scrambled},{"malformed_header_packets",malformed},
            {"error_packets",errorPackets},
            {"header_checks",J::array({"sync byte","TEI flag","reserved adaptation_field_control","adaptation length overrun"})},
            {"error_scope","Unique packets with sync, TEI or malformed adaptation/header errors. Excludes continuity, section CRC, PES, decoder and semantic errors."},
            {"rate_basis",bitrate>0?"user supplied normalized 188-byte TS bitrate":"unavailable; no measured PCR clock"},
            {"configured_bitrate_bps",bitrate>0?J(bitrate):J()},
            {"observed_duration_seconds",bitrate>0?J(double(observed)*1504.0/bitrate):J()},
            {"duration_scope","Sum of observed packet windows from supplied bitrate; not elapsed time across gaps"},
            {"pcr_derived",false}};
    }
    J page(size_t offset,size_t limit,bool errorsOnly,const std::string& sort,bool descending,double bitrate) const {
        std::vector<unsigned> order;
        for(unsigned i=0;i<pids.size();++i)if(pids[i].packets&&(!errorsOnly||pids[i].tei||pids[i].malformed))order.push_back(i);
        std::sort(order.begin(),order.end(),[&](unsigned a,unsigned b){
            if(sort=="packets"&&pids[a].packets!=pids[b].packets)return descending?pids[a].packets>pids[b].packets:pids[a].packets<pids[b].packets;
            return descending&&sort=="pid"?a>b:a<b;
        });
        J items=J::array();
        for(size_t i=offset;i<order.size()&&items.size()<limit;++i){
            auto id=order[i];const auto& p=pids[id];
            const double fraction=observed?double(p.packets)/double(observed):0;
            items.push_back({{"pid",id},{"packets",p.packets},{"packet_fraction",fraction},
                {"payload_packets",p.payload},{"adaptation_packets",p.adaptation},{"tei_packets",p.tei},
                {"scrambled_packets",p.scrambled},{"malformed_header_packets",p.malformed},
                {"first_packet",p.first},{"last_packet",p.last},
                {"bitrate_bps",bitrate>0?J(fraction*bitrate):J()},
                {"packets_per_second",bitrate>0?J(fraction*bitrate/1504.0):J()}});
        }
        const auto next=offset+items.size();
        return {{"items",items},{"total",order.size()},{"offset",offset},{"next_offset",next<order.size()?J(next):J()},
            {"sort",sort},{"descending",descending},{"errors_only",errorsOnly},{"summary",summary(bitrate)}};
    }
};
} // namespace transportstats
