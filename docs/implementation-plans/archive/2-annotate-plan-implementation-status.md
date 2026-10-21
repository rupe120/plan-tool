> **Auto-archived**: this plan was swept on 2026-06-15 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Annotate Plan Implementation Status
status: completed
priority: medium
steps:
- id: 1
  title: 'Add annotate classification core: ingest existing plan via read_existing_description,
    code-ground via extract_file_path_candidates/find_umbrella_root, classify sections
    IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED with a new Claude prompt'
  creates:
  - plan_tool/annotate.py
  - plan_tool/prompts/annotate.md
  - tests/test_annotate.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/annotate-plan-implementation-status/01-annotate-classification-core-ingest.md
  status: done
- id: 2
  title: 'Add two pure renderers over the one classification result: strictly-additive
    annotated report (verbatim original + per-section status blocks + coverage summary)
    and compact carryover create-seed, both carrying provenance/lineage fields'
  creates:
  - plan_tool/annotate_render.py
  - tests/test_annotate_render.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/annotate-plan-implementation-status/02-two-pure-renderers-over-one.md
  status: done
- id: 3
  title: 'Wire `plan-tool annotate` CLI handler: register subparser + dispatch, --output-dir/--report/--seed/--archive
    (reusing archive_existing_source), default the Claude seam to the real shell invoker,
    and regenerate the --help golden'
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - tests/cli/package_surface_help.golden.txt
  - tests/test_cli.py
  creates:
  - plan_tool/cli/annotate_cmd.py
  - tests/cli/test_annotate_cmd.py
  complexity: high
  change_type: feature
  gate:
  - uv run plan-tool annotate --help
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/annotate-plan-implementation-status/03-wire-plan-tool-annotate-cli-handler.md
  status: done
- id: 4
  title: 'Document `annotate` (RUNBOOK quick-ref row + per-flag bullets, README synopsis,
    CLAUDE.md pipeline note, mark BACKLOG #47 done) and contrast its forward-seed
    intent with reconcile-plan''s live-plan mutation'
  files:
  - RUNBOOK.md
  - README.md
  - BACKLOG.md
  - CLAUDE.md
  - integrations/claude/SKILL.md
  complexity: low
  change_type: non-code
  gate:
  - grep -q 'plan-tool annotate' RUNBOOK.md
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/annotate-plan-implementation-status/04-document-annotate-runbook-quick-ref-row.md
  status: done
---
# Annotate Plan Implementation Status

## Overview

Add a `plan-tool annotate <plan-file>` command that ingests an existing implementation-plan (or rough-notes) file, compares it against the current codebase, and emits two artifacts from one ingestion and one comparison: the **annotated report** (`<name>.annotated.md`) — the original preserved verbatim with per-section status blocks (IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED plus concrete code references) and a top-of-file coverage summary, never distilled — and the **create seed** (`<name>.seed.md`) — a compact, create-ready brief scoped to the carryover work (every NOT-IMPLEMENTED item whole, plus only the not-yet-implemented remainder of each PARTIAL item), with IMPLEMENTED items and the already-implemented half of each PARTIAL carried as done-context so they aren't re-planned. The seed is a second renderer over the same classification result, not a distill pass over the report, so `create --from-existing <name>.seed.md` produces the next plan. Read-only by default; `--archive` is the only opt-in mutation of the original. Implements BACKLOG.md item #47.

## Problem statement

Starting the next iteration from an old implementation plan plus the current codebase is manual today: there is no command that judges what an existing plan already got implemented (and how) versus what still carries forward, and renders a clean create-ready brief for the remaining work. `reconcile-plan --rollup` mutates a live plan to match code and emits a pass/warn/fail rollup — it does not produce a forward-seed or an additive, lossless audit trail. Authors need a forward path: original plan → annotated report → create seed → next plan, without losing any information from the original or re-planning already-done work.

## Architecture

`annotate` is composed from verified existing anchors rather than duplicating them:

