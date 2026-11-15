# Bug backlog drain: standing pickup

Use this handoff to drain `BUG_BACKLOG.md` one entry at a time. It records the
procedure and its fence, not a queue override: `BUG_BACKLOG.md` owns the
entries and [`docs/TRACKING.md`](../docs/TRACKING.md) owns the labels and
promotion rules. Delete this file when the drain route is retired; per
[`README.md`](README.md) § Retention, anything durable moves to its canonical
home first.

## Queue order

1. `BUG`, then `RISK`, then `MINOR`, top to bottom within a section.
2. Skip an entry that carries only `- **Promoted:** <key>`: its Jira ticket
   holds the brief.
3. Skip the `## ROADMAP` section: it is owner-tracked and not part of the
   drain.
4. This handoff drains `BUG_BACKLOG.md` only. Ordering across files, and
   Jira promotion, are the lead's call (`docs/TRACKING.md`).
5. Take an entry only when its Route is `direct` and its Readiness is `ready`
   (labels: `docs/TRACKING.md` § "Labels every entry carries"). Surface every
   other entry to the user instead of picking it up: `Route: plan` (use
   `plan-tool`) and any other Readiness (`decision-needed`, `evidence-gated`,
   `blocked-on #N`, `parked`).
6. An entry with no Route or Readiness label: read it, map an older
   `Approach:` tag per TRACKING, label it, and take it only if the result is
   `direct` + `ready`.

## Per-entry procedure

1. **Confirm the claim against tests before editing.** Read the test module
   covering the target code (`plan_tool/X.py` → `tests/test_X.py`). A passing
   test that pins the current behavior outranks a plausible static diagnosis.
   If the claim is refuted, report that with the evidence and do not fix.
2. **Name the defect class in one sentence, then enumerate sites** by
   identifier and by vocabulary before editing any of them. Apply at every
   site, or say per site why it stays.
3. **State the property the fix must produce**, then trace the mechanic
   against the common input, not only the edge case. Make the smallest change
   that makes the entry true.
4. **Add regression coverage that fails under the prior behavior** and name
   the test for the invariant it pins. Verify by mutation: break the fix and
   watch the test go red.
5. **Run focused tests, then the full suite**
   (`uv run pytest tests/ -q -n auto`, in the background with a named log under
   `.tmp/`, prefixed `set -o pipefail &&` when piped). A red sibling test
   during a class-wide fix is expected; read each one to decide carve-out or
   missed site.
6. **Review the complete diff** for sibling call sites, docs, and error
   outcomes the fix implies. Run `/code-review` at `high` after committing, and
   stop under `CLAUDE.md` § "Severity-aware conceptual-audit stopping rule":
   two consecutive low-yield passes (`handoffs/README.md` § Retention defines
   converged), or one of its three exits.
7. **Remove only the fulfilled entry** (or its promotion stub) and any obsolete
   references. Do not describe a retired risk as fixed; a retirement is
   recorded in
   [`docs/history/backlog-decisions.md`](../docs/history/backlog-decisions.md)
   with its re-open condition.
8. **Commit one bounded concern per commit**: the fix and its tests in one,
   the backlog removal in another when they are independent. Pushing or opening
   a PR needs a separate go-ahead.

## Stop conditions

- The same finding resurfaces across review rounds, or a fix needs structural
  rework that cannot land inline: stop and surface it to the user, or file it
  in `BUG_BACKLOG.md` / `BACKLOG.md`.
- A fix would touch an unrelated concern: file a backlog entry instead of
  folding it in.
- A scope or design decision appears: surface it to the user rather than
  self-adjudicating.

## Session log

Record each drained entry as one dated line: entry heading, disposition
(`fixed <commit>`, `refuted <evidence>`, `declined <reason>`,
`tracked <backlog id>`, or `pending`), and the commit that removed the entry.
A change that goes through a review loop keeps its pass-by-pass record in its
own ledger (`handoffs/README.md` § "Review ledgers"); the line here points to it.
Drop a `fixed` line once its change has merged to `main`, and a `refuted`,
`declined`, or `tracked` line once its evidence lives in `BUG_BACKLOG.md`,
`BACKLOG.md`, or `docs/history/backlog-decisions.md`; keep `pending` lines until
they resolve.

- 2026-11-13 — `create --from-existing` records `source_seed` as the seed it
  then archives (`BUG_BACKLOG.md`, BUG section): `pending`, narrowed to the
  roadmap-published case and `evidence-gated`. A one-step throwaway run at
  plan-tool 1.3.1 did not reproduce the HIGH for a plain `plan-seeds/` seed
  (`source_seed` stayed `plan-seeds/greeter.md` after the move to
  `plan-seeds/archive/`; the audit still read the seed and raised no finding
  about the path). The roadmap-published case (`plan-seed-drafts/`) is
  **untested**. Existing test
  `test_source_seed_survives_the_cli_archiving_its_own_seed` pins the recorded
  pre-archival path. The same run filed a second entry (the audit emitted a
  "no gap here" confirmation as a blocking medium finding), `evidence-gated`.
