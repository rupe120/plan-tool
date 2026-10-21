# `plan-tool runs`

## Usage

```
plan-tool runs [-h] [-y] {list,show,diff,profile,clear} ...
```

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |

## `plan-tool runs list`

list every run log with slug, run_id, command, duration, tokens

### Usage

```
plan-tool runs list [-h] [-y] [--slug SLUG]
```

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--slug` `SLUG` | — | limit the listing to a single plan slug |

## `plan-tool runs show`

print one run log's events to stdout (metadata to stderr, event lines to stdout)

### Usage

```
plan-tool runs show [-h] [-y] target
```

### Arguments

| Argument | Description |
| --- | --- |
| `target` | run identifier in the form <slug>/<run_id> (e.g. my-plan/2026-05-14T12-34-56-9f3a1c) |

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |

## `plan-tool runs diff`

render a per-phase wall-clock + token-count delta table for two runs, flagging only-in-A / only-in-B phases

### Usage

```
plan-tool runs diff [-h] [-y] a b
```

### Arguments

| Argument | Description |
| --- | --- |
| `a` | first run in the form <slug>/<run_id> |
| `b` | second run in the form <slug>/<run_id> |

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |

## `plan-tool runs profile`

aggregate claude_call_end events into a latency / cost report (by mode, step, or run)

### Usage

```
plan-tool runs profile [-h] [-y] [--slug SLUG] [--mode MODE] [--since DURATION] [--by {mode,step,run}] [--top N] [--json] [--include-incomplete]
```

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--slug` `SLUG` | — | limit profiling to a single plan slug |
| `--mode` `MODE` | — | filter to claude calls whose containing phase_start mode matches (e.g. run, check, reconcile, optimize) |
| `--since` `DURATION` | — | include only runs whose run_start ts is newer than DURATION (e.g. 30d, 48h, 90m, or seconds as integer) |
| `--by` `{mode|step|run}` | `mode` | aggregation key (default: mode) |
| `--top` `N` | — | show only the top N groups by total wall-clock (after sorting; useful with --by step or --by run) |
| `--json` | off | emit JSON instead of the table renderer |
| `--include-incomplete` | off | surface unmatched claude_call_start events (no end observed) in the incomplete column; they remain excluded from p50/p95 latency stats either way |

## `plan-tool runs clear`

delete run logs. Pass --all, a <slug>, or --older-than <DURATION>. Combine slug + --older-than to evict by age under one slug.

### Usage

```
plan-tool runs clear [-h] [-y] [--all] [--older-than DURATION] [slug]
```

### Arguments

| Argument | Description |
| --- | --- |
| `slug` | plan slug whose runs to clear (omit when using --all or --older-than) |

### Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--all` | off | clear every run log under the runs root |
| `--older-than` `DURATION` | — | evict only runs whose run_start ts is older than DURATION (e.g. 30d, 48h, 90m, or seconds as integer; 30d is the recommended default) |
