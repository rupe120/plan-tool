> **Replaced**: this file has been superseded by `docs/implementation-plans/2-arm-clustering-cross-round-consensus.md`.
> Preserved here for history; do not edit.

# Seed: arm-clustering cross-round consensus

## Outcome

`evaluate_arm_clustering`'s consensus requirement (`plan_tool/audit_shapes.py:194`,
≥2 samples per material finding, single agreeing target) becomes satisfiable
from round-over-round `completeness-audit` history, not only from same-execution
multi-pass observations — so the advisory stays available on `--audit-passes 1`
runs, which CLAUDE.md's stopping rule recommends for scope-contract-bound audits
and which today disables the detector outright (the two settled conventions are
currently mutually exclusive by construction).

## In scope

- A new caller that builds `consensus_targets` / `material_finding_ids` /
  `declared_step_ids` from `build_collapsed_completeness_passes` history
  (`plan_tool/convergence_diagnosis.py:345`) and calls the existing
  `evaluate_arm_clustering` leaf unchanged.
- Cross-round finding identity reuses the existing tiered `_matches`
  (step focus → concept-slug anchor → fuzzy title, `convergence_diagnosis.py:462`)
  — the same identity already trusted by `classify_impact_recurrence` and
  `classify_edit_drift`. This seed does not invent a second identity scheme.
- A round's "target" is the matched finding's own persisted `RunFinding.step_id`
  at that round (already present in history; no new per-round field).
- Rendering the cross-round advisory on the same surfaces the same-execution one
  already uses (`plan-tool convergence`, completeness stderr), following the
  precedent of `_impact_recurrence_lines` / `_edit_drift_lines`.
- Updating CLAUDE.md's "Cycle-free import constraints" list if the new caller's
  placement adds an edge (e.g. `convergence_diagnosis.py` importing
  `audit_shapes.py`) not already enumerated there.
- This is itself the "separately scoped work" CLAUDE.md's convergence-policy-
  boundary section requires before `arm-clustering` gains a new caller class —
  landing it discharges that requirement; it does not pre-empt it.

## Overview

`arm-clustering` today only sees consensus built from ≥2 passes inside one
`completeness-audit` invocation, where the prompt's carried-findings mechanism
keeps a finding's `rec.id` stable across passes. `--audit-passes 1` — the
setting this repo's own stopping-rule convention steers scope-contract-bound
audits toward — collapses that to one sample, so the detector goes dark on
exactly the audits it is meant to help decide. A round-over-round version reads
persisted history across separate invocations instead, where finding ids are
not stable but step-focused matching already is (per `_matches`), and answers a
different, arguably stronger question: does this arm keep generating findings
despite genuine remediation attempts between rounds, not just within one frozen
snapshot.

## Problem statement

`evaluate_arm_clustering` takes `consensus_targets: Mapping[str, int]` as a
plain input; nothing about its own logic is same-execution-specific. The
mutual exclusion is entirely in what the *caller* (`review.py:8040`) currently
feeds it. Building an equivalent mapping from history requires answering the
"same target" question round-over-round without inventing new machinery for
it: a step can be renumbered, split, or merged between rounds, and the existing
`_matches` tiering exists precisely to survive that — it is the settled
precedent, not a gap to redesign.

## Architecture

1. Restrict to the newest `window` same-`audit_stage` collapsed completeness
   passes from `build_collapsed_completeness_passes`, mirroring
   `classify_impact_recurrence` / `classify_edit_drift`'s own windowing — never
   mix bare and detail-stage history in one consensus computation.
2. For each pass, take its material findings (however materiality is computed
   at that call site) and match each across the window via `_matches`. A
   finding needs a `_matches` hit in ≥2 passes to be consensus-eligible at all,
   mirroring the existing `len(sample_ids) < 2` guard.
3. A matched finding's target per round is its own `step_id`. Consensus holds
   only when every round in the match shares one target — identical to today's
   `len(target_ids) != 1` fail-closed check.
4. When a step's renumbering means no `step_id` continuity is even inferable
   under `_matches` (the finding itself still matches by anchor/title, but its
   target cannot be resolved to one committed step across the window), drop
   that finding from consensus for the round pair rather than guessing a target
   or asserting a broken arm. Fail-closed, not fail-loud — matching
   `evaluate_arm_clustering`'s own posture when inputs are ambiguous.
