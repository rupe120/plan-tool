---
title: Escalate Recurring Seams
status: superseded
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Move the live completeness history snapshot into convergence diagnosis
  files:
  - plan_tool/cli/completeness_phases.py
  - plan_tool/convergence_diagnosis.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/escalate-recurring-seams/01-move-live-completeness-history-snapshot.md
  status: current
- id: 2
  title: Add a high-impact structural stop reason
  files:
  - plan_tool/convergence.py
  - plan_tool/convergence_diagnosis.py
  - tests/cli/test_convergence_cmd.py
  - tests/test_convergence.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/escalate-recurring-seams/02-high-impact-structural-stop-reason.md
- id: 3
  title: Stop completeness iteration and show the structural recommendation
  files:
  - plan_tool/cli/completeness_cmd.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/escalate-recurring-seams/03-stop-completeness-iteration-show.md
- id: 4
  title: Stop reconcile iteration and show the structural recommendation
  files:
  - plan_tool/cli/reconcile.py
  - tests/test_cli.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/escalate-recurring-seams/04-stop-reconcile-iteration-show.md
- id: 5
  title: 'Remove shipped backlog item #153 and update related convergence notes'
  files:
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/escalate-recurring-seams/05-remove-shipped-backlog-item-153-update.md
---
# Escalate Recurring Seams

> **Superseded; do not execute.** This plan assumes that high-impact recurrence
> can reuse the severity/decomposition classifier without changing that
> classifier's meaning. The replacement is `BACKLOG.md` #158, which owns a
> separate impact-recurrence classifier sharing history/matching infrastructure.
> #116/#129 continue to own the existing severity/decomposition classifier.

## Overview

Route recurring, high-impact seam findings in the live completeness/iterate loop to a structural recommendation instead of continuing audit passes. The loop reuses the existing convergence-history diagnosis path, stops with a new `should_continue` structural reason, and prints the diagnosis-selected recommend-only split, scope-out, or re-seed command. It does not mutate plan structure or bypass existing `--apply` and TTY confirmation gates.

## Problem statement

The live loop currently decides whether to continue from the current pass's findings through `plan_tool/convergence.py:should_continue` and `max_stall_rounds`, without consulting cross-run report history. This permits open audit→apply→audit loops to rediscover an un-applied high-impact seam, as in the `security-check-command` `--step`/`--reconcile` contract seam that appeared on passes 2, 11, and 13 of 13, instead of surfacing the needed re-split or scope-out remedy.

## Architecture

Use `plan_tool/convergence_diagnosis.py` as the single source of recurrence logic: the live loop calls `load_report_history(plan_path)`, `diagnose_convergence(...)`, and `classify_fork(diagnosis)` rather than introducing a second heuristic. This extends the existing after-the-fact `plan-tool convergence` path into the live stop decision while preserving that command's behavior.

Add one `plan_tool/convergence.py:should_continue` reason code, such as `"structural"`, for an `impact=high` finding recurring `≥N` passes without count-shrink. The live caller filters report history to its active completeness series or active reconcile kind/step before diagnosis. For this new structural-stop predicate only, recurrence eligibility admits report-eligible high-impact findings via `is_blocking_impact`, including `plan-completeness` high-impact `nit`/`info`; existing severity-only diagnostic verdicts and their `APPLY_ELIGIBLE_SOURCES` behavior remain unchanged. `cli/completeness_cmd.py` and `cli/reconcile.py` render the existing command selected for `FORK_LOCALIZED` / `FORK_SCOPE_OUT` / `FORK_STRUCTURAL`.

## Input

The live loop consumes persisted report history through `load_report_history(plan_path)` and the diagnosis/classification contract in `plan_tool/convergence_diagnosis.py`: `diagnose_convergence(...)` determines recurrence and count-shrink, while `classify_fork(diagnosis)` selects `FORK_LOCALIZED`, `FORK_SCOPE_OUT`, or `FORK_STRUCTURAL`. It also relies on `is_blocking_impact` for the existing high-impact definition; the change must preserve the existing `plan-tool convergence` behavior and all current `should_continue` reason strings.

## References

- [Python dataclasses — Python 3.13 documentation](https://docs.python.org/3.13/library/dataclasses.html) — Covers safe evolution of the frozen and mutable state models used by convergence and diagnosis logic.
- [pathlib — Python 3.13 documentation](https://docs.python.org/3.13/library/pathlib.html) — Documents Path-based filesystem access needed when loading persisted report history from a plan path.
- [sys — Python 3.13 documentation](https://docs.python.org/3.13/library/sys.html) — Explains standard streams and interactive execution context relevant to preserving the CLI’s TTY-gated recommendation behavior.
- [pytest monkeypatch documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Shows how to isolate history-loading and CLI seams in synthetic multi-pass tests without persistent side effects.
- [pytest capturing output documentation](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — Covers assertions against the recommend-only Next steps output emitted by completeness and reconcile loops.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Automatically mutating plan structure from the live loop — structural mutation remains behind `scope_out.py:scope_out_step` and `launcher.py:escalate_to_split` `--apply`/TTY-confirm gates.
- Changing the classification semantics or silently re-implementing recurrence logic — overlap with #116 and #129 is reconciled in `convergence_diagnosis.py`.

## Risks

- Duplicating recurrence logic outside `convergence_diagnosis.py` would create conflicting behavior; mitigate by reusing `load_report_history(plan_path)`, `diagnose_convergence(...)`, and `classify_fork(diagnosis)`.
- Changing existing `should_continue` reason strings would break asserted test contracts; retain every existing reason string and add only the new structural reason.
- A live-loop recommendation could accidentally mutate plan structure; retain the existing `scope_out.py:scope_out_step` and `launcher.py:escalate_to_split` `--apply`/TTY-confirm gates and make the loop recommend only.
- Recurrence tuning may overlap #116 and #129; reconcile overlap in one place rather than changing classification semantics or silently re-implementing them.

## Testing

- Add a synthetic multi-pass history test showing that a recurring high-impact seam stops with the structural reason and prints the recommend-only pointer.
- Verify that a non-recurring high-impact finding continues iterating normally.
- Verify that no structure mutation is auto-applied.
- Keep the `plan-tool convergence` command's behavior covered against regression.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- The live iterate loop consults report history through `load_report_history(plan_path)`, `diagnose_convergence(...)`, and `classify_fork(diagnosis)` from `plan_tool/convergence_diagnosis.py`, with no new recurrence heuristic.
- For an `impact=high` finding recurring `≥N` passes without count-shrink, including a high-impact `nit`/`info`, `plan_tool/convergence.py:should_continue` returns the structural reason and the loop prints the diagnosis-selected split, scope-out, or re-seed pointer.
- A non-recurring high-impact finding continues iterating normally, and all existing `should_continue` reason strings remain unchanged.
- The live loop does not auto-narrow or auto-split; `scope_out.py:scope_out_step` and `launcher.py:escalate_to_split` remain the mutation paths guarded by `--apply`/TTY confirmation.
- `plan-tool convergence` behavior does not regress.
- `BACKLOG.md` #153 is marked shipped/removed and the overlap with #116/#129 is reconciled in one place.

## Deferred

- Broader recurrence-threshold tuning — defer to the existing #116/#129 convergence work because this plan reuses the current diagnosis semantics.
