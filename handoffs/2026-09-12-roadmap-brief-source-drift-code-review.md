# Handoff: independent review of roadmap brief-source drift admission

## Status

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

## Reviewed scope

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

## Settled decisions

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

## Scope fence

- No framework-specific AI-DLC artifact names, stage slugs, or runtime paths.
- Do not review or mutate the Integration repository or its running workflow.
- No role-tagged multi-source intake, citation snapshots, inherited decisions,
  shared request framing, or coverage output (later roadmap-fit work).
- Do not run `reconcile-plan` against the completed implementation.
- Do not apply a finding during review; report it for a bounded correction loop.

## Findings

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

## Out-of-range / recall-mode findings

_(none)_ — every finding lies within the reviewed diff or its cited docs.
Pre-existing test pollution (`TestMaterializeMode`,
`TestKeyboardInterruptRunEndPairing`, one candidate-lifecycle test), confirmed on
base `3cca7b7d`, was deliberately not reported.

## Convergence status

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
