#pragma once
#include "tsAIT.h"
#include "DsmccModules.h"
#include "tsApplicationDescriptor.h"
#include "tsApplicationNameDescriptor.h"
#include "tsSimpleApplicationLocationDescriptor.h"
#include "tsTransportProtocolDescriptor.h"
#include "tsUNT.h"
#include "tsDSMCCCompatibilityDescriptor.h"
#include "tsSSULocationDescriptor.h"
#include "tsSSUURIDescriptor.h"
#include "tsSSUEventNameDescriptor.h"
#include "tsUpdateDescriptor.h"
#include "tsSchedulingDescriptor.h"
#include "tsSSUSubgroupAssociationDescriptor.h"
#include "tsTargetSmartcardDescriptor.h"
#include "tsTargetSerialNumberDescriptor.h"
#include "tsTargetMACAddressDescriptor.h"
#include "tsTargetIPAddressDescriptor.h"
#include "tsTargetIPv6AddressDescriptor.h"

// Read-only, bounded AIT/UNT source cards. Typed SDK descriptors provide values;
// bounded wire loops provide provenance, never offsets into merged XML.
namespace applicationsignalling {
inline unsigned word(const Bytes& b,size_t p){return unsigned(b.at(p))<<8|b.at(p+1);}
inline std::string decimal(uint64_t value){return std::to_string(value);}
inline std::string hexid(unsigned value){std::ostringstream out;out<<"0x"<<std::hex<<std::uppercase<<std::setfill('0')<<std::setw(4)<<value;return out.str();}
class Builder {
    static constexpr size_t MaxObjects=4096,MaxRelations=8192;
    ts::DuckContext& duck;
    const std::vector<const Record*>& parts;
    const std::vector<Record>* capture;
    size_t revision;uint64_t cutoff;std::string profile;
    std::map<std::string,J> objects;
    J relations=J::array(),diagnostics=J::array();
    std::map<std::string,std::map<std::string,J>> anchors;
    struct Transport {std::string id,parent;unsigned label;J evidence;bool supported;};
    struct Reference {std::string application;unsigned label;J evidence;};
    std::vector<Transport> transports;
    std::vector<Reference> references;
    std::map<std::string,size_t> identities;
    J evidence(const Record& r,size_t offset,size_t length,const std::string& key,bool field=false){
        if(!length||offset+length>r.raw.size())throw std::runtime_error("Application evidence range exceeds original section");
        const std::string token=r.id+":application-evidence:"+decimal(offset)+":"+decimal(length)+":"+key;
        J locator={{"field_id",field?J(token):J()},{"container_id",token},{"precision",field?"field":"container"},{"resolution_status","resolved"},
            {"byte_range",{{"offset_scope","section_bytes"},{"offset",offset},{"length",length}}},{"display_path",key}};
        J anchor=locator;anchor["label"]=key;anchors[r.id][token]=anchor;
        return {{"analysis_revision",revision},{"at_packet",cutoff},{"section_id",r.id},
            {"table_identity",{{"pid",r.pid},{"table_id",r.tid},{"extension",r.ext},{"version",r.version},{"section_number",r.number},{"current",r.current}}},
            {"assertion_key",key},{"role","declares"},{"locator",locator}};
    }
    J& object(const std::string& id,const std::string& kind,const std::string& label,const std::string& parent,const J& identity,const J& e){
        if(objects.size()>=MaxObjects)throw std::runtime_error("Application summary object limit exceeded (4096)");
        objects[id]={{"node_id",id},{"family","dvb"},{"object_type",kind},{"identity",identity},{"label",label},{"parent_id",parent.empty()?J():J(parent)},
            {"attributes",J::object()},{"attribute_conflicts",J::object()},{"observation_status","announced_only"},{"resolution_status","resolved"},{"unresolved_reasons",J::array()},{"evidence",J::array({e})}};
        return objects.at(id);
    }
    void reason(J& n,const std::string& text,const std::string& status="unresolved"){
        if(n["resolution_status"]!="conflict"||status=="conflict")n["resolution_status"]=status;n["unresolved_reasons"].push_back(text);
    }
    void relation(const std::string& from,const std::string& to,const std::string& name,const J& e,const std::string& status="resolved"){
        if(relations.size()>=MaxRelations)throw std::runtime_error("Application summary relation limit exceeded (8192)");
        relations.push_back({{"edge_id",from+":"+name+":"+to+":"+decimal(relations.size())},{"from",from},{"to",to},{"relation",name},{"resolution_status",status},{"evidence",e}});
    }
    void descriptors(const Record& r,size_t begin,size_t end,const std::string& parent,const std::string& application){
        size_t properties=0;
        for(size_t p=begin;p<end;){
            if(p+2>end||p+2+r.raw[p+1]>end)throw std::runtime_error("AIT descriptor exceeds its original loop");
            const size_t size=2+r.raw[p+1];const unsigned tag=r.raw[p];
            const std::string id=parent+":descriptor:"+r.id+":"+decimal(p);
            auto e=evidence(r,p,size,"AIT descriptor "+decimal(tag));
            ts::Descriptor bin(r.raw.data()+p,size);
            std::string kind="application_descriptor_reference",label="Unsupported application descriptor";J attrs={{"descriptor_tag",tag},{"raw_hex",hex(Bytes(r.raw.begin()+p,r.raw.begin()+p+size))},{"scope",application.empty()?"common_subtable":"application_local"}};
            bool valid=true,supported=true;
            if(tag==2){
                kind="application_transport";label="Application transport";ts::TransportProtocolDescriptor value(duck,bin);valid=value.isValid();
                if(valid){
                    attrs["protocol_id"]=value.protocol_id;attrs["transport_protocol_label"]=value.transport_protocol_label;
                    attrs["fetch_status"]="not_requested";attrs["execution_status"]="not_executed";
                    if(value.protocol_id==3){J urls=J::array();for(const auto& entry:value.http){J extensions=J::array();for(const auto& ext:entry.URL_extensions)extensions.push_back(ext.toUTF8());urls.push_back({{"base",entry.URL_base.toUTF8()},{"extensions",extensions}});}attrs["http_locations"]=urls;}
                    else if(value.protocol_id==1){auto optional=[](const auto& v)->J{return v.has_value()?J(*v):J();};attrs["object_carousel"]={{"original_network_id",optional(value.carousel.original_network_id)},{"transport_stream_id",optional(value.carousel.transport_stream_id)},{"service_id",optional(value.carousel.service_id)},{"component_tag",value.carousel.component_tag},{"module_reconstruction","unsupported"}};}
                    else{supported=false;attrs["selector_hex"]=hex(Bytes(r.raw.begin()+p+5,r.raw.begin()+p+size));}
                    transports.push_back({id,application,value.transport_protocol_label,e,supported});
                }
            }else if(tag==0&&!application.empty()){
                kind="application_properties";label="Application properties";ts::ApplicationDescriptor value(duck,bin);valid=value.isValid();++properties;
                if(valid){J profiles=J::array(),labels=J::array();for(const auto& item:value.profiles)profiles.push_back({{"application_profile",item.application_profile},{"version",J::array({item.version_major,item.version_minor,item.version_micro})}});
                    for(auto transport:value.transport_protocol_labels){labels.push_back(transport);references.push_back({application,transport,e});}
                    if(labels.empty())reason(objects.at(application),"No transport protocol labels advertised; delivery relation unresolved");
                    attrs.update({{"profiles",profiles},{"service_bound",value.service_bound},{"visibility",value.visibility},{"application_priority",value.application_priority},{"transport_protocol_labels",labels}});
                }
            }else if(tag==1&&!application.empty()){
                kind="application_name";label="Application names";ts::ApplicationNameDescriptor value(duck,bin);valid=value.isValid();
                if(valid){J names=J::array();for(const auto& entry:value.entries)names.push_back({{"language",entry.language.toUTF8()},{"name",entry.name.toUTF8()}});attrs["names"]=names;}
            }else if(tag==0x15&&!application.empty()){
                kind="application_location";label="Application initial path";ts::SimpleApplicationLocationDescriptor value(duck,bin);valid=value.isValid();
                if(valid){attrs["initial_path"]=value.initial_path.toUTF8();attrs["resolved_url"]=nullptr;attrs["fetch_status"]="not_requested";}
            }else supported=false;
            auto& n=object(id,kind,label,parent,{{"descriptor_section_id",r.id},{"descriptor_offset",p}},e);n["attributes"]=attrs;
            if(!valid){reason(n,"Known AIT descriptor failed SDK parsing; original bytes retained");if(!application.empty())reason(objects.at(application),"Malformed application descriptor retained as raw evidence");}
            else if(!supported)reason(n,"Descriptor or transport protocol semantics outside the bounded application summary");
            relation(parent,id,"contains",J::array({e}),n["resolution_status"]);p+=size;
        }
        if(!application.empty()&&properties!=1)reason(objects.at(application),properties?"Multiple application_descriptor declarations retained":"Required application_descriptor not observed",properties?"conflict":"unresolved");
    }
    struct UpdateLocation {std::string id;J evidence;bool supported;};
    std::vector<UpdateLocation> updateDescriptors(const Record& r,size_t begin,size_t end,const std::string& parent,const std::string& scope){
        std::vector<UpdateLocation> locations;
        for(size_t p=begin;p<end;){
            if(p+2>end||p+2+r.raw[p+1]>end)throw std::runtime_error("UNT descriptor exceeds original loop");
            const size_t size=2+r.raw[p+1];const unsigned tag=r.raw[p];const std::string id=parent+":descriptor:"+decimal(p);auto e=evidence(r,p,size,"UNT "+scope+" descriptor "+decimal(tag));ts::Descriptor bin(r.raw.data()+p,size);
            std::string kind="update_descriptor_reference",label="Unsupported update descriptor";J attrs={{"descriptor_tag",tag},{"raw_hex",hex(Bytes(r.raw.begin()+p,r.raw.begin()+p+size))},{"scope",scope}};bool valid=true,supported=true;const bool target=scope=="target";
            if(tag==3&&!target){kind="update_transport_reference";label="SSU carousel reference";ts::SSULocationDescriptor value(duck,bin);valid=value.isValid();if(valid){attrs.update({{"data_broadcast_id",value.data_broadcast_id},{"association_tag",value.data_broadcast_id==10?J(value.association_tag):J()},{"private_data_hex",hex(value.private_data)},{"component_pid",nullptr},{"association_resolution_status","unresolved"}});supported=value.data_broadcast_id==10;}}
            else if(tag==0x0d&&!target){kind="update_uri";label="SSU URI declaration";ts::SSUURIDescriptor value(duck,bin);valid=value.isValid();if(valid)attrs.update({{"uri",value.uri.toUTF8()},{"max_holdoff_minutes",value.max_holdoff_time},{"min_polling_interval_hours",value.min_polling_interval},{"fetch_status","not_requested"},{"installation_status","not_requested"}});}
            else if(tag==2&&!target){kind="update_advice";label="Update advice";ts::UpdateDescriptor value(duck,bin);valid=value.isValid();if(valid)attrs.update({{"update_flag_code",value.update_flag},{"update_method_code",value.update_method},{"update_priority",value.update_priority},{"private_data_hex",hex(value.private_data)},{"action_taken",false}});}
            else if(tag==5&&!target){kind="update_name";label="Update event name";ts::SSUEventNameDescriptor value(duck,bin);valid=value.isValid();if(valid)attrs.update({{"language",value.ISO_639_language_code.toUTF8()},{"name",value.name.toUTF8()},{"text",value.text.toUTF8()}});}
            else if(tag==1&&!target){kind="update_schedule";label="Update schedule declaration";ts::SchedulingDescriptor value(duck,bin);valid=value.isValid();if(valid){attrs.update({{"start_date_time",value.start_date_time.toString().toUTF8()},{"end_date_time",value.end_date_time.toString().toUTF8()},{"final_availability",value.final_availability},{"periodicity",value.periodicity},{"period",value.period},{"period_unit_code",value.period_unit},{"duration",value.duration},{"duration_unit_code",value.duration_unit},{"estimated_cycle_time",value.estimated_cycle_time},{"estimated_cycle_time_unit_code",value.estimated_cycle_time_unit},{"private_data_hex",hex(value.private_data)},{"available_now",nullptr}});valid=value.start_date_time<=value.end_date_time;}}
            else if(tag==0x0b&&scope=="operational"){kind="update_subgroup_reference";label="SSU subgroup reference";ts::SSUSubgroupAssociationDescriptor value(duck,bin);valid=value.isValid();if(valid)attrs.update({{"subgroup_tag",value.subgroup_tag},{"defining_oui",value.subgroup_tag>>16},{"subgroup_id",value.subgroup_tag&65535},{"carousel_group",nullptr}});}
            else if(tag==6&&target){kind="update_target_selector";label="Smartcard target declaration";ts::TargetSmartcardDescriptor value(duck,bin);valid=value.isValid();if(valid)attrs.update({{"super_ca_system_id",value.super_CA_system_id},{"private_data_hex",hex(value.private_data)},{"device_match",nullptr}});}
            else if(tag==8&&target){kind="update_target_selector";label="Serial target declaration";ts::TargetSerialNumberDescriptor value(duck,bin);valid=value.isValid();if(valid)attrs.update({{"serial_data_hex",hex(value.serial_data)},{"selector_semantics","manufacturer defined; not interpreted"},{"device_match",nullptr}});}
            else if(tag==7&&target){kind="update_target_selector";label="MAC target declaration";ts::TargetMACAddressDescriptor value(duck,bin);valid=value.isValid();if(valid){J matches=J::array();for(const auto& address:value.MAC_addr)matches.push_back(address.toString().toUTF8());attrs.update({{"mask",value.MAC_addr_mask.toString().toUTF8()},{"matches",matches},{"device_match",nullptr}});}}
            else if(tag==9&&target){kind="update_target_selector";label="IPv4 target declaration";ts::TargetIPAddressDescriptor value(duck,bin);valid=value.isValid();if(valid){J matches=J::array();for(const auto& address:value.IPv4_addr)matches.push_back(address.toString().toUTF8());attrs.update({{"mask",value.IPv4_addr_mask.toString().toUTF8()},{"matches",matches},{"device_match",nullptr}});}}
            else if(tag==10&&target){kind="update_target_selector";label="IPv6 target declaration";ts::TargetIPv6AddressDescriptor value(duck,bin);valid=value.isValid();if(valid){J matches=J::array();for(const auto& address:value.IPv6_addr)matches.push_back(address.toString().toUTF8());attrs.update({{"mask",value.IPv6_addr_mask.toString().toUTF8()},{"matches",matches},{"device_match",nullptr}});}}
            else supported=false;
            auto& n=object(id,kind,label,parent,{{"descriptor_section_id",r.id},{"descriptor_offset",p}},e);n["attributes"]=attrs;
            if(!valid)reason(n,"Malformed UNT descriptor or impossible scheduling range; original bytes retained");else if(!supported)reason(n,"Unsupported/private descriptor or invalid descriptor-loop context; no target or transport inferred");
            if(valid&&tag==3&&!target)reason(n,"Association tag is announced; PMT/component mapping and carousel data are not resolved");
            if(valid&&tag==0x0b&&scope=="operational")reason(n,"Subgroup declaration is not joined to a reconstructed carousel group");
            relation(parent,id,"contains",J::array({e}),n["resolution_status"]);
            if(!target&&(tag==3||tag==0x0d||tag==0x57))locations.push_back({id,e,valid&&supported});p+=size;
        }
        return locations;
    }
    static void validateCompatibility(const Bytes& b,size_t begin,size_t end){
        size_t p=begin+2;
        if(p==end)return; // Zero compatibility length has no count field.
        if(p+2>end)throw std::runtime_error("Compatibility descriptor count is truncated");
        const unsigned count=word(b,p);p+=2;
        for(unsigned i=0;i<count;++i){
            if(p+11>end||b[p+1]<9||p+2+b[p+1]>end)throw std::runtime_error("Compatibility descriptor count or length exceeds original structure");
            const size_t next=p+2+b[p+1];const unsigned subCount=b[p+10];size_t sub=p+11;
            for(unsigned j=0;j<subCount;++j){
                if(sub+2>next||sub+2+b[sub+1]>next)throw std::runtime_error("Compatibility sub-descriptor count or length exceeds original descriptor");
                sub+=2+b[sub+1];
            }
            if(sub!=next)throw std::runtime_error("Compatibility sub-descriptor count leaves unclaimed bytes");p=next;
        }
        if(p!=end)throw std::runtime_error("Compatibility descriptor count leaves unclaimed bytes");
    }
    void unt(){
        ts::BinaryTable binary;std::optional<uint32_t> fullOui;
        for(const auto* r:parts){
            if(r->raw.size()<18)throw std::runtime_error("UNT header truncated");const auto& b=r->raw;const uint32_t oui=uint32_t(b[8])<<16|word(b,9);
            if(b[4]!=(b[8]^b[9]^b[10]))throw std::runtime_error("UNT OUI hash disagrees with full 24-bit OUI; no device groups merged");
            if(fullOui&&*fullOui!=oui)throw std::runtime_error("UNT hash collision: selected sections have different full 24-bit OUIs; no device groups merged");fullOui=oui;
            if(b[3]!=1)throw std::runtime_error("UNT action type outside supported System Software Update action; raw evidence retained");
            binary.addNewSection(b.data(),b.size(),ts::PID(r->pid),ts::CRC32::CHECK);
        }
        ts::UNT typed(duck,binary);if(!typed.isValid())throw std::runtime_error("Selected UNT failed SDK validation");
        size_t deviceCount=0;
        for(const auto* r:parts){
            const auto& b=r->raw;const size_t end=b.size()-4;const std::string context="unt:"+r->id;auto ce=evidence(*r,8,4,"UNT OUI and processing order");
            auto& table=object(context,"update_notification","System software update notification",{},{{"pid",r->pid},{"oui",*fullOui},{"action_type",b[3]},{"version",r->version},{"section_number",r->number},{"current",r->current}},ce);
            table["attributes"]={{"processing_order",b[11]},{"device_match",nullptr},{"firmware_suitability",nullptr},{"installation_status","not_requested"},{"common_descriptor_scope","this original section only"}};
            table["evidence"].push_back(evidence(*r,8,3,"OUI",true));table["evidence"].push_back(evidence(*r,11,1,"processing_order",true));
            const size_t commonEnd=14+(word(b,12)&4095);if(commonEnd>end)throw std::runtime_error("UNT common descriptors exceed section");auto commonLocations=updateDescriptors(*r,14,commonEnd,context,"common");
            for(size_t p=commonEnd;p<end;){
                if(p+2>end)throw std::runtime_error("UNT compatibility length truncated");const size_t compatibilityEnd=p+2+word(b,p);if(compatibilityEnd+2>end)throw std::runtime_error("UNT compatibility exceeds section");
                validateCompatibility(b,p,compatibilityEnd);
                ts::DSMCCCompatibilityDescriptor compatibility;ts::PSIBuffer buffer(duck,b.data()+p,compatibilityEnd-p);compatibility.deserialize(buffer);if(buffer.error()||!buffer.endOfRead())throw std::runtime_error("UNT compatibility structure failed bounded SDK parsing");
                J selectors=J::array();bool unknownCompatibility=false;
                for(const auto& d:compatibility.descs){J sub=J::array();for(const auto& v:d.subdescs)sub.push_back({{"sub_descriptor_type",v.subDescriptorType},{"additional_information_hex",hex(v.additionalInformation)}});selectors.push_back({{"descriptor_type",d.descriptorType},{"specifier_type",d.specifierType},{"specifier_data",d.specifierData},{"model",d.model},{"version",d.version},{"sub_descriptors",sub}});unknownCompatibility|=d.descriptorType>2||d.specifierType!=1||!d.subdescs.empty();}
                const std::string did=context+":devices:"+decimal(p);auto de=evidence(*r,p,compatibilityEnd-p,"Device compatibility declaration");auto& device=object(did,"update_device_compatibility","Device compatibility declaration",context,{{"section_id",r->id},{"loop_offset",p}},de);device["attributes"]={{"selectors",selectors},{"device_match",nullptr},{"match_status","not_evaluated"},{"private_selector_semantics","opaque"}};
                if(unknownCompatibility)reason(device,"Private or unsupported compatibility selectors retained; device eligibility not evaluated");relation(context,did,"announces",J::array({ce,de}));++deviceCount;
                const size_t platformEnd=compatibilityEnd+2+word(b,compatibilityEnd);if(platformEnd>end)throw std::runtime_error("UNT platform loop exceeds section");size_t platforms=0;
                for(size_t q=compatibilityEnd+2;q<platformEnd;){
                    if(q+2>platformEnd)throw std::runtime_error("UNT target length truncated");const size_t targetEnd=q+2+(word(b,q)&4095);if(targetEnd+2>platformEnd)throw std::runtime_error("UNT target loop exceeds platform");const size_t operationalEnd=targetEnd+2+(word(b,targetEnd)&4095);if(operationalEnd>platformEnd)throw std::runtime_error("UNT operational loop exceeds platform");
                    const std::string pid=did+":platform:"+decimal(q);auto pe=evidence(*r,q,operationalEnd-q,"Target and operational loops");auto& platform=object(pid,"update_target","Update targeting and operations",did,{{"section_id",r->id},{"loop_offset",q}},pe);
                    platform["attributes"]={{"targeting_scope",targetEnd==q+2?"all devices matching compatibility declaration":"explicit target selectors"},{"device_match",nullptr},{"firmware_suitability",nullptr},{"installation_status","not_requested"}};relation(did,pid,"contains",J::array({de,pe}));
                    updateDescriptors(*r,q+2,targetEnd,pid,"target");auto operational=updateDescriptors(*r,targetEnd+2,operationalEnd,pid,"operational");const auto& applicable=operational.empty()?commonLocations:operational;
                    platform["attributes"]["location_scope"]=operational.empty()?"same-section common":"operational overrides same-section common";
                    platform["attributes"]["location_resolution_status"]=applicable.empty()?"missing":applicable.size()>1?"conflict":applicable[0].supported?"declared":"unresolved";
                    if(applicable.empty())reason(platform,"No supported location declaration in this operational loop or its own section common loop");
                    if(applicable.size()>1)reason(platform,"Multiple location declarations retained; no transport or URI selected","conflict");
                    if(applicable.size()==1&&!applicable[0].supported)reason(platform,"Location declaration is malformed or unsupported; no usable transport selected");
                    for(const auto& location:applicable)relation(pid,location.id,"references",J::array({pe,location.evidence}),applicable.size()>1?"conflict":location.supported?"resolved":"unresolved");
                    if(!operational.empty())for(const auto& local:operational)for(const auto& common:commonLocations)relation(local.id,common.id,"overrides",J::array({local.evidence,common.evidence}),local.supported&&common.supported?"resolved":"unresolved");
                    q=operationalEnd;++platforms;
                }
                if(!platforms)reason(device,"No target/operational platform loop observed");p=platformEnd;
            }
        }
        // TS 102 006 Annex C.1 requires compatibility at sub-table scope,
        // while common descriptors still apply only to their own section.
        if(!deviceCount)for(auto& [id,n]:objects)if(n["object_type"]=="update_notification")reason(n,"No device compatibility declaration observed in selected UNT sub-table");
    }
    J dsmcc(J out,const Record& r,bool tableComplete){
        // A generic original payload anchor remains navigable for malformed
        // messages that can block reconstruction without yielding semantic cards.
        J source; if(r.raw.size()>12)source=evidence(r,8,r.raw.size()-12,"DSM-CC message payload");
        const auto message=dsmccsignalling::parse(duck,r);
        if(!message.valid){out["status"]=message.status;out["diagnostics"].push_back(message.diagnostic);for(const auto& [id,a]:anchors[r.id])out["evidence_anchors"].push_back(a);return out;}
        const std::string context="dsmcc:"+r.id;
        J identity={{"pid",r.pid},{"download_id",message.downloadId},{"section_version",r.version},{"current",r.current}};
        if(message.ddb)identity.update({{"module_id",message.moduleId},{"module_version",message.moduleVersion},{"block_number",message.blockNumber}});
        else identity["transaction_id"]=message.transactionId;
        auto& root=object(context,message.ddb?"download_data_block":"download_information",message.ddb?"DSM-CC data block":"DSM-CC download information",{},identity,source);
        root["observation_status"]="observed";
        root["attributes"]={{"message_decode_status","decoded exact original section"},{"section_number",r.number},{"last_section_number",r.last},{"native_table_complete",tableComplete},{"protocol_discriminator",17},{"dsmcc_type",3},{"message_id",message.ddb?0x1003:0x1002},{"module_reconstruction","bounded_same_pid_snapshot"},{"decompression_status","not_requested"},{"execution_status","not_executed"}};
        auto field=[&](J& node,size_t p,size_t n,const std::string& label){node["evidence"].push_back(evidence(r,p,n,label,true));};
        field(root,10,2,"DSM-CC message_id");field(root,message.ddb?12:20,4,"DSM-CC download_id");
        if(message.ddb){
            root["attributes"]["data_length_bytes"]=message.dataLength;root["attributes"]["assembled_sha256"]=nullptr;
            field(root,20,2,"DDB module_id");field(root,22,1,"DDB module_version");field(root,24,2,"DDB block_number");
            if(message.dataLength)root["evidence"].push_back(evidence(r,message.dataOffset,message.dataLength,"DDB original block data"));

        }else{
            root["attributes"].update({{"block_size_bytes",message.blockSize},{"declared_module_count",message.modules.size()},{"compatibility_hex",hex(Bytes(r.raw.begin()+message.compatibilityOffset,r.raw.begin()+message.compatibilityOffset+message.compatibilityLength))},{"device_match",nullptr}});
            field(root,12,4,"DII transaction_id");field(root,24,2,"DII block_size");
            std::map<unsigned,size_t> counts;for(const auto& m:message.modules)++counts[m.id];
            for(const auto& m:message.modules){
                const std::string id=context+":module:"+decimal(m.offset);auto e=evidence(r,m.offset,m.length,"DII module declaration");
                auto& node=object(id,"download_module_announcement","DSM-CC module "+hexid(m.id),context,{{"pid",r.pid},{"download_id",message.downloadId},{"module_id",m.id},{"module_version",m.version}},e);
                node["attributes"]={{"declared_size_bytes",m.size},{"block_size_bytes",message.blockSize},{"module_info_hex",hex(Bytes(r.raw.begin()+m.infoOffset,r.raw.begin()+m.infoOffset+m.infoLength))},{"module_info_interpretation","opaque; SDK structural validation only"},{"assembly_status","announcement_only"},{"assembled_sha256",nullptr},{"decompression_status","not_requested"},{"execution_status","not_executed"}};
                field(node,m.offset,2,"DII module_id");field(node,m.offset+2,4,"DII module_size");field(node,m.offset+6,1,"DII module_version");
                if(counts[m.id]>1)reason(node,"Duplicate module identifier in one DII; no declaration selected","conflict");
                if(!message.blockSize)reason(node,"DII block size is zero; no default size substituted");
                relation(context,id,"announces",J::array({source,e}),node["resolution_status"]);
            }
        }
        if(capture&&r.current){
            const auto snapshot=dsmccsignalling::reconstruct(duck,*capture,r.pid,message.downloadId,cutoff);
            out["module_snapshot"]={{"status",snapshot.status},{"scope","Same PID/download, current announcements only; no withdrawal from partial DII"},{"orphan_block_observations",snapshot.orphanBlocks},{"invalid_message_observations",snapshot.invalidMessages},{"processed_observations",snapshot.observations},
                {"limits",{{"module_bytes",dsmccsignalling::MaxModuleBytes},{"snapshot_bytes",dsmccsignalling::MaxSnapshotBytes},{"module_sources",dsmccsignalling::MaxModuleSources},{"snapshot_source_associations",dsmccsignalling::MaxSnapshotSources},{"module_count",dsmccsignalling::MaxModules},{"capture_records",dsmccsignalling::MaxRecordScan},{"message_variants",dsmccsignalling::MaxVariants},{"message_occurrences",dsmccsignalling::MaxObservations},{"declaration_occurrence_work",dsmccsignalling::MaxDeclarationVisits},{"unique_declarations",4096}}}};
            for(const auto& diagnostic:snapshot.diagnostics)out["diagnostics"].push_back(diagnostic);
            for(const auto& [moduleId,state]:snapshot.modules){
                const std::string id="dsmcc-module:"+decimal(revision)+":"+decimal(r.pid)+":"+decimal(message.downloadId)+":"+decimal(moduleId)+":"+decimal(state.version)+":"+decimal(state.epochOrder);
                J evidenceSet=J::array();for(const auto& [sid,occurrence]:state.sources){
                    const auto& part=*occurrence.record;auto e=evidence(part,8,part.raw.size()-12,"DSM-CC message payload");
                    e["occurrence"]={{"completion_packet",occurrence.packet},{"completion_order",occurrence.order}};e["role"]=part.tid==0x3c?"block_evidence":"announcement_evidence";evidenceSet.push_back(e);
                }
                if(evidenceSet.empty())continue;
                auto& module=object(id,"download_module","Captured DSM-CC module "+hexid(moduleId),context,{{"analysis_revision",revision},{"pid",r.pid},{"download_id",message.downloadId},{"module_id",moduleId},{"module_version",state.version},{"announcement_epoch_order",state.epochOrder},{"announcement_epoch_packet",state.epochPacket}},evidenceSet.at(0));
                const std::string status=snapshot.status=="resource_limit"?"resource_limit":state.status;
                module["evidence"]=evidenceSet;module["observation_status"]=state.blocks.empty()?"announced_only":"observed";
                module["attributes"]={{"assembly_status",status},{"declared_size_bytes",state.size},{"block_size_bytes",state.blockSize},{"expected_block_count",state.blockSize?J((uint64_t(state.size)+state.blockSize-1)/state.blockSize):J()},{"received_block_count",state.blocks.size()},{"block_count_scope","Accepted blocks within reconstruction limits; not total captured DDB count"},{"duplicate_block_observations",state.duplicateObservations},{"contributing_source_count",state.sources.size()},{"module_version_candidates",state.versionCandidates},{"assembled_sha256",status=="complete"?J(state.sha256):J()},{"module_info_hex",hex(state.info)},{"decompression_status","not_requested"},{"execution_status","not_executed"},{"verification_scope","Captured bytes from CRC-valid sections; announced size, exact block coverage and lengths; optional module checksums/signatures are not evaluated"}};
                if(status!="complete"){for(const auto& why:state.reasons)reason(module,why,status=="conflict"?"conflict":"unresolved");if(state.reasons.empty()||snapshot.status=="resource_limit")reason(module,snapshot.status=="resource_limit"?"Snapshot resource limit prevents reconstruction":"Module is not completely verified");}
                relation(context,id,state.sources.count(r.id)?"contributes_to":"snapshot_context",J::array({source,evidenceSet.at(0)}),module["resolution_status"]);
            }
            if(message.ddb){auto found=snapshot.modules.find(message.moduleId);if(found==snapshot.modules.end()||!found->second.sources.count(r.id))reason(root,"Block is not a contributing observation in the current announcement epoch");}
            out=finish(out,r);if(snapshot.status=="resource_limit")out["status"]="resource_limit";return out;
        }
        if(!r.current){out["module_snapshot"]={{"status","unsupported_next"},{"scope","Current announcements only"}};reason(root,"Next-table source is retained but not used for current module reconstruction");}
        return finish(out,r);
    }
    J finish(J out,const Record& inspected){
        bool unresolved=false;for(const auto& [id,n]:objects){out["objects"].push_back(n);unresolved|=n["resolution_status"]!="resolved";}out["relations"]=relations;out["status"]=unresolved?"incomplete":"ok";
        for(const auto& [id,anchor]:anchors[inspected.id])out["evidence_anchors"].push_back(anchor);return out;
    }
public:
    Builder(ts::DuckContext& context,const std::vector<const Record*>& selected,size_t rev,uint64_t at,std::string standard,const std::vector<Record>* all=nullptr):duck(context),parts(selected),capture(all),revision(rev),cutoff(at),profile(std::move(standard)){}
    J build(const Record& inspected,bool complete,const std::string& decodeStatus){
        J out={{"schema_version",1},{"analysis_revision",revision},{"at_packet",cutoff},{"interpretation_profile",profile},{"status","unresolved"},
            {"objects",J::array()},{"relations",J::array()},{"diagnostics",J::array()},{"evidence_anchors",J::array()},
            {"scope","Read-only signalling declarations; no application download, URL fetch, browser execution or software installation"},
            {"unsupported_relations",J::array({"PMT/service ownership and component-tag resolution","Cross-PID DSM-CC association, object reconstruction, decompression and execution","HbbTV runtime conformance and application execution","Device eligibility/private selector evaluation and firmware installation"})}};
        if(profile!="dvb"){out["status"]="unsupported_profile";out["diagnostics"].push_back("Explicit DVB interpretation required for application/update/carousel summary semantics");return out;}
        if(inspected.tid==0x3b||inspected.tid==0x3c){try{return dsmcc(out,inspected,complete);}catch(const std::exception& error){out["status"]="unresolved";out["diagnostics"].push_back(error.what());return out;}}
        if(!inspected.valid||!complete||decodeStatus!="native TSDuck decoder"){out["status"]=!inspected.valid?"invalid":!complete?"incomplete_or_superseded":"malformed";out["diagnostics"].push_back("A valid, complete selected AIT/UNT generation is required; original inspection evidence retained");return out;}
        try{
            if(inspected.tid==0x4b){unt();return finish(out,inspected);}
            ts::BinaryTable binary;for(const auto* r:parts)binary.addNewSection(r->raw.data(),r->raw.size(),ts::PID(r->pid),ts::CRC32::CHECK);
            ts::AIT typed(duck,binary);if(!typed.isValid())throw std::runtime_error("Selected AIT failed SDK validation");
            const std::string context="ait:"+decimal(inspected.pid)+":"+decimal(inspected.ext)+":"+decimal(inspected.version);
            auto& table=object(context,"application_signalling","Application signalling",{},{{"pid",inspected.pid},{"application_type",typed.application_type},{"test_application_flag",typed.test_application_flag},{"version",inspected.version},{"current",inspected.current}},evidence(*parts.at(0),3,2,"AIT application type and test flag",true));
            table["attributes"]={{"execution_status","not_executed"},{"current_next",inspected.current}};
            for(const auto* r:parts){
                const auto& b=r->raw;const size_t end=b.size()-4;if(end<12)throw std::runtime_error("AIT common loop header truncated");
                const size_t commonEnd=10+(word(b,8)&4095);if(commonEnd+2>end)throw std::runtime_error("AIT common loop exceeds section");
                descriptors(*r,10,commonEnd,context,{});
                const size_t appEnd=commonEnd+2+(word(b,commonEnd)&4095);if(appEnd!=end)throw std::runtime_error("AIT application loop length disagrees with section");
                for(size_t p=commonEnd+2;p<appEnd;){
                    if(p+9>appEnd)throw std::runtime_error("AIT application header truncated");const size_t next=p+9+(word(b,p+7)&4095);if(next>appEnd)throw std::runtime_error("AIT application descriptors exceed loop");
                    const uint32_t org=uint32_t(word(b,p))<<16|word(b,p+2);const unsigned app=word(b,p+4);
                    const std::string identity=decimal(org)+":"+decimal(app),id=context+":application:"+identity+":"+r->id+":"+decimal(p);
                    auto e=evidence(*r,p,9,"Application header");auto& n=object(id,"application","Application "+hexid(app),context,{{"organization_id",org},{"application_id",app},{"ait_context",context}},e);
                    n["attributes"]={{"control_code",b[p+6]},{"execution_status","not_executed"},{"control_code_semantics","application-type dependent; no lifecycle action performed"}};identities[identity]++;
                    n["evidence"].push_back(evidence(*r,p,4,"organization_id",true));n["evidence"].push_back(evidence(*r,p+4,2,"application_id",true));n["evidence"].push_back(evidence(*r,p+6,1,"application_control_code",true));
                    relation(context,id,"announces",J::array({e}));descriptors(*r,p+9,next,id,id);p=next;
                }
            }
            for(auto& [id,n]:objects)if(n["object_type"]=="application"){
                const std::string identity=decimal(n["identity"]["organization_id"].get<unsigned>())+":"+decimal(n["identity"]["application_id"].get<unsigned>());
                if(identities.at(identity)>1)reason(n,"Duplicate application identifier; each wire observation retained","conflict");
            }
            for(const auto& ref:references){
                std::vector<const Transport*> found;for(const auto& t:transports)if(t.label==ref.label&&(t.parent.empty()||t.parent==ref.application))found.push_back(&t);
                if(found.empty()){
                    const std::string id=ref.application+":unresolved-transport:"+decimal(ref.label)+":"+decimal(relations.size());auto& n=object(id,"application_transport_reference","Missing transport label "+decimal(ref.label),ref.application,{{"transport_protocol_label",ref.label}},ref.evidence);reason(n,"No matching common or application-local transport descriptor in the selected AIT");reason(objects.at(ref.application),"Referenced transport label is missing");relation(ref.application,id,"references",J::array({ref.evidence}),"unresolved");
                }else for(const auto* t:found){const std::string status=found.size()>1?"conflict":t->supported?"resolved":"unresolved";relation(ref.application,t->id,"maps_to",J::array({ref.evidence,t->evidence}),status);if(status!="resolved")reason(objects.at(ref.application),found.size()>1?"Transport label matches multiple declarations; no transport selected":"Referenced transport protocol semantics unsupported",status);}
            }
            return finish(out,inspected);
        }catch(const std::exception& error){out["status"]="unresolved";out["objects"]=J::array();out["relations"]=J::array();out["diagnostics"].push_back(error.what());}
        return out;
    }
};
}
