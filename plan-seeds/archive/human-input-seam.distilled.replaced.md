> **Historical pre-recut source — 2026-08-27.** This snapshot described a
> repository-wide migration and is retained only as provenance. The current
> plan proves one `review_walk` vertical slice; #322 carries the remaining
> migration. Do not use this snapshot as current scope.

## Overview

This plan adds one injectable `ask_human(request: HumanInputRequest) -> Resolution` seam for every enumerated human-input and human-absence check in plan-tool. A process selects `tty`, `absent`, or `remote` once through `PLAN_TOOL_HUMAN_IO`; `tty` and `absent` preserve current behavior exactly, while `remote` either applies a declared `remote_default` with an advisory event or waits for a filesystem-backed resolution record. This is phase 1 of the `integration` headless-feedback bridge described in `.tmp/integration-headless-feedback-bridge.investigation.md`; the HTTP transport remains a separate seed.

## Problem statement

plan-tool has an established pattern for injectable Claude calls: `create.shell_claude_invoker` at `create.py:753`, `shell.shell_concept_invoker` at `shell.py:489`, `claude_invoker` at `create.py:9791`, `invoker` elsewhere, `transport` for the streaming path, and `backend_runner.py:312` `run_streaming_once`. `tests/conftest.py` prevents tests from spawning the real binary without an override.

Human input has no equivalent tool-wide seam. `review_walk.walk_recommendations` (`review_walk.py:600`) has a local `input_fn`/`output_fn`/`persist_fn` injection, while other sites call `builtins.input()` directly or infer that no human is available through `sys.stdin.isatty()`. `create.py:5299` also uses the distinct `_stdin_has_pending_input()` readiness check at `create.py:5165`. These mechanisms only model a person at the terminal or no person at all; headless operation under `integration` needs an explicit third state in which a person is reachable asynchronously.

## Architecture

### Seam and providers

Add `plan_tool/human_io.py` with `ask_human(request: HumanInputRequest) -> Resolution`. Select one provider once per process and never re-derive it per call:

- `tty` routes to today's `input()` behavior.
- `absent` routes to each site's existing auto-degrade behavior.
- `remote` uses a transport-agnostic provider whose reference transport writes a JSON request record to a configured directory and polls for a matching resolution record.

`PLAN_TOOL_HUMAN_IO` accepts `tty`, `absent`, or `remote`, following the existing `PLAN_TOOL_BACKEND`-style precedent. When it is set, the seam must not override it using `isatty()`; when it is unset, `isatty()` may continue selecting between `tty` and `absent`. Any exact CLI-flag surface is `create`'s call.

### Per-site policy

Every prompt site declares a stable `prompt_id`, such as `review-walk.recommendation`, `jira.epic-key`, `rate-limit.action`, or `create.cache-reuse`, plus an independent optional `remote_default`. The existing `absent` default and the new `remote_default` may differ. Presence of `remote_default` is the policy: when set, `remote` returns it and emits an advisory event; when explicitly `None`, `remote` blocks and asks. There is no separate escalate-vs-degrade policy table.

Every enumerated site must record an explicit, reasoned `remote_default` decision during `create`, rather than leaving site discovery to `detail`.

### Request and resolution records

`HumanInputRequest` carries `request_id`, `prompt_id`, `kind` (`confirm` | `choice` | `text`), `question`, `choices`, `allow_free_text`, `context`, and `remote_default` when set. `context` contains information already available to the caller, such as a plan slug, step id, or finding anchors. `allow_free_text` preserves prose guidance from the review walk's feedback key for the next Claude call.

`Resolution` carries `request_id`, `value`, optional `free_text`, and `outcome` (`answered` | `default-applied`).

### Filesystem reference transport

The reference `remote` transport writes a request record and polls for its resolution record. It proves request shape, blocking and resumption, and advisory events without an external service or integration-specific knowledge. Its protocol boundary must allow a later HTTP transport without changing the seam or callers.

### Call-site migration

Route the complete inventory through the seam without restructuring CLI layering, the invoker seam, or module boundaries beyond adding `human_io.py`:

