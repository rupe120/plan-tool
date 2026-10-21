> **Replaced**: this file has been superseded by `docs/implementation-plans/2-completeness-next-steps-blocking-set.md`.
> Preserved here for history; do not edit.

## Overview

After any `completeness-audit`, every message that tells the operator what to close and whether to move on is derived from one blocking set: the audit's own blocking verdict (`compute_conceptual_bar_blocking_ids` with the sampled `audit_stage`, surfaced as `outcome.conceptual_bar_blocking_ids`). A blocking gap is named everywhere and ends the command list with the re-audit to run after the session-directed edit, with no stage transition offered; an advisory gap is listed but holds back no stage. The finalize gate's contract (`--json` `has_blocking_findings`, `--fail-on-findings`, exit codes) does not change.

## Problem statement

Four readers decide on their own what to tell the operator after an audit: `completeness_report.suggested_next_steps` (saved report prose), `suggested_next_step_commands` (console list, whose empty result every caller turns into `next_stage_command`), `console_summary`, and `_render_grouped_report`'s next-steps block in `cli/completeness_phases.py`. Because none of them reads the finalize gate's blocking set, they can say "no plan-level gaps remain" and offer the next stage while a blocking gap is open. The originating symptom (Integration, 2026-10-10): a bare plan with one open high correctness gap printed a `detail` transition instead of the re-audit. The jira lane says "no gaps left — export" in the same situation, and the `detail` / `split` / `merge` parents in `cli/authoring.py` append `reconcile-plan` and `run` after the tail's commands even when the tail names a re-audit. A parked direct fix (`fix/audit-next-steps-open-correctness`) failed across four review rounds, each finding a new reader or edge case, and its fourth round failed by deriving the stage from `bundle_status.is_bare`, disagreeing with `derive_audit_stage` on step-less and partially detailed plans.

## Architecture

**One blocking set, computed once.** The set is computed where the finalize gate already computes it — `compute_conceptual_bar_blocking_ids` with the sampled `audit_stage`, surfaced as `outcome.conceptual_bar_blocking_ids` — and passed to every reader rather than re-derived. It includes blocking deterministic findings that no apply verb closes (self-consistency such as a missing `intent:`, purity coverage, data contract, lessons coverage, detail body). The stage bar stays in `is_blocking_finding` and the stage stays `derive_audit_stage`'s; no second blocking predicate is introduced anywhere.

**Readers consume, never decide.** `completeness_report.suggested_next_steps`, `suggested_next_step_commands`, `console_summary`, and `_render_grouped_report` receive the set. A non-empty set names each blocking gap and ends with the re-audit command (no stage transition); an empty set with advisory gaps lists them and offers the next stage. In the jira lane a blocking gap yields `completeness-audit <plan> --grade jira` (no `--iterate`).

**Parents respect the tail.** The `detail` / `split` / `merge` parents in `cli/authoring.py` omit `run` from the merged next-steps block while the tail names a re-audit.

**Incomplete audits.** When the canonical set is unavailable (`audit_incomplete`: budget-limited or unqualified), readers need a defined answer for that case rather than a re-derived one.

The only reorganization allowed is moving the blocking computation so readers receive it; if a reader cannot receive it without changing the finalize gate's contract, the work stops and surfaces to the user.

## Out of scope

- Changing what blocks: the stage bar stays in `is_blocking_finding`, and the
  stage stays `derive_audit_stage`'s.
- An apply command for conceptual gaps (#367 stays: they close by a
  session-directed edit).
- A second blocking predicate anywhere. Deliberately not: the parked direct
  fix's fourth review round failed exactly there, deriving the stage from
  `bundle_status.is_bare` and disagreeing with `derive_audit_stage` on
  step-less and partially detailed plans.
- Relabeling the loop-stop `open_findings=` banner beyond saying it counts
  deterministic findings.

## Risks

- The canonical set is unavailable on a budget-limited or unqualified audit
  (`audit_incomplete`). The readers need a defined answer for that case, not a
  re-derived one.
- Four parked review rounds found a new reader or edge case each time; a reader
  missed by the plan reintroduces the original "no gaps remain" message.

## Testing

- One table-driven test over audit stage (step-less, bare, partially
  detailed, detailed) × grade (run, jira) × finding kind (blocking and
  advisory correctness, completeness, deterministic) asserts the four readers
  agree, and that a stage transition appears only when the blocking set is
  empty.
- The Integration case — bare plan, one open high correctness gap — prints the
  re-audit and no `detail` transition.
- An info/nit-only tail offers the next stage.
- Each assertion verified red by mutation.

## Acceptance criteria

After any `completeness-audit`, every message that tells the operator what to
close and whether to move on agrees with the audit's own blocking verdict. A
blocking gap is named everywhere and ends the command list with the re-audit to
run after the session-directed edit, with no stage transition offered. An
advisory gap is listed but holds back no stage. No surface says "no plan-level
gaps remain" while a blocking gap is open.

- The jira lane: name `completeness-audit <plan> --grade jira` (no
  `--iterate`) while a blocking gap is open, not "no gaps left — export".
- The `detail` / `split` / `merge` parents in `cli/authoring.py`, which
  append `reconcile-plan` and `run` after the tail's commands: no `run`
  while the tail names a re-audit.

- The `detail` / `split` / `merge` merged next-steps block omits `run` while
  a blocking gap is open.

Moving the blocking computation so the readers receive it rather than
re-deriving it. No change to the finalize gate's contract (`--json`
`has_blocking_findings`, `--fail-on-findings`, exit codes).

When this plan ships, remove BACKLOG #479 and its roll-up line under
`gate-signal`. Authoring the plan alone marks #479 plan-authored; it does not
remove it.
