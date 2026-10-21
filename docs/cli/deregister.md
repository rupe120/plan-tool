# `plan-tool deregister`

## Usage

```
plan-tool deregister [-h] [-y] target
```

## Arguments

| Argument | Description |
| --- | --- |
| `target` | path to the plan file (absolute or repo-relative), or the slug of a registered plan. The file need not exist — stale entries pointing at deleted files can be pruned this way. |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
