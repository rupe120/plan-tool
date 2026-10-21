# Step 6 — Make --refresh-seeds, --materialize, --apply, and --accept-seed read the accepted version (enrolled-roadmap refusal retired; seed-state and plan-seed writes kept)

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step moves the four seed routes onto the accepted version. `plan_tool/roadmap.py` gets one loader, `load_accepted_roadmap_artifacts`, that returns the four stage artifacts parsed from `load_accepted_version`'s stored bytes. `refresh_roadmap_seeds`, `materialize_plan_seed`, `apply_roadmap_seeds`, and `accept_roadmap_seed`, plus the CLI's `--materialize` handler, read the plan rows and the prompt inputs through it. They no longer call the unenrolled writer guard. The routes keep their writer guard, `seed-state.json` writes, draft-seed writes, and `plan-seeds/` promotion. `plan_tool/roadmap_seed_manifest.py` gets the single `NoPublishedRoadmapVersionError` that refuses a folder with no accepted head. It also gets a message that points at hand conversion when top-level `0N-*.md` files exist. On green, a roadmap whose accepted head has moved past its root can refresh, materialize, accept, and apply seeds.

## Table of Contents

- [Why](#why) — what the seed routes refuse and read today
- [Input](#input) — what steps 1 and 3 supply and what tests cannot show
- [Files (creates vs edits)](#files-creates-vs-edits) — files touched, including one addition
- [Implementation](#implementation) — loader, error, per-route changes, constraints
- [Tests](#tests) — cases per behavior and invariant
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work left to other steps

## Why

- Each seed route starts with `_require_unenrolled_roadmap_writer_or_raise` (or `require_unenrolled_roadmap_writer` in the CLI's `_cmd_roadmap_materialize_owned`). It refuses a roadmap that has an accepted head. After step 3 every roadmap has one, so no seed route can run.
- The same routes read `04-roadmap.md` through `load_plans_artifact(plans_path(...))`, and `materialize_plan_seed` reads all four artifacts through `_load_stage_artifact(stage, ...)`, which calls `RoadmapStage.artifact_path`. Step 3 stops writing those top-level files, so these reads find nothing.
- The plan wants one stored copy of roadmap content, read by every command. Seed routes are the first reader to convert and the one that has to define the refusal for a folder with no accepted head.

## Input

- **Step 3 output:** a first run publishes a root version with the accepted head written last, and no top-level `0N-*.md` files. A legacy folder with those files and no head is refused at the stage run. Use that refusal's hand-conversion wording as landed; do not restate the stage run's mechanism here.
- **Step 1 output:** the `BACKLOG.md` #441 route inventory. It confirms that these four routes plus `create --from-existing` are the converted seed routes, and that nothing else here reads the top-level artifacts.
- **Version store (unchanged):** `plan_tool/roadmap_versions.py:load_accepted_version` returns a `ResolvedRoadmapVersion` or `None`. Its `artifact_bytes` follow `VERSION_ARTIFACT_INVENTORY` order. `plan_tool/roadmap_view.py:_parse_accepted_artifact_bundle` is the existing parse-per-member precedent; mirror it, do not import it (`plan_tool/roadmap.py` and `plan_tool/roadmap_view.py` stay independent branches).
- **Seed classification (unchanged contract):** `plan_tool/roadmap_seed_manifest.py:classify_draft_seeds` and `find_orphan_seed_records` take an already-parsed `PlansArtifact`. They read `seed-state.json` and the draft directory, never the stage files, so they work with a version-sourced artifact as is.
- **Limit:** unit tests build a version store from literal records and drive seeds with the `invoker=` stub. They cannot show that Integration's real accepted head produces good seeds. That is checked by the post-ship hand run.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — add `load_accepted_roadmap_artifacts`; switch `refresh_roadmap_seeds`/`_refresh_roadmap_seeds`, `materialize_plan_seed`/`_materialize_plan_seed`, `materialize_and_diff_one_plan` (and its inner function), `accept_roadmap_seed`/`_accept_roadmap_seed`, and `apply_roadmap_seeds` with `_reject_unmatched_operator_draft_fences` and `_apply_roadmap_seeds` to it; delete `_require_unenrolled_roadmap_writer_or_raise` once no caller remains.
  - `plan_tool/roadmap_seed_manifest.py` — add `NoPublishedRoadmapVersionError` and the message builder for the hand-conversion pointer. Rows and classification logic do not change.
  - `plan_tool/cli/roadmap_cmd.py` — **addition to the declared list, required:** `_cmd_roadmap_materialize_owned` calls `require_unenrolled_roadmap_writer` and `load_plans_artifact(plans_path(...))` itself, so `--materialize` cannot work without editing it. Swap those two calls for the new loader. No other CLI edit is needed.
  - `tests/test_roadmap.py`, `tests/test_roadmap_seed_manifest.py`, `tests/cli/test_roadmap_cmd.py` — cases listed under Tests; rewrite any existing case that pins the enrolled-roadmap refusal on a seed route.

## Implementation

**Behavior that must hold when the step is done:**

- **One reader.** All four routes get their plan rows and their prompt inputs from the accepted version. None reads `RoadmapStage.artifact_path`, `plans_path`, or `load_plans_artifact(path)` for roadmap content.
- **No enrolled refusal.** A roadmap whose head is a later version than its root passes every seed route's preflight.
- **Writes are unchanged.** Draft seeds, `seed-state.json` entries (`status`, `digest`, `published`), the `plan-seeds/` promotion, and the `_promoted_seed_body` marker keep their current shape and ordering ("the sidecar commits last").
- **Writer guard stays.** The routes still run under `_roadmap_writer_owner` and `require_roadmap_writer_token`. Only the "must be unenrolled" check goes.

**One loader, one error (recommended shape):**

- `load_accepted_roadmap_artifacts(plans_dir, slug) -> tuple[_LoadedArtifact, ...]` in `plan_tool/roadmap.py`. Call `load_accepted_version`; map `RoadmapVersionError` to `RoadmapError`; parse each member with the matching `STAGES` row's `parse` from the decoded bytes. The text field keeps the stored text as is. Do not re-render it, so the prompt sees exactly what the version holds.
- Build each `_LoadedArtifact` with the stored member's path (`version_directory_path` plus `artifact_member_name(stage.artifact_key)`), not `stage.artifact_path`. Step 11's guard bans production reads of `artifact_path`, so this keeps the guard satisfiable.
- A parse failure raises `RoadmapArtifactError` carrying the member path, as `_load_stage_artifact` does today.
- **Where the error lives.** Define `NoPublishedRoadmapVersionError` in `plan_tool/roadmap_seed_manifest.py`, subclassing `RoadmapArtifactError`. That module is a leaf both `roadmap.py` and `roadmap_view.py` already import, so steps 7, 10, and 11 can reuse it without a `roadmap`↔`roadmap_view` edge. A `RoadmapError` subclass in `roadmap.py` would force that edge. Every seed-route handler already catches `(RoadmapError, RoadmapArtifactError)`, so the exit code mapping (`_RC_USAGE`) does not change.
- **Message.** Say the roadmap has no published version. When any of the four top-level `*_FILENAME` files exists in the roadmap folder, also point at hand conversion as `docs/how-to/roadmap.md` § 1 documents it (delete the top-level files and regenerate under the same slug, or start a successor slug from the brief). Check existence only; never read those files. Other steps own the later readers' refusals; this step defines the error and uses it in the four seed routes.

**Per-route changes:**

- **`refresh_roadmap_seeds`:** `_refresh_roadmap_seeds` loads `STAGES[-1]` today. Use the loader's last element. Rows still go through `_materialize_seed_rows`.
- **`materialize_plan_seed`:** `_materialize_plan_seed` builds `loaded` from every stage and passes it to `_render_seed_materialize_prompt`. Pass the loader's tuple instead. The prompt renderer needs no change because it only reads `item.stage.artifact_key` and `item.text`.
- **`accept_roadmap_seed`, `apply_roadmap_seeds`:** replace each `load_plans_artifact(plans_path(...))` (including `_reject_unmatched_operator_draft_fences`, the second load in `_apply_roadmap_seeds` after the confirm wait) with the loader's plans artifact. Keep the second load; it is the freshness re-check.
- **CLI `--materialize`:** in `_cmd_roadmap_materialize_owned`, drop the unenrolled check and take `artifact` from the loader. Keep `_refuse_materialize_preflight` as the path for a loader error.
- **Callerless helper.** After the edits `_require_unenrolled_roadmap_writer_or_raise` has no caller (all seed routes were its only users). Delete it. Leave `require_unenrolled_roadmap_writer` and `_require_legacy_roadmap_run_available`; other steps own those.

**Shared locations checked (foundational logic: "seed routes read roadmap content from the accepted version"):**

- `plan_tool/cli/authoring.py` (`classify_draft_seeds` callers) and `create --from-existing` on a roadmap seed — left to the step the plan assigns to them; this step does not change them.
- `plan_tool/cli/roadmap_cmd.py` view paths and `_create_handoff_lines` (reads a stage-written plans file) — left to the view and stage-run steps.
- `plan_tool/roadmap_view.py` already reads the accepted version through `_parse_accepted_artifact_bundle`. A shared parser would be a cross-module consolidation; do not do it here. Parallel parsing is the same mirror-don't-import rule the plan applies between these two modules.

**Constraints and gotchas:**

- **Brief digest is not checked here.** The seed routes never compared the brief; do not add a brief check.
- **No fallback.** If the loader finds no head it raises. It must not fall back to top-level files, even when they exist.
- **Draft-seed paths come from the accepted `PlansArtifact`.** After a candidate promotion the head's rows can differ from the root's; `classify_draft_seeds` already reports such drift (`stale`, `missing`, `digest-mismatched`), so do not add new classification states.
- **Smallest change.** One loader and one error. No registry, no caching of the loaded version between routes.

## Tests

Test files: `tests/test_roadmap.py`, `tests/test_roadmap_seed_manifest.py`, `tests/cli/test_roadmap_cmd.py`. Build the stores with the existing version-store test helpers; stub backends through `invoker=`.

- `test_load_accepted_roadmap_artifacts_parses_the_stored_members_in_stage_order` — the four parsed artifacts match the stored bytes; text is returned unchanged.
- `test_loader_raises_no_published_version_error_when_no_accepted_head` — error type and message.
- `test_no_published_version_message_points_at_hand_conversion_only_when_top_level_files_exist` — pointer text appears with a top-level `0N-*.md` file present and is absent without one.
- `test_loader_never_falls_back_to_top_level_files_beside_an_accepted_head` — a top-level `04-roadmap.md` that differs from the stored one is ignored (the deliberate carve-out for inert leftovers).
- `test_refresh_seeds_runs_on_an_accepted_head_that_advanced_past_its_root` — outcome applied; draft files and sidecar entries written for the head's rows, not the root's.
- `test_materialize_prompt_embeds_the_accepted_versions_artifact_text` — the prompt the stub receives holds the head version's text.
- `test_accept_seed_records_digest_and_keeps_published_flag_on_an_advanced_head` — `seed-state.json` entry and promoted-seed rewrite behave as before.
- `test_apply_seeds_promotes_ordered_targets_from_the_accepted_plans_artifact` — targets follow the head's `ordering`; the post-confirm freshness re-check still reloads.
- `test_apply_refuses_with_no_published_version_and_writes_nothing` — no `plan-seeds/` or sidecar change.
- `test_seed_routes_no_longer_refuse_an_enrolled_roadmap` — replaces any case pinning the "enrolled" refusal on these routes.
- `test_seed_route_writes_stay_under_the_writer_guard` — a stale writer token still raises `RoadmapError` (existing stale-token cases at the seed routes stay green after the guard swap).
- `test_classify_draft_seeds_accepts_a_version_parsed_plans_artifact` (`tests/test_roadmap_seed_manifest.py`) — pins that classification needs no stage file on disk.
- `test_materialize_cli_refuses_with_no_published_version_via_preflight_path` (`tests/cli/test_roadmap_cmd.py`) — `_refuse_materialize_preflight` outcome and rc.
- `test_materialize_cli_selects_rows_from_the_accepted_version` — `--materialize` all and `--materialize PLAN_ID` use head rows.

### Tests for this step

The cases above are the roster: loader and error (4), the four routes on an advanced head (6), the no-head refusal (2 — apply and CLI materialize), guard and classifier pins (2). Every one must be green before the step is finished, with the full `tests/test_roadmap.py` and `tests/cli/test_roadmap_cmd.py` files green (rewrite, not delete, any case that pinned the old refusal).

## Acceptance criteria

- `--refresh-seeds`, `--materialize`, `--apply`, and `--accept-seed` succeed on a roadmap whose accepted head differs from its root, and read the head's plan rows.
- On a folder with no accepted head each route exits through the named error and writes no seed, sidecar, or `plan-seeds/` file.
- `rg 'artifact_path|plans_path\(|load_plans_artifact\(' plan_tool/roadmap.py` returns no match inside the seed routes or the new loader.
- `rg '_require_unenrolled_roadmap_writer_or_raise' plan_tool/` returns nothing.
- The CLI's `--materialize` handler no longer calls `require_unenrolled_roadmap_writer` or `load_plans_artifact`.
- `NoPublishedRoadmapVersionError` is importable from `plan_tool/roadmap_seed_manifest.py` without importing `plan_tool/roadmap.py`.
- Seed-state entry shape, draft-seed writes, and promotion output are unchanged for a first-root roadmap (existing tests green).

## References

- `docs/implementation-plans/2-roadmap-versioned-from-birth.md` — "Route disposition" and the no-published-version bullets in `## Architecture`.
- `BACKLOG.md` #441 — scope contract and the step 1 record.
- `ROADMAP_FORMAT.md` § "Immutable candidate-version authority" — accepted head and the direct-reader boundary.
- `plan_tool/roadmap_versions.py` — `load_accepted_version`, `ResolvedRoadmapVersion`, `artifact_member_name`, `version_directory_path`.
- `plan_tool/roadmap_view.py:_parse_accepted_artifact_bundle` — parse-per-member precedent.
- `docs/how-to/roadmap.md` § 1 — hand-conversion procedure the error points at.

## Applicable guardrails

- **The plan's "## Out of scope", candidate/seal/promotion/version-record contracts:** this step reads the version store and does not change any record, loader, or contract in it.
- **The plan's "## Out of scope", ledger format:** the step touches no ledger code.
- **The plan's "## Out of scope", tool-driven migration:** the error only names hand conversion. This step adds no conversion command or helper.
- **The plan's "## Out of scope", top-level mirror of the accepted version:** the loader reads stored bytes and writes no top-level file; the seed routes keep writing only the files they wrote before.
- **The plan's intent (one stored copy, every command reads the accepted version):** this step is the first reader conversion; it must not add a second read path for roadmap content.

## Deferred

- `create --from-existing` on a roadmap seed (`plan_tool/create.py:_load_roadmap_research_targets`, `plan_tool/cli/authoring.py`) — owned by the step the plan assigns to it; it reuses this step's error.
- `--view` and `--settle-decision` refusals on a folder with no accepted head — owned by the reader-closing step (step 11), which reuses `NoPublishedRoadmapVersionError`.
- `--compare` refusal — owned by the `--compare` step, same reuse.
- Removing `_require_legacy_roadmap_run_available` and `require_unenrolled_roadmap_writer` — owned by the stage-run and legacy-removal steps; they still have callers outside this step.
- Sharing one parser between `plan_tool/roadmap.py` and `plan_tool/roadmap_view.py` — a cross-module consolidation; file it in `BACKLOG.md` if it recurs, not part of this step.
