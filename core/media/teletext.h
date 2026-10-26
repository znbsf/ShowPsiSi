#ifndef SHOWPSISI_TELETEXT_H
#define SHOWPSISI_TELETEXT_H
#include <cstdint>
#include <cstddef>
#include <string>
#include <array>
#include <vector>
namespace mediawire {
// Lookup only the thirteen national positions for the declared default Latin
// group 0000 profile. Non-Resolved outcomes leave scalar unchanged. This helper
// does not apply preview blanking, header policy or extension selectors.
enum class TeletextNationalLookup { NotNational, Resolved, UnsupportedSelector };
TeletextNationalLookup teletext_latin_group0_national(
    uint8_t code, int national, uint32_t& scalar);
struct TeletextRow {
    int magazine=0, packet=0, page_hex=-1, subcode=-1, national=-1;
    uint64_t epoch=0;
    uint64_t source_unit_index=0;
    int designation=-1;
    std::string raw_hex;
    bool charset_override_unsupported=false;
    bool context=false, erase=false, subtitle=false, serial=false, supported=true;
    // Header C5/C7/C8/C9/C10 metadata, inherited only with acquired context.
    // Parsing these flags does not apply boxing, visibility or display timing.
    bool newsflash=false, suppress_header=false, update_indicator=false;
    bool interrupted_sequence=false, inhibit_display=false;
    unsigned corrected_bits=0, parity_errors=0;
    std::wstring text;
    std::string error;
};
// One instance per PID/input. DVB bytes have one defined wire orientation.
// Default Latin group 0000 is an explicit local profile assumption, not a
// universal interpretation of the three header national bits. X/28 and M/29
// selectors remain unsupported and mark affected snapshots unsupported.
// Records are transmission snapshots, not a persistent screen/subtitle renderer.
class TeletextDecoder {
    TeletextRow headers_[9];
    uint64_t epoch_=0;
    int active_magazine_=0;
    bool serial_=false;
    bool magazine_override_[9]={};
public:
    bool decode(const uint8_t* unit,std::size_t size,TeletextRow& out);
    // Opt-in semantic output must retain a known M/29 uncertainty even when
    // an invalidated/missing page header prevents normal row inheritance.
    bool magazine_charset_override_unsupported(int magazine) const {
        return magazine>=1 && magazine<=8 && magazine_override_[magazine];
    }
};
// Bounded transmitted packet memory, one store per PID/input. This is not a
// display renderer: retained rows carry their source epoch and raw unit, and
// unsupported enhancements are preserved without interpreting their content.
struct TeletextPage {
    bool clear_applied=false;
    TeletextRow header;
    std::array<TeletextRow,26> packets;
    std::array<bool,26> present={};
    std::vector<TeletextRow> extensions;
    bool charset_override_unsupported=false;
    uint64_t revision=0, last_update=0;
};
class TeletextPageStore {
    std::vector<TeletextPage> pages_;
    std::vector<TeletextRow> magazine_extensions_[9];
    uint64_t updates_=0, evictions_=0, unassociated_=0;
    int evicted_page_=-1, evicted_subcode_=-1;
public:
    enum { capacity=64 };
    // Caller supplies only successfully decoded units. Returns the changed page
    // or nullptr for a duplicate/stale event, unknown context or magazine data.
    // C4 is applied once on a new header epoch, never on inherited row flags.
    const TeletextPage* consume(const TeletextRow& row);
    const std::vector<TeletextPage>& pages() const { return pages_; }
    const std::vector<TeletextRow>& magazine_extensions(int magazine) const;
    uint64_t evictions() const { return evictions_; }
    uint64_t unassociated() const { return unassociated_; }
    int evicted_page() const { return evicted_page_; }
    int evicted_subcode() const { return evicted_subcode_; }
};
}
#endif
