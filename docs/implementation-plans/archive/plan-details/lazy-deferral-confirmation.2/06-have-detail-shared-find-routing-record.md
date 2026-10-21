> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Have detail record a flat pending `defer` decision for a body-section bucket on a record-absent plan, never signed under `-y`

<!-- Scope (settled): record-absent plan is the supported input for RECORDING a flat pending decision. A legacy full-tree record is not extended/clobbered — but a proposed deferral on a non-stale legacy record is NOT silently dropped: emit the migration warn (below, dual-mode plan Architecture H), so the deferral reaches a human. Full recording into a legacy record awaits BACKLOG #131. On a *stale* legacy record generate_detail still aborts at its existing load guard (legacy-staleness, out of this MVP's scope). -->


## Summary

Widen `plan_tool/detail.py`'s deferral routing so a detail step can record a **new, unreviewed flat `defer` decision** for a plan body-section **bucket** — instead of only linking an already-approved concept node. The deferral's `concept_id` now resolves against a candidate bucket set derived fresh from the current plan body (the `bootstrap_concepts` recipe scope-review and create already use), so it works with **no `concepts.json` on disk**; the persist tail writes each newly-deferred bucket as a `record_kind="decision-record"` node (step 1's shape) with `decision="defer"`, `review_state="unreviewed"`, via a direct `save_concepts`. The key rule: detail **never signs** the node — even under `-y` it stays `unreviewed`, leaving `plan-tool scope-review` the sole signer. On green, a detail run whose model proposes deferring a body-section bucket produces a flat pending decision-record on a plan that had no concept record, and `-y` never flips its `review_state` to `approved`.

## Table of Contents

- [Why](#why) — detail's deferral routing only handles a pre-approved tree node, so it can't record a fresh pending decision
- [Input](#input) — step 1's flat decision-record shape and the body-section bucket candidates this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — one code file, one test file
- [Implementation](#implementation) — derive candidate buckets, widen the parse gate, surface proposable buckets, record a flat unreviewed defer
- [Tests](#tests) — record-absent defer, never-signed under `-y`, unknown bucket refused, prompt surfacing
- [Acceptance criteria](#acceptance-criteria) — observable behaviors on green
- [References](#references) — dataclasses / json / pytest docs for the record shape
- [Deferred](#deferred) — legacy full-tree coexistence/migration, the include-regeneration machinery, shared-recipe consolidation

## Why

Detail's deferral routing today can only defer a concept that is **already an approved `defer` node** in a loaded concept tree. `plan_tool/detail.py:parse_structured_detail_response` (the gate inside its `all(supplied)` block) rejects a deferral unless the target node exists in the loaded `concept_tree`, has `review_state == "approved"`, and `decision == "defer"`. The persist tail near the end of `generate_detail` (the `if concept_tree is not None and not dry_run:` block) then only rewrites step-id links (`detail_deferral_step_ids`) on those existing nodes — it never creates a node or records a decision, and it is gated on `concept_tree is not None`, so a plan with no `concepts.json` records nothing. In the flat model this plan ships, `create` writes **no record** for an ordinary plan (step 2), so by detail time there is usually nothing to link. A detail step that discovers a concept worth deferring must be able to **record a fresh pending decision from scratch**, on any plan, and leave it for the operator to confirm — never sign it itself. This step makes detail a second producer of flat decision-record deferrals, matching what `create` records (step 2) but through detail's own persistence path.

## Input

This step reads one sibling step's outcome plus a deterministic body-section derivation. Depend on the outcome, not the mechanism.

- **Flat decision record — step 1.** Step 1 adds `ConceptTree.record_kind` (defaults to the legacy `"full-tree"`; the flat kind is `"decision-record"`) and `ConceptNode.bucket` (defaults `""`), and makes `plan_tool/concept_tree.py:load_concepts` skip the `StaleConceptTreeError` fingerprint check for a `decision-record`. A flat node carries a non-empty `bucket`, an empty `parent_path`, and a `decision` of `defer`/`wont_do`. Read those field names and defaults; do not restate step 1's decoder/validator work.
- **Body-section bucket candidates.** The set of buckets the model may defer is derived from the plan's current body sections, not from `concepts.json`. Reuse the exact recipe `bootstrap_concepts(plan, parse_body_sections(split_plan_document(plan_text).body), plan_slug=…, plan_fingerprint=…)` — the one `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` and `create_plan` already use — so each candidate's `id` (`concept_id(section.name, [])`) and `bucket`/`title` (`section.name`) match every producer and consumer. A bucket is the normalized H2 section name.
- **This step never depends on a pre-materialized tree.** A record-absent plan is the primary supported input: the candidate buckets come from the plan body, so the model can name one and detail can record it with no prior `concepts.json`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` —
    - Add imports for `parse_body_sections`, `split_plan_document` (from `plan_tool.parser`) and `bootstrap_concepts` (from `plan_tool.concept_bootstrap`), plus `ConceptNode` from `plan_tool.concept_tree`.
    - Derive the candidate bucket set once in `generate_detail` and thread it to the prompt block, the parse gate, and the persist tail.
    - Widen `parse_structured_detail_response`'s deferral gate to resolve `concept_id` against the candidate buckets and drop the two pre-approval rejections.
    - Extend `_format_concept_scope_block` to list proposable buckets so the model can name one.
    - Reshape the `generate_detail` persist tail (and/or `_replace_detail_deferrals`) so a newly-deferred bucket is recorded as a flat `record_kind="decision-record"` node (`decision="defer"`, `review_state="unreviewed"`) via `save_concepts`, including when `concepts.json` is absent.
  - `tests/test_detail.py` — add/rework `TestStructuredDetailDeferrals` cases and helpers (`_save_detail_concept`, `_structured_detail`) for the flat-record model.

## Implementation

Describe the desired forward state; the exact code is the implementer's.

- **Derive the candidate bucket set once, thread it everywhere.** In `generate_detail`, build the bucket candidates from the parsed `plan` and the plan text with the shared recipe (`bootstrap_concepts(plan, parse_body_sections(split_plan_document(plan_text).body), …)`). Build it **once** and pass the same set to the prompt render (`_format_concept_scope_block` via `render_detail_prompt`), to every `parse_structured_detail_response` call (the checkpoint parse and the author-step parse both currently pass `concept_tree`), and to the persist tail. Two independent derivations between the prompt surface and the recorder can disagree on an id and silently break the round-trip — one derivation avoids that.
  - *Constraint:* use the identical recipe/primitive `scope_review_cmd.py` and `create.py` use — do not hand-roll a section split. The `id` and `bucket` must match those producers or a later `scope-review`/`status` read won't recognize the same bucket.

- **Widen the parse gate.** In `parse_structured_detail_response`, replace "node exists in the loaded `concept_tree` and is an approved `defer`" with "id resolves to a known body-section bucket candidate". Drop **only** the two pre-approval rejections — `node.review_state != "approved"` and `node.decision != "defer"`. Keep the other guards: `deferral.step_id == step.id`, the id resolves to a candidate bucket, the owner check (unowned, or this step owns it), and the `## Deferred` section mentions the id. A gate that accepts a bucket the model can never see is dead code, which is why the prompt surfacing below ships in the same step.
  - *Latitude:* the gate currently takes `concept_tree`. One way: pass the candidate id→bucket map instead of (or alongside) the tree, since the resolution target is now the body-derived candidates, not the persisted record. Keep the `any(supplied) and not all(supplied)` symmetry so the shape-only parse path (no `plan`/`step`) is unchanged.

- **Surface proposable buckets in the prompt.** In `_format_concept_scope_block`, add a section listing the candidate buckets the model may defer — bare `id`, `bucket`/title — marked as proposable. Keep the existing approved-node lines unchanged so `tests/test_detail.py:TestStructuredDetailDeferrals.test_dry_run_reports_include_regeneration_without_writes` (asserts `decision=include` appears in the prompt) stays green. The model can only name a bucket the prompt shows it.

- **Record a flat unreviewed `defer` in the persist tail.** Reshape the tail (the `if … not dry_run:` block that today calls `_replace_detail_deferrals` + `save_concepts`) so each newly-deferred bucket becomes a flat `ConceptNode(id=<candidate id>, title=<section name>, bucket=<section name>, rationale=<the deferral reason>, decision="defer", review_state="unreviewed", parent_path=[])`, assembled into a `ConceptTree(record_kind="decision-record", …)` and written with `save_concepts`. The tail must run **even when the loaded record is absent** — don't gate the write on `concept_tree is not None` for the flat-record path.
  - **Capture the `rationale` — the record's "what/why".** The detail deferral envelope carries a short **`rationale`** field alongside `concept_id`/`step_id` (the model's reason for routing the find to `## Deferred`, which the shared-find directive already asks it to state). Populate `ConceptNode.rationale` from it so a confirmed deferral renders as `- {title} — {rationale}` via `render_scope_decisions` — not a bare section bullet (`- risks`). Without this, "what within the section was deferred, and why" is lost once the pending node is signed off (the `[deferral-rationale-content]` gap); the `status` lazy-context excerpt only helps *before* confirmation. Keep it short (one line); an absent/empty envelope rationale falls back to no `— rationale` suffix (still valid).
  - *Hard constraints (pin with tests):*
    - The recorded node is `record_kind="decision-record"`, `decision="defer"`, `review_state="unreviewed"`, non-empty `bucket`, and carries the envelope's `rationale` when supplied.
    - `review_state` stays `"unreviewed"` under `-y` — detail **never** sets `"approved"`. `scope-review` (step 4) is the only signer.
    - Persist via `save_concepts` (a direct write of a decision-record), **not** `synchronize_concepts` — that renders approved-only and would drop or force-sign an unreviewed node.
    - Set `plan_fingerprint = compute_plan_fingerprint(plan_path)` on the written tree for provenance (step 1 stores it unchecked for this kind); the value is never consulted on load for a decision-record.
  - *Merge into an existing `decision-record` (pin every case with tests):* a flat node's `id` is `concept_id(title, [])` with `title == bucket == section name`, so a re-deferral of a bucket resolves to the **same id** as any existing node for that section. Handle the collision by `review_state`:
    - existing **unreviewed** node for the id → **no-op** (the pending proposal already stands; do not duplicate).
    - existing **approved** node for the id (a prior `scope-review` signed it `defer`/`wont_do`) → **preserve it — do NOT re-open to `unreviewed`**. The operator's decision is authoritative; silently resurrecting it as pending is a correctness bug (`[detail-merge-into-existing-node]`). Leave the approved node untouched and record nothing new for that bucket.
    - new id (a different section) → add the flat node.
  - *Bucket-granularity limitation (`[multiple-concepts-per-bucket]`, documented):* because identity is the section name, **at most one deferral decision is tracked per body section** — two *distinct* concepts detail defers into the same section collapse to one node, and the second's `rationale` is not separately recorded. The MVP is deliberately bucket-granular (the flat "bucket is the leaf" model). Capturing multiple distinct concepts under one section needs finer-than-section identity — that is the sub-concept producer deferred to BACKLOG **#130** (the drill). So the founding-incident "none silently dropped" holds **at bucket granularity**; finer granularity is #130. Name this explicitly rather than letting the collapse be a silent surprise.
  - When a **legacy full-tree** record exists, do not clobber it — but do **not** silently drop the model's proposed deferral either: emit a `warn` naming the concept and telling the operator the plan's legacy record must be migrated (#131) to capture the deferral. The deferral is surfaced to a human (via the warn), never silently discarded — that silent-drop is the exact failure this plan exists to prevent (see Deferred for the migration boundary).

- **Foundational logic and shared sites.** The one behavior this step adds is: *record a fresh unreviewed flat `defer` decision for a body-section bucket, resolving the target from the current plan body*. The bucket-candidate derivation recipe is duplicated across `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, `plan_tool/create.py:create_plan`, and now `plan_tool/detail.py`. This step **reuses** that recipe (does not consolidate it) — extracting a shared candidate-derivation helper across three modules is a refactor beyond this step; see Deferred.

## Tests

All in `tests/test_detail.py`, extending `TestStructuredDetailDeferrals` and reworking its helpers.

- `test_detail_records_flat_defer_on_record_absent_plan` — a plan with no `concepts.json`; the model defers a real body-section bucket; on green a `concepts.json` exists with one `record_kind="decision-record"` node, `decision="defer"`, `review_state="unreviewed"`, non-empty `bucket`.
- `test_yes_does_not_sign_off_new_deferral` — same as above but with `generate_detail(..., yes=True)`; asserts the recorded node's `review_state` is still `"unreviewed"` (never `"approved"`).
- `test_deferral_for_unknown_bucket_does_not_publish_detail` — the envelope names an id that is not a current body-section bucket; the detail is not written and no record is created (mirrors current `test_unknown_concept_does_not_publish_detail`).
- `test_proposable_buckets_appear_in_prompt` — the rendered detail prompt lists the body-section buckets (bare id + bucket) as proposable, so the model can name one; a dry-run assertion on `results[0].prompt`.
- `test_deferred_section_must_mention_the_bucket_id` — an envelope whose `## Deferred` body omits the deferred id is rejected (the retained non-approval guard).
- `test_deferral_rationale_persisted_and_rendered` — a deferral envelope carrying a `rationale` records it on the flat node, and after a `scope-review` confirm the plan's `## Deferred` shows `- {title} — {rationale}` (not a bare section bullet); an envelope with no rationale records an empty rationale and renders `- {title}` cleanly.
- `test_existing_decision_record_gains_the_new_bucket` — a plan already carrying a pending `decision-record`; a new deferral for a different bucket merges in and leaves the prior pending node untouched (`review_state="unreviewed"`).
- `test_redeferral_of_pending_bucket_is_noop` — re-deferring a bucket that already has an **unreviewed** node makes no change (no duplicate, still one pending node).
- `test_redeferral_of_approved_bucket_preserves_decision` — re-deferring a bucket whose node was already signed off (`review_state="approved"`, e.g. `wont_do`) leaves it **approved** and does not re-open it to `unreviewed` — the operator's decision is preserved (`[detail-merge-into-existing-node]`).
- `test_legacy_record_deferral_warns_not_dropped` — a plan carrying a non-stale `record_kind="full-tree"` record; the model proposes a new deferral; on green the full-tree record is **not** modified but a `warn` naming the concept and the #131-migration remedy is emitted (captured via capsys) — the deferral is surfaced to a human, never silently discarded.
- Rework the existing full-tree-linkage cases (`test_valid_deferral_persists_after_detail_write`, `test_concurrent_deferrals_save_once_in_step_order`, and the `_save_detail_concept` helper) to the flat-record model, since the gate no longer requires an approved node.

### Test-creation order (feature step)

This is a **feature** step. Add each test above **with** the implementation it covers. Green-before-done gate: every new/reworked test in `TestStructuredDetailDeferrals` must pass, and `uv run pytest tests/test_detail.py -q` must be green before the step is considered finished.

## Acceptance criteria

- A detail run whose model defers a current body-section bucket on a plan with **no `concepts.json`** writes a `concepts.json` whose sole node has `record_kind`-tree `= "decision-record"`, `decision="defer"`, `review_state="unreviewed"`, and a non-empty `bucket` equal to the section name.
- `generate_detail(..., yes=True)` recording a new deferral never sets `review_state="approved"` — the node stays `"unreviewed"`.
- A deferral naming an id that is not a current body-section bucket does not write the detail file and creates no record.
- The rendered detail prompt lists the plan's body-section buckets as proposable (bare id + bucket), and a deferral whose `## Deferred` body omits the id is rejected.
- The recorded node is persisted through `save_concepts` (a decision-record write), never through `synchronize_concepts`.
- `uv run pytest tests/test_detail.py -q` passes.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — building the flat `ConceptNode` (bucket/decision/review_state) this step writes.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — the deferral envelope payload and the `save_concepts` serialization the tail writes.
- [pytest — full documentation](https://docs.pytest.org/en/stable/) — authoring the record-absent, never-signed, and unknown-bucket tests.

## Deferred

- **Legacy full-tree coexistence and migration** — when a non-stale `record_kind="full-tree"` record is already on disk, this step does not migrate it or clobber it, but it does **warn** (not silently drop) if the model proposes a new deferral it cannot record there (see the Latitude bullet in Implementation) — the deferral reaches a human. *Recording* into a legacy record (migration) stays deferred to BACKLOG #131.
- **The include-transition regeneration machinery** (`plan_tool/detail.py:_included_deferral_step_ids` and the `decision == "include"` regeneration path) — left dormant for legacy full-tree records; the flat model records only `defer`/`wont_do`, so detail does not exercise it. Not removed here.
- **Consolidating the bucket-candidate derivation recipe** into one shared helper across `scope_review_cmd.py`, `create.py`, and `detail.py` — a cross-module refactor beyond this step; reuse the recipe now and route the extraction to reconcile.
