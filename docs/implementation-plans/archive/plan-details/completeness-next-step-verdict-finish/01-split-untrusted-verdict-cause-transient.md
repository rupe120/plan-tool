> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Split the untrusted-verdict cause into transient, persistent, and stale-revision

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes the blocking verdict's `untrusted_cause` carry three values (`transient`, `persistent`, `stale-revision`) and gives each its own next action. `plan_tool/cli/completeness_cmd.py:_verdict_untrusted_cause` gains an explicit `revision_status` input and a stated precedence. `plan_tool/completeness_report.py` gains the `stale-revision` constant, and `_reaudit_command` plus `next_step_gaps` branch on it. The key decision is that the stale trigger has one source, `QualifiedAuditResult.revision_status`, and that a cut-short stop is judged before the awaiting-action headline can claim it. On green, a qualified result that stopped on `max_iterations` is told to re-audit. A stale-revision result gets the fresh-audit answer, and its saved gaps are not offered as text to close. The `--json` payload, `--fail-on-findings`, and exit codes do not change.

## Table of Contents

- [Why](#why) — what the classifier gets wrong today
- [Input](#input) — the facts the classifier reads
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint
- [Implementation](#implementation) — precedence, new constant, reader changes
- [Tests](#tests) — cases and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable results
- [References](#references) — docs for this step
- [Applicable guardrails](#applicable-guardrails) — fences that bind this step
- [Deferred](#deferred) — work left to other steps

## Why

`_verdict_untrusted_cause` tests the `no-qualified-current-evidence` and `QUALIFIED_RESULT_AWAITING_ACTION` headlines before it looks at the stop reason, and both return `persistent`. `classify_qualified_audit_result` marks any stop outside `converged` / `no_blocking_findings` as awaiting-action. So a qualified, current-revision audit that hit `max_iterations`, `deadline_exceeded`, or `no_progress` reaches `persistent` and is told "re-auditing unchanged text reproduces this result — triage". That is wrong, because a plain re-audit continues a cut-short run. The existing cut-short rows in the test table pass only because they use a `clean` headline, which a real cut-short stop never produces. Separately, a stale revision (`revision_status` `stale` or `unknown-legacy`) has no cause of its own. It lands in `persistent` and receives the same "reproduces this" text, which is false for changed text.

## Input

- **`classify_qualified_audit_result`** (`plan_tool/cli/completeness_cmd.py`) returns `QualifiedAuditResult` with `headline`, `revision_status`, and `coverage`.
  - `revision_status` is `current`, `unknown-legacy`, `stale`, or `not-sampled`.
  - `stale` and `unknown-legacy` come only from the branch that also returns the `no-qualified-current-evidence` headline.
  - `not-sampled` is also a no-evidence result: no sample exists, so it takes the fresh-audit (`stale-revision`) answer, not hand triage.
- **`finalize_completeness_run`** (same file) already holds `_qualified_result` when it builds the verdict, so `revision_status` is available at the call site without new plumbing.
- **Stop-reason sets** at HEAD:
  - `_CLEAN_ELIGIBLE_STOP_REASONS` is an alias of `_REMAP_STOP_FOR_CONCEPTUAL_BAR` in `plan_tool/cli/completeness_phases.py`.
  - `_HAND_APPLY_STOP_REASONS` is `terminal_hand_apply` and `manual_fix_blocking_findings`.
- **Precedence** is owned by the plan's `## Architecture` ("Precedence when one result carries several causes"). Implement that list; do not re-decide it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — add the `stale-revision` cause constant. Teach `_reaudit_command` its reason text. Teach `next_step_gaps` not to offer stale-revision ids as text to close. Update the constant comment block.
  - `plan_tool/cli/completeness_cmd.py` — extend `_verdict_untrusted_cause` with `revision_status` and the new order. Pass `_qualified_result.revision_status` at the `blocking_verdict_from_gate` call in `finalize_completeness_run`. Import the new constant.
  - `tests/test_completeness_report.py` — add and adjust verdict-reader cases.
  - `tests/cli/test_completeness_cmd.py` — replace the unrealistic cut-short rows and add the combined-cause rows.

## Implementation

**Cause vocabulary**
- Add `UNTRUSTED_STALE_REVISION = "stale-revision"` beside `UNTRUSTED_TRANSIENT` and `UNTRUSTED_PERSISTENT`.
- Use exactly these three values. Incomplete / budget-limited stays `persistent` with its retained ids; do not mint a fourth value.

**Classifier**
- Add a keyword `revision_status: str` to `_verdict_untrusted_cause` and evaluate in this order (first match wins):
  1. **Stale revision.** The headline is `QUALIFIED_RESULT_NO_EVIDENCE` and `revision_status` is `stale`, `unknown-legacy`, or `not-sampled`. Return `stale-revision`.
  2. **Incomplete or unqualified.** `audit_incomplete`, or the no-evidence headline on a current revision. Return `persistent`.
  3. **Non-empty blocking set.** Return `""`. This is the existing trust-follows-the-gate rule and is not re-decided here.
  4. **Cut-short stop.** The stop reason is neither clean-eligible nor in `_HAND_APPLY_STOP_REASONS`. Return `transient`. This check must run **before** the awaiting-action headline is read.
  5. **Hand-apply stop.** The stop reason is in `_HAND_APPLY_STOP_REASONS`. Return `persistent`.
  6. **Catch-all.** The awaiting-action headline (deferrals waiting on a person), or any other untrusted result. Return `persistent`, never `""`.
  7. Otherwise return `""`.
- Rules 4 and 5 are disjoint by stop reason, so their relative order is free.
- An incomplete audit with no retained ids returns `persistent`; `_reaudit_command` prescribes the plain re-audit (`--iterate` at run grade, `--grade jira` without `--iterate` at jira grade) and no stage. Readers name nothing to close and keep any findings listed as advisory.
- Derive the cause from the headline and `revision_status` that `classify_qualified_audit_result` produced. Do not pair cases by hand.
- Rejected alternative: have the classifier recompute staleness from the audit snapshot. That gives the trigger two sources and can disagree with the headline.

**Readers (all in `plan_tool/completeness_report.py`)**
- **`_reaudit_command`:**
  - Add a `stale-revision` branch whose reason says the saved result describes text that has since changed, so run a fresh audit.
  - It must not use the "reproduces this result" or "triage" wording.
  - The command is unchanged: `--iterate` for run grade, `--grade jira` without `--iterate` for jira grade.
  - Keep the `transient` wording ("the audit stopped early — re-audit to continue") and the `persistent` triage wording unchanged.
- **`next_step_gaps`:**
  - Under a `stale-revision` verdict, return empty `close_*` tuples and `unlisted_blocking == 0`.
  - Listed conceptual findings go to the advisory tuples.
  - Deterministic blockers still close, as the docstring promises.
- **`BlockingVerdict` docstring:** extend it to list the three cause values.

**Constraints**
- `blocking_verdict_from_gate` keeps its rule that a non-empty cause makes the verdict `incomplete` and offers no stage. Do not change `_verdict_offers_stage`.
- Do not touch `is_blocking_finding`, `is_blocking_impact`, `_completeness_finalize_is_clean`, `has_blocking`, or any exit-code path.
- Shared readers outside the declared files (`cli/completeness_phases.py`, the grouped report, console output) already consume `untrusted_cause` through `_reaudit_command` and `next_step_gaps`. Leave them to the later reader-seam steps; the only caller that needs editing here is the verdict builder.

## Tests

Test files: `tests/test_completeness_report.py` and `tests/cli/test_completeness_cmd.py`.

- `test_qualified_current_cut_short_stop_is_transient_even_under_awaiting_action_headline` (parametrized over `max_iterations`, `deadline_exceeded`, `no_progress`) — uses the headline `classify_qualified_audit_result` really produces; asserts `transient`.
- `test_stale_revision_no_evidence_is_stale_revision_cause` (parametrized over `stale`, `unknown-legacy`, `not-sampled`) — asserts `stale-revision`, not `persistent`.
- `test_no_evidence_on_current_revision_stays_persistent` — covers a `current` revision; the catch-all must not return `""`.
- `test_awaiting_action_deferrals_with_no_stop_reason_are_persistent_not_trusted` — pins the catch-all against the "no gaps remain" regression.
- `test_hand_apply_stops_stay_persistent` — `terminal_hand_apply` and `manual_fix_blocking_findings`.
- `test_stale_wins_over_incomplete_and_transient` — stale × incomplete and stale × cut-short stop (`max_iterations`) both return `stale-revision`; `unknown-legacy` alone returns `stale-revision`.
- `test_awaiting_action_empty_set_transient_vs_hand_apply_stop` — a qualified, current-revision, empty-set result under the awaiting-action headline returns `transient` for a cut-short stop and `persistent` for a hand-apply stop; the overlap rules 4 and 5 resolve.
- `test_incomplete_with_no_retained_ids_names_nothing_and_prescribes_plain_reaudit` — the reason text and command are the one wording step 4's readers share.
- `test_incomplete_wins_over_transient_stop` — a budget-limited audit that stopped on `max_iterations` is `persistent`.
- `test_nonempty_blocking_set_on_qualified_result_is_trusted_whatever_the_stop` — carve-out pin: the trust-follows-the-gate rule is unchanged.
- `test_reaudit_command_stale_revision_names_fresh_audit_not_triage` — the reason text omits "reproduces" and "triage"; the command text is unchanged per grade.
- `test_reaudit_command_transient_and_persistent_texts_unchanged` — pins the existing wording.
- `test_next_step_gaps_stale_revision_lists_no_close_conceptual_gaps_but_keeps_deterministic` — close lists are empty for conceptual ids; deterministic blockers still close.
- Existing parametrized tables in both files: replace the `clean`-headline cut-short rows with rows built from real `classify_qualified_audit_result` output.

**Green-before-done gate:** every test above, plus the existing verdict-reader and finalize suites in both files, must be green before this step is finished. Run `uv run pytest tests/test_completeness_report.py tests/cli/test_completeness_cmd.py -q -n auto` and confirm the `--json` and `--fail-on-findings` tests are untouched and green.

## Acceptance criteria

- A qualified, current-revision result that stopped on `max_iterations`, `deadline_exceeded`, or `no_progress` yields `untrusted_cause == "transient"`, and its next-command reason says to re-audit to continue.
- A `no-qualified-current-evidence` result with `revision_status` `stale`, `unknown-legacy`, or `not-sampled` yields `"stale-revision"`, and its reason text contains neither "reproduces" nor "triage".
- Under a `stale-revision` verdict, `next_step_gaps` returns no conceptual finding in a `close_*` tuple.
- `terminal_hand_apply`, `manual_fix_blocking_findings`, unqualified coverage, and awaiting-action deferrals with a current revision yield `"persistent"`. No untrusted result ever yields `""`.
- `_verdict_untrusted_cause` takes `revision_status` as an explicit argument, and the verdict builder passes `_qualified_result.revision_status`.
- The `--json` `has_blocking_findings`, `--fail-on-findings`, and exit-code tests pass without edits.

## References

- [dataclasses — Data Classes (Python 3.13 docs)](https://docs.python.org/3.13/library/dataclasses.html) — frozen `BlockingVerdict` semantics.
- [How to parametrize fixtures and test functions (pytest docs)](https://docs.pytest.org/en/stable/how-to/parametrize.html) — the cause × headline × stop tables.

## Applicable guardrails

- **The plan's "## Out of scope" (what blocks, finalize external contract):** this step changes only the cause label and the text and close lists derived from it. It must not edit the blocking predicates, `has_blocking`, `--json`, `--fail-on-findings`, or exit codes.
- **The plan's "## Out of scope" (#479's settled states):** `set` / `incomplete` / `absent` and the trust-follows-the-gate rule stay as they are. The new cause value lives inside `incomplete`, and a non-empty trusted set keeps `""`.
- **The plan's "## Out of scope" (no new advisories, gates, or signals):** the new constant is a cause label, not a gate or advisory.

## Deferred

- Retaining blocking ids for an incomplete audit in `plan_tool/cli/completeness_phases.py:_conceptual_bar_from_audit_recs` — a separate step; outside this step's declared files.
- Reader seams in the grouped report, console `blocking N` wording, `_authoring_guidance`, and the finalize deterministic-arm duplication — later steps of this plan.
- Updating `docs/how-to/pipeline/audit.md` and the audit-flow prose for the three causes — a docs step outside this step's declared files.
