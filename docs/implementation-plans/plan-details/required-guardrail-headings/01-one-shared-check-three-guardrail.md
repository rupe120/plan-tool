# Step 1 — One shared check for the three required guardrail headings

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds a constant naming the three required guardrail headings and a pure function to `plan_tool/scope_fence.py`. Given a seed's text, the function returns every required heading that is missing, duplicated, empty or a placeholder. It applies the rule `classify_file_backed_source` uses for `## References`: exactly one fence-safe H2, a non-empty body, and `_is_placeholder_section` false. `GUARDRAIL_BODY_SECTIONS`, `_is_placeholder_section` and `_SECTION_PLACEHOLDER_RE` stay unchanged, so a body of `None` counts as content. When this step is green, the create intake and the roadmap draft gate can call one function. `tests/test_scope_fence.py` gains cases for each offence, for multiple offenders, for `None` passing, and for `render_scope_fence` carrying a `None` body verbatim.

## Table of Contents

- [Why](#why) — why a shared check is needed
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — approach, key decisions and constraints
- [Tests](#tests) — cases in `tests/test_scope_fence.py`
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — code and docs to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left to other steps

## Why

Both the `create --from-existing` intake and the roadmap draft gate must refuse a seed with a bad guardrail heading. The plan's step intent requires that the two refusals agree on what a guardrail heading needs. Today only `## References` has a presence rule, inline in `plan_tool/create.py:classify_file_backed_source`. The three guardrail headings have none, and no function exists that both callers could share. `plan_tool/scope_fence.py` is a stdlib-only leaf that already owns `extract_h2_section_occurrences`, `_is_placeholder_section` and `render_scope_fence`, so the check belongs there. Callers in later steps import it without adding any dependency edge.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/scope_fence.py`:
    - add one constant holding the three headings in order: `## Scope guardrails`, `## Audit guardrails`, `## Expected placement`
    - add one pure function over seed text
  - `tests/test_scope_fence.py`: add one new test class for the check, plus the `render_scope_fence` carry-through case. Extend the existing `from plan_tool.scope_fence import (...)` block with the two new names.

## Implementation

- **Constant.**
  - Name it something like `REQUIRED_GUARDRAIL_HEADINGS`, a tuple of the three headings in the order `GUARDRAIL_BODY_SECTIONS` already uses.
  - Leave `GUARDRAIL_BODY_SECTIONS` alone. It also carries `Stack`, which is not required, and `render_scope_fence` and `extract_plan_guardrails` depend on its order.
  - Store the title without the `## ` prefix (for example `Scope guardrails`), because `extract_h2_section_occurrences` returns lowercased titles and callers want a short list to put in an error message. Choose one form and keep it consistent between the constant and the return value.
- **Function.**
  - Name it something like `missing_required_guardrail_headings(text: str) -> tuple[str, ...]`.
  - It returns the offending headings in constant order, and an empty tuple means the seed passes.
  - It reports every offender in one call, not the first. An operator with two bad headings should see both in one refusal.
  - One way to build it, following `classify_file_backed_source`:
    - Take `_strip_frontmatter(text)`.
    - Call `_fenced_code_spans(...)` once.
    - Call `extract_h2_section_occurrences(stripped, strip_fenced_code=True, fenced_spans=scan.spans)`.
    - For each required title, look up `occurrences.get(title.lower(), [])`.
    - Flag the heading unless there is exactly one occurrence, its body is non-empty, and `_is_placeholder_section(body)` is false.
  - Use the existing scanner. Do not write a second fence recognizer.
- **No raising, no I/O.**
  - The function must not call `reject_unmatched_create_fence`. That check is create-specific and lives in `plan_tool/create.py`, which this leaf cannot import.
  - An unclosed fence already spans to the end of the text in `_fenced_code_spans`, so a heading inside it counts as missing.
  - The function writes and deletes nothing.
- **`None` passes.**
  - `_SECTION_PLACEHOLDER_RE` matches only `_(TODO)_`, `TODO` and `(TODO)`.
  - `None`, `N/A` and `none` are therefore content. Leave the regex and `_is_placeholder_section` unchanged.
  - Do not add `None` or `N/A` to the pattern. The plan's scope guardrails forbid it, and the existing comment already warns against widening this vocabulary.
- **Smallest proof.**
  - Use a fixed check over three constants, with no rule engine and no configurable heading list.
  - Do not judge, compare or cap guardrail content. The check covers presence only.
- **Shared sites found by searching the same rule (`_is_placeholder_section` plus `extract_h2_section_occurrences`).**
  - `plan_tool/create.py:classify_file_backed_source` applies the rule to `## References` and to `_BODY_SECTIONS_CANONICAL_KEYS`. It stays as it is, because those checks are not about the guardrail headings.
  - `plan_tool/create.py:validate_from_existing_seed` and the roadmap draft gate are the consumers of the new function. They are separate steps (see Deferred).
  - Consolidating the inline `## References` rule into this function would change `create.py`'s behavior. It is outside this step.

## Tests

All cases go in `tests/test_scope_fence.py`, in a new class (for example `TestMissingRequiredGuardrailHeadings`). Build seed text with a small local helper that emits the three headings with bodies, so each case changes one thing.

- `test_complete_seed_reports_nothing` — a seed with all three headings and real bodies returns an empty tuple.
- `test_missing_heading_is_reported` — a seed without `## Audit guardrails` returns that heading only.
- `test_duplicated_heading_is_reported` — two `## Scope guardrails` sections return that heading, even when both bodies are non-empty.
- `test_empty_body_is_reported` — a heading directly followed by the next H2 is reported.
- `test_todo_placeholder_body_is_reported` — a body of `_(TODO)_` is reported.
- `test_heading_inside_fenced_code_does_not_count` — a heading that appears only inside a fenced block is reported as missing, so a quoted example cannot satisfy the rule.
- `test_seed_missing_two_headings_reports_both_in_constant_order` — dropping two headings returns both together, in constant order.
- `test_none_body_passes_the_presence_check` — a body of exactly `None` is accepted. This is deliberate: the plan wants an explicit `None` to be a valid answer.
- `test_none_na_and_lowercase_none_are_outside_the_placeholder_pattern` — `_is_placeholder_section` returns false for `None`, `N/A` and `none`. This pins the carve-out so nobody widens `_SECTION_PLACEHOLDER_RE` and breaks the explicit-`None` rule.
- `test_render_scope_fence_carries_a_none_guardrail_body_verbatim` — a plan whose `## Audit guardrails` body is `None` renders `## Audit guardrails` followed by `None`. Put it beside the existing `TestRenderScopeFence` cases (or in the new class). It proves a `None` body survives into the prompt.
- `test_check_is_pure_and_does_not_write` — the call leaves a `tmp_path` seed file's bytes unchanged, and the function takes text, not a path.

### Tests for this step

The tests above are the full roster. Every one must be green before this step is finished. Run `uv run pytest tests/test_scope_fence.py -q`, then `uv run pytest -m "not integration" tests/ -q -n auto` to check that `tests/test_duplication.py` and the leaf-import tests (`TestLeafImportDiscipline`) still pass. After writing the tests, break the function once (for example, treat a duplicate as acceptable) and confirm the matching case goes red.

## Acceptance criteria

- `missing_required_guardrail_headings` returns an empty tuple for a seed that has all three headings, each once, outside fenced code, with a non-empty body that is not a `_(TODO)_`-style placeholder.
- It returns every offending heading, in constant order, for a missing, duplicated, empty or placeholder heading.
- A body of `None` passes, and `_is_placeholder_section("None")`, `("N/A")` and `("none")` are all false.
- `render_scope_fence` output contains a `None` guardrail body verbatim.
- `_SECTION_PLACEHOLDER_RE`, `_is_placeholder_section` and `GUARDRAIL_BODY_SECTIONS` are unchanged. `git diff` shows only additions to `plan_tool/scope_fence.py`.
- `plan_tool/scope_fence.py` still imports no first-party module, and `TestLeafImportDiscipline` passes.
- The function performs no file writes and no deletions.
- The new tests pass, and the full suite passes with no change to any existing test.

## References

- BACKLOG #532 — the source entry for this plan.
- `plan_tool/create.py` (`classify_file_backed_source`) — the `## References` rule this step reuses.
- `plan_tool/scope_fence.py` (`GUARDRAIL_BODY_SECTIONS`, `_is_placeholder_section`, `render_scope_fence`, `extract_h2_section_occurrences`) — the leaf this step extends.
- `SEED_FORMAT.md` — the seed shape these headings belong to.

## Applicable guardrails

- The plan's "## Scope guardrails", presence-only rule: this step checks only that each of the three headings is present. It must not judge, compare or cap what a guardrail says.
- The plan's "## Scope guardrails", `None` must pass: this step must leave the placeholder pattern unchanged, so an explicit `None` stays valid.
- The plan's "## Scope guardrails", required set: this step must not require `## Stack`, `## Outcome` or `## In scope`.
- The plan's "## Out of scope": no code in this step touches inline `--from`, `--from-plan`, archived seeds, or any model call.

## Deferred

- Calling the new check from `plan_tool/create.py:validate_from_existing_seed` and from the roadmap draft gate — the plan's later steps own the refusals.
- Updating seed-writing tools (`plan_tool/roadmap.py:materialize_plan_seed`, `plan_tool/annotate_render.py:render_create_seed`, `plan_tool/scope_out.py`, `plan_tool/reground.py`) to emit the headings — separate steps.
- Moving the inline `## References` rule into a shared function — it would change `create.py` behavior outside this step.
- Docs updates (`SEED_FORMAT.md`, `PLAN_FORMAT.md`, `docs/how-to/pipeline/create-from-existing.md`) — the plan's docs step owns them.
