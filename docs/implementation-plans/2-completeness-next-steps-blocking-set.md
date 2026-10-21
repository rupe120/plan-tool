---
format_version: 1
title: Completeness Next Steps Blocking Set
intent: After any `completeness-audit`, every message that tells the operator what
  to close and whether to move on agrees with the audit's own blocking verdict. A
  blocking gap is named everywhere and ends the command list with the re-audit to
  run after the session-directed edit, with no stage transition offered. An advisory
  gap is listed but holds back no stage. No surface says "no plan-level gaps remain"
  while a blocking gap is open.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/completeness-next-steps-blocking-set.md
steps:
- id: 1
  title: Define the blocking verdict (set, incomplete, absent) and make the saved-report,
    console next-step, and console_summary readers, and their shared fallback next_stage_command,
    in completeness_report.py consume it
  intent: Own the blocking verdict's definition (its three states, and that only a
    completed empty set means nothing blocks), then make suggested_next_steps, suggested_next_step_commands,
    console_summary, and their shared fallback next_stage_command read it and stop
    saying 'no plan-level gaps remain' or offering the next stage unless it is an
    empty set, at run and jira grades.
  files:
  - plan_tool/completeness_report.py
  - tests/test_completeness_report.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/completeness-next-steps-blocking-set/01-define-blocking-verdict-set-incomplete.md
  status: done
- id: 2
  title: Build step 1's verdict from the finalize gate's own result and hand it to
    every next-step reader, including _render_grouped_report, without changing the
    gate's contract
  intent: Make sure the gate's own result (its deterministic arms collected as findings,
    plus outcome.conceptual_bar_blocking_ids at the sampled audit_stage) is computed
    once, read by the gate and every reader alike, and never re-derived. Every caller
    of suggested_next_steps, suggested_next_step_commands, console_summary, and next_stage_command,
    including the reused-audit path and the detail / split / merge parents, is listed
    with the verdict it passes; the loop-stop open_findings= banner is listed as deliberately
    not a reader, since it reports the loop count, not a next step. Once every caller
    passes a verdict, flip step 1's two-phase default so an omitted verdict reads
    as absent.
  files:
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/completeness_report.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_completeness_report.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the verdict's definition and the reader signatures that accept it
  detail: docs/implementation-plans/plan-details/completeness-next-steps-blocking-set/02-build-step-verdict-finalize-gate-own.md
  status: done
- id: 3
  title: Leave out run and jira in the detail / split / merge merged next-steps block
    unless the completeness tail's blocking verdict is an empty set
  intent: Keep the detail, split, and merge commands from offering run or jira unless
    the tail's blocking verdict is an empty set, reading that structured verdict rather
    than the printed command text.
  files:
  - plan_tool/cli/authoring.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: the completeness tail result carries the blocking verdict
  detail: docs/implementation-plans/plan-details/completeness-next-steps-blocking-set/03-leave-out-run-detail-split-merge-merged.md
  status: done
- id: 4
  title: Add one table-driven test showing all four readers agree across stage, grade,
    finding kind, and verdict state, plus the detail / split / merge parent cases,
    the Integration bare-plan case, and the advisory-only case
  intent: Prove the four readers agree everywhere and the detail, split, and merge
    parents follow the tail, so a reader missed later fails loudly and the original
    'no gaps remain' message cannot come back unnoticed.
  files:
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/completeness-next-steps-blocking-set/04-one-table-driven-test-showing-all-four.md
  status: done
- id: 5
  title: 'Document the one-blocking-set next-step rule in the audit how-to and remove
    BACKLOG #479 and its gate-signal roll-up line'
  intent: Make the operator contract match what now ships, and close the backlog entry
    the plan came from.
  files:
  - docs/how-to/pipeline/audit.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/completeness-next-steps-blocking-set/05-document-one-blocking-set-next-step.md
  status: done
---
# Completeness Next Steps Blocking Set

## Overview

After any `completeness-audit`, every message that tells the operator what to close and whether to move on is derived from one blocking verdict: the finalize gate's own result, made structured. Today the gate (`_completeness_has_blocking_findings`) returns a bool from its deterministic arms plus the conceptual ids in `outcome.conceptual_bar_blocking_ids` (`compute_conceptual_bar_blocking_ids`, conceptual sources only, at the sampled `audit_stage`). A blocking gap is named everywhere and ends the command list with the re-audit to run after the session-directed edit, with no stage transition offered; an advisory gap is listed but holds back no stage. The finalize gate's contract (`--json` `has_blocking_findings`, `--fail-on-findings`, exit codes) does not change.

## Problem statement

