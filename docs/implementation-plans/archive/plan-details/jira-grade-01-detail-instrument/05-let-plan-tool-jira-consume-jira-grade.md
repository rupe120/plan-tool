> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Let `plan-tool jira` consume jira-grade detail directly: `--grade` option, selected path map threaded through export, and pre-backend hard failure with contract re-validation

## Summary

Give `plan-tool jira` an opt-in `--grade jira` mode that grounds the story export on the jira-grade detail bundle instead of the run-grade `Step.detail` files: `plan_tool/jira.py:export_jira` builds its `step_detail_map` from the jira-grade path derivation step 3 adds to step 1's leaf, threads that selected map through the prompt (`render_jira_prompt`), both formatters (`format_markdown` / `format_json`), and append-mode freshness (`_ticket_needs_detail_refresh`), and hard-fails before any backend call when a step's jira-grade artifact is missing or fails step 3's required-H2 contract on read. The key design decision: validation runs up front over every **non-`done`** step, per the plan's one bundle-coverage rule — a missing artifact is never papered over by the run-grade file, and a run-grade body at a jira-grade path is rejected with the validator's wrong-schema message, so no hidden fallback can mask which contract the export consumed. The default path (`--grade run`, or no flag) is unchanged in every way. On green, `plan-tool jira <name> --grade jira` exports stories whose prompt grounding and detail links all point at `jira/` artifacts, and approx. 13 new tests pass across `tests/test_jira.py` and `tests/cli/test_jira_cmds.py`.

## Table of Contents

