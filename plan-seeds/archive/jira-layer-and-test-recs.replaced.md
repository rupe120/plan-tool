> **Replaced**: this file has been superseded by `docs/implementation-plans/2-jira-layer-and-test-recs.md`.
> Preserved here for history; do not edit.

# Plan seed: jira export layer designation + UI-impact note + frontend test recommendations

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/jira-layer-and-test-recs.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Source backlog entry:** `BACKLOG.md` **#104** (T5, export leg). The
> resulting plan MUST update `BACKLOG.md` on completion — remove #104 when the
> work ships, or mark it plan-authored while execution is pending, per CLAUDE.md's
> backlog-reconciliation rule. Put that bookkeeping in the plan's final
> docs/status step and its acceptance criteria.

---

## Overview

Enrich the `plan-tool jira` story export so every exported story declares which
**layer** it lands in — `frontend` / `backend` / `full-stack` / `infra` — and
carries two fields derived from that designation:

1. a **UI-impact note** on any backend/full-stack story (does this
   API/schema/behavior change surface a visible change the frontend must absorb,
   or is it UI-invisible — "none" is a first-class answer), and
2. a **what-and-how-to-test recommendation** for any story that impacts the
   frontend (a `frontend`/`full-stack` story, or a `backend` story whose
   UI-impact note is non-empty): which user-visible flows / components / states
   to cover, and at what level (unit component test, integration, visual/e2e).

On top of the structured fields, the export prepends a **short layer indicator to
the rendered story title** — a compact tag (e.g. `[FE]` / `[BE]` / `[FE+BE]` /
`[INFRA]`) at the front of the title — so FE vs BE stories are identifiable at a
glance when scanning a list of tickets, without reading the per-story `## Layer`
field.

The change is a single, well-bounded surface — the jira export leg — but touches
the `Story` schema, its parser, both renderers, the prompt template, validation,
the `--lint` path, and the docs.

## Problem statement — exported stories are layer-blind

The current `Story` record (`plan_tool/jira.py:457`, documented in
`JIRA_FORMAT.md` "Story schema") is layer-agnostic: `id`, `title`,
`description`, `acceptance_criteria`, `files`, `steps`, `depends_on`,
`estimate_hours`, `status`. Nothing tells a reviewer whether a story lands in the
UI, the service, or both — the reader has to infer it from `files` and prose.

Two signals get lost as a result:

- **Cross-layer coupling on backend work.** A backend story that changes an API
  shape or a validation rule often forces a visible frontend change, but the
  export never states it, so the UI follow-up is discovered late (or missed) at
  hand-off.
- **Testing on-ramp for UI work.** Frontend-facing changes are the surface most
  prone to under-testing, yet the story gives no guidance on *what* to test or at
  *which level* — `acceptance_criteria` says what "done" means, not how to prove
  it in the UI.

Making the layer explicit, forcing a UI-impact answer on backend stories, and
attaching a concrete test recommendation to frontend-impacting stories surfaces
all three at export time, in the artifact a tracker consumes.

## Design

### Schema — three additive fields on `Story`

Add to the `Story` dataclass (`plan_tool/jira.py`), all defaulted so existing
exports still parse (back-compat on re-run / `--lint`):

- `layer: str` — one of `frontend | backend | full_stack | infra`; default a
  sentinel (`unspecified`) when a legacy/older export omits it.
- `ui_impact: str` — prose; the downstream-UI-impact note. Empty means "not
  provided"; the literal `none`/`None` is a valid, meaningful value the prompt is
  told to emit when a backend change is UI-invisible.
- `frontend_test_recommendation: str` (or a `list[str]` of recommendations —
  settle in `detail`) — advisory; what-and-how-to-test guidance. Sits alongside
  `acceptance_criteria`, never replaces it.

Reflect the same fields in `DATA_CONTRACT.md` if the persisted jira JSON is
drift-tracked, and update the drift guard.

### Parser — read, validate, default

