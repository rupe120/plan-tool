# Plan seed: retire legacy Jira-grade detail artifacts and readers

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/retire-jira-grade-detail.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

Source: BACKLOG #308 → promoted to IPPT-17 (2026-09-28). This seed carries
that entry's scope contract verbatim, per the backlog-derived-seed rule; the
ticket holds the working brief.

**Decision (user-confirmed 2026-08-24, restated in the entry): fully retire**
the legacy `plan-details/<slug>/jira/` artifact lane and every reader or
selector for it. Do not migrate or retain it as a compatibility input.

## Outcome

One implementation-detail input remains for Jira export: run-grade detail
produces concise Jira stories and the paired developer handoff. Jira-grade
detail has no artifact, selector, reader, or schema anywhere in the tree.

## In scope

- `plan_tool/jira_grade.py` (confirmed still live, 2026-09-28).
- Jira-grade paths in `plan_tool/detail_artifacts.py`.
- Reader selectors in `jira`, `run`, `completeness-audit`
  (`plan_tool/cli/completeness_cmd.py`'s `GRADE_JIRA`/`JIRA_GRADE_VALUES`
  branches, confirmed still live), and `convergence`.
- Their tests, and the related format/CLI documentation.

## Out of scope / Non-goals

- Changing run-grade authoring or its detail contract.
- Recreating a separate Jira-detail route.
- Changing Jira story or developer-handoff rendering, destinations,
  provenance, or publication behavior.
- Rewriting archived historical evidence.

## Allowed behavior changes

The remaining Jira-grade reader flags and live legacy artifacts are removed
as one explicit breaking change; no fallback from an explicit removed
selector is allowed.

## Allowed reorganization

Only removals and the smallest dependency cleanup the selected policy
requires. That includes relocating `fenced_spans`, which `plan_tool/review.py`
imports for two non-Jira-grade parsers (`_find_redirect_heading`,
`_split_audit_fix`). It is **not** a drop-in for
`scope_fence._fenced_code_spans`: `review.py` deliberately accepts fences
indented past three spaces (pinned by
`test_indented_citation_fence_protects_the_boundary`), and `fenced_spans`
reads a line that opens with an inline code span as an unclosed fence, which
`scope_fence` does not. The relocation keeps the first behavior and decides
the second explicitly, rather than silently inheriting whichever one the
new location happens to have.

## Verification

- `plan-tool jira <plan>` exports concise stories and the paired developer
  handoff from a run-grade bundle.
- No CLI or direct reader accepts a Jira-grade selector or artifact.
- Live plan details contain no Jira-grade bundle.
- The full suite is green.

## Stop / defer

Any broader Jira-output redesign is a separate entry — this seed is removal
only, not a redesign of what ships to Jira.

## Dependencies

None — the user has selected full retirement. `#149`'s compact-schema phase
stays blocked until it is re-baselined without this lane (do not fold that
re-baseline into this seed).

## References

- `plan_tool/jira_grade.py` — the lane being removed.
- `plan_tool/detail_artifacts.py`, `plan_tool/cli/completeness_cmd.py`
  (`GRADE_JIRA`, `JIRA_GRADE_VALUES`) — the reader selectors to remove.
- `plan_tool/review.py` — imports `fenced_spans` from `jira_grade.py`; the
  relocation target this seed's "Allowed reorganization" names.
- `JIRA_FORMAT.md`, `DETAIL_FORMAT.md` — the format docs to update.

## Backlog reconciliation

`BACKLOG.md`'s `#308` entry is already a promotion stub pointing at IPPT-17.
No further backlog edit is required when this plan ships.
