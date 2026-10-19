#pragma once
#include <stdexcept>

// Independently authored bounded section inspection from ITU-T J.94 (10/2016),
// Annex B. No SCTE65 equivalence, receiver actions or cross-section map assembly.
namespace cableoob {
using Json = nlohmann::json;
inline bool table(unsigned tid) { return tid >= 0xc2 && tid <= 0xc5; }
inline std::string name(unsigned tid) {
    switch (tid) {
    case 0xc2: return "J94_SystemB_NIT";
    case 0xc3: return "J94_SystemB_NTT";
    case 0xc4: return "J94_SystemB_SVCT";
    case 0xc5: return "J94_SystemB_STT";
    default: return "J94_SystemB_unknown";
    }
}
inline std::string bytes(const std::vector<uint8_t>& data, size_t begin, size_t length) {
    static constexpr char digits[] = "0123456789ABCDEF";
    std::string out; out.reserve(length * 2);
    for (size_t i = begin; i < begin + length; ++i) { out += digits[data[i] >> 4]; out += digits[data[i] & 15]; }
    return out;
}
struct Reader {
    const std::vector<uint8_t>& data;
    size_t pos = 3, end;
    explicit Reader(const std::vector<uint8_t>& b):data(b),end(b.size() >= 4 ? b.size() - 4 : 0) {}
    void need(size_t n) const { if (pos > end || n > end - pos) throw std::runtime_error("Truncated field or descriptor"); }
    unsigned u8() { need(1); return data[pos++]; }
    unsigned u16() { const unsigned hi = u8(); return (hi << 8) | u8(); }
    uint64_t u32() { const uint64_t hi = u16(); return (hi << 16) | u16(); }
    void zero(unsigned value) const { if (value) throw std::runtime_error("Required zero bits are nonzero"); }
    Json descriptor() {
        const size_t offset = pos; const unsigned tag = u8(), length = u8(); need(length);
        Json out = {{"tag",tag},{"length",length},{"offset",offset},{"raw_hex",bytes(data,offset,2+length)},
                    {"decode_status","opaque; J.94 descriptor semantics not implemented"}};
        pos += length; return out;
    }
    Json descriptors(unsigned count) {
        Json out = Json::array(); for (unsigned i = 0; i < count; ++i) out.push_back(descriptor()); return out;
    }
    Json tail() { Json out = Json::array(); while (pos < end) out.push_back(descriptor()); return out; }
};
// B.8.1 / Tables B.50, B.52-B.55: NTT uses MTS, not ATSC MSS.
inline void utf8(std::string& text, unsigned code) {
    if (code < 0x80) text += char(code);
    else if (code < 0x800) { text += char(0xc0 | (code >> 6)); text += char(0x80 | (code & 63)); }
    else { text += char(0xe0 | (code >> 12)); text += char(0x80 | ((code >> 6) & 63)); text += char(0x80 | (code & 63)); }
}
inline Json mts(Reader& parent, unsigned length) {
    if (!length) throw std::runtime_error("SNS name_length must be 1..255");
    parent.need(length);
    Reader r(parent.data); r.pos = parent.pos; r.end = r.pos + length;
    Json out = {{"encoding","J.94 MTS (B.8.1)"},{"offset",r.pos},{"length",length},
                {"raw_hex",bytes(r.data,r.pos,length)},{"segments",Json::array()}};
    std::string text, status = "decoded"; unsigned effectors = 0;
    while (r.pos < r.end) {
        const size_t offset = r.pos; const unsigned mode = r.u8();
        const bool format = mode >= 0x40;
        const unsigned count = mode >= 0x40 && mode < 0xa0 ? 0 : r.u8(); r.need(count);
        Json segment = {{"offset",offset},{"mode",mode},{"length",count},
                        {"raw_hex",bytes(r.data,offset,r.pos-offset+count)}};
        std::string part, partStatus = "decoded";
        if (format) {
            ++effectors; segment["kind"] = "format_effector";
            segment["text_status"] = "ignored_in_NTT";
        } else {
            const bool page = mode <= 6 || (mode >= 9 && mode <= 0x10) ||
                              (mode >= 0x20 && mode <= 0x27) || (mode >= 0x30 && mode <= 0x33);
            segment["kind"] = mode == 0x3f ? "BMP_16bit" : page ? "character_page" : "reserved_page";
            if (mode == 0x3f && count % 2) throw std::runtime_error("MTS 16-bit segment length must be even");
            if (!page && mode != 0x3f) partStatus = "unsupported";
            else for (unsigned i = 0; i < count; ++i) {
                unsigned code = (mode << 8) | r.data[r.pos+i];
                if (mode == 0x3f) { code = (r.data[r.pos+i] << 8) | r.data[r.pos+i+1]; ++i; }
                else if (mode == 0 && code >= 0x80 && code <= 0x9f) {
                    switch (code) {
                    case 0x98: code = 0x2030; break;
                    case 0x9a: code = 0x266a; break;
                    case 0x9c: code = 0x2190; break;
                    case 0x9d: code = 0x2191; break;
                    case 0x9e: code = 0x2192; break;
                    case 0x9f: code = 0x2193; break;
                    default: partStatus = "unsupported"; continue;
                    }
                }
                if (code >= 0xd800 && code <= 0xdfff) { partStatus = "invalid_encoding"; continue; }
                utf8(part,code);
            }
            segment["text_status"] = partStatus;
            segment["text"] = partStatus == "decoded" ? Json(part) : Json(nullptr);
            if (partStatus == "invalid_encoding" || (partStatus == "unsupported" && status == "decoded")) status = partStatus;
            text += part;
        }
        r.pos += count; out["segments"].push_back(std::move(segment));
    }
    parent.pos = r.pos;
    out["text_status"] = status; out["text"] = status == "decoded" ? Json(text) : Json(nullptr);
    out["format_effectors_ignored"] = effectors;
    return out;
}
inline Json parse(const std::vector<uint8_t>& b) {
    Json out = {{"profile","ITU-T J.94 (10/2016) System B"},{"decode_status","malformed"},
                {"map_assembled",false},{"warnings",Json::array()}};
    Reader r(b);
    try {
        if (b.size() < 8 || b.size() > 1024 || size_t(3 + ((b[1] & 15) << 8) + b[2]) != b.size())
            throw std::runtime_error("J.94 C2..C5 section must be complete and at most 1024 bytes");
        r.zero(b[1] & 0xc0);
        const unsigned protocol = r.u8(); r.zero(protocol & 0xe0);
        out["protocol_version"] = protocol & 31;
        if (protocol & 31) { out["decode_status"] = "unsupported"; out["warnings"].push_back("Nonzero protocol version is not interpreted"); return out; }
        Json fields = Json::object();
        if (b[0] == 0xc2) {
            const unsigned first = r.u8(), count = r.u8(), type = r.u8(); r.zero(type & 0xf0);
            if (!first) throw std::runtime_error("NIT first_index must be 1..255");
            const unsigned subtype = type & 15;
            fields = {{"first_index",first},{"number_of_records",count},{"table_subtype",subtype},
                      {"records",Json::array()}};
            if (subtype != 1 && subtype != 2) { out["decode_status"] = "unsupported"; out["warnings"].push_back("Unsupported NIT subtype"); return out; }
            fields["subtype_name"] = subtype == 1 ? "CDS" : "MMS";
            unsigned index = first;
            for (unsigned i = 0; i < count; ++i) {
                if (index > 255) throw std::runtime_error("NIT index range exceeds 255");
                const size_t offset = r.pos; Json item;
                if (subtype == 1) {
                    const unsigned carriers = r.u8(), spacing = r.u16(), frequency = r.u16(); r.zero(spacing & 0x4000);
                    if (!carriers || (carriers > 1 && !(spacing & 0x3fff)) || index + carriers > 256)
                        throw std::runtime_error("Invalid CDS carrier count, spacing or index range");
                    const uint64_t spacingHz = uint64_t(spacing & 0x3fff) * (spacing & 0x8000 ? 125000 : 10000);
                    const uint64_t firstHz = uint64_t(frequency & 0x7fff) * (frequency & 0x8000 ? 125000 : 10000);
                    item = {{"offset",offset},{"first_carrier_index",index},{"number_of_carriers",carriers},
                            {"spacing_unit",spacing >> 15},{"frequency_spacing",spacing & 0x3fff},
                            {"frequency_unit",frequency >> 15},{"first_carrier_frequency",frequency & 0x7fff},
                            {"first_frequency_hz",firstHz},{"spacing_hz",spacingHz},{"spacing_applicable",carriers > 1},
                            {"last_frequency_hz",firstHz + (carriers - 1) * spacingHz}};
                    index += carriers;
                } else {
                    const unsigned coding = r.u8(), modulation = r.u8(); const uint64_t symbolRate = r.u32();
                    r.zero(modulation & 0x60); r.zero(unsigned(symbolRate >> 28));
                    item = {{"offset",offset},{"modulation_index",index++},{"transmission_system",coding >> 4},
                            {"inner_coding_mode",coding & 15},{"split_bitstream_mode",bool(modulation & 0x80)},
                            {"modulation_format",modulation & 31},{"symbol_rate",symbolRate}};
                }
                item["descriptors"] = r.descriptors(r.u8()); fields["records"].push_back(std::move(item));
            }
        } else if (b[0] == 0xc3) {
            const size_t languageOffset = r.pos; r.need(3);
            const bool wildcard = r.data[r.pos] == 255 && r.data[r.pos+1] == 255 && r.data[r.pos+2] == 255;
            std::string language; for (unsigned i = 0; i < 3; ++i) utf8(language,r.u8());
            const unsigned type = r.u8(); r.zero(type & 0xf0);
            if ((type & 15) != 6) { out["decode_status"] = "unsupported"; out["warnings"].push_back("Unsupported NTT subtype"); return out; }
            const unsigned count = r.u8();
            if (!count) throw std::runtime_error("SNS record count must be 1..255");
            fields = {{"table_subtype",6},{"subtype_name","SNS"},{"language_code_raw",bytes(b,languageOffset,3)},
                      {"language_code",wildcard ? Json(nullptr) : Json(language)},{"language_wildcard",wildcard},
                      {"record_count",count},{"records",Json::array()}};
            for (unsigned i = 0; i < count; ++i) {
                const size_t offset = r.pos; const unsigned flags = r.u8(); r.zero(flags & 127);
                const unsigned identity = r.u16(), length = r.u8();
                Json item = {{"offset",offset},{"application_type",bool(flags & 128)}};
                item[flags & 128 ? "application_id" : "source_id"] = identity;
                item["source_name"] = mts(r,length);
                if (item["source_name"]["text_status"] != "decoded")
                    out["warnings"].push_back("SNS text contains unsupported or invalid encoding; raw segments retained and complete text withheld");
                item["descriptors"] = r.descriptors(r.u8()); fields["records"].push_back(std::move(item));
            }
        } else if (b[0] == 0xc4) {
            const unsigned type = r.u8(); r.zero(type & 0xf0); const unsigned subtype = type & 15;
            fields = {{"table_subtype",subtype},{"vct_id",r.u16()},{"records",Json::array()}};
            if (subtype == 1 || subtype == 2) {
                const unsigned first = r.u16(), length = r.u8(); r.zero(first & 0xf000); r.zero(length & 0x80);
                if (!length) throw std::runtime_error("DCM/ICM record count must be 1..127");
                fields["subtype_name"] = subtype == 1 ? "DCM" : "ICM";
                fields[subtype == 1 ? "first_virtual_channel" : "first_map_index"] = first;
                fields["record_count"] = length;
                unsigned next = first;
                for (unsigned i = 0; i < length; ++i) {
                    const size_t offset = r.pos;
                    if (subtype == 1) {
                        const unsigned entry = r.u8(), count = entry & 127;
                        if (!count || next + count > 4096) throw std::runtime_error("DCM range exceeds virtual-channel bounds or is empty");
                        fields["records"].push_back({{"offset",offset},{"first_virtual_channel",next},
                            {"last_virtual_channel",next + count - 1},{"channels_count",count},{"range_defined",bool(entry & 128)}});
                        next += count;
                    } else {
                        const unsigned source = r.u16(), channel = r.u16(); r.zero(channel & 0xf000);
                        if (next > 4095) throw std::runtime_error("ICM map index exceeds 4095");
                        fields["records"].push_back({{"offset",offset},{"map_index",next++},{"source_id",source},{"virtual_channel_number",channel}});
                    }
                }
            } else if (subtype == 0) {
                const unsigned flags = r.u8(), splice = r.u8(); r.zero(flags & 0xdf); r.zero(splice & 127);
                const uint64_t activation = r.u32(); const unsigned count = r.u8();
                if (!count) throw std::runtime_error("VCM record count must be 1..255");
                fields["subtype_name"] = "VCM"; fields["descriptors_included"] = bool(flags & 32);
                fields["splice"] = bool(splice & 128); fields["activation_time"] = activation;
                fields["activation_time_basis"] = "Signalled GPS epoch seconds; no STT/UTC resolution or receiver activation";
                fields["record_count"] = count;
                for (unsigned i = 0; i < count; ++i) {
                    const size_t offset = r.pos; const unsigned channel = r.u16(), kind = r.u8(), identity = r.u16();
                    r.zero(channel & 0xf000); r.zero(kind & 0x40);
                    Json item = {{"offset",offset},{"virtual_channel_number",channel},{"application_virtual_channel",bool(kind & 128)},
                                 {"path_select",(kind >> 5) & 1},{"transport_type",(kind >> 4) & 1},{"channel_type",kind & 15}};
                    item[kind & 128 ? "application_id" : "source_id"] = identity; item["cds_reference"] = r.u8();
                    if (!(kind & 16)) {
                        const unsigned program = r.u16(), mms = r.u8();
                        if (program && !mms) throw std::runtime_error("Active MPEG-2 VCM record requires a nonzero MMS reference");
                        item["program_number"] = program; item["mms_reference"] = mms;
                    }
                    else { const unsigned video = r.u8(); r.zero(video & 0x70); r.zero(r.u16()); item["scrambled"] = bool(video & 128); item["video_standard"] = video & 15; }
                    item["descriptors"] = flags & 32 ? r.descriptors(r.u8()) : Json::array();
                    fields["records"].push_back(std::move(item));
                }
            } else { out["decode_status"] = "unsupported"; out["warnings"].push_back("Unsupported short-VCT subtype"); return out; }
        } else if (b[0] == 0xc5) {
            r.zero(r.u8()); const uint64_t time = r.u32(); const unsigned offset = r.u8();
            const int64_t utc = int64_t(time) - int64_t(offset);
            fields = {{"system_time",time},{"gps_utc_offset",offset},
                      {"signalled_time_basis",offset ? "GPS seconds since 1980-01-06T00:00:00Z" : "UTC seconds since 1980-01-06T00:00:00Z"},
                      {"utc_seconds_since_gps_epoch",utc},{"utc_unix_seconds",utc + 315964800},
                      {"time_scope","Arithmetic from this section only; no clock setting, capture-time validation or VCM activation"}};
        } else {
            out["decode_status"] = "unsupported"; out["warnings"].push_back("Unsupported J.94 table"); return out;
        }
        fields["descriptors"] = r.tail(); out["fields"] = std::move(fields); out["decode_status"] = "decoded";
    } catch (const std::runtime_error& error) { out["warnings"].push_back(error.what()); out["error_offset"] = r.pos; }
    return out;
}
inline Json tree(const Json& value, const std::string& label) {
    Json node = {{"name",label},{"attributes",Json::object()},{"children",Json::array()}};
    if (value.is_object()) for (auto it = value.begin(); it != value.end(); ++it) {
        if (it.value().is_structured()) node["children"].push_back(tree(it.value(),it.key()));
        else node["attributes"][it.key()] = it.value().is_string() ? it.value().get<std::string>() : it.value().dump();
    }
    else if (value.is_array()) for (const auto& item : value) node["children"].push_back(tree(item,"record"));
    else node["text"] = value.is_string() ? value.get<std::string>() : value.dump();
    return node;
}
} // namespace cableoob
