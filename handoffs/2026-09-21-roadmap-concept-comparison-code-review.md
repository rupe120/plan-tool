# `roadmap-concept-comparison` — post-run `/code-review` convergence

Post-run code-review loop for the `roadmap-concept-comparison` plan (steps 1–7 done). Each round used 8 parallel finder angles, each finding re-verified against source.

| Field | Value |
| --- | --- |
| Scope | `e77ebfa5..HEAD` (`roadmap_diff.py`, `roadmap_compare*.py`, `--compare` CLI wiring, refactored `roadmap_candidate.py`/`roadmap_versions.py`) |
| Checks | last full suite (round 10): 13230 passed, 189 skipped, 0 failed; round 11 changed no `.py` file, no suite run |
| Reviewer | the driving `/code-review high` loop, 11 rounds |
| Round commits | R1 `45fc73bf`, R2 `87656cd6`, R3 `b92902ad`, R4 `dcb5dd6f`, R5 `683e28dd`, R6 `30ba9213`, R7 `6a69f7f9`, R8 `130bbbca` (ledger only), R9 `96579a02`, R10 `9d586a34`, R11 `92c96ef3`; stop record `3c0b4ead` |
| Disposition | stopped by the owner after 11 rounds; not converged (see Stopped) |

## Settled decisions (from the dispositions below)

*Compression note (2026-09-29): this ledger had no original settled-decisions list; the list below was assembled from its own declined and refuted findings.*

- Dead-import claim on `artifact_row_diffs as _artifact_row_diffs` is a false positive: `tests/test_roadmap_candidate.py:884` uses it through the module namespace (rounds 1, 3, 6, 11).
- `raw_evidence_identity` is a do-not-merge look-alike of the canonical-JSON identity helpers (`stored_version_identity_preimage`, `_content_identity`, `checkpoint.compute_input_hash`): it hashes raw patch text byte-exact (rounds 3, 5, 11).
- The CLI handler narrows internal errors to one clean usage error; reversing it toward crash-loud is declined (rounds 3, 6).
- `_RELATION_FIELD_NAMES` drift is closed by test guards, not a structural merge.
- Other do-not-merge look-alikes: `_ordered_raw_evidence`; `_build_snapshot` versus `RoadmapVersionContent.__post_init__`; `build_roadmap_diff` digests versus `sha256_digests`.

## Findings

Round 1 (`45fc73bf`)
- **R1-1 — `load_resolved_stored_version` rewraps `RoadmapVersionError`** (correctness, high): every specific corruption message became "invalid id", incl. a corrupted accepted-head pointer. **Disposition:** fixed `45fc73bf` — `except RoadmapVersionError: raise` first; `test_load_accepted_version_surfaces_specific_corruption_diagnostic_not_generic_invalid_id`.
- **R1-2 — `entity_id` nulled in displayed field** (correctness, medium): stripping applied to display, not just equality. **Disposition:** fixed `45fc73bf` — `_stripped_for_comparison` used only in the `!=` check; `test_changed_card_keeps_the_real_entity_id_when_fields_changes_for_another_reason`.
- **R1-3 — renderer exceptions bypass the CLI error contract** (correctness, medium, unreachable today). **Disposition:** fixed `45fc73bf` — render moved inside the `try`, except widened; `test_comparison_renderer_invariant_failure_is_a_clean_usage_error`.
- **R1-4 — misleading refusal for a companion option without `--compare`** (correctness, medium). **Disposition:** fixed `45fc73bf` — explicit "require --compare" message; `test_comparison_companion_option_without_compare_names_the_missing_flag`.
- **R1-5 — commit `db0b8adf` carried a stray attribution trailer** (process). **Disposition:** fixed — `db0b8adf` amended unpushed before sharing; further concern declined by owner direction.
- **R1-6 — comparison modules import `plan_tool.roadmap` (`RoadmapStage`/`STAGES`), contradicting the documented read-only layering** (architecture, medium). **Disposition:** tracked #406 — a leaf-module extraction broke 18 of 30 `tests/test_roadmap_candidate.py` tests (Pydantic v2 forward-reference error on `GateCleanCandidate`); a direct `Violation` import did not fix it; extraction fully reverted. Doc claim corrected in R4-8.
- **R1-7 — `_json_value` likely duplicates `_wire_value` and `_canonical_value`** (reuse, low–medium). **Disposition:** tracked #407 — identity not machine-established (`tests/test_duplication.py` does not flag it; BACKLOG #79 showed "identical" claims are unreliable).
- **R1-8 — dead imports in `roadmap_candidate.py`** (cleanup, low). **Disposition:** fixed `45fc73bf` — six removed; the seventh (`_artifact_row_diffs`) restored because a test uses it.
- **R1-9 — `_capture_patches` spawns Git for identical artifacts** (efficiency, low). **Disposition:** tracked #408 — Git is the deliberate identity authority; at most 4 spawns.
- **R1-10 — `_RELATION_FIELD_NAMES` duplicates `_row_relation_specs`** (drift, medium). **Disposition:** fixed `45fc73bf` differently — `test_relation_field_names_matches_declared_relation_specs` instead of a structural merge.

