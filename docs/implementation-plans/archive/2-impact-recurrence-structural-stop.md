---
title: Impact Recurrence Structural Stop
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Make the shared history helpers in convergence_diagnosis public
  files:
  - plan_tool/convergence_diagnosis.py
  - plan_tool/telemetry_analysis.py
  - tests/test_convergence_diagnosis.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/impact-recurrence-structural-stop/01-make-shared-history-helpers-convergence.md
  status: current
- id: 2
  title: Carry each finding's impact and impact provenance into RunFinding
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  - tests/test_review_persistence.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/impact-recurrence-structural-stop/02-carry-each-finding-impact-impact.md
- id: 3
  title: Add an impact-recurrence classifier that spots a still-open high-impact region
    across three passes
  creates:
  - plan_tool/impact_recurrence.py
  - tests/test_impact_recurrence.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/impact-recurrence-structural-stop/03-impact-recurrence-classifier-that-spots.md
- id: 4
  title: Add the recommend-only next action and rendering for a recurring high-impact
    seam
  files:
  - plan_tool/impact_recurrence.py
  - tests/test_impact_recurrence.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/impact-recurrence-structural-stop/04-recommend-only-next-action-rendering.md
- id: 5
  title: Add a structural_stop reason to should_continue for a caller-supplied recurring
    seam
  files:
  - plan_tool/convergence.py
  - tests/test_convergence.py
  complexity: low
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/impact-recurrence-structural-stop/05-structural-stop-reason-should-continue.md
- id: 6
  title: Stop the completeness iterate loop on a recurring high-impact seam
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/impact-recurrence-structural-stop/06-stop-completeness-iterate-loop-on.md
- id: 7
  title: Stop the reconcile iterate loop on a recurring high-impact seam
  files:
  - plan_tool/cli/reconcile.py
  - tests/test_cli.py
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/impact-recurrence-structural-stop/07-stop-reconcile-iterate-loop-on.md
- id: 8
  title: 'Document the new stop and close out BACKLOG item #158'
  files:
  - docs/AUDIT_FLOW.md
  - RUNBOOK.md
  - DATA_CONTRACT.md
  - CLAUDE.md
  - BACKLOG.md
  - plan_tool/telemetry.py
  - plan_tool/telemetry_analysis.py
  - tests/test_telemetry_analysis.py
  complexity: low
  change_type: non-code
  depends_on:
  - 6
  - 7
  detail: docs/implementation-plans/plan-details/impact-recurrence-structural-stop/08-document-new-stop-close-out-backlog.md
---
# Impact Recurrence Structural Stop

> **Superseded; do not execute.** The audit loop diagnosed this decomposition as
> **spinning / structural** on 2026-07-20 (`plan-tool convergence` window 3;
> `split-criteria` altitude-3 `structural: fires (high)`): it decomposes **by code
> artifact**, so each of four design contracts straddles 3–4 steps and no finding
> can localize to one step. Do not revive this cut. `BACKLOG.md` #158 owns the
> outcome, re-seeded 2026-07-20 as two plans that land each contract whole inside
> one step — `plan-seeds/impact-recurrence-01-classifier.md` (offline classifier,
> no loop wiring) and `plan-seeds/impact-recurrence-02-loop-stop.md` (loop
> integration; depends on part 1). Archived 2026-08-02.

## Overview

Add a distinct impact-recurrence classifier and a structural stop to live completeness and reconcile iteration, implementing BACKLOG.md item #158. Persisted `Recommendation.impact` values are normalized with explicit-versus-legacy provenance so the loop can tell whether the same open high-impact seam (a matched region) keeps recurring across passes. The loop stops only after three newest consecutive compatible passes retain that seam without shrinkage, and it emits a non-successful `recurring_high_impact_seam` / `structural_stop` outcome rather than reporting success. Existing severity and decomposition diagnosis behavior is preserved and rendered alongside the distinct impact result; remediation stays recommend-only.

## Problem statement

Live completeness and reconcile iteration today has no way to distinguish a recurring high-impact seam from ordinary iteration churn, so a loop can keep spinning on the same unshrinking region and still exit as if it converged. Existing sidecars retain impact but do not retain whether an absent value is legacy; normalization must preserve that distinction before history can support a conservative stop. The user-visible symptom is an iteration that reports a successful outcome while the same high-impact seam stays open pass after pass.

