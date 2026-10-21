> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Brief Rebind Confirmation
intent: '`plan-tool roadmap` will require an explicit `--confirm-brief-rebind` signal
  before a stage run accepts a changed or legacy decoded-text brief baseline at its
  recorded source path; repeating `--from-existing` alone will refuse without mutating
  the baseline, artifacts, or seed state.'
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/roadmap-brief-rebind-confirmation.md
steps:
- id: 1
  title: Require confirmation before replacing changed or legacy source.json, keep
    initial recording unchanged, and stop refusals before artifact or seed writes
  intent: Prevent a repeated source path from silently accepting changed brief text
    while retaining the deliberate baseline-only rebind lifecycle.
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-brief-rebind-confirmation/01-require-confirmation-before-replacing.md
  status: done
- id: 2
  title: Add --confirm-brief-rebind only to stage runs, rejecting it before non-stage
    writers while preserving their normal writes
  intent: Give headless operators an explicit rebind command without granting confirmation
    authority to matching, initial, different-path, or non-stage routes.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/cli/__init__.py
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/package_surface_help.golden.txt
  - docs/cli/roadmap.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the confirmation-aware run_roadmap contract and admission behavior
      that the CLI exposes.
  detail: docs/implementation-plans/plan-details/roadmap-brief-rebind-confirmation/02-confirm-brief-rebind-only-stage-runs.md
  status: done
- id: 3
  title: Document confirmed brief rebinds across the source contract and operator
    guides
  intent: Ensure every supported guide distinguishes an unconfirmed refusal from the
    confirmed baseline-only rebind and keeps non-stage recovery out of scope.
  files:
  - ROADMAP_FORMAT.md
  - DATA_CONTRACT.md
  - README.md
  - RUNBOOK.md
  - USE_CASES.md
  - CAPABILITIES.md
  - docs/ARCHITECTURE.md
  - docs/ROADMAP_WALKTHROUGH.md
  - integrations/claude/SKILL.md
  - tests/test_roadmap_format.py
  - tests/test_data_contract.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Provides the final admission, refusal, redaction, and lifecycle behavior the
      documents describe.
    2: Provides the exact flag syntax, compatibility matrix, help text, and generated
      CLI reference.
  detail: docs/implementation-plans/plan-details/roadmap-brief-rebind-confirmation/03-document-confirmed-brief-rebinds-across.md
  status: done
---
# Roadmap Brief Rebind Confirmation

## Overview

This implements BACKLOG #367's user-confirmed operator-consent boundary. It
keeps a deliberate, headless rebind command available while making an
accidental same-path invocation fail closed.

## Problem statement

`plan_tool/roadmap.py:_run_roadmap` currently turns a `refused-changed` or
`refused-legacy` admission into `accepted-rebind` whenever the caller repeats
the recorded path through `--from-existing`. `plan_tool/cli/roadmap_cmd.py`
forwards that path but carries no distinct rebind consent. Path identity proves
which source is being considered; it does not prove that replacing its recorded
content baseline is intended.

## Architecture

The stage-run CLI gains the boolean `--confirm-brief-rebind` as the sole,
non-interactive operator signal for this authority. It authorizes only a
changed or legacy recorded baseline when `--from-existing` resolves to that
same recorded path. On matching and initial stage runs it is a no-op: those
routes retain their ordinary behavior and gain no rebind authority. A different
source path remains rejected, and every non-stage roadmap route rejects the
flag before its own handler or writer runs. The signal never authorizes a direct
artifact mutation.

Without the signal, changed and legacy records retain their existing
fail-closed admission dispositions, preflight failure ordering, redaction, and
no-write/no-backend guarantee. With it, the existing `accepted-rebind` lifecycle
remains the explicit baseline-only event: it writes only `source.json` before
ordinary re-entry and reports that fact separately from later stage effects.
The plan will preserve the closed lifecycle vocabulary unless a distinct value
is necessary to express a materially different persisted fact.

Close #367 and retire its pending handoff only after this plan's executable
steps are green and the mandatory post-run code-reconciliation and logic-review
tail converges. That closeout is deliberately outside this plan's `run` step
graph, because the tail begins only after its final executable step completes.

## Scope guardrails

- The observable is whether an explicitly supplied confirmation accompanies a
  same-recorded-path request that needs to replace a changed or legacy baseline.
- The implementation may check only that binary admission condition and its
  existing source identity/digest facts. It may not judge brief quality, compare
  semantic meaning, add an interactive prompt, or infer consent from path
  repetition, TTY state, or automation mode.
- Do not add generic confirmation infrastructure, a new source carrier,
  multi-source intake, a new roadmap stage, a Integration mutation, or a changed
  exit-code convention.

## References

- `BACKLOG.md` — #367, the user-confirmed scope contract and delivery status.
- `plan_tool/roadmap.py:_run_roadmap` and `_resolve_brief_path` — current
  same-path rebind admission and source-identity boundary.
- `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` and `register` — stage-run CLI
  forwarding and route selection.
- `plan_tool/run_log.py:RoadmapSourceAdmissionDisposition`,
  `DATA_CONTRACT.md`, and `ROADMAP_FORMAT.md` — redacted admission lifecycle.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- The delivered non-stage writer policy, including structural rewrite and its
  independent changed/legacy preflight route.
- Re-grounding, regeneration, reconciliation, or semantic confirmation of an
  existing roadmap; reviewer feedback and successor roadmap lineage remain the
  routes for those changes.
- Broader CLI cleanup, generic prompt/confirmation abstractions, and changes to
  ordinary current-baseline stage runs.

## Risks

- An over-broad flag could turn into a bypass for different-source or non-stage
  routes. The option matrix and negative tests keep its authority route-local.
- A refusal that writes a new digest or reaches artifact/model work defeats the
  consent boundary. Source-admission ordering and mutation tests prove it stops
  first.
- Lifecycle prose could claim a new fact without a matching persisted event.
  Keep code, run-log contract, CLI help, and format guidance aligned.

## Testing

Prove that a changed and a legacy same-path stage run refuse without
`--confirm-brief-rebind`, preserve the source record and every downstream
artifact/seed/backend boundary, and retain redacted lifecycle evidence.
Prove that the explicit headless command accepts each required rebind only at
the recorded path and preserves the baseline-only `accepted-rebind` route.
Prove matching and initial stage runs retain their normal behavior with or
without the flag, while different-path and non-stage combinations retain their
existing refusals without acquiring rebind authority. Mutate the consent check
to demonstrate the negative and positive cases distinguish it. Regenerate and
drift-check the CLI reference and test the documented lifecycle vocabulary.

## Acceptance criteria

- Repeating a recorded path alone cannot accept a changed or legacy brief.
- `--confirm-brief-rebind` supplies a documented, headless, route-local way to
  accept exactly that baseline replacement.
- Refusals remain redacted and occur before any baseline, artifact, seed, or
  backend effect.
- A confirmed rebind records only the existing baseline-only acceptance fact;
  subsequent stage outcomes remain separately reported.
- After complete shipment, the post-run closeout reconciles #367 in `BACKLOG.md`
  and retires its pending roadmap handoff.

## Deferred

If another roadmap authority needs confirmation, record its own evidence-backed
backlog item rather than extending this flag or extracting a shared framework.
