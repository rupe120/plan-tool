> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 11 — Expose enrollment, candidate review, answers, and promotion in roadmap CLI without changing the HTML overwrite or other modes

## Summary

Add five explicit lifecycle actions to `plan_tool/cli/roadmap_cmd.py`: enrollment, candidate proposal, candidate review, reviewer answer, and review-seal promotion. Keep `cmd_roadmap()` as thin argument-to-domain routing, with exclusive preflight before path resolution or runner calls. Preserve every current mode, especially the `--view html` default overwrite path in `_cmd_roadmap_view()`. On green, one fake-backend CLI test drives the full accepted-head-to-promoted-replacement path through the real downstream view reader.

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

Steps 3, 7, 8, and 9 provide the immutable lifecycle boundaries, but `plan_tool/cli/roadmap_cmd.py:cmd_roadmap()` currently exposes only stage, seed, baseline, local-revision, evidence, and view routes. Without a narrow CLI path, an operator cannot enroll an accepted root, request a candidate, see and answer its question, or explicitly promote its sealed replacement. The new surface must make that sequence usable without treating the existing `--enroll-baselines`, `--revise-feedback`, or HTML writer as substitutes.

## Input

- **Accepted root:** Step 3 supplies explicit immutable-root enrollment and accepted-head resolution. This step passes only the roadmap slug to enrollment and does not reuse `plan_tool/roadmap.py:enroll_roadmap_baselines()`.

- **Initial candidate:** Step 7 supplies the bounded proposal entry point. `--propose-candidate` passes one `ARTIFACT:FEEDBACK_ID` selector and the existing `cmd_roadmap()` invoker seam.

- **Review and replacement:** Step 8 supplies candidate-version-bound question generation, answer recording, same-lineage replacement, and domain-provided persisted predecessor diffs. The CLI must carry the selected candidate version or question identity and reviewer answer without interpreting its meaning, and it must present the stored comparison for both the initial and replacement versions before promotion.

- **Promotion:** Step 9 supplies explicit review-seal promotion. The CLI passes one review-seal identity and lets the domain boundary decide whether promotion succeeds.

- **Reader proof and writer fence:** Step 4 makes legacy writers refuse as soon as a roadmap enrolls, while step 10 makes ordinary roadmap views read the accepted head. The CLI test must exercise both effects through their existing command routes.

- **Current command seams:** `plan_tool/cli/roadmap_cmd.py:register()`, `cmd_roadmap()`, `_reject_incompatible_broad_modes()`, `_broad_mode_companions_present()`, and `_cmd_roadmap_view()` define the parser, dispatch, conflict, and HTML boundaries that remain in force.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Add the lifecycle flags, exclusive preflight, domain dispatch, concise result rendering, and command documentation while preserving existing mode handling.
  - `tests/cli/test_roadmap_cmd.py` — Extend parser and dispatch characterization tests, add no-side-effect conflict cases, and drive the representative lifecycle with a fake backend.
  - `CAPABILITIES.md` — Update the `Architecture roadmap` capability’s surface list and describe the explicit immutable candidate lifecycle.
  - `TESTING.md` — Document the fake-invoker seam and test boundary for roadmap candidate CLI actions.

## Implementation

- **Expose five separate actions.** Add `--enroll-version`, `--propose-candidate ARTIFACT:FEEDBACK_ID`, `--review-candidate CANDIDATE_VERSION_ID`, `--answer-question QUESTION_ID --answer TEXT`, and `--promote-review-seal REVIEW_SEAL_ID` to `plan_tool/cli/roadmap_cmd.py:register()`. These names make the state transition explicit and keep selection identity separate from the reviewer's answer text.

- **Keep enrollment meanings separate.** `--enroll-version` must call step 3’s immutable-root enrollment boundary. `--enroll-baselines` must retain its current call to `plan_tool/roadmap.py:enroll_roadmap_baselines()` and its baseline-only output; neither action may act as an alias for the other.

- **Make lifecycle actions exclusive.** Each new action must reject every existing broad or exclusive roadmap action, every other lifecycle action, `--from-existing`, `--from-stage`, `--view`, `--mode`, `--id`, `--output`, and `-y` before resolving paths, reading artifacts, rendering HTML, opening a run log, or invoking a backend. Require exactly one `--answer-question` and one `--answer` when recording an answer.

