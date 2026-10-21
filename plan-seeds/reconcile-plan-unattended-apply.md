# Plan seed: an explicit unattended-apply path for `reconcile-plan`

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/reconcile-plan-unattended-apply.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

Source: BACKLOG #69 → promoted to IPPT-13 (2026-09-27). This seed carries
that entry's scope contract; the ticket holds the working brief.

## Outcome

`reconcile-plan` gains an explicit, opt-in flag that converges apply-eligible
reconcile findings without a human in the loop — parity with
`completeness-audit --iterate`'s auto-apply, currently unavailable to
standalone `reconcile-plan`, whose only apply path is the TTY-gated
interactive walk.

## In scope

- `plan_tool/cli/review_cmd.py` (`cmd_review`, the `reconcile-plan` handler):
  a new opt-in flag, gated by `-y`, that runs an unattended convergence loop
  instead of only saving a report for the interactive walk.
- `plan_tool/cli/reconcile.py`: a new convergence-loop driver for this
  surface, following `_iterate_reconcile_loop`'s shape (apply → re-audit →
  repeat, stop-reason reporting).
- `docs/cli/`, regenerated for the new flag.

## Out of scope / Non-goals

- Changing `reconcile-plan`'s default (no-flag) interactive behavior.
- Any change to `run --mode reconcile` or to `_iterate_reconcile_loop` itself.
  **Do not reuse that function directly** — it is bound to a single `step_id`
  and drives `run_step`, and does not fit `reconcile-plan`'s whole-plan /
  `--step` / `--all` scope. Build a new driver that follows its shape.
- Auto-apply with no explicit opt-in. An unattended plan↔code rebase is
  higher-stakes than completeness's auto-apply; the interactive walk stays
  the default.

## Allowed behavior changes

None beyond the Outcome: a new opt-in flag exists and converges apply-eligible
findings when passed. `reconcile-plan`'s behavior with no flag is unchanged.

## Allowed reorganization

None beyond adding the new driver alongside `_iterate_reconcile_loop` in
`plan_tool/cli/reconcile.py`.

## Verification

- A fixture plan with apply-eligible reconcile findings converges to no
  remaining eligible findings under the new flag, with no TTY.
- `reconcile-plan` with no flag behaves exactly as before (existing tests
  covering its interactive path stay green).
- `uv run pytest tests/test_review.py tests/cli/test_review_cmd.py -q` is
  green.

## Stop / defer

Stop and surface to the user if the convergence scope (`--step` vs. `--all`
vs. whole-plan) or the stop/budget criteria can't be settled from precedent
during decomposition — these are open design questions for this seed's
`create`/`detail` steps to resolve, not something to guess at.

## References

- `plan_tool/cli/review_cmd.py` (`cmd_review`, the `reconcile-plan` handler) —
  where the new opt-in flag and driver call go.
- `plan_tool/cli/reconcile.py` (`_iterate_reconcile_loop`) — the shape to
  follow, not reuse; it is bound to a single `step_id` and drives
  `run --mode reconcile`.
- `docs/TRACKING.md` § "Jira board" — the review-and-merge workflow this
  ticket's `Route:` line points to.

## Backlog reconciliation

`BACKLOG.md`'s `#69` entry is already a promotion stub pointing at IPPT-13.
No further backlog edit is required when this plan ships.
