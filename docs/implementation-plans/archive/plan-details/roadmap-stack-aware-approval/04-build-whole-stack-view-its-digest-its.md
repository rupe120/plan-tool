> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Build the whole-stack view, its digest, and its one shared printout

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds three pieces that steps 5 and 6 consume. The first is a frozen stack-view record built from step 1's derivation. The second is a digest computed from that record's structured content. The third is one printout that renders the record. The record, its builder, and the digest go in `plan_tool/roadmap_candidate_review.py`. The printout goes in `plan_tool/cli/roadmap_cmd.py`. The key decisions are:
- The builder rebuilds every hop from stored records, so the caller's candidate supplies only its id and recorded root.
- The digest is computed in the library from structured facts and never from printed text.
- The printout renders the top candidate through the existing disclosure, so those lines stay in one place.

When the step is green, a real C1-structural / C2-presentation-only stack yields three things:
- a view listing both hops oldest first, with the root-to-tip diff;
- a digest that stays fixed across rebuilds and changes when any covered fact changes;
- a printout that shows all of it.

No command calls any of it until steps 5 and 6.

## Table of Contents

- [Summary](#summary) — what the step adds and the key decisions
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — the presentation gap the shared view closes
- [Input](#input) — the derivation, stored facts, and helpers the view reads, and what the tests here cannot show
- [Files (creates vs edits)](#files-creates-vs-edits) — the four declared files
- [Implementation](#implementation) — behavior, approach, rejected alternatives, constraints, and the site sweep
- [Tests](#tests) — test roster, stack builders, mutation checks, and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the plan and the modules involved
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work other steps own, and what is deliberately not built

## Why

The structural decision surface shows one candidate. `_render_structural_candidate_disclosure` in `plan_tool/cli/roadmap_cmd.py` prints the top candidate's own `predecessor_diff`, its source id, and its root id. For a stack whose top is presentation-only over a structural hop, that shows only the top hop's diff. It hides the hop that drives the seed invalidation. Steps 5 and 6 need one description of the whole stack, one printout of it, and one value an operator's confirm can bind to. Without a shared piece, each surface would build its own copy, and the copies could disagree. No stack-view, digest, or stack-printout symbol exists in `plan_tool/` or `tests/` at HEAD, so none of this work is already done.

## Input

- **Step 1's derivation.** One read-only function beside `source_ancestry_to_root` in `plan_tool/roadmap_candidate_run.py`.
  - **Names.** Step 1 recommends `candidate_stack_route` returning a frozen `CandidateStackRoute` with `hops` and `is_structural`. Read the landed names off that module. The landed names win over any name in this file.
  - **Contract used here.** It takes a tip id and a root id as keywords. `hops` holds the loaded `StoredCandidateProposal` for each unpromoted candidate, oldest first with the tip last and the root excluded. It returns an empty stack when the tip equals the root or the root is `None`. It raises `CandidateProposalError` for any unreadable hop, and it never reads the head or the admission pointer.
  - **Dependency.** The plan gives this step only step 1 as a dependency. Nothing here may need step 2's or step 3's code.
- **Facts each hop carries.** All are on `StoredCandidateProposal.evidence` (`CandidateProposalEvidence`):
  - `operation_classification`, which is `None` for a hop with no stored route;
  - `normalized_operations`;
  - `predecessor_diff`, which the loader checks against the stored bytes (`_require_reproducible_batch_diff`);
  - `batch_receipt` with `capsule_identity` and `reviewer_items`, the selected feedback;
  - `root_version_id`.
- **Loading the root and the tip's artifacts.**
  - `roadmap_candidate_run._load_resolved_version` loads a stored version and raises `CandidateProposalError`. This module already calls it.
  - `roadmap_candidate._parse_predecessor_artifacts(resolved, STAGES)` returns the parsed artifacts and their bytes, or a `CandidateRefusal` value. `_require_reproducible_batch_diff` already uses it.
  - The tip's bytes are already on the last hop as `content.artifact_bytes`.
- **The diff primitive.** `plan_tool/roadmap_diff.py:build_roadmap_diff` is pure. It takes `predecessor_artifacts`, `candidate_artifacts`, `predecessor_bytes`, `candidate_artifacts_bytes`, and `stages`, and returns a `RoadmapDiff`. `plan_tool/roadmap_candidate.py` already imports it under the alias `_build_predecessor_diff`.
- **Canonical serialization in the review module.** `_identity`, `_canonical_json_bytes`, and `_wire_value` in `plan_tool/roadmap_candidate_review.py` already canonicalize a `RoadmapDiff` (`_canonical_json_text(evidence.predecessor_diff)`). The CLI's `_render_stored_value` uses a different wire function from `plan_tool/roadmap_candidate.py`. The digest must not use it.
- **Limit of this step's tests.** They show the view, the digest, and the printed text over real stored stacks. They cannot show that an operator reads the printout or that a confirm binds to the digest. No command calls the builder or the printout until steps 5 and 6.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_review.py`:
    - add the frozen stack-view record, its builder, its digest, and a private helper that builds the digest's input;
    - import `build_roadmap_diff` from `plan_tool.roadmap_diff`.
  - `plan_tool/cli/roadmap_cmd.py`:
    - add the one stack printout beside `_render_structural_candidate_disclosure`, plus a small private helper that prints a diff's labeled lines;
    - import the view type by name into the existing `plan_tool.roadmap_candidate_review` import block, for the annotation.
  - `tests/test_roadmap_candidate_review.py`: view, digest, and failure-channel tests over real stacks.
  - `tests/cli/test_roadmap_cmd.py`: printout tests, and the module docstring's list of deliberate real-orchestrator exceptions.
- **No file outside the declared list changes.** `docs/cli/roadmap.md` needs no regeneration, because this step adds no flag.

## Implementation

**Behavior to deliver.**
- **Stack view.** One frozen record describes one candidate's whole unpromoted stack. It carries:
  - the recorded root id;
  - the hops, oldest first with the tip last. Each is the `StoredCandidateProposal` the derivation loaded. The printout reads id, stored route, selected feedback, and own diff off it;
  - the cumulative diff from the root to the tip.
- **Promotion effects.** The view exposes two read-only properties derived from `hops`. They are the promotion effects the printout states:
  - the ids of every hop, which are all promoted together with the top;
  - the ids of hops whose stored route is STRUCTURAL. These are the hops that make the enrolled seed state invalidate.
  - Both are functions of `hops`. They cannot disagree with it and need no separate digest coverage.
- **Builder.** One function takes `plans_dir`, `slug`, and the loaded candidate, and returns the view. Recommended names are `CandidateStackView` and `build_candidate_stack_view`. It refuses with `CandidateReviewError` when the stack is underivable, when the candidate has no recorded root, or when the cumulative diff cannot be derived. It never returns a partial view.
- **Digest.** The digest is a hex sha256 read as a `digest` property on the view.
  - It is computed from these facts:
    - the root id;
    - per hop, in order: version id, stored route (or `None`), batch receipt identity, selected feedback, typed operations, and own diff;
    - the cumulative diff;
    - a fixed `kind` tag for the view, the way `_identity({"candidate": ..., "kind": "structural-edit"})` tags its input.
  - It must change when any of those changes. That includes the hop set and the hop order.
- **Printout.** One function prints the view. It prints:
  - a header naming the root and the hop count;
  - one block per hop other than the top, oldest first, with a hop header line and the labeled per-hop facts;
  - the cumulative diff;
  - one line stating the promotion effects over the stack, meaning all hop ids and the structural hop ids;
  - the top candidate through the existing `_render_structural_candidate_disclosure`.

**Approach.** One way to do it:
- **Builder steps.**
  - Read only `candidate.version_id` and `candidate.evidence.root_version_id`. Refuse when the root is `None`.
  - Call step 1's derivation and translate `CandidateProposalError` into `CandidateReviewError` at that one call. Name the stack as underivable in the message.
  - Load the root with `roadmap_candidate_run._load_resolved_version`. Build a `ResolvedRoadmapVersion` for the tip from the last hop's record and content. Parse both with `_parse_predecessor_artifacts`. Turn a `CandidateRefusal` result into `CandidateReviewError`.
  - Call `build_roadmap_diff` with `STAGES` and return the view.
- **Digest.** Build a dict of the facts above and pass it through the module's `_identity`. Keep route-less hops in the dict with an explicit `None` route, so the digest tells a route-less hop from a presentation-only one.
- **Printout.**
  - Print the stack block before the disclosure, so the disclosure's closing `choices` line stays last.
  - Use one small private helper to print a diff's five labeled lines (affected artifacts, rows with before/after values, added relations, removed relations, ordering effects) under a caller-supplied prefix. The hop blocks and the cumulative block both call it.
  - Leave the disclosure's own lines untouched.
- **Single-hop stacks.** The cumulative diff always exists on the view, so the digest path is uniform. When exactly one hop sits above the root, the cumulative diff equals that hop's own diff. The printout then prints one explicit line saying so, and does not repeat the diff.

**Rejected alternatives.**
- **Hash the printed text.** A wording change would then refuse a valid confirm. The plan's Risks section names this.
- **Hash only the top hop's id.** A version id binds its bytes and predecessor, but not the stored route or selected feedback the operator saw. It also drops the cumulative diff, which the operator was shown.
- **A separate hop record type.** Step 1 keeps hops as loaded candidates so this step reads them directly. A second record type would have no reader beyond what the candidate already carries.
- **Store `promotion_effects` as a field or as wording.** Wording in the digest input makes the digest depend on rendering. A stored copy of a derived fact can disagree with `hops`.
- **Build the view from the caller's candidate object.** That object could be stale or edited in memory. Rebuilding every hop from stored records is what makes a recompute under step 5's writer guard trustworthy.
- **Reuse `plan_tool/roadmap_compare_run.py:run_roadmap_comparison`.** It captures Git patches through a subprocess and returns presentation-oriented data. The digest must depend only on stored bytes.
- **Extract a per-candidate fact printer from the disclosure.** That would mix a refactor into a feature step. Delegating to the disclosure keeps one copy of those lines without touching them.

**Constraints (not free to vary).**
- **Fresh hops.** Every hop in the view comes from the derivation's own loads. The passed candidate supplies only its id and recorded root.
- **All or nothing.** An underivable stack, a missing recorded root, or an underivable cumulative diff refuses. No view is returned with a hop or the diff missing. A digest over an incomplete view could confirm a stack the operator never saw.
- **The builder does not judge.** It must not test whether the stack is structural. It returns a view for an all-presentation stack too. The guards own eligibility.
- **Read-only.** The builder takes no writer guard, writes nothing, takes no invoker, and never reads the head or the admission pointer. It runs identically inside or outside a guard. Step 5 calls it inside the guard.
- **Digest independence.**
  - The digest must not depend on any printed text, label, or layout. `plan_tool/roadmap_candidate_review.py` must not import `plan_tool.cli`.
  - It must not use the CLI's `_render_stored_value` or its wire function.
- **No route from the diff.** The cumulative diff is presentation only. It must not feed `_classify_validated_operations` or any route or gate.
- **Explicit route-less marker.** The printout states that a hop has no stored route, and does not omit the line. It must be distinct from `presentation-only`.
- **The printout does not print the digest.** Step 5 prints it beside the printout on its two approve invocations. Step 6's surfaces have no confirm to use it.
- **The printout is a pure render of the view.** It reads no disk, no admission, and no stored candidate. It must not recompute anything the view holds.
- **The existing disclosure lines survive.** Every line the disclosure prints today for the top candidate must appear in the printout for that candidate, with the same labels.
- **Structural stacks only.** Surfaces call the printout only for a stack that carries a structural hop. The printout adds no branch for other stacks.

**Foundational logic and the sites.** The logic is one shared, render-independent description of a candidate's unpromoted stack. I swept `_render_structural_candidate_disclosure`, `_render_candidate_proposal_result`, `_render_candidate_review_result`, `_render_candidate_answer_result`, and `_render_structural_candidate_decision_result` by identifier. I swept "predecessor diff", "selected feedback", "promotion effects", and "cumulative" by vocabulary.
- **Changed here:** none of the existing renderers.
- **Called by the printout, unchanged:** `_render_structural_candidate_disclosure`, for the top candidate.
- **Owned by other steps:**
  - step 5 wires the printout and the digest on both approve invocations;
  - step 6 wires the printout on edit, reject, and the proposal output;
  - `_render_candidate_proposal_result`'s own-route check is step 6's.
- **Kept as is, deliberately:** the answered route's review and answer renderers print `predecessor diff:` for a stack their guard refuses, so the plan keeps their output.

**Interim reachability.** No command calls the builder or the printout until steps 5 and 6. Only tests do. This follows the plan's ordering: this step supplies the shared pieces, and steps 5 and 6 wire them.

## Tests

Library cases go in `tests/test_roadmap_candidate_review.py`. Printout cases go in `tests/cli/test_roadmap_cmd.py`.

**Stack builders (library tests).**
- **C1 structural, C2 presentation-only.** The interim batch block refuses this through `_run_batch` alone. Reuse the masking helper step 1 adds to `tests/test_roadmap_candidate_run.py`. Read its landed name and import it the way this module imports `_run_batch` and `_seed_batch_ledger`.
- **Hops that each change rows.**
  - `_SECOND_BATCH_DELTA` has no operations, so its diff is empty. The cumulative diff cases need a second delta with one operation on a different row, or on the same row.
  - It needs its own open ledger item, because `_FIRST_BATCH_DELTA` answers `batch-one`. `_batch_item` builds one.
  - Choose each operation by the stored route it must produce, and assert that route.
- **Route-less hop and forged hop.** Use `_edit_stored_evidence`. Drop both route fields for a route-less hop. Make one lower hop's route disagree with its stored operations for a forged hop.

**Library cases.**
- `test_stack_view_lists_hops_oldest_first_above_the_recorded_root_and_ends_at_the_tip` — over C1-structural / C2-presentation, the hop ids are `(C1, C2)`, the root id is absent from the hops, and the view's root equals the recorded root.
- `test_stack_view_promotion_effects_name_every_hop_and_only_the_structural_ones` — the promoted ids are `(C1, C2)` and the structural ids are `(C1,)`, although the top's own route is presentation-only.
- `test_cumulative_diff_is_the_root_to_tip_diff_recomputed_from_stored_bytes` — the view's diff equals `build_roadmap_diff` run by the test itself over the root's and the tip's stored artifacts. It differs from the top hop's own diff when the top changed fewer rows.
- `test_cumulative_diff_collapses_two_hops_editing_the_same_row_into_one_change` — the row shows the root's value before and the tip's value after, not two entries. This pins that it is not a concatenation of own diffs.
- `test_single_hop_cumulative_diff_equals_the_hops_own_diff` — over one structural candidate above the enrolled root, the two diffs are equal.
- `test_stack_view_carves_out_route_less_hops_and_never_judges_eligibility` — a route-less lower hop appears with a `None` route, and an all-presentation stack still yields a view with no structural ids. This is the deliberate "the builder does not judge" carve-out.
- `test_stack_view_is_rebuilt_from_stored_records_not_from_the_callers_candidate` — pass a copy of the top candidate whose evidence was altered in memory. The view and its digest equal those built from the unaltered candidate.
- `test_stack_view_refuses_an_underivable_stack_with_a_review_error_and_no_partial_view` — over a forged lower hop, an unreadable root, and a candidate with no recorded root, the builder raises `CandidateReviewError`, never `CandidateProposalError`, and returns nothing.
- `test_stack_view_digest_is_stable_across_rebuilds` — two builds of the same stack give the same 64-character digest.
- `test_stack_view_digest_changes_when_any_covered_fact_changes` — parametrized over each covered fact: root id, and per-hop version id, route, receipt identity, selected feedback, typed operations, and own diff. Also parametrized over the cumulative diff, the hop order, and a dropped hop. Each variant changes the digest. Build variants with `dataclasses.replace` and `model_copy(update=...)`.
- `test_stack_view_digest_distinguishes_a_route_less_hop_from_a_presentation_only_one` — the two give different digests.
- `test_storing_a_descendant_changes_the_new_tops_digest_and_leaves_an_ancestors_digest_alone` — the view for C3 over C2 differs from the view for C2, and the view for C2 is unchanged after C3 is stored. This pins the hop-set sensitivity and the stateless digest.
- `test_stack_view_module_does_not_import_the_cli_layer` — a scan of `plan_tool/roadmap_candidate_review.py` for any `plan_tool.cli` import. This pins why the digest cannot depend on the printout.

**Printout cases (`tests/cli/test_roadmap_cmd.py`).** Build the real view type over `_stored_structural_cli_candidate()` hops. The printout never touches `digest`, so hand-built hops are enough.
- `test_stack_printout_lists_every_hop_oldest_first_with_route_selected_feedback_and_own_diff` — over three hops, every id appears in order, and each hop's route, selected feedback, and rows appear.
- `test_stack_printout_keeps_every_line_the_existing_disclosure_prints_for_the_top_candidate` — every line `_render_structural_candidate_disclosure` prints for the top hop appears in the printout. This pins "extends, never replaces".
- `test_stack_printout_names_the_structural_hop_when_the_top_is_presentation_only` — the output names the lower structural hop's id and the count of promoted hops.
- `test_stack_printout_states_that_a_route_less_hop_has_no_stored_route` — the marker is present and differs from the `presentation-only` output.
- `test_stack_printout_prints_the_cumulative_diff_for_a_multi_hop_stack_and_one_line_for_a_single_hop` — both shapes.
- `test_stack_printout_is_a_pure_render_and_reads_no_stored_state` — with `load_stored_candidate_proposal` and `load_candidate_admission` in `roadmap_cmd` replaced by failing stubs, printing a hand-built view still works.
- `test_stack_printout_from_a_real_stack_prints_every_hop_and_never_prints_the_digest` — one real-record case. Build the real C1-structural / C2-presentation stack and its view, print it, and assert that both hop ids appear and that `view.digest` does not. Add this test to the module docstring's list of deliberate real-orchestrator exceptions in the same edit.

**Verify by mutation.** Break the code each of these ways and confirm each turns a test red:
- hash only the top hop;
- leave the cumulative diff out of the digest;
- leave one per-hop field out of the digest;
- reverse the hop order in the digest;
- build hops from the caller's candidate;
- swallow the derivation error and return a partial view;
- compute the cumulative diff from the top's own diff;
- drop the lower hops from the printout;
- print the digest in the printout;
- omit the route-less marker;
- add a `plan_tool.cli` import to the review module.

### Tests for this step

- **Tests added.** Approx. 13 library cases and 7 printout cases, listed above, in the two declared test files. They cover hop order, effects, the cumulative diff, the carve-outs, the failure channel, digest stability and sensitivity, and the printout's contents and purity.
- **Existing tests.** No existing test changes. The disclosure and proposal-output tests stay green and unedited, because nothing existing is edited.
- **Green gate.** Every test above and the rest of the suite must be green before the step is done. The step's `test_command` is `uv run pytest tests/ -q -n auto`. The added tests also satisfy the plan's test-authoring gate.

## Acceptance criteria

- **View.** The builder returns a frozen view holding the recorded root, the ordered hops (oldest first, tip last, root excluded), and the root-to-tip diff. Its promoted and structural hop ids are derived from `hops`.
- **Cumulative diff.** It equals `build_roadmap_diff` over the root's and the tip's stored artifacts. It is derived with no backend call.
- **Failure.** An underivable stack, a candidate with no recorded root, and an underivable cumulative diff each raise `CandidateReviewError`. No partial view is returned.
- **Fresh records.** The view and its digest are identical whether built from the stored candidate or from an in-memory altered copy.
- **Digest.**
  - It is a 64-character hex string.
  - It is identical across rebuilds.
  - It changes when any covered fact, the hop order, or the hop set changes.
  - It tells a route-less hop from a presentation-only one.
- **Render independence.** `plan_tool/roadmap_candidate_review.py` has no `plan_tool.cli` import, and the digest input holds no printed text.
- **Printout.**
  - It prints every hop's id, stored route or an explicit no-route marker, selected feedback, and own diff.
  - It prints the cumulative diff, or one line saying it equals the single hop's diff.
  - It prints the promotion-effects line.
  - It contains every line the existing disclosure prints for the top candidate.
  - It reads no stored state.
  - It does not print the digest.
- **No wiring.** No command calls the builder or the printout. `git diff --name-only` lists only the four declared files. The batch block in `_run_batch_candidate_proposal` is unchanged.
- **Suite.** `uv run pytest tests/ -q -n auto` passes.

## References

- [docs/implementation-plans/2-roadmap-stack-aware-approval.md](../../2-roadmap-stack-aware-approval.md) — § "Design decisions" (Stack view, Digest) and Risks define what the view, digest, and printout must and must not do.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/01-one-stack-route-derivation-beside.md](01-one-stack-route-derivation-beside.md) — step 1's derivation, its hop order, and its error channel.
- [handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md](../../../../../handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md) — the P2.1 defect and the owner decisions.
- [plan_tool/roadmap_candidate_review.py](../../../../../plan_tool/roadmap_candidate_review.py) — `_identity`, `_canonical_json_bytes`, and the module that gains the view and digest.
- [plan_tool/cli/roadmap_cmd.py](../../../../../plan_tool/cli/roadmap_cmd.py) — `_render_structural_candidate_disclosure` and `_render_stored_value`.
- [plan_tool/roadmap_diff.py](../../../../../plan_tool/roadmap_diff.py) — `build_roadmap_diff`, the cumulative diff's primitive.
- [ROADMAP_FEEDBACK_FORMAT.md](../../../../../ROADMAP_FEEDBACK_FORMAT.md) — the feedback lifecycle and the batch stacking rule.

## Applicable guardrails

- **The plan's "Scope guardrails", "Not allowed": no new persisted stack or binding field.** The view and the digest are computed at use from stored records. Nothing is written, cached, or stored. The plan's binary observable says the digest match is checked at confirm time and is not stored.
- **The plan's "Scope guardrails", "Not allowed": no cumulative classifier derived from content, and no quality or semantic judgment of stack content.** The cumulative diff is presentation. It must not feed a route, a gate, or `_classify_validated_operations`. The builder describes the stack and does not judge it.
- **The plan's "Scope guardrails", "Not allowed": no second structural gate, no per-hop approval, no auto-approval, and no terminal prompt.** This step adds a description and a printout. It adds no decision, gate, or prompt.
- **The plan's "Scope guardrails", "Not allowed": no separate read-only show command, and no stack output on reject, discard, or the answered route beyond what steps 5 and 6 assign.** This step adds no flag and no call site. `docs/cli/roadmap.md` is unchanged.
- **The plan's "Scope guardrails", "Not allowed": no change to the promotion writer, the journal, the recovery machinery, or the version and candidate stores.** This step touches none of them and takes no writer guard.
- **The plan's "Scope guardrails", ordering fence.** The batch block stays until step 7. This step supplies the view and printout that its removal depends on.
- **The plan's "Design decisions", Digest.** The digest is a function of the view's content, never of the printout. Step 5 recomputes it under the writer guard.
- **The plan's "Out of scope": edit sourcing, reject/discard pointer release, run-log coverage for the decision commands, and `_classify_validated_operations`.** All stay unchanged.

## Deferred

- Both approve invocations, the digest line, the digest comparison, and the confirm flag — step 5 owns them. This step exposes `view.digest` and prints nothing about it.
- Rendering the printout on edit, reject, and the proposal output, and the reject note — step 6 owns them.
- Retiring the batch block and end-to-end tests of the stack across the direct, answered, edited, and recovered routes — step 7 owns them.
- Documenting the two-invocation approve and the whole-stack scope — step 8 owns it.
- Folding `_render_structural_candidate_disclosure` into the printout, or sharing the diff-line helper with it — not built. The printout delegates the top candidate to the disclosure, so one copy of those lines exists.
- Reusing `run_roadmap_comparison` or sharing its snapshot loading — not built. It runs Git patch capture, which the digest must not depend on. Its snapshot parsing looks similar to `_parse_predecessor_artifacts`, but I did not verify the two are interchangeable. Any consolidation needs its own entry with machine-verified evidence.
- Persisting or caching the view — not built. Stored versions are immutable, so recomputing is correct.
- A printout branch for a stack with no structural hop — not built. The plan keeps those surfaces' current output, and no surface calls the printout for them.
