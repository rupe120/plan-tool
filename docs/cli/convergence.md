# `plan-tool convergence`

## Usage

```
plan-tool convergence [-h] [--grade {run,jira}] name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem (e.g. 1-my-feature), or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--grade` `{run|jira}` | `run` | which detail bundle to resolve the bare/detail audit stage against (default: run) — match whichever grade `completeness-audit` was run at, or the two commands can disagree about a plan audited only at jira grade |
