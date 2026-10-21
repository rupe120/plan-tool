# Step 3 — Add the settlement receipt record, its own evidence namespace, create-once committed publication, and a read-back check

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds `plan_tool/roadmap_decision_settlement_receipt.py`, adds a third `EvidenceNamespace` member to `plan_tool/roadmap_evidence_store.py`, and adds one keyword-only `namespace` argument to two Git helpers in `plan_tool/roadmap_escalation_run.py`. The new module builds an immutable, redacted receipt from step 2's preflight candidate. The receipt names the artifact, decision, cited feedback row, predecessor digest, and the exact result settlement is about to produce. The module publishes that receipt once into its own namespace, commits it to `HEAD` before any canonical write, and exposes a read-back check that says whether a receipt still proves a completed settlement. The key design decision is that the receipt's bytes are fully set by its inputs, with no timestamp. A retry with the same inputs therefore resolves to the same final name and the same bytes, and an existing final is returned rather than overwritten. On green, steps 4 and 5 can call one publisher and check its outcome against a closed set before writing.

## Table of Contents

- [Why](#why) — why settlement needs its own committed receipt and a shipped proof check
- [Input](#input) — the step-2 candidate, the evidence store, the escalation Git helpers, and the version store this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the new module and tests, the three edited files, and the files that must stay unchanged
- [Implementation](#implementation) — the receipt fields, the publication outcomes, the read-back rules, and rejected alternatives
- [Tests](#tests) — named cases per area, the fixture approach, and the breaks each case must catch
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer can run
- [References](#references) — plan-level references that bear on this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this module, and where breaking them is tempting
- [Deferred](#deferred) — work owned by later steps or left out of this plan

## Why

No record exists at HEAD that ties a decision's move to `settled` to the evidence that justified it. The closest precedent, the escalation receipt (`plan_tool/roadmap_escalation.py:EscalationReceipt`, published by `plan_tool/roadmap_escalation_run.py:run_roadmap_escalation_receipt`), records a different fact. That fact is an open feedback row asking for scope review, and `build_receipt` refuses any selection that is not `FeedbackState.OPEN`. Settlement's own motivating case is a feedback row in `awaiting-review`, so that record type cannot carry it.

Steps 4 and 5 both have to leave a durable trail before they write canonical content. If each runner shaped its own record and its own commit sequence, the two lineages' receipts would drift. The plan also promises a shipped check for whether a receipt still proves a completed settlement. That promise differs by lineage:

- **Enrolled:** proof lasts as long as the settled version stays in the accepted head's predecessor chain.
- **Un-enrolled:** proof lasts only while the stage's exact bytes are the settled bytes.

Without code that owns this rule, an operator would have to work it out by hand. This step gives one owner to the receipt shape, its storage location, its commit sequence, and its proof rule.

## Input

- **Step 2's `DecisionSettlementCandidate`** (`plan_tool/roadmap_decision_settlement.py`).
  - The receipt reads these fields: `selector` (`artifact_key`, `decision_id`, `feedback_id`), `accepted_version_id` (`None` means un-enrolled), `source_digest`, `evidence_digest`, and `settled_digest`.
  - Step 2 has a detail file but has not landed at HEAD. Read the field names off the landed module; the landed names win over this file.
  - Step 2's `stages` parameter shape (a small `Protocol` with `artifact_key` and `artifact_path`) is the shape the read-back check takes too.
- **`plan_tool/roadmap_evidence_store.py`.**
  - `publish_evidence(roadmap_dir, namespace, final_name, data)` returns `created`, `existing` (with the stored bytes), `invalid-input`, or `write-failed`. It creates each final once through an exclusive hard link and never overwrites or deletes one.
  - `read_evidence_final` reads one named final.
  - `namespace_relative_components` gives a namespace's fixed path.
  - A final name must be 64 lowercase hex characters (`_FINAL_NAME_RE`).
- **Escalation Git primitives** (`plan_tool/roadmap_escalation_run.py`):
  - `receipt_worktree_for_plans_dir(plans_dir)` finds the Git worktree, or returns `None`.
  - `receipt_path_is_within_worktree(roadmap_root, receipt_worktree)` checks the final can have a Git-relative path.
  - `receipt_head_state(receipt_data, *, receipt_final_name, roadmap_root, receipt_worktree)` returns `matching`, `missing`, `different`, or `unreadable` against one pinned `HEAD`.
  - `ReceiptCommitter` is the committer type.
  - Both path helpers derive the path from `escalation_receipt_path`, so today they only know the escalations namespace.
  - Other callers outside the escalation module: `plan_tool/roadmap_structural_revision.py` and `plan_tool/roadmap_impact_run.py` call both `receipt_head_state` and `receipt_worktree_for_plans_dir`. `plan_tool/cli/roadmap_cmd.py` calls only `receipt_worktree_for_plans_dir`. None of them passes a namespace.
- **`plan_tool/cli/gitcommit.py:commit_receipt(repo_root, receipt_path, subject)`** force-stages and commits only the one path. It leaves the file on disk when the commit fails and returns `(rc, tail)`. It is used unchanged.
- **Version store** (`plan_tool/roadmap_versions.py`):
  - `load_accepted_head` returns `None` only when no head exists.
  - `load_stored_version(*, plans_dir, slug, version_id)` re-checks that the record's id matches its fields.
  - `StoredRoadmapVersion` carries `predecessor_version_id` and `artifact_members`, where each member's `digest` is the SHA-256 of that member's raw bytes.
  - Both loaders raise `RoadmapVersionError` for a corrupt store.
- **Publication journal** (`plan_tool/roadmap_source_identity.py`): `load_pending_generation(pending_generation_path(roadmap_root))` returns the in-flight generation or `None`. Both lineages' writers use this one journal.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_decision_settlement_receipt.py` — the receipt model, builder, renderer, parser, final path, publisher, outcome vocabulary, and read-back check.
  - `tests/test_roadmap_decision_settlement_receipt.py` — the cases under Tests.
- **Existing files (edits only):**
  - `plan_tool/roadmap_evidence_store.py`:
    - add `EvidenceNamespace.DECISION_SETTLEMENTS = "decision-settlements"`;
    - add its `_NAMESPACE_COMPONENTS` entry `(".plan-tool", "evidence", "decision-settlements")`.
    - Nothing else changes.
  - `tests/test_roadmap_evidence_store.py`:
    - add a fixed-components case for the new member;
    - add the new namespace to the isolation case.
    - The cases parametrized over `list(EvidenceNamespace)` pick up the third member with no edit.
  - **Added beyond the declared files:** `plan_tool/roadmap_escalation_run.py`.
    - Add a keyword-only `namespace: EvidenceNamespace = EvidenceNamespace.ESCALATIONS` to `receipt_head_state` and `receipt_path_is_within_worktree`.
    - Both helpers derive the final's path from that namespace.
    - This is needed so the settlement receipt reuses the one existing Git HEAD-comparison code instead of a second copy (see Rejected alternatives).
- **Unchanged (zero-line diff):**
  - `plan_tool/roadmap_structural_revision.py`, `plan_tool/roadmap_impact_run.py`, `plan_tool/cli/roadmap_cmd.py` — they call on the default.
  - `tests/test_roadmap_escalation_run.py` — its `test_receipt_head_state_pins_one_head_for_tree_and_blob` already guards the default arm and is green at HEAD.
  - `tests/test_roadmap_structural_revision.py` — its `receipt_head_state` stubs take `*_args, **_kwargs`.
  - `plan_tool/roadmap_escalation.py` and `plan_tool/cli/gitcommit.py`.
  - `.gitignore` — deliberately no entry. The namespace is shared evidence like escalations, and `commit_receipt` force-stages it anyway.

## Implementation

### Public surface

These names are this step's to choose. Steps 4–7 read them off the landed module.

- **`DECISION_SETTLEMENT_RECEIPT_SCHEMA_VERSION = 1`**. It has its own version, not `EVIDENCE_SCHEMA_VERSIONS`, which belongs to the canonical-source-identity evidence family.
- **`DecisionSettlementReceiptError(ValueError)`** — raised for invalid construction or parse input.
- **`DecisionSettlementReceipt`** — a closed, frozen, strict pydantic model (`extra="forbid"`, `strict=True`, `frozen=True`, as `plan_tool/roadmap_versions.py:_FrozenRecord` does). Fields are in the table below. `final_name` is a property that returns `receipt_id`.
- **`build_decision_settlement_receipt(candidate, *, resulting_version_id: str | None) -> DecisionSettlementReceipt`** — pure, with no filesystem access.
- **`render_decision_settlement_receipt(receipt) -> bytes`** and **`parse_decision_settlement_receipt(data, *, expected_final_name) -> DecisionSettlementReceipt`**.
- **`decision_settlement_receipt_path(roadmap_root, final_name) -> Path`** — built from `namespace_relative_components(EvidenceNamespace.DECISION_SETTLEMENTS)`, never from a hand-copied path.
- **`DecisionSettlementReceiptOutcome`** — a `Literal` of the nine outcomes below.
- **`DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES = frozenset({"created", "reused", "committed-existing"})`**. Steps 4 and 5 check membership in this set rather than listing failures, so a new failure outcome can never pass by accident.
- **`DecisionSettlementReceiptPublication`** — a frozen dataclass with `outcome` and `receipt_id`. `receipt_id` is set only on a success outcome and is otherwise `None`, matching `EscalationRunResult.receipt_identity`.
- **`publish_decision_settlement_receipt(receipt, *, plans_dir, slug, receipt_committer) -> DecisionSettlementReceiptPublication`**. `receipt_committer` is a **required** keyword. The runners in steps 4 and 5 supply `plan_tool.cli.gitcommit.commit_receipt`, so this module never imports `plan_tool.cli`.
- **`decision_settlement_receipt_proves_completion(receipt, *, plans_dir, slug, stages) -> bool`**.

### Receipt fields

Every field below except `receipt_id` is part of the semantic field set. `receipt_id` is `plan_tool/checkpoint.py:compute_input_hash` over that set, the same recipe escalation receipts use.

| Field | Un-enrolled | Enrolled | Taken from |
| --- | --- | --- | --- |
| `schema_version` | `1` | `1` | the constant |
| `artifact_key`, `decision_id`, `feedback_id` | set | set | `candidate.selector` |
| `lineage` | `"unenrolled"` | `"enrolled"` | whether `candidate.accepted_version_id is None` |
| `predecessor_digest` | set | set | `candidate.source_digest` |
| `predecessor_version_id` | explicit `null` | set | `candidate.accepted_version_id` |
| `evidence_digest` | set | set | `candidate.evidence_digest` |
| `resulting_artifact_digest` | set | set | `candidate.settled_digest` |
| `resulting_version_id` | explicit `null` | set | the caller's `resulting_version_id` (step 5 computes it) |
| `receipt_id` | set | set | hash of the fields above |

- **The receipt holds ids and digests only.** It carries no `request`, `proposed_response`, `rationale`, or other row prose, the same way escalation receipts carry none.
- **Ids must pass `plan_tool/roadmap_feedback.py:is_receipt_safe_id`, and every digest must be lowercase SHA-256.** A model validator must also require that the lineage's null and non-null bindings match `lineage`. This follows the rule `StoredRoadmapVersion` applies to root versus candidate bindings.
- **Keep `null` explicitly in the rendered JSON.** Never drop a key when its value is `None`. A reader can then tell "un-enrolled" from "field missing".
- **There is deliberately no `created_at`.** The commit records when the receipt was made. Without a timestamp, the same inputs render the same bytes, so a retry resolves to the same final with the same content. That is the create-once property the step's title asks for.
- **The builder must refuse a lineage mismatch** with `DecisionSettlementReceiptError`: a `resulting_version_id` on an un-enrolled candidate, or a missing or non-digest one on an enrolled candidate.
- **The builder must not compute the version id itself.** Step 5 owns `content_identity` and the no-review sentinel that feed `create_candidate_version`. The builder only records the id it is given.
- **Rendering** is canonical JSON: `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, UTF-8. This mirrors `plan_tool/roadmap_escalation.py:render_receipt`.
- **Parsing is strict.** It requires:
  - exactly one JSON object;
  - no duplicate members, no non-finite constants, and no floats;
  - no unknown fields;
  - `receipt_id` equal to the hash of the parsed fields;
  - `final_name == expected_final_name`.
- **Reuse a decoder hook rather than copying one.** One way is the `_reject_duplicate_json_keys` hook that `plan_tool/roadmap_versions.py` already imports from `plan_tool/roadmap_source_identity.py`. Do not copy `plan_tool/roadmap_escalation.py:_decode_receipt_object` verbatim. If `tests/test_duplication.py` flags a new copy, import the existing helper instead of adding an allowlist entry.

### Publication outcomes

`publish_decision_settlement_receipt` follows `run_roadmap_escalation_receipt`'s storage-and-commit sequence (`_map_storage_result` → `_classify_existing` → `_result_from_receipt_head_state` → `_commit_receipt`), with one change: the worktree check comes first. The table is the complete mapping.

| State observed | Outcome |
| --- | --- |
| `receipt_worktree_for_plans_dir` is `None`, or the settlement path is not inside that worktree (`receipt_path_is_within_worktree(..., namespace=DECISION_SETTLEMENTS)`) | `no-worktree` |
| `publish_evidence` returns `invalid-input` | `storage-rejected` |
| `publish_evidence` returns `write-failed`, or raises `OSError` | `write-failed` |
| `created`, but reading the final back fails | `commit-failed` |
| `created` or valid `existing`, and `HEAD` already holds the same bytes at the path | `reused` |
| `created`, `HEAD` lacks the path, the commit succeeds, and `HEAD` then matches | `created` |
| valid `existing`, `HEAD` lacks the path, the commit succeeds, and `HEAD` then matches | `committed-existing` |
| `existing` bytes do not parse, or name a different final | `invalid-existing-receipt` |
| `existing` parses under the same name but its semantic fields differ | `collision` |
| `HEAD` holds different bytes at the path | `collision` |
| `HEAD` is unreadable, the committer returns non-zero or raises `OSError` / `CalledProcessError`, or `HEAD` does not match after the commit | `commit-failed` |

- **Check the worktree before any evidence write.** A `no-worktree` result leaves no local final and no namespace directory. The plan's Testing case 15 names `no-worktree` as its own refusal, so it must not fold into `storage-rejected`.
- **`write-failed` is included on purpose.** The plan's outcome list names five failures. The escalation precedent it points to also has `write-failed`, and the plan's rule that every outcome other than the three successes stops settlement covers it. It gets its own name rather than hiding inside another.
- **Nothing is overwritten or deleted.**
  - Finals are written only through `publish_evidence`.
  - `commit_receipt` keeps the file when a commit fails.
  - The module has no `unlink`, `rmtree`, or `os.remove`.
  - A failed commit leaves a local final that a retry resumes as `committed-existing`.
- **Commit subject:** `"roadmap: persist decision settlement receipt"`.
- **The publisher takes no lock, emits no run-log event, and catches no `KeyboardInterrupt`.** Steps 4 and 5 call it inside their writer lease and own the lease, telemetry, and interruption mapping.
- **It takes a built receipt, never loose facts.** It therefore cannot publish a receipt that lacks the resulting digest.

### Read-back check

`decision_settlement_receipt_proves_completion` answers one question: does the settlement this receipt names still hold in the roadmap's current state? It uses the rules below, applied in this order. The first rule that decides the answer ends the check.

1. **Any pending generation → `False`.** Read `load_pending_generation(pending_generation_path(roadmap_dir(plans_dir, slug)))`. A publication still in flight is not a completed settlement on either lineage. A malformed journal raises `RoadmapSourceIdentityError`, which propagates.
2. **Enrolled receipt.**
   - No accepted head → `False`.
   - Otherwise, walk from the head through `predecessor_version_id` with `load_stored_version` until the chain ends.
   - Return `True` only when both of these hold:
     - `resulting_version_id` is on that chain;
     - its record's `predecessor_version_id` equals the receipt's, and its member digest for `artifact_key` equals `resulting_artifact_digest`.
   - A later promotion therefore never ends the proof.
   - The walk needs no guard against loops. Each id hashes its predecessor's id, and `load_stored_version` re-checks every record's id.
3. **Un-enrolled receipt.** Compare `resulting_artifact_digest` with the current exact content digest of `artifact_key`:
   - If the roadmap is still un-enrolled, that is the SHA-256 of the stage file's raw bytes (`stage.artifact_path(plans_dir, slug)`). A missing or unreadable file → `False`.
   - If the roadmap has since been enrolled, it is the accepted head record's member digest for `artifact_key`. The accepted version is then the current content, the same source step 2 reads.
   - The comparison is exact: any later edit to that artifact ends the proof. That includes a feedback-only edit and deleting the cited feedback row, which baseline admission cannot see.
- **A corrupt version store propagates `RoadmapVersionError`.** It is a broken store, not a "does not prove" answer, the same stance step 2 takes.
- **Deliberately not checked:**
  - whether the receipt is committed at `HEAD` — that is the publisher's outcome, and `receipt_head_state` answers it separately;
  - baseline admission or `canonical_projection` — the exact digest is stricter and sees feedback edits;
  - whether the cited feedback row still exists — on the un-enrolled lineage the exact digest already covers it, and an enrolled version's feedback cannot change;
  - anything about the `request` text.
- **Stated limit, not a defect:** on the un-enrolled lineage the proof does not outlive a later edit to the same artifact. Keeping it longer would need a digest history, and this plan does not build one.

### Escalation helper change

- Add `namespace` as keyword-only with the `ESCALATIONS` default. Every existing call then keeps its exact behavior with no edit.
- Each helper builds the final's path from `namespace_relative_components(namespace)`.
- Whether `escalation_receipt_path` delegates to a shared private path helper is the implementer's call. Its public signature and result must not change.

### Rejected alternatives

- **A local copy of `receipt_head_state` in the new module.** It would be a second implementation of a subtle pinned-`HEAD` byte comparison (`rev-parse` → `ls-tree` → `show`). Its body would differ only in the path call, so the duplication guard would not catch it. The additive keyword keeps one owner.
- **Generalizing the escalation lifecycle mapping** (`_map_storage_result`, `_classify_existing`, `_commit_receipt`) so both receipts share it. Those functions are tied to `EscalationReceipt`, its parser and validators, and `EscalationRunResult`, so sharing them means refactoring the escalation runner. See Deferred.
- **Keeping a `created_at` field like escalation receipts.** A timestamp makes retry bytes differ, which forces the "same name, different bytes" path on every retry. The commit already records the time.
- **Defaulting `receipt_committer` by lazily importing `plan_tool.cli.gitcommit` here**, as the escalation runner does. That default belongs in the runners (steps 4 and 5), which are the programmatic entry points. Leaving it out keeps this module free of `plan_tool.cli`.
- **Proving the un-enrolled lineage through baseline admission.** Admission ignores feedback, so a deleted evidence row would still read as proven.

## Tests

**Fixture approach:**

- Build `DecisionSettlementCandidate` values directly with fixed digests. One seam case runs step 2's `build_decision_settlement_candidate` for real.
- For publisher cases, give the test file an autouse fixture that runs `git init` and sets `user.email` / `user.name` in `tmp_path`, as `tests/test_roadmap_escalation_run.py:_receipt_worktree` does. Use the real `commit_receipt` unless a case injects a failing committer.
- Build enrolled state by hand with `create_root_version` / `create_candidate_version`, `stored_version_members`, and `render_accepted_head`, as `tests/test_roadmap_view.py:_store_version` does.
- Write un-enrolled stage files with the real renderers, and write journals with `render_pending_generation`.
- **Never build fixtures through step 4's or step 5's writers**, `enroll_roadmap_root`, or `publish_stage_artifact`.

The module is new, so no case in its test file can be green at HEAD; all of them land with the module. In `tests/test_roadmap_evidence_store.py`, the parametrized cases change behavior (they gain a third member) only once the enum member exists.

### Tests for this step

**`tests/test_roadmap_evidence_store.py`** (2 cases added or extended):

- `test_decision_settlement_namespace_has_fixed_components` — `namespace_relative_components(EvidenceNamespace.DECISION_SETTLEMENTS) == (".plan-tool", "evidence", "decision-settlements")`.
- `test_namespaces_isolate_identical_final_names` (extended) — the same final name published in all three namespaces keeps three separate records.

**`tests/test_roadmap_decision_settlement_receipt.py` — record (pure):**

- `test_receipt_id_is_the_hash_of_its_semantic_fields` — `receipt_id == compute_input_hash(<fields>)` and `final_name == receipt_id`.
- `test_same_candidate_renders_the_same_bytes_every_time` — two builds and renders give equal bytes. Pins the no-timestamp decision.
- `test_changing_any_recorded_fact_changes_the_final_name` (parametrized over every semantic field).
- `test_unenrolled_receipt_keeps_explicit_null_version_bindings` — the rendered JSON has `"predecessor_version_id":null` and `"resulting_version_id":null`.
- `test_builder_refuses_a_lineage_mismatch` (parametrized: un-enrolled candidate with a version id; enrolled candidate without one; enrolled with a non-digest id) — `DecisionSettlementReceiptError`.
- `test_render_then_parse_returns_the_same_receipt` — on both lineages.
- `test_parse_rejects_malformed_receipts` (parametrized: not JSON, duplicate member, unknown field, float, wrong `receipt_id`, unsafe id, a lineage with the wrong nulls) — `DecisionSettlementReceiptError`.
- `test_parse_rejects_a_receipt_under_a_different_final_name`.
- `test_receipt_bytes_carry_no_row_prose` — the fixture's `request`, `rationale`, and `proposed_response` strings are absent from the rendered bytes.

**Publication:**

- `test_fresh_receipt_is_committed_before_created` — outcome `created`. `HEAD`'s last commit lists only the settlement receipt's path, and `git status` is clean for that path.
- `test_retry_with_the_same_inputs_reuses_the_committed_final_without_a_second_commit` — `reused`, and the committer is called once in total.
- `test_commit_failure_keeps_the_local_final_and_a_retry_resumes_as_committed_existing`.
- `test_commit_failure_variants_report_commit_failed_and_keep_the_final` (parametrized: non-zero rc, `OSError`, `CalledProcessError`).
- `test_no_worktree_refuses_before_any_evidence_write` (parametrized: no Git repo; roadmap outside the worktree) — `no-worktree`, and no `.plan-tool/evidence` directory exists afterward.
- `test_existing_final_with_different_head_bytes_is_a_collision_and_is_never_overwritten` — a committed receipt whose local file is re-rendered with extra whitespace gives `collision`. The committer is never called, and the local bytes are unchanged.
- `test_invalid_existing_final_is_refused_and_left_in_place` (parametrized: garbage bytes; a valid receipt stored under another receipt's name) — `invalid-existing-receipt`, and the file is unchanged.
- `test_existing_final_with_different_semantic_fields_is_a_collision` — mirrors `test_forged_existing_receipt_with_matching_final_is_collision`.
- `test_storage_outcomes_map_to_named_refusals` (parametrized: `invalid-input` → `storage-rejected`; `write-failed` → `write-failed`).
- `test_success_outcomes_are_exactly_created_reused_and_committed_existing` — pins `DECISION_SETTLEMENT_RECEIPT_SUCCESS_OUTCOMES` and the full `Literal` member set.
- `test_failure_outcomes_carry_no_receipt_id` (parametrized over every failure outcome).
- `test_settlement_receipts_live_only_in_their_own_namespace` — the final sits under `decision-settlements`, and the escalations namespace is never created.
- `test_head_state_reads_the_settlement_namespace_path` — after a commit, `receipt_head_state(..., namespace=DECISION_SETTLEMENTS)` is `matching`, while the default namespace reports `missing` for the same final name. This pins the new keyword arm.

**Read-back:**

- `test_unenrolled_receipt_proves_while_the_stage_holds_the_settled_bytes` — `True`.
- `test_unenrolled_receipt_from_an_interrupted_attempt_does_not_prove` — the stage still holds the predecessor bytes → `False`.
- `test_unenrolled_proof_ends_on_a_later_edit_to_the_same_artifact` (parametrized: another decision settled; the rationale revised) — `False`.
- `test_deleting_the_cited_feedback_row_ends_the_unenrolled_proof_though_the_baseline_still_admits` — the fixture shows `admit_baseline_backed_source` still accepts the edited source. The read-back is `False`.
- `test_missing_stage_file_does_not_prove`.
- `test_any_pending_generation_means_not_proven` (parametrized over lineage) — the content matches, but a journal exists → `False`.
- `test_enrolled_receipt_proves_while_its_version_is_the_head`.
- `test_enrolled_proof_survives_a_later_promotion` — the head moves to a child whose predecessor is the receipt's version → `True`.
- `test_enrolled_receipt_whose_version_was_never_stored_does_not_prove` — the interrupted-attempt shape → `False`.
- `test_enrolled_receipt_naming_a_version_off_the_head_chain_does_not_prove` — a sibling version is stored but is not an ancestor.
- `test_enrolled_version_with_a_different_member_digest_or_predecessor_does_not_prove` (parametrized).
- `test_enrolled_receipt_on_an_unenrolled_roadmap_does_not_prove`.
- `test_unenrolled_receipt_after_enrollment_compares_the_accepted_member` — `True` while the root member digest equals the settled digest; `False` after a promotion changes that member.
- `test_enrolled_readback_never_reads_stage_files` — the injected stage's `artifact_path` raises if called.
- `test_corrupt_version_store_raises_rather_than_reporting_false` — `RoadmapVersionError`.

**Seam and discipline:**

- `test_receipt_built_from_a_real_preflight_candidate_names_its_settled_digest` — step 2's builder, then this builder. `resulting_artifact_digest == sha256(candidate.settled_bytes)`.
- `test_module_never_imports_the_cli_computes_a_version_or_deletes_files` — a source scan for `plan_tool.cli`, `create_candidate_version`, `unlink`, `rmtree`, and `os.remove`.

That is approximately 38 cases in the new file and 2 in the evidence-store file. Every one must be green before this step counts as finished, and so must `uv run pytest tests/ -q -n auto`, which includes `tests/test_duplication.py` and the unchanged escalation, structural-revision, and impact-run suites.

**Verify by breaking the code, not by reading it.** Each break below must turn at least one case red:

| Deliberate break | Case that must go red |
| --- | --- |
| Add a `created_at` field | same-bytes-every-time |
| Publish before the worktree check | no-worktree-before-any-write |
| Overwrite an existing final on a mismatch | collision-never-overwritten |
| Treat `write-failed` as a success, or fold it into `storage-rejected` | storage-outcomes mapping |
| Compare the un-enrolled proof through baseline admission | deleted-cited-feedback case |
| Accept only the current head on the enrolled lineage | survives-a-later-promotion |
| Ignore the pending journal | pending-generation case |
| Read the stage file for an enrolled receipt | never-reads-stage-files |
| Hard-code the escalations path inside `receipt_head_state` | settlement-namespace head-state case |

## Acceptance criteria

- `namespace_relative_components(EvidenceNamespace.DECISION_SETTLEMENTS)` returns `(".plan-tool", "evidence", "decision-settlements")`.
- `build_decision_settlement_receipt` returns equal receipts and `render_decision_settlement_receipt` returns equal bytes for equal inputs. The rendered JSON has no `created_at` key.
- An enrolled receipt carries a `resulting_version_id` supplied by the caller. An un-enrolled receipt carries an explicit `null` for it and for `predecessor_version_id`.
- `publish_decision_settlement_receipt` returns only the nine outcomes in the Publication outcomes table. A success outcome is exactly one of `created`, `reused`, and `committed-existing`.
- A first publication commits only the receipt's path to `HEAD` before returning `created`. A same-input retry returns `reused` without a second commit.
- `no-worktree` leaves no evidence directory. No failure outcome removes or rewrites an existing final.
- `decision_settlement_receipt_proves_completion` returns:
  - `True` for an enrolled receipt whose version is an ancestor of a newer head;
  - `False` for an un-enrolled receipt after the cited feedback row is deleted;
  - `False` while any pending generation exists.
- `rg -n "plan_tool\.cli|create_candidate_version|unlink|rmtree|os\.remove|created_at|proposed_response" plan_tool/roadmap_decision_settlement_receipt.py` returns nothing.
- `git diff --stat` shows no change to `plan_tool/roadmap_structural_revision.py`, `plan_tool/roadmap_impact_run.py`, `plan_tool/cli/roadmap_cmd.py`, `plan_tool/roadmap_escalation.py`, `plan_tool/cli/gitcommit.py`, `tests/test_roadmap_escalation_run.py`, or `.gitignore`.
- `receipt_head_state` and `receipt_path_is_within_worktree` accept a keyword-only `namespace` whose default is `EvidenceNamespace.ESCALATIONS`.
- `uv run pytest tests/test_roadmap_decision_settlement_receipt.py tests/test_roadmap_evidence_store.py tests/test_roadmap_escalation_run.py -q` passes, and `uv run pytest tests/ -q -n auto` passes.

## References

- `plan_tool/roadmap_escalation_run.py` (`run_roadmap_escalation_receipt`, `_map_storage_result`, `_classify_existing`, `_commit_receipt`, `receipt_head_state`, `receipt_worktree_for_plans_dir`) — the committed-receipt sequence this publisher follows, and the Git primitives it reuses.
- `plan_tool/roadmap_escalation.py` (`EscalationReceipt`, `build_receipt`, `render_receipt`, `parse_receipt`) — the redacted, hash-named receipt shape this record follows, and the `OPEN`-only builder it cannot reuse.
- `plan_tool/cli/gitcommit.py:commit_receipt` — the path-limited commit the runners pass in.
- `plan_tool/roadmap_evidence_store.py` and `docs/ARCHITECTURE.md` § "Immutable roadmap evidence" — the create-once storage contract the new namespace inherits.
- `plan_tool/roadmap_versions.py` (`load_accepted_head`, `load_stored_version`, `StoredRoadmapVersion`, `create_candidate_version`) — the predecessor chain the enrolled proof walks, and the pure record builder step 5 uses to compute the id this receipt records.
- `plan_tool/roadmap_escalation_selection.py` (`CanonicalArtifactSnapshot.source_digest`) — the raw-byte digest rule behind `predecessor_digest` and the un-enrolled proof.

## Applicable guardrails

- **The plan's "## Scope guardrails": no judgment of whether cited feedback is genuine approval.**
  - The receipt records the feedback id and digest only, and the read-back never looks at `request` text.
  - The tempting site is the builder, where copying the row's text "for the audit trail" looks harmless.
  - Checked by the no-row-prose case and the `rg` criterion.
- **The plan's "## Scope guardrails": the cited feedback row's state never changes.**
  - This module writes only the evidence namespace and the Git commit. It never touches a canonical artifact.
- **The plan's "## Scope guardrails": on an enrolled roadmap, no accepted-head write outside the guarded swap, no synthetic candidate/review/seal chain, and no candidate evidence entries.**
  - The read-back only reads the version store.
  - The builder records a version id without building a version, which is why `create_candidate_version` is banned from this module by the `rg` criterion.
- **The plan's "## Scope guardrails": no route for citing feedback recorded after enrollment.**
  - The enrolled proof walks stored versions and never reads a stage file, pinned by the never-reads-stage-files case.
- **The plan's "## Out of scope": no recovery of an interrupted or malformed journal.**
  - The read-back treats an in-flight journal as "not proven" and lets a malformed one raise.
  - It never repairs one, and the publisher never runs `recover_roadmap_publication`.

## Deferred

- **Calling the publisher before the canonical write, inside the writer lease, after journal recovery and preflight; mapping the outcome to the runner's result; the default `commit_receipt` wiring; run-log events; and `KeyboardInterrupt` handling** — steps 4 and 5, which own the runners.
- **Computing `resulting_version_id`**, including the settlement-owned `content_identity` and the no-review sentinel — step 5.
- **Describing the third `EvidenceNamespace` and this module in `docs/ARCHITECTURE.md`, and stating in the roadmap docs that deleting the cited feedback row ends an un-enrolled receipt's proof** — step 7.
- **A CLI surface to list or check settlement receipts**, like the escalation receipt listing in `plan_tool/cli/roadmap_cmd.py` — no step in this plan owns one. File it in `BACKLOG.md` if wanted.
- **Sharing one lifecycle mapping between escalation and settlement receipts** — out of this step. The two differ in receipt type, parse and validation calls, and result type. Any merge needs a `BACKLOG.md` entry with machine-verified identity evidence and its excluded look-alikes, not a change here.
- **A digest history that would let an un-enrolled receipt's proof outlive later edits** — outside this plan, a stated limit rather than a gap.
