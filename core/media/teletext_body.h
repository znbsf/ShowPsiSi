#ifndef SHOWPSISI_TELETEXT_BODY_H
#define SHOWPSISI_TELETEXT_BODY_H
#include "teletext_render.h"
#include <array>
#include <cstddef>
#include <cstdint>

namespace mediawire {
constexpr std::size_t kTeletextBodyRows = 23;
constexpr std::size_t kTeletextBodyColumns = 40;
constexpr std::size_t kTeletextBodyCells = kTeletextBodyRows * kTeletextBodyColumns;
constexpr const char kTeletextBodyCapability[] = "body-level1-geometry-partial";

struct TeletextBodyRowInput {
    bool present = false;
    TeletextRenderRowInput input;
    TeletextRenderContext context;
};
using TeletextBodyInput = std::array<TeletextBodyRowInput, kTeletextBodyRows>;

enum class TeletextBodyCoverage : uint8_t { Own = 1, Covered = 2, Both = 3 };
enum class TeletextBodyCandidate : uint8_t { Maybe, No, Yes, NotEvaluated };
enum class TeletextBodySourcePresence : uint8_t { NotInspected, Missing, Present };
enum class TeletextBodyRole : uint8_t {
    Uncertain, Missing, Normal, UpperHalf, LowerHalf, BackgroundOnly
};
enum class TeletextBodyOrigin : uint8_t { Uncertain, Missing, Own, Derived };
enum class TeletextBodyBoundary : uint8_t { Uncertain, WithinBody, OutOfBody };

// Independent of TeletextRenderIssue; never OR source RenderIssue into these.
enum TeletextBodyIssue : uint32_t {
    BodyNoIssue = 0,
    BodyUnknownLayout = 1u << 0,
    BodyMissingRow = 1u << 1,
    BodySourceRowMismatch = 1u << 2,
    BodyInvalidSourceRow = 1u << 3,
    BodyIncompleteSource = 1u << 4,
    BodyOutOfBody = 1u << 5
};

struct TeletextBodySourceRow {
    TeletextBodySourcePresence presence = TeletextBodySourcePresence::NotInspected;
    bool evaluated = false;
    bool has_provisional = false;
    // Available only for Present/evaluated source. Inactive storage is not a
    // known default source/context and is serialized as null by the API probe.
    TeletextRenderSource original;
    TeletextRenderContext context;
    TeletextRenderedRow provisional;
};

struct TeletextBodyRow {
    uint8_t row = 0; // result sets physical1..23;0 is not a valid composed row
    TeletextBodyCoverage incoming = TeletextBodyCoverage::Both;
    TeletextBodyCandidate candidate = TeletextBodyCandidate::Maybe;
    TeletextBodyCoverage next = TeletextBodyCoverage::Both;
    uint32_t candidate_issues = BodyNoIssue;
    uint32_t effective_issues = BodyUnknownLayout;
    TeletextBodySourceRow source;
};

struct TeletextBodyCell {
    uint8_t row = 0, column = 0;
    bool geometry_known = false;
    TeletextBodyOrigin origin = TeletextBodyOrigin::Uncertain;
    TeletextBodyRole role = TeletextBodyRole::Uncertain;
    //0 means unavailable. Own/Derived references rows[origin_row-1].source
    // and its column; the returned object owns all referenced provenance.
    uint8_t origin_row = 0, origin_column = 0;
    uint32_t issues = BodyUnknownLayout; // geometry only
    TeletextSemanticCell cell;
    TeletextBodyCell() { cell.kind = TeletextCellKind::Unknown; }
};

struct TeletextBody {
    std::array<TeletextBodyCell, kTeletextBodyCells> cells;
    std::array<TeletextBodyRow, kTeletextBodyRows> rows;
    TeletextBodyBoundary boundary = TeletextBodyBoundary::Uncertain;
    bool has_unknown_geometry = true;
    bool layout_complete = false; // all geometry known AND boundary WithinBody
    bool page_composition_complete = false; // always false for this capability
    bool visibility_applied = false;        // always false for this capability
    uint32_t issues = BodyUnknownLayout;    // OR of row effective_issues only
};

// Pure logical body1..23 only. Fixed920 cells in row-major order, physical
// row1 has no incoming occupancy from excluded row0. All values are owned.
// Present candidates not definitely Covered invoke interpret_teletext_row once.
// Missing and Covered sources are not interpreted; Covered input is uninspected.
// Maybe geometry never uses fallback Normal/Double as proof. A Both row is
// entirely uncertain, but its known-No candidate can restore next Own.
// LowerHalf inherits upper attributes/provenance; BackgroundOnly inherits only
// upper background into a fresh neutral cell. No lower-source control is used.
// row23 next Own/Covered/Both maps boundary WithinBody/OutOfBody/Uncertain.
// No PageStore/raw/header/boxing/visibility/raster/timing or persistent state.
TeletextBody compose_teletext_body(const TeletextBodyInput&);
}
#endif
