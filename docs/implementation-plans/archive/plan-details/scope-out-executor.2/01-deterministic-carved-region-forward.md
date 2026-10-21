> **Auto-archived**: this plan was swept on 2026-06-25 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a deterministic carved-region forward-seed emitter in `plan_tool/scope_out.py`

## Summary

Adds the new leaf `plan_tool/scope_out.py` with one pure, deterministic function — `render_carved_seed(...)` — that serializes a single carved `schema.Step` (title, set of files, change type), its detail body as re-plan scope, its run state rendered as narrative prose that branches on status — a DONE carved step renders as done-context, a non-DONE (in-progress/CURRENT) one as attempted/partial context to account for, kept distinct from the "already implemented — do not re-plan" framing — and its captured upstream-dependency context into a `create --from-existing` forward-seed string. The function is a string builder only: **no file IO, no git, no Claude, no `invoker=` seam** — it mirrors `plan_tool/annotate_render.py:render_create_seed`'s design (path derivation, disk writes, and seed-path collision handling stay with the step-3 orchestrator). The key decisions are that the carved step's detail/frontmatter is work to re-plan, its run state is carried as narrative prose (`status` + `status_note`), never as a claimed live-status round-trip and never as a non-existent `progress` field, and upstream dependencies are split by status: DONE dependencies are assumed done-context, while non-DONE dependencies render as explicit external prerequisites. On green, `tests/test_scope_out.py` proves the emitter produces a valid carryover seed for a normal carved step, a bare (never-detailed) step, and upstream prerequisites in both statuses — all deterministically.

## Table of Contents

