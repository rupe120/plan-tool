---
title: Roadmap Revision Retention
intent: A reader of a revised roadmap can see, from the artifact alone, what a removed
  row said, what a closed review request asked for and how it was answered, and which
  decision drove a drop — without reading git.
status: planning
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
steps:
- id: 1
  title: Add the removed row's content snapshot to RemovalRecord, populated mechanically
    from the predecessor's own rendered row content — never model-authored — rendered
    back on every artifact rewrite, and give `check_design_row_continuity` a
    tampering-specific branch so an edited (not fabricated) carried removal is
    rejected with a message naming the changed field and telling the model to
    revert it, not drop the record, and add a dropped-removal check mirroring
    `check_feedback_integrity`'s dropped-feedback loop so a carried removal
    silently omitted from a reply is rejected too, not just an edited one
  intent: So a reader of a revised roadmap can see what the dropped row actually said
    instead of having to go read git, with no faithfulness question to gate because
    the render layer derives the snapshot rather than the model paraphrasing it, an
    accidental edit to a carried removal gets a correction the model can act on, and
    a carried removal cannot simply vanish from a reply either.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_gates.py
  - plan_tool/roadmap_view.py
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap_gates.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Add the optional decision reference to RemovalRecord, render it back, check
    it names a decision the artifact declares, and add it to the revision prompt's
    removals field list and worked example as a model-suppliable field
  intent: So a removal can point at the decision whose rejected alternatives explain
    the drop, instead of leaving the reasoning stranded in a separate collection —
    and so the model actually knows the field exists to supply it.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_gates.py
  - plan_tool/prompts/roadmap-revision.md
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap_gates.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Lands the omit-when-absent render idiom on _removal_mapping, the parse-unchanged
      back-compat cases this second field reuses, and the tampering-specific branch
      in check_design_row_continuity — step 2 extends that same branch to compare
      decision_reference too, rather than building a second one.
- id: 3
  title: Add `closed` to FeedbackState with a `_ANSWERED_FEEDBACK_STATE` self-mapping
    (so a carried closed row's lookup doesn't raise `KeyError` and crash the revision),
    and update the dropped-feedback gate's violation message and the revision
    prompt's state enum, carry-forward instruction, and "never do" text — all three
    currently say the only close is deleting the row
  intent: So a reviewer can retire a feedback request by setting its `state` field
    to `closed` in the file instead of deleting it, and the record of what was
    asked and how it was answered stays in the artifact; a reviewer keeps full
    deletion rights over any row, closed included, so this retention binds only
    the model's own edits, never the reviewer's.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_gates.py
  - plan_tool/prompts/roadmap-revision.md
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap_gates.py
  - tests/test_roadmap.py
  complexity: high
  change_type: feature
- id: 4
  title: Add a deterministic, stable closed-last sort to the `feedback` render layer,
    so any write — model-emitted or a reviewer's own hand-edit later picked up by
    any tool-driven write — always leaves closed rows after every non-`closed`
    row, with no gate and no model-facing prompt guidance needed
  intent: So the live part of the review queue reads first and retained closed rows
    accumulate at the end instead of interleaving with open requests, guaranteed
    on every ordinary revision run rather than only when the model happens to emit
    rows in order (see `## Architecture` for the named structural-revision gap
    this does not cover).
  files:
  - plan_tool/roadmap_artifacts.py
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Mints FeedbackState.CLOSED and makes a closed row legal to carry — there is
      nothing to order last until closed rows can exist.
