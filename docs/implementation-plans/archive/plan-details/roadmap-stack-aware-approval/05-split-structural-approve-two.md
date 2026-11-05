> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Split structural approve into two invocations bound by the stack digest

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step splits `--decide-candidate ID --candidate-decision approve` into two invocations. Without the new `--confirm-stack-digest DIGEST` flag, the command prints step 4's stack printout and the digest, writes nothing, and exits 2. With the flag, the library recomputes the digest under the writer guard that publishes the seal. It seals only on an exact match, and the CLI then promotes the returned seal as it does today.

- **`plan_tool/roadmap_candidate_review.py`:** `decide_structural_candidate` gains a keyword-only `confirm_digest`. Approve without it refuses, so the approval seal keeps one construction site.
- **`plan_tool/cli/roadmap_cmd.py`:** gains the flag, its conflict rules, and the split handler.
- **`docs/cli/roadmap.md`:** regenerated, not hand-edited.

The key decisions:
- The digest comparison lives only in the library, under the writer guard.
- The unconfirmed invocation never calls the library and never takes a guard.
- An unconfirmed approve exits 2, never 0.

On green, the first invocation over a real C1-structural / C2-presentation-only stack changes nothing on disk and prints a digest. The second invocation, given that digest, promotes C2. A differing digest seals nothing.

## Table of Contents

