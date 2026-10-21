> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Thread `depends_on_notes` through split, merge, scope-out narrow, and carved-seed upstream rendering

## Summary

This step implements the plan Architecture fan-out/fan-in table for `depends_on_notes`: split clears notes on repointed inbound edges and does not copy the target's notes onto replacement halves; merge outbound keeps a collapsed edge's note only when every merging member that declared that edge carried identical text (members without the edge are out of the vote); merge inbound keeps a note only when every collapsing edge an external dependent holds into the merge set carried identical text; every renumbering site remaps note keys through the same old-id→new-id map already used for `depends_on`; and scope-out's carved-seed upstream block renders each prerequisite's note in both its **done** and **external** sections. Primary edits land in `plan_tool/create.py` (`_apply_step_split`, `_apply_step_merge`) and `plan_tool/scope_out.py` (`compute_narrow`, `_resolve_upstream_context`, `_upstream_block`). Tests extend `tests/test_create.py`, `tests/test_scope_out.py`, `tests/test_detail.py`, and `tests/test_launcher.py` (mid-run `escalate_to_split` inherits the same policy). The never-graded allowlist in `tests/test_fingerprint.py` widens in the same change. The main design choice is a small shared remapping/collapse helper in `create.py` reused by scope-out's narrow path, mirroring how `depends_on` is already single-sourced per transform. On green, any split, merge, or scope-out narrow on a plan carrying notes produces a graph that still passes step 1's key-in-`depends_on` validator, and carved seeds name upstream consumption where the carved step recorded it.

## Table of Contents

