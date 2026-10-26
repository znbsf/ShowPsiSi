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
#include "tsPMT.h"
#include "tsDVB.h"
#include "tsStreamType.h"
#include "tsAbstractLogicalChannelDescriptor.h"
#include "tsDSMCCUserToNetworkMessage.h"
#include "tsNames.h"
#include "tsCharset.h"
#include "tsPSIRepository.h"
#include "tsDescriptorContext.h"
#include "tsLibTSDuckVersion.h"
#include "tsAbstractTable.h"
#include "tsAbstractDescriptor.h"
#include "tsTablesDisplay.h"
#include "tsxmlDocument.h"
#include "tsxmlElement.h"
#include "nlohmann/json.hpp"
#include <fstream>
#include <array>
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
#include <queue>
#include <memory>
#include <mutex>
#include <thread>
#ifdef _WIN32
#include <windows.h>
#endif

// Resolve version-specific symbols from both shared libraries before startup.
// A mismatched installed runtime must fail rather than decode with an unsafe ABI.
TS_LIBTSDUCK_CHECK();
#if TS_VERSION_INTEGER < 34504798
#error ShowPsiSi requires TSDuck 3.45-4798 or newer
#endif

using J = nlohmann::json;
#include "SiWireFields.h"
#include "NorDigMetadata.h"
#include "DvbiInput.h"
#include "CableOobMetadata.h"
using Bytes = std::vector<uint8_t>;
namespace fs = std::filesystem;
using Clock = std::chrono::steady_clock;
static double ms(Clock::time_point t) { return std::chrono::duration<double,std::milli>(Clock::now()-t).count(); }
static unsigned u16(const Bytes& b,size_t p) { return unsigned(b.at(p))*256+b.at(p+1); }
static std::string hex(const uint8_t* p,size_t n) { std::ostringstream o; o<<std::hex<<std::uppercase<<std::setfill('0'); for(size_t i=0;i<n;i++) o<<std::setw(2)<<int(p[i]); return o.str(); }
static std::string hex(const Bytes& b) { return hex(b.data(),b.size()); }
static std::string fingerprint(const Bytes& b) { uint64_t h=14695981039346656037ULL; for(auto c:b) { h^=c; h*=1099511628211ULL; } std::ostringstream o; o<<std::hex<<h; return o.str(); }
// C++20 paths return std::u8string. JSON and the wire protocol require a
// UTF-8 std::string, never locale-dependent path.string() or char8_t arrays.
static std::string pathUtf8(const fs::path& path) {
    const auto utf8=path.u8string();
    return std::string(reinterpret_cast<const char*>(utf8.data()),utf8.size());
}
static fs::path pathFromUtf8(std::string_view text) {
    std::u8string utf8;utf8.reserve(text.size());
    for(unsigned char byte:text)utf8.push_back(static_cast<char8_t>(byte));
    return fs::path(utf8);
}
static fs::path manifestPath(const fs::path& path) {
    fs::path manifest=path;manifest += ".manifest.json";return manifest;
}
static std::string sdkVersion(int major,int minor,int commit) {
    return std::to_string(major)+"."+std::to_string(minor)+"-"+std::to_string(commit);
}
static J readJson(const fs::path& p) { std::ifstream in(p); if(!in) throw std::runtime_error("Cannot open "+pathUtf8(p)); J j; in>>j; return j; }
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
    std::atomic<bool> paused{false};
    std::condition_variable changed;
    std::function<void(bool)> onPause;
    std::mutex mutex;
    bool finished=false;
    bool requestCancellation() {
        std::lock_guard<std::mutex> lock(mutex);
        if(finished)return false;
        cancelled.store(true);changed.notify_all();return true;
    }
    bool requestPause(bool value) {
        std::lock_guard<std::mutex> lock(mutex);
        if(finished||cancelled.load())return false;
        paused.store(value);changed.notify_all();return true;
    }
    void checkpoint() {
        std::unique_lock<std::mutex> lock(mutex);
        if(paused.load()&&!cancelled.load()){
            lock.unlock();if(onPause)onPause(true);lock.lock();
            changed.wait(lock,[&]{return !paused.load()||cancelled.load();});
            lock.unlock();if(onPause)onPause(false);
        }
    }
    bool finish(const std::function<void()>& beforeCommit={}) {
        for(;;){
            std::unique_lock<std::mutex> lock(mutex);
            if(finished)return cancelled.load();
            if(paused.load()&&!cancelled.load()){lock.unlock();checkpoint();continue;}
            if(beforeCommit&&!cancelled.load())beforeCommit();
            finished=true;changed.notify_all();return cancelled.load();
        }
    }
};
struct CancelledAnalysis : std::exception {
    const char* what() const noexcept override { return "Analysis cancelled"; }
};
static void checkCancelled(const std::shared_ptr<AnalysisControl>& control) {
    if(control){control->checkpoint();if(control->cancelled.load())throw CancelledAnalysis();}
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
    for(const auto& item:std::vector<std::pair<ts::Standards,const char*>>{{ts::Standards::MPEG,"MPEG"},{ts::Standards::DVB,"DVB"},{ts::Standards::ATSC,"ATSC"},{ts::Standards::ISDB,"ISDB"},{ts::Standards::JAPAN,"JAPAN"},{ts::Standards::ABNT,"ABNT"},{ts::Standards::SCTE,"SCTE"},{ts::Standards::DTMB,"DTMB"}})
        if((mask&item.first)!=ts::Standards::NONE){if(!names.empty())names+=", ";names+=item.second;}
    return names.empty()?"none":names;
}
static J xmlTree(const ts::xml::Element* element) {
    if(!element)return nullptr;
    J tree={{"name",element->name().toUTF8()},{"attributes",J::object()},{"children",J::array()}};
    std::map<ts::UString,ts::UString> attributes;element->getAttributes(attributes);
    // Keep the existing JSON API's ASCII-lowercase attribute keys. Native XML
    // is serialized separately with its original names and values unchanged.
    for(const auto& [name,value]:attributes){
        std::string key=name.toUTF8();for(char& ch:key)if(ch>='A'&&ch<='Z')ch=char(ch-'A'+'a');
        if(tree["attributes"].contains(key)){
            tree["attribute_case_collisions"].push_back(key);
            // Preserve every original spelling/value if normalization collides.
            for(const auto& [original,text]:attributes)tree["xml_attributes"][original.toUTF8()]=text.toUTF8();
        }else tree["attributes"][key]=value.toUTF8();
    }
    ts::UString text;element->getText(text,true);if(!text.empty())tree["text"]=text.toUTF8();
    for(auto* child=element->firstChildElement();child;child=child->nextSiblingElement())tree["children"].push_back(xmlTree(child));
    return tree;
}

// TSDuck 3.45 can resolve an observed dual-private REGID to a regular
// descriptor from another family. An exact registry entry proves ambiguity,
// not permission to guess. Keep generic bytes unless the SDK resolves it to
// that entry (or a real on-wire PDS explicitly selects another private entry).
static bool privateDualConflict(const ts::Descriptor& descriptor,ts::DescriptorContext& context,bool pdsOnWire) {
    const auto& repo=ts::PSIRepository::Instance();
    const auto& selected=repo.getDescriptor(descriptor.xdid(),context);
    if(pdsOnWire&&selected.edid.isPrivateDVB()&&selected.edid.pds()==context.getPDS())return false;
    const auto registrations=context.getREGIDs();
    for(auto it=registrations.rbegin();it!=registrations.rend();++it){
        const auto& registered=repo.getDescriptor(ts::EDID::PrivateDual(descriptor.tag(),*it));
        if(registered.factory&&registered.edid.isPrivateDual())return registered.edid!=selected.edid;
    }
    return false;
}

// Re-render only a PMT loop with a demonstrated namespace conflict, using SDK
// descriptors and their real parent/list index. Unaffected loops stay intact.
static bool guardPrivateDualLoop(ts::DuckContext& duck,const ts::DescriptorList& list,ts::xml::Element* parent,bool programLevel) {
    ts::xml::Document replacement;auto* container=replacement.initialize(u"descriptors");
    bool guarded=false,pdsOnWire=false;
    for(size_t index=0;index<list.size();++index){
        const auto& descriptor=list[index];ts::DescriptorContext context(duck,list,index);
        const bool conflict=privateDualConflict(descriptor,context,pdsOnWire);guarded|=conflict;
        descriptor.toXML(duck,container,context,conflict);
        if(descriptor.tag()==ts::DID_DVB_PRIV_DATA_SPECIF&&descriptor.payloadSize()==4)pdsOnWire=true;
    }
    if(!guarded)return false;
    ts::xml::Element* firstComponent=nullptr;
    for(auto* child=parent->firstChildElement();child;){
        auto* next=child->nextSiblingElement();
        if(programLevel&&child->name()==u"component"){if(!firstComponent)firstComponent=child;}
        else if(child->name()!=u"metadata"&&child->name()!=u"_metadata")delete child;
        child=next;
    }
    while(auto* child=container->firstChildElement()){
        if(firstComponent)child->moveBefore(firstComponent);else child->reparent(parent);
    }
    return true;
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
        if(!file)throw std::runtime_error("Cannot exclusively create output (it may already exist): "+pathUtf8(path));
    }
    ExportFile(const ExportFile&)=delete;
    ExportFile& operator=(const ExportFile&)=delete;
    ~ExportFile(){if(file)std::fclose(file);if(!committed){std::error_code ignored;fs::remove(path,ignored);}}
    void write(const void* data,size_t bytes){if(std::fwrite(data,1,bytes,file)!=bytes)throw std::runtime_error("Output write failed: "+pathUtf8(path));}
    void close(){auto* f=file;file=nullptr;if(f&&std::fclose(f)!=0)throw std::runtime_error("Output close failed: "+pathUtf8(path));}
    void commit(){committed=true;}
};

struct Record {
    std::string id,key; Bytes raw; unsigned pid=0,tid=0,ext=0,version=0,number=0,last=0; bool valid=true,current=true,j94=false;
    std::vector<uint64_t> positions,ends,orders; uint64_t lastPacket=0;
    J descriptors=J::array(),services=J::array(),events=J::array(),issues=J::array(),fields=J::object();
};

#include "SignalMetadata.h"
#include "SatelliteMetadata.h"
#include "ApplicationSignalling.h"
#include "SignalTopology.h"
#include "ApplicationCarriage.h"
#include "TransportStatistics.h"

class RejectedInput : public std::runtime_error { public: using std::runtime_error::runtime_error; };

