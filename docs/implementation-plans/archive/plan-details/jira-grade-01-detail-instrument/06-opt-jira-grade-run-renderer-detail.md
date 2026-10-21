> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add the opt-in jira-grade run renderer: `--detail-grade jira` keeps `--mode run` public, adds a `run-jira` prompt, and hard-fails on a missing or mislabeled jira artifact

## Summary

Give `plan-tool run` an opt-in detail-grade selector that executes a step from its jira-grade detail artifact instead of the run-grade `Step.detail` file: a new prompt template `plan_tool/prompts/run-jira.md`, grade-aware detail loading in `plan_tool/renderer.py`, a `detail_grade` keyword on `plan_tool/launcher.py:run_step`, and CLI threading through `cmd_run`, `_cmd_run_sweep`, `_build_run_resume_command`, and both `RunLogWriter.start` flags payloads in `plan_tool/cli/run_cmd.py`. The key design decision: grade is a separate axis from mode — the public `--mode run` value is unchanged (so `MUTATING_MODES` lifecycle, the sweep's mode allowlist, and the test-authoring gate all keep working), while the grade selects the prompt template and detail source internally, and a missing or wrong-schema jira artifact is a hard failure before any backend call — never a silent fall back to the run-grade body. On green, `plan-tool run <name> --detail-grade jira` executes and advances a step grounded on its five-section jira artifact, a default `plan-tool run` is unchanged in every way, and approx. 19–21 new tests pass across `tests/test_renderer.py`, `tests/test_launcher.py`, and `tests/cli/test_run_cmd.py`.

## Table of Contents

- [Summary](#summary) — what the step ships and the one design decision
- [Why](#why) — why execution needs a jira-grade lane with a loud failure mode
- [Input](#input) — the step 1 / step 3 / step 4 contracts this step consumes, and what can't be verified at HEAD
- [Files (creates vs edits)](#files-creates-vs-edits) — the new prompt template and per-file edits
- [Implementation](#implementation) — the grade axis, the strict loader, the deep gate, and the CLI threading
- [Tests](#tests) — renderer, launcher, and CLI cases, with the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the plan-level references relevant to this step
- [Deferred](#deferred) — callers and surfaces deliberately left on run-grade

## Why

`run` is the third consumer of the jira-grade artifact, and the one that shows a compact five-section body is enough to execute from. Stage 01 ships it opt-in and measures nothing (the plan's Out of scope), but its payoff lands inside this stage: the end-to-end smoke check on step 4 runs this renderer's dry-run leg over the first authored bundle, so a bundle nobody could build from fails there rather than in a later stage. At HEAD there is exactly one detail source in the run lane: `plan_tool/renderer.py:_build_variables` always calls the permissive `_load_detail(step, repo_root=...)`, which reads `Step.detail` and degrades a missing file into soft prose ("Proceed using the step title and files list"). That tolerance is right for the legacy default but wrong for an explicit grade selection — a run that silently executes against the run-grade body (or against no body) while claiming to execute the jira artifact misreports which contract it ran, which is the plan's `artifact-ambiguity` blocker (HIGH, recurring) in execution form. Steps 4 and 5 gave the plan an authoring surface and an export consumer for jira-grade artifacts; this step makes `run` the second consumer, with the same read-time contract validation and hard-failure shape step 5 established for `jira`. The naive route — registering `run-jira` as a new `--mode` value — fails structurally: `args.mode` is simultaneously the public review/execution selector, the sweep's allowlist (`_cmd_run_sweep` rejects every mode except `run`), the renderer's template key, and the `MUTATING_MODES` lifecycle gate, so a new mode value either breaks `--all` or stops the step from ever advancing.

## Input

- **Step 1's path derivation** (plan_tool/detail_artifacts.py — **step 1 is `done` and the leaf is merged**; step 3's extension is not): `derive_jira_detail_path(plan_path, plan, step)` returns `<plan_dir>/plan-details/<plan_slug>/jira/<NN>-<step_slug>.md`. There is no pointer axis — `Step.detail` stays run-grade-only — so jira-grade resolution is canonical derivation plus an `is_file()` check, and hard-failure semantics live in the consumer (here), not the leaf.
- **Step 3's contract authority** (plan_tool/jira_grade.py, created by step 3 — not at HEAD): the five required H2 sections (Intent, Change, Constraints, Done when, Out of scope; first-token matching) and the read-time validator (planned name `validate_jira_grade_body(text)`) returning findings with blocking/message fields, including a targeted wrong-schema message for a run-grade body at a jira-grade path. Read-time consumers validate the structural H2 contract only — the plain-English prose gate is authoring-loop machinery and must not run here.
- **Step 3's grade constants**: take the `run` / `jira` axis values from step 3 (the schema authority, landed at this step's turn), not from a sibling consumer's flag.
- **Remediation wording**: this step's failure messages point the operator at jira-grade authoring, which step 4 ships — and step 4 runs *after* this step. Word every such message so it is **permanently true and names no plan-internal step number**: this text ships to operators, and nothing owns editing it later (step 4's declared footprint cannot reach `plan_tool/renderer.py` or `plan_tool/cli/run_cmd.py`, and step 10 ships no production code). State the durable fact — the jira-grade artifact is missing at the named path, and its contract is documented in `DETAIL_FORMAT.md` — not a command line that fails until step 4 lands, and not a reference to a step number an operator cannot resolve.
- **Launcher lifecycle contract at HEAD** (verified): `plan_tool/launcher.py:MUTATING_MODES = frozenset({"run"})` gates mark-done/advance, the test-order directive append, and the test-authoring gate; `run_step` renders via `render_prompt(plan, step, repo_root=..., mode=mode, collect_blocks=...)` inside the `prompt_build` run-log phase, then branches on `dry_run` before calling the invoker. Keeping public `mode == "run"` is what keeps all of that working unchanged.
- **Verification limit**: step 1 is `done` — `plan_tool/detail_artifacts.py` is merged, so verify its symbols against the module. **By this step's actual turn, steps 3 and 5 have also landed** (execution order 1 → 2 → 3 → 5 → 6 → 7 → 8 → 9 → 4 → 10), so their symbols are verifiable too — re-grep and describe what shipped; where this file and the merged code disagree, the code wins. Only step 4 is still unbuilt at this step's turn. What follows describes the state at authoring time, when steps 3–5 were not implemented at HEAD: `plan_tool/jira_grade.py`, step 3's jira path additions, and the `detail`/`jira` `--grade` flags do not exist on disk yet. Those symbol names are dependency contracts; re-verify exact names and signatures against the merged code before implementing.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/run-jira.md` — the jira-grade execution prompt template.
- **Existing files (edits only):**
  - `plan_tool/renderer.py` — add a grade parameter to `render_prompt` (threaded into `_build_variables`), a strict jira-grade detail loader beside `_load_detail`, and template-key selection (`run-jira` when grade is jira and mode is `run`).
  - `plan_tool/launcher.py` — add `detail_grade: str = "run"` to `run_step`; deep guard rejecting jira grade with any non-`run` mode; surface load/validate failures as `LauncherError` before the invoker.
  - `plan_tool/cli/run_cmd.py` — register the flag; rc=2 guards before the run log opens; a whole-scope preflight that aggregates every missing/invalid jira artifact; pass the grade to both `run_step` call sites; add it to both `RunLogWriter.start` flags dicts and to `_build_run_resume_command`; skip the run-grade missing-detail warn/confirm helpers under jira grade.
  - `docs/cli/run.md` — regenerated via `python -m plan_tool.cli_reference --write`, never hand-edited (drift-guarded by `tests/cli/test_cli_reference.py`).
  - `tests/test_renderer.py`, `tests/test_launcher.py`, `tests/cli/test_run_cmd.py` — new test classes per the Tests section.

## Implementation

**The grade axis (the key decision).** Grade is input selection; mode is lifecycle. Add a detail-grade option to the `run` subparser — recommended spelling `--detail-grade` with `choices=("run", "jira")`, default `"run"`, matching the step title's "detail-grade option"; the exact flag name is the implementer's call, but it must be a new flag, never a new `--mode` value:

- **`AVAILABLE_MODES` (`plan_tool/cli/app.py`) gains nothing.** `run-jira` is an internal template key, not a public mode. The rejected alternative — adding `run-jira` to the mode list — breaks `_cmd_run_sweep`'s `args.mode != "run"` rejection and falls outside `MUTATING_MODES`, so `--all` would refuse it or the step would never advance.
- **`MUTATING_MODES` is untouched.** Because `mode` stays `"run"`, mark-done/advance, the lessons append, the test-order directive, and the test-authoring gate all apply to a jira-grade run with zero edits.
- Read the flag with `getattr(args, "detail_grade", "run")` everywhere — hand-built namespaces are a repo-wide test idiom, and `plan_tool/cli/direct_cmd.py:cmd_direct_run` reaches `cmd_run` with a copied namespace, so the getattr default is what keeps the packaged direct-run pipeline on run-grade.

**Grade-aware rendering (`plan_tool/renderer.py`).** A new prompt file alone is not enough: `_build_variables` would still inject the run-grade body into `${step_detail}` with its permissive fallback. Thread the grade into variable construction:

- `render_prompt` gains an optional keyword (e.g. `detail_grade: str = "run"`); the default preserves today's behavior exactly. `render_prompt` is publicly re-exported in `plan_tool/__init__.py`, so the parameter must be optional and keyword-only.
- Template selection: when grade is jira and mode is `run`, load `plan_tool/prompts/run-jira.md`; every other combination keeps the existing `prompts/<mode>.md` lookup.
- Detail loading splits by grade. Run grade keeps `_load_detail` unchanged. Jira grade uses a strict loader: derive the path via step 1/3's `derive_jira_detail_path`, and on a missing file or a body that fails step 3's `validate_jira_grade_body` structural check, **raise** (a renderer-owned exception type works; the renderer cannot import `launcher`) with a message naming the derived path and the failure, plus remediation worded per the Input rule above — the missing jira-grade artifact and its documented contract, never a step number or a command that does not exist yet. No prose placeholder, no fall back to `step.detail` — that soft shape is exactly what this grade must not have.
- `collect_blocks` must measure the body the prompt actually embeds — the jira body under jira grade — so the prompt-budget advisory and the run log's byte count stay honest.

**The `run-jira` prompt template (`plan_tool/prompts/run-jira.md`).** Model it on `plan_tool/prompts/run.md`: same `${...}` variables (`${step_detail}` carries the jira body), same closing contract — the `## Validation` / `## Summary` tail that `launcher.py:extract_summary` and the lessons append parse, and no conflict with the test-order directive `run_step` appends after rendering. The body differs in framing: tell the implementer the detail is a compact five-section contract, that **Done when** is the acceptance surface and **Out of scope** is the fence, and that the step title plus files list carry the footprint. Write it in plain, concise English: short direct sentences, familiar words, each thing said once, no filler — while keeping every `${...}` variable, path, and section name intact. This is the plan's plain-English prose contract, which names this template beside the step 4 authoring prompt. Nothing enforces it at run time — the file is hand-authored, not model output — so it is checked by this step's acceptance criteria and by review of the file itself. Keep it terse for the same reason the artifact is compact.

**The deep gate (`plan_tool/launcher.py:run_step`).** `run_step` gains `detail_grade: str = "run"` and passes it to `render_prompt`. Two hard rules:

- **Reject jira grade with any non-`run` mode** at the top of `run_step` (`LauncherError`) — review/reconcile prompts have their own grounding and the grade doesn't apply. This is the deep guard behind the CLI guard, for library callers that never pass through argparse.
- **The invoker is unreachable on any jira-grade load/validate failure, including under `--dry-run`.** The strict loader raises during the `prompt_build` phase — which is already before the `dry_run` branch and the invoker call — so ordering comes free; `run_step` must convert the renderer's grade error into `LauncherError` so `cmd_run` / `_cmd_run_sweep` surface it as rc=2 instead of a traceback. The existing `prompt_build` phase-end `outcome="error"` bookkeeping already covers the run-log side.

Only `run_step` gains the parameter. The other `render_prompt` call sites in `launcher.py` (`apply_finding`, its follow-up prompt, `run_all_done_steps`) and the other `run_step` callers (`plan_tool/auto_reconcile.py`, `plan_tool/bench.py`, `plan_tool/cli/review_actions.py`, `plan_tool/cli/reconcile.py` — three sites) stay on the default and keep compiling unchanged; the callers that must pass the value for the feature to exist are exactly the two in `plan_tool/cli/run_cmd.py`.

**CLI threading (`plan_tool/cli/run_cmd.py`).** Sweep the run flag surface and classify every interaction:

- **Rejected, rc=2, before any run log or context work** (a decline must leave no ghost run dir, mirroring the existing mutex checks in `cmd_run`): jira grade + `--mode <review>` (redirect: grade applies to execution only), and jira grade + `--reconcile` (the audit path uses its own `run-reconcile` prompt).
- **Work unchanged, scoped to the jira artifact:** `--step`, `--all`, `--commit`, `--dry-run` (renders the `run-jira` prompt; the hard gate still fires first), `-y`, `--archive`, `--allow-missing-parent`, `--max-steps`, and the backend/rate-limit flags.
- **Preflight, aggregated:** before the run log opens (single-step) and before the sweep loop starts (`--all`), check every in-scope step's jira artifact — derivation + `is_file()` + structural validation — and report **all** broken steps in one rc=2 error, not just the first (the same collect-everything shape step 5 used for the export gate). Checking only the in-scope steps is the plan's bundle-coverage rule applied at its narrowest permitted width: a consumer may check fewer steps than the rule's non-`done` set (a run grounds only on what it executes) but never more, so `run` can never reject a bundle the audit and the export call complete.
- **The one case where in-scope leaves the rule's set: an explicitly requested `done` step.** `plan_tool/launcher.py:resolve_step` honours `--step N` whatever the step's status, so `plan-tool run <name> --step N --detail-grade jira` on a `done` step puts a step the bundle-coverage rule exempts into this preflight's scope. Do **not** widen the rule and do **not** blanket-exempt `done` steps here — `run` cannot execute a step with no body, so silently skipping the check just moves the same failure to render time with a worse message. The resolution is that the two questions are different: *is this bundle complete?* is the coverage rule's question, and the bundle is still complete; *can this run execute the step it was asked to?* is this preflight's, and it cannot. So the check runs on the explicitly requested step, and its **error must not be worded as a bundle-coverage verdict** — it says this step has no jira-grade body to execute, names the derived path, and notes that `done` steps are exempt from bundle coverage, so the bundle itself is not at fault. Nothing about the audit's or the export's verdict on the same bundle changes, which is what the plan's one-rule criterion protects.
- **Skip the run-grade soft gates under jira grade:** `_confirm_missing_step_details` and `_warn_missing_step_detail` read `Step.detail` and recommend `plan-tool detail <name> --step N` — under jira grade both the check and the remediation point at the wrong artifact, and a warn-and-proceed path is the silent-fallback shape this grade forbids. The aggregated hard preflight replaces them.
- **Thread the value to both `run_step` call sites** (the one in `cmd_run` and the one inside `_cmd_run_sweep`'s loop). Keep the module-global call form on `run_step` — existing suites patch it by name.
- **Durability surfaces (required, easy to miss):** add the grade to both `RunLogWriter.start` `flags` dicts (the single-run payload beside `"mode"`, and the sweep payload beside `"all"`/`"sweep_index"`), and make `_build_run_resume_command` append the flag when it's non-default — otherwise a rate-limit resume replays the run under the wrong grade and the persisted log describes a different invocation than the one that ran.

## Tests

All new behavior; place cases in the existing suite files.

`tests/test_renderer.py` (new class, e.g. `TestRenderJiraGradePrompt`):
- `test_jira_grade_renders_jira_body` — jira artifact body appears in the prompt; the run-grade `Step.detail` body does not.
- `test_jira_grade_uses_run_jira_template` — a marker unique to `run-jira.md` is present; `run.md`'s framing is not.
- `test_jira_grade_missing_artifact_raises` — no jira file on disk raises; the run-grade body is not substituted.
- `test_jira_grade_wrong_schema_raises` — a seven-section run-grade body stored at the jira path is rejected with the wrong-schema message.
- `test_jira_grade_collect_blocks_measures_jira_body` — the "step detail" block byte count matches the jira body.
- `test_default_grade_render_unchanged` — `render_prompt` without the new keyword produces today's output for the same inputs.

`tests/test_launcher.py` (new class, e.g. `TestRunStepJiraGrade`; stub invoker per TESTING.md — no real backend):
- `test_jira_grade_happy_path_advances` — invoker exit 0 marks the step done and advances (public mode stays `run`), and the invoked prompt contains the jira body.
- `test_jira_grade_missing_artifact_no_invoke` — `LauncherError`; the stub invoker is never called; plan untouched.
- `test_jira_grade_invalid_artifact_no_invoke` — same for a wrong-schema body.
- `test_jira_grade_dry_run_still_validates` — `dry_run=True` with a broken artifact fails; no prompt is printed.
- `test_jira_grade_rejected_with_review_mode` — `mode="check"` + jira grade raises before any work.
- `test_jira_grade_appends_test_order_directive` — the mutating-mode directive still rides the jira prompt.
- `test_run_step_default_grade_unchanged` — omitting the kwarg reproduces today's behavior.

`tests/cli/test_run_cmd.py` (extends the deterministic pre-claude surface this file owns):
- `test_detail_grade_flag_registered` — parser accepts the flag with choices run/jira, default run.
- `test_detail_grade_jira_review_mode_rejected_rc2` — rc=2, no run dir created.
- `test_detail_grade_jira_reconcile_rejected_rc2` — rc=2 before the run log.
- `test_jira_preflight_aggregates_all_broken_steps` — one error names every missing/invalid artifact.
- `test_jira_preflight_explicit_done_step_without_artifact` — `--step N --detail-grade jira` on a `done` step with no jira artifact fails rc=2 naming the derived path, and its message does **not** claim the bundle is incomplete; the same bundle still passes `jira --grade jira` and `completeness-audit --grade jira`, so the three consumers stay in agreement.
- `test_resume_command_includes_detail_grade` — `_build_run_resume_command` carries the flag when jira.
- `test_resume_command_omits_default_grade` — no flag emitted for run grade.
- `test_run_log_flags_include_detail_grade` — single-run `flags` payload records the grade.
- `test_sweep_run_log_flags_include_detail_grade` — sweep payload records it too.
- `test_sweep_threads_detail_grade_to_run_step` — a stubbed `run_step` receives the kwarg from `_cmd_run_sweep`.
- `test_hand_built_namespace_defaults_to_run_grade` — a namespace without the attribute (the `_sweep_args` idiom) behaves as run grade, no `AttributeError`.

### Test-creation order (feature step)

Write each test beside the behavior it covers: renderer cases with the renderer edits, launcher cases with the `run_step` changes, CLI cases with the flag threading. Green-before-done gate: every test named above must pass — and the existing `tests/test_renderer.py`, `tests/test_launcher.py`, `tests/cli/test_run_cmd.py`, and `tests/test_cli.py` suites must stay green — before this step is finished.

## Acceptance criteria

- `plan-tool run <name> --detail-grade jira` (or the chosen flag spelling) executes the step from its jira-grade artifact, and on invoker success marks the step done and advances — public mode remains `run` throughout.
- A missing jira artifact, or a run-grade body at the jira path, fails with rc=2 **before any backend call**, including under `--dry-run`; the error names the derived path and carries remediation that is permanently true — the missing jira-grade artifact and its documented contract, with no plan-internal step number and no command line that fails until step 4 lands; the run-grade `Step.detail` body is never substituted.
- The single-step preflight and the `--all` preflight report every broken step in one error, not just the first.
- An explicitly requested `done` step with no jira artifact fails the preflight as an execution problem, not a coverage verdict: rc=2 naming the derived path, no claim that the bundle is incomplete, and the same bundle still passes `jira --grade jira` and `completeness-audit --grade jira`.
- `--detail-grade jira` combined with `--mode <review>` or `--reconcile` exits rc=2 before any run log opens; no ghost run dir exists afterward.
- `_build_run_resume_command` output includes the grade flag exactly when it's non-default; both `RunLogWriter.start` flags payloads record the grade.
- A default `plan-tool run <name>` (no grade flag, or a namespace lacking the attribute) is unchanged: same prompt bytes, same soft missing-detail warn/confirm behavior, same lifecycle.
- `AVAILABLE_MODES` and `MUTATING_MODES` are unmodified; `run-jira` is not selectable via `--mode`.
- `plan_tool/prompts/run-jira.md` reads as plain, concise English — short direct sentences, familiar words, no filler — with every `${...}` variable, path, and section name intact, satisfying the plan's plain-English prose contract for this template. Checked by reading the file, not by a runtime gate (it is hand-authored, not model output).
- `docs/cli/run.md` is regenerated (not hand-edited) and `tests/cli/test_cli_reference.py` passes.
- All new tests above pass; `uv run pytest tests/ -q` is green.

## References

- [Claude Code — Headless / programmatic mode](https://code.claude.com/docs/en/headless) — how the invoker seam shells out non-interactively; the jira-grade prompt rides the same `-p` call path as the run-grade one.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — flag registration with `choices` and defaults for the new detail-grade option on the `run` subparser.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — stubbing the invoker and `run_step` seams in the launcher and CLI tests.
- [CommonMark Spec 0.30 — ATX headings](https://spec.commonmark.org/0.30/) — ground truth for the H2 contract the read-time validation enforces on the jira artifact.

## Deferred

- Grade selection for `verify-all` / `run_all_done_steps` — the review sweep stays run-grade; its `render_prompt` call keeps the default. A jira-grade audit lane is steps 7–9's grade-aware grounding territory.
- The reconcile lane (`plan_tool/auto_reconcile.py`, `plan_tool/cli/reconcile.py`) stays run-grade — reconcile audits code against the run-grade plan contract; grade-aware audit grounding belongs to steps 7–9.
- An explicit direct-run grade selector — `cmd_direct_run` inherits run grade via the `getattr` default, which is a production behavioral commitment for the unattended pipeline; a deliberate `direct-run --grade` is a separate decision to route to `BACKLOG.md` (mirrors step 5's direct-jira deferral).
- `plan_tool/bench.py`'s `run_step` call — benchmark harness, stays on the default grade.
- Renumber-stale jira artifacts after a split — step 3 deferred this as a loud gap; this step's hard gate is exactly the loud consumer surface that makes the staleness visible (the run fails naming the missing derived path). No migration work here.
- Prose-gate enforcement at run time — step 3's audience split keeps the plain-English gate in the authoring loop only; this consumer validates the structural H2 contract and nothing more.