- **Preserve the existing broad-mode grammar.** Keep `_TrackRoadmapMode`, `_reject_incompatible_broad_modes()`, `_BROAD_MODE_ARGUMENTS` coverage, and the existing broad-mode usage grouping for stage, seed, and ordinary view actions. The new lifecycle actions are explicit exclusive routes; do not turn current actions into a different parser mode family.

- **Route only through owning domain boundaries.** Add private command handlers beside `_cmd_roadmap_enroll_baselines()` and `_cmd_roadmap_revise_feedback()` that forward the slug, identity input, resolved paths, and optional `invoker` to the step-owned domain entry points. Do not duplicate candidate storage, review-seal validation, gate checks, accepted-head selection, or answer-incorporation rules in `plan_tool/cli/roadmap_cmd.py`.

- **Reuse the existing actions for explicit continuation.** Repeating `--propose-candidate` for the same stable feedback identity must resume or return its one admitted lineage, never create a branch. Repeating `--answer-question` with the same question and byte-identical answer must continue or return that answer's one replacement and seal; different answer bytes refuse. Do not add a resume flag, interactive retry, or automatic loop in the CLI.

- **Keep the invoker seam narrow.** `--propose-candidate`, `--review-candidate`, and `--answer-question` must receive the optional `invoker` already accepted by `cmd_roadmap()`. Enrollment and promotion must not invoke a backend. The CLI must not read from a TTY or decide whether an answer or question is useful.

- **Render usable, bounded comparisons.** When candidate review succeeds, print the stored candidate-version and predecessor identities, the domain-provided persisted deterministic diff with its complete changed-row before/after values and relation changes, and the review question with its anchor. When an answer creates a replacement and seal, print that replacement's stored version identity, the domain-provided persisted predecessor diff, and the exact seal identity for the next command. Keep rendering to domain-provided facts: do not print full unchanged artifact contents, reconstruct a diff from live artifacts, or infer that a refusal is safe to retry. The answer command's replacement comparison is the final reviewer-visible candidate handoff before explicit promotion.

- **Preserve exit and interruption handling.** For proposal, question, and replacement results, map `stored` to exit 0, `response-rejected` and `failed` to the existing incomplete exit 1, and `refused` to the existing usage/refusal exit 2. Keep `KeyboardInterrupt` on exit 130 outside the domain result set. Render the phase and exact outcome so an operator can distinguish a response that a later explicit command may replace from a deterministic refusal; do not imply or perform an automatic retry. Ensure every new branch is covered by the same interruption handling as the current broad-mode dispatch.

- **Leave HTML behavior alone.** Do not change `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view()`, its `render_roadmap_html()` call, `review_path()` default destination, `atomic_write_text()` use, `--output -` behavior, or its existing error mapping. A lifecycle action paired with `--view html` must reject before that path runs.

- **Update capability and testing guidance with the landed surface.** In `CAPABILITIES.md`’s `Architecture roadmap` section, add the version and candidate modules delivered by steps 3 and 5 through 9 and describe the five CLI actions as an explicit, ordered lifecycle. In `TESTING.md`, document that CLI lifecycle tests pass a fake through `cmd_roadmap(..., invoker=...)`, while enrollment and promotion assert that no backend call occurs.

## Tests

- `tests/cli/test_roadmap_cmd.py` — Extend the existing parser and dispatch net without changing unrelated command behavior.

### Tests for this step

- `test_candidate_lifecycle_flags_parse_with_their_required_arguments` — Each new action parses to the expected namespace fields, and answer recording requires both its question identity and answer text.

- `test_enroll_version_dispatches_without_backend_or_stage_run` — Immutable-root enrollment receives the slug and plans directory while neither the stage runner nor candidate runner is called.

- `test_propose_candidate_forwards_selector_and_fake_invoker` — The selected feedback identity and injected fake reach step 7’s proposal boundary unchanged.

- `test_repeated_propose_candidate_and_exact_answer_replay_reenter_the_same_lineage` — The existing flags return or continue the admitted proposal and answer-bound replacement, while changed answer bytes refuse and no sibling model call is made after a stored result.

- `test_review_candidate_prints_the_stored_version_identity_diff_and_question` — Candidate review invokes only step 8's question path and prints its domain-provided candidate/predecessor identities, complete persisted diff, question identity, anchor, and text without consulting live artifacts.

- `test_answer_question_forwards_answer_and_prints_the_sealed_replacement_comparison` — The CLI forwards one answer unchanged without a content, length, or semantic filter, then prints the domain-provided replacement version identity, persisted diff, and exact review-seal identity.

