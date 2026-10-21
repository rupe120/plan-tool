> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Read and default the new fields in parse_jira_response and both lint readers

## Summary

Populate the three step-1 fields — `layer`, `ui_impact`, `frontend_test_recommendation` — at the three `Story(...)` construction sites that build from external input in `plan_tool/jira.py`: the Claude-response parser `parse_jira_response`, and the two lint readers `_read_json_stories_for_lint` and `_read_markdown_stories_for_lint`. The key design decision is that these fields are **additive and never hard-reject** — a missing or invalid value defaults to the sentinel (`_LAYER_UNSPECIFIED` / `""` / `[]`) instead of failing the parse, unlike the existing hard-rejecting field checks. This keeps legacy exports and pre-step-4 Claude responses (which carry none of the new keys) parsing cleanly. On green, a JSON story with the new keys reads them through, a story without them defaults them, the literal `none` UI-impact stays distinct from empty, and the markdown reader reads them from their sections or defaults when absent.

## Table of Contents

- [Why](#why) — why the three input sites need to learn the fields now
- [Input](#input) — the step-1 schema and helpers this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — how each of the three readers reads, validates, and defaults the fields
- [Tests](#tests) — unit tests to add with the code and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [References](#references) — the in-file symbols and patterns this step reads/mirrors
- [Deferred](#deferred) — render, prompt, and lint wiring owned by later steps

## Why

Step 1 added `layer`, `ui_impact`, and `frontend_test_recommendation` to `class Story` and threaded them through the in-module copy in `_normalize_story_references`, but it deliberately left the three sites that build a `Story` from **external input** untouched — those belong here. Until this step, a Claude response carrying the new keys parses fine but drops them (the fields fall back to their defaults at the `Story(...)` build), and both lint readers do the same. Nothing downstream (the renderers in step 3, the soft-lint checks in step 5) can act on fields that never make it off the wire. This step wires the reading and defaulting so the fields survive from a JSON payload or a markdown export into the in-memory `Story`, on a fixed schema the later steps build against.

## Input

This step reads the schema and constants step 1 landed in `plan_tool/jira.py`:

- **The three fields on `class Story`** — step 1 produces `layer: str` (default `_LAYER_UNSPECIFIED`), `ui_impact: str` (default `""`), and `frontend_test_recommendation: list[str]` (default `field(default_factory=list)`). Do not restate their defaults here — read them from the dataclass.
- **The layer vocabulary** — step 1 produces the per-value constants plus the `_VALID_LAYERS` tuple (the four assignable values `frontend`/`backend`/`full_stack`/`infra`) and the `_LAYER_UNSPECIFIED` sentinel, which is kept **out** of `_VALID_LAYERS`. This step validates a read `layer` against `_VALID_LAYERS` and defaults to `_LAYER_UNSPECIFIED` otherwise.
- **What this step does NOT consume** — `layer_tag` and `is_frontend_impacting` are step-1 helpers for the renderers (step 3) and soft-lint (step 5). This step reads raw fields only; it does not tag titles or decide frontend-impact. Leave those helpers to their consumer steps.

Confirm the exact constant and field names at HEAD after step 1 lands (grep `_VALID_LAYERS` / `_LAYER_UNSPECIFIED` in `plan_tool/jira.py`) and use whatever shipped, in case the names shifted during step 1.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/jira.py` — read/validate/default the three fields at three `Story(...)` sites: `parse_jira_response` (the Claude-response parser), `_read_json_stories_for_lint`, and `_read_markdown_stories_for_lint`.
  - `tests/test_jira.py` — add cases under the parse and lint-reader test classes covering read-through, defaulting-when-absent, invalid-value defaulting, the empty-vs-`none` distinction, and the list handling for `frontend_test_recommendation`.

## Implementation

**The core rule: read tolerantly, default on anything missing or invalid — never hard-reject on the new fields.** The existing field checks in `parse_jira_response` (id shape, `steps`, `depends_on`, `estimate_hours`) return `None` on violation. The three new fields must **not** join that set. A response or export that predates step 4's prompt change carries none of the keys, so hard-rejecting would break back-compat and drop otherwise-valid stories. Missing → default; wrong type or out-of-vocabulary → default. This tolerant stance is the main decision; the rejected alternative is mirroring the existing hard-reject validators, which would fail every legacy payload.

**`parse_jira_response` (the `Story(...)` build near the end of the loop, before the cross-story `depends_on` check).** Read the three keys off `item` and pass them into the `Story(...)` call:
- `layer` — read `item.get("layer")`; if it is a string in `_VALID_LAYERS`, use it; otherwise use `_LAYER_UNSPECIFIED`. No reject on an unknown string (e.g. `"middleware"` → `unspecified`).
- `ui_impact` — read `item.get("ui_impact")`; keep it verbatim if it is a string, else `""`. **Do not collapse `""` and `"none"`** — the literal `none` (any case) is a real answer a backend story uses; step 5's soft-lint treats empty and `none` differently. One way: `ui_impact = raw if isinstance(raw, str) else ""`.
- `frontend_test_recommendation` — read `item.get("frontend_test_recommendation")`; if it is a list, keep only its string members (`[x for x in raw if isinstance(x, str)]`); else `[]`. Do **not** mirror this function's `acceptance_criteria` check — that one hard-rejects a non-string member (`return None`), which would violate the "never hard-reject on the new fields" rule above; the tolerant keep-only-strings filter you want is the one in `_read_json_stories_for_lint`.
- The fields flow through the trailing `_normalize_story_references(stories, epic)` call unchanged — step 1 already made that copy field-complete, so no extra work is needed for them to survive the round-trip.

**`_read_json_stories_for_lint`.** This reader is already tolerant (it coerces bad types rather than rejecting), so match its style: read the three keys with the same validate-or-default logic as above, and thread them into its `Story(...)` call. Reuse the `layer ∈ _VALID_LAYERS` check and the same empty-vs-`none` rule.

**`_read_markdown_stories_for_lint`.** Read the three fields from their markdown sections using the existing `_markdown_section` and `_markdown_bullets` helpers, defaulting when a section is absent (legacy exports and any export written before step 3's renderer lands have no such sections):
- `layer` — `_markdown_section(block, "Layer").strip()`, validated against `_VALID_LAYERS`, else `_LAYER_UNSPECIFIED`.
- `ui_impact` — `_markdown_section(block, "UI impact").strip()`; an empty section → `""`.
- `frontend_test_recommendation` — `_markdown_bullets(_markdown_section(block, "Testing recommendation"))` (renders as bullets like `acceptance_criteria`), else `[]`.
- Thread all three into its `Story(...)` call.

**Cross-step contract with step 3 (render owner).** The exact markdown heading text (`## Layer`, `## UI impact`, `## Testing recommendation`) and the empty-vs-`none` placeholder that `format_markdown` writes are step 3's to settle. Use the heading names above as the agreed contract; if step 3's renderer diverges (e.g. folds `layer` into the story header banner instead of a `## Layer` section, or picks a distinct empty placeholder for `ui_impact`), that reader must be updated to match in the same change. Because this reader defaults tolerantly on an absent section, it stays correct against a legacy export regardless.

**Constraints that are not free to vary:**
- **Three sites, not four.** Only `parse_jira_response`, `_read_json_stories_for_lint`, and `_read_markdown_stories_for_lint` change here. The fourth `Story(...)` site, `_normalize_story_references`, is step 1's and is already field-complete — do not touch it.
- **No hard-reject on the new fields** in `parse_jira_response`. The existing rejects stay; the new fields only default.
- **Keep `""` and `"none"` distinct** for `ui_impact` at every site.
- **Copy the list, don't alias it** — build `frontend_test_recommendation` as a fresh `list[...]` (matching how `acceptance_criteria=list(acceptance)` is built), so no shared mutable state leaks between the parsed input and the `Story`.

## Tests

Add cases to `tests/test_jira.py`. Use **literal fixtures** (JSON dicts/strings and hand-written markdown blocks) so these tests depend only on step 1's schema, not on step 3's renderers. Existing parse tests live under `class TestParseJiraResponse` / `class TestParseJiraResponseHardened`; lint-reader tests under `class TestReadStoriesForLint`.

### Test-creation order (feature step)

This is a **feature** step. Write these unit tests alongside the code; every one must be green before the step is done (the plan sets `enforce_step_tests: true`).

- `test_parse_reads_new_fields` — a JSON story with `layer`/`ui_impact`/`frontend_test_recommendation` keys yields a `Story` carrying those exact values.
- `test_parse_defaults_missing_new_fields` — a JSON story with none of the new keys parses (not `None`) and defaults to `unspecified` / `""` / `[]`.
- `test_parse_invalid_layer_defaults_not_rejected` — an out-of-vocabulary `layer` (e.g. `"middleware"`) defaults to `unspecified` and does **not** reject the response.
- `test_parse_ui_impact_none_kept_distinct_from_empty` — a story with `ui_impact: "none"` keeps the literal `none`; a story omitting the key gets `""`.
- `test_parse_frontend_test_recommendation_list_filtered` — a list with non-string members keeps only the strings; a non-list value defaults to `[]`.
- `test_parse_new_fields_survive_normalize` — the values set in `parse_jira_response` are still present after the trailing `_normalize_story_references` call.
- `test_parse_legacy_payload_still_parses` — an existing new-field-free payload (e.g. the current `_consolidated_payload`) still parses unchanged (no regression).
- `test_json_lint_reader_reads_new_fields` — `_read_json_stories_for_lint` reads the three fields from a literal JSON story.
- `test_json_lint_reader_defaults_and_tolerates_bad_types` — missing keys and wrong-typed values default rather than raise.
- `test_markdown_lint_reader_reads_new_field_sections` — a hand-written markdown block with `## Layer` / `## UI impact` / `## Testing recommendation` sections yields a `Story` with those values.
- `test_markdown_lint_reader_defaults_when_sections_absent` — a markdown block without those sections defaults the three fields.

## Acceptance criteria

- `parse_jira_response` returns a `Story` whose `layer`, `ui_impact`, and `frontend_test_recommendation` match a JSON payload that supplies them.
- A JSON payload omitting the new keys parses to a non-`None` result with `layer == _LAYER_UNSPECIFIED`, `ui_impact == ""`, `frontend_test_recommendation == []`.
- An unknown `layer` string defaults to `unspecified` and does not cause `parse_jira_response` to return `None`.
- `ui_impact == "none"` is preserved verbatim and is not equal to the empty-default `""`.
- `_read_json_stories_for_lint` and `_read_markdown_stories_for_lint` each populate the three fields (from keys / sections) or default them, and the existing acceptance-criteria lint tests in `class TestReadStoriesForLint` still pass.
- All new tests in `tests/test_jira.py` pass; `uv run pytest tests/test_jira.py -q` is green.

## References

- `plan_tool/jira.py` — step 1's `_VALID_LAYERS` (the four assignable layer values) and the `_LAYER_UNSPECIFIED` sentinel kept out of it: the validate-against-`_VALID_LAYERS`-else-default-to-`_LAYER_UNSPECIFIED` contract every reader here applies. Grep both at HEAD after step 1 lands in case the names shifted.
- `plan_tool/jira.py` — the `acceptance_criteria=list(acceptance)` build in `parse_jira_response`: the fresh-`list` copy pattern to mirror for `frontend_test_recommendation` (copy, don't alias); its non-string-member hard-reject is the anti-pattern to avoid here (keep only string members instead).
- `plan_tool/jira.py` — `_read_json_stories_for_lint`'s coerce-or-default posture: the tolerant style the JSON reader matches for the three new fields.
- `plan_tool/jira.py` — the `_markdown_section` and `_markdown_bullets` helpers: the extractors `_read_markdown_stories_for_lint` uses to read the `Layer` / `UI impact` / `Testing recommendation` sections and default when a section is absent.

## Deferred

- **Rendering the new fields** (`format_markdown` / `format_json`) — step 3 owns the write side, including the exact markdown heading text and the empty-vs-`none` placeholder this step's markdown reader agrees with.
- **Round-trip tests through `format_markdown`/`format_json`** — deferred to step 3; those need the renderers to emit the new keys/sections, so step 2 tests use literal fixtures instead.
- **Asking the prompt for the fields** (`plan_tool/prompts/jira.md`) — step 4. Until it lands, a real Claude response carries no new keys, which is exactly the defaulting path this step handles.
- **The two new soft-lint checks** (missing UI-impact on backend/full-stack; missing/low-content test rec on frontend-impacting) — step 5, which consumes the fields this step reads plus step 1's `is_frontend_impacting`.
- **Updating `_normalize_story_references`** — step 1 already made that copy field-complete; not touched here.
