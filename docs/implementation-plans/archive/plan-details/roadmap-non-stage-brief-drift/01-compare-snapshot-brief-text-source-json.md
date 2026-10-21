> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Compare snapshot brief text with source.json and distinguish changed from legacy baselines

## Summary

Add a read-only baseline check to `plan_tool/roadmap_impact_snapshot.py` while capturing and rechecking recorded brief evidence. The check compares the current decoded-text digest with `source.json`’s accepted `brief_digest` and reports changed and legacy baselines distinctly. Keep `RoadmapImpactSnapshot`’s existing evidence fields and constructor compatibility intact. On green, a matching record captures normally, while changed and legacy records stop before artifact capture without any write or admission side effect.

## Table of Contents

- [Summary](#summary) — Quick statement of the completed behavior.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Explains the missing snapshot-level baseline decision.
- [Input](#input) — Defines the recorded source and digest contracts read here.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the three edited files.
- [Implementation](#implementation) — Describes the read-only classification and recheck rules.
- [Tests](#tests) — Names the focused capture and recheck coverage.
- [Acceptance criteria](#acceptance-criteria) — States observable completion conditions.
- [References](#references) — Points to the scoped policy and source contracts.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s authority and data boundaries.
- [Deferred](#deferred) — Records work owned by later route steps.

## Why

`capture_roadmap_impact_snapshot` records the current decoded brief digest but does not compare it with the accepted digest in `source.json`. That leaves structural revision, impact analysis, and root enrollment unable to tell a current baseline from changed text or an unknown legacy baseline. The snapshot seam needs one narrow, read-only classification so each later route can select and expose its own policy without inheriting stage-run rebind or lifecycle authority.

## Input

- **Recorded source contract:** `plan_tool/roadmap_source.py:read_recorded_brief_source` returns `RecordedBriefSource`, whose optional `brief_digest` is the accepted decoded-text baseline and whose `source_digest` binds raw `source.json` bytes.
- **Current brief contract:** one `brief_path.read_bytes()` result supplies both bindings. Derive comparison text from those bytes with the same UTF-8 universal-newline semantics as `plan_tool/roadmap_source.py:read_brief_text`, then pass that text to `digest_decoded_text`; retain the original bytes as raw evidence.
- **Snapshot binding contract:** `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` retains both semantic brief evidence and raw brief/source-record evidence; this step must not merge those meanings.
- **Verification limit:** this step classifies recorded-source state only. It does not select a terminal result, publish evidence, or decide whether a route may proceed.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_snapshot.py` — classify matching, changed, and legacy recorded brief baselines during capture and preserve that distinction during recheck.
  - `tests/test_roadmap_impact_snapshot.py` — make successful fixtures record a matching digest by default and add focused matching, changed, legacy, malformed, ordering, and recheck cases.
  - `tests/test_roadmap_impact_run.py` — make the ordinary impact-run fixture model a matching stage-admitted record so existing current-route tests remain current through this shared-snapshot change.

## Implementation

- **Bind semantic and raw evidence to one brief read during `_capture_recorded_brief_digests`.** Read `RecordedBriefSource.brief_digest`, then read the current brief bytes once. Derive comparison text from those retained bytes through an in-memory UTF-8 reader with universal-newline translation, matching `read_brief_text` without another source read; compute `digest_decoded_text` from that text and retain the original bytes as snapshot evidence. A present equal digest must permit ordinary snapshot capture.

- **Keep changed and legacy distinct.** A valid source record with no `brief_digest` must produce a legacy-specific snapshot failure. A valid digest that differs from the current decoded brief text must produce a changed-specific snapshot failure. Give callers a stable way to distinguish these cases from the existing general `RoadmapImpactSnapshotError` path.

- **Compare decoded text only.** The comparison must use `digest_decoded_text` over text derived from that single byte read with stage admission’s universal-newline semantics. It must not use `source_record_digest`, `brief_raw_digest`, or a direct hash of on-disk brief bytes as the acceptance baseline.

- **Reject torn evidence.** Do not perform a second brief read after computing the accepted digest. A capture or recheck either binds decoded comparison and raw evidence to one byte sequence or fails before artifact work; it cannot report a current result based on one brief version while retaining another.

- **Reject before artifact work.** Keep the comparison in the recorded-brief capture path that runs before `capture_roadmap_impact_snapshot` calls `_capture_artifact`. A changed or legacy brief must not reach artifact parsing or current-gate evaluation.

- **Preserve malformed-source behavior.** A malformed present `brief_digest` must remain malformed input through `read_recorded_brief_source`; it must not be treated as either legacy or changed.

- **Preserve the classification through `recheck_roadmap_impact_snapshot`.** When a previously matching snapshot sees changed text or a now-legacy record during its second capture, recheck must surface the matching changed or legacy failure rather than flattening it into `StaleRoadmapImpactSnapshotError`. Continue using `StaleRoadmapImpactSnapshotError` for a second capture that remains baseline-matched but no longer reproduces the captured raw source, raw brief, artifact, identity, or gate binding.

- **Keep the snapshot value compatible.** Do not add a required `RoadmapImpactSnapshot` constructor field for this classification. Existing consumers and test builders construct snapshots directly, while later route steps can handle the dedicated capture and recheck failures at their own boundaries.

- **Migrate ordinary current-route test setup without selecting a route policy.** Make `tests/test_roadmap_impact_run.py:_write_roadmap` write the matching decoded-text digest with its ordinary brief path. Keep tests that deliberately remove `brief_digest` as explicit legacy cases. Until step 3 maps these snapshot subclasses for inspection, update its changed-brief assertion to the existing generic `unavailable` result rather than the old stale-candidate result. Do not add changed-brief or legacy-brief impact outcomes here; steps 2 and 3 own those mappings.

- **Keep the helper read-only.** `capture_roadmap_impact_snapshot`, `recheck_roadmap_impact_snapshot`, and `_capture_recorded_brief_digests` must not acquire a writer guard, update `source.json`, emit stage-run lifecycle data, or gain a rebind path. Retain the existing raw-byte evidence and pending-generation checks.

- **Do not reuse stage-run admission control flow.** `plan_tool/roadmap.py:_run_roadmap` performs a similar comparison because it owns stage admission and same-path rebind. Leave that owner unchanged; a shared admission framework would broaden this step beyond its snapshot contract.

## Tests

- `test_capture_accepts_matching_recorded_brief_baseline` — a source record containing the digest of the current decoded brief captures successfully and retains the existing snapshot evidence.
- `test_capture_matches_stage_admission_digest_for_crlf_brief` — a CRLF-backed brief whose `source.json` digest comes from `read_brief_text` remains matching while its raw-byte evidence remains distinct.
- `test_capture_binds_decoded_digest_and_raw_evidence_to_one_brief_read` — a controlled brief reader that would return different bytes on a second read proves capture retains and compares one byte sequence rather than accepting one version and recording another.
- `test_capture_refuses_changed_brief_before_artifact_capture_without_mutation` — changed decoded text raises the changed-baseline failure before any stage parser runs and leaves inputs unchanged.
- `test_capture_refuses_legacy_brief_before_artifact_capture_without_mutation` — a valid path-only record raises the legacy-baseline failure before artifact work and does not add a digest.
- `test_capture_keeps_malformed_brief_digest_as_malformed_source` — malformed digest metadata remains a general malformed snapshot input failure, not either new baseline category.
- `test_recheck_preserves_changed_brief_baseline_failure` — a matching capture followed by a brief edit returns the changed-baseline failure from recheck.
- `test_recheck_preserves_legacy_brief_baseline_failure` — a matching capture followed by removal of `brief_digest` returns the legacy-baseline failure from recheck.
- `test_recheck_marks_source_record_presentation_change_stale_when_baseline_matches` — a source-record byte change that retains the same accepted digest remains a stale binding failure.
- `tests/test_roadmap_impact_run.py` ordinary current-route cases — verify their shared fixture records a matching stage-admitted digest, explicit path-only cases remain legacy input for later route-policy steps, and the pre-step-3 changed-brief inspection path remains generically unavailable.

### Tests for this step

Every listed case in `tests/test_roadmap_impact_snapshot.py` and the ordinary current-route cases in `tests/test_roadmap_impact_run.py` must be green before this step is considered finished. Existing capture, raw-presentation, artifact-identity, gate, pending-generation, and no-write tests must remain green as regression coverage.

## Acceptance criteria

- A recorded `brief_digest` equal to the current decoded UTF-8 brief text allows `capture_roadmap_impact_snapshot` to return its normal snapshot.
- A missing `brief_digest` on an otherwise valid source record produces a legacy-specific read-only snapshot failure.
- A differing valid `brief_digest` produces a changed-specific read-only snapshot failure.
- A malformed digest remains malformed source data and does not match either changed or legacy behavior.
- Changed and legacy failures occur before artifact parsing and leave `source.json`, artifacts, baselines, and writer-lock state unchanged.
- A matching capture or recheck derives its accepted decoded-text digest and retained raw brief evidence from one brief read; a torn read cannot yield a current snapshot.
- A CRLF brief whose accepted digest was written by stage admission remains matching, while its retained raw bytes and raw digest stay exact.
- `recheck_roadmap_impact_snapshot` preserves changed and legacy failure categories, while a raw source-record change with a still-matching baseline remains stale.
- Existing ordinary impact-route fixtures remain matching after this shared snapshot change, while explicit path-only cases remain legacy for step 2.
- `tests/test_roadmap_impact_snapshot.py` and `tests/test_roadmap_impact_run.py` pass with the new focused cases and existing regression coverage.

## References

- [BACKLOG.md closed route-local brief-drift record](../../../../../BACKLOG.md) — Read the route-specific authority boundary this snapshot classification supports.
- [Roadmap AI-DLC integration delivery handoff](../../../../../handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md) — Read the non-stage writer and stage-run separation.
- [ROADMAP_FORMAT.md](../../../../../ROADMAP_FORMAT.md) — Read the recorded brief digest and legacy-baseline contract.
- [plan_tool/roadmap_impact_snapshot.py](../../../../../plan_tool/roadmap_impact_snapshot.py) — Read the capture and recheck seam being extended.

## Applicable guardrails

- **Read-only route seam — the plan’s `## Scope`, shared snapshot helpers:** This step may classify source state only; it must not select route outcomes or add writer authority.

- **Digest representation — the plan’s `## Contracts and constraints`, `brief_digest` representation:** Compare the decoded-text digest only and retain raw source-record and raw brief evidence as separate bindings.

- **Legacy and malformed separation — the plan’s `## Contracts and constraints`, legacy baseline rule:** Preserve an absent digest as unknown legacy state and retain malformed metadata as malformed input.

- **Writer-window recheck — the plan’s `## Contracts and constraints`, capture and recheck requirement:** Apply the same one-read baseline classification during both initial capture and final recheck.

- **No stage-run authority — the plan’s `## Out of scope`, non-stage route boundary:** Do not add lifecycle events, same-path rebinding, or stage-run admission behavior to the snapshot module.

- **Redaction — the plan’s `## Contracts and constraints`, result disclosure boundary:** Failure categories must not expose brief text, absolute paths, or stored evidence bodies.

## Deferred

- **Route-specific result mapping** — steps 2 through 5 own the impact, inspection, structural-revision, and enrollment outcomes that consume these baseline failures.

- **Impact changed-brief and legacy-brief behavior** — step 2 owns distinct impact outcomes; this step only keeps its ordinary current-route fixture compatible with the new shared baseline contract.

- **Stage-run admission consolidation** — `plan_tool/roadmap.py:_run_roadmap` remains unchanged because it owns stage admission and baseline replacement; combining it with this read-only seam is separate shared work.
