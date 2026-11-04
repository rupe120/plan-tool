# Step 6 — Reconcile the backlog with command retirement

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `BACKLOG.md` and `BUG_BACKLOG.md` to reflect the retirement completed by steps 3–5. Remove #376 when the retirement ships, retire entries whose work exists only for removed commands, and trim retired portions from entries that still cover surviving behavior. File separate follow-ups for the unreachable granularity-split walk opt-in and stale `.plan-tool/lessons/project.md` guidance. Preserve the complete #369 entry exactly.

## Table of Contents

- [Summary](#summary) — Result and primary boundaries.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Why backlog reconciliation completes retirement.
- [Input](#input) — Dependency outcomes and tracking rules.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two backlog files.
- [Implementation](#implementation) — Entry dispositions and follow-up requirements.
- [Tests](#tests) — Verification for this non-code step.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant decisions and tracking contracts.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries.
- [Deferred](#deferred) — Implementation left to follow-up work.

## Why

`BACKLOG.md` #376 describes retirement as pending, while entries such as #106, #140, and #146 request improvements to commands this plan removes. Other entries mix those commands with work on surviving surfaces, so deleting every matching entry would lose valid work. The backlog must distinguish obsolete requests from remaining work and record adjacent cleanup without expanding retirement into shared review behavior or lesson maintenance.

## Input

- **Steps 3–5:** Consume their completed command, directive, and live-documentation retirement outcomes. Verify against the resulting tree before treating a request as obsolete.
- **Tracking contract:** Follow `docs/TRACKING.md`, especially “Which file does my entry go in?”, “Promotion stubs,” and “Scope contract and anti-creep.” `BACKLOG.md` under “Purpose” requires removal when a feature ships.
- **Protected entry:** Capture the complete `BACKLOG.md` #369 block before editing, including its heading and fields. Its comparison baseline must survive surrounding deletions.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `BACKLOG.md` — remove shipped #376, retire or trim obsolete requests and their working-set references, and file follow-ups that belong in the feature backlog.
  - `BUG_BACKLOG.md` — retire or trim affected defect entries if present and file follow-ups that describe incorrect current behavior.

## Implementation

- **Foundational logic: keep backlog work tied to surviving behavior.** Classify each affected entry as removed-command-only, mixed, surviving, or necessary provenance. Remove obsolete requests; preserve independent work and evidence needed to understand it.

- **Enumerate candidates before editing.** Search both declared files by command identifiers (`completeness-apply`, `direct-run`, `direct-jira`) and by related vocabulary, including conceptual application, parallel application, serial walking, direct pipelines, and structural opt-in. Record each candidate’s disposition in the implementation review evidence rather than creating a separate findings document.

- **Close #376 through the normal shipment rule.** Remove its pending entry or promotion stub only after the dependency outcomes establish shipment. Use the focused commit to identify `completeness-apply-retirement` as the delivered work; do not replace the entry with an extended historical closeout.

- **Retire requests exclusive to removed commands.** Inspect `BACKLOG.md` #106’s detail-bundle gate, #140’s direct-command hardening, and #146’s nested-repository pipeline support against the landed removals. Remove entries whose entire requested outcome no longer has a command to improve.

- **Trim mixed entries by responsibility.** For example, `BACKLOG.md` #114 also covers plan picking for surviving authoring and audit commands; preserve that work while removing the retired application surface. Apply the same rule to reconciliation sweep, commit inventory, telemetry, and performance entries containing retired-command portions. Check surviving consumers before deleting any shared requirement.

- **Sweep dependent prose and links.** Update affected working-set references, titles, dependencies, and vocabulary inside both backlog files. Before changing a heading, check inbound anchor links. Preserve dated origin citations when they remain useful provenance; a command-name zero-match is not the completion rule.

- **Preserve #369 exactly.** Do not change its heading, wording, fields, status, or reference to #376. Removing #376 does not authorize rewriting #369 or deciding the disposition of its remaining `apply_finding` callers.

- **File the granularity-split follow-up without changing shared code.** Ground the entry in `plan_tool/review_walk.py:is_granularity_split_finding()`, its `extra_apply_sources` condition, and `plan_tool/cli/review_actions.py:_build_review_action_fn()`. Confirm that removal of the application walk leaves no surviving production caller opting into that route. Record the unreachable route and the need for a separate disposition; do not reconnect it, remove it, or alter generic review in this step.

- **File lesson maintenance separately.** Identify concrete stale bullets in `.plan-tool/lessons/project.md`, such as guidance naming `plan_tool/cli/completeness_apply_parallel.py:WorktreePool` or the retired application source-rank machinery. Record the affected anchors and a bounded review-and-prune outcome. Do not edit the lessons file or treat every historical command mention as stale.

- **Use the tracking rules for both follow-ups.** Choose `BACKLOG.md` for proposed cleanup or a decision and `BUG_BACKLOG.md` for demonstrated incorrect behavior. Include evidence, scope, verification, and exclusions; check for an existing equivalent before adding an entry. Allocate any new feature-backlog IDs from the current file without renumbering existing entries.

## Tests

This is a non-code step. The test-authoring gate keys on `change_type` and does not apply to this step; no new test files are required.

### Verification (non-code step)

1. `protected_369_entry_is_unchanged` — compare the complete #369 block with the pre-edit baseline and require exact equality.
2. `shipped_retirement_has_no_pending_entry` — confirm #376 no longer appears as open work after dependency completion.
3. `retirement_candidates_have_explicit_dispositions` — repeat identifier and vocabulary searches across both backlog files; explain each remaining relevant match.
4. `mixed_entries_keep_surviving_work` — inspect each trimmed entry against surviving commands and consumers.
5. `followups_record_evidence_without_implementing_cleanup` — confirm both requested follow-ups exist and shared code and lesson files remain untouched by this step.
6. `backlog_ids_remain_unique_and_readable` — run `uv run pytest tests/test_backlog_ids.py tests/test_backlog_readability.py -q`.
7. `backlog_links_and_scope_remain_valid` — check changed links and anchors, then review the diff for edits limited to the declared files.

## Acceptance criteria

- `BACKLOG.md` no longer tracks #376 as pending after retirement ships.
- Requests exclusive to removed commands are absent from the active backlog and its working-set references.
- Mixed entries retain their surviving responsibilities and no longer request work on retired routes.
- The complete #369 entry matches its pre-edit baseline exactly.
- Separate follow-ups record the unreachable granularity-split opt-in and stale lesson guidance, with current evidence and bounded scope.
- Remaining retired-command mentions have an identified surviving purpose, protected-entry requirement, follow-up purpose, or necessary provenance.
- `tests/test_backlog_ids.py` and `tests/test_backlog_readability.py` pass.
- This step changes only `BACKLOG.md` and `BUG_BACKLOG.md`.

## References

- [BACKLOG.md](BACKLOG.md) — Read #376 for retirement scope and #369 for the independent inventory this step preserves.
- [Tracking rules](docs/TRACKING.md) — Use the backlog placement, shipment, entry-format, and scope-contract rules.
- [Convergence evidence arc](docs/implementation-plans/backlog-arcs/backlog-arc-convergence-evidence.md) — Read item 10 for the withdrawn evaluator decision behind direct retirement.
- [Documentation style](docs/reference/documentation-style.md) — Follow “Backlog entries and tickets” when writing the follow-ups.

## Applicable guardrails

- **The plan’s “Step intent”:** Limit reconciliation to shipment bookkeeping, obsolete requests, and the named follow-ups.
- **The plan’s “Scope guardrails”:** Record adjacent cleanup in the backlog without implementing it through this step.
- **The plan’s “Out of scope”:** Leave #369’s caller inventory independent and preserve the behavior and artifacts covered by that fence.

## Deferred

- Granularity-split walk disposition — this step files the follow-up; shared-route removal or reconnection requires separate work.
- `.plan-tool/lessons/project.md` maintenance — this step files grounded cleanup work without editing the lessons.
- Other `apply_finding` authorities — `BACKLOG.md` #369 retains ownership and remains unchanged.
