#ifndef SHOWPSISI_BIOP_MESSAGE_H
#define SHOWPSISI_BIOP_MESSAGE_H
#include <cstddef>
#include <cstdint>
#include <iosfwd>
#include <string>
#include <vector>
namespace biopwire {
struct BiopNameComponent {
    std::vector<uint8_t> id, kind;
};
struct BiopIorProfile {
    uint32_t profile_id = 0;
    std::vector<uint8_t> data;
    bool body_parsed = false;
    std::vector<uint8_t> object_key;
    uint32_t object_kind = 0;
    uint16_t object_info_length = 0;
    std::vector<uint8_t> object_info;
    bool location_parsed = false;
    uint16_t module_id = 0;
    uint32_t carousel_id = 0;
    bool legacy_module_version = false;
    uint8_t biop_version_major = 0, biop_version_minor = 0;
    uint8_t module_version = 0;
    std::string object_name;
};
struct BiopIor {
    uint32_t type_id = 0;
    std::vector<BiopIorProfile> profiles;
};
struct BiopBinding {
    std::vector<BiopNameComponent> names;
    uint8_t binding_type = 0;
    BiopIor ior;
    std::vector<uint8_t> object_info;
};
struct BiopContext {
    uint32_t context_id = 0;
    std::vector<uint8_t> data;
};
struct BiopStreamInfo {
    std::vector<uint8_t> description;
    uint32_t duration_seconds = 0, duration_microseconds = 0;
    uint8_t audio = 0, video = 0;
};
struct BiopStreamEvent {
    std::vector<std::vector<uint8_t> > event_names;
    std::vector<uint32_t> event_ids;
};
struct BiopMessage {
    uint32_t magic = 0, message_size = 0;
    uint8_t version_major = 0, version_minor = 0, byte_order = 0, message_type = 0;
    std::vector<uint8_t> object_key;
    uint32_t object_kind_length = 0, object_kind = 0;
    uint16_t object_info_length = 0;
    std::vector<uint8_t> object_info;
    bool location_parsed = false;
    uint16_t module_id = 0;
    uint8_t module_version = 0;
    std::string object_name;
    std::vector<BiopContext> service_contexts;
    uint32_t body_length = 0;
    std::vector<uint8_t> body;
    std::vector<BiopBinding> bindings;   // DirectoryMessage only
    std::vector<uint8_t> content;        // FileMessage only
    BiopStreamInfo stream_info;          // Stream/StreamEvent objectInfo
    BiopStreamEvent stream_event;        // StreamEventMessage body
    std::vector<uint8_t> stream_data;    // StreamMessage body (opaque payload)
    BiopIor srg_ior;                     // SRG body (independent envelope model)
    bool stream_info_parsed = false, stream_event_parsed = false;
    bool srg_ior_parsed = false;
    std::vector<uint8_t> raw;
};
struct BiopModule {
    std::vector<BiopMessage> objects;
    std::vector<std::size_t> offsets;
    std::size_t consumed = 0, error_offset = 0, duplicate_keys = 0;
    bool complete = false;
    std::string error;
};
// Exact concatenation only: no padding or resynchronization is implied. On
// damage retain the validated prefix and identify the first undecoded byte.
// Duplicate nonempty keys remain visible but must never resolve arbitrarily.
bool decode_biop_module(const uint8_t*, std::size_t, BiopModule&);
// Parses exactly one BIOP message (File/Directory/Stream/StreamEvent/SRG
// envelope). Directory bindings and File content are decoded; other body types
// are retained as raw bytes. Independent wire model; no carousel lifecycle or
// original-binary A/B is claimed.
bool decode_biop_ior(const uint8_t* bytes, std::size_t size,
                     BiopIor& output, std::string& error);
bool decode_biop_message(const uint8_t* bytes, std::size_t size,
                         BiopMessage& output, std::string& error);
const char* biop_kind_name(uint32_t kind);
}
#endif