## Architecture

A distinct impact-recurrence classifier is introduced alongside the existing severity/decomposition diagnosis, which keeps its current behavior unchanged. It uses existing persisted impact values plus a normalized explicit/legacy provenance field to compare successive passes for the same open high-impact seam and its count trend. The stop condition is evaluated only after normal apply work and report persistence, before the next Claude pass; it requires three newest consecutive compatible passes retaining the same seam without shrinkage. On trigger the loop emits a non-successful `recurring_high_impact_seam` / `structural_stop` outcome while preserving any ordinary severity/decomposition diagnosis. Remediation is recommend-only: a localized split or scope-out is recommended only when the impact evidence identifies a specific step; otherwise the recommendation falls back to conservative re-decomposition.

## References

- [RFC 8259 — The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259) — The primary specification each persisted provenance record must conform to, including value types, encoding, and duplicate-name behavior when round-tripping report sidecars.
- [Python `json` — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — API reference for serializing and tolerantly re-reading the persisted impact-provenance records, including custom encoders, `object_hook`, and `JSONDecodeError` handling for partial or legacy rows.
- [Python `dataclasses` — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Reference for `frozen=True`, `field`, and `asdict`, matching the codebase convention of frozen result records for the new impact-recurrence classifier's outcome type.
- [Python `enum` — Support for enumerations](https://docs.python.org/3/library/enum.html) — Covers `StrEnum`/`Enum` semantics for modeling the new non-successful outcome tokens (`recurring_high_impact_seam`, `structural_stop`) as stable serializable constants.
- [pytest — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Reference for table-driven regression tests over consecutive-pass sequences, which is the cleanest way to cover the three-pass no-shrinkage stop condition and its near-miss cases.
- [pytest — How to use temporary directories and files (`tmp_path`)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Documents the hermetic temp-directory fixtures required for tests that write and re-read persisted per-pass impact provenance without leaking state between runs.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing existing severity or decomposition diagnosis behavior — it stays unchanged; the impact-recurrence classifier is added alongside it, not folded into it.
- Auto-applying any structural remedy (split, scope-out, merge, re-ground, re-seed) on a recurring seam — remediation stays recommend-only, preserving the tool-wide rule that mutation is gated behind an explicit opt-in and confirm.
- Extending `convergence.is_blocking_impact` or the calibrated impact policy to new callers (completeness continuation, deterministic/reporting gates, prompts, schemas, `Recommendation`, `convergence_diagnosis.py`) — that boundary is deliberately narrow and changing it is separately scoped work.
- Cross-run historical diagnosis from saved report sidecars (`convergence_diagnosis.py` / `plan-tool convergence`) — this plan stops a *live* iterate loop; the offline spinning/converging verdict keeps its own surface.
- Auto-tuning the three-pass threshold or exposing it as a user flag — the threshold is a fixed constant so the stop stays explainable and reproducible; step 8 records structural-stop decision events through the existing telemetry path for later calibration.
- New `--jobs`/parallel surfaces or fan-out for the classifier — it is a cheap deterministic read over already-persisted evidence and spends no Claude.
- A second telemetry or evidence store — impact provenance rides on the existing persisted report records rather than introducing a parallel sidecar to keep in sync.

## Risks

- **False-positive stop on ordinary churn.** A loop that would have converged on the next pass is halted because the same high-impact seam happened to persist across three passes without measurable shrinkage. Severity: medium. Mitigation: the stop runs only after normal apply work, requires three newest consecutive same-series passes with usable impact evidence, and a code-fingerprint change breaks the streak. The recommendation tells the operator to apply the outstanding conceptual finding or use the existing remedy before a further iteration. Residual: "no shrinkage" is inferred from persisted recommendation evidence, not from measured region size.
- **False-negative — the seam is never recognized.** Recurrence detection uses the shared tiered region matcher (step focus, anchor, then title similarity); a genuinely recurring seam reported under drifting identity can reset the streak. Severity: medium. The conservative direction is a miss rather than a false correlation; no additional fuzzy matcher is introduced here.
- **Evidence gaps from legacy or partial records.** Persisted rows written before step 2 carry no impact provenance, and a partially-written row can fail to parse. Severity: low. Mitigation: reading stays tolerant — a row without provenance is counted but unresolved and cannot start or extend a streak, matching the existing ownerless/legacy telemetry convention. Consequence: immediately after this ships, the stop is inert until three new passes have accumulated.
- **Scope creep into the calibrated impact policy.** The classifier reads the same impact field `convergence.is_blocking_impact` calibrates, inviting a future change to widen that deliberately narrow boundary. Severity: high if it happens — it would silently change blocking semantics for every completeness caller. Mitigation: the new classifier lives in its own module and computes its own predicate; extending `is_blocking_impact` to new callers is explicitly out of scope.
- **Two diagnosis surfaces drifting apart.** This live stop and the offline `convergence_diagnosis.py` spinning verdict answer a similar question from different evidence and can disagree, confusing an operator who runs both. Severity: low. Mitigation: the live stop emits its own distinct `recurring_high_impact_seam` / `structural_stop` tokens rather than reusing the offline fork names, so the two verdicts are never mistaken for one another. Accepted residual: the plan does not unify them.
- **Recommendation quality when impact evidence is coarse.** When provenance identifies no specific step, the recommendation degrades to conservative re-decomposition, which is blunt advice on a large plan. Severity: low — advisory only. Accepted: a vague-but-honest recommendation is preferred over guessing a split target from prose.
- **Wiring regressions in the two loop call sites.** Steps 6 and 7 thread a new stop reason through completeness and reconcile iteration; a mis-wired reason could suppress a legitimate continuation or mask an unrelated stop. Severity: medium. Mitigation: `should_continue` gains the reason as a caller-supplied input (step 5) rather than reaching for state itself, and each call site lands with its own regression tests.

## Testing

Add regression tests covering the new impact-recurrence classifier and structural stop behavior.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- Persisted `Recommendation.impact` values are normalized with explicit-versus-legacy provenance through live completeness and reconcile iteration.
- The structural stop triggers only after normal apply work, report persistence, and three newest consecutive compatible passes retain the same open high-impact seam without shrinkage.
- Existing severity/decomposition diagnosis semantics are unchanged.
- The loop emits a non-successful `recurring_high_impact_seam` / `structural_stop` outcome when the stop triggers.
- A localized split/scope-out is recommended (recommend-only, never applied) when impact evidence identifies a step; otherwise a conservative re-decomposition is recommended; concurrent ordinary diagnosis evidence remains visible.
- Classifier failures fall through to existing loop behavior; the structural stop preserves the command's successful exit and report persistence.
- Regression tests cover the classifier and structural stop.
- BACKLOG.md item #158 completion tracking is updated when the work ships.

## Deferred

- **Fuzzy identity matching for a seam whose region identity drifts across passes** — recurrence keys on stable persisted identity, so a retitled or renumbered region resets the streak. Deferred because a fallback matcher needs its own similarity contract and false-match budget; the conservative miss is acceptable until that is designed.
- **Measured region-size shrinkage** — "no shrinkage" is inferred from persisted recommendation evidence rather than a measured region size. Deferred because a real size metric implies a new evidence field and a migration for existing rows; the inferred signal is adequate for the first cut.
- **Backfilling impact provenance onto pre-existing persisted rows** — the stop is inert until three new passes accumulate. Deferred because a migration pass over historical sidecars is a separate concern from the live loop this plan changes.
- **Unifying the live structural stop with the offline `convergence_diagnosis.py` verdict** — the two answer a similar question from different evidence and can disagree. Deferred because reconciling them is a design question spanning both surfaces, not a wiring change.
- **Threading the stop into the remaining Claude-invoking iterate loops (`create`, `detail`)** — only completeness and reconcile are wired here. Deferred to keep the first landing's blast radius to the two loops BACKLOG #158 names.
- **Operator-tunable pass threshold** — three passes is a fixed constant. Deferred because exposing a knob invites per-run tuning that makes the stop unexplainable; revisit only if field evidence shows three is wrong.
