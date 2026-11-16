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

- 2026-11-15 — out-of-tree detail archive writes: `pending`, narrowed to
  `detail --split` renames and `evidence-gated` (`detail --force` never writes
  outside `plan-details/<slug>/`; none of 1,033 declared pointers is out of
  tree).

- 2026-11-16 — drain survey of `BUG_BACKLOG.md`: no RISK section, and no
  `direct` + `ready` entry in BUG or MINOR until the ten-site run-log entry was
  split (owner decision). Other unlabelled `direct` entries stay out:
  `extract_h2_sections` defaults (compatibility review first), `install-skill`
  TOCTOU (re-open on a concurrent-install use case), `renderer.py`
  `MUTATING_MODES` (move it to a leaf first), fence-check consolidation (identity
  check first).
- 2026-11-16 — run-log calls with a reachable writer: `fixed a7aee31af` for
  `lessons consolidate` (writer open, no sink bound); refuted for the other four
  (`review_plan_full`, `extract_and_append_review_lessons`, `run_all_done_steps`,
  `_run_deep_for_step`): `cli/review_cmd.py` binds the sink around them. Runtime
  coverage exists only for `reconcile_plan`
  (`tests/test_review.py::TestCmdReviewSaveByDefault::test_claude_calls_land_in_the_run_log`,
  with `invoker=None`, so not the lessons call); the rest rely on
  `CALLER_BOUND_SITES`, which checks each call sits inside its caller's bind.
  Entry removed in `7db641e34`. These sites write no `claude_call_start`, so
  `runs profile` omits them (token totals are complete): retired, owner
  decision, recorded in `docs/history/backlog-decisions.md`.
- 2026-11-16 — overlap sweep: the split's no-writer entry duplicated BACKLOG
  #176 (`render_jira_export`, `classify_plan_implementation`) and #177
  (`suggest_slug`). It is now a MINOR entry for the two callerless functions
  only; `DEFERRED_SITES` reasons cite the tracking entry; #177 is unparked
  (`b71e9ce2f` met its condition) and `decision-needed`. Owner decision.
  Review (`HEAD~2..HEAD`, `/code-review high`): ten prose findings, all fixed.
  #332 is not an instance of #537 (`propose_references` binds a sink and is in
  `LOGGED_SITES`; #332's own "no sink" claim looks stale, left for its owner);
  #177 is `decision-needed`, not `ready`, and its 2026-10-02 note is past tense;
  #176 counts three verbs and notes `reconcile-plan-walk`'s unlisted site; the
  decision record names logged commands (`verify-all`, not its aliases), states
  the signature cost directly, and reopens only for latency or `prompt_sha256`;
  callerless reasons cite their entry; the ambient-writer line left the
  callerless entry. #537 also names `propose_distilled_seed_from_claude` (binds,
  unpinned).
- 2026-11-16 — review of `HEAD~4..HEAD` (`/code-review high`), pass 1: eight
  findings. Fixed: the bench's reconcile trial opened a run log but bound no
  sink, so its records carried no tokens (same class as `lessons consolidate`;
  now bound, with a test); the coverage guard only searched the caller file for
  the phase (now checks the call is inside the `with`, verified by mutation);
  the coverage comment overclaimed `find_lesson_equivalences` (now names the
  library-only route); this log's test citation and bench claim; the lessons
  sink is bound once around the loop. Refuted: the `detail` strict-check route
  to `find_lesson_equivalences` is unlogged but unreachable, since no CLI path
  sets `strict_check` or `warn_check`. Declined: a `claude_call_start` in
  `lessons consolidate` (the prompt is rendered per pair inside
  `find_lesson_equivalences`; same deliberately-not as above); the bind
  overriding the retry attempt number (every `bind_shell_sink` site does this
  by design). Pass 2 (`HEAD~6..HEAD`): eight findings, four of them on the
  coverage guard pass 1 added, so the review stopped here under exit 2 (the loop
  is auditing its own edits). Fixed: every call of a caller-bound site in its
  caller module must sit inside the bind, and calls inside a nested def or lambda
  no longer count; the bench bind is pinned as a second caller of
  `review_plan_full`; the deferred-site comment and message name
  `CALLER_BOUND_SITES`; `_read_log_stats`'s docstring no longer says reconcile
  trials carry no tokens; the ambient-writer "deliberately not done" line moved
  to the deferred entry. Declined: the deferred-site check cannot see a
  caller-side bind (said in its comment); a nested bind with another phase
  mislabels the phase but still records the tokens; folding the
  writer-or-`nullcontext` shape into one helper (incidental consolidation,
  unverified). Class-wide guard (every function opening a `RunLogWriter` also
  binds a sink): `tracked BACKLOG #537`, owner decision.

## Deliberately not in this handoff

- A snapshot of the current queue: it goes stale on the next drain, so read
  `BUG_BACKLOG.md` at the start of each session.
- Roadmap-owned entries and Jira promotion: the lead owns both.
- New concurrency or parallel fan-out to speed the drain: the tool is serial by
  design.
