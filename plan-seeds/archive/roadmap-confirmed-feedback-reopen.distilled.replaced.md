> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-confirmed-feedback-reopen.md`.
> Preserved here for history; do not edit.

## Overview

This plan adds one exclusive `roadmap` action that lets an operator explicitly reopen one receipt-safe selected `awaiting-review` row through `--reopen-feedback` and `--confirm-feedback-reopen`. The action's lifecycle, target, current-record, and source-currentness checks protect the mutation; they do not classify unavailable evidence. The confirmation is the operator's authority for that determination. On success it atomically clears the response, moves the row back to `open`, and appends one immutable, redacted feedback reopen record with a fresh nonce so the next receipt has a fresh identity. This is the smallest proof of one explicitly confirmed reopen followed by one fresh receipt; it does not design evidence classification, recovery, or response provenance.

## Problem statement

The original incident is correctly protected from ordinary re-escalation because it has already received a response, but its legacy evidence cannot support the normal path — leaving the operator with no supported way to retry the row short of a raw edit. The current artifact does not encode a category that can prove this condition. This plan restores one bounded, explicitly confirmed transition without claiming the unavailable evidence is verified or that ordinary safety checks classify the incident.

## Architecture

The action is exclusive and gated by an explicit `--confirm-feedback-reopen` flag. It accepts only a selected `awaiting-review` row with a nonblank response, receipt-resolvable target, unchanged source, and no current record; any other state, a missing confirmation, a duplicate request, or a changed selected row refuses before writing. Those are safety conditions, not evidence classification. The atomic transition clears the current response, moves the row to `open`, and appends one immutable, redacted record with the selector, fixed `operator-confirmed-evidence-unavailable` reason, fresh reopen nonce, and timestamp. It contains no response text, digest, evidence bytes, path, or free-form operator statement. The record says only that an operator confirmed the reopen and never represents legacy evidence as readable, valid, or verified. Receipt construction and currentness use the reopen nonce only for a row carrying this record, so the first receipt written after the transition is fresh and no earlier receipt can appear current for that row. Rows without the record — including a manually cleared row — keep their existing behavior and stay ineligible for ordinary receipt selection.

## Out of scope

- Retirement records, archive imports, arbitrary evidence paths, filesystem history traversal, or evidence-byte classification — this proof does not build a general evidence-recovery mechanism.
- General response-instance provenance, legacy response derivation, automatic evidence classification, or other recovery reasons — the feedback reopen record is narrowly scoped to one confirmed transition, not a response ledger.
- Structural rewrites, impact analyses, local revision retention, and #242 — unrelated to this bounded recovery transaction.
- Terminal-event bindings, publication journals beyond the existing atomic artifact writer, recovery commands, and broad operator views — no new publication or command surface beyond the one exclusive action.

## Testing

Focused CLI, artifact, receipt-currentness, and regression tests cover one successful confirmed reopen and all refusal edges (missing confirmation, an absent/blank response, the wrong state, a duplicate request, a manual clear, and a changed selected row). The full suite and the focused proof tests must pass.

## Acceptance criteria

- A complete, confirmed request reopens exactly one safe selected row and writes one redacted feedback reopen record atomically.
- Missing confirmation, an absent/blank response, the wrong state, a duplicate request, a manual clear, or a changed selected row refuses without mutation.
- Ordinary receipt selection rejects a manually cleared row and admits only a row carrying the matching proof record and fresh nonce.
- The first receipt after the proof has a different identity; the earlier receipt remains immutable but is not current for that row.
- The full suite and focused proof tests pass. No Integration project is tested until the resulting plan-tool changes are committed, pushed, and merged in `<repo-root>`.

## Deferred

This seed proves a single recovery shape only. A second invalidation reason, an evidence-retirement mechanism, a retained-evidence store, a generalized response ledger or provenance ledger, structural/analysis propagation, durable run-log recovery, review UI expansion, or #242 work is a separate seed authored from the observed limitation, rather than an expansion of this plan.
