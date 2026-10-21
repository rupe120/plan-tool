# Step 3 — Give finalize the BlockingVerdict as its single input and remove the dead deterministic splice from the fresh-audit early return

## Summary

This step makes `finalize_completeness_run` hand every gap list, count, and next-command decision to its readers through the one `BlockingVerdict` it builds, and removes the deterministic-findings splice in `_render_grouped_report`'s fresh-audit branch that can never add a step. The edits sit in `plan_tool/cli/completeness_cmd.py` and `plan_tool/cli/completeness_phases.py`. The key decision is that this is a behavior-preserving refactor: the gate pair (`has_blocking`, `conceptual_bar_blocking_ids`, `audit_incomplete`) keeps feeding `--json`, `--fail-on-findings`, and exit codes, while the verdict is the only value any list-naming reader sees. On green, the report text, console block, and `--json` payload are the same as before step 3, and step 4 can move the remaining readers onto the verdict without a second source to drift from.

## Table of Contents

- [Why](#why) — the two sources finalize carries today
- [Input](#input) — what steps 1 and 2 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint
- [Implementation](#implementation) — one input, one removal
- [Tests](#tests) — cases and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable results
- [Applicable guardrails](#applicable-guardrails) — fences that bind this step
- [Deferred](#deferred) — work left to other steps

## Why

`finalize_completeness_run` computes `conceptual_bar_blocking_ids` and `blocking_deterministic` once, builds `blocking_verdict` from them, and then also passes the raw ids to the JSON renderer, the qualified-result classifier, and the gate. A reader that names gaps can therefore take its list from either the verdict or the raw ids, and the two have already diverged for an incomplete audit (step 2 gives the verdict ids the gate withholds). Separately, `_render_grouped_report` ends with a `_fresh_audit_required` branch that replaces `_next_steps` and splices `_blocking_deterministic_steps(verdict)` into the replacement. That branch fires only for an unqualified result whose verdict is `absent` (the call passes `is_pre_apply_checkpoint=False` as a literal), and an `absent` verdict carries no deterministic findings, so the splice always returns an empty list. It reads as a second place a deterministic finding could be named.

## Input

- **Step 1** supplies the three-value `untrusted_cause` and the `revision_status` argument to `_verdict_untrusted_cause`. This step must not change how the cause is computed.
- **Step 2** supplies the verdict's own ids (the stage-bar ids kept for an incomplete audit), separate from the gate ids `_conceptual_bar_from_audit_recs` still returns. Read the landed names from HEAD; they win over this file.
- **`plan_tool/completeness_report.py`:** `BlockingVerdict`, `blocking_verdict_from_gate`, `_fresh_audit_required`, `_blocking_deterministic_steps`. `blocking_verdict_from_gate` never produces state `absent`, so only the default `ABSENT_BLOCKING_VERDICT` (or `None` read as absent) reaches the fresh-audit branch. Confirm this at HEAD before deleting.
- **Readers already on the verdict:** `_render_grouped_report`, `_persist_and_present_report`, `next_stage_command`, `suggested_next_step_commands`, and the `_blocking_verdict_sink` on `args`.
- **Readers deliberately on the gate:** `_render_completeness_json` (`has_blocking`, `conceptual_bar_blocking_ids`, `audit_incomplete`), `_completeness_finalize_is_clean`, `classify_qualified_audit_result`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — in `_render_grouped_report`, drop the `_blocking_deterministic_steps(verdict)` splice from the `_fresh_audit_required` branch. Route any remaining list, count, or id read in the render and persist path through the `verdict` argument.
  - `plan_tool/cli/completeness_cmd.py` — in `finalize_completeness_run`, keep one computed `blocking_verdict` and pass it to every reader that names gaps. Leave the gate pair on the JSON, classifier, and gate calls.
  - `tests/cli/test_completeness_cmd.py` — update the source-inspection test that pins how the verdict is built, and add the cases listed in Tests.

## Implementation

- **Enumerate readers first.** Name the defect as a class ("a reader of finalize's output derives its gap list or count from something other than the verdict") and search by identifier (`conceptual_bar_blocking_ids`, `blocking_deterministic`, `audit_incomplete` inside `finalize_completeness_run` and the render/persist calls it makes) and by vocabulary ("blocking", "gaps to close", "next step"). Record each hit as verdict-fed, gate-fed on purpose, or changed here. A green suite is not evidence the list is complete.
- **Keep the gate pair as is.** `--json` `has_blocking_findings`, `--fail-on-findings`, and exit codes read the gate. This is the plan's out-of-scope fence; do not route them through the verdict.
- **Build the verdict once, before any reader.** `blocking_verdict` already exists before the `--json` branch and the markdown branch; keep it computed in one place and do not rebuild it inside a reader.
- **Remove the splice, not the branch.** Keep `_fresh_audit_required` and the replacement `_next_steps` (the re-audit command and its line). Delete only the `_blocking_deterministic_steps(verdict)` unpacking inside it. The earlier `not _verdict_offers_stage(verdict)` block still names deterministic steps for every verdict that has any, so no step is lost.
- **Rejected alternative:** hoisting `_blocking_deterministic_steps` out of both branches into one shared call. It changes ordering in the earlier block and widens the diff for a branch that is dead; the removal is the smaller change.
- **Behavior must not change.** This step is a refactor; if a reader's output differs on any existing fixture, the reader was reading the gate's value on purpose or the verdict diverges from it. Stop and surface it rather than adjusting the output.

## Tests

- `test_finalize_passes_one_verdict_to_every_list_reader` — drives `finalize_completeness_run` with a stubbed render/persist and asserts the same `BlockingVerdict` object reaches the grouped report, the persist call, and the `_blocking_verdict_sink`.
- `test_fresh_audit_branch_names_no_deterministic_step_for_absent_verdict` — renders the report with an `absent` verdict and an unqualified result; asserts the next steps are exactly the re-audit line, pinning that the removed splice never contributed a step.
- `test_deterministic_blocker_still_named_when_verdict_is_incomplete` — an `incomplete` verdict carrying a blocking deterministic finding still names it once in the next steps (the carve-out the removal must not lose).
- `test_json_payload_gate_fields_do_not_follow_the_verdict_ids` — an incomplete audit with retained verdict ids still reports `conceptual_bar_blocking_ids: null` and the gate's `has_blocking_findings`; pins that only the verdict changed.
- `test_verdict_uses_post_loop_stage_not_frozen_outcome_ids` — update (existing) so the source check follows the step 2 id names and keeps the "not the frozen outcome ids" assertion.

### Tests for this step

The five cases above in `tests/cli/test_completeness_cmd.py`, plus the existing verdict-reader tables and `--json` payload tests, must all be green before the step is finished. The existing `test_json_payload_signature_is_unchanged_by_verdict_wiring` stays untouched and guards the external contract. Verify the new cases by mutation: re-add the splice, or feed the JSON the verdict ids, and watch the matching case go red.

## Acceptance criteria

- `_render_grouped_report`'s `_fresh_audit_required` branch contains no call to `_blocking_deterministic_steps`.
- `finalize_completeness_run` builds `blocking_verdict` once and every gap-naming reader receives it.
- `--json` output, `--fail-on-findings`, and exit codes are unchanged on every existing fixture (the full `tests/cli/test_completeness_cmd.py` and `tests/test_completeness_report.py` suites pass without edits other than the pinned source-inspection test).
- The reader enumeration (identifier and vocabulary searches, with a per-site disposition) is recorded in the handoff.

## Applicable guardrails

- **The plan's "## Out of scope", finalize gate contract:** this step must not alter `has_blocking_findings`, `--fail-on-findings`, or exit codes; the gate pair stays on the JSON and gate calls.
- **The plan's "## Out of scope", new advisories and gates:** the single-input change adds no gate, advisory, or convergence signal.
- **The plan's "## Out of scope", #479's settled states:** `set` / `incomplete` / `absent` and trust-follows-the-gate stay as landed.
- **Step intent:** finalize reads its list from the one verdict; nothing wider than that belongs here.

## Deferred

- Moving the grouped report, prose, console, and `_authoring_guidance` onto verdict-derived gap lists and counts — step 4 owns it.
- Cause-specific next actions and the `stale-revision` constant — step 1.
- Retained ids for an incomplete audit — step 2.
- Updating the audit how-to and removing the backlog entry — step 5.

<!-- plan-tool-detail-deferrals
{"deferrals":[]}
-->
