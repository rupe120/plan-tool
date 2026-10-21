# Roadmap derivation correction pickup

## Current direction

Improve the existing roadmap mapping → per-row seeds → create workflow. PR #105’s alternative creation mode and persistent set record are withdrawn by owner direction on 2026-10-16. The archived plan and its audit reports document that superseded scope; their clean findings do not certify the replacement.

BACKLOG #496 and plan-seeds/archive/roadmap-plan-derivation.replaced.md carry the corrected scope. The replacement branch is plan/roadmap-plan-derivation, based on origin/main 7f45215ec, in /private/tmp/plan-tool-roadmap-plan-set-20261016. Integration remains a frozen benchmark; no application implementation runs.

## Seed review

Identifier and vocabulary searches enumerate the prior proposal in its plan/details, archived seed, BACKLOG #496, benchmark evidence and this handoff. Native withdraw archives and deregisters the prior plan/details; archived seed provenance stays intact. Update the live backlog, evidence and handoff together. The replacement introduces no alternative authoring layer.

Source checks confirm stage four already supports split/merge mapping, stays repository independent, and materialization receives the accepted four-artifact bundle plus repository grounding for one selected row. The seed’s Outcome and seven scope fields match #496 verbatim. Seed-altitude review finds no material correctness issue or HIGH/CRITICAL omission that prevents decomposition. Implementation mechanics remain for create/detail. Instrument category (b) and its limits are recorded in #496.

## Completed authoring and verification

- Create uses explicit clone PYTHONPATH, backend codex, model gpt-6.1-sol, --iterate and closed stdin. Native run 2026-10-16T16-49-13+00-00-f4251a ends successfully; five steps are authored. Local References are again replaced by research output; restore source references before the bare audit and retain this witnessed create loss as step 3 evidence. Simplify the generated step 3 title without changing its preservation contract.
- Bare audit: completeness-audit roadmap-plan-derivation --iterate --audit-passes 1 --commit -y. Report 20261016-165253-completeness.md is clean, confirmed/current, run grade, 0/5 detailed; detail axes are withheld. Native run 2026-10-16T16-52-34+00-00-45896f ends successfully.
- Detail: detail roadmap-plan-derivation --no-completeness --commit -y, one-shot. All five details commit individually; native run 2026-10-16T16-53-07+00-00-c7d79d ends successfully. Session link review enumerates 21 broken targets in details 1/2/3/5, corrects the class and verifies every local detail link resolves.
- Full detail audit: same iterative audit command. Report 20261016-170021-completeness.md is clean, confirmed/current, run grade, 5/5 detailed with zero deterministic, correctness or completeness findings. Shell exits 0; verify native run_end before publication.
- Thirty backlog tests pass. No full suite or Claude Code review is claimed for this plan-only change. No conceptual finding-remediation loop or unchanged conceptual resampling occurs.

## Publication and next boundary

The user directs a new PR after #105 merges. Publish plan/roadmap-plan-derivation to main with the corrected five-step bundle and native withdrawal of the superseded proposal. No changelog fragment is needed for planning artifacts; implementation supplies one. After the user/architect merges, verify origin/main contains the bundle, branch separately for implementation, and drive run --commit with gpt-6.1-sol followed by the prescribed reconciliation and review tails. Never self-merge or use --skip-merge-check.

## Explicit granularity objective

The owner clarifies that improved plan-level granularity is the primary outcome: replace the overly high-level Integration-style breakdown with cohesive, dependency-ordered implementation routes. Plan intent, overview, problem, acceptance, steps 1/5, details 1/2/5 and #496 align. More internal steps or retained context alone do not establish this result; the comparison must show source-backed improvements in plan boundaries and remaining broad routes. Archived seeds retain their original provenance; the live plan and #496 contain this clarification. Re-audit 20261016-170558-completeness.md is clean, confirmed/current, run grade, 5/5 detailed, with zero findings. Native run completion and shell exit are verified before pushing the update to PR #106.
