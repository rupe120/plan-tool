# `plan-tool sweep`

## Usage

```
plan-tool sweep [-h] [-y] [--dry-run] [--report-only] [--archive-duplicates] [--commit]
```

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--dry-run` | off | report what WOULD be archived without touching disk or the manifest |
| `--report-only` | off | skip the archive pass entirely; print only the partial-status report |
| `--archive-duplicates` | off | move duplicate plan files discovered under non-selected candidate repo roots to an `archive/` subdirectory beside each duplicate. Use this after auto-discovery surfaces stale copies from a forgotten checkout or pre-move location. Requires -y for non-interactive runs. |
| `--commit` | off | after sweeping, stage all changes (git add -A) and create one commit for the archived plans + manifest edits (subject 'sweep: archive N completed plans'). Requires a clean working tree up front; incompatible with --dry-run / --report-only; off by default; only commits when the sweep moved something. |
