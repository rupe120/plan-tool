> **Historical pre-recut source — 2026-08-27.** This snapshot described a
> repository-wide migration and is retained only as provenance. The current
> plan proves one `review_walk` vertical slice; #322 carries the remaining
> migration. Do not use this snapshot as current scope.

# Explicit human-input seam for headless/remote operation

Source: `BACKLOG.md` **#321**. Elaborates that entry's scope contract
verbatim; does not invent a different fence. This plan's completion requires
updating `BACKLOG.md` #321 (remove or mark shipped) once the work lands.

## Outcome

Every point in plan-tool that currently blocks on `builtins.input()` or
silently auto-degrades via `sys.stdin.isatty()` instead resolves through one
injectable `ask_human(request) -> Resolution` seam, driven by an explicit
mode — `tty`, `absent`, or `remote` — resolved once at process start, never
inferred per call. `tty` and `absent` reproduce today's behavior exactly,
routed through the new seam rather than scattered `input()`/`isatty()` calls.
`remote` is new: each prompt site either applies its own declared
`remote_default` (emitting an advisory event, never silently) or blocks and
asks, through a filesystem-backed reference transport (write a request
record, poll for a resolution record) that proves the seam end-to-end with no
external service. This is phase 1 of the `integration` headless-feedback bridge
described in `.tmp/integration-headless-feedback-bridge.investigation.md`; the HTTP
transport that actually talks to integration is a separate, later seed.

## Overview

plan-tool has a real, tested pattern for asking *Claude* something: every
Claude-invoking function takes an injectable invoker parameter, supplied by a
named caller-side wrapper (e.g. `create.shell_claude_invoker`, `create.py:753`;
`shell.shell_concept_invoker`, `shell.py:489`) that a call site wires in — the
kwarg name itself varies by site (`claude_invoker` at `create.py:9791`,
`invoker` elsewhere, `transport` for the streaming path) — plus
`backend_runner.py:312` `run_streaming_once` for the streaming supervisor
itself. `tests/conftest.py` enforces via an autouse guard that nothing spawns
the real binary un-overridden.

There is no equivalent for asking a *human*. `review_walk.walk_recommendations`
(`review_walk.py:600`) injects `input_fn`/`output_fn`/`persist_fn`, but only
locally to that one walk. Every other prompt calls `builtins.input()` inline:
the jira epic wizard and its confirmations (`cli/jira_cmd.py:500,555,609-1098,
772,774,922`), destructive-action confirms (`cli/authoring.py:1240,279,367,
446,2260`; `cli/manifest.py:474,799`; `cli/worktree_cmd.py:301`;
`cli/lessons_cmd.py:332`), the rate-limit action prompt — two separate call
sites, `shell.py:409` (batch lane) and `launcher.py:548` (streaming lane),
both calling the shared prompt function `claude_errors.py:1050`
`ask_on_rate_limit_action` — and `create.py`'s cache/collision prompts
(`create.py:1864,3329,3454,3645,4089,4526,5263,6904`). A parallel, larger set
of sites detects the *absence* of a human via `sys.stdin.isatty()` and
auto-degrades to a default instead of blocking (`create.py`, `detail.py`,
`reground.py:286`, `scope_out.py:1492`, `change_collision.py:353`,
`roadmap.py:2523`, `cli/completeness_phases.py:991`, `cli/lessons_cmd.py:216`,
`cli/manifest.py:463,786`, `cli/jira_cmd.py:488,539,772`). A third, distinct
presence-detection mechanism exists alongside `isatty()`: `create.py:5299`
uses `_stdin_has_pending_input()` (`create.py:5165`, a `select.select`-based
non-blocking readiness check), not `sys.stdin.isatty()` — a separate site the
seam must also route through, not fold into the `isatty()` list.

