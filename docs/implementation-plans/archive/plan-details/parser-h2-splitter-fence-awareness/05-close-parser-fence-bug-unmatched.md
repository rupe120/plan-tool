> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Close the parser fence bug and unmatched-opening risk while keeping the default-off item open

## Summary

Update `BUG_BACKLOG.md` after steps 2, 3, and 4 land. Remove the two records that describe the fixed parser boundary and unmatched-opening defects. Keep the open default-off record in place and update it to state that its prerequisite is complete without claiming the default changed. On green, the backlog accurately distinguishes shipped fence safety from the separate default-change decision.

## Table of Contents

- [Summary](#summary) — The backlog reconciliation outcome.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the backlog must match the landed behavior.
- [Input](#input) — Upstream completion evidence and backlog conventions.
- [Files (creates vs edits)](#files-creates-vs-edits) — The sole documentation file changed.
- [Implementation](#implementation) — Required record removal and retention rules.
- [Tests](#tests) — Documentation verification for this non-code step.
- [Acceptance criteria](#acceptance-criteria) — Observable backlog-state checks.
- [References](#references) — Markdown behavior used to validate the record descriptions.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this documentation-only update.
- [Deferred](#deferred) — Work that remains outside this step.

## Why

`BUG_BACKLOG.md` currently describes the parser’s fenced pseudo-heading bug and unmatched-opening loss as active defects. After the dependent steps deliver and verify their protections, leaving those records open would report code behavior that no longer exists. The separate default-off record remains actionable because this plan deliberately does not change that default.

## Input

- **Steps 2, 3, and 4 completion** — Treat the committed implementation and test results from the dependent steps as the source of truth for closing records. Do not infer completion from `docs/implementation-plans/2-parser-h2-splitter-fence-awareness.md` alone.

- **Backlog record shape** — Preserve `BUG_BACKLOG.md`’s heading-based BUG and RISK records. The default-off item is currently under `## RISK`, so retain its existing classification unless a separate triage decision changes it.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `BUG_BACKLOG.md` — Remove the two closed fence records and refresh the remaining default-off record’s prerequisite status.

## Implementation

- **Confirm the shipped behavior before editing the backlog.** Review the landed results from steps 2, 3, and 4, including `plan_tool/parser.py:parse_body_sections`, `plan_tool/parser.py:split_body_sections`, `plan_tool/parser.py:replace_body_sections`, `plan_tool/scope_fence.py:_fenced_code_spans`, and their upstream regression coverage. This step records completed work; it must not certify an unverified implementation.

- **Remove the closed parser record.** Delete the complete `BUG_BACKLOG.md:### \`parser.py\`'s canonical plan-body H2 splitter has no fence-awareness...` record, including its supporting bullets. Do not retain a “fixed” copy in the active bug backlog.

- **Remove the closed unmatched-opening record.** Delete the complete `BUG_BACKLOG.md:### An unclosed fence in \`scope_fence.py\`'s fence scanner silently drops every H2 section after it, with no error` record. Its former failure mode is now covered by step 3’s refusal behavior and step 4’s concept-sync protection.

- **Keep the default-off record open.** Retain `BUG_BACKLOG.md:### \`extract_h2_sections\`'s \`ignore_fenced_code\`/\`strip_fenced_code\` default to off...` under `## RISK`. Update its Fix or Approach text to state that the parser-fence prerequisite has shipped, while making clear that the defaults remain unchanged and a future change still needs its own compatibility review.

- **Preserve unrelated backlog work.** Leave the other records, including `plan_tool/roadmap_gates.py:validate_draft_seed_content`’s double-frontmatter-parse item, unchanged.

- **Keep this step documentation-only.** Do not edit `plan_tool/scope_fence.py`, parser defaults, production tests, or other backlog files. The rejected alternative is changing the default while touching this record; that would bypass the separate decision and verification work the open entry represents.

## Tests

### Verification (non-code step)

- `verify_closed_parser_record_is_absent` — Search `BUG_BACKLOG.md` for the exact parser fence-awareness record title and confirm it has no match.

- `verify_closed_unmatched_opening_record_is_absent` — Search `BUG_BACKLOG.md` for the exact unclosed-fence record title and confirm it has no match.

- `verify_default_off_record_remains_open` — Confirm the `extract_h2_sections` default-off record appears once under `## RISK`, states that its prerequisite is complete, and does not claim a default change shipped.

- `verify_backlog_matches_landed_behavior` — Confirm the dependent steps’ committed code and regression results support both closed-record removals.

- `verify_documentation_only_footprint` — Confirm the final diff changes only `BUG_BACKLOG.md` and passes `git diff --check`.

## Acceptance criteria

- The active parser fence-awareness record is absent from `BUG_BACKLOG.md`.

- The active unmatched-opening fence record is absent from `BUG_BACKLOG.md`.

- The `extract_h2_sections` default-off record remains open under `## RISK`.

- The remaining default-off record states that its prerequisite is complete and does not state or imply that either default changed.

- The step changes only `BUG_BACKLOG.md`.

## References

- [CommonMark Spec — Fenced code blockshttps: — Use it to verify the fence behavior the closed records describe.

- [CommonMark Spec — ATX headingshttps: — Use it to verify the heading behavior protected by the completed work.

## Applicable guardrails

- **The plan’s “## Out of scope”, default behavior change** — This step must keep the default-off item open and must not change `plan_tool/scope_fence.py:extract_h2_sections` defaults.

- **The plan’s “## Out of scope”, unrelated parser work** — This step must not broaden backlog cleanup into other document shapes, scanners, or parser changes.

- **The plan’s step 5 file list** — Limit the update to `BUG_BACKLOG.md`.

## Deferred

- `plan_tool/scope_fence.py:extract_h2_sections` default change — Leave the default-off backlog record open for separate compatibility and call-site review.

- Further consolidation of `plan_tool/parser.py` and `plan_tool/scope_fence.py` — Leave any work beyond the upstream plan outcome to a separately scoped follow-up.
