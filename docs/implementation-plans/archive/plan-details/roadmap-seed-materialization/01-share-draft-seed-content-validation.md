> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Share draft-seed content validation between the stage-4 gates and the new seed materializer

## Summary

Extracts the two pieces of draft-seed judgment the stage-4 plans gate already implements — provenance/component-reference validation and plan-row basename-collision detection — into standalone functions in `plan_tool/roadmap_gates.py` that take a plan row (and, for content validation, one seed's text) directly, with no `ArtifactEnvelope` and no `draft_seed_bundle`. `check_draft_seed_provenance` and `check_draft_seed_bundle_alignment` become thin wrappers over these two functions, so today's gate behavior, violation kinds, and messages are unchanged. Alongside that extraction, renames `DRAFT_SEEDS_DIRNAME` in `plan_tool/roadmap_artifacts.py` from `"seeds"` to `"plan-seed-drafts"`, widens `_validate_draft_seed_path` to keep accepting the legacy `seeds/` prefix read-only, and sweeps the two hardcoded `"seeds"` checks in `plan_tool/roadmap_seed_state.py` to recognize both directory names. `plan_tool/prompts/roadmap-plans.md`'s `draft_seed_path` rule and worked example move to the new prefix. On green, the shared functions are ready for step 2's per-plan materializer and step 3's manifest classifier to call directly, and the plans gate set and every existing roadmap on disk keep behaving exactly as before.

## Table of Contents

- [Why](#why) — what forces this extraction now and what the rename buys
- [Input](#input) — the existing gate/envelope contract and `seed-state.json` schema this step must not break
- [Files (creates vs edits)](#files-creates-vs-edits) — the seven declared files plus one necessary addition
- [Implementation](#implementation) — the two extracted functions, the rename, and the sweep
- [Tests](#tests) — behavior-preserving cases versus new observable-behavior cases
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

`check_draft_seed_provenance` and `check_draft_seed_bundle_alignment` in `plan_tool/roadmap_gates.py` today only know how to judge a draft seed as one entry in a `draft_seed_bundle` living inside an `ArtifactEnvelope` — the shape stage 4's own single combined call produces. The plan's later steps need the same two judgments (does a seed's provenance frontmatter resolve against its owning plan row; do plan rows' `draft_seed_path` basenames collide) available with no bundle and no envelope at all: step 2's per-plan seed generator validates one freshly generated seed against one plan row before publishing it, and step 3's manifest classifier judges one on-disk draft the same way to produce its `duplicate`/`malformed` states. Without this step, step 2 and step 3 would each grow their own copy of "does this provenance resolve" and "do these basenames collide," and the two copies would drift the first time either rule changes.

The directory rename rides in the same step because it touches the same file for the same reason: `DRAFT_SEEDS_DIRNAME` is read by `_validate_draft_seed_path` (which the extraction's new callers also exercise) and by `draft_seeds_dir`, so moving it under a name that cannot be confused with the top-level `plan-seeds/` promotion destination is part of giving step 2/3 a stable, unambiguous contract to build on. The plan's own step-1 intent records that splitting the rename into its own step was considered and declined across three prior audit rounds — the extraction and the rename are both small and share one file for one reason — so this step does not re-open that question.

## Input

This step extends, and must not break, two existing contracts it does not own:

- **The gate contract in `plan_tool/roadmap_gates.py`.** `Violation(kind, artifact, row_id, message)`, the `Gate = Callable[[ArtifactEnvelope], list[Violation]]` shape, and `PLANS_GATES`' declared order are load-bearing for `plan_tool/roadmap.py`'s stage-4 retry loop and for `tests/test_roadmap.py`'s prompt/gate-rule pinning tests (`test_plans_prompt_states_every_plans_gate_rule` iterates `PLANS_GATES` by name). `check_draft_seed_provenance` and `check_draft_seed_bundle_alignment` must keep their existing signatures, stay members of `PLANS_GATES` in the same position, and keep emitting the same violation kinds and messages for the same inputs — only their internal implementation changes.
- **The `seed-state.json` schema in `plan_tool/roadmap_seed_state.py`.** `validate_seed_state`'s shape (`draft_seed_path`, `status`, `digest`, `published` per plan id) is unchanged by this step — `Risks` in the plan is explicit that a content-identity change must not require a schema migration. This step only widens which directory names `_structural_state_path`/`_matching_plan_id` recognize when locating a draft's sidecar entry from its file path; it does not add, rename, or remove a JSON field.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/roadmap_gates.py` — add the two envelope-free/bundle-free shared functions; rewrite `check_draft_seed_provenance` and `check_draft_seed_bundle_alignment` to delegate to them.
- `plan_tool/roadmap_artifacts.py` — rename `DRAFT_SEEDS_DIRNAME` to `"plan-seed-drafts"`; add a legacy-prefix constant; widen `_validate_draft_seed_path`.
- `plan_tool/roadmap_seed_state.py` — widen `_structural_state_path` and `_matching_plan_id` to recognize both directory names.
- `plan_tool/prompts/roadmap-plans.md` — update the `draft_seed_path` prefix rule and its worked example (the "Finally, provide `draft_seed_path`..." sentence and the `draft_seed_path:` line in the skeleton block) from `seeds/...` to `plan-seed-drafts/...`.
- `tests/test_roadmap_gates.py` — new direct tests for the two shared functions; existing gate tests are left unmodified as the behavior-preserving evidence.
- `tests/test_roadmap_artifacts.py` — update `draft_seeds_dir`'s expected path; add positive cases for both the new and legacy `draft_seed_path` prefixes.
- `tests/test_roadmap_seed_state.py` — add cases mirroring the existing three under the new directory name; existing cases are left unmodified as the legacy-prefix regression evidence.
- **`tests/cli/test_roadmap_cmd.py` (necessary addition, not in the plan's declared list — see below).**

**Why the addition is necessary:** `plan_tool/cli/roadmap_cmd.py:copy_aside_for` builds its stage-4 copy-aside line with `f"the slug {DRAFT_SEEDS_DIRNAME}/ tree"`, interpolating the constant this step renames. `test_overwriting_stage_four_names_seeds_tree_in_copy_aside` and `test_overwriting_stages_including_four_names_seeds_on_rewrite_warning` assert `"seeds/" in out` against that exact line — a substring present in `"seeds/"` but not in `"plan-seed-drafts/"`. Renaming the constant without touching this file leaves these two tests red the moment this step lands, in a file `plan_tool/cli/roadmap_cmd.py` this step correctly does not edit (its content — the "stage 4 replaces the tree atomically" claim — is step 9's to rewrite once that claim stops being true). The fix here is mechanical and narrow: update the two assertions to track the current constant's value (e.g. import `DRAFT_SEEDS_DIRNAME` from `plan_tool.roadmap_artifacts` and assert against `f"{DRAFT_SEEDS_DIRNAME}/"`) rather than a second hardcoded literal, so it does not need a third edit when step 9 changes the surrounding sentence. This is the only place in the repo where `DRAFT_SEEDS_DIRNAME`'s value reaches a test assertion outside this step's declared files — confirmed by checking every other consumer of the constant (`plan_tool/roadmap.py`'s two uses are internal temp/backup directory names never asserted on, and `plan_tool/roadmap.py`'s own tests exercise the rename correctly because they call `draft_seeds_dir(...)` rather than hardcoding a literal) and every hardcoded `"seeds"`/`"seeds/"` string across `tests/test_roadmap.py`, `tests/test_roadmap_view.py`, and `tests/cli/test_authoring_cmds.py` (all of those are literal `draft_seed_path` *row values* passed straight through, independent of the constant, and remain valid under the widened, legacy-accepting validator).

## Implementation

### Extracting the shared, envelope-free validators

Add two functions to `plan_tool/roadmap_gates.py`, both taking plan data directly rather than an `ArtifactEnvelope`, so a caller with no bundle and no upstream artifacts can use them (`Sequence` is already imported in this module):

- **A content/provenance validator**, roughly `validate_draft_seed_content(text: str, *, plan: PlanRow) -> list[Violation]`. Move `check_draft_seed_provenance`'s per-plan-row body into it: parse `text` with the existing `parse_draft_seed_provenance`, catch `RoadmapArtifactError` and return a `VIOLATION_DRAFT_SEED_PROVENANCE` violation, otherwise check `provenance.roadmap_components` against `plan.component_ids` (with the existing cross-cutting carve) and return `VIOLATION_UNDEFINED_SEED_COMPONENT_REFERENCE` violations for anything unresolved. Reuse the two existing violation kind constants — no new ones are needed. The basename used in messages is still `Path(plan.draft_seed_path).name`, derived from `plan` alone, so message text is unchanged.
- **A duplicate-basename finder**, roughly `find_duplicate_draft_seed_basenames(plans: Sequence[PlanRow]) -> list[Violation]`. Move `check_draft_seed_bundle_alignment`'s grouping and its `len(plan_ids) > 1` branch into it — this half never reads `draft_seed_bundle`, so it is already a static comparison over plan rows alone (this is the "generalized to compare plan rows alone" property the plan asks for) — but change what it groups **by**: group by the full `plan.draft_seed_path` string (prefix and basename together), not `Path(plan.draft_seed_path).name` alone. Architecture states both directory prefixes remain, and always will remain, structurally valid at once, so two rows whose basenames match but whose prefixes differ — `seeds/order-core.md` and `plan-seed-drafts/order-core.md` — resolve to two distinct, non-colliding files; a basename-only comparison would flag them `duplicate` and permanently block promotion with no real fix, since the plan's own remedy ("resolve the colliding rows") doesn't apply when nothing actually collides. Every existing fixture in `tests/test_roadmap_gates.py` uses a single prefix, so this change is byte-identical for all of them (the acceptance criterion below still holds); it changes behavior only for the new cross-prefix case this plan introduces. **Scope the rename to the collision emission only — `VIOLATION_MISSING_DRAFT_SEED_BUNDLE_ENTRY` is not a single-purpose constant.** At HEAD, `check_draft_seed_bundle_alignment` emits it from two distinct branches: the `len(plan_ids) > 1` collision loop being moved into `find_duplicate_draft_seed_basenames` above, and a separate, staying-in-place branch for a single, non-colliding plan row whose basename has no matching `draft_seed_bundle` key (`plan_tool/roadmap_gates.py:1953`, per this file's own "keeps its existing bundle-membership check... exactly as today"). Add a new constant, `VIOLATION_DUPLICATE_DRAFT_SEED_BASENAME`, and use it **only** for `find_duplicate_draft_seed_basenames`'s collision emission (the one moving in this edit); leave the missing-bundle-entry branch's own emission on the original `VIOLATION_MISSING_DRAFT_SEED_BUNDLE_ENTRY` name — that name is accurate for a genuine missing-bundle-entry case, and only ever misdescribes the collision case. Do **not** do a blanket rename of every reference: `test_missing_bundle_entry_for_plan_row_violates` (`tests/test_roadmap_gates.py:1020`) asserts `violation.kind == VIOLATION_MISSING_DRAFT_SEED_BUNDLE_ENTRY` and is this step's own "pass unchanged" evidence (see Tests) — converting that assertion's constant would both mislabel a non-collision violation and break the exact test this file calls unmodified. Only `test_duplicate_draft_seed_basename_across_plan_rows_violates`'s kind assertion moves to the new constant.

Rewrite the two gates as thin wrappers:

- `check_draft_seed_provenance(envelope)` keeps its `isinstance(artifact, PlansArtifact)` guard and its per-plan `basename not in bundle` skip, then calls `validate_draft_seed_content(bundle[basename], plan=plan)` for each plan whose seed is present in the bundle and extends the result list.
- `check_draft_seed_bundle_alignment(envelope)` keeps its guard, calls `find_duplicate_draft_seed_basenames(artifact.plans)` first, and folds those violations into its result; for every basename `find_duplicate_draft_seed_basenames` did *not* flag as a collision, it keeps its existing bundle-membership check (missing bundle entry / dangling bundle entry) exactly as today.

Neither function's public signature, membership in `PLANS_GATES`, or violation output for any existing fixture may change — this half of the step is the behavior-preserving extraction, and `tests/test_roadmap_gates.py`'s existing draft-seed cases (see Tests) are the evidence.

**Constraint:** `plan_tool/roadmap_gates.py` may keep importing `plan_tool.roadmap_artifacts` (already its one first-party import) but must not gain a second one — the new functions live here, not in `roadmap_artifacts.py`, precisely because `Violation` and the `VIOLATION_*` constants are defined here and `roadmap_artifacts.py`'s own docstring commits it to importing no first-party module at all.

### Renaming the draft-seed directory

In `plan_tool/roadmap_artifacts.py`:

- Change `DRAFT_SEEDS_DIRNAME = "seeds"` to `DRAFT_SEEDS_DIRNAME = "plan-seed-drafts"`. `draft_seeds_dir()` and every caller that derives a *write* location from the constant (including `plan_tool/roadmap.py`'s stage-4 writer, which is outside this step's files but reads the constant by name) automatically start writing new roadmaps under the new name with no further code change.
- Add a constant for the accepted legacy prefix (e.g. `LEGACY_DRAFT_SEEDS_DIRNAME = "seeds"`) — worth making public rather than private, since step 8's later directory-scan work needs the same literal to walk a roadmap's legacy `seeds/` directory alongside `plan-seed-drafts/`, and a public constant here is one source for both this step and that one instead of a second hardcoded `"seeds"`.
- Widen `_validate_draft_seed_path`'s prefix check from `parts[0] != DRAFT_SEEDS_DIRNAME` to accepting either `DRAFT_SEEDS_DIRNAME` or the legacy constant. `resolve_draft_seed_path` and `_parse_plan_rows`' parse-time validation both call through this one function, so both accept either prefix without further changes. No test currently pins the exact error message text (`rg "must begin with" tests/` returns no hits), so adjusting the message to name both accepted prefixes is free.

**Constraint:** the widened acceptance is read-only — nothing in this step rewrites an existing roadmap's stored `04-roadmap.md` or `seed-state.json` paths, and `resolve_plan_seed_dest`/`plan-seeds/` (the unrelated top-level promotion destination) are untouched. `"plan-seeds/..."` must keep being rejected by `_validate_draft_seed_path` — it is a different directory serving a different purpose, and `test_resolve_draft_seed_path_rejects_unsafe_relative_paths` already pins this case; verify it still rejects under the widened rule rather than assuming it does.

### Sweeping `roadmap_seed_state.py`

`_structural_state_path` and `_matching_plan_id` both currently test `source.parent.name == "seeds"` (and, for the archive case, `source.parent.parent.name == "seeds"`) as literal strings. Widen both checks to accept either directory name. Because this module's own docstring commits it to being a stdlib-only leaf so both `roadmap.py` and `create.py` can consult it with no import cycle, mirror the two literal directory-name strings locally here (e.g. a small module-level tuple) rather than importing `DRAFT_SEEDS_DIRNAME`/the legacy constant from `roadmap_artifacts.py` — the same mirror-don't-import shape this module already uses elsewhere in the codebase for shared literals.

### Updating the stage-4 prompt

In `plan_tool/prompts/roadmap-plans.md`, update the `draft_seed_path` rule sentence ("...must begin with `seeds/`...") and its inline example (`seeds/order-core.md`) to `plan-seed-drafts/` and `plan-seed-drafts/order-core.md`, and update the skeleton block's `draft_seed_path: seeds/plan-1.md` line to `draft_seed_path: plan-seed-drafts/plan-1.md`. Nothing else in this file changes — the seed-fence protocol, the scope-contract section list, and the Architecture-additions prose are step 9's to rewrite once stage 4 stops generating seed bodies inline at all. None of `tests/test_roadmap.py`'s prompt-pinning tests (placeholder subset, gate-rule-per-prompt, row-key/disposition/provenance-key presence) assert the literal example string, so this edit does not touch that file.

## Tests

### Tests for this step

**Behavior-preserving (unmodified — the extraction's evidence):**

- `tests/test_roadmap_gates.py::test_draft_seed_with_valid_provenance_passes`, `test_draft_seed_missing_roadmap_components_violates`, `test_draft_seed_lists_component_not_on_plan_row_violates`, `test_cross_cutting_seed_flag_matches_cross_cutting_plan` — pass unchanged through the rewritten `check_draft_seed_provenance`.
- `tests/test_roadmap_gates.py::test_plan_row_and_bundle_basenames_match_passes`, `test_missing_bundle_entry_for_plan_row_violates`, `test_dangling_bundle_key_violates`, `test_none_draft_seed_bundle_violates_for_every_plan_row` — pass unchanged through the rewritten `check_draft_seed_bundle_alignment`.
- `tests/test_roadmap_gates.py::test_duplicate_draft_seed_basename_across_plan_rows_violates` — its fixture rows share both prefix and basename, so full-path comparison still flags it; update only its `violation.kind` assertion to the renamed `VIOLATION_DUPLICATE_DRAFT_SEED_BASENAME` constant.
- `tests/test_roadmap_seed_state.py::test_direct_draft_and_its_archive_require_stale_seed_confirmation`, `test_promoted_seed_marker_survives_its_archive_move`, `test_create_requires_an_explicit_assent_for_an_invalidated_seed` — pass unchanged, pinning that the legacy `seeds/` directory keeps resolving.
- `tests/test_roadmap_artifacts.py::test_resolve_draft_seed_path_rejects_unsafe_relative_paths` — pass unchanged (still rejects `""`, `"   "`, an absolute path, a `..`-bearing path, and `"plan-seeds/x.md"`).

**New — the shared functions called with no envelope or bundle:**

- `test_validate_draft_seed_content_accepts_matching_components` — direct call with valid provenance text and a matching plan row returns `[]`.
- `test_validate_draft_seed_content_rejects_unparseable_provenance` — malformed frontmatter text returns a `VIOLATION_DRAFT_SEED_PROVENANCE` violation naming the plan row.
- `test_validate_draft_seed_content_rejects_component_not_on_plan_row` — a `roadmap_components` entry absent from `plan.component_ids` returns `VIOLATION_UNDEFINED_SEED_COMPONENT_REFERENCE`.
- `test_validate_draft_seed_content_allows_cross_cutting_flag` — a cross-cutting plan row with `cross_cutting: true` in the text returns `[]`.
- `test_find_duplicate_draft_seed_basenames_flags_shared_basename` — two `PlanRow`s whose `draft_seed_path` share both prefix and basename (e.g. both `plan-seed-drafts/order-core.md`) both come back flagged, with no bundle constructed.
- `test_find_duplicate_draft_seed_basenames_does_not_flag_shared_basename_under_different_prefixes` — two `PlanRow`s whose `draft_seed_path` share a basename but differ in directory prefix (`seeds/order-core.md` and `plan-seed-drafts/order-core.md`) return `[]` — they resolve to two distinct files, not a collision.
- `test_find_duplicate_draft_seed_basenames_empty_for_unique_paths` — non-colliding rows return `[]`.

**New — observable rename behavior:**

- `tests/test_roadmap_artifacts.py::test_draft_seeds_dir_uses_the_renamed_directory` (update of `test_plans_path_and_draft_seeds_dir_under_roadmap_slug`) — `draft_seeds_dir(...)` now ends in `plan-seed-drafts`.
- `tests/test_roadmap_artifacts.py::test_resolve_draft_seed_path_accepts_the_new_prefix` — `"plan-seed-drafts/x.md"` resolves without raising.
- `tests/test_roadmap_artifacts.py::test_resolve_draft_seed_path_still_accepts_the_legacy_prefix` — `"seeds/x.md"` still resolves without raising.
- `tests/test_roadmap_seed_state.py` — a new pair of cases mirroring `test_direct_draft_and_its_archive_require_stale_seed_confirmation` and `test_create_requires_an_explicit_assent_for_an_invalidated_seed`, but with the draft under `plan-seed-drafts/` and a matching sidecar `draft_seed_path`. (The promoted-seed-marker test needs no new-prefix case — it locates state through the durable marker written at promotion time, never through directory-name matching, so it is already prefix-independent.)
- `tests/cli/test_roadmap_cmd.py::test_overwriting_stage_four_names_seeds_tree_in_copy_aside`, `test_overwriting_stages_including_four_names_seeds_on_rewrite_warning` — updated to assert against the current `DRAFT_SEEDS_DIRNAME` value instead of the literal `"seeds/"`.

Every test above is green before this step is considered finished.

## Acceptance criteria

- `plan_tool/roadmap_gates.py` defines a content/provenance validator and a duplicate-basename finder whose signatures take a plan row (and, for the former, seed text) and carry no `ArtifactEnvelope` parameter — checkable with `rg -A1 'def validate_draft_seed_content|def find_duplicate_draft_seed_basenames' plan_tool/roadmap_gates.py`.
- `check_draft_seed_provenance` and `check_draft_seed_bundle_alignment` remain in `PLANS_GATES` at their current position and produce byte-identical violation lists (kind, artifact, row_id, message) to today's implementation for every existing fixture in `tests/test_roadmap_gates.py`.
- `plan_tool.roadmap_artifacts.DRAFT_SEEDS_DIRNAME == "plan-seed-drafts"`; `resolve_draft_seed_path` and `_parse_plan_rows` accept both `plan-seed-drafts/...` and `seeds/...` relative paths and reject every other prefix, including `plan-seeds/...`.
- `plan_tool.roadmap_seed_state.invalidated_seed_continuation` locates a tracked draft's sidecar entry correctly whether the draft sits under `seeds/` or `plan-seed-drafts/`, for both a direct draft and its `archive/` copy.
- `plan_tool/prompts/roadmap-plans.md`'s `draft_seed_path` rule sentence and example, and its skeleton's `draft_seed_path:` line, read `plan-seed-drafts/...`; no other content in that file changes.
- `tests/cli/test_roadmap_cmd.py`'s two `copy_aside_for` tests pass against the renamed constant.
- `uv run pytest tests/test_roadmap_gates.py tests/test_roadmap_artifacts.py tests/test_roadmap_seed_state.py tests/cli/test_roadmap_cmd.py -q` is green.

## References

- `ROADMAP_FORMAT.md` — documents today's `draft_seed_path`/`seeds/` prefix rule and the `check_draft_seed_bundle_alignment`/`check_draft_seed_provenance` gates this step generalizes; not edited by this step (step 9 updates its prose once the bundle-dependent gates are gone), but the source of truth for the contract being preserved here.
- `DATA_CONTRACT.md` — documents `seed-state.json`'s persisted shape; confirms this step's widening of `_structural_state_path`/`_matching_plan_id` is a read-path change only, with no field added, renamed, or removed.

## Applicable guardrails

- **Out of scope — redesigning the plan-seed prose format.** This step's edit to `plan_tool/prompts/roadmap-plans.md` is limited to the `draft_seed_path` prefix rule and its two literal examples. The scope-contract section headings, the Architecture-additions list, and the seed-fence output protocol stay exactly as they are.
- **Out of scope — a correctness gate on seed style, length, or model agreement.** The two extracted functions only check structural/provenance validity (parses, and ids resolve against the owning plan row) — they add no judgment about a seed's prose quality.
- **Out of scope — auto-promoting drafts or treating materialization as approval.** This step touches no promotion path (`--apply`, `_apply_roadmap_seeds`) at all; that wiring is step 6's.
- **In scope, narrowly — "the extraction necessary to separate stage-4 manifest handling from draft-seed materialization, while retaining one shared path-validation and promotion-preflight authority."** This step is exactly that licensed slice: it does not reorganize `create.py`, `roadmap.py`'s stage-4 write mechanics, or any other roadmap stage beyond the two gate functions and the directory-name plumbing named above.

## Deferred

- **The per-plan seed generation call, the manifest classifier, refresh/materialize CLI surfaces, and promotion refusal.** Steps 2, 3, 4/5, and 6 respectively — this step only ships the shared validators and directory rename those steps build on.
- **`_apply_roadmap_seeds`'s ad hoc provenance preflight in `plan_tool/roadmap.py`.** Stays as it is; step 6 replaces it with a call to this step's shared validator.
- **`ROADMAP_FORMAT.md`'s default-location prose, its `draft_seed_path` prefix rule, its worked examples, and its gate table's bundle-dependent row.** Step 9's to rewrite, once `check_draft_seed_provenance` and the bundle-dependent half of `check_draft_seed_bundle_alignment` are actually removed from `PLANS_GATES`.
- **`plan_tool/cli/roadmap_cmd.py`'s `copy_aside_for` sentence itself** ("...also replaces the slug `seeds/` tree atomically") — still true today, so its wording is untouched; step 9 rewrites it once stage 4 stops replacing that tree at all. This step only updates the two tests' assertion target so they track the renamed constant.
- **A stage-4 write physically landing seeds under `plan-seed-drafts/` for a *revision* over an existing, still-`seeds/`-prefixed roadmap, before step 9 retires the inline writer.** `plan_tool/roadmap.py`'s `_write_stage_outputs` writes every bundle entry into one `draft_seeds_dir()`-derived directory regardless of any individual row's own declared prefix, so between this step landing and step 9 removing that writer, a revision that regenerates an existing legacy-prefixed roadmap's seeds writes them to the new directory while the row still declares the old one. This is a real, narrow transient-state gap in the sequencing across the whole plan; closing it belongs to whichever of steps 2, 4, or 9 first changes how a seed's write location is chosen, not to this step, which does not touch `_write_stage_outputs` or any file outside its declared list that would let it do so.
