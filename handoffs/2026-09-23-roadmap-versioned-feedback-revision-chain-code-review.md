# Roadmap versioned feedback revision chain — post-run review ledger

## Summary

| Field | Value |
| --- | --- |
| Plan | `roadmap-versioned-feedback-revision-chain` (`docs/implementation-plans/archive/2-roadmap-versioned-feedback-revision-chain.md`), 11 steps, all `done`; `status: completed` (2026-09-23) |
| Branch | `codex/roadmap-feedback-batch-revision`; pushed through `2ba267a3` only, every commit since (from `25c7c737`) is local (the pre-push hook runs the full suite) |
| Run head (all steps green) | `c2c64ef4` |
| Checks run | `reconcile-code --all` sweep 1 (`gpt-5.6-terra`, `reports/20260923-144352…145713-run-reconcile.json`); sweep 2 (10 code steps, step 11 non-code, `reports/20260923-165831…171047-run-reconcile.json`, committed `0ac4b4a0`); full suite 13367 passed / 191 skipped at run head, 13601 passed / 190 skipped at `8e978039` |
| `/code-review` | Pass 1 (`high`, report-only, `e9a3e30b..HEAD` at `f00c1d95`): 10 ranked + 5 below-cap, 14 fixed (P1.5-P1.7 by a deliberately narrower remedy), 1 declined (P1.12). Pass 2 (`f00c1d95..93e0bac4`): 3, none high, fixed. Pass 3 (`93e0bac4..8a2b455d`): 3, none high, fixed by one rework. Pass 4 (`8a2b455d..cd4a3c4a`): 1 low, fixed. Pass 5 (`cd4a3c4a..54521e4f`): 2 low, fixed. Converged at the low-yield level |
| Current disposition | Both post-run tails done; no third `reconcile-code` sweep (no finding is a safety or authority failure); plan closed. Follow-ups: BACKLOG #427, #428, #429, #395 and one `BUG_BACKLOG.md` entry |

**Next:** nothing in this plan; it is closed and the loop is converged. Follow-ups: BACKLOG #427, #428, #429, #395. A logic-changing commit after `8e978039` re-opens the loop: run `/code-review high` (report-only, no `--fix`; never `ultra`, do not drift to `max`) over the diff since `8e978039` via the `code-review-loop` skill, into this one doc (no `-roundN` files), and disposition each finding before any further pass. Pass 5's fix changed no behavior, so it does not re-open the loop.

## Settled decisions (hand these to any reviewer)

*Compression note (added 2026-11-13; the ledger was compressed 2026-09-29): this ledger had no original settled-decisions list; the list below was assembled from its own declined and refuted findings.*

Decided by the user during plan authoring; a finding contradicting one is invalid unless the decision itself is reopened.

1. Promotion clears the active-candidate pointer in the same guarded publication as the accepted-head swap and writes no `CandidateTerminalResolution` (the promoted candidate becomes the root).
2. Legacy migration reads the frozen legacy working artifacts at migration time; enrollment blocks every old write route for the migration-pending window, and migration rechecks artifact bytes before publishing.
3. Settlement confirmation is a two-call handshake carried by an immutable confirmation-evidence receipt (`roadmap_evidence_store.publish_evidence`), read back by exact final name; distinct from the settlement receipt.
4. By judgment: `CandidateTerminalResolution` (`rejected|discarded|settled`) is defined once in step 5 and consumed by steps 7 and 8; `check_ledger_processing_ready` lives in step 1.
5. Batch review replacement (user, 2026-09-23; departs from detail 08, which is amended): predecessor is S, the reviewed candidate's source (not C1: that needs a capsule from the live ledger, forbidden, and puts R two hops from the root); R's responses replace the text on items still awaiting review on C1; the rebinding field is added now, `ProposalFields.candidate_version_id` (`8dbc044d`), no schema bump. By judgment: the pointer swap happens at seal time; after it, `seal_review` replay, `answer_candidate_question` replay and question/answer commands about C1 refuse (`test_review_commands_for_a_sealed_candidate_refuse_once_the_replacement_is_active`). Risk: if the intended model is "every revision chains from the last one", predecessor = S is wrong.
6. Fix-round rules: a legacy row with a blank request imports as a `closed` marker item, not skipped or refused. The smallest-proof rule (the smallest proof that completes the intent, not the eventual capability) narrowed P1.5 and P1.6. By judgment: the id normalization and null-selected fingerprint for an unresolvable target; `legacy_source` with no schema bump (ledger not on `main`); `RemovalRecord`s and `feedback_reopen` records not imported; P1.4 refuses rather than supersedes.
7. **Deliberately not built:** persisting `response_patch` and `derived_feedback` on the initial batch candidate's evidence. It would restore the `response` anchor and let batch evidence recompute its identity (closing the S4 residual), but nothing needs either today.

