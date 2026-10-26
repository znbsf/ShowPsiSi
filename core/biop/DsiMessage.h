#ifndef SHOWPSISI_DSMCC_DSI_H
#define SHOWPSISI_DSMCC_DSI_H
#include <cstddef>
#include <cstdint>
#include <iosfwd>
#include <string>
#include <vector>
namespace biopwire {
struct DsiHeader {
    uint8_t protocol_discriminator = 0, dsmcc_type = 0, reserved = 0, adaptation_length = 0;
    uint16_t message_id = 0, message_length = 0;
    uint32_t transaction_id = 0;
    std::vector<uint8_t> adaptation;
};
struct DsiProfile {
    uint32_t profile_id = 0;
    std::vector<uint8_t> data;
};
struct DsiTap {
    uint16_t id = 0, use = 0, association_tag = 0;
    std::vector<uint8_t> selector;
};
struct DsiContext {
    uint32_t context_id = 0;
    std::vector<uint8_t> data;
};
struct DsiMessage {
    DsiHeader header;
    std::vector<uint8_t> server_id;
    uint16_t compatibility_descriptor_length = 0;
    std::vector<uint8_t> compatibility_descriptor;
    uint16_t private_data_length = 0;
    std::vector<uint8_t> private_data;
    uint32_t ior_type_id = 0;  // wire type_id_length; legacy API/JSON name
    std::vector<DsiProfile> profiles;
    std::vector<DsiTap> taps;
    std::vector<DsiContext> service_contexts;
    uint16_t user_info_length = 0;
    std::vector<uint8_t> user_info;
    std::vector<uint8_t> raw;
};
// Parses a complete DSM-CC DownloadServerInitiate message (0x1006) including
// the common header and its declared length. Nonempty privateData contains an
// IOR (type-id length/bytes, profiles) and an optional taps/contexts/userInfo
// trailer, all bounded by privateDataLength. Independent wire model; no
// carousel lifecycle or BIOP profile-body decoding is claimed.
bool decode_dsi_message(const uint8_t* bytes, std::size_t size,
                        DsiMessage& output, std::string& error);
}
#endif
