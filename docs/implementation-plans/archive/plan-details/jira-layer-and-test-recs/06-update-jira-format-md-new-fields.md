> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Document the layer/UI-impact/test-rec fields in `JIRA_FORMAT.md` and retire BACKLOG #104

## Summary

Bring `JIRA_FORMAT.md` up to date with the three new `Story` fields — `layer`, `ui_impact`, `frontend_test_recommendation` — that steps 1–5 land in `plan_tool/jira.py`, its renderers, its prompt, and `jira --lint`, then reconcile `BACKLOG.md` #104. In `JIRA_FORMAT.md` this means three new rows in the "Story schema" table, the layer tag shown on the rendered markdown title, three new `##` sections in the markdown sample, three new keys in the JSON sample, a note that the new fields default (never reject) so back-compat holds, and two new rows under "Soft lints" for the `lint_layer_metadata` checks. In `BACKLOG.md` this means removing the shipped #104 entry and its mention in the T5 roll-up. This is a docs-and-backlog step — no production code changes. On green, the doc matches what the code writes at HEAD, and a grep for `#104` in `BACKLOG.md` returns nothing outside archived copies.

## Table of Contents

- [Why](#why) — what the doc and backlog still say that the code no longer matches
- [Input](#input) — the shipped fields, renderers, and lint this step documents
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — the doc edits and the backlog reconcile, with the verify-before-retire gate
- [Tests](#tests) — verification for a non-code step
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [References](#references) — the JIRA field docs that bear on this step
- [Deferred](#deferred) — what this step does not touch

## Why

`JIRA_FORMAT.md` is the human- and agent-facing reference for the jira story export. Its own top banner says the code wins and the doc must be fixed when they disagree. After steps 1–5 ship, the code writes a `layer`, a `ui_impact` note, and a `frontend_test_recommendation` on every story, renders a `[FE]`/`[BE]`/`[FE+BE]`/`[INFRA]` tag on the markdown title, emits three new markdown sections and three new JSON keys, and runs two new soft-lint checks — none of which the doc describes. A reviewer reading `JIRA_FORMAT.md` today would not know these fields exist or what values are valid. Separately, `BACKLOG.md` #104 is the entry this whole plan came from; the seed requires the plan to reconcile that entry when the work ships. This step closes both gaps: it makes the doc match the shipped code and retires the backlog item so the file stops advertising work that is done.

## Input

This step documents what steps 1–5 landed in `plan_tool/jira.py`, `plan_tool/prompts/jira.md`, and `plan_tool/cli/jira_cmd.py`. Confirm the exact names at HEAD before writing (grep them) and use whatever shipped, in case they shifted during those steps.

- **Step 1 — the three fields and the layer vocabulary.** `layer: str` (default the `unspecified` sentinel, `_LAYER_UNSPECIFIED`), `ui_impact: str` (default `""`), `frontend_test_recommendation: list[str]` (default empty list). The four assignable layer values are `frontend` / `backend` / `full_stack` / `infra` (`_VALID_LAYERS`), with `unspecified` kept out of that tuple. The bare title tag is `[FE]` / `[BE]` / `[FE+BE]` / `[INFRA]`, empty for `unspecified` (`layer_tag`).
- **Step 3 — the two render surfaces.** `format_markdown` prepends the tag to the title after the `[<id>] ` prefix and adds three sections whose exact headings are `## Layer`, `## UI impact`, `## Testing recommendation`. `format_json` emits `layer`, `ui_impact`, `frontend_test_recommendation` as keys and keeps the JSON `title` clean (no tag). Document the heading strings and JSON keys exactly as step 3 renders them — the doc's samples are the human-facing contract for those strings.
- **Step 2 — additive defaulting.** The parser and both lint readers default a missing or out-of-vocabulary field instead of rejecting, so legacy exports still parse. The literal `none` `ui_impact` stays distinct from empty. The doc's validation section must say the new fields default (never reject), not add them to the reject list.
- **Step 5 — the two soft-lint checks.** `lint_layer_metadata` flags a `backend`/`full_stack` story with an empty `ui_impact`, and a frontend-impacting story with an empty or too-thin `frontend_test_recommendation`. Both are advisory (soft-lint), wired into the `--lint` display and the export soft-warn, never the hard gate.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `JIRA_FORMAT.md` — add three rows to the "Story schema" table; note the layer tag on the `title` row; add the tag and three `##` sections to the markdown sample; add three keys to the JSON sample; add a line to the validation section saying the new fields default rather than reject; add two rows under "Soft lints" naming `lint_layer_metadata`.
  - `BACKLOG.md` — remove the #104 entry (heading through the `- **Origin:**` line) and drop `#104` from the T5 export-leg roll-up line.

## Implementation

**Verify the shipped symbols before retiring #104 — this is a gate, not a formality.** Grep `plan_tool/jira.py` for `layer`, `ui_impact`, `frontend_test_recommendation`, `_VALID_LAYERS`, `layer_tag`, and `lint_layer_metadata`, and `plan_tool/prompts/jira.md` for the three keys. If any are missing at HEAD, the depended-on code steps did not land — **stop and route back to the owning step (2/3/4/5)**. Do not patch `plan_tool/jira.py` or any code from this docs step; a docs step that edits code has no convergence loop and expands its footprint past its declared files. This mirrors the rule for retiring a tracked entry: removing #104 asserts the feature shipped, so confirm it did.

**Update `JIRA_FORMAT.md` to match the code — the doc's job is to describe the shipped shape, not to re-specify it.** Keep the edits tight to what steps 1–5 produce:

- **Story schema table** — add three rows after the existing `status` row:
  - `layer` · `string` · one of `frontend` / `backend` / `full_stack` / `infra`; defaults to `unspecified` when absent.
  - `ui_impact` · `string` · downstream-UI-impact note on backend/full-stack stories; `none` is a real answer, empty means not provided.
  - `frontend_test_recommendation` · `list[string]` · advisory what/how-to-test bullets for frontend-impacting stories; alongside `acceptance_criteria`, not a replacement.
- **`title` row note** — say the rendered markdown title carries the layer tag after the `[<id>] ` prefix (`[<KEY>-S1] [BE] <title>`), and that the tag is a markdown display decoration only — the stored `Story.title` and the JSON `title` stay clean.
- **Markdown sample** (the fenced block under "## Markdown format") — show the tag on the `## Title` line and add the three new sections in the order step 3 renders them. One way, matching step 3's headings exactly:
  ```
  ## Layer
  backend                        (or _(unspecified)_)

  ## UI impact
  <note, or `none`, or _(not provided)_>

  ## Testing recommendation
  - <bullet>                     (or _(none)_)
  ```
  Confirm the exact empty-state placeholder strings against `format_markdown` at HEAD and match them — the doc should not invent placeholder text the renderer doesn't emit.
- **JSON sample** (the fenced block under "## JSON format") — add `"layer"`, `"ui_impact"`, and `"frontend_test_recommendation"` keys to the story object, with the JSON `title` shown clean (no tag).
- **Validation rules** — add one line stating the three new fields are **additive and default on missing/invalid** (`unspecified` / `""` / `[]`), so they never reject a response and legacy exports still parse. Do not add them to the numbered hard-reject list — that would misdescribe the code.
- **Soft lints** — add two bullets under the existing list, attributing them to `lint_layer_metadata()`:
  - a `backend`/`full_stack` story with an empty `ui_impact`, and
  - a frontend-impacting story with an empty or too-thin `frontend_test_recommendation`.
  Note both are warnings, not rejections, like the acceptance-criteria lints.

**Reconcile `BACKLOG.md` #104.** Remove the entire `**#104 — Jira story export: …**` entry (its heading through the trailing `- **Origin:**` line, which sits just below the `Plan-tool commands` fenced command block) and drop `**#104**` from the T5 export-leg roll-up line so the entry leaves no dangling reference. Grep the whole file for `104` after editing and confirm the only remaining hits are unrelated numbers. **Leave the archived copies untouched** — `#104` in `plan-seeds/archive/` and the plan/detail files under `docs/implementation-plans/` are historical artifacts outside this reconcile's scope, and the plan's own detail files legitimately cite #104 as their source.

## Tests

### Verification (non-code step)

This step changes no production code — verification is doc accuracy and backlog cleanup, not unit tests. Run these checks:

- `grep -n "104" BACKLOG.md` — after the edit, no hit refers to the retired #104 entry or the T5 roll-up (only unrelated numbers, if any, remain).
- `grep -n "layer\|ui_impact\|frontend_test_recommendation" JIRA_FORMAT.md` — the schema table, both format samples, and the soft-lint section all mention the fields.
- Cross-check the three markdown heading strings (`## Layer`, `## UI impact`, `## Testing recommendation`) and the three JSON keys in `JIRA_FORMAT.md` against `format_markdown` / `format_json` in `plan_tool/jira.py` at HEAD — they match character-for-character.
- Cross-check the layer vocabulary in the doc against `_VALID_LAYERS` in `plan_tool/jira.py` at HEAD.
- `uv run pytest -m "not integration" tests/test_jira.py -q` — the existing jira suite still passes unchanged (this step touches no code, so nothing should move; run only as a sanity confirmation).

## Acceptance criteria

- `JIRA_FORMAT.md` "Story schema" table has rows for `layer`, `ui_impact`, and `frontend_test_recommendation` with the types and defaults above.
- The `JIRA_FORMAT.md` markdown sample shows the layer tag on the title (`[<KEY>-S1] [BE] …`) and the three sections `## Layer`, `## UI impact`, `## Testing recommendation`.
- The `JIRA_FORMAT.md` JSON sample includes the three new keys with a clean `title`.
- The `JIRA_FORMAT.md` validation section states the new fields default (never reject), and the "Soft lints" section names `lint_layer_metadata` with its two checks.
- The layer values and markdown heading strings in the doc match `_VALID_LAYERS` and `format_markdown` in `plan_tool/jira.py` at HEAD.
- `grep "104" BACKLOG.md` returns no reference to the retired entry or the T5 roll-up mention; the archived copies under `plan-seeds/archive/` and `docs/implementation-plans/` are untouched.

## References

- `plan_tool/jira.py` — `Story`, `format_markdown`, `format_json`, `lint_layer_metadata`, `_VALID_LAYERS`: the shipped symbols whose field names, heading strings, JSON keys, and layer vocabulary this doc step must match character-for-character.
- `JIRA_FORMAT.md` "code is source of truth" banner — the doc must be fixed to match the code when they disagree, which is exactly this step's job.

## Deferred

- `DATA_CONTRACT.md` and the jira JSON drift guard — the exported jira story JSON is **not** tracked in `DATA_CONTRACT.md` (grep confirms no `jira` entry there), so there is no persisted-shape doc or drift guard to update; the plan's "if drift-tracked" clause resolves to nothing here.
- Any change to `plan_tool/jira.py`, `plan_tool/prompts/jira.md`, or `plan_tool/cli/jira_cmd.py` — the schema, parser, renderers, prompt, and lint are owned by steps 1–5; this step only documents what they shipped and does not modify code.
- Marking #104 as plan-authored-but-pending — not applicable; all #104 work ships in this plan, so the entry is removed outright, not carried forward.
