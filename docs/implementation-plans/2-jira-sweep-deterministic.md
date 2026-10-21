---
title: Jira Sweep Deterministic
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Pin the jira-cli output contract in docs/JIRA_CLI_CONTRACT.md with captured
    fixtures
  creates:
  - docs/JIRA_CLI_CONTRACT.md
  - tests/fixtures/jira_cli/issue-list-single-page.json
  - tests/fixtures/jira_cli/issue-list-paged.json
  - tests/fixtures/jira_cli/issue-list-custom-done-status.json
  complexity: medium
  change_type: non-code
  status: current
- id: 2
  title: Block the jira binary in the test-suite spawn gate in tests/conftest.py
  files:
  - tests/conftest.py
  creates:
  - tests/test_spawn_gate.py
  complexity: low
  change_type: feature
- id: 3
  title: Add the jira-cli transport leaf plan_tool/jira_cli.py with an injectable
    invoker, minimal-field queries, pagination, and an actionable absent-binary error
  creates:
  - plan_tool/jira_cli.py
  - tests/test_jira_cli.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
- id: 4
  title: 'Add jira-sweep collect: build the candidate story set from the manifest
    and jira-stories exports and write it under .plan-tool/jira-sweep/'
  creates:
  - plan_tool/jira_sweep.py
  - tests/test_jira_sweep.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
- id: 5
  title: Implement the three-tier join and divergence classification in plan_tool/jira_sweep.py
  files:
  - plan_tool/jira_sweep.py
  - tests/test_jira_sweep.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
- id: 6
  title: 'Add jira-sweep check: fetch live epic children through the jira-cli transport
    and persist the fetched state'
  files:
  - plan_tool/jira_sweep.py
  - tests/test_jira_sweep.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 4
- id: 7
  title: 'Add jira-sweep report: write the readiness report naming matched, unmatched,
    divergent, and unknown stories'
  files:
  - plan_tool/jira_sweep.py
  - tests/test_jira_sweep.py
  complexity: low
  change_type: feature
  depends_on:
  - 5
  - 6
- id: 8
  title: Wire the jira-sweep command group into the CLI with collect, check, and report
    subcommands
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - tests/cli/package_surface_help.golden.txt
  - docs/cli/README.md
  creates:
  - plan_tool/cli/jira_sweep_cmd.py
  - tests/cli/test_jira_sweep_cmds.py
  - docs/cli/jira-sweep.md
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  - 6
  - 7
- id: 9
  title: 'Reconcile docs and status: CAPABILITIES.md entry, TESTING.md seam row, BACKLOG.md
    #142, and archive the superseded jira-sweep-integration plan'
  files:
  - CAPABILITIES.md
  - TESTING.md
  - CLAUDE.md
  - BACKLOG.md
  - docs/implementation-plans/2-jira-sweep-integration.md
  - .plan-tool/plans.json
  complexity: medium
  change_type: non-code
  depends_on:
  - 8
---
# Jira Sweep Deterministic

## Overview

This plan adds `plan-tool jira-sweep`, a read-only command group (`collect`, `check`, `report`) that tells whether a plan's exported Jira stories are actually closed, so `sweep`'s archive decision stops guessing. It makes zero Claude calls: live Jira state comes through the user's own `jira-cli` binary behind an injectable invoker, and stories match on an exact three-tier join (`Story.jira_issue_key`, then the `[<PREFIX>-S<NN>]` bracket token in the Jira summary, then the plan tag as tiebreak) — never title similarity. Done-ness reads the stable `statusCategory` key rather than per-project status names, and a story no tier resolves is reported `unknown` instead of guessed. Nothing writes to Jira or to local story state; commands exit non-zero only on failure-to-complete (including an absent `jira` binary, which fails with an actionable message naming the releases URL), never on findings.

## Problem statement

The `jira` export is a one-way handoff: `plan_tool/jira.py` writes stories and records the handoff on each story (`export_state`, `jira_issue_key`), but nothing ever reads back what happened to those issues in Jira. Every downstream decision that depends on that answer — chiefly `manifest sweep`'s archive decision — has to guess: an exported plan looks "handed off" whether its stories are closed, still in progress, or were never created in Jira at all. The user-visible symptom is a sweep that either archives a plan whose Jira work is still live or leaves a fully-closed plan lingering in the manifest, with no command that can say which.

