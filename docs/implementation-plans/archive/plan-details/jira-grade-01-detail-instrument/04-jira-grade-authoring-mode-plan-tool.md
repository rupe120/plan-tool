> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add a jira-grade authoring mode to `plan-tool detail` with its own prompt, response gate, and artifact target

## Summary

Give `plan-tool detail` an opt-in jira-grade mode: a new compact prompt template (`plan_tool/prompts/detail-jira.md`), a response gate built on step 3's `plan_tool/jira_grade.py` validator, and an artifact target routed through step 3's jira-grade path derivation — while the default run-grade path stays unchanged in every way. The key design decision: grade is a first-class mode that selects a complete bundle (prompt, parse gate, retry suffix, output path, checkpoint namespace, skip/force scope), not just an alternate template — and the jira-grade bundle bypasses the entire run-grade quality machinery (`plan_tool/detail.py:collect_detail_quality_findings`, the `--iterate` convergence loop, the foundational-logic sweep, lessons extraction, the deferral envelope, and the split escalation). `Step.detail` stays run-grade-only: jira-grade authoring never reads or writes that pointer. On green, `plan-tool detail <name> --grade jira` writes a five-section jira-grade artifact per step under the plan's `jira/` detail subdirectory, a default `plan-tool detail <name>` run is byte-for-byte the current behavior, and approx. 16–18 new tests pass across `tests/test_detail.py` and `tests/cli/test_authoring_cmds.py`.

## Table of Contents

