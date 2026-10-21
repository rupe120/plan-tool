> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Preserve Reused Audit Coverage
intent: A fresh and a fingerprint-fresh reused `completeness-audit` report the same
  conceptual-audit coverage verdict in both Markdown and `--json`, including a budget-limited
  or low-yield result, without making another Claude call.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Save normalized coverage in completeness audit sidecars
  intent: Keeps a fresh audit's coverage verdict available after its findings are
    saved.
  files:
  - plan_tool/review_persistence.py
  - plan_tool/completeness_report.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/data_contract.py
  - DATA_CONTRACT.md
  - tests/test_review_persistence.py
  - tests/test_completeness_report.py
  - tests/test_data_contract.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/preserve-reused-audit-coverage/01-save-normalized-coverage-completeness.md
  status: done
- id: 2
  title: Restore saved coverage when reusing a completeness audit
  intent: Makes reused Markdown and JSON reports show the original coverage verdict
    without another conceptual audit call.
  files:
  - plan_tool/completeness_report.py
  - plan_tool/cli/completeness_cmd.py
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/preserve-reused-audit-coverage/02-restore-saved-coverage-when-reusing.md
  status: done
- id: 3
  title: Record validation and close the source risk
  intent: Closes the shipped risk and leaves the validation and audit outcome for
    the next session.
  files:
  - BUG_BACKLOG.md
  creates:
  - handoffs/2026-08-04-reuse-audit-coverage-verdict-session.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/preserve-reused-audit-coverage/03-record-validation-close-source-risk.md
  status: done
---
# Preserve Reused Audit Coverage

## Overview

Persist the conceptual-audit coverage verdict in reusable `completeness-audit` sidecars so a fresh or fingerprint-fresh reused audit reports the same result in Markdown and `--json`. Reuse must preserve clean, budget-limited, and low-yield coverage without another Claude call, while coverage-less legacy sidecars remain reusable with an explicit conservative unknown result.

## Problem statement

`completeness-audit --reuse-audit` currently saves recommendations and fingerprints but not the conceptual audit's coverage and budget facts. When reuse skips the audit, rendering falls back to empty local state and can falsely present an unconfirmed or low-yield audit as clean or defaulted.

## Architecture

Treat coverage as conceptual-audit provenance alongside findings. A completeness sidecar stores a normalized `audit_coverage` object only when the producing audit observed coverage; its absence, including on a legacy sidecar, is an explicit unknown state. The saved-review loader exposes that known-or-unknown state, and the reusable-audit read seam provides it to both audit-only and `--iterate` reuse paths.

The public `coverage` block gains `evidence_status`: `"observed"` for a coverage value produced by the conceptual audit and `"unknown-legacy"` when a fresh reusable sidecar predates the optional provenance. An observed value keeps the existing fields and meanings: `budget_limited`, `passes_used`, `cap`, compatibility-null recommendation fields, and `confirmation_kind`. An unknown-legacy value sets the verdict-bearing fields (`budget_limited`, `passes_used`, `cap`, and `confirmation_kind`) to `null` and keeps compatibility fields `null`; Markdown renders “coverage confidence unknown — reused legacy sidecar has no saved coverage evidence”, never a clean/low-yield confidence claim. `DATA_CONTRACT.md` documents this additive public and sidecar contract.

`finalize_completeness_run` selects one coverage value before its rendering and final-sidecar sinks: a fresh audit-only run supplies `_noniter_budget`, a fresh iterate run supplies `outcome.budget`, and accepted audit-only reuse supplies the saved known-or-unknown value. Iterate reuse makes the equivalent selection inside `_run_iterate_convergence_loop`, before its pre-apply checkpoint, then carries that exact value in `outcome.budget` to finalization. Each sink therefore receives the same selected value without asking finalization to write a checkpoint that has already been written. The selection does not change which branch calls Claude or whether an audit-only reuse writes a new sidecar.

## References

- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-usage) — Documents non-interactive `claude -p` execution and JSON output flags, useful for preserving the no-call reuse boundary.
- [Python `json` — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Covers encoding, decoding, and parse errors for additive saved-review sidecar fields.
- [Python `dataclasses` — Data Classes](https://docs.python.org/3.13/library/dataclasses.html) — Covers dataclass defaults and `asdict`, which the saved-review persistence layer uses to serialize optional provenance.
- [Python `hashlib` — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Documents SHA-256 digest handling relevant to retaining the existing audit-fingerprint freshness gate.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Defines JSON objects and `null`, providing the interoperability baseline for the documented sidecar coverage contract.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing audit pass budgets, retry/timeout policy, coverage semantics, or the existing low-yield and blocking policy; this plan preserves current behavior.
- Re-running a fresh conceptual audit solely because a legacy sidecar omits the new optional field; legacy reuse must remain available.
- Changing general saved-review, reconcile, Jira-grade, convergence-history, checkpoint identity, or report filename behavior; these are unrelated behaviors.
- Addressing the distinct checkpoint identity risk; it remains separate backlog work.

## Risks

- Missing or invalid legacy coverage could be treated as proof of clean coverage, producing a false verdict; render an honest, stable unknown state while preserving reuse.
- Only fixing audit-only JSON/Markdown would leave `--iterate` reports incorrect; both reuse paths must share one restored value.
- Sidecar changes could break ordinary-review payload compatibility; additive reads must retain existing valid legacy sidecars.

## Testing

Exercise save/load and the real freshness/reuse boundary without a new conceptual call. Verify that budget-limited and confirmed-low-yield results retain coverage in audit-only and `--iterate` reuse output, legacy sidecars render the chosen unknown representation, and a fresh audit writes the normalized sidecar value. Run focused persistence/CLI suites and the contract test.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A reused sidecar preserves the coverage verdict from its fresh conceptual audit in Markdown and `--json` on both reuse paths.
- A legacy coverage-less sidecar emits `coverage.evidence_status` as `"unknown-legacy"`, nulls every verdict-bearing coverage field, renders the documented Markdown unknown-confidence notice, and does not spend a replacement Claude call.
- `--reuse-audit` continues to skip the conceptual audit when fingerprints match; stale saves still re-audit under existing rules.
- Sidecar additions are documented in `DATA_CONTRACT.md`, remain backward-compatible, and leave unrelated review kinds and Jira-grade behavior unchanged.
- After shipment, remove the source RISK from `BUG_BACKLOG.md` and record the validation/audit outcome in the session handoff.

## Deferred

- Keep checkpoint/final artifact identity and historical checkpoint migration in the separately tracked pre-apply-checkpoint RISK; it is a separate concern.
