> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Convergence Actuation And Surfacing
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Extract the fingerprint staleness verdict out of _actuate_scope_out into
    a shared helper
  files:
  - plan_tool/cli/convergence_cmd.py
  - tests/cli/test_convergence_cmd.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/convergence-actuation-and-surfacing/01-extract-fingerprint-staleness-verdict.md
  status: done
- id: 2
  title: Add the --apply-split flag and _actuate_split to convergence, dispatching
    the split executor for a spinning FORK_LOCALIZED verdict
  files:
  - plan_tool/cli/convergence_cmd.py
  - docs/cli/convergence.md
  - tests/cli/test_convergence_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/convergence-actuation-and-surfacing/02-apply-split-flag-actuate-split.md
  status: done
- id: 3
  title: Add a pure Convergence diagnosis section renderer to completeness_report.py,
    gated on a spinning verdict
  files:
  - plan_tool/completeness_report.py
  - tests/test_completeness_report.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/convergence-actuation-and-surfacing/03-pure-convergence-diagnosis-section.md
  status: done
- id: 4
  title: Wire the convergence section into _persist_and_present_report, counting the
    current run exactly once
  files:
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/convergence-actuation-and-surfacing/04-wire-convergence-section-persist.md
  status: done
- id: 5
  title: 'Document --apply-split and the report section, and reconcile BACKLOG #57
    plus the Quality/accuracy roll-up'
  files:
  - CLAUDE.md
  - RUNBOOK.md
  - docs/AUDIT_FLOW.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 4
  detail: docs/implementation-plans/plan-details/convergence-actuation-and-surfacing/05-document-apply-split-report-section.md
  status: done
---
# Convergence Actuation And Surfacing

## Overview

This plan closes the gap between the convergence diagnostic *detecting* a spinning audit/apply loop and an operator being able to *act* on it. It adds a `--apply-split` flag to `plan-tool convergence` that actuates the split executor for a spinning `FORK_LOCALIZED` verdict, and surfaces the convergence diagnosis as a rendered section inside the completeness report so a stuck loop is visible without running a separate command. The actuation stays behind the shared apply-or-recommend gate (recommend-only unless `--apply-split` plus a TTY confirm, or `-y`), spends no Claude, and preserves the convergence command's exit-code convention — 0 on every completed outcome, non-zero only on a mid-actuation failure.

## Problem statement

The convergence diagnostic (`convergence_diagnosis.py`, surfaced by `plan-tool convergence <name>`) can *detect* a spinning audit/apply loop — it classifies a `FORK_LOCALIZED` / `FORK_SCOPE_OUT` / `FORK_STRUCTURAL` verdict from the saved report history — but the operator can only *act* on the scope-out arm. `--apply-scope-out` actuates `FORK_SCOPE_OUT`; there is no companion flag to actuate the localized re-split that a spinning `FORK_LOCALIZED` verdict recommends, so a loop stuck on an over-packed step leaves the operator to run `plan-tool split` by hand from a recommendation string. The diagnosis is also only visible by running the standalone `convergence` command: a completeness audit that is silently spinning shows no in-report signal, so the operator never learns the loop is stuck unless they think to check separately.

The user-visible symptom is a completeness audit/apply loop that re-surfaces the same region across runs with no shrinkage, no in-report warning that it is spinning, and — for the localized-split remedy — no one-command actuation. This plan closes both gaps: a `--apply-split` flag that actuates the split executor for a spinning `FORK_LOCALIZED` verdict (behind the shared apply-or-recommend gate), and a rendered convergence-diagnosis section inside the completeness report so a stuck loop is visible without a separate command.

## Architecture

Two levers land on top of the existing convergence diagnostic (`convergence_diagnosis.py`) and its `plan-tool convergence <name>` command (`cli/convergence_cmd.py`), which already loads the saved report history, classifies the `FORK_LOCALIZED` / `FORK_SCOPE_OUT` / `FORK_STRUCTURAL` fork, and — via `--apply-scope-out` — actuates only the scope-out arm through `scope_out.py`. Nothing here changes the diagnostic's inputs (the persisted recommendation/annotation/fingerprint subset) or its zero-Claude, always-exit-0 default contract; the levers add an actuator for the localized-split arm and a passive in-report surface for the diagnosis.