Closing that gap by hand means opening Jira and eyeballing issue summaries against exported stories — unrecorded, unrepeatable, and wrong exactly when it matters: when summaries have drifted from story titles, or a project's custom workflow uses status names a human misreads as done. The tool has no read-only, deterministic surface that joins the local export record to live Jira state and reports, per story, matched / divergent / unknown — that is the surface this plan adds.

**Two measurements from the 2026-07-17 manual dry run (BACKLOG #142/#143) fix design decisions here; do not re-litigate them.** First, title-similarity matching produces false verdicts in both directions: `AIHARD-S32` was reported "unmatched" purely because its Jira summary had been reworded, while `PS-175` still carried the exact `[AIHARD-S32]` bracket token and was `Done`. That is why the join is exact and tiered, and why no similarity scoring appears anywhere. Second, a code-blind sync that trusted Jira's `Done` and overwrote local markers to match was **wrong for 24 of 29 divergent stories**, including endorsing two production regressions as shipped work. That is why this sweep reports and never writes — see Out of scope.

## Architecture

**Transport: the user's `jira-cli`, not an HTTP client and not Claude.** The `jira` binary on PATH owns auth entirely — plan-tool never sees, stores, or prompts for a credential — and the sweep spends zero Claude calls, because no judgment happens in the live query: it runs a fixed JQL and returns rows. When the binary is absent, every subcommand that needs it fails with an actionable message naming the jira-cli releases URL — never a stack trace, never a silent skip. Target projects are company-managed Jira Cloud; epic children resolve via `parent = <epicKey>`.

**Two cycle-free leaves plus a thin CLI wire.** `plan_tool/jira_cli.py` is the transport leaf: it owns the subprocess seam (an injectable invoker in the `shell_*_invoker` family, per `TESTING.md`), minimal-field queries (`key`, `summary`, `status` — not defaults), and pagination, which is a correctness requirement rather than an optimization (a silently truncated page reads as "story not in Jira"). `plan_tool/jira_sweep.py` is the logic leaf: collect, the three-tier join, divergence classification, and the report. It reuses `jira.py`'s real parsers, `jira_config.py`'s epic resolution, and `locator.py`'s manifest access rather than re-deriving any of them. `plan_tool/cli/jira_sweep_cmd.py` is thin command wiring only, matching the CLI layering rule. Sweep state persists under `.plan-tool/jira-sweep/` so `collect`, `check`, and `report` compose as separate runs and the artifact outlives the session.

**The join key, in priority order — the effort's core decision.** (1) `Story.jira_issue_key` when recorded — exact and unambiguous. (2) The `[<PREFIX>-S<NN>]` bracket token in the Jira summary — automatic and retroactive, since plan-tool renders it into every exported title, covering tickets created before `jira_issue_key` existed. (3) The plan tag as tiebreak for a token collision — collisions are observed, not hypothetical: `VNDSFTP-S19` matched both `PS-115` ("Vendor SSO") and `PS-226` ("CourseCardData mapper"), reproduced identically across two independent dry-run passes, which is what tier 3 exists to resolve. A story that survives all three unresolved is reported `unknown`. There is no similarity scoring anywhere — that is the one place judgment could re-enter, and it stays out.

**Done-ness reads `statusCategory`, not status name.** Status names are per-project configurable (`Done` / `Closed` / `Released`); the category key is the stable API-level grouping. Matching on names would silently misclassify any project with a custom workflow.

**Seam discipline and the closed spawn gate.** The `jira-cli` output schema is pinned by a contract doc (`docs/JIRA_CLI_CONTRACT.md`) plus captured fixtures, following the shape established by `docs/reference/contracts/codex-cli.md` + `tests/fixtures/codex/`, so schema drift across jira-cli versions surfaces as a fixture mismatch rather than a silent misparse. `tests/conftest.py`'s autouse spawn gate currently blocks only the registered LLM backend binaries; this plan extends it to the `jira` binary, so a stubbing mistake in a test can never query a real Jira project.

## References

- [jira-cli (ankitpokhrel/jira-cli) — README and usage referencehttps: — Authoritative guide to the `jira` binary's commands and flags (`issue list`, `--jql`, `--plain`, `--columns`, `--no-headers`, pagination flags) that the sweep's injectable invoker will shell out to and whose output the contract doc must pin.
- [jira-cli Releaseshttps: — The releases URL the plan requires the missing-binary error message to name, and the source for pinning which jira-cli version the output-schema contract and fixtures are captured against.
- [Jira Cloud platform REST API — Issue search (JQL)https: — Official reference for the JQL search endpoint underlying jira-cli queries, including `fields` selection (key, summary, status) and `nextPageToken`-based pagination semantics the paging correctness requirement depends on.
- [JQL fields reference — Jira Cloudhttps: — Atlassian's canonical JQL field catalog documenting `parent = <epicKey>` for resolving company-managed epic children and the `statusCategory` field used for done-ness classification.
- [Jira Cloud platform REST API — Workflow status categorieshttps: — Reference for the stable statusCategory keys and their mapping to configurable per-project status names, which the sweep reads instead of status names to classify custom workflows correctly.
- [Python 3 standard library — subprocesshttps: — Reference for spawning the `jira` binary through the invoker seam, including FileNotFoundError handling for the absent-binary path and capturing stdout/stderr deterministically.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Writing to Jira** — no issue creation, transition, comment, or close; the sweep is strictly read-only against live Jira state.
- **Mutating local story state** — `export_state` / `jira_issue_key` on exported stories stay untouched; sweep output lands only under `.plan-tool/jira-sweep/`. **No `--apply-story-status` flag, in any form.** The superseded `2-jira-sweep-integration.md` proposed one; the 2026-07-17 dry run measured what it does — wrong for 24 of 29 divergent stories, including flipping two to `done` whose eligibility checks were disabled in production. Jira is canonical for the *ticket*; a ticket's status is not evidence about the *code*. Audits must not re-propose this as a convenience: adjudicating divergence is BACKLOG #143, which reads code as the third record.
- **Automating `manifest sweep`'s archive decision** — this plan produces the readiness report; wiring `sweep` to consume it is follow-up work.
- **Title-similarity or fuzzy matching** — the three-tier join is exact by design; unresolved stories report `unknown` rather than a scored guess.
- **A direct HTTP Jira client or credential handling** — the user's `jira-cli` binary owns transport and auth; plan-tool never sees a credential.
- **Installing or vendoring `jira-cli`** — an absent binary fails with an actionable message naming the releases URL; the tool never installs it.
- **Team-managed (next-gen) Jira project support** — targets are company-managed Jira Cloud, where epic children resolve via `parent = <epicKey>`.
- **Claude-invoked judgment anywhere in the sweep** — collect, join, done-ness classification, and reporting are all deterministic; zero Claude calls.

## Risks

- **jira-cli output schema drifts across versions** — a newer binary changes field names or paging shape and the transport misparses live rows (high: wrong rows silently become wrong verdicts). Mitigated by the pinned contract doc plus captured fixtures, so drift surfaces as a fixture mismatch. Unresolved gap: fixtures detect drift only when re-captured against the newer binary; the contract names the pinned version so an operator can tell which side moved.
- **Silent pagination truncation** — a truncated result page reads as "story not in Jira" and a live story is reported unmatched (high: the exact failure that corrupts the archive decision). Mitigated by treating pagination as a correctness requirement in the transport leaf, with a paged fixture pinning the behavior.
- **Join misses on legacy or edited summaries** — a story exported before `jira_issue_key` existed whose summary was hand-edited loses its `[<PREFIX>-S<NN>]` bracket token and no tier resolves it (medium). Mitigated by design: the story reports `unknown` rather than a scored guess. Accepted residual: such stories stay `unknown` until an operator records the issue key; the sweep never infers it.
- **Custom workflow status names misread as done/not-done** — per-project names (`Released`, `Closed`) don't map to a human's or a name-matcher's notion of done (medium). Mitigated by classifying on the stable `statusCategory` key, never on status names.
- **A test stubbing mistake queries a real Jira project** — a missed invoker override in a test spawns the real `jira` binary against live data (medium: nondeterministic tests, real credentials exercised). Mitigated by extending `tests/conftest.py`'s autouse spawn gate to block the `jira` binary, mirroring the LLM-backend gate.
- **Team-managed (next-gen) project queried anyway** — `parent = <epicKey>` child resolution assumes company-managed Jira Cloud; against a team-managed project the child set can come back wrong or empty and read as "nothing exported was created" (medium). Mitigation is the declared scope fence only. Unresolved gap: the sweep cannot detect project type, so a wrong-project-type run is indistinguishable from a genuinely empty epic.
- **Stale persisted sweep state read as current** — `collect`, `check`, and `report` compose as separate runs over `.plan-tool/jira-sweep/`, so a report can render a `check` snapshot that predates recent Jira movement (low). Unresolved gap: no freshness gate; the report should carry the fetch provenance so the operator can judge staleness, but nothing blocks reporting over an old snapshot.
- **jira-cli failures beyond the absent binary** — auth expiry, network errors, or a bad JQL surface as a nonzero subprocess exit rather than a missing binary (low). Mitigated partially: the absent-binary path gets the actionable releases-URL message; other failures fail-to-complete with the captured stderr, never a silent skip or a fabricated verdict.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.
- step 8 (feature) — tests covering the behavior this step changes; green before completion.
- step 9 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- `docs/JIRA_CLI_CONTRACT.md` exists, names the pinned jira-cli version its schema was captured against, and pins the `issue list` output shape; the three fixtures (`tests/fixtures/jira_cli/issue-list-single-page.json`, `issue-list-paged.json`, `issue-list-custom-done-status.json`) are captured output conforming to that contract.
- `tests/conftest.py`'s autouse spawn gate raises when any test spawns the `jira` binary without opting out, and `tests/test_spawn_gate.py` proves both the block and the existing LLM-backend gate still fires.
- `plan_tool/jira_cli.py` accepts an injectable invoker in the `shell_*_invoker` family; `tests/test_jira_cli.py` exercises it entirely through stub invokers with no subprocess spawned.
- The transport requests only `key`, `summary`, and `status` fields and follows pagination to exhaustion: `tests/test_jira_cli.py` proves the paged fixture yields the union of all pages, not the first page.
- With no `jira` binary on PATH, any subcommand needing it exits non-zero with a message naming https://github.com/ankitpokhrel/jira-cli/releases — no stack trace; other jira-cli failures (nonzero exit) fail-to-complete with the captured stderr, never a fabricated verdict.
- `plan-tool jira-sweep collect <name>` exits 0 and writes the candidate story set under `.plan-tool/jira-sweep/`, built from the manifest and jira-stories exports; it neither reads live Jira nor mutates story `export_state`/`jira_issue_key`.
- The join resolves in exactly the order `Story.jira_issue_key` → `[<PREFIX>-S<NN>]` summary bracket token → plan tag tiebreak; `tests/test_jira_sweep.py` covers each tier, a token collision resolved by the tag, and a story no tier resolves reporting `unknown` — no similarity scoring exists in the module.
- Done-ness classification reads the Jira `statusCategory` key, never status names: a fixture-driven test classifies a custom-workflow status name (e.g. `Released`) correctly by its category.
- `plan-tool jira-sweep check <name>` fetches epic children via `parent = <epicKey>` through the transport leaf and persists the fetched state under `.plan-tool/jira-sweep/` with fetch provenance.
- `plan-tool jira-sweep report <name>` renders every collected story as exactly one of matched, unmatched, divergent, or unknown, and exits 0 even when divergent/unknown stories are present (non-zero only on failure-to-complete).
- `plan-tool jira-sweep --help` lists `collect`, `check`, and `report`; `plan_tool/cli/jira_sweep_cmd.py` is thin wiring only, `tests/cli/package_surface_help.golden.txt` and the generated `docs/cli/` reference are updated, and `tests/cli/test_jira_sweep_cmds.py` is green.
- No code path in `plan_tool/jira_cli.py` or `plan_tool/jira_sweep.py` invokes a Claude/LLM backend, and no path writes to Jira.
- Docs and status are reconciled: `CAPABILITIES.md` gains the jira-sweep entry (green under `plan-tool validate`), `TESTING.md` gains the jira invoker seam row, `BACKLOG.md` #142 is updated, and `docs/implementation-plans/2-jira-sweep-integration.md` is archived with `.plan-tool/plans.json` updated.
- `uv run pytest tests/ -q` passes with all of the above landed.

## Deferred

- **`manifest sweep` consuming the readiness report** — this plan stops at producing the report; wiring the archive decision to read it is a separate effort (the same fence `## Out of scope` states).
- **Freshness gate on persisted sweep state** — the `check` snapshot carries fetch provenance so an operator can judge staleness, but nothing blocks `report` over an old snapshot; a blocking staleness policy is postponed until one is decided.
- **Detecting team-managed (next-gen) projects** — the sweep cannot distinguish a wrong-project-type run from a genuinely empty epic; detection is deferred pending a reliable project-type signal, leaving the declared scope fence as the only guard.
- **Fixture re-capture workflow across jira-cli versions** — schema drift surfaces only when fixtures are re-captured against a newer binary; a re-capture recipe or automation is a separate concern beyond pinning the contract.
