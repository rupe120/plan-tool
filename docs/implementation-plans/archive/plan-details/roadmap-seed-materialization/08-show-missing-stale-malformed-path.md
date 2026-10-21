> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Show every draft-seed state and orphan in the roadmap views

## Summary

Adds `--view seeds`, a fifth read-only roadmap view that prints one line per plan row with its step 3 classification (`current`, `missing`, `stale`, `malformed`, `path-escaping`, `duplicate`, `digest-mismatched`) plus an orphans report — sidecar entries and on-disk draft files matching no current plan row, scanned across both `plan-seed-drafts/` and a roadmap's legacy `seeds/` directory. It also reroutes `--view walk`'s per-plan draft-seed line (`plan_tool/roadmap_view.py:_render_draft_seed`, today its own digest-blind file-exists-and-parse check) through the same classification, so the walk and the new view never call one draft two different things. The key design decision: `plan_tool/roadmap_view.py` keeps its supplied-projection stance — the CLI computes the classification map and the orphan records and passes both in, so the renderers' unit tests stay hand-built records; the orphan scan itself lands as a small necessary addition to step 3's `plan_tool/roadmap_seed_manifest.py`, the module that already owns per-draft judgment. On green, an operator sees from `roadmap <slug> --view seeds` alone exactly which drafts would refuse promotion and why, before ever running `--apply`.

## Table of Contents

