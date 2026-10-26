#ifndef SHOWPSISI_TELETEXT_RENDER_H
#define SHOWPSISI_TELETEXT_RENDER_H
#include <array>
#include <cstdint>

namespace mediawire {
// Partial, body-row semantic capability. No raw/header adapter, page
// composition, secondary charset resolution, rasterization or display clock.
enum class TeletextCellKind : uint8_t {
    Missing, Invalid, SpacingBlank, G0, G0Rectangle, Mosaic, Unknown
};
enum class TeletextCellHeight : uint8_t { Normal, Double };
enum class TeletextG0Selection : uint8_t { Primary, UnknownSecondary };

enum TeletextRenderIssue : uint32_t {
    RenderNoIssue = 0,
    RenderInvalidParity = 1u << 0,
    RenderMissingSource = 1u << 1,
    RenderUnknownNational = 1u << 2,
    RenderUnknownSecondary = 1u << 3,
    RenderEnhancementsUninterpreted = 1u << 4,
    // Bit5 is reserved; header rows are outside this capability.
    RenderBoxingUnimplemented = 1u << 6,
    RenderNeedsPageComposition = 1u << 7,
    RenderIllegalSizeBoundary = 1u << 8,
    RenderOutsideInitialRows = 1u << 9,
    RenderInvalidInput = 1u << 10
};

struct TeletextRenderSlot {
    uint8_t code = 0;  // logical seven-bit source code, never a preview glyph
    bool present = false;
    bool odd_parity_valid = false;
};
struct TeletextRenderSource {
    int packet = -1;
    uint64_t epoch = 0;
    int national = -1;  // provenance, not an implicit render selector
};
struct TeletextRenderRowInput {
    std::array<TeletextRenderSlot, 40> slots;
    TeletextRenderSource source;
};
struct TeletextRenderContext {
    int national = -1;  // explicit default Latin-group0000 selector,0..6 or unknown
    bool default_latin_group0000 = true;
    bool charset_override_uninterpreted = false;
};
struct TeletextSemanticCell {
    uint8_t column = 0;
    uint8_t source_code = 0;
    bool source_present = false, source_parity_valid = false;
    TeletextCellKind kind = TeletextCellKind::Missing;
    uint32_t unicode_scalar = 0;  // nonzero/resolved only for G0
    uint8_t mosaic_mask = 0;     // TL,TR,ML,MR,BL,BR; Mosaic only
    uint8_t foreground = 7, background = 0;
    bool separated = false, held = false;  // Mosaic only
    bool flash = false, conceal = false;
    TeletextCellHeight height = TeletextCellHeight::Normal;
    TeletextG0Selection g0 = TeletextG0Selection::Primary;
    uint32_t issues = RenderNoIssue;
};
struct TeletextRenderedRow {
    std::array<TeletextSemanticCell, 40> cells;
    TeletextRenderSource source;
    int render_national = -1;
    uint32_t issues = RenderNoIssue;
    bool row_interpretation_valid = false;
    bool page_composition_complete = false;  // always false for this capability
};

// Pure and stateless; resets all row attributes on each call. Accepts only
// body packet1..23 and exactly40 slots. Any code>127, including an absent
// slot's code, rejects the entire row. Rejected cells are Unknown with default
// attributes and the aggregate structural issue; source metadata is retained.
//
// Missing takes precedence over parity: no state update, own issue2; parity
// invalid: no state update, own issue1. Their attributes snapshot current state.
// These data issues do not make a structurally valid row invalid. No invalid or
// missing byte is treated as a spacing attribute or a held-mosaic update.
//
// Non-G0 scalar=0; non-Mosaic mask=0,separated=false,held=false. Issues are ORed
// into the row plus context uncertainty. Valid0d cells and valid cells painted
// in double height carry128 (also256 on row23); no lower row is generated.
// ESC cells carry8; G0 cells in unknown-secondary remain Unknown+8, while G1
// shapes remain known. Box controls carry64 without pretending to apply boxes.
// Level1 no-response00/10/0e/0f occupy control cells without changing state.
// With a known default Latin profile, an unknown national selector makes only
// the13 national positions Unknown+4. A non-Latin/override-uncertain context
// makes every G0 cell (including SPACE/rectangle) Unknown+16; G1 mosaic shapes
// stay known in this explicit partial profile. Secondary and context issues
// combine (8|16); the row carries context16 even if it contains no G0 cells.
TeletextRenderedRow interpret_teletext_row(
    const TeletextRenderRowInput&, const TeletextRenderContext&);
}
#endif
