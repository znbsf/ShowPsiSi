#pragma once
#include <stdexcept>
#include <algorithm>
#include <map>
#include <set>

// Independently authored bounded section inspection from ITU-T J.94 (10/2016),
// Annex B. Descriptor-revised subtables only; no SCTE65 equivalence, receiver
// actions or synchronized cross-subtable network lineup.
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
inline Json revisionDetection(const std::vector<uint8_t>& raw, const Json& descriptors) {
    Json out = {{"scope","table-level descriptor only"},{"status","absent"},{"candidates",Json::array()}};
    bool malformed = false; std::set<std::string> values;
    for (const auto& descriptor : descriptors) if (descriptor.at("tag") == 0x93) {
        const size_t offset = descriptor.at("offset"), length = descriptor.at("length");
        Json item = {{"offset",offset},{"length",length},{"raw_hex",descriptor.at("raw_hex")}};
        if (length < 3) { item["status"] = "malformed"; malformed = true; }
        else {
            const unsigned version = raw[offset+2] & 31, number = raw[offset+3], last = raw[offset+4];
            item["table_version_number"] = version; item["section_number"] = number;
            item["last_section_number"] = last; item["extension_hex"] = bytes(raw,offset+5,length-3);
            item["status"] = number <= last ? "valid" : "malformed";
            malformed |= number > last;
            values.insert(std::to_string(version)+":"+std::to_string(number)+":"+std::to_string(last)+":"+item["extension_hex"].get<std::string>());
        }
        out["candidates"].push_back(std::move(item));
    }
    const size_t count = out["candidates"].size();
    if (count) out["status"] = malformed ? "malformed" : values.size() > 1 ? "conflicting" : count > 1 ? "duplicate" : "valid";
    if (out["status"] == "valid") out["selected"] = out["candidates"][0];
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
        fields["descriptors"] = r.tail();
        if (b[0] != 0xc5) out["revision_detection"] = revisionDetection(b,fields["descriptors"]);
        out["fields"] = std::move(fields); out["decode_status"] = "decoded";
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
// Subtable assembly is separate from exact section inspection and MPEG headers.
// The caller supplies already observed engine records and a fixed capture cutoff.
constexpr size_t MaxGroups = 512, MaxObservations = 8192, MaxRecords = 8192;
template<class Records>
Json snapshot(const Records& records, uint64_t cutoff, size_t revision, size_t offset, size_t limit) {
    using Record = typename Records::value_type;
    struct Observation { const Record* record; uint64_t order, packet; size_t count; };
    struct Group { Json identity; std::vector<Observation> observations; };
    std::map<std::string,Group> groups; Json excluded = Json::array(); size_t observed = 0, outputRecords = 0;
    auto source = [&](const Observation& o) {
        return Json{{"analysis_revision",revision},{"at_packet",cutoff},{"section_id",o.record->id},
                    {"last_observed_packet",o.packet},{"receive_order",o.order},{"occurrences",o.count}};
    };
    for (const auto& record : records) {
        if (!record.j94 || record.tid == 0xc5) continue;
        auto end = std::upper_bound(record.ends.begin(),record.ends.end(),cutoff);
        if (end == record.ends.begin()) continue;
        if (++observed > MaxObservations) throw std::runtime_error("J.94 query observation limit (8192) exceeded; choose an earlier cutoff");
        const size_t index = size_t(end-record.ends.begin())-1;
        Observation o{&record,record.orders.at(index),record.ends[index],index+1};
        if (!record.valid || !record.fields.contains("j94_system_b") || record.fields.at("j94_system_b").value("decode_status",std::string()) != "decoded") {
            Json item = source(o); item["reason"] = !record.valid ? "invalid_integrity" : "unsupported_or_malformed_payload";
            excluded.push_back(std::move(item)); continue;
        }
        const Json& decoded = record.fields.at("j94_system_b"), &fields = decoded.at("fields");
        const unsigned subtype = fields.at("table_subtype");
        std::string id = std::to_string(record.pid)+":"+std::to_string(record.tid)+":"+std::to_string(subtype);
        Json identity = {{"pid",record.pid},{"table_id",record.tid},{"table_subtype",subtype},{"subtype_name",fields.at("subtype_name")}};
        if (record.tid == 0xc3) { identity["language_code_raw"] = fields.at("language_code_raw"); id += ":language="+fields.at("language_code_raw").get<std::string>(); }
        if (record.tid == 0xc4) { identity["vct_id"] = fields.at("vct_id"); id += ":vct="+std::to_string(fields.at("vct_id").get<unsigned>()); }
        auto [found,inserted] = groups.try_emplace(id,Group{identity,{}});
        if (inserted && groups.size() > MaxGroups) throw std::runtime_error("J.94 query group limit (512) exceeded; choose an earlier cutoff");
        found->second.observations.push_back(o);
    }
    Json result = {{"profile","ITU-T J.94 (10/2016) System B"},{"analysis_revision",revision},{"at_packet",cutoff},
                   {"total_groups",groups.size()},{"offset",offset},{"limit",limit},{"next_offset",nullptr},
                   {"groups",Json::array()},{"excluded_evidence",excluded},{"network_lineup_complete",false},
                   {"scope","Descriptor-revised subtables only; no cross-table synchronization, receiver activation or complete lineup"},
                   {"completeness_basis","Descriptor-declared section coverage without slot/key/range conflicts; text and descriptor support remains per-field"},
                   {"limits",{{"groups",MaxGroups},{"observations",MaxObservations},{"assembled_records",MaxRecords}}}};
    size_t groupIndex = 0;
    for (const auto& [id,g] : groups) {
        if (groupIndex++ < offset || result["groups"].size() >= limit) continue;
        const Observation* newest = &g.observations.front();
        Json observations = Json::array();
        for (const auto& o : g.observations) {
            if (o.order > newest->order) newest = &o;
            Json item = source(o); item["revision_detection"] = o.record->fields.at("j94_system_b").at("revision_detection"); observations.push_back(std::move(item));
        }
        const auto& latestRevision = newest->record->fields.at("j94_system_b").at("revision_detection");
        Json out = {{"id",id},{"identity",g.identity},{"analysis_revision",revision},{"at_packet",cutoff},
                    {"revision_detection",nullptr},{"observations",observations},{"sources",Json::array()},
                    {"records",Json::array()},{"diagnostics",Json::array()},{"sections_complete",false},
                    {"subtable_complete",false},{"network_lineup_complete",false},{"missing_section_numbers",Json::array()},
                    {"required_section_numbers",Json::array()},{"observed_section_numbers",Json::array()}};
        if (latestRevision.at("status") != "valid") {
            out["status"] = latestRevision.at("status") == "absent" ? "unversioned" : "revision_ambiguous";
            out["diagnostics"].push_back({{"code","revision_selection_blocked"},{"section_id",newest->record->id},
                {"detail","Newest valid payload has no unambiguous revision descriptor; no older complete fallback or baseline flattening"}});
            result["groups"].push_back(std::move(out)); continue;
        }
        const Json& selectedRevision = latestRevision.at("selected");
        const unsigned version = selectedRevision.at("table_version_number"), last = selectedRevision.at("last_section_number");
        out["revision_detection"] = {{"scope","table-level descriptor"},{"table_version_number",version},{"last_section_number",last}};
        uint64_t barrier = 0;
        auto matches = [&](const Observation& o) {
            const auto& r = o.record->fields.at("j94_system_b").at("revision_detection");
            return r.at("status") == "valid" && r.at("selected").at("table_version_number") == version && r.at("selected").at("last_section_number") == last;
        };
        for (const auto& o : g.observations) if (!matches(o)) barrier = std::max(barrier,o.order);
        out["generation_barrier_receive_order"] = barrier;
        std::map<unsigned,std::vector<const Observation*>> slots;
        for (const auto& o : g.observations) if (o.order > barrier && matches(o))
            slots[o.record->fields.at("j94_system_b").at("revision_detection").at("selected").at("section_number").template get<unsigned>()].push_back(&o);
        bool conflict = false;
        struct Range { unsigned first,last; Json source; };
        std::vector<Range> ranges; std::map<std::string,Json> keys;
        const std::string subtype = g.identity.at("subtype_name");
        for (unsigned number = 0; number <= last; ++number) {
            out["required_section_numbers"].push_back(number);
            auto found = slots.find(number);
            if (found == slots.end()) { out["missing_section_numbers"].push_back(number); continue; }
            out["observed_section_numbers"].push_back(number);
            for (const auto* candidate : found->second) {
                Json src = source(*candidate);
                src["revision_descriptor"] = candidate->record->fields.at("j94_system_b").at("revision_detection").at("selected");
                out["sources"].push_back(std::move(src));
            }
            if (found->second.size() != 1) {
                conflict = true; out["diagnostics"].push_back({{"code","conflicting_section_slot"},{"section_number",number}}); continue;
            }
            const Observation& o = *found->second.front(); const Json& fields = o.record->fields.at("j94_system_b").at("fields");
            const Json& rd = o.record->fields.at("j94_system_b").at("revision_detection").at("selected");
            for (const auto& item : fields.at("records")) {
                if (++outputRecords > MaxRecords) throw std::runtime_error("J.94 query assembled-record limit (8192) exceeded; narrow page or cutoff");
                Json src = source(o); src["record_offset"] = item.at("offset"); src["revision_descriptor_offset"] = rd.at("offset");
                src["descriptor_section_number"] = number; src["descriptor_version"] = version;
                Json row = item; row["source"] = src;
                std::string key; unsigned first = 0, finish = 0; bool hasRange = true;
                if (subtype == "CDS") { first = item.at("first_carrier_index"); finish = first + item.at("number_of_carriers").get<unsigned>() - 1; }
                else if (subtype == "MMS") first = finish = item.at("modulation_index");
                else if (subtype == "DCM") { first = item.at("first_virtual_channel"); finish = item.at("last_virtual_channel"); }
                else if (subtype == "ICM") first = finish = item.at("map_index");
                else {
                    hasRange = false;
                    if (subtype == "VCM") {
                        row["activation_time"] = fields.at("activation_time"); row["splice"] = fields.at("splice");
                        key = std::to_string(fields.at("activation_time").get<uint64_t>())+":"+std::to_string(item.at("virtual_channel_number").get<unsigned>());
                    } else key = item.at("application_type").get<bool>() ? "application:"+std::to_string(item.at("application_id").get<unsigned>()) : "source:"+std::to_string(item.at("source_id").get<unsigned>());
                    auto [prior,inserted] = keys.emplace(key,src);
                    if (!inserted) { conflict = true; out["diagnostics"].push_back({{"code","duplicate_record_key"},{"key",key},{"sources",Json::array({prior->second,src})}}); }
                }
                if (hasRange) ranges.push_back({first,finish,src});
                out["records"].push_back(std::move(row));
            }
        }
        std::sort(ranges.begin(),ranges.end(),[](const Range& a,const Range& b){return std::tie(a.first,a.last)<std::tie(b.first,b.last);});
        Json coverage = {{"ranges",Json::array()},{"gaps_between_observed_ranges",Json::array()},
                         {"outside_observed_bounds","unknown"},{"gaps_are_proof_of_missing_transmission",false}};
        unsigned highest = 0; bool seen = false;
        for (const auto& range : ranges) {
            coverage["ranges"].push_back({{"first",range.first},{"last",range.last},{"source",range.source}});
            if (seen && range.first <= highest) { conflict = true; out["diagnostics"].push_back({{"code","overlapping_index_range"},{"first",range.first},{"last",range.last},{"source",range.source}}); }
            if (seen && range.first > highest+1) coverage["gaps_between_observed_ranges"].push_back({{"first",highest+1},{"last",range.first-1}});
            highest = std::max(highest,range.last); seen = true;
        }
        out["range_coverage"] = coverage;
        out["sections_complete"] = out["missing_section_numbers"].empty() && std::all_of(slots.begin(),slots.end(),[](const auto& slot){return slot.second.size()==1;});
        out["subtable_complete"] = out["sections_complete"].get<bool>() && !conflict;
        out["status"] = conflict ? "conflict" : out["subtable_complete"].get<bool>() ? "complete_subtable" : "incomplete";
        result["groups"].push_back(std::move(out));
    }
    if (offset < groups.size() && result["groups"].size() < groups.size()-offset) result["next_offset"] = offset+result["groups"].size();
    return result;
}

} // namespace cableoob
