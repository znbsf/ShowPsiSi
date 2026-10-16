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
#include <atomic>
#include <condition_variable>
#include <deque>
#include <memory>
#include <mutex>
#include <thread>

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
static void emit(const J& j) {
    const std::string line=j.dump(-1,' ',false,J::error_handler_t::replace);
    static std::mutex outputMutex;
    std::lock_guard<std::mutex> lock(outputMutex);std::cout<<line<<'\n'<<std::flush;
}

// Only this small control object is shared with the input thread. Engine and
// every TSDuck object stay on the owner thread, including final state cleanup.
struct AnalysisControl {
    std::atomic<bool> cancelled{false};
    std::mutex mutex;
    bool finished=false;
    bool requestCancellation() {
        std::lock_guard<std::mutex> lock(mutex);
        if(finished)return false;
        cancelled.store(true);return true;
    }
    bool finish() {
        std::lock_guard<std::mutex> lock(mutex);
        finished=true;return cancelled.load();
    }
};
struct CancelledAnalysis : std::exception {
    const char* what() const noexcept override { return "Analysis cancelled"; }
};
static void checkCancelled(const std::shared_ptr<AnalysisControl>& control) {
    if(control&&control->cancelled.load())throw CancelledAnalysis();
}
#ifdef SHOWPSISI_TESTING
// Supplied only by the separately built test executable. No runtime gate or
// environment-variable handling is compiled into the production executable.
static std::function<void(const char*,const std::shared_ptr<AnalysisControl>&)> testCheckpoint;
#define TEST_CHECKPOINT(stage, control) do { if(testCheckpoint)testCheckpoint(stage,control); } while(false)
#else
#define TEST_CHECKPOINT(stage, control) ((void)0)
#endif

static bool schemaType(const J& value,const std::string& type) {
    return type=="string"?value.is_string():type=="integer"?value.is_number_integer():
        type=="number"?value.is_number():type=="array"?value.is_array():
        type=="object"?value.is_object():type=="boolean"?value.is_boolean():false;
}
static void validateValue(const J& value,const J& rule,const std::string& name) {
    const auto& types=rule.at("type");bool matches=false;
    if(types.is_array()){for(const auto& type:types)matches|=schemaType(value,type.get<std::string>());}
    else matches=schemaType(value,types.get<std::string>());
    if(!matches)throw std::runtime_error("Wrong type: "+name);
    if(rule.contains("minimum")&&value.get<double>()<rule["minimum"].get<double>())throw std::runtime_error("Below minimum: "+name);
    if(rule.contains("maximum")&&value.get<double>()>rule["maximum"].get<double>())throw std::runtime_error("Above maximum: "+name);
    if(rule.contains("enum")&&std::find(rule["enum"].begin(),rule["enum"].end(),value)==rule["enum"].end())throw std::runtime_error("Invalid choice: "+name);
    if(value.is_array()){
        if(rule.contains("maxItems")&&value.size()>rule["maxItems"].get<size_t>())throw std::runtime_error("Too many items: "+name);
        if(rule.contains("items"))for(const auto& item:value)validateValue(item,rule["items"],name+" entry");
    }
}
// Pure validation over an immutable catalog is safe in the input reader. It
// prevents invalid analyses from ever being registered as cancellable work.
static void validateArguments(const J& catalog,const std::string& method,const J& args) {
    if(!args.is_object())throw std::runtime_error("params must be an object");
    for(const auto& tool:catalog.at("tools"))if(tool.at("name")==method){
        const auto& schema=tool.at("inputSchema");
        for(const auto& field:schema.value("required",J::array()))if(!args.contains(field.get<std::string>()))throw std::runtime_error("Required argument: "+field.get<std::string>());
        for(auto it=args.begin();it!=args.end();++it){
            if(!schema.at("properties").contains(it.key()))throw std::runtime_error("Unknown argument: "+it.key());
            validateValue(it.value(),schema["properties"][it.key()],it.key());
        }
        return;
    }
    throw std::runtime_error("Unknown method: "+method);
}

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
    std::vector<uint64_t> positions,ends,orders; uint64_t lastPacket=0;
    J descriptors=J::array(),services=J::array(),events=J::array(),issues=J::array(),fields=J::object();
};

