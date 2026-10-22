# `plan-tool reconcile-plan-walk`

**Aliases:** `reconcile-walk`, `review-walk`

## Usage

```
plan-tool reconcile-plan-walk [-h] [-y] [--id STEM] [--rewalk] [--include-info] [--apply-structural] [--merge] [--reground] [--reground-rebaseline] name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem (e.g. 1-my-feature), or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--id` `STEM` | — | load exactly one final saved reconcile by a listed filename stem or basename in the selected plan's reports directory (e.g. 20260505-123456); path-bearing, missing, ambiguous, unreadable, and non-final ids exit 2 without fallback; default: newest eligible final |
| `--rewalk` | off | re-prompt items that already have annotations (default: skip already-annotated items) |
| `--include-info` | off | walk info-level findings too (default: skip them — the low-confidence heuristic hints that usually land no edit on apply). They remain in the saved reconcile either way. |
| `--apply-structural` | off | let a recognized structural-directive finding actuate its bridge on apply instead of only recommending — a pairwise `merge` directive folds steps via detail.merge_bridge, a re-ground directive marks already-built steps done via reground.reground_bridge (both ride a `granularity-merge` finding, split by directive kind). Recommend-only without it. A merge directive stays visible under the default info hide, so --apply-structural alone reaches it; the re-ground directive keeps its --include-info requirement. Each bridge owns its own safety checks and TTY confirm; a blanket apply-all never auto-confirms a fold, an applied merge halts the walk (its renumber invalidates later saved ids), and a stale saved directive is blocked before any mutation. |
| `--merge` | off | enable only the merge bridge on apply (the granular counterpart to --apply-structural, which enables both bridges): a pairwise `merge` directive folds steps via detail.merge_bridge while a re-ground directive stays recommend-only. A blanket apply-all still forces recommend-only. See --apply-structural to enable both remedies at once. |
| `--reground` | off | enable only the re-ground bridge on apply (the granular counterpart to --apply-structural, which enables both bridges): a re-ground directive marks already-built steps done via reground.reground_bridge while a `merge` directive stays recommend-only. Still needs --include-info to surface the info-level re-ground finding at all, and a blanket apply-all still forces recommend-only. See --apply-structural to enable both remedies at once. |
| `--reground-rebaseline` | off | disposition selector (not a visibility or enable toggle): on apply, make an actuated re-ground ALSO write a `create --from-existing` re-baseline seed under docs/implementation-plans/plan-seeds/ for the flagged already-built steps, in addition to marking them done. The seed supersedes the plan's remaining scope, so re-create from it and retire this plan. Still needs the re-ground enabled (--reground or --apply-structural) and surfaced (--include-info); on its own it does nothing observable. Without it, an actuated re-ground only marks the steps done. |
