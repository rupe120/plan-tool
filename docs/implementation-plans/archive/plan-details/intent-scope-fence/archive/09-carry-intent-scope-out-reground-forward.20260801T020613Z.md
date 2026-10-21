> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Carry intent into the scope-out and reground forward seeds

## Summary

This step makes the three `create --from-existing` seed renderers carry step 1's `Plan.intent` and `Step.intent` into their output: `plan_tool/scope_out.py`'s `render_carved_seed` and `render_carved_region_seed`, and `plan_tool/reground.py`'s `render_rebaseline_seed`. The main design decision is that **an intent renders attached to the thing it describes and is never re-pointed at a different thing** — a carved step's intent rides its own `## Scope to re-plan` block, and the source plan's intent renders once, labeled as the *source* plan's, never as the new effort's `## Outcome`. The second decision is that a blank or multi-line value is squeezed to one line or dropped before it reaches the seed, because a raw newline in a markdown seed can forge a heading. Neither `compute_narrow` nor `mark_steps_done` needs a production edit — both already copy every other step field through — so their intent rules ship as stated contract plus tests. On green, a carve or a re-baseline hands the next `create` the why behind each carried step, and a plan carrying no intent anywhere produces the same seed text it produces today.

## Table of Contents

- [Summary](#summary) — what ships, the attached-to-its-owner rule, and the result on green.
- [Why](#why) — the two structural verbs whose forward seeds drop the why on the floor.
- [Input](#input) — the five contracts this step reads and does not own, and what the tests cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — four edited files, no new files.
- [Implementation](#implementation) — the two propagation rules, the three renderers, the rejected alternatives, and eight gotchas.
- [Tests](#tests) — approx. 30 new cases plus one extended existing case, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — greps and equalities a reviewer can run.
- [References](#references) — the YAML, CommonMark, and pytest behavior this step leans on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the two places breaking them is tempting.
- [Deferred](#deferred) — what steps 2, 6, 8, and 10 own, and the two things routed out.

## Why

`scope-out` and `reground` are two of the four structural verbs the plan owes a propagation rule (step 8 covers the other two, split and merge). Both end by writing a **forward seed** — a `create --from-existing` input that becomes the next plan. That seed already carries almost everything a re-decomposition needs: the carried step's title, files, change type, feature tags, `concept_ids`, scope disposition, and full detail body. What it never carries is the *why*. So the one artifact whose entire job is to hand work forward drops exactly the field this plan exists to make durable, and the next `create` run re-derives each step's purpose from its title — the defect the plan opens with, reappearing at the handoff point where the loss is permanent. The seed is also the cheapest place to fix it: all three renderers are pure string builders with no Claude call and no file IO, and the values are already sitting on the `Step` and `Plan` objects each renderer holds.

## Input

Five contracts this step reads and does not own. Read each off HEAD before you start; where a landed name differs from a name below, the landed name wins.

- **Step 1's two schema fields.** `Plan.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD) and `Step.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), each `Optional[str] = None`, storing whatever YAML handed over with no stripping, no cap, and no validator. All five shapes are legal parses and reach these renderers: `None`, `""`, `"   "`, a normal one-liner, and a value with real newlines. This step decides what each one renders.
- **`plan_tool/scope_out.py`'s renderer signatures.** `render_carved_seed` and `render_carved_region_seed` are keyword-only and take **`plan_title: str`, not a `Plan`** — so the plan-level intent has no path into them today and needs a new parameter. Both delegate the per-step body to the shared `_scope_block` helper, which the region renderer calls once per carved step, so a change there lands in both seeds at once.
- **`plan_tool/reground.py:render_rebaseline_seed`'s signature.** It already takes `plan: Plan` plus `flagged_ids`, so both `plan.intent` and every `step.intent` are already in hand — **no signature change**. Its three per-step blocks (`_rebaseline_done_context_block`, `_rebaseline_scope_block`, `_rebaseline_deferred_block`) all render through the one `_rebaseline_step_bullet` helper.
- **`compute_narrow`'s survivor copy.** In `plan_tool/scope_out.py:compute_narrow`, each survivor is built with `s.model_copy(update={"id": ..., "depends_on": ..., "detail": ...})` and the narrowed plan with `plan.model_copy(update={"steps": ..., ...})`. Only the named keys change, so a **survivor's** intent already carries through a carve untouched — that half ships as a stated contract plus a pinning test, with no code edit, the same shape step 8 uses for its split rule. The **plan's own** intent is different: the plan-altitude rule in `## Architecture` requires a carve to **clear** `Plan.intent`, and because `model_copy` touches only the named keys, that clearing does **not** happen for free. Add `"intent": None` to the narrowed plan's `model_copy` update — a real production edit to `compute_narrow`, not a no-edit contract. `plan_tool/reground.py:mark_steps_done` stays a no-edit contract: it sets `step.status` and nothing else, and a re-baseline is not a carve.
- **`plan_tool/reground.py`'s import fence.** `tests/test_reground.py:test_imports_neither_launcher_nor_detail_at_module_level` and `test_reground_still_imports_no_detail_or_launcher` grep the module's own source and fail on any `plan_tool.detail`, `plan_tool.launcher`, or `plan_tool.scope_out` import. That closes the door on borrowing a shared one-line helper from `plan_tool/create.py` or `plan_tool/detail.py` here (see [Implementation](#implementation)).

**What the tests cannot prove.** Nothing here checks whether a carried intent is a *good* one, or whether it still describes the carved work accurately. The suite proves the text arrives, arrives on one line, arrives attached to its own step, and never arrives as a heading. Quality is deliberately unjudged (see [Applicable guardrails](#applicable-guardrails)).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — add a keyword-only `plan_intent` parameter to `render_carved_seed` and `render_carved_region_seed`; render the source-plan line in each renderer's intro block; render the step intent inside `_scope_block`; add the module's one-line normalizer; pass `plan.intent` from `scope_out_step`'s two seed call sites; state the survivor rule in `compute_narrow`'s docstring.
  - `plan_tool/reground.py` — render the source-plan line in `render_rebaseline_seed`'s intro block; append the step intent in `_rebaseline_step_bullet`; add the module's one-line normalizer; state the mark-done rule in `mark_steps_done`'s docstring.
  - `tests/test_scope_out.py` — approx. 17 new cases across the renderer, narrow, and orchestrator sections.
  - `tests/test_reground.py` — approx. 13 new cases plus one extended existing case.

## Implementation

**What must be true on green:** a carved step's intent and a re-baselined step's intent appear in the seed inside the block that describes that step and nowhere else; the source plan's intent appears once, labeled as the source plan's; a plan and steps carrying no intent render the seed text they render today; and no seed contains an `## Outcome` heading.

### The one rule, stated two ways

**An intent renders attached to the thing it describes, and is never re-pointed at a different thing.** That is the seed-altitude form of the plan's propagation contract, and it settles both verbs:

- **scope-out.** A carve changes *which steps exist*, never what a surviving step is *for*. So every survivor's intent carries unchanged (no edit — `compute_narrow` copies it), and the carved step's intent travels into its own `## Scope to re-plan (source step N)` block in the seed. The **narrowed plan's own `Plan.intent` is cleared**, per the plan-altitude rule in `## Architecture`: a carve removes a step, so a plan-level intent written for the un-narrowed plan may now over-claim — the same "authoritative but wrong" hazard the Risks section names, one altitude up. Clearing is the default; a plan keeps its intent through a carve only by stating and pinning why its purpose survives the loss.
- **reground.** Marking a step `done` is a lifecycle transition, not a change of purpose. So every step's intent survives `mark_steps_done` unchanged (no edit), and under the `re-baseline` disposition each rendered step's intent rides its own bullet — done-context, scope-to-re-plan, and parked-deferred alike.

The closest in-repo precedent is `concept_ids`, which both renderers already carry under exactly this rule: `tests/test_scope_out.py:test_region_seed_keeps_concept_ids_attached_to_source_steps` and `tests/test_reground.py:test_rebaseline_seed_does_not_union_concept_ids` both exist to pin "attached to its own source step, never merged across steps." Mirror their shape.

### The three renderers

- **`_scope_block` (both scope-out seeds).** Render the carved step's intent as a labeled line inside the block. One way: `Intent: <one line>` directly under the bolded title, before `Files:` — the why reads first, ahead of the footprint. The exact position is yours as long as it sits inside the block and vanishes when there is no intent.
- **`_rebaseline_step_bullet` (all three re-baseline blocks).** Append the intent to the existing one-line bullet, next to the `— concept_ids: [...]` suffix it already builds. Pick one order for the two suffixes, state it in the docstring, and pin it with a test — an unstated order is the kind of thing a later edit flips silently.
- **The source plan's intent, in all three seeds.** Render one labeled line in each renderer's intro block, beside the existing "This is a `plan-tool create --from-existing` input…" framing sentence. It must carry a short clause saying whose intent it is, because the two verbs stand in different relationships to it:
  - **carved seed / region seed** — the plan the region was carved *out of*. The carved region serves part of that purpose, so the line says the re-plan states its own Outcome rather than inheriting this one.
  - **re-baseline seed** — the same effort, re-decomposed from current code, so the line says the re-decomposition still serves it.

  Same label, one differing clause. That asymmetry is deliberate: it is the difference between the two verbs, not an inconsistency to iron out.

### Rejected alternatives

- **Promote an intent into an `## Outcome` H2 so the next `create` adopts it as the new plan's intent.** This is the tempting one, because step 6 lifts a seed's `## Outcome` into `Plan.intent` and it would close a satisfying loop. Refuse it here for three reasons. A **region seed carries N step intents** and no single one is the region's Outcome, so the renderer would have to invent one. A **carved seed's source plan intent over-claims** — it describes the whole plan, and the seed re-plans a slice, which is exactly the "authoritative but wrong" shape the plan's Risks section names. And it would make this step depend on step 6's lift, which step 9 does not declare in `depends_on`. Writing the intent as labeled prose gets it in front of the model that decomposes the seed without minting a claim about a plan that does not exist yet.
- **Join a region's step intents into one plan-level line.** Same failure as step 8's rejected `"; "` join for merge: it manufactures machine prose that then reads as an author's stated purpose.
- **Import a shared one-line helper from `plan_tool/create.py` or `plan_tool/detail.py`.** `plan_tool/reground.py` cannot — two existing tests grep its source for exactly those edges. Give each module its own small normalizer instead (see the gotcha below) and route the consolidation out.

### Gotchas — the parts not free to vary

- **Collapse before rendering; a raw newline is a heading injection.** A step intent containing `\n## Out of scope\n` renders a real H2 into a `create --from-existing` seed, silently forging a scope-contract section in the next plan's input. Replace every run of whitespace (newlines included) with a single space, then strip — the same shaping step 6 settled for the plan-level lift. Read what step 6 landed and match its rule; do not invent a second one.
- **Absent, empty, and whitespace-only all render nothing.** No label, no blank line, no `Intent: ` with nothing after it. This is the clearing behavior at seed altitude, and it is what keeps the no-intent case producing today's text.
- **`plan_tool/reground.py` gets its own normalizer, always.** Both `render_rebaseline_seed`'s docstring and the two import-discipline tests already record why the module mirrors rather than imports. `plan_tool/scope_out.py` may reuse a suitable existing helper if one is public on a module it already imports (it imports `plan_tool.detail`); otherwise it gets its own copy too. Either way, name it for what it does — `_one_line_intent(value) -> str | None`, returning `None` for absent/blank.
- **The new `plan_intent` parameter is keyword-only with a `None` default.** Every existing caller and test helper (including `tests/test_scope_out.py:_render`) constructs these renderers without it, and they must keep compiling and producing the same output.
- **`render_rebaseline_seed`'s signature does not change.** It already takes the whole `Plan`. Adding a parallel `plan_intent=` parameter would create two sources for one value.
- **Do not enforce step 2's length cap.** Step 2's advisory check judges presence and length; rendering is not checking. A 500-character intent renders in full, collapsed to one line. Truncating here would create a second, silent rule for the same field.
- **Pick one home for the source-plan line.** The intro block or `## Provenance`, not both. Two copies of the same value in one seed is the divergence risk the plan's Risks section names, scaled down.
- **`scope_out_step` and `reground_bridge` both re-parse the plan from disk** before rendering, so the intent that reaches the seed is the on-disk value at carve/re-ground time, not a caller's in-memory `Plan`. Keep the value read from that same parse — the two orchestrators already treat the disk parse as the only trustworthy source.
- **Seed-first ordering is unchanged.** `scope_out_step` writes the seed before `apply_narrow`, and `reground_bridge` writes it before `mark_steps_done`. Nothing here reorders that.

## Tests

### Tests for this step

**`tests/test_scope_out.py`** — approx. 17 new cases, landing in the existing renderer, preview-math, and orchestrator sections.

- `test_scope_block_renders_step_intent` — a carved step with an intent shows it inside its `## Scope to re-plan` block.
- `test_scope_block_omits_absent_step_intent` — `intent=None` renders no label.
- `test_scope_block_omits_blank_step_intent` — `"   "` renders no label.
- `test_step_intent_collapses_to_one_line` — a three-line intent renders with no newline inside it.
- `test_multi_line_step_intent_forges_no_heading` — an intent containing `\n## Out of scope\n` produces no new H2 in the seed.
- `test_seed_names_the_source_plan_intent` — the plan's intent appears once, under a label naming it as the source plan's.
- `test_seed_omits_source_plan_intent_when_absent` — `plan_intent=None` renders no label.
- `test_source_plan_intent_is_framed_as_source_not_as_the_new_outcome` — the rendered line carries the clause telling the re-plan to state its own Outcome.
- `test_seed_writes_no_outcome_heading` — neither seed contains `## Outcome`.
- `test_region_seed_keeps_intents_attached_to_source_steps` — two carved steps with different intents; each appears only inside its own block.
- `test_region_seed_renders_source_plan_intent_once` — a region seed names the plan intent one time, not once per carved step.
- `test_plan_intent_parameter_defaults_to_none` — calling `render_carved_seed` and `render_carved_region_seed` without `plan_intent` still renders.
- `test_no_intent_anywhere_renders_no_intent_line` — a plan and carved step with no intent produce output with no intent label of any kind.
- `test_intent_rendering_is_deterministic` — two renders of the same input are equal.
- `test_narrow_preserves_survivor_intents` — after `compute_narrow`, every survivor's intent is unchanged, including renumbered ones.
- `test_narrow_clears_plan_intent` — the narrowed plan's own `Plan.intent` is cleared by the carve, per the plan-altitude rule in `## Architecture`.
- `test_carved_step_and_plan_intents_reach_the_written_seed` — through `scope_out_step`'s applied path, both values appear in the seed on disk.

**`tests/test_reground.py`** — approx. 13 new cases plus one extended existing case.

- `test_rebaseline_seed_carries_flagged_step_intents` — done-context bullets show each flagged step's intent.
- `test_rebaseline_seed_carries_remaining_step_intents` — scope-to-re-plan bullets show theirs.
- `test_rebaseline_seed_carries_deferred_step_intents` — parked bullets show theirs.
- `test_rebaseline_seed_does_not_union_intents` — a step's intent never appears on another step's bullet.
- `test_rebaseline_seed_omits_absent_step_intent` — `intent=None` adds no suffix.
- `test_rebaseline_seed_omits_blank_step_intent` — `"   "` adds no suffix.
- `test_rebaseline_step_intent_collapses_to_one_line` — a multi-line intent stays inside its bullet.
- `test_rebaseline_bullet_suffix_order_is_stable` — the intent and `concept_ids` suffixes render in the stated order.
- `test_rebaseline_seed_names_the_source_plan_intent` — the plan's intent appears once, labeled as the source plan's.
- `test_rebaseline_seed_omits_source_plan_intent_when_absent` — no label when unset.
- `test_rebaseline_seed_writes_no_outcome_heading` — the seed contains no `## Outcome`.
- `test_rebaseline_no_intent_anywhere_renders_no_intent_line` — the legacy case renders today's text.
- `test_mark_steps_done_preserves_intents` — the actuator flips status only; every step's intent survives, including steps outside the marked set.
- `test_bridge_round_trip_preserves_intents` — re-parse the written plan after an applied `reground_bridge`; every intent is unchanged.
- **Extend `test_reground_still_imports_no_detail_or_launcher`** — add `plan_tool.create` to the forbidden-import list, since that module is the new temptation once a one-line helper lands there in step 6.

**Green-before-done gate:** every case above, plus the existing suites in both files, must pass before this step is finished. Run `uv run pytest tests/test_scope_out.py tests/test_reground.py -q`, then the full suite.

## Acceptance criteria

- `render_carved_seed` and `render_carved_region_seed` each accept a keyword-only `plan_intent` with a `None` default; called without it they render as they do today.
- `inspect.signature(render_rebaseline_seed).parameters` is unchanged from HEAD — no new parameter.
- `rg '## Outcome' plan_tool/scope_out.py plan_tool/reground.py` returns nothing.
- `rg 'plan_tool\.(detail|launcher|scope_out|create)' plan_tool/reground.py` returns nothing.
- A carved seed rendered from a plan and step that both carry an intent contains each value exactly once, and the step's value appears inside its own `## Scope to re-plan (source step N)` block.
- A region seed rendered from two carved steps with different intents keeps each value inside its own block and names the source plan's intent once.
- A re-baseline seed rendered from a plan whose done-context, remaining, and deferred steps each carry an intent shows each value on its own bullet and on no other.
- A seed rendered from a plan and steps with `intent=None` contains no intent label anywhere.
- An intent containing embedded newlines renders on one line, and the rendered seed gains no H2 heading from it.
- After `compute_narrow`, every survivor's intent equals its pre-narrow value and the narrowed plan's `Plan.intent` is cleared; after `mark_steps_done`, every step's intent equals its pre-mark value.
- `uv run pytest tests/test_scope_out.py tests/test_reground.py -q` is green, and the full suite passes with no edits to existing plan fixtures.

## References

- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — scalar styles and line folding, which decide what a "one line" intent is once it round-trips through a plan file and reaches these renderers.
- [ATX headings — CommonMark Spec](https://spec.commonmark.org/0.31.2/#atx-headings) — the rule that makes a line starting with `##` a heading, and therefore why a raw newline inside an intent can forge a section in a seed.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven cases for the absent / empty / whitespace-only / one-line / multi-line intent combinations, repeated across three renderers.
- [Be clear, direct, and detailed — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — phrasing the source-plan-intent line so it reads as context for the re-plan rather than as an instruction to adopt it.

## Applicable guardrails

- **"Nothing becomes required at parse time, and no plan on disk is migrated."** This binds every renderer here: an absent or blank intent must produce no label and no placeholder line, so a plan with no intent carves and re-grounds to the seed text it produces today. Two acceptance criteria exist to check exactly that.
- **"No step ships a check comparing an intent against prose or against a diff."** This step renders; it never judges. The temptation sits in the re-baseline seed, where each flagged step's intent lands one bullet away from the code that was actually built — comparing the two is precisely the agreement check the plan bans, and precisely what "already implemented — the code is the ground truth" invites. Render both, compare neither.
- **The fence's allowed behavior changes ("two optional frontmatter fields; one advisory finding class; rendered input across five templates").** These seeds are the propagation the plan's Architecture section requires for two of the four structural verbs, and they add no field, no finding class, and no check. The second tempting spot: neither `_confirm_scope_out` nor `_confirm_reground` gains an intent line — a change to an operator-facing confirm prompt is outside what the fence allows.
- **"Every rule must be able to clear the field."** At seed altitude the clearing form is rendering nothing rather than writing an empty label, and that is what a blank or absent value does.

## Deferred

- **Split's and merge's intent rules** — step 8 owns them in `plan_tool/detail.py`; this step covers only the other two structural verbs.
- **The advisory presence, placeholder, and length check** — step 2 owns it in `plan_tool/review.py`. Nothing here validates a rendered intent.
- **Lifting a seed's `## Outcome` into the next plan's `Plan.intent`** — step 6 owns that lift. These seeds deliberately write no `## Outcome`, so nothing they emit is auto-adopted as a new plan's intent.
- **Documenting the four propagation rules** — step 11 owns `PLAN_FORMAT.md`. This step records its two rules in the touched docstrings only.
- **Consolidating the one-line collapse copies** — after this step the same two-line squeeze exists in `plan_tool/create.py` (step 6), `plan_tool/detail.py` (step 8), `plan_tool/scope_out.py`, and `plan_tool/reground.py`. Merging them needs a shared leaf below all four and touches modules outside this step's file list; route it to `BACKLOG.md` or to reconcile. The mirror is the repo's standing answer where importing would cost a module its leaf status.
- **Re*writing* a narrowed plan's `Plan.intent` to describe what the plan now does** — this step **clears** it on a carve (see `## Implementation`), which is the plan's stated rule; composing a *new* plan-level intent from the survivors would require judging what the narrowed plan is for, and that is its own `BACKLOG.md` entry.
- **Intent in the two confirm prompts** (`plan_tool/scope_out.py:_confirm_scope_out`, `plan_tool/reground.py:_confirm_reground`) — an operator-facing surface change beyond the plan's allowed behavior changes.
- **The CLI operator summaries** (`plan_tool/cli/scope_out_cmd.py`, `plan_tool/cli/convergence_cmd.py`, `plan_tool/cli/review_actions.py`) — not in this step's file list and needing no edit; they read the frozen result objects, which gain no field here.
