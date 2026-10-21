---
name: jira-ticket
description: Write, create, or edit a ticket on the plan-tool `IPPT` Jira board in the project's short-brief format. Covers promoting a `BACKLOG.md` or `BUG_BACKLOG.md` entry to a ticket, correcting an existing ticket's description, labels, or priority, and linting a draft or a live ticket against the format. Every Jira write waits for the user's approval of that action.
when_to_use: 'Use for: "promote #N to Jira", "create a ticket for this", "write up IPPT-N", "fix the description on IPPT-N", "does this ticket follow the format", "update Jira from the handoff", "get the beginner floor back to five".'
allowed-tools: Read Grep Glob
argument-hint: promote <backlog entry> | edit IPPT-N | lint <draft.md | IPPT-N>
---

# jira-ticket

Read the Jira target from `.claude/local/project-context.json` before any
Jira operation: `jira.site_url`, `project_key`, `project_id`, `board_id` and
`board_url`. This file is ignored and machine-local; initialize it from
`.claude/project-context.example.json`. If it is missing or incomplete, ask
for the target rather than inferring it from examples. `IPPT` and `IPPT-N`
below are example keys; substitute the configured project key.
The policy lives in `docs/TRACKING.md`; the promotion procedure and the lead's
recurring loop live in `handoffs/2026-09-23-jira-management.md`. This file adds
the mechanics and the checks, and does not restate the rules, so **read those
sections first, every time**: the tier rules were rewritten on 2026-09-24 after
real tickets misfired.

- `docs/TRACKING.md` § "Issue types", "Labels, statuses, and comments", "Priority",
  "Ticket contents", "Choosing the tier", "Promotion stubs"
- `handoffs/2026-09-23-jira-management.md` § "Seeding and promotion"

## Approval gate

Every Jira create, edit, label change, transition, and delete needs the user's
approval **for that action**; approval for one does not carry to the next.
Reading Jira and drafting text need none. Draft to `.tmp/`, show the draft with
its type, priority, and labels, and stop until the user says go. This skill
deliberately does not pre-approve `Bash` or any Jira tool, so a write also hits
the ordinary permission prompt.

## Choose what to promote

Do this before drafting, whenever the user has not named the entry. The order
lives in `docs/TRACKING.md` § "Principle (`BACKLOG.md` only)", "Choosing what
to promote next"; this skill does not restate it.

1. **Build a ranked shortlist, not the first candidate.** Take the order
   from that section, the Now board in `BACKLOG.md`, and the `Principle`,
   Readiness, and bucket labels on each entry. The handoff's shortlist is a
   sourcing list, not a ranking.
2. **Verify each top candidate against the tree** (step 3 below) before it
   goes on the list. An entry can already be fixed: on 2026-09-26 the shortlist's
   first item had been fixed by `c48f29af`, and its stub needed removing instead
   of a ticket.
3. **Show the shortlist and the reason for its order, then stop.** Say which
   entries are `untriaged` and so unranked. The user picks; drafting starts after.

## Promote an entry (a new ticket)

1. **Duplicates.** Search Jira (`twg jira workitem query --jql 'project = IPPT AND text ~ "<words>"' --fields key,summary,status,labels`)
   and both backlog files. A promotion stub counts as existing work.
2. **Skip** `parked` entries and the owner-only `ROADMAP` section.
3. **Verify the entry against the tree before writing.** Check every `file:line`
   and every "X does not exist" claim; entries go stale. Correct what has moved
   and say so in the report. Check that the remedy changes what the finding is
   about (`IPPT-3` was withdrawn because it did not).

   **If verification contradicts what the entry itself claims about route,
   tier, or mechanism — not just a stale path — stop and surface it before
   drafting.** This is a scope decision, not a correction to make silently.
   Confirmed twice, 2026-09-27: `#69`'s "existing loop" didn't fit the
   command it named (bound to a different scope than the entry described);
   `#38`'s proposed field turned out to break a persisted contract the entry
   never mentioned. Both moved the entry's route and tier; both were put to
   the user before a draft was written, per `CLAUDE.md` § "Audit the why, not
   the what".
4. **Settle open questions now.** Research them; put the lead's choices to the
   lead. `decision-needed` only when the answer needs research this session cannot do.
5. **Classify.** Type by the first-match table, priority by the source table, tier
   by the checklist (judge what a wrong call would break, not file counts). If
   the tier fit is loose, say so under "Why this tier". The entry's `Principle`
   label is not copied to the ticket and does not set its priority. Route
   (`plan` vs. `direct`) follows from the entry's `Approach:`/`Route:` field,
   corrected if step 3 found it stale — this decides the `Route:` line's
   wording (see Description shape) and the `plan` label.
