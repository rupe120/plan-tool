> **Replaced**: this file has been superseded by `docs/implementation-plans/2-jira-layer-and-test-recs.md`.
> Preserved here for history; do not edit.

## Overview

Enrich the `plan-tool jira` story export so every exported story declares which **layer** it lands in — `frontend` / `backend` / `full_stack` / `infra` — and carries two derived fields: a **UI-impact note** on any backend/full-stack story (does the API/schema/behavior change surface a visible frontend change, with `none` a first-class answer) and a **what-and-how-to-test recommendation** for any frontend-impacting story (a `frontend`/`full_stack` story, or a `backend` story whose UI-impact note is non-empty and non-"none"). On top of the structured fields, the export prepends a short **layer indicator tag** to the rendered story title (e.g. `[FE]` / `[BE]` / `[FE+BE]` / `[INFRA]`) so FE vs BE stories are legible at a glance. The change is a single, well-bounded surface — the jira export leg — but touches the `Story` schema, its parser, both renderers, the `plan_tool/prompts/jira.md` prompt, validation, the `--lint` path, and the docs. Every new field is defaulted so existing exports still parse and round-trip.

## Problem statement

The current `Story` record (`plan_tool/jira.py:457`, documented in `JIRA_FORMAT.md` "Story schema") is layer-agnostic: `id`, `title`, `description`, `acceptance_criteria`, `files`, `steps`, `depends_on`, `estimate_hours`, `status`. Nothing tells a reviewer whether a story lands in the UI, the service, or both — the reader has to infer it from `files` and prose. Two signals get lost: **cross-layer coupling on backend work** — a backend story that changes an API shape or validation rule often forces a visible frontend change, but the export never states it, so the UI follow-up is discovered late or missed at hand-off; and the **testing on-ramp for UI work** — frontend-facing changes are the surface most prone to under-testing, yet the story gives no guidance on *what* to test or at *which level* (`acceptance_criteria` says what "done" means, not how to prove it in the UI). Making the layer explicit, forcing a UI-impact answer on backend stories, and attaching a concrete test recommendation to frontend-impacting stories surfaces all of this at export time, in the artifact a tracker consumes.

## Architecture

**Schema — three additive fields on `Story` (`plan_tool/jira.py`), all defaulted for back-compat:**
- `layer: str` — one of `frontend | backend | full_stack | infra`; defaults to the sentinel `unspecified` when a legacy/older export omits it.
- `ui_impact: str` — prose downstream-UI-impact note. Empty means "not provided"; the literal `none`/`None` is a valid, meaningful value the prompt is told to emit when a backend change is UI-invisible.
- `frontend_test_recommendation: str` (or a `list[str]` — settle in `detail`) — advisory what-and-how-to-test guidance that sits alongside `acceptance_criteria`, never replacing it.

Reflect the same fields in `DATA_CONTRACT.md` if the persisted jira JSON is drift-tracked, and update the drift guard.

**Parser — read, validate, default.** `parse_jira_response` (`plan_tool/jira.py:786`) and the lint-path reader (`read_stories_for_lint` / the parse at `:1470`) learn the fields: `layer` must be in the enum when present, and a missing/invalid value defaults to `unspecified` (do not hard-reject — additive/back-compat). When `layer` ∈ `{backend, full_stack}`, a missing `ui_impact` is a **soft-lint warning**, not a parse failure (mirroring the acceptance-criteria lint posture, `lint_acceptance_criteria` at `:291`). When a story is frontend-impacting (layer `frontend`/`full_stack`, or `backend` with a non-empty, non-"none" `ui_impact`), a missing/low-content `frontend_test_recommendation` is a soft-lint warning. Hard-blocking stays reserved for the crisp structural rules already enforced.

**Renderers — surface the fields.**
- *Title layer indicator (both renderers).* Prepend a short fixed-width layer tag to the rendered title. The title renders today with a `[<id>] ` prefix; the layer tag goes **right after** the id prefix, e.g. `[AUTH-S1] [BE] <title>`. Derive the tag deterministically from `layer` (`frontend → [FE]`, `backend → [BE]`, `full_stack → [FE+BE]`, `infra → [INFRA]`, `unspecified →` no tag). This is a **render-time decoration only** — do not bake the tag into the stored `Story.title`, so re-parse / re-run / `--lint` stay idempotent. Settle exact tag glyphs and whether `infra` shows a tag in `detail`.
- `format_markdown` (`:964`): apply the title tag, plus a `## Layer` line (or fold into the story header banner), a `## UI impact` section (rendered `_(none)_` when empty), and a `## Testing recommendation` section for frontend-impacting stories. Match the existing `_(no description)_` / `_(none specified)_` placeholder style.
- `format_json` (`:1077`): emit `layer`, `ui_impact`, `frontend_test_recommendation` keys alongside existing story fields. Keep the JSON `title` **clean** — the layer tag is a markdown-render decoration, not a stored value.

Update `JIRA_FORMAT.md`: schema table, markdown + JSON samples, validation-rules section, and soft-lint rows.

**Prompt — ask for the new fields.** Extend `plan_tool/prompts/jira.md` so the one whole-plan Claude call assigns each story its `layer`, writes the `ui_impact` note (explicitly instructing "state `none` when a backend change is UI-invisible"), and — for frontend-impacting stories — a concrete, non-generic testing recommendation naming flows/components and a test level. Tighten against the "test it works" failure mode with an explicit instruction plus example.

