# How we build with plan-tool

*Back to the [new contributor path](../../CONTRIBUTING.md#new-contributor-path).*

This page is about the people side of `plan-tool`: what the developer does,
what the coding assistant does, and the habits that make the two work well
together. Every example comes from building `plan-tool` itself.

## Two jobs: guardian and mentor

When an assistant does most of the typing and a good share of the checking,
the developer's job changes shape. It becomes two jobs.

**The guardian** holds what the assistant can't:

- the intent: what this work is *for*;
- the scope: what's in, what's out, and what gets filed for later;
- the contracts: persisted formats, blocking policy, and the rules other
  code relies on;
- the call on whether a piece of work should exist at all.

An assistant answers the question it's given, and it can be completely right
about something that shouldn't be built. Deciding the question is the
guardian's part.

**The mentor** keeps the assistant pointed the right way: context up front,
reminders at the moments that matter, and corrections when it drifts. Think
of a very fast, very well-read colleague with no long-term memory and a
strong urge to be helpful. [`CLAUDE.md` and
[`integrations/shared/DIRECTIVES.md`
are the mentor's notebook: written for the assistant, and worth reading
yourself so you know what it has been told.

`plan-tool` is the scaffolding that makes both jobs practical at scale:
schemas the tool can check, gates that stop a bad step, audits that surface
gaps, and saved reports that outlive the chat.

## What isn't new

Most of the habits in this repo are plain good engineering:

- fix the whole class of a bug, not just the line someone pointed at;
- run the test before calling something broken;
- review a pinned range of commits;
- make small commits with one concern each.

`CLAUDE.md` and `DIRECTIVES.md` repeat these constantly. That's not because
anyone thinks they're novel. Assistants need the reminder every time, and
the repetition is part of the mentoring.

What *is* new is the developer's role. When models write most of the text,
the scarce skill moves from writing code to **judging** it:

- stating what a change must deliver;
- deciding whether a finding is real and in scope;
- noticing when a fix is the wrong shape;
- knowing when to stop, and whether the work should exist at all.

## A field guide to assistant behavior

None of this is a flaw to fight. It's how the tools behave, the way a
compiler is strict or a network is sometimes slow. Knowing it lets you plan
around it.

| What assistants reliably do | How it showed up here | The habit that works with it |
| --- | --- | --- |
| **Fix the line they were shown, not its siblings.** | 2026-08-06: seven direct changes in one working tree, six applied only at the first site, and the full suite green on all of them. Finishing one of those sweeps turned five previously green tests red, because each had pinned the old behavior at a sibling. | Ask for the sweep: search by name *and* by wording, fix every instance, and expect sibling tests to go red. |
| **Believe their own reading of the code.** | 2026-08-14: 2 of 15 review findings were "confirmed" by reading, and an existing test contradicted each one. | Ask for the covering test to be run before a bug is called a bug. |
| **Start every session fresh.** | 2026-09-12 to 09-14: in a nine-pass review of the roadmap brief-source work, 11 findings came back after they had been settled in earlier passes. In pass 9 the reviewer checked the settled list first and re-reported none of the five recurring items. | Hand the reviewer the list of settled decisions. |
| **Keep going until someone says stop.** | The same review's per-pass gap counts were 13, 10, 4, 5, 1, 1, 11, 8, 2. The jump from 1 to 11 didn't mean anything had gotten worse. | You call the exits, not the count (see [the loops](#the-loops-and-how-they-end)). |
| **Answer inside the frame they're given.** | 2026-08-08: eight audit rounds refined `audit-trajectory-instrumentation`, every finding real and correctly applied. The symptom the plan existed to fix never reproduced; a throwaway replay script settled it in about 15 minutes. | Ask the "should this exist?" question that no audit can ask. |
| **Patch the newest symptom.** | The roadmap stage-status work, 2026-09: eight review rounds each found a new exception path. It stopped when the developer asked "why not wrap the whole thing?", and one `_stage_run_guard` replaced seven hand-copied try/except blocks (`720f4097`, 2026-09-02). | When the same code breaks in a new way each round, step back and ask the bigger question. |
| **Tidy up beyond the task.** | 2026-09-11: in a 24-round review of the authored-artifact format-version work, two rounds went into hardening `parse_jira_detail_response`, which is unreachable in production. Meanwhile the live parser's gap stayed open. | Keep scope fences, check that code is reachable before hardening it, and file the tidy-up as its own item. |
| **State reasons about the code confidently, and sometimes wrongly.** | 2026-08-04: a fix was placed on the grounds that it was "the only place that knows the run produced the artifact", and one grep for the call sites disproved it. Separately, four of five "duplicated helper" claims in BACKLOG #79 turned out wrong. | Check any claim a fix depends on before accepting the fix. |
| **Occasionally wander off.** | A verifier sub-agent kept running about 68 minutes after its parent review finished, and wrote to four files. Another time a pricier review tier was launched by mistake. | Reviewers read and don't write. The developer picks how deep a review goes. |

## The loops, and how they end

A plan goes through several loops: the bare-plan audit, the detail-grounded
audit, `run`, the `reconcile-code` sweep, and code review. A direct change
gets the same kind of loop, driven through the session. Every loop ends at one of three
exits:

1. **It converged:** a clean pass, or two quiet low-severity passes in a row.
2. **It's now reviewing your own edits:** the new findings describe your last
   fix rather than the plan. Finish applying, then go test, where a mismatch
   becomes a failing test instead of another finding.
3. **It isn't converging:** the same finding keeps coming back, or the real
   fix is a redesign. Stop and take it to whoever owns the scope.

**A falling count is not an exit, and a rising count isn't a verdict
either.** Compare what the findings *are* across at least three passes. After
three full `reconcile-code` sweeps, don't launch a fourth by reflex: sort
what's left by the property it threatens and fix that directly.
[`DIRECTIVES.md` has the exact rules.

Knowing when to stop is part of the skill. A stuck loop is asking a question,
and more compute on the same question rarely answers it.

Pull-request review is the team checkpoint after those local loops. It lets
the team review a bounded change, its evidence, and its settled decisions; it
does not substitute for running the local checks. See
[Contributing.

## Evidence outlives the chat

Decisions and findings go where the next person can find them:

- **saved reports** under `docs/implementation-plans/plan-details/<slug>/reports/`;
- **review ledgers and handoffs** under [`handoffs/`;
- **backlog entries** in [`BACKLOG.md` and
  [`BUG_BACKLOG.md`.

`.tmp/` is scratch and nothing there counts as recorded. One review pass
reported seven findings only in a tool reply that was never written down.
The next pass couldn't act on them, and they had to be rebuilt from session
history.

## Three ways in

The same work needs different hats. They describe **work, not people**:

| Hat | A wrong call shows up as… | The judgment it takes |
| --- | --- | --- |
| **Getting started:** reading the assistant's work | a failing test, or a review comment on a small diff | Is this change right? |
| **Experienced:** mentoring the assistant through a loop | an audit, reconcile, or review finding across modules | Is this finding real and in scope, and has the loop reached an exit? |
| **Architect:** guarding the intent | nothing at first: later work quietly builds on it, and every check passes because it checks the work against itself | Should this exist, and which contracts and principles hold? |

[`CONTRIBUTING.md` has the reading path
for each.

## Stories from the review ledgers

Short versions of the review loops that taught the habits above. Each one
names what the assistant was doing, as a plain fact, and what the developer
did about it.

**Whack-a-mole.** The roadmap stage-status feature promised that an operator
always sees a `stopped` line before anything crashes mid-stage. For eight
rounds, each fix added one more exception type or one more guarded site, and
each review found another one missing, including a round that declared
itself complete and was proven wrong by the next. The developer asked "why
not wrap the whole thing?" The answer, a single `_stage_run_guard` context
manager around the per-stage loop body (`720f4097`), replaced seven
scattered try/except blocks. *Habit: a new symptom in a new place every
round means the fix is the wrong shape.*

**Same function, new bug.** 2026-08-21: a three-line expression in
`cli/app.py:main()` that decides whether to check for a missing backend
binary drew a different confirmed bug in three consecutive review rounds.
Round 2's fix quietly broke an explicit `PLAN_TOOL_BACKEND=claude` setting
that had worked before, because no one had written down the rule the
expression must satisfy or the combinations of flag, environment variable,
and inferred backend it depends on. *Habit: before a second fix in the same
place, write down the invariant and every input combination.*

**It looked right.** 2026-08-14: a session-directed review applied 15 findings. Two
were false positives: the static reasoning was consistent, and an existing
test, written in the same commit as the flagged code, said otherwise. Both
were caught only because the full suite ran before the pass was declared
done. *Habit: run the covering test before believing the bug.*

**Polishing the door nobody uses.** 2026-09-09 to 09-11: a 24-round review
of the authored-artifact format-version work. Rounds 22 and 23 hardened
`parse_jira_detail_response`, which sits behind a deliberate "retired"
guard and never runs in production. The live `parse_detail_response` gap
that round 23 set out to close still reproduced afterward. The loop ended
with a note proposing to back up rather than keep patching forward. *Habit:
check reachability first, and treat backing up as a real option.*

**Groundhog Day.** 2026-09-12 to 09-14: a nine-pass review of the roadmap
brief-source work. Pass after pass re-raised findings the ledger had already
settled: a redundant ternary, a dead conjunct, a control-flow style point,
each declined with a reason. By pass 8, 11 findings had been recorded as
"reaffirmed decline", and the per-pass counts ran 13, 10, 4, 5, 1, 1, 11, 8.
Pass 9 checked the ledger before reporting. It re-reported none of the five
recurring items and came back with 2 findings: a regression-test gap and a
missing entry in a list of routes. *Habit: give the reviewer the settled
decisions, or it will rediscover them every time.*

**Reviewing the wrong 20 commits.** During the stage-status loop, about 11
rounds reviewed a range whose base had been typed by hand: 20 commits out
of the 46 the change actually spanned. Switching to the merge-base with
`origin/main` fixed it. *Habit: compute the range; don't type it.*

**When it just works.** 2026-08-30: the roadmap HTML view went through six
`/code-review` rounds, each on the previous round's committed snapshot.
Every finding was reproduced before it was fixed. Every fix was
mutation-checked: the bug was put back, the test went red, then the fix was
restored. Rounds 5 and 6 both came back low-severity, which is two
consecutive quiet passes, and that's where it stopped. *Habit: this is what
done looks like, so stop there.*

## What we haven't shown yet

All of this comes from **one developer** working with assistants, across a
few clones of this repo. Nobody has measured yet whether the guardian and
mentor habits carry over to other people, or whether writing them down
shortens the loops. The move to a team is the first real test. When a habit
works, or doesn't, add the story here with a date.