Four readers decide on their own what to tell the operator after an audit: `completeness_report.suggested_next_steps` (saved report prose), `suggested_next_step_commands` (console list, whose empty result every caller turns into `next_stage_command`), `console_summary`, and `_render_grouped_report`'s next-steps block in `cli/completeness_phases.py`. Because none of them reads the finalize gate's blocking set, they can say "no plan-level gaps remain" and offer the next stage while a blocking gap is open. The originating symptom (Integration, 2026-10-10): a bare plan with one open high correctness gap printed a `detail` transition instead of the re-audit. The jira lane says "no gaps left — export" in the same situation, and the `detail` / `split` / `merge` parents in `cli/authoring.py` append `reconcile-plan` and `run` after the tail's commands even when the tail names a re-audit. A parked direct fix (`fix/audit-next-steps-open-correctness`) failed across four review rounds, each finding a new reader or edge case, and its fourth round failed by deriving the stage from `bundle_status.is_bare`, disagreeing with `derive_audit_stage` on step-less and partially detailed plans.

## Architecture

**One blocking verdict, computed once.** `compute_conceptual_bar_blocking_ids` covers conceptual sources only; the gate's deterministic arms (self-consistency such as a missing `intent:`, purity coverage, data contract, lessons coverage, detail body, and the rest it checks) are separate boolean tests. The plan collects those arms as findings in one computation that the gate reads for its bool and every reader reads for its message, joined with the conceptual ids. The gate's bool, `--json` `has_blocking_findings`, and exit codes are unchanged. The stage bar stays in `is_blocking_finding` and the stage stays `derive_audit_stage`'s; no second blocking predicate is introduced anywhere.

