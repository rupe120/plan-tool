# `plan-tool direct-run`

## Usage

```
plan-tool direct-run [-h] [-y] [--from DESCRIPTION | --from-existing PATH] [--output-dir OUTPUT_DIR] [--iterate | --no-iterate] [slug]
```

## Arguments

| Argument | Description |
| --- | --- |
| `slug` | canonical slug for the plan the create stage authors — lowercase, dashes, no priority prefix, no .md suffix. Optional: suggested from the seed when omitted (taken as-is under --yes). |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts across every chained stage (the completeness-apply and run stages already run non-interactive). |
| `--from` `DESCRIPTION` | — | ask claude for initial steps given this inline description |
| `--from-existing` `PATH` | — | read an existing plan or notes file and use its contents as the create seed (mutually exclusive with --from) |
| `--output-dir` `OUTPUT_DIR` | — | directory to write the new plan into (default: docs/implementation-plans/ under the repo root) |
| `--iterate`, `--no-iterate` | on | run the create stage's post-write convergence loop until findings stabilize (default ON; pass --no-iterate for a one-shot write) |
