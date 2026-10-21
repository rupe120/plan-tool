> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add a module that classifies every plan's draft seed into a named state

## Summary

Adds `plan_tool/roadmap_seed_manifest.py`, a new leaf module whose `classify_draft_seeds(artifact, *, plans_dir, slug)` sorts every plan row in a roadmap's `04-roadmap.md` into exactly one of seven states — `current`, `missing`, `stale`, `malformed`, `path-escaping`, `duplicate`, `digest-mismatched` — using the precedence order the plan's Architecture section already specifies. It reuses step 1's shared validators (`validate_draft_seed_content`, `find_duplicate_draft_seed_basenames`) and the existing `seed-state.json` sidecar, computing the classification fresh every call rather than storing it. The module is read-only: it never writes a draft file or the sidecar. A small necessary addition to `plan_tool/roadmap_seed_state.py` splits its private path/marker resolution out of the status-filtered `invalidated_seed_continuation` into a new, status-independent `locate_tracked_seed`, so `plan_tool/cli/authoring.py`'s `_confirm_invalidated_roadmap_seed` can route through the new classifier and prompt on *any* non-`current` state instead of only a raw `invalidated` sidecar flag. `ROADMAP_FORMAT.md` and `CLAUDE.md` document the new module and its position in the roadmap module family. On green, every later step in this plan (materialize targeting, promotion refusal, the two view steps, the accept action) calls `classify_draft_seeds` as its single source of per-plan draft state.

## Table of Contents