Round 2 (`87656cd6`)
- **R2-1 — `_stripped_for_comparison` ignored `FieldType`** (correctness, medium): non-REFERENCE `entity_id` changes became invisible. **Disposition:** fixed `87656cd6` — strip only for `FieldType.REFERENCE`; `test_non_reference_field_entity_id_change_still_produces_a_card`.
- **R2-2 — `_json_value` duplication (recurrence).** **Disposition:** tracked #407.
- **R2-3 — error boundaries omit `RoadmapArtifactError`** (consistency, medium, masked). **Disposition:** fixed `87656cd6` — added to both except tuples.
- **R2-4 — `build_roadmap_diff` positional bytes versus keyed artifacts** (latent, low). **Disposition:** tracked #409 — one call site in the fragile candidate pipeline.
- **R2-5 — R1-10 guard missed `EntityRow`'s type-conditional rule.** **Disposition:** fixed `87656cd6` — `test_entity_field_stripping_matches_relation_specs_exactly_by_field_type`; exposing the mapping from `roadmap_relations.py` declined as disproportionate.
- **R2-6 — `_build_snapshot` re-implements the digest tuple** (reuse, low). **Disposition:** fixed `87656cd6` — `sha256_digests` added and used at three sites.
- **R2-7 — dead render and `Candidate*Diff` aliases** (cleanup, low). **Disposition:** fixed `87656cd6` — removed; `CandidatePredecessorDiff` kept.
- **R2-8 — digest dicts rebuilt 8 times in `comparison_json_payload`** (efficiency, low). **Disposition:** fixed `87656cd6` — hoisted.
- **R2-9 — `_capture_patches` spawns Git (recurrence).** **Disposition:** tracked #408.
- **R2-10 — `_has_roadmap_comparison` inlines default handling** (style, low). **Disposition:** tracked #410 — the fix widens the shared `_option_occurrences`.

