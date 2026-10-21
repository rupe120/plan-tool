# Step 2 — Add the read-only decision-settlement preflight leaf `plan_tool/roadmap_decision_settlement.py`

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds `plan_tool/roadmap_decision_settlement.py` and its test file. The new module is a read-only leaf that proves one settlement request is safe before any runner writes anything. It parses a decision selector and an evidence selector, then reads the selected artifact from the source that fits the roadmap's lineage. On an un-enrolled roadmap that source is the on-disk stage file, admitted against its baseline first. On an enrolled roadmap it is the accepted version's stored bytes. The module then checks the decision and the cited feedback row. It returns either a candidate or a refusal. A candidate carries the predecessor digest, an evidence digest, and the settled bytes built with step 1's `settle_pending_decision`. A refusal carries exactly one named verdict.

The key design decision is how evidence is matched. It counts only when `target.kind is FeedbackTargetKind.ROW and target.row_id == <decision id>` and `request` is not blank, in any `FeedbackState`. For that reason the existing receipt selector `select_receipt_feedback` is deliberately not reused, because it refuses any row that is not `open`. A companion currency check rebuilds the candidate from a fresh read and reports whether anything moved. On green, steps 4 and 5 can call both functions inside their writer lease.

## Table of Contents

- [Why](#why) — why the two settlement runners need one shared preflight, and why no existing preflight fits
- [Input](#input) — the step-1 helper, source-reading primitives, and row types this leaf builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files and the neighbors that stay unchanged
- [Implementation](#implementation) — the public surface, the refusal vocabulary, the check order, the currency check, and the leaf rules
- [Tests](#tests) — the named cases, the fixture approach, and the breaks each case must catch
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer can run
- [References](#references) — plan-level references that bear on this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this leaf, and where breaking them is tempting
- [Deferred](#deferred) — refusal classes and neighboring work owned by later steps

## Why

No code path at HEAD can decide whether a decision may be settled. Each nearby precedent answers a different question:

- `plan_tool/roadmap_feedback_reopen.py:build_feedback_reopen_candidate` proves that a feedback row may reopen, and its runner works only on an un-enrolled roadmap.
- `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback` admits only an `open` row with no `proposed_response`. That refuses this plan's motivating case: a `--revise-feedback` reply leaves the row `awaiting-review` with a response set.
- `plan_tool/roadmap_revision.py:preflight_feedback_revision` gates on `FeedbackState.OPEN`, and its field allowlist never includes `status`.

Steps 4 (un-enrolled write) and 5 (enrolled write) both need the same answer, and both must ask it again inside their writer lease just before writing. If each runner worked out that answer itself, the refusal names, the check order, and the rule for reading enrolled content would each exist twice and could drift apart. This step gives them one owner. Step 3's receipt also records the facts this step proves. Step 6's cross-lineage assertion relies on both lineages building the same settled bytes from the same source, and only one shared builder makes that true.

## Input

- **Step 1's `settle_pending_decision(artifact, *, decision_id)`** (`plan_tool/roadmap_artifacts.py`).
  - It returns a copy of the artifact with one Roadmap-derived `pending` row moved to `settled`, and the rendered text changes by exactly one line.
  - Its `ValueError`s are a backstop. This leaf pre-checks every one of them under a named verdict.
  - Step 1 has a detail file but has not run at HEAD. Read the helper's name off the landed module; the landed name wins over this file.
- **`plan_tool/roadmap_escalation_selection.py:canonical_artifact_snapshot(source_bytes, parse, render)`** returns one of five snapshot types. Only `CanonicalArtifactSnapshot` proves `render(parse(bytes)) == bytes`. Its `source_digest` is the SHA-256 of the raw bytes.
- **`plan_tool/roadmap_escalation_selection.py:admit_versioned_artifact_source(snapshot, *, plans_dir, roadmap_slug, stage_key)`** returns `VersionedArtifactAdmission | None`.
  - It returns `None` for:
    - an unreadable or unparsable snapshot;
    - a missing baseline;
    - a projection that drifted from the baseline;
    - a pending generation that touches this stage's baseline. `admit_baseline_backed_source` checks this by default.
  - It **accepts noncanonical snapshots**, so the render-canonical check has to be a separate step.
  - It compares `canonical_projection`, which leaves out `feedback`. A feedback-only edit therefore passes admission.
- **`plan_tool/roadmap_versions.py:load_accepted_version(*, plans_dir, slug)`** returns `ResolvedRoadmapVersion | None`.
  - It returns `None` only when no accepted head exists.
  - It raises `RoadmapVersionError` for a malformed head, a record that does not match, or a member whose bytes fail their recorded digest.
  - `artifact_bytes` lines up with `artifact_keys` (in `VERSION_ARTIFACT_INVENTORY` order), and `record.version_id` is the head's identity.
  - `plan_tool/roadmap_view.py:load_roadmap` already reads enrolled content from this source. It touches neither candidate evidence loader.
- **Shared selector primitives** (`plan_tool/roadmap_feedback.py`):
  - `parse_feedback_selector(value, artifact_keys)` handles the `<artifact-key>:<id>` grammar;
  - `is_receipt_safe_id` checks `RECEIPT_SAFE_ID_RE`;
  - `matching_feedback_rows` finds feedback rows by id.
- **`plan_tool/roadmap_artifacts.py:design_row_collections(artifact)`** returns every design-row collection. A `ROW` feedback target is matched against this whole set; `select_receipt_feedback` counts target matches across it for the same reason.
- **`FeedbackRow`**. `request` holds the reviewer's own words. It can parse blank, because `_text_at` treats blank prose as a gate's judgment rather than a shape error. `proposed_response` is model-authored.
- **`plan_tool/roadmap_source_identity.py:feedback_snapshot(artifact)`** computes the repo's canonical-JSON digest over an artifact's feedback rows. It accepts any dataclass or mapping that carries `feedback`.
- **The stage table** is `plan_tool/roadmap.py:STAGES`, whose `RoadmapStage` carries `artifact_key`, `artifact_path`, `parse`, and `render`.
  - This leaf must not import `plan_tool.roadmap`, because that module imports `plan_tool.shell`, the backend seam.
  - `plan_tool/roadmap_revision_publish.py:_RoadmapStage` is the in-repo precedent for a structural `Protocol` that stands in for the stage type.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_decision_settlement.py` — the selector type, the candidate and refusal types, the closed verdict vocabulary, and three public functions.
  - `tests/test_roadmap_decision_settlement.py` — the cases listed under Tests.
- **Existing files (edits only):** none. These stay unchanged:
  - `plan_tool/roadmap_escalation_selection.py`: `select_receipt_feedback` keeps its `not-open` / `already-responded` gates.
  - `plan_tool/roadmap_feedback_reopen.py`, `plan_tool/roadmap_feedback.py`, `plan_tool/roadmap_versions.py`, and `plan_tool/roadmap_revision.py`.
  - `plan_tool/roadmap_artifacts.py`: step 1 owns its only edit.
- **Possible addition:** `tests/test_duplication.py`, only if its guard flags the un-enrolled read as an exact duplicate (see Implementation → Leaf rules).

## Implementation

### Public surface

These names are this step's to choose. Steps 3–6 and step 7's docs read them off the landed module.

- **`DecisionSettlementSelector`** is a frozen dataclass with `artifact_key`, `decision_id`, and `feedback_id`, all three receipt-safe. The evidence row always lives in the decision's artifact, so it gets no artifact field of its own.
- **`DecisionSettlementCandidate`** is a frozen dataclass with these fields:
  - `selector`;
  - `accepted_version_id: str | None` — the lineage. `None` means un-enrolled; otherwise it holds the accepted head's version id the source was read from;
  - `source_digest` — the predecessor digest, the SHA-256 of the exact canonical source bytes. On an enrolled roadmap it equals the accepted record's member digest for that artifact;
  - `evidence_digest` — the canonical digest of the cited feedback row;
  - `settled_artifact` — step 1's helper's result, which is what step 4's `publish_stage_artifact` call takes;
  - `settled_bytes` and `settled_digest` — the rendered UTF-8 bytes and their SHA-256, which steps 3 and 5 consume.
- **`DecisionSettlementRefusal`** is a frozen dataclass with `verdict` only. It is redacted: no `request` text, `proposed_response`, `rationale`, or other row content.
- **`DecisionSettlementRefusalVerdict`** is a `Literal` holding the closed vocabulary below.
- **`resolve_decision_settlement_selector(decision_value, evidence_value, *, artifact_keys)`** returns a selector or a refusal. It is pure, with no filesystem access.
- **`build_decision_settlement_candidate(selector, *, plans_dir, slug, stages)`** returns a candidate or a refusal. It reads files and writes nothing.
- **`decision_settlement_candidate_is_current(candidate, *, plans_dir, slug, stages) -> bool`**.
- **`stages`** is typed with a small local `Protocol` (`artifact_key`, `artifact_path`, `parse`, `render`), mirroring `_RoadmapStage`. Runners pass `plan_tool.roadmap.STAGES`.

### Refusal vocabulary: one name per rejection class

The plan's Testing section owns the numbered case list. This table maps each case this step owns to its verdict.

| Plan Testing case | Verdict(s) | Checked in |
| --- | --- | --- |
| 1 — decision target missing or mismatched | `malformed-decision-selector`, `unknown-artifact`, `missing-decision` | resolver, resolver, build |
| 2 — inherited decision | `inherited-decision` | build |
| 3 — non-pending decision | `decision-not-pending` | build |
| 4 — duplicate decision or feedback id | `duplicate-decision`, `duplicate-feedback` | build |
| 5 — evidence selector missing or mismatched | `malformed-evidence-selector`, `evidence-artifact-mismatch`, `missing-feedback` | resolver, resolver, build |
| 6 — feedback does not target the decision | `feedback-not-targeting-decision` | build |
| 7 — empty `request` | `empty-request` | build |
| 8 — source not admitted (un-enrolled only) | `source-not-admitted` | build |
| 9 — source not render-canonical (both lineages) | `source-not-canonical` | build |
| 10 — id not receipt-safe | `unsafe-selector` | resolver and build |
| 11 — source moved since evidence was read | `source-changed` | named here; runners return it when the currency check is `False` |

- **The grammar names mirror the reopen runner's `malformed-selector` / `unknown-artifact`** (`FeedbackReopenRefusalVerdict`). They are split per selector so the operator can tell which value is wrong.
- **One verdict covers case 6's two shapes** (a row that targets a different row, and one that targets the whole artifact). Both are the same class: the row does not target this decision.
- **Cases 12–15 are not preflight classes.** Deferred names their owners.

### Check order

The order must hold. Each check that returns a refusal skips the rest.

1. **Selector-only checks, with no filesystem access:**
   - decision grammar → `malformed-decision-selector`;
   - decision artifact key not configured → `unknown-artifact`;
   - evidence grammar → `malformed-evidence-selector`;
   - evidence key differs from the decision's key, including an unconfigured key → `evidence-artifact-mismatch`;
   - any of the three ids fails `is_receipt_safe_id` → `unsafe-selector`.

   `build` repeats the `unsafe-selector` check on a hand-built selector before any read, as `build_feedback_reopen_candidate` does.
2. **Pick the lineage and read the source.**
   - **Call `load_accepted_version` first.** Let its `RoadmapVersionError` propagate unchanged.
   - **Enrolled (non-`None`).**
     - Take the member bytes for `selector.artifact_key` from `artifact_bytes`.
     - Never call `stage.artifact_path` and never consult a baseline record. That keeps an enrolled roadmap's citable feedback set exactly what the accepted version carries.
     - A stored member that is undecodable or unparsable must raise `RoadmapVersionError`, the class `load_accepted_version` already raises for a corrupt member. It is a broken immutable store, not an operator refusal. Runners map it to their failure outcome, the way the reopen runner maps `ValueError` to `write-failed`.
   - **Un-enrolled (`None`).**
     - Read the stage file's bytes, take `canonical_artifact_snapshot`, and call `admit_versioned_artifact_source`.
     - `None` → `source-not-admitted`. That covers a missing file, an unreadable or unparsable file, no baseline, a drifted baseline, and a pending generation on this stage.
     - **Admission comes before any row is read.** A drifted source reports `source-not-admitted` even when its rows would also fail.
3. **Render-canonical check, on both lineages.** The snapshot (on an un-enrolled roadmap, `admission.snapshot`) must be a `CanonicalArtifactSnapshot`; otherwise the verdict is `source-not-canonical`. Never normalize or rewrite bytes to make a source canonical.
4. **Decision checks on the parsed artifact:**
   - no row in `decisions` carries the id → `missing-decision`. An id carried only by an entity or another row type is still missing, because it is not a decision;
   - the id matches more than one row across `design_row_collections` → `duplicate-decision`. The check covers every row type because a `ROW` feedback target is matched against every design-row collection: if a decision shares its id with an entity, `row_id == decision_id` no longer names one row. Step 1's helper counts only `decisions`, so this preflight is deliberately stricter;
   - `source is not None` → `inherited-decision`. **This check comes before the status check.** Inherited rows are normally `settled`, so checking status first would hide this verdict. It is the same rule `preflight_feedback_revision` applies to inherited decision rows, with settlement's own name;
   - `status is not DecisionStatus.PENDING` → `decision-not-pending`.
5. **Evidence checks, only after the decision passes:**
   - `matching_feedback_rows` finds no row → `missing-feedback`; more than one → `duplicate-feedback`;
   - `target.kind is FeedbackTargetKind.ROW and target.row_id == selector.decision_id` is false → `feedback-not-targeting-decision`;
   - `not row.request.strip()` → `empty-request`. A whitespace-only request counts as blank, matching reopen's `missing-or-blank-response` check;
   - **No check reads `state` or `proposed_response`.** Every `FeedbackState` is eligible, and a filled `proposed_response` never stands in for a blank `request`.
6. **Build the settled content.**
   - Call `settle_pending_decision(artifact, decision_id=...)`, render it with `stage.render`, and encode the result as UTF-8.
   - Then check the byte contract: the settled bytes differ from the source bytes in exactly one line, and that line changes only from `status: pending` to `status: settled`.
   - A violation raises `ValueError`. It means step 1's contract or the renderer regressed, so no runner may write those bytes.
   - The comparison is meaningful only because step 3 of this order proved `render(parse(source)) == source`.
7. **Compute the evidence digest** with `feedback_snapshot` over a one-row feedback sequence holding only the cited row. One way is `feedback_snapshot(replace(artifact, feedback=(row,))).digest`.
   - Reuse the existing canonical-JSON digest rule; do not add a new hash recipe.
   - The digest depends on the cited row alone. It is therefore the same on both lineages and unchanged by edits to other feedback rows.

### Currency check

- **What it does:** `decision_settlement_candidate_is_current` rebuilds the candidate from a fresh read using `candidate.selector`. It returns `True` only when the rebuild is a candidate with the same `accepted_version_id`, `source_digest`, and `evidence_digest` as the captured one; ledger evidence lives outside the source bytes, so the evidence digest is compared too. Comparing the whole rebuilt candidate with `==` is one acceptable way; it also re-checks the settled bytes against step 1's contract.
- **Any refusal on the rebuild returns `False`.** Runners report `source-changed`. Do not return the rebuild's own verdict, because the operator's request did not change; the source did.
- **Why a digest on top of admission:** admission ignores `feedback`. An edit to any feedback row, including the cited one, passes admission but changes the bytes.
- **Why the version id on an enrolled roadmap:** a new head can leave the selected member's bytes unchanged while other members change. A digest check alone would miss that.
- **A lineage switch returns `False`**, for example a candidate built un-enrolled when the roadmap has since been enrolled.

### Leaf rules

- **First-party imports are exactly** `plan_tool.roadmap_artifacts`, `plan_tool.roadmap_escalation_selection`, `plan_tool.roadmap_feedback`, `plan_tool.roadmap_source_identity`, and `plan_tool.roadmap_versions`.
  - Never `plan_tool.roadmap`: it imports `plan_tool.shell`.
  - Never `plan_tool.roadmap_revision_publish` or `plan_tool.roadmap_feedback_reopen`: the first is the writer layer, and the second imports `plan_tool.roadmap`.
  - Never `plan_tool.cli`.
- **Read-only.** The leaf writes no file, takes no lock, calls no `recover_roadmap_publication`, creates no receipt, and has no confirm parameter. The runners in steps 4 and 5 hold the writer lease and call `build` and the currency check inside it.
- **No invoker seam and no backend call.**
- **Duplication guard.** The un-enrolled read (read bytes → snapshot → admit) looks like `roadmap_feedback_reopen.py:_admitted_stage_source`, which is private and sits behind an import this leaf must not take. If `tests/test_duplication.py` flags an exact duplicate, add an `ALLOWED_DUPLICATE_GROUPS` entry that states the leaf-import reason. Do not import the private helper.

### Rejected alternatives

- **Reusing `select_receipt_feedback` for evidence.** Its `not-open` / `already-responded` verdicts refuse the motivating case, and widening it would change escalation receipts.
- **Reading enrolled content from the on-disk stage file plus its baseline**, the escalation path. On-disk files can hold feedback written after enrollment, which the plan fences out.
- **An evidence digest over only `id` / `target` / `request`.** That needs a new projection recipe. Reusing `feedback_snapshot` keeps one digest rule.
- **Returning the rebuild's verdict from the currency check.** Two names for "the source moved" would split case 11 into several classes.

## Tests

All cases go in `tests/test_roadmap_decision_settlement.py`: approximately 32 test functions, several parametrized.

**Fixture approach:**

- Build rows and artifacts directly (`DomainArtifact`, `DecisionRow`, `FeedbackRow`, `FeedbackTarget`, `EntityRow`).
- Write stage files with the real renderers.
- Write baselines with `baseline_record` + `render_baseline_record`, as `tests/test_roadmap_feedback_reopen.py:_write_baseline` does.
- Build enrolled state by hand with `create_root_version` / `create_candidate_version`, `stored_version_members`, and `render_accepted_head`, as `tests/test_roadmap_view.py:_store_version` and `_select_accepted_version` do.
- **Never build fixtures through step 4's or step 5's writers**, `enroll_roadmap_root`, or `publish_stage_artifact`. Keeping fixtures raw keeps this suite independent of the writers it guards.
- Use `plan_tool.roadmap.STAGES` for ordinary cases, and an injected stage table for the two seam cases.

The module is new, so no case can be green at HEAD. All of them land with the module.

**Selector (pure):**

- `test_resolver_returns_one_selector_for_two_well_formed_same_artifact_values` — `domain:decision-1` + `domain:feedback-1` produce one `DecisionSettlementSelector`.
- `test_malformed_decision_selector_is_refused` (parametrized: non-string, no colon, blank id) — `malformed-decision-selector`.
- `test_malformed_evidence_selector_is_refused` — `malformed-evidence-selector`.
- `test_decision_selector_naming_an_unconfigured_artifact_is_unknown_artifact` — `unknown-artifact`.
- `test_evidence_in_another_or_unknown_artifact_is_an_artifact_mismatch` (parametrized: another configured key, an unconfigured key) — `evidence-artifact-mismatch`.
- `test_unsafe_decision_or_feedback_id_is_refused` (parametrized over which id holds a space) — `unsafe-selector`.
- `test_build_refuses_a_hand_built_unsafe_selector_before_any_read` — the stage's `artifact_path` and a patched `load_accepted_version` both raise if called; the result is `unsafe-selector`.

**Source and lineage:**

- `test_unenrolled_source_without_a_baseline_is_not_admitted` — `source-not-admitted`.
- `test_drifted_unenrolled_source_is_refused_before_any_row_check` — the source drifted from its baseline and also lacks the decision; the verdict is `source-not-admitted`, never `missing-decision`.
- `test_missing_undecodable_or_unparsable_unenrolled_source_is_not_admitted` (parametrized) — `source-not-admitted`.
- `test_admitted_but_noncanonical_source_is_refused` — a hand-filled feedback row not in rendered form. The baseline still matches because feedback is outside the projection; the verdict is `source-not-canonical`.
- `test_enrolled_preflight_reads_the_accepted_version_and_never_the_stage_file` — the injected stage's `artifact_path` raises, there is no baseline directory, and the result is a candidate with `accepted_version_id` set.
- `test_enrolled_feedback_present_only_on_disk_is_missing_feedback` — the cited row exists in the on-disk stage file but not in the accepted version → `missing-feedback`. This pins that post-enrollment feedback is never citable.
- `test_enrolled_noncanonical_accepted_bytes_are_refused` — `source-not-canonical`.
- `test_unparsable_accepted_member_raises_a_version_error_rather_than_refusing` — `RoadmapVersionError`, not a verdict.
- `test_selector_reads_the_artifact_its_key_names` (domain and constraints) — the candidate's `source_digest` matches the named stage's bytes.

**Decision:**

- `test_missing_decision_is_refused` — `missing-decision`.
- `test_an_id_carried_only_by_a_non_decision_row_is_a_missing_decision`.
- `test_duplicate_decision_id_is_refused_rather_than_settling_the_first` (parametrized: two decisions; a decision plus an entity sharing its id) — `duplicate-decision`.
- `test_inherited_decision_is_refused_before_its_status_is_checked` (parametrized: `settled`, `pending`) — always `inherited-decision`.
- `test_already_settled_decision_is_refused` — `decision-not-pending`.
- `test_decision_refusals_come_before_evidence_refusals` — an inherited decision plus a missing feedback id → `inherited-decision`.

**Evidence:**

- `test_missing_feedback_is_refused` — `missing-feedback`.
- `test_duplicate_feedback_id_is_refused` — `duplicate-feedback`.
- `test_feedback_targeting_another_row_or_the_whole_artifact_does_not_target_the_decision` (parametrized: `ROW` naming the decision's anchor entity; `ARTIFACT`) — `feedback-not-targeting-decision`.
- `test_blank_request_is_refused_even_when_a_proposed_response_is_set` (parametrized: `""`, `"   "`) — `empty-request`. This pins that model-authored text never counts as evidence.
- `test_every_feedback_state_is_eligible_evidence` (parametrized: `open`; `awaiting-review` with a `proposed_response`; `deferred`) — a candidate every time. This pins that state is never a gate.

**Candidate and currency:**

- `test_candidate_settles_only_the_selected_rows_status_line` — `settled_bytes` differs from the source in exactly one line (`status: pending` → `status: settled`). It also asserts `source_digest == sha256(source)` and `settled_digest == sha256(settled_bytes)`, and that the `feedback` tuple is unchanged.
- `test_evidence_digest_depends_on_the_cited_row_alone` — editing another feedback row leaves `evidence_digest` unchanged; editing the cited row's `request` changes it.
- `test_both_lineages_build_the_same_settled_bytes_and_evidence_digest` — the same artifact read un-enrolled and enrolled gives equal `settled_bytes`, `source_digest`, and `evidence_digest`.
- `test_a_renderer_that_changes_more_than_the_status_line_raises` — an injected `render` appends a line only when the selected decision is settled → `ValueError`.
- `test_currency_accepts_an_unchanged_source_on_either_lineage` (parametrized) — `True`.
- `test_currency_refuses_a_feedback_only_edit_that_baseline_admission_cannot_see` — the fixture edits source bytes only, never the baseline record → `False`.
- `test_enrolled_currency_refuses_a_new_head_that_leaves_the_selected_artifact_unchanged` — the head moves to a candidate version with an identical domain member and a changed constraints member → `False`.
- `test_currency_refuses_a_lineage_change` — a candidate built un-enrolled, then the roadmap is enrolled with the same bytes → `False`.

**Leaf discipline:**

- `test_module_imports_only_the_artifact_selection_feedback_identity_and_version_leaves` — a source grep, which catches a lazy import, plus a stub-package subprocess `sys.modules` check, which catches a transitive one. This mirrors `tests/test_roadmap_view.py:test_module_imports_only_the_artifact_gates_relations_seed_manifest_and_version_leaves`. The allowed transitive set adds `plan_tool.roadmap_json`.
- `test_module_never_writes_and_never_reads_feedback_state_or_proposed_response` — a source scan for write calls, `roadmap_writer_guard`, `recover_roadmap_publication`, `proposed_response`, and `FeedbackState`.

**Verify by breaking the code, not by reading it.** Each break below must turn at least one case red:

| Deliberate break | Case that must go red |
| --- | --- |
| Read rows from the un-enrolled source before admission | the drifted-source case |
| Swap the inherited and status checks | the inherited-decision case |
| Count the decision id only in `decisions` | the decision-plus-entity duplicate case |
| Refuse non-`open` rows, or reuse `select_receipt_feedback` | the every-state case |
| Fall back to `proposed_response` when `request` is blank | the blank-request case |
| Treat an `ARTIFACT` target as covering every row | the artifact-target case |
| Read the stage file on the enrolled branch | the enrolled never-reads-stage-file case |
| Compare only the artifact digest on an enrolled roadmap | the new-head case |
| Rely on admission alone in the currency check | the feedback-only-edit case |

### Tests for this step

The approximately 32 cases above cover the behavior this step adds: selector parsing, lineage-aware source reading, the refusal vocabulary and its order, the settled-bytes contract, the evidence digest, and the currency check. Every one must be green before this step counts as finished, and so must the full suite. The list adds no cases for writing, receipts, journal recovery, candidate lineages, or gates; later steps own those.

## Acceptance criteria

- `build_decision_settlement_candidate` returns a `DecisionSettlementCandidate` for a Roadmap-derived pending decision cited by a `ROW`-targeted feedback row with a non-blank `request`, on both an un-enrolled and an enrolled roadmap, in every `FeedbackState`.
- Every verdict in the refusal table is returned by its own named case, and no two plan Testing cases share a verdict.
- `inherited-decision` is returned for an inherited row whether it is `settled` or `pending`.
- A drifted un-enrolled source returns `source-not-admitted` even when its rows would also fail a row check.
- On an enrolled roadmap, the candidate is built with no read of any stage file and no baseline record present.
- A feedback row present only in the on-disk file of an enrolled roadmap returns `missing-feedback`.
- `settled_bytes` differs from the canonical source in exactly one line, and a renderer that changes any other line raises `ValueError`.
- `decision_settlement_candidate_is_current` returns `False` in each of these cases:
  - a feedback-only source edit;
  - a new accepted head whose selected member is unchanged;
  - a lineage change.
- `rg -n "^from plan_tool|^import plan_tool" plan_tool/roadmap_decision_settlement.py` lists exactly `roadmap_artifacts`, `roadmap_escalation_selection`, `roadmap_feedback`, `roadmap_source_identity`, and `roadmap_versions`.
- `rg -n "proposed_response|FeedbackState|write_bytes|write_text|atomic_write|roadmap_writer_guard|recover_roadmap_publication" plan_tool/roadmap_decision_settlement.py` returns nothing.
- `rg -n "select_receipt_feedback|preflight_feedback_revision" plan_tool/roadmap_decision_settlement.py` returns nothing.
- The step's diff touches only the two new files. The one exception is `tests/test_duplication.py`, and only when its guard flags the un-enrolled read, with the stated reason.
- `uv run pytest tests/test_roadmap_decision_settlement.py -q` passes, and so does `uv run pytest tests/ -q -n auto`.

## References

- **`plan_tool/roadmap_feedback_reopen.py` and `plan_tool/roadmap_escalation_selection.py`** (`ReceiptSafeSelector`, `CanonicalArtifactSnapshot.source_digest`, `admit_versioned_artifact_source`, `build_feedback_reopen_candidate`, `feedback_reopen_candidate_is_current`) — the shape this leaf's selector, candidate, currency check, and named refusals follow.
- **`plan_tool/roadmap_feedback.py`** (`parse_feedback_selector`, `is_receipt_safe_id`, `matching_feedback_rows`) — the shared grammar and lookups, reused unchanged.
- **`plan_tool/roadmap_versions.py`** (`load_accepted_version`, `ResolvedRoadmapVersion`) and **`plan_tool/roadmap_view.py:load_roadmap`** — the enrolled content source and its existing reader.
- **`plan_tool/roadmap_artifacts.py`** (`DecisionStatus`, `DecisionRow`, `FeedbackRow`, `FeedbackState`, `FeedbackTargetKind`, `design_row_collections`) — the row types and the design-row set a `ROW` target is matched against.
- **`plan_tool/roadmap_revision.py`** (`preflight_feedback_revision`) — the precedent for refusing inherited decision rows unconditionally, and the `OPEN`-only gate this leaf does not copy.

## Applicable guardrails

- **The plan's "## Scope guardrails": evidence is only a named, targeting feedback row with non-blank reviewer `request` text, in any `FeedbackState`.**
  - This binds this step hardest. The tempting site is evidence selection: `select_receipt_feedback` sits one import away and already returns a clean verdict, but its state gates refuse the plan's motivating case.
  - A second temptation is a length or keyword test on `request`.
  - Checked by the every-state case, the blank-request case, and the `rg` criterion over `proposed_response|FeedbackState`.
- **The plan's "## Scope guardrails": only `pending → settled` on exactly one Roadmap-derived row, never an inherited or already-settled row.**
  - The leaf takes one selector with one decision id, checks inheritance before status, and builds the settled content only through step 1's helper.
- **The plan's "## Scope guardrails": no other field and no other row changes.**
  - The one-line byte-contract check stops a regressed helper or renderer before any runner can write.
- **The plan's "## Scope guardrails": the cited feedback row's state never changes.**
  - The leaf writes nothing, and the candidate's `feedback` tuple is the source's own.
- **The plan's "## Scope guardrails": no route for citing feedback recorded after enrollment.**
  - The enrolled branch reads only the accepted version's bytes, pinned by the on-disk-only-feedback case.
- **The plan's "## Out of scope": no judgment of whether cited feedback is real approval, and no journal recovery.**
  - This leaf decides nothing beyond the binary facts in the refusal table, and it calls no recovery.

## Deferred

- **Journal recovery before the preflight (plan Testing case 12)** — steps 4 and 5. Their runners call `recover_roadmap_publication` inside the writer lease before calling this leaf, as the reopen runner does.
- **The admitted, unpromoted candidate-lineage refusal (case 13) and the `check_complete_roadmap_gates` refusal (case 14)** — step 5. Both are enrolled-write conditions, not facts about the selected decision or its evidence.
- **Receipt outcomes (case 15) and which candidate facts the receipt records** — step 3 owns the receipt; step 4 owns the call order.
- **The writer lease, confirm flag, `confirmation-required` / `mode-rejected`, and the CLI flag names** — steps 4 to 6. This leaf fixes only the selector value grammar.
- **The enrolled version id and settlement-owned `content_identity`** — step 5, built from this leaf's `settled_bytes`, `source_digest`, and `evidence_digest`.
- **Describing this module in `docs/ARCHITECTURE.md` and CLAUDE.md's cycle-free import list** — step 7.
- **Folding the read → snapshot → admit sequence that appears in the reopen runner, the escalation runner, and this leaf into one shared helper** — out of this step. The reopen copy is private and sits behind an import this leaf must not take. Any such consolidation needs a BACKLOG entry with machine-verified identity evidence, not a change here.
