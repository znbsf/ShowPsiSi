// dsmcc_dsi.cpp - independent wire parser for DSM-CC DSI (0x1006).
#include "DsiMessage.h"
#include <utility>
namespace biopwire {
namespace {
uint16_t dsi_be16(const uint8_t* p) {
    return uint16_t((uint16_t(p[0]) << 8) | p[1]);
}
uint32_t dsi_be32(const uint8_t* p) {
    return (uint32_t(p[0]) << 24) | (uint32_t(p[1]) << 16) |
           (uint32_t(p[2]) << 8) | p[3];
}
bool dsi_fail(std::string& error, const char* why) {
    error = why;
    return false;
}
std::string dsi_hex(const std::vector<uint8_t>& bytes) {
    static const char digits[] = "0123456789abcdef";
    std::string out;
    out.reserve(bytes.size() * 2);
    for (std::size_t i = 0; i < bytes.size(); ++i) {
        out += digits[bytes[i] >> 4];
        out += digits[bytes[i] & 15];
    }
    return out;
}
}  // namespace

bool decode_dsi_message(const uint8_t* bytes, std::size_t size,
                        DsiMessage& output, std::string& error) {
    error.clear();
    if (!bytes || size < 32) return dsi_fail(error, "truncated DSM-CC DSI message");
    DsiMessage message;
    DsiHeader& header = message.header;
    header.protocol_discriminator = bytes[0];
    header.dsmcc_type = bytes[1];
    header.message_id = dsi_be16(bytes + 2);
    header.transaction_id = dsi_be32(bytes + 4);
    header.reserved = bytes[8];
    header.adaptation_length = bytes[9];
    header.message_length = dsi_be16(bytes + 10);
    if (header.protocol_discriminator != 0x11 || header.dsmcc_type != 3 ||
        header.message_id != 0x1006 || header.reserved != 0xff)
        return dsi_fail(error, "unsupported DSM-CC DSI header");
    if (header.message_length != size - 12)
        return dsi_fail(error, "DSM-CC DSI declared message length mismatch");
    if (header.adaptation_length > header.message_length)
        return dsi_fail(error, "DSM-CC DSI adaptation exceeds message");
    const std::size_t body = 12u + header.adaptation_length;
    header.adaptation.assign(bytes + 12, bytes + body);
    std::size_t pos = body;
    if (size - pos < 20) return dsi_fail(error, "truncated DSI serverId");
    message.server_id.assign(bytes + pos, bytes + pos + 20);
    pos += 20;
    if (size - pos < 2) return dsi_fail(error, "truncated DSI compatibility descriptor length");
    message.compatibility_descriptor_length = dsi_be16(bytes + pos);
    pos += 2;
    if (message.compatibility_descriptor_length > size - pos)
        return dsi_fail(error, "DSI compatibility descriptor exceeds message");
    message.compatibility_descriptor.assign(bytes + pos, bytes + pos + message.compatibility_descriptor_length);
    pos += message.compatibility_descriptor_length;
    if (size - pos < 2) return dsi_fail(error, "truncated DSI privateDataLength");
    message.private_data_length = dsi_be16(bytes + pos);
    pos += 2;
    if (message.private_data_length > size - pos)
        return dsi_fail(error, "DSI privateData exceeds message");
    message.private_data.assign(bytes + pos, bytes + pos + message.private_data_length);
    const std::size_t private_end = pos + message.private_data_length;
    if (private_end != size) return dsi_fail(error, "DSI trailing bytes after privateData");

    // ServiceGatewayInfo, including its IOR and optional trailing fields, is
    // contained in privateData. Never look for it beyond that declared region.
    if (pos == private_end) {
        message.raw.assign(bytes, bytes + size);
        output = std::move(message);
        return true;
    }

    if (private_end - pos < 4) return dsi_fail(error, "truncated DSI IOR type id length");
    // Keep the public ior_type_id name for the wire type_id_length word.
    // The following type-id bytes (e.g. "srg\0") precede profile_count.
    message.ior_type_id = dsi_be32(bytes + pos);
    pos += 4;
    if (message.ior_type_id > private_end - pos)
        return dsi_fail(error, "DSI IOR type id exceeds privateData");
    pos += message.ior_type_id;
    if (private_end - pos < 4) return dsi_fail(error, "truncated DSI IOR profile count");
    const uint32_t profile_count = dsi_be32(bytes + pos);
    pos += 4;
    if (profile_count > (private_end - pos) / 8)
        return dsi_fail(error, "DSI IOR profile count exceeds privateData");
    for (uint32_t i = 0; i < profile_count; ++i) {
        if (private_end - pos < 8) return dsi_fail(error, "truncated DSI IOR profile header");
        DsiProfile profile;
        profile.profile_id = dsi_be32(bytes + pos);
        const uint32_t length = dsi_be32(bytes + pos + 4);
        pos += 8;
        if (length > private_end - pos) return dsi_fail(error, "DSI IOR profile data exceeds privateData");
        profile.data.assign(bytes + pos, bytes + pos + length);
        pos += length;
        message.profiles.push_back(std::move(profile));
    }
    // An IOR-only privateData has no optional taps/contexts/userInfo trailer.
    if (pos == private_end) {
        message.raw.assign(bytes, bytes + size);
        output = std::move(message);
        return true;
    }
    const uint8_t tap_count = bytes[pos++];
    for (unsigned i = 0; i < tap_count; ++i) {
        if (private_end - pos < 7) return dsi_fail(error, "truncated DSI download tap header");
        DsiTap tap;
        tap.id = dsi_be16(bytes + pos);
        tap.use = dsi_be16(bytes + pos + 2);
        tap.association_tag = dsi_be16(bytes + pos + 4);
        const uint8_t selector_length = bytes[pos + 6];
        pos += 7;
        if (selector_length > private_end - pos) return dsi_fail(error, "DSI download tap selector exceeds privateData");
        tap.selector.assign(bytes + pos, bytes + pos + selector_length);
        pos += selector_length;
        message.taps.push_back(std::move(tap));
    }
    if (private_end - pos < 1) return dsi_fail(error, "truncated DSI serviceContextList count");
    const uint8_t context_count = bytes[pos++];
    for (unsigned i = 0; i < context_count; ++i) {
        if (private_end - pos < 6) return dsi_fail(error, "truncated DSI service context header");
        DsiContext context;
        context.context_id = dsi_be32(bytes + pos);
        const uint16_t length = dsi_be16(bytes + pos + 4);
        pos += 6;
        if (length > private_end - pos) return dsi_fail(error, "DSI service context data exceeds privateData");
        context.data.assign(bytes + pos, bytes + pos + length);
        pos += length;
        message.service_contexts.push_back(std::move(context));
    }
    if (private_end - pos < 2) return dsi_fail(error, "truncated DSI userInfoLength");
    message.user_info_length = dsi_be16(bytes + pos);
    pos += 2;
    if (message.user_info_length > private_end - pos)
        return dsi_fail(error, "DSI userInfo exceeds privateData");
    message.user_info.assign(bytes + pos, bytes + pos + message.user_info_length);
    pos += message.user_info_length;
    if (pos != private_end) return dsi_fail(error, "DSI trailing bytes after userInfo");
    message.raw.assign(bytes, bytes + size);
    output = std::move(message);
    return true;
}

} // namespace biopwire