Round 3 (`b92902ad`)
- **R3-1 — `--compare` does not gate; a duplicate row id silently drops a row** (correctness, medium). **Disposition:** tracked #411 — a `check_duplicate_row_ids` pre-check looks feasible but needs `ArtifactEnvelope` construction understood.
- **R3-2 — widened except swallows internal-invariant bugs** (design trade-off, disputes R1-3). **Disposition:** declined — matches the feature's "one CLI contract" design; re-flipping is oscillation.
- **R3-3 — `ordered_stage_collections` re-implements `stage_row_collections`** (drift, medium). **Disposition:** fixed `b92902ad` — delegates to it; lost `TypeError` restored in R4-2.
- **R3-4 — `_ARTIFACT_PARSERS` duplicates `STAGES`** (drift, low–medium). **Disposition:** fixed `b92902ad` — derived from `STAGES`.
- **R3-5 — `_RELATION_FIELD_NAMES` (recurrence).** **Disposition:** refuted — parity tests pin the tables.
- **R3-6 — `raw_evidence_identity` versus canonical-JSON identity** (reuse, disputed). **Disposition:** declined — byte-exact patch text versus structured data.
- **R3-7 — O(n·m) `relation_occurrence_diffs`** (efficiency). **Disposition:** tracked #412 — measure first.
- **R3-8 — artifact bytes SHA-256'd up to 3×** (efficiency). **Disposition:** tracked #413 — KB-scale, negligible.
- **R3-9 — three "binds the fixed inventory" checks** (reuse, low). **Disposition:** fixed `b92902ad` in part — `_patch_by_artifact_key` merges the two same-shaped checks; `_ordered_raw_evidence` stays separate (different input, extra check).
- **R3-10 — dead import `_artifact_row_diffs`.** **Disposition:** refuted — `tests/test_roadmap_candidate.py:884`.
- Suite flake: `tests/test_roadmap_revision_publish.py::test_reader_guard_does_not_block_a_writer_for_a_different_roadmap` failed once under `-n auto` contention, passed alone and on re-run; unrelated.

Round 4 (`dcb5dd6f`)
- **R4-1 — `_stripped_for_comparison` omits the `entity_id is not None` half** (correctness, disputed). **Disposition:** refuted — reproduced live: change surfaces in `added_relations`; proposed fix is a no-op; `test_reference_field_entity_id_from_none_is_also_a_relation_only_change`.
- **R4-2 — `ordered_stage_collections` lost its `TypeError` guard.** **Disposition:** fixed `dcb5dd6f` — local `isinstance` guard restored.
- **R4-3 — `run_roadmap_comparison` except omits `TypeError`** (consistency, medium). **Disposition:** fixed `dcb5dd6f` — `test_bare_type_error_from_comparison_building_is_not_leaked_uncaught`.
- **R4-4 — `--comparison-output patch` builds an unused typed diff** (efficiency). **Disposition:** tracked #414 — measure first.
- **R4-5 — `_RELATION_FIELD_NAMES` (recurrence).** **Disposition:** refuted — guarded.
- **R4-6 — `_DISPLAY_KINDS` re-spells `roadmap_view.py` constants** (reuse, low). **Disposition:** fixed `dcb5dd6f`.
- **R4-7 — `_json_value` duplication (new evidence: key-handling divergence).** **Disposition:** tracked #407.
- **R4-8 — `docs/ARCHITECTURE.md` "does not import roadmap writers" claim false.** **Disposition:** fixed `dcb5dd6f` — reworded with pointer to #406.
- **R4-9 — `CandidatePredecessorDiff` permanent alias** (cleanup). **Disposition:** tracked #415 — about 18 sites in the fragile family.
- **R4-10 — inventory key tuple recomputed at 8 sites** (reuse, low). **Disposition:** fixed `dcb5dd6f` — `VERSION_ARTIFACT_KEYS` at 7 sites; the 8th (`roadmap_candidate_context.py`) done in R10-4.

Round 5 (`683e28dd`)
- **R5-1 — same-membership reorder yields a card with empty `changed_fields`** (completeness; `before`/`after` still show it). **Disposition:** tracked #417 — needs a design choice.
- **R5-2 — positional zip (recurrence).** **Disposition:** tracked #409 — `_verify_predecessor` is prior art.
- **R5-3 — local `TypeError` guard treats a symptom; gap is in `design_row_collections`.** **Disposition:** tracked #416 — local guard kept.
- **R5-4 — docstring a paragraph; guard unpinned** (style/coverage). **Disposition:** fixed `683e28dd` — trimmed, detail moved to `docs/ARCHITECTURE.md`; `test_ordered_stage_collections_refuses_an_unsupported_artifact_type`.
- **R5-5 — `_capture_patches` (recurrence).** **Disposition:** tracked #408.
- **R5-6 — `build_roadmap_diff` hand-rolled SHA-256; digest fields unread.** **Disposition:** declined for the reuse half (sequence helper, single value); tracked #418 for the unused fields (shared type).
- **R5-7 — `_stripped_for_comparison` docstring 16 lines.** **Disposition:** fixed `683e28dd`.
- **R5-8 — `raw_evidence_identity` versus `_content_identity`.** **Disposition:** declined — Settled decisions.
- **R5-9 — `_json_value` (recurrence; `_json_value` sorts keys, `_wire_value` does not).** **Disposition:** tracked #407.
- **R5-10 — unreachable `_has_roadmap_comparison(args)` predicate entry** (dead code, low). **Disposition:** fixed `683e28dd`.

