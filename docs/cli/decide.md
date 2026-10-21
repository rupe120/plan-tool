# `plan-tool decide`

## Usage

```
plan-tool decide [-h] --outcome {single,split,scope-out,reframe,withdraw,defer} --anchor ANCHOR --rationale RATIONALE name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem, or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--outcome` `{single|split|scope-out|reframe|withdraw|defer}` | — | the explicit decomposition outcome to record |
| `--anchor` `ANCHOR` | — | decision target: plan or step:<existing step id> |
| `--rationale` `RATIONALE` | — | non-empty reason for the explicit decision |
