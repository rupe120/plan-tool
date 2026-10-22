# Tracking work

*Back to the [contributor workflow](../CONTRIBUTING.md#driving-a-change-to-done).*

This page holds the rules for tracking work: how an idea or a bug gets
written down, how it's labeled, how someone picks it up, and how it gets
closed. The work itself lives in two lists:

- **[`BACKLOG.md`](../BACKLOG.md)**: forward-looking work, plus the board,
  the priority bands, and the routing arcs that say what to pick next.
- **[`BUG_BACKLOG.md`](../BUG_BACKLOG.md)**: behavior that's wrong today,
  drained in severity order.

Closed decisions that shouldn't be reopened live in
[the historical backlog decisions](history/backlog-decisions.md), so a
closed id stays citable.

## Choose a work record

| If you need to… | First action | Then read |
| --- | --- | --- |
| Record future work | Add an entry to `BACKLOG.md` | [Which file does my entry go in?](#which-file-does-my-entry-go-in) |
| Record behavior that is wrong today | Add an entry to `BUG_BACKLOG.md` | [Which file does my entry go in?](#which-file-does-my-entry-go-in) |
| Preserve a settled decision | Record it in the historical decision record | [The life of an item](#the-life-of-an-item) |
| Choose direct delivery or a plan | Classify its route before authoring | [Direct implementation vs. plan-tool plan](#direct-implementation-vs-plan-tool-plan) |
| Turn a backlog item into a plan | Write its seed and retain the scope contract | [How to author a new plan](#how-to-author-a-new-plan) |
| Assign work to someone | Promote it to Jira | [Jira board](#jira-board), [Promotion stubs](#promotion-stubs) |

## The life of an item

1. **Write it down.** Pick the file with the decision rule below and use the
   entry format in [Adding a new entry](#adding-a-new-entry). An idea or a
   finding that only lives in chat or `.tmp/` hasn't been filed.
2. **Label it.** Every entry gets a route, a readiness, and a tier (next
   section).
3. **Triage it (Jira is the system of record for assigned team work).** The project lead reads the board in `BACKLOG.md`'s
   [Priority section](../BACKLOG.md#priority-mission-grounded) and
   `BUG_BACKLOG.md`, and for each item selected to build, opens the matching
   Jira ticket (assignment, status, priority) and, when the work will run
   through `plan-tool`, authors the seed under `docs/implementation-plans/plan-seeds/` naming that
   ticket. Opening the ticket is **promotion**: the ticket takes the whole
   entry, and the entry becomes a [promotion stub](#promotion-stubs). An
   engineer picks up the Jira ticket, not the backlog entry
   directly — route, readiness, and tier stay useful signal for the lead's
   triage call (see [`CONTRIBUTING.md`](../CONTRIBUTING.md#three-ways-in)
   for how tier maps to who takes it on).
4. **Build it** by its route: a direct edit with the session-directed review loop, or a
   `plan-tool` plan. A backlog-derived seed names its source entry (and its
   ticket key, once promoted) and inherits its scope contract.
5. **Close it.** The change that ships the work removes the item's promotion
   stub in the same pull request. A ticket closed without a code change
   (closed as Done, with a comment saying why) has its stub removed by whoever closes it, in a
   docs-only change. Move the item to `docs/history/backlog-decisions.md`
   instead when a re-open condition is worth keeping. File anything that
   turned up along the way as a new entry. An item that was never promoted
   follows [its own rule](#promotion-stubs).

### Promotion stubs

A **promotion stub** is what remains of an entry after the lead promotes it.
It keeps the entry's id and title, so the `BACKLOG #N` citations in code,
tests, and docs, the `See BUG_BACKLOG` title citations in code comments, and
the heading anchors keep resolving. It also shows a session that searches the
backlog before filing that the item is already tracked.

| File | Stub form |
| --- | --- |
| `BACKLOG.md` | `**#N — <title>** → promoted to IPPT-123 (YYYY-MM-DD)` |
| `BUG_BACKLOG.md` | keep the `###` heading; the body becomes `- **Promoted:** IPPT-123 (YYYY-MM-DD)` |

- **One home at a time.** The ticket holds the working brief and the stub
  holds only the pointer; the entry's full text stays in git at the commit
  before promotion. A ticket that starts in Jira (a support report, an
  architect's export bug) never gets a backlog entry.
- **The ticket holds the scope contract after promotion, and the seed
  carries a copy.** Every rule that says a seed "inherits the source entry's
  scope contract" reads as "inherits it from the ticket" for a promoted item.
  The seed is the in-repo copy `create` reads, so whoever authors it copies
  the contract in from the ticket.
- **Older seeds and plans need no rewrite.** "Update the originating backlog
  file" and "remove the entry when this ships" mean the stub for a promoted
  item.
- **Unpromoted items keep the entry rule.** Owner-tracked work and any entry
  that never goes through Jira keeps its content in the entry: mark it
  plan-authored while a plan's execution is pending, and remove it when the
  work ships.

## Labels every entry carries

Three labels, each with a short fixed list of values. They apply to both
`BACKLOG.md` and `BUG_BACKLOG.md`, next to each file's existing fields.

| Label | Values | What it answers |
| --- | --- | --- |
| **Route** | `direct` · `plan` | Is this a direct edit with the session-directed review loop, or a `plan-tool` plan? For a conditional, write `direct` plus an `Escalate to plan if:` line naming the condition. |
| **Readiness** | `ready` · `decision-needed` · `evidence-gated` · `blocked-on #N` · `parked` | Can someone start today, or does a decision, a measurement, or another item come first? |
| **Tier** | `beginner` · `experienced` · `architect` | The least experienced kind of work that could own this item through to merge, with normal review. |

**Older entries carry an `Approach:` tag instead.** Read `Approach: direct` /
`plan-tool` as the Route, and read an `Approach:` that opens with "decision
first" or "investigation" as Readiness `decision-needed`. An entry without a
Tier is not triaged into the tiers yet. Fill it in when you next touch the
entry; a missing Tier says nothing about the entry's worth.

### Principle (`BACKLOG.md` only)

A feature entry carries one more label, because `BACKLOG.md` has no severity
sections to rank by (`BUG_BACKLOG.md` ranks by its `BUG` / `RISK` / `MINOR`
sections instead). It answers: which grounding principle in
[`MISSION.md`](../MISSION.md) does the item serve?

| Value | Ranks as |
| --- | --- |
| `converge-on-correct-plan` | P1, the trust core |
| `deterministic-non-determinism` | P2, the trust core |
| `keep-the-plan-true-to-code` | P3, the trust core |
| `survive-interruption` | P4 |
| `write-for-the-human` | P5 |
| `none`, with the reason after it | serves no principle directly (throughput, repository hygiene, cosmetic) and ranks below every principle |
| `untriaged` | not yet judged; a count of these is the triage debt |

- **Values are `MISSION.md`'s stable slugs, not positions.** The mission keeps a
  slug through any reorder or reword, so a label never needs rewriting when the
  principles are renumbered.
- **One value per entry, the primary principle.** An entry that serves two
  states the second in its prose.
- **`none` always carries its reason on the same line.** A bare `none` reads
  the same as "not looked at"; `untriaged` is the value for that.
- **Label an entry when you next touch it.** No bulk pass over the untouched
  entries: keyword-style bulk sizing misjudged entries in both directions
  ([Choosing the tier](#choosing-the-tier)).
- **Deliberately not done:** the label is not derived automatically, nothing
  gates on it, and it is not copied to Jira, where labels stay `beginner` /
  `experienced` / `architect`, `plan`, and the few in
  [Labels, statuses, and comments](#labels-statuses-and-comments). The lead
  reads it from the backlog when ordering To Do.

**Choosing what to promote next.** Take the first row that has a candidate.

1. An unpromoted, unblocked `BUG` in `BUG_BACKLOG.md`, outside `ROADMAP`.
2. A `BACKLOG.md` entry with Readiness `ready`, ordered by `Principle`
   (P1 first), then by bucket (A and B before D and E).
3. A `RISK` or `MINOR` bug entry. Where these rank against P1–P3 features is
   the lead's call and is deliberately not fixed here.
4. Any other entry, including `untriaged` ones and gated ones (`decision-needed`,
   `evidence-gated`), which are promoted only under the rules in
   [Issue types](#issue-types).

An active feature-breakout arc, or a pick on the Now board in
[`BACKLOG.md`](../BACKLOG.md), outranks this order. Verify each candidate
against the tree before drafting: an entry can already be fixed, and its
promotion stub then needs removing instead of a ticket.

### Choosing the tier

A tier describes the **work, not a person**. The question is where a wrong
call would show up:

| Tier | A wrong call shows up as… | The judgment it takes |
| --- | --- | --- |
| `beginner` | a failing test, or a review comment on a small diff | Is this change right? |
| `experienced` | an audit, reconcile, or review finding across modules | Is this finding real and in scope, and has the loop reached an exit? |
| `architect` | nothing at first: later work builds on it, and every check passes because it checks the work against itself | Should this exist, and which contracts and principles hold? |

Tier and route are independent. A small direct change can be `architect`,
for example one that flips which way a reconcile verb points. A `plan` can be
`experienced`.

**`architect`** if the item defines or changes any of these:

- a persisted contract or version (`DATA_CONTRACT.md`, `schema.py`,
  [`DIRECTIVES.md`](../integrations/shared/DIRECTIVES.md) § "Versioned
  persisted contracts");
- blocking or convergence policy ([`CLAUDE.md`](../CLAUDE.md) § "Convergence
  policy boundary");
- what an audit gate means, or the audit-shape registry;
- the import-graph rules, the exit-code convention, or the stance on
  parallelism;
- a [`MISSION.md`](../MISSION.md) principle, the canonical directives, this
  project's own `CLAUDE.md` rules, or a plan's scope or
  decomposition.

**`experienced`** if it stays within existing contracts but touches any of
these:

- a behavior change that spans modules, where one module's change depends on
  or alters what another does;
- a prompt under `plan_tool/prompts/`;
- a CLI surface (and so regenerating `docs/cli/`);
- a gate's behavior, or a gate message that something else reads: a test or
  CI that matches its text, or a retry correction that quotes it back to the
  model (a wording fix that nothing reads is not this);
- the `plan` route;
- a change to what a doc says about how machinery behaves (a link, path, or
  wording fix that leaves that description alone is not this).

The same small edit repeated at a few named sites (a renamed command in three
messages, one path fixed in several docs) does not span modules in this sense.
Judge by what a wrong call would break, not by how many files the diff touches.

**`beginner`** only if **all** of these hold:

- the item is `direct` and `ready`;
- it touches one module plus its matching test module, one doc, or the same
  small edit at a few named sites plus their tests;
- the acceptance check is written down;
- a past commit or an existing pattern in the code exists to copy from;
- none of the surfaces above are involved.

A `beginner` entry carries five more fields, always filled in (`none` is a
fine answer):

- **Start here:** the files and the test module.
- **Precedent:** a commit that did something similar, or an existing
  pattern in the code to copy, named by file and line.
- **Settled decisions to respect:** the lessons and decisions not to reopen.
- **Done when:** the acceptance check.
- **Reviewer:** a name, or `unassigned`.

When an `architect` item's decision lands, turn it into `ready` items, each
with its own tier. Carve out a `beginner` slice whenever there is one.

**Deliberately not done:**

- The tier isn't derived automatically. A keyword-based sizing of the
  backlog misjudged entries in both directions, so the tier is a judgment
  call by whoever writes the entry, like `Approach:`.
- Nothing gates on a tier. No check judges whether a tier "fits", and no
  exit code or permission keys on one.
- The tier checklist doesn't use line counts, file or module counts, effort
  on its own, or "it's only docs". Each of those misjudged a real entry: a
  module count put a three-string command-name fix at `experienced` (IPPT-2,
  2026-09-24).

A presence check that confirms the three labels use allowed values is fine;
`tests/test_backlog_ids.py` is the same kind of check, for entry ids.

## Jira board

The board holds **promoted work only**. The backlogs stay the discovery log, and nothing syncs
between them: the lead promotes by hand. Read the actual site, project key and board
from ignored `.claude/local/project-context.json`; initialize it from
`.claude/project-context.example.json`. `IPPT` in tracked examples is an
example project key, not a configured target.

- **Scope:** one project for the team's part of plan-tool. The `roadmap`
  verb and Integration are owner-tracked experimental work and stay off the board
  ([Roadmap boundary](#roadmap-boundary)).
- **Kanban**, with four statuses: To Do, In Progress, In Review, and Done. The
  lead orders To Do, and the top ticket is next. The board stays thin on
  purpose: labels carry classification and comments carry nuance
  ([Deliberately not configured](#deliberately-not-configured)).
- **`plan-tool jira` stays a supported feature.** Architects use the story
  export to hand detailed plans to teams on other projects. The team's own
  tickets are written from the backlogs directly, not generated by it.

### Issue types

An item gets exactly one type: the **first row that matches**.

| Order | The item is… | Jira type |
| --- | --- | --- |
| 1 | a feature-breakout arc or an ordered seed group | Epic. An anchor entry becomes the Epic and its arc moves into the description. If the anchor is `evidence-gated`, its gating investigation is the Epic's first Spike. |
| 2 | readiness `evidence-gated`: an investigation whose output may be "no action" | Spike: a Task with the `spike` label. Closing it with "no action" is a valid outcome, recorded in a comment. This row wins over the source, so an `evidence-gated` RISK entry is a Spike. |
| 3 | from `BUG_BACKLOG.md` (BUG, RISK, MINOR) | Bug |
| 4 | from `BACKLOG.md` bucket A (capability) or B (UX) | Story |
| 5 | from `BACKLOG.md` bucket D (hygiene) or E (cosmetic) | Task |

A `decision-needed` item is promoted only when its answer needs research the
promotion session cannot do (see [Ticket contents](#ticket-contents)). It
keeps the type its first matching row gives it and carries the
`decision-needed` label until the decision lands. Bucket C is
retired vocabulary: an entry that still carries it is typed by its readiness,
so an `evidence-gated` one is a Spike and one waiting on a decision is a Story
or Task labelled `decision-needed`.

Epics cover feature-breakout arcs and ordered seed groups only. The T1–T5
priority-band arcs are priority orderings, not epics; archived arcs are history; a bug
never gets an epic of its own.

### Labels, statuses, and comments

Jira carries no custom fields. Each backlog label maps to a status, a label,
a link, or a line of the description:

| Backlog label | Jira |
| --- | --- |
| Tier | label `beginner`, `experienced`, or `architect`. A saved filter counts the Architect's floor of five: `labels = beginner AND labels not in (needs-triage, decision-needed) AND status = "To Do"`. |
| Route `plan` | label `plan`; the description's `Route:` line (see [Ticket contents](#ticket-contents)) states the route, its starting command, and — once the seed exists — the `Seed:` line naming its path and where `create` archives it, then a `Plan:` line naming the plan file once `create` has run. A ticket without the label is `direct`, and its `Route:` line says so explicitly rather than leaving it to the label's absence. |
| Readiness `ready` | status **To Do**, in the lead's order |
| Readiness `decision-needed` | settle it in the promotion session first. Only when the answer needs research the session cannot do: label `decision-needed`, with the research named in a comment. An `evidence-gated` item is a Spike instead. |
| Readiness `blocked-on #N` | an "is blocked by" link to that item's ticket |
| Readiness `parked` | not promoted; stays in the backlog |
| entry id `#N` | a `Source:` line right after the Summary section: `Source: BACKLOG #N`, or `Source: BUG_BACKLOG "<entry heading>"` |
| quality-lens facet | optional label |

The other labels are `needs-triage` (a ticket filed directly in Jira; see
below), `spike`, `roadmap` (a team ticket that depends on owner-tracked
roadmap work; the owner's own roadmap work is not ticketed), and
`no-changelog` ([`docs/RELEASING.md`](RELEASING.md)).

**Pull rule.** An engineer takes the top **To Do** ticket whose Tier label
matches work they can own through to merge, skipping any ticket labelled
`needs-triage` or `decision-needed`.

**Workflow:** To Do → In Progress → In Review → Done. A `plan`-route ticket
adds one review moment before `run`:

1. While it is In Progress, the engineer authors the seed, plan, and detail
   bundle.
2. When the bundle is ready, the engineer opens a plan pull request — `main`
   is protected, so the bundle never lands there by a direct push — and links
   it in a comment on the ticket
   ([`CONTRIBUTING.md`](../CONTRIBUTING.md#review-plan-artifacts-apart-from-code)).
3. The Architect approves and merges the plan pull request once the
   completeness-audit gates have converged the bundle. `plan-tool run`
   enforces the same requirement — it refuses until the plan and a detail file
   for every committed step are on `origin/main` — so the engineer then
   branches from `main`, runs the plan, and moves the ticket to In Review.

A `direct`-route ticket has no plan review. Every ticket closes as Done. A
ticket closed without shipping a change says why in a comment and takes the
`no-changelog` label.

**Comments carry the nuance.** Put these in comments on the ticket, not in
extra statuses, fields, or labels:

- the open question on a `decision-needed` ticket, and its answer;
- a `plan` ticket's link to its plan pull request (merging it is the approval);
- why a ticket is blocked, and why one closed without shipping a change.

### Priority

| Source | Jira priority |
| --- | --- |
| a user is blocked or a release is broken | Highest |
| `BUG_BACKLOG.md` BUG | High |
| `BUG_BACKLOG.md` RISK, and every feature by default | Medium |
| `BUG_BACKLOG.md` MINOR | Low |

The field is not the ranking tool: the lead orders items by position on the
board. The T1–T5 priority bands and a feature entry's [`Principle`
label](#principle-backlogmd-only) inform where the lead places an item, and
they do not set its Jira priority: a feature stays Medium by default, and
deliberately not mapped from `Principle`, so the field and the board cannot
rank the same work two ways. The site also defines Critical and Lowest; the
team leaves both unused.

### Ticket contents

A ticket is a short brief, not a copy of the entry. Someone should be able to
do the work from it and stay inside its scope. Aim for under 300 words, or under
500 when the ticket carries an Example (below); a long list of sites can justify
more. The full entry stays in git at the commit before
promotion, so history, rationale, and evidence the change does not need are left
out.

In order:

1. **Summary**: one or two sentences saying what is wrong or wanted and what the
   change does.
2. A `Source:` line. The ticket title is the entry's heading and the `Source:`
   line quotes it; a promotion stub keeps that heading, so the title, the
   `Source:` line, and the stub stay identical.
3. **A `Route:` line, always present — not only the `plan` label.** State the
   route and the exact command that starts it, so the ticket is
   self-explaining without cross-referencing this file or the `plan` label:
   - `Route: plan — start with \`plan-tool create --from-existing
     docs/implementation-plans/plan-seeds/<name>.md\`, then follow the audit gates in
     integrations/shared/DIRECTIVES.md (bare-plan audit, \`detail\`,
     detail-grounded audit, \`run\`); see docs/TRACKING.md § "Jira board"
     for review and merge.`
   - `Route: direct — implement directly; no plan-tool create/detail/run.`

   A `plan`-route ticket's `Route:` line is immediately followed by a `Seed:`
   line, once the seed exists, and after `create` runs by a `Plan:` line:

   ```text
   Seed: `docs/implementation-plans/plan-seeds/<name>.md` — authored here; `create` archives it under `docs/implementation-plans/plan-seeds/archive/` as `<name>.replaced[.N].md`
   Plan: `docs/implementation-plans/<name>.md`
   ```

   `create` moves the seed, so the `Seed:` line states where it was authored and
   where it goes, and the `Plan:` line is the durable pointer once the seed is
   archived (see [Labels, statuses, and comments](#labels-statuses-and-comments)).
   A `direct`-route ticket has neither line. This is the same "mark the boundary structurally, not
   positionally" rule the label table itself follows
   ([`CLAUDE.md`](../CLAUDE.md) § "Prefer the explicit over the implicit"):
   before this line existed, a reader had to already know the label taxonomy
   and cross-reference this document to tell the two routes apart, or to find
   the command that starts one.
4. **Example**: one real input followed through the change, today and after:
   what is run, what the code reads, what is printed or refused. It defines each
   coined term once and marks illustrative wording as illustrative. A reader who
   has not read the plan should be able to say what the command will do from it.
   Tickets written before this section existed lint with a warning, not an error.
5. **Change**: a before-and-after table (situation, today, after), each row naming
   the command or function that does the work, plus the sites (files and line
   numbers) the table does not carry.
6. **Out of scope** and **Stop / defer**, one line each. Tighten the words, but
   keep every named exclusion: this fence keeps an engineer's coding assistant
   inside the scope, and a summarized fence does not.
7. A `beginner` ticket adds **Where to start**: Start here, Precedent, Settled
   decisions to respect, Done when, and Reviewer, one line each (the heading says
   what the section is for, so it is not read as the tier label). Any other
   ticket states **Done when**.
8. **Why this tier**: one or two lines naming the conditions in
   [Choosing the tier](#choosing-the-tier) that decide it. The type, priority,
   and other labels follow mechanical rules and need no explanation.

**No open questions.** Settle them in the promotion session before creating the
ticket: research them there, and put the choices that are the lead's to the lead.
The one exception is a question the session cannot answer without more research.
That ticket carries `decision-needed`, and a comment names the research.

### Tickets filed in Jira

Anyone may file directly in Jira: a support report, an export user's bug. Add
the `needs-triage` label; the lead triages that label the same way as the
backlogs. Such a ticket never gets a backlog entry (see
[Promotion stubs](#promotion-stubs)). Before filing a backlog entry, search
the backlog files (stubs included) and, where you have Jira access, the
board, so nothing is filed twice.

### Deliberately not configured

Jira stays thin: labels carry classification and comments carry nuance. Each
row below stays unconfigured until its "Add it when" condition holds, so a
missing status or field is a decision and not an oversight.

| Not configured | Carried by | Add it when |
| --- | --- | --- |
| Needs Decision, Ready, and Plan Review statuses | the `decision-needed` and `plan` labels, the order of To Do, and comments | tickets sit unnoticed in one of those states and no saved filter surfaces them |
| WIP limits | the team's own attention on about three engineers | In Progress or In Review visibly clogs |
| Custom fields `Tier`, `Route`, and `Backlog ref` | labels and the description's `Source:` line | label drift (typos or missing labels) makes the saved filters wrong |
| Components | the summary, and a label when a filter needs one | a report has to group tickets by product surface |
| Fix Version and a `next` release | the release check in [`docs/RELEASING.md`](RELEASING.md): Done tickets since the previous tag, against `changelog.d/` | someone needs to ask, after the fact, which release shipped a ticket |
| Resolutions Won't Do and No Action | Done, a comment saying why, and the `no-changelog` label | a report has to separate shipped from not-shipped closures without reading comments |
| A Spike work type | a Task with the `spike` label | Spikes need their own workflow or their own board column |

### Roadmap boundary

The `roadmap` verb and Integration are owner-tracked experimental work. The team's
queue excludes them, and the boundary is marked in
each place work is tracked:

| Surface | How the boundary is marked |
| --- | --- |
| Code and docs | Request owner review explicitly for changes to the roadmap capability; shared-code changes retain their normal review tier. |
| `BUG_BACKLOG.md` | roadmap-owned entries live under `## ROADMAP`, each with a `Severity` line. |
| `BACKLOG.md` | roadmap items are those `backlog-arc-roadmap.md` routes, plus any entry whose **Arc assignment** names that arc. The lead does not promote them. |
| Jira | no roadmap tickets. The `roadmap` label marks a team ticket that depends on owner work. |

- **Roadmap-owned** means the entry names at least one roadmap-specific code
  or documentation path and no shared code path. Roadmap-specific paths implement,
  test or document the `roadmap` capability. Shared documentation paths do not
  change the classification. Classify by the responsibility of the named paths,
  not by a reviewer-routing file. Resolve an ambiguous boundary with the owner
  before promotion.

  | The Files line names… | Roadmap-owned? |
  | --- | --- |
  | roadmap-specific code only | yes |
  | roadmap-specific code plus shared docs such as `RUNBOOK.md` | yes |
  | only roadmap-specific docs such as `docs/how-to/roadmap.md` | yes |
  | only shared docs | no |
  | roadmap-specific code plus shared code | no: see the next bullet |
  | shared code only | no |
- **Mixed entries stay with the team.** An entry that touches roadmap code
  and shared code stays in its severity section, because a defect in shared
  code is team work. Request the owner's review explicitly for its roadmap part.
- **Team work that needs a roadmap change hands up.** The ticket links to the
  owner's item and does not fold the change in.
- **Integration** is tracked in its own repository. A plan-tool finding Integration surfaces
  is filed like any other entry and is team work unless it is roadmap-owned.

## Which file does my entry go in?

Plan-tool tracks two separate lists. Pick the right one before
writing the entry — moving entries between files later is cheap
but introduces churn.

**`BACKLOG.md`** holds entries where shipping nothing
today is acceptable:

- Net-new capability or subcommand that doesn't exist yet.
- UX changes that improve workflows that currently work.
- Investigations whose output may be "no action."
- Process / hygiene refactors and test backfills that aren't
  fixing user-visible incorrect behavior.
- Cosmetic / churn (renames, rebranding).

**[`BUG_BACKLOG.md`](../BUG_BACKLOG.md)** holds entries where the
current code is wrong but unresolved:

- Incorrect behavior on a supported flow (broken output, missing
  data, wrong dispatch, partial state after failure, etc.).
- Contract violations (public dataclass shape changed without
  deprecation, positional arg added, schema field interpretation
  shifted).
- Dormant correctness bugs (broken under conditions that don't
  fire today but will under a foreseeable change).
- Race conditions, leaked resources, non-atomic writes,
  mis-reported run-log fields, silent fallbacks that mask errors.

**Decision rule when unsure:**

- "If I shipped the code as-is and a user filed an issue against
  this behavior, would they be right?" → BUG_BACKLOG.
- "If I shipped the code as-is, no user would notice anything
  missing or wrong, only that something *could* be better?" →
  BACKLOG.

The two files differ in metadata shape too:

- `BACKLOG.md` entries carry **Effort / Risks / Dependencies /
  Scope-Non-goals / Approach / Iterate** because "should this be a
  plan?", "what's the test fallout?", and "what must it *not* pull in?"
  are real decisions for new work.
- `BUG_BACKLOG.md` entries carry **Files / Symptom / Fix /
  Origin** because bugs typically have one approach (just fix
  it) and the reader's first question is "where and how."

If you find yourself writing Effort + Risks + Approach prose for
a clearly-broken behavior, that's a signal the entry belongs in
`BUG_BACKLOG.md` and the prose is over-shaped for what's needed.

## Direct implementation vs. plan-tool plan

Once a backlog item is picked, decide whether to implement it
directly or to author a formal `plan-tool` plan first. The two
modes have different overhead profiles and different return on the
investment.

**Implement directly when ALL of these hold:**

- The change fits in one logical step (touch a small number of
  related files; mental model fits in one head at once).
- The acceptance criteria are obvious from the backlog entry — you
  don't need to discover them, just satisfy them.
- The test surface is bounded and you can name the affected test
  classes up front.
- No cross-cutting design decisions remain open (no "we'd need to
  pick X over Y" trade-offs that should be documented).

Examples: a surgical bug-fix, a single-file refactor, a flag
default flip with mechanical test updates, restoring a dropped
capability via a small patch.

**Author a `plan-tool` plan first when ANY of these hold:**

- The change touches multiple modules with non-trivial coupling
  (e.g., extending an iteration loop to another entry point —
  needs detail steps for each module).
- Acceptance criteria need to be discovered, not just listed —
  you'd otherwise hand-wave them at coding time and regret it.
- The implementation has 2+ visible phases (e.g., "first add the
  scaffold, then wire callers, then update tests").
- There's a meaningful design choice worth a paper trail
  (Direction/Justification, scope guard, intent gates, etc.).
- The work would benefit from `--iterate` (reconcile +
  apply-finding loop) to converge against acceptance criteria.

Use the [How to author a new plan](#how-to-author-a-new-plan)
procedure below. Authored plans live under
`implementation-plans/` and become the canonical reference for
the work; the backlog entry (or its promotion stub) stays in its backlog
file until the plan's work ships, then both get removed together. When the
plan starts from a backlog entry, the seed must name that source entry
(and its ticket key, once promoted) and carry an explicit
backlog-reconciliation requirement into the resulting plan, usually as a
final docs/status step and acceptance criterion. The implementation is
not complete until the originating backlog file is updated: remove the
shipped entry or its stub, mark an unpromoted entry as plan-authored if
execution remains pending, or split/update any deferred follow-up that
still belongs in the backlog.

**Heuristic call:** if you can't tell from the backlog entry
whether direct or plan is right, default to authoring a plan.
The cost of an unused plan is one extra `plan-tool create` call;
the cost of an under-scoped direct-implementation is debugging
half-shipped state later.

**Per-entry Approach tag.** Each backlog item is pre-tagged with
the recommended path so you don't have to re-run the heuristic for
every browse. Tag values:

- `direct` — small enough to implement inline; acceptance criteria
  obvious; no design choices open.
- `plan-tool` — multi-step / multi-module / has open design
  decisions / benefits from `--iterate`.
- `direct unless <condition>` — a conditional that tips into
  plan-tool when the named scope expands (e.g., "direct unless the
  test fallout exceeds one class," "direct unless the
  auto-iterate variant is chosen").

Override the tag if your read of the work differs — the tag
captures the entry author's judgment at write time, not a hard
contract.

### Iterate convention for plan-tool entries

`plan-tool` and `--iterate` are orthogonal decisions. Picking
plan-tool means "author a plan first"; picking iterate means "let
the convergence loop refine OR review the artifact." Iteration
earns its keep in two distinct modes: **constructing** (body-fill,
per-step execution) and **reviewing** (catching missed edge cases
in plans or implementations where the work is interdependent and a
single pass tends to miss things). Most plan-tool entries follow
the same default recipe. Each phase carries a **canonical
reference** label — what the phase treats as ground truth:

- **plan canonical:** plan/detail says what should be true; audit
  or update code to match.
- **code canonical:** code on disk is the ground truth; audit or
  update detail/plan to match.
- **internal:** audit purely within the plan + detail set;
  neither code nor an external reference is consulted.

Naming the canonical reference makes phase ordering obvious
(plan-canonical phases come after authoring; code-canonical
audits come before execution; the executor itself flips code
from "pre-plan" to "matches plan").

1. **Author with `create --iterate`** (plan canonical; toolchain
   default). `create` produces frontmatter + step list + complete
   body sections from the source description; `--iterate` refines
   the plan for correctness and completeness. If `create` emits
   `_(TODO)_` placeholders in body sections, that is a bug in
   base `create` (see [`BUG_BACKLOG.md`](../BUG_BACKLOG.md#bug);
   step 3 of `bug-backlog-drain` enforces fail-loudly when stubs
   slip through) — do not reach for `--no-iterate` as a
   workaround. For backlog-derived work, the seed passed to
   `create` must include the source backlog entry (and its ticket key,
   once promoted) and require the plan to update the originating
   backlog file as part of its completion criteria.

1.25. **Bare-plan audit with `completeness-audit --iterate --commit`**
   (internal; [Gate 1](../integrations/shared/DIRECTIVES.md#gate-1--the-bare-plan-audit-before-detail)).
   Required before `detail`: it catches a missing plan-level contract,
   ordering, or acceptance criterion before detail prose multiplies it.

1.5. **Detail with `detail --commit`** (plan canonical). Draft each
   per-step detail file in its normal one-shot mode. Detail does not iterate
   unless an operator explicitly asks for it. Required before phase 2.

2. **Plan/detail coherence with `completeness-audit --iterate --commit`**
   (internal; [Gate 2](../integrations/shared/DIRECTIVES.md#gate-2--the-detail-grounded-audit-after-detail)). Two complementary jobs in one loop: (a) **fill
   body-content gaps** — deterministic completeness checks
   surface missing or `_(TODO)_` sections and `apply_finding`
   closes them; (b) **review the plan for missed edge cases** —
   concept-completeness audits acceptance criteria against the
   pending step list and flags conditions / branches the steps
   don't cover. Job (b) is especially load-bearing when the plan
   has many interdependent steps; the convergence loop catches
   what one read-through wouldn't. Phase 2 always follows `detail`: the
   audit judges the freshly authored detail bundle, which a canonical
   source description does not vouch for. A loop that converges on its
   first pass is the cheap case, not a reason to skip.

2.5. **Pre-execution audit with `plan-tool reconcile-plan <slug>`** (code
   canonical). One claude call audits every step's plan body +
   frontmatter against the current code on disk — surfaces steps
   that look already done, declared-files mismatches, missing
   runtime deps. Read-only; reports findings without applying.
   When `review` flags concrete drift in a step's per-step detail
   body, drill in with
   `plan-tool detail <slug> --reconcile --step N` to walk and
   apply findings deterministically. Skip 2.5 entirely when the
   plan is fresh AND all `files:` are net-new (no current code to
   audit against).

3. **Execute with `run --step N`** (plan canonical; per step).
   Single-pass executor lands code edits and advances the step
   to `done`. `--iterate` is a no-op under `--mode run` (the
   default) — only `--mode reconcile` honors the iteration
   loop, so do not pass `--iterate` on the execute call. For
   steps with discoverable acceptance criteria or expected
   drift, follow up with phase 3b below to converge
   post-execution.

3b. **Post-execute reconcile with `run --step N --mode reconcile
    --iterate`** (plan canonical; per step; optional). Audits
    the just-landed code against the plan and loops apply-
    finding until convergence. Skip 3b for mechanical / obvious
    steps where the loop would just spin without adding value
    (single-line deletions, mechanical renames, etc.).

4. **Post-run reconciliation and review** (plan canonical). After every
   green step is committed, use `reconcile-code <slug> --all` and a code-review
   loop. Do not re-run `completeness-audit` here: it evaluates the plan and
   detail bundle, not the implementation.

Per-entry `Iterate:` notes (when present) state which phases apply
and call out any divergences (e.g., "phase 3 essential — mechanical re-indent where
the loop catches silent whitespace bugs," "phase 4 critical —
cascading interdependencies between steps"). Absence of an Iterate
note on a plan-tool entry means the default recipe applies.

Iterate is the quality default across the toolchain, regardless of
approach. `create` and `completeness-audit` use their convergence loop by
default; `detail` is deliberately one-shot, and `run --iterate` applies only
to reconcile mode. Direct changes require the equivalent session-directed review and
test loop. An `Iterate:` note records only a meaningful divergence.

**Plan-tool entries MUST include explicit
`plan-tool` command examples for every phase that
applies**, with the entry's slug filled in (use the implied slug
from the source doc filename or coin one from the backlog item
title). This way a reader landing on an entry has runnable
commands at hand instead of having to translate the phase prose
into invocations. For phases that follow the default recipe
exactly, copy the relevant block from below; for divergent
phases, show the actual command and inline a `#` comment naming
the divergence.

Backend choice does not change the backlog bookkeeping rule. If
authoring through a non-default backend, use the normal backend
selection surface (`--backend codex`, `PLAN_TOOL_BACKEND=codex`,
or the `cursor` backend that shells out to the `agent` binary), but
keep the backlog source and backlog-update requirement in the seed
itself so every backend receives the same instruction.

Default-recipe command block (template — substitute the entry's
slug + paths):

```bash
# Phase 1: author the plan (plan canonical). --from <inline> or
# --from-existing <path>. If <source.md> was distilled from a
# BACKLOG.md / BUG_BACKLOG.md item, it must name that item (and its
# ticket key, once promoted) and require backlog reconciliation in the
# resulting plan.
plan-tool create <slug> --iterate -y \
  --output-dir <dir> --from-existing <source.md>

# Phase 1.25: bare-plan audit, Gate 1 (internal). Required before detail.
plan-tool completeness-audit <slug> --iterate --commit -y

# Phase 1.5: draft per-step detail files (plan canonical).
plan-tool detail <slug> --commit -y

# Phase 2: detail-grounded audit, Gate 2 (internal — body-fill +
# concept-completeness).
plan-tool completeness-audit <slug> --iterate --commit -y

# Phase 2.5: code-vs-detail reconcile (code canonical). Per step;
# skip for net-new files.
plan-tool detail <slug> --reconcile --step N -y

# Phase 3: execute the step (plan canonical). Per step.
plan-tool run <slug> --commit -y --step N

# Phase 3b: optional post-execute reconcile loop. Skip for
# mechanical / obvious steps.
plan-tool run <slug> --mode reconcile --iterate -y --step N

# Phase 4: post-execution reconcile and code review (plan canonical).
plan-tool reconcile-code <slug> --all
```

## Adding a new entry

When you add a candidate, include at minimum:

- **Id** (`BACKLOG.md` only; `BUG_BACKLOG.md` entries are titled headings
  with no id): open the entry `**#N — <title>**`, with N one above the highest
  id ever used. Fetch, run the command, and run it again right before you
  publish. Empty output or an error means it failed, not that no id exists.

  ```bash
  git fetch --all
  { git log --all -m --format= -p -G'^\*\*#[0-9]+ — ' -- ':(top)BACKLOG.md' | grep -E -o '^\+\*\*#[0-9]+ — '
    git grep -h -o -E '^\*\*#[0-9]+ — ' -- ':(top)BACKLOG.md'; } | grep -o -E '[0-9]+' | sort -n | tail -1
  ```

  - **What it reads.** Every `**#N — ` opener ever added on any ref your clone
    has, including one that only a merge resolution introduced and one removed
    since (a removed id stays cited from `docs/history/backlog-decisions.md`,
    commits, and seeds, so it is never free), plus the openers in your working
    tree, so an entry you have not committed yet counts.
  - **What it cannot see.** An id a sibling clone has not pushed, and a
    pull-request ref you have not fetched.
  - **What covers the rest.** `tests/test_backlog_ids.py` fails a duplicate on
    the first test run over a tree that holds both entries: your pre-push hook
    after a rebase or merge, or CI once one exists. Two branches that add the
    same id in different places merge cleanly on the server without running it.
  - **If two entries collide anyway,** the one cited elsewhere keeps its id.
    With equal citations the one filed later moves. Date each with
    `git log --all -S'**#N — ' --format='%h %ad %s' --date=iso -- ':(top)BACKLOG.md'`:
    the earliest author date among the commits that add the opener is when that
    entry was filed, and a commit that removes one is a renumber to skip.
- **Heading:** the `<title>` above, or the `###` line in `BUG_BACKLOG.md`. One
  sentence that says what goes wrong (or what is wanted), when, and the visible
  effect; file paths and function names go in the body. The
  [documentation style guide](reference/documentation-style.md#backlog-entries-and-tickets)
  has the wording rules.
- **What:** one-line description plus a sentence of context.
- **Effort:** small / medium / large, with the reasoning (touches N
  files, mechanical vs. design, etc.).
- **Risks / fallout:** test churn, breaking changes, dependency
  surface.
- **Dependencies:** which other backlog items (or external state)
  must land first.
- **Scope contract** (required for substantial entries; omit only
  for a genuinely atomic one-liner with no plausible creep direction).
  A backlog-derived seed/plan **inherits this contract verbatim** rather
  than inventing a different fence. Fields:

  - **Outcome:** exactly one measurable result. Two outcomes → two
    entries.
  - **In scope:** named surfaces (files, modules, commands, runtimes).
    Prefer paths over vague domains.
  - **Out of scope / Non-goals:** hard exclusions — sibling items in a
    dependency arc, tempting generalizations, adjacent surfaces, and
    follow-ups deferred elsewhere. Dependencies say what must land
    *first*; Non-goals say what must *not* be pulled in.
  - **Allowed behavior changes:** default **none beyond the stated
    Outcome**. List every permitted user- or operator-visible delta.
  - **Allowed reorganization:** default **none**. If reorganization is
    required, name the ownership boundary it fixes, the concrete
    blocker proving the move is necessary, and the smallest move that
    resolves that blocker. "Cleaner," "more reusable," and "while
    here" are not blockers.
  - **Verification:** how success is checked without expanding scope.
  - **Stop / defer:** newly discovered defects, resilience ideas, and
    adjacent cleanup become separate `BACKLOG.md` / `BUG_BACKLOG.md`
    entries (or the seed/plan Deferred section). They may block this
    item **only** when preserving current supported behavior is
    impossible. Deferring a valid out-of-scope finding is success, not
    incompleteness.

  See also [Scope contract and anti-creep](#scope-contract-and-anti-creep)
  below.
- **Evidence** (consolidation / de-duplication entries only): **how identity
  was established**, plus the **do-not-merge look-alikes** the entry excludes
  and why. An eyeballed "byte-identical" is a claim to re-verify, not a fact
  — #79 carried five such claims and four were wrong in the direction that
  breaks things (folding apart durability contracts, confirm gates that share
  an idiom but no implementation, timestamp helpers emitting different
  strings into a drift-guarded format). State the normalization used and the
  count it produced; a pair differing only in parameter names, or only in
  where a local `import` sits, will not group under a naive comparison. The
  excluded set is the half that gets skipped and the half that stops the next
  reader from "finishing the job" — name each exclusion's reason (a test
  seam, a pinned external contract, a differing failure policy, a flag whose
  name matches while its meaning does not).
- **Approach:** `direct`, `plan-tool`, or a conditional. Apply the
  [Direct vs. plan-tool plan](#direct-implementation-vs-plan-tool-plan)
  heuristic at write time and record the verdict here with a
  sentence of justification — saves every future reader from
  re-deriving it.
- **Quality:** (only when the item bears on output/analysis
  accuracy) — the facet(s) from the
  [Quality/accuracy lens](../BACKLOG.md#qualityaccuracy-lens-cross-cutting)
  (`grounding` / `audit-coverage` / `convergence` / `gate-signal` /
  `heuristic-tuning`) plus a clause on *what* about the tool's output
  or analysis this improves. Omit the field entirely for pure
  ergonomics / perf / refactor / cosmetic work, and add the item to
  the lens roll-up when you tag it.
- **Iterate:** (plan-tool entries only) — record only how this entry
  departs from the default recipe, which lives in
  [`DIRECTIVES.md`](../integrations/shared/DIRECTIVES.md) (its two audit gates, `detail` once, `run --commit`
  per step, then the post-run `reconcile-code --all` and code-review tail)
  and is summarized in the phase list above. Name the phases that are
  load-bearing or skippable for this entry and give the concrete
  invocation for any phase that departs; do not copy the whole recipe.
  `--iterate` on `run` belongs only to `--mode reconcile`. Direct entries
  omit this field entirely.
- **Status:** "not started," "design notes only," "plan authored at
  `<path>`," etc.

A skeleton:

```markdown
**Short title — punchy framing of the feature**

- **What:** ...
- **Effort:** ...
- **Risks:** ...
- **Dependencies:** ...
- **Outcome:** one measurable result
- **In scope:** named surfaces / paths
- **Out of scope / Non-goals:** what this deliberately does *not* do; sibling/adjacent work it must not absorb (a seed/plan inherits this fence)
- **Allowed behavior changes:** none beyond Outcome, or list deltas
- **Allowed reorganization:** none, or named move + concrete blocker
- **Verification:** how success is checked without expanding scope
- **Stop / defer:** file separate backlog/bug entries for out-of-scope discoveries; block only if supported behavior cannot be preserved
- **Approach:** direct | plan-tool | direct unless <condition> — <one-line justification>
- **Quality:** (only if it affects output/analysis accuracy) grounding | audit-coverage | convergence | gate-signal | heuristic-tuning — <what it sharpens>
- **Iterate:** (plan-tool only) — departures from the default recipe in
  `integrations/shared/DIRECTIVES.md`, with the concrete invocation for
  each departing phase. Example: `phase 3b essential — mechanical
  re-indent; plan-tool run <slug> --mode reconcile --iterate -y --step 2`
- **Status:** ...
```

### Ordered efforts: seed groups and staged scope

When one effort decomposes into more than one plan **with a required order of
operations**, the order must live in the artifacts, not in an operator's
memory:

- **Seed naming carries the order.** Ordered seeds use
  `docs/implementation-plans/plan-seeds/<group>-NN-<slug>.md` — a shared group name plus a zero-padded
  position (e.g. `quality-bench-01-corpus-and-noise-floor.md`,
  `quality-bench-02-judged-metrics.md`). Prefer the same `<group>-NN-<slug>` as
  the plan slug so manifests, run dirs, and saved reports sort in execution
  order. A standalone seed with no required order keeps a plain slug.
- **One arc, stated once.** The group's **anchor backlog entry** carries
  the full stage arc — each stage's deliverable and the tool state it
  leaves behind. Every other entry and seed in the group cites the anchor
  rather than restating the arc (one authority, no drift). Once the anchor
  is promoted, the Epic's description carries the arc and the anchor's
  [stub](#promotion-stubs) points to it. "Arc" is the
  settled term for this ordered stage sequence ("roadmap" is reserved for the
  project-decomposition pipeline — do not reintroduce it here).
- **Each seed pins its stage's tool state.** A staged seed declares what the
  tool looks like when its plan starts (which earlier stages shipped) and
  names the later stages it must not reach into. **Completeness audits of a
  staged plan judge it against that stage's tool state only:** a finding that
  belongs to a later stage is routed to that stage's seed/backlog entry as
  `[out-of-scope-deferred]` — never applied as expansion of the current plan
  — and per the severity-aware low-yield convention it neither resets low-yield streaks nor
  justifies raising pass caps. Prefer `--audit-passes 1` for
  scope-contract-bound audits of staged plans.
- **Later positions wait.** A later-position seed is deliberately left
  unauthored until its predecessors ship (or its design inputs exist — e.g. a
  stage gated on an evidence report), so its content is grounded in the tool
  state it will actually meet; the anchor entry records the planned seed name
  as a placeholder.

## Scope contract and anti-creep

Substantial backlog entries carry a **scope contract** (Outcome, In scope,
Out of scope / Non-goals, Allowed behavior changes, Allowed reorganization,
Verification, Stop / defer). Seeds and plans inherit it verbatim. See
`SEED_FORMAT.md` for the seed-authoring directives that build on this
contract (density, single-effort focus, destinations-not-turn-by-turn).

**Where it lives.** This is an **authoring** contract — it is carried in the
backlog entry and the seed, and it constrains `create` / `detail` /
`completeness-audit`. It is **not** a set of new required plan-body H2s: the plan
body's only schema-recognized scope carriers are `## Out of scope` and
`## Deferred` (enforced by `check_body_completeness`). The other fields
(Allowed behavior changes / reorganization, Verification, Stop / defer) live
in the seed/entry and in Overview/Architecture prose, and the audit honors
them as guidance. Promoting any of them to a first-class, schema-checked plan
section is deferred to a future item — until then, do not expect the
deterministic body checker to enforce them.

### Reorganization limits

Reorganization is permitted **only** when a named current ownership boundary
prevents the stated Outcome.

- **Allowed:** the smallest extraction or seam that creates one authoritative
  owner or telemetry/lifecycle seam for the Outcome.
- **Proof required:** before a seed or plan adds a reorganization step, cite
  the ownership boundary and the concrete blocker showing why the Outcome
  cannot be delivered safely through the existing boundary.
- **Forbidden:** broad cleanup, directory reshaping, generic frameworks,
  unrelated behavior normalization, or absorbing sibling arc items.

### Stop / defer during create, detail, completeness, and implementation

1. Ask: does this change deliver the entry's **Outcome**, or a different one?
2. If different → new backlog/bug entry or Deferred section. Do not add steps.
3. A valid finding is **not** automatic scope. High impact does not override
   an explicit Non-goal.
3a. **Duplication you notice in passing is a finding, not a chore.** Opening
   two modules for unrelated reasons and seeing the same helper twice is how
   consolidation opportunities surface — nearly always mid-task. File a
   `BACKLOG.md` entry and move on; folding it in now is scope creep wearing a
   "while I'm here" disguise, and the merge carries a home decision, a
   call-site sweep, a leaf/cycle check, and tests that this entry's Outcome
   does not cover. A note in `.tmp/` does not count as filed — that tree is
   transient.
4. Completeness audits must remain inside the declared contract; tag
   out-of-scope findings `[out-of-scope-deferred]` (kebab-case anchor, INFO
   or LOW) and do not auto-apply them. This is a prompt/operator convention
   until the sampler keys on it.
5. Prefer `--audit-passes 1` (CLI default remains `3`) plus one verification
   pass; extend only for unresolved **in-scope HIGH/CRITICAL** findings and
   record why. Out-of-scope or advisory findings never justify raising
   `--audit-passes`.
6. Label stops using the emitted coverage fields — do not invent parallel
   vocabulary: `confirmation_kind=confirmed-dry`,
   `confirmation_kind=confirmed-low-yield`, `budget_limited=true`, or
   `recommendation_kind=non-converging`. Do not call a bounded pass
   converged merely because its budget ended.

## Architectural map

**The module-by-module map lives in [`docs/ARCHITECTURE.md`](ARCHITECTURE.md)**,
and the normative rules that govern it — the invoker seam, the cycle-free import
constraints, the CLI layering, the exit-code convention, the parallelism
posture — live in `CLAUDE.md` § "Architecture". This section deliberately keeps
no second copy: a module list inlined here drifts from the code while the
maintained doc stays correct.

What a *scoping* read needs from this file, and all it needs, is the three
invariants an entry's fence has to respect:

- **`convergence` has no first-party imports**, and the same rule holds for the
  other pure leaves (`checkpoint`, `scope_guard` modulo `schema` for typing).
  Keeps the dependency graph a tree. `CLAUDE.md` § "Architecture" enumerates
  every edge a change must not add.
- **`apply_finding` snapshots only plan + detail.** Code edits Claude makes
  during an apply are *not* in the launcher's snapshot — `scope_guard` catches
  them post-hoc, and `compute_drift_watched_paths` excludes plan/detail so
  `apply_finding`'s own legitimate edits don't read as drift.
- **Plan is canonical when code drifts from spec.** The default direction is
  "update code"; "update plan" requires a recognized improvement justification,
  enforced by `apply_finding`'s `allowed_justifications` under `--strict-intent`.
  Which verb points which way is `CLAUDE.md`'s reconcile-directionality rule —
  `reconcile-plan` is pre-execution, `reconcile-code` post-execution.

## How to author a new plan

**The canonical recipe is [`integrations/shared/DIRECTIVES.md`](../integrations/shared/DIRECTIVES.md)**
— the two audit gates (bare-plan before `detail`, detail-grounded after), the
convergence loop and its three exits, `--iterate` / `--commit` rules, reconcile
directionality, and the post-run tail. Read it there rather than from a recipe
pinned in this page. A recipe that authors with `--no-iterate` is out of date;
the directives supersede it.

The short form, for scoping an entry:

```bash
# 1. Write the seed. SEED_FORMAT.md is the authoring directive.
#    Backlog-derived seeds name their source entry (and ticket key, once
#    promoted) and require the plan to reconcile it — see "Adding a new
#    entry" above.
$EDITOR docs/implementation-plans/plan-seeds/<slug>.md

# 2. Author the plan. --iterate is ON by default; do not opt out.
plan-tool create <slug> -y --from-existing docs/implementation-plans/plan-seeds/<slug>.md

# 3. Early design gate, while the plan is still bare.
plan-tool completeness-audit <slug> --iterate --audit-passes 1 -y
#    Make a session-directed edit for the material plan-level gaps, then re-audit.

# 4. Per-step detail. --iterate stays OFF (one-shot); --commit is per-step.
plan-tool detail <slug> -y --commit

# 5. Detail-grounded gate. The audit converges only the deterministic
#    findings; close the conceptual gaps through a session-directed edit, or with
#    `completeness-apply <slug>` as a human at a TTY.
plan-tool completeness-audit <slug> --iterate -y

# 6. Execute. --commit keeps the tree clean between steps, which the
#    test-authoring gate depends on.
plan-tool run <slug> --all --commit

# 7. Post-run tail, then a code-review pass.
plan-tool reconcile-code <slug> --all
```

Notes that are still live:

- `--output-dir` defaults to `docs/implementation-plans/` (project scope).
- Long `--from` arguments are per-string-elided in the run log; very long
  strings still work but get truncated in the log. Prefer `--from-existing`.
- `classify_plan_scope` in `scope_guard.py` routes scope-guard-emitted
  out-of-scope plans by `step.files`; trust the routing rather than passing
  `--output-dir` explicitly for those.

## Useful commands

`plan-tool --help` prints the full intent-organized catalog, and
[`docs/cli/`](cli) carries the generated per-subcommand flag reference
(every flag and default, drift-guarded by `tests/cli/test_cli_reference.py`).
Both are regenerated from the argparse parser, so prefer them to any list
transcribed into prose.

```bash
plan-tool list                          # every plan in this repo's manifest
plan-tool status <name>                 # step-by-step status for one plan
plan-tool list --status                 # roll up cached audit reports
plan-tool validate <name>               # schema-check frontmatter; no claude
plan-tool completeness-audit <name>     # judge the plan's design (reports only)
plan-tool completeness-apply <name>     # apply saved conceptual gaps (human at a TTY)
plan-tool convergence <name>            # is the audit/apply loop converging? no claude, exits 0
plan-tool split-criteria <name>         # why the plan is shaped the way it is
plan-tool reconcile-plan <name>         # code canonical — PRE-execution only
plan-tool reconcile-code <name> --all     # plan canonical — the post-run tail
plan-tool runs <name>                   # run-log history for a plan

uv run pytest tests/ -q -n auto         # full suite, parallel (~28s); prefer this
uv run pytest -m "not integration" tests/ -q   # fast loop during development
uv run pytest -m integration tests/ -q  # integration tier only
```

Two rate-limit / lock recoveries worth knowing without a doc lookup:

```bash
plan-tool --on-rate-limit {wait,switch,stop,ask} <verb> …   # non-interactive policy
plan-tool --force-lock <verb> …          # only when the holder PID is alive;
                                         # dead-PID lockfiles are auto-detected
```
