# `plan-tool run`

## Usage

```
plan-tool run [-h] [-y] [--max-iterations N] [--iteration-budget SECONDS] [--time-budget SECONDS] [--max-stall-rounds N] [--allow-drift] [--no-auto-reconcile-on-drift] [--no-triage] [--include-info] [--no-collision-sidecar] [--iterate | --no-iterate] [--reconcile] [--step STEP] [--all] [--accept] [--max-steps N] [--commit] [--archive] [--skip-merge-check] [--switch-branch] [--mode {run,check,optimize,document,test,security,lint}] [--dry-run] [--allow-missing-parent] [--no-save] [--no-walk] [--reuse | --no-reuse] [--reuse-id STEM] [name]
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem (e.g. 1-my-feature), or filename.md. Omit (or pass a name that doesn't resolve) to pick interactively from the plans that still have open steps. |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--max-iterations` `N` | `3` | compatibility iteration count; no run loop executes. Value validation applies to ordinary and --all runs. |
| `--iteration-budget` `SECONDS` | `1800` | compatibility progress budget; run has no iteration deadline. Value validation applies to ordinary and --all runs. |
| `--time-budget` `SECONDS` | — | compatibility loop time budget; this option does not limit run execution time. Flag and PLAN_TOOL_TIME_BUDGET value validation applies to ordinary and --all runs. |
| `--max-stall-rounds` `N` | `2` | compatibility stall count; run has no iteration stall detector. Value validation applies to ordinary and --all runs. |
| `--allow-drift` | off | compatibility flag; run does not use an iteration live-edit drift guard. |
| `--no-auto-reconcile-on-drift` | on | compatibility flag; run has no iteration-triggered auto-reconcile pass. |
| `--no-triage` | on | compatibility flag; run has no iterative finding-apply triage. |
| `--include-info` | off | compatibility flag; run does not auto-apply review findings. |
| `--no-collision-sidecar` | on | compatibility flag; run has no iteration collision-sidecar pause. |
| `--iterate`, `--no-iterate` | off | no effect on run; retained for script compatibility. --reconcile rejects --iterate. Use separate reconcile-code invocations after reviewing and committing corrections. |
| `--reconcile` | off | legacy form of 'plan-tool reconcile-code' (kept working). Audit code against the plan (plan is canonical) and land code edits inline; findings whose root cause is in the plan are short-circuited with [REDIRECT] pointing at 'plan-tool detail --reconcile'. Mutually exclusive with --mode and --iterate. |
| `--step` `STEP` | — | run a specific step by id (default: current or next runnable) |
| `--all` | off | sweep every runnable step in one invocation. Loops `next runnable -> run` until the plan completes, a step exits non-zero, or --max-steps N is hit. Implies -y. Mutually exclusive with --step and review-mode --mode values; only --mode run (default) is accepted. |
| `--accept` | off | with --step N: mark a hand-fixed step done with no backend call. Requires a clean working tree apart from the plan file and its lessons log, runs the plan's test_command and the step's gate, and writes nothing unless all pass; then applies the ordinary done-and-advance and the lessons entry. With --commit, commits only the plan and lessons files. Refused unless the step is current and committed, and when nothing certifies it. Not combinable with --all, --reconcile, --dry-run, --archive, or a review --mode (--iterate warns). |
| `--max-steps` `N` | — | for --all: cap the sweep at N steps (default: unlimited, bounded by plan length). Ignored without --all. |
| `--commit` | off | after each step goes green, stage all changes (git add -A) and create one commit with subject 'plan(<slug>): step N green — <title>'. Applies to execution (--mode run) at either scope (single-step or --all); requires a clean working tree up front; off by default. No-ops (with a warning) under --dry-run or review/--reconcile modes — nothing to commit. |
| `--archive` | off | for --all or a completing --step run: when the step takes the plan to N/N done, move it to archive/ (file + plan-details/) and deregister from the manifest, then print a 'plan-tool register' undo hint. Off by default. |
| `--skip-merge-check` | off | skip the pre-run check that you are off the default branch and that the plan and every committed step's detail file are on its remote ref (origin/main). The check is on by default; a repo can turn it off with run.require_merged_plan=false in .plan-tool/config.json or PLAN_TOOL_REQUIRE_MERGED_PLAN=0. |
| `--switch-branch` | off | for branch-aware repos: on an unowned branch whose plan expects a different branch, switch to (creating if missing) the plan's expected branch on a clean tree before running; refuses on a dirty tree. No effect when branch awareness is off. |
| `--mode` `{run|check|optimize|document|test|security|lint}` | `run` | prompt mode (default: run). 'run' executes the step and advances the plan; other modes are read-only inspections that leave the plan unchanged. Review modes parse claude's `## Findings` block and print a verdict; a completed audit exits 0 even with CRITICAL findings. |
| `--dry-run` | off | render the prompt and print it; do not invoke claude |
| `--allow-missing-parent` | off | skip the pre-flight check that refuses steps whose declared files have a missing parent directory under the repo root. Use when the step legitimately creates files under a path that doesn't exist yet (e.g. a new module directory). |
| `--no-save` | off | for --reconcile: skip persisting the audit findings to plan-details/<slug>/reports/. Implies --no-walk. Has no effect otherwise. |
| `--no-walk` | off | for --reconcile: skip the interactive walk over the audit findings. The findings are still saved unless --no-save is also set. Has no effect otherwise. |
| `--reuse`, `--no-reuse` | — | for --reconcile: reuse a saved run-reconcile's findings instead of running a fresh claude audit, when the save is fresh (plan AND code fingerprints still match). Default (unset): prompt interactively, auto-accepting under --yes / non-TTY stdin. --reuse always reuses a fresh save; --no-reuse always re-audits. A stale save is never reused — it declines to a fresh audit with a staleness note. |
| `--reuse-id` `STEM` | — | pin reuse to a specific saved run-reconcile by filename stem (the bare `<ts>` or full `<ts>-run-reconcile` form); default: newest matching save for this step. An unresolved id prints a note and falls back to a fresh audit. |
