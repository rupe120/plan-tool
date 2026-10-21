> **Replaced**: this file has been superseded by `docs/implementation-plans/2-annotate-plan-implementation-status.md`.
> Preserved here for history; do not edit.

## Overview

Add a `plan-tool annotate <plan-file>` command that ingests an existing implementation-plan (or rough-notes) file, compares it against the current codebase, and emits two artifacts from one ingestion and one comparison: the **annotated report** (`<name>.annotated.md`) — the original preserved verbatim with per-section status blocks (IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED plus concrete code references) and a top-of-file coverage summary, never distilled — and the **create seed** (`<name>.seed.md`) — a compact, create-ready brief scoped to the carryover (NOT-IMPLEMENTED / PARTIAL) work, with IMPLEMENTED items carried as done-context so they aren't re-planned. The seed is a second renderer over the same classification result, not a distill pass over the report, so `create --from-existing <name>.seed.md` produces the next plan. Read-only by default; `--archive` is the only opt-in mutation of the original. Implements BACKLOG.md item #47.

## Problem statement

Starting the next iteration from an old implementation plan plus the current codebase is manual today: there is no command that judges what an existing plan already got implemented (and how) versus what still carries forward, and renders a clean create-ready brief for the remaining work. `reconcile-plan --rollup` mutates a live plan to match code and emits a pass/warn/fail rollup — it does not produce a forward-seed or an additive, lossless audit trail. Authors need a forward path: original plan → annotated report → create seed → next plan, without losing any information from the original or re-planning already-done work.

## Architecture

`annotate` is composed from verified existing anchors rather than duplicating them:

- **Ingestion reuses the `--from-existing` reader.** `read_existing_description(path)` (`plan_tool/create.py:482`) reads any file in full as prose with no canonical-format requirement and no size limit. This is the single reader `annotate` reuses, which is why no new tolerant parser is needed. Only the *reader* is reused — the lossy distill output step is not.
- **Code-grounding helpers.** `extract_file_path_candidates` (`create.py:456`) + `find_umbrella_root` (`locator.py`) pull file references out of the ingested prose and resolve the owning repo, deciding which code to compare the plan against.
- **Comparison engine reused.** `verify_plan` (`plan_tool/launcher.py:2425`) — the `reconcile-plan --rollup` engine — already judges per-step whether code satisfies a spec. `annotate` reuses that judgement style for the "implemented and how" determination; it adds no second comparison engine. The difference is purely the output: additive markdown annotations + a create-ready seed, not plan/detail mutations or a rollup.
- **Two renderers over one classification.** The report renderer copies original content through verbatim and inserts a status block under each meaningful section (e.g. `> **IMPLEMENTED** — `plan_tool/foo.py:120-160` (`do_thing`); matches the spec.`, `> **PARTIAL** — table exists (`schema.py:40`) but the resolver in step 6 is missing.`, `> **NOT IMPLEMENTED** — no code found; carries into the next plan.`) plus a top-of-file coverage summary. The seed renderer renders directly from the same per-section judgement: carryover scope + a short IMPLEMENTED done-context block + a pointer to the report. The seed is never produced by distilling the report.
- **Distill stays a downstream no-op.** `propose_distilled_seed_from_claude` (`create.py:2827`) is lossy by design and remains where it lives, in `create`. `annotate` routes neither artifact through it; the compact seed passes through `create`'s distill gate as a no-op later, and a genuinely multi-effort carryover surfaces `create`'s split proposal at that point.
- **Preservation + lineage.** `archive_existing_source` (`create.py:514`) already moves a superseded source into `archive/` and prepends a one-line successor notice; `annotate` reuses (or mirrors) it for `--archive`. Provenance is explicit on disk and chained: original → report → seed → next plan. The report records the original's path (and, if resolvable, the compared commit/state); the seed records the report's path; the archived original records the report's path.
- **CLI layering.** A thin new `cli/` handler wires args (`<plan-file>`, `--output-dir` / `--report` / `--seed`, `--archive`, the iterate flags) to a new top-level orchestrator. The Claude seam defaults to the real shell invoker and must be overridable in tests per the invoker-seam rule. Discovery stays scoped to the cwd's git tree per `locator.py`.

## Out of scope

