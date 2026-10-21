> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Surface the new fields in `format_markdown` and `format_json`

## Summary

Render the three step-1 `Story` fields — `layer`, `ui_impact`, `frontend_test_recommendation` — in both export renderers in `plan_tool/jira.py`. In `format_markdown` (`_render_story_block`), prepend the layer tag to the rendered title right after the `[<id>] ` prefix, and add three new sections — `## Layer`, `## UI impact`, `## Testing recommendation` — using the exact heading strings step 2's markdown reader already reads. In `format_json` (`_story_to_json_dict`), emit `layer`, `ui_impact`, and `frontend_test_recommendation` as new keys while keeping the JSON `title` clean (no layer tag). The key decision: the layer tag is a markdown display decoration only — it never touches the stored `Story.title` or the JSON `title`, so the JSON `title` round-trips unchanged. The markdown lint reader strips only the `[<id>] ` prefix, so it recovers the tag in the title (`[BE] <title>`) — harmless, since lint reads the id, acceptance criteria, and the new fields, not the title. On green, a rendered markdown block shows `[AUTH-S1] [BE] <title>` plus the three sections, the JSON carries the three new keys with a clean title, and a story with the default `unspecified` layer renders exactly as before (no tag, no double space).

## Table of Contents

- [Why](#why) — what the export still hides after steps 1–2 and why rendering closes the gap
- [Input](#input) — the step-1 helpers/fields and step-2 reader this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — the title tag, the three markdown sections, the JSON keys, and the round-trip constraints
- [Tests](#tests) — unit tests to add with the code and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [References](#references) — the in-file render pattern and step-1/step-2 anchors this step reuses
- [Deferred](#deferred) — the prompt, soft-lint, and docs wiring owned by later steps

## Why

Steps 1–2 gave `Story` the three fields and taught the parser and both lint readers to read and default them, but nothing writes them out yet. A story parsed from Claude (or read for lint) now carries a `layer`, a `ui_impact` note, and a `frontend_test_recommendation` list, and both renderers silently drop all three — the markdown block and the JSON object look exactly as they did before. A reviewer pasting the export into JIRA still can't see at a glance whether a story is frontend or backend work, whether a backend change surfaces a UI follow-up, or how to test a UI-facing story. This step makes the fields visible on the two surfaces a tracker actually consumes, on the fixed schema step 1 landed. It also completes the write side of the markdown contract step 2's reader already reads against, so the two halves agree.

## Input

This step consumes what steps 1 and 2 produced in `plan_tool/jira.py`. Confirm the exact names at HEAD (grep them) and use whatever shipped, in case they shifted during those steps.

- **Step 1 — the two helpers.** `layer_tag(layer)` maps a layer string to a bare bracket tag (`[FE]` / `[BE]` / `[FE+BE]` / `[INFRA]`) and returns `""` for `unspecified`/unknown/empty — no surrounding space, because the composing caller owns the spacing. `is_frontend_impacting(story)` decides whether a story surfaces frontend work. Read these; do not restate their logic or re-derive the tag mapping.
- **Step 1 — the three fields on `class Story`.** `layer: str` (default `_LAYER_UNSPECIFIED`), `ui_impact: str` (default `""`), `frontend_test_recommendation: list[str]` (default empty list). This step reads them off the story; it defines no schema.
- **Step 2 — the markdown reader.** `_read_markdown_stories_for_lint` reads `layer` from the `## Layer` section, `ui_impact` from `## UI impact`, and `frontend_test_recommendation` as the bullets under `## Testing recommendation` (via `_markdown_section` / `_markdown_bullets`), defaulting when a section is absent. **Those three heading strings are the write/read contract** — this step's `format_markdown` must emit those exact headings so the reader round-trips them. If this step needs a different heading, step 2's reader would have to change in the same commit; keep them aligned instead.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/jira.py` — in `_render_story_block`, compose the title with the layer tag after the `[<id>] ` prefix and add the `## Layer`, `## UI impact`, and `## Testing recommendation` sections; in `_story_to_json_dict`, add the `layer`, `ui_impact`, and `frontend_test_recommendation` keys (title stays clean).
  - `tests/test_jira.py` — add cases under `class TestFormatMarkdown` and `class TestFormatJson` covering the title tag per layer value, the three markdown sections and their placeholders, the clean JSON title, the three JSON keys, and a markdown round-trip through step 2's reader.

## Implementation

**Markdown title — insert the layer tag between the id prefix and the title.** In `_render_story_block`, the title line is built today as `f"[{story.id}] {story.title}"`. Change it to place `layer_tag(story.layer)` right after the `[<id>] ` prefix, so a tagged story renders `[AUTH-S1] [BE] <title>`. The one constraint that is not free to vary: **when the tag is empty (the `unspecified` default), the line must stay exactly `[<id>] <title>` with a single space** — no trailing or doubled space. A naive `f"[{story.id}] {tag} {story.title}"` produces `[AUTH-S1]  x` (two spaces) when `tag == ""` and breaks the existing `test_consolidated_story_renders` and `test_markdown_prepends_id_to_title` assertions. One clean way: build the pieces `[f"[{story.id}]", tag, story.title]`, drop the empty tag, and join with a single space. Keep the existing `[<id>] `-prefix behavior for the `unspecified` case identical to today.

**Markdown title is render-only.** Do not write the tag into `story.title` or anywhere the parser reads back — the tag is decoration, so the stored `Story.title` and the JSON `title` stay clean and the JSON `title` round-trips unchanged. Note the markdown lint reader (`_read_markdown_stories_for_lint`) strips only the `[<id>] ` prefix, so it recovers the tag in the title (`[BE] <title>`); this is harmless because lint reads the id, acceptance criteria, and the new fields, not the title.

**Markdown — add three sections after the existing per-story sections.** Follow the same `lines.append(...)` shape `_render_story_block` already uses for `## Acceptance criteria` / `## Files in scope`, with a blank line between sections. Use these exact headings (the step-2 contract) and the module's existing placeholder style:
- **`## Layer`** — render the layer value so it round-trips through the reader. One way: emit `story.layer` verbatim as the body (including `unspecified`), which the reader validates against `_VALID_LAYERS` and defaults back to `unspecified`. Either always-render or render-only-for-real-layers round-trips, since the reader defaults an absent or out-of-vocabulary `## Layer` section to `unspecified`; pick whichever reads cleaner and pin it with a test.
- **`## UI impact`** — render `story.ui_impact` verbatim when non-empty (this includes the literal `none`, a backend story's real "no UI change" answer), and the `_(none)_` placeholder when empty. **Keep empty and the literal `none` distinct** — render empty as `_(none)_` and the literal as the plain word `none`, so the two never collapse to the same text. See the round-trip note below.
- **`## Testing recommendation`** — render the section when `is_frontend_impacting(story)` is true: one `- <bullet>` per entry in `frontend_test_recommendation` (mirroring how `## Acceptance criteria` renders its list), or the `_(none specified)_` placeholder when the list is empty. A non-frontend-impacting story renders no such section. Gate on the step-1 predicate; do not re-derive "is this frontend work" inline.

**JSON — add three keys, keep the title clean.** In `_story_to_json_dict`, add `"layer": story.layer`, `"ui_impact": story.ui_impact`, and `"frontend_test_recommendation": list(story.frontend_test_recommendation)` (fresh list copy, matching the existing `list(story.acceptance_criteria)` style) alongside the current keys. **Leave the `title` key as `f"[{story.id}] {story.title}"` — no layer tag.** The layer is already its own structured key in JSON, so the tag would be redundant noise there; the acceptance criteria require the JSON title to stay clean. Emit all three keys unconditionally (the JSON object is structured data — no `is_frontend_impacting` gating), so consumers can rely on the shape.

**Round-trip note for empty `ui_impact` (a gotcha, not a blocker).** Step 2's markdown reader reads the `## UI impact` body verbatim (`_markdown_section(...).strip()`) and does not map the `_(none)_` placeholder back to `""`. So an empty `ui_impact` rendered as `_(none)_` reads back through the *markdown* reader as the string `"_(none)_"`, not `""`. This matches the existing behavior of the `_(no description)_` placeholder and is fine for display, but it means **JSON is the faithful surface for the empty-vs-`none` distinction** — `format_json` keeps empty `ui_impact` as `""`. The literal `none` and any real note round-trip cleanly on both surfaces. Do not "fix" this by editing the reader here — that is step 2's code and ownership; if a later step needs the markdown lint to tell an empty note from a real one, that belongs in step 5's soft-lint design (Deferred).

**Foundational logic and where else it lives.** The title composition — `[<id>]` prefix plus a render-time decoration plus the title — exists at two sites: `_render_story_block` (markdown, gets the layer tag) and `_story_to_json_dict` (JSON, stays clean). Both are in this step's scope; keep them in sync on the prefix but deliberately diverge on the tag. The `## <Heading>` section-render pattern this step follows already appears for `## Acceptance criteria`, `## Files in scope`, and `## Depends on` in `_render_story_block` — reuse that shape rather than inventing a new one. No other module renders jira stories, so there is no third render site to update.

## Tests

Add cases to `tests/test_jira.py` under `class TestFormatMarkdown` and `class TestFormatJson`. Build `Story(...)` fixtures directly with the new fields set — no Claude, no invoker. The markdown round-trip case exercises step 2's text-based reader `_read_markdown_stories_for_lint`, which the test module does not yet import (its jira import at `tests/test_jira.py:33` pulls in only the public `Path`-based `read_stories_for_lint`); add the `_read_markdown_stories_for_lint` import to feed `format_markdown`'s string output through it directly, or write the rendered export to `tmp_path` and round-trip via the already-imported `read_stories_for_lint`.

### Test-creation order (feature step)

This is a **feature** step — new rendering behavior. Write these unit tests alongside the code; every one must be green before the step is done (`enforce_step_tests: true`).

- `test_markdown_title_carries_layer_tag` — a `backend` story renders `[<id>] [BE] <title>`; a `full_stack` story renders `[FE+BE]`; a `frontend` story renders `[FE]`.
- `test_markdown_unspecified_layer_renders_no_tag` — a story with the default `unspecified` layer renders `[<id>] <title>` with a single space and no bracket tag (guards the existing no-regression assertions).
- `test_markdown_renders_layer_section` — the `## Layer` section shows the story's layer value.
- `test_markdown_ui_impact_section_placeholder_when_empty` — an empty `ui_impact` renders `## UI impact` with `_(none)_`.
- `test_markdown_ui_impact_literal_none_distinct_from_empty` — a story with `ui_impact == "none"` renders the plain word `none`, not the `_(none)_` placeholder.
- `test_markdown_testing_recommendation_bullets_for_frontend_story` — a frontend-impacting story with a non-empty `frontend_test_recommendation` renders one bullet per entry under `## Testing recommendation`.
- `test_markdown_testing_recommendation_absent_for_non_frontend_story` — a `backend` story with empty `ui_impact` renders no `## Testing recommendation` section.
- `test_markdown_testing_recommendation_placeholder_when_empty` — a frontend-impacting story with an empty list renders the `_(none specified)_` placeholder.
- `test_markdown_round_trips_new_fields_through_reader` — feed `format_markdown` output back through `_read_markdown_stories_for_lint` and recover `layer`, the bullet list, and a non-empty `ui_impact` unchanged.
- `test_json_emits_new_field_keys` — `_story_to_json_dict` output carries `layer`, `ui_impact`, and `frontend_test_recommendation` with the story's values.
- `test_json_title_stays_clean_of_layer_tag` — a `backend` story's JSON `title` is `[<id>] <title>` with no `[BE]` tag.
- `test_json_frontend_test_recommendation_is_list_copy` — the JSON list is a copy, not an alias of the story's list.

Green-before-done: `uv run pytest tests/test_jira.py -q` passes, including every pre-existing `TestFormatMarkdown` / `TestFormatJson` / `TestStoryTitlePrefix` case.

## Acceptance criteria

- `format_markdown` renders the layer tag right after the `[<id>] ` prefix: `[AUTH-S1] [BE] <title>` for `backend`, `[FE+BE]` for `full_stack`, `[FE]` for `frontend`, `[INFRA]` for `infra`, and no tag for `unspecified`.
- A story with the default `unspecified` layer renders `[<id>] <title>` with a single space — the existing `TestFormatMarkdown` and `TestStoryTitlePrefix` assertions still pass.
- `format_markdown` emits `## Layer`, `## UI impact`, and `## Testing recommendation` using those exact heading strings; the `## UI impact` body is `_(none)_` when empty and the plain word `none` when `ui_impact == "none"`.
- The `## Testing recommendation` section appears for a frontend-impacting story (via `is_frontend_impacting`) and is absent for a non-frontend-impacting story.
- `format_json` includes `layer`, `ui_impact`, and `frontend_test_recommendation` keys, and the JSON `title` is `[<id>] <title>` with no layer tag.
- Feeding `format_markdown` output back through `_read_markdown_stories_for_lint` recovers `layer`, the testing-recommendation list, and a non-empty `ui_impact` unchanged.
- All new tests pass and `uv run pytest tests/test_jira.py -q` is green.

## References

- `_render_story_block` in `plan_tool/jira.py` — the existing `## Acceptance criteria` / `## Files in scope` / `## Depends on` section-render pattern (`lines.append(...)` with a blank line between sections) that this step's three new sections reuse rather than reinventing.
- Step 1's `layer_tag` and `is_frontend_impacting` in `plan_tool/jira.py` — the tag mapping the markdown title composes and the predicate that gates the `## Testing recommendation` section; read them, don't re-derive.
- Step 2's `_read_markdown_stories_for_lint` in `plan_tool/jira.py` — the reader whose `## Layer` / `## UI impact` / `## Testing recommendation` heading strings are the write/read contract `format_markdown` must emit verbatim to round-trip.

## Deferred

- **Reading/validating the fields in the parser and lint readers** — step 2 owns `parse_jira_response`, `_read_json_stories_for_lint`, and `_read_markdown_stories_for_lint`; this step only writes.
- **Mapping the `_(none)_` markdown placeholder back to `""` in the reader** — not done here; JSON is the faithful surface for empty `ui_impact`. Any need to distinguish an empty note from a real one when linting a *markdown* export belongs to step 5's soft-lint design.
- **Asking the prompt for the fields** (`plan_tool/prompts/jira.md`) — step 4. Until it lands, Claude responses carry no new keys and the fields render at their defaults.
- **The two new soft-lint checks** (missing UI-impact on backend/full-stack; missing/low-content test rec on frontend-impacting) — step 5, which consumes these rendered fields plus step 1's `is_frontend_impacting`.
- **Updating `JIRA_FORMAT.md`** (schema table, markdown/JSON samples, validation and soft-lint rows) and reconciling `BACKLOG.md` #104 — step 6. The jira JSON is not tracked in `DATA_CONTRACT.md` (that file defers the jira schema to `JIRA_FORMAT.md`), so no drift guard changes here.
