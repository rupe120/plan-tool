> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add tier-challenge as a high-severity manual finding

## Summary

Add `tier-challenge` as a recognized high-severity `plan-correctness` finding that stays visible in completeness reports and saved-history diagnosis but never reaches an apply writer. Update the audit parser, recommendation persistence, reporting, and completeness-apply routing across `plan_tool/review.py`, `plan_tool/completeness_report.py`, and the completeness CLI modules. Preserve the existing `files-coherence` rewrite and timestamped report allocation unchanged. On green, an unresolved challenge stops completeness-apply and therefore the existing direct pipelines before execution or export.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the manual finding route.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why this finding needs its own manual path.
- [Input](#input) — Upstream policy and saved-finding contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Code, documentation, and test footprint.
- [Implementation](#implementation) — Required parsing, blocking, reporting, and preservation behavior.
- [Tests](#tests) — Focused coverage and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for response parsing and tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Work owned by the next step or later follow-up.

## Why

`plan_tool/review.py:check_plan_audit` currently transports conceptual correctness findings through the normal `plan-correctness` route, which `plan_tool/cli/completeness_phases.py:_resolve_apply_walk_targets` can send to `apply_finding`. A finding that an explicit low-risk declaration is contradicted must block progress without allowing an automated rewrite to change that declaration or choose a higher tier. `DETAIL_FORMAT.md:## Files` is only the existing detail-file schema; no current finding identity or manual-resolution route implements this policy.

## Input

- **Step 1 output:** Consume step 1’s landed shared `tier-challenge` identity and fixed `standard` minimum. Step 1 owns the vocabulary; do not duplicate or redefine it here.

- **Conceptual finding transport:** Build on `plan_tool/review.py:Recommendation`, `_parse_plan_audit_findings_with_evidence`, and `plan_tool/convergence.py:CONCEPTUAL_SOURCES`. A recognized challenge remains `plan-correctness`, not a third conceptual source.

- **Saved-review compatibility:** Preserve the recommendation shape written by `plan_tool/completeness_report.py:write_completeness_report` and reloaded by `plan_tool/review_persistence.py:_load_recommendations`. New challenge-only fields need safe defaults for older sidecars.

- **Independent preserved paths:** Keep `plan_tool/cli/completeness_phases.py:_apply_files_coherence` and `plan_tool/completeness_report.py:_reserve_report_timestamp` independent of this finding.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Recognize an explicit-low challenge, retain its evidence, keep it out of apply eligibility, and merge its evidence across audit samples.
  - `plan_tool/convergence.py` — Preserve the existing high-severity blocking result at both audit stages without changing general finding policy.
  - `plan_tool/convergence_diagnosis.py` — Keep an open challenge visible as a high-severity history blocker without treating it as a structural finding.
  - `plan_tool/completeness_report.py` — Render the unresolved manual decision and avoid misleading apply guidance.
  - `plan_tool/cli/completeness_phases.py` — Exclude challenges from serial and parallel apply targets while returning a non-success manual-resolution outcome.
  - `plan_tool/cli/completeness_cmd.py` — Preserve the command’s return and terminal guidance for the manual-resolution outcome.
  - `DETAIL_FORMAT.md` — Document the reserved audit finding without changing the detail-file H2 schema.
  - `DATA_CONTRACT.md` — Extend the `Recommendation` and saved-review contract for challenge metadata and compatibility.
  - `docs/ARCHITECTURE.md` — Describe ownership of the manual route and its separation from deterministic rewrites.
  - `docs/AUDIT_FLOW.md` — Add the challenge’s parse, block, report, and non-apply flow.
  - `docs/cli/completeness-audit.md` — Explain the high-severity manual finding.
  - `docs/cli/completeness-apply.md` — Explain that the command reports rather than applies a challenge.
  - `tests/test_review.py` — Cover parser admission, evidence retention, sample aggregation, and apply eligibility.
  - `tests/test_convergence.py` — Cover bare and detail-stage blocking.
  - `tests/test_convergence_diagnosis.py` — Cover saved-history visibility and matching.
  - `tests/test_completeness_report.py` — Cover report guidance and preserved timestamp allocation.
  - `tests/cli/test_completeness_cmd.py` — Cover serial and parallel manual outcomes plus unaffected files-coherence behavior.
  - `tests/cli/test_direct_cmd.py` — Verify direct-run and direct-jira stop on the propagated non-success result.

## Implementation

- **Foundational logic:** Route a recognized `tier-challenge` as a high-severity, manual-only `plan-correctness` finding.

- **Use one challenge identity.** Consume step 1’s shared token and fixed `standard` proposal. Keep the finding source as `plan-correctness` so the existing report and conceptual-bar paths continue to work; do not add a source bucket or severity taxonomy.

- **Admit the special behavior only for explicit low risk.** Thread the current plan declaration to `plan_tool/review.py:_parse_plan_audit_findings_with_evidence` through `check_plan_audit` as needed. Only an explicit `risk_profile: low` declaration may receive the high-severity, manual-only treatment. Standard, high, and field-absent plans must keep ordinary finding handling if a response contains the reserved token.

- **Define one evidence admission record.** A low-only `[risk-profile:tier-challenge]` candidate is recognized only with a literal `Evidence:` sub-list containing one or more nonblank entries in the exact form `- <repository anchor>: <concrete contradiction>`. Store each accepted entry as an ordered record with its anchor and contradiction, not as unparsed finding prose. The record belongs to the challenge transport and saved-review schema; step 4 owns the surrounding low-only policy-class marker.

- **Fail closed on unusable evidence.** A missing heading, blank entry, or entry without both an anchor and contradiction triggers one response-format retry for that audit attempt. If the retry remains malformed, mark the audit unqualified and retain no `Recommendation` from the malformed candidate: it is neither an unsupported manual blocker nor an ordinary finding that can reach an apply writer. Do not infer evidence from the surrounding finding body.

- **Preserve evidence without inventing an escalation.** A recognized challenge carries the declared low tier, the fixed `standard` minimum, and all distinct accepted repository-evidence records collected across sampled audit passes. Normalize duplicate records by their anchor and contradiction while retaining first-pass order. The route must never propose or set `high`; that remains an operator decision.

- **Aggregate only the recognized challenge.** In `plan_tool/review.py:audit_plan_until_stable`, retain one logical challenge across matching passes and merge its ordered, de-duplicated evidence. Keep ordinary findings on the current first-occurrence union rule.

- **Make manual-only enforcement independent of apply options.** Update `plan_tool/review.py:is_apply_eligible`, `triage_reason`, and `plan_tool/cli/completeness_phases.py:_resolve_apply_walk_targets` so interactive mode, `--anchor`, `--no-triage`, `-y`, and `--jobs > 1` cannot dispatch the challenge to `apply_finding`.

- **Fail closed after independent work.** Preserve eligible prose and deterministic work, then return a distinct non-success manual-resolution outcome whenever an unresolved challenge remains. Both serial and parallel completeness-apply routes need the same result. `plan_tool/cli/direct_cmd.py:cmd_direct_run` and `cmd_direct_jira` already stop on a nonzero stage return, so this step changes no direct-command implementation.

- **Reuse the existing blocking policy.** Confirm that `plan_tool/convergence.py:is_blocking_impact` and `is_blocking_finding` retain a recognized high-severity challenge as blocking at `STAGE_BARE` and `STAGE_DETAIL`. Do not alter the current handling of unrelated grounded correctness findings or medium-severity domain exceptions.

- **Keep history focused.** `plan_tool/convergence_diagnosis.py:_finding_from_recommendation`, `_matches`, and `_latest_blocking_findings` must retain the challenge identity and unresolved high-severity visibility. Full evidence remains in the saved `Recommendation` and report; the compact `RunFinding` projection must not turn the challenge into a structural recurrence, split recommendation, or automatic reconciliation route.

- **Keep files-coherence unchanged.** Do not modify `plan_tool/review.py:_files_coherence_recommendation` or the behavior of `plan_tool/cli/completeness_phases.py:_apply_files_coherence`. Real-file citations remain eligible for the existing complete-bundle, serial `allowed_mentions:` rewrite; a challenge neither replaces nor triggers it.

- **Keep timestamped report publication unchanged.** Do not change `plan_tool/completeness_report.py:_report_artifact_paths`, `_reserve_report_timestamp`, or `write_completeness_report` path, suffix, sidecar, or collision behavior. A checkpoint and final report written in the same second must still receive separate timestamp stems.

- **Document by audience.** Update the format and data-contract docs for persisted meaning, the architecture and audit-flow docs for ownership and control flow, and the CLI docs for operator behavior. Step 4 owns audit-prompt wording and ceremony-finding replacement.

## Tests

- `test_tier_challenge_parses_as_high_manual_plan_correctness` — An explicit-low response produces one high-severity `plan-correctness` challenge with the standard proposal and retained evidence.
- `test_non_low_tier_challenge_token_uses_ordinary_finding_handling` — Standard, high, and field-absent plans never receive special manual or blocking behavior.
- `test_tier_challenge_evidence_aggregates_across_audit_samples` — Two passes with distinct evidence retain one challenge with both entries.
- `test_tier_challenge_evidence_record_round_trips` — Challenge metadata survives saved-review serialization and old sidecars remain readable.
- `test_tier_challenge_retries_then_rejects_missing_or_malformed_evidence` — A candidate without a valid evidence record is re-prompted once, then leaves the audit unqualified without a blocker or applyable recommendation.
- `test_tier_challenge_is_not_apply_eligible` — The challenge never enters `apply_finding` despite its conceptual correctness source.
- `test_tier_challenge_blocks_bare_and_detail_audit_stages` — High severity blocks both stage bars without changing unrelated rules.
- `test_tier_challenge_is_latest_unresolved_high_blocker` — An open saved challenge remains visible in convergence diagnosis.
- `test_report_labels_tier_challenge_manual_and_proposes_standard` — The report names the manual decision and does not advertise an apply command.
- `test_completeness_apply_reports_unresolved_tier_challenge_in_serial_and_parallel_modes` — Both routes avoid writers and return non-success.
- `test_direct_pipelines_halt_on_tier_challenge_manual_resolution` — Direct-run and direct-jira do not enter execution or export after the non-success result.
- `test_files_coherence_apply_still_runs_independently_of_tier_challenge` — The existing serial complete-bundle rewrite remains available.
- `test_same_second_checkpoint_and_final_allocate_distinct_report_pairs` — Report timestamp allocation remains unchanged.

### Tests for this step

- `tests/test_review.py::test_tier_challenge_parses_as_high_manual_plan_correctness` — Pins explicit-low parsing, severity, proposal, and evidence.
- `tests/test_review.py::test_non_low_tier_challenge_token_uses_ordinary_finding_handling` — Pins compatibility for every non-low state.
- `tests/test_review.py::test_tier_challenge_evidence_aggregates_across_audit_samples` — Pins the challenge-only union exception.
- `tests/test_review.py::test_tier_challenge_retries_then_rejects_missing_or_malformed_evidence` — Pins the evidence grammar, one retry, and no-routing failure result.
- `tests/test_review.py::test_tier_challenge_is_not_apply_eligible` — Pins the manual boundary before CLI dispatch.
- `tests/test_convergence.py::test_tier_challenge_blocks_bare_and_detail_audit_stages` — Pins both conceptual bars.
- `tests/test_convergence_diagnosis.py::test_tier_challenge_is_latest_unresolved_high_blocker` — Pins saved-history visibility.
- `tests/test_completeness_report.py::test_report_labels_tier_challenge_manual_and_proposes_standard` — Pins operator guidance.
- `tests/test_completeness_report.py::test_same_second_checkpoint_and_final_allocate_distinct_report_pairs` — Pins unchanged timestamped persistence.
- `tests/cli/test_completeness_cmd.py::test_completeness_apply_reports_unresolved_tier_challenge_in_serial_and_parallel_modes` — Pins all manual-resolution routes.
- `tests/cli/test_completeness_cmd.py::test_files_coherence_apply_still_runs_independently_of_tier_challenge` — Pins the unaffected deterministic rewrite.
- `tests/cli/test_direct_cmd.py::test_direct_pipelines_halt_on_tier_challenge_manual_resolution` — Pins existing direct-pipeline propagation.

Every listed test, plus `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- A recognized challenge remains one high-severity `plan-correctness` finding with the declared low tier, proposed `standard` minimum, and every distinct accepted evidence record.
- Every accepted evidence record identifies one repository anchor and its concrete contradiction; malformed challenge output is retried once then leaves the audit unqualified without a recommendation.
- The special behavior applies only to explicitly low plans.
- The challenge blocks both bare and detail-grounded completeness audits.
- Completeness-apply never sends the challenge to `apply_finding`, regardless of mode or flags.
- An unresolved challenge returns a non-success manual-resolution outcome in serial and parallel modes.
- Existing direct pipelines stop before run or Jira export when that outcome propagates.
- Saved reports retain enough data to display the challenge as an unresolved high-severity blocker across reruns.
- Files-coherence retains its existing `allowed_mentions:` rewrite and complete-detail-bundle gate.
- Same-second checkpoint and final report writes retain distinct timestamped artifact stems.
- The named tests in `tests/test_review.py`, `tests/test_convergence.py`, `tests/test_convergence_diagnosis.py`, `tests/test_completeness_report.py`, `tests/cli/test_completeness_cmd.py`, and `tests/cli/test_direct_cmd.py` pass.

## References

- [CommonMark Specification 0.31.2](https://spec.commonmark.org/0.31.2/) — Reference the heading and list syntax used by the conceptual-audit response format.
- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover tier states and apply modes without duplicating fixtures.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Keep the result proportionate by surfacing one evidence-backed operator decision instead of adding a ceremony-writing route.
- **The plan’s “## Step intent”** — Limit the change to the manual challenge route; do not decide whether a particular repository surface refutes the tier.
- **The plan’s “## Out of scope”** — Do not change the risk-profile field, generic correctness scoring, or existing direct-command behavior beyond its established nonzero-stage propagation.
- **The plan’s “Allowed behavior changes”** — Restrict new behavior to the tier-aware finding kind; plans without an explicit declaration retain current behavior.

## Deferred

- Tier-aware audit prompting and replacement of overlapping ceremony findings — Step 4 owns audit emission and replacement after this manual route exists.