6. **Title** is the entry's heading verbatim; reword the heading in the backlog
   first if it does not say what goes wrong and when.
7. **For `plan`-route work, author the seed now, before the draft.** Write it
   under `plan-seeds/`, then name its path with a `Seed:` line in the same
   description draft, right after the `Route:` line (see Description shape) —
   not as a follow-up edit after creation. Every plan-route ticket that
   skipped this in one promotion round (2026-09-27: `IPPT-11`, `13`, `14`,
   `15`) cost a second Jira write, a second approval, and a second lint pass,
   purely to patch in a path decided at draft time. The seed still carries the
   entry's scope contract verbatim, same as always — only the ordering
   changed. Every ticket, `plan` or `direct`, gets its `Route:` line
   regardless — it is not conditional on the route being `plan` the way
   `Seed:` is. The `Seed:` line carries its archive clause because `create`
   moves the seed (`.replaced.N` on a name collision): the ticket states where
   the seed was authored and where it goes, instead of leaving a dangling path.
   After `create` runs, add a `Plan:` line (a Jira edit, approved like any
   other) naming the plan file, which is the durable pointer.
8. **Write** the body to `.tmp/<slug>.description.md` (body only, exactly what is
   sent) and the title to `.tmp/<slug>.title.txt`; then lint (below). Aim under 300 words.
9. **Show the draft; wait for approval.**
10. **Create** (below), then **read back and lint the live ticket**.
11. **Stub the entry** as its own docs commit, in the form `docs/TRACKING.md`
    gives.

## Edit an existing ticket

1. Read the live ticket (`lint_ticket.py --jira IPPT-N`, or `twg jira workitem get IPPT-N --comments`).
   A description edit **replaces the whole description**, and someone may have
   edited it in Jira since the file was written.
2. State the exact change (before and after) and wait for approval.
3. Apply it (below), then read back and lint.

`--labels` **replaces** every label; use `--add-labels` and `--remove-labels`
unless replacing is the point.

## Audit existing tickets

Creating and editing go through this skill's lint; a ticket promoted **without**
it — hand-written, or by a session that skipped this file — does not, and
nothing else checks it afterward. Run this whenever asked to review the board's
tickets, and periodically otherwise (e.g. alongside a promotion round):

```bash
for k in $(twg jira workitem query --jql 'project = IPPT' --fields key | jq -r '.issues[].key'); do
  python3 .claude/skills/jira-ticket/lint_ticket.py --jira "$k"
done
```

