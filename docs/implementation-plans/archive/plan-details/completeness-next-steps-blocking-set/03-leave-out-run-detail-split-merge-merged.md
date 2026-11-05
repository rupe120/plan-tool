> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Offer `run` in the detail / split / merge next-steps block only when the tail's blocking verdict is an empty set

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes the merged `Next steps:` block printed by `cmd_detail`, `cmd_split`, and the merge handler in `plan_tool/cli/authoring.py` leave out the `plan-tool run <name>` entry unless the completeness tail's blocking verdict is a completed, empty `set`. It reads the structured verdict that steps 1 and 2 build, carried on `_CompletenessTailOutcome`. It does not read the printed command text. A tail that returned no verdict, or whose verdict is `incomplete` or `absent`, drops `run`; the existing leading re-audit command from `_authoring_audit_follow_up` stays. On green, the three merged blocks never pair an open blocking gap with an execute command, and `--json`, exit codes, and the tail's own sink contract are unchanged.

## Table of Contents

- [Why](#why) — the three merged blocks append `run` unconditionally
- [Input](#input) — the verdict the tail hands up and what is still absent at HEAD
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — carrying the verdict, one predicate, three call sites
- [Tests](#tests) — cases for each verdict state and each command
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — docs relevant to this step
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

- The `detail` merged block appends `plan-tool reconcile-plan`, `plan-tool run`, and `plan-tool jira` after `_authoring_audit_follow_up(...)`. The `split` and merge blocks append `reconcile-plan` and `run`. None of the three looks at whether the audit left a blocking gap open.
- The follow-up helper only decides which *audit* commands lead. `run` is a fixed trailing tuple, so a tail that ended with a blocking gap still prints "execute the next runnable step".
- This contradicts the plan intent: no stage transition while a blocking gap is open. The verdict that answers "does anything block" already exists in the finalize gate; the parent commands never see it.

## Input

- **Step 1 outcome:** a blocking verdict type with states `set`, `incomplete`, and `absent`, in `plan_tool/completeness_report.py`. A `set` carries the blocking ids; an empty `set` means the gate found nothing blocking. Use the landed names; they win over any spelling here.
- **Step 2 outcome:** the finalize path builds the verdict from the gate's own result (`audit_incomplete`, the conceptual ids, and the blocking deterministic findings) and appends it to `args._blocking_verdict_sink` when the parent installed that list, the same way `_final_qualified_result_sink` works. Step 2 owns writing it; this step owns installing and reading it, and must not re-derive the verdict in `plan_tool/cli/authoring.py`.
- **At HEAD:** no verdict symbol exists in `plan_tool/` (grep for `BlockingVerdict` / `blocking_verdict` returns nothing), and `_run_completeness_tail` installs only the two existing sinks.
- **Limit:** the checks below drive the parent commands with a stubbed `app.cmd_completeness` that populates the sinks. They prove the wiring and the gating, not that the real audit's verdict is correct.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py`:
    - add a verdict field to `_CompletenessTailOutcome` (default `absent`)
    - install the verdict sink in `_run_completeness_tail` and fill the field in its returned outcome
    - add one small predicate that says whether the tail's verdict allows `run`
    - gate the `plan-tool run` tuple in the `detail` merged block, the `split` merged block, and the merge merged block
  - `tests/cli/test_completeness_cmd.py` — add the cases listed under Tests. This file already holds the sink-contract tests for `_persist_and_present_report` (`test_final_qualified_result_reaches_parent_sink`), so the new parent-side cases sit beside them.
- **Addition outside the declared list:** `tests/cli/test_authoring_cmds.py` already drives `main(...detail...)` with a stubbed `cmd_completeness` and may pin the `run` line in the merged block. Cases there that expect `run` after a tail with no verdict must be updated in this step; this is a test-only edit and no other file is added.

## Implementation

**Behavior that must hold**
- The `plan-tool run <name>` entry appears in the three merged blocks only when the verdict state is `set` and its blocking ids are empty.
- Every other state (`set` with ids, `incomplete`, `absent`, or no tail at all) omits `run`. The re-audit command that `_authoring_audit_follow_up` already puts first stays, and `reconcile-plan` stays.
- The decision reads the structured verdict only. It must not parse command text, count tuples in `next_steps`, or call `is_blocking_finding` / `derive_audit_stage`. A second predicate is the failure the plan's out-of-scope list names.

**Approach (recommended)**
- Extend `_CompletenessTailOutcome` with one field for the verdict, defaulting to the `absent` state, so `_coerce_completeness_tail_outcome` keeps accepting legacy list doubles and returns `absent` for them.
- In `_run_completeness_tail`, add the verdict sink beside `final_results`, set it on `completeness_args` as `_blocking_verdict_sink`, and store its single entry on the returned outcome; zero or several entries stay `absent`, matching how `final_results` is read today.
- Add one helper next to `_authoring_audit_follow_up`, for example `_tail_allows_stage_transition(tail_outcome)`, returning true only for an empty `set`. Use the type's own accessor if step 1 landed one; do not unpack ids by hand.
- At each of the three sites, build the trailing tuples with a conditional: include the stage-transition tuples (`run` everywhere, and `jira` in the `detail` block) only when the helper is true. Keep the existing order and descriptions.

**Rejected alternative:** filtering `run` out of the final list by matching command strings. It reads printed text, which the step intent rules out, and breaks the moment a description changes.

**Gotchas**
- **Pre-apply checkpoint:** the parent's sink already skips pre-apply checkpoints for the qualified result; the verdict sink must do the same (step 2's side), so the parent never reads a mid-loop verdict.
- **`--no-completeness`:** with the tail skipped, `completeness_tail` is `None`, so the verdict is `absent` and `run` is omitted. That is the intended conservative result, since no audit says nothing blocks.
- **Parallel path in `detail`:** the `effective_jobs > 1` run skips the convergence loop but still reaches the same merged block; it needs no separate handling.
- **Unchanged blocks:** the `not author_details` blocks and the skipped-only `detail` block never offered `run` and stay as they are.
- **Test-double compatibility:** the sink is attached to a copied `Namespace`; a stub `cmd_completeness` that never touches it must leave the verdict `absent`, not raise.

## Tests

All new cases live in `tests/cli/test_completeness_cmd.py`, driving `main(tmp_repo.argv(...))` with `app.cmd_completeness` stubbed to populate the sinks, in the same style as the existing authoring-sink tests. `generate_detail` / `split_step` are stubbed at the `plan_tool.cli.authoring` module globals so no backend spawns.

### Tests for this step

- `test_detail_merged_block_offers_run_for_empty_blocking_set` — an empty `set` verdict with a current qualified result keeps the `plan-tool run <name>` line.
- `test_detail_merged_block_omits_run_when_blocking_set_is_not_empty` — a `set` with one blocking id drops `run` and keeps the leading re-audit/disposition commands.
- `test_detail_merged_block_omits_run_when_verdict_incomplete` — an `incomplete` verdict drops `run`.
- `test_detail_merged_block_omits_run_when_tail_returns_no_verdict` — a stub that never fills the verdict sink leaves `absent` and drops `run`; this pins the conservative default.
- `test_detail_no_completeness_omits_run_because_no_audit_ran` — `--no-completeness` has no tail, so `run` is omitted; names the deliberate change in behavior.
- `test_detail_failed_tail_omits_run_because_no_verdict_arrived` — a tail whose completeness call raises (the warning-only path in `_run_completeness_tail`) fills no verdict sink, so the verdict is `absent` and `run` is omitted.
- `test_split_merged_block_gates_run_on_empty_blocking_set` — parametrized over empty `set` / non-empty `set` / `incomplete` / `absent`, asserting `run` only for the first.
- `test_merge_merged_block_gates_run_on_empty_blocking_set` — the same parametrization for the merge handler.
- `test_run_gate_reads_verdict_not_command_text` — a tail whose `next_steps` sink holds a command containing the word `run` but whose verdict is non-empty still omits the `run` entry; guards against text matching.
- `test_reconcile_plan_entry_survives_when_run_is_omitted` — `reconcile-plan` stays in all three blocks when `run` is dropped; pins that only `run` is gated.
- `test_legacy_list_tail_double_reads_as_absent_verdict` — `_coerce_completeness_tail_outcome` on a bare list returns `absent`.

Green-before-done gate: every case above, plus the updated cases in `tests/cli/test_authoring_cmds.py` and the existing sink tests in `tests/cli/test_completeness_cmd.py`, must pass before the step is done. Break the gate (always append `run`) and confirm the non-empty and `absent` cases go red.

## Acceptance criteria

- With a tail verdict that is an empty `set`, the `detail`, `split`, and merge next-steps blocks each contain exactly one `plan-tool run <name>` entry.
- With a non-empty `set`, `incomplete`, or `absent` verdict, none of the three blocks contains a `plan-tool run <name>` entry, and each still starts with the re-audit or disposition command from `_authoring_audit_follow_up`.
- `rg 'blocking_ids|is_blocking_finding|derive_audit_stage' plan_tool/cli/authoring.py` shows no new second blocking predicate; the gate calls only the verdict's own accessor.
- `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/completeness_phases.py`, and `plan_tool/completeness_report.py` have no diff from this step.
- `--json` output, `--fail-on-findings`, and exit codes of `detail`, `split`, and merge are unchanged.
- All new and updated tests pass.

## References

- [pytest: How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — covers the verdict-state parametrization for the split and merge cases.
- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — `monkeypatch` and `capsys` for stubbing `cmd_completeness` and reading the next-steps block.
- [Python dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — frozen dataclass field defaults for the new `_CompletenessTailOutcome` field.

## Applicable guardrails

- **The plan's "## Out of scope", stage bar and stage:** this step must not touch what blocks or how the stage is derived. It consumes the verdict and adds no predicate of its own in `plan_tool/cli/authoring.py`.
- **The plan's "## Out of scope", second blocking predicate:** deriving "is anything blocking" from bundle state or command lists in this file is the exact path the plan rules out; the gate reads the structured verdict only.
- **The plan's "## Out of scope", loop-stop banner:** this step leaves the `open_findings=` banner untouched.
- **The plan's "## Out of scope", apply command:** conceptual gaps still close by a session-directed edit; this step adds no apply entry to any block.
- **Step intent:** the change is the `run` entry in the three merged blocks and nothing wider.

## Deferred

- Passing the verdict from the finalize path to a parent sink — owned by step 2, which builds and hands up the verdict from the gate's own values.
- The verdict type and the four report/console readers — owned by step 1 in `plan_tool/completeness_report.py`.
- Gating any `run` mention in standalone `completeness-audit` output — handled by the readers that steps 1 and 2 cover, not by the authoring parents.
