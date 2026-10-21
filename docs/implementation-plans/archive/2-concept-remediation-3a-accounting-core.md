---
title: Concept Remediation 3A Accounting Core
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Move legacy detail deferral handling into shared concept helpers
  files:
  - plan_tool/concept_tree.py
  - plan_tool/detail.py
  - plan_tool/review.py
  - tests/test_concept_tree.py
  - tests/test_detail.py
  - tests/test_review.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/concept-remediation-3a-accounting-core/01-move-legacy-detail-deferral-handling.md
  status: current
- id: 2
  title: Add durable non-delivery records and stable record IDs
  files:
  - plan_tool/concept_tree.py
  - plan_tool/data_contract.py
  - DATA_CONTRACT.md
  - tests/test_concept_tree.py
  - tests/test_data_contract.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/concept-remediation-3a-accounting-core/02-durable-non-delivery-records-stable.md
- id: 3
  title: Migrate valid legacy deferrals into non-delivery records
  files:
  - plan_tool/concept_tree.py
  - plan_tool/concept_sync.py
  - plan_tool/detail.py
  - plan_tool/create.py
  - plan_tool/scope_out.py
  - tests/test_concept_tree.py
  - tests/test_concept_sync.py
  - tests/test_detail.py
  - tests/test_create.py
  - tests/test_scope_out.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/concept-remediation-3a-accounting-core/03-migrate-valid-legacy-deferrals-non.md
- id: 4
  title: Reject invalid accounting before concept publication
  files:
  - plan_tool/concept_tree.py
  - plan_tool/concept_sync.py
  - tests/test_concept_tree.py
  - tests/test_concept_sync.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/concept-remediation-3a-accounting-core/04-reject-invalid-accounting-before.md
- id: 5
  title: Review and approve non-delivery records explicitly
  files:
  - plan_tool/concept_tree.py
  - plan_tool/concept_review.py
  - plan_tool/concept_sync.py
  - plan_tool/cli/scope_review_cmd.py
  - docs/cli/scope-review.md
  - tests/test_concept_tree.py
  - tests/test_concept_review.py
  - tests/test_concept_sync.py
  - tests/cli/test_scope_review_cmd.py
  - tests/cli/test_cli_reference.py
  complexity: high
  change_type: feature
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/concept-remediation-3a-accounting-core/05-review-approve-non-delivery-records.md
- id: 6
  title: Persist pending include regeneration requests
  files:
  - plan_tool/concept_tree.py
  - plan_tool/concept_review.py
  - plan_tool/concept_sync.py
  - plan_tool/data_contract.py
  - plan_tool/cli/scope_review_cmd.py
  - DATA_CONTRACT.md
  - docs/cli/scope-review.md
  - tests/test_concept_tree.py
  - tests/test_concept_review.py
  - tests/test_concept_sync.py
  - tests/test_data_contract.py
  - tests/cli/test_scope_review_cmd.py
  - tests/cli/test_cli_reference.py
  complexity: high
  change_type: feature
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/concept-remediation-3a-accounting-core/06-persist-pending-include-regeneration.md
- id: 7
  title: Resume include regeneration and publish it as one transaction
  files:
  - plan_tool/concept_sync.py
  - plan_tool/detail.py
  - tests/test_concept_sync.py
  - tests/test_detail.py
  complexity: high
  change_type: feature
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/concept-remediation-3a-accounting-core/07-resume-include-regeneration-publish-one.md
- id: 8
  title: Enforce concept conservation through check_concept_coverage
  files:
  - plan_tool/review.py
  - plan_tool/completeness_report.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - docs/cli/completeness-audit.md
  - docs/cli/completeness-apply.md
  - tests/test_review.py
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_cli_reference.py
  complexity: high
  change_type: feature
  depends_on:
  - 4
  - 6
  - 7
  detail: docs/implementation-plans/plan-details/concept-remediation-3a-accounting-core/08-enforce-concept-conservation-through.md
---
# Concept Remediation 3A Accounting Core

## Overview

Establish one durable conservation rule for reviewed concepts: every active reviewed concept must have one or more exact committed owners or one valid approved structured non-delivery record. Replace scattered `ConceptNode.source_metadata["detail_deferral_step_ids"]` handling with a first-class `ConceptTree` contract, explicit review transitions, resumable `defer|wont_do -> include` regeneration, and read-only completeness enforcement through `plan_tool/review.py:check_concept_coverage()`. This plan runs first in the three-part remediation sequence and consumes the publication transaction API from `concept-remediation-1-publication-transactions`, the authoring boundary from `concept-remediation-2-authoring-boundary-hardening`, and the exact concept ownership rules from `concept-signoff-integrations`.

## Problem statement

Concept accounting is currently scattered through `ConceptNode.source_metadata["detail_deferral_step_ids"]` and can treat weak signals such as a `wont_do` token, unsigned proposal, title match, or prose reference as if they established coverage. The system lacks a durable, explicitly reviewed representation of non-delivery and a safe transition from parked accounting to replacement delivery. As a result, malformed, stale, contradictory, or dangling ownership information can obscure whether every active reviewed concept is actually delivered or validly parked.

## Architecture

Add one persisted record type, such as `NonDeliveryRecord`, containing a stable `record_id`, exact `concept_id`, `defer` or `wont_do` disposition, rationale/evidence, explicit review/approval state, immutable `origin_ref`, relocatable `artifact_ref`, an ordered unique tuple of positive `linked_step_ids`, and bounded provenance. Derive `record_id` from a domain-tagged, length-prefixed SHA-256 encoding of `concept_id`, disposition, and immutable `origin_ref`, in that order. Exclude `artifact_ref`, `linked_step_ids`, rationale, and review state so artifact renames and routing changes do not create a new occurrence. Document the exact bytes and pin a golden vector.

