> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Move the plan scope-fence rendering into a shared leaf module

## Summary

This step creates `plan_tool/scope_fence.py` and moves the plan scope-fence renderer into it: `extract_plan_guardrails` out of `plan_tool/detail.py`, plus the two pieces it depends on today — the plan-body H2 splitter (`extract_h2_sections` and its `_H2_HEADING_RE`) and the three author-supplied guardrail heading names (`_GUARDRAIL_BODY_SECTIONS`) — out of `plan_tool/create.py`. The main design decision is **one implementation plus re-exports, not a mirrored copy**: the leaf owns the code, and `detail.py` and `create.py` import the moved names back so every existing import path keeps returning the same object. Behavior does not change at all — this is a pure move, so a plan renders the exact same `${plan_guardrails_block}` bytes before and after. On green, `plan_tool/scope_fence.py` imports nothing first-party, `plan_tool/reprocess.py` has a zero-line diff, and `renderer.py` has a fence renderer it can import in step 5 without closing an import cycle.

## Table of Contents

- [Summary](#summary) — what moves, the one-implementation decision, and the result on green.
- [Why](#why) — the import cycle that makes the move necessary before steps 4 and 5.
- [Input](#input) — the four contracts this step reads but does not own.
- [Files (creates vs edits)](#files-creates-vs-edits) — two new files, four edited.
- [Implementation](#implementation) — what lands in the leaf, why not a mirrored copy, and the three gotchas.
- [Tests](#tests) — ~20 cases in the new leaf suite, mostly relocated; the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — greps and identity checks a reviewer can run.
- [References](#references) — the `re` and import-system behavior the move relies on.
- [Applicable guardrails](#applicable-guardrails) — the fence's "one named move" clause and how far it reaches.
- [Deferred](#deferred) — what steps 4 and 5 and the carved follow-up own, and the consolidations routed out.

## Why

`plan_tool/detail.py:extract_plan_guardrails` is the one function that renders a plan's scope fence, and it sits at the bottom of the heaviest import chain in the package. `detail.py` imports `plan_tool.launcher` at module load; `launcher.py` imports `plan_tool.renderer`. So `renderer.py` cannot import anything out of `detail.py` — that closes a cycle. Step 5 needs exactly that: `renderer.py` must render the same fence for the `run` and `run-jira` prompts that `detail` already renders. The function also reaches sideways for its rules — it does a call-time `from plan_tool.create import ...` inside its own body, because the heading names and the H2 splitter live in `create.py`, another orchestrator. Moving all three into a leaf below everything is what makes one renderer serve both callers instead of two copies drifting apart.

## Input

Four contracts this step reads and does not own. Read each off HEAD; where a landed name differs from a name below, the landed name wins.

- **`plan_tool/create.py:extract_h2_sections`'s recognition rules.** Keys are the lowercased heading text; a section body runs from the heading line to the next H1 or H2 or EOF, stripped; a duplicate heading keeps the first occurrence; an empty body drops the section entirely; and a CommonMark closing sequence (`## Audit guardrails ##`) is normalized off before lowercasing. Every one of these is behavior the fence depends on and none may change here.
- **`plan_tool/create.py:_GUARDRAIL_BODY_SECTIONS`** — the three author-supplied headings, in order: `Scope guardrails`, `Audit guardrails`, `Expected placement`. Order is part of the contract: the fence renders these three first, then `Out of scope`.
- **The prompt slot.** `${plan_guardrails_block}` appears in `plan_tool/prompts/detail.md` and `plan_tool/prompts/detail-quality.md`. The empty-case placeholder text `_no plan-level guardrails or scope fence_` is substituted by `render_detail_prompt` / `render_detail_quality_prompt`, **not** by the extractor — the extractor returns `""`. Keep that split; the prompt-side default is not this step's to move.
- **`plan_tool/reprocess.py`'s import.** It does `from plan_tool.create import _H2_HEADING_RE, extract_h2_sections` at module level. `reprocess.py` is **not** in this step's file list, so both names must stay importable from `plan_tool.create` after the move.

Two facts about the current implementation worth pinning before you touch it:

- **It does not split frontmatter.** Unlike `plan_tool/detail.py:extract_plan_references` (which runs `_split_frontmatter` first), `extract_plan_guardrails` feeds the whole file text to the H2 matcher. This is safe because YAML requires a top-level key's continuation lines to be indented, so frontmatter cannot produce a `##` at column 0. Preserve the behavior — and note the leaf could not call `_split_frontmatter` anyway, since `plan_tool/parser.py` pulls in `schema.py` and pydantic.
- **What this step cannot verify.** Nothing about whether the fence block is any *good* as prompt input. The only claim the tests can make is that the rendered block is unchanged and the leaf's import graph is clean.

## Files (creates vs edits)

**New files:**

- `plan_tool/scope_fence.py` — the leaf. Owns the fence renderer, the plan-body H2 splitter, the guardrail heading names, and the `_(TODO)_` placeholder check.
- `tests/test_scope_fence.py` — the leaf's suite: relocated unit cases plus new leaf-discipline and re-export coverage.

**Existing files (edits only):**

- `plan_tool/detail.py` — delete the definitions of `extract_plan_guardrails`, `_DETAIL_FENCE_SECTIONS`, `_is_placeholder_section`, and `_SECTION_PLACEHOLDER_RE`; import them back from the leaf and re-export. Delete the call-time `from plan_tool.create import ...` that lived inside `extract_plan_guardrails`. The three call sites (in `generate_detail`, in the jira-grade authoring path, and in the detail-quality audit that builds `render_detail_quality_prompt`) keep calling the same name.
- `plan_tool/create.py` — delete the definitions of `extract_h2_sections`, `_H2_HEADING_RE`, and `_GUARDRAIL_BODY_SECTIONS`; import them back from the leaf and re-export under the names outside modules already use.
- `tests/test_detail.py` — relocate the five `TestExtractPlanGuardrails` unit cases to the leaf's suite; keep the prompt-wiring case that drives `render_detail_prompt`.
- `tests/test_create.py` — relocate the `TestExtractH2Sections` class and the module-level `test_atx_closing_sequence_guardrail_heading_is_recognized` case to the leaf's suite. Every create-flow guardrail test (the ones built on `_run_guardrail_create` and `_extract_supplied_guardrails`) stays put and untouched.

## Implementation

**What should be true when the step is done:** one module owns "read a plan file, pick out the fence sections, render them as a block", that module imports no first-party code, and `detail.py` / `create.py` / `reprocess.py` all behave exactly as they do today.

### What lands in the leaf

Five things, all currently split across two orchestrators:

- **`extract_plan_guardrails(plan_path) -> str`** — the renderer, moved from `plan_tool/detail.py` with its body unchanged except that the call-time `create` import becomes a module-level reference to the leaf's own names.
- **The plan-body H2 splitter** — `extract_h2_sections` and `_H2_HEADING_RE`, moved from `plan_tool/create.py`.
- **The guardrail heading names** — `_GUARDRAIL_BODY_SECTIONS`, moved from `plan_tool/create.py`. Since three modules now read it, give it a public name in the leaf (`GUARDRAIL_BODY_SECTIONS` reads fine) and let `create.py` alias or update its four internal uses — your call.
- **The fence section list** — `_DETAIL_FENCE_SECTIONS`, currently `("Out of scope",)`, moved from `plan_tool/detail.py`.
- **The placeholder check** — `_is_placeholder_section` and `_SECTION_PLACEHOLDER_RE`, moved from `plan_tool/detail.py`. `plan_tool/detail.py:extract_plan_references` also calls the check and stays in `detail.py`, so `detail.py` imports it back. The reason the comment on `_SECTION_PLACEHOLDER_RE` gives for keeping it out of `plan_tool/review.py` still holds after the move: the leaf does not import `review` either.

### The key decision: one implementation, not a mirrored copy

The alternative is that the leaf writes its own H2 splitter and its own copy of the three heading names, and `create.py` keeps its versions. That is what this repo usually does — `plan_tool/jira_grade.py` mirrors a heading matcher rather than importing one, and `plan_tool/roadmap_artifacts.py` mirrors the frontmatter fence scan rather than importing `plan_tool/parser.py`. **Reject it here**, for one reason those cases do not share: this code reads the very sections `create` *writes*. A mirror that drifts by one rule — say it stops stripping the closing `##` — silently stops recognizing a heading a real seed produced, and nothing goes red. The usual mirror cases describe different artifacts, so there is nothing to drift against.

Importing is legal in this direction. The leaf has no first-party imports, so `create.py → scope_fence` and `detail.py → scope_fence` are both downward edges that close no cycle. `plan_tool/detail_artifacts.py` is the precedent to copy: it pulled slug and path helpers out of `detail.py` into a leaf and `detail.py` re-imports them, with its module docstring stating that the re-exports keep every historical import path returning the same objects. Do the same here, and say so in the leaf's docstring.

### Constraints that are not free to vary

- **Leaf discipline is the whole point.** `plan_tool/scope_fence.py` imports only the standard library — `re`, `pathlib`, `typing`. No `plan_tool.parser`, no `plan_tool.schema`, no lazy first-party import inside a function body (that shape is invisible to an import-time check and is the likeliest way a leaf quietly loses leaf-ness).
- **Re-exports must be the same object, not a copy.** `plan_tool.detail.extract_plan_guardrails is plan_tool.scope_fence.extract_plan_guardrails` has to hold, so a monkeypatch on either path patches the one implementation and existing tests that patch the `detail` path keep working.
- **`plan_tool/reprocess.py` gets a zero-line diff.** Its `from plan_tool.create import _H2_HEADING_RE, extract_h2_sections` must keep resolving. That fixes which private name `create.py` re-exports.
- **Render order holds.** The three guardrail headings first, in their declared order, then `Out of scope`; each rendered as `## <Heading>\n\n<body>` and joined with a blank line. Empty and placeholder-only sections stay out.
- **No behavior change, none.** No new parameter, no new default, no tidying of the frontmatter question, no error handling added to the `OSError` path. A refactor step in this plan is allowed to change zero rendered bytes.

### Three gotchas

- **`_H2_HEADING_RE` is two different regexes.** `plan_tool/create.py`'s is `^(#{1,2})[ \t]+(.+?)[ \t]*$` and splits plan-body sections. `plan_tool/detail.py`'s is `^##\s+([A-Za-z]+)` and grabs the first word of a *detail file's* heading for the required-section check (`parse_detail_file_sections` and the required-H2 scan both use it). Only the `create.py` one moves. Importing the leaf's version into `detail.py` under that name would shadow detail's own and break detail-file section parsing with nothing obvious failing at import time.
- **Three modules already start with `scope_`.** `plan_tool/scope_guard.py` (post-apply file-scope diffing) and `plan_tool/scope_out.py` (the carve-and-seed remedy) are unrelated to this one. State the non-relationship in the new module's docstring so a later reader does not assume a family.
- **`detail.py` keeps two other lazy `create` imports.** The ones in the split and merge helpers exist to avoid the `create ↔ detail` cycle and are not this step's business. Only the one inside `extract_plan_guardrails` goes away.

### Optional, if you want it

One way to make steps 4 and 5 easier: split the renderer into a text-taking core and a thin path-reading wrapper, following the `parse_*(text)` / `load_*(path)` split `plan_tool/jira_grade.py` uses. It costs nothing here, keeps the path-bearing entry point callers already have, and gives the next two steps a seam their tests can drive without a `tmp_path` fixture. The move alone satisfies this step, so treat this as a recommendation, not a requirement.

## Tests

### Tests for this step

**`tests/test_scope_fence.py` (new).** Relocated cases keep their current names and bodies — the point is that no behavior test is lost:

- `test_returns_only_recognized_nonempty_guardrails` — recognized headings render, an unrelated H2 does not, and a closing-`##` heading is still matched.
- `test_missing_file_returns_empty` — an unreadable path returns `""`.
- `test_out_of_scope_is_threaded_as_fence` — the canonical `## Out of scope` section reaches the block.
- `test_placeholder_out_of_scope_is_omitted` — a `_(TODO)_` body renders nothing.
- `test_guardrails_precede_out_of_scope` — the fixed render order.
- `test_returns_empty_for_empty_input` — the splitter on `""`.
- `test_lowercases_titles_and_strips_body` — key casing and body trimming.
- `test_ignores_h1_and_h3` — only H2 headings become keys.
- `test_keeps_first_duplicate_title` — first occurrence wins.
- `test_drops_empty_section_body` — an empty section is absent, not empty-valued.
- `test_body_stops_at_next_h2` — an H3 stays inside its parent H2's body.
- `test_atx_closing_sequence_guardrail_heading_is_recognized` — `## Audit guardrails ##` normalizes.

New cases, because the placeholder helper and the leaf itself have no coverage today:

- `test_todo_only_section_is_placeholder` — every non-blank line a `_(TODO)_` / `TODO` / `(TODO)` variant.
- `test_mixed_prose_and_todo_is_not_placeholder` — one real line makes the section real.
- `test_empty_body_is_not_placeholder` — an empty string is not a placeholder.
- `test_reads_the_whole_file_without_splitting_frontmatter` — documents that the file text goes to the matcher unsplit, so the move cannot quietly change it.
- `test_leaf_has_no_first_party_runtime_import` — reads the module's own source and asserts no `^(from|import) plan_tool` line. This is the one that catches a lazy import inside a function; the subprocess check below cannot.
- `test_leaf_imports_no_other_plan_tool_module` — imports the leaf in a fresh interpreter under a stub `plan_tool` package (the real package `__init__` eagerly imports `detail`/`review`, which would mask what the leaf pulls in) and asserts no other `plan_tool.*` module landed in `sys.modules`. Model it on `tests/test_detail_artifacts.py:TestLeafAndReexports` and `tests/test_jira_grade.py:TestLeafImportDiscipline`.
- `test_detail_reexports_the_same_objects` — `plan_tool.detail.extract_plan_guardrails is plan_tool.scope_fence.extract_plan_guardrails`, and the same identity for the placeholder check.
- `test_create_reexports_the_same_objects` — same identity for `extract_h2_sections`, the H2 regex, and the guardrail heading tuple, so `plan_tool/reprocess.py`'s import still lands on the leaf's implementation.

**`tests/test_detail.py` (edited).** Delete the five relocated cases. Keep `test_out_of_scope_reaches_the_detail_prompt`, which drives the block through `render_detail_prompt` — it stays because it covers `detail`'s wiring, and it also proves the re-export works from a consumer's point of view. `TestRenderDetailPromptIncludesPlanRefs::test_plan_guardrails_are_authoritative_context` is untouched.

**`tests/test_create.py` (edited).** Delete the relocated `TestExtractH2Sections` class and the ATX case. Every create-flow guardrail test stays untouched and now exercises `create` through the leaf — that is the proof the re-export path works inside the real create flow, so do not rewrite them to import from the leaf.

**Green-before-done gate.** Every case above must be green, and the full suite (`uv run pytest tests/ -q`) must be green, before this step is finished. Because tests are relocated rather than added, the suite's total collected count must not go *down* — a drop means a case was dropped in the move.

## Acceptance criteria

- `rg -n '^(from|import) plan_tool' plan_tool/scope_fence.py` returns nothing.
- Importing `plan_tool.scope_fence` under a stub `plan_tool` package in a fresh interpreter leaves no other `plan_tool.*` entry in `sys.modules`.
- `rg -n 'invoker|claude|subprocess' plan_tool/scope_fence.py` returns nothing — the leaf spends no Claude call and has no invoker seam.
- `plan_tool.detail.extract_plan_guardrails is plan_tool.scope_fence.extract_plan_guardrails` evaluates `True`.
- `plan_tool.create.extract_h2_sections is plan_tool.scope_fence.extract_h2_sections` evaluates `True`, and the same identity holds for the H2 regex and the guardrail heading tuple.
- `from plan_tool.create import _H2_HEADING_RE, extract_h2_sections` still resolves — this is `plan_tool/reprocess.py`'s import line, and `reprocess.py` has a zero-line diff.
- `plan_tool/detail.py` still defines its own `_H2_HEADING_RE` (`^##\s+([A-Za-z]+)`), and `parse_detail_file_sections` still uses it.
- The guardrail import inside `extract_plan_guardrails` is gone; the two lazy `from plan_tool.create import ...` lines in `detail.py`'s split and merge helpers remain.
- For a plan carrying all four fence sections, `extract_plan_guardrails` returns the same string as at HEAD: `## Scope guardrails`, `## Audit guardrails`, `## Expected placement`, `## Out of scope`, in that order, blank-line joined.
- `git diff --name-only` lists only the six paths in this step's file list.
- `uv run pytest tests/ -q` is green and the collected-test count is not lower than at HEAD.

## References

- [`re` — Regular expression operations (Python 3 documentation)](https://docs.python.org/3/library/re.html) — `re.MULTILINE` anchoring and non-greedy matching, the two behaviors the moved H2 matcher depends on and must keep.
- [The import system (Python 3 language reference)](https://docs.python.org/3/reference/import.html) — module caching in `sys.modules`, which is what makes a re-export the same object and what the leaf-discipline subprocess check reads.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven form for the relocated section-recognition cases.

## Applicable guardrails

- **"Allowed reorganization: one named move — extract the plan scope-fence renderer out of `plan_tool/detail.py` into a shared leaf (`plan_tool/scope_fence.py`). Nothing else moves."** This step *is* that move. The judgment call it forces: the H2 splitter and the guardrail heading names also leave `create.py`, and that reads at first like a second move. It is not — the renderer cannot live in a leaf while its recognition rules live in an orchestrator the leaf may not import, so those two pieces are part of the one named move, not an extra one. The fence still bites everywhere else: nothing in `plan_tool/reprocess.py`, `plan_tool/review.py`, `plan_tool/jira_grade.py`, or `plan_tool/renderer.py` moves, and no other duplicated matcher gets consolidated on the way past.
- **"Allowed behavior changes: two optional frontmatter fields; one advisory finding class; rendered input reaching four templates — `detail.md`, `detail-jira.md`, `run.md`, `run-jira.md`. The run lane additionally gains the plan's existing guardrail and `## Out of scope` sections whether or not an intent is set, because it carries neither today. Nothing else."** Nothing on that list is reachable from this step, so this step changes zero behavior. The place that is tempting is the frontmatter question — `extract_plan_references` splits frontmatter first and this renderer does not, and "fixing" it while the code is already open would be a silent behavior change the fence does not allow.
- **"The guard is that intent travels, never that something checks it."** Do not add validation to the leaf. It reads sections and renders text; it judges nothing.
- **"No step ships a check comparing an intent against prose or against a diff."** Binds trivially here — the leaf gains no `intent` parameter at all in this step.

## Deferred

- **Rendering the plan and step intent into the fence** — step 4 owns it. This step's leaf renders exactly the four sections it renders today.
- **Wiring `renderer.py` so `run` and `run-jira` get the fence** — step 5 owns it. This step only makes that import possible.
- **Renaming `extract_plan_guardrails` to a fence-shaped name.** Leave it until the block actually carries both halves (steps 4–5), so this step stays a pure move with no call-site churn.
- **`PLAN_FORMAT.md`'s citation of `plan_tool/detail.py:extract_plan_guardrails`.** The re-export keeps that import path valid, and `PLAN_FORMAT.md` belongs to the carved follow-up seed — the citation update belongs in its doc sweep.
- **Retargeting `plan_tool/reprocess.py`'s import at the leaf.** Outside this step's declared files, and the re-export makes it unnecessary.
- **Consolidating the repo's other heading matchers** — `plan_tool/detail.py`'s detail-file `_H2_HEADING_RE` and `parse_detail_file_sections`, `plan_tool/jira_grade.py`'s H2 matcher, `plan_tool/reprocess.py`'s H2 walk. Four modules, three artifact types, one cross-module refactor a feature or refactor step cannot mint. Route it to `BACKLOG.md`.
- **Pointing `plan_tool/review.py:_BODY_PLACEHOLDER_RE` at the leaf's placeholder check.** Now technically possible, but `review.py` is not in this step's files. Route it to `BACKLOG.md`.
- **Whether the fence should split YAML frontmatter before matching headings.** A behavior question, not a move. It has no observed cost today (YAML indentation keeps a `##` off column 0), so route it to `BACKLOG.md` if it ever does.
