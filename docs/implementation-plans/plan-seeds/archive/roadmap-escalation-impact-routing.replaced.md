> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-escalation-impact-routing.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap Escalation Impact Routing

## Outcome

After a current structural-escalation receipt exists for one selected feedback
row, `plan-tool roadmap` will produce a separate, immutable impact-routing
analysis. It will validate the receipt, read a coherent current roadmap and
recorded-brief snapshot, resolve the declared relation closure, and classify
the evidence as same-artifact, cross-artifact, scope-review-required, or
invalid. It will route only to a named follow-on workflow; it will not invoke
`--from-stage`, write a canonical artifact, call a backend, or choose a patch.

## Overview

The structural-escalation receipt deliberately records why a selected request
needs review without claiming to know its impact. Relation closure, current
source grounding, and route safety are a separate decision surface: they read
all roadmap artifacts, need writer coordination and stored-analysis validation,
and decide whether a later single-artifact or cross-artifact workflow has
enough evidence to begin. Keeping that analysis out of receipt creation keeps
the routine receipt path small and makes its stronger read consistency visible.

## Problem statement

A reason such as `cross-artifact-impact` is a reviewer signal, not evidence
that current declared relations identify every required artifact. Conversely,
an apparent one-artifact closure cannot make a broad stage re-entry safe. The
tool needs a deterministic analysis that states exactly what the canonical
model supports and refuses to convert incomplete evidence into a broad command
or an automatic writer.

## Architecture

The analysis accepts one current receipt and validates its closed version-1
schema, including duplicate-member-free JSON, the shared selector grammar,
semantic identity, selector, feedback state, target kind/id,
selector-derived source path/digest, handoff, and redaction boundary before
using it. It re-derives the selected source and
re-runs the complete receipt-selection predicate before it treats the receipt
as current. Malformed, mismatched, stale, source-target-mismatched,
selection-ineligible, or unsupported receipts produce an invalid analysis with
no route. Receipt creation remains owned by
`roadmap-structural-revision-escalation`.

It derives an ordered, typed relation graph from every semantic relationship
the roadmap artifact model and gates validate. Nested references attach to
their containing stable design row, so every graph edge has an owner,
direction, deterministic projection, and order. The analysis records the
finite closure and its evidence; it does not infer relationships from prose or
the escalation reason.

The runner uses the participating roadmap writer boundary
`roadmap_revision_publish.py:roadmap_writer_guard` while it captures the four
canonical artifacts and the recorded brief's path and content digest. The
guard's durable lock, the immutable analysis record, and command telemetry are
the only permitted writes; canonical artifacts, feedback state, seed state,
and Git state remain unchanged. An invalid input, changed snapshot, unreadable
brief, or analysis-write failure produces no route and no partial readable
analysis.

The analysis has one closed route class with this precedence:

| Class | Producer condition | Consumer and exit |
| --- | --- | --- |
| `invalid` | Receipt, snapshot, brief, or stored-analysis validation fails | Correct or regenerate the named evidence; no workflow begins. |
| `requires-scope-review` | The current evidence cannot establish a complete declared closure for the selected request | An operator records or obtains a narrower evidence boundary; no broad command is printed. |
| `cross-artifact` | A current, complete closure names more than one canonical artifact | `roadmap-cross-artifact-revision-transaction` may consume the analysis after its own admission checks. |
| `same-artifact` | A current, complete closure names one canonical artifact | `roadmap-same-artifact-structural-revision` may consume the analysis or the receipt under its own admission checks. |

The analysis records the class, closure identities and digests, relation
evidence, snapshot/brief evidence, and the next workflow name. It does not
recommend an executable `--from-stage` command. Views validate stored analysis
identity and schema before recomputing freshness, remain log-free, and never
route from a stale or invalid record.

## Input

This work consumes a structural-escalation receipt, all four canonical roadmap
artifacts, the recorded brief and its content, the typed artifact model, and
the relation rules enforced at HEAD. Feedback prose, plan-seed drafts,
repository code, backend output, and arbitrary filesystem content are not
analysis inputs.

