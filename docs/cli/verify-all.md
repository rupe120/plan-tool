# `plan-tool verify-all`

**Aliases:** `reconcile-all`, `review-all`, `verify`

## Usage

```
plan-tool verify-all [-h] [-y] [--fail-on-findings] [--mode {check,optimize,document,test,security,lint}] [--rollup] [--deep] [--max-steps N] [--dry-run] name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem (e.g. 1-my-feature), or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--fail-on-findings` | off | exit non-zero when the audit's blocking findings are present (completeness: medium+; verify-all: a [FAIL] / critical finding; validate: INVALID). Off by default; intended for CI gates that stop the pipeline on findings. |
| `--mode` `{check|optimize|document|test|security|lint}` | — | read-only review mode to sweep across every done step (dumps raw per-step reports). Mutually exclusive with --rollup; one of the two is required (the 'verify' alias defaults to --rollup). |
| `--rollup` | off | run the reconcile prompt across done steps and print one [OK]/[WARN]/[FAIL] verdict per step instead of raw reports (the former 'verify' command). Mutually exclusive with --mode. |
| `--deep` | off | with --rollup, check every acceptance-criteria bullet from each step's detail file individually (one extra claude call per bullet; opt-in due to cost) |
| `--max-steps` `N` | — | limit to the last N done steps (default: all) |
| `--dry-run` | off | render prompts and print them; do not invoke claude |
