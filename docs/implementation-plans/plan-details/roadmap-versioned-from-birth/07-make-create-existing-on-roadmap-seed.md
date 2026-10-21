# Step 7 — Make create --from-existing on a roadmap seed read research targets and invalidation state from the accepted version

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step moves the two roadmap reads inside `create --from-existing` onto the accepted version. `plan_tool/create.py:_load_roadmap_research_targets` stops reading the top-level `02-constraints.md` and `03-components.md`. It reads the same two artifacts from the accepted version's stored bytes. `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed` stops reading the top-level `04-roadmap.md`. It reads the plan row from the accepted version's plans artifact. A folder with no accepted head is refused with step 6's `NoPublishedRoadmapVersionError`, and the CLI turns that into the usual rc 2 error. The target tokens, origins, order, and snapshot semantics stay the same. The `seed-state.json` lifecycle checks stay the same. On green, a roadmap whose accepted head has moved past its root can feed `create --from-existing`, and research targets come from the accepted 02 and 03.

## Table of Contents

- [Why](#why) — what the two reads do after step 3
- [Input](#input) — what steps 3 and 6 supply and what tests cannot show
- [Files (creates vs edits)](#files-creates-vs-edits) — the four files edited
- [Implementation](#implementation) — the two converted reads, refusal handling, constraints
- [Tests](#tests) — cases per behavior and invariant
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves to others

## Why

- `_load_roadmap_research_targets` builds paths with `constraints_path(plans_dir, slug)` and `components_path(plans_dir, slug)`. After step 3, no top-level `0N-*.md` files exist, so every tracked-seed `create` fails with "could not load selected roadmap products".
- `_confirm_invalidated_roadmap_seed` reads `load_plans_artifact(plans_path(plans_dir, slug))`. It hits the same missing file and reports a failure before the user's seed is read.
- Even where a top-level file survives (a hand-converted folder), it can differ from the accepted head. Research would then ground on stale products. The plan's intent is one stored copy that every command reads, and this step converts the `create --from-existing` reader.

## Input

- **Step 3 output:** a first run publishes the root version with the accepted head written last. No top-level `0N-*.md` files are written.
- **Step 6 output:** the accepted-version loader in `plan_tool/roadmap.py` (`load_accepted_roadmap_artifacts` in the plan's wording) and `NoPublishedRoadmapVersionError` in `plan_tool/roadmap_seed_manifest.py`. Read the landed names from those modules. The landed names win over any name in this detail.
- **Version store (unchanged):** `plan_tool/roadmap_versions.py:load_accepted_version(plans_dir=, slug=)` returns `ResolvedRoadmapVersion | None`. `artifact_bytes` follows `VERSION_ARTIFACT_INVENTORY` order, which is domain, constraints, components, plans. The parsers are `parse_constraints_artifact`, `parse_components_artifact`, `parse_plans_artifact` in `plan_tool/roadmap_artifacts.py`.
- **Seed lifecycle (unchanged):** `plan_tool/roadmap_seed_state.py:locate_tracked_seed` and `TrackedSeedLocation` locate the sidecar from the seed's path or marker. `classify_draft_seeds` takes an already-parsed `PlansArtifact`. Neither reads stage files.
- **Limit:** tests build a version store from literal rows and stub the invoker. They cannot show that Integration's real accepted head gives good research targets. The post-ship hand run checks that.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — `_load_roadmap_research_targets` reads constraints and components from the accepted version. Update the imports that fed the old reads.
  - `plan_tool/cli/authoring.py` — `_confirm_invalidated_roadmap_seed` reads the plans artifact from the accepted version. `cmd_create` handles the refusal error.
  - `tests/test_create.py` — `TestTrackedRoadmapReferences` and its `_write_roadmap_research_source` helper build an accepted-version store instead of top-level files.
  - `tests/cli/test_authoring_cmds.py` — `TestRoadmapSeedConfirmation` and `_write_tracked_draft` build an accepted-version store.

## Implementation

**Behavior that must hold when the step is done:**

- **Targets come from the accepted head.** `_load_roadmap_research_targets` returns the same targets (token, product, origin, description, research disclosure, source order) it returns today, sourced from the accepted version's constraints and components. The origin strings keep the `02-constraints.md` / `03-components.md` artifact names, since those are the artifact names the roadmap documents.
- **Invalidation reads the accepted head.** `_confirm_invalidated_roadmap_seed` finds the plan row in the accepted version's plans artifact. A missing row still refuses with "is no longer present in its roadmap". The sidecar-status and `classify_draft_seeds` branches, the `-y` rule, and the non-TTY message stay as they are.
- **No head means a named refusal.** When `load_accepted_version` returns `None`, raise or catch step 6's `NoPublishedRoadmapVersionError`. `cmd_create` prints it and returns 2 before any backend call. Do not mint a second error class here.
- **Read once, in the same place as today.** `create_plan` still reads targets once, before the authoring invoker runs, as the existing comment on that call says. Do not re-read the head later for publication. The snapshot rule stays.

**Recommended approach (latitude on the exact code):**

- **One way:** read with `load_accepted_version`, decode each member from `artifact_bytes` by its `VERSION_ARTIFACT_INVENTORY` position, and parse with the `parse_*_artifact` functions. This copies the parse-per-member precedent in `plan_tool/roadmap_view.py:_parse_accepted_artifact_bundle`. Keep the parse errors as they are: `RoadmapArtifactError` and `UnicodeDecodeError` become `CreateError` in `create.py`, and the existing `error(...)` path in `authoring.py`.
- **Rejected: import step 6's loader from `plan_tool/roadmap.py`.** `roadmap.py` is the backend-seam module with a large import list. `create.py` and `authoring.py` should depend on `roadmap_versions` and `roadmap_artifacts`, which they already touch. A small local decode-and-parse is the smaller change. If the implementer finds step 6's loader sits in a leaf with no `shell` edge, reusing it is fine. Check that the import adds no cycle before choosing it.
- **Rejected: a shared helper module for the two decode-and-parse reads.** Two call sites do not justify a new module in this step. See Deferred.

**Constraints and gotchas:**

- **Path math stays valid.** Both functions derive `plans_dir` from `location.state_path` (`roadmap_root.parent.parent`). Keep that derivation. `load_accepted_version` takes `plans_dir` and `slug`.
- **Product and plan rows are by position and id.** Do not change token formats (`hosting-N`, `stores-N`) or the row-skipping rule for an empty `product`. Cache keys for the references blob hash the target snapshot, so a token change would invalidate caches.
- **Unparseable member.** Only the members the function needs are parsed. A broken domain artifact must not fail target loading, and a broken plans artifact must not fail it either. Parse constraints and components in `create.py`, and plans in `authoring.py`.
- **A promoted copy still works.** For `via_marker=True` seeds, the plan row check now reads the accepted head. The sidecar-status check stays on `seed-state.json`.
- **No writes.** This step reads the store only. It does not write seed state, versions, or `INDEX.md`.
- **Comments and docstrings.** Update the two docstrings that say "accepted roadmap source" or describe the stage files. Keep them to a line or two.

## Tests

Tests live in `tests/test_create.py` and `tests/cli/test_authoring_cmds.py`. Both fixture helpers move to an accepted-version store. Use the landed store builders from steps 3 and 6 where they exist. Otherwise use `plan_tool/roadmap_versions.py` helpers such as `create_root_version` with literal artifact text. Do not parse text through the stage run.

**`tests/test_create.py` (`TestTrackedRoadmapReferences`)**

- `test_tracked_roadmap_source_selects_hosting_and_store_products_in_source_order` — keep the existing assertions on tokens and products, now over an accepted-version store.
- `test_research_targets_come_from_accepted_version_not_stale_top_level_files` — write a top-level `02-constraints.md` and `03-components.md` with different products than the accepted head, then assert only the head's products return. This pins "the accepted version is the one source".
- `test_research_targets_follow_a_head_that_moved_past_the_root` — store a root version and a later accepted head with changed products, then assert the head's rows return.
- `test_no_accepted_head_refuses_before_any_row_is_read` — the loader raises the named no-head error when no head exists, and no target list returns.
- `test_unparseable_constraints_member_is_a_create_error` — a bad constraints member raises `CreateError` naming the roadmap slug.
- `test_unparseable_domain_member_does_not_block_target_loading` — a bad domain member leaves targets intact. This pins the carve-out that only the needed members are parsed.
- The existing empty-product, description-less, and disclosure cases keep passing over the new fixture.

**`tests/cli/test_authoring_cmds.py` (`TestRoadmapSeedConfirmation`)**

- Keep every existing case, now over an accepted-version store: current classification needs no confirmation, invalidated needs `-y` or a TTY answer, a non-TTY refuses with the `--refresh-seeds` hint, and a promoted copy checks the sidecar.
- `test_plan_row_missing_from_accepted_head_refuses` — a plan id in the sidecar but absent from the head's plans artifact returns False with "no longer present in its roadmap".
- `test_plan_row_present_only_in_stale_top_level_file_is_still_absent` — pins that a leftover top-level `04-roadmap.md` is not consulted.
- `test_cmd_create_from_existing_refuses_when_roadmap_has_no_accepted_head` — drives `main([...])` with `create --from-existing` on a tracked draft, asserts rc 2, the named error text on stderr, and that the invoker was never called.
- `test_promoted_copy_validated_against_sidecar_while_row_read_from_head` — a promoted seed with its draft archived still passes when the sidecar says current and the head has the row.

### Tests for this step

The tests above are the ones this step adds or changes. Every one must be green, and the full `tests/test_create.py` and `tests/cli/test_authoring_cmds.py` files must pass, before this step is finished. Verify each new carve-out test by mutation: restore the top-level read and confirm the "not stale top-level files" cases go red.

## Acceptance criteria

- `_load_roadmap_research_targets` returns products from the accepted version's constraints and components, in source order, with unchanged tokens and origins.
- A stale top-level `02-constraints.md`, `03-components.md`, or `04-roadmap.md` does not change any result.
- `create --from-existing` on a tracked seed with no accepted head exits 2 with the step 6 no-head message, and no backend call is made.
- `rg 'constraints_path|components_path|plans_path' plan_tool/create.py plan_tool/cli/authoring.py` returns no production read of a top-level stage file (the import lines are removed too).
- The invalidation outcomes (current, stale, missing row, promoted copy) are unchanged for a roadmap that has an accepted head.
- `uv run pytest tests/test_create.py tests/cli/test_authoring_cmds.py -q` is green.

## References

- `BACKLOG.md` #441 — source entry and scope contract.
- `ROADMAP_FORMAT.md` § "Immutable candidate-version authority" — accepted head and the direct-reader boundary.
- `plan_tool/roadmap_versions.py` — `load_accepted_version`, `ResolvedRoadmapVersion`, `VERSION_ARTIFACT_INVENTORY`.
- `plan_tool/roadmap_view.py` — `_parse_accepted_artifact_bundle`, the parse-per-member precedent.
- `plan_tool/roadmap_seed_state.py` — `locate_tracked_seed`, `TrackedSeedLocation`.
- `plan_tool/roadmap_seed_manifest.py` — `classify_draft_seeds` and step 6's no-head error.

## Applicable guardrails

- **Plan intent and step intent.** Every change here serves "every command, including `create --from-existing`, reads the accepted version". Nothing in this step widens past grounding research targets and invalidation on the accepted head.
- **The plan's "## Out of scope", candidate, review-seal, promotion, and version-record contracts.** This step reads the store through its existing loader and changes none of those contracts.
- **The plan's "## Out of scope", ledger format and tool-driven migration.** This step adds no ledger change and no conversion path. A legacy folder with top-level files is handled by the step 6 refusal wording.
- **The plan's "## Out of scope", top-level mirror.** This step must not write or keep a read-only top-level copy for `create` to fall back to.

## Deferred

- Consolidating the decode-and-parse of accepted members across `plan_tool/roadmap_view.py`, `plan_tool/roadmap.py` (step 6), `plan_tool/create.py`, and `plan_tool/cli/authoring.py` — a shared-helper refactor is separate intentional work. File it in `BACKLOG.md` after the plan ships, with machine-checked evidence of identity.
- `seed-state.json` and draft-seed behavior — owned by step 6 and unchanged here.
- Deleting the top-level path helpers (`constraints_path`, `components_path`, `plans_path`) from `plan_tool/roadmap_artifacts.py` — owned by the plan's removal steps, not this one.
- Quality of research targets on Integration's real accepted head — checked by the post-ship hand run, not by the test suite.
