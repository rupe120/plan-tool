> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

## Summary

This step makes the three `create --from-existing` seed renderers carry `Plan.intent` and `Step.intent` into seed text: `plan_tool/scope_out.py`'s `render_carved_seed` / `render_carved_region_seed`, and `plan_tool/reground.py`'s `render_rebaseline_seed`. Each intent renders attached to the thing it describes — a step's value inside that step's block or bullet, the plan's value once as *source* context. The main design decision is **never write `## Outcome`**: `create`'s `_intent_from_seed_outcome` would otherwise stamp the old plan's why onto the next plan. On green, intent-bearing carves and re-baselines hand the next create the attached why; intent-free and placeholder-only (`TODO` / `_(TODO)_`) plans produce the same seed text they produce today.

## Table of Contents

- [Summary](#summary) — the three renderers and the no-Outcome rule.
- [Why](#why) — why the handoff seed is where the why is lost today.
- [Input](#input) — schema fields, collapse helper, Outcome map, signatures.
- [Files (creates vs edits)](#files-creates-vs-edits) — two production modules, two test files.
- [Implementation](#implementation) — attach-to-owner, parameters, rejected paths, gotchas.
- [Tests](#tests) — cases across scope-out and reground suites.
- [Acceptance criteria](#acceptance-criteria) — checkable facts.
- [References](#references) — heading and collapse docs this step leans on.
- [Applicable guardrails](#applicable-guardrails) — plan fence entries that bind here.
- [Deferred](#deferred) — audit prompt, docs, and out-of-scope neighbors.

## Why

`scope-out` and `reground` already hand the next `create` almost everything a re-decomposition needs: titles, files, change type, feature tags, `concept_ids`, disposition, and (for carve) the detail body. They never hand the *why*. The seed is the durable artifact after a carve or re-baseline; once it omits intent, the next create has to re-derive purpose from titles alone. Both verb families end in pure string builders with no Claude call — the cheapest place to attach the field that already sits on `Plan` / `Step`. The trap is promoting that text into `## Outcome`: `plan_tool/create.py:_intent_from_seed_outcome` maps that heading straight into the new plan's `intent`, which would make a carved *slice* inherit the whole source plan's purpose — authoritative and wrong.

## Input

Contracts this step reads and does not own. Confirm each at HEAD before coding.

- **`plan_tool/schema.py:Step` / `plan_tool/schema.py:Plan`.** Each carries an optional `intent: Optional[str] = None` field. Values may be `None`, blank, a one-liner, or contain real newlines — collapse before embedding in markdown.
- **`plan_tool/scope_fence.py:collapse_intent_to_one_line`.** The shared whitespace-collapse helper the plan's Architecture names. Use it; do not mint a third copy (closed #225 / the plan's Reuse bullet).
- **`plan_tool/create.py:_intent_from_seed_outcome`.** Maps a seed's `## Outcome` H2 into the new plan's `intent`. That is why these seeds must write **no** `## Outcome` heading — labeled prose is the handoff; auto-adoption is not.
- **Renderer signatures today.** `render_carved_seed` / `render_carved_region_seed` take `plan_title: str`, not a `Plan` — plan intent has no path in until an explicit parameter lands (the plan's Risks bullet). `render_rebaseline_seed` already takes `plan: Plan` and needs no new plan-intent parameter.
- **`compute_narrow` / `mark_steps_done`.** Survivors already keep step fields via `model_copy` / in-place status flips. No production intent fold required if tests prove preservation; do not invent a clear-`Plan.intent`-on-carve rule this plan does not state.

**What these tests cannot prove.** That a human or Claude reading the seed will rewrite a better Outcome. The contract is: the why is present, attached correctly, and not auto-mapped as Outcome.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — add keyword-only `plan_intent` (default `None`) to `render_carved_seed` and `render_carved_region_seed`; render source-plan and per-step intent via `_scope_block` / intro framing; pass `plan.intent` from `scope_out_step`'s two seed call sites; import `collapse_intent_to_one_line` from `plan_tool.scope_fence`.
  - `plan_tool/reground.py` — extend `_rebaseline_step_bullet` (and the re-baseline intro) so plan/step intents render under the attach-to-owner rule; import `collapse_intent_to_one_line` from `plan_tool.scope_fence` (allowed leaf — do **not** import `detail`, `launcher`, `scope_out`, or `create`).
  - `tests/test_scope_out.py` — renderer + narrow preservation cases; extend `_render` / helpers as needed.
  - `tests/test_reground.py` — re-baseline bullet / plan-intent cases; pin `mark_steps_done` preservation; keep the import-discipline tests green (forbid `detail` / `launcher` / `scope_out`; optionally also forbid `create`).

Deliberate zero-diff production files (reviewer check): `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/review.py`, `plan_tool/scope_fence.py`, `plan_tool/schema.py`, `plan_tool/parser.py`.

## Implementation

### The one rule

**An intent renders attached to the thing it describes, and is never re-pointed at something else.**

- **Step intent** — inside that step's `## Scope to re-plan` block (carve / region) or on that step's bullet (re-baseline done-context, scope-to-re-plan, and deferred alike). Mirror the existing `concept_ids` attach tests (`test_region_seed_keeps_concept_ids_attached_to_source_steps`, `test_rebaseline_seed_does_not_union_concept_ids`).
- **Source plan intent** — once per seed, in the intro framing (or `## Provenance`, not both), labeled as the *source* plan's. Carved / region seeds tell the re-plan to state its **own** Outcome rather than inherit this line. Re-baseline seeds may say the re-decomposition still serves that purpose — different clause, same label family; the asymmetry is the verb difference, not a bug to iron out.
- **Never emit `## Outcome`.** Labeled prose only.

### Approach (recommended shape)

- **Collapse helper.** Thin local wrapper around `collapse_intent_to_one_line` + the fence placeholder omit path: take `Optional[str]`, return `None` when the value is missing, collapses to empty, or is a `TODO` / `_(TODO)_` placeholder; otherwise return the one-line string. Absent / `""` / whitespace / those placeholders → no label. Intent-free and placeholder-only seeds stay unchanged vs today on **all three** renderers (`render_carved_seed`, `render_carved_region_seed`, `render_rebaseline_seed`). `TBD` is outside this named set.
- **`_scope_block`.** When the carved step has a usable collapsed intent, render one labeled line inside the block (one way: under the bold title, before `Files:`). Position is flexible as long as it stays inside the block and vanishes when absent.
- **`_rebaseline_step_bullet`.** Append a collapsed intent suffix beside the existing `— concept_ids: [...]` suffix. Pick one suffix order, state it in the docstring, pin it with a test.
- **`plan_intent=` on carve renderers.** Keyword-only, default `None`. `scope_out_step` passes `plan.intent` from the same disk parse it already uses for the seed. Callers and `_render` that omit the kwarg keep compiling and match today's output when nothing is set.
- **`render_rebaseline_seed`.** Signature stays as at HEAD — read `plan.intent` from the `Plan` it already holds.

### Rejected alternatives

- **Promote intent into `## Outcome`.** Auto-adopts the wrong why via `_intent_from_seed_outcome`; a region has N step intents and no single Outcome to invent.
- **Join a region's step intents into one plan-level line.** Same false "machine prose as author purpose" shape step 1 refuses for merge.
- **Import collapse from `create` / `detail`.** `reground` must not grow those edges (existing import-discipline tests). `scope_fence` is the shared leaf.
- **Hand-roll a second `re.sub(r"\s+", " ", …)`.** Forbidden by the plan Architecture Reuse bullet.

### Gotchas

- **Collapse before embed.** A value containing `\n## Out of scope\n` must not forge an H2 in the seed.
- **Default `plan_intent=None`.** Existing tests that call the carve renderers without it must stay green and unchanged for intent-free inputs.
- **Do not truncate.** Presence-only elsewhere; a long intent renders in full after collapse.
- **One home for the source-plan line.** Intro *or* Provenance, not both.
- **Leave `compute_narrow` / `mark_steps_done` production logic alone** unless a real bug shows intent dropping — pin with tests. Do not clear the narrowed plan's `Plan.intent` in this step; the current plan's seed rule does not require it (see Deferred).
- **Seed-first ordering unchanged.** `scope_out_step` writes the seed before `apply_narrow`; `reground_bridge` writes it before `mark_steps_done`.
- **No content-quality checks.** Render or omit; never compare an intent to detail prose or to code.

### Foundational-logic sweep

Core rule: **attach each intent to its owner in forward-seed text; never rewrite source plan intent as the next Outcome.**

| Site | Disposition |
|---|---|
| `render_carved_seed` / `render_carved_region_seed` / `_scope_block` | **This step** |
| `render_rebaseline_seed` / `_rebaseline_step_bullet` | **This step** |
| `scope_out_step` seed call sites | **This step** — pass `plan_intent=` |
| `compute_narrow` / `mark_steps_done` | **Tests only** — pin field survival |
| `create.py:_intent_from_seed_outcome` | **Zero-diff** — reason these seeds omit `## Outcome` |
| `detail.py:split_step` / `merge_steps` | **Step 1** |
| Conceptual-audit `${intent_block}` | **Step 3** |
| Docs naming the four verb rules | **Step 4** |

## Tests

### Tests for this step

All green before the step is done. Table-drive the five shapes (`None`, `""`, whitespace, one-liner, embedded newline) where useful. Extend existing helpers (`_render`, `_step`, `_plan`) rather than new fixture sprawl.

`tests/test_scope_out.py`:

- `test_scope_block_renders_step_intent` — carved step intent appears inside its `## Scope to re-plan` block.
- `test_scope_block_omits_absent_step_intent` — `intent=None` → no intent label.
- `test_scope_block_omits_blank_step_intent` — whitespace-only → no label.
- `test_scope_block_omits_placeholder_step_intent` — `TODO` / `_(TODO)_` → no label.
- `test_carved_seed_omits_placeholder_plan_and_step_intent` — source plan/step `TODO` → no Intent labels in `render_carved_seed` output.
- `test_carved_region_seed_omits_placeholder_intents` — same for `render_carved_region_seed`.
- `test_carved_seed_keeps_tbd_intent` — source plan/step `TBD` still renders (`TBD` outside fence set).
- `test_step_intent_collapses_to_one_line` — multi-line intent has no newline in the seed body line.
- `test_multi_line_step_intent_forges_no_heading` — intent containing `\n## Out of scope\n` adds no new H2.
- `test_seed_names_the_source_plan_intent` — plan intent appears once, labeled as the source plan's.
- `test_seed_omits_source_plan_intent_when_absent` — `plan_intent=None` → no source-plan intent label.
- `test_source_plan_intent_is_framed_as_source_not_as_the_new_outcome` — framing tells the re-plan to state its own Outcome.
- `test_seed_writes_no_outcome_heading` — neither carve nor region seed contains `## Outcome`.
- `test_region_seed_keeps_intents_attached_to_source_steps` — two different step intents stay in their own blocks.
- `test_region_seed_renders_source_plan_intent_once` — plan intent once, not once per carved step.
- `test_plan_intent_parameter_defaults_to_none` — calling both carve renderers without `plan_intent` still works.
- `test_no_intent_anywhere_renders_no_intent_line` — intent-free carve matches today's label-free text.
- `test_narrow_preserves_survivor_intents` — after `compute_narrow`, every survivor's intent equals the pre-narrow value (including renumbered ids).
- `test_carved_step_and_plan_intents_reach_the_written_seed` — applied `scope_out_step` path; both values appear in the on-disk seed.

`tests/test_reground.py`:

- `test_rebaseline_seed_carries_flagged_step_intents`
- `test_rebaseline_seed_carries_remaining_step_intents`
- `test_rebaseline_seed_carries_deferred_step_intents`
- `test_rebaseline_seed_does_not_union_intents`
- `test_rebaseline_seed_omits_absent_step_intent`
- `test_rebaseline_seed_omits_blank_step_intent`
- `test_rebaseline_seed_omits_placeholder_intents` — plan and/or step `TODO` / `_(TODO)_` → no Intent labels (lives here so reground green-before-done catches a reground-only miss).
- `test_rebaseline_seed_keeps_tbd_intent` — `TBD` still renders (outside fence set).
- `test_rebaseline_step_intent_collapses_to_one_line`
- `test_rebaseline_bullet_suffix_order_is_stable` — intent vs `concept_ids` order matches the docstring.
- `test_rebaseline_seed_names_the_source_plan_intent`
- `test_rebaseline_seed_omits_source_plan_intent_when_absent`
- `test_rebaseline_seed_writes_no_outcome_heading`
- `test_rebaseline_no_intent_anywhere_renders_no_intent_line`
- `test_mark_steps_done_preserves_intents` — status flips only; intents unchanged on marked and unmarked steps.
- Extend `test_reground_still_imports_no_detail_or_launcher` / `test_imports_neither_launcher_nor_detail_at_module_level` — still forbid `detail` / `launcher` / `scope_out`; add `create` to the forbidden set if useful.

**Green-before-done:** every case above plus the existing suites in both files. Loop with `uv run pytest tests/test_scope_out.py tests/test_reground.py -q`; full suite before closing.

## Acceptance criteria

- `render_carved_seed` and `render_carved_region_seed` each accept keyword-only `plan_intent` with default `None`; omitting it leaves intent-free output matching HEAD for the same inputs.
- `inspect.signature(render_rebaseline_seed)` gains no new parameter.
- No `## Outcome` string is emitted by the three seed renderers (`rg '## Outcome' plan_tool/scope_out.py plan_tool/reground.py` stays clean of seed-heading writes).
- `plan_tool/reground.py` still imports neither `detail`, `launcher`, `scope_out`, nor `create`.
- A carved seed with both plan and step intent shows each value once; the step value sits inside that step's `## Scope to re-plan` block; the plan value is labeled as source, not as Outcome.
- A region seed keeps per-step intents in their own blocks and names the source plan intent once.
- A re-baseline seed shows each step's intent only on that step's bullet across done-context, remaining, and deferred sections.
- Intent-free plan + steps produce seed text with no intent labels.
- Placeholder-only (`TODO` / `_(TODO)_`) plan and/or step intents produce seed text with no intent labels on **all three** renderers (`render_carved_seed`, `render_carved_region_seed`, `render_rebaseline_seed`) — same byte contract as intent-free for those labels.
- Embedded newlines collapse to one line and forge no H2.
- After `compute_narrow`, survivor step intents match pre-narrow values; after `mark_steps_done`, every step's intent matches its pre-mark value.
- `uv run pytest tests/test_scope_out.py tests/test_reground.py -q` passes; full suite passes.

## References

- [CommonMark Spec — ATX headings](https://spec.commonmark.org/0.31.2/#atx-headings) — why a raw newline inside an intent can forge a `##` heading in a seed.
- [SEED_FORMAT.md — Outcome](SEED_FORMAT.md) — `## Outcome` is the seed's intent and maps to `Plan.intent` on create; these forward seeds deliberately omit that heading.
- [pytest — parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-drive the five intent shapes across the three renderers.

## Applicable guardrails

- **The plan's "## Plan intent"** — every surviving step after structural work stays true-or-absent; this step's seed handoff must not invent a false why for the next create.
- **The plan's "## Step intent"** — attach the why to the carved / re-baseline subject; do not rewrite the source plan intent as the new Outcome.
- **The plan's "## Out of scope"** — do not reopen shipped intent authoring/fence work; do not add content validation; leave #212 and #161/#162 alone. This step only attaches existing fields into seed prose.

## Deferred

- **Split / merge intent fold** — step 1 owns `plan_tool/detail.py`.
- **Conceptual-audit `${intent_block}`** — step 3 owns `plan_tool/review.py` / `plan_tool/prompts/plan-audit.md`.
- **Documenting the four verb rules** — step 4 owns `PLAN_FORMAT.md` and the parent Deferred close-out.
- **Clearing or rewriting the narrowed plan's `Plan.intent` on carve** — not stated in this plan's settled seed rule; survivors keep step intents via existing `model_copy`. If carve should clear plan-level intent because the un-narrowed purpose may over-claim, that is a separate design decision → `BACKLOG.md` or a follow-up plan edit, not a silent add here.
- **Intent lines in `_confirm_scope_out` / `_confirm_reground`** — operator prompt surface outside this step's seed contract.
- **Exporting a shared "safe one-line or None" helper from `scope_fence`** — both modules can call `collapse_intent_to_one_line` today; a public wrapper would edit `plan_tool/scope_fence.py`, which is out of this step's file list → reconcile / BACKLOG if the local wrappers grow.
- **BACKLOG #212** — named in the plan's Out of scope / Deferred.
