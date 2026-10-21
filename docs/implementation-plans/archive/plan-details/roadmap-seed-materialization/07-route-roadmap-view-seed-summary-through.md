> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Route the roadmap view's seed summary through the new manifest module

## Summary

Swaps `summarize_seed_lifecycle`'s input in `plan_tool/roadmap_view.py` from the raw `seed-state.json` mapping to step 3's per-plan classification map, folding the seven states into the summary's coarse counts — `current` stays `current`, every other state counts as `invalidated`, and the `untracked` bucket disappears since the classifier answers for every plan row. `_summary_attention`'s per-seed guidance lines stop uniformly recommending `--refresh-seeds` and instead read each plan's classification directly, naming the specific tool that clears that state (`--materialize` for the four regenerable states, an accept-or-discard choice for `digest-mismatched`, a roadmap revision for `duplicate`). The key design decision: the view keeps its supplied-projection stance — the CLI calls `classify_draft_seeds` and passes the result in, so the summary's unit tests stay hand-built classification records rather than on-disk draft trees. On green, `--view summary` shows a hand-edited draft whose sidecar still says `current` as invalidated, which is the mistracked-drift case this plan exists to catch, and every seed attention line recommends a command that actually fixes its state.

## Table of Contents

- [Why](#why) — what the summary gets wrong today and what routing through the classifier fixes
- [Input](#input) — step 3's classifier contract and the current summary shapes this step rewires
- [Files (creates vs edits)](#files-creates-vs-edits) — the two declared files plus the CLI call-site edits the signature change forces
- [Implementation](#implementation) — the fold, the per-state attention lines, the retired untracked bucket, and the CLI wiring
- [Tests](#tests) — rewritten summary tests, new per-state cases, and the hygiene-test updates
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Today `summarize_seed_lifecycle` in `plan_tool/roadmap_view.py` reads only the sidecar's raw `status` strings: an entry saying `current` counts as current no matter what is actually on disk. A hand edit that drifted the file past its recorded digest, a draft that fails provenance validation, a path-escaping sidecar path, and a basename collision all render as healthy in `--view summary` — exactly the blind spots step 3's `classify_draft_seeds` was built to close for every consumer at once. The summary's attention lines have the matching problem: both the `invalidated` and `untracked` loops in `_summary_attention` recommend `--refresh-seeds`, which regenerates *every* draft — after step 5 ships `--materialize`, that advice steers an operator toward redoing work that is already fine, and for a `digest-mismatched` draft it steers them toward destroying the very hand edit step 10's accept action exists to preserve. This step makes the summary the second view consumer of step 3's single classification (step 6's promotion refusal being the write-side consumer) so the coarse counts and the recommended remedies both tell the truth.

## Input

This step consumes two contracts it does not own and rewires one it does:

- **Step 3's classifier**, `plan_tool.roadmap_seed_manifest.classify_draft_seeds(artifact, *, plans_dir, slug) -> dict[str, DraftSeedClassification]`, plus the seven `DRAFT_SEED_STATE_*` constants (`current`, `missing`, `stale`, `malformed`, `path-escaping`, `duplicate`, `digest-mismatched`). Each `DraftSeedClassification` carries `plan_id`, `state`, and a human-readable `detail`. The map covers exactly the artifact's plan rows — no retired sidecar entry can appear, which is why the view-side "ignore ids not in the artifact" filtering and the `untracked` bucket both retire here. Step 3's module lands before this step runs; read the landed module for the exact exported names and for which error type it raises when the sidecar as a whole is unusable (versus folding the problem into per-plan states) — the landed names win over any spelling this plan suggested. **`malformed` and `stale` fold into the same `invalidated` bucket here** (see this step's Summary), so the stale/malformed misattribution window step 3's detail describes (only fully resolved once step 9 lands) has no effect on this step's coarse counts — it can only affect `--view seeds`' per-plan detail line (step 8), never this fold.
- **Step 5's and step 10's command spellings.** The attention lines this step writes name `--materialize <plan-id>` (step 5) and the accept action (step 10, `--accept-seed` per the plan). Step 10 lands after this step, so the summary names an accept flag that ships later in the same plan — the plan's step 7 intent accepts that window deliberately; keep the wording aligned with step 10's intent and let step 10's own tests pin the argv.
- **The shapes this step rewires**, all in `plan_tool/roadmap_view.py`: `SeedLifecycleSummary` (fields `tracking`, `current_plan_ids`, `invalidated_plan_ids`, `untracked_plan_ids`, `reason`), `summarize_seed_lifecycle(loaded, seed_state=None, *, unavailable_reason=None)`, `_summary_seed_line`, and `_summary_attention`. The only external caller is `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view`'s summary branch, which today loads the sidecar via `roadmap_seed_state.load_seed_state` and folds `RoadmapSeedStateError` into `unavailable_reason`. `render_roadmap_summary(loaded, seed_lifecycle)`'s two-argument signature is pinned by `tests/cli/test_roadmap_cmd.py`'s `test_view_summary_calls_summary_renderer_with_lifecycle_snapshot` and should stay unchanged.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_view.py` — import the classifier types from `plan_tool.roadmap_seed_manifest`; change `summarize_seed_lifecycle` to take the classification map instead of the raw sidecar mapping; fold non-`current` states into `invalidated_plan_ids`; delete `SEED_TRACKING_UNTRACKED` and `untracked_plan_ids`; carry the classification map on `SeedLifecycleSummary` for `_summary_attention` (and step 8); rewrite `_summary_seed_line`'s counts and `_summary_attention`'s per-seed lines; update the `SeedLifecycleSummary` docstring.
  - `tests/test_roadmap_view.py` — rewrite the summary/lifecycle fixtures to hand-built classification records, add the per-state fold and attention cases, update the two leaf-hygiene tests for the new import.
  - `plan_tool/cli/roadmap_cmd.py` — **necessary addition** (not in the step's declared list): `_cmd_roadmap_view`'s summary branch must supply the classification once the raw-sidecar parameter is gone; it swaps `load_seed_state` for a `classify_draft_seeds` call. The step cannot land without this call-site edit.
  - `tests/cli/test_roadmap_cmd.py` — **necessary addition**: the summary-branch wiring test pins the old call shape and follows the edit above.

## Implementation

- **Keep the view's supplied-projection stance: the CLI classifies, the view folds and renders.** `SeedLifecycleSummary`'s docstring states the design — the module accepts a small data projection instead of opening the sidecar itself — and this step keeps it true, just with a richer projection. The rejected alternative was having `summarize_seed_lifecycle` take `plans_dir` and call `classify_draft_seeds` itself; that would collapse the CLI branch further but would force every summary unit test onto on-disk draft/sidecar fixtures and couple the view's tests to the classifier's disk behavior (the same coupling the accumulated lessons warn against for consumer tests). With the map passed in, the view tests build `DraftSeedClassification` records directly, matching the file's stated fixture policy.
- **`summarize_seed_lifecycle` signature:** replace the `seed_state` mapping parameter with the classification map (e.g. `classifications: Mapping[str, DraftSeedClassification]`). Keep the two branches the classifier cannot answer:
  - `loaded.plans is None` → `SEED_TRACKING_UNAVAILABLE` with the existing "04-roadmap.md is not readable" reason, unchanged.
  - `unavailable_reason` given → unavailable, unchanged. The CLI keeps folding a sidecar-level failure from the classifier into this parameter (see the CLI bullet). If the landed classifier turns out never to raise — folding every sidecar problem into per-plan states — this arm narrows to the unreadable-stage-4 case; verify at HEAD and adjust the unavailable test accordingly.
  - Otherwise fold: iterate `loaded.plans.plans` in artifact order (not the map's iteration order) and bucket each row's state — `current` → `current_plan_ids`, everything else → `invalidated_plan_ids`. Compare states against the `DRAFT_SEED_STATE_*` constants, not string literals.
- **Delete the untracked bucket rather than leaving it dead.** Remove `SEED_TRACKING_UNTRACKED`, the `untracked_plan_ids` field, `_summary_seed_line`'s three-count branch, and `_summary_attention`'s untracked loop. Nothing outside `plan_tool/roadmap_view.py` and its tests consumes them (the CLI imports only `summarize_seed_lifecycle` itself). `tracking` becomes two-valued: `SEED_TRACKING_TRACKED` or `SEED_TRACKING_UNAVAILABLE`. A plan row with no sidecar entry now arrives already classified (`missing` or `digest-mismatched` — step 3 owns that call), so it counts as invalidated instead of untracked; that is the intended behavior change, not a regression.
- **Carry the per-plan classification on the summary.** Add the map (or an equivalent per-plan tuple) as a field on `SeedLifecycleSummary` so `_summary_attention` can read each plan's `state` and `detail` without a second parameter — this keeps `render_roadmap_summary(loaded, seed_lifecycle)`'s signature unchanged, which keeps the CLI dispatch test green and gives step 8's report lines the same source through the same object. Exact field shape is the implementer's; the constraint is that state and detail per plan id reach the renderer.
- **`_summary_attention`'s per-seed lines**, replacing the two `--refresh-seeds` loops, in artifact plan order, keeping their current position in the priority queue (after indexed references, before decisions):
  - `missing`, `stale`, `malformed`, `path-escaping` → one line naming the plan id and its state in the classifier's own vocabulary, recommending `_summary_command(loaded, f"--materialize {plan_id}")`.
  - `digest-mismatched` → its own distinct line: the draft was edited since generation — review the diff, then accept the edit (step 10's accept action) or discard it (`--materialize <plan-id>`). Do not fold this state into the bare `--materialize` line; the whole point of the split is not steering an operator toward destroying a reviewable hand edit.
  - `duplicate` → a line saying the plan rows' `draft_seed_path` basenames collide and the fix is a roadmap revision; recommend no regeneration command, because none fixes a row collision. The classification's `detail` names the colliding sibling — using it here is one way to keep the line specific.
  - Keep the existing sidecar-unavailable attention line unchanged.
  - `--refresh-seeds` no longer appears in any per-plan line. It remains a valid command for regenerate-everything, but the summary stops presenting it as the remedy for one plan's state.
- **CLI wiring** (`plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view`, summary branch): replace the `seed_state_path` / `load_seed_state` block with a call to `classify_draft_seeds(loaded.plans, plans_dir=plans_dir, slug=loaded.slug)` when `loaded.plans` is not `None`, keeping the try/except that folds the classifier's sidecar error into `unavailable_reason=str(exc)`. The `state_path.exists()` pre-check goes away — a missing sidecar is now an ordinary classifier input, not a separate branch.
- **Constraints that are not free to vary:**
  - The fold is for the coarse counts only. The seeds count line stays two buckets (`N current · N invalidated`); per-state count lines and any new report section belong to step 8.
  - `render_roadmap_summary` stays deterministic and bounded (`_SUMMARY_ATTENTION_LIMIT` unchanged).
  - The view never re-derives any classification rule locally — no digest check, no `parse_draft_seed_provenance` call, no file probe in the summary path. The classifier's verdict is final; step 6's "same word every consumer uses" naming discipline applies to the state vocabulary in every line.
  - `plan_tool.roadmap_seed_manifest` sits below `roadmap_view.py` (step 3 documents the edge), so the new import keeps the module-family chain acyclic; import nothing else new — in particular nothing from `plan_tool.roadmap` or `plan_tool.roadmap_seed_state`.

## Tests

All in `tests/test_roadmap_view.py` unless noted. Fixtures build `DraftSeedClassification` records directly, per the file's stated policy; one deliberate seam case drives the real classifier.

### Tests for this step

Every test below must be green before this step is finished.

- `test_summary_reports_compact_counts_and_actionable_review_queue` (rewrite) — lifecycle fixture becomes a classification map; still asserts `0 current · 1 invalidated`; the `--refresh-seeds` assertion becomes `--materialize plan-checkout`; the retired-plan assertion drops (the map cannot carry retired ids — step 3's contract).
- `test_summary_folds_every_non_current_state_into_invalidated` (new, parametrized over the six non-`current` states) — each state counts as invalidated; `current` counts as current.
- `test_summary_seed_counts_have_exactly_two_buckets` (new) — the seeds line renders `N current · N invalidated` with no untracked term anywhere in the summary.
- `test_attention_recommends_materialize_for_each_regenerable_state` (new, parametrized over `missing`/`stale`/`malformed`/`path-escaping`) — the line names the plan id, the state in the classifier's word, and `--materialize <plan-id>`.
- `test_attention_digest_mismatched_offers_accept_or_discard` (new) — the line is distinct from the plain `--materialize` form and names both the accept action and `--materialize <plan-id>`.
- `test_attention_duplicate_recommends_a_roadmap_revision_not_regeneration` (new) — the duplicate line names no `--materialize` and no `--refresh-seeds`.
- `test_attention_never_recommends_refresh_seeds_per_plan` (new) — a summary over a mixed-state fixture contains no per-plan `--refresh-seeds` recommendation.
- `test_summary_unreadable_stage_four_stays_unavailable` (rewrite of the existing `loaded.plans is None` coverage) — no classification map required; the unavailable reason renders unchanged.
- `test_summary_marks_a_malformed_lifecycle_sidecar_unavailable` (kept or rewritten to match the landed classifier's error behavior) — `unavailable_reason` still renders the unavailable seeds line and its attention item.
- `test_summary_folds_a_real_classifier_result` (new seam case, `tmp_path`) — builds one on-disk roadmap with a draft and sidecar, runs the real `classify_draft_seeds`, feeds the result to `summarize_seed_lifecycle`, and asserts the two modules' types fit.
- `test_module_imports_only_the_artifact_and_gates_leaves` (update) — the expected import list and the subprocess allowed set gain `plan_tool.roadmap_seed_manifest` plus whatever it transitively pulls in (read the landed module's imports; `plan_tool.roadmap_seed_state` is the likely addition). Rename the test if its name stops matching its allowed set.
- `test_module_reads_disk_only_through_the_artifact_loaders_and_the_draft_seed_read` (unchanged, verify) — this step adds no `read_text`/`open(` to the module's own source, so the assertion holds as written.
- `tests/cli/test_roadmap_cmd.py::test_view_summary_calls_summary_renderer_with_lifecycle_snapshot` (update as needed) — still asserts `render_roadmap_summary` receives `(loaded, summary)`; adjust the stubbing for the summary branch's new `classify_draft_seeds` call, and cover the error-fold path (classifier's sidecar error → unavailable summary, rc 0).

## Acceptance criteria

- `summarize_seed_lifecycle` no longer accepts a raw sidecar mapping; its classification input is the map `classify_draft_seeds` returns, and a plan classified anything but `current` appears in `invalidated_plan_ids`.
- `rg 'untracked' plan_tool/roadmap_view.py` returns nothing: `SEED_TRACKING_UNTRACKED`, `untracked_plan_ids`, and the untracked rendering/attention code are gone.
- The rendered summary's seeds line has exactly the two buckets `current` and `invalidated`; `tracking` is only ever `tracked` or `unavailable`.
- For each of `missing`, `stale`, `malformed`, `path-escaping`, the attention queue names the state and recommends `--materialize <plan-id>`; for `digest-mismatched` it offers accept-or-discard; for `duplicate` it recommends a roadmap revision with no regeneration command; no per-plan line names `--refresh-seeds`.
- `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view`'s summary branch calls `classify_draft_seeds` and no longer calls `load_seed_state`; a sidecar-level classifier error still renders the unavailable seeds line instead of crashing the view.
- `render_roadmap_summary`'s signature is unchanged and `test_view_summary_calls_summary_renderer_with_lifecycle_snapshot` passes.
- Every test in the roster above is green, including both updated leaf-hygiene tests.

## References

- `ROADMAP_FORMAT.md` — the seven-state classification, its precedence order, and the manifest module's leaf position, as documented by step 3; the vocabulary this step's rendered lines must match.
- `DATA_CONTRACT.md` — the `seed-state.json` sidecar schema the classifier reads; useful context for why the view itself no longer touches it.
- `docs/ROADMAP_WALKTHROUGH.md` — the operator-facing narrative of the view surfaces; step 11 updates it, but it shows where the summary sits in the workflow this step's recommendations feed.

## Applicable guardrails

- **The plan's step 7 intent fence** — the fold serves the coarse counts only; the per-state detail stays in the attention lines and, later, step 8's report lines. This step must not add per-state count rows or new summary sections, and must keep the `digest-mismatched`/`--materialize` split exactly as the intent draws it.
- **The plan's "## Out of scope", no writes without an explicit action** — this step is render-only: `plan_tool/roadmap_view.py` keeps zero write paths, and no attention line may trigger regeneration itself, only recommend a command.
- **The plan's "## Out of scope", no seed-quality gate** — the summary reports the classifier's binary states and nothing else; no style, length, or content judgment enters the view.
- **The plan's "## Out of scope", only the necessary extraction** — the view consumes the classification; it does not re-implement any part of it. Any urge to add a local file or digest probe in the summary path is the tempting violation site here.
- **Step 8's boundary** — `_render_draft_seed` and the walk view stay untouched; routing them through the classifier is step 8's declared work, and doing it here would swallow a sibling step.

## Deferred

- Per-state report lines in the views and the orphan (no-matching-plan-row) scan — step 8's declared scope, reading the same classification this step wires in.
- `_render_draft_seed`'s digest-blind walk warning — step 8 routes it through the classifier; until then the walk and the summary can disagree about a hand-edited draft, a transient the plan's step ordering accepts.
- The accept action itself — step 10; between this step and step 10 the digest-mismatched attention line names an accept flag that does not exist yet, a window the plan's step 7 intent explicitly chose.
- `_create_handoff_lines`' seed-readiness routing in `plan_tool/cli/roadmap_cmd.py` — step 9's declared work; this step's CLI edit touches only the view branch.
- `create --from-existing`'s stale-draft confirmation routing — step 3 owns it.
