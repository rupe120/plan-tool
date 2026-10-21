# `plan-tool validate`

## Usage

```
plan-tool validate [-h] [-y] [--fail-on-findings] name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem (e.g. 1-my-feature), or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--fail-on-findings` | off | exit non-zero when the audit's blocking findings are present (completeness: medium+; verify-all: a [FAIL] / critical finding; validate: INVALID — except an unsupported declared format_version, for which validate always exits 1 regardless of this flag). Off by default; intended for CI gates that stop the pipeline on findings. |