- [Summary](#summary) — what the mode ships and the one design decision
- [Why](#why) — why the export must consume the jira-grade bundle directly, with a loud failure mode
- [Input](#input) — the step 1 / step 3 contracts this step consumes, and what can't be verified at HEAD
- [Files (creates vs edits)](#files-creates-vs-edits) — per-file edits; no new files
- [Implementation](#implementation) — the grade selector, the selected-map threading, the validation gate, and the flag-surface sweep
- [Tests](#tests) — export-seam and CLI-routing cases, with the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the plan-level references relevant to this step
- [Deferred](#deferred) — consumers and lifecycle gaps owned by later steps

## Why

The plan's whole point is that `jira` consumes the compact jira-grade schema directly — no down-conversion from run-grade prose — and the plan's `artifact-ambiguity` blocker (HIGH, recurring across three audit snapshots) is specifically about consumers that validate only path existence. At HEAD, `export_jira` reads exactly one detail source: `step_detail_map = {s.id: s.detail for s in plan.steps if s.detail}`, and the prompt side (`_render_step_detail`) reads `step.detail` directly, tolerating absence with a soft `_(no detail file)_` placeholder. That soft-fallback shape is right for the legacy default but wrong for an explicit grade selection: an export that silently grounds on the run-grade body (or on nothing) misreports which contract it consumed — the operator asked for jira-grade stories and got run-grade prose, with nothing red. That is the plan's no-hidden-fallback rule, and it stands on its own; this plan compares nothing (see its Out of scope). Step 4 gives the plan a way to author jira-grade artifacts; this step makes the first consumer read them — with the read-time contract validation the plan commits to, so a mislabeled artifact fails red instead of flowing into story prose.

## Input

- **Step 1's path derivation** (plan_tool/detail_artifacts.py — **step 1 is `done` and the leaf is merged**; step 3's jira additions to it are not): step 3's edit to that leaf produces `derive_jira_detail_path(plan_path, plan, step)` returning `<plan_dir>/plan-details/<plan_slug>/jira/<NN>-<step_slug>.md`. There is no pointer axis — `Step.detail` stays run-grade-only — so jira-grade resolution is canonical derivation plus an `is_file()` check; hard-failure semantics belong here, in the consumer, not in the leaf.
- **Step 3's contract authority** (plan_tool/jira_grade.py, created by step 3 — not at HEAD): the five required H2 display names and first-token matcher set, and a read-time validator (planned name `validate_jira_grade_body(text)`) returning findings with `kind` / `blocking` / `message`, including a targeted wrong-schema finding for a run-grade body at a jira-grade path. Step 3 splits enforcement by audience: **read-time consumers validate the structural five-H2 contract only** — the plain-English prose gate's blocking findings drive step 4's authoring retry loop, never this export. This step must respect that split: a conforming five-H2 body with style findings exports fine.
- **Step 4's artifact producer** (context, not a code dependency, and **not yet built at this step's turn** — execution order is 1 → 2 → 3 → 5 → 6 → 7 → 8 → 9 → 4 → 10): `plan-tool detail <name> --grade jira` is what will put artifacts at the derived paths. Do not pin this step's flag to step 4's; step 3 is the axis authority and both consumers take their values from it (see Implementation). Until step 4 lands, jira-grade artifacts are hand-authored or absent, and this step's job is to fail loudly when they are absent — which is exactly what its missing-artifact gate does.
- **Verification limit:** step 1 is `done`, so `plan_tool/detail_artifacts.py` is merged — verify its symbols against the module. `plan_tool/jira_grade.py`, step 3's jira path additions, and the step 4 wiring do **not** exist at HEAD; every symbol cited from those is a dependency contract from steps 3/4's detail files. Re-verify exact names against the merged code before wiring, and note in the PR if any drifted. Everything cited from `plan_tool/jira.py` and `plan_tool/cli/jira_cmd.py` is verified at HEAD.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/jira.py` — add the grade parameter to `export_jira`; build the jira-grade `step_detail_map` and validate every artifact before any render or invoke; thread an optional selected-path map through `render_jira_prompt` → `_render_steps_block` → `_render_step_detail`; pass the selected map to `format_markdown` / `format_json` and into `_export_jira_append` (whose existing `step_detail_map` parameter already reaches `_ticket_needs_detail_refresh`).
  - `plan_tool/cli/jira_cmd.py` — register `--grade {run,jira}` (default `run`) on the `jira` subparser in `register`; read it in `cmd_jira` via `getattr(args, "grade", "run")` and forward it to `export_jira`; add a loud guard for grade/flag combinations that would silently no-op.
  - `docs/cli/jira.md` — regenerated via `python -m plan_tool.cli_reference --write` (drift-guarded by `tests/cli/test_cli_reference.py`); never hand-edited.
  - `tests/test_jira.py` — export-seam tests: selected-map threading, hard-failure, wrong-schema rejection, append refresh, default-unchanged.
  - `tests/cli/test_jira_cmds.py` — CLI-routing tests: flag forwarding, legacy-namespace default, guard rejection.

## Implementation

- **The selector is `--grade {run,jira}`, default `run`, with the values taken from step 3's grade constants** (`JIRA_GRADE_VALUES` for `choices=`). Step 3 is the authority for the axis spelling; do not pin this flag to another consumer's flag, and do not re-declare the tokens. Register it in `plan_tool/cli/jira_cmd.py:register` beside the existing `--format` choice flag. Read it in `cmd_jira` with `getattr(args, "grade", "run")` — hand-built argparse namespaces are a repo-wide test idiom, and `cmd_direct_jira` (`plan_tool/cli/direct_cmd.py`) calls `cmd_jira` with a namespace that has no `grade` attribute; the getattr default keeps the unattended `direct-jira` pipeline on run-grade with zero edits there. On `export_jira`, one way: a keyword-only `grade: str = "run"` (matching `generate_detail`'s kwarg name from step 4), rejected values raising `JiraError` the same way an unknown `format` does.

- **When `grade == "jira"`, replace the map — don't merge.** Today's build is `step_detail_map = {s.id: s.detail for s in plan.steps if s.detail}` in `export_jira`. Under jira grade, build the map from `derive_jira_detail_path` for every step **whose jira artifact exists on disk**, converted to repo-relative POSIX strings (the map's values flow verbatim into markdown links, JSON `plan_detail_paths`, and `_ticket_needs_detail_refresh`'s string comparisons, all of which assume repo-relative paths like `s.detail` today). The run-grade map build stays untouched on the default path.

- **Validate before anything else spends work or writes output — including `--dry-run`.** A helper in `plan_tool/jira.py` (one way: `_build_jira_grade_detail_map(plan, plan_path, repo_root)`) that, per **non-`done`** step (the plan's bundle-coverage rule — `done` steps are exempt here exactly as they are in the grade-aware audit's bundle check, and as this step's own append logic already treats them by re-emitting only non-done tickets):
  - derives the path and checks `is_file()` — missing → `JiraError` naming the step id and the expected repo-relative path. **The message must be permanently true and must name no plan-internal step number** — this text ships to operators, and nothing in this plan owns editing it later (step 4 cannot: its declared footprint is `plan_tool/detail.py`, `plan_tool/cli/authoring.py`, `docs/cli/detail.md`, and tests; step 10 ships no production code). So state the durable fact — no jira-grade detail artifact exists at that path, and the jira-grade contract is documented in `DETAIL_FORMAT.md` — rather than naming a step or a command that does not exist yet and would need correcting once it does. A present run-grade `Step.detail` file is **never** accepted as a substitute — that's the plan's no-hidden-fallback rule, and the test pins it.
  - a **`done`** step whose artifact is missing is not an error: it is omitted from the map and renders with **no** detail body. It must never fall back to `Step.detail`'s run-grade prose — the exemption relaxes the coverage requirement, never the no-hidden-fallback rule. Pin both halves with a test.
  - reads the body and runs step 3's validator; any blocking **structural** finding → `JiraError` carrying the validator's message (the wrong-schema "run-grade body at a jira-grade path" message surfaces verbatim). Do not fail on prose-gate findings — read-time validates structure only, per step 3's audience split.
  - Collect all steps' problems into one error rather than failing on the first — an operator fixing a bundle wants the full list.

  Run this before the `dry_run` branch and before `read_existing_export`, so a dry run also fails loudly: the dry-run output is the prompt that embeds the bodies, and printing a prompt grounded on a missing or mislabeled artifact is exactly the masked-contract failure the plan forbids. The invoker must be unreachable on any validation failure.

- **Thread the selected map into the prompt — this is the one genuinely new plumbing.** `format_markdown` / `format_json` already take `step_detail_map`, and `_export_jira_append` already threads it to `_ticket_needs_detail_refresh` — for all of those, the only change is what the map contains. But `_render_step_detail` reads `step.detail` directly and ignores the map, so the prompt would embed run-grade bodies while the links point at jira artifacts. Add an optional selected-paths parameter (default `None` = today's `step.detail` behavior, keeping `render_jira_prompt`'s other callers and the public re-export in `plan_tool/__init__.py` compiling unchanged) down `render_jira_prompt` → `_render_steps_block` → `_render_step_detail`, and pass the jira map at all **four** `render_jira_prompt` call sites — the dry-run and the real invocation in `export_jira`, and the dry-run and the real invocation in `_export_jira_append` (verified at HEAD; re-count when implementing) — when the grade is jira. Missing any one of them (the dry-run branches are the easy misses) reproduces the masked-contract shape this step forbids: a `--dry-run --grade jira` prompt embedding run-grade bodies. Both in-footprint callers must pass it for the feature to exist; the enumerated out-of-footprint surface that stays on the default is just the `__init__` re-export (no other module calls these functions at HEAD).

- **Keep one output artifact; let append mode do the grade switch.** The export target stays `derive_jira_output_path` (`jira-stories.{md,json}`) regardless of grade — tickets are created in JIRA once, and a second parallel story file would fork ticket identity. Consequence, worth a comment and a test: re-exporting an existing run-grade-linked artifact under `--grade jira` makes `_ticket_needs_detail_refresh` flag every non-done ticket (its markdown/JSON detail links don't match the jira-grade map), so those tickets are re-emitted with their original ids and refreshed links. That is the intended behavior — links must describe the bundle the export actually consumed — not a bug to suppress. The reverse direction holds symmetrically and deserves the same comment: a later default (run-grade) append over a jira-grade-linked export re-flags every non-done ticket and reverts its links to run-grade paths, so alternating grades flip-flops the artifact's links export-by-export. The invariant is simply "links describe the most recent export's grounding"; operators who want stable jira-grade links keep exporting with `--grade jira` (step 10's `JIRA_FORMAT.md` note documents both directions).

- **Sweep the flag surface; nothing silently no-ops.** `--max-hours`, `--format`, `--output`, `--no-write`, `--stdout`, `--epic`, `--jira-tag`, `-y` all work unchanged under `--grade jira` (they're orthogonal to detail grounding). `--dry-run` works with the validate-first semantics above. Two combinations have no meaning: `--grade jira` with `--lint` (lint reads the story artifact, not detail) and with `jira config`. Recommended: reject `--lint --grade jira` with `error(...)` + rc 2 in `cmd_jira` before any context load; for `jira config` follow the existing convention (export-only flags are already ignored on the config dispatch path) — but pick one and test it, so the grade can never be selected and then silently ignored on the lint path.

- **Carry the plain-English story-prose directive into the export prompt.** The plan's prose contract covers the `jira` story output, not just the authored bodies — and story prose is born in the backend call this step grounds. When the grade is jira, append a short plain-English directive block to the rendered export prompt (in `plan_tool/jira.py`, after `render_jira_prompt` returns — no prompt-template fork): short, direct sentences; say each thing once; no filler; keep every path, symbol anchor, example, and constraint intact. This is a prompt contract, not a gate — read-time prose findings stay advisory per step 3's audience split, and the default (run-grade) prompt is byte-for-byte unchanged.

- **Don't touch the sanctioned test seams.** `cmd_jira` must keep calling `export_jira` as a bare module global — `tests/cli/test_jira_cmds.py`'s docstring pins that stubs `setattr` on `plan_tool.cli.jira_cmd`; no aliasing or local re-binding. Same for the existing `JiraInvoker` seam: all new tests inject fake invokers, per `tests/test_jira.py`'s no-real-claude rule.

## Tests

New cases in `tests/test_jira.py` (a new class beside `TestExportJira`, reusing its plan fixture plus jira-grade artifact fixtures written under `plan-details/<slug>/jira/`):

- `test_export_grade_jira_markdown_links_jira_paths` — `--grade jira` markdown output's per-step detail links all point at `jira/` paths, none at `Step.detail`.
- `test_export_grade_jira_json_plan_detail_paths` — JSON `plan_detail_paths` carry the jira-grade repo-relative paths.
- `test_export_grade_jira_prompt_embeds_jira_body` — the prompt handed to the invoker contains the jira-grade body text and not the run-grade body text for the same step.
- `test_export_grade_jira_missing_artifact_hard_fails` — one step's jira artifact absent → `JiraError` naming the step and expected path; the invoker is never called.
- `test_export_grade_jira_never_substitutes_run_grade` — the failing step has a present, valid run-grade `Step.detail` file → still fails; the run-grade path appears nowhere in the error's accepted sources.
- `test_export_grade_jira_mislabeled_body_hard_fails` — a complete run-grade seven-section body stored at the jira path → `JiraError` carrying the validator's wrong-schema message; invoker never called.
- `test_export_grade_jira_dry_run_validates` — `dry_run=True` with a missing/mislabeled artifact raises instead of printing a prompt.
- `test_export_grade_jira_dry_run_prompt_embeds_jira_body` — `dry_run=True` with a valid bundle emits a prompt containing the jira-grade body text and not the run-grade body text (pins the dry-run success branch's map threading).
- `test_export_grade_jira_prompt_carries_plain_english_directive` — the `--grade jira` prompt contains the plain-English directive block; the default-grade prompt does not.
- `test_export_grade_jira_reports_all_broken_steps` — two broken steps → one error naming both.
- `test_export_grade_jira_done_step_missing_artifact_exempt` — a `done` step with no jira artifact exports cleanly (the bundle-coverage rule's exemption). Scoped to this export's own exemption behavior: the cross-consumer half — that the same bundle also passes `completeness-audit --grade jira` — belongs to step 9, which is where both consumers first exist (this step runs before it).
- `test_export_grade_jira_done_step_never_falls_back_to_run_grade` — that exempt `done` step renders with no detail body; its run-grade `Step.detail` text appears nowhere in the prompt or the links.
- `test_export_grade_jira_prose_findings_do_not_block` — a conforming five-H2 body that would trip the plain-English gate exports successfully (read-time is structural only).
- `test_export_grade_jira_append_refreshes_links_preserves_ids` — append over an existing run-grade-linked export re-emits non-done tickets with the same ids and jira-grade links.
- `test_export_default_grade_unchanged` — no grade / `grade="run"` produces output identical to today's for the same fixture (the existing `TestExportJira` / `TestExportJiraAppend` / `TestRenderJiraPrompt` suites are the wider fence and must pass unmodified).

New cases in `tests/cli/test_jira_cmds.py`:

- `test_cmd_jira_grade_forwards_to_exporter` — `--grade jira` reaches the stubbed `plan_tool.cli.jira_cmd.export_jira` with the jira selection.
- `test_cmd_jira_legacy_namespace_defaults_run` — a hand-built namespace with no `grade` attribute exports run-grade (the `getattr` contract; also what keeps `direct-jira` unchanged).
- `test_cmd_jira_grade_lint_combination_guard` — the chosen lint-path behavior (recommended: rc 2 with an error naming the conflict, before any context load).

### Test-creation order (feature step)

This is a **feature** step: add each test with the code it covers — the map/threading tests alongside the `export_jira` changes, the validation tests alongside the gate helper, the CLI tests alongside the `register`/`cmd_jira` wiring. Gate: every test above green (and the existing jira suites green with zero edits) before the step is done.

## Acceptance criteria

- `plan-tool jira <name> --grade jira` on a plan with a complete, valid jira-grade bundle writes `jira-stories.{md,json}` whose prompt grounding, markdown links, and JSON `plan_detail_paths` all reference `plan-details/<slug>/jira/` paths.
- With any **non-`done`** step's jira artifact missing or failing the five-H2 contract, the export exits non-zero via `JiraError` before the backend invoker is called — including under `--dry-run` — and the error names each broken step and path; a present run-grade detail file is not accepted as a substitute.
- A `done` step with no jira artifact does not fail the export (the plan's bundle-coverage rule, matching the grade-aware audit's exemption so both consumers agree on the same bundle); it is omitted from the selected map and renders with no detail body, never the run-grade one.
- A run-grade body at a jira-grade path is rejected with the validator's wrong-schema message surfaced in the error.
- A conforming jira-grade body with prose-style findings exports without error.
- Under `--grade jira` the export prompt — including the `--dry-run` success path's prompt — embeds jira-grade bodies and carries the plain-English story-prose directive; the default-grade prompt is byte-for-byte unchanged.
- The flag is `--grade`, default `run`, with `choices=` taken from step 3's grade constants rather than re-declared or copied from a sibling consumer; `cmd_jira` reads it via `getattr(args, "grade", "run")`, and a namespace without the attribute behaves as run-grade.
- Default-path output is unchanged: all existing `tests/test_jira.py` and `tests/cli/test_jira_cmds.py` tests pass with zero edits.
- Append mode under `--grade jira` preserves existing ticket ids while refreshing their detail links to jira-grade paths.
- `docs/cli/jira.md` matches the regenerated reference (`tests/cli/test_cli_reference.py` green).
- All new tests enumerated above pass; `uv run pytest tests/ -q` is green.

## References

- [Jira Cloud platform REST API v3 — Issues](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/) — what the exported story fields ultimately map onto; useful when deciding what the jira-grade-grounded descriptions must carry.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — `choices`/default wiring for the `--grade` flag on the shared subparser.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — stubbing the module-global `export_jira` seam and the `JiraInvoker` in the new tests.
- [CommonMark Spec 0.30 — ATX headings](https://spec.commonmark.org/0.30/) — ground truth for the H2 syntax the read-time contract re-validation parses.

## Deferred

- Opt-in jira-grade `run` rendering — step 6 owns the renderer/launcher/run_cmd threading and the run-side no-silent-fallback rule.
- Grade-aware completeness audit grounding — steps 7–9 own audit-side grade resolution.
- `--grade` for `direct-jira` — the packaged pipeline stays run-grade via the `getattr` default; giving it an explicit grade selector is a separate decision for a later plan (route to `BACKLOG.md` if wanted).
- Grade-aware `jira --lint` semantics — lint judges the story artifact, not the detail bundle; nothing grade-shaped changes there beyond the combination guard.
- Renumber-staleness of unpointed `jira/` artifacts after a split — step 3 classified this a loud gap precisely because this step's hard failure is the detection surface; a durable migration routes through reconcile once a real corpus exists.
- Rendering jira-grade prose into Atlassian Document Format for direct API creation — the export stays markdown/JSON paste-ready; ADF is out of this plan's scope.
- Docs beyond the generated flag reference (`JIRA_FORMAT.md`, flow docs, backlog bookkeeping) — step 10 owns them.