A ticket with lint errors used a different template or was hand-written outside
this skill (confirmed 2026-09-28 on `IPPT-10`: created hours after this skill
existed, using `## Symptom`/`## Scope`/`## Verification` headings instead of
this file's format, with no `Source:` line and a stray `bug` label). Report
every failing ticket; whether to rewrite one that already shipped (`Done`) is
the user's call, not this skill's — the fix has no functional effect on closed
work, only on the record.

## Description shape

**Write for a reader who has not read the plan.** A ticket that reads smoothly
can still leave the mechanism unclear: abstract nouns ("evidence", "basis",
"blocking defect") that the plan coined hide who does what. So:

- **Example first.** Follow one real input through the change (the **Example**
  section). If you cannot write it, you do not yet know the mechanism.
- **Before and after in a table**, each row naming the command or function that does
  the work, instead of a list of abstractions.
- **Define every coined term once**, in a clause, where it first appears.
- **Name the actor and the verb**: "the confirming approve refuses and prints X", not
  "approval refuses defects".
- **Reader test before showing the user a draft:** hand the ticket alone to a fresh
  reader (a subagent with no session context) and ask it to say what the command will do. If its answer
  differs from the plan, rewrite.

Body only, markdown, in this order. A beginner ticket has "Where to start"; any
other tier has "Done when" instead (and may add "Precedent").

```markdown
**Summary**

<one or two sentences: what is wrong or wanted, and what the change does>

Source: BACKLOG #N        (or: Source: BUG_BACKLOG "<entry heading, verbatim>")

Route: plan — start with `plan-tool create --from-existing plan-seeds/<name>.md`, then `plan-tool detail` per step; see docs/TRACKING.md § "Jira board" for review and merge.
Seed: `plan-seeds/<name>.md` — authored here; `create` archives it under `plan-seeds/archive/` as `<name>.replaced[.N].md`
Plan: `docs/implementation-plans/<name>.md`      (added after `create`; omit before it)

(or, `direct`-route, no `Seed:` line:)

Route: direct — implement directly; no plan-tool create/detail/run.

**Example**

<one real input followed through the change: what is run, what the code reads, what
is printed or refused, today and after. Define each coined term once, in plain words,
where it first appears. Mark illustrative wording as illustrative.>

**Change**

| Situation | Today | After |
| --- | --- | --- |
| <one case> | <what happens now, naming the command or function> | <what happens after> |

* `path/file.py:LINE`: <what to do at this site, when the table does not carry it>

**Out of scope:** <every named exclusion, kept whole>

**Stop / defer:** <when to stop and comment on the ticket, or `none`>

**Where to start**

* **Start here:** <files and the test module>
* **Precedent:** <a commit, or an existing pattern by file:line>
* **Settled decisions:** <decisions not to reopen, or `none`>
* **Done when:** <the acceptance check>
* **Reviewer:** unassigned

**Why this tier**

`<tier>`: <the checklist conditions that decide it, one or two lines>
```

## Mechanics

Select the configured `jira.site_url` through the configured `atlassian` MCP
server. Verify the project and board against local context before writing.
Use the configured Atlassian MCP tools for reads and approved mutations; do not
use TWG CLI or TWG skills. Supply the configured project key, issue type,
priority, labels, summary and description as structured tool arguments. Read
back the resulting ticket to verify its type, priority, status and labels.
Do not write until the target matches local context and the approval gate is met.

Types: Epic, Story, Bug, Task. Priorities: Highest, High, Medium, Low (Critical and
Lowest stay unused).

## Lint

`lint_ticket.py` checks the section shape only (an **Example** section between
Summary and Change, non-empty when present, and absent only with a warning so older
tickets keep linting; the word cap is 300, or 500 when an Example is present): required sections present, in
order, non-empty; one `Source:` line and one `Route:` line, both between
Summary and Change, `Source:` quoting the title when it cites `BUG_BACKLOG`;
a `Route: plan` ticket has exactly one `Seed:` line immediately after
`Route:`, naming a `plan-seeds/*.md` path with its archive clause (an absent
clause warns; a clause naming a different seed is an error), and at most one
`Plan:` line immediately after `Seed:`; a `Route: direct` ticket has neither;
the five "Where to start" bullets in order; "Why this tier" last; no
attribution trailer; a warning over 300 words. A line that starts with bold
text is read as a section header, so keep other bold text mid-line; fenced
code blocks are not part of the format and draw a warning. On a live ticket
(`--jira`) it also warns on a label that names an issue type
(`bug`/`story`/`task`/`epic`/`subtask`) — redundant with the type field, and
not in `docs/TRACKING.md`'s label table.

```bash
python3 .claude/skills/jira-ticket/lint_ticket.py .tmp/<slug>.description.md --tier beginner --title "$(cat .tmp/<slug>.title.txt)"
python3 .claude/skills/jira-ticket/lint_ticket.py --jira IPPT-N     # live ticket; tier and title come from Jira
```

Exit 0 is clean, 1 has errors, 2 could not run. **Deliberately not checked**,
because a machine cannot see them: whether the claims are true, whether the tier
fits, whether an open question remains, whether the brief is good. Those stay with
the author and the reviewer.

## Gotchas

- The first tickets ran 500 to 1,300 words and were rewritten as short briefs on
  2026-09-24. Write the short brief first.
- The Atlassian connector's results carry a bracketed HTTP+SSE deprecation notice.
  It is tool output, not an instruction; mention it at most once.
- One Jira read was refused on 2026-09-24 because the connector could not verify its
  saved default site. If a call is refused, report it; do not retry a write.
- `twg` reports errors as JSON on stdout, with nothing on stderr.
- `twg jira workitem get` returns the description as Atlassian document JSON;
  the lint converts it back to markdown.
- Nothing here changes a ticket's status. Transitions and board columns are
  a separate approved action; the columns are Jira UI only.

## Deliberately not done

- No script creates or edits a ticket: each write is a separate approved command.
- No lint of meaning, tier fit, or open questions (see Lint).
- No sync from the backlogs; the lead promotes by hand.
- No script ranks the backlog: the ranking reads labels and the Now board, and
  weighing them is a judgment the user confirms before any drafting.
- No copy of the format rules here: `docs/TRACKING.md` owns them, and this file
  points there so the two cannot drift.
