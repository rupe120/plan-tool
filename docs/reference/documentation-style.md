# Developer documentation style

*Part of the plan-tool developer docs. Start at [Contributing](../../CONTRIBUTING.md).*

Developer documentation supports scanning before deep reading. It helps a
reader identify the normal path, the exceptions, the owner, and the next
action without first parsing a wall of prose. This guide shapes explanatory
text; it never permits dropping the technical facts that make a contract
actionable.

## Start with the reader's task

Name the reader and the question the section answers before writing it. The
document type sets the expected shape:

| Document type | Reader needs | Start with | Put depth in |
| --- | --- | --- | --- |
| Orientation | Where to begin | Purpose and next action | Links to the relevant guide |
| Workflow | What to do, in order | Normal path | Exceptions and recovery |
| Reference | What owns a behavior | Summary and ownership | Focused subsections and code anchors |
| Policy | What must remain true | Rule and its reason | Examples and the owning contract |
| Historical record | Why a current decision exists | Dated provenance | The current route and its fence |

## Choose the structure that matches the information

| When the reader needs to compare… | Use… |
| --- | --- |
| Owners, commands, terms, or fixed mappings | A table |
| Behavior that changes by state, grade, mode, or lifecycle | A state matrix |
| An ordered action, retry, or escalation path | A numbered flow |
| A normal rule with limited exceptions | The normal rule first, then a short exceptions subsection |
| One cohesive explanation or rationale | A short paragraph with its conclusion first |

A paragraph is not wrong because it is long. Treat a dense paragraph as a
review signal when it combines independent rules, state branches, ordered
actions, or several ownership boundaries. Keep it when splitting it would
hide one cohesive idea.

## Write a section for scanning

1. Lead with the outcome or purpose.
2. Put the normal path before exceptional paths.
3. Give each independent contract its own heading, row, or list item.
4. Explain a term before relying on its abbreviation or code anchor.
5. Link to the canonical deeper guide instead of repeating its operational
   detail.
6. Give each claim an explicit subject, and name what a metric counts instead
   of making the reader recover it from context.
7. Name the decision-maker and writer. A **session-directed edit** is a
   developer-directed coding-assistant edit after judgment; a **direct edit**
   is any artifact change outside a `plan-tool` automatic-apply path. Do not
   use ambiguous manual wording when the distinction matters.
8. Let top-level orientation pages route by task. Put detailed procedures in
   `docs/how-to/`, settled rationale in `docs/explanations/`, and exact
   contracts in `docs/reference/` as those documents are reviewed. Keep stable
   paths until their links have a deliberate migration.

Keep the existing facts while reshaping a section: commands, flags, paths,
symbols, ordering, state conditions, compatibility rules, acceptance criteria,
and the tests or document checks that pin them. A clearer structure is not a
license to weaken a boundary or turn a warning into a rule.

## Backlog entries and tickets

Entries in `BACKLOG.md` and `BUG_BACKLOG.md`, and the Jira tickets promoted from
them, are read by people who have not seen the code. Plain words and full detail
go together: put the precision in the body and say it simply.

- **Heading.** One sentence naming what goes wrong (or what is wanted), when it
  happens, and the visible effect. Name the command or screen a user meets, not
  only the internal module; file paths and function names go in **Files** and
  the body.
- **Say what fails.** Name the failure (an error, a wrong result, a lost
  record), what triggers it, and what it affects. A verb such as "raises",
  "trips", "discards", or "leaks" on its own does not say what happened.
- **Expand shorthand on first use.** Spell out abbreviations and terms of art,
  lint and error codes, and review phrases such as "the same shape as a sibling
  fix" (name the fix). For example, TOCTOU becomes "a check that can go stale
  between the moment it runs and the moment its result is used".
- **Keep every fact in an entry.** Plain is not shorter. Keep the numbers, ids,
  paths, line references, and reproduction steps, and say them simply.
- **A ticket is a brief, not a copy.** Give what someone needs to do the work
  and stay inside its scope, and leave out history and rationale the change
  does not need. `docs/TRACKING.md` § "Ticket contents" gives the shape.

| Before | After |
| --- | --- |
| `manifest sweep` can raise while printing an archive target reached through a symlinked repository path | `plan-tool sweep` fails with an error while printing its report when the repository path goes through a symlink |

Reword an awkward heading when you touch its entry, and always before promotion
(a promotion stub keeps its heading). Readability is a review judgment. Tooling
deliberately does not check it: a word-list or length check measures
vocabulary, not whether a reader understands.

## Generated plan and roadmap prose

Plans, detail files, and roadmap artifacts are written by prompts, and a
developer reviews them before approving. The prompts own the rules; this section
names where each lives so a change lands in one place.

| Prose | Reviewer's question | Rules live in |
| --- | --- | --- |
| Plan body | Is this plan right? | `plan_tool/prompts/synthesize-body.md` § "Writing style" rewords only `Overview`, `Problem statement`, and `Architecture`; every other section is lifted from the seed as written, so its wording is set by `SEED_FORMAT.md`. Section shapes live in `plan_tool/create.py` (`PLAN_BODY_SECTION_SHAPES`). |
| Step title | What does this step do? | `plan_tool/create.py:_render_from_prompt` (the "Write every `title` in plain, everyday words" rule). A long title that carries the step's description is fine. |
| Detail file | What will the implementer build? | `plan_tool/prompts/detail.md` § "Writing style (strict)" |
| Roadmap stages 1–4, `rationale` and `chosen_option` fields | Does this match the brief? | `plan_tool/prompts/roadmap-writing-style.md`, included in each stage prompt as `${writing_style}` |
| Roadmap revisions, candidate rows, candidate questions | What changed and why? | `plan_tool/prompts/roadmap-revision.md` § "Wording" and the candidate prompts |
| Draft seeds | Can `create` and a reviewer both use this? | `plan_tool/prompts/roadmap-seed.md`, `SEED_FORMAT.md` |

The rules every one of them shares:

1. **Plain words.** Write it the way you would say it to a teammate who is new to
   the codebase. Keep identifiers; swap decorative words.
2. **Point first.** Open a section or paragraph with the outcome or decision,
   then the reason.
3. **Define on first use.** A bare id or term of art is not an explanation.
4. **Keep every condition.** Plain must not drop a fact, boundary, or exception.
5. **Structure follows content.** Options, conditions, and ordered steps are
   bullets; a paragraph stays short.

| Before | After |
| --- | --- |
| "An item is on at most one open loan at any moment." | "Only one member can have an item at a time." |

Readability here is a review judgment. Tooling deliberately does not check it:
a word list or length cap measures vocabulary, not whether a reader understands
(see `CLAUDE.md` § "Validating a semantic property you cannot observe").

## Review before committing

- Can the intended reader state the section's purpose and next action after a
  scan?
- Are mappings, state differences, and ordered behavior represented in their
  natural structure?
- Does the normal path come before the exceptions?
- Does every sentence name its actor or subject, including the thing each
  metric counts?
- Does the text distinguish the person who owns a decision from the coding
  assistant that writes a session-directed edit?
- Does a top-level page let a reader choose a task before asking them to read
  its rationale or exhaustive reference material?
- Do links and code anchors still point to the authority that owns the detail?
- Did the edit preserve the concrete facts and update every repeated statement
  of a changed rule?
- For a backlog entry or ticket: does the heading say what goes wrong and when?

Record substantial live-documentation reviews and their fact fences in the
change's [handoff or review ledger](../../handoffs/README.md).