- `test_promote_review_seal_dispatches_without_backend` — Promotion forwards exactly one review-seal identity and makes no model or stage call.

- `test_candidate_lifecycle_actions_reject_companion_modes_before_side_effects` — Every lifecycle action conflicts with existing roadmap modes and sibling lifecycle actions before paths, logs, renderers, or domain runners run.

- `test_answer_question_requires_one_question_and_one_answer` — Missing or repeated command-line members of the answer pair return a usage error without creating a replacement.

- `test_candidate_action_cannot_reach_html_writer` — A lifecycle action combined with `--view html` returns a usage error and never calls `render_roadmap_html()`, `review_path()`, or `atomic_write_text()`.

- `test_cli_candidate_lifecycle_promotes_only_the_reviewer_displayed_answer_incorporated_replacement` — A representative fixture enrolls, proposes, reviews, answers, asserts the answer output displays the same replacement version and persisted diff bound by the seal, promotes that exact version, and then reads it through the real ordinary roadmap view while the prior candidate and accepted root remain unchanged.

- `test_candidate_model_route_outcomes_map_to_existing_cli_exits` — `stored`, `response-rejected`, `failed`, and `refused` map to 0, 1, 1, and 2 with the exact phase/outcome rendered, while interruption remains 130.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan-tool roadmap <slug> --enroll-version` enrolls the immutable root through step 3’s boundary and does not invoke a backend.

- `plan-tool roadmap <slug> --propose-candidate <artifact>:<feedback-id>` creates only one admitted inert-candidate lineage through step 7 and explicitly re-enters that lineage on repetition.

- `plan-tool roadmap <slug> --review-candidate <candidate-version-id>` presents the stored candidate's identity, persisted predecessor diff, and question without moving the accepted head.

- `plan-tool roadmap <slug> --answer-question <question-id> --answer <text>` records the reviewer answer, requests only the same-lineage replacement candidate version, and presents its persisted diff and seal identity before promotion; exact replay continues or returns it without changing the answer.

- `plan-tool roadmap <slug> --promote-review-seal <seal-id>` can move the accepted head only through step 9’s exact review-seal promotion boundary and invokes no backend.

- Any lifecycle action combined with another roadmap action, modifier, or `-y` returns a usage error before side effects.

- Proposal, question, and replacement commands use the shared four-value domain outcomes and the fixed 0/1/1/2 exit mapping; none retries a rejected response.

- The existing `tests/cli/test_roadmap_cmd.py:TestHtmlView` cases remain green without changing the HTML write, overwrite, output, or error behavior.

- The representative CLI lifecycle test proves that an ordinary roadmap view reads the promoted replacement through step 10’s accepted-head reader path.

- `tests/test_capability_catalog.py:test_check_real_repo_catalog_is_honest` remains green after `CAPABILITIES.md` names the landed surfaces.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, allowed behavior changes:** Limit this step to the new lifecycle command surface and its existing reader and writer fences. Keep unversioned roadmap behavior unchanged.

- **The plan’s “## Scope guardrails”, lifecycle ordering:** Expose the actions as separate transitions so candidate creation, review, answer, replacement, sealing, and promotion cannot be requested as one combined command.

- **The plan’s “## Scope guardrails”, model authority:** Send model-facing actions only to the bounded proposal and review boundaries. The CLI must not turn model output into canonical writes or promotion authority.

- **The plan’s “## Scope guardrails”, distinct bindings:** Preserve separate command inputs for feedback selection, candidate-version identity, question identity, answer text, and review-seal identity. Do not substitute one identity for another.

- **The plan’s “## Scope guardrails”, inspectable context:** Do not add CLI flags for context widening, summary input, or alternate candidate authority.

- **The plan’s “## Scope guardrails”, validation boundary:** Keep semantic and quality judgment out of CLI parsing and rendering. Let the dependency-step contracts return mechanical acceptance or refusal.

- **The plan’s “## Out of scope”, smallest functional path:** Do not add batch review, automatic promotion, rollback controls, history UI, or a general workflow framework.

## Deferred

- Additional version-aware readers and workflow interfaces — Step 10 supplies the required downstream reader proof; broader migration needs separate scope.

- Question usefulness measurement — fake-backend tests prove identity, ordering, and immutability, not real-model question quality.