## Fix guidance

- Verify every guard by mutation (revert the fix, watch the test go red). A RED with an empty failure line is a collection error: pass `-k` expressions as separate arguments. A guard behind an overlapping guard survives a single mutation by design: mutate the pair.
- `reconcile-code --all` audits only; `enforce_step_tests` checks only that a test file was touched, so a green step proves little about coverage.
- `publish_roadmap_generation` never compares a member's recorded old bytes with disk, so batch store and seal run `require_batch_state_unchanged` (pointer plus exact ledger bytes) in `before_replace`.
- Full suite: `uv run pytest tests/ -q -n auto` (~255 s; background it, tee to `.tmp/<slug>.*.log`). `plan-tool … --commit` needs a clean tree; use `--model gpt-5.6-terra` except for `create`/`roadmap`.

## Self-found during the run

- **Optional fields with no default broke the `exclude_none` evidence round-trip** (`ReviewerItemSnapshot.proposal`, `CandidateProposalEvidence.feedback`). **Disposition:** fixed `926273cb`.
- **Same class** (`CandidateQuestionInventory.feedback`, `RoadmapRowDiff.before/after`, `CandidateRowImpactAtom.before/after`; add-row/remove-row candidates refused as "evidence is invalid"), plus batch replacement parsing the legacy `{"delta": …}` wrapper. **Disposition:** fixed `8689d1fe` — model-graph guard test, mutation-verified.
- **`DATA_CONTRACT.md` section for `RoadmapLocalRevisionPreflight` deleted by step 11** while the event is still emitted. **Disposition:** fixed in the step 11 commit.
- **Every batch after a promotion refused `candidate processing pair changed`** (the plan's headline outcome was false): the pointer's root was compared with the head before checking whether it names a candidate. **Disposition:** fixed `a3a10610` — only a pointer naming an active candidate is judged against the current root; all `load_candidate_admission` readers swept; mutation-verified both directions.
- **Same class, settlement:** `_admission_blocks_settlement` refused forever (`unpromoted-candidate-lineage`) after reject/discard released a batch pointer. **Disposition:** fixed `cd31d12f` — applies only to a selector-era admission (`root_version_id is None`); legacy refusals stay pinned by `test_unpromoted_lineage_*`.
- **Acceptance test compared two empty dicts** (read a nonexistent `.plan-tool/versions`). **Disposition:** fixed `6d98c0d6` — `test_cli_candidate_lifecycle_promotes_only_the_reviewer_displayed_answer_incorporated_replacement` un-skipped, mutation-verified.
- **Promotion's own `source_ancestry_to_root` call is redundant** with `load_stored_candidate_proposal` plus the root check; removing it stays green. **Disposition:** declined — kept as defense in depth.

## Reconcile-code sweep 1

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

## Reconcile-code sweep 2 (9 high / 3 medium, down from 12 / 9)

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

## Review pass 1 (fixes `ee323b71`–`8a121008`, docs `7a47a593`; 13587 passed at `8a121008`)

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

## Review pass 2 (`f00c1d95..93e0bac4`)

- **P2.1 — reopening a blank-request marker item makes the marker eligible reviewer text** (severity not stated): three routes (reopen, target-only edit, retarget) opened a marker item. **Disposition:** fixed `7f3d64ed`, placement corrected by `a50964d2` — an item with `legacy_source` and the marker request cannot be reopened, target-edited or retargeted (named error, bytes unchanged); a real-text edit is the exit; reviewer-written items with the same sentence reopen normally (asserted); mutation-verified.
- **P2.2 — legacy migration re-parses the target artifact per row** (severity not stated): incomplete P1.14 sweep. **Disposition:** fixed `96fdb5c2` — shared `parsed` cache; parse count equal for one row and five.
- **P2.3 — `legacy_source` does not identify a row when an id repeats within one artifact** (low): needs a hand-edited artifact past `check_feedback_integrity`. **Disposition:** fixed (documentation) `572af8b7` — sentence narrowed; storing row position declined.

## Review pass 3 (`93e0bac4..8a2b455d`; all seeded by the `7f3d64ed` schema-level placement)

- **P3.1 — the invariant keys on text equality: a legacy row whose own words are the marker sentence blocks migration** (probed): **Disposition:** fixed `a50964d2` — rule lives only at the two opening actions; `test_a_legacy_row_whose_own_words_are_the_marker_sentence_migrates_as_an_ordinary_open_item`. Residual: refused on reopen once closed; a text-supplying edit clears it.
- **P3.2 — as a model validator, a hand-edited ledger becomes unloadable** (by read): **Disposition:** fixed `a50964d2` — `test_a_marker_item_hand_edited_to_open_still_loads_and_the_named_exit_still_runs`; the guard covers tool actions, not hand edits.
- **P3.3 — refusals reach the CLI as a raw pydantic dump** (by read): **Disposition:** fixed `a50964d2` — a `RoadmapFeedbackLedgerError` naming the item id, no validation residue, bytes unchanged.

Pass 3 was the "auditing your own edits" pattern: the schema placement was the wrong shape, so the remedy was the local shape at both actions, not a schema patch.

## Review pass 4 (`8a2b455d..cd4a3c4a`)

- **P4.1 — the guard refuses only the exact marker sentence, so a whitespace-only edit opens a marker item** (low): **Disposition:** fixed `507660d6` — uses migration's predicate `not request.strip()`; `test_an_edit_that_supplies_only_whitespace_cannot_open_a_blank_request_marker_item`. The pre-existing whitespace-only reviewer request looseness is tracked in `BUG_BACKLOG.md` ("The feedback ledger accepts a whitespace-only reviewer request"), `1693e4ae` (tightening `_requires_request` would change parse-time loading).

## Review pass 5 (`cd4a3c4a..54521e4f`)

- **P5.1 — the whitespace clause fires for every migrated item and its message misdescribes one with real text** (low): **Disposition:** fixed `8e978039` — message names the missing text and rule; docs say any migrated item; behavior unchanged.
- **P5.2 — the test pins the whitespace refusal only on the marker item** (low): **Disposition:** fixed `8e978039` — `test_a_blank_edit_cannot_open_any_migrated_item_and_refuses_with_the_named_error`, mutation-verified against the narrowing the pass describes.

## Out-of-range / recall-mode findings

_(none)_

## Filed in backlog

- **#427** — 96 step-detail test names with no matching test; absorbs F2, F14 and the citation gaps.
- **#428** — proposal current-or-stale status defined but never computed from `ProposalFields.candidate_version_id`.
- **#429** — `plan_tool/roadmap_revision_run.py` is CLI-unreachable but still emits `RoadmapLocalRevisionPreflight`; retiring it is outside this plan.
- **#395** — narrowed to the selector-era lineage (#394 removed). **`BUG_BACKLOG.md`** — whitespace-only reviewer request (`1693e4ae`).
- #428 and #429 were filed as #425 and #426 (still so in older commits, e.g. `9a4d34a2`) and renumbered at the `main` merge.

## Convergence status

Converged at the low-yield level; the plan is closed. Pass 1: 3 high / 3 medium / 4 low + 5 below-cap. Pass 2: 3 findings (P2.1 broke a stated invariant, material, reset the streak). Pass 3: 3 findings, all seeded by the pass 2 fix, two regressions (still material). Pass 4: 1 low, not a regression. Pass 5: 2 low, both about the pass 4 change. Passes 4 and 5 are two consecutive low-yield passes against the latest logic-changing commit `507660d6`: low-yield convergence, not a clean audit; advisory findings are retained above. Sweeps 1 and 2 are triaged and every true finding is fixed and mutation-verified. Follow-ups: #427, #428, #429, #395.

Final full suite: **13601 passed / 190 skipped, 0 failures at `8e978039`**. Earlier: 13367 run head; 13406 `cd2f0532`; 13439 `f4d4adb1`; 13455 `eaa4d8ca`; 13463 `4cd8acdf`; 13526 `868a89eb`; 13587 `8a121008`; 13593 pass 2 fixes; 13595 `a50964d2`; 13597 `507660d6`.
