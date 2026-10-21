# `plan-tool checkpoint`

## Usage

```
plan-tool checkpoint [-h] [-y] {list,show,clear} ...
```

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |

## `plan-tool checkpoint list`

list every cached checkpoint with slug, name, age, and bytes

### Usage

```
plan-tool checkpoint list [-h] [-y]
```

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |

## `plan-tool checkpoint show`

print one checkpoint's payload (metadata to stderr, payload to stdout)

### Usage

```
plan-tool checkpoint show [-h] [-y] target
```

### Arguments

| Argument | Description |
| --- | --- |
| `target` | checkpoint identifier in the form <slug>/<checkpoint>, where <checkpoint> is the per-plan name shown in the 'name' column of `plan-tool checkpoint list` (e.g. my-plan/detail-step-01) |

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |

## `plan-tool checkpoint clear`

delete cached checkpoints. Pass a <slug> to clear one plan's cache, or --all to wipe everything.

### Usage

```
plan-tool checkpoint clear [-h] [-y] [--all] [slug]
```

### Arguments

| Argument | Description |
| --- | --- |
| `slug` | plan slug whose checkpoints to clear (omit when using --all) |

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--all` | off | clear every checkpoint in the repo's checkpoints directory |
