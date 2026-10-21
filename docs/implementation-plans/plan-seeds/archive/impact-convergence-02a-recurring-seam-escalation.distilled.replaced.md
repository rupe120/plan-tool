> **Replaced**: this file was superseded by `2-escalate-recurring-seams.md`, itself
> archived 2026-08-02 to `docs/implementation-plans/archive/`. The live successor is
> BACKLOG #158's re-seed pair (`plan-seeds/impact-recurrence-01-classifier.md`, `-02-loop-stop.md`).
> Preserved here for history; do not edit.

## Overview

Route recurring high-impact seam findings in the live completeness/iterate loop to a structural recommendation instead of continuing audit passes. The loop will reuse the existing history diagnosis path, stop with a new `should_continue` reason code, and print a recommend-only `plan-tool split …` or `plan-tool scope-out …` command; it will not mutate plan structure or bypass existing `--apply`/TTY gates.

## Problem statement

The live loop currently decides whether to continue from the current pass's findings through `plan_tool/convergence.py:should_continue` and `max_stall_rounds`, without consulting cross-run report history. This permits open audit→apply→audit loops to rediscover an un-applied high-impact seam, as in the `security-check-command` `--step`/`--reconcile` contract seam that appeared on passes 2, 11, and 13 of 13, instead of surfacing the needed re-split or scope-out remedy.

## Architecture

Use `plan_tool/convergence_diagnosis.py` as the single source of recurrence logic: the live loop calls `load_report_history(plan_path)`, `diagnose_convergence(...)`, and `classify_fork(diagnosis)` rather than introducing a second heuristic. This extends the existing after-the-fact `plan-tool convergence` path into the live stop decision while preserving that command's behavior.

Add one `plan_tool/convergence.py:should_continue` reason code, such as `"structural"`, for an `impact=high` finding recurring `≥N` passes without count-shrink. `cli/completeness_cmd.py` and `cli/reconcile.py` consult that result at their live-loop stop points and render a recommend-only structural pointer according to `FORK_LOCALIZED` / `FORK_SCOPE_OUT` / `FORK_STRUCTURAL` using the existing `Next steps:` convention. High-impact status reuses #152's `is_blocking_impact`; structural mutation remains exclusively behind `scope_out.py:scope_out_step` and `launcher.py:escalate_to_split` `--apply`/TTY-confirm gates.

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

## Acceptance criteria

- The live iterate loop consults report history through `load_report_history(plan_path)`, `diagnose_convergence(...)`, and `classify_fork(diagnosis)` from `plan_tool/convergence_diagnosis.py`, with no new recurrence heuristic.
- For an `impact=high` finding recurring `≥N` passes without count-shrink, `plan_tool/convergence.py:should_continue` returns the structural reason, the loop stops before the pass cap, and `cli/completeness_cmd.py` or `cli/reconcile.py` prints a recommend-only `plan-tool split` or `plan-tool scope-out` pointer.
- A non-recurring high-impact finding continues iterating normally, and all existing `should_continue` reason strings remain unchanged.
- The live loop does not auto-narrow or auto-split; `scope_out.py:scope_out_step` and `launcher.py:escalate_to_split` remain the mutation paths guarded by `--apply`/TTY confirmation.
- `plan-tool convergence` behavior does not regress.
- `BACKLOG.md` #153 is marked shipped/removed and the overlap with #116/#129 is reconciled in one place.
