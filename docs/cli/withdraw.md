# `plan-tool withdraw`

## Usage

```
plan-tool withdraw [-h] [-y] --reason REASON target
```

## Arguments

| Argument | Description |
| --- | --- |
| `target` | path to the plan file (absolute or repo-relative), or a bare slug. Need not currently be registered. |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--reason` `REASON` | — | why this plan is being withdrawn — required. An archived plan with no stated reason reads as completed to the next reader. |
