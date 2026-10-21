# `plan-tool gate-status`

## Usage

```
plan-tool gate-status [-h] [--json] [--grade {run,jira}] name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan slug, filename stem, or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--json` | off | accepted for explicit JSON requests; output is always JSON |
| `--grade` `{run|jira}` | `run` | select saved results and current stage for this detail grade (default: run) |
