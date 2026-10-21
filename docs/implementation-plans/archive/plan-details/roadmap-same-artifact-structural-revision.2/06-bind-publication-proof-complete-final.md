> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Bind publication to the proof and complete final snapshot, preserve lock-byte initialization and seed invalidation, and narrow atomic replacement to the matched artifact

## Summary

Update `plan_tool/roadmap_revision_publish.py` so structural publication accepts only a successful step-5 proof and rechecks step 2’s complete evidence binding while the existing writer lease remains active. Keep the new proof-bound publisher separate from `publish_revision_candidate`, which continues to serve local feedback revision. Publish the proof’s exact UTF-8 candidate text atomically to the rechecked selected artifact only. On green, any stale proof input or failed current gate refuses before replacement while lock and seed-state behavior stays conservative.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why proof alone is not a safe final write authority.
- [Input](#input) — Proof, preflight, snapshot, lock, and seed-state contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint.
- [Implementation](#implementation) — Guarded final recheck and one-artifact publication rules.
- [Tests](#tests) — Focused publication, stale-input, lock, and seed-state coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Atomic replacement, locking, and digest references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain publication.
- [Deferred](#deferred) — Related work outside this one-artifact boundary.

## Why

`plan_tool/roadmap_revision_publish.py:publish_revision_candidate` validates a local typed candidate immediately before writing, but it re-renders the artifact and has no way to confirm the exact receipt-analysis evidence or full snapshot that step 5 proved. A structural candidate must keep its source-preserving text and must not reach replacement after any proof input changes, so this step adds a narrow final boundary that rereads the complete binding under the participating-writer guard.

## Input

- **Step 2 exact-evidence context:** Step 2 supplies the explicitly named receipt and analysis finals, their raw digests, the selected stage and feedback slice, and the complete `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` binding.

- **Step 5 proof:** Step 5 supplies the successful candidate proof, including the exact candidate text, selected-stage identity, evidence facts, and full snapshot binding that final publication must reproduce.

- **Current-state recheck:** `plan_tool/roadmap_impact_snapshot.py:recheck_roadmap_impact_snapshot` verifies a snapshot’s source, brief, artifact, and gate binding, but does not bind immutable evidence finals. Reuse step 2’s exact-pair preflight and its no-enumeration exact-final reader for the complete final comparison.

- **Writer and seed contracts:** `plan_tool/roadmap_revision_publish.py:require_roadmap_writer_token`, `roadmap_writer_guard`, and `preinvalidate_roadmap_seeds` define the participating-writer lease and conservative invalidation behavior.

- **Replacement primitive:** `plan_tool/fileio.py` needs a binary same-directory atomic replacement helper for one canonical artifact; the existing text helper is not safe for cross-platform raw-byte preservation.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/fileio.py` — Add a binary atomic replacement helper that writes supplied bytes unchanged and preserves the existing sibling-tempfile cleanup semantics.
  - `plan_tool/roadmap_revision_publish.py` — Add a proof-bound structural publication boundary, final exact-evidence and snapshot comparison, and matched-artifact-only replacement while preserving existing local publication, lock, and seed helpers.
  - `tests/test_fileio.py` — Add focused binary-write coverage, including LF preservation under a Windows newline simulation.
  - `tests/test_roadmap_revision_publish.py` — Add focused coverage for final rechecks, exact-byte replacement, writer-lease scope, seed-state preservation, and lock-byte initialization.

## Implementation

- **Foundational logic:** Recheck every proof input under one active writer lease, then atomically replace only the artifact that the recheck and proof both select.

- **Add a separate structural publication boundary.** Accept a successful step-5 proof and the resolved inputs needed to repeat step 2’s exact-pair preflight. Keep `plan_tool/roadmap_revision_publish.py:publish_revision_candidate` unchanged for `plan_tool/roadmap_revision_run.py:run_local_feedback_revision`; its render-and-gate behavior is not safe for source-preserving structural candidates.

- **Require the caller’s active writer token first.** Validate the supplied token through `plan_tool/roadmap_revision_publish.py:require_roadmap_writer_token`. Do not acquire a second lease or release the caller’s lease during the final comparison and replacement.

- **Rebuild the complete current binding while guarded.** Re-run step 2’s
  exact-pair preflight using the proof’s explicit receipt and analysis final
  names. That recheck must use the same no-enumeration exact-final reader as
  initial preflight: unrelated evidence records, including unreadable ones,
  cannot affect the selected pair. Compare the fresh result against every
  proof-bound fact: both final names, both raw evidence digests, and every
  member of the complete `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot`
  binding.

- **Refuse every stale proof input before writing.** A changed selected or unselected artifact, recorded source, recorded brief, receipt final, analysis final, stage order, or current gate result must produce a typed stale-publication failure. Do not reduce this check to the selected artifact digest or reuse a proof after a failed recheck.

- **Bind the target to the proof and fresh preflight.** Require the proof’s selected stage and the rechecked selected stage to describe the same artifact. Derive the replacement path from that matched stage; do not accept a caller-supplied output path, another stage, or another candidate as an override.

- **Write the proved bytes without reshaping them.** Encode the proof’s exact candidate text once as UTF-8, then pass those bytes to the new binary atomic replacement helper. The helper must write bytes through a binary sibling tempfile so platform text newline handling cannot alter LF or any other approved candidate byte. Do not parse, render, rerun generic revision gates, call `publish_revision_candidate`, or pass through `atomic_write_text` on this path; those operations can change bytes outside step 4’s approved spans.

- **Keep replacement single-file and atomic.** Replace only the matched canonical artifact after the complete comparison succeeds. Do not write evidence, another roadmap artifact, a journal, or recovery state from this boundary.

- **Preserve conservative seed behavior.** Leave `preinvalidate_roadmap_seeds` as the runner-owned pre-publication action. The structural publisher must neither restore nor otherwise alter seed state; a final-snapshot refusal or write failure leaves canonical artifact bytes unchanged and may retain the existing invalidated seed state.

- **Preserve lock-byte behavior.** Keep `plan_tool/roadmap_revision_publish.py:_acquire_writer_lock` responsible for initializing an empty Windows lock file before byte-range locking. Keep `roadmap_reader_guard` read-only with respect to lock bytes.

## Tests

### Tests for this step

- `test_structural_publication_requires_the_matching_active_writer_token` — Refuse an inactive, foreign, or reader token before a final preflight or replacement runs.

- `test_structural_publication_rechecks_exact_evidence_and_complete_snapshot_under_one_lease` — Assert that the final exact-pair recheck and replacement occur while the caller’s writer lease remains active.

- `test_structural_publication_exact_recheck_ignores_unrelated_evidence_finals` —
  Asserts that an unrelated unreadable or malformed final cannot reject the
  selected pair at the final guarded boundary.

- `test_structural_publication_refuses_each_changed_proof_input_before_replacement` — Cover changes to the recorded source, brief, selected artifact, unselected artifact, receipt final, analysis final, and snapshot stage binding.

- `test_structural_publication_refuses_current_gate_failure_before_replacement` — Assert that a changed current gate result prevents replacement even when persisted proof bytes still match.

- `test_structural_publication_writes_exact_proved_bytes_to_only_the_matched_artifact` — Assert that the selected artifact receives the proof text unchanged and every sibling artifact retains its prior bytes.

- `test_atomic_write_bytes_preserves_lf_payload_on_every_platform` — Asserts the binary helper preserves an LF-containing UTF-8 payload under a Windows newline simulation.

- `test_structural_publication_does_not_use_generic_candidate_rendering` — Assert that a structural candidate is not passed through `publish_revision_candidate` or a stage renderer before replacement.

- `test_structural_publication_keeps_invalidated_seed_state_after_refusal` — Assert that a stale final recheck leaves the canonical artifact unchanged and does not restore invalidated seed entries.

- `test_structural_publication_does_not_restore_invalidated_seed_state_after_success` — Assert that successful replacement also leaves the existing invalidation result intact.

- `test_writer_guard_initializes_one_msvcrt_lock_byte_before_locking` — Assert that the Windows writer-lock path expands an empty lock file before requesting its byte-range lock.

- `test_reader_guard_preserves_lock_bytes_and_never_yields_a_writer_token` — Keep the existing reader-lock regression coverage so the structural path does not weaken lock-file or writer-token rules.

Green-before-done gate: `uv run pytest tests/test_fileio.py tests/test_roadmap_revision_publish.py -q` passes.

## Acceptance criteria

- A structural publication boundary accepts only a successful step-5 proof and a matching active `RoadmapWriterToken`.

- Final publication rereads the exact receipt and analysis finals and compares their raw digests plus every complete snapshot-binding member to the proof before replacement.

- Both the initial and final exact-pair preflights read only the two named
  immutable finals; an unrelated evidence-record failure cannot turn a proved
  selected pair stale.

- A changed proof input or current gate failure raises a typed refusal before any canonical artifact is replaced.

- Successful structural publication atomically writes the proof’s exact UTF-8 candidate bytes through the binary helper to only the rechecked selected artifact.

- `publish_revision_candidate` retains its current local-revision contract and structural publication does not use it.

- Seed invalidation remains unchanged by final-snapshot refusal, write failure, and successful structural publication.

- Writer locking continues to initialize the Windows lock byte, while reader locking preserves existing lock bytes and never yields writer authority.

- `uv run pytest tests/test_fileio.py tests/test_roadmap_revision_publish.py -q` passes.

## References

- [Python `os.replace`](https://docs.python.org/3.13/library/os.html#os.replace) — Confirm the atomic replacement semantics used by the binary helper in `plan_tool/fileio.py`.

- [Python `fcntl.flock`](https://docs.python.org/3.13/library/fcntl.html#fcntl.flock) — Confirm the advisory locking behavior behind the participating-writer guard.

- [Python `hashlib` — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html#hashlib.file_digest) — Use deterministic raw-byte digests when comparing immutable evidence and snapshot inputs.

## Applicable guardrails

- **The plan’s intent, one-artifact publication boundary:** Derive and replace only the selected artifact path; do not add a second canonical write.

- **The plan’s step intent, proof-freshness boundary:** Require a successful proof and a complete final comparison before the atomic replacement boundary.

- **The plan’s `## Architecture`, continuous-guard boundary:** Keep the participating-writer lease active through evidence reload, snapshot comparison, and replacement without claiming protection from an external manual-write race.

- **The plan’s `## Out of scope`, transaction and schema boundary:** Do not add recovery, broader authoring, schema, or revision-mode behavior to this publisher.

## Deferred

- **Shared final-recheck abstraction** — Leave `plan_tool/roadmap_impact_run.py:_run_while_guarded` and `plan_tool/roadmap_impact_snapshot.py:recheck_roadmap_impact_snapshot` unchanged because impact-analysis publication does not carry this proof and exact-evidence contract; route any wider consolidation through reconcile work.

- **Candidate semantic-impact classification and broader transaction behavior** (`74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`) — The plan’s `## Out of scope` keeps this outside the one-artifact publisher; BACKLOG #289 remains the follow-up path for a demonstrated semantic-classification need.
