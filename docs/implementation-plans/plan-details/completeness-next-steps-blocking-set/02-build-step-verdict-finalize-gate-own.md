# Step 2 — Build the verdict from the finalize gate's own result and hand it to every next-step reader

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step builds one blocking verdict (the type step 1 defines) from the result the finalize gate already computed. It passes that verdict to every caller of `next_stage_command`, `suggested_next_steps`, `suggested_next_step_commands`, and `console_summary`, including `_render_grouped_report`. The work is in `plan_tool/cli/completeness_phases.py` and `plan_tool/cli/completeness_cmd.py`. The key decision is that the gate's deterministic arms are collected once as findings, the gate's bool is derived from that collection plus the conceptual ids, and the verdict wraps the same collection, the conceptual ids, and `audit_incomplete`; nothing is re-derived. On green, no next-step surface offers a stage transition while the gate says something blocks, and `--json`, `--fail-on-findings`, and exit codes are unchanged.

## Table of Contents

- [Why](#why) — the readers have the verdict parameter but nobody passes it
- [Input](#input) — what step 1 provides and what the gate already holds
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files touched
- [Implementation](#implementation) — builder, caller table, gotchas
- [Tests](#tests) — cases pinning each caller and the gate's contract
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — docs relevant to this step
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

- Step 1 makes the readers honor a verdict, but an omitted verdict still keeps today's output (step 1's two-phase default). This step wires every caller, then flips that default so an omitted verdict reads as `absent`.
- The gate's answer already exists in `finalize_completeness_run` (`plan_tool/cli/completeness_cmd.py`): `conceptual_bar_blocking_ids`, `audit_incomplete`, and `has_blocking`. The report and console callers sit in other functions and do not see it.
- `_render_grouped_report` is called from three places and has no verdict parameter. Its next-steps block picks "No gaps to close" from list emptiness.

## Input

- **Step 1 outcome:** the blocking verdict type with states `set`, `incomplete`, `absent`, plus a constructor that wraps ids without re-testing them. The four readers take it as an optional keyword. Use the names step 1 landed in `plan_tool/completeness_report.py`; the landed names win over any spelling in this file.
- **Gate values, all computed once in `finalize_completeness_run`:**
  - `_conceptual_bar_from_audit_recs` returns `(conceptual_bar_blocking_ids, audit_incomplete)`. When the audit is incomplete the ids are `()`, so an empty tuple alone does not mean "clear".
  - `_completeness_has_blocking_findings` takes `det.*` findings plus the bar ids and returns `has_blocking` from separate deterministic arms that can block even when the bar ids are empty. This step collects those arms into one list of blocking deterministic findings that the gate's bool and the verdict both read (see Implementation).
- **Callers with no audit outcome:** a reused saved audit goes through `_resolve_audit_reuse` and the same finalize path, so it passes a set. `list --status` and the detail/split parents (`plan_tool/cli/authoring.py` sink idiom) do not run the readers directly (verified by grep at HEAD); they consume what `cmd_completeness` hands up.
- **Limit:** the checks below verify wiring with canned recs. They do not prove the model's findings are right.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — add one small builder that turns the gate's values into the verdict; add a verdict parameter to `_render_grouped_report` and `_persist_and_present_report`; pass it to every reader call inside them; carry it on `_IterateOutcome` or as a keyword where the pre-apply checkpoint path calls them.
  - `plan_tool/cli/completeness_cmd.py` — in `finalize_completeness_run`, build the verdict right after `has_blocking` and pass it to the `_render_grouped_report` and `_persist_and_present_report` calls. No change to `has_blocking`, `_completeness_has_blocking_findings`, the `--json` payload, or exit codes.
  - `plan_tool/completeness_report.py` — map step 1's unset verdict sentinel to `absent`, after every caller above passes a verdict.
  - `tests/cli/test_completeness_cmd.py` — add the wiring cases; update cases that pin "No gaps to close" from list emptiness.
  - `tests/test_completeness_report.py` — delete step 1's unset-verdict test and pass an explicit empty-set verdict in the cases that assert a stage transition.

## Implementation

**Behavior that must hold**
- Every reader call in `completeness_phases.py` receives a verdict built from the gate's values at that point. None computes blocking from its own lists.
- Trust follows the gate. The verdict is a trusted `set` when `audit_incomplete` is false and the result is not `no-qualified-current-evidence`; a non-empty set then names its gaps whatever the stop reason (a hand-apply stop included, with no blanket exemption). An empty set is `incomplete` unless finalize is clean (`_completeness_finalize_is_clean`) and the result is not `awaiting-human-action`. `incomplete` keeps the computed ids. `_verdict_untrusted_cause` in `completeness_cmd.py` returns `""` (trusted), `persistent` (unqualified coverage, no-qualified-current-evidence, a hand-apply stop with an empty set, or `awaiting-human-action` with an empty set) or `transient` (any other unclean stop), and `blocking_verdict_from_gate(..., untrusted_cause=...)` wraps it. Amended 2026-10-10 after implementation review round 3.
- One parametrized test over stop reason, set empty or not, coverage qualified or not, and headline asserts a stage is offered iff the set is empty, finalize is clean, and the headline is neither `awaiting-human-action` nor `no-qualified-current-evidence`, and that the ids named equal the gate's in every non-absent case.
- Deterministic blockers must not read as clear. Extract the gate's deterministic arms in `_completeness_has_blocking_findings` into one function that returns the blocking deterministic findings (self-consistency, purity coverage, data contract, lessons coverage, detail body, and every other arm it tests). The gate's bool becomes "any of those, or any bar id", and the verdict's `blocking_deterministic` is that same list. The invariant is "clear if and only if the gate is clear", and it holds by construction because both read one computation.

**Builder (recommended shape)**
- One function in `completeness_phases.py`, for example `_blocking_verdict_from_gate(*, audit_incomplete, conceptual_bar_blocking_ids, blocking_deterministic)`.
- It takes values already computed. It must not call `is_blocking_finding`, `is_blocking`, `compute_conceptual_bar_blocking_ids`, or `derive_audit_stage`. This is how the second-predicate fence holds.
- Rejected alternative: have `_render_grouped_report` and `_persist_and_present_report` recompute from `audit_recs`. That is the parked fix's failure shape, and it can disagree with `--json`'s `has_blocking_findings`.

**Caller table (every site, with what it passes)**

| Site | Reader(s) | Verdict source |
| --- | --- | --- |
| `finalize_completeness_run`, non-iterate and iterate-final `_render_grouped_report` call | `next_stage_command` (two branches inside it) | built after `has_blocking` |
| `_run_iterate_convergence_loop` pre-apply checkpoint `_render_grouped_report` call (`is_pre_apply_checkpoint=True`) | same | the loop's own `_conceptual_bar_blocking_ids` and its `audit_incomplete`; no finalize gate exists yet, so `has_blocking` comes from the same `_completeness_has_blocking_findings` call the loop already makes, or the verdict is `absent` if it has none |
| `_persist_and_present_report`, `console_summary` call | `console_summary` | same verdict as the report |
| `_persist_and_present_report`, `suggested_next_step_commands` call | `suggested_next_step_commands` | same verdict |
| `_persist_and_present_report`, empty-list fallback `next_stage_command` | `next_stage_command` | same verdict |
| the curated summary's `suggested_next_steps` inside `completeness_report.py` | `suggested_next_steps` | reached through `_persist_and_present_report`'s write of the report; thread the same verdict |
| `_next_steps_sink` consumers (`plan_tool/cli/authoring.py` detail/split/merge parents) | none directly | they merge tuples the sink already holds, which now end with the re-audit command when the gate blocks |
| verdict sink for the parents: `_blocking_verdict_sink` on `args`, beside `_final_qualified_result_sink` | not a reader | this step writes the final verdict into the list when the parent installed one (never for a pre-apply checkpoint); step 3 installs and reads it |
| loop-stop `open_findings=` banner | not a reader | deliberately not touched: it reports the loop count, not a next step |

**Constraints and gotchas**
- **Pre-apply checkpoint is not final.** It must not claim a clear verdict it cannot know. If no gate result exists yet, pass `absent` so no stage is offered.
- **Stale stage.** `finalize_completeness_run` recomputes bar ids against `result_audit_stage` on purpose. Build the verdict from those fresh values, never from the loop's frozen `outcome` ids.
- **Keep the module-global call forms.** Tests patch `plan_tool.review.*` seams; do not alias them while threading the parameter.
- **Leaf direction.** `completeness_phases.py` stays free of an import of `completeness_cmd`. The verdict is computed in `completeness_cmd.py` and passed in, or the builder lives in `completeness_phases.py` and takes plain values.
- **Defaults.** New keyword parameters are keyword-only. After every caller passes a verdict, map step 1's unset sentinel to `absent` in `plan_tool/completeness_report.py`, delete step 1's `test_unset_verdict_keeps_todays_output_until_callers_are_wired`, and rewrite the existing cases (in `tests/test_completeness_report.py` and `tests/cli/test_completeness_cmd.py`) that call a reader with no verdict and assert a stage transition: pass a completed empty-set verdict, which keeps their intent and makes the default change explicit.

## Tests

### Tests for this step

All in `tests/cli/test_completeness_cmd.py`, using the existing invoker stubs; no real backend. Every case below, plus the rest of the module, must be green before this step is finished.

- `test_clean_gate_builds_empty_set_verdict_and_offers_stage` — no blocking ids, complete audit, no deterministic blockers: report and console offer the stage command.
- `test_blocking_bar_id_closes_every_next_step_surface` — one blocking conceptual id: grouped report, console summary, command list, and fallback all omit run/jira/detail and end with the re-audit command.
- `test_deterministic_blocker_with_empty_bar_ids_is_not_clear` — a blocking deterministic finding and `conceptual_bar_blocking_ids == ()` still withholds the stage. Named for the invariant: an empty id tuple must never be read as "nothing blocks".
- `test_incomplete_audit_builds_incomplete_verdict_not_empty_set` — `audit_incomplete` true yields no stage offer even though the ids are `()`.
- `test_verdict_clear_iff_gate_clear` — parametrized over the gate's inputs: the verdict is a completed empty set exactly when `_completeness_has_blocking_findings` is false and the audit is complete.
- `test_pre_apply_checkpoint_report_offers_no_stage` — the checkpoint `_render_grouped_report` call never claims a clear verdict.
- `test_verdict_uses_post_loop_stage_not_frozen_outcome_ids` — a stage change after the loop is reflected in the verdict.
- `test_json_has_blocking_findings_and_exit_code_unchanged` — `--json` payload keys, `--fail-on-findings`, and rc are the same as before the wiring for a blocking and a clean run.
- `test_next_steps_sink_receives_reaudit_command_when_gate_blocks` — the detail/split sink ends with the re-audit tuple, not a stage command.
- Update existing cases that assert "No gaps to close" from list emptiness so they build a clear gate explicitly.

## Acceptance criteria

- With the gate blocking (bar ids or deterministic findings), no output of `completeness-audit` in report, console, or sink contains "no plan-level gaps remain", "No gaps to close", or a `run`/`jira`/detail-authoring command, at run and jira grade.
- With `audit_incomplete`, the same surfaces offer no stage and do not claim nothing blocks.
- With a clean complete gate, the stage command still appears.
- When a parent installed `args._blocking_verdict_sink`, `finalize_completeness_run` appends exactly one built verdict to it (none for a pre-apply checkpoint); step 3 installs and reads that list.
- Every reader call in `plan_tool/cli/completeness_phases.py` passes a verdict; `rg "next_stage_command\(|suggested_next_step_commands\(|console_summary\(" plan_tool/cli/completeness_phases.py` shows none without it.
- `rg "is_blocking_finding|is_blocking\(|derive_audit_stage|is_bare" plan_tool/cli/completeness_phases.py` shows no new use added by this step.
- `_completeness_has_blocking_findings`, the `--json` payload, `--fail-on-findings`, and exit codes are unchanged.
- `uv run pytest tests/cli/test_completeness_cmd.py tests/test_completeness_report.py -q` is green.

## References

- [pytest: How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — for the clear-iff-gate-clear table.
- [Python dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — for passing the frozen verdict through keyword parameters.
- [Python sys.exit and exit status](https://docs.python.org/3/library/sys.html#sys.exit) — to confirm exit codes stay as before.

## Applicable guardrails

- **The plan's "## Out of scope", changing what blocks:** this step reads the gate's result and does not alter the stage bar or `derive_audit_stage`.
- **The plan's "## Out of scope", a second blocking predicate:** the builder only repackages `has_blocking`, `audit_incomplete`, and the bar ids. No reader-side derivation from list emptiness or `bundle_status.is_bare`.
- **The plan's "## Out of scope", an apply command for conceptual gaps:** the re-audit guidance names a session-directed edit, never `completeness-apply`.
- **The plan's "## Out of scope", the loop-stop banner:** the `open_findings=` banner stays untouched.
- **The plan's step intent:** every caller is listed in the Implementation table with the verdict it passes, including callers with no audit outcome and the detail/split parents.

## Deferred

- Surfacing the verdict in `--json` or the saved sidecar — would change a persisted contract (`DATA_CONTRACT.md`); separate shared work.
- Merging `_completeness_has_blocking_findings` with the verdict builder — a cross-module refactor, routed to the backlog.
- Passing a verdict through `list --status` — it does not call these readers at HEAD; revisit only if that changes.
