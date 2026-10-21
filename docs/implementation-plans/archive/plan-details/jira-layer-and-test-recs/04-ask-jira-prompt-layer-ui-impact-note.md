> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Ask the jira prompt for layer, UI-impact note, and frontend test recommendation

## Summary

Teach the whole-plan JIRA story prompt (`plan_tool/prompts/jira.md`) to emit three new per-story keys — `layer`, `ui_impact`, and `frontend_test_recommendation` — that step 1 added to `class Story` and step 2 taught the parser to read. The edit adds the three keys to the story-object shape near the top of the prompt and adds three rules under the existing `Rules:` list: the closed layer vocabulary (`frontend` / `backend` / `full_stack` / `infra`), when and how to write a UI-impact note (keeping the literal `none` distinct from an empty/absent answer), and what a frontend test recommendation is. The key decision: the prompt asks for the raw field *values*, never a title tag — the layer bracket (`[FE]` / `[BE]` / …) is a renderer decoration owned by step 3, so `title` stays clean, exactly as the prompt already forbids prepending the story id. On green, a Claude response carries the three keys, step 2's `parse_jira_response` reads them, and a legacy/pre-step-4 response that omits them still parses because the fields default.

## Table of Contents

- [Why](#why) — what the export prompt still can't ask for, and why closing it here
- [Input](#input) — the step-1 schema/vocabulary and step-2/3 contracts this prompt must match
- [Files (creates vs edits)](#files-creates-vs-edits) — the one prompt file this step touches
- [Implementation](#implementation) — the three new keys, the three new rules, and the constraints they must hold
- [Tests](#tests) — verification for a prompt-only change
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [References](#references) — prompt-shaping and Jira field docs that bear on this step
- [Deferred](#deferred) — the renderers, soft-lint, and docs owned by other steps

## Why

Steps 1–2 gave `class Story` the three fields and taught `parse_jira_response` to read and default them, but the prompt Claude actually answers never asks for them. Until the prompt requests `layer`, `ui_impact`, and `frontend_test_recommendation`, every real export sends stories that omit all three, and the parser dutifully defaults them to the sentinel — the fields exist end to end but are always empty. This step is the producer side: it makes the whole-plan JIRA call emit the values so the schema step 1 landed and the renderers step 3 wires actually carry real content. It also fixes the vocabulary Claude must use, so the values it returns match the closed set step 2 validates against instead of free-form guesses.

## Input

This step's prompt text must agree with contracts other steps own. Confirm the exact constant/field names at HEAD before writing (grep `_VALID_LAYERS` / `_LAYER_UNSPECIFIED` in `plan_tool/jira.py`) and use whatever shipped.

- **Step 1 — the field names and layer vocabulary.** The three keys are `layer`, `ui_impact`, `frontend_test_recommendation`. The four assignable layer values are `frontend` / `backend` / `full_stack` / `infra` (step 1's `_VALID_LAYERS`), with `unspecified` (`_LAYER_UNSPECIFIED`) as the sentinel kept out of that tuple. The prompt must ask for these exact string values.
- **Step 2 — tolerant defaulting.** `parse_jira_response` and both lint readers default a missing or out-of-vocabulary field to the sentinel instead of rejecting (`layer` → `_LAYER_UNSPECIFIED`, `ui_impact` → `""`, `frontend_test_recommendation` → `[]`). This is what lets the prompt change land without breaking any response written before it. Step 2 is not a declared dependency of this step (frontmatter is `depends_on: 1` only); it is independent and safe in either order, because the fields are additive and this prompt-only edit consumes no step-2 code. The prompt asks for the fields; it does not need to promise they are always present.
- **Step 2 — the `none` vs empty distinction on `ui_impact`.** The literal `none` is a real answer (a backend story saying "no visible UI change"); an empty string means "not answered". Step 5's soft-lint treats them differently. The prompt must make Claude emit `none` deliberately rather than leaving `ui_impact` blank when there genuinely is no UI change.
- **Step 3 — the layer tag is renderer-owned.** `format_markdown` prepends the layer bracket to the rendered title; the stored/JSON `title` stays clean. So the prompt must tell Claude **not** to put a layer tag in `title`, the same way it already forbids the story-id prefix.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/prompts/jira.md` — add `layer`, `ui_impact`, `frontend_test_recommendation` to the story-object JSON shape near the top; add three rules to the `Rules:` list describing each field's vocabulary, when to answer, and the keep-the-title-clean constraint.

## Implementation

**Add the three keys to the story-object shape.** In `plan_tool/prompts/jira.md`, the fenced example object under "Each story is one object of shape:" lists the current keys (`id`, `title`, `description`, `acceptance_criteria`, `files`, `steps`, `depends_on`, `estimate_hours`). Add the three new keys with short inline placeholders, e.g.:

- `"layer": "<frontend | backend | full_stack | infra>"`
- `"ui_impact": "<short note on downstream UI impact, or \"none\">"`
- `"frontend_test_recommendation": ["<how to test the UI-facing behavior>", ...]`

Place them after `estimate_hours` so the required, well-established fields stay first and the new metadata reads as an addition.

**Add three rules under `Rules:`.** Match the existing rule style (bold lead phrase, then guidance). Recommended shape:

- **`layer`** — one of the four values `frontend` / `backend` / `full_stack` / `infra`. Tell Claude to pick the layer the story's work lands in: UI-only → `frontend`, service/data/API-only → `backend`, both → `full_stack`, build/deploy/config/tooling → `infra`. State that it should choose the best fit from full plan context and only fall back to `unspecified` when the story genuinely spans no clear layer. Do **not** teach the bracket tags here — the values are the contract; the tag is added later by the renderer.
- **`ui_impact`** — a short note about user-visible impact. Instruct Claude to write the literal `none` when a story changes no user-visible behavior (typical for a `backend`/`infra` story), and a one-line note when a backend or full-stack change surfaces a downstream UI follow-up a reviewer should know about. Make the `none`-vs-blank distinction explicit: use `none` to say "checked, no UI change", not an empty string.
- **`frontend_test_recommendation`** — a list of short strings, each a concrete way to test the UI-facing behavior (component test, interaction/e2e check, visual/state assertion). Ask for it whenever the story touches the frontend (`frontend` or `full_stack`, or a `backend` story whose `ui_impact` flags real UI follow-up); an empty list is correct for a story with no frontend surface. Keep bullets short, one idea each — the same shape as `acceptance_criteria`.

**Keep the title clean of the layer tag.** Extend or sit beside the existing rule that forbids prepending the story id to `title`. Add one sentence: do not prepend a layer tag (`[FE]`, `[BE]`, …) to `title` either — the renderer adds it, so the markdown and JIRA share one canonical title. This is the main gotcha: without it, Claude may helpfully tag the title and step 3's renderer would double-tag it.

**Constraints that must hold:**

- **Use the field *values*, not the display tags.** The prompt asks for `frontend`/`backend`/`full_stack`/`infra`; the `[FE]`/`[BE]`/`[FE+BE]`/`[INFRA]` brackets are step-3 renderer output and must not appear in `layer` or `title`.
- **Additive, never a new hard requirement.** The prompt requests the fields but must not imply a response is invalid without them — step 2 defaults them, and older responses omit them. Don't add language that would make Claude refuse or the export fail when a field is absent.
- **`frontend_test_recommendation` stays a list.** Step 1 settled it as `list[str]`; the prompt's placeholder and rule must ask for a JSON array of strings, mirroring `acceptance_criteria`, not a single string.
- **Leave `render_jira_prompt` alone.** The new text is static prompt content, so it needs no new `${...}` substitution variable and no change to `plan_tool/jira.py:render_jira_prompt` or its `template.safe_substitute(...)` call. The four assignable values are a fixed vocabulary, not a runtime value — inline them in the template. (One way, if a later need arises to vary the vocabulary, is a new substitution variable — not needed now; avoid the extra seam.)
- **The clarification fallback and append mode need no new handling.** The "too vague to plan" single-story fallback and the append-mode / refresh-ticket sections already in the prompt can omit the new fields; they default cleanly. Don't thread the new keys into those branches.

**Foundational logic and where else it lives.** The core behavior is "the JIRA story schema the prompt advertises." That schema is single-sourced in this one prompt file — the parser (`plan_tool/jira.py:parse_jira_response`, step 2) and the renderers (`format_markdown` / `format_json`, step 3) each read/write the fields, but none of them re-declares the *prompt-facing* shape. So there is no duplicated prompt block to keep in sync here. The one cross-file agreement to respect is that the vocabulary strings in this prompt must match step 1's `_VALID_LAYERS` values; that agreement is verified by grepping the constant at HEAD, not by editing `jira.py` in this step.

## Tests

### Verification (non-code step)

This step changes only the prompt template `plan_tool/prompts/jira.md` — no production Python. Verify by inspection and by rendering, not unit tests of new code:

- `render_jira_prompt(...)` output contains `layer`, `ui_impact`, and `frontend_test_recommendation` — a quick render in a REPL (or an existing prompt-render test, if one asserts on prompt substrings) shows the three keys in the story-shape block.
- The four layer values in the prompt exactly match `plan_tool/jira.py:_VALID_LAYERS` at HEAD — grep the constant and compare the strings (no typo like `fullstack` vs `full_stack`).
- The existing JIRA parse/round-trip tests in `tests/test_jira.py` (the `parse_jira_response` cases and any prompt-render assertions) still pass unchanged — this edit adds nothing that could break parsing, since step 2 already reads the fields.
- Manual read-through confirms: `title` guidance forbids the layer tag; `ui_impact` guidance names the literal `none` and distinguishes it from blank; `frontend_test_recommendation` guidance asks for a list.

## Acceptance criteria

- `plan_tool/prompts/jira.md`'s story-object shape lists `layer`, `ui_impact`, and `frontend_test_recommendation` alongside the existing keys.
- The prompt's `Rules:` list names the four layer values `frontend` / `backend` / `full_stack` / `infra`, and those strings match `plan_tool/jira.py:_VALID_LAYERS`.
- The prompt instructs Claude to emit the literal `none` for a story with no user-visible UI change, distinct from leaving `ui_impact` empty.
- The prompt asks for `frontend_test_recommendation` as a JSON array of strings.
- The prompt tells Claude not to prepend a layer tag to `title` (in addition to the existing no-id-prefix rule).
- `render_jira_prompt(...)` renders without error and the rendered text contains the three new key names.
- `uv run pytest tests/test_jira.py -q` passes with no changes to `plan_tool/jira.py`.

## References

- [Tool use with Claude (Anthropic API docs)](https://docs.claude.com/en/docs/agents-and-tools/tool-use/overview) — how to shape the whole-plan prompt so Claude reliably returns the structured `layer` / `ui_impact` / `frontend_test_recommendation` fields in the JSON array.
- [Jira Cloud REST API v3 — Issues (Atlassian Developer)](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/) — Jira story/issue field semantics, useful when deciding how the layer and UI-impact metadata read to a tracker consumer.

## Deferred

- Reading/defaulting the three fields at the parse and lint sites — owned by step 2 (`parse_jira_response`, `_read_json_stories_for_lint`, `_read_markdown_stories_for_lint`); independent, and safe in either order because the fields are additive and this prompt-only edit consumes no step-2 code.
- Rendering the fields (the layer title tag, the `## Layer` / `## UI impact` / `## Testing recommendation` markdown sections, the JSON keys) — owned by step 3's `format_markdown` / `format_json`. This step only asks Claude for the values.
- The soft-lint checks that flag an empty `ui_impact` or a thin `frontend_test_recommendation` on a frontend-impacting story — owned by step 5's `jira --lint`.
- Any `render_jira_prompt` substitution-variable change — not needed; the vocabulary is fixed prompt text, not a runtime value.
- Docs describing the new export fields (JIRA_FORMAT.md and friends) — owned by the plan's later docs/status step, not this prompt edit.
