# Project model selection plan review

| Item | Evidence |
| --- | --- |
| Scope | Plan and detail authoring; copied-skill validation backlog #525 |
| Review range | `cf98ac17e99c8a37a294cb126a75f01408c1504e...plan/project-model-selection` |
| Audited content checkpoint | `74ed3976b`; final report commit `5d35d1ac2` |
| Reviewer | Codex session judgment and plan-tool Codex conceptual audits |
| Checks | 228 existing focused tests pass; plan validation and four detail parsers pass |
| Disposition | Converged: final bare and detail-grounded audits are clean, confirmed, and current |

## Settled scope

The plan adds project backend defaults and backend-scoped command models in
the existing backend configuration file. Explicit invocation overrides win.
CLI command validation supplies a model value to the existing selector;
backend APIs need no command registry. Existing configurations and fallback
behavior remain supported. General settings consolidation, phase routing,
named tiers, and copied-skill freshness validation remain outside this plan.

## Findings and disposition

- `explicit-backend-model-defaults`: **fixed `d4e5637e8`** — backend-only flags
  retain that backend's model defaults; an explicit model overrides them.
  Architecture and step 4 agree; the second bare audit has no findings.
- `command-authority-handoff`: **fixed `448f82e0d`** — the CLI validates and
  normalizes command settings, then passes the selected backend's command
  model value into the existing selector. All four details and the affected
  step summaries agree. Repeated test inventories become compact matrices;
  the correction removes 315 net lines. The following conceptual audit is clean.
- `step1-files-coherence-23dab2d4`: **fixed `74ed3976b`** — the detail uses
  the full declared `plan_tool/cli/parser.py` citation. The final deterministic
  checks and conceptual audit have no findings.
- Copied project skill validation: **tracked #525**, separate from this plan
  and coordinated with the broader doctor spike #403.

## Closure and implementation boundary

The bare audit closes at
`20261113-024203-completeness.md` with 0/4 details. The detail-grounded audit
closes at `20261113-030242-completeness.md` with 4/4 details, no findings,
confirmed coverage, and current revision. Both reports live under
`docs/implementation-plans/plan-details/project-model-selection/reports/`.
The trajectory includes five completed snapshots with session-directed fixes.

Steps 2 and 3 retain authoring-provenance warnings after judged summary edits;
the final qualified audit covers the current plan and all current details.
Baseline tests establish existing behavior, not implementation of the proposed
feature. No production code changes or full-suite implementation claim belong
to this PR. No changelog fragment is needed because this PR ships only planning
and tracking artifacts. Backlog #254 stays open until implementation ships.

The PR requires team review and merge before a separate implementation run.
