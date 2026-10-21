> **Withdrawn 2026-08-19**: this seed fed a plan whose premise the plan-level
> review rejected. The withdrawn plan is preserved at
> `docs/implementation-plans/archive/2-bad-fix-provenance.withdrawn.2.md`.
> Preserve this source for history; do not edit or re-seed it.

## Overview

Add durable apply→finding provenance so `plan-tool convergence` can issue a recommend-only “likely bad fix / re-check the last edit” advisory when a later finding matches an earlier one and an intervening remedy note exists. First, every apply path—including hand-apply—records an `Annotation`; then the diagnostic joins same-issue identity with that history. The advisory does not change `stop_reason`, exit codes, plan contents, or create a second provenance store.

## Problem statement

A later recurrence alone cannot establish that the last edit caused the issue, so current recurrence and `edit_drift` advice cannot make a bad-fix claim. Claude-session / operator hand-apply edits prose without an annotation, while `DATA_CONTRACT.md` says only the interactive walk populates them. The saved audit history therefore lacks the intervening remedy evidence needed for a reliable recommend-only advisory.

## Architecture

Use one shared writer near `update_annotation` to persist `annotations[rec_id]` entries using the existing `Annotation` shape: finding identity plus `applied` or deliberate decline (`status=skip` with empty `halt_reason`). Interactive walk, `completeness-apply` serial and parallel paths, and a thin completeness-family record CLI all call that writer; the record command accepts a saved completeness report and a recommendation by id and/or anchor.

Determine same-issue identity with ordered, first-decisive tiers: equal finding `id` when both exist; equal `[anchor-slug]` `anchor` when both exist; equal normalized issue skeleton via `_normalize_audit_fingerprint` / body skeleton when no anchor; then title / existing `_matches` tier-3 fuzzy title. Reuse or extend helpers with `_matches` where safe, but preserve existing `_matches` consumer semantics unless tests cover a change. Finding `id` is a fast path, not the sole identity, because wording drift can churn it.

After writer coverage ships, `plan-tool convergence`—and optional completeness iterate stderr when the same evidence is already loaded—emits the advisory only for identity plus an intervening note. Identity without a note keeps existing recurrence / re-decomposition-leaning behavior or silence. `self-seeded-finding` remains `judgment_only` in the audit-shapes registry.

## Out of scope

- Hard edit-drift / iterate stop, exit-code flip, and `--fail-on-findings` changes: this signal is recommend-only.
- Plan mutation, auto split / scope-out / re-seed: owned by `#159` / `#160` / `#168` / `#116`.
- Raw full-body Claude issue similarity and prose “sounds like last edit” grading: not an accepted identity matcher.
- Converting `self-seeded-finding` into a gate or adding a second provenance store: `annotations` carries the note.
- Stage bars (`#91` / `#248`), reporting polish `#260`, four-loop consistency `#261`, Stage 4 `#241` / `#164`, Stage 5 chat, and detail-prompt fence copy (`#229`): separate work.

## Testing

- Verify the shared writer through interactive walk, parallel apply, and the record CLI: each leaves a durable `Annotation` on the sidecar, and removing the writer call makes each site fail.
- Add fixture pairs that prove same-issue tier precedence, equal-`id` fast-path behavior, and `id` churn matching through `anchor` or `_normalize_audit_fingerprint` / skeleton.
- Add synthetic history fixtures proving the diagnostic fires only for identity plus an intervening note and remains silent for identity-only, note-only, mismatched identity, and missing history.
- Verify no import of retired fork/region APIs and no `stop_reason` or exit-code change.

## Acceptance criteria

- Every interactive walk, `completeness-apply` serial or parallel apply, and completeness-family record command writes an `annotations[rec_id]` `Annotation` with finding identity and either `applied` or deliberate decline (`status=skip` with empty `halt_reason`).
- The record CLI can record `applied` or deliberate decline on a saved completeness report by rec id and/or anchor.
- Same-issue matching selects the first decisive tier among equal `id`, equal `anchor` (`[anchor-slug]`), normalized issue skeleton (`_normalize_audit_fingerprint` / body skeleton when no anchor), and title / existing `_matches` tier-3 fuzzy title.
- `plan-tool convergence` emits the recommend-only bad-fix advisory only when same-issue identity and an intervening remedy note are both present.
- The bad-fix signal alone does not alter `stop_reason`, an exit code, `--fail-on-findings`, or `self-seeded-finding`'s `judgment_only` audit-shapes registry status.
- `DATA_CONTRACT.md` lists the expanded annotations producers, DIRECTIVES / `CLAUDE.md` names the record command for hand-apply, and backlog `#231` is updated in the final docs/status step.

## Deferred

- A hard exit keyed on this signal: future entry after this ships.
- Re-seed actuation after a named seam: `#159` / `#160` / `#168` after their own re-premise.
- Valid out-of-scope findings: defer to `BACKLOG.md` / `BUG_BACKLOG.md`.

## Input

The plan consumes saved audit history and its sidecar `annotations[rec_id]` records, using the existing `Annotation` shape (`status`, `note`, and `halt_reason` for deliberate declines). It also consumes finding `id`, `anchor` (`[anchor-slug]`), normalized issue skeleton from `_normalize_audit_fingerprint` / body skeleton, and title / existing `_matches` tier-3 fuzzy title. A saved completeness report is the input for the hand-apply record CLI.
