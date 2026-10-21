> **Replaced**: this file has been superseded by `docs/implementation-plans/2-jira-sweep-integration.md`.
> Preserved here for history; do not edit.

## Overview

This plan folds the external `example-app-amplify` `scripts/jira-plan-sweep/` workflow into plan-tool as a new `plan-tool jira-sweep` command group with three subcommands: `collect` (deterministic candidate scan), `check` (the one Claude-invoking step, querying live Jira status via Atlassian MCP), and `report` (deterministic matcher/report writer, with an optional `--apply-story-status` gate). It answers a question `plan-tool sweep` cannot answer today: whether a plan's exported Jira stories are all closed and therefore ready to archive. The deterministic two-thirds of the work reuses existing seams (`jira_config.py`, `jira.py`, `locator.py`); only the live Jira query needs a new Claude-invoking step, following the existing `shell.py` invoker pattern. The command group stays report-only for plan/archive mutation — it never flips plan frontmatter `status:` and never invokes `sweep` itself.

## Problem statement

Today, knowing whether a plan's exported Jira stories are all closed requires running a bespoke 3-script workflow (`collect-candidates.mjs` → a live Jira check run by hand inside a Claude Code session with Atlassian MCP → `report.mjs`) that lives entirely outside plan-tool, in the `example-app-amplify` repo. That workflow re-implements logic plan-tool already owns: it re-parses `jira-config.json` by hand instead of using `plan_tool/jira_config.py`'s `load_config` / `JiraConfig.epic_for_plan`, it uses ad hoc regexes (`HEADER_RE`, `TITLE_RE`, `EPIC_LINE_RE`) to parse `jira-stories.md` instead of `plan_tool/jira.py`'s real parser (`read_stories_for_lint`), and it shells out to `plan-tool status <slug>` per plan and greps stdout instead of using `locator.py`'s typed manifest access (`load_manifest_plan_paths` / `list_plans_from_manifest` / `PlanEntry`). Meanwhile `plan-tool sweep` already archives *completed* plans but has no way to know a plan's Jira-tracked stories are actually done, so operators are stuck maintaining a second, drifting implementation just to feed `sweep` the readiness signal it's missing.

## Architecture

