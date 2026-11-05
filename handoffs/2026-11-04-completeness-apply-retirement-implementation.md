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
Before execution, `reconcile-plan --all --no-walk -y` saves
`reports/20261104-130427.json`; the semantic review identified obsolete step-5 paths, wrong #367 ownership,
and removed Jira-grade wording. Its already-built suggestions are token matches
contradicted by the semantic review; no step status changes follow. The correction
also aligns seed, backlog, and documentation paths and includes Cursor guidance
and the glossary. Bare-stage completeness application remains withheld. The
bounded correction ensures retirement does
not widen into unrelated application authority; judged corrections retain generic application
and deterministic repair authority, and preserve #369's independent scope.
The seed remains archived and inert, not a competing scope owner.

Both audit gates use `completeness-audit completeness-apply-retirement
--iterate --commit --audit-passes 1 -y` with backend Codex, model
`gpt-6.1-sol`, and closed stdin. Bare report
`reports/20261104-130709-completeness.md` records 0/6 details, zero conceptual
findings, confirmed coverage, current revision, and a fresh conceptual call.
The sole heuristic `plan-claim-vs-delivery-caca4275` names deliberately preserved
`apply_finding`; it does not justify plan expansion.

One-shot `detail --commit -y` authors all six details. Its tail saves
`reports/20261104-132734-completeness.md`, with zero findings. The iterative
detail-grounded gate adds `--reuse-audit` and saves
`reports/20261104-140106-completeness.md`: 6/6 details, zero open findings,
confirmed coverage, current revision, explicit conceptual-call reuse, and an
advisory-only result. There is no conceptual correction loop requiring a
three-snapshot trajectory. These records certify the authored bundle, not
implementation delivery; the implementation and post-run reviews below own
that evidence. Do not rerun pre-execution plan-mutating audits on executed work.

## Execution and recovery

Commands use `uv run plan-tool --backend codex --model gpt-6.1-sol` with closed
stdin and `-y`. `run completeness-apply-retirement --all --commit` advances
steps 1 and 2 through green full-suite gates, then stops step 3 at its test gate.
The implementation subprocess commits its changes at `b25c6f5dc`; eight tests
in `tests/test_review_walk.py::TestCliCompletenessApplySubcommand` still invoke
the removed command or monkeypatch its deleted walk seam. Focused reproduction
confirms all eight failures. The class and its two exclusively used fixtures
are removed at `1d3aa6401`; shared walk coverage remains. A full suite passes
with 14,705 passed and 67 skipped. `run completeness-apply-retirement --step 3
--accept --commit` reruns acceptance and advances the step without a backend
call. The resumed `run --all --commit` finishes steps 4–6 with green full-suite
gates. No status is edited by hand.

## Reconciliation and code review

Both sweeps use:
`uv run plan-tool --backend codex --model gpt-6.1-sol reconcile-code completeness-apply-retirement --all --no-walk -y < /dev/null`.
All three code steps are included; the three explicit non-code steps are skipped.
Each report is retained under the plan's `reports/` directory.

| Evidence | Result and disposition |
| --- | --- |
| `20261104-144231-run-reconcile.json`, step 1 | One nit: stale command/automatic-conceptual-repair explanations. Confirmed by identifier and vocabulary searches across report, tail, split, merge, and invoker docstrings. `bf5ead546` corrects the full documentation class without runtime changes. |
| `20261104-144415-run-reconcile.json`, step 2 | Zero findings. |
| `20261104-144608-run-reconcile.json`, step 3 | Zero findings. |
| Confirmation reports `20261104-144955`, `20261104-145334`, `20261104-145531` | Zero findings across all three code steps after the correction. |
| `codex review -c 'model="gpt-6.1-sol"' --base origin/main`, reviewed head `bf5ead546` | Completed with no actionable regressions. Full diff covers correctness, completeness, command wiring, surviving audit paths, and compatibility. The reviewer reports 1,337 focused tests passing. Later changes add release/review documentation only. |

The code-review conclusion is: “No actionable regressions were identified in
the command retirements or remaining audit paths.” Its captured transcript is
`.tmp/completeness-apply-retirement.review-1.log`; this ledger retains the
conclusion and scope because scratch logs are transient.

## Final validation

- `uv run pytest tests/ -q -n auto` passes independently: **14,705 passed,
  67 skipped in 61.74 seconds**. Captured log:
  `.tmp/completeness-apply-retirement.isolated-tests.log`.
- A concurrent validation attempt records two worker crashes in unchanged
  data-contract path-reference tests; the reviewer independently records a
  filesystem-traversal timeout. These are not established code regressions.
  The standalone green rerun is the final regression evidence; no timeout,
  worker policy, or unrelated data-contract logic changes follow from them.
- `git diff --check` passes; #369 exact comparison passes.
- No post-execution plan-mutating reconciliation or design audit runs.

## Publication