- **No new file parser** — ingestion reuses `read_existing_description`; the file never has to be valid plan frontmatter.
- **No new comparison engine** — the implemented-vs-spec judgement reuses the `verify_plan` (`reconcile-plan --rollup`) style.
- **No distilling either artifact inside `annotate`** — the seed is rendered directly from the classification; the distill gate stays in `create` and acts as a no-op on the already-compact seed.
- **No in-place mutation of the original** beyond the opt-in `--archive` move (which preserves it with a lineage notice).
- **No manifest registration** — `annotate` produces a report and a seed file, not a registered plan; registration happens when the author runs `create` on the seed.
- **No portfolio/multi-plan sweep** — one plan file per invocation; per-plan `reconcile-plan --rollup` remains the live-plan progress view.
- **No cross-project enumeration** — discovery stays scoped to the cwd's git tree per `locator.py`.

## Risks

- **Annotation accuracy depends on complete code-grounding.** If `extract_file_path_candidates` under-resolves the relevant files, sections may be misclassified NOT-IMPLEMENTED. Severity: correctness of the audit. Mitigation: allow the comparison to widen to the resolved repo root, and mark low-confidence classifications explicitly rather than asserting them.
- **Round-trip drift — largely designed out.** Because the seed is rendered compact directly (not the report pushed through distill), there is no lossy second pass to mangle annotations. Residual risk: the seed renderer itself drops a carryover item. Mitigation: render the seed from the structured classification and test the round-trip explicitly; `create`'s distill should be a no-op on it.
- **Additive guarantee is easy to regress.** A report-renderer change could silently drop original content. Severity: violates the lossless property. Mitigation: a test that diffs original lines against the report and fails on any omission.
- **Overlap with `reconcile-plan`.** `reconcile` mutates a live plan to match code; `annotate` produces a forward-seed and never mutates the source plan. Mitigation: keep the intents distinct in docs so users pick the right verb (live plan upkeep → reconcile; start the next iteration from an old plan + current code → annotate).

## Testing

Follow the project's unit-first convention (`TESTING.md`); mirror source modules (`plan_tool/X.py` → `tests/test_X.py`) and neutralize every Claude seam per TESTING.md — override the orchestrator's `invoker=`/`claude_invoker=` default so no test spawns the real backend (the autouse gate in `tests/conftest.py` raises otherwise).

Unit tests:
- Report renderer is strictly additive — original content fully preserved and never distilled (diff original lines against the report; fail on any omission or rewording).
- Seed renderer emits the carryover scope (NOT-IMPLEMENTED / PARTIAL) plus an IMPLEMENTED done-context block and a pointer to the report.
- Classification mapping — IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED with concrete `file:line` / symbol references for implemented and partial cases.
- Provenance fields present on both files (report → original, seed → report).

Integration tests (`@pytest.mark.integration`, driving `main(["annotate", ...])`): over a temp plan + fixture code where some steps are implemented and some aren't, assert the report's status blocks are correct; then feed `<name>.seed.md` to `create --from-existing` (invoker stubbed) and assert the new plan's scope is the carryover set and IMPLEMENTED items are carried as done-context, not re-planned. Existing `create` / `verify_plan` / reconcile suites must still pass; run the integration tests that exercise the from-existing reader and the `verify_plan` comparison when modifying those source files.

## Acceptance criteria

- `plan-tool annotate <plan-file>` writes a report (`<name>.annotated.md`) whose every original line is present verbatim, with section status blocks added and a top-of-file coverage summary, plus a seed (`<name>.seed.md`).
- For a fixture where some steps are implemented in the repo and some are not, each section is classified IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED with a concrete code reference for the implemented and partial cases.
- `plan-tool create --from-existing <name>.seed.md` accepts the seed and produces a plan whose scope is the carryover (NOT-IMPLEMENTED / PARTIAL) items; IMPLEMENTED items are carried as done-context, not re-planned. The seed passes through `create`'s distill gate as a no-op (never distilled inside `annotate`).
- With `--archive`, the original is moved and annotated with a notice pointing at the report; without it the original is untouched.
- Provenance chains: report → original, seed → report; no information from the original is lost.
- Every Claude seam is overridden in tests; no test spawns the real backend.