- id: 5
  title: 'Count closed rows in the `--mode history` summary (`_summary_feedback_counts`
    / `render_roadmap_summary`, roadmap_view.py) and update the post-run summary''s
    close guidance (`_feedback_summary_lines`, cli/roadmap_cmd.py) to say closing
    sets `state: closed` rather than deleting — the post-run summary reports no
    per-state counts today (`RoadmapResult` has no closed accumulator, only the
    scalar `feedback_awaiting_review`) and adding one would touch the `run_roadmap`
    orchestrator, out of scope per BACKLOG #242, so it keeps reporting only that
    existing scalar'
  intent: So the two hand-written state lists an operator actually reads stop disagreeing
    with the state vocabulary the parser accepts — fully on the renamed `--mode
    history` view, whose whole rationale is surfacing retained history, and on the
    post-run summary's guidance text without touching the orchestrator to add a
    count it doesn't have today.
  files:
  - plan_tool/roadmap_view.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap_view.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: 'Adds the CLOSED member these two surfaces must report, and settles that setting
      `state: closed` is the supported close so the CLI guidance can name it.'
- id: 6
  title: Rename `--mode review` to `--mode history` everywhere it appears — the argparse
    choices, MODE_REVIEW's branch sites and docstrings in roadmap_view.py (including
    its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text,
    plan_tool/cli/__init__.py's package-level `--help` catalog docstring (and the
    golden snapshot pinning it), and every literal `--mode review` example in
    README.md, docs/how-to/roadmap.md, and docs/ARCHITECTURE.md — dropping
    the `review` spelling with no alias
  intent: So the flag says what the mode shows now that the collections it surfaces
    retain history rather than only pending review work, and no operator-facing
    text anywhere — including the top-level `plan-tool --help` catalog — still
    tells someone to pass a value the parser now rejects. This sweep is scoped to
    the roadmap `--view ... --mode {current,review}` flag only — `run --mode
    <review>` / `verify-all --mode <m>`'s unrelated per-step audit primitive
    (check/optimize/document/test/security/lint) shares no code and stays
    untouched even where it appears near this flag's own documentation in the
    same files. `docs/cli/roadmap.md` is generated from the live argparse
    parser and drift-guarded by
    `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_every_generated_file_matches_disk`;
    regenerate it with `python -m plan_tool.cli_reference --write` after the
    parser change rather than hand-editing it.
  files:
  - plan_tool/roadmap_view.py
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/cli/__init__.py
  - docs/cli/roadmap.md
  - README.md
  - docs/ARCHITECTURE.md
  - docs/how-to/roadmap.md
  - integrations/claude/SKILL.md
  - tests/test_roadmap_view.py
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/package_surface_help.golden.txt
  complexity: medium
  change_type: refactor
  depends_on:
  - 5