- [Why](#why) — the gap in today's status check and what one shared classifier buys every later step
- [Input](#input) — step 1's validators, the seed-state schema, and the narrow resolver this step widens
- [Files (creates vs edits)](#files-creates-vs-edits) — the declared files plus one necessary addition
- [Implementation](#implementation) — the classification algorithm, the resolver split, and the `create` routing
- [Tests](#tests) — coverage for the classifier, the resolver split, and the routed confirmation
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Today the only reader of `seed-state.json` outside `roadmap.py`/`roadmap_seed_state.py`/`roadmap_cmd.py` is `plan_tool/cli/authoring.py`'s `_confirm_invalidated_roadmap_seed`, and it only ever asks one question: does `roadmap_seed_state.invalidated_seed_continuation` find a tracked entry whose `status` is literally `"invalidated"`. That check is blind to every other way a draft can be untrustworthy — a hand edit that changed the file without going through generation (the sidecar's `digest` no longer matches, or was never recorded), a draft that fails step 1's provenance/component check while its sidecar status still says `current`, a plan row whose `draft_seed_path` basename collides with a sibling's, or a sidecar entry whose own `draft_seed_path` field was hand-edited into something `_validate_draft_seed_path` would reject. Every one of those drafts sails through `create --from-existing` today with no prompt at all.

The plan's later steps all need the same answer to "is this plan's draft safe to use right now" — step 5's `--materialize` needs to know which plan ids are recoverable, step 6's promotion refusal needs to know which drafts to block, steps 7 and 8 need it for the roadmap views, and step 10's accept action needs to know a draft is specifically `digest-mismatched` before it will touch it. Without this step, each of those would either duplicate the same seven-way judgment or, worse, five slightly different versions of it. This step gives them one function to call, and lets `create` be the first caller to benefit: it starts asking the honest question ("is this draft anything but `current`") instead of the narrow one it asks today.

## Input

This step is grounded in three contracts, two of which step 1 (`depends_on`) supplies and one of which it widens:

- **Step 1's shared validators**, `plan_tool.roadmap_gates.validate_draft_seed_content(text: str, *, plan: PlanRow) -> list[Violation]` and `plan_tool.roadmap_gates.find_duplicate_draft_seed_basenames(plans: Sequence[PlanRow]) -> list[Violation]`. Both take plan data directly — no `ArtifactEnvelope`, no bundle — which is exactly the shape a manifest sweep over an already-loaded `PlansArtifact` needs. `find_duplicate_draft_seed_basenames` compares each row's full `draft_seed_path` (prefix and basename together), not basename alone, and emits `VIOLATION_DUPLICATE_DRAFT_SEED_BASENAME` (renamed by step 1 in the same edit that extracts the function) for a genuine collision — this step reads that constant's violations, not a new one.
- **The renamed directory constants and widened path validator** in `plan_tool/roadmap_artifacts.py`: `DRAFT_SEEDS_DIRNAME` (`"plan-seed-drafts"`), the new legacy-prefix constant, and `_validate_draft_seed_path`, which after step 1 accepts either prefix. This step's `path-escaping` check reuses `_validate_draft_seed_path` directly rather than re-implementing the parts/`..`/absolute-path checks a second time — it is, per the plan's own step 3 intent, this function's only consumer of the escape check applied to sidecar data rather than a plan row.
- **The unchanged `seed-state.json` schema** (`plan_tool/roadmap_seed_state.py`): `validate_seed_state`'s per-plan-id shape (`draft_seed_path`, `status` — `"current"`/`"invalidated"` — `digest`, `published`). This step adds no field and migrates nothing; `load_seed_state`, `seed_state_path`, and `digest_text` are the read primitives it calls directly, mirroring the two-line composition `plan_tool/roadmap.py`'s private `_load_roadmap_seed_state` already uses (`load_seed_state(seed_state_path(roadmap_dir(plans_dir, slug)))`) rather than importing that private helper — this module cannot import `plan_tool/roadmap.py` without creating the cycle Architecture rules out.
- **The existing narrow resolver**, `roadmap_seed_state.invalidated_seed_continuation` and its one production caller, `plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed`. Its docstring already states the two ways it locates a tracked seed from an arbitrary path — structurally, via `_structural_state_path`/`_matching_plan_id`, for a direct roadmap draft or its `archive/` copy; via the embedded HTML marker, for a promoted `plan-seeds/<id>.md` copy or its own archived generation. Both paths currently fold "found" and "is invalidated" into one check. This step needs the "found" half on its own, decoupled from status, so `_confirm_invalidated_roadmap_seed` can hand the resolved `(plan_id, roadmap_slug)` to the new classifier instead. See Files/Implementation for the split this requires.

**What this step does not read or write:** it never opens a draft file for anything but classification, never calls step 2's `materialize_plan_seed`, and never writes `seed-state.json` or a `plan-seeds/` copy. Every write path (materialize, promote, accept) is a later step.

## Files (creates vs edits)

**New files:**

- `plan_tool/roadmap_seed_manifest.py` — the classifier: the seven state constants, the precedence order, `DraftSeedClassification`, and `classify_draft_seeds`.
- `tests/test_roadmap_seed_manifest.py` — its tests.

**Existing files (edits only):**

- `ROADMAP_FORMAT.md` — a new subsection under "## Draft seeds — side output under the roadmap slug" documenting the seven states, the precedence order, and this module's position in the roadmap module family.
- `CLAUDE.md` — bump "Roadmap's five modules" to six and add `roadmap_seed_manifest.py`'s edges to that bullet.
- `plan_tool/cli/authoring.py` — rewrite `_confirm_invalidated_roadmap_seed` to route through `classify_draft_seeds`; add the new imports this requires.
- `tests/cli/test_authoring_cmds.py` — new cases for the routed confirmation covering states beyond the old raw-`invalidated` check.

**`plan_tool/roadmap_seed_state.py` and `tests/test_roadmap_seed_state.py` (necessary addition, not in the plan's declared list — see below).**

**Why the addition is necessary:** `_confirm_invalidated_roadmap_seed` receives only a `source_path` — it does not know which roadmap or which plan id a seed belongs to until it is resolved. Today's `invalidated_seed_continuation` does that resolution, but it folds the resolution together with an `entry["status"] == "invalidated"` filter, so it structurally cannot report a tracked seed whose status is still `"current"` — exactly the case for a hand edit that never went through invalidation, or a corrupt/colliding draft. Reimplementing that resolution logic (the structural directory-name match, the archived-copy filename pattern, the marker-comment JSON parse) a second time inside the new leaf module would duplicate roughly 40 lines of matching logic that step 1 is *already* widening in place (to recognize both `seeds/` and `plan-seed-drafts/`) — a second copy doubles that drift risk exactly where step 1 just closed it once. The smaller, behavior-preserving fix is to split `invalidated_seed_continuation`'s existing body: extract its "find where this source's tracked entry lives" half into a new function, and turn `invalidated_seed_continuation` into a thin wrapper that calls it and then applies the same `status == "invalidated"` filter it always has. See Implementation for the exact split and why it is behavior-preserving for every existing caller and test.

## Implementation

### The classifier module

Add `plan_tool/roadmap_seed_manifest.py` as a leaf that imports only `plan_tool.roadmap_artifacts` and `plan_tool.roadmap_gates` (for the shared validators) and `plan_tool.roadmap_seed_state` (for the sidecar). It must **not** import `plan_tool.roadmap` or `plan_tool.roadmap_view` — both will call into this module starting with later steps (step 3's own intent describes this module's position "as a leaf below `roadmap.py` and `roadmap_view.py`, like `roadmap_gates.py`"), so the reverse import would be the cycle Architecture's layering rules out.

Seven module-level string constants, one per state, plus a precedence tuple that states the "first match wins" order directly rather than leaving it implicit in the code's branch order — this is what lets a test iterate the order and what lets the docs cite one source instead of re-deriving it:

```
DRAFT_SEED_STATE_DUPLICATE = "duplicate"
DRAFT_SEED_STATE_PATH_ESCAPING = "path-escaping"
DRAFT_SEED_STATE_MISSING = "missing"
DRAFT_SEED_STATE_DIGEST_MISMATCHED = "digest-mismatched"
DRAFT_SEED_STATE_STALE = "stale"
DRAFT_SEED_STATE_MALFORMED = "malformed"
DRAFT_SEED_STATE_CURRENT = "current"

DRAFT_SEED_STATE_PRECEDENCE = (
    DRAFT_SEED_STATE_DUPLICATE,
    DRAFT_SEED_STATE_PATH_ESCAPING,
    DRAFT_SEED_STATE_MISSING,
    DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    DRAFT_SEED_STATE_STALE,
    DRAFT_SEED_STATE_MALFORMED,
    DRAFT_SEED_STATE_CURRENT,
)
```

A frozen result type, one per plan: `DraftSeedClassification(plan_id: str, state: str, detail: str = "")`. `detail` is a human-readable elaboration later steps surface directly — the colliding plan ids for `duplicate`, the `_validate_draft_seed_path` error for `path-escaping`, `validate_draft_seed_content`'s violation messages for `malformed`, and so on. Leave it empty for `current` and `stale` (the state name says everything a caller needs). This mirrors step 1's own `Violation.message` design (a message written to be read standalone), and it is what step 5's "already current/duplicate" refusal, step 6's per-state apply refusal, and step 10's "reports the validation failure" all need without re-deriving it.

The entry point, `classify_draft_seeds(artifact: PlansArtifact, *, plans_dir: Path, slug: str) -> dict[str, DraftSeedClassification]`, keyed by plan id. A dict is safe here (unlike a parse-time collection) because `check_duplicate_row_ids` already blocks two plan rows sharing an id before a `04-roadmap.md` is ever accepted — this function only ever sees an already-gated artifact. One call:

1. Load the sidecar once: `roadmap_root = roadmap_dir(plans_dir, slug)`; `state = load_seed_state(seed_state_path(roadmap_root))`. Let `RoadmapSeedStateError` propagate uncaught — a corrupt sidecar is a roadmap-level failure, not a per-plan classification, and this leaf has no `RoadmapError` of its own to convert it to; callers in `roadmap.py` already have that conversion (`_load_roadmap_seed_state`) and can wrap this call the same way.
2. Compute the duplicate set once: `find_duplicate_draft_seed_basenames(artifact.plans)`, folded into a `{row_id: violation.message}` mapping. Architecture is explicit that `duplicate` is "a plan-row property, checked before any file read" — computing it once up front, not per plan, is what makes that true in the implementation too.
3. For each `plan` in `artifact.plans`, apply the precedence order as a sequence of early returns (first match wins, matching `DRAFT_SEED_STATE_PRECEDENCE`):
   - **`duplicate`** — `plan.id` is a key in the duplicate mapping from step 2.
   - **`path-escaping`** — only reachable when a sidecar `entry` exists for `plan.id` (`state["seeds"].get(plan.id)`): call `_validate_draft_seed_path(entry["draft_seed_path"])` (imported from `roadmap_artifacts`, per Input) and catch `RoadmapArtifactError`. This checks the *sidecar's* stored path, not `plan.draft_seed_path` — an accepted roadmap's plan-row paths are already gated at parse time and can never carry an escaping value, so the sidecar entry (unvalidated JSON a hand-editor can corrupt) is the only place this state is reachable at runtime, exactly as Architecture states.
   - **`missing`** — resolve the file location from **`plan.draft_seed_path`**, not the sidecar entry's stored path: `source = resolve_draft_seed_path(plans_dir, slug, plan.draft_seed_path)`. The plan row is authoritative for *where the file is*, per Architecture ("the plan row's own `draft_seed_path` is authoritative for the live file/digest check whenever it disagrees with the sidecar entry's stored path"). `missing` fires when `not source.is_file()`, independent of whether `entry` exists at all.
   - **`digest-mismatched`** — check the two sidecar-only conditions *before* attempting a read: when `entry is None` or `entry.get("digest") is None`, classify `digest-mismatched` immediately — there is no known-good digest to trust either way, and Architecture states this rule ("the same rule as an entry recording a null digest") independent of whether the file is even readable, so it must not wait on a read that isn't needed to decide it. Only when `entry` exists and carries a non-`None` digest does this bullet read the file: `text = source.read_text(...)`. An `OSError`/`UnicodeDecodeError` here, despite `is_file()` having just passed, cannot itself distinguish `stale` from `malformed` — check the sidecar entry's `status`: when `entry["status"] == "invalidated"`, classify `stale` (the same precedence `stale` holds over `malformed` when the read succeeds — an invalidated entry never needs content validation to explain why it needs regenerating); otherwise the read failure falls through to `malformed`, with the read error as `detail` — Architecture's "genuine unexpected corruption" case, not an eighth state. On a *successful* read, compute `live_digest = digest_text(text)` and classify `digest-mismatched` when `entry["digest"] != live_digest`; otherwise fall through to the next bullet.
   - **`stale`** — digest matched; `entry["status"] == "invalidated"`. Checked before `malformed` on purpose — see the next bullet.
   - **`malformed`** — digest matched, status is not `"invalidated"`; call `validate_draft_seed_content(text, plan=plan)` and classify `malformed` on any non-empty violation list, with the joined violation messages as `detail`. Architecture is explicit about why `stale` must be checked first: `validate_draft_seed_content` validates `roadmap_components` against the plan row's *current* `component_ids`, which a revision can change at the same moment it invalidates the entry — checking content before staleness would misreport a revision-driven change as corruption.

   **This ordering's correctness depends on step 9's new invalidation trigger, which does not exist while this step lands (step 3 depends only on step 1, well before step 9 in the plan's order).** Today, an ordinary no-feedback stage-4 replace calls `_mark_roadmap_seeds_current`, not `_invalidate_roadmap_seeds`, so a plan whose `component_ids` changed on such a revision keeps its sidecar `status` at `"current"` — this classifier correctly reaches `malformed` for it in that window, exactly the misclassification Architecture's ordering exists to prevent, because nothing has actually set `status="invalidated"` yet for the ordering to catch. This is a real but narrow, self-resolving window: it closes the moment step 9 lands and starts invalidating on every stage-4 replace, not something this step can close on its own by reordering checks that all correctly read a sidecar step 9 hasn't started writing to yet. Every consumer of `classify_draft_seeds` — this module, and steps 5, 6, 7, 8, and 10 — inherits the same window; each names it in its own detail file rather than assuming it away.
   - **`current`** — every earlier check passed.
4. Return the `{plan_id: DraftSeedClassification}` mapping built from step 3.

**Constraint — this function never writes.** No call to `write_seed_state`, `atomic_write_text`, or anything under `plan-seeds/`. Every classification is recomputed from disk and the sidecar on every call; nothing is cached or stored back as a new sidecar field. This is the plan's own "computed fresh each run... never stored as a new sidecar `status` value" rule, and it is also what "Out of scope — auto-promoting drafts... treating draft materialization as user approval" requires structurally, not just by convention (see Applicable guardrails).

### Splitting `invalidated_seed_continuation`'s resolver

In `plan_tool/roadmap_seed_state.py`, extract the "find which tracked entry this source belongs to" half of `invalidated_seed_continuation` into a new function that does not check status:

- A new frozen type, e.g. `TrackedSeedLocation(plan_id: str, roadmap_slug: str, state_path: Path)` — same shape as today's `SeedContinuation`, but its meaning is "this source is tracked", not "this source needs a stale-use confirmation". Keep `SeedContinuation` as it is; its docstring ("An invalidated roadmap seed that `create` must confirm explicitly") stays accurate once it is only ever constructed for the `stale` case.
- A new function, e.g. `locate_tracked_seed(source: Path, *, repo_root: Path) -> Optional[TrackedSeedLocation]`. Move `invalidated_seed_continuation`'s current body into it verbatim, deleting only the two `status == "invalidated"` checks (and the state lookups that exist solely to perform them) — both branches (marker-based and structural) already resolve `plan_id`/`roadmap_slug`/`state_path` before checking status today, so this is a subtraction, not a rewrite.
- Rewrite `invalidated_seed_continuation` as a thin wrapper: call `locate_tracked_seed`; if it returns `None`, return `None`; otherwise load the sidecar at `location.state_path`, look up `location.plan_id`, and return a `SeedContinuation` built from `location`'s fields only when `entry["status"] == "invalidated"`.

**Constraint — behavior-preserving.** Every existing `invalidated_seed_continuation` caller and test must see identical return values for identical inputs; `tests/test_roadmap_seed_state.py`'s existing four cases stay green unmodified as the evidence, the same way step 1 kept the gate-extraction tests unmodified as its own extraction's evidence.

### Routing `create --from-existing` through the classifier

In `plan_tool/cli/authoring.py`, `_confirm_invalidated_roadmap_seed` (around `cmd_create`'s `--from-existing` handling) needs to go from "is this source's tracked entry `invalidated`" to "what does this source's plan classify as, and is it `current`". The pieces:

1. Call `locate_tracked_seed(source_path, repo_root=repo_root)`. `None` means an untracked file — return `True` immediately, exactly as today (an ordinary, non-roadmap-derived seed is never confirmed on).
2. Derive `plans_dir` from the resolved location rather than re-resolving it from `args`/`--plans-dir`: `seed_state_path(roadmap_dir(plans_dir, slug))` is `<plans_dir>/roadmaps/<slug>/seed-state.json`, so `location.state_path.parent.parent.parent` is exactly the `plans_dir` this seed was materialized under — correct even under a custom `--plans-dir`, and it sidesteps a real ordering problem: `_confirm_invalidated_roadmap_seed` runs before `cmd_create` resolves its own `plans_dir` for the *new* plan being authored (that happens much later, after slug and repo-root resolution), and the two need not be the same value in every configuration.
3. Load `04-roadmap.md`: `load_plans_artifact(plans_path(plans_dir, location.roadmap_slug))`. Catch `RoadmapArtifactError` — a roadmap that has since been deleted or corrupted since the seed was drafted — and fail the same conservative way the function already does for a corrupt sidecar (`except RoadmapSeedStateError`): report the error and require confirmation rather than silently proceeding.
4. Call `classify_draft_seeds(artifact, plans_dir=plans_dir, slug=location.roadmap_slug)` and look up `location.plan_id`. Treat a missing key the same conservative way — a plan id a roadmap revision has since dropped is not evidence the draft is fine.
5. `state == DRAFT_SEED_STATE_CURRENT` returns `True` with no prompt, same as today's "no continuation found" path. Every other state confirms, using the same `yes`/non-tty/interactive-prompt structure the function already has.

**Constraint — message text.** For the `stale` state, keep today's confirmation wording ("is invalidated by applied feedback") unchanged — it is still correct for the cases this function already reached, and the plan's step 9 is the one that corrects its *accuracy* once invalidation stops being feedback-exclusive (see Deferred). Write new, distinct wording for the five states this function could never reach before (`missing`, `malformed`, `path-escaping`, `duplicate`, `digest-mismatched`) — each should name the classification plainly (e.g. "draft seed for plan '{plan_id}' in roadmap '{roadmap_slug}' classifies as '{state}'") plus `classification.detail` when it is non-empty, rather than reusing feedback-specific language that would misdescribe why these five need confirmation.

New imports this requires in `plan_tool/cli/authoring.py`: `load_plans_artifact`, `plans_path`, `roadmap_dir`, `RoadmapArtifactError` from `plan_tool.roadmap_artifacts`; `classify_draft_seeds` and the state constants from `plan_tool.roadmap_seed_manifest`; `locate_tracked_seed` added to the existing `plan_tool.roadmap_seed_state` import block alongside `RoadmapSeedStateError`/`invalidated_seed_continuation` (the latter may become unused here once the routing lands — check and drop it from the import if so, rather than leaving an unused import).

### Documenting the module

In `ROADMAP_FORMAT.md`, add a new subsection at the end of "## Draft seeds — side output under the roadmap slug" (after the existing "Feedback invalidation and explicit refresh" content) naming the seven states, the precedence order from Architecture, and this module's leaf position — "`plan_tool/roadmap_seed_manifest.py`, a leaf below `roadmap.py` and `roadmap_view.py` like `roadmap_gates.py`, consumed by `cli/authoring.py`" (steps 5 through 10 add `roadmap.py`/`roadmap_view.py` themselves as consumers later; word this so it stays true as those steps land — a bare "consumed by `cli/authoring.py`" plus "designed to be called from `roadmap.py`/`roadmap_view.py`" avoids overclaiming what step 3 alone ships). Follow the doc's established banner convention (`PLAN_FORMAT.md`/`DETAIL_FORMAT.md`/`JIRA_FORMAT.md`/`ROADMAP_FORMAT.md` all open with a source-of-truth blockquote naming the enforcing code) by citing `plan_tool/roadmap_seed_manifest.py` as the enforcing module for this new subsection's claims, the same way the file's own opening banner already does for shape/relations.

In `CLAUDE.md`, edit the "Roadmap's five modules" bullet under "## Architecture": bump the count to six, and add `roadmap_seed_manifest.py`'s edges — it imports `roadmap_artifacts.py` and `roadmap_gates.py` (like `roadmap_gates.py` imports only `roadmap_artifacts.py`) plus `roadmap_seed_state.py`, and sits below `roadmap.py`/`roadmap_view.py` without being imported by either yet. Keep the edit to a clause or two, per this file's own "Code comments" rule — depth belongs in `ROADMAP_FORMAT.md`, not here.

## Tests

### Tests for this step

**`tests/test_roadmap_seed_manifest.py` — one roadmap/plan/sidecar fixture set, reused across cases:**

- `test_classify_current_when_digest_matches_and_content_validates` — a plan with a matching digest, `status: current`, and clean provenance classifies `current` with empty `detail`.
- `test_classify_missing_when_no_file_and_no_sidecar_entry` — no file, no entry: `missing`.
- `test_classify_missing_when_sidecar_entry_exists_but_file_is_gone` — entry present, file absent: `missing`.
- `test_classify_digest_mismatched_when_entry_has_null_digest` — file exists, entry's `digest` is `None`: `digest-mismatched`.
- `test_classify_digest_mismatched_when_file_exists_with_no_sidecar_entry` — file exists, no entry at all: `digest-mismatched`.
- `test_classify_digest_mismatched_when_recorded_digest_disagrees_with_live_file` — a hand-edited file whose bytes no longer hash to the recorded digest: `digest-mismatched`.
- `test_classify_digest_mismatched_when_file_is_unreadable_and_no_sidecar_digest_exists` — a file that exists but raises on read/decode, paired separately with (a) no sidecar entry at all and (b) an entry whose `digest` is `None`: both classify `digest-mismatched`, not `malformed` — the sidecar-only check fires without ever attempting the read, so a read failure cannot mask it.
- `test_classify_stale_when_status_invalidated_and_digest_matches` — `status: invalidated`, digest matches: `stale`.
- `test_classify_malformed_when_content_violates_and_not_invalidated` — digest matches, `status: current`, but `validate_draft_seed_content` returns violations (e.g. a `roadmap_components` entry absent from the plan row): `malformed`, `detail` carries the violation message(s).
- `test_classify_malformed_when_file_exists_but_is_unreadable` — a file that exists but raises on read/decode, with a sidecar entry whose `status` is `current` (not `invalidated`) and a non-`None` `digest`: `malformed`, not a raised exception.
- `test_classify_stale_when_file_is_unreadable_and_entry_is_invalidated` — a file that exists but raises on read/decode, with a sidecar entry whose `status` is `invalidated` and a non-`None` `digest`: `stale`, not `malformed` — the same read failure must not short-circuit past the `invalidated` check the way an unconditional read-failure-means-malformed rule would, matching Architecture's stale-before-malformed precedence via a different trigger than the content-validation case below.
- `test_stale_takes_precedence_over_malformed_when_both_would_fire` — digest matches, `status: invalidated`, *and* content that would fail `validate_draft_seed_content` (simulating a revision that changed `component_ids` the same moment it invalidated the entry): classifies `stale`, not `malformed` — the ordering acceptance test for Architecture's explicit "stale checked before malformed" rule.
- `test_classify_path_escaping_when_sidecar_draft_seed_path_is_unsafe` — sidecar entry's `draft_seed_path` contains `..` (hand-edited JSON): `path-escaping`, even though the plan row's own `draft_seed_path` is fine.
- `test_path_escaping_takes_precedence_over_missing` — an escaping sidecar path *and* no file at the plan row's declared location: classifies `path-escaping`, not `missing`.
- `test_classify_duplicate_when_two_plan_rows_share_a_basename` — two `PlanRow`s whose `draft_seed_path` share a basename both classify `duplicate`, `detail` naming the sibling.
- `test_duplicate_takes_precedence_over_every_other_state` — a colliding plan row that is also missing its file: classifies `duplicate`, not `missing` — pins that duplicate is checked "before any file read" per Architecture.
- `test_classify_accepts_legacy_seeds_prefix_paths` — a plan row and sidecar entry both under the legacy `seeds/` prefix (step 1's widened `_validate_draft_seed_path`) classify identically to an equivalent `plan-seed-drafts/` fixture — no `path-escaping` false positive on a pre-rename roadmap.
- `test_classify_draft_seeds_returns_one_entry_per_plan_row` — a three-plan roadmap returns exactly three keys, each keyed by plan id.
- `test_classify_draft_seeds_never_writes_the_sidecar_or_a_draft_file` — run classification, assert `seed-state.json`'s mtime/bytes and every draft file's bytes are unchanged afterward.
- `test_precedence_constant_matches_the_documented_order` — `DRAFT_SEED_STATE_PRECEDENCE` equals the seven-tuple Architecture states, in order — a one-line guard against the constant and the doc silently drifting apart.

**`tests/test_roadmap_seed_state.py` — the resolver split:**

- `tests/test_roadmap_seed_state.py::test_direct_draft_and_its_archive_require_stale_seed_confirmation`, `test_promoted_seed_marker_survives_its_archive_move`, `test_create_requires_an_explicit_assent_for_an_invalidated_seed` — unchanged, the behavior-preserving evidence for `invalidated_seed_continuation`.
- `test_locate_tracked_seed_finds_a_direct_draft_regardless_of_status` — a direct draft with `status: current` (not invalidated) still resolves via `locate_tracked_seed`, unlike `invalidated_seed_continuation`, which would return `None` for it.
- `test_locate_tracked_seed_finds_an_archived_copy` — mirrors the existing archive case for `invalidated_seed_continuation`, but for a `current`-status entry.
- `test_locate_tracked_seed_finds_a_promoted_copy_via_its_marker_regardless_of_status` — mirrors the promoted-copy case, `current` status.
- `test_locate_tracked_seed_returns_none_for_an_untracked_file` — an ordinary, non-roadmap file: `None`.
- `test_invalidated_seed_continuation_still_returns_none_for_a_current_entry` — pins that the status filter survives the refactor: a `locate_tracked_seed`-resolvable, `status: current` source still yields `None` from `invalidated_seed_continuation`.

**`tests/cli/test_authoring_cmds.py` — the routed confirmation:**

- `test_confirm_unrelated_source_needs_no_confirmation` — an untracked file: `True`, no prompt (pins the unchanged fast path).
- `test_confirm_current_classification_needs_no_confirmation` — a tracked, `current`-classifying source: `True`, no prompt.
- `test_confirm_stale_classification_prompts_with_existing_wording` — a `stale` source still shows the "invalidated by applied feedback" text and honors `-y`/non-tty exactly as today.
- `test_confirm_digest_mismatched_classification_prompts_naming_the_state` — a hand-edited draft (recorded digest disagrees) prompts, and the message names `digest-mismatched`, not the old feedback-specific wording.
- `test_confirm_malformed_classification_prompts_with_the_violation_detail` — a draft that fails `validate_draft_seed_content` prompts, and the message includes the violation text.
- `test_confirm_duplicate_classification_prompts_naming_the_state` — a source whose plan row collides with a sibling's basename prompts, naming `duplicate`.
- `test_confirm_yes_flag_bypasses_every_non_current_state` — `-y` accepts each of the five new states plus `stale`, matching the existing bypass behavior.
- `test_confirm_non_tty_refuses_every_non_current_state_without_yes` — mirrors the existing non-tty refusal for `stale`, extended to the new states.
- `test_confirm_falls_back_conservatively_on_an_unreadable_roadmap` — `locate_tracked_seed` resolves a location, but `load_plans_artifact` raises `RoadmapArtifactError` (roadmap deleted since the seed was drafted): the function reports the error and returns `False`/requires confirmation rather than proceeding silently.

Every test above is green before this step is considered finished.

## Acceptance criteria

- `plan_tool.roadmap_seed_manifest.classify_draft_seeds(artifact, *, plans_dir, slug)` exists, returns one `DraftSeedClassification` per plan row in `artifact.plans`, keyed by plan id — checkable with `rg -A3 'def classify_draft_seeds' plan_tool/roadmap_seed_manifest.py`.
- The seven state constants and `DRAFT_SEED_STATE_PRECEDENCE` are defined at module scope in `plan_tool/roadmap_seed_manifest.py` and the precedence tuple matches the order stated in the plan's Architecture section.
- `plan_tool/roadmap_seed_manifest.py` imports only `plan_tool.roadmap_artifacts` and `plan_tool.roadmap_gates` (first-party) plus `plan_tool.roadmap_seed_state` — never `plan_tool.roadmap` or `plan_tool.roadmap_view` — checkable with `rg '^from plan_tool\.|^import plan_tool\.' plan_tool/roadmap_seed_manifest.py`.
- A roadmap fixture exercising every one of the seven states classifies each plan correctly, including the two precedence-order cases (`stale` over `malformed`; `duplicate`/`path-escaping` over `missing`).
- Classification never writes: running it against a fixture leaves `seed-state.json` and every draft file byte-for-byte unchanged.
- `plan_tool.roadmap_seed_state.locate_tracked_seed` exists and resolves a tracked seed's `(plan_id, roadmap_slug, state_path)` regardless of the entry's `status`; `invalidated_seed_continuation` is unchanged in behavior for every existing test.
- `plan_tool/cli/authoring.py`'s `_confirm_invalidated_roadmap_seed` prompts (absent `-y`) for a source classifying as any of `missing`, `stale`, `malformed`, `path-escaping`, `duplicate`, or `digest-mismatched`, and returns `True` with no prompt for `current` or an untracked file.
- `ROADMAP_FORMAT.md`'s "## Draft seeds" section documents all seven states, their precedence order, and `plan_tool/roadmap_seed_manifest.py`'s position.
- `CLAUDE.md`'s roadmap-modules bullet names six modules and includes `roadmap_seed_manifest.py`'s edges.
- `uv run pytest tests/test_roadmap_seed_manifest.py tests/test_roadmap_seed_state.py tests/cli/test_authoring_cmds.py -q` is green.

## References

- `ROADMAP_FORMAT.md` — the `draft_seed_path`/`seed-state.json` contract this module classifies against, and the section this step extends with the new state vocabulary.
- `DATA_CONTRACT.md` — `seed-state.json`'s persisted shape; confirms this step reads existing fields only and adds none.

## Applicable guardrails

- **Out of scope — a correctness gate on seed style, length, or model agreement.** `classify_draft_seeds`'s `malformed` state runs step 1's structural/provenance validator only; it adds no judgment about a seed's prose quality, length, or agreement with the roadmap's design rows.
- **Out of scope — auto-promoting drafts, auto-accepting roadmap feedback, or treating draft materialization as user approval.** This module is read-only end to end — see the "never writes" constraint in Implementation and its own test. Routing `_confirm_invalidated_roadmap_seed` through it widens *when a human is asked to confirm*; it does not remove or weaken the confirmation itself.
- **Out of scope — deleting a stale seed to hide it, or writing a replacement without the explicit materialization/refresh action.** Nothing in this step regenerates, deletes, or rewrites a draft; that is step 5's (`--materialize`) and step 4's (`--refresh-seeds`) job.
- **In scope, narrowly — "the extraction necessary to separate stage-4 manifest handling from draft-seed materialization... is in scope."** This module *is* that manifest handling: it reads the existing sidecar and roadmap artifact and answers one question about their relationship. It does not touch stage 4's own write path, `PLANS_GATES`, or the bundle machinery — those stay exactly as they are until step 9.

## Deferred

- **Materializing, refreshing, or otherwise regenerating any classified state.** Steps 4 and 5 — this module only reports; it never fixes what it finds.
- **Promotion refusal wiring in `--apply`.** Step 6 — `_apply_roadmap_seeds`'s existing ad hoc preflight (`source.is_file()`, a bare `parse_draft_seed_provenance` call) is untouched by this step; step 6 replaces it with a call to `classify_draft_seeds`.
- **Routing the roadmap views (`summarize_seed_lifecycle`, `_render_draft_seed`) through this classification.** Steps 7 and 8 — this step ships no change to `plan_tool/roadmap_view.py`.
- **Retiring stage 4's own inline seed generation, its bundle-based gates, and the "invalidated by applied feedback" wording's accuracy.** Step 9 — this step's routed confirmation keeps that exact phrase for the `stale` state (see Implementation); step 9 is the one that corrects it once invalidation stops being feedback-exclusive.
- **Accepting a hand-edited, `digest-mismatched` draft as current.** Step 10's accept action — this module classifies that state but provides no way to clear it; only regeneration (steps 4/5) or the future accept action change a draft's classification.
- **Targeted/incremental revision marking which plan ids actually went stale.** `docs/implementation-plans/plan-seeds/roadmap-incremental-revision.md`, not yet promoted to a plan — this module classifies whatever the sidecar and roadmap currently say; it does not change which plan ids a revision invalidates.
