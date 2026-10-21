# `plan-tool lessons`

## Usage

```
plan-tool lessons [-h] [-y] {consolidate} ...
```

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |

## `plan-tool lessons consolidate`

scan lessons files for duplicate/conflict findings using the lessons-equivalence primitive. Default: emit a unified diff for review. --apply rewrites with confirmation; --apply --dry-run prints the rewrite to stdout.

### Usage

```
plan-tool lessons consolidate [-h] [-y] [--apply] [--dry-run] [--plan SLUG] [--min-confidence FLOAT] [--no-resume] [--ignore-recurrence]
```

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--apply` | off | rewrite the affected files in place (after a Y/N confirmation on a TTY; silent with -y). Default: emit a unified diff to stdout and exit without touching disk. |
| `--dry-run` | off | with --apply: print the rewritten file body(ies) to stdout without touching disk (useful for piping into diff tools). Without --apply: no-op (the default mode already does not write). |
| `--plan` `SLUG` | — | scope the run to one plan's per-plan lessons.md (file at the path declared by that plan's `lessons:` frontmatter). Default: every discovered lessons file. |
| `--min-confidence` `FLOAT` | `0.6` | primitive threshold below which findings are dropped (default: 0.6). Lower to see borderline cases; raise to require higher claude confidence before a duplicate drives a drop. |
| `--no-resume` | off | force a fresh equivalence-primitive call per file, ignoring any cached payload under .plan-tool/checkpoints/lessons-equivalence/. The input hash already invalidates the cache when the lessons body changes; pass this when re-spending tokens is the explicit goal. |
| `--ignore-recurrence` | off | skip the recurrence weighting (don't read .plan-tool/lessons-warnings.jsonl). Default: findings flagged across many prior detail/review iterations sort ahead of first-time findings, annotated with recurrence=N. Pass this to see the raw primitive ordering when investigating noise patterns. |