- [Summary](#summary) — what the step does and the key decisions
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — the single-command approve and what it leaves unbound
- [Input](#input) — the steps 2–4 outputs and stored facts this step reads, and what its tests cannot show
- [Files (creates vs edits)](#files-creates-vs-edits) — the declared files, two of them mechanical test additions
- [Implementation](#implementation) — the two-invocation contract, per-outcome table, approach, rejected alternatives, constraints, and site sweep
- [Tests](#tests) — test roster, existing tests that must change, mutation checks, and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the plan and the modules involved
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work other steps own, and what is deliberately not built

## Why

The approve path is one command today. `_cmd_roadmap_structural_candidate_decision` in `plan_tool/cli/roadmap_cmd.py` prints the disclosure, calls `decide_structural_candidate`, and then calls `_cmd_roadmap_promote_review_seal_id`. The approve arm of `decide_structural_candidate` publishes the seal with no binding to what the operator was shown. Two tests pin that shape: `test_structural_candidate_approval_discloses_then_promotes_the_exact_seal` in `tests/cli/test_roadmap_cmd.py` and `test_structural_approval_seals_the_displayed_initial_candidate_without_a_question` in `tests/test_roadmap_candidate_review.py`.

Steps 2 and 3 make a presentation-only top of a structural stack approvable and promotable. Step 4 supplies the whole-stack view. Without this step, an operator still approves a stack they never had to look at first. No `confirm_digest`, `confirm_stack_digest`, or `--confirm-stack-digest` symbol exists in `plan_tool/`, `tests/`, or `docs/cli/` at HEAD, so none of this work is done.

## Input

- **Step 4's stack view, digest, and printout.**
  - **Names.** Step 4 recommends `CandidateStackView` with a `digest` property, `build_candidate_stack_view(plans_dir, slug, candidate)` in `plan_tool/roadmap_candidate_review.py`, and one printout function in `plan_tool/cli/roadmap_cmd.py`. Read the landed names off those modules. The landed names win over any name in this file.
  - **Builder contract.** It rebuilds every hop from stored records and refuses with `CandidateReviewError` when the stack is underivable or has no recorded root. It never judges eligibility, takes no guard, and writes nothing.
  - **Printout contract.** It renders the stack and delegates the top candidate to `_render_structural_candidate_disclosure`. It does not print the digest. Printing the digest is this step's job.
- **Step 2's guards.** `_require_structural_candidate` and `_require_active_structural_candidate` are stack-aware. The CLI precheck in `_cmd_roadmap_structural_candidate_decision` asks the stack derivation and refuses with status 2 before any output. Step 2 adds a helper in `tests/cli/test_roadmap_cmd.py` that stubs the derivation. Read its landed name.
- **Step 3's promotion boundary.** A structural stack promotes only under a `structural-approval` seal on its top candidate. This step does not change the seal record or `promote_review_seal`.
- **Current approve arm.** Inside `roadmap_writer_guard` it does these things in order:
  - it loads the admitted candidate with `_load_admitted_initial_candidate`;
  - it runs `_require_structural_candidate`;
  - it builds the seal with `_new_structural_approval_seal`;
  - if the seal file already exists, it returns the stored seal;
  - otherwise it publishes the seal with an active-candidate recheck at `before_replace`.
- **`roadmap_writer_guard` writes.** It creates the lock file (`os.O_CREAT`) and its parent directory. An invocation that "writes nothing" must therefore not take it. `roadmap_reader_guard` (`plan_tool/roadmap_revision_publish.py`) creates nothing but raises `RoadmapWriterGuardError` when no lock exists yet.
- **Option plumbing.**
  - `_TrackExclusiveOption` records every occurrence as `_<dest>_occurrences`.
  - `_option_occurrences` returns `()` only when the value is `None`, so an empty string is a present value.
  - `_has_candidate_lifecycle_action` lists the lifecycle option names. Every exclusive-mode conflict predicate (comparison, enrollment, escalation, rewrite, reopen, restore, settlement) reads it.
  - `_candidate_lifecycle_has_conflict` enforces one action with no companions.
- **Exit-code precedent.** A missing confirmation is already a status-2 pre-flight refusal:
  - settlement's `confirmation-required` maps to `preflight-rejected`, status 2, in `_STATUS_BY_OUTCOME` of `plan_tool/roadmap_decision_settlement_run.py`;
  - `--confirm-feedback-reopen` maps the same way in `_reopen_result`.
  - Both existing confirm flags are booleans. This one carries a value.
- **A pinned help string.** `tests/cli/test_cli_reference.py` asserts that the generated reference contains `one structural candidate choice: approve, edit, or reject`. The `--candidate-decision` help must keep that phrase.
- **Limit of this step's tests.** They show that a digest printed by one invocation is the only value the second accepts, and that nothing is written before it. They cannot show that an operator reads the printout. The digest proves the supplied value equals the one the tool recomputes for the stack, and nothing more.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only), declared for this step:**
  - `plan_tool/roadmap_candidate_review.py`:
    - `decide_structural_candidate` gains keyword-only `confirm_digest: str | None = None` and the approve-arm compare.
    - It also gains two refusals: approve without a digest, and edit or reject with one.
    - Two private message constants let tests tell the two digest refusals from every other refusal.
  - `plan_tool/cli/roadmap_cmd.py`:
    - `_cmd_roadmap_structural_candidate_decision` splits the approve branch.
    - Register `--confirm-stack-digest` and add `_confirm_stack_digest_occurrences=()` to `set_defaults`.
    - Add `"confirm_stack_digest"` to `_has_candidate_lifecycle_action`.
    - Add the flag clauses to `_candidate_lifecycle_has_conflict`.
    - Add a small renderer for the unconfirmed result.
    - Import `build_candidate_stack_view` by name so tests can stub it here.
    - Extend the help of `--decide-candidate` and `--candidate-decision`.
  - `docs/cli/roadmap.md`: regenerate with `uv run python -m plan_tool.cli_reference --write`. Do not edit by hand.
  - `tests/test_roadmap_candidate_review.py` and `tests/cli/test_roadmap_cmd.py`: new tests, updates to existing approve tests, and `_ns` gains `confirm_stack_digest=None` and `_confirm_stack_digest_occurrences=()`.
- **Two mechanical test files, each forced by the new required digest:**
  - `tests/test_roadmap_candidate_run.py`: one helper beside `_run_batch`, and the one approve call in the batch-block test that reaches an approved-not-promoted state.
  - `tests/test_roadmap_version_promotion.py`: every approve call that builds a seal for a promotion test.
  - Each existing approve call there asserts `stored` and a seal. It turns red without a digest, so leaving these files out would break the suite.

## Implementation

**Behavior to deliver.**
- **Unconfirmed approve.** With no `--confirm-stack-digest`, the command prints step 4's printout for the candidate's whole stack, then a `stack digest:` line, then the pending-confirmation result. It writes nothing. It calls no library decision, takes no guard, and exits 2.
- **Confirmed approve.** With the flag, the command prints the same printout and digest line, then calls `decide_structural_candidate(..., confirm_digest=<value>)`. The library recomputes the digest and seals only on an exact match. A stored seal is then promoted through the existing `_cmd_roadmap_promote_review_seal_id`.
- **One seal construction site.** `decide_structural_candidate(approve)` with `confirm_digest=None` returns `refused` before any guard is taken. No library path seals without a digest.
- **Digest confirms approve only.** `decide_structural_candidate` with edit or reject and a `confirm_digest` returns `refused` with no write. The CLI rejects that combination first, so this check guards direct library callers.

**Per-value contract for `--confirm-stack-digest`.**
- **Producer.** The `stack digest:` line that either approve invocation prints, from step 4's `view.digest`. Nothing stores the value.
- **Form.** The 64-character lowercase hex string exactly as printed. The comparison is exact string equality. It must not trim, case-fold, or match a prefix. A differently cased copy refuses.
- **Absent versus empty.** An absent flag (`None`) is the unconfirmed invocation. A present flag, including an empty string, is a confirmed invocation and refuses when it differs. The code must test `is None`, never truthiness.
- **Consumer.** Only the library approve arm compares it. The CLI passes the operator's value through unchanged and must never substitute the digest it just computed. On the confirmed invocation, the printed digest is informational. The library's recompute is the only comparison.
- **Precedence, first to last:**
  1. The conflict predicate: any misuse of the flag exits 2 before any path is resolved or disk is read.
  2. The CLI precheck, from step 2.
  3. The CLI's stack-view build, from step 4.
  4. The printout and the `stack digest:` line.
  5. Flag absent: stop with the pending-confirmation result.
  6. Library, before any guard: the digest-absent and digest-with-edit-or-reject refusals.
  7. Library, under `roadmap_writer_guard`: the admitted-candidate load, then `_require_structural_candidate`, then the digest recompute and compare.
  8. Library: the stored-seal early return, otherwise publish with the active-candidate recheck.
  9. CLI: promotion.

**Per-outcome contract.**

| Invocation | Situation | Writes | Key output | Exit |
| --- | --- | --- | --- | --- |
| Any | Flag misuse (see Constraints) | none | the existing lifecycle conflict `error(...)` | 2 |
| Any | Precheck refusal | none | `error(...)`, no printout | 2 |
| Any | Stack view cannot be built | none | `error(...)`, no printout | 2 |
| Unconfirmed | Eligible candidate | none | printout, `stack digest: D`, `structural decision: approve confirmation-required`, a `reason:` naming `--confirm-stack-digest D` | 2 |
| Confirmed | Library `refused` (differing digest, candidate no longer active, guard refusal) | none | printout, digest line, `structural decision: approve refused`, `reason:` | 2 |
| Confirmed | Library `failed` | none | the existing decision-result lines | 1 |
| Confirmed | Seal stored, promotion succeeds | seal and promotion | `structural decision: approve stored`, `review seal:`, `promoted version:` | 0 |
| Confirmed | Seal stored, promotion refused | seal only | the existing promotion error | existing (2, or 1 for `OSError`) |
| Any | Ctrl-C | none new | `interrupted` | 130 (existing) |

- **Unconfirmed approve never exits 0.** Automation can read exit 0 from this command as "approved". The status matches the confirmation precedent in the Input section. Result lines, not the exit code, tell "confirmation required" from "digest differs".
- **Retry after a partial confirm.** A seal stored but not promoted is not lost while its candidate is still the active one. Re-running with the same digest hits the stored-seal return behind the digest check and promotes. `--promote-review-seal` is unchanged and also works.

**Approach.** One way to do it:
- **Library.**
  - Put the two early refusals beside the existing "structural decision is unknown" check.
  - In the approve arm, after `_require_structural_candidate` and before `_new_structural_approval_seal`, rebuild the view with `build_candidate_stack_view(plans_dir=..., slug=..., candidate=candidate)`.
  - Raise `CandidateReviewError` (already mapped to `refused`) when `view.digest != confirm_digest`.
  - Give the absent-digest and mismatch refusals distinct private constants.
- **CLI.**
  - In `_cmd_roadmap_structural_candidate_decision`, keep the precheck as it is, then branch once on `decision == "approve"`.
  - Approve builds the view (`except (ValueError, OSError)` gives `error(...)` and status 2), prints step 4's printout and the digest line, and either stops or calls the library.
  - The non-approve branch keeps today's `_render_structural_candidate_disclosure` call unchanged. Step 6 replaces it. Keep the split as one `if` so step 6's edit touches only the other branch.
  - Reuse `_render_structural_candidate_decision_result` for the confirmed outcomes. Add one small renderer for the unconfirmed result.
- **Conflict predicate.**
  - Read `_option_occurrences(args, "confirm_stack_digest")`.
  - Conflict when it appears more than once.
  - Conflict when it appears without `--decide-candidate` and `--candidate-decision approve`.
  - A stray flag on its own is already caught by the existing "exactly one selected action" clause. Adding it to `_has_candidate_lifecycle_action` is what routes it to that clause.
- **Registration.** Register the flag after `--candidate-correction` with `_TrackExclusiveOption`, `default=None`, and `metavar="DIGEST"`. Its help states that it is valid only with the approve pair, needed exactly once, refuses with no write when it differs from the recomputed digest, and that `-y` is not confirmation.
- **Regenerate.** Run the generator once the help text is final.

**Rejected alternatives.**
- **Compare in the CLI before the guard.** A CLI compare leaves a window before the seal publishes and adds a second compare site. The plan puts the recompute under the seal's writer guard.
- **A `confirmation-required` member on `CandidateReviewOutcome`.** The unconfirmed invocation never calls the library, so it needs no library outcome. Widening the closed vocabulary would touch `_result_return_code` and every consumer.
- **A digest-optional library approve.** It leaves two ways to build the seal, which the plan's binary observable rules out.
- **A separate read-only library function for the unconfirmed view.** The CLI already loads the candidate and calls step 4's builder, so a new function would have no caller beyond the CLI.
- **Guards on the unconfirmed invocation.** The writer guard creates a lock file. The reader guard refuses when no lock exists. The printed digest is only ever compared under the writer guard, so a guard here buys nothing.
- **Exit 0 or exit 1 for the unconfirmed invocation.** Exit 0 reads as approval to automation. Exit 1 departs from the two existing confirmation refusals.
- **Persisting the digest or a confirmation receipt.** The plan makes the digest stateless.
- **Normalizing the digest before comparing.** That adds behavior nothing needs. The printed value is what an operator pastes.

**Constraints (not free to vary).**
- **Nothing written before a match.** The unconfirmed invocation and every refusal before the seal publishes must leave the tree byte-identical. No lock file, run log, seal, pointer, or head change.
- **Recompute under the guard.** The library must rebuild the view from stored records inside the writer guard, after the eligibility guards and before the stored-seal return. It must not accept a view or digest from the caller.
- **Eligibility before digest.** A candidate that is not active or not eligible is refused for that reason, never as a digest mismatch.
- **The CLI passes the operator's value through.** It must not compare, trim, or replace it.
- **Presence is `is None`.**
- **Flag misuse exits 2 before any side effect.** Misuse means:
  - the flag with edit or reject;
  - the flag twice;
  - the flag with `-y` or any other companion;
  - the flag alone.
- **`-y` is not confirmation.**
- **The seal record and `promote_review_seal` are unchanged.** No digest field is added to any stored record.
- **The printout is step 4's, unchanged.** Both invocations render the same function. The `stack digest:` line is printed beside it, not inside it.

**Foundational logic and the sites.** The logic is "an approval seals only the stack whose digest the operator supplied". A sweep by identifier (`decide_structural_candidate`, `_new_structural_approval_seal`, `"structural-approval"`, `_cmd_roadmap_promote_review_seal_id`) and by vocabulary (approve, confirm, seal, digest, disclose) gives these sites.
- **Changed here:**
  - the approve arm and signature of `decide_structural_candidate`;
  - `_cmd_roadmap_structural_candidate_decision`;
  - `_has_candidate_lifecycle_action` and `_candidate_lifecycle_has_conflict`, whose one edit covers every sibling exclusive-mode predicate;
  - the parser registration and the two help strings.
- **In-repo callers of `decide_structural_candidate(..., "approve", ...)`.** Re-run `rg 'decide_structural_candidate\(' plan_tool tests` when implementing, because steps 1–4 add sites. At HEAD, callers exist in `tests/test_roadmap_candidate_review.py`, `tests/test_roadmap_candidate_run.py`, and `tests/test_roadmap_version_promotion.py`. Every approve call is updated here.
- **Stay unchanged, deliberately:**
  - `_new_structural_approval_seal` and `CandidateReviewSeal`;
  - `promote_review_seal`, the promotion writer, and recovery (step 3's);
  - `_render_structural_candidate_disclosure`;
  - `--promote-review-seal`: a seal can exist only after a matching confirm, so promoting one needs no digest;
  - edit sourcing and reject and discard pointer release.
- **Owned by other steps:** step 6 owns the printout on edit and reject and on the proposal output. Step 7 owns the end-to-end property across routes and the batch block's removal. Step 8 owns docs.

**Interim reachability.** Between this step and step 7, the stacked shape is reachable only through a test helper. Every structural approval, stacked or not, is now two invocations.

## Tests

Library cases go in `tests/test_roadmap_candidate_review.py`. CLI cases go in `tests/cli/test_roadmap_cmd.py`.

**Builders.**
- **Real stacks.** Reuse step 1's masking helper for C1-structural / C2-presentation-only, imported the way these modules import `_run_batch`.
- **A digest of a different stack.** Build C1's view with `build_candidate_stack_view` to get a valid but wrong digest for C2.
- **Approve helper.** Add `_approve_structural_candidate(plans_dir, candidate)` beside `_run_batch` in `tests/test_roadmap_candidate_run.py`. It builds the view, then calls `decide_structural_candidate(..., "approve", confirm_digest=view.digest)`. Use it for every approve that is setup, not the subject.
- **CLI stand-ins.** In unit-level CLI cases, stub `roadmap_cmd.build_candidate_stack_view` to return an object with a fixed 64-hex `digest`. Stub step 4's printout with a recorder. Hand-built hops need not be digestible.

**Library cases.**
- `test_structural_approve_without_a_digest_refuses_and_writes_nothing` — `confirm_digest=None` returns `refused`, no seal, tree unchanged, and `roadmap_writer_guard` never entered. This pins that the library has no unconfirmed path.
- `test_structural_approve_with_the_matching_digest_seals_the_top_candidate` — over one structural hop, the seal has decision `structural-approval` and binds the candidate id.
- `test_structural_approve_of_a_presentation_only_top_confirms_against_the_whole_stack_digest` — over C1-structural / C2-presentation, C2's own digest seals C2, and C1's digest refuses.
- `test_structural_approve_with_a_differing_digest_refuses_with_no_write` — parametrized: one flipped character, the digest of another stack, an empty string, the correct digest in uppercase, and the correct digest with padding. Each returns `refused`, no seal, tree and pointer unchanged. The uppercase and padded cases pin that the digest is deliberately not normalized.
- `test_digest_is_recomputed_from_stored_records_under_the_writer_guard_not_taken_from_the_caller` — a builder wrapper records that the writer guard is held when it runs. A second run with the builder returning a view whose hop differs refuses the old digest.
- `test_ineligible_candidate_is_refused_for_its_own_reason_before_the_digest_is_compared` — rejected and superseded candidates given a wrong digest return their guard's refusal, not the mismatch constant.
- `test_reapproving_an_already_sealed_candidate_still_requires_the_matching_digest` — after a confirmed approve, the same digest returns the same stored seal (the retry path), and a wrong digest refuses. This pins that the stored-seal return sits behind the compare.
- `test_structural_edit_and_reject_refuse_a_digest_with_no_write` — a digest confirms an approval only.
- `test_structural_approval_seal_has_one_construction_site` — a source scan of `plan_tool/` finds `_new_structural_approval_seal(` exactly twice: its definition and its one call, in `decide_structural_candidate`.

**CLI cases (unit level).**
- `test_unconfirmed_structural_approve_prints_the_stack_and_digest_and_writes_nothing` — the printout is called once with the builder's view, `stack digest: <D>` and `structural decision: approve confirmation-required` appear, and the reason names `--confirm-stack-digest <D>`. `decide_structural_candidate`, `roadmap_writer_guard`, and promotion fail if called.
- `test_unconfirmed_structural_approve_never_exits_zero` — status 2 for an own-structural candidate and for a presentation-only top over a structural stack. Automation can read exit 0 as approval.
- `test_confirmed_structural_approve_prints_the_same_printout_then_seals_and_promotes_the_returned_seal` — replaces `test_structural_candidate_approval_discloses_then_promotes_the_exact_seal`. The order is printout, digest line, library decision, promotion, and the exit is 0.
- `test_confirmed_approve_passes_the_operators_digest_not_the_one_the_cli_computed` — the builder returns A, the operator supplies B, and the library receives B. A CLI that substituted `view.digest` would confirm anything.
- `test_empty_digest_is_a_present_confirm_that_reaches_the_library_not_an_absent_one` — `confirm_stack_digest=""` calls the library with `""`. It does not take the unconfirmed path.
- `test_stack_view_failure_refuses_before_any_output_and_any_decision` — a builder raising `CandidateReviewError` gives status 2, an error on stderr, no printout, and no decision call, both with and without the flag.
- `test_structural_precheck_refusal_precedes_the_stack_printout_for_both_invocations` — extends `test_structural_decision_refuses_an_ineligible_candidate_before_any_disclosure_or_decision` so approve runs with and without the flag.
- `test_confirm_flag_parses_as_a_tracked_value_option` — `_parse` yields `confirm_stack_digest` and `_confirm_stack_digest_occurrences` for one and for two uses.
- `test_roadmap_help_documents_the_confirm_flag_and_the_write_nothing_first_invocation` — `_roadmap_help()` names `--confirm-stack-digest` and its `DIGEST` metavar.
- **Extend `test_candidate_lifecycle_actions_reject_companion_modes_before_side_effects`** with rows for the flag: alone; with edit and a correction; with reject; with `--reject-candidate`; given twice; without `--candidate-decision`; with `--promote-review-seal`; with `-y`; with `--apply`.
- `test_confirm_flag_beside_a_sibling_exclusive_mode_is_rejected` — parametrized over compare, restore, settlement, reopen, and escalation. Each returns 2 with no dispatch. This pins the one-tuple sweep through `_has_candidate_lifecycle_action`.

**Real-orchestrator cases (`tests/cli/test_roadmap_cmd.py`).** Use the real C1-structural / C2-presentation stack, the `storefront` slug, `tmp_path / "plans"`, and the promotion tests' green-gates stub. Add both to the module docstring's list of deliberate real-orchestrator exceptions in the same edit.
- `test_unconfirmed_approve_over_a_real_stack_writes_nothing_and_its_digest_confirms_the_second_invocation` — the first invocation exits 2, prints both hop ids and a `stack digest:` line, and leaves the tree and the head unchanged. The second invocation passes the digest parsed from that output and exits 0. The head is C2, and the seal is `structural-approval` on C2. This pins the producer-to-consumer seam that neither stubbed layer shows.
- `test_confirmed_approve_with_a_differing_digest_over_a_real_stack_refuses_and_changes_nothing` — status 2, tree byte-identical.

**Existing tests that must change.** A red approve test is expected. Read each to decide whether it is the new subject or setup.
- **`tests/test_roadmap_candidate_review.py`:**
  - Every approve call passes the matching digest, including those step 2 adds.
  - In parametrized cases where approve must refuse for a named guard, pass the digest the builder yields for the stored candidate, or a well-formed dummy when it is not stored. Otherwise the case refuses for the missing digest and stays green for the wrong reason.
  - `test_structural_decision_refuses_candidate_evidence_changed_before_publication[approve]` must reach the publication recheck.
- **`tests/cli/test_roadmap_cmd.py`:** `test_structural_decision_results_remain_distinct_without_promotion` passes `confirm_stack_digest` on its approve rows and stubs the builder.
- **`tests/test_roadmap_candidate_run.py` and `tests/test_roadmap_version_promotion.py`:** every approve call goes through the helper. Reject and edit calls are untouched.

**Verify by mutation.** Break the code each of these ways and confirm each turns a test red:
- seal for any digest;
- take the digest from the caller instead of recomputing it;
- recompute outside the writer guard;
- move the stored-seal return above the compare;
- let `confirm_digest=None` reach the seal;
- have the CLI pass `view.digest` in place of the operator's value;
- call the library on the unconfirmed invocation;
- exit 0 when unconfirmed;
- treat an empty digest as absent;
- drop the flag from `_has_candidate_lifecycle_action`;
- accept the flag with edit or reject;
- print the printout after the library call;
- add a second `_new_structural_approval_seal(` call.

### Tests for this step

- **Tests added or changed.** About 9 library cases and about 12 CLI cases (two of them real-orchestrator), plus updates to the existing approve calls in four test files. They cover the two invocations, the per-outcome exits, the digest's producer-to-consumer seam, the recompute under the guard, the carve-outs (empty versus absent, no normalization, stored-seal retry), and the flag's conflict rules.
- **Green gate.** Every test above and the rest of the suite must be green before the step is done. The step's `test_command` is `uv run pytest tests/ -q -n auto`. The added tests also satisfy the plan's test-authoring gate. `tests/cli/test_cli_reference.py` must pass against the regenerated `docs/cli/roadmap.md`.

## Acceptance criteria

- **Unconfirmed approve.** Over a real stack, `--decide-candidate ID --candidate-decision approve` without the flag exits 2, prints every hop id and a `stack digest:` line, and leaves the plans directory byte-identical (no seal, pointer, head, or lock change).
- **Matching digest.** The same command with `--confirm-stack-digest <printed digest>` exits 0, stores one `structural-approval` seal on the top candidate, and promotes it.
- **Differing digest.** A differing, empty, re-cased, or padded digest exits 2 and changes nothing.
- **One construction site.** `decide_structural_candidate` with `confirm_digest=None` returns `refused` with no write. The source scan finds one call of `_new_structural_approval_seal(`.
- **Recompute under the guard.** The library rebuilds the digest from stored records inside `roadmap_writer_guard`, after the eligibility guards. The CLI never substitutes its own digest for the operator's.
- **Flag conflicts.** The flag with edit, reject, another action, a companion option, `-y`, or twice exits 2 before any path resolution.
- **Help and reference.** `docs/cli/roadmap.md` is regenerated. `git diff --name-only docs/cli` lists only that file. It carries the new flag and still contains `one structural candidate choice: approve, edit, or reject`.
- **No stored change.** `CandidateReviewSeal`, `promote_review_seal`, and the promotion writer are unchanged. No new persisted field exists.
- **Files.** `git diff --name-only` lists only the seven declared files; the diffs in `tests/test_roadmap_candidate_run.py` and `tests/test_roadmap_version_promotion.py` are limited to approve call sites and the helper.
- **Suite.** `uv run pytest tests/ -q -n auto` passes.

## References

- [docs/implementation-plans/2-roadmap-stack-aware-approval.md](../../2-roadmap-stack-aware-approval.md) — § "Architecture" owner decision 3 and § "Design decisions" (Digest) define the two invocations and the recompute under the guard.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/04-build-whole-stack-view-its-digest-its.md](04-build-whole-stack-view-its-digest-its.md) — the view, digest, and printout this step wires.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/02-make-review-side-guards-stack-aware.md](02-make-review-side-guards-stack-aware.md) — the stack-aware guards and CLI precheck this step keeps.
- [handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md](../../../../../handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md) — the P2.1 defect and the owner decisions.
- [plan_tool/roadmap_candidate_review.py](../../../../../plan_tool/roadmap_candidate_review.py) — `decide_structural_candidate` and `_new_structural_approval_seal`.
- [plan_tool/cli/roadmap_cmd.py](../../../../../plan_tool/cli/roadmap_cmd.py) — `_cmd_roadmap_structural_candidate_decision` and `_candidate_lifecycle_has_conflict`.
- [plan_tool/roadmap_decision_settlement_run.py](../../../../../plan_tool/roadmap_decision_settlement_run.py) — `_STATUS_BY_OUTCOME`, the confirmation exit precedent.
- [ROADMAP_FEEDBACK_FORMAT.md](../../../../../ROADMAP_FEEDBACK_FORMAT.md) — the feedback lifecycle and the batch stacking rule.

## Applicable guardrails

- **The plan's "Scope guardrails", binary observable.** The confirmed approve invocation is the seal's only construction site, and the digest match is checked at confirm time and not stored. The library refuses to seal without a digest, and no field or receipt is persisted.
- **The plan's "Scope guardrails", "Not allowed": no terminal prompt and no auto-approval.** The two invocations are the only confirmation mechanism. Nothing asks interactively, and `-y` is not confirmation.
- **The plan's "Scope guardrails", "Not allowed": no second gate, no per-hop approval, and no new persisted binding.** The digest covers the whole stack once. It is recomputed from stored records and compared, never stored.
- **The plan's "Scope guardrails", "Not allowed": no separate read-only show command.** The unconfirmed approve is the view. This step adds no other command.
- **The plan's "Scope guardrails", "Not allowed": no confirm step for edit or reject, and no stack output on other surfaces.** The flag is valid only with approve. The non-approve branch and every other renderer keep their current output.
- **The plan's "Scope guardrails", "Not allowed": no change to the promotion writer, the journal, recovery, or the stores.** This step edits none of them, and `--promote-review-seal` keeps its contract.
- **The plan's "Scope guardrails", ordering fence.** The batch block stays until step 7. This step lands the confirm step that its removal depends on.
- **The plan's "Out of scope", earlier single-command seals and run-log lifecycles.** An unpromoted earlier seal stays promotable while its candidate is still the active one. No run log is added to the decision commands.

## Deferred

- The stack printout on edit, on reject (with its note), and on the proposal output — step 6 owns them. This step leaves the non-approve branch on today's disclosure.
- Removing the batch block and the end-to-end property across the direct, answered, edited, and recovered routes — step 7 owns them. This step's real-stack tests pin the two-invocation contract only.
- Updating `docs/how-to/roadmap.md`, `ROADMAP_FEEDBACK_FORMAT.md`, `CAPABILITIES.md`, `README.md`, the pin in `tests/test_roadmap_feedback_format.py`, and the changelog for the two-invocation approve — step 8 owns them. Until then `docs/how-to/roadmap.md` still shows the single-command approve.
- A digest receipt or any stored confirmation — not built. The plan makes the digest stateless.
- A confirm step for edit or reject, and a separate show command — refused by the plan, not deferred. No backlog entry is filed.
- Normalizing or abbreviating the supplied digest — not built. The printed value is what an operator pastes, and an exact match is the whole contract.
- Run-log lifecycles for the decision commands — out of scope. The owner tracks them separately.
