> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add tier-challenge as a high-severity manual finding

## Summary

Add `tier-challenge` as a recognized high-severity `plan-correctness` finding that remains visible in completeness reports and saved-history diagnosis but never reaches an apply writer. Update the parser, recommendation transport, reporting, and completeness-apply routing across `plan_tool/review.py`, `plan_tool/completeness_report.py`, and the completeness CLI modules. Keep the existing `files-coherence` rewrite and timestamped report allocation unchanged. On green, an unresolved challenge returns a non-success manual-resolution result, so existing direct pipelines stop before execution or Jira export.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the manual finding route.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why a tier contradiction needs a manual path.
- [Input](#input) — Upstream policy and saved-finding contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Code, documentation, and test footprint.
- [Implementation](#implementation) — Finding admission, blocking, reporting, and preservation rules.
- [Tests](#tests) — Focused coverage and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for response parsing and test coverage.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this step.
- [Deferred](#deferred) — Work owned by step 4 or later follow-up.

## Why

`plan_tool/review.py:check_plan_audit` currently sends conceptual correctness findings through the ordinary `plan-correctness` route, which `plan_tool/cli/completeness_phases.py:_resolve_apply_walk_targets` can offer to `apply_finding`. Evidence that an explicitly declared low tier is unsuitable must block progress, but no automated rewrite may change the declaration or choose a higher tier for the operator. This step adds that manual boundary before step 4 emits tier-aware audit findings.

## Input

- **Step 1 policy contract:** Consume the shared `tier-challenge` identity and fixed `standard` minimum from step 1’s `plan_tool/plan_directives.py`. Step 1 owns the vocabulary; do not redefine it here.

- **Plan declaration:** Use the `risk_profile` field of `plan_tool/schema.py:Plan` to decide whether special handling applies. `Plan.effective_risk_profile` is not evidence of an explicit low declaration, so legacy plans stay on ordinary finding handling.

- **Conceptual finding transport:** Build on `plan_tool/review.py:Recommendation`, `_parse_plan_audit_findings_with_evidence`, and `plan_tool/convergence.py:CONCEPTUAL_SOURCES`. A recognized challenge remains `plan-correctness`, not a third conceptual source.

- **Saved-review compatibility:** Preserve the recommendation shape written through `plan_tool/completeness_report.py:write_completeness_report` and read by `plan_tool/review_persistence.py`. Challenge-specific fields need defaults so older sidecars remain readable.

- **Preserved paths:** Keep `plan_tool/cli/completeness_phases.py:_apply_files_coherence` and `plan_tool/completeness_report.py:_reserve_report_timestamp` independent of this finding.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Recognize explicit-low tier challenges, retain structured evidence, merge challenge evidence across audit samples, and prevent challenge recommendations from being apply-eligible.
  - `plan_tool/convergence.py` — Keep the existing high-severity blocking result for challenges at both audit stages without changing general severity policy.
  - `plan_tool/convergence_diagnosis.py` — Keep an unresolved challenge visible as a high-severity history blocker without treating it as a structural finding.
  - `plan_tool/completeness_report.py` — Render a clear manual-resolution disposition and avoid apply guidance for a challenge.
  - `plan_tool/cli/completeness_phases.py` — Exclude challenges from serial and parallel apply targets while preserving independent deterministic work and returning the manual-resolution result.
  - `plan_tool/cli/completeness_cmd.py` — Preserve the command’s return and terminal guidance for that result.
  - `DETAIL_FORMAT.md` — Document the reserved audit finding without changing the detail-file H2 schema.
  - `DATA_CONTRACT.md` — Document challenge metadata, persistence, and old-sidecar compatibility under the saved-review contract.
  - `docs/ARCHITECTURE.md` — Assign ownership of the manual route and distinguish it from deterministic rewrites.
  - `docs/AUDIT_FLOW.md` — Describe challenge admission, blocking, reporting, and non-apply control flow.
  - `docs/cli/completeness-audit.md` — Explain the high-severity manual finding to audit operators.
  - `docs/cli/completeness-apply.md` — Explain that the command reports rather than applies a challenge.
  - `tests/test_review.py` — Cover parsing, evidence retention, sample aggregation, and apply eligibility.
  - `tests/test_convergence.py` — Cover bare and detail-stage blocking.
  - `tests/test_convergence_diagnosis.py` — Cover saved-history visibility and stable matching.
  - `tests/test_completeness_report.py` — Cover report guidance, sidecar round-trip behavior, and unchanged timestamp allocation.
  - `tests/cli/test_completeness_cmd.py` — Cover serial and parallel manual outcomes plus unaffected files-coherence behavior.
  - `tests/cli/test_direct_cmd.py` — Verify direct-run and direct-jira stop on the propagated non-success result.

## Implementation

- **Foundational logic:** Route a recognized `tier-challenge` as one high-severity, manual-only `plan-correctness` finding.

- **Admit special behavior only for explicit low risk.** Extend `plan_tool/review.py:_parse_plan_audit_findings_with_evidence` and its `check_plan_audit` caller so the manual route is available only when `Plan.risk_profile` is explicitly low. Standard, high, and undeclared plans keep ordinary finding behavior if their response happens to contain the reserved token.

- **Use one evidence record.** A low-tier candidate marked `[risk-profile:tier-challenge]` must carry a literal `Evidence:` sub-list with one or more nonblank entries in the exact form `- <repository anchor>: <concrete contradiction>`. Preserve each accepted item as ordered anchor-and-contradiction data rather than only as finding prose, so reports and saved audits retain why the operator must reconsider the tier.

- **Fail closed on unusable evidence.** Missing, blank, or incomplete evidence must trigger the existing response-format retry boundary in `plan_tool/review.py:check_plan_audit`. If the retry remains malformed, leave that audit unqualified and do not route a recommendation from the malformed candidate.

- **Keep the proposed direction bounded.** A recognized challenge records the declared low tier, the shared `standard` minimum, and its evidence. It must not propose or apply `high`; choosing a different declaration remains an operator decision.

- **Merge only this finding across samples.** `plan_tool/review.py:audit_plan_until_stable` normally keeps the first occurrence of each finding. Preserve that rule for ordinary findings, but merge ordered, de-duplicated evidence into one recognized challenge when several sampled passes identify the same tier contradiction.

- **Make the manual boundary independent of flags.** Ensure `plan_tool/review.py:is_apply_eligible`, `triage_reason`, and `plan_tool/cli/completeness_phases.py:_resolve_apply_walk_targets` prevent a challenge from reaching `apply_finding` in interactive mode, with `--anchor`, with `--no-triage`, under `-y`, and through `--jobs > 1`.

- **Finish independent work before failing.** Let eligible findings and the existing deterministic paths proceed, then return a distinct non-success manual-resolution result while an unresolved challenge remains. Both serial and parallel completeness-apply paths need the same outcome. `plan_tool/cli/direct_cmd.py:cmd_direct_run` and `cmd_direct_jira` already stop on a nonzero stage result, so no production direct-command change belongs in this step.

- **Reuse existing severity rules.** Confirm through `plan_tool/convergence.py:is_blocking_impact` and `is_blocking_finding` that a recognized high-severity challenge blocks both `STAGE_BARE` and `STAGE_DETAIL`. Do not change treatment of unrelated conceptual findings or medium-severity domain exemptions.

- **Keep history focused.** Preserve the challenge’s stable identity through `plan_tool/convergence_diagnosis.py:_finding_from_recommendation`, `_matches`, and `_latest_blocking_findings`. The compact history projection may omit the full evidence body, but it must keep the unresolved high-severity finding visible and must not classify it as structural recurrence or an automatic reconciliation route.

- **Keep files-coherence unchanged.** Do not change `plan_tool/review.py:_files_coherence_recommendation` or `plan_tool/cli/completeness_phases.py:_apply_files_coherence`. Real-file citations still use the existing complete-bundle, serial `allowed_mentions:` rewrite; a tier challenge neither replaces nor triggers it.

- **Keep timestamped publication unchanged.** Do not change `plan_tool/completeness_report.py:_report_artifact_paths`, `_reserve_report_timestamp`, or `write_completeness_report` filename, suffix, sidecar, and collision behavior. A checkpoint and final report written in the same second must still receive distinct artifact stems.

- **Document by audience.** Put persisted-field meaning in `DETAIL_FORMAT.md` and `DATA_CONTRACT.md`; ownership and control flow in `docs/ARCHITECTURE.md` and `docs/AUDIT_FLOW.md`; and operator behavior in the two completeness CLI documents. Step 4 owns audit-prompt wording and ceremony-request replacement.

## Tests

- `test_tier_challenge_parses_as_high_manual_plan_correctness` — An explicit-low response produces one high-severity `plan-correctness` challenge with the standard minimum and retained evidence.

- `test_non_low_tier_challenge_token_uses_ordinary_finding_handling` — Standard, high, and undeclared plans never receive special manual behavior.

- `test_tier_challenge_retries_then_rejects_malformed_evidence` — A malformed candidate is retried once, then leaves the audit unqualified without a blocker or applyable recommendation.

- `test_tier_challenge_evidence_aggregates_across_audit_samples` — Distinct evidence from two passes yields one challenge with both records in first-seen order.

- `test_tier_challenge_is_not_apply_eligible` — The challenge cannot enter `apply_finding` despite its `plan-correctness` source.

- `test_tier_challenge_blocks_bare_and_detail_audit_stages` — High severity blocks both conceptual stage bars without changing unrelated rules.

- `test_tier_challenge_is_latest_unresolved_high_blocker` — An open saved challenge remains visible in convergence diagnosis.

- `test_tier_challenge_metadata_round_trips_through_completeness_sidecar` — New metadata persists, while an old-shape recommendation still loads safely.

- `test_report_labels_tier_challenge_manual_and_proposes_standard` — The report names the manual decision and does not advertise an apply command.

- `test_completeness_apply_reports_unresolved_tier_challenge_in_serial_and_parallel_modes` — Both paths avoid writers and return non-success after permitted work.

- `test_files_coherence_apply_still_runs_independently_of_tier_challenge` — The existing serial complete-bundle rewrite remains available.

- `test_same_second_checkpoint_and_final_allocate_distinct_report_pairs` — Report timestamp allocation remains unchanged.

- `test_direct_pipelines_halt_on_tier_challenge_manual_resolution` — Direct-run and direct-jira do not enter execution or export after the non-success result.

### Tests for this step

- `tests/test_review.py::test_tier_challenge_parses_as_high_manual_plan_correctness` — Pins explicit-low parsing, severity, proposal, and evidence.

- `tests/test_review.py::test_non_low_tier_challenge_token_uses_ordinary_finding_handling` — Pins compatibility for every non-low state.

- `tests/test_review.py::test_tier_challenge_retries_then_rejects_malformed_evidence` — Pins evidence validation, one retry, and no-routing failure behavior.

- `tests/test_review.py::test_tier_challenge_evidence_aggregates_across_audit_samples` — Pins the challenge-only union exception.

- `tests/test_review.py::test_tier_challenge_is_not_apply_eligible` — Pins the manual boundary before CLI dispatch.

- `tests/test_convergence.py::test_tier_challenge_blocks_bare_and_detail_audit_stages` — Pins both conceptual stage bars.

- `tests/test_convergence_diagnosis.py::test_tier_challenge_is_latest_unresolved_high_blocker` — Pins saved-history visibility.

- `tests/test_completeness_report.py::test_tier_challenge_metadata_round_trips_through_completeness_sidecar` — Pins persistence compatibility.

- `tests/test_completeness_report.py::test_report_labels_tier_challenge_manual_and_proposes_standard` — Pins operator guidance.

- `tests/test_completeness_report.py::test_same_second_checkpoint_and_final_allocate_distinct_report_pairs` — Pins unchanged timestamped persistence.

- `tests/cli/test_completeness_cmd.py::test_completeness_apply_reports_unresolved_tier_challenge_in_serial_and_parallel_modes` — Pins every manual-resolution route.

- `tests/cli/test_completeness_cmd.py::test_files_coherence_apply_still_runs_independently_of_tier_challenge` — Pins the unaffected deterministic rewrite.

- `tests/cli/test_direct_cmd.py::test_direct_pipelines_halt_on_tier_challenge_manual_resolution` — Pins existing direct-pipeline propagation.

Every listed test, plus `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- A recognized challenge remains one high-severity `plan-correctness` finding with the declared low tier, the proposed `standard` minimum, and every accepted evidence record.

- Every accepted evidence record identifies a repository anchor and concrete contradiction; malformed output is retried once, then leaves the audit unqualified without a recommendation.

- Special challenge behavior applies only to explicitly low plans.

- The challenge blocks both bare and detail-grounded completeness audits.

- Completeness-apply never sends the challenge to `apply_finding`, regardless of mode or flags.

- An unresolved challenge returns a non-success manual-resolution outcome in serial and parallel modes.

- Existing direct pipelines stop before run or Jira export when that outcome propagates.

- Saved reports retain enough data to display the challenge as an unresolved high-severity blocker across reruns.

- Files-coherence retains its existing `allowed_mentions:` rewrite and complete-detail-bundle gate.

- Same-second checkpoint and final report writes retain distinct timestamped artifact stems.

- The focused tests in `tests/test_review.py`, `tests/test_convergence.py`, `tests/test_convergence_diagnosis.py`, `tests/test_completeness_report.py`, `tests/cli/test_completeness_cmd.py`, and `tests/cli/test_direct_cmd.py` pass.

## References

- [Models | Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Review explicit model fields used to distinguish declared low risk from legacy defaults.

- [CommonMark Specification 0.31.2](https://spec.commonmark.org/0.31.2/) — Reference heading and list syntax for the conceptual-audit response format.

- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover risk-profile states and apply modes without duplicating fixtures.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Keep the result proportionate by surfacing one evidence-backed operator decision instead of adding a ceremony-writing route.

- **The plan’s “## Step intent”** — Limit behavior to the manual challenge route; do not decide whether any specific repository surface refutes a tier.

- **The plan’s “## Out of scope”** — Leave risk-profile declaration, general correctness scoring, and non-completeness command behavior unchanged beyond existing nonzero-result propagation.

- **The plan’s scope contract, allowed behavior changes** — Restrict new behavior to the tier-aware finding kind; plans without an explicit declaration retain current behavior.

## Deferred

- Tier-aware audit prompting and replacement of overlapping ceremony findings — Step 4 owns audit emission and replacement after this manual route exists.

- Risk-profile classifier and frontmatter changes — The plan’s “## Out of scope” reserves those decisions for the related work.

- Real-model calibration — Canned responses prove parser and routing behavior; production hit-rate measurement needs a separate representative corpus.