- [Why](#why) — the per-plan blind spot step 7's folded counts leave, and the orphan hole nothing reports today
- [Input](#input) — step 3's classifier contract, step 7's landed wiring, the sidecar schema, and step 1's directory names
- [Files (creates vs edits)](#files-creates-vs-edits) — the two declared files plus the necessary CLI, manifest, and doc additions
- [Implementation](#implementation) — the new view, the orphan finder, the walk reroute, and the choice-list sweep
- [Tests](#tests) — new seeds-view cases, rewritten walk seed cases, orphan-finder cases, and the hygiene-test outcome
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

After step 7, `--view summary` tells the truth in coarse counts — N current, M invalidated — but an operator deciding whether `--apply` will succeed needs the per-plan answer: *which* drafts are broken, and in *which* of the six ways step 6's promotion refusal distinguishes. Today no view gives it. `--view walk` comes closest, but its `_render_draft_seed` helper in `plan_tool/roadmap_view.py` runs its own two checks (`source.is_file()`, a bare `parse_draft_seed_provenance`) — the same digest-blind pair step 6 rips out of the promotion preflight — so a hand-edited, `digest-mismatched` draft renders as a clean seed in the walk while step 6 refuses to promote it and step 7's summary counts it invalidated. Separately, nothing anywhere reports an orphan: a `seed-state.json` entry or an on-disk draft file left behind by a roadmap rewrite that dropped its plan row is invisible in every view, because `classify_draft_seeds` deliberately covers exactly the artifact's plan rows and the sidecar-reading views filter to those same ids. This step closes both holes in one read-only surface, making the view family the third consumer of step 3's single classification (after step 6's write-side refusal and step 7's summary fold).

## Input

This step consumes three contracts it does not own and one landed convention it must follow:

- **Step 3's classifier**, `plan_tool.roadmap_seed_manifest.classify_draft_seeds(artifact, *, plans_dir, slug) -> dict[str, DraftSeedClassification]`, the seven `DRAFT_SEED_STATE_*` constants, and the precedence order the plan's Architecture section fixes. Each record carries `plan_id`, `state`, and a human-readable `detail` written to be printed directly. The map covers exactly the artifact's plan rows — which is precisely why orphans need this step's separate scan. Read the landed module for exact exported names; the landed names win over any spelling in this file. Its stance when the sidecar as a whole is unusable is fixed by step 3: `classify_draft_seeds` lets `RoadmapSeedStateError` propagate rather than catching it, and this step's own `find_orphan_seed_records` matches that stance (see Implementation) — the CLI layer, not the manifest module, is where that error becomes a rendered "unavailable" line instead of a crash. **This step is the one place in the plan that prints `stale` and `malformed` as visibly distinct words per plan** (step 7's summary folds both into one `invalidated` count). Until step 9 lands, an ordinary no-feedback revision can leave a changed plan's sidecar `status` at `current`, so `--view seeds` may print `malformed` where the true cause is an unacknowledged revision (see step 3's detail for why) — this is a real but self-resolving accuracy window in what this step displays, not a defect in this step's own rendering logic, and it does not change which remedy (`--materialize`) an operator would run either way.
- **Step 7's landed wiring.** Step 7 already makes `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view` call `classify_draft_seeds` for the summary and rewrites `_summary_attention`'s per-seed lines to name the per-state remedy (`--materialize`, accept-or-discard, roadmap revision). This step reuses that computed map (compute once per view invocation, pass it to whichever renderer needs it) and reuses step 7's per-state remedy wording rather than minting a second copy. Also follow step 7's landed choice for how `plan_tool/roadmap_view.py` refers to classification records in signatures — whether it imports the record type from `plan_tool.roadmap_seed_manifest` (widening the pinned import list in `tests/test_roadmap_view.py:test_module_imports_only_the_artifact_and_gates_leaves`) or reads `state`/`detail` attributes without importing the type. Whatever step 7 landed wins; do not introduce a second convention.
- **The `seed-state.json` schema** (`plan_tool/roadmap_seed_state.py:validate_seed_state`): per-plan-id entries carrying `draft_seed_path`, `status`, `digest`, `published`. The orphan scan reads entries whose keys match no plan row; it never writes the sidecar.
- **Step 1's directory names.** Step 1 renames `DRAFT_SEEDS_DIRNAME` in `plan_tool/roadmap_artifacts.py` to `plan-seed-drafts` and keeps the legacy `seeds/` prefix accepted read-only. The orphan scan's directory walk must use the landed constants for both names (step 1 owns their spelling), never a fresh string literal.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_view.py` — new seeds-view renderer plus its supplied-projection record type(s); `_render_draft_seed` and `render_traceability_walk` reworked to take the classification; shared per-state remedy wording reused from step 7's landed summary code.
  - `tests/test_roadmap_view.py` — new seeds-view cases; the five walk draft-seed cases rewritten against classification records; hygiene-test updates only as the landed step 7 convention requires.

  Necessary additions beyond the declared list (each forced by a commitment the step intent makes, noted per file):
  - `plan_tool/roadmap_seed_manifest.py` — the orphan-scan function and its record type live beside `classify_draft_seeds`, because `plan_tool/roadmap_view.py`'s stated contract (the `SeedLifecycleSummary` docstring's supplied-projection stance) forbids the view opening the sidecar, and the CLI handler must stay thin.
  - `tests/test_roadmap_seed_manifest.py` — the orphan-scan cases.
  - `plan_tool/cli/roadmap_cmd.py` — the `--view seeds` choice, its dispatch branch in `_cmd_roadmap_view`, passing the classification into the walk call, and the module-docstring/help-text view-list sweep.
  - `tests/cli/test_roadmap_cmd.py` — dispatch and flag-combination coverage for the new choice.
  - `plan_tool/cli/console.py` — a `seeds` entry in `_ROADMAP_VIEW_TITLES` so the banner names the view instead of falling back to the generic title.
  - `docs/cli/roadmap.md` — regenerated via `python -m plan_tool.cli_reference --write` (drift-guarded by `tests/cli/test_cli_reference.py`).
  - `README.md`, `plan_tool/cli/__init__.py`, `ROADMAP_FORMAT.md` — the three remaining sites that enumerate the view choice list `{summary,walk,ledger,index}`; each gains `seeds` in its enumeration (see the sweep list in Implementation).

## Implementation

Three pieces, in dependency order: the orphan scan, the view renderer, the walk reroute.

**1. The orphan scan (`plan_tool/roadmap_seed_manifest.py`).**

- Add a read-only function — one way: `find_orphan_seed_records(artifact, *, plans_dir, slug)` — returning orphan records of two kinds, each carrying enough to print one self-contained line:
  - **sidecar orphans** — `seed-state.json` entries keyed by a plan id no `artifact.plans` row carries;
  - **file orphans** — files sitting directly in the roadmap's `plan-seed-drafts/` directory, when it exists, and its legacy `seeds/` directory, when that exists, that no plan row's resolved `draft_seed_path` (via `plan_tool.roadmap_artifacts.resolve_draft_seed_path`) points at. **Both directories get the same existence guard, not only the legacy one.** Today `plan-seed-drafts/` is unconditionally created by stage 4's inline bundle write, so its absence is untested and easy to assume away — but once step 9 retires that write path, step 2's `materialize_plan_seed` is the only thing that ever creates it, and a freshly generated roadmap with no plan yet materialized has no `plan-seed-drafts/` directory on disk at all. This step depends only on steps 3 and 7 (not 9) and is never revisited once step 9 lands, so the directory-existence check must be unconditional from the start, not added later: skip a directory's scan entirely when `.exists()` is false, for either directory, the same way. Add a test for a roadmap whose `plan-seed-drafts/` directory doesn't exist yet (no plan materialized) — `--view seeds` must report zero file orphans, not raise.
- **Match by resolved path, not by prefix.** A legacy roadmap's plan row referencing `seeds/foo.md` owns the file in the legacy directory; the two-directory walk exists to catch genuinely unreferenced files in either directory, not to flag legacy-prefix rows.
- **Skip the `archive/` subdirectory and any other directories.** Archived `.replaced.N` generations (the shape `plan_tool/roadmap_seed_state.py:_matching_plan_id` recognizes) are deliberate history, not orphans. Walk the top level of each directory only; skip non-files.
- **A corrupt sidecar propagates, the same as `classify_draft_seeds`; an absent sidecar does not, and is not an error at all.** `find_orphan_seed_records` must not itself catch `RoadmapSeedStateError` — mirroring the landed `classify_draft_seeds`'s stance (see Input: it lets that error propagate for its caller to convert, per step 3's own contract) keeps the two manifest-layer functions consistent with each other, rather than one leaf swallowing an error its neighbor deliberately raises. A genuinely absent sidecar is a different case and stays exactly as described below: `load_seed_state` already returns an empty state for a missing file, so an absent sidecar means zero sidecar orphans, no exception at all. Converting a propagated `RoadmapSeedStateError` into something a view can render without crashing is the CLI dispatch layer's job, not this function's — see the CLI wiring bullet below, which reuses step 7's summary-branch pattern for the identical failure.
- **Emission cardinality:** one record per orphan (per sidecar entry, per file), in a deterministic order — sorted plan ids for sidecar orphans, sorted filenames per directory for file orphans — so repeat renders are identical.
- The classification is deliberately not consumed here: a `duplicate` basename collision means the file *is* referenced (twice), so it is not an orphan; the two judgments stay independent.

**2. The seeds view (`plan_tool/roadmap_view.py` + CLI wiring).**

- Add a renderer — one way: `render_seed_state_view(loaded, classifications, orphans, *, unavailable_reason=None)` — that takes the classification map and orphan records as supplied data and touches no disk. It opens with the same `_mode_header` / `_artifact_notice` lines every sibling view prints. `unavailable_reason` mirrors `summarize_seed_lifecycle`'s existing keyword-only parameter (step 7): when given, print a single unavailable-seeds line naming it and stop, before the `seeds:`/`orphans:` sections — the same fold step 7's summary view already applies for the identical sidecar-unusable failure. `classifications`/`orphans` are only meaningful when `unavailable_reason` is `None`.
- When `loaded.plans is None`, print that per-plan seed states cannot be reported (naming absent versus unparseable, which `loaded.absent` / `loaded.unparseable` already distinguish) and stop — without plan rows, "orphan" is not decidable either, and guessing would misreport every file. Say that in the rendered text rather than printing an empty report.
- Otherwise, when `unavailable_reason` is `None`, render, in this order:
  - a `seeds:` section, one line per plan row in artifact order: the plan id, its `state`, and the record's `detail` printed verbatim (step 6's precedent — the classifier's `detail` is written to be surfaced, never re-derived);
  - a per-state remedy on each non-`current` line, using step 7's landed state-to-remedy wording. One way to keep the two surfaces from drifting: extract the mapping step 7 lands in its summary-attention code into a small module-level helper both call. If that extraction pulls step 7's landed tests around, prefer calling the same wording constants over restructuring.
  - an `orphans:` section with two labeled sub-lists (sidecar entries naming no plan row; files naming no plan row), each with an explicit `(none)` when empty, matching the module's stated-empty convention.
- Never raises; every odd state is a rendering annotation, per the module docstring's contract.
- CLI: add `seeds` to the `--view` choices in `plan_tool/cli/roadmap_cmd.py:register`, add the dispatch branch in `_cmd_roadmap_view`: call `classify_draft_seeds` and `find_orphan_seed_records` inside the same `try/except RoadmapSeedStateError` shape the `summary` branch immediately above already uses (step 7) — on success, hand both results to `render_seed_state_view`; on `RoadmapSeedStateError`, call `render_seed_state_view(loaded, {}, (), unavailable_reason=str(exc))` instead of crashing, so `--view seeds` degrades to one unavailable line the same way `--view summary` already does for the identical corrupt-sidecar failure, rather than inventing a second try/except shape for the same error. Keep the existing pre-dispatch rule that rejects `--id` with any view but `index` — `--id seeds` combinations must keep failing with the current message. A completed `--view seeds` render exits 0 unconditionally, per the module's exit-code convention; no state, orphan, or unavailable-sidecar case changes the rc.

**3. The walk reroute (`plan_tool/roadmap_view.py:_render_draft_seed`).**

- `render_traceability_walk` gains a required classification-map parameter, threaded down to `_render_draft_seed`, which drops its own `is_file()` / `parse_draft_seed_provenance` judgment and prints the plan's classified `state` (and `detail` for a non-`current` draft) instead — the same word the seeds view prints for the same record.
- For a `current` draft, keep today's provenance body: read the file and print its `roadmap_components` ids literally (still never resolved through `resolve_id` — checking them stays the classifier's job). This keeps the module's single `read_text` call, so `tests/test_roadmap_view.py:test_module_reads_disk_only_through_the_artifact_loaders_and_the_draft_seed_read` stays true as written (`read_text(` count of one); a read that fails anyway (the file changed between classification and render) degrades to a marker line, never a raise. `_render_draft_seed`'s own docstring currently says checking a draft's `roadmap_components` against its plan row's `component_ids` "stays `check_draft_seed_provenance`'s job" (`plan_tool/roadmap_view.py`) — step 9 deletes that function, so update this docstring in the same edit to cite step 3's `validate_draft_seed_content`/`classify_draft_seeds` instead, not left as a dangling reference to a removed function.
- A plan id the map lacks should render a distinct marker rather than raise — unreachable when the CLI supplies the map (step 3's contract covers every plan row), but the walk's never-raises contract holds for hand-assembled inputs too.
- The walk's other guarantees are not free to vary: body identical under both modes, identical on repeat calls, plans in `ordering` sequence with the existing duplicate/ambiguous markers. The classification is mode-independent and computed once by the caller, so both hold without new work — keep the existing tests proving them green.

**The choice-list sweep.** Five sites enumerate the view set and each must gain `seeds`: `plan_tool/cli/roadmap_cmd.py` (module docstring and `register`'s help text), `plan_tool/cli/__init__.py`'s usage block, `README.md`'s command catalog line, `ROADMAP_FORMAT.md`'s module-family bullet naming `roadmap_view.py`, and the regenerated `docs/cli/roadmap.md`. Grep for `summary,walk,ledger,index` (and its spaced variant) after editing to confirm the sweep found every site.

**Constraints that are not free to vary:**

- `plan_tool/roadmap_view.py` opens neither the sidecar nor the manifest module's disk paths itself — the supplied-projection stance is a stated module contract, and the hygiene tests in `tests/test_roadmap_view.py` pin it mechanically.
- No edge appears between `plan_tool/roadmap.py` and `plan_tool/roadmap_view.py` in either direction (the plan's architecture rule); the manifest module never imports the view.
- The printed state vocabulary is step 3's constants, never a local respelling — the whole point is that promotion refusal, the summary, the walk, and this view use one word per state.

## Tests

### Tests for this step

Every test below must be green before this step is finished.

`tests/test_roadmap_view.py` — new seeds-view cases (hand-built classification and orphan records, per the module's fixture policy):

- `test_seeds_view_prints_one_line_per_plan_row_with_its_state` — all seven states across seven plan rows each render their state word and `detail`, in artifact order.
- `test_seeds_view_states_use_the_classifier_constants` — the rendered state words are the `DRAFT_SEED_STATE_*` values, asserted against the imported constants, not string literals.
- `test_seeds_view_non_current_lines_name_the_same_remedy_as_the_summary` — a non-`current` state's remedy wording matches step 7's summary-attention wording for the same state (one source, no drift).
- `test_seeds_view_renders_sidecar_and_file_orphans_in_their_own_sections` — supplied orphan records of both kinds render under the two labeled sub-lists.
- `test_seeds_view_empty_orphan_sections_are_stated_not_dropped` — no orphans renders both sub-lists with an explicit `(none)`.
- `test_seeds_view_unreadable_plans_artifact_reports_unavailable_not_empty` — `loaded.plans is None` renders the unavailable explanation and no per-plan or orphan lines.
- `test_seeds_view_names_its_mode_and_the_absent_unparseable_files` — the shared header/notice lines, matching the sibling views' cases.
- `test_seeds_view_render_is_the_same_on_repeat_calls` — determinism over the same inputs.

`tests/test_roadmap_view.py` — walk reroute (rewrites of the five existing draft-seed cases; a red sibling here is the expected class-sweep outcome, not a reason to narrow):

- `test_walk_prints_seed_path_and_provenance_for_a_current_seed` — a `current` classification still renders the seed path and `roadmap_components` ids read off disk.
- `test_walk_names_each_non_current_state_from_the_classification` — parametrized over the six non-`current` states: the walk line renders the classified state word, with no file-existence probe deciding it (e.g. a `digest-mismatched` record for a file that exists and parses renders flagged, not clean — the mistracked-drift case this plan exists to catch).
- `test_walk_and_seeds_view_agree_on_one_drafts_state_word` — the same classification record renders the same state word in both views.
- `test_walk_current_seed_whose_file_vanished_degrades_to_a_marker_not_a_raise` — the read-failure fallback.
- `test_walk_plan_missing_from_the_classification_map_renders_a_marker` — the never-raises contract for hand-assembled inputs.
- The existing mode-invariance and repeat-call walk tests stay green unchanged.

`tests/test_roadmap_view.py` — hygiene:

- `test_module_reads_disk_only_through_the_artifact_loaders_and_the_draft_seed_read` — stays green as written (single `read_text`, no `open(`, no invoker).
- `test_module_imports_only_the_artifact_and_gates_leaves` — updated only if step 7's landed convention already widened the import list; otherwise unchanged.

`tests/test_roadmap_seed_manifest.py` — orphan scan:

- `test_sidecar_entry_naming_no_plan_row_is_an_orphan` — one record per unmatched entry.
- `test_file_in_the_draft_dir_no_plan_row_names_is_an_orphan` — and the record carries the path.
- `test_file_in_the_legacy_seeds_dir_is_scanned_too` — an unreferenced file in legacy `seeds/` is found.
- `test_legacy_prefix_plan_row_owns_its_legacy_file` — a row referencing the legacy path leaves that file un-orphaned (resolved-path matching).
- `test_archive_subdirectory_is_skipped` — `.replaced.N` generations produce no orphan records.
- `test_no_sidecar_and_empty_dirs_produce_no_orphans` — the clean roadmap returns an empty result, not an error.
- `test_orphan_records_come_back_in_deterministic_order` — sorted ids and filenames.
- `test_unusable_sidecar_propagates_matching_the_classifier_stance` — a corrupt `seed-state.json` raises `RoadmapSeedStateError` out of `find_orphan_seed_records`, the same as the landed `classify_draft_seeds` does for the same input — not caught and swallowed here.

`tests/cli/test_roadmap_cmd.py`:

- `test_view_seeds_dispatches_to_the_seeds_renderer_and_exits_zero` — including on a roadmap full of non-`current` states (findings never flip the rc).
- `test_view_seeds_rejects_id` — `--id` with `--view seeds` keeps the existing rc-2 rejection.
- `test_view_seeds_folds_a_corrupt_sidecar_into_an_unavailable_line_not_a_crash` — a corrupt `seed-state.json` renders the unavailable-seeds line (naming the classifier's error text) and exits 0, mirroring `test_view_summary`'s existing unavailable-sidecar case (step 7) rather than raising `RoadmapSeedStateError` out of the CLI.
- `test_view_walk_passes_the_classification` — the walk call site supplies the computed map.
- `tests/cli/test_cli_reference.py` — green after regenerating `docs/cli/roadmap.md`.

## Acceptance criteria

- `plan-tool roadmap <slug> --view seeds` renders one line per plan row in `04-roadmap.md` carrying that plan's step 3 state and `detail`, plus the two orphan sub-lists, and exits 0 for every combination of states.
- A draft whose sidecar says `current` but whose bytes drifted past the recorded digest renders as `digest-mismatched` in **both** `--view walk` and `--view seeds` — no view calls it clean.
- The walk's old self-judged wording keyed on `is_file()`/parse (`⚠ missing draft seed:` / `⚠ unparseable draft seed:` as its own verdicts) is gone from `plan_tool/roadmap_view.py:_render_draft_seed`; states come only from the supplied classification.
- An unreferenced file in the legacy `seeds/` directory appears in the orphans section; a legacy-prefix plan row's own file does not.
- A corrupt `seed-state.json` renders `--view seeds` as a single unavailable-seeds line (exit 0), never a raised `RoadmapSeedStateError` out of the CLI — the same fold `--view summary` already applies for the identical failure.
- `rg 'summary,walk,ledger,index'` (and the spaced variant) over the repo returns no site missing `seeds` in its enumeration.
- `tests/test_roadmap_view.py:test_module_reads_disk_only_through_the_artifact_loaders_and_the_draft_seed_read` passes unmodified.
- Every test enumerated above passes; `uv run pytest tests/test_roadmap_view.py tests/test_roadmap_seed_manifest.py tests/cli/test_roadmap_cmd.py -q` is green.

## References

- `ROADMAP_FORMAT.md` — the staged-artifact and `seed-state.json` contract this step reads, and one of the five view-list sweep sites.
- `DATA_CONTRACT.md` — the persisted sidecar schema conventions behind the orphan scan's sidecar half.

## Applicable guardrails

- **The plan's "## Out of scope", regeneration and deletion fence** — this step reports orphans and broken states only: no view writes, deletes, regenerates, or promotes anything, and the seeds view recommends the explicit surfaces (`--materialize`, `--apply`, a revision) rather than acting. Orphan cleanup specifically stays out; the report makes the orphan visible and stops.
- **The plan's "## Out of scope", no correctness gate on seed content** — the seeds view is a rendering surface, not a gate: no state, count, or orphan changes the exit code, and no finding blocks any other verb. The binary observable stays step 3's classification; this step only displays it.
- **The plan's "## Out of scope", no second seed store** — the orphan scan reads the existing `seed-state.json` sidecar and the draft directories; it introduces no new persisted state, cache, or index.
- **The plan's "## Step intent" (this step)** — binds the footprint hardest at the walk reroute: the intent names `_render_draft_seed` and the two-directory scan explicitly, so leaving either half undone (a seeds view without the walk agreeing, or a scan of only the new directory) does not satisfy the step.

## Deferred

- Orphan cleanup (deleting or archiving an orphaned sidecar entry or file) — reporting only, per the step intent; a cleanup action would be a new mutating surface routed to `BACKLOG.md` if wanted.
- Acting on a `digest-mismatched` draft — step 10 owns the accept action; this step only renders the state and points at the choice.
- Consolidating the three generate-parse-retry loops, the fence-scan copies, or any other cross-module refactor noticed en route — out of this read-only step; file in `BACKLOG.md`.
- A `--view seeds --id <plan>` single-plan filter — `--id` stays index-only; widening it is a separate CLI decision, not implied by this step.
- Extending `annotate`, `create`, or promotion behavior based on orphan findings — the plan's other steps own their consumers; this step changes no verb but `--view`.
