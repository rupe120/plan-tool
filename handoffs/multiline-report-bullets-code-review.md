# Multi-line finding bullets — review ledger

| Field | Value |
| --- | --- |
| Change | BUG_BACKLOG "A completeness report puts a finding's multi-line body on its bullet without indenting it": every finding bullet indents its continuation lines under the bullet |
| Branch | `fix/multiline-report-bullets` |
| Reviewer | `/code-review high main` in-session (forked), report-only |

## Settled decisions

- One helper, `review.indent_bullet_body`, beside `confidence_label`. Fence delimiter lines (found by `jira_grade.fenced_spans`, the repo's one scanner) are set to the bullet's margin; every other continuation line is dedented by their common margin, so relative indentation inside a fence survives. Blank lines stay empty; the cited text is never rewritten or escaped.
- One bullet formatter, `completeness_report.format_finding_bullet(rec, key)`, serves the two `_fmt_*` functions and the six grouped-report buckets, so the bullet shape changes in one place.
- An applied-outcome bullet whose body is multi-line carries its note and confidence on their own line, so text is never appended to a closing fence.

## Class enumeration

Class: a finding body rendered onto a markdown bullet (or a bullet inside a model prompt) without continuation indentation. Searched by identifier (`rec.body`, `.body.strip()`, `{body}`) and by vocabulary (`- {...}` bullets built from findings).

| Site | Disposition |
| --- | --- |
| `completeness_report._fmt_finding_line`, `_fmt_pending_line` | Fixed, via `format_finding_bullet` |
| `completeness_report` applied-outcome bullet | Fixed (note on its own line) |
| `completeness_phases._render_grouped_report` x6 | Fixed, via `format_finding_bullet`; each site reverted in turn turns a test red |
| `review._render_extract_lessons_prompt` | Fixed (round 1 finding 2; the first enumeration missed it because the body is `.strip()`ed inline) |
| `cli/inspect.py` `validate` console `_emit` | Stays: terminal print, not a markdown list |
| `detail.py` audit print | Stays: collapses the body to one line already |

## Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | A fence indented 4+ spaces beside a column-0 line is pushed to 6+ and reads as an indented code block | **Fixed.** Fence-aware via `fenced_spans`; mixed-margin and `~~~` cases pinned; an unclosed fence's last line stays content |
| 2 | The extract-lessons prompt builder is the same class and was not swept | **Fixed**, pinned by `test_review_lesson_prompt_keeps_a_multiline_body_inside_its_list_item` |
| 3 | Comments still argue "one or two sentences, body sits inline" | **Fixed.** Both comments rewritten |
| 4 | Nine hand-edited formatter sites | **Fixed.** One `format_finding_bullet` |
| 5 | Applied bullet keyed on "multi-line" with a nested conditional | **Fixed.** Explicit if/else; the multi-line rule is documented in place |
| 6 | Import order and line width | **Fixed.** The helper moved out of `completeness_report.py`, taking `textwrap` with it |

Process note: reverting a mutation with `git checkout <file>` discarded the file's uncommitted fixes. Restore mutations from a saved copy, and commit before mutating.
