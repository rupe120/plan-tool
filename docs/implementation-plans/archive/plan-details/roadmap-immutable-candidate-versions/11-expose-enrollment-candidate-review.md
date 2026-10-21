> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 11 — Expose enrollment, candidate review, answers, and promotion in roadmap CLI without changing the HTML overwrite or other modes

## Summary

Add five explicit lifecycle actions to `plan_tool/cli/roadmap_cmd.py`: enrollment, candidate proposal, candidate review, reviewer answer, and review-seal promotion. Keep `cmd_roadmap()` as thin argument-to-domain routing, with exclusive preflight before path resolution or runner calls. Preserve every current mode, especially the `--view html` default overwrite path in `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view()`. On green, one fake-backend CLI test drives the accepted-head-to-promoted-replacement path through the real downstream view reader.

## Table of Contents

- [Summary](#summary) — The CLI outcome and compatibility boundary.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why the completed lifecycle needs an operator-facing route.
- [Input](#input) — The upstream lifecycle contracts and current CLI seams.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four existing files this step updates.
- [Implementation](#implementation) — Lifecycle actions, dispatch rules, and unchanged modes.
- [Tests](#tests) — CLI characterization and end-to-end fake-backend coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable command and compatibility results.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that constrain this CLI surface.
- [Deferred](#deferred) — Related workflow work outside this command proof.

## Why

Steps 3 through 10 provide the immutable lifecycle boundaries, but `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()` exposes only stage, seed, baseline, local-revision, evidence, and view routes. Without a narrow CLI path, an operator cannot enroll an accepted root, request a candidate, review and answer its question, or explicitly promote its sealed replacement. The new surface must make that sequence usable without treating `--enroll-baselines`, `--revise-feedback`, or the HTML writer as substitutes.

## Input

- **Accepted-head contract:** Step 3 supplies immutable version selection, while step 4 supplies root enrollment and the enrolled-roadmap writer fence. This step passes only the requested roadmap identity to those boundaries.

- **Initial candidate:** Step 7 supplies the bounded proposal route. `--propose-candidate` carries one `ARTIFACT:FEEDBACK_ID` selector and the existing `cmd_roadmap()` invoker seam.

- **Review and replacement:** Step 8 supplies candidate-bound question generation, immutable answer storage, stored question-and-answer-pair resolution, same-lineage replacement, persisted predecessor diffs, and review seals. The CLI carries the question id and exact answer text without accepting question prose or interpreting either value's meaning.

- **Promotion:** Step 9 supplies exact review-seal promotion and requires an active matching writer token. The CLI owns the existing roadmap writer guard for this action, holds it through promotion's journaled final recheck, and passes the seal identity with that token.

- **Reader proof:** Step 10 makes ordinary roadmap views select enrolled content through the accepted head. The representative CLI test must exercise that real reader after promotion.

- **Current command seams:** `plan_tool/cli/roadmap_cmd.py:register()`, `cmd_roadmap()`, `_TrackExclusiveOption`, `_option_occurrences()`, `_reject_incompatible_broad_modes()`, `_broad_mode_companions_present()`, and `_cmd_roadmap_view()` define the parser, dispatch, conflict, and HTML boundaries that remain in force.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Add lifecycle flags, exclusive preflight, domain dispatch, concise result rendering, and command help while preserving current modes.
  - `tests/cli/test_roadmap_cmd.py` — Extend parser and dispatch characterization, add no-side-effect conflict cases, and drive the representative lifecycle with a fake backend.
  - `CAPABILITIES.md` — Update the `Architecture roadmap` surface list and describe the explicit immutable candidate lifecycle.
  - `TESTING.md` — Document the fake-invoker seam and test boundary for roadmap candidate CLI actions.

## Implementation

- **Foundational logic:** Route exactly one lifecycle action through its owning domain boundary only after exclusive preflight succeeds.

- **Expose five separate actions.** Add `--enroll-version`, `--propose-candidate ARTIFACT:FEEDBACK_ID`, `--review-candidate INITIAL_CANDIDATE_VERSION_ID`, `--answer-question QUESTION_ID --answer TEXT`, and `--promote-review-seal REVIEW_SEAL_ID` in `plan_tool/cli/roadmap_cmd.py:register()`. Keep the selection identities and reviewer answer as separate inputs.

- **Track exclusive occurrences.** Use `plan_tool/cli/roadmap_cmd.py:_TrackExclusiveOption` and `_option_occurrences()` for every new lifecycle input that needs an exact occurrence count. Seed their occurrence defaults beside the existing receipt, rewrite, and reopen defaults so duplicate flags refuse before dispatch.

- **Keep enrollment meanings separate.** `--enroll-version` must use step 4’s immutable-root enrollment boundary. `--enroll-baselines` must retain its call to `plan_tool/roadmap.py:enroll_roadmap_baselines()` and its baseline-only output; neither action may alias the other.

- **Make lifecycle actions exclusive.** Each lifecycle action must reject every current broad or exclusive roadmap action, sibling lifecycle action, `--from-existing`, `--from-stage`, `--view`, `--mode`, `--id`, `--output`, and `-y`. Reject before resolving repository paths, reading artifacts, rendering HTML, opening a run log, or invoking a backend. `--answer-question` and `--answer` must each occur exactly once.

- **Preserve the broad-mode grammar.** Keep `_TrackRoadmapMode`, `_reject_incompatible_broad_modes()`, and the current grouped usage behavior for stage, seed, and ordinary view actions. The new actions are exclusive routes, not additions to the broad-mode family.

- **Delegate rather than reimplement.** Add focused command handlers near `_cmd_roadmap_enroll_baselines()` and `_cmd_roadmap_revise_feedback()` that forward the slug, selected identity, resolved paths, and optional invoker to the step-owned boundaries. `plan_tool/cli/roadmap_cmd.py` must not validate candidate storage, review seals, gates, accepted-head selection, answer incorporation, or context membership.

- **Own promotion's existing writer lease.** After exclusive CLI preflight and path resolution, the promotion handler must acquire `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()` for the selected slug, pass its matching active token to step 9, and keep the context open until promotion returns after its final journal recheck. Do not acquire this guard for proposal, question, or answer model calls, and do not add another lock or lease type.

- **Keep the fixed admission deterministic.** Repeating `--propose-candidate` for the admitted feedback identity must continue or return its lineage, never create a branch. A different feedback selector for that roadmap must refuse through step 7 before backend invocation, both before and after promotion; the CLI adds no clear-or-replace operation for the admission. Replaying `--answer-question` with the same question id and unchanged answer bytes must continue or return the replacement built from the same stored question-and-answer pair; changed answer bytes must refuse. Do not add a resume flag, TTY retry, automatic loop, or sequential multi-feedback lifecycle.

- **Keep the backend seam narrow.** Proposal, question, and answer routes must receive the optional `invoker` already accepted by `cmd_roadmap()`. Enrollment and promotion must not invoke a backend. The CLI must not read from a TTY or judge whether an answer or question is useful.

- **Render only stored review facts.** Successful review must print the candidate and predecessor identities, the persisted predecessor diff, and the stored question identity, anchor, and text. Successful answer processing must print the replacement identity, its persisted diff, and its exact seal identity. Do not print unchanged artifact contents, reconstruct a diff from live artifacts, or infer whether a refusal is safe to retry.

- **Keep exit and interruption handling consistent.** Map the shared proposal and review outcomes from steps 7 and 8 so `stored` returns 0, `response-rejected` and `failed` return 1, and `refused` returns 2. Preserve the current exit 130 handling for `KeyboardInterrupt`, outside the domain result set.

- **Leave HTML behavior alone.** Do not change `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view()`, its `plan_tool/roadmap_html.py:render_roadmap_html()` call, `plan_tool/roadmap_html.py:review_path()` default destination, `plan_tool/fileio.py:atomic_write_text()` use, `--output -` behavior, or its error mapping. A lifecycle action paired with `--view html` must reject before that path runs.

- **Update the catalog and test guide.** Add `plan_tool/roadmap_versions.py`, `plan_tool/roadmap_candidate_context.py`, `plan_tool/roadmap_candidate.py`, `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_review.py`, and `plan_tool/roadmap_version_promotion.py` to the `CAPABILITIES.md` architecture-roadmap surface once the dependency steps land. In `TESTING.md`, document that lifecycle CLI tests inject a fake through `cmd_roadmap(..., invoker=...)`, while enrollment and promotion assert that no backend call occurs.

## Tests

- `tests/cli/test_roadmap_cmd.py` — Extend the existing parser and dispatch net without changing unrelated command behavior.

### Tests for this step

- `test_candidate_lifecycle_flags_preserve_exact_occurrences_and_required_answer_pair` — Each lifecycle flag parses to its expected namespace fields, repeated exclusive values remain visible to preflight, and answer recording requires one question identity and one answer.

- `test_new_lifecycle_options_do_not_join_the_broad_mode_group` — Lifecycle actions remain outside the `_TrackRoadmapMode` grammar while the existing broad-mode usage group remains intact.

- `test_enroll_version_dispatches_without_backend_or_stage_run` — Immutable-root enrollment receives the slug and plans directory while neither the stage runner nor a candidate runner is called.

- `test_propose_candidate_forwards_selector_and_fake_invoker` — The selected feedback identity and injected fake reach step 7’s proposal boundary unchanged.

- `test_review_candidate_prints_stored_identity_diff_and_question` — Candidate review prints only domain-provided candidate and predecessor identities, persisted diff, question identity, anchor, and text.

- `test_answer_question_forwards_exact_pair_and_prints_sealed_replacement` — The CLI forwards the exact question-and-answer pair and prints its sealed replacement.

- `test_promote_review_seal_holds_matching_writer_guard_through_dispatch_without_backend` — Promotion forwards one seal identity with the active matching token, keeps the guard held until the domain call returns, and makes no model or stage call.

- `test_candidate_lifecycle_actions_reject_companion_modes_before_side_effects` — Every lifecycle action conflicts with existing roadmap modes and sibling lifecycle actions before path resolution, logs, renderers, or domain runners run.

- `test_cli_candidate_lifecycle_promotes_only_the_reviewer_displayed_answer_incorporated_replacement` — A representative fixture enrolls, proposes, reviews, answers, verifies the displayed replacement and diff bind to the seal, promotes that exact replacement, and reads it through the real ordinary roadmap view while earlier versions remain unchanged.

- `test_candidate_model_route_outcomes_map_to_existing_cli_exits` — `stored`, `response-rejected`, `failed`, and `refused` map to 0, 1, 1, and 2 with the outcome rendered, while interruption remains 130.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan-tool roadmap <slug> --enroll-version` enrolls an immutable root through step 4’s boundary and does not invoke a backend.

- `plan-tool roadmap <slug> --propose-candidate <artifact>:<feedback-id>` creates or re-enters the roadmap's one fixed admitted inert-candidate lineage through step 7; a different feedback refuses before backend work, including after promotion.

- `plan-tool roadmap <slug> --review-candidate <initial-candidate-version-id>` presents the stored initial candidate identity, persisted predecessor diff, and question without moving the accepted head; a replacement candidate identity refuses before backend work.

- `plan-tool roadmap <slug> --answer-question <question-id> --answer <text>` records or resumes only the same-lineage answer-driven replacement; step 8 supplies the replacement model with the exact stored question id, anchor, opaque text, answer id, and answer text before the CLI presents the persisted diff and seal identity.

- `plan-tool roadmap <slug> --promote-review-seal <seal-id>` holds the existing matching roadmap writer guard through step 9’s final recheck, moves the accepted head only through that exact review-seal promotion boundary, and invokes no backend.

- Any lifecycle action combined with another roadmap action, modifier, duplicate exclusive input, or `-y` returns a usage error before side effects.

- The existing `tests/cli/test_roadmap_cmd.py:TestHtmlView` cases remain green without changing HTML write, overwrite, output, or error behavior.

- The representative lifecycle test proves that an ordinary roadmap view reads the promoted replacement through step 10’s accepted-head reader path.

- `tests/test_capability_catalog.py:test_check_real_repo_catalog_is_honest` remains green after `CAPABILITIES.md` names the landed surfaces.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, allowed behavior changes:** Limit this step to the lifecycle command surface and its existing reader and writer fences. Keep unversioned roadmap behavior unchanged.

- **The plan’s “## Scope guardrails”, lifecycle ordering:** Expose separate transitions so a candidate, question, answer, replacement, seal, and promotion cannot be requested as one combined command.

- **The plan’s “## Scope guardrails”, model authority:** Send model-facing actions only to the bounded proposal and review boundaries. The CLI must not turn model output into canonical writes or promotion authority.

- **The plan’s “## Scope guardrails”, distinct bindings:** Preserve separate command inputs for feedback selection, candidate identity, question identity, answer text, and seal identity.

- **The plan’s “## Scope guardrails”, inspectable context:** Do not add CLI flags for context widening, summary input, or alternate candidate authority.

- **The plan’s “## Scope guardrails”, validation boundary:** Keep semantic and quality judgment out of CLI parsing and rendering. Let dependency-step contracts return mechanical acceptance or refusal.

- **The plan’s “## Out of scope”, smallest functional path:** Do not add batch review, automatic promotion, rollback controls, history UI, or a general workflow framework.

## Deferred

- Additional version-aware readers and workflow interfaces — Step 10 supplies the required downstream reader proof; broader migration needs separate scope.

- Question usefulness measurement — Fake-backend tests prove identity, ordering, and immutability, not real-model question quality.