class Engine : public ts::SectionHandlerInterface, public ts::InvalidSectionHandlerInterface {
    fs::path root,source; ts::DuckContext duck { &NULLREP }; J extension=J::object(),configuredExtension=J::object();
    std::vector<Record> records; std::unordered_map<std::string,size_t> ids; J history=J::array();
    std::unordered_map<std::string,std::string> previous;
    uint64_t packets=0,totalBytes=0,observations=0,crcErrors=0; size_t stride=188,prefix=0;
    double bitrate=0,firstMs=-1,totalMs=0; Clock::time_point began;
    std::string standardsContext="auto",analysisStatus="idle";
    J requestId; std::function<void()> onFirst; bool complete=false; size_t revision=0;
    J pending=J::object(), demuxStatus=J::object(); std::vector<std::pair<unsigned,Bytes>> patchSections;
    // A DVB table identity includes the network/transport identifiers in its
    // payload. table_id_extension alone is insufficient for SDT-other / EIT.
    static std::string tableGroup(const Record& r) {
        std::string key=std::to_string(r.pid)+":"+std::to_string(r.tid)+":"+std::to_string(r.ext);
        if((r.tid==0x42||r.tid==0x46)&&r.raw.size()>=11)key+=":onid="+std::to_string(u16(r.raw,8));
        if(r.tid>=0x4e&&r.tid<=0x6f&&r.raw.size()>=14)key+=":tsid="+std::to_string(u16(r.raw,8))+":onid="+std::to_string(u16(r.raw,10));
        return key;
    }
    static std::string sectionKey(const Record& r) { return tableGroup(r)+":"+std::to_string(r.number); }
    std::map<std::string,const Record*> latest(uint64_t at,bool current=true) const {
        struct Observation { const Record* record; uint64_t order; };
        std::vector<Observation> observed;
        std::map<std::string,Observation> generations;
        for(const auto& r:records)if(r.valid&&r.current==current){
            auto end=std::upper_bound(r.ends.begin(),r.ends.end(),at);if(end==r.ends.begin())continue;
            const auto group=tableGroup(r);Observation item{&r,r.orders.at(size_t(end-r.ends.begin())-1)};observed.push_back(item);
            auto found=generations.find(group);
            if(found==generations.end()||found->second.order<=item.order)generations.insert_or_assign(group,item);
        }
        // A repeated five-bit version after a different observed generation is
        // not permission to resurrect siblings from its previous cycle. A receive
        // ordinal disambiguates multiple completed sections in one TS packet.
        std::map<std::string,uint64_t> barriers;
        for(const auto& item:observed){
            const auto group=tableGroup(*item.record);const auto& newest=*generations.at(group).record;
            if(item.record->version!=newest.version||item.record->last!=newest.last){
                auto found=barriers.find(group);if(found==barriers.end()||found->second<item.order)barriers[group]=item.order;
            }
        }
        std::map<std::string,Observation> slots;
        for(const auto& item:observed){
            const auto& r=*item.record;const auto group=tableGroup(r);const auto& newest=*generations.at(group).record;
            auto barrier=barriers.find(group);
            if(r.version!=newest.version||r.last!=newest.last||(barrier!=barriers.end()&&item.order<=barrier->second))continue;
            const auto key=sectionKey(r);auto found=slots.find(key);
            if(found==slots.end()||found->second.order<=item.order)slots.insert_or_assign(key,item);
        }
        std::map<std::string,const Record*> chosen;for(const auto& [key,item]:slots)chosen[key]=item.record;return chosen;
    }
    bool completeGroup(const Record& r,const std::map<std::string,const Record*>& selected) const {
        for(unsigned i=0;i<=r.last;i++){
            auto it=selected.find(tableGroup(r)+":"+std::to_string(i));
            if(it==selected.end()||it->second->version!=r.version||it->second->last!=r.last||it->second->current!=r.current)return false;
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
            if(auto* native=bin.toXML(descriptorDuck,parent,descriptorDuck.actualPDS(pds),ts::TID(r.tid))){d["native"]=xmlTree(native);d["name"]=native->name().toUTF8();d["native_decoded"]=native->name()!=u"generic_descriptor";}

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
        Record& r=records[it->second];r.positions.push_back(first);r.ends.push_back(last);r.orders.push_back(observations);r.lastPacket=last;
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
    J derivedSnapshot(const std::map<std::string,const Record*>& selected) const {
        J out={{"services",J::array()},{"events",J::array()}};
        std::map<std::string,J> services; std::map<std::pair<unsigned,unsigned>,unsigned> pmts; std::map<std::pair<unsigned,unsigned>,J> components;
        for(const auto& [key,item]:selected) {
            const Record& r=*item;
            if((r.tid==0||r.tid==2||r.tid==0x42)&&!completeGroup(r,selected))continue;
            if(r.tid==0&&r.pid==0)for(const auto& p:r.fields.value("programs",J::array()))if(p["service_id"]!=0)pmts[{r.ext,p["service_id"].get<unsigned>()}]=p["pmt_pid"].get<unsigned>();
            if(r.tid==2)components[{r.pid,r.ext}]=r.fields;
            if(r.tid==0x42&&r.pid==0x11)for(const auto& s:r.services)services[std::to_string(s["onid"].get<unsigned>())+":"+std::to_string(s["ts_id"].get<unsigned>())+":"+std::to_string(s["id"].get<unsigned>())]=s;
            for(const auto& e:r.events)out["events"].push_back(e);
        }
        std::string groupBy=extension.value("organization",J::object()).value("group_by",std::string("group"));
        for(auto& [key,s]:services) { unsigned sid=s["id"];s["key"]=key;auto pat=pmts.find({s["ts_id"].get<unsigned>(),sid});s["pmt_pid"]=pat!=pmts.end()?J(pat->second):J();if(pat!=pmts.end()){auto pmt=components.find({pat->second,sid});if(pmt!=components.end())s["components"]=pmt->second;}s["group"]=s.value(groupBy,J("Unassigned"));out["services"].push_back(s); }
        std::string sort=extension.value("organization",J::object()).value("sort_by",std::string("id"));
        std::sort(out["services"].begin(),out["services"].end(),[&](const J&a,const J&b){J av=a.value(sort,J());J bv=b.value(sort,J());return (av.is_null()?a["id"]:av)<(bv.is_null()?b["id"]:bv);});
        return out;
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
    J state(uint64_t at=UINT64_MAX,const std::shared_ptr<AnalysisControl>& control=nullptr) {
        checkCancelled(control);
        J out={{"source",source.u8string()},{"file_name",source.filename().u8string()},{"source_bytes",totalBytes},{"packets",packets},{"packet_size",stride},{"observations",observations},{"crc_errors",crcErrors},{"complete",complete},{"analysis_status",analysisStatus},{"revision",revision},{"extension_id",extension.value("id",std::string("none"))},{"time_basis",bitrate>0?"user supplied bitrate":"packet index"},{"bitrate",bitrate},{"tables",J::array()},{"services",J::array()},{"events",J::array()},{"history",history},{"diagnostics",J::array()},{"density",J::array()},{"metrics",{{"first_section_ms",firstMs},{"scan_ms",analysisStatus=="analyzing"?ms(began):totalMs}}}};
        out["text_charset"]=duck.charsetIn()->name().toUTF8();out["time_reference"]=duck.timeReferenceName().toUTF8();out["standards_context"]=standardsContext;out["detected_standards"]=standardsNames(duck.standards());
        const auto selected=latest(at);
        for(const auto& r:records) {
            checkCancelled(control);
            auto stop=std::upper_bound(r.ends.begin(),r.ends.end(),at);if(stop==r.ends.begin())continue;
            out["tables"].push_back(summary(r,at));
            for(auto d:r.issues) { d["id"]=r.id;d["pid"]=r.pid;d["packet"]=r.positions.front();d["count"]=size_t(stop-r.ends.begin());out["diagnostics"].push_back(d); }
        }
        checkCancelled(control);const auto derived=derivedSnapshot(selected);checkCancelled(control);out["services"]=derived["services"];out["events"]=derived["events"];
        constexpr size_t bins=80; std::vector<uint64_t> counts(bins,0),bad(bins,0); uint64_t denominator=std::max<uint64_t>(1,totalBytes/stride);
        for(const auto& r:records)for(auto pos:r.positions){checkCancelled(control);size_t bucket=std::min<uint64_t>(bins-1,pos*bins/denominator);counts[bucket]++;if(!r.valid)bad[bucket]++;}
        for(size_t i=0;i<bins;i++)out["density"].push_back({{"count",counts[i]},{"bad",bad[i]}});
        out["selected_packet"]=at==UINT64_MAX?J():J(at);out["demux"]=demuxStatus;out["scope"]={{"tables_services_events","selected packet"},{"history_density_counters_demux","entire scan"},{"services","complete actual SDT on canonical PID 0x0011; nonstandard SDT PIDs remain table evidence"}};
        if(demuxStatus.value("discontinuities",uint64_t(0))>0)out["diagnostics"].push_back({{"code","transport_discontinuity"},{"detail","TSDuck continuity-counter discontinuities on monitored PSI/SI PIDs (aggregate; packet locations not yet retained)"},{"count",demuxStatus["discontinuities"]},{"pid",0},{"packet",0},{"id",""},{"aggregate",true}});
        return out;
    }
    J diffSnapshots(const J& args) const {
        if(!complete||packets==0)throw std::runtime_error("Complete a successful analysis before comparing snapshots");
        const uint64_t from=args.at("from_packet").get<uint64_t>(),to=args.at("to_packet").get<uint64_t>();
        if(from>=packets||to>=packets)throw std::runtime_error("Snapshot packet must be within the analyzed packet range (0.."+std::to_string(packets-1)+")");
        const std::string kind=args.value("kind",std::string("all"));
        const size_t offset=args.value("offset",size_t(0)),limit=args.value("limit",size_t(100));
        struct Item { J identity,value,content; std::vector<const Record*> evidence; };
        using Items=std::map<std::string,std::map<std::string,Item>>;
        auto snapshot=[&](uint64_t at){
            Items result;const auto selected=latest(at);const auto derived=derivedSnapshot(selected);
            std::map<unsigned,std::vector<const Record*>> patEvidence;
            std::map<std::pair<unsigned,unsigned>,std::vector<const Record*>> pmtEvidence;
            for(const auto& [key,ptr]:selected){
                const auto& r=*ptr;
                J identity={{"pid",r.pid},{"table_id",r.tid},{"extension",r.ext},{"section",r.number}};
                if((r.tid==0x42||r.tid==0x46)&&r.raw.size()>=11)identity["original_network_id"]=u16(r.raw,8);
                if(r.tid>=0x4e&&r.tid<=0x6f&&r.raw.size()>=14){identity["transport_stream_id"]=u16(r.raw,8);identity["original_network_id"]=u16(r.raw,10);}
                J value=summary(r,at);value["complete_group"]=completeGroup(r,selected);
                J content={{"version",r.version},{"last_section",r.last},{"payload",r.id}};
                result["tables"][key]={identity,value,content,{&r}};
                if(completeGroup(r,selected)){
                    if(r.tid==0&&r.pid==0)patEvidence[r.ext].push_back(&r);
                    if(r.tid==2)pmtEvidence[{r.pid,r.ext}].push_back(&r);
                }
            }
            for(const auto& service:derived["services"]){
                const auto& r=records.at(ids.at(service.at("source_id").get<std::string>()));
                J identity={{"original_network_id",service["onid"]},{"transport_stream_id",service["ts_id"]},{"service_id",service["id"]},{"source_pid",r.pid}};
                J content=service;content.erase("source_id");content.erase("key");
                std::vector<const Record*> sources={&r};
                // Include the exact complete PAT/PMT evidence used to derive the
                // association, never a stale PMT sharing only the service id.
                if(!service["pmt_pid"].is_null()){
                    const auto& pat=patEvidence[service["ts_id"].get<unsigned>()];sources.insert(sources.end(),pat.begin(),pat.end());
                    if(service.contains("components")){
                        const auto& pmt=pmtEvidence[{service["pmt_pid"].get<unsigned>(),service["id"].get<unsigned>()}];sources.insert(sources.end(),pmt.begin(),pmt.end());
                    }
                }
                result["services"][service.at("key").get<std::string>()]={identity,service,content,sources};
            }
            // Event identities retain EIT table/PID/section and start time.
            // This deliberately does not merge p/f and schedule evidence or a
            // reused event id at another scheduled time into one event.
            for(const auto& event:derived["events"]){
                const auto& r=records.at(ids.at(event.at("source_id").get<std::string>()));
                J identity={{"original_network_id",event["onid"]},{"transport_stream_id",event["ts_id"]},{"service_id",event["service_id"]},{"pid",r.pid},{"table_id",r.tid},{"section",r.number},{"event_id",event["id"]},{"start",event["start"]}};
                J content=event;content.erase("source_id");
                const std::string base=identity.dump();std::string key=base;size_t occurrence=0;
                // Malformed duplicate identities within one section remain
                // individually visible rather than overwriting one another.
                while(result["events"].count(key))key=base+":duplicate="+std::to_string(++occurrence);
                if(occurrence)identity["duplicate_index"]=occurrence;
                result["events"][key]={identity,event,content,{&r}};
            }
            return result;
        };
        const auto before=snapshot(from),after=snapshot(to);
        J out={{"source",source.u8string()},{"revision",revision},{"from_packet",from},{"to_packet",to},{"kind",kind},{"summary",J::object()},{"changes",J::array()},{"offset",offset},{"limit",limit},{"next_offset",nullptr}};
        out["scope"]={{"cutoffs","inclusive section completion packet indexes in this analysis revision"},{"tables","selected valid current section slots; byte/version changes, excluding repeated observations"},{"services","complete actual-SDT services on canonical PID 0x0011; other PIDs remain table evidence; PAT/PMT fields only from complete matching generations; compare derived fields, not provenance-only changes"},{"events","observed DVB-layout EIT (table ids 0x4e..0x6f) section events, separated by PID/table/section/ONID/TSID/SID/event id/start; no schedule segment completeness guarantee"},{"evidence","each side contains only occurrences completed at or before its cutoff; no scan-global history, counters or density"},{"decoding_context","fixed analysis-session standards and extension context"},{"absence","absence is observed snapshot state, not proof a service/event ceased broadcasting"},{"order","tables, services, events; lexicographic identity key within each kind"}};
        size_t total=0;
        for(const auto* category:{"tables","services","events"}){
            const std::map<std::string,Item> empty;
            const auto& a=before.count(category)?before.at(category):empty;const auto& b=after.count(category)?after.at(category):empty;
            J counts={{"added",0},{"removed",0},{"changed",0},{"unchanged",0}};
            std::set<std::string> keys;for(const auto& [key,item]:a)keys.insert(key);for(const auto& [key,item]:b)keys.insert(key);
            for(const auto& key:keys){
                auto old=a.find(key),now=b.find(key);std::string change;
                if(old==a.end())change="added";else if(now==b.end())change="removed";
                else change=old->second.content==now->second.content?"unchanged":"changed";
                counts[change]=counts[change].get<size_t>()+1;
                if(change=="unchanged"||(kind!="all"&&kind!=category))continue;
                const size_t index=total++;if(index<offset||out["changes"].size()>=limit)continue;
                J fields=J::array();
                if(change=="changed"){
                    std::set<std::string> names;for(auto it=old->second.content.begin();it!=old->second.content.end();++it)names.insert(it.key());for(auto it=now->second.content.begin();it!=now->second.content.end();++it)names.insert(it.key());
                    for(const auto& name:names)if(!old->second.content.contains(name)||!now->second.content.contains(name)||old->second.content.at(name)!=now->second.content.at(name))fields.push_back(name);
                }
                auto side=[&](const Item& item,uint64_t at){J evidence=J::array();for(const auto* r:item.evidence)evidence.push_back(summary(*r,at));return J{{"at_packet",at},{"value",item.value},{"evidence",evidence}};};
                out["changes"].push_back({{"kind",category},{"change",change},{"key",key},{"identity",now!=b.end()?now->second.identity:old->second.identity},{"changed_fields",fields},{"before",old==a.end()?J():side(old->second,from)},{"after",now==b.end()?J():side(now->second,to)}});
            }
            out["summary"][category]=counts;
        }
        out["total_changes"]=total;
        if(offset<total&&out["changes"].size()<total-offset)out["next_offset"]=offset+out["changes"].size();
        return out;
    }
    void clearEvidence() {
        records.clear();ids.clear();history=J::array();previous.clear();pending=J::object();patchSections.clear();
        observations=crcErrors=0;demuxStatus=J::object();
    }
    J analyze(const J& args,const J& rid,const std::shared_ptr<AnalysisControl>& control) {
        // A new scan owns a new revision even when opening or framing fails.
        // Never allow old evidence or preview tokens to acquire a new source label.
        clearEvidence();++revision;analysisStatus="analyzing";
        source.clear();packets=totalBytes=0;complete=false;
        firstMs=-1;totalMs=0;stride=188;prefix=0;onFirst=nullptr;began=Clock::now();requestId=rid;
        try {
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
        bitrate=args.value("bitrate",0.0);
        source=fs::absolute(fs::u8path(args.at("path").get<std::string>()));
        TEST_CHECKPOINT("before_analysis",control);
        checkCancelled(control);
        // This API scans bounded local files, not blocking pipes or device streams.
        // status follows symlinks, so ordinary links to regular files remain valid.
        std::error_code sourceError;
        if(!fs::is_regular_file(source,sourceError))throw std::runtime_error("Source must be a regular local file");
        std::ifstream in(source,std::ios::binary);
        if(!in)throw std::runtime_error("Cannot read source file");totalBytes=fs::file_size(source);if(totalBytes<188)throw std::runtime_error("Source is too small for a TS packet");
        checkCancelled(control);
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
        auto progress=[&](){
            checkCancelled(control);TEST_CHECKPOINT("before_progress",control);checkCancelled(control);
            J snapshot=state(UINT64_MAX,control);checkCancelled(control);
            emit({{"event","progress"},{"request_id",rid},{"state",std::move(snapshot)}});
            TEST_CHECKPOINT("after_progress",control);checkCancelled(control);
        };
        onFirst=progress;
        std::vector<uint8_t> block(stride*8192);auto lastNotify=Clock::now();
        while(in) {
            checkCancelled(control);TEST_CHECKPOINT("before_read",control);checkCancelled(control);
            in.read(reinterpret_cast<char*>(block.data()),block.size());size_t n=size_t(in.gcount());
            for(size_t p=0;p+stride<=n;p+=stride){
                // The file read is bounded to 8192 packets; SDK feed checkpoints
                // every 256 packets bound additional work without a lock per feed.
                if((p/stride)%256==0)checkCancelled(control);
                ts::TSPacket packet;std::memcpy(packet.b,block.data()+p+prefix,188);++packets;demux.feedPacket(packet);
            }
            if(ms(lastNotify)>=100){progress();lastNotify=Clock::now();}
        }
        onFirst=nullptr;checkCancelled(control);
        if(in.bad())throw std::runtime_error("Source read failed; analysis is incomplete");
        ts::SectionDemux::Status status(demux);demuxStatus={{"wrong_crc",status.wrong_crc},{"discontinuities",status.discontinuities},{"invalid_ts",status.invalid_ts},{"invalid_length",status.inv_sect_length},{"truncated_sections",status.truncated_sect}};
        TEST_CHECKPOINT("before_complete",control);
        // This is the linearization point: a cancellation accepted before it
        // always wins, and one arriving afterwards must report not_running.
        if(control&&control->finish())throw CancelledAnalysis();
        complete=true;analysisStatus="complete";totalMs=ms(began);
        TEST_CHECKPOINT("after_complete",control);
        J out=state();out["trailing_bytes"]=totalBytes%stride;return out;
        } catch(...) {
            onFirst=nullptr;totalMs=ms(began);complete=false;
            const bool cancelled=control&&control->finish();
            clearEvidence();analysisStatus=cancelled?"cancelled":"failed";
            if(cancelled)throw CancelledAnalysis();
            throw;
        }
    }
    J inspect(const J& args) {
        std::string id=args.at("id");if(!ids.count(id))throw std::runtime_error("Unknown section id");const Record&r=records[ids.at(id)];
        const uint64_t cutoff=args.value("at_packet",r.lastPacket);
        auto observed=std::upper_bound(r.ends.begin(),r.ends.end(),cutoff);
        if(observed==r.ends.begin())throw std::runtime_error("Section was not observed at or before selected packet");
        const size_t occurrenceCount=size_t(observed-r.ends.begin());
        J out=summary(r,cutoff);out["native_table_at_packet"]=cutoff;
        out["inspection_scope"]={{"occurrences_and_summary",args.contains("at_packet")?"at or before selected packet":"all occurrences of this section"},{"native_table",args.contains("at_packet")?"selected observed generation at or before selected packet":"selected observed generation at last occurrence of inspected section"}};
        out["raw_hex"]=hex(r.raw);out["fields"]=r.fields;out["descriptors"]=r.descriptors;out["issues"]=r.issues;out["services"]=r.services;out["events"]=r.events;
        out["occurrences"]=std::vector<uint64_t>(r.positions.begin(),r.positions.begin()+occurrenceCount);out["occurrence_end_packets"]=std::vector<uint64_t>(r.ends.begin(),observed);out["first_file_offset"]=r.positions.front()*stride+prefix;out["offset_note"]="TS packet offset, not section payload offset; a section may span packets";
        out["text_charset"]=duck.charsetIn()->name().toUTF8();out["time_reference"]=duck.timeReferenceName().toUTF8();out["standards_context"]=standardsContext;out["native_table_complete"]=false;out["native_decode_status"]="invalid section; raw evidence retained";
        if(r.valid){
            // Share the same generation boundary as query/export, including
            // current/next isolation and version rollover.
            const auto selected=latest(cutoff,r.current);
            std::map<unsigned,const Record*> group;
            for(const auto& [key,candidate]:selected)if(tableGroup(*candidate)==tableGroup(r))group[candidate->number]=candidate;
            ts::BinaryTable table;bool full=group.size()==r.last+1;
            const bool superseded=!group.count(r.number)||group.at(r.number)->id!=r.id;if(superseded)full=false;
            for(unsigned i=0;i<=r.last;i++){auto found=group.find(i);if(found==group.end()){full=false;break;}const auto& part=*found->second;table.addNewSection(part.raw.data(),part.raw.size(),ts::PID(part.pid),ts::CRC32::CHECK);}
            ts::DuckContext tableDuck(&NULLREP);tableDuck.resetStandards(duck.standards());tableDuck.setDefaultCharsetIn(duck.charsetIn());tableDuck.setDefaultCharsetOut(duck.charsetOut());tableDuck.setTimeReferenceOffset(duck.timeReferenceOffset());
            ts::xml::Document document;auto* parent=document.initialize(u"tsduck");
            if(full&&table.isValid()){
                auto* native=table.toXML(tableDuck,parent);out["native_table_complete"]=true;
                if(native){out["native_table"]=xmlTree(native);const auto name=native->name();out["native_decode_status"]=(name==u"generic_long_table"||name==u"generic_short_table")?"generic raw fallback":"native TSDuck decoder";}
                out["tsduck_xml"]=document.toString().toUTF8();
            }else{ts::SectionFile file(duck);file.add(std::make_shared<ts::Section>(r.raw.data(),r.raw.size(),ts::PID(r.pid),ts::CRC32::CHECK));out["tsduck_xml"]=file.toXML().toUTF8();out["native_decode_status"]=superseded?"inspected section superseded at selected packet; raw section retained":"incomplete table; raw section retained";}
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
        if(patch){
            const auto& target=records.at(ids.at(pending.at("source_id").get<std::string>()));
            for(const auto& [key,r]:selected)if(r->pid==target.pid&&r->tid==target.tid&&r->ext==target.ext&&tableGroup(*r)!=tableGroup(target))
                throw std::runtime_error("Ambiguous SDT edit: multiple network identities share the target PID and transport stream id at this snapshot");
        }
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
    J dispatch(const std::string& method,const J& args,const J& rid,const std::shared_ptr<AnalysisControl>& control=nullptr) {
        // runCore validates against its immutable startup catalog before queueing.
        // Re-reading mutable schemas here could invalidate an accepted analysis.
        if(method=="capabilities"){
            J result=readJson(root/"api/tools.json");ts::UStringList tables,descriptors;
            ts::PSIRepository::Instance().getRegisteredTableNames(tables);ts::PSIRepository::Instance().getRegisteredDescriptorNames(descriptors);
            J registry={{"table_names",J::array()},{"descriptor_names",J::array()},{"table_count",tables.size()},{"descriptor_count",descriptors.size()},{"note","Registered decoders, not a guarantee that every payload or regional variant is supported. Explicit standards context resolves ambiguous identifiers."}};
            for(const auto& name:tables)registry["table_names"].push_back(name.toUTF8());for(const auto& name:descriptors)registry["descriptor_names"].push_back(name.toUTF8());result["native_registry"]=registry;return result;
        }
        if(method=="analyze")return analyze(args,rid,control);
        if(method=="query")return state(args.value("at_packet",UINT64_MAX));
        if(method=="diff_snapshots")return diffSnapshots(args);
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

struct QueuedRequest {
    J id,args;
    std::string method,key;
    std::shared_ptr<AnalysisControl> control;
};

static int runCore(int argc,char**argv) {
    std::cin.tie(nullptr);
    fs::path root=fs::current_path();for(int i=1;i+1<argc;i++)if(std::string(argv[i])=="--root")root=fs::u8path(argv[++i]);
    try {
        Engine engine(root);
        // The reader validates JSON and schemas only. No Engine/TSDuck calls or
        // state access are permitted there, even for a cancellation response.
        const J catalog=readJson(root/"api/tools.json");
        constexpr size_t queueCapacity=64;
        std::mutex mutex;std::condition_variable ready;bool inputEnded=false;
        std::deque<QueuedRequest> queue;
        std::map<std::string,std::shared_ptr<AnalysisControl>> analyses;
        std::thread reader([&](){
            std::string line;
            while(std::getline(std::cin,line)) {
                J id=nullptr;
                try {
                    J request=J::parse(line);
                    if(!request.is_object())throw std::runtime_error("request must be an object");
                    id=request.value("id",J());
                    const std::string method=request.at("method").get<std::string>();
                    J args=request.value("params",J::object());
                    validateArguments(catalog,method,args);
                    if(method=="cancel_analysis"){
                        const J target=args.at("request_id");std::shared_ptr<AnalysisControl> control;
                        {std::lock_guard<std::mutex> lock(mutex);auto found=analyses.find(target.dump());if(found!=analyses.end())control=found->second;}
                        const bool requested=control&&control->requestCancellation();
                        J result={{"request_id",target},{"requested",requested}};
                        if(!requested)result["reason"]="not_running";
                        emit({{"id",id},{"result",result}});continue;
                    }
                    QueuedRequest work{id,std::move(args),method,"",nullptr};
                    std::string reject;
                    {
                        std::lock_guard<std::mutex> lock(mutex);
                        if(queue.size()>=queueCapacity)reject="queue_full";
                        else {
                            if(method=="analyze"){
                                work.control=std::make_shared<AnalysisControl>();
                                // Legacy missing/null ids still run, but cannot
                                // be targeted. Scalar integer/string ids can.
                                if(id.is_string()||id.is_number_integer()){
                                    work.key=id.dump();
                                    if(analyses.count(work.key))reject="duplicate_request_id";
                                    else analyses.emplace(work.key,work.control);
                                }
                            }
                            if(reject.empty())queue.push_back(std::move(work));
                        }
                    }
                    if(!reject.empty())emit({{"id",id},{"error",{{"code",reject},{"message",reject=="queue_full"?"Ordinary request queue is full (64 waiting requests)":"An analysis with this request id is already queued or running"}}}});
                    else ready.notify_one();
                } catch(const std::exception& e){emit({{"id",id},{"error",{{"code","request_failed"},{"message",e.what()}}}});}
            }
            {std::lock_guard<std::mutex> lock(mutex);inputEnded=true;}
            ready.notify_one();
        });
        for(;;){
            QueuedRequest work;
            {
                std::unique_lock<std::mutex> lock(mutex);
                ready.wait(lock,[&]{return inputEnded||!queue.empty();});
                if(queue.empty())break;
                work=std::move(queue.front());queue.pop_front();
            }
            J terminal;
            try {
                J result=engine.dispatch(work.method,work.args,work.id,work.control);
                terminal={{"id",work.id},{"result",std::move(result)}};
            } catch(const CancelledAnalysis& e){
                terminal={{"id",work.id},{"error",{{"code","analysis_cancelled"},{"message",e.what()},{"data",{{"state",engine.state()}}}}}};
            } catch(const std::exception& e){
                terminal={{"id",work.id},{"error",{{"code","request_failed"},{"message",e.what()}}}};
            }
            if(work.control){
                work.control->finish();
                std::lock_guard<std::mutex> lock(mutex);
                auto found=analyses.find(work.key);
                if(found!=analyses.end()&&found->second==work.control)analyses.erase(found);
            }
            // Retire the registry entry before publishing the response, so a
            // client can immediately reuse a completed ID without a false duplicate.
            emit(terminal);
            if(work.method=="analyze")TEST_CHECKPOINT("after_terminal",work.control);
        }
        // EOF is not cancellation: every accepted FIFO request is drained first.
        reader.join();
    } catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
    return 0;
}
#ifndef SHOWPSISI_TESTING
int main(int argc,char**argv) { return runCore(argc,argv); }
#endif
