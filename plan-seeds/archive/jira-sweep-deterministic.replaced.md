> **Replaced**: this file has been superseded by `docs/implementation-plans/2-jira-sweep-deterministic.md`.
> Preserved here for history; do not edit.

# Plan seed: deterministic jira-sweep — link plan stories to live Jira via `jira-cli`

This file is a `plan-tool create` input. Use it via:

```
plan-tool create jira-sweep-deterministic --from-existing plan-seeds/jira-sweep-deterministic.md --iterate
```

> **Source and lifecycle.** Implements BACKLOG **#142** and inherits its full
> scope contract, including its sharpened boundary: the sweep **surfaces**
> divergence and never resolves it by writing either side. Supersedes
> `docs/implementation-plans/2-jira-sweep-integration.md` (`status: planning`,
> never executed) — archive that plan when this one lands; no work is lost.
> **#143** consumes this sweep's divergence list as its input and is not in
> scope here. The final docs/status step must reconcile `BACKLOG.md` #142:
> mark it plan-authored while execution is pending, remove it only after this
> ships, and note that #143 still depends on the artifact. Out-of-scope
> findings route to the backlog files, never into this plan.

---

## Overview

`plan-tool sweep` archives completed plans but cannot tell whether a plan's
exported Jira stories are actually closed. That readiness signal lives today
in a separate JS workflow (`scripts/jira-plan-sweep/` in
`example-app-amplify`) that re-implements parsing plan-tool already owns.

This effort folds it in as `plan-tool jira-sweep` — three subcommands,
**zero Claude calls**, keyed on an exact join rather than title similarity.

When it ships: `jira-sweep collect` writes the candidate set, `jira-sweep
check` fetches live Jira state through the user's own `jira-cli`, and
`jira-sweep report` writes a readiness report naming matched, unmatched, and
divergent stories. Nothing writes to Jira, and nothing writes local story
state.

## Problem statement

Two failures make the existing approach untrustworthy, both observed rather
than theorized.

**Title-matching produces false verdicts.** `AIHARD-S32` reported "unmatched"
purely because its Jira summary was reworded, while `PS-175` still carried
the exact `[AIHARD-S32]` bracket token and was `Done`. Reconciliation built
on title similarity misses real drift and invents fake drift.

**An LLM is the wrong transport.** The superseded plan routed the live query
through a `claude -p` call so it could reach Atlassian MCP tools. No judgment
happens in that call — it runs a fixed JQL and returns rows. It buys
non-determinism, token cost, and (per #142) a response large enough to blow
the budget on default fields, in exchange for nothing. The output drives an
**archive decision**, where a hallucinated status or a dropped page silently
archives live work.

## Architecture

**Transport: the user's `jira-cli`, not an HTTP client and not Claude.**
`jira-cli` (`jira` on PATH, <https://github.com/ankitpokhrel/jira-cli>) owns
auth entirely; plan-tool never sees, stores, or prompts for a credential.
When the binary is absent, every subcommand that needs it fails with an
actionable message naming the releases URL — never a stack trace, never a
silent skip. Projects are **company-managed Jira Cloud**; epic children
resolve via `parent = <epicKey>`.

**The join key, in priority order.** This is the effort's core decision.

1. **`Story.jira_issue_key`** when recorded — exact, unambiguous.
2. **The `[<PREFIX>-S<NN>]` bracket token** in the Jira summary — automatic
   and retroactive, since plan-tool renders it into every exported title.
   This covers every ticket created before `jira_issue_key` existed.
3. **The plan tag** disambiguates a token collision. #142 observed
   `VNDSFTP-S19` matching both `PS-115` and `PS-226`, reproduced across two
   independent passes; a summary carrying `[VNDSFTP-S19] [SSO]` resolves it.

A story that survives all three unresolved is reported **unknown**. There is
no similarity scoring anywhere — that is the one place judgment could
re-enter, and it stays out.

**Done-ness reads `statusCategory`, not status name.** Status names are
per-project configurable (`Done` / `Closed` / `Released`); the category key
is the stable API-level grouping. Matching on names would silently
misclassify any project with a custom workflow.

**Layering.** A cycle-free leaf owns the sweep logic and the `jira-cli`
seam; a thin `cli/` module wires the three subcommands. The leaf reuses
`jira.py`'s real parsers, `jira_config.py`'s epic resolution, and
`locator.py`'s manifest access rather than re-deriving any of them.

**Seam discipline.** The `jira-cli` call goes through an injectable invoker
in `shell.py`'s `shell_*_invoker` family, per `TESTING.md`. Its output schema
is pinned by a contract doc plus fixtures, following the shape already
established by `docs/CODEX_CLI_CONTRACT.md` + `tests/fixtures/codex/`.

**Close the spawn gate.** `tests/conftest.py`'s autouse gate blocks only
`registered_binaries()` — the LLM backends. A `jira` subprocess is currently
unblocked, so a stubbing mistake would query a real Jira project from the
test suite. The gate must cover the `jira` binary too.

## Out of scope

- **Writing to Jira.** No transitions, no edits, no creates. Read-only.
- **Writing local story state.** No `export_state` flip from Jira status, no
  `--apply-story-status`. A by-hand version of exactly this got **24 of 29
  divergent stories wrong**, including flipping two to `done` whose
  eligibility checks were disabled in production. Jira is canonical for the
  *ticket*; a ticket's status is not evidence about the *code*. Do not
  reintroduce this — it is the reason #142 carries its scope boundary.
- **Arbitrating divergence** — which side is true is **#143**, downstream.
- **Auth, config, or credential handling** of any kind.
- **Archiving plans.** `sweep` still decides that; this only informs it.
- **Changing the jira export format**, `Story`, or `JIRA_FORMAT.md`.
- **Re-querying from `reconcile` / `verify`.** Persisting the artifact for
  them to consume is in scope; wiring them to it is not.

## Risks

- **`jira-cli` output schema drift** across versions — mitigated by the
  pinned contract doc + fixtures, and by requesting minimal fields
  (`key`, `summary`, `status`) rather than defaults.
- **Pagination** past the first page silently truncating a large epic, which
  reads as "story not in Jira." Paging is a correctness requirement, not an
  optimization.
- **Token collisions beyond the plan-tag tiebreak** — report as `unknown`
  rather than picking one.
- **A recorded `jira_issue_key` pointing outside the configured epic** (a
  moved ticket) — report it, do not treat it as unmatched.

## Testing

Fixture-driven against captured `jira-cli` output; no network, no live Jira.
Cover: each join tier and its precedence, the observed collision, an absent
binary, a paged response, a custom-named done status, and a story with no
key and no token.

## Acceptance criteria

- The three subcommands run end to end with **no backend invocation**; the
  suite proves it via the spawn gate, now covering `jira`.
- A story whose Jira summary was reworded still matches by bracket token.
- The `VNDSFTP-S19`-shaped collision resolves via plan tag, or reports
  `unknown` — never picks arbitrarily.
- A done-category issue under a custom status name is classified done.
- A missing `jira` binary produces an actionable install message naming the
  releases URL, and exits non-zero as failure-to-complete.
- No command mutates a plan, a jira-stories export, or a Jira issue.
- `BACKLOG.md` #142 is reconciled, with #143's dependency on the artifact
  preserved.

## Deferred

- Divergence arbitration (**#143**).
- `reconcile` / `verify` consuming the persisted mapping.
- Team-managed project support (`parent` semantics differ).