- **Ingestion reuses the `--from-existing` reader.** `read_existing_description(path)` (`plan_tool/create.py:482`) reads any file in full as prose with no canonical-format requirement and no size limit. This is the single reader `annotate` reuses, which is why no new tolerant parser is needed. Only the *reader* is reused — the lossy distill output step is not.
- **Code-grounding helpers.** `extract_file_path_candidates` (`create.py:456`) + `find_umbrella_root` (`locator.py`) pull file references out of the ingested prose and resolve the owning repo, deciding which code to compare the plan against.
- **New judgement seam modeled on `verify_plan`'s style.** `verify_plan` (`plan_tool/launcher.py:2425`) — the `reconcile-plan --rollup` engine — already judges per-step whether code satisfies a spec, but it judges per parsed `Plan` step and cannot be called on free-form prose. `annotate` authors its own section-level judgement seam (`annotate.md` prompt + parser) modeled on that style for the "implemented and how" determination, rather than reusing the engine. The difference is purely the output: additive markdown annotations + a create-ready seed, not plan/detail mutations or a rollup.
- **Plan-tool plans: frontmatter `steps:` are the classifiable units, not the `## Steps` prose.** A plan-tool plan's substantive spec lives in YAML `steps:` (each entry's `title:`/`detail:`), while its `## Steps` body is a placeholder (literally "See the `steps:` block in the frontmatter"). The classifier must therefore treat each frontmatter `steps:` entry as a classifiable section — the `title:` is the section heading and the `detail:` file (when present) is its spec body — instead of judging only the `Overview`/`Architecture`/`Risks` prose and emitting a contentless NOT-IMPLEMENTED verdict for the placeholder `## Steps`. The grounding/ingestion seam parses frontmatter when the input is a valid plan file and feeds each step entry to the prompt as its own unit; for a non-plan or rough-notes input (no parseable `steps:`), it falls back to markdown-section units (heading-less input → one synthesized section). Step 2's report renderer anchors per-step verdicts on the matching `## Steps`-region location for plan inputs, so a step verdict whose heading is a quoted YAML `title:` does not get dumped to the unmatched-sections addendum.
- **Two renderers over one classification.** The report renderer copies original content through verbatim and inserts a status block under each meaningful section (e.g. `> **IMPLEMENTED** — `plan_tool/foo.py:120-160` (`do_thing`); matches the spec.`, `> **PARTIAL** — table exists (`schema.py:40`) but the resolver in step 6 is missing.`, `> **NOT IMPLEMENTED** — no code found; carries into the next plan.`) plus a top-of-file coverage summary. The seed renderer renders directly from the same per-section judgement: carryover scope + a short done-context block + a pointer to the report. PARTIAL sections are split, not carried whole — their implemented portion (code refs + evidence) joins the done-context block, and only the not-yet-implemented remainder enters the carryover scope, so the next plan never re-plans the already-done half. The seed is never produced by distilling the report.
- **Distill stays a downstream no-op — via `--no-distill`, not compactness.** `propose_distilled_seed_from_claude` (`create.py:2827`) is lossy by design and remains where it lives, in `create`. `annotate` routes neither artifact through it. The no-op is *not* automatic: `create` skips distill only when the seed already covers every canonical body section (`Overview`/`Problem statement`/`Architecture`/…) and is under the size threshold, and the seed's body (`Carryover scope`/`Already implemented`/`Provenance`) does not satisfy that skip condition — so the documented handoff is `create --from-existing <name>.seed.md --no-distill`, which feeds the raw seed straight through unchanged. Note that split detection lives *inside* distill (`create.py:create_plan` returns the `SplitProposal` only from the `if distill and raw_seed is not None:` block), so `--no-distill` disables split detection too — a genuinely multi-effort carryover gets no split proposal on this handoff. When the carryover spans multiple efforts, the operator drops `--no-distill` and accepts distill (which restores split detection at the cost of the lossy pass) rather than relying on a split that cannot fire under `--no-distill`.
- **Preservation + lineage.** `archive_existing_source` (`create.py:514`) already moves a superseded source into `archive/` and prepends a one-line successor notice; `annotate` reuses (or mirrors) it for `--archive`. Provenance is explicit on disk for the two links annotate writes: the report records the original's path (report → original) and the seed records the report's path (seed → report); the archived original records the report's path. The seed → next-plan hop is not persisted — `create --from-existing <seed>` writes no provenance frontmatter today — so the on-disk chain stops at the seed.
- **CLI layering.** A thin new `cli/` handler wires args (`<plan-file>`, `--output-dir` / `--report` / `--seed`, `--archive`) to a new top-level orchestrator. The Claude seam defaults to the real shell invoker and must be overridable in tests per the invoker-seam rule. Discovery stays scoped to the cwd's git tree per `locator.py`.

## References