`parse_jira_response` (`plan_tool/jira.py:786`) and the lint-path reader
(`read_stories_for_lint` / the parse at `:1470`) learn the fields:

- `layer` must be in the enum when present; a missing/invalid value defaults to
  `unspecified` (do **not** hard-reject — additive/back-compat).
- When `layer` ∈ `{backend, full_stack}`, a **missing `ui_impact`** is a
  **soft-lint warning**, not a parse failure (mirror the acceptance-criteria lint
  posture, `lint_acceptance_criteria` at `:291`).
- When a story is **frontend-impacting** (layer `frontend`/`full_stack`, or
  `backend` with a non-empty, non-"none" `ui_impact`), a **missing/low-content
  `frontend_test_recommendation`** is a soft-lint warning.

Keep hard-blocking reserved for the crisp structural rules already enforced; the
new content requirements are advisory lints so a partial export still round-trips.

### Renderers — surface the fields

- **Title layer indicator (both renderers).** Prepend a short, fixed-width layer
  tag to the rendered title so FE vs BE is legible at a glance in a ticket list.
  The title is rendered today with a `[<id>] ` prefix (`JIRA_FORMAT.md` "Story
  schema" / `## Title`); the layer tag goes **right after** the id prefix, e.g.
  `[AUTH-S1] [BE] <title>`. Derive the tag deterministically from `layer`
  (`frontend → [FE]`, `backend → [BE]`, `full_stack → [FE+BE]`, `infra → [INFRA]`,
  `unspecified →` no tag). This is a **render-time decoration only** — do not bake
  the tag into the stored `Story.title`, so re-parse / re-run / `--lint` stay
  idempotent and the title round-trips unchanged. Settle the exact tag glyphs and
  whether `infra` shows a tag in `detail`.
- `format_markdown` (`:964`): apply the title tag above, plus add a `## Layer`
  line (or fold into the story header banner), a `## UI impact` section (rendered
  `_(none)_` when empty), and a `## Testing recommendation` section for
  frontend-impacting stories. Match the existing `_(no description)_` /
  `_(none specified)_` placeholder style.
- `format_json` (`:1077`): emit `layer`, `ui_impact`,
  `frontend_test_recommendation` keys alongside the existing story fields. Keep
  the JSON `title` **clean** (the layer tag is a markdown-render decoration, not a
  stored value); the JSON consumer reads `layer` directly.

Update `JIRA_FORMAT.md`: the schema table, the markdown + JSON samples, the
validation-rules section, and the soft-lint rows.

### Prompt — ask for the new fields

Extend `plan_tool/prompts/jira.md` so the one whole-plan Claude call assigns each
story its `layer`, writes the `ui_impact` note (explicitly instructing "state
`none` when a backend change is UI-invisible" so the field is never left
implicit), and — for frontend-impacting stories — a concrete, non-generic
testing recommendation naming flows/components and a test level. Tighten against
the "test it works" failure mode with an explicit instruction + example.

### Lint — extend `jira --lint`

`cmd_jira_lint` (`plan_tool/cli/jira_cmd.py:177`) and the shared lint reporting
(`lint_acceptance_criteria` and the aggregation at `:1840`) gain the two new
soft-lint checks (missing UI-impact on backend/full-stack; missing/low-content
test rec on frontend-impacting), so linting an existing export flags gaps without
a backend call.

## Open questions — settle during `create` / `detail`

- **Layer vocabulary.** Is `{frontend, backend, full_stack, infra}` the right
  closed set, or is `infra` noise (fold into backend)? Lean to the four-value set;
  confirm in `detail`.
- **Block vs. soft-lint.** Should missing UI-impact / test-rec ever hard-block
  under `--fail-on-findings`, or stay purely advisory? Lean **soft-lint only**,
  matching the acceptance-criteria posture — but wire severity so a future flip is
  cheap.
- **Deterministic vs. Claude inference.** Can `layer` be inferred
  deterministically from a step's `files:` / change types (e.g. paths under a
  `web/`/`ui/` tree → frontend), or is it Claude-assigned? Lean **Claude-assigned**
  for `ui_impact` and the test rec (judgment), with an *optional* deterministic
  pre-hint for `layer` from file paths if cheap.
