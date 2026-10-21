> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Update the ingestion, resume, CLI, seed-format, arc, and backlog surfaces to describe the shipped route contract

## Summary

Update the documentation-only surfaces for file-backed seed ingestion after steps 2–6 ship the route contract. Keep `docs/reference/contracts/seed-ingestion.md` as the detailed contract owner, with flow, resume, seed-authoring, README, arc, and backlog pages linking to or accurately summarizing it. The key decision is that `direct`, `normalized`, `split`, and `refused` are explicit selected outcomes, while unmatched-fence input safety and References evidence preflight remain separate no-run-record refusals. On green, no maintained operator-facing page describes file-backed routing as a size-based distill shortcut or raw-passthrough fallback.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation sweep.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — The documentation drift this step closes.
- [Input](#input) — Shipped route and lifecycle surfaces this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation files updated by this step.
- [Implementation](#implementation) — Route, lifecycle, and backlog documentation requirements.
- [Tests](#tests) — Existing route fixtures and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation completion checks.
- [References](#references) — Heading and CLI reference material.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this sweep.
- [Deferred](#deferred) — Work intentionally left outside the documentation closeout.

## Why

The maintained pages describe `plan_tool/create.py:_prepare_create_plan` as a size-gated distill pass that can fall back to raw source text, while steps 2–6 establish a file-backed route decision with source authority, terminal outcomes, checkpoint ownership, and route-aware CLI behavior. Leaving those statements in place misleads seed authors and operators about when a model runs, what can publish, and what a rerun preserves.

## Input

- **Steps 2–5 route result:** Read the landed file-backed result surface from `plan_tool/create.py:CreateResult`, `plan_tool/create.py:create_plan`, and `plan_tool/cli/authoring.py:cmd_create`. Use the shipped field and helper names if they differ from the names in earlier detail files.
- **Step 6 lifecycle:** Read the shipped checkpoint and artifact behavior at `plan_tool/create.py:_finalize_create_plan`, `plan_tool/create.py:archive_existing_source`, and `plan_tool/cli/authoring.py:cmd_create`. The documentation must describe route-owned retention, cleanup, and archival rather than infer them from a normalized payload.
- **Contract home:** Start with `docs/reference/contracts/seed-ingestion.md:## Decisions`, `## Section contract`, and `## Planned terminal lifecycle`. Update this document first, then make the other surfaces point to it instead of copying a competing route table.
- **CLI reference boundary:** `docs/cli/create.md` is the detailed flag reference from step 5. This step verifies it agrees with the shipped behavior but does not edit it.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `docs/how-to/pipeline/create-from-existing.md` — replace the distill-first-pass route diagram and route descriptions with the file-backed preflight, direct assessment, preparation, terminal outcomes, and route-aware archival behavior.
  - `docs/reference/contracts/seed-ingestion.md` — convert the decision record’s planned and current-state language into the shipped contract and retain the sole detailed route/lifecycle table.
  - `docs/how-to/recovery/create.md` — document route-specific checkpoint reuse, retention, cleanup, and rerun boundaries.
  - `docs/how-to/recovery/README.md` — keep shared checkpoint mechanics generic, update the create exit-code summary, and link readers to the per-create route lifecycle.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md` — mark the selected route complete and remove stale active-route guidance while preserving the separate #102 handoff.
  - `SEED_FORMAT.md` — tell seed authors how the References fallback, normalized canonical headings, strict steps, and free-form preparation affect file-backed ingestion.
  - `README.md` — update `## Decision flow` and `## CLI usage` with a concise file-backed route summary and links to the detailed contract.
  - `BACKLOG.md` — close #327, remove it from active queue guidance, and retain the independent status of related entries.

## Implementation

- **Foundational logic:** Document one file-backed create decision from source preflight through a selected terminal route.

- **Keep one detailed route owner.** Make `docs/reference/contracts/seed-ingestion.md` own the full route and lifecycle table. It must distinguish unmatched-fence input safety and References-preflight refusals from the four selected routes: `direct`, `normalized`, `split`, and `refused`.

- **Preserve both preflight exceptions.** State that unmatched-fence protection and `plan_tool/create.py:validate_from_existing_seed` reject before a run record, routing checkpoint, model call, plan, or manifest entry. The latter rejects missing, duplicate, or placeholder References. Neither preflight is a fifth selected route.

- **Name selected-source identity and library ownership.** Document that file-backed CLI and library intake selects `seed_body` when present, even when empty, otherwise `from_description`; a description cannot mask an empty provenance source. State that `create_plan(..., from_existing_path=...)` uses the same route and checkpoint rules but leaves its caller-owned source untouched, while `cmd_create` alone performs clean route-specific archival.

- **Describe direct authority precisely.** In `docs/how-to/pipeline/create-from-existing.md`, show that a direct-ready file-backed source keeps its supplied body and References, receives the required raw-source split assessment, and bypasses generic post-write convergence after publication. Do not describe direct readiness as a byte threshold.

- **Describe create-owned authority precisely.** Document that direct raw body
  and References, plus normalized source-materialized evidence-only fields,
  remain protected through scope rendering, concept synchronization, and
  convergence for that create invocation. Do not claim that this prevents a
  later operator-directed audit from revising the published plan.

- **Describe preparation as exhaustive.** State that a non-direct file-backed source enters one preparation decision that ends as normalized publication, split, or refusal. A failed preparation or invalid direct assessment must not publish raw text, silently enter another route, or create a new public route name.

- **Keep split discoverable.** Document `plan_tool/create.py:SplitProposal` and `plan_tool/cli/authoring.py:_emit_split_proposal` as a successful no-plan, no-manifest result with an operator-visible next action. The raw source remains available for carving.

- **Document lifecycle by route.** Update `docs/how-to/recovery/create.md:## What resumes on a re-run` and `## When checkpoints are kept vs swept` so direct and clean normalized publication discard completed routing checkpoints, split retains its versioned result for retry, and post-preflight refusal removes its terminal routing result while leaving the raw source available. A normalized iteration-incomplete result keeps its raw source and checkpoints, emits no normalized archive artifact, and directs the operator to `plan-tool completeness-audit <slug> --iterate` against the registered plan; it is not resumed by a second create invocation. Keep the shared rules in `docs/how-to/recovery/README.md` free of a second route table.

- **Keep inline compatibility separate.** Explain in `docs/how-to/pipeline/create-from-existing.md`, `SEED_FORMAT.md`, and `README.md` that `--from-existing` follows the file-backed route contract, while inline `--from` retains its separate compatibility behavior. `--no-distill` must not appear as a file-backed bypass.

- **Give seed authors useful guidance without adding validation.** Update `SEED_FORMAT.md:## Conventions` to require one usable References section and explain that complete canonical body headings after case and closing-ATX normalization can select direct ingestion, while missing, duplicate, or placeholder body headings select preparation rather than a broader universal source rejection. Do not tell authors to pad sections or introduce semantic heading aliases.

- **Keep summaries concise.** Update `README.md:## Decision flow` and `## CLI usage` to help an operator choose `--from-existing` and find the detailed contract. Link to `docs/how-to/pipeline/create-from-existing.md` and `docs/reference/contracts/seed-ingestion.md` instead of reproducing the route table.

- **Close the planning surfaces.** Update `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md` and `BACKLOG.md:#327` so they describe the delivered route, no longer present #327 as active planning, and leave #102 as separate work. Remove stale present-tense planning claims rather than retaining them beside the shipped status.

- **Use landed symbols.** Refresh source maps and symbolic references against the completed code. Retain unrelated intent, risk, provenance, collision, and shared-resume guidance unless the route change makes a statement false.

## Tests

- `tests/test_create.py:test_from_existing_reference_eligibility_ignores_fenced_example` — use as the documentation oracle for the References-only preflight and fenced-example behavior.
- `tests/test_create.py:test_file_backed_unmatched_fence_preflight` — use as the documentation oracle for the no-route, no-run-record unmatched-fence refusal.
- `tests/test_create.py:test_create_plan_split_proposal_bypasses_later_phases` — use as the oracle for split’s no-publication and no-later-work boundary.
- `tests/test_distill.py:TestCmdCreateDistillCli.test_split_proposal_saved_and_exit_zero` — use as the oracle for the split success shape and operator-visible worksheet.
- `tests/cli/test_authoring_cmds.py:test_main_create_split_proposal_does_not_stamp` — use as the oracle that a no-plan split does not receive publication-only follow-up work.

### Verification (non-code step)

1. Verify every relative Markdown link added or changed in the eight declared files resolves to an existing repository file and intended heading.
2. Compare each documented terminal outcome with the landed route fixtures in `tests/test_create.py`, `tests/test_distill.py`, and `tests/cli/test_authoring_cmds.py`.
3. Search the declared documentation files for size-gated file-backed routing, raw-passthrough wording, and active #327 planning language; retain only statements that describe the separate inline compatibility path.
4. Verify the contract distinguishes non-destructive public-library success from `cmd_create` archival, and that no page says a valid description can replace an empty selected provenance source.
5. Run the focused route suites without modifying them, then confirm `git diff --name-only` contains only the eight declared documentation files.

## Acceptance criteria

- `docs/reference/contracts/seed-ingestion.md` contains one shipped route/lifecycle table that distinguishes unmatched-fence and References preflights from `direct`, `normalized`, `split`, and `refused`.
- `docs/how-to/pipeline/create-from-existing.md` states that a direct-ready file-backed source keeps raw authority, receives split assessment, and does not use generic post-write convergence.
- Documentation states the selected-source rule and that public file-backed `create_plan` calls leave their source untouched while `cmd_create` owns clean archival.
- `docs/how-to/recovery/create.md` identifies the route-specific checkpoint and artifact outcome for every terminal file-backed result, while `docs/how-to/recovery/README.md` retains only shared recovery rules plus an accurate create exit-code summary.
- Documentation states that split and refused no-plan outcomes roll back a
  collision-created branch binding, and that normalized iteration-incomplete
  recovery uses the existing plan’s completeness-audit command rather than a
  source-path create retry.
- `SEED_FORMAT.md` requires usable References without turning all canonical body headings into universal preflight requirements.
- `README.md` directs operators to the file-backed route contract without presenting `--no-distill` as a file-backed escape hatch.
- `docs/implementation-plans/backlog-arcs/backlog-arc-seed-ingestion.md` and `BACKLOG.md` present #327 as complete and do not list it as active or next work.
- The existing focused route tests pass, all edited relative links resolve, and the documentation diff stays within the declared files.

## References

- [CommonMark Spec 0.31.2 — ATX Headings and Fenced Code Blockshttps: — Verify the heading and fenced-content terms used in seed-authoring guidance.
- [Python argparse — Parser for command-line options and subcommandshttps: — Verify concise CLI flag and exit-behavior descriptions.

## Applicable guardrails

- **The plan’s `## Plan intent`, source authority:** Keep the supplied source authoritative on the direct route and describe preparation as an explicit route, not a silent replacement.
- **The plan’s `## Step intent`, maintained operator surfaces:** Limit this step to aligning documentation and closing the originating planning records after the shipped implementation.
- **The plan’s `## Out of scope`, route boundaries:** Do not document a broader preflight, separate split command, hidden single-plan continuation, heading-alias policy, or changes to downstream authoring contracts.

## Deferred

- Exhaustive create-flag reference changes — `docs/cli/create.md` remains the focused CLI-reference surface from step 5.
- Future routing-policy changes — require a separately selected implementation effort rather than a documentation-only extension.
