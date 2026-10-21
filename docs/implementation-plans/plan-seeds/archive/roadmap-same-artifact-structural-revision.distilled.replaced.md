> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-same-artifact-structural-revision.md`.
> Preserved here for history; do not edit.

## Overview

`plan-tool roadmap` adds a bounded structural-revision path that consumes one current structural-escalation receipt and one selected open feedback row, then proposes typed changes to exactly one canonical roadmap artifact and one feedback response. It supports controlled prose replacement and row creation, replacement, removal, reordering, and relationship changes without re-entering later roadmap stages. The command validates its bounded candidate and existing read-only upstream dependencies before atomically publishing the single artifact, while preserving reviewer ownership of feedback.

## Problem statement

`roadmap-incremental-revision` permits only one same-artifact row, one allowlisted presentation-field replacement, and one feedback response. That boundary cannot fully answer feedback targeting an entire artifact such as `01-domain.md`, or row-targeted feedback that requires additional rules and relations such as a lifecycle map; treating either request as a local presentation edit would report a partial answer as satisfied.

`roadmap-structural-revision-escalation` supplies immutable receipt and selected-source evidence, but there is no write-capable structural path that consumes it. Broad `--from-stage` re-entry would rewrite later artifacts unnecessarily, while a cross-artifact transaction would exceed the current local publisher's atomic single-path guarantee.

## Architecture

The structural runner takes one artifact-qualified feedback selector plus the semantic id/digest of a current version-1 escalation receipt. Before seed invalidation or a backend call, it revalidates the receipt's closed schema and duplicate-member-free JSON, shared selector grammar, semantic identity, source digest, source-derived target kind/id, and complete receipt-selection predicate. A missing, stale, source-target-mismatched, selection-ineligible, invalid, or non-structural receipt is refused, and a normal `--revise-feedback` attempt never falls through into this mode.

The selected artifact is the complete canonical write set. The selected feedback may target a row or the artifact, while required upstream artifacts remain read-only inputs to existing gates. Sibling and downstream artifacts, draft seeds, repository code, unselected feedback, other artifact text, and generated seeds stay outside backend context and the write set. Operator output names this one-artifact write set before the backend call.

The backend returns a closed, versioned operation schema rather than a replacement artifact. Variants cover marked prose replacement and create/replace/remove/reorder row operations, with every row operation declaring its row type and stable target identity where one exists. New rows carry schema-valid stable IDs and explicit relation endpoints. Artifact-specific allowlists define which of the four canonical artifact row models can be created, changed, removed, or reordered in each stage and which structural gate protects each relation change.

A deterministic merger rejects ID collisions, unrecognized row types, duplicate operations, inferred targets, incompatible row ordering, operations outside the selected artifact, and invalid relation endpoints. Rows, removals, feedback, decisions, prose segments, and accepted serialized data absent from an allowed operation remain unchanged. The selected artifact must first pass the same render-canonical preflight used by local revision, so opaque or lossy input is rejected instead of normalized.

Each backend reply contains exactly one `respond-feedback` operation for the selected open feedback row. A valid candidate may move only that row to `awaiting-review` with a proposed response; it cannot close feedback, change another feedback row, infer acceptance, or treat generated structural content as human approval.

Candidate construction flows through parser and gate validation before atomic one-artifact publication. The runner reuses the shared participating-writer guard, established durable pre-backend seed-invalidation seam, local revision failure and interrupt seams where their contracts fit, and existing conservative state and writer guarantees. It never materializes, refreshes, accepts, or promotes seed prose, and a failed attempt may leave drafts stale but cannot leave changed roadmap content represented by a current derived draft.

Backend context contains only the current receipt, selected feedback, the selected artifact's canonical prose and rows, immutable row/relation inventory, and the closed operation schema. The command records selector and receipt semantic ids and digests, write-set summary, context bytes/counts, operation verdicts, validation and publication result, termination reason, and one explicit backend-attempt outcome. It does not retry through broad stage authoring, and logs exclude feedback requests, roadmap prose, prompts, backend replies, and raw seed content.

Shared selector, receipt-identity validation, operation-validation, candidate-gate, or writer-guard helpers may be extracted only when ownership remains clear between local and structural single-artifact modes. Broad stage generation, artifact schemas, seed machinery, and readers are not refactored merely to make revision modes uniform.

## Out of scope

- Selecting multiple feedback rows, coalescing requests, or inferring related feedback items; this command handles one explicitly selected row.
- Writing multiple canonical roadmap artifacts, deriving a dependency closure, or adding multi-file publication and recovery; the complete write set remains one artifact.
- Backend-created free-form YAML/Markdown replacement, arbitrary manual text editing, collaborative editing, or lossless editing of unknown extensions; mutations use the closed typed-operation schema.
- Altering `--from-stage`, its prompts, retry/timeouts, or broad write and recovery semantics; structural revision is an exclusive path.
- Per-plan selective seed invalidation, seed generation or promotion, or changes to materialization state semantics; the runner reuses existing conservative behavior.
- Git checkpoints, worktree requirements, external tickets, identity changes, or a browser workflow; none belongs to this revision path.

## Risks

- **Cross-artifact widening — critical boundary risk.** A request may require another canonical artifact. The command mitigates this by rejecting the request, preserving the current receipt, and routing it to the cross-artifact seed rather than adding a second writer.
- **Unrepresentable structural mutation — blocking schema risk.** A row type may not be safely expressible through explicit typed operations and existing gates. Work stops and records the schema gap; preflight, type checks, and conservative invalidation remain unchanged.
- **Lossy or opaque input mutation — publication risk.** Normalization could discard accepted serialized data or unknown content. The render-canonical preflight rejects such input before mutation.
- **Partial or unauthorized mutation — publication risk.** Collisions, inferred targets, invalid relation endpoints, unmentioned changes, cross-artifact operations, and changes to unselected feedback could corrupt the bounded candidate. The strict parser, deterministic merger, operation allowlists, preservation rules, structural gates, and atomic publisher reject these cases before publication.
- **Stale derived state after failure — conservative state risk.** An accepted preflight invalidates seed state before the backend call, so a backend, parse, gate, or interrupt failure may leave drafts stale. The artifact remains byte-for-byte intact, and no changed roadmap content is represented by a current derived draft.
- **Sensitive content in lifecycle evidence — observability risk.** Logs could expose feedback, roadmap prose, prompts, backend replies, or raw seeds. Evidence is restricted to semantic ids, digests, counts, verdicts, results, and termination metadata.

## Testing

Unit and CLI coverage exercises every operation type, artifact-specific allowlists, deterministic merge behavior, forbidden write-set widening, stale and mismatched receipt rejection, render-canonical preflight, byte preservation of unmentioned content, parser and gate failures, writer interleavings, sidecar invalidation, and observability redaction. Fixtures include Integration-shaped artifact-level domain feedback and row-targeted lifecycle-map feedback.

Candidate tests attempt an ID collision, an unmentioned-row change, mutation of an unselected feedback row, an upstream or sibling artifact change, an invented relation endpoint, a whole-document replacement, and omission of the selected response; each must fail before publication. Failure-path tests cover backend, parse, gate, and interrupt outcomes after accepted preflight and verify that the artifact remains byte-for-byte intact with only the existing conservative seed-state result.

Regression coverage keeps existing local `--revise-feedback`, structural escalation, `--from-stage`, materialize/refresh/apply, and roadmap view contracts passing. Tests use no live backend. One disposable opt-in smoke test exercises a real structural feedback row and verifies the event and redaction boundary.

## Acceptance criteria

- Given a current artifact-target escalation receipt for a fixture domain artifact, the command can add a new rule, entity, or flow and its declared relations, then publishes only the selected artifact and its selected feedback response after parser and gate success.
- Given a current row-targeted escalation receipt, the command can add a multi-row lifecycle map and publishes only the selected artifact and selected feedback response after parser and gate success.
- Before any backend call, operator output names the complete one-artifact write set.
- Missing, stale, source-target-mismatched, selection-ineligible, invalid, or non-structural receipts are rejected before seed invalidation or backend contact.
- Noncanonical, opaque, or lossy artifact input is rejected before seed invalidation or backend contact.
- Every accepted backend reply uses the closed typed-operation schema and contains exactly one `respond-feedback` operation for the selected open feedback row.
- A candidate may move only the selected feedback row to `awaiting-review` with a proposed response; it cannot close feedback, alter another feedback row, or infer acceptance.
- ID collisions, duplicate operations, unrecognized row types, inferred targets, incompatible ordering, invalid relation endpoints, whole-document replacement, unmentioned changes, and operations outside the selected artifact fail before publication.
- Content absent from an allowed operation remains byte-for-byte unchanged.
- Backend, parse, gate, and interrupt failures after accepted preflight leave the canonical artifact byte-for-byte intact and retain only the existing conservative seed-state result.
- Successful publication is atomic and changes exactly one canonical roadmap artifact.
- Logs contain selector and receipt semantic ids and digests, write-set summary, bounded-context counts, operation verdicts, validation and publication result, termination reason, and one backend-attempt outcome, but no feedback request, roadmap prose, prompt, backend reply, or raw seed content.
- Existing local `--revise-feedback`, structural escalation, `--from-stage`, materialize/refresh/apply, and roadmap views retain their documented contracts.
- Documentation distinguishes presentation revision, structural same-artifact revision, escalation, and broad stage re-entry, and explains how a reviewer inspects the proposed response and explicitly accepts or reopens feedback through the existing lifecycle.

## Deferred

- Cross-artifact structural revision is routed to the cross-artifact seed when a request requires another canonical artifact; this command retains its one-artifact writer boundary.
- A row type that cannot be represented safely through explicit typed operations and existing gates is deferred as a recorded schema gap rather than admitted by weakening validation.

## Input

This plan consumes one artifact-qualified feedback selector, one selected open feedback row, and the semantic id/digest of a current version-1 structural-escalation receipt produced by `roadmap-structural-revision-escalation`. It relies on the receipt's closed, duplicate-member-free JSON schema; shared selector grammar; semantic identity; source digest; source-derived target kind/id; structural classification; and complete receipt-selection predicate.

It also reads the selected artifact's canonical prose and rows, immutable row/relation inventory, and any required upstream artifacts used by existing read-only gates. Those inputs are limited to the bounded artifact slice: sibling and downstream artifacts, repository code, unselected feedback, draft seeds, other artifact text, and generated seeds are neither verified as part of the candidate nor supplied to the backend.
