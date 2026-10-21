> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-confirmed-feedback-reopen.md`.
> Preserved here for history; do not edit.

# Seed: confirm one roadmap feedback reopen

## Outcome

Prove one narrow recovery transaction: an operator can explicitly reopen one
selected `awaiting-review` row when they determine unavailable legacy evidence
makes its nonblank response unusable. The confirmation is the authority for
that determination; the tool preserves a minimal redacted record of the
transition and the next receipt has a fresh identity. The proof does not become
evidence classification, recovery, or response provenance.

## Problem statement

The incident reported by BACKLOG #315 is correctly protected from ordinary
re-escalation because it has already received a response. Its legacy evidence
cannot support the normal path, so the operator currently has no supported way
to retry the row without a raw edit. The artifact does not encode a category
that proves this evidence condition. The proof therefore restores one bounded,
explicitly confirmed transition without claiming the evidence is verified or
that ordinary safety checks classify the incident.

## In scope

- One exclusive `roadmap` action with one receipt-safe selector and an explicit
  `--confirm-feedback-reopen` acknowledgement.
- Safety checks only for one `awaiting-review` row with a nonblank current
  response, a receipt-resolvable target, and no current feedback reopen record.
- One immutable, redacted feedback reopen record on the row: the exact
  selector object, fixed `operator-confirmed-evidence-unavailable` reason,
  fresh reopen nonce, and timestamp. It contains no response text, digest,
  evidence bytes, path, or free-form operator statement.
- One atomic transition that clears the current response, moves the row to
  `open`, appends that proof record, and refuses a changed row before writing.
- Receipt construction and currentness use the nonce only for a row carrying
  this proof record, so the post-reopen receipt is fresh and an earlier receipt
  cannot appear current.
- Focused CLI, artifact, receipt-currentness, and regression tests for one
  successful proof and all refusal edges.

## Scope contract

- **Smallest proof:** one explicitly confirmed reopen followed by one fresh
  receipt. Do not design an evidence classifier or eventual generic capability.
- **Ordinary protection:** `open` rows without this proof record retain their
  existing behavior; a manual clear remains ineligible for ordinary receipt
  selection.
- **Truth boundary:** the record says only that an operator confirmed the
  reopen. It must never represent legacy evidence as readable, valid, or
  verified.
- **Stop condition:** stop after this transition, receipt identity, CLI result,
  and tests are proved. Any second invalidation reason, archive import,
  retained-evidence store, general response ledger, structural/analysis
  propagation, durable run-log recovery, review UI expansion, or #242 work is
  a separate seed.

## Out of scope

- Retirement records, archive imports, arbitrary evidence paths, filesystem
  history traversal, or evidence-byte classification.
- General response-instance provenance, legacy response derivation, automatic
  evidence classification, or other recovery reasons.
- Structural rewrites, impact analyses, local revision retention, and #242.
- Terminal-event bindings, publication journals beyond the existing atomic
  artifact writer, recovery commands, and broad operator views.

## Acceptance criteria

- A complete, confirmed request reopens exactly one safe selected row and
  writes one redacted feedback reopen record atomically; confirmation is the
  authority for the unavailable-evidence determination.
- Missing confirmation, an absent/blank response, the wrong state, a duplicate
  request, a manual clear, or a changed selected row refuses without mutation.
- Ordinary receipt selection rejects a manually cleared row and admits only a
  row carrying the matching proof record and fresh nonce.
- The first receipt after the proof has a different identity; the earlier
  receipt remains immutable but is not current for that row.
- The full suite and focused proof tests pass. No Integration project is tested until
  the resulting plan-tool changes are committed, pushed, and merged in
  `<repo-root>`.

## Deferred

This seed proves a single recovery shape only. If the proof needs another
reason, an evidence-retirement mechanism, a generalized provenance ledger, or
post-run recovery, author a new seed from the observed limitation rather than
expanding this plan.
