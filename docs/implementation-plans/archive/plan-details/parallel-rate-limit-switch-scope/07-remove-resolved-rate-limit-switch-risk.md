> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Remove the Resolved Rate-Limit Switch Risk

## Summary

This non-code step retires the active bug-backlog risk for process-wide rate-limit backend switching after steps 3-6 have shipped scoped switching, downstream parallel coverage, and documentation. The primary edit is `BUG_BACKLOG.md`, where the `## RISK` entry `Auto-\`SWITCH\` flips the process-wide backend for all parallel workers` should be removed from the active backlog. `BACKLOG.md` is checked and updated only for stale inbound references that still frame that resolved risk as open. On green, the active bug backlog no longer lists the resolved scoped-switch risk, while live follow-up work such as `BACKLOG.md:#98 — Rate-limit handling under parallel workers: non-interactive policy + de-dup the invoker helpers` remains intact.

## Table of Contents

- [Summary](#summary) — The short version of the cleanup and expected result.
- [Why](#why) — Why the active backlog must stop listing the resolved risk.
- [Input](#input) — The dependency outcomes and backlog conventions this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two markdown files in scope and what may change.
- [Implementation](#implementation) — The recommended cleanup path and boundaries.
- [Tests](#tests) — The grep and review checks that cover this non-code step.
- [Verification (non-code step)](#verification-non-code-step) — The manual verification commands for the cleanup.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for completion.
- [References](#references) — Markdown reference for keeping edits valid.
- [Deferred](#deferred) — Related work that stays out of this cleanup.

## Why

Steps 3-6 make rate-limit backend switches scoped to the current invoke, prove that behavior through parallel apply, and document the operator contract. Leaving `BUG_BACKLOG.md:## RISK` with `Auto-\`SWITCH\` flips the process-wide backend for all parallel workers` tells future triage that the cross-worker backend leak is still outstanding. The cleanup matters because both `BUG_BACKLOG.md:How to use it` and `BACKLOG.md:Purpose` say active backlog files should represent current work, not completed history.

## Input

- **Step 6 dependency:** step 6 documents scoped rate-limit switch behavior after steps 3-5 land the implementation and coverage. This step should run only after that dependency is true.
- **Bug backlog convention:** `BUG_BACKLOG.md:How to use it` says fixed items are removed, not marked fixed in place.
- **Empty-section convention:** if deleting the resolved risk leaves `BUG_BACKLOG.md:## RISK` with no entries, use the file's existing empty-section style if present; otherwise keep the heading valid and add a plain `_(none outstanding)_` marker.
- **Feature backlog convention:** `BACKLOG.md:Purpose` says shipped feature entries leave the active backlog, but this step is not retiring every rate-limit follow-up.
- **Live follow-up boundary:** `BACKLOG.md:#98 — Rate-limit handling under parallel workers: non-interactive policy + de-dup the invoker helpers` tracks repeated prompts under parallel workers and helper duplication. Preserve it unless a sentence still describes the scoped backend leak as unresolved.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `BUG_BACKLOG.md` — Remove the resolved `## RISK` entry `Auto-\`SWITCH\` flips the process-wide backend for all parallel workers`; keep the `## RISK` section shape valid if it becomes empty.
  - `BACKLOG.md` — Sweep for inbound references to the retired risk and repair only wording that still frames cross-worker backend switching as an open defect. Leave live follow-ups such as `#98` and `#101` in place when they track different remaining work.

## Implementation

- **Foundational logic:** resolved-risk backlog retirement.

- **Delete the active risk entry.** Remove the full `BUG_BACKLOG.md:Auto-\`SWITCH\` flips the process-wide backend for all parallel workers` block from `BUG_BACKLOG.md:## RISK`. Do not replace it with a "fixed" note; git history and this implementation plan are the record.

- **Keep `BUG_BACKLOG.md:## RISK` readable.** If no other risk entries remain after deletion, leave the heading in place and add `_(none outstanding)_` under it. Do not disturb `BUG_BACKLOG.md:## BUG` or `BUG_BACKLOG.md:## MINOR`.

- **Repair stale inbound references.** Search `BUG_BACKLOG.md` and `BACKLOG.md` for these phrases before editing:
  - `Auto-\`SWITCH\``
  - `process-wide backend`
  - `cross-worker`
  - `parallel workers`
  - `fallback-backend`
  - `#98`
  - `rate-limit switch`

- **Edit only stale status claims in `BACKLOG.md`.** If `BACKLOG.md:#98 — Rate-limit handling under parallel workers: non-interactive policy + de-dup the invoker helpers` or `BACKLOG.md:#101 — Factor out the duplicated rate-limit retry loop shared by \`shell.claude_invoke\` and \`launcher.shell_invoker\`` still says the scoped backend leak is open, rewrite that sentence so it no longer points to the retired risk. Keep any remaining work that is truly still live, especially repeated operator prompts under `--jobs N` and helper deduplication.

- **Do not broaden the cleanup.** This step does not edit `README.md`, `RUNBOOK.md`, `CLAUDE.md`, or `docs/design-plans/BACKEND_SELECTION.md`; step 6 owns operator and maintainer documentation. This step also does not touch `plan_tool/backend.py`, `plan_tool/shell.py`, `plan_tool/launcher.py`, or `tests/cli/test_completeness_apply_parallel.py`; steps 2-5 own those behavior and coverage changes.

- **Avoid new tracking entries.** Do not create a replacement backlog entry for the retired risk. If the sweep finds a different live issue, leave the existing live backlog entry in place or route it as a separate follow-up outside this step.

## Tests

- `BUG_BACKLOG resolved-risk sweep` — ``rg 'Auto-`SWITCH` flips the process-wide backend|process-wide backend for all parallel workers' BUG_BACKLOG.md BACKLOG.md`` finds no active outstanding-risk wording.
- `BUG_BACKLOG section-shape check` — manual markdown review confirms `BUG_BACKLOG.md:## BUG`, `BUG_BACKLOG.md:## RISK`, and `BUG_BACKLOG.md:## MINOR` still have valid headings and readable content.
- `BACKLOG live-follow-up check` — `rg '#98|#101|rate-limit' BACKLOG.md` shows live follow-ups remain only for repeated prompts, helper duplication, or other distinct work, not the retired scoped-switch leak.
- `Markdown render check` — a normal markdown preview or lint pass shows no broken list indentation around the edited sections.

### Verification (non-code step)

This is a non-code step. No unit test ordering applies.

Run the verification as document checks:

- ``rg 'Auto-`SWITCH` flips the process-wide backend|process-wide backend for all parallel workers' BUG_BACKLOG.md BACKLOG.md``
- ``rg 'Auto-`SWITCH`|cross-worker|process-wide backend|fallback-backend|parallel workers|rate-limit switch|#98|#101' BUG_BACKLOG.md BACKLOG.md``
- Manual read of `BUG_BACKLOG.md:## RISK` to confirm the resolved entry is gone and the section is still valid.
- Manual read of `BACKLOG.md:#98 — Rate-limit handling under parallel workers: non-interactive policy + de-dup the invoker helpers` to confirm it still tracks the live repeated-prompt/helper work and no longer depends on the retired risk.

## Acceptance criteria

- `BUG_BACKLOG.md` no longer contains the `Auto-\`SWITCH\` flips the process-wide backend for all parallel workers` entry.
- `BUG_BACKLOG.md:## RISK` remains present and valid after the deletion, with `_(none outstanding)_` if no risk entries remain.
- `BACKLOG.md` contains no wording that frames the scoped backend leakage risk as still unresolved.
- `BACKLOG.md:#98 — Rate-limit handling under parallel workers: non-interactive policy + de-dup the invoker helpers` remains present unless a separate plan decision retires it.
- No files outside `BUG_BACKLOG.md` and `BACKLOG.md` are edited by this step.

## References

- [CommonMark Specification](https://spec.commonmark.org/) — Use this to keep heading, list, and emphasis syntax valid while editing the markdown backlog files.

## Deferred

- **Operator and maintainer docs** — Step 6 owns `README.md`, `RUNBOOK.md`, `CLAUDE.md`, and `docs/design-plans/BACKEND_SELECTION.md`.
- **Backend implementation or tests** — Steps 2-5 own scoped backend helpers, shell/launcher wiring, and parallel apply coverage.
- **Repeated rate-limit prompts under parallel workers** — Keep this live under `BACKLOG.md:#98` unless a separate implementation retires it.
- **Rate-limit retry-loop helper deduplication** — Keep this live under `BACKLOG.md:#101` unless a separate refactor plan ships it.
