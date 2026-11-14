# Roadmap feedback and lifecycle

Feedback, approval, versioning, brief drift, comparison and the stack layer in the `roadmap` verb. Each section below is one change or route in this workstream, ordered by the date it was opened; new work in the workstream appends a section here instead of creating a file (`README.md` § "Naming").

| Section | Opened |
| --- | --- |
| [independent review of roadmap brief-source drift admission](#independent-review-of-roadmap-brief-source-drift-admission) | 2026-09-12 |
| [`roadmap-concept-comparison` — post-run `/code-review` convergence](#roadmap-concept-comparison--post-run-code-review-convergence) | 2026-09-21 |
| [Roadmap feedback revision and approval handoff](#roadmap-feedback-revision-and-approval-handoff) | 2026-09-22 |
| [Roadmap structural feedback approval — post-run review ledger](#roadmap-structural-feedback-approval--post-run-review-ledger) | 2026-09-23 |
| [Roadmap versioned feedback revision chain — post-run review ledger](#roadmap-versioned-feedback-revision-chain--post-run-review-ledger) | 2026-09-23 |
| [Roadmap stack-aware approval — post-run review ledger](#roadmap-stack-aware-approval--post-run-review-ledger) | 2026-09-24 |
| [Roadmap versioned-from-birth — code review ledger](#roadmap-versioned-from-birth--code-review-ledger) | 2026-10-06 |
| [Roadmap stack layer — code review ledger](#roadmap-stack-layer--code-review-ledger) | 2026-10-08 |
| [Roadmap stack propagation — code review ledger](#roadmap-stack-propagation--code-review-ledger) | 2026-10-08 |

## independent review of roadmap brief-source drift admission

*Opened 2026-09-12.*

### Status

| Field | Value |
| --- | --- |
| Review range | `3cca7b7d..baea1281` (roadmap brief-source drift admission) |
| Head | `baea1281` |
| Checks | Three post-run reconcile sweeps; ten `/code-review` passes at effort `high`; full suite `uv run pytest tests/ -q -n auto` — 12,247 passed, 189 skipped, 0 failed (round 6); round-10 scoped run 1255 passed, 188 skipped |
| Reviewer | Independent `/code-review` pass per round |
| Disposition | **Converged (2026-09-14).** Round 10 is clean; all 55 findings resolved; no round 11 |

This handoff is evidence of the closed loop, not part of the reviewed range. A
later change to the brief-admission surface needs a fresh review against its new
diff. It neither authorizes a workflow rerun nor changes the separate Integration scope
fence.

**Identifier provenance (2026-09-15).** This report uses the then-current `#365`
(route-local non-stage policy) and `#366` (stage-run rebind decision).
Repository integration later assigns `#365` and `#366` to unrelated work; use
the unnumbered closed route-local record and `#367` for the successor that
closes on 2026-09-16.

### Reviewed scope

Files: `plan_tool/roadmap_source.py`, `roadmap.py`, `run_log.py`,
`cli/roadmap_cmd.py`, `cli/__init__.py`, their tests, `DATA_CONTRACT.md`,
`ROADMAP_FORMAT.md`, README/RUNBOOK/USE_CASES, `docs/ARCHITECTURE.md`,
`docs/ROADMAP_WALKTHROUGH.md`, `docs/cli/roadmap.md`. Intent authority:
`docs/implementation-plans/2-roadmap-brief-source-drift.md` and its detail
bundle. Backlog edits in the range (including removal of a stale retired `#354` reference) are reviewed for stale identifiers only.

Commits: `6b8cf60b`, `75c1775c`, `f9802e39`, `d0f4cf77`; convergence `96b6eaa7`,
`ee10b346`, `93339259`, `edf5a91d`, `329dd9b9`, `39bea159`, `215894de`,
`7ae1518d`, `6130c3d8`, `cbb6c77c`, `4fe3643a`, `baea1281`. Sweeps 1 and 3 found
medium test/type gaps, fixed (`96b6eaa7`, `ee10b346`, `93339259`; no fourth
sweep, per the post-run stop rule); sweep 2 clean. Reports live under
`docs/implementation-plans/plan-details/roadmap-brief-source-drift/reports/`.

Known ambient failure, unchanged by this range: a pre-existing Pydantic
forward-reference (`GateCleanCandidate`) import-order defect fails four
`tests/test_roadmap_version_promotion.py` cases on one worker (18/18 in
isolation). It is suite instability, not evidence for or against this work.

### Settled decisions

1. `source.json` binds `brief_path` and the SHA-256 of decoded UTF-8 brief text.
   A path-only record is a distinguishable legacy state; malformed digest
   metadata fails closed.
2. A concrete directory at `source.json` refuses as malformed before brief read
   or artifact work. A symlink-to-directory is replaceable absence (the atomic
   writer replaces the link itself).
3. An unchanged digest follows ordinary behavior. Changed or legacy content
   without explicit acceptance refuses before artifact loading, backend
   invocation, artifact publication, or seed-state effects.
4. Explicit `--from-existing` at the same resolved recorded path accepts a
   legacy/changed baseline by atomically replacing only `source.json`; the
   invocation then follows its ordinary feedback-free or open-feedback route. The
   rebind owns no artifact or seed authority.
5. Every run reaching admission emits exactly one redacted
   `roadmap_source_admission` event from the closed vocabulary `initial`,
   `matched`, `accepted-rebind`, `refused-legacy`, `refused-changed`,
   `refused-malformed`. Refusals precede their preflight-failure event; no brief
   text is logged.
6. Docs distinguish baseline acceptance from semantic reconciliation and route
   semantic changes to owning-artifact feedback or a successor roadmap lineage.

Reaffirmed rulings are recorded at F1/F25/F30/F46, F7, F24, and F18/F26/F44; do not re-raise them, or the cleanup recurrences F8-F13, F16, F20-F22, without new failing behavior.

### Scope fence

- No framework-specific AI-DLC artifact names, stage slugs, or runtime paths.
- Do not review or mutate the Integration repository or its running workflow.
- No role-tagged multi-source intake, citation snapshots, inherited decisions,
  shared request framing, or coverage output (later roadmap-fit work).
- Do not run `reconcile-plan` against the completed implementation.
- Do not apply a finding during review; report it for a bounded correction loop.

### Findings

The source recorded no per-finding severity and no CONFIRMED/PLAUSIBLE tag
except where noted inline; none is invented. Ids are the source's global numbers.
Rounds: R1 F1-13, R2 F14-23, R3 F24-27, R4 F28-32, R5 F33, R6 F34, R7 F35-45,
R8 F46-53, R9 F54-55, R10 none.

- **F1 — admission gate bypassed by three entry points** (flagged highest,
  re-confirmed): `_capture_recorded_brief_digests` never compares the digest, so
  `--rewrite-structural`, `--impact-analysis`, `--enroll-version` act on a
  changed brief. **Disposition:** refuted — `_run_roadmap` owns stage-run
  admission; those routes have separate evidence/writer contracts and gating them
  widens the slice.
- **F2 — rebind unreported when the same run later fails** (flagged highest,
  re-confirmed). **Disposition:** fixed `d6ae319a` (invalid/exhausted printers)
  and `fac5abc0` (later preflight errors).
- **F3 — admission writer lacks closed-set validation.** **Disposition:** fixed
  `d6ae319a` — rejects values outside the six; test.
- **F4 — "different recorded path" refusal emits no admission event.**
  **Disposition:** refuted — rejected before any digest decision; its
  `brief_source` preflight event is deliberately narrower and the vocabulary has
  no different-path disposition.
- **F5 — rebind write has no `OSError` handling.** **Disposition:** fixed
  `d6ae319a` — named `RoadmapError` plus preflight failure, no false admission.
- **F6 — new stat calls outside the exception guard.** **Disposition:** fixed
  `d6ae319a` — `OSError` becomes `RoadmapSourceError`; injected-error test.
- **F7 — "same path" is path identity, not content identity** (case-insensitive
  volume). **Disposition:** refuted — exact resolved-path identity is the
  declared contract; case variants weaken the recorded-path boundary.
- **F8 — `_SHA256_DIGEST` duplicates the shared regex.** **Disposition:**
  declined — same accepted language, no demonstrated drift.
- **F9 — rebind write is speculative, collapses legacy/changed.**
  **Disposition:** refuted — replacing only `source.json` before ordinary
  processing is the specified order; `accepted-rebind` records completed
  acceptance, the stage route records its own outcome.
- **F10 — `.startswith("refused-")` stands in for the `Literal`.**
  **Disposition:** declined — closed vocabulary, runtime-guarded at emission.
- **F11 — symlink carve-out undocumented in spec.** **Disposition:** fixed
  `d6ae319a` — format and architecture docs distinguish concrete directory from
  replaceable symlink.
- **F12 — `_brief_reference(...)` recomputed at three sites.** **Disposition:**
  declined — immutable inputs, no observable divergence.
- **F13 — redundant `brief_digest` ternary.** **Disposition:** declined —
  `brief_path` validation exits for non-mapping JSON first; no raw-error path.
- **F14 — test broken by round 1's own repair** (reproduced; "concrete" wording
  in `test_source_admission_guidance_rejects_non_replaceable_record_target`).
  **Disposition:** fixed `60363a8b`.
- **F15 — `RoadmapArtifactError` downgraded to `RoadmapError` on the rebind
  path.** **Disposition:** fixed `60363a8b` — one helper preserves type and path;
  test.
- **F16 — `load_recorded_brief_path` dead code bypassing admission.**
  **Disposition:** declined — no admission authority (returns a path, accepts no
  digest, starts no stage, emits no lifecycle result).
- **F17 — `RoadmapSourceAdmission` unregistered in `PersistedDataclassContract`.**
  **Disposition:** fixed `60363a8b`.
- **F18 — three non-atomic stat calls (TOCTOU).** **Disposition:** declined —
  outside the single-writer boundary; external replacement cannot be made atomic
  by a preflight, and atomic replacement still refuses a concrete directory. Risk
  kept in `BUG_BACKLOG.md`'s external-replacement entry.
- **F19 — rebind-reannouncement handler copied at two sites.** **Disposition:**
  fixed `60363a8b` with F15.
- **F20 — `recorded_brief_source is not None` conjunct is dead.**
  **Disposition:** declined — documents the rebind precondition; a true
  invariant is safer than a cleanup-only change.
- **F21 — `record_brief_source` vs `recorded_brief_source` naming.**
  **Disposition:** declined — distinct, local, test-covered roles.
- **F22 — `_print_baseline_rebind` repeated at four printers.** **Disposition:**
  declined — explicit printers keep ordering local and cover every outcome.
- **F23 — `_write_brief_source` docstring outdated.** **Disposition:** fixed
  `60363a8b`.
- **F24 — gate blocks a `--from-stage` re-entry that never reads the brief**
  (reproduced, `invoker.calls == 0`). **Disposition:** refuted — the re-entry
  still reaches `_load_and_regate_below` and admits artifacts, the contract
  requires refusal before artifact loading, `_run_stage` passes the same `brief`
  to `_render_stage_prompt` for every stage, and `RUNBOOK.md` says every stage
  prompt is brief-grounded; a bypass contradicts the closed property.
- **F25 — bypass on three entry points (recurrence of F1).** **Disposition:**
  tracked `BACKLOG.md` #365 — scope refutation reaffirmed, no new evidence.
- **F26 — non-atomic stat calls (recurrence of F18).** **Disposition:** declined
  — reaffirmed single-writer boundary.
- **F27 — test helper trades a sort race for an mtime-tie race** (test-only).
  **Disposition:** fixed `98d157bd` — retains the exact log created per call;
  roadmap module 485 passed, 168 skipped.
- **F28 — non-artifact `RoadmapError` subclasses downgraded on rebind** (latent;
  affects rc 1 vs 2). **Disposition:** fixed `215894de` — context added and the
  original rethrown; `RoadmapEnvironmentalError` test.
- **F29 — first-write path has no `OSError` handling.** **Disposition:** fixed
  `215894de` — maps to `RoadmapEnvironmentalError`; test asserts `stopped` with
  no false preflight event.
- **F30 — bypass on three entry points (third recurrence; two finders converged
  unprompted).** **Disposition:** tracked `BACKLOG.md` #365 — route-specific
  tested policy for the three writers, no generic framework; supports its
  priority, does not widen this repair.
- **F31 — format tests assert bare-word substrings.** **Disposition:** fixed
  `215894de` — per-guide sets of complete contract phrases.
- **F32 — F27's fix misses the zero-or-multiple-new-logs case** (latent).
  **Disposition:** fixed `215894de` — clears the path, requires exactly one new
  log; zero- and two-log tests.
- **F33 — round 4's fix makes an exception its own `__cause__`** (confirmed
  live, `raise exc from exc`). **Disposition:** fixed `7ae1518d` — distinct
  same-type exception (keeps `.path`) chained from the original; tests assert a
  distinct `__cause__`.
- **F34 — `DATA_CONTRACT.md` lacks the rebind-write-failure carve-out**
  (documentation gap; behavior pinned by
  `tests/test_roadmap.py::test_rebind_write_failure_is_a_source_preflight_error`).
  **Disposition:** fixed `6130c3d8` — sentence added plus a documentation guard.
- **F35 — rebind-write `OSError` is plain `RoadmapError`, first-write is
  environmental.** **Disposition:** fixed `cbb6c77c` — both sites use
  `RoadmapEnvironmentalError`.
- **F36 — no signal separating deliberate acceptance from habitual same-path
  re-invocation** (design-level; a CI wrapper silently flips to
  `accepted-rebind`). **Disposition:** tracked `BACKLOG.md` #366 — the delivered
  contract defines same-path `--from-existing` as deliberate acceptance;
  changing the intent signal is a plan-level CLI decision.
- **F37 — runtime validation hand-duplicates the closed set.** **Disposition:**
  fixed `cbb6c77c` — derived from `RoadmapSourceAdmissionDisposition`.
- **F38 — `.startswith("refused-")` (recurrence of F10/F20).** **Disposition:**
  declined — reaffirmed.
- **F39 — `_rebind_preflight_error` assumes a single-arg constructor** (latent;
  no such subclass exists). **Disposition:** declined — future-only
  generalization.
- **F40 — digest regex rejects uppercase hex.** **Disposition:** fixed
  `cbb6c77c` — contract states lowercase (writer's `hexdigest()`); test rejects
  uppercase as noncanonical.
- **F41 — SHA-256 regex duplicates two validators (recurrence of F8, citing
  F40).** **Disposition:** declined — F40 shows a lowercase contract, not
  divergence; the validators cover distinct source-record and evidence
  identities.
- **F42 — rebind-preflight try/except blocks still duplicated (partial
  recurrence of F19).** **Disposition:** declined — distinct checks and phase
  labels; construction already shared.
- **F43 — dead `recorded_brief_source is not None` conjunct (recurrence of
  F20).** **Disposition:** declined — reaffirmed.
- **F44 — three stat calls (third raise; F18/F26).** **Disposition:** declined —
  same boundary; a syscall-count rewrite does not repair it.
- **F45 — undated "Closed" arc entry in `backlog-arc-roadmap.md`.**
  **Disposition:** fixed `cbb6c77c` — dated `Closed (2026-09-12)`; guard pins
  the route and ordered #365/#366 follow-up.
- **F46 — bypass on three entry points (fourth recurrence; F1/F25/F30).**
  **Disposition:** tracked `BACKLOG.md` #365 — reaffirmed, no new evidence.
- **F47 — baseline-rebind disclosure lost on a later-stage rendering failure**
  (new, confirmed by trace, low likelihood). **Disposition:** fixed `4fe3643a` —
  acceptance context wraps any later escaping `RoadmapError`/
  `RoadmapArtifactError` in stage dispatch, keeping type and cause; sweep covered
  `_rebind_preflight_error` (renamed), every `baseline_rebound` branch, both stage
  callers and both prompt renderers; regression added.
- **F48 — `BACKLOG.md` router claims a paired `BUG_BACKLOG.md` brief-drift entry
  that no longer exists** (bump `#362–#364` to `#362–#365` left the claim
  unswept; entry replaced in `25e4e7e0`). **Disposition:** fixed `4fe3643a` —
  router names only the structured-upstream group; sweep found this sole claim.
- **F49 — SHA-256 regex duplication (third raise; F8/F41).** **Disposition:**
  declined — a broader count shows no divergence.
- **F50 — `load_recorded_brief_path` dead (second raise; F16).** **Disposition:**
  declined — no admission authority, no production caller.
- **F51 — redundant ternary (second raise; F13).** **Disposition:** declined —
  same control-flow proof.
- **F52 — `.startswith("refused-")` (third raise).** **Disposition:** declined —
  no failed control-flow case.
- **F53 — dead conjunct (third raise).** **Disposition:** declined —
  cleanup-only.
- **F54 — F47's test covers only the fresh-stage path** (new). **Disposition:**
  fixed `baea1281` — open-feedback regression forces
  `_render_stage_feedback_prompt` to fail after a changed baseline and proves
  cause, disclosure and persisted digest.
- **F55 — arc-router line omits #366 from its enumeration** (`#328, #242, #208`
  plus group `#362-#365`; sibling of F48). **Disposition:** fixed `baea1281` —
  #366 listed separately; sweep covered the router, arc assignment and route step
  8; a format regression pins the enumeration.

### Out-of-range / recall-mode findings

_(none)_ — every finding lies within the reviewed diff or its cited docs.
Pre-existing test pollution (`TestMaterializeMode`,
`TestKeyboardInterruptRunEndPairing`, one candidate-lifecycle test), confirmed on
base `3cca7b7d`, was deliberately not reported.

### Convergence status

**Converged.** Round 9 (two low-severity findings, fixed in `baea1281`) and
round 10 (clean, zero findings; recurrences F1/F25/F30/F46, F24, F16/F50
re-verified, not re-reported) are two consecutive low-yield/clean rounds, and
round 10 is the completed independent review of `3cca7b7d..baea1281` that round
9 required. Finding counts per round: 13, 10, 4, 5, 1, 1, 11, 8, 2, 0.
Recurrences dominated rounds 7-8 (the spin signal); the genuinely new items were
bounded and fixed. No self-seeded majority was recorded.

Open follow-ups: `BACKLOG.md` #365 (F25, F30, F46) and #366 (F36), renumbered per
the provenance note above. No `pending` findings. **The loop stops here.** A
future change to `roadmap.py`, `roadmap_source.py`, or the brief-admission
surface opens a fresh review rather than resuming this ledger.

## `roadmap-concept-comparison` — post-run `/code-review` convergence

*Opened 2026-09-21.*

Post-run code-review loop for the `roadmap-concept-comparison` plan (steps 1–7 done). Each round used 8 parallel finder angles, each finding re-verified against source.

| Field | Value |
| --- | --- |
| Scope | `e77ebfa5..HEAD` (`roadmap_diff.py`, `roadmap_compare*.py`, `--compare` CLI wiring, refactored `roadmap_candidate.py`/`roadmap_versions.py`) |
| Checks | last full suite (round 10): 13230 passed, 189 skipped, 0 failed; round 11 changed no `.py` file, no suite run |
| Reviewer | the driving `/code-review high` loop, 11 rounds |
| Round commits | R1 `45fc73bf`, R2 `87656cd6`, R3 `b92902ad`, R4 `dcb5dd6f`, R5 `683e28dd`, R6 `30ba9213`, R7 `6a69f7f9`, R8 `130bbbca` (ledger only), R9 `96579a02`, R10 `9d586a34`, R11 `92c96ef3`; stop record `3c0b4ead` |
| Disposition | stopped by the owner after 11 rounds; not converged (see Stopped) |

### Settled decisions (from the dispositions below)

*Compression note (added 2026-11-13; the ledger was compressed 2026-09-29): this ledger had no original settled-decisions list; the list below was assembled from its own declined and refuted findings.*

- Dead-import claim on `artifact_row_diffs as _artifact_row_diffs` is a false positive: `tests/test_roadmap_candidate.py:884` uses it through the module namespace (rounds 1, 3, 6, 11).
- `raw_evidence_identity` is a do-not-merge look-alike of the canonical-JSON identity helpers (`stored_version_identity_preimage`, `_content_identity`, `checkpoint.compute_input_hash`): it hashes raw patch text byte-exact (rounds 3, 5, 11).
- The CLI handler narrows internal errors to one clean usage error; reversing it toward crash-loud is declined (rounds 3, 6).
- `_RELATION_FIELD_NAMES` drift is closed by test guards, not a structural merge.
- Other do-not-merge look-alikes: `_ordered_raw_evidence`; `_build_snapshot` versus `RoadmapVersionContent.__post_init__`; `build_roadmap_diff` digests versus `sha256_digests`.

### Findings

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

### Out-of-range / recall-mode findings

_(none)_

### Stopped (2026-09-21, owner-directed — not a two-consecutive-low-yield exit)

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

## Roadmap feedback revision and approval handoff

*Opened 2026-09-22.*

### Purpose

Record the completed roadmap feedback revision and structural-approval work. This
handoff preserves the implementation boundary and any separate follow-up; it
does not assign a new plan.

### Settled direction

Roadmap feedback revisions use a commit-like immutable history. Each feedback update proposes a successor from the accepted head, review binds exact candidate bytes, promotion advances only the accepted-head selector, and the next update starts from the promoted successor. Live top-level roadmap files are not a mutable working tree for pending feedback.

The structural approval gate now uses that history. Users submit one ordinary
feedback type. Valid typed operations determine whether the bounded or
structural candidate path applies; users never pre-classify feedback as
structural. Approval binds one reviewed top candidate and covers every
unpromoted candidate beneath it, edit creates a replacement for a fresh
decision, rejection releases only the active candidate, and promotion alone
advances the accepted head.

### Completion record

The revision-history plan and the Roadmap Structural Feedback Approval plan are
complete. The latter documents and implements one ordinary feedback intake,
validated operation routing, exact structural approval, promotion-only
publication, failure preservation, enrolled seed-state effects, and
accepted-version predecessors for later feedback revisions. Its documentation
and focused contract tests close BACKLOG #423.

The detail-grounded audit is clean at 7/7 detail coverage
(`20260923-220408-completeness.md`). Three complete post-run
`reconcile-code --all` sweeps cover all six code steps; step 7 is non-code.
Four independent post-run `/code-review` passes (`high`, headless) found three
routes by which structural content could reach the accepted head without a
structural decision, plus test and documentation gaps; each is fixed and pinned.
The answered route refuses a structural initial candidate and a structural
replacement, and promotion refuses an answered seal whose initial candidate is
structural. The full suite is green (13,730 passed, 190 skipped). The
loop closed on 2026-09-24 by owner decision on executed evidence — a randomized
state-machine search of 51,000 transitions with a route-independent oracle found
no violation — short of the two-consecutive-clean-pass rule. The findings,
dispositions, and convergence status are in the review record below.

The property those guards protect — structural content reaches the accepted
head, or changes enrolled seed state, only through a structural approval — holds
for stacked candidates too. The `roadmap-stack-aware-approval` plan (2026-09-24)
carries it: a new `--propose-candidate` batch stacks under a structural
candidate, and an approval covers the whole unpromoted stack in two invocations,
the second bound to a digest of the stack the first printed.

The plans remained sequential: approval consumes the immutable candidate,
review-seal, promotion, publication-journal, and accepted-head contracts from
revision history. Separate selector-shaped escalation, settlement, analysis,
and exact-pair rewrite routes remain outside ordinary proposal approval.

### Current artifacts

- Revision-history plan: `docs/implementation-plans/archive/2-roadmap-versioned-feedback-revision-chain.md` (`completed`). Its seed was consumed by `create`; the final generation is archived at `plan-seeds/archive/roadmap-versioned-feedback-revision-chain.replaced.2.md`.
- Revision-history review record: `roadmap-feedback.md` § "Roadmap versioned feedback revision chain — post-run review ledger".
- Revision-history pull request: `https://github.com/rupe120/plan-tool/pull/18`, squash-merged 2026-09-23.
- Structural-approval plan: `docs/implementation-plans/archive/2-roadmap-structural-feedback-approval.md`.
- Structural-approval review record: `roadmap-feedback.md` § "Roadmap structural feedback approval — post-run review ledger".
- Stack-aware approval plan: `docs/implementation-plans/archive/2-roadmap-stack-aware-approval.md`. It extends the structural-approval lifecycle to the whole unpromoted stack.
- Reconstruction evidence: `<integration-consumer-root>/.tmp/plan-tool-423-structural-roadmap-feedback-revision-reconstruction.md`.

The structural-approval plan completes the approval work; do not treat its seed
or this handoff as an active pickup instruction.

### Reuse boundary

The completed approval plan reuses the immutable candidate store,
`AcceptedRoadmapHead`, candidate review bindings, exact review seal, promotion
writer, publication journal, checkpoint/recovery behavior, feedback-state
handling, and seed invalidation. It introduces no second version chain,
candidate store, accepted-head writer, or transaction system.

### Remaining boundary

The lifecycle does not add workflow authoring, automatic approval, feedback
grouping, multi-user approval, or a general transaction system. Any work on
those capabilities requires a separate decision and plan.

## Roadmap structural feedback approval — post-run review ledger

*Opened 2026-09-23.*

> **2026-09-24:** the interim refusal of a `--propose-candidate` batch under a structural candidate (`ae3fb0bc`) was superseded by `roadmap-stack-aware-approval`. Passes 2–4 below record that refusal as it stood.

### Summary

| Field | Value |
| --- | --- |
| Plan | `roadmap-structural-feedback-approval` (`docs/implementation-plans/archive/2-roadmap-structural-feedback-approval.md`), 7 steps (6 code, step 7 non-code), all green |
| Branch | `codex/roadmap-structural-approval-handoff` (base `main` at `30484873`, PR #18 merged) |
| Run head (all steps green) | `471aa057` |
| Checks run | Detail-grounded `completeness-audit --iterate` clean at 7/7 detail coverage (`20260923-220408-completeness.md`); three complete `reconcile-code --all` sweeps over the six code steps (commits `6fa71bfa`, `e15ac3e1`, `d1d2921a`); final full suite green at `75664e74` (13,730 passed, 190 skipped; log `.tmp/roadmap-structural-approval-review.p4-fixes.pytest.log`) |
| `/code-review` | Pass 1 (`high`, `eb68ba19..d1d2921a`): 8 findings (7 reviewed, P1.8 found during P1.1 class enumeration), 2 high. Pass 2 (`high`, `d1d2921a..65802426`): 3 findings, 1 high. Pass 3 (`high`, `65802426..4561ff6e`): logic and coverage clean, 4 low documentation findings. Pass 4 (`high`, `65802426..b3685c47`): no correctness defect after 51,000 executed transitions, 1 medium coverage and 2 low documentation findings. All findings dispositioned. |
| Current disposition | Closed by owner decision (2026-09-24), not by the two-consecutive-pass stopping rule: the strict count against the latest logic commit `ae3fb0bc` is one (pass 3), because pass 4 returned a medium finding. See § "Convergence status". The stack direction shipped as `roadmap-stack-aware-approval`; wider run-log coverage stays open (§ "Open owner directions"). |

### Settled decisions (hand these to every reviewer)

From the plan, BACKLOG #423's closure, and the revision-approval handoff. A finding that proposes the opposite is
invalid, not deferrable.

- **One intake, no user-chosen type.** Validated typed operations select the presentation-only or structural route.
- **Approval binds the top candidate and covers its whole stack.** `approve` is two invocations: the first prints
  every unpromoted hop, the cumulative diff, and a digest and writes nothing; the second, with
  `--confirm-stack-digest`, seals the top candidate only when the recomputed digest matches. `edit` creates an
  unsealed replacement; `reject` releases the active candidate and drops every unpromoted hop; promotion alone
  advances `AcceptedRoadmapHead`.
- **Reuse, do not duplicate** the candidate store, review seal, promotion writer, publication journal,
  checkpoint/recovery, feedback-state and seed-invalidation owners. No second chain, store, head writer, or
  transaction system.
- **Fence.** No workflow authoring, automatic approval, feedback grouping, multi-user approval, or general
  transaction system. Selector-shaped escalation, settlement, analysis, and exact-pair rewrite routes stay outside
  ordinary proposal approval; structural operations outside current stage authority stay deferred.
- **Legacy batch evidence.** Route-less evidence written before this plan is readable and ineligible for every
  structural decision; checks key on a stored STRUCTURAL route, never on absence.
- **Answered chain.** `--review-candidate` / `--answer-question` / `--promote-review-seal` is the nonstructural
  route; a candidate whose stack carries a structural hop is refused there and named `--decide-candidate`
  (`bf3c7fda`); a replacement whose own computed classification is structural is refused before storage
  (`41a1ae44`). Rejection stays available on both routes. Answered replacements stored before this plan keep
  their pre-plan behavior (live legacy contract).
- **Stacks are allowed and approved as a whole.** A `--propose-candidate` batch takes the active candidate as its
  source. A stack is structural iff any hop above the recorded root stores a STRUCTURAL route (derived at use, no
  persisted field; a hop with no stored route contributes nothing). Every guard asks that one derivation.
  Structural content reaches the head, or changes enrolled seed state, only through a confirmed structural
  approval of the whole unpromoted stack (`roadmap-stack-aware-approval`, 2026-09-24).
- **Run-log coverage.** Every model-calling candidate lifecycle command writes a run-log lifecycle under its own
  phase and mode (propose, question, replacement, and — since `85177a89` — structural edit); reviewer prose stays
  out of the log (owner direction, 2026-09-24). Decision commands are not covered; see § "Open owner directions".
- **Deliberately not** a semantic or quality check on candidate content, a second structural gate on the answered
  route, or a check needing a new persisted field without a consumer the finding breaks.
- **Documentation-only corrections** are tested for accuracy but do not reset the logic-convergence window.
- **Project rule edits** need architect-tier review in the PR; this loop does not edit rules.

### Findings

Ids: P1.x pass 1 (`eb68ba19..d1d2921a`), P2.x pass 2, P3.x pass 3, P4.x pass 4. Each pass was an independent
headless `high` review.

#### Pass 1

- **P1.1 — Answered route promotes a structural candidate** (high, correctness): only `--decide-candidate`
  consulted the stored route, so the answered chain advanced the head with no decision or seed invalidation.
  **Disposition:** fixed `bf3c7fda` — guards at `generate_candidate_question`, the shared admitted-initial loader,
  and the answered-seal branch of `_load_complete_sealed_candidate`; `reject_candidate_review` deliberately
  unguarded; tests in `tests/test_roadmap_candidate_review.py`, `tests/test_roadmap_version_promotion.py`.
- **P1.2 — Structural edit refusal and failure branches unpinned** (medium, coverage): deleting the
  non-structural-replacement check stayed green. **Disposition:** fixed `03bc3f49` — tests only, mutation-verified;
  the expansion-request branch is unreachable (`allow_expansion=False` raises first) and deliberately not pinned.
- **P1.3 — Prior candidate's lost eligibility unpinned on the decision surface** (medium, coverage).
  **Disposition:** fixed `03bc3f49` — tests only; the claim is partly refuted (the publication recheck
  `_require_active_structural_candidate` also refuses unsealed superseded candidates), but the loader is the sole
  guard for a sealed-then-superseded candidate (`approved-then-superseded-by-edit` cell). The edit-path loader
  mutant is equivalent by design.
- **P1.4 — Legacy route-less evidence pinned as ineligible for approve only** (low, coverage). **Disposition:**
  fixed `03bc3f49` (library) and `3722f7a6` (CLI) — tests only, mutation-verified.
- **P1.5 — CLI prints the full approval disclosure before eligibility is checked** (low, correctness).
  **Disposition:** fixed `3722f7a6` — the handler compares the id with `admission.candidate_version_id` before
  rendering; the library still re-checks, so the CLI check is presentation only. Deliberately not a new public
  eligibility function.
- **P1.6 — Structural edit has no run-log lifecycle and requires an argument it discards** (low, coverage /
  consistency). **Disposition:** fixed `85177a89` — declined at first (no criterion required a trail), reversed by
  the owner 2026-09-24 (comprehensive log coverage); phase `roadmap-candidate-structural-edit`, mode
  `candidate-structural-edit`, logged invoker, interrupt and terminal records, rejected reply kept in the
  parse-failure sidecar, reviewer text out of the log; six outcomes tested, mutation-verified.
- **P1.7 — Two claims wider than the code** (low, documentation): the `DATA_CONTRACT.md` retention sentence and the
  `--promote-review-seal` help. **Disposition:** fixed `bf3c7fda` — narrowed, `docs/cli/roadmap.md` regenerated
  (`tests/cli/test_cli_reference.py`).
- **P1.8 — Presentation-only candidate takes a structural replacement through the answered route** (high,
  correctness; class completion of P1.1, found during its enumeration): `_store_batch_replacement` never
  consulted the replacement's computed classification. **Disposition:** fixed `41a1ae44` — refusal reads that
  classification (no persisted field); regression test and mutation verified. Deliberately not: a persisted
  classification on replacements, or a promotion-side re-check of stored answered replacements. The selector-era
  `_store_replacement` stays outside the plan (BACKLOG #429).

#### Pass 2

- **P2.1 — Structural content reaches the head as ancestry of a stacked presentation-only candidate** (high,
  correctness): a batch sourced from an active structural C1 classifies presentation-only relative to C1 and the
  answered chain promotes it with C1's changes. **Disposition:** fixed `ae3fb0bc` — reproduced by probe first; the
  batch source in `roadmap_candidate_run.py` (the only producer of a descendant of an active candidate's content)
  refuses when the active candidate's stored route is STRUCTURAL, keyed on the value, after `no eligible work` and
  before the first model call. Owner-flagged reversible call narrowing the prerequisite plan's stacking rule;
  smaller than cumulative classification or a promotion-side ancestor refusal (which strands the chain). Refusal
  later superseded by `roadmap-stack-aware-approval`.
- **P2.2 — Legacy route-less carve-out pinned only on the decision side** (medium, coverage). **Disposition:**
  fixed `ffceb1e8` — test only; mutation executed (entry and promotion guards keyed on absence go red).
- **P2.3 — Retention sentence says prompts are not retained** (low, documentation): the capsule persists the
  model-facing payload. **Disposition:** fixed `19682e8f` — sentence corrected; batch block and answered-route
  refusal stated in `docs/how-to/roadmap.md`, `ROADMAP_FEEDBACK_FORMAT.md`, `docs/ARCHITECTURE.md`.

#### Pass 3 (logic and coverage clean against `ae3fb0bc`)

- **P3.1 — Ledger named the review tooling and tier** (low, documentation). **Disposition:** fixed (pass-3
  documentation commit; hash not recorded in the source) — four sites reworded.
- **P3.2 — "No raw model reply is retained" contradicted by the failure sidecar** (low, documentation).
  **Disposition:** fixed (pass-3 documentation commit; hash not recorded) — claim scoped to evidence and seals; the
  sidecar is named.
- **P3.3 — "approve, edit, or reject ends it" misstates edit** (low, documentation): an edit stores another
  structural candidate. **Disposition:** fixed (pass-3 documentation commit; hash not recorded) — approval with
  promotion or rejection ends the block; an edit continues it.
- **P3.4 — Ordering rationale rests on a re-entry return that cannot fire** (low, documentation): the batch receipt
  binds `source`, so the same-receipt return never matches while a candidate is active. **Disposition:** fixed
  (ledger text only); the never-firing branch is tracked as BACKLOG #430 (evidence-gated, may be no action).

#### Pass 4 (no correctness defect; 51,000 transitions, 0 violations)

- **P4.1 — States that keep the batch block pinned by no test** (medium, coverage): a guard narrowed to ignore an
  approved-unpromoted or edit-produced structural candidate kept 830 tests green. **Disposition:** fixed
  `68a3749f` — tests only; refusal test parametrized over initial, approved-not-promoted, and edit-produced
  states; each narrowed-guard mutant fails its own cell. The pass-3 triage had wrongly judged this redundant.
- **P4.2 — Seed-state member described as journaled for every promotion** (low, documentation). **Disposition:**
  fixed `75664e74` — `DATA_CONTRACT.md` and `docs/ARCHITECTURE.md` corrected.
- **P4.3 — Route-less batch evidence described as legacy only** (low, documentation): answered-review replacements
  also persist neither field. **Disposition:** fixed `75664e74` — paragraph corrected.

### Reconcile-code sweeps

Three complete `reconcile-code --all` sweeps over the six code steps ran before review (commits `6fa71bfa`,
`e15ac3e1`, `d1d2921a`). The source records no per-sweep finding triage beyond these commits.

### Out-of-range findings

_(none)_ — weighed and dropped: an unreachable `assert` in `_classify_validated_operations`; consolidation
candidates (belong in `BACKLOG.md` with machine-verified evidence); an edit reproducing an existing candidate is
refused as an identity collision (fails closed); pre-plan structural answered replacements and route-less
candidates (settled live legacy contract); a hand-edited stored route (outside the threat model); the same-receipt
return (P3.4, #430); a promotion-generation crash window (interrupted enrolled generations refuse recovery by
design).

### Open owner directions

**Whole-stack presentation and confirmed approval — shipped as `roadmap-stack-aware-approval` (decided
2026-09-24; do not reopen).** The interim batch refusal is gone; a structural approval covers everything built on
the approved candidate. Every approval or confirmation presents the entire unpromoted stack (supersedes the
last-hop-only disclosure weighed in passes 3 and 4). Approve is confirmed in a separate invocation with a
stateless stack digest. There is deliberately no read-only show command: an unconfirmed approve prints the stack
and writes nothing; `--propose-candidate` cannot re-show a candidate because a re-run builds on the active one
(see #430).

One owner direction remains open.

**Wider run-log coverage (owner aim, 2026-09-24; not done).** Only propose, question, replacement, and now
structural edit write run logs. The decision commands that change state — approve, reject, discard, and promote —
write none. Whether and how to log them is undecided.

**Tracked 2026-09-29:** `BACKLOG.md` #434 records the decision and its fence.

### Convergence status

Closed by owner decision, not by the strict stopping rule (see the decision below). Passes 1 and 2 were not clean and needed four
logic-changing commits (`bf3c7fda`, `41a1ae44`, `3722f7a6`, `ae3fb0bc`). Against the newest, `ae3fb0bc`, pass 3
was low-yield (logic and coverage clean, four low documentation findings). Pass 4 found no correctness defect,
and its executed evidence is the strongest yet (51,000 transitions, an oracle independent of the stored route,
guard mutants detected), but it returned one medium coverage finding on the central guard. A medium finding is
not advisory-severity, so under `integrations/shared/DIRECTIVES.md` § "After `run` finishes a plan" and the
severity-aware stopping rule the streak restarts after its fix. The fixes are test-only and documentation-only
and leave the logic head unchanged.

**Owner decision (2026-09-24): stop here and accept convergence.** This deliberately does **not** satisfy the
two-consecutive-clean-or-low-yield-pass rule: the strict count against `ae3fb0bc` is one (pass 3), because pass 4
returned a medium finding. The owner judged the executed evidence sufficient instead of spending passes 5 and 6:
no correctness defect in passes 3 or 4; a randomized state-machine search over the real library functions
(51,000 transitions, an oracle that judges structural change from artifact content and never from the stored
route, guard mutants detected) with 0 violations; the full suite green at `75664e74` (13,730 passed, 190
skipped); and every finding across the four passes dispositioned. Deliberately not done: passes 5 and 6, and any
mutation or crash-window testing beyond what pass 4 executed. The closure did not cover the two owner directions
open at the time, which were follow-on work: the stack direction shipped as `roadmap-stack-aware-approval`, and
wider run-log coverage remains open. That plan's logic commits (steps 1–7) post-date this closure, and this ledger
records no review pass over them. A later logic-changing commit reopens the window,
and a new finding of the recurring class (structural content reaching the head without a decision) should be
treated as a non-converging signal and surfaced rather than patched by another per-route guard; the alternative
recorded for that case is to enforce the property once at promotion by measuring what the promoted version
changes against the accepted head.

Trajectory across the four passes, by identity and severity: the high correctness finding recurred in the same
class twice more (P1.8, P2.1) and did not recur in passes 3 or 4; the non-documentation tail went from three
coverage findings and three low findings (pass 1), to one coverage finding (pass 2), to none (pass 3), to one
coverage finding (pass 4) that pass 3 had explicitly dropped; the documentation tail is the retention and
publication-contract wording, corrected four times, each time narrower.

## Roadmap versioned feedback revision chain — post-run review ledger

*Opened 2026-09-23.*

### Summary

| Field | Value |
| --- | --- |
| Plan | `roadmap-versioned-feedback-revision-chain` (`docs/implementation-plans/archive/2-roadmap-versioned-feedback-revision-chain.md`), 11 steps, all `done`; `status: completed` (2026-09-23) |
| Branch | `codex/roadmap-feedback-batch-revision`; pushed through `2ba267a3` only, every commit since (from `25c7c737`) is local (the pre-push hook runs the full suite) |
| Run head (all steps green) | `c2c64ef4` |
| Checks run | `reconcile-code --all` sweep 1 (`gpt-5.6-terra`, `reports/20260923-144352…145713-run-reconcile.json`); sweep 2 (10 code steps, step 11 non-code, `reports/20260923-165831…171047-run-reconcile.json`, committed `0ac4b4a0`); full suite 13367 passed / 191 skipped at run head, 13601 passed / 190 skipped at `8e978039` |
| `/code-review` | Pass 1 (`high`, report-only, `e9a3e30b..HEAD` at `f00c1d95`): 10 ranked + 5 below-cap, 14 fixed (P1.5-P1.7 by a deliberately narrower remedy), 1 declined (P1.12). Pass 2 (`f00c1d95..93e0bac4`): 3, none high, fixed. Pass 3 (`93e0bac4..8a2b455d`): 3, none high, fixed by one rework. Pass 4 (`8a2b455d..cd4a3c4a`): 1 low, fixed. Pass 5 (`cd4a3c4a..54521e4f`): 2 low, fixed. Converged at the low-yield level |
| Current disposition | Both post-run tails done; no third `reconcile-code` sweep (no finding is a safety or authority failure); plan closed. Follow-ups: BACKLOG #427, #428, #429, #395 and one `BUG_BACKLOG.md` entry |

**Next:** nothing in this plan; it is closed and the loop is converged. Follow-ups: BACKLOG #427, #428, #429, #395. A logic-changing commit after `8e978039` re-opens the loop: run `/code-review high` (report-only, no `--fix`; never `ultra`, do not drift to `max`) over the diff since `8e978039` via the `code-review-loop` skill, into this one doc (no `-roundN` files), and disposition each finding before any further pass. Pass 5's fix changed no behavior, so it does not re-open the loop.

### Settled decisions (hand these to any reviewer)

*Compression note (added 2026-11-13; the ledger was compressed 2026-09-29): this ledger had no original settled-decisions list; the list below was assembled from its own declined and refuted findings.*

Decided by the user during plan authoring; a finding contradicting one is invalid unless the decision itself is reopened.

1. Promotion clears the active-candidate pointer in the same guarded publication as the accepted-head swap and writes no `CandidateTerminalResolution` (the promoted candidate becomes the root).
2. Legacy migration reads the frozen legacy working artifacts at migration time; enrollment blocks every old write route for the migration-pending window, and migration rechecks artifact bytes before publishing.
3. Settlement confirmation is a two-call handshake carried by an immutable confirmation-evidence receipt (`roadmap_evidence_store.publish_evidence`), read back by exact final name; distinct from the settlement receipt.
4. By judgment: `CandidateTerminalResolution` (`rejected|discarded|settled`) is defined once in step 5 and consumed by steps 7 and 8; `check_ledger_processing_ready` lives in step 1.
5. Batch review replacement (user, 2026-09-23; departs from detail 08, which is amended): predecessor is S, the reviewed candidate's source (not C1: that needs a capsule from the live ledger, forbidden, and puts R two hops from the root); R's responses replace the text on items still awaiting review on C1; the rebinding field is added now, `ProposalFields.candidate_version_id` (`8dbc044d`), no schema bump. By judgment: the pointer swap happens at seal time; after it, `seal_review` replay, `answer_candidate_question` replay and question/answer commands about C1 refuse (`test_review_commands_for_a_sealed_candidate_refuse_once_the_replacement_is_active`). Risk: if the intended model is "every revision chains from the last one", predecessor = S is wrong.
6. Fix-round rules: a legacy row with a blank request imports as a `closed` marker item, not skipped or refused. The smallest-proof rule (the smallest proof that completes the intent, not the eventual capability) narrowed P1.5 and P1.6. By judgment: the id normalization and null-selected fingerprint for an unresolvable target; `legacy_source` with no schema bump (ledger not on `main`); `RemovalRecord`s and `feedback_reopen` records not imported; P1.4 refuses rather than supersedes.
7. **Deliberately not built:** persisting `response_patch` and `derived_feedback` on the initial batch candidate's evidence. It would restore the `response` anchor and let batch evidence recompute its identity (closing the S4 residual), but nothing needs either today.

### Fix guidance

- Verify every guard by mutation (revert the fix, watch the test go red). A RED with an empty failure line is a collection error: pass `-k` expressions as separate arguments. A guard behind an overlapping guard survives a single mutation by design: mutate the pair.
- `reconcile-code --all` audits only; `enforce_step_tests` checks only that a test file was touched, so a green step proves little about coverage.
- `publish_roadmap_generation` never compares a member's recorded old bytes with disk, so batch store and seal run `require_batch_state_unchanged` (pointer plus exact ledger bytes) in `before_replace`.
- Full suite: `uv run pytest tests/ -q -n auto` (~255 s; background it, tee to `.tmp/<slug>.*.log`). `plan-tool … --commit` needs a clean tree; use `--model gpt-5.6-terra` except for `create`/`roadmap`.

### Self-found during the run

- **Optional fields with no default broke the `exclude_none` evidence round-trip** (`ReviewerItemSnapshot.proposal`, `CandidateProposalEvidence.feedback`). **Disposition:** fixed `926273cb`.
- **Same class** (`CandidateQuestionInventory.feedback`, `RoadmapRowDiff.before/after`, `CandidateRowImpactAtom.before/after`; add-row/remove-row candidates refused as "evidence is invalid"), plus batch replacement parsing the legacy `{"delta": …}` wrapper. **Disposition:** fixed `8689d1fe` — model-graph guard test, mutation-verified.
- **`DATA_CONTRACT.md` section for `RoadmapLocalRevisionPreflight` deleted by step 11** while the event is still emitted. **Disposition:** fixed in the step 11 commit.
- **Every batch after a promotion refused `candidate processing pair changed`** (the plan's headline outcome was false): the pointer's root was compared with the head before checking whether it names a candidate. **Disposition:** fixed `a3a10610` — only a pointer naming an active candidate is judged against the current root; all `load_candidate_admission` readers swept; mutation-verified both directions.
- **Same class, settlement:** `_admission_blocks_settlement` refused forever (`unpromoted-candidate-lineage`) after reject/discard released a batch pointer. **Disposition:** fixed `cd31d12f` — applies only to a selector-era admission (`root_version_id is None`); legacy refusals stay pinned by `test_unpromoted_lineage_*`.
- **Acceptance test compared two empty dicts** (read a nonexistent `.plan-tool/versions`). **Disposition:** fixed `6d98c0d6` — `test_cli_candidate_lifecycle_promotes_only_the_reviewer_displayed_answer_incorporated_replacement` un-skipped, mutation-verified.
- **Promotion's own `source_ancestry_to_root` call is redundant** with `load_stored_candidate_proposal` plus the root check; removing it stays green. **Disposition:** declined — kept as defense in depth.

### Reconcile-code sweep 1

- **F1 — `_find_exact_row` scans legacy `FeedbackRow`s** (high): a ledger item targeting one fingerprinted, then the batch refused `incomplete-closure`. **Disposition:** fixed `e8d7894d` — probe-verified; now `design_row_collections`, two tests, mutation-verified.
- **F2 — missing step 1 lifecycle/stale-target tests** (medium, lead): **Disposition:** tracked #427 (five step 1 detail names have no matching test).
- **F3 — missing step 3 tests** (medium, lead): **Disposition:** fixed by S1 `744201da`; cited names in #427.
- **F4 — `build_candidate_context` keeps the selector overload** (medium): **Disposition:** fixed `4cd8acdf` — detail 03 states the legacy selector boundary (ledger-less route and re-verification of stored selector-era capsules).
- **F5 — batch artifacts always re-rendered** (medium, lead): **Disposition:** fixed by S2 `aa77ce05`.
- **F6 — storage-window `migration-required`/changed pair/changed item surface as `failed`, not `refused`** (high): **Disposition:** fixed `4286be3a` — `CandidateStorageRefusal` at every deterministic raise site of the batch path (exit 2), six mutation-verified tests; the selector path `_store_candidate` keeps `failed` deliberately (pre-plan contract).
- **F7 — no supersession relation beside the former active candidate** (high): **Disposition:** fixed `ce810c45` — `CandidateSupersession` and `build_supersession_member`, written in the pointer-replacing generation; a pre-existing record fails the generation; history only; mutation-verified.
- **F8 — `CandidateTerminalResolution` accepts arbitrary identity strings** (medium, lead): **Disposition:** fixed by S5 `dba3c5eb`.
- **F9 — no third successor: context accepts only a root or its direct candidate** (high): **Disposition:** fixed `cd2f0532` — `source_ancestry_to_root` used by evidence validation, the batch runner and promotion; `build_candidate_context` verifies the chain and stays fail-closed at one hop without one.
- **F10 — `_processing_source()` does not validate stored evidence** (high): **Disposition:** refuted — `load_resolved_stored_version` digest-verifies every member, step 6 needs only the source's bytes, the spec does not ask for it, and the pointer is written only by step 5's guarded publication.
- **F11 — ledger-run tests are 4 helper-level tests** (high, lead): **Disposition:** fixed by S7 `41cab1b1` and the migration tests since.
- **F12 — settlement always uses `matching_feedback_rows`** (high): root cause was the file missing from plan frontmatter `files:`; corrected. **Disposition:** fixed `e2f9ecaf` (+ `48eeb59c` CLAUDE.md, architect-tier review needed in the PR, own commit) — ledger evidence when the ledger path exists; new verdicts `feedback-not-eligible`, `migration-required`; the digest hashes only reviewer-authored fields because an `open` item can carry a hand-flipped proposal (`test_ledger_evidence_digest_binds_the_reviewer_request_and_ignores_a_model_proposal`); 30 leaf tests, six mutations red. #394 removed, #395 narrowed at closure.
- **F13 — settlement writes no `CandidateTerminalResolution(settled)`** (high): the old `_before_replace` guard made an affirmed settlement with an active candidate impossible. **Disposition:** fixed `834875d4` (code), `25c7c737` (tests + detail 07) — mutation-verified three ways.
- **F14 — enrolled-settlement tests skip affirmed-atomic, settled history, drift, receipt-window cases** (medium, lead): **Disposition:** fixed in substance by `25c7c737`, `16ca0ee2`, `92280d95` and existing window tests (not matched one by one; cited names in #427).
- **F15 — embedded-feedback assertions kept for enrolled roadmaps** (medium): **Disposition:** fixed — ledger cases added with `e2f9ecaf`; embedded tests kept for ledger-less enrolled roadmaps.
- **F16 — replacement flow is selector-era** (high): also found: R was unreadable without its own `candidate-evidence.json`; promotion's identity recheck omitted the response patch and derived feedback. **Disposition:** fixed — binding `8dbc044d`, records `c58cf505`, request/store `2a4aaec3`, seal swap `f4d4adb1`, promotion `eaa4d8ca` (with `a3a10610`, `cd31d12f`, `180902cf`, tests `6d98c0d6`, docs `44e8e465`, `81de8da4`, `4cd8acdf`, `b148f302`). R applies the delta to S using C1's stored capsule; `seal_review` publishes seal, supersession, pointer swap and ledger patch (skips reopened/edited/closed/deferred items); selector-era seal bytes pinned by `_LEGACY_SEAL_BYTES`; 16 promotion tests incl. multi-hop; mutation-verified.
- **F17 — records do not persist root/source/batch identities** (high): **Disposition:** fixed `c58cf505`.
- **F18 — review tests are one synthetic assertion** (medium, lead): **Disposition:** fixed by S11 `008f6b81`, `e1ea0e3e`; cited names in #427.
- **F19 — selector-era admission branches retained in review** (medium): **Disposition:** refuted as stated — live legacy for ledger-less roadmaps and on-disk records; branch once on `batch_receipt is not None` (landed with F16).
- **F20 — promotion accepts root-less admissions and does not release the slot** (high): **Disposition:** partly refuted, fixed `eaa4d8ca` — `roadmap_version_promotion.py:95` already releases the pointer (now really tested); the root-less admission is live legacy (detail 09); the real gap was promoting a batch replacement.
- **F21 — CLI passes `feedback_selector=None` to a `str` parameter** (high): untidy, nothing reads run-log argv. **Disposition:** fixed `180902cf` — `str | None`, argv omits it.

**Coverage note.** 212 step-detail test names cited, 116 defined, 96 not (a missing name is a claim to check, not a confirmed gap). **Disposition:** tracked #427.

### Reconcile-code sweep 2 (9 high / 3 medium, down from 12 / 9)

- **S1 — step 3 batch tests missing** (medium, PARTLY): **Disposition:** fixed `744201da` (tests); the repeatability test pins determinism and has no natural mutation.
- **S2 — step 4 batch assembly re-renders every member** (high, PARTLY): retention gated on `not feedback_free`, unreachable today. **Disposition:** fixed `aa77ce05`.
- **S3 — derived feedback hashed in the model's order** (high, TRUE): **Disposition:** fixed `1b862a7c` — sorted by `context_id`.
- **S4 — batch evidence accepts a capsule differing from its receipt** (high, TRUE): six edits accepted by probe. **Disposition:** fixed `1ff3e546`. Residual: a capsule and receipt edited consistently together is undetectable (no response patch in batch evidence).
- **S5 — terminal resolution and release builder do not bind root/source/candidate** (high, PARTLY): **Disposition:** fixed `dba3c5eb` — validators and builder check; reject/discard report `refused`.
- **S6 — a request edit keeps the old fingerprint and stays ineligible** (high, REFUTED): **Disposition:** refuted — plan line 269 says a changed target stays ineligible until retargeted; rebinding on edit would approve a changed target.
- **S7 — step 6 ledger-run coverage** (high, TRUE): also found every reviewer action and migration published with no in-window byte comparison. **Disposition:** fixed `41cab1b1` — exact-byte recheck in `_publish_ledger`, 8 new tests.
- **S8 — settlement binding omits the active candidate's source and terminal state** (high, REFUTED): probe shows refusal before any receipt, `source-changed` inside the window. **Disposition:** refuted, tests `16ca0ee2` (the `elif confirmed_binding is not None` branch is redundant with the next; the pair is pinned).
- **S9 — settlement falls back to embedded feedback for a ledger-less enrolled roadmap** (medium, TRUE plan-side): deliberate, two tests pin it. **Disposition:** fixed `38ffe921` (detail 07).
- **S10 — `_publish_batch_seal` checks migration readiness, forbidden by detail 08** (high, PARTLY): a hand-set `migration-pending` is reachable. **Disposition:** fixed `5d885743` (detail 08), test `008f6b81`; code kept.
- **S11 — step 8 tests omit rejection, discard, stale release, anchors** (high, TRUE): `--reject-candidate`/`--discard-candidate` had no test. **Disposition:** fixed `008f6b81`, `e1ea0e3e`; dead "idempotent replay" branch removed.
- **S12 — CLI tests keep the retired selector-bound contract** (medium, TRUE low risk): **Disposition:** fixed `868a89eb`; the ~15 `run_local_feedback_revision` monkeypatches and `_revise_feedback_has_conflict` alias stay with #429.

### Review pass 1 (fixes `ee323b71`–`8a121008`, docs `7a47a593`; 13587 passed at `8a121008`)

P1.3, P1.7, P1.9, P1.10, P1.14 were built in a worktree and cherry-picked; hashes are branch commits.

- **P1.1 — one delta prompt serves only the batch shape** (high, CONFIRMED): selector-era proposals ended `response-rejected`. **Disposition:** fixed `ce48d805` — pre-range template restored (from `bde7990b`) as `roadmap-candidate-delta-selector.md`, chosen by capsule type; mutation-verified.
- **P1.2 — `_content_identity` changes every selector-era identity** (high, CONFIRMED): also the admission no longer round-tripped. **Disposition:** fixed `ee323b71` — keys added only when `response_patch is not None`; `_LEGACY_SEAL_BYTES` had been captured post-change and is replaced with bytes from `e9a3e30b`; mutation-verified.
- **P1.3 — legacy migration cannot import legal rows** (high, CONFIRMED by read): removed-row target, same id in two artifacts, unsafe ids, empty response. **Disposition:** fixed `1e10274e`, `8d0f3356` — all four probed; unresolvable target imports ineligible, unsafe or repeated ids become `legacy-<artifact>-<12 hex>`, empty response imports as no proposal, every item records `legacy_source`, blank request imports as a `closed` `LEGACY_BLANK_REQUEST_MARKER` item; a stale branch ledger must be re-created (no `LEDGER_SCHEMA_VERSION` bump).
- **P1.4 — batch route overwrites an unpromoted selector-era admission** (medium, PLAUSIBLE): **Disposition:** fixed `ee323b71` — refuses `unpromoted-candidate-lineage` under a deliberately narrower predicate than settlement's (a selector lineage has no discard route, #395); mutation-verified.
- **P1.5 — batch `_validate_candidate_evidence` skips reproductions** (medium, PLAUSIBLE): **Disposition:** fixed in part, by design `12b47511` — `predecessor_diff` (the only consumed stored field) is recomputed; `content_identity` refuted (record binding refuses an edit); `gate_evidence`, `review_requirement`, capsule reproduction deliberately not recomputed (identity would need the persisted patch, the unbuilt capability).
- **P1.6 — batch question cannot be grounded in a proposed response** (medium, PLAUSIBLE): **Disposition:** fixed by narrowing `5dc8ffd4` — the `response` anchor is withdrawn and refused with a reason; details 05, 08 and the plan body corrected; persisting the patch not chosen.
- **P1.7 — settlement evidence not rechecked in the publication window** (low, PLAUSIBLE): **Disposition:** fixed (narrow), other half declined `92280d95` — `decision_settlement_candidate_is_current` compares the evidence digest (window A). Window C (edit after `is_current`) declined: no ledger member in settlement's generation so no lost update (`test_settled_root_owns_no_derived_context_from_the_released_candidate_and_the_ledger_is_untouched`), and only an out-of-band hand edit reaches it.
- **P1.8 — batch route records no failure diagnostics** (low, CONFIRMED): **Disposition:** fixed `ae416327` — `last_response`, `response_accepted`, `call_count` set; parse-failure receipt written.
- **P1.9 — ledger-less enrolled roadmap reported as corrupt ledger** (low, PLAUSIBLE): **Disposition:** fixed `07e223d0` — load gated on `ledger_path.exists()`.
- **P1.10 — CLI error-handling gaps** (low, CONFIRMED/PLAUSIBLE): reject/discard drop `result.detail`; ledger handler omits `RoadmapWriterGuardError`. **Disposition:** fixed `2eff39f9` (second half narrower than stated, added anyway).
- **P1.11 — dead aliases and a pass-through wrapper** (cleanup, CONFIRMED): **Disposition:** fixed `28854ee9`.
- **P1.12 — `_confirmation_result` attaches undeclared attributes; evidence published before gates** (low, PLAUSIBLE): **Disposition:** declined — `object.__setattr__` keeps the shared result at four fields (`test_result_is_the_shared_redacted_run_result`); evidence before gates is the settled handshake (gates rerun at the response; evidence inert).
- **P1.13 — `_anchor_resolves` accepts new anchor kinds for selector-era candidates** (low, PLAUSIBLE): **Disposition:** fixed `28854ee9`, three-kind test.
- **P1.14 — per-item artifact parsing in `eligible_reviewer_items`** (low, PLAUSIBLE): **Disposition:** fixed `8a121008` — per-call cache, spy-pinned.
- **P1.15 — settlement handshake and reject/discard/migrate flows missing from the how-to** (low, PLAUSIBLE): **Disposition:** fixed `7a47a593`; #394 and #395 reconciled at closure.

### Review pass 2 (`f00c1d95..93e0bac4`)

- **P2.1 — reopening a blank-request marker item makes the marker eligible reviewer text** (severity not stated): three routes (reopen, target-only edit, retarget) opened a marker item. **Disposition:** fixed `7f3d64ed`, placement corrected by `a50964d2` — an item with `legacy_source` and the marker request cannot be reopened, target-edited or retargeted (named error, bytes unchanged); a real-text edit is the exit; reviewer-written items with the same sentence reopen normally (asserted); mutation-verified.
- **P2.2 — legacy migration re-parses the target artifact per row** (severity not stated): incomplete P1.14 sweep. **Disposition:** fixed `96fdb5c2` — shared `parsed` cache; parse count equal for one row and five.
- **P2.3 — `legacy_source` does not identify a row when an id repeats within one artifact** (low): needs a hand-edited artifact past `check_feedback_integrity`. **Disposition:** fixed (documentation) `572af8b7` — sentence narrowed; storing row position declined.

### Review pass 3 (`93e0bac4..8a2b455d`; all seeded by the `7f3d64ed` schema-level placement)

- **P3.1 — the invariant keys on text equality: a legacy row whose own words are the marker sentence blocks migration** (probed): **Disposition:** fixed `a50964d2` — rule lives only at the two opening actions; `test_a_legacy_row_whose_own_words_are_the_marker_sentence_migrates_as_an_ordinary_open_item`. Residual: refused on reopen once closed; a text-supplying edit clears it.
- **P3.2 — as a model validator, a hand-edited ledger becomes unloadable** (by read): **Disposition:** fixed `a50964d2` — `test_a_marker_item_hand_edited_to_open_still_loads_and_the_named_exit_still_runs`; the guard covers tool actions, not hand edits.
- **P3.3 — refusals reach the CLI as a raw pydantic dump** (by read): **Disposition:** fixed `a50964d2` — a `RoadmapFeedbackLedgerError` naming the item id, no validation residue, bytes unchanged.

Pass 3 was the "auditing your own edits" pattern: the schema placement was the wrong shape, so the remedy was the local shape at both actions, not a schema patch.

### Review pass 4 (`8a2b455d..cd4a3c4a`)

- **P4.1 — the guard refuses only the exact marker sentence, so a whitespace-only edit opens a marker item** (low): **Disposition:** fixed `507660d6` — uses migration's predicate `not request.strip()`; `test_an_edit_that_supplies_only_whitespace_cannot_open_a_blank_request_marker_item`. The pre-existing whitespace-only reviewer request looseness is tracked in `BUG_BACKLOG.md` ("The feedback ledger accepts a whitespace-only reviewer request"), `1693e4ae` (tightening `_requires_request` would change parse-time loading).

### Review pass 5 (`cd4a3c4a..54521e4f`)

- **P5.1 — the whitespace clause fires for every migrated item and its message misdescribes one with real text** (low): **Disposition:** fixed `8e978039` — message names the missing text and rule; docs say any migrated item; behavior unchanged.
- **P5.2 — the test pins the whitespace refusal only on the marker item** (low): **Disposition:** fixed `8e978039` — `test_a_blank_edit_cannot_open_any_migrated_item_and_refuses_with_the_named_error`, mutation-verified against the narrowing the pass describes.

### Out-of-range / recall-mode findings

_(none)_

### Filed in backlog

- **#427** — 96 step-detail test names with no matching test; absorbs F2, F14 and the citation gaps.
- **#428** — proposal current-or-stale status defined but never computed from `ProposalFields.candidate_version_id`.
- **#429** — `plan_tool/roadmap_revision_run.py` is CLI-unreachable but still emits `RoadmapLocalRevisionPreflight`; retiring it is outside this plan.
- **#395** — narrowed to the selector-era lineage (#394 removed). **`BUG_BACKLOG.md`** — whitespace-only reviewer request (`1693e4ae`).
- #428 and #429 were filed as #425 and #426 (still so in older commits, e.g. `9a4d34a2`) and renumbered at the `main` merge.

### Convergence status

Converged at the low-yield level; the plan is closed. Pass 1: 3 high / 3 medium / 4 low + 5 below-cap. Pass 2: 3 findings (P2.1 broke a stated invariant, material, reset the streak). Pass 3: 3 findings, all seeded by the pass 2 fix, two regressions (still material). Pass 4: 1 low, not a regression. Pass 5: 2 low, both about the pass 4 change. Passes 4 and 5 are two consecutive low-yield passes against the latest logic-changing commit `507660d6`: low-yield convergence, not a clean audit; advisory findings are retained above. Sweeps 1 and 2 are triaged and every true finding is fixed and mutation-verified. Follow-ups: #427, #428, #429, #395.

Final full suite: **13601 passed / 190 skipped, 0 failures at `8e978039`**. Earlier: 13367 run head; 13406 `cd2f0532`; 13439 `f4d4adb1`; 13455 `eaa4d8ca`; 13463 `4cd8acdf`; 13526 `868a89eb`; 13587 `8a121008`; 13593 pass 2 fixes; 13595 `a50964d2`; 13597 `507660d6`.

## Roadmap stack-aware approval — post-run review ledger

*Opened 2026-09-24.*

### Summary

| Field | Value |
| --- | --- |
| Plan | `roadmap-stack-aware-approval` (`docs/implementation-plans/archive/2-roadmap-stack-aware-approval.md`), 8 steps (7 code, step 8 non-code), all green. Source: `BACKLOG.md` #431; Jira `IPPT-9`. |
| Branch | `codex/roadmap-stack-aware-approval-seed`, based on `origin/main` at `950365c2` (PR #19 merged). Local only; publishing needs a force-push. |
| Range | Baseline `aba83968`; run head `f62aad66`; reconcile-code reports committed at `d942827d`. Product code net +378 lines, tests net +3,573. |
| Checks run | Four bare-plan `completeness-audit --iterate` rounds and one detail-grounded audit (`20260924-235704-completeness.md`), each `no-qualified-current-evidence` at the pass cap; loop stopped by exit 2. Full suite green after every step and at the end: 13,936 passed, 190 skipped. One `reconcile-code --all` sweep (`20260925-014553` through `20260925-015848` `-run-reconcile.json`): 0 critical/high/medium, 1 nit. |
| `/code-review` | Pass 1 (`high`, report-only, `aba83968..b64880d9`): no logic findings. Pass 2 (`high`, independent, `aba83968..40fdb416`): no critical/high/medium; one low PLAUSIBLE finding, three nits. |
| Current disposition | **Converged (2026-09-25).** Sweep nit declined. P1.1 fixed, P1.2 and P1.3 declined, P1.4 trimmed, P1.5 left. P2.1 declined and filed in `BUG_BACKLOG.md`, P2.2 declined, P2.3 and P2.4 fixed. |

### Settled decisions (hand these to every reviewer)

From `BACKLOG.md` #431, the plan's Architecture, and the owner's decisions of 2026-09-24. A finding proposing the opposite is invalid, not deferrable.

- **Approval carries the stack.** A structural approval covers every unpromoted hop above the candidate's recorded root (`root_version_id` in stored evidence, never the current head). The stack is structural iff any such hop stores a STRUCTURAL route. Derived at use; no new persisted field; the root's own route is never read.
- **Hop contributions.** A stored route contributes itself; a hop with none (legacy, or an answered replacement) contributes nothing. A candidate with no recorded root yields "no structural hop", distinct from underivable. A hop that is missing, not a stored candidate, or fails validation makes the whole stack underivable: every guard and the recovery predicate refuse it.
- **Presentation scope (decision 2, amended 2026-09-24).** The structural decision and the proposal output of a stack with a structural hop show the whole stack. The answered route's output, `--reject-candidate`, `--discard-candidate`, and any stack with no structural hop keep current output; showing presentation-only hops on the answered route is invalid.
- **Confirm step.** Approve without `--confirm-stack-digest` prints the stack and a digest and writes nothing; with the digest recomputed at confirm time it seals and promotes; any other digest refuses with no write. The digest is stateless and not stored; no terminal prompt, show command, or confirm for edit or reject.
- **Binary observable.** Every candidate-lineage promotion whose hops above the root include a STRUCTURAL one carries a `structural-approval` seal on its top candidate and journals the enrolled seed-state member. The seal has one construction site, the confirmed approve. An answered seal over a structural stack is refused at the promotion boundary and both answered-route entries.
- **Edit and reject.** The edit check tests the replacement's stack (source's stack plus its own computed route). Reject and discard still release the whole active pointer; abandoned hops stay as history.
- **The interim block is retired last.** `--propose-candidate` stacks under a structural candidate; the stacking carve-out tests stay.
- **Old seals.** Not migrated; an unpromoted one stays promotable only while its candidate is active.
- **Deliberately not:** semantic judgment of stack content; a content-derived cumulative classifier; a second structural gate or per-hop approval; a new persisted stack or binding field; auto-approval; a terminal prompt; changes to the promotion writer's authority, publication journal, recovery machinery (beyond its stack-aware predicate), or the version and candidate stores; run-log lifecycles for decision commands; the ledger's current/stale label (#428); the unreachable selected-local runner (#429); behavior changes for legacy candidates without a route or root.

### Reconcile-code sweep 1 — triage

- **Nit (step 6, `impact: low`)** — `_render_structural_reject_effect` (`plan_tool/cli/roadmap_cmd.py`) inlines `tuple(hop.version_id for hop in view.hops)`, the same expression as `CandidateStackView.promoted_version_ids` (`plan_tool/roadmap_candidate_review.py:1483`). **Disposition:** declined — the property is named for what a promotion carries while the note lists what a reject drops, and `test_reject_note_lists_every_dropped_hop_and_says_nothing_is_promoted` fails if the note stops naming every hop.

### Review pass 1 (2026-09-24)

No logic findings; the route sweep, guard inventory, carve-out pinning tests, confirm step, and block removal (`db4e1809`) matched the code.

- **P1.1 — Comment and test docstring overclaim** (nit, documentation, CONFIRMED): `plan_tool/cli/roadmap_cmd.py:1207-1209` and `test_proposal_output_keeps_todays_output_when_the_stack_has_no_structural_hop` say "gains no failure mode", but an unreadable lower hop exits 1 after the proposal is stored (fail-closed, pinned by `test_proposal_stack_failure_after_a_stored_proposal_prints_the_stored_lines_and_exits_incomplete`). **Disposition:** fixed `5949f8fa` — wording only.
- **P1.2 — Approve and non-approve branches build and render the view identically** (nit, simplification): `roadmap_cmd.py:1351-1370`; suggestion is to hoist. **Disposition:** declined — no plan property depends on it, step 5's detail split them on purpose, and a refactor would reset the convergence window for a nit.
- **P1.3 — One confirmed approve derives the stack seven times** (low, efficiency, CONFIRMED by count): repeats inside the writer guard are independent re-checks. **Disposition:** declined — the guarded repeats are the design, stack depth is small, and sharing the pre-guard derivations adds coupling.
- **P1.4 — Prose and vocabulary pins in `tests/test_roadmap_feedback_format.py`** (proportionality, not a logic verdict): five new tests (+116 lines), including a retired-wording scan that admits a new spelling escapes, and two pins on the earlier ledger § "Roadmap structural feedback approval — post-run review ledger"; agreement checks between prose artifacts are the shape the development guide refuses. **Disposition:** fixed `cce75613` (source word: "trimmed") — scan, both earlier-ledger tests, and their helpers removed (73 lines); the two format-doc phrase tests stay. Full suite after: 13,936 passed, 190 skipped.
- **P1.5 — CLI label tests, flag-plumbing rows, stated redundancy** (proportionality, not a logic verdict): about fifteen cases pin labels, line order, and flag misuse exiting 2. **Disposition:** declined (source word: "left") — they pin producer-to-consumer seams stubs cannot show and are cheap; removal is churn.

Considered and not reported (refuted or settled): the boundary check "untested" (refuted by `test_seal_requirement_holds_at_the_boundary_when_the_review_guards_are_bypassed`); old single-command seals (pinned by `test_an_approval_of_a_lower_hop_cannot_promote_after_a_later_batch_stacks_on_it`); reject note printed before the decision, exit 1 after a stored proposal, route-less hops, and legacy hops failing validation (all settled and pinned).

### Review pass 2 (2026-09-24)

Scope `aba83968..40fdb416` (comment, docstring, and test changes since pass 1). No critical, high, or medium finding; twelve traced attacks were clean, and pass 1's claims re-checked against the code.

- **P2.1 — A hop whose stored artifacts fail today's parser escapes as a raw exception** (low, error path, PLAUSIBLE): `_require_reproducible_batch_diff` (`plan_tool/roadmap_candidate_run.py:927`) catches `ValueError` but not `RoadmapArtifactError` (`class RoadmapArtifactError(Exception)`, `plan_tool/roadmap_artifacts.py:378`), so such a hop gives a traceback instead of the underivable refusal. No write happens on any path; only the refusal shape is wrong. Not reproduced. **Disposition:** declined and filed in `BUG_BACKLOG.md` (section ROADMAP, severity RISK, commit `62785adc`) — contrived trigger, and a logic-changing fix would reset the convergence window; owner, 2026-09-25. Fix on file: add `RoadmapArtifactError` to the catch tuple with one test in `tests/test_roadmap_candidate_run.py`.
- **P2.2 — Reject note printed in the indicative before the decision applies** (nit, output wording, CONFIRMED): `roadmap_cmd.py:1371-1372`; on a library refusal stdout shows "released … dropped" above `structural decision: reject refused`, exit 2. Order is pinned by `test_reject_over_a_real_stack_prints_every_hop_and_the_drop_note_before_releasing_the_pointer`. **Disposition:** declined — the final line and exit status are correct; owner, 2026-09-25.
- **P2.3 — `_ROOT` left unused by the P1.4 trim** (nit, dead code, CONFIRMED): `tests/test_roadmap_feedback_format.py`. **Disposition:** fixed `718a3a7c`.
- **P2.4 — This ledger named the review model, tool invocation, and a session id** (nit, convention; reviewer PLAUSIBLE, verified CONFIRMED): a repeat of the earlier ledger's P3.1 class. **Disposition:** fixed `48a7aefa` — both sites say "an independent review pass"; the pre-push grep found no other hit.

Considered and not reported (settled): retroactive refusal of pre-change stored state (the defect the plan closes); a stacked batch orphaning a sealed-but-unpromoted approval; stack-view failure blocking edit and reject; recovery failing closed on lower-hop load problems.

### Out-of-range findings

_(none)_

### Convergence status

**Converged (2026-09-25).** Pass 1 was clean on logic. Pass 2 added one low PLAUSIBLE finding (P2.1, declined and filed as a `RISK` in `BUG_BACKLOG.md`) and three nits (P2.2 declined, P2.3 and P2.4 fixed), with no new material issue. Two consecutive clean or low-yield passes against the latest logic-changing commit `db4e1809` (step 7) satisfy `integrations/shared/DIRECTIVES.md`, "After `run` finishes a plan". Every commit since is a comment, docstring, test, or document change (`5949f8fa`, `cce75613`, `718a3a7c`, `48a7aefa`, `62785adc`, and the ledger commits), so the window was never reset. No further pass launches.

Not covered: P2.1 stays open in the bug backlog; the reconcile-code sweep ran once (a further full sweep is warranted only after a verified class-wide correction). The full suite passed at the end of the loop (13,936 passed, 190 skipped) on the tree holding every code, test, and backlog commit.

## Roadmap versioned-from-birth — code review ledger

*Opened 2026-10-06.*

| Field | Value |
| --- | --- |
| Change | `roadmap-versioned-from-birth`: the roadmap folder holds versions from its first stage run; the removed routes (stage re-entry, enrollment, rollback checkpoint, escalation, impact analysis, structural rewrite) and their modules are deleted |
| Branch | `impl/roadmap-versioned-from-birth` |
| Review range | pass 1: merge-base `main...HEAD` at `7b021100` (40 commits, 137 files); later passes at `db82e058`, `8a5ea497..HEAD`, `49a1663b~1..HEAD` |
| Checks run | Full suite `uv run pytest tests/ -q -n auto` after each fix batch: 13,385 (pass 1), 13,398 (pass 2), 13,400 (pass 3), 13,402 passed (pass 4), 65-67 skipped (`.tmp/roadmap-versioned-from-birth.review{1..4}-fixes.log`); mutation checks recorded per finding |
| Reviewer | headless review sessions, report-only, four passes (`.tmp/roadmap-versioned-from-birth-code-review-1.md` to `-4.md`); no reviewer could run programs, so runtime evidence is the suite plus failing-test-first and mutation checks |
| Disposition | passes 1 to 4 triaged; loop closed 2026-10-06 (see "Closure") |

### Settled decisions (hand to each reviewer)

- Plan files under `docs/implementation-plans/**` are canonical for this change and are not edited by review fixes.
- Out of scope for review: `BACKLOG.md` #444 (callerless `structural_codex_*`, run-log structural/impact/escalation events, update-judgment section and prompt), `BACKLOG.md` #445 (docs outside the version-only docs sweep), and the render-version constraint on the byte-stable feedback key comment in `plan_tool/roadmap_artifacts.py`.
- `NoPublishedRoadmapVersionError` from `create`'s research-target reader is pinned by a test; only a corrupt version store becomes a `CreateError`.
- Callerless leftovers found by review are filed, not deleted, in this change (`BACKLOG.md` #446).

### Findings

Every claim was static reading; each was reproduced (failing test first) or checked in the driving session before a fix. "fixed" below means fixed in this change set (no per-finding commit is recorded).

Pass 1 (`7b021100`):

1. medium, fixed: recovery did not recognize a completed root generation because the ledger member was missing from the expected member list (`roadmap_revision_publish.py`; a crash after the head write left a journal every guarded writer refused). The recognizer now expects the version record, brief, four artifacts, the initial ledger (`old=None`), then the selector; the masking test now feeds `captured[0]` unmodified; two sibling tests that pinned the old shape publish the real member list. New: `test_recognizer_accepts_the_real_root_member_list_including_the_initial_ledger`, `test_recognizer_refuses_a_root_member_list_that_is_not_exactly_the_published_one`. Mutation removing the ledger member turns five tests red.
2. low-medium, fixed: a corrupt or missing version store was an uncaught exception in `create --from-existing` on a roadmap-promoted seed (`RoadmapVersionError`). `_confirm_invalidated_roadmap_seed` prints and returns `False`; `_load_roadmap_research_targets` raises `CreateError`; missing head still raises `NoPublishedRoadmapVersionError`. Tests `test_corrupt_accepted_head_is_an_error_message_not_a_traceback`, `test_corrupt_accepted_head_is_a_create_error_not_a_traceback` fail with the fix stashed.
3. low-medium, tracked #446: dead stage-feedback revision path and never-populated `RoadmapResult` fields. The review's "only test callers" claim was partly wrong (machine-verified counts in #446: `_run_bounded_stage_feedback`, `_check_predecessor_review_rows`, `_awaiting_review_count`, `_newly_settled_decision_ids`, `_feedback_counts_by_state`, `_has_open_feedback` have no caller anywhere; three result fields are set by neither construction). `invalidated_seed_count` in `run_log.py` is a different record (#444), not in #446.
4. low, fixed: `DATA_CONTRACT.md` and `docs/OPERATIONS.md` described removed run-log events and preflight categories; `check` list now names the emitted values, `RoadmapStageWritten` describes one event per held stage with `replaced` always `false`, removed bullets dropped. Declined: adding the categories to a drift test (documented prose; no consumer needs it closed).
5. low, fixed: operator/model-visible text still described on-disk artifacts and stage re-entry (`roadmap_cmd.py` help/docstring, `roadmap.py` docstrings, four `roadmap-*.md` stage prompts); `docs/cli/roadmap.md` regenerated; the byte-stable key comment untouched.
6. low, fixed: `_create_handoff_lines` `plans_dir` fallback computed the roadmap folder; `plans_dir` is now a required keyword (test comment corrected, not the fixture line).
7. low, fixed: backlog entries described removed rollback/checkpoint/enrollment routes; after verifying each subject is gone, #398, #399, #400, #401, #274, #275, #429 and two `BUG_BACKLOG.md` entries deleted, dead clauses trimmed from #355 and one receipt entry; `BUG_BACKLOG.md` joins `_REMOVED_ROUTE_DOC_FILES`. Dated closed entries and the connectivity-recovery entry (its design decision) left as written.
8. low, fixed in part: `current =` spacing and a ledger-less-roadmap comment corrected. Declined: the successor-slug remedy on the missing-ledger read (different site from decision settlement, where absence is supported; reachable only by hand-deleting the ledger; no test pins a new message).

Pass 2 (`db82e058`; six findings, no wrong-content or store-corruption defect; not clean):

9. medium, fixed: a SIGKILL during a durable write left `.<name>.<random>.tmp` that `_pre_head_state_paths` counted, blocking every retry with `RoadmapPreHeadStateError`. `fileio.is_write_temp_name` (leading dot, `.tmp` suffix, at least three dots) is skipped; any other stored file still counts. Tests `test_stray_durable_write_temp_files_are_not_pre_head_state`, `test_a_real_stored_file_still_refuses_even_when_it_resembles_a_temp_name`; mutations (drop filter; loosen to `endswith(".tmp")`) turn them red. Declined: unlinking temp siblings in recovery (inert once ignored).
10. medium-low, fixed in part, tracked in part (#447): after a crash between head write and journal unlink no ordinary writer recovers and the refusal named no route. Fixed: the refusal names the journal path and `plan-tool roadmap <slug> --from-existing <brief>`; `docs/how-to/roadmap.md` § 3 and `RUNBOOK.md` updated; test `test_publish_beside_a_leftover_journal_names_the_recovery_command_and_changes_nothing`. Deferred, tracked #447: recover-before-publish in the shared writer guard and unrecoverable non-root journal kinds beside a head (design decision).
11. low-medium, fixed: `delete_resume` failing after the head commit reported a published roadmap as a failed run; the call warns and returns the completed result. Test `test_a_failing_resume_cleanup_after_the_head_commit_warns_and_still_completes`; mutation (catch `ZeroDivisionError`) red.
12. low, fixed: the completed-root recognizer re-implemented initial-ledger construction; `roadmap_feedback_ledger.initial_ledger(slug, ledger_state)` is the one construction. Test `test_initial_ledger_bytes_are_one_construction_shared_by_publisher_and_recognizer`.
13. low, fixed in part: first-run stage loop sent revision-era correction text and rationale; retry correction now reads in first-run terms, predecessor branches deleted (`_authored_review_rows` takes the artifact alone), CLI exhaustion line updated. Test `test_the_retry_correction_names_the_dropped_entries_in_first_run_terms`. Producer-less names tracked #446 (`source_recheck` of `_run_stage`, `RoadmapSourceAdmissionError` raises/handlers, `_StageOutcome.invalid_detail` and `.reused_predecessor`, `OUTCOME_STAGE_INVALID`/`_print_invalid`, `OUTCOME_COMPLETED_NO_CHANGE`/`_print_completed_no_change`); not deleted here per the settled decision.
14. low, fixed: resume-directory files were written without fsync; both writers use `durable_write_bytes` and `read_held_stages` skips write-temp names silently while other strays still warn. Tests `TestResumeWritesAreDurable`, `TestInterruptedWriteLeftoversAreNotWarnedAbout`.

Pass 3 (`8a5ea497..HEAD`; none above low-medium; low-yield by severity):

15. low-medium, fixed: `_require_no_accepted_head` called `delete_resume` unguarded, turning the head refusal into a raw `OSError` and skipping the index refresh; `_delete_resume_or_warn` serves both sites. Test `test_a_failing_resume_cleanup_beside_an_accepted_head_still_refuses_and_refreshes_the_index`; mutation red.
16. low-medium, fixed: stage files after a gap or damaged stage were warned as "not held" but left on disk, so a later run could re-gate a stale stage; `_run_roadmap` calls `discard_stages_from(repo_root, slug, len(held.stages) + 1)` after the digest check. Test `test_stages_after_a_damaged_stage_are_discarded_so_a_later_run_cannot_regate_them`; mutation red.
17. low, declined (no code change): continuing in memory when the resume directory is unwritable would break the owner-decided resume guarantee; failing at the first write bounds loss to one stage reply (`cannot hold stage 1 for resume (...)` via `RoadmapEnvironmentalError`); `docs/how-to/roadmap.md` § 3 states it.
18. low, fixed: `roadmap-plans.md` still told the model it may author `feedback` and `removals`; sentence replaced and "a newly authored or revised row" became "a newly authored row" after a vocabulary sweep of all four stage prompts and the other roadmap prompts (remaining hits legitimate).
19. low, tracked #447: root-journal recognizer pins initial ledger bytes, so a hand edit between a crash and recovery makes recovery refuse with no remedy; same class as 10. Remedy options recorded there: exempt the ledger member once the head names the published version, or name the hand-removal remedy in the refusal.
20. low, declined (documented): the newly created resume directory chain is not fsynced; a power loss costs only regeneration of held stages, nothing published or corrupted.

Pass 4 (`49a1663b~1..HEAD`; five low, no medium; eleven crash points walked):

21. low, tracked #448 (a), `decision-needed`: resume directory keyed by (repo root, slug) while head and writer guard are keyed by plans directory, so two plans dirs sharing a slug can delete/reuse each other's held stages; scoping choice (path vs recorded owner) is a design decision, bounded loss, nothing published affected. Verified by reading only.
22. low, fixed: `discard_stages_from` could raise at preflight on a stray entry the resume module promises only to warn about (side effect of the finding 16 fix); each entry is unlinked in `try/except OSError`, warning and continuing. Test `test_discard_warns_and_continues_when_an_entry_cannot_be_removed`; mutation red.
23. low, tracked #448 (b), `decision-needed`: one unreadable historic record makes `INDEX.md` stale (still labeling the previous version `accepted head`) instead of marking it; remedies (stale marker, absence, partial rows) change what the index promises, so the owner chooses. Verified by reading only.
24. low, fixed: `roadmap-plans.md` gave a false rationale ("reviewers add those rows after the roadmap is published"); now "A first run authors `decisions` only; do not author `feedback` or `removals` rows." Sweep over the four stage prompts found no other live hit.
25. low, fixed: `_print_exhausted` told the operator to delete the resume directory without naming it; it now prints the directory via `roadmap.stage_resume_directory` (the CLI must not import the resume module; `test_resume_directory_is_referenced_only_by_the_stage_run_and_its_owner`) and says deleting restarts at stage 1. Test `test_gates_exhaustion_names_the_resume_directory_and_that_deleting_it_restarts`; mutation red.

### Closure

Closure label: **stopped at exit 2** (the loop was auditing its own edits; neither converged nor clean). Passes 1 and 2 found medium crash-recovery gaps, all fixed with reproducing tests; passes 3 and 4 found nothing above low-medium, and findings 22 and 24 were side effects of pass-3 edits (16 and 18). Per the exit-2 rule the loop finished applying and stopped; no fifth pass.

### Tracked

- **tracked** `BACKLOG.md` #444: callerless escalation, impact-analysis, and structural-rewrite leftovers.
- **tracked** `BACKLOG.md` #446: callerless stage-feedback revision path and result fields (findings 3, 13).
- **tracked** `BACKLOG.md` #447: recover an interrupted publication journal before any writer publishes (findings 10, 19).
- **tracked** `BACKLOG.md` #448: resume directory scoped by plans directory; `INDEX.md` after a failed refresh (findings 21, 23).
- The render-version constraint on the byte-stable feedback key comment in `plan_tool/roadmap_artifacts.py` (settled out of scope).

Not verified: findings 21 and 23 are verified by reading only; no multi-plans-dir scenario and no filesystem-level failure (power loss, unwritable runs directory beyond the monkeypatched and directory-entry cases) was exercised end to end.

## Roadmap stack layer — code review ledger

*Opened 2026-10-08.*

The record of how BACKLOG #461 (plan `roadmap-stack-layer`) was executed and judged.
One ledger, updated in place. Closure label (see `handoffs/README.md` § "Retention"):
**converged** (low-yield rule: passes 4 and 5 were LOW-only display, doc and hardening findings; each changed code, so there is no clean pass).

| | |
| --- | --- |
| Review range | `8ce4516c..HEAD` on `impl/roadmap-stack-layer` (25 commits) |
| Plan | `docs/implementation-plans/archive/2-roadmap-stack-layer.md`, 8 of 8 steps `done` |
| Checks run | Full suite green at 13,591 passed, 67 skipped after review pass 5; five headless review passes; `reconcile-code --all` twice (sweep 1: 5 medium, 2 nit across steps 3, 6, 7; sweep 2: 0 critical / 0 high / 0 medium / 0 nits on all 7 code steps) |
| Reviewer | Headless `claude -p` sessions at effort `high`, report-only, each with a named findings file |
| Disposition | Closed; PR #46 |

### Settled decisions (hand to each reviewer)

- The stack is a `stack` collection in `02-constraints.md`. A missing collection
  (`ConstraintsArtifact.stack is None`) means "stack not recorded" and re-renders
  byte-for-byte as before; `()` means recorded and empty. Nothing may default a
  missing stack to `()`.
- Stack totality binds only an artifact that carries the collection, and a first
  run. It never refuses an artifact for lacking the collection.
- Stack rows carry exactly one of a non-empty `choice` or `open: true`, enforced by the
  `stack-row-state` gate, not the parser. The `concern` field is fixed on edit. Rows can
  be added, replaced, and revised, never removed.
- Stack rows have no row-owned prose (`allow_prose=False`). A candidate `add-row`
  for a prose-less row type treats `prose_amendment` as optional and refuses it when
  supplied (`_add_row_key_contract`). Prose-eligible row types still require it.
- A candidate can introduce the stack on a stack-less roadmap; candidate operations
  apply in target-id order, not the order the model listed them.
- `artifact_row_diffs` pairs collections by name, so a stack-less artifact diffs
  against a stack-bearing one without error.
- An anchorless stack add is authorized by any bound feedback item, including one
  aimed at an unrelated row (decided 2026-10-08, user-confirmed): a stack row declares
  no relation to anchor to, the totality gate refuses a partial stack, and the approver
  sees every added row in the stack callout. The revision route is stricter by design.
- A candidate `replace-row` must preserve every field its row policy fixes
  (`immutable_fields`), as the revision route does; this covers hosting's `facet` as
  well as stack's `concern`.
- The feedback ledger addresses design rows only; stores, hosting and stack rows are
  ineligible reviewer-feedback targets by design. An existing stack row reaches a
  candidate only through a relation (for example a decision anchored to it).
- The stack callouts (first-run output, `INDEX.md`, candidate review) are display
  only: never a defect class, never an approval gate (decided 2026-10-08 under #461).
- The `INDEX.md` stack section reads the accepted head through
  `load_resolved_stored_version`, which verifies every stored member; an
  unparseable member raises and never reads as "not recorded".
- The seed `## Stack` section gains a `### Technology stack` sub-part after
  `### Stores`, rendered by `_render_stack_section`.
- Two optional step 6 tests (per-site callout printing; approval independence of
  stack content) are filed as BACKLOG #465, not written.

### Owner decision: the parser checks types, the gate owns choice/open

Decided 2026-10-08 (user-confirmed): the stack parser accepts a row carrying both
`choice` and `open`, or neither; `stack-row-state` is the single owner of the rule on
every route, matching the step 1 detail's Implementation prose. The step 1 Tests
section's parser-level shape error is superseded. Do not report as a finding.

### Run record

- Step 1: the test-authoring gate misfired (the model had modified a test file); recovered by hand, committed `e7f80792`, `done` flipped as a separate commit.
- Step 2: failed the full suite on two sibling tests pinning the old gate set; fixed by hand (`bb7a94e9`).
- Step 3: a bare `git checkout` of one file discarded the model's uncommitted edits, so the step was reset and re-run; the re-run wrote no tests (gate failed correctly), so tests were applied from the first attempt's saved patch and adapted, one stale invariant test rewritten (`test_every_addable_row_type_has_a_valid_add_row_shape`, mutation-checked) (`9269f33a`).
- Step 5: failed 8 index tests because the fixtures wrote no recorded brief; fixed in the fixtures (`e21d0be6`). The `done` flip is a replacement when the previous step's commit has already written `status: current`; a first attempt inserted a duplicate key and was caught in `git diff`.
- Steps 4, 6-8: green, committed by the tool.
- `reconcile-code` sweep 1 findings were missing detail-promised tests; writing them exposed two code defects, both fixed: the candidate route refused the first stack add (`_prepare_operations`), and `artifact_row_diffs` raised pairing a stack-less artifact with a stack-bearing one.

### Findings

Every pass was static traces (probes refused in the reviewer sandbox); each finding was reproduced in the driving session before acceptance.

Pass 1, `8ce4516c..b8420509`:

1. HIGH: a candidate stack add could not be stored or replayed (wire form carried `prose_amendment: null`; `roadmap_candidate.py:_operations_wire_for_reparse`; reproduced: `candidate add-row prose amendment must be a JSON object`). fixed fe6b5e38.
2. HIGH: candidate context crashed on any roadmap recording a stack (`_project_members` reached `_row_label` with a `StackRow`; `TypeError: unsupported impact row type`). fixed fe6b5e38 (skipped in the inventory as stores are). The related point that an existing stack row cannot be targeted by ledger feedback: refuted as a defect (settled ledger limit).
3. HIGH: `roadmap compare` crashed on a stack card (`display_label` lacked a `StackRow` branch). fixed fe6b5e38.
4. MEDIUM: a decision anchored to a stack row read "undefined" in review views (`_constraints_entries` omitted stack). fixed fe6b5e38.
5. MEDIUM: an anchorless stack add is authorized by any bound feedback item. declined (decided 2026-10-08): deliberate wider authority, pinned by the docstring of `test_candidate_introduces_a_complete_stack_on_a_stackless_roadmap`.
6. LOW: the candidate route never enforced fixed fields (two `replace-row` ops could swap stack concerns; hosting `facet` same gap). fixed (decided 2026-10-08: every policy-declared fixed field enforced, hosting included; mutation-checked).
7. LOW: gate and parser disagreed on a blank `choice`. fixed fe6b5e38 (mutation-checked).
8. LOW: candidate prompts still said every `add-row` carries `prose_amendment`. fixed fe6b5e38.

Class behind 2-4: row-type dispatch predating `StackRow` (`_row_label`, `display_label`, `_constraints_entries`); a sweep by `StoreRow`/`HostingRow` dispatch found no further sites.

Pass 2, `8ce4516c..da28b61c` (ceiling fell from three HIGH to two MEDIUM):

1. MEDIUM: `--view html` linked a stack anchor to a missing element. fixed (Stack block rendered only when a stack is recorded).
2. MEDIUM-LOW: `duplicate-stack-concern` told the model to rename an id. fixed (`_DROP_EXTRA_ROWS_GATE_KINDS`).
3. LOW-MEDIUM: stack summary printed model text unsanitized into `INDEX.md` and the terminal. fixed (one-line collapse).
4. LOW: inherited-decision gate rejects a stack-row anchor the authored-decision gate accepts. declined: same asymmetry holds for hosting; an inherited anchor names a design row by design.
5. LOW: a both/neither `choice`/`open` row can never reach `stack-row-state` on the candidate route. Open at the time pending the owner decision recorded above (parser checks types, gate owns the rule); not reported as a finding.
6. LOW: batch prompt never showed the stack row shape or totality rule. fixed (both templates).
7. LOW: `prose_amendment: null` on a stack add got a misleading message. fixed.
8. LOW (reuse): fixed-field phrase built three times. declined: incidental consolidation, below the duplication guard's threshold.
9. LOW (altitude): "stack is the one creatable collection" encoded in four places. declined: wait for a second optional collection.
10. LOW (efficiency): `INDEX.md` refresh loads the head twice. declined: minor cost on a rare path.

Pass 3, `8ce4516c..51b08cd5` (no crash or data-loss; code changed after, so no clean-pass credit):

1. MEDIUM: format docs called a stack row a ledger feedback target. fixed (`ROADMAP_FEEDBACK_FORMAT.md`, `ROADMAP_FORMAT.md`).
2. LOW-MEDIUM: docs and one gate comment still said the parser rejects both/neither. fixed (vocabulary sweep: `rejects a row carrying`, `parser itself rejects`, `parser's definition`).
3. LOW-MEDIUM: "Pending concerns" ignored a pending decision authored in `04-roadmap.md`. fixed in index and first-run output (mutation-checked); domain decisions stay out since the domain stage runs before any stack row exists.
4. LOW-MEDIUM: summary sanitized `choice`/`concern` but not `id` nor open/pending lines. fixed (mutation-checked).
5. LOW: `stack-row-state` got only generic candidate correction text. fixed (specific branch).
6. LOW: renderers disagreed on a neither-choice row. fixed (`no choice` in `display_label`, HTML block, seed section).
7. LOW: candidate callout lists `model`/`topology` hosting rows as "no product recorded". declined: explicit none marker is deliberate, pinned by `test_hosting_and_store_products_are_listed_verbatim_with_explicit_none_marker`.
8. LOW: candidate callout delta is against the source hop, not the root. declined: narrative evidence has the same per-hop basis.
9. LOW: `CONSTRAINTS_OPTIONAL_ROW_KEYS` referenced nowhere. fixed (deleted).

Pass 4, `8ce4516c..f3fb2ef2` (six LOW; code changed, no clean-pass credit):

1. LOW-MEDIUM: `INDEX.md` stack groups rendered as one list in a Markdown viewer. fixed (blank line before each group heading; test pinned).
2. LOW: plan and step 5 detail described a two-artifact pending read and a stack feedback target. fixed (vocabulary sweep).
3. LOW: the embedded `removals` route can still drop a stack row. declined: authorized by the reviewer's own open feedback as for any design row; `ROADMAP_FORMAT.md`'s "never reverts" is now scoped to typed operations.
4. LOW: seed `## Stack` lead said every row is settled. fixed (names the open exception).
5. LOW: class-name `row_type` spellings (`StackRow`) draw a `prose_amendment` demand in retry text. declined: same for `StoreRow`, at most one retry, diagnostic already says `use stack`.
6. LOW: `_one_line` keeps non-whitespace control characters. declined: no other roadmap model text is filtered for them; hardening one summary would not close the class.

Pass 5, `8ce4516c..b03090c9` (no crash, data-loss or gate-bypass; five LOW):

1. LOW: pass 4's blank separators printed as empty bullets in first-run terminal output (regression from the pass 4 fix). fixed (plain print, as the candidate callout does; test pinned).
2. LOW: choice-or-open display rule written four times, disagrees on a whitespace-only choice. declined: reachable only on a version no gate judged, display only; a shared helper belongs in the backlog if wanted.
3. LOW: fixed-field enforcement also runs on stored-candidate replay. declined: no stored candidate can carry a stack row or facet swap the totality gate accepted before this range.
4. LOW (doc): format doc and plan said the candidate callout lists open and pending concerns. fixed.
5. LOW (doc): step 8's detail still said stack rows are feedback targets. fixed (step 3's text about the embedded stage-feedback route stays).

### Tracked

- **tracked** #465 — two optional step 6 stack-callout tests.
- **shipped** — the pre-push hook drops the repo-local git environment, so a push from a
  secondary worktree no longer lets the suite write into the shared `.git` (was #466,
  removed from the backlog).
- **shipped** — the directives' done-flip sentence now covers a replacement when the
  previous step's commit has set `status: current` (was #467, removed from the backlog).

## Roadmap stack propagation — code review ledger

*Opened 2026-10-08.*

The record of how BACKLOG #460 (plan `roadmap-stack-propagation`) was judged. The
change shipped in pull request #40 (merged as `cba602a8`); its plan shipped in #39.
One ledger, updated in place. Closure label (see `handoffs/README.md` § "Retention"):
**converged**.

| | |
| --- | --- |
| Review range | `bfc8b261..3991adb7` (pass 1 reviewed `bfc8b261..0af115dd`) |
| Last logic-changing commit | `ec368b44` |
| Branch head at merge | `6a834bb1`; merge commit `cba602a8` |
| Checks run | Full suite green at 13,465 passed, 67 skipped; touched test files (1,061 tests) green after the last docs commit; `reconcile-code --all` twice, steps 1-3 at 0 critical / 0 high / 0 medium / 0 nits both times (sweep 1's unreadable step 3 verdict was re-run clean); tests added by the review fixes mutation-checked (breaking the replacer, title normalization, frontmatter handling or the Jira whitelist turns them red); the tests the plan's steps authored were not mutation-checked |
| Reviewer | Four independent headless `claude -p` sessions at effort `high`, report-only |
| Disposition | Converged: passes 3 and 4 were consecutive, independent, and clean against `3991adb7`, which contains `ec368b44` |

### Settled decisions (hand to each reviewer)

- The tool owns the `## Stack` heading of a draft seed: it renders the section from the
  accepted version and replaces any model-authored `## Stack`. The checkable fact is that
  the seed's section equals the accepted rows.
- Hosting rows render `id`, `facet`, `value`, `product`; store rows render `id`,
  `category`, `sharing`, `product`. A missing product renders the explicit open wording.
  A plan row with no components renders the hosting rows alone.
- `Stack` is the fourth, last entry of `GUARDRAIL_BODY_SECTIONS`; `create` preserves the
  seed's section verbatim and the scope fence carries it into detail prompts.
- Conflict surfacing, notes, or technology-name comparison inside `create` and `detail`
  are deliberately not built; the plan audit is the contradiction check (decided
  2026-10-08).
- The Jira handoff deliberately omits `## Stack` (a whitelist).
- A draft not rematerialized after the accepted version changes keeps its older stack;
  detecting that is an accepted limit left to the existing digest.

### Findings

Pass 1 (`bfc8b261..0af115dd`; static traces, finding 1 reproduced by hand):

1. Model-authored heading variants (`## stack`, `## STACK`, `##  Stack`, `## Stack ##`) survived the replacer (4 of 5 variants won), so `create` read the model's text as the plan's stack; medium-high. fixed df4397f5: reuses the reader's own rules via `scope_fence.h2_section_spans`.
2. Replacer's fence scanner differed from the validator's (indentation, info strings). fixed df4397f5, same root cause.
3. A removed model section ran to the next H2 while readers end at the next H1. fixed df4397f5, same root cause.
4. Dead error branch and a second read of the accepted version that could cite a different version. fixed df4397f5: version id comes from the same load.
5. "No accepted store is used" asserted a fact for a plan row with no components. fixed df4397f5: the line says the components name no store.
6. Product values with newlines or markdown could start a heading inside the section. fixed df4397f5: values render on one line; blank product reads as open.
- D1 (“replaces any model-authored `## Stack`” held only for the exact spelling) fixed df4397f5; D2 “four recognized headings” comment declined (accurate); D3 prompt line width declined (cosmetic); D4 stale `#460` references refuted (none remain on the merged tree).

Pass 2 (`bfc8b261..df4397f5`):

7. The replacer scanned the draft's YAML frontmatter: a column-0 `## Stack` comment there deleted the closing `---` and the provenance block (reproduced); low-medium. fixed ec368b44: replacer works on the body only and returns frontmatter bytes untouched; two tests.
8. Nothing pinned that the Jira handoff omits `## Stack`, so a consolidation over `GUARDRAIL_BODY_SECTIONS` would turn it on silently; test gap, medium. fixed 1f8f5bb3.
- D5 `ROADMAP_FORMAT.md` superseded empty-stores sentence, D6 `SEED_FORMAT.md` and D7 `docs/how-to/pipeline/audit.md` heading lists missing the tool-written Stack: fixed 3991adb7. D8 `PLAN_FORMAT.md` “author-supplied” declined (section explains the tool-written case).

Pass 3 (`bfc8b261..3991adb7`): no logic findings; both pass-2 findings re-checked closed. D9 `SEED_FORMAT.md` lead sentence still says “three” headings: declined (accurate for a hand-authored seed; next sentence names the fourth). D10 `PLAN_FORMAT.md` wording: declined, as D8.

Pass 4 (`bfc8b261..3991adb7`, emphasis on tests and callers; 2,676 touched-file tests pass): no logic findings. W1 cross-cutting-listed-components test alone would stay green under another source of `store-checkout`: declined (the exclusion test covers that mutation). D11 `JIRA_FORMAT.md` silent on the Stack omission, D12 a prompt-key test comment claiming an assertion it does not make, D13 trailing blank line: fixed 93d53d41.

### Closure

Converged. The window restarted at each of `df4397f5` and `ec368b44`; after `ec368b44` two independent passes were clean. The two plan-canonical sweeps (steps 1-3 clean; sweep 1's unreadable step 3 verdict re-run) ran before and after the review fixes. Documentation-only commits after `ec368b44` did not reset the window.

### Run record

Steps 3 and 4 were committed by the tool. Steps 1 and 2 were accepted by hand
(`RUNBOOK.md` § "Accept as complete"): each failed the full-suite gate on a defect in the
step's own test or a pinned prompt line break; fixed, suite green, step committed
(`2621def3`, `9a771741`), status set to `done` (`edabfee5`, `b77efc10`). A bare re-run
after a hand fix cannot advance a step (the model changes nothing, so the test-authoring
gate fails, and `--commit` refuses a dirty tree). The recovery is written into
`integrations/shared/DIRECTIVES.md` on branch `docs/directives-hand-fix-on-step-test-failure`;
the gap is tracked below.

### Tracked

Items marked tracked are live in `BACKLOG.md` and `BUG_BACKLOG.md` since pull request #41
merged (`49ec6c5f`).

- **tracked** #463 — `run --step N --accept`, so a hand-fixed step is certified and marked
  done through the tool; the three "re-run" messages name it. Additions recorded on #455
  (the retry prompt never carries `status_note`) and #87 (the no-edit re-run's false
  positive, cause 1 again).
- **tracked** `BUG_BACKLOG.md`, "`create --from-existing` reads several seed sections
  without first removing the seed's YAML frontmatter" — the residual `create`-side
  counterpart of finding 7, with a reproduction and a counted enumeration.
- **tracked** #464 — twelve assertions pin a line break inside wrapped prose; the step 2
  hand fix was restoring one.

### Audit replay

Owed by plan step 3; gates nothing. A throwaway bare one-step plan whose `## Stack` listed
`store-app-db` as PostgreSQL while its `## Architecture` and step 1 used a local SQLite
file was run through `plan-tool --model claude-sonnet-5-5 completeness-audit <plan>
--iterate -y` (2 conceptual passes, bare-plan stage). Both passes reported the
contradiction as a HIGH `plan-correctness` finding quoting both texts, with a fix offering
either choice. One sample, bare-plan stage, `limited` confidence; no detail-grounded replay
or Integration-sized plan. The audit prompt needs no change on this evidence.

### Next session — pickup

State as of 2026-10-08, with `origin/main` at `49ec6c5f`.

| Item | State |
| --- | --- |
| #38, #39, #40, #41 | merged (backlog arc; plans #460, #461 and #462; the #460 implementation; the follow-up entries and the first version of this ledger) |
| `docs/directives-hand-fix-on-step-test-failure` | **local only**, two commits (`512e3aff`, `7fc2567b`): the directives section, a runbook pointer, and a router row in the three skills; no pull request yet |
| #461 plan | on `main`, `planning`, 0 of 8 steps run |
| `stash@{0}` | an abandoned first attempt at plan step 1, superseded by the committed step; safe to drop |

Do these in order. Only 2 still needs a model call (1 is done).

1. **Integration-style audit replay — done 2026-10-08.** See § "Audit replay" below. No action owed.
2. **Re-audit #461's detail bundle.** Its last fixes (duplicate concern, non-removal
   ownership, the narrowed "never unseen" claim) were never re-audited. Plan edits go
   through a plan branch and a plan pull request (the default branch is protected, and
   `run` refuses until the plan is on `origin/main`). `plan-tool status roadmap-stack-layer`
   reports **stale detail** for steps 2 and 3. That is advisory and expected: the step
   fingerprints hash a step's title, files and the plan's scope sections, and the titles
   changed after the details were written. The detail files were edited by hand to match,
   so their content is current. Do **not** run `detail --force` to clear the warning; it
   regenerates the files and discards those edits. Read `grounding.py` for a refresh route
   before touching it.
3. **Decide the directives branch's pull request.** It changes a shared rule, so the
   project `CLAUDE.md` asks for architect review. One small addition is still owed on that
   branch before it goes up: a sentence saying a step that never ran under the tool has no
   `status:` line, so the manual flip to `done` is an insertion that must be verified
   before committing.
4. **Execute #461 only after 2.** Step 7 of that plan extends the `## Stack` renderer,
   which is now shipped. Run it with `run roadmap-stack-layer --commit -y` from a branch
   off `main`.

Housekeeping, only when asked: `git stash drop` for the stash above; the merged local
branches whose remotes are gone belong to `tracking-and-jira.md` § "general branch cleanup"; local
`main` is far behind, so fast-forward it before branching.

### Operating notes for the next session

- A `run` step that fails the suite gate on its own test defect is recovered by hand
  (`integrations/shared/DIRECTIVES.md` § "When a `run` step's own tests fail", once it is
  on `main`; until then on the branch above). Never hand-fix and then bare re-run, and
  never use `--skip-merge-check` to get past the refusal.
- When flipping a step to `done`, assert that the edit landed before committing, and stop
  the command chain if it did not. A failed flip leaves the step runnable, and the next
  `run` re-drives it.
- A `reconcile-code` verdict reading "could not summarize (no findings block)" is not
  clean. Re-run that step.
- Headless review sessions: launch through the expansion of the `claude-personal` alias
  (`CLAUDE_CONFIG_DIR=~/.claude "$(command -v claude)"`), pass the prompt on
  stdin (the variadic `--allowedTools` swallows an argument prompt), grant the findings
  file with `Edit(//<absolute path>)` only, and verify findings dynamically yourself:
  probes through `uv run python -c` are refused inside the headless sandbox.
- This machine's shell has no `timeout`, does not expand aliases in tool calls, and its
  `sed -i` needs an empty suffix argument.
