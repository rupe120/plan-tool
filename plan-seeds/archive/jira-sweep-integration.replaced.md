> **Replaced**: this file has been superseded by `docs/implementation-plans/2-jira-sweep-integration.md`.
> Preserved here for history; do not edit.

# Plan seed: `jira-sweep` — fold the external jira-plan-sweep workflow into plan-tool

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/jira-sweep-integration.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below
and proposes a step decomposition; the author then runs `plan-tool detail`
per step.

---

## Background

A consuming repo (`example-app-amplify`) has a bespoke 3-script workflow at
`scripts/jira-plan-sweep/` (`collect-candidates.mjs` → a live Jira check run
by hand inside a Claude Code session with Atlassian MCP → `report.mjs`) that
answers one question: **which un-archived plans have every exported Jira
story closed, and are therefore ready for `plan-tool sweep`?** It exists
because `plan-tool sweep` already archives *completed* plans but has no way
to know a plan's Jira-tracked stories are actually done — that check
currently lives outside plan-tool entirely, re-implementing logic plan-tool
already owns.

This plan folds that workflow into plan-tool itself as a new command group,
because the deterministic two-thirds of it already has a home:

- **Epic resolution** — the script re-parses `jira-config.json` by hand;
  `plan_tool/jira_config.py` (`load_config`, `JiraConfig.epic_for_plan`)
  already does this, including plan-assignment validation.
- **`jira-stories.md` parsing** — the script uses ad hoc regexes
  (`HEADER_RE`, `TITLE_RE`, `EPIC_LINE_RE`) that can drift from the real
  format documented in `JIRA_FORMAT.md`; `plan_tool/jira.py` already has a
  real parser (`read_stories_for_lint` / `_read_markdown_stories_for_lint`)
  producing typed `Story` records, plus `reconcile_existing_statuses` /
  `_set_markdown_block_status` for flipping a story's `[status: todo|done]`
  tag in place.
- **Plan enumeration** — the script shells out to `plan-tool status <slug>`
  per plan and greps its stdout; `locator.py` (`load_manifest_plan_paths` /
  `list_plans_from_manifest` / `PlanEntry`) already gives typed, per-project
  access to the same data in-process.
- **The archive step this feeds** — `plan-tool sweep` already exists;
  this plan produces the readiness signal `sweep` needs but doesn't have.

The one piece that does **not** have a home: the live Jira query. It
inherently requires interactive Atlassian MCP tool access (`searchJiraIssuesUsingJql`
et al.) — not something a pure Python function can do. The design below
automates it the same way `plan-tool jira` already automates story
synthesis: shell out to `claude -p` via the existing invoker seam
(`plan_tool/shell.py`), relying on the *caller's* environment already having
Atlassian MCP configured (project `.mcp.json` / user settings) — plan-tool
does not provision or configure MCP servers itself, matching how the manual
workflow already assumes MCP is available in-session.

## Command surface

A new top-level verb group, `plan-tool jira-sweep`, with three subcommands
mirroring the three workflow phases (naming/exact flags are for `create` to
firm up during decomposition — this is the intent, not the final CLI):

1. **`plan-tool jira-sweep collect [--all | <name>...]`** — no Claude, no
   network. Enumerates registered, un-archived plans (`locator.py`), finds
   the ones with a `plan-details/<slug>/jira-stories.md`, resolves each to
   an epic via `jira_config.py`, parses stories via `jira.py`'s existing
   parser, and writes `.plan-tool/jira-sweep/candidates.json`. Prints the
   unique `jira_epic_id` set the next step needs. A plan with an unresolved
   epic key is skipped with a warning, same as today's script.

