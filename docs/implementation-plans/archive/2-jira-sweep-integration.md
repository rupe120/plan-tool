---
title: Jira Sweep Integration
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a deterministic scan that collects each plan's Jira stories and epic
  files:
  - plan_tool/jira_config.py
  - plan_tool/jira.py
  - plan_tool/locator.py
  creates:
  - plan_tool/jira_sweep.py
  - tests/test_jira_sweep.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Wire up `plan-tool jira-sweep collect`
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - .gitignore
  creates:
  - plan_tool/cli/jira_sweep_cmd.py
  - tests/cli/test_jira_sweep_cmd.py
  complexity: low
  change_type: feature
  depends_on:
  - 1
- id: 3
  title: Add the live-Jira-status Claude call (`jira-sweep check`)
  files:
  - TESTING.md
  creates:
  - plan_tool/prompts/jira-sweep-check.md
  complexity: high
  change_type: feature
  depends_on:
  - 1
- id: 4
  title: Wire up `plan-tool jira-sweep check`
  complexity: low
  change_type: feature
  depends_on:
  - 2
  - 3
- id: 5
  title: Match local stories against Jira status and write the readiness report
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 3
- id: 6
  title: Wire up `plan-tool jira-sweep report`
  complexity: low
  change_type: feature
  depends_on:
  - 4
  - 5
- id: 7
  title: Add a public helper to flip a story's status tag by id
  files:
  - plan_tool/jira.py
  complexity: low
  change_type: feature
- id: 8
  title: Add the `--apply-story-status` gate to `jira-sweep report`
  files:
  - plan_tool/cli/app.py
  complexity: medium
  change_type: feature
  depends_on:
  - 6
  - 7
- id: 9
  title: Document the jira-sweep workflow and note the follow-up cleanup in the other
    repo
  files:
  - RUNBOOK.md
  - CAPABILITIES.md
  - CLAUDE.md
  - docs/cli/README.md
  creates:
  - docs/cli/jira-sweep.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  - 4
  - 6
  - 8
---
# Jira Sweep Integration

## Overview

This plan folds the external `example-app-amplify` `scripts/jira-plan-sweep/` workflow into plan-tool as a new `plan-tool jira-sweep` command group with three subcommands: `collect` (deterministic candidate scan), `check` (the one Claude-invoking step, querying live Jira status via Atlassian MCP), and `report` (deterministic matcher/report writer, with an optional `--apply-story-status` gate). It answers a question `plan-tool sweep` cannot answer today: whether a plan's exported Jira stories are all closed and therefore ready to archive. The deterministic two-thirds of the work reuses existing seams (`jira_config.py`, `jira.py`, `locator.py`); only the live Jira query needs a new Claude-invoking step, following the existing `shell.py` invoker pattern. The command group stays report-only for plan/archive mutation — it never flips plan frontmatter `status:` and never invokes `sweep` itself.

## Problem statement

Today, knowing whether a plan's exported Jira stories are all closed requires running a bespoke 3-script workflow (`collect-candidates.mjs` → a live Jira check run by hand inside a Claude Code session with Atlassian MCP → `report.mjs`) that lives entirely outside plan-tool, in the `example-app-amplify` repo. That workflow re-implements logic plan-tool already owns: it re-parses `jira-config.json` by hand instead of using `plan_tool/jira_config.py`'s `load_config` / `JiraConfig.epic_for_plan`, it uses ad hoc regexes (`HEADER_RE`, `TITLE_RE`, `EPIC_LINE_RE`) to parse `jira-stories.md` instead of `plan_tool/jira.py`'s real parser (`read_stories_for_lint`), and it shells out to `plan-tool status <slug>` per plan and greps stdout instead of using `locator.py`'s typed manifest access (`load_manifest_plan_paths` / `list_plans_from_manifest` / `PlanEntry`). Meanwhile `plan-tool sweep` already archives *completed* plans but has no way to know a plan's Jira-tracked stories are actually done, so operators are stuck maintaining a second, drifting implementation just to feed `sweep` the readiness signal it's missing.

## Architecture