5. Feed the resulting `consensus_targets` and the newest round's committed
   `declared_step_ids` / material finding set into `evaluate_arm_clustering`
   unchanged. The leaf's own gap-free proper-majority-arm math is not touched.

## Out of scope

- Any change to `evaluate_arm_clustering`'s own signature or arm math in
  `audit_shapes.py` — it already accepts a plain mapping; this seed supplies a
  second way to build one.
- Any change to the existing same-execution (`--audit-passes N > 1`) consensus
  path in `review.py` — both paths coexist.
- Any new blocking gate, exit-code flip, or apply-dispatch keyed on the
  advisory. `arm-clustering` stays recommend-only, exactly as
  `impact_recurrence` / `edit_drift` are — this seed adds an evidence source,
  not a gate.
- Reviving the retired `spinning` / `FORK_*` region-trending diagnostic
  (BACKLOG #251, cut 2026-08-08) or any of its vocabulary — this works over
  adjacent territory (cross-round finding history) and must not resemble it.
- Modifying `classify_impact_recurrence` / `classify_edit_drift`'s own logic;
  their exposed helpers (`build_collapsed_completeness_passes`, `_matches`) are
  consumed read-only.
- Changing `--audit-passes 1`'s behavior, the stopping-rule recommendation, or
  any other convergence-policy-boundary caller class.
- Backfilling consensus for history predating this change, or for rounds run
  at a different `audit_stage` than the newest one.

## Allowed behavior changes

- `arm-clustering` becomes computable and renderable from round-over-round
  history on `--audit-passes 1` runs, in addition to its existing
  same-execution path. No other advisory's eligibility or rendering changes.

## Allowed reorganization

Only the new caller function itself, placed wherever it can reach both
`build_collapsed_completeness_passes`/`_matches` and `evaluate_arm_clustering`
without introducing an import edge CLAUDE.md's constraints list forbids; update
that list if the placement adds a legitimate new one (e.g. `convergence_
diagnosis.py` → `audit_shapes.py`, which is acyclic since `audit_shapes.py` is
a pure leaf). No other module boundary moves.

## Risks

- A naive per-round target could silently misattribute a finding across a
  renumbered step if `_matches` is bypassed instead of reused — this is why
  reuse, not reinvention, is the settled decision above.
- Treating a fail-closed drop (step 4) as "no consensus, arm broken" rather
  than "insufficient evidence this round" would produce a false negative that
  reads as the arm resolving when it merely became unmeasurable — the wording
  of any rendered line must distinguish the two.
- Windowing on the wrong `audit_stage` (mixing bare and detail history) would
  manufacture a consensus target that never coexisted in one coherent audit.

## Testing

Prove: (1) a finding with a stable `_matches` identity and one agreeing
`step_id` across ≥2 same-stage rounds produces a consensus target equivalent to
today's same-execution result; (2) a finding whose matched `step_id` disagrees
across rounds yields no consensus target, not a guessed one; (3) a renumbered
step that breaks `step_id` continuity but still matches by anchor/title drops
out of consensus rather than asserting a broken arm; (4) mixed-stage history is
never combined into one window; (5) `--audit-passes 1` with ≥2 qualifying prior
rounds now produces an `arm-clustering` advisory where it previously produced
none, while the same-execution multi-pass path is unchanged by this work.

## Acceptance criteria

- `evaluate_arm_clustering` fires from round-over-round history alone under
  `--audit-passes 1`, using only existing cross-round identity machinery
  (`_matches`, `build_collapsed_completeness_passes`).
- The same-execution consensus path and the leaf itself are unmodified.
- `arm-clustering` remains recommend-only: no gate, dispatch path, or
  continuation rule reads the cross-round result any differently than the
  same-execution one does today.
- CLAUDE.md's Cycle-free import constraints list reflects any import edge this
  work actually adds.
- BACKLOG.md's #264 entry is removed (or updated to note partial delivery, if
  scope is deliberately trimmed during execution) once this ships.

## Deferred

Any generalization of cross-round `_matches`-based consensus to a signal beyond
`arm-clustering` is a separate, separately scoped effort. The retired region-
trending diagnostic (BACKLOG #251) stays retired; this seed does not reopen it.