- [argparse — Parser for command-line options, arguments and sub-commands — Python docs](https://docs.python.org/3/library/argparse.html) — Official reference for subparsers, handler wiring, and per-command flags — needed to add the thin `annotate` subcommand and its `--archive`/`--output-dir` flags to the CLI layer. `annotate` is single-pass; any `--iterate`/`--no-iterate` flag is reserved/no-op and its help text must say so plainly (or be omitted until the convergence loop lands) rather than falsely advertise convergence.
- [subprocess — Subprocess management — Python docs](https://docs.python.org/3/library/subprocess.html) — Authoritative spec for `subprocess.run`/`Popen`, args, and capture — the basis for the invoker seam that shells out to the Claude backend and must stay overridable in tests.
- [pathlib — Object-oriented filesystem paths — Python docs](https://docs.python.org/3/library/pathlib.html) — Reference for path resolution, stem/suffix handling, and read/write — used to derive `<name>.annotated.md`/`<name>.seed.md` output paths and resolve the owning repo root.
- [difflib — Helpers for computing deltas — Python docs](https://docs.python.org/3/library/difflib.html) — Line-diff primitives for the additive-guarantee test that diffs original plan lines against the report and fails on any omission or rewording.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Canonical guide to `safe_load` and YAML emission — relevant for reading plan frontmatter and writing the three recorded provenance links (report → original, seed → report, archived original → report); the seed → next-plan hop is not persisted, so the on-disk chain stops at the seed.
- [Claude Code — Headless / Run programmatically](https://code.claude.com/docs/en/headless) — Official reference for non-interactive `-p`/`--print`, `--output-format`, and auth flags — the contract the real shell invoker depends on when `annotate` calls Claude for the implemented-vs-spec judgement.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **No new file parser** — ingestion reuses `read_existing_description`; the file never has to be valid plan frontmatter.
- **No reuse of the `verify_plan` engine** — `annotate` authors its own section-level judgement seam modeled on the `verify_plan` (`reconcile-plan --rollup`) style, since that engine judges per parsed `Plan` step and cannot run on free-form prose.
- **No distilling either artifact inside `annotate`** — the seed is rendered directly from the classification; the distill gate stays in `create`, and the documented handoff passes `--no-distill` so the raw seed is fed straight through (the seed's non-canonical body would otherwise trigger distill regardless of size).
- **No in-place mutation of the original** beyond the opt-in `--archive` move (which preserves it with a lineage notice).
- **No manifest registration** — `annotate` produces a report and a seed file, not a registered plan; registration happens when the author runs `create` on the seed.
- **No portfolio/multi-plan sweep** — one plan file per invocation; per-plan `reconcile-plan --rollup` remains the live-plan progress view.
- **No cross-project enumeration** — discovery stays scoped to the cwd's git tree per `locator.py`.

## Risks

- **Annotation accuracy depends on complete code-grounding.** If `extract_file_path_candidates` under-resolves the relevant files, sections may be misclassified NOT-IMPLEMENTED. Severity: correctness of the audit. Mitigation: allow the comparison to widen to the resolved repo root, and mark low-confidence classifications explicitly rather than asserting them.
- **Round-trip drift — largely designed out.** Because the seed is rendered compact directly (not the report pushed through distill), there is no lossy second pass to mangle annotations. Residual risk: the seed renderer itself drops a carryover item. Mitigation: render the seed from the structured classification and test the round-trip explicitly; the documented handoff passes `create --from-existing <name>.seed.md --no-distill` so distill never runs on it (the seed's `Carryover scope`/`Already implemented`/`Provenance` body does not meet `create`'s canonical-coverage skip condition, so compactness alone would not bypass distill).
- **Per-file truncation can misclassify large files.** `_ground_source` reads at most `_MAX_GROUND_FILE_BYTES` (4096) per grounded file, so a large implemented file whose relevant symbol sits past 4KB is judged on incomplete evidence and may be marked PARTIAL/NOT-IMPLEMENTED. Severity: correctness of the audit. Mitigation: label truncated files in the grounded prompt block and mark any verdict grounded on a truncated file `low_confidence` rather than asserting it (same surface-doubt posture as the under-resolution risk).
- **Additive guarantee is easy to regress.** A report-renderer change could silently drop original content. Severity: violates the lossless property. Mitigation: a test that diffs original lines against the report and fails on any omission.
- **Overlap with `reconcile-plan`.** `reconcile` mutates a live plan to match code; `annotate` produces a forward-seed and never mutates the source plan. Mitigation: keep the intents distinct in docs so users pick the right verb (live plan upkeep → reconcile; start the next iteration from an old plan + current code → annotate).
- **`--archive` on a registered live plan orphans its manifest entry.** `archive_existing_source` moves the source plan (and co-moves its `plan-details/<slug>/` bundle) but never touches `<repo>/.plan-tool/plans.json`, and `## Out of scope` excludes manifest registration — so archiving a plan registered in the manifest leaves a dangling entry pointing at the moved file that `locator.py` resolution then fails on. Mitigation: step 3 documents/warns this case rather than deregistering (manifest mutation stays out of scope); annotate's typical input is an unregistered old plan or rough-notes file.

## Testing

Follow the project's unit-first convention (`TESTING.md`); mirror source modules (`plan_tool/X.py` → `tests/test_X.py`) and neutralize every Claude seam per TESTING.md — override the orchestrator's `invoker=`/`claude_invoker=` default so no test spawns the real backend (the autouse gate in `tests/conftest.py` raises otherwise).

Unit tests:
- Report renderer is strictly additive — original content fully preserved and never distilled (diff original lines against the report; fail on any omission or rewording).
- Seed renderer scopes carryover to NOT-IMPLEMENTED sections plus each PARTIAL's `remaining_work`, and routes IMPLEMENTED sections plus each PARTIAL's already-implemented half into a done-context block; includes a pointer to the report.
- Classification mapping — IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED with concrete `file:line` / symbol references for implemented and partial cases.
- Provenance fields present on both files (report → original, seed → report).

Integration tests (`@pytest.mark.integration`, driving `main(["annotate", ...])`): over a temp plan + fixture code where some steps are implemented and some aren't, assert the report's status blocks are correct; then feed `<name>.seed.md` to `create --from-existing` (invoker stubbed) and assert the new plan's scope is the carryover set — every NOT-IMPLEMENTED item plus only each PARTIAL's `remaining_work` — while IMPLEMENTED items and each PARTIAL's already-implemented half are carried as done-context, not re-planned. Existing `create` / `verify_plan` / reconcile suites must still pass; run the integration tests that exercise the from-existing reader and the `verify_plan` comparison when modifying those source files.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool annotate <plan-file>` writes a report (`<name>.annotated.md`) whose every original line is present verbatim, with section status blocks added and a top-of-file coverage summary, plus a seed (`<name>.seed.md`).
- For a fixture where some steps are implemented in the repo and some are not, each section is classified IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED with a concrete code reference for the implemented and partial cases.
- `plan-tool create --from-existing <name>.seed.md --no-distill` accepts the seed and produces a plan whose scope is the carryover work: every NOT-IMPLEMENTED item plus only the not-yet-implemented remainder of each PARTIAL item. IMPLEMENTED items, and the already-implemented portion of PARTIAL items, are carried as best-effort done-context: `create` has no structural done-context concept, so the only signal is the seed's `Already implemented` prose section (its done items labeled and scoped out of the carryover), which `create` may or may not honor — this is documented as best-effort, not an enforced guarantee. The documented handoff passes `--no-distill` so the raw seed is fed straight through (the seed is never distilled inside `annotate`, and its non-canonical body would otherwise trigger `create`'s distill regardless of size).
- Multi-effort carryover survives the distill handoff: when the carryover spans multiple efforts, the operator drops `--no-distill` so `create`'s split detection fires (it lives inside distill), and the resulting split's efforts are scoped to the carryover work only — the seed's `Already implemented` done-context is not folded back into any effort's scope. Because distill is a lossy pass that reorganizes the seed's non-canonical body into canonical sections and can blur the carryover/done-context partition, this path is documented as requiring the operator to re-verify the split's scope against the report rather than asserting it preserved automatically.
- With `--archive`, the original is moved and annotated with a notice pointing at the report; without it the original is untouched.
- Provenance chains: report → original, seed → report; no information from the original is lost.
- Fully-implemented terminal case (every section classifies IMPLEMENTED, so carryover is empty): annotate still writes both artifacts. The report's coverage summary reads 100% implemented, and the seed is still written with an empty `## Carryover scope` that carries an explicit "No remaining work — every section is implemented" marker (not a bare empty heading) so that feeding it to `create --from-existing` is a defined no-op rather than undefined input. The CLI signals the operator that there is no forward work — a stdout notice naming the report and stating no next plan is needed — so the operator is not left to infer it from an empty seed.
- Every Claude seam is overridden in tests; no test spawns the real backend.

## Deferred

- _None yet._ No work has been dropped or postponed — the plan is at `planning` status with no steps complete. Populate this section as steps land and items are deliberately deferred, each with a one-line reason (too large, blocked, or a separate concern), keeping it distinct from the permanent exclusions in `## Out of scope`.
