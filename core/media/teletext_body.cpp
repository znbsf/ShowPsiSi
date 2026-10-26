#include "teletext_body.h"

namespace mediawire {
namespace {
TeletextBodyCell base_cell(uint8_t row, uint8_t column) {
    TeletextBodyCell result;
    result.row = row;
    result.column = column;
    result.cell.column = column;
    return result;
}

void evaluate_source(const TeletextBodyRowInput& input, TeletextBodyRow& row) {
    if (!input.present) {
        row.source.presence = TeletextBodySourcePresence::Missing;
        row.candidate_issues = BodyMissingRow;
        row.candidate = TeletextBodyCandidate::Maybe;
        return;
    }
    row.source.presence = TeletextBodySourcePresence::Present;
    row.source.original = input.input.source;
    row.source.context = input.context;
    row.source.evaluated = true;
    row.source.provisional = interpret_teletext_row(input.input, input.context);
    row.source.has_provisional = true;
    if (input.input.source.packet != row.row)
        row.candidate_issues |= BodySourceRowMismatch;
    if (!row.source.provisional.row_interpretation_valid)
        row.candidate_issues |= BodyInvalidSourceRow;
    for (const auto& slot : input.input.slots) {
        if (!slot.present || !slot.odd_parity_valid) {
            row.candidate_issues |= BodyIncompleteSource;
            break;
        }
    }
    if (row.candidate_issues != BodyNoIssue) {
        row.candidate = TeletextBodyCandidate::Maybe;
        return;
    }
    row.candidate = TeletextBodyCandidate::No;
    for (const auto& cell : row.source.provisional.cells) {
        if (cell.height == TeletextCellHeight::Double) {
            row.candidate = TeletextBodyCandidate::Yes;
            break;
        }
    }
}

TeletextBodyCoverage next_coverage(TeletextBodyCoverage incoming,
                                 TeletextBodyCandidate candidate) {
    if (incoming == TeletextBodyCoverage::Both)
        return candidate == TeletextBodyCandidate::No ? TeletextBodyCoverage::Own :
                                                        TeletextBodyCoverage::Both;
    if (candidate == TeletextBodyCandidate::No) return TeletextBodyCoverage::Own;
    if (candidate == TeletextBodyCandidate::Yes) return TeletextBodyCoverage::Covered;
    return TeletextBodyCoverage::Both;
}

void paint_own(TeletextBody& output, std::size_t index, TeletextBodyRow& row) {
    const bool outside = row.row == static_cast<uint8_t>(kTeletextBodyRows) &&
                         row.candidate == TeletextBodyCandidate::Yes;
    row.effective_issues = outside ? BodyOutOfBody : BodyNoIssue;
    for (std::size_t column = 0; column < kTeletextBodyColumns; ++column) {
        auto cell = base_cell(row.row, static_cast<uint8_t>(column));
        cell.cell = row.source.provisional.cells[column];
        cell.geometry_known = true;
        cell.origin = TeletextBodyOrigin::Own;
        cell.origin_row = row.row;
        cell.origin_column = static_cast<uint8_t>(column);
        const bool upper = cell.cell.height == TeletextCellHeight::Double;
        cell.role = upper ? TeletextBodyRole::UpperHalf : TeletextBodyRole::Normal;
        cell.issues = outside && upper ? BodyOutOfBody : BodyNoIssue;
        output.cells[index * kTeletextBodyColumns + column] = cell;
    }
}

void paint_unknown(TeletextBody& output, std::size_t index, TeletextBodyRow& row) {
    row.effective_issues = BodyUnknownLayout;
    if (row.incoming == TeletextBodyCoverage::Own)
        row.effective_issues |= row.candidate_issues;
    const bool missing = row.incoming == TeletextBodyCoverage::Own &&
                         row.source.presence == TeletextBodySourcePresence::Missing;
    for (std::size_t column = 0; column < kTeletextBodyColumns; ++column) {
        auto cell = base_cell(row.row, static_cast<uint8_t>(column));
        if (missing) {
            cell.origin = TeletextBodyOrigin::Missing;
            cell.role = TeletextBodyRole::Missing;
        }
        cell.issues = row.effective_issues;
        output.cells[index * kTeletextBodyColumns + column] = cell;
    }
}

void paint_lower(TeletextBody& output, std::size_t index, TeletextBodyRow& row) {
    // Covered can only follow a definite Own+Yes row; row1 starts Own.
    const auto& upper = output.rows[index - 1].source.provisional;
    row.effective_issues = BodyNoIssue;
    for (std::size_t column = 0; column < kTeletextBodyColumns; ++column) {
        auto cell = base_cell(row.row, static_cast<uint8_t>(column));
        cell.geometry_known = true;
        cell.origin = TeletextBodyOrigin::Derived;
        cell.origin_row = static_cast<uint8_t>(row.row - 1);
        cell.origin_column = static_cast<uint8_t>(column);
        cell.issues = BodyNoIssue;
        if (upper.cells[column].height == TeletextCellHeight::Double) {
            cell.role = TeletextBodyRole::LowerHalf;
            cell.cell = upper.cells[column];
        } else {
            cell.role = TeletextBodyRole::BackgroundOnly;
            TeletextSemanticCell neutral;
            neutral.column = static_cast<uint8_t>(column);
            neutral.kind = TeletextCellKind::SpacingBlank;
            neutral.background = upper.cells[column].background;
            cell.cell = neutral;
        }
        output.cells[index * kTeletextBodyColumns + column] = cell;
    }
}
}  // namespace

TeletextBody compose_teletext_body(const TeletextBodyInput& input) {
    TeletextBody output;
    output.issues = BodyNoIssue;
    TeletextBodyCoverage incoming = TeletextBodyCoverage::Own;
    for (std::size_t index = 0; index < kTeletextBodyRows; ++index) {
        auto& row = output.rows[index];
        row.row = static_cast<uint8_t>(index + 1);
        row.incoming = incoming;
        if (incoming == TeletextBodyCoverage::Covered) {
            // Do not inspect even present/source metadata on suppressed input.
            row.candidate = TeletextBodyCandidate::NotEvaluated;
            row.next = TeletextBodyCoverage::Own;
            paint_lower(output, index, row);
        } else {
            evaluate_source(input[index], row);
            row.next = next_coverage(incoming, row.candidate);
            if (incoming == TeletextBodyCoverage::Own &&
                (row.candidate == TeletextBodyCandidate::No ||
                 row.candidate == TeletextBodyCandidate::Yes))
                paint_own(output, index, row);
            else
                paint_unknown(output, index, row);
        }
        output.issues |= row.effective_issues;
        incoming = row.next;
    }
    if (incoming == TeletextBodyCoverage::Own)
        output.boundary = TeletextBodyBoundary::WithinBody;
    else if (incoming == TeletextBodyCoverage::Covered)
        output.boundary = TeletextBodyBoundary::OutOfBody;
    else
        output.boundary = TeletextBodyBoundary::Uncertain;
    output.has_unknown_geometry = false;
    for (const auto& cell : output.cells) {
        if (!cell.geometry_known) {
            output.has_unknown_geometry = true;
            break;
        }
    }
    output.layout_complete = !output.has_unknown_geometry &&
                            output.boundary == TeletextBodyBoundary::WithinBody;
    return output;
}
}