- id: 7
  title: Document the removal snapshot, the decision reference, and the `closed` state
    (including the closed-last ordering rule) in ROADMAP_FORMAT.md, describing
    both setting `state` to `closed` and the still-valid plain-deletion path
    rather than replacing one with the other — correcting all five sites that
    currently say deletion is the only close (the schema block's `state`
    comment, the Closed vocabularies table, the feedback-lifecycle's situation
    5, the worked example near "## Decisions", and
    `check_feedback_integrity`'s gate-documentation table row,
    which also needs "or `closed`" added to its "carried in `awaiting-review` or
    `deferred`" language) — correct RUNBOOK.md's close-request table row the same
    dual-option way, plus its "Preserved by the gates" table, and correct README.md's
    and docs/how-to/roadmap.md's close-by-deleting prose to name both options
    too — and add a feedback-state vocabulary-completeness test to
    tests/test_roadmap_format.py mirroring
    `test_hosting_schema_documents_the_complete_gate_owned_vocabulary` /
    `test_store_schema_documents_the_complete_gate_owned_vocabulary`, since no such
    guard exists today for FeedbackState
  intent: So the review collections' schema is readable without opening the parser,
    which is what the whole FORMAT-doc family exists to guarantee, so a reviewer
    who trusts RUNBOOK.md, README.md, or the walkthrough learns the retention path
    exists without losing the still-valid deletion option, and so the two most-read
    operator docs stop contradicting the shipped `closed` state.
  files:
  - ROADMAP_FORMAT.md
  - RUNBOOK.md
  - README.md
  - docs/how-to/roadmap.md
  - tests/test_roadmap_format.py
  complexity: high
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  - 4
  depends_on_notes:
    1: Mints the snapshot field's wire key and its render idiom; the doc records the
      name that actually landed, not the one this plan proposed.
    2: Mints the decision-reference wire key and its resolution rule for the relations
      table.
    3: Mints the `closed` literal that test_every_closed_vocabulary_literal_the_doc_prints_is_real
      checks the FeedbackState table against.
    4: Settles where the ordering rule is enforced, which decides whether it is documented
      as a shape rule or a relation rule.
- id: 8
  title: Update BACKLOG #242 to reflect this plan's shipment
  intent: So the backlog stops advertising work that shipped. docs/ARCHITECTURE.md
    needs no change here — its "twenty-eight relation gates" count stays accurate
    (the tampering and dropped-removal checks land as branches inside the existing
    `check_design_row_continuity`, not new top-level `check_*` gates) and it carries
    no close-by-deleting claim to correct; only "feedback rows and their text are
    the reviewer's" mentions feedback, and it stays true unchanged.
  files:
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 6
  - 7
  depends_on_notes:
    6: Lands the last behavior change, so the backlog entry can be marked shipped
      or left with an accurate deferred remainder.
    7: Lands the last documentation change; step 8 is the plan's final step and
      waits for both branches (6 and 7, which together transitively cover 1-5)
      to close before touching BACKLOG.md.
---
# Roadmap Revision Retention

## Overview

Three additive changes to the shared review-collection shape:

- `RemovalRecord` gains a content snapshot — the removed row's rendered
  content as it stood at removal.
- `FeedbackState` gains `closed`; closed rows are retained in the `feedback`
  collection — never deleted by the model — and render last within it. A
  reviewer, editing the file directly before a run, keeps full deletion
  rights over any row, closed included, exactly as today; retention binds
  only the model's own edits.
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
The shipped hosting/store schema's precedent (fields on existing rows, not a
fifth artifact) keeps
retention in the one place `check_feedback_integrity` and
`check_design_row_continuity` already resolve `feedback`/`removals` against —
a second collection would mean two places to look for a feedback id.

**The snapshot is mechanically captured, never model-authored.** When a
removal is newly declared — its `removed_id` not yet in `carried` — the
render layer copies the predecessor's own rendered content for that row
into the snapshot before the artifact is written; the model supplies only
`removed_id`, `rationale`, and `feedback_ids`, exactly as it does today, and
step 1 makes no prompt change. This is why `## Not allowed`'s ban on a
faithfulness gate is safe: there is no faithfulness question to gate,
because the snapshot is derived from the row's own last-known-good render
rather than paraphrased. It stays inside BACKLOG #242's "no orchestrator
change" boundary because the capture is a render-time transform in
`roadmap_artifacts.py`, not a change to `roadmap.py`'s stage-running
orchestrator.

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

A tampered carried removal — one field edited, so it no longer matches
`carried` — currently re-trips `check_design_row_continuity`'s
`VIOLATION_REMOVAL_WITHOUT_A_PREDECESSOR_ROW`, whose message says to drop
the record. That is the right remedy for a genuinely fabricated removal but
the wrong one here: dropping the record does *not* land safely — the row
it names cannot be in `predecessor`'s declared design rows (a row and its
own removal record can never coexist there, per
`VIOLATION_REMOVAL_NAMES_A_PRESENT_ROW`), so `VIOLATION_DROPPED_DESIGN_ROW`
never sees it either. The drop instead falls straight into the gap the next
paragraph names — a dropped removal that trips nothing at all — which is
exactly why step 1 ships the tampering branch and the dropped-removal check
together rather than the tampering branch alone. This check needs
a tampering-specific branch — distinguishing an exact-match absence (no
predecessor record with this `removed_id` at all) from a near-match one (a
predecessor record with the same `removed_id` but a different field) — with
the near-match message telling the model to revert the edited field, not
drop the record.

