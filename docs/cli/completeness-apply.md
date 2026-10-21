# `plan-tool completeness-apply`

## Usage

```
plan-tool completeness-apply [-h] [-y] [--id STEM] [--anchor SLUG] [--rewalk] [--include-info] [--apply-structural] [--commit] [--jobs N] name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem (e.g. 1-my-feature), or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--id` `STEM` | — | load a specific saved completeness audit by filename stem (e.g. 20260505-123456-completeness); default: newest `-completeness.json` for this plan |
| `--anchor` `SLUG` | — | address one gap by its `[anchor-slug]` (from the report). Repeatable to target several gaps. Default: walk all gaps. |
| `--rewalk` | off | re-prompt items that already have annotations (default: skip already-annotated items) |
| `--include-info` | off | walk info-level gaps too (default: skip them) |
| `--apply-structural` | off | opt the serial walk into *applying* a medium granularity-split step split (via escalate_to_split) on a safe plan with an interactive confirm; without it (or under -y, or --jobs > 1) the split finding is recommend-only. Independent of --include-info: the medium split is walked regardless of it. |
| `--commit` | off | after applying gap-closing edits, stage all changes (git add -A) and create one commit with subject 'plan(<slug>): completeness — applied N gap(s)'. Requires a clean working tree up front; off by default; only commits when a gap was applied. |
| `--jobs` `N` | `1` | apply up to N gaps concurrently in isolated worktrees (explicit integer >= 1; default 1 = the interactive per-gap walk; there is no 0/auto mode). N>1 is NON-INTERACTIVE and requires -y (it bypasses the per-gap confirm), a clean working tree (isolation is off HEAD), and applies both conceptual sources (including ambiguity under correctness) correctness-first. A single --anchor gap degrades to serial (nothing to parallelize). |
