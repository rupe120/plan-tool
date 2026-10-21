> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Ask create's step proposal and the manual step wizard for a per-edge note, and drop any note key the step doesn't depend on

## Summary

This step wires `depends_on_notes` into `plan_tool/create.py`'s two human-facing authoring paths: the Claude step-proposal round-trip (`_render_from_prompt` → `_parse_steps_json` → `propose_steps_from_claude`) and the manual fallback wizard (`prompt_steps` / `_prompt_one_step`). The proposal prompt gains an optional `depends_on_notes` JSON field in the same turn that already asks for `depends_on`; the parser keeps only keys that appear in that step's `depends_on` list and never treats a missing note as a defect. The manual wizard adds one optional prompt per declared edge after `_ask_int_list`. The canonical Claude-free path (`extract_steps_from_canonical`) and interactive step review (`_review_step_change_types`, step 4) stay untouched. Tests land in `tests/test_create.py` beside the existing `TestParseStepsJsonIntent` / `TestProposalPromptAsksForIntent` patterns. On green, a proposed or manually entered note round-trips into written plan frontmatter; a silent edge stays silent with no re-prompt and no repair retry.

## Table of Contents

- [Summary](#summary) — what ships, where, and the green outcome
- [Why](#why) — the gap after steps 1–2
- [Input](#input) — contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint per file
- [Implementation](#implementation) — prompt, parser, wizard, and boundaries
- [Tests](#tests) — cases and green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs worth reading
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly not this step

## Why

Step 1 adds `Step.depends_on_notes` with a structural key-in-`depends_on` rule; step 2 threads notes through split, merge, and scope-out transforms. Neither step teaches `create` to collect notes at authoring time. Today `_render_from_prompt`'s JSON contract ends at `"depends_on": [int, ...]`, `_parse_steps_json` never reads a notes key, and `_prompt_one_step` stops after `_ask_int_list` — so every plan born through `create` carries empty notes even when the operator or model could have named what each edge delivers. This step closes that gap using the same "one call, optional field" pattern as `intent` on the proposal path, but without `intent`'s soft-rejection retry: silence is valid.

## Input

- **Step 1 outcome** — `plan_tool/schema.py:Step` carries `depends_on_notes: dict[int, str]` (default `{}`) with a step-level validator rejecting any key not in `depends_on`. Partial edge coverage parses; empty-string values parse only as a content-not-graded courtesy — **authoring must omit the key for silent edges**, never write `{id: ""}`.
- **Step 2 outcome** — split/merge/narrow already remap note keys when the step graph is rewritten. Step 3 does not edit those transforms; it only produces correctly keyed notes at create time.
- **Proposal pipeline** — `plan_tool/create.py:_render_from_prompt` assembles the inline prompt (items 1–7 plus optional gate/foundational tail); `plan_tool/create.py:_parse_steps_json` lifts a JSON array and builds `Step` objects with ids from `enumerate`; `plan_tool/create.py:propose_steps_from_claude` dry-runs `Plan(...)` and shares one repair retry across graph, parse, and missing-`intent` failures — notes must not become a fourth rejection kind.
- **Manual wizard** — `plan_tool/create.py:prompt_steps` loops `_prompt_one_step`, which already collects title, complexity, files, and `depends_on` via `_ask_int_list`.
- **Explicit non-input (note-less by construction)** — `plan_tool/create.py:extract_steps_from_canonical` / `plan_tool/canonical.py:extract_canonical_steps`, and `plan_tool/foundational_logic.py:merge_sweep_into_steps` (consolidation steps with wired `depends_on` but no notes). Stay note-less; pin with negative-space tests.

## Files (creates vs edits)

- **New files:** none

- **Existing files (edits only):**
  - `plan_tool/create.py` — extend `_render_from_prompt`'s JSON contract and explainer; parse and sanitize `depends_on_notes` in `_parse_steps_json`; add a small manual-wizard helper and call it from `_prompt_one_step` (and adjust `prompt_steps` if it needs prior-step context for prompts).
  - `tests/test_create.py` — prompt contract, parser lenience, orphan-key dropping, manual wizard blank acceptance, canonical/foundational negative-space, and at least one end-to-end path from proposal or manual input to written frontmatter.
  - `tests/test_fingerprint.py` — widen the never-graded allowlist for this step's authoring writes under `plan_tool/create.py`.

## Implementation

### Design stance

- **Same turn as `depends_on`, optional like `gate`** — the model may supply notes in the proposal JSON; the operator may supply them in the manual wizard. Neither path adds a second round-trip or a follow-up question when notes are absent.
- **Rejected alternative: soft-rejection retry for missing notes** — mirrors `intent` but violates the plan fence ("a proposed edge with no note is accepted unchanged"). Do not add a `_steps_missing_depends_on_notes` check or a `_REPAIR_CORRECTION_*` tail for notes.
- **Rejected alternative: fail the whole proposal on orphan note keys** — step 1's validator would reject the graph; instead **sanitize in `_parse_steps_json`** before constructing `Step`, keeping only keys present in that object's `depends_on` list. A model that names `{99: "…"}` on a step whose `depends_on` is `[1]` loses the orphan silently; the rest of the proposal still lands.

### Claude proposal prompt (`_render_from_prompt`)

- Add a short explainer constant (one way: `_PROPOSAL_DEPENDS_ON_NOTES_EXPLAINER`) stating:
  - when a step lists `depends_on`, it **may** include `depends_on_notes` mapping each antecedent id to one line naming what that antecedent delivers to this step;
  - omit the key, or omit individual ids, when nothing needs saying;
  - **never** require a note; do not invent notes for ordering-only edges.
- Extend the JSON shape line (the `"Then respond with ONLY a JSON array…"` block) to include an optional `"depends_on_notes": {int: str}` entry — same placement pattern as the conditional `"gate": [str, ...]` fragment.
- **Do not** add a new numbered prompt item that renumbers items 8–9; ride the JSON contract like `gate`, not item 7 like `intent`.
- Pin the contract in tests across all four `_render_from_prompt` A/B arms (same approach as `TestProposalPromptAsksForIntent`).

### Parser (`_parse_steps_json`)

- Read optional `depends_on_notes` from each proposal object **after** `depends_on` is parsed.
- **Lenient top-level shape** (mirror `gate` / `change_type`, not `files`):
  - absent key, `null`, or non-object → treat as `{}`;
  - object entries whose keys are not `int` (after accepting JSON string keys that parse as integers) or whose values are not strings → drop that entry, not the whole step;
  - **omit empty-string values** — if the model supplies `{1: ""}`, drop that entry (treat as silent). Silent edges omit the key; never store `""`. Matches Architecture's binary observable and the wizard's blank behavior.
- **Sanitize keys:** compute `allowed = set(depends_on)` and keep only `{k: v for k, v in notes.items() if k in allowed}`.
- Pass the sanitized dict into `Step(..., depends_on_notes=...)`.
- **No usability or plausibility check** — store text verbatim (light strip on surrounding whitespace is fine; do not collapse multi-line prose unless you already do the same for `intent` via `collapse_intent_to_one_line`, and if you do, say why in a comment).
- **Do not** add note-key errors to `_REPAIR_CORRECTION_GRAPH`; orphan keys are dropped, not repaired.

### Manual wizard (`_prompt_one_step`)

- After `_ask_int_list` returns a non-empty `depends_on`, collect optional notes — one prompt per edge, in `depends_on` order.
- **Blank answer is accepted** with no re-prompt (unlike `_ask_int_list`'s validation loop) — omit the key for that edge (never store `{id: ""}`).
- Suggested prompt shape: name the dependent step id and antecedent id; ask what the antecedent delivers (optional). Include the antecedent title when cheap — `prompt_steps` already holds prior `Step` objects and can pass them into `_prompt_one_step` for lookup.
- When `depends_on` is empty, skip note prompts and leave `depends_on_notes` at the schema default.
- One way: add `_ask_depends_on_notes(input_fn, step_id, depends_on, prior_steps) -> dict[int, str]` beside `_ask_int_list`; keep `_prompt_one_step`'s existing four-prompt contract test (`test_manual_step_unclassified_then_reviewed`) updated to account for the new prompts only when `depends_on` is non-empty.

### Call sites and paths that stay unchanged

- **`extract_steps_from_canonical`** — zero diff; canonical seeds carry no notes by construction (pin with a negative-space test).
- **`merge_sweep_into_steps`** — foundational consolidation steps stay note-less by construction (pin with a negative-space test; do not teach the sweep to author notes).
- **`propose_steps_from_claude` retry loop** — no new branch for notes; missing notes never trigger repair.
- **Interactive step review** — step 4 owns showing notes during `_review_step_change_types`; do not render notes here.
- **`_preserve_on_disk_step_fields`** — extend same-title iterate merges to carry forward on-disk `depends_on_notes` when the new proposal **omits** the key; when the proposal **includes** the key (even as `{}`), use the proposal. Parallel to existing `intent` preservation. When preserving, **intersect** with the proposal step's current `depends_on` (same orphan-key drop as `_parse_steps_json`) so a shrunk edge list cannot restore stale note keys that fail step 1's membership check. Add `test_preserve_on_disk_keeps_depends_on_notes_when_proposal_omits` and `test_preserve_on_disk_intersects_notes_with_proposal_depends_on` beside the intent-preservation cases.

### Never-graded guard

- This step adds `depends_on_notes` **writes** under `plan_tool/create.py`. Widen step 1's allowlist in `tests/test_fingerprint.py` in this same change (now in this step's `files:`).

## Tests

Every test below must be green before this step is done.

### Tests for this step

**Prompt contract** (extend or mirror `TestProposalPromptAsksForIntent` / `TestRenderFromPromptABMode`):

- `test_proposal_prompt_names_depends_on_notes_shape` — `_render_from_prompt` output includes the `depends_on_notes` JSON key and states notes are optional per edge.
- `test_depends_on_notes_explainer_survives_both_prompt_arms` — combined and split `_render_from_prompt` arms both carry the contract (parametrize the four arm dicts like `TestProposalPromptAsksForIntent._ARMS`).

**Parser** (new class `TestParseStepsJsonDependsOnNotes`, modeled on `TestParseStepsJsonGate` / `TestParseStepsJsonIntent`):

- `test_parse_steps_json_reads_depends_on_notes` — valid mapping for ids in `depends_on` lands on `Step.depends_on_notes`.
- `test_parse_steps_json_tolerates_missing_depends_on_notes` — no key → `{}`.
- `test_parse_steps_json_tolerates_non_object_depends_on_notes` — wrong type → `{}`; proposal survives.
- `test_parse_steps_json_drops_orphan_note_keys` — `depends_on: [1]` with `{2: "…"}` → `{}` or `{1: …}` only; no `ValidationError` from `_parse_steps_json`.
- `test_parse_steps_json_drops_note_for_removed_depends_on_id` — notes keyed only to ids still listed after sanitization.
- `test_parse_steps_json_coerces_stringified_int_keys` — JSON `{"1": "…"}` with `depends_on: [1]` keeps the note (JSON objects only have string keys).
- `test_parse_steps_json_accepts_partial_edge_coverage` — `depends_on: [1, 2]` with note only for `1`.
- `test_parse_steps_json_drops_empty_string_note_values` — `{1: ""}` with `depends_on: [1]` → `{}` (silent = absent key).

**Manual wizard**:

- `test_prompt_one_step_collects_optional_notes` — queued blanks for two edges → `{}`; queued text for one edge → single-entry dict.
- `test_prompt_one_step_skips_note_prompts_when_no_depends_on` — blank `depends_on` → no extra prompts beyond the existing four (update `test_manual_step_unclassified_then_reviewed` queue lengths accordingly).

**End-to-end**:

- `test_proposed_depends_on_notes_reach_written_frontmatter` — mirror `test_proposed_intents_reach_the_written_frontmatter`: canned JSON with `depends_on` + `depends_on_notes`, `create_plan` with `from_description`, assert `parse_plan` and frontmatter text carry the note.
- `test_proposed_step_without_note_accepted_unchanged` — proposal with `depends_on: [1]` and no `depends_on_notes` key succeeds with `{}` and does **not** invoke a second invoker call beyond any unrelated repair (pin: no note-driven retry).
- `test_preserve_on_disk_keeps_depends_on_notes_when_proposal_omits` — same-title iterate merge: on-disk step has notes; new proposal omits the key → preserved; proposal includes `{}` → cleared.
- `test_preserve_on_disk_intersects_notes_with_proposal_depends_on` — on-disk notes for antecedents `{1, 2}`; proposal omits `depends_on_notes` but `depends_on: [1]` only → preserved notes are `{1: …}` (key `2` dropped), and the merge would pass step 1's membership check.

**Negative space**:

- `test_canonical_extraction_produces_no_depends_on_notes` — lift a canonical seed with `Depends on:` lines; every step has `depends_on_notes == {}`.
- `test_merge_sweep_into_steps_produces_no_depends_on_notes` — when foundational sweep appends a consolidation step with a wired `depends_on`, that step's `depends_on_notes` is `{}`.

## Acceptance criteria

- `_render_from_prompt` names optional `depends_on_notes` in the JSON contract in all four A/B prompt arms.
- `_parse_steps_json` stores sanitized notes on `Step.depends_on_notes` and drops keys not in that step's `depends_on` without rejecting the proposal; empty-string values are dropped (silent = absent key).
- Missing or empty `depends_on_notes` in a proposal never triggers `propose_steps_from_claude`'s repair retry.
- `_prompt_one_step` asks an optional per-edge note after `_ask_int_list` when `depends_on` is non-empty; blank answers omit the key.
- A note authored through either path appears in the written plan frontmatter and re-parses through `parse_plan`.
- `_preserve_on_disk_step_fields` keeps on-disk notes across same-title iterate merges when the proposal omits the key (intersected with the proposal's `depends_on`), and adopts the proposal when the key is present.
- `extract_steps_from_canonical` and `merge_sweep_into_steps` remain note-less.
- `rg 'depends_on_notes' plan_tool/create.py` shows only read/carry/write in the authoring paths — no scoring, gating, or content validation; the never-graded allowlist includes this step's carriers.
- All tests listed above pass.

## References

- [Pydantic v2 — Fields](https://docs.pydantic.dev/latest/concepts/fields/) — optional `dict` defaults on `Step`; this step writes the field, not defines it.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — int-key maps in frontmatter for end-to-end frontmatter assertions.
- [Python `typing` — standard library reference](https://docs.python.org/3/library/typing.html) — `dict[int, str]` annotation style already used in `plan_tool/schema.py`.

## Applicable guardrails

- **Plan fence (structural key membership only)** — this step may record notes and carry them on disk; it must not score, rank, or gate on note text or note-on-edge presence. No new retry, warning-as-refusal, or severity change when an edge is silent. Silent = absent key.
- **Plan "## Out of scope", content validation** — parser and wizard store note text verbatim; no length, plausibility, or truth checks. Do not reject placeholder wording.
- **Plan "## Out of scope", requiring notes** — do not require `depends_on_notes` on every edge or on existing plans; partial coverage and `{}` stay valid.
- **Plan Architecture, canonical path** — `extract_steps_from_canonical` stays Claude-free and note-less; do not extend canonical parsing or seeds here.
- **Plan Architecture, foundational sweep** — `merge_sweep_into_steps` stays note-less; do not teach consolidation steps to author notes.
- **Plan Architecture, the trap** — do not add prose that implies notes prove coupling is real; prompt copy should describe what the note is for, not certify edge quality.

## Deferred

- **Interactive step review display (`_review_step_change_types`)** — step 4 renders `depends_on` ids alongside notes at confirm/split time; out of scope here.
- **`PLAN_FORMAT.md` documentation** — step 6.
- **Fixture re-authoring of `audit-trajectory-instrumentation`** — step 5.
- **Reading `depends_on_notes` in cohesion grounding or `SoftEdge` heuristics** — future work; BACKLOG #252 stays structural-only at HEAD. / BACKLOG #257.
