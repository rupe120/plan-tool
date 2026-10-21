> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add the decision ledger view in both modes

## Summary

Adds `render_decision_ledger(loaded: LoadedRoadmap) -> str` to `plan_tool/roadmap_view.py` — the view behind `--view ledger`: every `DecisionRow` across all four artifacts, grouped `settled` / `pending`, each with its `anchor` resolved through step 1's `resolve_id`. Under `mode="review"` the pending group also carries every unclosed `FeedbackRow` from `LoadedRoadmap.feedback_index`, each showing its `request` text beside its `target` resolved through step 1's `resolve_feedback_target` — the one function in this module that can resolve a target through a removal, and this step is its first and, within this plan, only caller. A removal renders exactly there, beside the live feedback row whose target resolved through it, and nowhere else. This is the one view of the three that touches no file at all, not even indirectly: it reads only `LoadedRoadmap`, the same shape step 3's reverse index reads, never `plans_dir`. On green, every decision on disk is accounted for exactly once in both modes, a removal appears only beside the feedback that is still live and resolves through it, a removal whose citing feedback has been closed (deleted) renders in no view, and a settled decision's anchor — gate-protected against ever pointing at a removed row — is shown to be safe by the same uniform resolution path a hand-edited pending decision would fail visibly through.

## Table of Contents