class Engine : public ts::SectionHandlerInterface, public ts::InvalidSectionHandlerInterface {
    dvbi::Store dvbiDocuments;
    fs::file_time_type analysisSourceStamp{}; bool analysisSourceKnown=false;
    fs::path root,source; ts::DuckContext duck { &NULLREP }; J extension=J::object(),configuredExtension=J::object();
    std::vector<Record> records; std::unordered_map<std::string,size_t> ids; J history=J::array();
    std::unordered_map<std::string,std::string> previous;
    J tableHistory=J::array();
    std::unordered_map<std::string,size_t> historySlots;
    uint64_t packets=0,totalBytes=0,observations=0,crcErrors=0; size_t stride=188,prefix=0;
    double bitrate=0,firstMs=-1,totalMs=0; Clock::time_point began;
    transportstats::Statistics transportStatistics;
    std::string standardsContext="auto",analysisStatus="idle";
    J requestId; std::function<void()> onFirst; bool complete=false; size_t revision=0;
    J coverage=J::object(),resultCache=J::object();uint64_t cacheCutoff=UINT64_MAX,scannedPackets=0,plannedPackets=0,demuxOffset=0;
    std::array<uint64_t,80> densityCounts{},densityBad{};
    bool compactResponse=false;
    J pending=J::object(), demuxStatus=J::object(); std::vector<std::pair<unsigned,Bytes>> patchSections;
    // A DVB table identity includes the network/transport identifiers in its
    // payload. table_id_extension alone is insufficient for SDT-other / EIT.
    static std::string tableGroup(const Record& r) {
        if(r.j94)return r.key; // Exact observation variants; no fabricated J.94 map generation.
        std::string key=std::to_string(r.pid)+":"+std::to_string(r.tid)+":"+std::to_string(r.ext);
        if((r.tid==0x42||r.tid==0x46)&&r.raw.size()>=11)key+=":onid="+std::to_string(u16(r.raw,8));
        if(r.tid>=0x4e&&r.tid<=0x6f&&r.raw.size()>=14)key+=":tsid="+std::to_string(u16(r.raw,8))+":onid="+std::to_string(u16(r.raw,10));
        return key;
    }
    static std::string sectionKey(const Record& r) { return tableGroup(r)+":"+std::to_string(r.number); }
    std::map<std::string,const Record*> latest(uint64_t at,bool current=true) const {
        struct Observation { const Record* record; uint64_t order; };
        uint64_t segmentStart=0;
        for(const auto& range:coverage.value("ranges",J::array())){const auto start=range["start_packet"].get<uint64_t>();if(start<=std::min(at,packets?packets-1:0))segmentStart=start;}
        std::vector<Observation> observed;
        std::map<std::string,Observation> generations;
        for(const auto& r:records)if(r.valid&&r.current==current){
            auto end=std::upper_bound(r.ends.begin(),r.ends.end(),at);if(end==r.ends.begin()||*(end-1)<segmentStart)continue;
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
    J descriptors(Record& r,size_t begin,size_t end,int serviceId=-1,const ts::REGIDVector& inheritedRegistrations={}) {
        J result=J::object(); uint32_t pds=0;bool pdsOnWire=false;
        ts::DuckContext descriptorDuck(&NULLREP);descriptorDuck.resetStandards(duck.standards());descriptorDuck.setDefaultCharsetIn(duck.charsetIn());descriptorDuck.setDefaultCharsetOut(duck.charsetOut());descriptorDuck.setTimeReferenceOffset(duck.timeReferenceOffset());
        ts::REGIDVector registrations=inheritedRegistrations;
        if(r.raw.size()<4||end>r.raw.size()-4) { issue(r,"descriptor_loop_overrun",begin,"Descriptor loop exceeds section payload"); return result; }
        for(size_t p=begin;p<end;) {
            if(p+2>end) { issue(r,"descriptor_header_truncated",p,"Missing descriptor length"); break; }
            size_t n=r.raw[p+1],next=p+2+n; int tag=r.raw[p];
            J d={{"tag",tag},{"length",n},{"offset",p},{"service_id",serviceId},{"pds",pds},{"name","opaque_descriptor"},{"raw",hex(r.raw.data()+p,std::min(next,end)-p)},{"fields",J::object()}};
            if(next>end) { d["decode_status"]="parse_failure";issue(r,"descriptor_length",p,"Declared length exceeds descriptor loop; raw bytes retained"); d["malformed"]=true; r.descriptors.push_back(d); break; }
            ts::Descriptor bin(r.raw.data()+p,n+2);
            ts::xml::Document nativeDocument;auto* parent=nativeDocument.initialize(u"descriptor");
            // Ordered wire REGIDs are local to this loop, with program-level PMT
            // registrations inherited ahead of component-level registrations.
            ts::DescriptorContext context(descriptorDuck,ts::TID(r.tid),descriptorDuck.standards(),ts::CASID_NULL,registrations,pdsOnWire?pds:ts::PDS_NULL);
            d["registration_ids"]=registrations;
            const bool namespaceConflict=privateDualConflict(bin,context,pdsOnWire);
            if(namespaceConflict)d["native_decode_warning"]="Observed registration id conflicts with SDK descriptor namespace resolution; generic bytes retained";
            if(auto* native=bin.toXML(descriptorDuck,parent,context,namespaceConflict)){d["native"]=xmlTree(native);d["name"]=native->name().toUTF8();d["native_decoded"]=native->name()!=u"generic_descriptor";}

            const auto& descriptorClass=ts::PSIRepository::Instance().getDescriptor(bin.xdid(),context);
            d["decoder_registered"]=descriptorClass.factory!=nullptr;
            d["decode_status"]=namespaceConflict?"context_guarded":d.value("native_decoded",false)?"decoded":descriptorClass.factory?"parse_failure":"unknown_or_unsupported";
            d["decode_scope"]="SDK registry in observed descriptor context; unknown private syntax cannot be distinguished from unsupported specification without external evidence";
            if(tag==0x05&&n>=4)registrations.push_back((uint32_t(u16(r.raw,p+2))<<16)|u16(r.raw,p+4));
            // ETSI TS 101 211 4.2.7.1: either namespace descriptor ends the
            // previous PDS scope. Malformed replacements cannot inherit it.
            if(tag==0x5f) {
                pdsOnWire=n==4;pds=pdsOnWire?(uint32_t(u16(r.raw,p+2))<<16)|u16(r.raw,p+4):0;
                if(pdsOnWire){d["name"]="private_data_specifier_descriptor";d["fields"]["private_data_specifier"]=pds;}
            }
            else if(tag==0x0f){pds=0;pdsOnWire=false;}
            if(tag==0x0f||(tag==0x5f&&n!=4))d["native_decode_warning"]="Private namespace scope ends here; unanchored SDK section text may retain stale private meanings and is withheld. Original bytes and contextual descriptors remain available.";
            if(tag==0x48) {
                ts::ServiceDescriptor native(duck,bin); d["name"]="service_descriptor";
                if(native.isValid()) { result["name"]=native.service_name.toUTF8(); result["provider"]=native.provider_name.toUTF8(); result["type"]=native.service_type; d["fields"]=result; }
                else issue(r,"service_descriptor_invalid",p,"TSDuck rejected service descriptor");
            } else if(tag==0x4d) {
                ts::ShortEventDescriptor native(duck,bin); d["name"]="short_event_descriptor";
                if(native.isValid()) { d["fields"]={{"language_code",native.language_code.toUTF8()},{"title",native.event_name.toUTF8()},{"text",native.text.toUTF8()}}; }
                else issue(r,"short_event_descriptor_invalid",p,"TSDuck rejected event descriptor");
            } else if(tag==0x4e&&r.tid>=0x4e&&r.tid<=0x6f) {
                // Retain malformed fragments in the event's language evidence too.
                d["name"]="extended_event_descriptor";
            }
            // Diagnose the SDK/public identity before any user display-name override.
            signalmeta::diagnose(r,d,duck.charsetIn());
            nordigmeta::decode(d,bin,descriptorDuck,context,!namespaceConflict&&pdsOnWire&&pds==0x29&&tag==0x87&&(r.tid==0x40||r.tid==0x41));
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
            // Only SDK-resolved ordinary LCN descriptors participate. HD-simulcast
            // and regional/list descriptors are retained in native evidence, not flattened.
            const std::set<std::string> lcnNames={"logical_channel_number_descriptor","eacem_logical_channel_number_descriptor","nordig_logical_channel_descriptor_v1","dtg_logical_channel_descriptor","australia_logical_channel_descriptor"};
            if(!namespaceConflict&&pdsOnWire&&lcnNames.count(d.value("name",std::string()))){
                auto native=bin.deserialize(descriptorDuck,context);
                if(auto* lcn=dynamic_cast<ts::AbstractLogicalChannelDescriptor*>(native.get());lcn&&lcn->isValid()){
                    d["lcn_entries"]=J::array();
                    for(const auto& entry:lcn->entries)d["lcn_entries"].push_back({{"service_id",entry.service_id},{"number",entry.lcn},{"visible",entry.visible}});
                }else if(auto* nordig=dynamic_cast<ts::NorDigLogicalChannelDescriptorV1*>(native.get());nordig&&nordig->isValid()){
                    d["lcn_entries"]=J::array();
                    for(const auto& entry:nordig->entries)d["lcn_entries"].push_back({{"service_id",entry.service_id},{"number",entry.lcn},{"visible",entry.visible}});
                }
            }
            r.descriptors.push_back(d); p=next;
        }
        return result;
    }
    void decode(Record& r) {
        const auto& b=r.raw; size_t end=b.size()>=4?b.size()-4:0;
        if(!r.valid)return;
        // All manually decoded long-table loops below use offsets after the
        // eight-byte header. A short envelope must not invent those identities.
        const size_t longMinimum=r.tid==0||r.tid==1?12:r.tid==2?16:
            r.tid==0x42||r.tid==0x46?15:r.tid==0x40||r.tid==0x41||r.tid==0x4a?16:
            r.tid>=0x4e&&r.tid<=0x6f?18:0;
        if(longMinimum&&(b.size()<longMinimum||(b[1]&0x80)==0)){
            issue(r,"long_section_required",1,"This table requires a complete MPEG long-section header and fixed payload; raw evidence retained");return;
        }
        if(r.j94){r.fields["j94_system_b"]=cableoob::parse(b);return;}
        if((r.tid==0x42||r.tid==0x46)&&b.size()>=15) {
            r.fields["transport_stream_id"]=r.ext; r.fields["original_network_id"]=u16(b,8);
            for(size_t p=11;p<end;) {
                if(p+5>end){issue(r,"service_loop_truncated",p,"Incomplete SDT service header");break;}
                int sid=u16(b,p); size_t n=u16(b,p+3)&0xfff;
                J s={{"id",sid},{"name","Service "+std::to_string(sid)},{"provider",""},{"group","Unassigned"},{"logical_channel_number",nullptr},{"source_id",r.id},{"ts_id",r.ext},{"onid",u16(b,8)},{"encrypted",(b[p+3]&0x10)!=0}};
                J decoded=descriptors(r,p+5,p+5+n,sid); s.update(decoded);
                s["name_from_descriptor"]=decoded.contains("name") && decoded["name"].is_string() && !decoded["name"].get<std::string>().empty();
                r.services.push_back(s); p+=5+n;
            }
        } else if(r.tid==0&&b.size()>=12) {
            r.fields["programs"]=J::array();
            for(size_t p=8;p+4<=end;p+=4)r.fields["programs"].push_back({{"service_id",u16(b,p)},{"pmt_pid",u16(b,p+2)&0x1fff}});
            if((end-8)%4) issue(r,"pat_length",8,"PAT program loop is not a multiple of four");
        } else if(r.tid==2&&b.size()>=16) {
            r.fields["pcr_pid"]=u16(b,8)&0x1fff; r.fields["streams"]=J::array();
            size_t n=u16(b,10)&0xfff; descriptors(r,12,12+n);
            // Classification consumes only descriptors which passed the same
            // context-aware native decoding used by the evidence inspector.
            auto addDecoded=[&](ts::DescriptorList& list,size_t begin,size_t stop){
                for(const auto& d:r.descriptors){const size_t offset=d["offset"],length=d["length"];
                    if(offset>=begin&&offset+2+length<=stop&&d.value("decode_status",std::string())=="decoded")list.add(b.data()+offset,2+length);
                }
            };
            ts::PMT nativePMT; if(12+n<=end)addDecoded(nativePMT.descs,12,12+n);
            ts::REGIDVector programRegistrations;
            for(size_t p=12;p+2<=std::min(12+n,end);){size_t next=p+2+b[p+1];if(next>std::min(12+n,end))break;if(b[p]==0x05&&b[p+1]>=4)programRegistrations.push_back((uint32_t(u16(b,p+2))<<16)|u16(b,p+4));p=next;}
            for(size_t p=12+n;p<end;) {
                if(p+5>end){issue(r,"pmt_stream_truncated",p,"Incomplete stream header");break;}
                size_t len=u16(b,p+3)&0xfff;
                descriptors(r,p+5,p+5+len,-1,programRegistrations);
                ts::PMT::Stream nativeStream(&nativePMT,b[p]);
                if(p+5+len<=end)addDecoded(nativeStream.descs,p+5,p+5+len);
                // SDK isAudio/isVideo include private stream-type shortcuts. A
                // private numeric value alone does not establish its namespace.
                bool audio=nativeStream.isAudio(duck),video=nativeStream.isVideo(duck);
                if(b[p]>=0x80){
                    const bool atsc=(duck.standards()&ts::Standards::ATSC)!=ts::Standards::NONE;
                    auto registered=[&](ts::REGID id){return nativePMT.descs.containsRegistration(id)||nativeStream.descs.containsRegistration(id);};
                    const bool hdmv=registered(ts::REGID_HDMV);
                    if(hdmv){
                        // HDMV 0x80 is LPCM, not DigiCipher video; 0x91 is IGS,
                        // not A52/AC3. Use the SDK's documented HDMV audio set.
                        const std::set<unsigned> types={0x80,0x81,0x82,0x83,0x84,0x85,0x86,0x87,0x8a,0x94,0xa1,0xa2};
                        audio=types.count(b[p])&&ts::StreamTypeIsAudio(b[p],std::set<ts::REGID>{ts::REGID_HDMV});video=false;
                    }else if((b[p]==0xd2||b[p]==0xd4)&&registered(ts::REGID_AVSVideo)){
                        audio=false;video=nativeStream.isVideo(duck);
                    }else if((b[p]==0xd3||b[p]==0xd5)&&registered(ts::REGID_AVSAudio)){
                        audio=nativeStream.isAudio(duck);video=false;
                    }else{
                        if(!(atsc&&(b[p]==0x81||b[p]==0x87)))nativeStream.stream_type=0x06;
                        const auto codec=nativeStream.getCodec(duck);
                        audio=ts::CodecTypeIsAudio(codec);video=ts::CodecTypeIsVideo(codec);
                    }
                }
                r.fields["streams"].push_back({{"pid",u16(b,p+1)&0x1fff},{"type",b[p]},
                    {"is_audio",audio},{"is_video",video},
                    {"classification_basis","TSDuck PMT classification; private stream types require namespace or descriptor evidence"}});
                p+=5+len;
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
                const size_t first=r.descriptors.size();
                e.update(descriptors(r,p+12,p+12+len,r.ext));
                e["language_variants"]=signalmeta::languages(r,first,duck);
                e["default_language"]=nullptr;e["text"]="";
                e["language_selection"]="First usable short description in language-code order; UI preference is presentation only";
                for(const auto& variant:e["language_variants"])if(variant["short_status"]=="complete"){
                    e["default_language"]=variant["language_code"];e["title"]=variant["title"];e["text"]=variant["short_text"];break;
                }
                r.events.push_back(e);p+=12+len;
            }
        }
    }
    void receive(const uint8_t* data,size_t size,unsigned pid,uint64_t first,uint64_t last,bool valid) {
        if(size<3)return;
        first+=demuxOffset;last+=demuxOffset;
        const size_t bucket=std::min<uint64_t>(79,first*80/std::max<uint64_t>(1,totalBytes/stride));++densityCounts[bucket];
        ++observations; Bytes b(data,data+size);
        unsigned tid=b[0],ext=size>=8&&(b[1]&0x80)?u16(b,3):0;
        unsigned ver=size>=8&&(b[1]&0x80)?(b[5]>>1)&31:0,num=size>=8&&(b[1]&0x80)?b[6]:0;
        std::string key=std::to_string(pid)+":"+std::to_string(tid)+":"+std::to_string(ext)+":"+std::to_string(num);
        std::string id=key+":"+fingerprint(b);
        const bool j94=standardsContext=="j94-system-b"&&cableoob::table(tid);
        if(j94){key+=":j94-observation="+fingerprint(b);id=key;}
        auto it=ids.find(id);
        if(it==ids.end()) {
            if(records.size()>=50000)throw std::runtime_error("Unique-section limit (50000) exceeded; narrow input");
            Record r; r.id=id;r.key=key;r.raw=std::move(b);r.pid=pid;r.tid=tid;r.ext=ext;r.version=ver;r.number=num;r.valid=valid;r.j94=j94;
            r.current=size>=8&&(data[1]&0x80)?(data[5]&1)!=0:true;r.last=size>=8&&(data[1]&0x80)?data[7]:0;
            // SectionDemux validates long-section CRCs, but short TOT/SCTE-35
            // integrity must also be checked before derived/export selection.
            const auto crcStatus=crcEvidence(r)["status"];
            if(crcStatus=="invalid")issue(r,"crc32",size-4,"MPEG-2 CRC32 mismatch; excluded from derived services");
            else if(r.j94&&crcStatus!="valid")issue(r,"j94_crc_unavailable",0,"J.94 requires a complete verified CRC; raw bytes retained without semantic decoding");
            else if(!valid)issue(r,"invalid_section",0,"Rejected by TSDuck section demux");
            decode(r); ids[id]=records.size();records.push_back(std::move(r));it=ids.find(id);
        }
        Record& r=records[it->second];densityBad[bucket]+=!r.valid;r.positions.push_back(first);r.ends.push_back(last);r.orders.push_back(observations);r.lastPacket=last;
        // All captured table families, including short/private/invalid/next
        // evidence. Each entry is a content transition of an exact section slot,
        // not a claim that a multi-section generation was complete at arrival.
        const std::string historyKey=key+":"+(r.current?"current":"next")+":"+(r.valid?"valid":"invalid");
        auto slot=historySlots.find(historyKey);
        if(slot==historySlots.end() || tableHistory[slot->second]["id"]!=id) {
            historySlots[historyKey]=tableHistory.size();
            tableHistory.push_back({{"id",id},{"event_id",tableHistory.size()},{"pid",pid},{"table_id",tid},{"extension",ext},
                {"name",nativeTableName(r)},{"version",(data[1]&0x80)?J(ver):J()}, {"section",num},{"current",r.current},{"valid",r.valid},
                {"first_packet",first},{"at_packet",last},{"last_packet",last},{"observations",1}});
            if(r.j94){auto& item=tableHistory.back();for(const auto* field:{"extension","version","section","current"})item[field]=nullptr;item["versioning_supported"]=false;item["header_semantics"]="J.94 exact section observation; no wire version/section numbering";}
            if(r.tid==0x70||r.tid==0x73){auto& item=tableHistory.back();for(const auto* field:{"extension","version","section","current"})item[field]=nullptr;item["versioning_supported"]=false;item["header_semantics"]="DVB short syntax; exact time observation";if(r.fields.contains("utc_time"))item["utc_time"]=r.fields["utc_time"];}
        } else {
            auto& entry=tableHistory[slot->second]; entry["last_packet"]=last;
            entry["observations"]=entry["observations"].get<uint64_t>()+1;
        }
        if(!r.issues.empty() && r.issues[0]["code"]=="crc32")++crcErrors;
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
        if(r.j94)return cableoob::name(r.tid);
        const auto& table=ts::PSIRepository::Instance().getTable(ts::TID(r.tid),ts::SectionContext(ts::PID(r.pid),duck.standards()));
        if(table.factory&&!table.xml_name.empty())return table.xml_name.toUTF8();
        return tableName(r.tid)!="Private / other"?tableName(r.tid):"Unknown / private (table id "+std::to_string(r.tid)+")";
    }
    J crcEvidence(const Record& r) const {
        const auto& b=r.raw;
        const bool carries=b.size()>=3&&((b[1]&0x80)!=0||r.tid==0x73||r.tid==0xfc||r.j94);
        const bool knownNoCRC=r.tid==0x70||r.tid==0x71||r.tid==0x72||r.tid==0x7e;
        J out={{"status",!carries&&knownNoCRC?"not_present":"unavailable"},{"transmitted_hex",nullptr},{"calculated_hex",nullptr}};
        // Only interpret the trailing bytes as CRC when the whole declared section exists.
        if(carries&&b.size()>=7&&size_t(3+((b[1]&15)<<8)+b[2])==b.size()){
            const uint32_t value=ts::CRC32(b.data(),b.size()-4).value();
            const uint8_t bytes[]={uint8_t(value>>24),uint8_t(value>>16),uint8_t(value>>8),uint8_t(value)};
            out["transmitted_hex"]=hex(b.data()+b.size()-4,4);out["calculated_hex"]=hex(bytes,4);
            out["status"]=ts::CRC32(b.data(),b.size()).value()==0?"valid":"invalid";
        }
        return out;
    }
    J evidenceIdentity(const Record& r) const {
        if(r.tid==0x70||r.tid==0x73)return {{"table_key",tableGroup(r)},{"pid",r.pid},{"table_id",r.tid},{"extension",nullptr},{"version",nullptr},{"current_next",nullptr},{"section_number",nullptr},{"last_section_number",nullptr},{"versioning_supported",false},{"header_semantics","DVB short syntax; exact section observation"}};
        if(r.j94)return {{"table_key",tableGroup(r)},{"pid",r.pid},{"table_id",r.tid},{"extension",nullptr},{"version",nullptr},{"current_next",nullptr},{"section_number",nullptr},{"last_section_number",nullptr},{"versioning_supported",false},{"header_semantics","J.94 short envelope; exact section observation, not an assembled map"}};
        return {{"table_key",tableGroup(r)},{"pid",r.pid},{"table_id",r.tid},{"extension",r.ext},{"version",r.version},{"current_next",r.current},{"section_number",r.number},{"last_section_number",r.last}};
    }
    J distribution(const std::vector<const Record*>& parts,uint64_t at,const std::shared_ptr<AnalysisControl>& control=nullptr) const {
        const uint64_t extent=std::max<uint64_t>(1,at==UINT64_MAX?packets:std::min(packets,at+1));
        const size_t bins=size_t(std::min<uint64_t>(32,extent));
        J out={{"basis",bitrate>0?"user supplied bitrate":"packet index"},{"pcr_derived",false},{"observation_count",0},{"first_packet",nullptr},{"last_packet",nullptr},{"first_seconds",nullptr},{"last_seconds",nullptr},{"min_gap_packets",nullptr},{"max_gap_packets",nullptr},{"mean_gap_packets",nullptr},{"bins",J::array()}};
        std::vector<uint64_t> counts(bins),bad(bins);std::vector<size_t> limits;
        // Merge sorted per-variant occurrences without copying/sorting all observations.
        using Cursor=std::tuple<uint64_t,size_t,size_t>;std::priority_queue<Cursor,std::vector<Cursor>,std::greater<Cursor>> pending;
        for(size_t i=0;i<parts.size();++i){checkCancelled(control);const auto& r=*parts[i];limits.push_back(std::upper_bound(r.ends.begin(),r.ends.end(),at)-r.ends.begin());if(limits.back())pending.emplace(r.positions[0],i,0);}
        uint64_t count=0,first=0,last=0,low=UINT64_MAX,high=0;
        while(!pending.empty()){
            if((count&255)==0)checkCancelled(control);
            const auto [pos,part,occurrence]=pending.top();pending.pop();const auto& r=*parts[part];
            const auto bucket=std::min<uint64_t>(bins-1,pos*bins/extent);++counts[bucket];bad[bucket]+=!r.valid;
            if(count){low=std::min(low,pos-last);high=std::max(high,pos-last);}else first=pos;last=pos;++count;
            if(occurrence+1<limits[part])pending.emplace(r.positions[occurrence+1],part,occurrence+1);
        }
        for(size_t i=0;i<bins;++i)out["bins"].push_back({{"from_packet",(i*extent+bins-1)/bins},{"to_packet",((i+1)*extent+bins-1)/bins-1},{"count",counts[i]},{"bad",bad[i]}});
        out["observation_count"]=count;
        if(count){out["first_packet"]=first;out["last_packet"]=last;if(bitrate>0){out["first_seconds"]=first*188.0*8/bitrate;out["last_seconds"]=last*188.0*8/bitrate;}if(count>1){out["min_gap_packets"]=low;out["max_gap_packets"]=high;out["mean_gap_packets"]=double(last-first)/(count-1);}}
        return out;
    }
    J summary(const Record& r,uint64_t at=UINT64_MAX,const std::shared_ptr<AnalysisControl>& control=nullptr,bool includeDistribution=true) const {
        auto stop=std::upper_bound(r.ends.begin(),r.ends.end(),at); size_t count=size_t(stop-r.ends.begin());
        J out={{"id",r.id},{"key",r.key},{"name",nativeTableName(r)},{"pid",r.pid},{"table_id",r.tid},{"extension",r.ext},{"version",r.version},{"section",r.number},{"last_section",r.last},{"current",r.current},{"valid",r.valid},{"bytes",r.raw.size()},{"count",count},{"first_packet",r.positions.empty()?0:r.positions.front()},{"last_packet",count?*(stop-1):0},{"issue_count",r.issues.size()}};
        if(r.tid>=0x4e&&r.tid<=0x6f&&r.raw.size()>=14){out["segment_last_section_number"]=r.raw[12];out["last_table_id"]=r.raw[13];}
        if(r.j94){for(const auto* key:{"extension","version","section","last_section","current"})out[key]=nullptr;out["versioning_supported"]=false;out["header_semantics"]="J.94 short envelope; no wire version/section numbering";}
        if(r.tid==0x70||r.tid==0x73){
            for(const auto* key:{"extension","version","section","last_section","current"})out[key]=nullptr;
            out["versioning_supported"]=false;out["header_semantics"]="DVB short syntax; no wire version/current-next/section numbering";
            if(r.fields.contains("utc_time"))out["utc_time"]=r.fields["utc_time"];
        }
        out["identity"]=evidenceIdentity(r);out["crc"]=crcEvidence(r);if(includeDistribution)out["distribution"]=distribution({&r},at,control);

        return out;
    }
    J tableGroups(uint64_t at,const std::shared_ptr<AnalysisControl>& control=nullptr,bool includeDistribution=true) const {
        std::map<std::string,std::vector<const Record*>> groups;
        for(const auto& r:records)if(!r.ends.empty()&&r.ends.front()<=at)groups[tableGroup(r)+":v="+std::to_string(r.version)+":current="+std::to_string(r.current)+":last="+std::to_string(r.last)].push_back(&r);
        const auto current=latest(at),next=latest(at,false);J result=J::array();
        for(const auto& [key,parts]:groups){
            checkCancelled(control);const auto& first=*parts.front();std::set<unsigned> seen,good,bad,selectedNumbers;J ids=J::array(),selectedIds=J::array();size_t validCount=0,invalidCount=0;
            const auto& selected=first.current?current:next;
            for(const auto* r:parts){checkCancelled(control);ids.push_back(r->id);seen.insert(r->number);(r->valid?good:bad).insert(r->number);
                const size_t count=std::upper_bound(r->ends.begin(),r->ends.end(),at)-r->ends.begin();(r->valid?validCount:invalidCount)+=count;
                auto chosen=selected.find(sectionKey(*r));if(chosen!=selected.end()&&chosen->second==r){selectedIds.push_back(r->id);selectedNumbers.insert(r->number);}
            }
            J missing=J::array(),missingValid=J::array(),selectedMissing=J::array();
            const bool schedule=first.tid>=0x50&&first.tid<=0x6f;
            std::set<unsigned> expected;
            if(schedule){for(const auto* r:parts)if(r->valid&&r->raw.size()>=14){unsigned segmentLast=r->raw[12];if(segmentLast>=r->number&&segmentLast<=r->last&&segmentLast/8==r->number/8)for(unsigned n=r->number&~7u;n<=segmentLast;++n)expected.insert(n);}}
            else for(unsigned n=0;n<=first.last;++n)expected.insert(n);
            for(unsigned n:expected){if(!seen.count(n))missing.push_back(n);if(!good.count(n))missingValid.push_back(n);}
            for(unsigned n=0;n<=first.last;++n)if(!selectedNumbers.count(n))selectedMissing.push_back(n);
            J compactDistribution={{"observation_count",validCount+invalidCount},{"first_packet",nullptr},{"last_packet",nullptr},{"detail_available",true}};
            uint64_t firstPosition=UINT64_MAX,lastPosition=0;for(const auto* r:parts){auto stop=std::upper_bound(r->ends.begin(),r->ends.end(),at);if(stop!=r->ends.begin()){firstPosition=std::min(firstPosition,r->positions.front());lastPosition=std::max(lastPosition,r->positions[size_t(stop-r->ends.begin())-1]);}}
            if(firstPosition!=UINT64_MAX){compactDistribution["first_packet"]=firstPosition;compactDistribution["last_packet"]=lastPosition;}
            J groupIdentity=evidenceIdentity(first);groupIdentity.erase("section_number");
            result.push_back({{"id",key},{"name",nativeTableName(first)},{"identity",groupIdentity},{"pid",first.pid},{"table_id",first.tid},{"extension",first.ext},{"version",first.version},{"current",first.current},{"last_section",first.last},{"section_ids",ids},{"observed_section_numbers",seen},{"valid_section_numbers",good},{"invalid_section_numbers",bad},{"missing_section_numbers",missing},{"missing_valid_section_numbers",missingValid},{"selected_section_ids",selectedIds},{"selected_missing_section_numbers",selectedMissing},{"selected_complete",selectedMissing.empty()&&!selectedIds.empty()},{"validity",validCount?(invalidCount?"mixed":"valid"):"all_invalid"},{"valid_observations",validCount},{"invalid_observations",invalidCount},{"distribution",includeDistribution?distribution(parts,at,control):compactDistribution},{"coverage_model",schedule?"observed EIT schedule segment ranges only":"section_number 0 through last_section_number"},{"expected_section_numbers",expected},{"schedule_unobserved_segments_unknown",schedule},{"coverage_scope","observed version across capture cutoff; selected_* uses generation-safe snapshot; repetitions are not missing sections; EIT schedule segment completeness not inferred"}});
        }
        std::sort(result.begin(),result.end(),[](const J& a,const J& b){return std::tuple(a["pid"].get<unsigned>(),a["table_id"].get<unsigned>(),a["extension"].get<unsigned>(),a["version"].get<unsigned>(),a["current"].get<bool>(),a["id"].get<std::string>())<std::tuple(b["pid"].get<unsigned>(),b["table_id"].get<unsigned>(),b["extension"].get<unsigned>(),b["version"].get<unsigned>(),b["current"].get<bool>(),b["id"].get<std::string>());});
        for(auto& group:result)if(group["identity"].value("versioning_supported",true)==false){
            for(const auto* key:{"extension","version","last_section","current"})group[key]=nullptr;
            for(const auto* key:{"observed_section_numbers","valid_section_numbers","invalid_section_numbers","missing_section_numbers","missing_valid_section_numbers","selected_missing_section_numbers","expected_section_numbers"})group[key]=J::array();
            group["versioning_supported"]=false;group["selected_complete"]=false;
            const bool dvbTime=group["table_id"]==0x70||group["table_id"]==0x73;
            group["coverage_model"]=dvbTime?"exact DVB time section observation; no section numbering":"exact J.94 section observation; map assembly unsupported";
            group["coverage_scope"]=dvbTime?"Content observations; no inferred wire version or numbered-section coverage":"No inferred version, missing ranges or complete network/channel map";
        }
        return result;
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
        for(auto& [key,s]:services) {
            unsigned sid=s["id"];s["key"]=key;s["service_type"]=s.value("type",J());s["service_type_name"]=nullptr;
            if(s["service_type"].is_number_unsigned()||s["service_type"].is_number_integer()){
                const auto name=ts::ServiceTypeName(s["service_type"].get<uint8_t>()).toUTF8();
                if(name.find("unknown")==std::string::npos&&name.find("Unknown")==std::string::npos)s["service_type_name"]=name;
            }
            auto pat=pmts.find({s["ts_id"].get<unsigned>(),sid});s["pmt_pid"]=pat!=pmts.end()?J(pat->second):J();
            s["audio_pids"]=J::array();s["video_pids"]=J::array();s["media_status"]="PMT unavailable";
            if(pat!=pmts.end()){auto pmt=components.find({pat->second,sid});if(pmt!=components.end()){
                s["components"]=pmt->second;s["media_status"]="decoded PMT";
                for(const auto& stream:pmt->second.value("streams",J::array())){
                    if(stream.value("is_audio",false))s["audio_pids"].push_back(stream["pid"]);
                    if(stream.value("is_video",false))s["video_pids"].push_back(stream["pid"]);
                }
            }}
            s["lcn_candidates"]=J::array();
            s["lcn_list_candidates"]=J::array();
            for(const auto& [unused,ptr]:selected){const auto& r=*ptr;if(!completeGroup(r,selected))continue;
                for(const auto& d:r.descriptors){
                    auto add=[&](const J& number,const J& visible){s["lcn_candidates"].push_back({{"number",number},{"visible",visible},{"region",nullptr},{"namespace",d.value("extension",d.value("name",std::string("unknown")))},{"pds",d["pds"]},{"source_id",r.id},{"descriptor_offset",d["offset"]}});};
                    if(r.id==s["source_id"].get<std::string>()&&d["service_id"]==sid&&d["fields"].contains("logical_channel_number"))add(d["fields"]["logical_channel_number"],nullptr);
                    if(r.tid!=0x40&&r.tid!=0x41&&r.tid!=0x4a)continue;
                    for(const auto& transport:r.fields.value("transports",J::array())){
                        const size_t start=transport["descriptor_offset"],length=transport["descriptor_bytes"],offset=d["offset"];
                        if(transport["transport_stream_id"]!=s["ts_id"]||transport["original_network_id"]!=s["onid"]||offset<start||offset>=start+length)continue;
                        for(const auto& entry:d.value("lcn_entries",J::array()))if(entry["service_id"]==sid)add(entry["number"],entry["visible"]);
                        if(r.tid==0x40||r.tid==0x41)nordigmeta::append(s,d,r.id);
                    }
                }
            }
            std::set<J> numbers,visibility,namespaces;
            for(const auto& candidate:s["lcn_candidates"]){numbers.insert(candidate["number"]);visibility.insert(candidate["visible"]);namespaces.insert(candidate["namespace"]);}
            const bool conflict=numbers.size()>1||visibility.size()>1||namespaces.size()>1;
            s["lcn_status"]=numbers.empty()?"unknown":conflict?"conflict":"known";
            s["logical_channel_number"]=numbers.size()==1&&!conflict?*numbers.begin():J();
            nordigmeta::finish(s);
            s["lcn_scope"]="Exact ONID/TSID/SID and on-wire namespace; NorDig v2 list candidates retain country/list evidence and require explicit selection; HD-simulcast mappings not selected";
            s["group"]=s.value(groupBy,J("Unassigned"));out["services"].push_back(s);
        }
        std::string sort=extension.value("organization",J::object()).value("sort_by",std::string("id"));
        std::sort(out["services"].begin(),out["services"].end(),[&](const J&a,const J&b){J av=a.value(sort,J());J bv=b.value(sort,J());return (av.is_null()?a["id"]:av)<(bv.is_null()?b["id"]:bv);});
        return out;
    }

public:
    explicit Engine(fs::path p):root(std::move(p)) { if(fs::exists(root/"extensions/demo.json"))extension=readJson(root/"extensions/demo.json"); configuredExtension=extension; }
    void handleSection(ts::SectionDemux& demux,const ts::Section& s) override {
        // Discover dependent signalling PIDs before later packets in this block.
        if(s.tableId()==0&&s.sourcePID()==0&&s.isLongSection()&&s.size()>=12) { const auto* b=s.content(); for(size_t p=8;p+4<=s.size()-4;p+=4)demux.addPID(((b[p+2]&31)<<8)|b[p+3]); }
        if(s.tableId()==0xc7&&(standardsContext=="auto"||standardsContext=="atsc")&&s.sectionNumber()==0&&s.lastSectionNumber()==0){
            ts::BinaryTable binary;binary.addNewSection(s.content(),s.size(),s.sourcePID(),ts::CRC32::CHECK);ts::MGT mgt(duck,binary);
            if(mgt.isValid())for(const auto& entry:mgt.tables)demux.addPID(entry.second.table_type_PID);
        }
        if(s.tableId()==2&&s.isLongSection()&&s.size()>=16){
            const auto* b=s.content();size_t end=s.size()-4,p=12+(((b[10]&15)<<8)|b[11]);
            while(p+5<=end){size_t len=((b[p+3]&15)<<8)|b[p+4];if(p+5+len>end)break;
                if(b[p]==0x05||b[p]==0x0b||b[p]==0x0d||b[p]==0x13||b[p]==0x14||b[p]==0x86)demux.addPID(((b[p+1]&31)<<8)|b[p+2]);p+=5+len;
            }
        }
        receive(s.content(),s.size(),s.sourcePID(),s.firstTSPacketIndex(),s.lastTSPacketIndex(),true);
    }
    void handleInvalidSection(ts::SectionDemux&,const ts::DemuxedData& s,ts::Section::Status) override { receive(s.content(),s.size(),s.sourcePID(),s.firstTSPacketIndex(),s.lastTSPacketIndex(),false); }
    void appendStandardsMetadata(J& out) const {
        out["standards_context"]=standardsContext;
        out["detected_standards"]=standardsNames(duck.standards());
        if(standardsContext=="j94-system-b"){
            out["sdk_inferred_standards"]=out["detected_standards"];
            out["detected_standards"]="MPEG (J.94 System B selected explicitly)";
            out["standards_inference_warning"]="SDK family inference from colliding private table IDs is not evidence of ATSC/ISDB in the explicit J.94 profile";
        }
    }
    J state(uint64_t at=UINT64_MAX,const std::shared_ptr<AnalysisControl>& control=nullptr) {
        checkCancelled(control);
        J out={{"source",pathUtf8(source)},{"file_name",pathUtf8(source.filename())},{"source_bytes",totalBytes},{"packets",packets},{"packet_size",stride},{"observations",observations},{"crc_errors",crcErrors},{"complete",complete},{"analysis_status",analysisStatus},{"revision",revision},{"extension_id",extension.value("id",std::string("none"))},{"time_basis",bitrate>0?"user supplied bitrate":"packet index"},{"bitrate",bitrate},{"tables",J::array()},{"services",J::array()},{"events",J::array()},{"history",history},{"diagnostics",J::array()},{"density",J::array()},{"metrics",{{"first_section_ms",firstMs},{"scan_ms",analysisStatus=="analyzing"?ms(began):totalMs}}}};
        out["analysis_revision"]=revision;out["text_charset"]=duck.charsetIn()->name().toUTF8();out["time_reference"]=duck.timeReferenceName().toUTF8();
        appendStandardsMetadata(out);
        const auto selected=latest(at);
        for(const auto& r:records) {
            checkCancelled(control);
            auto stop=std::upper_bound(r.ends.begin(),r.ends.end(),at);if(stop==r.ends.begin())continue;
            out["tables"].push_back(summary(r,at,control));
            for(auto d:r.issues) { d["id"]=r.id;d["pid"]=r.pid;d["packet"]=r.positions.front();d["count"]=size_t(stop-r.ends.begin());out["diagnostics"].push_back(d); }
        }
        checkCancelled(control);const auto derived=derivedSnapshot(selected);checkCancelled(control);out["services"]=derived["services"];out["events"]=derived["events"];
        constexpr size_t bins=80; std::vector<uint64_t> counts(bins,0),bad(bins,0); uint64_t denominator=std::max<uint64_t>(1,totalBytes/stride);
        for(const auto& r:records)for(auto pos:r.positions){checkCancelled(control);size_t bucket=std::min<uint64_t>(bins-1,pos*bins/denominator);counts[bucket]++;if(!r.valid)bad[bucket]++;}
        for(size_t i=0;i<bins;i++)out["density"].push_back({{"count",counts[i]},{"bad",bad[i]}});
        out["table_groups"]=tableGroups(at,control);out["timing"]={{"packet_unit","zero-based TS packet index"},{"seconds_per_packet",bitrate>0?J(188.0*8/bitrate):J()},{"bitrate_unit","bits/second for 188-byte TS packets"},{"basis",bitrate>0?"user supplied bitrate":"packet index"},{"pcr_derived",false},{"note","Arrival positions are TS packet indexes; seconds require supplied 188-byte TS bitrate, not measured PCR timing"}};
        out["transport_summary"]=transportStatistics.summary(bitrate);
        out["selected_packet"]=at==UINT64_MAX?J():J(at);out["demux"]=demuxStatus;out["scope"]={{"tables_services_events","selected packet"},{"history_density_counters_demux","entire scan"},{"services","complete actual SDT on canonical PID 0x0011; nonstandard SDT PIDs remain table evidence"}};
        out["table_history"]=tableHistory;
        out["scope"]["table_history"]="entire scan; content transitions per PID/table/extension/section/current/validity; at_packet is first completed occurrence; not complete-generation transitions";
        if(demuxStatus.value("discontinuities",uint64_t(0))>0)out["diagnostics"].push_back({{"code","transport_discontinuity"},{"detail","TSDuck continuity-counter discontinuities on monitored PSI/SI PIDs (aggregate; packet locations not yet retained)"},{"count",demuxStatus["discontinuities"]},{"pid",0},{"packet",0},{"id",""},{"aggregate",true}});
        out["coverage"]=coverage;out["coverage"]["scanned_packets"]=scannedPackets;
        return out;
    }
    // Compact transport never enumerates occurrences or copies transition logs.
    J compactState(uint64_t at=UINT64_MAX) {
        const size_t visibleTables=at==UINT64_MAX?records.size():size_t(std::count_if(records.begin(),records.end(),[&](const Record& r){return !r.ends.empty()&&r.ends.front()<=at;}));
        J counts={{"tables",visibleTables},{"history",history.size()},{"table_history",tableHistory.size()},{"density",80},{"services",nullptr},{"events",nullptr},{"diagnostics",nullptr},{"table_groups",nullptr}};
        if(cacheCutoff==at)for(auto it=resultCache.begin();it!=resultCache.end();++it)counts[it.key()]=it.value().size();
        J cov=coverage;cov["scanned_packets"]=scannedPackets;
        J out={{"response_mode","compact"},{"source",pathUtf8(source)},{"file_name",pathUtf8(source.filename())},{"source_bytes",totalBytes},{"packets",packets},{"packet_size",stride},{"observations",observations},{"crc_errors",crcErrors},{"complete",complete},{"analysis_status",analysisStatus},{"revision",revision},{"analysis_revision",revision},{"extension_id",extension.value("id",std::string("none"))},{"bitrate",bitrate},{"time_basis",bitrate>0?"user supplied bitrate":"packet index"},{"text_charset",duck.charsetIn()->name().toUTF8()},{"time_reference",duck.timeReferenceName().toUTF8()},{"selected_packet",at==UINT64_MAX?J():J(at)},{"coverage",cov},{"result_counts",counts},{"progress_fraction",plannedPackets?double(scannedPackets)/plannedPackets:0.0},{"demux",demuxStatus},{"timing",{{"seconds_per_packet",bitrate>0?J(188.0*8/bitrate):J()},{"basis",bitrate>0?"user supplied bitrate":"packet index"},{"pcr_derived",false}}},{"metrics",{{"scan_ms_basis","Wall elapsed time including pauses and owner finalization; excludes client result hydration"},{"first_section_ms",firstMs},{"scan_ms",(analysisStatus=="analyzing"||analysisStatus=="paused"||analysisStatus=="finalizing")?ms(began):totalMs}}}};
        out["transport_summary"]=transportStatistics.summary(bitrate);
        appendStandardsMetadata(out);return out;
    }
    J queryTransport(const J& args) const {
        if(!complete)throw std::runtime_error("Complete a successful analysis before querying transport statistics");
        if(args.at("analysis_revision")!=revision)throw std::runtime_error("Stale transport analysis_revision");
        auto out=transportStatistics.page(args.value("offset",size_t(0)),args.value("limit",size_t(100)),args.value("errors_only",false),args.value("sort",std::string("pid")),args.value("descending",false),bitrate);
        out["aggregate_errors"]=J::array();
        const auto badSync=out["summary"]["bad_sync_packets"].get<uint64_t>();
        if(badSync)out["aggregate_errors"].push_back({{"code","transport_sync_error"},{"pid",nullptr},{"id",nullptr},{"aggregate",true},{"count",badSync},{"detail","Invalid sync byte; PID and exact source section are unavailable"}});
        out["analysis_revision"]=revision;out["source"]=pathUtf8(source);out["coverage"]=coverage;return out;
    }
    J queryResult(const J& args) {
        if(!complete)throw std::runtime_error("Complete the requested scan before querying result pages");
        if(args.at("analysis_revision")!=revision)throw std::runtime_error("Stale result analysis_revision");
        const uint64_t at=args.value("at_packet",UINT64_MAX);
        if(at!=UINT64_MAX&&at>=packets)throw std::runtime_error("Result cutoff is outside analyzed source extent");
        if(at!=cacheCutoff){resultCache=J::object();cacheCutoff=at;}
        const std::string collection=args.at("collection");
        const J* rows=nullptr;
        if(collection=="history")rows=&history;
        else if(collection=="table_history")rows=&tableHistory;
        else {
            if(!resultCache.contains(collection)){
                J items=J::array();
                if(collection=="tables"){
                    const auto chosen=latest(at),chosenNext=latest(at,false);for(const auto& r:records)if(!r.ends.empty()&&r.ends.front()<=at){auto item=summary(r,at,nullptr,false);item["table_group_id"]=tableGroup(r)+":v="+std::to_string(r.version)+":current="+std::to_string(r.current)+":last="+std::to_string(r.last);const auto& selection=r.current?chosen:chosenNext;const auto found=selection.find(sectionKey(r));item["selected_in_snapshot"]=found!=selection.end()&&found->second==&r;items.push_back(std::move(item));}
                }else if(collection=="services"||collection=="events"){
                    auto derived=derivedSnapshot(latest(at));resultCache["services"]=std::move(derived["services"]);resultCache["events"]=std::move(derived["events"]);
                }else if(collection=="table_groups"){
                    items=tableGroups(at,nullptr,false);
                    for(auto& item:items){
                        for(const char* field:{"section_ids","selected_section_ids"})if(item[field].size()>128){item[std::string(field)+"_total"]=item[field].size();item[field].erase(item[field].begin()+128,item[field].end());item["member_ids_truncated"]=true;}
                    }
                }else if(collection=="density"){
                    for(size_t i=0;i<80;++i)items.push_back({{"count",densityCounts[i]},{"bad",densityBad[i]}});
                }else if(collection=="diagnostics"){
                    for(const auto& r:records){const auto stop=std::upper_bound(r.ends.begin(),r.ends.end(),at);if(stop==r.ends.begin())continue;for(auto d:r.issues){d["id"]=r.id;d["pid"]=r.pid;d["packet"]=r.positions.front();d["count"]=size_t(stop-r.ends.begin());items.push_back(std::move(d));}}
                    if(demuxStatus.value("discontinuities",uint64_t(0)))items.push_back({{"code","transport_discontinuity"},{"detail","TSDuck continuity-counter discontinuities within observed contiguous windows"},{"count",demuxStatus["discontinuities"]},{"pid",0},{"packet",0},{"id",""},{"aggregate",true}});
                }
                if(!resultCache.contains(collection))resultCache[collection]=std::move(items);
            }
            rows=&resultCache.at(collection);
        }
        const size_t offset=args.value("offset",size_t(0)),limit=args.value("limit",size_t(200));
        J items=J::array();size_t bytes=0;
        for(size_t i=offset;i<rows->size()&&items.size()<limit;++i){const size_t size=(*rows)[i].dump(-1,' ',false,J::error_handler_t::replace).size();if(size>262144)throw std::runtime_error("Result item exceeds compact page byte limit; use specific section inspection");if(bytes+size>262144)break;items.push_back((*rows)[i]);bytes+=size;}
        const size_t next=offset+items.size();
        return {{"analysis_revision",revision},{"collection",collection},{"items",items},{"total",rows->size()},{"next_offset",next<rows->size()?J(next):J()},{"at_packet",at==UINT64_MAX?J():J(at)},{"item_payload_byte_limit",262144},{"coverage",coverage}};
    }
    // Semantic reconstruction must never use siblings or module blocks from an
    // earlier disjoint window, even when their wire versions happen to match.
    std::vector<Record> segmentRecords(uint64_t at) const {
        uint64_t start=0;for(const auto& range:coverage.value("ranges",J::array()))if(range["start_packet"].get<uint64_t>()<=at)start=range["start_packet"].get<uint64_t>();
        std::vector<Record> out;
        for(const auto& original:records){auto first=std::lower_bound(original.positions.begin(),original.positions.end(),start),last=std::upper_bound(original.ends.begin(),original.ends.end(),at);const size_t a=first-original.positions.begin(),b=last-original.ends.begin();if(a>=b)continue;out.emplace_back();auto& r=out.back();r.id=original.id;r.key=original.key;r.raw=original.raw;r.pid=original.pid;r.tid=original.tid;r.ext=original.ext;r.version=original.version;r.number=original.number;r.last=original.last;r.valid=original.valid;r.current=original.current;r.j94=original.j94;r.descriptors=original.descriptors;r.services=original.services;r.events=original.events;r.issues=original.issues;r.fields=original.fields;r.positions.assign(original.positions.begin()+a,original.positions.begin()+b);r.ends.assign(original.ends.begin()+a,original.ends.begin()+b);r.orders.assign(original.orders.begin()+a,original.orders.begin()+b);r.lastPacket=r.ends.back();}
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
                J value=summary(r,at);value["complete_group"]=!r.j94&&completeGroup(r,selected);
                J content={{"version",r.version},{"last_section",r.last},{"payload",r.id}};
                if(r.j94){identity=evidenceIdentity(r);identity["observation_key"]=r.key;content["version"]=nullptr;content["last_section"]=nullptr;}
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
                // Evidence location/version changes alone are not service changes.
                std::set<J> semanticCandidates;
                for(auto candidate:content["lcn_candidates"]){candidate.erase("source_id");candidate.erase("descriptor_offset");semanticCandidates.insert(std::move(candidate));}
                content["lcn_candidates"]=semanticCandidates;
                content["lcn_list_candidates"]=nordigmeta::semanticCandidates(content["lcn_list_candidates"]);
                std::vector<const Record*> sources={&r};
                J allCandidates=service["lcn_candidates"];for(const auto& candidate:service["lcn_list_candidates"])allCandidates.push_back(candidate);
                for(const auto& candidate:allCandidates){
                    const auto* source=&records.at(ids.at(candidate["source_id"].get<std::string>()));
                    if(std::find(sources.begin(),sources.end(),source)==sources.end())sources.push_back(source);
                }
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
                signalmeta::removeSources(content["language_variants"]);
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
        J out={{"source",pathUtf8(source)},{"revision",revision},{"from_packet",from},{"to_packet",to},{"kind",kind},{"summary",J::object()},{"changes",J::array()},{"offset",offset},{"limit",limit},{"next_offset",nullptr}};
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
        records.clear();ids.clear();history=J::array();previous.clear();tableHistory=J::array();historySlots.clear();pending=J::object();patchSections.clear();
        observations=crcErrors=0;transportStatistics.clear();demuxStatus=J::object();resultCache=J::object();cacheCutoff=UINT64_MAX;densityCounts.fill(0);densityBad.fill(0);
    }
    // Bounded admission check, before replacing the existing analysis identity.
    // The actual scan reopens and revalidates the source to detect later changes.
    void validateCandidate(const J& args) const {
        const auto candidate=fs::absolute(pathFromUtf8(args.at("path").get<std::string>()));
        std::error_code error;
        if(!fs::is_regular_file(candidate,error))throw std::runtime_error("Source must be a regular local file");
        std::ifstream input(candidate,std::ios::binary);
        if(!input)throw std::runtime_error("Cannot read source file");
        const auto bytes=fs::file_size(candidate);
        if(bytes<188)throw std::runtime_error("Source is too small for a TS packet");
        std::array<uint8_t,5*204> probe{};input.read(reinterpret_cast<char*>(probe.data()),probe.size());
        const size_t got=size_t(input.gcount());size_t width=0;
        if(input.bad())throw std::runtime_error("Cannot read source framing");
        for(size_t candidateWidth:{size_t(188),size_t(192),size_t(204)}) {
            const size_t offset=candidateWidth==192?4:0;bool valid=got>offset;
            for(size_t i=0;i<5&&offset+i*candidateWidth<got;i++)valid&=probe[offset+i*candidateWidth]==0x47;
            if(valid){width=candidateWidth;break;}
        }
        if(!width)throw std::runtime_error("No aligned 188/192/204-byte TS framing at file start");
        const auto charset=args.value("default_charset",std::string());
        if(!charset.empty()&&!ts::Charset::GetCharset(ts::UString::FromUTF8(charset)))throw std::runtime_error("Unsupported default_charset: "+charset);
        const auto mode=args.value("scan_mode",std::string("full"));
        if(args.contains("sample_percent")&&args.contains("max_packets"))throw std::runtime_error("Specify sample_percent or max_packets, not both");
        if(args.contains("sample_percent")&&mode!="prefix"&&mode!="distributed")throw std::runtime_error("sample_percent is supported only for prefix or distributed scans");
        if(mode=="range") {
            const auto start=args.value("start_packet",uint64_t(0)),end=args.value("end_packet",bytes/width);
            if(start>=end||end>bytes/width)throw std::runtime_error("Range must satisfy 0 <= start_packet < end_packet <= source packets");
        }
    }
    J analyze(const J& args,const J& rid,const std::shared_ptr<AnalysisControl>& control) {
        if(!control||!control->cancelled.load()) {
            try { validateCandidate(args); }
            catch(const std::exception& error) {
                if(!control||!control->finish())throw RejectedInput(error.what());
            }
        }
        // A new scan owns a new revision even when opening or framing fails.
        // Never allow old evidence or preview tokens to acquire a new source label.
        clearEvidence();++revision;analysisStatus="analyzing";
        source.clear();analysisSourceKnown=false;packets=totalBytes=0;complete=false;coverage=J::object();scannedPackets=plannedPackets=demuxOffset=0;compactResponse=args.value("response_mode",std::string("legacy"))=="compact";
        firstMs=-1;totalMs=0;stride=188;prefix=0;onFirst=nullptr;began=Clock::now();requestId=rid;
        std::string pausedPhase;
        if(control)control->onPause=[&](bool paused){if(paused){pausedPhase=analysisStatus;analysisStatus="paused";}else analysisStatus=pausedPhase;if(!control->cancelled.load())emit({{"event","progress"},{"request_id",rid},{"state",compactState()}});};
        try {
        extension=configuredExtension;standardsContext=args.value("standards",std::string("auto"));
        ts::Standards standards=ts::Standards::MPEG;
        if(standardsContext=="dvb")standards|=ts::Standards::DVB|ts::Standards::DVBONLY;
        else if(standardsContext=="atsc")standards|=ts::Standards::ATSC;
        else if(standardsContext=="isdb")standards|=ts::Standards::ISDB;
        else if(standardsContext=="isdb-japan")standards|=ts::Standards::ISDB|ts::Standards::JAPAN;
        else if(standardsContext=="isdb-brazil")standards|=ts::Standards::ISDB|ts::Standards::ABNT;
        else if(standardsContext=="scte")standards|=ts::Standards::SCTE;
        else if(standardsContext=="dtmb")standards|=ts::Standards::DTMB;
        duck.resetStandards(standards);duck.resetDefaultREGIDs();duck.setDefaultCharsetIn(nullptr);duck.setDefaultCharsetOut(nullptr);duck.setTimeReference(u"UTC");
        if(standardsContext=="isdb-japan"){duck.setDefaultCharsetIn(ts::Charset::GetCharset(u"ARIB-STD-B24"));duck.setDefaultCharsetOut(ts::Charset::GetCharset(u"ARIB-STD-B24"));duck.setTimeReference(u"JST");}
        if(standardsContext=="isdb-brazil"){duck.setDefaultCharsetIn(ts::Charset::GetCharset(u"RAW-ISO-8859-15"));duck.setDefaultCharsetOut(ts::Charset::GetCharset(u"RAW-ISO-8859-15"));duck.setTimeReference(u"UTC-3");}
        const auto charsetName=args.value("default_charset",std::string());
        if(!charsetName.empty()){
            const auto* charset=ts::Charset::GetCharset(ts::UString::FromUTF8(charsetName));
            if(!charset)throw std::runtime_error("Unsupported default_charset: "+charsetName);
            duck.setDefaultCharsetIn(charset);
        }
        bitrate=args.value("bitrate",0.0);
        source=fs::absolute(pathFromUtf8(args.at("path").get<std::string>()));
        TEST_CHECKPOINT("before_analysis",control);
        checkCancelled(control);
        // This API scans bounded local files, not blocking pipes or device streams.
        // status follows symlinks, so ordinary links to regular files remain valid.
        std::error_code sourceError;
        if(!fs::is_regular_file(source,sourceError))throw std::runtime_error("Source must be a regular local file");
        std::ifstream in(source,std::ios::binary);
        if(!in)throw std::runtime_error("Cannot read source file");const auto sourceStamp=fs::last_write_time(source);analysisSourceStamp=sourceStamp;analysisSourceKnown=true;totalBytes=fs::file_size(source);if(totalBytes<188)throw std::runtime_error("Source is too small for a TS packet");
        checkCancelled(control);
        std::vector<uint8_t> probe(5*204);in.read(reinterpret_cast<char*>(probe.data()),probe.size());size_t got=size_t(in.gcount());in.clear();in.seekg(0);
        bool framing=false;
        for(size_t width:{size_t(188),size_t(192),size_t(204)}) { size_t off=width==192?4:0;bool ok=true;for(size_t i=0;i<5&&off+i*width<got;i++)ok&=probe[off+i*width]==0x47;if(ok){stride=width;prefix=off;framing=true;break;} }
        if(!framing)throw std::runtime_error("No aligned 188/192/204-byte TS framing at file start");
        const uint64_t sourcePackets=totalBytes/stride;
        const std::string mode=args.value("scan_mode",std::string("full"));
        std::vector<std::pair<uint64_t,uint64_t>> ranges;
        if(args.contains("sample_percent")&&args.contains("max_packets"))throw std::runtime_error("Specify sample_percent or max_packets, not both");
        if(args.contains("sample_percent")&&mode!="prefix"&&mode!="distributed")throw std::runtime_error("sample_percent is supported only for prefix or distributed scans");
        const uint64_t percent=args.value("sample_percent",uint64_t(0));
        const uint64_t budget=percent?std::max<uint64_t>(1,(sourcePackets/100)*percent+(sourcePackets%100)*percent/100):std::min(sourcePackets,args.value("max_packets",uint64_t(250000)));
        if(mode=="full")ranges.emplace_back(0,sourcePackets);
        else if(mode=="prefix")ranges.emplace_back(0,budget);
        else if(mode=="range"){
            const uint64_t start=args.value("start_packet",uint64_t(0)),end=args.value("end_packet",sourcePackets);
            if(start>=end||end>sourcePackets)throw std::runtime_error("Range must satisfy 0 <= start_packet < end_packet <= source packets");
            ranges.emplace_back(start,end);
        }else if(mode=="distributed"){
            const uint64_t count=std::min(budget,args.value("window_count",uint64_t(4)));
            if(budget==sourcePackets)ranges.emplace_back(0,sourcePackets);
            else for(uint64_t i=0,used=0;i<count;++i){
                const uint64_t length=budget/count+(i<budget%count),start=used+(count>1?(sourcePackets-budget)*i/(count-1):0);
                ranges.emplace_back(start,start+length);used+=length;
            }
        }
        std::vector<std::pair<uint64_t,uint64_t>> merged;
        for(const auto& range:ranges){if(!merged.empty()&&merged.back().second==range.first)merged.back().second=range.second;else merged.push_back(range);}
        ranges=std::move(merged);
        coverage={{"mode",mode},{"partial",false},{"source_packets",sourcePackets},{"scanned_packets",0},{"ranges",J::array()},{"range_end","exclusive"},{"ranges_scope","Requested windows; all are observed only when complete=true. scanned_packets counts processed packets."},{"evidence_scope","Only observed contiguous windows; gaps are unknown and never assembled across"}};
        for(const auto& [start,end]:ranges){plannedPackets+=end-start;coverage["ranges"].push_back({{"start_packet",start},{"end_packet",end}});}
        coverage["partial"]=plannedPackets!=sourcePackets;coverage["requested_sample_percent"]=percent?J(percent):J();
        ts::SectionDemux demux(duck,nullptr,this);for(unsigned pid:{0u,1u,2u,0x10u,0x11u,0x12u,0x13u,0x14u,0x16u,0x1bu,0x1cu,0x1eu,0x1fu})demux.addPID(pid);
        if(standardsContext=="auto"||standardsContext.rfind("isdb",0)==0){for(unsigned pid=0x20;pid<=0x29;pid++)demux.addPID(pid);demux.addPID(0x17);demux.addPID(0x2e);}
        if(standardsContext=="auto"||standardsContext=="atsc")for(unsigned pid:{0x1ff7u,0x1ff9u,0x1ffbu})demux.addPID(pid);
        // SCTE18 EAS can use the ATSC PSIP PID. Explicit SCTE context must not
        // hide these already-TS-framed alerts that auto/ATSC mode can inspect.
        // Other unadvertised/OOB capture PIDs still require extra_pids.
        if(standardsContext=="scte")demux.addPID(ts::PID_PSIP);
        if(standardsContext=="j94-system-b")demux.addPID(0x1ffc);
        for(const auto& pid:args.value("extra_pids",J::array())){if(!pid.is_number_integer()||pid<0||pid>8191)throw std::runtime_error("extra_pids entries must be integers in 0..8191");demux.addPID(pid.get<unsigned>());}
        for(auto pid:extension.value("extra_pids",J::array()))demux.addPID(pid.get<unsigned>());
        demux.setInvalidSectionHandler(this);demux.setCurrentNext(true,true);demux.trackInvalidSectionVersions(true);
        auto progress=[&](){
            checkCancelled(control);TEST_CHECKPOINT("before_progress",control);checkCancelled(control);
            J snapshot=compactResponse?compactState():state(UINT64_MAX,control);checkCancelled(control);
            emit({{"event","progress"},{"request_id",rid},{"state",std::move(snapshot)}});
            TEST_CHECKPOINT("after_progress",control);checkCancelled(control);
        };
        onFirst=progress;
        std::vector<uint8_t> block(stride*8192);auto lastNotify=Clock::now();
        uint64_t fed=0;
        for(const auto& [start,end]:ranges){
            // resetPID clears assemblers and CC expectations without altering the
            // demux's running packet index or its dynamically discovered PID set.
            for(unsigned pid=0;pid<8192;++pid)if(demux.hasPID(pid))demux.resetPID(pid);
            demuxOffset=start-fed;packets=start;
            in.clear();in.seekg(std::streamoff(start*stride));if(!in)throw std::runtime_error("Source seek failed");
            while(packets<end) {
                checkCancelled(control);TEST_CHECKPOINT("before_read",control);checkCancelled(control);
                const size_t wanted=size_t(std::min<uint64_t>(8192,end-packets))*stride;
                in.read(reinterpret_cast<char*>(block.data()),wanted);size_t n=size_t(in.gcount());
                if(n!=wanted)throw std::runtime_error("Source changed or read failed; analysis is incomplete");
                for(size_t p=0;p+stride<=n;p+=stride){
                    if((p/stride)%256==0)checkCancelled(control);
                    ts::TSPacket packet;std::memcpy(packet.b,block.data()+p+prefix,188);transportStatistics.observe(packet.b,packets);++packets;++scannedPackets;++fed;demux.feedPacket(packet);
                }
                if(ms(lastNotify)>=100){progress();lastNotify=Clock::now();}
            }
        }
        onFirst=nullptr;checkCancelled(control);
        if(in.bad()||fs::file_size(source)!=totalBytes||fs::last_write_time(source)!=sourceStamp)throw std::runtime_error("Source changed during analysis; evidence discarded");
        ts::SectionDemux::Status status(demux);demuxStatus={{"wrong_crc",status.wrong_crc},{"discontinuities",status.discontinuities},{"invalid_ts",status.invalid_ts},{"invalid_length",status.inv_sect_length},{"truncated_sections",status.truncated_sect}};
        coverage["scanned_packets"]=scannedPackets;
        analysisStatus="finalizing";
        if(compactResponse)emit({{"event","progress"},{"request_id",rid},{"state",compactState()}});
        // Assemble only bounded metadata before the cancellation commit. Lazy
        // collection pages and per-section inspection do the remaining work.
        J out=compactResponse?compactState():state(UINT64_MAX,control);
        TEST_CHECKPOINT("before_complete",control);
        // This is the linearization point: a cancellation accepted before it
        // always wins, and one arriving afterwards must report not_running.
        if(control&&control->finish([&]{if(fs::file_size(source)!=totalBytes||fs::last_write_time(source)!=sourceStamp)throw std::runtime_error("Source changed during analysis; evidence discarded");}))throw CancelledAnalysis();
        complete=true;analysisStatus="complete";totalMs=ms(began);
        TEST_CHECKPOINT("after_complete",control);
        if(control)control->onPause=nullptr;
        out["complete"]=true;out["analysis_status"]="complete";out["progress_fraction"]=1.0;out["metrics"]["scan_ms"]=totalMs;out["trailing_bytes"]=totalBytes%stride;return out;
        } catch(...) {
            if(control){control->onPause=nullptr;control->requestPause(false);}
            onFirst=nullptr;totalMs=ms(began);complete=false;
            const bool cancelled=control&&control->finish();
            clearEvidence();analysisStatus=cancelled?"cancelled":"failed";
            if(cancelled)throw CancelledAnalysis();
            throw;
        }
    }
    J queryCableOob(const J& args) {
        if(!complete||packets==0)throw std::runtime_error("Complete a successful analysis before querying cable subtables");
        if(standardsContext!="j94-system-b")throw std::runtime_error("Cable subtable query requires explicit j94-system-b context");
        auto number=[&](const char* key,uint64_t fallback){
            if(!args.contains(key))return fallback;
            const auto& value=args.at(key);
            if(!value.is_number_unsigned()&&!(value.is_number_integer()&&value.get<int64_t>()>=0))throw std::runtime_error(std::string(key)+" must be a nonnegative integer");
            return value.get<uint64_t>();
        };
        if(number("analysis_revision",revision)!=revision)throw std::runtime_error("Stale cable analysis_revision");
        const uint64_t at=number("at_packet",packets-1),offset=number("offset",0),limit=number("limit",20);
        if(at>=packets)throw std::runtime_error("Cable at_packet must be within the completed analysis");
        if(offset>cableoob::MaxGroups||limit<1||limit>100)throw std::runtime_error("Cable offset/limit outside bounded page range");
        if(offset&&(!args.contains("analysis_revision")||!args.contains("at_packet")))throw std::runtime_error("Cable continuation page requires analysis_revision and at_packet");
        const auto windowRecords=coverage.value("partial",false)?segmentRecords(at):std::vector<Record>{};auto out=cableoob::snapshot(coverage.value("partial",false)?windowRecords:records,at,revision,size_t(offset),size_t(limit));out["coverage"]=coverage;out["semantic_scope"]="Only the contiguous window containing or preceding the cutoff; gaps remain unknown";return out;
    }
    J queryTopology(const J& args) {
        if(!complete||packets==0)throw std::runtime_error("Complete a successful analysis before querying topology");
        if(args.contains("analysis_revision")&&args["analysis_revision"]!=revision)throw std::runtime_error("Stale topology analysis_revision");
        const uint64_t at=args.value("at_packet",packets-1);
        if(at>=packets)throw std::runtime_error("Topology at_packet must be within the completed analysis");
        const auto selected=latest(at);std::vector<const Record*> full;J incomplete=J::array();std::set<std::string> seen;
        for(const auto& [key,r]:selected){
            const bool dvbLayout=standardsContext=="dvb"||standardsContext.rfind("isdb",0)==0;
            const bool applicable=(r->pid==0&&r->tid==0)||r->tid==2||
                (dvbLayout&&((r->pid==0x10&&(r->tid==0x40||r->tid==0x41))||(r->pid==0x11&&(r->tid==0x42||r->tid==0x46))))||
                (standardsContext=="atsc"&&(r->tid==0xc8||r->tid==0xc9));
            if(!applicable)continue;
            if(completeGroup(*r,selected))full.push_back(r);else if(seen.insert(tableGroup(*r)).second)incomplete.push_back({{"code","incomplete_generation"},{"section_id",r->id},{"message","Selected current topology table generation is incomplete; no semantic relationships derived"}});
        }
        size_t raw=0;for(const auto& r:records)if(!r.ends.empty()&&r.ends.front()<=at)raw++;
        ts::DuckContext topologyDuck(&NULLREP);topologyDuck.resetStandards(duck.standards());topologyDuck.setDefaultCharsetIn(duck.charsetIn());topologyDuck.setDefaultCharsetOut(duck.charsetOut());topologyDuck.setTimeReferenceOffset(duck.timeReferenceOffset());
        topology::Builder builder(full,topologyDuck,root,standardsContext,revision,at);auto out=builder.build(args,raw,incomplete);out["coverage"]=coverage;out["semantic_scope"]="Only the contiguous window containing or preceding the cutoff; gaps remain unknown";return out;
    }
    J sourcePacket(const Record& r) const {
        J out={{"status","unavailable"},{"raw_hex",""},{"section_offset",nullptr},{"section_bytes",0}};
        // Read only the first observed 188-byte TS packet, not a reconstructed
        // transport packet. Section linking is allowed only at real PSI starts.
        try {
            if(!analysisSourceKnown || r.positions.empty() || !fs::is_regular_file(source))return out;
            if(fs::file_size(source)!=totalBytes || fs::last_write_time(source)!=analysisSourceStamp){out["status"]="source_changed";return out;}
            const uint64_t offset=r.positions.front()*stride+prefix;
            std::ifstream input(source,std::ios::binary);input.seekg(std::streamoff(offset));Bytes packet(188);input.read(reinterpret_cast<char*>(packet.data()),188);
            if(input.gcount()!=188 || packet[0]!=0x47 || ((unsigned(packet[1]&31)<<8)|packet[2])!=r.pid)return out;
            if(fs::file_size(source)!=totalBytes || fs::last_write_time(source)!=analysisSourceStamp){out["status"]="source_changed";return out;}
            out["status"]="available";out["raw_hex"]=hex(packet);out["packet_index"]=r.positions.front();out["file_offset"]=offset;out["framing_stride"]=stride;
            out["scope"]="First observed source TS packet, 188 bytes; framing prefix/parity excluded";
            const unsigned afc=(packet[3]>>4)&3;
            if((packet[1]&0xc0)!=0x40 || (packet[3]&0xc0) || !(afc&1))return out;
            size_t p=4;if(afc&2)p+=size_t(packet[4])+1;if(p>=188)return out;
            p+=size_t(packet[p])+1;
            for(;p+3<=188 && packet[p]!=0xff;){
                const size_t length=3+((size_t(packet[p+1]&15)<<8)|packet[p+2]);
                const size_t count=std::min(length,188-p);
                if(length==r.raw.size() && std::equal(packet.begin()+p,packet.begin()+p+count,r.raw.begin())){
                    out["section_offset"]=p;out["section_bytes"]=count;break;
                }
                if(length>188-p)break;p+=length;
            }
        }catch(const fs::filesystem_error&){out["status"]="unavailable";}
        return out;
    }
    J inspect(const J& args) {
        if(args.contains("analysis_revision")&&args["analysis_revision"]!=revision)throw std::runtime_error("Stale inspection analysis_revision");
        std::string id=args.at("id");if(!ids.count(id))throw std::runtime_error("Unknown section id");const Record&r=records[ids.at(id)];
        const uint64_t cutoff=args.value("at_packet",r.lastPacket);
        auto observed=std::upper_bound(r.ends.begin(),r.ends.end(),cutoff);
        if(observed==r.ends.begin())throw std::runtime_error("Section was not observed at or before selected packet");
        const size_t occurrenceCount=size_t(observed-r.ends.begin());
        J out=summary(r,cutoff);out["analysis_revision"]=revision;out["evidence_anchors"]=topology::anchors(r,standardsContext);out["native_table_at_packet"]=cutoff;out["native_table_sources"]=J::array();
        out["inspection_scope"]={{"occurrences_and_summary",args.contains("at_packet")?"at or before selected packet":"all occurrences of this section"},{"native_table",args.contains("at_packet")?"selected observed generation at or before selected packet":"selected observed generation at last occurrence of inspected section"}};
        out["source_packet"]=sourcePacket(r);
        out["si_structure"]=siwire::inspect(r.raw,r.descriptors,r.valid && !r.j94);
        out["raw_hex"]=hex(r.raw);out["fields"]=r.fields;out["descriptors"]=r.descriptors;out["issues"]=r.issues;out["services"]=r.services;out["events"]=r.events;
        out["identifier_lookups"]=signalmeta::identifiers(r,standardsContext);
        out["satellite_associations"]=satellitemeta::inspect(root,r);
        out["text_diagnostics"]=J::array();
        for(const auto& d:r.descriptors)for(const auto& t:d.value("text_diagnostics",J::array()))out["text_diagnostics"].push_back(t);
        out["text_diagnostic_scope"]="Selected section, supported DVB SI text fields only. ATSC multiple strings, native-only table loops and private text retain raw evidence without per-field diagnostics.";
        const size_t occurrenceOffset=std::min(occurrenceCount,args.value("occurrence_offset",size_t(0))),occurrenceEnd=occurrenceOffset+std::min(occurrenceCount-occurrenceOffset,args.value("occurrence_limit",occurrenceCount));
        out["semantic_scope"]="Only the contiguous window containing or preceding the cutoff; gaps remain unknown";out["occurrence_total"]=occurrenceCount;out["occurrence_next_offset"]=occurrenceEnd<occurrenceCount?J(occurrenceEnd):J();out["coverage"]=coverage;
        out["occurrences"]=std::vector<uint64_t>(r.positions.begin()+occurrenceOffset,r.positions.begin()+occurrenceEnd);out["occurrence_end_packets"]=std::vector<uint64_t>(r.ends.begin()+occurrenceOffset,r.ends.begin()+occurrenceEnd);out["first_file_offset"]=r.positions.front()*stride+prefix;out["offset_note"]="TS packet offset, not section payload offset; a section may span packets";
        out["text_charset"]=duck.charsetIn()->name().toUTF8();out["time_reference"]=duck.timeReferenceName().toUTF8();out["standards_context"]=standardsContext;out["native_xml_guarded"]=false;out["native_table_complete"]=false;out["native_decode_status"]="invalid section; raw evidence retained";
        out["section_native_text"]=nullptr;out["section_decode_scope"]="Exact original section; no renumbering or synthetic table assembly";
        if(r.j94){
            out["application_decoder"]="ITU-T J.94 (10/2016) Annex B; independent bounded section parser";
            out["section_decode_scope"]="Exact J.94 section; SDK decoding suppressed to avoid colliding ATSC/ISDB identities";
            out["native_xml_guarded"]=true;out["tsduck_xml"]=nullptr;
            out["inspection_scope"]["native_table"]="Exact observed J.94 section only; no map assembly";
            out["native_table_complete"]=r.valid;
            if(r.valid){
                const auto& decoded=r.fields.at("j94_system_b");
                out["native_table_sources"].push_back(summary(r,cutoff));
                out["native_decode_status"]=decoded["decode_status"]=="decoded"?"application J.94 section decoder":"generic raw fallback";
                out["native_table"]=cableoob::tree(decoded,decoded["decode_status"]=="decoded"?cableoob::name(r.tid):"generic_short_table");
            }
        }else if(r.valid){
            std::ostringstream displayText;ts::DuckContext displayDuck(&NULLREP,&displayText);
            displayDuck.resetStandards(duck.standards());displayDuck.setDefaultCharsetIn(duck.charsetIn());displayDuck.setTimeReferenceOffset(duck.timeReferenceOffset());
            ts::TablesDisplay display(displayDuck);ts::Section exact(r.raw.data(),r.raw.size(),ts::PID(r.pid),ts::CRC32::CHECK);display.displaySection(exact);
            bool guardedDisplay=r.tid==ts::TID_DSMCC_UNM&&(duck.standards()&ts::Standards::DVB)==ts::Standards::NONE;
            for(const auto& descriptor:r.descriptors)guardedDisplay|=descriptor.contains("native_decode_warning");
            if(guardedDisplay)out["section_decode_scope"]="SDK section text suppressed because descriptor namespace is guarded; exact raw and contextual descriptor evidence retained";
            else out["section_native_text"]=displayText.str();
            // Share the same generation boundary as query/export, including
            // current/next isolation and version rollover.
            const auto selected=latest(cutoff,r.current);
            std::map<unsigned,const Record*> group;
            for(const auto& [key,candidate]:selected)if(tableGroup(*candidate)==tableGroup(r))group[candidate->number]=candidate;
            for(const auto& [number,part]:group)out["native_table_sources"].push_back(summary(*part,cutoff));
            ts::BinaryTable table;bool full=group.size()==r.last+1;
            const bool superseded=!group.count(r.number)||group.at(r.number)->id!=r.id;if(superseded)full=false;
            for(unsigned i=0;i<=r.last;i++){auto found=group.find(i);if(found==group.end()){full=false;break;}const auto& part=*found->second;table.addNewSection(part.raw.data(),part.raw.size(),ts::PID(part.pid),ts::CRC32::CHECK);}
            ts::DuckContext tableDuck(&NULLREP);tableDuck.resetStandards(duck.standards());tableDuck.setDefaultCharsetIn(duck.charsetIn());tableDuck.setDefaultCharsetOut(duck.charsetOut());tableDuck.setTimeReferenceOffset(duck.timeReferenceOffset());
            ts::xml::Document document;auto* parent=document.initialize(u"tsduck");
            if(full&&table.isValid()){
                auto* native=table.toXML(tableDuck,parent);out["native_table_complete"]=true;
                // Guard the same observed private-dual REGID conflicts in the
                // complete PMT tree/XML that are guarded in flat descriptors.
                if(native&&r.tid==ts::TID_PMT&&native->name()==u"PMT"){
                    tableDuck.resetStandards(duck.standards());ts::PMT pmt(tableDuck,table);bool guarded=false;
                    if(pmt.isValid()){
                        guarded=guardPrivateDualLoop(tableDuck,pmt.descs,native,true);
                        for(auto* component=native->firstChildElement();component;component=component->nextSiblingElement())if(component->name()==u"component"){
                            uint16_t pid=ts::PID_NULL;
                            if(component->getIntAttribute(pid,u"elementary_PID")&&pmt.streams.count(pid)){
                                tableDuck.resetStandards(duck.standards());
                                guarded=guardPrivateDualLoop(tableDuck,pmt.streams.at(pid).descs,component,false)||guarded;
                            }
                        }
                    }
                    if(guarded){
                        out["native_xml_guarded"]=true;out["native_xml_guard_reason"]="Observed REGID conflicts with SDK private-dual descriptor resolution";
                        out["native_decode_warnings"]=J::array({"Observed registration id conflicts with SDK descriptor namespace resolution; affected PMT descriptors remain generic bytes."});
                    }
                }
                // In 3.45, DSM-CC DII module tags overlap MPEG descriptor tags.
                // Without DVB evidence the SDK can label module CRC32 tag 0x05
                // as a registration descriptor. Retain the decoded table but
                // render those module descriptors as exact generic bytes until
                // their DVB namespace is explicitly established.
                if(native&&r.tid==ts::TID_DSMCC_UNM&&(duck.standards()&ts::Standards::DVB)==ts::Standards::NONE){
                    ts::DSMCCUserToNetworkMessage message(tableDuck,table);
                    const auto* dii=message.isValid()?message.toDII():nullptr;
                    if(dii){
                        bool hasDescriptors=false;for(const auto& [index,module]:dii->modules)hasDescriptors|=!module.descs.empty();
                        if(hasDescriptors){
                            auto* diiNode=native->findFirstChild(u"DII");ts::xml::ElementVector modules;
                            const bool matching=diiNode&&diiNode->getChildren(modules,u"module")&&modules.size()==dii->modules.size();
                            if(matching){
                                size_t index=0;
                                for(const auto& [key,module]:dii->modules){
                                    auto* element=const_cast<ts::xml::Element*>(modules[index++]);
                                    for(auto* child=element->firstChildElement();child;){auto* next=child->nextSiblingElement();if(child->name()!=u"tap")delete child;child=next;}
                                    ts::DescriptorContext context(tableDuck,ts::TID_DSMCC_UNM,tableDuck.standards());
                                    for(const auto& descriptor:module.descs)descriptor.toXML(tableDuck,element,context,true);
                                }
                            }else{
                                delete native;ts::BinaryTable::XMLOptions options;options.forceGeneric=true;native=table.toXML(tableDuck,parent,options);
                            }
                            out["native_xml_guarded"]=true;out["native_xml_guard_reason"]="DSM-CC module descriptor namespace not established";
                            out["native_decode_warnings"]=J::array({"DSM-CC DII module descriptor namespace is not established; generic bytes retained. Select DVB only when independently known."});
                        }
                    }
                }
                bool namespaceBarrier=false;
                for(const auto& [number,part]:group)for(const auto& d:part->descriptors)
                    namespaceBarrier=namespaceBarrier||d.value("tag",-1)==0x0f||(d.value("tag",-1)==0x5f&&d.value("length",0)!=4);
                if(namespaceBarrier){
                    if(!out.contains("native_decode_warnings"))out["native_decode_warnings"]=J::array();
                    out["native_decode_warnings"].push_back("SDK merged XML is preserved as rendered. Private descriptor names are not validated namespace evidence across PDI or malformed PDS barriers; use the original contextual descriptor results and raw bytes.");
                }
                if(native){out["native_table"]=xmlTree(native);const auto name=native->name();out["native_decode_status"]=(name==u"generic_long_table"||name==u"generic_short_table")?"generic raw fallback":"native TSDuck decoder";}
                out["tsduck_xml"]=document.toString().toUTF8();
            }else{ts::SectionFile file(duck);file.add(std::make_shared<ts::Section>(r.raw.data(),r.raw.size(),ts::PID(r.pid),ts::CRC32::CHECK));out["tsduck_xml"]=file.toXML().toUTF8();out["native_decode_status"]=superseded?"inspected section superseded at selected packet; raw section retained":"incomplete table; raw section retained";}
        }
        const auto& nativeClass=ts::PSIRepository::Instance().getTable(ts::TID(r.tid),ts::SectionContext(ts::PID(r.pid),duck.standards()));
        out["table_decoder_registered"]=!r.j94&&nativeClass.factory!=nullptr;
        out["table_decode_category"]=!r.valid?"invalid_evidence":!out["native_table_complete"].get<bool>()?"incomplete_or_superseded":out["native_decode_status"]=="generic raw fallback"?(!r.j94&&nativeClass.factory?"registered_decoder_fallback":"unknown_or_unsupported"):"decoded";
        if(r.j94)out["assembly_limitation"]="J.94 network/channel maps are not assembled; native_table_complete means this exact CRC-valid section envelope only. No receiver activation, reference resolution or snapshot export.";
        if(r.tid==0x3b||r.tid==0x3c)out["assembly_limitation"]="Native-table assembly is distinct from the bounded same-PID module snapshot in application_signalling; original sections are unchanged";
        J sourceIds=J::array();for(const auto& part:out["native_table_sources"])sourceIds.push_back(part["id"]);
        out["merged"]={{"complete",out["native_table_complete"]},{"source_ids",sourceIds},{"native_table",out["native_table_complete"].get<bool>()?out.value("native_table",J()):J()},{"tsduck_xml",out["native_table_complete"].get<bool>()?out.value("tsduck_xml",J()):J()},{"scope","selected observed table generation; raw_hex, fields and descriptors above belong only to the inspected section"}};
        if(r.j94){out["merged"]["complete"]=false;out["merged"]["scope"]="J.94 native_table is exact section evidence only; use query_cable_oob for bounded descriptor-revised subtables";}
        if(r.tid==0x74||r.tid==0x4b||r.tid==0x3b||r.tid==0x3c){
            std::vector<const Record*> applicationSources,applicationSnapshot;
            for(const auto& [key,part]:latest(cutoff,r.current)){if(r.tid==0x74&&applicationSnapshot.size()<=applicationcarriage::MaxSelected)applicationSnapshot.push_back(part);if(tableGroup(*part)==tableGroup(r))applicationSources.push_back(part);}
            std::sort(applicationSources.begin(),applicationSources.end(),[](auto* a,auto* b){return a->number<b->number;});
            ts::DuckContext applicationDuck(&NULLREP);applicationDuck.resetStandards(duck.standards());applicationDuck.setDefaultCharsetIn(duck.charsetIn());
            const auto windowRecords=coverage.value("partial",false)?segmentRecords(cutoff):std::vector<Record>{};
            applicationsignalling::Builder builder(applicationDuck,applicationSources,revision,cutoff,standardsContext,coverage.value("partial",false)?&windowRecords:&records);
            out["application_signalling"]=builder.build(r,out["native_table_complete"],out["native_decode_status"]);
            if(r.tid==0x74)out["application_signalling"]=applicationcarriage::enrich(std::move(out["application_signalling"]),applicationDuck,r,applicationSnapshot,revision,cutoff,standardsContext);
            if(!out.contains("evidence_anchors"))out["evidence_anchors"]=J::array();
            for(const auto& anchor:out["application_signalling"]["evidence_anchors"])out["evidence_anchors"].push_back(anchor);
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
                    if(valid&&reference.contains("required_pds"))valid=reference["required_pds"].is_number_unsigned()&&reference["required_pds"].get<uint64_t>()<=UINT32_MAX;
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
            if((mask&ts::Standards::DTMB)!=ts::Standards::NONE)families.insert("DTMB");
        }else if(standardsContext.rfind("isdb",0)==0)families.insert("ISDB");
        else if(standardsContext=="dvb")families.insert("DVB");else if(standardsContext=="atsc")families.insert("ATSC");else if(standardsContext=="scte")families.insert("SCTE");else if(standardsContext=="dtmb")families.insert("DTMB");
        if(standardsContext=="j94-system-b")families.insert("J94_SYSTEM_B");
        if(standardsContext=="isdb-japan")families.insert("JAPAN");if(standardsContext=="isdb-brazil")families.insert("ABNT");
        bool privateReferenceWithheld=false;
        auto references=[&](const std::string& name,const char* kind,const J* wireDescriptor){
            J found=J::array();for(const auto& reference:sources){bool context=false;for(const auto& family:reference["standards"])context=context||families.count(family.get<std::string>());const auto& names=reference[kind];if(context&&std::find(names.begin(),names.end(),J(name))!=names.end()){
                // Merged SDK XML may carry a private class name without the
                // original ordered loop context. Never infer that namespace.
                if(reference.contains("required_pds")&&(!wireDescriptor||wireDescriptor->value("pds",J())!=reference["required_pds"]||wireDescriptor->value("decode_status",std::string())!="decoded")){privateReferenceWithheld=true;continue;}
                J compact=J::object();for(const auto* field:{"id","title","url","version","scope","access","notes","standards"})if(reference.contains(field))compact[field]=reference[field];found.push_back(compact);
            }}return found;
        };
        std::function<void(J&,bool,const J*)> annotate=[&](J& node,bool table,const J* wireDescriptor){
            if(!node.is_object())return;node["references"]=references(node.value("name",std::string()),table?"table_names":"descriptor_names",wireDescriptor);
            for(auto& child:node["children"])annotate(child,false,wireDescriptor);
        };
        if(out.contains("native_table")){annotate(out["native_table"],true,nullptr);out["references"]=out["native_table"]["references"];}
        for(auto& descriptor:out["descriptors"]){descriptor["references"]=J::array();if(descriptor.contains("native")){annotate(descriptor["native"],false,&descriptor);descriptor["references"]=descriptor["native"]["references"];}}
        if(privateReferenceWithheld)out["reference_warnings"].push_back("Private-namespace standard links require original descriptor-loop evidence; merged SDK XML names alone are not sufficient. See the original descriptor sources.");
        return out;
    }
    J preview(const J& args) {
        if(!complete)throw std::runtime_error("Complete a successful analysis before editing");
        if(coverage.value("partial",false))throw std::runtime_error("Partial analysis cannot be edited; run a full analysis first");
        pending=J::object();patchSections.clear();std::string id=args.at("id"),name=args.at("name");int sid=args.at("service_id");
        if(!ids.count(id))throw std::runtime_error("Unknown section id");const Record&r=records[ids.at(id)];
        if(!r.valid||r.tid!=0x42||r.number!=0||r.last!=0)throw std::runtime_error("Prototype rename requires a valid complete single-section actual SDT");
        if(name.empty()||name.size()>180)throw std::runtime_error("Service name must contain 1..180 UTF-8 bytes");
        ts::BinaryTable table;table.addNewSection(r.raw.data(),r.raw.size(),ts::PID(r.pid),ts::CRC32::CHECK);ts::SDT sdt(duck,table);
        if(!sdt.isValid()||!sdt.services.count(sid))throw std::runtime_error("Service is absent from target SDT");
        size_t serviceDescriptors=0;for(const auto& descriptor:sdt.services[sid].descs)if(descriptor.tag()==ts::DID_DVB_SERVICE)++serviceDescriptors;
        if(serviceDescriptors>1)throw std::runtime_error("Ambiguous duplicate service descriptors; no preview created");
        const ts::SDT original(duck,table);
        std::string before=sdt.services[sid].serviceName(duck).toUTF8();sdt.services[sid].setName(duck,ts::UString::FromUTF8(name));sdt.incrementVersion();
        ts::BinaryTable changed;if(!sdt.serialize(duck,changed))throw std::runtime_error("TSDuck could not serialize edit");
        // setName() has no failure result: an oversized service_descriptor can
        // disappear, and a regional output charset can silently drop characters.
        // A valid SDT/CRC therefore does not prove that the requested edit survived.
        // Verify the exact bytes that will be exported before publishing any token.
        const ts::SDT verified(duck,changed);
        auto preserved=[](bool ok){if(!ok)throw std::runtime_error("Rename would change unrelated SDT metadata; no preview created");};
        preserved(verified.isValid()&&verified.isActual()==original.isActual()&&verified.ts_id==original.ts_id&&
                  verified.onetw_id==original.onetw_id&&verified.isCurrent()==original.isCurrent()&&
                  verified.version()==sdt.version()&&verified.services.size()==original.services.size());
        for(const auto& [id,old]:original.services){
            const auto found=verified.services.find(id);preserved(found!=verified.services.end());const auto& edited=found->second;
            preserved(edited.EITs_present==old.EITs_present&&edited.EITpf_present==old.EITpf_present&&
                      edited.running_status==old.running_status&&edited.CA_controlled==old.CA_controlled);
            if(id!=sid){preserved(edited.descs==old.descs);continue;}
            size_t target=0;while(target<old.descs.size()&&old.descs[target].tag()!=ts::DID_DVB_SERVICE)++target;
            ts::ServiceDescriptor previous,actual;
            const bool existed=target<old.descs.size();
            if((existed&&!old.locateServiceDescriptor(duck,previous))||
               !edited.locateServiceDescriptor(duck,actual)||actual.service_name.toUTF8()!=name||
               actual.provider_name!=(existed?previous.provider_name:ts::UString())||
               actual.service_type!=(existed?previous.service_type:1))
                throw std::runtime_error("Service name cannot be encoded losslessly within the descriptor capacity for this charset; no preview created");
            preserved(edited.descs.size()==old.descs.size()+(existed?0:1)&&edited.descs[target].tag()==ts::DID_DVB_SERVICE);
            for(size_t i=0;i<old.descs.size();++i)if(i!=target)preserved(edited.descs[i]==old.descs[i]);
        }
        for(size_t i=0;i<changed.sectionCount();i++){auto s=changed.sectionAt(i);patchSections.push_back({r.pid,Bytes(s->content(),s->content()+s->size())});}
        pending={{"token",std::to_string(revision)+":"+id+":"+fingerprint(patchSections.front().second)},{"source_id",id},{"revision",revision},{"service_id",sid},{"before",before},{"after",name},{"old_version",r.version},{"new_version",sdt.version()},{"crc_recomputed",true},{"writes_source",false}};
        return pending;
    }
    J exportData(const J& args) {
        if(std::any_of(records.begin(),records.end(),[](const Record& r){return r.j94;}))throw std::runtime_error("J.94 snapshot export is unsupported until map/version selection is defined; original sections remain inspectable");
        if(!complete||records.empty())throw std::runtime_error("Complete a successful analysis before exporting");
        if(coverage.value("partial",false))throw std::runtime_error("Partial analysis cannot be exported; run a full analysis first");
        const std::string format=args.value("format",std::string("ts"));if(format!="ts"&&format!="bin")throw std::runtime_error("format must be ts or bin");
        fs::path path=fs::absolute(pathFromUtf8(args.at("path").get<std::string>()));
        if(fs::exists(path)||fs::exists(manifestPath(path)))throw std::runtime_error("Output already exists; choose a new path");
        bool patch=args.contains("preview_token");if(patch&&(pending.empty()||args["preview_token"]!=pending["token"]||pending["revision"]!=revision))throw std::runtime_error("Missing or stale edit preview token");
        uint64_t at=args.value("at_packet",UINT64_MAX);const auto selected=latest(at);
        if(patch){
            const auto& target=records.at(ids.at(pending.at("source_id").get<std::string>()));
            for(const auto& [key,r]:selected)if(r->pid==target.pid&&r->tid==target.tid&&r->ext==target.ext&&tableGroup(*r)!=tableGroup(target))
                throw std::runtime_error("Ambiguous SDT edit: multiple network identities share the target PID and transport stream id at this snapshot");
        }
        for(const auto& [key,r]:selected)if((r->tid==0||r->tid==2||r->tid==0x42)&&!completeGroup(*r,selected))throw std::runtime_error("Incomplete PAT/PMT/SDT at selected packet; wait for all sections of one version");
        std::vector<std::pair<unsigned,Bytes>> output;J evidence=J::array();bool applied=false;
        for(const auto& [key,r]:selected){if(patch&&r->id==pending.at("source_id").get<std::string>()){output.insert(output.end(),patchSections.begin(),patchSections.end());applied=true;}else output.push_back({r->pid,r->raw});evidence.push_back(summary(*r,at));}
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
        J receipt={{"path",pathUtf8(path)},{"bytes",fs::file_size(path)},{"format",format},{"section_count",output.size()},{"source",pathUtf8(source)},{"source_revision",revision},{"at_packet",at==UINT64_MAX?J():J(at)},{"selected_sections",evidence},{"edit",patch?pending:J()},{"has_media",false},{"has_pcr",false},{"timing","snapshot repetition; no original packet timing or PCR retained"},{"cycles",format=="ts"?cycles:1},{"null_packets_per_cycle",format=="ts"?nulls:0}};
        J offsets=J::array();size_t offset=0;for(const auto& [pid,b]:output){offsets.push_back({{"pid",pid},{"bin_offset",offset},{"bytes",b.size()},{"fingerprint_fnv1a",fingerprint(b)}});offset+=b.size();}receipt["sections"]=offsets;
        ExportFile manifest(manifestPath(path));const std::string text=receipt.dump(2)+"\n";manifest.write(text.data(),text.size());manifest.close();out.commit();manifest.commit();return receipt;
    }
    J dispatch(const std::string& method,const J& args,const J& rid,const std::shared_ptr<AnalysisControl>& control=nullptr) {
        // runCore validates against its immutable startup catalog before queueing.
        // Re-reading mutable schemas here could invalidate an accepted analysis.
        if(method=="capabilities"){
            J result=readJson(root/"api/tools.json");ts::UStringList tables,descriptors;
            const std::string runtime=sdkVersion(tsduckLibraryVersionMajor,tsduckLibraryVersionMinor,tsduckLibraryVersionCommit);
            result["engine"]="C++ / TSDuck "+runtime;
            result["native_sdk"]={{"headers",TS_VERSION_STRING},{"tsduck_runtime",runtime},{"tscore_runtime",sdkVersion(tscoreLibraryVersionMajor,tscoreLibraryVersionMinor,tscoreLibraryVersionCommit)},{"version_symbols_enforced",true},{"cpp_standard",20}};
            ts::PSIRepository::Instance().getRegisteredTableNames(tables);ts::PSIRepository::Instance().getRegisteredDescriptorNames(descriptors);
            J registry={{"table_names",J::array()},{"descriptor_names",J::array()},{"table_count",tables.size()},{"descriptor_count",descriptors.size()},{"note","Registered XML names (including aliases), not a guarantee that every payload or regional variant is supported. Explicit standards context resolves ambiguous identifiers."}};
            for(const auto& name:tables)registry["table_names"].push_back(name.toUTF8());for(const auto& name:descriptors)registry["descriptor_names"].push_back(name.toUTF8());result["native_registry"]=registry;return result;
        }
        if(method=="lookup_satellite")return satellitemeta::lookup(root,args);
        if(method=="lookup_identifier"){
            const auto& value=args.at("value");
            if(!value.is_number_integer()||value<0||value>UINT32_MAX)throw std::runtime_error("Identifier value must be an integer in 0..4294967295");
            const auto standard=args.value("standards",std::string("auto"));
            if(std::set<std::string>{"auto","dvb","atsc","isdb","isdb-japan","isdb-brazil","scte","dtmb"}.count(standard)==0)throw std::runtime_error("Unknown standards context");
            return signalmeta::lookup(args.at("namespace"),value,standard);
        }
        if(method=="import_dvbi"){
            const auto path=args.at("path").get<std::string>();
            dvbi::validateLocalPath(path);
            return dvbiDocuments.importDocument(args,pathFromUtf8(path));
        }
        if(method=="query_dvbi")return dvbiDocuments.query(args);
        if(method=="inspect_dvbi")return dvbiDocuments.inspect(args);
        if(method=="analyze")return analyze(args,rid,control);
        if(method=="query")return args.value("response_mode",std::string("legacy"))=="compact"?compactState(args.value("at_packet",UINT64_MAX)):state(args.value("at_packet",UINT64_MAX));
        if(method=="query_result")return queryResult(args);
        if(method=="query_transport")return queryTransport(args);
        if(method=="query_cable_oob")return queryCableOob(args);
        if(method=="query_topology")return queryTopology(args);
        if(method=="diff_snapshots")return diffSnapshots(args);
        if(method=="inspect")return inspect(args);
        if(method=="preview_rename")return preview(args);
        if(method=="export")return exportData(args);
        if(method=="load_extension") {
            J candidate=readJson(pathFromUtf8(args.at("path").get<std::string>()));
            auto require=[](bool ok,const std::string& message){if(!ok)throw std::runtime_error("Invalid extension: "+message);};
            auto integer=[](const J& value,uint64_t max){return value.is_number_integer()&&value>=0&&value<=max;};
            require(candidate.is_object()&&candidate.contains("id")&&candidate["id"].is_string()&&!candidate["id"].get<std::string>().empty(),"nonempty string id required");
            require(candidate.contains("descriptors")&&candidate["descriptors"].is_array(),"descriptors must be an array");
            std::set<std::tuple<uint64_t,unsigned,unsigned>> descriptorScopes;
            const std::set<std::string> reservedFields={"id","key","source_id","ts_id","onid","encrypted","service_id","pmt_pid","components","name","provider","type","title","text","start","duration_seconds","service_type","service_type_name","audio_pids","video_pids","media_status","name_from_descriptor","lcn_status","lcn_candidates","lcn_list_candidates","lcn_list_status","lcn_scope","language_variants","default_language","language_selection","identifier_lookups","text_diagnostics"};
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

#ifdef _WIN32
// Installer/uninstaller AppMutex uses the same name as the Qt process. The
// non-owned handle allows multiple workbenches, but blocks replacing shared
// runtime/resources while any core (including standalone JSONL/MCP) is alive.
class ApplicationLifetimeMutex {
    HANDLE handle;
public:
    ApplicationLifetimeMutex():handle(CreateMutexW(nullptr,FALSE,L"Local\\ShowPsiSi.ApplicationLifetime")) {
        if(!handle)throw std::runtime_error("Cannot create the application lifetime mutex; refusing unprotected startup (Windows error "+std::to_string(GetLastError())+")");
    }
    ApplicationLifetimeMutex(const ApplicationLifetimeMutex&)=delete;
    ApplicationLifetimeMutex& operator=(const ApplicationLifetimeMutex&)=delete;
    ~ApplicationLifetimeMutex(){CloseHandle(handle);}
};
#endif

static int runCore(int argc,char**argv) {
    std::cin.tie(nullptr);
    fs::path root=fs::current_path();for(int i=1;i+1<argc;i++)if(std::string(argv[i])=="--root")root=pathFromUtf8(argv[++i]);
    try {
#ifdef _WIN32
        const ApplicationLifetimeMutex applicationLifetime;
#endif
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
                    if(method=="cancel_analysis"||method=="pause_analysis"||method=="resume_analysis"){
                        const J target=args.at("request_id");std::shared_ptr<AnalysisControl> control;
                        {std::lock_guard<std::mutex> lock(mutex);auto found=analyses.find(target.dump());if(found!=analyses.end())control=found->second;}
                        const bool requested=control&&(method=="cancel_analysis"?control->requestCancellation():control->requestPause(method=="pause_analysis"));
                        J result={{"request_id",target},{"requested",requested}};
                        if(!requested)result["reason"]="not_running";
                        emit({{"id",id},{"result",result}});continue;
                    }
                    if(method=="query"||method=="query_result"||method=="query_transport"||method=="inspect"||method=="query_topology"||method=="query_cable_oob"||method=="diff_snapshots"){
                        bool paused=false;{std::lock_guard<std::mutex> lock(mutex);for(const auto& [key,control]:analyses)paused|=control->paused.load();}
                        if(paused){emit({{"id",id},{"error",{{"code","analysis_paused"},{"message","Analysis is paused; resume or cancel it before detailed inspection. Progress remains available."}}}});continue;}
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
            {std::lock_guard<std::mutex> lock(mutex);inputEnded=true;for(auto& [key,control]:analyses)control->requestPause(false);}
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
            } catch(const RejectedInput& e){
                terminal={{"id",work.id},{"error",{{"code","input_rejected"},{"message",e.what()},{"data",{{"state_preserved",true}}}}}};
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
#ifdef _WIN32
// Windows gives wmain lossless UTF-16 arguments; narrow main depends on the
// active code page and can corrupt a non-ASCII --root before parsing begins.
static int runWide(int argc,wchar_t** argv,int (*run)(int,char**)) {
    std::vector<std::string> utf8;utf8.reserve(argc);
    for(int i=0;i<argc;++i)utf8.push_back(pathUtf8(fs::path(argv[i])));
    std::vector<char*> args;args.reserve(argc+1);
    for(auto& arg:utf8)args.push_back(arg.data());args.push_back(nullptr);
    return run(argc,args.data());
}
#endif
#ifndef SHOWPSISI_TESTING
#ifdef _WIN32
int wmain(int argc,wchar_t** argv) { return runWide(argc,argv,runCore); }
#else
int main(int argc,char**argv) { return runCore(argc,argv); }
#endif
#endif
