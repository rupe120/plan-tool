> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Pass both fence halves into the run and run-jira prompts through renderer.py

## Summary

This step gives `plan_tool/renderer.py` a `scope_fence_block` template variable built from step 4's `render_scope_fence`, and adds the matching `${scope_fence_block}` slot to `plan_tool/prompts/run.md` and `plan_tool/prompts/run-jira.md`. The main design decision copies the shape `_load_lessons_section` already uses in the same module: the slot **replaces an existing blank line** and the renderer returns `""` when there is no fence, so a plan carrying neither an intent nor a fence section renders the same run prompt bytes it renders today. The wrapper heading lives in `renderer.py`, not in the templates, so it disappears along with the block. On green, `run` and `run-jira` both carry the plan's intent, the step's intent, and the plan's guardrail and `## Out of scope` sections — the same block `detail` gets, from the same function — and the two templates each show a one-line diff.

## Table of Contents

- [Summary](#summary) — what ships, the empty-renders-nothing decision, and the result on green.
- [Why](#why) — the one surface that writes code and today sees no boundary at all.
- [Input](#input) — the four contracts this step reads from steps 3 and 4 and from the run lane, and what the tests cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — five edited files, no new files.
- [Implementation](#implementation) — the new variable, the two slots, the "unchanged" claim resolved for `run`, and six gotchas.
- [Tests](#tests) — ~15 renderer cases, ~7 launcher cases, and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — greps, diffs, and equalities a reviewer can run.
- [References](#references) — the `string.Template` and prompt-placement behavior this step leans on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the two places breaking them is tempting.
- [Deferred](#deferred) — what the carved follow-up owns, and the consolidations routed out.

## Why

`run` is the surface that writes code, and it is the one surface that gets no statement of the boundary at all. The prompt it renders today carries a plan title, a step title, a detail body, and a file list — nothing saying what the work is for and nothing saying what the plan refuses to build. `detail` has had the negative half for a while (`${plan_guardrails_block}` in `plan_tool/prompts/detail.md`), and step 4 gave it the positive half too. `run` has had neither. That is the most expensive place for the gap to sit: creep during authoring costs a re-audit, creep during execution costs code. Step 3 made the fence renderer importable from `plan_tool/renderer.py` without closing an import cycle, and step 4 made it render both halves. This step is the second and last caller — the one that makes "both halves travel, through one renderer, to both `detail` and `run`" true.

## Input

Four contracts this step reads and does not own. Read each off HEAD before you start; where a landed name differs from a name below, the landed name wins.

- **Step 4's fence renderer.** `plan_tool/scope_fence.py:render_scope_fence(plan_path, *, plan_intent="", step_intent="")` returns the whole fence as one string: plan intent, step intent, then the guardrail sections and `## Out of scope`, each rendered `## <Heading>\n\n<body>` and joined with a blank line. It returns `""` when nothing survives. It takes **strings, not a `Plan` or a `Step`** — the leaf may not import `plan_tool.schema` — so this step's caller does the unwrapping.
- **`plan_tool/scope_fence.py` is not in this step's file list.** Call the leaf exactly as step 4 shipped it. If the block needs a different shape for `run`, shape it in `plan_tool/renderer.py`, not in the leaf.
- **Step 1's two schema fields.** `Plan.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD) and `Step.intent` (created by step 1 in `plan_tool/schema.py`; not at HEAD), each `Optional[str] = None`. `None` becomes `""` at this call site.
- **The run lane's call site.** `plan_tool/launcher.py:run_step` calls `render_prompt` inside its `prompt_build` phase with `collect_blocks=budget_blocks`, `plan_path=plan_path`, and `detail_grade=detail_grade`. It is the **only** caller that renders `run.md` or `run-jira.md`, and it always passes `plan_path`. The other `render_prompt` call sites in `plan_tool/launcher.py` — `apply_finding`, its follow-up render, `run_deep_verify`, and `run_all_done_steps` — pass no `plan_path`, and none of their templates has the slot. `run_all_done_steps` refuses `MUTATING_MODES` outright, so it can never reach `run.md`.

**What this step cannot verify.** Nothing about whether a fence in the run prompt actually keeps an executing model inside it. The tests assert what lands in the prompt text. Measuring whether a delivered fence changes what `run` writes needs real backend runs and somewhere to record them — out of this plan.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/renderer.py` — add a `_scope_fence_section` helper and a `scope_fence_block` entry to `_build_variables`' returned map; append the block's byte count to `collect_blocks`; extend the module docstring's template-variable list.
- `plan_tool/prompts/run.md` — one changed line: the blank line between `${step_files}` and `## What to do` becomes `${scope_fence_block}`.
- `plan_tool/prompts/run-jira.md` — the same one changed line, in the same position.
- `tests/test_renderer.py` — ~15 new cases in a new class for the fence block.
- `tests/test_launcher.py` — ~7 new cases covering the run lane end to end.

## Implementation

**What should be true when the step is done:** `run` and `run-jira` both carry the plan's fence and both intents, built by the same call to the same function that feeds `detail`; a plan with no intent and no fence sections renders the run prompt byte for byte as it does today; and no other mode's prompt changes at all.

### The new variable

In `plan_tool/renderer.py:_build_variables`, build the block and add it to the returned map under the key `scope_fence_block` — the same name step 4 settled for `plan_tool/prompts/detail.md`. Reusing the name is the point: one name, one meaning, two surfaces.

The wrapping helper should read like its neighbor. `_load_lessons_section` already returns either `""` or `"\n## Lessons from earlier steps\n\n{body}\n"`, with the heading held in Python rather than in the template — that is exactly the shape to copy. One way:

```
_scope_fence_section(plan, step, *, plan_path) -> str
```

- **Return `""` when the fence is empty.** No heading, no lead-in, no blank line. This is what makes the unchanged case unchanged.
- **Return `"\n" + lead_in + "\n\n" + fence + "\n"` otherwise**, matching the lessons helper's leading and trailing newlines so the slot slots into the template's line structure.
- **Return `""` when `plan_path` is `None`.** The guardrail half cannot be read without a path, and every caller that passes no path renders a template with no slot. Recommend a short comment saying so, and pin it with a test so a future caller that renders `run` without a path fails loudly in review rather than silently losing the fence.
- **Unwrap the intents here:** `plan_intent=plan.intent or ""`, `step_intent=step.intent or ""`. The leaf never sees `None`.

### The lead-in has one job: say whose fence this is

The block's own headings are `## Scope guardrails`, `## Out of scope`, and step 4's two intent headings. Dropped into `run.md` they sit at the same heading level as the template's own `## Files in scope` and `## What to do`, and in `run-jira.md` the artifact's `## Out of scope` section is already explained a few lines above. So the prompt ends up with two things called "out of scope" from two different sources.

**The lead-in must name the block as the plan-level fence** and say it binds. One way:

> **Scope fence (authoritative, from the plan).** These sections state what the whole plan is for, what this step is for, and what the plan will not build. They bind this step. Do not widen past them.

Wording is yours. Two rules are not:

- **Do not re-level the fence's headings.** Step 4 pinned those heading strings, and `detail` renders the same block. Rewriting `## Out of scope` to `### Out of scope` here would make the two surfaces disagree about a string a test in `tests/test_scope_fence.py` already pins.
- **Pin the lead-in with a test.** It is the only prose this step mints, and it appears on the one surface that writes code.

### The two template edits

Both templates have the same three lines:

```
${step_files}

## What to do
```

Replace the **blank line** with `${scope_fence_block}` in each. The result:

- **Empty fence → the value is `""` → the line is empty → the bytes are exactly what they are today.** That is the whole reason to replace a blank line instead of adding a new one, and it is what makes the plan's "unchanged prompts" requirement hold by the way the code is built rather than by a test getting lucky.
- **Non-empty fence → a blank line, the lead-in, a blank line, the fence, a blank line, then `## What to do`.**
- **Nothing else in either template changes.** Not the `## Files in scope` heading, not the `## What to do` prose, not the closing `## Validation` / `## Summary` contract.

Placement between the files list and the instructions is deliberate: the prompt states the footprint, then the boundary, then what to do about them — and it keeps the fence away from the tail, which is where the test directive gets appended and where the harness-parsed closing contract lives.

### What "unchanged prompts" means for `run`

The plan asks for unchanged prompts when no intent is set. For `detail` that is literal, and step 4 delivers it. For `run` the claim is narrower, and this is the reading to hold:

- **A plan with no intent and no fence sections renders the run prompt byte for byte as today.** That is the checkable property, and it is what the blank-line replacement buys.
- **A plan that already carries `## Out of scope` gains it in the run prompt.** That gain is this step's whole point — the plan's Problem statement names "`run` receives neither half" as one of the three costs it closes, and this step's title says both halves travel. It is also not new content: it is the same block `detail` has been receiving all along.

Do not narrow this step to the intent half to make the wider reading true. The step title, the plan's Architecture section, and the plan's acceptance criterion ("Intent reaches both the `detail` and `run` prompts through one renderer") all name both halves.

### One map, two templates

`render_prompt` picks `run-jira.md` over `run.md` when `detail_grade == "jira"` and `mode == "run"`, then calls `_build_variables` once either way. Keep it that way: the fence is built in `_build_variables`, above the template choice, so the two grades cannot drift into rendering different fences. The **only** difference between them stays the detail body and the template prose.

### The budget breakdown

`collect_blocks` already receives `("step detail", n)` and `("lessons", n)` from `_build_variables`, and `plan_tool/launcher.py:run_step` feeds the list to the prompt-budget advisory. Append `("scope fence", len(block.encode("utf-8")))` alongside them, measured from the string this render already built — no second file read, same rule the existing two entries follow. Append it unconditionally, like `lessons`, so a zero-byte fence shows as `0 B` rather than vanishing from the breakdown.

Use `"scope fence"` — space-separated lowercase, matching the two labels beside it in the same list. Step 4's detail-side label is `scope-fence` because `plan_tool/detail.py`'s list is hyphenated throughout. Two lists, two local conventions; **do not unify them here**, and do not "fix" one to match the other.

### Six gotchas

- **`safe_substitute` fails silently.** A slot added to a template with no matching key leaves the literal `${scope_fence_block}` in the prompt and raises nothing. Land the variable and both slots in one edit, and keep the existing "no leftover `${`" assertion honest.
- **A substituted value is not re-scanned.** `string.Template.safe_substitute` makes one pass over the *template*, so a `${foo}` sitting inside a plan's `## Out of scope` prose lands in the prompt verbatim and is never treated as a placeholder. Correct behavior — but `tests/test_renderer.py:TestAllModesShip::test_template_renders` asserts `"${" not in prompt`, so any fixture feeding a fence into that assertion must carry no literal `${`.
- **The test directive is appended after rendering.** `run_step` adds `_test_directive(step.change_type)` to the rendered string under mutating modes. The fence sits mid-prompt, so the directive stays last — assert that, because a fence appended at the tail would push it out of position and also collide with the closing `## Validation` / `## Summary` contract the harness parses.
- **`run_all_done_steps` renders without a `plan_path`.** It refuses `MUTATING_MODES`, so it never reaches `run.md`; its review-style templates have no slot. Nothing to do — but it is the call site that looks like it needs a fix and does not.
- **The prompt now says some things twice.** A run-grade detail body carries its own `## Applicable guardrails`, and a jira-grade artifact carries its own `## Out of scope`. Both are step-scoped restatements; the fence block is the plan-level source. That is why the lead-in names the source rather than just labeling the block authoritative.
- **The block is per-step, not per-plan.** Step intent varies across steps, so the value must be rebuilt on every render. `_build_variables` runs once per `render_prompt` call, so this is free — do not cache the block on the plan or hoist it out of any loop that calls the renderer.

## Tests

### Tests for this step

**`tests/test_renderer.py` (edited).** ~15 new cases in a new `TestScopeFenceInRunPrompt` class, sited beside `TestRenderRunPrompt` and `TestRenderJiraGradePrompt`:

- `test_fence_reaches_the_run_prompt` — a plan with `## Out of scope` and both intents renders all of them into `mode="run"`.
- `test_fence_reaches_the_run_jira_prompt` — the same plan at `detail_grade="jira"` renders the same content.
- `test_run_and_run_jira_carry_the_same_fence` — the fence substring is identical in both prompts. The two-grades-cannot-drift guard.
- `test_plan_intent_reaches_the_run_prompt` — plan intent alone.
- `test_step_intent_reaches_the_run_prompt` — step intent alone.
- `test_each_step_gets_its_own_intent` — two steps with different intents; each prompt carries its own and not the other's.
- `test_fenceless_plan_renders_no_fence_block` — no intent, no fence sections: neither intent heading nor the lead-in appears.
- `test_fenceless_prompt_keeps_one_blank_line_before_what_to_do` — the rendered prompt contains the files list followed by exactly one blank line and `## What to do`. This is the byte-for-byte-unchanged check.
- `test_no_plan_path_renders_an_empty_fence` — `mode="run"` with `plan_path=None` renders no fence and no leftover `${`.
- `test_fence_sits_between_the_files_list_and_the_instructions` — index ordering of the three markers.
- `test_lead_in_names_the_plan_as_the_source` — the exact lead-in string, since it is the only prose this step mints.
- `test_fence_block_is_measured_in_collect_blocks` — a `scope fence` entry appears with the block's real byte count.
- `test_empty_fence_still_reports_a_zero_byte_block` — the breakdown entry is present at 0 bytes.
- `test_dollar_brace_in_the_fence_survives_verbatim` — a plan whose `## Out of scope` contains `${example}` lands it unchanged; nothing is substituted a second time.
- `test_other_modes_render_no_fence_block` — for the same fenced plan, a `check`-mode prompt contains no lead-in and no `## Scope guardrails`, because only the two run templates have the slot.

**`tests/test_launcher.py` (edited).** ~7 new cases:

- `test_run_step_prompt_carries_the_fence` — drive `run_step` with a capturing fake invoker over a fenced plan; the invoked prompt carries both intents and the plan's `## Out of scope`.
- `test_jira_grade_run_prompt_carries_the_fence` — the same through `detail_grade="jira"`, in `TestRunStepJiraGrade`.
- `test_each_run_steps_prompt_carries_its_own_intent` — run two steps with different intents; each captured prompt carries its own.
- `test_test_directive_stays_last_after_the_fence` — under a mutating mode the appended test directive is still at the tail.
- `test_prompt_budget_breakdown_includes_the_scope_fence` — reuse `TestRunStepPromptBudget._spy_warn`; `kwargs["blocks"]` carries a `scope fence` entry.
- `test_fenceless_plan_run_prompt_has_no_fence` — a plan with neither intent nor fence sections produces a prompt with no lead-in.
- `test_dry_run_preview_shows_the_fence` — `dry_run=True` prints the fence to stdout, so an operator previewing a step sees the boundary the executor will see.

**Green-before-done gate.** Every case above must be green, and `uv run pytest tests/ -q` must be green, before this step is finished. No existing plan fixture may gain an `intent:` line or a fence section to make anything pass — a fixture edit here would falsify the plan's no-migration claim.

## Acceptance criteria

- `rg -n 'scope_fence_block' plan_tool/prompts/run.md plan_tool/prompts/run-jira.md` matches exactly once in each file.
- `git diff --stat plan_tool/prompts/run.md plan_tool/prompts/run-jira.md` shows one changed line per file, with no net line-count change.
- For a plan with no intent and no fence sections, `render_prompt(plan, step, repo_root=..., mode="run", plan_path=...)` contains the step's file list followed by exactly one blank line and then `## What to do`.
- For the same plan, `render_prompt(..., mode="run")` contains no lead-in text and no `## Scope guardrails`.
- For a plan carrying both intents and `## Out of scope`, the `run` prompt and the `run-jira` prompt contain the same fence substring.
- `render_prompt(..., mode="run", plan_path=None)` renders no fence and contains no `${`.
- A `check`-mode prompt for a fenced plan contains no fence content.
- `collect_blocks` from a `run` render contains exactly one `scope fence` entry, whose byte count equals the block's UTF-8 length.
- `rg -n 'render_scope_fence' plan_tool/renderer.py` matches; `rg -n 'extract_plan_guardrails' plan_tool/renderer.py` returns nothing.
- `git diff --name-only` lists only the five paths in this step's file list.
- `uv run pytest tests/ -q` is green.

## References

- [`string` — Common string operations (Python 3 documentation)](https://docs.python.org/3/library/string.html#template-strings) — `safe_substitute`'s silent pass-through of an unmatched `${name}`, and its single pass over the template, which is why a `${…}` inside a substituted fence is never re-substituted.
- [Long context prompting tips — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — where authoritative context belongs relative to instructions, behind placing the fence between the files list and `## What to do`.
- [Be clear, direct, and detailed — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/be-clear-and-direct) — how to phrase the lead-in so the block constrains the executing model instead of reading as decoration.
- [Use XML tags to structure your prompts — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags) — on delimiting authoritative sections consistently; the reason the fence keeps the heading shape step 4 pinned rather than getting a second delimiter here.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven form for the two-grade and per-mode cases.

## Applicable guardrails

- **"Allowed behavior changes: two optional frontmatter fields; one advisory finding class; rendered input reaching four templates — `detail.md`, `detail-jira.md`, `run.md`, `run-jira.md`. The run lane additionally gains the plan's existing guardrail and `## Out of scope` sections whether or not an intent is set, because it carries neither today. Nothing else."** This step is the run half of that five-template delivery — `run` and its grade variant `run-jira` are one surface with two templates, both fed by one variable. The clause binds hardest on the templates' **static text**: any reworded heading, added directive sentence, or new placeholder line would change the prompt for every plan on disk, including plans carrying nothing. That is why the only template edit is a blank line becoming a slot, and why the lead-in lives inside the substituted value.
- **"No step ships a check comparing an intent against prose or against a diff."** The tempting site is inside this step: `plan_tool/launcher.py:run_step` sees the step's intent and, after the call, the diff the step produced — the post-flight gate is right there and comparing the two is a few lines. Refuse it. This step renders text and asserts nothing about it. `renderer.py` also judges nothing: it filters on presence and placeholder shape, exactly as step 4's leaf already does, and reports nothing about what it skipped.
- **"Nothing becomes required at parse time, and no plan on disk is migrated."** Nothing here reads or writes frontmatter, and no test fixture gains an `intent:` line. A plan with no intent renders `plan.intent or ""` and gets the guardrail half alone.
- **"The guard is that intent travels, never that something checks it."** This step is the travelling, on the surface that matters most. Resist adding a warning when a step reaches `run` with no intent — step 2 owns absence, over-length, and placeholders, and a second home for the same rule is how the two drift.
- **"Findings proposing that intent be made required, that an agreement check be added, or that propagation widen past the four structural verbs are outside this fence."** If an audit proposes gating a run on a present intent, feeding the fence to the review or reconcile prompts, or checking the diff against the intent, route it to `BACKLOG.md` rather than applying it here.

## Deferred

- **The review, reconcile, and verify prompts** — `plan_tool/prompts/review.md`, `run-reconcile.md`, `reconcile-deep.md`, `check.md`, and the rest gain no slot. Their call sites pass no `plan_path`, and widening propagation past `detail` and `run` is outside the plan's fence. Route any request for it to `BACKLOG.md`.
- **`plan_tool/prompts/apply-finding.md`** — same reason, plus its prompt already carries the full plan text, so the fence would be a third copy of content it holds.
- **The jira-grade authoring prompt** — `plan_tool/prompts/detail-jira.md` is **step 4's file, and step 4 shipped it**: it reversed the earlier deferral and added the fence slot there, so both detail grades and both run grades now carry the fence. Nothing about it is deferred; it is simply not this step's file.
- **What `split` and `merge` do with a step's intent** — the carved follow-up seed owns the rule. Until then a rebuilt step carries no intent, renders no step-intent section, and the fence shows the plan half alone.
- **Carrying intent into the scope-out and reground seeds** — the carved follow-up seed owns `plan_tool/scope_out.py` and `plan_tool/reground.py`.
- **Documenting the run lane's fence block** — the carved follow-up seed owns `docs/RUN_FLOW.md`, `PLAN_FORMAT.md`, `docs/DETAIL_FLOW.md`, and `CLAUDE.md`. That includes recording the two prompt slots and the four propagation rules.
- **Unifying the two budget-breakdown label conventions** — `plan_tool/renderer.py` uses space-separated labels and `plan_tool/detail.py` uses hyphenated ones. Two separate lists on two separate surfaces; consolidating them touches a file outside this step. Route it to `BACKLOG.md` if it ever costs anything.
- **A `run`-side preflight that refuses a step with no intent** — refused, not postponed. Presence is advisory and step 2 is its only home.
- **Measuring whether a delivered fence changes what `run` writes** — needs real backend runs and a place to record them. Out of this plan.
