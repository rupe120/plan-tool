> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Pass the plan and step intent into the conceptual audit prompt

## Summary

This step delivers step 1's `Plan.intent` and `Step.intent` to the conceptual audit, whose only plan input today is the **frontmatter-stripped** body (`plan_tool/review.py:_collect_plan_body`) — so a frontmatter field is invisible to it. It adds one formatter, `_format_intent_block`, to `plan_tool/review.py`, one new `${intent_block}` slot to `plan_tool/prompts/plan-audit.md`, and one more keyword in `render_plan_audit_prompt`'s `safe_substitute` call. The main design decision is that **every word this step adds to the prompt lives inside the dynamic block, never in the template's static prose** — so a plan carrying no intent renders exactly the prompt bytes it renders today, and the template diff is one line (a blank line becomes the slot). On green, an intent-carrying plan's audit sees the plan's stated purpose and each step's, framed as input to the `Stay inside the declared scope contract` rule the prompt already carries, and an intent-free plan's audit is untouched.

## Table of Contents

- [Summary](#summary) — what ships, the all-text-inside-the-block decision, and the result on green.
- [Why](#why) — the one consumer a frontmatter field cannot reach by accident.
- [Input](#input) — the five contracts this step reads and does not own, and what the tests cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — three edited files, no new files.
- [Implementation](#implementation) — the formatter, the one-line template edit, the rejected alternatives, and eight gotchas.
- [Tests](#tests) — approx. 17 new cases, four existing cases that must stay green unchanged, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — greps and diffs a reviewer can run.
- [References](#references) — the `string.Template` and prompt-placement behavior this step leans on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the one line where breaking them is tempting.
- [Deferred](#deferred) — what step 11 and BACKLOG #162 own, and the plan-body defect routed to reconcile.

## Why

The conceptual audit is the consumer where scope creep actually happens — a completeness pass proposing work the plan's author deliberately fenced out — and it is the one consumer a new frontmatter field cannot reach as a side effect. `plan_tool/review.py:render_plan_audit_prompt` builds its plan input from `_collect_plan_body`, which strips the frontmatter and hands over the markdown body only. So steps 4 and 5 can thread intent into `detail` and `run` through the shared fence renderer and the audit still sees nothing. The gap is sharper than "one more consumer": the prompt's `## Rules` section **already** tells the judge to "Stay inside the declared scope contract… within the plan/seed Outcome, In scope, Out of scope / Non-goals" — and the plan/seed Outcome is the one item on that list the prompt never receives. Step 6 makes `Plan.intent` exactly that Outcome, lifted from the seed. This step supplies the missing input to a rule that is already written.

## Input

Five contracts this step reads and does not own. Read each off HEAD before you start; where a landed name differs from a name below, the landed name wins.

- **Step 1's two schema fields.** `Plan.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD) and `Step.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), each `Optional[str] = None`, storing whatever YAML handed over with no stripping, no cap, and no validator. All five shapes are legal parses and reach this formatter: `None`, `""`, `"   "`, a normal one-liner, and a value with real newlines. This step decides what each one renders into the prompt.
- **`render_plan_audit_prompt`'s signature and its early return.** It already takes the parsed `plan` object, so both fields are in hand with no re-parse and no new parameter. Its first act is `body = _collect_plan_body(plan_path)`; `body is None` returns `None` and no Claude call is made. That ordering is a contract — `tests/test_review.py:TestCheckPlanAudit::test_render_prompt_returns_none_for_bodyless_plan` pins it, and a plan that carries an intent but has no body must still return `None`.
- **The template substitution contract.** `plan_tool/prompts/plan-audit.md` is loaded with `string.Template` and rendered with `safe_substitute`. Two consequences bind this step: an unsupplied `${name}` is left in the prompt **literally** rather than raising, so the new key must be passed at the call site; and substitution is a **single pass**, so a `$` or a `${…}` inside an intent value is never re-expanded and needs no escaping.
- **How a dynamic block carries its own framing.** `_format_detail_bundle_status_block` and `_format_carried_findings_block` both put their *instructions* inside the returned string and return `""` when they have nothing to say, so the fully-grounded prompt is unchanged. That is the shape this step copies — it is what makes "unchanged when no intent is set" true for a prompt whose static prose is shared by every plan.
- **The one prompt-render call site.** `render_plan_audit_prompt` is called from exactly two places in the package: `check_plan_audit` and `audit_plan_until_stable` (the multi-pass sampler), both inside `plan_tool/review.py`. The completeness surface reaches the audit through `audit_plan_until_stable` (`plan_tool/cli/completeness_phases.py`, `plan_tool/cli/completeness_cmd.py`), which passes the same parsed `plan`. So one edit reaches every audit pass on every surface, and no CLI file changes.

**What this step cannot verify.** The tests drive canned invoker responses through the real renderer, so they prove the intent text is *delivered* to the prompt and that the prompt is well-formed. They cannot show that a judge actually narrows its findings because of it — that needs a real backend and a corpus of plans, and it is not in this step.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/review.py` — add `_format_intent_block(plan)`; pass `intent_block=` in `render_plan_audit_prompt`'s `safe_substitute` call; one clause in `render_plan_audit_prompt`'s docstring (and, if it reads stale, `check_plan_audit`'s) naming the new input.
- `plan_tool/prompts/plan-audit.md` — one line: the blank line between `${carried_findings_block}` and `## Plan body` becomes `${intent_block}`.
- `tests/test_review.py` — approx. 17 new cases in a new `TestAuditPromptIntentBlock` class.

## Implementation

**What must be true on green**

- An intent-carrying plan's audit prompt states the plan's intent and every step intent that is set, framed as authoritative scope input.
- A plan carrying no intent anywhere renders the audit prompt **exactly as today**, byte for byte.
- The prompt never asks the judge to compare an intent against plan prose, a detail file, or code.

**The formatter**

Add `_format_intent_block(plan: Plan) -> str` next to the other audit-prompt block formatters in `plan_tool/review.py` (`_format_carried_findings_block`, `_format_detail_bundle_status_block`, `_format_bundle_framing_block`). It takes the `Plan` and nothing else — it reads no file and needs no `plan_path`, `repo_root`, or `detail_grade`.

- **Return `""` when nothing survives.** No plan intent and no step intent → empty string. This is half of the unchanged-prompt property.
- **Squeeze each value to one line.** Collapse every whitespace run to a single space and strip the ends — the `" ".join(value.split())` idiom `plan_tool/review.py` already uses in `_split_audit_fix`'s fix capture and in `check_plan_audit`'s response-tail log line. A real newline in a value would otherwise let a `##` at line start forge a heading in a markdown prompt. Steps 6, 7, and 9 settle the same one-line rule for their own producers; if step 4 or step 6 landed a public one-line helper you can import without a cycle, reuse it rather than minting a third copy — otherwise repeat the two-line collapse here and see the Deferred note.
- **Drop a value that is empty after the squeeze**; treat `None`, `""`, and `"   "` identically.
- **Render a placeholder value as written.** A literal `TODO` goes into the prompt unchanged. Step 2 owns the advisory judgment of whether an intent is any good; this block's job is to deliver the field, and an audit that can see the plan states `TODO` is better off than one that cannot see the field at all. *Rejected:* reusing step 2's placeholder predicate to filter here — it splits ownership of one judgment across two steps and hides the state from the judge.
- **List every step that carries an intent, in `plan.steps` order, keyed by id and title** — `step 3 (Move the plan scope-fence rendering into a shared leaf module)`. The plan body's `## Steps` section says only "See the `steps:` block in the frontmatter", so the bundle headers are the audit's only other source of step titles; keying by both id and title makes each line resolvable on its own. Do **not** filter by `status` — the bundle does not either, and the prompt already has its own rule for how to treat a `done` step.
- **Put the framing inside the returned string**, following `_format_detail_bundle_status_block`. Recommended shape: a bold lead line marking the block authoritative, one sentence saying these lines are the positive half of the fence and pointing at the prompt's existing `Stay inside the declared scope contract` rule, the bullet list, then the use-and-limits sentence: use it to decide whether a gap you are about to raise is inside the plan's declared purpose; a gap outside it is `[out-of-scope-deferred]`, not a completeness finding; do **not** audit the intent itself — do not compare it against the plan's prose, a detail file's `## Why`, or a step's implementation, and do not raise a finding that a step's work disagrees with its stated intent. That last clause is the plan's fence written into the artifact that would otherwise be most tempted to break it.
- **Own the trailing blank line**, as the sibling blocks do (they end their line list with `""`), so the block separates cleanly from `## Plan body`.

**The template edit**

Replace the blank line that sits between `${carried_findings_block}` and the `## Plan body` heading with `${intent_block}`. One line changes. This placement does three things at once: an empty substitution puts a blank line exactly where a blank line already was, so the no-intent prompt is unchanged; the block lands with the other input blocks at the end of the prompt, where the opening paragraph already tells the judge to look for its inputs; and it stays **after** the style guidance, so `TestCheckPlanAudit::test_plan_audit_phrase_guidance_stays_in_stable_prefix` (which asserts guidance precedes `## Plan body`) is unaffected.

*Rejected: adding a sentence to the template's static `## Rules` or opening paragraph.* Static text changes the prompt for every plan, including intent-free ones, which forfeits the unchanged property for no gain — the block's own framing reaches exactly the runs that have something to frame.

*Rejected: rendering step intent into `_format_audit_detail_bundle`'s `### Step NN — <title>` headers.* Adjacency to each step's detail body is the argument for it, and it loses: that formatter is shared by both grades, its output is excerpted and byte-capped per step, its header shape is pinned by `TestJiraGradeAuditBundle`, and a bare step already renders a note in place of a body. One block with one owner is cheaper to reason about and to test.

*Rejected: calling step 4's `plan_tool/scope_fence.py:render_scope_fence` here.* It renders the negative half too — the guardrail sections and `## Out of scope` — and the audit prompt already embeds the whole plan body, so those sections would arrive twice. The plan is explicit that step 10 delivers the intent fields to this prompt and nothing more.

**Gotchas**

- **Supply the key.** `safe_substitute` leaves an unsupplied `${intent_block}` in the prompt as literal text with nothing raising. Add `intent_block=_format_intent_block(plan)` to the existing `safe_substitute` call and cover it with a no-leftover-`${` test.
- **Keep the bodyless early return first.** Build the block after `_collect_plan_body` returns, not before — a plan with an intent and no body must still return `None`.
- **Leave `collect_blocks` alone.** The out-param names the *major* byte contributors for the prompt-budget advisory; `_format_carried_findings_block` is already omitted from it on the same grounds, and `tests/test_review.py:TestAuditPromptBudgetAdvisory::test_plan_audit_collect_blocks_names_major_blocks` asserts the list equals `["plan body", "detail bundle", "detail-bundle status"]` exactly. An intent block is a handful of one-line entries. If you do decide to collect it, that exact-equality assertion must be rewritten in the same edit.
- **No cap, no truncation.** An over-long intent renders whole. Step 2 flags length advisorily; silently clipping here would make the block disagree with the finding.
- **The block is grade-independent.** `detail_grade` selects detail artifacts; intent comes from frontmatter, so both grades render the same block. Don't thread the grade into the formatter.
- **A `$` in an intent value is safe.** Single-pass substitution means a value containing `$` or `${x}` reaches the model literally. Don't add escaping — and don't build the block by pre-substituting into the template.
- **Read the fields off the in-memory `plan`.** `_collect_plan_body` re-reads the file for the body; the intent must not trigger a second parse.
- **Don't touch `_PLAN_AUDIT_REPROMPT_SUFFIX`.** The one-retry path appends to the already-rendered prompt, so the block rides along with no change.

## Tests

All new cases land in `tests/test_review.py`, in a new `TestAuditPromptIntentBlock` class that writes its own plan fixtures (the existing `_write_plan` helper belongs to `TestCheckPlanAudit` and emits no `intent:` keys). This step's `change_type` is `feature` under a plan with `enforce_step_tests: true`, so the test-authoring gate applies and `tests/test_review.py` is in the declared file list.

### Tests for this step

Formatter cases (approx. 9):

- `test_intent_block_is_empty_when_no_intent_is_set` — a plan with no plan intent and no step intent returns `""`. This plus the blank-line slot is what makes the no-intent prompt unchanged.
- `test_intent_block_is_empty_for_blank_and_whitespace_values` — `""` and `"   "` on both the plan and a step return `""`.
- `test_intent_block_renders_the_plan_intent` — the plan-level line carries the value verbatim.
- `test_intent_block_renders_each_step_intent_with_id_and_title` — one line per carrier, keyed by both id and title, in `plan.steps` order.
- `test_intent_block_skips_steps_with_no_intent` — a plan where two of four steps carry one lists exactly those two.
- `test_intent_block_renders_with_only_a_plan_intent` — no step carries one; the block still renders.
- `test_intent_block_renders_with_only_step_intents` — no plan intent; the block still renders.
- `test_intent_block_collapses_a_multi_line_intent_to_one_line` — a value with real newlines renders on one line, so a leading `##` cannot forge a heading.
- `test_intent_block_renders_a_placeholder_value_as_written` — `TODO` reaches the prompt rather than being dropped.

Prompt cases (approx. 8):

- `test_prompt_carries_the_plan_and_step_intent` — both values appear in the rendered prompt.
- `test_prompt_places_the_intent_block_before_the_plan_body` — the block's index precedes `## Plan body`.
- `test_prompt_has_no_unresolved_template_placeholder` — no `${` survives in the rendered prompt.
- `test_no_intent_prompt_inserts_nothing_before_the_plan_body` — for an intent-free plan, the text preceding `## Plan body` is whitespace only after the last style bullet.
- `test_bodyless_plan_returns_none_even_with_an_intent_set` — the early return is preserved.
- `test_intent_block_renders_the_same_at_jira_grade` — the block is unaffected by `detail_grade`.
- `test_dollar_sign_in_an_intent_reaches_the_prompt_literally` — a value containing `${x}` renders unchanged (single-pass substitution).
- `test_prompt_never_asks_for_an_intent_agreement_check` — the block's framing routes an out-of-scope gap to `[out-of-scope-deferred]` and states the do-not-compare rule; assert on that deliberate phrase set, not on a broad word blocklist.

Existing cases that must stay green **unchanged** (do not edit them; if one reddens, the placement or the empty-return is wrong):

- `TestCheckPlanAudit::test_render_prompt_returns_none_for_bodyless_plan`
- `TestCheckPlanAudit::test_plan_audit_phrase_guidance_stays_in_stable_prefix`
- `TestAuditPromptBudgetAdvisory::test_plan_audit_collect_blocks_names_major_blocks`
- every case in `TestJiraGradeAuditBundle` and `TestDetailBundleStatus`

**Green-before-done gate:** every case above, plus `uv run pytest tests/test_review.py -q` and the full suite, must be green before this step is finished.

## Acceptance criteria

- `rg -n 'intent_block' plan_tool/prompts/plan-audit.md` returns exactly one line, and `git diff --stat plan_tool/prompts/plan-audit.md` shows one insertion and one deletion.
- `rg -n 'intent_block' plan_tool/review.py` shows the formatter definition and one `safe_substitute` keyword — no other production site.
- `_format_intent_block(plan)` returns `""` for a plan whose `Plan.intent` is `None` and whose every `Step.intent` is `None`.
- For a plan carrying `intent:` at plan level and on at least one step, `render_plan_audit_prompt` returns a prompt containing both values, positioned before `## Plan body`.
- No rendered audit prompt contains the substring `${`.
- `render_plan_audit_prompt` still returns `None` for a plan with frontmatter (including an intent) and an empty body.
- The blocks list passed to `collect_blocks` still equals `["plan body", "detail bundle", "detail-bundle status"]`.
- The prompt gains no instruction to compare an intent against plan prose, a detail file, or a diff; the block's framing states the opposite explicitly.
- `uv run pytest tests/test_review.py -q` is green, and so is the full suite, with no edits to existing plan fixtures.

## References

- [Template strings — `string` (Python 3 documentation)](https://docs.python.org/3/library/string.html#template-strings) — `safe_substitute`'s leave-unknown-placeholders-in-place behavior and its single substitution pass, which decide whether the new key must be supplied and whether a `$` in an intent value needs escaping.
- [Long context prompting tips — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — where authoritative context belongs relative to instructions in a long prompt, which informs putting the block with the other inputs before the plan body.
- [Be clear, direct, and detailed — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — phrasing the block's framing so it constrains which findings the judge raises instead of reading as decoration.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — scalar styles and line folding, which set what a parsed intent value can contain and why the one-line squeeze is needed before it reaches a markdown prompt.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven cases for the five value shapes (`None`, `""`, `"   "`, one-liner, multi-line).

## Applicable guardrails

- **"No step ships a check comparing an intent against prose or against a diff."** This binds this step hardest, because the audit prompt is the one artifact in the plan that instructs a judge. The tempting line is a single sentence asking the judge to confirm each step's design serves its stated intent — it would read as rigor and is exactly the withdrawn prose-conformance shape the plan's `## Out of scope` names. The block's framing carries the opposite instruction in so many words, and `test_prompt_never_asks_for_an_intent_agreement_check` guards it.
- **"Nothing becomes required at parse time, and no plan on disk is migrated."** The formatter must handle an absent intent as the normal case and render nothing for it.
- **"Step 10 delivers the intent fields to that prompt and nothing more"** (the `## Out of scope` entry on BACKLOG #162). Render `Plan.intent` and `Step.intent` only — not the seed's In scope / Non-goals, not the plan-body guardrail sections (already inside `${plan_body_block}`), not a re-rendered `## Out of scope`.
- **Audit guardrails.** A finding out of this audit proposing that intent become required, that an agreement check be added, or that propagation widen past the four structural verbs goes to `BACKLOG.md`, not into this plan.

## Deferred

- **BACKLOG #162's full delivery** — rendering the seed/backlog scope contract (Outcome, In scope, Non-goals) into this prompt as an authoritative block. This step opens the channel with the two intent fields; #162 fills it.
- **Any intent-vs-work agreement instruction, at any altitude** — banned by the plan's fence; if it is ever revisited it is its own entry and must first answer what makes it different from the withdrawn per-`change_type` test-ordering contract.
- **Documenting this hop in `docs/AUDIT_FLOW.md`, `PLAN_FORMAT.md`, and `CLAUDE.md`** — step 11 owns every doc edit in this plan.
- **Threading intent into the reconcile prompt (`plan_tool/review.py:render_review_prompt`) or `run --mode check`** — the plan names three consumers (`detail`, `run`, the conceptual audit); a fourth is a `BACKLOG.md` entry, not an expansion here.
- **Step intent inside `_format_audit_detail_bundle`'s step headers** — the rejected placement; revisit only with evidence that block-level placement loses the judge.
- **Adding the intent block to `collect_blocks`' byte accounting** — the block is small and the carried-findings block sets the precedent for omitting one.
- **Consolidating the one-line squeeze rule** — steps 6, 7, 9, and this step each need "collapse whitespace to one line, drop if empty". If three or more copies land, that is a cross-module extraction a feature step cannot mint; route it to reconcile or `BACKLOG.md` rather than widening this step's footprint.
- **The plan body's stale per-step test-strategy list** — it labels step 10 `non-code` and omits step 11, while the frontmatter has step 10 as `feature` and step 11 as `non-code`. This step follows the frontmatter; correcting the body prose is a plan edit for reconcile.
- **The `Allowed behavior changes` clause's "two prompts" count** — the plan's Overview, Architecture, Acceptance criteria, and this step's own `files:` all name the conceptual audit prompt as the third consumer. This step follows those; the stale numeral is a plan-body fix for reconcile, not something to reinterpret here.
