# Plan seed: Roadmap Revision Retention

## Outcome

`plan-tool roadmap` will retain the reader-visible evidence a revision resolves:
a removed row's rendered content, a closed feedback row, and an optional
decision reference explaining a removal. Existing roadmap artifacts remain
valid forever without those additions.

## Overview

This is additive schema work for the existing roadmap artifacts. It preserves
the current live feedback queue while keeping completed review context in the
same collection, and it improves what existing readers can render without
adding a new history renderer or reconstructing a repository history.

## Problem statement

`RemovalRecord` currently preserves only an ID, rationale, and feedback IDs, so
a reader cannot see the content that was removed. Closing feedback deletes the
row, so an artifact cannot retain a resolved review request. A removal also has
no optional reference to the decision that motivates it. Git remains useful for
provenance, but these three facts must be readable from the artifact itself.

## Architecture

`RemovalRecord` gains optional rendered-content snapshot and optional decision
reference fields. `FeedbackState` gains `closed`; closed feedback remains in
the existing `feedback` collection after every active row and never participates
in stage guidance. A reviewer may close a row. The model may neither close a
feedback row nor create, edit, or remove historical retention evidence carried
from its predecessor.

Parsers accept all legacy artifacts with the fields absent and render them
without invented data. Existing gates continue to protect design continuity,
feedback integrity, and settled decisions; the implementation evaluates their
new-field interactions without weakening their established behavior. The
existing review-history presentation mode is renamed to `history` only at its
minimum compatibility and documentation surface, because the retained data now
describes more than live review.

## In scope

- Optional removal content snapshot and decision-reference fields, parsing, and
  rendering in the existing roadmap artifact schema.
- Retained `closed` feedback state, deterministic collection ordering, and
  exclusion of closed rows from active stage guidance.
- Continuity, feedback-integrity, and settled-decision gate interactions;
  reviewer-only closure and model immutability of carried retention fields.
- Existing prompts, `ROADMAP_FORMAT.md`, history-mode compatibility surface,
  and mutation-based regression tests for legacy and new artifacts.

## Out of scope

- Required migration fields, revision numbers, timestamps, per-row revision
  attribution, Git reads, diff/history comparison, restoration, or a structured
  restorable copy of removed rows.
- A retention cap, pruning policy, archive rotation, a new artifact/stage, a
  second feedback collection, generic structural operations, or changes to
  `--from-stage` behavior and exit-code conventions.
- A new rendering design; this work adds the retained data that existing readers
  may use and leaves expanded presentation to a separately evidenced request.

## Risks

- **Compatibility break:** required parsing would invalidate every legacy
  roadmap. Every retention field stays optional indefinitely.
- **Historical mutation:** a model reply could rewrite evidence that belongs to
  a prior reviewer decision. Continuity checks reject it by field.
- **Queue confusion:** a closed row could remain in active guidance or reorder
  before unresolved feedback. Ordering and guidance tests make the split
  explicit.
- **Scope expansion:** a snapshot could grow into a restorable schema copy.
  Store rendered content only; stop if typed restoration becomes necessary.

## Testing

Use fixtures written before this change to prove parsing and rendering stay
unchanged with every new field absent. Mutate removal snapshots, decision
references, and feedback state to prove round-trip behavior, closed-row last
ordering, active-guidance exclusion, reviewer-only closure, and rejection of
model edits to carried historical fields. Exercise all three affected gates on
legacy and retained-data artifacts, including the settled-decision refusal.

## Acceptance criteria

- A legacy artifact with no retention data parses and renders exactly as before.
- A removal can retain rendered content and an optional decision reference
  without becoming a restorable object.
- Closed feedback stays in the existing collection after active feedback,
  remains visible to readers, and is excluded from stage guidance.
- A model cannot close feedback or alter carried snapshots or decision
  references; violations name the protected field or row.
- `--mode history` is the compatible name for the existing review-history
  surface, with no new history renderer implied.

## Deferred

If real artifact growth requires caps, pruning, restoration, structured row
snapshots, or a richer historical view, record a separate evidence-backed
request. BACKLOG #242 owns only the additive retained facts above.
