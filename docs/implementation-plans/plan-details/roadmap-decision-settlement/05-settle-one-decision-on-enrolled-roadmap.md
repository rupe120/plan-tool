# Step 5 — Add the enrolled settlement runner `plan_tool/roadmap_decision_settlement_enrolled.py`: store the settled bytes as a new candidate version and swap the accepted head in one journaled `decision-settlement` generation

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds `plan_tool/roadmap_decision_settlement_enrolled.py` and its test file. It also adds one recognition branch, plus one kind constant, to `plan_tool/roadmap_revision_publish.py:_is_completed_version_owned_generation`. The new runner settles one decision on an enrolled roadmap under one writer lease. It runs the existing journal recovery, builds step 2's candidate, and refuses while an admitted candidate lineage is still unpromoted on the current head. It then stores the settled bytes as an ordinary `version_kind: "candidate"` record, built with `create_candidate_version`. That record carries a dedicated no-review sentinel and a settlement-owned `content_identity`. The runner runs the complete gate walk, commits step 3's receipt, and publishes the six version members plus the accepted-head swap as one `PendingGeneration` of the new `"decision-settlement"` kind. The key design decision is that settlement never goes through `promote_review_seal`. It reuses only that function's mechanics: the writer token, the journal, and a selector recheck inside the journal window. So no model-authored admission, evidence file, or seal is ever made up. On green, the accepted head names a new version that differs from its predecessor in exactly one status line, and a committed receipt names that version.

## Table of Contents

