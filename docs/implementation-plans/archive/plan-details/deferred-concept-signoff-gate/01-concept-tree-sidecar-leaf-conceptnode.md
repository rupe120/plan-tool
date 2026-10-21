# Step 1 — Add the concept-tree sidecar leaf: `ConceptNode` / `ConceptTree`, `concepts_path`, save/load, and its data contract

## Summary

Add a new stdlib-only leaf `plan_tool/concept_tree.py` that models a plan's hierarchical concept tree and persists it as one tracked JSON sidecar at `plan-details/<slug>/concepts.json`. The leaf ships two dataclasses (`ConceptNode`, `ConceptTree`), a `concepts_path(plan_path)` resolver, a content-addressed node-id helper, and `save`/`read` functions that distinguish absence from invalid persisted state — all modeled on `plan_tool/grounding.py`. Register both dataclasses in `plan_tool/data_contract.py` and add paired sections to `DATA_CONTRACT.md` so the drift guard covers them. The most important decision: the node `id` is a stable content hash of title + parent path (no timestamp, no environment), so the tree diffs and round-trips deterministically. On green, a caller can build a `ConceptTree`, save it, and read back a byte-equal record; `tests/test_data_contract.py` passes with the two new registrations.

## Table of Contents

- [Why](#why) — what's missing today and why this leaf comes first
- [Files (creates vs edits)](#files-creates-vs-edits) — the one new leaf, one new test, two edits
- [Implementation](#implementation) — dataclass shapes, path resolution, save/load, id hashing, data-contract wiring
- [Tests](#tests) — round-trip, id stability, integrity-aware load, path resolution
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — dataclasses, hashlib, datetime, RFC 3339
- [Deferred](#deferred) — navigator, producer, gate wiring, atomic-write extraction

## Why

The deferral decision — which concepts a plan includes vs defers vs won't-do — is made silently by Claude today with no machine record and no operator sign-off (see the plan's Problem statement). The whole feature rests on one persisted artifact: the concept tree. This step lays that foundation — the dataclasses, the on-disk shape, and its data contract — with **no** producer, navigator, or gate wiring yet. Getting the sidecar shape and its drift-guard registration right first means every later step (emit in step 2, navigate in step 3, wire into `create`/`detail`/`completeness`/`scope-out` in steps 4–8) builds on a settled contract instead of reshaping it. There is a working sibling to copy exactly: `plan_tool/grounding.py` already solves the tracked-sidecar-beside-the-bundle problem, so this step mirrors it closely rather than inventing a new persistence shape.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/concept_tree.py` — the leaf: `ConceptNode`, `ConceptTree`, `CONCEPTS_SCHEMA_VERSION`, `CONCEPTS_FILENAME`, `concepts_path`, the node-id helper, `save_concepts`, `read_concepts`.
  - `tests/test_concept_tree.py` — unit tests for the leaf (round-trip, id stability, integrity-aware load, path resolution).
- **Existing files (edits only):**
  - `plan_tool/data_contract.py` — add two `PersistedDataclassContract` entries (for `ConceptTree` and `ConceptNode`) to `persisted_dataclass_contracts()`, mirroring the `Grounding` entry.
  - `DATA_CONTRACT.md` — add a `## Concept tree sidecar …` section plus two `### ` subsections (`ConceptTree`, `ConceptNode`), one field row per persisted field, modeled on the existing `## Grounding sidecar` block.

## Implementation

**Model `plan_tool/concept_tree.py` on `plan_tool/grounding.py` — same shape, same rules.** It is a stdlib-only leaf: no CLI, no backend/Claude imports, and any first-party helper (the slug resolver, the fingerprint) is imported **function-locally**, exactly as `grounding.py` imports `plan_tool.locator.slug_from_filename` and `plan_tool.fingerprint` inside function bodies. This keeps the module import-light and cycle-free. Register it in CLAUDE.md's leaf list — but that doc paragraph is owned by step 9's reconcile, not this step.

**Add two module constants** next to the dataclasses, matching `GROUNDING_FILENAME` / `GROUNDING_SCHEMA_VERSION`:
- `CONCEPTS_FILENAME = "concepts.json"`
- `CONCEPTS_SCHEMA_VERSION = 1`

**`ConceptNode` — a flat node with a `parent_id`, not a nested tree.** Fields (all from the plan's Architecture §A; a flat list is easier to fingerprint/diff/drift-guard):
- `id: str` — stable content hash of title + parent path; the annotations/coverage key.
- `path: str` — materialized dotted path, e.g. `auth.mfa.totp`.
- `title: str`.
- `depth: int` — 0 = top.
- `parent_id: str | None`.
- `order: int` — sibling order.
- `state: str` — one of `include` / `defer` / `wont_do`. The concept-tree vocabulary is deliberately its own: it shares only the keep/defer/reject *axis* with `StepScope` (`plan_tool/schema.py`), not its value strings (`StepScope`'s literals are `committed` / `deferred` / `wont_do` — only `wont_do` coincides). Do not reuse `StepScope`'s strings.
- `rationale: str` — one-line evidence-only note.
- `source: str` — `create` / `detail` / `manual`.
- `signed_off: bool` — default `False`.
- `signed_off_at: str | None` — ISO-8601 UTC or `None`; default `None`.
- `covered_by: list[str]` — a **reserved, advisory** field (owning step-title slugs), default empty. Coverage is recomputed by slug every audit and **never reads this field**, so no step populates it (§E/§H); this step only defines it. Store it as a plain `list[str]` with `field(default_factory=list)`.

Keep `state`, `source` as plain `str` for now (matching how `Grounding` uses plain fields) — do not add an Enum unless a later step needs one; the plan does not ask for one.

**`ConceptTree` — the top-level record.** Fields:
- `plan_slug: str`.
- `updated_at: str` — ISO-8601 UTC with trailing `Z` (same format string `grounding.py` uses: `"%Y-%m-%dT%H:%M:%SZ"`).
- `plan_fingerprint: str` — default `""` (the unset sentinel, as in `Grounding`); computed via `plan_tool/review_persistence.py:compute_plan_fingerprint` only when the plan markdown is finalized. Create-time navigator checkpoints taken before that write keep the sentinel and are unsigned resume state; the create caller refreshes the fingerprint after writing the finalized plan. A nonempty fingerprint that differs from the current plan fingerprint defines the single **stale-tree** state; the persisted record remains valid but its decisions are not current.
- `nodes: list[ConceptNode]` — `field(default_factory=list)`.
- `schema_version: int = CONCEPTS_SCHEMA_VERSION`.

**The node-id helper is the step's foundational logic — a content-addressed id.** Add a small helper (e.g. `compute_node_id(title, parent_path)`) that returns a `hashlib.sha256` hex digest over the title plus the parent's materialized path. Constraints that must hold:
- **Hash only identity inputs — title + parent path — never a timestamp, `order`, `state`, or any environment value.** Identity must not depend on when or where the node was recorded, so the id is reproducible from the stored fields on every later audit. (This mirrors the telemetry `decision_id` rule that observational fields stay out of a content hash — but here the input set is even narrower: purely structural.)
- **The same title under the same parent path yields the same id across runs.** A sibling with a different title, or the same title under a different parent, yields a different id. Add tests for both directions.
- Pick a stable framing for the two inputs (e.g. `parent_path\0title`) so a title containing the delimiter can't collide with a different (parent, title) pair.

**`concepts_path(plan_path)` mirrors `grounding_path`, not `locator`.** Compute `plan_path.parent / "plan-details" / slug / CONCEPTS_FILENAME`, reusing `plan_tool/locator.py:slug_from_filename` (function-local import, `default_to_stem=True` so it never returns `None`). Copy `grounding.py:grounding_path` almost verbatim — `locator.py` resolves only plan `.md` paths, never the detail-bundle dir, so it is the wrong tool here. Because the sidecar lands **inside** `plan-details/<slug>/`, existing archive/move/rename paths that byte-copy the whole bundle carry `concepts.json` for free (same as `grounding.json`); that is not this step's concern.

**`save_concepts` — atomic write, injectable clock.** Follow `grounding.py:write_grounding`:
- Take `plan_path` plus the tree data, derive `plan_slug` internally from `plan_path` (single-sourced from the same place `concepts_path` uses, so location and slug can never disagree).
- Preserve an explicitly unset `plan_fingerprint` for a prospective plan path that has not been written yet; compute the fingerprint only when the caller saves against finalized plan markdown.
- Accept an optional `now: datetime | None` param for deterministic tests; when omitted use `datetime.now(timezone.utc)`. **Sample the clock exactly once** and reuse that value for `updated_at`.
- `path.parent.mkdir(parents=True, exist_ok=True)`, then write `json.dumps(asdict(record), indent=2) + "\n"` through an atomic tempfile+`os.replace` writer. `dataclasses.asdict` recurses into `nodes`, so the nested `ConceptNode` list serializes without extra work.
- Return the absolute sidecar `Path`.

**`read_concepts(plan_path)` distinguishes absence from invalid persisted state.** Its signature is canonical and takes the **plan path**, mirroring `grounding.py:read_grounding(plan_path)` — it resolves the sidecar internally via `concepts_path(plan_path)`. Callers pass the plan path, never a pre-resolved sidecar path; sibling steps (6, 7) bind to this arity, not `read_concepts(concepts_path(plan_path))`. An absent file returns `None`, preserving the treeless-plan contract. If the file exists but is unreadable/malformed JSON, has a non-dict top level, has a mismatched/absent `schema_version`, or has a missing/wrong-typed required field, raise a dedicated `ConceptTreeIntegrityError` so callers cannot confuse corruption of the persisted machine contract with absence. Reconstruct **key-by-key with `.get(key, default)`** where fields are optional by contract, rebuild each `ConceptNode` from its dict, and read the **stored** `id` — never recompute it on read (recompute would reintroduce the drift the stored id freezes).

**A stale tree is valid data with one uniform caller policy, not an absent or invalid tree.** `read_concepts` returns the decoded tree unchanged and never derives, mutates, warns, or suppresses it; the consuming surface compares its stored fingerprint with the current plan fingerprint. `create` and `detail` stop their concept gates before consuming stale decisions and direct the operator to `scope-review --rederive`. `scope-review` likewise refuses to navigate or write the stale tree unless the operator supplies `--rederive`; that explicit path is the only stale-tree refresh and may invoke the producer. Completeness remains passive: it emits one advisory `concept-stale` finding, skips coverage/sign-off checks, and never derives or mutates. `scope-out` aborts before changing the plan, forward seed, or sidecar. Thus every surface preserves the old tree for recovery while treating none of its decisions as current.

**Atomic-write copy — inline it, flag the extraction.** `plan_tool/review_persistence.py:_atomic_write_text`, `plan_tool/lessons.py:_atomic_write_text`, and `plan_tool/grounding.py:_atomic_write_text` are already three inlined near-copies (grounding's docstring calls itself "the third near-copy" and names extraction "the next follow-up" once a fourth site appears). This leaf is that fourth site. Follow the codebase's mirror-not-share convention here: **inline a fourth copy** rather than importing one — extracting a shared `atomic_write_json` would touch `review_persistence.py` and `grounding.py`, both outside this step's declared files, and that consolidation is a reconcile-owned refactor. Note the now-due extraction in `## Deferred`.

**Register both dataclasses in `plan_tool/data_contract.py`.** Add two `PersistedDataclassContract` entries to `persisted_dataclass_contracts()`, copying the `Grounding` entry's shape:
- `ConceptTree` — `cls=concept_tree.ConceptTree`, `section_title="ConceptTree"`, `source_symbol="plan_tool/concept_tree.py:ConceptTree"`, `schema_constants=("CONCEPTS_SCHEMA_VERSION",)`. Add `from plan_tool import concept_tree` at module top (next to `from plan_tool import grounding`).
- `ConceptNode` — its own entry (nested dataclasses are registered separately here, exactly as `Recommendation` is registered on its own even though it nests inside `SavedReview`), `section_title="ConceptNode"`, `source_symbol="plan_tool/concept_tree.py:ConceptNode"`.

The registry discovers fields dynamically via `dc.fields`, so no per-field code is needed — but `tests/test_data_contract.py:test_every_persisted_field_is_documented_in_own_section` then **requires** every field to appear as `` `name` `` in that dataclass's `DATA_CONTRACT.md` section. That doc edit is the mandatory gate.

**Add the `DATA_CONTRACT.md` sections.** Mirror the `## Grounding sidecar (<plan-dir>/plan-details/<slug>/grounding.json)` block: a top `## Concept tree sidecar (…concepts.json)` intro naming the writer/reader, then a `### ConceptTree (concept_tree.py)` and a `### ConceptNode (concept_tree.py)` subsection, each a `| Field | Meaning |` table with one row per persisted field. Note the schema version as `` `1` = `CONCEPTS_SCHEMA_VERSION` `` and that a mismatch reads as re-derive, matching the `Grounding` row.

## Tests

Add to `tests/test_concept_tree.py` (unit tests, unmarked, hermetic, own `tmp_path`). Write these **with** the implementation; every one must be green before the step is done.

- `test_save_read_round_trip` — save a tree with 2–3 nodes, read it back, assert the record equals the input (all fields, including nested `ConceptNode` list).
- `test_read_missing_returns_none` — `read_concepts` on a plan with no sidecar returns `None`.
- `test_read_malformed_json_raises_integrity_error` — a garbage/non-JSON sidecar raises `ConceptTreeIntegrityError`.
- `test_read_wrong_schema_version_raises_integrity_error` — a sidecar whose `schema_version` != `CONCEPTS_SCHEMA_VERSION` raises `ConceptTreeIntegrityError`.
- `test_read_missing_required_field_raises_integrity_error` — a dict missing a required field raises `ConceptTreeIntegrityError`.
- `test_read_stale_fingerprint_returns_valid_tree_unchanged` — a well-formed sidecar whose nonempty fingerprint differs from the current plan reads as the stored tree rather than `None` or an integrity error; callers own the stale-tree policy.
- `test_node_id_is_stable` — same (title, parent path) → same id across two calls.
- `test_node_id_differs_by_title_and_by_parent` — different title, or same title under a different parent path, → different id.
- `test_node_id_ignores_nonstructural_fields` — building nodes that differ only in `order` / `state` / `rationale` gives the same id (id keys on title + parent path only).
- `test_concepts_path_mirrors_grounding_layout` — `concepts_path(plan_path)` ends in `plan-details/<slug>/concepts.json` and sits beside where `grounding_path` resolves.
- `test_save_is_atomic_and_creates_bundle_dir` — saving into a plan dir with no existing `plan-details/<slug>/` creates it and leaves no `.tmp` file behind.
- `test_updated_at_uses_injected_clock` — passing `now=` produces that exact `updated_at` (format `…Z`), and the clock is sampled once.

In `tests/test_data_contract.py` the existing parametrized guards (`test_every_persisted_field_is_documented_in_own_section`, `test_contract_registry_discovers_dataclass_fields`) pick up the two new registrations automatically once `DATA_CONTRACT.md` documents the fields — they are the wiring check for this step and must stay green.

## Acceptance criteria

- `plan_tool/concept_tree.py` exists as a stdlib-only leaf: `grep -E '^(from|import) plan_tool' plan_tool/concept_tree.py` returns nothing (any first-party import is function-local).
- `ConceptNode` and `ConceptTree` exist with the fields listed above; `CONCEPTS_SCHEMA_VERSION == 1` and `CONCEPTS_FILENAME == "concepts.json"`.
- `concepts_path(plan_path)` returns `<plan_path.parent>/plan-details/<slug>/concepts.json`.
- `save_concepts` then `read_concepts` round-trips a tree to an equal record; the file is valid JSON ending in a newline.
- `read_concepts` returns `None` only for a missing sidecar and raises `ConceptTreeIntegrityError` for a present malformed, wrong-version, unreadable, or field-invalid sidecar.
- A well-formed stale sidecar reads back unchanged; consuming surfaces compare its fingerprint and apply the plan's stale-tree policy without silently consuming its decisions.
- The node id is a deterministic hash of title + parent path: equal inputs → equal id, and it is unchanged by `order`/`state`/`rationale`.
- `persisted_dataclass_contracts()` includes entries for `ConceptTree` and `ConceptNode`; `DATA_CONTRACT.md` has matching sections with one row per field.
- `uv run pytest tests/test_concept_tree.py tests/test_data_contract.py -q` passes.

## References

- [dataclasses — Data Classes (Python 3.13 docs)](https://docs.python.org/3/library/dataclasses.html) — the `@dataclass` decorator, `field(default_factory=...)`, and `asdict` recursion used to model and serialize `ConceptTree` / `ConceptNode`.
- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — computing the stable SHA-256 node id from title + parent path.
- [datetime — Basic date and time types (Python docs)](https://docs.python.org/3/library/datetime.html) — producing timezone-aware UTC `updated_at` / `signed_off_at` timestamps (`datetime.now(timezone.utc)`).
- [RFC 3339 — Date and Time on the Internet: Timestamps](https://www.rfc-editor.org/rfc/rfc3339) — the ISO-8601/RFC 3339 UTC format (`…Z`) for the timestamp fields.

## Deferred

- **The concept-emit producer and its `invoker=` seam** — step 2. This step defines the tree shape and persistence only; nothing populates it from Claude yet.
- **`navigate_concepts` and the drill-down navigator** — step 3. The leaf gets no interactive walk in this step.
- **Wiring the sign-off gate into `create` / `detail` / `completeness` / `scope-out`, and the `scope-review` command** — steps 4–8.
- **The coverage and unsigned-deferral checks** — step 6, which recomputes coverage by slug every audit and never reads `covered_by`. This step only defines the `covered_by` field (a reserved, advisory `list[str]`, default empty).
- **Extracting a shared `atomic_write_json` helper** — reconcile-owned. `concept_tree.py` inlines the fourth near-copy of `_atomic_write_text`; per `grounding.py`'s documented convention the fourth call site is the trigger to extract, but consolidation touches `review_persistence.py`, `lessons.py`, and `grounding.py` (outside this step's files) and is a refactor `detail` cannot mint.
- **Registering the new leaf's import boundary in CLAUDE.md** — step 9's docs reconcile.
