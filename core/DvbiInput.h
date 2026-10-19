#pragma once
// Local, read-only DVB-I metadata adapter. Original bytes never become TS evidence.
// Published baseline: ETSI TS 103 770 V1.2.1 (2024-09), clauses 5.4--5.6.
#include <expat_config.h>
#include <expat.h>
#include <tsSHA256.h>
#include <nlohmann/json.hpp>
#include <chrono>
#include <filesystem>
#include <map>
#include <memory>
#include <set>
#include <string>
#include <vector>
#include <limits>
#include <cstring>
#include <charconv>
#ifdef _WIN32
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace dvbi {
using Json=nlohmann::json;
namespace fs=std::filesystem;
using Clock=std::chrono::steady_clock;
inline constexpr size_t MaxBytes=4*1024*1024, MaxText=2*1024*1024, MaxNodes=20000, MaxDepth=48, MaxPaths=8*1024*1024;
inline constexpr char Namespace[]="urn:dvb:metadata:servicediscovery:2024";
inline constexpr char TypesNamespace[]="urn:dvb:metadata:servicediscovery-types:2023";
inline constexpr char XmlNamespace[]="http://www.w3.org/XML/1998/namespace";
inline constexpr char Profile[]="etsi-ts-103770-v1.2.1";
inline std::string hex(const std::string& value) { static const char* d="0123456789abcdef";std::string s;s.reserve(value.size()*2);for(unsigned char c:value){s+=d[c>>4];s+=d[c&15];}return s; }
inline std::string digest(const std::string& value) {ts::SHA256 sha;ts::ByteBlock b;if(!sha.hash(value.data(),value.size(),b))throw std::runtime_error("DVB-I SHA-256 calculation failed");return hex(std::string(reinterpret_cast<const char*>(b.data()),b.size()));}
inline void validateLocalPath(const std::string& path) {
    if(path.empty()||path.find('\0')!=std::string::npos)throw std::runtime_error("DVB-I input path is empty or contains NUL");
    // Reject UNC and Win32 device/extended namespace before any OS open. This
    // check is portable so malformed input has the same failure on each host.
    if(path.size()>=2&&(path[0]=='/'||path[0]=='\\')&&(path[1]=='/'||path[1]=='\\'))throw std::runtime_error("DVB-I requires a local path; UNC and device paths are unsupported");
}
inline std::string utf8Path(const fs::path& path){const auto s=path.u8string();return std::string(reinterpret_cast<const char*>(s.data()),s.size());}
inline void deadline(Clock::time_point start){if(Clock::now()-start>std::chrono::seconds(2))throw std::runtime_error("DVB-I import deadline exceeded (2 seconds)");}
// Open first, then verify the actual handle. O_NONBLOCK avoids FIFO replacement
// races; reparse points are refused on Windows. No URL or network resolver exists.
inline std::string readLocal(const fs::path& path,Clock::time_point start) {
    validateLocalPath(utf8Path(fs::absolute(path)));
    std::string result;char buffer[16384];
#ifdef _WIN32
    const auto absolute=fs::absolute(path);
    const auto drive=absolute.root_path().wstring();
    if(GetDriveTypeW(drive.c_str())==DRIVE_REMOTE)throw std::runtime_error("DVB-I remote drives are unsupported");
    for(const auto& part:absolute){
        std::wstring name=part.wstring();
        // Only the drive-root colon is allowed; reject DOS aliases and ADS.
        if(part!=absolute.root_name()&&name.find(L':')!=std::wstring::npos)throw std::runtime_error("DVB-I device or alternate-stream paths are unsupported");
        for(auto& c:name)if(c>=L'a'&&c<=L'z')c-=32;
        name=name.substr(0,name.find(L'.'));
        while(!name.empty()&&name.back()==L' ')name.pop_back();
        const bool serial=name.size()==4&&(name.rfind(L"COM",0)==0||name.rfind(L"LPT",0)==0)&&((name[3]>=L'1'&&name[3]<=L'9')||name[3]==0xB9||name[3]==0xB2||name[3]==0xB3);
        if(serial||name==L"CON"||name==L"CONIN$"||name==L"CONOUT$"||name==L"PRN"||name==L"AUX"||name==L"NUL")throw std::runtime_error("DVB-I device paths are unsupported");
    }
    HANDLE fd=CreateFileW(path.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_FLAG_OPEN_REPARSE_POINT|FILE_FLAG_SEQUENTIAL_SCAN,nullptr);
    if(fd==INVALID_HANDLE_VALUE)throw std::runtime_error("Cannot open DVB-I local regular file");
    struct Guard{HANDLE fd;~Guard(){CloseHandle(fd);}} guard{fd};
    BY_HANDLE_FILE_INFORMATION info{};LARGE_INTEGER size{};
    if(GetFileType(fd)!=FILE_TYPE_DISK||!GetFileInformationByHandle(fd,&info)||(info.dwFileAttributes&(FILE_ATTRIBUTE_DIRECTORY|FILE_ATTRIBUTE_REPARSE_POINT))||!GetFileSizeEx(fd,&size))throw std::runtime_error("DVB-I input must be a regular file, not a directory or reparse point");
    if(size.QuadPart<0||uint64_t(size.QuadPart)>MaxBytes)throw std::runtime_error("DVB-I input exceeds 4 MiB byte limit");
    for(;;){deadline(start);DWORD count=0;if(!ReadFile(fd,buffer,sizeof(buffer),&count,nullptr))throw std::runtime_error("DVB-I local file read failed");if(!count)break;if(result.size()+count>MaxBytes)throw std::runtime_error("DVB-I input exceeds 4 MiB byte limit");result.append(buffer,count);}
#else
    int fd=open(path.c_str(),O_RDONLY|O_CLOEXEC|O_NONBLOCK|O_NOFOLLOW);
    if(fd<0)throw std::runtime_error("Cannot open DVB-I local regular file");
    struct Guard{int fd;~Guard(){close(fd);}} guard{fd};struct stat info{};
    if(fstat(fd,&info)!=0||!S_ISREG(info.st_mode))throw std::runtime_error("DVB-I input must be a regular file");
    if(info.st_size<0||uint64_t(info.st_size)>MaxBytes)throw std::runtime_error("DVB-I input exceeds 4 MiB byte limit");
    for(;;){deadline(start);ssize_t count=read(fd,buffer,sizeof(buffer));if(count<0)throw std::runtime_error("DVB-I local file read failed");if(!count)break;if(result.size()+size_t(count)>MaxBytes)throw std::runtime_error("DVB-I input exceeds 4 MiB byte limit");result.append(buffer,size_t(count));}
#endif
    deadline(start);if(result.empty())throw std::runtime_error("DVB-I XML input is empty");return result;
}
struct Name {
    std::string ns,local,qualified;
    explicit Name(const char* raw="") {std::string s(raw);auto a=s.find('\x1f');if(a==std::string::npos){local=qualified=s;return;}ns=s.substr(0,a);auto b=s.find('\x1f',a+1);local=s.substr(a+1,b==std::string::npos?b:b-a-1);qualified=b==std::string::npos?local:s.substr(b+1)+":"+local;}
    std::string expanded() const{return "Q{"+ns+"}"+local;}
};
struct Attribute {Name name;std::string value;};
struct Element {Name name;std::string path,text,language;size_t parent=SIZE_MAX;uint64_t line=0,column=0,originalByteOffset=0;std::vector<Attribute> attributes;std::vector<size_t> children;std::map<std::string,size_t> siblingCounts;};
struct Document {
    uint64_t revision=0;std::string original,sourcePath,sha256;std::vector<Element> elements;Json nodes=Json::array(),diagnostics=Json::array();bool supported=false;size_t omittedDiagnostics=0;
    Json evidence(size_t index,const std::string& attr="") const {const auto& e=elements.at(index);Json j={{"document_revision",revision},{"source_sha256",sha256},{"element_id","e"+std::to_string(index)},{"path",e.path+(attr.empty()?"":"/@"+attr)},{"precision",attr.empty()?"element":"attribute"},{"line",e.line},{"column",e.column},{"line_precision","element_start"},{"original_byte_offset",e.originalByteOffset},{"byte_offset_precision","element_start"}};if(!attr.empty())j["attribute_name"]=attr;return j;}
    void diagnostic(const std::string& code,const std::string& message,size_t index=0){if(diagnostics.size()<100)diagnostics.push_back({{"code",code},{"message",message},{"evidence",evidence(index)}});else omittedDiagnostics++;}
    Json metadata() const {return {{"schema_version",1},{"document_revision",revision},{"source",{{"kind","local_dvbi_xml"},{"path",sourcePath},{"sha256",sha256},{"bytes",original.size()},{"encoding","UTF-8"}}},{"profile",Profile},{"parser",{{"name","Expat"},{"version",XML_ExpatVersion()},{"static_link",true}}},{"namespace",elements.empty()?"":elements[0].name.ns},{"status",supported?"partial":"unsupported"},{"diagnostics",diagnostics},{"diagnostics_omitted",omittedDiagnostics},{"counts",{{"nodes",nodes.size()},{"elements",elements.size()}}},{"coverage",{{"schema_validation",false},{"network_fetch",false},{"media_reception",false},{"ts_association",false},{"async_cancel",false},{"scope","Local UTF-8 service-list identity, alternatives and LCN projection; remaining XML retained without semantic interpretation."}}}};}
};
class Parser {
    XML_Parser parser=nullptr;Document& doc;std::vector<size_t> stack;Clock::time_point start;const char* failure=nullptr;size_t textBytes=0,pathBytes=0;
    void stop(const char* reason) noexcept {if(!failure)failure=reason;XML_StopParser(parser,XML_FALSE);}
    bool check() noexcept {if(failure)return false;if(Clock::now()-start>std::chrono::seconds(2)){stop("DVB-I import deadline exceeded (2 seconds)");return false;}return true;}
    template<class F> void callback(F f) noexcept {if(!check())return;try{f();}catch(...){stop("DVB-I XML resource allocation failed");}}
    static void XMLCALL begin(void* user,const char* raw,const char** attrs) noexcept {auto& p=*static_cast<Parser*>(user);p.callback([&]{
        if(p.stack.size()>=MaxDepth){p.stop("DVB-I XML depth limit exceeded (48)");return;}
        if(p.doc.elements.size()>=MaxNodes){p.stop("DVB-I XML element limit exceeded (20000)");return;}
        if(std::strlen(raw)>1024){p.stop("DVB-I XML name limit exceeded");return;}
        Element e;e.name=Name(raw);e.parent=p.stack.empty()?SIZE_MAX:p.stack.back();e.line=XML_GetCurrentLineNumber64(p.parser);e.column=XML_GetCurrentColumnNumber64(p.parser)+1;
        const auto byte=XML_GetCurrentByteIndex64(p.parser);
        if(byte<0||uint64_t(byte)>=p.doc.original.size()||p.doc.original[size_t(byte)]!='<'){p.stop("DVB-I XML element source offset unavailable");return;}e.originalByteOffset=uint64_t(byte);
        size_t occurrence=1;if(e.parent!=SIZE_MAX){auto& parent=p.doc.elements[e.parent];occurrence=++parent.siblingCounts[e.name.expanded()];e.path=parent.path;e.language=parent.language;}
        e.path+="/"+e.name.expanded()+"["+std::to_string(occurrence)+"]";p.pathBytes+=e.path.size();if(p.pathBytes>MaxPaths){p.stop("DVB-I XML cumulative path limit exceeded");return;}
        for(size_t i=0;attrs[i];i+=2){if(i>=128||std::strlen(attrs[i])>1024||std::strlen(attrs[i+1])>65536){p.stop("DVB-I XML attribute limit exceeded");return;}e.attributes.push_back({Name(attrs[i]),attrs[i+1]});const auto& a=e.attributes.back();if(a.name.ns==XmlNamespace&&a.name.local=="lang")e.language=a.value;}
        size_t n=p.doc.elements.size();p.doc.elements.push_back(std::move(e));if(!p.stack.empty())p.doc.elements[p.stack.back()].children.push_back(n);p.stack.push_back(n);
    });}
    static void XMLCALL end(void* user,const char*) noexcept {auto& p=*static_cast<Parser*>(user);p.callback([&]{if(!p.stack.empty())p.stack.pop_back();});}
    static void XMLCALL text(void* user,const char* data,int count) noexcept {auto& p=*static_cast<Parser*>(user);p.callback([&]{p.textBytes+=size_t(count);if(p.textBytes>MaxText){p.stop("DVB-I XML text limit exceeded (2 MiB)");return;}if(!p.stack.empty()){auto& s=p.doc.elements[p.stack.back()].text;if(s.size()+size_t(count)>65536){p.stop("DVB-I XML element text limit exceeded (64 KiB)");return;}s.append(data,size_t(count));}});}
    static void XMLCALL doctype(void* user,const char*,const char*,const char*,int) noexcept {static_cast<Parser*>(user)->stop("DVB-I XML DTD and entities are forbidden");}
    static int XMLCALL external(XML_Parser parser,const char*,const char*,const char*,const char*) noexcept {static_cast<Parser*>(XML_GetUserData(parser))->stop("DVB-I XML external entities are forbidden");return XML_STATUS_ERROR;}
    static void XMLCALL declaration(void* user,const char* version,const char* encoding,int) noexcept {auto& p=*static_cast<Parser*>(user);p.callback([&]{if(version&&std::strcmp(version,"1.0")){p.stop("DVB-I supports XML 1.0 only");return;}if(encoding){std::string e(encoding);for(auto& c:e)if(c>='a'&&c<='z')c-=32;if(e!="UTF-8")p.stop("DVB-I unsupported encoding: UTF-8 is required");}});}
public:
    Parser(Document& d,Clock::time_point s):doc(d),start(s){parser=XML_ParserCreateNS("UTF-8",'\x1f');if(!parser)throw std::runtime_error("Cannot allocate DVB-I XML parser");XML_SetUserData(parser,this);XML_SetReturnNSTriplet(parser,1);XML_SetElementHandler(parser,begin,end);XML_SetCharacterDataHandler(parser,text);XML_SetStartDoctypeDeclHandler(parser,doctype);XML_SetExternalEntityRefHandler(parser,external);XML_SetXmlDeclHandler(parser,declaration);if(!XML_SetParamEntityParsing(parser,XML_PARAM_ENTITY_PARSING_NEVER)||!XML_SetReparseDeferralEnabled(parser,XML_TRUE)||!XML_SetBillionLaughsAttackProtectionMaximumAmplification(parser,2.0f)||!XML_SetBillionLaughsAttackProtectionActivationThreshold(parser,1024)||!XML_SetAllocTrackerMaximumAmplification(parser,16.0f)||!XML_SetAllocTrackerActivationThreshold(parser,1024*1024)){XML_ParserFree(parser);parser=nullptr;throw std::runtime_error("DVB-I XML hardening setup failed");}}
    Parser(const Parser&)=delete;Parser& operator=(const Parser&)=delete;
    ~Parser(){XML_ParserFree(parser);}
    void parse(){if(doc.original.find('\0')!=std::string::npos)throw std::runtime_error("DVB-I unsupported encoding or NUL: UTF-8 XML is required");for(size_t offset=0;offset<doc.original.size();offset+=16384){deadline(start);size_t n=std::min<size_t>(16384,doc.original.size()-offset);auto result=XML_Parse(parser,doc.original.data()+offset,int(n),offset+n==doc.original.size());if(result!=XML_STATUS_OK)throw std::runtime_error(failure?failure:std::string("Invalid DVB-I XML: ")+XML_ErrorString(XML_GetErrorCode(parser))+" at line "+std::to_string(XML_GetCurrentLineNumber64(parser)));}deadline(start);if(doc.elements.empty())throw std::runtime_error("DVB-I XML has no root element");}
};
inline const Attribute* attribute(const Element& e,const std::string& local,const std::string& ns="") {for(const auto& a:e.attributes)if(a.name.local==local&&a.name.ns==ns)return &a;return nullptr;}
inline std::string trim(const std::string& s){size_t a=s.find_first_not_of(" \t\r\n");if(a==std::string::npos)return {};return s.substr(a,s.find_last_not_of(" \t\r\n")-a+1);}
inline std::vector<size_t> children(const Document& d,size_t parent,const std::string& local,const std::string& ns=Namespace){std::vector<size_t> out;for(size_t i:d.elements[parent].children)if(d.elements[i].name.ns==ns&&d.elements[i].name.local==local)out.push_back(i);return out;}
inline Json rawAttributes(const Element& e){Json j=Json::array();for(const auto& a:e.attributes)j.push_back({{"namespace",a.name.ns},{"local_name",a.name.local},{"qualified_name",a.name.qualified},{"value",a.value}});return j;}
inline Json names(const Document& d,size_t parent,const std::string& local){Json j=Json::array();for(size_t i:children(d,parent,local))j.push_back({{"text",d.elements[i].text},{"language",d.elements[i].language},{"evidence",d.evidence(i)}});return j;}
class Projection {
    Document& d;Clock::time_point start;std::map<std::string,std::vector<size_t>> identifiers,serviceRefs;
    Json& add(size_t e,const std::string& type,const std::string& parent,const Json& identity,const std::string& key,const std::string& fallback){deadline(start);std::string stable="dvbi:"+type+":"+digest(key);auto& group=identifiers[stable];std::string id=stable+":"+std::to_string(group.size());group.push_back(d.nodes.size());d.nodes.push_back({{"node_id",id},{"parent_id",parent.empty()?Json():Json(parent)},{"object_type",type},{"identity",identity},{"label",fallback},{"attributes",{{"xml_attributes",rawAttributes(d.elements[e])}}},{"observation_status","announced_only"},{"resolution_status","resolved"},{"evidence",Json::array({d.evidence(e)})},{"unresolved_reasons",Json::array()}});return d.nodes.back();}
    void issue(Json& node,const std::string& reason,size_t e,const std::string& status="incomplete"){node["resolution_status"]=status;node["unresolved_reasons"].push_back(reason);d.diagnostic(status,reason,e);}
    void numeric(Json& node,size_t e,const std::string& attr,const std::string& key,uint64_t max=UINT64_MAX,bool positive=false,bool required=false){auto* a=attribute(d.elements[e],attr);if(!a){if(required)issue(node,"Missing "+attr,e);return;}std::string v=trim(a->value);if(!v.empty()&&v[0]=='+')v.erase(v.begin());uint64_t n=0;auto p=std::from_chars(v.data(),v.data()+v.size(),n);if(v.empty()||p.ec!=std::errc()||p.ptr!=v.data()+v.size()||n>max||(positive&&n==0)){node["attributes"][key]=nullptr;issue(node,"Invalid "+attr+" integer",e);return;}node["attributes"][key]=n;node["evidence"].push_back(d.evidence(e,a->name.expanded()));}
    void baseNames(Json& node,size_t e,const std::string& name){node["attributes"]["names"]=names(d,e,name);node["attributes"]["providers"]=names(d,e,"ProviderName");if(!node["attributes"]["names"].empty())node["label"]=node["attributes"]["names"][0]["text"];for(auto k:{"names","providers"})for(const auto& n:node["attributes"][k])node["evidence"].push_back(n["evidence"]);}
    void regions(Json& node,size_t e){node["attributes"]["target_regions"]=Json::array();for(auto c:children(d,e,"TargetRegion")){node["attributes"]["target_regions"].push_back({{"region_ref",trim(d.elements[c].text)},{"evidence",d.evidence(c)}});node["evidence"].push_back(d.evidence(c));}}
    void unknown(Json& node,size_t e,const std::set<std::string>& known){node["attributes"]["uninterpreted_elements"]=Json::array();for(size_t c:d.elements[e].children){const auto& child=d.elements[c];if(child.name.ns!=Namespace||!known.count(child.name.local))node["attributes"]["uninterpreted_elements"].push_back({{"namespace",child.name.ns},{"local_name",child.name.local},{"evidence",d.evidence(c)}});}}
    void boolean(Json& node,size_t e,const std::string& key,bool fallback){const auto* a=attribute(d.elements[e],key);node["attributes"][key+"_origin"]=a?"declared":"schema_default";if(!a){node["attributes"][key]=fallback;return;}auto v=trim(a->value);if(v=="true"||v=="1")node["attributes"][key]=true;else if(v=="false"||v=="0")node["attributes"][key]=false;else{node["attributes"][key]=nullptr;issue(node,"Invalid "+key+" boolean",e);}node["evidence"].push_back(d.evidence(e,a->name.expanded()));}
    void region(size_t e,const std::string& parent,const std::string& list){const auto* a=attribute(d.elements[e],"regionID");const std::string id=a?a->value:"";auto& node=add(e,"region",parent,{{"region_id",id.empty()?Json():Json(id)}},list+"\n"+(id.empty()?d.elements[e].path:id),id.empty()?"Unidentified region":id);const std::string nodeId=node["node_id"];baseNames(node,e,"RegionName");if(id.empty())issue(node,"Missing regionID",e);unknown(node,e,{"RegionName","Region"});for(auto c:children(d,e,"Region"))region(c,nodeId,list);}
    void instance(size_t e,const std::string& parent){const auto* a=attribute(d.elements[e],"id");std::string id=a?a->value:"0";Json& node=add(e,"service_instance",parent,{{"instance_id",id},{"id_origin",a?"declared":"schema_default"}},parent+"\n"+id,"Instance "+id);std::string nodeId=node["node_id"];baseNames(node,e,"DisplayName");numeric(node,e,"priority","priority");if(!attribute(d.elements[e],"priority")){node["attributes"]["priority"]=0;node["attributes"]["priority_origin"]="schema_default";}else node["attributes"]["priority_origin"]="declared";node["attributes"]["delivery_parameters"]=Json::array();
        const std::set<std::string> delivery={"DVBTDeliveryParameters","DVBSDeliveryParameters","DVBCDeliveryParameters","DASHDeliveryParameters","RTSPDeliveryParameters","MulticastTSDeliveryParameters","SATIPDeliveryParameters","IdentifierBasedDeliveryParameters","OtherDeliveryParameters"};
        for(size_t c:d.elements[e].children)if(d.elements[c].name.ns==Namespace&&delivery.count(d.elements[c].name.local)){
            Json value={{"type",d.elements[c].name.local},{"evidence",d.evidence(c)},{"reception_status","unverified"},{"interpretation_status","raw_only"}};
            auto triplets=children(d,c,"DVBTriplet");if(!triplets.empty()){value["broadcast_triplets"]=Json::array();for(auto t:triplets){Json triplet={{"evidence",d.evidence(t)},{"association_status","not_joined"}};for(auto field:{"origNetId","tsId","serviceId"}){auto* v=attribute(d.elements[t],field);if(!v){triplet[field]=nullptr;if(std::string(field)=="serviceId")issue(node,"Missing DVBTriplet serviceId",t);continue;}std::string raw=trim(v->value);if(!raw.empty()&&raw[0]=='+')raw.erase(raw.begin());uint64_t number=0;auto p=std::from_chars(raw.data(),raw.data()+raw.size(),number);if(raw.empty()||p.ec!=std::errc()||p.ptr!=raw.data()+raw.size()||number>65535){triplet[field]=nullptr;issue(node,"Invalid DVBTriplet "+std::string(field),t);}else triplet[field]=number;triplet[std::string(field)+"_raw"]=v->value;}value["broadcast_triplets"].push_back(triplet);}}
            if(d.elements[c].name.local=="DASHDeliveryParameters"){value["uris"]=Json::array();for(auto location:children(d,c,"UriBasedLocation"))for(auto uri:children(d,location,"URI",TypesNamespace))value["uris"].push_back({{"value",d.elements[uri].text},{"evidence",d.evidence(uri)},{"fetch_status","not_fetched"}});}
            node["attributes"]["delivery_parameters"].push_back(value);node["evidence"].push_back(d.evidence(c));
        }
        unknown(node,e,{"DisplayName","DVBTDeliveryParameters","DVBSDeliveryParameters","DVBCDeliveryParameters","DASHDeliveryParameters"});
        if(node["attributes"]["delivery_parameters"].empty())issue(node,"No supported delivery declaration; XML retained",e,"unresolved");
    }
public:
    Projection(Document& value,Clock::time_point clock):d(value),start(clock){}
    void run(){d.supported=d.elements[0].name.ns==Namespace&&d.elements[0].name.local=="ServiceList";if(!d.supported){d.diagnostic("unsupported_namespace_or_root","No semantic projection for this exact namespace/root; original XML remains inspectable.");return;}
        const auto* rid=attribute(d.elements[0],"id");std::string listId=rid?rid->value:"";auto& root=add(0,"service_list","",{{"list_id",listId.empty()?Json():Json(listId)}},listId.empty()?d.elements[0].path:listId,"Service list");std::string parent=root["node_id"];baseNames(root,0,"Name");regions(root,0);numeric(root,0,"version","version",UINT64_MAX,true,true);if(listId.empty())issue(root,"Missing service-list id",0);if(children(d,0,"Name").empty())issue(root,"Missing service-list Name",0);if(children(d,0,"ProviderName").empty())issue(root,"Missing service-list ProviderName",0);if(d.elements[0].language.empty())issue(root,"Missing service-list xml:lang",0);unknown(root,0,{"Name","ProviderName","Service","TestService","LCNTableList","RegionList","TargetRegion"});
        for(size_t e:d.elements[0].children)if(d.elements[e].name.ns==Namespace&&(d.elements[e].name.local=="Service"||d.elements[e].name.local=="TestService")){
            auto ids=children(d,e,"UniqueIdentifier");std::string id=ids.size()!=1?"":trim(d.elements[ids[0]].text);auto& node=add(e,"service",parent,{{"list_id",listId},{"service_id",id.empty()?Json():Json(id)}},parent+"\n"+(id.empty()?d.elements[e].path:id),id.empty()?"Unidentified service":id);std::string serviceNode=node["node_id"];size_t nodeIndex=d.nodes.size()-1;if(!id.empty())serviceRefs[id].push_back(nodeIndex);node["attributes"]["identity_candidates"]=Json::array();for(auto candidate:ids)node["attributes"]["identity_candidates"].push_back({{"value",trim(d.elements[candidate].text)},{"evidence",d.evidence(candidate)}});baseNames(node,e,"ServiceName");regions(node,e);numeric(node,e,"version","version",UINT64_MAX,true,true);node["attributes"]["test_service"]=d.elements[e].name.local=="TestService";if(ids.size()!=1||id.empty())issue(node,"Exactly one nonempty UniqueIdentifier is required",e,ids.size()>1?"conflict":"incomplete");for(auto candidate:ids)node["evidence"].push_back(d.evidence(candidate));unknown(node,e,{"UniqueIdentifier","ServiceName","ProviderName","ServiceInstance","TargetRegion"});for(auto c:children(d,e,"ServiceInstance"))instance(c,serviceNode);
        }
        for(auto regionList:children(d,0,"RegionList"))for(auto r:children(d,regionList,"Region"))region(r,parent,parent);
        for(auto container:children(d,0,"LCNTableList"))for(auto e:children(d,container,"LCNTable")){
            auto& table=add(e,"lcn_table",parent,{{"document_path",d.elements[e].path}},parent+"\n"+d.elements[e].path,"LCN table");std::string tableId=table["node_id"];regions(table,e);boolean(table,e,"preserveBroadcastLCN",false);unknown(table,e,{"TargetRegion","LCN"});std::map<std::string,std::vector<size_t>> channels;
            for(auto c:children(d,e,"LCN")){auto* ref=attribute(d.elements[c],"serviceRef");auto* num=attribute(d.elements[c],"channelNumber");std::string service=ref?trim(ref->value):"";auto& node=add(c,"lcn_assignment",tableId,{{"service_ref",service.empty()?Json():Json(service)},{"channel_number_raw",num?Json(num->value):Json()}},tableId+"\n"+d.elements[c].path,"LCN "+(num?num->value:"?"));numeric(node,c,"channelNumber","channel_number",UINT64_MAX,true,true);boolean(node,c,"visible",true);boolean(node,c,"selectable",true);node["attributes"]["service_nodes"]=Json::array();auto found=serviceRefs.find(service);if(service.empty()||found==serviceRefs.end())issue(node,"Unresolved serviceRef",c,"unresolved");else{for(auto n:found->second)node["attributes"]["service_nodes"].push_back(d.nodes[n]["node_id"]);if(found->second.size()!=1)issue(node,"Ambiguous serviceRef",c,"conflict");}if(node["attributes"].contains("channel_number")&&!node["attributes"]["channel_number"].is_null())channels[node["attributes"]["channel_number"].dump()].push_back(d.nodes.size()-1);}
            for(const auto& [number,indices]:channels)if(indices.size()>1)for(auto i:indices){d.nodes[i]["resolution_status"]="conflict";d.nodes[i]["unresolved_reasons"].push_back("Multiple assignments for one channel number in the same LCN table");}
        }
        // Duplicate declarations remain separate. Never choose by display name.
        for(const auto& [key,indices]:identifiers)if(indices.size()>1)for(size_t i:indices){d.nodes[i]["resolution_status"]="conflict";d.nodes[i]["unresolved_reasons"].push_back("Duplicate declared identity");}
        d.diagnostic("partial_projection","Published 2024 namespace subset only; no complete XSD/conformance validation, schedule, playback, RF tuning or TS association.");deadline(start);
    }
};
class Store {
    std::unique_ptr<Document> current;uint64_t revision=0;
    const Document& require(const Json& args) const {if(!current)throw std::runtime_error("Import a DVB-I document first");if(args.contains("document_revision")&&args.at("document_revision")!=current->revision)throw std::runtime_error("Stale DVB-I document revision");return *current;}
public:
    Json importDocument(const Json& args,const fs::path& path){if(args.at("profile")!=Profile)throw std::runtime_error("Unsupported DVB-I profile");if(args.contains("expected_document_revision")&&args.at("expected_document_revision")!=revision)throw std::runtime_error("Stale DVB-I document revision before import");const auto start=Clock::now();auto d=std::make_unique<Document>();d->revision=revision+1;d->sourcePath=utf8Path(fs::absolute(path));d->original=readLocal(path,start);d->sha256=digest(d->original);{Parser parser(*d,start);parser.parse();}Projection(*d,start).run();auto result=d->metadata();current=std::move(d);revision=current->revision;return result;}
    Json query(const Json& args) const {const auto& d=require(args);size_t offset=args.value("offset",size_t(0)),limit=args.value("limit",size_t(200));if(limit<1||limit>500)throw std::runtime_error("DVB-I query limit must be 1..500");Json result=d.metadata(),nodes=Json::array();size_t end=std::min(d.nodes.size(),offset>d.nodes.size()?d.nodes.size():offset+limit);for(size_t i=offset;i<end;i++)nodes.push_back(d.nodes[i]);result["nodes"]=nodes;result["page"]={{"offset",offset},{"limit",limit},{"total",d.nodes.size()},{"has_more",end<d.nodes.size()},{"next_offset",end<d.nodes.size()?Json(end):Json()}};return result;}
    Json inspect(const Json& args) const {
        const auto& d=require(args);const std::string id=args.value("element_id",std::string("e0"));size_t index=0;
        auto parsed=id.empty()?std::from_chars(id.data(),id.data(),index):std::from_chars(id.data()+1,id.data()+id.size(),index);
        if(id.size()<2||id[0]!='e'||parsed.ec!=std::errc()||parsed.ptr!=id.data()+id.size()||index>=d.elements.size())throw std::runtime_error("Unknown DVB-I element id");
        const auto& e=d.elements[index];Json result=d.metadata(),kids=Json::array(),summaries=Json::array();
        const size_t childOffset=args.value("child_offset",size_t(0)),childLimit=args.value("child_limit",size_t(200));
        if(childLimit<1||childLimit>500||childOffset>MaxNodes)throw std::runtime_error("Invalid DVB-I child page");
        const size_t childEnd=std::min(e.children.size(),std::min(childOffset,e.children.size())+childLimit);
        for(size_t child:e.children)kids.push_back("e"+std::to_string(child));
        for(size_t i=childOffset;i<childEnd;i++){
            const auto child=e.children[i];const auto& c=d.elements[child];
            summaries.push_back({{"element_id","e"+std::to_string(child)},{"namespace",c.name.ns},{"local_name",c.name.local},{"qualified_name",c.name.qualified},{"path",c.path},{"line",c.line},{"column",c.column},{"has_children",!c.children.empty()},{"original_byte_offset",c.originalByteOffset},{"byte_offset_precision","element_start"}});
        }
        result["child_summaries"]=summaries;
        result["child_page"]={{"offset",childOffset},{"limit",childLimit},{"total",e.children.size()},{"has_more",childEnd<e.children.size()},{"next_offset",childEnd<e.children.size()?Json(childEnd):Json()}};
        result["element"]={{"element_id",id},{"parent_id",e.parent==SIZE_MAX?Json():Json("e"+std::to_string(e.parent))},{"namespace",e.name.ns},{"local_name",e.name.local},{"qualified_name",e.name.qualified},{"path",e.path},{"line",e.line},{"column",e.column},{"original_byte_offset",e.originalByteOffset},{"byte_offset_precision","element_start"},{"attributes",rawAttributes(e)},{"text",e.text},{"text_encoding","UTF-8 XML-normalized character data; authoritative original bytes are separate"},{"children",kids},{"evidence",d.evidence(index)}};
        const size_t offset=args.value("source_offset",size_t(0)),limit=args.value("source_limit",size_t(65536));
        if(limit<1||limit>65536||offset>d.original.size())throw std::runtime_error("Invalid DVB-I source page");
        const size_t count=std::min(limit,d.original.size()-offset),end=offset+count;
        // Original UTF-8 is already validated. Trim only partial code points at
        // the requested page edges; the hex range remains byte-for-byte exact.
        auto continuation=[&](size_t i){return i<d.original.size()&&(static_cast<unsigned char>(d.original[i])&0xc0)==0x80;};
        size_t textOffset=offset,textEnd=end;
        while(textOffset<end&&continuation(textOffset))++textOffset;
        while(textEnd>textOffset&&continuation(textEnd))--textEnd;
        size_t line=1;for(size_t i=0;i<textOffset;i++)if(d.original[i]=='\r'){++line;if(i+1<textOffset&&d.original[i+1]=='\n')++i;}else if(d.original[i]=='\n')++line;
        Json marker;
        if(e.originalByteOffset>=textOffset&&e.originalByteOffset<textEnd){
            size_t units=0;for(size_t i=textOffset;i<e.originalByteOffset;i++){
                const auto c=static_cast<unsigned char>(d.original[i]);if((c&0xc0)!=0x80)units+=c>=0xf0?2:1;
            }marker=units;
        }
        result["original_source"]={{"encoding","hex"},{"offset",offset},{"length",count},{"total",d.original.size()},{"has_more",end<d.original.size()},{"next_offset",end<d.original.size()?Json(end):Json()},{"data",hex(d.original.substr(offset,count))},
            {"text",d.original.substr(textOffset,textEnd-textOffset)},{"text_offset",textOffset},{"text_length",textEnd-textOffset},{"text_encoding","Original UTF-8 bytes; incomplete page-edge characters omitted with explicit byte range"},{"text_start_line",line},{"element_start_character",marker},{"character_offset_unit","UTF-16 code units in text; element start only, not an original byte offset"}};
        return result;
    }
};
} // namespace dvbi
