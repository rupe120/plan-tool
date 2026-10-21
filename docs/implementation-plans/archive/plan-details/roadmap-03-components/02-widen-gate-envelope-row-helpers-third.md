> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Widen the gate envelope and row helpers for a third artifact

## Summary

This step extends `plan_tool/roadmap_gates.py` so the shared gate runner can carry **domain, constraints, and components** in one frozen envelope without the orchestrator learning which stage is running. It adds a `components` slot to `ArtifactEnvelope`, extends `StageArtifact`, `artifact_under_check`, `filename_under_check`, `_rows_of`, `design_row_ids`, and `_envelope_rows`, and fixes the two existing gates that today use `envelope.constraints is None` as a stand-in for stage identity — `check_decision_records` and `check_artifact_non_empty`. The main design decision is unchanged from position 02: **one envelope type, one gate call shape**, with the artifact under check inferred from the last filled slot rather than a stage number branch. On green, a hand-built three-artifact envelope reports the components file as under check, folds component ids into `design_row_ids` and duplicate-id scope, and every existing domain/constraints gate case still passes with no caller edits outside this module's tests.

## Table of Contents

- [Summary](#summary) — envelope widening, row helpers, and what stays out of scope.
- [Why](#why) — the pinned limitation step 3 and step 5 need routed around.
- [Input](#input) — step 1 symbols this step imports and must not re-list.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches.
- [Implementation](#implementation) — envelope fields, row helpers, gate dispatch fixes, and rules that are not free to vary.
- [Tests](#tests) — new cases plus the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — typing and dataclass docs worth skimming.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — what later steps own.

## Why

`ArtifactEnvelope` today holds at most two artifacts and decides which one is under check with `constraints is None`. That worked for stages 1–2 but breaks the moment a third artifact exists: with domain, constraints, and components all present, `artifact_under_check` would still name constraints, `filename_under_check` would still return `02-constraints.md`, and `check_artifact_non_empty` would judge the wrong collections. `tests/test_roadmap.py:TestSyntheticThirdStage` already documents the workaround — stage 3 reuses the `constraints` `artifact_key` because the envelope has no components slot. Step 1 lands the typed `ComponentsArtifact` and `components_design_rows`; step 3's five traceability gates and step 5's `STAGES` row both need the envelope and row helpers widened first so variation stays in data, not in `plan_tool/roadmap.py`.

## Input

This step depends on step 1 landing the third artifact contract in `plan_tool/roadmap_artifacts.py`. It imports symbols from that module only — leaf discipline unchanged.

- **`COMPONENTS_FILENAME`** — `"03-components.md"`; used by `filename_under_check`, `_envelope_rows`, and violation messages on the components stage.
- **`ComponentsArtifact`** — the parsed third artifact; joins `DomainArtifact` and `ConstraintsArtifact` in the `StageArtifact` union and in `predecessor` typing.
- **`components_design_rows(artifact)`** — step 1's public `(kind label, id)` enumerator for every design row on a components artifact. Step 2 wires `_rows_of` and `design_row_ids` to this function instead of re-declaring collection names — the same anti-drift reason `design_row_ids` is already public for `plan_tool/roadmap.py:_check_predecessor_review_rows`.
- **Existing row helpers** — `_domain_rows`, `_constraints_rows`, `_rows_of`, `design_row_ids`, `_envelope_rows` are the extension points; domain and constraints behavior must stay the same when `components` is absent.

Field and wire names come from the landed step 1 module; if this detail and step 1 disagree, the code on disk wins.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_gates.py` — widen `ArtifactEnvelope`, `StageArtifact`, row-enumeration helpers, and the stage-dispatch arms in `check_decision_records` and `check_artifact_non_empty`; import `COMPONENTS_FILENAME`, `ComponentsArtifact`, and `components_design_rows` from the artifact leaf.
  - `tests/test_roadmap_gates.py` — add a `make_components` / `components_envelope` fixture pair, envelope and row-helper cases for the third artifact, regression guards for unchanged domain/constraints behavior, and extend imports; all existing cases must stay green.

## Implementation

### Envelope widening

- **Add `components: Optional[ComponentsArtifact] = None`** to `ArtifactEnvelope`, defaulting to `None` so every existing caller that passes only `domain` and/or `constraints` keeps compiling with zero edits — including `plan_tool/roadmap.py:_build_envelope`, which fills slots by `artifact_key` and does not change in this step.
- **Extend `StageArtifact`** to `Union[DomainArtifact, ConstraintsArtifact, ComponentsArtifact]`. `predecessor` stays typed as `Optional[StageArtifact]`; a components revision carries a `ComponentsArtifact` predecessor the same way constraints already does.
- **Replace the two-slot `artifact_under_check` / `filename_under_check` logic** with a last-filled-slot rule:
  - `components is not None` → components artifact / `COMPONENTS_FILENAME`
  - else `constraints is not None` → constraints artifact / `CONSTRAINTS_FILENAME`
  - else → domain artifact / `DOMAIN_FILENAME`
- **Update the `ArtifactEnvelope` docstring** to name three artifact slots and to say `predecessor` is the prior version of whichever artifact is under check (domain, constraints, or components).
- **Rejected alternative:** branching on stage number inside the gate module or leaving orchestrator call sites to pass a separate "under check" pointer. That moves per-stage knowledge back into code the stage table exists to keep dumb.

### Row helpers

- **`_rows_of`** — add a `ComponentsArtifact` arm that returns `components_design_rows(artifact)` unchanged. Keep the existing `DomainArtifact` and `ConstraintsArtifact` arms; do not inline collection names from step 1.
- **`design_row_ids`** — no signature change; it already delegates to `_rows_of`, so component ids enter the set automatically once the dispatch lands.
- **`_envelope_rows`** — after appending domain and (when present) constraints rows, append `(COMPONENTS_FILENAME, …)` when `envelope.components is not None`. Use `_rows_of(envelope.components)` or call `components_design_rows` directly — same tuple shape either way. Upstream-first ordering must stay: domain, then constraints, then components.
- **Feedback and removal rows stay out of `_rows_of`.** The existing comment block above `_prior_version` still governs; review rows are not design rows.

### Fix gates that confuse "constraints present" with "constraints stage"

Two gates today use `envelope.constraints is None` as a proxy for stage identity. Both must key off what is under check instead.

- **`check_decision_records`** — build the anchor-resolvable id set from the union of every design row `_envelope_rows` carries (after components are included), not from a domain-vs-constraints binary. Message wording should name the files actually in the envelope (domain only; domain + constraints; or all three). One way: derive `undefined_by` from the filenames `_envelope_rows` returns rather than hard-coding two strings. **Also replace today's `envelope.constraints is None` binary's `anchor_hint` text** — at HEAD it tells authors to anchor to disposition/constraint/entity ids and never names component or pattern ids. When `components` is present, `anchor_hint` must list the row kinds `_envelope_rows` actually carries (component, pattern, constraint, and domain row ids) so components-stage retry text does not misdirect.
- **`check_artifact_non_empty`** — dispatch on the type of `envelope.artifact_under_check` (or equivalently on `filename_under_check`):
  - **`DomainArtifact`** — keep today's rule: require non-empty `entities` and `workflows`.
  - **`ConstraintsArtifact`** — keep today's rule: require non-empty `constraints` (dispositions alone are not enough).
  - **`ComponentsArtifact`** — require non-empty `components` (at least one component row). Do **not** add partition-quality, pattern-count, or entity-coverage rules here — step 3 owns those as separate traceability gates.
- **Gates that already early-return or read upstream correctly need no edit** for this step:
  - `check_attribute_totality` and `check_constraint_anchors` return `[]` when `envelope.constraints is None`; on a components-stage envelope constraints is present, which is correct — they judge constraints against domain, not the artifact under check.
  - Revision gates (`check_design_row_continuity`, `check_feedback_integrity`, `check_settled_decisions`) already read `artifact_under_check` and `_rows_of`; they work on components once the properties and row helpers are fixed.
  - `check_duplicate_row_ids` already fans out over `_envelope_rows`; widening that helper is enough for cross-file id collisions involving components.

### Constraints that are not free to vary

- **No new traceability gates** — do not add entity coverage, pattern presence, constraint discharge, or `run_components_gates` / `COMPONENTS_GATES`; step 3 owns those.
- **No orchestrator edits** — `plan_tool/roadmap.py`, prompts, and CLI stay untouched; step 5 adds the `STAGES` row with `artifact_key="components"`.
- **Leaf import discipline** — still exactly one first-party import (`plan_tool.roadmap_artifacts`). Keep `test_module_imports_only_the_artifact_leaf` green.
- **Do not confuse with `plan_tool/gates.py`** — that module proposes shell commands for plan steps; this module stays pure and deterministic.
- **Backward compatibility** — keyword-only default on `components` is what makes zero-diff true for existing envelope call sites; do not update `plan_tool/roadmap.py` or `tests/test_roadmap.py` in this step.

## Tests

All cases live in `tests/test_roadmap_gates.py`. Plain unit tests (unmarked). Fixtures build row dataclasses directly; do not route gate cases through step 1's text parser except where noted as a deliberate seam test.

### Tests for this step

Every new case below must be green before this step is finished, and **all existing cases in `tests/test_roadmap_gates.py` must still pass**.

**Fixtures**

- `make_components` — builds a minimal conforming `ComponentsArtifact` with at least one system pattern, one component pattern, one component (with non-empty `entity_ids` and `pattern_ids`), and prose that names every design-row id.
- `components_envelope` — returns `ArtifactEnvelope(domain=…, constraints=…, components=…)` with sensible defaults, mirroring `constraints_envelope`.

**Envelope properties**

- `test_artifact_under_check_returns_components_when_present` — with all three slots filled, `artifact_under_check` is the components artifact, not constraints.
- `test_filename_under_check_returns_components_filename` — `filename_under_check` is `COMPONENTS_FILENAME` when `components` is set.
- `test_domain_and_constraints_envelopes_unchanged` — domain-only and domain+constraints envelopes still report domain / constraints as under check (regression guard for the last-filled-slot rule).

**Row helpers**

- `test_design_row_ids_includes_component_and_pattern_ids` — `design_row_ids(components_artifact)` contains every system-pattern, component-pattern, component, and decision id from the fixture.
- `test_envelope_rows_lists_three_artifacts_upstream_first` — `_envelope_rows` on a full envelope returns domain, then constraints, then components entries in that order.
- `test_components_rows_match_step_one_enumerator` — `_rows_of(components_artifact)` equals `components_design_rows(components_artifact)` (proves the gate module did not fork the inventory).

**Duplicate-id scope**

- `test_id_shared_across_components_and_domain_violates` — a component id colliding with a domain entity id produces one duplicate-id violation, reported against `COMPONENTS_FILENAME` as the side the retried stage rewrites.

**Stage dispatch fixes**

- `test_decision_anchor_on_components_resolves_upstream_constraint_id` — a decision on the components artifact anchoring to a constraint id defined in the envelope's constraints artifact passes `check_decision_records` (would fail if anchor resolution still used the old binary).
- `test_decision_unresolved_anchor_hint_on_components_names_component_and_pattern_ids` — unresolved anchor violation message on a components-stage envelope mentions component/pattern row kinds (fails if `anchor_hint` still uses the old disposition/constraint/entity-only binary).
- `test_artifact_non_empty_requires_component_rows` — a components artifact with zero component rows violates; one component row passes.
- `test_artifact_non_empty_still_requires_constraints_on_constraints_stage` — regression: constraints-stage envelope with dispositions but no constraints still violates.

**Revision gates on components**

- `test_design_row_continuity_on_components_predecessor` — dropping a component row without a removal record violates when `predecessor` is a prior `ComponentsArtifact`.
- `test_feedback_integrity_on_components_envelope` — an answered feedback row on a components revision clears when predecessor and response match (shared gate, new artifact kind).

**Layering (unchanged — must stay green)**

- `test_module_imports_only_the_artifact_leaf` — still passes after adding `ComponentsArtifact` imports.

## Acceptance criteria

- Only `plan_tool/roadmap_gates.py` and `tests/test_roadmap_gates.py` change among production and test code.
- `plan_tool/roadmap.py`, `tests/test_roadmap.py`, and `tests/test_roadmap_format.py` carry **zero diff** — existing `ArtifactEnvelope(domain=…, constraints=…)` call sites compile and behave unchanged.
- `ArtifactEnvelope` accepts an optional `components=` keyword defaulting to `None`.
- `StageArtifact` includes `ComponentsArtifact`; `artifact_under_check` and `filename_under_check` follow the last-filled-slot rule (components → constraints → domain).
- `_rows_of`, `design_row_ids`, and `_envelope_rows` include components design rows when the slot is filled; `_rows_of` dispatches through `components_design_rows` from step 1 rather than re-listing collections.
- `check_decision_records` resolves anchors against the union of design rows in every artifact the envelope carries, not against a `constraints is None` binary.
- When `components` is present, unresolved-anchor `anchor_hint` text names component and pattern ids (alongside constraint and domain row kinds) — not the old disposition/constraint/entity-only wording.
- `check_artifact_non_empty` dispatches on artifact type and requires at least one component row when a `ComponentsArtifact` is under check.
- `run_components_gates`, `COMPONENTS_GATES`, and the five components traceability gate functions **do not exist yet** — step 3 adds them.
- `rg '^(from|import) plan_tool' plan_tool/roadmap_gates.py` matches only `plan_tool.roadmap_artifacts`; `test_module_imports_only_the_artifact_leaf` passes.
- `uv run pytest tests/test_roadmap_gates.py -q` passes, and the full suite stays green.

## References

- [typing — Support for type hints](https://docs.python.org/3/library/typing.html) — `Union` / optional fields on the widened envelope and `StageArtifact`.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — frozen `ArtifactEnvelope` and test fixtures built with `replace`.

## Applicable guardrails

- **The plan's step intent — table-driven runner, no orchestrator branch.** This step widens data (`ArtifactEnvelope`, row helpers) only; it does not edit `plan_tool/roadmap.py` or add stage conditionals there.
- **The plan's Out of scope — partition quality and pattern merit.** No new gates encode decomposition quality; the components non-empty rule is the same structural guard domain and constraints already use (require the primary inventory rows), not a merit check.
- **The plan's Out of scope — second feedback channel.** Revision gates reuse the existing feedback/removal contract; component ids enter `design_row_ids` so pre-flight and gate resolution stay one channel.
- **The plan's Out of scope — pre-emptive skeleton redesign.** Smallest additive change: one optional envelope field, last-filled-slot properties, and targeted fixes to gates that would mis-identify the stage — not a new envelope type or per-stage wrapper.

## Deferred

- **The five components traceability gates and `run_components_gates` / `COMPONENTS_GATES`** — step 3; this step deliberately does not mint them.
- **`plan_tool/roadmap.py` `STAGES` row, prompt assembly, disk write, and `--from-stage 3`** — step 5; `_build_envelope` already fills slots by `artifact_key` and needs no change until that row exists.
- **Updating `tests/test_roadmap.py:TestSyntheticThirdStage` to use `artifact_key="components"`** — step 5 when the real stage lands; the test's comment documents today's two-slot limitation this step removes in the gate module only.
- **`ROADMAP_FORMAT.md` documentation and executable examples** — step 4.
- **Consolidating the three frontmatter fence scanners** — cross-module refactor; not this step.
