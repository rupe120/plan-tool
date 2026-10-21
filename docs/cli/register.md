# `plan-tool register`

## Usage

```
plan-tool register [-h] [-y] target
```

## Arguments

| Argument | Description |
| --- | --- |
| `target` | path to the plan file (absolute or repo-relative), or a bare slug to look up under directories that already host registered plans |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