- [Summary](#summary) — what the mode ships and the one design decision
- [Why](#why) — why jira-grade needs its own authoring lane, not a template swap
- [Input](#input) — the step 1 / step 3 contracts and the run-grade seams this step must not disturb
- [Files (creates vs edits)](#files-creates-vs-edits) — the new prompt template and per-file edits
- [Implementation](#implementation) — the mode bundle, where it branches, the constraints on each piece, and the one end-to-end smoke check
- [Tests](#tests) — generation-seam and CLI-routing cases, with the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the plan-level references relevant to this step
- [Deferred](#deferred) — consumer wiring and lifecycle gaps owned by later steps

## Why

The plan's goal is a compact, stakeholder-facing jira-grade detail artifact that coexists with the developer-facing run-grade file — and steps 5 (jira export), 6 (run renderer), and 7–9 (the grade-aware audit) all consume that artifact. Nothing can author it yet. **This step runs last of the code steps by deliberate design:** its frontmatter declares `depends_on: [1, 3, 9]`, so the audit understands the grade axis and can judge a jira bundle *before* any such bundle can exist — the plan body's "validator lands before the producer" rule. The edge points backward in step numbering, which `depends_on` permits, so the real execution order is 1 → 2 → 3 → 5 → 6 → 7 → 8 → 9 → 4 → 10. At this step's turn steps 2, 3, 5, 6, 7, 8, and 9 are all merged and verifiable — verify their shipped spellings against the code rather than treating them as predictions. The naive route — pointing the existing authoring path at a different template — fails structurally: `plan_tool/detail.py`'s quality machinery is schema-coupled to the run-grade seven-section contract. `parse_detail_response` enforces `_REQUIRED_H2_TOKENS` and synthesizes stubs for run-grade sections; `_REPROMPT_SUFFIX` re-teaches the seven-H2 contract on retry; `collect_detail_quality_findings` and its rewrite loop judge run-grade section shape; and the checkpoint cache (`_DETAIL_CHECKPOINT_NAME`, keyed by `_detail_step_input_hash` on step shape only, not grade) would happily resume a cached run-grade body into a jira-grade write. A compact five-section body looks malformed to every one of those, and a run-grade body looks acceptable to none of the jira-grade consumers. So this step adds a parallel authoring lane that shares the orchestration mechanics (per-step loop, invoker seam, retry loop, reporter, run log, dry-run/skip/force semantics) but swaps the grade-coupled pieces, and keeps `Step.detail` untouched so the new artifact activates only when its consumer steps (5–6) deliberately select it.

## Input

- **Step 3's jira-grade contract authority** (plan_tool/jira_grade.py, produced by step 3 — not at HEAD): the five required H2 tokens (`intent`, `change`, `constraints`, `done`, `out`, matched by the first-token convention), a closed-schema validator that rejects unknown top-level H2s (so a run-grade body fails structurally), and a deterministic plain-English prose gate whose blocking findings are meant to drive this step's reject-and-retry loop — not read-time consumers. This step consumes those symbols; it must not re-declare the tokens or write a second validator.
- **Step 3's artifact path routing** (added to plan_tool/detail_artifacts.py by step 3 — step 1's leaf is merged, step 3's jira additions are not): jira-grade artifacts derive to a `jira/` subdirectory of the plan's detail directory (`plan-details/<plan_slug>/jira/<NN>-<step_slug>.md`), chosen so `plan_tool/detail.py:_archive_orphan_details`'s non-recursive `{NN}-*.md` glob and `find_unreferenced_detail_for_step`'s adoption never touch it. This step consumes that derivation; it must not invent a second path convention.
- **Run-grade seams this step must leave intact** (all in `plan_tool/detail.py` at HEAD): `generate_detail`'s default-mode skip rule ("`step.detail` set AND file on disk → skip"), the adopt-unreferenced pass that reattaches run-grade pointers, `_author_step_detail`'s retry loop with `_REPROMPT_SUFFIX`, the checkpoint save/discard cycle under `_DETAIL_CHECKPOINT_NAME`, and the monkeypatch seams existing suites rely on (`plan_tool.cli.authoring.generate_detail`, `plan_tool.detail.collect_detail_quality_findings`, the module-level `apply_finding` import). Every one of these keeps its current name, call form, and default behavior.
- **Verification limit:** this file was authored when only step 1 was `done`, so it cites steps 3 and 5–9 as dependency contracts. **By this step's actual turn that is no longer true** — the backward `depends_on: [1, 3, 9]` edge puts it last among the code steps, so steps 2, 3, 5, 6, 7, 8, and 9 are all merged and every symbol, flag spelling, and path convention cited from them is verifiable in the code. Re-grep and describe what shipped; where this file and the merged code disagree, the code wins.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/detail-jira.md` — the jira-grade authoring prompt template.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — add a `grade` selection to `generate_detail` (default run-grade); add the jira-grade prompt renderer, response gate, retry suffix, and checkpoint namespace; route the jira-grade branch around the quality loop, foundational sweep, lessons extraction, deferral envelope, pointer adoption, and `Step.detail` update.
  - `plan_tool/cli/authoring.py` — register the grade flag on the `detail` subparser in `register`; add the mode-conflict guards in `cmd_detail`; forward the grade to `generate_detail`; skip the auto-completeness tail in jira-grade mode.
  - `docs/cli/detail.md` — regenerated flag reference (via `python -m plan_tool.cli_reference --write`; the file is generated from the argparse parser, drift-guarded by `tests/cli/test_cli_reference.py` — do not hand-edit).
  - `tests/test_detail.py` — new test class covering the jira-grade generation seam (prompt, gate, artifact, checkpoint, bypass behavior).
  - `tests/cli/test_authoring_cmds.py` — new routing tests for grade selection and the conflict guards.

## Implementation

### The mode is a bundle, selected once

- **Add a grade selector to `plan_tool/detail.py:generate_detail`** — likely a keyword `grade: str = "run"` (exact name/shape is the implementer's call; a two-value string mirrors how later steps select grades on `jira` and `run`). The default must mean "today's behavior exactly": every existing caller, including `plan_tool/cli/authoring.py:cmd_detail`, `plan_tool/detail.py:merge_bridge`'s re-author path, and the split flow, runs unchanged without passing it.
- **Grade selects everything at once.** When `grade` is jira, the per-step unit swaps: prompt renderer (new `render_jira_detail_prompt` → `plan_tool/prompts/detail-jira.md`), response gate (step 3's validator + prose gate instead of `parse_detail_response`), retry suffix (a new `_JIRA_REPROMPT_SUFFIX` spelling the five-H2 closed contract instead of `_REPROMPT_SUFFIX`'s seven), output path (step 3's jira-grade derivation instead of the run-grade path), checkpoint name (a distinct namespace, e.g. `jira-detail-step-{NN}`), and skip/force scope (the jira artifact only). A template-only branch was rejected: it would publish a compact body through run-grade parsing and stub-synthesis, resume run-grade checkpoints into jira writes, and apply skip/force to the wrong artifact.
- **Recommended factoring, not a mandate:** reuse the shared orchestration — the step-target loop, `_author_step_detail`'s resume-or-invoke → parse → checkpoint → write sequence, the reporter/run-log plumbing, `_MAX_INVOKE_ATTEMPTS`, dry-run prompt carrying, and `_print_detail_summary` on the CLI side — by parameterizing the grade-coupled inputs (prompt, parse function, reprompt suffix, output path, checkpoint name) rather than copying the loop. How far to parameterize `_author_step_detail` versus branching around it is implementer latitude; what is not free to vary is that the run-grade path through those functions stays behaviorally identical.

### What the jira-grade branch must skip

When `grade` is jira, none of the run-grade quality machinery runs:

- **No quality/convergence loop** — `collect_detail_quality_findings` is never called (it is schema-coupled to the run-grade contract; the project lesson for this plan pins this bypass). The CLI rejects `--grade jira --iterate` loudly (see guards below); `generate_detail` also refuses `grade="jira"` with an enabled `IterativeBudget` as a deep guard, mirroring its existing `jobs > 1` guards.
- **No foundational-logic sweep, no lessons extraction, no scenario capture** — pass/force `foundational_invoker=None`-equivalent behavior, `extract_lessons=False`-equivalent behavior, and skip `capture_scenarios` on the jira branch (the prompt-mode experiment's arms describe run-grade authoring; do not add a jira arm to `PROMPT_MODE_EXPERIMENT`).
- **No deferral envelope** — the jira prompt does not ask for the `plan-tool-detail-deferrals` transport block, and the jira parse path never calls `parse_structured_detail_response`. Concept deferrals are a run-grade authoring concern.
- **No purity/split machinery** — no `parse_mixed_step_findings` strip, no `escalate_to_split` reachability; `--grade jira --split` is rejected at the CLI.
- **No `Step.detail` read or write** — the jira branch skips the adopt-unreferenced pass and never calls `update_step_detail_field`. The skip rule is purely "jira artifact on disk → skip unless `--force`"; a step whose run-grade pointer is set, unset, or stale gets identical jira-mode treatment.
- **No cross-grade checkpoint reuse** — the distinct checkpoint name is the constraint that matters: a jira-grade run must never resume a run-grade cached body (or vice versa), because `_detail_step_input_hash` keys on step shape, not grade, so the hashes would otherwise match.

Two shared behaviors carry over deliberately:

- **The output-path pin.** The jira prompt names the canonical jira artifact path and forbids the subprocess writing any file itself — same orphan-avoidance reason `render_detail_prompt` documents.
- **Stale-sibling cleanup inside `jira/` only.** One way: call `_archive_orphan_details(jira_output_path, step.id)` after a successful write — it is path-relative, so it sweeps only stale `NN-*.md` jira siblings into `jira/archive/`. Whatever the implementer chooses, jira-mode authoring must never move, archive, or rewrite any run-grade file.

### The prompt template

`plan_tool/prompts/detail-jira.md` is a compact authoring prompt, much smaller than `plan_tool/prompts/detail.md`: plan metadata, the step (id/title/complexity/files/depends_on), the declared file contents block (reuse the existing helper — it iterates `step.all_files`, declared `files:` plus `creates:`, and that is the correct surface), the pinned output path with the no-file-writes instruction, the five required H2s with the closed-schema rule ("no other top-level sections"), and the plain-English expectations the prose gate enforces. Write the template's own prose to that same standard — plain, concise, no filler — per the plan's prose contract, which names this file beside step 6's `run-jira.md`; nothing enforces it at run time, so its acceptance criterion is the check. No deferral envelope, no self-check block, no seven-section scaffolding. Latitude: whether to include sibling jira artifacts for tone once a corpus exists.

### The response gate and retry loop

- Reuse the lenient envelope cleanup shape from `parse_detail_response` (strip leading preamble before the first `#`, strip unmatched fences) — **mirror it locally; do not extract it**. Extracting would be a behavior-preserving restructuring of `plan_tool/detail.py`'s parsing path riding inside a feature step — the same refactor-fused-with-feature shape this plan's `step-1-type-purity` blocker was split to remove; the small duplication keeps this step type-pure, and consolidating the two copies routes to reconcile later (the same disposition step 3 chose for the H2-matcher consolidation). Then validate with step 3's closed validator and plain-English gate. Both kinds of findings are blocking retry triggers here (the authoring loop is exactly the audience the prose gate's blocking findings are for; read-time consumers in steps 5–6 check structure only).
- **No stub synthesis.** Run-grade parsing stubs one missing section; the jira gate hard-rejects any missing or unknown H2. Five sections is small enough that a stub would fabricate a fifth of the artifact.
- On rejection, retry once with `_JIRA_REPROMPT_SUFFIX` (same `_MAX_INVOKE_ATTEMPTS` budget and `_log_parse_failure` dump as run-grade), then record a failed `DetailResult` with a clear reason.

### CLI wiring (`plan_tool/cli/authoring.py`)

- **Register the flag** on the `detail` subparser in `register` — recommended: `--grade` defaulting to `run`, with `choices=` taken from step 3's grade constants. Step 3 is the single authority for the axis spelling, so every consumer's selector matches by construction rather than by each one copying a sibling. Read it in `cmd_detail` via `getattr(args, "grade", "run")` so hand-built namespaces in older tests keep working.
- **Guards fire before any run log opens**, matching the sibling guards' placement in `cmd_detail`: `--grade jira` combined with `--iterate`, `--detail-only`, or `--reconcile` → `error(...)` + rc 2, each message naming the conflict and the way out. **`--split` is deliberately not in that list**: it is declared `action=argparse.BooleanOptionalAction, default=True` on the `detail` subparser, so a bare `plan-tool detail <name> --grade jira` would carry `split=True` and a conflict guard would reject every jira-grade invocation — including leg 1 of the plan's end-to-end smoke check. The jira branch simply does not run the split machinery, so the flag has no jira-grade meaning. Implementer latitude on how loud to be: silently ignoring it is acceptable, and distinguishing an *explicitly passed* `--split` (via a sentinel default) to reject only that is better if it costs little. What is not free to vary: a defaulted `--split` must not fail the run. Recommended for v1: also reject `--grade jira --jobs N>1` (the parallel worker's serial replay tail is run-grade shaped; lift the restriction later only if a real need appears — the architecture rules set a high bar for extending concurrency surfaces).
- **Skip the auto-completeness tail** when grade is jira — the tail audits the plan's design and run-grade detail bundle, which a jira authoring run neither changed nor produced.
- `--force`, `--dry-run`, `--step`, `--no-resume`, `--commit`, and `-y` all work in jira mode with their existing meanings, scoped to the jira artifact (dry-run renders the jira prompt and mutates nothing; `--commit` commits each written jira artifact per step).
- **No flag is left unclassified** — the sweep steps 5, 6, and 7 each commit to. The remaining two are already-off-by-construction: `--no-completeness` and `--no-lessons` are **no-ops** under `--grade jira`, because the branch skips the completeness tail and lessons extraction unconditionally. Do not reject them (they are the *safe* direction and scripts pass them habitually); state the no-op in `--help` or a one-line notice so an operator is never left wondering whether the flag did anything.
- Any `Next steps:` output added for the mode suggests only `plan-tool …` commands.

### The end-to-end smoke check (run once, when this step is green)

This step is the last of the code steps, so it is the first moment a jira-grade bundle can exist and the last moment all three consumers can be exercised on one together — before step 10 closes the plan. Author one bundle and walk it through every consumer, in order, against a scratch plan rather than one of this repo's tracked plans, so no `jira/` artifacts land in a live detail directory (a small hand-written plan file in a temp repo is enough; `create` need not be involved):

1. `plan-tool detail <scratch-plan> --grade jira -y` — authors a real bundle through the mode this step ships.
2. `plan-tool jira <scratch-plan> --grade jira` — the export consumes it (step 5).
3. `plan-tool run <scratch-plan> --detail-grade jira --dry-run` — the renderer builds a run prompt from the jira body (step 6).
4. `plan-tool completeness-audit <scratch-plan> --grade jira --audit-passes 1` — the audit grounds on that bundle (steps 7–9).

Each must exit 0 and visibly consume the jira artifact: the exported story bodies and the dry-run prompt carry the five-section content, and the audit's provenance names the `jira/` paths. This is a functional check that the pieces meet — nothing is counted, no run-grade counterpart is authored, and no result is compared against anything (the plan's Out of scope). A failure here is a real defect in whichever consumer failed; fix it before step 10, or file it if it needs its own work.

### Constraints that are not free to vary

- Default-grade behavior is unchanged everywhere; the existing `tests/test_detail.py` and `tests/cli/test_authoring_cmds.py` suites pass with zero edits to existing tests.
- `plan_tool/detail.py` imports `plan_tool/jira_grade.py` top-level only if step 3 shipped it as a leaf below `detail` (its stated contract); otherwise import lazily. Never import `detail.py` from `jira_grade.py`.
- Keep the sanctioned monkeypatch seams intact: `cmd_detail` keeps calling the module-global `generate_detail`, and the jira branch must not alias `collect_detail_quality_findings` (the completeness suites patch it by module path).
- Reuse `shell_detail_invoker` / the `invoker=` seam for the jira claude call — no new real-backend default, so no new `TESTING.md` neutralization entry is needed.

## Tests

All new tests stub the invoker (or patch `plan_tool.cli.authoring.generate_detail` for routing cases); none spawn a real backend.

`tests/test_detail.py` (new class, e.g. `TestJiraGradeAuthoring`):

- `test_jira_prompt_names_five_sections_and_closed_rule` — rendered jira prompt contains the five required H2s and the no-other-sections rule.
- `test_jira_prompt_pins_output_path` — prompt names the canonical `jira/` artifact path and forbids the subprocess writing files.
- `test_jira_mode_writes_to_jira_subdirectory` — a conforming invoker response lands at the step-3-derived `jira/` path.
- `test_jira_mode_leaves_step_detail_unset` — after a jira write, the plan frontmatter's `detail:` pointer is still unset.
- `test_jira_mode_leaves_run_grade_artifact_untouched` — with a run-grade pointer + file present, jira authoring changes neither.
- `test_jira_gate_rejects_run_grade_body` — a complete, valid run-grade seven-section body is rejected by the jira gate (the lesson-mandated negative case).
- `test_jira_gate_accepts_conforming_body` — a five-section jira body parses and writes.
- `test_jira_retry_uses_jira_reprompt_suffix` — on first-attempt rejection, attempt 2's prompt carries the jira suffix, not `_REPROMPT_SUFFIX`.
- `test_jira_gate_no_stub_synthesis` — a four-of-five-section body is rejected, not stubbed.
- `test_jira_mode_skips_existing_artifact` — second run over the same step skips with an "already exists" reason.
- `test_jira_force_regenerates_only_jira_artifact` — `force=True` rewrites the jira artifact; the run-grade file is unchanged.
- `test_jira_dry_run_mutates_nothing` — dry-run carries the rendered jira prompt; no file or plan write.
- `test_jira_mode_never_calls_quality_loop` — patched `collect_detail_quality_findings` is not called; `grade="jira"` with an enabled budget raises `DetailError`.
- `test_jira_mode_does_not_resume_run_grade_checkpoint` — a valid run-grade checkpoint for the step is ignored by a jira run.
- `test_jira_mode_skips_lessons_and_sweep` — lessons and foundational-sweep stubs are never invoked on the jira branch.

`tests/cli/test_authoring_cmds.py` (new class, e.g. `TestDetailGradeRouting`):

- `test_detail_default_grade_is_run` — patched `generate_detail` receives the run-grade default from a bare `detail <name>` invocation.
- `test_detail_grade_jira_forwards_to_generator` — `--grade jira` reaches the patched `generate_detail` with the jira selection.
- `test_detail_grade_jira_rejects_iterate` — rc 2 before any generator call; message names both flags.
- `test_detail_grade_jira_rejects_reconcile_and_split` — same guard shape for the other conflicts.
- `test_detail_grade_jira_skips_completeness_tail` — no completeness tail runs after a clean jira authoring pass.

### Test-creation order (feature step)

Feature step — author each test with the implementation slice it covers: gate tests alongside the gate, routing tests alongside the CLI wiring, artifact/pointer tests alongside the branch in `generate_detail`. Green-before-done gate: every test above passes, and the full suite (`uv run pytest tests/ -q`) is green with zero edits to existing tests, before this step is considered finished.

## Acceptance criteria

- `plan-tool detail <name> --grade jira` writes a five-section artifact at the step-3-derived `jira/` path for each step lacking one, and exits 0.
- A default `plan-tool detail <name>` run is behaviorally unchanged: run-grade path, run-grade gate, `Step.detail` pointer update, quality machinery availability — all existing tests pass unmodified.
- After a jira-grade run, no step's `detail:` frontmatter field was added, changed, or removed.
- The jira gate rejects a complete run-grade seven-section body and rejects any body with a missing or unknown top-level H2; no stub section is ever synthesized on the jira path.
- On rejection, the retry prompt ends with the jira-specific suffix naming exactly the five required H2s.
- `--grade jira` combined with `--iterate`, `--detail-only`, or `--reconcile` exits 2 with an error naming the conflict, before any claude call or run log.
- A bare `plan-tool detail <name> --grade jira` — carrying the default `--split` — exits 0 and authors normally; the defaulted flag never fails the run.
- `--force` under `--grade jira` rewrites only the jira artifact; `--dry-run` writes nothing and prints the jira prompt; a repeat run without `--force` skips.
- A jira-grade run never loads a run-grade checkpoint and never calls `collect_detail_quality_findings`, the foundational sweep, or lessons extraction (asserted via stubs).
- `plan_tool/prompts/detail-jira.md` reads as plain, concise English in its own right — short direct sentences, familiar words, no filler — with every `${...}` variable, path, and H2 token intact, satisfying the plan's plain-English prose contract for this template. This is about the prompt's own prose, distinct from the plain-English expectations it states for the model. Checked by reading the file, not by a runtime gate (it is hand-authored, not model output) — the same treatment step 6 gives `plan_tool/prompts/run-jira.md`.
- The end-to-end smoke check ran once and passed: one bundle authored by this mode was consumed by `jira --grade jira`, `run --detail-grade jira --dry-run`, and `completeness-audit --grade jira`, each exiting 0 on the jira artifact (see Implementation). Its outcome, including any defect it surfaced, is recorded in this step's commit message.
- `docs/cli/detail.md` regenerates cleanly and `tests/cli/test_cli_reference.py` passes.
- Approx. 20 new tests across `tests/test_detail.py` and `tests/cli/test_authoring_cmds.py` pass; full suite green.

## References

- [Claude Code — Headless / programmatic mode](https://code.claude.com/docs/en/headless) — the non-interactive `claude -p` contract behind `shell_detail_invoker`, which the jira mode reuses unchanged.
- [CommonMark Spec 0.30 — ATX headings](https://spec.commonmark.org/0.30/) — ground truth for the H2 syntax the five-section gate and reprompt suffix describe.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — choices-restricted flags and mutually-exclusive-group behavior for the grade flag and its conflict guards.
- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — stubbing the invoker seam and the `plan_tool.cli.authoring.generate_detail` routing seam in the new tests.

## Deferred

- Consuming the jira artifact in `jira` export, `run`, and the completeness audit — owned by steps 5, 6, and 7–9 respectively; this step only authors it.
- Renumber/split staleness of unpointed `jira/` artifacts — step 3 classified this as a loud gap (consumers hard-fail on a missing selected artifact) and routed a durable migration to reconcile once a real corpus exists; nothing new here changes that.
- `--jobs > 1` support for jira-grade authoring — rejected in v1; revisit only against the architecture rules' cut-work-first bar if serial jira authoring is ever a measured bottleneck.
- Consolidating the repo's four first-token H2 matchers (`plan_tool/detail.py`, `plan_tool/create.py:extract_h2_sections`, `parse_detail_file_sections`, `plan_tool/jira_grade.py`) into one — a cross-module refactor routed to reconcile per step 3's decision; this step mirrors, never merges.
- A jira arm in `PROMPT_MODE_EXPERIMENT` / scenario capture, and paired run-vs-jira outcome evaluation — stage 03 owns the measurement side entirely (`plan-seeds/jira-grade-03-quality-ledger.md`); this step captures nothing for the jira branch.
- Completeness-audit awareness of jira artifacts (e.g. counting them in bundle status) — owned by steps 7–9's grade-aware grounding.
