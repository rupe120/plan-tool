> **Replaced**: this file has been superseded by `docs/implementation-plans/2-audit-shape-registry.md`.
> Preserved here for history; do not edit.

# Audit-shape registry

## Outcome

The five audit traps in CLAUDE.md's "Audit the why, not the what" section have
stable ids and a checked versus judgment-only classification. The three
mechanically observable shapes produce advisory, citable report signals from
persisted audit data; the two judgment-only shapes are recorded as never-fire.
A validate-time drift check prevents the registry and CLAUDE.md's authoritative
five-shape list from diverging. No shape gates, changes an exit code, or
automatically applies a remedy.

## Overview

This is BACKLOG #224's tool-side half of the standing rule that a fired audit
shape is a scope decision, not a nag. It makes a silent override costly by
giving the signal a stable name, an observable tell, and an explicit statement
of what the operator is overriding. The tool remains advisory: it surfaces a
reason to stop and re-ask, then leaves the scope decision to the user.

## Problem statement

CLAUDE.md currently describes five recurring audit traps only as prose. That
leaves the checked versus judgment-only boundary vulnerable to accidental
expansion: a later session can convert "this remedy seems too big" into a
high-false-positive detector, or treat a clustering signal as merely another
finding to apply.

The existing taper warning also routes a round-two signal to plan-tool
convergence, which needs three cross-run reports and therefore answers
insufficient-history at the exact point where a carve is cheapest. On
intent-required, the warning correctly identified an under-decomposed arm, but
15 findings were applied before that arm was carved.

## Architecture

Add plan_tool/audit_shapes.py as a stdlib-only leaf. It owns one canonical,
ordered entry per CLAUDE.md audit shape: stable id, one-line tell, and a
checked or judgment-only discriminator. It owns parsing or comparison helpers
needed for the registry's deterministic consumers, without importing audit
or CLI modules.

The five shapes and their classification are settled:

1. checked: arm clustering. Findings already carry step_id, so concentration
   in a step or contiguous arm within one report is arithmetic. It replaces
   the round-two dead-end with a per-report advisory that identifies the
   concentrated arm and directs the operator to the existing scope decision.
2. checked: check saturation. A source firing across every applicable artifact
   is a count over persisted findings. It says investigate the producer chain;
   it must not claim statically that no producer exists.
3. judgment-only: measurement instrument adequacy. Whether a method can see
   the relevant data needs significance and ground truth the tool does not
   possess.
4. checked: self-seeded finding. A cited file or region intersecting commits
   since the previous report is observable from persisted report context and
   git history. It points out the provenance loop; it does not decide whether
   the edit was justified.
5. judgment-only: remedy proportionality. Whether the remedy outgrew the
   defect is a human scope judgment and must never become a detector.

Checked shapes report only from data already persisted by the existing audit
flows. Their thresholds are calibrated against saved report history rather
than guessed. If a checked shape has a high false-positive rate on this
repository's history, remove its reporting behavior and classify it
judgment-only; never tune thresholds merely to quiet it.

The registry is pinned to the authoritative CLAUDE.md list through the same
validate-time, no-Claude honesty-check pattern used for the capability
catalog. The source text must carry the stable identifiers in a form the drift
check can verify. A mismatch is surfaced by validate; it does not introduce an
unrelated gate, audit exit-code flip, or mutation.

When a checked shape fires, report its stable id, the observable evidence, and
the override rule: name the affected arm or source, explain why it still
belongs or propose a carve, and say plainly when continuing overrides the
signal. Detection is unconditional; all mutation remains explicitly gated.

## In scope

- plan_tool/audit_shapes.py and its focused tests.
- The report surfaces for arm clustering, check saturation, and self-seeded
  findings.
- The validate-time drift check that keeps the registry synchronized with
  CLAUDE.md's five-shape list.
- CLAUDE.md documentation and tests that pin the checked versus judgment-only
  boundary.
- Calibration against saved report history and a documented kill-to-
  judgment-only outcome for an unacceptably noisy checked shape.

## Out of scope

- Any detector, heuristic, finding, or auto-remedy for measurement instrument
  adequacy or remedy proportionality.
- A gate, exit-code flip, or refusal-to-advance based on any audit shape.
- Automatically carving an arm, applying a finding, or tuning thresholds from
  telemetry.
- Extending convergence.is_blocking_impact to another caller.
- A generic semantic judgment about whether an arm belongs, a producer is
  missing, an instrument is adequate, or a remedy is proportional.

## Allowed behavior changes

Three new advisory finding classes and one validate-time registry drift check.
Nothing else changes observable command success or mutation behavior.

## Allowed reorganization

None. New registry and reporting seams must preserve existing ownership
boundaries rather than relocate audit logic.

## Risks

The checked/judgment boundary is the main risk: an attractive but subjective
detector would recreate the prose-conformance failure this work prevents.
Historical reports may be too sparse to justify a threshold. In that case,
leave the shape judgment-only rather than guessing or adding a noisy signal.
Git provenance for self-seeded findings must be scoped to the cited
file/region and the previous report, not inferred from broad assignment scans.

## Testing

The registry round-trips all five stable ids and classifications. The
validate-time check detects a missing, renamed, reordered, or reclassified
CLAUDE.md shape. A concentrated report names the clustering id; a source that
fires on every applicable artifact names saturation; a finding whose cited
region changed since the previous report names self-seeded. The two
judgment-only ids have no emitter path and cannot change an exit code. Tests
also cover the round-two clustering route and the false-positive kill outcome.

## Acceptance criteria

- Exactly five registry entries match the CLAUDE.md list and each has a stable
  id, tell, and checked or judgment-only classification.
- The three checked shapes emit advisory, evidence-bearing signals only from
  persisted data; no signal decides merit or mutates a plan.
- The two judgment-only shapes are citable but cannot emit a finding.
- Validate exposes registry/document drift without invoking a model or
  changing an exit-code convention outside validate's normal failure behavior.
- A round-two clustering signal gives an actionable scope-decision prompt
  instead of routing solely to cross-run convergence history.
- Every fired checked shape tells the operator what a deliberate override must
  state, while leaving the user in control.
- BACKLOG #224 is updated when the work ships, including any killed shape or
  deferred calibration evidence.

## Deferred

The rest of the audit-shape catalog, a generic history/telemetry threshold
trainer, automated remedies, and cross-command mutation policy belong to later
work.

## Stop / defer

If saved-report calibration shows a checked shape is noisy, reclassify it as
judgment-only and record the evidence in BACKLOG.md. Do not keep narrowing or
raising thresholds to preserve a detector that does not earn operator trust.
