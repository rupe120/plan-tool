> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

## Summary

This step delivers `Plan.intent` and `Step.intent` into the conceptual-audit prompt. Today `plan_tool/review.py:render_plan_audit_prompt` builds plan input only from `_collect_plan_body`, which strips frontmatter, so the stay-inside-scope rule never sees the Outcome that lives in those fields. Add one formatter (`_format_intent_block`), one `${intent_block}` slot in `plan_tool/prompts/plan-audit.md`, and one `safe_substitute` keyword. The main design decision is **every new word lives inside the dynamic block** — never in the template's static prose — so an intent-free plan keeps the same prompt it has today. On green, an intent-bearing plan's audit sees plan and step purpose framed as scope input; an intent-free plan's audit is unchanged.

## Table of Contents

- [Summary](#summary) — formatter, template slot, and the all-text-inside-the-block rule.
- [Why](#why) — why frontmatter intent never reaches this consumer today.
- [Input](#input) — schema fields, render signature, Template contract, sibling block shape.
- [Files (creates vs edits)](#files-creates-vs-edits) — three edits, no new files.
- [Implementation](#implementation) — formatter shape, template placement, rejected paths, gotchas.
- [Tests](#tests) — formatter and prompt cases in `tests/test_review.py`.
- [Acceptance criteria](#acceptance-criteria) — checkable facts.
- [References](#references) — Template and heading docs this step leans on.
- [Applicable guardrails](#applicable-guardrails) — plan fence entries that bind here.
- [Deferred](#deferred) — docs, other prompts, and out-of-scope neighbors.

## Why

The conceptual audit is where scope creep shows up — a completeness pass proposing work the author fenced out — and it is the one consumer a frontmatter field cannot reach by accident. `render_plan_audit_prompt` feeds the judge `_collect_plan_body`'s markdown only. The prompt's `## Rules` already says **Stay inside the declared scope contract** and names Outcome among the bounds. That Outcome is exactly what `Plan.intent` carries, and the prompt never receives it. Detail and run already see intent through the fence renderer; this step closes the same gap for the audit.

## Input

Contracts this step reads and does not own. Confirm each at HEAD before coding.

- **`plan_tool/schema.py:Plan` / `plan_tool/schema.py:Step`.** Each carries an optional `intent: Optional[str] = None` field. All five shapes are legal and reach the formatter: `None`, `""`, whitespace-only, a one-liner, and a value with real newlines. `TODO` / `_(TODO)_` are fence presence non-values (`TBD` is outside this plan's named set).
- **`render_plan_audit_prompt`'s early return.** It already takes the parsed `plan`, so both fields are in hand with no re-parse and no new parameter. First act is `_collect_plan_body(plan_path)`; `None` means skip the Claude call. A plan with intent but no body must still return `None` (`TestCheckPlanAudit::test_render_prompt_returns_none_for_bodyless_plan`).
- **`string.Template.safe_substitute`.** An unsupplied `${name}` stays in the prompt as literal text — the new key must be passed. Substitution is one pass, so a `$` or `${…}` inside an intent value is never re-expanded.
- **Sibling empty-block shape.** `_format_carried_findings_block` and `_format_detail_bundle_status_block` put framing inside the returned string and return `""` when empty, so the shared static template stays the same for every plan. Copy that shape.
- **Call sites.** `render_plan_audit_prompt` is called from `check_plan_audit` and `audit_plan_until_stable` inside `plan_tool/review.py` only. Completeness reaches the audit through those; no CLI file changes.
- **`plan_tool/scope_fence.py:collapse_intent_to_one_line`.** The shared collapse helper the plan's Architecture names. Import and use it; do not mint a third copy.

**What these tests cannot prove.** That a live judge narrows findings because of the block. They prove the text is delivered and the prompt stays well-formed.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add `_format_intent_block(plan)`; pass `intent_block=` in `render_plan_audit_prompt`'s `safe_substitute` call; one docstring clause naming the new input; import `collapse_intent_to_one_line` from `plan_tool.scope_fence`.
  - `plan_tool/prompts/plan-audit.md` — replace the blank line between `${carried_findings_block}` and `## Plan body` with `${intent_block}` (one line).
  - `tests/test_review.py` — new `TestAuditPromptIntentBlock` class (~17 cases).

Deliberate zero-diff production files (reviewer check): `plan_tool/scope_fence.py`, `plan_tool/schema.py`, `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/completeness_phases.py`.

## Implementation

### What must hold on green

- An intent-carrying plan's audit prompt states the plan intent and every set step intent, framed as authoritative scope input for the existing stay-inside-scope rule.
- A plan with no usable intent anywhere renders the audit prompt **exactly as today**.
- The prompt never asks the judge to compare an intent against plan prose, a detail file, or code.

### The formatter

Add `_format_intent_block(plan: Plan) -> str` next to the other audit-prompt block formatters (`_format_carried_findings_block`, `_format_detail_bundle_status_block`, `_format_bundle_framing_block`). It takes the `Plan` only — no `plan_path`, `repo_root`, or `detail_grade`.

- **Return `""` when nothing survives.** No *usable* plan or step intent after the shared presence check → empty string. That is half of the unchanged-prompt property.
- **Collapse with the shared helper.** Call `collapse_intent_to_one_line` on each value. A real newline must not put `##` at line start inside the prompt.
- **Drop the fence presence non-values.** Treat `None`, `""`, whitespace-only, and `TODO` / `_(TODO)_` placeholders as empty — use the fence omit path (`_is_placeholder_section` / same predicate `_render_intent_section` uses), **not** `is_usable_intent` (that also drops `TBD`, which is outside this plan's named set). Presence, not content validation: a `TODO` must not become authoritative scope input.
- **List every step that carries an intent**, in `plan.steps` order, keyed by **id and title** (e.g. `step 3 (Put plan and step intents into the conceptual-audit prompt)`). Do not filter by `status` — the detail bundle does not either, and the prompt already says how to treat a `done` step.
- **Put framing inside the returned string.** Recommended shape: a bold lead marking the block authoritative; one sentence that these lines are the positive half of the fence and feed the prompt's existing stay-inside-scope rule; the plan line (when present) then the step bullets; then use-and-limits: use this to decide whether a gap is inside the declared purpose; a gap outside it is `[out-of-scope-deferred]`, not a completeness finding; do **not** audit the intent itself (no compare against Overview / `## Why` / detail / code, and no finding that work disagrees with stated intent).
- **Own the trailing blank line**, same as the sibling blocks, so the block separates cleanly from `## Plan body`.

### The template edit

Replace the blank line between `${carried_findings_block}` and `## Plan body` with `${intent_block}`. Empty substitution keeps the same blank gap before the body. The block sits with the other inputs at the end of the prompt, after style guidance, so `TestCheckPlanAudit::test_plan_audit_phrase_guidance_stays_in_stable_prefix` stays green.

### Rejected alternatives

- **Static prose in `## Rules` or the opening paragraph.** Changes every plan's prompt, including intent-free ones — the plan's Risks bullet forbids this.
- **Step intent inside `_format_audit_detail_bundle` headers.** Shared by both grades, byte-capped, pinned by `TestJiraGradeAuditBundle`; one owned block is cheaper.
- **Calling `render_scope_fence`.** It also renders guardrail / Out-of-scope sections already present in `${plan_body_block}` — double delivery. Deliver the two intent fields only.
- **Hand-rolling `" ".join(value.split())` instead of `collapse_intent_to_one_line`.** Forbidden by the plan Architecture Reuse bullet.

### Gotchas

- **Supply the key.** Missing `intent_block=` leaves literal `${intent_block}` in the prompt.
- **Keep the bodyless early return first.** Build the block after `_collect_plan_body` succeeds, not before.
- **Leave `collect_blocks` alone.** `TestAuditPromptBudgetAdvisory::test_plan_audit_collect_blocks_names_major_blocks` pins the exact list `["plan body", "detail bundle", "detail-bundle status"]`. Carried findings are already omitted; the intent block is small the same way.
- **No cap, no truncation.** Presence-only elsewhere; a long intent renders in full after collapse.
- **Grade-independent.** `detail_grade` selects detail artifacts; intent comes from frontmatter — both grades get the same block.
- **A `$` in an intent is safe.** One-pass substitution; do not escape.
- **Read fields off the in-memory `plan`.** Do not re-parse the file for intent.
- **Do not touch `_PLAN_AUDIT_REPROMPT_SUFFIX`.** The retry appends to the already-rendered prompt; the block rides along.

### Foundational-logic sweep

Core rule: **inject plan/step intents into the conceptual-audit prompt via a dynamic block that is empty when absent.**

| Site | Disposition |
|---|---|
| `_format_intent_block` / `render_plan_audit_prompt` / `plan-audit.md` | **This step** |
| `check_plan_audit` / `audit_plan_until_stable` | **Inherit** — same `plan` object; no signature change |
| `collapse_intent_to_one_line` | **Reuse** — import from `plan_tool.scope_fence` |
| `render_scope_fence` / detail / run fence | **Zero-diff** — already ships intent; do not call from here |
| Split / merge intent fold | **Step 1** |
| Forward-seed intent attach | **Step 2** |
| Docs naming the four rules | **Step 4** |
| Reconcile / other prompts | **Deferred** |

## Tests

### Tests for this step

All new cases in `tests/test_review.py`, class `TestAuditPromptIntentBlock`. Write fixtures that set `intent:` keys (existing `_write_plan` helpers often omit them). Table-drive the five shapes where useful. Green before done.

Formatter cases:

- `test_intent_block_is_empty_when_no_intent_is_set` — no plan/step intent → `""`.
- `test_intent_block_is_empty_for_blank_and_whitespace_values` — `""` / whitespace on plan and step → `""`.
- `test_intent_block_is_empty_for_placeholder_values` — `TODO` / `_(TODO)_` on plan or step → `""` (same as fence; prompt byte-identical to intent-free).
- `test_intent_block_renders_tbd_as_written` — `TBD` reaches the prompt (`TBD` outside this plan's fence presence set).
- `test_intent_block_renders_the_plan_intent` — plan value appears.
- `test_intent_block_renders_each_step_intent_with_id_and_title` — id + title, `plan.steps` order.
- `test_intent_block_skips_steps_with_no_intent` — only carriers listed.
- `test_intent_block_renders_with_only_a_plan_intent` — block still renders.
- `test_intent_block_renders_with_only_step_intents` — block still renders.
- `test_intent_block_collapses_a_multi_line_intent_to_one_line` — no newline; no forged H2.

Prompt cases:

- `test_prompt_carries_the_plan_and_step_intent` — both values in the rendered prompt.
- `test_prompt_places_the_intent_block_before_the_plan_body` — block index precedes `## Plan body`.
- `test_prompt_has_no_unresolved_template_placeholder` — no `${` left.
- `test_no_intent_prompt_inserts_nothing_before_the_plan_body` — intent-free: only whitespace between prior content and `## Plan body`.
- `test_bodyless_plan_returns_none_even_with_an_intent_set` — early return preserved.
- `test_intent_block_renders_the_same_at_jira_grade` — identical block under `detail_grade="jira"`.
- `test_dollar_sign_in_an_intent_reaches_the_prompt_literally` — `${x}` unchanged.
- `test_prompt_never_asks_for_an_intent_agreement_check` — framing states do-not-compare and routes outside-purpose gaps to `[out-of-scope-deferred]`.

Existing cases that must stay green **unchanged** (if one fails, placement or empty-return is wrong):

- `TestCheckPlanAudit::test_render_prompt_returns_none_for_bodyless_plan`
- `TestCheckPlanAudit::test_plan_audit_phrase_guidance_stays_in_stable_prefix`
- `TestAuditPromptBudgetAdvisory::test_plan_audit_collect_blocks_names_major_blocks`
- every case in `TestJiraGradeAuditBundle` / `TestDetailBundleStatus`

**Green-before-done:** every case above; `uv run pytest tests/test_review.py -q`; full suite before closing.

## Acceptance criteria

- `plan_tool/prompts/plan-audit.md` contains exactly one `${intent_block}` and no new static intent instructions in `## Rules` or the opening paragraph.
- `_format_intent_block` is defined in `plan_tool/review.py` and is the only production site that builds the block; `safe_substitute` passes `intent_block=` once.
- `_format_intent_block(plan)` returns `""` when plan and every step have no *usable* intent (including placeholders).
- For a plan with plan-level and at least one usable step intent, `render_plan_audit_prompt` includes both values before `## Plan body`.
- A plan whose only intents are placeholders renders the audit prompt byte-identical to an intent-free plan.
- No rendered audit prompt contains the substring `${`.
- `render_plan_audit_prompt` still returns `None` for a bodyless plan even when intent is set.
- `collect_blocks` still names exactly `["plan body", "detail bundle", "detail-bundle status"]`.
- The block framing states the do-not-compare rule; the template gains no agreement-check instruction.
- `uv run pytest tests/test_review.py -q` passes; full suite passes.

## References

- [string.Template — Python 3.13 Library Reference](https://docs.python.org/3.13/library/string.html#template-strings) — `safe_substitute` leave-unknown-placeholders behavior and single-pass substitution — why the new key must be supplied and why `$` in an intent needs no escaping.
- [CommonMark Spec — ATX headings](https://spec.commonmark.org/0.31.2/#atx-headings) — why a raw newline inside an intent can forge a `##` heading in the prompt.
- [Claude Prompting Best Practices (Anthropic)](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — keep variable authoritative context in an isolated block rather than mixing it into static instructions.
- [pytest — parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-drive the five intent shapes through the formatter.

## Applicable guardrails

- **The plan's "## Plan intent"** — after every conceptual-audit call, the audit must receive plan/step intents when present; this step is that delivery.
- **The plan's "## Step intent"** — the audit sees the intents the stay-inside-scope rule already assumes, not only the stripped body; do not widen into content validation or agreement checks.
- **The plan's "## Out of scope"** — do not reopen shipped intent authoring/fence work; do not add content validation; leave #212 and #161/#162 alone. Deliver the two fields into this prompt only.
- **The plan Architecture conceptual-audit row** — dynamic `${intent_block}` only; empty → unchanged prompt. Static template prose for intent is out.

## Deferred

- **Documenting the four intent rules** — step 4 owns `PLAN_FORMAT.md` and the parent Deferred close-out.
- **Split / merge intent fold** — step 1 owns `plan_tool/detail.py`.
- **Forward-seed intent attach** — step 2 owns `plan_tool/scope_out.py` / `plan_tool/reground.py`.
- **BACKLOG #161 / #162 full scope-contract block** — seed In scope / Non-goals as an authoritative audit block; this step opens the channel with the two intent fields only.
- **BACKLOG #212** — `apply_finding` stale intent; named in the plan's Out of scope / Deferred.
- **Threading intent into `render_review_prompt` or `run --mode check`** — further prompt consumers; plan Deferred says any further consumers are out.
- **Step intent inside `_format_audit_detail_bundle` headers** — rejected placement; revisit only with evidence the single block loses the judge.
- **Adding the intent block to `collect_blocks`** — small; carried-findings sets the omit precedent.
- **Other prompt consumers** (reconcile, jira, apply) — out of this plan; new backlog entry if needed.
- **#212 / #161 / #162** — named in the plan Deferred; leave alone.
