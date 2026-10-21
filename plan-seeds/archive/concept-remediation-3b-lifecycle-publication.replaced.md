> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-remediation-3b-lifecycle-publication.md`.
> Preserved here for history; do not edit.

# Plan seed: Concept Remediation 3B — lifecycle transforms and seed publication

This file is a `plan-tool create` input. Use it after part 1 via:

```text
PLAN_TOOL_BACKEND=codex plan-tool create concept-remediation-3b-lifecycle-publication \
  --from-existing plan-seeds/concept-remediation-3b-lifecycle-publication.md --no-iterate
```

It is not itself an implementation plan. It is part 2 of 3 and replaces the
structural-transform and producer portion of the oversized
`concept-remediation-3-ownership-lifecycle-accounting` plan.

## Order and prerequisites

Require `concept-remediation-3a-accounting-core` to be shipped. Consume its
`NonDeliveryRecord`, routing fields, candidate-publication validator, transition
policy, and accounting helpers without redefining them. Also consume the public
transaction/recovery API from `concept-remediation-1-publication-transactions`.

This plan produces the exact seed-accounting envelope consumed by part 3,
`concept-remediation-3c-seed-restoration`. It does not implement create-time
restoration.

## Goal

Conserve exact ownership and reviewed non-delivery accounting through split,
merge, scope-out, and re-baseline operations. Every operation prepares one
validated candidate generation before mutation and publishes all related plan,
detail, sidecar, and seed changes through the prerequisite transaction API.

Produce bounded, reconstructable machine-readable accounting envelopes for
re-baseline and carved seeds. The envelope must preserve exact concept state
and explicitly tell the future create consumer what is context, what requires
delivery, and what remains deliberate non-delivery.

## Split and merge transforms

Extend existing exact ownership conservation rather than building a parallel
path.

For split:

- prepare the replacement steps, ownership distribution, non-delivery routing,
  and detail renames before any write;
- reject missing or invented concept IDs and invalid child allocations;
- remap each record's ordered `linked_step_ids` to all selected replacement
  children, preserving one `record_id` and immutable `origin_ref`;
- update current `artifact_ref` when the active detail path moves; and
- publish plan, details, and sidecar in one transaction.

For merge:

- map merged members to the surviving step;
- preserve exact many-owner semantics outside the merge;
- deterministically deduplicate routing links and equivalent records;
- update current artifact paths in the same transaction; and
- preserve approval for routing-only remaps while requiring review for semantic
  changes.

Dry-run and apply must share candidate preparation and report the same exact
ownership/routing distribution. Neither may infer identity from titles.

## Scope-out publication

When scope-out removes a concept's final committed owner, prepare the part-1
structured non-delivery transition and require explicit review before mutation.
Concepts with another committed owner survive without an invented deferral.
Non-TTY or `--yes` execution without reviewed inputs refuses before mutation
and prints an exact resumable scope-review/scope-out command; update the CLI and
convergence surfaces that currently imply `-y` can approve the carve.

Submit the carved seed, narrowed plan, migrated details, and reviewed concept
candidate as one typed prerequisite transaction. A recoverable failure restores
the original generation and seed absence. A rollback-failed result names every
uncertain path and routes the operator to transaction recovery. Do not retain or
test a normal seed-first orphan after `apply_narrow()` failure; that state is
eliminated by the prerequisite contract.

## Shared seed-accounting envelope

Define one versioned, clearly delimited JSON envelope contract shared by the
re-baseline and carved-seed producers. It must include:

- format discriminator and schema version;
- source kind, source plan path, source plan fingerprint, and complete source
  concept-record fingerprint;
- canonical projections of every referenced `ConceptNode`, including all
  strict reconstruction inputs such as `title`, `parent_path`, decision/review
  state, evidence, and supported metadata;
- ordered source-step accounting with exact `concept_ids` and stable source
  references;
- exact structured non-delivery records and their immutable identities;
- the prepared post-operation accounting projection where applicable; and
- one validated restoration action for each relevant concept.

Opaque concept IDs are not reconstructable state: `ConceptNode` validation
recomputes IDs from `title` and `parent_path`, so producers must carry the
canonical node projection and include it in the documented fingerprint. Prose
is never an identity fallback.

Use this restoration-action vocabulary:

- `context_only`: available as provenance/prompt context but excluded from the
  destination conservation set;
- `require_delivery`: must receive explicitly reviewed committed destination
  ownership; and
- `preserve_non_delivery`: must retain its exact reviewed non-delivery record
  unless a later operator reviews a transition.

For re-baseline seeds, map roles deterministically:
`done_context -> context_only`, `replan -> require_delivery`, and
`parked -> preserve_non_delivery`. Keep roles separate from a record's
`defer`/`wont_do` disposition.

For carved seeds, selected destination concepts use `require_delivery`. The
source plan's approved defer record is carried as signed transition provenance,
not as active destination non-delivery; part 3 may retire it only after explicit
destination ownership review succeeds.

Serialize deterministically with a documented format tag, UTF-8 encoding,
canonical key/separator rules, preserved authored list order, and golden digest
vectors. Renderers remain pure and receive already-prepared projections.

## Publication rules

- Re-baseline prepares the complete seed, marked plan, and refreshed concept
  fingerprint before one transaction. The envelope distinguishes reviewed
  pre-mark provenance from the intended final plan fingerprint.
- Scope-out prepares the seed and post-carve accounting from the same candidate
  submitted to the transaction.
- Blocked, declined, dry-run, recommend-only, non-TTY, malformed, and stale
  paths write nothing.
- Recoverable failures restore the full original generation; rollback failure
  reports uncertainty rather than claiming either projection is current.

## Expected implementation surfaces

- `plan_tool/concept_tree.py`
- `plan_tool/create.py` and `plan_tool/detail.py` for existing split/merge paths
- `plan_tool/scope_out.py`
- `plan_tool/reground.py`
- `plan_tool/cli/scope_out_cmd.py`
- `plan_tool/cli/convergence_cmd.py`
- focused split, merge, scope-out, re-ground, and CLI tests

## Acceptance criteria

- Split and merge conserve exact concept IDs, record IDs, approval, artifact
  paths, and one-to-many routing without dangling removed steps.
- Dry-run and apply expose the same prepared distribution and reject invented or
  dropped IDs before writing.
- Scope-out never treats an unsigned transition as valid accounting and never
  publishes a seed orphan through the normal recoverable-failure path.
- Every modern seed contains one parseable deterministic envelope with complete
  reconstructable concept projections and explicit restoration actions.
- Re-baseline role/action mapping and carved-destination transition semantics are
  unambiguous and golden-tested.
- All generation changes use the prerequisite transaction and recovery result
  types.
- Focused tests, the full suite, completeness audit, and `reconcile-code` pass.

## Deferred

No work inside the lifecycle-publication boundary is intentionally deferred.
Create-time parsing, mapping review, restoration, and lifecycle proof are
dependency-ordered follow-on work assigned to
`concept-remediation-3c-seed-restoration`.

## Out of scope

- The persisted accounting model and completeness policy belong to part 1.
- Parsing envelopes, create-time mapping/review, and lifecycle integration/docs
  belong to part 3.
- Heuristic title/path matching and automatic destination-step invention are
  prohibited rather than deferred.
