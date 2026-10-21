# `plan-tool data-contract-apply`

Interactively apply DATA_CONTRACT.md drift recommendations saved by completeness-audit.

## Usage

```
plan-tool data-contract-apply [-h] [--id ID] [--anchor ANCHOR] [--rewalk] [--include-info] name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name/slug |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--id` `ID` | — | saved completeness audit id/stem to replay |
| `--anchor` `ANCHOR` | — | walk only a recommendation id or anchor (repeatable) |
| `--rewalk` | off | revisit findings already annotated applied/skipped |
| `--include-info` | off | include info-level recommendations in the walk |
