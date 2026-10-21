> **Auto-archived**: this plan was swept on 2026-06-01 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Review Findings And Output Cleanup
status: completed
priority: medium
steps:
- id: 1
  title: 'Make MISSING_PARENT cross-step aware: in check_file_existence, accumulate
    earlier steps'' creates: parents+ancestors into a will-exist set and downgrade
    later steps'' files: matches from MISSING_PARENT to NEW (positional/list order;
    preserve detect_path_style_mismatch counts and the --allow-missing-parent escape
    hatch)'
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  detail: docs/implementation-plans/plan-details/review-findings-and-output-cleanup/01-make-missing-parent-cross-step-aware.md
  status: done
- id: 2
  title: 'De-duplicate report vs walk in cmd_review: when the walk runs, drop the
    Suggested actions block AND slim the per-step status WARN lines to finding counts
    so finding detail lives only in the walk (full detail retained when the walk is
    skipped); cmd_review passes its walk-eligibility decision into assemble_report;
    keep the report (incl. semantic review) and severity banner always; no new flag'
  files:
  - plan_tool/cli.py
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  detail: docs/implementation-plans/plan-details/review-findings-and-output-cleanup/02-de-duplicate-report-vs-walk-cmd-review.md
  status: done
- id: 3
  title: Add a one-line severity-count banner near the top of assemble_report (under
    Metadata/Repo root header) tallying findings by severity across the severity-bearing
    deterministic sources (heuristic, file-check, dependency, completeness, info;
    semantic review is freeform prose, surfaced beside the banner but not tallied),
    reusing the existing severity constants (_FILE_CHECK_MISSING_PARENT_SEV, _HEURISTIC_HIT_SEV,
    etc.) rather than a parallel scheme
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  detail: docs/implementation-plans/plan-details/review-findings-and-output-cleanup/03-one-line-severity-count-banner-near-top.md
  status: done
---
# Review Findings And Output Cleanup

## Overview

Three remaining cleanup items for the `plan-tool review` subcommand, following a prior session's readability fixes (repo-relative paths, hoisted low-confidence disclaimer, semantic-review-leads ordering, collapsed files-coherence INFO block). One is a finding-accuracy correctness fix and two are output/UX improvements. All three live in `plan_tool/review.py` and the `review` CLI command and share test file `tests/test_review.py`. They are to be implemented as three independent, separately-reconcilable steps.

## Problem statement

Three distinct issues remain in `plan-tool review`:

- **MISSING_PARENT is plan-blind across steps.** `check_file_existence` (`plan_tool/review.py`) classifies each declared file's parent directory against the *current* on-disk state only, one step at a time. A pending step whose `files:` entry lives under a directory that an EARLIER step's `creates:` will bring into existence is falsely flagged `MISSING_PARENT`. Created files themselves are already exempt (entries carry `created=True` and `_describe_file_check` returns before the MISSING_PARENT branch), but the *directories* those created files imply do not propagate forward to later steps.
- **Report and walk duplicate every finding.** `plan-tool review` prints the full markdown report (`assemble_report`) AND then walks every recommendation interactively (`extract_recommendations` + `walk_recommendations` in `plan_tool/review_walk.py`). Each finding appears two to three times: in the per-step status block, in the "Suggested actions" block, and as a walk item. For a 14-recommendation review this is a wall of repetition before the user makes a single decision.
- **No at-a-glance severity summary.** The report has no leading tally of findings by severity, so the reader cannot tell what needs action before scrolling.

## Architecture

**Step 1 — MISSING_PARENT cross-step awareness.** Accumulate a plan-wide set of directories that will exist after earlier steps' `creates:` entries (each created path's parent plus all ancestors up to repo root). In the MISSING_PARENT branch of `check_file_existence`, downgrade the classification to `NEW` (an expected creation, not a suspect path) when the parent directory is covered by that accumulated set. **Decision (resolved): positional / list order.** Credit directories created by any step earlier in the `steps` list, mirroring `next_runnable_step`'s list-order iteration (`schema.py:166`). This is the actual default execution order and it still works when `depends_on` is omitted — the common case. The only mis-credit is a step with a *forward* `depends_on` (referencing a higher id), which is rare and at worst suppresses one advisory WARN. Full `depends_on` topological-sort semantics remain out of scope.