**Lever 1 — `--apply-split` actuation (steps 1–2).** The command grows a companion actuator `_actuate_split` beside `_actuate_scope_out`, reached only for a spinning `FORK_LOCALIZED` verdict. It dispatches the existing split executor (the same one `plan-tool split` and `escalate_to_split` drive) rather than introducing a new split path, so re-split semantics stay single-sourced. `--apply-split` and `--apply-scope-out` are mutually exclusive: a single invocation actuates at most one fork arm, matching the diagnostic's single-verdict classification. Actuation stays behind the project's shared apply-or-recommend gate — recommend-only unless `--apply-split` plus a TTY confirm, or a non-interactive `-y` — so the default path spends no Claude and performs no mutation, and the mutation itself is journaled inside the split executor. Step 1 first hoists the fingerprint-staleness verdict currently inlined in `_actuate_scope_out` into a shared helper so both actuators short-circuit identically on a stale saved report (the diagnosis must not be actuated against fingerprints that no longer match current code); this is a behavior-preserving refactor pinned by characterization tests before Lever 1's new arm consumes the helper. Exit codes follow the command's convention: 0 on every completed outcome (including recommend-only and no-fork), non-zero only on a mid-actuation failure.

**Lever 2 — in-report convergence section (steps 3–4).** The diagnosis becomes visible without running the standalone command by rendering it into the completeness report. Step 3 adds a *pure* section renderer to `completeness_report.py` — no I/O, no Claude — gated to emit only on a spinning verdict, so a healthy loop adds no report noise. **Scope: the completeness series, not the plan-wide worst-of.** Because the completeness report is the completeness loop's own surface, the in-report section reflects only the completeness series' spinning verdict — not `diagnose_convergence`'s plan-wide worst-of headline, which also spans the `detail-reconcile` / `run-reconcile` series. A reconcile-series spin must not read as the completeness loop spinning: step 4 scopes the diagnosis fed to step 3's renderer to the completeness series, and step 3's section heading names the completeness audit/apply loop so the signal never overstates the completeness loop's state. The plan-wide worst-of verdict stays the standalone `plan-tool convergence` command's job. Step 4 wires the section into `_persist_and_present_report` (`cli/completeness_phases.py`), where the subtlety is run-counting: the current audit run must be counted into the report history exactly once when computing recurrence/no-shrinkage — the diagnosis is computed before `build_report_md` from loaded history plus the in-memory current run with this invocation's checkpoint dropped — so the diagnosis neither double-counts nor misses the run that triggered it.

