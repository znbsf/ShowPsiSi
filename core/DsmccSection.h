#pragma once
#include "tsDSMCCDownloadDataMessage.h"
#include "tsDSMCCUserToNetworkMessage.h"
#include "tsPSIBuffer.h"
#include "tsSection.h"

// Exact original-section adapter for the pinned SDK's protected payload API.
// No section rewrite, fabricated complete BinaryTable or validity override.
namespace dsmccsignalling {
template<class Table> class SectionDecoder final: public Table {
public:
    bool decode(ts::DuckContext& duck, const ts::Section& section) {
        this->clear();
        if (!section.isValid() || !section.isLongSection() || !this->isValidTableId(section.tableId())) {
            this->invalidate();
            return false;
        }
        ts::PSIBuffer buffer(duck, section.payload(), section.payloadSize());
        this->deserializePayloadWrapper(buffer, section);
        if (buffer.error() || !buffer.endOfRead()) {
            this->clear();
            this->invalidate();
        }
        if (this->isValid()) duck.addStandards(this->definingStandards());
        return this->isValid();
    }
};
struct ModuleDeclaration {
    size_t offset=0,length=0,infoOffset=0,infoLength=0;
    uint16_t id=0;
    uint8_t version=0;
    uint32_t size=0;
};
struct Message {
    bool valid=false,ddb=false;
    std::string status="malformed",diagnostic;
    uint32_t downloadId=0,transactionId=0;
    uint16_t blockSize=0,moduleId=0,blockNumber=0;
    uint8_t moduleVersion=0;
    size_t dataOffset=0,dataLength=0,compatibilityOffset=0,compatibilityLength=0;
    std::vector<ModuleDeclaration> modules;
};
inline Message parse(ts::DuckContext& duck, const Record& record) {
    Message result;
    const auto& b=record.raw;
    const auto fail=[&](const std::string& why,const std::string& status="malformed") {result.diagnostic=why;result.status=status;return result;};
    const auto word=[&](size_t p){return uint16_t(unsigned(b.at(p))<<8|b.at(p+1));};
    const auto dword=[&](size_t p){return uint32_t(word(p))<<16|word(p+2);};
    if(!record.valid)return fail("Invalid section evidence; no DSM-CC message decoded","invalid");
    if(b.size()<24 || b.size()>4096 || (b[0]!=0x3b&&b[0]!=0x3c))return fail("DSM-CC message header is absent or truncated");
    if((b[1]&0xc0)!=0x80)return fail("Only CRC-protected long DSM-CC sections are supported","unsupported_framing");
    ts::Section section(b.data(),b.size(),ts::PID(record.pid),ts::CRC32::CHECK);
    if(!section.isValid())return fail("Original DSM-CC section failed SDK envelope/CRC validation","invalid");
    if(b[8]!=0x11 || b[9]!=3)return fail("Unsupported DSM-CC protocol discriminator or message type","unsupported_message");
    if(word(18)!=b.size()-24)return fail("DSM-CC message_length disagrees with original section payload");
    if(b[16]!=0xff)return fail("DSM-CC message reserved byte is invalid");
    if(b[17]!=0)return fail("DSM-CC adaptation headers remain unsupported; original bytes retained","unsupported_adaptation");
    result.ddb=b[0]==0x3c;
    if(word(10)!=(result.ddb?0x1003:0x1002))return fail("Only DII and DDB source cards are supported","unsupported_message");
    if(result.ddb) {
        SectionDecoder<ts::DSMCCDownloadDataMessage> value;
        if(!value.decode(duck,section))return fail("Exact DDB payload failed SDK validation");
        if(b.size()<30 || b[23]!=0xff)return fail("DDB header is truncated or has invalid reserved data");
        result.downloadId=value.header.download_id;result.moduleId=value.module_id;result.moduleVersion=value.module_version;result.blockNumber=value.block_number;
        result.dataOffset=26;result.dataLength=b.size()-30;
        if(value.block_data.size()!=result.dataLength || value.block_number!=word(24) || value.module_id!=word(20) || value.module_version!=b[22] || value.version()!=record.version || value.isCurrent()!=record.current)
            return fail("Pinned SDK exact-section DDB contract mismatch");
    } else {
        if(b.size()<46)return fail("DII fixed fields are truncated");
        // Bound untrusted counts before the SDK allocates its typed entry list.
        const size_t end=b.size()-4,compatEnd=38+word(36);size_t p=38;
        if(compatEnd+2>end)return fail("DII compatibility exceeds original section");
        result.compatibilityOffset=36;result.compatibilityLength=2+word(36);
        if(word(36)) {
            if(p+2>compatEnd)return fail("DII compatibility count is truncated");
            const unsigned descriptors=word(p);p+=2;
            if(descriptors>256)return fail("DII compatibility declaration limit exceeded (256)","resource_limit");
            for(unsigned i=0;i<descriptors;++i) {
                if(p+11>compatEnd || b[p+1]<9 || p+2+b[p+1]>compatEnd)return fail("DII compatibility descriptor exceeds original structure");
                const size_t next=p+2+b[p+1];const unsigned subCount=b[p+10];size_t sub=p+11;
                for(unsigned j=0;j<subCount;++j) {if(sub+2>next || sub+2+b[sub+1]>next)return fail("DII private compatibility selector exceeds descriptor");sub+=2+b[sub+1];}
                if(sub!=next)return fail("DII compatibility descriptor length disagrees with selectors");p=next;
            }
            if(p!=compatEnd)return fail("DII compatibility length disagrees with descriptor count");
        }
        const unsigned count=word(p);p+=2;
        if(count>256)return fail("DII module declaration limit exceeded (256)","resource_limit");
        for(unsigned i=0;i<count;++i) {
            if(p+8>end || p+8+b[p+7]>end)return fail("DII module declaration exceeds original section");
            result.modules.push_back({p,size_t(8+b[p+7]),p+8,b[p+7],word(p),b[p+6],dword(p+2)});p+=result.modules.back().length;
        }
        if(p+2>end || p+2+word(p)!=end)return fail("DII private-data length disagrees with original section");
        SectionDecoder<ts::DSMCCUserToNetworkMessage> value;
        if(!value.decode(duck,section) || !value.isDII())return fail("Exact DII payload failed SDK validation; non-BIOP module-info profiles may be unsupported");
        const auto* dii=value.toDII();result.downloadId=dii->download_id;result.transactionId=value.header.transaction_id;result.blockSize=dii->block_size;
        if(count!=dii->modules.size() || value.version()!=record.version || value.isCurrent()!=record.current)return fail("Pinned SDK DII module-list or section-header contract mismatch");
        auto typed=dii->modules.begin();
        for(const auto& module:result.modules) {
            const auto& sdk=(typed++)->second;
            if(module.id!=sdk.module_id || module.size!=sdk.module_size || module.version!=sdk.module_version)return fail("Pinned SDK DII module-field contract mismatch");
        }
    }
    result.valid=true;result.status="decoded";return result;
}
}
