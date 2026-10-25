#pragma once
#include <nlohmann/json.hpp>
#include <vector>
#include <string>
#include <sstream>
#include <iomanip>

// Presentation evidence for the selected section only. MSB-first bit offsets;
// never attach guessed offsets to SDK XML or to a merged multi-section table.
namespace siwire {
using Json = nlohmann::json;
class Builder {
    const std::vector<uint8_t>& bytes;
    const Json& descriptors;
    size_t end;
    size_t word(size_t p) const { return (size_t(bytes[p]) << 8) | bytes[p+1]; }
    Json node(const std::string& path,const std::string& label) const {
        return {{"path",path},{"label",label},{"fields",Json::array()},{"children",Json::array()}};
    }
    void field(Json& n,const char* name,size_t bit,size_t width,const std::string& comment="") const {
        if(!width || bit>bytes.size()*8 || width>bytes.size()*8-bit)return;
        std::string value;
        if(width<=48){
            uint64_t number=0;
            for(size_t i=bit;i<bit+width;++i)number=(number<<1)|((bytes[i/8]>>(7-i%8))&1);
            std::ostringstream text;text<<"0x"<<std::hex<<std::uppercase<<std::setfill('0')<<std::setw(int((width+3)/4))<<number;
            text<<" ["<<std::dec<<number<<"]";value=text.str();
        }else{
            std::ostringstream text;text<<std::hex<<std::uppercase<<std::setfill('0');
            for(size_t i=bit/8;i<(bit+width+7)/8;++i)text<<std::setw(2)<<unsigned(bytes[i]);
            value=text.str();
        }
        n["fields"].push_back({{"name",name},{"value",value},{"help",comment},{"bit_offset",bit},{"bit_length",width}});
    }
    void loop(Json& parent,size_t begin,size_t stop) const {
        if(begin>stop || stop>end)return;
        for(size_t p=begin;p+2<=stop;){
            const size_t length=bytes[p+1];if(length>stop-p-2)break;
            std::string name="Descriptor";bool decoded=false;
            for(const auto& d:descriptors)if(d.value("offset",size_t(-1))==p){name=d.value("name",name);decoded=d.value("decode_status",std::string())=="decoded";break;}
            auto n=node(parent["path"].get<std::string>()+"/descriptor/"+std::to_string(p),name);
            n["descriptor_offset"]=p;n["range"]={{"offset",p},{"length",length+2}};
            field(n,"descriptor_tag",p*8,8,"Descriptor type; private meanings require namespace evidence");
            field(n,"descriptor_length",p*8+8,8,"Payload length in bytes");
            field(n,"payload",(p+2)*8,length*8,"Original payload; decoded attributes are available below without inferred bit ranges");
            // Only expose descriptor layouts whose SDK identity was established
            // in the current namespace. Unknown/private payloads remain opaque.
            if(decoded){
                const size_t q=p+2,stop=q+length;
                if(name=="stream_identifier_descriptor" && length==1)field(n,"component_tag",q*8,8);
                else if(name=="registration_descriptor" && length>=4){field(n,"format_identifier",q*8,32);field(n,"additional_identification_info",(q+4)*8,(length-4)*8);}
                else if(name=="CA_descriptor" && length>=4){field(n,"CA_system_id",q*8,16);field(n,"reserved",q*8+16,3);field(n,"CA_PID",q*8+19,13);field(n,"private_data",(q+4)*8,(length-4)*8,"Opaque CA-system-specific data");}
                else if(name=="ISO_639_language_descriptor" && length%4==0){
                    for(size_t i=q;i<stop;i+=4){auto entry=node(n["path"].get<std::string>()+"/language/"+std::to_string(i),"Language");field(entry,"ISO_639_language_code",i*8,24);field(entry,"audio_type",i*8+24,8);n["children"].push_back(std::move(entry));}
                }else if(name=="service_descriptor" && length>=3){
                    field(n,"service_type",q*8,8);field(n,"service_provider_name_length",q*8+8,8);
                    size_t next=q+2+bytes[q+1];
                    if(next<stop){field(n,"service_provider_name",(q+2)*8,bytes[q+1]*8,"Encoded broadcast text; decoded text below");field(n,"service_name_length",next*8,8);if(bytes[next]<=stop-next-1)field(n,"service_name",(next+1)*8,bytes[next]*8,"Encoded broadcast text; decoded text below");}
                }else if(name=="network_name_descriptor" || name=="bouquet_name_descriptor")field(n,name=="network_name_descriptor"?"network_name":"bouquet_name",q*8,length*8,"Encoded broadcast text; decoded text below");
                else if(name=="short_event_descriptor" && length>=5){
                    field(n,"ISO_639_language_code",q*8,24);field(n,"event_name_length",q*8+24,8);
                    size_t next=q+4+bytes[q+3];
                    if(next<stop){field(n,"event_name",(q+4)*8,bytes[q+3]*8,"Encoded broadcast text; decoded text below");field(n,"text_length",next*8,8);if(bytes[next]<=stop-next-1)field(n,"text",(next+1)*8,bytes[next]*8,"Encoded broadcast text; decoded text below");}
                }
            }
            parent["children"].push_back(std::move(n));p+=length+2;
        }
    }
public:
    Builder(const std::vector<uint8_t>& b,const Json& d):bytes(b),descriptors(d),end(b.size()){}
    Json build(bool semanticLayout) {
        auto root=node("section","Section");
        if(bytes.size()<3)return root;
        const unsigned tid=bytes[0];const bool longSyntax=(bytes[1]&0x80)!=0;
        field(root,"table_id",0,8,"Table identifier");
        field(root,"section_syntax_indicator",8,1,"Long-section syntax indicator");
        field(root,"private_indicator",9,1,"Meaning depends on the table specification");
        field(root,"reserved",10,2,"Reserved bits");
        field(root,"section_length",12,12,"Bytes following this field, including CRC when present");
        // A declared-length mismatch cannot establish payload or CRC boundaries.
        if((word(1)&0x0fff)+3!=bytes.size())return root;
        const bool crc=longSyntax || tid==0x73;
        if(crc && bytes.size()>=7)end-=4;
        if(longSyntax && end>=8){
            field(root,"table_id_extension",24,16,tid==2?"program_number":tid==0?"transport_stream_id":"Table-specific extension");
            field(root,"reserved",40,2,"Reserved bits");
            field(root,"version_number",42,5,"Version of this section");
            field(root,"current_next_indicator",47,1,"1: current; 0: next");
            field(root,"section_number",48,8,"Section number within this table");
            field(root,"last_section_number",56,8,"Last section number within this table");
        }
        // Decode loop boundaries only for a valid, context-decoded table.
        if(semanticLayout && longSyntax && tid==0 && end>=8){
            for(size_t p=8;p+4<=end;p+=4){
                auto n=node("section/program/"+std::to_string(p),"Program "+std::to_string(word(p)));
                field(n,"program_number",p*8,16,"0: network signalling; otherwise program identifier");
                field(n,"reserved",p*8+16,3,"Reserved bits");
                field(n,word(p)?"program_map_PID":"network_PID",p*8+19,13,"Packet identifier");root["children"].push_back(std::move(n));
            }
        }else if(semanticLayout && longSyntax && tid==2 && end>=12){
            field(root,"reserved",64,3);field(root,"PCR_PID",67,13,"Program clock reference PID");
            field(root,"reserved",80,4);field(root,"program_info_length",84,12,"Program descriptor loop length");
            const size_t length=word(10)&0xfff;loop(root,12,12+length);
            for(size_t p=12+length;p+5<=end;){
                const size_t count=word(p+3)&0xfff;if(count>end-p-5)break;
                auto n=node("section/stream/"+std::to_string(p),"Stream PID "+std::to_string(word(p+1)&0x1fff));
                field(n,"stream_type",p*8,8,"Signalled stream type; private values require context");
                field(n,"reserved",p*8+8,3);field(n,"elementary_PID",p*8+11,13,"Elementary stream packet identifier");
                field(n,"reserved",p*8+24,4);field(n,"ES_info_length",p*8+28,12,"Stream descriptor loop length");
                loop(n,p+5,p+5+count);root["children"].push_back(std::move(n));p+=5+count;
            }
        }else if(semanticLayout && longSyntax && (tid==0x42 || tid==0x46) && end>=11){
            field(root,"original_network_id",64,16);field(root,"reserved",80,8);
            for(size_t p=11;p+5<=end;){
                size_t count=word(p+3)&0xfff;if(count>end-p-5)break;
                auto n=node("section/service/"+std::to_string(p),"Service "+std::to_string(word(p)));
                field(n,"service_id",p*8,16);field(n,"reserved",p*8+16,6);
                field(n,"EIT_schedule_flag",p*8+22,1);field(n,"EIT_present_following_flag",p*8+23,1);
                field(n,"running_status",p*8+24,3);field(n,"free_CA_mode",p*8+27,1);
                field(n,"descriptors_loop_length",p*8+28,12);loop(n,p+5,p+5+count);
                root["children"].push_back(std::move(n));p+=5+count;
            }
        }else if(semanticLayout && longSyntax && (tid==0x40 || tid==0x41 || tid==0x4a) && end>=12){
            field(root,"reserved",64,4);field(root,tid==0x4a?"bouquet_descriptors_length":"network_descriptors_length",68,12);
            size_t p=10+(word(8)&0xfff);loop(root,10,p);
            if(p+2<=end){
                field(root,"reserved",p*8,4);field(root,"transport_stream_loop_length",p*8+4,12);
                const size_t stop=p+2+(word(p)&0xfff);p+=2;
                if(stop<=end)for(;p+6<=stop;){
                    const size_t count=word(p+4)&0xfff;if(count>stop-p-6)break;
                    auto n=node("section/transport/"+std::to_string(p),"Transport "+std::to_string(word(p)));
                    field(n,"transport_stream_id",p*8,16);field(n,"original_network_id",p*8+16,16);
                    field(n,"reserved",p*8+32,4);field(n,"transport_descriptors_length",p*8+36,12);
                    loop(n,p+6,p+6+count);root["children"].push_back(std::move(n));p+=6+count;
                }
            }
        }else if(semanticLayout && longSyntax && tid>=0x4e && tid<=0x6f && end>=14){
            field(root,"transport_stream_id",64,16);field(root,"original_network_id",80,16);
            field(root,"segment_last_section_number",96,8);field(root,"last_table_id",104,8);
            for(size_t p=14;p+12<=end;){
                const size_t count=word(p+10)&0xfff;if(count>end-p-12)break;
                auto n=node("section/event/"+std::to_string(p),"Event "+std::to_string(word(p)));
                field(n,"event_id",p*8,16);field(n,"start_time",p*8+16,40,"MJD and UTC BCD; decoded time in semantic fields");
                field(n,"duration",p*8+56,24,"BCD hours, minutes, seconds");
                field(n,"running_status",p*8+80,3);field(n,"free_CA_mode",p*8+83,1);
                field(n,"descriptors_loop_length",p*8+84,12);loop(n,p+12,p+12+count);
                root["children"].push_back(std::move(n));p+=12+count;
            }
        }else if(semanticLayout && !longSyntax && (tid==0x70 || tid==0x73) && end>=8){
            field(root,"UTC_time",24,40,"MJD and UTC BCD; decoded time in semantic fields");
            if(tid==0x73 && end>=10){field(root,"reserved",64,4);field(root,"descriptors_loop_length",68,12);loop(root,10,10+(word(8)&0xfff));}
        }else if(semanticLayout && longSyntax && tid==1 && end>=8)loop(root,8,end);
        if(crc && bytes.size()>=7)field(root,"CRC_32",end*8,32,"Transmitted CRC; validity is reported by the engine");
        root["scope"]="Selected section, MSB-first bit ranges; unsupported payload fields retain semantic/raw views";
        return root;
    }
};
inline Json inspect(const std::vector<uint8_t>& bytes,const Json& descriptors,bool semanticLayout){return Builder(bytes,descriptors).build(semanticLayout);}
}
