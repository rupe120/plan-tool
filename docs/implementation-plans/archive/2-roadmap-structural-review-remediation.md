> **Archived:** this completed plan moved here on 2026-08-20 after all steps reached `done`.

---
title: Roadmap Structural Review Remediation
intent: Ensure the one-artifact structural rewrite honors its settled merge-safety,
  generic-repository isolation, and route-selection contract.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Reject target scalars that cross physical YAML lines before building the
    bounded replacement candidate
  intent: Prevent source-span patches from accepting canonically rendered scalars
    that cannot be replaced safely as one physical line.
  files:
  - plan_tool/roadmap_structural_revision_patch.py
  - tests/test_roadmap_structural_revision_patch.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-structural-review-remediation/01-reject-target-scalars-that-cross.md
  status: done
- id: 2
  title: Prove a generic repository-owned evaluator probe works on the host before
    its Seatbelt denial and fail closed when that proof is unavailable
  intent: Make verified macOS evaluator isolation available to generic consuming repositories
    without weakening its data, metadata, or write protections.
  files:
  - plan_tool/roadmap_structural_revision_run.py
  - tests/test_roadmap_structural_revision_run.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-structural-review-remediation/02-prove-generic-repository-owned.md
  status: done
- id: 3
  title: Document both admitted route classes, scope refusal to structural preflight,
    and keep the writer single-artifact
  intent: Keep every public route guide aligned with the existing rule that same-artifact
    and cross-artifact evidence may build one bounded candidate without granting transaction
    authority, while only the structural writer refuses requires-scope-review.
  files:
  - ROADMAP_FORMAT.md
  - README.md
  - RUNBOOK.md
  - CLAUDE.md
  - CAPABILITIES.md
  - docs/ARCHITECTURE.md
  - docs/CODEX_CLI_CONTRACT.md
  - docs/ROADMAP_WALKTHROUGH.md
  - docs/cli/roadmap.md
  - integrations/claude/SKILL.md
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_cli_reference.py
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/roadmap-structural-review-remediation/03-document-both-admitted-route-classes.md
  status: done
---
# Roadmap Structural Review Remediation

## Overview

This plan completes the three remaining confirmed review fixes for the one-artifact structural roadmap rewrite. It prevents structural patches from targeting scalar spans that cross physical YAML lines, makes the macOS evaluator isolation probe work safely in generic consuming repositories, and corrects public guidance for `same-artifact` and `cross-artifact` routes. It preserves the exact receipt-analysis pair, complete snapshot binding before acceptance, the single-artifact write set, redacted telemetry, and structural-preflight refusal of `requires-scope-review`; the immutable analysis still completes successfully with no workflow for that route.

## Problem statement

Three confirmed defects remain after the one-artifact structural roadmap rewrite. The structural patcher can accept a target scalar span crossing a physical YAML line, including a canonical plain scalar naturally folded by the production renderer; the macOS isolation probe depends on the nongeneric `pyproject.toml` sentinel; and public route-selection guidance incorrectly says only `same-artifact` evidence can use the exact-pair structural rewrite. These defects leave merge safety, generic repository isolation, and route documentation inconsistent with the settled rewrite contract recorded in `.tmp/roadmap-structural-revision-escalation.handoff.md`.

## Architecture

The structural patcher refuses every target scalar span that crosses a physical YAML line. The regression case constructs a canonically rendered predecessor through the real artifact renderer so the safety rule covers naturally folded plain scalars rather than only artificial block scalars.

The macOS structural-evaluator isolation probe selects a non-symlink regular-file sentinel owned by the repository root. Its data and metadata operations must succeed outside Seatbelt before the profile's failures on that same sentinel establish the denied-root boundary; it fails closed when no such probe exists. This correction does not relax the Seatbelt profile, version pin, isolated temporary root, no-tool evaluator boundary, or denial of data and metadata reads. Detail chooses the candidate enumeration and host-check mechanism, but cannot accept a link, an outside target, or a host-inaccessible target as proof of the denied-root boundary.

Public route documentation, including the generated CLI reference and the Codex CLI command contract that expose the exact-pair route, states that both `same-artifact` and `cross-artifact` routes can construct the bounded single-artifact candidate. An unavailable evaluator rejects fact-free before evidence is loaded; after evaluator admission, exact-pair preflight validates the evidence and can reject a `requires-scope-review` analysis before seed invalidation, backend use, candidate construction, or publication. The documentation changes form one vocabulary sweep after the patch-span and evaluator corrections, without granting transaction authority.

## Input

This follow-up consumes the existing one-artifact structural roadmap rewrite contract: an exact receipt-analysis pair, complete snapshot binding before acceptance, a single-artifact write set, redacted telemetry, and `--rewrite-structural` preflight refusal of `requires-scope-review` after its successful no-workflow analysis result. `.tmp/roadmap-structural-revision-escalation.handoff.md` records the remaining confirmed findings as B (multiline scalar spans), C (Python-only evaluator sentinel), and D (cross-artifact route guidance). `docs/implementation-plans/2-roadmap-same-artifact-structural-revision.md` is the completed predecessor plan; this work does not re-run its ten implementation steps.

## References

