> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-brief-rebind-confirmation.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap brief rebind confirmation

## Outcome

`plan-tool roadmap` will require an explicit `--confirm-brief-rebind` signal
before a stage run accepts a changed or legacy decoded-text brief baseline at
its recorded source path; repeating `--from-existing` alone will refuse without
mutating the baseline, artifacts, or seed state.

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
same recorded path. It must not authorize an initial source record, a different
source path, matching content, a direct artifact mutation, or any non-stage
roadmap route. Incompatible or otherwise useless combinations fail before
source persistence with clear, redacted operator guidance.

Without the signal, changed and legacy records retain their existing
fail-closed admission dispositions, preflight failure ordering, redaction, and
no-write/no-backend guarantee. With it, the existing `accepted-rebind` lifecycle
remains the explicit baseline-only event: it writes only `source.json` before
ordinary re-entry and reports that fact separately from later stage effects.
The plan will preserve the closed lifecycle vocabulary unless a distinct value
is necessary to express a materially different persisted fact.

## In scope

- The stage-run flag, source-admission boundary, result/error wording, and
  stage-run-only option validation for the confirmed rebind.
- Existing source-admission lifecycle and redacted run-log/data-contract
  documentation, plus generated roadmap CLI reference and operator guidance.
- Regression coverage for changed, legacy, matching, initial, different-path,
  and non-stage-route behavior; verified no-write/no-model refusal paths and
  confirmed baseline-only rebind path.
- Updating BACKLOG #367 when the resulting plan ships, after its implementation,
  reconciliation, and logic-focused review convergence complete.

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
Prove matching, initial, different-path, and non-stage combinations retain
their existing authority or fail as incompatible without acquiring rebind
authority. Mutate the consent check to demonstrate the negative and positive
cases distinguish it. Regenerate and drift-check the CLI reference and test the
documented lifecycle vocabulary.

## Acceptance criteria

- Repeating a recorded path alone cannot accept a changed or legacy brief.
- `--confirm-brief-rebind` supplies a documented, headless, route-local way to
  accept exactly that baseline replacement.
- Refusals remain redacted and occur before any baseline, artifact, seed, or
  backend effect.
- A confirmed rebind records only the existing baseline-only acceptance fact;
  subsequent stage outcomes remain separately reported.
- #367 is reconciled in `BACKLOG.md` only after complete shipment.

## Deferred

If another roadmap authority needs confirmation, record its own evidence-backed
backlog item rather than extending this flag or extracting a shared framework.

## References

- `BACKLOG.md` — #367, the user-confirmed scope contract and delivery status.
- `plan_tool/roadmap.py:_run_roadmap` and `_resolve_brief_path` — current
  same-path rebind admission and source-identity boundary.
- `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` and `register` — stage-run CLI
  forwarding and route selection.
- `plan_tool/run_log.py:RoadmapSourceAdmissionDisposition`,
  `DATA_CONTRACT.md`, and `ROADMAP_FORMAT.md` — redacted admission lifecycle.
