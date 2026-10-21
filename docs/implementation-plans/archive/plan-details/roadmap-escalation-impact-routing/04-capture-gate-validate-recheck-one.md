> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Capture, gate validate, and recheck one coherent roadmap and brief snapshot

## Summary

Create `plan_tool/roadmap_impact_snapshot.py` and `tests/test_roadmap_impact_snapshot.py` for a read-only current-state snapshot of one roadmap. The module captures raw recorded-brief source bytes, all four canonical artifact byte streams, parsed artifacts, and safe digests; it rejects any input that is unreadable, noncanonical, or fails a current gate tuple. Its key rule is that capture and recheck bind the same exact raw source record, artifact bytes, gates, and broad-equivalent brief digest rather than combining later reads. Green means later analysis can consume one validated snapshot and refuse it if any bound input changes before publication.

## Table of Contents

- [Summary](#summary) — The completed snapshot boundary and observable result.
- [Table of Contents](#table-of-contents) — Links to each section in this file.
- [Why](#why) — Why impact analysis needs one bound current-state read.
- [Input](#input) — Existing stage, gate, artifact, and brief-reader contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — New snapshot module and focused tests.
- [Implementation](#implementation) — Capture, validation, recheck, and side-effect boundaries.
- [Tests](#tests) — Cases that prove coherent capture and stale-snapshot refusal.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Primary documentation for digest, JSON, locking, and test seams.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Later ownership for locking, receipt checks, and analysis publication.

## Why

`plan_tool/roadmap.py:_load_and_regate_below` validates only the upstream portion needed for broad re-entry, while `plan_tool/roadmap_revision_publish.py:publish_revision_candidate` validates one replacement candidate. Neither produces a reusable, full current-state binding for the four artifacts, `source.json`, and recorded brief. Without that binding, impact analysis could validate one revision and derive evidence from another.

## Input

- **Stage contract:** Reuse the ordered `plan_tool/roadmap.py:STAGES` and `RoadmapStage` fields as the source of artifact paths, parsers, renderers, and gate entry points. Do not create another four-stage inventory or invoke `plan_tool/roadmap.py:run_roadmap`.

- **Artifact contract:** Read the canonical paths selected by each stage and require `stage.render(stage.parse(text))` to reproduce the captured artifact text. `plan_tool/roadmap_artifacts.py:brief_source_path` identifies the source-record location.

- **Current-state gates:** Build each `plan_tool/roadmap_gates.py:ArtifactEnvelope` from the captured artifacts through that stage and invoke the stage’s complete gate tuple with `predecessor=None`.

- **Recorded brief contract:** Step 3 supplies the landed `plan_tool/roadmap_source.py` reader, raw source-record byte digest, and decoded-text brief-digest contracts. Use those contracts for source-record interpretation, brief text, and their distinct digests; do not recreate source-path rules or hashing behavior.

- **Writer coordination:** `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` remains the caller-owned boundary. Step 8 holds it while it calls capture and recheck; this module must not acquire it itself.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_impact_snapshot.py` — Provide the immutable snapshot result plus read-only capture and freshness-recheck operations.
  - `tests/test_roadmap_impact_snapshot.py` — Cover successful capture, validation failures, byte binding, rechecks, and side-effect boundaries.

- **Existing files (edits only):**
  - None.

## Implementation

- **Foundational rule:** Return a snapshot only when one exact raw source-record read, four artifact byte streams, their parsed values, the full current gate results, and the recorded brief digest all describe the same current input set. A failed capture or recheck returns no partial snapshot.

- **Capture raw artifacts before treating them as model data.** Read each stage artifact in `plan_tool/roadmap.py:STAGES` order, decode it as UTF-8, parse it through the stage parser, and require the corresponding renderer to reproduce the captured text exactly. Keep ordered artifact-byte digests alongside the parsed artifacts so later analysis can bind its evidence to what was read, not to a re-rendered approximation.

- **Bind the source record and brief together.** Use step 3’s `plan_tool/roadmap_source.py` contract to read raw `source.json` bytes, parse those same bytes, and read the referenced brief. Preserve SHA-256 of the exact raw source-record bytes and the broad-equivalent decoded-text brief digest as distinct fields. Do not retain or expose the brief path, source-record bytes, or brief text as snapshot evidence.

- **Run every current gate tuple.** For each captured stage, construct `plan_tool/roadmap_gates.py:ArtifactEnvelope` from that stage and all captured upstream artifacts, then invoke the stage’s own gate entry point. Always pass `predecessor=None`; do not filter `DOMAIN_GATES`, `CONSTRAINTS_GATES`, `COMPONENTS_GATES`, or `PLANS_GATES`.

- **Keep predecessor-independent checks active.** `predecessor=None` makes only prior-version comparisons inactive. `plan_tool/roadmap_gates.py:check_design_row_continuity` still validates local removal records, and `plan_tool/roadmap_gates.py:check_feedback_integrity` still rejects invalid current feedback such as duplicate ids. Do not remove these gates because review data is excluded from later relation closure.

- **Make freshness a second complete validation.** Provide a recheck operation that rereads exact raw source-record bytes, the artifact byte vector, and recorded brief through the same capture rules; compares them with the original binding; and reruns the full gate sequence. A source-record whitespace or newline change, changed artifact bytes, brief digest, parse/render result, or gate result makes the snapshot stale and unusable.

- **Keep capture read-only and narrow.** Do not acquire `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard`, write `source.json`, publish evidence, call a backend, inspect a receipt, calculate relation closure, or assign a route. Step 8 supplies guarded execution; steps 2 and 5 own closure and routing.

- **Use one stage source, not copied mechanics.** One approach is to accept the ordered stage contract as an input so focused tests can control interleavings while production passes `plan_tool/roadmap.py:STAGES`. The required outcome is that production has one stage inventory and tests can prove recheck behavior without a filesystem race.

## Tests

### Tests for this step

- `test_capture_returns_an_ordered_canonical_current_snapshot` — A valid raw source record, recorded brief, and four canonical artifacts produce parsed artifacts plus ordered source-record, artifact, and brief digests.

- `test_capture_rejects_missing_unreadable_or_malformed_source_artifact_or_brief_without_partial_snapshot` — Every required input failure produces the snapshot failure path and exposes no partially captured result.

- `test_capture_rejects_parseable_but_noncanonical_artifact_text` — Artifact text that parses but differs from its stage renderer is not admitted.

- `test_capture_uses_each_stage_current_gate_tuple_with_predecessor_none` — Every stage receives its captured upstream envelope, its own gate entry point runs in stage order, and each envelope has `predecessor is None`.

- `test_predecessor_none_keeps_removal_and_feedback_integrity_checks_active` — A locally invalid removal record or duplicate feedback id rejects capture even though predecessor-only comparisons are inactive.

- `test_capture_uses_step_threes_recorded_brief_and_decoded_text_digest_contract` — Relative recorded paths, UTF-8 decoding, and the brief digest match the landed step 3 reader contract.

- `test_recheck_accepts_an_unchanged_snapshot` — A second full read of identical inputs preserves the captured binding and succeeds.

- `test_recheck_refuses_changed_raw_source_record_artifact_bytes_or_brief_digest` — A change to any bound input, including semantically equivalent `source.json` whitespace, after capture rejects the snapshot rather than mixing old and new data.

- `test_recheck_reruns_current_gates_even_when_captured_bytes_match` — A controlled gate result that becomes invalid after capture makes recheck fail, proving freshness is not only a digest comparison.

- `test_snapshot_capture_never_acquires_writer_guard_or_writes_evidence` — Capture and recheck perform no lock acquisition, backend call, canonical write, evidence publication, or telemetry write.

- **Green-before-done gate:** `uv run pytest tests/test_roadmap_impact_snapshot.py -q` passes.

## Acceptance criteria

- A successful snapshot binds exactly one raw recorded-source byte stream and its SHA-256 digest, four UTF-8 canonical artifact texts, parsed artifact set, ordered artifact-byte digest vector, and decoded-text brief digest.

- Every artifact satisfies `render(parse(captured_text)) == captured_text` before it enters a snapshot.

- Each stage’s complete current gate tuple runs with `ArtifactEnvelope.predecessor=None`; predecessor-independent removal and feedback-integrity failures still reject capture.

- Recheck rereads and revalidates all bound inputs and rejects any changed, unreadable, malformed, noncanonical, or gate-invalid state without returning a usable snapshot.

- `plan_tool/roadmap_impact_snapshot.py` creates no lock, evidence, telemetry, canonical artifact, backend call, receipt decision, closure, or route.

- `uv run pytest tests/test_roadmap_impact_snapshot.py -q` passes.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Read this for the recorded `source.json` decoding boundary.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Read this for binding artifact and brief content to SHA-256 digests.

- [fcntl — The fcntl and ioctl system calls](https://docs.python.org/3.13/library/fcntl.html) — Read this for the advisory locking behavior that step 8 uses around snapshot capture and recheck.

- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Read this for controlled changed-input and gate-result tests.

## Applicable guardrails

- **The plan’s “## Step intent,” coherent current-state snapshot:** Limit this step to capturing and validating one current snapshot; do not add receipt, closure, routing, or publication behavior.

- **The plan’s “## Architecture,” complete current gate tuple:** Keep the full stage gates active with `predecessor=None`; only their prior-version checks become inactive.

- **The plan’s “## Architecture,” recorded-brief binding:** Use step 3’s broad-equivalent source and decoded-text digest contract rather than a separate path or hash policy.

- **The plan’s “## Out of scope,” writer boundary:** Do not replace, widen, or acquire the existing writer coordination boundary from this module.

- **The plan’s “## Out of scope,” operational workflow changes:** Do not call a backend, mutate artifacts or reviewer state, infer relations from prose, or choose a patch.

## Deferred

- Guard acquisition and the before-publication call sequence — step 8 owns holding `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` while it captures and rechecks.

- Receipt revalidation, declared closure, immutable analysis identity, and route precedence — steps 2 and 5 own those consumers of a valid snapshot.

- Consolidating `plan_tool/roadmap.py:_load_and_regate_below`, `plan_tool/roadmap.py:_build_envelope`, and `plan_tool/roadmap_revision_publish.py:publish_revision_candidate` with snapshot logic — these callers have different re-entry and publication policies; a shared refactor exceeds this step’s new-file scope.
