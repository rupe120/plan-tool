# `plan-tool bench`

## Usage

```
plan-tool bench [-h] [-y] {run,report} ...
```

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |

## `plan-tool bench run`

run the task-family × backend × trial matrix over the corpus

### Usage

```
plan-tool bench run [-h] [-y] [--backends BACKENDS] [--families FAMILIES] [--trials N] [--timeout SECONDS] [--no-resume] [--stamp STAMP] [--corpus-root CORPUS_ROOT]
```

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--backends` `BACKENDS` | — | comma-separated backend names to iterate (default: all registered) |
| `--families` `FAMILIES` | — | comma-separated family names to iterate (default: all — proposal, detail, reconcile, implementation, apply) |
| `--trials` `N` | `3` | trials per cell (default: 3) |
| `--timeout` `SECONDS` | `600` | per-cell wall-clock cap; a slow cell records failure_kind=timeout and the matrix continues (default: 600) |
| `--no-resume` | on | re-run completed cells instead of skipping them (default: resume, skipping cells already present for the stamp) |
| `--stamp` `STAMP` | — | run stamp / directory name (default: a fresh timestamp). Reuse to resume. |
| `--corpus-root` `CORPUS_ROOT` | — | override the corpus root (default: <repo>/benchmarks/corpus) |

## `plan-tool bench report`

render one bench run's scored per-(family, backend) report

### Usage

```
plan-tool bench report [-h] [-y] --stamp STAMP [--format {markdown,json}] [--write-recommendations] [--corpus-root CORPUS_ROOT]
```

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--stamp` `STAMP` | — | which run stamp (directory under .plan-tool/bench/runs/) to report |
| `--format` `{markdown|json}` | `markdown` | output format for the report (default: markdown) |
| `--write-recommendations` | off | render docs/evidence/backend-recommendations.md from this run and print its path (a regenerable artifact, never directly edited) |
| `--corpus-root` `CORPUS_ROOT` | — | override the corpus root used for on-the-fly scoring + the staleness drift recompute (default: <repo>/benchmarks/corpus) |
