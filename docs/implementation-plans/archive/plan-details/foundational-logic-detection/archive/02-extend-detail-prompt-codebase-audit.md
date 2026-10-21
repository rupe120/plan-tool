> **Auto-archived**: this plan was swept on 2026-06-11 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Teach detail's `## Codebase audit` to flag the step's foundational logic and its shared siblings

## Summary

Append one bullet to the `## Codebase audit (do this first)` list in `plan_tool/prompts/detail.md` directing claude to name the step's *foundational logic* (the core behavior/rule the step changes) and Grep the rest of the app for other locations that share it, then cite those siblings inside the existing body sections. This is a plain-text edit to one Markdown template — no `${...}` placeholder added, no change to `render_detail_prompt` in `plan_tool/detail.py`, and no change to the `## What to produce` required-structure contract. The mirror step for `create` is step 1 (`_render_from_prompt`); this step is its `detail`-side analog and carries no `depends_on`. On green, the rendered prompt (`render_detail_prompt(plan, step, repo_root=...)`) contains the new foundational-logic guidance, the four existing audit bullets stay byte-identical, the required-output H2 list is unchanged, and a new test class in `tests/test_detail.py` asserts the instruction's presence plus the no-new-section guard.

## Table of Contents

- [Why](#why) — what shared-logic blindness costs the detail phase today
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the exact audit-bullet edit and why it stays structure-free
- [Tests](#tests) — prompt-content assertions, no-new-section guard, placeholder guard
- [Acceptance criteria](#acceptance-criteria) — checkable prompt/test outcomes
- [References](#references) — the docs an implementer consults
- [Deferred](#deferred) — structural detection, precision tuning, downstream concerns left out

## Why

- **The detail audit verifies the step's own files but never asks about shared logic.** The `## Codebase audit (do this first)` list in `plan_tool/prompts/detail.md` tells claude to Grep for the symbols it will cite, Read sibling source files, confirm already-implemented hits, and Glob for test files — but nothing asks it to notice that the behavior this step changes also lives at *other* call sites the step's `files:` list never names.
- **A detail file that documents one copy of duplicated logic ships an incomplete footprint.** When the same validation/dispatch/path-resolution rule is duplicated across modules, a detail body scoped only to the declared `files:` describes fixing one copy and silently omits the siblings — exactly the project-root-path duplication class the plan's Problem statement cites, and the kind of omission `run` inherits because it trusts the detail body as the work description.
- **The audit phase is the cheapest place to surface siblings.** claude already has Grep/Read/Glob in hand during the audit; adding one instruction to scan for shared logic and cite the hits inside the existing `## Implementation` / `## Files` / `## Deferred` sections costs nothing structurally and catches the omission before it reaches `run` or reconcile.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/prompts/detail.md` — append one bullet to the `## Codebase audit (do this first)` list, after the existing Glob bullet and before the `Do not narrate the audit in the response` closing line.
  - `tests/test_detail.py` — add a test class asserting the new instruction renders, the required-output structure is unchanged, and no stray template placeholder is introduced.

## Implementation

### `plan_tool/prompts/detail.md` — `## Codebase audit (do this first)`

- **Append the new instruction as the LAST bullet of the audit list**, immediately after the `Use Glob to locate the matching test file(s)…` bullet and immediately before the `Do not narrate the audit in the response…` paragraph that closes the section. Appending (not inserting mid-list) keeps the four existing bullets byte-identical so the existing `TestRenderDetailPrompt` substring assertions stay green; the bullets are unnumbered prose, so there is no renumbering to do.
- **Instruction content (single bullet, plain imperative prose):** direct claude to —
  - **Name the step's foundational logic** — the core behavior or rule this step adds/changes (a validation predicate, a parsing routine, a dispatch branch, a path-resolution helper), stated in one phrase.
  - **Grep the rest of the app for other locations that exercise the same logic** — duplicated blocks, parallel call sites, sibling modules implementing the same rule — using the same Grep/Read/Glob audit the bullets above already mandate.
  - **Cite every shared location inside the existing body sections** — fold the siblings into `## Files (creates vs edits)`, `## Implementation`, or `## Deferred` as candidates for update or consolidation; frame them as review candidates, not mandatory edits (per the plan's false-positive Risk).
- **Do NOT add a new required output section.** The foundational-logic findings ride inside the body sections already listed in `## What to produce`. Leave the required-H2 structure block (`# Step … / ## Summary / ## Table of Contents / ## Why / ## Files / ## Implementation / ## Tests / ## Acceptance criteria / ## References / ## Deferred`) byte-unchanged — the detail-side analog of step 1's "no new JSON key" rule.
- **Introduce no `$` character.** `render_detail_prompt` renders this file through `string.Template(...).safe_substitute(...)` in `plan_tool/detail.py`. The audit section today contains no `${...}` placeholders; a bare `$` or an accidental `${word}` in the new bullet would be (mis)read as a template placeholder. Write the bullet with no `$` so it passes through `safe_substitute` verbatim.
- **No signature or call-site change.** `render_detail_prompt` reads the template via `prompts_dir() / "detail.md"` and substitutes the same keyword set; a text-only edit to the audit section needs no Python change. `render_detail_quality_prompt` reads a different template (`detail-quality.md`) and is untouched.

### `tests/test_detail.py`

- **Add a new test class** (e.g. `TestRenderDetailPromptFoundationalLogic`) beside the existing `TestRenderDetailPrompt` class, rendering via the established `render_detail_prompt(plan, step, repo_root=tmp_path)` pattern over the module's `_write_detail_plan(tmp_path)` fixture (mirroring `test_prompt_carries_references_instructions`). The class asserts the new guidance is present and the output contract is unchanged.

## Tests

Reference file: `tests/test_detail.py` (new class `TestRenderDetailPromptFoundationalLogic`, modeled on `TestRenderDetailPrompt::test_prompt_carries_references_instructions`).

- `test_audit_instructs_foundational_logic_scan` — rendered prompt contains the new guidance (assert on stable lowercased substrings, e.g. `"foundational logic"` and a shared-location phrase like `"share"`/`"shared"`); proves the bullet renders.
- `test_audit_instructs_surfacing_shared_locations` — rendered prompt directs folding siblings into existing sections (substring such as `"consolidat"` or a body-section reference); proves the instruction targets existing sections, not a new one.
- `test_no_new_required_output_section` — rendered prompt does NOT advertise a new required H2 named for foundational logic (assert `"## Foundational logic"` absent); the negative guard that a prose instruction did not silently become an output-structure change. Detail-side analog of step 1's `test_no_new_json_key_advertised`.
- `test_existing_audit_bullets_unchanged` — the four prior audit cues still render (`"Use Grep to find the public symbols"`, `"Use Read on sibling files"`, `"already-implemented signal"`, `"Use Glob to locate the matching test file"`); proves the append did not perturb existing bullets.
- `test_no_unsubstituted_placeholder_introduced` — `"${" not in prompt` after render; guards that the new bullet adds no stray `string.Template` placeholder (every real placeholder in `detail.md` is substituted, so a surviving `${` means the edit introduced one).

### Test-creation order (feature step)

This is a **feature** step — new prompt behavior. Author all five cases above **with** the `detail.md` edit. Green-before-done gate: every new test in `TestRenderDetailPromptFoundationalLogic` must pass, and the pre-existing `TestRenderDetailPrompt` suite must stay green (the append must not break any existing substring assertion), before this step is considered finished. Run `uv run pytest tests/test_detail.py -q` to verify.

## Acceptance criteria

- `render_detail_prompt(plan, step, repo_root=...)` output contains a foundational-logic-scan instruction inside the `## Codebase audit (do this first)` section.
- The instruction directs claude to Grep for other app locations sharing the step's foundational logic and to cite them inside the existing body sections (`## Files` / `## Implementation` / `## Deferred`).
- The `## What to produce` required-output H2 list is byte-unchanged — no new required section advertised.
- The four pre-existing audit bullets (Grep / Read / already-implemented / Glob) remain byte-identical.
- Rendered prompt contains no unsubstituted `${` placeholder.
- `uv run pytest tests/test_detail.py -q` passes, including the new `TestRenderDetailPromptFoundationalLogic` class and the unchanged `TestRenderDetailPrompt` class.

## References

- [string — Template strings (Python Standard Library)](https://docs.python.org/3/library/string.html#template-strings) — Why a literal `$` in the new bullet is unsafe: `render_detail_prompt` renders `detail.md` through `Template(...).safe_substitute(...)`, which treats `$`/`${...}` as placeholders.
- [ast — Abstract Syntax Trees (Python Standard Library)](https://docs.python.org/3/library/ast.html) — Background on programmatic foundational-logic identification; this step uses prompt-driven detection only (structural AST matching is Deferred).

## Deferred

- Structural (AST / tree-sitter / difflib) detection of shared logic — this step is a prompt-text edit only; mechanical duplicate-detection is the plan-level Deferred item and a separate effort.
- Precision tuning to reduce false positives — surfaced siblings are framed as review candidates, not mandatory edits, per the plan's Risks; tightening the match is out of scope.
- The `create`-side mirror (`_render_from_prompt` in `plan_tool/create.py`) — owned by step 1; this step changes only the `detail` audit prompt.
- The detail-quality review prompt (`plan_tool/prompts/detail-quality.md`, rendered by `render_detail_quality_prompt`) — not in this step's `files:`; whether the quality gate should check for surfaced siblings is a separate decision.