[Implementation PR #163](https://bitbucket.org/protagona/plan-tool/pull-requests/163)
and [plan-status PR #164](https://bitbucket.org/protagona/plan-tool/pull-requests/164)
are verified merged, in that order. `git fetch origin main` resolves to
`cf303fe29`; path-scoped diffs against `BACKLOG-376-code` and `BACKLOG-376-plan`
are empty for their respective snapshots. The item has no promoted Jira key;
BACKLOG #376 is the source record. No additional publication is pending.

Claude review uses the `claude-personal` alias. The ordinary CLI's expired
login prevented two review starts; those attempts establish no review evidence.
The five completed rounds below establish the retained convergence result.

## Review pass 1 — /code-review high findings (2026-11-04)

**Reviewed commit:** `a5ac60bca71e9609ffe624322cfb4cb3839ad3f2` (clean tree).
**Scope:** `origin/main...implement/completeness-apply-retirement` (73 files).
**Method:** Report-only `/code-review` at `high`. The reviewer ran
`uv run pytest tests/ -q -n auto -m "not integration"` (13841 passed, 66
skipped; log `.tmp/completeness-apply-retirement.review-tests.log`). Integration
tests were not run. The reviewer's pyflakes claims were re-checked
here by `uvx pyflakes` and by grep; reviewer line numbers were off, so the
lines below are the verified ones.

**Result:** no correctness bugs and no regressions to create/detail repair,
review/reconcile routes, persisted schemas, legacy readers, blocking policy or
exit codes were found. Seven low or nit findings remain, all dead code or stale
prose.

### Findings (in scope, low/nit)

#### 1. Unused module imports left by the deletions — nit [CONFIRMED]
`plan_tool/cli/completeness_phases.py:68,77,79,95` — `DetailFormatError`,
`GRANULARITY_SPLIT_SOURCE` (also redefined by function-local imports at
749/843/1172/3897), `UnsupportedPlanFormatVersionError`, `success`.
`plan_tool/cli/completeness_cmd.py:31` — `warn`. Pyflakes is clean for these
names on `origin/main`. Failure scenario: names read as live module-scope
dependencies and fail any later lint step.
Smallest correction: delete the five imports (and the module-level
`GRANULARITY_SPLIT_SOURCE` if the local imports are kept).
Verification note: `completeness_cmd.py:55-56` (`_finding_progress_label`,
`_fmt_finding_counts`) are also unused there, but a pre-existing comment at
`completeness_cmd.py:44` documents them as deliberate re-exports; the same
imports exist on `origin/main` (`:91-92`). **Not a finding.**
**Disposition:** fixed `3a200d72b` — remove the five unused module imports; retain deliberate re-exports and all function-local imports.

#### 2. Stale "direct pipelines" comment — nit [CONFIRMED]
`plan_tool/create.py:10571` — "direct pipelines stop from this result field".
`direct-run` and `direct-jira` are retired; `authoring.py` is the only consumer.
Vocabulary survivor of the removed concept (CLAUDE.md § "Documentation is
forward-looking"). Smallest correction: reword to name `authoring.py`.
**Disposition:** fixed `3a200d72b` — name the surviving `cli/authoring.py` consumer; its `iteration_stage_failure` call sites remain unchanged.

#### 3. Stale apply-walk rationale on `open_findings` — nit [CONFIRMED]
`plan_tool/cli/completeness_phases.py` near `:3876-3884` — the comment keeps
"fruitless `--iterate` re-run"/unreached-bucket reasoning for a value that is
always `[]`. Smallest correction: reduce to a one-line note or drop the variable.
**Disposition:** fixed `3a200d72b` — replace the rationale with one line; keep the report input and runtime behavior unchanged.

#### 4. Apply-walk wording in `_latest_blocking_findings` — low/nit [PLAUSIBLE]
`plan_tool/convergence_diagnosis.py:~1544` — the docstring says "an apply walk's
applied/declined findings are no longer open evidence". The filtering stays
correct for legacy sidecars (live legacy-reader contract), so only the wording
is stale. Smallest correction: reword as "legacy sidecars that carry
applied/declined annotations". **Disposition:** fixed `3a200d72b` — the cited text is in `_open_medium_plus`, not `_latest_blocking_findings`; describe legacy annotations. Existing `test_saved_apply_annotations_keep_their_history_meaning` pins the preserved behavior.

### Advisory / out-of-scope observations (not findings)

- **A1 — medium `granularity-split` replay persisted with no consumer**
  (`completeness_phases.py:~3896-3911`, `mixed_split_recs`; also
  `split_escalation_target`, `halt_on_applied`, `guard_saved_directive`,
  `extra_apply_sources`). The reviewer ranks it most severe. It is the
  unreachable structural opt-in that BACKLOG #519 owns, and the issue
  statement for this review preserves that deferral. Related stale comment
  wording ("replayable") should be updated by #519, not here.
  **Disposition:** deferred to BACKLOG #519 — preserve the explicit structural-route scope exclusion; no implementation or extra cleanup here.
- **A2 — CLAUDE.md rule edits require `architect`-tier review.** The diff
  rewrites several rules; the handoff's opening already notes the Architect
  reviews CLAUDE rule changes. A process reminder for PR routing, not a code
  defect. **Disposition:** retained process requirement — route CLAUDE changes to Architect review in the code PR; no code correction required.
- **A3 — `docs/evidence/public-release-final-selection-verification-20261021.json`
  (and the distribution-verification JSON) list now-deleted files**
  (`docs/cli/completeness-apply.md`, `docs/cli/direct-run.md`,
  `docs/how-to/pipeline/direct-pipeline.md`). These files are unchanged by the
  branch (dated historical records); no reader tool was found. Risk only.
  **Disposition:** declined — retain dated historical evidence unchanged under the plan’s explicit no-migration boundary; no active consumer is established.

## Pass 1 application evidence

The defect class is deletion leftovers: unused module dependencies and stale
explanations must not describe retired consumers as live. Before editing,
identifier searches cover the five imports, `stage_failure`, `open_findings`,
`_latest_blocking_findings`, and the actual `_open_medium_plus` owner. Vocabulary
searches cover direct pipelines, fruitless iteration, unreached buckets, apply
walks, and applied/declined annotations. The relevant sites are the two
completeness modules, `create.py`, and `convergence_diagnosis.py`; all are
corrected at `3a200d72b`. Function-local granularity imports, deliberate
transitive re-exports, #519's preserved route, and historical evidence stay.
No new behavioral test is needed for import removal and comment-only edits.
The full suite passes: **14,705 passed, 67 skipped in 68.75 seconds**; log
`.tmp/completeness-apply-retirement.pass-1-fixes-tests.log`. Identifier and
vocabulary rechecks confirm the cited obsolete wording and unused module
imports are absent. No runtime predicate, annotation handling, or schema changes.

## Convergence status

**Low-yield convergence, 2026-11-04.** Five completed Claude skill reviews are
retained below. Pass 4 has one nit and no material defects; its unused import
is fixed at `9236fea4e`. Pass 5 independently reviews the full updated diff at
`d7f33ecbb` and reports **no actionable findings**. These are two consecutive
low-yield rounds after the substantive pass-3 corrections. All findings have
explicit dispositions. Stop the review loop under the repository's severity
aware policy; this is low-yield convergence, not a claim that every round is
clean or every diff line is independently re-read. Pass 5's coverage limits
remain in its report below.

Final regression evidence after optional documentation follow-through:
**14,702 passed, 67 skipped in 64.61 seconds**, log
`.tmp/completeness-apply-retirement.final-claude-tests.log`. No runtime source
changes follow pass 5. The restored persistence test is mutation-verified;
tracked skill copies match their canonical sources. Prepared local code and
plan-status branches are refreshed from the final committed work through the
repository split script; pre-Claude snapshots are retained under suffixed
branch names. Publication is verified under the Publication section above.

## Review pass 2 — claude-personal /code-review high (2026-11-04)

# Claude review pass 2: completeness-apply-retirement

**Skill invoked:** `code-review` (local-diff form) at high effort, report-only.
**Reviewed range:** `origin/main...HEAD` at `e6e1f32af`. The review was report-only: I made no edits, commits or remote comments, ran no tests, and used no TWG tools. I spot-checked the first three findings below with grep after the skill returned.

**Result:** 8 findings, none above low or medium. I found no functional regression in the removed-command surfaces, and no exit-code, schema or legacy-reader break. All are deletion leftovers or governance items. F4 and F5 overlap the deferred A1 (#519), so treat them as advisory.

## Actionable findings (stale text left after the deletion)

| # | Sev | Location | Scenario | Evidence | Smallest remedy |
|---|---|---|---|---|---|
| F1 | low | `plan_tool/cli/completeness_phases.py:3720`; `plan_tool/completeness_report.py:855`, ~2146, ~2300 | Bare-plan audit output says "informational in this bare-plan audit — apply is withheld until a detail bundle exists". The updated DIRECTIVES and CLAUDE.md tell the operator to hand-edit plan-level gaps before `detail`, and no apply verb exists any more. | Confirmed by grep at 3720 and 855. At 2146 the text is `"axis are withheld until a complete detail bundle exists, so "`. I did not locate the ~2300 "apply verb is not named" text. | Reword these lines to "detail-owned remedy, hand-edit" and drop the apply vocabulary. Also check any tests that pin the old strings. |
| F2 | low | `docs/how-to/pipeline/audit.md:710, 822, 825` | The live doc cites `cmd_completeness_apply()`, the deleted `completeness_apply_parallel.py` / `run_parallel_apply`, and a "Conceptual gap apply walk" module-map row. A reader following the map finds nothing. | Confirmed by grep. | Delete the row at 825. Remove the module at 822. Rephrase line 710 without the symbol. |
| F3 | medium (if the copies are consumed) | `.claude/skills/plan-tool/DIRECTIVES.md`, `.claude/skills/plan-tool/SKILL.md` | These tracked, regular-file copies still document the retired commands: 13 matches for `completeness-apply\|direct-run\|direct-jira` in DIRECTIVES.md and 3 in SKILL.md. The `integrations/` originals were rewritten, but these copies were not touched in this diff. An in-repo session loading them would run commands that now fail with an invalid-choice error. | Confirmed: tracked, mode 100644, mtime Oct 22. | The parent should check whether a sync or generator step owns these copies. If so, regenerate them. If not, hand-sync them. |
| F4 | low | `plan_tool/cli/completeness_phases.py:3881` | `mixed_split_recs` is still persisted "for saved readers" and the comment calls it "replayable", but the only walker that replayed it is gone. | Per the skill. This overlaps A1 and #519. | Reword the comment only, to say the recs are retained for saved-report readers and that nothing replays them. Do not remove the behavior. |
| F5 | low | `plan_tool/cli/review_actions.py:~217, 947, 1509, 1515` | The `granularity-split` dispatch branch is unreachable from production, and its comments still name "the completeness-apply granularity-split branch". | Per the skill. A1 (#519) defers the disposition. | Only the comments that name the deleted lane need rewording. Leave the branch for #519. |
| F6 | nit | `plan_tool/review_walk.py:~290` | The reworded `_APPLY_AS_FINDING_SOURCES` comment dropped the reason `plan-correctness` is excluded: the generic walks can load a `-completeness.json` sidecar, and auto-applying would bypass the detail-bundle gate. A later contributor could add it to the base set. | Per the skill. | Restore one clause stating that invariant. |
| F7 | nit | `plan_tool/completeness_report.py:~1409` | A comment in `suggested_next_step_commands` says BLOCKED findings need a manual edit because "`apply` can't add or restructure steps". That rationale is gone. | Per the skill. | Reword the comment. Also confirm that `by_source` still has a live use after the deleted files-coherence block. |

## Process item

**G1 (governance):** `CLAUDE.md` changed, with 22 additions and 42 deletions in this diff. The file's own rule requires architect-tier review through the pull-request flow, and I take that to be A2 in your ledger. Record it in the handoff and PR so it is not missed.

## Out-of-scope or deferred (not proposed for implementation)

- A1 / #519: unreachable `granularity-split` and structural opt-in machinery. F4 and F5 only ask for comment wording.
- A3: preserved historical evidence.
- #369 and #520: deliberately untouched.

## Advisory

- Run a post-fix vocabulary sweep for `apply is withheld`, `apply verb`, `apply walk`, `completeness-apply` and `direct-run` across `plan_tool/`, `docs/`, `.claude/` and `integrations/`. Exclude the evidence and handoff files, which are preserved history. F1 to F3 are all misses from the identifier sweep or the vocabulary sweep.

**Not found:** no behavioral regression in create/detail deterministic repair, the review/reconcile routes, persisted schemas, legacy readers, audit blocking policy, or exit codes.

### Pass 2 dispositions and evidence

| Finding | Disposition |
| --- | --- |
| F1 | Confirmed; fixed `139283de5`. Bare output and report prose distinguish plan-level edits now from detail-only remedies later. Remove obsolete apply-command explanations without changing stage predicates or exit codes. Update the tests that pin those strings. |
| F2 | Confirmed; fixed `139283de5`. Remove deleted command/module references and the obsolete module-map row from the live audit guide; preserve the surviving data-contract reader contract. |
| F3 | Confirmed; fixed `139283de5`. Both files are tracked regular copies consumed as the local skill. `cli/skill_cmd.py:cmd_install_skill` establishes their canonical owners: `integrations/claude/SKILL.md` and `integrations/shared/DIRECTIVES.md`. Refresh copies from those sources without independently editing their rules. |
| F4 | Deferred to #519, as pass 1 A1 explicitly records. Keep the existing persistence and the route's comment disposition in that separate effort. |
| F5 | Refuted as a current production-text defect: no `completeness-apply` or deleted-lane comment remains in `cli/review_actions.py`. The reviewed target comments describe preserved dispatch semantics. Unreachable route disposition remains #519. |
| F6 | Declined proposed detail-gate rationale: that command gate is retired. The current comment correctly requires caller opt-in and excludes generic design auto-apply; existing dispatch tests pin both the exclusion and explicit-opt-in carve-out. Do not restore a nonexistent gate as present design. |
| F7 | Confirmed comment fix at `139283de5`; the related BLOCKED command descriptions also drop retired apply-capability rationale. `by_source` is live in detail-coverage guidance and stays. |
| G1 | Retain Architect review requirement for CLAUDE rule changes in the code PR. No session approval/merge is authorized. |

The defect class is live guidance naming removed application authority. Before
editing, identifier searches cover the retired commands, modules and handler,
`CORRECTNESS_INTRO_BARE`, `by_source`, and tracked `.claude` copies. Vocabulary
searches cover withheld apply, apply verb, apply walk, and the structural-route
comments across production, integrations, local skills, and live audit docs.
Sites: report introductions/next steps and comments, grouped audit guidance,
audit-guide module map, tracked skill copies, and their existing report/CLI
tests. Generic reconcile/data-contract walks remain real behavior; #519's route
and historical evidence remain excluded. Post-fix identifier search returns no
retired command/module references in production, integrations, `.claude`, or
the live audit guide. Canonical and installed skill bytes match.

Focused validation initially exposes three assertions pinning old report prose;
they now assert the plan-level/detail-only distinction. The final full suite
passes: **14,705 passed, 67 skipped in 80.08 seconds**, log
`.tmp/completeness-apply-retirement.pass-2-tests.log`. Temporarily restoring the
pre-fix report and grouped renderer makes both targeted regression assertions
fail; fixed source is restored afterward (mutation log
`.tmp/completeness-apply-retirement.pass-2-mutation.log`). No runtime policy,
persisted schema, generic caller, or historical artifact changes.

## Review pass 3 — claude-personal /code-review high (2026-11-04)

## Claude review pass 3: completeness-apply-retirement

**Skill invoked:** `engineering:code-review` through the Skill tool, at high effort, local-diff form.
**Reviewed range:** `origin/main...HEAD` at `7d0d7c0ce` (76 files). I made no edits, commits, remote comments or test runs, and used no TWG tools. I ran `pyflakes` and read-only `rg`/`git` commands. I read the handoff ledger first, so none of the findings below repeat a pass 1 or pass 2 disposition.

**Result:** no functional regression found in the removed-command surfaces, `create`/`detail` deterministic repair, the review/reconcile routes, persisted schemas, legacy readers, blocking policy or exit codes. I found three low or nit findings, all deletion leftovers or a test-coverage gap.

### Actionable findings

| # | Sev | Location | Failing scenario | Evidence | Smallest remedy |
|---|---|---|---|---|---|
| H1 | low | `plan_tool/cli/authoring.py:959-966` (`_create_result_sink`) | `cmd_create` still has an opt-in hook that deposits `CreateResult` into `args._create_result_sink`. Its comment names "the direct-pipeline verbs" as the caller, and those verbs are gone. Nothing in `plan_tool/` sets the attribute now, so it is dead production code with a retired-concept comment. | On `origin/main` the only setters were `direct_cmd.py:331` and `:527`. At HEAD there are none under `plan_tool/`. `tests/test_create.py:13508` (`TestCmdCreateResultSink`) and `tests/cli/test_authoring_cmds.py:1165` still pin the hook. The plan and handoff never mention `_create_result_sink`, and the pass 1 and pass 2 sweeps did not cover it. This is "exclusive machinery" under the stated intent. | Delete the `result_sink` block, remove or retarget `TestCmdCreateResultSink` and the no-sink case in `test_authoring_cmds.py`. If you keep it deliberately, reword the comment to say it has no in-tree consumer. |
| H2 | low | `tests/cli/test_completeness_cmd.py`; removed `TestCarriedFindingsWiring::test_high_impact_advisory_audit_finding_is_reported_but_not_in_completeness_open_set` | The test is not specific to the retired verb. It ran `completeness-audit --iterate --yes` and asserted three things. No conceptual finding reaches `apply_finding` (`captured == []`). `plan-correctness` and `plan-completeness` findings persist to the `-completeness.json` sidecar unapplied. The `impact="high"` field survives the round-trip. | I extracted the 119 test names the branch removed from this file (via `git diff`). 63 of them no longer exist anywhere in `tests/`. Most are apply-walk, files-coherence-writer or bare-withheld tests, which is fine. This one tests surviving #85 behavior. A search for `corr-alpha`, `corr-beta` and `comp-x` in `tests/` finds nothing. The remaining iterate tests (around `:9660-9727`) assert only `stop_reason == "terminal_hand_apply"`, not sidecar persistence or the absence of dispatch. Only the removed test's docstring mentions `completeness-apply`. | Restore the test with the docstring reworded ("persisted unapplied for judged edits"). This protects the one exemption the whole retirement relies on, so I rate the gap low but real. **PLAUSIBLE:** I did not mutation-check it. If a test elsewhere covers sidecar persistence through `main(... --iterate)`, downgrade this. |
| H3 | nit | `tests/test_review_walk.py:2653, 2666-2686, 4029, 4045`; `tests/test_review.py:9096`; `tests/test_launcher.py:4935` | Test names and docstrings describe a live `completeness-apply` walker or lane. One says `completeness-apply --anchor` accepts the anchor slug, and that flag is gone. `test_plan_correctness_dispatch_scoped_to_completeness_apply` names a nonexistent caller. | The assertions are still valid. They test the `extra_sources` opt-in, and `data_contract_cmd.py:425` is a live caller. Only the wording is stale. The pass 2 vocabulary sweep covered production, integrations, `.claude` and docs, but not `tests/`. | Reword the docstrings and comments. Rename the one test to something like `..._requires_caller_opt_in`. Do not touch the assertions. |

### Out-of-scope or deferred (not proposed for implementation)

- **#519:** the `granularity-split` opt-in (`split_escalation_target`, `halt_on_applied`, `guard_saved_directive`, `mixed_split_recs`) now has no production caller. `review_walk.py:367` and `test_review_walk.py:4029` still say "the completeness-apply lane". Reword them only as part of #519.
- **#369 and #520:** untouched, as intended.
- **Launcher restoration-safety plumbing:** `launcher.py:~3152` still has restoration-safety code that `DATA_CONTRACT.md` described for "deferred workers". The deleted DATA_CONTRACT text described the parallel apply path. This may now be unused beyond `detail --jobs`; I did not trace it. Put it in the backlog only if you want the consolidation recorded.
- **Pre-existing `pyflakes` warnings:** unused imports in `completeness_report.py:58` (`compute_plan_fingerprint`) and `authoring.py:32` (`os`) are identical on `origin/main`, so they are not regressions. The `completeness_cmd.py:47` re-exports are the documented deliberate ones.
- **Historical evidence JSON and CLAUDE.md Architect review (G1):** unchanged from pass 1 and pass 2. The CLAUDE.md edits still need Architect-tier review in the PR.

### Advisory

- `DATA_CONTRACT.md` has leftover consecutive blank lines where the parallel-replay paragraphs were removed (around `:1773-1790`). This is cosmetic.
- Add `tests/` to the vocabulary sweep (`completeness-apply`, `direct-pipeline`, `apply walker`, `--anchor`). H1 and H3 are the same class: leftovers outside the directories the earlier sweeps covered.

### Checked and clean

- **Removed-command surface:** no references to the removed commands or modules remain in `plan_tool/`, `prompts/`, `integrations/`, `.claude/` or live docs. This covers `COMMAND_MODULES`, `CANONICAL_COMMAND_ORDER` and `_LOCKED_MUTATING_COMMANDS`. `test_cli_parser.py:223-244` asserts the invalid-choice rejection.
- **Skill copies:** the `.claude/skills/plan-tool/` copies match `integrations/shared/DIRECTIVES.md` and `integrations/claude/SKILL.md` byte for byte.
- **`by_source` in `suggested_next_step_commands`:** still used, by the `detail-coverage` branch at `completeness_report.py:1437`.
- **Legacy annotation reader:** the renamed test `test_saved_apply_annotations_keep_their_history_meaning` keeps the legacy applied/declined behavior pinned.
- **Deleted test files:** none of the deleted `test_direct_cmd` or `test_completeness_apply_parallel` tests covers a surviving surface that I could find. I checked removed test names in `test_review_walk.py`, `test_completeness_report.py`, `test_data_contract.py` and `test_cli_reference.py`, and all the lost ones are apply-specific.
- **Docs claims:** the `README`, `TRACKING`, `GLOSSARY` and changelog claims match the code, and none leaves a dangling pointer.

### Pass 3 dispositions and evidence

| Finding | Disposition |
| --- | --- |
| H1 | Confirmed; fixed `2c4a3f518`. Identifier search finds no surviving production setter of `_create_result_sink`; vocabulary search identifies only the removed direct-pipeline hook and its exclusive tests. Remove that block and four command-hook tests. Retarget the no-sink test to the surviving ordinary create behavior without changing its backend assertions. |
| H2 | Confirmed; fixed `8aa3a5319`. Restore the integration regression as `TestConceptualAuditReportPersistence::test_iterate_keeps_conceptual_axes_unapplied_and_preserves_high_impact`. It asserts no conceptual apply dispatch, both axes in the saved sidecar, and high-impact preservation. Existing terminal-hand-apply tests do not cover that full persistence contract. |
| H3 | Confirmed non-structural test descriptions; fixed `e261e7356`. Reword the generic opt-in, readable anchor, shared finding prompt, sidecar, and parallel-detail tests without changing assertions. Structural-route test commentary remains #519's explicit deferral. Rejection tests, historical examples, and legacy fixture strings remain intentional. |

The invariant is that removing dedicated command authority leaves no exclusive
handoff hook while preserving regression coverage for surviving audit behavior.
Pre-edit identifier/vocabulary searches include `_create_result_sink`, direct
pipelines, retired-command names, caller opt-ins, readable anchors, and sidecar
persistence across source and tests. Post-edit no result-sink symbol remains.
The restored test and ordinary-create test pass in isolation. Temporarily
removing conceptual-completeness persistence makes the restored test fail;
the source is restored immediately (log
`.tmp/completeness-apply-retirement.pass-3-mutation.log`). Full suite:
**14,702 passed, 67 skipped in 76.96 seconds**, log
`.tmp/completeness-apply-retirement.pass-3-tests.log`. Four exclusive hook tests
retire and one surviving-contract regression returns, accounting for the
three-test reduction. No deferred structural-route behavior or restoration
safety plumbing changes. The cosmetic blank-line suggestion is declined as
non-actionable; pre-existing pyflakes warnings remain out of scope.

## Review pass 4 — claude-personal /code-review high (2026-11-04)

## Claude review pass 4: completeness-apply-retirement

**Skill invoked:** `engineering:code-review` through the Skill tool, at high effort, local-diff form.
**Reviewed range:** `origin/main...HEAD` at `aad6f78d2` (81 files). I read the full implementation ledger first, including pass 1–3 dispositions. I made no edits, commits, test runs or remote comments, and used no TWG tools. I ran `pyflakes` and read-only `rg` and `git` commands.

**Result:** no material defects and no functional regressions. I found one nit-level actionable finding, a deletion leftover from pass 3's own correction.

### Actionable finding

| # | Sev | Location | Failing scenario | Evidence | Smallest remedy |
|---|---|---|---|---|---|
| J1 | nit | `tests/test_create.py:9` (`import argparse`) | Commit `2c4a3f518` removed `TestCmdCreateResultSink`, whose helper annotation `"argparse.Namespace"` was the only use of `argparse` in the file. The import is now unused. This is the same class as pass 1 finding 1, so any later lint step fails on it. | `uvx pyflakes tests/test_create.py` reports `'argparse' imported but unused`. On `origin/main` the same check has no `argparse` hit, because the string annotation at the old line 13519 counted as a use. At HEAD `rg argparse tests/test_create.py` returns only line 9. | Delete line 9. No behaviour change. |

I also diffed `pyflakes` output for every changed `.py` file against `origin/main`. Only `argparse` in `tests/test_create.py` is new. The other differences are `redefinition of unused …` messages in `plan_tool/cli/authoring.py`, `tests/cli/test_authoring_cmds.py` and `tests/test_completeness_report.py`. I did not trace them to a cause, and they probably only differ in line numbers. The pass 3 review already recorded `authoring.py:32` (`os`) as identical on `origin/main`.

### Checks run and clean

- **Pass 3 corrections:**
  - The `_create_result_sink` block is gone from `cmd_create`, and no production or test reference remains outside archived plan details.
  - The inline split-proposal path through `cmd_create` is still covered by `tests/cli/test_authoring_cmds.py:5384`. The removed sink test was not the only coverage.
  - `_seed_repo_for_cmd_create` is still used by 10+ surviving tests.
  - The renamed `TestCreateCliAuthoring::test_cmd_create_writes_plan_with_stubbed_backend` keeps its backend assertions.
- **Restored regression test:** `TestConceptualAuditReportPersistence::test_iterate_keeps_conceptual_axes_unapplied_and_preserves_high_impact` asserts three things:
  - `apply_finding` is never dispatched.
  - Both conceptual sources land in the `-completeness.json` sidecar.
  - `impact="high"` survives the round-trip.

  The handoff reports a mutation check on it.
- **Rewording commit `e261e7356`:** the changes in `test_review_walk.py`, `test_review.py`, `test_launcher.py`, `test_shell.py`, `test_review_actions.py` and `test_completeness_report.py` are comments and docstrings only. Assertions are unchanged, and the new test name is accurate.
- **Removed-command sweep:** no live reference to `completeness-apply`, `direct-run`, `direct-jira`, `direct-pipeline`, `run_parallel_apply` or `_create_result_sink` remains in `plan_tool/`, `prompts/`, `integrations/`, `.claude/`, `README`, `CAPABILITIES` or `docs/reference`.
  - Remaining hits are archives, historical docs, backlog records and plan seeds.
  - I also checked a few generic hits that use "apply walk" for the reconcile/review and data-contract walks, which are still real behaviour: `reconcile.py:870`, `data_contract_cmd.py:405`, `RUNBOOK` and `common-workflows`.

### Out-of-scope, advisory and optional polish (none proposed for action)

- **#519 and #369 scope fences:**
  - The `granularity-split` opt-in has no production caller. Its comments, including `review_walk.py` and the `test_review_walk.py` structural-route commentary, stay with #519.
  - #369 and #520 are untouched.
- **Historical references to the retired commands:** `experiments/minimize-claude/LESSONS.md:367` mentions the `completeness-apply` replay verb. That is #520 territory (stale lesson guidance). `docs/history/backlog-decisions.md:363` is dated history.
- **Possibly stale prose, not traced:** `MISSION.md:36` ("The audit→apply walk runs until it converges") and `docs/ARCHITECTURE.md:205` ("one shape `apply_finding` can't fix"). Both read as generic or historical, and I have not traced them to a live claim. This is optional polish only if the parent wants to reword them.
- **Optional wording:** `tests/cli/test_review_actions.py` and `tests/test_review.py` now have over-long comment lines from the reword. This is style only.
- **Governance (G1):** the `CLAUDE.md` rule edits still need architect-tier review in the code PR.

**Verdict:** clean apart from J1 (nit, one-line deletion). Nothing material remains.

**Disposition:** J1 confirmed and fixed by removing the sole `argparse`
import from `tests/test_create.py` after verifying no other reference remains.
The full suite passes: **14,702 passed, 67 skipped in 69.97 seconds**, log
`.tmp/completeness-apply-retirement.pass-4-tests.log`. All other observations
remain advisory or under their recorded backlog/governance owners. No additional
source changes follow from optional prose or formatting suggestions.

## Review pass 5 — claude-personal /code-review high (2026-11-04)

## Code Review: completeness-apply-retirement (`origin/main...HEAD`)

**Skill invoked:** `engineering:code-review` through the Skill tool, at high effort, report-only. I made no edits, ran no tests, made no commits, and published nothing.
**Reviewed range:** merge-base `465e493fc` (origin/main, PR #162) to `d7f33ecbb`. That is 30 commits and 81 files, +3,337/−13,134.

**Coverage.** I did not read every line of the roughly 6,000-line `tests/cli/test_completeness_cmd.py` rewrite or the deleted modules. I covered the rest of the diff and these checks:
- Read the full source diff outside the deleted modules and the two large rewritten files, plus the added lines of the rewritten `completeness_cmd.py` and `completeness_phases.py`.
- Searched HEAD by identifier and by vocabulary for the retired names.
- Ran ruff `F` rules on the touched modules against the same files at origin/main (details below).
- Checked the doc claims against the parser, code and the surviving tests.

### Summary
**No actionable findings.** I found no correctness, completeness, compatibility or behavior-change defect. The two items below are optional doc polish; I would not hold convergence on either.

### Critical Issues
None.

### Suggestions (optional polish, not defects)
| # | File | Line | Suggestion | Category |
|---|------|------|------------|----------|
| 1 | `BACKLOG.md` | 1795–1810, 1883 (#256) | #256, a deferred entry, still names the retired verb in two live places. One is the render target: "…carried-findings block, and the `completeness-apply` / `apply_finding` context". The other is acceptance criterion (g): "one focused integration fixture shows `completeness-apply` receives one class-wide finding". Both are conditioned on a command that no longer exists. Step 6 of the plan trims only entries that exist solely for the removed commands, and #256 is not one of them, so this was a defensible omission. The smallest remedy is to reword (g) and the context mention to the surviving consumers (`apply_finding` in `create`/`detail`, and the saved report), or to defer the wording to #256's own plan. | Forward-looking docs |
| 2 | `DATA_CONTRACT.md` | ~1766–1785 | Deleting the parallel-replay paragraphs left a run of blank lines after the "wasteful volume)." paragraph. It also left `#### Escalate-to-split outcome` directly after "…remains in the run-log." with no blank line. GFM still renders the heading, so this is cosmetic. The remedy is to restore one blank line before the heading and collapse the extra blanks. | Doc hygiene |

### Verified clean (evidence)
- **Retired surface.**
  - A search of HEAD for `completeness-apply`, `completeness_apply`, `direct-run`, `direct-jira`, `direct_cmd`, `apply_parallel`, `_create_result_sink` and `cmd_completeness_apply` returns nothing under `plan_tool/`, `prompts/`, `integrations/`, `.claude/`, `RUNBOOK.md`, `README.md`, `CAPABILITIES.md`, `docs/cli`, `docs/how-to` or `docs/reference`.
  - Remaining hits fall in these places:
    - `tests/`: intentional rejection assertions and a legacy-annotation fixture.
    - Archived seeds, historical docs, `docs/history`, `experiments/` and `handoffs/`.
    - Dated provenance in #74, #139 and #176.
    - `.plan-tool/lessons/*` (#520).
    - #519/#520 and their origin lines.
  - The installed skill copy `.claude/skills/plan-tool/DIRECTIVES.md` is byte-identical to `integrations/shared/DIRECTIVES.md`. It had 11 stale mentions at origin/main.
- **Dead and dangling code.**
  - Every helper deleted from `completeness_phases.py` (`_run_apply_walk`, `_resolve_saved_completeness_audit`, `_saved_audit_revision_is_current`, `_detail_bundle_staleness`, the data-contract walk helpers and the source-rank tables) has no remaining reference in source or docs outside #520.
  - `ruff --select F` on 19 touched source and test files, compared against origin/main, shows no new unused or undefined names. The four "new" lines are the same pre-existing F811 redefinitions, with a shifted line number in the message text.
- **Dispatch, parser and mutation-lock sites.**
  - `COMMAND_MODULES`, `CANONICAL_COMMAND_ORDER`, `_LOCKED_MUTATING_COMMANDS`, `cli/__init__.py`, `docs/cli/README.md` and the package-surface golden file are all swept. Parser tests assert exit 2 and `invalid choice` for all three retired commands.
  - `create`, `detail`, `jira`, `run`, `reconcile-code`, `completeness-audit` and `data-contract-apply` remain registered and are asserted so.
- **Preserved behavior.**
  - `data_contract_cmd.py` has no imports from the removed code.
  - The surviving review/reconcile walk still calls `apply_finding(record_verdict=False, verdict_observer=…)` at `review_actions.py:594`. That call is unchanged from main, so the deferred-recorder contract that `DATA_CONTRACT.md` still describes is intact.
  - `--commit` is accepted on exactly four surfaces in the parser: `run`, `detail`, `completeness-audit` and `manifest`. This matches the new directive text.
  - The `--max-stall-rounds` and `terminal_hand_apply` references in the docs exist in code.
  - The "each repair fingerprint dispatches at most once" claim is backed by `applied_fingerprints`.
  - `test_files_coherence_findings_do_not_promote_allowed_mentions` pins the one deliberate behavior change: the report no longer offers the deterministic `allowed_mentions` clear. It tells the reader to hand-edit.
- **Legacy and compatibility.** `test_saved_apply_annotations_remain_readable_without_apply_command` covers four annotation statuses, and persisted schemas are untouched. The `DATA_CONTRACT.md` verdict-token test still pins the six tokens and asserts that `replay_results` is absent.
- **Scope exclusions respected.** BACKLOG #369 is untouched, and #519 and #520 are filed with scope fences. No conceptual auto-apply is reconnected. The `review_walk.py` change is a comment and docstring edit only, and the `granularity-split` opt-in stays in place for #519.

### Out-of-scope observations (not for this change)
- `.plan-tool/lessons/project.md` and `project-citations.jsonl` still carry the instructional bullets about `completeness_apply_parallel.py`, `WorktreePool` and the source-rank dicts. That is #520, already filed.
- `_correctness_apply` in `completeness_phases.py:3583` keeps an "apply" name. It is live: it gates bare-plan wording at lines 3621, 3666 and 3682. Renaming it would be churn.
- The handoff notes that `launcher.py` restoration-safety plumbing may now be used only by the surviving review walk. That is optional consolidation; it should go in the backlog only if you want it recorded.

### Verdict
**Approve.** There are no actionable findings. The two optional polish items above do not affect behavior, and I would not count either as a material finding for the low-yield stopping rule.

### Pass 5 dispositions

No actionable findings. Optional #256 references are corrected to the surviving finding anchors, saved readers, and `apply_finding` caller context without assigning new application authority or expanding its scope. Optional `DATA_CONTRACT.md` spacing is normalized. These are documentation-only follow-through after the clean source review. All out-of-scope observations retain their existing #519/#520/#369 owners or explicit declined-consolidation disposition; no speculative cleanup is filed without verified evidence. Architect review of CLAUDE changes remains required.
