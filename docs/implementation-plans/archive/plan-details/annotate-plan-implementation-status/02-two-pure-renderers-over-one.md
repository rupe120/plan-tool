> **Auto-archived**: this plan was swept on 2026-06-15 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Two pure renderers over one `PlanAnnotation`: strictly-additive annotated report + compact carryover create-seed

## Summary

- Create `plan_tool/annotate_render.py` with **two pure functions** over step 1's `PlanAnnotation`: `render_annotated_report(annotation) -> str` (verbatim original + per-section status blocks + top-of-file coverage summary + provenance) and `render_create_seed(annotation, *, report_path) -> str` (compact carryover brief scoped to the NOT-IMPLEMENTED sections **plus the `remaining_work` of each PARTIAL**, with the IMPLEMENTED sections **and each PARTIAL's already-implemented half** as done-context).
- **Load-bearing decision:** both renderers are **pure string builders** — no file IO, no git, no Claude, no `invoker=` seam. They import only `PlanAnnotation`/`SectionAnnotation`/`AnnotationStatus` from `plan_tool/annotate.py` (step 1) plus stdlib. Path derivation, disk writes, and archiving all stay in step 3's CLI.
- **The additive guarantee is the central invariant:** the report inserts status blocks only as new `>`-prefixed lines *after* matching heading lines and prepends a summary/provenance header — it never edits, reorders, or drops an original line. Every line of `annotation.source_text` survives verbatim and in order.
- **The seed is rendered directly from the classification, never by distilling the report** — it walks the same `sections` tuple, partitioning by status, so there is no lossy second pass.
- On green: `render_annotated_report` round-trips every original line (difflib subsequence check passes) with correct status blocks and coverage counts; `render_create_seed` scopes carryover to the NOT-IMPLEMENTED sections plus each PARTIAL's `remaining_work` (never its already-implemented `code_refs`), routes the IMPLEMENTED sections and each PARTIAL's implemented half into done-context, and emits an original→report→seed provenance chain.

## Table of Contents

