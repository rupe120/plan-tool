# plan-tool CLI reference

Per-subcommand reference, generated from the argparse parser by
`python -m plan_tool.cli_reference --write`. Do not edit directly — the
files here are regenerated and drift-checked in CI. For narrative
walkthroughs see the user guides in `docs/` (e.g. `RUNBOOK.md`).

| Command | Summary |
| --- | --- |
| [`list`](list.md) | list plan-tool-compatible plans |
| [`status`](status.md) | show step-by-step status for a plan |
| [`init`](init.md) | capture one confirmed project intent in a tracked profile |
| [`validate`](validate.md) | validate a plan's frontmatter |
| [`register`](register.md) | adopt an on-disk plan file into the structured-plans manifest (path or slug accepted) |
| [`deregister`](deregister.md) | remove a plan from the structured-plans manifest (path or slug accepted; leaves the file on disk) |
| [`sweep`](sweep.md) | archive completed plans (top-level status: completed AND all steps done), report on partially implemented plans, offer to prune manifest entries whose files no longer exist, and report unregistered plan files found beside registered plans |
| [`withdraw`](withdraw.md) | archive a plan being abandoned, as distinct from one that completed (sweep) or was superseded (create): moves the file to archive/<stem>.withdrawn.md, moves its plan-details alongside it, prepends a dated reason header, and deregisters it |
| [`checkpoint`](checkpoint.md) | inspect / manage on-disk resume checkpoints under <repo>/.plan-tool/checkpoints/. Subactions: list / show / clear. |
| [`runs`](runs.md) | inspect / manage on-disk run logs under <repo>/.plan-tool/runs/. Subactions: list / show / diff / profile / clear. |
| [`lessons`](lessons.md) | maintenance verbs over plan-tool's lessons files (general.md / project.md / per-plan lessons.md). Subactions: consolidate. |
| [`roadmap`](roadmap.md) | stage a concept brief into gated architecture artifacts under docs/implementation-plans/roadmaps/<slug>/ (one rung above create); use --apply to promote draft seeds into plan-seeds/ or --refresh-seeds to regenerate invalidated seeds |
| [`create`](create.md) | interactively author a new plan |
| [`reconcile-plan`](reconcile-plan.md) | reconcile the plan against the current codebase (edits the plan) |
| [`reconcile-code`](reconcile-code.md) | audit the code against the plan (plan is canonical) and land code edits inline; plan-rooted findings redirect to 'detail --reconcile' (legacy form: 'run --reconcile') |
| [`reconcile-plan-walk`](reconcile-plan-walk.md) | walk and apply the findings from a saved reconcile (any kind: reconcile-plan / reconcile-code / detail --reconcile), no claude call; loads the newest eligible final save for <name> by default |
| [`verify-all`](verify-all.md) | audit every done step (read-only): --mode sweeps a review mode and dumps reports; --rollup prints a per-step pass/warn/fail verdict |
| [`completeness-audit`](completeness-audit.md) | conceptual audit of a plan: deterministic authoring-gap checks (body sections, detail files, lessons) plus a claude call judging whether the plan's own concepts are correct, complete, and unambiguous (grounded in the per-step detail bundle where present + code at HEAD; a bare plan with no detail yet is audited at the plan/concept level). Conceptual gaps are reported for a session-directed edit, not applied by a tool command. A completed audit exits 0; findings are in the report (and --json exposes stage-aware has_blocking_findings, conceptual_bar_blocking_ids, and audit_incomplete), or use --fail-on-findings to gate CI on bar-aware blockers and incomplete audit samples. With --iterate, applies the deterministic well-formedness findings and converges on them; conceptual ambiguity is reported with correctness, and both it and completeness gaps are persisted unapplied for a session-directed edit (#85). |
| [`completeness-apply`](completeness-apply.md) | DEPRECATED, going away (BACKLOG #376) — walking findings one gap at a time is slow and obscures the convergence signal; read the saved report and make a session-directed edit to the plan/detail files instead. walk the conceptual gaps from the most recent saved `completeness-audit` and apply gap-closing edits via claude, one finding at a time, AND deterministically clear files-coherence drift (no claude: add cited real-file paths to the step's allowed_mentions). Walks BOTH conceptual sources — plan-correctness (including material ambiguity) first, then plan-completeness — which the audit persists unapplied (read-only-audit split, #85). Pairs with completeness-audit; does NOT re-run the audit. A current saved arm-clustering advisory prints once as a non-blocking keep-or-carve prompt before serial work or parallel worker provisioning; a stale advisory is hidden without changing the saved walk. Always interactive: one per-gap confirm so you review each conceptual issue in context (no blanket auto-apply). On a bare plan only plan-correctness gaps are walked; other saved sources are reported as withheld until detail exists. The deterministic files-coherence fix runs only when a complete detail bundle exists. On a non-interactive stdin the walk is skipped and the gaps are reported. `--anchor <slug>` (repeatable) restricts to specific gaps. |
| [`data-contract-apply`](data-contract-apply.md) | walk saved DATA_CONTRACT.md drift findings from a completeness audit |
| [`gate-status`](gate-status.md) | report saved audit gate verdicts as versioned JSON |
| [`convergence`](convergence.md) | diagnose whether a plan's audit/apply loop is converging |
| [`telemetry`](telemetry.md) | analyze recorded heuristic decisions and their outcomes |
| [`decide`](decide.md) | record an explicit plan decomposition decision |
| [`jira`](jira.md) | emit copy-paste-ready JIRA story titles and descriptions; `jira config` opens the configuration wizard |
| [`detail`](detail.md) | draft developer-actionable per-step detail markdown files |
| [`run`](run.md) | execute a step via claude subprocess |
| [`direct-jira`](direct-jira.md) | DEPRECATED, going away (BACKLOG #376) — exists only to chain completeness-apply's gap-by-gap apply, retiring for the same reason (slow, and obscures the convergence signal); drive create / detail / jira as separate, hand-reviewed steps instead. chain create → detail → completeness-apply → jira in one process and publish paired Jira stories plus a developer handoff (small plans only) |
| [`direct-run`](direct-run.md) | DEPRECATED, going away (BACKLOG #376) — exists only to chain completeness-apply's gap-by-gap apply, retiring for the same reason (slow, and obscures the convergence signal); drive create / detail / run / reconcile-code as separate, hand-reviewed steps instead. chain create → detail → completeness-apply → run → reconcile-code in one process (small plans only) |
| [`suggest-gates`](suggest-gates.md) | propose gate: commands for a plan's remaining steps, grounded in its already-built (done) steps |
| [`bench`](bench.md) | run the backend-quality benchmark matrix and report raw results. Subactions: run / report. |
| [`annotate`](annotate.md) | judge an existing plan/notes file against the current code and emit two artifacts — an additive `<name>.annotated.md` (verbatim original + per-section IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED status) and a carryover `<name>.seed.md` for `create --from-existing`; read-only except the opt-in `--archive`. |
| [`attach-branch`](attach-branch.md) | attach a registered plan to an ad-hoc branch (untracked local git-config override; refuses unless branch awareness is enabled; re-homes the plan onto its own branch on a convention-name collision) |
| [`detach-branch`](detach-branch.md) | clear a registered plan's ad-hoc branch override (refuses unless branch awareness is enabled; leaves the branch on disk in place) |
| [`scope-out`](scope-out.md) | carve an over-packed step out of a plan into a create --from-existing seed (recommend-only; --apply to mutate) |
| [`scope-review`](scope-review.md) | review and sign off scoped concept decisions, then synchronize them to the plan |
| [`split-criteria`](split-criteria.md) | show the split-criteria legend, or (with a plan) why that plan is shaped the way it is (read-only; no claude; criteria exit 0) |
| [`worktree`](worktree.md) | provision and inspect isolated per-plan workspaces (worktrees / clones) |
| [`root`](root.md) | report the repo root plan-tool discovers from here |
| [`split`](split.md) | split a step into named sub-steps on demand, author their detail files, then loop on the completeness audit |
| [`merge`](merge.md) | merge a contiguous set of steps into one on demand, combine + re-author their detail file, then loop on the completeness audit |
| [`install-skill`](install-skill.md) | install the bundled Claude Code / Codex / Cursor skill into a project (opt-in; the CLI is standalone and needs no skill) |