**A carried removal record must survive a revision the same way a carried
feedback row must — today nothing enforces that.**
`check_design_row_continuity` only validates removals *present* in the
candidate against `carried`; it never loops over `predecessor.removals` the
way `check_feedback_integrity` loops over `predecessor.feedback` to catch a
dropped row. The check's own docstring ("the model may never drop a carried
removal") and `prompts/roadmap-revision.md`'s "never delete or prune a
`removals` record" both assert this already, but no gate backs either claim:
a model that simply omits a carried removals record from its reply passes
every existing check. Before this plan that meant losing three thin fields;
once the snapshot and decision reference exist, the same silent omission
loses exactly the content this plan exists to retain. Step 1 adds a
dropped-removal check mirroring `check_feedback_integrity`'s pattern — a
predecessor removal absent from the candidate is rejected, naming the
record — closing this gap as part of the same re-check BACKLOG #242's own
Risks section already calls for on this gate.

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

Eleven sites total currently say "close by deleting the row," and none is
claimed twice: `check_feedback_integrity`'s `VIOLATION_DROPPED_FEEDBACK`
message and `prompts/roadmap-revision.md`'s carry-forward instruction and
"never do" text are step 3's (3 sites); the run/revision post-run summary's
CLI guidance (`_feedback_summary_lines`) is step 5's, text-only (see step
5's note below) (1 site); and step 7 owns the remaining seven —
README.md's and `docs/how-to/roadmap.md`'s prose descriptions of
closing a feedback row (2 sites), plus five inside `ROADMAP_FORMAT.md`:
situation 5, the schema `state` comment, the Closed vocabularies table, a
worked example near "## Decisions", and `check_feedback_integrity`'s own
gate-documentation table row, whose "carried in `awaiting-review` or
`deferred`" language needs "or `closed`" added now that the check is
state-generic past `open`.

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

**A `decision_reference` can itself go stale, and that is recoverable
rather than broken.** The referenced `DecisionRow` is an ordinary design row
unless `settled`, so it can be dropped by its own removal record like any
other row. Because carried removal records are immutable and never
re-judged (above), no gate re-validates an older removal's
`decision_reference` after the decision it names is later removed. A reader
who finds a `decision_reference` naming nothing in `artifact.decisions`
should look for that id's own removal record — carrying its own snapshot
once step 1 ships — rather than read the reference as broken.

**Model-authored fabrication of a whole row or record is
`roadmap.py:_authored_review_rows`'s job (line 1225), not a new check — and
the backlog's citation of `_invented_review_rows` is stale; no symbol of
that name exists.** It already refuses an invented feedback row or a
removal record with no predecessor, ahead of every gate. Retention adds no
new fabrication case: a model-invented `closed` state or decision reference
on a *carried* record is caught by the field-level checks above, and this
function stays unchanged.

**No existing mechanism orders the `feedback` collection at all, and the
ordering rule is a deterministic render-time sort, not a model-facing
gate.** Every artifact's `feedback` tuple is plain parse/insertion order
(`roadmap_artifacts.py:528,541,595,645`), and `_review_mappings`
(`roadmap_artifacts.py:1815-1832`) renders whatever order the tuple holds.
Making the render layer stable-sort closed rows last on every write —
mirroring step 1's mechanical-snapshot precedent — is strictly better than a
gate that rejects a misordered model reply: it guarantees the invariant on
every ordinary parse/render round-trip, including after a reviewer's own
hand-edit that leaves a `closed` row mid-list (the artifact self-corrects
the next time an ordinary revision run re-renders it, rather than staying
out of order until that happens), and it needs no prompt guidance telling
the model how to order rows it emits. Step 4 adds this sort to the render
layer; it adds no gate and rejects nothing.

