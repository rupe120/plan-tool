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

- 2026-11-13 — `detail` raises a bare `ValueError` on a plan body that has a
  heading normalizing to empty (`## :`, `## .`): `fixed b1b935f56`, entry removed in
  `ae7a03808`. The detection and refusal text now live in one place,
  `empty_concept_headings_message` in `plan_tool/concept_bootstrap.py`; `create`
  (same message as before), `detail` (`derive_candidate_buckets` raises
  `DetailError`) and the `scope-review` legacy full-tree route (warns and
  returns the invalid-state exit, writing nothing) each raise it through their
  own error path. Probed first: the legacy route raised the bare error at
  command level, and the flat decision-record route already worked with such a
  body (returned 0), so the refusal is deliberately not applied there and a test
  pins that. Tests: 10 new across `tests/test_concept_bootstrap.py`,
  `tests/test_detail.py` and `tests/cli/test_scope_review_cmd.py`; before the
  fix exactly the three refusal tests failed with the bare error. Mutants
  checked by this session: skipping the refusal in each of the three commands,
  widening the helper to a zero-width name, and refusing on the flat route are
  each caught. Full suite 14,916 passed, 67 skipped (the extra skip is the
  run-log scope proxy `tests/test_cli.py:3277`, which skips when a branch's diff
  touches test files outside its allowlist). Not tested: the `plan-tool detail`
  command end to end (`derive_candidate_buckets` has one caller). Review:
  pass 1 pending.

## Deliberately not in this handoff

- A snapshot of the current queue: it goes stale on the next drain, so read
  `BUG_BACKLOG.md` at the start of each session.
- Roadmap-owned entries and Jira promotion: the lead owns both.
- New concurrency or parallel fan-out to speed the drain: the tool is serial by
  design.
