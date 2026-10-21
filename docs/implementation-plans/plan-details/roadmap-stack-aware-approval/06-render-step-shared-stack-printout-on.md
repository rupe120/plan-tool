# Step 6 — Render step 4's shared stack printout on edit, reject, and a structural-stack proposal

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step wires step 4's stack printout onto three surfaces in `plan_tool/cli/roadmap_cmd.py`.
- **Structural decision, edit and reject:** the printout replaces today's top-hop-only disclosure. Reject also prints a note that it drops every unpromoted hop.
- **Edit's stored replacement:** the replacement's whole stack is printed.
- **Proposal output:** the printout appears when the candidate's stack carries a structural hop, whether or not its own route is structural.

The main design decision is that handlers build the view and pass it to the renderers, so the renderers stay pure. The proposal handler asks step 1's derivation first, so a stack with no structural hop keeps today's output and gains no new failure mode. On green, a real C1-structural / C2-presentation-only stack shows both hops on reject, on edit, and on a proposal. Approve is step 5's and is not touched.

## Table of Contents

- [Summary](#summary) — what the step wires and the key decision
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — the top-hop-only presentation on the three remaining surfaces
- [Input](#input) — the step 1, 2, 4, and 5 outputs and the stored facts this step reads, and what its tests cannot show
- [Files (creates vs edits)](#files-creates-vs-edits) — the two declared files
- [Implementation](#implementation) — behavior, per-outcome table, approach, rejected alternatives, constraints, and the site sweep
- [Tests](#tests) — test roster, existing tests that change, mutation checks, and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable checks
- [References](#references) — the plan and the modules involved
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work other steps own, and what is deliberately not built

## Why

After steps 2 and 3, a presentation-only top over a structural hop is decidable, but three surfaces still show only the top hop.
- **Edit and reject:** `_cmd_roadmap_structural_candidate_decision` calls `_render_structural_candidate_disclosure` on the candidate being decided. That prints the top's own `predecessor_diff` and hides the structural hop below it.
- **Edit's result:** `_render_structural_candidate_decision_result` prints the same top-only disclosure for the replacement the operator approves next.
- **Proposal output:** `_render_candidate_proposal_result` prints the disclosure only when the candidate's own stored route is structural. A C2 that is presentation-only over a structural C1 prints no structural lines at all.

Step 5 covers approve. Step 4 supplies the printout. The already-implemented signal (`def proposal` in `tests/cli/test_roadmap_cmd.py`) matches two local stubs of `run_initial_candidate_proposal` in the dispatch tests. Both return `candidate=None`. A search of `plan_tool/` and `tests/` for `build_candidate_stack_view`, `candidate_stack_route`, `CandidateStackView`, and `_render_.*stack` returns no matches at HEAD, so none of this work is done.

## Input

- **Step 4's view, builder, and printout.**
  - **Names.** Step 4 recommends `CandidateStackView` and `build_candidate_stack_view(plans_dir, slug, candidate)` in `plan_tool/roadmap_candidate_review.py`, plus one printout function in `plan_tool/cli/roadmap_cmd.py`. Read the landed names off those modules. The landed names win over any name in this file.
  - **Builder contract.**
    - It reads only the candidate's id and recorded root, and rebuilds every hop from stored records.
    - It raises `CandidateReviewError` for an underivable stack, a missing recorded root, or an underivable cumulative diff. It never returns a partial view.
    - It takes no guard, reads no head or admission pointer, and writes nothing.
    - The view exposes the ids of every hop and of the structural hops, both derived from `hops`. Read the landed property names.
  - **Printout contract.** It is a pure render of the view. It delegates the top candidate to `_render_structural_candidate_disclosure`, and it does not print the digest.
- **Step 1's derivation.** `candidate_stack_route` takes a tip id and a root id. It returns an empty, non-structural stack when the root is `None` or equals the tip. It raises `CandidateProposalError` for an underivable stack. Step 2 imports it by name into `roadmap_cmd`.
- **Step 2's precheck.** `_cmd_roadmap_structural_candidate_decision` already refuses a non-structural or underivable stack with status 2 before any output. When this step prints, the stack is structural and derivable, unless it changed between the precheck and the build.
- **Step 5's split.** The handler has an approve branch and a non-approve branch.
  - Step 5 builds the view in the approve branch. Its `except (ValueError, OSError)` becomes `error(...)` and status 2, before any output.
  - The non-approve branch still calls today's disclosure. This step replaces that call.
  - Steps 2, 4, and 5 are declared dependencies, so read the handler as steps 2 and 5 leave it: the precheck first, then step 5's approve and non-approve split. Change only the edit and reject arms.
- **What the library returns.**
  - **Edit.** A stored edit returns the replacement as `CandidateReviewResult.active_candidate`. `_store_active_structural_replacement` publishes it before `_stored_result` is built, so it is stored when the CLI sees it. It is sourced from the top's own source and keeps the top's recorded root, so its stack is the lower hops plus itself.
  - **Reject.** `reject_candidate_review` releases the active pointer and stores nothing new. The hops stay stored as history.
- **Today's edit output.** The disclosure prints twice, once before the decision and once for `active_candidate`. `test_structural_candidate_edit_requires_one_correction_and_never_promotes` counts two `stored route: "structural"` lines.
- **Proposal handler.** `_cmd_roadmap_propose_candidate` is the only caller of `_render_candidate_proposal_result`. It serves both `--propose-candidate` and selector-free `--revise-feedback`. Its result can carry `candidate=None`.
- **Exit codes.** `_RC_USAGE` is 2 and `_RC_INCOMPLETE` is 1. `error` from `plan_tool.style` prints to stderr.
- **Limit of this step's tests.** They show that the printout reaches each surface and that the carve-outs keep today's output. They cannot show that an operator reads it, or that it matches what the library later decides on. Edit and reject have no confirm and no digest binding, by the plan's fence.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py`:
    - The non-approve branch of `_cmd_roadmap_structural_candidate_decision` builds the view, prints the printout, and, for reject only, prints the drop note. It does this in place of the top-only disclosure.
    - The edit result renders the replacement's stack. `_render_structural_candidate_decision_result` stops calling the disclosure for `active_candidate` and takes the replacement's view from its caller.
    - `_cmd_roadmap_propose_candidate` decides whether the stack is structural and builds the view. `_render_candidate_proposal_result` takes that view (or `None`) and prints the printout in place of the own-route disclosure.
    - Import the derivation and `build_candidate_stack_view` by name if steps 2 and 5 have not already done so, so tests can stub both here.
  - `tests/cli/test_roadmap_cmd.py`: new tests, four updated existing tests, and the module docstring's list of deliberate real-orchestrator exceptions.
- **No other file changes.** The library needs no edit, because step 4's builder is used as is. `docs/cli/roadmap.md` needs no regeneration, because this step adds no flag and changes no help text. Nothing new is persisted.

## Implementation

**Behavior to deliver.**
- **Edit and reject, before the decision.** After the precheck, print step 4's printout for the candidate's whole stack, then call the library. Today's single disclosure call for these two decisions is gone.
- **Reject note.** After the printout and before the library call, print one labeled line that states what reject does. Recommended label: `reject effect:`. It must hold these facts:
  - the active candidate is released and nothing is promoted;
  - every unpromoted hop above the recorded root is dropped, with each id listed;
  - the hops stay stored as history.
- **Reject note details.**
  - The ids come from the view's hops, the same object the printout renders.
  - The note prints for every structural-decision reject, including a single-hop stack, with no branch on hop count.
  - Edit does not print it.
- **Edit result.** After `replacement: <id>`, print the printout of the replacement's whole stack in place of its top-only disclosure. Build that view from the stored replacement.
- **Proposal output.** Keep the existing `candidate proposal:`, `candidate:`, `predecessor:`, and `predecessor diff:` lines first. Then print the printout when the stored candidate's stack carries a structural hop, at any position. Every other proposal prints exactly what it prints today.
- **No digest, no confirm.** None of these surfaces prints the digest or adds a flag.

**Per-outcome contract.**

| Surface | Situation | Output | Exit |
| --- | --- | --- | --- |
| Edit or reject | Precheck refusal (step 2) | `error(...)`, no printout, builder not called | 2 |
| Edit or reject | View cannot be built | `error(...)`, no printout, no library call | 2 |
| Edit or reject | Library returns a non-stored outcome | printout, note (reject), existing result lines | existing mapping |
| Reject | Stored | printout, note, `structural decision: reject stored` | 0 |
| Edit | Stored, replacement view builds | printout, `structural decision: edit stored`, `replacement: <id>`, replacement's printout | 0 |
| Edit | Stored, replacement view cannot be built | the stored result lines, then `error(...)`. No top-only disclosure. | 1 |
| Proposal | Stored, stack carries a structural hop | the existing lines, then the printout | 0 |
| Proposal | Stored, no structural hop, route-less, no recorded root, or no candidate | today's output | existing mapping |
| Proposal | Stored, stack structural but derivation or view fails | the existing lines, then `error(...)` | 1 |

- **Failure before a write is 2; failure after a write is 1.** A view failure before any write refuses like step 5's approve. After a write, the stored result stays visible. The exit must not be 0, because the operator was not shown what the write covers. It must not be 2, because 2 means "refused with no write".

**Approach.** One way to do it:
- **Edit and reject.**
  - In the non-approve branch, after the precheck, build the view for the loaded candidate. Map `(ValueError, OSError)` to `error(str(exc))` and `_RC_USAGE`, before any output.
  - Print the printout, then the note for reject, then call the library as today.
  - Reuse the build-and-print helper step 5 landed for approve.
  - Edit only the non-approve arm, so step 5's approve arm is untouched.
- **Edit replacement.**
  - After a stored edit, build the replacement's view from `result.active_candidate` and pass it to `_render_structural_candidate_decision_result` as a keyword.
  - When the result carries a replacement, print `replacement: <id>` and then the printout. The renderer never builds a view.
  - On build failure, print the result lines without the printout, then `error(...)`, and return `_RC_INCOMPLETE`.
- **Proposal.**
  - When `result.candidate is not None`, ask the derivation for the candidate's own id and its `evidence.root_version_id`. If the stack is structural, build the view.
  - Pass the view, or `None`, to `_render_candidate_proposal_result` as a required keyword-only `stack_view`. The renderer prints the printout iff it is not `None`. The own-route check is deleted.
  - A derivation or build failure prints the stored lines, then `error(...)`, and returns `_RC_INCOMPLETE`.
  - A required keyword makes a forgotten caller a `TypeError`, not a silent skip. The `None` carve-out is then asserted explicitly.

**Rejected alternatives.**
- **Renderers build the view themselves.** That adds `plans_dir` and `slug` to renderers and puts disk reads and their errors inside rendering. Step 4's printout is a pure render, and the post-write failure paths need the handler anyway.
- **Keep the own-route check and add a stack check beside it.** The own route is the top hop's route, which is a subset of the stack question. Two copies of the predicate can drift.
- **Build the view for every stored proposal and test its structural ids.** The builder refuses a candidate with no recorded root and derives a cumulative diff. A stack with no structural hop must keep today's output with no new failure mode, so the cheap derivation gates first.
- **Print after the decision on edit and reject.** The order today is display first, and a test pins it for approve. For edit, a slow or failed backend call would leave the operator with nothing shown.
- **Fall back to the top-only disclosure when the view cannot be built.** That is the defect this step ends, hidden behind an error path.
- **Print the reject note only for multi-hop stacks.** It adds a branch. A single-hop reject also drops its one hop, so the uniform note is true.
- **A digest or confirm on edit or reject.** The plan fences it.

**Constraints (not free to vary).**
- **Approve is step 5's.** This step must not edit the approve branch or its output.
- **Precheck first.** An ineligible candidate never reaches the builder or the printout. Edit and reject must not spend a backend call or write before the view builds.
- **Step 4's printout, unchanged.** Call it as is. This step adds no per-hop printing code and no digest line.
- **Pure renderers.** `_render_candidate_proposal_result` and `_render_structural_candidate_decision_result` must not read disk or call the builder.
- **Carve-outs keep today's output exactly:**
  - a proposal whose stack has no structural hop, whose candidate is route-less or has no recorded root, or whose result has no candidate;
  - `--reject-candidate` and `--discard-candidate`;
  - the answered route's review, answer, and promote-review-seal output.
- **Post-write failure.** It must not exit 0 or 2, and it must not print the top-only disclosure as a substitute.
- **No library change.** Edit sourcing, reject and discard pointer release, and every guard are unchanged.

**Foundational logic and the sites.** The logic is "show the whole stack, not the top hop, wherever a structural approval is asked for or confirmed". I searched by identifier (`_render_structural_candidate_disclosure`, `_render_candidate_proposal_result`, `_render_structural_candidate_decision_result`) and by vocabulary (`predecessor diff:`, `structural proposal:`, `choices: approve`, disclosure, own route, top hop). All printers of that vocabulary are in `plan_tool/cli/roadmap_cmd.py`.
- **Changed here:** the edit and reject arm of the decision handler, the replacement branch of `_render_structural_candidate_decision_result`, and the proposal handler and its renderer.
- **Changed by step 5:** the approve arm.
- **Called by the printout, unchanged:** `_render_structural_candidate_disclosure`.
- **Kept as is, deliberately:**
  - `_render_candidate_review_result` and `_render_candidate_answer_result`, which print `predecessor diff:` for a stack the answered route refuses;
  - `_cmd_roadmap_candidate_resolution`, which prints `candidate rejection` or `candidate discard` for the standalone flags;
  - `_cmd_roadmap_promote_review_seal_id`.
- **Interim reachability.** Until step 7 removes the batch block, a stack with a structural hop under a presentation-only top exists only through test helpers. A real proposal can still show an own-structural single hop, which now goes through the printout.

## Tests

All tests go in `tests/cli/test_roadmap_cmd.py`.

**Builders.**
- **View stub.** One helper stubs `roadmap_cmd.build_candidate_stack_view`, keyed on `candidate.version_id`, and records each call's `plans_dir`, slug, and candidate. It returns a real step 4 view record over hand-built hops from `_stored_structural_cli_candidate()`. The real printout stays unstubbed, so assertions check output content. Hand-built hops need not be digestible.
- **Derivation stub.** Extend the step 2 helper that stubs the derivation in `roadmap_cmd`, so it can return a non-structural stack, an empty stack, or an error.
- **Real stack.** Reuse step 1's masking helper for C1-structural / C2-presentation-only, with the `storefront` slug and `tmp_path / "plans"`.

**Unit cases.**
- `test_edit_and_reject_print_every_hop_of_the_stack_before_the_decision` — parametrized over edit and reject. Hop ids appear oldest first and before the decision call, and the builder receives the loaded candidate with the command's `plans_dir` and slug.
- `test_reject_note_lists_every_dropped_hop_and_says_nothing_is_promoted` — the line found by its label names every hop id from the view, sits after the printout and before the decision line, and says nothing is promoted.
- `test_reject_note_prints_for_a_single_hop_stack_too` — parametrized over 1 and 3 hops. This pins that the note has no hop-count branch.
- `test_edit_and_standalone_reject_and_discard_carry_no_reject_note_and_no_stack_printout` — edit prints no note. `--reject-candidate` and `--discard-candidate` print no printout and no note, with the builder stubbed to fail if called. This asserts the plan's fence as a carve-out.
- `test_answered_route_output_carries_no_stack_printout` — `_render_candidate_review_result`, `_render_candidate_answer_result`, and `_cmd_roadmap_promote_review_seal_id` print exactly their current lines, with the builder and the derivation stubbed to fail if called. This pins the owner's narrowed decision 2.
- `test_edit_result_prints_the_replacements_whole_stack_not_its_top_hop_alone` — the builder is called with the library's `active_candidate`. After `replacement: <id>`, the lower hop's id appears and the edited candidate's id does not.
- `test_edit_and_reject_refuse_before_any_output_and_any_decision_when_the_stack_view_cannot_be_built` — the builder raises `CandidateReviewError`. Status is 2, an error is on stderr, there is no printout, and the library is not called, so no backend call happens for edit.
- `test_stored_edit_with_an_unbuildable_replacement_view_reports_the_write_and_exits_incomplete` — the builder raises for the replacement only. The `structural decision: edit stored` and `replacement:` lines print, the top-only disclosure does not (`structural proposal: stored` appears once, from the pre-decision printout), an error goes to stderr, and the status is 1. This pins the write-happened failure channel.
- `test_proposal_output_prints_the_stack_when_a_lower_hop_is_structural_though_the_candidates_own_route_is_not` — parametrized over `propose_candidate` and `revise_feedback`. The derivation stub says structural and the own route is presentation-only. The printout appears after the `predecessor diff:` line. This is the reported defect's shape.
- `test_proposal_output_for_an_own_structural_candidate_keeps_the_disclosure_lines_through_the_printout` — `structural proposal: stored` and `choices: approve, edit, reject` still print.
- `test_proposal_output_keeps_todays_output_when_the_stack_has_no_structural_hop` — parametrized over an all-presentation stack, a route-less candidate, a candidate with no recorded root, and a result with `candidate=None`. Output has no `structural proposal:`, the builder is never called, and the `candidate=None` case never calls the derivation. This is the deliberate carve-out.
- `test_proposal_stack_is_derived_from_the_candidates_own_id_and_recorded_root` — the stub records its keywords: tip is the candidate's id and root is `evidence.root_version_id`. This rules out reading the head or the admission pointer.
- `test_proposal_stack_failure_after_a_stored_proposal_prints_the_stored_lines_and_exits_incomplete` — parametrized over the derivation raising `CandidateProposalError` and the builder raising `CandidateReviewError`. The stored lines print, an error goes to stderr, there is no top-only disclosure, and the status is 1.

**Real-orchestrator cases.** Add all three to the module docstring's list of deliberate real-orchestrator exceptions in the same edit. Each covers a seam that stubs cannot show.
- `test_reject_over_a_real_stack_prints_every_hop_and_the_drop_note_before_releasing_the_pointer` — `--candidate-decision reject` over the real stack exits 0. Both hop ids appear in order before `structural decision: reject stored`. The note lists both. The stack's `view.digest`, computed by the test, is absent from the output. The pointer is released and both hops stay stored.
- `test_proposal_output_over_a_real_stack_with_a_structural_lower_hop_prints_the_whole_stack` — real stored C1/C2 records with `run_initial_candidate_proposal` stubbed to return C2 as stored. Real derivation, builder, and printout show both hop ids and C1's structural route. The digest is absent. C2's own route is presentation-only, so the old own-route check would have printed nothing structural.
- `test_edit_over_a_real_stack_prints_the_replacements_stack_built_from_the_stored_replacement` — pass the invoker through `cmd_roadmap`, reusing the reply in step 2's `test_structural_edit_over_a_structural_lower_hop_accepts_a_presentation_only_replacement`. After `replacement:`, the output holds C1's id and the replacement's id but not C2's id. This pins that the view is built from the stored replacement, after the library returns.

**Existing tests that must change.** A red test here is expected. Read each to decide whether the printout adds lines or the test needs a stub.
- `test_structural_candidate_edit_requires_one_correction_and_never_promotes` — stub the builder. Confirm the `stored route: "structural"` count of 2 still holds under the printout, and update it if the printout adds route lines.
- `test_structural_decision_results_remain_distinct_without_promotion` — stub the builder on the reject and edit rows. Approve rows are step 5's.
- `test_structural_decision_refuses_an_ineligible_candidate_before_any_disclosure_or_decision` — add a builder stub that fails if called, so "before any output" also covers the printout.
- `test_presentation_candidate_keeps_the_existing_proposal_output` — pass `stack_view=None` explicitly.

**Verify by mutation.** Break the code each of these ways and confirm each turns a test red:
- revert edit and reject to the top-only disclosure;
- print the reject note only when the stack has more than one hop;
- print the note on edit or on standalone `--reject-candidate`;
- build the replacement's view from the edited candidate;
- call the library before printing;
- restore the own-route check on the proposal output;
- build the view for every candidate, with no derivation gate;
- fall back to the top-only disclosure when the view fails;
- exit 0 after a post-write failure;
- print the digest;
- call the builder before the precheck.

### Tests for this step

- **Tests added or changed.** About 12 unit cases, 3 real-orchestrator cases, and 4 updated existing tests, all in `tests/cli/test_roadmap_cmd.py`. They cover the printout on each surface, the reject note, the replacement's stack, the before-write and after-write failure channels, the carve-outs, and the derivation's inputs.
- **Green gate.** Every test above and the rest of the suite must be green before the step is done. The step's `test_command` is `uv run pytest tests/ -q -n auto`. The added tests also satisfy the plan's test-authoring gate.

## Acceptance criteria

- **Edit and reject.** Over a real stack, both print every hop id, oldest first, before the decision result. Neither calls the library when the view cannot be built (status 2, no output).
- **Reject note.** Every structural-decision reject prints one labeled line listing every dropped hop and saying nothing is promoted. Edit, `--reject-candidate`, and `--discard-candidate` print neither the note nor the printout.
- **Answered route.** `--review-candidate`, `--answer-question`, and `--promote-review-seal` print exactly today's output and call neither the builder nor the derivation.
- **Edit result.** The replacement's whole stack prints, built from the stored replacement. A view failure after the write exits 1, prints the stored result lines, and prints no top-only disclosure.
- **Proposal output.** A stored candidate whose stack carries a structural hop prints the printout, including when its own route is presentation-only. Every other proposal prints exactly today's output.
- **Digest and confirm.** No output added here prints the digest, and no flag is added.
- **Purity.** The two renderers read no disk and call no builder.
- **Files.** `git diff --name-only` lists only `plan_tool/cli/roadmap_cmd.py` and `tests/cli/test_roadmap_cmd.py`. The approve arm and `docs/cli/roadmap.md` are unchanged.
- **Suite.** `uv run pytest tests/ -q -n auto` passes.

## References

- [docs/implementation-plans/2-roadmap-stack-aware-approval.md](../../2-roadmap-stack-aware-approval.md) — § "Architecture" owner decision 2 and § "Design decisions" (Stack view) name the surfaces and the reject note.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/04-build-whole-stack-view-its-digest-its.md](04-build-whole-stack-view-its-digest-its.md) — the view, builder, and printout this step renders.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/05-split-structural-approve-two.md](05-split-structural-approve-two.md) — the approve branch this step leaves alone, and the build-failure exit it mirrors.
- [docs/implementation-plans/plan-details/roadmap-stack-aware-approval/02-make-review-side-guards-stack-aware.md](02-make-review-side-guards-stack-aware.md) — the precheck and the derivation stub helper.
- [handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md](../../../../handoffs/2026-09-23-roadmap-structural-feedback-approval-code-review.md) — the P2.1 defect and the owner decisions.
- [plan_tool/cli/roadmap_cmd.py](../../../../plan_tool/cli/roadmap_cmd.py) — `_cmd_roadmap_structural_candidate_decision`, `_render_structural_candidate_decision_result`, `_cmd_roadmap_propose_candidate`, `_render_candidate_proposal_result`.
- [plan_tool/roadmap_candidate_review.py](../../../../plan_tool/roadmap_candidate_review.py) — `_edit_structural_candidate` and `reject_candidate_review`, for what each result carries.

## Applicable guardrails

- **The plan's "Scope guardrails", "Not allowed": no confirm step for edit or reject.** This step adds no flag, no digest, and no confirm. The printout on these decisions is informational only.
- **The plan's "Scope guardrails", "Not allowed": no stack output on `--reject-candidate`, `--discard-candidate`, or the answered route.** Those handlers and renderers are untouched. Only the structural decision's reject carries the note.
- **The plan's "Scope guardrails", "Not allowed": no separate read-only show command.** This step adds no command.
- **The plan's "Scope guardrails", "Not allowed": no quality judgment, no cumulative classifier, no second gate.** The proposal gate reads step 1's derivation over stored routes, and the printout describes the stack without judging it.
- **The plan's "Scope guardrails", "Not allowed": no new persisted stack or binding field, and no wider run-log coverage.** Nothing is stored, and no run log is added.
- **The plan's "Scope guardrails", "Not allowed": no behavior change for legacy candidates that have no route.** A route-less candidate, a candidate with no recorded root, and an all-presentation stack keep today's output, each asserted as a carve-out.
- **The plan's "Architecture", owner decision 2.** Only the structural decision and a structural-stack proposal are presenting surfaces.
- **The plan's "Scope guardrails", ordering fence.** The batch block stays until step 7. This step lands the presentation that step 7 depends on.
- **The plan's "Out of scope": edit sourcing and reject and discard pointer release.** The library is unchanged.

## Deferred

- Both approve invocations, the digest line, and the confirm flag — step 5 owns them.
- Removing the batch block, and end-to-end tests of the stack across the direct, answered, edited, and recovered routes — step 7 owns them. This step's real edit test pins the replacement's presentation only.
- Documenting the whole-stack output and the reject note in `docs/how-to/roadmap.md` and the other docs — step 8 owns it. `docs/cli/roadmap.md` needs no regeneration here.
- A confirm step or digest for edit or reject, and a separate show command — refused by the plan, not deferred. No backlog entry is filed.
- Stack output on `--reject-candidate`, `--discard-candidate`, and the answered route, including presentation-only hops lower in a stack there — deliberately not built. No backlog entry is filed.
- Rewording the disclosure's `promotion effects:` line for edit and reject — not built. Step 4's printout keeps every disclosure line, and the reject note states what reject does.
- Run-log lifecycles for the decision commands — out of scope. The owner tracks them separately.
