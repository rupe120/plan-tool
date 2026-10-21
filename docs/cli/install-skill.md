# `plan-tool install-skill`

## Usage

```
plan-tool install-skill [-h] [--root {.claude,.agents}] [--integration {claude,codex,cursor}] [--user] [--copy] [--force]
```

## Options

| Option | Default | Description |
| --- | --- | --- |
| `--root` `{.claude|.agents}` | — | skill root to install under (default: .claude; .agents for --integration codex, which does not read .claude) |
| `--integration` `{claude|codex|cursor}` | `claude` | which bundled SKILL.md to install (default: claude) |
| `--user` | off | install under ~/<root> (e.g. ~/.claude) so every project the operator drives discovers it — no per-project step |
| `--copy` | off | copy the file instead of symlinking — the skill travels with the repo (committable), but goes stale on a plan-tool upgrade; always on for --integration codex, which ignores a symlinked SKILL.md |
| `--force` | off | overwrite destination files that point elsewhere — only the colliding paths are unlinked; an already-correct sibling is left untouched |
