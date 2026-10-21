> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-remediation-3c-seed-restoration.md`.
> Preserved here for history; do not edit.

# Plan seed: Concept Remediation 3C — seed restoration and lifecycle proof

This file is a `plan-tool create` input. Use it after parts 1 and 2 via:

```text
PLAN_TOOL_BACKEND=codex plan-tool create concept-remediation-3c-seed-restoration \
  --from-existing plan-seeds/concept-remediation-3c-seed-restoration.md --no-iterate
```

It is not itself an implementation plan. It is part 3 of 3 and replaces the
consumer, integration, and documentation portion of the oversized
`concept-remediation-3-ownership-lifecycle-accounting` plan.

## Order and prerequisites

Require both `concept-remediation-3a-accounting-core` and
`concept-remediation-3b-lifecycle-publication` to be shipped. Consume their
record types, exact validation helpers, transition semantics, and shared
versioned seed-accounting envelope. Do not redefine producer formats locally.

## Goal

Make create restore exact reviewed accounting from modern re-baseline and
carved seeds without model or prose inference. Parse control metadata before
distillation, reconcile it against settled destination steps through explicit
operator review, and publish the destination plan and concept sidecar together.

Then prove the conservation invariant across the supported lifecycle and
document the operator workflows only after the integration matrix is green.

## Parse and validate before synthesis

Parse the original raw seed before distillation or any other model pass can
replace its text. A seed with no envelope follows the existing legacy flow. A
present but malformed, stale, or unsupported envelope fails before model
invocation or mutation; never fall back to headings, bullets, or title matching.

Keep one strict write-free parser in `plan_tool/concept_tree.py`. Reject
duplicate JSON keys, unknown fields, invalid types/actions, malformed source
references, duplicate identities, mismatched fingerprints, and concept IDs
whose canonical node projections do not recompute correctly from required
fields including `title` and `parent_path`. Preserve producer-defined ordering.

Update the distillation prompt so the machine envelope is opaque control
metadata already consumed by the caller. The model must not copy, paraphrase,
reinterpret, or invent identifiers and decisions from it.

## Deterministic restoration scope

Applicability is selected only by the producer's validated restoration action:

- `context_only` is available for provenance and bounded prompt context but is
  excluded from destination conservation and cannot gain ownership by textual
  similarity;
- `require_delivery` enters the conservation set and must receive at least one
  explicitly selected committed destination owner;
- `preserve_non_delivery` enters the conservation set with its exact approved
  record and remains parked unless the operator explicitly reviews a semantic
  transition; and
- a carved source defer carried as transition provenance is retired in the
  destination only after the matching `require_delivery` concept receives
  durable reviewed ownership.

Reject an unknown action or a producer role/action disagreement. In particular,
re-baseline `done_context` is excluded, `replan` requires delivery, and `parked`
preserves non-delivery. Carved destination concepts require delivery. There is
no local interpretation of the vague phrase “applicable source concept.”

## Explicit create review

Build the restoration candidate from complete canonical concept-node
projections before optional evidence-backed enrichment. Preserve exact source
IDs and reviewed record state; never try to reverse an opaque ID or allow model
output to replace a restored identity.

Run restoration review only after destination change types, gates, splits,
dependencies, and step IDs are settled. Present source accounting and proposed
destination mappings together. Require the operator to:

- select one or more real committed destination owners for every
  `require_delivery` concept;
- preserve order without duplicate owners;
- confirm every `preserve_non_delivery` record or explicitly review a semantic
  transition;
- resolve ambiguous mappings rather than accepting defaults; and
- leave no dropped, invented, contradictory, or stale identity.

Do not infer ownership from title, path, source step number, model-proposed
`concept_ids`, or a single apparent candidate. A concept cannot finish with
both active committed ownership and approved whole-concept non-delivery unless
the shared contract later models partial decisions explicitly.

Unattended `--yes` or non-TTY create cannot approve restoration choices. Refuse
before archive, plan, sidecar, manifest, or other mutation and print an exact
interactive resume instruction. A multi-plan distillation proposal remains
write-free; do not heuristically divide one envelope among destinations.

After review, use the existing create synchronization/publication tail to
publish matching `Step.concept_ids` and `ConceptTree` accounting. Preserve
create-owned cleanup and manifest ordering on publication failure.

## Lifecycle integration proof

Add a production-level integration matrix that starts with multiple concepts,
shared and sole owners, `defer`, `wont_do`, unsigned proposals, and reviewed
records. Exercise in dependency order:

1. create restoration from re-baseline and carved envelopes;
2. split with one-to-many routing;
3. merge and deterministic deduplication;
4. re-ground/mark-done and re-baseline publication;
5. scope-out with surviving-owner and final-owner cases;
6. interrupted then resumed include regeneration; and
7. completeness/reconcile after every successful transition.

Use `check_concept_coverage()` as the production policy oracle and pair it with
direct persisted-state assertions so weakening the checker cannot make the
matrix pass. Exercise recoverable publication failure and rollback-failed
uncertainty. Assert exact IDs, routing, approval, fingerprints, no title
inference, and absence of partial committed generations.

## Documentation and backlog closure

Only after the integration matrix passes, update `RUNBOOK.md`, `CLAUDE.md`, and
the relevant backlog entries. Document modern versus legacy seeds, restoration
actions, interactive mapping, unattended refusal, scope-review/include resume,
transaction recovery, and how to diagnose an accounting finding. Modify parser
or help sources before regenerating generated CLI references; do not hand-edit
generated rows.

## Expected implementation surfaces

- `plan_tool/concept_tree.py`
- `plan_tool/create.py`
- `plan_tool/prompts/distill-seed.md`
- `tests/test_create.py`
- lifecycle integration tests spanning create, detail, re-ground, scope-out,
  completeness, and CLI behavior
- `RUNBOOK.md`, `CLAUDE.md`, `BACKLOG.md`, and generated CLI documentation where
  command behavior requires it

## Acceptance criteria

- Modern seed accounting is parsed and provenance-validated before any model
  call; malformed modern metadata never falls back to prose.
- Exact canonical `ConceptNode` state is reconstructable and independently
  fingerprinted; opaque IDs are never treated as reversible.
- Restoration scope follows the closed action table, including exclusion of
  contextual done concepts and reviewed transition of carved concepts to
  delivery.
- Every required mapping is explicit, ambiguous cases remain unresolved, and
  unattended execution writes nothing.
- Successful create publishes matching plan ownership and sidecar accounting;
  failure leaves no create-owned partial generation or manifest entry.
- The lifecycle matrix proves exact owner-or-valid-non-delivery conservation
  after every supported operation and failure class.
- Operator and generated documentation match shipped commands, and the concept
  remediation backlog is reconciled only after verification.
- Focused tests, lifecycle integration tests, the full suite, generated-doc
  drift checks, completeness audit, and `reconcile-code` pass.

## Deferred

No work inside the seed-restoration and lifecycle-proof boundary is
intentionally deferred. Producer serialization and accounting-core behavior
remain prerequisites owned by 3B and 3A rather than unnamed TODOs here.

## Out of scope

- Producer serialization and split/merge/scope-out transforms belong to part 2.
- Core record schema, transition review, and completeness finding semantics
  belong to part 1.
- Automatic covering-step generation, heuristic restoration, and automatic
  division of one envelope among multiple new plans remain prohibited.
