> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Intent Structural Propagation
intent: After every structural mutation and every conceptual-audit call, every surviving
  step's `intent` is either **true of that step** or **absent** — never a quietly
  false carry-over — and the conceptual audit **receives** the plan/step intents its
  "stay inside the declared scope contract" rule already assumes.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Make split drop intent and merge keep it only when every member agrees
  intent: After a split or merge, every surviving step carries an intent that is still
    true of it, or none at all.
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/intent-structural-propagation/01-make-split-drop-intent-merge-keep-only.md
  status: done
- id: 2
  title: Carry plan and step intent into the three forward-seed renderers
  intent: A carved or re-baseline seed hands the next create the why attached to the
    thing it describes, without rewriting the source plan intent as the new Outcome.
  files:
  - plan_tool/scope_out.py
  - plan_tool/reground.py
  - tests/test_scope_out.py
  - tests/test_reground.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/intent-structural-propagation/02-carry-plan-step-intent-three-forward.md
  status: done
- id: 3
  title: Put plan and step intents into the conceptual-audit prompt
  intent: The conceptual audit can see the plan and step intents its stay-inside-scope
    rule already assumes, instead of only the frontmatter-stripped body.
  files:
  - plan_tool/review.py
  - plan_tool/prompts/plan-audit.md
  - tests/test_review.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/intent-structural-propagation/03-put-plan-step-intents-conceptual-audit.md
  status: done
- id: 4
  title: Document the four intent rules and discharge the parent Deferred
  intent: Operators and later audits can find the split, merge, forward-seed, and
    audit intent contracts in one place, and the parent plan's open carve is closed
    without inventing a second intent program.
  files:
  - PLAN_FORMAT.md
  - docs/implementation-plans/archive/2-intent-scope-fence.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/intent-structural-propagation/04-document-four-intent-rules-discharge.md
  status: done
---
# Intent Structural Propagation

## Overview

`Plan.intent` and `Step.intent` exist and reach `detail`/`run`, but the four
structural verbs either leave intent unspecified (so the next edit copies it
blindly) or drop it on the floor when writing the next `create
--from-existing` seed. The conceptual audit still strips frontmatter, so the
prompt rule that says "Stay inside the declared scope contract" never sees
the plan/step intents that rule already assumes. This plan closes that
residual only.

## Problem statement

A stale or missing why is worst exactly where structure changes: split can
duplicate a parent's purpose onto two half-steps; merge can keep a member's
why over a survivor that now does more; carve/re-baseline seeds hand the next
`create` every field except the why; the conceptual audit is the creep
detector and is the one consumer a frontmatter field cannot reach by accident.

## Architecture

**One invariant.** Every surviving step ends with an intent that is true of
it, or with none. Prefer absent over false.

**Settled verb rules** (from the carve; load-bearing — do not reopen):

| Verb | Rule |
|---|---|
| split | never copy target intent onto halves |
| merge | keep only if every member's intent is the same *usable* value (fence presence set — `TODO` / `_(TODO)_` count as absent; `TBD` is outside this set); else clear |
| scope-out / reground seeds | attach intent to its owner; source plan intent ≠ new `## Outcome`; drop fence presence non-values and collapse newlines before embed |
| conceptual audit | dynamic `${intent_block}` only; empty under the fence presence set → byte-identical prompt |

**Ordering.** Pin split/merge first (in-plan structure), then forward-seed
renderers (handoff), then audit delivery (consumer). Each layer is
independently shippable and testable.

