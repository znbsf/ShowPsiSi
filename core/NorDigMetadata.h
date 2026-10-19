#pragma once
#include "tsNorDigLogicalChannelDescriptorV2.h"
#include "tsNorDigLogicalChannelDescriptorV1.h"

// Read-only NorDig LCD v2 projection. SDK decoding supplies text and fields;
// wire bounds and list identity remain explicit. No receiver selection policy.
namespace nordigmeta {
using Json = nlohmann::json;

inline void decode(Json& descriptor, const ts::Descriptor& binary,
                   ts::DuckContext& duck, ts::DescriptorContext& context,
                   bool eligible)
{
    if (!eligible) return;
    descriptor["lcn_list_decode_status"] = "invalid";
    descriptor["lcn_list_warnings"] = Json::array();
    auto fail = [&](const char* message) { descriptor["lcn_list_warnings"].push_back(message); };
    auto decoded = binary.deserialize(duck, context);
    const auto* native = dynamic_cast<const ts::NorDigLogicalChannelDescriptorV2*>(decoded.get());
    if (!native || !native->isValid()) {
        fail("SDK rejected NorDig LCD v2; no partial list projection");
        return;
    }
    const auto* bytes = binary.payload();
    const size_t length = binary.payloadSize();
    size_t pos = 0, listIndex = 0;
    Json lists = Json::array();
    for (const auto& list : native->entries) {
        // One id, one name length, name bytes, three country bytes, loop length.
        if (pos + 6 > length) { fail("Truncated NorDig channel-list header"); return; }
        const size_t start = pos, nameBytes = bytes[pos + 1];
        if (nameBytes > 23) { fail("NorDig channel-list name exceeds 23 wire bytes"); return; }
        if (pos + 6 + nameBytes > length) { fail("Truncated NorDig channel-list name/country"); return; }
        pos += 5 + nameBytes;
        const size_t serviceBytes = bytes[pos++];
        if (serviceBytes % 4 || serviceBytes > length - pos || list.services.size() != serviceBytes / 4) {
            fail("Invalid NorDig service-loop length; no partial list projection"); return;
        }
        const size_t base = descriptor.at("offset").get<size_t>() + 2;
        Json item = {{"channel_list_id", list.channel_list_id},
                     {"channel_list_name", list.channel_list_name.toUTF8()},
                     {"country_code", list.country_code.toUTF8()},
                     {"list_index", listIndex++}, {"list_offset", base + start},
                     {"channel_list_name_bytes", nameBytes}, {"services", Json::array()}};
        std::map<uint16_t, size_t> counts;
        for (const auto& service : list.services) ++counts[service.service_id];
        size_t serviceIndex = 0;
        for (const auto& service : list.services) {
            const bool reserved = !(service.visible ? service.lcn >= 1 && service.lcn <= 999 : service.lcn == 0);
            item["services"].push_back({{"service_id", service.service_id}, {"number", service.lcn},
                {"visible", service.visible}, {"allocation_status", reserved ? "reserved" : service.visible ? "visible" : "hidden"},
                {"duplicate_service", counts[service.service_id] > 1},
                {"service_index", serviceIndex++}, {"entry_offset", base + pos}});
            pos += 4;
        }
        lists.push_back(std::move(item));
    }
    if (pos != length) { fail("Trailing NorDig channel-list bytes"); return; }
    descriptor["lcn_lists"] = std::move(lists);
    descriptor["lcn_list_decode_status"] = "decoded";
}

inline void append(Json& service, const Json& descriptor, const std::string& source)
{
    for (const auto& list : descriptor.value("lcn_lists", Json::array())) {
        for (const auto& entry : list["services"]) {
            if (entry["service_id"] != service["id"]) continue;
            Json candidate = entry;
            for (const auto* field : {"channel_list_id", "channel_list_name", "country_code", "list_index", "list_offset"})
                candidate[field] = list[field];
            candidate["onid"] = service["onid"];
            candidate["ts_id"] = service["ts_id"];
            candidate["namespace"] = "nordig_logical_channel_descriptor_v2";
            candidate["pds"] = descriptor["pds"];
            candidate["source_id"] = source;
            candidate["descriptor_offset"] = descriptor["offset"];
            candidate["selected"] = false;
            service["lcn_list_candidates"].push_back(std::move(candidate));
        }
    }
}

inline void finish(Json& service)
{
    bool conflict = false;
    std::map<unsigned, std::set<Json>> definitions;
    for (const auto& candidate : service["lcn_list_candidates"]) {
        definitions[candidate["channel_list_id"].get<unsigned>()].insert(
            Json::array({candidate["channel_list_name"], candidate["country_code"], candidate["number"], candidate["visible"]}));
        conflict = conflict || candidate["duplicate_service"].get<bool>();
    }
    for (const auto& [id, values] : definitions) conflict = conflict || values.size() > 1;
    service["lcn_list_status"] = definitions.empty() ? "none" : conflict ? "conflict" : "selection_required";
    if (!definitions.empty()) {
        // Do not let an ordinary/v1 projection silently overrule available v2
        // lists. Choosing a country/list is a separate, not-yet-implemented action.
        service["logical_channel_number"] = nullptr;
        service["lcn_status"] = service["lcn_list_status"];
    }
}

inline Json semanticCandidates(const Json& candidates)
{
    std::set<Json> values;
    for (auto candidate : candidates) {
        for (const auto* field : {"source_id", "descriptor_offset", "entry_offset", "list_offset", "list_index", "service_index"})
            candidate.erase(field);
        values.insert(std::move(candidate));
    }
    return values;
}
} // namespace nordigmeta
