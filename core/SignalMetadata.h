#pragma once

// Interpretation metadata never changes the captured section or SDK XML.
#include "tsDVBCharset.h"
#include "tsDVBCharTable.h"
#include "tsExtendedEventDescriptor.h"

namespace signalmeta {
struct Registry { const char* key; const char* section; unsigned bits; };
inline const Registry registries[] = {
    {"original_network_id", "OriginalNetworkId", 16}, {"network_id", "NetworkId", 16},
    {"bouquet_id", "BouquetId", 16}, {"ca_system_id", "CASystemId", 16},
    {"private_data_specifier", "PrivateDataSpecifier", 32},
    {"registration_id", "mpeg.registration_id", 32}, {"data_broadcast_id", "DataBroadcastId", 16},
    {"platform_id", "INT.platform_id", 24}, {"oui", "OUI", 24}
};
inline J lookup(const std::string& kind, uint64_t value, const std::string& standard) {
    const Registry* registry=nullptr;
    for(const auto& entry:registries)if(kind==entry.key)registry=&entry;
    if(!registry || value >= (uint64_t(1)<<registry->bits))throw std::runtime_error("Identifier namespace or value out of range");
    const bool japan=standard=="isdb-japan";
    const bool dvb=standard=="dvb"||standard=="dtmb";
    const bool global=kind=="registration_id"||kind=="oui";
    const bool contextual=!global&&!dvb&&!(japan&&kind=="ca_system_id");
    const std::string section=japan&&kind=="ca_system_id"?"ARIBCASystemId":registry->section;
    const std::string file=kind=="oui"?"tsduck.oui.names":"tsduck.dtv.names";
    const auto label=contextual?std::string():ts::NameFromSection(ts::UString::FromUTF8(file),ts::UString::FromUTF8(section),value,ts::NamesFlags::NO_UNKNOWN).toUTF8();
    std::ostringstream number;number<<"0x"<<std::hex<<std::uppercase<<std::setfill('0')<<std::setw(registry->bits/4)<<value;
    return {{"namespace",kind},{"raw_value",value},{"raw_hex",number.str()},{"label",label.empty()?J():J(label)},
        {"status",contextual?"context_required":label.empty()?"unknown":"registry_label"},{"standards_context",standard},
        {"source",{{"kind","installed_sdk_name_registry"},{"file",file},{"section",section},
            {"sdk_version",TS_VERSION_STRING},
            {"url","https://tsduck.io/"},{"registry_date",nullptr}}},
        {"uncertainty",contextual?"Select the applicable standard; no cross-family name is inferred.":
            "SDK reference label, not verified current operator ownership. Registry may include ranges, historical names or extensions; absence is not proof of an unassigned ID."}};
}

inline J evidence(const Record& r, size_t offset) {
    return {{"section_id",r.id},{"pid",r.pid},{"table_id",r.tid},{"section_offset",offset}};
}

// Keep provenance in API values, but do not call an unchanged event changed
// merely because it moved within a section or its section version changed.
inline void removeSources(J& value) {
    if(value.is_object())value.erase("source");
    if(value.is_structured())for(auto& child:value)removeSources(child);
}

inline J identifiers(const Record& r,const std::string& standard) {
    J result=J::array();
    auto add=[&](const std::string& kind,uint64_t value,const std::string& path,size_t offset){
        auto entry=lookup(kind,value,standard);entry["wire_source"]=evidence(r,offset);
        entry["field_path"]=path;entry["wire_source"]["offset_scope"]="containing header or descriptor; field_path identifies the decoded field";result.push_back(entry);
    };
    if(r.fields.contains("original_network_id"))add("original_network_id",r.fields["original_network_id"],"fields.original_network_id",8);
    if(r.fields.contains("network_id"))add("network_id",r.fields["network_id"],"fields.network_id",3);
    if(r.fields.contains("bouquet_id"))add("bouquet_id",r.fields["bouquet_id"],"fields.bouquet_id",3);
    if(r.tid>=0x4e&&r.tid<=0x6f&&r.raw.size()>=14)add("original_network_id",u16(r.raw,10),"events.original_network_id",10);
    for(const auto& transport:r.fields.value("transports",J::array()))add("original_network_id",transport["original_network_id"],"transports.original_network_id",transport["descriptor_offset"].get<size_t>()-4);
    std::function<void(const J&,const std::string&,size_t)> walk=[&](const J& node,const std::string& path,size_t offset){
        if(node.value("name",std::string())=="registration_descriptor"&&node.value("attributes",J::object()).contains("format_identifier")){
            try{const std::string s=node["attributes"]["format_identifier"];size_t used=0;const auto value=std::stoull(s,&used,0);if(used==s.size())add("registration_id",value,path+".format_identifier",offset);}catch(const std::exception&){}
        }
        for(const auto& entry:registries)if(node.value("attributes",J::object()).contains(entry.key)){
            const auto& raw=node["attributes"][entry.key];
            if(raw.is_string())try{const std::string s=raw;size_t used=0;const auto value=std::stoull(s,&used,0);if(used==s.size())add(entry.key,value,path+"."+entry.key,offset);}catch(const std::exception&){}
        }
        size_t i=0;for(const auto& child:node.value("children",J::array()))walk(child,path+"/"+child.value("name",std::string())+"["+std::to_string(i++)+"]",offset);
    };
    for(const auto& descriptor:r.descriptors)if(descriptor.value("native_decoded",false)&&descriptor.contains("native"))
        walk(descriptor["native"],"descriptors@"+std::to_string(descriptor["offset"].get<size_t>()),descriptor["offset"]);
    return result;
}

// Return diagnostics for precisely bounded wire strings, not re-encoded XML.
inline J text(const Record& r, const ts::Charset* charset, const std::string& field,
              size_t offset,size_t length,size_t limit,const std::string& language="") {
    const size_t available=offset<=limit?std::min(length,limit-offset):0;
    J out={{"field",field},{"language_code",language},{"source",evidence(r,offset)},
        {"declared_bytes",length},{"available_bytes",available},{"raw_hex",available?hex(r.raw.data()+offset,available):""},
        {"configured_charset",charset->name().toUTF8()},{"selector_hex",""},{"effective_charset",nullptr},
        {"basis","configured_charset"},{"status","decoded"},{"decoded_text",""},{"warnings",J::array()},
        {"uncertainty","Decoder success does not prove the broadcaster used the declared/default encoding."}};
    if(length!=available){out["status"]="truncated";out["warnings"].push_back("String length exceeds its containing field");}
    if(!available){if(!length)out["status"]="empty";return out;}
    const auto* bytes=r.raw.data()+offset;
    bool selectorOK=true;
    if(dynamic_cast<const ts::DVBCharset*>(charset)){
        uint32_t code=0;size_t size=0;
        selectorOK=ts::DVBCharTable::DecodeTableCode(code,size,bytes,available);
        const size_t indicated=bytes[0]>=0x20?0:bytes[0]==0x10?3:bytes[0]==0x1f?2:1;
        out["selector_hex"]=hex(bytes,std::min(indicated,available));
        out["basis"]=indicated?"wire_selector":"default_charset";
        if(indicated){
            const auto* table=selectorOK?ts::DVBCharTable::GetTableFromLeadingCode(code):nullptr;
            if(table)out["effective_charset"]=table->name().toUTF8();
            else {selectorOK=false;out["warnings"].push_back("Invalid, truncated or SDK-unsupported character table selector");}
        }else out["effective_charset"]=charset->name().toUTF8();
    }else out["effective_charset"]=charset->name().toUTF8();
    ts::UString decoded;
    const bool ok=charset->decode(decoded,bytes,available);
    out["decoded_text"]=decoded.toUTF8();out["decoder_success"]=ok;
    if(!selectorOK)out["status"]="unsupported_or_invalid_selector";
    else if(!ok){out["status"]="decode_error";out["warnings"].push_back("SDK could not decode all input bytes; partial text is not authoritative");}
    if(length!=available)out["status"]="truncated";
    if(decoded.find(char16_t(0xfffd))!=ts::UString::npos)out["warnings"].push_back("Decoded text contains U+FFFD (may be transmitted or a replacement)");
    return out;
}

inline void diagnose(Record& r,J& d,const ts::Charset* charset) {
    d["text_diagnostics"]=J::array();
    const std::string name=d.value("name",std::string());
    const size_t begin=d["offset"].get<size_t>()+2, end=begin+d["length"].get<size_t>();
    if(end>r.raw.size())return;
    auto add=[&](const std::string& field,size_t offset,size_t length,const std::string& language=""){
        d["text_diagnostics"].push_back(text(r,charset,field,offset,length,end,language));
    };
    auto sized=[&](const std::string& field,size_t& p,const std::string& language=""){
        if(p>=end)return false;const size_t n=r.raw[p++];add(field,p,n,language);p+=n;return p<=end;
    };
    auto lang=[&](size_t p){return p+3<=end?std::string(reinterpret_cast<const char*>(r.raw.data()+p),3):std::string();};
    size_t p=begin;
    if(name=="service_descriptor"&&p<end){++p;if(sized("provider_name",p))sized("service_name",p);}
    else if(name=="short_event_descriptor"&&p+3<=end){auto language=lang(p);p+=3;if(sized("event_name",p,language))sized("text",p,language);}
    else if(name=="extended_event_descriptor"&&p+5<=end){
        auto language=lang(p+1);p+=4;size_t stop=p+1+r.raw[p];++p;unsigned i=0;
        while(p<stop&&stop<=end){
            // Item lengths are bounded by the item loop, not the trailing text.
            for(const char* field:{"description","value"}){
                if(p>=stop)return;const size_t n=r.raw[p++];
                d["text_diagnostics"].push_back(text(r,charset,"items["+std::to_string(i)+"]."+field,p,n,stop,language));
                p+=n;if(p>stop)return;
            }++i;
        }
        if(p==stop)sized("text",p,language);
    }else if(name=="network_name_descriptor"||name=="bouquet_name_descriptor")add("name",p,end-p);
    else if(name=="component_descriptor"&&p+6<=end)add("text",p+6,end-p-6,lang(p+3));
    else if(name=="multilingual_network_name_descriptor"||name=="multilingual_bouquet_name_descriptor"||name=="multilingual_service_name_descriptor"||name=="multilingual_component_descriptor"){
        if(name=="multilingual_component_descriptor")++p;
        unsigned i=0;while(p+3<=end){auto language=lang(p);p+=3;
            if(name=="multilingual_service_name_descriptor"&&!sized("entries["+std::to_string(i)+"].provider_name",p,language))break;
            if(!sized("entries["+std::to_string(i++)+"].name",p,language))break;
        }
    }
    d["text_diagnostic_scope"]="Wire strings in service, short/extended event, network/bouquet, component and multilingual name descriptors; other structures are not diagnosed";
}

inline J languages(const Record& r,size_t first,ts::DuckContext& duck) {
    std::map<std::string,J> byLanguage;
    for(size_t i=first;i<r.descriptors.size();++i){
        const auto& d=r.descriptors[i];
        // This function is called only for a DVB-layout EIT event loop. A user
        // extension's display name must never turn a private tag into event text.
        const unsigned tag=d["tag"];
        const std::string name=tag==0x4d?"short_event_descriptor":tag==0x4e?"extended_event_descriptor":"";
        if(name!="short_event_descriptor"&&name!="extended_event_descriptor")continue;
        const size_t offset=d["offset"],length=d["length"];
        if(offset+length+2>r.raw.size()||length<(name=="short_event_descriptor"?3u:4u))continue;
        const size_t lp=offset+(name=="short_event_descriptor"?2:3);
        std::string language(reinterpret_cast<const char*>(r.raw.data()+lp),3);
        if(!byLanguage.count(language))byLanguage[language]={{"language_code",language},{"short_descriptions",J::array()},{"extended_fragments",J::array()},{"warnings",J::array()}};
        auto& variant=byLanguage[language];ts::Descriptor binary(r.raw.data()+offset,length+2);
        const auto diagnostics=d.value("text_diagnostics",J::array());bool textOK=true;
        for(const auto& t:diagnostics)if(t["status"]!="decoded"&&t["status"]!="empty")textOK=false;
        J item={{"source",evidence(r,offset)},{"raw_hex",d["raw"]},{"text_diagnostics",diagnostics}};
        if(name=="short_event_descriptor"){
            ts::ShortEventDescriptor native(duck,binary);
            item["valid"]=native.isValid()&&textOK;item["title"]=native.event_name.toUTF8();item["text"]=native.text.toUTF8();
            variant["short_descriptions"].push_back(item);
        }else{
            ts::ExtendedEventDescriptor native(duck,binary);
            item["number"]=r.raw[offset+2]>>4;item["last_number"]=r.raw[offset+2]&15;
            item["valid"]=native.isValid()&&textOK;item["text"]=native.text.toUTF8();item["items"]=J::array();
            for(const auto& entry:native.entries)item["items"].push_back({{"description",entry.item_description.toUTF8()},{"value",entry.item.toUTF8()}});
            variant["extended_fragments"].push_back(item);
        }
    }
    J result=J::array();
    for(auto& [language,v]:byLanguage){
        v["title"]="";v["short_text"]="";v["extended_text"]=nullptr;v["items"]=J::array();
        v["missing_fragments"]=J::array();v["duplicate_fragments"]=J::array();
        v["short_status"]="absent";const auto& shorts=v["short_descriptions"];
        if(!shorts.empty()){
            bool conflict=false,invalid=false;
            for(const auto& s:shorts){invalid|=!s["valid"].get<bool>();conflict|=s["title"]!=shorts[0]["title"]||s["text"]!=shorts[0]["text"];}
            v["short_status"]=invalid?"invalid":conflict?"conflict":"complete";
            if(!invalid&&!conflict){v["title"]=shorts[0]["title"];v["short_text"]=shorts[0]["text"];}
            else v["warnings"].push_back("Short descriptions conflict or contain undecodable text; inspect each original descriptor");
        }
        const auto& fragments=v["extended_fragments"];v["extended_status"]="absent";
        if(!fragments.empty()){
            std::map<unsigned,J> parts;const unsigned last=fragments[0]["last_number"];bool conflict=false,invalid=false;
            for(const auto& f:fragments){const unsigned number=f["number"];
                invalid|=!f["valid"].get<bool>();conflict|=f["last_number"]!=last||number>last;
                auto found=parts.find(number);
                if(found!=parts.end()){v["duplicate_fragments"].push_back(number);conflict|=found->second["raw_hex"]!=f["raw_hex"];}
                else parts[number]=f;
            }
            for(unsigned n=0;n<=last;++n)if(!parts.count(n))v["missing_fragments"].push_back(n);
            const bool complete=!invalid&&!conflict&&v["missing_fragments"].empty();
            v["extended_status"]=invalid?"invalid":conflict?"conflict":complete?"complete":"incomplete";
            if(complete){std::string assembled;for(const auto& [number,f]:parts){assembled+=f["text"].get<std::string>();for(const auto& item:f["items"])v["items"].push_back(item);}v["extended_text"]=assembled;}
            else v["warnings"].push_back("Extended text is not assembled across missing, invalid or conflicting fragments");
        }
        v["assembly_scope"]="One event loop in one original EIT section; no cross-version, cross-event or cross-language stitching";
        result.push_back(v);
    }
    return result;
}
}
