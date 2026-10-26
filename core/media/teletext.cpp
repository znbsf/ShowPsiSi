#include "teletext.h"
#include "teletext_render.h"
#include <algorithm>
#include <cstring>
namespace mediawire {
// ETSI EN 300 706 V1.2.1 Tables 32/36, default Latin group 0000 only.
// Unicode text policy: English 0x60 -> U+2014, 0x7c -> U+2016.
TeletextNationalLookup teletext_latin_group0_national(
    uint8_t c,int national,uint32_t& scalar){
    static const uint8_t positions[]={0x23,0x24,0x40,0x5b,0x5c,0x5d,0x5e,0x5f,0x60,0x7b,0x7c,0x7d,0x7e};
    static const wchar_t subsets[7][13]={
        {0x00a3,0x0024,0x0040,0x2190,0x00bd,0x2192,0x2191,0x0023,0x2014,0x00bc,0x2016,0x00be,0x00f7}, // English
        {0x0023,0x0024,0x00a7,0x00c4,0x00d6,0x00dc,0x005e,0x005f,0x00b0,0x00e4,0x00f6,0x00fc,0x00df}, // German
        {0x0023,0x00a4,0x00c9,0x00c4,0x00d6,0x00c5,0x00dc,0x005f,0x00e9,0x00e4,0x00f6,0x00e5,0x00fc}, // Swedish/Finnish/Hungarian
        {0x00a3,0x0024,0x00e9,0x00b0,0x00e7,0x2192,0x2191,0x0023,0x00f9,0x00e0,0x00f2,0x00e8,0x00ec}, // Italian
        {0x00e9,0x00ef,0x00e0,0x00eb,0x00ea,0x00f9,0x00ee,0x0023,0x00e8,0x00e2,0x00f4,0x00fb,0x00e7}, // French
        {0x00e7,0x0024,0x00a1,0x00e1,0x00e9,0x00ed,0x00f3,0x00fa,0x00bf,0x00fc,0x00f1,0x00e8,0x00e0}, // Portuguese/Spanish
        {0x0023,0x016f,0x010d,0x0165,0x017e,0x00fd,0x00ed,0x0159,0x00e9,0x00e1,0x011b,0x00fa,0x0161}, // Czech/Slovak
    };
    for(unsigned i=0;i<sizeof(positions);++i){
        if(c!=positions[i])continue;
        if(national<0 || national>=7)return TeletextNationalLookup::UnsupportedSelector;
        scalar=static_cast<uint32_t>(subsets[national][i]);
        return TeletextNationalLookup::Resolved;
    }
    return TeletextNationalLookup::NotNational;
}
namespace {
uint8_t reverse8(uint8_t v){uint8_t r=0;for(int i=0;i<8;++i){r=uint8_t((r<<1)|(v&1));v>>=1;}return r;}
unsigned bits(uint8_t v){unsigned n=0;while(v){n+=v&1;v>>=1;}return n;}
int hamming(uint8_t v,unsigned& corrected){
    const uint8_t table[]={0x15,0x02,0x49,0x5e,0x64,0x73,0x38,0x2f,0xd0,0xc7,0x8c,0x9b,0xa1,0xb6,0xfd,0xea};
    for(int i=0;i<16;++i){unsigned d=bits(v^table[i]);if(d<=1){corrected+=d;return i;}}return -1;
}
// Preserve the historical lossy preview; semantic cells use the shared
// lookup directly and keep controls/rectangle/uncertainty separately.
wchar_t latin_group0_glyph(uint8_t c,int national,bool& supported){
    if(c<32 || c==127)return L' ';
    uint32_t scalar=0;
    const auto lookup=teletext_latin_group0_national(c,national,scalar);
    if(lookup==TeletextNationalLookup::Resolved)return static_cast<wchar_t>(scalar);
    if(lookup==TeletextNationalLookup::UnsupportedSelector){supported=false;return 0xfffd;}
    return wchar_t(c);
}
}
bool TeletextDecoder::decode(const uint8_t* unit,std::size_t size,TeletextRow& out){
    TeletextRow r;
    if(!unit||size!=44||unit[1]!=0xe4){for(auto& h:headers_)h=TeletextRow();active_magazine_=0;serial_=true;r.error="invalid DVB Teletext unit length/framing";out=r;return false;}
    const char digits[]="0123456789abcdef";
    for(std::size_t i=0;i<size;++i){r.raw_hex+=digits[unit[i]>>4];r.raw_hex+=digits[unit[i]&15];}
    uint8_t d[42];for(int i=0;i<42;++i)d[i]=reverse8(unit[i+2]);
    int lo=hamming(d[0],r.corrected_bits),hi=hamming(d[1],r.corrected_bits);
    if(lo<0||hi<0){for(auto& h:headers_)h=TeletextRow();active_magazine_=0;serial_=true;r.error="uncorrectable Teletext address";out=r;return false;}
    int address=lo|(hi<<4);r.magazine=(address&7)?address&7:8;r.packet=address>>3;
    if(r.packet==0){
        int h[8];bool valid=true;for(int i=0;i<8;++i){h[i]=hamming(d[2+i],r.corrected_bits);valid=valid&&h[i]>=0;}
        if(!valid){headers_[r.magazine]=TeletextRow();active_magazine_=0;serial_=true;r.error="uncorrectable Teletext page header";out=r;return false;}
        r.page_hex=(r.magazine<<8)|(h[1]<<4)|h[0];r.subcode=h[2]|((h[3]&7)<<4)|(h[4]<<8)|((h[5]&3)<<12);
        r.erase=(h[3]&8)!=0;r.subtitle=(h[5]&8)!=0;r.serial=(h[7]&1)!=0;
        r.newsflash=(h[5]&4)!=0;r.suppress_header=(h[6]&1)!=0;
        r.update_indicator=(h[6]&2)!=0;r.interrupted_sequence=(h[6]&4)!=0;r.inhibit_display=(h[6]&8)!=0;
        r.national=((h[7]&2)<<1)|((h[7]&4)>>1)|((h[7]&8)>>3);r.epoch=++epoch_;r.context=true;r.charset_override_unsupported=magazine_override_[r.magazine];
        headers_[r.magazine]=r;active_magazine_=r.magazine;serial_=r.serial;
    }else if(headers_[r.magazine].context && (!serial_||active_magazine_==r.magazine)){
        const auto& h=headers_[r.magazine];r.context=true;r.page_hex=h.page_hex;r.subcode=h.subcode;r.epoch=h.epoch;r.national=h.national;r.erase=h.erase;r.subtitle=h.subtitle;r.serial=h.serial;r.charset_override_unsupported=h.charset_override_unsupported;
        r.newsflash=h.newsflash;r.suppress_header=h.suppress_header;r.update_indicator=h.update_indicator;
        r.interrupted_sequence=h.interrupted_sequence;r.inhibit_display=h.inhibit_display;
    }
    if(r.packet>=26 && r.packet<=29){unsigned ignored=0;r.designation=hamming(d[2],ignored);}
    if(r.packet==28 && r.context){headers_[r.magazine].charset_override_unsupported=true;r.charset_override_unsupported=true;}
    if(r.packet==29){magazine_override_[r.magazine]=true;headers_[r.magazine].charset_override_unsupported=true;r.charset_override_unsupported=true;}
    if(r.packet<=25){
        if(r.national==7){r.supported=false;r.error="reserved national subset in default Latin group 0000";}
        for(int i=r.packet==0?10:2;i<42;++i){if(bits(d[i])%2!=1){++r.parity_errors;r.text+=wchar_t(0xfffd);}else r.text+=latin_group0_glyph(d[i]&127,r.national,r.supported);}
    }else{r.supported=false;r.error="extension/service packet retained raw; rendering unsupported";}
    if(r.charset_override_unsupported && r.packet<=25){r.supported=false;r.error="charset override unsupported in this epoch";}
    if(!r.supported && r.packet<=25 && r.error.empty())r.error="national character position unsupported";
    out=r;return true;
}
namespace {
// All extension designations, including one explicit undecodable slot, are
// bounded to 17 per packet type. Unknown content is never treated as text.
void retain_extension(std::vector<TeletextRow>& records,const TeletextRow& row){
    for(auto& old:records)if(old.packet==row.packet && old.designation==row.designation){old=row;return;}
    records.push_back(row);
}
}
const std::vector<TeletextRow>& TeletextPageStore::magazine_extensions(int magazine) const {
    static const std::vector<TeletextRow> empty;
    return magazine>=1 && magazine<=8 ? magazine_extensions_[magazine] : empty;
}
const TeletextPage* TeletextPageStore::consume(const TeletextRow& row){
    if(row.magazine<1 || row.magazine>8 || row.packet<0 || row.packet>31)return nullptr;
    if(row.packet>=26 && row.packet<=29 && (row.designation< -1 || row.designation>15))return nullptr;
    if(row.packet==29){
        retain_extension(magazine_extensions_[row.magazine],row);
        for(auto& page:pages_)if(page.header.magazine==row.magazine){
            // An uncertainty update is not an on-air page packet reception.
            page.charset_override_unsupported=true;++page.revision;
        }
        return nullptr;
    }
    if(row.packet>28)return nullptr; // service packets are not page memory.
    // Annex A.1: FF is a time-filling/terminating header, not an acquired page.
    if(!row.context || row.epoch==0 || row.page_hex<0 || row.subcode<0 || (row.page_hex&255)==255){++unassociated_;return nullptr;}
    auto found=std::find_if(pages_.begin(),pages_.end(),[&](const TeletextPage& p){
        return p.header.page_hex==row.page_hex && p.header.subcode==row.subcode;
    });
    if(row.packet==0){
        if(found!=pages_.end() && row.epoch<=found->header.epoch)return nullptr;
        if(found==pages_.end()){
            if(pages_.size()==capacity){
                auto victim=std::min_element(pages_.begin(),pages_.end(),[](const TeletextPage& a,const TeletextPage& b){return a.last_update<b.last_update;});
                evicted_page_=victim->header.page_hex;evicted_subcode_=victim->header.subcode;
                pages_.erase(victim);++evictions_;
            }
            pages_.push_back(TeletextPage());found=pages_.end()-1;
        }
        if(row.erase){found->clear_applied=true;found->present.fill(false);found->packets=std::array<TeletextRow,26>();found->extensions.clear();found->charset_override_unsupported=false;}
        found->header=row;
        found->charset_override_unsupported=found->charset_override_unsupported || row.charset_override_unsupported || !magazine_extensions_[row.magazine].empty();
    }else if(found==pages_.end() || found->header.epoch!=row.epoch){
        // An evicted page requires a fresh header; a surviving decoder context
        // alone cannot silently reconstruct an incomplete cached page.
        ++unassociated_;return nullptr;
    }
    if(row.packet<=25){found->packets[row.packet]=row;found->present[row.packet]=true;}
    else retain_extension(found->extensions,row);
    if(row.packet==28 || row.charset_override_unsupported)found->charset_override_unsupported=true;
    found->last_update=++updates_;++found->revision;return &*found;
}
}
