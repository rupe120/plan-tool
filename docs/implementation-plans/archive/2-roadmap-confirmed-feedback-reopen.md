> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Confirmed Feedback Reopen
intent: 'Prove one narrow recovery transaction: an operator can explicitly reopen
  one selected `awaiting-review` row when they determine that unavailable legacy evidence
  makes its nonblank response unusable. The confirmation is the authority for that
  determination; the tool records the transition and gives the next receipt a fresh
  identity without attempting evidence classification, recovery, or provenance.'
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because the confirmed lifecycle
  exception changes one artifact through the existing atomic writer.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/archive/roadmap-confirmed-feedback-reopen.replaced.md
steps:
- id: 1
  title: Add a redacted feedback reopen record and fresh nonce field
  intent: Give a selected feedback row a redacted current-artifact fact recording
    its operator-confirmed reopen, carrying the fresh nonce later steps use to force
    receipt currentness to reset. Update the lifecycle documentation and rendered
    reviewer guidance to name this one explicit, operator-confirmed exception to reviewer-only
    reopening; it remains unavailable to model-authored revision.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap.py
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-confirmed-feedback-reopen/01-add-feedback-reopen-record.md
  status: done
- id: 2
  title: Build feedback reopen safety checks and candidate construction
  intent: 'Decide, without touching disk, whether a receipt-safe selected row is safe
    to reopen: it is awaiting-review, has a nonblank response, has a receipt-resolvable
    target, and has no current feedback reopen record. These checks protect the mutation;
    they do not classify unavailable evidence. The explicit operator confirmation
    is the authority for that determination. Reuse baseline-backed source admission
    at capture and final recheck so non-feedback semantic drift refuses while the
    intended feedback-only transition remains safe. Retain the selected artifact''s
    exact canonical source digest for a final pre-replace check. The current record
    prevents the CLI from reusing an intact recovery record, but this proof does not
    add history that detects a raw removal or alteration. Keep the predicate separate
    from the write path so it stays unit-testable against hand-built rows.'
  creates:
  - plan_tool/roadmap_feedback_reopen.py
  - tests/test_roadmap_feedback_reopen.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: supplies the FeedbackState vocabulary and feedback reopen record shape this
      safety check reads to detect an already-reopened row
  detail: docs/implementation-plans/plan-details/roadmap-confirmed-feedback-reopen/02-build-feedback-reopen-candidate.md
  status: done
- id: 3
  title: Fold the reopen nonce into escalation receipt identity and currentness
  intent: Make the first escalation receipt issued after the proof differ from the
    earlier receipt even though the feedback-independent canonical source identity
    does not change when only the response and state change. Extend version-2 receipt
    and impact identity with an optional proof nonce; an absent nonce stays absent
    from the legacy semantic preimage so existing finals retain their names, while
    a matching proof nonce is required in every currentness and identity reconstruction
    path for the reopened row.
  files:
  - plan_tool/roadmap_escalation.py
  - plan_tool/roadmap_escalation_run.py
  - plan_tool/roadmap_escalation_selection.py
  - plan_tool/roadmap_impact_analysis.py
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_escalation.py
  - tests/test_roadmap_escalation_run.py
  - tests/test_roadmap_escalation_selection.py
  - tests/test_roadmap_impact_analysis.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: supplies the feedback reopen record's nonce field this step reads when building
      or comparing a receipt's identity
  detail: docs/implementation-plans/plan-details/roadmap-confirmed-feedback-reopen/03-use-reopen-nonce-in-receipt.md
  status: done
- id: 4
  title: Add the confirmed feedback reopen operation
  intent: Give the tool one deterministic entry point that re-validates the selected
    row, baseline-backed source admission, and captured canonical source digest under
    the writer lock. It refuses semantic drift, a source change visible at its final
    pre-replace check, a missing confirmation, or an existing-record request. It builds
    the redacted reopen record and publishes only when that final check matches; it
    adds no merge, external-writer serialization, log, or recovery contract.
  files:
  - plan_tool/roadmap_feedback_reopen.py
  - plan_tool/roadmap_revision_publish.py
  - tests/test_roadmap_feedback_reopen.py
  - tests/test_roadmap_revision_publish.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: supplies the feedback reopen record this operation builds and appends
    2: supplies the safety checks this operation calls before mutating anything
  detail: docs/implementation-plans/plan-details/roadmap-confirmed-feedback-reopen/04-confirmed-feedback-reopen.md
  status: done
