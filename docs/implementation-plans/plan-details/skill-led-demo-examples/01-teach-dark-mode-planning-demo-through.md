# Step 1 — Teach the dark-mode planning demo through assistant requests

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Convert `docs/demos/planning-demo.md` into an assistant-led walkthrough of the retained dark-mode scenario. Add `docs/demos/dark-mode-example.md` with clearly labeled reading samples and refresh `plans/2-demo.md` as a separate minimal fixture. Keep operational rules in their existing reference documents and distinguish authored examples from captured results. On completion, readers can request grounded planning, inspect both audit stages and understand the paired local story and developer handoff.

## Table of Contents

- [Summary](#summary) — What this step delivers.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Where the retained examples mislead readers.
- [Input](#input) — Contracts and preparation evidence to preserve.
- [Files (creates vs edits)](#files-creates-vs-edits) — The bounded documentation footprint.
- [Implementation](#implementation) — Requests, examples and fixture corrections.
- [Tests](#tests) — Reviewer-run checks for this non-code step.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Existing owners of procedural and artifact rules.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that constrain this conversion.
- [Deferred](#deferred) — Related surfaces outside this step.

## Why

`docs/demos/planning-demo.md` teaches preparation mainly through stage commands and branch switching, leaving readers to operate the pipeline themselves. Its retained fixture, `plans/2-demo.md`, also describes an embedded skill and application layout that do not match this repository, including application-specific tests and stale CLI references. The demo needs a clear assistant request route and inspectable examples that explain what readers review without claiming unrecorded model results.

## Input

- **Artifact contracts:** Use `SEED_FORMAT.md`, `PLAN_FORMAT.md`, `DETAIL_FORMAT.md` and `JIRA_FORMAT.md` for any example artifacts. Run-grade detail remains the authoring route; the paired developer handoff is an export companion, not a replacement detail artifact.
- **Preparation evidence:** Read `handoffs/2026-10-21-demo-refresh.md`, especially “Verification and presentation boundary.” Its local fixture checks do not establish qualified live audit convergence, and its temporary preparation files may be absent.
- **Fixture identity:** `plans/2-demo.md` declares one low-complexity step named `first`, with step status `current` and plan status `planning`. Preserve its minimal fixture role rather than turning it into the dark-mode implementation plan.
- **Evidence limits:** Authored reading samples demonstrate artifact shape and review questions. They do not prove model reliability, successful live authoring or audit convergence.

## Files (creates vs edits)

**New files:**

- `docs/demos/dark-mode-example.md` — Authored dark-mode reading samples covering the seed, plan, detail, audit interpretation and paired local export.

**Existing files (edits only):**

- `docs/demos/planning-demo.md` — Make assistant requests the main learning path; connect requests to reviewable artifacts and retain accurate preparation status.
- `plans/2-demo.md` — Correct repository references, fixture scope, testing guidance and acceptance checks while preserving the minimal fixture identity.

## Implementation

- **User review checkpoints.** In the dark-mode walkthrough and reading samples, show separate requests to review the assistant-authored seed before create, the bare plan plus audit before detail, and the details plus grounded audit before execution or export. The assistant links each artifact, summarizes changes and asks for corrections or continuation. Wait for the user unless explicit existing delegation covers that transition; do not infer approval from elapsed time. This changes the demo interaction, not tool enforcement.

- **Foundational logic: assistant request → inspectable artifact → human decision.** Apply this teaching pattern locally in the walkthrough and example page. Keep procedural authority in existing documentation; reject a second command-by-command policy embedded in the demo.

- **Lead the walkthrough with usable requests.** Rework `docs/demos/planning-demo.md` around its “Prepare the example” and “Present the workflow” sections. Include requests that ask the assistant to:
  - Inspect the consuming repository and draft a grounded, scope-fenced seed for the dark-mode toggle.
  - Drive the plan-tool skill through planning and both audit stages, reporting progress and bringing consequential decisions back for review.
  - Produce local stories and their paired developer handoff without implementing the feature.
  Each request must make the expected artifact and reader review point apparent.

- **Preserve the audit sequence and honest reporting.** The walkthrough must distinguish the bare-plan audit from the later detail-grounded audit. Ask the assistant to report saved report locations, detail coverage, qualification, convergence outcome and unresolved decisions under `docs/how-to/pipeline/audit.md`. Link to that procedure for exact rules; a successful process exit must not become a claim of a clean audit.

- **Keep preparation separate from presentation.** Retain useful presenter guidance and the checkpoint names `demo/1-seed` through `demo/4-jira`, but describe their preparation status accurately. Preserve the clean-tree switching advice and disposable location for live calls. Documentation completion alone must not remove the warning that the remote checkpoints need review.

- **Make the example page useful without inventing evidence.** One approach is a short sequence of annotated excerpts in `docs/demos/dark-mode-example.md`: request, seed, plan, representative detail, bare/detail audit review, and story plus developer handoff. Label authored samples at the page opening and beside result-shaped examples. Use hypothetical application paths only with an explicit illustrative label; requests for a real repository must ask the assistant to verify its actual paths first.

- **Show both export audiences.** Explain the story’s tracker-facing scope and the developer handoff’s implementation context using `JIRA_FORMAT.md:Paired developer handoff` and “Not a detail, audit, or reconciliation input.” The sample must not suggest remote Jira creation or treat the companion as canonical execution detail. Link the walkthrough to the example page and provide a return link.

- **Correct the fixture throughout its body.** In `plans/2-demo.md`, update “Overview,” “Architecture,” “References,” “Out of scope,” “Risks,” “Testing” and “Acceptance criteria” together. Remove embedded installation paths, unrelated application/infrastructure claims, obsolete CLI module references and unsupported test commands. Use real repository references and checkable fixture properties; remove claims that populated sections still contain placeholders. Do not author a fixture detail or execute the placeholder step.

- **Preserve format compatibility.** Check fixture frontmatter against `PLAN_FORMAT.md` and `plan_tool/parser.py:parse_plan_text`. Add currently required declarations if needed without expanding its workload. `plan_tool/parser.py:render_plan_text` provides the existing renderer for round-trip verification; this step changes neither parser nor schema.

- **Sweep identifiers and vocabulary within the declared files.** Search for embedded-skill paths, application names, stale test commands and descriptions of deprecated apply-driven teaching. Correct each occurrence or identify why it remains as explicitly labeled illustration. Before renaming headings, check inbound anchors so links remain usable.

## Tests

This is a non-code step. The test-authoring gate applies to `feature` and `refactor`, so it does not require a new test file here. Existing relevant coverage includes `tests/test_parser.py`, `tests/test_jira.py` and `tests/test_jira_handoff.py`; extend no suite solely to assert prose wording.

### Verification (non-code step)

1. `assistant_requests_expose_artifacts_and_decisions` — Read the walkthrough as a newcomer and verify that each request names its expected output and review point.
2. `both_audit_stages_remain_distinct` — Verify seed → plan → bare audit → detail → detail-grounded audit → local export ordering and reporting links.
3. `authored_samples_do_not_claim_captured_results` — Check that result-shaped samples carry an illustrative label and contain no invented report paths, measured counts or convergence claims.
4. `local_export_includes_both_audiences` — Verify that examples explain the story and developer companion without promising remote writes or treating the companion as run-grade detail.
5. `minimal_fixture_preserves_identity_and_parses` — Parse `plans/2-demo.md` with `plan_tool/parser.py:parse_plan`; verify its retained identity and reparse rendered text using `render_plan_text` and `parse_plan_text`.
6. `complete_embedded_artifacts_pass_existing_checks` — If the example includes complete machine-readable artifacts, exercise their real readers and validators; round-trip artifacts with existing renderers. Mark intentionally incomplete excerpts as excerpts.
7. `links_and_references_point_to_current_owners` — Check local links, heading anchors and cited symbols; search the three files for stale identifiers and application vocabulary.
8. `publication_and_preparation_claims_match_evidence` — Compare status language with `handoffs/2026-10-21-demo-refresh.md`; verify that no branch replacement or live-run claim follows merely from these edits.

## Acceptance criteria

- The step’s deliverables show explicit user review of seeds, plans and details at the correct stage boundaries, including artifact links, change summaries and correction/continuation requests; continuation follows a user response or explicit prior delegation.
- `docs/demos/planning-demo.md` offers copyable assistant requests covering grounded seed creation, skill-driven planning, progress reporting, review decisions and paired local export.
- The walkthrough identifies both audit stages and links to their authoritative procedure without replacing qualification with exit-code success.
- `docs/demos/dark-mode-example.md` provides labeled dark-mode reading samples and distinguishes authored material from captured evidence.
- The example explains both the story export and developer handoff, including their different roles.
- `plans/2-demo.md` parses and round-trips through the existing parser and renderer while retaining its minimal fixture identity.
- The fixture contains no unsupported embedded-skill layout, unrelated application testing instructions or stale CLI entry-point references.
- Links and cited anchors in the three changed files point to existing targets or explicitly labeled illustrative destinations.
- Preparation status remains consistent with retained evidence; no verified live workflow or remote checkpoint refresh is implied.
- The implementation diff changes only the three declared files.

## References

- [Seed format](../../../../SEED_FORMAT.md) — Required scope and reference content for seed samples.
- [Plan format](../../../../PLAN_FORMAT.md) — Frontmatter and body requirements for the retained fixture.
- [Detail format](../../../../DETAIL_FORMAT.md) — Current run-grade detail contract.
- [Jira format](../../../../JIRA_FORMAT.md) — Local story export and paired developer handoff ownership.
- [Audit procedure](../../../how-to/pipeline/audit.md) — Audit sequence, coverage and qualified-result interpretation.
- [Demo refresh handoff](../../../../handoffs/2026-10-21-demo-refresh.md) — Preparation evidence and publication boundary.
- [Documentation style](../../../reference/documentation-style.md) — Task-first structure and review checks.

## Applicable guardrails

- **The plan’s “Scope guardrails,” existing behavior:** Keep the conversion within the three documentation/example files; route operational details to their current owners.
- **The plan’s “Scope guardrails,” publication boundary:** Describe retained checkpoint status without changing refs or exposing private preparation material.
- **The plan’s “Out of scope,” scenario boundary:** Retain dark mode and leave other demo scenarios and historical material to their existing owners.
- **Step intent, reader review:** Keep assistant requests focused on grounded planning and inspectable results; do not turn the walkthrough into feature execution.

## Deferred

- `docs/demos/roadmap-demo.md` — Its advanced assistant-led teaching needs its own scoped conversion.
- `docs/how-to/use-cases.md`, `docs/how-to/choose-a-starting-point.md` and `docs/how-to/common-workflows.md` — Related learning surfaces remain outside this step’s declared footprint.
- `docs/demos/README.md` — Demo discovery and aggregate preparation status remain outside this step; preserve accurate status in the walkthrough itself.
- Live demo regeneration and remote checkpoint replacement — Reading samples do not establish live audit evidence, and publication remains separately authorized work.
