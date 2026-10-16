#include "tsDuckContext.h"
#include "tsNullReport.h"
#include "tsSectionDemux.h"
#include "tsSection.h"
#include "tsTSPacket.h"
#include "tsSectionFile.h"
#include "tsSDT.h"
#include "tsServiceDescriptor.h"
#include "tsShortEventDescriptor.h"
#include "tsMJD.h"
#include "tsMGT.h"
#include "tsNames.h"
#include "tsCharset.h"
#include "tsPSIRepository.h"
#include "tsAbstractTable.h"
#include "tsxmlDocument.h"
#include "tsxmlElement.h"
#include "nlohmann/json.hpp"
#include <fstream>
#include <iostream>
#include <filesystem>
#include <chrono>
#include <unordered_map>
#include <iomanip>
#include <functional>
#include <algorithm>
#include <cstring>
#include <map>
#include <sstream>
#include <cstdio>
#include <set>
#include <tuple>

using J = nlohmann::json;
using Bytes = std::vector<uint8_t>;
namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;
static double ms(Clock::time_point t) { return std::chrono::duration<double,std::milli>(Clock::now()-t).count(); }
static unsigned u16(const Bytes& b,size_t p) { return unsigned(b.at(p))*256+b.at(p+1); }
static std::string hex(const uint8_t* p,size_t n) { std::ostringstream o; o<<std::hex<<std::uppercase<<std::setfill('0'); for(size_t i=0;i<n;i++) o<<std::setw(2)<<int(p[i]); return o.str(); }
static std::string hex(const Bytes& b) { return hex(b.data(),b.size()); }
static std::string fingerprint(const Bytes& b) { uint64_t h=14695981039346656037ULL; for(auto c:b) { h^=c; h*=1099511628211ULL; } std::ostringstream o; o<<std::hex<<h; return o.str(); }
static J readJson(const fs::path& p) { std::ifstream in(p); if(!in) throw std::runtime_error("Cannot open "+p.u8string()); J j; in>>j; return j; }
static std::string tableName(int tid) { switch(tid) {case 0:return "PAT";case 1:return "CAT";case 2:return "PMT";case 0x40:case 0x41:return "NIT";case 0x42:case 0x46:return "SDT";case 0x4a:return "BAT";case 0x70:return "TDT";case 0x73:return "TOT";} if(tid>=0x4e&&tid<=0x6f)return "EIT"; return "Private / other"; }
static void emit(const J& j) { std::cout<<j.dump(-1,' ',false,J::error_handler_t::replace)<<'\n'<<std::flush; }

static std::string standardsNames(ts::Standards mask) {
    std::string names;
    for(const auto& item:std::vector<std::pair<ts::Standards,const char*>>{{ts::Standards::MPEG,"MPEG"},{ts::Standards::DVB,"DVB"},{ts::Standards::ATSC,"ATSC"},{ts::Standards::ISDB,"ISDB"},{ts::Standards::JAPAN,"JAPAN"},{ts::Standards::ABNT,"ABNT"},{ts::Standards::SCTE,"SCTE"}})
        if((mask&item.first)!=ts::Standards::NONE){if(!names.empty())names+=", ";names+=item.second;}
    return names.empty()?"none":names;
}
static J xmlTree(const ts::xml::Element* element) {
    if(!element)return nullptr;
    J tree={{"name",element->name().toUTF8()},{"attributes",J::object()},{"children",J::array()}};
    std::map<ts::UString,ts::UString> attributes;element->getAttributes(attributes);
    for(const auto& [name,value]:attributes)tree["attributes"][name.toUTF8()]=value.toUTF8();
    ts::UString text;element->getText(text,true);if(!text.empty())tree["text"]=text.toUTF8();
    for(auto* child=element->firstChildElement();child;child=child->nextSiblingElement())tree["children"].push_back(xmlTree(child));
    return tree;
}

// Exclusive creation protects both the source and competing exports. Failed
// data/manifest writes are removed; success is returned only after both close.
class ExportFile {
    fs::path path; std::FILE* file=nullptr; bool committed=false;
public:
    explicit ExportFile(const fs::path& p):path(p) {
#ifdef _WIN32
        file=_wfopen(path.c_str(),L"wbx");
#else
        file=std::fopen(path.c_str(),"wbx");
#endif
        if(!file)throw std::runtime_error("Cannot exclusively create output (it may already exist): "+path.u8string());
    }
    ExportFile(const ExportFile&)=delete;
    ExportFile& operator=(const ExportFile&)=delete;
    ~ExportFile(){if(file)std::fclose(file);if(!committed){std::error_code ignored;fs::remove(path,ignored);}}
    void write(const void* data,size_t bytes){if(std::fwrite(data,1,bytes,file)!=bytes)throw std::runtime_error("Output write failed: "+path.u8string());}
    void close(){auto* f=file;file=nullptr;if(f&&std::fclose(f)!=0)throw std::runtime_error("Output close failed: "+path.u8string());}
    void commit(){committed=true;}
};

struct Record {
    std::string id,key; Bytes raw; unsigned pid=0,tid=0,ext=0,version=0,number=0,last=0; bool valid=true,current=true;
    std::vector<uint64_t> positions,ends; uint64_t lastPacket=0;
    J descriptors=J::array(),services=J::array(),events=J::array(),issues=J::array(),fields=J::object();
};

class Engine : public ts::SectionHandlerInterface, public ts::InvalidSectionHandlerInterface {
    fs::path root,source; ts::DuckContext duck { &NULLREP }; J extension=J::object(),configuredExtension=J::object();
    std::vector<Record> records; std::unordered_map<std::string,size_t> ids; J history=J::array();
    std::unordered_map<std::string,std::string> previous;
    uint64_t packets=0,totalBytes=0,observations=0,crcErrors=0; size_t stride=188,prefix=0;
    double bitrate=0,firstMs=-1,totalMs=0; Clock::time_point began;
    std::string standardsContext="auto";
    J requestId; std::function<void()> onFirst; bool complete=false; size_t revision=0;
    J pending=J::object(), demuxStatus=J::object(); std::vector<std::pair<unsigned,Bytes>> patchSections;
    std::map<std::string,const Record*> latest(uint64_t at) const {
        std::map<std::string,const Record*> chosen;
        std::map<std::string,std::pair<uint64_t,unsigned>> generations;
        for(const auto& r:records)if(r.valid&&r.current){
            auto end=std::upper_bound(r.ends.begin(),r.ends.end(),at);if(end==r.ends.begin())continue;
            std::string group=std::to_string(r.pid)+":"+std::to_string(r.tid)+":"+std::to_string(r.ext);
            if(generations[group].first<=*(end-1))generations[group]={*(end-1),r.version};
            auto found=chosen.find(r.key);
            if(found==chosen.end()||*(end-1)>=*std::prev(std::upper_bound(found->second->ends.begin(),found->second->ends.end(),at)))chosen[r.key]=&r;
        }
        for(auto it=chosen.begin();it!=chosen.end();){const auto&r=*it->second;std::string group=std::to_string(r.pid)+":"+std::to_string(r.tid)+":"+std::to_string(r.ext);if(r.version!=generations.at(group).second)it=chosen.erase(it);else ++it;}
        return chosen;
    }
    bool completeGroup(const Record& r,const std::map<std::string,const Record*>& selected) const {
        for(unsigned i=0;i<=r.last;i++){
            auto it=selected.find(std::to_string(r.pid)+":"+std::to_string(r.tid)+":"+std::to_string(r.ext)+":"+std::to_string(i));
            if(it==selected.end()||it->second->version!=r.version||it->second->last!=r.last)return false;
        }
        return true;
    }

