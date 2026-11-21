# Step 2 — Verify roadmap citations in a fresh file-backed creation

<!-- plan-tool:detail-format-version: 1 -->

## Summary

One fresh `create --from-existing` run on the normalized route demonstrates whether a covered body writer and a covered step writer carry the selected seed’s exact roadmap version-store paths into the published plan. Check both writer outputs before convergence edits and then check the corresponding citations in the final plan. Update `BUG_BACKLOG.md` according to that evidence, with removal reserved for a passing proof when the fix ships.

## Table of Contents

- [Summary](#summary) — The proof and its effect on the backlog.
- [Table of Contents](#table-of-contents) — The sections in this detail.
- [Why](#why) — Why the published plan alone cannot prove citation preservation.
- [Input](#input) — The upstream change, proof seed, and expected citations.
- [Files (creates vs edits)](#files-creates-vs-edits) — The tracked backlog edit.
- [Implementation](#implementation) — How to collect the proof and act on each outcome.
- [Tests](#tests) — Manual verification and existing regression coverage.
- [Acceptance criteria](#acceptance-criteria) — What a reviewer can verify from the run.
- [References](#references) — The citation, intake, and recovery contracts.
- [Applicable guardrails](#applicable-guardrails) — The limits on the proof and backlog edit.
- [Deferred](#deferred) — Follow-up that requires separate scope.

## Why

A version-store path in the published plan can come from copied References or a later convergence edit. A generated citation can still be missing or shortened to a filename that points readers at an inert copy. Checking each writer’s output against the seed, then checking the published plan, shows whether the generated text carries the right path through to the reader.

## Input

- **Step 1 outcome.** Run against the implementation that supplies the selected source’s roadmap citation evidence to the covered body and step writers.
- **Representative seed.** Choose one valid roadmap-derived seed that needs preparation and whose claims give both writers a reason to cite a roadmap member. `plan_tool/create.py:classify_file_backed_source` distinguishes direct-ready input from input that needs preparation. The completed run must report `normalized`.
- **Expected paths.** Read the exact repository-relative paths and their supported claims from the originally selected source, following `plan_tool/create.py:select_file_backed_source` and the plan’s `## Architecture`. Keep those paths as the comparison baseline, including the version identifiers.
- **Evidence limit.** Step 1’s canned-response tests establish prompt and source-evidence delivery. This step checks model output from one live run.

## Files (creates vs edits)

**New files**

- None in the tracked change. Use a disposable checkout for the proof run and its evidence.

**Existing files (edits only)**

- `BUG_BACKLOG.md` — Reconcile the entry headed “Bare roadmap file names in prose `create`'s model writes during synthesis resolve to inert top-level copies beside an accepted head.” Preserve the current plan-authored status while execution or shipment remains pending.

## Implementation

- **Run one fresh creation.** Use `plan-tool create <proof-slug> --from-existing <seed-path> --iterate --no-resume` with the real backend, a clean committed baseline containing step 1, and an unused slug. Use a disposable checkout containing the seed and its cited roadmap members so normal publication and source archival can proceed there. Invoke plan-tool through an environment tied to the checkout that contains the committed step 1 implementation. Record its import path and revision with the proof.
- **Capture the writer outputs before convergence.** On the ordinary combined route, inspect the accepted outputs from `plan_tool/create.py:propose_distilled_seed_from_claude` or, when it supplies the body passage, `plan_tool/create.py:propose_body_sections`, and from `plan_tool/create.py:propose_steps_from_claude` for the step text. Use the existing backend stream logs and create run events to identify the accepted attempt. Check the parser and selection outcome if a repair occurred, since a successful repair call can still leave the first reply selected. Record the writer and the accepted passage for each surface. Missing or ambiguous attribution leaves the proof inconclusive.
- **Trace each citation into the final plan.** Compare the full path in a generated body passage outside `## References` and in generated step text with the path tied to each claim in the source. In the published plan, inspect the corresponding body passage and the step field in `steps` frontmatter. A path found only in References does not count.
- **Apply the plan’s proof outcomes.** Any observed shortened or substituted citation on either covered surface, in accepted writer output or in the published plan, fails the proof even when other citations match. With no demonstrated mismatch, an omitted citation on either surface or missing writer evidence leaves the proof inconclusive. For either outcome, keep the bug open and record what the run establishes. Attribute a mismatch to a specific writer only when its output establishes responsibility. Remove the entry only when both surfaces pass and the fix ships.

## Tests

### Verification (non-code step)

`plan_tool/launcher.py:_step_requires_test_authoring` exempts this `non-code` step from the plan’s test-authoring gate. Use the live proof and existing regression coverage.

1. Fresh normalized route — Confirm the implementation revision and imported package path, then verify the route and published plan path from the same live run with no replay of proof responses.
2. Body and step citations — Check all citations in the accepted writer outputs and corresponding published surfaces with the exact source path and claim.
3. Direct-source regression — Run `tests/test_create.py::TestFileBackedSourceIntake::test_direct_single_preserves_source_references_without_generic_authoring` and `tests/cli/test_authoring_cmds.py::TestCmdCreateRouteArtifacts::test_cmd_create_direct_archives_raw_source_only_after_clean_completion`.
4. Backlog disposition — Check that the entry’s retention or removal agrees with the proof and shipment status.

## Acceptance criteria

- One fresh normalized run against the verified step 1 build supplies an exact source version-store citation in covered body output outside References and another in covered step output. Both appear in their corresponding locations in the published plan, and neither verified surface contains a shortened or substituted citation.
- Existing direct-source body, References, and publication regression checks pass.
- `BUG_BACKLOG.md` keeps the entry open for an inconclusive proof or a mismatch, keeps it plan-authored while execution is pending, and removes it only when the proof passes and the fix ships.

## References

- [Roadmap path convention](ROADMAP_FORMAT.md#path-convention) — Locate the immutable artifact identified by a citation.
- [File-backed create workflow](docs/how-to/pipeline/create-from-existing.md#preparation-and-normalized-publication) — Check preparation and normalized publication.
- [Raw backend stream log](docs/how-to/pipeline/run.md#raw-backend-stream-log) — Locate retained writer responses.
- [Originating bug](BUG_BACKLOG.md#bare-roadmap-file-names-in-prose-creates-model-writes-during-synthesis-resolve-to-inert-top-level-copies-beside-an-accepted-head) — Locate the entry for disposition.

## Applicable guardrails

- The plan’s `## Scope guardrails` and `## Out of scope` limit the proof to the existing create route and lifecycle. Use the recorded source paths throughout.
- The plan’s `## Audit guardrails` limit verification to the two named generated surfaces and their published counterparts.
- The plan’s `## Expected placement` assigns prompt and workflow changes to step 1. Step 2 owns the live proof and backlog reconciliation.

## Deferred

- Deterministic output validation — Follow the plan’s `## Deferred` if the live evidence warrants separate work.
