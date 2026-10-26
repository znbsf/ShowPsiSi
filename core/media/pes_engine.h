#ifndef SHOWPSISI_PES_ENGINE_H
#define SHOWPSISI_PES_ENGINE_H
#include <cstddef>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>
namespace mediawire {
struct PesFragment {uint64_t packet_index=0;std::size_t packet_offset=0,pes_offset=0,length=0;};
struct PesPacket {
    uint16_t pid = 0;
    uint8_t stream_id = 0;
    uint16_t packet_length = 0;
    std::vector<uint8_t> raw;
    std::vector<PesFragment> fragments;
    std::size_t payload_offset = 0;
    bool has_optional_header = false, has_pts = false, has_dts = false;
    uint64_t pts = 0, dts = 0;
    uint8_t scrambling_control = 0;
};
const char* pes_stream_id_name(unsigned stream_id);
bool parse_pes(uint16_t pid, const uint8_t* data, std::size_t size,
               PesPacket& result, std::string& error);
struct PesStats {
    uint64_t packets = 0, selected_packets = 0, delivered_pes = 0;
    uint64_t duplicate_packets = 0, incomplete_pes = 0, discontinuities = 0;
};
class PesEngine {
public:
    typedef std::function<bool(const PesPacket&, uint64_t, uint64_t)> Observer;
    explicit PesEngine(uint16_t pid);
    void set_observer(Observer observer) { observer_ = observer; }
    bool feed_packet(const uint8_t* packet, std::size_t size);
    bool feed_packet(const uint8_t* packet, std::size_t size, uint64_t packet_index);
    bool finish();
    void abandon(){discard();}
    void set_discontinuity_observer(std::function<void()> observer){discontinuity_observer_=observer;}
    const std::string& error() const { return error_; }
    const PesStats& stats() const { return stats_; }
private:
    bool fail(const std::string& message);
    void discard();
    bool deliver();
    uint16_t pid_;
    PesStats stats_;
    Observer observer_;
    std::function<void()> discontinuity_observer_;
    std::string error_;
    std::vector<uint8_t> pending_, last_packet_;
    std::vector<PesFragment> fragments_;
    unsigned duplicate_count_=0;
    bool have_cc_ = false, finished_ = false;
    uint8_t cc_ = 0;
    uint64_t start_ = 0, end_ = 0;
};
}
#endif
