#include "pes_engine.h"
#include <algorithm>
#include <utility>
namespace mediawire {
namespace {
const std::size_t kMaxPes = 16u * 1024u * 1024u;
bool special(uint8_t id) {
    return id == 0xbc || id == 0xbe || id == 0xbf || id == 0xf0 ||
           id == 0xf1 || id == 0xff || id == 0xf2 || id == 0xf8;
}
bool timestamp(const uint8_t* p, uint8_t prefix, uint64_t& value) {
    if ((p[0] >> 4) != prefix || !(p[0]&1) || !(p[2]&1) || !(p[4]&1)) return false;
    value = (uint64_t((p[0] >> 1)&7) << 30) | (uint64_t(p[1]) << 22) |
            (uint64_t(p[2] >> 1) << 15) | (uint64_t(p[3]) << 7) | (p[4] >> 1);
    return true;
}
}
bool parse_pes(uint16_t pid, const uint8_t* b, std::size_t n,
               PesPacket& result, std::string& error) {
    error.clear();
    const auto bad = [&](const char* s) { error = s; return false; };
    if (!b || n < 6) return bad("PES header truncated");
    if (pid > 0x1ffe) return bad("invalid PES PID");
    if (b[0] || b[1] || b[2] != 1) return bad("invalid PES start code prefix");
    if (b[3] < 0xbc) return bad("start code is not a PES stream_id");
    PesPacket p;
    p.pid = pid; p.stream_id = b[3]; p.packet_length = uint16_t((b[4]<<8)|b[5]);
    if (p.packet_length ? n != std::size_t(p.packet_length)+6 : (b[3]<0xe0 || b[3]>0xef))
        return bad("invalid PES declared length");
    if (n > kMaxPes) return bad("PES exceeds 16 MiB limit");
    p.payload_offset = 6;
    if (!special(b[3])) {
        if (n < 9) return bad("PES optional header truncated");
        if ((b[6]&0xc0) != 0x80) return bad("unsupported MPEG-1 or invalid PES header");
        p.has_optional_header = true;
        p.scrambling_control = (b[6] >> 4)&3;
        p.payload_offset = 9u + b[8];
        if (p.payload_offset > n) return bad("PES header data length exceeds packet");
        const uint8_t flags = b[7] >> 6;
        if (flags == 1) return bad("reserved PTS_DTS flags");
        std::size_t pos = 9;
        if (flags & 2) {
            if (pos+5 > p.payload_offset || !timestamp(b+pos, flags==3 ? 3 : 2, p.pts))
                return bad("invalid PTS prefix, markers or length");
            p.has_pts = true; pos += 5;
        }
        if (flags == 3) {
            if (pos+5 > p.payload_offset || !timestamp(b+pos, 1, p.dts))
                return bad("invalid DTS prefix, markers or length");
            p.has_dts = true; pos += 5;
        }
        // The original nxteletext fun_1460 uses the same flags and final
        // 9 + header_data_length payload boundary. Guard its optional spans.
        const unsigned widths[] = {6,3,1,1,2};
        for (unsigned i=0; i<5; ++i) if (b[7] & (0x20 >> i)) {
            if (pos + widths[i] > p.payload_offset) return bad("PES optional field truncated");
            if (i == 0 && ((b[pos]&0xc0) || !(b[pos]&4) || !(b[pos+2]&4) || !(b[pos+4]&4) || !(b[pos+5]&1)))
                return bad("invalid ESCR reserved bits or markers");
            if (i == 1 && (!(b[pos]&0x80) || !(b[pos+2]&1))) return bad("invalid ES_rate markers");
            if (i == 3 && !(b[pos]&0x80)) return bad("invalid additional_copy_info marker");
            pos += widths[i];
        }
        if (b[7]&1) {
            if (pos >= p.payload_offset) return bad("PES extension truncated");
            uint8_t f=b[pos++];
            if (f&0x80) pos+=16;
            if (pos > p.payload_offset) return bad("PES private data truncated");
            if (f&0x40) {
                if (pos >= p.payload_offset) return bad("PES pack header truncated");
                unsigned length=b[pos++]; pos+=length;
            }
            if (f&0x20) {
                if (pos+2 > p.payload_offset) return bad("PES sequence counter truncated");
                if (!(b[pos]&0x80) || !(b[pos+1]&0x80)) return bad("invalid PES sequence counter markers");
                pos+=2;
            }
            if (f&0x10) {
                if (pos+2 > p.payload_offset) return bad("PES P-STD buffer truncated");
                if ((b[pos]&0xc0)!=0x40) return bad("invalid PES P-STD prefix");
                pos+=2;
            }
            if (pos > p.payload_offset) return bad("PES extension field truncated");
            if (f&1) {
                if (pos >= p.payload_offset || !(b[pos]&0x80)) return bad("invalid PES extension 2");
                unsigned length=b[pos++]&0x7f; pos+=length;
                if (pos > p.payload_offset) return bad("PES extension 2 truncated");
            }
        }
        for (; pos < p.payload_offset; ++pos)
            if (b[pos]!=0xff) return bad("invalid PES header stuffing byte");
    }
    p.raw.assign(b,b+n); result = std::move(p); return true;
}
PesEngine::PesEngine(uint16_t pid) : pid_(pid) {
    if (pid > 0x1ffe) error_ = "invalid PES PID";
}
bool PesEngine::fail(const std::string& s) { if (error_.empty()) error_=s; return false; }
void PesEngine::discard() { if (!pending_.empty()) ++stats_.incomplete_pes; pending_.clear(); fragments_.clear(); }
bool PesEngine::deliver() {
    PesPacket p; std::string e;
    if (!parse_pes(pid_,pending_.data(),pending_.size(),p,e)) return fail(e);
    p.fragments=fragments_;
    if (observer_ && !observer_(p,start_,end_)) return fail("PES observer rejected packet");
    ++stats_.delivered_pes; pending_.clear(); fragments_.clear(); return true;
}
bool PesEngine::feed_packet(const uint8_t* p, std::size_t n) {
    return feed_packet(p,n,stats_.packets);
}
bool PesEngine::feed_packet(const uint8_t* p, std::size_t n, uint64_t index) {
    if (!error_.empty()) return false;
    if (finished_) return fail("PES feed after finish");
    ++stats_.packets;
    if (!p || n!=188 || p[0]!=0x47) return fail("invalid TS packet size or sync");
    unsigned afc=(p[3]>>4)&3;
    if (!afc) return fail("reserved TS adaptation field control");
    std::size_t pos=4; bool dis=false;
    if (afc&2) {
        unsigned len=p[4];
        if (len>183 || (afc==2 && len!=183) || (afc==3 && len>182)) return fail("invalid TS adaptation field length");
        if (len) dis=(p[5]&0x80)!=0;
        pos=5u+len;
    }
    if ((((p[1]&0x1f)<<8)|p[2])!=pid_) return true;
    ++stats_.selected_packets;
    if (p[1]&0x80) return fail("selected TS packet has transport error");
    if (p[3]&0xc0) return fail("selected TS packet is scrambled");
    // A duplicate carrying discontinuity is still the same transmitted payload.
    // Detect it before resetting the remembered continuity state.
    if ((afc&1) && have_cc_ && (p[3]&15)==cc_ && last_packet_.size()==188 &&
        std::equal(last_packet_.begin(),last_packet_.end(),p)) {
        if(++duplicate_count_>1)return fail("More than one consecutive duplicate TS payload");
        ++stats_.duplicate_packets; return true;
    }
    if (dis) { if(discontinuity_observer_)discontinuity_observer_();++stats_.discontinuities; discard(); have_cc_=false; last_packet_.clear(); }
    if (!(afc&1)) return true;
    const uint8_t cc=p[3]&15;
    if (have_cc_ && cc==cc_) {
        if (last_packet_.size()==188 && std::equal(last_packet_.begin(),last_packet_.end(),p)) {
            ++stats_.duplicate_packets; return true;
        }
        return fail("conflicting TS packets with same continuity counter");
    }
    if (have_cc_ && cc!=((cc_+1)&15)) { if(discontinuity_observer_)discontinuity_observer_();++stats_.discontinuities; discard(); }
    duplicate_count_=0;cc_=cc; have_cc_=true; last_packet_.assign(p,p+188);
    bool start=(p[1]&0x40)!=0;
    if (start) {
        if (!pending_.empty()) {
            if (pending_.size()>=6 && pending_[4]==0 && pending_[5]==0) { if (!deliver()) return false; }
            else discard();
        }
        start_=index;
        // PES begins directly at the TS payload boundary. PSI pointer fields do
        // not apply to PES; never guess past bytes to locate a start code.
        // The fixed start code/header may straddle TS packets; the first six
        // collected bytes are validated below without skipping any payload.
    } else if (pending_.empty()) return true;
    end_=index;
    // First collect only the fixed header, which can straddle TS packets.
    while (pos<188) {
        std::size_t target=6;
        if (pending_.size()>=6) {
            if (pending_[0] || pending_[1] || pending_[2]!=1) return fail("invalid PES start code prefix");
            unsigned length=(pending_[4]<<8)|pending_[5];
            if (!length && (pending_[3]<0xe0 || pending_[3]>0xef)) return fail("zero length PES requires video stream_id");
            target=length ? 6u+length : kMaxPes;
        }
        std::size_t count=std::min(188-pos,target-pending_.size());
        if(count){if(!fragments_.empty()&&fragments_.back().packet_index==index&&fragments_.back().packet_offset+fragments_.back().length==pos)fragments_.back().length+=count;else fragments_.push_back({index,pos,pending_.size(),count});}
        pending_.insert(pending_.end(),p+pos,p+pos+count); pos+=count;
        if (pending_.size()==6) {
            if (pending_[0] || pending_[1] || pending_[2]!=1) return fail("invalid PES start code prefix");
            if (pending_[4]==0 && pending_[5]==0 && (pending_[3]<0xe0 || pending_[3]>0xef)) return fail("zero length PES requires video stream_id");
            continue;
        }
        if (pending_.size()==target) {
            if (target==kMaxPes) {
                if (pos<188) return fail("PES exceeds 16 MiB limit");
                break;
            }
            // Validate the whole contributing TS payload before emitting an event.
            // Remaining bytes are padding, never part of the bounded PES.
            for (;pos<188;++pos) if (p[pos]!=0xff) return fail("non-stuffing data after bounded PES");
            if (!deliver()) return false;
            break;
        }
    }
    return true;
}
bool PesEngine::finish() {
    if (!error_.empty()) return false;
    if (finished_) return true;
    finished_=true;
    if (!pending_.empty()) {
        if (pending_.size()>=6 && pending_[4]==0 && pending_[5]==0) return deliver();
        discard();
    }
    return true;
}
}





namespace mediawire {
const char* pes_stream_id_name(unsigned stream_id) {
    if (stream_id == 0xbc) return "program_stream_map";
    if (stream_id == 0xbd) return "private_stream_1";
    if (stream_id == 0xbe) return "padding_stream";
    if (stream_id == 0xbf) return "private_stream_2";
    if (stream_id >= 0xc0 && stream_id <= 0xdf) return "audio";
    if (stream_id >= 0xe0 && stream_id <= 0xef) return "video";
    if (stream_id >= 0xf0 && stream_id <= 0xff) return "DSM-CC/ECM/EMM";
    return "other";
}
}  // namespace mediawire