**Lint — extend `jira --lint`.** `cmd_jira_lint` (`plan_tool/cli/jira_cmd.py:177`) and the shared lint reporting (`lint_acceptance_criteria` and the aggregation at `:1840`) gain the two new soft-lint checks (missing UI-impact on backend/full-stack; missing/low-content test rec on frontend-impacting), so linting an existing export flags gaps without a backend call.

**Open questions to settle during `create`/`detail`:** layer vocabulary (lean to the four-value set, confirm `infra` isn't noise); block vs. soft-lint (lean soft-lint only, but wire severity so a future `--fail-on-findings` flip is cheap); deterministic vs. Claude inference (lean Claude-assigned for `ui_impact` and the test rec, with an optional deterministic pre-hint for `layer` from file paths); and `frontend_test_recommendation` shape (lean `list[str]` for renderer symmetry with `acceptance_criteria`).

## Out of scope

- **Any non-jira surface.** No change to plan authoring, detail, run, review, or completeness — this is the export leg only.
- **Actually running or generating tests.** The story carries a *recommendation*; it never scaffolds or executes a test.
- **A frontend/backend detector for the whole tool.** Layer designation lives on the exported story, derived per story; it is not a new plan-wide classifier.
- **Reworking epic assignment or story sizing.** The `--max-hours` ceiling, epic config, and step consolidation logic are untouched.

## Risks

- **Model over-tags `full_stack` / emits generic test recs.** Severity: output quality. Mitigation: a tight prompt with an example of a specific recommendation, plus a soft-lint that flags empty/low-content test recs (reuse the acceptance-criteria lint machinery).
- **Back-compat break on existing exports.** Severity: correctness on re-run / `--lint`. Mitigation: every new field is defaulted and optional; a legacy export with none of them parses to `unspecified` layer + empty notes and round-trips unchanged.
- **Doc/code drift.** Severity: contract. Mitigation: update `JIRA_FORMAT.md` and the JSON drift guard / `DATA_CONTRACT.md` in the same plan step that lands the schema change.

## Testing

Follow the project's unit-first convention, mirroring source to tests (`plan_tool/jira.py` → `tests/test_jira.py`; `plan_tool/cli/jira_cmd.py` → `tests/test_jira_cmd.py`). Unit tests should cover: parse of a full export with all three fields present; parse of a legacy export with none of them (verifying `unspecified` layer + empty notes defaults and a clean round-trip); both renderers (`format_markdown` and `format_json`) surfacing the fields, the deterministic title tag derivation for each `layer` value including `unspecified` → no tag, the JSON `title` staying clean, and the `_(none)_` UI-impact placeholder when empty; and each new soft-lint check firing and not firing (missing UI-impact on backend/full-stack; missing/low-content test rec on frontend-impacting). Keep the Claude seams stubbed via the invoker seam — no real `claude` spawn. All existing jira export/lint suites must still pass.

## Acceptance criteria

- `Story` carries `layer`, `ui_impact`, and `frontend_test_recommendation`, all defaulted; an export produced before this change still parses and re-runs without error.
- `parse_jira_response` (and the lint reader) validate `layer` against the enum, default a missing/invalid layer to `unspecified`, and never hard-reject on the new content fields.
- `format_markdown` and `format_json` both surface the three fields, with the UI-impact section rendering a placeholder when empty.
- The rendered markdown title carries a short layer tag (`[FE]`/`[BE]`/`[FE+BE]`/`[INFRA]`) right after the `[<id>] ` prefix, derived deterministically from `layer`; `unspecified` renders no tag. The tag is render-only — the stored `Story.title` and the JSON `title` stay clean, so re-parse / `--lint` round-trip the title unchanged (idempotent).
- The `jira.md` prompt asks for the layer, a UI-impact note (with `none` as an explicit valid answer), and — for frontend-impacting stories — a concrete what-and-how-to-test recommendation.
- `jira --lint` warns (soft-lint, not failure) on a backend/full-stack story missing a UI-impact note and on a frontend-impacting story missing a non-trivial test recommendation.
- `JIRA_FORMAT.md` (schema table + markdown/JSON samples + validation + soft-lint rows) and, if tracked, `DATA_CONTRACT.md` + its drift guard reflect the new fields.
- Tests cover: parse of a full export with all fields, parse of a legacy export with none (defaults + round-trip), both renderers, and each new soft-lint firing / not firing; Claude seams stay stubbed (invoker seam) — no real `claude` spawn.
- **Backlog reconciliation:** `BACKLOG.md` #104 is updated on completion (removed when shipped, or marked plan-authored while execution is pending), per CLAUDE.md.

## Deferred

- **Deterministic layer inference from `files:` paths** as the *primary* source (rather than an optional pre-hint) — revisit if Claude-assigned layers prove noisy in practice.
- **Per-story test-plan scaffolding** (emitting an actual test skeleton file per frontend-impacting story) — a separate, larger capability; this seed only produces a textual recommendation.
- **`--fail-on-findings` hard-block** on missing UI-impact / test recs — keep the new checks advisory in v1; flip severity later if a CI gate is wanted.
