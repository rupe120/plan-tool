> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-remediation-3a-accounting-core.md`.
> Preserved here for history; do not edit.

## Overview

Establish one durable conservation rule for reviewed concepts: every active reviewed concept must have one or more exact committed owners or one valid approved structured non-delivery record. Replace scattered `ConceptNode.source_metadata["detail_deferral_step_ids"]` handling with a first-class `ConceptTree` contract, explicit review transitions, resumable `defer|wont_do -> include` regeneration, and read-only completeness enforcement through `plan_tool/review.py:check_concept_coverage()`. This plan runs first in the three-part remediation sequence and consumes the publication transaction API from `concept-remediation-1-publication-transactions`, the authoring boundary from `concept-remediation-2-authoring-boundary-hardening`, and the exact concept ownership rules from `concept-signoff-integrations`.

## Problem statement

Concept accounting is currently scattered through `ConceptNode.source_metadata["detail_deferral_step_ids"]` and can treat weak signals such as a `wont_do` token, unsigned proposal, title match, or prose reference as if they established coverage. The system lacks a durable, explicitly reviewed representation of non-delivery and a safe transition from parked accounting to replacement delivery. As a result, malformed, stale, contradictory, or dangling ownership information can obscure whether every active reviewed concept is actually delivered or validly parked.

## Architecture

Add one persisted record type, such as `NonDeliveryRecord`, containing a stable `record_id`, exact `concept_id`, `defer` or `wont_do` disposition, rationale/evidence, explicit review/approval state, immutable `origin_ref`, relocatable `artifact_ref`, an ordered unique tuple of positive `linked_step_ids`, and bounded provenance. Derive `record_id` from a domain-tagged, length-prefixed SHA-256 encoding of `concept_id`, disposition, and immutable `origin_ref`, in that order. Exclude `artifact_ref`, `linked_step_ids`, rationale, and review state so artifact renames and routing changes do not create a new occurrence. Document the exact bytes and pin a golden vector.

Separate structural decoding from semantic publication validation. Strict decoding rejects malformed shape, duplicate keys and IDs, unknown fields, invalid enum values, and a `record_id` that does not match its identity inputs, while still permitting structurally valid records with unknown concepts or dangling routes to load for completeness diagnostics. A stricter candidate-publication validator rejects those semantic defects before new generation is written. Migrate valid legacy detail-deferral metadata deterministically, reject ambiguous or malformed legacy values, remove the legacy key from newly persisted sidecars, and register every persisted shape in `plan_tool/data_contract.py` and `DATA_CONTRACT.md`.

Extend scoped concept review so new or changed `defer` and `wont_do` records are reviewed with their disposition, evidence, origin, and artifact link. Semantic changes invalidate approval; routing-only changes to `artifact_ref` or `linked_step_ids` do not. Unattended or non-TTY execution cannot create approval.

Represent `defer|wont_do -> include` as a durable pending transition. Retain the approved non-delivery record and parked plan effect while persisting an exact `IncludeRegenerationRequest` for the concept, retained record, destination step, and intended detail artifact. Resume from that request, then publish regenerated detail, plan accounting, request removal, and record removal in one prerequisite transaction. Recoverable failure retains the parked accounting and request; rollback failure reports every uncertain path and requires recovery. Completeness treats the retained record as the effective parked decision while separately validating the reviewed include intent and regeneration request.

Make `plan_tool/review.py:check_concept_coverage()` the single read-only completeness boundary. It remains inert when no current concept record exists; otherwise it reports stable findings for missing exact accounting, unknown concept IDs, dangling routing, unsigned or stale records, semantic contradictions, simultaneous whole-concept delivery and non-delivery, and malformed pending-include combinations. Many-owner delivery remains valid, invalid links never count as coverage, unsigned parked proposals remain a separate nonblocking advisory, and accounting findings are not prose-apply eligible. Keep self-consistency, Markdown/JSON reports, saved audit replay, CLI help, and generated CLI references aligned.

Implementation surfaces include `plan_tool/concept_tree.py`, `plan_tool/concept_sync.py`, `plan_tool/detail.py`, `plan_tool/review.py`, `plan_tool/completeness_report.py`, `plan_tool/data_contract.py`, `plan_tool/cli/scope_review_cmd.py`, `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/completeness_phases.py`, `DATA_CONTRACT.md`, generated completeness CLI documentation, and focused concept-tree, concept-sync, detail, review, data-contract, and CLI tests. `concept-remediation-3b-lifecycle-publication` consumes the persisted records, transition policy, and validation helpers delivered here; `concept-remediation-3c-seed-restoration` depends on both earlier parts.

## Out of scope

- Split/merge routing transforms, scope-out publication, and seed-envelope production belong to `concept-remediation-3b-lifecycle-publication`.
- Create-time seed restoration and the end-to-end lifecycle matrix belong to `concept-remediation-3c-seed-restoration`.
- Publisher internals and model-output hardening remain owned by the prerequisite remediation plans.

## Risks

- **Identity instability — high severity:** including relocatable routing or mutable review fields in `record_id` would mint a new occurrence after artifact renames or structural routing changes. Mitigation: derive identity only from the domain-tagged, length-prefixed encoding of `concept_id`, disposition, and immutable `origin_ref`, and pin the exact bytes with a golden vector.
- **Invalid records accepted as new accounting — high severity:** unknown concepts or dangling routes could be mistaken for coverage. Mitigation: load structurally valid records for diagnostics but reject semantic defects in the stricter candidate-publication validator; invalid links never count as coverage.
- **Ambiguous legacy migration — high severity:** guessing at malformed `ConceptNode.source_metadata["detail_deferral_step_ids"]` values could create false accounting. Mitigation: migrate only valid values deterministically and reject ambiguous or malformed values.
- **Forged or stale approval — high severity:** unattended execution or semantic edits could leave an invalid record approved. Mitigation: unattended or non-TTY execution cannot create approval, and semantic changes invalidate approval.
- **Premature removal during `defer|wont_do -> include` — high severity:** interruption could leave a concept with neither parked accounting nor durable replacement delivery. Mitigation: retain the approved record and request until regenerated detail and plan accounting are published atomically with their removal; recoverable failures retain both.
- **Rollback uncertainty — high severity:** a failed rollback can leave multi-file state uncertain. Mitigation: report all uncertain paths and require recovery; every durable multi-file update uses the prerequisite transaction API.
- **Contradictory pending state — high severity:** a bare include plus a non-delivery record, a request without its retained record, or mismatched concept/origin/target fields could be accepted. Mitigation: validate the reviewed include intent and exact regeneration request separately from the retained effective parked decision.

## Testing

Add focused concept-tree, concept-sync, detail, review, data-contract, and CLI tests covering persisted record identity, the golden identity vector, ordered unique `linked_step_ids`, strict structural decoding, semantic candidate-publication rejection, deterministic legacy migration, approval invalidation, unattended approval prevention, pending-include interruption and recovery, atomic publication, completeness findings, reporting, audit replay, and CLI documentation alignment. Run data-contract checks, CLI reference drift checks, the full suite, and `reconcile-code`.

## Acceptance criteria

- Structured non-delivery records have one documented, golden-tested identity derived from immutable `origin_ref`; relocatable routing fields are excluded.
- One record can represent split fan-out through ordered, unique `linked_step_ids`.
- Structurally valid dangling records load for diagnostics but cannot be newly published.
- Explicit review authors and approves non-delivery records; unattended runs cannot create approval.
- Pending include regeneration survives interruption and removes parked accounting only after replacement delivery is durable.
- Completeness recognizes the valid pending state without accepting a bare decision/record mismatch.
- Every durable multi-file update uses the prerequisite transaction API.
- Focused tests, data-contract checks, CLI reference drift checks, the full suite, and `reconcile-code` pass.

## Deferred

- Lifecycle transforms and seed-envelope publication are assigned to `concept-remediation-3b-lifecycle-publication` because they depend on this plan's accounting core.
- Create-time restoration and the end-to-end lifecycle proof are assigned to `concept-remediation-3c-seed-restoration` because they depend on both earlier parts.
- No work inside the accounting-core boundary is intentionally deferred.
