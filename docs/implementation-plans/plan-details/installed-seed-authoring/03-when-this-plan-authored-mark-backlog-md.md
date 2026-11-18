# Step 3 — Keep #377 open until installed seed guidance ships

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Use the linked `Plan authored` status in `BACKLOG.md` to keep #377 visible while implementation or verification is pending. That status already points to `docs/implementation-plans/2-installed-seed-authoring.md`. Remove only the #377 entry once the guidance ships and step 2 confirms that the required source-install and isolated wheel checks pass, including explicit `--copy`.

## Table of Contents

- [Summary](#summary) — When #377 stays open and when it closes.
- [Table of Contents](#table-of-contents) — Where to find the closure rules and checks.
- [Why](#why) — What the backlog status tells a reader.
- [Input](#input) — The plan link, shipment status, and verification evidence.
- [Files (creates vs edits)](#files-creates-vs-edits) — The backlog entry this step owns.
- [Implementation](#implementation) — How to retain or close the entry.
- [Tests](#tests) — How to verify the evidence and the backlog diff.
- [Acceptance criteria](#acceptance-criteria) — The observable backlog state before and after closure.
- [References](#references) — The tracking rule, plan, and verification procedure.
- [Applicable guardrails](#applicable-guardrails) — The limits on bookkeeping and release review.
- [Deferred](#deferred) — Work tracked by #510 and #378.

## Why

`BACKLOG.md` tracks delivery. The `Status` field under `#377 — Teach installed plan-tool skills to author and validate plan seeds` lets a reader find the authored plan while the work is still open. The source and isolated wheel checks cover different installation paths, so closure needs evidence from both.

## Input

- Use the linked `Plan authored` status in `BACKLOG.md` and confirm that its target is `docs/implementation-plans/2-installed-seed-authoring.md`.
- Use step 1’s shipped guidance and router links, and step 2’s source-install and isolated wheel results for that guidance. Check step 2’s `## Acceptance criteria` for the required evidence, including the installed links and the two seed examples. Both installation checks cover Claude, Codex, and Cursor in default and explicit `--copy` modes.

## Files (creates vs edits)

- **New files** — None.
- **Existing files (edits only)**
  - `BACKLOG.md` — Keep #377’s linked authoring status while the work is pending. Remove the #377 entry when the closure conditions are met.

## Implementation

- **Foundational rule — shipment and passing checks together close #377.** Apply the existing unpromoted-entry rule in `docs/TRACKING.md` under `Promotion stubs`. The current `Status` field already records plan authorship. Keep the full entry and its link while shipment or any required result is pending, missing, or failing.
- **Check the evidence before removing the entry.** Confirm that step 1’s guidance ships and that step 2’s source and isolated wheel results cover the guidance that ships. Default Codex installation copies files, but that result does not cover an invocation with explicit `--copy`.
- **Limit the removal to the #377 entry.** Find it by its bold entry opener in `BACKLOG.md` and use the next entry opener, `#378`, as the end boundary. The installed-skill arc summary, the priority list, and other entries also cite #377. Use the entry boundaries to scope the deletion and preserve those references. A direct backlog edit is enough because step 2 already supplies the evidence needed for the decision.

## Tests

### Verification (non-code step)

`plan_tool/launcher.py:_step_requires_test_authoring()` exempts `non-code` steps from the test-authoring gate. Use the following checks for this backlog edit.

1. **Open entry and link** — While shipment or any required check is pending, failing, or missing, confirm that the full #377 entry remains and its status link opens the Installed Seed Authoring plan.
2. **Closure evidence** — Before removal, confirm shipment and review step 2’s source-install and isolated wheel results. Check for a passing result in both modes for each backend, including the explicit `--copy` invocation for Codex.
3. **Diff boundary** — Review `git diff -- BACKLOG.md` against the pre-edit state. Confirm that closure removes the #377 entry and preserves both neighboring entries and #377 references elsewhere in the file.
4. `tests/test_backlog_ids.py:test_backlog_entry_ids_are_unique` — Remaining backlog entry IDs are unique.
5. `tests/test_backlog_readability.py:test_backlog_is_fully_readable_by_the_id_guard` — The backlog remains readable by the entry ID check.

## Acceptance criteria

- While shipment or any required verification is pending, missing, or failing, `BACKLOG.md` contains the full #377 entry with a working `Plan authored` link.
- After the guidance ships and all step 2 acceptance checks pass, including explicit `--copy` in both the source-install and isolated wheel runs, the #377 entry is absent.
- The closure diff touches only the #377 entry in `BACKLOG.md`. The #378 and #510 entries remain intact, and both backlog checks pass.

## References

- [Tracking rules — Read the unpromoted-entry rule under Promotion stubs](../../../../docs/TRACKING.md#promotion-stubs)
- [Installed Seed Authoring — Read the source-entry obligation and acceptance criteria](../../2-installed-seed-authoring.md#acceptance-criteria)
- [Step 2 — Review the installed-guidance checks required for closure](02-extend-existing-install-skill-coverage.md#acceptance-criteria)
- [Backlog — Find #377 by its entry title and Status field](../../../../BACKLOG.md)

## Applicable guardrails

- **The plan’s `## Scope guardrails`, tracking boundary.** Limit edits to #377 bookkeeping in `BACKLOG.md`.
- **The plan’s `## Audit guardrails`, review boundary.** Base closure on the installed authoring path and the plan’s acceptance evidence. Public onboarding sign-off has its own owner.
- **The plan’s `## Expected placement`, guidance ownership.** Use the installed shared reference as evidence of shipment. Keep authoring instructions in their owning documents.
- **The plan’s `## Out of scope`, tracker boundary.** Apply the existing closure rule only to the originating entry. Tracker policy stays with its existing owner.

## Deferred

- Public first-task onboarding — `BACKLOG.md` #510 owns the walkthrough that uses the shipped seed guidance.
- Tracker discovery and stale-entry handling — `BACKLOG.md` #378 owns those rules.