- [Summary](#summary) — what ships, where, and the observable green outcome
- [Why](#why) — the gap after step 1 and why transforms must handle notes now
- [Input](#input) — the step 1 field contract this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint per file
- [Implementation](#implementation) — fan-out/fan-in rules, helpers, and call sites
- [Tests](#tests) — cases and green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs worth reading for this step
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly out of scope for this step

## Why

Step 1 adds `Step.depends_on_notes` with a structural rule: every note key must appear in that step's `depends_on`. Split, merge, and scope-out narrow already rewire `depends_on` and renumber survivors through `plan_tool/create.py:_apply_step_split`, `plan_tool/create.py:_apply_step_merge`, and `plan_tool/scope_out.py:compute_narrow`, but they never touch `depends_on_notes`. A plan with notes would either keep stale keys after renumbering (failing the step 1 validator inside the existing dry-run graph check) or silently carry a note onto an edge whose endpoints changed. This step closes that gap by applying the Architecture table's "prefer absent over a quietly false carry-over" rule at each transform site, before the dry-run validation that aborts bad graphs — `CreateError` on split/merge, and a wrapped `NarrowError` on scope-out (HEAD today raises a bare pydantic `ValidationError` from `compute_narrow`'s `Plan.model_validate`; this step must close that gap).

## Input

- **Step 1 outcome** — `plan_tool/schema.py:Step` carries `depends_on_notes: dict[int, str]` (default `{}`) with a step-level `@model_validator(mode="after")` rejecting any key not in `depends_on`. Content is never checked; `{}` elides on rewrite via `plan_tool/parser.py:write_plan`.
- **Existing transform contracts** — `_apply_step_split` and `_apply_step_merge` are pure list→list transforms that finish with a dry-run `Plan(...)` and raise `plan_tool/create.py:CreateError` with `plan_tool/create.py:_summarize_step_graph_error` on failure. `compute_narrow` builds survivors via `Step.model_copy(update={...})` using the same `old_to_new` map for `id` and `depends_on`, then validates with bare `Plan.model_validate(...)` today — wrap that failure as `NarrowError` (import `_summarize_step_graph_error` from create, or share a thin helper) so a stale note key is as diagnosable as a split/merge abort.
- **Production callers of `_apply_step_split`** — `plan-tool split` / create review / `plan_tool/detail.py:split_step` / `plan_tool/launcher.py:escalate_to_split` all call the same transform; inherit note policy without a second remapper. Cover escalate with a focused test (detail already has end-to-end split coverage).
- **Carved-seed upstream path** — `plan_tool/scope_out.py:_resolve_upstream_context` already emits `(id, title, status_value)` triples from each carved step's external `depends_on`, remapped through `NarrowPreview.renumber`; `plan_tool/scope_out.py:_upstream_block` renders them. Notes live on the carved step's edge to each prerequisite (`carved_step.depends_on_notes.get(dep_id)`).
- **Out of scope for threading** — the carved region's own internal `depends_on` graph (re-derived by synthesis) and `plan_tool/reground.py:render_rebaseline_seed` (renders no `depends_on` today). Negative-space tests pin those exclusions; no edits there.

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - `plan_tool/create.py` — add note-threading helpers; extend `_apply_step_split` and `_apply_step_merge` to read/write `depends_on_notes` per the Architecture table; keep dry-run `Plan(...)` → `CreateError` validation as the abort gate.
  - `plan_tool/scope_out.py` — extend `compute_narrow`'s survivor `model_copy` to remap note keys; wrap `Plan.model_validate` failures as `NarrowError` with summarized validator text; extend `_resolve_upstream_context` tuple shape and `_upstream_block` rendering for upstream notes.
  - `tests/test_create.py` — new cases on `TestApplyStepSplit` / `TestApplyStepMerge` (and helpers) covering each fan-out/fan-in branch plus post-transform validity.
  - `tests/test_scope_out.py` — narrow remapping cases, upstream note rendering, carved-region negative-space, diagnosable narrow abort on stale note keys.
  - `tests/test_detail.py` — one end-to-end case each through `plan_tool/detail.py:split_step` and `plan_tool/detail.py:merge_steps` proving the detail orchestrators inherit the create transforms unchanged.
  - `tests/test_launcher.py` — prove mid-run `escalate_to_split` inherits the same note fan-out / abort rules (third production caller of `_apply_step_split`).
  - `tests/test_fingerprint.py` — widen step 1's never-graded allowlist to include `plan_tool/create.py` and `plan_tool/scope_out.py` transform carriers in this same change.

## Implementation

### Governing rule

- **Prefer absent over a false carry-over** — same stance as `PLAN_FORMAT.md`'s intent-under-mutation table. When an edge does not survive one-to-one, drop its note rather than invent or guess text. No transform may add a note to fill a gap.

### Shared helper (recommended location: `plan_tool/create.py`)

- **One place for key remapping** — add a small pure helper (one name: `_remap_depends_on_notes` or similar) that takes a step's `depends_on_notes`, an old→new id map, and optional collapse groups (when several old antecedent ids fold onto one new id). Return a new dict with only keys still in the step's remapped `depends_on`.
- **Unanimous collapse** — when multiple old keys map to one new key, keep the note only if every contributing edge had the same text (including all absent vs one present → not unanimous → drop). Mirror the spirit of `plan_tool/detail.py:_unanimous_intent` but keyed on antecedent ids, not step intent. Empty string `""` counts as a present value (step 1 accepts it).
- **Rejected alternative:** pushing outbound-merge note assembly into `detail.py:merge_steps` — `_apply_step_merge` already owns `merged_deps` and `_remap_external`; splitting note logic across modules duplicates the id maps and is where drift caused the pre-step-1 bug class.

### Split — `plan_tool/create.py:_apply_step_split`

- **Inbound repoint (fan-out)** — when a survivor's `depends_on` entry remaps from `target_id` to `terminal_new_id` via the existing `remap()` function, **clear** any note keyed on that antecedent. Do not copy the old note onto the repointed edge.
- **Target halves** — replacement steps must **not** inherit the split target's `depends_on_notes` (parallel to `plan_tool/detail.py:split_step` not copying the target's `intent` onto either half). `_apply_step_split` today only overwrites `id` / `depends_on` / `status` on each `rep.model_copy(update={…})`, so any notes already on the parsed replacements would survive — **always set `depends_on_notes={}` on both halves** in that update (same ownership as `depends_on`). Also extend `_propose_step_split`'s JSON contract with "Do not include `depends_on_notes`" beside the existing "Do not include `depends_on`" line, so a model-supplied note cannot land on rewired edges the transform never authored.
- **Renumber survivors** — for every other step, remap note keys with the same `remap()` used for `depends_on` values so keys track shifted antecedent ids.
- **Validation** — unchanged: dry-run `Plan(...)` at the end; stale keys surface through step 1's validator and become `CreateError("split produced an invalid step graph: …")`.

### Merge — `plan_tool/create.py:_apply_step_merge`

- **Outbound (merged survivor's `depends_on`)** — when building `merged_deps` from members' external edges, build `merged_depends_on_notes` in the same pass: for each external antecedent id, keep a note only if every member that depended on that id carried identical note text (missing note vs present note → not identical → omit).
- **Inbound (external dependents)** — in the non-member survivor loop where `_remap_external` collapses edges onto one survivor id, collapse notes with the same unanimous rule before writing `depends_on_notes` on the updated step.
- **Renumber** — remap note keys on every survivor with the `renumber` dict already computed for the walk.
- **Caller content** — the `merged` step the caller passes still supplies title/files/etc.; the transform owns `id`, `depends_on`, `status`, `concept_ids`, and (after this step) the merged survivor's `depends_on_notes` for outbound edges — same division as today for `depends_on`.

### Scope-out narrow — `plan_tool/scope_out.py:compute_narrow`

- **Surviving plan renumber** — in the survivor `model_copy(update={...})` block (~the loop that sets `id`, `depends_on`, `detail`), also set `depends_on_notes` by remapping keys through `old_to_new` (same map as `depends_on`). No separate shift arithmetic.
- **Diagnosable abort** — wrap the final `Plan.model_validate(...)` in `try`/`except` for pydantic `ValidationError`; raise `NarrowError` whose message includes `_summarize_step_graph_error(exc)` (same text shape as split/merge's `CreateError`). Do not leave a raw ValidationError as the operator-facing abort.
- **Blockers unchanged** — inbound-dependent and downstream-orphan gates run before mutation; this step does not relax them.

### Carved-seed upstream — `plan_tool/scope_out.py`

- **`_resolve_upstream_context`** — extend the return tuple to carry an optional note per prerequisite, e.g. `(new_id, title, status_value, note | None)`, sourced from `carved_step.depends_on_notes.get(dep_id)` for the edge being rendered. When multiple carved steps share the same external dep, keep today's first-seen `dep_id` dedupe: the **first carved step that contributes that dep** wins for title *and* note (including "no note" if that first step has none) — a later carved step's note for the same dep never overrides. Do not invent unanimous-or-prefer-absent logic that title lacks.
- **`_upstream_block`** — when `note` is non-empty, append it to the bullet (one way: ` — consumes: {note}` or ` Note: {note}`; pick one format and pin it in tests). Omit extra prose when the note is absent.
- **Callers** — `render_carved_seed` and `render_carved_region_seed` already pass `upstream_context` through; no API shape change beyond the tuple width.

### Detail / launcher orchestrators (no `plan_tool/detail.py` or `launcher.py` edit expected)

- **`split_step` / `merge_steps`** — both delegate to `_apply_step_split` / `_apply_step_merge`. Correct threading in `create.py` covers `plan-tool split` / `plan-tool merge` and create's review-time split. Confirm with one test per orchestrator in `tests/test_detail.py`.
- **`escalate_to_split`** — mid-run bridge in `plan_tool/launcher.py` also calls `_apply_step_split` directly. Confirm with one focused test in `tests/test_launcher.py` that a plan carrying notes through escalate follows the same fan-out clear / remapping / `CreateError` abort rules (no second remapper in launcher).

### Abort path (real failure mode)

- **Not silent corruption** — a threading bug that leaves a note key outside `depends_on` fails dry-run graph validation. Split/merge raise `CreateError` with `_summarize_step_graph_error` text; scope-out raises `NarrowError` with the same summarized text after this step's wrap (not a bare pydantic traceback).
- **Do not swallow validator errors** — keep `from exc` chaining on `CreateError` / `NarrowError` raises so the step 1 message (naming the bad key) remains visible in the summary.

### Sibling sites deliberately untouched

- **`plan_tool/detail.py` / `plan_tool/launcher.py`** — no code change unless an unexpected second remapping path appears on audit; both should inherit create transforms only.
- **`plan_tool/reground.py`** — excluded by Architecture; negative test only.

## Tests

Every test below must be green before this step is done.

### Tests for this step

**`tests/test_create.py`** (extend `TestApplyStepSplit` / `TestApplyStepMerge`):

- `test_split_clears_note_on_repointed_inbound_edge` — step 3 depends on split target 2 with `{2: "…"}`; after split, depends on terminal half id and `depends_on_notes` is `{}`.
- `test_split_does_not_copy_target_notes_to_replacements` — target carries `{1: "…"}` on its outbound edge; neither replacement half inherits it.
- `test_split_clears_notes_on_parsed_replacements` — replacements arrive from `_parse_steps_json` with their own `depends_on_notes`; after `_apply_step_split`, both halves have `depends_on_notes == {}`.
- `test_propose_step_split_prompt_forbids_depends_on_notes` — `_propose_step_split`'s prompt includes "Do not include `depends_on_notes`" alongside the existing `depends_on` forbid.
- `test_split_remaps_note_keys_for_untouched_downstream` — a step below the splice whose note key references a shifted antecedent id gets remapped keys, not stale ones.
- `test_merge_outbound_keeps_note_when_unanimous` — members 2 and 3 both `{1: "same"}` on external dep 1 → merged survivor `{1: "same"}`.
- `test_merge_outbound_keeps_note_when_only_one_member_has_edge` — member 2 depends on 1 with a note; member 3 has no edge to 1 → merged survivor keeps member 2's note (member 3 is out of the vote).
- `test_merge_outbound_clears_note_when_text_differs` — members carry different notes for the same external dep → merged survivor has no entry for that antecedent.
- `test_merge_inbound_clears_note_when_collapsed_edges_disagree` — dependent on both merge members with different notes → single collapsed edge, note absent.
- `test_merge_inbound_keeps_note_when_collapsed_edges_agree` — dependent on both members with identical notes → single edge retains the note.
- `test_split_with_notes_produces_valid_graph` — post-split, every step satisfies `set(notes) ⊆ set(depends_on)`.
- `test_merge_with_notes_produces_valid_graph` — same property after merge.
- `test_merge_stale_note_key_raises_create_error` — force a stale/unmapped note key through `_apply_step_merge`; raises `CreateError` whose message includes `_summarize_step_graph_error` output (parallel to split and narrow abort fixtures).

**`tests/test_scope_out.py`**:

- `test_narrow_remaps_depends_on_notes_with_survivors` — carve drops ids below a survivor; note keys on remapped antecedents match new ids.
- `test_upstream_block_renders_note_when_present` — `_render(upstream_context=[(1, "Base", "done", "consumes schema")])` includes the note text in the done prerequisites section.
- `test_upstream_block_omits_note_when_absent` — fourth tuple element empty/None → bullet matches today's title-only shape.
- `test_upstream_shared_dep_first_carved_step_wins` — two carved steps share one external dep; only the second carries a note → upstream renders without that note (first-seen carved step had none).
- `test_done_upstream_context_includes_note_in_seed` — end-to-end `scope_out_step` where carved step records a note on a DONE prerequisite.
- `test_carved_region_internal_depends_on_notes_not_in_upstream` — two-step region with internal `depends_on` and notes: upstream block lists only external deps; internal notes do not leak into upstream prerequisites.
- **Existing three-tuple fixture migration** — every current `upstream_context=[(id, title, status)]` call site in this module (e.g. `test_done_upstream_prerequisites_rendered_as_assumed_done`) must be updated to the four-tuple shape in the same change, **or** `_upstream_block` / `_resolve_upstream_context` must document and implement a tolerant unpack that still accepts three-tuples. Pin the chosen approach with a test; do not leave the pre-step-2 fixtures ambiguous at green.

**`tests/test_detail.py`**:

- `test_split_step_threads_depends_on_notes` — `split_step` on a plan whose downstream step carries a note through split/merge policy (assert via parsed plan on disk or dry-run result).
- `test_merge_steps_threads_depends_on_notes` — `merge_steps` dry-run preview leaves unanimous outbound notes on the survivor.

**`tests/test_launcher.py`**:

- `test_escalate_to_split_threads_depends_on_notes` — mid-run `escalate_to_split` on a plan whose dependent carries a note on the split target clears/remaps per Architecture (same fan-out rule as `test_split_clears_note_on_repointed_inbound_edge`).
- `test_escalate_to_split_stale_note_raises_create_error` — force a threading mistake (or assert the dry-run path) so a bad note key surfaces as `CreateError`, not an uncaught ValidationError.

**`tests/test_scope_out.py`** (abort addition):

- `test_narrow_stale_note_key_raises_narrow_error` — after deliberately leaving a stale note key, `compute_narrow` raises `NarrowError` whose message includes the step 1 validator summary (not a bare pydantic traceback).

**`tests/test_fingerprint.py`**:

- Widen the never-graded allowlist so `plan_tool/create.py` and `plan_tool/scope_out.py` may reference `depends_on_notes` as carriers; assert the sweep still fails if a new scoring/gating site appears outside the allowlist.

**Negative space (read-only imports OK):**

- `test_reground_seed_ignores_depends_on_notes` — in `tests/test_detail.py`, call `plan_tool/reground.py:render_rebaseline_seed` on a flagged plan whose steps carry `depends_on_notes`; assert the rendered seed body contains none of the note strings (proves reground exclusion without editing `reground.py`).

## Acceptance criteria

- `_apply_step_split` clears notes on edges repointed to the terminal replacement and does not copy the target's `depends_on_notes` onto replacement halves; both halves always get `depends_on_notes={}` from the transform (not from the proposer), and `_propose_step_split`'s prompt forbids including the field.
- `_apply_step_merge` applies unanimous-note collapse for outbound merged edges and inbound collapsed dependent edges; non-unanimous notes are dropped.
- `compute_narrow` remaps every survivor's `depends_on_notes` keys through the same `old_to_new` map used for `depends_on`.
- `_upstream_block` renders a non-empty note in both its **done** and **external** upstream sections when the carved step recorded one on that edge (HEAD already splits prerequisites that way — do not document external-only).
- After each transform, `set(step.depends_on_notes) ⊆ set(step.depends_on)` for every step (equivalently: dry-run `Plan(...)` succeeds for the fixtures above).
- A stale-key threading mistake raises `CreateError` on split/merge and `NarrowError` on scope-out (both messages include `_summarize_step_graph_error` output, not a bare pydantic traceback).
- `escalate_to_split` inherits the same note fan-out / abort rules without a launcher-local remapper.
- All tests listed in [Tests](#tests) pass.
- `rg 'depends_on_notes' plan_tool/create.py plan_tool/scope_out.py` shows only read/carry logic — no scoring, gating, or content validation; the never-graded allowlist in `tests/test_fingerprint.py` includes both carriers.

## References

- [Pydantic v2 — Validators](https://docs.pydantic.dev/latest/concepts/validators/) — the step 1 cross-field validator this step must satisfy after every rewire; read for `model_validator(mode="after")` error shape.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — int-key maps in frontmatter if fixtures hand-write `depends_on_notes` blocks in tests.

## Applicable guardrails

- **Plan fence (structural key membership only)** — this step only moves or drops notes; it never grades, scores, or gates on note text or note-on-edge presence. Helpers carry strings unchanged; no plausibility checks. Silent = absent key.
- **Step intent (prefer absent over false carry-over)** — every fan-out/fan-in branch drops ambiguous notes; tests assert absence, not rewritten prose.
- **Plan "## Out of scope", content validation** — no note-content validation, no requirement that edges have notes, no retroactive edits to existing plans.
- **Plan "## Out of scope", gates** — threading success/failure uses existing structural abort paths only; do not add new exit-code flips or refusal-to-advance keyed on note presence.

## Deferred

- **`plan_tool/reground.py` note threading** — Architecture excludes `render_rebaseline_seed`; negative test proves no accidental carry-over — BACKLOG / follow-up if reground ever renders `depends_on`.
- **Carved region internal graph notes** — edges between co-carved steps are re-planned by synthesis, not copied; negative test only, no `_scope_block` change.
- **`PLAN_FORMAT.md` mutation table row for `depends_on_notes`** — documented in step 6 (`change_type: non-code`); this step implements the behavior the doc will later describe.
- **Consolidating `_unanimous_intent` and note-unanimous collapse** — similar shape, different fields; merge stays local to avoid a cross-module refactor in this step.
