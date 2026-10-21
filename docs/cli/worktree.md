# `plan-tool worktree`

## Usage

```
plan-tool worktree [-h] {add,list,remove,prune} ...
```

## `plan-tool worktree add`

provision (or reuse) the plan's workspace on its branch

### Usage

```
plan-tool worktree add [-h] [--branch BRANCH] [--clone] name
```

### Arguments

| Argument | Description |
| --- | --- |
| `name` | path or slug of a registered plan |

### Options

| Option | Default | Description |
| --- | --- | --- |
| `--branch` `BRANCH` | — | branch to provision the workspace on (overrides the derived name: derive_branch when branch-awareness is on, else the slug) |
| `--clone` | off | provision a standalone clone instead of a git worktree (an independent repo dir whose .git is a directory) |

## `plan-tool worktree list`

report every plan's workspace: kind, branch, path, dirty state

### Usage

```
plan-tool worktree list [-h]
```

## `plan-tool worktree remove`

delete a plan's workspace (clean-tree gated; --force to override)

### Usage

```
plan-tool worktree remove [-h] [-y] [--force] name
```

### Arguments

| Argument | Description |
| --- | --- |
| `name` | path or slug of a registered plan |

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept the confirmation prompt (for scripted/unattended runs) |
| `--force` | off | delete even a dirty worktree (bypasses the clean-tree gate) |

## `plan-tool worktree prune`

sweep dead (deregistered/path-gone) worktrees; dirty ones are surfaced, not deleted

### Usage

```
plan-tool worktree prune [-h] [-y]
```

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept the confirmation prompt (for scripted/unattended runs) |
