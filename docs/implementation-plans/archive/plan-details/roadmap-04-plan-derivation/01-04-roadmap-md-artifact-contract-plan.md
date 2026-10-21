> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add 04-roadmap.md artifact contract with plan rows, disposition vocabulary, and draft-seed paths

## Summary

Extend `plan_tool/roadmap_artifacts.py` with the fourth roadmap artifact: `04-roadmap.md`. The module gains path helpers, closed plan-disposition vocabulary, typed row dataclasses (plans, ordering, inter-plan assumptions, reused decisions/feedback/removals), a `plans_design_rows` enumerator, draft-seed path resolution under the roadmap slug directory, and pinned draft-seed provenance key names. Ship `parse_plans_artifact` / `render_plans_artifact` / `load_plans_artifact` in the same step with round-trip tests. Relation checks (component coverage, ordering totality, `create` slug shape, seed bundle alignment) stay in step 3 gates; parsing accepts dangling refs and duplicate ids like stages 1–3. On green, every new test in `tests/test_roadmap_artifacts.py` passes and the module remains a stdlib-plus-YAML leaf.

## Table of Contents

- [Summary](#summary) — what lands and where
- [Table of Contents](#table-of-contents) — section index
- [Why](#why) — gap this step closes
- [Input](#input) — patterns reused from earlier artifacts and `create`
- [Files (creates vs edits)](#files-creates-vs-edits) — touched paths only
- [Implementation](#implementation) — contract shape, helpers, parse/render rules
- [Tests](#tests) — new cases and green gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — external docs for YAML, dataclasses, paths, enums
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — explicitly later steps

## Why

Stages 1–3 already parse and render `01-domain.md`, `02-constraints.md`, and `03-components.md` from one leaf module, but there is no typed contract for `04-roadmap.md` — no filename constant, no plan-row shape, no ordering or assumptions inventory, no draft-seed path helpers, and no shared provenance key names for draft seeds. Step 2 cannot widen `plan_tool/roadmap_gates.py:_rows_of` / `design_row_ids`, step 3 cannot run relation gates, and step 6 cannot write disk until this shape exists and round-trips through the same parse/render pair the orchestrator will persist.

## Input

- **Reuse row parsers, do not fork them.** `DecisionRow`, `FeedbackRow`, `RemovalRecord`, and their private parsers (`_parse_decision_rows`, `_parse_feedback_rows`, `_parse_removal_records`) already live in `plan_tool/roadmap_artifacts.py`. The plans artifact uses the same review collections and decision shape as stages 1–3.
- **Reuse render helpers.** `_decision_mapping`, `_feedback_mapping`, `_removal_mapping`, `_review_mappings`, and `_render` are the rendering path; do not invent a second YAML dumper.
- **Plan id slug shape.** Plan row `id` values must eventually satisfy `plan_tool/create.py:SLUG_RE` (`^[a-z0-9][a-z0-9-]*[a-z0-9]$`). This leaf cannot import `create.py`; mirror the pattern locally as `PLAN_ID_SLUG_RE` and pin equality in a test that imports `create.SLUG_RE.pattern`. **Shape parsing does not reject a bad slug** — step 3's gate owns that relation check.
- **Draft seed provenance keys.** Gate 3 (step 3) scans draft-seed frontmatter for `roadmap_components` (required list) and optional `cross_cutting: true`. Mint the wire-key constants here; full seed-body validation stays out of scope.

## Files (creates vs edits)

- **New files:** none
- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — add fourth-artifact paths, vocabularies, row types, `PlansArtifact`, `plans_design_rows`, draft-seed provenance constants, minimal draft-seed frontmatter parser, parse/render/load API; update module docstring to name `04-roadmap.md`
  - `tests/test_roadmap_artifacts.py` — import new public symbols; add a **Plans artifact** test section mirroring the Components artifact block (conforming fixture, round-trip, shape errors, relation non-checks, design-row enumeration, leaf discipline unchanged)

## Implementation

### Paths and filename constants

Add alongside the existing stage filenames:

- `PLANS_FILENAME = "04-roadmap.md"`
- `DRAFT_SEEDS_DIRNAME = "seeds"` — default subdirectory under the slug dir (plan architecture); plan rows still store a **relative path from the slug root**, e.g. `seeds/order-core.md`, not only a basename
- `plans_path(plans_dir, slug)` — `roadmap_dir(plans_dir, slug) / PLANS_FILENAME`
- `draft_seeds_dir(plans_dir, slug)` — `roadmap_dir(plans_dir, slug) / DRAFT_SEEDS_DIRNAME` (convenience for later steps; no filesystem I/O here)
- `resolve_draft_seed_path(plans_dir, slug, draft_seed_path)` — join `roadmap_dir` with the row's relative path after **path-segment validation** (reject empty, absolute, or traversal-bearing paths — same spirit as `_validate_slug`, applied to the relative path string)

**Rejected alternative:** hardcoding `plan-seeds/` or repo-root paths. Drafts live under the roadmap slug until `--apply` (step 7).

### Wire keys and row inventory (mint names here; step 4 documents them)

Expose prompt-pinnable constants:

- `PLANS_ROW_KEYS = ("plans", "ordering", "assumptions", "decisions")` — design collections only, same split as `DOMAIN_ROW_KEYS` / `COMPONENTS_ROW_KEYS` vs `REVIEW_ROW_KEYS`
- `PLANS_DESIGN_ROW_KINDS` — optional tuple of message labels if you want explicit pinning; otherwise derive labels inside `plans_design_rows`

**Plan row** (`plans` collection) — one mapping per derived plan:

| Field | Shape rule at parse |
| --- | --- |
| `id` | required non-empty string |
| `title` | required string (may be blank — emptiness is a gate judgment) |
| `disposition` | required closed enum (below) |
| `component_ids` | optional list of non-empty id strings; absent/null → empty tuple |
| `draft_seed_path` | required non-empty relative path under `DRAFT_SEEDS_DIRNAME` (`seeds/…`); reject paths that escape that directory (absolute, `..`, or first segment ≠ `seeds`) |
| `sizing_rationale` | required string (may be blank) |

**Ordering entry** (`ordering` collection) — execution sequence, not a design row with its own id:

| Field | Shape rule |
| --- | --- |
| `plan_id` | required non-empty string |
| `depends_on` | optional list of plan id strings |
| `assumption_targets` | optional list of plan id strings (ordering-level assumption **targets**, distinct from the `assumptions` inventory rows) |

Keep `ordering` as an **ordered tuple** of entries — do not collapse to a dict keyed by `plan_id`; step 3's "every plan id exactly once" gate needs the raw sequence with duplicates intact.

**Assumption row** (`assumptions` collection):

| Field | Shape rule |
| --- | --- |
| `id` | required non-empty string |
| `statement` | required string |
| `consuming_plan_ids` | required list (present-empty allowed) of non-empty id strings |

**Review collections** — unchanged contract: `feedback`, `removals`, `decisions` on `PlansArtifact` with the same dataclasses and parse/render behavior as earlier stages.

### Closed vocabulary

Add `PlanDisposition(str, enum.Enum)` with exactly four members matching the plan architecture:

- `keep` — one component → one plan
- `merge` — several components → one plan
- `split` — one component → several plans
- `cross-cutting` — not owned by a single component (CI, auth plumbing, etc.)

Add `_coerce_plan_disposition` mirroring `_coerce_disposition` / `_coerce_status` — unknown member raises `RoadmapArtifactError` naming the vocabulary.

Export member values for prompt pinning tests the same way existing enum tests do.

### Dataclasses and design-row enumeration

```text
PlanRow
OrderingEntry
AssumptionRow
PlansArtifact(plans, ordering, assumptions, decisions, body, feedback=(), removals=())
```

Add `plans_design_rows(artifact: PlansArtifact) -> tuple[tuple[str, str], ...]` returning **(kind label, id)** in render order:

1. every `plans` row → `("plan", row.id)`
2. every `assumptions` row → `("assumption", row.id)`
3. every `decision` row → `("decision", row.id)`

**Do not include `ordering` entries** — they reference plan ids but mint no row ids. Step 2 will wire `plans_design_rows` into `plan_tool/roadmap_gates.py:_rows_of` for `PlansArtifact`; pin that contract here so continuity, feedback targets, duplicate-id union, and inventory-has-prose gates cover **plans + assumptions + decisions**, not plans alone (completeness audit finding `plans-design-row-scope`).

### Parse / render / load API

Mirror the existing trio:

- `parse_plans_artifact(text: str) -> PlansArtifact`
- `render_plans_artifact(artifact: PlansArtifact) -> str`
- `load_plans_artifact(path: Path) -> PlansArtifact` via `_load`

**Open frontmatter schema** — ignore unknown keys; renderer emits only contract keys plus conditional review keys (same as stages 1–3).

**Shape vs relation split** — parsing raises on malformed YAML, missing required keys, wrong types, unknown enum members, and unsafe `draft_seed_path` strings. Parsing **accepts without raising** (add explicit negative tests for each):

- `component_ids` naming a component id not in `03-components.md`
- `ordering` entries referencing plan ids not in `plans`
- duplicate ids within or across `plans` / `assumptions` / `decisions`
- `consuming_plan_ids` / `depends_on` / `assumption_targets` naming unknown plan ids
- plan `id` failing `PLAN_ID_SLUG_RE`
- `cross-cutting` disposition with empty or non-empty `component_ids` (gate policy, not parse policy)
- ordering missing some plan ids or listing extras (totality — step 3)
- draft-seed provenance listing component ids not on the plan row (step 3 gate 3)

**Duplicate ids survive as separate rows** — keep ordered tuples, never dict-key at parse time (cross-step lesson).

**Serializer ships with parser** — `parse_plans_artifact(render_plans_artifact(x)) == x` must hold for a conforming fixture including feedback/removals. Enum fields render via `.value` (PyYAML `RepresenterError` lesson). Review keys omitted when empty.

Update the module docstring opening paragraph to list four artifacts including `04-roadmap.md`.

### Draft-seed provenance (minimal second parser)

Stage 4 side-output seeds carry a small YAML frontmatter block gates scan before `--apply` strips it. Add:

- `DRAFT_SEED_ROADMAP_COMPONENTS_KEY = "roadmap_components"`
- `DRAFT_SEED_CROSS_CUTTING_KEY = "cross_cutting"`
- `@dataclass(frozen=True) DraftSeedProvenance` — `roadmap_components: tuple[str, ...]`, `cross_cutting: bool = False`
- `parse_draft_seed_provenance(text: str) -> DraftSeedProvenance` — split frontmatter like other artifacts; require `roadmap_components` as a list of non-empty strings; accept optional `cross_cutting` boolean (default false when absent); **do not** validate that ids exist on a plan row or in components (step 3); **do not** validate seed body prose or `SEED_FORMAT.md` fence completeness here

One helper to render provenance back to a frontmatter block is optional; if omitted, step 6 can hand-assemble using the constants. Prefer a tiny `render_draft_seed_provenance` if it keeps gate fixtures DRY.

### Leaf discipline (must stay true)

- No first-party imports — mirror `create.SLUG_RE` pattern string locally; do not import `plan_tool/create.py`
- No `invoker` / subprocess seam
- Keep `_split_frontmatter` as a local mirror of `plan_tool/parser.py:_split_frontmatter` (consolidation stays deferred)
- Existing path helpers (`domain_path`, `constraints_path`, `components_path`) are **zero-diff** for their callers

### Shared locations (this step does not edit)

- `plan_tool/roadmap_gates.py:_rows_of`, `design_row_ids`, `_envelope_rows` — step 2 adds `PlansArtifact` arms using `plans_design_rows`
- `plan_tool/roadmap.py` stage table, lift path, disk writes — steps 5–6
- `ROADMAP_FORMAT.md` — step 4 reads landed names from this module
- `plan_tool/create.py:SLUG_RE` — authoritative slug definition; mirrored pattern tested from `tests/test_roadmap_artifacts.py` only

## Tests

Every test below must be green before the step is done. Extend `tests/test_roadmap_artifacts.py`; reuse existing helpers (`_load` patterns, frontmatter builder functions, `RoadmapArtifactError` assertions, leaf subprocess checks at the file tail).

### Tests for this step

- `test_plan_disposition_members` — four closed values in plan order
- `test_plan_id_slug_re_matches_create_slug_re` — local `PLAN_ID_SLUG_RE.pattern` equals `create.SLUG_RE.pattern`
- `test_plans_path_and_draft_seeds_dir_under_roadmap_slug` — path helpers nest under `roadmaps/<slug>/`
- `test_resolve_draft_seed_path_rejects_unsafe_relative_paths` — traversal / absolute paths raise
- `test_plans_row_key_constants_match_rendered_frontmatter` — rendered YAML keys equal `PLANS_ROW_KEYS` (+ review keys when present)
- `test_design_row_key_constants_exclude_review_keys_on_plans` — `feedback` / `removals` not in `PLANS_ROW_KEYS`
- `test_plans_design_rows_lists_plan_assumption_and_decision_kinds` — enumerator returns all three kinds in order; **no ordering entries**
- `test_conforming_plans_body_parses_every_row_kind` — typed rows match fixture
- `test_plans_artifact_round_trips_through_render_and_parse` — equality including ordering order
- `test_plans_feedback_and_removals_round_trip` — review collections on plans artifact
- `test_duplicate_plan_row_ids_survive_as_separate_rows` — tuple preservation
- `test_unknown_plan_disposition_raises_naming_vocabulary` — parse error names enum
- `test_missing_required_plan_row_key_raises_naming_row` — shape error cites row id / key
- `test_component_id_not_in_components_still_parses` — relation non-check
- `test_ordering_referencing_unknown_plan_id_still_parses` — relation non-check
- `test_assumption_consuming_unknown_plan_id_still_parses` — relation non-check
- `test_plan_id_not_matching_slug_re_still_parses` — SLUG_RE deferred to gates
- `test_duplicate_ordering_plan_ids_survive` — ordering not collapsed
- `test_unknown_frontmatter_keys_ignored_on_plans` — open schema
- `test_malformed_yaml_raises_and_names_path_for_plans` — `load_plans_artifact` binds path
- `test_parse_draft_seed_provenance_requires_roadmap_components` — shape error when missing
- `test_parse_draft_seed_provenance_accepts_cross_cutting_flag` — boolean optional member
- `test_draft_seed_provenance_unknown_component_id_still_parses` — relation non-check
- `test_leaf_imports_no_first_party_module` — unchanged green (existing test)
- `test_leaf_declares_no_invoker_seam` — unchanged green (existing test)

(approx. 22 new cases plus 2 existing leaf guards)

## Acceptance criteria

- `PLANS_FILENAME`, `PLANS_ROW_KEYS`, `PlanDisposition`, `PlanRow`, `OrderingEntry`, `AssumptionRow`, `PlansArtifact`, `plans_design_rows`, `parse_plans_artifact`, `render_plans_artifact`, `load_plans_artifact`, `plans_path`, `resolve_draft_seed_path`, `DRAFT_SEED_ROADMAP_COMPONENTS_KEY`, `DRAFT_SEED_CROSS_CUTTING_KEY`, and `parse_draft_seed_provenance` are importable from `plan_tool.roadmap_artifacts`
- `plans_design_rows` includes plan, assumption, and decision rows only (ordering excluded) — verified by `test_plans_design_rows_lists_plan_assumption_and_decision_kinds`
- `parse_plans_artifact(render_plans_artifact(x)) == x` for the conforming fixture
- Each relation non-check listed under Implementation has a test proving parse does **not** raise
- `PLAN_ID_SLUG_RE.pattern == create.SLUG_RE.pattern` in tests
- `rg 'from plan_tool' plan_tool/roadmap_artifacts.py` returns nothing; leaf subprocess tests still pass
- `uv run pytest tests/test_roadmap_artifacts.py -q` exits 0
- No edits outside the two declared files

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_load` / `safe_dump` for frontmatter parse and render
- [YAML 1.2.2 specification](https://yaml.org/spec/1.2.2/) — list-of-mapping row syntax for inventories
- [dataclasses — Python 3.13](https://docs.python.org/3.13/library/dataclasses.html) — frozen row types and artifact aggregate
- [pathlib — Python 3.13](https://docs.python.org/3.13/library/pathlib.html) — slug-dir path composition for `plans_path` / `resolve_draft_seed_path`
- [enum — Python 3.13](https://docs.python.org/3.13/library/enum.html) — `PlanDisposition` closed vocabulary

## Applicable guardrails

- **Plan intent / no merit gates** — this step defines shape only. Do not add parse-time checks for disposition correctness, seed prose quality, plan count, or sizing rationale content; those are excluded by the plan's scope fence and belong nowhere in this module.
- **Plan Out of scope / no auto-create** — no helpers that invoke `create`, write `plan-seeds/`, or preview runnable CLI lines; path helpers stop at resolved paths under the slug directory.
- **Shape vs relation split** — document and test every relation the gates own (see Implementation non-check list); do not tighten the parser to "help" step 3.
- **Feedback lifecycle** — reuse existing review row types unchanged; do not add new feedback states or review walks.
- **Leaf module** — no imports from `plan_tool/roadmap_gates.py`, `plan_tool/roadmap.py`, or `plan_tool/create.py` in production code.

## Deferred

- `plan_tool/roadmap_gates.py` envelope widening, `_rows_of` / `_envelope_rows` plans arm, and all relation gates including `SLUG_RE`, component coverage, ordering totality, and draft-bundle alignment — step 2–3
- `ROADMAP_FORMAT.md` fourth-artifact documentation — step 4 (reads landed constants from this module; code wins on name disagreements)
- Stage table row, multi-fence lift, side-output envelope field, atomic draft-dir rewrite — steps 5–6
- `--apply` / `-y` copy into `plan-seeds/` — step 7
- Consolidating the three `_split_frontmatter` copies (`parser.py`, `reprocess.py`, `roadmap_artifacts.py`) — BACKLOG / reconcile, not this step
- Full `SEED_FORMAT.md` body validation for draft seeds — step 6 prompt + operator review; this step only parses provenance keys gates need