**Step 2 — de-duplicate report vs walk.** **Decision (resolved): conditionally drop "Suggested actions"; no new flag.** Keep the full markdown report always — the semantic review (Claude's prose, the highest-value findings) is rendered *only* in the report, never as a walk recommendation (`extract_recommendations` builds recs from the deterministic findings only), so it must not be hidden. Render the "Suggested actions" block only when the interactive walk is *not* going to run (`--no-walk`, non-TTY, or zero recommendations); when the walk runs it supersedes that block, so it is the pure redundancy to cut. **Residual-overlap decision (resolved): also slim the per-step status WARN lines to finding *counts* while walking** (e.g. `Step 3 (pending)  WARN — 2 findings`) so each deterministic finding's *detail* appears exactly once (in the walk) rather than twice (status WARN line + walk item). The per-step status map is retained in every mode as the at-a-glance OK/WARN overview, and its full WARN detail is retained when the walk is skipped — only the redundant detail is collapsed to a count in the walking case. This satisfies the problem statement's "two-to-three times" complaint fully. The severity banner stays in every mode.

**Data flow (resolved):** the walk-eligibility decision is computed in `cmd_review` (`cli.py:7353`) but the affected blocks are built by `assemble_report`. `cmd_review` therefore passes that boolean into `assemble_report` (a new keyword arg, e.g. `walk_will_run: bool`), and `assemble_report` uses it to gate the "Suggested actions" block and the WARN-line slimming. No new *CLI* flag is added — this is an internal parameter threaded from the command into the report builder. Options (a) gate-report-behind-flag and (c) report/walk-mutually-exclusive were rejected because both bury the semantic review by default.

**Step 3 — severity-count summary banner.** Add a one-line summary banner near the top of the report (just under the Metadata / Repo root header, above or alongside the leading semantic review) tallying findings by severity across the severity-bearing deterministic sources — heuristic, file-check, dependency, completeness, and info. Example shape: "2 likely blockers · 4 reconcile hints · 3 path warnings · 8 info". Tally by each source's existing severity constant in `plan_tool/review.py` (`_FILE_CHECK_MISSING_PARENT_SEV`, `_HEURISTIC_HIT_SEV`, etc.); the bucket labels ("likely blockers / reconcile hints / path warnings / info") are display names for those existing severity levels, not a new source→severity classification. No new severity taxonomy or constants are introduced — see Out of scope. The semantic review is freeform prose with no machine-countable severity (it is rendered, never turned into recommendations — see Step 2), so it is not tallied per-severity; it remains surfaced as prose beside the banner. **Zero-findings decision (resolved): always render a clean-state banner** — on a review with no deterministic findings the banner reads an explicit clean line (e.g. `✓ no findings`) rather than being suppressed, so its presence/absence is never ambiguous and a clean review is positively confirmed. Localized to `assemble_report`; no CLI or persistence changes expected.

## References

- [pathlib — Object-oriented filesystem paths (Python docs)](https://docs.python.org/3/library/pathlib.html) — Authoritative reference for PurePath.parent and PurePath.parents, needed to accumulate each created file's parent plus all ancestors up to repo root in Step 1.
- [os.path — Common pathname manipulations (Python docs)](https://docs.python.org/3/library/os.path.html) — Reference for exists/isdir/dirname semantics underlying check_file_existence's on-disk parent-directory classification.
- [pytest — Full documentation](https://docs.pytest.org/en/stable/) — Primary guide for the test framework used in tests/test_review.py to cover the new cross-step, dedup, and severity-banner behaviors.
- [How to use temporary directories and files in tests (pytest tmp_path)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Explains the tmp_path fixture for constructing on-disk file/directory layouts to test MISSING_PARENT vs NEW classification.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- New finding detectors or check categories — this plan only reshapes existing findings' accuracy and presentation.
- A new severity taxonomy or new severity constants — Step 3 reuses the existing constants in `plan_tool/review.py`.
- Full `depends_on` execution/topological-sort semantics — Step 1 only resolves which ordering the will-exist set follows.
- Changes to the interactive walk's prompts or decision flow — Step 2 touches only the report/walk duplication, not walk UX.
- Reworking repo-relative paths, the low-confidence disclaimer, or the files-coherence INFO block — those landed in the prior session.

## Risks

- **Step 1 may regress the plan-wide path-style hint.** `detect_path_style_mismatch` keys off MISSING_PARENT counts; **resolved sequencing:** the detector consumes the *post-downgrade* `FileCheck` list from `check_file_existence`, so a cross-step-covered path (now `NEW`) is correctly excluded from path-style evidence. Counts drop only for the false multi-step new-tree hint; a genuine wrong-repo-root plan with no covering `creates:` downgrades nothing and keeps identical counts.
- **Step 1 must preserve the `--allow-missing-parent` escape hatch.** The existing override behavior must remain intact.

## Testing

All three steps share `tests/test_review.py`.

- **Step 1:** Add tests for cross-step parent creation (an earlier step's `creates:` covers a later step's `files:` parent → `NEW` not `WARN`). Confirm the single-step and no-creates cases are unchanged.
- **Step 2:** Test `assemble_report` with `walk_will_run=True` (Suggested actions omitted; per-step WARN lines collapsed to counts) and `walk_will_run=False` (full Suggested actions block and full WARN detail retained). Confirm the semantic review and severity banner render in both. Update the `cmd_review` tests that thread the walk-eligibility flag.
- **Step 3:** Add tests covering the severity banner tally in `assemble_report`.

## Acceptance criteria

- In `check_file_existence`, a later step's `files:` parent directory that is covered by an earlier step's `creates:` (parent plus ancestors up to repo root) is classified `NEW`, not `MISSING_PARENT`/`WARN`.
- Single-step and no-creates file-existence cases produce unchanged classifications.
- `detect_path_style_mismatch` runs on the post-downgrade `FileCheck` set: it returns `None` for a multi-step plan whose later `files:` parents are all covered by earlier `creates:`, and returns a `PathStyleHint` with unchanged counts for a genuine wrong-repo-root plan with no covering `creates:`. The `--allow-missing-parent` escape hatch behaves as before after the Step 1 change.
- When the walk runs (interactive / `-y`), a `plan-tool review` run prints each deterministic finding's detail exactly once (in the walk): the "Suggested actions" block is omitted and the per-step status WARN lines collapse to finding counts. When the walk is skipped (`--no-walk`, non-TTY, zero recs), the full "Suggested actions" block and full WARN-line detail are retained. No new CLI flag is added; `cmd_review` threads its walk-eligibility decision into `assemble_report`.
- The report includes a one-line severity-count banner near the top tallying findings by severity across the severity-bearing deterministic sources (heuristic, file-check, dependency, completeness, info), using the existing severity constants in `plan_tool/review.py`; the freeform semantic review is surfaced beside the banner but not tallied per-severity. On a review with zero deterministic findings the banner renders an explicit clean-state line rather than being suppressed.

## Deferred

- None yet — no items have been dropped or postponed during implementation.
