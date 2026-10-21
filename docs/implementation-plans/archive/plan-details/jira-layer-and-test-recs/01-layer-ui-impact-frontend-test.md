> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add `layer`, `ui_impact`, `frontend_test_recommendation` to `Story` plus layer-tag and frontend-impact helpers

## Summary

Add three defaulted fields to the `Story` dataclass in `plan_tool/jira.py` — `layer`, `ui_impact`, and `frontend_test_recommendation` — and two small pure helpers that later steps consume: a `layer_tag` function that maps a layer string to a short bracket tag (`[FE]` / `[BE]` / `[FE+BE]` / `[INFRA]`, empty for `unspecified`), and an `is_frontend_impacting` predicate that decides whether a story surfaces frontend work. All three fields default so a legacy `Story` still constructs and round-trips. This step only defines the schema and the helpers plus their unit tests; wiring them into the parser, renderers, prompt, and lint is left to steps 2–5. On green, a `Story` can be built with or without the new fields, the module's own `_normalize_story_references` copy preserves them, and both helpers return the right value for every layer value.

## Table of Contents

- [Why](#why) — what the export is missing today and why the schema comes first
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — the fields, the vocabulary constants, the two helpers, and the one in-module copy site to keep field-complete
- [Tests](#tests) — unit tests to add with the code and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [References](#references) — the stdlib docs that bear on this step
- [Deferred](#deferred) — the consumer wiring owned by later steps

## Why

The `Story` record in `plan_tool/jira.py` (`class Story`) is layer-agnostic — nothing says whether a story lands in the UI, the service, or both, and there's no place to carry a downstream-UI-impact note or a testing recommendation. The plan adds all of that, but every consumer (parser, both renderers, the prompt, `--lint`) needs a stable schema and stable helper contracts to build against. This step lands that foundation first: the three fields and the two deterministic helpers, each pinned by tests, so steps 2–5 wire real behavior onto a fixed shape instead of a moving target. Keeping it schema-only also keeps the risky part — back-compat — small and easy to prove: a `Story` built the old way still works.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/jira.py` — add three defaulted fields to `class Story`; add layer-vocabulary constants and the layer→tag map near the existing `_STORY_STATUS_*` / `_VALID_STORY_STATUSES` block; add the `layer_tag` and `is_frontend_impacting` helpers; thread the three new fields through the `Story(...)` copy inside `_normalize_story_references` so the module's own reconstruction stays field-complete.
  - `tests/test_jira.py` — add a test class covering the field defaults, the tag mapping for every layer value, the frontend-impact predicate, and the normalize round-trip.

## Implementation

**Add three defaulted fields to `class Story`.** Keep the dataclass `frozen=True`. Order the new fields after the existing `status` field:
- `layer: str` — defaults to a sentinel meaning "not provided". Recommend a module constant `_LAYER_UNSPECIFIED = "unspecified"` used as the default, mirroring how `status` defaults to `_STORY_STATUS_TODO`.
- `ui_impact: str = ""` — empty means "not provided"; the literal `none` (any case) is a real, meaningful value a backend story uses to say "no visible UI change". Do **not** collapse empty and `none` — later steps treat them differently (empty → soft-lint gap; `none` → answered).
- `frontend_test_recommendation: list[str]` — defaults to an empty list via `field(default_factory=list)`, matching `acceptance_criteria`.

**Settle the `frontend_test_recommendation` shape as `list[str]`** (the plan left `str` vs `list[str]` open). Reasons: it renders the same way `acceptance_criteria` does (one bullet per line), and the step-5 "missing / low-content" soft-lint reads naturally as "empty list or too few/too-short bullets". This is the design decision for the step — later steps build on `list[str]`.

**Define the layer vocabulary as string constants, not an `Enum`.** The plan frontmatter types `layer` as `str`, and the file's established pattern for a small closed set is module constants plus a validity tuple (`_STORY_STATUS_TODO` / `_STORY_STATUS_DONE` / `_VALID_STORY_STATUSES`). Follow it:
- One constant per value: `frontend`, `backend`, `full_stack`, `infra`, plus the `unspecified` sentinel.
- A `_VALID_LAYERS` tuple of the four real values (the sentinel is the default, not an assignable choice). Step 2's parser validates against this set.

**Add `layer_tag(layer: str) -> str`.** Deterministic, pure, no Claude:
- Map with a small dict: `frontend → "[FE]"`, `backend → "[BE]"`, `full_stack → "[FE+BE]"`, `infra → "[INFRA]"`.
- Return `""` for `unspecified` and for any unknown/empty value — an unknown layer must never crash or emit a stray tag.
- Return the **bare bracket** (e.g. `"[BE]"`), no surrounding spaces. Step 3 owns where the tag sits and its spacing (right after the `[<id>] ` title prefix). This differs on purpose from `plan_tool/style.py:change_type_tag`, which returns a leading-space form; here the caller composes `[<id>] [BE] <title>`, so keep spacing out of the helper.

**Add `is_frontend_impacting(story: Story) -> bool`.** This predicate is the shared rule steps 2, 3, and 5 all key on, so it lives in one place now:
- `True` when `story.layer` is `frontend` or `full_stack`.
- `True` when `story.layer` is `backend` **and** `story.ui_impact` is non-empty and not `none` — compare on `story.ui_impact.strip().lower()` not in `{"", "none"}`.
- `False` otherwise (including `infra` and `unspecified`).
- Read only `layer` and `ui_impact`; don't inspect `files` or prose.

**Keep the module's own `Story` copy field-complete.** `_normalize_story_references` rebuilds each story with an explicit `Story(...)` call listing every field. It currently lists nine fields and would silently reset the three new ones to their defaults. Add `layer=s.layer`, `ui_impact=s.ui_impact`, and `frontend_test_recommendation=list(s.frontend_test_recommendation)` to that construction (copy the list, don't alias it). This is in-scope because the fields must actually survive the module's own reconstruction to be "additive"; without it, step 2 (whose `parse_jira_response` ends by calling `_normalize_story_references`) would populate the fields and then lose them. The other `Story(...)` sites — the build in `parse_jira_response` and the two in the lint readers `_read_json_stories_for_lint` / `_read_markdown_stories_for_lint` — populate the fields from parsed input and belong to step 2; leave them here.

**Constraints that are not free to vary:**
- Every new field must be defaulted — an existing export and every existing `Story(...)` call site must keep working with no new argument.
- Empty `ui_impact` and the literal `none` stay distinct values.
- `layer_tag` and `is_frontend_impacting` are pure and deterministic — no invoker, no Claude, no disk.
- Unknown/unexpected layer strings degrade quietly (`layer_tag` → `""`, `is_frontend_impacting` → `False`), never raise.

## Tests

Add these to `tests/test_jira.py` (recommend a new class, e.g. `TestStoryLayerFields`), alongside the existing `TestFormatMarkdown` / `TestLintAcceptanceCriteria` classes. No real `claude` spawn — none of these reach an invoker.

### Test-creation order (feature step)

This is a **feature** step. Write these unit tests with the implementation; every one must be green before the step is done.

- `test_story_defaults_new_fields` — a `Story` built with only the pre-existing args has `layer == "unspecified"`, `ui_impact == ""`, and `frontend_test_recommendation == []`.
- `test_story_accepts_new_fields` — a `Story` built with `layer="backend"`, a `ui_impact` string, and a non-empty recommendation list keeps those values.
- `test_layer_tag_for_each_layer` — `layer_tag` returns `[FE]` / `[BE]` / `[FE+BE]` / `[INFRA]` for the four real values.
- `test_layer_tag_unspecified_and_unknown_empty` — `layer_tag("unspecified")` and `layer_tag("bogus")` and `layer_tag("")` all return `""`.
- `test_frontend_impacting_frontend_and_full_stack` — `is_frontend_impacting` is `True` for `layer="frontend"` and `layer="full_stack"` regardless of `ui_impact`.
- `test_frontend_impacting_backend_with_ui_impact` — `True` for `layer="backend"` with a real `ui_impact` note.
- `test_frontend_impacting_backend_none_or_empty` — `False` for `layer="backend"` when `ui_impact` is `""`, `"none"`, or `"None"`.
- `test_frontend_impacting_infra_and_unspecified` — `False` for `layer="infra"` and `layer="unspecified"`.
- `test_valid_layers_membership` — `_VALID_LAYERS` holds exactly the four real values and does not include the `unspecified` sentinel.
- `test_normalize_preserves_new_fields` — pass a story carrying `layer="backend"`, a `ui_impact` note, and a recommendation list through `_normalize_story_references` and assert all three survive on the returned story (the list is preserved, and is a copy — mutating the input list afterward doesn't change the output).

## Acceptance criteria

- `Story` has `layer`, `ui_impact`, and `frontend_test_recommendation`, all defaulted; `Story(id=..., title=..., description=...)` with no new args still constructs.
- Default values are `layer == "unspecified"`, `ui_impact == ""`, `frontend_test_recommendation == []`.
- `layer_tag` returns `[FE]`, `[BE]`, `[FE+BE]`, `[INFRA]` for the four real layers and `""` for `unspecified`, unknown, and empty input.
- `is_frontend_impacting` returns `True` for `frontend`/`full_stack`, `True` for `backend` with a non-empty non-`none` `ui_impact`, and `False` for `backend` with empty/`none` `ui_impact`, for `infra`, and for `unspecified`.
- `_normalize_story_references` preserves all three new fields (list copied, not aliased).
- The full `tests/test_jira.py` suite passes, including every pre-existing test — no regressions.

## References

- [dataclasses — Data Classes (Python Standard Library)](https://docs.python.org/3/library/dataclasses.html) — how to add defaulted fields (and a `field(default_factory=list)` for the recommendation list) to a `frozen=True` dataclass so old call sites keep working.

## Deferred

- **Validating `layer` against `_VALID_LAYERS` and defaulting invalid input** — owned by step 2 in `parse_jira_response` and both lint readers (`_read_json_stories_for_lint`, `_read_markdown_stories_for_lint`), which also populate the new fields from parsed input.
- **Rendering the fields and the title tag** — owned by step 3: `format_markdown` (title tag placement after the `[<id>] ` prefix, `## UI impact` / `## Testing recommendation` sections, `_(none)_` placeholder) and `format_json` (emit the keys, keep the JSON `title` clean).
- **Asking Claude for the fields** — owned by step 4 in `plan_tool/prompts/jira.md`.
- **The two new soft-lint checks** (missing UI-impact on backend/full-stack; missing/low-content test rec on frontend-impacting) — owned by step 5 in `lint_acceptance_criteria` and `plan_tool/cli/jira_cmd.py`; those checks call `is_frontend_impacting` defined here.
- **Docs** — `JIRA_FORMAT.md` schema/sample/validation/soft-lint rows and BACKLOG #104 reconciliation are step 6. The jira story JSON is not tracked in `DATA_CONTRACT.md` (that file defers the jira schema to `JIRA_FORMAT.md`), so no drift-guard change is needed here.
