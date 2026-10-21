# `plan-tool annotate`

## Usage

```
plan-tool annotate [-h] [--output-dir OUTPUT_DIR] [--report REPORT] [--seed SEED] [--report-dir REPORT_DIR] [--seed-dir SEED_DIR] [--archive] [--iterate | --no-iterate] path-or-glob [path-or-glob ...]
```

## Arguments

| Argument | Description |
| --- | --- |
| `path-or-glob` | existing plan/notes path or glob to annotate against the current code; accepts multiple values |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--output-dir` `OUTPUT_DIR` | — | directory for the derived <name>.annotated.md / <name>.seed.md (default: beside the source file) |
| `--report` `REPORT` | — | explicit path for the annotated report (overrides the derived name + --output-dir) |
| `--seed` `SEED` | — | explicit path for the create-seed (overrides the derived name + --output-dir) |
| `--report-dir` `REPORT_DIR` | — | directory for derived <name>.annotated.md reports (default: --output-dir or beside each source file) |
| `--seed-dir` `SEED_DIR` | — | directory for derived <name>.seed.md carryover files (default: --output-dir or beside each source file) |
| `--archive` | off | move the original (and, for an N-slug.md plan file, its sibling plan-details/<slug>/ bundle) into archive/ with a notice pointing at the report (the only mutation of the source; default: leave it in place) |
| `--iterate`, `--no-iterate` | off | unsupported for annotate: annotation is currently single-pass (one classification + two renderers). Deliberately defaults OFF — diverging from the authoring family's opt-out default=True (create/detail) — because there is no convergence loop to drive. |