Round 6 (`30ba9213`)
- **R6-1/R6-2 — duplicate-id drop; ordering reorder (recurrences).** **Disposition:** tracked #411, #417.
- **R6-3 — `_load_working_snapshot` has no concurrent-writer protection** (concurrency, narrow). **Disposition:** tracked #419 — cross-cutting, no locking primitive exists.
- **R6-4 — broad except may mask a renderer bug (third surfacing).** **Disposition:** declined — no new argument; see R3-2.
- **R6-5 — `_RELATION_FIELD_NAMES` (recurrence).** **Disposition:** refuted — guarded.
- **R6-6 — `_json_value` (recurrence).** **Disposition:** tracked #407.
- **R6-7 — `raw_evidence` built though the terminal renderer ignores it** (efficiency). **Disposition:** tracked #414.
- **R6-8 — `_capture_patch` discards Git `stderr`** (diagnosability, low–medium). **Disposition:** fixed `30ba9213` — exit code and stderr in the message; test extended.
- **R6-9 — dead import `_artifact_row_diffs` (third time).** **Disposition:** refuted — `tests/test_roadmap_candidate.py:884`.
- **R6-10 — `_stripped_for_comparison` docstring still 6 lines.** **Disposition:** fixed `30ba9213`.

Round 7 (`6a69f7f9`)
- **R7-1 — this ledger carried prose naming the authoring tooling, against the owner's global no-attribution rule** (process, high). **Disposition:** fixed `6a69f7f9` — rewritten in impersonal voice, keeping only the fact that a stray trailer was removed from one commit.
- **R7-2 — NUL-containing artifact diffed as binary, discarding the patch** (data integrity, medium). **Disposition:** fixed `6a69f7f9` — `--text` added; `test_embedded_nul_byte_still_produces_a_real_diff_not_a_binary_placeholder`.
- **R7-3/R7-4/R7-5 — #411, #417, #419 (recurrences).** **Disposition:** tracked #411, #417, #419.
- **R7-6 — parity-test parametrize list hand-written** (coverage). **Disposition:** fixed `6a69f7f9` — `test_relation_field_names_covers_every_stage_row_type`.

Round 8 (`130bbbca`, ledger only)
- **R8-1 — eight recurrences, no new information.** **Disposition:** tracked #411, #416, #409, #407, #418, #412, #408, #414.
- **R8-9 — `_build_snapshot` re-validates `RoadmapVersionContent.__post_init__` checks** (reuse). **Disposition:** declined — working snapshots have no `brief_bytes`.
- **R8-10 — three inventory checks (broader framing).** **Disposition:** declined — tuple length versus keyed membership differ.

Round 9 (`96579a02`)
- **R9-1 — seven recurrences.** **Disposition:** tracked #411, #417, #409, #407, #412, #408; `_RELATION_FIELD_NAMES` refuted (guarded).
- **R9-2 — ambient `core.autocrlf=true` hides a real byte difference** (data integrity, medium). **Disposition:** fixed `96579a02` — `-c core.autocrlf=false -c core.safecrlf=false`; `test_ambient_autocrlf_config_does_not_hide_a_real_byte_difference` (verified failing without the fix).
- **R9-9 — `_ordering_diffs` duplicates `artifact_row_diffs`' by-id diff** (reuse, low). **Disposition:** fixed `96579a02` — `_diff_by_id`; candidate suite verified.
- **R9-10 — `raw_evidence_identity` stored though derived** (simplification). **Disposition:** tracked #420 — low value; serialization risk.

