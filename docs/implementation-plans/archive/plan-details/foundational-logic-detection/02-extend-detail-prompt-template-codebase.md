> **Auto-archived**: this plan was swept on 2026-06-11 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Teach detail's `## Codebase audit` to identify the step's foundational logic and surface shared call sites

## Summary

Add one bullet to the `## Codebase audit` list in `plan_tool/prompts/detail.md` directing claude to name the step's *foundational logic* (the core behavior/rule the step changes) and grep the rest of the app for other locations that exercise the same logic, then fold those locations into the existing detail-body sections (`## Implementation`, `## Files (creates vs edits)`, `## Deferred`). This is a pure prompt-string edit to the template Python `Template`-renders via `plan_tool/detail.py:render_detail_prompt` — no schema change, no parser change, no new required H2 in the produced detail file. The new guidance instructs claude to surface shared locations *inside the existing required structure*, never as a new heading. On green, `render_detail_prompt(...)` output contains the new foundational-logic guidance, the existing audit bullets (Grep/Read/already-implemented/Glob) and the seven required H2 headings stay byte-identical, and a new test class asserts the instruction's presence plus the no-new-heading invariant.

## Table of Contents

- [Why](#why) — what shared-logic blindness costs the detail phase today
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the exact audit-bullet edit and why it stays structure-free
- [Tests](#tests) — prompt-content assertions, no-new-heading negative, audit-bullets-unchanged
- [Acceptance criteria](#acceptance-criteria) — checkable prompt/test outcomes
- [References](#references) — the docs an implementer consults
- [Deferred](#deferred) — schema fields, detection mechanics, the create-side sibling, downstream phases

## Why

The `## Codebase audit` section in `plan_tool/prompts/detail.md` already tells claude to verify symbols with Grep, Read sibling files, confirm already-implemented hits, and Glob for test files — but nothing asks it to notice that the behavior *this step* changes also lives at *other* call sites in the app. When a step touches foundational logic (a validation predicate, a parse routine, a dispatch branch) that is duplicated or shared across modules, the detail body documents the one named file and silently omits its siblings; `run` then trusts the detail's footprint and ships a step that fixes one copy while the others drift. Step 1 owns adding this audit instinct to `create`'s step-proposal prompt (`plan_tool/create.py:_render_from_prompt`); this step extends the same instinct to `detail`, the next phase, so a shared-logic location missed at proposal time still gets surfaced when the per-step detail is authored — at the cheapest remaining point before implementation.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/prompts/detail.md` — append one bullet to the `## Codebase audit` bullet list, placed after the Glob bullet and before the `Do not narrate the audit in the response` sentence.
  - `tests/test_detail.py` — add a test class asserting the new instruction renders, the existing audit bullets are unperturbed, and no new H2 is advertised in the required structure.

## Implementation

### `plan_tool/prompts/detail.md` — `## Codebase audit` section

- **Append the foundational-logic bullet at the END of the audit bullet list**, immediately after the existing `- Use Glob to locate the matching test file(s)…` bullet and immediately before the `Do not narrate the audit in the response…` paragraph. Appending (not inserting mid-list) keeps the four existing bullets byte-identical so any substring assertion that pins them stays green; the audit list is unnumbered prose, so there is no renumber.
- **Bullet content — direct claude to:**
  - **Name the step's foundational logic** — the core behavior/rule this step adds or changes, stated in one phrase (e.g. a validation predicate, a parse routine, a dispatch branch).
  - **Grep the rest of the app for other locations that exercise the same logic** — duplicated blocks, parallel call sites, sibling modules implementing the same rule — reusing the Grep/Glob audit already mandated by the bullets above.
  - **Surface every shared location inside the existing detail-body sections** — cite them in `## Implementation` (if this step should also change them), in `## Files (creates vs edits)` (if they belong in this step's footprint), or in `## Deferred` (if intentionally left for another step, with the reason — including a shared location that needs **consolidating into a single source to prevent side effects** via a new refactor/consolidation step, which `detail` cannot mint, so route that find to `## Deferred`/reconcile rather than expanding the plan footprint). Use full repo-root-relative paths and symbolic anchors per the citation rules at the top of the template.
- **Do NOT advertise a new heading or section.** The produced detail file's required structure is fixed by the `## What to produce` block (Summary, Table of Contents, Why, Files, Implementation, Tests, Acceptance criteria, plus optional References/Deferred). The shared-location findings ride inside those existing sections — adding a `## Shared logic`-style heading would diverge the detail-file shape every downstream reader and the detail-quality review expect. The bullet must say findings go into existing sections.
- **No edit to `plan_tool/detail.py`.** `render_detail_prompt` reads the template verbatim via `Template(template_path.read_text(...))` and `.safe_substitute(...)`; the new bullet contains no `${...}` placeholder, so substitution is unaffected and no Python change is needed.

### `tests/test_detail.py` — new test class

- **Add `class TestRenderDetailPromptFoundationalLogic`** mirroring the existing `TestRenderDetailPrompt` setup: build a plan via the module-level `_write_detail_plan(tmp_path)` helper, `parse_plan`, pick a step, call `render_detail_prompt(plan, step, repo_root=tmp_path)`, and assert on the returned string.
- **Pin the new instruction by a stable substring** chosen from the bullet's wording (e.g. `"foundational logic"`), not by line position.
- **Assert the existing audit bullets and the structure list are unperturbed** so the append did not shift sibling content.

## Tests

Reference: `tests/test_detail.py`, new class `TestRenderDetailPromptFoundationalLogic`.

- `test_foundational_logic_instruction_present` — `render_detail_prompt(...)` output contains the foundational-logic audit guidance (substring `"foundational logic"`).
- `test_instruction_directs_grep_for_shared_locations` — output instructs grepping the app for other locations sharing the logic (substring on the shared-location wording).
- `test_existing_audit_bullets_unchanged` — output still contains the Grep, Read, already-implemented, and Glob audit bullets and the `Do not narrate the audit in the response` sentence, proving the append left them intact.
- `test_no_new_required_heading_advertised` — output advertises no produced-file H2 beyond the seven required headings; assert the `## What to produce` required-structure block is byte-unchanged (or, equivalently, that the advertised H2 set is exactly `## Summary`, `## Table of Contents`, `## Why`, `## Files (creates vs edits)`, `## Implementation`, `## Tests`, `## Acceptance criteria` plus the optional References/Deferred), so an alternately-named new heading cannot silently pass a literal `## Shared logic`-token check.

### Test-creation order (feature step)

This is a **feature** step — new prompt guidance. Author all four cases above in `tests/test_detail.py` alongside the `plan_tool/prompts/detail.md` edit. Green-before-done gate: every new test must pass (`uv run pytest tests/test_detail.py -q`) before this step is considered finished.

## Acceptance criteria

- `render_detail_prompt(plan, step, repo_root=...)` returns a string containing the foundational-logic audit instruction.
- The returned string still contains all four pre-existing audit bullets (Grep, Read, already-implemented, Glob) and the `Do not narrate the audit in the response` sentence.
- The foundational-logic instruction frames shared locations as candidates to be updated **or consolidated to prevent side effects**, routing a needed consolidation step to `## Deferred`/reconcile since `detail` cannot mint steps.
- The returned string advertises no new produced-file H2 beyond the existing required set; `## Shared logic` (or equivalent new heading) does not appear.
- No change to `plan_tool/detail.py`; `Template.safe_substitute` still renders the template, leaving any unmatched `${...}` placeholder untouched rather than raising.
- `uv run pytest tests/test_detail.py -q` passes, including the new `TestRenderDetailPromptFoundationalLogic` class.

## References

- [string — Template strings (Python Standard Library)](https://docs.python.org/3/library/string.html#template-strings) — Confirms `Template.substitute` treats the new prose bullet as literal text (no `${...}` placeholder added), so the template edit needs no Python change.

## Deferred

- New `Step`/`Plan` schema field for shared locations — out of scope; the findings ride inside existing detail-body sections, no frontmatter change. Needs a plan-level decision first.
- Programmatic duplicate-logic detection (AST/tokenize/tree-sitter from the plan-level references) — out of scope; this step adds prompt guidance only, leaving discovery to claude's Grep audit.
- The create-side sibling instruction — owned by Step 1 (`plan_tool/create.py:_render_from_prompt`); this step covers only the `detail` prompt.
- Downstream reconcile/run enforcement of surfaced shared locations — out of scope; this step surfaces them in the detail body, it does not gate on them.
