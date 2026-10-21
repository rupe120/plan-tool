# `plan-tool reconcile-code`

## Usage

```
plan-tool reconcile-code [-h] [-y] [--step STEP | --all] [--dry-run] [--allow-missing-parent] [--no-save] [--no-walk] [--reuse | --no-reuse] [--reuse-id STEM] name
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name — slug, filename stem (e.g. 1-my-feature), or filename.md |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--step` `STEP` | — | reconcile a specific step by id (default: current or next runnable) |
| `--all` | off | reconcile every step in plan order (mutually exclusive with --step) |
| `--dry-run` | off | render the prompt and print it; do not invoke claude |
| `--allow-missing-parent` | off | skip the pre-flight check that refuses steps whose declared files have a missing parent directory under the repo root. |
| `--no-save` | off | skip persisting the audit findings to plan-details/<slug>/reports/. Implies --no-walk. |
| `--no-walk` | off | skip the interactive walk over the audit findings. The findings are still saved unless --no-save is also set. |
| `--reuse`, `--no-reuse` | — | reuse a saved run-reconcile's findings instead of running a fresh claude audit, when the save is fresh (plan AND code fingerprints still match). Default (unset): prompt interactively, auto-accepting under --yes / non-TTY stdin. --reuse always reuses a fresh save; --no-reuse always re-audits. A stale save is never reused — it declines to a fresh audit with a staleness note. |
| `--reuse-id` `STEM` | — | pin reuse to a specific saved run-reconcile by filename stem (the bare `<ts>` or full `<ts>-run-reconcile` form); default: newest matching save for this step. An unresolved id prints a note and falls back to a fresh audit. Not compatible with --all (a pinned save can't mean anything sensible across every step). |
