> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Replace oversized code fingerprint maps with a stable digest

## Summary

Replace the path-to-hash map persisted on telemetry `DecisionEvent` rows with one canonical SHA-256 digest. `plan_tool/telemetry.py` owns the digest rule and legacy-row normalization, while `plan_tool/refresh.py`, `plan_tool/review.py`, and `plan_tool/cli/completeness_phases.py` keep full maps only where later per-path comparison requires them. Bump the telemetry schema and keep schema-v1/v2 rows readable without changing the analysis verdict vocabulary. On green, fingerprint-heavy telemetry remains well below `_MAX_LINE_BYTES`, equal maps produce equal digests regardless of insertion order, and changed maps produce a different tested digest.

## Table of Contents

- [Summary](#summary) — Compact description of the persisted telemetry change.
- [Why](#why) — Why full fingerprint maps make valid events disappear.
- [Input](#input) — Existing map, event, and JSONL contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped source, test, and contract changes.
- [Implementation](#implementation) — Digest framing, compatibility, and producer rules.
- [Tests](#tests) — Unit and integration cases for stability and legacy tolerance.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary serialization and hashing specifications.
- [Deferred](#deferred) — Related producer work owned by later steps.

## Why

`plan_tool/telemetry.py:record_decision` drops a row when its encoded JSON exceeds `_MAX_LINE_BYTES`, and a full `code_fingerprint` map is the largest common contributor on drift-gate, code-reveals-split, and create events. Telemetry consumers use this field as a code-state identity, not to report individual changed paths; the per-path maps needed for drift checks already live in grounding and saved-review artifacts. Persisting a stable digest keeps the equality join while preventing large plans from silently losing otherwise valid decision rows.

## Input

- **Code fingerprint map** — `plan_tool/fingerprint.py:compute_code_fingerprint` produces a deterministic `{repo-relative-posix-path: sha256-hex}` map. Treat its paths and hashes as opaque strings; do not read code files again while forming the telemetry digest.
- **Telemetry event contract** — `plan_tool/telemetry.py:DecisionEvent`, `plan_tool/telemetry.py:record_decision`, and `plan_tool/telemetry.py:read_decisions` define the append-only JSONL shape and its tolerant reader.
- **Size boundary** — `plan_tool/telemetry.py:_MAX_LINE_BYTES` remains the final encoded-row limit. This step makes the known fingerprint-heavy field compact; it does not authorize truncating another oversized context bag.
- **Legacy rows** — schema-v1 rows may omit `code_fingerprint`; schema-v2 rows may contain `{}` or a full map. The reader must accept all three forms alongside the new digest form.
- **Full-map consumers** — `plan_tool/refresh.py:refresh_plan` still needs the map for `check_grounding_drift` and `write_grounding`, while `plan_tool/cli/completeness_phases.py:_persist_and_present_report` still supplies it to saved-review and convergence code that compares paths. Those artifacts are not telemetry rows.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/telemetry.py` — define the canonical map-to-digest rule, persist the compact code-state value on `DecisionEvent`, bump the schema, and normalize legacy map rows in `read_decisions`.
  - `plan_tool/telemetry_analysis.py` — keep event handling compatible with normalized legacy and new rows without changing inline or asynchronous outcome meanings.
  - `plan_tool/refresh.py` — send the compact code-state identity to `record_drift_gate` while retaining the full map for grounding comparisons and writes.
  - `plan_tool/review.py` — make the code-reveals-split producer send the compact identity from its guarded fingerprint block.
  - `plan_tool/cli/completeness_phases.py` — keep saved-review fingerprint maps separate from telemetry values and align the granularity and audit-coverage calls with the compact telemetry contract.
  - `tests/test_telemetry.py` — cover canonical hashing, persisted size, schema compatibility, and non-truncation.
  - `tests/test_telemetry_analysis.py` — prove legacy and new code-state representations do not change resolution or aggregation.
  - `tests/test_review.py` — verify the real code-reveals-split producer persists a digest rather than a path map.
  - `tests/test_data_contract.py` — drift-guard the new field meaning and telemetry schema version.
  - `DATA_CONTRACT.md` — document canonical framing, the absent sentinel, schema compatibility, and the distinction between telemetry digests and full-map artifacts.

## Implementation

The foundational logic is **canonical map-to-SHA-256 digest normalization at the telemetry persistence boundary**.

- **Persist identity, not paths.** Replace the telemetry row’s full code fingerprint map with a full-length SHA-256 hex digest. Keep the field an equality-only code-state anchor; no telemetry consumer needs the original paths.

- **Use one canonical framing rule.** A recommended shape is compact UTF-8 JSON over path/hash pairs sorted by path, with a fixed format tag included before hashing. Sorting must happen inside the digest helper so insertion order cannot affect the result. Do not use `repr`, mapping iteration order, or delimiter-only string concatenation, which can make framing ambiguous.

- **Keep the helper in the stdlib-only leaf.** Place the digest logic in `plan_tool/telemetry.py` near `_compute_decision_id` so every recorder uses one implementation without adding first-party imports. Use `json` and `hashlib`, which the module already imports.

- **Version the persisted type change.** Bump `plan_tool/telemetry.py:TELEMETRY_SCHEMA_VERSION`; changing `DecisionEvent.code_fingerprint` from a JSON object to a digest string is a breaking event-shape change. Keep the new field defaulted so positional and legacy construction remains tolerant.

- **Keep computed-empty distinct from unavailable.** Use `""` only when no fingerprint was computed (`None` / missing / legacy unavailable). A newly computed empty map is a real code state and must hash through the same canonical framing as a non-empty map, producing a non-empty digest. Legacy schema-v2 `{}` rows remain readable as unavailable because those rows did not persist a presence marker; do not project that historical ambiguity onto new events.

- **Read stored digests unchanged.** `plan_tool/telemetry.py:read_decisions` must accept a new string digest without recomputing it. For a legacy mapping, compute the normalized digest from the stored path/hash pairs; never inspect current files, because the row records past state.

- **Keep the recorder best-effort.** `plan_tool/telemetry.py:record_decision` must continue swallowing serialization, hashing, directory, and append errors. Digest failure must result in the established empty sentinel or a dropped telemetry row, never an exception in the host command.

- **Do not weaken the line cap.** Keep `_MAX_LINE_BYTES` and the “drop whole row” behavior for an unrelated oversized context. Never slice encoded JSON. A retained row must always be one complete RFC 8259 JSON value followed by a newline.

- **Make the append result truthful.** Move the low-level append into a stdlib-only helper used by `record_decision`. Hold an exclusive advisory lock for the transaction, remember the file length under that lock, and loop on `os.write` until the entire newline-terminated row is written. Treat zero progress or an exception as failure; if bytes from this attempt were written, truncate back to the remembered length before releasing the lock. Continue swallowing the failure at the public telemetry boundary. This closes normal short-write corruption and gives step 2 a reliable success signal; process death and storage corruption remain outside the best-effort contract.

  This is not a general append refactor: truthful row persistence is inseparable from this step's promise that compacted events are valid and from step 2's parent-success gate. Keep the helper private and change no unrelated storage behavior.

- **Preserve caller-side safety.** Digest computation performed before a recorder call does not inherit `record_decision`’s error swallowing. Keep it inside the existing guarded blocks at `plan_tool/refresh.py:refresh_plan` and `plan_tool/review.py:extract_recommendations`, or let the telemetry-owned recorder perform the conversion from an already-computed map.

- **Reuse the map already in hand.** `plan_tool/refresh.py:refresh_plan` computes `current_code_fp` once for drift detection. Derive the telemetry digest from that value; do not re-read the code surface inside `_emit_drift_gate`.

- **Keep review computation conditional.** In `plan_tool/review.py:extract_recommendations`, compute the code-state value only inside the existing `if split_recs` and `plan_path is not None` path. A silent detector or the non-reconcile caller must still avoid fingerprint work and telemetry output.

- **Keep completeness artifact maps intact.** In `plan_tool/cli/completeness_phases.py:_persist_and_present_report`, `code_fp` remains a full map for `write_completeness_report` and `_completeness_convergence_diagnosis`. Do not replace those values with the telemetry digest because those consumers perform code-drift comparisons. The telemetry calls in `_run_deterministic_checks` and `_sample_conceptual_audit` may continue using the unavailable sentinel where they deliberately avoid rehashing on every iteration.

- **Do not change resolver outcomes.** `plan_tool/telemetry_analysis.py:resolve_decision_inline`, `resolve_decision_async`, and `resolve_decisions` must continue producing only `acted-on`, `no-op`, `reverted`, and `still-open`. The code-state field is opaque correlation data and must not introduce a new verdict or rate rule.

- **Keep `decision_id` stable in meaning.** `_compute_decision_id` deliberately excludes the code fingerprint. Do not add the new digest to its hash inputs; doing so would change decision identity rather than only compacting a join key.

- **Document the two fingerprint forms clearly.** Update `DATA_CONTRACT.md:Decision telemetry log` and its `DecisionEvent` table to describe the digest and legacy normalization. Keep `DATA_CONTRACT.md:Fingerprints` clear that grounding, saved reviews, and detail bundles still use path-to-hash maps where per-path drift is required.

## Tests

- `test_code_fingerprint_digest_is_order_independent` — the same path/hash pairs in different insertion orders produce the same 64-character lowercase SHA-256 digest.
- `test_code_fingerprint_digest_changes_with_path_or_hash` — changing a path, adding or removing an entry, or changing a content hash changes the tested digest.
- `test_computed_empty_code_fingerprint_has_stable_nonempty_digest` — an explicitly computed `{}` hashes to a stable non-empty digest distinct from the unavailable `""` sentinel.
- `test_record_decision_persists_code_fingerprint_digest` — `tests/test_telemetry.py` confirms a supplied map is stored as the compact digest, not as path keys.
- `test_large_code_fingerprint_stays_below_line_cap` — a map that would push the old event beyond `_MAX_LINE_BYTES` records one complete, readable JSONL row.
- `test_unrelated_oversized_context_is_dropped_not_truncated` — an oversized non-fingerprint context writes no partial JSON and leaves existing rows readable.
- `test_record_decision_retries_short_write_to_complete_json_line` — a monkeypatched first short write is completed under the same locked append and the row remains readable.
- `test_record_decision_rolls_back_partial_write_on_append_failure` — a short write followed by zero progress or an exception restores the pre-append length and reports failure without leaving an invalid JSONL tail.
- `test_reads_v1_row_without_code_fingerprint` — a schema-v1 row normalizes to the empty digest sentinel.
- `test_reads_v2_row_with_empty_code_fingerprint_map` — a schema-v2 `{}` value normalizes to the empty digest sentinel.
- `test_reads_v2_row_with_code_fingerprint_map` — a schema-v2 non-empty map normalizes to the canonical digest without reading current files.
- `test_reads_current_row_with_stored_digest` — the reader preserves a stored digest exactly.
- `test_schema_version_matches_digest_contract` — `tests/test_telemetry.py` and `tests/test_data_contract.py` pin the new `TELEMETRY_SCHEMA_VERSION` and documented field.
- `test_code_reveals_split_event_carries_code_fingerprint_digest` — `tests/test_review.py` proves the real reconcile-lane producer records a digest and still carries the plan fingerprint.
- `test_code_reveals_split_fingerprint_failure_is_best_effort` — a raising fingerprint or digest computation does not change the returned recommendations.
- `test_legacy_and_current_rows_resolve_identically` — `tests/test_telemetry_analysis.py` proves equivalent old-map and new-digest events keep the same resolution.
- `test_analysis_accepts_ownerless_legacy_digest_rows` — legacy rows with empty plan or run anchors remain counted and unresolved rather than raising.

### Test-creation order (feature step)

Add the canonical digest and legacy-reader tests with `plan_tool/telemetry.py` before changing producer assertions. Then update the review wiring, analysis compatibility, and data-contract drift tests. Every new test listed above, the existing focused suites in `tests/test_telemetry.py`, `tests/test_telemetry_analysis.py`, `tests/test_review.py`, and `tests/test_data_contract.py`, and the full existing suite must be green before this step is finished.

## Acceptance criteria

- `plan_tool/telemetry.py:DecisionEvent` persists an unavailable code fingerprint as `""` and every computed map, including `{}`, as a 64-character lowercase SHA-256 digest; it never persists a new full path-to-hash map.
- Identical non-empty maps produce the same digest regardless of insertion order.
- Representative path, membership, and hash changes produce different digests under the documented framing.
- A fingerprint-heavy event that exceeded `_MAX_LINE_BYTES` with the old map records as one valid JSONL row below the cap.
- `record_decision` retries short writes to a complete newline-terminated row; a detected failure after partial progress rolls that attempt back while locked and is not reported as append success.
- Schema-v1 rows without the field and schema-v2 rows containing empty or non-empty maps remain readable.
- `read_decisions` preserves a stored current-schema digest without consulting current code.
- `plan_tool/refresh.py:refresh_plan` retains full maps for grounding while drift-gate telemetry carries only the compact identity.
- `plan_tool/review.py:extract_recommendations` records the code-reveals-split event with a compact digest and remains silent when the detector does not fire.
- `plan_tool/cli/completeness_phases.py:_persist_and_present_report` continues passing full maps to saved-review and convergence consumers that require drift comparison.
- `plan_tool/telemetry_analysis.py` retains its existing outcome vocabulary and gives equivalent legacy and current events the same result.
- `DATA_CONTRACT.md:Decision telemetry log` documents the new schema version, digest framing, unavailable sentinel, computed-empty digest, and legacy map normalization. This is the declared `DATA_CONTRACT.md` deliverable for step 1.
- All new and existing focused tests pass before completion.

## References

- [Python json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Use deterministic key or pair ordering, compact separators, Unicode handling, and valid JSON encoding.
- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Use the stdlib SHA-256 API for the compact code-state identity.
- [RFC 8785 — JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Follow its canonical ordering and UTF-8 framing principles for repeatable hashing.
- [RFC 8259 — The JavaScript Object Notation Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Preserve complete, interoperable JSON values and never truncate an oversized event.

## Deferred

- **Create assessment-to-outcome deduplication** — step 2 removes the repeated compact code-state value from each `create-step-outcome` and adds an unambiguous assessment join.
- **Backend invocation failure telemetry** — step 3 adds the new `apply-verdict` result and its resolver mapping.
- **Canonical parallel-apply ownership** — step 4 moves durable result recording to canonical replay.
- **General oversized-context diagnostics or telemetry rotation** — this step removes the known fingerprint-map cause but does not add a second log, dropped-event counter, rotation policy, or size dashboard.
- **Historical log rewriting** — old local rows are normalized when read; this step does not rewrite append-only telemetry files.
- **Replacing grounding or saved-review maps** — those artifacts retain full maps because `plan_tool/grounding.py:check_grounding_drift` and saved-review staleness checks require per-path comparison.