2. **`plan-tool jira-sweep check`** — the one Claude-invoking step. Reads
   `candidates.json`, builds **one consolidated prompt** listing every
   unique epic id (mirroring `jira.py`'s "one Claude call over the whole
   plan" idiom rather than one subprocess per epic), and asks the invoked
   `claude` to run the documented JQL (`"Epic Link" = <id> ORDER BY created
   ASC`, paginating on `nextPageToken`) via Atlassian MCP tools and return
   each epic's issues (`key`, `summary`, `status`, `status.statusCategory.key`)
   as structured JSON on stdout. plan-tool parses that response (Python
   owns the write, matching every other invoker in this codebase — Claude
   proposes, Python persists) and writes `.plan-tool/jira-sweep/jira-status.json`.
   New invoker `shell_jira_check_invoker` in `shell.py`'s family,
   `invoker=` overridable per `TESTING.md`'s seam discipline. Fails
   clearly (not silently) when MCP tools aren't available to the
   subprocess or the response doesn't parse — this command is useless
   without live Jira access and must say so, not produce an empty report.

3. **`plan-tool jira-sweep report`** — no Claude. Reads both JSON files,
   matches local stories to Jira issues by normalized title (bracket
   prefix stripped, case/whitespace-insensitive — same heuristic as today,
   since local story keys don't reliably carry the epic prefix Jira lands
   on), and writes `.plan-tool/jira-sweep/report.md`: per-plan story
   counts, unmatched/still-open stories, and which plans are fully closed.
   Stays **report-only for plan/archive mutation** — never flips plan
   frontmatter `status:` and never invokes `sweep` itself, preserving the
   original workflow's deliberate stop-short-of-full-automation (plan
   frontmatter and archiving are both git-tracked mutations worth a human
   glance). Its printed next-step block follows CLAUDE.md's rule (plan-tool
   commands only, never a session activity): "mark steps done + `status:
   completed`, then `plan-tool sweep --dry-run`".

   One optional, gated value-add beyond the original script: **`--apply-story-status`**
   (interactive confirm, or `-y` to skip — the same apply-or-recommend gate
   shape as `scope_out_step` / `escalate_to_split` / `reground_bridge`)
   flips `[status: done]` on `jira-stories.md` blocks whose matched Jira
   issue is closed, via `jira.py`'s existing `_set_markdown_block_status`.
   This is the low-risk mechanical half (an export sidecar catching up to
   reality) — it must **not** be conflated with the archive decision, which
   still requires the human-glance step above.

## Seams already in place (verify before extending)

- `plan_tool/jira_config.py` — `load_config`, `JiraConfig.epic_for_plan`,
  `Epic.jira_epic_id`. Reuse directly; do not re-parse `jira-config.json`.
- `plan_tool/jira.py` — `read_stories_for_lint` (dispatches markdown/JSON),
  `Story` dataclass, `reconcile_existing_statuses`, `_set_markdown_block_status`,
  `derive_jira_output_path` (to find `jira-stories.md` for a given plan
  slug). Some of these are private (`_`-prefixed) — decide during
  decomposition whether to widen their visibility or add thin public
  wrappers rather than duplicating the logic.
- `plan_tool/locator.py` — `load_manifest_plan_paths` / `list_plans_from_manifest`
  / `PlanEntry` for per-project plan enumeration; `PlanToolContext` for the
  repo-scoped `.plan-tool/` directory the new JSON artifacts live under.
- `plan_tool/shell.py` — `claude_invoke` and the `shell_*_invoker` wrapper
  pattern (`shell_jira_invoker`, `shell_detail_invoker`) this plan's
  `shell_jira_check_invoker` should follow, including rate-limit recovery
  via `rate_limit_loop.py` (already shared infra, not to be re-implemented).
- `plan_tool/sweep.py` — `sweep_plans`, `classify_plan`. This plan does not
  modify `sweep`; it only produces the readiness report a human consults
  before running it.
- `TESTING.md` — the invoker-neutralization table. `shell_jira_check_invoker`
  must be added there and every test overriding it, matching the existing
  discipline (the autouse `conftest.py` gate already raises if a test spawns
  the real `claude` binary without opting in).

## Scope of work

1. **`jira-sweep collect`** — deterministic candidate scan reusing
   `locator.py` + `jira_config.py` + `jira.py`'s parser. Writes
   `.plan-tool/jira-sweep/candidates.json`. CLI wiring in a new
   `cli/jira_sweep_cmd.py` (or folded into `cli/jira_cmd.py` if decomposition
   finds that cleaner — decide during `create`).
2. **`jira-sweep check`** — new `shell_jira_check_invoker` + prompt template
   (mirroring `plan_tool/prompts/jira.md`'s existing pattern) instructing
   Claude to query each epic's issues via Atlassian MCP and return
   structured JSON; a parser (`parse_jira_status_response` or similar,
   mirroring `parse_jira_response`'s hardening) that validates shape before
   writing `.plan-tool/jira-sweep/jira-status.json`. Clear, actionable
   failure when MCP access isn't available or the response is malformed —
   this is the one step allowed to fail loudly and stop the pipeline.
3. **`jira-sweep report`** — deterministic matcher/report writer, plus the
   opt-in `--apply-story-status` gate described above. Writes
   `.plan-tool/jira-sweep/report.md`.
4. **Manifest/gitignore** — confirm `.plan-tool/jira-sweep/` falls under the
   existing `.plan-tool/*` gitignore rule (it does, per the original
   README); no new rule needed, just verify.
5. **Docs** — `RUNBOOK.md` (the three-command walkthrough, replacing the
   external script's README as the source of truth), `CAPABILITIES.md`
   (map the new surface to the relevant `MISSION.md` principle(s)),
   `docs/cli/` regeneration (`python -m plan_tool.cli_reference --write`),
   and CLAUDE.md's command-list mention alongside `sweep`.
6. **Migration note for the consuming repo** — not part of this plan's
   code, but the plan's final step/acceptance criteria should say so
   explicitly: once `jira-sweep` ships, `example-app-amplify`'s
   `scripts/jira-plan-sweep/` becomes redundant and should be removed
   there (a separate, manual follow-up in that repo — this plan does not
   touch other repos).
7. **Tests.** `collect` against a `tmp_path` project with a fabricated
   manifest/jira-config/jira-stories.md fixture (epic resolution, missing-epic
   skip, unparseable-stories skip). `check`'s invoker stubbed per
   `TESTING.md` discipline (never the real `claude` binary) — cover the
   consolidated-prompt construction, response parsing/validation, and the
   MCP-unavailable / malformed-response failure paths. `report`'s title-matching
   (bracket-stripped, case/whitespace-insensitive), fully-closed vs.
   blocked classification, unmatched/open reporting, and
   `--apply-story-status` (confirm gate, `-y` bypass, correct blocks
   flipped, plan frontmatter/`sweep` never touched).

## Non-goals

- **No plan-frontmatter mutation, ever, from this command group.** Marking
  steps `done` / plan `status: completed` stays a manual step a human does
  before running `sweep` — this plan only reports readiness.
- **No auto-invoking `sweep`.** `report` may *suggest* the exact next
  commands; it never runs them.
- **No MCP provisioning.** `jira-sweep check` assumes the calling
  environment already has Atlassian MCP configured (exactly as the manual
  workflow does today) — plan-tool does not install, configure, or manage
  MCP servers.
- **No generalization to other trackers.** This mirrors `plan-tool jira`'s
  existing Jira-only scope; a GitHub Issues / Linear equivalent is a
  separate future plan if ever needed.
- **No change to `plan-tool jira`'s export behavior** (story synthesis,
  `jira-stories.md` format, `jira-config.json` schema) — this plan only
  *reads* those artifacts.

## Acceptance criteria (plan-level)

- `plan-tool jira-sweep collect` produces a `candidates.json` equivalent in
  content/shape to the original script's output, reusing `jira_config.py`
  and `jira.py` rather than re-parsing either format.
- `plan-tool jira-sweep check` fails with a clear, actionable message (not
  a silently-empty `jira-status.json`) when Atlassian MCP tools aren't
  reachable from the invoked subprocess.
- `plan-tool jira-sweep report` correctly classifies a fixture set of
  candidates + jira-status into fully-closed / blocked (unmatched or open
  stories), matching today's script's title-normalization semantics.
- `--apply-story-status` flips only the matched-and-closed stories' status
  tags in `jira-stories.md`, never plan frontmatter, and is gated behind a
  TTY confirm (or `-y`).
- Every new invoker seam is neutralized in tests per `TESTING.md`; no test
  spawns the real `claude` binary.
- `RUNBOOK.md` documents the three-command flow end to end, replacing the
  external script's README as the operational source of truth.

## Risks

- **Consolidated single-call prompt for `check` may hit context/response
  limits** if a repo has many epics with many issues each. If decomposition
  finds this a real risk, consider chunking (N epics per call) while still
  avoiding one-subprocess-per-epic overhead — note this as an open question
  for `create`/`detail` to resolve, not a decision made here.
- **Title-matching is inherently a heuristic** (inherited from the original
  script) — an unmatched story must stay surfaced as "unmatched," never
  silently treated as open or closed. Preserve that behavior exactly.
- **Widening `jira.py` private helpers' visibility** (`_set_markdown_block_status`,
  `_read_markdown_stories_for_lint`) risks scope creep into an unrelated
  module's internals. Prefer adding thin public wrappers over renaming
  existing `_`-prefixed functions, so `jira.py`'s existing contract and
  tests are undisturbed.
- **MCP-dependent step is inherently non-deterministic / environment-coupled**,
  unlike every other invoker in this codebase. Its failure mode must be
  loud and specific ("Atlassian MCP tool call failed/unavailable"), not a
  generic empty-result silently treated as "nothing to check."
