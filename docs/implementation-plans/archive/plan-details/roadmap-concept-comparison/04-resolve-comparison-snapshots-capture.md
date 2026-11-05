> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Resolve comparison snapshots and capture all four controlled Git patches without writing roadmap state

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Create `plan_tool/roadmap_compare_run.py` as the read-only operation that selects two roadmap snapshots, validates their complete artifact bundles, and captures Git’s unified patch for every fixed artifact pair. Add `tests/test_roadmap_compare_run.py` for selection, snapshot refusal, controlled Git outcomes, and no-write behavior. Keep the operation separate from rendering: it returns identified snapshots, parsed artifacts, digests, and complete patch evidence for step 5. On green, a valid comparison produces four controlled Git results, including byte-identical pairs, without changing roadmap or Git state.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the comparison operation.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why comparison needs one complete read-only snapshot and evidence boundary.
- [Input](#input) — Snapshot, typed comparison, and fixed-inventory contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — New operation module and focused tests.
- [Implementation](#implementation) — Snapshot selection, validation, Git evidence, and refusal rules.
- [Tests](#tests) — Focused behavior and safety coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Roadmap version, artifact, and comparison contracts.
- [Applicable guardrails](#applicable-guardrails) — Read-only, complete-evidence, and scope boundaries.
- [Deferred](#deferred) — Rendering and CLI work left to later steps.

## Why

Step 2 can attribute typed changes only after it receives complete raw evidence, while step 3 makes immutable selections trustworthy but does not load working artifacts or invoke Git. A comparison needs one owner that binds each selected side to the exact four parsed byte streams and collects Git’s evidence under controlled options. Without that boundary, callers could compare a partial or changing live bundle, trust a malformed stored member, or present a patch affected by local Git diff behavior.

## Input

- **Step 2 comparison contract:** Consume step 2’s pure typed comparison and raw-evidence attribution surface from `plan_tool/roadmap_compare.py`. Supply it complete artifact-pair evidence; do not recreate concept matching or raw-evidence identity rules here.
- **Step 3 immutable reader:** Use step 3’s complete explicit-version reader in `plan_tool/roadmap_versions.py`, alongside `load_accepted_version`, for immutable base and target selection.
- **Fixed artifact inventory:** Use `plan_tool/roadmap_versions.py:VERSION_ARTIFACT_INVENTORY` as the sole ordered inventory for snapshot bytes, artifact digests, and the four Git invocations.
- **Working artifact contract:** Use `plan_tool/roadmap_artifacts.py:roadmap_dir` and the typed parsers associated with each configured artifact key to read and validate the current working target. The working snapshot must retain the bytes it parsed rather than rereading files later.
- **Snapshot metadata:** Retain immutable version kind, version id, and recorded brief digest when supplied by `ResolvedRoadmapVersion`. A working snapshot must not invent a version or brief identity that it cannot bind.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_compare_run.py` — Own snapshot selection, complete working-bundle loading, controlled per-artifact Git patch capture, and read-only comparison results.
  - `tests/test_roadmap_compare_run.py` — Cover selectors, fail-closed input validation, Git result handling, complete evidence, and state preservation.

- **Existing files (edits only):**
  - None.

## Implementation

- **Foundational logic:** Resolve two complete roadmap snapshots and collect one controlled Git no-index patch for each fixed artifact pair.

- **Keep selection closed.** Support only the snapshot forms named by the plan: a base selected from `load_accepted_version` or an explicit stored version, and a target selected from working artifacts or an explicit stored version. An absent accepted head must refuse a default-base request; it must not choose a live bundle or another stored version as a fallback.

- **Load immutable versions through step 3.** Use the public complete reader from `plan_tool/roadmap_versions.py` for explicit ids and `load_accepted_version` for the default base. Preserve `ResolvedRoadmapVersion.record`, `brief_bytes`, and fixed-order `artifact_bytes` as the immutable snapshot’s bound inputs.

- **Capture the working target once.** Read all configured artifact paths before beginning comparison work, decode each as strict UTF-8, and parse each with its matching `plan_tool/roadmap_artifacts.py:parse_domain_artifact`, `parse_constraints_artifact`, `parse_components_artifact`, or `parse_plans_artifact` contract. Retain the exact bytes, parsed values, and SHA-256 digests from that read. Missing, unreadable, undecodable, or unparseable members must refuse the whole comparison before Git runs.

- **Validate every resolved bundle before comparison.** Apply the same strict UTF-8
  decode and artifact-parser validation to the captured immutable bytes as to the
  working bytes. Step 3 remains the byte-integrity reader; this operation owns
  parsing because it needs parsed values for the typed diff. A digest-valid but
  syntactically invalid immutable member refuses before Git runs.

- **Require a complete pair.** Both snapshots must contain exactly the configured artifact keys in `VERSION_ARTIFACT_INVENTORY` order. Do not compare an available subset, skip an unchanged artifact, or splice bytes from another snapshot. The parsed values and raw bytes passed to step 2 must come from the same captured bundle.

- **Capture every patch through Git.** For each configured artifact pair, invoke Git’s no-index diff engine with external diff, text conversion, and color disabled. Use controlled temporary copies of the already-captured bytes so Git receives the exact snapshot data and does not read mutable live artifact paths during patch collection. Give each side stable artifact labels so temporary paths do not leak into evidence or make output vary between runs.

- **Treat Git status as evidence, not failure by itself.** Status `0` means a successful identical pair and retains its empty patch result. Status `1` means a successful differing pair and retains Git’s complete unified patch unchanged. Any other status, launch error, or inability to decode the captured patch must refuse the entire comparison rather than returning partial evidence.

- **Do not substitute a Python diff.** `difflib` and a generalized repository-diff interface are not replacements for Git’s required evidence. The operation may use local temporary files to drive Git, but it must not write roadmap artifacts, version records, selectors, baselines, receipts, seeds, run logs, or the Git index.

- **Return facts for later layers.** Expose a small immutable operation result that gives step 5 the two snapshot identities, fixed-order artifact digests, parsed artifacts, all four raw patch results, and the step 2 comparison result. Keep terminal formatting, JSON shape, labels from `plan_tool/roadmap_view.py:display_label`, and CLI argument parsing out of this module.

## Tests

### Tests for this step

- `tests/test_roadmap_compare_run.py:test_default_base_uses_complete_accepted_version` — an accepted-head base reaches the complete immutable reader and retains its record identity, brief digest, artifact bytes, and digests.
- `tests/test_roadmap_compare_run.py:test_explicit_stored_base_and_target_use_complete_version_reader` — explicit stored selectors do not fall back to accepted or working content.
- `tests/test_roadmap_compare_run.py:test_missing_accepted_head_requires_explicit_base` — a default-base request refuses when no accepted selector exists.
- `tests/test_roadmap_compare_run.py:test_working_target_captures_and_parses_all_configured_artifacts` — a working target returns the exact bytes, parsed artifacts, and digests for the fixed inventory order.
- `tests/test_roadmap_compare_run.py:test_working_snapshot_refuses_before_git_for_missing_invalid_or_non_utf8_member` — any incomplete or invalid working bundle prevents every Git invocation.
- `tests/test_roadmap_compare_run.py:test_stored_snapshot_refusal_does_not_fall_back_or_run_git` — corrupt, missing, digest-mismatched, or digest-valid-but-unparseable immutable content refuses without another selector or partial evidence.
- `tests/test_roadmap_compare_run.py:test_every_inventory_artifact_gets_one_controlled_git_patch` — all configured artifact pairs invoke Git once, including byte-identical pairs, with controlled no-index options and stable labels.
- `tests/test_roadmap_compare_run.py:test_git_status_zero_is_successful_identical_evidence` — status `0` returns an identified pair with its retained empty patch.
- `tests/test_roadmap_compare_run.py:test_git_status_one_preserves_complete_unified_patch` — status `1` returns Git’s unchanged patch bytes/text for the correct artifact pair.
- `tests/test_roadmap_compare_run.py:test_git_launch_decode_or_abnormal_status_refuses_complete_comparison` — launch failures, undecodable patch output, and statuses outside `0` and `1` return no partial comparison result.
- `tests/test_roadmap_compare_run.py:test_comparison_does_not_write_roadmap_or_git_state_on_success_or_refusal` — successful and refused runs leave artifacts, version metadata, selectors, related roadmap state, and the Git index unchanged.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A comparison operation accepts only the plan’s working or immutable target and accepted-head or immutable base selectors.
- Default-base selection refuses when `accepted-head.json` is absent.
- Each resolved snapshot contains exactly the artifact bytes, parsed values, and digests for `VERSION_ARTIFACT_INVENTORY` in its configured order.
- A missing, corrupt, mismatched, undecodable, or unparseable member from either
  snapshot form refuses the operation before partial patches or typed output are
  returned.
- The operation invokes controlled Git no-index diff once for every configured artifact pair and preserves Git’s full unified output.
- Git statuses `0` and `1` are successful identical and differing evidence respectively; all other execution or decode outcomes refuse.
- The result provides step 5 with bound snapshot metadata, per-artifact digests, parsed artifacts, and all four patch results.
- `tests/test_roadmap_compare_run.py` passes.
- Successful and refused comparisons leave roadmap state and the Git index unchanged.

## References

- [BACKLOG.md #402](BACKLOG.md) — Read the feature’s selector, Git-evidence, and no-mutation contract.
- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Read the fixed artifact and immutable-version contracts.
- [plan_tool/roadmap_versions.py](plan_tool/roadmap_versions.py) — Read `VERSION_ARTIFACT_INVENTORY`, `ResolvedRoadmapVersion`, `load_accepted_version`, and the explicit complete reader from step 3.
- [plan_tool/roadmap_artifacts.py](plan_tool/roadmap_artifacts.py) — Read `roadmap_dir` and the artifact parsers used to validate a working snapshot.
- [plan_tool/roadmap_compare.py](plan_tool/roadmap_compare.py) — Read step 2’s supplied typed comparison and raw-evidence attribution contract.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, read-only behavior:** `plan_tool/roadmap_compare_run.py` must only read snapshots and create disposable comparison inputs; it must not change any roadmap lifecycle state.
- **The plan’s “## Scope guardrails”, raw evidence role:** Preserve Git’s complete patch for each pair unchanged and refuse rather than return incomplete evidence.
- **The plan’s “## Scope guardrails”, deterministic comparison:** Use fixed selection, inventory, and Git options; do not add model calls or generated interpretation.
- **The plan’s “## Scope guardrails”, compatibility:** Do not change existing roadmap views, candidate behavior, or lifecycle writers.
- **The plan’s “## Scope guardrails”, artifact-family boundary:** Keep comparison limited to the configured roadmap inventory.
- **The plan’s “## Out of scope”:** Do not add acceptance actions, generalized repository comparison, source-brief comparison, interactive output, or HTML rendering.

## Deferred

- **Terminal, patch, and JSON rendering** — Step 5 owns presentation of the bound operation result.
- **CLI selector parsing and output-mode selection** — Step 6 owns the command surface.
- **Roadmap-wide labels and index construction** — Later rendering reuses `plan_tool/roadmap_view.py:display_label` and its index builders without changing their ownership.
- **Acceptance policy and lifecycle recovery** — Keep candidate, promotion, enrollment, settlement, repair, and migration behavior outside this read-only operation.
