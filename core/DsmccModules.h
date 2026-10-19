#pragma once
#include "DsmccSection.h"
#include "tsSHA256.h"

namespace dsmccsignalling {
struct SourceOccurrence {const Record* record=nullptr;uint64_t packet=0,order=0;};
struct ModuleState {
    uint16_t id=0,blockSize=0;uint8_t version=0;uint32_t size=0;
    uint64_t epochOrder=0,epochPacket=0;
    Bytes info;
    std::string status="incomplete",sha256;
    std::vector<std::string> reasons;
    std::set<uint8_t> versionCandidates;
    std::map<std::string,SourceOccurrence> sources;
    std::map<uint16_t,const Record*> blocks;
    size_t expectedBlocks=0,duplicateObservations=0;
};
struct ModuleSnapshot {
    std::string status="ok";
    std::vector<std::string> diagnostics;
    std::map<uint16_t,ModuleState> modules;
    size_t orphanBlocks=0,invalidMessages=0,observations=0;
};
inline constexpr size_t MaxModuleBytes=16*1024*1024,MaxSnapshotBytes=64*1024*1024,MaxModuleSources=2048,MaxSnapshotSources=8192,MaxModules=256,MaxVariants=4096,MaxObservations=200000,MaxRecordScan=20000,MaxDeclarationVisits=65536;
inline void problem(ModuleState& state,const std::string& status,const std::string& reason) {
    if(state.status!="resource_limit"&&(state.status!="conflict"||status=="resource_limit"))state.status=status;
    if(std::find(state.reasons.begin(),state.reasons.end(),reason)==state.reasons.end()&&state.reasons.size()<32)state.reasons.push_back(reason);
}
inline bool source(ModuleState& state,const Record& record,uint64_t packet,uint64_t order) {
    if(state.sources.count(record.id))return true;
    if(state.sources.size()>=MaxModuleSources){problem(state,"resource_limit","Module source-evidence limit exceeded (2048)");return false;}
    state.sources.emplace(record.id,SourceOccurrence{&record,packet,order});return true;
}
inline ModuleSnapshot reconstruct(ts::DuckContext& duck,const std::vector<Record>& records,unsigned pid,uint32_t downloadId,uint64_t cutoff) {
    ModuleSnapshot out;
    auto limit=[&](const std::string& why){out.status="resource_limit";out.diagnostics.push_back(why);return out;};
    if(records.size()>MaxRecordScan)return limit("Capture record scan limit exceeded (20000)");
    struct Parsed {const Record* record;Message message;size_t observations;};
    struct Event {size_t parsed,index;uint64_t order;};
    std::vector<Parsed> parsed;size_t eventCount=0,totalDeclarations=0;uint64_t declarationVisits=0;
    for(const auto& record:records){
        if(record.pid!=pid||!record.valid||!record.current||record.ends.empty()||record.ends.front()>cutoff||(record.tid!=0x3b&&record.tid!=0x3c))continue;
        const auto& b=record.raw;
        if(b.size()<24)continue;
        const unsigned mid=unsigned(b[10])<<8|b[11];
        if((record.tid==0x3b&&mid!=0x1002&&mid!=0x1005)||(record.tid==0x3c&&mid!=0x1003))continue;
        const size_t idOffset=record.tid==0x3c?12:20;
        if(idOffset+4>b.size()-4)continue;
        const uint32_t id=uint32_t(b[idOffset])<<24|uint32_t(b[idOffset+1])<<16|uint32_t(b[idOffset+2])<<8|b[idOffset+3];
        // Unsupported adaptation can obscure the identifier, so it is a barrier
        // for every download on this PID rather than a guessed association.
        if(id!=downloadId && !(record.tid==0x3b && b[17]!=0))continue;
        if(parsed.size()>=MaxVariants)return limit("DSM-CC variant limit exceeded (4096)");
        const size_t count=std::upper_bound(record.ends.begin(),record.ends.end(),cutoff)-record.ends.begin();
        if(count>MaxObservations-eventCount)return limit("DSM-CC occurrence limit exceeded (200000)");eventCount+=count;
        auto decoded=parse(duck,record);
        if(decoded.modules.size()>4096-totalDeclarations)return limit("DII declaration processing limit exceeded (4096)");totalDeclarations+=decoded.modules.size();
        declarationVisits+=uint64_t(decoded.modules.size())*count;
        if(declarationVisits>MaxDeclarationVisits)return limit("DII declaration occurrence work limit exceeded (65536)");
        parsed.push_back({&record,std::move(decoded),count});
    }
    std::vector<Event> events;events.reserve(eventCount);
    for(size_t i=0;i<parsed.size();++i)for(size_t n=0;n<parsed[i].observations;++n)events.push_back({i,n,parsed[i].record->orders.at(n)});
    std::sort(events.begin(),events.end(),[](const auto& a,const auto& b){return a.order<b.order;});out.observations=eventCount;
    std::map<std::string,SourceOccurrence> barriers;size_t currentSources=0;
    auto addSource=[&](ModuleState& state,const Record& record,uint64_t packet,uint64_t order){
        if(state.sources.count(record.id))return true;
        if(currentSources>=MaxSnapshotSources){out.status="resource_limit";out.diagnostics.push_back("Snapshot source-evidence limit exceeded (8192)");return false;}
        if(!source(state,record,packet,order))return false;++currentSources;return true;
    };
    for(const auto& event:events){
        const auto& entry=parsed[event.parsed];const auto& record=*entry.record;const auto& message=entry.message;const uint64_t packet=record.ends.at(event.index);
        if(!message.valid){
            ++out.invalidMessages;
            // Do not borrow a past announcement through malformed replacement or
            // unsupported DownloadCancel signalling in this bounded first slice.
            if(record.tid==0x3b||record.raw.size()<30||record.raw[17]!=0){
                if(!barriers.count(record.id)&&barriers.size()>=MaxModuleSources)return limit("Unresolved message evidence exceeds source limit (2048)");
                barriers[record.id]={&record,packet,event.order};
            }
            else if(record.raw.size()>=30){const unsigned id=unsigned(record.raw[20])<<8|record.raw[21];auto found=out.modules.find(id);if(found!=out.modules.end()&&found->second.version==record.raw[22]){addSource(found->second,record,packet,event.order);problem(found->second,"conflict","Malformed DDB observed after matching announcement");}}
            if(out.status=="resource_limit")return out;
            continue;
        }
        if(!message.ddb){
            std::map<uint16_t,size_t> counts;for(const auto& module:message.modules)++counts[module.id];std::set<uint16_t> declared;
            for(const auto& module:message.modules){
                auto found=out.modules.find(module.id);
                if(found==out.modules.end()&&out.modules.size()>=MaxModules)return limit("Module identity limit exceeded (256)");
                Bytes info(record.raw.begin()+module.infoOffset,record.raw.begin()+module.infoOffset+module.infoLength);
                const bool duplicateVersion=!declared.insert(module.id).second;
                if(found==out.modules.end()||(found->second.version!=module.version&&!duplicateVersion)){
                    if(found!=out.modules.end())currentSources-=found->second.sources.size();
                    ModuleState state;state.id=module.id;state.version=module.version;state.size=module.size;state.blockSize=message.blockSize;state.info=std::move(info);state.epochOrder=event.order;state.epochPacket=packet;state.versionCandidates.insert(module.version);
                    if(!state.blockSize)problem(state,"invalid_announcement","Announced block size is zero; no default substituted");
                    else if(!state.size)problem(state,"unsupported_empty_module","Empty-module reconstruction is outside this slice");
                    else if(state.size>MaxModuleBytes)problem(state,"resource_limit","Declared module exceeds 16 MiB byte limit");
                    else {const uint64_t expected=(uint64_t(state.size)+state.blockSize-1)/state.blockSize;if(expected>=MaxModuleSources)problem(state,"resource_limit","Required blocks plus announcement exceed source limit (2048)");else state.expectedBlocks=size_t(expected);}
                    found=out.modules.insert_or_assign(module.id,std::move(state)).first;
                }else if(found->second.version!=module.version||found->second.size!=module.size||found->second.blockSize!=message.blockSize||found->second.info!=info)problem(found->second,"conflict","Same-version module announcements disagree; no latest-wins selection");
                found->second.versionCandidates.insert(module.version);
                addSource(found->second,record,packet,event.order);
                if(counts[module.id]>1)problem(found->second,"conflict","Duplicate module identifier in one DII");
            }
        }else{
            auto found=out.modules.find(message.moduleId);
            if(found==out.modules.end()||found->second.version!=message.moduleVersion){++out.orphanBlocks;continue;}
            auto& state=found->second;
            if(!addSource(state,record,packet,event.order)||!state.expectedBlocks){if(out.status=="resource_limit")return out;continue;}
            if(message.blockNumber>=state.expectedBlocks){problem(state,"conflict","DDB block number exceeds announced module extent");continue;}
            const uint64_t offset=uint64_t(message.blockNumber)*state.blockSize;const size_t expected=size_t(std::min<uint64_t>(state.blockSize,uint64_t(state.size)-offset));
            if(message.dataLength!=expected){problem(state,"conflict","DDB data length disagrees with announced block or exact final-block size");continue;}
            const auto old=state.blocks.find(message.blockNumber);
            if(old!=state.blocks.end()){
                ++state.duplicateObservations;
                const auto& previous=old->second->raw;
                if(!std::equal(record.raw.begin()+message.dataOffset,record.raw.begin()+message.dataOffset+message.dataLength,previous.begin()+26))problem(state,"conflict","Conflicting duplicate block bytes retained; no block chosen");
            }else state.blocks.emplace(message.blockNumber,&record);
        }
        if(out.status=="resource_limit")return out;
    }
    // Resolve all blocking evidence before budgeting hash work. Unsupported
    // large declarations do not consume another independent module's budget.
    for(auto& [id,state]:out.modules){
        for(const auto& [sid,barrier]:barriers)if(barrier.order>=state.epochOrder){addSource(state,*barrier.record,barrier.packet,barrier.order);problem(state,"unresolved","Unsupported or malformed DSM-CC evidence obscures applicable announcement/block identity");}
        if(out.status=="resource_limit")return out;
    }
    uint64_t hashBytes=0;
    for(const auto& [id,state]:out.modules)if(state.status=="incomplete"&&state.expectedBlocks&&state.blocks.size()==state.expectedBlocks)hashBytes+=state.size;
    if(hashBytes>MaxSnapshotBytes)return limit("Eligible complete-module bytes exceed 64 MiB hash-work limit");
    for(auto& [id,state]:out.modules){
        if(state.status!="incomplete")continue;
        if(state.blocks.size()!=state.expectedBlocks){problem(state,"incomplete","Captured module has missing blocks");continue;}
        ts::SHA256 hash;if(!hash.init()){problem(state,"unresolved","SHA-256 provider could not initialize");continue;}
        bool success=true;uint64_t bytes=0;
        for(const auto& [number,record]:state.blocks){const size_t length=record->raw.size()-30;bytes+=length;success=hash.add(record->raw.data()+26,length)&&success;}
        uint8_t digest[ts::SHA256::HASH_SIZE];success=hash.getHash(digest,sizeof(digest))&&success;
        if(!success||bytes!=state.size){problem(state,"unresolved","Module hash/length verification failed");continue;}
        static constexpr char digits[]="0123456789abcdef";for(auto byte:digest){state.sha256+=digits[byte>>4];state.sha256+=digits[byte&15];}state.status="complete";
    }
    return out;
}
}
