# `plan-tool suggest-gates`

## Usage

```
plan-tool suggest-gates [-h] [-y] [--all-steps] slug
```

## Arguments

| Argument | Description |
| --- | --- |
| `slug` | plan slug or name |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | non-interactive: print the suggested gates as a report instead of prompting; nothing is written (executable commands are never applied unvetted). |
| `--all-steps` | off | propose speculative gates from the step details even when no step is built yet (e.g. on a freshly-created plan); every not-done step becomes a valid target. Default grounds gates only on already-built (done) steps. |
