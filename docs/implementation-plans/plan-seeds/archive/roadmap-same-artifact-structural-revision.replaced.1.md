> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-same-artifact-structural-revision.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap Same-Artifact Structural Rewrite

## Outcome

`plan-tool roadmap` will turn one current structural-escalation receipt and
its selected open feedback row into a reviewable rewrite of exactly one
canonical roadmap artifact. The rewrite changes only explicitly allowed fields
of existing rows and the contents of already-delimited prose regions. It
preserves every row identity, relation, decision, collection order, unselected
feedback row, and every other canonical artifact, then publishes only the
selected artifact and its proposed feedback response after a candidate proof
and final snapshot check.

## Overview

This is the safe one-artifact structural path for a request whose answer is a
rewrite, not a new or rewired design element. It remains an exclusive command:
it never starts broad stage re-entry and never promotes itself into a
cross-artifact writer.

## Problem statement

The existing local revision path is intentionally limited to one allowlisted
presentation-field change. A whole-artifact or coordinated existing-row rewrite
needs bounded prose and structured replacements, but a generic structural
operation language would also need to decide whether a candidate creates
downstream obligations. Current static impact routing cannot make that decision
for a candidate that preserves identity: `roadmap_impact_snapshot._require_current_gates`,
`resolve_impact_closure`, and `check_entity_component_coverage` correctly make
a gate-valid Domain artifact appear cross-artifact even when a candidate only
rewrites existing content.

## Architecture

A current closed receipt and a current impact analysis bound to the same
selector are required preflight evidence. They validate source identity,
selected feedback, and the safe bounded input slice, but the analysis route is
not itself permission to publish. Invalid, stale, mismatched, unavailable, or
`requires-scope-review` evidence refuses before seed invalidation or backend
contact. A `same-artifact` or `cross-artifact` static route may proceed only to
candidate construction; it cannot prove the candidate's final write scope.

The backend returns a duplicate-member-free, finite, versioned rewrite
envelope. Its closed operations replace only allowlisted fields of existing
selected-artifact rows and the contents of unique pre-existing prose regions.
The merger rejects an unknown row, an identity or relation change, a new or
removed row, collection-order change, decision mutation, unselected-feedback
mutation, absent/ambiguous/full-body prose region, or any operation outside the
selected artifact. It preserves region delimiters and every byte outside a
replaced region.

Before publication, a candidate-versus-predecessor proof establishes that the
selected artifact's row-id inventory, relation inventory, decisions, collection
orders, and all non-selected feedback are unchanged, and substitutes the
candidate into the current full roadmap gate context to prove no downstream
obligation changes. The runner captures the selected source and relevant
evidence digests before backend work, then re-reads and compares them while the
participating writer guard is held immediately before the one-artifact
replacement. `roadmap_revision_publish.publish_revision_candidate` currently
does not make this final comparison, so the plan must add it rather than rely
on writer coordination alone.

Each accepted reply contains exactly one response for the selected open
feedback row. Publication may move only that row to `awaiting-review` with a
proposed response. Existing conservative seed invalidation, atomic
single-artifact publication, and redacted lifecycle boundaries remain in force;
a failed attempt leaves canonical bytes unchanged and may leave only the
existing stale derived-state result.

## In scope

- Current receipt and impact-analysis preflight that treats static route class
  as evidence, not as candidate-write authority.
- A closed rewrite-only operation envelope, deterministic merger, existing-row
  field allowlists, and existing prose-region replacement.
- Candidate/predecessor preservation proof, full current-gate evaluation, and
  an immediately pre-publication source/evidence snapshot recheck.
- One-artifact runner and exclusive CLI path, selected-feedback response,
  conservative seed invalidation, atomic publication, redacted telemetry, and
  documentation for the rewrite-only boundary.

## Out of scope

- Row creation, removal, reordering, ID changes, relation rewiring, decision
  changes, prose-region creation, or a generic typed patch language.
- A candidate-aware impact subsystem capable of classifying additions or other
  changed downstream obligations; record that later work in BACKLOG #289 when
  a real request demonstrates it.
- Writing another canonical artifact, journaled multi-file recovery, broad
  `--from-stage` authoring, automatic escalation, or a generic document editor.
- Changes to canonical roadmap schemas, seed materialization semantics, or
  unrelated revision modes merely to unify implementation.

## Risks

- **Static-route overreach:** treating a route as a candidate proof would
  reject safe rewrites or admit a widening change. Candidate preservation and
  full-gate proof, not static route class, determine publication.
- **Lost concurrent edit:** a participating-writer guard does not stop an
  external reviewer edit. The final digest comparison refuses rather than
  overwriting it.
- **Hidden structural change:** a field replacement could change identity,
  relations, ordering, or a downstream obligation. The closed allowlists and
  candidate/predecessor proof reject it before publication.

## Testing

Backend-free unit and CLI tests cover current/mismatched evidence, both static
route classes, invalid no-route evidence, allowed existing-row and bounded
prose rewrites, every rejected structural operation, candidate-proof failures,
full-gate failures, source changes during backend work, selected-feedback-only
transitions, seed-state outcomes, atomic failure paths, and lifecycle
redaction. Fixtures prove a Domain rewrite can proceed when its preserved
identity and relations leave component ownership unchanged, while a candidate
that adds an entity, relation, row, or downstream obligation refuses before
publication.

## Acceptance criteria

- A current receipt plus current static impact evidence can produce a
  one-artifact rewrite only after the candidate proof confirms all identity,
  relation, ordering, decision, feedback, and downstream-gate invariants.
- The command replaces only approved fields of existing rows and contents of
  eligible existing prose regions; every unsupported structural operation
  fails before seed invalidation, backend contact where determinable, or
  publication.
- A changed selected-source or evidence snapshot immediately before
  publication refuses without replacement.
- Successful publication changes exactly the selected canonical artifact and
  selected feedback response; failure leaves canonical content byte-for-byte
  intact and preserves the existing conservative seed-state contract.
- Documentation distinguishes presentation revision, rewrite-only structural
  revision, evidence-only escalation/impact analysis, generic structural work,
  cross-artifact transactions, and broad stage re-entry.

## Deferred

BACKLOG #289 owns generic creation, removal, ordering, and relation-changing
operations, plus the candidate-aware impact proof those operations require. A
cross-artifact transaction remains dormant until that generic contract and a
real declared multi-artifact request exist.
