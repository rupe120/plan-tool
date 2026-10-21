> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-remediation-3a-accounting-core.md`.
> Preserved here for history; do not edit.

# Plan seed: Concept Remediation 3A — accounting core and enforcement

This file is a `plan-tool create` input. Use it via:

```text
PLAN_TOOL_BACKEND=codex plan-tool create concept-remediation-3a-accounting-core \
  --from-existing plan-seeds/concept-remediation-3a-accounting-core.md --no-iterate
```

It is not itself an implementation plan. It is part 1 of 3 and replaces the
core-accounting portion of the oversized
`concept-remediation-3-ownership-lifecycle-accounting` plan.

## Order and prerequisites

This plan runs first. It consumes the publication transaction API from
`concept-remediation-1-publication-transactions`, the authoring boundary from
`concept-remediation-2-authoring-boundary-hardening`, and the shipped exact
concept ownership rules from `concept-signoff-integrations`.

Part 2, `concept-remediation-3b-lifecycle-publication`, must depend on the
persisted records, transition policy, and validation helpers delivered here.
Part 3, `concept-remediation-3c-seed-restoration`, depends on both earlier
parts.

## Goal

Define and enforce one durable conservation rule for reviewed concepts before
adding more lifecycle producers: every active reviewed concept has one or more
exact committed owners or one valid approved structured non-delivery record.
A `wont_do` token, unsigned proposal, title match, or prose reference is not
accounting.

Replace scattered `ConceptNode.source_metadata["detail_deferral_step_ids"]`
handling with a first-class contract on `ConceptTree`. Then deliver explicit
review transitions, resumable `defer|wont_do -> include` regeneration, and the
read-only completeness policy that consumes the contract.

## Durable non-delivery contract

Add one persisted record type, such as `NonDeliveryRecord`, with:

- a stable `record_id`;
- exact `concept_id`;
- `defer` or `wont_do` disposition;
- rationale/evidence and explicit review/approval state;
- immutable `origin_ref` identifying the producing occurrence;
- relocatable current `artifact_ref`;
- an ordered, unique tuple of positive `linked_step_ids` so split fan-out is
  representable without duplicating one record identity; and
- bounded provenance required by validation and operator review.

Derive `record_id` from a domain-tagged, length-prefixed SHA-256 encoding of
`concept_id`, disposition, and immutable `origin_ref`, in that order. Exclude
current `artifact_ref`, `linked_step_ids`, rationale, and review state. Artifact
renames and structural routing changes must not mint a different occurrence.
Document the exact bytes and pin a golden vector.

Keep structural decoding separate from semantic publication validation.
Strict decoding rejects malformed shape, duplicate keys and IDs, unknown
fields, invalid enum values, and an ID that does not match its identity inputs.
It may load a structurally valid record with an unknown concept or dangling
route so completeness can diagnose it. A stricter candidate-publication
validator rejects those semantic defects before any new generation is written.

Migrate valid legacy detail-deferral metadata deterministically. Reject
ambiguous or malformed legacy values rather than guessing. Remove the legacy
key from newly persisted sidecars and register/document every persisted shape
in `plan_tool/data_contract.py` and `DATA_CONTRACT.md`.

## Review and transition policy

Extend scoped concept review so a new or changed `defer`/`wont_do` record is
explicitly reviewed with its disposition, evidence, origin, and artifact link.
Changing semantic fields invalidates approval. Exact routing-only changes to
`artifact_ref` or `linked_step_ids` do not invalidate approval. Unattended or
non-TTY execution cannot forge approval.

Model `defer|wont_do -> include` as an explicit durable pending transition.
Approval of the include intent does not prove replacement delivery exists:

1. Retain the approved non-delivery record and its parked plan effect.
2. Persist an exact `IncludeRegenerationRequest` that references the concept,
   retained record, destination step, and intended detail artifact.
3. Resume regeneration from that request without asking the model to recover
   intent from prose.
4. Publish the regenerated detail, plan accounting, request removal, and
   non-delivery-record removal in one prerequisite transaction.
5. On recoverable failure retain the old parked accounting and request; on
   rollback failure report all uncertain paths and require recovery.

The pending state is deliberately not a contradiction. Completeness evaluates
it against the retained effective parked decision while separately validating
the reviewed include intent and exact regeneration request. A bare include plus
a non-delivery record, a request without its retained record, or mismatched
concept/origin/target fields remains invalid.

## Completeness enforcement

Make `plan_tool/review.py:check_concept_coverage()` the single read-only policy
boundary. When no current concept record exists it remains inert. Otherwise it
must report stable findings for:

- a reviewed concept with neither exact committed ownership nor valid approved
  non-delivery;
- unknown concept IDs in `Step.concept_ids` or records;
- dangling artifact or step routing;
- unsigned, stale, or semantically contradictory records;
- simultaneous whole-concept delivery and non-delivery; and
- malformed pending-include combinations.

Many-owner delivery remains valid. Invalid links never count as coverage.
Preserve a separate nonblocking advisory for unsigned parked proposals.
Accounting findings are not prose-apply eligible. Keep self-consistency,
Markdown/JSON reports, saved audit replay, CLI help, and generated CLI
references aligned.

## Expected implementation surfaces

- `plan_tool/concept_tree.py`
- `plan_tool/concept_sync.py`
- `plan_tool/detail.py`
- `plan_tool/review.py`
- `plan_tool/completeness_report.py`
- `plan_tool/data_contract.py`
- `plan_tool/cli/scope_review_cmd.py`
- `plan_tool/cli/completeness_cmd.py`
- `plan_tool/cli/completeness_phases.py`
- `DATA_CONTRACT.md` and generated completeness CLI documentation
- focused concept-tree, concept-sync, detail, review, data-contract, and CLI
  tests

## Acceptance criteria

- Structured non-delivery records have one documented, golden-tested identity
  based on immutable `origin_ref`; relocatable routing fields are excluded.
- Split fan-out is representable by one record with ordered unique
  `linked_step_ids`.
- Structurally valid dangling records load for diagnostics but cannot be newly
  published.
- Explicit review authors and approves non-delivery records; unattended runs
  cannot create approval.
- Pending include regeneration survives interruption and removes parked
  accounting only after replacement delivery is durable.
- Completeness recognizes the valid pending state without accepting a bare
  decision/record mismatch.
- Every durable multi-file update uses the prerequisite transaction API.
- Focused tests, data-contract checks, CLI reference drift checks, the full
  suite, and `reconcile-code` pass.

## Deferred

No work inside the accounting-core boundary is intentionally deferred. The
dependency-ordered follow-on work is already assigned, rather than left as an
unnamed TODO: lifecycle transforms and seed-envelope publication belong to
`concept-remediation-3b-lifecycle-publication`; create-time restoration and the
end-to-end lifecycle proof belong to
`concept-remediation-3c-seed-restoration`.

## Out of scope

- Split/merge routing transforms, scope-out publication, and seed-envelope
  production belong to part 2.
- Create-time seed restoration and the end-to-end lifecycle matrix belong to
  part 3.
- Publisher internals and model-output hardening remain owned by the prerequisite
  remediation plans.
