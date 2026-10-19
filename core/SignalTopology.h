#pragma once
#include "tsTVCT.h"
#include "tsCVCT.h"
#include "tsTSInformationDescriptor.h"
#include "tsPartialReceptionDescriptor.h"
#include "tsCableDeliverySystemDescriptor.h"
#include "tsTerrestrialDeliverySystemDescriptor.h"

// Read-only semantic projection. Inputs are the engine's already selected,
// complete, valid-current generations. No XML tree or display name is a key.
namespace topology {
constexpr size_t MaxNodes=20000, MaxEdges=40000, MaxEvidence=200000;
inline std::string num(unsigned n){return std::to_string(n);}
inline std::string hexid(unsigned n,unsigned width=4){std::ostringstream s;s<<"0x"<<std::hex<<std::uppercase<<std::setfill('0')<<std::setw(width)<<n;return s.str();}
inline J locator(const Record& r,const std::string& key,size_t offset=SIZE_MAX,size_t length=0,size_t container=SIZE_MAX,const std::string& precision="field") {
    const bool bounded=offset!=SIZE_MAX&&length&&offset<=r.raw.size()&&length<=r.raw.size()-offset;
    const std::string anchor=r.id+"@"+num(unsigned(bounded?offset:0));
    return {{"field_id",bounded&&precision=="field"?J(anchor+"/"+key):J()},
        {"container_id",bounded?J(r.id+"@"+num(unsigned(container==SIZE_MAX?offset:container))+"/container"):J()},
        {"precision",bounded?precision:"section"},{"resolution_status",bounded?"resolved":"unsupported"},
        {"byte_range",bounded?J{{"offset_scope","section_bytes"},{"offset",offset},{"length",length}}:J()},
        {"display_path",key}};
}
// These byte locators describe exact original section bytes only. They never
// claim offsets in merged SDK XML. Repeated loop entries use their wire offset.
inline J anchors(const Record& r,const std::string& profile) {
    J out=J::array();const auto& b=r.raw;const size_t end=b.size()>=4?b.size()-4:0;
    auto add=[&](const std::string& key,size_t p,size_t n,size_t container=SIZE_MAX,const std::string& precision="field"){
        auto a=locator(r,key,p,n,container,precision);a["label"]=key;out.push_back(a);
    };
    auto descriptors=[&](size_t start,size_t stop){
        for(size_t p=start;p+2<=stop&&stop<=end;){const size_t n=b[p+1],next=p+2+n;if(next>stop)break;
            add("descriptor",p,n+2,p,"container");
            if((r.tid==0x42||r.tid==0x46)&&b[p]==0x48&&n>=3){const size_t q=p+3,provider=b[q];if(q+1+provider<next){const size_t name=q+1+provider;add("service_type",p+2,1,p);if(provider)add("provider",q+1,provider,p);if(name+1+b[name]<=next&&b[name])add("name",name+1,b[name],p);}}
            if(profile=="isdb-japan"&&(r.tid==0x40||r.tid==0x41)&&b[p]==0xcd&&n>=2){add("remote_control_key_id",p+2,1,p);size_t len=b[p+3]>>2;if(p+4+len<=next&&len)add("ts_name",p+4,len,p);}
            if(profile=="isdb-japan"&&(r.tid==0x40||r.tid==0x41)&&b[p]==0xfb&&n%2==0)for(size_t q=p+2;q+2<=next;q+=2)add("partial_reception_service_id",q,2,p);
            p=next;
        }
    };
    const bool longHeader=b.size()>=8&&(b[1]&0x80)!=0;
    if(longHeader){add("table_id_extension",3,2,0);add("section_header",0,8,0,"container");}
    else if(b.size()>=3)add("section_header",0,3,0,"container");
    // Short sections (including TDT/TOT and cable OOB SI) do not carry the
    // MPEG long-header extension/version/section fields at these byte offsets.
    if(!r.valid||!longHeader)return out;
    if(r.tid==0&&end>=8){for(size_t p=8;p+4<=end;p+=4){add("program_number",p,2,p);add("pmt_pid",p+2,2,p);add("pat_mapping",p,4,p,"container");}}
    if(r.tid==2&&end>=12){add("pcr_pid",8,2,0);size_t n=u16(b,10)&4095;descriptors(12,12+n);for(size_t p=12+n;p+5<=end;){size_t next=p+5+(u16(b,p+3)&4095);if(next>end)break;add("component",p,next-p,p,"container");add("stream_type",p,1,p);add("elementary_pid",p+1,2,p);descriptors(p+5,next);p=next;}}
    if((r.tid==0x42||r.tid==0x46)&&end>=11){add("original_network_id",8,2,0);for(size_t p=11;p+5<=end;){size_t next=p+5+(u16(b,p+3)&4095);if(next>end)break;add("service_id",p,2,p);add("service",p,next-p,p,"container");descriptors(p+5,next);p=next;}}
    if((r.tid==0x40||r.tid==0x41)&&end>=12){size_t n=u16(b,8)&4095;descriptors(10,10+n);for(const auto& t:r.fields.value("transports",J::array())){size_t p=t["descriptor_offset"].get<size_t>()-6,bytes=t["descriptor_bytes"];add("transport",p,6+bytes,p,"container");add("transport_stream_id",p,2,p);add("original_network_id",p+2,2,p);descriptors(p+6,p+6+bytes);}}
    if(profile=="atsc"&&(r.tid==0xc8||r.tid==0xc9)&&end>=10){size_t p=10;for(unsigned i=0;i<b[9]&&p+32<=end;i++){size_t next=p+32+(u16(b,p+30)&1023);if(next>end)break;add("virtual_channel",p,next-p,p,"container");add("short_name",p,14,p);add("channel_number",p+14,3,p);add("channel_tsid",p+22,2,p);add("program_number",p+24,2,p);add("channel_flags",p+26,2,p,"container");add("atsc_source_id",p+28,2,p);descriptors(p+32,next);p=next;}}
    return out;
}

class Builder {
    const std::vector<const Record*>& sections;
    ts::DuckContext& duck;
    const fs::path& root;
    std::map<std::string,J> satelliteSections;
    std::string profile,family;
    size_t revision;uint64_t at;size_t evidenceCount=0;
    std::map<std::string,J> nodes;
    J edges=J::array(),diagnostics=J::array();
    std::map<std::string,size_t> edgeIndexes;
    std::map<std::string,std::set<std::string>> evidenceKeys;
    std::map<std::string,J> anchorSets;
    std::map<std::string,J> values;
    struct Mapping{const Record* record;size_t offset;unsigned pid;};
    std::map<std::pair<unsigned,unsigned>,std::vector<Mapping>> pats;
    std::map<unsigned,std::set<std::string>> localTransports;
    std::map<std::pair<unsigned,unsigned>,std::vector<const Record*>> pmts;
    std::map<std::pair<unsigned,unsigned>,std::string> programs;
    std::set<std::string> missing;
    J ref(const Record& r,const std::string& key,size_t offset=SIZE_MAX,const std::string& role="declares") {
        if(++evidenceCount>MaxEvidence)throw std::runtime_error("Topology evidence limit exceeded (200000); choose an earlier cutoff");
        if(!anchorSets.count(r.id))anchorSets[r.id]=anchors(r,profile);
        J loc=locator(r,key);
        for(const auto& a:anchorSets.at(r.id))if(a["display_path"]==key&&a["byte_range"].is_object()&&a["byte_range"]["offset"]==offset){loc=a;loc.erase("label");break;}
        return {{"analysis_revision",revision},{"at_packet",at},{"section_id",r.id},
            {"table_identity",{{"pid",r.pid},{"table_id",r.tid},{"extension",r.ext},{"version",r.version},{"section_number",r.number},{"current",r.current}}},
            {"assertion_key",key},{"role",role},{"locator",loc}};
    }
    void addEvidence(J& target,const J& e){
        const std::string id=target.contains("node_id")?target["node_id"].get<std::string>():target["edge_id"].get<std::string>();
        auto& seen=evidenceKeys[id];if(seen.insert(e.dump()).second){
            if(target["evidence"].size()>=2048)throw std::runtime_error("Topology per-object evidence limit exceeded (2048); choose an earlier cutoff");
            target["evidence"].push_back(e);
        }
    }
    J& node(const std::string& id,const std::string& type,const J& identity,const std::string& label,const std::string& observation="announced_only",const J& parent=nullptr){
        if(!nodes.count(id)){
            if(nodes.size()>=MaxNodes)throw std::runtime_error("Topology node limit exceeded (20000); choose an earlier cutoff");
            nodes[id]={{"node_id",id},{"family",family},{"object_type",type},{"identity",identity},{"label",label},{"attributes",J::object()},{"attribute_conflicts",J::object()},
                {"observation_status",observation},{"resolution_status","resolved"},{"evidence",J::array()},{"unresolved_reasons",J::array()},{"parent_id",parent}};
        }
        auto& n=nodes.at(id);if(observation=="observed_here")n["observation_status"]=observation;return n;
    }
    void reason(J& n,const std::string& why,const std::string& state="incomplete"){
        if(std::find(n["unresolved_reasons"].begin(),n["unresolved_reasons"].end(),why)==n["unresolved_reasons"].end())n["unresolved_reasons"].push_back(why);
        if(n["resolution_status"]!="conflict"||state=="conflict")n["resolution_status"]=state;
    }
    void attribute(J& n,const std::string& key,const J& value,const J& e){
        addEvidence(n,e);auto& seen=values[n["node_id"].get<std::string>()+"/"+key];if(seen.is_null())seen=J::array();
        J candidate={{"value",value},{"evidence",J::array({e})}};bool found=false;
        for(auto& item:seen)if(item["value"]==value){found=true;if(std::find(item["evidence"].begin(),item["evidence"].end(),e)==item["evidence"].end())item["evidence"].push_back(e);}
        if(!found){if(seen.size()>=256)throw std::runtime_error("Topology conflicting-attribute limit exceeded (256); choose an earlier cutoff");seen.push_back(candidate);}
        if(seen.size()==1)n["attributes"][key]=value;
        else{n["attributes"][key]=nullptr;n["attribute_conflicts"][key]=seen;reason(n,"Conflicting declarations for "+key,"conflict");}
    }
    void edge(const std::string& from,const std::string& to,const std::string& relation,const J& evidence,const std::string& resolution="resolved"){
        if(edges.size()>=MaxEdges)throw std::runtime_error("Topology edge limit exceeded (40000); choose an earlier cutoff");
        const std::string id=from+"/"+relation+"/"+to;
        if(edgeIndexes.count(id)){auto& e=edges[edgeIndexes.at(id)];for(const auto& r:evidence)addEvidence(e,r);if(resolution!="resolved")e["resolution_status"]=resolution;return;}
        edgeIndexes[id]=edges.size();
        edges.push_back({{"edge_id",id},{"from",from},{"to",to},{"relation",relation},{"resolution_status",resolution},{"evidence",evidence}});
    }
    std::string transport(unsigned onid,unsigned tsid){return family+":ts:"+num(onid)+":"+num(tsid);}
    std::string service(unsigned onid,unsigned tsid,unsigned sid){return family+":service:"+num(onid)+":"+num(tsid)+":"+num(sid);}
    void indexPrograms(){
        for(auto* r:sections){if(r->tid==0&&r->pid==0)for(size_t p=8;p+4<=r->raw.size()-4;p+=4)if(u16(r->raw,p))pats[{r->ext,u16(r->raw,p)}].push_back({r,p,u16(r->raw,p+2)&8191});
            if(r->tid==2)pmts[{r->pid,r->ext}].push_back(r);}
    }
    void components(const std::string& id,unsigned tsid,unsigned sid){
        auto& n=nodes.at(id);auto mapping=pats.find({tsid,sid});
        if(mapping==pats.end()){reason(n,"PAT mapping not observed for this service");missing.insert("PAT mapping");return;}
        std::set<unsigned> pids;J prerequisites=J::array();
        for(const auto& m:mapping->second){auto e=ref(*m.record,"pat_mapping",m.offset,"maps_program");prerequisites.push_back(e);attribute(n,"pmt_pid",m.pid,e);pids.insert(m.pid);}
        if(pids.size()!=1){reason(n,"PAT declares conflicting PMT PIDs","conflict");return;}
        auto matched=pmts.find({*pids.begin(),sid});
        if(matched==pmts.end()){reason(n,"Complete matching PAT-selected PMT not observed");missing.insert("PMT");return;}
        n["attributes"]["program_number"]=sid;n["attributes"]["media_presence"]="unverified";
        for(auto* r:matched->second){auto e=ref(*r,"table_id_extension",3,"matches_program_number");prerequisites.push_back(e);addEvidence(n,e);attribute(n,"pcr_pid",r->fields.value("pcr_pid",J()),ref(*r,"pcr_pid",8));
            const auto& b=r->raw;size_t p=12+(u16(b,10)&4095),index=0;
            for(const auto& s:r->fields.value("streams",J::array())){if(p+5>b.size()-4)break;size_t next=p+5+(u16(b,p+3)&4095);if(next>b.size()-4)break;unsigned pid=s["pid"];std::string cid=id+":component:"+num(pid);
                auto& c=node(cid,"component",{{"program_node_id",id},{"pid",pid}},"Component "+hexid(pid),"announced_only",id);
                auto ce=ref(*r,"component",p);attribute(c,"stream_type",s["type"],ref(*r,"stream_type",p));attribute(c,"pid",pid,ref(*r,"elementary_pid",p+1));
                attribute(c,"classification",s.value("is_video",false)?"video":s.value("is_audio",false)?"audio":"unknown",ce);
                c["attributes"]["classification_basis"]=s["classification_basis"];c["attributes"]["media_presence"]="unverified";
                for(const auto& d:r->descriptors){const size_t q=d["offset"];if(q<p+5||q>=next||d.value("decode_status",std::string())!="decoded")continue;
                    if(d.value("name",std::string())=="stream_identifier_descriptor"&&d["length"]==1)attribute(c,"component_tag",b[q+2],ref(*r,"descriptor",q));
                    if(d.value("name",std::string())=="ISO_639_language_descriptor")attribute(c,"languages",d.value("native",J()),ref(*r,"descriptor",q));}
                J evidence=prerequisites;evidence.push_back(ce);edge(id,cid,"contains",evidence);p=next;++index;
            }
        }
    }
    void delivery(const Record& r,const J& transportInfo,const std::string& transportId){
        if(family!="dvb")return;
        const size_t begin=transportInfo["descriptor_offset"],length=transportInfo["descriptor_bytes"];
        for(const auto& d:r.descriptors){
            const size_t offset=d["offset"],bytes=d["length"];
            if(offset<begin||offset+2+bytes>begin+length)continue;
            const bool decoded=d.value("native_decoded",false)&&d.value("decode_status",std::string())=="decoded";
            if(!decoded){
                // The explicit DVB/NIT scope and registered standard tag identify
                // the attempted syntax, never its malformed numeric payload.
                const unsigned tag=d["tag"];
                if(!d.value("decoder_registered",false)||d.value("decode_status",std::string())!="parse_failure"||(tag!=0x43&&tag!=0x44&&tag!=0x5a))continue;
                const std::string id=transportId+":delivery:"+r.id+":"+num(unsigned(offset));
                auto& n=node(id,"delivery_parameters",{{"transport_node_id",transportId},{"descriptor_section_id",r.id},{"descriptor_offset",offset}},"Malformed DVB delivery declaration","announced_only",transportId);
                auto e=ref(r,"descriptor",offset);addEvidence(n,e);reason(n,"Registered DVB delivery descriptor failed SDK parsing; no parameters or satellite candidates inferred","unresolved");
                n["attributes"]={{"parameters",J::object()},{"parameter_status","invalid_or_unsupported"},{"physical_transponder_id",nullptr},{"confirmed_satellite",nullptr},{"raw_descriptor_hex",d["raw"]},{"reception_verified",false}};
                edge(transportId,id,"references",J::array({ref(r,"transport",begin-6),e}),"unresolved");continue;
            }
            const J native=d.value("native",J::object());const std::string name=native.value("name",std::string());
            if(name!="satellite_delivery_system_descriptor"&&name!="cable_delivery_system_descriptor"&&name!="terrestrial_delivery_system_descriptor")continue;
            J parameters=J::object(),association;std::string system,status="resolved",parameterStatus="decoded",issue;
            ts::Descriptor binary(r.raw.data()+offset,bytes+2);
            auto bcdValid=[&](size_t start,size_t digits){for(size_t i=0;i<digits;i++)if(((r.raw[start+i/2]>>(i%2?0:4))&15)>9)return false;return true;};
            if(name=="satellite_delivery_system_descriptor"){
                if(!satelliteSections.count(r.id))satelliteSections[r.id]=satellitemeta::inspect(root,r);
                for(const auto& a:satelliteSections.at(r.id))if(a["wire_source"]["section_offset"]==offset){association=a;break;}
                if(association.is_null())continue;
                system=native.value("attributes",J::object()).value("modulation_system",std::string("unknown"));
                const std::string astatus=association["status"];
                if(astatus=="invalid_parameters"||astatus=="unsupported_delivery_system")status="unresolved";
                else parameters=association["raw_parameters"];
            }else if(name=="cable_delivery_system_descriptor"){
                system="DVB-C";ts::CableDeliverySystemDescriptor typed(duck,binary);
                if(!typed.isValid()||bytes!=11||!bcdValid(offset+2,8)||!bcdValid(offset+9,7)||!typed.frequency||!typed.symbol_rate)status="unresolved";
                else parameters={{"frequency_hz",typed.frequency},{"symbol_rate",typed.symbol_rate},{"modulation_code",typed.modulation},{"fec_outer_code",typed.FEC_outer},{"fec_inner_code",typed.FEC_inner}};
            }else{
                system="DVB-T";ts::TerrestrialDeliverySystemDescriptor typed(duck,binary);
                if(!typed.isValid()||bytes!=11)status="unresolved";
                else {
                    // The SDK maps the wire 0xFFFFFFFF sentinel to zero. Keep
                    // known modulation fields without presenting zero as RF Hz.
                    parameters={{"frequency_hz",typed.centre_frequency?J(typed.centre_frequency):J()},{"frequency_code",uint32_t(u16(r.raw,offset+2))<<16|u16(r.raw,offset+4)},
                        {"bandwidth_code",typed.bandwidth},{"bandwidth_hz",typed.getBandwidth()?J(typed.getBandwidth()):J()},
                        {"constellation_code",typed.constellation},{"hierarchy_code",typed.hierarchy},{"code_rate_hp_code",typed.code_rate_hp},{"code_rate_lp_code",typed.code_rate_lp},
                        {"guard_interval_code",typed.guard_interval},{"transmission_mode_code",typed.transmission_mode},{"other_frequency",typed.other_frequency}};
                    if(!typed.centre_frequency){status="unresolved";parameterStatus="partial";issue="DVB-T center frequency unspecified or zero; other advertised parameters retained, no RF frequency inferred";}
                }
            }
            const std::string id=transportId+":delivery:"+r.id+":"+num(unsigned(offset));
            auto& n=node(id,"delivery_parameters",{{"transport_node_id",transportId},{"descriptor_section_id",r.id},{"descriptor_offset",offset}},system+" delivery parameters","announced_only",transportId);
            const auto evidence=ref(r,"descriptor",offset);addEvidence(n,evidence);
            n["attributes"]={{"delivery_system",system},{"parameters",parameters},{"parameter_status",parameterStatus=="partial"?"partial":status=="resolved"?"decoded":"invalid_or_unsupported"},
                {"physical_transponder_id",nullptr},{"reception_verified",false},{"raw_descriptor_hex",d["raw"]},{"sdk_parameters",native.value("attributes",J::object())},
                {"scope","Advertised delivery / TP parameters only. A transport stream is not a confirmed physical transponder; no tuning or reception measurement."}};
            if(status!="resolved")reason(n,issue.empty()?"Invalid or unsupported delivery parameters; original descriptor retained":issue,"unresolved");
            edge(transportId,id,"references",J::array({ref(r,"transport",begin-6),evidence}),status);
            if(association.is_null())continue;
            n["attributes"]["satellite_association_status"]=association["status"];n["attributes"]["confirmed_satellite"]=nullptr;
            n["attributes"]["satellite_uncertainty"]=association["uncertainty"];n["attributes"]["satellite_matching"]=association["matching"];
            n["attributes"]["satellite_catalog"]=association.value("catalog",J());
            for(const auto& candidate:association["candidates"]){
                const std::string cid=id+":satellite-candidate:"+candidate["id"].get<std::string>();
                auto& c=node(cid,"satellite_candidate",{{"delivery_node_id",id},{"catalog_entry_id",candidate["id"]}},candidate["name"].get<std::string>()+" · candidate","unresolved",id);
                addEvidence(c,evidence);reason(c,"Nominal orbital-slot candidate only; spacecraft and capture-date assignment unconfirmed","unresolved");c["attributes"]=candidate;c["attributes"]["confirmed_satellite"]=nullptr;c["attributes"]["uncertainty"]=association["uncertainty"];
                J references=J::array({{{"catalog",association["catalog"]},{"source",candidate["source"]}}});c["reference_sources"]=references;
                edge(id,cid,"candidate_association",J::array({evidence}),"candidate");edges[edgeIndexes.at(id+"/candidate_association/"+cid)]["reference_sources"]=references;
            }
        }
    }
    void nit(){
        for(auto* r:sections)if(r->pid==0x10&&(r->tid==0x40||r->tid==0x41)){
            const std::string nid=family+":network:"+num(r->ext);auto& network=node(nid,"network",{{"network_id",r->ext}},"Network "+hexid(r->ext));addEvidence(network,ref(*r,"table_id_extension",3));
            for(const auto& t:r->fields.value("transports",J::array())){unsigned onid=t["original_network_id"],tsid=t["transport_stream_id"];size_t start=t["descriptor_offset"],length=t["descriptor_bytes"];
                const std::string tid=transport(onid,tsid);auto& n=node(tid,"transport",{{"original_network_id",onid},{"transport_stream_id",tsid}},"Transport "+hexid(onid)+" / "+hexid(tsid),"announced_only",nid);
                auto e=ref(*r,"transport",start-6);addEvidence(n,e);edge(nid,tid,"announces",J::array({ref(*r,"table_id_extension",3),e}));
                delivery(*r,t,tid);
                if(family!="isdb")continue;
                for(const auto& d:r->descriptors){size_t p=d["offset"],len=d["length"];if(p<start||p+2+len>start+length||d.value("decode_status",std::string())!="decoded")continue;
                    if(profile!="isdb-japan"){if(d["tag"]==0xcd||d["tag"]==0xfb)reason(n,"ISDB descriptor relation requires a validated regional profile","unresolved");continue;}
                    ts::Descriptor bin(r->raw.data()+p,len+2);
                    if(d.value("name",std::string())=="TS_information_descriptor"){
                        ts::TSInformationDescriptor typed(duck,bin);if(!typed.isValid())continue;attribute(n,"remote_control_key_id",typed.remote_control_key_id,ref(*r,"remote_control_key_id",p+2));
                        attribute(n,"ts_name",typed.ts_name.toUTF8(),ref(*r,"ts_name",p+4));J transmission=J::array();for(const auto& v:typed.transmission_types)transmission.push_back({{"transmission_type_info",v.transmission_type_info},{"service_ids",v.service_ids}});
                        attribute(n,"transmission_types",transmission,ref(*r,"descriptor",p));n["attributes"]["transmission_type_interpretation"]="raw; no RF layer or segment assignment inferred";
                    }
                    if(d.value("name",std::string())=="partial_reception_descriptor"){
                        ts::PartialReceptionDescriptor typed(duck,bin);if(!typed.isValid())continue;size_t q=p+2;
                        for(unsigned sid:typed.service_ids){const std::string rid=tid+":partial:"+num(sid);auto& reference=node(rid,"service_reference",{{"original_network_id",onid},{"transport_stream_id",tsid},{"service_id",sid}},"Partial reception reference "+hexid(sid),"announced_only",tid);
                            auto pe=ref(*r,"partial_reception_service_id",q);addEvidence(reference,pe);reference["attributes"]["declaration"]="partial reception; actual reception and RF layers unverified";edge(tid,rid,"references",J::array({e,pe}));q+=2;}
                    }
                }
            }
        }
    }
    void sdt(){
        for(auto* r:sections)if(r->pid==0x11&&(r->tid==0x42||r->tid==0x46)&&r->raw.size()>=15){unsigned onid=u16(r->raw,8);std::string tid=transport(onid,r->ext);bool actual=r->tid==0x42;
            auto& t=node(tid,"transport",{{"original_network_id",onid},{"transport_stream_id",r->ext}},"Transport "+hexid(onid)+" / "+hexid(r->ext),actual?"observed_here":"announced_only");
            addEvidence(t,ref(*r,"original_network_id",8));addEvidence(t,ref(*r,"table_id_extension",3));if(actual)localTransports[r->ext].insert(tid);
            size_t p=11;for(const auto& s:r->services){size_t next=p+5+(u16(r->raw,p+3)&4095);unsigned sid=s["id"];std::string id=service(onid,r->ext,sid);auto& n=node(id,"service",{{"original_network_id",onid},{"transport_stream_id",r->ext},{"service_id",sid}},"Service "+hexid(sid),actual?"observed_here":"announced_only",tid);
                auto e=ref(*r,"service_id",p);addEvidence(n,e);edge(tid,id,"contains",J::array({ref(*r,"table_id_extension",3),ref(*r,"original_network_id",8),e}));
                for(const auto& d:r->descriptors){size_t q=d["offset"];if(q<p+5||q>=next||d.value("name",std::string())!="service_descriptor"||!d["fields"].contains("name"))continue;
                    const size_t provider=r->raw[q+3],name=q+4+provider;attribute(n,"name",d["fields"]["name"],ref(*r,"name",name+1));attribute(n,"provider",d["fields"].value("provider",J()),ref(*r,"provider",q+4));attribute(n,"service_type",d["fields"].value("type",J()),ref(*r,"service_type",q+2));}
                if(n["attributes"].contains("name"))n["label"]=n["attributes"]["name"].is_string()&&!n["attributes"]["name"].get<std::string>().empty()?n["attributes"]["name"]:J("Service "+hexid(sid));
                if(actual)n["attributes"]["actual_sdt"]=true;p=next;
            }
        }
    }
    void mpegPrograms(){
        for(const auto& [key,mappings]:pats){auto [tsid,sid]=key;std::string id,parent;bool ambiguous=localTransports[tsid].size()>1;
            if(family!="atsc"&&localTransports[tsid].size()==1){parent=*localTransports[tsid].begin();unsigned onid=nodes.at(parent)["identity"]["original_network_id"];std::string candidate=service(onid,tsid,sid);if(nodes.count(candidate))id=candidate;}
            if(id.empty()){
                if(family!="atsc"&&parent.empty()){parent=family+":observed-ts:"+num(tsid);auto& t=node(parent,"transport_observation",{{"transport_stream_id",tsid},{"original_network_id",nullptr}},"Observed transport "+hexid(tsid),"observed_here");addEvidence(t,ref(*mappings.front().record,"table_id_extension",3));reason(t,ambiguous?"Multiple actual SDT ONIDs share this TSID; PAT cannot select one":"Original network ID not established by actual SDT",ambiguous?"conflict":"unresolved");}
                id=family+":program:"+num(tsid)+":"+num(sid);auto& n=node(id,"mpeg_program",{{"transport_stream_id",tsid},{"program_number",sid}},"Program "+hexid(sid),"observed_here",parent.empty()?J():J(parent));
                if(family!="atsc")reason(n,ambiguous?"Ambiguous actual SDT transport identity":"Matching actual SDT service not observed",ambiguous?"conflict":"incomplete");
                if(!parent.empty())edge(parent,id,"contains",J::array({ref(*mappings.front().record,"pat_mapping",mappings.front().offset)}));
            }
            programs[key]=id;components(id,tsid,sid);
        }
        // SDT-only services remain real declarations, never silently disappear.
        for(auto& [id,n]:nodes)if(n["object_type"]=="service"&&n["attributes"].value("actual_sdt",false)){
            unsigned tsid=n["identity"]["transport_stream_id"],sid=n["identity"]["service_id"];
            if(localTransports[tsid].size()>1)reason(n,"Multiple actual SDT ONIDs share this TSID; PAT/PMT relation withheld","conflict");
            else if(!programs.count({tsid,sid})){reason(n,"PAT mapping not observed for this service");missing.insert("PAT mapping");}
        }
    }
    void vct(){
        std::map<std::tuple<unsigned,unsigned,unsigned>,std::vector<const Record*>> groups;
        for(auto* r:sections)if(r->tid==0xc8||r->tid==0xc9)groups[{r->pid,r->tid,r->ext}].push_back(r);
        for(auto& [key,parts]:groups){std::sort(parts.begin(),parts.end(),[](auto* a,auto* b){return a->number<b->number;});ts::BinaryTable binary;
            for(auto* r:parts)binary.addNewSection(r->raw.data(),r->raw.size(),ts::PID(r->pid),ts::CRC32::CHECK);
            std::unique_ptr<ts::VCT> parsed;if(std::get<1>(key)==0xc8)parsed=std::make_unique<ts::TVCT>(duck,binary);else parsed=std::make_unique<ts::CVCT>(duck,binary);
            if(!parsed->isValid()){diagnostics.push_back({{"code","vct_parse_failure"},{"section_id",parts.front()->id},{"message","Complete VCT failed SDK validation; no channel relationships emitted"}});continue;}
            const Record& first=*parts.front();std::string context="atsc:vct:"+num(first.pid)+":"+num(first.tid)+":"+num(first.ext);
            auto& lineup=node(context,"vct_context",{{"pid",first.pid},{"table_id",first.tid},{"transport_stream_id",first.ext}},std::string(first.tid==0xc8?"TVCT":"CVCT")+" "+hexid(first.ext),"observed_here");
            for(auto* r:parts)addEvidence(lineup,ref(*r,"table_id_extension",3));
            struct Channel{const Record* record;size_t offset;const ts::VCT::Channel* value;std::string slot;J number;};std::vector<Channel> entries;std::map<std::string,size_t> counts;
            auto decoded=parsed->channels.begin();
            for(auto* r:parts){size_t p=10,end=r->raw.size()-4;for(unsigned i=0;i<r->raw[9]&&p+32<=end&&decoded!=parsed->channels.end();i++,++decoded){const auto& c=decoded->second;size_t next=p+32+(u16(r->raw,p+30)&1023);if(next>end)break;
                    bool one=first.tid==0xc9&&(c.major_channel_number&0x3f0)==0x3f0;
                    bool reserved=!one&&(first.tid==0xc9?(c.major_channel_number>=1000||c.minor_channel_number>=1000):(c.major_channel_number<1||c.major_channel_number>99||c.minor_channel_number>=1000));
                    unsigned single=((c.major_channel_number&15)<<10)|c.minor_channel_number;
                    std::string slot=one?"one:"+num(single):(reserved?"raw:":"two:")+num(c.major_channel_number)+":"+num(c.minor_channel_number);
                    J number={{"format",one?"one_part":reserved?"reserved":"two_part"},{"major",c.major_channel_number},{"minor",c.minor_channel_number},{"one_part",one?J(single):J()}};
                    entries.push_back({r,p,&c,slot,number});counts[slot]++;p=next;
                }}
            for(const auto& item:entries){const auto& r=*item.record;const auto& c=*item.value;const size_t p=item.offset;std::string id=context+":channel:"+item.slot;
                if(counts[item.slot]>1)id+=":observation:"+r.id+":"+num(unsigned(p));
                std::string display=item.number["format"]=="one_part"?num(item.number["one_part"].get<unsigned>()):num(c.major_channel_number)+"."+num(c.minor_channel_number);
                auto& n=node(id,"virtual_channel",{{"vct_context",context},{"channel_number",item.number}},display+" "+c.short_name.toUTF8(),"observed_here",context);
                auto e=ref(r,"virtual_channel",p);addEvidence(n,e);attribute(n,"short_name",c.short_name.toUTF8(),ref(r,"short_name",p));attribute(n,"channel_number",item.number,ref(r,"channel_number",p+14));
                attribute(n,"channel_tsid",c.channel_TSID,ref(r,"channel_tsid",p+22));attribute(n,"program_number",c.program_number,ref(r,"program_number",p+24));attribute(n,"atsc_source_id",c.source_id,ref(r,"atsc_source_id",p+28));
                n["attributes"].update({{"hidden",c.hidden},{"hide_guide",c.hide_guide},{"access_controlled",c.access_controlled},{"out_of_band",c.out_of_band},{"path_select",c.path_select},{"modulation_mode",c.modulation_mode},{"etm_location",c.ETM_location},{"service_type",c.service_type},{"carrier_frequency_raw",c.carrier_frequency},{"rf_frequency",nullptr}});
                addEvidence(n,ref(r,"channel_flags",p+26));edge(context,id,"contains",J::array({ref(r,"table_id_extension",3),e}));
                if(counts[item.slot]>1)reason(n,"Duplicate virtual-channel slot; each wire observation retained","conflict");
                if(item.number["format"]=="reserved")reason(n,"Reserved virtual-channel number encoding; raw major/minor retained","unresolved");
                const std::string source=c.source_id?context+":source:"+num(c.source_id):id+":source-unidentified";auto& sn=node(source,"programme_source_reference",{{"vct_context",context},{"atsc_source_id",c.source_id}},"Programme source "+hexid(c.source_id),"announced_only",context);addEvidence(sn,ref(r,"atsc_source_id",p+28));if(c.source_id==0)reason(sn,"ATSC source_id zero identifies no programme source","unresolved");edge(id,source,"references",J::array({ref(r,"atsc_source_id",p+28)}));
                if(c.program_number==0||c.program_number==65535){n["attributes"]["mapping_status"]=c.program_number==0?"inactive":"analog";continue;}
                auto found=programs.find({c.channel_TSID,c.program_number});std::string target;
                if(found!=programs.end()){
                    target=found->second;if(nodes.at(target)["parent_id"].is_null())nodes.at(target)["parent_id"]=id;
                    J ev=J::array({ref(r,"channel_tsid",p+22,"maps_transport"),ref(r,"program_number",p+24,"maps_program")});
                    for(const auto& m:pats.at({c.channel_TSID,c.program_number}))ev.push_back(ref(*m.record,"pat_mapping",m.offset,"matches_pat"));
                    std::string status=nodes.at(target)["resolution_status"];n["attributes"]["mapping_status"]=status;if(status!="resolved")reason(n,"Matching MPEG program lacks a resolved PMT",status);edge(id,target,"maps_to",ev,status);
                }else{target=id+":program-reference";auto& pn=node(target,"mpeg_program_reference",{{"transport_stream_id",c.channel_TSID},{"program_number",c.program_number}},"Program reference "+hexid(c.program_number),"announced_only",id);addEvidence(pn,ref(r,"program_number",p+24));reason(pn,"Matching local PAT transport/program not observed","unresolved");reason(n,"Channel maps outside observed PAT transport/program","unresolved");n["attributes"]["mapping_status"]="unresolved";edge(id,target,"maps_to",J::array({ref(r,"channel_tsid",p+22),ref(r,"program_number",p+24)}),"unresolved");}
                // Preserve independent service-location declarations; never use
                // them as a missing-PMT replacement or discard disagreement.
                const size_t stop=p+32+(u16(r.raw,p+30)&1023);for(size_t q=p+32;q+2<=stop;){size_t len=r.raw[q+1],next=q+2+len;if(next>stop)break;
                    if(r.raw[q]==0xa1&&len>=3&&len==3+6*size_t(r.raw[q+4])){J declared=J::array();unsigned pcr=u16(r.raw,q+2)&8191;for(size_t k=q+5;k+6<=next;k+=6)declared.push_back({{"stream_type",r.raw[k]},{"pid",u16(r.raw,k+1)&8191}});
                        auto de=ref(r,"descriptor",q);attribute(n,"service_location_declaration",{{"pcr_pid",pcr},{"components",declared}},de);
                        if(found!=programs.end()&&nodes.at(target)["attributes"].contains("pcr_pid")){
                            std::set<std::pair<unsigned,unsigned>> actual,announced;for(const auto& [unused,cn]:nodes)if(cn["object_type"]=="component"&&cn["parent_id"]==target&&cn["attributes"]["stream_type"].is_number_integer())actual.insert({cn["attributes"]["pid"].get<unsigned>(),cn["attributes"]["stream_type"].get<unsigned>()});for(const auto& dc:declared)announced.insert({dc["pid"].get<unsigned>(),dc["stream_type"].get<unsigned>()});
                            if(actual!=announced||nodes.at(target)["attributes"]["pcr_pid"]!=pcr){reason(n,"VCT service-location declaration conflicts with PAT-selected PMT","conflict");J ev=nodes.at(target)["evidence"];ev.push_back(de);edge(id,target,"maps_to",ev,"conflict");}
                        }
                    }q=next;
                }
            }
        }
    }
public:
    Builder(const std::vector<const Record*>& input,ts::DuckContext& ctx,const fs::path& resources,std::string standard,size_t rev,uint64_t cutoff):sections(input),duck(ctx),root(resources),profile(std::move(standard)),revision(rev),at(cutoff){family=profile=="dvb"?"dvb":profile=="atsc"?"atsc":profile.rfind("isdb",0)==0?"isdb":"unresolved";}
    J build(const J& args,size_t rawSections,const J& incomplete){
        indexPrograms();
        if(family=="dvb"||family=="isdb"){nit();sdt();mpegPrograms();}
        else if(family=="atsc"){mpegPrograms();vct();}
        else{mpegPrograms();diagnostics.push_back({{"code","explicit_profile_required"},{"message","Select DVB, ATSC or an ISDB analysis profile and rescan to resolve ambiguous signalling families. View filters do not change interpretation."}});}
        // Resolve only explicit ISDB service triplets. Missing SDT remains a
        // reference and does not create a service by name or numeric coincidence.
        if(family=="isdb")for(auto& [id,n]:nodes)if(n["object_type"]=="service_reference"){
            const auto& identity=n["identity"];std::string target=service(identity["original_network_id"],identity["transport_stream_id"],identity["service_id"]);
            if(nodes.count(target)){J ev=n["evidence"];for(const auto& e:nodes.at(target)["evidence"])ev.push_back(e);edge(id,target,"references",ev);}else reason(n,"Referenced SDT service not observed","unresolved");}
        if(pats.empty())missing.insert("PAT");
        if(family=="atsc"&&std::none_of(nodes.begin(),nodes.end(),[](const auto& item){return item.second["object_type"]=="vct_context";}))missing.insert("TVCT/CVCT");
        if((family=="dvb"||family=="isdb")&&localTransports.empty())missing.insert("actual SDT");
        if((family=="dvb"||family=="isdb")&&std::none_of(sections.begin(),sections.end(),[](auto* r){return r->pid==0x10&&(r->tid==0x40||r->tid==0x41);}))missing.insert("NIT");
        for(const auto& item:incomplete)diagnostics.push_back(item);
        std::map<std::string,std::vector<std::string>> children;std::vector<std::string> roots;
        size_t unresolved=0;for(auto& [id,n]:nodes){if(n["resolution_status"]!="resolved")unresolved++;if(n["resolution_status"]=="conflict")n["observation_status"]="conflict";if(n["parent_id"].is_null())roots.push_back(id);else children[n["parent_id"].get<std::string>()].push_back(id);}
        std::vector<std::string> order;std::function<void(const std::string&)> walk=[&](const std::string& id){order.push_back(id);for(const auto& child:children[id])walk(child);};for(const auto& id:roots)walk(id);
        const std::string filter=args.value("family",std::string("all"));std::vector<std::string> candidates;
        if(args.contains("parent_id")&&!args["parent_id"].get<std::string>().empty()&&!nodes.count(args["parent_id"].get<std::string>()))throw std::runtime_error("Unknown topology parent_id in this snapshot");
        for(const auto& id:order){const auto& n=nodes.at(id);if(filter!="all"&&n["family"]!=filter)continue;if(args.contains("parent_id")){const std::string p=args["parent_id"];if(p.empty()?!n["parent_id"].is_null():n["parent_id"]!=p)continue;}candidates.push_back(id);}
        const size_t offset=args.value("offset",size_t(0)),limit=args.value("limit",size_t(200));const size_t stop=offset>=candidates.size()?candidates.size():offset+std::min(limit,candidates.size()-offset);
        J selected=J::array(),context=J::array(),selectedEdges=J::array();std::set<std::string> selectedIds,contextIds;
        for(size_t i=offset;i<stop;i++){selected.push_back(nodes.at(candidates[i]));selectedIds.insert(candidates[i]);}
        for(const auto& id:selectedIds){auto parent=nodes.at(id)["parent_id"];while(parent.is_string()){std::string p=parent;if(!selectedIds.count(p))contextIds.insert(p);parent=nodes.at(p)["parent_id"];}}
        for(const auto& id:order)if(contextIds.count(id))context.push_back(nodes.at(id));
        for(const auto& e:edges)if(selectedIds.count(e["from"].get<std::string>()))selectedEdges.push_back(e);
        std::string label=family=="dvb"?"DVB":family=="atsc"?"ATSC 1.0":profile=="isdb-japan"?"ISDB Japan":profile=="isdb-brazil"?"ISDB Brazil":family=="isdb"?"ISDB · region unspecified":"Unresolved signalling";
        J unsupported=J::array({"BAT/bouquet and regional LCN semantic projections","Physical transponder/satellite identification, S2 extension/S2X/T2 and non-DVB delivery topology","ATSC MGT/STT/RRT/EPG/ETT semantic relationships","ISDB BIT/CDT/SDTT/logo/broadcaster semantic relationships","Actual media presence, RF tuning, layers and reception"});
        if(family=="isdb"&&profile!="isdb-japan")unsupported.push_back("ISDB remote-control and partial-reception semantics outside validated Japan profile");
        return {{"schema_version",1},{"analysis_revision",revision},{"at_packet",at},{"interpretation_profile",profile},{"status",family=="unresolved"?"unresolved":nodes.empty()&&diagnostics.empty()?"empty":unresolved||!diagnostics.empty()||!missing.empty()?"incomplete":"ok"},
            {"diagnostics",diagnostics},{"counts",{{"nodes",nodes.size()},{"edges",edges.size()},{"unresolved",unresolved},{"raw_sections",rawSections}}},
            {"coverage",{{"supported_adapters",J::array({"dvb","atsc","isdb"})},{"active_adapter",family},{"missing_tables",missing},{"unsupported_relations",unsupported},{"limits",{{"nodes",MaxNodes},{"edges",MaxEdges},{"evidence",MaxEvidence},{"evidence_per_object",2048},{"attribute_candidates",256},{"page",500}}}}},
            {"nodes",selected},{"context_nodes",context},{"edges",selectedEdges},{"projections",J::array({{{"family",family},{"label",label},{"roots",roots}}})},
            {"page",{{"offset",offset},{"limit",limit},{"total",candidates.size()},{"has_more",stop<candidates.size()},{"next_offset",stop<candidates.size()?J(stop):J()}}}};
    }
};
}