- [Why](#why) — the gap this step closes and the two functions it is the first to actually exercise together
- [Input](#input) — the step 1 and step 2 contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — both edits, no new files
- [Implementation](#implementation) — grouping, anchor resolution, and the review-mode pending join
- [Tests](#tests) — what `tests/test_roadmap_view.py` covers
- [Acceptance criteria](#acceptance-criteria) — observable behavior on green
- [References](#references) — stdlib docs for the pieces this step uses
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences this step's code must respect
- [Deferred](#deferred) — what later steps, and other parts of the codebase, own instead

## Why

After steps 1 and 2, every id can be turned into a label and a roadmap loads off disk into one snapshot that degrades to whatever parsed — but nothing yet rolls up the one row kind the plan's Problem statement singles out as the highest-value gap: 41 `DecisionRow` records (measured on the demo roadmap) scattered across four files with no single list today. `DecisionRow.anchor` is one of the seventeen bare-id fields the plan exists to resolve, and it is on **all four artifacts** — `DOMAIN_ROW_KEYS`, `CONSTRAINTS_ROW_KEYS`, `COMPONENTS_ROW_KEYS`, and `PLANS_ROW_KEYS` all list `decisions` as a row collection, and `roadmap_gates._domain_rows` / `_constraints_rows` / `components_design_rows` / `plans_design_rows` each fold `artifact.decisions` into `design_row_ids` under the `"decision"` kind label. This step is the first to read `.decisions` off all four artifacts together instead of one file at a time.

It is also the first step to give `resolve_feedback_target` a caller. Step 1 built that function specifically to reproduce `plan_tool/roadmap.py:_check_predecessor_review_rows`'s `design_row_ids(artifact) | {removed_id for removal in artifact.removals}` formula — "the review loop's designed success path" per the plan's Architecture — but neither step 3's reverse index nor step 4's walk calls it: step 3 reads `FeedbackTarget.kind` and `.row_id` directly off `loaded.feedback_index`'s rows to build citer edges, and step 4 never touches feedback at all. This step is where a live feedback row's own target actually gets resolved end to end, which is what makes the removals-fallback branch in `resolve_feedback_target` reachable from a render instead of only from step 1's own unit tests.

The plan's Architecture calls this "the view the mode changes most": `current` mode's ledger is decisions only; `review` mode's ledger is where "the reviewer's own `request` text, which is the substance" becomes visible, with a removal beside it "closing the loop, and nowhere else." Two existing CLI-side surfaces already summarize parts of this — `plan_tool/cli/roadmap_cmd.py:_feedback_summary_lines` (a count of `feedback_awaiting_review` plus editing instructions, printed once after a `--apply`/`--from-stage` run) and `_newly_settled_summary_lines` (decision ids a revision settled that the predecessor had not) — but both read a `RoadmapResult` from one just-finished run, not a `LoadedRoadmap` snapshot of a roadmap on disk, and both print counts and ids rather than resolved, joined content. `plan_tool/roadmap_view.py` cannot import `plan_tool.cli.roadmap_cmd` regardless (the one-way chain runs the other way), so there is no consolidation available here — the two surfaces answer "what did this run just do," this step answers "what does this roadmap currently look like," and nothing about either changes.

## Input

This step builds on step 1's resolver and step 2's loaded snapshot and reads no new contract:

- **Step 1** supplies `resolve_id(id, index) -> Resolution` and `design_row_index`, used here to resolve every `DecisionRow.anchor`; `display_label` and `Resolution`'s four `RESOLUTION_*` statuses (`RESOLVED`, `DANGLING`, `AMBIGUOUS`, `ARTIFACT_SCOPE`); and, the function this step is first to call, `resolve_feedback_target(target: FeedbackTarget, index, removals) -> Resolution`. Per step 1's own Implementation, a hit in the removals index resolves via `display_label` on the matched `RemovalRecord` — the tombstone text (`"removed: {removed_id} — {rationale}"`) — so calling `resolve_feedback_target` and printing `.text` is the entire mechanism for rendering "any removal that feedback cited beside it as a tombstone." This step does not walk `RemovalRecord.feedback_ids` itself to find that join; that field is a different, provenance-facing edge (which feedback *asked for* a removal) that step 3's citation map already owns as one of its eleven fields, in the opposite direction from the one this step needs (does this feedback's *own target* resolve through a removal).
- **Step 2** supplies `LoadedRoadmap`: `slug`, `mode`, the four optional parsed artifacts (`domain`, `constraints`, `components`, `plans`), `design_row_index`, `removal_index`, `feedback_index`, `absent`, `unparseable`. Three shape facts drive correctness here:
  - `domain` / `constraints` / `components` / `plans` are **not** mode-gated — each carries its full `.decisions` tuple regardless of `mode`, which is what makes "a pending decision renders in both modes" true by reading these fields directly rather than through any mode-filtered index.
  - `feedback_index` **is** mode-gated: empty under `mode="current"`, and under `mode="review"` a `Mapping[str, tuple[FeedbackRow, ...]]` — plural per key, because step 2 keeps both rows reachable on a cross-artifact feedback-id collision rather than dropping one. This step must flatten `feedback_index.values()` (each value a tuple, possibly of length > 1) to get every live `FeedbackRow`, not assume one row per key.
  - `removal_index` is likewise mode-gated and keyed by `removed_id`; this step never iterates it directly — it reaches removals only through `resolve_feedback_target`'s own removals-fallback branch.
- **`roadmap_gates.check_design_row_continuity`** — the gate this step's anchor resolution relies on being enforced upstream, never re-checked here: "a row a **settled** decision anchors to may not go at all — not even with a cited removal." That is why `resolve_id` (not `resolve_feedback_target`) is the right function for `DecisionRow.anchor` on a gate-clean roadmap: a settled decision's anchor is guaranteed present in `design_row_index`. A **pending** decision carries no such guarantee, so this step's own resolution path must still behave correctly — dangling, not silently resolved — if a hand edit points one at a removed id; it must not add a removals fallback of its own to paper over that case.

## Files (creates vs edits)

- **New files:** none. Step 1 creates both files this step touches.
- **Existing files (edits only):**
  - `plan_tool/roadmap_view.py` — adds `render_decision_ledger` and whatever private per-status/per-decision/per-feedback-row helpers the implementation needs. No new dataclass: this step reuses `Resolution` and `display_label` as-is and needs no new record type of its own.
  - `tests/test_roadmap_view.py` — adds the test functions in § Tests.

## Implementation

**Enumerate decisions off the four artifacts directly, not through `design_row_index`.** `design_row_index` exists to *resolve references*, and decisions are indexed into it (kind `"decision"`) only so something else's anchor can point at one — it is not the right tool for *enumerating* every decision, since it holds every design row kind interleaved under one id-keyed mapping. Instead, walk `loaded.domain`, `loaded.constraints`, `loaded.components`, `loaded.plans` in that stage order, skip whichever is `None` (an absent or unparseable artifact, per step 2's contract), and read each one's `.decisions` tuple in its own source order — the same "stage order, then source order within an artifact" rule step 1's index and step 3's citation map already apply. `DecisionStatus` is a closed two-member vocabulary (`SETTLED`, `PENDING`), so partitioning `.decisions` into exactly two groups by `.status` never leaves a decision unclassified.

**Each decision prints its own fields directly — `chosen_option`, `rationale`, and `rejected_alternatives` (each `RejectedAlternative.option` / `.reason` pair) — never through `display_label`.** `display_label(DecisionRow)` returns `.chosen_option` alone (step 1's one-label-per-kind rule), which is exactly right when some *other* row's reference resolves to a decision, but this step is rendering the decision itself, where the fuller record is the point. The one place this step calls a step 1 function on a decision is its `anchor`: `resolve_id(decision.anchor, loaded.design_row_index).text`, printed beside the decision's own fields. This is deliberately the *same* function every other reference field in this plan resolves through — no removals fallback for a decision anchor, ever. A pending decision hand-edited to anchor a removed id therefore renders `resolve_id`'s own `"⚠ undefined: {id}"` here, which is correct: only a `FeedbackTarget` gets the removals fallback (per the plan's Architecture, "The one id that is not dangling despite resolving to no design row is a feedback `target`"), and a decision anchor reusing that fallback would quietly hide the exact hand-edit the dangling marker exists to surface.

**Under `mode="review"`, the pending group also carries every row `loaded.feedback_index` holds — no `if loaded.mode == ...` branch needed, matching the pattern steps 3 and 4 already establish for reading `LoadedRoadmap`'s mode-gated fields as-is.** `FeedbackState` has no `closed` member, so every row present in a parsed artifact's `.feedback` tuple is, by construction, unclosed — "closing" a row means deleting it from the file, at which point it is simply absent from `feedback_index` and this step never sees it. Flatten `feedback_index.values()` to get the individual `FeedbackRow`s (a value is a tuple even when only one artifact declared that id). For each:

- print `request` — Architecture's own words for this view are "the reviewer's own `request` text, which is the substance." `proposed_response` is not named as part of this view's required content anywhere in the plan's Architecture, Testing, or Acceptance criteria; printing it alongside is a reasonable option if it reads better, but nothing here requires it.
- resolve `target` via `resolve_feedback_target(feedback.target, loaded.design_row_index, loaded.removal_index)` and print `.text` beside the request. This step never branches on `.status` itself — it prints `.text` uniformly — so every outcome the function can return falls out automatically, including the removal-collision case step 1 added after this step's own logic was first written:
  - a live design row → `.text` is that row's ordinary `display_label`;
  - `FeedbackTargetKind.ARTIFACT` → status is `RESOLUTION_ARTIFACT_SCOPE`; print it as bearing on the artifact as a whole, never as `"⚠ undefined:"`;
  - an id absent from `design_row_index` but present in `removal_index` under exactly one match → `.text` is that `RemovalRecord`'s tombstone label. **This is the entire mechanism for "any removal that feedback cited rendered beside it as a tombstone."** There is no second lookup, no walk over `RemovalRecord.feedback_ids`, and no new join to write — the function this step calls already does it.
  - an id present in `removal_index` under **more than one** match (a colliding `removed_id`) → status is `RESOLUTION_AMBIGUOUS`; `.text` is the ambiguous marker and `.matches` names every tombstone — this step prints `.text` exactly as it would any other outcome, with no special case.
  - an id in neither index still resolves `RESOLUTION_DANGLING`, unchanged from any other reference this plan resolves.

**A removal is reachable from this view exactly once, through the feedback row whose target resolves through it, and never any other way.** A removal cited by a feedback row that has since been closed renders in no view here: the closed row is deleted from the artifact, so it is absent from `feedback_index`, so nothing calls `resolve_feedback_target` for it, so the removal it would have surfaced through is never reached. This step adds no separate pass over `removal_index` looking for "orphaned" removals to report — doing so would recreate the standalone removals section the plan's Out of scope refuses under either mode, "a place a reader arrives at rather than passes through."

**Ordering inside the pending group:** list pending decisions first, in stage-then-source order, then unclosed feedback rows, in stage-then-source order over `feedback_index`'s own already-ordered construction (step 2 builds it that way). The Architecture names both "the pending group" and "the feedback rows in review mode" as populations the stage-then-source rule fixes, listing them separately — decisions-then-feedback as two clearly labeled groups within Pending is one reasonable layout that respects both orderings without inventing a third rule to interleave two different row kinds; the fixed contract is that each population keeps its own stated order, not the exact visual arrangement.

**Signature:** `render_decision_ledger(loaded: LoadedRoadmap) -> str`, taking only what step 3's reverse index takes — no `plans_dir`, unlike step 4's walk, since this view reads nothing off disk beyond `LoadedRoadmap` itself. Of the three views, this is the second (with the reverse index) to need zero direct file access.

**Reuse the render header and absent/unparseable notice, but do not treat step 3's private helpers as an input contract this step can rely on.** This step's own `depends_on` is `[1, 2]`, not `3` — unlike step 4, which lists `3` and is explicitly told to call step 3's header/notice helpers. Every render still has to state its mode and, once before its own output, name what `loaded.absent` and `loaded.unparseable` list, per the plan's Architecture. Write this step's own small version against `LoadedRoadmap.mode` / `.absent` / `.unparseable` directly, matching the wording and placement step 3 established (so the three views read identically), rather than importing a symbol this step's declared dependencies do not name. If, by the time this step is implemented, a shared helper already exists in the module from step 3 with the same shape, calling it instead of writing a third near-duplicate is a reasonable simplification — but the fixed contract is the wording and the once-before-output placement, not which function produces it.

## Tests

`tests/test_roadmap_view.py`, extending steps 1–4's suite. Fixtures follow step 2's and step 3's pattern — real `DomainArtifact` / `ConstraintsArtifact` / `ComponentsArtifact` / `PlansArtifact` values loaded into a `LoadedRoadmap` via `load_roadmap`, not hand-typed YAML.

### Tests for this step

- `test_ledger_lists_every_decision_across_all_four_artifacts_exactly_once` — a fixture with decisions on all four artifacts accounts for each exactly once.
- `test_ledger_groups_decisions_by_status` — `SETTLED` and `PENDING` decisions land in their respective groups, in both modes.
- `test_ledger_decisions_order_stage_then_source` — decisions from two artifacts, and two decisions within one artifact, render in domain-before-constraints-before-components-before-plans order, each artifact's own decisions in source order.
- `test_ledger_resolves_decision_anchor_to_a_label` — a decision anchoring a live design row prints that row's `display_label` beside it.
- `test_ledger_prints_rejected_alternatives_and_rationale` — a decision's `chosen_option`, `rationale`, and every `RejectedAlternative` (`option` + `reason`) appear in its rendered entry.
- `test_ledger_dangling_decision_anchor_renders_the_marker` — a decision anchoring an id no artifact declares renders `resolve_id`'s own `"⚠ undefined: {id}"`.
- `test_ledger_ambiguous_decision_anchor_names_every_match` — a decision anchoring an id two rows declare renders `resolve_id`'s ambiguous text, naming both.
- `test_ledger_settled_decision_anchor_with_a_hand_edited_dangling_reference_renders_as_dangling` — a `SETTLED` decision (the case `check_design_row_continuity` normally protects) hand-fixtured to anchor an id present only in `removal_index`, not `design_row_index`, renders plain `"⚠ undefined:"` rather than the removal's tombstone — pinning that decision anchors never take the removals fallback, regardless of status.
- `test_ledger_current_mode_pending_group_has_no_feedback_or_removal` — under `mode="current"`, the pending group contains pending decisions only; no `FeedbackRow` content and no removal tombstone appear anywhere in the render.
- `test_ledger_review_mode_adds_unclosed_feedback_to_pending` — the same fixture under `mode="review"` adds every row from `feedback_index` to the pending group, each showing its `request`.
- `test_ledger_all_three_unclosed_feedback_states_reach_the_pending_group` (parametrized over `OPEN`, `AWAITING_REVIEW`, `DEFERRED`) — a feedback row in each state appears in `review` mode's pending group.
- `test_ledger_feedback_target_resolving_a_live_row_prints_its_label` — a `ROW`-kind target naming a live design row prints that row's ordinary label beside the request.
- `test_ledger_feedback_target_artifact_scope_prints_as_artifact_scope` — a `FeedbackTarget(kind=ARTIFACT)` prints the artifact-scope resolution, never `"⚠ undefined:"`.
- `test_ledger_feedback_target_through_a_removal_renders_the_tombstone` — the false-positive case named in the plan's Risks: a live feedback row whose target names an id absent from `design_row_index` but present in `removal_index` renders that removal's tombstone label beside the request, not a dangling marker.
- `test_ledger_feedback_target_genuinely_dangling_renders_the_marker` — a target naming an id in neither index renders `"⚠ undefined:"` — the negative case proving the removals fallback above is not a blanket amnesty.
- `test_ledger_removal_whose_citing_feedback_is_closed_renders_in_no_view` — the same removal-citing fixture, with the citing feedback row deleted from the artifact (closed), renders no trace of that removal anywhere in the ledger.
- `test_ledger_removal_rendering_names_only_the_id_and_rationale` — a rendered removal tombstone names `removed_id` and `rationale` and asserts nothing about the removed row's content, per the plan's "never dressed as a resolved row" rule.
- `test_ledger_removal_never_appears_under_its_own_heading` — a fixture carrying a live, citing feedback row and its removal renders the removal only inside that feedback row's entry, never under a section or list of its own.
- `test_ledger_pending_decision_renders_in_both_modes` — a `PENDING` decision appears in the pending group under both `mode="current"` and `mode="review"`, unchanged.
- `test_ledger_pending_feedback_orders_after_pending_decisions_in_stage_then_source_order` — within one pending group, decisions precede feedback rows, and each population keeps its own stage-then-source order.
- `test_ledger_render_names_its_mode_and_the_absent_unparseable_files` — the rendered text states the mode it was produced under and, once, before the ledger's own output, the artifacts `loaded.absent` and `loaded.unparseable` name.
- `test_ledger_render_is_the_same_on_repeat_calls` — rendering the same `LoadedRoadmap` twice produces the same text.
- `test_ledger_on_a_domain_only_roadmap_lists_only_domain_decisions` — a roadmap with only `01-domain.md` parsed lists that artifact's decisions and names the other three as absent, raising no exception.
- `test_module_reads_disk_only_through_the_artifact_loaders_and_the_draft_seed_read` — unchanged from step 4; stays green, since `render_decision_ledger` takes only a `LoadedRoadmap` and reads nothing off disk itself.
- `test_module_imports_only_the_artifact_and_gates_leaves` — unchanged from step 1; stays green, since this step adds no new first-party import.

Every test above is green before this step is considered finished.

## Acceptance criteria

- Every `DecisionRow` on every parsed artifact appears in the ledger exactly once, grouped by `status` into exactly two groups, in both modes; an absent or unparseable artifact contributes none of its own without affecting the others.
- Each decision's `anchor` resolves through `resolve_id` against `design_row_index` — resolved, dangling, or ambiguous — and never through `resolve_feedback_target` or any removals fallback, regardless of the decision's `status`.
- Each decision's own `chosen_option`, `rationale`, and every `rejected_alternatives` entry (`option` and `reason`) render from the row directly, not through `display_label`.
- Under `mode="current"`, the pending group contains pending decisions only — no feedback content and no removal appear anywhere in the render.
- Under `mode="review"`, the pending group additionally contains every row in `loaded.feedback_index`, in all three `FeedbackState` members, each showing its `request` and its `target` resolved through `resolve_feedback_target`.
- A live feedback row whose target resolves to a design row, to `FeedbackTargetKind.ARTIFACT`, or to a `RemovalRecord` (via the removals fallback) each render distinctly and correctly; a target in neither index renders `resolve_id`'s dangling marker.
- A removal renders exactly once, beside the live feedback row whose target resolved through it, naming only `removed_id` and `rationale`; it renders in no view once the feedback row that resolved through it is deleted, and never under a heading or list of its own.
- A pending decision renders identically in both modes; decisions and, under `review` mode, feedback rows each keep stage-then-source order within the pending group.
- The rendered ledger states the mode it was produced under and names the artifacts `loaded.absent` / `loaded.unparseable` list, once, before the ledger's own output; the same `LoadedRoadmap` rendered twice produces the same text.
- `render_decision_ledger` reads nothing off disk beyond the `LoadedRoadmap` it is given; it adds no new first-party import and no new direct `read_text` call.
- `plan-tool validate` and the full existing roadmap suite (`tests/test_roadmap_artifacts.py`, `tests/test_roadmap_gates.py`, `tests/test_roadmap.py`, `tests/test_roadmap_format.py`) stay green.

## References

- [dataclasses — Data Classes (Python 3 docs)](https://docs.python.org/3/library/dataclasses.html) — the frozen-dataclass shape `DecisionRow` and `RejectedAlternative` already carry, which this step reads but does not extend.
- [textwrap — Text wrapping and filling (Python 3 docs)](https://docs.python.org/3/library/textwrap.html) — `indent()` for nesting rejected alternatives under a decision and feedback entries under the pending group as stable indented text, and for dedenting expected output in fixtures.
- [string — Format Specification Mini-Language (Python 3 docs)](https://docs.python.org/3/library/string.html#format-specification-mini-language) — alignment and width specifiers for keeping the ledger's columns stable across runs.

## Applicable guardrails

- **The one-way import chain (plan's Architecture, "Placement preserves the one-way chain").** This step adds no new first-party import; the module's imports stay `plan_tool.roadmap_artifacts` and `plan_tool.roadmap_gates`, never `plan_tool.roadmap` or anything under `plan_tool/cli/` — including `_feedback_summary_lines` and `_newly_settled_summary_lines`, which this step's Why section notes as related but unreachable and unneeded.
- **The gates import stays narrow (plan's Architecture, "Why the gates import").** This step adds no new `roadmap_gates` symbol; it relies on `check_design_row_continuity` and `check_settled_decisions` being enforced upstream, never re-implements or re-checks either.
- **One display label per row kind, fixed in the resolver (plan's Architecture).** Wherever this step resolves an id — a decision's `anchor`, a feedback row's `target` — it prints step 1's `Resolution.text` or `display_label` output verbatim; it defines no second label or marker wording of its own.
- **Not a second enforcement channel (plan's Out of scope).** A dangling or ambiguous decision anchor, and a dangling, artifact-scope, or removal-resolved feedback target, are rendering annotations here, exactly as step 1 defined them — this step raises on none of them and adds no severity or blocking field.
- **No standalone removals section, in either mode, and no removals section by another name under `review` (plan's Out of scope and its 2026-08-07 narrowing).** This is the guardrail this step binds hardest, since the ledger is the view `review` mode changes most: a removal must render only inside the pending feedback entry whose target resolved through it, never under its own heading, its own list, or a place a reader arrives at directly.
- **The mode filter belongs to `LoadedRoadmap`, not to this step's own re-derivation (plan's Architecture).** Pending-group feedback inclusion follows `feedback_index` as-is, with no `if loaded.mode == ...` branch in this step's code for that purpose.
- **Machine-readable output stays out of scope (plan's Out of scope).** `render_decision_ledger` returns plain text; this step adds no `--json` form.

## Deferred

- **The reverse index and `RemovalRecord.feedback_ids` as a citer edge** — step 3's job, in the opposite direction from this step's join: step 3 answers "which feedback asked for this removal," this step answers "does this feedback's own target resolve through a removal."
- **The traceability walk over plans, components, entities, patterns, and constraints** — step 4; this step renders no `PlanRow`, `ComponentRow`, or `EntityRow` content.
- **CLI wiring (`--view`, `--mode`, `--id`) and the exit-code mapping** — step 6; `render_decision_ledger` is not called from anywhere yet.
- **The doc sweep and `CAPABILITIES.md` update** — step 7.
- **A decision-arc narrative on top of this view, and any Mermaid or other graph output** — the plan's own Deferred and Out of scope items; this step's ledger is a flat, grouped list, not a causal narrative or a graph.
- **Consolidating with `plan_tool/cli/roadmap_cmd.py`'s `_feedback_summary_lines` / `_newly_settled_summary_lines`** — not applicable: those summarize one just-finished `RoadmapResult`, this step renders a `LoadedRoadmap` snapshot of the roadmap on disk, and the one-way import chain forbids this leaf from importing CLI code regardless.
