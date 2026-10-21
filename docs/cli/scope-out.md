# `plan-tool scope-out`

## Usage

```
plan-tool scope-out [-h] [-y] --step STEP [--through M] [--apply] name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem (e.g. 1-my-feature), or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | skip the interactive carve confirmation (relevant only with --apply): the deliberate second opt-in that may mutate a plan without a TTY. Useful for scripted/unattended runs. |
| `--step` `STEP` | — | step id to carve out of the plan (N; the region start with --through) |
| `--through` `M` | — | carve the inclusive N..M region (from --step N) in one carve, writing one forward-seed for the whole region; omit for a single-step carve. M must be >= N. |
| `--apply` | off | opt in to mutating the plan: write the forward-seed and narrow the plan (default: recommend only). Requires an interactive confirm unless paired with -y/--yes. |