A new top-level verb group, `plan-tool jira-sweep`, with three subcommands mirroring the three workflow phases. `collect [--all | <name>...]` is no-Claude, no-network: it enumerates registered, un-archived plans via `locator.py`, finds each plan's `plan-details/<slug>/jira-stories.md`, resolves an epic via `jira_config.py`, parses stories via `jira.py`'s existing parser, and writes `.plan-tool/jira-sweep/candidates.json`; a plan with an unresolved epic key is skipped with a warning. `check` is the one Claude-invoking step: it builds one consolidated prompt listing every unique epic id (mirroring `jira.py`'s "one Claude call over the whole plan" idiom rather than one subprocess per epic), asks the invoked `claude` to run the documented JQL (`"Epic Link" = <id> ORDER BY created ASC`, paginating on `nextPageToken`) via Atlassian MCP tools, and parses the structured JSON response itself before writing `.plan-tool/jira-sweep/jira-status.json` — Python owns the write, Claude only proposes. It introduces a new invoker, `shell_jira_check_invoker`, in `shell.py`'s `shell_*_invoker` family, overridable per `TESTING.md`'s seam discipline, with rate-limit recovery via the shared `rate_limit_loop.py`. `report` is no-Claude: it reads both JSON files, matches local stories to Jira issues by normalized title (bracket prefix stripped, case/whitespace-insensitive), and writes `.plan-tool/jira-sweep/report.md` with per-plan story counts, unmatched/still-open stories, and which plans are fully closed; its printed next-step block names only `plan-tool` commands, per CLAUDE.md's rule. An optional, gated `--apply-story-status` flag (interactive confirm, or `-y`) flips `[status: done]` on `jira-stories.md` blocks whose matched Jira issue is closed, via `jira.py`'s existing `_set_markdown_block_status` — the same apply-or-recommend gate shape as `scope_out_step` / `escalate_to_split` / `reground_bridge`. The key design trade-off: the deterministic pieces reuse existing seams directly, but the live Jira query inherently cannot be a pure Python function since it requires interactive Atlassian MCP tool access — so it's automated the same way `plan-tool jira` already automates story synthesis, shelling out to `claude -p` through the existing invoker seam and relying on the *caller's* environment already having MCP configured, rather than plan-tool provisioning or configuring MCP servers itself. CLI wiring lands in a new `cli/jira_sweep_cmd.py` (or folds into `cli/jira_cmd.py` if decomposition finds that cleaner).

## Out of scope

- No plan-frontmatter mutation, ever, from this command group — marking steps `done` / plan `status: completed` stays a manual step a human does before running `sweep`; this plan only reports readiness.
- No auto-invoking `sweep` — `report` may *suggest* the exact next commands but never runs them.
- No MCP provisioning — `jira-sweep check` assumes the calling environment already has Atlassian MCP configured (exactly as the manual workflow does today); plan-tool does not install, configure, or manage MCP servers.
- No generalization to other trackers — this mirrors `plan-tool jira`'s existing Jira-only scope; a GitHub Issues / Linear equivalent is a separate future plan if ever needed.
- No change to `plan-tool jira`'s export behavior (story synthesis, `jira-stories.md` format, `jira-config.json` schema) — this plan only *reads* those artifacts.

## Risks

- **Consolidated single-call prompt for `check` may hit context/response limits** if a repo has many epics with many issues each. If decomposition finds this a real risk, consider chunking (N epics per call) while still avoiding one-subprocess-per-epic overhead — an open question for `create`/`detail` to resolve, not a decision made here.
- **Title-matching is inherently a heuristic** (inherited from the original script) — an unmatched story must stay surfaced as "unmatched," never silently treated as open or closed. Preserve that behavior exactly.
- **Widening `jira.py` private helpers' visibility** (`_set_markdown_block_status`, `_read_markdown_stories_for_lint`) risks scope creep into an unrelated module's internals. Prefer adding thin public wrappers over renaming existing `_`-prefixed functions, so `jira.py`'s existing contract and tests are undisturbed.
- **MCP-dependent step is inherently non-deterministic / environment-coupled**, unlike every other invoker in this codebase. Its failure mode must be loud and specific ("Atlassian MCP tool call failed/unavailable"), not a generic empty-result silently treated as "nothing to check."

## Testing

`collect` is tested against a `tmp_path` project with a fabricated manifest/jira-config/jira-stories.md fixture, covering epic resolution, missing-epic skip, and unparseable-stories skip. `check`'s invoker (`shell_jira_check_invoker`) is stubbed per `TESTING.md`'s seam-neutralization discipline — never the real `claude` binary — covering consolidated-prompt construction, response parsing/validation, and the MCP-unavailable / malformed-response failure paths. `report`'s title-matching (bracket-stripped, case/whitespace-insensitive) is tested for fully-closed vs. blocked classification, unmatched/open reporting, and `--apply-story-status` (confirm gate, `-y` bypass, correct blocks flipped, plan frontmatter/`sweep` never touched). Every new invoker seam, including `shell_jira_check_invoker`, must be added to `TESTING.md`'s invoker-neutralization table and covered by tests that override it.

## Acceptance criteria

- `plan-tool jira-sweep collect` produces a `candidates.json` equivalent in content/shape to the original script's output, reusing `jira_config.py` and `jira.py` rather than re-parsing either format.
- `plan-tool jira-sweep check` fails with a clear, actionable message (not a silently-empty `jira-status.json`) when Atlassian MCP tools aren't reachable from the invoked subprocess.
- `plan-tool jira-sweep report` correctly classifies a fixture set of candidates + jira-status into fully-closed / blocked (unmatched or open stories), matching today's script's title-normalization semantics.
- `--apply-story-status` flips only the matched-and-closed stories' status tags in `jira-stories.md`, never plan frontmatter, and is gated behind a TTY confirm (or `-y`).
- Every new invoker seam is neutralized in tests per `TESTING.md`; no test spawns the real `claude` binary.
- `RUNBOOK.md` documents the three-command flow end to end, replacing the external script's README as the operational source of truth.

## Deferred

- **Consuming-repo cleanup** — once `jira-sweep` ships, `example-app-amplify`'s `scripts/jira-plan-sweep/` becomes redundant and should be removed there; this plan does not touch other repos, so that removal is a separate, manual follow-up to name explicitly in this plan's final step/acceptance criteria rather than code done here.
