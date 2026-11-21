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
  intent: Generated plan body and steps preserve the roadmap paths that informed the selected seed.
  files:
  - plan_tool/create.py
  - plan_tool/prompts/distill-seed.md
  - plan_tool/prompts/synthesize-body.md
  - tests/test_create.py
  - tests/test_distill.py
  complexity: medium
  change_type: feature
  status: current
  description: Instruct existing preparation, step proposal, and fallback synthesis
    calls to preserve the full version-store path when citing a roadmap file named
    by the selected source. Carry the source evidence into applicable repair and step
    re-proposal calls. Use the seed's own path, including its recorded version. Preserve
    source-body copying, References, and publication. Verify the applicable prompts carry
    both the instruction and the source path.
- id: 2
  intent: One fresh creation demonstrates citation preservation before the bug is closed.
  files:
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  description: Run a fresh file-backed creation from a representative roadmap-derived
    seed and inspect the citations in model-written prose and steps. Compare them with
    the source path. A matching copied References entry alone is insufficient. Close the
    originating backlog entry after verification. Retain it with the failing writer
    identified if the proof fails.
---
# Create Roadmap Version Citations

## Overview

A roadmap-derived plan needs to send its readers to the exact artifact that informed the seed. The existing roadmap seed writer supplies that path. This effort carries that evidence across model-written plan sections and steps.

## Problem statement

The seed contract already supplies version-store paths. Generated prose can shorten a citation to its filename, which can direct a reader to an inert top-level copy or a missing file. Direct intake preserves the supplied body, but still proposes steps when the source has no strict step list. Normalized intake can generate body prose during preparation, and body synthesis can run when preparation does not supply a complete map.

## Architecture

Use the source citation in the prompts that prepare or synthesize body sections and propose steps for file-backed creation. Preserve a cited path verbatim, including its version identifier. If the source supplies no usable path for an artifact, leave the artifact path unspecified. A later change to the accepted head does not change a citation to the source version.

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

Roadmap seed generation and admission, version selection, promotion, top-level copies, rewriting existing plans, and changes to audit rules or publication behavior. Intent drafting, operator-triggered step splits, and finding application remain separate from this authoring scope. Any deterministic output gate needs separate evidence that the prompt rule is insufficient.

## Risks

One prompt can be correct while a sibling writer still shortens the same citation. Model compliance can vary even when the instructions and source evidence reach every applicable writer.

## Testing

Check that the relevant model calls receive the rule and the source path. Run one fresh representative file-backed creation and inspect the resulting plan for the complete citation in generated prose. Keep the retained source body and References coverage for the direct route.

## Acceptance criteria

- The representative generated plan cites the source's immutable version-store path wherever its generated prose names that roadmap artifact as a file.
- Existing direct-source copy and publication behavior is preserved.
- Reconcile the entry titled “Bare roadmap file names in prose `create`'s model writes during synthesis resolve to inert top-level copies beside an accepted head” in `BUG_BACKLOG.md`. Mark it plan-authored while execution is pending and remove it when the change ships.

## Deferred

A deterministic post-synthesis check remains a separate option if a fresh result shows that a prompt change cannot carry the citation reliably.
