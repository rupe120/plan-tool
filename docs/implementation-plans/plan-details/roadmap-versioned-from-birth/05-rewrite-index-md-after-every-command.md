# Step 5 — Rewrite INDEX.md after every version-store change

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds one best-effort wrapper, `refresh_roadmap_index`, in `plan_tool/roadmap.py`. It calls step 4's renderer and write function and turns any failure into a warning. The step then calls the wrapper right after each successful `publish_roadmap_generation` that changes the version store or accepted head. The call sites are the root publish, candidate storage and admission, terminal resolution, supersession, pointer release, review replacement, promotion, and enrolled decision settlement. The stage command's post-head refusal path calls it too. The key decision is that the index is written after the publish and never inside the pending generation, so a failed index write cannot roll back or block a commit. On green, `INDEX.md` matches the store after every committing command, and a broken index write leaves the command's result and exit code unchanged.

## Table of Contents

- [Why](#why) — what goes stale without a refresh
- [Input](#input) — what steps 3 and 4 supply
- [Files (creates vs edits)](#files-creates-vs-edits) — the files edited
- [Implementation](#implementation) — wrapper, commit-point inventory, constraints
- [Tests](#tests) — cases per behavior and invariant
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left to other steps

## Why

- Step 4 builds the renderer, and nothing calls it yet. Without call sites, `INDEX.md` never exists or goes stale after the first version change.
- The status of a version comes from several records (head, admission pointer, terminal resolutions, supersessions). Each command that writes one of them can change the answer.
- The index is a human aid that no command reads (plan intent, step 1's record on `BACKLOG.md` #441). It must never be able to fail a command whose version-store commit already succeeded.
- This step owns every `INDEX.md` call, so one reviewer can check the full call list in one place.

## Input

- **Step 4 output:** `plan_tool/roadmap_index.py` with a render function and a write function for `<roadmap folder>/INDEX.md`. Use its names as landed; the landed names win over any name in this detail. The write replaces the whole file each time.
- **Step 3 output:** the stage run in `plan_tool/roadmap.py` that publishes the root version with the accepted head written last, and refuses once a head exists.
- **Existing commit points:** each calls `publish_roadmap_generation` from `plan_tool/roadmap_revision_publish.py`.
  - `plan_tool/roadmap_candidate_run.py`: `_store_batch_candidate`, `_store_candidate`, and the terminal-resolution and pointer-release generations (`build_terminal_resolution_generation`, `build_active_candidate_pointer_release_generation`).
  - `plan_tool/roadmap_candidate_review.py`: `_store_active_structural_replacement`, `_release_active_candidate`, `_store_replacement`, `_store_batch_replacement`, and the publish in `_stored_result` that backs sealing.
  - `plan_tool/roadmap_version_promotion.py`: `promote_review_seal`.
  - `plan_tool/roadmap_decision_settlement_enrolled.py`: `run_enrolled_decision_settlement`.
- **Limit:** the tests use canned stores and canned model replies. They cannot prove that an index rendered after a real multi-command session reads well. They only prove that the call happens after each commit and never blocks it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — add `refresh_roadmap_index(plans_dir, slug)` and call it after the root publish and on the post-head refusal path.
  - `plan_tool/roadmap_candidate_run.py` — call the wrapper after each successful publish at the commit points above.
  - `plan_tool/roadmap_candidate_review.py` — same, at the review commit points above.
  - `plan_tool/roadmap_version_promotion.py` — same, after the promotion publish in `promote_review_seal`.
  - `plan_tool/roadmap_decision_settlement_enrolled.py` — same, after the settlement publish.
  - `tests/test_roadmap_candidate_run.py` — add the candidate-side cases.
  - `tests/test_roadmap_version_promotion.py` — add the promotion-side cases.
- **Addition to flag:** the review, settlement, and `roadmap.py` call sites have no test file in the declared set. Cover them in the two declared test files through their public entry points, or add a case to a sibling test file and note the addition.

## Implementation

**Behavior that must hold when the step is done:**

- **One wrapper owns the failure policy.** `refresh_roadmap_index` renders and writes the index. It catches every `Exception` from step 4's functions, emits one warning line naming the folder and the error, and returns. It never raises, never changes a return code, and never touches the version store.
- **Written after the publish, never inside it.** The call comes after `publish_roadmap_generation` returns. The index is not a generation member, so no crash recovery or pending-generation journal ever mentions it.
- **No rollback.** A failed index write leaves the committed version, head, or record in place. The next committing command rewrites the file whole.
- **Whole-file replace every time.** The wrapper never reads the old `INDEX.md` or patches it.
- **Every committing path calls it once.** This includes paths that commit nothing new but change what the index must say: the post-head stage refusal (step 3 refuses once a head exists) refreshes the index and then refuses as before. The `already-promoted` result in `promote_review_seal` also refreshes, because an earlier run may have died after the publish and before the index write.

**Recommended approach:**

- **Home of the wrapper.** Put it in `plan_tool/roadmap.py`. `roadmap_candidate_run.py` and `roadmap_candidate_review.py` already import `plan_tool.roadmap`, and `roadmap.py` cannot import them back, so one definition in `roadmap.py` reaches every call site without a new import edge. A second copy in another module would trip `tests/test_duplication.py`.
- **Warning channel.** Follow the existing convention for non-fatal notes in these modules, such as a `run_logger` event where one is in scope, or a single stderr line otherwise. The orchestrator docstring says `roadmap.py` prints no operator summary, so keep the line to the warning only.
- **Locking.** Call the wrapper while the writer guard is still held where the call site already holds it, so two commands cannot interleave writes. Where the guard is released before the function returns, call it just before release. The wrapper takes no guard of its own.

**Call-site inventory (the checklist to enumerate before editing):**

- Class: "a command commits a version-store change and must refresh the index." Search by identifier (`publish_roadmap_generation(`, `recover_roadmap_publication`) and by vocabulary ("terminal resolution", "supersession", "release", "pointer", "admission").
- Apply at each hit listed under Input, or say per site why it stays. A hit that only reads, such as `load_stored_candidate_proposal`, stays untouched.
- A recovery call that completes a dangling publish counts as a commit point. Refresh after it succeeds.

**Constraints (not free to vary):**

- **Do not change any contract.** No change to candidate, seal, promotion, or version-record content, and no new field recorded for the index.
- **No timestamps** in anything this step writes.
- **No reads of `INDEX.md`** anywhere. Step 11's guard checks that.

## Tests

Candidate-side cases go in `tests/test_roadmap_candidate_run.py` and promotion-side cases in `tests/test_roadmap_version_promotion.py`. Both reuse the existing store builders (`_store_stack`, `_run_batch`, `_approve_structural_candidate`).

- `test_index_exists_and_lists_the_candidate_after_storing_a_proposal` — a stored candidate appears in `INDEX.md` with its status.
- `test_index_status_changes_after_terminal_resolution` — rejecting or settling a candidate updates its listed status.
- `test_index_marks_superseded_candidate_after_replacement` — a replacement run rewrites the file with the supersession shown.
- `test_index_shows_new_head_after_promotion` — `promote_review_seal` leaves `INDEX.md` naming the promoted version as the accepted head.
- `test_already_promoted_result_still_refreshes_the_index` — the `already-promoted` path rewrites the index, so a crash between publish and index write heals on retry.
- `test_index_write_failure_warns_and_never_fails_the_command` — with the write function patched to raise, each commit path returns its normal result and rc and emits one warning.
- `test_failed_index_write_never_rolls_back_the_committed_version` — after the patched failure, the version, head, and records are all present and `load_accepted_version` still works.
- `test_index_is_replaced_whole_not_patched` — pre-seed `INDEX.md` with junk, run a commit, and assert the file equals the fresh render.
- `test_post_head_stage_refusal_refreshes_the_index` — the stage refusal after a head exists still refuses with the named error and also leaves a current index.
- `test_index_is_not_a_generation_member` — the pending-generation journal for a publish names no `INDEX.md` path, so crash recovery never replays or deletes it.
- `test_every_publish_call_site_is_followed_by_the_wrapper` — a source scan that every `publish_roadmap_generation(` in the five production modules has a wrapper call in the same function. The five are the four step-5 production files plus `plan_tool/roadmap.py`. This pins the sweep so a new commit point fails loudly.

### Tests for this step

- All cases above must be green before the step is finished.
- Each case covers a behavior this step adds: the call after commit, the failure policy, or the whole-file replace. Do not pad the roster.
- Run `uv run pytest tests/test_roadmap_candidate_run.py tests/test_roadmap_version_promotion.py tests/test_duplication.py -q`, then the full suite with `-n auto`. Expect existing tests that pin "no `INDEX.md` in the folder" to need an update.

## Acceptance criteria

- After a root publish, a candidate store, a terminal resolution, a supersession, a pointer release, a replacement, a promotion, and an enrolled settlement, `INDEX.md` equals step 4's render of the current store.
- A raised error inside step 4's write leaves every command's return value and exit code unchanged and prints exactly one warning.
- `rg -n 'publish_roadmap_generation\(' plan_tool/roadmap.py plan_tool/roadmap_candidate_run.py plan_tool/roadmap_candidate_review.py plan_tool/roadmap_version_promotion.py plan_tool/roadmap_decision_settlement_enrolled.py` lists only calls that are paired with the wrapper in the same function.
- `refresh_roadmap_index` is defined once, in `plan_tool/roadmap.py`, and `tests/test_duplication.py` stays at zero groups.
- No production code reads `INDEX.md`.

## References

- `BACKLOG.md` #441 — source entry, scope contract, and step 1's route inventory.
- `plan_tool/roadmap_index.py` (step 4) — the render and write functions this step calls.
- `plan_tool/roadmap_revision_publish.py` — `publish_roadmap_generation`, `recover_roadmap_publication`, and the writer guard.
- `ROADMAP_FORMAT.md` § "Immutable candidate-version authority" — what the head and records mean.

## Applicable guardrails

- **The plan's "## Out of scope", contract changes:** this step only adds calls. It must not alter the candidate, seal, promotion, or version-record content, and it must not add a field for the index.
- **The plan's "## Out of scope", timestamps:** neither the wrapper nor its warning may carry a date or timestamp.
- **The plan's "## Out of scope", top-level mirror:** `INDEX.md` is a generated index, not a copy of artifact content. The wrapper must not write artifact text anywhere outside the version store.
- **Step intent:** a failed index write must never fail the command. That is why the call sits after the publish and why the wrapper swallows errors.

## Deferred

- The guard that no production code reads `INDEX.md` — owned by the plan's guard step (step 11), not here.
- Operator documentation of `INDEX.md` — owned by the plan's docs step.
- Consolidating the many `publish_roadmap_generation` call shapes into one commit helper — a cross-module refactor `detail` cannot mint. File it on `BACKLOG.md` if it recurs.
- Any command that reads `INDEX.md` or depends on its content — out of scope by the plan's intent.
