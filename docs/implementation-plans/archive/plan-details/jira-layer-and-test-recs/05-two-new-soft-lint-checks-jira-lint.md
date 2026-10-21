> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add the two new soft-lint checks to `jira --lint`

## Summary

Add two new soft-lint checks to the jira export: a story tagged `backend` or `full_stack` that leaves `ui_impact` empty, and a frontend-impacting story whose `frontend_test_recommendation` is empty or too thin. The key decision: put these in a **new** producer function in `plan_tool/jira.py` (e.g. `lint_layer_metadata`), separate from `lint_acceptance_criteria`, and wire it only into the **soft** display paths (`cmd_jira_lint` in `plan_tool/cli/jira_cmd.py`, and the export soft-warn `_emit_story_warnings`) — never into the export hard gate `_raise_for_acceptance_criteria_lint`. Keeping them out of the hard gate is what makes them advisory in v1, matching the plan's deferral of a `--fail-on-findings` hard-block. On green, `jira --lint` reports these two gaps (added to the existing warning count) without a Claude call, an export that trips them still writes, and a story with a complete layer, a real (or `none`) UI-impact note, and a substantive test recommendation produces no new warning.

## Table of Contents

- [Why](#why) — what `--lint` can't flag today and why a separate producer
- [Input](#input) — the step-1/step-2 fields and helpers this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source + two test files
- [Implementation](#implementation) — the new producer, the two checks, and the soft-only wiring
- [Tests](#tests) — unit tests to add with the code and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer can run
- [References](#references) — the stdlib/API docs that bear on this step
- [Deferred](#deferred) — the hard-block, docs, and prompt work owned elsewhere

## Why

Steps 1–4 gave every story a `layer`, a `ui_impact` note, and a `frontend_test_recommendation` list, taught the parser and both lint readers to read them, made both renderers surface them, and made the prompt ask Claude for them. But nothing checks whether Claude actually filled them in. A backend story can ship with no UI-impact answer at all (the exact cross-layer coupling this plan set out to surface), and a frontend-impacting story can ship with an empty or one-word test recommendation (the under-testing on-ramp gap). `jira --lint` already flags weak acceptance criteria without a backend call; this step extends that no-Claude check so a reviewer can catch these two layer-metadata gaps in an existing export before pasting it into a tracker.

## Input

This step reads what steps 1 and 2 landed in `plan_tool/jira.py`. Confirm the exact names at HEAD before writing (grep them) and use whatever shipped, in case they shifted during those steps.

- **The `is_frontend_impacting(story)` predicate** — step 1 produces the shared rule this step's second check keys on. It returns `True` for `layer` `frontend`/`full_stack`, `True` for `backend` with a non-empty non-`none` `ui_impact`, and `False` otherwise (including `infra`/`unspecified`). Call it; do not re-derive the rule here.
- **The layer vocabulary constants** — step 1 produces one constant per value plus the `_VALID_LAYERS` tuple. This step's first check needs the `backend` and `full_stack` values (grep `_VALID_LAYERS` / the per-value constants such as `_LAYER_BACKEND` / `_LAYER_FULL_STACK`); use the real constants rather than bare string literals.
- **The three fields on `class Story`** — `layer: str`, `ui_impact: str`, `frontend_test_recommendation: list[str]`. This step reads them off the story; it defines no schema.
- **The `none` vs empty distinction on `ui_impact`** — step 2 keeps the literal `none` (a backend story saying "no visible UI change") distinct from `""` at every read site. This step's first check treats them differently: empty → warn; `none` → no warn. `is_frontend_impacting` already encodes the same distinction, so the two checks agree.
- **The lint readers** — step 2 taught `read_stories_for_lint` / `_read_json_stories_for_lint` / `_read_markdown_stories_for_lint` to populate the three fields from a JSON or markdown export. This step's CLI test feeds stories through that reader, so the new fields survive from disk into the linted `Story`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/jira.py` — add the new producer `lint_layer_metadata(stories: list[Story]) -> list[str]` near `lint_acceptance_criteria`; inline the two warning messages in `lint_layer_metadata` and add the `_TEST_REC_MIN_SUBSTANTIVE_CHARS` floor constant near the existing `_VAGUE_AC_PATTERNS` block; call it from `_emit_story_warnings` (soft display) after the existing `lint_acceptance_criteria` loop.
  - `plan_tool/cli/jira_cmd.py` — import the new producer from `plan_tool.jira`; in `cmd_jira_lint`, aggregate its findings with `lint_acceptance_criteria`'s so the display loop and the found/passed counts include both.
  - `tests/test_jira.py` — add a test class for the new producer covering each check firing and not firing.
  - `tests/cli/test_jira_cmds.py` — add cases under `TestCmdJiraLint` proving `jira --lint` surfaces the new findings end-to-end through a JSON input fixture.

## Implementation

**The foundational logic: produce per-story soft-lint findings for missing layer-derived fields, and keep them advisory.** The core rule this step adds is two deterministic per-story checks that return human-readable warning strings. The existing sibling that does the same job for acceptance criteria is `plan_tool/jira.py:lint_acceptance_criteria`. That function's output feeds three call sites — grep confirms them: the export **hard gate** `_raise_for_acceptance_criteria_lint` (raises `JiraError` before writing on any finding), the export **soft display** `_emit_story_warnings` (informational, never rejects), and the **`--lint` display** in `cmd_jira_lint`. The key decision below turns on that split.

**Add a new producer `lint_layer_metadata`, don't fold into `lint_acceptance_criteria`.** The two new checks must stay advisory (the plan defers a `--fail-on-findings` hard-block). If they joined `lint_acceptance_criteria`, they would flow through `_raise_for_acceptance_criteria_lint` and **hard-block the export** — a new export with `layer=backend` and an empty `ui_impact` would fail to write. That contradicts "soft-lint, not failure". A separate producer keeps the AC hard gate reserved for the crisp structural rules it already enforces and confines the new checks to the soft paths. (Step 1's Deferred note pointed at `lint_acceptance_criteria` as the likely home; the separate function is the same intent — the two new checks land in `plan_tool/jira.py` and wire into `--lint` — but split out so they never reach the hard gate.)

**Give it the same shape as its sibling** so aggregation is trivial:
- Signature `lint_layer_metadata(stories: list[Story]) -> list[str]`, returning `style.warn()` bodies (no `warning:` prefix), exactly like `lint_acceptance_criteria`.
- At most **one warning per check per story** — mirror the sibling's per-category convention so many stories with the same gap don't drown the reviewer.

**Check 1 — missing UI-impact on a backend/full-stack story:**
- Fire when `story.layer` is `backend` or `full_stack` **and** `story.ui_impact.strip() == ""`.
- The literal `none` (any case) is a real answer, not a gap, and does **not** fire — the empty-string fire condition already excludes it (a non-empty `none` never satisfies `strip() == ""`), so no separate `none` check is needed here.
- Do not fire for `frontend`, `infra`, or `unspecified` layers.
- Message: name the story id and say the backend/full-stack story is missing a UI-impact note; point the author at answering it (with `none` a valid answer when the change is UI-invisible).

**Check 2 — missing or thin test recommendation on a frontend-impacting story:**
- Fire when `is_frontend_impacting(story)` is `True` **and** the recommendation is empty or low-content.
- **Empty** — `frontend_test_recommendation` has no bullets, or every bullet is blank after `strip()`.
- **Low-content** — the recommendation exists but is too thin to act on. One way: treat a bullet as substantive only when it clears a small character floor (recommend ~20 non-space characters across the recommendation, or no single bullet reaching ~12 chars); fire when no bullet is substantive. The floor is yours to tune — pin the observable behavior in tests, not the exact number: a stub like `["test it"]` fires, a concrete multi-clause recommendation does not.
- Message: name the story id and say the frontend-impacting story lacks a usable test recommendation; point the author at naming the flow/component and a test level.

**How the two checks compose** (worth confirming, since a story can be both backend and frontend-impacting):
- backend + empty `ui_impact` → check 1 fires; `is_frontend_impacting` is `False`, so check 2 does not. One warning.
- backend + `ui_impact="none"` → neither fires. Zero warnings.
- backend + real `ui_impact` + empty rec → check 1 does not fire; `is_frontend_impacting` is `True`, check 2 fires. One warning.
- full_stack + empty `ui_impact` + empty rec → both fire (two distinct gaps). Two warnings — correct.
- frontend + empty rec → only check 2 fires.
- infra / unspecified → neither fires.

**Wiring — soft paths only:**
- `plan_tool/jira.py:_emit_story_warnings` — add a loop `for body in lint_layer_metadata(stories): warn(body)` right after the existing `lint_acceptance_criteria` loop. This is the export soft-warn path (informational, shared by fresh and append export). Leave `_raise_for_acceptance_criteria_lint` untouched — the new checks must never reach it.
- `plan_tool/cli/jira_cmd.py:cmd_jira_lint` — import `partition_lint_findings` alongside `read_stories_for_lint` (the import block already pulls these from `plan_tool.jira`) and consume its `(blocking, advisory)` split (`blocking, advisory_findings = partition_lint_findings(stories)`) rather than concatenating `lint_acceptance_criteria` and `lint_layer_metadata` inline. The existing display loop, the found/passed counts, and the return codes then cover both with no other change.

**Constraints that are not free to vary:**
- The two new checks stay **out** of `_raise_for_acceptance_criteria_lint` — they never flip the export from writing to raising.
- Empty `ui_impact` and the literal `none` stay distinct at check 1 — `none` is an answered gap, empty is not.
- Check 2 calls `is_frontend_impacting` (step 1) rather than re-implementing the frontend-impacting rule, so the predicate stays single-sourced.
- The producer is pure and deterministic — no invoker, no Claude, no disk. `jira --lint` must keep working with no backend call and no epic assignment.
- The new import in `cmd_jira_lint` must be a module-level `from plan_tool.jira import ...` name (the module already imports its jira symbols this way); do not reach through an `app` alias.

- **Single-source the severity split through `partition_lint_findings`.** `plan_tool/jira.py:partition_lint_findings(stories) -> (blocking, advisory)` returns the acceptance-criteria findings as `blocking` and the `lint_layer_metadata` findings as `advisory`, so the export gate and `--lint` cannot drift on which lint class is soft vs hard — a new lint class picks a side there, not in the CLI handler. `cmd_jira_lint` consumes it (`blocking, advisory_findings = partition_lint_findings(stories)`) rather than concatenating the two producers inline.

## Tests

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write these unit tests **with** the implementation; every new test must be green before the step is done. Keep the Claude seams stubbed — none of these reach an invoker, so no real `claude` spawn. The `_story` helper in `tests/test_jira.py` (and `_lint_story` in `tests/cli/test_jira_cmds.py`) build a `Story` without the new fields today; extend them to accept `layer` / `ui_impact` / `frontend_test_recommendation`, or build `Story(...)` directly in the new tests.

Add to `tests/test_jira.py` (recommend a new class, e.g. `TestLintLayerMetadata`, beside `TestLintAcceptanceCriteria`):
- `test_backend_missing_ui_impact_warns` — a `backend` story with `ui_impact=""` yields exactly one finding naming the story id and the UI-impact gap.
- `test_full_stack_missing_ui_impact_warns` — same for `full_stack`.
- `test_backend_ui_impact_none_no_warning` — a `backend` story with `ui_impact="none"` (and `"None"`) yields no UI-impact finding.
- `test_backend_ui_impact_present_no_warning` — a `backend` story with a real `ui_impact` note yields no UI-impact finding.
- `test_frontend_infra_unspecified_no_ui_impact_check` — `frontend`, `infra`, and `unspecified` layers never trip check 1.
- `test_frontend_impacting_empty_test_rec_warns` — a `frontend` story with an empty recommendation list yields one test-rec finding.
- `test_backend_with_ui_impact_empty_test_rec_warns` — a `backend` story with a real `ui_impact` and an empty rec yields one test-rec finding (frontend-impacting via `is_frontend_impacting`).
- `test_low_content_test_rec_warns` — a frontend-impacting story with a stub rec like `["test it"]` yields a test-rec finding.
- `test_substantive_test_rec_no_warning` — a frontend-impacting story with a concrete multi-clause recommendation yields no test-rec finding.
- `test_non_frontend_impacting_test_rec_not_checked` — a `backend` story with `ui_impact="none"` and an empty rec yields no test-rec finding (not frontend-impacting).
- `test_full_stack_empty_both_yields_two_findings` — a `full_stack` story with empty `ui_impact` and empty rec yields two findings.
- `test_one_warning_per_check_per_story` — a story that trips a check only once regardless of how many bullets share the problem.

Add to `tests/cli/test_jira_cmds.py` under `TestCmdJiraLint`:
- `test_lint_flags_missing_ui_impact_from_json` — write a JSON export with a `backend` story and empty `ui_impact` (clean acceptance criteria), run `main(["jira", "--lint", "--input", <path>])`, assert `rc == 0` and the UI-impact wording appears on stderr as an advisory warning.
- `test_lint_flags_missing_test_rec_from_json` — write a JSON export with a frontend-impacting story and empty recommendation (clean acceptance criteria), assert `rc == 0` and the test-rec wording appears as an advisory warning.
- `test_lint_passes_complete_layer_metadata` — write a JSON export whose stories carry complete layer metadata (real or `none` UI-impact, substantive rec, clean acceptance criteria), assert `rc == 0` and the "passed" line prints.

Use JSON `--input` fixtures for the CLI tests: step 5 depends on steps 1 and 2 (the reader), **not** step 3 (the markdown renderer). A JSON fixture round-trips the new fields through step 2's `_read_json_stories_for_lint` without depending on `format_markdown`. Hand-authored markdown with `## Layer` / `## UI impact` / `## Testing recommendation` sections is a valid alternative, but do not render fixtures through `format_markdown` here.

Green gate: every new test above passes, and the full `tests/test_jira.py` and `tests/cli/test_jira_cmds.py` suites stay green with no regressions.

## Acceptance criteria

- `lint_layer_metadata([backend story, ui_impact=""])` returns exactly one finding; `lint_layer_metadata([backend story, ui_impact="none"])` returns none.
- `lint_layer_metadata([frontend-impacting story, frontend_test_recommendation=[]])` returns one finding; a story with a substantive recommendation returns none.
- A `full_stack` story with both `ui_impact=""` and an empty recommendation returns two findings.
- `jira --lint` exits `0`, printing the UI-impact and/or test-rec text as advisory layer-metadata warnings, and exits `1` only on acceptance-criteria findings.
- `export_jira` still writes an export whose stories trip the new checks (they are not in `_raise_for_acceptance_criteria_lint`); the AC hard gate is unchanged.
- No test in this step spawns a real `claude` process (the conftest backend gate stays satisfied).
- The full `tests/test_jira.py` and `tests/cli/test_jira_cmds.py` suites pass.

## References

- `plan_tool/jira.py:lint_acceptance_criteria` — the sibling producer to copy in shape: `(stories) -> list[str]` returning `style.warn()` bodies, one warning per category per story. `lint_layer_metadata` mirrors it.
- `plan_tool/jira.py:_emit_story_warnings` and `_raise_for_acceptance_criteria_lint` — the two export-side consumers of the sibling. Wire the new producer into the **soft** `_emit_story_warnings` loop only; the hard gate `_raise_for_acceptance_criteria_lint` must stay untouched so the new checks stay advisory.
- `plan_tool/jira.py:partition_lint_findings` — the single-source severity split `(stories) -> (blocking, advisory)` (blocking = acceptance-criteria findings, advisory = `lint_layer_metadata` findings) that keeps the export gate and `--lint` from drifting on which lint class is soft vs hard; a new lint class picks a side here, not in the CLI handler.
- `plan_tool/cli/jira_cmd.py:cmd_jira_lint` — the `--lint` display path; consume `partition_lint_findings`'s `(blocking, advisory)` split so the display loop and found/passed counts cover both without concatenating the producers inline.
- `plan_tool/jira.py:is_frontend_impacting` and the `_VALID_LAYERS` / per-layer constants (from step 1) — the shared frontend-impacting predicate check 2 calls and the `backend`/`full_stack` layer values check 1 keys on; reuse them rather than re-deriving the rule or using bare string literals.
- `plan_tool/jira.py:_VAGUE_AC_PATTERNS` — the existing low-content pattern block near which the new warning-message constants land; reference for the pattern-vs-length-floor choice in check 2.
- [re — Regular expression operations (Python Standard Library)](https://docs.python.org/3/library/re.html) — stdlib reference only if you choose a pattern-based low-content check over a character floor.

## Deferred

- **A `--fail-on-findings` hard-block on the two new checks** — kept advisory in v1; flipping severity so these gate the exit code is a later change, and they deliberately stay out of `_raise_for_acceptance_criteria_lint`.
- **Rendering, parsing, and prompting for the fields** — owned by steps 2 (readers), 3 (`format_markdown` / `format_json`), and 4 (`plan_tool/prompts/jira.md`); this step only reads the already-populated fields.
- **`JIRA_FORMAT.md` soft-lint rows and BACKLOG #104 reconciliation** — owned by step 6.
- **Deterministic layer inference from `files:` paths** — a separate deferred capability in the plan; this step lints what Claude assigned, it does not infer layers.