- id: 5
  title: Add confirmed feedback reopen CLI flags
  intent: Expose the operation as one exclusive, explicitly-confirmed CLI action that
    refuses an existing-record request and every other roadmap mode, reusing the existing
    selector-plus-companion-flag and occurrence-tracking pattern. Reconcile only the
    named operator guides that now falsely require a raw manual reopen, while preserving
    reviewer ownership for close, defer, and ordinary reopening. Prove end to end
    that a reopened row's first receipt is not the row's earlier receipt.
  files:
  - plan_tool/cli/__init__.py
  - plan_tool/cli/roadmap_cmd.py
  - docs/cli/roadmap.md
  - README.md
  - RUNBOOK.md
  - CAPABILITIES.md
  - docs/how-to/roadmap.md
  - docs/how-to/roadmap-demo.md
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/package_surface_help.golden.txt
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  depends_on_notes:
    3: supplies the nonce-aware receipt currentness this step's end-to-end regression
      test verifies after a reopen
    4: supplies the operation this CLI handler dispatches to
  detail: docs/implementation-plans/plan-details/roadmap-confirmed-feedback-reopen/05-add-feedback-reopen-command.md
  status: done
- id: 6
  title: Record the delivered feedback reopen in the backlog
  intent: 'After the proof ships, replace BACKLOG #315''s stale ''no reopen mechanism
    exists anywhere'' framing with this bounded behavior; update #242''s reference
    to #315, BUG_BACKLOG.md, and the roadmap arc so they identify the delivered proof
    without claiming that #242 or a general recovery capability shipped.'
  files:
  - BACKLOG.md
  - BUG_BACKLOG.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md
  complexity: low
  change_type: non-code
  depends_on:
  - 5
  depends_on_notes:
    5: the shipped CLI action and tested behavior this step documents against the
      backlog entries
  detail: docs/implementation-plans/plan-details/roadmap-confirmed-feedback-reopen/06-record-backlog-delivery.md
  status: done
---
# Confirmed Feedback Reopen

## Overview

This plan adds one exclusive `roadmap` action that lets an operator explicitly reopen one receipt-safe selected `awaiting-review` row through `--reopen-feedback` and `--confirm-feedback-reopen`. The selected row must satisfy the action's lifecycle, target, current-record, and source-currentness safety checks. Those checks do not identify unavailable evidence: the explicit operator confirmation is the authority for that determination. On success the action atomically clears the response, moves the row back to `open`, and appends one redacted feedback reopen record with a fresh nonce so the next receipt has a fresh identity. A later normal stage response clears that current-artifact record as it creates a new response instance. This is the smallest proof of a confirmed reopen followed by one fresh receipt; it does not design evidence classification, recovery, or response provenance. The record is a fact in the current artifact, not a response-history ledger that survives arbitrary raw edits.

