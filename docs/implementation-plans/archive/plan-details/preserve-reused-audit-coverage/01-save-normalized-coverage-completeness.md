> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Save normalized coverage in completeness audit sidecars

## Summary

Add optional conceptual-audit coverage provenance to saved completeness sidecars. Update `plan_tool/review_persistence.py`, `plan_tool/completeness_report.py`, and `plan_tool/cli/completeness_phases.py` so a known coverage result has one normalized persisted form. Keep absent or malformed legacy coverage distinguishable as unknown while preserving existing freshness and saved-review behavior. On green, save/load, annotation rewrites, the completeness writer, and the reuse read seam retain the same known coverage value.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the persisted coverage change.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The missing provenance problem this step fixes.
- [Input](#input) — Existing coverage and sidecar contracts that constrain the work.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required persistence behavior and boundaries.
- [Tests](#tests) — Focused test coverage for the new sidecar field.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for JSON and dataclass persistence.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that limit this step.
- [Deferred](#deferred) — Follow-up ownership outside this step.

## Why

`plan_tool/cli/completeness_phases.py:_render_completeness_json` can report the conceptual audit’s coverage verdict, but `plan_tool/review_persistence.py:save_review` currently saves findings and fingerprints without that verdict. A fingerprint-fresh reuse can therefore skip the conceptual audit yet lose whether the saved run was budget-limited or confirmed low-yield. Persisting the original normalized value lets the reuse path report what the audit actually established without treating missing legacy data as evidence of a clean result.

## Input

- **Public coverage shape:** `plan_tool/cli/completeness_phases.py:_render_completeness_json` defines the current `coverage` fields: `budget_limited`, `passes_used`, `cap`, the three compatibility-null recommendation fields, and `confirmation_kind`.

- **Coverage producer:** `plan_tool/review.py:audit_plan_until_stable` fills the conceptual audit’s `budget_report`; preserve its existing meanings rather than recalculating coverage from findings or report prose.

- **Saved-review compatibility:** `plan_tool/review_persistence.py:SavedReview`, `save_review`, `load_review`, and `update_annotation` support existing sidecars at the current schema versions. A missing or invalid optional coverage value must load as unknown without changing the existing fingerprint-based freshness verdict. At the public boundary, that unknown is `coverage.evidence_status == "unknown-legacy"` with `budget_limited`, `passes_used`, `cap`, and `confirmation_kind` set to `null`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/review_persistence.py` — Add the optional normalized coverage provenance to `SavedReview` and preserve it through save, load, and annotation rewrites.
  - `plan_tool/completeness_report.py` — Let `write_completeness_report` persist coverage with a completeness sidecar and expose the loaded value through `ReusableAudit`.
  - `plan_tool/cli/completeness_phases.py` — Use the shared normalized coverage shape at the JSON/report persistence boundary.
  - `plan_tool/data_contract.py` — Register the optional saved-review coverage field as conditionally persisted.
  - `DATA_CONTRACT.md` — Document the optional completeness-sidecar coverage object and its unknown legacy state.
  - `tests/test_review_persistence.py` — Cover persistence, legacy tolerance, and annotation rewrite retention.
  - `tests/test_completeness_report.py` — Cover completeness-sidecar writing and reuse-seam exposure.
  - `tests/test_data_contract.py` — Cover registry and documentation drift protection for the new field.

## Implementation

- **Persist one canonical coverage object.** Add an optional `audit_coverage` provenance field to `plan_tool/review_persistence.py:SavedReview`. A known value has `budget_limited: bool`, positive integer `passes_used` and `cap` with `passes_used <= cap`, the three compatibility fields normalized to `null`, and `confirmation_kind` of `null`, `"confirmed-dry"`, or `"confirmed-low-yield"`. Validate it against `audit_plan_until_stable`'s producer states: a budget-limited result has `cap > 1`, `passes_used == cap`, and no confirmation; an unconfirmed non-budget-limited result is the cap-one tuple (`passes_used == cap == 1`, `confirmation_kind == null`); a confirmed result is non-budget-limited, and `confirmed-low-yield` has `passes_used >= 2` (while `confirmed-dry` may be one-pass). Reject all other typed combinations as producer-impossible, including a budget-limited value before its cap or a too-short low-yield confirmation. This preserves the cap-one producer result as observed coverage rather than unknown. Omit the field only when the caller has no captured coverage, so legacy omission stays distinguishable from a known clean result.

- **Keep unknown distinct from clean.** Treat an absent field, a non-object value, wrong field types, unsupported confirmation value, or contradictory coverage state as unknown in `plan_tool/review_persistence.py:load_review`. Do not reject the whole saved review and do not convert unknown into the ordinary false/null JSON default. Project unknown as `evidence_status: "unknown-legacy"` with null verdict fields; Markdown states that coverage confidence is unknown because a reused legacy sidecar lacks saved evidence.

- **Use a shared normalizer and projection.** Put validation and normalization near `plan_tool/review_persistence.py:SavedReview` or another persistence-owned seam, then use it from `plan_tool/cli/completeness_phases.py:_render_completeness_json`, the Markdown coverage-confidence renderer, and the completeness-sidecar write path. The public projection adds `evidence_status`; this prevents JSON, Markdown, and sidecar values from drifting through separate hand-built dictionaries.

- **Preserve existing sidecar lanes.** Thread the optional value through `plan_tool/completeness_report.py:write_completeness_report` into `plan_tool/review_persistence.py:save_review` only when writing a completeness sidecar. Keep ordinary review and reconcile payload behavior, filename selection, schema-version handling, fingerprint calculation, and Jira-grade sidecar suppression unchanged.

- **Retain coverage during walks.** Update `plan_tool/review_persistence.py:update_annotation` so its explicit payload rewrite carries known coverage forward, alongside the existing fingerprints and optional advisory. A walk decision must never erase provenance captured by the audit.

- **Expose, do not reinterpret.** Add the normalized known-or-unknown value to `plan_tool/completeness_report.py:ReusableAudit` so reuse consumers have one read seam. `plan_tool/completeness_report.py:resolve_reusable_audit` must keep its existing plan/code fingerprint checks; missing coverage changes only the coverage result available to later rendering, never whether findings can be reused.

- **Accept fresh coverage at the sidecar boundary.** Extend `plan_tool/cli/completeness_phases.py:_persist_and_present_report` and `plan_tool/completeness_report.py:write_completeness_report` with a selected coverage input so a fresh audit-only result, which currently lives in `finalize_completeness_run`’s `_noniter_budget`, reaches `save_review` as well as an iterate result. Step 2 chooses and supplies the value; this step preserves it in the sidecar.

- **Document the additive contract.** Update `plan_tool/data_contract.py:persisted_dataclass_contracts` and the saved-review sections of `DATA_CONTRACT.md` to show that the field is optional, completeness-specific provenance. State that valid values follow the public `coverage` contract and that absent or malformed legacy values are unknown.

- **Do not infer coverage from Markdown.** Parsing `report_md` or rerunning `plan_tool/review.py:audit_plan_until_stable` would make persistence depend on presentation or spend another audit call. Store only the completed audit’s supplied coverage value.

## Tests

### Tests for this step

- `test_save_load_normalized_audit_coverage` — `tests/test_review_persistence.py` saves a valid coverage result and loads the identical canonical object.

- `test_normalized_audit_coverage_accepts_cap_one_unconfirmed` — `tests/test_review_persistence.py` proves the producer's one-pass (`budget_limited == false`, `passes_used == cap == 1`, `confirmation_kind == null`) result remains observed coverage rather than becoming unknown.

- `test_normalized_audit_coverage_rejects_producer_impossible_tuples` — `tests/test_review_persistence.py` proves a budget-limited result before the cap and a confirmed-low-yield result under two passes load as unknown rather than an observed verdict.

- `test_missing_or_malformed_audit_coverage_is_unknown_but_loadable` — `tests/test_review_persistence.py` proves legacy and malformed optional values preserve the saved findings and load as unknown.

- `test_unknown_audit_coverage_projection_has_no_clean_verdict` — focused JSON and Markdown rendering proves `evidence_status == "unknown-legacy"`, null verdict fields, and the explicit unknown-confidence notice.

- `test_update_annotation_preserves_audit_coverage` — `tests/test_review_persistence.py` proves an annotation rewrite does not drop persisted coverage.

- `test_write_completeness_report_persists_normalized_audit_coverage` — `tests/test_completeness_report.py` verifies `write_completeness_report` places the normalized value in its sibling completeness JSON sidecar.

- `test_resolve_reusable_audit_exposes_saved_audit_coverage` — `tests/test_completeness_report.py` verifies a fingerprint-fresh reusable audit exposes the saved known value without reinterpreting it.

- `test_saved_review_coverage_is_conditionally_persisted` — `tests/test_data_contract.py` verifies the registry marks the field optional and the documented `SavedReview` section names it.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A completeness sidecar written with a valid conceptual-audit coverage result contains one normalized `audit_coverage` object; public rendering adds `coverage.evidence_status == "observed"` without changing known verdict values.

- `plan_tool/review_persistence.py:load_review` returns the known normalized value for a valid field and an explicit unknown value for absent or malformed optional coverage without rejecting the sidecar. Its public projection uses `"unknown-legacy"`, null verdict fields, and the documented Markdown notice rather than a clean/default result.

- `plan_tool/review_persistence.py:update_annotation` retains saved coverage after a walk updates annotations.

- `plan_tool/completeness_report.py:resolve_reusable_audit` exposes saved known coverage while retaining its existing plan/code fingerprint freshness result.

- Fresh audit-only and fresh iterate calls can pass their selected coverage to the completeness sidecar writer; this step preserves it without changing any reuse decision.

- Ordinary review and reconcile sidecars, Markdown-only completeness reports, report filenames, and Jira-grade sidecar suppression retain their current behavior.

- `DATA_CONTRACT.md` and `plan_tool/data_contract.py:persisted_dataclass_contracts` agree that the coverage field is optional persisted provenance.

## References

- [Python `json` — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use for the additive JSON-object and malformed-input handling rules.

- [Python `dataclasses` — Data Classes](https://docs.python.org/3.13/library/dataclasses.html) — Use for the `SavedReview` field and `asdict` serialization behavior.

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Use for JSON object and `null` interoperability semantics.

## Applicable guardrails

- **The plan’s intent:** Store the original coverage verdict as provenance so later reuse can report it without another conceptual audit call.

- **The plan’s “## Out of scope”, audit-policy boundary:** Record existing coverage facts only; do not alter pass budgets, retries, timeouts, low-yield rules, or blocking policy.

- **The plan’s “## Out of scope”, legacy-reuse boundary:** Missing or invalid optional coverage remains reusable for findings and becomes unknown rather than triggering a replacement audit.

- **The plan’s “## Out of scope”, saved-sidecar boundary:** Limit the change to additive completeness-sidecar provenance; leave unrelated saved-review, reconcile, Jira-grade, checkpoint, and filename behavior unchanged.

## Deferred

- `plan_tool/cli/completeness_cmd.py:finalize_completeness_run` reuse-time selection and delivery of the known-or-unknown value to both Markdown and JSON renderers — step 2 owns the caller wiring for fresh audit-only, fresh iterate, and reused audit paths.