- [Why](#why) — why neither the un-enrolled writer nor seal promotion can settle an enrolled decision today
- [Input](#input) — the step 2–4 surfaces, the version store, the journal and recovery contracts, and the candidate admission this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the new runner and tests, the additive recovery branch, and the files that stay unchanged
- [Implementation](#implementation) — the public surface, refusals, run order, the settlement version, the generation and swap, the recovery branch, the exception mapping, and rejected alternatives
- [Tests](#tests) — named cases per area, which ones are green at HEAD, and the breaks each case must catch
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer can run
- [References](#references) — plan-level references that apply to this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this runner, and where breaking them is tempting
- [Deferred](#deferred) — work owned by step 6, step 7, or tracked backlog entries

## Why

At HEAD, no route changes an enrolled roadmap's canonical content except model-authored seal promotion:

- **Every legacy writer refuses an enrolled roadmap.** `plan_tool/roadmap_revision_publish.py:require_unenrolled_roadmap_writer` guards `publish_stage_artifact`, `publish_feedback_reopen_candidate`, and the other in-place writers. Step 4's runner therefore refuses an enrolled roadmap as `enrolled-roadmap-rejected`.
- **Seal promotion needs a full model-authored chain.** `plan_tool/roadmap_version_promotion.py:promote_review_seal` loads a seal and then walks `_load_complete_sealed_candidate`: the admission, the initial proposal plus its evidence file, the question inventory, the answer, the replacement binding, and the replacement evidence. `tests/test_roadmap_version_promotion.py::test_promotion_requires_one_complete_exact_review_seal_lineage` pins that. The only way to route a settlement through it would be to make up that whole chain, which the plan forbids.
- **Recovery recognizes only two version-owned shapes.** On an enrolled roadmap, `recover_roadmap_publication` drops a leftover journal only when `_is_completed_version_owned_generation` recognizes it: `"root-enrollment"` or a one-member `"review-seal-promotion"`. `tests/test_roadmap_revision_publish.py::test_version_owned_recovery_refuses_foreign_selector_generation` pins the refusal of any other selector-writing kind. A settlement generation interrupted after its last member would block the roadmap permanently unless recovery learns its shape.

Steps 2 and 3 already supply the enrolled preflight (read from `load_accepted_version`) and a receipt that records a `resulting_version_id`. What is missing is a runner that turns step 2's `settled_bytes` into an immutable version and moves the head to it without editing any stored version in place. Step 4 settles the un-enrolled lineage, and this step gives enrolled roadmaps the same outcome.

## Input

- **Step 2's preflight** (`plan_tool/roadmap_decision_settlement.py`): `resolve_decision_settlement_selector`, `build_decision_settlement_candidate`, `decision_settlement_candidate_is_current`, `DecisionSettlementRefusal.verdict`, and `DecisionSettlementCandidate`. On an enrolled roadmap the candidate carries these fields:
  - `accepted_version_id`, the head the source was read from;
  - `source_digest`, the stored member's digest;
  - `evidence_digest`;
  - `settled_bytes` and `settled_digest`.

  Its enrolled branch never reads a stage file or a baseline, and it never returns `source-not-admitted`.
- **Step 3's receipt** (`plan_tool/roadmap_decision_settlement_receipt.py`): `build_decision_settlement_receipt(candidate, *, resulting_version_id)`, `publish_decision_settlement_receipt(...)`, `DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES`, the outcome `Literal`, and `decision_settlement_receipt_proves_completion`. That read-back check proves an enrolled receipt only when `resulting_version_id` is on the head's predecessor chain, its record's predecessor matches, and its member digest equals `resulting_artifact_digest`. This step's version must satisfy all three.
- **Step 4's runner** (`plan_tool/roadmap_decision_settlement_run.py`): `DecisionSettlementRunResult`, `DecisionSettlementOutcome` (five outcomes), `DecisionSettlementRunRefusal`, and the names `confirmation-required`, `mode-rejected`, and `journal-unrecoverable`. Step 4's Deferred explicitly leaves reuse of its result type to this step.
- **Steps 2–4 have detail files but have not landed at HEAD.** Read every name off the landed modules. The landed names win over this file.
- **Version store** (`plan_tool/roadmap_versions.py`):
  - `load_accepted_version` returns the head's record, `brief_bytes`, and `artifact_bytes` in `VERSION_ARTIFACT_INVENTORY` order.
  - `create_candidate_version(*, roadmap_slug, predecessor_version_id, content_identity, review_lineage_identity, brief_digest, artifact_digests)` is pure. `StoredRoadmapVersion`'s validator requires all three candidate bindings to be non-null lowercase SHA-256 values.
  - `PreparedRoadmapVersion` checks that the content matches the record's digests.
  - `stored_version_members(prepared)` returns the record, the brief, and then the four artifacts.
  - `version_directory_path`, `accepted_head_path`, and `render_accepted_head` are also used.
  - `build_root_enrollment_generation` is the in-repo precedent for version members written before the selector, with a refusal whenever a member already exists.
- **Journal primitives** (`plan_tool/roadmap_revision_publish.py`):
  - `publish_roadmap_generation` checks the writer token and refuses when a journal already exists. It then writes the journal durably, runs `before_replace`, and writes the members **in list order**. If `before_replace` raises, it deletes the journal and re-raises.
  - `PendingGeneration.kind` is an open `str` (`plan_tool/roadmap_source_identity.py`), so a new kind needs no vocabulary change.
  - On an enrolled roadmap, `recover_roadmap_publication` drops the journal only when the generation is recognized **and** every member already holds its new bytes. It never writes a member. Anything else raises `RoadmapPublicationRecoveryError` and leaves the journal in place.
- **Seal promotion's swap** (`promote_review_seal`) is the mechanism to copy, not to call:
  - it reads the old selector bytes and requires them to name the accepted version (`_load_current_accepted_version`);
  - it publishes a selector member under the caller's writer token;
  - its `final_recheck` requires the selector to still name the predecessor.
- **Candidate admission** (`plan_tool/roadmap_candidate_run.py`):
  - `load_candidate_admission(*, plans_dir, slug)` returns `CandidateProposalAdmission | None` and raises `CandidateProposalError` for an unreadable admission.
  - The admission carries `predecessor_version_id` and `candidate_version_id` (`None` after a rejected response).
  - `run_initial_candidate_proposal` creates the admission under `roadmap_writer_guard`, and nothing deletes it.
  - Promotion changes only the selector: `tests/test_roadmap_version_promotion.py::test_promoted_head_keeps_the_fixed_roadmap_admission_terminal_without_an_extra_member` pins that the admission bytes stay the same. Moving the head past the admission's predecessor is therefore the whole observable effect of promoting that lineage.
- **Gate walk** (`plan_tool/roadmap_impact_snapshot.py:check_complete_roadmap_gates(evidence, *, stages)`):
  - It takes a `CompleteRoadmapGateEvidence` with keys, texts, parsed artifacts, digests, and `brief_bytes`.
  - It raises `RoadmapImpactSnapshotError` when those do not bind.
  - It is content-only.
  - Its evaluator always passes `predecessor=None`, so `check_settled_decisions` is a no-op here. This step must not claim otherwise.
- **The evidence loaders fail closed on a version with no evidence file.** `load_stored_candidate_proposal` requires `candidate_evidence_path`, and `load_stored_candidate_review_replacement` requires `replacement_evidence_path`. Both raise when the file is missing.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_decision_settlement_enrolled.py`: the runner, the no-review sentinel, the content-identity recipe, the refusal alias, and private builders for the version and the generation.
  - `tests/test_roadmap_decision_settlement_enrolled.py`: the runner cases under Tests.
- **Existing files (edits only):**
  - `plan_tool/roadmap_revision_publish.py`:
    - add `DECISION_SETTLEMENT_GENERATION_KIND = "decision-settlement"`;
    - add one `generation.kind == DECISION_SETTLEMENT_GENERATION_KIND` branch in `_is_completed_version_owned_generation`, placed after the root-enrollment branch returns and before the review-seal-promotion check;
    - add the `roadmap_versions` imports that branch needs;
    - update the function's one-line docstring to name the third shape.
    - `recover_roadmap_publication`, the root-enrollment branch, and the review-seal-promotion branch keep a zero-line diff.
  - `tests/test_roadmap_revision_publish.py`: two new pinning cases, green at HEAD, and four new recognition cases. No existing case changes.
- **Unchanged (zero-line diff):**
  - `plan_tool/roadmap_versions.py`: the `root`/`candidate` `version_kind` vocabulary and `INITIAL_EMPTY_REVIEW_LINEAGE_ID` stay as they are.
  - `plan_tool/roadmap_version_promotion.py`, `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`, `plan_tool/roadmap_candidate.py`, `plan_tool/roadmap_impact_snapshot.py`, `plan_tool/roadmap.py`.
  - Steps 2–4's modules, and `plan_tool/cli/roadmap_cmd.py`, which step 6 owns.

## Implementation

### Public surface

Steps 6 and 7 read these names off the landed module.

- **`run_enrolled_decision_settlement(slug, decision_value, evidence_value, confirmation, *, plans_dir, stages=STAGES, mode_rejected=False, receipt_committer=None) -> DecisionSettlementRunResult`.** It mirrors step 4's runner signature, so step 6 can pick a runner by lineage and call both the same way.
- **The result type is step 4's `DecisionSettlementRunResult`, with its five outcomes and statuses.** Reuse it unchanged so step 6 renders one redacted result shape.
- **`EnrolledDecisionSettlementRunRefusal`** is a `Literal` alias: step 4's `DecisionSettlementRunRefusal` members plus this step's three names below. Step 4's module is not edited. Its `refusal` annotation is a type hint that nothing in the suite checks.
- **`DECISION_SETTLEMENT_NO_REVIEW_LINEAGE_ID`** is a module constant: the SHA-256 of a fixed preimage in the style of `INITIAL_EMPTY_REVIEW_LINEAGE_ID`. One way: `b'{"review_lineage_version":1,"review":"none","route":"decision-settlement"}'`.
  - It must be lowercase 64-hex, because `StoredRoadmapVersion` validates it that way.
  - It must differ from `INITIAL_EMPTY_REVIEW_LINEAGE_ID`.
  - It states "no review occurred". It never means "proposed, awaiting review".
- **`decision_settlement_content_identity(*, predecessor_version_id, artifact_key, decision_id, feedback_id, evidence_digest) -> str`** is pure.
  - One way: `plan_tool/checkpoint.py:compute_input_hash` over those five values plus a fixed `schema_version` and a `route: "decision-settlement"` tag.
  - It must never call `plan_tool/roadmap_candidate.py:_content_identity`, which hashes a model capsule receipt this route never produces.

### Outcomes and refusals

The outcomes, statuses, and `receipt_id` rules are step 4's, unchanged. This table maps the plan's Testing cases to what this runner reports.

| Plan Testing case | `refusal` | Owner |
| --- | --- | --- |
| 1–7, 9, 10 | step 2's verdict, copied exactly | step 2 |
| 8 | cannot happen here: an enrolled source is never baseline-admitted | — |
| 11 | `source-changed`, from the currency check after the receipt or from the in-window selector check | step 2's name |
| 12 | `journal-unrecoverable` | step 4's name, reused |
| 13 | `unpromoted-candidate-lineage` | this step |
| 14 | `settled-content-fails-gates` | this step |
| 15 | step 3's outcome name, under `receipt-rejected` | step 3 |
| lineage mismatch | `unenrolled-roadmap-rejected` | this step, mirroring step 4's `enrolled-roadmap-rejected` |

- Every refusal above is `preflight-rejected` with status `2`, except a case-15 receipt failure, which is `receipt-rejected` with status `1`.
- `settled-content-fails-gates` carries the name only. It carries no violation text, which keeps step 4's redacted result shape.

### Run order

The order must hold. Each refusal returns right away.

1. `confirmation is not True` → `confirmation-required`. Nothing on this path touches the filesystem.
2. `mode_rejected` → `mode-rejected`.
3. `roadmap_dir(plans_dir, slug)` raises `TypeError` or `ValueError` → `mode-rejected`.
4. Default `receipt_committer` to `plan_tool.cli.gitcommit.commit_receipt` through a lazy import, as step 4 does.
5. Enter `roadmap_writer_guard(plans_dir, slug)`. Steps 6–17 all run inside this one lease.
6. **Lineage:** `load_accepted_version` returns `None` → `unenrolled-roadmap-rejected`, **before** recovery runs. Un-enrolled recovery belongs to step 4's runner.
7. `recover_roadmap_publication(...)`. A `RoadmapPublicationRecoveryError` from **this call only** → `journal-unrecoverable`. The journal stays in place.
8. `resolve_decision_settlement_selector(...)` returns a refusal → that verdict. As in step 4, this may run before the lease.
9. **Case 13:** `load_candidate_admission`. The runner refuses as `unpromoted-candidate-lineage` when the admission is not `None` and its `predecessor_version_id` equals the accepted head's version id, read after recovery.
   - This is a comparison with the current head, nothing more. No age, no `candidate_version_id` state, and no proposal outcome changes the answer.
   - The check runs before step 2's build. A roadmap-wide block gets reported before request-level refusals.
10. `build_decision_settlement_candidate(...)` returns a refusal → that verdict.
11. **Pin the head.** Read the selector file's raw bytes and `load_accepted_version`. Both the parsed selector and the accepted record must name `candidate.accepted_version_id`; otherwise → `source-changed`. Build the settlement version (see below).
12. **Case 14:** run `check_complete_roadmap_gates` over the settlement version's four artifacts and the accepted `brief_bytes`, with the runner's `stages`. The runner refuses as `settled-content-fails-gates` in any of these cases:
    - the outcome count differs from `len(stages)`;
    - an outcome's stage is not its stage-table entry;
    - an outcome has any violation.

    Check this the same way `promote_review_seal`'s `_recheck_stored_candidate` checks its outcomes.
13. **Build the generation** (see below). An existing member path raises `RoadmapVersionError`.
14. `build_decision_settlement_receipt(candidate, resulting_version_id=<new version id>)`, then `publish_decision_settlement_receipt(...)`. An outcome outside the success set → `receipt-rejected`. **No version member or selector is written on this path.**
15. **Full recheck:** `decision_settlement_candidate_is_current(...)` is `False` → `source-changed`. Case 13 is checked again → `unpromoted-candidate-lineage`. This catches anything a Git hook moved while the receipt was committed, the same reason step 4 gives. The receipt stays as evidence of the attempt.
16. `publish_roadmap_generation(generation, plans_dir=..., slug=..., writer_token=..., before_replace=<in-window check>)`.
17. Return `settled` with the receipt id.

Every refusal in steps 6–13 happens before the receipt, so a published receipt always names a version that was fully validated.

### The settlement version

- **Content:**
  - the accepted `brief_bytes`, unchanged;
  - the accepted `artifact_bytes`, with the member at `selector.artifact_key`'s inventory index replaced by `candidate.settled_bytes`;
  - the other three members, keeping the predecessor's bytes.
- **Record:** `create_candidate_version` with these values:
  - `roadmap_slug=slug`;
  - `predecessor_version_id=accepted.record.version_id`;
  - `content_identity` from `decision_settlement_content_identity`, fed by the selector's `artifact_key` / `decision_id` / `feedback_id` and `candidate.evidence_digest`;
  - `review_lineage_identity=DECISION_SETTLEMENT_NO_REVIEW_LINEAGE_ID`;
  - `brief_digest=accepted.record.brief_digest`;
  - `artifact_digests` from the new content.

  Wrap the record and content in `PreparedRoadmapVersion`. Its check that content matches digests is the backstop.
- **The version id is deterministic.** A retry with the same inputs on the same head gives the same id. Step 3's receipt then resolves to the same final.
- **The version directory holds exactly the six stored members.** It never gets `candidate-evidence.json`, a replacement-evidence file, or any admission write.
- **Top-level stage files, `.roadmap-baselines`, and `seed-state.json` are not touched.** This matches `promote_review_seal`, which changes only the accepted head, and `ROADMAP_FORMAT.md`'s rule that live top-level paths do not select enrolled content.

### The generation and the swap

- **Members, in this order:**
  - the six `stored_version_members(prepared)` entries, each with `old_bytes=None`, at `version_directory_path(...) / member_name`;
  - **last**, the selector at `accepted_head_path(...)`, with `old_bytes` = the raw selector bytes pinned in run step 11 and `new_bytes = render_accepted_head(<head naming the new version>)`.

  All paths are relative to `roadmap_dir(plans_dir, slug)`, as `build_root_enrollment_generation` builds them. The selector must be last. If a write is interrupted, the head then never names a version whose members are incomplete.
- **Kind:** `DECISION_SETTLEMENT_GENERATION_KIND`, imported from `plan_tool/roadmap_revision_publish.py`. There is **one** generation, never a store step followed by a separate promote step.
- **Stored members are never overwritten or deleted.**
  - When building, any existing path, including a symlink, at a version-member location raises `RoadmapVersionError`, as `build_root_enrollment_generation` and `_store_candidate` do.
  - The in-window check repeats that existence check.
  - The module has no `unlink`, and it never calls a write helper directly.
- **The in-window check (`before_replace`)** runs after the journal is written:
  - the selector file's raw bytes must equal the pinned old bytes; otherwise it raises a private stale-head exception, reported as `source-changed`;
  - no version-member path may exist; otherwise it raises `RoadmapVersionError`, reported as `write-failed`.
  - On any raise, `publish_roadmap_generation` deletes the journal before any member is written.
  - Selector bytes are enough inside the window: stored versions are immutable, and the head fully names the content.
  - Do not call step 2's build or currency check here. They re-read the whole store for no added coverage.

### Recovery branch in `_is_completed_version_owned_generation`

The new branch returns `True` only when all of these hold:

- the accepted record's `version_kind == "candidate"`;
- `generation.members[:-1]` equals the six `GenerationMember`s rebuilt from the accepted version, each with `old_bytes=None`. One way: `stored_version_members(PreparedRoadmapVersion(record, RoadmapVersionContent(brief_bytes, artifact_bytes)))`, mapped to paths relative to the roadmap root. A `RoadmapVersionError` while rebuilding means `False`;
- the last member is at the selector's relative path, its `new_bytes == render_accepted_head(selected_head)`, and its `old_bytes` is non-`None` and parses as a head for this slug whose `version_id == record.predecessor_version_id`.

Also note:

- **Recovery itself is unchanged.** It already requires every member's current bytes to equal `new_bytes` before it drops the journal. So a settlement interrupted before the swap, where the head is still the old version, fails recognition and is refused, the same as any unrecognized generation.
- **Deliberately not checked: the no-review sentinel.**
  - The publish layer would have to import the settlement module, which imports the publish layer.
  - Recognition already binds the exact members and the old head.
  - Recovery never writes, so a looser check can only drop a journal whose members all hold their new bytes already.
- **The root-enrollment and review-seal-promotion branches do not change.** A behavior-preserving rewrite, such as sharing a member-list helper between branches, is out of this step.

### Exception mapping

- The private stale-head exception → `preflight-rejected` / `source-changed`. Catch it before any generic `ValueError` mapping.
- `KeyboardInterrupt` → `interrupted` (`130`). The `with` block releases the lease. If the interrupt lands mid-write, the journal stays, and the next run's recovery refuses it (see Deferred).
- These all map to `write-failed` (`1`):
  - `OSError`;
  - `RoadmapRevisionPublishError`, including a `RoadmapPublicationRecoveryError` raised by publication rather than recovery;
  - `RoadmapWriterGuardError`;
  - `ValueError`, which covers `RoadmapVersionError` (a corrupt store, an invalid head at step 6, or a member collision), `CandidateProposalError` (an unreadable admission), `RoadmapImpactSnapshotError` (a stored member that cannot bind for the gate walk), step 2's byte-contract `ValueError`, and step 3's `DecisionSettlementReceiptError`.

  These are broken-store or broken-contract states, not operator refusals. Step 2 takes the same stance.

### Module rules

- **No backend call, no invoker seam, no run log.** This matches step 4.
- **Writes go only through step 3's publisher and one `publish_roadmap_generation` call.**
- **Imports:**
  - `plan_tool.roadmap` (`STAGES`);
  - steps 2, 3, and 4's modules;
  - `plan_tool.roadmap_revision_publish`;
  - `plan_tool.roadmap_versions`;
  - `plan_tool.roadmap_impact_snapshot`;
  - `plan_tool.roadmap_candidate_run` for `load_candidate_admission` only;
  - `plan_tool.checkpoint`.
- **Never import** `plan_tool.roadmap_version_promotion`, `plan_tool.roadmap_candidate_review`, or `plan_tool.roadmap_candidate`. `plan_tool.cli` is imported lazily, and only for the committer default.
- **No copies of step 4's private helpers.** If `tests/test_duplication.py` flags a body copied from step 4's module, reuse the step 4 symbol instead.

### Rejected alternatives

- **Calling `promote_review_seal`** after storing the version. That needs a made-up admission, proposal evidence, answer, replacement evidence, and seal. The plan's guardrails forbid all of them.
- **Adding a new `version_kind`** (for example `"settlement"`). The two evidence loaders are reachable only from the model pipeline, and `StoredRoadmapVersion`'s closed vocabulary lives in a module this step does not own.
- **Reusing `INITIAL_EMPTY_REVIEW_LINEAGE_ID`.** It asserts "proposed, awaiting review". `load_stored_candidate_review_replacement` also treats every other lineage id as answer-bound, and it fails closed without an evidence file, so the dedicated sentinel is safe too.
- **Two generations (store, then swap)**, the candidate pipeline's split. Settlement has no held-for-review state, and one generation removes the "stored but never promoted" case.
- **Writing the selector first.** An interrupted write would leave a head naming an incomplete version, so every reader would fail rather than only recovery.
- **Treating any admission as blocking.** Plan state (b), a promoted lineage, must proceed. The check compares the admission's predecessor with the head.

## Tests

**Fixture approach:**

- **Git.** Use an autouse fixture that runs `git init` in `tmp_path` and sets `user.email` / `user.name`, as in step 4's runner tests.
- **Enrolled roadmap.** Build it raw from four gate-clean rendered artifacts: a domain with a Roadmap-derived `pending` decision anchored on an entity, plus a `ROW` feedback row targeting it with a non-blank `request`.
  - Store the versions with `create_root_version` / `create_candidate_version`, `stored_version_members`, and `render_accepted_head`, as `tests/test_roadmap_view.py:_store_version` and `_select_accepted_version` do.
  - `tests/test_roadmap_version_promotion.py:_root` is a model for a gate-clean four-artifact bundle.
- **Admissions.** Create them through `run_initial_candidate_proposal` with a stub invoker: a rejected reply gives an admission with no candidate, and a valid delta gives a stored candidate.
- **Never build fixtures through this runner, `promote_review_seal`, or `enroll_roadmap_root`.**
- **The recognition cases in `tests/test_roadmap_revision_publish.py` build the settlement-shaped generation by hand** and do not import this step's module. A builder bug and a recognizer bug therefore cannot hide each other. One seam case in the runner file ties the two together.

### Tests for this step

**`tests/test_roadmap_revision_publish.py`: pinning cases, green at HEAD (write these first).** They guard the untouched branches while the new branch is added.

- `test_completed_root_enrollment_journal_is_dropped_without_touching_members`: a real root enrollment has all its members written and its journal left behind. Recovery removes only the journal.
- `test_completed_review_seal_promotion_journal_is_dropped_without_touching_members`: a hand-stored child version is selected, and a one-member selector journal is left behind. Recovery removes only the journal.

**`tests/test_roadmap_revision_publish.py`: cases that land with the branch.**

- `test_completed_decision_settlement_journal_is_dropped_without_touching_members`: all seven members hold their new bytes. The journal is removed, and every member keeps the same bytes.
- `test_decision_settlement_journal_interrupted_before_the_selector_swap_is_refused_and_left_in_place` (parametrized: two of six version members written; all six written with the head not swapped): `RoadmapPublicationRecoveryError`. The journal, the partial members, and the head are unchanged.
- `test_decision_settlement_recognition_requires_the_old_head_to_name_the_versions_predecessor`: the selector member's old bytes name a sibling version, and recovery refuses.
- `test_decision_settlement_recognition_refuses_a_malformed_member_list` (parametrized: selector not last; an extra `candidate-evidence.json` member; brief member missing; a version member with non-`None` old bytes; the accepted version is a root): `_is_completed_version_owned_generation` returns `False`.

**`tests/test_roadmap_decision_settlement_enrolled.py`.** The module is new, so every case lands with it.

*Refusals before the lease:*

- `test_missing_or_non_true_confirmation_refuses_before_any_filesystem_access` (parametrized: `None`, `False`, `"yes"`).
- `test_mode_rejected_refuses_before_any_filesystem_access`.
- `test_invalid_slug_is_mode_rejected`.

*Lineage and recovery:*

- `test_unenrolled_roadmap_is_refused_before_recovery_and_preflight`: the result is `unenrolled-roadmap-rejected`, and the recovery spy and the build spy are never called.
- `test_invalid_accepted_head_is_write_failed_before_recovery`.
- `test_completed_settlement_journal_left_behind_is_dropped_and_the_retry_is_decision_not_pending` (the seam case). The generation the runner published is captured and its journal re-written. The retry drops it, and the result is `decision-not-pending` with no second version.
- `test_settlement_interrupted_mid_write_is_write_failed_and_the_retry_is_journal_unrecoverable`: the third version member's write raises `OSError`. The first result is `write-failed` with `receipt_id` set. On retry, the result is `journal-unrecoverable`, and the journal, the partial members, and the head are unchanged.
- `test_non_version_owned_journal_is_journal_unrecoverable`: a `stage-publication` journal exists on the enrolled roadmap.

*Preflight wiring:*

- `test_preflight_refusals_are_reported_verbatim_and_store_no_version` (parametrized: `malformed-decision-selector`, `missing-decision`, `inherited-decision`, `decision-not-pending`, `feedback-not-targeting-decision`, `empty-request`, `source-not-canonical`, and `missing-feedback` for a row present only in the on-disk stage file): no evidence directory, no new version directory, and the head is unchanged.

*Candidate lineage (plan case 13):*

- `test_unpromoted_lineage_on_the_current_head_refuses_before_any_receipt` (parametrized: rejected proposal with no candidate; stored candidate awaiting its question): the result is `unpromoted-candidate-lineage`, no receipt exists, and step 2's build is never called.
- `test_unpromoted_lineage_refusal_has_no_age_limit`: the admission's mtime is set decades back, and the result is still refused.
- `test_refusal_clears_once_the_head_moves_past_the_admissions_predecessor`: a stored child of the admission's predecessor is selected, which is the state promotion leaves. The run settles, and the admission's bytes are unchanged.
- `test_runner_offers_no_way_to_abandon_or_override_a_lineage`: `inspect.signature` lists only the documented parameters, and a refused run leaves the admission's bytes unchanged.

*Gates (plan case 14):*

- `test_gate_violation_on_the_settled_content_refuses_before_any_receipt`: an injected stage table with a failing plans-stage gate. The result is `settled-content-fails-gates`, with no receipt, no version directory, and the head unchanged.
- `test_gate_walk_sees_the_settled_bytes_and_the_accepted_brief`: a spy on `check_complete_roadmap_gates` sees the selected key's text equal to `settled_bytes` decoded, and `brief_bytes` equal to the accepted brief.

*The settlement version:*

- `test_no_review_sentinel_is_a_fixed_sha256_distinct_from_the_initial_review_lineage`.
- `test_settlement_version_is_a_candidate_record_with_the_no_review_sentinel_and_the_old_head_as_predecessor`.
- `test_content_identity_is_the_settlement_recipe_over_its_named_inputs` (parametrized over each of the five inputs): changing any one input changes the identity.
- `test_settlement_version_directory_holds_only_the_six_stored_members`: there is no candidate evidence file and no replacement evidence file, and no admission file is created.
- `test_new_version_changes_only_the_selected_status_line`: the selected member differs by one line (`status: pending` → `status: settled`). The other three members and the brief keep the predecessor's bytes.
- `test_cited_feedback_row_is_unchanged_in_the_new_version`: an `awaiting-review` row with a `proposed_response`, the plan's motivating case.
- `test_settlement_version_is_refused_by_both_model_pipeline_loaders` (parametrized): the two loaders raise `CandidateProposalError` and `CandidateReviewError`.
- `test_existing_member_at_the_settlement_version_path_is_never_overwritten`: the result is `write-failed` before any receipt, and the file's bytes and the head are unchanged.
- `test_prior_stored_versions_are_never_modified_or_removed`: a byte snapshot of `.roadmap-versions/` before and after. The only changes are the new directory's files and the selector.
- `test_top_level_stage_files_baselines_and_seed_state_are_untouched`.

*The swap:*

- `test_version_members_and_selector_swap_publish_as_one_decision_settlement_generation`: a spy sees exactly one call, of kind `DECISION_SETTLEMENT_GENERATION_KIND`. It has six members with `None` old bytes, and then the selector last, with the prior head's bytes as its old bytes.
- `test_head_names_the_new_version_after_settlement`.
- `test_head_move_during_the_receipt_commit_refuses_as_source_changed`: the committer selects another stored version and then commits. The result is `source-changed` with `receipt_id` set, and no settlement version directory exists.
- `test_head_move_inside_the_journal_window_refuses_and_leaves_no_journal`: a patched `roadmap_revision_publish.durable_write_bytes` rewrites the selector when the journal is written. The result is `source-changed`, no journal remains, and no member is written.
- `test_accepted_head_is_written_only_inside_the_decision_settlement_journal_window`: a spy on `roadmap_revision_publish.durable_write_bytes` records exactly one write to the accepted-head path, made while a journal of the settlement kind exists.
- `test_no_call_reaches_promotion_or_the_model_pipeline`: `promote_review_seal`, `_load_complete_sealed_candidate`, both evidence loaders, and `roadmap_candidate._content_identity` are patched to `pytest.fail`. The run still settles.

*Receipt ordering:*

- `test_receipt_is_committed_to_head_before_the_generation_is_published`.
- `test_receipt_names_the_stored_version_and_proves_completion`: `resulting_version_id` equals the new head's id, and step 3's read-back returns `True`.
- `test_each_non_success_receipt_outcome_stops_before_any_version_write` (parametrized over step 3's non-success outcomes via `typing.get_args`): `publish_roadmap_generation` is never called, no version directory exists, and `receipt_id is None`.
- `test_commit_failure_then_retry_settles_with_the_same_receipt_and_version_id`: the second run's publisher outcome is `committed-existing`, exactly one receipt final exists, and the version id is the same.

*Result and module rules:*

- `test_result_is_the_shared_redacted_run_result`: the result is a step 4 `DecisionSettlementRunResult`, and the fixture's row prose is absent from its `repr`.
- `test_enrolled_refusal_alias_adds_exactly_three_names`: `unenrolled-roadmap-rejected`, `unpromoted-candidate-lineage`, and `settled-content-fails-gates`, with no overlap with step 4's alias.
- `test_keyboard_interrupt_reports_interrupted_and_releases_the_lease`.
- `test_settlement_modules_have_no_direct_write_route_to_the_accepted_head` (parametrized over the four settlement modules from steps 2–5). A source scan checks these rules:
  - no direct write call and no `unlink`;
  - `accepted_head_path` and `render_accepted_head` appear only in this step's module;
  - this step's module calls `publish_roadmap_generation` once.

  The test's docstring names root enrollment and `promote_review_seal` as deliberately out of its scope.

That is 6 cases in the publish file and approximately 40 in the runner file. Every one must be green before this step counts as finished, and so must `uv run pytest tests/ -q -n auto`.

**Verify by breaking the code, not by reading it.** Each break below must turn at least one case red:

| Deliberate break | Case that must go red |
| --- | --- |
| Use `INITIAL_EMPTY_REVIEW_LINEAGE_ID` | the sentinel cases |
| Put the selector member first | the one-generation case |
| Publish version storage and the swap as two generations | the one-generation case |
| Drop the in-window selector check | the journal-window head-move case |
| Skip the full recheck after the receipt | the receipt-commit head-move case |
| Block on any admission rather than one on the current head | the refusal-clears case |
| Skip the gate walk | the gate-violation case |
| Drop the existing-member check | the never-overwritten case |
| Leave out the recognition branch | the seam case and the completed-settlement-journal publish case |
| Recognize the kind without checking the old head | the old-head publish case |
| Run recovery before the lineage check | the un-enrolled case (recovery spy) |

## Acceptance criteria

- `run_enrolled_decision_settlement` returns `settled` with status `0` for an enrolled roadmap in all of these conditions:
  - a Roadmap-derived pending decision is cited by a `ROW`-targeted feedback row with a non-blank `request`;
  - the source artifact is render-canonical;
  - there is no admission, or the admission's predecessor is not the current head.
- After a settled run:
  - the head names a new `candidate` version whose predecessor is the old head;
  - its `review_lineage_identity` is `DECISION_SETTLEMENT_NO_REVIEW_LINEAGE_ID`;
  - its `content_identity` equals `decision_settlement_content_identity(...)`;
  - its directory holds exactly six members;
  - only the selected status line differs from the predecessor.
- Every earlier stored version file, every top-level stage file, every baseline, `seed-state.json`, and the admission file keep their bytes.
- The version members and the swap are published as one `"decision-settlement"` generation, with the selector last.
- The receipt is committed to `HEAD` before that generation is published and names the new version id.
- `unpromoted-candidate-lineage` is returned while an admission's predecessor is the current head, whatever the admission's state or age. The run settles once the head has moved past that predecessor.
- `settled-content-fails-gates`, every step 2 verdict, and `unpromoted-candidate-lineage` leave no receipt, no version directory, and an unchanged head.
- `recover_roadmap_publication` drops a completed decision-settlement journal without writing, and it refuses one interrupted before the swap.
- `rg -n "roadmap_version_promotion|roadmap_candidate_review|roadmap_candidate\.|from plan_tool\.roadmap_candidate import|load_stored_candidate_proposal|load_stored_candidate_review_replacement|candidate_evidence_path|replacement_evidence_path|candidate_admission_path|CandidateProposalAdmission|CandidateReviewSeal|INITIAL_EMPTY_REVIEW_LINEAGE_ID" plan_tool/roadmap_decision_settlement_enrolled.py` returns nothing.
- `rg -n "write_bytes|write_text|durable_write|unlink|rmtree|os\.remove|publish_stage_artifact|seed_state|baseline_path" plan_tool/roadmap_decision_settlement_enrolled.py` returns nothing.
- `rg -n '"decision-settlement"' plan_tool/` returns exactly one line: the constant in `plan_tool/roadmap_revision_publish.py`.
- The `git diff` of `plan_tool/roadmap_revision_publish.py` changes no existing line in `recover_roadmap_publication`, the root-enrollment branch, or the review-seal-promotion branch.
- `git diff --stat` shows no change to `plan_tool/roadmap_versions.py`, `plan_tool/roadmap_version_promotion.py`, `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`, `plan_tool/roadmap_candidate.py`, `plan_tool/roadmap_impact_snapshot.py`, `plan_tool/roadmap.py`, steps 2–4's modules, or `plan_tool/cli/roadmap_cmd.py`.
- `uv run pytest tests/test_roadmap_decision_settlement_enrolled.py tests/test_roadmap_revision_publish.py tests/test_roadmap_version_promotion.py -q` passes, and so does `uv run pytest tests/ -q -n auto`.

## References

- `plan_tool/roadmap_version_promotion.py` (`promote_review_seal`, `_load_current_accepted_version`, `_load_complete_sealed_candidate`, `_recheck_stored_candidate`): the selector swap and gate-outcome check this step copies, and the sealed chain it never enters.
- `plan_tool/roadmap_versions.py` (`create_candidate_version`, `StoredRoadmapVersion`, `stored_version_members`, `build_root_enrollment_generation`, `load_accepted_version`, `INITIAL_EMPTY_REVIEW_LINEAGE_ID`): the record builder, the bundled members-before-selector precedent, and the sentinel this step must not reuse.
- `plan_tool/roadmap_revision_publish.py` (`recover_roadmap_publication`, `_is_completed_version_owned_generation`, `publish_roadmap_generation`): the journal, the recovery, and the kind branch this step extends.
- `plan_tool/roadmap_candidate_run.py` (`load_candidate_admission`, `load_stored_candidate_proposal`) and `plan_tool/roadmap_candidate_review.py` (`load_stored_candidate_review_replacement`): the admission read for case 13, and the two loaders a settlement version never enters.
- `plan_tool/roadmap_impact_snapshot.py` (`check_complete_roadmap_gates`, `_evaluate_full_roadmap_gates`): the content-only gate walk for case 14, and the `predecessor=None` gap it does not close.
- `ROADMAP_FORMAT.md` § "Immutable candidate-version authority": the accepted-head authority text step 7 updates to name this second guarded writer.
- `BACKLOG.md` #394 and #395, and the `BUG_BACKLOG.md` entries "Incomplete immutable lifecycle journals…" and "An enrolled roadmap's candidate promotion never re-checks a settled decision against its predecessor": the limits this runner leaves as they are.

## Applicable guardrails

- **The plan's "## Scope guardrails", enrolled-roadmap bullet: no accepted-head write outside the guarded swap, no made-up admission or seal, and no candidate admission or evidence entries.**
  - This binds this step hardest. The tempting site is run step 16: calling `promote_review_seal` "to reuse its checks" would need exactly the made-up chain the plan forbids.
  - Checked by the no-pipeline-call case, the six-member case, the write-window spy, and the first `rg` criterion.
- **The plan's "## Scope guardrails", enrolled-roadmap bullet: no route for citing feedback recorded after enrollment.**
  - The runner takes evidence only through step 2's accepted-version read.
  - Pinned by the on-disk-only `missing-feedback` case.
- **The plan's "## Scope guardrails": only `pending → settled` on one Roadmap-derived row, and no other field or row changes.**
  - The new version reuses step 2's `settled_bytes` for one member and the predecessor's bytes for everything else.
  - The tempting site is re-rendering the other members to "normalize" them. Do not.
- **The plan's "## Scope guardrails": no judgment of the cited feedback, and the row's state never changes.**
  - The result carries no row text, and the cited row is unchanged in the new version.
- **The plan's "## Scope guardrails": not a batch operation.** One call stores one version.
- **The plan's "## Out of scope": no recovery of a malformed or interrupted journal.**
  - The new branch only recognizes a *completed* settlement generation.
  - An interrupted one is refused as `journal-unrecoverable` and left in place.
- **The plan's "## Out of scope": no change to `check_settled_decisions`.**
  - The gate walk runs as it is. No test here claims it protects a settled decision on the enrolled lineage.

## Deferred

- **Choosing this runner or step 4's by lineage, the CLI flags, the confirm flag, two-way exclusivity, and `docs/cli/roadmap.md`**: step 6.
- **The cross-lineage identical-row assertion**: step 6.
- **Docs**: step 7. That covers naming this second accepted-head writer in `ROADMAP_FORMAT.md` and `CAPABILITIES.md`, the `docs/ARCHITECTURE.md` module entry, CLAUDE.md's import list, the three enrolled limits, and extending the `BUG_BACKLOG.md` journal entry to name the `"decision-settlement"` generation shape.
- **Repairing a settlement journal interrupted before the swap**: out of plan scope, tracked by the `BUG_BACKLOG.md` "Incomplete immutable lifecycle journals" entry. Until then, such a journal blocks the roadmap as `journal-unrecoverable`.
- **A route to abandon a stalled candidate lineage** (`BACKLOG.md` #395) and **a route to record post-enrollment feedback** (`BACKLOG.md` #394): separate capabilities. This runner neither adds nor works around them.
- **Settled-decision drift protection on the enrolled lineage** (`_evaluate_full_roadmap_gates` passes `predecessor=None`): tracked in its own `BUG_BACKLOG.md` entry. Fixing it changes the shared evaluator.
- **Seed-state invalidation on the enrolled lineage**: deliberately not done. The enrolled write mirrors seal promotion, which changes only the accepted head.
- **Reporting gate-violation messages in the run result**: not built. The result keeps step 4's redacted shape.
- **Widening step 4's `DecisionSettlementRunRefusal` annotation to list the enrolled names**: a type-hint-only edit to a module outside this step's files.
