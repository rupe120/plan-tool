---
title: Deferred Roadmap Source Baseline Recovery
intent: Preserve the user-confirmed deferral of reusable roadmap source-baseline
  recovery and the evidence needed to reconsider it, without authorizing recovery
  design or implementation.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/archive/roadmap-source-baseline-recovery.replaced.md
steps:
- id: 1
  title: Defer reusable source-baseline recovery
  intent: Keep a reusable recovery capability out of active scope; the single Integration
    2:3 source-baseline stop does not itself justify a new recovery subsystem.
  files:
  - plan_tool/roadmap.py
  - plan_tool/roadmap_source_identity.py
  - plan_tool/roadmap_revision_publish.py
  - plan_tool/roadmap_seed_state.py
  - tests/test_roadmap.py
  - tests/test_roadmap_source_identity.py
  - tests/test_roadmap_revision_publish.py
  - tests/test_roadmap_seed_state.py
  complexity: high
  change_type: feature
  status: pending
  scope: deferred
  status_note: >-
    Deferred 2026-08-27 (user-confirmed): reconsider only for a second independently
    justified recovery need or an explicit request for a bounded one-time Integration 2:3
    remedy.
- id: 2
  title: Keep existing baseline authority unchanged
  intent: Leave ordinary drift refusal, baseline enrollment, and canonical-publication
    writer authority unchanged while recovery is deferred.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/cli/__init__.py
  - tests/cli/test_roadmap_cmd.py
  - docs/cli/roadmap.md
  - ROADMAP_FORMAT.md
  - RUNBOOK.md
  complexity: medium
  change_type: feature
  status: pending
  scope: deferred
  status_note: >-
    Deferred 2026-08-27 (user-confirmed): no recovery command or authority design is
    active.
  depends_on:
  - 1
  depends_on_notes:
    1: Re-entry first requires a separately justified decision to build a recovery route.
- id: 3
  title: Retain the Integration evidence boundary and re-entry condition
  intent: "Keep #242 and the exact receipt paused until a new, explicitly authorized
    decision supersedes this deferral."
  files:
  - tests/test_roadmap_escalation_run.py
  - tests/test_roadmap_impact_run.py
  - tests/test_roadmap_structural_revision.py
  - docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md
  - handoffs/2026-08-27-integration-roadmap-evidence-preflight.md
  complexity: medium
  change_type: feature
  status: pending
  scope: deferred
  status_note: >-
    Deferred 2026-08-27 (user-confirmed): do not re-run Integration analysis merely to
    reopen this receipt.
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: The recovery direction remains deferred.
    2: Existing authority remains the only authority.
---
# Deferred Roadmap Source Baseline Recovery

## Overview

**Deferred 2026-08-27 (user-confirmed).** This plan records why the Integration
source-baseline stop does not authorize a reusable recovery capability. The
exact receipt remains fail-closed and #242 remains paused; no recovery command,
implementation work, or Integration re-evaluation follows from this plan.

## Problem statement

The single known Integration case affects existing baselines for stages 2:3 after an
intentional direct source change. The latest bare-plan audit showed that making
this reusable would require durable confirmation binding, interruption
ownership, derived-seed source binding, and an unambiguous Integration follow-up. Those
are a recovery subsystem, not the smallest proof for one blocked receipt.

## References

- `ROADMAP_FORMAT.md` — defines canonical roadmap source and admission requirements.
- `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — records the
  blocked Integration roadmap evidence arc and this deferral's re-entry condition.
- `handoffs/2026-08-27-integration-roadmap-evidence-preflight.md` — preserves the exact
  receipt evidence and operational boundary.
- `plan-seeds/archive/roadmap-source-baseline-recovery.replaced.md` — retains the
  earlier proposal as history; it is not an active implementation specification.

## Architecture

No recovery architecture is selected. Ordinary source-drift refusal, baseline
enrollment, canonical-publication writers, artifact immutability, and
equality-based evidence currentness remain the active design. This plan does not
create an alternate authority or a one-time exception.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Reusable recovery implementation, a generic accept-current action, automatic
  baseline refresh, manual baseline-state edits, or an authority substitute for
  ordinary source admission.
- A one-time Integration 2:3 workaround without a new explicit user decision.
- Retention redesign, structural-rewrite selection, cross-artifact transactions,
  or rerunning the paused Integration evidence work.

## Risks

- Treating one intentional source change as sufficient proof for a reusable
  authority would expand #242's blocked evidence work into a new subsystem.
- Retrying the unchanged receipt could be mistaken for progress despite the same
  fail-closed source admission result.
- Leaving the earlier proposal marked active could authorize work the user deferred.

## Testing

No recovery code changes are active, so no implementation test work follows.
Any new authorization starts with a fresh bare plan grounded in the then-current
code and Integration evidence; it selects only the tests needed for its chosen scope.

## Acceptance criteria

- All three steps remain `scope: deferred`; no recovery code or command is
  authorized by this plan.
- The roadmap arc and handoff retain the exact Integration receipt, affected 2:3 range,
  and the reason #242 remains paused.
- Re-entry requires either a second independently justified source-baseline
  recovery need or an explicit user request for a bounded one-time Integration 2:3
  remedy. It starts with a fresh bare plan rather than reviving this proposal.

## Deferred

- **User-confirmed 2026-08-27:** reusable roadmap source-baseline recovery and
  #242's blocked Integration route are deferred. The prior proposal is retained only as
  historical context; no later session should infer current authorization from it.