Both existing modes assume the tool is either talking to a person at the
terminal right now, or talking to no one. Headless operation under `integration`
introduces a third case neither handles: no one is at the terminal, but a
real person is reachable asynchronously. This seed adds that third mode as a
first-class, explicit selection — not a special case layered onto the
`isatty()` idiom — and generalizes the one existing DI pattern
(`review_walk`'s `input_fn`) into a tool-wide seam every prompt site routes
through.

## Architecture

### The seam and its three providers

One entry point, `ask_human(request: HumanInputRequest) -> Resolution`,
backed by a provider selected once per process from an explicit mode — never
re-derived per call, and never read from `isatty()` when the mode is
`remote`. `isatty()` may still choose between `tty` and `absent` when no mode
is set explicitly (today's behavior, preserved). Modes:

- **`tty`** — today's `input()`, unchanged behavior, now called through the
  seam instead of inline.
- **`absent`** — today's auto-degrade-to-default, unchanged behavior, made an
  explicit provider instead of an implicit `isatty()` branch scattered across
  a dozen files.
- **`remote`** — new. Backed by a transport-agnostic protocol; this seed
  ships one transport, filesystem-backed (§ below).

Mode selection: an explicit `PLAN_TOOL_HUMAN_IO` environment variable (`tty`
| `absent` | `remote`), following the existing `PLAN_TOOL_BACKEND`-style
precedent for env-driven mode selection. Exact CLI-flag surface (if any) is
`create`'s call; the seam itself must not infer the mode from `isatty()` when
`PLAN_TOOL_HUMAN_IO` is set.

### Per-site declaration: `prompt_id` and an independent `remote_default`

Every prompt site declares a stable `prompt_id` (e.g. `review-walk.
recommendation`, `jira.epic-key`, `rate-limit.action`, `create.cache-reuse`)
and, separately from whatever default the `absent` mode already uses at that
site, an optional `remote_default`. The two may differ — `absent` mode's
default is tuned for "no one is watching, be conservative"; `remote` mode has
a person reachable, so a site may reasonably want a different default, or
none at all.

**The policy is expressed by presence, not a separate table.** If
`remote_default` is set for a site, `remote` mode applies it automatically
and emits an advisory event recording that it did (never a silent
auto-answer). If unset, `remote` mode blocks and asks. This replaces a
previously-considered separate escalate-vs-degrade policy table with one
field per site — deciding "does this need a human" is deciding whether to
set the field, not maintaining a second data structure.

Every enumerated site (§ In scope) must explicitly declare `remote_default`
one way or the other — including explicitly `None` for "always ask" — as
part of this plan's own site enumeration, per CLAUDE.md's "fix the class,
not the cited spot": the enumeration is this plan's `create`-time
deliverable, not something `detail` discovers site by site.

### The filesystem reference transport

`remote` mode's default transport: write a request record (JSON) to a
configured directory, then poll that directory for a matching resolution
record. This is the transport used by tests and by anyone running `remote`
mode outside a integration container; it has no integration-specific knowledge and proves
the seam end-to-end (request shape, blocking-and-resume, advisory events)
without any external service existing. A later seed adds an HTTP transport
implementing the same provider protocol once integration's API shape is signed off
— this seed's transport abstraction must be shaped so that addition needs no
change to the seam or its callers, only a new transport implementation.

### `--jobs N` is refused, not degraded

`completeness-apply --jobs N>1` already means "no human consulted, Claude
approves everything" (`cli/completeness_phases.py:581,739`). Combining that
with `remote` mode — whose premise is a human *is* reachable — would queue N
concurrent blocking asks against one person, contradicting `--jobs N`'s own
unattended intent. `remote` mode plus `--jobs N>1` must fail fast with an
explicit, actionable error at startup, before any work begins — never
silently fall back to either mode's behavior.

### Request and resolution shape

A `HumanInputRequest` carries: `request_id`, `prompt_id`, `kind` (`confirm` |
`choice` | `text`), `question`, `choices` (for `choice`), `allow_free_text`,
`context` (whatever the call site already has — plan slug, step id, finding
anchors), `remote_default` (if set). A `Resolution` carries: `request_id`,
`value`, optional `free_text`, and `outcome` (`answered` | `default-applied`).
`allow_free_text` matters concretely: the review walk's feedback key takes
prose guidance that gets fed into the next Claude call, and a pure
multiple-choice shape can't carry that.

## In scope

The seam and its type (`plan_tool/human_io.py`, new); the `tty` and `absent`
providers (reshape of existing behavior, not new); the `remote` provider and
its filesystem reference transport; `PLAN_TOOL_HUMAN_IO` mode selection; the
`--jobs N` refusal in `cli/completeness_phases.py`; routing every enumerated
site through the seam with an explicit `prompt_id` + `remote_default`:
`review_walk.py:600` (`walk_recommendations`'s existing `input_fn` injection
becomes a seam call), `cli/jira_cmd.py` (epic wizard `:609-1098`, confirms
`:500,555,772,774`, story menu `:922`), `cli/authoring.py:1240,279,367,446,
2260`, `cli/manifest.py:474,799`, `cli/worktree_cmd.py:301`,
`cli/lessons_cmd.py:216,332`, the rate-limit action prompt
(`shell.py:409`, `launcher.py:548`, both calling `claude_errors.py:1050`
`ask_on_rate_limit_action`), `create.py`'s cache/collision prompts
(`:1864,3329,3454,3645,4089,4526,5263,6904`), its `isatty()` sites
(`:6378,6733,7988,8437`), and its separate `_stdin_has_pending_input()` site
(`:5299`, the check itself at `:5165`), `detail.py`
(`:5707,5739,5926,6300`), `reground.py:286`, `scope_out.py:1492`,
`change_collision.py:353`, `roadmap.py:2523`,
`cli/completeness_phases.py:991`. `TESTING.md`'s invoker-seam neutralization
table (`TESTING.md:64`, rows `:66-84`) gains this seam's entry; `tests/`.

### Scope contract

- **Binary observable, in one sentence:** for a given prompt site and mode,
  either a real answer was obtained (via `input()`, a filesystem resolution
  record, or the site's declared default) or the call blocked waiting for
  one — nothing about whether the answer was *good*, only that the plumbing
  delivered one.
- **Allowed behavior changes:** none for `tty`/`absent` modes (byte-identical
  to today, verified by a regression test per site); `remote` mode and
  `PLAN_TOOL_HUMAN_IO` are new; `remote` + `--jobs N>1` now fails fast
  instead of being unhandled/undefined.
- **Allowed reorganization:** `builtins.input()`/`isatty()` call sites move
  behind the new seam. No other reorganization — do not restructure the CLI
  layering, the invoker seam, or any module boundary beyond adding
  `human_io.py`.
- **Verification:** § Testing below.
- **Stop / defer:** § Deferred, and anything the iteration loop surfaces
  outside this fence goes to `BACKLOG.md` / `BUG_BACKLOG.md`, never applied
  as plan expansion.

## Out of scope

- The HTTP transport and any integration-specific wire format — a separate, later
  seed once integration's API shape is signed off (see
  `.tmp/integration-headless-feedback-bridge.investigation.md` § Sequencing).
- Anything in the `integration` repository.
- Changing what any existing prompt asks, its `tty`-mode wording, or its
  `absent`-mode default value — this is a routing change behind a new seam,
  not a UX change to the two existing modes.
- A separate escalate-vs-degrade policy table — superseded by the per-site
  `remote_default` field (§ Architecture).
- Who may answer a `remote`-mode request, request expiry/timeout policy, and
  first-write-wins resolution semantics — integration-side/transport-level concerns
  (recorded as decided in
  `.tmp/integration-headless-feedback-bridge.investigation.md`) that apply once the
  HTTP transport exists; the filesystem reference transport in this seed has
  a single local reader and no concurrent-answer race to resolve.
- Any change to the Claude invoker seam (`shell.py`, `backend_runner.py`) —
  this seed only adds the analogous seam for humans.

## Risks

- **Incomplete call-site sweep** — a missed `builtins.input()` site would
  hang forever in a headless container with no TTY and no reachable remote
  human. Mitigated by treating the § In scope enumeration as a hard, checked
  deliverable of `create` (grep-verified, per CLAUDE.md's class-sweep rule),
  not best-effort discovery during `detail`.
- **Wrong per-site `remote_default` judgment** — too many sites left to
  "always ask" trains a remote operator to ignore the channel; too many
  silent defaults means the tool makes consequential decisions (destructive
  confirms, conflict resolution) unattended. Mitigated by requiring an
  explicit, reasoned `remote_default` decision per site rather than a bulk
  default, and by always emitting an advisory event when a default fires.
- **`absent`/`tty` regression** — since this is a refactor of load-bearing
  existing behavior, a mis-migrated site could silently change today's
  CLI/CI behavior. Mitigated by a regression test per relocated site proving
  byte-identical behavior in both existing modes.
- **`--jobs N` + `remote` left undefined instead of refused** — would
  produce N concurrent blocking asks against one human with no coordination.
  Mitigated by the explicit fail-fast check at startup (§ Architecture).

## Testing

- **Per-site regression, `tty` mode:** every relocated site still calls
  through to an `input()`-equivalent and returns the same value it does
  today.
- **Per-site regression, `absent` mode:** every relocated site still returns
  its existing default with no behavior change, now via the explicit
  `absent` provider rather than an inline `isatty()` branch.
- **`remote` mode, no `remote_default`:** the seam blocks; a resolution
  record written to the filesystem transport's directory unblocks it with
  the written value.
- **`remote` mode, with `remote_default`:** the seam returns the default
  immediately, with no filesystem write required, and emits the advisory
  event.
- **Mode resolution:** `PLAN_TOOL_HUMAN_IO=remote` is honored even when
  `isatty()` would say otherwise (no TTY-based override once the mode is
  explicit); with no `PLAN_TOOL_HUMAN_IO` set, `isatty()` still selects
  between `tty` and `absent` as today.
- **`--jobs N` refusal:** `remote` mode combined with `completeness-apply
  --jobs N>1` fails immediately with an actionable error, before any gap is
  processed.
- **Seam test discipline:** every test overriding the seam, per the existing
  invoker-seam convention (`TESTING.md`); none exercises a real filesystem
  poll loop live end-to-end without an injected short poll interval.

## Acceptance criteria

- No `builtins.input()` or `sys.stdin.isatty()` call remains outside
  `plan_tool/human_io.py` at any of the enumerated sites.
- `tty` and `absent` modes are behavior-identical to pre-change plan-tool
  for every relocated site.
- `remote` mode, filesystem transport, blocks and resumes correctly with no
  `remote_default` set, and returns the default with an advisory event when
  one is set.
- `remote` mode combined with `--jobs N>1` fails fast with a clear error and
  processes zero gaps.
- Every enumerated site has an explicit, reasoned `remote_default` decision
  recorded (a value, or explicitly "always ask").
- `TESTING.md`'s invoker-neutralization table documents the new seam.
- `BACKLOG.md` #321 is updated to reflect this plan's authoring (per
  CLAUDE.md's backlog-derived-seed convention) once the plan ships.

## Deferred

- The HTTP transport talking to integration, once integration's API shape is signed off —
  own seed.
- Request expiry/timeout policy, who-may-answer, and first-write-wins
  resolution semantics — apply once a multi-reader transport (HTTP) exists;
  not needed for the single-reader filesystem transport this seed ships.
- Any CLI-flag surface for choosing `PLAN_TOOL_HUMAN_IO` beyond the
  environment variable, if real operator demand emerges.
- Extending `remote_default` policy to be settable per-run rather than only
  per-prompt-site (e.g. "always ask this run regardless of site defaults"),
  if real operator demand emerges.
