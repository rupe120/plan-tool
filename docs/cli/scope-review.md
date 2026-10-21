# `plan-tool scope-review`

Review and sign off an explicit concept scope, then synchronize accepted decisions to the concept record and plan Markdown. Exit 3 means conflict; exit 4 means invalid state.

## Usage

```
plan-tool scope-review [-h] --concept CONCEPT_ID --decision CONCEPT_ID=DECISION name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem, or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--concept` `CONCEPT_ID` | — | concept ID in the exact review scope (repeat for a grouped scope) |
| `--decision` `CONCEPT_ID=DECISION` | — | scoped decision: include, defer, or wont_do (repeat once per concept) |
