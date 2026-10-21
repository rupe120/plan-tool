> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Persist and check brief digests before artifact admission

## Summary

Update `plan_tool/roadmap.py` so a roadmap records the accepted decoded-text brief digest with its first `source.json` write and checks that baseline before loading artifacts or contacting a backend. Add the `roadmap_source_admission` lifecycle event in `plan_tool/run_log.py`, document its persisted shape in `DATA_CONTRACT.md`, and cover the decisions in `tests/test_roadmap.py` and `tests/test_run_log.py`. The key design decision is to fail closed at one shared preflight point for every stage route, while preserving the existing post-publication atomic source write. On green, unchanged recorded briefs proceed as today, while legacy, changed, or malformed records cannot reach artifact admission, replacement, or seed cleanup.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the changed admission boundary.
- [Table of Contents](#table-of-contents) — Section map for this detail.
- [Why](#why) — The silent source-drift gap this step closes.
- [Input](#input) — Persisted source and lifecycle contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — In-scope source, test, and contract changes.
- [Implementation](#implementation) — Required digest persistence, admission, and ordering behavior.
- [Tests](#tests) — Focused regression coverage for every admission result.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Contracts and code paths to consult.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Follow-up work outside this implementation.

## Why

`plan_tool/roadmap.py:_run_roadmap` already reads and logs a brief digest, but `source.json` only stores the path, so a changed file at that same path can continue through a run as if it were unchanged. The roadmap must compare current decoded text to the accepted baseline before any artifact becomes input, because allowing that comparison later can spend backend work or mutate artifacts and seed state under an unaccepted brief.

## Input

- **Step 1 recorded-source contract:** Step 1 extends `plan_tool/roadmap_source.py:RecordedBriefSource` and `read_recorded_brief_source` with a validated optional saved decoded-text digest and rejects an existing directory at the source-record target. This step must use that shared record state rather than reopen, reparse, or separately classify `source.json`.

- **Digest contract:** `plan_tool/roadmap_source.py:digest_decoded_text` remains the sole digest meaning for this flow. Compare the current text returned by `read_brief_text` using that contract.

- **Existing stage lifecycle:** `plan_tool/roadmap.py:_run_roadmap` currently resolves and reads the brief before `_load_and_regate_below`, `_load_predecessors`, `publish_stage_artifact`, and seed-state effects. Keep the new admission at that boundary.

- **Existing source persistence:** `plan_tool/roadmap.py:_write_brief_source` writes `source.json` through `plan_tool/fileio.py:atomic_write_text` only after the first successful stage artifact publication. This step extends that record, not its publication timing.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — read the step-1 recorded source shape, persist the initial accepted digest, decide source admission before artifact work, and emit lifecycle facts.
  - `plan_tool/run_log.py` — add the typed `roadmap_source_admission` event and `RunLogWriter` emitter; extend the recorded-source event only if the final lifecycle contract needs its persisted digest.
  - `tests/test_roadmap.py` — cover initial persistence, matched re-entry, each refused preflight path, ordering, and preservation of existing artifacts and seed state.
  - `tests/test_run_log.py` — cover event construction, serialization, and lifecycle event contents without brief text.
  - `DATA_CONTRACT.md` — document the source-record digest field and `roadmap_source_admission` event shape and ordering.

## Implementation

The foundational logic is: **admit a current brief only when it has an initial baseline or exactly matches the recorded decoded-text digest.**

- **Use one admission decision before artifacts.** Adapt `plan_tool/roadmap.py:_resolve_brief_path` and `_run_roadmap` so the code can retain the step-1 `RecordedBriefSource` state alongside the effective path. A caught `RoadmapSourceError` for malformed persisted metadata decides `refused-malformed` before any brief read. After `read_brief_text` succeeds, decide whether the run is `initial`, `matched`, `refused-legacy`, or `refused-changed` before `_load_and_regate_below` or `_load_predecessors` runs.

- **Keep path identity separate from content identity.** Preserve `_resolve_brief_path`’s existing different-path refusal. A recorded path still selects the source; the saved decoded-text digest decides whether the current contents are admissible. Do not treat a same-path mismatch as a path change or silently establish a new baseline.

- **Fail closed for unknown, changed, or non-replaceable source state.** A record with no saved digest from step 1 is legacy/unknown and must refuse. A valid saved digest that differs from `digest_decoded_text(brief)` must refuse. Invalid source metadata and an existing directory at the source-record target follow the malformed admission result rather than being treated as a match or eligible absence. Each refusal stops before artifact loading, stage prompts, invoker calls, `publish_stage_artifact`, artifact replacement, or seed invalidation.

- **Preserve the initial write transaction shape.** Extend `plan_tool/roadmap.py:_write_brief_source` to include the digest for the exact decoded brief accepted by the run. Continue calling it only after `publish_stage_artifact` succeeds for the first accepted stage, and continue using `atomic_write_text`. Do not create or rewrite `source.json` when the first stage exhausts its attempts or a run stops at source admission.

- **Preserve ordinary writes and replacements.** For an `initial` or `matched` admission, keep the existing `publish_stage_artifact` path, replacement behavior, read-back admission, and seed cleanup unchanged. The source check must not add a separate artifact mutation, seed-state rewrite, or retry category.

- **Emit one decision event per run that reaches admission.** Add a frozen lifecycle event, likely `RoadmapSourceAdmission`, in `plan_tool/run_log.py` with a closed producer-owned disposition vocabulary and an always-safe `source_record_path`. `RunLogWriter` emits `refused-malformed` from the source-record error path before any brief read; it emits every other disposition after the brief read and before artifact admission. Refusals emit this event before the existing `roadmap_preflight_failed` fact, and admitted paths must not emit a duplicate decision later in the stage loop.

- **Keep lifecycle facts narrow and redacted.** The new event records the decision and the portable `source.json` path—repository-relative when possible and absolute otherwise—never brief text. That path remains available even when invalid JSON or an invalid `brief_path` prevents a safe brief reference. Keep `RoadmapSourceResolved`, `RoadmapSourceRecorded`, and `RoadmapPreflightFailed` as separate facts rather than overloading one of them with admission semantics.

- **Document the real persisted contract.** Update `DATA_CONTRACT.md` near `RoadmapSourceResolved` and `RoadmapSourceRecorded` to describe the saved digest and the new admission event, including when each event appears. The code owns the final field names and exact values; the document must match them.

- **Do not widen shared source authority.** `plan_tool/roadmap_source.py` remains the reader and digest-contract owner from step 1. Do not move source selection, lifecycle reporting, artifact gates, or source acceptance into that module.

## Tests

### Tests for this step

- `tests/test_roadmap.py::test_initial_stage_write_persists_the_decoded_brief_digest_atomically_after_artifact_publish` — asserts the first accepted artifact is published before `source.json` appears, and the record contains the digest from `digest_decoded_text`.

- `tests/test_roadmap.py::test_matched_recorded_brief_reentry_reaches_existing_artifact_admission` — asserts unchanged recorded text follows the current re-entry path and does not rewrite the source record.

- `tests/test_roadmap.py::test_changed_recorded_brief_refuses_before_artifact_loading_or_backend_call` — changes brief text at the recorded path and asserts no artifact loader or invoker is reached.

- `tests/test_roadmap.py::test_legacy_record_without_brief_digest_refuses_before_publication` — asserts a valid path-only source record cannot replace an artifact or change seed state.

- `tests/test_roadmap.py::test_malformed_recorded_source_emits_malformed_admission_before_read_or_preflight_failure` — asserts malformed source metadata records only the safe source-record path, produces the closed malformed decision before a brief read, and reaches no stage work.

- `tests/test_roadmap.py::test_source_record_directory_refuses_before_initial_artifact_publication` — places a directory at the computed `source.json` target and asserts malformed admission occurs before artifact loading, backend invocation, or publication.

- `tests/test_roadmap.py::test_refused_brief_admission_preserves_existing_artifacts_and_seed_cleanup_state` — asserts changed and legacy brief refusals leave existing artifact bytes and seed-state bytes unchanged.

- `tests/test_roadmap.py::test_first_stage_failure_does_not_persist_a_source_digest_or_source_record` — asserts an exhausted or failed initial stage cannot create a baseline.

- `tests/test_roadmap.py::test_each_brief_admission_path_emits_one_decision_before_artifact_admission` — covers initial, matched, legacy, changed, and malformed paths; asserts malformed precedes reading, the other dispositions follow reading, and every path records one lifecycle decision before artifact work.

- `tests/test_run_log.py::test_roadmap_source_admission_event_serializes_closed_disposition_without_brief_text` — asserts event construction and JSONL serialization retain the disposition and omit source content.

- `tests/test_run_log.py::test_roadmap_source_recorded_carries_the_persisted_brief_digest` — asserts the recorded-source lifecycle event matches the durable source baseline if that field is added to the event contract.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A first successful stage write stores both the existing brief path and the decoded-text SHA-256 digest in `source.json` through `plan_tool/roadmap.py:_write_brief_source`.

- The source record is not created when an initial stage fails before artifact publication.

- An unchanged recorded brief reaches the existing artifact-admission and stage-run path without changing artifact, replacement, or seed-cleanup behavior.

- A legacy record with no saved digest, a changed recorded brief, malformed source metadata, and an existing directory at the source-record target each stop before artifact loading, backend invocation, publication, replacement, and seed cleanup.

- Every run that reaches source admission emits exactly one `roadmap_source_admission` event before artifact admission. Malformed metadata records the safe source-record path before any brief read; other dispositions follow a successful read; refusal paths emit the decision before `roadmap_preflight_failed`.

- Lifecycle records and `DATA_CONTRACT.md` retain path and digest facts only, never brief text.

- `tests/test_roadmap.py` and `tests/test_run_log.py` pass.

## References

- [Roadmap Brief Source Drift plan — Read the architecture, testing, and lifecycle decision contract for this step.

- [BUG_BACKLOG.md — Read the originating changed-brief risk entry.

- [plan_tool/roadmap.py — Consult `_resolve_brief_path`, `_write_brief_source`, and `_run_roadmap` for source selection and stage ordering.

- [plan_tool/roadmap_source.py — Use `RecordedBriefSource`, `read_recorded_brief_source`, and `digest_decoded_text` as the source-record contract from step 1.

- [DATA_CONTRACT.md — Update the roadmap lifecycle event documentation to match the persisted code shape.

- [docs/ARCHITECTURE.md — Consult the “Brief-source persistence” boundary when preserving one-shot source binding.

- [ROADMAP_FORMAT.md — Consult source and re-entry rules that prohibit automatic re-grounding.

## Applicable guardrails

- **The plan’s “## Step intent”, source admission only** — block changed or unknown content before downstream work while leaving matched runs unchanged.

- **The plan’s “## Out of scope”, artifact regeneration and reconciliation** — do not regenerate, reconcile, or otherwise alter artifacts because a brief changed.

- **The plan’s “## Out of scope”, source acceptance surfaces** — do not add an acceptance flag, prompt, or alternate recovery route in this step; step 3 owns the explicit same-path exception.

- **The plan’s “## Out of scope”, existing roadmap semantics** — retain source path identity, artifact-gate behavior, feedback behavior, retry budgets, and stage exit rules.

## Deferred

- Explicit same-path source-baseline acceptance — step 3 owns the operator-authorized rebinding flow and its lifecycle result.

- Source-admission and operator guidance documentation outside `DATA_CONTRACT.md` — step 4 owns the format, architecture, user-facing, and backlog updates.
