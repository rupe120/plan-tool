# Manage the Jira board and promote backlog work

How the project lead promotes `BACKLOG.md` and `BUG_BACKLOG.md` entries to Jira
project `IPPT` and runs the recurring triage loop. The policy lives in
[`docs/TRACKING.md` § "Jira board"](../TRACKING.md#jira-board), which keeps the board
deliberately thin: labels carry classification and comments carry nuance. This page does
not repeat that rationale.

Resolve the site, project and board from ignored `.claude/local/project-context.json` and
verify their state with the configured Atlassian MCP server. `twg` reads work. It has no
status or board-column write, and neither does the Atlassian connector, so status and
column changes happen in the Jira UI.

## Seeding and promotion

The project lead promotes work by hand; nothing syncs from the backlog files.
Each Jira write (create, edit, transition, delete) needs the owner's approval
for that action.

1. Search Jira and both backlog files for duplicates. A promotion stub counts
   as existing work.
2. Skip `parked` items and owner-only roadmap work.
3. Settle every open question in the session: research it, and put the choices
   that are the lead's to the lead. Create a `decision-needed` ticket only when
   the answer needs research the session cannot do, and name that research in a
   comment.
4. Apply the first-match issue-type table in `docs/TRACKING.md`. An
   `evidence-gated` item is a Spike: a Task with the `spike` label.
5. Use the entry's heading as the ticket title. If it does not say what goes
   wrong and when, reword the heading first (the stub keeps it and the
   `Source:` line quotes it). Write the description as a short brief in the shape
   `docs/TRACKING.md` § "Ticket contents" gives; it is not a copy of the entry.
6. Set the priority and the labels that apply: Tier (`beginner`,
   `experienced`, or `architect`), `plan` for plan-route work,
   `decision-needed`, `roadmap`, `spike`. Add an "is blocked by" link for
   `blocked-on #N` work.
7. For `plan` work, create the seed under `plan-seeds/` and name the Jira key
   in it.
8. Replace the source entry with the promotion stub defined in
   `docs/TRACKING.md`.
9. Read the ticket back with `twg jira workitem get <key>` and verify the
   labels, priority, links, the Summary section, the `Source:` line, and the
   Why this tier section.

## Recurring management

The lead runs this loop during triage:

1. Triage new backlog entries and tickets labelled `needs-triage`.
2. Keep at least five `beginner` tickets in To Do without `needs-triage` or
   `decision-needed`.
3. Order To Do by the actual work sequence. Priority is a coarse class, not the
   ordering mechanism.
4. Leave `parked` work out of Jira.
5. Require a `plan` ticket's plan pull request to merge before `run`;
   `plan-tool run` refuses until it has.
6. When work ships, remove its promotion stub and confirm it has a changelog
   fragment or the `no-changelog` label. A ticket closed without shipping a
   change closes as Done with a comment saying why and takes `no-changelog`.

## Release management

[`docs/RELEASING.md`](../RELEASING.md) is canonical. Its release check
compares tickets resolved since the previous tag with `changelog.d/`; the
board carries no Fix Version.