- [Why](#why) — what step 1 leaves unrendered and why two renderers, not one distill.
- [Files (creates vs edits)](#files-creates-vs-edits) — two new files, zero edits.
- [Implementation](#implementation) — the two public renderers, the additive insertion algorithm, provenance/lineage fields, and the private helpers.
- [Tests](#tests) — unit cases over hand-built `PlanAnnotation` fixtures, with creation order.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the step-relevant subset of the plan's links.
- [Deferred](#deferred) — CLI wiring, archiving, commit/state capture, distill no-op verification.

## Why

- **Step 1 produces a `PlanAnnotation` but renders nothing.** Its detail (`docs/implementation-plans/plan-details/annotate-plan-implementation-status/01-annotate-classification-core-ingest.md`) explicitly ships zero rendering and defers both renderers here. Without this step the classification is an in-memory dataclass no operator can read or feed forward.
- **The plan's two output artifacts must come from one classification, not two passes.** The plan's `## Architecture` mandates the seed be rendered *directly* from the per-section judgement, never by pushing the report through `plan_tool/create.py:propose_distilled_seed_from_claude` — that distiller is lossy by design and stays in `create`. Authoring both renderers as pure consumers of one `PlanAnnotation` is what designs out the round-trip-drift risk called out in the plan's `## Risks`.
- **The additive (lossless) property is easy to regress and only a renderer-level test catches it.** The plan flags this as a top risk; this step both establishes the renderer and locks the diff-original-against-report test that fails on any omission or rewording.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/annotate_render.py` — the two public renderers (`render_annotated_report`, `render_create_seed`) plus private helpers (`_coverage_summary`, `_status_block`, `_status_label`, `_format_code_refs`, `_insert_status_blocks`, `_normalize_heading`). Pure stdlib + step-1 imports.
  - `tests/test_annotate_render.py` — unit tests over hand-built `PlanAnnotation` fixtures (no invoker stub needed — the renderers never call Claude).
- **Existing files (edits only):** none. This step imports `PlanAnnotation`, `SectionAnnotation`, `AnnotationStatus` from `plan_tool/annotate.py` and adds no symbols to it.

## Implementation

### `plan_tool/annotate_render.py`

**Imports:**

- `from plan_tool.annotate import AnnotationStatus, PlanAnnotation, SectionAnnotation` (step 1's frozen contract).
- Stdlib only otherwise: `from pathlib import Path`, `from collections import Counter`. No `plan_tool.shell`, no `plan_tool.create`, no `invoker` — the renderers are deterministic and side-effect-free, so the autouse real-backend gate in `tests/conftest.py` is irrelevant here.

**Public renderer 1 — the annotated report (strictly additive):**

- `def render_annotated_report(annotation: PlanAnnotation) -> str:`
  - **Provenance/lineage header (prepended, machine + human readable):** an HTML-comment block recording the lineage `report → original`:
    ```
    <!-- plan-tool annotate report
    source: <annotation.source_path>
    repo_root: <annotation.repo_root>
    grounded_files: <len(annotation.grounded_files)>
    -->
    ```
    `source_path`/`repo_root`/`grounded_files` all come straight off `PlanAnnotation` (step 1 fields). This satisfies the plan's "report records the original's path" lineage requirement.
  - **Coverage summary (top-of-file, after the header):** one blockquote line built by `_coverage_summary(annotation.sections)` — e.g. `> **Coverage:** 3 IMPLEMENTED · 1 PARTIAL · 2 NOT-IMPLEMENTED · 1 low-confidence`. Counts via `Counter(s.status for s in annotation.sections)`; append the low-confidence tally only when `> 0`. **Terminal (fully-implemented) case:** when every section is IMPLEMENTED, append a `· 100% implemented` marker to the line so the all-done state is explicit (not merely inferable from `0 NOT-IMPLEMENTED`), satisfying the plan's "coverage summary reads 100% implemented" criterion.
  - **Body:** `_insert_status_blocks(annotation.source_text, annotation.sections)` — the verbatim original with one status block inserted after each matched heading. Return `header + "\n" + summary + "\n\n" + body`.
  - **The report intentionally ignores `remaining_work`.** It is the lossless audit, so a PARTIAL section renders its *whole* verdict (`status` + `evidence` + all `code_refs`) under its heading — the implemented/remaining split is a seed-scoping concern only. Do **not** "fix" the report to split a PARTIAL; only `render_create_seed` consumes `remaining_work`.
- `def _insert_status_blocks(source_text: str, sections) -> str:` — **the additive insertion algorithm, the load-bearing routine:**
  - **Partition `sections` into prose sections (`is_step` is `False`) and plan-step sections (`is_step` is `True`).** A plan-step section's `heading` is a frontmatter `title:` string that never appears as a markdown heading line, so it is anchored to the `## Steps` region (below), not heading-matched. Without this split every per-step verdict would miss `by_norm` and fall to the unmatched addendum, leaving the `## Steps` region bare — the exact contradiction the finding flagged against the Architecture's plan-input anchoring promise.
  - **Prose sections (heading-matched):** build `by_norm: dict[str, SectionAnnotation]` keyed by `_normalize_heading(s.heading)` over the prose sections only. Split `source_text` with `.splitlines()` (preserve every line). Walk lines in order; copy each line **unchanged** into the output. After copying a line, if `_normalize_heading(line)` hits an unmatched entry in `by_norm`, emit `_status_block(section)` lines and mark that heading consumed (first match wins — guards against a heading string recurring).
  - **Plan-step sections (`## Steps`-region anchoring):** while walking, detect the `## Steps` heading via `_normalize_heading(line) == "Steps"`; immediately after copying that line, emit each plan-step section's block in `sections` order (step 1's parser preserves frontmatter `steps:` order), each prefixed with a `> **<step title>**` label naming the step so the verdict is attributable even though the body has no per-step heading line. This places every per-step verdict inside the `## Steps` region — honoring the Architecture's "anchors per-step verdicts on the matching `## Steps`-region location" claim — instead of the addendum. If the source has no `## Steps` heading (a non-plan input, which should carry no `is_step` sections), any stray step section falls through to the unmatched addendum so it is never dropped.
  - **Never modify, reorder, or drop an original line** — the only writes are: pass-through of each original line, plus inserted `>`-prefixed block lines. This is what makes the difflib subsequence test pass.
  - **Unmatched sections:** any prose `SectionAnnotation` whose heading never appeared in `source_text` (and any step section when the source lacks a `## Steps` heading) gets its status block appended under a trailing `\n## Annotate — unmatched sections\n` addendum, so no verdict is silently lost. Additive (append-only), so the guarantee holds.
- `def _normalize_heading(line: str) -> str:` — `line.lstrip("#").strip()`. Tolerates whether step 1's parser captured the heading with or without its leading `#`/`##`/`###` markers (the prompt-emitted `heading` is "verbatim" but marker inclusion is not guaranteed). Matching on the marker-stripped text is robust to both.

**Public renderer 2 — the compact create-seed:**

- `def render_create_seed(annotation: PlanAnnotation, *, report_path: Path) -> str:`
  - **`report_path` is a required keyword** — the seed records the `seed → report` lineage, but the report's eventual on-disk path is a step-3 CLI decision, so it is injected, not derived here (keeps the renderer filesystem-agnostic).
  - **Partition `annotation.sections`, splitting each PARTIAL across both blocks.** This is the architecture's "PARTIAL sections are split, not carried whole" mandate (`docs/implementation-plans/2-annotate-plan-implementation-status.md` `## Architecture`) and the sole consumer of step 1's `SectionAnnotation.remaining_work` — without this split, `remaining_work` is an orphaned field and the next plan re-plans the already-done half of every PARTIAL.
    - **Carryover scope** = every `NOT_IMPLEMENTED` section (carried whole) **plus the `remaining_work` of every `PARTIAL` section** (its not-yet-implemented remainder only). A PARTIAL contributes *only* `remaining_work` here — its already-implemented `code_refs`/`evidence` are deliberately **excluded** from carryover so the next plan never re-scopes done work.
    - **Done-context** = every `IMPLEMENTED` section (carried whole) **plus the already-implemented half of every `PARTIAL` section** (its `code_refs` + `evidence`). This is what keeps a PARTIAL's done portion out of the carryover.
  - **Provenance header (HTML comment):** records both `source: <annotation.source_path>` and `report: <report_path>` — the full original → report → seed chain.
  - **Visible body shape** (a `create --from-existing` brief, mirroring the prose style of `plan-seeds/per-user-agent-cost-tracking.md`):
    - A `# Plan seed: carryover from <annotation.source_path.name>` title.
    - A one-paragraph "this is a `plan-tool create` input; it scopes only the remaining work; IMPLEMENTED items and the already-done half of PARTIAL items below are done-context, not to be re-planned" preamble that points at `report_path`.
    - `## Carryover scope (remaining work)` — one subsection per carryover entry:
      - For a `NOT_IMPLEMENTED` section: the original heading, a `[NOT-IMPLEMENTED]` tag, and the section's `evidence` (the whole section carries forward).
      - For a `PARTIAL` section: the original heading, a `[PARTIAL — remaining]` tag, and its **`remaining_work`** as the scoped work — **not** its implemented `code_refs` (those live in done-context). Add a one-line `(already-implemented portion below in Already implemented)` pointer so the author sees the split rather than assuming the whole section is open.
      - **Empty-`remaining_work` fallback:** a `PARTIAL` whose `remaining_work` is `""` (the model omitted the remainder) still carries forward — render its `evidence` as the scope and tag it `(remainder not pinned — verify scope before planning)` so nothing is silently dropped. This mirrors step 1's `low_confidence`-not-drop posture; never skip a PARTIAL just because `remaining_work` is empty.
      - **Terminal (empty-carryover) case:** when no section is NOT-IMPLEMENTED and no PARTIAL contributes any remainder — i.e. every section classifies IMPLEMENTED, so carryover is empty — render the `## Carryover scope (remaining work)` heading with an explicit marker line `No remaining work — every section is implemented.` rather than a bare empty heading, so feeding the seed to `create --from-existing` is a defined no-op rather than undefined input (the plan's fully-implemented-terminal-case criterion).
      - Append `(low confidence — verify before planning)` when `section.low_confidence`. A PARTIAL carries a single `low_confidence` flag while it is split across both blocks — surface the flag in *both* halves (the carryover entry and the done-context bullet), since both halves of an uncertain verdict warrant author review.
    - `## Already implemented (done-context — do not re-plan)` — one bullet per done-context entry:
      - For an `IMPLEMENTED` section: `<heading> — <code_refs>`.
      - For a `PARTIAL` section: `<heading> (partial — done half) — <code_refs>`, rendering its implemented `code_refs` via `_format_code_refs` so the next plan treats that portion as done-context, not work.
      - A low-confidence entry stays here tagged `(low confidence)` so the author can decide rather than having it dropped or re-planned.
    - `## Provenance` — bullets: `Original: <source_path>`, `Report: <report_path>`.
  - Return the assembled string. **No distill, no `create.py` call** — the seed is the direct render.

**Private formatting helpers:**

- `def _status_label(status: AnnotationStatus) -> str:` — display form: `IMPLEMENTED`/`PARTIAL`/`NOT IMPLEMENTED` (render the wire `NOT-IMPLEMENTED` with a space for the human-facing block, matching the plan's `## Architecture` examples).
- `def _status_block(section: SectionAnnotation) -> str:` — one blockquote line: `> **{label}** — {evidence}{refs_suffix}{low_conf_suffix}` where `refs_suffix` is ` (` + `_format_code_refs(section.code_refs)` + `)` when refs are present, and `low_conf_suffix` is ` _(low confidence)_` when `section.low_confidence`. Mirrors the plan's `> **IMPLEMENTED** — …` / `> **PARTIAL** — …` / `> **NOT IMPLEMENTED** — …` shapes.
- `def _format_code_refs(refs: tuple[str, ...]) -> str:` — backtick-wrap each ref and join with `, `; return `""` for an empty tuple.
- `def _coverage_summary(sections) -> str:` — the top-of-file counts line described above.

**Status comparison:** `AnnotationStatus` subclasses `str` (step 1), so partition by direct member comparison (`s.status == AnnotationStatus.IMPLEMENTED`) — no `.value` needed.

**Foundational logic — status-to-display mapping and carryover partitioning:**

- This is the single place that turns a `SectionAnnotation.status` into operator-facing prose.
- The only sibling that renders a code-vs-spec verdict to text is `plan_tool/launcher.py:verify_plan` (the `reconcile-plan --rollup` rollup), but it judges per parsed `Plan` step and emits a pass/warn/fail rollup, not an additive annotation.
- Step 1 already established the two judgement seams stay separate; that separation extends to rendering — do **not** route either renderer through `verify_plan`'s output formatting.
- No shared rendering helper exists to consolidate; keep both renderers self-contained here.

## Tests

All tests live in `tests/test_annotate_render.py` and run over **hand-built `PlanAnnotation` fixtures** — construct `PlanAnnotation(source_path=…, source_text=…, repo_root=…, grounded_files=…, sections=(SectionAnnotation(...), …))` directly. No invoker stub, no `@pytest.mark.allow_real_claude`, no `main([...])` (those are step 3's integration concern).

### Test-creation order (feature step)

Author these unit tests **with** the implementation; each must be green before the step is done.

- `test_report_preserves_every_original_line` — the additive guarantee: every line of `source_text.splitlines()` appears, in order, as a subsequence of `render_annotated_report(...).splitlines()` (use `difflib.SequenceMatcher` or an in-order membership walk). Fails on any omission or rewording.
- `test_report_inserts_status_block_under_each_heading` — for a source with three headings, the rendered report has each matching `> **STATUS** — …` block immediately after its heading line.
- `test_report_status_block_renders_evidence_and_refs` — an IMPLEMENTED section's block contains its `evidence` text and backtick-wrapped `code_refs`.
- `test_report_not_implemented_label_has_space` — a NOT_IMPLEMENTED section renders `NOT IMPLEMENTED` (display) in its block, not the wire `NOT-IMPLEMENTED`.
- `test_report_coverage_summary_counts` — the top-of-file summary reports the correct IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED counts.
- `test_report_low_confidence_marked` — a section with `low_confidence=True` adds the `_(low confidence)_` marker to its block and increments the summary's low-confidence tally.
- `test_report_unmatched_section_appended` — a prose `SectionAnnotation` whose heading is absent from `source_text` still has its verdict rendered in the trailing unmatched-sections addendum, and no original line is lost.
- `test_report_plan_step_verdicts_anchored_in_steps_region` — for a plan-style `source_text` containing a `## Steps` heading and step sections (`is_step=True`) whose headings are YAML `title:` strings absent from the body, each per-step status block (labeled with its step title) renders inside the `## Steps` region (after the `## Steps` heading) and **not** in the unmatched-sections addendum (the anchoring contract the finding flagged).
- `test_report_header_records_source_and_repo_root` — the provenance comment contains `annotation.source_path` and `annotation.repo_root`.
- `test_seed_carryover_scope_is_remaining_work_and_not_implemented` — the seed's carryover section lists every NOT_IMPLEMENTED heading and every PARTIAL heading, and excludes IMPLEMENTED ones.
- `test_seed_partial_scopes_remaining_work_not_implemented_refs` — for a PARTIAL section with `remaining_work="resolver in step 6 still missing"` and `code_refs=("schema.py:Table",)`, the carryover entry contains the `remaining_work` text and does **not** contain `schema.py:Table`; that ref appears only under done-context. (Locks the `remaining_work`-is-consumed contract — the exact gap Finding 1 flagged.)
- `test_seed_partial_implemented_half_in_done_context` — a PARTIAL section's `code_refs` appear under the done-context block tagged as the done half, so the implemented portion is carried as done-context, never promoted into carryover scope.
- `test_seed_partial_empty_remaining_work_falls_back_to_evidence` — a PARTIAL with `remaining_work=""` still appears in carryover scope (rendering its `evidence`, tagged remainder-not-pinned) and is never silently dropped.
- `test_seed_done_context_lists_implemented` — IMPLEMENTED headings appear under the done-context block with their code refs, and never in carryover scope.
- `test_seed_records_report_and_source_provenance` — the seed's provenance reflects both the injected `report_path` and `annotation.source_path` (the original → report → seed chain).
- `test_seed_low_confidence_implemented_flagged_not_replanned` — a low-confidence IMPLEMENTED section stays in done-context with a `(low confidence)` tag and is not promoted into carryover scope.
- `test_seed_low_confidence_partial_flagged_in_both_halves` — a low-confidence PARTIAL surfaces the low-confidence tag in both its carryover entry and its done-context bullet (the single flag applies to both halves of the split).
- `test_seed_single_synthesized_section_partial_splits` — a one-section annotation whose heading is the synthesized filename (the heading-less rough-notes case from step 1) classified PARTIAL still splits: its `remaining_work` lands in carryover and its `code_refs` in done-context, confirming the split is not heading-shape dependent.
- `test_seed_all_implemented_renders_empty_carryover_marker` — an annotation whose every section is IMPLEMENTED (empty carryover) renders the `## Carryover scope (remaining work)` heading followed by the `No remaining work — every section is implemented.` marker line, not a bare heading (the terminal-case `create --from-existing` no-op contract).
- `test_report_all_implemented_coverage_100` — an annotation whose every section is IMPLEMENTED renders the coverage summary with the `100% implemented` marker.
- `test_renderers_are_pure_no_side_effects` — calling either renderer twice on the same annotation yields byte-identical output and touches no filesystem (deterministic-purity guard).

**Green-before-done gate:** all of the above pass under `uv run pytest -m "not integration" tests/test_annotate_render.py -q` before this step is considered finished.

## Acceptance criteria

- `render_annotated_report(annotation)` output contains every line of `annotation.source_text` verbatim and in order (difflib subsequence check passes); status blocks are inserted only as added lines.
- Each judged prose section's status block appears under its matching heading, rendering status label, `evidence`, and `code_refs`; a `low_confidence` section is visibly marked.
- Each plan-step section (`is_step=True`, whose heading is a YAML `title:` with no body heading line) has its labeled status block rendered inside the `## Steps` region in frontmatter order, not in the unmatched-sections addendum.
- The report's top-of-file coverage summary reports correct per-status counts; when every section is IMPLEMENTED it appends a `100% implemented` marker; the provenance header records `source_path` and `repo_root`.
- `render_create_seed(annotation, report_path=…)` scopes carryover to every NOT-IMPLEMENTED section (whole) plus only the `remaining_work` of every PARTIAL section, while the done-context block carries every IMPLEMENTED section and the already-implemented half (`code_refs`/`evidence`) of every PARTIAL section — so a PARTIAL's done portion is never re-planned and `SectionAnnotation.remaining_work` is consumed, not orphaned (a PARTIAL with empty `remaining_work` still surfaces in carryover via its `evidence`, tagged remainder-not-pinned). When carryover is empty (every section IMPLEMENTED), the `## Carryover scope` heading carries the explicit `No remaining work — every section is implemented.` marker rather than a bare heading. Provenance records both the original and the report path.
- Neither renderer imports `plan_tool.shell`, calls `propose_distilled_seed_from_claude`, performs file IO, or spawns the backend; both are deterministic over their inputs.
- `tests/test_annotate_render.py` passes under `-m "not integration"`.

## References

- [difflib — Helpers for computing deltas — Python docs](https://docs.python.org/3/library/difflib.html) — `SequenceMatcher` primitives for the additive-guarantee test that diffs original lines against the report and fails on any omission.
- [pathlib — Object-oriented filesystem paths — Python docs](https://docs.python.org/3/library/pathlib.html) — `Path.name`/string forms for rendering `source_path`/`report_path` provenance lines (the renderers take `Path`s but never touch disk).
- [string — Common string operations — Python docs](https://docs.python.org/3/library/string.html) — `str.splitlines`/`str.lstrip` semantics underpinning verbatim line walking and `_normalize_heading`.
- [collections — Container datatypes (Counter) — Python docs](https://docs.python.org/3/library/collections.html#collections.Counter) — `Counter` for the coverage-summary status tally.

## Deferred

- **CLI wiring, path derivation, and disk writes** — step 3 (`plan_tool/cli/annotate_cmd.py`). It derives `<name>.annotated.md` / `<name>.seed.md`, calls these two renderers, and writes the files; the renderers stay filesystem-agnostic and return strings.
- **`--archive` preservation/lineage** via `plan_tool/create.py:archive_existing_source` — step 3. The renderers never mutate the original.
- **Compared commit/state capture in the report header** — the plan's "if resolvable, the compared commit/state" is a git read a pure renderer cannot do; route the git-state lookup to step 3's CLI (or a follow-up) and pass it in. The renderer records `repo_root` + grounded-file count as the available state proxy.
- **Distill no-op verification** (`plan_tool/create.py:propose_distilled_seed_from_claude` acting as a no-op on the compact seed) — exercised in step 3's `create --from-existing` integration test, not here. This step only guarantees the seed is rendered directly, never distilled inside `annotate`.
- **Consolidating verdict rendering with `plan_tool/launcher.py:verify_plan`** — a shared "render a code-vs-spec verdict" helper would be a refactor `detail` cannot mint; the two seams stay separate, consistent with step 1's deferral of the judgement-engine consolidation.