- 2026-11-13 — `create --from-existing` crashes with "concept scope contains
  duplicate IDs" (`BUG_BACKLOG.md`, BUG section): `pending`, narrowed to
  `evidence-gated`. Not reproduced at 1.3.1 with the entry's nine-heading seed
  and a stubbed distill; the original distill response is not retained. No
  code or test change: the scratch test was discarded because it could not be
  shown to fail under the old behavior. A repeated non-canonical heading in a
  direct-ready seed did crash with the same message; `create` now refuses it
  with the headings named (PR #199, merged 2026-11-13).

- 2026-11-13 — the loop-termination lists in `RUNBOOK.md` and `docs/ITERATION.md`
  omit the `no_progress` and `no_blocking_findings` stops: `fixed c8bd15643`,
  entry removed in `ea5396a14`. `docs/ITERATION.md` § "How the loop terminates"
  now lists every `should_continue` reason with its code, per-command scope and
  exit codes, pinned by a drift test. Pass-by-pass record and closure (stopped at
  exit 2); the pass-by-pass record was retired 2026-11-13.

- 2026-11-15 — `completeness_report.py` kept `WHY["open"]` and `_HEADINGS["open"]`,
  which no report path renders: `fixed ed32f3f77`, entry removed in `0805402b8`.
  `deferred_kind` still returns `open` (the loop's deferral summary counts it).
- 2026-11-15 — `--accept`'s clean-tree check misread quoted and renamed paths:
  `fixed 3ab6d153f`, entry removed in `6d5001351`. It now reads `git status -z`
  from the git top level, so spaces, non-ASCII names, renames and a nested
  project root match.
- 2026-11-15 — the post-commit clean check on paths git keeps reporting as
  modified: `fixed ae5956a9c` for untracked content in a committed submodule;
  the filter-modified half is retired by design (record in
  `docs/history/backlog-decisions.md`). Entry removed in `cfd3b2ed7`.
- 2026-11-15 — `create --from-existing` read seed sections without stripping
  frontmatter: `fixed cc09f31ad`, entry removed in `67f8947be`. Seven readers,
  one test each, plus a test for the distill gate that had none. Two further
  readers stay unstripped on purpose (the distiller's own output, the tool's
  rendered plan body); each says so in a comment.
- 2026-11-15 — run IDs collided within a second (24-bit tail): `fixed 49ff32c94`,
  entry removed in `e9c43949b`. The tail is `token_hex(8)`; a deterministic test
  replaces the sampling one.
- 2026-11-15 — `CLAUDE.md`, `TESTING.md` and backlog #190 cited the missing
  `prompts/reconcile.md`: `fixed 3d35705c5`, entry removed in `fe72a5791`. The
  `CLAUDE.md` edit is architect-tier (its own header): it needs review in the
  pull request. `lessons/general.md` still names the old path as a record of
  past plans and is left alone.
- 2026-11-15 — out-of-tree detail archive writes: `pending`, narrowed to
  `detail --split` renames and `evidence-gated` (`detail --force` never writes
  outside `plan-details/<slug>/`; none of 1,033 declared pointers is out of
  tree).
- 2026-11-15 — four live seeds refused for `## References`: `fixed 18438c1a9`
  for `roadmap-revision-retention.md` and the carved intent seed; the two
  impact-recurrence seeds described a design closed on 2026-08-11 and were
  deleted (`0038319ae`, owner decision, recorded in `backlog-decisions.md`).
- 2026-11-15 — the tracked `.claude/skills/plan-tool/` copy had drifted 87 lines
  from `integrations/`: untracked and ignored (`e12e7e019`, owner decision,
  recorded in `backlog-decisions.md`).
- 2026-11-15 — review of the drain branch, closed as converged (three
  consecutive low-yield passes; every finding low or nit). Pass 1: eight
  findings, three refuted with evidence, two declined, three fixed in `20e85619d`.
  Pass 2: eight findings, five repeats or declines, two fixed
  (`find_dropped_references` also strips echoed frontmatter; the `open` comment
  says only what was verified). Pass 3, over the range plus the two decision
  commits: seven findings, five repeats or declines, two fixed (the two `open`
  comments agree and name `_render_grouped_report`; the example run ID in the
  `runs` help, `RUNBOOK.md` and `commands.md` has the current shape). Declined
  every time: `unexpected_dirty_paths` and the post-commit check treat
  submodules differently on purpose (one asks "clean before I start?", the other
  "did the commit absorb what it could?").

## Deliberately not in this handoff

- A snapshot of the current queue: it goes stale on the next drain, so read
  `BUG_BACKLOG.md` at the start of each session.
- Roadmap-owned entries and Jira promotion: the lead owns both.
- New concurrency or parallel fan-out to speed the drain: the tool is serial by
  design.
