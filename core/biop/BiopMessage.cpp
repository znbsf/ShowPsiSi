// biop_message.cpp - generic BIOP message envelope + Directory bindings.
#include "BiopMessage.h"
#include <utility>
#include <set>
namespace biopwire {
namespace {
uint16_t bm_be16(const uint8_t* p) {
    return uint16_t((uint16_t(p[0]) << 8) | p[1]);
}
uint32_t bm_be32(const uint8_t* p) {
    return (uint32_t(p[0]) << 24) | (uint32_t(p[1]) << 16) |
           (uint32_t(p[2]) << 8) | p[3];
}
bool bm_fail(std::string& error, const char* why) {
    error = why;
    return false;
}
std::string bm_hex(const std::vector<uint8_t>& bytes) {
    static const char digits[] = "0123456789abcdef";
    std::string out;
    out.reserve(bytes.size() * 2);
    for (std::size_t i = 0; i < bytes.size(); ++i) {
        out += digits[bytes[i] >> 4];
        out += digits[bytes[i] & 15];
    }
    return out;
}
bool parse_profile_body(BiopIorProfile& profile) {
    const std::vector<uint8_t>& data=profile.data;
    if(data.empty()) return false;
    const uint8_t key_length=data[0];
    if(1u+key_length+4+2>data.size()) return false;
    std::size_t pos=1;
    profile.object_key.assign(data.begin()+pos,data.begin()+pos+key_length);
    pos+=key_length;
    profile.object_kind=bm_be32(data.data()+pos);
    pos+=4;
    profile.object_info_length=bm_be16(data.data()+pos);
    pos+=2;
    if(profile.object_info_length>data.size()-pos) return false;
    profile.object_info.assign(data.begin()+pos,data.begin()+pos+profile.object_info_length);
    profile.body_parsed=true;
    return true;
}
bool parse_isop_location(BiopIorProfile& profile) {
    const std::vector<uint8_t>& d = profile.data;
    if (d.size() < 17 || d[2] != 'I' || d[3] != 'S' || d[4] != 'O' || d[5] != 'P')
        return false;
    // ISO ObjectLocation carries BIOP major/minor, not the DII moduleVersion.
    // Older lab fixtures used a zero-length component with a module version.
    const bool legacy = d[1] == 0 && d[6] == 0;
    const uint16_t name_length = legacy ? bm_be16(d.data()+14) : d[15];
    if (16u + name_length > d.size()) return false;
    if (!legacy && (d[0] != 0 || d[6] < 9u + name_length || d[14] != 0)) return false;
    profile.location_parsed = true;
    profile.carousel_id = bm_be32(d.data() + 7);
    profile.module_id = bm_be16(d.data() + 11);
    profile.legacy_module_version = legacy;
    if (legacy) profile.module_version = d[13];
    else { profile.biop_version_major = d[13]; profile.biop_version_minor = d[14]; }
    profile.object_name.assign(d.begin() + 16, d.begin() + 16 + name_length);
    profile.object_key.assign(d.begin() + 16, d.begin() + 16 + name_length);
    while (!profile.object_name.empty() && profile.object_name.back() == '\0')
        profile.object_name.pop_back();
    return true;
}

bool parse_ior(const uint8_t* p, std::size_t size, std::size_t& pos,
               BiopIor& ior, std::string& error) {
    if (size - pos < 8) return bm_fail(error, "truncated BIOP IOR header");
    const std::size_t ior_start = pos;
    ior.type_id = bm_be32(p + pos);
    uint32_t count = bm_be32(p + pos + 4);
    pos += 8;
    if (count > (size - pos) / 8) {
        // Some 2005 carousel encoders put a 4-byte object-kind FourCC
        // ("dir\0", "fil\0", ...) where the standard profileCount sits.
        if(size-ior_start<12)return bm_fail(error,"truncated BIOP alternate IOR header");
        const std::size_t kind_pos = ior_start + 4;
        const std::size_t alt = ior_start + 12;
        const uint32_t alt_count = bm_be32(p + ior_start + 8);
        const bool fourcc = alt <= size && p[kind_pos] && p[kind_pos + 1] &&
                            p[kind_pos + 2] && p[kind_pos + 3] == 0 &&
                            p[kind_pos] >= 0x20 && p[kind_pos] <= 0x7e &&
                            p[kind_pos + 1] >= 0x20 && p[kind_pos + 1] <= 0x7e &&
                            p[kind_pos + 2] >= 0x20 && p[kind_pos + 2] <= 0x7e;
        if (!fourcc || alt_count > (size - alt) / 8)
            return bm_fail(error, "BIOP IOR profile count exceeds message");
        count = alt_count;
        pos = alt;
    }
    for (uint32_t i = 0; i < count; ++i) {
        if (size - pos < 8) return bm_fail(error, "truncated BIOP IOR profile header");
        BiopIorProfile profile;
        profile.profile_id = bm_be32(p + pos);
        const uint32_t length = bm_be32(p + pos + 4);
        pos += 8;
        if (length > size - pos) return bm_fail(error, "BIOP IOR profile data exceeds message");
        profile.data.assign(p + pos, p + pos + length);
        pos += length;
        parse_profile_body(profile);
        parse_isop_location(profile);
        ior.profiles.push_back(std::move(profile));
    }
    return true;
}
bool parse_stream_info(const std::vector<uint8_t>& info,
                       BiopStreamInfo& stream,
                       std::string& error) {
    if (info.size() < 1) return bm_fail(error, "truncated BIOP StreamInfo description length");
    const uint8_t description_length = info[0];
    if (std::size_t(1) + description_length + 10 > info.size())
        return bm_fail(error, "BIOP StreamInfo description exceeds objectInfo");
    stream.description.assign(info.begin() + 1, info.begin() + 1 + description_length);
    std::size_t pos = 1 + description_length;
    stream.duration_seconds = bm_be32(info.data() + pos);
    stream.duration_microseconds = bm_be32(info.data() + pos + 4);
    stream.audio = info[pos + 8];
    stream.video = info[pos + 9];
    pos += 10;
    if (pos != info.size()) return bm_fail(error, "BIOP StreamInfo trailing bytes");
    return true;
}

bool parse_stream_event(const std::vector<uint8_t>& body,
                        BiopStreamEvent& event,
                        std::string& error) {
    if (body.size() < 2) return bm_fail(error, "truncated BIOP StreamEvent names count");
    std::size_t pos = 0;
    const uint16_t name_count = bm_be16(body.data());
    pos += 2;
    for (unsigned i = 0; i < name_count; ++i) {
        if (pos >= body.size()) return bm_fail(error, "truncated BIOP StreamEvent name length");
        const uint8_t length = body[pos++];
        if (length > body.size() - pos) return bm_fail(error, "BIOP StreamEvent name exceeds body");
        event.event_names.push_back(std::vector<uint8_t>(body.begin() + pos, body.begin() + pos + length));
        pos += length;
    }
    if (body.size() - pos < 2) return bm_fail(error, "truncated BIOP StreamEvent ids count");
    const uint16_t id_count = bm_be16(body.data() + pos);
    pos += 2;
    if (id_count > (body.size() - pos) / 4)
        return bm_fail(error, "BIOP StreamEvent ids count exceeds body");
    for (unsigned i = 0; i < id_count; ++i) {
        event.event_ids.push_back(bm_be32(body.data() + pos));
        pos += 4;
    }
    if (pos != body.size()) return bm_fail(error, "BIOP StreamEvent trailing bytes");
    return true;
}

bool parse_bindings(const std::vector<uint8_t>& body,
                    std::vector<BiopBinding>& bindings, std::string& error) {    if (body.size() < 2) return bm_fail(error, "truncated BIOP directory bindings count");
    const uint16_t count = bm_be16(body.data());
    std::size_t pos = 2;
    if (count > (body.size() - pos) / 5)
        return bm_fail(error, "BIOP directory bindings count exceeds body");
    for (uint16_t i = 0; i < count; ++i) {
        if (body.size() - pos < 1) return bm_fail(error, "truncated BIOP binding name count");
        const uint8_t name_count = body[pos++];
        BiopBinding binding;
        for (unsigned n = 0; n < name_count; ++n) {
            if (body.size() - pos < 2) return bm_fail(error, "truncated BIOP name component");
            BiopNameComponent component;
            const uint8_t id_length = body[pos++];
            if (id_length > body.size() - pos) return bm_fail(error, "BIOP name id exceeds body");
            component.id.assign(body.begin() + pos, body.begin() + pos + id_length);
            pos += id_length;
            if (body.size() - pos < 1) return bm_fail(error, "truncated BIOP name kind length");
            const uint8_t kind_length = body[pos++];
            if (kind_length > body.size() - pos) return bm_fail(error, "BIOP name kind exceeds body");
            component.kind.assign(body.begin() + pos, body.begin() + pos + kind_length);
            pos += kind_length;
            binding.names.push_back(std::move(component));
        }
        if (body.size() - pos < 1) return bm_fail(error, "truncated BIOP binding type");
        binding.binding_type = body[pos++];
        if (!parse_ior(body.data(), body.size(), pos, binding.ior, error)) return false;
        if (body.size() - pos < 2) return bm_fail(error, "truncated BIOP binding objectInfoLength");
        const uint16_t info_length = bm_be16(body.data() + pos);
        pos += 2;
        if (info_length > body.size() - pos)
            return bm_fail(error, "BIOP binding objectInfo exceeds body");
        binding.object_info.assign(body.begin() + pos, body.begin() + pos + info_length);
        pos += info_length;
        bindings.push_back(std::move(binding));
    }
    if (pos != body.size()) return bm_fail(error, "BIOP directory trailing bytes after bindings");
    return true;
}
}  // namespace

bool decode_biop_module(const uint8_t* bytes, std::size_t size, BiopModule& output) {
    BiopModule parsed;
    std::set<std::vector<uint8_t> > keys;
    while (bytes && parsed.consumed < size) {
        if(parsed.objects.size()>=4096){parsed.error="BIOP object limit exceeded (4096)";break;}
        const std::size_t pos = parsed.consumed, remaining = size - pos;
        if (remaining < 12) { parsed.error = "truncated BIOP module header/tail"; break; }
        if (bytes[pos]!='B'||bytes[pos+1]!='I'||bytes[pos+2]!='O'||bytes[pos+3]!='P') {
            parsed.error = "invalid BIOP module magic/tail"; break;
        }
        const uint32_t declared = bm_be32(bytes + pos + 8);
        if (declared > remaining - 12) { parsed.error = "truncated BIOP module message"; break; }
        BiopMessage message;
        if (!decode_biop_message(bytes + pos, 12u + declared, message, parsed.error)) break;
        if (!message.object_key.empty() && !keys.insert(message.object_key).second)
            ++parsed.duplicate_keys;
        parsed.offsets.push_back(pos);
        parsed.objects.push_back(std::move(message));
        parsed.consumed += 12u + declared;
    }
    if (parsed.objects.empty() && parsed.error.empty()) parsed.error = "empty BIOP module";
    parsed.error_offset = parsed.consumed;
    parsed.complete = parsed.error.empty() && parsed.consumed == size;
    output = std::move(parsed);
    return output.complete;
}

const char* biop_kind_name(uint32_t kind) {
    if (kind == 0x66696c00) return "fil";
    if (kind == 0x64697200) return "dir";
    if (kind == 0x73747200) return "str";
    if (kind == 0x73726700) return "srg";
    if (kind == 0x73746600) return "stf";
    return "unknown";
}

bool decode_biop_ior(const uint8_t* bytes, std::size_t size,
                     BiopIor& output, std::string& error) {
    error.clear();
    if (!bytes || size == 0) { error = "empty BIOP IOR"; return false; }
    std::size_t pos = 0;
    return parse_ior(bytes, size, pos, output, error);
}

bool decode_biop_message(const uint8_t* bytes, std::size_t size,
                         BiopMessage& output, std::string& error) {
    error.clear();
    if (!bytes || size < 24) return bm_fail(error, "truncated BIOP message");
    BiopMessage message;
    message.magic = bm_be32(bytes);
    message.version_major = bytes[4];
    message.version_minor = bytes[5];
    message.byte_order = bytes[6];
    message.message_type = bytes[7];
    message.message_size = bm_be32(bytes + 8);
    if (message.magic != 0x42494f50) return bm_fail(error, "invalid BIOP magic");
    if (message.version_major != 1 || message.version_minor != 0 || message.byte_order != 0)
        return bm_fail(error, "unsupported BIOP version/byte order");
    if (message.message_type > 5) return bm_fail(error, "unsupported BIOP message_type");
    if (message.message_size != size - 12)
        return bm_fail(error, "BIOP message_size does not match input");
    std::size_t pos = 12;
    if (size - pos < 1) return bm_fail(error, "truncated BIOP objectKey length");
    const uint8_t key_length = bytes[pos++];
    if (key_length > size - pos) return bm_fail(error, "BIOP objectKey exceeds message");
    message.object_key.assign(bytes + pos, bytes + pos + key_length);
    pos += key_length;
    if (size - pos < 4) return bm_fail(error, "truncated BIOP objectKind length");
    message.object_kind_length = bm_be32(bytes + pos);
    pos += 4;
    if (message.object_kind_length != 4)
        return bm_fail(error, "unsupported BIOP objectKind length");
    if (size - pos < 4) return bm_fail(error, "truncated BIOP objectKind");
    message.object_kind = bm_be32(bytes + pos);
    pos += 4;
    if (size - pos < 2) return bm_fail(error, "truncated BIOP objectInfo length");
    message.object_info_length = bm_be16(bytes + pos);
    pos += 2;
    if (message.object_info_length > size - pos)
        return bm_fail(error, "BIOP objectInfo exceeds message");
    message.object_info.assign(bytes + pos, bytes + pos + message.object_info_length);
    pos += message.object_info_length;
    if (size - pos < 1) return bm_fail(error, "truncated BIOP serviceContextList count");
    const uint8_t context_count = bytes[pos++];
    for (unsigned i = 0; i < context_count; ++i) {
        if (size - pos < 6) return bm_fail(error, "truncated BIOP service context header");
        BiopContext context;
        context.context_id = bm_be32(bytes + pos);
        const uint16_t length = bm_be16(bytes + pos + 4);
        pos += 6;
        if (length > size - pos) return bm_fail(error, "BIOP service context data exceeds message");
        context.data.assign(bytes + pos, bytes + pos + length);
        pos += length;
        message.service_contexts.push_back(std::move(context));
    }
    if (size - pos < 4) return bm_fail(error, "truncated BIOP messageBodyLength");
    message.body_length = bm_be32(bytes + pos);
    pos += 4;
    if (message.body_length != size - pos)
        return bm_fail(error, "BIOP messageBodyLength does not match remaining bytes");
    message.body.assign(bytes + pos, bytes + size);
    if (message.object_kind == 0x66696c00) {
        if (message.body.size() < 4) return bm_fail(error, "truncated BIOP FileMessage body");
        const uint32_t content_length = bm_be32(message.body.data());
        if (content_length != message.body.size() - 4)
            return bm_fail(error, "BIOP FileMessage content length mismatch");
        if(message.object_info.size()>=8){uint64_t declared=0;for(unsigned i=0;i<8;++i)declared=(declared<<8)|message.object_info[i];if(declared!=content_length)return bm_fail(error,"BIOP File objectInfo content size mismatch");}
        message.content.assign(message.body.begin() + 4, message.body.end());
    } else if (message.object_kind == 0x64697200) {
        if (!parse_bindings(message.body, message.bindings, error)) return false;
    } else if (message.object_kind == 0x73747200 ||
               message.object_kind == 0x73746600) {
        if (!message.object_info.empty()) {
            if (!parse_stream_info(message.object_info, message.stream_info, error)) return false;
            message.stream_info_parsed = true;
        }
        if (message.object_kind == 0x73746600 && !message.body.empty()) {
            if (!parse_stream_event(message.body, message.stream_event, error)) return false;
            message.stream_event_parsed = true;
        }
        if (message.object_kind == 0x73747200) message.stream_data = message.body;
    } else if (message.object_kind == 0x73726700) {
        if (!message.body.empty()) {
            std::string bindings_error;
            if (parse_bindings(message.body, message.bindings, bindings_error)) {
                // Some 2005 SRG bodies use the DirectoryMessage binding list
                // instead of a bare IOR; bindings take precedence.
            } else {
                error.clear();
                std::size_t pos = 0;
                if (!parse_ior(message.body.data(), message.body.size(), pos,
                               message.srg_ior, error)) {
                    error = bindings_error + "; SRG IOR: " + error;
                    return false;
                }
                if (pos != message.body.size())
                    return bm_fail(error, "BIOP SRG IOR trailing bytes");
                message.srg_ior_parsed = true;
            }
        }
    }
    message.raw.assign(bytes, bytes + size);
    output = std::move(message);
    return true;
}

} // namespace biopwire
