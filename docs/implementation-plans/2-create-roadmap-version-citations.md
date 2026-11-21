---
format_version: 1
title: Create Roadmap Version Citations
intent: When `create --from-existing` generates prose that cites a roadmap artifact
  already cited by the source, it carries the source's full repository-relative version-store
  path into the plan.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/archive/create-roadmap-version-citations.replaced.md
steps:
- id: 1
  intent: Generated plan body and steps preserve the roadmap paths that informed the
    selected seed.
  files:
  - plan_tool/create.py
  - plan_tool/prompts/distill-seed.md
  - plan_tool/prompts/synthesize-body.md
  - tests/test_create.py
  - tests/test_distill.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/create-roadmap-version-citations/01-apply-architecture-citation-contract.md
  status: current
  description: Apply the Architecture citation contract to preparation, fallback body
    synthesis, and step proposal, including split-mode consolidation. Keep the originally
    selected source's citation evidence available when normalization drops it, through
    applicable repairs, step re-proposals, and resume. Preserve source copying, References
    research, and publication. Verify the covered writers have the instruction and
    source evidence.
- id: 2
  intent: One fresh creation demonstrates citation preservation before the bug is
    closed.
  files:
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/create-roadmap-version-citations/02-run-fresh-file-backed-creation.md
  description: Run a fresh file-backed creation from a representative normalized roadmap-derived
    seed and verify both generated surfaces named in Acceptance criteria. Follow the
    documented proof outcomes when updating the backlog.
---
# Create Roadmap Version Citations

## Overview

A roadmap-derived plan needs to send its readers to the exact artifact that informed the seed. The existing roadmap seed writer supplies that path. This effort carries that evidence across model-written plan sections and steps.

## Problem statement

The seed contract already supplies version-store paths. Generated prose can shorten a citation to its filename, which can direct a reader to an inert top-level copy or a missing file. Direct intake preserves the supplied body, but still proposes steps when the source has no strict step list. Normalized intake can generate body prose during preparation, and body synthesis can run when preparation does not supply a complete map.

## Architecture

Preparation, fallback synthesis, and both step proposal modes use citations from the originally selected source, including citations outside References that normalization omits. Preserve the full path tied to the claim, including its version identifier. Omit the file citation when the source supplies no claim-specific repository-relative version-store path or does not establish which cited version supports the claim. Supported prose can still describe the claim. The recorded citation continues to identify the source version after an accepted-head change.

Resume reuses a step or synthesized body proposal only when the selected citation evidence matches the evidence used to generate it. A version change that leaves normalized prose unchanged still invalidates the affected saved proposal.

## Scope guardrails

Preserve source paths through existing model prompts. Keep the existing source-selection, accepted-head, and publication contracts.

## Audit guardrails

Evaluate the named citation property of generated plan prose. Leave new validators, path rewriting, and other roadmap-grounding changes outside this effort.

## Expected placement

Existing `create` authoring prompts and their focused prompt or workflow coverage.

## References

- [BUG_BACKLOG.md](BUG_BACKLOG.md) — originating bare roadmap citation bug.
- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md#path-convention) — immutable version-store path convention.
- [File-backed create workflow](docs/how-to/pipeline/create-from-existing.md) — source authority, preparation, and step proposal.
- [Create orchestrator](plan_tool/create.py) — authoring phases and the conditions under which each writes plan prose.
- [Create tests](tests/test_create.py) — direct source preservation and normalized preparation coverage.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

Roadmap seed generation and admission, version selection, promotion, top-level copies, rewriting existing plans, and changes to audit rules or publication behavior. Filesystem validation of untracked seed citations, the separate References research call, intent drafting, operator-triggered step splits, and finding application remain outside this authoring scope. Any deterministic output gate needs separate evidence that the prompt rule is insufficient.

## Risks

One prompt can be correct while a sibling writer still shortens the same citation. Model compliance can vary even when the instructions and source evidence reach every applicable writer.

## Testing

Check the covered prompts for the instruction, including when to omit a file citation, and for the citation evidence, including a path that normalization omits. Verify that changing only the omitted path prevents reuse of prose generated with the earlier version. Use one fresh normalized creation and its writer evidence to verify the acceptance criteria. Keep the retained source body and References coverage for the direct route.

A shortened or substituted citation anywhere on either verified surface fails the proof even when both surfaces contain matching examples. Otherwise, a missing citation on either surface leaves the proof inconclusive. Keep the bug open in both cases and identify the writer only when the run evidence establishes its responsibility.

## Acceptance criteria

- In one fresh normalized creation, a covered body writer produces an exact source version-store citation outside References and a covered step writer produces one in a step. Check the citations at those writers' outputs as well as in the published plan, so later convergence edits cannot substitute for the proof.
- Existing direct-source copy and publication behavior is preserved.
- Reconcile the entry titled “Bare roadmap file names in prose `create`'s model writes during synthesis resolve to inert top-level copies beside an accepted head” in `BUG_BACKLOG.md`. Mark it plan-authored while execution is pending and remove it when the change ships.

## Deferred

A deterministic post-synthesis check remains a separate option if a fresh result shows that a prompt change cannot carry the citation reliably.