## In scope

- Current-receipt validation and immutable impact-analysis persistence and
  inspection.
- A deterministic graph and closure over the canonical relation model.
- Participating writer coordination, coherent snapshot/brief freshness, and
  stored-analysis integrity checks.
- The closed route-class contract and redacted lifecycle evidence.
- Unit, CLI, and interleaving tests proving no-route behavior and the declared
  noncanonical write set.

## Out of scope / Non-goals

- Receipt creation, selector/reason capture, or changes to the receipt-only
  command; `roadmap-structural-revision-escalation` owns those.
- Invoking or changing broad `--from-stage` generation, prompts, retries,
  timeouts, or publication semantics.
- Same-artifact structural patching, cross-artifact patching, multi-file
  transactions, seed invalidation, or feedback-state transitions.
- Backend calls, model-selected scope, relation inference from prose, and a
  generic artifact graph unrelated to roadmap semantics.
- Replacing the existing writer boundary or extending it to arbitrary external
  filesystem readers and writers.

## Allowed behavior changes

- An operator can inspect a current, deterministic statement of whether one
  receipt has same-artifact, cross-artifact, insufficient, or invalid evidence.
- The named follow-on workflows can require that analysis as an additional
  admission artifact; no existing writer or broad command changes behavior.

## Allowed reorganization

Extract only relation-inventory, snapshot, receipt/analysis-validation, and
route-class helpers that preserve the existing roadmap reader/writer boundary.
Do not refactor canonical artifact schemas, broad generation, seed machinery,
or unrelated views for uniformity.

## Risks

- **A reason becomes inferred scope:** the analysis could treat reviewer prose
  or a reason as proof of relations. The graph therefore uses only typed,
  validated model relationships and returns `requires-scope-review` when they
  are insufficient.
- **Mixed evidence looks current:** an analysis could combine different roadmap
  or brief revisions. The shared writer boundary and before-publication
  verification make a changed snapshot invalid rather than routable.
- **A stored analysis becomes authority:** malformed, stale, or substituted records
  could route work. Version, identity, and live-freshness validation precede
  every route-class result.

## Testing

Use fixture and interleaving tests to prove that each validated relation shape
has a stable owner and closure, all route classes follow their precedence, and
each invalid receipt/snapshot/brief/analysis shape yields no route. Verify a
writer interleaving cannot expose a current analysis for mixed inputs, views
remain log-free, permitted noncanonical writes are exact, and no backend or
canonical write occurs.

## Acceptance criteria

- A current receipt and coherent roadmap/brief snapshot produce an immutable,
  deterministic analysis with declared closure evidence and exactly one route
  class.
- Every route class has the documented producer, consumer, precedence, and
  no-route or follow-on exit.
- Malformed, unsupported, mismatched, stale, or substituted receipts and
  analyses, invalid roadmap inputs, changed snapshots, and unreadable or
  changed briefs never route work or expose a partial analysis.
- The graph includes every gate-validated semantic relationship and assigns
  nested references to stable parent rows with deterministic ordering.
- The command writes only the declared analysis, telemetry, and participating
  writer lock; it invokes no backend and changes no canonical or reviewer-owned
  state.
- No analysis prints or executes a broad command, and existing receipt,
  same-artifact, cross-artifact, and broad workflows retain their contracts.

## Deferred

- A safe broad-stage recommendation belongs to a later evidence-backed plan;
  this analysis deliberately routes to workflows rather than commands.
- `roadmap-cross-artifact-revision-transaction` owns a multi-file writer and
  recovery journal after a `cross-artifact` analysis becomes admissible.

## Stop / defer

If the existing writer boundary cannot provide a coherent participating-command
snapshot without widening the declared noncanonical write set, stop and record
that platform boundary rather than offering optimistic route advice. If real
receipts do not yield a relation-complete cross-artifact case, keep the
transaction seed dormant.
