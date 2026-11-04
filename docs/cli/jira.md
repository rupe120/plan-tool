# `plan-tool jira`

## Usage

```
plan-tool jira [-h] [-y] [--show] [--lint] [--input INPUT] [--max-hours MAX_HOURS] [--format {markdown,json}] [--output OUTPUT] [--no-write] [--stdout] [--epic EPIC] [--jira-tag JIRA_TAG] [--handoff-output HANDOFF_OUTPUT] [--adopt-existing] [name]
```

## Arguments

| Argument | Description |
| --- | --- |
| `name` | plan name to export, or the literal `config` to manage jira-config.json (epics + plan assignments) |

## Options

| Option | Default | Description |
| --- | --- | --- |
| `-y`, `--yes` | off | auto-accept Y/N confirmation prompts (proceed with the offered action without asking). Useful for scripted/unattended runs. |
| `--show` | off | only meaningful with `jira config` — print the current config and exit without opening the wizard |
| `--lint` | off | lint an existing jira-stories artifact without invoking claude or assigning an epic; pass a plan name or --input <path> |
| `--input` `INPUT` | — | with --lint, check this existing jira-stories markdown/json file instead of resolving a plan's conventional output |
| `--max-hours` `MAX_HOURS` | `8` | advisory per-story size target in hours (default: 8). A soft target, not a hard cap — stories are sized to be atomic PRs (independently mergeable without breaking the build), so a large-but-atomic story is kept whole rather than fragmented. |
| `--format` `{markdown|json}` | `markdown` | output format (default: markdown, paste-ready into JIRA) |
| `--output` `OUTPUT` | — | explicit output file path. Default: <plan_dir>/plan-details/<plan_slug>/jira-stories.{md,json} |
| `--no-write` | off | invoke the story generator but do not write either artifact; print the story and developer handoff instead |
| `--stdout` | off | also print the formatted output to stdout (default prints only a short summary line when writing succeeds) |
| `--epic` `EPIC` | — | epic key to assign this plan to when it isn't yet listed in `plan_assignments`. Useful for scripts: skips the interactive prompt that the TTY flow would otherwise show. Must match a defined epic key in `jira-config.json`. |
| `--jira-tag` `JIRA_TAG` | — | short grouping tag to confirm for this plan when it isn't yet listed in `plan_tags` (rendered into every story title so tickets from the same plan stay grouped). Useful for scripts: skips the interactive confirm prompt / -y auto-accept that the TTY flow would otherwise show. 1-24 chars, letters/digits/-/_ only. |
| `--handoff-output` `HANDOFF_OUTPUT` | — | explicit developer-handoff output path. Default: <plan_dir>/jira-handoffs/<plan_slug>/<normalized-story-stem>.developer-handoff.md |
| `--adopt-existing` | off | allow this export to replace the selected readable legacy story source after validating every carried Jira key and story state; never adopts a handoff |