**This guarantee is not unconditional — it does not cover the structural-
revision family of consumers, and this plan does not resolve that gap.**
`roadmap_impact_snapshot.py:_capture_artifact` and
`roadmap_structural_revision_patch.py` (`_require_preflight`,
`_parse_canonical_candidate`) all require the on-disk artifact to already
be render-canonical — literal on-disk bytes equal `render(parse(bytes))` —
and raise rather than re-render when it is not; none of the three re-renders
before comparing. Once `render()` sort-corrects closed-row order, an
artifact where a reviewer hand-set a `closed` row mid-list (exactly the
case this plan makes legitimate) is non-canonical until an ordinary
revision run next touches it — and any of these three consumers, structural
revision included, rejects it outright in the meantime rather than
self-correcting. Resolving this means changing capture/canonicality
behavior inside the already-completed, protected structural-rewrite-safety
arc (see `docs/implementation-plans/backlog-arcs/backlog-arc-structural-
rewrite-safety.md`: "do not reopen"), which this plan's scope fence does not
authorize on its own. This is a known, named gap — see `## Risks` — not a
silent omission.

## Not allowed

No gate, finding, or prompt directive in this effort may assert any of these.
A proposal for one is a scope violation, not a deferral:

- whether a removal's snapshot faithfully represents the dropped row,
  whether a closed row's `proposed_response` actually answers its
  `request`, or whether a decision reference is the right decision for a
  removal — every one of the three new checks this plan adds stays a
  presence/equality/membership check, never a content judgment.
- restoring a removed row from its snapshot, or any mechanism treating the
  snapshot as more than what a reader needs to recognize what was lost.
- a retention cap, pruning policy, or archive rotation for `feedback` or
  `removals`.
- reading git from any roadmap code path, or any revision numbering,
  timestamp, or per-row revision attribution.
- widening `check_design_row_continuity`'s `pinned_by_anchor` refusal, or
  any other gate behavior, beyond what the decision reference concretely
  makes tractable, per `## Risks`.
- any new exit-code flip — a stage that fails these gates retries with its
  violations quoted back, exactly as the shipped gates do.

## References

