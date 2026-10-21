> **Replaced**: this file has been superseded by `docs/implementation-plans/2-jira-grade-detail-side-by-side-evaluation.md`.
> Preserved here for history; do not edit.

## Overview

Add an explicit jira-grade detail mode beside the existing run-grade path so the same plan can retain comparable detail bundles for `jira` and an opt-in `run` path. Run-grade remains the default, legacy bundles remain run-grade, and both contracts must be selected without ambiguity. Record a small, reproducible paired evaluation so a later plan can decide whether jira-grade should become the default.

## Problem statement

Today `detail` creates implementation-grade prose for `run`, while `jira` down-converts it into a story. Run-grade detail commits to volatile facts such as precise edits, named call sites, test rosters, and prescribed mechanics; after scope changes, those commitments can become stale and cause audit churn even when the design is still correct. Jira-grade detail may reduce that contradiction surface, but changing the default without a matched control would leave its effect on execution quality, retries, and diff scope adherence unknown.

## Architecture

Keep the existing run-grade detail format, parser, artifact selection, and `run` renderer as the control. Add a compact jira-grade contract with `Intent`/problem, `Change`, `Constraints`, `Done when`, and `Out of scope`, aligned with or sequenced after BACKLOG #149's compact schema; it should describe outcomes and boundaries rather than prescribe edits, tests, or algorithms unless a declared constraint requires them.

Add explicit depth selection and separate, collision-safe artifact routing so run-grade and jira-grade bundles can coexist for one plan. Legacy bundles are always read as run-grade and must never be silently rewritten or reinterpreted. `jira` consumes jira-grade detail directly, while an opt-in jira-grade `run` renderer receives the same schema plus normal plan/repository grounding and leaves implementation choices to the executor.

Provide a repeatable paired-evaluation harness or documented command sequence using the same baseline, plan steps, repository revision, and verification command for both depths. Predeclare the adoption threshold before measurement; only a later plan may invert the default if the report shows jira-grade is no worse on first-pass green rate and scope adherence/diff quality, does not materially regress retries, elapsed time, or available cost telemetry, and reduces scope-change audit churn.

## Out of scope

- Making jira-grade detail the default for `detail`, `run`, or `jira`; default inversion requires a later evidence-backed plan.
- Re-authoring or bulk-rewriting existing run-grade bundles; legacy compatibility is preserved instead.
- Changing plan-body schema, step decomposition, `change_type`, or completeness audit logic; this experiment is limited to detail contracts and consumers.
- Weakening audit checks to make the experiment appear more successful; evidence must remain comparable.
- A corpus-wide benchmark or broad model comparison; this is a focused decision experiment with recorded provenance.

## Risks

- **Run quality regression:** thinner detail may cause more rediscovery, retries, or incorrect diffs. Severity: high. Mitigation: unchanged run-grade control, paired inputs, a predeclared gate, and no default flip here.
- **Artifact ambiguity:** mixed-depth files could cause a run to consume the wrong contract. Severity: high. Mitigation: explicit mode/depth selection, isolated storage or unambiguous metadata, and tests that reject ambiguous selection.
- **Metric noise:** backend nondeterminism can swamp one-off outcomes. Severity: medium. Mitigation: record every setting and raw result, compare matched runs, and mark thin evidence indeterminate rather than extrapolating.
- **Schema duplication with #149:** two compact contracts could drift. Severity: medium. Mitigation: sequence #149 first or define one shared token/alias layer; do not create competing required-section authorities.

## Testing

Test both contracts, legacy run-grade read compatibility, explicit artifact selection, ambiguous or mislabeled selection failures, and prompt routing while confirming no default changed. Add fixture coverage for paired-run provenance and metric calculations.

Run the paired evaluation against at least one real plan with nontrivial implementation work and a deliberately scoped change. Record matched baseline inputs, repository revision, backend/model settings, commands, timestamps, first-pass result, retries, elapsed time, available cost/tool-use telemetry, verification outcome, human-reviewed scope-adherence/diff-quality verdict, controlled scope-change replay, and `completeness-audit` findings.

After the detail bundle exists, follow `CLAUDE.md` manual-convergence policy: run `completeness-audit` with `--iterate`, save and review reports, apply in-scope conceptual corrections with judgment, and re-audit without auto-driving `completeness-apply`. Capture baseline, post-correction, and third audit snapshots; compare stable finding identities and material severities, and stop patching when high-impact findings recur, material findings stay flat, or an architecture contradiction emerges.

## Acceptance criteria

- Run-grade detail remains the default, and legacy run-grade bundles remain readable and executable without a rewrite.
- An explicit jira-grade mode produces and selects artifacts independently from run-grade for the same plan; ambiguous or mislabeled selection fails clearly.
- Jira-grade detail validates a compact schema focused on intent, change, constraints, acceptance, and exclusions, aligned with #149 where applicable.
- `jira` consumes jira-grade detail directly, and an opt-in `run` path renders from it while the existing run-grade renderer remains available as the control.
- Tests cover both contracts, legacy read compatibility, artifact selection, prompt routing, and that no default changed.
- A durable paired-evaluation report records the matched baseline, commands, raw outcomes, specified execution metrics, controlled scope-change audit result, and recommendation against a threshold declared before measurement.
- No default inversion ships from this plan; a later plan may propose one only when the report passes its declared gate.
- The final documentation/status step reconciles BACKLOG #164 without removing it merely because this plan was authored; out-of-scope audit findings are routed to `BACKLOG.md` or `BUG_BACKLOG.md`.

## Deferred

- Default inversion and any migration or re-authoring policy for the existing corpus; require passing evidence and a separate plan.
- An escape hatch for individual jira-grade steps that need mechanically prescriptive supplemental detail; determine this from experiment failures rather than expanding the base schema preemptively.
- Wider benchmark automation and repeated-sample statistical confidence beyond the focused paired experiment.

## Input

This plan consumes the existing run-grade detail format, parser, artifact selection, and `run` renderer as its unchanged control, with legacy bundles interpreted as run-grade. It also depends on BACKLOG #164's scope/lifecycle contract, BACKLOG #149's compact-schema alignment, `CLAUDE.md` manual-convergence policy, and saved `completeness-audit` reports; the paired report must record the plan, steps, repository revision, backend/model settings, commands, timestamps, raw artifact/report locations, and outcomes.
