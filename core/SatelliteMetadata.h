#pragma once
#include <cmath>

// Reference enrichment only. Nothing here identifies the received spacecraft.
namespace satellitemeta {
inline const char* uncertainty = "Candidate satellites only, never a confirmed identification. Co-located spacecraft may share a slot. The incomplete reference snapshot may be stale; capture-date assignments, transponders and reception are not verified.";
inline J base(const J& parameters) {
    return {{"status","insufficient_parameters"},{"confirmed_satellite",nullptr},{"raw_parameters",parameters},
        {"candidates",J::array()},{"uncertainty",uncertainty},
        {"matching",{{"basis","nominal GEO orbital position only"},{"unchecked_parameters",J::array({"frequency_hz","symbol_rate","polarization","modulation_system","modulation_type","roll_off","fec_inner","reception_location","capture_date"})}}}};
}
inline void validateParameters(const J& p) {
    auto number=[&](const char* key,double low,double high){
        if(p.contains(key)&&(!p[key].is_number()||!std::isfinite(p[key].get<double>())||p[key]<low||p[key]>high))
            throw std::runtime_error(std::string("Invalid satellite parameter: ")+key);
    };
    number("orbital_position_degrees",0,180);number("tolerance_degrees",0,1);
    number("frequency_hz",1,1000000000000.0);number("symbol_rate",1,1000000000);
    if(p.contains("direction")&&p["direction"]!="E"&&p["direction"]!="W")throw std::runtime_error("Satellite direction must be E or W");
    if(p.contains("polarization")&&p["polarization"]!="horizontal"&&p["polarization"]!="vertical"&&p["polarization"]!="left"&&p["polarization"]!="right")throw std::runtime_error("Unknown satellite polarization");
}
inline J lookup(const fs::path& root,const J& parameters) {
    validateParameters(parameters);
    J out=base(parameters);
    const auto file=root/"references"/"satellites.json";
    out["catalog"]={{"path","references/satellites.json"},{"status","unavailable"}};
    try {
        // Read a bounded, regular local file, retaining the identity of these exact bytes.
        if(!fs::is_regular_file(file))throw std::runtime_error("Satellite catalog is missing or is not a regular file");
        std::ifstream in(file,std::ios::binary);
        if(!in)throw std::runtime_error("Satellite catalog cannot be read");
        Bytes bytes;char buffer[4096];
        while(in.read(buffer,sizeof(buffer))||in.gcount()){
            bytes.insert(bytes.end(),buffer,buffer+in.gcount());
            if(bytes.size()>1024*1024)throw std::runtime_error("Satellite catalog exceeds 1 MiB");
        }
        if(in.bad())throw std::runtime_error("Satellite catalog read failed");
        out["catalog"]["fingerprint"]=fingerprint(bytes);
        out["catalog"]["fingerprint_algorithm"]="fnv1a64 (content identity, not a security hash)";
        const J catalog=J::parse(bytes);
        auto require=[](bool ok){if(!ok)throw std::runtime_error("Invalid satellite catalog schema");};
        require(catalog.is_object()&&catalog.value("schema_version",0)==1&&catalog.at("revision").is_string()&&catalog.at("entries").is_array()&&catalog["entries"].size()<=1000);
        std::set<std::string> ids;
        for(const auto& e:catalog["entries"]){
            require(e.is_object()&&e.at("id").is_string()&&e.at("name").is_string()&&!e["name"].get<std::string>().empty());
            require(ids.insert(e["id"].get<std::string>()).second);
            require(e.at("longitude_degrees_east").is_number()&&e["longitude_degrees_east"]>=-180&&e["longitude_degrees_east"]<=180);
            const auto& s=e.at("source");
            require(s.is_object()&&s.at("publisher").is_string()&&s.at("url").is_string()&&s["url"].get<std::string>().rfind("https://",0)==0&&s.at("reviewed_at").is_string());
        }
        out["catalog"].update({{"status","loaded"},{"revision",catalog["revision"]},{"entry_count",catalog["entries"].size()},{"coverage","Curated, incomplete GEO reference snapshot; not a transponder database or historical orbit service"}});
        if(!parameters.contains("orbital_position_degrees")||!parameters.contains("direction"))return out;
        const double position=parameters["orbital_position_degrees"].get<double>()*(parameters["direction"]=="W"?-1:1);
        const double tolerance=parameters.value("tolerance_degrees",0.0);
        out["matching"]["longitude_degrees_east"]=position;out["matching"]["tolerance_degrees"]=tolerance;
        for(const auto& entry:catalog["entries"]){
            const double difference=std::abs(position-entry["longitude_degrees_east"].get<double>());
            const double delta=std::min(difference,360-difference);
            if(delta>tolerance+1e-9)continue;
            J candidate=entry;
            candidate["status"]="candidate";candidate["orbital_delta_degrees"]=delta;
            candidate["match_reason"]="Nominal orbital position within the explicitly reported tolerance; no transponder identity check";
            candidate["assignment_valid_at_capture"]=nullptr;
            out["candidates"].push_back(candidate);
        }
        out["status"]=out["candidates"].empty()?"no_catalog_match":"candidates";
    }catch(const std::exception& e){
        out["status"]="catalog_unavailable";out["catalog"]["status"]="unavailable";out["catalog"]["error"]=e.what();
        out["candidates"]=J::array();
    }
    return out;
}
inline J inspect(const fs::path& root,const Record& r) {
    J result=J::array();
    for(const auto& d:r.descriptors){
        const auto native=d.value("native",J::object());
        if(!d.value("native_decoded",false)||d.value("decode_status",std::string())!="decoded"||native.value("name",std::string())!="satellite_delivery_system_descriptor")continue;
        const size_t offset=d.at("offset");
        const auto attributes=native.value("attributes",J::object());
        const auto system=attributes.value("modulation_system",std::string());
        const bool supported=system=="DVB-S"||system=="DVB-S2";
        J p=J::object();bool valid=supported&&r.valid&&d.at("length")==11&&offset+13<=r.raw.size();
        auto bcd=[&](size_t at,size_t digits){
            uint64_t value=0;
            for(size_t i=0;i<digits;i++){const unsigned digit=(r.raw[at+i/2]>>(i%2?0:4))&15;valid&=digit<=9;value=value*10+digit;}
            return value;
        };
        if(valid){
            p["frequency_hz"]=bcd(offset+2,8)*10000;
            p["orbital_position_degrees"]=double(bcd(offset+6,4))/10;
            const auto flags=r.raw[offset+8];
            p["direction"]=(flags&0x80)?"E":"W";
            p["symbol_rate"]=bcd(offset+9,7)*100;
            const char* polarizations[]={"horizontal","vertical","left","right"};
            p["polarization"]=polarizations[(flags>>5)&3];
            p["modulation_system"]=(flags&4)?"DVB-S2":"DVB-S";
            p["modulation_type_code"]=flags&3;p["roll_off_code"]=(flags>>3)&3;p["fec_inner_code"]=r.raw[offset+12]&15;
            valid&=p["orbital_position_degrees"]<=180&&p["frequency_hz"]>0&&p["symbol_rate"]>0;
        }
        J item=base(p);
        if(valid)item=lookup(root,p);else item["status"]=supported?"invalid_parameters":"unsupported_delivery_system";
        item["wire_source"]=signalmeta::evidence(r,offset);
        item["wire_source"]["section_valid"]=r.valid;
        item["raw_descriptor_hex"]=d.at("raw");item["sdk_parameters"]=attributes;
        item["transport"]=nullptr;
        for(const auto& transport:r.fields.value("transports",J::array())){
            const size_t begin=transport.at("descriptor_offset"),length=transport.at("descriptor_bytes");
            if(offset>=begin&&offset+13<=begin+length)item["transport"]=transport;
        }
        item["observation_scope"]="Advertised delivery parameters in this exact section, not proof of the physically received satellite. NIT-other/BAT can advertise other transports. S2/S2X extensions are not used for identity matching.";
        if(!valid)item["parameter_error"]=supported?"Invalid section, descriptor length, BCD digits or parameter range; no candidates inferred":"Only DVB-S/S2 descriptor layout is matched; other SDK interpretations remain in sdk_parameters and original bytes";
        result.push_back(item);
    }
    return result;
}
}
