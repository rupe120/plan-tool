# Step 8 — Enforce concept conservation through `check_concept_coverage`

## Summary

This step makes `plan_tool/review.py:check_concept_coverage()` the read-only boundary that accounts for every active reviewed concept. It replaces legacy metadata-based coverage with exact committed ownership, approved `NonDeliveryRecord` state, and the pending-include contract from steps 6 and 7. The completeness phases, saved reports, JSON output, blocking gate, and generated CLI documentation will present the same stable findings without sending them to a prose apply path. On green, valid delivery and parked states pass, while missing, stale, dangling, unsigned, contradictory, or malformed accounting produces clear findings with the correct severity and remedy.

## Table of Contents

- [Summary](#summary) — Overview of the conservation check and its completeness integration.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why the existing legacy coverage rule is insufficient.
- [Input](#input) — Contracts supplied by steps 4, 6, and 7.
- [Files (creates vs edits)](#files-creates-vs-edits) — Production, documentation, and test files changed.
- [Implementation](#implementation) — Conservation rules, finding identity, and reporting flow.
- [Tests](#tests) — Unit, phase, report, CLI, and generated-reference coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Testing guidance relevant to the step.
- [Deferred](#deferred) — Later lifecycle work outside this step.

## Why

`plan_tool/review.py:check_concept_coverage()` currently accepts a bare approved `wont_do` decision or legacy `ConceptNode.source_metadata["detail_deferral_step_ids"]`, and it cannot diagnose durable records, stale approval, unknown IDs, contradictory ownership, or pending include requests. That leaves the completeness gate weaker than the publication rules established by the dependency steps. This step makes the check enforce the plan’s conservation rule from current typed state while keeping invalid historical evidence readable and actionable.

## Input

- **Step 4 accounting validation:** Use the semantic rules supplied by step 4 for exact ownership, known concepts, current step routes, artifact references, disposition agreement, and delivery-versus-non-delivery contradictions. Publication may reject these states; completeness must report them without writing.
- **Step 6 pending state:** Read step 6's planned persisted include-regeneration request collection together with the retained approved records. A complete pending include remains effectively parked and covered while its request is outstanding.
- **Step 7 completed state:** Successful regeneration leaves committed replacement ownership and removes the related requests and retained records. Coverage must then come from the committed owner.
- **Exact delivery:** The plan's `steps[].concept_ids` field counts only on `StepScope.COMMITTED` steps. Several committed owners for one concept remain valid.
- **Durable non-delivery:** Step 2's planned non-delivery record collection counts only through a semantically valid approved record for the exact concept.
- **Read boundary:** A missing `concepts.json` remains inert. A present malformed or stale sidecar must produce a stable diagnostic instead of crashing the audit or being treated as valid coverage.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Replace legacy deferral interpretation in `check_concept_coverage()`, add exhaustive read-only accounting diagnostics, and preserve self-consistency and apply-ineligibility membership.
  - `plan_tool/completeness_report.py` — Update the concept-accounting disposition, headings, counts, remedies, and suggested next steps.
  - `plan_tool/cli/completeness_cmd.py` — Keep concept-accounting findings blocking but non-appliable, and clarify the audit/apply help text.
  - `plan_tool/cli/completeness_phases.py` — Carry one computed concept-accounting set through deterministic checks, Markdown, JSON, and saved-report persistence.
  - `docs/cli/completeness-audit.md` — Regenerate the audit reference with the concept-accounting gate description.
  - `docs/cli/completeness-apply.md` — Regenerate the apply reference to state that concept-accounting findings require review or plan repair and are not walked as prose gaps.
  - `tests/test_review.py` — Replace legacy coverage fixtures and add direct conservation and diagnostic tests.
  - `tests/test_completeness_report.py` — Cover the concept-accounting disposition, rationale, counts, and next actions.
  - `tests/cli/test_completeness_cmd.py` — Cover deterministic collection, blocking, rendering, persistence, and apply exclusion.
  - `tests/cli/test_cli_reference.py` — Pin the regenerated completeness references and their accounting guidance.

## Implementation

The foundational logic is: **every active reviewed concept must have one or more exact committed owners or at least one valid approved non-delivery record, but never effective delivery and non-delivery at the same time.**

- **Replace the legacy predicate.** Remove `_structured_concept_deferral_is_valid()` and stop reading `detail_deferral_step_ids` inside `plan_tool/review.py:check_concept_coverage()`. A bare node decision, title match, feature tag, prose reference, or retired metadata key never establishes coverage.

- **Keep the check read-only.** `check_concept_coverage()` may load and inspect the sidecar, plan, linked steps, and referenced artifacts, but it must not repair, migrate, approve, save, or refresh any state.

- **Preserve the absent-record contract.** Return `[]` when `plan_path` is `None` or `plan_tool/concept_tree.py:concepts_path()` does not exist. Do not derive a fingerprint or create directories in that case.

- **Report unreadable current state.** Catch the typed stale and invalid sidecar errors raised by `plan_tool/concept_tree.py:load_concepts()`. Emit one stable medium `concept-coverage` finding for a stale fingerprint or malformed sidecar and stop deeper accounting analysis, because its plan-relative routes cannot be trusted.

- **Build exact indexes once.** One suitable approach is to index concepts, committed owners, non-delivery records, requests, and current steps before producing findings. Keep sorting deterministic by concept order and stable IDs rather than filesystem or dictionary iteration order.

- **Check ownership in both directions.**
  - An approved concept is delivered when its exact ID appears on at least one committed step.
  - Owners on deferred or out-of-scope steps do not count.
  - Several committed owners are valid.
  - A `Step.concept_ids` value absent from the concept tree is an invalid accounting finding, not an implied concept.

- **Check every non-delivery record.** Report unknown concept IDs, unknown or owner-incompatible linked steps, missing or mismatched artifacts, disposition disagreement, unsigned approval-sensitive state, and other semantic failures defined by step 4. An invalid record never counts toward conservation.

- **Reuse validation rules without parsing errors.** Prefer the typed facts or low-level predicates behind step 4’s semantic accounting validator. Do not derive finding categories by matching `InvalidConceptTreeError` message text. If the publication validator returns only a whole-candidate verdict, keep the reporting walk in `check_concept_coverage()` explicit over the typed records so it can emit stable per-record findings.

- **Treat approval correctly.** An approved record can provide non-delivery accounting. An unreviewed parked proposal emits `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` at `info` and does not cover the concept. Rejected records neither cover nor need an unsigned reminder.

  Recompute the semantic review digest: `approved` with a missing or mismatched digest is a stable stale-approval finding and never counts as coverage.

- **Handle pending include as effective parked accounting.** For the narrow state supplied by step 6, retain the approved record as coverage even though the reviewed concept intent is `include`. Validate the requests separately:
  - each request names the same concept and retained record;
  - every retained approved record that must regenerate has a request;
  - destinations and intended artifacts match current plan state;
  - every request's reviewed mapping digest matches its exact current mapping;
  - every effectively parked concept routed through a destination belongs to the same closed request batch;
  - no committed owner already claims completed delivery.
  
  A malformed request produces a medium accounting finding. Do not also report the concept as unaccounted when its retained record remains valid and effective.

- **Recognize completed regeneration.** After step 7 removes the request and retained record, the replacement committed owner supplies coverage. A bare include decision without committed ownership does not.

- **Report contradictions explicitly.** A concept with effective committed delivery and approved non-delivery is a medium finding even though either side alone could satisfy coverage. Conflicting record dispositions, an include intent with retained records but no complete request set, and requests without retained records also produce medium findings.

- **Report missing conservation last.** After evaluating owners, records, and pending state, emit one medium finding for each active reviewed concept with neither valid delivery nor valid non-delivery. This keeps record-specific defects visible while still stating the final conservation failure.

- **Keep recommendation identity stable.** Continue using `plan_tool/review.py:_make_rec_id()`, but key findings on immutable identifiers:
  - concept-level gaps use the exact concept ID;
  - record defects use `record_id` plus a fixed defect token;
  - request defects use their exact concept, retained-record, and destination identifiers;
  - sidecar-wide stale or malformed findings use a fixed sidecar token.
  
  Titles, rationale, artifact prose, and mutable routing text must not affect recommendation IDs. Keep human-facing anchors based on the exact concept or record ID.

- **Preserve source and severity lanes.** Keep blocking accounting failures under `CONCEPT_COVERAGE_SOURCE` at `medium` and retain that source in `SELF_CONSISTENCY_SOURCES`. Keep unsigned parked proposals under `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` at `info`, outside `SELF_CONSISTENCY_SOURCES`.

- **Keep accounting out of apply.** Do not add `CONCEPT_COVERAGE_SOURCE` to `APPLY_ELIGIBLE_SOURCES`, `collect_deterministic_findings()`, `_CONCEPTUAL_APPLY_SOURCE_RANK`, or `_SAVED_SERIAL_APPLY_SOURCE_RANK`. The valid remedies require exact ownership, record review, or regeneration rather than a prose edit.

- **Keep both self-consistency producers aligned.** `plan_tool/review.py:collect_self_consistency_findings()` and `_self_consistency_from_smells()` must expose identical blocking `concept-coverage` membership. `collect_smell_findings()` may continue carrying the unsigned info reminders into the advisory bucket.

- **Compute once per deterministic phase.** `plan_tool/cli/completeness_phases.py:_run_deterministic_checks()` already places coverage findings in `_DeterministicReport.self_consistency_recs`. Pass that set into `_persist_and_present_report()` instead of calling `check_concept_coverage()` again. Use the same objects for the grouped report, JSON payload, blocking decision, saved audit, and final Markdown.

- **Persist findings without making them replay targets.** Include current `concept-coverage` recommendations in the saved completeness sidecar so audit reuse and historical reports retain the diagnostics. `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply()` must continue filtering them out of `walk_recs`.

- **Update report language.** In `plan_tool/completeness_report.py:deferred_kind()`, `WHY`, `_HEADINGS`, `build_report_md()`, `suggested_next_steps()`, and `suggested_next_step_commands()`, describe the broader class as invalid or missing concept accounting. Point operators toward assigning exact committed ownership, reviewing a non-delivery record, or completing pending regeneration; do not promise that `completeness-apply` can fix it.

- **Keep every output aligned.** `plan_tool/cli/completeness_phases.py:_render_grouped_report()` should name ownership, approved non-delivery, and pending transition defects. `_render_completeness_json()` should retain the full stable finding fields in `checks.self_consistency`, and `_completeness_has_blocking_findings()` should continue gating on medium findings there.

- **Regenerate only the declared references.** Adjust the relevant option help in `plan_tool/cli/completeness_cmd.py:register()` and run `python -m plan_tool.cli_reference --write` so `docs/cli/completeness-audit.md` and `docs/cli/completeness-apply.md` match the live parser. Avoid changing the command-summary text that would also require an undeclared `docs/cli/README.md` edit.

## Tests

- `tests/test_review.py:test_concept_coverage_missing_sidecar_is_inert` — No sidecar returns no findings and does not compute a fingerprint.
- `tests/test_review.py:test_concept_coverage_reports_stale_sidecar` — A present stale sidecar produces one stable medium finding instead of raising.
- `tests/test_review.py:test_concept_coverage_reports_malformed_sidecar` — Invalid persisted shape produces a stable medium diagnostic instead of crashing completeness.
- `tests/test_review.py:test_concept_coverage_accepts_many_committed_owners` — One or more exact committed owners conserve an approved concept.
- `tests/test_review.py:test_concept_coverage_rejects_non_committed_owner` — Ownership on a parked step does not count.
- `tests/test_review.py:test_concept_coverage_reports_unknown_owned_concept` — A step cannot establish a concept by listing an ID absent from the tree.
- `tests/test_review.py:test_concept_coverage_accepts_approved_non_delivery_record` — A valid approved `defer` or `wont_do` record supplies coverage.
- `tests/test_review.py:test_concept_coverage_invalid_record_does_not_cover` — Dangling routes, missing artifacts, or disposition mismatch produce record findings and a missing-accounting finding.
- `tests/test_review.py:test_concept_coverage_unsigned_record_is_advisory_only` — An unreviewed parked record emits info and does not enter the blocking source set.
- `tests/test_review.py:test_concept_coverage_reports_delivery_non_delivery_contradiction` — Committed ownership plus effective approved non-delivery is blocking.
- `tests/test_review.py:test_concept_coverage_accepts_complete_pending_include` — A retained approved record with a complete request stays covered during regeneration.
- `tests/test_review.py:test_concept_coverage_reports_malformed_pending_include` — Bare include, missing retained record, partial requests, or bad destinations produce stable medium findings.
- `tests/test_review.py:test_concept_coverage_accepts_completed_include_regeneration` — Committed replacement ownership with no retained record or request passes.
- `tests/test_review.py:test_concept_coverage_does_not_infer_from_legacy_metadata_or_prose` — Retired metadata, matching titles, tags, and prose do not count.
- `tests/test_review.py:test_concept_coverage_ids_ignore_mutable_prose_and_routing_text` — Finding IDs remain stable across non-identity wording edits.
- `tests/test_review.py:test_concept_coverage_collector_membership_matches_finalize_path` — Both self-consistency producers return the same blocking accounting IDs.
- `tests/test_review.py:test_concept_coverage_stays_out_of_apply_deterministic_findings` — `collect_deterministic_findings()` never returns accounting findings.
- `tests/test_completeness_report.py:test_concept_accounting_uses_specific_disposition_and_remedy` — The curated report counts and explains invalid or missing accounting without suggesting prose apply.
- `tests/test_completeness_report.py:test_concept_accounting_next_steps_name_review_and_regeneration` — Suggested actions cover ownership, record review, and pending regeneration.
- `tests/cli/test_completeness_cmd.py:test_run_deterministic_checks_collects_concept_accounting_findings` — The deterministic phase places blocking findings only in `self_consistency_recs`.
- `tests/cli/test_completeness_cmd.py:test_concept_accounting_computed_once_per_report_phase` — Grouped, JSON, persisted, and blocking consumers reuse one computed set.
- `tests/cli/test_completeness_cmd.py:test_json_preserves_concept_accounting_finding` — JSON retains severity, source, ID, title, and full body.
- `tests/cli/test_completeness_cmd.py:test_medium_concept_accounting_blocks_fail_on_findings` — A medium finding sets the blocking flag and CI exit status.
- `tests/cli/test_completeness_cmd.py:test_saved_audit_keeps_accounting_findings_out_of_apply_walk` — Saved diagnostics remain available for audit history but are not selected by `cmd_completeness_apply()`.
- `tests/cli/test_cli_reference.py:test_completeness_references_document_concept_accounting` — Generated audit and apply references state the gate and its non-appliable remedy.
- `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk` — Both committed references match `plan_tool.cli_reference.render_reference()`.

### Test-creation order (feature step)

1. Add `tests/test_review.py` fixtures for approved records, invalid historical records, pending requests, stale sidecars, and exact committed ownership.
2. Add direct conservation tests for delivery, non-delivery, contradictions, missing accounting, stable IDs, and unsigned advisories.
3. Add collector-parity and apply-exclusion tests before changing completeness orchestration.
4. Add report and CLI tests for Markdown, JSON, blocking, saved-sidecar persistence, and single computation.
5. Update parser help, regenerate the two declared CLI references, and add focused reference assertions.
6. Run the existing completeness report, audit, apply, and reference drift suites.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/review.py:check_concept_coverage()` returns `[]` when no concept sidecar exists.
- A stale or malformed present sidecar produces a stable medium finding instead of escaping an exception.
- Every active reviewed concept passes only with at least one exact committed owner or valid approved non-delivery record.
- Several exact committed owners for one concept are accepted.
- Unknown concepts, dangling routes, missing or mismatched artifacts, unsigned records, disposition mismatches, and contradictory delivery state never count as coverage.
- A valid pending include remains covered by its retained approved record and produces no accounting finding.
- An incomplete or contradictory pending include produces a medium finding without discarding valid retained parked accounting.
- Completed regeneration passes through committed ownership after its request and retained record are removed.
- Legacy `detail_deferral_step_ids`, titles, feature tags, and prose references do not establish coverage.
- Blocking accounting findings use `concept-coverage`; unsigned parked proposals use `concept-unsigned-deferral` at info severity.
- Accounting findings remain absent from `APPLY_ELIGIBLE_SOURCES`, `collect_deterministic_findings()`, and `completeness-apply` walk selection.
- Markdown, JSON, blocking evaluation, and saved completeness artifacts use the same computed accounting recommendations.
- `docs/cli/completeness-audit.md` and `docs/cli/completeness-apply.md` match the generated parser reference.
- All new tests in `tests/test_review.py`, `tests/test_completeness_report.py`, `tests/cli/test_completeness_cmd.py`, and `tests/cli/test_cli_reference.py` pass.

## References

- [pytest API and Built-in Fixtures](https://docs.pytest.org/en/stable/builtin.html) — Use temporary paths, monkeypatching, stream capture, and parametrization for sidecar, report, and CLI tests.

## Deferred

- Split, merge, scope-out, and artifact-move transforms — `concept-remediation-3b-lifecycle-publication` updates durable record and request routing during later lifecycle changes.
- Create-time restoration and the end-to-end lifecycle matrix — `concept-remediation-3c-seed-restoration` restores accounting from machine-readable seeds and proves the full sequence.
- Automatic repair of invalid accounting — this check is read-only; ownership changes, record approval, and regeneration remain explicit operator or transaction workflows.
- Consolidating unrelated completeness phase helpers — this step only removes duplicate concept-coverage computation needed to keep its outputs consistent.