**Placement.** Both levers sit above `convergence_diagnosis.py` and reuse the split executor and `scope_out.py` actuators — they add no new structural-remedy primitive, only a second actuation entry point for `FORK_LOCALIZED` and a read-only projection of the existing diagnosis into the report. The dependency direction is unchanged: the CLI/report layer imports the diagnostic leaf, never the reverse.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — Official argparse reference covering mutually exclusive groups (for `--apply-split` vs `--apply-scope-out`) and the `append` action (for repeated `--into` titles) that Lever 1's new flags rely on.
- [io — Core tools for working with streams: IOBase.isatty (Python docs)](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — Documents `isatty()` on stream objects, the primitive behind the TTY-confirm gate that makes `--apply-split` recommend-only on non-interactive invocations unless `-y` is passed.
- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — Standard-library JSON load/dump reference for reading the saved completeness/reconcile report sidecars and fingerprints that the zero-Claude convergence diagnosis and report section render from.
- [How to monkeypatch/mock modules and environments (pytest docs)](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — pytest's monkeypatch guide for overriding the invoker seam and asserting zero-Claude behavior in the new `test_convergence_cmd.py` / `test_completeness_report.py` cases.
- [How to mark test functions with attributes (pytest markers)](https://docs.pytest.org/en/stable/how-to/mark.html) — Reference for `@pytest.mark` usage needed to add the `@pytest.mark.integration` end-to-end tests driving `main([...])` for each lever.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Actuating the `FORK_STRUCTURAL` arm — re-seed/re-decompose stays recommend-only; there is no companion `--apply` flag, since restarting a plan is not a single deterministic mutation.
- Changing `FORK_SCOPE_OUT` actuation — `--apply-scope-out` and `scope_out.py` are reused unchanged; this plan only adds the sibling split arm.
- Modifying `convergence_diagnosis.py`'s inputs, fork classification, or trend heuristics — both levers sit above the diagnostic and consume its existing verdict as-is.
- Introducing a new split executor or structural-remedy primitive — `_actuate_split` dispatches the existing split path so re-split semantics stay single-sourced.
- Surfacing the convergence section in reconcile or other report-producing commands — the in-report projection lands only in the completeness report.

## Risks

- **Refactoring the staleness verdict changes behavior (step 1).** Hoisting the fingerprint-staleness check out of `_actuate_scope_out` could subtly alter when scope-out short-circuits. Severity: high — a regression here silently actuates against stale fingerprints. Mitigation: characterization tests pin `_actuate_scope_out`'s current staleness behavior before the extraction and must pass unchanged after.
- **`_actuate_split` actuating against stale fingerprints.** The new split arm must short-circuit on a stale saved report just as scope-out does; if it skips the shared staleness helper, it re-splits a step whose code no longer matches the fingerprints the diagnosis was computed from. Severity: high. Mitigation: both actuators consume the same step-1 helper, so the short-circuit is single-sourced; covered by a stale-report test for the split arm.
- **`--apply-split` and `--apply-scope-out` both passed.** Two fork actuators in one invocation would contradict the diagnostic's single-verdict classification. Severity: medium. Mitigation: the flags are mutually exclusive (argparse group), rejected before dispatch.
- **Report run-counting off by one (step 4).** Wiring the section into `_persist_and_present_report` must count the current run exactly once — the diagnosis is computed before `build_report_md` from loaded history plus the in-memory current run with this invocation's checkpoint dropped; a double-count or miss skews the recurrence/no-shrinkage trend and mis-fires or suppresses the spinning verdict. Severity: medium. Mitigation: step 4's tests assert the current run is counted once across the audit-only and iterate paths.
- **Known limit: historical iterate checkpoints stay double-counted (step 4).** The count-once invariant covers only *this* invocation's own pre-apply checkpoint; `load_report_history` still returns both the checkpoint and the final sidecar for every *prior* iterate run (both `kind="completeness"`), so the shared trend baseline is uneven — each past iterate run counts twice and each audit-only run once, and the standalone `plan-tool convergence` command reads the same skewed history. A past invocation's checkpoint (pre-apply findings) then final (post-apply, fewer findings) can even read as an artificial recurrence-then-shrink. Severity: low — a residual, not a regression this plan introduces. Accepted residual: deduping checkpoint+final per invocation belongs in `load_report_history`, which lives in `convergence_diagnosis.py` — out of scope here (see `## Out of scope`); this plan counts the current run once and leaves the historical dedup to a dedicated diagnostic change.
- **In-report section adding noise to healthy loops.** A section that renders on every run would clutter reports for loops that are converging. Severity: low. Mitigation: the pure renderer is gated to emit only on a spinning verdict, and step 4 scopes that verdict to the completeness series so a spinning reconcile series alone never renders the section.
- **Unresolved gap: the split arm inherits the split executor's own safety limits.** `_actuate_split` dispatches the existing split path, so any downstream-blocked / unsafe-split cases it cannot handle surface as recommend-only outcomes rather than mutations — acceptable, since this plan adds an actuation entry point, not new split semantics.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool convergence <name> --apply-split` on a spinning `FORK_LOCALIZED` verdict dispatches the existing split executor and exits 0; a `test_convergence_cmd.py` case asserts exactly one mutating `split_step` call fires on the actuated path while a refusal path mutates nothing, and no new split executor is introduced.
- `plan-tool convergence <name>` with no apply flag performs no mutation and spends no Claude — the invoker seam is never called; asserted by a zero-Claude `test_convergence_cmd.py` case under the autouse real-backend gate.
- Passing both `--apply-split` and `--apply-scope-out` in one invocation is rejected before dispatch (argparse mutually-exclusive group); a `test_convergence_cmd.py` case asserts the parse error.
- `--apply-split` is recommend-only on a non-interactive invocation unless `-y` is passed: without a TTY and without `-y` it emits a recommendation and mutates nothing; with `-y` it actuates. Both branches asserted in `test_convergence_cmd.py`.
- Both `_actuate_scope_out` and `_actuate_split` short-circuit identically on a stale saved report via the shared step-1 helper; a stale-fingerprint `test_convergence_cmd.py` case asserts each actuator declines to mutate.
- The step-1 extraction is behavior-preserving: the characterization tests pinning `_actuate_scope_out`'s pre-refactor staleness behavior pass unchanged after the helper is hoisted.
- `plan-tool convergence <name> --apply-split` exits 0 on every completed outcome (applied, recommend-only, no-fork) and non-zero only when the split executor fails mid-actuation; asserted by exit-code cases in `test_convergence_cmd.py`.
- The `completeness_report.py` convergence-section renderer emits output only for a spinning verdict and returns empty for a converging/healthy verdict, doing no I/O and spending no Claude, and its section heading names the completeness audit/apply loop rather than a plan-wide verdict; asserted by pure-renderer cases in `test_completeness_report.py`.
- A completeness audit whose completeness loop is spinning renders the convergence section in its report; the diagnosis is computed over the completeness series before `build_report_md` from loaded history plus the in-memory current run with this invocation's checkpoint dropped, counting the current run exactly once on both the audit-only and iterate paths; a spinning `detail-reconcile` / `run-reconcile` series alone does not render the section; asserted by `test_completeness_cmd.py` cases that check the run is neither double-counted nor missed and that a reconcile-only spin stays silent.
- Step 5 leaves no stale references: `BACKLOG #57` and the Quality/accuracy roll-up are reconciled, and `docs/cli/convergence.md` documents `--apply-split`; verifiable by grepping the docs for the new flag and the resolved backlog entry.

## Deferred

- None yet — nothing has been postponed during implementation; permanent exclusions live in `## Out of scope`. Populate as items surface.