**One verdict, three states.** Every reader receives one blocking verdict, which is exactly one of: a **set** (the gate established its result; the set may be empty), **incomplete** (the gate could not certify its result; it still carries every blocking conceptual id and deterministic finding it computed), or **absent** (the caller passed no verdict and no ids; the safe default for an unwired or future caller). Readers test the state before testing emptiness. An `incomplete` verdict also carries an `untrusted_cause`, set once where the verdict is built (`cli/completeness_cmd.py`) and read only by the shared next-command function: `transient` (a cut-short iterate stop such as `deadline_exceeded`, `max_iterations`, `no_progress`; a re-audit continues it) or `persistent` (unqualified or budget-limited coverage, `no-qualified-current-evidence`, a hand-apply stop with nothing left to name, or deferrals awaiting a person; a re-audit of unchanged text reproduces it). The absent default lands in two phases so every step stays green under `run`'s full-suite gate: step 1 adds the verdict with an unset default that keeps today's output, and step 2 flips that default to absent once every caller passes a verdict (decided 2026-10-10, after step 1's first run failed six step-2 tests).

**Trust follows the gate.** The verdict is a trusted `set` exactly when finalize itself treats the conceptual verdict as established: coverage qualifies (`audit_incomplete` is false) and the result is not `no-qualified-current-evidence`. A non-empty trusted set names its gaps whatever the stop reason, including a hand-apply stop. A stage is offered only when the trusted set is empty, `_completeness_finalize_is_clean` holds, and the result is not `awaiting-human-action`; an empty set that fails any of these is `incomplete`. The set and `incomplete` differ only in the stage: `next_step_gaps` treats the ids of both as gaps to close, so a HIGH correctness gap from a cut-short run reads "fix these first", never "advisory". Amended 2026-10-10 after implementation review round 3: the earlier model dropped the ids of an `incomplete` verdict and exempted every hand-apply stop from trust.

**Readers consume, never decide.** `completeness_report.suggested_next_steps`, `suggested_next_step_commands`, `console_summary`, and `_render_grouped_report` receive the verdict. A non-empty set, or an `incomplete` verdict that kept ids, names each blocking gap and ends with the re-audit command (no stage transition); an empty set with advisory gaps lists them and offers the next stage. Incomplete and absent never say "no gaps remain". A verdict names the blocking deterministic findings the gate found, since those checks are certain even when the conceptual audit is not, and a deterministic blocker already remedied by another bullet in the same reader (a structural, self-consistency, purity, `detail`, or diagnostic bullet) is not listed a second time. The advisory wording ("hold back no stage") follows only advisory gap rows, never a required step (BLOCKED split, code-drift reconcile, concept-link assignment, diagnostic remedy). Every reader call today runs inside the finalize or report-writing path, including a reused audit (`_resolve_audit_reuse` feeds the reused findings back through the same finalize path, so it passes a set); `list --status` calls no reader. Every re-audit a reader names is built by the one `_reaudit_command` and carries the audit's grade: `completeness-audit <plan> --iterate` in the run lane, `completeness-audit <plan> --grade jira` with no `--iterate` in the jira lane. Reasons to re-audit (open blocking count, concept-link assignment, unreached findings) merge into that one row's description. A `persistent` cause is not answered with a bare re-audit: the one next step tells the operator to triage the saved report's findings, correct them in a session-directed edit, commit, then re-audit the changed snapshot; a `transient` cause keeps the plain `--iterate` re-audit.

**Parents respect the tail.** The `detail` / `split` / `merge` parents in `cli/authoring.py` receive the tail's structured verdict and omit the stage transitions (`run`, and `jira` in the `detail` block) from the merged next-steps block unless it is an empty set. They never parse the tail's printed commands.

The only reorganization allowed is moving the blocking computation so readers receive it; if a reader cannot receive it without changing the finalize gate's contract, the work stops and surfaces to the user.

## References

- [pytest: How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Covers `@pytest.mark.parametrize` and stacked parametrization; open it when building the table-driven stage × grade × finding-kind test that checks the four readers agree.
- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — The primary reference for pytest marks, `pytest.param` ids, `monkeypatch`, and `capsys`; useful for capturing console next-steps output and stubbing the invoker seam.
- [Python dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Documents frozen dataclasses and field defaults; consult it when shaping the structured blocking verdict and passing it to the readers without changing their existing contracts.
- [Python argparse — Parser for command-line options](https://docs.python.org/3/library/argparse.html) — The reference for the CLI flags this plan must leave unchanged (`--grade jira`, `--iterate`, `--fail-on-findings`, `--json`) and for how the parent commands are wired.
- [Python json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Covers serialization rules; open it to confirm the `--json` `has_blocking_findings` payload stays byte-compatible while the readers change.
- [Python sys.exit and exit status](https://docs.python.org/3/library/sys.html#sys.exit) — Defines how a CLI exit status is set; use it to check that exit codes, including the `--fail-on-findings` flip, stay unchanged.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing what blocks: the stage bar stays in `is_blocking_finding`, and the
  stage stays `derive_audit_stage`'s.
- An apply command for conceptual gaps (#367 stays: they close by a
  session-directed edit).
- A second blocking predicate anywhere. Deliberately not: the parked direct
  fix's fourth review round failed exactly there, deriving the stage from
  `bundle_status.is_bare` and disagreeing with `derive_audit_stage` on
  step-less and partially detailed plans.
- The loop-stop `open_findings=` banner. It is left untouched; it is not a
  next-step reader.

## Risks

- An empty set means "nothing blocks" only when the audit completed; a reader
  that tests emptiness before the incomplete or absent state reintroduces "no
  gaps remain" on exactly those audits.
- Four parked review rounds found a new reader or edge case each time; a reader
  missed by the plan reintroduces the original "no gaps remain" message. Step 2's
  caller list is the guard.

## Testing

- One table-driven test over audit stage (step-less, bare, partially
  detailed, detailed) × grade (run, jira) × finding kind (blocking and
  advisory correctness, completeness, deterministic) × verdict state (set,
  incomplete, absent) asserts the four readers and their shared fallback
  `next_stage_command`
  agree, and that a stage transition appears only when the blocking set is
  empty.
- The Integration case — bare plan, one open high correctness gap — prints the
  re-audit and no `detail` transition.
- An info/nit-only tail offers the next stage.
- The verdict state (set, incomplete, absent) is an axis of the table: incomplete
  and absent offer only the fresh re-audit in every reader and parent, with no
  stage transition.
- For each of the `detail`, `split`, and `merge` parents: a blocking tail
  leaves `run` (and `jira` in `detail`) out of the merged block, and an
  advisory-only tail keeps them. A tail that never ran (`--no-completeness`)
  or failed is absent: neither is offered.
- An incomplete verdict that also carries a blocking deterministic finding
  names that finding and still offers only the re-audit.
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
- The `detail` / `split` / `merge` merged next-steps block omits `run` (and `jira` in `detail`) unless
  the tail's verdict is an empty set, and keeps it after an advisory-only tail.
- An incomplete or absent verdict offers only the one re-audit in every reader
  and parent (hand triage first when the cause is persistent), at the audit's grade (`--grade jira`, no `--iterate`, in the jira
  lane).
- Every caller of the next-step readers, including the parents and callers with
  no audit outcome, is listed in step 2 with the verdict it passes.
- The finalize gate's contract is unchanged (`--json` `has_blocking_findings`,
  `--fail-on-findings`, exit codes).

When this plan ships, remove BACKLOG #479 and its roll-up line under
`gate-signal`. Authoring the plan alone marks #479 plan-authored; it does not
remove it.

## Deferred

_(none yet)_ — nothing has been postponed; permanent exclusions live under
`## Out of scope`. Add items here only if implementation drops work that may
return.
