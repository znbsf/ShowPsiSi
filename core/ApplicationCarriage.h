#pragma once
#include "tsApplicationSignallingDescriptor.h"
#include "tsPAT.h"
#include "tsPMT.h"

// Additive local carriage evidence, after generation-safe engine selection.
// This does not identify an application runtime, component carousel or owner.
namespace applicationcarriage {
constexpr size_t MaxSelected=20000,MaxGroups=1024,MaxMappings=4096,MaxStreams=4096,MaxDescriptors=8192,MaxCards=256,MaxEvidence=2048;
using Group=std::map<unsigned,const Record*>;
struct LimitError:std::runtime_error{using std::runtime_error::runtime_error;};
inline bool binary(const Group& parts,ts::BinaryTable& table) {
    if(parts.empty())return false;
    const auto& first=*parts.begin()->second;
    if(parts.size()!=size_t(first.last)+1)return false;
    for(unsigned n=0;n<=first.last;++n){auto it=parts.find(n);if(it==parts.end())return false;const auto& r=*it->second;
        if(!r.valid||!r.current||r.raw.size()<12||!(r.raw[1]&0x80)||r.version!=first.version||r.last!=first.last)return false;
        table.addNewSection(r.raw.data(),r.raw.size(),ts::PID(r.pid),ts::CRC32::CHECK);
    }
    return table.isValid();
}
inline J evidence(const Record& r,const std::string& key,size_t offset,size_t length,size_t container,const std::string& precision,size_t revision,uint64_t cutoff){
    return {{"analysis_revision",revision},{"at_packet",cutoff},{"section_id",r.id},
        {"table_identity",{{"pid",r.pid},{"table_id",r.tid},{"extension",r.ext},{"version",r.version},{"section_number",r.number},{"current",r.current}}},
        {"assertion_key",key},{"role","declares_carriage"},{"locator",topology::locator(r,key,offset,length,container,precision)}};
}
inline J enrich(J summary,ts::DuckContext& duck,const Record& ait,const std::vector<const Record*>& selected,size_t revision,uint64_t cutoff,const std::string& profile){
    for(auto& relation:summary["unsupported_relations"])if(relation=="PMT/service ownership and component-tag resolution")relation="Exclusive application ownership, component-tag and remote-service resolution";
    J context={{"status","unresolved"},{"scope","Observed local PAT/PMT carriage declarations; nonexclusive, no runtime/compatibility/ownership claim"},{"diagnostics",J::array()},
        {"limits",{{"selected_sections",MaxSelected},{"table_groups",MaxGroups},{"pat_mappings",MaxMappings},{"pmt_streams",MaxStreams},{"descriptors",MaxDescriptors},{"carriage_cards",MaxCards},{"source_references",MaxEvidence}}}};
    auto stop=[&](const std::string& status,const std::string& why){context["status"]=status;context["diagnostics"].push_back(why);summary["diagnostics"].push_back("AIT carriage: "+why);summary["carriage_context"]=context;return summary;};
    if(profile!="dvb")return stop("unsupported_profile","Explicit DVB interpretation is required for AIT carriage declarations");
    if(!ait.current)return stop("unsupported_next","Current PAT/PMT carriage is not attached to next-table AIT evidence");
    std::string aitNode;J aitEvidence;
    for(const auto& node:summary["objects"])if(node["object_type"]=="application_signalling"){aitNode=node["node_id"];break;}
    if(aitNode.empty())return stop("unavailable_ait","A complete, valid selected AIT is required for carriage relations");
    if(selected.size()>MaxSelected)return stop("resource_limit","Selected-section limit exceeded");
    try {
        std::map<unsigned,Group> pats;
        std::map<std::pair<unsigned,unsigned>,Group> pmts;
        for(const auto* r:selected){
            if(!r->valid||!r->current)continue;
            if(r->tid==0&&r->pid==0){if(!pats.count(r->ext)&&pats.size()+pmts.size()>=MaxGroups)return stop("resource_limit","PAT/PMT group limit exceeded");pats[r->ext][r->number]=r;}
            else if(r->tid==2){const auto key=std::make_pair(r->pid,r->ext);if(!pmts.count(key)&&pats.size()+pmts.size()>=MaxGroups)return stop("resource_limit","PAT/PMT group limit exceeded");pmts[key][r->number]=r;}
        }
        if(pats.empty())return stop("missing_pat","A current PAT on PID 0 was not observed");
        if(pats.size()!=1)return stop("conflict","Multiple selected PAT transport identities prevent a unique local carriage context");
        const auto& [tsid,patParts]=*pats.begin();ts::BinaryTable patBinary;
        if(!binary(patParts,patBinary))return stop("incomplete_pat","The selected PAT generation is incomplete");
        struct Mapping {const Record* record;size_t offset;unsigned pid;};
        std::map<unsigned,std::vector<Mapping>> programs;size_t mappingCount=0;
        for(const auto& [number,r]:patParts){const auto& b=r->raw;const size_t end=b.size()-4;
            if(end<8||(end-8)%4)return stop("malformed_pat","PAT mapping loop length is inconsistent");
            for(size_t p=8;p<end;p+=4){if(++mappingCount>MaxMappings)return stop("resource_limit","PAT mapping limit exceeded");unsigned program=u16(b,p);if(program)programs[program].push_back({r,p,unsigned(u16(b,p+2)&8191)});}
        }
        ts::PAT typedPat(duck,patBinary);if(!typedPat.isValid())return stop("malformed_pat","The selected PAT failed SDK validation");
        J cards=J::array(),relations=J::array();size_t streamCount=0,descriptorCount=0,evidenceCount=0;bool unresolved=false;
        auto addEvidence=[&](J& target,const J& e){if(++evidenceCount>MaxEvidence)throw LimitError("Carriage source-reference limit exceeded");target.push_back(e);};
        aitEvidence=evidence(ait,"table_id_extension",3,2,0,"field",revision,cutoff);
        for(const auto& [program,mappings]:programs){
            std::set<unsigned> pids;for(const auto& mapping:mappings)pids.insert(mapping.pid);
            for(unsigned pid:pids){
                auto group=pmts.find({pid,program});if(group==pmts.end())continue;ts::BinaryTable pmtBinary;
                if(!binary(group->second,pmtBinary))continue;
                // Bound wire loops before constructing SDK stream/descriptor lists.
                for(const auto& [number,r]:group->second){const auto& b=r->raw;const size_t end=b.size()-4;
                    auto countDescriptors=[&](size_t begin,size_t stop){if(stop>end)throw std::runtime_error("PMT descriptor loop exceeds its section");for(size_t q=begin;q<stop;){if(++descriptorCount>MaxDescriptors)throw LimitError("PMT descriptor work limit exceeded");if(q+2>stop||q+2+b[q+1]>stop)throw std::runtime_error("PMT descriptor is truncated");q+=2+b[q+1];}};
                    if(end<12)return stop("malformed_pmt","PMT fixed fields are truncated");size_t p=12+(u16(b,10)&4095);countDescriptors(12,p);
                    while(p<end){if(++streamCount>MaxStreams)return stop("resource_limit","PMT stream work limit exceeded");if(p+5>end)return stop("malformed_pmt","PMT stream header is truncated");const size_t next=p+5+(u16(b,p+3)&4095);countDescriptors(p+5,next);p=next;}
                }
                ts::PMT typedPmt(duck,pmtBinary);if(!typedPmt.isValid())continue;
                std::vector<size_t> programCards;
                for(const auto& [number,r]:group->second){const auto& b=r->raw;const size_t end=b.size()-4;if(end<12)continue;
                    size_t p=12+(u16(b,10)&4095);if(p>end)continue;
                    while(p<end){
                        if(p+5>end)return stop("malformed_pmt","PMT elementary-stream header is truncated");
                        const size_t next=p+5+(u16(b,p+3)&4095);if(next>end)return stop("malformed_pmt","PMT elementary-stream descriptor loop exceeds its section");
                        if((u16(b,p+1)&8191)!=ait.pid){p=next;continue;}
                        if(cards.size()>=MaxCards)return stop("resource_limit","AIT carriage-card limit exceeded");
                        J ev=J::array();addEvidence(ev,aitEvidence);
                        for(const auto& mapping:mappings)addEvidence(ev,evidence(*mapping.record,"pat_mapping",mapping.offset,4,mapping.offset,"container",revision,cutoff));
                        addEvidence(ev,evidence(*r,"table_id_extension",3,2,0,"field",revision,cutoff));
                        addEvidence(ev,evidence(*r,"component",p,next-p,p,"container",revision,cutoff));
                        addEvidence(ev,evidence(*r,"elementary_pid",p+1,2,p,"field",revision,cutoff));
                        J reasons=J::array();std::set<unsigned> versions,types;bool present=false,validDescriptor=false,malformed=false;
                        for(size_t q=p+5;q<next;){
                            if(q+2>next||q+2+b[q+1]>next)return stop("malformed_pmt","PMT descriptor exceeds elementary-stream loop");
                            const size_t bytes=2+b[q+1];if(b[q]==0x6f){present=true;addEvidence(ev,evidence(*r,"descriptor",q,bytes,q,"container",revision,cutoff));
                                ts::Descriptor bin(b.data()+q,bytes);ts::ApplicationSignallingDescriptor value(duck,bin);
                                bool reserved=true;for(size_t entry=q+2;entry+3<=q+bytes;entry+=3)reserved&=(b[entry]&0x80)!=0&&(b[entry+2]&0xe0)==0xe0;
                                if(!value.isValid()||b[q+1]%3||!reserved){malformed=true;reasons.push_back("Malformed length, reserved bits or SDK value in application_signalling_descriptor; raw source retained");}
                                else {validDescriptor=true;for(const auto& entry:value.entries){types.insert(entry.application_type);if(entry.application_type==(ait.ext&32767))versions.insert(entry.AIT_version_number);}}
                            }q+=bytes;
                        }
                        std::string status="resolved",versionStatus=versions.empty()?(malformed?"unavailable_malformed_descriptor":!present?"not_declared":"not_signalled"):versions.size()==1&&*versions.begin()==ait.version?"matching":"conflict";
                        if(b[p]!=5){status="unresolved";reasons.push_back("AIT carriage declaration requires stream_type 0x05");}
                        if(!present){status="unresolved";reasons.push_back("No application_signalling_descriptor in this elementary-stream loop");}
                        if(malformed||!validDescriptor)status="unresolved";
                        if(pids.size()!=1){status="conflict";reasons.push_back("PAT declares conflicting PMT PIDs for this program; no owner selected");}
                        if(versionStatus=="conflict"){status="conflict";reasons.push_back("Advertised current AIT version conflicts with observed AIT or other advertisements");}
                        const std::string id=aitNode+":carriage:"+std::to_string(tsid)+":"+std::to_string(program)+":"+r->id+":"+std::to_string(p);
                        J attrs={{"stream_type",b[p]},{"descriptor_present",present},{"valid_descriptor_present",validDescriptor},{"advertised_application_types",types},{"advertised_ait_versions",versions},{"version_signalling",versionStatus},{"version_signalling_scope","validated_descriptor_entries_only"},{"descriptor_validation",malformed?(validDescriptor?"mixed":"invalid"):validDescriptor?"valid":"missing"},{"application_type_advertisement",types.count(ait.ext&32767)?"listed":malformed?"unavailable_malformed_descriptor":types.empty()?"not_signalled":"not_listed"},{"runtime_compatibility","not_evaluated"},{"component_carousel_relation","unsupported"}};
                        cards.push_back({{"node_id",id},{"family","dvb"},{"object_type","application_carriage"},{"identity",{{"transport_stream_id",tsid},{"program_number",program},{"pmt_pid",pid},{"ait_pid",ait.pid},{"application_type",ait.ext&32767},{"observed_ait_version",ait.version},{"test_application_flag",bool(ait.ext&32768)}}},{"label","AIT carriage · program "+topology::hexid(program)},{"parent_id",aitNode},{"attributes",attrs},{"attribute_conflicts",J::object()},{"observation_status","observed"},{"resolution_status",status},{"unresolved_reasons",reasons},{"evidence",ev}});
                        programCards.push_back(cards.size()-1);p=next;
                    }
                }
                if(programCards.size()>1)for(size_t index:programCards){cards[index]["resolution_status"]="conflict";cards[index]["unresolved_reasons"].push_back("Multiple elementary-stream declarations repeat this AIT PID in the same program");}
            }
        }
        if(cards.empty())return stop("unresolved","No complete PAT-selected PMT references this AIT PID at the selected cutoff");
        if(summary["objects"].size()+cards.size()>4096||summary["relations"].size()+cards.size()>8192)return stop("resource_limit","Application graph limit prevents carriage enrichment");
        for(const auto& card:cards){const std::string status=card["resolution_status"];unresolved|=status!="resolved";const bool declaration=card["attributes"]["stream_type"]==5&&card["attributes"]["valid_descriptor_present"];
            relations.push_back({{"edge_id",card["node_id"].get<std::string>()+":declares_carriage"},{"from",card["node_id"]},{"to",aitNode},{"relation",declaration?"declares_carriage":"references_ait_pid"},{"resolution_status",status},{"evidence",card["evidence"]}});
            summary["objects"].push_back(card);
        }
        for(const auto& relation:relations)summary["relations"].push_back(relation);
        context["status"]=unresolved?"incomplete":"ok";context["carriage_count"]=cards.size();summary["carriage_context"]=context;
        if(unresolved)summary["status"]="incomplete";
    }catch(const LimitError& error){return stop("resource_limit",error.what());}
    catch(const std::exception& error){return stop("unresolved",error.what());}
    return summary;
}
}
