> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Render the plan and step intent in the shared fence and pass it to the detail prompt

## Summary

This step adds `render_scope_fence` to `plan_tool/scope_fence.py` — one function that renders the *positive* half of the fence (step 1's `Plan.intent` and `Step.intent`) as a prefix on top of the *negative* half the leaf already renders (`extract_plan_guardrails`) — and points `plan_tool/detail.py`'s two authoring call sites at it. The main design decision is that **the intent half is a prefix, so with no intent set `render_scope_fence(plan_path)` returns exactly what `extract_plan_guardrails(plan_path)` returns today**: the plan's "unchanged prompts when no intent is set" property holds by the way the function is built, not by a test's good luck. The second decision is that the intent half deliberately does *not* reach the detail-quality review prompt — handing a reviewer both the intent and the authored prose sets up exactly the intent-vs-prose agreement check the plan's fence bans. On green, a plan or step carrying an `intent:` sees it in the authoring prompt's authoritative fence block, a plan carrying none renders the same prompt bytes it renders today, and step 5 has one function to call from `plan_tool/renderer.py`.

## Table of Contents

- [Summary](#summary) — what ships, the prefix decision, and the result on green.
- [Why](#why) — why a field nothing renders is a field that changes nothing.
- [Input](#input) — the four contracts this step reads from steps 1 and 3, and what the tests cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — six edited files, no new files.
- [Implementation](#implementation) — the new function, the two call sites, the template-variable rename, and the five gotchas.
- [Tests](#tests) — ~16 new leaf cases, ~8 in the detail suite, 2 keyword updates, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — greps and equalities a reviewer can run.
- [References](#references) — the prompt-engineering and `string.Template` behavior this step relies on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the three places breaking them is tempting.
- [Deferred](#deferred) — what step 5 and the carved follow-up own, and the consolidations routed out.

## Why

Steps 1 and 2 make intent parseable and make its absence visible, and neither makes it *do* anything. The plan's stated guard is that intent **travels** — it reaches the model doing the work as authoritative input, the same way `## Out of scope` already does. `detail` is the first of the two surfaces that has to receive it, and it is the one where the fence machinery already exists: `plan_tool/detail.py` builds a block from the plan body and substitutes it into `${plan_guardrails_block}` under a heading already labeled "(authoritative)". Right now that block carries only "what not to build". Until the positive half rides in the same block, an author's stated purpose for a step dies in the plan file, and every `detail` pass keeps re-deriving the step's motivation from its title and the surrounding prose — which is the defect the plan opens with.

## Input

Four contracts this step reads and does not own. Read each off HEAD before you start; where a landed name differs from a name below, the landed name wins.

- **Step 1's two schema fields.** `Plan.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD) and `Step.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), each `Optional[str] = None`, storing whatever YAML handed over with no stripping. So a caller sees `None`, `""`, `"   "`, `"TODO"`, a 500-character line, or a string with real newlines — all five are legal parses, and this step decides what each one renders.
- **Step 3's leaf.** `plan_tool/scope_fence.py` owns `extract_plan_guardrails(plan_path) -> str`, the plan-body H2 splitter, the guardrail heading names, and the `_(TODO)_` placeholder check (`_is_placeholder_section` / `_SECTION_PLACEHOLDER_RE`). The leaf imports **no** first-party code — not at module level and not lazily inside a function body. That rule is what fixes this step's function signature: the fence renderer takes intent as plain strings, never a `Plan` or a `Step`, because taking those would mean importing `plan_tool.schema`.
- **The render shape the leaf already uses.** Each section renders as `## <Heading>\n\n<body>`; sections join with `"\n\n"`; empty and placeholder-only bodies are skipped; order is the three author-supplied guardrail headings, then `Out of scope`. The intent half must match that shape and slot in ahead of it, so the whole block stays one consistent list of `## `-headed sections.
- **The prompt-side default.** `render_detail_prompt` substitutes `_no plan-level guardrails or scope fence_` when the block is empty; the leaf returns `""`. That split stays exactly as it is — the default text is not reworded here (see [Applicable guardrails](#applicable-guardrails)).

**What this step cannot verify.** Nothing about whether the rendered intent actually steers the authoring model. The tests drive strings through a renderer and assert what lands in the prompt text; they prove the intent is *delivered*, not that it *works*. Measuring whether a delivered intent changes what `detail` writes needs real backend runs and somewhere to record them — out of this plan.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/scope_fence.py` — add `render_scope_fence(plan_path, *, plan_intent="", step_intent="")` and the two intent heading constants. `extract_plan_guardrails` keeps its current body and its current callers.
- `plan_tool/detail.py` — point the two authoring call sites (in `_generate_detail_concurrent`'s pre-dispatch loop and in `generate_detail`'s serial loop) at `render_scope_fence`, passing each step's own intent; rename `render_detail_prompt`'s `plan_guardrails_block` keyword to `scope_fence_block` and its budget label from `plan-guardrails` to `scope-fence`. `render_detail_quality_prompt` and the call site in `collect_detail_quality_findings` are deliberate zero-line diffs.
- `plan_tool/prompts/detail.md` — one changed line: `${plan_guardrails_block}` → `${scope_fence_block}`. The surrounding heading and every line of instruction prose stay unchanged.
- `plan_tool/prompts/detail-jira.md` — **add** a `${scope_fence_block}` slot under an authoritative heading matching `detail.md`'s. Unlike `detail.md` there is no existing slot to rename, so this template gains one; `render_jira_detail_prompt` in `plan_tool/detail.py` gains the matching substitution. The jira grade's own required section is `## Intent`, so it is the one authoring lane that must not be fence-free.
- `tests/test_scope_fence.py` — ~16 new cases for the intent half plus the no-intent equality.
- `tests/test_detail.py` — ~8 new cases; update the two `render_detail_prompt` call sites that pass the old keyword.

## Implementation

**What should be true when the step is done:** one function renders both halves of the fence from a plan path plus two strings; `detail`'s authoring prompt receives it; a plan with no intent produces the same prompt bytes it produces today; and the detail-quality review prompt still receives the guardrails half only.

### The new function

Add to `plan_tool/scope_fence.py`:

```
render_scope_fence(plan_path, *, plan_intent: str = "", step_intent: str = "") -> str
```

- **Both intents default to `""`**, so `render_scope_fence(plan_path)` is the same string as `extract_plan_guardrails(plan_path)`. That equality is the step's central property — write it as a test, not as a comment.
- **Build the intent sections, then append the guardrails string, then join with `"\n\n"`.** Reuse the leaf's existing joiner and section shape rather than inventing a second one.
- **Skip an intent that is empty, whitespace-only, or a placeholder**, reusing the leaf's `_is_placeholder_section`. Rendering `## Plan intent\n\nTODO` inside a block the prompt labels authoritative is worse than rendering nothing — it reads as a directive.
- **Render a surviving intent at full length, collapsed to one line.** No truncation and no trailing-period tidying — there is no length cap anywhere in this plan (the `## Scope guardrails` forbid one), and altering the value here would make the prompt disagree with the file. But whitespace **is** collapsed: every run becomes a single space and the ends are stripped, per the single rule in the plan's `## Architecture`. That is not tidying, it is the heading-injection guard — a value with a real newline could otherwise put `##` at line start and forge a heading in a markdown prompt. Length is preserved; line structure is not.
- **Plan intent first, then step intent, then every guardrail section.** Widest fence first, same as the guardrail half's own fixed order.

Headings should name whose intent it is and read as an instruction, since the model sees them with no other framing. One way:

- `## Plan intent (what the whole plan is for — every part of this step must serve it)`
- `## Step intent (what this step is for — do not widen past it)`

The exact wording is yours, but **pin it with a test**: step 5 renders the same block into the `run` prompt through the same function, so the strings have to be stable enough that a wording change is a visible diff rather than a silent drift between two surfaces.

### Why strings, not a `Plan` object

The obvious alternative is `render_scope_fence(plan_path, plan, step)`, which reads better at the call site and needs no `or ""` from the caller. **Reject it**: `plan_tool/scope_fence.py` cannot import `plan_tool.schema`, and step 3's whole reason for existing is that the leaf stays importable from `plan_tool/renderer.py` without closing a cycle. Taking two strings keeps the leaf stdlib-only and keeps its tests free of plan fixtures. The caller does the unwrapping — `plan.intent or ""`, `step.intent or ""` — which is also where `None` becomes `""`, so the leaf never has to think about it.

### The two call sites in `detail.py`

Both already sit inside a per-step loop and both already rebuild the block once per step:

- `_generate_detail_concurrent` — the serial pre-dispatch pass, `for step in target_steps:`, beside `plan_references_block = extract_plan_references(plan_path)`.
- `generate_detail` — the serial authoring loop, `for step in serial_steps:`, the same pairing.

Swap `extract_plan_guardrails(plan_path)` for `render_scope_fence(plan_path, plan_intent=plan.intent or "", step_intent=step.intent or "")` at each. `plan` is in scope at both sites.

**Do not hoist either call out of its loop.** The block is now step-dependent, and hoisting would put step 1's intent in every step's prompt. It looks like a free optimization because the call re-reads the plan file each iteration and the result used to be step-invariant — which is exactly why the trap is worth naming.

### The template-variable rename

`${plan_guardrails_block}` becomes `${scope_fence_block}` in `plan_tool/prompts/detail.md`, and `render_detail_prompt`'s keyword changes to match. The point: the block now carries both halves, and step 5 has to name the same thing in `plan_tool/renderer.py` — settling the name here keeps the two callers from inventing two.

- **A `${...}` rename changes zero rendered bytes.** The value lands in the same place; only the slot's name differs. That is what makes this edit compatible with the plan's "unchanged prompts when no intent is set" requirement, while a heading or prose edit would not be.
- **`render_detail_quality_prompt` keeps `plan_guardrails_block`, and `plan_tool/prompts/detail-quality.md` keeps `${plan_guardrails_block}`.** The two names now record a real difference in content — the review prompt genuinely gets guardrails only.
- **`plan_tool/prompts/detail.md`'s static text is otherwise untouched**: the `### Plan-level guardrails and scope fence (authoritative)` heading, the `## Applicable guardrails` instruction, and the `## Constraints` bullets all stay as they are.

### The quality-audit call site stays on the guardrails half

`collect_detail_quality_findings` builds `render_detail_quality_prompt(..., plan_guardrails_block=extract_plan_guardrails(plan_path))`. Leave it. That prompt already carries the authored detail body and asks the reviewer to check it, so adding the intent hands it both sides of a comparison the plan's fence refuses — "not intent vs a detail's `## Why`". Write this as a test, not just a decision: the review prompt must contain no intent heading even when the plan carries one.

### Five gotchas

- **`safe_substitute` fails silently.** If the template rename lands and the code keyword does not (or the reverse), `string.Template.safe_substitute` leaves the literal `${plan_guardrails_block}` in the prompt and raises nothing. Land both in one edit and add the "no leftover `${`" assertion.
- **`render_detail_prompt` is publicly re-exported** from `plan_tool/__init__.py`, so the keyword is public API. In-repo callers are the two `detail.py` sites plus the test suite — a closed set, but the rename is a signature change, not an internal tidy.
- **The leaf's placeholder vocabulary is narrower than review's.** `_SECTION_PLACEHOLDER_RE` covers `_(TODO)_`, `TODO`, and `(TODO)`; step 2's check reuses `plan_tool/review.py:_BODY_PLACEHOLDER_RE`, which also covers `TBD`. So `intent: TBD` renders into the fence while step 2 flags it. **Leave the divergence.** Widening the leaf's regex would also stop a `## Out of scope` body of `TBD` from rendering — a behavior change outside the plan's allowed list, on a section this step is not here to touch.
- **`_is_placeholder_section` matches per line, not per value.** It is true only when *every* non-blank line is a placeholder, so a multi-line intent whose first line is `TODO` and whose second is real prose renders in full. That is the right behavior (the same rule the sections get) and it is not obvious from the helper's name.
- **The empty-case default text is not reworded.** `_no plan-level guardrails or scope fence_` now also stands for "no intent", and changing it to say so would alter the prompt for every plan on disk that carries no fence at all.

### One judgment call, called out

The budget-breakdown label in `render_detail_prompt`'s `collect_blocks` list reads `plan-guardrails` and now measures a block that includes the intent. Rename it to `scope-fence`. It is an operator-facing display string in the prompt-budget advisory — no prompt bytes, no exit code, no test asserts it today. Leaving it would mean a label that names one half while measuring two, which is a defect sitting inside code rather than a preserved behavior.

## Tests

### Tests for this step

**`tests/test_scope_fence.py` (edited — step 3 creates it).** ~16 new cases:

- `test_no_intent_renders_exactly_the_guardrail_block` — for a plan carrying all four fence sections, `render_scope_fence(p) == extract_plan_guardrails(p)`. The step's central property.
- `test_no_intent_and_no_guardrails_returns_empty` — both halves absent → `""`.
- `test_plan_intent_renders_as_its_own_section` — heading plus the exact value.
- `test_step_intent_renders_as_its_own_section` — same at step level.
- `test_plan_intent_precedes_step_intent` — fixed order.
- `test_intent_sections_precede_every_guardrail_section` — both intents ahead of `## Scope guardrails` and `## Out of scope`.
- `test_step_intent_alone_renders_no_plan_intent_section` — one half set, one heading rendered.
- `test_plan_intent_alone_renders_no_step_intent_section` — the mirror case.
- `test_sections_join_with_one_blank_line` — the intent half uses the guardrail half's joiner, so the whole block is one uniform list.
- `test_empty_intent_renders_nothing` — `""`.
- `test_whitespace_only_intent_renders_nothing` — `"   "`.
- `test_placeholder_intent_renders_nothing` — parametrized over `_(TODO)_`, `TODO`, `(TODO)`.
- `test_tbd_intent_still_renders` — pins the accepted divergence from step 2's wider vocabulary, so nobody "fixes" the leaf's regex.
- `test_prose_mentioning_todo_still_renders` — "Fix the TODO handling in the parser" is a real intent.
- `test_long_intent_renders_at_full_length` — a ~500-character intent arrives whole; nothing truncates it.
- `test_multi_line_intent_collapses_to_one_line` — a value containing real newlines renders as a single line, and a leading `##` on an interior line cannot forge a heading in the rendered block.
- `test_intent_renders_when_the_plan_file_is_missing` — an unreadable path plus an intent renders the intent and no guardrails, pinning that the intent half never depends on reading the file.
- `test_intent_headings_are_stable` — the exact heading strings, because step 5 renders the same block.
- `test_leaf_still_has_no_first_party_runtime_import` — re-run the source scan step 3 added; the new function must not have reached for `plan_tool.schema` to type its parameters.

**`tests/test_detail.py` (edited).** ~8 new cases plus 2 keyword updates:

- `test_plan_and_step_intent_reach_the_detail_prompt` — end-to-end through `render_detail_prompt` with a real fence block.
- `test_prompt_carries_no_intent_heading_when_no_intent_is_set` — a no-intent plan's substituted block equals `extract_plan_guardrails(plan_path)` and neither intent heading appears.
- `test_no_unresolved_template_placeholder_in_the_detail_prompt` — `"${"` is absent from the rendered prompt. Catches a half-landed rename.
- `test_generate_detail_passes_each_steps_own_intent` — drive `generate_detail` over a two-step plan whose steps carry different intents with a capturing fake invoker; each captured prompt carries its own step's intent and not the other's. This is the anti-hoisting guard.
- `test_concurrent_detail_passes_each_steps_own_intent` — the same assertion through the `jobs=2` path, since the pre-dispatch loop is a second copy of the same wiring.
- `test_detail_quality_prompt_never_receives_the_intent` — with a plan carrying both intents, the prompt from `render_detail_quality_prompt` contains the guardrail body and no intent heading. Pins the fence decision.
- `test_budget_breakdown_labels_the_fence_block` — `collect_blocks` carries `scope-fence` and no `plan-guardrails`.
- `test_plan_guardrails_are_authoritative_context` (existing) and `test_out_of_scope_reaches_the_detail_prompt` (existing) — switch the keyword to `scope_fence_block=`; their assertions are unchanged.
- `TestRenderDetailQualityPrompt::test_includes_authoritative_plan_guardrails` (existing) — untouched, still passes `plan_guardrails_block=`.

**Green-before-done gate.** Every case above must be green, and `uv run pytest tests/ -q` must be green, before the step is finished. No existing plan fixture may gain an `intent:` line to make anything pass — a fixture edit here would falsify the plan's no-migration claim.

## Acceptance criteria

- `render_scope_fence(p)` with no intent arguments returns a string equal to `extract_plan_guardrails(p)`, for a plan with all four fence sections and for one with none.
- `render_scope_fence(p, plan_intent="X", step_intent="Y")` returns a block whose plan-intent section precedes its step-intent section, and both precede `## Scope guardrails` and `## Out of scope`.
- `render_scope_fence(p, plan_intent="   ")` and `render_scope_fence(p, plan_intent="TODO")` each equal `render_scope_fence(p)`.
- A 500-character intent and a two-line intent each appear in the rendered block in full, character for character.
- `rg -n '^(from|import) plan_tool' plan_tool/scope_fence.py` returns nothing.
- `rg -n 'plan_guardrails_block' plan_tool/prompts/detail.md` returns nothing; `rg -n 'plan_guardrails_block' plan_tool/prompts/detail-quality.md` still matches.
- `git diff --stat plan_tool/prompts/detail.md` shows exactly one changed line.
- For a plan with no intent, `render_detail_prompt` produces a prompt containing no `${` and neither intent heading.
- For a plan carrying both intents, `render_detail_prompt`'s output contains both values and `render_detail_quality_prompt`'s output contains neither.
- `rg -n 'extract_plan_guardrails' plan_tool/detail.py` matches only the import and the `collect_detail_quality_findings` call site.
- `collect_blocks` from `render_detail_prompt` contains a `scope-fence` entry and no `plan-guardrails` entry.
- `git diff --name-only` lists only the five paths in this step's file list.
- `uv run pytest tests/ -q` is green.

## References

- [Be clear, direct, and detailed — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — how to phrase the injected intent headings so the block constrains the authoring model instead of reading as decoration.
- [Use XML tags to structure your prompts — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags) — on consistently delimiting authoritative sections; the reason the intent half reuses the guardrail half's `## <Heading>` shape rather than inventing a second delimiter.
- [Long context prompting tips — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — where authoritative context belongs relative to instructions in an already-long prompt, behind the choice to prefix the intent onto the existing block rather than open a new slot elsewhere.
- [`string` — Common string operations (Python 3 documentation)](https://docs.python.org/3/library/string.html#template-strings) — `safe_substitute`'s silent pass-through of an unmatched `${name}`, the failure mode the template rename has to avoid.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven form for the placeholder-vocabulary and empty-value cases.

## Applicable guardrails

- **"Allowed behavior changes: two optional frontmatter fields; one advisory finding class; rendered input reaching four templates — `detail.md`, `detail-jira.md`, `run.md`, `run-jira.md`. The run lane additionally gains the plan's existing guardrail and `## Out of scope` sections whether or not an intent is set, because it carries neither today. Nothing else."** This step is the detail half of that five-template delivery. The clause binds hardest on *when*: rendered input appears **only** when a field is set. That rules out any static text edit to `plan_tool/prompts/detail.md` — a reworded heading, an added directive sentence, or a retouched `_no plan-level guardrails or scope fence_` default would all change the prompt for plans that carry no intent at all. The template-variable rename is compatible precisely because a `${...}` name is invisible in the rendered output.
- **"No step ships a check comparing an intent against prose or against a diff."** The tempting site is concrete and inside this step: `collect_detail_quality_findings` is the third call site of the fence renderer, it already holds the authored detail body, and pointing it at `render_scope_fence` would be a one-word change. That change would put the intent and the `## Why` it is supposed to explain in front of a reviewing model together, which is the banned comparison arriving by accident rather than by design. The renderer also judges nothing itself: it filters on presence and placeholder shape, exactly as the section half already does, and reports nothing about what it skipped.
- **"Nothing becomes required at parse time, and no plan on disk is migrated."** Nothing here reads or writes a plan file's frontmatter, and no fixture gains an `intent:` line. Both new parameters default to `""`, so every existing caller keeps working untouched.
- **"The guard is that intent travels, never that something checks it."** This step is the travelling. Resist adding a warning when an intent is absent or multi-line at render time — step 2 owns absence, and a second home for the same rule is how the two drift.
- **"Findings proposing that intent be made required, that an agreement check be added, or that propagation widen past the four structural verbs are outside this fence."** If an audit proposes feeding the intent to the quality reviewer, or gating the render on any length rule, route it to `BACKLOG.md` rather than applying it here.

## Deferred

- **Getting the fence to the `run` and `run-jira` prompts** — step 5 owns `plan_tool/renderer.py` and both templates. This step only makes `render_scope_fence` exist and proves it works from one caller.
- ~~The jira-grade authoring prompt~~ — **no longer deferred; this step owns it** (decided 2026-08-01). `render_jira_detail_prompt` and `plan_tool/prompts/detail-jira.md` carry no fence block at all today, so unlike `detail.md` there is no existing slot — this step **adds** one, giving the jira grade the same `${scope_fence_block}` the run grade's sibling template already gets from step 5. The reason it cannot stay deferred: the jira grade's own required section is literally `## Intent`, so leaving it fence-free asks that author to state a step's intent with no access to `Step.intent`. `plan_tool/prompts/detail-jira.md` is in this step's declared `files:`.
- **The detail-quality review prompt** — refused, not merely postponed. See [Applicable guardrails](#applicable-guardrails).
- **What `split` and `merge` do with a step's intent** — the carved follow-up seed owns the rule. Until then a rebuilt step simply carries no intent, so it renders no step-intent section, which is the honest outcome.
- **Renaming `extract_plan_guardrails`** — the name still fits: after this step it renders exactly the guardrail half, and `render_scope_fence` is the name for the whole fence. Step 3's deferral is discharged by adding the second name rather than by renaming the first.
- **Documenting the fence block and the four propagation rules** — the carved follow-up seed owns `PLAN_FORMAT.md`, `docs/DETAIL_FLOW.md`, `docs/RUN_FLOW.md`, and `CLAUDE.md`. That includes `PLAN_FORMAT.md`'s citation of the renderer.
- **Renaming `render_detail_quality_prompt`'s `plan_guardrails_block` keyword** — it is accurate as it stands, and `plan_tool/prompts/detail-quality.md` is not in this step's files.
- **Aligning the leaf's placeholder vocabulary with `plan_tool/review.py:_BODY_PLACEHOLDER_RE`** — one covers `TBD` and one does not. Consolidating them changes how existing `## Out of scope` sections render, which this plan's fence does not allow. Route it to `BACKLOG.md`.
- **Measuring whether a delivered intent changes what `detail` writes** — needs real backend runs and a place to record them. Out of this plan.