A new top-level verb group, `plan-tool jira-sweep`, with three subcommands mirroring the three workflow phases. `collect [--all | <name>...]` is no-Claude, no-network: it enumerates registered, un-archived plans via `locator.py`, finds each plan's `plan-details/<slug>/jira-stories.md`, resolves an epic via `jira_config.py`, parses stories via `jira.py`'s existing parser, and writes `.plan-tool/jira-sweep/candidates.json`; a plan with an unresolved epic key is skipped with a warning. `check` is the one Claude-invoking step: it builds one consolidated prompt listing every unique epic id (mirroring `jira.py`'s "one Claude call over the whole plan" idiom rather than one subprocess per epic), asks the invoked `claude` to run the documented JQL (`"Epic Link" = <id> ORDER BY created ASC`, paginating on `nextPageToken`) via Atlassian MCP tools, and parses the structured JSON response itself before writing `.plan-tool/jira-sweep/jira-status.json` — Python owns the write, Claude only proposes. It introduces a new invoker, `shell_jira_check_invoker`, in `shell.py`'s `shell_*_invoker` family, overridable per `TESTING.md`'s seam discipline, with rate-limit recovery via the shared `rate_limit_loop.py`. `report` is no-Claude: it reads both JSON files, matches local stories to Jira issues by normalized title (bracket prefix stripped, case/whitespace-insensitive), and writes `.plan-tool/jira-sweep/report.md` with per-plan story counts, unmatched/still-open stories, and which plans are fully closed; its printed next-step block names only `plan-tool` commands, per CLAUDE.md's rule. An optional, gated `--apply-story-status` flag (interactive confirm, or `-y`) flips `[status: done]` on `jira-stories.md` blocks whose matched Jira issue is closed, via `jira.py`'s existing `_set_markdown_block_status` — the same apply-or-recommend gate shape as `scope_out_step` / `escalate_to_split` / `reground_bridge`. The key design trade-off: the deterministic pieces reuse existing seams directly, but the live Jira query inherently cannot be a pure Python function since it requires interactive Atlassian MCP tool access — so it's automated the same way `plan-tool jira` already automates story synthesis, shelling out to `claude -p` through the existing invoker seam and relying on the *caller's* environment already having MCP configured, rather than plan-tool provisioning or configuring MCP servers itself. CLI wiring lands in a new `cli/jira_sweep_cmd.py` (or folds into `cli/jira_cmd.py` if decomposition finds that cleaner).

## References

- [The Jira Cloud platform REST API — Issue Search](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/) — Official Jira Cloud REST API v3 reference for the /search/jql endpoint, including the nextPageToken-based pagination contract needed to page through all issues for an epic.
- [JQL fields | Jira Cloud | Atlassian Support](https://support.atlassian.com/jira-software-cloud/docs/jql-fields/) — Atlassian's authoritative field reference for JQL, covering the Epic Link/parent field and ORDER BY syntax the check step's consolidated query relies on.
- [Getting started with the Atlassian Rovo MCP Server](https://support.atlassian.com/atlassian-rovo-mcp-server/docs/getting-started-with-the-atlassian-remote-mcp-server/) — Official setup and capability guide for Atlassian's remote MCP server, the tool surface the `check` subcommand assumes is already configured in the caller's environment.
- [atlassian/atlassian-mcp-server (GitHub)](https://github.com/atlassian/atlassian-mcp-server) — Official repo for Atlassian's remote MCP server, useful for confirming the exact tool names/schemas exposed for Jira issue search over MCP.
- [Run Claude Code programmatically (Headless mode)](https://code.claude.com/docs/en/headless) — Official Claude Code docs for the `-p`/print, non-interactive invocation and `--output-format json` contract that the new `shell_jira_check_invoker` must follow.
- [Model Context Protocol Specification (2025-06-18)](https://modelcontextprotocol.io/specification/2025-06-18) — The canonical MCP protocol spec, useful for understanding the tool-call/response shape underlying any Atlassian MCP tool invocation made from within a Claude session.

## Steps

See the `steps:` block in the frontmatter.

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

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (feature) — unit tests added with the implementation; green before completion.
- step 9 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool jira-sweep collect` produces a `candidates.json` equivalent in content/shape to the original script's output, reusing `jira_config.py` and `jira.py` rather than re-parsing either format.
- `plan-tool jira-sweep check` fails with a clear, actionable message (not a silently-empty `jira-status.json`) when Atlassian MCP tools aren't reachable from the invoked subprocess.
- `plan-tool jira-sweep report` correctly classifies a fixture set of candidates + jira-status into fully-closed / blocked (unmatched or open stories), matching today's script's title-normalization semantics.
- `--apply-story-status` flips only the matched-and-closed stories' status tags in `jira-stories.md`, never plan frontmatter, and is gated behind a TTY confirm (or `-y`).
- Every new invoker seam is neutralized in tests per `TESTING.md`; no test spawns the real `claude` binary.
- `RUNBOOK.md` documents the three-command flow end to end, replacing the external script's README as the operational source of truth.

## Deferred

- **Consuming-repo cleanup** — once `jira-sweep` ships, `example-app-amplify`'s `scripts/jira-plan-sweep/` becomes redundant and should be removed there; this plan does not touch other repos, so that removal is a separate, manual follow-up to name explicitly in this plan's final step/acceptance criteria rather than code done here.
