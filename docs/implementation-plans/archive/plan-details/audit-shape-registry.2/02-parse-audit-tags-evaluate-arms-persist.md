> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Parse audit tags, evaluate arms, and persist the advisory

## Summary

Extend the conceptual-audit flow to capture optional `[audit-step:N]` evidence without changing `Recommendation` routing fields. Use step 1’s `plan_tool/audit_shapes.py` registry to evaluate one fail-closed `arm-clustering` result from the final unioned audit findings, then save the typed `AuditShapeAdvisory` with completeness sidecars. The key decision is that tags remain ephemeral evidence keyed by finding ID; `Recommendation.step_id` stays `None` for conceptual audit findings. When green, a qualifying fresh audit persists one non-executable advisory with an exact audit-input fingerprint and minimal readable, non-routing evidence, while all legacy sidecars and ordinary review behavior continue to work.

## Table of Contents

- [Summary](#summary) — The completed behavior and its main boundary.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The missing evidence path in the current audit flow.
- [Input](#input) — Existing contracts and upstream step output this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — In-scope files and required scope additions.
- [Implementation](#implementation) — Tag parsing, consensus, pure evaluation, and persistence.
- [Tests](#tests) — Focused coverage for the new evidence and sidecar contract.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Primary references for the data and parsing work.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep the result advisory-only.
- [Deferred](#deferred) — Presentation and unrelated audit-shape work left to later steps.

## Why

`plan_tool/review.py:_parse_plan_audit_findings()` currently turns model output directly into plan-level `Recommendation` objects, while `plan_tool/review.py:audit_plan_until_stable()` unions only those recommendations. That leaves no reliable, typed evidence for deciding whether material conceptual findings cluster in one plan arm. Reusing `Recommendation.step_id` would alter an existing apply-routing field, so this step must preserve audit attribution separately and persist only a small advisory snapshot for later presentation.

## Input

- **Step 1 registry:** depend on `plan_tool/audit_shapes.py:AUDIT_SHAPES`, `audit_shape_by_id()`, and `is_advisory_emitter_eligible()`. Step 1 owns the classifications; this step must not add an eligibility allowlist.

- **Conceptual findings:** consume the stable ID, source, severity, impact, complexity, and anchor produced by `plan_tool/review.py:_parse_plan_audit_findings()` and unioned by `plan_tool/review.py:audit_plan_until_stable()`. The new tag evidence stays in a separate internal envelope and never changes the finding record used by normal review routing.

- **Plan order and scope:** validate a tag against the declared order in `plan_tool/schema.py:Plan`, the target step's lifecycle status, and its commitment scope. Only a `scope: committed`, non-`done` step can provide valid attribution; deferred and `wont_do` steps are ineligible even when their lifecycle status is still `pending`.

- **Materiality:** use `plan_tool/convergence.py:is_blocking_impact()` with the one audit-scoped calibration lookup already created by `plan_tool/review.py:audit_plan_until_stable()`. Do not create a second severity or impact policy.

- **Saved-review contract:** extend `plan_tool/review_persistence.py:SavedReview`, `save_review()`, `load_review()`, and `update_annotation()` additively. The new optional advisory field is absent from legacy JSON, which must load as having no advisory.

- **Completeness persistence path:** `plan_tool/cli/completeness_cmd.py:finalize_completeness_run()` and `_run_iterate_convergence_loop()` select fresh audit results; `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint()` and `_persist_and_present_report()` persist them. `plan_tool/completeness_report.py:write_completeness_report()` is the existing forwarding point to `save_review()`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/audit_shapes.py` — add the frozen advisory payload and pure arm-clustering evaluator beside the step 1 registry helpers.
  - `plan_tool/prompts/plan-audit.md` — define the optional literal audit-step tag and examples in the machine-parsed findings contract.
  - `plan_tool/review.py` — parse audit-step evidence, retain it across samples outside `Recommendation`, and evaluate the final normalized audit union.
  - `plan_tool/review_persistence.py` — serialize, load, and preserve an optional `AuditShapeAdvisory` on `SavedReview`.
  - `plan_tool/cli/completeness_phases.py` — carry the fresh advisory through checkpoint and final sidecar persistence without rendering or dispatching it.
  - `plan_tool/cli/completeness_cmd.py` — carry the fresh advisory through audit-only and iterate result handoffs.
  - `plan_tool/completeness_report.py` — forward the optional advisory to the saved-review writer as the persisted-data prerequisite for step 3.
  - `tests/test_audit_shapes.py` — extend the step 1 leaf suite with pure arm-evaluation coverage.
  - `tests/test_review.py` — cover tag grammar, cross-sample consensus, material-union evaluation, and `Recommendation.step_id` non-interference.
  - `tests/test_review_persistence.py` — cover advisory round trips, legacy JSON, and annotation rewrites.
  - `tests/cli/test_completeness_cmd.py` — cover audit-only and iterate persistence handoffs.

## Implementation

- **Make fail-closed arm evaluation the foundational logic.** Extend `plan_tool/audit_shapes.py` with a frozen `AuditShapeAdvisory` and a pure evaluator that accepts only primitive, already-validated evidence: declared step order, material finding IDs, and their consensus targets. Keep this module free of `Recommendation`, `Plan`, CLI, persistence, filesystem, and model-invocation imports.

- **Use the registry as the only emitter decision.** The evaluator must consult `is_advisory_emitter_eligible()` for `arm-clustering`; it must return no result for an unknown or judgment-only shape. Do not compare shape IDs in a second local policy table.

- **Specify one strict tag grammar.** Update `plan_tool/prompts/plan-audit.md` and the retry reminder in `plan_tool/review.py:_PLAN_AUDIT_REPROMPT_SUFFIX` so an optional `[audit-step:N]` appears immediately after `[anchor-slug]`. `N` must match `0` or `-?[1-9][0-9]*` and name one committed plan step whose status is not `done`. Plan-wide, multi-step, uncertain, repeated, malformed, unknown, or prose-only references are unattributed.

- **Parse evidence without changing recommendations.** Have `plan_tool/review.py:_parse_plan_audit_findings()` and `check_plan_audit()` retain an internal per-sample attribution observation keyed by the stable finding ID. The tag must not enter `Recommendation`, alter its ID, leak into title or body text, or populate `Recommendation.step_id`.

- **Make the two-section response contract part of advisory evidence.** After `check_plan_audit()` uses its one retry, a response still missing either required findings heading is malformed for advisory purposes. Preserve its parsed ordinary recommendations under the existing review contract, but mark that completed sample advisory-invalid: do not derive tag observations from it, do not count it as successful consensus evidence, and suppress the advisory for the whole run rather than silently treating a one-axis partial response as a complete sample.

- **Fail closed on an absent audit response too.** A call that raises or exits non-zero remains neutral for `audit_plan_until_stable()`’s existing ordinary convergence accounting and does not discard the unioned ordinary findings, but it is advisory-invalid for the whole audit operation. Record that invalid state beside the ephemeral sample evidence so two otherwise agreeing responses cannot emit an advisory across a failed or absent audit call.

- **Require non-vacuous consensus before trusting a target.** In `plan_tool/review.py:audit_plan_until_stable()`, retain every observation for each stable finding across successful samples. A material finding is attributable only when it appears with the same valid, committed target in at least two successful samples; a missing, invalid, repeated, or conflicting tag in any observed occurrence suppresses the advisory rather than dropping the finding. A one-sample observation is insufficient evidence, even if it has a valid tag.

- **Evaluate the final material union once.** Reuse the audit-scoped `is_blocking_impact()` rule to select material conceptual findings from the normalized union, not from pass counts or report history. Require at least three material findings, valid consensus attribution for every one, and one strict-majority, gap-free, contiguous proper arm of committed steps in declared plan order. A gap partitions runs; ties, a whole-plan arm, insufficient support, a parked target, or any unattributed material finding return no advisory. Store ordered arm step IDs, all material finding IDs, arm finding IDs, and explicit counts so later code can render evidence without reinterpreting findings.

- **Preserve existing list-return callers.** Keep the normal `check_plan_audit()` and `audit_plan_until_stable()` recommendation results usable by current callers. One workable approach is an internal result envelope or optional typed output channel; avoid changing unrelated review and reconciliation callers merely to carry audit-tag data.

- **Own one exact audit-input snapshot operation.** Add a narrow `AuditInputSnapshot` capture/fingerprint helper beside persistence, separate from the existing generic saved-review `compute_plan_fingerprint()`. Read the plan bytes once, parse the `Plan` metadata from those exact bytes, and resolve every run-grade detail input through the same `resolve_detail_artifact()` branch the audit renderer uses—not by separately reading only `step.detail`. This includes an unset pointer's canonical-detail fallback and every explicit-pointer state, including present, missing, and unreadable. Read each selected artifact once and build every sample prompt from this immutable plan/detail snapshot rather than re-reading either source per sample. The helper fingerprints the captured plan bytes, resolver branch, selected path, and explicit `present(bytes)`, `missing`, or `unreadable` state in declared order; do not rely on a top-level detail-directory glob. If the captured bytes cannot be parsed or used consistently to resolve every sample input, omit the advisory. The same helper must recompute freshness later through that same resolver.

- **Separate initial capture from later stale presentation.** Immediately before the first checkpoint/fresh-sidecar save, compare the captured snapshot with disk; if it changed while samples were running, omit the advisory because no saved payload describes a coherent audit input. Once that initial advisory has been saved, later iterate and final-report sidecars must retain the exact original payload even if plan edits make it stale. Step 3 suppresses its display after that mismatch; never restamp, clear, or recompute it from later inputs.

- **Keep JIRA-grade audits outside this transport.** `completeness-audit --grade jira` has a distinct detail bundle and no saved-review reuse contract. Leave that grade's output and persistence behavior unchanged and emit no advisory for it; the run-grade snapshot above is the only producer of `AuditShapeAdvisory`.

- **Thread, do not render or dispatch.** Carry the optional fresh advisory through `plan_tool/cli/completeness_cmd.py:finalize_completeness_run()`, `_run_iterate_convergence_loop()`, and the `_IterateOutcome` handoff in `plan_tool/cli/completeness_phases.py`. Pass it to both `write_pre_apply_audit_checkpoint()` and `_persist_and_present_report()` so checkpoint and final sidecars preserve the same source evidence. Step 3 owns report, JSON, and apply-time presentation.

- **Version the additive saved payload safely.** Add `audit_shape_advisory: Optional[AuditShapeAdvisory]` to `SavedReview` and the `save_review()` / `load_review()` payload path. Write advisory-bearing sidecars as schema version 2; new code must still load version-1 sidecars as legacy records with no advisory. Older code must reject a version-2 sidecar rather than silently load and erase its unknown field, and `update_annotation()` in new code must preserve a present advisory. When an otherwise valid current-version sidecar has an absent, wrong-typed, or structurally invalid *optional* advisory payload, load its ordinary findings and annotations with `audit_shape_advisory=None` (optionally emit one local diagnostic); do not let the optional decision aid block the existing saved-review walk. This tolerance does not weaken rejection of malformed top-level review data or an unsupported schema version. `write_completeness_report()` should pass the field to `save_review()` directly; do not derive or mutate a sibling sidecar after it is written.

- **Keep the payload non-executable and non-prose.** For each material finding, persist its stable ID plus only its already-structured anchor slug and audit axis/source; keep the ordered arm IDs and counts. Do not persist a title, body, summary sentence, step target, or other executable field. The advisory is not a `Recommendation`, does not change blocking state or exit codes, and does not enter `plan_tool/review_walk.py`, action dispatch, or convergence diagnosis.

## Tests

### Tests for this step

Every test below must be green before this step is complete.

- `tests/test_audit_shapes.py:test_arm_clustering_evaluates_a_single_contiguous_majority_arm` — a valid material evidence set produces one immutable advisory with ordered IDs and counts.

- `tests/test_audit_shapes.py:test_arm_clustering_fails_closed_for_ineligible_or_ambiguous_evidence` — judgment-only shapes, insufficient support, ties, gaps that prevent a qualifying run, and whole-plan coverage produce no advisory.

- `tests/test_review.py:test_plan_audit_accepts_only_the_literal_audit_step_tag_slot` — valid tags parse only immediately after the anchor, while malformed, repeated, prose-only, unknown, done-step, and multi-step forms stay unattributed.

- `tests/test_review.py:test_audit_tag_consensus_is_keyed_by_stable_finding_id` — at least two successful samples must agree on one committed target for each material finding; one-sample, parked, conflicting, or untagged evidence suppresses the advisory while ordinary recommendations remain untouched.

- `tests/test_review.py:test_malformed_post_retry_audit_sample_invalidates_only_advisory_evidence` — a response still missing either required findings heading after the retry preserves the current ordinary finding union but contributes no tag evidence and suppresses the run’s advisory.

- `tests/test_review.py:test_failed_audit_call_invalidates_only_advisory_evidence` — an invoker exception or non-zero response stays neutral to the existing finding-union and dry-counter behavior but prevents an advisory even if the other samples agree.

- `tests/test_review.py:test_final_audit_union_uses_existing_materiality_rule_for_arm_evaluation` — the final normalized union, not the pass series, supplies material evidence with one frozen calibration lookup.

- `tests/test_review.py:test_audit_advisory_uses_one_immutable_source_snapshot` — mid-sampling changes to the plan or a resolved detail file neither alter later prompts nor produce the initial advisory; an out-of-tree detail pointer participates in freshness, and generic saved-review fingerprint behavior remains unchanged.

- `tests/test_review.py:test_audit_snapshot_distinguishes_present_missing_and_unreadable_details` — changes among an exact detail file's bytes, missing state, and unreadable state change the snapshot and suppress a new advisory.

- `tests/test_review.py:test_audit_snapshot_parses_the_same_plan_bytes_it_fingerprints` — a plan write between a caller's initial parse and snapshot capture cannot combine an old step map with new fingerprinted bytes; every sampled prompt uses one parsed captured version or no advisory is produced.

- `tests/test_review.py:test_audit_snapshot_matches_run_grade_detail_resolution` — explicit present and missing pointers, an unset pointer's canonical fallback, and unreadable artifacts each use the renderer's selected branch and invalidate freshness when that exact sampled input changes.

- `tests/cli/test_completeness_cmd.py:test_jira_grade_does_not_emit_or_persist_audit_shape_advice` — the unsupported JIRA-grade audit path retains its current output contract and has no advisory.

- `tests/test_review_persistence.py:test_audit_shape_advisory_round_trips_with_a_completeness_review` — a saved advisory preserves its typed IDs, anchor/axis evidence, and exact-input source fingerprint without finding prose or targets.

- `tests/test_review_persistence.py:test_legacy_review_and_annotation_rewrite_preserve_optional_advisory_contract` — a version-1 sidecar loads with no advisory, a version-2 advisory sidecar round-trips, older-version rejection is explicit, and `update_annotation()` does not drop a present advisory.

- `tests/test_review_persistence.py:test_malformed_optional_advisory_does_not_block_saved_review_loading` — bad optional advisory types or fields degrade to no advisory while preserving ordinary findings and annotations; malformed core review fields and unsupported schema versions still reject.

- `tests/cli/test_completeness_cmd.py:test_fresh_audit_persists_the_same_advisory_for_checkpoint_and_final_sidecar` — audit-only and iterate checkpoint/final paths forward the fresh payload without changing conceptual recommendations.

- `tests/cli/test_completeness_cmd.py:test_audit_shape_advisory_does_not_change_completeness_blocking_or_dispatch` — persistence leaves blocking state, exit behavior, and normal finding handling unchanged.

## Acceptance criteria

- A plan-audit finding can supply audit evidence only through the documented optional `[audit-step:N]` tag in its literal position.

- Every conceptual audit `Recommendation` still has `step_id=None`; the tag is never used as apply or walk routing data.

- `arm-clustering` returns at most one advisory and only for a fully attributed material union with at least three findings and a qualifying strict-majority contiguous arm.

- Missing, invalid, conflicting, repeated, plan-wide, tied, or insufficient evidence produces no advisory.

- A completed response that still lacks either required findings section after the one retry contributes no advisory evidence and prevents an advisory for that audit run, without changing ordinary finding parsing.

- An errored or absent audit call prevents an advisory for that audit operation while preserving the existing neutral error accounting and ordinary finding union.

- A saved completeness sidecar can contain an immutable advisory with its shape ID, source plan fingerprint, ordered arm IDs, material and arm finding IDs, and counts.

- Legacy sidecars without `audit_shape_advisory` load successfully, and annotation updates preserve a present advisory.

- A malformed optional advisory is unavailable rather than fatal to an otherwise valid saved review; invalid core sidecar data and unsupported versions still reject.

- The checkpoint and final completeness persistence paths save the same fresh advisory without adding report text, JSON output, apply behavior, blocking behavior, or exit-code changes.

- All listed tests pass.

## References

- [Python dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Use frozen records and safe serialization boundaries for the advisory payload.

- [Python regular-expression operations](https://docs.python.org/3.13/library/re.html) — Define the strict literal `[audit-step:N]` parser.

- [Python JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Preserve the additive, backward-compatible saved-review field.

- [Python hashlib](https://docs.python.org/3.13/library/hashlib.html) — Support the source-plan fingerprint carried by the advisory.

- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Confirm `Plan` and `Step` status and ID handling at the validation boundary.

- [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover the tag and arm-selection failure matrix compactly.

## Applicable guardrails

- **The plan’s `intent`, dedicated advisory transport** — keep audit evidence outside `Recommendation` and persist only the small `AuditShapeAdvisory` payload.

- **The plan’s step 2 intent, reliable evidence boundary** — evaluate only the settled arm-clustering case from step 1 and fail closed when attribution is incomplete.

- **The plan’s `## Out of scope`, dispatch and automation fence** — do not change generic walks, apply dispatch, blocking, exit codes, automatic remedies, or acknowledgement behavior.

- **The plan’s `## Out of scope`, audit-shape boundary** — do not add emitters or causal-history logic for the other audit shapes.

## Deferred

- Fresh, reused, and saved-apply advisory presentation — step 3 owns report, JSON, console, and fingerprint-fresh display behavior.

- `plan_tool/convergence_diagnosis.py:diagnose_convergence()` — cross-run history analysis remains separate from this within-audit evidence check.

- Count-only coverage guidance retirement — step 3 owns removal of the existing `plan_tool/review.py:recommend_audit_passes()` route while preserving coverage compatibility fields.

- Non-`arm-clustering` emitters — remain outside this step under the plan’s audit-shape boundary.