- [YAML 1.2.2 Specification](https://yaml.org/spec/1.2.2/) — Defines plain-scalar line folding and multiline presentation semantics needed to identify unsafe physical-line-spanning spans.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Documents composition nodes, source marks, scalar styles, and safe dumping used by the structural patcher and renderer.
- [sandbox-exec(1) macOS Manual Page](https://keith.github.io/xcode-man-pages/sandbox-exec.1.html) — Provides the system command reference for executing a process under a macOS sandbox profile.
- [Accessing Files from the macOS App Sandbox](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox) — Explains macOS sandbox file-access restrictions and the interaction with other filesystem access controls.
- [Python 3.13 pathlib Documentation](https://docs.python.org/3.13/library/pathlib.html) — Documents regular-file detection, path resolution, and symlink behavior relevant to selecting a safe generic sentinel.
- [Python 3.13 subprocess Documentation](https://docs.python.org/3.13/library/subprocess.html) — Covers bounded process invocation, return-code inspection, timeouts, working directories, and discarded probe output.
- [Python 3.13 tempfile Documentation](https://docs.python.org/3.13/library/tempfile.html) — Documents securely created temporary directories and context-managed cleanup for the isolated evaluator root.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- No generic patch language, broad stage re-entry, creation, removal, reordering, relation changes, or multi-artifact transaction; the writer remains bounded to the existing single-artifact authority.
- No changes to receipt/analysis storage, snapshot binding, publication, or roadmap writer authority; this follow-up preserves the existing V1 contract.
- No new roadmap architecture stage or backlog item; this is a narrow direct-remediation follow-up rather than a new architecture effort or a re-run of the ten steps in `docs/implementation-plans/2-roadmap-same-artifact-structural-revision.md`.

## Risks

- **Physical-span misclassification — high.** A source-mark or span-boundary error could admit a scalar that reaches another physical YAML line and corrupt the bounded replacement. The patcher refuses every cross-line target, and renderer-backed regression coverage exercises the common folded plain-scalar case. Safe structural replacement of multiline scalars remains unsupported, so those inputs remain refused.
- **Unavailable evaluator-isolation probe — high.** A generic consuming repository may contain no owned, non-symlink regular file whose ordinary data and metadata operations succeed and can therefore prove Seatbelt denial of that same target. The evaluator fails closed when that safety property cannot be established, while focused tests preserve the existing isolation boundary. Structural evaluation remains unavailable in repositories without a suitable probe even when their local sandbox configuration might otherwise be safe.
- **Route-guidance drift — medium.** A missed public wording site could continue to refuse `cross-artifact` candidate construction, confuse the evaluator-first evidence-validation order with a no-workflow analysis or structural-writer preflight refusal, or imply multi-artifact transaction authority. The documentation vocabulary sweep and guide-inventory coverage pin both admitted route classes, the single-artifact write set, and the writer-only refusal boundary. Documentation introduced outside the covered public surfaces can still drift until it joins that coverage.

## Testing

Use focused tests for each correction. The patch-span regression test constructs the predecessor through the real artifact renderer and proves that merge rejects a canonical plain scalar whose target span crosses a physical YAML line; it does not rely on an artificial block-scalar fixture. The evaluator tests prove selection of a generic repository-owned sentinel, ordinary-host capability for that same sentinel, fail-closed behavior when no safe sentinel exists or a link would escape the denied root, and Seatbelt denial of both data and metadata reads. The route-guide tests inventory every named public guide, checking the CLI module description directly and its parser help through the generated reference, and prove the admitted classes, evaluator-first refusal order, and one-artifact boundary. Each step includes its focused test target, and final verification runs the full parallel test suite.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the public route guidance and generated CLI reference this step changes; green before completion.

## Acceptance criteria

- The structural patcher rejects every target scalar span crossing a physical YAML line, including a canonical plain scalar naturally folded by the production renderer.
- A regression test constructs the multiline predecessor through the real artifact renderer and proves merge rejection without using an artificial block-scalar fixture.
- On macOS, the structural-evaluator isolation probe uses a repository-owned non-symlink regular-file sentinel available in a generic consuming repository rather than a Python-specific file.
- The same sentinel's ordinary data and metadata operations succeed before its Seatbelt failures establish the denied-root proof; the evaluator fails closed when no sentinel meeting that ownership and host-capability boundary can be found.
- Evaluator tests prove generic safe-sentinel selection, ordinary-host capability, link rejection, and required denial of data and metadata reads without relaxing the Seatbelt profile, version pin, isolated temporary root, or no-tool evaluator boundary.
- Every route-selection guide named in step 3, including the generated CLI reference and `docs/CODEX_CLI_CONTRACT.md`, states that both `same-artifact` and `cross-artifact` routes can construct the bounded single-artifact candidate; it distinguishes an unavailable evaluator's fact-free early rejection from the successful no-workflow `requires-scope-review` analysis result and its evaluator-first, evidence-validating structural-preflight refusal.
- Route documentation preserves the single-artifact write set and does not describe the writer as a transaction.
- Focused route-guide coverage checks every named public guide, the CLI module description directly, and the parser-help-to-generated-reference path for both admitted classes, the refusal order, and the single-artifact boundary.
- Every step passes its focused test target, and the full parallel test suite passes for final acceptance.

## Deferred

- Safe structural replacement of multiline scalars — postpone this broader merge design because this remediation deliberately fails closed on every cross-line target.
- An alternative evaluator-isolation proof for repositories without a suitable protected regular-file probe — postpone this separate sandbox design while the evaluator fails closed.
