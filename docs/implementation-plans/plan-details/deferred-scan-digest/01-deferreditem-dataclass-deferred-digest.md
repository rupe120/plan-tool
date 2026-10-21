# Step 1 — Add the DeferredItem model and the deferred_digest leaf module

## Summary

This step creates `plan_tool/deferred_digest.py` as an empty leaf module carrying one thing: the `DeferredItem` dataclass, the shared value record every later collector, the dedup pass, the classifier, and the renderer pass around. It also adds the four `source_kind` string constants the collectors tag their items with. The key design decision is that every field beyond the harvest-time core is **optional with a default**, so each of the three collectors (steps 3/4/5) can build an item from only the fields its source actually has. The module imports nothing first-party, keeping it a clean leaf below the CLI. On green, `import plan_tool.deferred_digest` succeeds, `DeferredItem` constructs from a minimal field set, and the new unit tests in `tests/test_deferred_digest.py` pass.

## Table of Contents

- [Summary](#summary) — what the step ships and the observable result on green
- [Why](#why) — why a shared harvest record has to land first
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files this step adds
- [Implementation](#implementation) — the `DeferredItem` shape, the source-kind constants, and the leaf-module rules to respect
- [Tests](#tests) — the unit cases that pin the model and the constants
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer confirms
- [References](#references) — the Python docs behind the dataclass choices
- [Deferred](#deferred) — everything later steps own, kept out of this one

## Why

The whole plan is one harvest → dedup → classify → render pipeline, and every stage hands the next a list of the same record. Nothing works until that record exists. Step 1 is the foundation: it defines the `DeferredItem` model the three collectors (steps 3/4/5) fill, the dedup pass (step 6) filters, the classifier (steps 7/8) tags, and the renderer (step 9) prints. Landing the model and the module first — with no collectors, no CLI, no Claude — gives every dependent step (2 through 9 all list `depends_on: 1`) a stable shape to build against and keeps the risky parsing and classification work in later, smaller steps. There is nothing to run yet; the deliverable is the shared type and a place to hang the rest of the module.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/deferred_digest.py` — the leaf module, containing the module docstring, the `source_kind` constants, and the `DeferredItem` dataclass. No functions yet.
  - `tests/test_deferred_digest.py` — the mirror unit-test file, covering `DeferredItem` construction and the constants.
- **Existing files (edits only):** none.

## Implementation

**Add `DeferredItem` as a dataclass holding harvest-time provenance for one parked item.** Ground the field set in the plan's `## Architecture` section. The core fields every collector sets:

- `title: str` — the parked item's short name (the bold lead of a `- **Title** — body` bullet, a report finding's title, or a concept node's label).
- `summary: str` — the one-line rationale / body text.
- `source_kind: str` — which collector produced it; one of the four constants below.
- `source_path: Path` — the plan `.md`, `reports/*.json`, or `concepts.json` the item came from.
- `origin_slug: str` — the plan slug the deferral traces back to (the dedup pass in step 6 matches this against backlog `Origin:` backlinks).

The optional fields, each defaulted so a collector that has no such signal never sets them:

- `archived: bool = False` — set `True` by the archived-plan branch (step 2); the renderer sorts archived sources below live ones.
- `severity: Optional[str] = None`, `impact: Optional[str] = None`, `complexity: Optional[str] = None` — carried only from a report finding (step 4), feeding the classifier's pre-score (step 7).
- `node_id: Optional[str] = None`, `bucket: Optional[str] = None` — set only by the concept-deferral collector (step 5), which reads flat `decision-record` nodes.
- a pending/reviewed flag for concept records (e.g. `pending: bool = False`) — set by step 5 so the digest can show a concept deferral that is not yet `scope-review`-signed. Pick one clear directional name; do not model it as a tri-state unless step 5 needs one.

**Make every non-core field optional with a default — this is the load-bearing decision.** The three collectors populate different subsets: the plan-body collector has no `severity` or `node_id`; the report collector has `severity` but no `bucket`; the concept collector has `node_id`/`bucket` but no report triage. Optional-with-default lets each build a valid `DeferredItem` with keyword args for only its fields. The rejected alternative is one required field set that forces every collector to pass placeholder `None`s explicitly — more noise at every call site with no benefit.

**Recommend `@dataclass(frozen=True)`.** A harvest record is immutable provenance, and this matches the frozen-result convention of the sibling records `plan_tool/scope_out.py:ScopeOutResult` and `plan_tool/launcher.py:EscalateResult`. If steps 7/9 later want to attach a classifier `approach` tag or a render-time stable id onto the record, they do it with `dataclasses.replace` (idiomatic on a frozen dataclass) or on a downstream wrapper — that choice belongs to those steps, so **do not pre-declare `approach` or a stable-id field here.** Frozen is a recommendation, not a hard requirement; if a later step finds `replace` churny it can revisit, but default to frozen.

**Add the four `source_kind` values as module-level string constants**, not bare string literals scattered across collectors. Mirror the source-constant convention in `plan_tool/review.py` (e.g. its `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` / `CONCEPT_BUCKET_MISSING_SOURCE` string constants). The four values, taken verbatim from the plan's Architecture:

- `plan-deferred` — a `## Deferred` plan-body bullet.
- `plan-out-of-scope` — a `## Out of scope` plan-body bullet.
- `report-deferred` — a report-JSON `open_deferred` entry or `status == "skip"` recommendation.
- `concept-deferral` — a `concepts.json` `defer` / `wont_do` decision-record node.

Name the constants self-descriptively (e.g. `SOURCE_PLAN_DEFERRED = "plan-deferred"`). Steps 3/4/5 reference the constant, so the string lives in one place.

**Keep the module a leaf with no first-party imports.** Step 1 needs only `from dataclasses import dataclass, field`, `from pathlib import Path`, and `from typing import Optional`. Do **not** import `plan_tool.locator`, `plan_tool.parser`, `plan_tool.concept_tree`, or `plan_tool.review` here — those come later and, per the plan's import-cycle risk, get lazy-imported inside the collector functions that need them. Model the stdlib-only-leaf stance on `plan_tool/distill_thresholds.py`.

**Do not add placeholder function stubs.** "Module skeleton" here means the module plus the model and constants — not `NotImplementedError` stubs for harvest/dedup/classify/render. Each later step adds its own real functions against `DeferredItem`. Empty stubs would be dead scaffolding that reads as unfinished work on every reconcile.

**`DeferredItem` is a new aggregation record, not a consolidation of an existing one.** It deliberately sits alongside `plan_tool/review.py`'s `Recommendation` and `plan_tool/concept_tree.py`'s `ConceptNode` rather than reusing either: step 5's concept collector *reads* a `ConceptNode` and maps it into a `DeferredItem`, but the two types answer different questions (a concept ledger entry vs. a cross-source triage line). Do not fold them together.

## Tests

All cases live in `tests/test_deferred_digest.py`:

- `test_deferred_item_minimal_construction` — building with only the core fields (`title`, `summary`, `source_kind`, `source_path`, `origin_slug`) succeeds and leaves `archived` `False` and every optional field `None`.
- `test_deferred_item_carries_report_signal` — `severity`, `impact`, `complexity` round-trip when a report-style item sets them.
- `test_deferred_item_carries_concept_fields` — `node_id`, `bucket`, and the pending flag round-trip when a concept-style item sets them.
- `test_deferred_item_archived_flag` — `archived=True` is preserved.
- `test_deferred_item_is_frozen` — assigning to a field after construction raises `dataclasses.FrozenInstanceError` (drop this case only if a later decision makes the record non-frozen).
- `test_source_kind_constants` — the four constants equal `plan-deferred` / `plan-out-of-scope` / `report-deferred` / `concept-deferral` and are all distinct.
- `test_module_imports_cleanly` — `import plan_tool.deferred_digest` succeeds (a smoke check that the leaf has no broken or cyclic import).

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write the tests above alongside the `DeferredItem` definition and the constants in the same step. Every listed test must be green before step 1 is considered finished (green-before-done gate). The suite is fast and needs no `invoker=` stub, because step 1 spends no Claude and touches no backend.

## Acceptance criteria

- `plan_tool/deferred_digest.py` exists and `import plan_tool.deferred_digest` succeeds with no first-party imports.
- `DeferredItem` is a dataclass whose required fields are `title`, `summary`, `source_kind`, `source_path`, `origin_slug`, and whose optional defaulted fields include `archived` (default `False`), `severity`, `impact`, `complexity`, `node_id`, `bucket`, and a pending/reviewed flag (all defaulting to `None`/`False`).
- Constructing `DeferredItem` with only the required fields leaves every optional field at its default.
- Four module-level constants carry the exact `source_kind` strings `plan-deferred`, `plan-out-of-scope`, `report-deferred`, `concept-deferral`.
- `tests/test_deferred_digest.py` exists and all its cases pass under `uv run pytest tests/test_deferred_digest.py -q`.
- The module contains no function stubs and no first-party imports.

## References

- [dataclasses — Data Classes (Python docs)https: — `@dataclass`, `field(default=...)` / `field(default_factory=...)`, `frozen=True`, and `dataclasses.replace`, the basis for the `DeferredItem` model and the optional-with-default field rules.
- [pathlib — Object-oriented filesystem paths (Python docs)https: — `Path` as the type for the `source_path` field carried on each item.

## Deferred

- **Live + archived plan enumeration** — step 2, via `plan_tool/locator.py:load_manifest_plan_paths` plus the `**/archive/**/*.md` glob; step 1 only declares the `archived` field it sets.
- **Plan-body `## Out of scope` / `## Deferred` collector** — step 3.
- **Report-JSON collector** (`open_deferred` + `status: skip`) — step 4; it sets the `severity`/`impact`/`complexity` fields declared here.
- **Concept-deferral collector** reading `concepts.json` `defer`/`wont_do` decision records — step 5; it sets `node_id`/`bucket`/pending.
- **Backlog dedup** by `Origin:` backlink and normalized title — step 6.
- **Deterministic pre-score classifier** (`direct` vs `plan-tool`) — step 7; where the classifier `approach` tag lives is step 7's call.
- **Optional batched Claude refinement behind the `invoker=` seam** — step 8.
- **Stable ids (`d1`, `d2`, …) and the digest renderer** — step 9; where the render-time id lives is step 9's call.
- **The `plan-tool deferred` CLI command** — step 10.