**Reuse.** Collapse/one-line helpers already used by the fence renderer —
call them; do not invent a third normalization copy (see closed #225). For
this plan's three surfaces (merge, forward seeds, conceptual audit),
**"empty" means the fence omit set**: `None`, blank/whitespace after
collapse, and `TODO` / `_(TODO)_`-style placeholders as
`scope_fence._is_placeholder_section` / `_render_intent_section` already
define. That is presence, not content validation. **`TBD` is outside this
named set** — `is_usable_intent` also drops bare `TBD` for the advisory
presence smell, but structural surfaces must use the fence omit path so
they do not silently clear `TBD`. (`detail` already imports `review` for
other reasons; that is not why we avoid `is_usable_intent` here.)

## In scope

1. **`split` / `merge` intent rules** on the step transforms
   (`detail.py:split_step` / `merge_steps` and their create-side ownership
   helpers). Settled contracts (do not re-litigate):
   - **Split never copies** the target's intent onto either half.
   - **Merge keeps** an intent only when every folded member states the
     *same usable* intent (placeholders count as absent); otherwise clears it.
2. **Forward-seed renderers** for `scope-out` and `reground`
   (`render_carved_seed`, `render_carved_region_seed`,
   `render_rebaseline_seed`). Settled contracts:
   - An intent renders **attached to the thing it describes** — a carved
     step's intent rides its own scope block; the source plan's intent is
     labeled as the *source* plan's, never rewritten as the new effort's
     `## Outcome`.
   - Absent / blank / whitespace / placeholder values are dropped; multi-line
     values are collapsed to one line before seed text (no forged headings).
   - `compute_narrow` / `mark_steps_done` need no production edit if they
     already copy step fields through — pin with tests.
3. **Conceptual-audit prompt delivery** (`review.py` +
   `prompts/plan-audit.md`): a dynamic intent block; **all new prompt text
   lives inside the block**. A plan with no usable intents renders
   **byte-identical** audit prompts to today.

## Out of scope / Non-goals

- Re-authoring schema, presence check, `create` Outcome mapping, wizard
  proposal, or fence rendering into `detail`/`run` — shipped.
- **Any validation of intent content** — quality, agreement with `## Why`,
  length caps, gates, exit-code flips. Permanently refused (same fence as
  `2-intent-scope-fence` / CLAUDE.md intent record). Presence non-values
  (`None`, blank, `TODO` / `_(TODO)_` placeholders) are the existing fence
  empty set, not content validation. `TBD` is outside this plan's named set.
- **BACKLOG #212** (`apply_finding` leaving a stale intent) — deliberately
  fenced out of the structural-verb set; file/keep separate.
- #161/#162 seed/backlog scope-contract prompt work.
- New CLI verbs, migrations, backfills, or requiring intent on existing plans.
- Changing required detail H2s at either grade.

## Allowed behavior changes

- Split/merge frontmatter after a structural edit: surviving steps carry a
  defensible intent or none.
- Carved / re-baseline seeds may gain labeled intent lines when source
  intents are usable under the fence presence set; intent-free and
  placeholder-only (`TODO` / `_(TODO)_`) plans produce **identical** seed
  text to today.
- Conceptual-audit prompts gain an intent block only when at least one
  fence-usable intent is present.

## Allowed reorganization

None. Edits stay in the existing transform and renderer owners.

## Verification

- Intent-free and placeholder-only plans: byte-identical split/merge
  frontmatter paths (no new `intent:` keys), byte-identical forward seeds,
  byte-identical audit prompts.
- Split of an intent-bearing step → neither half carries the parent's
  intent.
- Merge of matching intents → survivor keeps it; mixed/blank → cleared.
- Carve/re-baseline of an intent-bearing plan → source plan intent labeled
  as source; per-step intents attached to their blocks; newlines cannot
  forge headings.
- Intent-bearing plan's audit prompt contains the intents; bodyless plan
  still returns `None` from the renderer (existing contract).
- No test asserts intent *quality* or length beyond one-line collapse.

## Stop / defer

- #212 and any non-structural stale-intent path → `BACKLOG.md`.
- Intent content validation proposals → reject; cite the permanent fence.
- Further audit consumers beyond conceptual audit → new backlog entry.

## References

- [string.Template — Python 3.13 Library Reference](https://docs.python.org/3.13/library/string.html#template-strings) — Documents `Template.safe_substitute` and `${…}` placeholders — the exact mechanism for injecting a dynamic `${intent_block}` into `plan-audit.md` without changing intent-free prompt bytes.
- [YAML 1.2.2 Specification](https://yaml.org/spec/1.2.2/) — Normative rules for scalars, nulls, and multiline values that govern how optional `intent:` frontmatter keys must serialize, collapse, or be omitted after split/merge.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Primary Python API for `safe_load`/`dump` of plan frontmatter, used when verifying intent-free paths stay free of new `intent:` keys and when rewriting surviving steps.
- [CommonMark Spec — ATX headings](https://spec.commonmark.org/0.31.2/#atx-headings) — Defines when a `#`-prefixed line becomes a heading, which is why seed and audit renderers must collapse multi-line intents before embedding them in markdown.
- [Claude Prompting Best Practices (Anthropic)](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — Official guidance on structuring variable prompt inputs (including XML-tagged blocks) so a conceptual-audit intent block stays isolated from static template prose.
- [Pydantic `model_copy` — API](https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel.model_copy) — How `Step` / `Plan` transforms override selected fields (`model_copy(update=…)`) without blind field copy — the live split/merge assembly path.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

See the scope contract above (**In scope** through **Stop / defer**). Explicitly:
shipped intent authoring/fence work; #212; content validation beyond the
shared presence non-value set; #161/#162.

## Risks

- Someone "helpfully" copies intent on split by analogy with `change_type` —
  the tests are the contract.
- Forward-seed parameter gaps (`render_carved_seed` takes `plan_title: str`,
  not `Plan`) — plan intent needs an explicit new parameter, not a silent
  omission.
- Putting static intent prose in `plan-audit.md` would change every prompt
  even for intent-free plans — keep all new text inside the dynamic block.

## Testing

Green-before-done on the three surfaces. Intent-free fixtures must stay
byte-identical. Table-drive the five legal intent shapes (`None`, `""`,
whitespace, one-liner, embedded newline) on merge and on seed render.
No content-quality assertions.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- Split/merge obey the settled rules; pinned by tests.
- The three forward-seed renderers carry plan/step intent per the attach-to-
  owner rule; intent-free and placeholder-only output unchanged on all three.
- Conceptual audit prompt receives intents when present and is unchanged
  when absent.
- Permanent no-validation fence holds in code and tests.
- Docs: `PLAN_FORMAT.md` / structural-verb notes name the four rules; the
  parent plan's Deferred / any new backlog entry is reconciled on ship.

## Deferred

- BACKLOG #212 (`apply_finding` stale intent).
- #161/#162 scope-contract audit block.
- Any further prompt consumers.
- Unifying `scope_fence` placeholder omit with `is_usable_intent`'s broader `TBD` forms (or narrowing `TBD` out of the presence smell) — shipped predicates differ; this plan pins structural surfaces to the fence set and leaves alignment to BACKLOG #227.
