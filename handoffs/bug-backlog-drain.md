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
4. An entry with a `Priority` line (for example, "blocks the next Integration
   proposal") goes first within its section.
5. Prefer `Route: direct` + `Readiness: ready`. Treat these as not drain work:
   `Route: plan` (use `plan-tool`), `decision-needed`, `evidence-gated`, and
   `needs investigation`. Surface them to the user instead of picking them up.

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
   iterate until a round is clean or low-yield.
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

Record each drained entry here as one line: entry heading, disposition
(`fixed <commit>`, `refuted <evidence>`, `declined <reason>`,
`tracked <backlog id>`, or `pending`), and the commit that removed the entry.

- `create --from-existing` records `source_seed` as the seed it then archives
  (`BUG_BACKLOG.md`, BUG section) — `pending`. Plain `plan-seeds/` case run
  2026-11-13 in a throwaway repo (one `create`, one single-pass bare audit):
  `source_seed` stayed `plan-seeds/greeter.md` after the seed moved to
  `plan-seeds/archive/`; the audit still read the seed (`source_seed_digest` set)
  and raised no finding about the path. Not reproduced for the plain case.
  The roadmap-published case (`plan-seed-drafts/`) is **untested**, so the
  entry stays, narrowed to that case and marked `evidence-gated`. A second
  entry (audit emits a "no gap here" confirmation as a blocking medium
  finding) was filed `evidence-gated` from the same run. Log:
  `.tmp/source-seed-archive-repro.run4.log`. Existing test
  `test_source_seed_survives_the_cli_archiving_its_own_seed` pins the
  recorded pre-archival path.
- `create --from-existing` crashes with "concept scope contains duplicate IDs"
  (`BUG_BACKLOG.md`, BUG section) — `pending`, narrowed to `evidence-gated`
  2026-11-13. Not reproduced at 1.3.1 with the entry's nine-heading seed and a
  stubbed distill; the original distill response is not retained. No code or
  test change: the scratch test was discarded because it could not be shown to
  fail under the old behavior.

## Deliberately not in this handoff

- A snapshot of the current queue: it goes stale on the next drain, so read
  `BUG_BACKLOG.md` at the start of each session.
- Roadmap-owned entries and Jira promotion: the lead owns both.
- New concurrency or parallel fan-out to speed the drain: the tool is serial by
  design.