This plan delivers the narrow recovery prompted by [BACKLOG #315. It supersedes `2-roadmap-feedback-evidence-reopen.md`, whose response ledger, evidence-retirement, and operator-attestation design is the eventual capability rather than the proof selected here. Its archived plan and details remain historical evidence only; they must not be executed or treated as a follow-on already authorized by the backlog item.

## Problem statement

The original incident is correctly protected from ordinary re-escalation because it has already received a response, but its legacy evidence cannot support the normal path — leaving the operator with no supported way to retry the row short of a raw edit. The current artifact does not encode a category that can prove this evidence condition. This plan therefore restores one bounded, explicitly confirmed transition without claiming the evidence has been verified or pretending its ordinary safety checks classify the incident.

## Architecture

The reviewer remains the ordinary owner of feedback lifecycle moves. The explicitly confirmed `--reopen-feedback` action is the one deliberate operator-authorized exception: it is not model-authored, and it does not make `--revise-feedback` or another roadmap mode able to close, defer, or reopen feedback. Candidate construction and final recheck use the existing baseline-backed source admission, so design-row or prose drift refuses while the intended feedback-only transition remains safe. The action accepts only one `awaiting-review` row with a nonblank current response whose target the ordinary receipt selector can resolve; any other state, a missing or ambiguous target, a missing confirmation, an existing current feedback reopen record, a semantic-admission failure, or a source change visible at the final check refuses before writing. These are safety preconditions, not an evidence-unavailability classifier: the explicit confirmation is the sole authority for reopening the selected row. Candidate construction retains the selected artifact's canonical source digest. Under the writer lock, the action rereads and revalidates the whole artifact immediately before replacement. A selected-row, unselected-feedback, design-row, or prose change visible then refuses with no write; the tool does not merge it. An external raw edit can still race after that final check and before replacement, because this proof does not create a transaction shared with external writers; it makes no preservation or serializability claim for that window. Only then does the atomic transition clear the response, move the row to `open`, and append one redacted feedback reopen record: the canonical selector object, fixed `operator-confirmed-evidence-unavailable` reason, nonempty URL-safe base64 nonce, and RFC 3339 UTC timestamp. The record contains no response text, response digest, evidence bytes, path, or free-form operator statement. Its truth boundary is deliberate: it records only that an operator confirmed the recovery, and never represents legacy evidence as readable, valid, or verified. A later normal stage response clears the current record while creating its fresh `awaiting-review` response; it does not author a record. The action refuses an intact current record, but does not add a ledger or integrity boundary that detects raw removal or alteration of it. The version-2 receipt and impact schemas accept an absent nonce for existing finals and omit it from their legacy semantic preimages and persisted wire forms; a record-bearing row instead requires its exact nonempty nonce in receipt construction, `current_escalation_receipt`, `_receipt_matches_captured_artifact`, and `ImpactReceiptEvidence` identity reconstruction. That keeps old finals immutable, canonical, and parseable while making the first post-reopen receipt fresh and every existing currentness reader reject the earlier receipt for that row. Rows without a record retain their existing ordinary behavior. This proof deliberately does not detect or reject arbitrary raw manual clears: a legal clear to `open` is indistinguishable from a virgin open row without the response-history capability this plan excludes.

## References

- [secrets — Generate secure random numbers for managing secretshttps: — Official reference for generating cryptographically strong random tokens, applicable to producing the fresh reopen nonce that must give the next receipt a distinct identity.
- [os — Miscellaneous operating system interfaces (os.replace)https: — Documents os.replace()'s atomic-rename semantics on POSIX and Windows, the primitive an implementer would use to write the proof record and state transition atomically.
- [argparse — Parser for command-line options, arguments and sub-commandshttps: — Standard library CLI-parsing reference for wiring up the exclusive action's explicit --confirm-feedback-reopen acknowledgement flag and its refusal-without-mutation error paths.
- [pytest fixtures: explicit, modular, scalablehttps: — Official pytest guide to authoring isolated fixtures, useful for structuring the focused CLI, artifact, and receipt-currentness tests covering the success path and each refusal edge.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Retirement records, archive imports, arbitrary evidence paths, filesystem history traversal, or evidence-byte classification — this proof does not build a general evidence-recovery mechanism.
- General response-instance provenance, legacy response derivation, automatic evidence classification, or other recovery reasons — the feedback reopen record is narrowly scoped to one operator-confirmed transition, not a response ledger.
- General feedback-lifecycle editing without explicit confirmation or a second tool-driven reopen path — this proof adds one named, confirmed exception and leaves reviewer ownership as the default.
- Structural rewrites, new impact-analysis capabilities, local revision retention, and #242 — unrelated to this bounded recovery transaction. Step 3 updates only the existing impact-analysis receipt identity and currentness readers required to keep this proof's fresh-receipt claim true.
- Terminal-event bindings, publication journals beyond the existing atomic artifact writer, recovery commands, and broad operator views — no new publication or command surface beyond the one exclusive action.

## Risks

- **Feedback reopen record misread as evidence verification.** A reader or downstream tooling could treat the redacted feedback reopen record as confirmation that the legacy evidence is valid, rather than only that an operator confirmed the bounded recovery. Severity: medium. Mitigation: the record's truth boundary is stated explicitly in `## Architecture` and enforced by keeping it free of response text, evidence bytes, path, or free-form operator statement. Unresolved gap: nothing in the record itself stops a future feature from reusing it as a provenance signal beyond this scope; that risk is why `## Deferred` requires a new seed rather than an extension.
- **Nonce not consistently threaded into receipt identity.** If a currentness reader misses the nonce, an earlier receipt could still validate as current for a reopened row, silently defeating the fresh-receipt guarantee. Severity: high. Mitigation: step 3 makes the nonce load-bearing in receipt construction, `current_escalation_receipt`, `_receipt_matches_captured_artifact`, and `ImpactReceiptEvidence` identity reconstruction; focused tests cover each existing route. Unresolved gap: a future receipt-currentness reader must adopt the same identity contract before it can claim to decide proof-row currentness.
- **Non-atomic write leaves state and feedback reopen record inconsistent.** A crash or interrupted write between clearing the response, reopening the row, and appending the record could leave one without the other. Severity: medium. Mitigation: step 4 publishes through the existing atomic artifact writer so the transition and the record land in one atomic operation. Unresolved gap: none identified beyond the existing atomic-writer guarantees.
- **Selected artifact changes between selection and confirmed write.** A receipt-safe selector can go stale if its artifact is edited between selection and the confirmed reopen call. Severity: medium. Mitigation: step 2 retains the canonical source digest and step 4 revalidates the whole artifact at its final check, refusing selected-row, unselected-feedback, design-row, and prose edits visible there. Unresolved gap: a raw external writer can race after that check; no shared-writer transaction, merge, or preservation behavior ships.
- **Semantic source drift is accepted as feedback-only.** A raw design-row or prose edit could otherwise be carried into the reopen publication. Severity: high. Mitigation: step 2 and step 4 reuse baseline-backed source admission at capture and final recheck, which rejects semantic drift while allowing the intended feedback-only transition. Unresolved gap: no manual-edit repair workflow ships here.
- **A raw edit alters or removes the reopen record.** The current artifact can then no longer show the record to the CLI. Severity: medium. Mitigation: the action rejects an intact current record and records one transition atomically. Unresolved gap: detecting raw record removal requires the response-history or integrity capability explicitly deferred by this proof.
- **Lifecycle guidance could imply that the model can reopen feedback.** The tool exception changes a reviewer-owned lifecycle invariant. Severity: medium. Mitigation: step 1 updates the format, rendered reviewer guidance, and roadmap module documentation; step 5 updates the CLI reference and the named operator guides that otherwise prescribe only a raw manual reopen. The action stays operator-confirmed and exclusive; `--revise-feedback` remains unable to reopen feedback. Unresolved gap: direct reviewer edits retain their existing behavior.
- **Scope drift toward a general evidence-recovery or provenance capability.** Because the feedback reopen record and safety checks are new machinery, a future change could be tempted to turn them into an automatic evidence classifier, defeating this plan's intentionally narrow proof. Severity: low. Mitigation: `## Out of scope` and `## Deferred` explicitly name the excluded capabilities and require a new seed for any generalization. Unresolved gap: this is a documentation-level guard, not a code-level one, so it depends on future authors reading it.

## Testing

Focused CLI, artifact, lifecycle-guidance, source-admission, receipt-currentness, impact-analysis, and regression tests cover one successful confirmed reopen and all action refusal edges (missing confirmation, an absent/blank response, the wrong state including an already-open row, a target that ordinary receipt selection cannot resolve, an existing-record request, a baseline-admission failure, and a changed selected-artifact byte visible at the final check in selected feedback, unselected feedback, a design row, or prose). They assert no write when that final check detects a change, without claiming a raw external edit after the check can be preserved. They prove the record contains no response text or digest, that confirmation is documented as authority rather than automated evidence classification, and that the renderer and named operator guides document the operator-confirmed exception without widening `--revise-feedback`. They also prove pre-existing version-2 receipt and impact-analysis bytes with no nonce stay canonical and parseable with their legacy identities while every existing currentness reader rejects an earlier receipt after the matching transition. The full suite and the focused proof tests must pass.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A complete, confirmed request reopens exactly one safe selected row with a target that ordinary receipt selection can resolve and writes one redacted feedback reopen record atomically; confirmation is authority for the unavailable-evidence determination.
- Missing confirmation, an absent/blank response, the wrong state (including an already-open row), an unresolvable or ambiguous target, an existing-record request, a baseline-admission failure, or a selected-artifact change visible at the final check refuses without mutation. No assertion covers an external raw write after that check.
- The action applies only its stated lifecycle, target, record, and source-currentness safety checks; it does not classify evidence availability. The current record contains no response text or digest; an intact record blocks this CLI action, while raw record removal or alteration remains outside this proof. A raw manual clear retains its existing ordinary behavior; this proof makes no claim to identify its origin.
- The format, rendered reviewer guidance, roadmap module documentation, CLI reference, and named operator guides identify `--reopen-feedback` as the sole operator-confirmed exception to reviewer-only reopening; `--revise-feedback` retains its existing no-reopen contract.
- The first receipt after the proof has a different identity; the earlier receipt remains immutable but is not current for that row.
- Existing no-nonce version-2 receipt and nested impact-analysis bytes parse and render unchanged; the optional nonce is absent from their persisted wire forms.
- The full suite and focused proof tests pass. No Integration project is tested until the resulting plan-tool changes are committed, pushed, and merged in `<repo-root>`.

## Deferred

This seed proves a single recovery shape only. A second invalidation reason, an evidence-retirement mechanism, a retained-evidence store, a generalized response ledger or provenance ledger, structural/analysis propagation beyond the existing receipt-currentness readers, durable run-log recovery, review UI expansion, or #242 work requires a fresh seed from an observed limitation rather than an expansion of this plan.
