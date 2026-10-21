# Step 3 — Remove the IPPT-10 promotion stub after the behavior and tests ship

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Remove the completed IPPT-10 promotion stub from `BUG_BACKLOG.md`. Keep the backlog’s remaining entries and its promotion-stub policy unchanged. Perform this non-code cleanup only after step 2’s behavior and focused tests have landed. Green behavior leaves no IPPT-10 stub in the bug backlog.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the scoped backlog cleanup.
- [Table of Contents](#table-of-contents) — Links to this detail file’s sections.
- [Why](#why) — Why the completed promotion pointer must leave the live bug backlog.
- [Input](#input) — The completed upstream behavior and backlog stub contract.
- [Files (creates vs edits)](#files-creates-vs-edits) — Declared file change.
- [Implementation](#implementation) — Required removal boundary and unchanged tracking rule.
- [Tests](#tests) — Non-code verification for the removal.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Backlog promotion-stub contract.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this cleanup.

## Why

`BUG_BACKLOG.md` currently retains the heading “Structural candidate generation can emit internal row-class names that its validator rejects” with its `IPPT-10` promotion pointer. Once steps 1 and 2 have shipped the prompt vocabulary, bounded correction behavior, and focused coverage, that pointer advertises completed work as still active in the bug backlog.

## Input

- **Step 2 completion:** Depend on step 2’s landed retry behavior and its focused coverage in `tests/test_roadmap_candidate_run.py`; this step does not reimplement or revalidate that behavior.
- **Promotion-stub contract:** Read `BUG_BACKLOG.md`’s `## Triage` guidance and `docs/TRACKING.md`’s `## Promotion stubs` section. They define the stub being removed and the unchanged tracking policy.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `BUG_BACKLOG.md` — Remove only the IPPT-10 heading and its `Promoted` line.

## Implementation

- **Remove the completed stub only.** Delete the `### Structural candidate generation can emit internal row-class names that its validator rejects` entry and its `- **Promoted:** IPPT-10 (2026-09-25)` line from `BUG_BACKLOG.md`.

- **Wait for the upstream result.** Make this edit only after step 2 has landed its behavior and focused tests. The backlog removal must not become evidence that the implementation is complete before the implementation exists.

- **Preserve the surrounding backlog.** Leave the neighboring entries, section structure, and `BUG_BACKLOG.md` `## Triage` rules unchanged. The removal must not rewrite the promotion-stub policy.

- **Reuse the tracking rule unchanged.** `docs/TRACKING.md`’s `## Promotion stubs` section remains the source for how promoted bug entries are represented; this step removes one fulfilled stub and does not change that shared contract.

## Tests

### Verification (non-code step)

The test-authoring gate does not apply because this is a non-code step. Verify:

1. `rg -n 'IPPT-10|Structural candidate generation can emit internal row-class names' BUG_BACKLOG.md` returns no matches.
2. Review `git diff -- BUG_BACKLOG.md` and confirm it removes only the completed heading and promotion line.
3. Run `git diff --check` and confirm the Markdown edit introduces no whitespace errors.
4. Confirm `BUG_BACKLOG.md` still retains its `## BUG` section and adjacent backlog entries.

## Acceptance criteria

- `BUG_BACKLOG.md` contains no IPPT-10 promotion stub.
- `BUG_BACKLOG.md` no longer contains the completed structural-candidate row-class-name heading.
- The diff changes only `BUG_BACKLOG.md`.
- `BUG_BACKLOG.md` retains its existing promotion-stub guidance and surrounding backlog entries.

## References

- [Backlog promotion stubs](../../../TRACKING.md#promotion-stubs) — Read the removal rule and the distinction between a live stub and the Jira work record.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, behavior boundary:** This step must not alter candidate generation, parsing, retry, evidence, or publication behavior.
- **The plan’s “## Out of scope”, lifecycle and parsing limits:** This cleanup must not expand into persistence, parser, selector-era, or approval work.
- **The plan’s step intent, completed-work cleanup:** Limit the edit to removing the fulfilled IPPT-10 stub.
