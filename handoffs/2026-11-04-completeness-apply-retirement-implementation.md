# Completeness apply retirement implementation

All six steps are shipped on `origin/main` at `cf303fe29`. Plan PR #162,
implementation PR #163, and plan-status PR #164 are verified merged on
2026-11-04; the code and plan snapshots match their fetched remote paths.
This closed review ledger retains implementation and validation provenance.
Independent completed fixes retain their dispositions in the
[maintenance review ledger](2026-11-05-completed-maintenance-code-review.md);
remaining work belongs to `BACKLOG.md` and `BUG_BACKLOG.md`.

## Delivered scope

The CLI rejects `completeness-apply`, `direct-run`, and `direct-jira`. Their
exclusive handlers, serial/parallel apply machinery, direct pipelines, generated
references, help, and capability entries are removed. Live guidance directs
conceptual findings to judged edits. Create/detail deterministic repair,
generic review/reconcile authority, benchmark fixtures, persisted schemas,
legacy readers, blocking policy, and exit codes retain their contracts.

BACKLOG #376 and removed-command-only requests are removed; mixed requests keep
surviving work. #519 owns the unreachable structural opt-in disposition; #520
owns stale lesson maintenance. A machine comparison with `origin/main` confirms
the complete #369 block is byte-for-byte unchanged. The changelog fragment
`changelog.d/completeness-apply-retirement.md` marks the CLI removal as breaking
and gives the replacement workflow.

## Pre-execution audit provenance

Historical evidence, 2026-11-04. The archived bundle is
`docs/implementation-plans/archive/plan-details/completeness-apply-retirement/`.
`reconcile-plan --all --no-walk -y` saved `reports/20261104-130427.json`; its
semantic review found obsolete step-5 paths, wrong #367 ownership, and removed
Jira-grade wording. Its already-built suggestions were token matches
contradicted by that review, so no step status changes follow. The correction
also aligned seed, backlog, and documentation paths and added Cursor guidance
and the glossary. The bounded correction keeps retirement from widening into
unrelated application authority: generic application and deterministic repair
authority stay, and #369's scope stays independent. The seed remains archived
and inert, not a competing scope owner.

Both audit gates use `completeness-audit completeness-apply-retirement
--iterate --commit --audit-passes 1 -y` with backend Codex, model `gpt-6.1-sol`,
and closed stdin.

- Bare report `reports/20261104-130709-completeness.md`: 0/6 details, zero
  conceptual findings, confirmed coverage, current revision, fresh conceptual
  call. The sole heuristic `plan-claim-vs-delivery-caca4275` names deliberately
  preserved `apply_finding` and does not justify plan expansion.
- One-shot `detail --commit -y` authored all six details; its tail saved
  `reports/20261104-132734-completeness.md` with zero findings.
- Detail-grounded gate (adds `--reuse-audit`) saved
  `reports/20261104-140106-completeness.md`: 6/6 details, zero open findings,
  confirmed coverage, current revision, explicit conceptual-call reuse,
  advisory-only. No conceptual correction loop ran, so no three-snapshot
  trajectory applies.

These records certify the authored bundle, not implementation delivery. Do not
rerun pre-execution plan-mutating audits on executed work.

## Execution and recovery

Commands use `uv run plan-tool --backend codex --model gpt-6.1-sol` with closed
stdin and `-y`. `run completeness-apply-retirement --all --commit` advanced
steps 1 and 2 through green full-suite gates, then stopped step 3 at its test
gate. The implementation subprocess committed at `b25c6f5dc`; eight tests in
`tests/test_review_walk.py::TestCliCompletenessApplySubcommand` still invoked the
removed command or monkeypatched its deleted walk seam (focused reproduction
confirmed all eight). The class and its two exclusively used fixtures are
removed at `1d3aa6401`; shared walk coverage remains. Full suite: 14,705 passed,
67 skipped. `run completeness-apply-retirement --step 3 --accept --commit` reran
acceptance and advanced the step without a backend call; the resumed
`run --all --commit` finished steps 4-6 with green full-suite gates. No status
was edited by hand.

