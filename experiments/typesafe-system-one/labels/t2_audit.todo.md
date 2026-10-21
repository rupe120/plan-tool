# t2_audit — blind labeling

**Question.** Did the prior edit introduce the problem this finding describes? `yes` = the problem exists only because of text the edit added or changed; `no` = the problem was already present before the edit, or the edit is unrelated.

## 1. `roadmap-decision-settlement|2026-09-18T14:43:52Z|plan-plan-correctness-6334a767`

**Cited step:** 7: Document the settlement route; retire every live hand-edit settlement instruction (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md, RUNBOOK.md, docs/how-to/use-cases.md, integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md, docs/how-to/roadmap.md) with recovery guidance for an operator who already followed that advice; state that --revise-feedback still cannot change status; correct ROADMAP_FORMAT.md's Immutable candidate-version authority block and CAPABILITIES.md's accepted-head-authority statement to name both guarded writers, updating tests/test_roadmap_format.py::test_candidate_policy_reference_keeps_review_inert_until_exact_promotion to match, and separately correct the Decision status paragraph and gate-table row to confine the drift-protection claim to the un-enrolled lineage; add a settlement bullet to CAPABILITIES.md's roadmap entry beside the other roadmap actions, covering both lineages; state all three enrolled settlement limits with their backlog pointers (citable feedback must predate enrollment, backlog entry 394; an admitted candidate lineage the operator never finishes blocks settlement with no way to abandon it, backlog entry 395; non-canonical accepted bytes block settlement with no repair path) and that closing (deleting) the cited feedback row ends an un-enrolled receipt's proof; add the settlement receipt as a third EvidenceNamespace in docs/ARCHITECTURE.md; extend the "Incomplete immutable lifecycle journals" BUG_BACKLOG.md entry to name the new settlement generation shape(s); and remove the settlement BUG_BACKLOG.md entry now that the capability ships

**Finding (plan-correctness, medium):** Step 7's Implementation §1 justifies keeping `docs/how-to/roadmap.md`'s heading numbered `## 4.` by citing two sources t

Step 7's Implementation §1 justifies keeping `docs/how-to/roadmap.md`'s heading numbered `## 4.` by citing two sources that allegedly reference it by section number: `BUG_BACKLOG.md:275` and "`CLAUDE.md`'s reference-docs bullet." The `BUG_BACKLOG.md:275` half is true. The `CLAUDE.md` half is false: CLAUDE.md's `docs/how-to/roadmap.md` reference-docs bullet reads `` `docs/how-to/roadmap.md` — the `roadmap` verb end to end on one real run through automated plan derivation (stage 4) and printed `create --from-existing` lines; § 5 keeps a direct fallback procedure; position **04** is shipped; position **05** (framework lenses) is not `` — it cites **§ 5**, a different section (the position-05 fallback procedure), not §4. The underlying instruction ("keep the section number") is still correct on its own, since `BUG_BACKLOG.md:275` alone justifies it, but the stated rationale names a source that doesn't say what the plan claims it says.

**Suggested action:** Correct the parenthetical in step 7's Implementation §1 (`docs/how-to/roadmap.md` bullet) to cite only `BUG_BACKLOG.md:275` as the reason to keep the section numbered "4", dropping the inaccurate claim about CLAUDE.md's reference-docs bullet.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index 4a7cb059..abe7aaf5 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -28,4 +28,5 @@ steps:
   complexity: low
   change_type: feature
+  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/01-settle-one-decision-helper-plan-tool.md
   status: current
 - id: 2
@@ -38,10 +39,10 @@ steps:
   intent: Prove, before any write, that exactly one live Roadmap-derived pending decision
     was named with no duplicate id in the artifact, that a named live feedback row
-    (no duplicate id either) actually targets it (not just resolves) and carries
-    non-empty reviewer-authored `request` text in any FeedbackState (never
-    model-authored `proposed_response`), that an un-enrolled source is admitted
-    against its recorded baseline and is render-canonical, and that the source bytes
-    (on-disk artifact for an un-enrolled roadmap) and, on an enrolled roadmap, the
-    accepted head's own identity have not moved since the evidence was read.
+    (no duplicate id either) actually targets it (not just resolves) and carries non-empty
+    reviewer-authored `request` text in any FeedbackState (never model-authored `proposed_response`),
+    that an un-enrolled source is admitted against its recorded baseline and is render-canonical,
+    and that the source bytes (on-disk artifact for an un-enrolled roadmap) and, on
+    an enrolled roadmap, the accepted head's own identity have not moved since the
+    evidence was read.
   creates:
   - plan_tool/roadmap_decision_settlement.py
@@ -54,4 +55,5 @@ steps:
     1: the transition helper the preflight's candidate is built against, and the byte-preservation
       contract its staleness recheck re-verifies
+  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/02-decision-settlement-preflight-leaf-that.md
 - id: 3
   title: Add the immutable settlement receipt record, its own evidence namespace in
@@ -66,10 +68,9 @@ steps:
     to the same already-published final, an existing final is returned rather than
     overwritten, and nothing is deleted
-  intent: Make every successful settlement leave a durable, readable, committed
-    record — created before the canonical write it proves, never after — of which
-    artifact, decision, predecessor digest, feedback evidence, and resulting content
-    digest justify it, with a shipped check (not a manual procedure) for whether that
-    proof still holds later, so a receipt never outlives or outraces the settlement
-    it names.
+  intent: Make every successful settlement leave a durable, readable, committed record
+    — created before the canonical write it proves, never after — of which artifact,
+    decision, predecessor digest, feedback evidence, and resulting content digest
+    justify it, with a shipped check (not a manual procedure) for whether that proof
+    still holds later, so a receipt never outlives or outraces the settlement it names.
   files:
   - plan_tool/roadmap_evidence_store.py
@@ -85,13 +86,13 @@ steps:
     2: the admitted selector, evidence identity, and source digest that are the receipt's
       recorded facts
+  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/03-immutable-settlement-receipt-record-its.md
 - id: 4
   title: Settle one decision on an un-enrolled roadmap by publishing its receipt first,
-    then, once source admission and staleness both hold, publishing through
-    publish_stage_artifact's multi-member generation with its default seed-invalidation
-    behavior (never invalidate_seeds=False), keeping the existing journal recovery
-    (roll back or drop an in-flight generation) unchanged and updating the selected
-    artifact's bytes, its stage baseline record, and tracked derived seed state (marked
-    invalidated, exactly like any other stage-level content change) together — no
-    other artifact or stage is rewritten
+    then, once source admission and staleness both hold, publishing through publish_stage_artifact's
+    multi-member generation with its default seed-invalidation behavior (never invalidate_seeds=False),
+    keeping the existing journal recovery (roll back or drop an in-flight generation)
+    unchanged and updating the selected artifact's bytes, its stage baseline record,
+    and tracked derived seed state (marked invalidated, exactly like any other stage-level
+    content change) together — no other artifact or stage is rewritten
   intent: Let an operator settle an approved decision on an ordinary roadmap by naming
     it, naming its evidence, and confirming — with no hand-edit of a canonical artifact,
@@ -112,4 +113,5 @@ steps:
       recheck, called inside the writer lease before the artifact is replaced
     3: the receipt writer, called before the artifact write, not after
+  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/04-settle-one-decision-on-un-enrolled.md
 - id: 5
   title: Settle one decision on an enrolled roadmap by storing the settled artifact
@@ -121,15 +123,17 @@ steps:
     but never calls _load_complete_sealed_candidate or either evidence loader; recovers
     a recognized completed version-owned generation exactly as existing recovery does
-    and refuses anything else; refuses whenever the current accepted head carries an
-    admitted, unpromoted candidate lineage (permanently, if that lineage never resolves);
-    root-enrollment and review-seal-promotion recovery stay exactly as they are, and
-    stored version members are never overwritten or deleted
+    and refuses anything else; refuses whenever the current accepted head carries
+    an admitted, unpromoted candidate lineage, clearing only once that same lineage
+    is promoted (nothing time-bounds a response-rejected retry or an unanswered question,
+    and no route abandons the admission early); root-enrollment and review-seal-promotion
+    recovery stay exactly as they are, and stored version members are never overwritten
+    or deleted
   intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one,
     for a decision whose approving feedback already exists in the accepted version
-    (nothing can add feedback to an enrolled roadmap today), without ever editing its
-    accepted head in place, without fabricating a synthetic model-authored
-    candidate/review/seal chain, evidence file, or content_identity to satisfy
-    promote_review_seal's existing preconditions, and without any accepted-head write
-    path outside the guarded selector swap.
+    (nothing can add feedback to an enrolled roadmap today), without ever editing
+    its accepted head in place, without fabricating a synthetic model-authored candidate/review/seal
+    chain, evidence file, or content_identity to satisfy promote_review_seal's existing
+    preconditions, and without any accepted-head write path outside the guarded selector
+    swap.
   files:
   - plan_tool/roadmap_revision_publish.py
@@ -145,4 +149,5 @@ steps:
     4: the shared preflight-to-receipt sequence and the settled-artifact bytes, which
       this step stores as a version instead of writing over the stage file
+  detail: docs/implementation-plans/plan-details/roadmap-decision-settlement/05-settle-one-decision-on-enrolled-roadmap.md
 - id: 6
   title: Add the decision selector, evidence selector, and required confirm flag to
@@ -156,10 +161,10 @@ steps:
   intent: Give the operator the actual command, with the confirm flag that makes settlement
     their decision rather than the tool's and no backend call anywhere on the path,
-    make that exclusivity hold no matter which side names the conflicting option
-    rather than letting a combined command silently run a different action and drop
-    the settlement reques
````

## 2. `roadmap-revision-retention|2026-08-19T13:34:16Z|plan-plan-correctness-763b2170`

**Cited step:** 5: Count closed rows in the roadmap summary and tell the operator to close by setting `state: closed` rather than by deleting

**Finding (plan-correctness, medium):** Step 5's title, "Count closed rows in the roadmap summary," names one of two separate summary renderers without saying w

Step 5's title, "Count closed rows in the roadmap summary," names one of two separate summary renderers without saying which: `_feedback_summary_lines` in `cli/roadmap_cmd.py` (the run/revision post-run summary, the one the Architecture section cites by name and line) and `render_roadmap_summary` / `_summary_feedback_counts` in `roadmap_view.py:1747-1755` (the read-only `--view summary` surface that step 6 renames from `--mode review` to `--mode history` precisely because it now shows retained history). `_summary_feedback_counts` builds its dict from every `FeedbackState` member, so a closed count is already computed without crashing, but the render line at `roadmap_view.py:1750-1752` hard-lists only `open` / `awaiting review` / `deferred` and silently drops it. If step 5 is built against only the cited `cli/roadmap_cmd.py` site, the newly-renamed `--mode history` view — whose whole rationale is that it now surfaces retained history — still hides closed rows in its summary, undercutting the rename step 6 makes for exactly that reason.

**Suggested action:** state explicitly that step 5 covers both feedback-count surfaces (`cli/roadmap_cmd.py:_feedback_summary_lines` and `roadmap_view.py:_summary_feedback_counts`/`render_roadmap_summary`), or say why the `--mode history` surface is deliberately left out.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-revision-retention.md b/docs/implementation-plans/2-roadmap-revision-retention.md
index 6f58492e..71f49c1d 100644
--- a/docs/implementation-plans/2-roadmap-revision-retention.md
+++ b/docs/implementation-plans/2-roadmap-revision-retention.md
@@ -10,13 +10,14 @@ enforce_step_tests: true
 steps:
 - id: 1
-  title: Add the removed row's content snapshot to RemovalRecord, render it back on
-    every artifact rewrite, and require it only on newly declared removals
+  title: Add the removed row's content snapshot to RemovalRecord, populated mechanically
+    from the predecessor's own rendered row content — never model-authored — and
+    rendered back on every artifact rewrite
   intent: So a reader of a revised roadmap can see what the dropped row actually said
-    instead of having to go read git.
+    instead of having to go read git, with no faithfulness question to gate because
+    the render layer derives the snapshot rather than the model paraphrasing it.
   files:
   - plan_tool/roadmap_artifacts.py
   - plan_tool/roadmap_gates.py
   - plan_tool/roadmap_view.py
-  - plan_tool/prompts/roadmap-revision.md
   - tests/test_roadmap_artifacts.py
   - tests/test_roadmap_gates.py
@@ -26,8 +27,10 @@ steps:
   status: current
 - id: 2
-  title: Add the optional decision reference to RemovalRecord, render it back, and
-    check it names a decision the artifact declares
+  title: Add the optional decision reference to RemovalRecord, render it back, check
+    it names a decision the artifact declares, and add it to the revision prompt's
+    removals field list and worked example as a model-suppliable field
   intent: So a removal can point at the decision whose rejected alternatives explain
-    the drop, instead of leaving the reasoning stranded in a separate collection.
+    the drop, instead of leaving the reasoning stranded in a separate collection —
+    and so the model actually knows the field exists to supply it.
   files:
   - plan_tool/roadmap_artifacts.py
@@ -46,8 +49,12 @@ steps:
       join whole-record carry identity.
 - id: 3
-  title: Add `closed` to FeedbackState, keep the reviewer's delete-the-row close working,
-    and replace the gates' 'close by deleting the row' correction text
-  intent: So a reviewer can answer and retire a feedback request in the file itself,
-    and the record of what was asked and how it was answered stays in the artifact.
+  title: Add `closed` to FeedbackState and update the dropped-feedback gate's violation
+    message and the revision prompt's state enum, carry-forward instruction, and
+    "never do" text — all three currently say the only close is deleting the row
+  intent: So a reviewer can retire a feedback request by setting its `state` field
+    to `closed` in the file instead of deleting it, and the record of what was
+    asked and how it was answered stays in the artifact; a reviewer keeps full
+    deletion rights over any row, closed included, so this retention binds only
+    the model's own edits, never the reviewer's.
   files:
   - plan_tool/roadmap_artifacts.py
@@ -60,8 +67,10 @@ steps:
   change_type: feature
 - id: 4
-  title: Add a gate requiring closed feedback rows to come after every other row in
-    the feedback collection
+  title: Add a gate rejecting a revision whose `feedback` collection places a `closed`
+    row before a non-`closed` row, and tell the model in the revision prompt to keep
+    closed rows last when it re-emits the collection
   intent: So the live part of the review queue reads first and retained closed rows
-    accumulate at the end instead of interleaving with open requests.
+    accumulate at the end instead of interleaving with open requests, and the model
+    has the guidance it needs to satisfy the gate on the first attempt.
   files:
   - plan_tool/roadmap_gates.py
@@ -94,8 +103,12 @@ steps:
       `state: closed` is the supported close so the CLI guidance can name it.'
 - id: 6
-  title: Rename `--mode review` to `--mode history`, dropping the `review` spelling
-    from the choices with no alias
+  title: Rename `--mode review` to `--mode history` everywhere it appears — the argparse
+    choices, MODE_REVIEW's branch sites and docstrings in roadmap_view.py (including
+    its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text, and
+    every literal `--mode review` example in README.md, docs/ROADMAP_WALKTHROUGH.md,
+    and docs/ARCHITECTURE.md — dropping the `review` spelling with no alias
   intent: So the flag says what the mode shows now that the collections it surfaces
-    retain history rather than only pending review work.
+    retain history rather than only pending review work, and no operator-facing
+    text anywhere still tells someone to pass a value the parser now rejects.
   files:
   - plan_tool/roadmap_view.py
@@ -113,10 +126,17 @@ steps:
   - 5
 - id: 7
-  title: Document the removal snapshot, the decision reference, the `closed` state,
-    and the closed-last ordering rule in ROADMAP_FORMAT.md
+  title: Document the removal snapshot, the decision reference, and the `closed` state
+    (including the closed-last ordering rule) in ROADMAP_FORMAT.md — correcting all
+    three existing "no `closed` member" sites (the schema block's `state` comment,
+    the Closed vocabularies table, and the feedback-lifecycle's situation 5) rather
+    than adding fresh prose beside them — and correct RUNBOOK.md's close-request
+    table row and "Preserved by the gates" tables to match
   intent: So the review collections' schema is readable without opening the parser,
-    which is what the whole FORMAT-doc family exists to guarantee.
+    which is what the whole FORMAT-doc family exists to guarantee, and so a reviewer
+    who trusts RUNBOOK.md's walkthrough learns the retention path exists instead of
+    being told deletion is still the only way to close a request.
   files:
   - ROADMAP_FORMAT.md
+  - RUNBOOK.md
   - tests/test_roadmap_format.py
   complexity: high
@@ -165,5 +185,8 @@ Three additive changes to the shared review-collection shape:
   content as it stood at removal.
 - `FeedbackState` gains `closed`; closed rows are retained in the `feedback`
-  collection (never deleted) and render last within it.
+  collection — never deleted by the model — and render last within it. A
+  reviewer, editing the file directly before a run, keeps full deletion
+  rights over any row, closed included, exactly as today; retention binds
+  only the model's own edits.
 - `RemovalRecord` gains an optional reference to the `DecisionRow` whose
   `rejected_alternatives` explain the drop.
@@ -204,4 +227,17 @@ retention in the one place `check_feedback_integrity` and
 a second collection would mean two places to look for a feedback id.
 
+**The snapshot is mechanically captured, never model-authored.** When a
+removal is newly declared — its `removed_id` not yet in `carried` — the
+render layer copies the predecessor's own rendered content for that row
+into the snapshot before the artifact is written; the model supplies only
+`removed_id`, `rationale`, and `feedback_ids`, exactly as it does today, and
+step 1 makes no prompt change. This is why `## Not allowed`'s ban on a
+faithfulness gate is safe: there is no faithfulness question to gate,
+because the snapshot is derived from the row's own last-known-good render
+rather than paraphrased. It stays inside BACKLOG #242's "no orchestrator
+change" boundary because the capture is a render-time transform in
+`roadmap_artifacts.py`, not a change to `roadmap.py`'s stage-running
+orchestrator.
+
 **Removal-carry identity is whole-record equality, and the new fields join
 it — this is what makes the fields' immutability enforceable for free.**
@@ -217,4 +253,18 @@ asks the model to touch a carried record afterward. No separate
 immutability gate is needed for these two fields.
 
+A tampered carried removal — one field edited, so it no lo
````

## 3. `roadmap-candidate-vocabulary-retry|2026-09-25T17:38:55Z|plan-plan-correctness-743a296b`

**Cited step:** 1: Show valid collection names and disambiguate existing batch rows

**Finding (plan-correctness, medium):** Step 1 and step 2 both own the same retry behavior, so their completion boundaries conflict. Step 1 says:

Step 1 and step 2 both own the same retry behavior, so their completion boundaries conflict. Step 1 says:
  ```
  Update `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` so parsing or materialization rejection produces one correction prompt and one final model attempt.
  ```
  while step 2 says:
  ```
  Extend `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` so an error from `parse_candidate_delta` or a refusal from `materialize_candidate` receives one correction attempt.
  ```
  Step 1 also requires corrected-success, exhaustion, transport, and storage retry tests that step 2 repeats. Since step 2 depends on step 1, step 1 either ships step 2’s feature early or cannot meet its own acceptance criteria.

**Suggested action:** Make step 1 own only prompt vocabulary and source-bound hints, and make step 2 the sole owner of correction, rejected-response diagnostics, and retry tests.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md b/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md
index c6dcbc51..0fa658a3 100644
--- a/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md
+++ b/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md
@@ -25,8 +25,9 @@ steps:
   complexity: low
   change_type: feature
+  detail: docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/01-show-valid-collection-names.md
   status: current
 - id: 2
-  title: Retry rejected ledger replies once; preserve one candidate
-    publication, guarded pointer and ledger replacements, and exact response receipts
+  title: Retry rejected ledger replies once; preserve one candidate publication, guarded
+    pointer and ledger replacements, and exact response receipts
   intent: Malformed replies get a chance to correct themselves, and exhaustion leaves
     no candidate published.
@@ -39,5 +40,7 @@ steps:
   - 1
   depends_on_notes:
-    1: The first prompt gives both attempts valid row vocabulary and exact existing-row collection hints.
+    1: The first prompt gives both attempts valid row vocabulary and exact existing-row
+      collection hints.
+  detail: docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/02-retry-rejected-ledger-replies-once.md
 - id: 3
   title: Remove the IPPT-10 promotion stub after the behavior and tests ship
@@ -49,4 +52,5 @@ steps:
   depends_on:
   - 2
+  detail: docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/03-remove-ippt-10-promotion-stub-after.md
 ---
 # Roadmap Candidate Vocabulary Retry
diff --git a/docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/01-show-valid-collection-names.md b/docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/01-show-valid-collection-names.md
new file mode 100644
index 00000000..1221a2a5
--- /dev/null
+++ b/docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/01-show-valid-collection-names.md
@@ -0,0 +1,103 @@
+# Step 1 — Show valid collection names and disambiguate existing batch rows
+
+<!-- plan-tool:detail-format-version: 1 -->
+
+## Summary
+
+Make the batch candidate prompt show the collection vocabulary the delta parser accepts and identify the collection for each referenced existing row. Update the prompt-view context and batch proposal flow without changing immutable capsule or receipt bytes. Add bounded correction for rejected model replies so a corrected `entities` operation can store a structural candidate. Green behavior includes two-call exhaustion for repeated malformed replies with no candidate publication.
+
+## Table of Contents
+
+- [Summary](#summary) — Reviewer overview of the prompt and retry change.
+- [Table of Contents](#table-of-contents) — Links to this detail file’s sections.
+- [Why](#why) — The current class-name versus collection-name mismatch.
+- [Input](#input) — Immutable batch and delta contracts this step reads.
+- [Files (creates vs edits)](#files-creates-vs-edits) — Declared file changes.
+- [Implementation](#implementation) — Required prompt hints and bounded retry behavior.
+- [Tests](#tests) — Focused regression and failure-boundary coverage.
+- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
+- [References](#references) — Format and code contracts to consult.
+- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this work.
+
+## Why
+
+`plan_tool/roadmap_candidate_context.py:_row_identity` records Python row-type names such as `EntityRow`, while `plan_tool/roadmap_candidate.py:parse_candidate_delta` accepts collection names such as `entities`. That leaves a model with enough context to identify a row but not enough vocabulary to emit a valid operation, and `PatternRow` has two possible collections. The batch path in `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` currently rejects the first malformed response without giving the model one bounded chance to correct it.
+
+## Input
+
+- **Immutable batch evidence:** Read `CandidateContextBatchCapsule`, `CandidateContextBatchReceipt`, and the payload rendered by `plan_tool/roadmap_candidate_context.py:_render_batch_payload`. Prompt-only guidance must not alter this persisted evidence or its identities.
+- **Operation vocabulary:** Read `plan_tool/roadmap_candidate.py:_ROW_TYPE_NAMES`, `_parse_stage_row`, and `_find_existing_row` as the closed vocabulary and lookup behavior the prompt must help the model satisfy.
+- **Actual collection ownership:** Use `plan_tool/roadmap_artifacts.py:stage_row_collections` to distinguish a row’s real collection, especially `ComponentsArtifact.system_patterns` from `ComponentsArtifact.component_patterns`.
+- **Batch authority:** Preserve the reviewer-item snapshot contract carried by `CandidateContextBatchCapsule.reviewer_items`; hints describe valid operation syntax only and must not add edit authority.
+
+## Files (creates vs edits)
+
+- **New files:** None.
+
+- **Existing files (edits only):**
+  - `plan_tool/roadmap_candidate_context.py` — Add or expose prompt-only collection information derived from the current source artifacts while retaining existing serialized row identities and payload rendering.
+  - `plan_tool/roadmap_candidate_run.py` — Render collection guidance into batch prompts and retry only rejected model content within the fixed proposal budget.
+  - `plan_tool/prompts/roadmap-candidate-delta.md` — Tell the model where to find valid collection names and how existing rows are disambiguated.
+  - `tests/test_roadmap_candidate_run.py` — Cover prompt guidance, successful correction, exhaustion, and terminal failure classification.
+
+## Implementation
+
+- **Keep persisted identities unchanged.** `plan_tool/roadmap_candidate_context.py:_row_identity` and `_row_digest` must retain their current persisted representation. The collection hint is a prompt-view fact, not a new capsule field, receipt field, digest input, replay key, or authority source.
+
+- **Derive collection names from the actual artifact shape.** Use the stage collection ownership exposed by `plan_tool/roadmap_artifacts.py:stage_row_collections` when preparing model-facing guidance. A referenced `EntityRow` must be shown as belonging to `entities`; a referenced `PatternRow` must name the specific collection that contains it. Do not infer a pattern collection from the Python class alone.
+
+- **Show the parser’s accepted vocabulary.** The batch prompt rendered by `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt` must present valid collection names in the form accepted by `plan_tool/roadmap_candidate.py:parse_candidate_delta`. Keep class names invalid rather than normalizing or accepting them.
+
+- **Keep new-pattern choices available.** Show both pattern collection names as valid choices for a new pattern. Existing-row guidance must identify one actual collection; it must not imply that the same `PatternRow` class maps to only one collection globally.
+
+- **Keep prompt guidance outside issued evidence.** A likely approach is to calculate a transient prompt supplement from the resolved source version in the batch run and pass it through `render_candidate_delta_prompt` and `_invoke_once`. Preserve compatible behavior for existing prompt callers, including the review callers in `plan_tool/roadmap_candidate_review.py`, unless they supply the new prompt-only input.
+
+- **Retry only rejected model content.** Update `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` so parsing or materialization rejection produces one correction prompt and one final model attempt. The correction must explain the rejected response using the same closed operation contract and must not change the issued batch, source version, or reviewer-item authority.
+
+- **Use one shared two-call budget.** A malformed response followed by a 
````

## 4. `roadmap-decision-settlement|2026-09-18T02:00:16Z|plan-plan-completeness-90fe7179`

**Cited step:** 8: Document the settlement route, retire the hand-edit instruction it replaces, state that --revise-feedback still cannot change status, and remove the BUG_BACKLOG.md entry now that the capability ships

**Finding (plan-completeness, medium):** Step 8 (document the settlement route) promises "no reader is still told to hand-edit a canonical artifact", but its fil

Step 8 (document the settlement route) promises "no reader is still told to hand-edit a canonical artifact", but its files and acceptance criterion miss three live docs that still tell readers to settle by hand:
  - `README.md`: "Settle one by editing its `status` to `settled` in place; that edit *is* the resolution."
  - `docs/how-to/common-workflows.md`: the same sentence.
  - `docs/how-to/roadmap-demo.md`: "settle one through a direct edit if needed".

  The acceptance criterion names only `ROADMAP_FORMAT.md` and `docs/how-to/roadmap.md`, though step 8's files also include `integrations/shared/DIRECTIVES.md` ("Settle a `pending` decision by editing its `status` in place") and `CAPABILITIES.md`. The intended wording also conflicts. Step 8's title says "retire the hand-edit instruction", while the criterion only says docs "no longer instruct a hand-edit as the only path". Step 1 keeps every existing write path, so a hand edit plus re-entry still works on an un-enrolled roadmap, and the plan never says whether docs keep it as an alternative.

**Suggested action:** List every live hand-edit settlement instruction in step 8's files and acceptance criterion: `README.md`, `docs/how-to/common-workflows.md`, `docs/how-to/roadmap-demo.md`, `integrations/shared/DIRECTIVES.md`, `ROADMAP_FORMAT.md`, and `docs/how-to/roadmap.md`, with the `DecisionStatus` docstring kept in step 1. State once whether docs present the hand edit as a still-working alternative or drop it.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index e2972409..8f8f0d5b 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -142,9 +142,11 @@ steps:
       head
 - id: 7
-  title: Prove both lineages produce the same settled row and that check_settled_decisions
-    still refuses drift on a row this route settled
+  title: Prove both lineages produce the same settled row, that check_settled_decisions
+    refuses drift on an un-enrolled settled row, and document that the same protection
+    does not yet exist on the enrolled lineage (tracked separately in BUG_BACKLOG.md)
   intent: Show the enrolled and un-enrolled paths are one capability rather than two
-    look-alikes, by asserting identical before/after row content across both, instead
-    of settling for parallel 'it runs' coverage.
+    look-alikes, by asserting identical before/after row content across both, and
+    state plainly rather than silently which lineage's settled decisions are actually
+    protected from later drift.
   files:
   - tests/cli/test_roadmap_cmd.py
@@ -361,7 +363,16 @@ evidence-bound shape every other narrow roadmap action already has.
   extend `TEXT_FIELDS_BY_ROW_TYPE` or route through this generic,
   unconfirmed, evidence-free `--revise-feedback` path.
-- `plan_tool/roadmap_gates.py` (`check_settled_decisions`) — the complementary
-  gate that must keep making a settled decision immutable once this route
-  produces one.
+- `plan_tool/roadmap_gates.py` (`check_settled_decisions`) and
+  `plan_tool/roadmap_impact_snapshot.py` (`_evaluate_full_roadmap_gates`) —
+  `check_settled_decisions` genuinely protects a settled decision against
+  later drift on the un-enrolled lineage, where ordinary revision/reconcile
+  paths build a real `predecessor`. `_evaluate_full_roadmap_gates` —
+  the evaluator every enrolled candidate promotion runs through — always
+  builds `predecessor=None`, so `check_settled_decisions` is a permanent
+  no-op there; this is a pre-existing gap (tracked as its own
+  `BUG_BACKLOG.md` entry, "An enrolled roadmap's candidate promotion never
+  re-checks a settled decision against its predecessor"), not one this plan
+  creates or fixes, and step 7 only demonstrates the protection that
+  actually exists.
 - `plan_tool/roadmap_feedback_reopen.py` and
   `plan_tool/roadmap_escalation_selection.py`
@@ -369,11 +380,18 @@ evidence-bound shape every other narrow roadmap action already has.
   `FeedbackSelector`) — the structural precedent this route's selector,
   predecessor-digest staleness check, and named-reason refusal shape should
-  follow; both are wired only for an un-enrolled roadmap today via
-  `require_unenrolled_roadmap_writer` (`plan_tool/roadmap_revision_publish.py`),
-  confirming the enrolled side has no narrow-route precedent to reuse as-is.
-  Neither touches `.roadmap-baselines`, because feedback is the one thing
-  `canonical_projection` excludes from the digest; a decision's `status` is
-  not excluded, so the un-enrolled write must instead follow
-  `plan_tool/roadmap_revision_publish.py:publish_stage_artifact`'s
+  follow. `roadmap_feedback_reopen.py`'s canonical-artifact write is wired
+  only for an un-enrolled roadmap via `require_unenrolled_roadmap_writer`
+  (`plan_tool/roadmap_revision_publish.py`), confirming the enrolled side
+  has no canonical-artifact-mutation precedent to reuse as-is — this is
+  what step 5 must build fresh. `roadmap_escalation_selection.py` and its
+  runner `roadmap_escalation_run.py`, by contrast, call no writer guard and
+  check no enrollment state at all: escalation-receipt creation already
+  works unchanged on an enrolled roadmap because it writes only into the
+  immutable evidence store, never a canonical artifact — an already-working
+  enrolled-and-un-enrolled precedent for step 3's evidence-namespace
+  receipt write. Neither touches `.roadmap-baselines`, because feedback is
+  the one thing `canonical_projection` excludes from the digest; a
+  decision's `status` is not excluded, so the un-enrolled write must
+  instead follow `plan_tool/roadmap_revision_publish.py:publish_stage_artifact`'s
   multi-member generation, which updates the artifact and its baseline
   record together.
@@ -462,4 +480,11 @@ See the `steps:` block in the frontmatter.
   mistake must get the same refusal `preflight_feedback_revision` already
   gives other inherited-row edits, not a new, differently-worded one.
+- **Overclaimed enrolled protection:** `_evaluate_full_roadmap_gates` (the
+  evaluator every enrolled candidate promotion runs through) always builds
+  `predecessor=None`, so `check_settled_decisions` is a permanent no-op on
+  the enrolled lineage — a pre-existing gap this plan is the first to make
+  reachable, tracked as its own `BUG_BACKLOG.md` entry. This plan must not
+  claim or test a drift protection on the enrolled lineage that does not
+  exist; state the gap plainly instead.
 
 ## Testing
@@ -489,6 +514,9 @@ the settlement receipt records the artifact key, decision id, predecessor
 digest, and cited feedback id/digest, and that a legacy roadmap with no
 receipts directory still parses and settles correctly. Confirm
-`check_settled_decisions` still refuses drift on the row this route just
-settled.
+`check_settled_decisions` refuses drift on an un-enrolled row this route
+just settled. Do not test or claim the same protection on the enrolled
+lineage: `_evaluate_full_roadmap_gates` always builds `predecessor=None`,
+so `check_settled_decisions` is a documented no-op on every enrolled
+candidate promotion today (tracked separately in `BUG_BACKLOG.md`).
 
 ## Acceptance criteria
@@ -509,4 +537,8 @@ settled.
   enrolled write never constructs a synthetic model-authored
   candidate/review/seal chain.
+- `check_settled_decisions` is demonstrated to refuse drift on an
+  un-enrolled settled row. The plan documents, rather than silently
+  overclaims, that the enrolled lineage has no equivalent protection today
+  (a pre-existing gap tracked in `BUG_BACKLOG.md`, not fixed by this plan).
 - A durable receipt exists after every successful settlement and can be read
   back to prove which evidence justified it.
@@ -520,4 +552,10 @@ settled.
 A symmetric "un-settle" / reopen route for a `settled` decision, BACKLOG
 #242's feedback-closing work, and any repair path for a malformed immutable
-lifecycle journal all remain separate efforts. File any newly discovered gap
-in `BACKLOG.md` or `BUG_BACKLOG.md` rather than expanding this plan.
+lifecycle journal all remain separate efforts. Also deferred: giving
+`_evaluate_full_roadmap_gates` a real predecessor so `check_settled_decisions`
+actually protects a settled decision against a later enrolled candidate
+promotion — a pre-existing gap this plan is the first to make reachable,
+filed as its own `BUG_BACKLOG.md` entry rather than bundled into this
+feature, since it changes the shared evaluator every candidate promotion
+runs through. File any newly discovered gap in `BACKLOG.md` or
+`BUG_BACKLOG.md` rather than expanding this plan.

````

## 5. `roadmap-candidate-vocabulary-retry|2026-09-25T17:38:55Z|plan-plan-correctness-bceb3caf`

**Cited step:** 1: Show valid collection names and disambiguate existing batch rows

**Finding (plan-correctness, high):** Step 1 leaves stored-batch model calls without the required source-bound hint route. Architecture says:

Step 1 leaves stored-batch model calls without the required source-bound hint route. Architecture says:
  ```
  The same resolution applies when a stored batch is replayed into a new model call.
  ```
  but step 1 says:
  ```
  Preserve compatible behavior for existing prompt callers, including the review callers in `plan_tool/roadmap_candidate_review.py`, unless they supply the new prompt-only input.
  ```
  `roadmap_candidate_review._invoke_replacement` and `run_structural_candidate_edit` call `render_candidate_delta_prompt` from stored capsule/receipt data, while that renderer has no source-resolution input; step 1’s tests also omit the promised replay and source-binding-refusal cases. The implementation can therefore satisfy fresh-batch hints while a stored batch is replayed with no verified collection hint.

**Suggested action:** Define the source-bound prompt-hint route for every stored-batch model call, including refusal before invocation when its recorded source or row membership cannot be proved, and cover replayed calls.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md b/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md
index c6dcbc51..0fa658a3 100644
--- a/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md
+++ b/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md
@@ -25,8 +25,9 @@ steps:
   complexity: low
   change_type: feature
+  detail: docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/01-show-valid-collection-names.md
   status: current
 - id: 2
-  title: Retry rejected ledger replies once; preserve one candidate
-    publication, guarded pointer and ledger replacements, and exact response receipts
+  title: Retry rejected ledger replies once; preserve one candidate publication, guarded
+    pointer and ledger replacements, and exact response receipts
   intent: Malformed replies get a chance to correct themselves, and exhaustion leaves
     no candidate published.
@@ -39,5 +40,7 @@ steps:
   - 1
   depends_on_notes:
-    1: The first prompt gives both attempts valid row vocabulary and exact existing-row collection hints.
+    1: The first prompt gives both attempts valid row vocabulary and exact existing-row
+      collection hints.
+  detail: docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/02-retry-rejected-ledger-replies-once.md
 - id: 3
   title: Remove the IPPT-10 promotion stub after the behavior and tests ship
@@ -49,4 +52,5 @@ steps:
   depends_on:
   - 2
+  detail: docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/03-remove-ippt-10-promotion-stub-after.md
 ---
 # Roadmap Candidate Vocabulary Retry
diff --git a/docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/01-show-valid-collection-names.md b/docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/01-show-valid-collection-names.md
new file mode 100644
index 00000000..1221a2a5
--- /dev/null
+++ b/docs/implementation-plans/plan-details/roadmap-candidate-vocabulary-retry/01-show-valid-collection-names.md
@@ -0,0 +1,103 @@
+# Step 1 — Show valid collection names and disambiguate existing batch rows
+
+<!-- plan-tool:detail-format-version: 1 -->
+
+## Summary
+
+Make the batch candidate prompt show the collection vocabulary the delta parser accepts and identify the collection for each referenced existing row. Update the prompt-view context and batch proposal flow without changing immutable capsule or receipt bytes. Add bounded correction for rejected model replies so a corrected `entities` operation can store a structural candidate. Green behavior includes two-call exhaustion for repeated malformed replies with no candidate publication.
+
+## Table of Contents
+
+- [Summary](#summary) — Reviewer overview of the prompt and retry change.
+- [Table of Contents](#table-of-contents) — Links to this detail file’s sections.
+- [Why](#why) — The current class-name versus collection-name mismatch.
+- [Input](#input) — Immutable batch and delta contracts this step reads.
+- [Files (creates vs edits)](#files-creates-vs-edits) — Declared file changes.
+- [Implementation](#implementation) — Required prompt hints and bounded retry behavior.
+- [Tests](#tests) — Focused regression and failure-boundary coverage.
+- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
+- [References](#references) — Format and code contracts to consult.
+- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this work.
+
+## Why
+
+`plan_tool/roadmap_candidate_context.py:_row_identity` records Python row-type names such as `EntityRow`, while `plan_tool/roadmap_candidate.py:parse_candidate_delta` accepts collection names such as `entities`. That leaves a model with enough context to identify a row but not enough vocabulary to emit a valid operation, and `PatternRow` has two possible collections. The batch path in `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` currently rejects the first malformed response without giving the model one bounded chance to correct it.
+
+## Input
+
+- **Immutable batch evidence:** Read `CandidateContextBatchCapsule`, `CandidateContextBatchReceipt`, and the payload rendered by `plan_tool/roadmap_candidate_context.py:_render_batch_payload`. Prompt-only guidance must not alter this persisted evidence or its identities.
+- **Operation vocabulary:** Read `plan_tool/roadmap_candidate.py:_ROW_TYPE_NAMES`, `_parse_stage_row`, and `_find_existing_row` as the closed vocabulary and lookup behavior the prompt must help the model satisfy.
+- **Actual collection ownership:** Use `plan_tool/roadmap_artifacts.py:stage_row_collections` to distinguish a row’s real collection, especially `ComponentsArtifact.system_patterns` from `ComponentsArtifact.component_patterns`.
+- **Batch authority:** Preserve the reviewer-item snapshot contract carried by `CandidateContextBatchCapsule.reviewer_items`; hints describe valid operation syntax only and must not add edit authority.
+
+## Files (creates vs edits)
+
+- **New files:** None.
+
+- **Existing files (edits only):**
+  - `plan_tool/roadmap_candidate_context.py` — Add or expose prompt-only collection information derived from the current source artifacts while retaining existing serialized row identities and payload rendering.
+  - `plan_tool/roadmap_candidate_run.py` — Render collection guidance into batch prompts and retry only rejected model content within the fixed proposal budget.
+  - `plan_tool/prompts/roadmap-candidate-delta.md` — Tell the model where to find valid collection names and how existing rows are disambiguated.
+  - `tests/test_roadmap_candidate_run.py` — Cover prompt guidance, successful correction, exhaustion, and terminal failure classification.
+
+## Implementation
+
+- **Keep persisted identities unchanged.** `plan_tool/roadmap_candidate_context.py:_row_identity` and `_row_digest` must retain their current persisted representation. The collection hint is a prompt-view fact, not a new capsule field, receipt field, digest input, replay key, or authority source.
+
+- **Derive collection names from the actual artifact shape.** Use the stage collection ownership exposed by `plan_tool/roadmap_artifacts.py:stage_row_collections` when preparing model-facing guidance. A referenced `EntityRow` must be shown as belonging to `entities`; a referenced `PatternRow` must name the specific collection that contains it. Do not infer a pattern collection from the Python class alone.
+
+- **Show the parser’s accepted vocabulary.** The batch prompt rendered by `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt` must present valid collection names in the form accepted by `plan_tool/roadmap_candidate.py:parse_candidate_delta`. Keep class names invalid rather than normalizing or accepting them.
+
+- **Keep new-pattern choices available.** Show both pattern collection names as valid choices for a new pattern. Existing-row guidance must identify one actual collection; it must not imply that the same `PatternRow` class maps to only one collection globally.
+
+- **Keep prompt guidance outside issued evidence.** A likely approach is to calculate a transient prompt supplement from the resolved source version in the batch run and pass it through `render_candidate_delta_prompt` and `_invoke_once`. Preserve compatible behavior for existing prompt callers, including the review callers in `plan_tool/roadmap_candidate_review.py`, unless they supply the new prompt-only input.
+
+- **Retry only rejected model content.** Update `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal` so parsing or materialization rejection produces one correction prompt and one final model attempt. The correction must explain the rejected response using the same closed operation contract and must not change the issued batch, source version, or reviewer-item authority.
+
+- **Use one shared two-call budget.** A malformed response followed by a 
````

## 6. `roadmap-decision-settlement|2026-09-18T02:46:54Z|plan-plan-correctness-5b1b98fa`

**Cited step:** None: None

**Finding (plan-correctness, medium):** Testing case 8 and the Risks "Gate interaction" entry describe the final staleness recheck as a changed baseline. But th

Testing case 8 and the Risks "Gate interaction" entry describe the final staleness recheck as a changed baseline. But the mechanism they test compares the digest of the artifact's source bytes, and in this codebase "baseline" names the `.roadmap-baselines` record that case 7 checks. Testing says:

  ```
  8. A changed source baseline between evidence selection and confirmation —
     the final staleness recheck, distinct from case 7's up-front admission
  ```

  Risks "Gate interaction" says "verify against a changed-baseline fixture".

  A fixture that edits the baseline record leaves the source digest unchanged, so the digest recheck never fires. The test would then pass for the wrong reason or exercise case 7's path, and the two cases the plan insists are distinct would not both be proven.

**Suggested action:** Reword case 8 and the Gate interaction risk to say the fixture changes the artifact's source bytes after the preflight read. Keep "baseline" for case 7's record.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index 8f8f0d5b..39e715c5 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -31,12 +31,16 @@ steps:
 - id: 2
   title: Add a decision-settlement preflight leaf that resolves the decision target,
-    its feedback evidence, and the predecessor digest — reading enrolled content from
-    the accepted version, not on-disk stage files — with one named refusal per rejection
-    class
+    matches feedback evidence to it by FeedbackTargetKind.ROW/row_id rather than just
+    resolving the feedback id, accepts any FeedbackState, requires un-enrolled baseline
+    admission before reading the source, and computes the predecessor digest — reading
+    enrolled content from the accepted version, not on-disk stage files — with one
+    named refusal per rejection class
   intent: Prove, before any write, that exactly one live Roadmap-derived pending decision
-    was named, that a named live feedback row carries non-empty reviewer-authored
-    `request` text (never model-authored `proposed_response`), and that the source
-    bytes (on-disk artifact for an un-enrolled roadmap, accepted-version bytes for
-    an enrolled one) have not moved since the evidence was read.
+    was named, that a named live feedback row actually targets it (not just resolves)
+    and carries non-empty reviewer-authored `request` text in any FeedbackState (never
+    model-authored `proposed_response`), that an un-enrolled source is admitted against
+    its recorded baseline, and that the source bytes (on-disk artifact for an un-enrolled
+    roadmap, accepted-version bytes for an enrolled one) have not moved since the
+    evidence was read.
   creates:
   - plan_tool/roadmap_decision_settlement.py
@@ -51,9 +55,13 @@ steps:
 - id: 3
   title: Add the immutable settlement receipt record and its own evidence namespace
-    in plan_tool/roadmap_evidence_store.py; publication stays create-once, so an existing
-    final is returned rather than overwritten and nothing is deleted
-  intent: Make every successful settlement leave a durable, readable record of which
-    artifact, decision, predecessor digest, and feedback evidence justified it, so
-    the approval can be proven after the fact.
+    in plan_tool/roadmap_evidence_store.py, naming the exact resulting content digest
+    settlement is about to produce; publication stays create-once and keyed on its
+    own inputs so a retry resolves to the same already-published final, an existing
+    final is returned rather than overwritten, and nothing is deleted
+  intent: Make every successful settlement leave a durable, readable record — written
+    before the row-level write it proves, never after — of which artifact, decision,
+    predecessor digest, feedback evidence, and resulting content digest justify it,
+    so the approval can be proven after the fact and a receipt never outlives or
+    outraces the settlement it names.
   files:
   - plan_tool/roadmap_evidence_store.py
@@ -70,5 +78,6 @@ steps:
       recorded facts
 - id: 4
-  title: Settle one decision on an un-enrolled roadmap and publish its receipt through
+  title: Settle one decision on an un-enrolled roadmap by publishing its receipt first,
+    then, once source admission and staleness both hold, publishing through
     publish_stage_artifact's multi-member generation with invalidate_seeds=False,
     keeping the existing journal recovery (roll back or drop an in-flight generation)
@@ -77,5 +86,6 @@ steps:
     and after
   intent: Let an operator settle an approved decision on an ordinary roadmap by naming
-    it, naming its evidence, and confirming — with no hand-edit of a canonical artifact.
+    it, naming its evidence, and confirming — with no hand-edit of a canonical artifact,
+    and with a receipt that always precedes the write it proves.
   files:
   - plan_tool/roadmap_revision_publish.py
@@ -90,21 +100,24 @@ steps:
   - 3
   depends_on_notes:
-    2: the preflight candidate and its final staleness recheck, called inside the
-      writer lease before the artifact is replaced
-    3: the receipt record published once the artifact write lands
+    2: the preflight candidate, its source-admission check, and its final staleness
+      recheck, called inside the writer lease before the artifact is replaced
+    3: the receipt writer, called before the artifact write, not after
 - id: 5
   title: Settle one decision on an enrolled roadmap by storing the settled artifact
     bytes as an ordinary version_kind candidate record — via create_candidate_version,
-    with a new dedicated no-review sentinel in place of INITIAL_EMPTY_REVIEW_LINEAGE_ID
-    and no candidate_evidence_path/replacement_evidence_path entries — then advancing
-    the accepted head through a new additive PendingGeneration.kind recovery branch
-    that reuses promote_review_seal's writer-token/journal selector-swap but never
-    calls _load_complete_sealed_candidate or either evidence loader; refuses an
-    in-flight pending generation; root-enrollment and review-seal-promotion recovery
-    stay exactly as they are, and stored version members are never overwritten or
-    deleted
-  intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one
-    without ever editing its accepted head in place, without fabricating a synthetic
-    model-authored candidate/review/seal chain or evidence file to satisfy
+    with a new dedicated no-review sentinel in place of INITIAL_EMPTY_REVIEW_LINEAGE_ID,
+    a settlement-owned content_identity, and no candidate_evidence_path/replacement_evidence_path
+    entries — then advancing the accepted head through a new additive PendingGeneration.kind
+    recovery branch that reuses promote_review_seal's writer-token/journal selector-swap
+    but never calls _load_complete_sealed_candidate or either evidence loader; refuses
+    an in-flight pending generation and an admitted, unpromoted candidate lineage whose
+    predecessor is the current accepted head; root-enrollment and review-seal-promotion
+    recovery stay exactly as they are, and stored version members are never overwritten
+    or deleted
+  intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one,
+    for a decision whose approving feedback already exists in the accepted version
+    (nothing can add feedback to an enrolled roadmap today), without ever editing its
+    accepted head in place, without fabricating a synthetic model-authored
+    candidate/review/seal chain, evidence file, or content_identity to satisfy
     promote_review_seal's existing preconditions, and without any accepted-head write
     path outside the guarded selector swap.
@@ -142,11 +155,11 @@ steps:
       head
 - id: 7
-  title: Prove both lineages produce the same settled row, that check_settled_decisions
-    refuses drift on an un-enrolled settled row, and document that the same protection
-    does not yet exist on the enrolled lineage (tracked separately in BUG_BACKLOG.md)
+  title: Prove both lineages produce the same settled row and that check_settled_decisions
+    refuses drift on an un-enrolled settled row this route just settled
   intent: Show the enrolled and un-enrolled paths are one capability rather than two
     look-alikes, by asserting identical before/after row content across both, and
-    state plainly rather than silently which lineage's settled decisions are actually
-    protected from later drift.
+    prove only what these test files can actually demonstrate — the un-enrolled drift
+    refusal, not any claim about the enrolled lineage, which step 8's docs disclose
+    separately.
   files:
   - tests/cli/test_roadmap_cmd.py
@@ -159,15 +172,28 @@ steps:
     6: the single command entry both lineages are driven throug
````

## 7. `roadmap-decision-settlement|2026-09-18T03:30:15Z|plan-plan-correctness-9999436b`

**Cited step:** 6: Add the decision selector, evidence selector, and required confirm flag to plan-tool roadmap as one exclusive action (missing-confirm and companion-option refusals named, matching --reopen-feedback's confirmation-required/mode-rejected precedent), regenerate docs/cli/roadmap.md, and prove both lineages produce the same settled row and that check_settled_decisions refuses drift on an un-enrolled settled row this route just settled

**Finding (plan-correctness, medium):** Step 6 (the CLI action) makes the settlement flags exclusive only from their own side, and it misdescribes where its pre

Step 6 (the CLI action) makes the settlement flags exclusive only from their own side, and it misdescribes where its precedent's refusals come from. Step 6's title promises "one exclusive action", and References describes the precedent as:

  ```
  a selector flag paired with one required, argument-less confirm flag,
    exclusive of every other roadmap option, no backend call.
  ```

  Testing covers only the settlement side's `mode-rejected`, and places it "at the command-parsing layer, matching `--reopen-feedback`'s own precedent". At HEAD, `confirmation-required` and `mode-rejected` are not parser errors. They are verdicts returned by `roadmap_feedback_reopen.py:run_confirmed_feedback_reopen` (members of `FeedbackReopenRefusalVerdict`, rendered as `feedback reopen: preflight-rejected`).

  `cli/roadmap_cmd.py:cmd_roadmap` dispatches impact analysis, escalation receipts, and `--revise-feedback` one after another. Each is guarded only by its own `_*_has_conflict` check, and the `_broad_mode_companions_present` docstring says a new exclusive mode must be added to each sibling's check. Unless the existing actions also reject the settlement flags, `--revise-feedback ID` plus the settlement flags runs a backend revision and publishes an artifact while quietly dropping the settlement request.

**Suggested action:** State in step 6, and add an acceptance criterion, that exclusivity holds both ways: any other roadmap action given the settlement flags refuses, with no backend call and no write. Also correct Testing's "command-parsing layer" wording so it names where the precedent's `confirmation-required` and `mode-rejected` verdicts actually come from.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index 39e715c5..80ac1b1b 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -137,11 +137,19 @@ steps:
 - id: 6
   title: Add the decision selector, evidence selector, and required confirm flag to
-    plan-tool roadmap as one exclusive action, reject them alongside every other roadmap
-    option, and regenerate docs/cli/roadmap.md
+    plan-tool roadmap as one exclusive action (missing-confirm and companion-option
+    refusals named, matching --reopen-feedback's confirmation-required/mode-rejected
+    precedent), regenerate docs/cli/roadmap.md, and prove both lineages produce the
+    same settled row and that check_settled_decisions refuses drift on an un-enrolled
+    settled row this route just settled
   intent: Give the operator the actual command, with the confirm flag that makes settlement
-    their decision rather than the tool's, and no backend call anywhere on the path.
+    their decision rather than the tool's and no backend call anywhere on the path,
+    then show the enrolled and un-enrolled paths are one capability rather than two
+    look-alikes by asserting identical before/after row content across both — proving
+    only the un-enrolled drift refusal, not any claim about the enrolled lineage, which
+    step 7's docs disclose separately.
   files:
   - plan_tool/cli/roadmap_cmd.py
   - tests/cli/test_roadmap_cmd.py
+  - tests/test_roadmap_gates.py
   - docs/cli/roadmap.md
   complexity: medium
@@ -155,31 +163,17 @@ steps:
       head
 - id: 7
-  title: Prove both lineages produce the same settled row and that check_settled_decisions
-    refuses drift on an un-enrolled settled row this route just settled
-  intent: Show the enrolled and un-enrolled paths are one capability rather than two
-    look-alikes, by asserting identical before/after row content across both, and
-    prove only what these test files can actually demonstrate — the un-enrolled drift
-    refusal, not any claim about the enrolled lineage, which step 8's docs disclose
-    separately.
-  files:
-  - tests/cli/test_roadmap_cmd.py
-  - tests/test_roadmap_gates.py
-  complexity: medium
-  change_type: non-code
-  depends_on:
-  - 6
-  depends_on_notes:
-    6: the single command entry both lineages are driven through end to end
-- id: 8
   title: Document the settlement route; retire every live hand-edit settlement instruction
-    (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md,
-    integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md, docs/how-to/roadmap.md);
-    state that --revise-feedback still cannot change status; correct ROADMAP_FORMAT.md's
-    Decision status paragraph and gate-table row plus CAPABILITIES.md's accepted-head-authority
-    statement to name both guarded writers and confine the drift-protection claim to
-    the un-enrolled lineage, updating tests/test_roadmap_format.py's pinning test to
-    match; extend the "Incomplete immutable lifecycle journals" BUG_BACKLOG.md entry
-    to name the new settlement generation shape(s); and remove the settlement
-    BUG_BACKLOG.md entry now that the capability ships
+    (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md, RUNBOOK.md,
+    docs/how-to/use-cases.md, integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md,
+    docs/how-to/roadmap.md); state that --revise-feedback still cannot change status;
+    correct ROADMAP_FORMAT.md's Immutable candidate-version authority block and
+    CAPABILITIES.md's accepted-head-authority statement to name both guarded writers,
+    updating tests/test_roadmap_format.py::test_candidate_policy_reference_keeps_review_inert_until_exact_promotion
+    to match, and separately correct the Decision status paragraph and gate-table row
+    to confine the drift-protection claim to the un-enrolled lineage; add the settlement
+    receipt as a third EvidenceNamespace in docs/ARCHITECTURE.md; extend the "Incomplete
+    immutable lifecycle journals" BUG_BACKLOG.md entry to name the new settlement
+    generation shape(s); and remove the settlement BUG_BACKLOG.md entry now that the
+    capability ships
   intent: Leave one honest account of how a decision is settled and which lineage's
     settled decisions are actually protected from later drift, so no reader is still
@@ -192,4 +186,7 @@ steps:
   - docs/how-to/common-workflows.md
   - docs/how-to/roadmap-demo.md
+  - RUNBOOK.md
+  - docs/how-to/use-cases.md
+  - docs/ARCHITECTURE.md
   - integrations/shared/DIRECTIVES.md
   - CLAUDE.md
@@ -201,9 +198,7 @@ steps:
   depends_on:
   - 6
-  - 7
   depends_on_notes:
-    6: the shipped flag names and refusal messages the docs describe, read off the
-      landed parser rather than off this plan
-    7: the passing cross-lineage proof that makes removing the backlog entry honest
+    6: the shipped flag names, refusal messages, and cross-lineage proof the docs
+      describe, read off the landed parser and tests rather than off this plan
 ---
 # Roadmap Decision Settlement
@@ -241,8 +236,16 @@ helper regardless; `check_settled_decisions`
 (`plan_tool/roadmap_gates.py`) already refuses a *settled* decision's id,
 status, chosen option, or anchor from drifting; it does not, and must not
-start to, gate `pending → settled` itself. Nothing today reaches `settled`
-except a hand-edit (un-enrolled) or authoring a full model candidate through
-propose → review → promote (enrolled) — both bypass the operator-confirmed,
-evidence-bound shape every other narrow roadmap action already has.
+start to, gate `pending → settled` itself. `settled` is not rare today: the
+domain stage prompt instructs "Use `settled` otherwise" for a decision the
+brief already resolves, so ordinary model-authored stage authoring is the
+dominant route; an ordinary un-enrolled revision can newly settle a decision
+too (`ROADMAP_FORMAT.md` lists "decisions the revision newly settled" as
+expected run residue); a candidate proposal on an enrolled roadmap can
+already change a decision's `status`, including to `settled`, as ordinary
+delta content; and a hand-edit remains the only way an *operator* flips an
+existing `pending` row today. None of these is operator-confirmed and
+evidence-bound the way every other narrow roadmap action already is — that
+absence, not the absence of any route to `settled` at all, is this plan's
+actual gap.
 
 ## Architecture
@@ -333,4 +336,28 @@ evidence-bound shape every other narrow roadmap action already has.
   A stage with no recorded baseline refuses rather than settlement silently
   creating one from unadmitted bytes.
+
+  Baseline admission alone does not prove the source is in the parser's
+  exact rendered form: `admit_baseline_backed_source` compares only
+  `canonical_projection`, a semantic digest that ignores exact bytes.
+  Settlement also requires a render-canonical check —
+  `roadmap_escalation_selection.py:canonical_artifact_snapshot`, the same
+  distinction `--reopen-feedback` (`source-not-canonical`) and
+  `--revise-feedback` (`preflight_feedback_revision`'s
+  `RenderCanonicalMismatch`) already enforce — and refuses a non-canonical
+  source under its own named reason, never silently rewriting bytes outside
+  the selected row to make it canonical. The common trigger is an operator
+  hand-filling the `_NO_FEEDBACK_KEY_COMMENT` stub to write the very
+  feedback row settlement will cite: that file is non-canonical until its
+  owning stage is re-run with `--from-stage`, which an operator must do
+  before the evidence becomes citable.
+- **Enrolled non-canonical bytes are a standing, permanent limitation, not
+  a repair target.** `roadmap_versions.py:prepare_root_version_from_snapshot`
+  captures on-disk text with no render-canonical check, so an accepted
+  version can hold non-c
````

## 8. `roadmap-decision-settlement|2026-09-18T03:30:15Z|plan-plan-correctness-30894127`

**Cited step:** 7: Document the settlement route; retire every live hand-edit settlement instruction (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md, RUNBOOK.md, docs/how-to/use-cases.md, integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md, docs/how-to/roadmap.md); state that --revise-feedback still cannot change status; correct ROADMAP_FORMAT.md's Immutable candidate-version authority block and CAPABILITIES.md's accepted-head-authority statement to name both guarded writers, updating tests/test_roadmap_format.py::test_candidate_policy_reference_keeps_review_inert_until_exact_promotion to match, and separately correct the Decision status paragraph and gate-table row to confine the drift-protection claim to the un-enrolled lineage; add the settlement receipt as a third EvidenceNamespace in docs/ARCHITECTURE.md; extend the "Incomplete immutable lifecycle journals" BUG_BACKLOG.md entry to name the new settlement generation shape(s); and remove the settlement BUG_BACKLOG.md entry now that the capability ships

**Finding (plan-correctness, medium):** The Architecture's advice for making a hand-written feedback row citable sends the operator through the one route that c

The Architecture's advice for making a hand-written feedback row citable sends the operator through the one route that can settle the decision without confirmation. The Architecture un-enrolled render-canonical paragraph says:

  ```
  The common trigger is an operator
    hand-filling the `_NO_FEEDBACK_KEY_COMMENT` stub to write the very
    feedback row settlement will cite: that file is non-canonical until its
    owning stage is re-run with `--from-stage`, which an operator must do
    before the evidence becomes citable.
  ```

  Testing case 8 repeats the advice ("a hand-filled `_NO_FEEDBACK_KEY_COMMENT` stub before its stage is re-run"). A `--from-stage` run of a stage with open feedback calls the backend (`docs/how-to/roadmap.md` §4). That stage revision may newly settle a decision: `roadmap.py:_newly_settled_decision_ids` reports it and never refuses it (RUNBOOK: "a gate would false-positive when your own request decided the question").
  - An operator whose feedback asks to settle decision X will often get X settled by the model, which is exactly the unconfirmed path the Problem statement names as the gap. The new route then refuses as case 3 (non-pending).
  - The "must" is also false. A hand-written row in exact rendered form (the leftover stub comment lines removed) is canonical without any backend call. `--revise-feedback` already requires that: `preflight_feedback_revision` raises `RenderCanonicalMismatch`, and §5 has the operator add the row by hand.

  Step 7 will pass this advice on to operators. Sites: Architecture un-enrolled render-canonical paragraph, Testing case 8, step 7's docs.

**Suggested action:** Replace the "re-run with `--from-stage`" advice in the Architecture, Testing case 8, and step 7's docs with the no-backend route: write the feedback row in exact rendered form, as `--revise-feedback` already requires. Also state that a `--from-stage` feedback revision may itself newly settle the decision, after which settlement refuses as already settled.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index 39e715c5..80ac1b1b 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -137,11 +137,19 @@ steps:
 - id: 6
   title: Add the decision selector, evidence selector, and required confirm flag to
-    plan-tool roadmap as one exclusive action, reject them alongside every other roadmap
-    option, and regenerate docs/cli/roadmap.md
+    plan-tool roadmap as one exclusive action (missing-confirm and companion-option
+    refusals named, matching --reopen-feedback's confirmation-required/mode-rejected
+    precedent), regenerate docs/cli/roadmap.md, and prove both lineages produce the
+    same settled row and that check_settled_decisions refuses drift on an un-enrolled
+    settled row this route just settled
   intent: Give the operator the actual command, with the confirm flag that makes settlement
-    their decision rather than the tool's, and no backend call anywhere on the path.
+    their decision rather than the tool's and no backend call anywhere on the path,
+    then show the enrolled and un-enrolled paths are one capability rather than two
+    look-alikes by asserting identical before/after row content across both — proving
+    only the un-enrolled drift refusal, not any claim about the enrolled lineage, which
+    step 7's docs disclose separately.
   files:
   - plan_tool/cli/roadmap_cmd.py
   - tests/cli/test_roadmap_cmd.py
+  - tests/test_roadmap_gates.py
   - docs/cli/roadmap.md
   complexity: medium
@@ -155,31 +163,17 @@ steps:
       head
 - id: 7
-  title: Prove both lineages produce the same settled row and that check_settled_decisions
-    refuses drift on an un-enrolled settled row this route just settled
-  intent: Show the enrolled and un-enrolled paths are one capability rather than two
-    look-alikes, by asserting identical before/after row content across both, and
-    prove only what these test files can actually demonstrate — the un-enrolled drift
-    refusal, not any claim about the enrolled lineage, which step 8's docs disclose
-    separately.
-  files:
-  - tests/cli/test_roadmap_cmd.py
-  - tests/test_roadmap_gates.py
-  complexity: medium
-  change_type: non-code
-  depends_on:
-  - 6
-  depends_on_notes:
-    6: the single command entry both lineages are driven through end to end
-- id: 8
   title: Document the settlement route; retire every live hand-edit settlement instruction
-    (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md,
-    integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md, docs/how-to/roadmap.md);
-    state that --revise-feedback still cannot change status; correct ROADMAP_FORMAT.md's
-    Decision status paragraph and gate-table row plus CAPABILITIES.md's accepted-head-authority
-    statement to name both guarded writers and confine the drift-protection claim to
-    the un-enrolled lineage, updating tests/test_roadmap_format.py's pinning test to
-    match; extend the "Incomplete immutable lifecycle journals" BUG_BACKLOG.md entry
-    to name the new settlement generation shape(s); and remove the settlement
-    BUG_BACKLOG.md entry now that the capability ships
+    (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md, RUNBOOK.md,
+    docs/how-to/use-cases.md, integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md,
+    docs/how-to/roadmap.md); state that --revise-feedback still cannot change status;
+    correct ROADMAP_FORMAT.md's Immutable candidate-version authority block and
+    CAPABILITIES.md's accepted-head-authority statement to name both guarded writers,
+    updating tests/test_roadmap_format.py::test_candidate_policy_reference_keeps_review_inert_until_exact_promotion
+    to match, and separately correct the Decision status paragraph and gate-table row
+    to confine the drift-protection claim to the un-enrolled lineage; add the settlement
+    receipt as a third EvidenceNamespace in docs/ARCHITECTURE.md; extend the "Incomplete
+    immutable lifecycle journals" BUG_BACKLOG.md entry to name the new settlement
+    generation shape(s); and remove the settlement BUG_BACKLOG.md entry now that the
+    capability ships
   intent: Leave one honest account of how a decision is settled and which lineage's
     settled decisions are actually protected from later drift, so no reader is still
@@ -192,4 +186,7 @@ steps:
   - docs/how-to/common-workflows.md
   - docs/how-to/roadmap-demo.md
+  - RUNBOOK.md
+  - docs/how-to/use-cases.md
+  - docs/ARCHITECTURE.md
   - integrations/shared/DIRECTIVES.md
   - CLAUDE.md
@@ -201,9 +198,7 @@ steps:
   depends_on:
   - 6
-  - 7
   depends_on_notes:
-    6: the shipped flag names and refusal messages the docs describe, read off the
-      landed parser rather than off this plan
-    7: the passing cross-lineage proof that makes removing the backlog entry honest
+    6: the shipped flag names, refusal messages, and cross-lineage proof the docs
+      describe, read off the landed parser and tests rather than off this plan
 ---
 # Roadmap Decision Settlement
@@ -241,8 +236,16 @@ helper regardless; `check_settled_decisions`
 (`plan_tool/roadmap_gates.py`) already refuses a *settled* decision's id,
 status, chosen option, or anchor from drifting; it does not, and must not
-start to, gate `pending → settled` itself. Nothing today reaches `settled`
-except a hand-edit (un-enrolled) or authoring a full model candidate through
-propose → review → promote (enrolled) — both bypass the operator-confirmed,
-evidence-bound shape every other narrow roadmap action already has.
+start to, gate `pending → settled` itself. `settled` is not rare today: the
+domain stage prompt instructs "Use `settled` otherwise" for a decision the
+brief already resolves, so ordinary model-authored stage authoring is the
+dominant route; an ordinary un-enrolled revision can newly settle a decision
+too (`ROADMAP_FORMAT.md` lists "decisions the revision newly settled" as
+expected run residue); a candidate proposal on an enrolled roadmap can
+already change a decision's `status`, including to `settled`, as ordinary
+delta content; and a hand-edit remains the only way an *operator* flips an
+existing `pending` row today. None of these is operator-confirmed and
+evidence-bound the way every other narrow roadmap action already is — that
+absence, not the absence of any route to `settled` at all, is this plan's
+actual gap.
 
 ## Architecture
@@ -333,4 +336,28 @@ evidence-bound shape every other narrow roadmap action already has.
   A stage with no recorded baseline refuses rather than settlement silently
   creating one from unadmitted bytes.
+
+  Baseline admission alone does not prove the source is in the parser's
+  exact rendered form: `admit_baseline_backed_source` compares only
+  `canonical_projection`, a semantic digest that ignores exact bytes.
+  Settlement also requires a render-canonical check —
+  `roadmap_escalation_selection.py:canonical_artifact_snapshot`, the same
+  distinction `--reopen-feedback` (`source-not-canonical`) and
+  `--revise-feedback` (`preflight_feedback_revision`'s
+  `RenderCanonicalMismatch`) already enforce — and refuses a non-canonical
+  source under its own named reason, never silently rewriting bytes outside
+  the selected row to make it canonical. The common trigger is an operator
+  hand-filling the `_NO_FEEDBACK_KEY_COMMENT` stub to write the very
+  feedback row settlement will cite: that file is non-canonical until its
+  owning stage is re-run with `--from-stage`, which an operator must do
+  before the evidence becomes citable.
+- **Enrolled non-canonical bytes are a standing, permanent limitation, not
+  a repair target.** `roadmap_versions.py:prepare_root_version_from_snapshot`
+  captures on-disk text with no render-canonical check, so an accepted
+  version can hold non-c
````

## 9. `arm-clustering-cross-round-consensus|2026-08-12T21:33:43Z|plan-plan-completeness-4776a019`

**Cited step:** 1: Build arm-clustering consensus targets from saved audit history

**Finding (plan-completeness, medium):** Step 1's code sample (Implementation §3) types `step_statuses: Mapping[int, StepStatus]`, but `StepStatus` is not import

Step 1's code sample (Implementation §3) types `step_statuses: Mapping[int, StepStatus]`, but `StepStatus` is not imported anywhere in `plan_tool/convergence_diagnosis.py` today (confirmed: the module's top-level imports are `convergence`, `granularity`, `locator`, `review`, `review_persistence` — no `plan_tool.schema`). Step 1's "Files (creates vs edits)" section only says to "add `Mapping, Sequence` to the existing `typing` import" and never mentions adding `from plan_tool.schema import StepStatus` (or similar), so the code sample's own type annotation can't be satisfied by the declared file-level edit list as written.

**Suggested action:** add "import `StepStatus` from `plan_tool.schema`" to step 1's Files section for `plan_tool/convergence_diagnosis.py`, alongside the `Mapping, Sequence` addition.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
index f245ca0c..7a8e5205 100644
--- a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
+++ b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
@@ -17,7 +17,7 @@ steps:
     `Recommendation`/`RunFinding` (today it is parsed by `_split_audit_step_evidence`
     and then discarded into a transient in-call structure before a review is saved),
-    then let a material finding earn a consensus step target from that persisted
-    value across separate audit rounds, so arm-clustering has evidence to work with
-    on the --audit-passes 1 runs that give it only one same-execution sample.
+    then let a material finding earn a consensus step target from that persisted value
+    across separate audit rounds, so arm-clustering has evidence to work with on the
+    --audit-passes 1 runs that give it only one same-execution sample.
   files:
   - plan_tool/review.py
@@ -29,4 +29,5 @@ steps:
   complexity: high
   change_type: feature
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/01-build-arm-clustering-consensus-targets.md
   status: current
 - id: 2
@@ -51,9 +52,14 @@ steps:
     1: the classifier function and its advisory record, which diagnose_convergence
       calls and the render lines read fields off
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/02-cross-round-arm-clustering-advisory.md
 - id: 3
   title: Parse the plan once in cmd_convergence instead of inside _current_audit_stage
   intent: Make the parsed plan reachable from cmd_convergence so the next step can
     read its committed steps without parsing the file a second time or copying the
-    best-effort try/except.
+    best-effort try/except. The hoisted `parse_plan` call must keep degrading to `diagnose_convergence`'s
+    pre-stage-bar blanket-blocking defaults on a parse failure or missing plan — the
+    same outcome `_current_audit_stage`'s existing try/except gives today — so `cmd_convergence`'s
+    documented "always exits 0, never surfaces an error" contract survives the move
+    unchanged.
   files:
   - plan_tool/cli/convergence_cmd.py
@@ -61,13 +67,15 @@ steps:
   complexity: low
   change_type: refactor
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/03-parse-plan-once-cmd-convergence-instead.md
 - id: 4
   title: Pass committed step ids to the diagnosis from the convergence and completeness
     surfaces
   intent: Turn the classifier on for real operators by threading real committed step
-    ids *and* each step's current status (step 1's function signature accepts both as
-    parameters — a bare id list alone carries no status, and step 1's done-step drop
-    check needs it — but this step is what supplies real values from the plan's parsed
-    `Step` objects, not step 1) into it from the two places the sibling advisories
-    already print, so `plan-tool convergence` and completeness stderr both surface it.
+    ids *and* each step's current status (step 1's function signature accepts both
+    as parameters — a bare id list alone carries no status, and step 1's done-step
+    drop check needs it — but this step is what supplies real values from the plan's
+    parsed `Step` objects, not step 1) into it from the two places the sibling advisories
+    already print, so `plan-tool convergence` and completeness stderr both surface
+    it.
   files:
   - plan_tool/cli/convergence_cmd.py
@@ -85,4 +93,5 @@ steps:
     3: the parsed plan hoisted into cmd_convergence, so committed step ids come from
       the parse the stage lookup already did
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/04-pass-committed-step-ids-diagnosis.md
 - id: 5
   title: Update the docs for the cross-round advisory and settle the backlog entries
@@ -92,8 +101,8 @@ steps:
     CLAUDE.md''s "cycle-free leaf" bullet and `docs/ARCHITECTURE.md`''s "Convergence
     diagnostic" entry both restate that import set already inaccurately (CLAUDE.md
-    omits `granularity`; both predate this plan and are wrong independent of it), so
-    correct both to the module''s full current set (`review_persistence`, `review`,
-    `locator`, `convergence`, `granularity`) plus the new `audit_shapes` edge step 2
-    adds — not only append the one new edge onto an already-wrong baseline. The
+    omits `granularity`; both predate this plan and are wrong independent of it),
+    so correct both to the module''s full current set (`review_persistence`, `review`,
+    `locator`, `convergence`, `granularity`) plus the new `audit_shapes` edge step
+    2 adds — not only append the one new edge onto an already-wrong baseline. The
     module''s own docstring paragraph is step 2''s fix, made where the import lands,
     not this step''s.'
@@ -110,4 +119,5 @@ steps:
     4: the shipped surfaces and the final import edge, so the docs describe what landed
       rather than what was proposed
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/05-update-docs-cross-round-advisory-settle.md
 ---
 # Arm Clustering Cross Round Consensus
@@ -165,16 +175,33 @@ settled precedent, not a gap to redesign.
    Every cross-round consumer this plan builds reads `RunFinding`, not
    `Recommendation`, so missing the second site leaves the field permanently
-   `None` on everything this plan actually consumes. Document both fields in
-   `DATA_CONTRACT.md`. This is the one new piece of persisted state this plan
-   adds; `evaluate_arm_clustering` and the same-execution consensus path are
+   `None` on everything this plan actually consumes. The two fields get two
+   different kinds of documentation, landed in **this same step**, not
+   deferred to step 5's docs pass: `Recommendation.audit_step_target` is
+   persisted/serialized (round-trips via `save_review`), so it gets a row in
+   `DATA_CONTRACT.md`'s existing `Recommendation` table, same as `anchor` or
+   `impact`. `RunFinding` is not persisted on its own — its own docstring
+   calls it a flattening "from a saved report's recommendation list," and
+   `DATA_CONTRACT.md` documents only persisted/serialized schemas, which is
+   why none of `convergence_diagnosis.py`'s other dataclasses have an entry
+   there — so `RunFinding.audit_step_target` is documented inline in
+   `RunFinding`'s own docstring instead, matching how `step_id`, `anchor`, and
+   `impact` are already documented there, not as a new `DATA_CONTRACT.md`
+   section. This is the one new piece of persisted state this plan adds;
+   `evaluate_arm_clustering` and the same-execution consensus path are
    unaffected — they keep reading `observations_by_id` and the transient tag
    directly.
 2. Materiality: treat a matched finding as material via
    `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=…)`
-   checked **only against the newest round's copy** of that finding — the
-   same rule `classify_edit_drift`'s `_edit_drift_eligible` already applies to
-   `RunFinding` objects pulled from history (`convergence_diagnosis.py:885`),
-   and the same newest-round keying point 7 already uses for the output
-   mapping. A finding's severity/impact tag can differ across matched rounds;
+   checked **only against the newest round's copy** of that finding —
+   reusing only the stage-bar half of `classify_edit_drift`'s
+   `_edit_drift_eligible` (`convergence_diagnosis.py:885`), and the same
+   newest-round keying point 7 already uses for the output mapping.
+   `_edit_drift_eligible` also runs a second check —
+   `_is_resolved_in_run(annotations.get(finding.id))`, dropping a finding the
+   operator already declined between rounds — that this plan deliberately
+   does **not** reuse: Out of scope already refuses to gate cross-round
+
````

## 10. `roadmap-decision-settlement|2026-09-18T03:30:15Z|plan-plan-correctness-a82f9fdf`

**Cited step:** 4: Settle one decision on an un-enrolled roadmap by publishing its receipt first, then, once source admission and staleness both hold, publishing through publish_stage_artifact's multi-member generation with invalidate_seeds=False, keeping the existing journal recovery (roll back or drop an in-flight generation) unchanged and updating the selected artifact's bytes and its stage baseline record together — seed state and every other artifact/stage stay byte-identical before and after

**Finding (plan-correctness, high):** Settlement's `invalidate_seeds=False` is justified by a claim the code contradicts. The Architecture "Un-enrolled roadma

Settlement's `invalidate_seeds=False` is justified by a claim the code contradicts. The Architecture "Un-enrolled roadmap" bullet says:

  ```
  settlement must pass `invalidate_seeds=False` explicitly, since
  flipping one decision's status is not a design change any derived seed needs reworked against.
  ```

  Draft seeds do depend on decision status. `plan_tool/prompts/roadmap-seed.md` tells the seed author to "carry chosen options from upstream artifacts as settled fences" and not to revise "settled decisions". `ROADMAP_FORMAT.md` § "Invalidation and explicit refresh" states that when "a stage-4 write replaces `04-roadmap.md`, every tracked derived seed is marked **invalidated**". Settling a `plans` decision is exactly that kind of write. The only existing `publish_stage_artifact` caller (`roadmap.py`, the stage route) always keeps the invalidating default. This feature's own BUG_BACKLOG entry describes the harm as not being able to prove "the artifact set is settled before seed materialization". As written, a seed drafted while the decision was `pending` stays `current`, and `create --from-existing` uses it without the invalidated-seed confirmation. The same choice is pinned in four places:
  - step 4's title ("with invalidate_seeds=False … seed state … stay byte-identical");
  - Testing ("Prove the roadmap's seed-state file is byte-identical before and after a settlement");
  - the fourth acceptance criterion ("leaves the roadmap's seed-state file byte-identical");
  - step 7, which does not list `ROADMAP_FORMAT.md` § "Invalidation and explicit refresh" among its corrections.

**Suggested action:** Decide seed handling once. Either keep the default invalidation, and replace the "seed-state byte-identical" requirement in step 4, Testing, and the acceptance criteria with "tracked seeds are marked invalidated". Or keep `False` with a reason that holds up against the seed prompt, and have step 7 add a documented settlement carve-out to `ROADMAP_FORMAT.md` § "Invalidation and explicit refresh".

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index 39e715c5..80ac1b1b 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -137,11 +137,19 @@ steps:
 - id: 6
   title: Add the decision selector, evidence selector, and required confirm flag to
-    plan-tool roadmap as one exclusive action, reject them alongside every other roadmap
-    option, and regenerate docs/cli/roadmap.md
+    plan-tool roadmap as one exclusive action (missing-confirm and companion-option
+    refusals named, matching --reopen-feedback's confirmation-required/mode-rejected
+    precedent), regenerate docs/cli/roadmap.md, and prove both lineages produce the
+    same settled row and that check_settled_decisions refuses drift on an un-enrolled
+    settled row this route just settled
   intent: Give the operator the actual command, with the confirm flag that makes settlement
-    their decision rather than the tool's, and no backend call anywhere on the path.
+    their decision rather than the tool's and no backend call anywhere on the path,
+    then show the enrolled and un-enrolled paths are one capability rather than two
+    look-alikes by asserting identical before/after row content across both — proving
+    only the un-enrolled drift refusal, not any claim about the enrolled lineage, which
+    step 7's docs disclose separately.
   files:
   - plan_tool/cli/roadmap_cmd.py
   - tests/cli/test_roadmap_cmd.py
+  - tests/test_roadmap_gates.py
   - docs/cli/roadmap.md
   complexity: medium
@@ -155,31 +163,17 @@ steps:
       head
 - id: 7
-  title: Prove both lineages produce the same settled row and that check_settled_decisions
-    refuses drift on an un-enrolled settled row this route just settled
-  intent: Show the enrolled and un-enrolled paths are one capability rather than two
-    look-alikes, by asserting identical before/after row content across both, and
-    prove only what these test files can actually demonstrate — the un-enrolled drift
-    refusal, not any claim about the enrolled lineage, which step 8's docs disclose
-    separately.
-  files:
-  - tests/cli/test_roadmap_cmd.py
-  - tests/test_roadmap_gates.py
-  complexity: medium
-  change_type: non-code
-  depends_on:
-  - 6
-  depends_on_notes:
-    6: the single command entry both lineages are driven through end to end
-- id: 8
   title: Document the settlement route; retire every live hand-edit settlement instruction
-    (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md,
-    integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md, docs/how-to/roadmap.md);
-    state that --revise-feedback still cannot change status; correct ROADMAP_FORMAT.md's
-    Decision status paragraph and gate-table row plus CAPABILITIES.md's accepted-head-authority
-    statement to name both guarded writers and confine the drift-protection claim to
-    the un-enrolled lineage, updating tests/test_roadmap_format.py's pinning test to
-    match; extend the "Incomplete immutable lifecycle journals" BUG_BACKLOG.md entry
-    to name the new settlement generation shape(s); and remove the settlement
-    BUG_BACKLOG.md entry now that the capability ships
+    (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md, RUNBOOK.md,
+    docs/how-to/use-cases.md, integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md,
+    docs/how-to/roadmap.md); state that --revise-feedback still cannot change status;
+    correct ROADMAP_FORMAT.md's Immutable candidate-version authority block and
+    CAPABILITIES.md's accepted-head-authority statement to name both guarded writers,
+    updating tests/test_roadmap_format.py::test_candidate_policy_reference_keeps_review_inert_until_exact_promotion
+    to match, and separately correct the Decision status paragraph and gate-table row
+    to confine the drift-protection claim to the un-enrolled lineage; add the settlement
+    receipt as a third EvidenceNamespace in docs/ARCHITECTURE.md; extend the "Incomplete
+    immutable lifecycle journals" BUG_BACKLOG.md entry to name the new settlement
+    generation shape(s); and remove the settlement BUG_BACKLOG.md entry now that the
+    capability ships
   intent: Leave one honest account of how a decision is settled and which lineage's
     settled decisions are actually protected from later drift, so no reader is still
@@ -192,4 +186,7 @@ steps:
   - docs/how-to/common-workflows.md
   - docs/how-to/roadmap-demo.md
+  - RUNBOOK.md
+  - docs/how-to/use-cases.md
+  - docs/ARCHITECTURE.md
   - integrations/shared/DIRECTIVES.md
   - CLAUDE.md
@@ -201,9 +198,7 @@ steps:
   depends_on:
   - 6
-  - 7
   depends_on_notes:
-    6: the shipped flag names and refusal messages the docs describe, read off the
-      landed parser rather than off this plan
-    7: the passing cross-lineage proof that makes removing the backlog entry honest
+    6: the shipped flag names, refusal messages, and cross-lineage proof the docs
+      describe, read off the landed parser and tests rather than off this plan
 ---
 # Roadmap Decision Settlement
@@ -241,8 +236,16 @@ helper regardless; `check_settled_decisions`
 (`plan_tool/roadmap_gates.py`) already refuses a *settled* decision's id,
 status, chosen option, or anchor from drifting; it does not, and must not
-start to, gate `pending → settled` itself. Nothing today reaches `settled`
-except a hand-edit (un-enrolled) or authoring a full model candidate through
-propose → review → promote (enrolled) — both bypass the operator-confirmed,
-evidence-bound shape every other narrow roadmap action already has.
+start to, gate `pending → settled` itself. `settled` is not rare today: the
+domain stage prompt instructs "Use `settled` otherwise" for a decision the
+brief already resolves, so ordinary model-authored stage authoring is the
+dominant route; an ordinary un-enrolled revision can newly settle a decision
+too (`ROADMAP_FORMAT.md` lists "decisions the revision newly settled" as
+expected run residue); a candidate proposal on an enrolled roadmap can
+already change a decision's `status`, including to `settled`, as ordinary
+delta content; and a hand-edit remains the only way an *operator* flips an
+existing `pending` row today. None of these is operator-confirmed and
+evidence-bound the way every other narrow roadmap action already is — that
+absence, not the absence of any route to `settled` at all, is this plan's
+actual gap.
 
 ## Architecture
@@ -333,4 +336,28 @@ evidence-bound shape every other narrow roadmap action already has.
   A stage with no recorded baseline refuses rather than settlement silently
   creating one from unadmitted bytes.
+
+  Baseline admission alone does not prove the source is in the parser's
+  exact rendered form: `admit_baseline_backed_source` compares only
+  `canonical_projection`, a semantic digest that ignores exact bytes.
+  Settlement also requires a render-canonical check —
+  `roadmap_escalation_selection.py:canonical_artifact_snapshot`, the same
+  distinction `--reopen-feedback` (`source-not-canonical`) and
+  `--revise-feedback` (`preflight_feedback_revision`'s
+  `RenderCanonicalMismatch`) already enforce — and refuses a non-canonical
+  source under its own named reason, never silently rewriting bytes outside
+  the selected row to make it canonical. The common trigger is an operator
+  hand-filling the `_NO_FEEDBACK_KEY_COMMENT` stub to write the very
+  feedback row settlement will cite: that file is non-canonical until its
+  owning stage is re-run with `--from-stage`, which an operator must do
+  before the evidence becomes citable.
+- **Enrolled non-canonical bytes are a standing, permanent limitation, not
+  a repair target.** `roadmap_versions.py:prepare_root_version_from_snapshot`
+  captures on-disk text with no render-canonical check, so an accepted
+  version can hold non-c
````

## 11. `roadmap-model-failure-receipts|2026-09-21T15:24:25Z|plan-plan-correctness-f1c9f87c`

**Cited step:** 4: Record bounded roadmap feedback failures before retry while preserving accepted revision writes

**Finding (plan-correctness, high):** Steps 4 (`Record bounded roadmap feedback failures before retry while preserving accepted revision writes`) and 5 (`Reco

Steps 4 (`Record bounded roadmap feedback failures before retry while preserving accepted revision writes`) and 5 (`Record local feedback revision failures and reply-bearing gate rejections while preserving recoverable publication replacement`) leave reply-bearing rejection outcomes outside the stated receipt policy. Architecture names only `invoke`, `parse`, `authored-review-rows`, and local gate rejection; at HEAD, `roadmap.py:_run_bounded_stage_feedback` returns `invalid_detail` for a reply exceeding stage limits, while `roadmap_revision_run.py:_run_accepted_revision` has distinct `operation-rejected`, `merge-rejected`, and `candidate-parse-failed` outcomes. The plan does not choose their receipt reason or sidecar disposition, so implementers can omit receipts or retain raw replies inconsistently despite the stated contract:
  ```
  Fresh stage authoring, bounded stage feedback, and local feedback revision
  all emit the same redacted terminal-failure receipt contract.
  ```
  (Acceptance criteria)

**Suggested action:** Define receipt reasons and sidecar dispositions for every reply-bearing bounded-feedback and local-revision rejection outcome, and extend the producer matrix to prove those routes emit exactly one receipt.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-model-failure-receipts.md b/docs/implementation-plans/2-roadmap-model-failure-receipts.md
index 520c8bf4..9be73b35 100644
--- a/docs/implementation-plans/2-roadmap-model-failure-receipts.md
+++ b/docs/implementation-plans/2-roadmap-model-failure-receipts.md
@@ -19,5 +19,5 @@ steps:
     best-effort whole-file replacement
   intent: Give roadmap and detail one reusable owner for rejected-response sidecars
-    without changing detail behavior.
+    without changing detail behavior or subsuming create's separate later migration.
   files:
   - plan_tool/detail.py
@@ -127,7 +127,8 @@ their diagnostic evidence depends on which loop rejected the response. A
 recovered parse failure can be counted without preserving the malformed bytes;
 an exhausted local revision can report `operation-rejected` without the parser
-reason; and sidecar capture is currently a detail-specific convention. This
-slice establishes one receipt contract and applies it across the selected
-roadmap stage and revision routes.
+reason; and roadmap has no shared sidecar owner with detail. Create separately
+mirrors detail's existing helper and remains a later migration. This slice
+establishes one receipt contract and applies it across the selected roadmap
+stage and revision routes.
 
 ## Problem statement

````

## 12. `security-check-command|2026-06-20T21:11:54Z|plan-plan-completeness-e3bd0ad0`

**Cited step:** 2: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json persistence (sibling of resolve_reusable_audit); scope reuse by target (plan vs code) via the filename suffix as well as fingerprint so a plan-axis caller never reuses a code-axis report or vice versa (per-target scoping lands here, not deferred); the target="code" axis additionally scopes its lookup by step_id (mirroring the reconcile family's per-step _find_saved_for_step, not the whole-plan resolve_reusable_audit shape) because the <ts>-security-code.json suffix encodes only the target and not the step, so two steps' code audits write same-suffix sidecars and a target-suffix-only resolver would serve one step's saved code audit to another step's caller; a target="plan" save verdicts fresh on an unchanged plan fingerprint alone — do NOT gate plan-target freshness on saved.code_fingerprint_present (that code-fingerprint staleness gate from resolve_reusable_audit applies only to the code/reconcile targets)

**Finding (plan-completeness, medium):** Step 2 (`resolve_reusable_security` + persistence) and step 4 freeze the reconcile sidecar's on-disk schema now, but tha

Step 2 (`resolve_reusable_security` + persistence) and step 4 freeze the reconcile sidecar's on-disk schema now, but that schema cannot record partial coverage: `write_security_report` persists via `review_persistence.save_review`, whose payload carries `kind`/`step_id`/fingerprints/`recommendations` but **no coverage or `skipped_steps` field**, so the step-1 `SecurityAuditResult.skipped_steps` count does not round-trip to disk. The Risks section names plan+code-fingerprint-gated reuse of the `<ts>-security-reconcile.json` sidecar as the eventual fan-out bound (deferred consumer); when that consumer short-circuits the whole sweep on a fingerprint hit, it will serve a sidecar written from a partial sweep (7 of 10 steps audited) as a complete clean reconcile — re-introducing exactly the false-assurance step 4 added `skipped_steps` to surface. Freezing the format without a coverage marker bakes the hazard in.

**Suggested action:** require the reconcile sidecar schema to record the audited/skipped step coverage (so the deferred reuse consumer can refuse to reuse a partial-coverage reconcile report) and lock it with a criterion in step 2.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index f1c5187f..32c7f146 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -47,5 +47,10 @@ steps:
     --fail-on-findings) across all five registration seams; reuse-prompt wiring of
     resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
-    --target code requires --step (single-step audit)'
+    --target code requires --step (single-step audit), and --step is rejected at
+    parse time when combined with --reconcile (usage error, non-zero rc — the reconcile
+    direction is whole-plan full-surface, so a single --step is meaningless against it);
+    cmd_security renders
+    result.skipped_steps alongside the findings so a partial reconcile sweep (step 4)
+    is reported as partial, not as a clean pass'
   files:
   - plan_tool/cli/app.py
@@ -75,5 +80,9 @@ steps:
     persistence suppressed so write_security_report is the sole on-disk writer) back
     into a SecurityAuditResult so step 3's cmd_security can render result.findings
-    and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(...,
+    and persist via write_security_report; because the generalized hook's best-effort loop
+    skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel
+    to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit)
+    and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default —
+    so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(...,
     target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
     the reconcile family uses resolve_saved_review in review_persistence
@@ -255,5 +264,5 @@ Security is **already a per-step review mode**, but only at the per-step level:
 ## Architecture
 
-A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`.
+A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`. **`--step` is rejected at parse time when combined with `--reconcile`** (a usage error, non-zero rc, never dispatching): the reconcile direction derives its scope from the full plan⇄code surface (every step and its declared files), so a single `--step` is meaningless against it — `plan-tool security --reconcile --step <id> <name>` is an error, not a one-step reconcile, keeping the whole-plan full-surface contract unambiguous. `--step` remains required for `--target code` (single-step audit) and unused for `--target plan`.
 
 A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit` reuse pattern. Because `target="plan"`, `target="code"`, and `target="reconcile"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json` vs `-security-reconcile.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a `--target code` caller can never resolve a `target="plan"` save, nor vice versa — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa. Beyond the target suffix, the **`target="code"` axis must additionally scope its lookup by `step_id`**: the `-security-code.json` suffix encodes only the target, not the step, so two steps' code audits write same-suffix sidecars — `resolve_reusable_security` for the code target must therefore key on `step_id` (mirroring the reconcile family's per-step `_find_saved_for_step`), not return the newest target-suffix sidecar (the whole-plan `resolve_reusable_audit` shape it is otherwise cloned from), or it would serve one step's saved code audit to a different step's caller. **`resolve_reusable_security` ships dormant in this plan:** step 2 builds it and step 3 writes the `<ts>-security-<target>.json` sidecar, but **no in-plan step reads the resolver** — the reuse-prompt wiring that would short-circuit a Claude call on an unchanged fingerprint is deferred to a follow-up for all three targets (see `## Deferred`). The persistence/lookup machinery lands write-ready so the follow-up only adds the consumer; this plan does not claim a reuse short-circuit it does not deliver.
@@ -261,5 +270,5 @@ A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by generalizing the `run_auto_reconcile_on_drift` hook (`auto_reconcile.py`) to audit plan-stated security intent against the code's actual security posture under a `mode="security-reconcile"` prompt and emit drift findings, so a code change since the last security audit re-triggers it. **No `security-reconcile` row is added to `cli/reconcile.py:_RECONCILE_KINDS`** — it would be dead config: the existing `detail-reconcile` / `run-reconcile` `name_includes` suffixes are substring-disjoint from `-security-reconcile`, so they already cannot mis-grab a security sidecar, and no production caller queries `resolve_reusable_reconc
````

## 13. `security-check-command|2026-06-14T02:22:31Z|plan-plan-completeness-fd8a64b3`

**Cited step:** 2: Add resolve_reusable_security + fingerprinted <ts>-security.json persistence (sibling of resolve_reusable_audit); scope reuse by target/source (plan vs code) as well as kind+fingerprint so a plan-axis caller never reuses a code-axis report or vice versa (per-target scoping lands here, not deferred)

**Finding (plan-completeness, high):** The Architecture mandates that security reuse "must scope by target/source as well as kind+fingerprint" so "a plan-audit

The Architecture mandates that security reuse "must scope by target/source as well as kind+fingerprint" so "a plan-audit reuse must never serve a code-audit report or vice versa," but no step operationalizes it: step 2 (`add resolve_reusable_security`) builds a flat newest-`-security.json`-by-suffix resolver and defers target scoping to step 3; step 3 defers the entire reuse path to a follow-up; and step 5's `_sample_security_audit` calls the flat `resolve_reusable_security` with no target filter. A `--target code --step` save (`source="security-code"`, same `-security.json` suffix) is therefore the newest sidecar a plan-axis completeness run reuses, folding code findings into the plan dimension.

**Suggested action:** assign the per-target/source reuse scoping the Architecture requires to a concrete step (step 2 or step 3) so the plan and code axes never cross-serve

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index c2880123..0129b00a 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -21,5 +21,7 @@ steps:
 - id: 2
   title: Add resolve_reusable_security + fingerprinted <ts>-security.json persistence
-    (sibling of resolve_reusable_audit)
+    (sibling of resolve_reusable_audit); scope reuse by target/source (plan vs code)
+    as well as kind+fingerprint so a plan-axis caller never reuses a code-axis report
+    or vice versa (per-target scoping lands here, not deferred)
   files:
   - plan_tool/security_audit.py
@@ -53,6 +55,12 @@ steps:
 - id: 4
   title: 'Add security-reconcile ReconcileKind + run_auto_reconcile_on_drift hook and
-    teach run_security_audit the reconcile target wired to it for plan⇆code security
-    drift'
+    teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add the
+    dispatch branch) wired to it for plan⇆code security drift, and construct the standalone
+    full plan⇄code surface drift scope (every step and its declared files in scope) so
+    security --reconcile runs on a tree with no recorded file drift — synthesize that
+    whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every
+    step''s declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift''s
+    int / self-persisted security-reconcile.json output back into a SecurityAuditResult so
+    step 3''s cmd_security can render result.findings and persist via write_security_report'
   files:
   - plan_tool/cli/reconcile.py
@@ -142,5 +150,7 @@ steps:
     and prompts/security.md, populate rec.anchor in _security_recommendations, seed
     SECURITY_AUTO_APPLY_ALLOWLIST with hardcoded-secret, and wire security_finding_is_auto_applicable
-    into the --iterate convergence apply loop'
+    into the --iterate convergence apply loop; update RUNBOOK.md to document the now-active
+    allowlist and apply-loop wiring (auto-apply is no longer advisory-only) since step
+    8 documents only the inert step-7 primitive'
   files:
   - plan_tool/prompts/security-plan.md
@@ -149,4 +159,5 @@ steps:
   - plan_tool/convergence.py
   - plan_tool/review_walk.py
+  - RUNBOOK.md
   - tests/test_security_audit.py
   - tests/test_convergence.py
@@ -176,9 +187,9 @@ A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by extending the `ReconcileKind` descriptor family (`cli/reconcile.py`) with a `security-reconcile` kind that audits plan-stated security intent against the code's actual security posture and emits drift findings, reusing `resolve_reusable_reconcile` fingerprinting and the `run_auto_reconcile_on_drift` hook so a code change since the last security audit re-triggers it. The standalone `plan-tool security --reconcile <name>` does **not** depend on in-run file drift: it derives its drift scope from the full plan⇄code surface — treating every plan step (and the files each step declares) as in scope — so it runs the intent-vs-posture comparison across the whole plan even on a tree with no recorded file drift. The `run_auto_reconcile_on_drift` hook's file-drift-gated path (caller-supplied `drifted`/`file_to_step`, auditing only steps that own drifted files) stays the completeness/iteration-loop re-trigger mechanism (step 5), distinct from the standalone command's full-surface sweep. This requires a **dedicated drift prompt** that compares the plan's stated security intent against the code's actual posture (e.g. detecting a plan that *states* an authz step the code lacks); reusing the per-step `prompts/security.md` code audit via `mode="security"` does **not** satisfy these drift semantics — it only re-runs a code-only audit and cannot detect plan-vs-code divergence in the reconcile direction. Step 4 must author this drift prompt rather than relabeling the per-step code audit.
+Reconcile is added by extending the `ReconcileKind` descriptor family (`cli/reconcile.py`) with a `security-reconcile` kind that audits plan-stated security intent against the code's actual security posture and emits drift findings, reusing `resolve_reusable_reconcile` fingerprinting and the `run_auto_reconcile_on_drift` hook so a code change since the last security audit re-triggers it. The standalone `plan-tool security --reconcile <name>` does **not** depend on in-run file drift: it derives its drift scope from the full plan⇄code surface — treating every plan step (and the files each step declares) as in scope — so it runs the intent-vs-posture comparison across the whole plan even on a tree with no recorded file drift. Step 5's completeness security dimension re-triggers by **fingerprint-gated reuse**, not the hook: on an unchanged plan+code fingerprint it reuses the saved `<ts>-security.json` report and skips the Claude pass, re-sampling only on a fingerprint miss — distinct from the standalone command's full-surface sweep. Wiring `run_auto_reconcile_on_drift`'s file-drift-gated path (caller-supplied `drifted`/`file_to_step`, auditing only steps that own drifted files) into the completeness/iteration loop is deferred to a follow-up step, not done in step 5. This requires a **dedicated drift prompt** that compares the plan's stated security intent against the code's actual posture (e.g. detecting a plan that *states* an authz step the code lacks); reusing the per-step `prompts/security.md` code audit via `mode="security"` does **not** satisfy these drift semantics — it only re-runs a code-only audit and cannot detect plan-vs-code divergence in the reconcile direction. Step 4 must author this drift prompt rather than relabeling the per-step code audit.
 
 The CLI subcommand lives in `cli/security_cmd.py` following the `review_cmd.py` pattern: a `register(subparsers) -> dict[str, Handler]` export and a `cmd_security(args) -> int` handler, added to the command-module registry and to `CANONICAL_COMMAND_ORDER` in `parser.py`, with `--fail-on-findings` support.
 
-Completeness integration adds a deterministic pre-pass plus a claude security dimension to `completeness_phases.py`: the security audit call is added alongside `_run_deterministic_checks()` but joins the conceptual (claude-backed) layer rather than the deterministic one; security findings are grouped in `_render_grouped_report()` as their own labeled section; and a `security` bucket is added to `_render_completeness_json()`. The completeness dimension reuses step 2's `<ts>-security.json` sidecar via `resolve_reusable_security` — on an unchanged plan+code fingerprint it reuses the saved report and skips the Claude pass, re-sampling (and persisting via `write_security_report`) only on a fingerprint miss. Cost is gated — the security dimension runs only when the plan touches security-relevant files/areas, or behind an explicit `--with-security` flag if always-on is too expensive — with the default decided in the detail step.
+Completeness integration adds a deterministic pre-pass plus a claude security dimension to `completeness_phases.py`: the security audit call is added alongside `_run_deterministic_checks()` but joins the conceptual (claude-backed) layer rather than the deterministic one; security findings are grouped in `_render_grouped_report()` as their own labeled section; and a `security` bucket is added to `_render_completeness_json()`. The completeness dimension reuses step 2's `<ts>-security.json` sidecar via `resolve_reusable_security` — on an unchanged plan+code fingerprint it reuses the saved report and skips the Claude pass, re-sampling (and persisting via `write_securit
````

## 14. `arm-clustering-cross-round-consensus|2026-08-12T19:37:39Z|plan-plan-correctness-06786201`

**Cited step:** 5: Update the docs for the cross-round advisory and settle the backlog entries

**Finding (plan-correctness, medium):** Step 5's acceptance criterion says CLAUDE.md's `convergence_diagnosis.py` import line and the module's own "cycle-free l

Step 5's acceptance criterion says CLAUDE.md's `convergence_diagnosis.py` import line and the module's own "cycle-free leaf" docstring paragraph "name the same fact today" — checked against the code, they already don't. CLAUDE.md says the module "imports only `review_persistence`, `review`, `locator`, `convergence`"; the module's own docstring says "it imports `review_persistence`, `review`, and `locator`... so every import sits at module top" — the docstring already drops `convergence`, and both already drop `granularity` (`from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE`). If step 5 only appends the new `audit_shapes` edge step 2 adds, both statements ship still wrong about `granularity` and still disagreeing with each other about `convergence` — the exact staleness step 5 says it wants to prevent for the next session.

**Suggested action:** have step 5 correct both statements to the module's full current import set (`review_persistence`, `review`, `locator`, `convergence`, `granularity`, plus the new `audit_shapes` edge), not only append the one edge this plan adds.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
index dc35c926..d82b3756 100644
--- a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
+++ b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
@@ -80,6 +80,10 @@ steps:
   title: Update the docs for the cross-round advisory and settle the backlog entries
   intent: 'Keep the always-injected guidance honest once this ships, so the next session
-    does not read `--audit-passes 1 disables it outright`, the four-import leaf claim,
-    or an open #264 as still true.'
+    does not read `--audit-passes 1 disables it outright`, the four-import leaf claim
+    in CLAUDE.md, `convergence_diagnosis.py`''s own matching "cycle-free leaf" docstring
+    paragraph, or `docs/ARCHITECTURE.md`''s third restatement of the same
+    "review_persistence, review, locator, convergence" import list (all three name the
+    same fact and all three need the same audit_shapes.py import added by step 2), or
+    an open #264 as still true.'
   files:
   - CLAUDE.md
@@ -87,4 +91,5 @@ steps:
   - docs/AUDIT_FLOW.md
   - BACKLOG.md
+  - plan_tool/convergence_diagnosis.py
   complexity: medium
   change_type: non-code
@@ -144,10 +149,14 @@ settled precedent, not a gap to redesign.
    unaffected — they keep reading `observations_by_id` and the transient tag
    directly.
-2. Materiality: treat a saved finding as material via
+2. Materiality: treat a matched finding as material via
    `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=…)`
-   — the same rule `classify_edit_drift`'s `_edit_drift_eligible` already
-   applies to `RunFinding` objects pulled from history
-   (`convergence_diagnosis.py:885`). This is a different, deliberate choice
-   from same-execution arm-clustering's `is_blocking_impact` +
+   checked **only against the newest round's copy** of that finding — the
+   same rule `classify_edit_drift`'s `_edit_drift_eligible` already applies to
+   `RunFinding` objects pulled from history (`convergence_diagnosis.py:885`),
+   and the same newest-round keying point 7 already uses for the output
+   mapping. A finding's severity/impact tag can differ across matched rounds;
+   only the newest round's copy decides materiality, never a mix or an
+   older round's. This is a different, deliberate choice from same-execution
+   arm-clustering's `is_blocking_impact` +
    `build_low_impact_demotion_lookup(repo_root)` (`review.py:7929,7774`),
    which rebuilds a live per-run calibration lookup and was designed for a
@@ -176,8 +185,17 @@ settled precedent, not a gap to redesign.
    targets disagree; a target is missing on some round; a step's renumbering
    breaks target continuity even though the finding still matches by
-   anchor/title; **or** the single agreed target is not among the *current*
-   round's `declared_step_ids` (the step was deferred, marked `wont_do`,
-   deleted, or renumbered since the last matched round). Never guess a target
-   and never pass an unresolved or stale one through.
+   anchor/title; the single agreed target is not among the *current* round's
+   `declared_step_ids` (the step was deferred, marked `wont_do`, deleted, or
+   renumbered since the last matched round); **or** the target step's current
+   `status` is `done`. `declared_step_ids` / `committed_step_ids` is built
+   from `StepScope.COMMITTED` (`completeness_report.py:122`,
+   `review.py:8059`), which is the commitment axis, not the lifecycle axis
+   (`schema.py:StepScope`) — a shipped step stays `scope: committed` and so
+   stays in that list, so list membership alone cannot detect a target that
+   shipped between the matched rounds and a later `plan-tool convergence`
+   read. Check the target step's `status` directly; this plan's own
+   governing rule (a `done` step is "shipped: context, never a target") is
+   how a stale-but-shipped target must be treated here too. Never guess a
+   target and never pass an unresolved or stale one through.
    `evaluate_arm_clustering` returns `None` for the *entire* advisory the
    moment any id in `material_finding_ids` lacks a target inside the
@@ -188,5 +206,21 @@ settled precedent, not a gap to redesign.
    ids), that same resolved-subset `material_finding_ids`, and the newest
    round's committed `declared_step_ids` into `evaluate_arm_clustering`
-   unchanged. The leaf's own gap-free proper-majority-arm math is not touched.
+   unchanged. Two more of the leaf's parameters are not optional in practice
+   and must be supplied, matching same-execution's own call
+   (`review.py:8064-8076`): `material_finding_evidence` — built from the
+   newest round's own `RunFinding.anchor`/`.source` for each resolved id
+   (already-persisted fields, no new plumbing) — since an empty evidence
+   tuple defaults every item to `anchor=None`, which
+   `completeness_report.py`'s renderer (`_advisory_arm_steps`,
+   line ~149-157) skips, leaving the printed arm's finding list empty; and
+   `source_plan_fingerprint` — the plan's *current* fingerprint computed at
+   call time (not a saved round's), matching how same-execution stamps
+   `audit_input_snapshot.fingerprint` and how `completeness_report.py`'s
+   `matches_disk` staleness check consumes it. Leaving either at its
+   signature default (`()` / `""`) is a caller bug, not a valid choice: an
+   empty `source_plan_fingerprint` fails `_is_valid_stored_arm_advisory`'s
+   own non-empty check (`audit_shapes.py:121`) and voids the advisory
+   outright. The leaf's own gap-free proper-majority-arm math is not
+   touched.
 8. When the classifier has nothing to report — including when a previously-
    firing arm's cross-round consensus becomes unresolvable — the render emits
@@ -253,5 +287,5 @@ See the `steps:` block in the frontmatter.
   the field and its `DATA_CONTRACT.md` entry must land in the same step, not
   split across steps 1 and 5.
-- A silent non-fire (Architecture point 7) is easy to misread from the outside
+- A silent non-fire (Architecture point 8) is easy to misread from the outside
   as "the arm resolved" rather than "evidence became unavailable." Acceptance
   criteria settle this as accepted, explicitly-decided behavior rather than a
@@ -260,4 +294,9 @@ See the `steps:` block in the frontmatter.
 - Windowing on the wrong `audit_stage` (mixing bare and detail history) would
   manufacture a consensus target that never coexisted in one coherent audit.
+- `evaluate_arm_clustering`'s `material_finding_evidence` and
+  `source_plan_fingerprint` both default to empty/falsy values that are easy
+  to leave unset by omission rather than by decision — the former silently
+  degrades the render, the latter silently voids the whole advisory. Both are
+  named explicitly in Architecture point 7 so they are supplied by decision.
 
 ## Testing
@@ -266,22 +305,31 @@ Prove: (1) the plan-audit's parsed `[audit-step:N]` tag round-trips onto a
 saved `Recommendation`/`RunFinding` via `save_review`/`resolve_saved_review`,
 documented in `DATA_CONTRACT.md`; (2) materiality for cross-round consensus is
-computed via `is_blocking_finding` (stage-aware, matching
-`classify_edit_drift`'s own use on `RunFinding`s), independent of and not
-required to agree with same-execution's `is_blocking_impact` +
-calibration-lookup materiality; (3) a finding with a stable `_matches` identity
-and one agreeing persisted `audit_step_target` across the 2-round window
-produces a resolved consensus target; (4) a finding whose matched target
-disagrees, is missing on one round, or agrees across the window but is absent
-from the *current* `declared_step_ids` (deferred/`wont_do`/deleted/renumbered
-since the match), is dropped from **both** `consensus_targets` and the
-`material_finding_ids` passed to `evaluate_arm_clustering`, never causing the
-whole advisory to return `None`; (5) a renumbered step that 
````

## 15. `roadmap-revision-retention|2026-08-19T13:34:16Z|plan-plan-correctness-e85df478`

**Cited step:** 1: Add the removed row's content snapshot to RemovalRecord, populated mechanically from the predecessor's own rendered row content — never model-authored — and rendered back on every artifact rewrite

**Finding (plan-correctness, high):** The Architecture section fully specifies a fix to `check_design_row_continuity`'s tamper handling — distinguishing an ex

The Architecture section fully specifies a fix to `check_design_row_continuity`'s tamper handling — distinguishing an exact-match absence from a near-match one (a predecessor removal record with the same `removed_id` but a differing field) and giving the near-match case a "revert the tampered field" message instead of `VIOLATION_REMOVAL_WITHOUT_A_PREDECESSOR_ROW`'s current "drop the record" text (`roadmap_gates.py:1358`, message body confirmed at HEAD) — but no step's title, intent, or `depends_on_notes` assigns this branch as a deliverable. Step 1 and step 2 both list `roadmap_gates.py` in `files:`, but neither's title mentions tampering, near-match detection, or field-naming, unlike the closed-state fix which step 4's `depends_on_notes` on step 3 now explicitly owns ("makes a closed row legal to carry"). This matters because the branch spans both new fields: step 1 lands before `decision_reference` exists, so if step 1 builds the near-match check it can only compare `snapshot` (plus the pre-existing fields), and step 2 must then extend the same branch to compare `decision_reference` too — a two-step incremental build the plan never states. The acceptance criterion ("the model may not alter a carried removal's snapshot or decision reference … with a message telling the model to revert the tampered field rather than drop the record") and the matching Testing bullet both depend on this unassigned mechanism.

**Suggested action:** assign the near-match/exact-match branch and its field-naming message to step 1 (covering the fields that exist at that point), and add a step 2 note that it extends the same branch to compare `decision_reference` once that field lands

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-revision-retention.md b/docs/implementation-plans/2-roadmap-revision-retention.md
index 6f58492e..71f49c1d 100644
--- a/docs/implementation-plans/2-roadmap-revision-retention.md
+++ b/docs/implementation-plans/2-roadmap-revision-retention.md
@@ -10,13 +10,14 @@ enforce_step_tests: true
 steps:
 - id: 1
-  title: Add the removed row's content snapshot to RemovalRecord, render it back on
-    every artifact rewrite, and require it only on newly declared removals
+  title: Add the removed row's content snapshot to RemovalRecord, populated mechanically
+    from the predecessor's own rendered row content — never model-authored — and
+    rendered back on every artifact rewrite
   intent: So a reader of a revised roadmap can see what the dropped row actually said
-    instead of having to go read git.
+    instead of having to go read git, with no faithfulness question to gate because
+    the render layer derives the snapshot rather than the model paraphrasing it.
   files:
   - plan_tool/roadmap_artifacts.py
   - plan_tool/roadmap_gates.py
   - plan_tool/roadmap_view.py
-  - plan_tool/prompts/roadmap-revision.md
   - tests/test_roadmap_artifacts.py
   - tests/test_roadmap_gates.py
@@ -26,8 +27,10 @@ steps:
   status: current
 - id: 2
-  title: Add the optional decision reference to RemovalRecord, render it back, and
-    check it names a decision the artifact declares
+  title: Add the optional decision reference to RemovalRecord, render it back, check
+    it names a decision the artifact declares, and add it to the revision prompt's
+    removals field list and worked example as a model-suppliable field
   intent: So a removal can point at the decision whose rejected alternatives explain
-    the drop, instead of leaving the reasoning stranded in a separate collection.
+    the drop, instead of leaving the reasoning stranded in a separate collection —
+    and so the model actually knows the field exists to supply it.
   files:
   - plan_tool/roadmap_artifacts.py
@@ -46,8 +49,12 @@ steps:
       join whole-record carry identity.
 - id: 3
-  title: Add `closed` to FeedbackState, keep the reviewer's delete-the-row close working,
-    and replace the gates' 'close by deleting the row' correction text
-  intent: So a reviewer can answer and retire a feedback request in the file itself,
-    and the record of what was asked and how it was answered stays in the artifact.
+  title: Add `closed` to FeedbackState and update the dropped-feedback gate's violation
+    message and the revision prompt's state enum, carry-forward instruction, and
+    "never do" text — all three currently say the only close is deleting the row
+  intent: So a reviewer can retire a feedback request by setting its `state` field
+    to `closed` in the file instead of deleting it, and the record of what was
+    asked and how it was answered stays in the artifact; a reviewer keeps full
+    deletion rights over any row, closed included, so this retention binds only
+    the model's own edits, never the reviewer's.
   files:
   - plan_tool/roadmap_artifacts.py
@@ -60,8 +67,10 @@ steps:
   change_type: feature
 - id: 4
-  title: Add a gate requiring closed feedback rows to come after every other row in
-    the feedback collection
+  title: Add a gate rejecting a revision whose `feedback` collection places a `closed`
+    row before a non-`closed` row, and tell the model in the revision prompt to keep
+    closed rows last when it re-emits the collection
   intent: So the live part of the review queue reads first and retained closed rows
-    accumulate at the end instead of interleaving with open requests.
+    accumulate at the end instead of interleaving with open requests, and the model
+    has the guidance it needs to satisfy the gate on the first attempt.
   files:
   - plan_tool/roadmap_gates.py
@@ -94,8 +103,12 @@ steps:
       `state: closed` is the supported close so the CLI guidance can name it.'
 - id: 6
-  title: Rename `--mode review` to `--mode history`, dropping the `review` spelling
-    from the choices with no alias
+  title: Rename `--mode review` to `--mode history` everywhere it appears — the argparse
+    choices, MODE_REVIEW's branch sites and docstrings in roadmap_view.py (including
+    its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text, and
+    every literal `--mode review` example in README.md, docs/ROADMAP_WALKTHROUGH.md,
+    and docs/ARCHITECTURE.md — dropping the `review` spelling with no alias
   intent: So the flag says what the mode shows now that the collections it surfaces
-    retain history rather than only pending review work.
+    retain history rather than only pending review work, and no operator-facing
+    text anywhere still tells someone to pass a value the parser now rejects.
   files:
   - plan_tool/roadmap_view.py
@@ -113,10 +126,17 @@ steps:
   - 5
 - id: 7
-  title: Document the removal snapshot, the decision reference, the `closed` state,
-    and the closed-last ordering rule in ROADMAP_FORMAT.md
+  title: Document the removal snapshot, the decision reference, and the `closed` state
+    (including the closed-last ordering rule) in ROADMAP_FORMAT.md — correcting all
+    three existing "no `closed` member" sites (the schema block's `state` comment,
+    the Closed vocabularies table, and the feedback-lifecycle's situation 5) rather
+    than adding fresh prose beside them — and correct RUNBOOK.md's close-request
+    table row and "Preserved by the gates" tables to match
   intent: So the review collections' schema is readable without opening the parser,
-    which is what the whole FORMAT-doc family exists to guarantee.
+    which is what the whole FORMAT-doc family exists to guarantee, and so a reviewer
+    who trusts RUNBOOK.md's walkthrough learns the retention path exists instead of
+    being told deletion is still the only way to close a request.
   files:
   - ROADMAP_FORMAT.md
+  - RUNBOOK.md
   - tests/test_roadmap_format.py
   complexity: high
@@ -165,5 +185,8 @@ Three additive changes to the shared review-collection shape:
   content as it stood at removal.
 - `FeedbackState` gains `closed`; closed rows are retained in the `feedback`
-  collection (never deleted) and render last within it.
+  collection — never deleted by the model — and render last within it. A
+  reviewer, editing the file directly before a run, keeps full deletion
+  rights over any row, closed included, exactly as today; retention binds
+  only the model's own edits.
 - `RemovalRecord` gains an optional reference to the `DecisionRow` whose
   `rejected_alternatives` explain the drop.
@@ -204,4 +227,17 @@ retention in the one place `check_feedback_integrity` and
 a second collection would mean two places to look for a feedback id.
 
+**The snapshot is mechanically captured, never model-authored.** When a
+removal is newly declared — its `removed_id` not yet in `carried` — the
+render layer copies the predecessor's own rendered content for that row
+into the snapshot before the artifact is written; the model supplies only
+`removed_id`, `rationale`, and `feedback_ids`, exactly as it does today, and
+step 1 makes no prompt change. This is why `## Not allowed`'s ban on a
+faithfulness gate is safe: there is no faithfulness question to gate,
+because the snapshot is derived from the row's own last-known-good render
+rather than paraphrased. It stays inside BACKLOG #242's "no orchestrator
+change" boundary because the capture is a render-time transform in
+`roadmap_artifacts.py`, not a change to `roadmap.py`'s stage-running
+orchestrator.
+
 **Removal-carry identity is whole-record equality, and the new fields join
 it — this is what makes the fields' immutability enforceable for free.**
@@ -217,4 +253,18 @@ asks the model to touch a carried record afterward. No separate
 immutability gate is needed for these two fields.
 
+A tampered carried removal — one field edited, so it no lo
````

## 16. `roadmap-candidate-vocabulary-retry|2026-09-25T17:28:17Z|plan-plan-correctness-3839f530`

**Cited step:** 2: Retry rejected ledger replies once; preserve one candidate publication, guarded pointer and ledger replacements, and exact response receipts

**Finding (plan-correctness, high):** Step 2 (`Retry rejected ledger replies once; preserve one candidate publication, guarded pointer and ledger replacements

Step 2 (`Retry rejected ledger replies once; preserve one candidate publication, guarded pointer and ledger replacements, and exact response receipts`) requires receipt semantics for each attempt but does not say when the first rejected response becomes durable before the correction call or how both attempts are represented on exhaustion. Current `roadmap_candidate_run:_run_batch_candidate_proposal` has one invocation, while outer failure diagnostics retain only `last_response`; without an explicit lifecycle, a retry can satisfy the two-call count while losing the first reply’s exact receipt. This affects Architecture, Scope guardrails, Testing, Acceptance criteria, and step 2.
  
  ```
  “Each attempt keeps redacted telemetry and the existing response receipt semantics; exhaustion reports `response-rejected` with call count 2.”
  ```

**Suggested action:** Specify the per-attempt rejection, receipt, telemetry, and terminal-reporting lifecycle for step 2, ensuring the first rejected reply is retained before correction and exhaustion reports both attempts without candidate publication.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md b/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md
index f2dec4f9..7f659fc0 100644
--- a/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md
+++ b/docs/implementation-plans/2-roadmap-candidate-vocabulary-retry.md
@@ -15,8 +15,10 @@ source_seed: plan-seeds/roadmap-candidate-vocabulary-retry.md
 steps:
 - id: 1
-  title: Show the valid collection name for every batch row class
+  title: Show valid collection names and disambiguate existing batch rows
   intent: A model adding a Domain entity can choose `entities` when the issued context
-    names `EntityRow`.
+    names `EntityRow`, and can distinguish the two collections containing `PatternRow`.
   files:
+  - plan_tool/roadmap_candidate_context.py
+  - plan_tool/roadmap_candidate_run.py
   - plan_tool/prompts/roadmap-candidate-delta.md
   - tests/test_roadmap_candidate_run.py
@@ -25,5 +27,5 @@ steps:
   status: current
 - id: 2
-  title: Retry rejected ledger replies within a fixed budget; preserve one candidate
+  title: Retry rejected ledger replies once; preserve one candidate
     publication, guarded pointer and ledger replacements, and exact response receipts
   intent: Malformed replies get a chance to correct themselves, and exhaustion leaves
@@ -37,5 +39,5 @@ steps:
   - 1
   depends_on_notes:
-    1: The first prompt gives every attempt the valid row vocabulary.
+    1: The first prompt gives both attempts valid row vocabulary and exact existing-row collection hints.
 - id: 3
   title: Remove the IPPT-10 promotion stub after the behavior and tests ship
@@ -60,9 +62,9 @@ The 2026-09-25 Integration proposal returned `candidate proposal: response-rejected` fo
 ## Architecture
 
-Present the closed internal-class-to-collection vocabulary in the model-facing prompt or rendered view, without changing the issued capsule, receipt, stored `row_type`, or strict delta parser. Add a bounded correction attempt sequence to the ledger-batch proposal path for parse and candidate-materialization rejections. Failed transport and storage remain their existing failure classes. Each attempt keeps redacted telemetry and the existing response receipt semantics, with an exact terminal result and call count. Reuse the same immutable batch and receipt across attempts; a valid reply stores through the existing publication boundary.
+Present the closed internal-class-to-collection vocabulary in the model-facing prompt or rendered view, without changing the issued capsule, receipt, stored `row_type`, or strict delta parser. `PatternRow` has two valid collections, `system_patterns` and `component_patterns`; for an existing row reference, derive its exact collection from the source artifact and show that as a syntax hint bound to the issued row identity. The hint grants no edit authority beyond the capsule. Add one correction opportunity after a parse or candidate-materialization rejection: at most two total model calls for a ledger batch. Failed transport and storage remain their existing failure classes. Each attempt keeps redacted telemetry and the existing response receipt semantics; exhaustion reports `response-rejected` with call count 2. Reuse the same immutable batch and receipt across attempts; a valid reply stores through the existing publication boundary.
 
 ## Scope guardrails
 
-The binary observable is that an ordinary ledger request to add a Domain entity reaches a stored structural candidate when the model uses `entities`, while malformed `EntityRow` replies exhaust a finite correction budget without candidate publication. The model-facing mapping cannot change capsule payload bytes, receipt/digest identities, authority, or replay keys. Correction cannot turn a transport or storage failure into a rejected model response.
+The binary observable is that an ordinary ledger request to add a Domain entity reaches a stored structural candidate when the model uses `entities`, while malformed `EntityRow` replies exhaust two total model calls without candidate publication. For every existing row reference, the model-facing hint identifies the actual collection, including either `system_patterns` or `component_patterns` for `PatternRow`; both collection names remain available for a new pattern. The hint cannot change capsule payload bytes, receipt/digest identities, authority, or replay keys. Correction cannot turn a transport or storage failure into a rejected model response.
 
 ## References
@@ -90,11 +92,11 @@ A mapping that rewrites issued context would invalidate stored evidence. A retry
 ## Testing
 
-Exercise an ordinary ledger batch that adds a Domain entity through the real prompt and storage path; prove the response reaches the structural decision gate. Exercise an `EntityRow` response followed by correction and exhaustion, checking prompt, bounded attempt count, redacted telemetry, exact response receipts, and no candidate publication. Replay stored context before and after the rendering change to prove byte and identity stability.
+Exercise an ordinary ledger batch that adds a Domain entity through the real prompt and storage path; prove the response reaches the structural decision gate. Include both kinds of `PatternRow` in source context and verify each exact existing-row hint. Exercise an `EntityRow` response followed by correction and exhaustion, checking the second prompt, two-call limit, redacted telemetry, exact response receipts, and no candidate publication. Replay stored context before and after the rendering change to prove byte and identity stability.
 
 ## Acceptance criteria
 
-- The model sees the valid collection token for every class name exposed by the batch context, including `EntityRow` to `entities`.
+- The model sees the valid collection token for every class name exposed by the batch context, including `EntityRow` to `entities`; each existing `PatternRow` is identified as either `system_patterns` or `component_patterns` according to its source collection.
 - A valid Domain entity operation stores an inert structural candidate and can enter the structural approve/edit/reject decision route.
-- A malformed class-name operation triggers a named, bounded correction attempt; exhaustion reports the exact failure and publishes no candidate.
+- A malformed class-name operation triggers one named correction attempt; exhaustion after two total model calls reports `response-rejected` with call count 2 and publishes no candidate.
 - Existing persisted capsule, receipt, digest, and replay identity remain unchanged; strict parsing still rejects class names.
 - The originating `BUG_BACKLOG.md` promotion stub is removed only after the implementation and tests ship; Jira IPPT-10 remains the work record during execution.

````

## 17. `roadmap-model-failure-receipts|2026-09-21T17:08:59Z|plan-plan-correctness-04ba575f`

**Cited step:** 3: Record fresh roadmap stage failures before retry while preserving accepted artifact writes

**Finding (plan-correctness, high):** Steps 3 (`Record fresh roadmap stage failures before retry while preserving accepted artifact writes`) and 4 (`Record bo

Steps 3 (`Record fresh roadmap stage failures before retry while preserving accepted artifact writes`) and 4 (`Record bounded roadmap feedback failures before retry while preserving accepted revision writes`) exclude gate-rejected replies from the receipt even though the Architecture’s `not-retained` disposition requires a receipt that correlates to `gate_violations`. Their tests and acceptance criteria instead require no model-failure receipt, so fresh and bounded gate failures violate the selected-producer receipt guarantee.

```text
Architecture — “The receipt's phase and attempt correlate it with the existing bounded `gate_violations` event”
```

```text
Step 3 Implementation — “the new receipt must not duplicate its messages”
Step 4 Implementation — “Do not persist a raw response or emit a model-failure receipt for `FAILURE_GATES`”
```

**Suggested action:** Define `not-retained` as a redacted receipt emitted alongside existing fresh and bounded gate diagnostics, then align steps 3–4, tests, and acceptance criteria without retaining raw replies or copying messages.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-model-failure-receipts.md b/docs/implementation-plans/2-roadmap-model-failure-receipts.md
index 47f7ccb6..a1d62143 100644
--- a/docs/implementation-plans/2-roadmap-model-failure-receipts.md
+++ b/docs/implementation-plans/2-roadmap-model-failure-receipts.md
@@ -28,4 +28,5 @@ steps:
   complexity: medium
   change_type: refactor
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/01-move-detail-raw-response-sidecar-writes.md
   status: current
 - id: 2
@@ -46,4 +47,5 @@ steps:
     1: Provides the shared sidecar result needed to record written, no-response, not-retained,
       and write-failed dispositions.
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/02-shared-redacted-model-failure-receipt.md
 - id: 3
   title: Record fresh roadmap stage failures before retry while preserving accepted
@@ -63,4 +65,5 @@ steps:
       stage, and attempt identifiers.
     2: Provides the redacted receipt shape and its closed sidecar dispositions.
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/03-record-fresh-roadmap-stage-failures.md
 - id: 4
   title: Record bounded roadmap feedback failures before retry while preserving accepted
@@ -80,9 +83,11 @@ steps:
     2: Provides the common receipt contract used for retained replies, absent replies,
       gate diagnostics, and sidecar write failures.
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/04-record-bounded-roadmap-feedback.md
 - id: 5
-  title: Record local feedback revision failures and reply-bearing gate rejections while
-    preserving recoverable publication replacement
+  title: Record local feedback revision failures and reply-bearing gate rejections
+    while preserving recoverable publication replacement
   intent: Give local --revise-feedback failures the same diagnostic evidence as roadmap
-    stage failures, retaining a rejected reply only when no structured gate diagnostic exists.
+    stage failures, retaining a rejected reply only when no structured gate diagnostic
+    exists.
   files:
   - plan_tool/roadmap_revision_run.py
@@ -97,4 +102,5 @@ steps:
       a local gate rejection that has no structured diagnostic event.
     2: Provides the shared receipt emitted after the sidecar disposition is resolved.
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/05-record-local-feedback-revision-failures.md
 - id: 6
   title: Document roadmap failure receipts and record the shipped backlog slice
@@ -118,4 +124,5 @@ steps:
     5: Delivers the local revision receipt behavior and completes the selected roadmap
       producer class.
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/06-document-roadmap-failure-receipts.md
 ---
 # Roadmap Model Failure Receipts
diff --git a/docs/implementation-plans/plan-details/roadmap-model-failure-receipts/03-record-fresh-roadmap-stage-failures.md b/docs/implementation-plans/plan-details/roadmap-model-failure-receipts/03-record-fresh-roadmap-stage-failures.md
new file mode 100644
index 00000000..b0c584be
--- /dev/null
+++ b/docs/implementation-plans/plan-details/roadmap-model-failure-receipts/03-record-fresh-roadmap-stage-failures.md
@@ -0,0 +1,101 @@
+# Step 3 — Record fresh roadmap stage failures before retry while preserving accepted artifact writes
+
+<!-- plan-tool:detail-format-version: 1 -->
+
+## Summary
+
+Add fresh-stage failure receipts to `plan_tool/roadmap.py` before `_run_stage` retries an invoke, parse, or authored-review-row failure. Reuse the shared sidecar and redacted receipt contracts delivered by steps 1 and 2, while keeping the current retry budget, correction prompts, artifact publication path, and gate diagnostics unchanged. Extend `tests/test_roadmap.py` around the existing retry-loop and `TestAttemptFailedEvent` coverage. On green, a failed fresh attempt remains diagnosable even when a later attempt writes the accepted artifact.
+
+## Table of Contents
+
+- [Summary](#summary) — Gives the reviewer the step’s outcome and main boundary.
+- [Table of Contents](#table-of-contents) — Links to the detail sections.
+- [Why](#why) — Explains the missing evidence for recovered fresh-stage failures.
+- [Input](#input) — Names the upstream receipt contracts this producer consumes.
+- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the focused code and test edits.
+- [Implementation](#implementation) — Defines when fresh-stage receipts are recorded and what remains unchanged.
+- [Tests](#tests) — Lists focused regression coverage for recovered failures and accepted writes.
+- [Acceptance criteria](#acceptance-criteria) — States observable completion conditions.
+- [References](#references) — Points to the relevant receipt and roadmap contracts.
+- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s safety and scope limits.
+- [Deferred](#deferred) — Identifies related producer paths outside this step.
+
+## Why
+
+`plan_tool/roadmap.py:_run_stage` records spent attempts through `_note_stage_attempt_failure`, but `attempt_failed` does not retain a response identity or best-effort raw-response availability. When a later attempt succeeds, `RoadmapResult` carries only the accepted artifact, so an earlier fresh invoke, parse, or authored-review-row failure lacks the complete redacted evidence this plan requires.
+
+## Input
+
+- **Step 1 sidecar contract:** Use the shared rejected-response sidecar result produced by step 1. Preserve its disposition and path outcome without reopening, transforming, or cleaning up the sidecar.
+- **Step 2 receipt contract:** Use the shared run-log receipt helper produced by step 2 for the producer-owned phase, attempt, failure reason, response identity, and sidecar result.
+- **Fresh-stage failure classification:** `plan_tool/roadmap.py:_run_stage`, `_StageOutcome`, and `FAILURE_AUTHORED_REVIEW_ROWS` define the fresh attempt paths that spend the stage budget. The established `FAILURE_INVOKE` and `FAILURE_PARSE` outcomes remain their current classifications.
+
+## Files (creates vs edits)
+
+- **New files:**
+  - None.
+
+- **Existing files (edits only):**
+  - `plan_tool/roadmap.py` — Record a shared failure receipt for reply-bearing fresh-stage invoke, parse, and authored-review-row failures before `_run_stage` retries.
+  - `tests/test_roadmap.py` — Add focused recovered-attempt receipt coverage beside `TestRetryLoop` and `TestAttemptFailedEvent`.
+
+## Implementation
+
+- **Record each rejected fresh reply before retrying.** Extend `plan_tool/roadmap.py:_run_stage` so the fresh authoring loop uses the step 1 sidecar owner and step 2 run-log helper for failures that have a model reply. Emit the receipt in the same attempt that `_note_stage_attempt_failure` records the existing attempt classification, before control continues to the next attempt.
+
+- **Keep identity tied to the rejected reply.** Derive the receipt’s byte count and digest from the original reply returned by `invoker`, not from lifted artifact text, parser errors, correction text, or `_reply_head`. A non-empty reply attached to a failed invocation remains receipt-eligible; an absent or empty reply must use the shared no-response disposition without inventing content.
+
+- **Cover both parse branches.** `_run_stage` can reject a reply because `_lift_artifact_text` cannot find an artifact or because `stage.parse` raises `RoadmapArtifactError`. Both paths must produce the same parse-kind receipt behavior, while retaining their current correction messages and retry behavior.
+
+- **Treat authored review rows as model failure evidence.** The `FAILURE_AUTHORED_REVIEW_ROWS` branch after `_authored_review_rows(artifact, None)` must produce a receipt for the reply it rejects. Preserve the branch’s current rule: fresh model output cannot create reviewer-owned feedback or removal records.
+
+- **Preserve acce
````

## 18. `roadmap-decision-settlement|2026-09-18T04:18:42Z|plan-plan-completeness-b03c1a13`

**Cited step:** 7: Document the settlement route; retire every live hand-edit settlement instruction (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md, RUNBOOK.md, docs/how-to/use-cases.md, integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md, docs/how-to/roadmap.md) with recovery guidance for an operator who already followed that advice; state that --revise-feedback still cannot change status; correct ROADMAP_FORMAT.md's Immutable candidate-version authority block and CAPABILITIES.md's accepted-head-authority statement to name both guarded writers, updating tests/test_roadmap_format.py::test_candidate_policy_reference_keeps_review_inert_until_exact_promotion to match, and separately correct the Decision status paragraph and gate-table row to confine the drift-protection claim to the un-enrolled lineage; add a settlement bullet to CAPABILITIES.md's roadmap entry beside the other roadmap actions, covering both lineages; state all three enrolled settlement limits with their backlog pointers (citable feedback must predate enrollment, backlog entry 394; a stalled candidate lineage blocks settlement permanently, backlog entry 395; non-canonical accepted bytes block settlement with no repair path) and that closing (deleting) the cited feedback row ends an un-enrolled receipt's proof; add the settlement receipt as a third EvidenceNamespace in docs/ARCHITECTURE.md; extend the "Incomplete immutable lifecycle journals" BUG_BACKLOG.md entry to name the new settlement generation shape(s); and remove the settlement BUG_BACKLOG.md entry now that the capability ships

**Finding (plan-completeness, medium):** Step 7 (`Document the settlement route; …`) never names `docs/reference/commands.md`, and neither does the docs acceptan

Step 7 (`Document the settlement route; …`) never names `docs/reference/commands.md`, and neither does the docs acceptance criterion. That file lists every other roadmap action (`--revise-feedback`, `--reopen-feedback`, `--escalate-feedback`, `--analyze-escalation`, …) in its command block and bullets. The command reference would be the one operator-facing command list that leaves out the new settlement action, even though step 7 updates README, CAPABILITIES, and the generated `docs/cli/roadmap.md`.

**Suggested action:** Add `docs/reference/commands.md` to step 7's document list and to the acceptance criterion that lists the docs that must describe the action.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index 80ac1b1b..4a7cb059 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -37,10 +37,11 @@ steps:
     named refusal per rejection class
   intent: Prove, before any write, that exactly one live Roadmap-derived pending decision
-    was named, that a named live feedback row actually targets it (not just resolves)
-    and carries non-empty reviewer-authored `request` text in any FeedbackState (never
-    model-authored `proposed_response`), that an un-enrolled source is admitted against
-    its recorded baseline, and that the source bytes (on-disk artifact for an un-enrolled
-    roadmap, accepted-version bytes for an enrolled one) have not moved since the
-    evidence was read.
+    was named with no duplicate id in the artifact, that a named live feedback row
+    (no duplicate id either) actually targets it (not just resolves) and carries
+    non-empty reviewer-authored `request` text in any FeedbackState (never
+    model-authored `proposed_response`), that an un-enrolled source is admitted
+    against its recorded baseline and is render-canonical, and that the source bytes
+    (on-disk artifact for an un-enrolled roadmap) and, on an enrolled roadmap, the
+    accepted head's own identity have not moved since the evidence was read.
   creates:
   - plan_tool/roadmap_decision_settlement.py
@@ -54,14 +55,21 @@ steps:
       contract its staleness recheck re-verifies
 - id: 3
-  title: Add the immutable settlement receipt record and its own evidence namespace
-    in plan_tool/roadmap_evidence_store.py, naming the exact resulting content digest
-    settlement is about to produce; publication stays create-once and keyed on its
-    own inputs so a retry resolves to the same already-published final, an existing
-    final is returned rather than overwritten, and nothing is deleted
-  intent: Make every successful settlement leave a durable, readable record — written
-    before the row-level write it proves, never after — of which artifact, decision,
-    predecessor digest, feedback evidence, and resulting content digest justify it,
-    so the approval can be proven after the fact and a receipt never outlives or
-    outraces the settlement it names.
+  title: Add the immutable settlement receipt record, its own evidence namespace in
+    plan_tool/roadmap_evidence_store.py, and a read-back check that takes a receipt
+    plus the roadmap's current state and reports whether it still proves a completed
+    settlement (accepted-version-or-predecessor membership on the enrolled lineage;
+    exact current-digest match, including a deleted evidence feedback row, on the
+    un-enrolled one); the receipt names the exact resulting content digest settlement
+    is about to produce, is committed to HEAD (created/reused/committed-existing vs.
+    commit-failed/collision/storage-rejected/invalid-existing-receipt/no-worktree),
+    and publication stays create-once and keyed on its own inputs so a retry resolves
+    to the same already-published final, an existing final is returned rather than
+    overwritten, and nothing is deleted
+  intent: Make every successful settlement leave a durable, readable, committed
+    record — created before the canonical write it proves, never after — of which
+    artifact, decision, predecessor digest, feedback evidence, and resulting content
+    digest justify it, with a shipped check (not a manual procedure) for whether that
+    proof still holds later, so a receipt never outlives or outraces the settlement
+    it names.
   files:
   - plan_tool/roadmap_evidence_store.py
@@ -80,9 +88,10 @@ steps:
   title: Settle one decision on an un-enrolled roadmap by publishing its receipt first,
     then, once source admission and staleness both hold, publishing through
-    publish_stage_artifact's multi-member generation with invalidate_seeds=False,
-    keeping the existing journal recovery (roll back or drop an in-flight generation)
-    unchanged and updating the selected artifact's bytes and its stage baseline record
-    together — seed state and every other artifact/stage stay byte-identical before
-    and after
+    publish_stage_artifact's multi-member generation with its default seed-invalidation
+    behavior (never invalidate_seeds=False), keeping the existing journal recovery
+    (roll back or drop an in-flight generation) unchanged and updating the selected
+    artifact's bytes, its stage baseline record, and tracked derived seed state (marked
+    invalidated, exactly like any other stage-level content change) together — no
+    other artifact or stage is rewritten
   intent: Let an operator settle an approved decision on an ordinary roadmap by naming
     it, naming its evidence, and confirming — with no hand-edit of a canonical artifact,
@@ -110,9 +119,10 @@ steps:
     entries — then advancing the accepted head through a new additive PendingGeneration.kind
     recovery branch that reuses promote_review_seal's writer-token/journal selector-swap
-    but never calls _load_complete_sealed_candidate or either evidence loader; refuses
-    an in-flight pending generation and an admitted, unpromoted candidate lineage whose
-    predecessor is the current accepted head; root-enrollment and review-seal-promotion
-    recovery stay exactly as they are, and stored version members are never overwritten
-    or deleted
+    but never calls _load_complete_sealed_candidate or either evidence loader; recovers
+    a recognized completed version-owned generation exactly as existing recovery does
+    and refuses anything else; refuses whenever the current accepted head carries an
+    admitted, unpromoted candidate lineage (permanently, if that lineage never resolves);
+    root-enrollment and review-seal-promotion recovery stay exactly as they are, and
+    stored version members are never overwritten or deleted
   intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one,
     for a decision whose approving feedback already exists in the accepted version
@@ -139,13 +149,17 @@ steps:
     plan-tool roadmap as one exclusive action (missing-confirm and companion-option
     refusals named, matching --reopen-feedback's confirmation-required/mode-rejected
-    precedent), regenerate docs/cli/roadmap.md, and prove both lineages produce the
-    same settled row and that check_settled_decisions refuses drift on an un-enrolled
-    settled row this route just settled
+    precedent), extend every other broad roadmap mode's own _*_has_conflict check
+    to refuse when the settlement flags are present (exclusivity in both directions,
+    not only the settlement flags refusing others), regenerate docs/cli/roadmap.md,
+    and prove both lineages produce the same settled row and that check_settled_decisions
+    refuses drift on an un-enrolled settled row this route just settled
   intent: Give the operator the actual command, with the confirm flag that makes settlement
     their decision rather than the tool's and no backend call anywhere on the path,
-    then show the enrolled and un-enrolled paths are one capability rather than two
-    look-alikes by asserting identical before/after row content across both — proving
-    only the un-enrolled drift refusal, not any claim about the enrolled lineage, which
-    step 7's docs disclose separately.
+    make that exclusivity hold no matter which side names the conflicting option
+    rather than letting a combined command silently run a different action and drop
+    the settlement request, then show the enrolled and un-enrolled paths are one
+    capability rather than two look-alikes by asserting identical before/after row
+    content across both — proving only the un-enrolled drift refusal, not any claim
+    about the e
````

## 19. `roadmap-revision-rollback|2026-09-18T19:04:10Z|plan-plan-correctness-feaa652a`

**Cited step:** 1: Add a roadmap revision checkpoint file that records, for every file a stage run can write (the four stage artifacts, their baselines, seed-state.json, and source.json), its pre-run bytes and the bytes the run last wrote, with absence recorded explicitly; discarding it deletes only the checkpoint file

**Finding (plan-correctness, medium):** Step 1 (`docs/implementation-plans/plan-details/roadmap-revision-rollback/01-roadmap-revision-checkpoint-file-that.md`) 

Step 1 (`docs/implementation-plans/plan-details/roadmap-revision-rollback/01-roadmap-revision-checkpoint-file-that.md`) defines `tracked_paths(plans_dir, slug) -> tuple[Path, ...]` returning ten *absolute* paths, and `CheckpointEntry.relative_path: str`, and its own Input section states the requirement plainly:

  ```
  its own per-entry relative-path convention (see Implementation) must
  match `GenerationMember.relative_path`'s convention exactly — root-relative,
  forward-slash, no leading `./` — or step 3's conversion breaks silently on
  the first hand-off.
  ```

  But nowhere in step 1's Implementation, References, or Tests does it name the mechanism that turns each absolute `tracked_paths()` entry into that relative-path string. The codebase already has exactly this helper, `roadmap_relative_stage_path` (`plan_tool/roadmap_artifacts.py:115-131`, `.resolve()` on both root and candidate before `.relative_to()`/`.as_posix()`), and step 2 explicitly imports it for the identical purpose ("It is not currently imported into `plan_tool/roadmap.py`; this step adds it..."), but step 1's own References section for `tracked_paths` lists only `roadmap_dir`, `domain_path`/`constraints_path`/`components_path`/`plans_path`, `brief_source_path` — never `roadmap_relative_stage_path`. An implementer of `capture_checkpoint` is left to invent this conversion, and a plausible but different implementation (e.g. `Path(p).relative_to(roadmap_dir(plans_dir, slug)).as_posix()` without first calling `.resolve()` on both sides) can diverge from `GenerationMember`'s convention under a symlinked temp directory (a real risk on macOS, where `/tmp` resolves to `/private/tmp`) even though it would pass step 1's own fixture-only tests, which never compare against `roadmap_relative_stage_path`'s output.

**Suggested action:** Name `roadmap_relative_stage_path` explicitly in step 1's Implementation and References as the function `capture_checkpoint` uses to derive each `CheckpointEntry.relative_path`, and add a test asserting the checkpoint's captured relative paths equal `roadmap_relative_stage_path`'s output for each of the ten tracked files.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-revision-rollback.md b/docs/implementation-plans/2-roadmap-revision-rollback.md
index 7de73cae..60aad30b 100644
--- a/docs/implementation-plans/2-roadmap-revision-rollback.md
+++ b/docs/implementation-plans/2-roadmap-revision-rollback.md
@@ -339,11 +339,15 @@ See the `steps:` block in the frontmatter.
   checkpoint bookkeeping update for it would leave the checkpoint stale in a
   way its own write-time check cannot distinguish from an outside change.
-  Step 2 closes this for both `source.json` writes (the write's own payload
-  is cheap to recompute and compare against the mismatched current bytes).
-  For `publish_stage_artifact`'s three-member write, closing it the same way
-  would require duplicating `_publication_members`' internal baseline/seed-state
-  derivation outside `roadmap_revision_publish.py`; this narrow, purely-local
-  window (no model call or network I/O inside it) is accepted as a known,
-  pinned residual instead, named explicitly rather than left implicit.
+  Step 2 closes this for `source.json`: when `admission` resolves to
+  `"matched"`, current bytes already reflect this tool's own settled write
+  (a genuine divergence would have produced a `"refused-*"` admission
+  instead), so the checkpoint's stale entry is reconciled to current bytes
+  as part of capture-or-continue, before either `source.json` write site is
+  ever reached. For `publish_stage_artifact`'s three-member write, no
+  equivalent signal is cheaply available without duplicating
+  `_publication_members`' internal baseline/seed-state derivation outside
+  `roadmap_revision_publish.py`; this narrow, purely-local window (no model
+  call or network I/O inside it) is accepted as a known, pinned residual
+  instead, named explicitly rather than left implicit.
 - `seed-state.json` is one of the ten tracked files, and `--refresh-seeds`,
   `--accept-seed`, and `--apply` are legitimate other writers of it, each
@@ -392,15 +396,19 @@ See the `steps:` block in the frontmatter.
   than reading the hand-edited value, writing its own new value on top, and
   recording that as the checkpoint's last-tracked bytes.
-- A run whose `source.json` write already landed in an earlier crashed
-  attempt in the same lineage (current bytes already equal the payload this
-  write would produce) does not refuse -- it skips the redundant write and
-  catches the checkpoint's bookkeeping up. A genuinely different mismatch
-  still refuses. A test also pins the accepted residual: a stage-publish
+- A run whose `admission` resolves to `"matched"` reconciles a stale
+  `source.json` checkpoint entry to current on-disk bytes as part of
+  capture-or-continue (proof that an earlier crashed attempt's write landed
+  without its checkpoint bookkeeping), rather than leaving that entry stale
+  until a later write or a restore call falsely refuses against it. A
+  genuine divergence never reaches `"matched"`, so it still refuses through
+  the ordinary path. A test also pins the accepted residual: a stage-publish
   crash between the commit and its checkpoint update still refuses, as a
   known, named limitation rather than a silently-absent one.
 - A dangling journal that is restore's own prior, interrupted attempt (not a
-  stage-publish journal) is excluded from a continuing run's or a direct
-  restore's checkpoint reconciliation, so restore reports "already-restored"
-  for its own already-completed prior attempt rather than "restored."
+  stage-publish journal) is excluded from both a continuing run's and a
+  direct restore's checkpoint reconciliation, so a stale, already-restored
+  checkpoint is never adopted as a brand-new revision's own baseline, and
+  restore reports "already-restored" for its own already-completed prior
+  attempt rather than "restored."
 - Run the complete suite. Regenerate the CLI reference with
   `python -m plan_tool.cli_reference --write`.
@@ -422,9 +430,9 @@ See the `steps:` block in the frontmatter.
   value for it, instead of silently recording its own new write over an
   untracked change.
-- A `source.json` write whose current bytes already equal the payload it was
-  about to produce (an earlier crashed attempt's write landed, but its
-  checkpoint bookkeeping did not) is recognized and does not refuse; the
-  equivalent gap for a stage-publish write is an accepted, explicitly-named
-  residual rather than a silently-missing case.
+- A `"matched"`-admission run recognizes and reconciles a `source.json`
+  checkpoint entry left stale by an earlier crashed attempt's write, rather
+  than refusing or silently masking a genuine divergence; the equivalent gap
+  for a stage-publish write is an accepted, explicitly-named residual rather
+  than a silently-missing case.
 - Restore reports "already-restored", not "restored", when the checkpoint it
   is resolving is its own prior, interrupted attempt.

````

## 20. `roadmap-decision-settlement|2026-09-18T01:26:10Z|plan-plan-correctness-2554a9bc`

**Cited step:** 5: Settle one decision on an enrolled roadmap by storing the settled artifact bytes as an ordinary version_kind candidate record — via create_candidate_version, with a new dedicated no-review sentinel in place of INITIAL_EMPTY_REVIEW_LINEAGE_ID and no candidate_evidence_path/replacement_evidence_path entries — then advancing the accepted head through a new additive PendingGeneration.kind recovery branch that reuses promote_review_seal's writer-token/journal selector-swap but never calls _load_complete_sealed_candidate or either evidence loader; refuses an in-flight pending generation; root-enrollment and review-seal-promotion recovery stay exactly as they are, and stored version members are never overwritten or deleted

**Finding (plan-correctness, high):** The plan's References section claims `check_settled_decisions` keeps a settled decision immutable once this route produc

The plan's References section claims `check_settled_decisions` keeps a settled decision immutable once this route produces one:

  ```
  `plan_tool/roadmap_gates.py` (`check_settled_decisions`) — the complementary gate that must keep making a settled decision immutable once this route produces one.
  ```

  but `check_settled_decisions` compares only against `envelope.predecessor` and skips any row whose predecessor status isn't already `SETTLED`, while the enrolled-roadmap content-validity check step 5 reuses — `check_complete_roadmap_gates` → `_evaluate_full_roadmap_gates` in `roadmap_impact_snapshot.py`, the same evaluator `promote_review_seal`'s `_recheck_stored_candidate` runs on every later candidate promotion — never builds an `ArtifactEnvelope` with a `predecessor` at all, so the gate is unconditionally a no-op on that path. Once step 5 settles a decision on an enrolled roadmap, the next ordinary candidate proposal and promotion can change that same decision's `status`, `chosen_option`, or `anchor` back and nothing refuses it, recreating the "internally contradictory" state the Problem statement names as the harm this plan exists to close — except now behind a receipt that falsely attests permanence. This is a new exposure, not a pre-existing one: an enrolled roadmap has no other live route to a Roadmap-derived `settled` decision (inherited rows arrive pre-settled at carry time), so step 5 is the first mutation path to reach this gap. Step 7's acceptance ("prove... `check_settled_decisions` still refuses drift on a row this route settled") cannot be demonstrated against the real enrolled pipeline this way — it can only be shown by calling the gate directly on a hand-built envelope, which proves nothing about whether a real subsequent promotion is actually blocked.

**Suggested action:** For the enrolled lineage, either add a dedicated drift check to the candidate-promotion validity path that compares a proposed candidate's decisions against the currently accepted version's settled decisions (the same comparison `check_settled_decisions` already makes, given a real predecessor), or state plainly in Risks/Deferred that a settled decision on an enrolled roadmap has no protection against a later candidate promotion until a separate effort adds it — rather than leaving the References/Out-of-scope framing assert a protection this lineage does not have.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index cbef4422..e2972409 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -71,8 +71,9 @@ steps:
 - id: 4
   title: Settle one decision on an un-enrolled roadmap and publish its receipt through
-    publish_stage_artifact's multi-member generation, keeping the existing journal
-    recovery (roll back or drop an in-flight generation) unchanged and updating the
-    selected artifact's bytes and its stage baseline record together — no seed-state
-    or other artifact/stage is rewritten
+    publish_stage_artifact's multi-member generation with invalidate_seeds=False,
+    keeping the existing journal recovery (roll back or drop an in-flight generation)
+    unchanged and updating the selected artifact's bytes and its stage baseline record
+    together — seed state and every other artifact/stage stay byte-identical before
+    and after
   intent: Let an operator settle an approved decision on an ordinary roadmap by naming
     it, naming its evidence, and confirming — with no hand-edit of a canonical artifact.
@@ -93,16 +94,19 @@ steps:
     3: the receipt record published once the artifact write lands
 - id: 5
-  title: Settle one decision on an enrolled roadmap by storing a deterministic,
-    gate-checked version and advancing the accepted head through a new narrow promotion
-    boundary that reuses promote_review_seal's writer-token/journal selector-swap
-    but not its model-authored seal/review preconditions; refuses an in-flight pending
-    generation; enrolled recovery learns the settlement generation while root-enrollment
-    and review-seal-promotion recovery stay exactly as they are, and stored version
-    members are never overwritten or deleted
+  title: Settle one decision on an enrolled roadmap by storing the settled artifact
+    bytes as an ordinary version_kind candidate record — via create_candidate_version,
+    with a new dedicated no-review sentinel in place of INITIAL_EMPTY_REVIEW_LINEAGE_ID
+    and no candidate_evidence_path/replacement_evidence_path entries — then advancing
+    the accepted head through a new additive PendingGeneration.kind recovery branch
+    that reuses promote_review_seal's writer-token/journal selector-swap but never
+    calls _load_complete_sealed_candidate or either evidence loader; refuses an
+    in-flight pending generation; root-enrollment and review-seal-promotion recovery
+    stay exactly as they are, and stored version members are never overwritten or
+    deleted
   intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one
     without ever editing its accepted head in place, without fabricating a synthetic
-    model-authored candidate/review/seal chain to satisfy promote_review_seal's existing
-    preconditions, and without any accepted-head write path outside the guarded selector
-    swap.
+    model-authored candidate/review/seal chain or evidence file to satisfy
+    promote_review_seal's existing preconditions, and without any accepted-head write
+    path outside the guarded selector swap.
   files:
   - plan_tool/roadmap_revision_publish.py
@@ -197,8 +201,14 @@ uses for other single-row, evidence-bound, confirmed state changes
 `source`. `decisions` is a field on all four staged artifacts
 (Domain/Constraints/Components/Plans), not one file. `TEXT_FIELDS_BY_ROW_TYPE`
-in `plan_tool/roadmap_revision.py` is the field-authority allowlist for
-`--revise-feedback`; it names only `("rationale",)` for `decisions`, so
-`status` is structurally excluded — there is no explicit denial to relax,
-only an absent grant to add. `check_settled_decisions`
+in `plan_tool/roadmap_revision.py` is the field-authority allowlist for the
+generic, unconfirmed `--revise-feedback` local-revision path; it names only
+`("rationale",)` for `decisions`, so `status` is structurally excluded from
+it. Settlement does not add `status` to that allowlist or route through
+`preflight_feedback_revision` — doing so would open an unconfirmed,
+evidence-free path to flip a decision's status, the opposite of the
+narrow, evidence-bound action this plan builds. `replace_design_row`
+(`plan_tool/roadmap_artifacts.py`) already refuses any field whose current
+value is an `enum.Enum`, so `status` needs its own dedicated transition
+helper regardless; `check_settled_decisions`
 (`plan_tool/roadmap_gates.py`) already refuses a *settled* decision's id,
 status, chosen option, or anchor from drifting; it does not, and must not
@@ -250,30 +260,58 @@ evidence-bound shape every other narrow roadmap action already has.
   generation (`roadmap_revision_publish.py`) — the same primitive an
   ordinary stage revision uses — so the artifact bytes and the stage
-  baseline record update atomically together. No other artifact, seed-state,
-  or unrelated stage's baseline is touched.
+  baseline record update atomically together. `publish_stage_artifact`
+  defaults to invalidating the roadmap's shared derived-seed state on every
+  call (`invalidate_seeds=None` resolves to `True`); settlement must pass
+  `invalidate_seeds=False` explicitly, since flipping one decision's status
+  is not a design change any derived seed needs reworked against. No other
+  artifact, seed-state, or unrelated stage's baseline is touched.
 - **Enrolled roadmap.** `promote_review_seal` (`roadmap_version_promotion.py`)
   is not a generic accepted-head write: it requires a full model-authored
   `CandidateProposalAdmission` → reviewer answer → `CandidateReviewSeal`
-  chain, and it is the sole existing writer of `accepted_head_path` after
-  root enrollment. Reusing it as-is would mean fabricating a synthetic
-  model-provenance record for a change nothing proposed or reviewed that
-  way. Settlement instead adds one new, narrow, non-model promotion
-  boundary: store the settled artifact bytes as a new immutable version
-  (reusing the existing storage primitives in `roadmap_versions.py`), prove
-  it gate-valid with the existing `check_complete_roadmap_gates` evaluator
-  (`roadmap_impact_snapshot.py` — the same evaluator `promote_review_seal`
-  itself uses), then advance `accepted_head_path` under the existing
-  writer-token lease and `PendingGeneration` journal — the same
-  selector-swap mechanics `promote_review_seal` uses, without its
-  seal/review preconditions. It must never write the accepted head outside
-  that guarded swap. A journal mid-flight (`PendingGeneration`) refuses
-  rather than attempting recovery — that repair belongs to the separate,
-  already-tracked "Incomplete immutable lifecycle journals" bug entry,
-  deferred pending BACKLOG #328 sign-off. The preflight leaf (step 2) reads
-  an enrolled roadmap's current content from
-  `load_accepted_version(...).artifact_bytes` — the same source
-  `roadmap_view.py:load_roadmap()` already uses for enrolled content —
-  never from on-disk stage files or the un-enrolled `ReceiptSafeSelector`
-  read path.
+  chain (via `_load_complete_sealed_candidate`), and it is the sole existing
+  writer of `accepted_head_path` after root enrollment. Reusing it as-is
+  would mean fabricating a synthetic model-provenance record for a change
+  nothing proposed or reviewed that way.
+
+  Settlement stores its settled artifact bytes as an ordinary
+  `version_kind: "candidate"` record via the existing
+  `create_candidate_version` (`roadmap_versions.py`) — the closed
+  `root`/`candidate` vocabulary is not widened, because
+  `_load_complete_sealed_candidate`'s two evidence loaders
+  (`load_stored_candidate_proposal`, `load_stored_candidate_review_replacement`)
+  are reachable only from the model-authored propose→review→promote pipeline
+  itself, never from `load_accepted_version` or any other generic content
+  read — a candidate record with no matchi
````

## 21. `roadmap-decision-settlement|2026-09-18T02:00:16Z|plan-plan-completeness-3eed2095`

**Cited step:** 8: Document the settlement route, retire the hand-edit instruction it replaces, state that --revise-feedback still cannot change status, and remove the BUG_BACKLOG.md entry now that the capability ships

**Finding (plan-completeness, medium):** The plan hands an interrupted settlement journal to the "Incomplete immutable lifecycle journals" `BUG_BACKLOG.md` entry

The plan hands an interrupted settlement journal to the "Incomplete immutable lifecycle journals" `BUG_BACKLOG.md` entry, but that entry does not cover the new shape:
  - It names only the promotion and candidate proposal, review, and replacement generation shapes, and step 8 only removes the settlement entry.
  - On an enrolled roadmap, `recover_roadmap_publication` accepts only a completed version-owned generation (`_is_completed_version_owned_generation`).
  - So a settlement generation interrupted before its selector write blocks every later enrolled writer, just like the listed shapes.
  - Yet that entry's future fix ("define and validate each exact writer-produced promotion and candidate generation shape") has no record that the settlement shapes exist.

**Suggested action:** Add to step 8's acceptance criteria that the "Incomplete immutable lifecycle journals" entry names the decision-settlement generation shape(s), so its deferred fix covers them.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index e2972409..8f8f0d5b 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -142,9 +142,11 @@ steps:
       head
 - id: 7
-  title: Prove both lineages produce the same settled row and that check_settled_decisions
-    still refuses drift on a row this route settled
+  title: Prove both lineages produce the same settled row, that check_settled_decisions
+    refuses drift on an un-enrolled settled row, and document that the same protection
+    does not yet exist on the enrolled lineage (tracked separately in BUG_BACKLOG.md)
   intent: Show the enrolled and un-enrolled paths are one capability rather than two
-    look-alikes, by asserting identical before/after row content across both, instead
-    of settling for parallel 'it runs' coverage.
+    look-alikes, by asserting identical before/after row content across both, and
+    state plainly rather than silently which lineage's settled decisions are actually
+    protected from later drift.
   files:
   - tests/cli/test_roadmap_cmd.py
@@ -361,7 +363,16 @@ evidence-bound shape every other narrow roadmap action already has.
   extend `TEXT_FIELDS_BY_ROW_TYPE` or route through this generic,
   unconfirmed, evidence-free `--revise-feedback` path.
-- `plan_tool/roadmap_gates.py` (`check_settled_decisions`) — the complementary
-  gate that must keep making a settled decision immutable once this route
-  produces one.
+- `plan_tool/roadmap_gates.py` (`check_settled_decisions`) and
+  `plan_tool/roadmap_impact_snapshot.py` (`_evaluate_full_roadmap_gates`) —
+  `check_settled_decisions` genuinely protects a settled decision against
+  later drift on the un-enrolled lineage, where ordinary revision/reconcile
+  paths build a real `predecessor`. `_evaluate_full_roadmap_gates` —
+  the evaluator every enrolled candidate promotion runs through — always
+  builds `predecessor=None`, so `check_settled_decisions` is a permanent
+  no-op there; this is a pre-existing gap (tracked as its own
+  `BUG_BACKLOG.md` entry, "An enrolled roadmap's candidate promotion never
+  re-checks a settled decision against its predecessor"), not one this plan
+  creates or fixes, and step 7 only demonstrates the protection that
+  actually exists.
 - `plan_tool/roadmap_feedback_reopen.py` and
   `plan_tool/roadmap_escalation_selection.py`
@@ -369,11 +380,18 @@ evidence-bound shape every other narrow roadmap action already has.
   `FeedbackSelector`) — the structural precedent this route's selector,
   predecessor-digest staleness check, and named-reason refusal shape should
-  follow; both are wired only for an un-enrolled roadmap today via
-  `require_unenrolled_roadmap_writer` (`plan_tool/roadmap_revision_publish.py`),
-  confirming the enrolled side has no narrow-route precedent to reuse as-is.
-  Neither touches `.roadmap-baselines`, because feedback is the one thing
-  `canonical_projection` excludes from the digest; a decision's `status` is
-  not excluded, so the un-enrolled write must instead follow
-  `plan_tool/roadmap_revision_publish.py:publish_stage_artifact`'s
+  follow. `roadmap_feedback_reopen.py`'s canonical-artifact write is wired
+  only for an un-enrolled roadmap via `require_unenrolled_roadmap_writer`
+  (`plan_tool/roadmap_revision_publish.py`), confirming the enrolled side
+  has no canonical-artifact-mutation precedent to reuse as-is — this is
+  what step 5 must build fresh. `roadmap_escalation_selection.py` and its
+  runner `roadmap_escalation_run.py`, by contrast, call no writer guard and
+  check no enrollment state at all: escalation-receipt creation already
+  works unchanged on an enrolled roadmap because it writes only into the
+  immutable evidence store, never a canonical artifact — an already-working
+  enrolled-and-un-enrolled precedent for step 3's evidence-namespace
+  receipt write. Neither touches `.roadmap-baselines`, because feedback is
+  the one thing `canonical_projection` excludes from the digest; a
+  decision's `status` is not excluded, so the un-enrolled write must
+  instead follow `plan_tool/roadmap_revision_publish.py:publish_stage_artifact`'s
   multi-member generation, which updates the artifact and its baseline
   record together.
@@ -462,4 +480,11 @@ See the `steps:` block in the frontmatter.
   mistake must get the same refusal `preflight_feedback_revision` already
   gives other inherited-row edits, not a new, differently-worded one.
+- **Overclaimed enrolled protection:** `_evaluate_full_roadmap_gates` (the
+  evaluator every enrolled candidate promotion runs through) always builds
+  `predecessor=None`, so `check_settled_decisions` is a permanent no-op on
+  the enrolled lineage — a pre-existing gap this plan is the first to make
+  reachable, tracked as its own `BUG_BACKLOG.md` entry. This plan must not
+  claim or test a drift protection on the enrolled lineage that does not
+  exist; state the gap plainly instead.
 
 ## Testing
@@ -489,6 +514,9 @@ the settlement receipt records the artifact key, decision id, predecessor
 digest, and cited feedback id/digest, and that a legacy roadmap with no
 receipts directory still parses and settles correctly. Confirm
-`check_settled_decisions` still refuses drift on the row this route just
-settled.
+`check_settled_decisions` refuses drift on an un-enrolled row this route
+just settled. Do not test or claim the same protection on the enrolled
+lineage: `_evaluate_full_roadmap_gates` always builds `predecessor=None`,
+so `check_settled_decisions` is a documented no-op on every enrolled
+candidate promotion today (tracked separately in `BUG_BACKLOG.md`).
 
 ## Acceptance criteria
@@ -509,4 +537,8 @@ settled.
   enrolled write never constructs a synthetic model-authored
   candidate/review/seal chain.
+- `check_settled_decisions` is demonstrated to refuse drift on an
+  un-enrolled settled row. The plan documents, rather than silently
+  overclaims, that the enrolled lineage has no equivalent protection today
+  (a pre-existing gap tracked in `BUG_BACKLOG.md`, not fixed by this plan).
 - A durable receipt exists after every successful settlement and can be read
   back to prove which evidence justified it.
@@ -520,4 +552,10 @@ settled.
 A symmetric "un-settle" / reopen route for a `settled` decision, BACKLOG
 #242's feedback-closing work, and any repair path for a malformed immutable
-lifecycle journal all remain separate efforts. File any newly discovered gap
-in `BACKLOG.md` or `BUG_BACKLOG.md` rather than expanding this plan.
+lifecycle journal all remain separate efforts. Also deferred: giving
+`_evaluate_full_roadmap_gates` a real predecessor so `check_settled_decisions`
+actually protects a settled decision against a later enrolled candidate
+promotion — a pre-existing gap this plan is the first to make reachable,
+filed as its own `BUG_BACKLOG.md` entry rather than bundled into this
+feature, since it changes the shared evaluator every candidate promotion
+runs through. File any newly discovered gap in `BACKLOG.md` or
+`BUG_BACKLOG.md` rather than expanding this plan.

````

## 22. `security-check-command|2026-06-16T18:45:54Z|plan-plan-completeness-9d5b6a30`

**Cited step:** 5: Wire security dimension into completeness: conceptual-layer call + route security_recs through the existing findings-summarization/rollup gate before rendering + grouped-report section + JSON security bucket (the completeness --iterate loop firing of run_auto_reconcile_on_drift with mode="security" that operationalizes the step 4 drift-retrigger hook is deferred to a dedicated follow-up step, not wired here)

**Finding (plan-completeness, medium):** Step 5 claims the completeness security dimension reuses the saved `<ts>-security-plan.json` report on the **plan** fing

Step 5 claims the completeness security dimension reuses the saved `<ts>-security-plan.json` report on the **plan** fingerprint alone, treating code drift as advisory — but step 2's `resolve_reusable_security` is a clone of `completeness_report.py:resolve_reusable_audit`, which returns a composite `fresh` verdict that folds code staleness (`drifted_code`, gated on `code_fingerprint_present`). The plan never says step 5 must consult the plan-axis match alone; if it reads the composite `fresh`, a code-only commit re-spends the Claude pass, silently defeating the second cost layer the HIGH *Cost/latency in completeness* risk depends on.

**Suggested action:** state that the completeness dimension keys reuse on the plan-fingerprint match only and ignores the resolver's code-staleness verdict.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index 0129b00a..13cbe922 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -20,8 +20,12 @@ steps:
   status: current
 - id: 2
-  title: Add resolve_reusable_security + fingerprinted <ts>-security.json persistence
-    (sibling of resolve_reusable_audit); scope reuse by target/source (plan vs code)
-    as well as kind+fingerprint so a plan-axis caller never reuses a code-axis report
-    or vice versa (per-target scoping lands here, not deferred)
+  title: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json persistence
+    (sibling of resolve_reusable_audit); scope reuse by target (plan vs code) via the
+    filename suffix as well as fingerprint so a plan-axis caller never reuses a code-axis
+    report or vice versa (per-target scoping lands here, not deferred); a target="plan"
+    save verdicts fresh on an unchanged plan fingerprint alone — do NOT gate plan-target
+    freshness on saved.code_fingerprint_present (that code-fingerprint staleness gate from
+    resolve_reusable_audit applies only to the code/reconcile targets), so step 5's
+    plan-fingerprint reuse engages instead of verdicting stale every run
   files:
   - plan_tool/security_audit.py
@@ -79,6 +83,7 @@ steps:
   detail: docs/implementation-plans/plan-details/security-check-command/04-security-reconcile-reconcilekind-run.md
 - id: 5
-  title: 'Wire security dimension into completeness: conceptual-layer call + grouped-report
-    section + JSON security bucket (the completeness --iterate loop firing of
+  title: 'Wire security dimension into completeness: conceptual-layer call + route
+    security_recs through the existing findings-summarization/rollup gate before
+    rendering + grouped-report section + JSON security bucket (the completeness --iterate loop firing of
     run_auto_reconcile_on_drift with mode="security" that operationalizes the step 4
     drift-retrigger hook is deferred to a dedicated follow-up step, not wired here)'
@@ -148,5 +153,6 @@ steps:
 - id: 9
   title: 'Deliver security auto-apply end-to-end: emit a [category-slug] from prompts/security-plan.md
-    and prompts/security.md, populate rec.anchor in _security_recommendations, seed
+    only (the per-step prompts/security.md is left unchanged so the --mode security per-step
+    path is preserved), populate rec.anchor in _security_recommendations, seed
     SECURITY_AUTO_APPLY_ALLOWLIST with hardcoded-secret, and wire security_finding_is_auto_applicable
     into the --iterate convergence apply loop; update RUNBOOK.md to document the now-active
@@ -155,5 +161,4 @@ steps:
   files:
   - plan_tool/prompts/security-plan.md
-  - plan_tool/prompts/security.md
   - plan_tool/security_audit.py
   - plan_tool/convergence.py
@@ -183,15 +188,22 @@ Security is **already a per-step review mode**, but only at the per-step level:
 A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean completeness hook; downstream steps assume this unless the detail step pushes back to the user.
 
-A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security.json` with a plan+code fingerprint, following the `resolve_reusable_audit`/`resolve_reusable_reconcile` reuse pattern. Because `target="plan"` and `target="code"` audits share the `kind="security"` bucket distinguished only by `source`, reuse resolution must scope by target/source as well as kind+fingerprint — a newest-by-kind lookup would serve a `target="code"` save to a plan-axis caller (completeness, step 5) or a plan save to `--target code` (step 3). A plan-audit reuse must never serve a code-audit report or vice versa.
+A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit`/`resolve_reusable_reconcile` reuse pattern. Because `target="plan"` and `target="code"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a plan-axis caller (completeness, step 5) can never resolve a `target="code"` save, nor `--target code` (step 3) a plan save — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa.
 
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by extending the `ReconcileKind` descriptor family (`cli/reconcile.py`) with a `security-reconcile` kind that audits plan-stated security intent against the code's actual security posture and emits drift findings, reusing `resolve_reusable_reconcile` fingerprinting and the `run_auto_reconcile_on_drift` hook so a code change since the last security audit re-triggers it. The standalone `plan-tool security --reconcile <name>` does **not** depend on in-run file drift: it derives its drift scope from the full plan⇄code surface — treating every plan step (and the files each step declares) as in scope — so it runs the intent-vs-posture comparison across the whole plan even on a tree with no recorded file drift. Step 5's completeness security dimension re-triggers by **fingerprint-gated reuse**, not the hook: on an unchanged plan+code fingerprint it reuses the saved `<ts>-security.json` report and skips the Claude pass, re-sampling only on a fingerprint miss — distinct from the standalone command's full-surface sweep. Wiring `run_auto_reconcile_on_drift`'s file-drift-gated path (caller-supplied `drifted`/`file_to_step`, auditing only steps that own drifted files) into the completeness/iteration loop is deferred to a follow-up step, not done in step 5. This requires a **dedicated drift prompt** that compares the plan's stated security intent against the code's actual posture (e.g. detecting a plan that *states* an authz step the code lacks); reusing the per-step `prompts/security.md` code audit via `mode="security"` does **not** satisfy these drift semantics — it only re-runs a co
````

## 23. `arm-clustering-cross-round-consensus|2026-08-12T21:33:43Z|plan-plan-correctness-8f0a679a`

**Cited step:** 1: Build arm-clustering consensus targets from saved audit history

**Finding (plan-correctness, high):** Step 1's Implementation §3 point 2 ("Cross-round match") says to require "a `_matches` hit against every *other* pass in

Step 1's Implementation §3 point 2 ("Cross-round match") says to require "a `_matches` hit against every *other* pass in the window," and point 4 ("Target agreement") says to collect `audit_step_target` "from the newest finding and every matched representative in the other window passes." Neither says what to do when more than one finding in a single earlier pass matches the newest finding via `_matches`. This is a real case, not a corner case: the plan's own Risks section says `_matches` tier 1 matches purely on a shared leading `step<N>` anchor with no other check, and one completeness round routinely emits several findings anchored to the same step. Two reasonable readings diverge materially — (a) pool every match across every pass and require the pooled non-None target values to reduce to one value, the natural extension of the boolean `any(_matches(...))` pattern `_edit_drift_eligible`/`_build_prior_apply_set` already use; or (b) expect exactly one match per pass and, with no rule for the multi-match case, arbitrarily pick one candidate — silently attaching a possibly-wrong `audit_step_target` to the newest finding. Reading (b) reproduces, through a different door, exactly the "fabricating the two-round evidence this plan exists to require" failure the plan's Risks section already treats as serious for the single-candidate case.

**Suggested action:** state explicitly in step 1 that a newest-pass finding's target is resolved from the union of every finding in every window pass that `_matches` it — never a single "representative" per pass — and that finding is consensus-eligible only when that union's non-None target values reduce to exactly one value, using the same drop rule multi-round disagreement already gets; apply this wherever step 1's prose otherwise implies one match per pass (Implementation §3 points 2 and 4, and the Testing roster, which currently only exercises a one-finding-per-pass scenario).

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
index f245ca0c..7a8e5205 100644
--- a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
+++ b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
@@ -17,7 +17,7 @@ steps:
     `Recommendation`/`RunFinding` (today it is parsed by `_split_audit_step_evidence`
     and then discarded into a transient in-call structure before a review is saved),
-    then let a material finding earn a consensus step target from that persisted
-    value across separate audit rounds, so arm-clustering has evidence to work with
-    on the --audit-passes 1 runs that give it only one same-execution sample.
+    then let a material finding earn a consensus step target from that persisted value
+    across separate audit rounds, so arm-clustering has evidence to work with on the
+    --audit-passes 1 runs that give it only one same-execution sample.
   files:
   - plan_tool/review.py
@@ -29,4 +29,5 @@ steps:
   complexity: high
   change_type: feature
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/01-build-arm-clustering-consensus-targets.md
   status: current
 - id: 2
@@ -51,9 +52,14 @@ steps:
     1: the classifier function and its advisory record, which diagnose_convergence
       calls and the render lines read fields off
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/02-cross-round-arm-clustering-advisory.md
 - id: 3
   title: Parse the plan once in cmd_convergence instead of inside _current_audit_stage
   intent: Make the parsed plan reachable from cmd_convergence so the next step can
     read its committed steps without parsing the file a second time or copying the
-    best-effort try/except.
+    best-effort try/except. The hoisted `parse_plan` call must keep degrading to `diagnose_convergence`'s
+    pre-stage-bar blanket-blocking defaults on a parse failure or missing plan — the
+    same outcome `_current_audit_stage`'s existing try/except gives today — so `cmd_convergence`'s
+    documented "always exits 0, never surfaces an error" contract survives the move
+    unchanged.
   files:
   - plan_tool/cli/convergence_cmd.py
@@ -61,13 +67,15 @@ steps:
   complexity: low
   change_type: refactor
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/03-parse-plan-once-cmd-convergence-instead.md
 - id: 4
   title: Pass committed step ids to the diagnosis from the convergence and completeness
     surfaces
   intent: Turn the classifier on for real operators by threading real committed step
-    ids *and* each step's current status (step 1's function signature accepts both as
-    parameters — a bare id list alone carries no status, and step 1's done-step drop
-    check needs it — but this step is what supplies real values from the plan's parsed
-    `Step` objects, not step 1) into it from the two places the sibling advisories
-    already print, so `plan-tool convergence` and completeness stderr both surface it.
+    ids *and* each step's current status (step 1's function signature accepts both
+    as parameters — a bare id list alone carries no status, and step 1's done-step
+    drop check needs it — but this step is what supplies real values from the plan's
+    parsed `Step` objects, not step 1) into it from the two places the sibling advisories
+    already print, so `plan-tool convergence` and completeness stderr both surface
+    it.
   files:
   - plan_tool/cli/convergence_cmd.py
@@ -85,4 +93,5 @@ steps:
     3: the parsed plan hoisted into cmd_convergence, so committed step ids come from
       the parse the stage lookup already did
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/04-pass-committed-step-ids-diagnosis.md
 - id: 5
   title: Update the docs for the cross-round advisory and settle the backlog entries
@@ -92,8 +101,8 @@ steps:
     CLAUDE.md''s "cycle-free leaf" bullet and `docs/ARCHITECTURE.md`''s "Convergence
     diagnostic" entry both restate that import set already inaccurately (CLAUDE.md
-    omits `granularity`; both predate this plan and are wrong independent of it), so
-    correct both to the module''s full current set (`review_persistence`, `review`,
-    `locator`, `convergence`, `granularity`) plus the new `audit_shapes` edge step 2
-    adds — not only append the one new edge onto an already-wrong baseline. The
+    omits `granularity`; both predate this plan and are wrong independent of it),
+    so correct both to the module''s full current set (`review_persistence`, `review`,
+    `locator`, `convergence`, `granularity`) plus the new `audit_shapes` edge step
+    2 adds — not only append the one new edge onto an already-wrong baseline. The
     module''s own docstring paragraph is step 2''s fix, made where the import lands,
     not this step''s.'
@@ -110,4 +119,5 @@ steps:
     4: the shipped surfaces and the final import edge, so the docs describe what landed
       rather than what was proposed
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/05-update-docs-cross-round-advisory-settle.md
 ---
 # Arm Clustering Cross Round Consensus
@@ -165,16 +175,33 @@ settled precedent, not a gap to redesign.
    Every cross-round consumer this plan builds reads `RunFinding`, not
    `Recommendation`, so missing the second site leaves the field permanently
-   `None` on everything this plan actually consumes. Document both fields in
-   `DATA_CONTRACT.md`. This is the one new piece of persisted state this plan
-   adds; `evaluate_arm_clustering` and the same-execution consensus path are
+   `None` on everything this plan actually consumes. The two fields get two
+   different kinds of documentation, landed in **this same step**, not
+   deferred to step 5's docs pass: `Recommendation.audit_step_target` is
+   persisted/serialized (round-trips via `save_review`), so it gets a row in
+   `DATA_CONTRACT.md`'s existing `Recommendation` table, same as `anchor` or
+   `impact`. `RunFinding` is not persisted on its own — its own docstring
+   calls it a flattening "from a saved report's recommendation list," and
+   `DATA_CONTRACT.md` documents only persisted/serialized schemas, which is
+   why none of `convergence_diagnosis.py`'s other dataclasses have an entry
+   there — so `RunFinding.audit_step_target` is documented inline in
+   `RunFinding`'s own docstring instead, matching how `step_id`, `anchor`, and
+   `impact` are already documented there, not as a new `DATA_CONTRACT.md`
+   section. This is the one new piece of persisted state this plan adds;
+   `evaluate_arm_clustering` and the same-execution consensus path are
    unaffected — they keep reading `observations_by_id` and the transient tag
    directly.
 2. Materiality: treat a matched finding as material via
    `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=…)`
-   checked **only against the newest round's copy** of that finding — the
-   same rule `classify_edit_drift`'s `_edit_drift_eligible` already applies to
-   `RunFinding` objects pulled from history (`convergence_diagnosis.py:885`),
-   and the same newest-round keying point 7 already uses for the output
-   mapping. A finding's severity/impact tag can differ across matched rounds;
+   checked **only against the newest round's copy** of that finding —
+   reusing only the stage-bar half of `classify_edit_drift`'s
+   `_edit_drift_eligible` (`convergence_diagnosis.py:885`), and the same
+   newest-round keying point 7 already uses for the output mapping.
+   `_edit_drift_eligible` also runs a second check —
+   `_is_resolved_in_run(annotations.get(finding.id))`, dropping a finding the
+   operator already declined between rounds — that this plan deliberately
+   does **not** reuse: Out of scope already refuses to gate cross-round
+
````

## 24. `security-check-command|2026-06-20T21:11:54Z|plan-plan-completeness-1e1f63ef`

**Cited step:** 9: Deliver security auto-apply end-to-end: emit a [category-slug] from prompts/security-plan.md only (the per-step prompts/security.md is left unchanged so the --mode security per-step path is preserved), populate a per-finding-unique rec.anchor (the category slug composed with a per-body discriminator so same-category findings keep distinct ids) in _security_recommendations and key auto-apply on the bare category component, not the full id-bearing anchor, seed SECURITY_AUTO_APPLY_ALLOWLIST with hardcoded-secret so the step-8 `security --iterate` apply loop (NOT the completeness loop) — which filters via apply_eligible_security_findings → security_finding_is_auto_applicable and calls apply_finding directly, never should_apply_as_finding — applies for real; the security_finding_is_auto_applicable OR-branch (beside the existing review_walk source pre-filter) is scoped to that --iterate loop only and is NOT additionally wired into the interactive review/reconcile walk — step 4 registers no security kind in _RECONCILE_KINDS (security-plan/security-code/security-reconcile are all absent), so no walk loads a security-plan sidecar and the only allowlisted category (hardcoded-secret, plan-target only) is unreachable from that walk; update RUNBOOK.md to document the now-active allowlist and apply-loop wiring (auto-apply is no longer advisory-only) since step 10 documents only the inert step-7 primitive

**Finding (plan-completeness, medium):** `--target code` findings keep `rec.anchor=None` (step 9), and step 8's `--iterate` loop is rejected only for `--reconcil

`--target code` findings keep `rec.anchor=None` (step 9), and step 8's `--iterate` loop is rejected only for `--reconcile`, never for `--target code` — so `plan-tool security --target code <name> --step <id> --iterate` is a permitted combination that routes anchor-`None` findings through `apply_eligible_security_findings → security_finding_is_auto_applicable → security_auto_apply_category`. The plan says code findings "stay advisory" but never names how the category extractor behaves on a `None` anchor; if `security_auto_apply_category` splits/parses the anchor unconditionally it raises rather than returning a non-allowlisted category.

**Suggested action:** name the `anchor=None` (code-target) case and require `security_auto_apply_category`/`security_finding_is_auto_applicable` to treat it as not-applicable rather than leaving the eligibility predicate undefined for it.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index f1c5187f..32c7f146 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -47,5 +47,10 @@ steps:
     --fail-on-findings) across all five registration seams; reuse-prompt wiring of
     resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
-    --target code requires --step (single-step audit)'
+    --target code requires --step (single-step audit), and --step is rejected at
+    parse time when combined with --reconcile (usage error, non-zero rc — the reconcile
+    direction is whole-plan full-surface, so a single --step is meaningless against it);
+    cmd_security renders
+    result.skipped_steps alongside the findings so a partial reconcile sweep (step 4)
+    is reported as partial, not as a clean pass'
   files:
   - plan_tool/cli/app.py
@@ -75,5 +80,9 @@ steps:
     persistence suppressed so write_security_report is the sole on-disk writer) back
     into a SecurityAuditResult so step 3's cmd_security can render result.findings
-    and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(...,
+    and persist via write_security_report; because the generalized hook's best-effort loop
+    skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel
+    to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit)
+    and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default —
+    so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(...,
     target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
     the reconcile family uses resolve_saved_review in review_persistence
@@ -255,5 +264,5 @@ Security is **already a per-step review mode**, but only at the per-step level:
 ## Architecture
 
-A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`.
+A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`. **`--step` is rejected at parse time when combined with `--reconcile`** (a usage error, non-zero rc, never dispatching): the reconcile direction derives its scope from the full plan⇄code surface (every step and its declared files), so a single `--step` is meaningless against it — `plan-tool security --reconcile --step <id> <name>` is an error, not a one-step reconcile, keeping the whole-plan full-surface contract unambiguous. `--step` remains required for `--target code` (single-step audit) and unused for `--target plan`.
 
 A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit` reuse pattern. Because `target="plan"`, `target="code"`, and `target="reconcile"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json` vs `-security-reconcile.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a `--target code` caller can never resolve a `target="plan"` save, nor vice versa — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa. Beyond the target suffix, the **`target="code"` axis must additionally scope its lookup by `step_id`**: the `-security-code.json` suffix encodes only the target, not the step, so two steps' code audits write same-suffix sidecars — `resolve_reusable_security` for the code target must therefore key on `step_id` (mirroring the reconcile family's per-step `_find_saved_for_step`), not return the newest target-suffix sidecar (the whole-plan `resolve_reusable_audit` shape it is otherwise cloned from), or it would serve one step's saved code audit to a different step's caller. **`resolve_reusable_security` ships dormant in this plan:** step 2 builds it and step 3 writes the `<ts>-security-<target>.json` sidecar, but **no in-plan step reads the resolver** — the reuse-prompt wiring that would short-circuit a Claude call on an unchanged fingerprint is deferred to a follow-up for all three targets (see `## Deferred`). The persistence/lookup machinery lands write-ready so the follow-up only adds the consumer; this plan does not claim a reuse short-circuit it does not deliver.
@@ -261,5 +270,5 @@ A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by generalizing the `run_auto_reconcile_on_drift` hook (`auto_reconcile.py`) to audit plan-stated security intent against the code's actual security posture under a `mode="security-reconcile"` prompt and emit drift findings, so a code change since the last security audit re-triggers it. **No `security-reconcile` row is added to `cli/reconcile.py:_RECONCILE_KINDS`** — it would be dead config: the existing `detail-reconcile` / `run-reconcile` `name_includes` suffixes are substring-disjoint from `-security-reconcile`, so they already cannot mis-grab a security sidecar, and no production caller queries `resolve_reusable_reconc
````

## 25. `roadmap-revision-retention|2026-08-19T14:56:49Z|plan-plan-completeness-1c775e6f`

**Cited step:** 6: Rename `--mode review` to `--mode history` everywhere it appears — the argparse choices, MODE_REVIEW's branch sites and docstrings in roadmap_view.py (including its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text, plan_tool/cli/__init__.py's package-level `--help` catalog docstring (and the golden snapshot pinning it), and every literal `--mode review` example in README.md, docs/ROADMAP_WALKTHROUGH.md, and docs/ARCHITECTURE.md — dropping the `review` spelling with no alias

**Finding (plan-completeness, high):** Step 6's site list for renaming `--mode review` to `--mode history` — argparse choices, `roadmap_view.py`'s `MODE_REVIEW

Step 6's site list for renaming `--mode review` to `--mode history` — argparse choices, `roadmap_view.py`'s `MODE_REVIEW` branches and docstrings, `cli/roadmap_cmd.py`'s help text, `plan_tool/cli/__init__.py`'s catalog docstring plus its golden snapshot, and every literal `--mode review` example in README.md, `docs/ROADMAP_WALKTHROUGH.md`, and `docs/ARCHITECTURE.md` — leaves out `docs/cli/roadmap.md`. That file is generated from the live argparse parser (CLAUDE.md's own Reference docs entry: "regenerate with `python -m plan_tool.cli_reference --write`") and currently documents `--mode {current,review}` at three spots (its usage line, its `--view` row, and its own `--mode` row). It is drift-guarded by `tests/cli/test_cli_reference.py`'s `TestCliReferenceDrift.test_every_generated_file_matches_disk`, which fails whenever the parser's rendered output disagrees with the committed `docs/cli/` files. Once step 6 changes `choices=[MODE_CURRENT, MODE_REVIEW]` and its help text, this existing test goes red against the unregenerated file.

**Suggested action:** add `docs/cli/roadmap.md` and the `python -m plan_tool.cli_reference --write` regeneration step to step 6's site list, so the rename lands with the generated CLI reference in sync and the existing drift-guard test stays green.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-revision-retention.md b/docs/implementation-plans/2-roadmap-revision-retention.md
index d7b2a424..c5cd7bdc 100644
--- a/docs/implementation-plans/2-roadmap-revision-retention.md
+++ b/docs/implementation-plans/2-roadmap-revision-retention.md
@@ -15,9 +15,12 @@ steps:
     tampering-specific branch so an edited (not fabricated) carried removal is
     rejected with a message naming the changed field and telling the model to
-    revert it, not drop the record
+    revert it, not drop the record, and add a dropped-removal check mirroring
+    `check_feedback_integrity`'s dropped-feedback loop so a carried removal
+    silently omitted from a reply is rejected too, not just an edited one
   intent: So a reader of a revised roadmap can see what the dropped row actually said
     instead of having to go read git, with no faithfulness question to gate because
-    the render layer derives the snapshot rather than the model paraphrasing it, and
-    so an accidental edit to a carried removal gets a correction the model can act on.
+    the render layer derives the snapshot rather than the model paraphrasing it, an
+    accidental edit to a carried removal gets a correction the model can act on, and
+    a carried removal cannot simply vanish from a reply either.
   files:
   - plan_tool/roadmap_artifacts.py
@@ -74,14 +77,14 @@ steps:
   change_type: feature
 - id: 4
-  title: Add a gate rejecting a revision whose `feedback` collection places a `closed`
-    row before a non-`closed` row, and tell the model in the revision prompt to keep
-    closed rows last when it re-emits the collection
+  title: Add a deterministic, stable closed-last sort to the `feedback` render layer,
+    so any write — model-emitted or a reviewer's own hand-edit later picked up by
+    any tool-driven write — always leaves closed rows after every non-`closed`
+    row, with no gate and no model-facing prompt guidance needed
   intent: So the live part of the review queue reads first and retained closed rows
-    accumulate at the end instead of interleaving with open requests, and the model
-    has the guidance it needs to satisfy the gate on the first attempt.
+    accumulate at the end instead of interleaving with open requests, guaranteed
+    unconditionally rather than only when the model happens to emit rows in order.
   files:
-  - plan_tool/roadmap_gates.py
-  - plan_tool/prompts/roadmap-revision.md
-  - tests/test_roadmap_gates.py
+  - plan_tool/roadmap_artifacts.py
+  - tests/test_roadmap_artifacts.py
   - tests/test_roadmap.py
   complexity: medium
@@ -93,13 +96,17 @@ steps:
       nothing to order last until closed rows can exist.
 - id: 5
-  title: 'Count closed rows in both roadmap summary renderers — `_feedback_summary_lines`
-    (cli/roadmap_cmd.py, the run/revision post-run summary) and `_summary_feedback_counts`
-    / `render_roadmap_summary` (roadmap_view.py, the `--view summary` surface step
-    6 renames to `--mode history`) — and tell the operator to close by setting
-    `state: closed` rather than by deleting'
+  title: 'Count closed rows in the `--mode history` summary (`_summary_feedback_counts`
+    / `render_roadmap_summary`, roadmap_view.py) and update the post-run summary''s
+    close guidance (`_feedback_summary_lines`, cli/roadmap_cmd.py) to say closing
+    sets `state: closed` rather than deleting — the post-run summary reports no
+    per-state counts today (`RoadmapResult` has no closed accumulator, only the
+    scalar `feedback_awaiting_review`) and adding one would touch the `run_roadmap`
+    orchestrator, out of scope per BACKLOG #242, so it keeps reporting only that
+    existing scalar'
   intent: So the two hand-written state lists an operator actually reads stop disagreeing
-    with the state vocabulary the parser accepts, on both the post-run summary and
-    the renamed `--mode history` view whose whole rationale is surfacing retained
-    history.
+    with the state vocabulary the parser accepts — fully on the renamed `--mode
+    history` view, whose whole rationale is surfacing retained history, and on the
+    post-run summary's guidance text without touching the orchestrator to add a
+    count it doesn't have today.
   files:
   - plan_tool/roadmap_view.py
@@ -125,5 +132,10 @@ steps:
     retain history rather than only pending review work, and no operator-facing
     text anywhere — including the top-level `plan-tool --help` catalog — still
-    tells someone to pass a value the parser now rejects.
+    tells someone to pass a value the parser now rejects. This sweep is scoped to
+    the roadmap `--view ... --mode {current,review}` flag only — `run --mode
+    <review>` / `verify-all --mode <m>`'s unrelated per-step audit primitive
+    (check/optimize/document/test/security/lint) shares no code and stays
+    untouched even where it appears near this flag's own documentation in the
+    same files.
   files:
   - plan_tool/roadmap_view.py
@@ -144,20 +156,30 @@ steps:
 - id: 7
   title: Document the removal snapshot, the decision reference, and the `closed` state
-    (including the closed-last ordering rule) in ROADMAP_FORMAT.md — correcting all
-    three existing "no `closed` member" sites (the schema block's `state` comment,
-    the Closed vocabularies table, and the feedback-lifecycle's situation 5) rather
-    than adding fresh prose beside them — correct RUNBOOK.md's close-request table
-    row and "Preserved by the gates" tables to match, and add a feedback-state
-    vocabulary-completeness test to tests/test_roadmap_format.py mirroring
+    (including the closed-last ordering rule) in ROADMAP_FORMAT.md, describing
+    both setting `state` to `closed` and the still-valid plain-deletion path
+    rather than replacing one with the other — correcting all five sites that
+    currently say deletion is the only close (the schema block's `state`
+    comment, the Closed vocabularies table, the feedback-lifecycle's situation
+    5, the worked example near "## Decisions", and
+    `check_feedback_integrity`'s gate-documentation table row,
+    which also needs "or `closed`" added to its "carried in `awaiting-review` or
+    `deferred`" language) — correct RUNBOOK.md's close-request table row the same
+    dual-option way, plus its "Preserved by the gates" table, and correct README.md's
+    and docs/ROADMAP_WALKTHROUGH.md's close-by-deleting prose to name both options
+    too — and add a feedback-state vocabulary-completeness test to
+    tests/test_roadmap_format.py mirroring
     `test_hosting_schema_documents_the_complete_gate_owned_vocabulary` /
     `test_store_schema_documents_the_complete_gate_owned_vocabulary`, since no such
     guard exists today for FeedbackState
   intent: So the review collections' schema is readable without opening the parser,
-    which is what the whole FORMAT-doc family exists to guarantee, and so a reviewer
-    who trusts RUNBOOK.md's walkthrough learns the retention path exists instead of
-    being told deletion is still the only way to close a request.
+    which is what the whole FORMAT-doc family exists to guarantee, so a reviewer
+    who trusts RUNBOOK.md, README.md, or the walkthrough learns the retention path
+    exists without losing the still-valid deletion option, and so the two most-read
+    operator docs stop contradicting the shipped `closed` state.
   files:
   - ROADMAP_FORMAT.md
   - RUNBOOK.md
+  - README.md
+  - docs/ROADMAP_WALKTHROUGH.md
   - tests/test_roadmap_format.py
   complexity: high
@@ -288,4 +310,21 @@ the near-match message telling the model to revert the edited field, not
 drop the record.
 
+**A carried removal record must survive a revision the same way a carried
+feedback row must — today nothing enforces that.**
+`check_design_row_continuity` only validates removals *present* in the
+candidate against `carried`; it never loops over `predecessor.removals` the
+way `check_feedback_integrity` 
````

## 26. `roadmap-decision-settlement|2026-09-18T04:18:42Z|plan-plan-correctness-794efec0`

**Cited step:** 1: Add a settle-one-decision helper to plan_tool/roadmap_artifacts.py and correct DecisionStatus's hand-edit docstring; replace_design_row keeps refusing enum fields and no existing write path is narrowed or retired

**Finding (plan-correctness, medium):** Both the accepted-head write boundary and its call-graph test are limited to "this plan's own new modules", and the ARCH

Both the accepted-head write boundary and its call-graph test are limited to "this plan's own new modules", and the ARCHITECTURE criterion counts "the four new settlement modules". No section names those modules. Some of the plan's work has to land in existing modules: the new `"decision-settlement"` recovery branch in `roadmap_revision_publish.py:_is_completed_version_owned_generation`, the receipt namespace in `roadmap_evidence_store.py`, and step 1's helper in `roadmap_artifacts.py`. Whether the test covers any of them is undecided. An implementer can pass the test just by putting the selector-swap builder in an existing module. Affected sites: the Architecture "Enrolled roadmap" bullet ("Within **this plan's own new modules**"), the Testing structural-guarantee paragraph, and two acceptance criteria:
  ```
  The accepted-head-write boundary is proven structurally, scoped explicitly to this plan's own new modules, not as a claim about every writer in the repository.
  ```
  ```
  and describes the four new settlement modules.
  ```

**Suggested action:** Name the settlement modules once. Say which are new, and which additions to existing modules, such as the recovery branch and generation builder, fall inside the write-boundary test. Reuse that list in Testing, the acceptance criteria, and step 7's ARCHITECTURE update.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index 80ac1b1b..4a7cb059 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -37,10 +37,11 @@ steps:
     named refusal per rejection class
   intent: Prove, before any write, that exactly one live Roadmap-derived pending decision
-    was named, that a named live feedback row actually targets it (not just resolves)
-    and carries non-empty reviewer-authored `request` text in any FeedbackState (never
-    model-authored `proposed_response`), that an un-enrolled source is admitted against
-    its recorded baseline, and that the source bytes (on-disk artifact for an un-enrolled
-    roadmap, accepted-version bytes for an enrolled one) have not moved since the
-    evidence was read.
+    was named with no duplicate id in the artifact, that a named live feedback row
+    (no duplicate id either) actually targets it (not just resolves) and carries
+    non-empty reviewer-authored `request` text in any FeedbackState (never
+    model-authored `proposed_response`), that an un-enrolled source is admitted
+    against its recorded baseline and is render-canonical, and that the source bytes
+    (on-disk artifact for an un-enrolled roadmap) and, on an enrolled roadmap, the
+    accepted head's own identity have not moved since the evidence was read.
   creates:
   - plan_tool/roadmap_decision_settlement.py
@@ -54,14 +55,21 @@ steps:
       contract its staleness recheck re-verifies
 - id: 3
-  title: Add the immutable settlement receipt record and its own evidence namespace
-    in plan_tool/roadmap_evidence_store.py, naming the exact resulting content digest
-    settlement is about to produce; publication stays create-once and keyed on its
-    own inputs so a retry resolves to the same already-published final, an existing
-    final is returned rather than overwritten, and nothing is deleted
-  intent: Make every successful settlement leave a durable, readable record — written
-    before the row-level write it proves, never after — of which artifact, decision,
-    predecessor digest, feedback evidence, and resulting content digest justify it,
-    so the approval can be proven after the fact and a receipt never outlives or
-    outraces the settlement it names.
+  title: Add the immutable settlement receipt record, its own evidence namespace in
+    plan_tool/roadmap_evidence_store.py, and a read-back check that takes a receipt
+    plus the roadmap's current state and reports whether it still proves a completed
+    settlement (accepted-version-or-predecessor membership on the enrolled lineage;
+    exact current-digest match, including a deleted evidence feedback row, on the
+    un-enrolled one); the receipt names the exact resulting content digest settlement
+    is about to produce, is committed to HEAD (created/reused/committed-existing vs.
+    commit-failed/collision/storage-rejected/invalid-existing-receipt/no-worktree),
+    and publication stays create-once and keyed on its own inputs so a retry resolves
+    to the same already-published final, an existing final is returned rather than
+    overwritten, and nothing is deleted
+  intent: Make every successful settlement leave a durable, readable, committed
+    record — created before the canonical write it proves, never after — of which
+    artifact, decision, predecessor digest, feedback evidence, and resulting content
+    digest justify it, with a shipped check (not a manual procedure) for whether that
+    proof still holds later, so a receipt never outlives or outraces the settlement
+    it names.
   files:
   - plan_tool/roadmap_evidence_store.py
@@ -80,9 +88,10 @@ steps:
   title: Settle one decision on an un-enrolled roadmap by publishing its receipt first,
     then, once source admission and staleness both hold, publishing through
-    publish_stage_artifact's multi-member generation with invalidate_seeds=False,
-    keeping the existing journal recovery (roll back or drop an in-flight generation)
-    unchanged and updating the selected artifact's bytes and its stage baseline record
-    together — seed state and every other artifact/stage stay byte-identical before
-    and after
+    publish_stage_artifact's multi-member generation with its default seed-invalidation
+    behavior (never invalidate_seeds=False), keeping the existing journal recovery
+    (roll back or drop an in-flight generation) unchanged and updating the selected
+    artifact's bytes, its stage baseline record, and tracked derived seed state (marked
+    invalidated, exactly like any other stage-level content change) together — no
+    other artifact or stage is rewritten
   intent: Let an operator settle an approved decision on an ordinary roadmap by naming
     it, naming its evidence, and confirming — with no hand-edit of a canonical artifact,
@@ -110,9 +119,10 @@ steps:
     entries — then advancing the accepted head through a new additive PendingGeneration.kind
     recovery branch that reuses promote_review_seal's writer-token/journal selector-swap
-    but never calls _load_complete_sealed_candidate or either evidence loader; refuses
-    an in-flight pending generation and an admitted, unpromoted candidate lineage whose
-    predecessor is the current accepted head; root-enrollment and review-seal-promotion
-    recovery stay exactly as they are, and stored version members are never overwritten
-    or deleted
+    but never calls _load_complete_sealed_candidate or either evidence loader; recovers
+    a recognized completed version-owned generation exactly as existing recovery does
+    and refuses anything else; refuses whenever the current accepted head carries an
+    admitted, unpromoted candidate lineage (permanently, if that lineage never resolves);
+    root-enrollment and review-seal-promotion recovery stay exactly as they are, and
+    stored version members are never overwritten or deleted
   intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one,
     for a decision whose approving feedback already exists in the accepted version
@@ -139,13 +149,17 @@ steps:
     plan-tool roadmap as one exclusive action (missing-confirm and companion-option
     refusals named, matching --reopen-feedback's confirmation-required/mode-rejected
-    precedent), regenerate docs/cli/roadmap.md, and prove both lineages produce the
-    same settled row and that check_settled_decisions refuses drift on an un-enrolled
-    settled row this route just settled
+    precedent), extend every other broad roadmap mode's own _*_has_conflict check
+    to refuse when the settlement flags are present (exclusivity in both directions,
+    not only the settlement flags refusing others), regenerate docs/cli/roadmap.md,
+    and prove both lineages produce the same settled row and that check_settled_decisions
+    refuses drift on an un-enrolled settled row this route just settled
   intent: Give the operator the actual command, with the confirm flag that makes settlement
     their decision rather than the tool's and no backend call anywhere on the path,
-    then show the enrolled and un-enrolled paths are one capability rather than two
-    look-alikes by asserting identical before/after row content across both — proving
-    only the un-enrolled drift refusal, not any claim about the enrolled lineage, which
-    step 7's docs disclose separately.
+    make that exclusivity hold no matter which side names the conflicting option
+    rather than letting a combined command silently run a different action and drop
+    the settlement request, then show the enrolled and un-enrolled paths are one
+    capability rather than two look-alikes by asserting identical before/after row
+    content across both — proving only the un-enrolled drift refusal, not any claim
+    about the e
````

## 27. `roadmap-decision-settlement|2026-09-18T01:26:10Z|plan-plan-correctness-615c9d6b`

**Cited step:** 3: Add the immutable settlement receipt record and its own evidence namespace in plan_tool/roadmap_evidence_store.py; publication stays create-once, so an existing final is returned rather than overwritten and nothing is deleted

**Finding (plan-correctness, medium):** The References section states:

The References section states:

  ```
  both are wired only for an un-enrolled roadmap today via `require_unenrolled_roadmap_writer` (`plan_tool/roadmap_revision_publish.py`), confirming the enrolled side has no narrow-route precedent to reuse as-is.
  ```

  about `roadmap_feedback_reopen.py` and `roadmap_escalation_selection.py`, but this is only true of `--reopen-feedback`. `roadmap_escalation_selection.py` and its runner `roadmap_escalation_run.py` never call `require_unenrolled_roadmap_writer`, acquire no writer guard, and check no enrollment state — escalation-receipt creation already runs unchanged on an enrolled roadmap because it only writes into the immutable evidence store, never the canonical artifact. An enrolled-compatible narrow-route precedent therefore already exists for the receipt half of this design (step 3); the "no narrow-route precedent" claim only holds for the canonical-artifact-mutation half (step 5).

**Suggested action:** Narrow the References claim to the canonical-artifact-mutation precedent only, and note that escalation-receipt creation is itself a working enrolled-and-un-enrolled precedent for step 3's evidence-namespace write.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index cbef4422..e2972409 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -71,8 +71,9 @@ steps:
 - id: 4
   title: Settle one decision on an un-enrolled roadmap and publish its receipt through
-    publish_stage_artifact's multi-member generation, keeping the existing journal
-    recovery (roll back or drop an in-flight generation) unchanged and updating the
-    selected artifact's bytes and its stage baseline record together — no seed-state
-    or other artifact/stage is rewritten
+    publish_stage_artifact's multi-member generation with invalidate_seeds=False,
+    keeping the existing journal recovery (roll back or drop an in-flight generation)
+    unchanged and updating the selected artifact's bytes and its stage baseline record
+    together — seed state and every other artifact/stage stay byte-identical before
+    and after
   intent: Let an operator settle an approved decision on an ordinary roadmap by naming
     it, naming its evidence, and confirming — with no hand-edit of a canonical artifact.
@@ -93,16 +94,19 @@ steps:
     3: the receipt record published once the artifact write lands
 - id: 5
-  title: Settle one decision on an enrolled roadmap by storing a deterministic,
-    gate-checked version and advancing the accepted head through a new narrow promotion
-    boundary that reuses promote_review_seal's writer-token/journal selector-swap
-    but not its model-authored seal/review preconditions; refuses an in-flight pending
-    generation; enrolled recovery learns the settlement generation while root-enrollment
-    and review-seal-promotion recovery stay exactly as they are, and stored version
-    members are never overwritten or deleted
+  title: Settle one decision on an enrolled roadmap by storing the settled artifact
+    bytes as an ordinary version_kind candidate record — via create_candidate_version,
+    with a new dedicated no-review sentinel in place of INITIAL_EMPTY_REVIEW_LINEAGE_ID
+    and no candidate_evidence_path/replacement_evidence_path entries — then advancing
+    the accepted head through a new additive PendingGeneration.kind recovery branch
+    that reuses promote_review_seal's writer-token/journal selector-swap but never
+    calls _load_complete_sealed_candidate or either evidence loader; refuses an
+    in-flight pending generation; root-enrollment and review-seal-promotion recovery
+    stay exactly as they are, and stored version members are never overwritten or
+    deleted
   intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one
     without ever editing its accepted head in place, without fabricating a synthetic
-    model-authored candidate/review/seal chain to satisfy promote_review_seal's existing
-    preconditions, and without any accepted-head write path outside the guarded selector
-    swap.
+    model-authored candidate/review/seal chain or evidence file to satisfy
+    promote_review_seal's existing preconditions, and without any accepted-head write
+    path outside the guarded selector swap.
   files:
   - plan_tool/roadmap_revision_publish.py
@@ -197,8 +201,14 @@ uses for other single-row, evidence-bound, confirmed state changes
 `source`. `decisions` is a field on all four staged artifacts
 (Domain/Constraints/Components/Plans), not one file. `TEXT_FIELDS_BY_ROW_TYPE`
-in `plan_tool/roadmap_revision.py` is the field-authority allowlist for
-`--revise-feedback`; it names only `("rationale",)` for `decisions`, so
-`status` is structurally excluded — there is no explicit denial to relax,
-only an absent grant to add. `check_settled_decisions`
+in `plan_tool/roadmap_revision.py` is the field-authority allowlist for the
+generic, unconfirmed `--revise-feedback` local-revision path; it names only
+`("rationale",)` for `decisions`, so `status` is structurally excluded from
+it. Settlement does not add `status` to that allowlist or route through
+`preflight_feedback_revision` — doing so would open an unconfirmed,
+evidence-free path to flip a decision's status, the opposite of the
+narrow, evidence-bound action this plan builds. `replace_design_row`
+(`plan_tool/roadmap_artifacts.py`) already refuses any field whose current
+value is an `enum.Enum`, so `status` needs its own dedicated transition
+helper regardless; `check_settled_decisions`
 (`plan_tool/roadmap_gates.py`) already refuses a *settled* decision's id,
 status, chosen option, or anchor from drifting; it does not, and must not
@@ -250,30 +260,58 @@ evidence-bound shape every other narrow roadmap action already has.
   generation (`roadmap_revision_publish.py`) — the same primitive an
   ordinary stage revision uses — so the artifact bytes and the stage
-  baseline record update atomically together. No other artifact, seed-state,
-  or unrelated stage's baseline is touched.
+  baseline record update atomically together. `publish_stage_artifact`
+  defaults to invalidating the roadmap's shared derived-seed state on every
+  call (`invalidate_seeds=None` resolves to `True`); settlement must pass
+  `invalidate_seeds=False` explicitly, since flipping one decision's status
+  is not a design change any derived seed needs reworked against. No other
+  artifact, seed-state, or unrelated stage's baseline is touched.
 - **Enrolled roadmap.** `promote_review_seal` (`roadmap_version_promotion.py`)
   is not a generic accepted-head write: it requires a full model-authored
   `CandidateProposalAdmission` → reviewer answer → `CandidateReviewSeal`
-  chain, and it is the sole existing writer of `accepted_head_path` after
-  root enrollment. Reusing it as-is would mean fabricating a synthetic
-  model-provenance record for a change nothing proposed or reviewed that
-  way. Settlement instead adds one new, narrow, non-model promotion
-  boundary: store the settled artifact bytes as a new immutable version
-  (reusing the existing storage primitives in `roadmap_versions.py`), prove
-  it gate-valid with the existing `check_complete_roadmap_gates` evaluator
-  (`roadmap_impact_snapshot.py` — the same evaluator `promote_review_seal`
-  itself uses), then advance `accepted_head_path` under the existing
-  writer-token lease and `PendingGeneration` journal — the same
-  selector-swap mechanics `promote_review_seal` uses, without its
-  seal/review preconditions. It must never write the accepted head outside
-  that guarded swap. A journal mid-flight (`PendingGeneration`) refuses
-  rather than attempting recovery — that repair belongs to the separate,
-  already-tracked "Incomplete immutable lifecycle journals" bug entry,
-  deferred pending BACKLOG #328 sign-off. The preflight leaf (step 2) reads
-  an enrolled roadmap's current content from
-  `load_accepted_version(...).artifact_bytes` — the same source
-  `roadmap_view.py:load_roadmap()` already uses for enrolled content —
-  never from on-disk stage files or the un-enrolled `ReceiptSafeSelector`
-  read path.
+  chain (via `_load_complete_sealed_candidate`), and it is the sole existing
+  writer of `accepted_head_path` after root enrollment. Reusing it as-is
+  would mean fabricating a synthetic model-provenance record for a change
+  nothing proposed or reviewed that way.
+
+  Settlement stores its settled artifact bytes as an ordinary
+  `version_kind: "candidate"` record via the existing
+  `create_candidate_version` (`roadmap_versions.py`) — the closed
+  `root`/`candidate` vocabulary is not widened, because
+  `_load_complete_sealed_candidate`'s two evidence loaders
+  (`load_stored_candidate_proposal`, `load_stored_candidate_review_replacement`)
+  are reachable only from the model-authored propose→review→promote pipeline
+  itself, never from `load_accepted_version` or any other generic content
+  read — a candidate record with no matchi
````

## 28. `security-check-command|2026-06-16T18:45:54Z|plan-plan-completeness-bbe95d20`

**Cited step:** 4: Add security-reconcile ReconcileKind + run_auto_reconcile_on_drift hook and teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add the dispatch branch) wired to it for plan⇆code security drift, and construct the standalone full plan⇄code surface drift scope (every step and its declared files in scope) so security --reconcile runs on a tree with no recorded file drift — synthesize that whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every step's declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift's int / self-persisted security-reconcile.json output back into a SecurityAuditResult so step 3's cmd_security can render result.findings and persist via write_security_report

**Finding (plan-completeness, medium):** For `--reconcile`, step 4's `run_auto_reconcile_on_drift` self-persists a per-step `security-reconcile.json` save (`save

For `--reconcile`, step 4's `run_auto_reconcile_on_drift` self-persists a per-step `security-reconcile.json` save (`save_review(kind="security-reconcile", step_id=...)`) for each drifted step, while step 3's `cmd_security` separately persists an aggregate via `write_security_report`. The plan never says which sidecar is canonical for `resolve_reusable_reconcile`/`resolve_reusable_security` reuse, so newest-wins resolution can pick a per-step save over the aggregate (or vice versa) nondeterministically.

**Suggested action:** define which reconcile sidecar is authoritative for reuse and eliminate the double-write.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index 0129b00a..13cbe922 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -20,8 +20,12 @@ steps:
   status: current
 - id: 2
-  title: Add resolve_reusable_security + fingerprinted <ts>-security.json persistence
-    (sibling of resolve_reusable_audit); scope reuse by target/source (plan vs code)
-    as well as kind+fingerprint so a plan-axis caller never reuses a code-axis report
-    or vice versa (per-target scoping lands here, not deferred)
+  title: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json persistence
+    (sibling of resolve_reusable_audit); scope reuse by target (plan vs code) via the
+    filename suffix as well as fingerprint so a plan-axis caller never reuses a code-axis
+    report or vice versa (per-target scoping lands here, not deferred); a target="plan"
+    save verdicts fresh on an unchanged plan fingerprint alone — do NOT gate plan-target
+    freshness on saved.code_fingerprint_present (that code-fingerprint staleness gate from
+    resolve_reusable_audit applies only to the code/reconcile targets), so step 5's
+    plan-fingerprint reuse engages instead of verdicting stale every run
   files:
   - plan_tool/security_audit.py
@@ -79,6 +83,7 @@ steps:
   detail: docs/implementation-plans/plan-details/security-check-command/04-security-reconcile-reconcilekind-run.md
 - id: 5
-  title: 'Wire security dimension into completeness: conceptual-layer call + grouped-report
-    section + JSON security bucket (the completeness --iterate loop firing of
+  title: 'Wire security dimension into completeness: conceptual-layer call + route
+    security_recs through the existing findings-summarization/rollup gate before
+    rendering + grouped-report section + JSON security bucket (the completeness --iterate loop firing of
     run_auto_reconcile_on_drift with mode="security" that operationalizes the step 4
     drift-retrigger hook is deferred to a dedicated follow-up step, not wired here)'
@@ -148,5 +153,6 @@ steps:
 - id: 9
   title: 'Deliver security auto-apply end-to-end: emit a [category-slug] from prompts/security-plan.md
-    and prompts/security.md, populate rec.anchor in _security_recommendations, seed
+    only (the per-step prompts/security.md is left unchanged so the --mode security per-step
+    path is preserved), populate rec.anchor in _security_recommendations, seed
     SECURITY_AUTO_APPLY_ALLOWLIST with hardcoded-secret, and wire security_finding_is_auto_applicable
     into the --iterate convergence apply loop; update RUNBOOK.md to document the now-active
@@ -155,5 +161,4 @@ steps:
   files:
   - plan_tool/prompts/security-plan.md
-  - plan_tool/prompts/security.md
   - plan_tool/security_audit.py
   - plan_tool/convergence.py
@@ -183,15 +188,22 @@ Security is **already a per-step review mode**, but only at the per-step level:
 A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean completeness hook; downstream steps assume this unless the detail step pushes back to the user.
 
-A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security.json` with a plan+code fingerprint, following the `resolve_reusable_audit`/`resolve_reusable_reconcile` reuse pattern. Because `target="plan"` and `target="code"` audits share the `kind="security"` bucket distinguished only by `source`, reuse resolution must scope by target/source as well as kind+fingerprint — a newest-by-kind lookup would serve a `target="code"` save to a plan-axis caller (completeness, step 5) or a plan save to `--target code` (step 3). A plan-audit reuse must never serve a code-audit report or vice versa.
+A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit`/`resolve_reusable_reconcile` reuse pattern. Because `target="plan"` and `target="code"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a plan-axis caller (completeness, step 5) can never resolve a `target="code"` save, nor `--target code` (step 3) a plan save — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa.
 
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by extending the `ReconcileKind` descriptor family (`cli/reconcile.py`) with a `security-reconcile` kind that audits plan-stated security intent against the code's actual security posture and emits drift findings, reusing `resolve_reusable_reconcile` fingerprinting and the `run_auto_reconcile_on_drift` hook so a code change since the last security audit re-triggers it. The standalone `plan-tool security --reconcile <name>` does **not** depend on in-run file drift: it derives its drift scope from the full plan⇄code surface — treating every plan step (and the files each step declares) as in scope — so it runs the intent-vs-posture comparison across the whole plan even on a tree with no recorded file drift. Step 5's completeness security dimension re-triggers by **fingerprint-gated reuse**, not the hook: on an unchanged plan+code fingerprint it reuses the saved `<ts>-security.json` report and skips the Claude pass, re-sampling only on a fingerprint miss — distinct from the standalone command's full-surface sweep. Wiring `run_auto_reconcile_on_drift`'s file-drift-gated path (caller-supplied `drifted`/`file_to_step`, auditing only steps that own drifted files) into the completeness/iteration loop is deferred to a follow-up step, not done in step 5. This requires a **dedicated drift prompt** that compares the plan's stated security intent against the code's actual posture (e.g. detecting a plan that *states* an authz step the code lacks); reusing the per-step `prompts/security.md` code audit via `mode="security"` does **not** satisfy these drift semantics — it only re-runs a co
````

## 29. `security-check-command|2026-06-17T02:07:13Z|plan-plan-completeness-9db3a98a`

**Cited step:** 4: Add security-reconcile ReconcileKind + run_auto_reconcile_on_drift hook and teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add the dispatch branch) wired to it for plan⇆code security drift, and construct the standalone full plan⇄code surface drift scope (every step and its declared files in scope) so security --reconcile runs on a tree with no recorded file drift — synthesize that whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every step's declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift's in-memory int / per-step findings output (with its per-step security-reconcile.json persistence suppressed so write_security_report is the sole on-disk writer) back into a SecurityAuditResult so step 3's cmd_security can render result.findings and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(..., target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile; the reconcile family uses resolve_saved_review in review_persistence

**Finding (plan-completeness, high):** The HIGH "Standalone `security --reconcile` fan-out cost" risk states its *only* mitigation is the `resolve_reusable_sec

The HIGH "Standalone `security --reconcile` fan-out cost" risk states its *only* mitigation is the `resolve_reusable_security(..., target="reconcile")` hit short-circuiting the whole-plan sweep — but step 4's Deferred list defers that reuse wiring (see [reuse-read-wiring]). As sequenced, every standalone `security --reconcile` runs `run_auto_reconcile_on_drift` per step (confirmed: one `run_step` Claude call per step over `build_file_to_step_map`'s whole-plan scope) even on a clean tree, with no in-plan bound. The named mitigation does not exist in this plan.

**Suggested action:** bring the fingerprint-gated short-circuit into an in-plan step, or restate the risk as accepted/unmitigated within this plan's scope.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index 4fcd07cd..4166446e 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -13,4 +13,6 @@ steps:
   - plan_tool/prompts/security-plan.md
   - tests/test_security_audit.py
+  allowed_mentions:
+  - plan_tool/prompts/security.md
   complexity: high
   change_type: feature
@@ -20,12 +22,12 @@ steps:
   status: current
 - id: 2
-  title: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json persistence
-    (sibling of resolve_reusable_audit); scope reuse by target (plan vs code) via the
-    filename suffix as well as fingerprint so a plan-axis caller never reuses a code-axis
-    report or vice versa (per-target scoping lands here, not deferred); a target="plan"
-    save verdicts fresh on an unchanged plan fingerprint alone — do NOT gate plan-target
-    freshness on saved.code_fingerprint_present (that code-fingerprint staleness gate from
-    resolve_reusable_audit applies only to the code/reconcile targets), so step 5's
-    plan-fingerprint reuse engages instead of verdicting stale every run
+  title: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json
+    persistence (sibling of resolve_reusable_audit); scope reuse by target (plan vs
+    code) via the filename suffix as well as fingerprint so a plan-axis caller never
+    reuses a code-axis report or vice versa (per-target scoping lands here, not deferred);
+    a target="plan" save verdicts fresh on an unchanged plan fingerprint alone — do
+    NOT gate plan-target freshness on saved.code_fingerprint_present (that code-fingerprint
+    staleness gate from resolve_reusable_audit applies only to the code/reconcile
+    targets)
   files:
   - plan_tool/security_audit.py
@@ -38,7 +40,7 @@ steps:
 - id: 3
   title: 'Register security subcommand (cli/security_cmd.py: --target plan|code, --reconcile,
-    --fail-on-findings) across all five registration seams, wiring resolve_reusable_security
-    into cmd_security so --target code reuses a saved report on a fingerprint hit; --target
-    code requires --step (single-step audit)'
+    --fail-on-findings) across all five registration seams; reuse-prompt wiring of
+    resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
+    --target code requires --step (single-step audit)'
   files:
   - plan_tool/cli/app.py
@@ -58,14 +60,17 @@ steps:
   detail: docs/implementation-plans/plan-details/security-check-command/03-register-security-subcommand-cli.md
 - id: 4
-  title: 'Add security-reconcile ReconcileKind + run_auto_reconcile_on_drift hook and
-    teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add the
-    dispatch branch) wired to it for plan⇆code security drift, and construct the standalone
-    full plan⇄code surface drift scope (every step and its declared files in scope) so
-    security --reconcile runs on a tree with no recorded file drift — synthesize that
-    whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every
-    step''s declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift''s
-    in-memory int / per-step findings output (with its per-step security-reconcile.json persistence
-    suppressed so write_security_report is the sole on-disk writer) back into a SecurityAuditResult so
-    step 3''s cmd_security can render result.findings and persist via write_security_report'
+  title: Add security-reconcile ReconcileKind + run_auto_reconcile_on_drift hook and
+    teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add
+    the dispatch branch) wired to it for plan⇆code security drift, and construct the
+    standalone full plan⇄code surface drift scope (every step and its declared files
+    in scope) so security --reconcile runs on a tree with no recorded file drift —
+    synthesize that whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map
+    over every step's declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift's
+    in-memory int / per-step findings output (with its per-step security-reconcile.json
+    persistence suppressed so write_security_report is the sole on-disk writer) back
+    into a SecurityAuditResult so step 3's cmd_security can render result.findings
+    and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(...,
+    target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
+    the reconcile family uses resolve_saved_review in review_persistence
   files:
   - plan_tool/cli/reconcile.py
@@ -77,4 +82,7 @@ steps:
   creates:
   - plan_tool/prompts/security-reconcile.md
+  allowed_mentions:
+  - plan_tool/prompts/detail-reconcile.md
+  - plan_tool/prompts/security.md
   complexity: medium
   change_type: feature
@@ -84,30 +92,37 @@ steps:
   detail: docs/implementation-plans/plan-details/security-check-command/04-security-reconcile-reconcilekind-run.md
 - id: 5
-  title: 'Wire security dimension into completeness: conceptual-layer call + route
-    security_recs through the existing findings-summarization/rollup gate before
-    rendering + grouped-report section + JSON security bucket + emit a `security --reconcile`
-    advisory pointer on code-only drift (cached `<ts>-security-plan.json` reused, not re-sampled)
-    (the completeness --iterate loop firing of
-    run_auto_reconcile_on_drift with mode="security" that operationalizes the step 4
-    drift-retrigger hook is deferred to a dedicated follow-up step, not wired here)'
+  title: Emit a relevance-gated `plan-tool security` next-step pointer at the end
+    of `detail` and `completeness` — NOT a security dimension inside completeness.
+    Append a suggestion line via the existing _print_next_steps helper (cli/console.py)
+    in cli/authoring.py:cmd_detail (after the existing review/run/jira Next-steps
+    block) and in cli/completeness_phases.py:_persist_and_present_report (both the
+    --iterate summary path and the audit-only path). Completeness does NOT invoke
+    run_security_audit, render a Security section in _render_grouped_report, or add
+    a security bucket to _render_completeness_json — security stays a standalone command
+    the pointer advertises. Unconditional emission lands here; step 6 adds the relevance
+    gate
   files:
+  - plan_tool/cli/authoring.py
   - plan_tool/cli/completeness_phases.py
-  - plan_tool/cli/completeness_cmd.py
-  - tests/test_cli.py
+  - tests/cli/test_authoring.py
   - tests/cli/test_completeness_cmd.py
-  complexity: high
+  allowed_mentions:
+  - tests/cli/test_authoring_cmds.py
+  complexity: medium
   change_type: feature
   depends_on:
-  - 1
-  - 2
-  - 4
-  detail: docs/implementation-plans/plan-details/security-check-command/05-wire-security-dimension-completeness.md
+  - 3
+  detail: docs/implementation-plans/plan-details/security-check-command/05-emit-relevance-gated-plan-tool-security.md
 - id: 6
-  title: Add cost relevance gate + --with-security flag controlling whether the completeness
-    security dimension runs
+  title: Add a cheap, no-Claude relevance gate (keyword scan of plan title + step
+    titles + declared file paths) that decides whether the step-5 next-step pointer
+    is shown, plus a --no-security-hint suppression flag. A wrong verdict only shows
+    or hides a one-line suggestion (no Claude spend either way), so the gate is low-stakes
+    — it gates the pointer, never an audit pass
   files:
+  - plan_tool/cli/authoring.py
   - plan_tool/cli/completeness_phases.py
-  - plan_tool/cli/completeness_cmd.py
   - plan_tool/cli/parser.py
+  - plan_tool/security_audit.py
   - tests/cli/test_completeness_cmd.py
   complexity: medium
@@ -115,8 +130,11 @@ steps:
   depends_on:
   - 5
-  detail: docs
````

## 30. `roadmap-revision-retention|2026-08-19T13:34:16Z|plan-plan-completeness-27abd946`

**Cited step:** 3: Add `closed` to FeedbackState and update the dropped-feedback gate's violation message and the revision prompt's state enum, carry-forward instruction, and "never do" text — all three currently say the only close is deleting the row

**Finding (plan-completeness, critical):** `_ANSWERED_FEEDBACK_STATE` (`roadmap_gates.py:1406-1409`) has no `FeedbackState.CLOSED` key, so `check_feedback_integrit

`_ANSWERED_FEEDBACK_STATE` (`roadmap_gates.py:1406-1409`) has no `FeedbackState.CLOSED` key, so `check_feedback_integrity`'s lookup `_ANSWERED_FEEDBACK_STATE[prior.state]` (`roadmap_gates.py:1557`) raises an unhandled `KeyError` on the very first revision run against an artifact carrying a `closed` feedback row — before the code ever reaches the response-equality check just below it (`roadmap_gates.py:1585-1602`). That means neither of the plan's own headline acceptance criteria — "a closed feedback row persists across a revision that touches unrelated rows" and "a closed row's `proposed_response` changing... is rejected by the same check" — can even be exercised; the run crashes instead. The plan's own Architecture section names the exact fix verbatim ("`_ANSWERED_FEEDBACK_STATE`... needs a `FeedbackState.CLOSED: FeedbackState.CLOSED` self-mapping — the same shape `DEFERRED` already has"), but step 3, the step that adds `closed` to `FeedbackState`, enumerates a narrower, explicit list of edits (the dropped-feedback gate's violation message, and the revision prompt's state enum, carry-forward instruction, and "never do" text) that does not include this dict, and no other step names it either.

**Suggested action:** add the `_ANSWERED_FEEDBACK_STATE` self-mapping addition to step 3's scope explicitly, alongside the `FeedbackState.CLOSED` member itself.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-revision-retention.md b/docs/implementation-plans/2-roadmap-revision-retention.md
index 6f58492e..71f49c1d 100644
--- a/docs/implementation-plans/2-roadmap-revision-retention.md
+++ b/docs/implementation-plans/2-roadmap-revision-retention.md
@@ -10,13 +10,14 @@ enforce_step_tests: true
 steps:
 - id: 1
-  title: Add the removed row's content snapshot to RemovalRecord, render it back on
-    every artifact rewrite, and require it only on newly declared removals
+  title: Add the removed row's content snapshot to RemovalRecord, populated mechanically
+    from the predecessor's own rendered row content — never model-authored — and
+    rendered back on every artifact rewrite
   intent: So a reader of a revised roadmap can see what the dropped row actually said
-    instead of having to go read git.
+    instead of having to go read git, with no faithfulness question to gate because
+    the render layer derives the snapshot rather than the model paraphrasing it.
   files:
   - plan_tool/roadmap_artifacts.py
   - plan_tool/roadmap_gates.py
   - plan_tool/roadmap_view.py
-  - plan_tool/prompts/roadmap-revision.md
   - tests/test_roadmap_artifacts.py
   - tests/test_roadmap_gates.py
@@ -26,8 +27,10 @@ steps:
   status: current
 - id: 2
-  title: Add the optional decision reference to RemovalRecord, render it back, and
-    check it names a decision the artifact declares
+  title: Add the optional decision reference to RemovalRecord, render it back, check
+    it names a decision the artifact declares, and add it to the revision prompt's
+    removals field list and worked example as a model-suppliable field
   intent: So a removal can point at the decision whose rejected alternatives explain
-    the drop, instead of leaving the reasoning stranded in a separate collection.
+    the drop, instead of leaving the reasoning stranded in a separate collection —
+    and so the model actually knows the field exists to supply it.
   files:
   - plan_tool/roadmap_artifacts.py
@@ -46,8 +49,12 @@ steps:
       join whole-record carry identity.
 - id: 3
-  title: Add `closed` to FeedbackState, keep the reviewer's delete-the-row close working,
-    and replace the gates' 'close by deleting the row' correction text
-  intent: So a reviewer can answer and retire a feedback request in the file itself,
-    and the record of what was asked and how it was answered stays in the artifact.
+  title: Add `closed` to FeedbackState and update the dropped-feedback gate's violation
+    message and the revision prompt's state enum, carry-forward instruction, and
+    "never do" text — all three currently say the only close is deleting the row
+  intent: So a reviewer can retire a feedback request by setting its `state` field
+    to `closed` in the file instead of deleting it, and the record of what was
+    asked and how it was answered stays in the artifact; a reviewer keeps full
+    deletion rights over any row, closed included, so this retention binds only
+    the model's own edits, never the reviewer's.
   files:
   - plan_tool/roadmap_artifacts.py
@@ -60,8 +67,10 @@ steps:
   change_type: feature
 - id: 4
-  title: Add a gate requiring closed feedback rows to come after every other row in
-    the feedback collection
+  title: Add a gate rejecting a revision whose `feedback` collection places a `closed`
+    row before a non-`closed` row, and tell the model in the revision prompt to keep
+    closed rows last when it re-emits the collection
   intent: So the live part of the review queue reads first and retained closed rows
-    accumulate at the end instead of interleaving with open requests.
+    accumulate at the end instead of interleaving with open requests, and the model
+    has the guidance it needs to satisfy the gate on the first attempt.
   files:
   - plan_tool/roadmap_gates.py
@@ -94,8 +103,12 @@ steps:
       `state: closed` is the supported close so the CLI guidance can name it.'
 - id: 6
-  title: Rename `--mode review` to `--mode history`, dropping the `review` spelling
-    from the choices with no alias
+  title: Rename `--mode review` to `--mode history` everywhere it appears — the argparse
+    choices, MODE_REVIEW's branch sites and docstrings in roadmap_view.py (including
+    its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text, and
+    every literal `--mode review` example in README.md, docs/ROADMAP_WALKTHROUGH.md,
+    and docs/ARCHITECTURE.md — dropping the `review` spelling with no alias
   intent: So the flag says what the mode shows now that the collections it surfaces
-    retain history rather than only pending review work.
+    retain history rather than only pending review work, and no operator-facing
+    text anywhere still tells someone to pass a value the parser now rejects.
   files:
   - plan_tool/roadmap_view.py
@@ -113,10 +126,17 @@ steps:
   - 5
 - id: 7
-  title: Document the removal snapshot, the decision reference, the `closed` state,
-    and the closed-last ordering rule in ROADMAP_FORMAT.md
+  title: Document the removal snapshot, the decision reference, and the `closed` state
+    (including the closed-last ordering rule) in ROADMAP_FORMAT.md — correcting all
+    three existing "no `closed` member" sites (the schema block's `state` comment,
+    the Closed vocabularies table, and the feedback-lifecycle's situation 5) rather
+    than adding fresh prose beside them — and correct RUNBOOK.md's close-request
+    table row and "Preserved by the gates" tables to match
   intent: So the review collections' schema is readable without opening the parser,
-    which is what the whole FORMAT-doc family exists to guarantee.
+    which is what the whole FORMAT-doc family exists to guarantee, and so a reviewer
+    who trusts RUNBOOK.md's walkthrough learns the retention path exists instead of
+    being told deletion is still the only way to close a request.
   files:
   - ROADMAP_FORMAT.md
+  - RUNBOOK.md
   - tests/test_roadmap_format.py
   complexity: high
@@ -165,5 +185,8 @@ Three additive changes to the shared review-collection shape:
   content as it stood at removal.
 - `FeedbackState` gains `closed`; closed rows are retained in the `feedback`
-  collection (never deleted) and render last within it.
+  collection — never deleted by the model — and render last within it. A
+  reviewer, editing the file directly before a run, keeps full deletion
+  rights over any row, closed included, exactly as today; retention binds
+  only the model's own edits.
 - `RemovalRecord` gains an optional reference to the `DecisionRow` whose
   `rejected_alternatives` explain the drop.
@@ -204,4 +227,17 @@ retention in the one place `check_feedback_integrity` and
 a second collection would mean two places to look for a feedback id.
 
+**The snapshot is mechanically captured, never model-authored.** When a
+removal is newly declared — its `removed_id` not yet in `carried` — the
+render layer copies the predecessor's own rendered content for that row
+into the snapshot before the artifact is written; the model supplies only
+`removed_id`, `rationale`, and `feedback_ids`, exactly as it does today, and
+step 1 makes no prompt change. This is why `## Not allowed`'s ban on a
+faithfulness gate is safe: there is no faithfulness question to gate,
+because the snapshot is derived from the row's own last-known-good render
+rather than paraphrased. It stays inside BACKLOG #242's "no orchestrator
+change" boundary because the capture is a render-time transform in
+`roadmap_artifacts.py`, not a change to `roadmap.py`'s stage-running
+orchestrator.
+
 **Removal-carry identity is whole-record equality, and the new fields join
 it — this is what makes the fields' immutability enforceable for free.**
@@ -217,4 +253,18 @@ asks the model to touch a carried record afterward. No separate
 immutability gate is needed for these two fields.
 
+A tampered carried removal — one field edited, so it no lo
````

## 31. `arm-clustering-cross-round-consensus|2026-08-12T19:37:39Z|plan-plan-completeness-d75cc9fa`

**Cited step:** None: None

**Finding (plan-completeness, medium):** Architecture point 7 lists exactly three arguments to pass into `evaluate_arm_clustering` unchanged — `consensus_targets

Architecture point 7 lists exactly three arguments to pass into `evaluate_arm_clustering` unchanged — `consensus_targets`, `material_finding_ids`, `declared_step_ids` — and never mentions `material_finding_evidence`, the fourth input the same-execution caller always builds from each finding's real `anchor`/`source`. Left unset, the leaf still returns a well-formed advisory (it fills in a placeholder empty-anchor/empty-source entry per id when none is passed), but every cross-round advisory would render blank anchor/source instead of the finding's actual ones, unlike the same-execution advisory.

**Suggested action:** have step 2 also build `material_finding_evidence` from each matched `RunFinding`'s `anchor`/`source`, the same shape the same-execution caller already builds from `Recommendation`.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
index dc35c926..d82b3756 100644
--- a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
+++ b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
@@ -80,6 +80,10 @@ steps:
   title: Update the docs for the cross-round advisory and settle the backlog entries
   intent: 'Keep the always-injected guidance honest once this ships, so the next session
-    does not read `--audit-passes 1 disables it outright`, the four-import leaf claim,
-    or an open #264 as still true.'
+    does not read `--audit-passes 1 disables it outright`, the four-import leaf claim
+    in CLAUDE.md, `convergence_diagnosis.py`''s own matching "cycle-free leaf" docstring
+    paragraph, or `docs/ARCHITECTURE.md`''s third restatement of the same
+    "review_persistence, review, locator, convergence" import list (all three name the
+    same fact and all three need the same audit_shapes.py import added by step 2), or
+    an open #264 as still true.'
   files:
   - CLAUDE.md
@@ -87,4 +91,5 @@ steps:
   - docs/AUDIT_FLOW.md
   - BACKLOG.md
+  - plan_tool/convergence_diagnosis.py
   complexity: medium
   change_type: non-code
@@ -144,10 +149,14 @@ settled precedent, not a gap to redesign.
    unaffected — they keep reading `observations_by_id` and the transient tag
    directly.
-2. Materiality: treat a saved finding as material via
+2. Materiality: treat a matched finding as material via
    `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=…)`
-   — the same rule `classify_edit_drift`'s `_edit_drift_eligible` already
-   applies to `RunFinding` objects pulled from history
-   (`convergence_diagnosis.py:885`). This is a different, deliberate choice
-   from same-execution arm-clustering's `is_blocking_impact` +
+   checked **only against the newest round's copy** of that finding — the
+   same rule `classify_edit_drift`'s `_edit_drift_eligible` already applies to
+   `RunFinding` objects pulled from history (`convergence_diagnosis.py:885`),
+   and the same newest-round keying point 7 already uses for the output
+   mapping. A finding's severity/impact tag can differ across matched rounds;
+   only the newest round's copy decides materiality, never a mix or an
+   older round's. This is a different, deliberate choice from same-execution
+   arm-clustering's `is_blocking_impact` +
    `build_low_impact_demotion_lookup(repo_root)` (`review.py:7929,7774`),
    which rebuilds a live per-run calibration lookup and was designed for a
@@ -176,8 +185,17 @@ settled precedent, not a gap to redesign.
    targets disagree; a target is missing on some round; a step's renumbering
    breaks target continuity even though the finding still matches by
-   anchor/title; **or** the single agreed target is not among the *current*
-   round's `declared_step_ids` (the step was deferred, marked `wont_do`,
-   deleted, or renumbered since the last matched round). Never guess a target
-   and never pass an unresolved or stale one through.
+   anchor/title; the single agreed target is not among the *current* round's
+   `declared_step_ids` (the step was deferred, marked `wont_do`, deleted, or
+   renumbered since the last matched round); **or** the target step's current
+   `status` is `done`. `declared_step_ids` / `committed_step_ids` is built
+   from `StepScope.COMMITTED` (`completeness_report.py:122`,
+   `review.py:8059`), which is the commitment axis, not the lifecycle axis
+   (`schema.py:StepScope`) — a shipped step stays `scope: committed` and so
+   stays in that list, so list membership alone cannot detect a target that
+   shipped between the matched rounds and a later `plan-tool convergence`
+   read. Check the target step's `status` directly; this plan's own
+   governing rule (a `done` step is "shipped: context, never a target") is
+   how a stale-but-shipped target must be treated here too. Never guess a
+   target and never pass an unresolved or stale one through.
    `evaluate_arm_clustering` returns `None` for the *entire* advisory the
    moment any id in `material_finding_ids` lacks a target inside the
@@ -188,5 +206,21 @@ settled precedent, not a gap to redesign.
    ids), that same resolved-subset `material_finding_ids`, and the newest
    round's committed `declared_step_ids` into `evaluate_arm_clustering`
-   unchanged. The leaf's own gap-free proper-majority-arm math is not touched.
+   unchanged. Two more of the leaf's parameters are not optional in practice
+   and must be supplied, matching same-execution's own call
+   (`review.py:8064-8076`): `material_finding_evidence` — built from the
+   newest round's own `RunFinding.anchor`/`.source` for each resolved id
+   (already-persisted fields, no new plumbing) — since an empty evidence
+   tuple defaults every item to `anchor=None`, which
+   `completeness_report.py`'s renderer (`_advisory_arm_steps`,
+   line ~149-157) skips, leaving the printed arm's finding list empty; and
+   `source_plan_fingerprint` — the plan's *current* fingerprint computed at
+   call time (not a saved round's), matching how same-execution stamps
+   `audit_input_snapshot.fingerprint` and how `completeness_report.py`'s
+   `matches_disk` staleness check consumes it. Leaving either at its
+   signature default (`()` / `""`) is a caller bug, not a valid choice: an
+   empty `source_plan_fingerprint` fails `_is_valid_stored_arm_advisory`'s
+   own non-empty check (`audit_shapes.py:121`) and voids the advisory
+   outright. The leaf's own gap-free proper-majority-arm math is not
+   touched.
 8. When the classifier has nothing to report — including when a previously-
    firing arm's cross-round consensus becomes unresolvable — the render emits
@@ -253,5 +287,5 @@ See the `steps:` block in the frontmatter.
   the field and its `DATA_CONTRACT.md` entry must land in the same step, not
   split across steps 1 and 5.
-- A silent non-fire (Architecture point 7) is easy to misread from the outside
+- A silent non-fire (Architecture point 8) is easy to misread from the outside
   as "the arm resolved" rather than "evidence became unavailable." Acceptance
   criteria settle this as accepted, explicitly-decided behavior rather than a
@@ -260,4 +294,9 @@ See the `steps:` block in the frontmatter.
 - Windowing on the wrong `audit_stage` (mixing bare and detail history) would
   manufacture a consensus target that never coexisted in one coherent audit.
+- `evaluate_arm_clustering`'s `material_finding_evidence` and
+  `source_plan_fingerprint` both default to empty/falsy values that are easy
+  to leave unset by omission rather than by decision — the former silently
+  degrades the render, the latter silently voids the whole advisory. Both are
+  named explicitly in Architecture point 7 so they are supplied by decision.
 
 ## Testing
@@ -266,22 +305,31 @@ Prove: (1) the plan-audit's parsed `[audit-step:N]` tag round-trips onto a
 saved `Recommendation`/`RunFinding` via `save_review`/`resolve_saved_review`,
 documented in `DATA_CONTRACT.md`; (2) materiality for cross-round consensus is
-computed via `is_blocking_finding` (stage-aware, matching
-`classify_edit_drift`'s own use on `RunFinding`s), independent of and not
-required to agree with same-execution's `is_blocking_impact` +
-calibration-lookup materiality; (3) a finding with a stable `_matches` identity
-and one agreeing persisted `audit_step_target` across the 2-round window
-produces a resolved consensus target; (4) a finding whose matched target
-disagrees, is missing on one round, or agrees across the window but is absent
-from the *current* `declared_step_ids` (deferred/`wont_do`/deleted/renumbered
-since the match), is dropped from **both** `consensus_targets` and the
-`material_finding_ids` passed to `evaluate_arm_clustering`, never causing the
-whole advisory to return `None`; (5) a renumbered step that 
````

## 32. `roadmap-revision-retention|2026-08-19T14:05:05Z|plan-plan-correctness-63374786`

**Cited step:** 6: Rename `--mode review` to `--mode history` everywhere it appears — the argparse choices, MODE_REVIEW's branch sites and docstrings in roadmap_view.py (including its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text, plan_tool/cli/__init__.py's package-level `--help` catalog docstring (and the golden snapshot pinning it), and every literal `--mode review` example in README.md, docs/ROADMAP_WALKTHROUGH.md, and docs/ARCHITECTURE.md — dropping the `review` spelling with no alias

**Finding (plan-correctness, medium):** `--mode review` names two unrelated CLI flags in this codebase: `roadmap --view … --mode {current,review}` (what step 6 

`--mode review` names two unrelated CLI flags in this codebase: `roadmap --view … --mode {current,review}` (what step 6 means to rename) and the completely separate per-step audit primitive `run <name> --mode <review>` / `verify-all <name> --mode <m>` (`plan_tool/cli/__init__.py:44-45`, `README.md:1764-1771`), whose "review" is a placeholder for one of check/optimize/document/test/security/lint and has nothing to do with the roadmap arc. Step 6's title says "Rename `--mode review` to `--mode history` everywhere it appears," and its own site list includes "every literal `--mode review` example in README.md" and "`plan_tool/cli/__init__.py`'s package-level `--help` catalog docstring" — the same file and, in README's case, a heading a few paragraphs away ("Review-mode result summarization") from the unrelated flag's documentation. A literal-string sweep for the exact phrase `--mode review` happens to stay safe today (the unrelated flag is spelled `--mode <review>` / `--mode <m>`), but the step's own vocabulary doesn't state that distinction, so a reader following "everywhere it appears" has to independently notice the boundary the plan never names.

**Suggested action:** add one sentence to step 6 naming the unrelated `run`/`verify-all` review-mode audit flag as explicitly out of scope for this rename, so the sweep of the shared catalog docstring and README.md doesn't need to be inferred site-by-site.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-revision-retention.md b/docs/implementation-plans/2-roadmap-revision-retention.md
index 71f49c1d..d7b2a424 100644
--- a/docs/implementation-plans/2-roadmap-revision-retention.md
+++ b/docs/implementation-plans/2-roadmap-revision-retention.md
@@ -11,9 +11,13 @@ steps:
 - id: 1
   title: Add the removed row's content snapshot to RemovalRecord, populated mechanically
-    from the predecessor's own rendered row content — never model-authored — and
-    rendered back on every artifact rewrite
+    from the predecessor's own rendered row content — never model-authored — rendered
+    back on every artifact rewrite, and give `check_design_row_continuity` a
+    tampering-specific branch so an edited (not fabricated) carried removal is
+    rejected with a message naming the changed field and telling the model to
+    revert it, not drop the record
   intent: So a reader of a revised roadmap can see what the dropped row actually said
     instead of having to go read git, with no faithfulness question to gate because
-    the render layer derives the snapshot rather than the model paraphrasing it.
+    the render layer derives the snapshot rather than the model paraphrasing it, and
+    so an accidental edit to a carried removal gets a correction the model can act on.
   files:
   - plan_tool/roadmap_artifacts.py
@@ -45,11 +49,14 @@ steps:
   - 1
   depends_on_notes:
-    1: Lands the omit-when-absent render idiom on _removal_mapping and the parse-unchanged
-      back-compat cases this second field reuses, and settles that both new fields
-      join whole-record carry identity.
+    1: Lands the omit-when-absent render idiom on _removal_mapping, the parse-unchanged
+      back-compat cases this second field reuses, and the tampering-specific branch
+      in check_design_row_continuity — step 2 extends that same branch to compare
+      decision_reference too, rather than building a second one.
 - id: 3
-  title: Add `closed` to FeedbackState and update the dropped-feedback gate's violation
-    message and the revision prompt's state enum, carry-forward instruction, and
-    "never do" text — all three currently say the only close is deleting the row
+  title: Add `closed` to FeedbackState with a `_ANSWERED_FEEDBACK_STATE` self-mapping
+    (so a carried closed row's lookup doesn't raise `KeyError` and crash the revision),
+    and update the dropped-feedback gate's violation message and the revision
+    prompt's state enum, carry-forward instruction, and "never do" text — all three
+    currently say the only close is deleting the row
   intent: So a reviewer can retire a feedback request by setting its `state` field
     to `closed` in the file instead of deleting it, and the record of what was
@@ -86,8 +93,13 @@ steps:
       nothing to order last until closed rows can exist.
 - id: 5
-  title: 'Count closed rows in the roadmap summary and tell the operator to close
-    by setting `state: closed` rather than by deleting'
+  title: 'Count closed rows in both roadmap summary renderers — `_feedback_summary_lines`
+    (cli/roadmap_cmd.py, the run/revision post-run summary) and `_summary_feedback_counts`
+    / `render_roadmap_summary` (roadmap_view.py, the `--view summary` surface step
+    6 renames to `--mode history`) — and tell the operator to close by setting
+    `state: closed` rather than by deleting'
   intent: So the two hand-written state lists an operator actually reads stop disagreeing
-    with the state vocabulary the parser accepts.
+    with the state vocabulary the parser accepts, on both the post-run summary and
+    the renamed `--mode history` view whose whole rationale is surfacing retained
+    history.
   files:
   - plan_tool/roadmap_view.py
@@ -105,13 +117,17 @@ steps:
   title: Rename `--mode review` to `--mode history` everywhere it appears — the argparse
     choices, MODE_REVIEW's branch sites and docstrings in roadmap_view.py (including
-    its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text, and
-    every literal `--mode review` example in README.md, docs/ROADMAP_WALKTHROUGH.md,
-    and docs/ARCHITECTURE.md — dropping the `review` spelling with no alias
+    its two hard-coded operator hint strings), cli/roadmap_cmd.py's help text,
+    plan_tool/cli/__init__.py's package-level `--help` catalog docstring (and the
+    golden snapshot pinning it), and every literal `--mode review` example in
+    README.md, docs/ROADMAP_WALKTHROUGH.md, and docs/ARCHITECTURE.md — dropping
+    the `review` spelling with no alias
   intent: So the flag says what the mode shows now that the collections it surfaces
     retain history rather than only pending review work, and no operator-facing
-    text anywhere still tells someone to pass a value the parser now rejects.
+    text anywhere — including the top-level `plan-tool --help` catalog — still
+    tells someone to pass a value the parser now rejects.
   files:
   - plan_tool/roadmap_view.py
   - plan_tool/cli/roadmap_cmd.py
+  - plan_tool/cli/__init__.py
   - docs/cli/roadmap.md
   - README.md
@@ -121,4 +137,5 @@ steps:
   - tests/test_roadmap_view.py
   - tests/cli/test_roadmap_cmd.py
+  - tests/cli/package_surface_help.golden.txt
   complexity: medium
   change_type: refactor
@@ -130,6 +147,10 @@ steps:
     three existing "no `closed` member" sites (the schema block's `state` comment,
     the Closed vocabularies table, and the feedback-lifecycle's situation 5) rather
-    than adding fresh prose beside them — and correct RUNBOOK.md's close-request
-    table row and "Preserved by the gates" tables to match
+    than adding fresh prose beside them — correct RUNBOOK.md's close-request table
+    row and "Preserved by the gates" tables to match, and add a feedback-state
+    vocabulary-completeness test to tests/test_roadmap_format.py mirroring
+    `test_hosting_schema_documents_the_complete_gate_owned_vocabulary` /
+    `test_store_schema_documents_the_complete_gate_owned_vocabulary`, since no such
+    guard exists today for FeedbackState
   intent: So the review collections' schema is readable without opening the parser,
     which is what the whole FORMAT-doc family exists to guarantee, and so a reviewer

````

## 33. `roadmap-decision-settlement|2026-09-18T02:46:54Z|plan-plan-completeness-6404abc3`

**Cited step:** 3: Add the immutable settlement receipt record and its own evidence namespace in plan_tool/roadmap_evidence_store.py, naming the exact resulting content digest settlement is about to produce; publication stays create-once and keyed on its own inputs so a retry resolves to the same already-published final, an existing final is returned rather than overwritten, and nothing is deleted

**Finding (plan-completeness, medium):** Step 3 (settlement receipt record) adds a third `EvidenceNamespace`, but no step updates docs/ARCHITECTURE.md § "Immutab

Step 3 (settlement receipt record) adds a third `EvidenceNamespace`, but no step updates docs/ARCHITECTURE.md § "Immutable roadmap evidence". That section says `publish_evidence` "accepts only the code-owned `EvidenceNamespace.ESCALATIONS` or `EvidenceNamespace.IMPACT_ANALYSES` token" and lists exactly two fixed paths. The four new modules (`roadmap_decision_settlement.py`, `roadmap_decision_settlement_receipt.py`, `roadmap_decision_settlement_run.py`, `roadmap_decision_settlement_enrolled.py`) also get no entry in that module-by-module doc. Once step 3 ships, the two-namespace statement is false, and neither step 3 nor step 8 lists `docs/ARCHITECTURE.md` or has a criterion covering it.

**Suggested action:** Add `docs/ARCHITECTURE.md` to step 8 (or step 3), with an acceptance line requiring that the evidence-namespace list include the settlement namespace and that the settlement modules be described.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index 8f8f0d5b..39e715c5 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -31,12 +31,16 @@ steps:
 - id: 2
   title: Add a decision-settlement preflight leaf that resolves the decision target,
-    its feedback evidence, and the predecessor digest — reading enrolled content from
-    the accepted version, not on-disk stage files — with one named refusal per rejection
-    class
+    matches feedback evidence to it by FeedbackTargetKind.ROW/row_id rather than just
+    resolving the feedback id, accepts any FeedbackState, requires un-enrolled baseline
+    admission before reading the source, and computes the predecessor digest — reading
+    enrolled content from the accepted version, not on-disk stage files — with one
+    named refusal per rejection class
   intent: Prove, before any write, that exactly one live Roadmap-derived pending decision
-    was named, that a named live feedback row carries non-empty reviewer-authored
-    `request` text (never model-authored `proposed_response`), and that the source
-    bytes (on-disk artifact for an un-enrolled roadmap, accepted-version bytes for
-    an enrolled one) have not moved since the evidence was read.
+    was named, that a named live feedback row actually targets it (not just resolves)
+    and carries non-empty reviewer-authored `request` text in any FeedbackState (never
+    model-authored `proposed_response`), that an un-enrolled source is admitted against
+    its recorded baseline, and that the source bytes (on-disk artifact for an un-enrolled
+    roadmap, accepted-version bytes for an enrolled one) have not moved since the
+    evidence was read.
   creates:
   - plan_tool/roadmap_decision_settlement.py
@@ -51,9 +55,13 @@ steps:
 - id: 3
   title: Add the immutable settlement receipt record and its own evidence namespace
-    in plan_tool/roadmap_evidence_store.py; publication stays create-once, so an existing
-    final is returned rather than overwritten and nothing is deleted
-  intent: Make every successful settlement leave a durable, readable record of which
-    artifact, decision, predecessor digest, and feedback evidence justified it, so
-    the approval can be proven after the fact.
+    in plan_tool/roadmap_evidence_store.py, naming the exact resulting content digest
+    settlement is about to produce; publication stays create-once and keyed on its
+    own inputs so a retry resolves to the same already-published final, an existing
+    final is returned rather than overwritten, and nothing is deleted
+  intent: Make every successful settlement leave a durable, readable record — written
+    before the row-level write it proves, never after — of which artifact, decision,
+    predecessor digest, feedback evidence, and resulting content digest justify it,
+    so the approval can be proven after the fact and a receipt never outlives or
+    outraces the settlement it names.
   files:
   - plan_tool/roadmap_evidence_store.py
@@ -70,5 +78,6 @@ steps:
       recorded facts
 - id: 4
-  title: Settle one decision on an un-enrolled roadmap and publish its receipt through
+  title: Settle one decision on an un-enrolled roadmap by publishing its receipt first,
+    then, once source admission and staleness both hold, publishing through
     publish_stage_artifact's multi-member generation with invalidate_seeds=False,
     keeping the existing journal recovery (roll back or drop an in-flight generation)
@@ -77,5 +86,6 @@ steps:
     and after
   intent: Let an operator settle an approved decision on an ordinary roadmap by naming
-    it, naming its evidence, and confirming — with no hand-edit of a canonical artifact.
+    it, naming its evidence, and confirming — with no hand-edit of a canonical artifact,
+    and with a receipt that always precedes the write it proves.
   files:
   - plan_tool/roadmap_revision_publish.py
@@ -90,21 +100,24 @@ steps:
   - 3
   depends_on_notes:
-    2: the preflight candidate and its final staleness recheck, called inside the
-      writer lease before the artifact is replaced
-    3: the receipt record published once the artifact write lands
+    2: the preflight candidate, its source-admission check, and its final staleness
+      recheck, called inside the writer lease before the artifact is replaced
+    3: the receipt writer, called before the artifact write, not after
 - id: 5
   title: Settle one decision on an enrolled roadmap by storing the settled artifact
     bytes as an ordinary version_kind candidate record — via create_candidate_version,
-    with a new dedicated no-review sentinel in place of INITIAL_EMPTY_REVIEW_LINEAGE_ID
-    and no candidate_evidence_path/replacement_evidence_path entries — then advancing
-    the accepted head through a new additive PendingGeneration.kind recovery branch
-    that reuses promote_review_seal's writer-token/journal selector-swap but never
-    calls _load_complete_sealed_candidate or either evidence loader; refuses an
-    in-flight pending generation; root-enrollment and review-seal-promotion recovery
-    stay exactly as they are, and stored version members are never overwritten or
-    deleted
-  intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one
-    without ever editing its accepted head in place, without fabricating a synthetic
-    model-authored candidate/review/seal chain or evidence file to satisfy
+    with a new dedicated no-review sentinel in place of INITIAL_EMPTY_REVIEW_LINEAGE_ID,
+    a settlement-owned content_identity, and no candidate_evidence_path/replacement_evidence_path
+    entries — then advancing the accepted head through a new additive PendingGeneration.kind
+    recovery branch that reuses promote_review_seal's writer-token/journal selector-swap
+    but never calls _load_complete_sealed_candidate or either evidence loader; refuses
+    an in-flight pending generation and an admitted, unpromoted candidate lineage whose
+    predecessor is the current accepted head; root-enrollment and review-seal-promotion
+    recovery stay exactly as they are, and stored version members are never overwritten
+    or deleted
+  intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one,
+    for a decision whose approving feedback already exists in the accepted version
+    (nothing can add feedback to an enrolled roadmap today), without ever editing its
+    accepted head in place, without fabricating a synthetic model-authored
+    candidate/review/seal chain, evidence file, or content_identity to satisfy
     promote_review_seal's existing preconditions, and without any accepted-head write
     path outside the guarded selector swap.
@@ -142,11 +155,11 @@ steps:
       head
 - id: 7
-  title: Prove both lineages produce the same settled row, that check_settled_decisions
-    refuses drift on an un-enrolled settled row, and document that the same protection
-    does not yet exist on the enrolled lineage (tracked separately in BUG_BACKLOG.md)
+  title: Prove both lineages produce the same settled row and that check_settled_decisions
+    refuses drift on an un-enrolled settled row this route just settled
   intent: Show the enrolled and un-enrolled paths are one capability rather than two
     look-alikes, by asserting identical before/after row content across both, and
-    state plainly rather than silently which lineage's settled decisions are actually
-    protected from later drift.
+    prove only what these test files can actually demonstrate — the un-enrolled drift
+    refusal, not any claim about the enrolled lineage, which step 8's docs disclose
+    separately.
   files:
   - tests/cli/test_roadmap_cmd.py
@@ -159,15 +172,28 @@ steps:
     6: the single command entry both lineages are driven throug
````

## 34. `roadmap-decision-settlement|2026-09-18T02:00:16Z|plan-plan-correctness-dc5041fb`

**Cited step:** None: None

**Finding (plan-correctness, high):** The plan requires that settlement evidence be "a live feedback row ... that targets the decision," but never says what m

The plan requires that settlement evidence be "a live feedback row ... that targets the decision," but never says what makes a feedback row count as targeting a decision, and the plan's own list of seven refusal cases in Testing never names a case for a feedback row that exists, has non-empty text, but is about something else. The Architecture section states the requirement this way:

```
a second selector naming one live `feedback` row in the same artifact whose
`request` field — "the reviewer's own words," per `FeedbackRow`'s own
docstring, and never rewritten by the model — is non-empty and targets the
decision, plus the operator's own required, argument-less confirm flag
```

  `FeedbackRow.target` (`FeedbackTarget` in `plan_tool/roadmap_artifacts.py`) can point at the whole artifact (`FeedbackTargetKind.ARTIFACT`, no `row_id`) or at one specific row (`FeedbackTargetKind.ROW`, with `row_id` set). The sibling `--revise-feedback` path this plan cites as its own structural precedent (`preflight_feedback_revision` in `plan_tool/roadmap_revision.py`) already answers this exact question for its own use case by requiring `target.kind is FeedbackTargetKind.ROW` and matching `target.row_id` to the row being edited — but nothing in this plan says the settlement route must do the same check against the selected decision's id. The evidence selector the plan describes (`FeedbackSelector`-style: artifact key + feedback id) only resolves a feedback row by its own id; matching it to *the row it's about* is a separate step this plan never names. Without that check, an operator (or a bug in whatever builds the command) could cite any live, non-empty feedback row in the same artifact — one written about a completely different decision, or one that doesn't name a row at all — as "evidence" for settling any pending decision in that artifact, which quietly defeats the "bound to explicit reviewed evidence" guarantee the whole feature exists to provide.

**Suggested action:** State that a feedback row "targets the decision" only when its `target.kind` is `FeedbackTargetKind.ROW` and `target.row_id` equals the selected decision's id, add this as an explicit named refusal case alongside the other seven (a resolvable feedback row that does not target the selected decision), and add a test proving that citing a live, non-empty-`request` feedback row that targets a *different* row (or the whole artifact) is refused rather than accepted.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index e2972409..8f8f0d5b 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -142,9 +142,11 @@ steps:
       head
 - id: 7
-  title: Prove both lineages produce the same settled row and that check_settled_decisions
-    still refuses drift on a row this route settled
+  title: Prove both lineages produce the same settled row, that check_settled_decisions
+    refuses drift on an un-enrolled settled row, and document that the same protection
+    does not yet exist on the enrolled lineage (tracked separately in BUG_BACKLOG.md)
   intent: Show the enrolled and un-enrolled paths are one capability rather than two
-    look-alikes, by asserting identical before/after row content across both, instead
-    of settling for parallel 'it runs' coverage.
+    look-alikes, by asserting identical before/after row content across both, and
+    state plainly rather than silently which lineage's settled decisions are actually
+    protected from later drift.
   files:
   - tests/cli/test_roadmap_cmd.py
@@ -361,7 +363,16 @@ evidence-bound shape every other narrow roadmap action already has.
   extend `TEXT_FIELDS_BY_ROW_TYPE` or route through this generic,
   unconfirmed, evidence-free `--revise-feedback` path.
-- `plan_tool/roadmap_gates.py` (`check_settled_decisions`) — the complementary
-  gate that must keep making a settled decision immutable once this route
-  produces one.
+- `plan_tool/roadmap_gates.py` (`check_settled_decisions`) and
+  `plan_tool/roadmap_impact_snapshot.py` (`_evaluate_full_roadmap_gates`) —
+  `check_settled_decisions` genuinely protects a settled decision against
+  later drift on the un-enrolled lineage, where ordinary revision/reconcile
+  paths build a real `predecessor`. `_evaluate_full_roadmap_gates` —
+  the evaluator every enrolled candidate promotion runs through — always
+  builds `predecessor=None`, so `check_settled_decisions` is a permanent
+  no-op there; this is a pre-existing gap (tracked as its own
+  `BUG_BACKLOG.md` entry, "An enrolled roadmap's candidate promotion never
+  re-checks a settled decision against its predecessor"), not one this plan
+  creates or fixes, and step 7 only demonstrates the protection that
+  actually exists.
 - `plan_tool/roadmap_feedback_reopen.py` and
   `plan_tool/roadmap_escalation_selection.py`
@@ -369,11 +380,18 @@ evidence-bound shape every other narrow roadmap action already has.
   `FeedbackSelector`) — the structural precedent this route's selector,
   predecessor-digest staleness check, and named-reason refusal shape should
-  follow; both are wired only for an un-enrolled roadmap today via
-  `require_unenrolled_roadmap_writer` (`plan_tool/roadmap_revision_publish.py`),
-  confirming the enrolled side has no narrow-route precedent to reuse as-is.
-  Neither touches `.roadmap-baselines`, because feedback is the one thing
-  `canonical_projection` excludes from the digest; a decision's `status` is
-  not excluded, so the un-enrolled write must instead follow
-  `plan_tool/roadmap_revision_publish.py:publish_stage_artifact`'s
+  follow. `roadmap_feedback_reopen.py`'s canonical-artifact write is wired
+  only for an un-enrolled roadmap via `require_unenrolled_roadmap_writer`
+  (`plan_tool/roadmap_revision_publish.py`), confirming the enrolled side
+  has no canonical-artifact-mutation precedent to reuse as-is — this is
+  what step 5 must build fresh. `roadmap_escalation_selection.py` and its
+  runner `roadmap_escalation_run.py`, by contrast, call no writer guard and
+  check no enrollment state at all: escalation-receipt creation already
+  works unchanged on an enrolled roadmap because it writes only into the
+  immutable evidence store, never a canonical artifact — an already-working
+  enrolled-and-un-enrolled precedent for step 3's evidence-namespace
+  receipt write. Neither touches `.roadmap-baselines`, because feedback is
+  the one thing `canonical_projection` excludes from the digest; a
+  decision's `status` is not excluded, so the un-enrolled write must
+  instead follow `plan_tool/roadmap_revision_publish.py:publish_stage_artifact`'s
   multi-member generation, which updates the artifact and its baseline
   record together.
@@ -462,4 +480,11 @@ See the `steps:` block in the frontmatter.
   mistake must get the same refusal `preflight_feedback_revision` already
   gives other inherited-row edits, not a new, differently-worded one.
+- **Overclaimed enrolled protection:** `_evaluate_full_roadmap_gates` (the
+  evaluator every enrolled candidate promotion runs through) always builds
+  `predecessor=None`, so `check_settled_decisions` is a permanent no-op on
+  the enrolled lineage — a pre-existing gap this plan is the first to make
+  reachable, tracked as its own `BUG_BACKLOG.md` entry. This plan must not
+  claim or test a drift protection on the enrolled lineage that does not
+  exist; state the gap plainly instead.
 
 ## Testing
@@ -489,6 +514,9 @@ the settlement receipt records the artifact key, decision id, predecessor
 digest, and cited feedback id/digest, and that a legacy roadmap with no
 receipts directory still parses and settles correctly. Confirm
-`check_settled_decisions` still refuses drift on the row this route just
-settled.
+`check_settled_decisions` refuses drift on an un-enrolled row this route
+just settled. Do not test or claim the same protection on the enrolled
+lineage: `_evaluate_full_roadmap_gates` always builds `predecessor=None`,
+so `check_settled_decisions` is a documented no-op on every enrolled
+candidate promotion today (tracked separately in `BUG_BACKLOG.md`).
 
 ## Acceptance criteria
@@ -509,4 +537,8 @@ settled.
   enrolled write never constructs a synthetic model-authored
   candidate/review/seal chain.
+- `check_settled_decisions` is demonstrated to refuse drift on an
+  un-enrolled settled row. The plan documents, rather than silently
+  overclaims, that the enrolled lineage has no equivalent protection today
+  (a pre-existing gap tracked in `BUG_BACKLOG.md`, not fixed by this plan).
 - A durable receipt exists after every successful settlement and can be read
   back to prove which evidence justified it.
@@ -520,4 +552,10 @@ settled.
 A symmetric "un-settle" / reopen route for a `settled` decision, BACKLOG
 #242's feedback-closing work, and any repair path for a malformed immutable
-lifecycle journal all remain separate efforts. File any newly discovered gap
-in `BACKLOG.md` or `BUG_BACKLOG.md` rather than expanding this plan.
+lifecycle journal all remain separate efforts. Also deferred: giving
+`_evaluate_full_roadmap_gates` a real predecessor so `check_settled_decisions`
+actually protects a settled decision against a later enrolled candidate
+promotion — a pre-existing gap this plan is the first to make reachable,
+filed as its own `BUG_BACKLOG.md` entry rather than bundled into this
+feature, since it changes the shared evaluator every candidate promotion
+runs through. File any newly discovered gap in `BACKLOG.md` or
+`BUG_BACKLOG.md` rather than expanding this plan.

````

## 35. `roadmap-decision-settlement|2026-09-18T02:00:16Z|plan-plan-correctness-a457c7d7`

**Cited step:** 2: Add a decision-settlement preflight leaf that resolves the decision target, its feedback evidence, and the predecessor digest — reading enrolled content from the accepted version, not on-disk stage files — with one named refusal per rejection class

**Finding (plan-correctness, medium):** Step 2 (settlement preflight) must give "an inherited decision selected as target" and "a non-pending decision (already 

Step 2 (settlement preflight) must give "an inherited decision selected as target" and "a non-pending decision (already settled)" separate named reasons. But an inherited row is always `settled`, so both classes match on any artifact that passes the gates, and the plan never says which one wins. Testing lists them as separate cases:

  ```
  own named reason: missing or mismatched decision target; an inherited
  decision selected as target; a non-pending decision (already settled);
  ```

  At HEAD, `roadmap_gates.py:check_inherited_decisions` emits `inherited-decision-unconfirmed` for any inherited row whose status is not `settled`. If step 2 checks status first, the inherited refusal can only be reached, and tested, with an artifact that fails that gate. Risks "Inherited-row confusion" implies the inherited reason should win but never says so.

**Suggested action:** State that the inherited-row check runs before the status check, and have the inherited-row test use a settled inherited row that passes the gates.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index e2972409..8f8f0d5b 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -142,9 +142,11 @@ steps:
       head
 - id: 7
-  title: Prove both lineages produce the same settled row and that check_settled_decisions
-    still refuses drift on a row this route settled
+  title: Prove both lineages produce the same settled row, that check_settled_decisions
+    refuses drift on an un-enrolled settled row, and document that the same protection
+    does not yet exist on the enrolled lineage (tracked separately in BUG_BACKLOG.md)
   intent: Show the enrolled and un-enrolled paths are one capability rather than two
-    look-alikes, by asserting identical before/after row content across both, instead
-    of settling for parallel 'it runs' coverage.
+    look-alikes, by asserting identical before/after row content across both, and
+    state plainly rather than silently which lineage's settled decisions are actually
+    protected from later drift.
   files:
   - tests/cli/test_roadmap_cmd.py
@@ -361,7 +363,16 @@ evidence-bound shape every other narrow roadmap action already has.
   extend `TEXT_FIELDS_BY_ROW_TYPE` or route through this generic,
   unconfirmed, evidence-free `--revise-feedback` path.
-- `plan_tool/roadmap_gates.py` (`check_settled_decisions`) — the complementary
-  gate that must keep making a settled decision immutable once this route
-  produces one.
+- `plan_tool/roadmap_gates.py` (`check_settled_decisions`) and
+  `plan_tool/roadmap_impact_snapshot.py` (`_evaluate_full_roadmap_gates`) —
+  `check_settled_decisions` genuinely protects a settled decision against
+  later drift on the un-enrolled lineage, where ordinary revision/reconcile
+  paths build a real `predecessor`. `_evaluate_full_roadmap_gates` —
+  the evaluator every enrolled candidate promotion runs through — always
+  builds `predecessor=None`, so `check_settled_decisions` is a permanent
+  no-op there; this is a pre-existing gap (tracked as its own
+  `BUG_BACKLOG.md` entry, "An enrolled roadmap's candidate promotion never
+  re-checks a settled decision against its predecessor"), not one this plan
+  creates or fixes, and step 7 only demonstrates the protection that
+  actually exists.
 - `plan_tool/roadmap_feedback_reopen.py` and
   `plan_tool/roadmap_escalation_selection.py`
@@ -369,11 +380,18 @@ evidence-bound shape every other narrow roadmap action already has.
   `FeedbackSelector`) — the structural precedent this route's selector,
   predecessor-digest staleness check, and named-reason refusal shape should
-  follow; both are wired only for an un-enrolled roadmap today via
-  `require_unenrolled_roadmap_writer` (`plan_tool/roadmap_revision_publish.py`),
-  confirming the enrolled side has no narrow-route precedent to reuse as-is.
-  Neither touches `.roadmap-baselines`, because feedback is the one thing
-  `canonical_projection` excludes from the digest; a decision's `status` is
-  not excluded, so the un-enrolled write must instead follow
-  `plan_tool/roadmap_revision_publish.py:publish_stage_artifact`'s
+  follow. `roadmap_feedback_reopen.py`'s canonical-artifact write is wired
+  only for an un-enrolled roadmap via `require_unenrolled_roadmap_writer`
+  (`plan_tool/roadmap_revision_publish.py`), confirming the enrolled side
+  has no canonical-artifact-mutation precedent to reuse as-is — this is
+  what step 5 must build fresh. `roadmap_escalation_selection.py` and its
+  runner `roadmap_escalation_run.py`, by contrast, call no writer guard and
+  check no enrollment state at all: escalation-receipt creation already
+  works unchanged on an enrolled roadmap because it writes only into the
+  immutable evidence store, never a canonical artifact — an already-working
+  enrolled-and-un-enrolled precedent for step 3's evidence-namespace
+  receipt write. Neither touches `.roadmap-baselines`, because feedback is
+  the one thing `canonical_projection` excludes from the digest; a
+  decision's `status` is not excluded, so the un-enrolled write must
+  instead follow `plan_tool/roadmap_revision_publish.py:publish_stage_artifact`'s
   multi-member generation, which updates the artifact and its baseline
   record together.
@@ -462,4 +480,11 @@ See the `steps:` block in the frontmatter.
   mistake must get the same refusal `preflight_feedback_revision` already
   gives other inherited-row edits, not a new, differently-worded one.
+- **Overclaimed enrolled protection:** `_evaluate_full_roadmap_gates` (the
+  evaluator every enrolled candidate promotion runs through) always builds
+  `predecessor=None`, so `check_settled_decisions` is a permanent no-op on
+  the enrolled lineage — a pre-existing gap this plan is the first to make
+  reachable, tracked as its own `BUG_BACKLOG.md` entry. This plan must not
+  claim or test a drift protection on the enrolled lineage that does not
+  exist; state the gap plainly instead.
 
 ## Testing
@@ -489,6 +514,9 @@ the settlement receipt records the artifact key, decision id, predecessor
 digest, and cited feedback id/digest, and that a legacy roadmap with no
 receipts directory still parses and settles correctly. Confirm
-`check_settled_decisions` still refuses drift on the row this route just
-settled.
+`check_settled_decisions` refuses drift on an un-enrolled row this route
+just settled. Do not test or claim the same protection on the enrolled
+lineage: `_evaluate_full_roadmap_gates` always builds `predecessor=None`,
+so `check_settled_decisions` is a documented no-op on every enrolled
+candidate promotion today (tracked separately in `BUG_BACKLOG.md`).
 
 ## Acceptance criteria
@@ -509,4 +537,8 @@ settled.
   enrolled write never constructs a synthetic model-authored
   candidate/review/seal chain.
+- `check_settled_decisions` is demonstrated to refuse drift on an
+  un-enrolled settled row. The plan documents, rather than silently
+  overclaims, that the enrolled lineage has no equivalent protection today
+  (a pre-existing gap tracked in `BUG_BACKLOG.md`, not fixed by this plan).
 - A durable receipt exists after every successful settlement and can be read
   back to prove which evidence justified it.
@@ -520,4 +552,10 @@ settled.
 A symmetric "un-settle" / reopen route for a `settled` decision, BACKLOG
 #242's feedback-closing work, and any repair path for a malformed immutable
-lifecycle journal all remain separate efforts. File any newly discovered gap
-in `BACKLOG.md` or `BUG_BACKLOG.md` rather than expanding this plan.
+lifecycle journal all remain separate efforts. Also deferred: giving
+`_evaluate_full_roadmap_gates` a real predecessor so `check_settled_decisions`
+actually protects a settled decision against a later enrolled candidate
+promotion — a pre-existing gap this plan is the first to make reachable,
+filed as its own `BUG_BACKLOG.md` entry rather than bundled into this
+feature, since it changes the shared evaluator every candidate promotion
+runs through. File any newly discovered gap in `BACKLOG.md` or
+`BUG_BACKLOG.md` rather than expanding this plan.

````

## 36. `security-check-command|2026-06-20T21:11:54Z|plan-plan-completeness-6bfb8730`

**Cited step:** 6: Add a cheap, no-Claude relevance gate (exact-token, not substring, scan of plan title + step titles + declared file paths — each declared path first split into tokens on the path separators and word boundaries `/`, `_`, `.`, and `-`, so e.g. `plan_tool/cli/security_cmd.py` yields tokens {plan, tool, cli, security, cmd, py} and the bare path string is never matched whole) that decides whether the step-5 next-step pointer is shown, plus a --no-security-hint suppression flag. A wrong verdict only shows or hides a one-line suggestion (no Claude spend either way), so the gate is low-stakes — it gates the pointer, never an audit pass

**Finding (plan-completeness, medium):** Step 6 (`security_hint_is_relevant` in `security_audit.py`) decides whether the `→ plan-tool security --target plan` poi

Step 6 (`security_hint_is_relevant` in `security_audit.py`) decides whether the `→ plan-tool security --target plan` pointer is shown by exact-token scanning only the plan title, step titles, and declared file paths (`Step.all_files`) — never the plan/step **body prose**. But the plan-target audit's flagship purpose (Architecture: "secrets baked into the plan body") and its sole auto-apply category (`hardcoded-secret`, step 9, confined to "a literal value present in the plan prose itself") live exactly in that body. A plan that bakes a literal secret into a step's prose while its titles/paths carry no security keyword gets no pointer, so the operator is never nudged toward the one audit designed to mechanically remove it — the gate's own "enough to suppress on plans with no plausible security surface" justification is overstated for the body-secret case.

**Suggested action:** acknowledge in step 6 (and the pointer acceptance criterion) that the keyword gate is structurally blind to body-baked secrets, and either extend the relevance scan to plan/step body prose or state body-secret false-negatives as an accepted limitation.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index f1c5187f..32c7f146 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -47,5 +47,10 @@ steps:
     --fail-on-findings) across all five registration seams; reuse-prompt wiring of
     resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
-    --target code requires --step (single-step audit)'
+    --target code requires --step (single-step audit), and --step is rejected at
+    parse time when combined with --reconcile (usage error, non-zero rc — the reconcile
+    direction is whole-plan full-surface, so a single --step is meaningless against it);
+    cmd_security renders
+    result.skipped_steps alongside the findings so a partial reconcile sweep (step 4)
+    is reported as partial, not as a clean pass'
   files:
   - plan_tool/cli/app.py
@@ -75,5 +80,9 @@ steps:
     persistence suppressed so write_security_report is the sole on-disk writer) back
     into a SecurityAuditResult so step 3's cmd_security can render result.findings
-    and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(...,
+    and persist via write_security_report; because the generalized hook's best-effort loop
+    skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel
+    to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit)
+    and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default —
+    so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(...,
     target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
     the reconcile family uses resolve_saved_review in review_persistence
@@ -255,5 +264,5 @@ Security is **already a per-step review mode**, but only at the per-step level:
 ## Architecture
 
-A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`.
+A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`. **`--step` is rejected at parse time when combined with `--reconcile`** (a usage error, non-zero rc, never dispatching): the reconcile direction derives its scope from the full plan⇄code surface (every step and its declared files), so a single `--step` is meaningless against it — `plan-tool security --reconcile --step <id> <name>` is an error, not a one-step reconcile, keeping the whole-plan full-surface contract unambiguous. `--step` remains required for `--target code` (single-step audit) and unused for `--target plan`.
 
 A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit` reuse pattern. Because `target="plan"`, `target="code"`, and `target="reconcile"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json` vs `-security-reconcile.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a `--target code` caller can never resolve a `target="plan"` save, nor vice versa — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa. Beyond the target suffix, the **`target="code"` axis must additionally scope its lookup by `step_id`**: the `-security-code.json` suffix encodes only the target, not the step, so two steps' code audits write same-suffix sidecars — `resolve_reusable_security` for the code target must therefore key on `step_id` (mirroring the reconcile family's per-step `_find_saved_for_step`), not return the newest target-suffix sidecar (the whole-plan `resolve_reusable_audit` shape it is otherwise cloned from), or it would serve one step's saved code audit to a different step's caller. **`resolve_reusable_security` ships dormant in this plan:** step 2 builds it and step 3 writes the `<ts>-security-<target>.json` sidecar, but **no in-plan step reads the resolver** — the reuse-prompt wiring that would short-circuit a Claude call on an unchanged fingerprint is deferred to a follow-up for all three targets (see `## Deferred`). The persistence/lookup machinery lands write-ready so the follow-up only adds the consumer; this plan does not claim a reuse short-circuit it does not deliver.
@@ -261,5 +270,5 @@ A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by generalizing the `run_auto_reconcile_on_drift` hook (`auto_reconcile.py`) to audit plan-stated security intent against the code's actual security posture under a `mode="security-reconcile"` prompt and emit drift findings, so a code change since the last security audit re-triggers it. **No `security-reconcile` row is added to `cli/reconcile.py:_RECONCILE_KINDS`** — it would be dead config: the existing `detail-reconcile` / `run-reconcile` `name_includes` suffixes are substring-disjoint from `-security-reconcile`, so they already cannot mis-grab a security sidecar, and no production caller queries `resolve_reusable_reconc
````

## 37. `arm-clustering-cross-round-consensus|2026-08-12T21:33:43Z|plan-plan-correctness-4776a019`

**Cited step:** 1: Build arm-clustering consensus targets from saved audit history

**Finding (plan-correctness, medium):** Step 1's classifier body (Implementation §3, point 5 "Currency") requires `step_statuses.get(target) is not StepStatus.D

Step 1's classifier body (Implementation §3, point 5 "Currency") requires `step_statuses.get(target) is not StepStatus.DONE` as a live runtime comparison, but step 1's Files section only lists adding `Mapping, Sequence` to the existing `typing` import for `plan_tool/convergence_diagnosis.py` — it never lists adding a `StepStatus` import. The one sentence addressing it ("`StepStatus` from `plan_tool/schema.py`, already a dependency-safe leaf import — `plan_tool.review`, which this module already imports, pulls it in too") explains why adding the import introduces no new dependency-graph edge, not that the name is already usable: `convergence_diagnosis.py`'s existing `from plan_tool.review import Recommendation, STRUCTURAL_SOURCES, classify_finding_domain` is a selective import that does not bring `StepStatus` into this module's namespace. Without an explicit import, `StepStatus.DONE` is a `NameError` waiting to happen the first time the classifier body runs.

**Suggested action:** name the exact import statement (`from plan_tool.schema import StepStatus`, or via `plan_tool.review`) that step 1's Files/Implementation section must add, rather than the transitive-import phrase that doesn't actually add the name to this module's namespace.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
index f245ca0c..7a8e5205 100644
--- a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
+++ b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
@@ -17,7 +17,7 @@ steps:
     `Recommendation`/`RunFinding` (today it is parsed by `_split_audit_step_evidence`
     and then discarded into a transient in-call structure before a review is saved),
-    then let a material finding earn a consensus step target from that persisted
-    value across separate audit rounds, so arm-clustering has evidence to work with
-    on the --audit-passes 1 runs that give it only one same-execution sample.
+    then let a material finding earn a consensus step target from that persisted value
+    across separate audit rounds, so arm-clustering has evidence to work with on the
+    --audit-passes 1 runs that give it only one same-execution sample.
   files:
   - plan_tool/review.py
@@ -29,4 +29,5 @@ steps:
   complexity: high
   change_type: feature
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/01-build-arm-clustering-consensus-targets.md
   status: current
 - id: 2
@@ -51,9 +52,14 @@ steps:
     1: the classifier function and its advisory record, which diagnose_convergence
       calls and the render lines read fields off
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/02-cross-round-arm-clustering-advisory.md
 - id: 3
   title: Parse the plan once in cmd_convergence instead of inside _current_audit_stage
   intent: Make the parsed plan reachable from cmd_convergence so the next step can
     read its committed steps without parsing the file a second time or copying the
-    best-effort try/except.
+    best-effort try/except. The hoisted `parse_plan` call must keep degrading to `diagnose_convergence`'s
+    pre-stage-bar blanket-blocking defaults on a parse failure or missing plan — the
+    same outcome `_current_audit_stage`'s existing try/except gives today — so `cmd_convergence`'s
+    documented "always exits 0, never surfaces an error" contract survives the move
+    unchanged.
   files:
   - plan_tool/cli/convergence_cmd.py
@@ -61,13 +67,15 @@ steps:
   complexity: low
   change_type: refactor
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/03-parse-plan-once-cmd-convergence-instead.md
 - id: 4
   title: Pass committed step ids to the diagnosis from the convergence and completeness
     surfaces
   intent: Turn the classifier on for real operators by threading real committed step
-    ids *and* each step's current status (step 1's function signature accepts both as
-    parameters — a bare id list alone carries no status, and step 1's done-step drop
-    check needs it — but this step is what supplies real values from the plan's parsed
-    `Step` objects, not step 1) into it from the two places the sibling advisories
-    already print, so `plan-tool convergence` and completeness stderr both surface it.
+    ids *and* each step's current status (step 1's function signature accepts both
+    as parameters — a bare id list alone carries no status, and step 1's done-step
+    drop check needs it — but this step is what supplies real values from the plan's
+    parsed `Step` objects, not step 1) into it from the two places the sibling advisories
+    already print, so `plan-tool convergence` and completeness stderr both surface
+    it.
   files:
   - plan_tool/cli/convergence_cmd.py
@@ -85,4 +93,5 @@ steps:
     3: the parsed plan hoisted into cmd_convergence, so committed step ids come from
       the parse the stage lookup already did
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/04-pass-committed-step-ids-diagnosis.md
 - id: 5
   title: Update the docs for the cross-round advisory and settle the backlog entries
@@ -92,8 +101,8 @@ steps:
     CLAUDE.md''s "cycle-free leaf" bullet and `docs/ARCHITECTURE.md`''s "Convergence
     diagnostic" entry both restate that import set already inaccurately (CLAUDE.md
-    omits `granularity`; both predate this plan and are wrong independent of it), so
-    correct both to the module''s full current set (`review_persistence`, `review`,
-    `locator`, `convergence`, `granularity`) plus the new `audit_shapes` edge step 2
-    adds — not only append the one new edge onto an already-wrong baseline. The
+    omits `granularity`; both predate this plan and are wrong independent of it),
+    so correct both to the module''s full current set (`review_persistence`, `review`,
+    `locator`, `convergence`, `granularity`) plus the new `audit_shapes` edge step
+    2 adds — not only append the one new edge onto an already-wrong baseline. The
     module''s own docstring paragraph is step 2''s fix, made where the import lands,
     not this step''s.'
@@ -110,4 +119,5 @@ steps:
     4: the shipped surfaces and the final import edge, so the docs describe what landed
       rather than what was proposed
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/05-update-docs-cross-round-advisory-settle.md
 ---
 # Arm Clustering Cross Round Consensus
@@ -165,16 +175,33 @@ settled precedent, not a gap to redesign.
    Every cross-round consumer this plan builds reads `RunFinding`, not
    `Recommendation`, so missing the second site leaves the field permanently
-   `None` on everything this plan actually consumes. Document both fields in
-   `DATA_CONTRACT.md`. This is the one new piece of persisted state this plan
-   adds; `evaluate_arm_clustering` and the same-execution consensus path are
+   `None` on everything this plan actually consumes. The two fields get two
+   different kinds of documentation, landed in **this same step**, not
+   deferred to step 5's docs pass: `Recommendation.audit_step_target` is
+   persisted/serialized (round-trips via `save_review`), so it gets a row in
+   `DATA_CONTRACT.md`'s existing `Recommendation` table, same as `anchor` or
+   `impact`. `RunFinding` is not persisted on its own — its own docstring
+   calls it a flattening "from a saved report's recommendation list," and
+   `DATA_CONTRACT.md` documents only persisted/serialized schemas, which is
+   why none of `convergence_diagnosis.py`'s other dataclasses have an entry
+   there — so `RunFinding.audit_step_target` is documented inline in
+   `RunFinding`'s own docstring instead, matching how `step_id`, `anchor`, and
+   `impact` are already documented there, not as a new `DATA_CONTRACT.md`
+   section. This is the one new piece of persisted state this plan adds;
+   `evaluate_arm_clustering` and the same-execution consensus path are
    unaffected — they keep reading `observations_by_id` and the transient tag
    directly.
 2. Materiality: treat a matched finding as material via
    `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=…)`
-   checked **only against the newest round's copy** of that finding — the
-   same rule `classify_edit_drift`'s `_edit_drift_eligible` already applies to
-   `RunFinding` objects pulled from history (`convergence_diagnosis.py:885`),
-   and the same newest-round keying point 7 already uses for the output
-   mapping. A finding's severity/impact tag can differ across matched rounds;
+   checked **only against the newest round's copy** of that finding —
+   reusing only the stage-bar half of `classify_edit_drift`'s
+   `_edit_drift_eligible` (`convergence_diagnosis.py:885`), and the same
+   newest-round keying point 7 already uses for the output mapping.
+   `_edit_drift_eligible` also runs a second check —
+   `_is_resolved_in_run(annotations.get(finding.id))`, dropping a finding the
+   operator already declined between rounds — that this plan deliberately
+   does **not** reuse: Out of scope already refuses to gate cross-round
+
````

## 38. `roadmap-model-failure-receipts|2026-09-21T17:08:59Z|plan-plan-correctness-b2ca207d`

**Cited step:** 3: Record fresh roadmap stage failures before retry while preserving accepted artifact writes

**Finding (plan-correctness, medium):** Steps 3 (`Record fresh roadmap stage failures before retry while preserving accepted artifact writes`) and 4 (`Record bo

Steps 3 (`Record fresh roadmap stage failures before retry while preserving accepted artifact writes`) and 4 (`Record bounded roadmap feedback failures before retry while preserving accepted revision writes`) do not cover source admission rejected after a reply returns; `plan_tool/roadmap.py:_run_stage` rechecks sources after parsing and `_run_bounded_stage_feedback` calls `guard()` after parsing. Step 5 (`Record local feedback revision failures and reply-bearing gate rejections while preserving recoverable publication replacement`) includes the local path but treats `RoadmapSourceAdmissionError` as `gate-rejected`, not the Architecture’s required `source-admission-rejected`, leaving the promised shared reason and coverage inconsistent. 

```text
Architecture — “A source-admission failure found after a reply is returned uses the safe receipt reason `source-admission-rejected` and is sidecar-eligible across fresh authoring, bounded feedback, and local revision.”
```

**Suggested action:** Define and test one post-reply source-admission receipt route across steps 3–5, using `source-admission-rejected` and sidecar eligibility while keeping genuinely pre-invocation admission failures outside the receipt contract.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-model-failure-receipts.md b/docs/implementation-plans/2-roadmap-model-failure-receipts.md
index 47f7ccb6..a1d62143 100644
--- a/docs/implementation-plans/2-roadmap-model-failure-receipts.md
+++ b/docs/implementation-plans/2-roadmap-model-failure-receipts.md
@@ -28,4 +28,5 @@ steps:
   complexity: medium
   change_type: refactor
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/01-move-detail-raw-response-sidecar-writes.md
   status: current
 - id: 2
@@ -46,4 +47,5 @@ steps:
     1: Provides the shared sidecar result needed to record written, no-response, not-retained,
       and write-failed dispositions.
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/02-shared-redacted-model-failure-receipt.md
 - id: 3
   title: Record fresh roadmap stage failures before retry while preserving accepted
@@ -63,4 +65,5 @@ steps:
       stage, and attempt identifiers.
     2: Provides the redacted receipt shape and its closed sidecar dispositions.
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/03-record-fresh-roadmap-stage-failures.md
 - id: 4
   title: Record bounded roadmap feedback failures before retry while preserving accepted
@@ -80,9 +83,11 @@ steps:
     2: Provides the common receipt contract used for retained replies, absent replies,
       gate diagnostics, and sidecar write failures.
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/04-record-bounded-roadmap-feedback.md
 - id: 5
-  title: Record local feedback revision failures and reply-bearing gate rejections while
-    preserving recoverable publication replacement
+  title: Record local feedback revision failures and reply-bearing gate rejections
+    while preserving recoverable publication replacement
   intent: Give local --revise-feedback failures the same diagnostic evidence as roadmap
-    stage failures, retaining a rejected reply only when no structured gate diagnostic exists.
+    stage failures, retaining a rejected reply only when no structured gate diagnostic
+    exists.
   files:
   - plan_tool/roadmap_revision_run.py
@@ -97,4 +102,5 @@ steps:
       a local gate rejection that has no structured diagnostic event.
     2: Provides the shared receipt emitted after the sidecar disposition is resolved.
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/05-record-local-feedback-revision-failures.md
 - id: 6
   title: Document roadmap failure receipts and record the shipped backlog slice
@@ -118,4 +124,5 @@ steps:
     5: Delivers the local revision receipt behavior and completes the selected roadmap
       producer class.
+  detail: docs/implementation-plans/plan-details/roadmap-model-failure-receipts/06-document-roadmap-failure-receipts.md
 ---
 # Roadmap Model Failure Receipts
diff --git a/docs/implementation-plans/plan-details/roadmap-model-failure-receipts/03-record-fresh-roadmap-stage-failures.md b/docs/implementation-plans/plan-details/roadmap-model-failure-receipts/03-record-fresh-roadmap-stage-failures.md
new file mode 100644
index 00000000..b0c584be
--- /dev/null
+++ b/docs/implementation-plans/plan-details/roadmap-model-failure-receipts/03-record-fresh-roadmap-stage-failures.md
@@ -0,0 +1,101 @@
+# Step 3 — Record fresh roadmap stage failures before retry while preserving accepted artifact writes
+
+<!-- plan-tool:detail-format-version: 1 -->
+
+## Summary
+
+Add fresh-stage failure receipts to `plan_tool/roadmap.py` before `_run_stage` retries an invoke, parse, or authored-review-row failure. Reuse the shared sidecar and redacted receipt contracts delivered by steps 1 and 2, while keeping the current retry budget, correction prompts, artifact publication path, and gate diagnostics unchanged. Extend `tests/test_roadmap.py` around the existing retry-loop and `TestAttemptFailedEvent` coverage. On green, a failed fresh attempt remains diagnosable even when a later attempt writes the accepted artifact.
+
+## Table of Contents
+
+- [Summary](#summary) — Gives the reviewer the step’s outcome and main boundary.
+- [Table of Contents](#table-of-contents) — Links to the detail sections.
+- [Why](#why) — Explains the missing evidence for recovered fresh-stage failures.
+- [Input](#input) — Names the upstream receipt contracts this producer consumes.
+- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the focused code and test edits.
+- [Implementation](#implementation) — Defines when fresh-stage receipts are recorded and what remains unchanged.
+- [Tests](#tests) — Lists focused regression coverage for recovered failures and accepted writes.
+- [Acceptance criteria](#acceptance-criteria) — States observable completion conditions.
+- [References](#references) — Points to the relevant receipt and roadmap contracts.
+- [Applicable guardrails](#applicable-guardrails) — Applies the plan’s safety and scope limits.
+- [Deferred](#deferred) — Identifies related producer paths outside this step.
+
+## Why
+
+`plan_tool/roadmap.py:_run_stage` records spent attempts through `_note_stage_attempt_failure`, but `attempt_failed` does not retain a response identity or best-effort raw-response availability. When a later attempt succeeds, `RoadmapResult` carries only the accepted artifact, so an earlier fresh invoke, parse, or authored-review-row failure lacks the complete redacted evidence this plan requires.
+
+## Input
+
+- **Step 1 sidecar contract:** Use the shared rejected-response sidecar result produced by step 1. Preserve its disposition and path outcome without reopening, transforming, or cleaning up the sidecar.
+- **Step 2 receipt contract:** Use the shared run-log receipt helper produced by step 2 for the producer-owned phase, attempt, failure reason, response identity, and sidecar result.
+- **Fresh-stage failure classification:** `plan_tool/roadmap.py:_run_stage`, `_StageOutcome`, and `FAILURE_AUTHORED_REVIEW_ROWS` define the fresh attempt paths that spend the stage budget. The established `FAILURE_INVOKE` and `FAILURE_PARSE` outcomes remain their current classifications.
+
+## Files (creates vs edits)
+
+- **New files:**
+  - None.
+
+- **Existing files (edits only):**
+  - `plan_tool/roadmap.py` — Record a shared failure receipt for reply-bearing fresh-stage invoke, parse, and authored-review-row failures before `_run_stage` retries.
+  - `tests/test_roadmap.py` — Add focused recovered-attempt receipt coverage beside `TestRetryLoop` and `TestAttemptFailedEvent`.
+
+## Implementation
+
+- **Record each rejected fresh reply before retrying.** Extend `plan_tool/roadmap.py:_run_stage` so the fresh authoring loop uses the step 1 sidecar owner and step 2 run-log helper for failures that have a model reply. Emit the receipt in the same attempt that `_note_stage_attempt_failure` records the existing attempt classification, before control continues to the next attempt.
+
+- **Keep identity tied to the rejected reply.** Derive the receipt’s byte count and digest from the original reply returned by `invoker`, not from lifted artifact text, parser errors, correction text, or `_reply_head`. A non-empty reply attached to a failed invocation remains receipt-eligible; an absent or empty reply must use the shared no-response disposition without inventing content.
+
+- **Cover both parse branches.** `_run_stage` can reject a reply because `_lift_artifact_text` cannot find an artifact or because `stage.parse` raises `RoadmapArtifactError`. Both paths must produce the same parse-kind receipt behavior, while retaining their current correction messages and retry behavior.
+
+- **Treat authored review rows as model failure evidence.** The `FAILURE_AUTHORED_REVIEW_ROWS` branch after `_authored_review_rows(artifact, None)` must produce a receipt for the reply it rejects. Preserve the branch’s current rule: fresh model output cannot create reviewer-owned feedback or removal records.
+
+- **Preserve acce
````

## 39. `arm-clustering-cross-round-consensus|2026-08-12T21:33:43Z|plan-plan-completeness-949233bb`

**Cited step:** 3: Parse the plan once in cmd_convergence instead of inside _current_audit_stage

**Finding (plan-completeness, medium):** `cmd_convergence` (`plan_tool/cli/convergence_cmd.py`) carries the comment "No parsed Plan here, so no map" directly abo

`cmd_convergence` (`plan_tool/cli/convergence_cmd.py`) carries the comment "No parsed Plan here, so no map" directly above its `record_convergence` call, explaining why only `plan_fingerprint` (not a per-file `code_fingerprint` map) is supplied. Step 3 hoists `parse_plan(path)` into `cmd_convergence` itself, so a parsed `Plan` (or `None` on failure) is in scope at exactly that point once step 3 lands — the comment becomes false the moment this step's own change ships. No step revises it: step 3's Files section only names updating "both functions' docstrings" (`cmd_convergence`'s and `_current_audit_stage`'s), not this inline comment; step 4 doesn't touch this file's telemetry block; step 5's doc sweep is scoped to `CLAUDE.md`/`docs/ARCHITECTURE.md`/`docs/AUDIT_FLOW.md`/`BACKLOG.md`, not this source file. This is the same class of stale-comment drift the plan is otherwise careful about (step 2's own docstring fix, step 5's whole purpose), just in a file none of the five steps' doc-accuracy work reaches.

**Suggested action:** have step 3 correct this comment (and sweep `plan_tool/cli/convergence_cmd.py` for any other prose whose truth depends on "cmd_convergence has no parsed Plan") to say a parsed Plan is now available but is deliberately not used to build a `code_fingerprint` map here, rather than leaving a now-false claim in place.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
index f245ca0c..7a8e5205 100644
--- a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
+++ b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
@@ -17,7 +17,7 @@ steps:
     `Recommendation`/`RunFinding` (today it is parsed by `_split_audit_step_evidence`
     and then discarded into a transient in-call structure before a review is saved),
-    then let a material finding earn a consensus step target from that persisted
-    value across separate audit rounds, so arm-clustering has evidence to work with
-    on the --audit-passes 1 runs that give it only one same-execution sample.
+    then let a material finding earn a consensus step target from that persisted value
+    across separate audit rounds, so arm-clustering has evidence to work with on the
+    --audit-passes 1 runs that give it only one same-execution sample.
   files:
   - plan_tool/review.py
@@ -29,4 +29,5 @@ steps:
   complexity: high
   change_type: feature
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/01-build-arm-clustering-consensus-targets.md
   status: current
 - id: 2
@@ -51,9 +52,14 @@ steps:
     1: the classifier function and its advisory record, which diagnose_convergence
       calls and the render lines read fields off
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/02-cross-round-arm-clustering-advisory.md
 - id: 3
   title: Parse the plan once in cmd_convergence instead of inside _current_audit_stage
   intent: Make the parsed plan reachable from cmd_convergence so the next step can
     read its committed steps without parsing the file a second time or copying the
-    best-effort try/except.
+    best-effort try/except. The hoisted `parse_plan` call must keep degrading to `diagnose_convergence`'s
+    pre-stage-bar blanket-blocking defaults on a parse failure or missing plan — the
+    same outcome `_current_audit_stage`'s existing try/except gives today — so `cmd_convergence`'s
+    documented "always exits 0, never surfaces an error" contract survives the move
+    unchanged.
   files:
   - plan_tool/cli/convergence_cmd.py
@@ -61,13 +67,15 @@ steps:
   complexity: low
   change_type: refactor
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/03-parse-plan-once-cmd-convergence-instead.md
 - id: 4
   title: Pass committed step ids to the diagnosis from the convergence and completeness
     surfaces
   intent: Turn the classifier on for real operators by threading real committed step
-    ids *and* each step's current status (step 1's function signature accepts both as
-    parameters — a bare id list alone carries no status, and step 1's done-step drop
-    check needs it — but this step is what supplies real values from the plan's parsed
-    `Step` objects, not step 1) into it from the two places the sibling advisories
-    already print, so `plan-tool convergence` and completeness stderr both surface it.
+    ids *and* each step's current status (step 1's function signature accepts both
+    as parameters — a bare id list alone carries no status, and step 1's done-step
+    drop check needs it — but this step is what supplies real values from the plan's
+    parsed `Step` objects, not step 1) into it from the two places the sibling advisories
+    already print, so `plan-tool convergence` and completeness stderr both surface
+    it.
   files:
   - plan_tool/cli/convergence_cmd.py
@@ -85,4 +93,5 @@ steps:
     3: the parsed plan hoisted into cmd_convergence, so committed step ids come from
       the parse the stage lookup already did
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/04-pass-committed-step-ids-diagnosis.md
 - id: 5
   title: Update the docs for the cross-round advisory and settle the backlog entries
@@ -92,8 +101,8 @@ steps:
     CLAUDE.md''s "cycle-free leaf" bullet and `docs/ARCHITECTURE.md`''s "Convergence
     diagnostic" entry both restate that import set already inaccurately (CLAUDE.md
-    omits `granularity`; both predate this plan and are wrong independent of it), so
-    correct both to the module''s full current set (`review_persistence`, `review`,
-    `locator`, `convergence`, `granularity`) plus the new `audit_shapes` edge step 2
-    adds — not only append the one new edge onto an already-wrong baseline. The
+    omits `granularity`; both predate this plan and are wrong independent of it),
+    so correct both to the module''s full current set (`review_persistence`, `review`,
+    `locator`, `convergence`, `granularity`) plus the new `audit_shapes` edge step
+    2 adds — not only append the one new edge onto an already-wrong baseline. The
     module''s own docstring paragraph is step 2''s fix, made where the import lands,
     not this step''s.'
@@ -110,4 +119,5 @@ steps:
     4: the shipped surfaces and the final import edge, so the docs describe what landed
       rather than what was proposed
+  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/05-update-docs-cross-round-advisory-settle.md
 ---
 # Arm Clustering Cross Round Consensus
@@ -165,16 +175,33 @@ settled precedent, not a gap to redesign.
    Every cross-round consumer this plan builds reads `RunFinding`, not
    `Recommendation`, so missing the second site leaves the field permanently
-   `None` on everything this plan actually consumes. Document both fields in
-   `DATA_CONTRACT.md`. This is the one new piece of persisted state this plan
-   adds; `evaluate_arm_clustering` and the same-execution consensus path are
+   `None` on everything this plan actually consumes. The two fields get two
+   different kinds of documentation, landed in **this same step**, not
+   deferred to step 5's docs pass: `Recommendation.audit_step_target` is
+   persisted/serialized (round-trips via `save_review`), so it gets a row in
+   `DATA_CONTRACT.md`'s existing `Recommendation` table, same as `anchor` or
+   `impact`. `RunFinding` is not persisted on its own — its own docstring
+   calls it a flattening "from a saved report's recommendation list," and
+   `DATA_CONTRACT.md` documents only persisted/serialized schemas, which is
+   why none of `convergence_diagnosis.py`'s other dataclasses have an entry
+   there — so `RunFinding.audit_step_target` is documented inline in
+   `RunFinding`'s own docstring instead, matching how `step_id`, `anchor`, and
+   `impact` are already documented there, not as a new `DATA_CONTRACT.md`
+   section. This is the one new piece of persisted state this plan adds;
+   `evaluate_arm_clustering` and the same-execution consensus path are
    unaffected — they keep reading `observations_by_id` and the transient tag
    directly.
 2. Materiality: treat a matched finding as material via
    `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=…)`
-   checked **only against the newest round's copy** of that finding — the
-   same rule `classify_edit_drift`'s `_edit_drift_eligible` already applies to
-   `RunFinding` objects pulled from history (`convergence_diagnosis.py:885`),
-   and the same newest-round keying point 7 already uses for the output
-   mapping. A finding's severity/impact tag can differ across matched rounds;
+   checked **only against the newest round's copy** of that finding —
+   reusing only the stage-bar half of `classify_edit_drift`'s
+   `_edit_drift_eligible` (`convergence_diagnosis.py:885`), and the same
+   newest-round keying point 7 already uses for the output mapping.
+   `_edit_drift_eligible` also runs a second check —
+   `_is_resolved_in_run(annotations.get(finding.id))`, dropping a finding the
+   operator already declined between rounds — that this plan deliberately
+   does **not** reuse: Out of scope already refuses to gate cross-round
+
````

## 40. `arm-clustering-cross-round-consensus|2026-08-12T19:37:39Z|plan-plan-correctness-e2f2f1c2`

**Cited step:** 4: Pass committed step ids to the diagnosis from the convergence and completeness surfaces

**Finding (plan-correctness, high):** Architecture point 6 requires dropping a consensus target when "the target step's current status is done" — a live look-

Architecture point 6 requires dropping a consensus target when "the target step's current status is done" — a live look-up against each step's status, not id membership. Step 4 is titled "Pass committed step ids to the diagnosis... from the convergence and completeness surfaces," and its own description commits only to feeding "committed step ids," matching `evaluate_arm_clustering`'s existing `declared_step_ids: Sequence[int]` parameter that Architecture point 7 says stays unchanged. Neither step 2 (which owns the new classifier function) nor step 4 (which supplies the plan data) says where the per-step status value the point-6 check needs actually comes from — a bare id list carries no status — and this is exactly the round-3 `stale-done-step-target` gap this plan already fixed once, now left without a stated data source.

**Suggested action:** state in step 4 that the plan data threaded from `cmd_convergence`/completeness surfaces into the classifier carries each committed step's current status alongside its id (e.g. the `Step` objects themselves or an id→status map), not a bare `Sequence[int]`.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
index dc35c926..d82b3756 100644
--- a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
+++ b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
@@ -80,6 +80,10 @@ steps:
   title: Update the docs for the cross-round advisory and settle the backlog entries
   intent: 'Keep the always-injected guidance honest once this ships, so the next session
-    does not read `--audit-passes 1 disables it outright`, the four-import leaf claim,
-    or an open #264 as still true.'
+    does not read `--audit-passes 1 disables it outright`, the four-import leaf claim
+    in CLAUDE.md, `convergence_diagnosis.py`''s own matching "cycle-free leaf" docstring
+    paragraph, or `docs/ARCHITECTURE.md`''s third restatement of the same
+    "review_persistence, review, locator, convergence" import list (all three name the
+    same fact and all three need the same audit_shapes.py import added by step 2), or
+    an open #264 as still true.'
   files:
   - CLAUDE.md
@@ -87,4 +91,5 @@ steps:
   - docs/AUDIT_FLOW.md
   - BACKLOG.md
+  - plan_tool/convergence_diagnosis.py
   complexity: medium
   change_type: non-code
@@ -144,10 +149,14 @@ settled precedent, not a gap to redesign.
    unaffected — they keep reading `observations_by_id` and the transient tag
    directly.
-2. Materiality: treat a saved finding as material via
+2. Materiality: treat a matched finding as material via
    `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=…)`
-   — the same rule `classify_edit_drift`'s `_edit_drift_eligible` already
-   applies to `RunFinding` objects pulled from history
-   (`convergence_diagnosis.py:885`). This is a different, deliberate choice
-   from same-execution arm-clustering's `is_blocking_impact` +
+   checked **only against the newest round's copy** of that finding — the
+   same rule `classify_edit_drift`'s `_edit_drift_eligible` already applies to
+   `RunFinding` objects pulled from history (`convergence_diagnosis.py:885`),
+   and the same newest-round keying point 7 already uses for the output
+   mapping. A finding's severity/impact tag can differ across matched rounds;
+   only the newest round's copy decides materiality, never a mix or an
+   older round's. This is a different, deliberate choice from same-execution
+   arm-clustering's `is_blocking_impact` +
    `build_low_impact_demotion_lookup(repo_root)` (`review.py:7929,7774`),
    which rebuilds a live per-run calibration lookup and was designed for a
@@ -176,8 +185,17 @@ settled precedent, not a gap to redesign.
    targets disagree; a target is missing on some round; a step's renumbering
    breaks target continuity even though the finding still matches by
-   anchor/title; **or** the single agreed target is not among the *current*
-   round's `declared_step_ids` (the step was deferred, marked `wont_do`,
-   deleted, or renumbered since the last matched round). Never guess a target
-   and never pass an unresolved or stale one through.
+   anchor/title; the single agreed target is not among the *current* round's
+   `declared_step_ids` (the step was deferred, marked `wont_do`, deleted, or
+   renumbered since the last matched round); **or** the target step's current
+   `status` is `done`. `declared_step_ids` / `committed_step_ids` is built
+   from `StepScope.COMMITTED` (`completeness_report.py:122`,
+   `review.py:8059`), which is the commitment axis, not the lifecycle axis
+   (`schema.py:StepScope`) — a shipped step stays `scope: committed` and so
+   stays in that list, so list membership alone cannot detect a target that
+   shipped between the matched rounds and a later `plan-tool convergence`
+   read. Check the target step's `status` directly; this plan's own
+   governing rule (a `done` step is "shipped: context, never a target") is
+   how a stale-but-shipped target must be treated here too. Never guess a
+   target and never pass an unresolved or stale one through.
    `evaluate_arm_clustering` returns `None` for the *entire* advisory the
    moment any id in `material_finding_ids` lacks a target inside the
@@ -188,5 +206,21 @@ settled precedent, not a gap to redesign.
    ids), that same resolved-subset `material_finding_ids`, and the newest
    round's committed `declared_step_ids` into `evaluate_arm_clustering`
-   unchanged. The leaf's own gap-free proper-majority-arm math is not touched.
+   unchanged. Two more of the leaf's parameters are not optional in practice
+   and must be supplied, matching same-execution's own call
+   (`review.py:8064-8076`): `material_finding_evidence` — built from the
+   newest round's own `RunFinding.anchor`/`.source` for each resolved id
+   (already-persisted fields, no new plumbing) — since an empty evidence
+   tuple defaults every item to `anchor=None`, which
+   `completeness_report.py`'s renderer (`_advisory_arm_steps`,
+   line ~149-157) skips, leaving the printed arm's finding list empty; and
+   `source_plan_fingerprint` — the plan's *current* fingerprint computed at
+   call time (not a saved round's), matching how same-execution stamps
+   `audit_input_snapshot.fingerprint` and how `completeness_report.py`'s
+   `matches_disk` staleness check consumes it. Leaving either at its
+   signature default (`()` / `""`) is a caller bug, not a valid choice: an
+   empty `source_plan_fingerprint` fails `_is_valid_stored_arm_advisory`'s
+   own non-empty check (`audit_shapes.py:121`) and voids the advisory
+   outright. The leaf's own gap-free proper-majority-arm math is not
+   touched.
 8. When the classifier has nothing to report — including when a previously-
    firing arm's cross-round consensus becomes unresolvable — the render emits
@@ -253,5 +287,5 @@ See the `steps:` block in the frontmatter.
   the field and its `DATA_CONTRACT.md` entry must land in the same step, not
   split across steps 1 and 5.
-- A silent non-fire (Architecture point 7) is easy to misread from the outside
+- A silent non-fire (Architecture point 8) is easy to misread from the outside
   as "the arm resolved" rather than "evidence became unavailable." Acceptance
   criteria settle this as accepted, explicitly-decided behavior rather than a
@@ -260,4 +294,9 @@ See the `steps:` block in the frontmatter.
 - Windowing on the wrong `audit_stage` (mixing bare and detail history) would
   manufacture a consensus target that never coexisted in one coherent audit.
+- `evaluate_arm_clustering`'s `material_finding_evidence` and
+  `source_plan_fingerprint` both default to empty/falsy values that are easy
+  to leave unset by omission rather than by decision — the former silently
+  degrades the render, the latter silently voids the whole advisory. Both are
+  named explicitly in Architecture point 7 so they are supplied by decision.
 
 ## Testing
@@ -266,22 +305,31 @@ Prove: (1) the plan-audit's parsed `[audit-step:N]` tag round-trips onto a
 saved `Recommendation`/`RunFinding` via `save_review`/`resolve_saved_review`,
 documented in `DATA_CONTRACT.md`; (2) materiality for cross-round consensus is
-computed via `is_blocking_finding` (stage-aware, matching
-`classify_edit_drift`'s own use on `RunFinding`s), independent of and not
-required to agree with same-execution's `is_blocking_impact` +
-calibration-lookup materiality; (3) a finding with a stable `_matches` identity
-and one agreeing persisted `audit_step_target` across the 2-round window
-produces a resolved consensus target; (4) a finding whose matched target
-disagrees, is missing on one round, or agrees across the window but is absent
-from the *current* `declared_step_ids` (deferred/`wont_do`/deleted/renumbered
-since the match), is dropped from **both** `consensus_targets` and the
-`material_finding_ids` passed to `evaluate_arm_clustering`, never causing the
-whole advisory to return `None`; (5) a renumbered step that 
````

## 41. `roadmap-revision-retention|2026-08-19T14:56:49Z|plan-plan-correctness-d664dcf3`

**Cited step:** 8: Update BACKLOG #242 and sweep the roadmap gate count and review-collection claims in docs/ARCHITECTURE.md

**Finding (plan-correctness, medium):** Step 8's stated reason for touching `docs/ARCHITECTURE.md` — "the architecture summary stops stating a gate count and a 

Step 8's stated reason for touching `docs/ARCHITECTURE.md` — "the architecture summary stops stating a gate count and a close-by-deleting workflow that are no longer true" — describes a defect that doesn't exist in the file today. Its roadmap paragraph (the `**Roadmap (...)**` block) says "twenty-eight relation gates," which still matches the code (`grep -c "^def check_" plan_tool/roadmap_gates.py` = 28) even after this plan ships, because step 1's tampering and dropped-removal checks are added as branches inside the existing `check_design_row_continuity` function, not as new top-level `check_*` gates — so the count doesn't go stale. A full search of the file for feedback/removal/close language finds no "close-by-deleting" claim anywhere; the only relevant sentence, "feedback rows and their text are the reviewer's," stays true unchanged once `closed` ships.

**Suggested action:** drop the gate-count and close-by-deleting claims from step 8's stated reason for editing `docs/ARCHITECTURE.md`, and if a real update to that file is needed once the new fields/state ship, name the actual sentence it corrects instead.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-revision-retention.md b/docs/implementation-plans/2-roadmap-revision-retention.md
index d7b2a424..c5cd7bdc 100644
--- a/docs/implementation-plans/2-roadmap-revision-retention.md
+++ b/docs/implementation-plans/2-roadmap-revision-retention.md
@@ -15,9 +15,12 @@ steps:
     tampering-specific branch so an edited (not fabricated) carried removal is
     rejected with a message naming the changed field and telling the model to
-    revert it, not drop the record
+    revert it, not drop the record, and add a dropped-removal check mirroring
+    `check_feedback_integrity`'s dropped-feedback loop so a carried removal
+    silently omitted from a reply is rejected too, not just an edited one
   intent: So a reader of a revised roadmap can see what the dropped row actually said
     instead of having to go read git, with no faithfulness question to gate because
-    the render layer derives the snapshot rather than the model paraphrasing it, and
-    so an accidental edit to a carried removal gets a correction the model can act on.
+    the render layer derives the snapshot rather than the model paraphrasing it, an
+    accidental edit to a carried removal gets a correction the model can act on, and
+    a carried removal cannot simply vanish from a reply either.
   files:
   - plan_tool/roadmap_artifacts.py
@@ -74,14 +77,14 @@ steps:
   change_type: feature
 - id: 4
-  title: Add a gate rejecting a revision whose `feedback` collection places a `closed`
-    row before a non-`closed` row, and tell the model in the revision prompt to keep
-    closed rows last when it re-emits the collection
+  title: Add a deterministic, stable closed-last sort to the `feedback` render layer,
+    so any write — model-emitted or a reviewer's own hand-edit later picked up by
+    any tool-driven write — always leaves closed rows after every non-`closed`
+    row, with no gate and no model-facing prompt guidance needed
   intent: So the live part of the review queue reads first and retained closed rows
-    accumulate at the end instead of interleaving with open requests, and the model
-    has the guidance it needs to satisfy the gate on the first attempt.
+    accumulate at the end instead of interleaving with open requests, guaranteed
+    unconditionally rather than only when the model happens to emit rows in order.
   files:
-  - plan_tool/roadmap_gates.py
-  - plan_tool/prompts/roadmap-revision.md
-  - tests/test_roadmap_gates.py
+  - plan_tool/roadmap_artifacts.py
+  - tests/test_roadmap_artifacts.py
   - tests/test_roadmap.py
   complexity: medium
@@ -93,13 +96,17 @@ steps:
       nothing to order last until closed rows can exist.
 - id: 5
-  title: 'Count closed rows in both roadmap summary renderers — `_feedback_summary_lines`
-    (cli/roadmap_cmd.py, the run/revision post-run summary) and `_summary_feedback_counts`
-    / `render_roadmap_summary` (roadmap_view.py, the `--view summary` surface step
-    6 renames to `--mode history`) — and tell the operator to close by setting
-    `state: closed` rather than by deleting'
+  title: 'Count closed rows in the `--mode history` summary (`_summary_feedback_counts`
+    / `render_roadmap_summary`, roadmap_view.py) and update the post-run summary''s
+    close guidance (`_feedback_summary_lines`, cli/roadmap_cmd.py) to say closing
+    sets `state: closed` rather than deleting — the post-run summary reports no
+    per-state counts today (`RoadmapResult` has no closed accumulator, only the
+    scalar `feedback_awaiting_review`) and adding one would touch the `run_roadmap`
+    orchestrator, out of scope per BACKLOG #242, so it keeps reporting only that
+    existing scalar'
   intent: So the two hand-written state lists an operator actually reads stop disagreeing
-    with the state vocabulary the parser accepts, on both the post-run summary and
-    the renamed `--mode history` view whose whole rationale is surfacing retained
-    history.
+    with the state vocabulary the parser accepts — fully on the renamed `--mode
+    history` view, whose whole rationale is surfacing retained history, and on the
+    post-run summary's guidance text without touching the orchestrator to add a
+    count it doesn't have today.
   files:
   - plan_tool/roadmap_view.py
@@ -125,5 +132,10 @@ steps:
     retain history rather than only pending review work, and no operator-facing
     text anywhere — including the top-level `plan-tool --help` catalog — still
-    tells someone to pass a value the parser now rejects.
+    tells someone to pass a value the parser now rejects. This sweep is scoped to
+    the roadmap `--view ... --mode {current,review}` flag only — `run --mode
+    <review>` / `verify-all --mode <m>`'s unrelated per-step audit primitive
+    (check/optimize/document/test/security/lint) shares no code and stays
+    untouched even where it appears near this flag's own documentation in the
+    same files.
   files:
   - plan_tool/roadmap_view.py
@@ -144,20 +156,30 @@ steps:
 - id: 7
   title: Document the removal snapshot, the decision reference, and the `closed` state
-    (including the closed-last ordering rule) in ROADMAP_FORMAT.md — correcting all
-    three existing "no `closed` member" sites (the schema block's `state` comment,
-    the Closed vocabularies table, and the feedback-lifecycle's situation 5) rather
-    than adding fresh prose beside them — correct RUNBOOK.md's close-request table
-    row and "Preserved by the gates" tables to match, and add a feedback-state
-    vocabulary-completeness test to tests/test_roadmap_format.py mirroring
+    (including the closed-last ordering rule) in ROADMAP_FORMAT.md, describing
+    both setting `state` to `closed` and the still-valid plain-deletion path
+    rather than replacing one with the other — correcting all five sites that
+    currently say deletion is the only close (the schema block's `state`
+    comment, the Closed vocabularies table, the feedback-lifecycle's situation
+    5, the worked example near "## Decisions", and
+    `check_feedback_integrity`'s gate-documentation table row,
+    which also needs "or `closed`" added to its "carried in `awaiting-review` or
+    `deferred`" language) — correct RUNBOOK.md's close-request table row the same
+    dual-option way, plus its "Preserved by the gates" table, and correct README.md's
+    and docs/ROADMAP_WALKTHROUGH.md's close-by-deleting prose to name both options
+    too — and add a feedback-state vocabulary-completeness test to
+    tests/test_roadmap_format.py mirroring
     `test_hosting_schema_documents_the_complete_gate_owned_vocabulary` /
     `test_store_schema_documents_the_complete_gate_owned_vocabulary`, since no such
     guard exists today for FeedbackState
   intent: So the review collections' schema is readable without opening the parser,
-    which is what the whole FORMAT-doc family exists to guarantee, and so a reviewer
-    who trusts RUNBOOK.md's walkthrough learns the retention path exists instead of
-    being told deletion is still the only way to close a request.
+    which is what the whole FORMAT-doc family exists to guarantee, so a reviewer
+    who trusts RUNBOOK.md, README.md, or the walkthrough learns the retention path
+    exists without losing the still-valid deletion option, and so the two most-read
+    operator docs stop contradicting the shipped `closed` state.
   files:
   - ROADMAP_FORMAT.md
   - RUNBOOK.md
+  - README.md
+  - docs/ROADMAP_WALKTHROUGH.md
   - tests/test_roadmap_format.py
   complexity: high
@@ -288,4 +310,21 @@ the near-match message telling the model to revert the edited field, not
 drop the record.
 
+**A carried removal record must survive a revision the same way a carried
+feedback row must — today nothing enforces that.**
+`check_design_row_continuity` only validates removals *present* in the
+candidate against `carried`; it never loops over `predecessor.removals` the
+way `check_feedback_integrity` 
````

## 42. `security-check-command|2026-06-17T02:07:13Z|plan-plan-completeness-e9c2f6e8`

**Cited step:** 4: Add security-reconcile ReconcileKind + run_auto_reconcile_on_drift hook and teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add the dispatch branch) wired to it for plan⇆code security drift, and construct the standalone full plan⇄code surface drift scope (every step and its declared files in scope) so security --reconcile runs on a tree with no recorded file drift — synthesize that whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every step's declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift's in-memory int / per-step findings output (with its per-step security-reconcile.json persistence suppressed so write_security_report is the sole on-disk writer) back into a SecurityAuditResult so step 3's cmd_security can render result.findings and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(..., target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile; the reconcile family uses resolve_saved_review in review_persistence

**Finding (plan-completeness, medium):** Step 4 adds a `security-reconcile` row to `_RECONCILE_KINDS` "so the saved-reconcile recognition family isolates `-secur

Step 4 adds a `security-reconcile` row to `_RECONCILE_KINDS` "so the saved-reconcile recognition family isolates `-security-reconcile.json` from the detail/run kinds," but reconcile reuse keys on `resolve_reusable_security` (not `resolve_reusable_reconcile`) and the per-step `save_review` is suppressed — and the existing `detail-reconcile`/`run-reconcile` `name_includes` filters (`-detail-reconcile`/`-run-reconcile`) already cannot match `-security-reconcile`, so no consumer of `_RECONCILE_KINDS` clearly reads the new row. It may be dead config.

**Suggested action:** name the recognition path that would otherwise mis-grab the security sidecar, or drop the row as unnecessary.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index 4fcd07cd..4166446e 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -13,4 +13,6 @@ steps:
   - plan_tool/prompts/security-plan.md
   - tests/test_security_audit.py
+  allowed_mentions:
+  - plan_tool/prompts/security.md
   complexity: high
   change_type: feature
@@ -20,12 +22,12 @@ steps:
   status: current
 - id: 2
-  title: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json persistence
-    (sibling of resolve_reusable_audit); scope reuse by target (plan vs code) via the
-    filename suffix as well as fingerprint so a plan-axis caller never reuses a code-axis
-    report or vice versa (per-target scoping lands here, not deferred); a target="plan"
-    save verdicts fresh on an unchanged plan fingerprint alone — do NOT gate plan-target
-    freshness on saved.code_fingerprint_present (that code-fingerprint staleness gate from
-    resolve_reusable_audit applies only to the code/reconcile targets), so step 5's
-    plan-fingerprint reuse engages instead of verdicting stale every run
+  title: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json
+    persistence (sibling of resolve_reusable_audit); scope reuse by target (plan vs
+    code) via the filename suffix as well as fingerprint so a plan-axis caller never
+    reuses a code-axis report or vice versa (per-target scoping lands here, not deferred);
+    a target="plan" save verdicts fresh on an unchanged plan fingerprint alone — do
+    NOT gate plan-target freshness on saved.code_fingerprint_present (that code-fingerprint
+    staleness gate from resolve_reusable_audit applies only to the code/reconcile
+    targets)
   files:
   - plan_tool/security_audit.py
@@ -38,7 +40,7 @@ steps:
 - id: 3
   title: 'Register security subcommand (cli/security_cmd.py: --target plan|code, --reconcile,
-    --fail-on-findings) across all five registration seams, wiring resolve_reusable_security
-    into cmd_security so --target code reuses a saved report on a fingerprint hit; --target
-    code requires --step (single-step audit)'
+    --fail-on-findings) across all five registration seams; reuse-prompt wiring of
+    resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
+    --target code requires --step (single-step audit)'
   files:
   - plan_tool/cli/app.py
@@ -58,14 +60,17 @@ steps:
   detail: docs/implementation-plans/plan-details/security-check-command/03-register-security-subcommand-cli.md
 - id: 4
-  title: 'Add security-reconcile ReconcileKind + run_auto_reconcile_on_drift hook and
-    teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add the
-    dispatch branch) wired to it for plan⇆code security drift, and construct the standalone
-    full plan⇄code surface drift scope (every step and its declared files in scope) so
-    security --reconcile runs on a tree with no recorded file drift — synthesize that
-    whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every
-    step''s declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift''s
-    in-memory int / per-step findings output (with its per-step security-reconcile.json persistence
-    suppressed so write_security_report is the sole on-disk writer) back into a SecurityAuditResult so
-    step 3''s cmd_security can render result.findings and persist via write_security_report'
+  title: Add security-reconcile ReconcileKind + run_auto_reconcile_on_drift hook and
+    teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add
+    the dispatch branch) wired to it for plan⇆code security drift, and construct the
+    standalone full plan⇄code surface drift scope (every step and its declared files
+    in scope) so security --reconcile runs on a tree with no recorded file drift —
+    synthesize that whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map
+    over every step's declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift's
+    in-memory int / per-step findings output (with its per-step security-reconcile.json
+    persistence suppressed so write_security_report is the sole on-disk writer) back
+    into a SecurityAuditResult so step 3's cmd_security can render result.findings
+    and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(...,
+    target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
+    the reconcile family uses resolve_saved_review in review_persistence
   files:
   - plan_tool/cli/reconcile.py
@@ -77,4 +82,7 @@ steps:
   creates:
   - plan_tool/prompts/security-reconcile.md
+  allowed_mentions:
+  - plan_tool/prompts/detail-reconcile.md
+  - plan_tool/prompts/security.md
   complexity: medium
   change_type: feature
@@ -84,30 +92,37 @@ steps:
   detail: docs/implementation-plans/plan-details/security-check-command/04-security-reconcile-reconcilekind-run.md
 - id: 5
-  title: 'Wire security dimension into completeness: conceptual-layer call + route
-    security_recs through the existing findings-summarization/rollup gate before
-    rendering + grouped-report section + JSON security bucket + emit a `security --reconcile`
-    advisory pointer on code-only drift (cached `<ts>-security-plan.json` reused, not re-sampled)
-    (the completeness --iterate loop firing of
-    run_auto_reconcile_on_drift with mode="security" that operationalizes the step 4
-    drift-retrigger hook is deferred to a dedicated follow-up step, not wired here)'
+  title: Emit a relevance-gated `plan-tool security` next-step pointer at the end
+    of `detail` and `completeness` — NOT a security dimension inside completeness.
+    Append a suggestion line via the existing _print_next_steps helper (cli/console.py)
+    in cli/authoring.py:cmd_detail (after the existing review/run/jira Next-steps
+    block) and in cli/completeness_phases.py:_persist_and_present_report (both the
+    --iterate summary path and the audit-only path). Completeness does NOT invoke
+    run_security_audit, render a Security section in _render_grouped_report, or add
+    a security bucket to _render_completeness_json — security stays a standalone command
+    the pointer advertises. Unconditional emission lands here; step 6 adds the relevance
+    gate
   files:
+  - plan_tool/cli/authoring.py
   - plan_tool/cli/completeness_phases.py
-  - plan_tool/cli/completeness_cmd.py
-  - tests/test_cli.py
+  - tests/cli/test_authoring.py
   - tests/cli/test_completeness_cmd.py
-  complexity: high
+  allowed_mentions:
+  - tests/cli/test_authoring_cmds.py
+  complexity: medium
   change_type: feature
   depends_on:
-  - 1
-  - 2
-  - 4
-  detail: docs/implementation-plans/plan-details/security-check-command/05-wire-security-dimension-completeness.md
+  - 3
+  detail: docs/implementation-plans/plan-details/security-check-command/05-emit-relevance-gated-plan-tool-security.md
 - id: 6
-  title: Add cost relevance gate + --with-security flag controlling whether the completeness
-    security dimension runs
+  title: Add a cheap, no-Claude relevance gate (keyword scan of plan title + step
+    titles + declared file paths) that decides whether the step-5 next-step pointer
+    is shown, plus a --no-security-hint suppression flag. A wrong verdict only shows
+    or hides a one-line suggestion (no Claude spend either way), so the gate is low-stakes
+    — it gates the pointer, never an audit pass
   files:
+  - plan_tool/cli/authoring.py
   - plan_tool/cli/completeness_phases.py
-  - plan_tool/cli/completeness_cmd.py
   - plan_tool/cli/parser.py
+  - plan_tool/security_audit.py
   - tests/cli/test_completeness_cmd.py
   complexity: medium
@@ -115,8 +130,11 @@ steps:
   depends_on:
   - 5
-  detail: docs
````

## 43. `roadmap-revision-rollback|2026-09-18T17:33:34Z|plan-plan-completeness-f7dd4947`

**Cited step:** 2: Move run_roadmap's confirmed brief rebind write of source.json to after recover_roadmap_publication (today it runs before), so recover_roadmap_publication always runs first; then take the checkpoint right before its first write, that rebind write included, keep an earlier failed run's checkpoint and its pre-run bytes, verify each tracked file's current bytes against the checkpoint's last-tracked value before writing it and refuse the run on a mismatch, update the last-written bytes after each stage publish and each source.json write, and delete the checkpoint only when the run completes (including a no-change run); a run refused before any write creates none, and existing stage publishes and journal cleanup stay unchanged

**Finding (plan-completeness, medium):** The checkpoint's write-time verification (step 2) is wired only into `_run_roadmap`'s stage-run path, but `seed-state.js

The checkpoint's write-time verification (step 2) is wired only into `_run_roadmap`'s stage-run path, but `seed-state.json` — one of the ten tracked inventory files — is also written by three other roadmap actions dispatched straight from `cmd_roadmap` before the stage-run code ever runs: `refresh_roadmap_seeds` (`--refresh-seeds`), `_accept_roadmap_seed` (`--accept-seed`), and `apply_roadmap_seeds` (`--apply`), each calling `_write_roadmap_seed_state` directly. None of these three actions appears in the plan's Scope guardrails' "No change to `--revise-feedback`, `--materialize`, `--enroll-baselines`, or `--enroll-version`" list, and the plan's Risk section frames the "another writer's change" hazard only as "a later hand edit" or something "outside this tool's own generation history" — it never considers an ordinary, same-tool seed action running between two attempts of the same failed revision. Nothing appears to be actually broken here: the whole-vector bytes comparison in step 3's restore matrix, and the write-time check in step 2, would both treat the seed action's change to `seed-state.json` the same as any other unexpected change and refuse rather than silently overwrite it. But that refusal also discards the legitimate `--refresh-seeds`/`--accept-seed`/`--apply` work along with the failed run's own restore/retry, and no test in either step 2's or step 3's roster exercises this specific, plausible-in-practice sequence (retry a failed roadmap revision, or restore it, after running one of these three seed actions).

**Suggested action:** Name `--refresh-seeds`, `--accept-seed`, and `--apply` as legitimate other writers of the tracked `seed-state.json` file in the plan's Risk section, and add one test (to step 2's or step 3's roster) proving that a seed action's write between two runs of the same checkpoint lineage is caught by the existing mismatch check and refuses safely rather than being folded into the next write.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-revision-rollback.md b/docs/implementation-plans/2-roadmap-revision-rollback.md
index fa555a2c..4ed21871 100644
--- a/docs/implementation-plans/2-roadmap-revision-rollback.md
+++ b/docs/implementation-plans/2-roadmap-revision-rollback.md
@@ -27,22 +27,22 @@ steps:
   complexity: medium
   change_type: feature
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/01-roadmap-revision-checkpoint-file-that.md
   status: current
 - id: 2
-  title: Move run_roadmap's confirmed brief rebind write of source.json to after
-    recover_roadmap_publication (today it runs before), so recover_roadmap_publication
-    always runs first; then take the checkpoint right before its first write, that
-    rebind write included, keep an earlier failed run's checkpoint and its pre-run
-    bytes, verify each tracked file's current bytes against the checkpoint's
-    last-tracked value before writing it and refuse the run on a mismatch, update
-    the last-written bytes after each stage publish and each source.json write,
-    and delete the checkpoint only when the run completes (including a no-change
-    run); a run refused before any write creates none, and existing stage
-    publishes and journal cleanup stay unchanged
-  intent: Makes a checkpoint that still exists mean exactly that a run did not
-    complete, makes it hold the roadmap state from before the first of any
-    consecutive failed runs, keeps a later run in the same checkpoint's lineage
-    from silently building its own next write on top of a change the checkpoint
-    never tracked, and closes the one case today -- the confirmed brief rebind --
-    where recovery does not yet run before the run's first tracked write.
+  title: Move run_roadmap's confirmed brief rebind write of source.json to after recover_roadmap_publication
+    (today it runs before), so recover_roadmap_publication always runs first; then
+    take the checkpoint right before its first write, that rebind write included,
+    keep an earlier failed run's checkpoint and its pre-run bytes, verify each tracked
+    file's current bytes against the checkpoint's last-tracked value before writing
+    it and refuse the run on a mismatch, update the last-written bytes after each
+    stage publish and each source.json write, and delete the checkpoint only when
+    the run completes (including a no-change run); a run refused before any write
+    creates none, and existing stage publishes and journal cleanup stay unchanged
+  intent: Makes a checkpoint that still exists mean exactly that a run did not complete,
+    makes it hold the roadmap state from before the first of any consecutive failed
+    runs, keeps a later run in the same checkpoint's lineage from silently building
+    its own next write on top of a change the checkpoint never tracked, and closes
+    the one case today -- the confirmed brief rebind -- where recovery does not yet
+    run before the run's first tracked write.
   files:
   - plan_tool/roadmap.py
@@ -54,4 +54,5 @@ steps:
   depends_on_notes:
     1: the checkpoint record, its path, and its write/update/discard operations
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/02-move-run-roadmap-confirmed-brief-rebind.md
 - id: 3
   title: 'Add the revision restore runner: under the writer lock, run recover_roadmap_publication
@@ -77,4 +78,5 @@ steps:
     2: real stage runs that leave a checkpoint after an invalid, exhausted, interrupted,
       or crashed run, for the end-to-end restore-then-re-run cases
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/03-revision-restore-runner-under-writer.md
 - id: 4
   title: Add the paired restore and confirm options to plan-tool roadmap, exclusive
@@ -94,16 +96,16 @@ steps:
     3: the restore runner and its outcome/refusal result the CLI dispatches to and
       renders
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/04-paired-restore-confirm-options-plan.md
 - id: 5
-  title: Name the restore command, when a checkpoint exists, at all four of
-    cmd_roadmap's disconnected outcome paths -- the RoadmapResult-based
-    invalid/exhausted branch that already reaches _print_invalid/_print_exhausted,
-    the except (OSError, RoadmapEnvironmentalError) branch that today only calls
-    error() and returns _RC_INCOMPLETE, the except (RoadmapError, RoadmapArtifactError,
-    RoadmapWriterGuardError) branch that today only calls error() and returns
-    _RC_USAGE, and the except KeyboardInterrupt branch that today only prints
-    "interrupted" -- and never after a completed run
-  intent: Tells the operator of a run that did not complete that a restore is
-    available and exactly how to invoke it, at every path a run can end
-    without completing, not only the two that already produce a RoadmapResult.
+  title: Name the restore command, when a checkpoint exists, at all four of cmd_roadmap's
+    disconnected outcome paths -- the RoadmapResult-based invalid/exhausted branch
+    that already reaches _print_invalid/_print_exhausted, the except (OSError, RoadmapEnvironmentalError)
+    branch that today only calls error() and returns _RC_INCOMPLETE, the except (RoadmapError,
+    RoadmapArtifactError, RoadmapWriterGuardError) branch that today only calls error()
+    and returns _RC_USAGE, and the except KeyboardInterrupt branch that today only
+    prints "interrupted" -- and never after a completed run
+  intent: Tells the operator of a run that did not complete that a restore is available
+    and exactly how to invoke it, at every path a run can end without completing,
+    not only the two that already produce a RoadmapResult.
   files:
   - plan_tool/cli/roadmap_cmd.py
@@ -117,4 +119,5 @@ steps:
     2: the checkpoint that exists exactly when a run did not complete
     4: the restore and confirm option names the message must print
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/05-name-restore-command-when-checkpoint.md
 - id: 6
   title: 'Document the checkpoint file and the restore route and its refusal matrix
@@ -122,8 +125,7 @@ steps:
     checkpoint list/clear''s create/detail authoring cache, and remove BACKLOG.md
     #394 once the route ships and its tests pass'
-  intent: Makes the restore route discoverable from the operator docs, keeps an
-    operator from conflating this checkpoint with the unrelated plan-tool
-    checkpoint list/clear subcommand family, and closes the backlog entry it
-    discharges.
+  intent: Makes the restore route discoverable from the operator docs, keeps an operator
+    from conflating this checkpoint with the unrelated plan-tool checkpoint list/clear
+    subcommand family, and closes the backlog entry it discharges.
   files:
   - ROADMAP_FORMAT.md
@@ -145,4 +147,5 @@ steps:
     4: the shipped option names the operator docs cite
     5: the closing-message pointer the how-to and runbook describe
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/06-document-checkpoint-file-restore-route.md
 ---
 # Roadmap Revision Rollback
diff --git a/docs/implementation-plans/plan-details/roadmap-revision-rollback/02-move-run-roadmap-confirmed-brief-rebind.md b/docs/implementation-plans/plan-details/roadmap-revision-rollback/02-move-run-roadmap-confirmed-brief-rebind.md
new file mode 100644
index 00000000..e71a7f22
--- /dev/null
+++ b/docs/implementation-plans/plan-details/roadmap-revision-rollback/02-move-run-roadmap-confirmed-brief-rebind.md
@@ -0,0 +1,137 @@
+# Step 2 — Move the confirmed brief rebind write after publication recovery, and wire the revision checkpoint into every roadmap run
+
+<!-- plan-tool:detail-format-version: 1 -->
+
+## Summary
+
+`_run_roadmap` in `plan_tool/roadmap.py` writes `source.json` for a confirmed brief rebind (the `confirm_brief_rebind` branch, before `parse_carried_decisions`) before it ever calls `rec
````

## 44. `roadmap-decision-settlement|2026-09-18T03:30:15Z|plan-plan-correctness-2376291f`

**Cited step:** 3: Add the immutable settlement receipt record and its own evidence namespace in plan_tool/roadmap_evidence_store.py, naming the exact resulting content digest settlement is about to produce; publication stays create-once and keyed on its own inputs so a retry resolves to the same already-published final, an existing final is returned rather than overwritten, and nothing is deleted

**Finding (plan-correctness, high):** The plan never places the receipt's commit to `HEAD` in the write order, and never says what a failed commit does to the

The plan never places the receipt's commit to `HEAD` in the write order, and never says what a failed commit does to the settlement, so steps 3 and 4 can ship materially different behavior. The plan says both:

  ```
  The receipt is created **first**
  ```

  ```
  It carries
  the same `created`/`reused`/`committed-existing` versus
  `commit-failed`/`collision` outcomes escalation receipts already define.
  ```

  It does not say whether the commit comes before or after the artifact or accepted-head write, or whether `commit-failed`, `collision`, or a store failure stops the settlement. The escalation precedent is `roadmap_escalation_run.py:run_roadmap_escalation_receipt`. It refuses up front when the roadmap is not inside a Git worktree (`receipt_worktree_for_plans_dir`), and its outcomes also include `storage-rejected` and `invalid-existing-receipt`. None of these appears in Testing's refusal list, which calls itself "the canonical, complete list of preflight and publication refusals". If the write goes ahead after a failed commit, the criterion "A receipt is committed to `HEAD`, is created before the canonical write it proves" is false for that settlement. If the write stops instead, the "complete" list is missing refusals. Affected sites:
  - Architecture "Receipt, written before the canonical write, never after";
  - step 3's title and intent;
  - step 4's title ("publishing its receipt first");
  - Testing's receipt paragraph and its refusal list;
  - the receipt acceptance criterion.

**Suggested action:** Pick one order and one failure rule, and state them. The escalation precedent fits: commit the receipt before any canonical write, and let every receipt outcome other than `created`, `reused`, or `committed-existing` stop the settlement before that write, including a missing Git worktree. Then name those outcomes in Testing's refusal list, or in a separate receipt-outcome list, and in the receipt acceptance criterion.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index 39e715c5..80ac1b1b 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -137,11 +137,19 @@ steps:
 - id: 6
   title: Add the decision selector, evidence selector, and required confirm flag to
-    plan-tool roadmap as one exclusive action, reject them alongside every other roadmap
-    option, and regenerate docs/cli/roadmap.md
+    plan-tool roadmap as one exclusive action (missing-confirm and companion-option
+    refusals named, matching --reopen-feedback's confirmation-required/mode-rejected
+    precedent), regenerate docs/cli/roadmap.md, and prove both lineages produce the
+    same settled row and that check_settled_decisions refuses drift on an un-enrolled
+    settled row this route just settled
   intent: Give the operator the actual command, with the confirm flag that makes settlement
-    their decision rather than the tool's, and no backend call anywhere on the path.
+    their decision rather than the tool's and no backend call anywhere on the path,
+    then show the enrolled and un-enrolled paths are one capability rather than two
+    look-alikes by asserting identical before/after row content across both — proving
+    only the un-enrolled drift refusal, not any claim about the enrolled lineage, which
+    step 7's docs disclose separately.
   files:
   - plan_tool/cli/roadmap_cmd.py
   - tests/cli/test_roadmap_cmd.py
+  - tests/test_roadmap_gates.py
   - docs/cli/roadmap.md
   complexity: medium
@@ -155,31 +163,17 @@ steps:
       head
 - id: 7
-  title: Prove both lineages produce the same settled row and that check_settled_decisions
-    refuses drift on an un-enrolled settled row this route just settled
-  intent: Show the enrolled and un-enrolled paths are one capability rather than two
-    look-alikes, by asserting identical before/after row content across both, and
-    prove only what these test files can actually demonstrate — the un-enrolled drift
-    refusal, not any claim about the enrolled lineage, which step 8's docs disclose
-    separately.
-  files:
-  - tests/cli/test_roadmap_cmd.py
-  - tests/test_roadmap_gates.py
-  complexity: medium
-  change_type: non-code
-  depends_on:
-  - 6
-  depends_on_notes:
-    6: the single command entry both lineages are driven through end to end
-- id: 8
   title: Document the settlement route; retire every live hand-edit settlement instruction
-    (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md,
-    integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md, docs/how-to/roadmap.md);
-    state that --revise-feedback still cannot change status; correct ROADMAP_FORMAT.md's
-    Decision status paragraph and gate-table row plus CAPABILITIES.md's accepted-head-authority
-    statement to name both guarded writers and confine the drift-protection claim to
-    the un-enrolled lineage, updating tests/test_roadmap_format.py's pinning test to
-    match; extend the "Incomplete immutable lifecycle journals" BUG_BACKLOG.md entry
-    to name the new settlement generation shape(s); and remove the settlement
-    BUG_BACKLOG.md entry now that the capability ships
+    (README.md, docs/how-to/common-workflows.md, docs/how-to/roadmap-demo.md, RUNBOOK.md,
+    docs/how-to/use-cases.md, integrations/shared/DIRECTIVES.md, ROADMAP_FORMAT.md,
+    docs/how-to/roadmap.md); state that --revise-feedback still cannot change status;
+    correct ROADMAP_FORMAT.md's Immutable candidate-version authority block and
+    CAPABILITIES.md's accepted-head-authority statement to name both guarded writers,
+    updating tests/test_roadmap_format.py::test_candidate_policy_reference_keeps_review_inert_until_exact_promotion
+    to match, and separately correct the Decision status paragraph and gate-table row
+    to confine the drift-protection claim to the un-enrolled lineage; add the settlement
+    receipt as a third EvidenceNamespace in docs/ARCHITECTURE.md; extend the "Incomplete
+    immutable lifecycle journals" BUG_BACKLOG.md entry to name the new settlement
+    generation shape(s); and remove the settlement BUG_BACKLOG.md entry now that the
+    capability ships
   intent: Leave one honest account of how a decision is settled and which lineage's
     settled decisions are actually protected from later drift, so no reader is still
@@ -192,4 +186,7 @@ steps:
   - docs/how-to/common-workflows.md
   - docs/how-to/roadmap-demo.md
+  - RUNBOOK.md
+  - docs/how-to/use-cases.md
+  - docs/ARCHITECTURE.md
   - integrations/shared/DIRECTIVES.md
   - CLAUDE.md
@@ -201,9 +198,7 @@ steps:
   depends_on:
   - 6
-  - 7
   depends_on_notes:
-    6: the shipped flag names and refusal messages the docs describe, read off the
-      landed parser rather than off this plan
-    7: the passing cross-lineage proof that makes removing the backlog entry honest
+    6: the shipped flag names, refusal messages, and cross-lineage proof the docs
+      describe, read off the landed parser and tests rather than off this plan
 ---
 # Roadmap Decision Settlement
@@ -241,8 +236,16 @@ helper regardless; `check_settled_decisions`
 (`plan_tool/roadmap_gates.py`) already refuses a *settled* decision's id,
 status, chosen option, or anchor from drifting; it does not, and must not
-start to, gate `pending → settled` itself. Nothing today reaches `settled`
-except a hand-edit (un-enrolled) or authoring a full model candidate through
-propose → review → promote (enrolled) — both bypass the operator-confirmed,
-evidence-bound shape every other narrow roadmap action already has.
+start to, gate `pending → settled` itself. `settled` is not rare today: the
+domain stage prompt instructs "Use `settled` otherwise" for a decision the
+brief already resolves, so ordinary model-authored stage authoring is the
+dominant route; an ordinary un-enrolled revision can newly settle a decision
+too (`ROADMAP_FORMAT.md` lists "decisions the revision newly settled" as
+expected run residue); a candidate proposal on an enrolled roadmap can
+already change a decision's `status`, including to `settled`, as ordinary
+delta content; and a hand-edit remains the only way an *operator* flips an
+existing `pending` row today. None of these is operator-confirmed and
+evidence-bound the way every other narrow roadmap action already is — that
+absence, not the absence of any route to `settled` at all, is this plan's
+actual gap.
 
 ## Architecture
@@ -333,4 +336,28 @@ evidence-bound shape every other narrow roadmap action already has.
   A stage with no recorded baseline refuses rather than settlement silently
   creating one from unadmitted bytes.
+
+  Baseline admission alone does not prove the source is in the parser's
+  exact rendered form: `admit_baseline_backed_source` compares only
+  `canonical_projection`, a semantic digest that ignores exact bytes.
+  Settlement also requires a render-canonical check —
+  `roadmap_escalation_selection.py:canonical_artifact_snapshot`, the same
+  distinction `--reopen-feedback` (`source-not-canonical`) and
+  `--revise-feedback` (`preflight_feedback_revision`'s
+  `RenderCanonicalMismatch`) already enforce — and refuses a non-canonical
+  source under its own named reason, never silently rewriting bytes outside
+  the selected row to make it canonical. The common trigger is an operator
+  hand-filling the `_NO_FEEDBACK_KEY_COMMENT` stub to write the very
+  feedback row settlement will cite: that file is non-canonical until its
+  owning stage is re-run with `--from-stage`, which an operator must do
+  before the evidence becomes citable.
+- **Enrolled non-canonical bytes are a standing, permanent limitation, not
+  a repair target.** `roadmap_versions.py:prepare_root_version_from_snapshot`
+  captures on-disk text with no render-canonical check, so an accepted
+  version can hold non-c
````

## 45. `arm-clustering-cross-round-consensus|2026-08-12T19:37:39Z|plan-plan-correctness-7c833cdf`

**Cited step:** 1: Build arm-clustering consensus targets from saved audit history

**Finding (plan-correctness, high):** The Risks section claims "A new field on `Recommendation`/`RunFinding` round-trips through generic `asdict` / `Recommend

The Risks section claims "A new field on `Recommendation`/`RunFinding` round-trips through generic `asdict` / `Recommendation(**r)` serialization automatically" — checked against the code, that is true only for `Recommendation`. `RunFinding` is never built by `asdict`/`Recommendation(**r)`; it is built field-by-field by `convergence_diagnosis.py`'s `_finding_from_recommendation`, which the module's own docstring calls a deliberate "persisted-field whitelist" and which copies `id`, `source`, `severity`, `impact`, `step_id`, `anchor`, `title`, `purity_verdict_provenance`, `redirect_present`, `domain` one at a time — nothing about it is generic. Architecture point 1 also names only one edit site ("the same parse site" in `review.py`) for both classes. Every cross-round consumer this plan builds (steps 1, 2, 4) reads `RunFinding`, not `Recommendation`, from history, so skipping `_finding_from_recommendation` leaves `audit_step_target` saving and reloading fine on `Recommendation` while staying permanently `None` on every `RunFinding` — silently failing Testing criterion (1)'s round-trip claim at that hop.

**Suggested action:** correct the Risks claim to say `RunFinding` needs its own explicit edit, and name `_finding_from_recommendation` (add `audit_step_target=rec.audit_step_target` to its `RunFinding(...)` construction) as a required site in Architecture point 1.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
index dc35c926..d82b3756 100644
--- a/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
+++ b/docs/implementation-plans/2-arm-clustering-cross-round-consensus.md
@@ -80,6 +80,10 @@ steps:
   title: Update the docs for the cross-round advisory and settle the backlog entries
   intent: 'Keep the always-injected guidance honest once this ships, so the next session
-    does not read `--audit-passes 1 disables it outright`, the four-import leaf claim,
-    or an open #264 as still true.'
+    does not read `--audit-passes 1 disables it outright`, the four-import leaf claim
+    in CLAUDE.md, `convergence_diagnosis.py`''s own matching "cycle-free leaf" docstring
+    paragraph, or `docs/ARCHITECTURE.md`''s third restatement of the same
+    "review_persistence, review, locator, convergence" import list (all three name the
+    same fact and all three need the same audit_shapes.py import added by step 2), or
+    an open #264 as still true.'
   files:
   - CLAUDE.md
@@ -87,4 +91,5 @@ steps:
   - docs/AUDIT_FLOW.md
   - BACKLOG.md
+  - plan_tool/convergence_diagnosis.py
   complexity: medium
   change_type: non-code
@@ -144,10 +149,14 @@ settled precedent, not a gap to redesign.
    unaffected — they keep reading `observations_by_id` and the transient tag
    directly.
-2. Materiality: treat a saved finding as material via
+2. Materiality: treat a matched finding as material via
    `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=…)`
-   — the same rule `classify_edit_drift`'s `_edit_drift_eligible` already
-   applies to `RunFinding` objects pulled from history
-   (`convergence_diagnosis.py:885`). This is a different, deliberate choice
-   from same-execution arm-clustering's `is_blocking_impact` +
+   checked **only against the newest round's copy** of that finding — the
+   same rule `classify_edit_drift`'s `_edit_drift_eligible` already applies to
+   `RunFinding` objects pulled from history (`convergence_diagnosis.py:885`),
+   and the same newest-round keying point 7 already uses for the output
+   mapping. A finding's severity/impact tag can differ across matched rounds;
+   only the newest round's copy decides materiality, never a mix or an
+   older round's. This is a different, deliberate choice from same-execution
+   arm-clustering's `is_blocking_impact` +
    `build_low_impact_demotion_lookup(repo_root)` (`review.py:7929,7774`),
    which rebuilds a live per-run calibration lookup and was designed for a
@@ -176,8 +185,17 @@ settled precedent, not a gap to redesign.
    targets disagree; a target is missing on some round; a step's renumbering
    breaks target continuity even though the finding still matches by
-   anchor/title; **or** the single agreed target is not among the *current*
-   round's `declared_step_ids` (the step was deferred, marked `wont_do`,
-   deleted, or renumbered since the last matched round). Never guess a target
-   and never pass an unresolved or stale one through.
+   anchor/title; the single agreed target is not among the *current* round's
+   `declared_step_ids` (the step was deferred, marked `wont_do`, deleted, or
+   renumbered since the last matched round); **or** the target step's current
+   `status` is `done`. `declared_step_ids` / `committed_step_ids` is built
+   from `StepScope.COMMITTED` (`completeness_report.py:122`,
+   `review.py:8059`), which is the commitment axis, not the lifecycle axis
+   (`schema.py:StepScope`) — a shipped step stays `scope: committed` and so
+   stays in that list, so list membership alone cannot detect a target that
+   shipped between the matched rounds and a later `plan-tool convergence`
+   read. Check the target step's `status` directly; this plan's own
+   governing rule (a `done` step is "shipped: context, never a target") is
+   how a stale-but-shipped target must be treated here too. Never guess a
+   target and never pass an unresolved or stale one through.
    `evaluate_arm_clustering` returns `None` for the *entire* advisory the
    moment any id in `material_finding_ids` lacks a target inside the
@@ -188,5 +206,21 @@ settled precedent, not a gap to redesign.
    ids), that same resolved-subset `material_finding_ids`, and the newest
    round's committed `declared_step_ids` into `evaluate_arm_clustering`
-   unchanged. The leaf's own gap-free proper-majority-arm math is not touched.
+   unchanged. Two more of the leaf's parameters are not optional in practice
+   and must be supplied, matching same-execution's own call
+   (`review.py:8064-8076`): `material_finding_evidence` — built from the
+   newest round's own `RunFinding.anchor`/`.source` for each resolved id
+   (already-persisted fields, no new plumbing) — since an empty evidence
+   tuple defaults every item to `anchor=None`, which
+   `completeness_report.py`'s renderer (`_advisory_arm_steps`,
+   line ~149-157) skips, leaving the printed arm's finding list empty; and
+   `source_plan_fingerprint` — the plan's *current* fingerprint computed at
+   call time (not a saved round's), matching how same-execution stamps
+   `audit_input_snapshot.fingerprint` and how `completeness_report.py`'s
+   `matches_disk` staleness check consumes it. Leaving either at its
+   signature default (`()` / `""`) is a caller bug, not a valid choice: an
+   empty `source_plan_fingerprint` fails `_is_valid_stored_arm_advisory`'s
+   own non-empty check (`audit_shapes.py:121`) and voids the advisory
+   outright. The leaf's own gap-free proper-majority-arm math is not
+   touched.
 8. When the classifier has nothing to report — including when a previously-
    firing arm's cross-round consensus becomes unresolvable — the render emits
@@ -253,5 +287,5 @@ See the `steps:` block in the frontmatter.
   the field and its `DATA_CONTRACT.md` entry must land in the same step, not
   split across steps 1 and 5.
-- A silent non-fire (Architecture point 7) is easy to misread from the outside
+- A silent non-fire (Architecture point 8) is easy to misread from the outside
   as "the arm resolved" rather than "evidence became unavailable." Acceptance
   criteria settle this as accepted, explicitly-decided behavior rather than a
@@ -260,4 +294,9 @@ See the `steps:` block in the frontmatter.
 - Windowing on the wrong `audit_stage` (mixing bare and detail history) would
   manufacture a consensus target that never coexisted in one coherent audit.
+- `evaluate_arm_clustering`'s `material_finding_evidence` and
+  `source_plan_fingerprint` both default to empty/falsy values that are easy
+  to leave unset by omission rather than by decision — the former silently
+  degrades the render, the latter silently voids the whole advisory. Both are
+  named explicitly in Architecture point 7 so they are supplied by decision.
 
 ## Testing
@@ -266,22 +305,31 @@ Prove: (1) the plan-audit's parsed `[audit-step:N]` tag round-trips onto a
 saved `Recommendation`/`RunFinding` via `save_review`/`resolve_saved_review`,
 documented in `DATA_CONTRACT.md`; (2) materiality for cross-round consensus is
-computed via `is_blocking_finding` (stage-aware, matching
-`classify_edit_drift`'s own use on `RunFinding`s), independent of and not
-required to agree with same-execution's `is_blocking_impact` +
-calibration-lookup materiality; (3) a finding with a stable `_matches` identity
-and one agreeing persisted `audit_step_target` across the 2-round window
-produces a resolved consensus target; (4) a finding whose matched target
-disagrees, is missing on one round, or agrees across the window but is absent
-from the *current* `declared_step_ids` (deferred/`wont_do`/deleted/renumbered
-since the match), is dropped from **both** `consensus_targets` and the
-`material_finding_ids` passed to `evaluate_arm_clustering`, never causing the
-whole advisory to return `None`; (5) a renumbered step that 
````

## 46. `security-check-command|2026-06-20T21:11:54Z|plan-plan-correctness-96a4a472`

**Cited step:** 4: Add a security-reconcile run_auto_reconcile_on_drift hook and teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add the dispatch branch) wired to it for plan⇆code security drift, and construct the standalone full plan⇄code surface drift scope (every step and its declared files in scope) so security --reconcile runs on a tree with no recorded file drift — synthesize that whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every step's declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift's in-memory int / per-step findings output (with its per-step security-reconcile.json persistence suppressed so write_security_report is the sole on-disk writer) back into a SecurityAuditResult so step 3's cmd_security can render result.findings and persist via write_security_report; because the generalized hook's best-effort loop skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit) and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default — so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(..., target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile; the reconcile family uses resolve_saved_review in review_persistence

**Finding (plan-correctness, medium):** Step 4's `prompts/security-reconcile.md` is mandated to mirror `detail-reconcile.md`'s "exact `## Findings` block contra

Step 4's `prompts/security-reconcile.md` is mandated to mirror `detail-reconcile.md`'s "exact `## Findings` block contract" (detail line 26/80), and that contract emits a trailing `

**Suggested action:** …` line per bullet (confirmed in `detail-reconcile.md`). But `extract_reconcile_recommendations` only strips `→ fix:` when `source in _RECONCILE_FIX_SOURCES` (`review.py:3085`), and step 4 keeps `source="security-reconcile"` **out** of every apply-eligible set — so `parse_fix` resolves `False` and the `→ fix:` text is never split off, leaking into each reconcile finding's `body` and the title derived from `body.splitlines()[0]`. Neither the body nor step 4's detail addresses whether security-reconcile findings carry a fix line or how it is stripped. → fix: state in step 4 whether `security-reconcile` findings carry `→ fix:` and, if so, how the line is stripped from the body/title (e.g. force `parse_fix=True` for the security extraction) so remediation text never leaks into the finding body.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index f1c5187f..32c7f146 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -47,5 +47,10 @@ steps:
     --fail-on-findings) across all five registration seams; reuse-prompt wiring of
     resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
-    --target code requires --step (single-step audit)'
+    --target code requires --step (single-step audit), and --step is rejected at
+    parse time when combined with --reconcile (usage error, non-zero rc — the reconcile
+    direction is whole-plan full-surface, so a single --step is meaningless against it);
+    cmd_security renders
+    result.skipped_steps alongside the findings so a partial reconcile sweep (step 4)
+    is reported as partial, not as a clean pass'
   files:
   - plan_tool/cli/app.py
@@ -75,5 +80,9 @@ steps:
     persistence suppressed so write_security_report is the sole on-disk writer) back
     into a SecurityAuditResult so step 3's cmd_security can render result.findings
-    and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(...,
+    and persist via write_security_report; because the generalized hook's best-effort loop
+    skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel
+    to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit)
+    and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default —
+    so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(...,
     target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
     the reconcile family uses resolve_saved_review in review_persistence
@@ -255,5 +264,5 @@ Security is **already a per-step review mode**, but only at the per-step level:
 ## Architecture
 
-A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`.
+A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`. **`--step` is rejected at parse time when combined with `--reconcile`** (a usage error, non-zero rc, never dispatching): the reconcile direction derives its scope from the full plan⇄code surface (every step and its declared files), so a single `--step` is meaningless against it — `plan-tool security --reconcile --step <id> <name>` is an error, not a one-step reconcile, keeping the whole-plan full-surface contract unambiguous. `--step` remains required for `--target code` (single-step audit) and unused for `--target plan`.
 
 A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit` reuse pattern. Because `target="plan"`, `target="code"`, and `target="reconcile"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json` vs `-security-reconcile.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a `--target code` caller can never resolve a `target="plan"` save, nor vice versa — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa. Beyond the target suffix, the **`target="code"` axis must additionally scope its lookup by `step_id`**: the `-security-code.json` suffix encodes only the target, not the step, so two steps' code audits write same-suffix sidecars — `resolve_reusable_security` for the code target must therefore key on `step_id` (mirroring the reconcile family's per-step `_find_saved_for_step`), not return the newest target-suffix sidecar (the whole-plan `resolve_reusable_audit` shape it is otherwise cloned from), or it would serve one step's saved code audit to a different step's caller. **`resolve_reusable_security` ships dormant in this plan:** step 2 builds it and step 3 writes the `<ts>-security-<target>.json` sidecar, but **no in-plan step reads the resolver** — the reuse-prompt wiring that would short-circuit a Claude call on an unchanged fingerprint is deferred to a follow-up for all three targets (see `## Deferred`). The persistence/lookup machinery lands write-ready so the follow-up only adds the consumer; this plan does not claim a reuse short-circuit it does not deliver.
@@ -261,5 +270,5 @@ A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by generalizing the `run_auto_reconcile_on_drift` hook (`auto_reconcile.py`) to audit plan-stated security intent against the code's actual security posture under a `mode="security-reconcile"` prompt and emit drift findings, so a code change since the last security audit re-triggers it. **No `security-reconcile` row is added to `cli/reconcile.py:_RECONCILE_KINDS`** — it would be dead config: the existing `detail-reconcile` / `run-reconcile` `name_includes` suffixes are substring-disjoint from `-security-reconcile`, so they already cannot mis-grab a security sidecar, and no production caller queries `resolve_reusable_reconc
````

## 47. `security-check-command|2026-06-20T21:11:54Z|plan-plan-correctness-58ec398a`

**Cited step:** 4: Add a security-reconcile run_auto_reconcile_on_drift hook and teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add the dispatch branch) wired to it for plan⇆code security drift, and construct the standalone full plan⇄code surface drift scope (every step and its declared files in scope) so security --reconcile runs on a tree with no recorded file drift — synthesize that whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map over every step's declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift's in-memory int / per-step findings output (with its per-step security-reconcile.json persistence suppressed so write_security_report is the sole on-disk writer) back into a SecurityAuditResult so step 3's cmd_security can render result.findings and persist via write_security_report; because the generalized hook's best-effort loop skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit) and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default — so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(..., target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile; the reconcile family uses resolve_saved_review in review_persistence

**Finding (plan-correctness, medium):** Step 4 (`security-reconcile` target) frames `security --reconcile` as whole-plan plan⇄code drift ("the plan's stated sec

Step 4 (`security-reconcile` target) frames `security --reconcile` as whole-plan plan⇄code drift ("the plan's stated security intent against the code's actual posture", "detecting a plan that states an authz step the code lacks"), but its engine `run_auto_reconcile_on_drift` issues one per-step Claude call scoped to that step's declared files via `build_file_to_step_map`. A security gap that spans steps, or one requiring a step that does not exist (an unprotected code surface no plan step covers), has no step to be audited against and is structurally invisible to the sweep — the per-step audit can confirm a declared step's code matches its stated intent but cannot surface a missing-step or cross-cutting concern. The "plan-wide" framing oversells what N independent per-step audits deliver.

**Suggested action:** scope the reconcile goal and its acceptance criterion to per-step intent-vs-code divergence only, stating explicitly that missing-step/cross-cutting security surface is not detected by this sweep

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index f1c5187f..32c7f146 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -47,5 +47,10 @@ steps:
     --fail-on-findings) across all five registration seams; reuse-prompt wiring of
     resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
-    --target code requires --step (single-step audit)'
+    --target code requires --step (single-step audit), and --step is rejected at
+    parse time when combined with --reconcile (usage error, non-zero rc — the reconcile
+    direction is whole-plan full-surface, so a single --step is meaningless against it);
+    cmd_security renders
+    result.skipped_steps alongside the findings so a partial reconcile sweep (step 4)
+    is reported as partial, not as a clean pass'
   files:
   - plan_tool/cli/app.py
@@ -75,5 +80,9 @@ steps:
     persistence suppressed so write_security_report is the sole on-disk writer) back
     into a SecurityAuditResult so step 3's cmd_security can render result.findings
-    and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(...,
+    and persist via write_security_report; because the generalized hook's best-effort loop
+    skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel
+    to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit)
+    and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default —
+    so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(...,
     target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
     the reconcile family uses resolve_saved_review in review_persistence
@@ -255,5 +264,5 @@ Security is **already a per-step review mode**, but only at the per-step level:
 ## Architecture
 
-A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`.
+A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`. **`--step` is rejected at parse time when combined with `--reconcile`** (a usage error, non-zero rc, never dispatching): the reconcile direction derives its scope from the full plan⇄code surface (every step and its declared files), so a single `--step` is meaningless against it — `plan-tool security --reconcile --step <id> <name>` is an error, not a one-step reconcile, keeping the whole-plan full-surface contract unambiguous. `--step` remains required for `--target code` (single-step audit) and unused for `--target plan`.
 
 A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit` reuse pattern. Because `target="plan"`, `target="code"`, and `target="reconcile"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json` vs `-security-reconcile.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a `--target code` caller can never resolve a `target="plan"` save, nor vice versa — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa. Beyond the target suffix, the **`target="code"` axis must additionally scope its lookup by `step_id`**: the `-security-code.json` suffix encodes only the target, not the step, so two steps' code audits write same-suffix sidecars — `resolve_reusable_security` for the code target must therefore key on `step_id` (mirroring the reconcile family's per-step `_find_saved_for_step`), not return the newest target-suffix sidecar (the whole-plan `resolve_reusable_audit` shape it is otherwise cloned from), or it would serve one step's saved code audit to a different step's caller. **`resolve_reusable_security` ships dormant in this plan:** step 2 builds it and step 3 writes the `<ts>-security-<target>.json` sidecar, but **no in-plan step reads the resolver** — the reuse-prompt wiring that would short-circuit a Claude call on an unchanged fingerprint is deferred to a follow-up for all three targets (see `## Deferred`). The persistence/lookup machinery lands write-ready so the follow-up only adds the consumer; this plan does not claim a reuse short-circuit it does not deliver.
@@ -261,5 +270,5 @@ A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by generalizing the `run_auto_reconcile_on_drift` hook (`auto_reconcile.py`) to audit plan-stated security intent against the code's actual security posture under a `mode="security-reconcile"` prompt and emit drift findings, so a code change since the last security audit re-triggers it. **No `security-reconcile` row is added to `cli/reconcile.py:_RECONCILE_KINDS`** — it would be dead config: the existing `detail-reconcile` / `run-reconcile` `name_includes` suffixes are substring-disjoint from `-security-reconcile`, so they already cannot mis-grab a security sidecar, and no production caller queries `resolve_reusable_reconc
````

## 48. `roadmap-decision-settlement|2026-09-18T02:46:54Z|plan-plan-correctness-042e636d`

**Cited step:** 3: Add the immutable settlement receipt record and its own evidence namespace in plan_tool/roadmap_evidence_store.py, naming the exact resulting content digest settlement is about to produce; publication stays create-once and keyed on its own inputs so a retry resolves to the same already-published final, an existing final is returned rather than overwritten, and nothing is deleted

**Finding (plan-correctness, medium):** Steps 3 (settlement receipt record), 4 and 5 never say whether the settlement receipt is committed to git, and the two p

Steps 3 (settlement receipt record), 4 and 5 never say whether the settlement receipt is committed to git, and the two precedents the plan names do opposite things. Architecture "Receipt" says:

  ```
  publishes one durable, immutable, create-once record — following the
  existing immutable-evidence pattern already used for escalation and
  impact-analysis receipts, not a new ad hoc log — naming the artifact key,
  ```

  - **Escalation receipts:** `roadmap_escalation_run.py` stores the final and then commits only that file to `HEAD` through `cli/gitcommit.py:commit_receipt`. `ROADMAP_FORMAT.md` trusts an escalation receipt only after that commit, with `created`, `reused` and `committed-existing` versus `commit-failed` and `collision` outcomes.
  - **Impact analyses:** stay local. `.gitignore` excludes `**/.plan-tool/evidence/impact-analyses/` as "local runtime evidence".

  Each reading changes what the command does:
  - **Committed:** settlement makes a git commit holding only the receipt, while the settled artifact stays an uncommitted working-tree change. It also needs commit-failure and collision outcomes the plan never lists.
  - **Local and ignored:** the receipt never travels with the artifact ("Artifacts are committed docs"), so the after-the-fact proof exists only on the machine that ran the settlement.
  - **Neither:** the new namespace shows up as untracked files.

  Sites: Architecture "Receipt" bullet; step 3 (new namespace in `roadmap_evidence_store.py`); steps 4 and 5; step 8's docs; the receipt acceptance criterion.

**Suggested action:** State whether the settlement receipt is committed to `HEAD` (the escalation shape, with its commit outcomes) or kept as ignored local evidence (the impact-analysis shape). Assign the chosen git or `.gitignore` behavior to its owning step, and have step 8 and the receipt acceptance criterion reflect it.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-decision-settlement.md b/docs/implementation-plans/2-roadmap-decision-settlement.md
index 8f8f0d5b..39e715c5 100644
--- a/docs/implementation-plans/2-roadmap-decision-settlement.md
+++ b/docs/implementation-plans/2-roadmap-decision-settlement.md
@@ -31,12 +31,16 @@ steps:
 - id: 2
   title: Add a decision-settlement preflight leaf that resolves the decision target,
-    its feedback evidence, and the predecessor digest — reading enrolled content from
-    the accepted version, not on-disk stage files — with one named refusal per rejection
-    class
+    matches feedback evidence to it by FeedbackTargetKind.ROW/row_id rather than just
+    resolving the feedback id, accepts any FeedbackState, requires un-enrolled baseline
+    admission before reading the source, and computes the predecessor digest — reading
+    enrolled content from the accepted version, not on-disk stage files — with one
+    named refusal per rejection class
   intent: Prove, before any write, that exactly one live Roadmap-derived pending decision
-    was named, that a named live feedback row carries non-empty reviewer-authored
-    `request` text (never model-authored `proposed_response`), and that the source
-    bytes (on-disk artifact for an un-enrolled roadmap, accepted-version bytes for
-    an enrolled one) have not moved since the evidence was read.
+    was named, that a named live feedback row actually targets it (not just resolves)
+    and carries non-empty reviewer-authored `request` text in any FeedbackState (never
+    model-authored `proposed_response`), that an un-enrolled source is admitted against
+    its recorded baseline, and that the source bytes (on-disk artifact for an un-enrolled
+    roadmap, accepted-version bytes for an enrolled one) have not moved since the
+    evidence was read.
   creates:
   - plan_tool/roadmap_decision_settlement.py
@@ -51,9 +55,13 @@ steps:
 - id: 3
   title: Add the immutable settlement receipt record and its own evidence namespace
-    in plan_tool/roadmap_evidence_store.py; publication stays create-once, so an existing
-    final is returned rather than overwritten and nothing is deleted
-  intent: Make every successful settlement leave a durable, readable record of which
-    artifact, decision, predecessor digest, and feedback evidence justified it, so
-    the approval can be proven after the fact.
+    in plan_tool/roadmap_evidence_store.py, naming the exact resulting content digest
+    settlement is about to produce; publication stays create-once and keyed on its
+    own inputs so a retry resolves to the same already-published final, an existing
+    final is returned rather than overwritten, and nothing is deleted
+  intent: Make every successful settlement leave a durable, readable record — written
+    before the row-level write it proves, never after — of which artifact, decision,
+    predecessor digest, feedback evidence, and resulting content digest justify it,
+    so the approval can be proven after the fact and a receipt never outlives or
+    outraces the settlement it names.
   files:
   - plan_tool/roadmap_evidence_store.py
@@ -70,5 +78,6 @@ steps:
       recorded facts
 - id: 4
-  title: Settle one decision on an un-enrolled roadmap and publish its receipt through
+  title: Settle one decision on an un-enrolled roadmap by publishing its receipt first,
+    then, once source admission and staleness both hold, publishing through
     publish_stage_artifact's multi-member generation with invalidate_seeds=False,
     keeping the existing journal recovery (roll back or drop an in-flight generation)
@@ -77,5 +86,6 @@ steps:
     and after
   intent: Let an operator settle an approved decision on an ordinary roadmap by naming
-    it, naming its evidence, and confirming — with no hand-edit of a canonical artifact.
+    it, naming its evidence, and confirming — with no hand-edit of a canonical artifact,
+    and with a receipt that always precedes the write it proves.
   files:
   - plan_tool/roadmap_revision_publish.py
@@ -90,21 +100,24 @@ steps:
   - 3
   depends_on_notes:
-    2: the preflight candidate and its final staleness recheck, called inside the
-      writer lease before the artifact is replaced
-    3: the receipt record published once the artifact write lands
+    2: the preflight candidate, its source-admission check, and its final staleness
+      recheck, called inside the writer lease before the artifact is replaced
+    3: the receipt writer, called before the artifact write, not after
 - id: 5
   title: Settle one decision on an enrolled roadmap by storing the settled artifact
     bytes as an ordinary version_kind candidate record — via create_candidate_version,
-    with a new dedicated no-review sentinel in place of INITIAL_EMPTY_REVIEW_LINEAGE_ID
-    and no candidate_evidence_path/replacement_evidence_path entries — then advancing
-    the accepted head through a new additive PendingGeneration.kind recovery branch
-    that reuses promote_review_seal's writer-token/journal selector-swap but never
-    calls _load_complete_sealed_candidate or either evidence loader; refuses an
-    in-flight pending generation; root-enrollment and review-seal-promotion recovery
-    stay exactly as they are, and stored version members are never overwritten or
-    deleted
-  intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one
-    without ever editing its accepted head in place, without fabricating a synthetic
-    model-authored candidate/review/seal chain or evidence file to satisfy
+    with a new dedicated no-review sentinel in place of INITIAL_EMPTY_REVIEW_LINEAGE_ID,
+    a settlement-owned content_identity, and no candidate_evidence_path/replacement_evidence_path
+    entries — then advancing the accepted head through a new additive PendingGeneration.kind
+    recovery branch that reuses promote_review_seal's writer-token/journal selector-swap
+    but never calls _load_complete_sealed_candidate or either evidence loader; refuses
+    an in-flight pending generation and an admitted, unpromoted candidate lineage whose
+    predecessor is the current accepted head; root-enrollment and review-seal-promotion
+    recovery stay exactly as they are, and stored version members are never overwritten
+    or deleted
+  intent: Give an enrolled roadmap the same settlement outcome as an un-enrolled one,
+    for a decision whose approving feedback already exists in the accepted version
+    (nothing can add feedback to an enrolled roadmap today), without ever editing its
+    accepted head in place, without fabricating a synthetic model-authored
+    candidate/review/seal chain, evidence file, or content_identity to satisfy
     promote_review_seal's existing preconditions, and without any accepted-head write
     path outside the guarded selector swap.
@@ -142,11 +155,11 @@ steps:
       head
 - id: 7
-  title: Prove both lineages produce the same settled row, that check_settled_decisions
-    refuses drift on an un-enrolled settled row, and document that the same protection
-    does not yet exist on the enrolled lineage (tracked separately in BUG_BACKLOG.md)
+  title: Prove both lineages produce the same settled row and that check_settled_decisions
+    refuses drift on an un-enrolled settled row this route just settled
   intent: Show the enrolled and un-enrolled paths are one capability rather than two
     look-alikes, by asserting identical before/after row content across both, and
-    state plainly rather than silently which lineage's settled decisions are actually
-    protected from later drift.
+    prove only what these test files can actually demonstrate — the un-enrolled drift
+    refusal, not any claim about the enrolled lineage, which step 8's docs disclose
+    separately.
   files:
   - tests/cli/test_roadmap_cmd.py
@@ -159,15 +172,28 @@ steps:
     6: the single command entry both lineages are driven throug
````

## 49. `security-check-command|2026-06-20T21:11:54Z|plan-plan-correctness-426cbc90`

**Cited step:** 1: Add security_audit.py orchestrator + plan-level prompt + shell_security_invoker seam

**Finding (plan-correctness, medium):** Step 1 (`security_audit.py:_security_recommendations`) and step 4 (`security-reconcile` target) normalize an authored `L

Step 1 (`security_audit.py:_security_recommendations`) and step 4 (`security-reconcile` target) normalize an authored `LOW` finding to different stored severities. Step 1 only keeps `LOW`/`NIT` "out of the blocking band" (leaving a non-blocking `low`), while step 4 mandates mapping `LOW`→`"nit"` at parse time. The same input `LOW` therefore carries `low` on `--target plan`/`code` and `nit` on `--reconcile`, so a user reading or severity-filtering findings sees an inconsistent badge for identical severity; rc is unaffected (both non-blocking), only the rendered token diverges.

**Suggested action:** pin one canonical non-blocking normalization (e.g. `LOW`→`nit` on all three targets) so the displayed severity is target-independent.

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-security-check-command.md b/docs/implementation-plans/2-security-check-command.md
index f1c5187f..32c7f146 100644
--- a/docs/implementation-plans/2-security-check-command.md
+++ b/docs/implementation-plans/2-security-check-command.md
@@ -47,5 +47,10 @@ steps:
     --fail-on-findings) across all five registration seams; reuse-prompt wiring of
     resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
-    --target code requires --step (single-step audit)'
+    --target code requires --step (single-step audit), and --step is rejected at
+    parse time when combined with --reconcile (usage error, non-zero rc — the reconcile
+    direction is whole-plan full-surface, so a single --step is meaningless against it);
+    cmd_security renders
+    result.skipped_steps alongside the findings so a partial reconcile sweep (step 4)
+    is reported as partial, not as a clean pass'
   files:
   - plan_tool/cli/app.py
@@ -75,5 +80,9 @@ steps:
     persistence suppressed so write_security_report is the sole on-disk writer) back
     into a SecurityAuditResult so step 3's cmd_security can render result.findings
-    and persist via write_security_report. Reconcile reuse keys on resolve_reusable_security(...,
+    and persist via write_security_report; because the generalized hook's best-effort loop
+    skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel
+    to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit)
+    and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default —
+    so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(...,
     target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
     the reconcile family uses resolve_saved_review in review_persistence
@@ -255,5 +264,5 @@ Security is **already a per-step review mode**, but only at the per-step level:
 ## Architecture
 
-A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`.
+A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`. **`--step` is rejected at parse time when combined with `--reconcile`** (a usage error, non-zero rc, never dispatching): the reconcile direction derives its scope from the full plan⇄code surface (every step and its declared files), so a single `--step` is meaningless against it — `plan-tool security --reconcile --step <id> <name>` is an error, not a one-step reconcile, keeping the whole-plan full-surface contract unambiguous. `--step` remains required for `--target code` (single-step audit) and unused for `--target plan`.
 
 A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit` reuse pattern. Because `target="plan"`, `target="code"`, and `target="reconcile"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json` vs `-security-reconcile.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a `--target code` caller can never resolve a `target="plan"` save, nor vice versa — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa. Beyond the target suffix, the **`target="code"` axis must additionally scope its lookup by `step_id`**: the `-security-code.json` suffix encodes only the target, not the step, so two steps' code audits write same-suffix sidecars — `resolve_reusable_security` for the code target must therefore key on `step_id` (mirroring the reconcile family's per-step `_find_saved_for_step`), not return the newest target-suffix sidecar (the whole-plan `resolve_reusable_audit` shape it is otherwise cloned from), or it would serve one step's saved code audit to a different step's caller. **`resolve_reusable_security` ships dormant in this plan:** step 2 builds it and step 3 writes the `<ts>-security-<target>.json` sidecar, but **no in-plan step reads the resolver** — the reuse-prompt wiring that would short-circuit a Claude call on an unchanged fingerprint is deferred to a follow-up for all three targets (see `## Deferred`). The persistence/lookup machinery lands write-ready so the follow-up only adds the consumer; this plan does not claim a reuse short-circuit it does not deliver.
@@ -261,5 +270,5 @@ A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full
 The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.
 
-Reconcile is added by generalizing the `run_auto_reconcile_on_drift` hook (`auto_reconcile.py`) to audit plan-stated security intent against the code's actual security posture under a `mode="security-reconcile"` prompt and emit drift findings, so a code change since the last security audit re-triggers it. **No `security-reconcile` row is added to `cli/reconcile.py:_RECONCILE_KINDS`** — it would be dead config: the existing `detail-reconcile` / `run-reconcile` `name_includes` suffixes are substring-disjoint from `-security-reconcile`, so they already cannot mis-grab a security sidecar, and no production caller queries `resolve_reusable_reconc
````

## 50. `roadmap-revision-rollback|2026-09-18T17:33:34Z|plan-plan-correctness-a406225d`

**Cited step:** 2: Move run_roadmap's confirmed brief rebind write of source.json to after recover_roadmap_publication (today it runs before), so recover_roadmap_publication always runs first; then take the checkpoint right before its first write, that rebind write included, keep an earlier failed run's checkpoint and its pre-run bytes, verify each tracked file's current bytes against the checkpoint's last-tracked value before writing it and refuse the run on a mismatch, update the last-written bytes after each stage publish and each source.json write, and delete the checkpoint only when the run completes (including a no-change run); a run refused before any write creates none, and existing stage publishes and journal cleanup stay unchanged

**Finding (plan-correctness, medium):** Step 2's Implementation opens with a sentence that asserts two opposite things about where `recover_roadmap_publication`

Step 2's Implementation opens with a sentence that asserts two opposite things about where `recover_roadmap_publication` ends up relative to `parse_carried_decisions`:

```
Move the actual `_write_brief_source` call ... to run **after**
`recover_roadmap_publication` succeeds, while leaving `recover_roadmap_publication`
itself where it already sits relative to `parse_carried_decisions` and
`reject_direct_artifact_deletions` — move `recover_roadmap_publication`'s own
call earlier, to before `parse_carried_decisions`, so it becomes unconditional
for every surviving admission
```

The first clause claims no change in position relative to `parse_carried_decisions` (today recovery runs after it); the second clause, in the same sentence, says to move it before `parse_carried_decisions`. The rest of the section (the ordered bullet list, and the explicit requirement that `parse_carried_decisions` stay "positioned exactly where it is today relative to the write — after it") makes the second clause the one actually meant, so this resolves on a careful read — but an implementer skimming only this opening sentence could keep recovery in its current position and break the "recover_roadmap_publication always runs first" invariant the plan's Architecture section states.

**Suggested action:** Delete the incorrect "leaving `recover_roadmap_publication` itself where it already sits relative to `parse_carried_decisions`" clause, keeping only the "move it earlier, to before `parse_carried_decisions`" instruction (its position relative to `reject_direct_artifact_deletions` is what stays unchanged).

**Prior edit:**

````diff
diff --git a/docs/implementation-plans/2-roadmap-revision-rollback.md b/docs/implementation-plans/2-roadmap-revision-rollback.md
index fa555a2c..4ed21871 100644
--- a/docs/implementation-plans/2-roadmap-revision-rollback.md
+++ b/docs/implementation-plans/2-roadmap-revision-rollback.md
@@ -27,22 +27,22 @@ steps:
   complexity: medium
   change_type: feature
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/01-roadmap-revision-checkpoint-file-that.md
   status: current
 - id: 2
-  title: Move run_roadmap's confirmed brief rebind write of source.json to after
-    recover_roadmap_publication (today it runs before), so recover_roadmap_publication
-    always runs first; then take the checkpoint right before its first write, that
-    rebind write included, keep an earlier failed run's checkpoint and its pre-run
-    bytes, verify each tracked file's current bytes against the checkpoint's
-    last-tracked value before writing it and refuse the run on a mismatch, update
-    the last-written bytes after each stage publish and each source.json write,
-    and delete the checkpoint only when the run completes (including a no-change
-    run); a run refused before any write creates none, and existing stage
-    publishes and journal cleanup stay unchanged
-  intent: Makes a checkpoint that still exists mean exactly that a run did not
-    complete, makes it hold the roadmap state from before the first of any
-    consecutive failed runs, keeps a later run in the same checkpoint's lineage
-    from silently building its own next write on top of a change the checkpoint
-    never tracked, and closes the one case today -- the confirmed brief rebind --
-    where recovery does not yet run before the run's first tracked write.
+  title: Move run_roadmap's confirmed brief rebind write of source.json to after recover_roadmap_publication
+    (today it runs before), so recover_roadmap_publication always runs first; then
+    take the checkpoint right before its first write, that rebind write included,
+    keep an earlier failed run's checkpoint and its pre-run bytes, verify each tracked
+    file's current bytes against the checkpoint's last-tracked value before writing
+    it and refuse the run on a mismatch, update the last-written bytes after each
+    stage publish and each source.json write, and delete the checkpoint only when
+    the run completes (including a no-change run); a run refused before any write
+    creates none, and existing stage publishes and journal cleanup stay unchanged
+  intent: Makes a checkpoint that still exists mean exactly that a run did not complete,
+    makes it hold the roadmap state from before the first of any consecutive failed
+    runs, keeps a later run in the same checkpoint's lineage from silently building
+    its own next write on top of a change the checkpoint never tracked, and closes
+    the one case today -- the confirmed brief rebind -- where recovery does not yet
+    run before the run's first tracked write.
   files:
   - plan_tool/roadmap.py
@@ -54,4 +54,5 @@ steps:
   depends_on_notes:
     1: the checkpoint record, its path, and its write/update/discard operations
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/02-move-run-roadmap-confirmed-brief-rebind.md
 - id: 3
   title: 'Add the revision restore runner: under the writer lock, run recover_roadmap_publication
@@ -77,4 +78,5 @@ steps:
     2: real stage runs that leave a checkpoint after an invalid, exhausted, interrupted,
       or crashed run, for the end-to-end restore-then-re-run cases
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/03-revision-restore-runner-under-writer.md
 - id: 4
   title: Add the paired restore and confirm options to plan-tool roadmap, exclusive
@@ -94,16 +96,16 @@ steps:
     3: the restore runner and its outcome/refusal result the CLI dispatches to and
       renders
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/04-paired-restore-confirm-options-plan.md
 - id: 5
-  title: Name the restore command, when a checkpoint exists, at all four of
-    cmd_roadmap's disconnected outcome paths -- the RoadmapResult-based
-    invalid/exhausted branch that already reaches _print_invalid/_print_exhausted,
-    the except (OSError, RoadmapEnvironmentalError) branch that today only calls
-    error() and returns _RC_INCOMPLETE, the except (RoadmapError, RoadmapArtifactError,
-    RoadmapWriterGuardError) branch that today only calls error() and returns
-    _RC_USAGE, and the except KeyboardInterrupt branch that today only prints
-    "interrupted" -- and never after a completed run
-  intent: Tells the operator of a run that did not complete that a restore is
-    available and exactly how to invoke it, at every path a run can end
-    without completing, not only the two that already produce a RoadmapResult.
+  title: Name the restore command, when a checkpoint exists, at all four of cmd_roadmap's
+    disconnected outcome paths -- the RoadmapResult-based invalid/exhausted branch
+    that already reaches _print_invalid/_print_exhausted, the except (OSError, RoadmapEnvironmentalError)
+    branch that today only calls error() and returns _RC_INCOMPLETE, the except (RoadmapError,
+    RoadmapArtifactError, RoadmapWriterGuardError) branch that today only calls error()
+    and returns _RC_USAGE, and the except KeyboardInterrupt branch that today only
+    prints "interrupted" -- and never after a completed run
+  intent: Tells the operator of a run that did not complete that a restore is available
+    and exactly how to invoke it, at every path a run can end without completing,
+    not only the two that already produce a RoadmapResult.
   files:
   - plan_tool/cli/roadmap_cmd.py
@@ -117,4 +119,5 @@ steps:
     2: the checkpoint that exists exactly when a run did not complete
     4: the restore and confirm option names the message must print
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/05-name-restore-command-when-checkpoint.md
 - id: 6
   title: 'Document the checkpoint file and the restore route and its refusal matrix
@@ -122,8 +125,7 @@ steps:
     checkpoint list/clear''s create/detail authoring cache, and remove BACKLOG.md
     #394 once the route ships and its tests pass'
-  intent: Makes the restore route discoverable from the operator docs, keeps an
-    operator from conflating this checkpoint with the unrelated plan-tool
-    checkpoint list/clear subcommand family, and closes the backlog entry it
-    discharges.
+  intent: Makes the restore route discoverable from the operator docs, keeps an operator
+    from conflating this checkpoint with the unrelated plan-tool checkpoint list/clear
+    subcommand family, and closes the backlog entry it discharges.
   files:
   - ROADMAP_FORMAT.md
@@ -145,4 +147,5 @@ steps:
     4: the shipped option names the operator docs cite
     5: the closing-message pointer the how-to and runbook describe
+  detail: docs/implementation-plans/plan-details/roadmap-revision-rollback/06-document-checkpoint-file-restore-route.md
 ---
 # Roadmap Revision Rollback
diff --git a/docs/implementation-plans/plan-details/roadmap-revision-rollback/02-move-run-roadmap-confirmed-brief-rebind.md b/docs/implementation-plans/plan-details/roadmap-revision-rollback/02-move-run-roadmap-confirmed-brief-rebind.md
new file mode 100644
index 00000000..e71a7f22
--- /dev/null
+++ b/docs/implementation-plans/plan-details/roadmap-revision-rollback/02-move-run-roadmap-confirmed-brief-rebind.md
@@ -0,0 +1,137 @@
+# Step 2 — Move the confirmed brief rebind write after publication recovery, and wire the revision checkpoint into every roadmap run
+
+<!-- plan-tool:detail-format-version: 1 -->
+
+## Summary
+
+`_run_roadmap` in `plan_tool/roadmap.py` writes `source.json` for a confirmed brief rebind (the `confirm_brief_rebind` branch, before `parse_carried_decisions`) before it ever calls `rec
````

