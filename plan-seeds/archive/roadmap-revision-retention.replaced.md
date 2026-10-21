> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-revision-retention.md`.
> Preserved here for history; do not edit.

# Roadmap revision retention: removal content, closed feedback, decision links

Seed for BACKLOG **#242**. Extends the `feedback`/`removals` review
collections every staged artifact already carries (`DomainArtifact`,
`ConstraintsArtifact`, `ComponentsArtifact`, `PlansArtifact` —
`plan_tool/roadmap_artifacts.py:515-649`). Not a new arc position and mints
no new artifact — see `## Architecture`. The resulting plan updates
`BACKLOG.md` (#242) in its final docs step.

## Outcome

A reader of a revised roadmap can see, from the artifact alone, what a
removed row said, what a closed review request asked for and how it was
answered, and which decision drove a drop — without reading git.

## Overview

Three additive changes to the shared review-collection shape:

- `RemovalRecord` gains a content snapshot — the removed row's rendered
  content as it stood at removal.
- `FeedbackState` gains `closed`; closed rows are retained in the `feedback`
  collection (never deleted) and render last within it.
- `RemovalRecord` gains an optional reference to the `DecisionRow` whose
  `rejected_alternatives` explain the drop.

All three are optional and back-compat only: every roadmap on disk today has
removals with no snapshot and feedback with no `closed` row, and must keep
parsing unchanged.

## Problem statement

Three structural losses, each confirmed at HEAD:

- **A removal keeps no content.** `RemovalRecord` is exactly `removed_id`,
  `rationale`, `feedback_ids` (`roadmap_artifacts.py:502-511`). Nothing
  renders the dropped row's content anywhere — `_removal_mapping`
  (`roadmap_artifacts.py:1747-1753`) emits only those three keys, and
  `ROADMAP_FORMAT.md`'s `removals:` schema (`ROADMAP_FORMAT.md:495-529`)
  documents nothing more. The row's name, statement, fields, and edges
  survive only in git.
- **Closing feedback deletes it.** `FeedbackState` has exactly `open`,
  `awaiting-review`, `deferred` (`roadmap_artifacts.py:229-239`). A reviewer
  resolves a row only by deleting it before a run — the CLI's own guidance
  says so verbatim (`cli/roadmap_cmd.py:1610`: "close one by deleting the row
  (git keeps the record)"). Every feedback row that reaches disk is
  unresolved by construction.
- **No removal names its decision.** `DecisionRow.rejected_alternatives`
  (`roadmap_artifacts.py:427-440`, `RejectedAlternative` pairs at 419-423) is
  where reasoning about roads not taken lives, and no field joins a
  `RemovalRecord` to it.

## Architecture

**Shaped as new fields on the existing dataclasses, in the existing
collections — not a new collection, artifact, or arc position.** Matches
#243's precedent (fields on existing rows, not a fifth artifact) and keeps
retention in the one place `check_feedback_integrity` and
`check_design_row_continuity` already resolve `feedback`/`removals` against —
a second collection would mean two places to look for a feedback id.

**Removal-carry identity is whole-record equality, and the new fields join
it — this is what makes the fields' immutability enforceable for free.**
`check_design_row_continuity` treats a removal as carried
(`carried = set(predecessor.removals)`, `roadmap_gates.py:1346`) by
frozen-dataclass equality over every field, and never re-judges a carried
record. Once the snapshot and decision reference exist, they are part of
that identity: a removal is re-judged only when one of its fields differs
from the predecessor's. That is exactly the backlog's stated invariant — "a
carried removal's snapshot and decision reference are not the model's to
edit" — provided the plan writes both fields once, at removal time, and never
asks the model to touch a carried record afterward. No separate
immutability gate is needed for these two fields.

**Closing is a state move, not a deletion — the existing dropped-feedback
check already protects a closed row once it stops needing to be deleted.**
`check_feedback_integrity`'s `VIOLATION_DROPPED_FEEDBACK`
(`roadmap_gates.py:1481`) already fires whenever any predecessor feedback
row is absent from a revision. Once "closing" means the reviewer sets
`state: closed` in the file before a run, rather than deleting the row, a
closed row simply stays present and this check keeps protecting it
unchanged. Two things do need to change: `_ANSWERED_FEEDBACK_STATE`
(`roadmap_gates.py:1406`) needs a `FeedbackState.CLOSED: FeedbackState.CLOSED`
self-mapping — the same shape `DEFERRED` already has — so the model may
carry a closed row forward but never move it out of `closed`; and
`_feedback_summary_lines`'s CLI text (`cli/roadmap_cmd.py:1610`) needs its
"close one by deleting the row" guidance replaced. The carried-response
equality check just below that mapping is already state-generic past
`OPEN` and needs no change — it will compare a `closed` row's
`proposed_response` for equality the same way it already does for
`deferred`/`awaiting-review`.

**The settled-decision-anchor refusal a decision reference might interact
with lives in `check_design_row_continuity`, not `check_settled_decisions` —
the backlog entry's own citation is wrong and the plan must ground itself
against the right block.** `check_settled_decisions`
(`roadmap_gates.py:1606`) only pins a settled decision row's own id, status,
chosen option, and anchor. The refusal to drop the row a settled decision
*anchors to* — "a settled decision pins its anchor, so this row may not go,
with or without a removal record," reported whether or not a removal record
covers the drop — is `check_design_row_continuity`'s `pinned_by_anchor`
block (`roadmap_gates.py` 1298, 1309-1328). Any question of whether a
decision reference makes that refusal tractable is a question about this
block specifically.

**Model-authored fabrication of a whole row or record is
`roadmap.py:_authored_review_rows`'s job (line 1225), not a new check — and
the backlog's citation of `_invented_review_rows` is stale; no symbol of
that name exists.** It already refuses an invented feedback row or a
removal record with no predecessor, ahead of every gate. Retention adds no
new fabrication case: a model-invented `closed` state or decision reference
on a *carried* record is caught by the field-level checks above, and this
function stays unchanged.

**No existing mechanism orders the `feedback` collection at all.** Every
artifact's `feedback` tuple is plain parse/insertion order
(`roadmap_artifacts.py:528,541,595,645`), and `_review_mappings`
(`roadmap_artifacts.py:1815-1832`) renders whatever order the tuple holds.
"Closed rows ordered last" is new behavior authored from scratch, not an
extension of something that already sorts — the plan must decide where the
ordering is enforced (render time, or a structural invariant a gate checks)
and that decision belongs to `create`/`detail`, not this seed.

## Scope of work

- The removal snapshot field and the optional decision reference on
  `RemovalRecord`, and the `FeedbackState.CLOSED` member, in
  `plan_tool/roadmap_artifacts.py` — parse, render (`_removal_mapping`,
  `_feedback_mapping`), and back-compat-safe defaults. Name the two new
  `RemovalRecord` fields following the codebase's existing `_id`/`_ids`
  reference-suffix convention for the decision reference.
- `_ANSWERED_FEEDBACK_STATE`'s `CLOSED` self-mapping and the closed-last
  ordering rule for the `feedback` collection, in `plan_tool/roadmap_gates.py`.
- Re-checking `check_design_row_continuity`, `check_feedback_integrity`, and
  `check_settled_decisions` against the new fields/state, per
  `## Architecture` — including whether `check_design_row_continuity`'s
  `pinned_by_anchor` refusal becomes tractable given a decision reference.
- The stage prompts' review-collection instructions, and
  `_feedback_summary_lines`'s CLI guidance text (`cli/roadmap_cmd.py:1610`).
- `ROADMAP_FORMAT.md`'s review-collections schema (`## The review
  collections`, currently `ROADMAP_FORMAT.md:495-529`).
- The `--mode review` → `--mode history` rename (`MODE_REVIEW = "review"`,
  `plan_tool/roadmap_view.py:449`) and its CLI surface — a naming correction
  on an existing flag, not new rendering; see `## Not allowed`.
- `tests/test_roadmap_artifacts.py`, `tests/test_roadmap_gates.py`,
  `tests/test_roadmap_format.py`, and the `--mode` rename's existing tests.

## The binary observables

A carried removal record equals its predecessor's exactly, field for field,
wherever the model has not fabricated a new one; a `closed` feedback row
present in the predecessor and absent from the revision is
`VIOLATION_DROPPED_FEEDBACK`, exactly as any other absent predecessor row is
today; a feedback row whose predecessor state is `closed` and revision
state is anything else is `VIOLATION_DISALLOWED_FEEDBACK_STATE`; a
`closed` row's `proposed_response` changing from its predecessor's is
`VIOLATION_ALTERED_CARRIED_RESPONSE` — the same checks these gates already
run for `deferred`, extended by one member. Set membership and equality —
nothing else.

## Not allowed — enumerated, not implied

No gate, finding, or prompt directive in this effort may assert any of
these. A proposal for one is invalid, not deferrable:

- whether a removal's snapshot **faithfully represents** the dropped row,
  whether a `closed` row's `proposed_response` **actually answers** its
  `request`, or whether a decision reference is the **right** decision for a
  removal — recorded and gated for presence/equality only, never content;
- restoring a removed row from its snapshot, or any mechanism treating the
  snapshot as more than what a reader needs to recognize what was lost — the
  snapshot is the row's **rendered content**, never a structured,
  re-parseable copy (per `## Deferred`);
- a retention cap, pruning policy, or archive rotation for `feedback` or
  `removals`;
- reading git from any roadmap code path, or reconstructing revision
  numbers, timestamps, or per-row revision attribution — the backlog's own
  rejected alternative, not reopened here;
- the model authoring or moving any row into `closed`, or editing a carried
  removal's snapshot or decision reference — enforced by the field-level
  checks in `## Architecture`, never loosened;
- any new arc position, fifth artifact, or a second `feedback`/`removals`
  collection;
- any rendering of the new fields beyond what round-trips through
  parse/render — `roadmap-view`'s presentation of them (a removals section
  with content, a resolved-feedback section) is a separate effort with its
  own fence, not this one's to design;
- widening `check_design_row_continuity`'s `pinned_by_anchor` refusal, or
  any other gate behavior, beyond what the decision reference concretely
  makes tractable — if it does not make the refusal tractable, the refusal
  stays exactly as it is today;
- any new exit-code flip. A stage that fails these gates retries with its
  violations quoted back, exactly as the shipped gates do.

## Out of scope

- `roadmap-view`'s rendering of the new fields — a removals-with-content
  section, a resolved-feedback section — filed separately if a real reader
  need emerges once the data exists.
- Migrating or backfilling any existing on-disk roadmap. An artifact
  predating this change has no snapshot, no closed rows, and no decision
  references, and stays valid exactly as it parses today.
- Any diff or compare-two-revisions surface.
- Any interaction between the new fields and #243's `hosting`/`stores`
  blocks — unrelated schema regions with no shared row.
- Changing how `--from-stage` re-entry works, or anything about seed
  drafting or `--apply`.

## Allowed behavior changes

The `removals` collection gains an optional content snapshot and an
optional decision reference, on every artifact that carries it; `feedback`
gains a `closed` state, and closed rows are retained (never deleted) and
render last within the collection; `--mode review` becomes
`--mode history`. No change to stage ordering, filenames, numbering,
`--from-stage` re-entry, seed drafting, `--apply`, or any gate's exit-code
behavior.

## Allowed reorganization

None beyond the `--mode` rename named above.

## Risks

- **Ceremony on a stage that has never closed anything.** Mitigation:
  `closed` is a reviewer-only move made in the editor before a run, exactly
  like the existing `deferred`/reopen moves — no new prompt obligation lands
  on the model.
- **The carry-identity coupling this design leans on.** If a later need
  arises to correct a carried removal's snapshot or decision reference in
  place, whole-record equality makes that indistinguishable from a
  fabricated new removal. This is a known sharp edge to note, not a defect
  to solve here.
- **`check_design_row_continuity` re-examination.** Only reopen the
  `pinned_by_anchor` refusal if a decision reference genuinely resolves the
  un-settle instruction that block's message already gives the reviewer;
  otherwise leave it untouched, per `## Not allowed`.
- **The feedback-ordering rule has no existing hook**, per `## Architecture`
  — treating it as "add one more enum member" is the likeliest source of an
  incomplete first pass.

## Testing

Hermetic, fixture-driven, stubbed invokers — the arc's existing pattern.
What would prove the Outcome: an artifact written before this change (no
snapshot, no `closed` feedback, no decision reference) parses unchanged —
asserted by mutation, not by reading (CLAUDE.md § Tests); a removal's
snapshot round-trips through parse and render; a `closed` feedback row
survives a revision unrelated to it and renders after every non-`closed`
row in the `feedback` collection; a revision that sets any row to `closed`,
or edits a carried removal's snapshot or decision reference, is rejected
naming the field, by the existing carry/state checks generalized in
`## Architecture`; a `closed` row moved to any other state is rejected; a
`closed` row's `proposed_response` changing between predecessor and
revision is rejected by the same check that already rejects an altered
`deferred`/`awaiting-review` response; and each of the three re-checked
gates keeps its current behavior on artifacts using none of the new fields.

## Acceptance criteria

- A removal record's snapshot, once carried, round-trips unchanged through
  parse and render on an artifact that made no other change to that record.
- A `closed` feedback row persists across a revision that touches unrelated
  rows, and renders after every non-`closed` row in the `feedback`
  collection.
- The model may not set any feedback row to `closed`; a revision that does
  is rejected, naming the row.
- The model may not alter a carried removal's snapshot or decision
  reference; a revision that does is rejected, naming the record.
- A `closed` row's `proposed_response` changing between predecessor and
  revision is rejected, by the same check that already rejects an altered
  `deferred`/`awaiting-review` response.
- An artifact written before this change parses unchanged, with no snapshot
  on any removal, no `closed` feedback rows, and no decision references.
- `ROADMAP_FORMAT.md`'s review-collections section documents the new
  fields, the `closed` state, and the ordering rule, and
  `tests/test_roadmap_format.py` holds it to the shipped constants.
- The `roadmap` view surface accepts `--mode history` and no longer exposes
  `--mode review`.
- `BACKLOG.md`'s #242 entry is updated once the plan ships — marked shipped,
  or left with an accurate deferred remainder, per the plan's final docs
  step.

## Deferred

- `roadmap-view`'s rendering of the new fields.
- Migrating or backfilling any existing on-disk roadmap.
- Any second `--mode` surface change beyond the `review` → `history` rename.
- Re-examining `check_design_row_continuity`'s settled-decision-anchor
  refusal, unless the decision reference is shown during authoring to make
  it tractable.