- `review_walk.py:600` (`walk_recommendations`'s existing `input_fn` injection)
- `cli/jira_cmd.py` (epic wizard `:609-1098`, confirms `:500,555,772,774`, story menu `:922`)
- `cli/authoring.py:1240,279,367,446,2260`
- `cli/manifest.py:474,799`
- `cli/worktree_cmd.py:301`
- `cli/lessons_cmd.py:216,332`
- `shell.py:409` and `launcher.py:548`, both calling `claude_errors.py:1050` `ask_on_rate_limit_action`
- `create.py` cache/collision prompts at `:1864,3329,3454,3645,4089,4526,5263,6904`
- `create.py` `isatty()` sites at `:6378,6733,7988,8437`
- `create.py:5299` and `_stdin_has_pending_input()` at `create.py:5165`
- `detail.py` at `:5707,5739,5926,6300`
- `reground.py:286`
- `scope_out.py:1492`
- `change_collision.py:353`
- `roadmap.py:2523`
- `cli/completeness_phases.py:991`

The broader direct-input inventory includes the jira epic wizard and confirmations (`cli/jira_cmd.py:500,555,609-1098,772,774,922`), destructive confirmations (`cli/authoring.py:1240,279,367,446,2260`; `cli/manifest.py:474,799`; `cli/worktree_cmd.py:301`; `cli/lessons_cmd.py:332`), and `create.py:1864,3329,3454,3645,4089,4526,5263,6904`. The current human-absence inventory also covers `create.py`, `detail.py`, `reground.py:286`, `scope_out.py:1492`, `change_collision.py:353`, `roadmap.py:2523`, `cli/completeness_phases.py:991`, `cli/lessons_cmd.py:216`, `cli/manifest.py:463,786`, and `cli/jira_cmd.py:488,539,772`.

Update `TESTING.md`'s invoker-seam neutralization table at `TESTING.md:64`, including rows `:66-84`, and cover the seam under `tests/`.

### Parallel apply refusal

`completeness-apply --jobs N>1` already means no human is consulted and Claude approves everything at `cli/completeness_phases.py:581,739`. Combining it with `remote` would create concurrent blocking requests against one person, so this combination must fail at startup with an actionable error before any work begins.

## Out of scope

- The HTTP transport and any integration-specific wire format; these remain a separate seed until integration's API shape is signed off, as described in `.tmp/integration-headless-feedback-bridge.investigation.md` § Sequencing.
- Anything in the `integration` repository.
- Changes to what existing prompts ask, their `tty`-mode wording, or their `absent`-mode default values; this is a routing change for existing modes.
- A separate escalate-vs-degrade policy table; the per-site `remote_default` field supersedes it.
- Who may answer a `remote` request, request expiry or timeout policy, and first-write-wins resolution semantics; `.tmp/integration-headless-feedback-bridge.investigation.md` assigns these to the future multi-reader transport.
- Changes to the Claude invoker seam in `shell.py` or `backend_runner.py`; this plan adds only the analogous human-input seam.

## Risks

- **Incomplete call-site sweep:** a remaining `builtins.input()` site can hang forever in a headless container with no TTY and no reachable remote human. Treat the In-scope inventory as a grep-verified deliverable during `create`, not best-effort discovery during `detail`.
- **Wrong per-site `remote_default`:** too many `None` decisions can overwhelm the remote operator, while too many defaults can make consequential decisions such as destructive confirmations or conflict resolution unattended. Require an explicit, reasoned decision per site and emit an advisory event whenever a default is applied.
- **`absent` or `tty` regression:** moving load-bearing behavior can silently change current CLI or CI behavior. Require a regression test for every relocated site in both existing modes.
- **Undefined `--jobs N` interaction:** allowing `remote` with `--jobs N>1` can create N concurrent blocking requests with no coordination. Refuse the combination at startup.

## Testing

- Under `tests/`, verify every relocated site in `tty` mode calls an `input()`-equivalent and returns the same value as today.
- Under `tests/`, verify every relocated site in `absent` mode returns its existing default through the `absent` provider with no behavior change.
- Verify `remote` without `remote_default` blocks until a matching filesystem resolution record is written, then returns its value.
- Verify `remote` with `remote_default` returns immediately, requires no filesystem write, and emits an advisory event.
- Verify `PLAN_TOOL_HUMAN_IO=remote` remains authoritative regardless of `isatty()`, while an unset `PLAN_TOOL_HUMAN_IO` preserves current `isatty()` selection between `tty` and `absent`.
- Verify `remote` combined with `completeness-apply --jobs N>1` fails before processing any gap and reports an actionable error.
- Follow the seam-neutralization convention documented in `TESTING.md`; tests override the seam, and filesystem transport tests inject a short poll interval rather than exercising a live default poll loop.

## Acceptance criteria

- For every enumerated prompt site and selected mode, the seam either obtains an answer through `input()`, a filesystem resolution record, or the site's declared default, or blocks waiting for an answer.
- No `builtins.input()` or `sys.stdin.isatty()` call remains outside `plan_tool/human_io.py` at any enumerated site, including the distinct `_stdin_has_pending_input()` route.
- `tty` and `absent` remain behavior-identical to pre-change plan-tool at every relocated site.
- In `remote` mode without `remote_default`, the filesystem transport blocks and resumes with the matching resolution value.
- In `remote` mode with `remote_default`, the seam returns that value and emits an advisory event.
- `remote` combined with `completeness-apply --jobs N>1` fails fast with a clear error and processes zero gaps.
- Every enumerated site records an explicit, reasoned `remote_default` value or explicitly records `None` as always ask.
- `TESTING.md`'s invoker-neutralization table documents the new seam.
- `BACKLOG.md` #321 is removed or marked shipped once the work lands.

## Deferred

- An HTTP transport that talks to integration, once integration's API shape is signed off; it receives its own seed.
- Request expiry and timeout policy, who may answer, and first-write-wins resolution semantics; these apply when a multi-reader HTTP transport exists, not to the single-reader filesystem transport.
- A CLI flag for choosing `PLAN_TOOL_HUMAN_IO` beyond the environment variable, if operator demand emerges.
- Per-run overrides of `remote_default`, such as always asking during one run regardless of site defaults, if operator demand emerges.

## Input

- `BACKLOG.md` #321 supplies the scope contract and must be updated when the plan ships.
- Existing prompt behavior is an input contract: `tty` must preserve current `builtins.input()` behavior, and `absent` must preserve each site's current `sys.stdin.isatty()`-driven default.
- `review_walk.walk_recommendations` at `review_walk.py:600` supplies the existing local `input_fn`/`output_fn`/`persist_fn` injection pattern that becomes a seam call.
- `claude_errors.py:1050` `ask_on_rate_limit_action` is shared by the batch lane at `shell.py:409` and streaming lane at `launcher.py:548`; both callers must route through the new seam.
- `.tmp/integration-headless-feedback-bridge.investigation.md` supplies the phase boundary: the filesystem transport belongs here, while integration-specific HTTP behavior remains later.