## Reconciliation and code review

Both sweeps used `uv run plan-tool --backend codex --model gpt-6.1-sol
reconcile-code completeness-apply-retirement --all --no-walk -y < /dev/null`,
covering the three code steps and skipping the three explicit non-code steps.
Reports are retained under the plan's `reports/` directory.

| Evidence | Result and disposition |
| --- | --- |
| `20261104-144231-run-reconcile.json`, step 1 | One nit: stale command/automatic-conceptual-repair explanations, confirmed by identifier and vocabulary searches across report, tail, split, merge, and invoker docstrings. Fixed `bf5ead546` (documentation class only, no runtime change). |
| `20261104-144415-run-reconcile.json` (step 2), `20261104-144608-run-reconcile.json` (step 3) | Zero findings. |
| Confirmation reports `20261104-144955`, `20261104-145334`, `20261104-145531` | Zero findings across all three code steps after the correction. |
| `codex review -c 'model="gpt-6.1-sol"' --base origin/main`, head `bf5ead546` | No actionable regressions across correctness, completeness, command wiring, surviving audit paths and compatibility; 1,337 focused tests reported passing. Conclusion: "No actionable regressions were identified in the command retirements or remaining audit paths." Transcript `.tmp/completeness-apply-retirement.review-1.log` (transient). |

## Final validation

- `uv run pytest tests/ -q -n auto` passes independently: 14,705 passed, 67
  skipped in 61.74 seconds (`.tmp/completeness-apply-retirement.isolated-tests.log`).
- A concurrent validation attempt recorded two worker crashes in unchanged
  data-contract path-reference tests, and the reviewer recorded a
  filesystem-traversal timeout. Neither is an established regression; the
  standalone green rerun is the evidence, and no timeout, worker-policy or
  data-contract change follows.
- `git diff --check` passes; the #369 exact comparison passes. No
  post-execution plan-mutating reconciliation or design audit runs.

## Publication

