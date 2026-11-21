> **Replaced**: this file has been superseded by `docs/implementation-plans/2-create-roadmap-version-citations.md`.
> Preserved here for history; do not edit.

# Preserve versioned roadmap citations in create output

## Outcome

When `create --from-existing` generates prose that cites a roadmap artifact already cited by the source, it carries the source's full repository-relative version-store path into the plan.

## Overview

A roadmap-derived plan needs to send its readers to the exact artifact that informed the seed. The existing roadmap seed writer supplies that path. This effort carries that evidence across model-written plan sections and steps.

## Problem statement

The seed contract already supplies version-store paths. Generated prose can shorten a citation to its filename, which can direct a reader to an inert top-level copy or a missing file. Direct intake preserves the supplied body, but still proposes steps when the source has no strict step list. Normalized intake can generate body prose during preparation, and body synthesis can run when preparation does not supply a complete map.

## Architecture

Use the source citation in the existing authoring prompts where the model can write plan prose. Preserve a cited path verbatim, including its version identifier. If the source supplies no usable path for an artifact, leave the artifact path unspecified. A later change to the accepted head does not change a citation to the source version.

## In scope

Model-written plan body and step text in file-backed `create`, including applicable re-proposals. Reuse the existing source evidence and preserve the deterministic body and References copy on direct intake.

## Out of scope

Roadmap seed generation and admission, version selection, promotion, top-level copies, rewriting existing plans, and changes to audit rules or publication behavior. Any deterministic output gate needs separate evidence that the prompt rule is insufficient.

## Allowed behavior changes

The model receives instructions to preserve known version-store citations when it generates plan prose.

## Allowed reorganization

None.

## Risks

One prompt can be correct while a sibling writer still shortens the same citation. Model compliance can vary even when the instructions and source evidence reach every applicable writer.

## Testing

Check that the relevant model calls receive the rule and the source path. Run one fresh representative file-backed creation and inspect the resulting plan for the complete citation in generated prose. Keep the retained source body and References coverage for the direct route.

## Acceptance criteria

- The representative generated plan cites the source's immutable version-store path wherever its generated prose names that roadmap artifact as a file.
- Existing direct-source copy and publication behavior is preserved.
- Reconcile the entry titled “Bare roadmap file names in prose `create`'s model writes during synthesis resolve to inert top-level copies beside an accepted head” in `BUG_BACKLOG.md`. Mark it plan-authored while execution is pending and remove it when the change ships.

## Stop / defer

If a writer lacks the source citation, establish the missing evidence handoff before proposing new machinery. File output validation or unrelated roadmap citation issues separately.

## Deferred

A deterministic post-synthesis check remains a separate option if a fresh result shows that a prompt change cannot carry the citation reliably.

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
