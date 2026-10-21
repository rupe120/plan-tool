# `plan-tool list`

## Usage

```
plan-tool list [-h] [-y] [--status] [--report-dir REPORT_DIR] [--format {text,md}]
```

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--status` | off | roll up cached annotate reports for active plans, including per-status counts and grounding metadata |
| `--report-dir` `REPORT_DIR` | — | additional directory of cached *.annotated.md reports to include with list --status; may be repeated |
| `--format` `{text|md}` | `text` | output format for list --status (default: text) |