[Implementation PR #163](https://bitbucket.org/protagona/plan-tool/pull-requests/163)
and [plan-status PR #164](https://bitbucket.org/protagona/plan-tool/pull-requests/164)
are verified merged, in that order. `git fetch origin main` resolves to
`cf303fe29`; path-scoped diffs against `BACKLOG-376-code` and `BACKLOG-376-plan`
are empty. The item has no promoted Jira key; BACKLOG #376 is the source record.
No publication is pending.

Claude review uses the `claude-personal` alias; the ordinary CLI's expired login
prevented two review starts, which establish no review evidence. The five
completed rounds below establish the convergence result.

## Review ledger

Reviewer provenance: `/code-review` at `high`, report-only, local-diff form,
`claude-personal` (pass 1 by the driving session). Reviewers made no edits and
none claimed a clean sweep beyond the coverage they state.

### Pass 1 (2026-11-04, `a5ac60bca71e9609ffe624322cfb4cb3839ad3f2`, 73 files)

The reviewer ran `uv run pytest tests/ -q -n auto -m "not integration"` (13841
passed, 66 skipped; integration not run). Its pyflakes claims were re-checked by
`uvx pyflakes` and grep; its line numbers were off, so cited lines are verified
ones. No correctness bugs and no regressions to create/detail repair,
review/reconcile routes, persisted schemas, legacy readers, blocking policy or
exit codes; seven low/nit findings, all dead code or stale prose.

1. Nit, unused imports left by the deletions (`DetailFormatError`, `GRANULARITY_SPLIT_SOURCE`, `UnsupportedPlanFormatVersionError`, `success` in `plan_tool/cli/completeness_phases.py`; `warn` in `completeness_cmd.py`). Disposition: fixed `3a200d72b` (five imports removed; function-local imports and the documented re-exports `_finding_progress_label`/`_fmt_finding_counts` at `completeness_cmd.py:55-56`, identical on `origin/main`, stay).
2. Nit, stale "direct pipelines" comment at `plan_tool/create.py:10571`. Disposition: fixed `3a200d72b` (names the surviving `cli/authoring.py` consumer; `iteration_stage_failure` call sites unchanged).
3. Nit, stale apply-walk rationale on `open_findings` in `completeness_phases.py` (~3876-3884) for a value always `[]`. Disposition: fixed `3a200d72b` (one-line note; report input and runtime behavior unchanged).
4. Low/nit, apply-walk wording in `convergence_diagnosis.py` (~1544). Disposition: fixed `3a200d72b`; the cited text is in `_open_medium_plus`, not `_latest_blocking_findings`, and now describes legacy sidecar annotations. `test_saved_apply_annotations_keep_their_history_meaning` pins the preserved behavior.
- A1, medium `granularity-split` replay persisted with no consumer (`mixed_split_recs`, `split_escalation_target`, `halt_on_applied`, `guard_saved_directive`, `extra_apply_sources` in `completeness_phases.py` ~3896-3911). Disposition: tracked #519, the unreachable structural opt-in; its "replayable" comment wording is updated there, not here.
- A2, CLAUDE.md rule edits require `architect`-tier review. Disposition: pending (process requirement, kept open): route CLAUDE changes to Architect review in the code PR; no session approval or merge is authorized.
- A3, `docs/evidence/public-release-final-selection-verification-20261021.json` (and the distribution-verification JSON) list now-deleted files (`docs/cli/completeness-apply.md`, `docs/cli/direct-run.md`, `docs/how-to/pipeline/direct-pipeline.md`). Disposition: declined; dated historical evidence stays unchanged under the plan's no-migration boundary and no active consumer exists.

Application: defect class is deletion leftovers (unused dependencies and explanations describing retired consumers as live); identifier and vocabulary searches covered the five imports, `stage_failure`, `open_findings`, direct pipelines, fruitless iteration, apply walks and applied/declined annotations. All sites corrected at `3a200d72b`. Full suite 14,705 passed, 67 skipped (`.tmp/completeness-apply-retirement.pass-1-fixes-tests.log`); no runtime predicate, annotation handling or schema changed.

### Pass 2 (2026-11-04, `e6e1f32af`)

Eight findings, none above low/medium; no functional regression, exit-code, schema or legacy-reader break.

- F1, low, bare-plan audit output said "apply is withheld until a detail bundle exists" (`completeness_phases.py:3720`; `completeness_report.py:855`, ~2146, ~2300). Disposition: fixed `139283de5` (output distinguishes plan-level edits now from detail-only remedies later; stage predicates and exit codes unchanged; three tests pinning old prose updated, and restoring the pre-fix report and grouped renderer makes both targeted assertions fail, `.tmp/completeness-apply-retirement.pass-2-mutation.log`).
- F2, low, `docs/how-to/pipeline/audit.md:710, 822, 825` cited deleted `cmd_completeness_apply()`, `completeness_apply_parallel.py`/`run_parallel_apply` and a module-map row. Disposition: fixed `139283de5` (references and row removed; data-contract reader contract kept).
- F3, medium if consumed, `.claude/skills/plan-tool/DIRECTIVES.md` and `SKILL.md` (tracked copies, 13 and 3 matches) still documented the retired commands. Disposition: fixed `139283de5`; `cli/skill_cmd.py:cmd_install_skill` shows the canonical owners are `integrations/claude/SKILL.md` and `integrations/shared/DIRECTIVES.md`, and the copies were refreshed from them (bytes match).
- F4, low, `mixed_split_recs` persisted "for saved readers" with a "replayable" comment (`completeness_phases.py:3881`). Disposition: tracked #519 (see A1).
- F5, low, unreachable `granularity-split` dispatch comments in `cli/review_actions.py`. Disposition: refuted; no `completeness-apply` or deleted-lane comment remains there and the comments describe preserved dispatch semantics. Route disposition stays #519.
- F6, nit, `_APPLY_AS_FINDING_SOURCES` comment (`review_walk.py:~290`) dropped why `plan-correctness` is excluded. Disposition: declined; the detail-gate command it would cite is retired. The comment correctly requires caller opt-in, and existing dispatch tests pin the exclusion and the explicit-opt-in carve-out.
- F7, nit, `suggested_next_step_commands` comment (`completeness_report.py:~1409`) said BLOCKED findings need a manual edit because "`apply` can't add or restructure steps". Disposition: fixed `139283de5` (BLOCKED command descriptions also drop the retired rationale; `by_source` is live in detail-coverage guidance and stays).
- G1, governance, `CLAUDE.md` changed (22 additions, 42 deletions). Disposition: pending (same item as A2).

Application: defect class is live guidance naming removed application authority; searches covered retired commands/modules/handler, `CORRECTNESS_INTRO_BARE`, `by_source`, tracked `.claude` copies, and "apply withheld/verb/walk" across production, integrations, local skills and live audit docs. Post-fix no retired reference remains in production, integrations, `.claude` or the live audit guide. Full suite 14,705 passed, 67 skipped (`.tmp/completeness-apply-retirement.pass-2-tests.log`); generic reconcile/data-contract walks, #519's route and historical evidence excluded.

### Pass 3 (2026-11-04, `7d0d7c0ce`, 76 files)

Three low/nit findings; no functional regression. The reviewer read this ledger first and repeated no earlier disposition.

- H1, low, dead opt-in hook `_create_result_sink` in `cmd_create` (`plan_tool/cli/authoring.py:959-966`) whose only setters (`direct_cmd.py:331`, `:527`) are gone; `TestCmdCreateResultSink` (`tests/test_create.py:13508`) and `tests/cli/test_authoring_cmds.py:1165` still pinned it. Disposition: fixed `2c4a3f518` (block and four command-hook tests removed; no-sink test retargeted to ordinary create with its backend assertions kept).
- H2, low, removed test `TestCarriedFindingsWiring::test_high_impact_advisory_audit_finding_is_reported_but_not_in_completeness_open_set` covered surviving #85 behavior (no conceptual finding reaches `apply_finding`, both axes persist unapplied to the `-completeness.json` sidecar, `impact="high"` survives). Disposition: fixed `8aa3a5319` (restored as `TestConceptualAuditReportPersistence::test_iterate_keeps_conceptual_axes_unapplied_and_preserves_high_impact`; removing conceptual-completeness persistence makes it fail, `.tmp/completeness-apply-retirement.pass-3-mutation.log`).
- H3, nit, test names/docstrings in `tests/test_review_walk.py`, `tests/test_review.py:9096`, `tests/test_launcher.py:4935` describing a live `completeness-apply` walker or lane. Disposition: fixed `e261e7356` (wording only, assertions unchanged; structural-route commentary stays #519's).
- Out of scope: #519 comment rewording (`review_walk.py:367`, `test_review_walk.py:4029`); #369 and #520 untouched; launcher restoration-safety plumbing (`launcher.py:~3152`) may now serve only `detail --jobs` and the review walk, untraced, backlog only if the owner wants it recorded; pre-existing pyflakes warnings (`completeness_report.py:58`, `authoring.py:32`) identical on `origin/main`. Advisory `DATA_CONTRACT.md` blank lines: declined as non-actionable at this pass (normalized after pass 5).

Application: invariant is that removing dedicated command authority leaves no exclusive handoff hook while keeping regression coverage of surviving audit behavior; no result-sink symbol remains. Full suite 14,702 passed, 67 skipped (`.tmp/completeness-apply-retirement.pass-3-tests.log`); four exclusive hook tests retired and one regression restored account for the three-test reduction.

### Pass 4 (2026-11-04, `aad6f78d2`, 81 files)

No material defects or functional regressions; one nit.

- J1, nit, unused `import argparse` at `tests/test_create.py:9`, left by pass 3's removal of `TestCmdCreateResultSink` (same class as pass 1 finding 1; `uvx pyflakes` confirms). Disposition: fixed `9236fea4e` (sole import removed after verifying no other reference). Full suite 14,702 passed, 67 skipped (`.tmp/completeness-apply-retirement.pass-4-tests.log`).
- Advisory, none actioned: #519 and #369 fences hold; `experiments/minimize-claude/LESSONS.md:367` is #520 territory; `docs/history/backlog-decisions.md:363` is dated history; `MISSION.md:36` and `docs/ARCHITECTURE.md:205` read as generic or historical and were untraced; over-long comment lines from rewording are style only; G1 stays pending.

### Pass 5 (2026-11-04, merge-base `465e493fc` to `d7f33ecbb`, 30 commits, 81 files)

**No actionable findings; verdict Approve.** Coverage limits: the roughly 6,000-line `tests/cli/test_completeness_cmd.py` rewrite and the deleted modules were not read line by line; the rest of the diff was read, searched by identifier and vocabulary, and checked with ruff `F` against `origin/main` (no new unused or undefined names).

- Suggestion 1, `BACKLOG.md` #256 still named the retired verb in its render target and acceptance criterion (g). Disposition: fixed (documentation-only follow-through: #256 now names the surviving finding anchors, saved readers and `apply_finding` caller context, with no new application authority or scope).
- Suggestion 2, blank lines left in `DATA_CONTRACT.md` (~1766-1785) after the parallel-replay paragraphs and a missing blank line before `#### Escalate-to-split outcome`. Disposition: fixed (spacing normalized).
- Out of scope: `.plan-tool/lessons/project.md` and `project-citations.jsonl` still carry `completeness_apply_parallel.py`/`WorktreePool` bullets, owned by #520; `_correctness_apply` keeps an "apply" name but is live (gates bare-plan wording at `completeness_phases.py` 3621, 3666, 3682) and is not renamed; launcher restoration-safety consolidation recorded as declined, with no speculative cleanup filed without verified evidence.
- Verified clean: retired-surface searches over `plan_tool/`, `prompts/`, `integrations/`, `.claude/`, `RUNBOOK.md`, `README.md`, `CAPABILITIES.md`, `docs/cli`, `docs/how-to`, `docs/reference`; parser tests assert exit 2 and `invalid choice` for the three retired commands; `--commit` is accepted on exactly `run`, `detail`, `completeness-audit` and `manifest`; `apply_finding(record_verdict=False, verdict_observer=...)` at `review_actions.py:594` is unchanged; `test_files_coherence_findings_do_not_promote_allowed_mentions` pins the one deliberate behavior change; `test_saved_apply_annotations_remain_readable_without_apply_command` covers legacy annotations.

## Convergence status

**Low-yield convergence, 2026-11-04.** Five completed Claude skill reviews are retained above. Pass 4 has one nit and no material defects (its unused import is fixed at `9236fea4e`). Pass 5 independently reviews the full updated diff at `d7f33ecbb` and reports **no actionable findings**. These are two consecutive low-yield rounds after the substantive pass-3 corrections. All findings have explicit dispositions. The loop stops under the repository's severity-aware policy; this is low-yield convergence, not a claim that every round is clean or every diff line is independently re-read.

Final regression evidence after optional documentation follow-through: 14,702 passed, 67 skipped in 64.61 seconds (`.tmp/completeness-apply-retirement.final-claude-tests.log`). No runtime source changes follow pass 5. The restored persistence test is mutation-verified; tracked skill copies match their canonical sources. Prepared local code and plan-status branches are refreshed from the final committed work through the repository split script; pre-Claude snapshots are retained under suffixed branch names. Publication is verified in the Publication section above.

Open items: #519 (unreachable structural opt-in and its comment wording), #520 (stale lessons), #369 (untouched, independent), and the pending Architect-tier review of the `CLAUDE.md` rule edits (A2/G1).