    void issue(Record& r,const std::string& code,size_t offset,const std::string& detail) {
        r.valid=false; r.issues.push_back({{"code",code},{"section_offset",offset},{"detail",detail}});
    }
    J descriptors(Record& r,size_t begin,size_t end,int serviceId=-1,const std::set<uint32_t>& inheritedRegistrations={}) {
        J result=J::object(); uint32_t pds=0;
        ts::DuckContext descriptorDuck(&NULLREP);descriptorDuck.resetStandards(duck.standards());descriptorDuck.setDefaultCharsetIn(duck.charsetIn());descriptorDuck.setDefaultCharsetOut(duck.charsetOut());descriptorDuck.setTimeReferenceOffset(duck.timeReferenceOffset());
        for(auto registration:inheritedRegistrations)descriptorDuck.addRegistrationId(registration);
        if(end>r.raw.size()-4) { issue(r,"descriptor_loop_overrun",begin,"Descriptor loop exceeds section payload"); return result; }
        for(size_t p=begin;p<end;) {
            if(p+2>end) { issue(r,"descriptor_header_truncated",p,"Missing descriptor length"); break; }
            size_t n=r.raw[p+1],next=p+2+n; int tag=r.raw[p];
            J d={{"tag",tag},{"length",n},{"offset",p},{"service_id",serviceId},{"pds",pds},{"name","opaque_descriptor"},{"raw",hex(r.raw.data()+p,std::min(next,end)-p)},{"fields",J::object()}};
            if(next>end) { issue(r,"descriptor_length",p,"Declared length exceeds descriptor loop; raw bytes retained"); d["malformed"]=true; r.descriptors.push_back(d); break; }
            ts::Descriptor bin(r.raw.data()+p,n+2);
            ts::xml::Document nativeDocument;auto* parent=nativeDocument.initialize(u"descriptor");
            if(auto* native=bin.toXML(descriptorDuck,parent,pds,ts::TID(r.tid))){d["native"]=xmlTree(native);d["name"]=native->name().toUTF8();d["native_decoded"]=native->name()!=u"generic_descriptor";}

            if(tag==0x05&&n>=4)descriptorDuck.addRegistrationId((uint32_t(u16(r.raw,p+2))<<16)|u16(r.raw,p+4));
            if(tag==0x5f&&n==4) { pds=(uint32_t(u16(r.raw,p+2))<<16)|u16(r.raw,p+4); d["name"]="private_data_specifier_descriptor"; d["fields"]["private_data_specifier"]=pds; }
            else if(tag==0x48) {
                ts::ServiceDescriptor native(duck,bin); d["name"]="service_descriptor";
                if(native.isValid()) { result["name"]=native.service_name.toUTF8(); result["provider"]=native.provider_name.toUTF8(); result["type"]=native.service_type; d["fields"]=result; }
                else issue(r,"service_descriptor_invalid",p,"TSDuck rejected service descriptor");
            } else if(tag==0x4d) {
                ts::ShortEventDescriptor native(duck,bin); d["name"]="short_event_descriptor";
                if(native.isValid()) { result["title"]=native.event_name.toUTF8(); result["text"]=native.text.toUTF8(); d["fields"]=result; }
                else issue(r,"short_event_descriptor_invalid",p,"TSDuck rejected event descriptor");
            }
            for(const auto& spec:extension.value("descriptors",J::array())) {
                if(spec.at("tag")!=tag || spec.at("pds")!=pds) continue;
                const auto& tids=spec.at("table_ids"); if(std::find(tids.begin(),tids.end(),J(r.tid))==tids.end()) continue;
                d["name"]=spec.at("name"); d["extension"]=extension.at("id");
                if(n!=spec.at("payload_bytes").get<size_t>()) { issue(r,"private_descriptor_length",p,"Length rejected by loaded extension schema"); continue; }
                for(const auto& f:spec.at("fields")) {
                    size_t off=f.at("offset"); std::string type=f.at("type"),name=f.at("name"); size_t width=type=="u16be"?2:1;
                    if(off+width>n) { issue(r,"private_field_bounds",p,"Extension field exceeds payload"); continue; }
                    unsigned value=width==2?u16(r.raw,p+2+off):r.raw[p+2+off];
                    J display=value; std::string key=std::to_string(value);
                    if(f.contains("labels")&&f["labels"].contains(key))display=f["labels"][key];
                    d["fields"][name]=display; result[name]=display;
                }
            }
            r.descriptors.push_back(d); p=next;
        }
        return result;
    }
    void decode(Record& r) {
        const auto& b=r.raw; size_t end=b.size()>=4?b.size()-4:0;
        if(!r.valid)return;
        if((r.tid==0x42||r.tid==0x46)&&b.size()>=15) {
            r.fields["transport_stream_id"]=r.ext; r.fields["original_network_id"]=u16(b,8);
            for(size_t p=11;p<end;) {
                if(p+5>end){issue(r,"service_loop_truncated",p,"Incomplete SDT service header");break;}
                int sid=u16(b,p); size_t n=u16(b,p+3)&0xfff;
                J s={{"id",sid},{"name","Service "+std::to_string(sid)},{"provider",""},{"group","Unassigned"},{"logical_channel_number",nullptr},{"source_id",r.id},{"ts_id",r.ext},{"onid",u16(b,8)},{"encrypted",(b[p+3]&0x10)!=0}};
                J decoded=descriptors(r,p+5,p+5+n,sid); s.update(decoded); r.services.push_back(s); p+=5+n;
            }
        } else if(r.tid==0&&b.size()>=12) {
            r.fields["programs"]=J::array();
            for(size_t p=8;p+4<=end;p+=4)r.fields["programs"].push_back({{"service_id",u16(b,p)},{"pmt_pid",u16(b,p+2)&0x1fff}});
            if((end-8)%4) issue(r,"pat_length",8,"PAT program loop is not a multiple of four");
        } else if(r.tid==2&&b.size()>=16) {
            r.fields["pcr_pid"]=u16(b,8)&0x1fff; r.fields["streams"]=J::array();
            size_t n=u16(b,10)&0xfff; descriptors(r,12,12+n);
            std::set<uint32_t> programRegistrations;
            for(size_t p=12;p+2<=std::min(12+n,end);){size_t next=p+2+b[p+1];if(next>std::min(12+n,end))break;if(b[p]==0x05&&b[p+1]>=4)programRegistrations.insert((uint32_t(u16(b,p+2))<<16)|u16(b,p+4));p=next;}
            for(size_t p=12+n;p<end;) {
                if(p+5>end){issue(r,"pmt_stream_truncated",p,"Incomplete stream header");break;}
                size_t len=u16(b,p+3)&0xfff;
                r.fields["streams"].push_back({{"pid",u16(b,p+1)&0x1fff},{"type",b[p]}});
                descriptors(r,p+5,p+5+len,-1,programRegistrations);p+=5+len;
            }
        } else if(r.tid==1&&b.size()>=12) {
            descriptors(r,8,end);
        } else if((r.tid==0x40||r.tid==0x41||r.tid==0x4a)&&b.size()>=16) {
            r.fields[r.tid==0x4a?"bouquet_id":"network_id"]=r.ext;
            size_t n=u16(b,8)&0xfff;descriptors(r,10,10+n);
            size_t p=10+n;if(p+2>end){issue(r,"transport_loop_truncated",p,"Missing transport loop length");return;}
            size_t stop=p+2+(u16(b,p)&0xfff);p+=2;r.fields["transports"]=J::array();
            if(stop!=end){issue(r,"transport_loop_length",p-2,"Transport loop does not match section payload");return;}
            while(p<stop){
                if(p+6>stop){issue(r,"transport_loop_truncated",p,"Incomplete transport header");break;}
                size_t len=u16(b,p+4)&0xfff;
                if(p+6+len>stop){issue(r,"transport_descriptor_overrun",p+4,"Transport descriptors exceed loop");break;}
                r.fields["transports"].push_back({{"transport_stream_id",u16(b,p)},{"original_network_id",u16(b,p+2)},{"descriptor_offset",p+6},{"descriptor_bytes",len}});
                descriptors(r,p+6,p+6+len);p+=6+len;
            }
        } else if(r.tid==0x70||r.tid==0x73) {
            const size_t minimum=r.tid==0x70?8:14;
            if(b.size()<minimum){issue(r,"time_table_truncated",3,"Incomplete UTC time table");return;}
            ts::Time time;bool ok=ts::DecodeMJD(b.data()+3,ts::MJD_FULL,time);
            if(ok)time-=duck.timeReferenceOffset();r.fields["utc_time"]=ok?time.toString().toUTF8():"Unknown";
            if(!ok)issue(r,"utc_time_invalid",3,"Invalid MJD UTC time");
            if(r.tid==0x70&&b.size()!=8)issue(r,"tdt_length",0,"TDT must be exactly eight bytes");
            if(r.tid==0x73){size_t n=u16(b,8)&0xfff;if(10+n!=end)issue(r,"tot_length",8,"TOT descriptor loop does not match section payload");else descriptors(r,10,end);}
        } else if(r.tid>=0x4e&&r.tid<=0x6f&&b.size()>=18) {
            for(size_t p=14;p<end;) {
                if(p+12>end){issue(r,"eit_event_truncated",p,"Incomplete event header");break;}
                auto bcd=[](uint8_t v){return (v>>4)*10+(v&15);}; ts::Time time;
                bool ok=ts::DecodeMJD(b.data()+p+2,ts::MJD_FULL,time);if(ok)time-=duck.timeReferenceOffset();
                size_t len=u16(b,p+10)&0xfff;
                J e={{"id",u16(b,p)},{"service_id",r.ext},{"ts_id",u16(b,8)},{"onid",u16(b,10)},{"title","Untitled event"},{"start",ok?time.toString().toUTF8():"Unknown"},{"duration_seconds",bcd(b[p+7])*3600+bcd(b[p+8])*60+bcd(b[p+9])},{"source_id",r.id}};
                e.update(descriptors(r,p+12,p+12+len,r.ext));r.events.push_back(e);p+=12+len;
            }
        }
    }
    void receive(const uint8_t* data,size_t size,unsigned pid,uint64_t first,uint64_t last,bool valid) {
        if(size<3)return;
        ++observations; Bytes b(data,data+size);
        unsigned tid=b[0],ext=size>=8&&(b[1]&0x80)?u16(b,3):0;
        unsigned ver=size>=8&&(b[1]&0x80)?(b[5]>>1)&31:0,num=size>=8&&(b[1]&0x80)?b[6]:0;
        std::string key=std::to_string(pid)+":"+std::to_string(tid)+":"+std::to_string(ext)+":"+std::to_string(num);
        std::string id=key+":"+fingerprint(b);
        auto it=ids.find(id);
        if(it==ids.end()) {
            if(records.size()>=50000)throw std::runtime_error("Unique-section limit (50000) exceeded; narrow input");
            Record r; r.id=id;r.key=key;r.raw=std::move(b);r.pid=pid;r.tid=tid;r.ext=ext;r.version=ver;r.number=num;r.valid=valid;
            r.current=size>=8&&(data[1]&0x80)?(data[5]&1)!=0:true;r.last=size>=8&&(data[1]&0x80)?data[7]:0;
            if(!valid) {
                if(size>=12&&(data[1]&0x80)&&ts::CRC32(data,size).value()!=0)issue(r,"crc32",size-4,"MPEG-2 CRC32 mismatch; excluded from derived services");
                else issue(r,"invalid_section",0,"Rejected by TSDuck section demux");
            }
            decode(r); ids[id]=records.size();records.push_back(std::move(r));it=ids.find(id);
        }
        Record& r=records[it->second];r.positions.push_back(first);r.ends.push_back(last);r.lastPacket=last;
        if(!valid && !r.issues.empty() && r.issues[0]["code"]=="crc32")++crcErrors;
        if(r.valid&&r.current) {
            if(previous[key]!=id) {
                if((tid==0x42||tid==0x46))history.push_back({{"id",id},{"version",ver},{"first_packet",first},{"last_packet",last},{"label","SDT v"+std::to_string(ver)}});
                previous[key]=id;
            }
            if(tid==0x42||tid==0x46)for(auto h=history.rbegin();h!=history.rend();++h)if((*h)["id"]==id){(*h)["last_packet"]=last;break;}
        }
        if(firstMs<0)firstMs=ms(began);
        if(observations==1&&onFirst)onFirst();
    }
    std::string nativeTableName(const Record& r) const {
        auto factory=ts::PSIRepository::Instance().getTableFactory(ts::TID(r.tid),duck.standards(),ts::PID(r.pid));
        if(factory){auto table=factory();if(table)return table->xmlName().toUTF8();}
        return tableName(r.tid)!="Private / other"?tableName(r.tid):"Unknown / private (table id "+std::to_string(r.tid)+")";
    }
    J summary(const Record& r,uint64_t at=UINT64_MAX) const {
        auto stop=std::upper_bound(r.ends.begin(),r.ends.end(),at); size_t count=size_t(stop-r.ends.begin());
        return {{"id",r.id},{"key",r.key},{"name",nativeTableName(r)},{"pid",r.pid},{"table_id",r.tid},{"extension",r.ext},{"version",r.version},{"section",r.number},{"last_section",r.last},{"current",r.current},{"valid",r.valid},{"bytes",r.raw.size()},{"count",count},{"first_packet",r.positions.empty()?0:r.positions.front()},{"last_packet",count?*(stop-1):0},{"issue_count",r.issues.size()}};
    }
public:
    explicit Engine(fs::path p):root(std::move(p)) { if(fs::exists(root/"extensions/demo.json"))extension=readJson(root/"extensions/demo.json"); configuredExtension=extension; }
    void handleSection(ts::SectionDemux& demux,const ts::Section& s) override {
        // Discover dependent signalling PIDs before later packets in this block.
        if(s.tableId()==0&&s.sourcePID()==0) { const auto* b=s.content(); for(size_t p=8;p+4<=s.size()-4;p+=4)demux.addPID(((b[p+2]&31)<<8)|b[p+3]); }
        if(s.tableId()==0xc7&&(standardsContext=="auto"||standardsContext=="atsc")&&s.sectionNumber()==0&&s.lastSectionNumber()==0){
            ts::BinaryTable binary;binary.addNewSection(s.content(),s.size(),s.sourcePID(),ts::CRC32::CHECK);ts::MGT mgt(duck,binary);
            if(mgt.isValid())for(const auto& entry:mgt.tables)demux.addPID(entry.second.table_type_PID);
        }
        if(s.tableId()==2&&s.size()>=16){
            const auto* b=s.content();size_t end=s.size()-4,p=12+(((b[10]&15)<<8)|b[11]);
            while(p+5<=end){size_t len=((b[p+3]&15)<<8)|b[p+4];if(p+5+len>end)break;
                if(b[p]==0x05||b[p]==0x0b||b[p]==0x0d||b[p]==0x13||b[p]==0x14||b[p]==0x86)demux.addPID(((b[p+1]&31)<<8)|b[p+2]);p+=5+len;
            }
        }
        receive(s.content(),s.size(),s.sourcePID(),s.firstTSPacketIndex(),s.lastTSPacketIndex(),true);
    }
    void handleInvalidSection(ts::SectionDemux&,const ts::DemuxedData& s) override { receive(s.content(),s.size(),s.sourcePID(),s.firstTSPacketIndex(),s.lastTSPacketIndex(),false); }
    J state(uint64_t at=UINT64_MAX) {
        J out={{"source",source.u8string()},{"file_name",source.filename().u8string()},{"source_bytes",totalBytes},{"packets",packets},{"packet_size",stride},{"observations",observations},{"crc_errors",crcErrors},{"complete",complete},{"revision",revision},{"extension_id",extension.value("id",std::string("none"))},{"time_basis",bitrate>0?"user supplied bitrate":"packet index"},{"bitrate",bitrate},{"tables",J::array()},{"services",J::array()},{"events",J::array()},{"history",history},{"diagnostics",J::array()},{"density",J::array()},{"metrics",{{"first_section_ms",firstMs},{"scan_ms",complete?totalMs:ms(began)}}}};
        out["text_charset"]=duck.charsetIn()->name().toUTF8();out["time_reference"]=duck.timeReferenceName().toUTF8();out["standards_context"]=standardsContext;out["detected_standards"]=standardsNames(duck.standards());
        const auto selected=latest(at);
        for(const auto& r:records) {
            auto stop=std::upper_bound(r.ends.begin(),r.ends.end(),at);if(stop==r.ends.begin())continue;
            out["tables"].push_back(summary(r,at));
            for(auto d:r.issues) { d["id"]=r.id;d["pid"]=r.pid;d["packet"]=r.positions.front();d["count"]=size_t(stop-r.ends.begin());out["diagnostics"].push_back(d); }
        }
        std::map<std::string,J> services; std::map<std::pair<unsigned,unsigned>,unsigned> pmts; std::map<std::pair<unsigned,unsigned>,J> components;
        for(const auto& [key,item]:selected) {
            const Record& r=*item;
            if((r.tid==0||r.tid==2||r.tid==0x42)&&!completeGroup(r,selected))continue;
            if(r.tid==0&&r.pid==0)for(const auto& p:r.fields.value("programs",J::array()))if(p["service_id"]!=0)pmts[{r.ext,p["service_id"].get<unsigned>()}]=p["pmt_pid"].get<unsigned>();
            if(r.tid==2)components[{r.pid,r.ext}]=r.fields;
            if(r.tid==0x42)for(const auto& s:r.services)services[std::to_string(s["onid"].get<unsigned>())+":"+std::to_string(s["ts_id"].get<unsigned>())+":"+std::to_string(s["id"].get<unsigned>())]=s;
            for(const auto& e:r.events)out["events"].push_back(e);
        }
        std::string groupBy=extension.value("organization",J::object()).value("group_by",std::string("group"));
        for(auto& [key,s]:services) { unsigned sid=s["id"];s["key"]=key;auto pat=pmts.find({s["ts_id"].get<unsigned>(),sid});s["pmt_pid"]=pat!=pmts.end()?J(pat->second):J();if(pat!=pmts.end()){auto pmt=components.find({pat->second,sid});if(pmt!=components.end())s["components"]=pmt->second;}s["group"]=s.value(groupBy,J("Unassigned"));out["services"].push_back(s); }
        std::string sort=extension.value("organization",J::object()).value("sort_by",std::string("id"));
        std::sort(out["services"].begin(),out["services"].end(),[&](const J&a,const J&b){J av=a.value(sort,J());J bv=b.value(sort,J());return (av.is_null()?a["id"]:av)<(bv.is_null()?b["id"]:bv);});
        constexpr size_t bins=80; std::vector<uint64_t> counts(bins,0),bad(bins,0); uint64_t denominator=std::max<uint64_t>(1,totalBytes/stride);
        for(const auto& r:records)for(auto pos:r.positions){size_t bucket=std::min<uint64_t>(bins-1,pos*bins/denominator);counts[bucket]++;if(!r.valid)bad[bucket]++;}
        for(size_t i=0;i<bins;i++)out["density"].push_back({{"count",counts[i]},{"bad",bad[i]}});
        out["selected_packet"]=at==UINT64_MAX?J():J(at);out["demux"]=demuxStatus;out["scope"]={{"tables_services_events","selected packet"},{"history_density_counters_demux","entire scan"}};
        if(demuxStatus.value("discontinuities",uint64_t(0))>0)out["diagnostics"].push_back({{"code","transport_discontinuity"},{"detail","TSDuck continuity-counter discontinuities on monitored PSI/SI PIDs (aggregate; packet locations not yet retained)"},{"count",demuxStatus["discontinuities"]},{"pid",0},{"packet",0},{"id",""},{"aggregate",true}});
        return out;
    }
    J analyze(const J& args,const J& rid) {
        // A new scan owns a new revision even when opening or framing fails.
        // Never allow old evidence or preview tokens to acquire a new source label.
        records.clear();ids.clear();history=J::array();previous.clear();pending=J::object();patchSections.clear();++revision;
        extension=configuredExtension;standardsContext=args.value("standards",std::string("auto"));
        ts::Standards standards=ts::Standards::MPEG;
        if(standardsContext=="dvb")standards|=ts::Standards::DVB;
        else if(standardsContext=="atsc")standards|=ts::Standards::ATSC;
        else if(standardsContext=="isdb")standards|=ts::Standards::ISDB;
        else if(standardsContext=="isdb-japan")standards|=ts::Standards::ISDB|ts::Standards::JAPAN;
        else if(standardsContext=="isdb-brazil")standards|=ts::Standards::ISDB|ts::Standards::ABNT;
        else if(standardsContext=="scte")standards|=ts::Standards::SCTE;
        duck.resetStandards(standards);duck.resetRegistrationIds();duck.setDefaultCharsetIn(nullptr);duck.setDefaultCharsetOut(nullptr);duck.setTimeReference(u"UTC");
        if(standardsContext=="isdb-japan"){duck.setDefaultCharsetIn(ts::Charset::GetCharset(u"ARIB-STD-B24"));duck.setDefaultCharsetOut(ts::Charset::GetCharset(u"ARIB-STD-B24"));duck.setTimeReference(u"JST");}
        if(standardsContext=="isdb-brazil"){duck.setDefaultCharsetIn(ts::Charset::GetCharset(u"RAW-ISO-8859-15"));duck.setDefaultCharsetOut(ts::Charset::GetCharset(u"RAW-ISO-8859-15"));duck.setTimeReference(u"UTC-3");}
        source.clear();packets=totalBytes=observations=crcErrors=0;demuxStatus=J::object();complete=false;
        firstMs=-1;totalMs=0;stride=188;prefix=0;onFirst=nullptr;bitrate=args.value("bitrate",0.0);began=Clock::now();requestId=rid;
        source=fs::absolute(fs::u8path(args.at("path").get<std::string>()));std::ifstream in(source,std::ios::binary);
        if(!in)throw std::runtime_error("Cannot read source file");totalBytes=fs::file_size(source);if(totalBytes<188)throw std::runtime_error("Source is too small for a TS packet");
        std::vector<uint8_t> probe(5*204);in.read(reinterpret_cast<char*>(probe.data()),probe.size());size_t got=size_t(in.gcount());in.clear();in.seekg(0);
        bool framing=false;
        for(size_t width:{size_t(188),size_t(192),size_t(204)}) { size_t off=width==192?4:0;bool ok=true;for(size_t i=0;i<5&&off+i*width<got;i++)ok&=probe[off+i*width]==0x47;if(ok){stride=width;prefix=off;framing=true;break;} }
        if(!framing)throw std::runtime_error("No aligned 188/192/204-byte TS framing at file start");
        ts::SectionDemux demux(duck,nullptr,this);for(unsigned pid:{0u,1u,2u,0x10u,0x11u,0x12u,0x13u,0x14u,0x16u,0x1bu,0x1cu,0x1eu,0x1fu})demux.addPID(pid);
        if(standardsContext=="auto"||standardsContext.rfind("isdb",0)==0){for(unsigned pid=0x20;pid<=0x29;pid++)demux.addPID(pid);demux.addPID(0x17);demux.addPID(0x2e);}
        if(standardsContext=="auto"||standardsContext=="atsc")for(unsigned pid:{0x1ff7u,0x1ff9u,0x1ffbu})demux.addPID(pid);
        for(const auto& pid:args.value("extra_pids",J::array())){if(!pid.is_number_integer()||pid<0||pid>8191)throw std::runtime_error("extra_pids entries must be integers in 0..8191");demux.addPID(pid.get<unsigned>());}
        for(auto pid:extension.value("extra_pids",J::array()))demux.addPID(pid.get<unsigned>());
        demux.setInvalidSectionHandler(this);demux.setCurrentNext(true,true);demux.trackInvalidSectionVersions(true);
        onFirst=[&](){emit({{"event","progress"},{"request_id",rid},{"state",state()}});};
        std::vector<uint8_t> block(stride*8192);auto lastNotify=Clock::now();
        try { while(in) {
            in.read(reinterpret_cast<char*>(block.data()),block.size());size_t n=size_t(in.gcount());
            for(size_t p=0;p+stride<=n;p+=stride){ts::TSPacket packet;std::memcpy(packet.b,block.data()+p+prefix,188);++packets;demux.feedPacket(packet);}
            if(ms(lastNotify)>=100) {emit({{"event","progress"},{"request_id",rid},{"state",state()}});lastNotify=Clock::now();}
        }
        } catch(...) {onFirst=nullptr;totalMs=ms(began);throw;}
        onFirst=nullptr;if(in.bad())throw std::runtime_error("Source read failed; analysis is incomplete");complete=true;totalMs=ms(began);
        ts::SectionDemux::Status status(demux);demuxStatus={{"wrong_crc",status.wrong_crc},{"discontinuities",status.discontinuities},{"invalid_ts",status.invalid_ts},{"invalid_length",status.inv_sect_length},{"truncated_sections",status.truncated_sect}};
        J out=state();
        out["trailing_bytes"]=totalBytes%stride;return out;
    }
    J inspect(const J& args) {
        std::string id=args.at("id");if(!ids.count(id))throw std::runtime_error("Unknown section id");const Record&r=records[ids.at(id)];
        J out=summary(r);out["raw_hex"]=hex(r.raw);out["fields"]=r.fields;out["descriptors"]=r.descriptors;out["issues"]=r.issues;out["services"]=r.services;out["events"]=r.events;
        out["occurrences"]=r.positions;out["occurrence_end_packets"]=r.ends;out["first_file_offset"]=r.positions.front()*stride+prefix;out["offset_note"]="TS packet offset, not section payload offset; a section may span packets";
        out["text_charset"]=duck.charsetIn()->name().toUTF8();out["time_reference"]=duck.timeReferenceName().toUTF8();out["standards_context"]=standardsContext;out["native_table_complete"]=false;out["native_decode_status"]="invalid section; raw evidence retained";
        if(r.valid){
            // Assemble only one observed version/current group at this occurrence.
            std::map<unsigned,const Record*> group;
            for(const auto& candidate:records)if(candidate.valid&&candidate.pid==r.pid&&candidate.tid==r.tid&&candidate.ext==r.ext&&candidate.version==r.version&&candidate.current==r.current&&candidate.last==r.last){
                auto end=std::upper_bound(candidate.ends.begin(),candidate.ends.end(),r.lastPacket);if(end==candidate.ends.begin())continue;
                auto found=group.find(candidate.number);if(found==group.end()||*(end-1)>=*std::prev(std::upper_bound(found->second->ends.begin(),found->second->ends.end(),r.lastPacket)))group[candidate.number]=&candidate;
            }
            ts::BinaryTable table;bool full=group.size()==r.last+1;
            for(unsigned i=0;i<=r.last;i++){auto found=group.find(i);if(found==group.end()){full=false;break;}const auto& part=*found->second;table.addNewSection(part.raw.data(),part.raw.size(),ts::PID(part.pid),ts::CRC32::CHECK);}
            ts::DuckContext tableDuck(&NULLREP);tableDuck.resetStandards(duck.standards());tableDuck.setDefaultCharsetIn(duck.charsetIn());tableDuck.setDefaultCharsetOut(duck.charsetOut());tableDuck.setTimeReferenceOffset(duck.timeReferenceOffset());
            ts::xml::Document document;auto* parent=document.initialize(u"tsduck");
            if(full&&table.isValid()){
                auto* native=table.toXML(tableDuck,parent);out["native_table_complete"]=true;
                if(native){out["native_table"]=xmlTree(native);const auto name=native->name();out["native_decode_status"]=(name==u"generic_long_table"||name==u"generic_short_table")?"generic raw fallback":"native TSDuck decoder";}
                out["tsduck_xml"]=document.toString().toUTF8();
            }else{ts::SectionFile file(duck);file.add(std::make_shared<ts::Section>(r.raw.data(),r.raw.size(),ts::PID(r.pid),ts::CRC32::CHECK));out["tsduck_xml"]=file.toXML().toUTF8();out["native_decode_status"]="incomplete table; raw section retained";}
        }
        out["references"]=J::array();out["reference_warnings"]=J::array();
        J sources=J::array();
        try {
            const fs::path indexPath=root/"references/standards.json";
            if(fs::exists(indexPath)){
                J index=readJson(indexPath);
                if(!index.is_object()||index.value("schema_version",0)!=1||!index.contains("sources")||!index["sources"].is_array())throw std::runtime_error("Unsupported reference index schema");
                for(const auto& reference:index["sources"]){
                    bool valid=reference.is_object();
                    for(const auto* key:{"id","title","url"})valid=valid&&reference.contains(key)&&reference[key].is_string();
                    for(const auto* key:{"standards","table_names","descriptor_names"}){
                        valid=valid&&reference.contains(key)&&reference[key].is_array();
                        if(valid)for(const auto& value:reference[key])valid=valid&&value.is_string();
                    }
                    if(valid)valid=reference["url"].get<std::string>().rfind("https://",0)==0;
                    if(valid)sources.push_back(reference);else out["reference_warnings"].push_back("Ignored malformed or non-HTTPS standard reference");
                }
            }else out["reference_warnings"].push_back("Optional standards reference index is not installed");
        }catch(const std::exception& e){out["reference_warnings"].push_back(std::string("Could not load optional standards references: ")+e.what());}
        std::set<std::string> families={"MPEG"};
        auto mask=duck.standards();
        if(standardsContext=="auto"){
            if((mask&ts::Standards::DVB)!=ts::Standards::NONE)families.insert("DVB");
            if((mask&ts::Standards::ATSC)!=ts::Standards::NONE)families.insert("ATSC");
            if((mask&ts::Standards::ISDB)!=ts::Standards::NONE)families.insert("ISDB");
            if((mask&ts::Standards::SCTE)!=ts::Standards::NONE)families.insert("SCTE");
        }else if(standardsContext.rfind("isdb",0)==0)families.insert("ISDB");
        else if(standardsContext=="dvb")families.insert("DVB");else if(standardsContext=="atsc")families.insert("ATSC");else if(standardsContext=="scte")families.insert("SCTE");
        if(standardsContext=="isdb-japan")families.insert("JAPAN");if(standardsContext=="isdb-brazil")families.insert("ABNT");
        auto references=[&](const std::string& name,const char* kind){
            J found=J::array();for(const auto& reference:sources){bool context=false;for(const auto& family:reference["standards"])context=context||families.count(family.get<std::string>());const auto& names=reference[kind];if(context&&std::find(names.begin(),names.end(),J(name))!=names.end()){
                J compact=J::object();for(const auto* field:{"id","title","url","version","scope","access","notes","standards"})if(reference.contains(field))compact[field]=reference[field];found.push_back(compact);
            }}return found;
        };
        std::function<void(J&,bool)> annotate=[&](J& node,bool table){
            if(!node.is_object())return;node["references"]=references(node.value("name",std::string()),table?"table_names":"descriptor_names");
            for(auto& child:node["children"])annotate(child,false);
        };
        if(out.contains("native_table")){annotate(out["native_table"],true);out["references"]=out["native_table"]["references"];}
        for(auto& descriptor:out["descriptors"]){descriptor["references"]=J::array();if(descriptor.contains("native")){annotate(descriptor["native"],false);descriptor["references"]=descriptor["native"]["references"];}}
        return out;
    }
    J preview(const J& args) {
        if(!complete)throw std::runtime_error("Complete a successful analysis before editing");
        pending=J::object();patchSections.clear();std::string id=args.at("id"),name=args.at("name");int sid=args.at("service_id");
        if(!ids.count(id))throw std::runtime_error("Unknown section id");const Record&r=records[ids.at(id)];
        if(!r.valid||r.tid!=0x42||r.number!=0||r.last!=0)throw std::runtime_error("Prototype rename requires a valid complete single-section actual SDT");
        if(name.empty()||name.size()>180)throw std::runtime_error("Service name must contain 1..180 UTF-8 bytes");
        ts::BinaryTable table;table.addNewSection(r.raw.data(),r.raw.size(),ts::PID(r.pid),ts::CRC32::CHECK);ts::SDT sdt(duck,table);
        if(!sdt.isValid()||!sdt.services.count(sid))throw std::runtime_error("Service is absent from target SDT");
        std::string before=sdt.services[sid].serviceName(duck).toUTF8();sdt.services[sid].setName(duck,ts::UString::FromUTF8(name));sdt.version=(sdt.version+1)%32;
        ts::BinaryTable changed;if(!sdt.serialize(duck,changed))throw std::runtime_error("TSDuck could not serialize edit");
        for(size_t i=0;i<changed.sectionCount();i++){auto s=changed.sectionAt(i);patchSections.push_back({r.pid,Bytes(s->content(),s->content()+s->size())});}
        pending={{"token",std::to_string(revision)+":"+id+":"+fingerprint(patchSections.front().second)},{"source_id",id},{"revision",revision},{"service_id",sid},{"before",before},{"after",name},{"old_version",r.version},{"new_version",sdt.version},{"crc_recomputed",true},{"writes_source",false}};
        return pending;
    }
    J exportData(const J& args) {
        if(!complete||records.empty())throw std::runtime_error("Complete a successful analysis before exporting");
        const std::string format=args.value("format",std::string("ts"));if(format!="ts"&&format!="bin")throw std::runtime_error("format must be ts or bin");
        fs::path path=fs::absolute(fs::u8path(args.at("path").get<std::string>()));
        if(fs::exists(path)||fs::exists(path.u8string()+".manifest.json"))throw std::runtime_error("Output already exists; choose a new path");
        bool patch=args.contains("preview_token");if(patch&&(pending.empty()||args["preview_token"]!=pending["token"]||pending["revision"]!=revision))throw std::runtime_error("Missing or stale edit preview token");
        uint64_t at=args.value("at_packet",UINT64_MAX);const auto selected=latest(at);
        for(const auto& [key,r]:selected)if((r->tid==0||r->tid==2||r->tid==0x42)&&!completeGroup(*r,selected))throw std::runtime_error("Incomplete PAT/PMT/SDT at selected packet; wait for all sections of one version");
        std::vector<std::pair<unsigned,Bytes>> output;J evidence=J::array();bool applied=false;
        for(const auto& [key,r]:selected){if(patch&&r->id==pending["source_id"]){output.insert(output.end(),patchSections.begin(),patchSections.end());applied=true;}else output.push_back({r->pid,r->raw});evidence.push_back(summary(*r,at));}
        if(output.empty())throw std::runtime_error("No valid current sections at selected packet");
        if(patch&&!applied)throw std::runtime_error("Edited SDT is not selected at export packet; choose matching time region");
        uint64_t nulls=args.value("null_packets",uint64_t(200));unsigned cycles=args.value("cycles",10u);if(nulls>100000||cycles<1||cycles>1000)throw std::runtime_error("Export bounded to 1..1000 cycles and 100000 null packets/cycle");
        fs::create_directories(path.parent_path());ExportFile out(path);
        std::map<unsigned,unsigned> counters;
        if(format=="bin")for(const auto& [pid,b]:output)out.write(reinterpret_cast<const char*>(b.data()),b.size());
        else for(unsigned cycle=0;cycle<cycles;cycle++) {
            for(const auto& [pid,b]:output)for(size_t p=0;p<b.size();) {
                Bytes packet(188,0xff);packet[0]=0x47;packet[1]=(pid>>8)|(p==0?0x40:0);packet[2]=pid&255;packet[3]=0x10|(counters[pid]++&15);
                size_t off=p==0?5:4;if(p==0)packet[4]=0;size_t n=std::min<size_t>(188-off,b.size()-p);std::copy_n(b.data()+p,n,packet.data()+off);p+=n;out.write(reinterpret_cast<const char*>(packet.data()),188);
            }
            Bytes packet(188,0xff);packet[0]=0x47;packet[1]=0x1f;packet[2]=0xff;packet[3]=0x10;for(uint64_t i=0;i<nulls;i++)out.write(reinterpret_cast<const char*>(packet.data()),188);
        }
        out.close();
        J receipt={{"path",path.u8string()},{"bytes",fs::file_size(path)},{"format",format},{"section_count",output.size()},{"source",source.u8string()},{"source_revision",revision},{"at_packet",at==UINT64_MAX?J():J(at)},{"selected_sections",evidence},{"edit",patch?pending:J()},{"has_media",false},{"has_pcr",false},{"timing","snapshot repetition; no original packet timing or PCR retained"},{"cycles",format=="ts"?cycles:1},{"null_packets_per_cycle",format=="ts"?nulls:0}};
        J offsets=J::array();size_t offset=0;for(const auto& [pid,b]:output){offsets.push_back({{"pid",pid},{"bin_offset",offset},{"bytes",b.size()},{"fingerprint_fnv1a",fingerprint(b)}});offset+=b.size();}receipt["sections"]=offsets;
        ExportFile manifest(fs::u8path(path.u8string()+".manifest.json"));const std::string text=receipt.dump(2)+"\n";manifest.write(text.data(),text.size());manifest.close();out.commit();manifest.commit();return receipt;
    }
    J dispatch(const std::string& method,const J& args,const J& rid) {
        if(!args.is_object())throw std::runtime_error("params must be an object");
        const auto catalog=readJson(root/"api/tools.json");
        for(const auto& tool:catalog.at("tools"))if(tool.at("name")==method){
            const auto& schema=tool.at("inputSchema");
            for(const auto& field:schema.value("required",J::array()))if(!args.contains(field.get<std::string>()))throw std::runtime_error("Required argument: "+field.get<std::string>());
            for(auto it=args.begin();it!=args.end();++it){
                if(!schema.at("properties").contains(it.key()))throw std::runtime_error("Unknown argument: "+it.key());
                const auto& rule=schema["properties"][it.key()];std::string type=rule.at("type");const auto& v=it.value();
                if((type=="string"&&!v.is_string())||(type=="integer"&&!v.is_number_integer())||(type=="number"&&!v.is_number())||(type=="array"&&!v.is_array()))throw std::runtime_error("Wrong type: "+it.key());
                if(rule.contains("maxItems")&&v.is_array()&&v.size()>rule["maxItems"].get<size_t>())throw std::runtime_error("Too many items: "+it.key());
                if(rule.contains("minimum")&&v.get<double>()<rule["minimum"].get<double>())throw std::runtime_error("Below minimum: "+it.key());
                if(rule.contains("maximum")&&v.get<double>()>rule["maximum"].get<double>())throw std::runtime_error("Above maximum: "+it.key());
                if(rule.contains("enum")&&std::find(rule["enum"].begin(),rule["enum"].end(),v)==rule["enum"].end())throw std::runtime_error("Invalid choice: "+it.key());
            }
        }
        if(method=="capabilities"){
            J result=readJson(root/"api/tools.json");ts::UStringList tables,descriptors;
            ts::PSIRepository::Instance().getRegisteredTableNames(tables);ts::PSIRepository::Instance().getRegisteredDescriptorNames(descriptors);
            J registry={{"table_names",J::array()},{"descriptor_names",J::array()},{"table_count",tables.size()},{"descriptor_count",descriptors.size()},{"note","Registered decoders, not a guarantee that every payload or regional variant is supported. Explicit standards context resolves ambiguous identifiers."}};
            for(const auto& name:tables)registry["table_names"].push_back(name.toUTF8());for(const auto& name:descriptors)registry["descriptor_names"].push_back(name.toUTF8());result["native_registry"]=registry;return result;
        }
        if(method=="analyze")return analyze(args,rid);
        if(method=="query")return state(args.value("at_packet",UINT64_MAX));
        if(method=="inspect")return inspect(args);
        if(method=="preview_rename")return preview(args);
        if(method=="export")return exportData(args);
        if(method=="load_extension") {
            J candidate=readJson(fs::u8path(args.at("path").get<std::string>()));
            auto require=[](bool ok,const std::string& message){if(!ok)throw std::runtime_error("Invalid extension: "+message);};
            auto integer=[](const J& value,uint64_t max){return value.is_number_integer()&&value>=0&&value<=max;};
            require(candidate.is_object()&&candidate.contains("id")&&candidate["id"].is_string()&&!candidate["id"].get<std::string>().empty(),"nonempty string id required");
            require(candidate.contains("descriptors")&&candidate["descriptors"].is_array(),"descriptors must be an array");
            std::set<std::tuple<uint64_t,unsigned,unsigned>> descriptorScopes;
            const std::set<std::string> reservedFields={"id","key","source_id","ts_id","onid","encrypted","service_id","pmt_pid","components","name","provider","type","title","text","start","duration_seconds"};
            for(const auto& d:candidate["descriptors"]){
                require(d.is_object(),"descriptor must be an object");
                require(d.contains("tag")&&integer(d["tag"],255),"tag must be 0..255");
                require(d.contains("pds")&&integer(d["pds"],UINT32_MAX),"pds must be 0..4294967295");
                require(d.contains("payload_bytes")&&integer(d["payload_bytes"],255),"payload_bytes must be 0..255");
                require(d.contains("name")&&d["name"].is_string(),"descriptor name must be a string");
                require(d.contains("table_ids")&&d["table_ids"].is_array(),"table_ids must be an array");
                for(const auto& tid:d["table_ids"]){
                    require(integer(tid,255),"table id must be 0..255");
                    require(descriptorScopes.emplace(d["pds"].get<uint64_t>(),tid.get<unsigned>(),d["tag"].get<unsigned>()).second,"conflicting descriptor definitions for the same PDS, table id and tag");
                }
                require(d.contains("fields")&&d["fields"].is_array(),"fields must be an array");
                std::set<std::string> fieldNames;
                for(const auto& f:d["fields"]){
                    require(f.is_object()&&f.contains("type")&&f["type"].is_string()&&f.contains("name")&&f["name"].is_string(),"field name and type must be strings");
                    const std::string name=f["name"];
                    require(!name.empty()&&!reservedFields.count(name),"field name is empty or reserved: "+name);
                    require(fieldNames.insert(name).second,"duplicate field name: "+name);
                    std::string type=f["type"];require(type=="u8"||type=="u16be","supported field types: u8,u16be");
                    require(f.contains("offset")&&integer(f["offset"],255),"field offset must be 0..255");
                    require(f["offset"].get<unsigned>()+(type=="u8"?1:2)<=d["payload_bytes"].get<unsigned>(),"field exceeds payload");
                    if(f.contains("labels")){require(f["labels"].is_object(),"labels must be an object");for(const auto& label:f["labels"])require(label.is_string(),"label values must be strings");}
                }
            }
            if(candidate.contains("extra_pids")){require(candidate["extra_pids"].is_array(),"extra_pids must be an array");for(const auto& pid:candidate["extra_pids"])require(integer(pid,8191),"extra PID must be 0..8191");}
            if(candidate.contains("organization")){require(candidate["organization"].is_object(),"organization must be an object");for(const auto* key:{"group_by","sort_by"})if(candidate["organization"].contains(key))require(candidate["organization"][key].is_string(),"organization keys must be strings");}
            // Decoding and organization stay attached to the extension used for this
            // analysis. Loading a schema only configures the next scan.
            configuredExtension=candidate;return {{"loaded",candidate["id"]},{"requires_rescan",true}};
        }
        throw std::runtime_error("Unknown method: "+method);
    }
};

int main(int argc,char**argv) {
    fs::path root=fs::current_path();for(int i=1;i+1<argc;i++)if(std::string(argv[i])=="--root")root=fs::u8path(argv[++i]);
    try {
        Engine engine(root);std::string line;
        while(std::getline(std::cin,line)) {
            J id=nullptr;
            try { J request=J::parse(line);id=request.value("id",J());J result=engine.dispatch(request.at("method"),request.value("params",J::object()),id);emit({{"id",id},{"result",result}}); }
            catch(const std::exception& e){emit({{"id",id},{"error",{{"code","request_failed"},{"message",e.what()}}}});}
        }
    } catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}
