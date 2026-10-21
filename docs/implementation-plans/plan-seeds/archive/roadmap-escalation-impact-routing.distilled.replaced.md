> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-escalation-impact-routing.md`.
> Preserved here for history; do not edit.

## Overview

`plan-tool roadmap` adds a separate, immutable impact-routing analysis after a current structural-escalation receipt exists for one selected feedback row. It validates the receipt, reads a coherent current roadmap and recorded-brief snapshot, resolves the declared relation closure, and classifies the evidence as `same-artifact`, `cross-artifact`, `requires-scope-review`, or `invalid`. It routes only to a named follow-on workflow and never invokes `--from-stage`, writes a canonical artifact, calls a backend, or chooses a patch.

## Problem statement

A structural-escalation reason such as `cross-artifact-impact` signals that review is needed, but it does not prove that the current declared relations identify every affected artifact. Likewise, an apparent one-artifact closure cannot make broad stage re-entry safe. The tool needs a deterministic, current-source-grounded analysis that states exactly what the canonical model supports and refuses to turn incomplete evidence into a broad command or automatic writer.

## Architecture

The analysis accepts one current receipt and validates its closed version-1 schema, including duplicate-member-free JSON, the shared selector grammar, semantic identity, selector, feedback state, target kind/id, selector-derived source path/digest, handoff, and redaction boundary. It re-derives the selected source and re-runs the complete receipt-selection predicate before treating the receipt as current. Malformed, mismatched, stale, source-target-mismatched, selection-ineligible, or unsupported receipts produce an `invalid` analysis with no route. Receipt creation remains owned by `roadmap-structural-revision-escalation`.

It derives an ordered, typed relation graph from every semantic relationship validated by the roadmap artifact model and gates. Nested references attach to their containing stable design row so every edge has an owner, direction, deterministic projection, and order. The finite closure and its evidence are recorded without inferring relationships from prose or the escalation reason.

The runner uses `roadmap_revision_publish.py:roadmap_writer_guard` while capturing the four canonical artifacts and the recorded brief's path and content digest. The guard's durable lock, the immutable analysis record, and command telemetry are the only permitted writes; canonical artifacts, feedback state, seed state, and Git state remain unchanged. An invalid input, changed snapshot, unreadable brief, or analysis-write failure produces no route and no partial readable analysis.

The closed route class uses this precedence:

| Class | Producer condition | Consumer and exit |
| --- | --- | --- |
| `invalid` | Receipt, snapshot, brief, or stored-analysis validation fails | Correct or regenerate the named evidence; no workflow begins. |
| `requires-scope-review` | The current evidence cannot establish a complete declared closure for the selected request | An operator records or obtains a narrower evidence boundary; no broad command is printed. |
| `cross-artifact` | A current, complete closure names more than one canonical artifact | `roadmap-cross-artifact-revision-transaction` may consume the analysis after its own admission checks. |
| `same-artifact` | A current, complete closure names one canonical artifact | `roadmap-same-artifact-structural-revision` may consume the analysis or the receipt under its own admission checks. |

The analysis records the class, closure identities and digests, relation evidence, snapshot/brief evidence, and next workflow name. Views validate stored-analysis identity and schema before recomputing freshness, remain log-free, and never route from a stale or invalid record. Helper extraction is limited to relation-inventory, snapshot, receipt/analysis-validation, and route-class helpers that preserve the existing roadmap reader/writer boundary.

## Out of scope

- Receipt creation, selector/reason capture, or changes to the receipt-only command; `roadmap-structural-revision-escalation` owns those.
- Invoking or changing broad `--from-stage` generation, prompts, retries, timeouts, or publication semantics.
- Same-artifact structural patching, cross-artifact patching, multi-file transactions, seed invalidation, or feedback-state transitions.
- Backend calls, model-selected scope, relation inference from prose, and a generic artifact graph unrelated to roadmap semantics.
- Replacing the existing writer boundary or extending it to arbitrary external filesystem readers and writers.
- Refactoring canonical artifact schemas, broad generation, seed machinery, or unrelated views for uniformity.

## Risks

- **A reason becomes inferred scope:** reviewer prose or an escalation reason could be treated as proof of relations. The graph uses only typed, validated model relationships and returns `requires-scope-review` when they are insufficient. Severity and unresolved gaps are not stated.
- **Mixed evidence looks current:** an analysis could combine different roadmap or brief revisions. The shared writer boundary and before-publication verification make a changed snapshot invalid rather than routable. Severity and unresolved gaps are not stated.
- **A stored analysis becomes authority:** malformed, stale, or substituted records could route work. Version, identity, and live-freshness validation precede every route-class result. Severity and unresolved gaps are not stated.
- **The writer boundary cannot provide a coherent snapshot:** if the existing writer boundary cannot support a coherent participating-command snapshot without widening the declared noncanonical write set, stop and record that platform boundary instead of offering optimistic route advice. Severity is not stated.

## Testing

Use fixture and interleaving tests to prove that each validated relation shape has a stable owner and closure, every route class follows its precedence, and every invalid receipt, snapshot, brief, or analysis shape yields no route. Unit and CLI coverage verifies the closed validation and routing contracts. Interleaving coverage verifies that a writer cannot expose a current analysis for mixed inputs, views remain log-free, permitted noncanonical writes are exact, and no backend or canonical write occurs. The seed does not name test paths, test cases, or existing suites.

## Acceptance criteria

- A current receipt and coherent roadmap/brief snapshot produce an immutable, deterministic analysis with declared closure evidence and exactly one route class.
- Every route class has the documented producer, consumer, precedence, and no-route or follow-on exit.
- Malformed, unsupported, mismatched, stale, or substituted receipts and analyses, invalid roadmap inputs, changed snapshots, and unreadable or changed briefs never route work or expose a partial analysis.
- The graph includes every gate-validated semantic relationship and assigns nested references to stable parent rows with deterministic ordering.
- The command writes only the declared analysis, telemetry, and participating writer lock; it invokes no backend and changes no canonical or reviewer-owned state.
- No analysis prints or executes a broad command, and existing receipt, same-artifact, cross-artifact, and broad workflows retain their contracts.
- An operator can inspect a current, deterministic statement of whether one receipt has same-artifact, cross-artifact, insufficient, or invalid evidence.
- Named follow-on workflows can require the analysis as an additional admission artifact without changing existing writer or broad-command behavior.

## Deferred

- A safe broad-stage recommendation belongs to a later evidence-backed plan; this analysis routes to workflows rather than commands.
- `roadmap-cross-artifact-revision-transaction` owns a later multi-file writer and recovery journal after a `cross-artifact` analysis becomes admissible.
- If real receipts do not yield a relation-complete cross-artifact case, keep the transaction seed dormant.
