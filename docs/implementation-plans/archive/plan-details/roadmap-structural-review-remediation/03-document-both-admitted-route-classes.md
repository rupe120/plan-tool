# Step 3 — Document both admitted route classes, scope refusal to structural preflight, and keep the writer single-artifact

## Summary

Align the roadmap documentation with the existing structural-preflight contract: immutable analysis classifies `requires-scope-review` as a successful no-workflow route, while a later structural-writer invocation revalidates the exact pair after evaluator admission and refuses any preflight failure — a `requires-scope-review` route included — before mutation. Both `same-artifact` and `cross-artifact` analyses can admit one bounded candidate. Update the roadmap references, CLI help source, generated CLI reference, capability catalog, and integration guidance. Keep the exact-pair writer limited to the selected artifact and selected feedback row for either admitted evidence class. On green, the public guidance and generated reference describe the same route boundary that `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` enforces.

## Table of Contents

- [Summary](#summary) — States the documentation outcome and single-artifact limit.
- [Table of Contents](#table-of-contents) — Links to each review section.
- [Why](#why) — Explains the current route-contract mismatch.
- [Input](#input) — Names the route and preflight contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the documentation, CLI help, and test updates.
- [Implementation](#implementation) — Defines the route wording and writer boundary to preserve.
- [Tests](#tests) — Covers the route wording and generated-reference checks.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion conditions.
- [References](#references) — Points to the evaluator-platform reference.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s authority and scope limits.
- [Deferred](#deferred) — Records work that remains outside this documentation step.

## Why

The route guides currently describe the exact-pair writer as same-artifact-only even though `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` admits both `same-artifact` and `cross-artifact` analyses, refusing any preflight failure — a `requires-scope-review` route included — as `evidence-rejected`, with only an ineligible selected feedback row distinguished as `feedback-rejected`. That mismatch can send operators away from a valid bounded rewrite or imply that cross-artifact evidence grants transaction authority. Correct the public contract now so the documented route choice matches the live preflight without widening the writer.

## Input

- **Route classification:** `plan_tool/roadmap_impact_analysis.py:ImpactRouteClass` and `_classify_route` define `same-artifact`, `cross-artifact`, and `requires-scope-review`, with workflow labels separate from writer authority.

- **Runner ordering:** `plan_tool/roadmap_structural_revision_run.py:run_structural_revision` admits the evaluator before it calls `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight`; an unavailable evaluator therefore rejects fact-free before evidence is read.

- **Structural admission:** `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` rebuilds and validates the exact evidence pair and refuses on any failure — a `requires-scope-review` route included — before seed invalidation, backend use, candidate construction, or publication, with only an ineligible selected feedback row distinguished from the rest.

- **Single-artifact candidate:** `plan_tool/roadmap_structural_revision.py:StructuralRevisionPreflight` retains one selected stage, artifact, feedback row, and target row. The documentation must describe that bounded result for either admitted route class.

- **Upstream safety work:** Build on steps 1 and 2’s completed patch and evaluator safeguards without changing their behavior or re-explaining their implementation.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Update `### Choose the revision route` and `### Evidence, publication, and availability boundary` to distinguish evidence admission from write authority.
  - `README.md` — Correct the roadmap command cheat sheet and roadmap route guidance.
  - `RUNBOOK.md` — Update the roadmap command table and `### Record structural feedback without revising the roadmap`.
  - `CLAUDE.md` — Correct the concise roadmap structural-feedback summary and reference-doc wording.
  - `CAPABILITIES.md` — Update the `## Architecture roadmap` structural-rewrite capability description.
  - `docs/ARCHITECTURE.md` — Align `### Immutable roadmap evidence` descriptions of impact analyses and the exact-pair writer.
  - `docs/CODEX_CLI_CONTRACT.md` — Describe the evaluator profile without limiting admitted evidence to one route class.
  - `docs/ROADMAP_WALKTHROUGH.md` — Correct `### Record structural feedback, then analyze its current route`.
  - `docs/cli/roadmap.md` — Regenerate the `# plan-tool roadmap` reference from parser help; do not hand-edit generated output.
  - `integrations/claude/SKILL.md` — Update the roadmap rewrite request map and subcommand summary.
  - `plan_tool/cli/roadmap_cmd.py` — Update the module route description and `register` help for `--rewrite-structural` and `--rewrite-analysis`; keep parser behavior unchanged.
  - `tests/cli/test_cli_reference.py` — Add a semantic assertion for the generated structural-rewrite description.
  - `tests/test_roadmap_format.py` — Extend the structural-route reference guard for both admitted classes and the single-artifact boundary.

## Implementation

- **Foundational rule:** Treat `same-artifact` and `cross-artifact` as the two evidence classes that can reach the exact-pair structural writer. Structural preflight refuses any invalid or non-admitted current pair — a `requires-scope-review` route included — rather than treating that route class as its sole refusal case.

- **Separate admission from authority:** In `ROADMAP_FORMAT.md:### Choose the revision route` and `ROADMAP_FORMAT.md:### Evidence, publication, and availability boundary`, state that a valid route class decides whether the writer may build its bounded candidate; it never changes the writer’s canonical write set.

- **Keep the writer one-artifact:** Describe the selected artifact from `plan_tool/roadmap_structural_revision.py:StructuralRevisionPreflight` as the only canonical artifact the exact-pair route may publish. A cross-artifact analysis may be evidence for that candidate, but it must not produce a transaction, a second artifact update, or broader relation changes.

- **Place refusal at the correct boundary:** Describe `requires-scope-review` as a successful analysis result with no workflow. Its later writer refusal is one `load_structural_revision_preflight` failure after evaluator admission and exact-pair validation, but before seed invalidation, backend contact, candidate construction, or publication; do not describe analysis creation or inspection as a refusal.

- **Preserve the transaction handoff:** Keep `roadmap-cross-artifact-revision-transaction` documented as a future transaction workflow. It is not a command and does not become an alternative writer merely because cross-artifact evidence can admit the bounded writer.

- **Update every operator-facing route guide:** Apply the same distinction to the roadmap material in `README.md`, `RUNBOOK.md`, `CLAUDE.md`, `CAPABILITIES.md`, `docs/ARCHITECTURE.md`, `docs/CODEX_CLI_CONTRACT.md`, `docs/ROADMAP_WALKTHROUGH.md`, and `integrations/claude/SKILL.md`. Keep `ROADMAP_FORMAT.md` as the detailed contract and use concise pointers elsewhere.

- **Keep CLI behavior unchanged:** Update `plan_tool/cli/roadmap_cmd.py`’s module documentation and `register` option help so generated help names both admitted classes and the `requires-scope-review` preflight boundary. Do not add flags, alter `_structural_rewrite_has_conflict`, or change `_cmd_roadmap_structural_rewrite` dispatch.

- **Prove the complete guide sweep:** Keep one explicit inventory of every guide named in this step. Its focused test must prove each guide states both admitted evidence classes, distinguishes an unavailable evaluator from the later scope-review refusal, and keeps the writer one-artifact. Read the `plan_tool/cli/roadmap_cmd.py` module route description directly; cover its parser help through the semantic generated-reference assertion plus `tests/cli/test_cli_reference.py:TestCliReferenceDrift`. Do not treat reference freshness as coverage of the module description.

- **Regenerate the CLI reference:** Generate `docs/cli/roadmap.md` from `plan_tool/cli/roadmap_cmd.py:register` after changing the help text, preserving `tests/cli/test_cli_reference.py:TestCliReferenceDrift` as the source-to-reference drift check.

## Tests

### Tests for this step

- `tests/test_roadmap_format.py:test_structural_rewrite_route_reference_separates_local_evidence_generic_transaction_and_broad_paths` — Assert that the format contract names both admitted evidence classes, identifies `requires-scope-review` as an included structural-preflight failure rather than its only refusal, and retains one-artifact publication.
- `tests/test_roadmap_format.py:test_structural_rewrite_route_guidance_sweep_covers_every_named_public_guide` — Assert the explicit guide inventory covers each named nongenerated public guide and the `plan_tool/cli/roadmap_cmd.py` module route description directly; each entry states both admitted classes, the evaluator-first evidence-validation order, and the one-artifact boundary.
- `tests/cli/test_cli_reference.py:test_roadmap_reference_documents_both_admitted_structural_route_classes` — Assert that the rendered roadmap reference names both admitted classes, the any-failure structural-preflight boundary, and no transaction authority.
- `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk` — Assert that the committed `docs/cli/roadmap.md` matches the changed parser help.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Every updated roadmap guide states that `same-artifact` and `cross-artifact` evidence can admit the exact-pair structural writer.
- Every updated roadmap guide distinguishes an unavailable evaluator's fact-free early rejection from the later structural preflight, which refuses any failure — a `requires-scope-review` route included — only after evaluator admission and exact-pair validation rather than during analysis creation or inspection.
- Every updated roadmap guide preserves the rule that the exact-pair writer publishes only the selected artifact.
- The documentation keeps the cross-artifact transaction as a future workflow, not a second writer or fallback.
- `plan_tool/cli/roadmap_cmd.py:register` exposes the corrected route contract through `--rewrite-structural` and `--rewrite-analysis` help without changing parser or dispatch behavior.
- `docs/cli/roadmap.md` is regenerated and `tests/cli/test_cli_reference.py` passes.
- `tests/test_roadmap_format.py` passes with an explicit guide inventory covering every named nongenerated public guide and the direct CLI module description, both admitted classes, the refusal order, and the no-transaction boundary.

## References

- [sandbox-exec(1) macOS Manual Page](https://keith.github.io/xcode-man-pages/sandbox-exec.1.html) — Keep the evaluator-profile wording accurate while updating its route-class description.

## Applicable guardrails

- **The plan’s “## Plan intent”, structural rewrite contract:** Keep the documented behavior aligned with the settled merge-safety, isolation, and route-selection rules.
- **The plan’s “## Step intent”, public route guidance:** Limit this work to documenting the admitted evidence classes, structural-preflight refusal, and one-artifact writer boundary.
- **The plan’s “## Out of scope”, authority boundary:** Do not add generic operations, broad re-entry behavior, new evidence handling, or multi-artifact transaction authority.

## Deferred

- Multi-artifact structural transaction — Requires separate authorization and remains a future workflow.
- Route-class schema or structural-runner behavior changes — The existing implementation already supplies the contract this step documents.
