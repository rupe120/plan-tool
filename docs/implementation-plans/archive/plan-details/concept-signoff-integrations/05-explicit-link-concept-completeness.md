> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add explicit-link concept completeness findings

## Summary

Add deterministic completeness findings that compare the signed-off concept record with `plan_tool/schema.py:Step.concept_ids` and the structured deferral links produced by step 4. Update `plan_tool/review.py` so a signed-off concept is covered only by a valid explicit owner or valid structured deferral; never infer coverage from titles, features, or detail prose. Route missing-link findings through the existing self-consistency and blocking paths in `plan_tool/cli/completeness_phases.py`, and give them a specific explanation and remedy in `plan_tool/completeness_report.py`. On green, audit, `--json`, `--fail-on-findings`, and the saved Markdown report agree on every missing concept link.

## Table of Contents

- [Summary](#summary) — The explicit-link audit and its observable result.
- [Why](#why) — Why inferred concept coverage is not reliable enough.
- [Input](#input) — The concept, ownership, and deferral contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The six existing files changed by this step.
- [Implementation](#implementation) — The coverage predicate, finding routing, and report behavior.
- [Tests](#tests) — Unit and CLI cases for ownership, deferrals, blocking, and reporting.
- [Acceptance criteria](#acceptance-criteria) — Observable requirements for completion.
- [References](#references) — Validation semantics relevant to explicit identifiers.
- [Deferred](#deferred) — Ownership-preserving structural remedies owned by later steps.

## Why

Completeness cannot reliably decide that a signed-off concept is covered by comparing its words with a step title, feature tag, or detail prose. Those strings can change without changing responsibility, and unrelated text can look similar enough to hide a real omission. Steps 1, 3, and 4 provide durable concept IDs, reviewed ownership, and structured deferrals, so completeness can now use one deterministic rule: every signed-off concept must point to at least one valid committed owner or a valid structured deferral.

## Input

- **Step 1 — explicit ownership:** step 1 adds `plan_tool/schema.py:Step.concept_ids`. An ID on a step is the authoritative ownership link; an empty list remains valid input and may produce a completeness finding rather than a parse error.
- **Step 3 — reviewed concept record:** step 3 leaves create output with a persisted concept record and accepted concept IDs assigned to owning steps. Use the shipped concept core’s reader, node state, sign-off state, and stable IDs as they exist at implementation time.
- **Step 4 — structured deferrals:** step 4 persists concept-to-step deferral links through the shipped concept-record contract. Only those structured links count; `## Deferred` prose without a recorded concept ID does not.
- **Committed-step rules:** use the existing committed-versus-parked step semantics in `plan_tool/schema.py:StepScope` and `plan_tool/schema.py:Plan`. A parked, removed, or otherwise non-committed step must not satisfy active ownership merely because its `concept_ids` still contain the ID.
- **Existing completeness routing:** `plan_tool/review.py:collect_self_consistency_findings` supplies the `--iterate` blocking signal, while `plan_tool/review.py:_self_consistency_from_smells` supplies the final report and `--fail-on-findings` gate. Both must return the same concept-coverage membership.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/review.py` — implement the explicit ownership-or-deferral coverage check, define its finding source, and add blocking findings to both self-consistency producers without making them apply-eligible.
  - `plan_tool/completeness_report.py` — classify missing concept links under a concept-specific disposition with an accurate heading and operator remedy.
  - `plan_tool/cli/completeness_phases.py` — collect, group, render, and serialize concept findings through the existing smell and self-consistency buckets.
  - `tests/test_review.py` — cover the coverage predicate, inert cases, stable findings, source membership, and exclusion from the apply-fed collector.
  - `tests/test_completeness_report.py` — cover concept-specific disposition counts, heading, explanation, and full finding rendering.
  - `tests/cli/test_completeness_cmd.py` — cover deterministic-phase wiring, grouped Markdown, JSON output, and blocking behavior.

## Implementation

- **Use one explicit coverage predicate.** The foundational logic is: a signed-off concept is complete when at least one valid committed step owns its exact ID or the shipped concept record contains a valid structured deferral for that exact ID. Compare identifiers directly. Do not use title slugs, `Plan.features`, `Step.features`, Markdown searches, fuzzy matching, or concept titles as alternate proof.

- **Build on the shipped concept check.** The execution prerequisite is expected to provide the concept-record reader and may provide `plan_tool/review.py:check_concept_coverage` and the `concept-coverage` source. Confirm the landed symbols at HEAD, then update that public check instead of creating a parallel checker. If the prerequisite names the operation differently, keep one authoritative function and update the callers named below.

- **Audit signed-off commitments only.** Apply the missing-link check to concepts whose reviewed state makes them an authoritative commitment. Unsigned bootstrap or enrichment candidates must remain audit-inert for blocking coverage. Preserve any shipped advisory check for unsigned deferred or `wont_do` concepts; it is a sign-off reminder, not a missing-owner failure.

- **Accept either valid accounting path.** Treat a concept as accounted for when it has:

  - at least one exact `Step.concept_ids` match on a committed step; or
  - a structured deferral that is valid under the shipped concept-record contract.

  A title mention or prose-only deferral must not suppress the finding. An invalid or stale structured link must not count as coverage.

- **Emit one stable finding per uncovered concept.** Use the existing `plan_tool/review.py:Recommendation` and `plan_tool/review.py:_make_rec_id` conventions. The finding should identify the stable concept ID, name the concept for the operator, explain that neither a valid owner nor a valid deferral exists, and recommend the two legitimate remedies: assign the ID to a committed step or record a reviewed structured deferral. Keep the ID stable across step renumbering and prose edits.

- **Keep the finding blocking but non-appliable.** Add `concept-coverage` to `plan_tool/review.py:SELF_CONSISTENCY_SOURCES` and give it `medium` severity so the existing medium-or-higher gate blocks. Deliberately leave it out of `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES`, `plan_tool/review.py:STRUCTURAL_SOURCES`, and `plan_tool/review.py:collect_deterministic_findings`. `apply_finding` cannot safely invent an owner or approve a deferral.

- **Keep both self-consistency producers equal.** Fold the concept check into both `plan_tool/review.py:collect_self_consistency_findings` and `plan_tool/review.py:_self_consistency_from_smells`. One way is to call the same concept-check function from both paths. Preserve the existing parity rule tested by `tests/test_review.py:TestCollectSelfConsistencyFindings`.

- **Do not derive or persist coverage during audit.** Read the current plan and concept record, compute the result, and return recommendations. Completeness must not create a missing concept record, add `concept_ids`, write deferrals, or update the sidecar. A plan with no concept record remains inert unless the shipped core defines a separate integrity finding for a present but unreadable record.

- **Reuse the existing blocking gate.** `plan_tool/cli/completeness_cmd.py:_completeness_has_blocking_findings` already evaluates `self_consistency_recs` at medium or higher. No edit to `plan_tool/cli/completeness_cmd.py` is required: `plan_tool/cli/completeness_phases.py:_run_deterministic_checks` must place the new recommendations in `_DeterministicReport.self_consistency_recs`.

- **Keep advisory sign-off findings separate.** If the shipped core supplies `concept-unsigned-deferral`, route it through `_DeterministicReport.smell_recs` at info severity. It must render and serialize but must not enter `SELF_CONSISTENCY_SOURCES` or affect `has_blocking_findings`.

- **Update every report view.** In `plan_tool/cli/completeness_phases.py`, make the new sources clear in:

  - `_run_deterministic_checks`, which collects and partitions them;
  - `_render_completeness_json`, which preserves `source`, severity, ID, title, and body;
  - `_render_grouped_report`, whose `### Self-consistency` and `### Smells (advisory)` introductions should name the concept cases accurately;
  - the `has_any` calculation, so concept-only findings suppress the all-clear message.

- **Give missing links their own remedy.** The default `plan_tool/completeness_report.py:deferred_kind` result for a non-appliable source is `diagnostic`, whose path/detail repair text is wrong for concept ownership. Add a concept-specific disposition and update all four related surfaces together: `deferred_kind`, `WHY`, `_HEADINGS`, the disposition-summary counter in `build_report_md`, and the deferred-kind rendering loop. The explanation must direct the operator to assign an explicit owner or record a reviewed structured deferral, not to run the prose apply loop.

- **Preserve full finding detail.** `plan_tool/completeness_report.py:build_report_md` and `plan_tool/cli/completeness_phases.py:_render_grouped_report` should render the full recommendation body and stable anchor. Do not reduce the report to a count or clipped title; the concept ID and valid remedies are needed to fix the plan.

## Tests

- `test_concept_coverage_accepts_exact_committed_owner` — a signed-off concept owned through an exact `Step.concept_ids` match produces no finding.
- `test_concept_coverage_accepts_valid_structured_deferral` — a signed-off concept with no owner but a valid structured deferral produces no finding.
- `test_concept_coverage_reports_missing_owner_and_deferral` — a signed-off concept with neither accounting link produces one medium `concept-coverage` recommendation.
- `test_concept_coverage_does_not_infer_from_title_or_features` — matching prose, titles, and feature tags do not suppress a missing explicit link.
- `test_concept_coverage_ignores_non_committed_owner` — an ID carried only by a parked step does not satisfy active ownership.
- `test_concept_coverage_counts_any_surviving_committed_owner` — one valid owner is sufficient when several steps mention the concept ID.
- `test_concept_coverage_reports_each_uncovered_concept_once` — several uncovered IDs produce distinct stable recommendations without duplicates.
- `test_unsigned_concept_does_not_create_blocking_coverage_finding` — unsigned bootstrap or enrichment candidates remain inert for blocking coverage.
- `test_missing_concept_record_is_audit_inert` — absence of the sidecar does not derive, write, or report concept coverage.
- `test_concept_coverage_id_survives_step_renumber_and_prose_edits` — finding identity is based on the concept, not mutable step text.
- `test_concept_coverage_is_self_consistency_source` — the blocking source belongs to `SELF_CONSISTENCY_SOURCES` and not to `APPLY_ELIGIBLE_SOURCES`.
- `test_collect_self_consistency_includes_concept_coverage` — the iterate-loop collector returns the uncovered concept finding.
- `test_self_consistency_producers_have_concept_coverage_parity` — the loop collector and final deterministic phase return identical concept findings.
- `test_collect_deterministic_findings_omits_concept_coverage` — the apply-fed pre/post collector never dispatches the non-appliable finding.
- `test_unsigned_deferral_remains_advisory` — an unsigned deferred concept, when supported by the shipped core, stays info severity and outside the blocking source set.
- `test_deferred_kind_uses_concept_link_remedy` — `concept-coverage` receives the concept-specific disposition instead of the generic structural diagnostic.
- `test_report_renders_concept_link_heading_and_reason` — the saved Markdown explains both valid remedies and includes the full finding body.
- `test_report_counts_concept_link_findings` — the disposition summary counts the new kind without also counting it as a structural diagnostic.
- `test_run_deterministic_checks_collects_concept_findings` — the phase places coverage findings in `self_consistency_recs` and advisory sign-off findings in `smell_recs`.
- `test_grouped_report_renders_concept_coverage_under_self_consistency` — grouped Markdown shows the blocking finding and suppresses the all-clear message.
- `test_grouped_report_renders_unsigned_deferral_under_smells` — the advisory sign-off reminder appears only in the advisory section.
- `test_json_includes_explicit_link_concept_findings` — JSON preserves the source, severity, ID, title, and body.
- `test_medium_concept_coverage_blocks_fail_on_findings` — the existing self-consistency gate treats the medium finding as blocking.
- `test_info_unsigned_deferral_does_not_block` — an advisory concept finding leaves `has_blocking_findings` false by itself.

### Test-creation order (feature step)

Add the `plan_tool/review.py` predicate tests first with the explicit-link implementation. Add self-consistency parity and apply-exclusion tests with the collector wiring, then add report classification tests and CLI rendering, JSON, and blocking tests with their respective integrations. Every new test must be green before this step is considered finished.

## Acceptance criteria

- A signed-off concept with an exact ID on at least one committed step produces no `concept-coverage` finding.
- A signed-off concept with a valid structured deferral produces no `concept-coverage` finding.
- A signed-off concept with neither a valid committed owner nor a valid structured deferral produces exactly one medium `concept-coverage` finding.
- Similar titles, feature tags, and Markdown prose never satisfy concept ownership or deferral.
- Unsigned concepts do not produce blocking coverage findings.
- A missing concept record causes no concept-record write, model call, or derived coverage finding.
- `concept-coverage` appears in `SELF_CONSISTENCY_SOURCES` and remains absent from `APPLY_ELIGIBLE_SOURCES` and `collect_deterministic_findings`.
- `collect_self_consistency_findings` and `_self_consistency_from_smells` return the same concept-coverage membership.
- `completeness-audit --json` includes the concept finding and sets `has_blocking_findings` for medium coverage gaps.
- `completeness-audit --fail-on-findings` returns the existing blocking result when a medium concept-coverage finding is present.
- The grouped and saved Markdown reports show the full concept finding with an owner-or-deferral remedy, not the generic path/detail diagnostic.
- All new tests in `tests/test_review.py`, `tests/test_completeness_report.py`, and `tests/cli/test_completeness_cmd.py` pass.

## References

- [JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation) — Use the identifier and array validation semantics when checking persisted ownership and deferral links.

## Deferred

- **Split ownership distribution** — step 6 requires replacement steps to preserve every source concept ID.
- **Merge ownership union** — step 7 assigns the union of source ownership to the merged step.
- **Re-ground ownership preservation** — step 8 carries concept IDs through re-grounding.
- **Scope-out deferral creation** — step 9 records structured deferrals when no committed owner survives.
- **Inferring ownership from legacy prose** — intentionally out of scope; legacy plans become complete only through explicit ownership or structured deferral links.
