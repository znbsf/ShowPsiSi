#include "teletext_render.h"
#include "teletext.h"

namespace mediawire {
namespace {
struct RowState {
    bool mosaics = false, separated = false, hold = false;
    uint8_t foreground = 7, background = 0;
    uint8_t held_mask = 0;
    bool held_separated = false;
    bool flash = false, conceal = false, secondary = false;
    TeletextCellHeight height = TeletextCellHeight::Normal;
};

void clear_held(RowState& state) {
    state.held_mask = 0;
    state.held_separated = false;
}
void set_height(RowState& state, TeletextCellHeight height) {
    if (state.height != height) clear_held(state);
    state.height = height;
}
void set_colour(RowState& state, uint8_t colour, bool mosaics) {
    if (state.mosaics != mosaics) clear_held(state);
    state.mosaics = mosaics;
    state.foreground = colour;
    state.conceal = false;
}
void snapshot(TeletextSemanticCell& cell, const RowState& state) {
    cell.foreground = state.foreground;
    cell.background = state.background;
    cell.flash = state.flash;
    cell.conceal = state.conceal;
    cell.height = state.height;
    cell.g0 = state.secondary ? TeletextG0Selection::UnknownSecondary :
                                TeletextG0Selection::Primary;
}
void paint_mosaic(TeletextSemanticCell& cell, uint8_t mask, bool separated,
                  bool held) {
    cell.kind = TeletextCellKind::Mosaic;
    cell.mosaic_mask = mask;
    cell.separated = separated;
    cell.held = held;
}
void paint_g0(TeletextSemanticCell& cell, uint8_t code, const RowState& state,
              const TeletextRenderContext& context) {
    if (state.secondary) cell.issues |= RenderUnknownSecondary;
    if (!context.default_latin_group0000 || context.charset_override_uninterpreted)
        cell.issues |= RenderEnhancementsUninterpreted;
    if (cell.issues & (RenderUnknownSecondary | RenderEnhancementsUninterpreted)) {
        cell.kind = TeletextCellKind::Unknown;
        return;
    }
    if (code == 0x7f) {
        cell.kind = TeletextCellKind::G0Rectangle;
        return;  // semantic symbol, not ASCII DEL or a chosen font's pixels
    }
    uint32_t scalar = 0;
    const auto lookup = teletext_latin_group0_national(code, context.national, scalar);
    if (lookup == TeletextNationalLookup::UnsupportedSelector) {
        cell.kind = TeletextCellKind::Unknown;
        cell.issues |= RenderUnknownNational;
        return;
    }
    cell.kind = TeletextCellKind::G0;
    cell.unicode_scalar = lookup == TeletextNationalLookup::Resolved ? scalar : code;
}
void set_at(RowState& state, uint8_t code) {
    switch (code) {
    case 0x09: state.flash = false; break;
    case 0x0c: set_height(state, TeletextCellHeight::Normal); break;
    case 0x18: state.conceal = true; break;
    case 0x19: state.separated = false; break;
    case 0x1a: state.separated = true; break;
    case 0x1c: state.background = 0; break;
    case 0x1d: state.background = state.foreground; break;
    case 0x1e: state.hold = true; break;
    default: break;
    }
}
void set_after(RowState& state, uint8_t code) {
    if (code >= 0x01 && code <= 0x07) set_colour(state, code, false);
    else if (code >= 0x11 && code <= 0x17) set_colour(state, code & 7, true);
    else if (code == 0x08) state.flash = true;
    else if (code == 0x0d) set_height(state, TeletextCellHeight::Double);
    else if (code == 0x1b) state.secondary = !state.secondary;
    else if (code == 0x1f) state.hold = false;
    // Level1/1.5 no-response00/10/0e/0f have no state effect. Box controls
    // remain explicit unsupported metadata, not a fabricated box policy.
}
}  // namespace

TeletextRenderedRow interpret_teletext_row(const TeletextRenderRowInput& input,
                                          const TeletextRenderContext& context) {
    TeletextRenderedRow output;
    output.source = input.source;
    output.render_national = context.national;
    uint32_t structural_issues = RenderNoIssue;
    if (input.source.packet < 1 || input.source.packet > 23)
        structural_issues |= RenderOutsideInitialRows;
    for (const auto& slot : input.slots)
        if (slot.code > 0x7f) structural_issues |= RenderInvalidInput;
    for (unsigned column = 0; column < input.slots.size(); ++column) {
        auto& cell = output.cells[column];
        const auto& slot = input.slots[column];
        cell.column = static_cast<uint8_t>(column);
        cell.source_code = slot.code;
        cell.source_present = slot.present;
        cell.source_parity_valid = slot.odd_parity_valid;
        if (structural_issues) {
            cell.kind = TeletextCellKind::Unknown;
            cell.issues = structural_issues;
        }
    }
    if (structural_issues) {
        output.issues = structural_issues;
        return output;
    }
    output.row_interpretation_valid = true;
    if (!context.default_latin_group0000 || context.charset_override_uninterpreted)
        output.issues |= RenderEnhancementsUninterpreted;
    RowState state;
    for (unsigned column = 0; column < input.slots.size(); ++column) {
        const auto& slot = input.slots[column];
        auto& cell = output.cells[column];
        const uint8_t code = slot.code;
        if (!slot.present || !slot.odd_parity_valid) {
            snapshot(cell, state);
            cell.kind = slot.present ? TeletextCellKind::Invalid : TeletextCellKind::Missing;
            cell.issues = slot.present ? RenderInvalidParity : RenderMissingSource;
        } else {
            const bool control = code < 0x20;
            if (control) set_at(state, code);
            snapshot(cell, state);
            if (code == 0x0a || code == 0x0b) cell.issues |= RenderBoxingUnimplemented;
            if (code == 0x1b) cell.issues |= RenderUnknownSecondary;
            if (code == 0x0d || state.height == TeletextCellHeight::Double) {
                cell.issues |= RenderNeedsPageComposition;
                if (input.source.packet == 23) cell.issues |= RenderIllegalSizeBoundary;
            }
            if (control) {
                if (state.mosaics && state.hold)
                    paint_mosaic(cell, state.held_mask, state.held_separated, true);
                else cell.kind = TeletextCellKind::SpacingBlank;
            } else if (state.mosaics && (code & 0x20)) {
                const uint8_t mask = (code & 0x1f) | ((code & 0x40) >> 1);
                paint_mosaic(cell, mask, state.separated, false);
                state.held_mask = mask;
                state.held_separated = state.separated;
            } else {
                paint_g0(cell, code, state, context);
            }
            if (control) set_after(state, code);
        }
        output.issues |= cell.issues;
    }
    return output;
}
}
