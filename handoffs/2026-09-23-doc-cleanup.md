# Handoff: general documentation cleanup

This tracks documentation hygiene that belongs to no feature: what is queued,
what is undecided, and what a future session must not "fix". Delete an item when
it closes. Work that has an owner and a fence lives in the backlog; this file
is the index that keeps the loose ends in one place.

## Queued

| Item | Where it is tracked | Next step |
| --- | --- | --- |
| Broken relative links in `RUNBOOK.md` and three dated handoffs | `BACKLOG.md` #426 | Repoint 13 links; decide two with no identified successor. |
| A link-check test | Not filed | Owner decides whether to file it as its own entry (see below). |
| Jira docs vs the real `IPPT` project | [`2026-09-23-jira-management.md`](2026-09-23-jira-management.md) | Seed the first tickets. |
| `CLAUDE.md` evidence extraction | `handoffs/2026-09-17-team-handoff-open-decisions-proposal.md` § 6 | Move the multi-paragraph measurements to `docs/evidence/`; keep the rule and a short verdict. Needs Architect review. |
| Bucket C to readiness, per entry | The same handoff, decision 7 | Check each entry the "Readiness lens" section once called bucket C against its actual readiness label. |
| Route, readiness, and tier labels | `docs/TRACKING.md` § "Labels every entry carries" | Count coverage with `grep -c '^- \*\*Route:\*\*' BACKLOG.md` (likewise `Readiness:` and `Tier:`) against `grep -c '^\*\*#[0-9]* — ' BACKLOG.md`. Tag an entry when someone next touches it. |
| One stale citation in a roadmap plan detail | The 09-17 handoff, "for the roadmap owner" | `docs/implementation-plans/archive/plan-details/roadmap-decision-settlement/07-document-settlement-route-retire-every.md` line 77 cites `BUG_BACKLOG.md:275`. Fix it at that plan's next re-audit: editing the detail makes its saved reports stale. |

## Broken relative links: the scan

The scan finds **142** broken relative links in tracked markdown. Only 13 are a
defect that is in scope to fix now.

| Count | Where | What it is | Action |
| --- | --- | --- | --- |
| 81 | 17 plan and plan-detail files under `docs/implementation-plans/` | Frozen once audited. Not classified further. | Leave. Editing one makes its saved audit reports stale. |
| 26 | `tests/fixtures/reformat/` (2 files) | Fictional links in test input. | Leave. |
| 12 | The four `SKILL.md` copies, all to `DIRECTIVES.md` | **Not broken.** `plan-tool install-skill` writes `SKILL.md` and `DIRECTIVES.md` into one directory, so they resolve once installed. | Leave. Repointing them would break them there. |
| 10 | `RUNBOOK.md` | Docs renamed or deleted by a docs restructure. Eight have a likely new home that exists; two have none identified. | `BACKLOG.md` #426. |
| 8 | Two archived design plans under `docs/design-plans/archive/` | Frozen. | Leave. |
| 3 | Two dated handoffs | Docs renamed to `docs/explanations/`. | `BACKLOG.md` #426. |
| 2 | `lessons/general.md` | Fictional examples (`app://nope`, `other.md#slug`), not links. | Leave. |

The scan reads every tracked `*.md` outside `docs/implementation-plans/archive/`,
`plan-seeds/archive/`, `.plan-tool/`, and saved `reports/`, drops fenced code
blocks, and resolves each markdown link target that is not `http`, `mailto`, or an
in-page anchor against the file's own directory:

```python
import os, re, subprocess
files = subprocess.run(["git", "ls-files", "*.md"], capture_output=True, text=True).stdout.split()
skip = ("docs/implementation-plans/archive/", "plan-seeds/archive/", ".plan-tool/")
fence = "`" * 3  # built, not written, so this block holds no fence characters
fenced = re.compile(re.escape(fence) + ".*?" + re.escape(fence), re.S)
broken = []
for f in files:
    if f.startswith(skip) or "/reports/" in f:
        continue
    text = fenced.sub("", open(f, encoding="utf-8", errors="replace").read())
    for m in re.finditer(r"\]\(([^)\s]+)\)", text):
        target = m.group(1)
        if target.startswith(("http", "mailto", "#", "<")):
            continue
        path = target.split("#")[0]
        if path and not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(f), path))):
            broken.append((f, target))
print(len(broken), "broken relative links")
for f, target in broken:
    print(f"{f}: {target}")
```

## A link-check test: undecided

The same defect (docs moved or renamed, citers not swept) recurs: it has hit
`BACKLOG.md`'s links, the decisions log and two handoffs, and one live doc. A
test would catch the next one. A project rule says one
Outcome per entry, so it would be its own backlog entry, not part of #426. It
must treat three groups as exceptions, or it starts red at the baseline above:
the installed-layout links in the `SKILL.md` copies, the fixtures, and the frozen
plan and plan-detail files. Nothing is filed; the owner decides.

## Jira docs vs the real project

`docs/TRACKING.md` § "Jira board" describes the board, and
[`2026-09-23-jira-management.md`](2026-09-23-jira-management.md) owns the
ticket seeding.

## Settled: do not reopen

- The `DIRECTIVES.md` links in the `SKILL.md` copies are correct as installed.
  A link scan flags them; they are not defects.
- Frozen plan and plan-detail files are not edited for link hygiene.
- A dated handoff may take a path-only repoint when the owner asks. Nine links in
  two handoffs have had one.
- `BACKLOG.md` #191 and #217 look stale but are not: each describes genuinely open
  remaining scope (half shipped, with a "what remains" section). Leave them.
