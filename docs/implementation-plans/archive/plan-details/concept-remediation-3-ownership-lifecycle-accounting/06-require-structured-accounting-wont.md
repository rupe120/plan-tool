# Step 6 — Require structured accounting for `wont_do` and dangling concept links

## Summary

This step makes `plan_tool/review.py:check_concept_coverage` enforce the full ownership-or-non-delivery rule delivered by steps 2–4. An approved `wont_do` decision counts only when it has a matching approved structured non-delivery record, while dangling, contradictory, and unaccounted links produce stable blocking findings. `plan_tool/completeness_report.py`, `plan_tool/cli/completeness_phases.py`, and `plan_tool/cli/completeness_cmd.py` must report those findings with remedies that match the defect and must never send them to the prose apply path. On green, Markdown, JSON, saved audits, CLI help, and generated CLI references agree on the same accounting result.

## Table of Contents

- [Summary](#summary) — Overview of the accounting rule and observable result.
- [Why](#why) — Why decisions and links alone cannot prove delivery or deliberate non-delivery.
- [Input](#input) — Structured records and transition outcomes consumed from steps 2–4.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production, documentation, and test changes.
- [Implementation](#implementation) — Validation, finding, reporting, and CLI behavior.
- [Tests](#tests) — Unit and command cases for valid and invalid accounting.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions required for completion.
- [References](#references) — Relevant CLI and test documentation.
- [Deferred](#deferred) — Lifecycle transformations and broader documentation owned by later steps.

## Why

`plan_tool/review.py:check_concept_coverage` currently accepts `node.decision == "wont_do"` without requiring any separate accounting record, and it considers only reviewed concepts that lack coverage rather than every invalid link surrounding them. This lets a decision token stand in for reviewed evidence and lets stale `Step.concept_ids` or non-delivery references remain in the record without a focused diagnostic. Because `concept-coverage` is already medium severity, non-apply-eligible, and part of the self-consistency gate, tightening its foundational predicate now makes audit-only, `--iterate`, `--json`, `--fail-on-findings`, saved-report, and apply-follow-up behavior enforce the same lifecycle rule.

## Input

- **Step 2 output:** consume the durable structured non-delivery record as delivered, including exact concept identity, `defer` or `wont_do` disposition, rationale or evidence, approval state, and stable source or artifact reference. Do not define a second record shape in this step.
- **Step 3 output:** use the shared validity and approval rules for unchanged, replaced, and reviewed non-delivery records. A decision or unapproved proposal must not bypass those rules.
- **Step 4 output:** rely on include-triggered accounting removal occurring only after regenerated detail output is durable. This check reads the resulting current state; it does not repeat regeneration or publication.
- **Delivery links:** continue treating `plan_tool/schema.py:Step.concept_ids` as exact ownership links. Only owners whose scope represents committed delivery count; many committed owners remain valid.
- **Reader boundary:** preserve the current absent-record behavior in `plan_tool/review.py:check_concept_coverage`: if no concept record exists, the check is inert. Run the accounting comparison only after the existing reader returns a current usable record.
- **Verification limit:** this step validates persisted identities, dispositions, approval, and references exposed by the upstream contract. It must not infer ownership or non-delivery from titles, body prose, heuristic similarity, or an LLM response.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — tighten `check_concept_coverage`, replace the legacy metadata-specific validity path with the step-2 contract, detect dangling and contradictory links, and preserve self-consistency producer parity.
  - `plan_tool/completeness_report.py` — classify all structured-accounting findings under an accurate non-apply disposition and render defect-specific remedies and next steps.
  - `plan_tool/cli/completeness_phases.py` — expose the expanded accounting findings consistently in grouped Markdown, JSON, and saved completeness artifacts.
  - `plan_tool/cli/completeness_cmd.py` — keep accounting findings out of apply dispatch, surface them when replaying a saved audit, support accounting anchors without reporting a false “no match,” and update parser-owned help text.
  - `docs/cli/completeness-audit.md` — regenerate the audit reference from the updated parser metadata.
  - `docs/cli/completeness-apply.md` — regenerate the apply reference so it explains that structured-accounting findings are reported but not prose-applied.
  - `docs/cli/README.md` — regenerate the command summaries from the live parser.
  - `tests/test_review.py` — add the accounting validation and producer-parity matrix.
  - `tests/test_completeness_report.py` — cover classification, counts, headings, remedies, and next-step rendering.
  - `tests/cli/test_completeness_cmd.py` — cover grouped/JSON output, blocking behavior, persistence, saved-audit replay, anchors, and non-dispatch.
  - `tests/cli/test_cli_reference.py` — keep the generated-reference drift guard green after regeneration.

## Implementation

The foundational logic is: **a reviewed concept is valid only when it has exact committed ownership or one matching approved structured non-delivery record, and every persisted accounting link must point to a real compatible target.**

- **Make `plan_tool/review.py:check_concept_coverage` the read-only policy boundary.** Compare the loaded concept record, all `Step.concept_ids`, and the step-2 non-delivery records in one pass. Reuse the upstream record validators and accounting helpers; do not add another JSON parser, title matcher, or record-normalization implementation.

- **Evaluate reviewed concepts regardless of decision.** For each reviewed concept:
  - accept one or more exact owners on committed delivery steps;
  - accept an approved structured `defer` or `wont_do` record whose concept ID, disposition, and stable reference pass the upstream contract;
  - do not accept `node.decision == "wont_do"` by itself;
  - do not accept an unsigned non-delivery proposal;
  - do not accept a record whose disposition disagrees with the reviewed decision; and
  - reject simultaneous delivery ownership and approved non-delivery unless the step-2 contract explicitly represents that combination as partial accounting.

- **Keep many-owner delivery valid.** More than one committed step may carry the same exact concept ID. The check must not impose exclusive ownership or treat duplicate ownership across distinct committed steps as a conflict.

- **Audit links in both directions.** Report:
  - a reviewed concept with neither valid delivery nor valid non-delivery;
  - a `Step.concept_ids` entry that names no concept in the current record;
  - a non-delivery record that names an unknown concept;
  - a non-delivery source or artifact reference that no longer points to a valid target under the upstream contract;
  - a record whose approval, disposition, or reviewed fields no longer match the current decision; and
  - contradictory active delivery and non-delivery.

- **Do not count an invalid link as coverage.** A dangling or contradictory record may produce its own finding, but the affected reviewed concept must still be evaluated as unaccounted. Avoid duplicate findings for the same defect by giving each issue one canonical kind and identity.

- **Keep finding identities stable.** Derive each `Recommendation.id` from the defect kind, exact concept ID, and the upstream stable accounting-record or artifact identity when present. Do not hash mutable explanatory prose or rely on title similarity. Preserve deterministic concept order and link order so repeated audits return findings in the same order.

- **Use remedies that match the defect.** The recommendation body and `suggested_action` should distinguish:
  - missing included ownership — assign the exact concept ID to a committed step;
  - missing `defer` or `wont_do` accounting — run the explicit scoped review workflow delivered by step 3;
  - unsigned or changed accounting — review and approve the replacement record;
  - dangling ownership — remove or remap the unknown `Step.concept_ids` entry;
  - dangling non-delivery — repair or replace its structured source or artifact link; and
  - contradictory delivery and non-delivery — choose and publish one consistent reviewed state.

- **Preserve the unsigned advisory lane.** `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` remains info severity, stays outside `SELF_CONSISTENCY_SOURCES`, and never becomes blocking. A reviewed parked decision with missing or invalid structured accounting is different: it produces the medium blocking accounting finding.

- **Preserve self-consistency parity.** `plan_tool/review.py:collect_self_consistency_findings` and `plan_tool/review.py:_self_consistency_from_smells` must return the same blocking accounting membership. Keep these findings out of `plan_tool/review.py:collect_deterministic_findings` and `APPLY_ELIGIBLE_SOURCES`; their remedies require ownership or reviewed structured decisions, not a prose edit by `apply_finding`.

- **Generalize the report disposition.** Update `plan_tool/completeness_report.py:deferred_kind`, `WHY`, `_HEADINGS`, `build_report_md`, `console_summary`, `suggested_next_steps`, and `suggested_next_step_commands` so the existing concept-specific bucket covers invalid accounting, not only a missing link. The heading and rationale must not tell an operator to “assign or defer” when the actual problem is a dangling, unsigned, or contradictory record.

- **Keep every report channel aligned.** In `plan_tool/cli/completeness_phases.py:_run_deterministic_checks`, retain accounting findings in `_DeterministicReport.self_consistency_recs` and out of `smell_recs`. `plan_tool/cli/completeness_phases.py:_render_grouped_report` and `_render_completeness_json` must preserve each finding’s source, stable ID, anchor, severity, and full message. Medium findings must continue feeding `has_blocking_findings`.

- **Persist the same findings that the gate sees.** `plan_tool/cli/completeness_phases.py:_persist_and_present_report` currently calls `check_concept_coverage` again to add `concept-coverage` recommendations to the saved sidecar and curated report. Keep that read-only resampling aligned with the self-consistency producer and deduplicate by stable ID. Do not create or approve accounting records while reporting.

- **Keep `--iterate` non-applying.** `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop` must include medium accounting findings in its blocking signal through `collect_self_consistency_findings`, but never pass them to `apply_finding`. A loop with only structured-accounting findings should stop with those findings still visible, not claim clean convergence.

- **Make saved-audit replay honest.** `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` must recognize saved accounting findings separately from `_SAVED_SERIAL_APPLY_SOURCE_RANK`. Show their full defect-specific remediation, honor `--anchor` selection for them, and exclude them from serial and parallel apply dispatch. Selecting only an accounting finding is a successful report-only action, not a missing-anchor error and not an invitation to run Claude against plan prose.

- **Update parser-owned documentation text.** In `plan_tool/cli/completeness_cmd.py:register`, explain that `completeness-audit` treats reviewed concepts without valid ownership or approved structured non-delivery as blocking self-consistency findings. Explain that `completeness-apply` displays these saved findings but does not apply them. Regenerate `docs/cli/completeness-audit.md`, `docs/cli/completeness-apply.md`, and `docs/cli/README.md` through `python -m plan_tool.cli_reference --write`; do not hand-maintain generated prose.

## Tests

- `tests/test_review.py:test_wont_do_decision_without_record_is_unaccounted` — an approved `wont_do` decision alone produces one medium blocking finding.
- `tests/test_review.py:test_approved_wont_do_record_satisfies_accounting` — a matching approved structured record suppresses the missing-accounting finding.
- `tests/test_review.py:test_unsigned_wont_do_record_does_not_satisfy_accounting` — an unsigned record leaves the concept unaccounted and retains the separate info advisory.
- `tests/test_review.py:test_defer_and_wont_do_require_matching_dispositions` — a record with the wrong disposition does not satisfy the reviewed decision.
- `tests/test_review.py:test_multiple_committed_owners_remain_valid` — several exact committed owners count as valid delivery.
- `tests/test_review.py:test_dangling_step_concept_id_is_reported` — a `Step.concept_ids` value absent from the current concept record produces a stable finding.
- `tests/test_review.py:test_dangling_non_delivery_concept_is_reported` — a structured record naming an unknown concept produces a stable finding.
- `tests/test_review.py:test_dangling_non_delivery_reference_is_reported` — an invalid stable source or artifact link does not count as coverage.
- `tests/test_review.py:test_delivery_and_non_delivery_conflict_is_reported` — simultaneous active delivery and signed non-delivery produces a conflict finding.
- `tests/test_review.py:test_multiple_accounting_defects_have_stable_order_and_ids` — repeated checks preserve finding IDs and deterministic order.
- `tests/test_review.py:test_accounting_findings_have_self_consistency_producer_parity` — `collect_self_consistency_findings` and `_self_consistency_from_smells` return identical accounting membership.
- `tests/test_review.py:test_accounting_findings_never_enter_deterministic_apply_collection` — `collect_deterministic_findings` and `APPLY_ELIGIBLE_SOURCES` exclude the blocking accounting source.
- `tests/test_completeness_report.py:test_accounting_disposition_covers_missing_dangling_and_conflicting_links` — each accounting defect uses the dedicated non-apply disposition.
- `tests/test_completeness_report.py:test_accounting_report_uses_defect_specific_remedies` — the report does not give missing-owner advice for dangling or contradictory records.
- `tests/test_completeness_report.py:test_accounting_summary_counts_each_finding_once` — the disposition summary and detailed section neither drop nor double-count findings.
- `tests/cli/test_completeness_cmd.py:test_grouped_report_renders_structured_accounting_findings` — grouped Markdown includes the full accounting message and remediation.
- `tests/cli/test_completeness_cmd.py:test_json_accounting_finding_is_blocking` — JSON places the medium finding in `checks.self_consistency` and sets `has_blocking_findings`.
- `tests/cli/test_completeness_cmd.py:test_fail_on_findings_fails_for_invalid_accounting` — `--fail-on-findings` returns non-zero for a medium accounting defect.
- `tests/cli/test_completeness_cmd.py:test_iterate_never_dispatches_accounting_findings` — the convergence loop blocks on the finding without calling `apply_finding`.
- `tests/cli/test_completeness_cmd.py:test_saved_audit_persists_all_accounting_findings` — missing, dangling, and conflicting findings retain IDs, anchors, and messages in the saved audit.
- `tests/cli/test_completeness_cmd.py:test_completeness_apply_reports_accounting_without_dispatch` — saved accounting findings are shown but never sent to serial or parallel apply.
- `tests/cli/test_completeness_cmd.py:test_accounting_anchor_is_recognized_as_report_only` — selecting an accounting anchor does not emit a false unmatched-anchor warning.
- `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk` — regenerated completeness references match the live parser.
- `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_index_links_every_command` — the regenerated index still links both completeness commands.

### Test-creation order (feature step)

Add the `tests/test_review.py` accounting matrix with the `check_concept_coverage` changes, including producer parity and apply-exclusion cases. Add `tests/test_completeness_report.py` disposition and remedy cases with the report changes. Then add `tests/cli/test_completeness_cmd.py` grouped, JSON, blocking, persistence, replay, anchor, and non-dispatch cases before regenerating the CLI references. Every new test and all focused existing tests in these files must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/review.py:check_concept_coverage` no longer accepts an approved `wont_do` decision without a matching approved structured non-delivery record.
- Every reviewed concept in a current usable concept record has at least one exact committed owner or one valid matching approved non-delivery record.
- Unsigned records, mismatched dispositions, dangling references, and contradictory delivery/non-delivery do not satisfy coverage.
- Every unknown `Step.concept_ids` value and every dangling structured non-delivery link produces a stable deterministic finding.
- Multiple committed owners remain valid and are not collapsed to one owner.
- `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` remains info-only and nonblocking.
- Medium structured-accounting findings appear in both self-consistency producers, block `has_blocking_findings` and `--fail-on-findings`, and remain absent from `collect_deterministic_findings` and `APPLY_ELIGIBLE_SOURCES`.
- Grouped Markdown, JSON, the curated completeness report, console summaries, suggested next steps, and saved audit recommendations expose the same accounting findings without double-counting.
- `completeness-audit --iterate` never dispatches structured-accounting findings to `apply_finding`.
- `completeness-apply` recognizes saved accounting anchors, prints defect-specific remediation, and never sends those findings through serial or parallel apply.
- `docs/cli/completeness-audit.md`, `docs/cli/completeness-apply.md`, and `docs/cli/README.md` match `plan_tool.cli_reference.render_reference`.
- All new and existing focused tests in `tests/test_review.py`, `tests/test_completeness_report.py`, `tests/cli/test_completeness_cmd.py`, and `tests/cli/test_cli_reference.py` pass.

## References

- [argparse — Parser for Command-Line Options, Arguments and Subcommands](https://docs.python.org/3/library/argparse.html) — Use for the parser-owned help and description text that generates the CLI references.
- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use to cover the reviewed decision, accounting record, ownership, and dangling-link matrix without duplicating fixtures.

## Deferred

- Split and merge transformation of structured non-delivery links — steps 6 and 7 own remapping, conservation, and deduplication during structural changes.
- Scope-out publication of reviewed non-delivery accounting — step 8 owns that caller’s transaction and rollback behavior.
- Seed restoration and create reconciliation — steps 9–11 own machine-readable seed accounting and explicit restoration review.
- Full lifecycle integration coverage — step 12 verifies the completed create, detail, split, merge, re-ground, scope-out, and completeness sequence.
- Operator runbook and backlog reconciliation — step 13 owns `RUNBOOK.md`, architecture guidance, and tracking closure.
- Automatic creation of a covering implementation step — outside this plan; this step reports missing ownership but does not invent delivery work.
