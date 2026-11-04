# Completeness apply retirement pickup

The existing #376 plan has six authored details and confirmed bare and
detail-grounded audit coverage. The next action is scope review before
implementation. The branch is `plan/completeness-apply-retirement-refresh`.
No execution is authorized by the pickup handoff. #369 remains independent
and unchanged.

## Grounding and site inventory

Defect class: the parked retirement plan carries stale owners and overbroad
authority claims that conflict with #376's explicit exclusions.

The 2026-11-04 identifier search uses `cmd_completeness_apply`, `apply_finding(`,
`completeness-apply`, `direct-run`, `direct-jira`, and their underscore forms.
The vocabulary search uses conceptual application, unattended, parallel replay,
and blind apply across production code, integrations, and live documentation.

| Sites | Disposition and reason |
| --- | --- |
| `cli/completeness_cmd.py`, apply-only helpers in `cli/completeness_phases.py`, `cli/completeness_apply_parallel.py` | Retire command-exclusive application machinery. |
| `cli/direct_cmd.py` | Retire both command chains; these are the external callers of `cmd_completeness_apply`. |
| `cli/app.py`, `cli/parser.py`, `cli/__init__.py`, capability catalog and generated CLI pages/help | Remove retired registrations, exports, locks, and references. |
| `completeness_report.py`, `cli/authoring.py`, completeness output | Preserve conceptual hand-edit guidance; replace surviving retired-command remedies. |
| `create.py`, `detail.py`, deterministic iterate in `cli/completeness_phases.py` | Preserve repair authority; excluded by #376. |
| `cli/review_actions.py` and the shared `launcher.py:apply_finding` | Preserve generic review/reconcile authority; #369 owns further inventory. |
| `bench.py:_run_apply` | Preserve isolated benchmark fixtures; this is not a hidden completeness-command continuation. |
| Shared review, convergence, backend, error, and commit helpers | Remove only retired-command branches; preserve shared contracts and legacy readers. |
| `CLAUDE.md`, shared directives, Claude/Codex/Cursor skills | Rewrite live retired-command instructions in execution step 4; CLAUDE rule changes require architect-tier PR review. |
| Current command/use-case/demo guides, glossary, architecture, gates, README, contributing, testing, runbook, Jira/data contracts | Sweep live instructions in execution steps 3–5. Use lowercase `docs/reference/commands.md`, `docs/how-to/use-cases.md`, and `docs/demos/roadmap-demo.md`. |
| Historical plans, archived seed, evidence, saved reports, sidecars, run logs | Retain as provenance and compatibility data; no vocabulary migration. |
| Unrelated unattended roadmap, scope-out, reground, worktree, lessons, and rate-limit behavior | Retain; vocabulary overlap does not put these in scope. |

The seed resolves to `plan-seeds/archive/completeness-apply-retirement.replaced.md`;
its archived do-not-edit instruction stays intact. The existing plan is the live
scope owner with BACKLOG #376; no replacement seed or competing plan is needed.

## Review evidence

2026-11-04 command:
`uv run plan-tool --backend codex --model gpt-6.1-sol reconcile-plan completeness-apply-retirement --all --no-walk -y < /dev/null`.
It completes with report
`docs/implementation-plans/plan-details/completeness-apply-retirement/reports/20261104-130427.json`.
The semantic review identifies obsolete step-5 paths, incorrect #367 ownership,
and removed Jira-grade wording. Its heuristic already-built suggestions are
token matches, contradicted by the semantic review and live command definitions;
no step status changes follow from them.

The bounded correction aligns intent and acceptance criteria with the preserved
caller exclusions, corrects the seed/backlog/doc paths, and adds Cursor guidance
and the glossary to the existing sweep. The property is that retiring three
commands cannot silently widen into retiring unrelated application authorities.
No production code changes accompany this correction.

## Bare gate

2026-11-04 command:
`uv run plan-tool --backend codex --model gpt-6.1-sol completeness-audit completeness-apply-retirement --iterate --commit --audit-passes 1 -y < /dev/null`.
The final report is `reports/20261104-130709-completeness.md` under the plan's
detail directory: 0/6 detailed, zero conceptual correctness/completeness findings,
confirmed coverage, current revision, and advisory-only result. The conceptual
call is fresh, not reused. Bare-stage completeness application remains withheld;
there are no findings on that axis to carry into detail. The sole heuristic
`plan-claim-vs-delivery-caca4275` names `apply_finding`, which the plan expressly
preserves rather than delivers; it requires no plan expansion. No correction
loop is necessary and unchanged-plan resampling serves no purpose. Detail may
proceed; this does not certify the unauthored detail bundle.

## Detail gate and review scope

2026-11-04 authoring command:
`uv run plan-tool --backend codex --model gpt-6.1-sol detail completeness-apply-retirement --commit -y < /dev/null`.
All six details are authored in one-shot mode and committed per step. The
automatic conceptual tail saves `reports/20261104-132734-completeness.md`:
zero correctness/completeness findings, confirmed coverage, current revision,
detail stage. Deterministic checks also report zero findings.

The required iterative gate uses the fresh conceptual evidence rather than
resampling unchanged text:
`uv run plan-tool --backend codex --model gpt-6.1-sol completeness-audit completeness-apply-retirement --iterate --commit --audit-passes 1 --reuse-audit -y < /dev/null`.
The final report is `reports/20261104-140106-completeness.md`: 6/6 detailed,
zero open findings, confirmed coverage, current revision, advisory-only result.
Conceptual-call reuse is explicit; no edits or applies occur. The same
non-blocking claim-vs-delivery heuristic remains, with the bare-gate disposition
above. No three-snapshot remediation trajectory is needed: there is no
conceptual correction loop to assess.

| Execution step | Scope for review |
| --- | --- |
| 1 | Retain hand-edit guidance and replace remaining retired-command remedies. |
| 2 | Remove both direct command chains and their exclusive wiring. |
| 3 | Remove completeness-apply and exclusive serial/parallel machinery; preserve shared behavior and readers. |
| 4 | Align shared directives and all three backend skills; obtain architect-tier review for CLAUDE rule changes. |
| 5 | Sweep live reference/workflow/demo guidance; retain historical artifacts. |
| 6 | Remove #376 only on shipment, trim obsolete backlog requests, file the two bounded follow-ups, preserve #369 exactly. |

The details keep generic review/reconcile authority, benchmark fixtures,
deterministic repair, schemas, blocking predicates, and exit codes outside the
removal. No production implementation or runtime tests accompany this planning
work. Implementation requires the scope-review boundary in the source pickup
handoff; once authorized, follow the plan PR and normal execution/reconcile/review
gates rather than running immediately from a tool's printed next-step suggestion.
