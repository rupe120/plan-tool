> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add tier-challenge as a high-severity manual finding

## Summary

Add `tier-challenge` as a recognized, high-severity `plan-correctness` finding that remains visible in completeness reports and history but never reaches an apply writer. Update the audit parser and completeness routing in `plan_tool/review.py`, `plan_tool/cli/completeness_phases.py`, and `plan_tool/completeness_report.py`, with matching blocking and history behavior. Keep the existing `files-coherence` frontmatter rewrite and timestamped report allocation unchanged. On green, sampled audit passes retain one challenge with all cited contradiction evidence and the standard minimum; an unresolved challenge yields a non-success manual-resolution result, so existing direct pipelines stop before execution or export.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the manual finding route.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why a dedicated manual route is needed.
- [Input](#input) — Upstream policy and persisted-finding contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Code, documentation, and test footprint.
- [Implementation](#implementation) — Required finding, blocking, reporting, and preservation behavior.
- [Tests](#tests) — Focused coverage and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for the response and test contracts.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Work owned by later steps or separate follow-ups.

## Why

`plan_tool/review.py:check_plan_audit` currently sends every conceptual correctness finding through the normal `plan-correctness` route, which `plan_tool/cli/completeness_phases.py:_resolve_apply_walk_targets` can later offer to `apply_finding`. A finding that the declared low tier is wrong is different: it must be prominent and block execution, but an automated rewrite must not change a risk declaration or choose a higher tier for the operator. This step adds that manual boundary before step 4 starts emitting tier-aware audit findings.

## Input

- **Step 1 policy contract:** Consume the shared `tier-challenge` identity and fixed standard minimum from `plan_tool/plan_directives.py`. Step 1 owns the vocabulary; this step must not restate or fork it.

- **Conceptual finding transport:** Build on `plan_tool/review.py:Recommendation`, `_parse_plan_audit_findings_with_evidence`, and the two conceptual sources in `plan_tool/convergence.py:CONCEPTUAL_SOURCES`. A tier challenge remains a `plan-correctness` finding, not a third conceptual audit axis; its optional, ordered evidence collection belongs only to this recognized finding.

- **Saved-audit contract:** Preserve compatibility with `plan_tool/review_persistence.py:SavedReview.recommendations`, which `plan_tool/completeness_report.py:write_completeness_report` saves and `plan_tool/convergence_diagnosis.py:_finding_from_recommendation` reads back.

- **Existing deterministic route:** Leave `plan_tool/cli/completeness_phases.py:_apply_files_coherence` and `plan_tool/completeness_report.py:_reserve_report_timestamp` as independent contracts. A manual tier challenge must not alter their prerequisites, writes, paths, or ordering.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Recognize the shared tier-challenge identity only for explicitly low plans, retain it as high-severity correctness evidence with a stable evidence collection, and mark it non-applyable.
  - `plan_tool/convergence.py` — Make the stage-bar treatment explicit so a tier challenge blocks both bare and detail audits without changing the general severity policy.
  - `plan_tool/convergence_diagnosis.py` — Preserve the finding’s stable identity and unresolved high-severity status in saved-history diagnosis without treating it as a structural remedy.
  - `plan_tool/completeness_report.py` — Render a clear manual-resolution explanation and avoid suggesting an apply command for this finding.
  - `plan_tool/cli/completeness_phases.py` — Keep tier challenges in reports and blocking calculations while excluding them from serial and parallel apply targets and reporting their unresolved manual state.
  - `plan_tool/cli/completeness_cmd.py` — Return a non-success manual-resolution result and keep command help and terminal guidance accurate for that outcome.
  - `DETAIL_FORMAT.md` — Document the reserved tier-challenge identity at the detail/audit boundary without changing the detail-file H2 schema.
  - `DATA_CONTRACT.md` — Describe how the persisted recommendation representation identifies and preserves a manual tier challenge and its cross-pass evidence collection.
  - `docs/ARCHITECTURE.md` — Describe the manual finding route and its separation from `files-coherence` rewrites.
  - `docs/AUDIT_FLOW.md` — Add the challenge’s audit, blocking, report, and non-apply flow.
  - `docs/cli/completeness-audit.md` — Explain that a tier challenge is a high-severity result requiring human review.
  - `docs/cli/completeness-apply.md` — Explain that this command does not dispatch a tier challenge.
  - `tests/test_review.py` — Cover parsing, identity, high severity, and non-apply eligibility.
  - `tests/test_convergence.py` — Cover both audit-stage blocking behavior.
  - `tests/test_convergence_diagnosis.py` — Cover persisted-history visibility and stable matching.
  - `tests/test_completeness_report.py` — Cover manual report guidance and existing timestamp allocation behavior.
  - `tests/cli/test_completeness_cmd.py` — Cover serial/parallel apply exclusion and preserved files-coherence behavior.
  - `tests/cli/test_direct_cmd.py` — Verify existing direct-run and direct-jira chains halt on the propagated manual-resolution result.

## Implementation

- **Foundational logic:** Route a recognized `tier-challenge` as a high-severity, manual-only `plan-correctness` finding.

- **Keep one canonical identity and evidence record.** Use step 1’s shared token to distinguish the challenge from ordinary correctness findings. Keep its audit source as `plan-correctness` so the existing conceptual-report and stage-bar model remains intact; do not add a third conceptual section or a new generic severity class. Give only the recognized challenge an optional ordered evidence collection on `Recommendation`, with a legacy-empty default. Persist and render that collection through the existing sidecar path. Its entries are normalized solely for deterministic de-duplication while preserving the first cited spelling; unrelated recommendations keep their current representation and first-occurrence union behavior.

- **Admit the special identity only for explicit low.** The parser creates a `tier-challenge` only when the current plan carries an explicit `risk_profile: low` declaration. On standard, high, or field-absent plans, the token receives ordinary existing conceptual-finding handling with no high-severity, manual-only, or blocking override. This defensive admission gate preserves non-low behavior even if a response contains the reserved text unexpectedly.

- **Require the manual outcome.** A recognized challenge must carry the declared low tier, each cited repository-evidence entry that contradicts it, and the proposed `standard` minimum through parsing, cross-pass aggregation, saved recommendation, and report rendering. Parse the prompt's dedicated evidence sub-list when present; safely retain the whole challenge body as one evidence entry for a malformed legacy-shaped response rather than dropping a cited signal. It must never propose or automatically set `high`; an operator may choose that separately.

- **Make blocking explicit but narrow.** Update `plan_tool/convergence.py:is_blocking_impact` and `is_blocking_finding` only as needed to guarantee that the recognized high-severity challenge blocks both `STAGE_BARE` and `STAGE_DETAIL`. Do not change how unrelated grounded correctness findings are scored or how medium findings receive their existing domain treatment.

- **Stop before every apply route, then fail closed.** Update `plan_tool/review.py:is_apply_eligible`, `triage_reason`, and the saved-finding selection in `plan_tool/cli/completeness_phases.py:_resolve_apply_walk_targets` so the challenge cannot reach `apply_finding`. This exclusion must hold for the interactive walk, `--anchor`, `--no-triage`, `-y`, and `--jobs > 1`; options that normally widen application must not override a manual-only finding. After any independent eligible work finishes, an unresolved challenge makes `completeness-apply` return a distinct non-success manual-resolution outcome in both serial and parallel modes. Existing direct-run and direct-jira already halt on a nonzero stage result, so this adds no execution or export behavior.

- **Keep completeness output honest.** Use `plan_tool/completeness_report.py:build_report_md`, `suggested_next_steps`, and related grouped rendering to show the challenge as unresolved operator work, not as a missing detail file, structural split, or an addressable `completeness-apply --anchor` item. `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` should make the same distinction in its help and terminal guidance.

- **Aggregate only this record across samples.** In `plan_tool/review.py:audit_plan_until_stable`, when a later recommendation has the same recognized challenge identity, merge its normalized evidence entries into the existing ordered collection and render the surviving challenge from that collection. Keep the current first-occurrence union for every other recommendation, including reworded ordinary findings. This preserves one manual decision without discarding a consumer, credential, or live-surface citation that only a later pass saw.

- **Preserve history semantics.** Ensure `plan_tool/convergence_diagnosis.py:_finding_from_recommendation`, `_matches`, and `_latest_blocking_findings` retain the challenge’s stable identity, accumulated evidence, and high-severity visibility across saved reports. It may remain a run-readiness blocker, but it must not become a structural-recurrence, split, or automatic reconciliation recommendation.

- **Keep files-coherence unchanged.** Do not modify `plan_tool/review.py:_files_coherence_recommendation` or the behavior of `plan_tool/cli/completeness_phases.py:_apply_files_coherence`: real cited paths may still be added to `allowed_mentions:` only under the existing complete-bundle, serial-apply conditions. A tier challenge must neither replace nor trigger that deterministic rewrite.

- **Keep report publication unchanged.** Do not change the report directory, suffixes, sidecar pairing, or collision handling in `plan_tool/completeness_report.py:_report_artifact_paths`, `_reserve_report_timestamp`, and `write_completeness_report`. A checkpoint and final report written in the same second must continue to receive distinct timestamp stems.

- **Document the contract once per audience.** Update `DETAIL_FORMAT.md` and `DATA_CONTRACT.md` for the artifact and persisted-record rules, `docs/ARCHITECTURE.md` for ownership, `docs/AUDIT_FLOW.md` for control flow, and the two CLI references for operator behavior. Keep the detailed tier-aware audit-emission policy out of this step; step 4 owns the audit prompt and ceremony-finding replacement.

## Tests

- `test_tier_challenge_parses_as_high_manual_plan_correctness` — A synthetic explicit-low conceptual-audit response using the shared identity produces one high-severity correctness recommendation with its challenge evidence intact.

- `test_non_low_tier_challenge_token_uses_ordinary_finding_handling` — Standard, high, and field-absent plans never receive the marker's special manual or blocking behavior.

- `test_tier_challenge_identity_is_stable_when_evidence_is_reworded` — Rewording the evidence does not create a second logical challenge in the audit union or saved history.

- `test_tier_challenge_evidence_record_round_trips` — A structured evidence sub-list persists through the saved recommendation, while an older malformed-shaped response falls back to one retained evidence entry.

- `test_tier_challenge_is_not_apply_eligible` — The manual classification stays outside `apply_finding` even though its source is `plan-correctness`.

- `test_tier_challenge_blocks_bare_and_detail_audit_stages` — The finding blocks both `STAGE_BARE` and `STAGE_DETAIL` and is not demoted by ordinary conceptual-domain handling.

- `test_tier_challenge_is_latest_unresolved_high_blocker` — A saved open challenge remains visible to `plan_tool/convergence_diagnosis.py:render_diagnosis` as a high-severity blocker.

- `test_report_labels_tier_challenge_manual_and_proposes_standard` — The completeness report names the manual decision and standard minimum without advertising an apply command.

- `test_completeness_apply_reports_unresolved_tier_challenge_in_serial_and_parallel_modes` — Neither apply mode calls an apply writer or records the challenge as applied, and both return the manual-resolution result.

- `test_direct_pipelines_halt_on_tier_challenge_manual_resolution` — Existing direct-run and direct-jira chains stop before their execution or export stage when the propagated apply result is non-success.

- `test_files_coherence_apply_still_runs_independently_of_tier_challenge` — A complete serial bundle still receives the existing deterministic `allowed_mentions:` rewrite when applicable.

- `test_same_second_checkpoint_and_final_allocate_distinct_report_pairs` — Existing report-stem allocation remains green without a changed path or timestamp contract.

### Tests for this step

- `tests/test_review.py::test_tier_challenge_parses_as_high_manual_plan_correctness` — Pins parsing, retained evidence, and high severity.

- `tests/test_review.py::test_non_low_tier_challenge_token_uses_ordinary_finding_handling` — Pins the explicit-low admission gate and non-low compatibility.

- `tests/test_review.py::test_tier_challenge_is_not_apply_eligible` — Pins the manual-only boundary before any CLI walk.

- `tests/test_review.py::test_tier_challenge_evidence_record_round_trips` — Pins structured parsing, legacy fallback, and saved-record compatibility.

- `tests/test_convergence.py::test_tier_challenge_blocks_bare_and_detail_audit_stages` — Pins both stage-bar outcomes.

- `tests/test_convergence_diagnosis.py::test_tier_challenge_is_latest_unresolved_high_blocker` — Pins saved-history visibility and stable recurrence matching.

- `tests/test_completeness_report.py::test_report_labels_tier_challenge_manual_and_proposes_standard` — Pins report wording and absence of apply guidance.

- `tests/test_completeness_report.py::test_same_second_checkpoint_and_final_allocate_distinct_report_pairs` — Keeps timestamped report publication unchanged.

- `tests/cli/test_completeness_cmd.py::test_completeness_apply_reports_unresolved_tier_challenge_in_serial_and_parallel_modes` — Pins every apply mode’s exclusion and non-success manual outcome.

- `tests/cli/test_direct_cmd.py::test_direct_pipelines_halt_on_tier_challenge_manual_resolution` — Pins existing direct-chain propagation before run or Jira export.

- `tests/cli/test_completeness_cmd.py::test_files_coherence_apply_still_runs_independently_of_tier_challenge` — Pins the unaffected deterministic rewrite.

Every listed test must be green, along with `uv run pytest tests/ -q -n auto`, before this step is complete.

## Acceptance criteria

- A recognized `tier-challenge` is retained as one high-severity `plan-correctness` finding with the declared tier, every distinct contradiction-evidence entry cited across sampled passes, and the proposed `standard` minimum visible in the report.

- The finding blocks both bare and detail-grounded completeness audits and sets the existing blocking result surfaces accordingly.

- `completeness-apply` never sends a tier challenge to `apply_finding`, regardless of interactive, forced, anchored, or parallel options.

- An unresolved challenge makes `completeness-apply` return a non-success manual-resolution outcome in serial and parallel modes; existing direct pipelines halt before run or Jira export.

- The special identity is admitted only on an explicit low declaration; standard, high, and field-absent plans retain ordinary finding behavior if a response includes the token.

- Saved reports preserve enough identity for `plan-tool convergence` to display an unresolved tier challenge as a high-severity blocker across reruns.

- `files-coherence` keeps its existing deterministic `allowed_mentions:` rewrite behavior and complete-detail-bundle gate.

- Two completeness artifacts written in the same second still receive separate timestamped report and sidecar stems.

- The named tests in `tests/test_review.py`, `tests/test_convergence.py`, `tests/test_convergence_diagnosis.py`, `tests/test_completeness_report.py`, `tests/cli/test_completeness_cmd.py`, and `tests/cli/test_direct_cmd.py` pass.

## References

- [CommonMark Specification 0.31.2](https://spec.commonmark.org/0.31.2/) — Reference the heading and list rules used by the conceptual-audit response format.

- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover audit stage, apply mode, and report-publication variants without duplicating fixtures.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Keep the result proportionate: surface one evidence-backed operator decision instead of creating a new ceremony-writing route.

- **The plan’s “## Step intent”** — Limit this step to the manual challenge route; do not decide whether a particular repository surface refutes the tier.

- **The plan’s “## Out of scope”** — Do not modify risk-profile declaration, generic correctness severity policy, or existing-plan history. Existing direct command code remains unchanged; its established nonzero-stage propagation is the manual gate's final stop.

## Deferred

- Tier-aware audit prompting and replacement of overlapping ceremony requests — Step 4 owns audit emission and replacement policy after this manual route exists.

- Risk-profile classification and declaration changes — The plan’s “## Out of scope” reserves those decisions for the separate follow-up.
