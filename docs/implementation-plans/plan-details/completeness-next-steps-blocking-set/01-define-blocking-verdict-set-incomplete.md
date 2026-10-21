# Step 1 — Define the blocking verdict and make the three completeness_report.py readers consume it

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds one small blocking-verdict type to `plan_tool/completeness_report.py` with three states: `set`, `incomplete`, and `absent`. `next_stage_command`, `suggested_next_steps`, `suggested_next_step_commands`, and `console_summary` read it. Only a completed, empty `set` may say "no gaps remain" or offer `run` / `jira` / `detail`. Any other state names the open blocking gaps and ends with the re-audit command.

The key design decision is that the verdict carries the gate's own answer — the conceptual-bar blocking ids and the blocking deterministic findings the gate's other arms test (a missing `intent:`, purity coverage, data contract, lessons coverage, detail body) — and re-derives nothing. The observable result on green is that no reader in this file prints "no plan-level gaps remain" or a stage transition while a blocking gap is open, at run or jira grade.

## Table of Contents

- [Why](#why) — what is inconsistent today
- [Input](#input) — the gate result the verdict wraps
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — verdict shape, reader behavior, gotchas
- [Tests](#tests) — cases pinning each state and each reader
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — docs relevant to this step
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

- `next_stage_command` returns "no plan-level gaps remain — author the detail bundle…" or "no gaps left — execute…" from bundle state alone. It never sees the audit's blocking verdict.
- `suggested_next_steps` and `suggested_next_step_commands` pick their "No gaps left to close" fallback from which lists are empty. `_actionable_conceptual_gaps` demotes completeness gaps on a bare plan or at jira grade without asking whether anything blocks.
- A blocking conceptual finding can therefore sit open while the report and console offer the next stage.
- `_completeness_has_blocking_findings` in `plan_tool/cli/completeness_cmd.py` and `compute_conceptual_bar_blocking_ids` in `plan_tool/cli/completeness_phases.py` already hold the real answer. The readers do not consume it.

## Input

- **Gate result:** two parts, both built by step 2 from `_completeness_has_blocking_findings`. (1) The conceptual ids from `compute_conceptual_bar_blocking_ids(audit_recs, audit_stage=...)` / `_conceptual_bar_from_audit_recs` in `plan_tool/cli/completeness_phases.py`, which covers conceptual sources only. (2) The blocking deterministic findings the gate's other arms test, which have no conceptual id. This step only defines the carrier; it takes both as plain data.
- **Stage:** `derive_audit_stage` (`plan_tool/cli/completeness_phases.py`). It is already resolved once upstream; this step never recomputes it.
- **Existing reader inputs:** `correctness`, `advisory_conceptual`, `bundle_status`, `detail_grade`, and `qualified_result`. The verdict is an additional keyword.
- **Wiring is not this step's.** Passing the verdict from `plan_tool/cli/completeness_phases.py` call sites (`next_stage_command` at two sites, `suggested_next_step_commands`, and the finalize-time `console_summary`/`suggested_next_steps` callers) is outside this step's declared files. This step makes the readers accept and honor it; the later steps in the plan own the call sites. Until step 2 wires them, an omitted verdict keeps today's behavior (see the two-phase default below).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — add the verdict type and a constructor; add an optional keyword-only verdict parameter to the four readers; change their "no gaps" and stage-transition branches to read it.
  - `tests/test_completeness_report.py` — add the verdict cases and the table-driven four-reader agreement test; rewrite existing cases that pin the old "no gaps left" output with no verdict.

## Implementation

**Verdict shape (recommended)**
- Add a small frozen dataclass next to `_QUALIFIED_RESULT_UNSET` in `plan_tool/completeness_report.py`, for example `BlockingVerdict(state, blocking_ids, blocking_deterministic)`. `blocking_deterministic` holds the gate's blocking deterministic findings (their `source` and `severity` are enough to name them).
- `state` takes three values: `set` (the gate established its result; `blocking_ids` and `blocking_deterministic` together are the set, possibly empty), `incomplete` (the gate could not certify its result, e.g. a budget-limited, unqualified, or cut-short audit; it **keeps every blocking id and `blocking_deterministic` finding it computed**, which readers treat as gaps to close exactly as for `set`, while offering no stage), and `absent` (no verdict and no ids were supplied).
- An `incomplete` verdict carries `untrusted_cause`: `transient` (cut-short iterate stop; the plain `--iterate` re-audit continues it) or `persistent` (re-auditing unchanged text reproduces the result; the one next step is hand triage of the saved report, a session-directed edit, a commit, then the re-audit). Amended 2026-10-10 after implementation review round 3.
- `next_step_gaps` puts the ids of `set` and `incomplete` to close and the ids of `absent` nowhere; `_reaudit_command` is the one source of the re-audit command and its description, merging any extra reasons a reader passes (open blocking count, concept-link assignment, unreached findings) into one description, and only it reads `untrusted_cause`.
- Use module constants for the three state names, in the same style as the other kind tokens in this repo.
- Add a constructor that wraps the gate's own ids and deterministic findings without filtering or re-testing them.
- Only a `set` state with both `blocking_ids` and `blocking_deterministic` empty means "nothing blocks". The dataclass must not expose a predicate that treats `absent` or `incomplete` as clear.

**Reader behavior**
- **`next_stage_command`:** keep its `(command, description)` return type. When the verdict is not a completed empty set, return the re-audit command (`plan-tool completeness-audit <name>`) with a description naming the open or unknown blocking state, and no `run` / `jira` / `detail` command. Its callers in `plan_tool/cli/completeness_phases.py` (the standalone fallback and the detail-lane tails) therefore need no branch of their own.
- **`suggested_next_steps`:**
  - Never emit "No gaps left to close — …" or the bare-plan "No structural gaps left…" bullet unless the verdict is a completed empty set.
  - When blocking ids are open, name the count and close through a session-directed edit. Name each blocking deterministic finding by its source (for a missing `intent:`, say to add one), since it has no conceptual id.
  - End the list with the re-audit bullet, after the edit bullets and before nothing.
  - Keep advisory gaps listed but make them hold back no stage.
- **`suggested_next_step_commands`:**
  - When the verdict is open or not a completed empty set, end the command list with `plan-tool completeness-audit <name>`.
  - The existing "May return `[]`" contract narrows. An empty list is valid only for a completed empty set, so the standalone fallback (`next_stage_command`) is the only place a stage transition can appear.
- **`console_summary`:**
  - Add a line for the verdict state next to the existing `result` / `correctness` lines.
  - Say `blocking N gap(s)` when the set is non-empty and `blocking verdict unavailable` for `incomplete` / `absent`.
  - Never print an empty-set statement from list emptiness.
- **Both grades:** the same rule applies at run and jira grade. `_actionable_conceptual_gaps` may keep deciding which lists are *listed*, but it must not decide whether the stage transition is offered.

**Constraints and gotchas**
- **One definition of "blocking":** do not add a predicate in this file. Do not derive the stage or blocking from `bundle_status.is_bare`. The parked direct fix failed review there by disagreeing with `derive_audit_stage` on step-less and partially detailed plans.
- **Two-phase default:** the verdict parameter defaults to a private unset sentinel that means "no verdict was threaded yet", and an unset call keeps today's output exactly. Only an explicit `absent` verdict is conservative. The plan's `run` test gate needs the full suite green after every step, and the unwired callers in `plan_tool/cli/completeness_phases.py` (step 2's files) would otherwise lose every stage transition in between. Step 2 wires every caller and then maps the unset sentinel to `absent`. Decided 2026-10-10 after step 1's first run failed six step-2 tests for exactly that reason; do not make the conservative default land in this step.
- **Leaf direction:** `plan_tool/completeness_report.py` may not import `plan_tool/cli` at module level. It already imports `derive_audit_stage` lazily in one place, so keep the verdict self-contained and take ids as plain data.
- **Out of the readers' reach:** do not touch the loop-stop `open_findings=` banner.
- **Rejected alternative:** have each reader call `compute_conceptual_bar_blocking_ids` itself on the lists it already receives. That re-derives the verdict in four places and can disagree with the gate (and with `--json`'s `has_blocking_findings`).

## Tests

All in `tests/test_completeness_report.py` (no real backend; invoker not involved).

### Tests for this step

- `test_empty_set_verdict_offers_stage_transition_at_run_grade` — a `set` verdict with no blocking ids yields `plan-tool run <name>` from `next_stage_command` and the "no gaps left" bullet.
- `test_empty_set_verdict_offers_stage_transition_at_jira_grade` — same at `GRADE_JIRA`, naming `plan-tool jira <name> --grade jira`.
- `test_empty_set_verdict_on_bare_plan_offers_detail_authoring` — bare plan with an empty set still routes to the detail command.
- `test_nonempty_set_verdict_never_says_no_gaps_remain` — a `set` verdict with blocking ids: none of the readers in this file (`next_stage_command`, `suggested_next_steps`, `suggested_next_step_commands`, `console_summary`) emits "no plan-level gaps remain", "No gaps left", `plan-tool run`, `plan-tool jira`, or the detail-authoring stage command.
- `test_nonempty_set_verdict_ends_command_list_with_reaudit` — the last tuple from `suggested_next_step_commands` is the `completeness-audit` command.
- `test_absent_verdict_is_not_read_as_empty_set` — an explicit `absent` verdict offers no stage and is not treated as clear. Named for the invariant: a missing verdict must never read as "nothing blocks".
- `test_unset_verdict_keeps_todays_output_until_callers_are_wired` — a call with no verdict argument returns exactly what it returned before this step; step 2 replaces this test when it flips the default.
- `test_incomplete_verdict_is_not_read_as_empty_set` — `incomplete` behaves like `absent` for stage offers, and the summary says the verdict is unavailable.
- `test_advisory_gaps_are_listed_but_hold_back_no_stage` — advisory-only findings with a completed empty set still list the gaps and still allow the stage.
- `test_four_readers_agree_on_blocking_state` — table-driven (`pytest.mark.parametrize` over stage-adjacent bundle status × grade × verdict state × finding kind): `next_stage_command`, `suggested_next_steps`, `suggested_next_step_commands`, and `console_summary` all agree on whether a stage is offered.
- `test_verdict_wraps_gate_ids_without_refiltering` — the constructor passes the supplied ids through unchanged; guards against a second blocking predicate.
- Existing cases that call these readers with no verdict stay unchanged in this step; step 2 rewrites them when it flips the default.

**Green-before-done gate:** every case above, plus the rest of `tests/test_completeness_report.py`, must be green before this step is finished. Run the module with `uv run pytest tests/test_completeness_report.py -q`, and `tests/cli/` for the call sites that consume `next_stage_command`.

## Acceptance criteria

- `next_stage_command` returns a stage command only when the verdict is a completed, empty `set`; otherwise it returns the re-audit command.
- With a non-empty `set` verdict, none of those readers contains "no plan-level gaps remain", "No gaps left", or a `run` / `jira` / detail-authoring stage command, at run and at jira grade.
- With `absent` or `incomplete`, no reader offers a stage transition and none claims nothing blocks.
- `suggested_next_step_commands` ends with `plan-tool completeness-audit <name>` whenever blocking ids are open.
- `rg "is_bare" plan_tool/completeness_report.py` shows no new use that decides blocking or stage; the verdict is the only blocking source in the readers.
- `rg "is_blocking_finding|is_blocking\(" plan_tool/completeness_report.py` shows no new predicate added by this step.
- `--json` `has_blocking_findings`, `--fail-on-findings`, and exit codes are unchanged (no edit to `plan_tool/cli/completeness_cmd.py`).
- `tests/test_completeness_report.py` is green.

## References

- [pytest: How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — for the stage × grade × verdict-state × finding-kind agreement table.
- [Python dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — for the frozen verdict type and its field defaults.

## Applicable guardrails

- **The plan's "## Out of scope", changing what blocks:** this step reads the gate's result and does not alter `is_blocking_finding` or `derive_audit_stage`. No finding becomes blocking or non-blocking because of this edit.
- **The plan's "## Out of scope", an apply command for conceptual gaps:** the new re-audit bullet and command name a session-directed edit followed by `completeness-audit`. They never name `completeness-apply` for conceptual gaps.
- **The plan's "## Out of scope", a second blocking predicate:** the verdict only carries the gate's ids. The readers must not derive blocking or stage from `bundle_status.is_bare` or from list emptiness.
- **The plan's "## Out of scope", the loop-stop banner:** the `open_findings=` banner is not edited here.
- **The plan's intent:** an advisory gap is listed but holds back no stage; a blocking gap is named everywhere and ends the command list with the re-audit.

## Deferred

- Passing the verdict from `plan_tool/cli/completeness_phases.py` call sites (including the detail/split tails and the sink merge) — outside this step's declared files; owned by the plan's later steps.
- Surfacing the verdict in `--json` or the saved sidecar — it would change a persisted contract (`DATA_CONTRACT.md`) and is separate shared work.
- Consolidating `_completeness_has_blocking_findings` with the new verdict constructor — a cross-module refactor in `plan_tool/cli/completeness_cmd.py`, routed to the backlog rather than this step.