Round 10 (`9d586a34`)
- **R10-1 — round 9's extraction left an unreachable `return tuple(diffs)` with an undefined name** (self-introduced). **Disposition:** fixed `9d586a34`; a lint sweep of touched files found nothing else (the `F821` in `tests/cli/test_roadmap_cmd.py` is from unrelated `b14bc2a9`).
- **R10-2 — CLI except omits `KeyError`** (defensive, low). **Disposition:** fixed `9d586a34`.
- **R10-3 — companion-mode rejection thinly tested (2 of about 9 groups).** **Disposition:** tracked #421.
- **R10-4 — `_verify_predecessor` is the un-swept sibling of R2/R4 consolidations** (reuse). **Disposition:** fixed `9d586a34` — shared helpers; 148 candidate tests verified.
- **R10-5/R10-6 — #418, #407 (recurrences).** **Disposition:** tracked #418, #407.

Round 11 (`92c96ef3`)
- **R11-1 — duplicate-id collapse in `_diff_by_id` (sharper reproduction).** **Disposition:** tracked #411 — folded in; one fix covers both callers.
- **R11-2 — `_option_occurrences` contract breaks for non-`None` defaults.** **Disposition:** tracked #410.
- **R11-3 — four recurrences (#409, #407, #408, `_RELATION_FIELD_NAMES`).** **Disposition:** tracked #409, #407, #408; last refuted (guarded).
- **R11-6 — `_card_for_row_diff` ordering carve-out is a name check** (latent). **Disposition:** tracked #422 — deliberately not built; only `OrderingEntry` has that shape.
- **R11-7 — `raw_evidence_identity` versus `checkpoint.compute_input_hash`.** **Disposition:** declined — Settled decisions.
- **R11-9 — dead import `_artifact_row_diffs` (fourth time).** **Disposition:** refuted — Settled decisions.
- **R11-10 — plan cites `BACKLOG.md` #402, deleted by this diff** (doc accuracy). **Disposition:** fixed `92c96ef3` — plan reference closed with a dated note, dead acceptance line deleted; 8 `plan-details/` files and one archived seed deliberately left (pre-date this scope).

Round 12 was launched and stopped at the owner's request before any findings.

## Out-of-range / recall-mode findings

_(none)_

## Stopped (2026-09-21, owner-directed — not a two-consecutive-low-yield exit)

The loop ended on the owner's instruction after 11 rounds. It did not reach the two-consecutive-low-yield bar and is not converged.

- **State:** 11 rounds, each committed separately (`45fc73bf` through `92c96ef3`); rounds 1–10 full-suite green (last line above). A mid-loop self-audit of about 35 fixes (intent-fit, smallest proof, altitude, sweep completeness) was clean apart from R10-1, closed the next round.
- **Trend:** toward low yield — round 8 had zero actionable items, rounds 10–11 were mostly recurrences (6 of 10 in round 11), later new items were lower severity. The later new items were data-integrity bugs in rounds 7 and 9, then documentation staleness and latent structural fragility in round 11; round 12 never ran.
- **17 items left in `BACKLOG.md` #406–#422**, none known-broken on a reachable path:
  - #406 layering import (extraction reverted, Pydantic break); #415 alias rename, #416 `design_row_collections` guard, #418 digest fields (shared candidate-family types); #419 concurrent-writer locking (repo-wide design).
  - #417 reorder summary and #422 ordering carve-out (deliberately not built for shapes the schema does not produce); #410 `_option_occurrences` contract; #411 duplicate-id drop (needs gate wiring).
  - #407 and #420 consolidation/simplification needing identity evidence; #409 positional zip; #421 test-authoring only.
  - #408, #412, #413, #414 unmeasured efficiency.
- **Reverted:** round 1's `RoadmapStage`/`STAGES` extraction (#406), history recorded there.
- **No known regression and no uncommitted state.**