- [Why](#why) — what's missing today and why the emitter lands first
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files this step creates
- [Implementation](#implementation) — the `render_carved_seed` contract, its blocks, and the adapt-don't-reuse decision
- [Tests](#tests) — the unit cases added with the implementation and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — stdlib and pytest docs relevant to this step
- [Deferred](#deferred) — the narrow primitive, orchestrator, CLI, and disk concerns left for steps 2–5

## Why

- **The scope-out remedy has no actuator.** The convergence diagnostic recommends carving a spinning region out of a plan, but nothing emits the durable, re-plannable artifact the carve needs. This step builds the first half of that actuator: the deterministic renderer that turns a carved step into a `create --from-existing` forward-seed.
- **Build the pure renderer first so steps 2–4 compose it.** The narrow primitive (step 2), the seed-first orchestrator + safety gate (step 3), and the CLI (step 4) all depend on a settled emitter contract. Landing it as a side-effect-free string builder — the same shape as `plan_tool/annotate_render.py:render_create_seed` — keeps it trivially testable and lets step 3 own all disk writes, path derivation, and collision handling.
- **The run-state "carry" has a real mechanism subtlety.** `create --from-existing` re-decomposes into fresh `PENDING` steps and cannot round-trip a live `status`; `schema.Step` has **no `progress` field** (only `status: StepStatus` and the ephemeral `status_note`). Getting this right at the emitter — keeping carved detail/frontmatter in re-plan scope while carrying status/status_note as narrative prose that branches on status (DONE as done-context, non-DONE as attempted/partial context to account for, not the "already implemented — do not re-plan" framing), not a resume claim — is the most important correctness decision, so it belongs in this step's tests from the start.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/scope_out.py` — the new leaf; this step adds `render_carved_seed(...)` plus its private block helpers.
  - `tests/test_scope_out.py` — unit tests for the emitter (mirrors `plan_tool/scope_out.py` per the repo's `X.py → tests/test_X.py` rule).
- **Existing files (edits only):** none. This step is purely additive — no orchestrator, CLI, or convergence-diagnosis edits land here (those are steps 2–5).

## Implementation

### `plan_tool/scope_out.py` (new)

- **Module docstring** — state the leaf's contract in two lines: a deterministic string builder for the carved-region forward-seed; no file IO, no git, no Claude, no `invoker=`. Cite `plan_tool/annotate_render.py` as the sibling pattern. Keep it terse per the repo's comment rule.
- **Imports — keep the leaf minimal and cycle-free.**
  - `from __future__ import annotations`
  - stdlib only beyond schema: `from pathlib import Path`, `from collections.abc import Sequence`
  - `from plan_tool.schema import Step` — the only first-party import (the step's frozen-ish contract). **Do not** import `plan_tool.detail`, `plan_tool.create`, or `plan_tool.cli` — step-1's renderer needs none of them, and importing the heavy orchestrators would pull a large surface into what must stay a leaf. Step slug/path derivation (`plan_tool/detail.py:derive_step_slug`, `derive_detail_path`) is the orchestrator's concern in step 3, not the emitter's.

- **Public function — `render_carved_seed`.** Signature (keyword-only, mirroring `render_create_seed(annotation, *, report_path)`'s injected-path style):
  - `plan_title: str` — the source plan's title, woven into the seed's intro for human context.
  - `carved_step: Step` — the step being carved; the renderer reads `title`, `all_files` (the `files` + `creates` property on `plan_tool/schema.py:Step`, an ordered, de-duplicated `list[str]` — iterate it directly, never `set(all_files)`, so the deterministic-ordering guarantee holds), `change_type`, `status`, `status_note`, `depends_on`, `features` (carried into the seed as re-plan scope so the re-planned successor re-registers any tag the dropped step solely implemented — seed decision `carved-step-features-disposition`; step 2's narrow prunes the now-unimplemented registry entries), and `scope` (the carved step's `StepScope` — rendered as a disposition note so a `deferred`/`wont_do` carve is not re-planned as committed work; seed decision `carved-step-scope-disposition`).
  - `detail_body: str | None` — the carved step's detail-file markdown body, **passed in by the caller**, or `None` when no body is available. The emitter never reads it from disk.
  - `detail_missing: bool = False` — disambiguates the two `detail_body is None` cases the caller resolves. `False` means the step was **never detailed** (no `detail:` pointer); `True` means the step had a `detail:` pointer but its file was **absent** (moved/deleted/slug-drifted). The emitter renders a plain "never detailed / frontmatter only" note for the former and a **missing-detail warning** for the latter, so a lost carved body is reported rather than mislabeled as a step that was never detailed (seed decision `carved-detail-pointed-but-missing`). Ignored when `detail_body` is non-`None`.
  - `upstream_context: Sequence[tuple[int, str, str]] = ()` — `(step_id, title, status_value)` triples for the **surviving upstream** steps the carved step `depends_on`, resolved by the caller. Only entries whose `status_value == "done"` are captured as done-context so `create --from-existing` re-establishes that assumption; every other status renders as an explicit external prerequisite, not as already-done context (seed decision 3, outbound edge).
  - `source_path: Path` — the source plan file path, **injected not derived** (as `render_create_seed` injects `report_path`), used only for the provenance header via `str(source_path)`; no filesystem access.
  - Returns `str` — the full seed markdown, ready for the step-3 orchestrator to write under `plan-seeds/<plan>-carved-<slug>.md`.

- **Seed structure the function assembles** (build a `list[str]` of lines and `"\n".join(...)`, exactly as `render_create_seed` does):
  1. **Provenance comment header** — an HTML comment `<!-- plan-tool scope-out carved-seed`, with `source:` (the `source_path`) and `carved_step:` (the carved step id) lines, closed by `-->`. Mirrors `render_create_seed`'s `<!-- plan-tool annotate create-seed ... -->` block.
  2. **`# Plan seed: carved step <id> from <plan_title>`** — the top-level title.
  3. **Intro paragraph** — one sentence stating this is a `plan-tool create --from-existing` input that re-plans **only the carved region**, and that the "Done-context" section below is context, not work to re-plan (echoing `render_create_seed`'s intro wording so operators see a familiar contract).
  4. **`## Scope to re-plan`** — the carved step's `title`, its `all_files` set of files (one bullet per path, or a "no files declared" line when empty), its `change_type` (rendered as its value, or "unspecified" when `None`), its `features` tags (one bullet per tag, framed as features the re-plan must re-register since the drop leaves no implementer; omit the line when the step has no tags), and the `detail_body` when provided. When `detail_body is None`, branch on `detail_missing`: `False` emits a single line noting the carved step was never detailed and that the re-plan scope comes from the carved frontmatter only (seed wiring note `carved-step-missing-detail`); `True` emits an explicit **missing-detail warning** line stating the step's `detail:` pointer was set but its file was absent (moved/deleted/slug-drifted) so the original body could not be carried, and the re-plan scope falls back to the carved frontmatter only — the loss is reported, never silently rendered as "never detailed". Render the carved step's `scope` disposition here too: a `committed` step is ordinary re-plan scope (no extra note), while a `deferred`/`wont_do` step carries an explicit disposition note (e.g. "this step was parked as `<scope>` — re-plan only if intentionally resuming abandoned/deferred work") so `create --from-existing` does not silently resurrect parked work as committed and a `deferred` carve keeps its gated disposition (seed decision `carved-step-scope-disposition`). This section is the actual carved-region work for `create --from-existing` to decompose; do **not** mark it as already implemented done-context.
  5. **`## Done-context (already done — do not re-plan)`** — lead the section with an explicit **don't-re-plan framing line** that reproduces `render_create_seed`'s contract: a sentence telling the `create --from-existing` pass that everything in this section is *already implemented* done-context and must **not** be re-planned or re-implemented (echo `render_create_seed`'s "Already implemented (done-context — do not re-plan)" / "not to be re-planned" wording). This "already implemented — do not re-plan" framing is reserved for **genuinely-complete** context: DONE upstream assumptions and any explicitly known completed work the caller supplies later. The carved step's **own** run state does **not** go here when it is non-DONE: because the carved step is typically the spinning, often CURRENT (i.e. in-progress) step, its `status`/`status_note` render as **attempted/partial context to account for** — narrative prose naming `status` and, when present, the `status_note` text, framed as what was left half-done so the re-plan accounts for it, explicitly **not** as already-implemented done-context. Labeling a non-DONE carved step's partial `status_note` as done-context would risk the re-plan treating the half-built carved work as complete-and-skip; the carved step's detail/frontmatter therefore stays in `## Scope to re-plan` (it is work to re-plan) even when its status reads as in-progress. A DONE carved step's status may render plainly as done-context. Explicitly **do not** emit a `progress:` key or any field that implies a resumable live step — the prose says what state the step was left in, and the re-plan accounts for it.
  6. **`## Upstream prerequisites (assumed already done)`** — one bullet per DONE `upstream_context` entry (`- step <id>: <title>`), framed as done-context outputs the carved work assumed from earlier steps. **`## External prerequisites (not done yet)`** — one bullet per non-DONE upstream entry (`- step <id> [<status>]: <title>`), framed as dependencies the carved re-plan must wait on or coordinate with outside this seed. When either bucket is empty, **omit that section entirely** rather than emitting an empty heading (no dangling section).
  7. **`## Provenance`** — a bullet with the source plan path and the carved step id, mirroring `render_create_seed`'s provenance block.

- **Private helpers** — factor the scope, done-context, and upstream blocks into small private functions (e.g. `_scope_block(carved_step, detail_body, detail_missing) -> list[str]`, `_done_context_block(carved_step) -> list[str]`, and `_upstream_block(upstream_context) -> list[str]`) returning line lists, matching `annotate_render`'s `_carryover_entry` / `_done_context_bullet` decomposition. Keep each terse.

- **Foundational logic of this step:** *serialize a carved single-step subset into a deterministic `create --from-existing` seed string, carrying carved detail/frontmatter as re-plan scope and run state as prose.*
  - The one sibling that does whole-plan seed serialization is `plan_tool/annotate_render.py:render_create_seed`, which consumes a whole-plan `PlanAnnotation` (produced by a Claude pass in `plan_tool/annotate.py:classify_plan_implementation`) and is written beside the source.
  - That is the **wrong contract** for a deterministic single-step carve under `plan-seeds/`, so this step adapts the pattern rather than reusing the function (seed decision 8).
  - The two emitters stay separate by design — different inputs (whole-plan annotation vs one `Step` + body), different output homes.
  - Do **not** fold a shared-helper extraction across the two into this step; if a future reconcile wants to unify the done-context-block rendering, that is a behavior-preserving refactor `detail` cannot mint here — see Deferred.

## Tests

`tests/test_scope_out.py` (new). All cases are pure unit tests over `render_carved_seed` — no `invoker`, no `tmp_path` IO, construct `schema.Step` directly. No `@pytest.mark.integration` (the cross-module CLI wiring test arrives in step 4).

### Test-creation order (feature step)

This is a **feature** step. Author every test below **with** the implementation; each must be green before the step is considered finished (green-before-done gate).

- `test_scope_block_names_title_files_and_detail` — the returned seed contains the carved step's title, every entry of its `all_files` set, and the provided detail body under the `## Scope to re-plan` heading.
- `test_scope_block_renders_change_type` — a step with `change_type=ChangeType.FEATURE` shows `feature`; a step with `change_type=None` shows "unspecified" (no crash, no empty rendering).
- `test_scope_block_renders_feature_tags` — a step with `features=["foo", "bar"]` renders both tags under `## Scope to re-plan` as features the re-plan must re-register; a step with no tags omits the features line — guards `carved-step-features-disposition`.
- `test_scope_block_notes_non_committed_disposition` — a carved step with `scope=StepScope.WONT_DO` (and one with `StepScope.DEFERRED`) renders an explicit parked-disposition note under `## Scope to re-plan`, while a `committed` step renders no such note — guards `carved-step-scope-disposition` (parked/abandoned work is not re-planned as committed).
- `test_done_context_renders_status_as_prose` — a carved step with `status=StepStatus.CURRENT` and a `status_note` has both rendered as narrative text under `## Done-context`; asserts the note text is present.
- `test_done_context_emits_no_progress_field` — the rendered seed contains **no** `progress:` field/key and no "resume this in-progress step" claim — guards `progress-source-undefined` / `runstate-resume-overclaim`.
- `test_done_context_marks_context_as_done_not_to_replan` — the `## Done-context` section carries the explicit don't-re-plan framing (already-implemented done-context, not work-to-re-plan) while omitting the carved detail body.
- `test_detail_body_inlined_in_scope_when_present` — a non-empty `detail_body` string appears verbatim inside the scope-to-re-plan section.
- `test_bare_step_without_detail` — `detail_body=None` with `detail_missing=False` produces a valid seed with a "never detailed / frontmatter only" note in the scope-to-re-plan section and does not raise.
- `test_pointed_but_missing_detail_renders_warning` — `detail_body=None` with `detail_missing=True` produces a seed whose scope-to-re-plan section carries an explicit missing-detail warning (pointer set but file absent, body could not be carried) and does **not** render the "never detailed" note — guards `carved-detail-pointed-but-missing`.
- `test_done_upstream_prerequisites_rendered_as_assumed_done` — each `(id, title, "done")` in `upstream_context` appears as an assumed-done bullet under `## Upstream prerequisites`.
- `test_non_done_upstream_prerequisites_rendered_as_external` — each non-DONE upstream entry appears under `## External prerequisites (not done yet)` with its current status and does **not** appear under the assumed-done section.
- `test_no_upstream_sections_when_empty` — `upstream_context=()` omits both upstream headings entirely (no empty sections).
- `test_output_is_deterministic` — calling `render_carved_seed` twice with identical inputs returns identical strings; the file bullets preserve `all_files` list order (the renderer iterates the list directly, never `set(all_files)`), so the ordering is stable.
- `test_seed_is_create_from_existing_input` — the output starts with the provenance comment and includes the `create --from-existing` framing + the `# Plan seed:` title, so step 3 can write it straight to `plan-seeds/`.
- `test_provenance_records_source_and_step` — the `## Provenance` block names the injected `source_path` and the carved step id.

## Acceptance criteria

- `render_carved_seed(plan_title=..., carved_step=..., detail_body=..., upstream_context=..., source_path=...)` returns a `str` and takes **no** `invoker` argument and performs no file IO (signature inspection + behavior).
- The returned seed contains the carved step's `title`, every `all_files` path, its `change_type` (or "unspecified" when `None`), its `features` tags (as features the re-plan must re-register; line omitted when the step has none), and its detail body under `## Scope to re-plan`; that section is the carved-region work to re-plan, not already-implemented done-context.
- The carved step's `scope` is rendered in the seed: a `committed` step carries no disposition note, while a `deferred`/`wont_do` step carries an explicit parked-disposition note under `## Scope to re-plan` so `create --from-existing` does not silently resurrect parked/abandoned work as committed; an AC test asserts a `wont_do` carved step's seed carries that note and a `committed` one does not — guards `carved-step-scope-disposition`.
- The carved step's `status` and `status_note` are rendered as narrative prose; the output contains no `progress:` field and no live-resume claim. A non-DONE (e.g. IN_PROGRESS/CURRENT) carved step's status renders as attempted/partial context to account for — **not** under the "already implemented — do not re-plan" done-context framing — and its detail body remains in `## Scope to re-plan`; an AC test asserts an IN_PROGRESS carved step's body stays in re-plan scope and its partial `status_note` is not framed as already-implemented done-context.
- The `## Done-context` section reproduces `render_create_seed`'s "done-context — do not re-plan" framing for status/status_note, upstream assumptions, and explicitly known completed context only; an AC test asserts the don't-re-plan framing is present and the carved detail body is absent from this section.
- A non-empty `detail_body` is inlined in the re-plan scope; `detail_body=None` with `detail_missing=False` yields a valid seed with a "never detailed" note in the re-plan scope and does not raise; `detail_body=None` with `detail_missing=True` yields a missing-detail warning (pointer set, file absent, body uncarried) in the re-plan scope and does **not** emit the "never detailed" note.
- Each DONE `upstream_context` `(id, title, status)` triple renders as an assumed-done bullet; each non-DONE triple renders as an external prerequisite with its current status; an empty `upstream_context` omits both upstream sections entirely.
- `render_carved_seed` is deterministic — two calls with identical inputs return identical strings.
- `tests/test_scope_out.py` passes under `uv run pytest tests/test_scope_out.py -q`.

## References

- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path` is the type of the injected `source_path` provenance argument; the emitter only stringifies it (no filesystem calls), as `render_create_seed` does with `report_path`.
- [pytest — How to mark test functions with attributes](https://docs.pytest.org/en/stable/how-to/mark.html) — confirms this step's tests stay unmarked unit tests (no `@pytest.mark.integration` until the step-4 CLI wiring test).

## Deferred

- **The narrow primitive (drop-renumber + `depends_on` repair + detail migrate/archive + CURRENT cursor)** — step 2 (`depends_on: 1`). Step 1 only renders the seed; it mutates no plan structure.
- **The seed-first orchestrator, safety gate, and frozen `EscalateResult`-style return** — step 3. That step owns reading the carved step's detail body from disk, resolving `upstream_context` from the plan graph, deriving the `plan-seeds/<plan>-carved-<slug>.md` path, making it collision-safe (suffix/abort-on-exists), and writing the file. The emitter stays a pure string builder.
- **CLI wiring (`plan-tool scope-out <plan> --step N`)** — step 4.
- **Flipping the convergence scope-out recommendation to a runnable command** — step 5, in `plan_tool/convergence_diagnosis.py`.
- **Consolidating done-context rendering with `plan_tool/annotate_render.py:render_create_seed`** — left unconsolidated by design (different contracts: whole-plan `PlanAnnotation` vs one carved `Step` + body). A shared-helper extraction is a behavior-preserving refactor `detail` cannot mint inside this feature step; route it to reconcile if a future audit wants it.
