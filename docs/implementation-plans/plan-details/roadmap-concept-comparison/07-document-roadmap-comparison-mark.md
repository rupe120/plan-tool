# Step 7 — Document roadmap comparison and mark BACKLOG #402 shipped

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Document the shipped read-only roadmap comparison across the roadmap reference, capability catalog, command guides, walkthrough, architecture map, and contributor guidance. Remove the completed `BACKLOG.md` #402 entry and add focused documentation drift coverage in `tests/test_roadmap_format.py`. Keep the comparison separate from lifecycle actions and existing views, with Git’s complete patch remaining the evidence source. On green, operators can discover the command, select snapshots safely, understand its output and refusals, and find no stale backlog claim that the feature remains pending.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation and backlog closeout.
- [Table of Contents](#table-of-contents) — Links to every detail section.
- [Why](#why) — Why the shipped comparison needs one consistent operator story.
- [Input](#input) — Shipped comparison contract and documentation owners this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation, catalog, backlog, and drift-test edits.
- [Implementation](#implementation) — Required documentation boundaries and closeout approach.
- [Tests](#tests) — Documentation drift coverage and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Roadmap contracts and feature source material.
- [Applicable guardrails](#applicable-guardrails) — Read-only and evidence-preservation limits.
- [Deferred](#deferred) — Follow-up presentation work outside this step.

## Why

The roadmap command gains a two-snapshot comparison route in steps 1–6, but the current docs only describe one-snapshot views and lifecycle actions. Without a coordinated documentation sweep, an operator cannot distinguish a read-only comparison from an acceptance action, and `BACKLOG.md` #402 falsely presents delivered work as pending.

## Input

- **Shipped comparison route:** Read the CLI syntax and output choices from step 6’s landed `plan_tool/cli/roadmap_cmd.py:register` and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`; landed names win over this plan’s wording.
- **Comparison facts:** Treat steps 1–5’s typed comparison, snapshot resolution, Git patch evidence, and rendering contracts as the implementation source. Document their observable behavior without restating internal algorithms.
- **Existing documentation ownership:** Preserve `ROADMAP_FORMAT.md` as the operator-facing roadmap contract, `docs/ARCHITECTURE.md` as the layer-boundary map, `CAPABILITIES.md` as the capability catalog, and `docs/reference/commands.md` as the concise command list.
- **Backlog source record:** Use `BACKLOG.md` #402 as the exact entry to retire. Confirm no remaining `#402` references describe the delivered comparison as future work.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Add the comparison’s operator-visible selector, evidence, output, refusal, and read-only contract near the existing roadmap presentation and version material.
  - `CAPABILITIES.md` — Extend the `architecture-roadmap` capability’s surfaces and description to include the comparison route and its read-only boundary.
  - `README.md` — Add the comparison invocation to the roadmap CLI cheat sheet and concise roadmap guidance.
  - `CLAUDE.md` — Update the `## Reference docs` roadmap bullet tersely so future development sessions discover the comparison contract without duplicating it.
  - `docs/ARCHITECTURE.md` — Describe the comparison modules as a read-only branch and retain the established roadmap import-direction boundaries.
  - `docs/reference/commands.md` — Add the concise comparison invocation and state its read-only purpose.
  - `docs/how-to/roadmap.md` — Add an operator workflow for comparing snapshots before a separate acceptance action.
  - `BACKLOG.md` — Remove the complete #402 entry and any stale local wording that says its plan or execution remains pending.
  - `tests/test_roadmap_format.py` — Add focused drift coverage for the cross-document comparison contract and backlog retirement.

## Implementation

- **Foundational logic:** Keep one operator-visible comparison contract consistent across the roadmap documentation set while retiring its completed backlog item.

- **Document the command from landed behavior.** Use the parser registration and dispatch in `plan_tool/cli/roadmap_cmd.py:register` and `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` to record the actual selector syntax, default base behavior, available output forms, successful identical-versus-different outcomes, and explicit refusal cases. Do not document a proposed flag name or selector form from earlier detail files if the landed CLI differs.

- **Keep comparison distinct from views and writers.** Explain that comparison binds two snapshots for review, while `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view` remains a one-snapshot inspection route. State that reviewing comparison output does not accept, enroll, promote, settle, repair, or otherwise change roadmap state.

- **Preserve evidence precedence.** In `ROADMAP_FORMAT.md`, `README.md`, `docs/reference/commands.md`, and `docs/how-to/roadmap.md`, make clear that the concept cards and JSON explain the exact Git patch; they do not replace it. Document that stable-id changes remain separate removal and addition facts, raw-only artifacts are identified, and mixed patch bytes are not silently assigned to a nearby concept.

- **Use each document for its existing job.**
  - `ROADMAP_FORMAT.md` owns the detailed comparison contract and terminology.
  - `docs/ARCHITECTURE.md` names the comparison’s read-only layer and its relationship to `plan_tool/roadmap_versions.py:VERSION_ARTIFACT_INVENTORY`, `plan_tool/roadmap_view.py:display_label`, and the comparison modules shipped by steps 1–5.
  - `CAPABILITIES.md` lists the new surface beside the existing `architecture-roadmap` capability rather than creating a competing capability.
  - `README.md` and `docs/reference/commands.md` remain concise command-entry points.
  - `docs/how-to/roadmap.md` shows when an operator compares before taking a separate action.
  - `CLAUDE.md` stays a short pointer to the authoritative docs.

- **Retire #402 completely.** Remove the #402 feature entry from `BACKLOG.md`, including its pending status and plan-authoring wording. Search `BACKLOG.md` for `#402` and roadmap-comparison phrasing after the edit; retain only unrelated references when they do not claim this feature is pending.

- **Add a narrow drift guard.** Extend `tests/test_roadmap_format.py` beside its existing cross-guide documentation checks. Test the required comparison facts by stable command and contract fragments, not broad prose substrings: the route is read-only, uses two snapshots, preserves complete Git evidence, and remains separate from acceptance actions. Include a test that #402 no longer appears as an active backlog entry.

- **Do not widen the documentation sweep.** `docs/cli/roadmap.md` is generated from the parser and belongs to step 6’s CLI work. Do not add a separate HTML renderer, comparison lifecycle, or new artifact schema while documenting the delivered route.

## Tests

- `test_roadmap_comparison_guidance_sweep_matches_landed_contract` — verifies every selected public guide names the shipped comparison route and its read-only, evidence-preserving boundary.
- `test_roadmap_comparison_guidance_keeps_comparison_and_acceptance_separate` — verifies the workflow does not present comparison as enrollment, promotion, settlement, or another lifecycle action.
- `test_roadmap_comparison_backlog_retirement_removes_402` — verifies `BACKLOG.md` no longer contains an active #402 entry or pending execution claim.
- `test_roadmap_format.py` existing suite — remains green so the documentation changes preserve existing roadmap examples and route guidance.

### Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap_format.py -q`.
2. Run `uv run pytest tests/test_capability_catalog.py -q` to confirm the updated `CAPABILITIES.md` remains valid and maps only to real surfaces.
3. Compare every documented command form with `plan_tool/cli/roadmap_cmd.py:register`.
4. Search the declared documentation files for stale comparison wording and inspect each remaining match for current meaning.
5. Confirm `git diff` changes only the declared documentation and drift-test files.

## Acceptance criteria

- `ROADMAP_FORMAT.md` documents the shipped comparison route’s two-snapshot selection, output forms, refusal boundary, stable-id treatment, and Git-evidence precedence.
- `CAPABILITIES.md` lists the comparison surface under `architecture-roadmap` and remains accepted by `plan_tool/capability_catalog.py:check_capabilities`.
- `README.md` and `docs/reference/commands.md` include the exact landed invocation without presenting comparison as a writer.
- `docs/how-to/roadmap.md` gives an operator a comparison-before-acceptance workflow and keeps acceptance as a separate explicit action.
- `docs/ARCHITECTURE.md` identifies the comparison as read-only and preserves existing roadmap layer boundaries.
- `CLAUDE.md` points future contributors to the expanded roadmap reference without duplicating the detailed contract.
- `BACKLOG.md` contains no active #402 entry or claim that roadmap concept comparison remains pending.
- The focused `tests/test_roadmap_format.py` comparison and backlog-retirement checks pass.

## References

- [BACKLOG.md #402 — Source feature contract for the delivered comparison and its retirement](../../BACKLOG.md)
- [ROADMAP_FORMAT.md — Roadmap artifacts, version identities, and presentation contract](../../ROADMAP_FORMAT.md)
- [plan_tool/roadmap_versions.py — Fixed artifact inventory and immutable version loading](../../plan_tool/roadmap_versions.py)
- [plan_tool/roadmap_view.py — Existing roadmap labels and reader presentation ownership](../../plan_tool/roadmap_view.py)
- [plan_tool/cli/roadmap_cmd.py — Landed roadmap parser and exclusive command dispatch](../../plan_tool/cli/roadmap_cmd.py)

## Applicable guardrails

- **Plan intent, read-only comparison:** Document comparison as review-only and do not add a lifecycle mutation or acceptance policy.
- **Plan intent, complete evidence:** Preserve the rule that structured output explains complete Git evidence without filtering or replacing it.
- **Plan intent, stable identity:** Describe changed stable ids as separate removal and addition facts; do not imply label- or prose-based matching.
- **Plan intent, deterministic and model-free behavior:** Do not describe generated summaries, recommendations, or model judgment as comparison output.
- **Plan scope guardrails, existing-route compatibility:** Keep existing roadmap views and lifecycle writers unchanged while adding comparison documentation.
- **Plan out of scope, renderer expansion:** Do not document HTML comparison output as shipped work.

## Deferred

- HTML or interactive comparison presentation — remains outside this plan’s terminal and machine-readable comparison contract.
