> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Load a roadmap off disk into LoadedRoadmap, naming what it did not find

## Summary

Adds a `LoadedRoadmap` type and a `load_roadmap` entry point to `plan_tool/roadmap_view.py`, giving the three views their only look at disk. `load_roadmap(plans_dir, slug, *, mode=...)` reads whichever of the four staged artifacts it can, records which ones it could not find versus which it found but could not parse, records whether the roadmap directory exists at all, and builds the roadmap-wide id index step 1 already supplies — degrading to whatever parsed rather than raising. The key decision is that the mode (`current` vs `review`) is a property of this loaded snapshot, not of any renderer: under `current` mode the feedback and removal populations are empty by construction, and under `review` mode they carry every feedback row and removal record the parsed artifacts declare. On green, a partly-authored roadmap — the normal state after `--from-stage` re-entry or an interrupted run — loads into one `LoadedRoadmap` value that names exactly what it found, what it didn't, and what it couldn't read, and no exception reaches the caller for any combination of absent or malformed artifacts.

## Table of Contents

- [Why](#why) — the gap this step closes and why it can't reuse the orchestrator's own loader
- [Input](#input) — step 1's resolver contract and the artifact/error surfaces this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — both edits, no new files
- [Implementation](#implementation) — `LoadedRoadmap`'s shape, the absent/unparseable split, and the mode filter
- [Tests](#tests) — what `tests/test_roadmap_view.py` covers
- [Acceptance criteria](#acceptance-criteria) — observable behavior on green
- [References](#references) — stdlib docs for the pieces this step uses
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences this step's code must respect
- [Deferred](#deferred) — what later steps own instead

## Why

After step 1, `plan_tool/roadmap_view.py` can turn an id into a label once handed already-parsed artifacts, but nothing in the module reads a roadmap off disk, and nothing anywhere records which of the four staged files a caller actually found. `plan_tool.roadmap` reads artifacts too, through `_load_stage_artifact` and `_load_predecessor` — but those are orchestrator-private, built for a stage run's job, and raise on almost every failure: a stage cannot proceed past a broken predecessor, so it stops there. A read-only view has the opposite job. An operator re-entering after `--from-stage`, or reading a roadmap with an open review conversation, is the *normal* case, so a missing `04-roadmap.md` or a hand-broken `02-constraints.md` must degrade to whatever did parse, never abort. Steps 3, 4, and 5 each need the same four facts — which artifacts loaded, which didn't and why, whether the directory exists at all, and how much of the review channel is in scope — and without one place to build that state, each view would reopen every file itself and reinvent absent/malformed handling three times, the exact risk the plan's Architecture names for the resolver and now extends to disk state.

The one-way import chain (`roadmap_artifacts` → `roadmap_gates` → `roadmap_view`) means this step cannot import `plan_tool.roadmap` to reuse `_load_predecessor`'s absent-vs-malformed split even though the split is exactly right — `path.exists()` first, `RoadmapArtifactError` after. This step mirrors that shape rather than importing it, the same choice step 1 made for `_check_predecessor_review_rows`'s resolution formula.

## Input

This step builds directly on step 1's resolver and on the artifact contract both steps read:

- **Step 1 produces** `build_design_row_index(*, domain=None, constraints=None, components=None, plans=None)` and `build_removal_index(*, domain=None, constraints=None, components=None, plans=None)`, both in `plan_tool/roadmap_view.py`, both with every parameter optional for exactly this reason — a partially loaded roadmap. This step calls them with whichever artifacts parsed and leaves the rest at their default; it does not re-derive their id-collection logic.
- **`plan_tool/roadmap_artifacts.py`'s load surface** — `load_domain_artifact`, `load_constraints_artifact`, `load_components_artifact`, `load_plans_artifact`, each `Path -> Artifact`, each raising `RoadmapArtifactError` (never a bare `OSError`) on any read or shape failure, with `.path` set to the file that failed. The path helpers `domain_path`, `constraints_path`, `components_path`, `plans_path`, and `roadmap_dir` (which raises `ValueError` for a slug that isn't a single safe path component) are pure and touch no filesystem themselves.
- **What this step cannot inherit by import**: `plan_tool/roadmap.py:_load_predecessor`'s `path.exists()`-before-`RoadmapArtifactError` split, and `plan_tool/roadmap.py:_check_predecessor_review_rows`'s per-artifact feedback-id-uniqueness and `design_row_ids(artifact) | {removals}` resolution formula. Both live in orchestrator-private code this leaf must not import (see Applicable guardrails); this step reproduces the *shape* of the first and relies on step 1 for the second, never the code itself.
- **Its limit**: `_check_predecessor_review_rows` enforces feedback-id uniqueness only *within* the one artifact it is called on — there is no roadmap-wide feedback-id uniqueness gate, unlike `check_duplicate_row_ids`'s roadmap-wide scope for design rows. A hand-edited roadmap can therefore carry the same feedback id in two different artifacts with nothing on disk having rejected it; this step's own index-building has to not lose one of the two (see Implementation).

## Files (creates vs edits)

- **New files:** none. Step 1 creates both files this step touches.
- **Existing files (edits only):**
  - `plan_tool/roadmap_view.py` — adds `LoadedRoadmap`, the `load_roadmap` entry point, the mode constants, and whatever private per-artifact loading helper the implementation needs.
  - `tests/test_roadmap_view.py` — adds the test classes/functions in § Tests, and edits the one inherited test named below.

## Implementation

**`LoadedRoadmap` is the type the plan names**, and it is the type steps 3, 4, and 5 read instead of touching disk. A reasonable shape, as a frozen dataclass:

- `slug: str` and `mode: str` — carried so a renderer can print its own header ("roadmap `<slug>`, mode: `<mode>`") without threading them separately; not load-bearing for any check below, just a convenience.
- `directory_exists: bool` — set once, from `roadmap_dir(plans_dir, slug).exists()`, before any per-artifact loading. This is the field the plan's Architecture calls out by name as step 2's to detect and step 6's to map to an exit code — set it and stop; do not decide what it means for the process's return code here.
- `domain: Optional[DomainArtifact]`, `constraints: Optional[ConstraintsArtifact]`, `components: Optional[ComponentsArtifact]`, `plans: Optional[PlansArtifact]` — all four optional, unlike `ArtifactEnvelope.domain`, which is mandatory. This is the type the plan's Architecture points at directly under "It is deliberately not called an envelope."
- `absent: tuple[str, ...]` — the filename constants (`DOMAIN_FILENAME`, `CONSTRAINTS_FILENAME`, `COMPONENTS_FILENAME`, `PLANS_FILENAME`) for artifacts whose path did not exist, in stage order.
- `unparseable: tuple[..., ...]` — the filename plus the `RoadmapArtifactError` message for artifacts whose path existed but failed to load, in stage order. One way: a small frozen record (e.g. `UnparseableArtifact(filename: str, reason: str)`) rather than a bare tuple, so a caller reads `.filename` / `.reason` instead of unpacking a pair.
- `design_row_index` — the return value of `build_design_row_index(...)`, called with whichever of the four artifacts parsed. Built once, mode-independent: every renderer resolves design-row ids the same way regardless of `mode`.
- `removal_index` and `feedback_index` — see the mode filter below.

**Loading one artifact never raises past this function**, mirroring `_load_predecessor`'s existence check rather than importing it:

```
path = domain_path(plans_dir, slug)      # or constraints_path / components_path / plans_path
if not path.exists():
    # record DOMAIN_FILENAME in absent; the field stays None
else:
    try:
        domain = load_domain_artifact(path)
    except RoadmapArtifactError as exc:
        # record (DOMAIN_FILENAME, str(exc)) in unparseable; the field stays None
```

Repeat per artifact. This is the one place `path.exists()` needs to be checked *before* calling the loader rather than after: `load_domain_artifact` wraps a `FileNotFoundError` and a genuine parse failure into the same `RoadmapArtifactError`, so catching the exception alone cannot distinguish "not found" from "found but broken" — the pre-check is what makes `absent` and `unparseable` two different lists instead of one. `directory_exists=False` does not short-circuit this loop: `Path.exists()` on a child of a directory that doesn't exist already returns `False`, so the same per-artifact logic produces the correct all-four-absent result whether the directory is merely empty or genuinely missing, with no separate branch. The two states differ only in the `directory_exists` field — which is exactly the distinction the plan's Architecture draws between a pre-flight failure and a real (if empty) render.

**The only exception this step lets through is `ValueError` from an invalid slug**, raised by `roadmap_dir` (via `_validate_slug`) before any path is even built. That is existing, unrelated validation this step must not swallow or duplicate.

**The mode filter is this step's central duty**, per the plan's Architecture ("The mode is a property of `LoadedRoadmap`, not of each renderer"):

- Under `mode="current"`, `removal_index` and `feedback_index` are both empty — bind them to an empty mapping without even calling a builder. This is what makes "current mode must resolve no removal at all" true by construction, the same guarantee step 1's Implementation states for its own resolve functions.
- Under `mode="review"`, `removal_index` is `build_removal_index(...)` over whichever artifacts parsed — step 1's function, reused as-is (`Mapping[str, tuple[RemovalRecord, ...]]`, plural per key for the same reason `feedback_index` is: a colliding `removed_id` must stay reachable, not overwritten).
- `feedback_index` has no step-1 precedent; this step introduces it. Build it the same way — one pass in stage order, each artifact's `.feedback` tuple in source order — but shape it as `Mapping[str, tuple[FeedbackRow, ...]]`, plural per key, not a single row. This matters because of the Input section's limit: feedback-id uniqueness is enforced only within one artifact, so two different artifacts can legitimately (if messily) declare a feedback row under the same id, and collapsing to one value per key would silently drop one of them — exactly the loss step 1's design-row index avoids by keeping multiple matches under one key. This step does not decide what a collision *means* (that is step 3's, deferred below); it only refuses to lose data.

**Constraints and gotchas that are not free to vary:**

- `load_roadmap` must never raise for any combination of absent, unparseable, or entirely-missing-directory input — only an invalid slug's `ValueError` passes through. A traceback from this function is the exact failure mode the plan's Architecture calls out as designed out.
- `design_row_index` is built the same way regardless of `mode`; only `removal_index` and `feedback_index` are mode-gated. Do not thread `mode` into `build_design_row_index` or otherwise make it mode-aware.
- Every read this module performs goes through `Path.exists()` and the four `load_*_artifact` functions — never a direct `path.read_text()` or `open()` call in `roadmap_view.py` itself. All four loaders already bind the failing path to their `RoadmapArtifactError`, so there is nothing this step needs to read itself.
- `absent`, `unparseable`, `design_row_index`, `removal_index`, and `feedback_index` are all populated in stage order (domain → constraints → components → plans) and, within an artifact, in the artifact's own declared row order — the same ordering rule step 1 already applies, and the one the plan's Architecture states is what makes "one deterministic rendering" true later.

**One inherited test needs an edit, not just a new sibling.** Step 1 shipped `test_module_touches_no_filesystem_and_no_subprocess`, whose docstring says "disk reads are step 2's job." After this step, the module *does* touch the filesystem — through `Path.exists()` and the four loaders — so the test's name and docstring now overclaim. The underlying grep assertions (no `open(`, `subprocess`, or `invoker` token, and no direct `read_text` call) still hold and are still worth keeping, because they are what forces every read through the shipped artifact loaders instead of a hand-rolled one — but the test needs renaming and its docstring correcting to say so, rather than being left describing a state this step ends.

## Tests

`tests/test_roadmap_view.py`, extending step 1's suite. Unlike step 1's fixtures (built as row dataclasses only, no disk), this step's fixtures write real files: build a `DomainArtifact` / `ConstraintsArtifact` / `ComponentsArtifact` / `PlansArtifact` directly, render it with `render_domain_artifact` / `render_constraints_artifact` / `render_components_artifact` / `render_plans_artifact`, and write the text to `domain_path(tmp_path, slug)` etc. — mirroring `tests/test_roadmap.py`'s `_Env.write_domain` / `write_constraints` / `write_components` / `write_plans` pattern rather than hand-typing YAML.

### Tests for this step

- `test_load_roadmap_parses_all_four_when_present` — a roadmap directory holding all four valid artifacts loads with `domain`/`constraints`/`components`/`plans` all populated and both `absent` and `unparseable` empty.
- `test_load_roadmap_names_absent_artifacts_in_stage_order` — a domain-only roadmap loads with `constraints`/`components`/`plans` filenames in `absent`, in stage order, and those three fields `None`.
- `test_load_roadmap_names_unparseable_artifact_distinctly_from_absent` — a present-but-malformed `02-constraints.md` is reported in `unparseable`, not `absent`, while the other three still parse and `load_roadmap` does not raise.
- `test_missing_roadmap_directory_is_distinguishable_from_all_four_absent` — a slug whose roadmap directory does not exist sets `directory_exists=False`; the same slug with an existing but empty directory sets `directory_exists=True` — both name all four filenames in `absent`, differing only in `directory_exists`.
- `test_load_roadmap_propagates_invalid_slug` — a slug containing a path separator raises `ValueError`, unchanged from `roadmap_dir`'s existing guard.
- `test_design_row_index_matches_design_row_ids_for_every_parsed_artifact` (parametrized over which subset of the four parsed) — `loaded.design_row_index`'s id set equals the union of `roadmap_gates.design_row_ids(artifact)` over only the artifacts that parsed, imported and compared directly.
- `test_design_row_index_is_mode_independent` — the same fixture loaded under `mode="current"` and `mode="review"` produces an identical `design_row_index`.
- `test_current_mode_exposes_no_feedback_and_no_removal` — a fixture whose artifacts carry feedback rows and removal records loads under `mode="current"` with `feedback_index` and `removal_index` both empty.
- `test_review_mode_exposes_feedback_and_removal` — the same fixture loaded under `mode="review"` has `feedback_index` and `removal_index` populated with every feedback row and removal record the parsed artifacts declare.
- `test_feedback_index_orders_stage_then_source` — feedback rows from two different artifacts resolve in domain-before-constraints-before-components-before-plans order, each artifact's own rows in source order.
- `test_feedback_index_preserves_both_rows_on_a_cross_artifact_id_collision` — two different artifacts each declare a feedback row sharing one id; both rows are reachable under that key in `feedback_index` rather than one overwriting the other.
- `test_removal_index_matches_build_removal_index` — under `mode="review"`, `loaded.removal_index` equals calling step 1's `build_removal_index` directly on the same parsed artifacts.
- `test_module_reads_only_through_the_artifact_loaders` — replaces step 1's `test_module_touches_no_filesystem_and_no_subprocess`: asserts no `open(`, `subprocess`, or `invoker` token and no direct `read_text` call in the module's source, with a corrected docstring stating the module now reads disk state exclusively through `Path.exists()` and the four `load_*_artifact` functions.
- `test_module_imports_only_the_artifact_and_gates_leaves` — unchanged from step 1; stays green because this step adds no new first-party import.

Every test above is green before this step is considered finished.

## Acceptance criteria

- `LoadedRoadmap` is a frozen dataclass carrying `directory_exists`, the four optional parsed artifacts, `absent`, `unparseable`, `design_row_index`, `removal_index`, and `feedback_index`.
- `load_roadmap` returns a `LoadedRoadmap` for every combination of present, absent, and malformed artifacts without raising, propagating only `ValueError` from an invalid slug.
- A roadmap directory that does not exist sets `directory_exists=False`; one that exists but holds none of the four sets `directory_exists=True` — both name all four filenames in `absent`, and the two states differ only in `directory_exists`.
- Each artifact missing from disk is named by its filename constant in `absent`; each artifact present but failing to parse is named in `unparseable` with its `RoadmapArtifactError` message, distinctly from `absent`; every other artifact still populates its field.
- `design_row_index`'s id set equals the union of `roadmap_gates.design_row_ids(artifact)` over the artifacts that parsed, and is identical whether `mode` is `"current"` or `"review"`.
- Under `mode="current"`, `feedback_index` and `removal_index` are both empty; under `mode="review"`, both contain every feedback row and removal record from the artifacts that parsed, in stage-then-source order, and a feedback id declared by two different artifacts leaves both rows reachable rather than dropping one.
- The module's only first-party imports remain `plan_tool.roadmap_artifacts` and `plan_tool.roadmap_gates`; no raw `open(`, `subprocess`, or `invoker` token appears in the module's source, and no direct `read_text` call exists outside the shipped `load_*_artifact` functions it delegates to.
- `plan-tool validate` and the full existing roadmap suite (`tests/test_roadmap_artifacts.py`, `tests/test_roadmap_gates.py`, `tests/test_roadmap.py`, `tests/test_roadmap_format.py`) stay green.

## References

- [pathlib — Object-oriented filesystem paths (Python 3 docs)](https://docs.python.org/3/library/pathlib.html) — `Path.exists()` is what separates an absent artifact from a present-but-unparseable one, ahead of calling the loader.
- [dataclasses — Data Classes (Python 3 docs)](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` for `LoadedRoadmap` and the small unparseable-artifact record, matching every other roadmap type's shape.
- [collections — Container datatypes (Python 3 docs)](https://docs.python.org/3/library/collections.html) — ordered-mapping semantics for building `feedback_index` in one stage-then-source pass, the same guarantee step 1's `defaultdict(list)` gives the design-row index.

## Applicable guardrails

- **The one-way import chain (plan's Architecture, "Placement preserves the one-way chain").** This step's only first-party imports stay `plan_tool.roadmap_artifacts` and `plan_tool.roadmap_gates`. It reproduces `_load_predecessor`'s absent-vs-malformed shape rather than importing `plan_tool.roadmap`, exactly as step 1 reproduced `_check_predecessor_review_rows`'s resolution formula rather than importing it.
- **The gates import stays narrow (plan's Architecture, "Why the gates import").** This step adds no new `roadmap_gates` symbol to the module's imports; it reaches `design_row_ids` only indirectly, through step 1's `build_design_row_index`.
- **Not called an envelope (plan's Architecture, "It is deliberately not called an envelope").** `LoadedRoadmap.domain` is `Optional`, unlike `ArtifactEnvelope.domain`; the type must keep tolerating an absent `01-domain.md`.
- **Not a second enforcement channel (plan's Out of scope).** `absent` and `unparseable` are plain data fields, never a `Violation` or a finding; `load_roadmap` never raises or picks an exit code for missing or malformed content — that mapping belongs to a later step.
- **The missing-directory signal and its exit-code mapping are two different steps' jobs (plan's Architecture, "The missing-directory signal lives in `LoadedRoadmap`...").** This step's only obligation is to set `directory_exists` correctly; it must not itself refuse to load, print an error, or otherwise act as if the missing-directory case were already an rc-2 failure.
- **The mode filter belongs to `LoadedRoadmap`, not to any renderer (plan's Architecture, "The mode is a property of `LoadedRoadmap`...").** This step is where that filter is implemented. `removal_index` and `feedback_index` being empty under `current` mode is what later steps rely on instead of re-checking `mode` themselves against the raw artifacts' `.feedback` / `.removals` tuples.

## Deferred

- **Reading draft seeds or calling `parse_draft_seed_provenance`** — step 4's job; `load_roadmap` reads only the four staged artifacts.
- **Rendering the absent/unparseable notice as printed text, and how often it prints per invocation** — steps 3–6; this step supplies the structured `absent` / `unparseable` fields, not their wording or placement.
- **The reverse index, the traceability walk, and the decision ledger's own logic** — steps 3, 4, and 5, all consuming `LoadedRoadmap` without touching disk themselves.
- **Whether a cross-artifact feedback-id collision should render as an "ambiguous" outcome the way a colliding design-row id does** — step 3's reverse index decides that; this step only keeps every colliding feedback row reachable in `feedback_index` instead of dropping one.
- **Mapping `directory_exists=False`, or any other loaded state, to a process exit code** — step 6 owns the exit-code mapping.
- **CLI wiring (`--view`, `--mode`, `--id`) and the doc sweep** — steps 6 and 7.