- **`frontend_test_recommendation` shape** — single prose string vs. a bulleted
  `list[str]`. Lean list for renderer symmetry with `acceptance_criteria`.

## Out of scope

- **Any non-jira surface.** No change to plan authoring, detail, run, review, or
  completeness — this is the export leg only.
- **Actually running or generating tests.** The story carries a *recommendation*;
  it never scaffolds or executes a test.
- **A frontend/backend detector for the whole tool.** Layer designation lives on
  the exported story, derived per story; it is not a new plan-wide classifier.
- **Reworking epic assignment or story sizing.** The `--max-hours` ceiling, epic
  config, and step consolidation logic are untouched.

## Risks

- **Model over-tags `full_stack` / emits generic test recs.** Severity:
  output quality. Mitigation: a tight prompt with an example of a specific
  recommendation, plus a soft-lint that flags empty/low-content test recs
  (reuse the acceptance-criteria lint machinery).
- **Back-compat break on existing exports.** Severity: correctness on re-run /
  `--lint`. Mitigation: every new field is defaulted and optional; a legacy
  export with none of them parses to `unspecified` layer + empty notes and
  round-trips unchanged.
- **Doc/code drift.** Severity: contract. Mitigation: update `JIRA_FORMAT.md`
  and the JSON drift guard / `DATA_CONTRACT.md` in the same plan step that lands
  the schema change.

## Acceptance criteria

- `Story` carries `layer`, `ui_impact`, and `frontend_test_recommendation`, all
  defaulted; an export produced before this change still parses and re-runs
  without error.
- `parse_jira_response` (and the lint reader) validate `layer` against the enum,
  default a missing/invalid layer to `unspecified`, and never hard-reject on the
  new content fields.
- `format_markdown` and `format_json` both surface the three fields, with the
  UI-impact section rendering a placeholder when empty.
- The rendered markdown title carries a short layer tag (`[FE]`/`[BE]`/`[FE+BE]`/
  `[INFRA]`) right after the `[<id>] ` prefix, derived deterministically from
  `layer`; `unspecified` renders no tag. The tag is render-only — the stored
  `Story.title` and the JSON `title` stay clean, so re-parse / `--lint` round-trip
  the title unchanged (idempotent).
- The `jira.md` prompt asks for the layer, a UI-impact note (with `none` as an
  explicit valid answer), and — for frontend-impacting stories — a concrete
  what-and-how-to-test recommendation.
- `jira --lint` warns (soft-lint, not failure) on a backend/full-stack story
  missing a UI-impact note and on a frontend-impacting story missing a
  non-trivial test recommendation.
- `JIRA_FORMAT.md` (schema table + markdown/JSON samples + validation +
  soft-lint rows) and, if tracked, `DATA_CONTRACT.md` + its drift guard reflect
  the new fields.
- Tests cover: parse of a full export with all fields, parse of a legacy export
  with none (defaults + round-trip), both renderers, and each new soft-lint
  firing / not firing. Claude seams stay stubbed (invoker seam) — no real
  `claude` spawn.
- **Backlog reconciliation:** `BACKLOG.md` #104 is updated on completion
  (removed when shipped, or marked plan-authored while execution is pending),
  per CLAUDE.md.

## Deferred

- **Deterministic layer inference from `files:` paths** as the *primary* source
  (rather than an optional pre-hint) — revisit if Claude-assigned layers prove
  noisy in practice.
- **Per-story test-plan scaffolding** (emitting an actual test skeleton file per
  frontend-impacting story) — a separate, larger capability; this seed only
  produces a textual recommendation.
- **`--fail-on-findings` hard-block** on missing UI-impact / test recs — keep the
  new checks advisory in v1; flip severity later if a CI gate is wanted.
