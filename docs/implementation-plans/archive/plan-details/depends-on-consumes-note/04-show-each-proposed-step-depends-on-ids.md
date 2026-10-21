> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Show each proposed step's `depends_on` ids and their notes in create's interactive step review

## Summary

This step adds read-only dependency context to `create`'s interactive change-type review. When `_ask_change_type` prompts the operator to confirm, override, or split a step, it prints every `depends_on` id on that step together with any `depends_on_notes` text for that edge; edges with no note still show their id. A small formatter in `plan_tool/create.py` owns the line shape; `_review_step_change_types` passes the current reviewed step list so antecedent titles can appear beside ids. The post-split recap in `_review_step_change_types` reuses the same formatter so notes stay visible after a split rewires the graph. No new prompts, gates, or note-editing paths — display only. Tests extend `tests/test_create.py` beside `TestAskChangeType` and the existing review-loop capsys cases. On green, an interactive create review surfaces what each edge delivers before the operator answers.

## Table of Contents

- [Summary](#summary) — what ships, where, and the green outcome
- [Why](#why) — the gap after step 3
- [Input](#input) — contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint per file
- [Implementation](#implementation) — formatter, call sites, and boundaries
- [Tests](#tests) — cases and green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly not this step

## Why

Step 3 teaches `create` to collect optional per-edge notes during Claude proposal and the manual wizard, and step 2 keeps those notes aligned when split or merge rewires the graph. The interactive review loop — where the operator confirms or splits the proposed step graph — still shows only title, `change_type`, rationale, and granularity hints via `plan_tool/create.py:_ask_change_type`. Neither `depends_on` nor `depends_on_notes` appears there, so the operator decides purity and decomposition without seeing what each edge is claimed to deliver. This step closes that gap at the moment of confirmation.

## Input

- **Step 1 outcome** — `plan_tool/schema.py:Step` carries `depends_on_notes: dict[int, str]` (default `{}`); every note key must be in that step's `depends_on`. Content is never validated; `{}` and partial edge coverage are valid.
- **Step 3 outcome** — proposal and manual paths may populate `depends_on_notes` on `Step` objects before review runs. Step 4 only reads the field; it does not collect or edit notes.
- **Step 2 outcome** — after a review-time split via `plan_tool/create.py:_apply_step_split`, notes on repointed or divided edges follow the Architecture fan-out rules (often cleared). Display reflects whatever notes remain on the `Step` being shown, not a recomputation.
- **Review loop contract** — `plan_tool/create.py:_review_step_change_types` walks `reviewed` in order, calls `_ask_change_type` per step in interactive TTY mode, and already prints a short post-split recap (`depends_on=[…]` list form). Non-interactive exits (`--yes`, non-TTY stdin, checkpoint resume) return steps without prompting and stay unchanged.

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - `plan_tool/create.py` — add a pure formatter for dependency review lines; call it from `_ask_change_type` and from the post-split recap in `_review_step_change_types`; thread the current step list into `_ask_change_type` (new optional parameter).
  - `tests/test_create.py` — formatter unit cases and capsys coverage on `_ask_change_type` / `_review_step_change_types` (extend `TestAskChangeType` and/or add a focused class beside the existing review-loop tests).
  - `tests/test_fingerprint.py` — widen the never-graded allowlist for this step's read-only display references under `plan_tool/create.py`.

## Implementation

### Design stance

- **Display only, never collect** — show ids and notes the step already carries; do not add prompts, retries, warnings, or refusal paths keyed on missing notes. Rejected alternative: optional "edit note now" branch in review — out of scope and violates the plan fence against gating on presence.
- **Ids and notes together** — every `depends_on` entry gets a review line; a note prints beside its id when present **and non-empty**. A missing key and a residual empty-string value (parse-only; authoring never writes one) both display as silent — id only, no empty quote. Rejected alternative: print notes only when non-empty *and* hide silent edges entirely — that hides silent edges and repeats the baseline gap the step intent names.
- **Follow `depends_on` order** — iterate `step.depends_on` in list order so display matches frontmatter ordering.

### Formatter (recommended: `plan_tool/create.py`)

- Add a small pure helper (one name, e.g. `_format_depends_on_review_lines`) taking `(step: Step, steps_by_id: dict[int, Step]) -> list[str]`.
- **Non-empty `depends_on` only** — return `[]` when `step.depends_on` is empty; callers print nothing (no "depends_on: none" header).
- **Per-edge line shape** — pin one format in tests; one workable shape:
  - with note: `depends_on {id} ({antecedent title}): {note text}`
  - without note: `depends_on {id} ({antecedent title})`
  - when the antecedent id is missing from `steps_by_id` (invalid graph that somehow reached review): print the id without a title rather than skipping the edge.
- **Note text** — print verbatim; no truncation, wrapping policy, or content judgment.
- **Indent** — helper returns unprefixed lines; `_ask_change_type` prints each with the same two-space prefix used for `rationale:` and `granularity:`.

### `_ask_change_type`

- Add an optional keyword-only parameter for the reviewed step list (e.g. `all_steps: Optional[list[Step]] = None`).
- After the `proposed change_type` line and before `rationale` / `granularity` hints, build `steps_by_id = {s.id: s for s in all_steps}` when `all_steps` is provided, call the formatter, and print each line.
- **Default `None` stays valid** — existing call sites that omit the list behave as today (no dependency lines). The interactive review call site passes the live `reviewed` list.
- Do not change the prompt string, accepted answers, or return values.

### `_review_step_change_types`

- At the `_ask_change_type` call inside the interactive loop, pass `all_steps=reviewed` (rebuilt each iteration so post-split ids stay correct).
- **Post-split recap** — the block that prints `split step N into:` currently emits `depends_on=[…]` per replacement step. Reuse the formatter (or a one-line wrapper) so each half's outbound edges show ids and any surviving notes consistently with the per-step prompt. Step 2 may have cleared notes on repointed edges; show the cleared state, do not restore old text.

### Paths that stay unchanged

- **`--yes`, non-TTY, checkpoint resume** — no new stdout; these paths never call `_ask_change_type`.
- **`propose_steps_from_claude` / `_render_from_prompt`** — model-facing grounding (`dependency_cohesion_block`, bridging-edge blocks) is a separate surface; step 4 does not edit it.
- **Split/merge transforms** — step 2 owns note threading; step 4 does not edit `_apply_step_split`, `_apply_step_merge`, or `_propose_step_split`.
- **Checkpoint payload** — `depends_on_notes` already rides on serialized `Step` objects once step 3 lands; no checkpoint schema change unless serialization drops the field (fix only if discovered).

### Never-graded guard

- This step adds **read-only** prints. Do not introduce scoring, ranking, exit-code changes, or advisory severity keyed on note presence or text. A grep over new code should show no branch that refuses advance when a note is missing. Widen the never-graded allowlist in `tests/test_fingerprint.py` in this same change.

## Tests

Every test below must be green before this step is done.

### Tests for this step

**Formatter** (new class, e.g. `TestFormatDependsOnReviewLines`):

- `test_formatter_emits_nothing_when_depends_on_empty` — `depends_on=[]` → `[]`.
- `test_formatter_emits_id_without_note` — `depends_on=[1]` and no note key → line contains antecedent id (and title when lookup exists).
- `test_formatter_emits_id_with_note` — `depends_on_notes={1: "consumes schema"}` → line contains id and note text.
- `test_formatter_treats_empty_string_as_silent` — `depends_on_notes={1: ""}` → line shows id only (same as missing key; no empty quote).
- `test_formatter_partial_coverage` — `depends_on=[1, 2]` with note only for `1` → two lines; second shows id only.
- `test_formatter_preserves_depends_on_order` — `depends_on=[2, 1]` → lines appear in that order.

**`_ask_change_type`** (extend `TestAskChangeType`, mirror `test_granularity_hint_printed` / `test_no_granularity_hint_when_absent`):

- `test_ask_change_type_prints_depends_on_and_note` — capsys: step with edge + note shows both id and text.
- `test_ask_change_type_prints_depends_on_without_note` — capsys: edge with no note still shows id; no note-only line without id.
- `test_ask_change_type_omits_depends_on_when_empty` — capsys: no `depends_on` output when list empty.
- `test_ask_change_type_omits_depends_on_when_all_steps_not_passed` — default/`None` `all_steps` → no dependency lines (backward compat for direct unit calls).

**Review loop** (extend existing `_review_step_change_types` capsys tests near `test_mixed_title_step_shows_hint`):

- `test_review_prints_depends_on_notes_before_prompt` — interactive review of a two-step graph with a note on step 2's edge to step 1; captured stdout before the `(r)efactor` prompt includes the antecedent id and note text.

## Acceptance criteria

- In interactive TTY review, `_ask_change_type` prints every `depends_on` id on the step under review; edges with a note also print that note text on the same line block.
- Edges without a note still print their id; no note appears without its id.
- Steps with empty `depends_on` add no dependency lines to the review output.
- No new prompt, retry, warning-as-refusal, or exit-code change when notes are absent or empty.
- Post-split recap output uses the same id+note display rules as the per-step prompt (or documents one intentional difference in a test comment — prefer one shared formatter).
- `--yes`, non-TTY stdin, and checkpoint resume behavior is unchanged (no new dependency output on those paths).
- All tests listed above pass.
- `rg 'depends_on_notes' plan_tool/create.py` shows only read/print/carry paths in this step's edits — no scoring or gating branches added by step 4.

## Applicable guardrails

- **Plan fence (structural key membership only)** — this step may show notes; it must not score, rank, or gate on note text or note-on-edge presence. Missing notes are a normal silent edge (absent key), not a defect.
- **Plan "## Out of scope", content validation** — display note text verbatim; no length, plausibility, or truth checks in the formatter.
- **Plan "## Out of scope", requiring notes** — do not require notes on every edge or add a review prompt to supply them.
- **Plan "## Out of scope", gates and exit codes** — no refusal-to-advance, lowered severity, or warning treated as blocking when an edge lacks a note.
- **Step intent (ids and notes together)** — do not ship note-only output without the corresponding `depends_on` id on the same review surface.

## Deferred

- **Collecting or editing notes during review** — step 3 owns authoring; step 4 is read-only display.
- **Dependency display in `--yes`, non-TTY, or checkpoint-resume paths** — no operator is present; unchanged behavior is correct.
- **`PLAN_FORMAT.md` / BACKLOG #253 bookkeeping** — step 6.
- **Withdrawn-plan fixture** — step 5.
- **Cohesion / bridging-edge blocks in the Claude proposal prompt** — separate informational surface (`_bridging_dependency_edges` / `_render_dependency_cohesion_block`); not the operator confirm loop.
- **Reading `depends_on_notes` in BACKLOG #252 cohesion ordering or `SoftEdge` heuristics** — future work; structural overlap signal stays note-blind.
