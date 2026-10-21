> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Join create step outcomes to one assessment event

## Summary

Give every create change-type review pass a fresh `assessment_id` and store it on the pass-level assessment plus every interactive step outcome from that pass. Keep step 1’s compact code-state value only on the `create-review` event; `create-step-outcome` events carry the small association key instead. Update `plan_tool/telemetry.py`, `plan_tool/create.py`, and `DATA_CONTRACT.md`, with compatibility coverage in the scoped telemetry, create, analysis, and contract tests. On green, all outcomes from one review point unambiguously to one assessment without repeating its fingerprint.

## Table of Contents

- [Summary](#summary) — Review-level overview of the create telemetry change.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why the current repeated fingerprint does not provide a good association.
- [Input](#input) — Upstream digest and existing create-event contracts this step uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped source, test, and contract changes.
- [Implementation](#implementation) — Required association, ownership, ordering, and compatibility rules.
- [Tests](#tests) — Focused cases for recorder shape, create wiring, analysis, and legacy rows.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Primary references for UUID generation and JSON persistence.
- [Deferred](#deferred) — Related telemetry work outside this step.

## Why

`plan_tool/create.py:_review_step_change_types` already computes one create-time code fingerprint and reuses it across the review loop, but `plan_tool/create.py:_record_step_outcome` persists that same value on every step answer and split attempt. This repeats assessment-level state once per outcome without identifying which exact `create-review` occurrence owns those outcomes. Joining by `plan_slug` and second-precision `DecisionEvent.ts` can collide, while `DecisionEvent.decision_id` is documented as non-unique and intentionally excludes context. A fresh per-pass association keeps the large state on one event, gives every outcome an unambiguous owner, and preserves the existing action-level analysis.

## Input

- **Step 1 output** — step 1 replaces the telemetry code-fingerprint map with its documented compact code-state value and keeps older rows readable. This step treats that value and its empty sentinel as opaque.
- **Create assessment contract** — `plan_tool/telemetry.py:record_create_granularity_assessment` records `kind="granularity"` and `decision=CREATE_DECISION_REVIEW`, including `candidate_fingerprint`, assessment counts, mode, and the code-state value.
- **Create outcome contract** — `plan_tool/telemetry.py:record_create_step_outcome` records `decision=CREATE_DECISION_STEP_OUTCOME`, with the action and step-specific fields in the context mapping on `plan_tool/telemetry.py:DecisionEvent`.
- **Create review lifecycle** — `plan_tool/create.py:_review_step_change_types` emits one assessment for checkpoint, `--yes`, non-TTY, or interactive mode. Only the interactive `while i < len(reviewed)` loop emits step outcomes.
- **Inline outcome contract** — `plan_tool/telemetry_analysis.py:_inline_evidence` and `plan_tool/telemetry_analysis.py:resolve_decision_inline` identify create outcomes by the `(kind, decision)` pair and map the `action` member of `plan_tool/telemetry.py:DecisionEvent`'s context mapping to the existing verdict vocabulary.
- **Historical rows** — existing create events have no assessment association key. They must remain readable and, for outcome rows, inline-resolvable; this step does not reconstruct an association for them.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/telemetry.py` — add the create assessment association to both recorder context shapes and stop forwarding the assessment’s code-state value from `record_create_step_outcome`.
  - `plan_tool/create.py` — mint one association per `_review_step_change_types` call, pass it to the assessment and every outcome, and keep the code-state value assessment-only.
  - `tests/test_telemetry.py` — update direct recorder tests for the association key and assessment-only fingerprint ownership.
  - `tests/test_create.py` — prove one review shares one association, separate reviews do not collide, and split retry paths keep the same association.
  - `tests/test_telemetry_analysis.py` — prove association-bearing and legacy create outcomes retain the same inline resolution and aggregation behavior.
  - `tests/test_data_contract.py` — drift-guard the new context key and its join semantics.
  - `DATA_CONTRACT.md` — document the association, ownership rule, legacy behavior, and distinction from `decision_id` and `candidate_fingerprint`.

`plan_tool/telemetry_analysis.py` is in scope for compatibility, but no production edit is expected if its current context-tolerant mapping already passes the new tests.

## Implementation

The foundational logic is: **every newly recorded create step outcome carries the same fresh `assessment_id` as the single create assessment for that review pass**.

- **Use an explicit per-pass association.** Add an `assessment_id` context value to `plan_tool/telemetry.py:record_create_granularity_assessment` and `plan_tool/telemetry.py:record_create_step_outcome`. Make it required for new producer calls so a future caller cannot silently create an unassociated outcome.

- **Mint the association once.** Generate one opaque, non-empty value near the start of `plan_tool/create.py:_review_step_change_types`, alongside the existing once-per-pass fingerprint work. A random UUID such as `uuid.uuid4().hex` is a suitable approach because separate passes remain distinct even when they share a slug, candidate list, timestamp second, and code state.

- **Keep association creation observational.** Caller-side work does not inherit `record_decision`’s swallow-all-errors guarantee. If association generation fails, the review must continue unchanged and should skip create telemetry for that pass rather than emit outcomes with an empty or fabricated association.

- **Keep one value through every branch.** Pass the same association into `plan_tool/create.py:_record_create_assessment` for checkpoint, `--yes`, non-TTY, and interactive assessments. In the interactive loop, pass it through every `plan_tool/create.py:_record_step_outcome` call, including:
  - accepted, overridden, and previously unclassified answers;
  - `CREATE_ACTION_SPLIT_REQUESTED`;
  - `CREATE_ACTION_SPLIT_ERROR`;
  - `CREATE_ACTION_SPLIT_UNUSABLE`;
  - `CREATE_ACTION_SPLIT_INVALID`;
  - `CREATE_ACTION_SPLIT_APPLIED`;
  - answers for replacement steps after a successful split.

- **Preserve event ordering.** The interactive `create-review` event must be attempted before the first associated outcome. Do not move assessment recording into the per-step loop or emit a second assessment after a split; split attempts and replacement-step answers belong to the original review pass.

- **Gate children on confirmed parent persistence.** Extend the best-effort recorder seam to return an append-success boolean while preserving its swallow-all-errors behavior for callers that ignore the return. Success means the complete newline-terminated parent row was written, including completion of a short write; step 1's locked append helper rolls a detected partial failure back and returns false. `record_create_granularity_assessment` and `_record_create_assessment` propagate that acknowledgement. Emit associated step outcomes only when the assessment append returned success; if the parent append fails, skip all child telemetry for that pass so no valid-looking orphan `assessment_id` is persisted. This acknowledgement changes observational emission only and must not alter the create review.

- **Give the assessment sole ownership of code state.** Continue computing the create-time code-state value once through `plan_tool/create.py:_create_decision_code_fingerprint`, then pass it only through `plan_tool/create.py:_record_create_assessment`. Remove `code_fingerprint` from `_record_step_outcome` and its call sites. Newly written `create-step-outcome` rows must use step 1’s empty fingerprint sentinel.

- **Do not use nearby identifiers as substitutes.**
  - `DecisionEvent.decision_id` cannot be the association because `DATA_CONTRACT.md` documents it as non-unique and its hash omits context.
  - `candidate_fingerprint` identifies equivalent candidate content for deduplication, not one observed review occurrence.
  - `plan_slug` plus `ts` can collide and must not be the primary join.
  - `run_id` is normally empty for this authoring-time flow.

- **Keep the persisted change inside `context`.** This association does not require another `DecisionEvent` field or an additional schema-version bump after step 1. `plan_tool/telemetry.py:read_decisions` should continue accepting old rows whose context lacks `assessment_id`.

- **Preserve analysis meaning.** `plan_tool/telemetry_analysis.py:_inline_evidence` must continue reading the outcome’s `action`, and `resolve_decision_inline` must keep the current action-to-verdict mapping. The added association and absent outcome fingerprint must not change `ResolvedDecision`, `DecisionAggregate`, recommendation thresholds, or the four public outcome values.

- **Document the two identities separately.** In `DATA_CONTRACT.md:Create granularity decisions`, state that `assessment_id` joins one observed `create-review` occurrence to its outcomes, while `candidate_fingerprint` groups repeated observations of equivalent candidate lists. Also state that legacy outcome rows may lack `assessment_id` and remain readable but cannot be linked to one assessment occurrence.

## Tests

- `tests/test_telemetry.py:test_record_create_assessment_roundtrips_assessment_id` — the assessment recorder stores the supplied non-empty association with the assessment context.
- `tests/test_telemetry.py:test_record_step_outcome_carries_assessment_id_without_code_fingerprint` — a new outcome stores the association and uses step 1’s empty code-fingerprint sentinel.
- `tests/test_telemetry.py:test_create_recorders_keep_assessment_and_candidate_identities_distinct` — `assessment_id` and `candidate_fingerprint` remain separate contract values with different meanings.
- `tests/test_telemetry.py:test_legacy_create_outcome_without_assessment_id_is_readable` — an older JSONL outcome lacking the new context key still loads.
- `tests/test_create.py:test_step_outcomes_join_one_assessment` — every answer in a multi-step interactive review shares the assessment event’s `assessment_id`.
- `tests/test_create.py:test_split_attempts_and_replacement_answers_share_assessment_id` — requested, applied, and replacement-step outcome rows all point to the original assessment.
- `tests/test_create.py:test_separate_reviews_get_distinct_assessment_ids` — two reviews with the same slug and candidate steps do not collide.
- `tests/test_create.py:test_create_assessment_alone_owns_code_fingerprint` — the assessment carries the code-state value and all associated outcomes carry only the association.
- `tests/test_create.py:test_fingerprint_failure_keeps_association_and_review_behavior` — fingerprint computation failure uses the empty sentinel without dropping the association or changing the reviewed steps.
- `tests/test_create.py:test_assessment_id_failure_skips_create_telemetry_without_breaking_review` — association generation failure does not alter prompts, results, or exceptions and leaves no unassociated create events.
- `tests/test_create.py:test_failed_assessment_append_skips_associated_outcomes` — a best-effort parent append failure preserves the review result and writes no child rows carrying the orphaned association.
- `tests/test_create.py:test_partial_assessment_append_failure_skips_associated_outcomes` — a partial parent append that is rolled back returns false and suppresses every child outcome.
- `tests/test_telemetry_analysis.py:test_associated_create_outcome_keeps_inline_mapping` — an outcome with `assessment_id` and no fingerprint maps from `action` exactly as before.
- `tests/test_telemetry_analysis.py:test_legacy_create_outcome_keeps_inline_mapping` — an outcome without `assessment_id` still resolves inline.
- `tests/test_telemetry_analysis.py:test_create_association_does_not_change_aggregate_buckets` — assessment and outcome rows remain grouped by their existing `(kind, decision)` values.
- `tests/test_data_contract.py:test_create_granularity_context_keys_documented` — the create contract lists `assessment_id`.
- `tests/test_data_contract.py:test_create_assessment_join_semantics_documented` — the contract states assessment-only fingerprint ownership, per-pass association, collision avoidance, and legacy behavior.

### Test-creation order (feature step)

Add the recorder-shape and legacy-row tests in `tests/test_telemetry.py` with the `plan_tool/telemetry.py` change. Add the real review-pass tests in `tests/test_create.py` while wiring `plan_tool/create.py`, then add analysis and documentation drift tests in `tests/test_telemetry_analysis.py` and `tests/test_data_contract.py`. Every new test must be green before this step is considered finished.

## Acceptance criteria

- One call to `plan_tool/create.py:_review_step_change_types` uses one non-empty `assessment_id` for its `create-review` event and every `create-step-outcome` it emits.
- Two separate review calls receive different associations even when their slug, candidate steps, timestamp second, and code state match.
- The interactive assessment is attempted before any outcome carrying its association.
- Every newly written associated outcome has a successfully appended assessment earlier in the same pass; a failed assessment append suppresses child telemetry without changing review behavior.
- Split requests, failures, retries, successful splits, and replacement-step answers remain associated with the original review assessment.
- A newly recorded `create-review` event carries step 1’s compact code-state value.
- Newly recorded `create-step-outcome` events do not repeat that code-state value and instead carry only their compact assessment association plus existing outcome context.
- `DecisionEvent.decision_id`, `candidate_fingerprint`, `plan_slug`, and `run_id` retain their existing meanings.
- Schema-v1/v2 rows and rows written under step 1 remain readable when `assessment_id` is absent.
- Legacy and association-bearing create outcomes produce the same `resolve_decision_inline` verdict for the same `action`.
- Existing `(kind, decision)` aggregation and the four public outcome values remain unchanged.
- Association generation, fingerprint computation, and recorder failures do not change create’s prompts, returned steps, or failure behavior.
- `DATA_CONTRACT.md:Create granularity decisions` documents parent-append acknowledgement, orphan suppression, assessment-only fingerprint ownership, and legacy rows. This is the declared `DATA_CONTRACT.md` deliverable for step 2.
- The focused tests in `tests/test_telemetry.py`, `tests/test_create.py`, `tests/test_telemetry_analysis.py`, and `tests/test_data_contract.py` pass.

## References

- [Python uuid — UUID objects according to RFC 9562](https://docs.python.org/3/library/uuid.html) — Use `uuid4()` and its compact hexadecimal form as the recommended fresh per-review association.
- [Python json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Check JSON encoding and decoding behavior for the added context key and legacy-row compatibility.

## Deferred

- **Historical association backfill** — existing outcome rows lack enough information for a guaranteed one-assessment join and remain unassociated.
- **Assessment-level analytics or UI** — this step records the relationship but does not add a dashboard, command, or new aggregation vocabulary.
- **Global `DecisionEvent.decision_id` uniqueness** — its documented class-identity behavior remains unchanged; the create association solves only review-pass ownership.
- **Backend-failure and canonical parallel-apply telemetry** — steps 3–5 own those producer-hardening changes and their direct regression coverage.
