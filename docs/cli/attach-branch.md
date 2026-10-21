# `plan-tool attach-branch`

## Usage

```
plan-tool attach-branch [-h] [-y] plan branch
```

## Arguments

| Argument | Description |
| --- | --- |
| `plan` | path or slug of a registered plan |
| `branch` | branch to attach (arbitrary; stored as an untracked local-git-config override) |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
