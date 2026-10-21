> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Widen the gate envelope and design-row helpers for a fourth artifact

## Summary

Extend `plan_tool/roadmap_gates.py` so one frozen `ArtifactEnvelope` can carry **domain, constraints, components, and plans** plus an optional in-memory **draft-seed side-output bundle**. Add a `plans` slot and a `draft_seed_bundle` field, extend `StageArtifact`, the last-filled-slot properties (`artifact_under_check`, `filename_under_check`), `_rows_of`, `design_row_ids`, and `_envelope_rows`, and fix the two gates that still treat “constraints present” as a stage identity (`check_decision_records`, `check_artifact_non_empty`). The main design choice matches position 03: **one envelope type, one `Gate` call shape** — the artifact under check is the last filled slot, not a stage number branch; draft seeds ride on the envelope so `_run_stage` keeps passing a single argument. On green, a hand-built four-artifact envelope reports `04-roadmap.md` as under check, unions plan + assumption + decision ids into duplicate-id and decision-anchor scope, accepts a basename-keyed seed bundle without reading it yet, and every existing domain/constraints/components gate case still passes with no caller edits outside this module's tests.

## Table of Contents

- [Summary](#summary) — envelope widening, row helpers, side-output field, and scope boundary
- [Why](#why) — the gap step 3 and step 5 need closed first
- [Input](#input) — step 1 symbols this step imports
- [Files (creates vs edits)](#files-creates-vs-edits) — the two paths this step touches
- [Implementation](#implementation) — envelope fields, row helpers, gate dispatch fixes, bundle field
- [Tests](#tests) — new cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — typing and dataclass docs
- [Applicable guardrails](#applicable-guardrails) — plan fences binding this step
- [Deferred](#deferred) — later steps own the rest

## Why

`ArtifactEnvelope` at HEAD holds at most three artifacts and picks the one under check with a two-step rule (`components` → else `constraints` → else domain). That works for stages 1–3 but breaks the moment stage 4 exists: with all four slots filled, `artifact_under_check` would still name components, `filename_under_check` would still return `03-components.md`, and shared gates would judge the wrong collections. Worse, `check_duplicate_row_ids` and `check_decision_records` enumerate rows only through `_envelope_rows`, which today stops at three files — plan ids would never enter cross-artifact duplicate or anchor resolution even after a plans artifact parses. Step 1 lands `PlansArtifact` and `plans_design_rows`; step 3's relation gates and step 5's side-output lift both need the envelope widened first so variation stays in data, not in `plan_tool/roadmap.py`.

## Input

This step depends on step 1 landing the fourth artifact contract in `plan_tool/roadmap_artifacts.py`. It imports from that leaf only — leaf discipline unchanged.

- **`PLANS_FILENAME`** — `"04-roadmap.md"`; used by `filename_under_check`, `_envelope_rows`, and violation messages on the plans stage.
- **`PlansArtifact`** — parsed fourth artifact; joins `DomainArtifact`, `ConstraintsArtifact`, and `ComponentsArtifact` in the `StageArtifact` union and in `predecessor` typing.
- **`plans_design_rows(artifact)`** — step 1's public `(kind label, id)` enumerator. Returns plan, assumption, and decision rows in render order; **ordering entries are excluded** (they reference plan ids but mint no row ids). Step 2 wires `_rows_of` and `design_row_ids` to this function — the same anti-drift reason `design_row_ids` is already public for `plan_tool/roadmap.py:_check_predecessor_review_rows`.
- **Existing row helpers** — `_domain_rows`, `_constraints_rows`, `_rows_of`, `design_row_ids`, `_envelope_rows` are the extension points; domain, constraints, and components behavior must stay the same when `plans` is absent.

Field and wire names come from the landed step 1 module; if this detail and step 1 disagree, the code on disk wins.

## Files (creates vs edits)

- **New files:** none
- **Existing files (edits only):**
  - `plan_tool/roadmap_gates.py` — widen `ArtifactEnvelope`, `StageArtifact`, row-enumeration helpers, and stage-dispatch arms in `check_decision_records` and `check_artifact_non_empty`; add `draft_seed_bundle`; import `PLANS_FILENAME`, `PlansArtifact`, and `plans_design_rows` from the artifact leaf
  - `tests/test_roadmap_gates.py` — add `make_plans` / `plans_envelope` fixtures, envelope and row-helper cases for the fourth artifact and bundle field, regression guards for unchanged three-artifact behavior, extend imports; all existing cases must stay green

## Implementation

### Envelope widening

- **Add `plans: Optional[PlansArtifact] = None`** to `ArtifactEnvelope`, defaulting to `None` so every existing caller that passes only domain/constraints/components keeps compiling with zero edits — including `plan_tool/roadmap.py:_build_envelope`, which fills slots by `artifact_key` and does not change in this step.
- **Add `draft_seed_bundle: Optional[Mapping[str, str]] = None`** — keys are each plan row's `draft_seed_path` **basename**; values are the full lifted seed text (provenance frontmatter plus body). Defaults to `None`; step 5 fills it after lift; step 3 gates 3–4 read it. **This step adds the field only** — no gate inspects it yet.
- **Extend `StageArtifact`** to include `PlansArtifact`. `predecessor` stays `Optional[StageArtifact]`; a plans revision carries a `PlansArtifact` predecessor the same way components already does.
- **Replace the three-slot last-filled-slot rule** with a four-slot rule:
  - `plans is not None` → plans artifact / `PLANS_FILENAME`
  - else `components is not None` → components artifact / `COMPONENTS_FILENAME`
  - else `constraints is not None` → constraints artifact / `CONSTRAINTS_FILENAME`
  - else → domain artifact / `DOMAIN_FILENAME`
- **Update the `ArtifactEnvelope` docstring** to name four artifact slots, describe `draft_seed_bundle`, and say `predecessor` is the prior version of whichever artifact is under check.
- **Rejected alternative:** a parallel argument to the gate runner for the seed bundle. That breaks `Gate = Callable[[ArtifactEnvelope], list[Violation]]` and forces `_run_stage` to branch — the plan's architecture pins the bundle on the envelope instead.

### Row helpers

- **`_rows_of`** — add a `PlansArtifact` arm returning `plans_design_rows(artifact)` unchanged. Keep existing domain, constraints, and components arms; do not inline collection names from step 1.
- **`design_row_ids`** — no signature change; delegates to `_rows_of`, so plan, assumption, and decision ids enter the set once the dispatch lands. **Ordering ids stay out** — step 1's enumerator excludes them on purpose.
- **`_envelope_rows`** — after domain, constraints (when present), and components (when present), append `(PLANS_FILENAME, …)` when `envelope.plans is not None`. Upstream-first ordering must stay: domain → constraints → components → plans. This is what makes plan ids visible to `check_duplicate_row_ids` and `check_decision_records` cross-artifact scope (completeness audit finding `envelope-rows-plans`).
- **Feedback and removal rows stay out of `_rows_of`.** The comment block above `_prior_version` still governs; review rows are not design rows.

### Fix gates that confuse slot presence with stage identity

Two gates still use patterns that break when a fourth artifact is under check.

- **`check_decision_records`** — build the anchor-resolvable id set from the union of every design row `_envelope_rows` carries (including plans when present). Message wording should name the files actually in the envelope. When `plans` is present, `anchor_hint` must list the row kinds `_envelope_rows` actually carries (plan, assumption, component, pattern, constraint, and domain row kinds) so plans-stage retry text does not misdirect authors toward component-only or constraint-only anchors.
- **`check_artifact_non_empty`** — replace the final `else` (today implicitly `ComponentsArtifact`) with explicit type dispatch on `envelope.artifact_under_check`:
  - **`DomainArtifact`** — unchanged: non-empty `entities` and `workflows`
  - **`ConstraintsArtifact`** — unchanged: non-empty `constraints`
  - **`ComponentsArtifact`** — unchanged: non-empty `components`
  - **`PlansArtifact`** — require non-empty `plans` (at least one plan row). Do **not** require ordering totality, component coverage, seed-bundle alignment, or slug shape here — step 3 owns those as separate relation gates.
- **Gates that already early-return or read upstream correctly need no edit** for this step:
  - Components traceability gates (`check_component_entity_references`, `check_entity_component_coverage`, etc.) already return `[]` when `artifact_under_check` is not a `ComponentsArtifact`
  - Revision gates (`check_design_row_continuity`, `check_feedback_integrity`, `check_settled_decisions`) already read `artifact_under_check` and `_rows_of`; they work on plans once properties and row helpers are fixed
  - `check_duplicate_row_ids` already fans out over `_envelope_rows`; widening that helper is enough for cross-file id collisions involving plan ids

### Draft-seed bundle field (shape only)

- **Field contract:** `draft_seed_bundle` is optional; when set, each key is a basename string and each value is the complete seed text the stage would write. Empty mapping is valid data (step 3 gate 4 decides whether that violates); `None` means "no bundle attached yet" (stages 1–3 and pre-lift stage 4 attempts).
- **No gate reads the bundle in this step.** Do not add provenance scanning, path alignment, or seed-body checks — step 3 gates 3–4 consume this field.
- **One accessor pattern is enough:** gates that need lookup by basename can iterate the mapping or build a local dict; no separate helper is required unless it keeps step 3 fixtures DRY.

### Constraints that are not free to vary

- **No new plan-relation gates** — do not add component coverage, ordering totality, `SLUG_RE`, seed provenance, or `run_plans_gates` / `PLANS_GATES`; step 3 owns those.
- **No orchestrator edits** — `plan_tool/roadmap.py`, prompts, and CLI stay untouched; step 5 fills `draft_seed_bundle`; step 6 adds the `STAGES` row with `artifact_key="plans"`.
- **Leaf import discipline** — still exactly one first-party import (`plan_tool.roadmap_artifacts`). Keep `test_module_imports_only_the_artifact_leaf` green.
- **Do not confuse with `plan_tool/gates.py`** — that module proposes shell commands for plan steps; this module stays pure and deterministic.
- **Backward compatibility** — keyword-only defaults on `plans` and `draft_seed_bundle` are what make zero-diff true for existing envelope call sites; do not update `plan_tool/roadmap.py`, `tests/test_roadmap.py`, or `tests/test_roadmap_format.py` in this step.

## Tests

All cases live in `tests/test_roadmap_gates.py`. Plain unit tests (unmarked). Fixtures build row dataclasses directly; do not route gate cases through step 1's text parser except where an existing seam test already does.

### Tests for this step

Every new case below must be green before this step is finished, and **all existing cases in `tests/test_roadmap_gates.py` must still pass**.

**Fixtures**

- `make_plans` — builds a minimal `PlansArtifact` with at least one plan row (with `draft_seed_path` whose basename can key a bundle entry), one assumption row, one decision row, and prose naming every design-row id from `plans_design_rows`
- `plans_envelope` — returns `ArtifactEnvelope(domain=…, constraints=…, components=…, plans=…)` with sensible defaults, mirroring `components_envelope`

**Envelope properties**

- `test_artifact_under_check_returns_plans_when_present` — with all four slots filled, `artifact_under_check` is the plans artifact, not components
- `test_filename_under_check_returns_plans_filename` — `filename_under_check` is `PLANS_FILENAME` when `plans` is set
- `test_domain_constraints_and_components_envelopes_unchanged` — domain-only, domain+constraints, and three-artifact envelopes still report the same under-check artifact as today (regression guard for the last-filled-slot rule)
- `test_draft_seed_bundle_defaults_to_none` — `ArtifactEnvelope(domain=…)` constructs with `draft_seed_bundle is None`
- `test_draft_seed_bundle_stores_basename_keyed_text` — envelope accepts a mapping keyed by draft-seed basename; values round-trip unchanged

**Row helpers**

- `test_design_row_ids_includes_plan_assumption_and_decision_ids` — `design_row_ids(plans_artifact)` contains every plan, assumption, and decision id; **does not** contain ordering-only references
- `test_envelope_rows_lists_four_artifacts_upstream_first` — `_envelope_rows` on a full envelope returns domain, constraints, components, then plans in that order
- `test_plans_rows_match_step_one_enumerator` — `_rows_of(plans_artifact)` equals `plans_design_rows(plans_artifact)`
- `test_ordering_entries_absent_from_plans_design_rows` — explicit guard that ordering plan ids are not design rows (pins step 1 contract step 2 depends on)

**Duplicate-id and decision-anchor scope**

- `test_id_shared_across_plans_and_components_violates` — a plan id colliding with a component id produces one duplicate-id violation, reported against `PLANS_FILENAME` as the side the retried stage rewrites
- `test_decision_anchor_on_plans_resolves_plan_id` — a decision on the plans artifact anchoring to a plan row id defined in the same artifact passes `check_decision_records`
- `test_decision_unresolved_anchor_hint_on_plans_names_plan_and_assumption_ids` — unresolved-anchor message on a plans-stage envelope mentions plan (and assumption) row kinds, not only component/pattern kinds

**Stage dispatch fixes**

- `test_artifact_non_empty_requires_plan_rows` — a plans artifact with zero plan rows violates; one plan row passes
- `test_artifact_non_empty_still_requires_components_on_components_stage` — regression: three-slot envelope with patterns but no component rows still violates

**Revision gates on plans**

- `test_design_row_continuity_on_plans_predecessor` — dropping an assumption row without a removal record violates when `predecessor` is a prior `PlansArtifact`
- `test_feedback_integrity_on_plans_envelope` — answered feedback on a plans revision clears when predecessor and response match (shared gate, new artifact kind)
- `test_predecessor_feedback_preflight_resolves_plan_id` — `design_row_ids(plans_artifact)` includes plan ids a feedback row can target (documents the contract `plan_tool/roadmap.py:_check_predecessor_review_rows` will use once stage 4 lands; no orchestrator edit in this step)

**Layering (unchanged — must stay green)**

- `test_module_imports_only_the_artifact_leaf` — still passes after adding `PlansArtifact` imports

## Acceptance criteria

- Only `plan_tool/roadmap_gates.py` and `tests/test_roadmap_gates.py` change among production and test code
- `plan_tool/roadmap.py`, `tests/test_roadmap.py`, and `tests/test_roadmap_format.py` carry **zero diff** — existing `ArtifactEnvelope(domain=…, constraints=…, components=…)` call sites compile and behave unchanged
- `ArtifactEnvelope` accepts optional `plans=` and `draft_seed_bundle=` keywords defaulting to `None`
- `StageArtifact` includes `PlansArtifact`; `artifact_under_check` and `filename_under_check` follow the four-slot last-filled rule (plans → components → constraints → domain)
- `_rows_of`, `design_row_ids`, and `_envelope_rows` include plans design rows when the slot is filled; `_rows_of` dispatches through `plans_design_rows` from step 1; ordering entries are excluded from design-row scope
- `check_decision_records` resolves anchors against the union of design rows in every artifact the envelope carries, including plans when present
- When `plans` is present, unresolved-anchor `anchor_hint` text names plan and assumption row kinds alongside upstream kinds
- `check_artifact_non_empty` dispatches on artifact type and requires at least one plan row when a `PlansArtifact` is under check
- `run_plans_gates`, `PLANS_GATES`, and plan-relation gate functions **do not exist yet** — step 3 adds them; no gate reads `draft_seed_bundle` yet — step 3 gates 3–4 do
- `rg '^(from|import) plan_tool' plan_tool/roadmap_gates.py` matches only `plan_tool.roadmap_artifacts`; `test_module_imports_only_the_artifact_leaf` passes
- `uv run pytest tests/test_roadmap_gates.py -q` passes, and the full suite stays green

## References

- [typing — Support for type hints (Python 3.13)](https://docs.python.org/3.13/library/typing.html) — `Union`, `Optional`, and `Mapping` on the widened envelope and `StageArtifact`
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — frozen `ArtifactEnvelope` and test fixtures built with `replace`

## Applicable guardrails

- **The plan's step intent — table-driven runner, no orchestrator branch.** This step widens data (`ArtifactEnvelope`, row helpers, bundle field) only; it does not edit `plan_tool/roadmap.py` or add stage conditionals there.
- **The plan's Out of scope — merit and seed-quality gates.** No gate in this step judges disposition choice, seed prose, or plan count; the plans non-empty rule is the same structural guard earlier stages use (require the primary inventory rows), not a quality check.
- **The plan's Out of scope — rewriting stages 1–3 feedback lifecycle.** Revision gates reuse the existing feedback/removal contract; plan and assumption ids enter `design_row_ids` so pre-flight and gate resolution stay one channel — minimum widening only.
- **The plan's Architecture — side-output bundle on the envelope.** The bundle field lands here so step 5 can fill it and step 3 can gate it without changing the `Gate` type or `_run_stage`'s single-envelope call.

## Deferred

- **`run_plans_gates`, `PLANS_GATES`, and the six plan-relation observables** — step 3; includes gates 3–4 reading `draft_seed_bundle`
- **`plan_tool/roadmap.py` side-output lift, `_build_envelope` filling `draft_seed_bundle`, and the stage-4 `STAGES` row** — steps 5–6; `_build_envelope` already fills artifact slots by `artifact_key` and needs no change until the plans row exists
- **`plan_tool/roadmap.py:_check_predecessor_review_rows` edits** — none required once `design_row_ids` covers plans; stage wiring is step 6
- **`ROADMAP_FORMAT.md` documentation and executable examples** — step 4
- **Consolidating frontmatter fence scanners** — cross-module refactor; not this step
