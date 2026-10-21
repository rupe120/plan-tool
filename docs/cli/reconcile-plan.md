# `plan-tool reconcile-plan`

**Aliases:** `reconcile`, `review`

## Usage

```
plan-tool reconcile-plan [-h] [-y] [--step STEP | --all] [--dry-run] [--refresh] [--no-heuristic] [--allow-missing-parent | --no-allow-missing-parent] [--no-save] [--no-walk] [--include-info] [--apply-structural] [--merge] [--reground] [--reground-rebaseline] [--lessons | --no-lessons] [--reuse | --no-reuse] [--reuse-id STEM] name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem (e.g. 1-my-feature), or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--step` `STEP` | — | reconcile one step by id (default: every step in the plan) |
| `--all` | off | reconcile every step in the plan (the explicit default scope) |
| `--dry-run` | off | render the claude prompt and print it; do not invoke |
| `--refresh` | off | re-ground the plan against the current code instead of running a full audit. Gates the plan's grounding fingerprint against the code with NO claude call; on no drift exits fast (nothing to do). On drift, runs a reconcile scoped to exactly the changed files and saves the findings for 'reconcile-plan-walk'; it re-stamps the grounding sidecar ONLY when that reconcile is clean (pending findings leave the drift gate open until you apply them, so a re-run never masks the staleness). Contrast a plain audit (always spends claude) and 'create --reprocess' (fills placeholder text, no code involvement). |
| `--no-heuristic` | off | skip the symbol-token 'looks already done' heuristic. File-existence, dep, and path-style checks still run; Claude's semantic review still fires. Use for plans whose step titles share tokens with existing code structurally (e.g., refactor plans). |
| `--allow-missing-parent`, `--no-allow-missing-parent` | on | treat declared files whose parent directory is missing under the repo root as expected creators (NEW) instead of MISSING_PARENT. Silences the per-step warning and the plan-wide path-style hint; NEW-on-DONE, deps, heuristic, and the Claude review still fire. Default ON for review -- pass --no-allow-missing-parent to flag steps whose parent directories don't exist yet. |
| `--no-save` | off | skip persisting the reconcile under <plan-dir>/plan-details/<slug>/reports/. By default each run is saved so 'plan-tool reconcile-plan-walk' can step through recommendations later. Pass this for one-off runs that shouldn't clutter the history. |
| `--no-walk` | off | skip the interactive walk after the report. By default, when stdin is a TTY and the review produced recommendations, plan-tool steps through them with (a)pply/(s)kip/(f)eedback/(q)uit prompts. Pass this for one-shot reviews or when piping output. Ordinary CI and non-TTY contexts skip the walk automatically; explicit PLAN_TOOL_HUMAN_IO=remote instead permits a restricted non-TTY (s)kip/(q)uit walk. |
| `--include-info` | off | walk info-level findings too. By default the interactive walk skips them — these are the low-confidence heuristic hints that, on apply, dispatch a reconcile and usually land no edit (pure token spend). They are still saved to the reconcile JSON; pass this (or 'reconcile-plan-walk --include-info') to step through them. |
| `--apply-structural` | off | let a recognized structural-directive finding actuate its bridge on apply instead of only recommending — a pairwise `merge` directive folds steps via detail.merge_bridge, a re-ground directive marks already-built steps done via reground.reground_bridge (both ride a `granularity-merge` finding, split by directive kind). Recommend-only without it. A merge directive stays visible under the default info hide, so --apply-structural alone reaches it; the re-ground directive keeps its --include-info requirement. Each bridge owns its own safety checks and TTY confirm; a blanket apply-all never auto-confirms a fold, an applied merge halts the walk (its renumber invalidates later saved ids), and a stale saved directive is blocked before any mutation. |
| `--merge` | off | enable only the merge bridge on apply (the granular counterpart to --apply-structural, which enables both bridges): a pairwise `merge` directive folds steps via detail.merge_bridge while a re-ground directive stays recommend-only. A blanket apply-all still forces recommend-only. See --apply-structural to enable both remedies at once. |
| `--reground` | off | enable only the re-ground bridge on apply (the granular counterpart to --apply-structural, which enables both bridges): a re-ground directive marks already-built steps done via reground.reground_bridge while a `merge` directive stays recommend-only. Still needs --include-info to surface the info-level re-ground finding at all, and a blanket apply-all still forces recommend-only. See --apply-structural to enable both remedies at once. |
| `--reground-rebaseline` | off | disposition selector (not a visibility or enable toggle): on apply, make an actuated re-ground ALSO write a `create --from-existing` re-baseline seed under plan-seeds/ for the flagged already-built steps, in addition to marking them done. The seed supersedes the plan's remaining scope, so re-create from it and retire this plan. Still needs the re-ground enabled (--reground or --apply-structural) and surfaced (--include-info); on its own it does nothing observable. Without it, an actuated re-ground only marks the steps done. |
| `--lessons`, `--no-lessons` | off | capture lessons learned (default: off). When on, after the review produces recommendations, a second claude call distills new general lessons into ~/.plan-tool/lessons/general.md and project-specific lessons into <repo_root>/.plan-tool/lessons/project.md. Off by default because it costs an extra claude call; pass --lessons to opt in. --no-lessons is the explicit form of the default. |
| `--reuse`, `--no-reuse` | — | reuse a saved review's findings instead of running a fresh claude audit, when the save is eligible and fresh (plan AND code fingerprints still match). Eligibility is read from the loaded payload, not the filename: only an ordinary-final reconcile-plan review qualifies, so the newest-first lookup skips unreadable sidecars, pre-apply audit checkpoints, unknown-role payloads, and other kinds (completeness / reconcile) rather than walking their findings. Default (unset): prompt interactively, auto-accepting under --yes / non-TTY stdin — ordinary non-TTY reuse prints the saved findings and skips the per-finding walk, while explicit PLAN_TOOL_HUMAN_IO=remote permits a restricted (s)kip/(q)uit walk for promptable findings. --reuse always reuses an eligible fresh save; --no-reuse always re-audits. A stale save is never reused — it declines to a fresh review with a staleness note. |
| `--reuse-id` `STEM` | — | pin reuse to a specific saved review by filename stem (the bare `<ts>` form); default: the newest eligible save for this plan. The pin is exact: an unmatched stem, an unreadable file, and an ineligible payload (a checkpoint, an unknown role, or another kind) each print their own note and fall back to a fresh review — never to an older save. |
