# Step 5 — Verify selected content in an independent single-commit snapshot

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Verify the selected content and existing tests in a temporary independent Git repository containing one root commit. Record the selected baseline, isolation checks, content checks and test outcomes in `docs/evidence/public-release-content-snapshot.md`. Build the temporary repository from selected tracked content without copying internal Git storage or ignored configuration. Completion provides bounded evidence that the selected content works without internal ancestry, with failures and coverage limits stated explicitly.

## Table of Contents

- [Summary](#summary) — Deliverable and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Why verification needs an independent repository.
- [Input](#input) — Selection, dependency outcomes and existing contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Durable record changes.
- [Implementation](#implementation) — Snapshot isolation and verification approach.
- [Tests](#tests) — Existing coverage and numbered verification checks.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Scope and verification sources.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on verification and conclusions.
- [Deferred](#deferred) — Work outside this verification step.

## Why

A publication candidate must install and work from its selected content in an
independent environment. Verify exact bytes, references, dependencies and tests
without relying on a developer's local settings. This makes the release boundary
observable and keeps test results tied to a specific candidate.

## Input

- **Selected content:** Read `docs/evidence/public-release-content-snapshot.md`, created by step 1 and updated by the preparation steps. Use its exact path dispositions and identified baseline; do not invent a new selection.
- **Step 2 reference closure:** Require the evidence record to account for the 13 known retained document owners and their concrete report dependencies. A prior green run limited to the original five-file footprint does not supply this result; use the corrected step's actual repair evidence.
- **Step 3 outcome:** Consume the self-contained retained guidance and citation dispositions. Check that retained explanations and replacement instructions work without the cited internal objects.
- **Step 4 outcome:** Consume the rights-approved selection or explicit exclusions. Keep unresolved rights visible; successful technical checks do not settle them.
- **Report identity:** Reuse `plan_tool/fingerprint.py:audit_input_revision` and `plan_tool/review_persistence.py:normalize_audit_revision` unchanged when checking retained report claims. A valid revision structure does not prove that unavailable original inputs can be replayed.
- **Test environment:** Read `pyproject.toml` for dependencies and pytest configuration, and `TESTING.md` § “Running tests” for supported commands. Keep the existing isolation fixtures in `tests/conftest.py`, including `_drop_repo_local_git_env`, active.
- **Evidence limits:** The independent repository proves behavior for the recorded selected bytes and environment. It does not prove semantic privacy, redistribution rights or the full fresh-consumer workflow.

## Files (creates vs edits)

**New files:**

- None in the maintained checkout. The temporary repository and its generated environment are disposable verification artifacts.

**Existing files (edits only):**

- `docs/evidence/public-release-content-snapshot.md` — Add the tested baseline, selected-content identity, isolation evidence, commands, results, residual findings and coverage limits.

## Implementation

- **Foundational logic: selected content must work without internal ancestry or ignored configuration.** Verify that property through a temporary independent repository. Reject a worktree, ordinary clone or shallow clone as the verification boundary because each can retain internal objects or repository relationships.

- **Bind the run to an exact selection.** Start from a committed preparation baseline after steps 3 and 4. Record the source commit, applied exclusions and a reproducible description of the exported path set. Include retained generated artifacts in the selection review rather than assuming generated content is safe.

- **Export content, then initialize fresh Git storage.** One approach is to export selected tracked entries from the identified baseline into an empty temporary directory and initialize Git there. Preserve selected file contents, executable modes and symlink targets; do not copy the source Git directory, ignored files or local configuration.

- **Prove independence before testing.** The temporary repository must contain one parentless snapshot commit, no source-history refs, no remotes and no alternate object store. Check for shared storage or environment settings that redirect Git to the source checkout. Root-count evidence alone is insufficient if internal objects remain available.

- **Use a fresh verification environment.** Install dependencies from the selected `pyproject.toml` and tracked lockfile when present. Do not reuse the source virtual environment, editable installation or ignored tool configuration. Record Python, Git and dependency-tool versions and any environment settings required by the checks.

- **Repeat the selected-content checks inside the snapshot.** Check filenames and structured content as well as prose. Review identifier and vocabulary matches against the approved dispositions; report legitimate survivors rather than requiring blanket zero matches. Check retained local links, plan-manifest entries and discovery using only selected files. Include the 13 known document owners and concrete capture-opening instructions, preserving the distinction between usable live references, dated measurement context and illustrative runtime paths. An unresolved dependency prevents a successful snapshot-verification claim.

- **Check instructions by their intended result.** Exercise bounded retained instructions that depend on repository content or Git state. Confirm that step 3’s replacement routes work without internal ancestry. Identify credential-dependent, unavailable or out-of-scope instructions explicitly instead of presenting them as verified.

- **Preserve identity meanings.** For retained examples and reports, verify the digest claims that selected bytes support. Keep the historical and sanitized identities in `docs/evidence/integration-context-budget-2026-10-09/provenance.json` distinct. Do not rewrite qualification metadata or runtime readers to make a failed check pass.

- **Run existing tests without changing their contracts.** Run the affected suites in the independent repository. Run the full suite when preparation changes fixtures or code, as required by the plan’s testing contract. Record commands, exit codes, pass/fail/skip totals and skip reasons; distinguish existing skips from tests not run.

- **Treat history-dependent failures as findings.** Determine whether a failure exposes selected content that needs repair, an existing test assumption or an environment limitation. Do not add skips, relax assertions, import old objects or copy ignored settings to obtain a green result. Route repairs to their owning steps and repeat verification against the corrected committed selection.

- **Keep the record tied to the tested bytes.** Record the temporary root commit and selected-content identity before adding results to the maintained evidence document. State that the results entry itself is added afterward; do not claim that the tested root includes evidence written after the run.

- **Reuse shared owners unchanged.** `plan_tool/fingerprint.py:audit_input_revision`, `plan_tool/review_persistence.py:normalize_audit_revision` and `tests/conftest.py` retain their existing responsibilities. This step records their results and does not create a second identity validator, test harness or snapshot framework.

## Tests

No test files are created or edited. This is a non-code step; `plan_tool/launcher.py:_step_requires_test_authoring` limits the test-authoring gate to code change types, so that gate does not apply here.

- `tests/test_fingerprint.py` — Existing regression coverage for content fingerprints and detail-bundle identity remains green in the selected snapshot.
- `tests/test_review_persistence.py` — Existing regression coverage for persisted review identity remains green without changing report contracts.
- Affected existing suites — Select additional retained test files from the actual preparation diff and record their full repository-relative paths.
- Full existing suite — Run `uv run pytest tests/ -q -n auto` when preparation changes fixtures or code; retain existing test isolation and assertions.

### Verification (non-code step)

1. **Selected bytes match the recorded selection** — Compare exported paths, contents, modes and symlink targets against the committed baseline and explicit exclusions.
2. **Snapshot has no internal ancestry or shared storage** — Verify one parentless commit, expected refs, no remotes, no object alternates and no Git redirection to the source checkout.
3. **Ignored configuration is unnecessary** — Establish dependencies and run checks without the source environment, ignored settings or local credentials.
4. **Content matches have reviewed dispositions** — Repeat filename, identifier, vocabulary and structured-content checks; record unresolved candidates and approved survivors.
5. **Retained references work locally** — Check selected links, manifest paths, discovery and bounded instructions using only snapshot content, including all 13 report-reference owners. Demonstrate that no required explanation or action depends on an omitted capture; classify legitimate provenance/examples without pretending that a raw text match is a broken link.
6. **Digest claims describe the right bytes** — Check retained report normalization and example digests without conflating historical inputs with sanitized replacements.
7. **Test outcomes remain honest** — Record existing-suite results, history-dependent failures, skips and unavailable coverage without modifying tests to hide them.
8. **Durable evidence identifies the tested state** — Record source and root commits, selection identity, environment, commands and results in `docs/evidence/public-release-content-snapshot.md`.

## Acceptance criteria

- `docs/evidence/public-release-content-snapshot.md` identifies the committed source baseline, exact selected path set or reproducible selection description, exclusions and temporary root commit.
- The temporary repository contains one parentless snapshot commit and no internal objects, source-history refs, remotes, alternate object storage or ignored source configuration.
- Exported content matches the selected baseline, including file modes and symlink targets.
- The record contains results for selected-content scans, retained local links, discovery, bounded instructions and applicable digest checks.
- Affected existing tests pass in the independent repository; the full suite runs when preparation changes fixtures or code.
- Every failure, skip, blocked check and untested instruction has an explicit reason and disposition. Unresolved failures prevent a claim that verification is green.
- Tests, report schemas, qualification rules and runtime code remain unchanged by this step.
- The evidence distinguishes technical verification from unresolved rights and release prerequisites.
- The maintained checkout changes only `docs/evidence/public-release-content-snapshot.md`, and its results identify the bytes tested before the results entry is added.

## References

- [Public Release Content Snapshot](../../2-public-release-content-snapshot.md) — Read the architecture, testing contract and scope boundary for local snapshot verification.
- [Release preparation handoff](../../../../handoffs/2026-10-19-public-onboarding-and-release.md) — Read “Current decisions” and “Next actions” for the preparation boundary.
- [Public-release coordination arc](../../backlog-arcs/backlog-arc-public-release.md) — Distinguish this content check from distribution and onboarding work.
- [Testing guide](../../../../TESTING.md) — Use the supported test commands and existing isolation rules.
- [Sanitized-example provenance](../../../evidence/integration-context-budget-2026-10-09/provenance.json) — Check the distinction between historical input identity and sanitized example identity.
- [Context-budget evidence](../../../evidence/integration-context-budget-2026-10-09/sizing.md) — Read the limits on replaying historical measurements.
- [Developer documentation style](../../../reference/documentation-style.md) — Keep the evidence record organized around results, exceptions and next actions.

## Applicable guardrails

- **The plan’s “Scope guardrails,” local verification boundary:** Use a disposable repository and record results; do not change the maintained checkout’s ancestry or any remote.
- **The plan’s “Scope guardrails,” unchanged runtime contracts:** Investigate failed identity checks without changing report readers, schemas or qualification behavior.
- **The plan’s “Scope guardrails,” evidence limits:** Describe scan and test coverage precisely; do not turn passing checks into privacy or rights clearance.
- **The plan’s “Scope guardrails,” approved references:** Judge residual matches against recorded dispositions rather than deleting legitimate references to satisfy a search.
- **The plan’s “Out of scope,” separate release and onboarding work:** Keep verification focused on selected content and existing tests. Do not expand it into the separately owned workflows.
- **The plan’s “Scope guardrails,” protected guidance review:** Record guidance defects for their owning step; do not edit protected guidance within this evidence-only step.

## Deferred

- Publication, remote snapshot installation and distribution/sync procedures — Separate owner-authorized work under BACKLOG #514.
- Full fresh-consumer pipeline exercise — BACKLOG #515 owns that verification.
- Content, instruction or test repairs exposed by verification — Return findings to the owning preparation step or tracking process; this step only edits the evidence record.
- Shared identity, lifecycle or test-harness changes — Separate intentional work if verification establishes a need; do not broaden this snapshot check.
- Semantic privacy and redistribution-rights clearance — Technical checks supply bounded evidence; unresolved decisions remain with their existing owners.