- [dataclasses — Data Classes (Python 3 documentation)https: — Reference for frozen dataclasses, generated `__eq__` semantics, optional field defaults and ordering rules, and `replace()` — the exact mechanics the removal carry-identity (whole-record equality) and the back-compat-safe new `RemovalRecord` fields depend on.
- [enum — Support for enumerations (Python 3 documentation)https: — Canonical rules for enum member definition, values, aliasing, and lookup, needed when adding `FeedbackState.CLOSED` to an existing enum without disturbing parse or comparison behavior.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2https: — The primary YAML spec, in particular literal (`|`) and folded (`>`) block scalars and chomping — required to store a removed row's multi-line rendered-content snapshot in frontmatter so it round-trips through parse and render.
- [PyYAML Documentationhttps: — Library reference for the project's YAML dependency, covering `safe_load`/`dump`, `default_flow_style`, key ordering, and scalar-style emission — the behaviors that determine whether the new fields serialize stably and older artifacts keep parsing unchanged.
- [argparse — Parser for command-line options, arguments and subcommandshttps: — Reference for `choices` and the 3.13+ `deprecated=True` option flag, relevant to renaming `--mode review` to `--mode history` on the roadmap view surface.
- [How to parametrize fixtures and test functions — pytesthttps: — Official guide to `@pytest.mark.parametrize` and parametrized fixtures, the pattern for asserting the new fields and states uniformly across all four staged artifact classes and each re-checked gate.
- [Sorting Techniques (Python HOWTO)https: — Documents `sorted`/`list.sort` key functions and the stability guarantee, which is what lets 'closed rows render last' be implemented without perturbing the existing parse/insertion order of the remaining feedback rows.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- `roadmap-view`'s rendering of the new fields — a removals-with-content
  section, a resolved-feedback section — filed separately if a real reader
  need emerges once the data exists.
- Migrating or backfilling any existing on-disk roadmap. An artifact
  predating this change has no snapshot, no closed rows, and no decision
  references, and stays valid exactly as it parses today.
- Any diff or compare-two-revisions surface.
- Any interaction between the new fields and the existing `hosting`/`stores`
  blocks — unrelated schema regions with no shared row.
- Changing how `--from-stage` re-entry works, or anything about seed
  drafting or `--apply`.
- Any change to `roadmap_impact_snapshot.py` or
  `roadmap_structural_revision_patch.py`'s render-canonicality checks. The
  closed-last sort's gap against these consumers (`## Risks`) is named, not
  resolved, here — the structural-rewrite-safety arc is complete and
  protected, and reopening it needs a separate, explicit decision.

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
- **Unbounded artifact growth.** Every closed row and every removal
  snapshot accumulates in the artifact forever — no cap, pruning policy, or
  archive rotation ships (`## Not allowed`). This is an accepted
  consequence of the retention Outcome, matching BACKLOG #242's own
  framing; revisit only with real evidence of growth becoming a problem,
  not preemptively.
- **The closed-last render sort does not cover the structural-revision
  family of consumers.** `roadmap_impact_snapshot.py` and
  `roadmap_structural_revision_patch.py` require the on-disk artifact to
  already be render-canonical and reject rather than re-render when it is
  not, so an artifact where a reviewer hand-set a `closed` row mid-list
  stays rejected by these consumers until an ordinary revision run
  re-renders it first. Resolving this touches the completed, protected
  structural-rewrite-safety arc's canonicality checks, which this plan does
  not authorize itself to change — see `## Architecture` and `## Out of
  scope`. Flagged for the operator to decide: fold a fix into this plan,
  scope a separate plan against the structural-rewrite-safety arc, or
  accept the gap.

## Testing

Hermetic, fixture-driven, stubbed invokers — the arc's existing pattern.
What would prove the Outcome: an artifact written before this change (no
snapshot, no `closed` feedback, no decision reference) parses unchanged —
asserted by mutation, not by reading (CLAUDE.md § Tests); a removal's
snapshot round-trips through parse and render; a `closed` feedback row
survives a revision unrelated to it and renders after every non-`closed`
row in the `feedback` collection; an artifact whose `feedback` collection
has a `closed` row before a non-`closed` row — however it got that way —
renders stable-sorted closed-last the next time an ordinary revision run
re-renders it, with the relative order among non-`closed` rows and among
multiple `closed` rows otherwise preserved; a revision that sets any row to
`closed`, edits a carried removal's snapshot or decision reference, or
omits a carried removal record entirely, is rejected naming the field or
record, by the existing carry/state checks generalized in `## Architecture`;
a `closed` row moved to any other state is rejected; a `closed` row's
`proposed_response` changing between predecessor and revision is rejected by
the same check that already rejects an altered `deferred`/`awaiting-review`
response; and each of the three re-checked gates keeps its current behavior
on artifacts using none of the new fields.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (refactor) — tests covering the behavior this step changes; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 8 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A removal record's snapshot, once carried, round-trips unchanged through
  parse and render on an artifact that made no other change to that record.
- A `closed` feedback row persists across a revision that touches unrelated
  rows, and renders after every non-`closed` row in the `feedback`
  collection.
- An artifact whose `feedback` collection has a `closed` row before a
  non-`closed` row is rendered with closed rows stable-sorted last the next
  time an ordinary revision run re-renders it — a deterministic sort, not a
  rejection — with the relative order among non-`closed` rows, and among
  multiple `closed` rows, otherwise preserved. The structural-revision
  family of consumers is not covered by this guarantee (`## Risks`).
- The model may not set any feedback row to `closed`; a revision that does
  is rejected, naming the row.
- The model may not alter a carried removal's snapshot or decision
  reference; a revision that does is rejected, naming the record, with a
  message telling the model to revert the tampered field rather than drop
  the record.
- The model may not omit a carried removal record from a revision either; a
  revision that does is rejected, naming the missing record — the same
  protection `check_feedback_integrity` already gives a carried feedback
  row.
- A newly declared removal's snapshot is populated from the predecessor's
  own rendered row content, not model-authored text — the model supplies no
  snapshot and the written artifact carries one matching the dropped row's
  prior render.
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