Bind approval separately from identity with a persisted semantic review digest over the exact concept, disposition, rationale/evidence, and immutable origin shown to the operator. A migrated legacy record starts unreviewed; no unattended migration may synthesize approval. Every current-schema writer must either publish a fully migrated legacy-free candidate through its owning transaction or refuse without writing.

Separate structural decoding from semantic publication validation. Strict decoding rejects malformed shape, duplicate keys and IDs, unknown fields, invalid enum values, and a `record_id` that does not match its identity inputs, while still permitting structurally valid records with unknown concepts or dangling routes to load for completeness diagnostics. A stricter candidate-publication validator rejects those semantic defects before new generation is written. Migrate valid legacy detail-deferral metadata deterministically, reject ambiguous or malformed legacy values, remove the legacy key from newly persisted sidecars, and register every persisted shape in `plan_tool/data_contract.py` and `DATA_CONTRACT.md`.

Extend scoped concept review so new or changed `defer` and `wont_do` records are reviewed with their disposition, evidence, origin, and artifact link. Semantic changes invalidate approval; routing-only changes to `artifact_ref` or `linked_step_ids` do not. Unattended or non-TTY execution cannot create approval.

Represent `defer|wont_do -> include` as a durable pending transition. Retain the approved non-delivery record and parked plan effect while persisting an exact `IncludeRegenerationRequest` for the concept, retained record, destination step, and intended detail artifact. Resume from that request, then publish regenerated detail, plan accounting, request removal, and record removal in one prerequisite transaction. Recoverable failure retains the parked accounting and request; rollback failure reports every uncertain path and requires recovery. Completeness treats the retained record as the effective parked decision while separately validating the reviewed include intent and regeneration request.

Persist a review digest binding each exact request mapping shown at TTY confirmation. Reject target substitution and destination steps shared with parked concepts outside the same closed request batch. Scoped review also owns write-free-on-failure cancellation and atomic replacement of pending mappings.

Make `plan_tool/review.py:check_concept_coverage()` the single read-only completeness boundary. It remains inert when no current concept record exists; otherwise it reports stable findings for missing exact accounting, unknown concept IDs, dangling routing, unsigned or stale records, semantic contradictions, simultaneous whole-concept delivery and non-delivery, and malformed pending-include combinations. Many-owner delivery remains valid, invalid links never count as coverage, unsigned parked proposals remain a separate nonblocking advisory, and accounting findings are not prose-apply eligible. Keep self-consistency, Markdown/JSON reports, saved audit replay, CLI help, and generated CLI references aligned.

Implementation surfaces include `plan_tool/concept_tree.py`, `plan_tool/concept_sync.py`, `plan_tool/detail.py`, `plan_tool/review.py`, `plan_tool/completeness_report.py`, `plan_tool/data_contract.py`, `plan_tool/cli/scope_review_cmd.py`, `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/completeness_phases.py`, `DATA_CONTRACT.md`, generated completeness CLI documentation, and focused concept-tree, concept-sync, detail, review, data-contract, and CLI tests. `concept-remediation-3b-lifecycle-publication` consumes the persisted records, transition policy, and validation helpers delivered here; `concept-remediation-3c-seed-restoration` depends on both earlier parts.

## References

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Defines JSON syntax and interoperability rules, including unique object-member names relevant to strict sidecar decoding.
- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Documents the SHA-256 byte-oriented API needed to derive and golden-test stable record identifiers.
- [Python json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Covers JSON parsing hooks such as object_pairs_hook that enable duplicate-key detection and controlled structural decoding.
- [Python os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Documents os.replace, fsync, and related filesystem primitives used when implementing durable transactional publication.
- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Explains typed persisted models, strict validation, forbidden extra fields, serialization, and immutable model configuration.
- [Pydantic Validators](https://docs.pydantic.dev/latest/concepts/validators/) — Documents field and model validators for enforcing identity, ordered-unique links, and cross-field state invariants.
- [pytest API and Built-in Fixtures](https://docs.pytest.org/en/stable/builtin.html) — Provides the fixture and testing APIs needed for isolated publication, interruption, rollback, CLI, and filesystem tests.

## Steps

See the `steps:` block in the frontmatter.

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

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- Structured non-delivery records have one documented, golden-tested identity derived from immutable `origin_ref`; relocatable routing fields are excluded.
- One record can represent split fan-out through ordered, unique `linked_step_ids`.
- Structurally valid dangling records load for diagnostics but cannot be newly published.
- Explicit review authors and approves non-delivery records; unattended runs cannot create approval.
- Approval and pending-target digests bind the exact semantics and mapping shown at TTY review; stale substitutions are rejected.
- Legacy migration creates unreviewed records, covers every current-schema writer, and never publishes details separately from their accounting sidecar.
- Pending include regeneration survives interruption and removes parked accounting only after replacement delivery is durable.
- Pending requests support reviewed cancellation/replacement and destination closure across every parked concept sharing a target.
- Completeness recognizes the valid pending state without accepting a bare decision/record mismatch.
- Every durable multi-file update uses the prerequisite transaction API.
- Focused tests, data-contract checks, CLI reference drift checks, the full suite, and `reconcile-code` pass.

## Deferred

- Lifecycle transforms and seed-envelope publication are assigned to `concept-remediation-3b-lifecycle-publication` because they depend on this plan's accounting core.
- Create-time restoration and the end-to-end lifecycle proof are assigned to `concept-remediation-3c-seed-restoration` because they depend on both earlier parts.
- No work inside the accounting-core boundary is intentionally deferred.
