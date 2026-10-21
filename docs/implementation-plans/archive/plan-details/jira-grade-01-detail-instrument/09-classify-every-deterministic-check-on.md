> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Classify every deterministic check on the grade axis and make the jira-grade report surfaces grade-correct

## Summary

Step 8 made every deterministic detector individually dispatchable through one registry, with a single run-everything policy. This step adds the **grade axis as a policy over that registry** — each entry classified grade-independent, run-grade-only, or jira-grade-only — plus the jira bundle check that supplies what the run-grade detail readers no longer produce, and the report surfaces that would otherwise mix grades: the findings sidecar, the convergence diagnosis, the operator-guidance prose, and the stderr notice announcing what was withheld. The main files are `plan_tool/cli/completeness_phases.py` (the grade policy and `_persist_and_present_report`), `plan_tool/review.py` (`check_jira_grade_bundle` and the body-issue message slot), `plan_tool/completeness_report.py` (guidance producers and grade-correct renderer wording), and `plan_tool/cli/completeness_cmd.py` (the notice, the `--json` payload, the step 2 handoff). The key design decision: **grade is data on a registry entry, not a branch at a call site.** Step 8's source-level guard already fails the build when a detector bypasses the registry, so "a check ran without a grade class" cannot happen — this step's own guard is the narrower one that every registry entry *has* a class. On green, `plan-tool completeness-audit <name> --grade jira` is a supported surface end to end, a default run is byte-for-byte unchanged, and approx. 20–24 new tests pass.

## Table of Contents

- [Summary](#summary) — what this half ships and the one design decision
- [Why](#why) — why the grade axis is a policy, not a set of branches
- [Input](#input) — step 7's axis, step 8's registry, and the HEAD facts this step depends on
- [Files (creates vs edits)](#files-creates-vs-edits) — per-file edits; no new files
- [Implementation](#implementation) — the classification, the bundle check, the suppressions, the guidance prose
- [Tests](#tests) — classification coverage, then per-surface cases
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the references relevant to this step
- [Deferred](#deferred) — the sidecar decision and neighbours left alone

## Why

Step 7 pointed the conceptual audit at the selected grade's bytes under that grade's contract. That is not enough on its own: the deterministic battery still reads run-grade detail bodies, and several report surfaces read *saved history* or print *operator guidance* rather than findings. Any of them left run-grade under `--grade jira` puts two artifacts' judgments under one heading — the split brain.

Step 8 is what makes closing that tractable. Before it, the detectors were not addressable: `detect_suppression_shape`, `detect_claim_vs_delivery`, and `detect_orphaned_deliverable` ran inside fan-outs alongside grade-independent siblings, so skipping one meant skipping all — dropping grade-independent checks, which Out of scope forbids. With every detector a registry entry, classification becomes data rather than a restructure, and this step stays a small feature.

## Input

- **Step 7's grade axis**: `--grade {run,jira}` on `completeness-audit`, the rc-2 guards, purity forced off, the grade threaded to `render_plan_audit_prompt` and `audit_detail_bundle_status`, bare-step treatment for a missing jira artifact, note-instead-of-body for a mislabeled one, and the grade axis on `compute_detail_bundle_fingerprint`. This step consumes that axis; it does not re-declare flags or re-thread the prompt.
- **Step 8's registry**: every deterministic detector the battery runs is a registry entry with explicit result routing, dispatched in the current order, under a single run-everything policy. Its **source-level guard** fails the build if a detector is called outside the registry dispatch, and its characterization guard fails if an entry is dropped. This step adds a policy dimension; it must not reintroduce a direct call.
- **Step 3's contract authority** (plan_tool/jira_grade.py — not at HEAD): the closed-schema validator (planned name `validate_jira_grade_body`) whose findings carry kind/blocking/message, including the targeted wrong-schema message for a run-grade body at a jira-grade path — which step 3 calls a first-class requirement, not a nice error string.
- **Step 2's handoff**: the allowed-mentions promotion call to `check_files_coherence` inside `plan_tool/cli/completeness_cmd.py:_apply_files_coherence` was deliberately left pointer-only, naming this work as its owner. Step 2 added the `plan_path=None` keyword; this step passes the value at that one remaining site.
- **Verified at HEAD** (re-check before implementing):
  - `_completeness_has_blocking_findings` is **not** uniformly severity-driven: it reads `any(i.kind == "missing_on_disk" for i in detail_cov_issues)` and a bare `if detail_body_issues:`; only the `Recommendation`-shaped arms consult `is_blocking(r.severity)`. `DetailCoverageIssue` is `(step_id, kind, detail_path)`; `DetailBodyIssue` is `(step_id, kind, section, detail_path)` — **neither carries a severity, and neither carries a free-text message.**
  - `_persist_and_present_report` computes `_completeness_convergence_diagnosis` inside `if not skip_sidecar_write:`, gated on `suppress_convergence` alone.
  - `finalize_completeness_run` returns from its `if args.json:` branch **before** `_persist_and_present_report` runs.
  - `check_detail_coverage` reads `Step.detail` and emits `missing_on_disk` / `unreferenced_on_disk` into `detail_cov_issues`.
  - `write_completeness_report` writes the `.json` sidecar via `save_review` **only when `recommendations` is passed**.
  - `check_test_strategy_alignment` is **not** in this battery — its only call site is `collect_deterministic_findings` (`review.py:5138`). Do not classify it.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — add the grade class to each registry entry and the grade policy to the dispatch; grade parameter on `_persist_and_present_report` (sidecar + convergence suppression, jira grounding provenance); grade-correct next-steps in `_render_grouped_report`'s `_next_steps` block.
  - `plan_tool/review.py` — `check_jira_grade_bundle`; an optional message slot on `DetailBodyIssue` so step 3's wrong-schema text has a home; **the grade axis the both-grades classification depends on** — a grade parameter threaded through `build_plan_footprint` → `_read_detail_body` (and `_deliverable_deferred`, which already takes `plan`/`plan_path`) so `detect_orphaned_deliverable` reads the jira artifact under jira grade, plus the `acceptance`/`overview` → `done` key mapping for its claim scan. Without this that detector's both-grades classification is a silent no-op — see the classification list. `detect_claim_vs_delivery` needs no such axis: it reads the declared-only `_declared_footprint` (zero file I/O) plus the plan body, so it takes no grade parameter and must not grow one.
  - `plan_tool/completeness_report.py` — grade parameter on the operator-guidance producers (`suggested_next_steps`, `suggested_next_step_commands`, `diagnostic_remedies`, the per-finding `Address:` lines, the two `completeness-apply` header blocks); grade-correct wording for the coverage and body renderers.
  - `plan_tool/cli/completeness_cmd.py` — the sidecar-suppression stderr notice on both the `--json` and normal paths; the `detail_grade` key and provenance in the `--json` payload under jira selection; pass `plan_path` into `_apply_files_coherence`'s `check_files_coherence` call (the step 2 handoff).
  - `tests/cli/test_completeness_cmd.py`, `tests/test_completeness_report.py`, `tests/test_review.py` — per the Tests section.

## Implementation

### The grade classification

Each registry entry gains a grade class. The classification, verified against step 8's registry (which is the contract, not this list):

- **Grade-independent**: `check_file_existence`, `detect_path_style_mismatch`, `validate_deps`, `check_body_completeness`, `check_lessons_coverage`, `assess_granularity`, `_collect_data_contract_drift`, `validate_feature_refs`, `detect_self_referential_features`, `check_concept_coverage`, and the plan-level branch of `check_input_contract_references`. Dropping any of these under jira grade would be a weakening — Out of scope forbids it.
- **Run-grade only** (they read run-grade detail bodies under the seven-section contract): `check_detail_body_completeness`, `check_files_coherence`, `check_detail_coverage`, `detect_suppression_shape`, and the per-step detail loop of `check_input_contract_references`.
- **Both grades** — `detect_orphaned_deliverable` and `detect_claim_vs_delivery` are **plan-altitude** checks whose primary signal is grade-independent: they key on a step's declared `creates:`/`files:`, whether another in-scope step consumes them, and whether the plan body's `## Acceptance criteria` / `## Overview` names them. Classifying them run-grade-only would drop a blocking `medium` check under `--grade jira` for a reason that does not apply — a plan shipping a deliverable nothing consumes would pass clean — which is exactly the "dropping grade-independent checks" this step's Out of scope forbids.

  **Both-grades is only correct if this step lands the grade axis `detect_orphaned_deliverable` reads through; it is not free.** That detector reaches detail bodies via `plan_tool/review.py:build_plan_footprint` → `_read_detail_body`, which resolves the run-grade pointer-or-canonical path and carried **no grade parameter**. Left alone, a `--grade jira` audit runs it over run-grade bodies — two artifacts judged under one heading, the split brain this step exists to close. Three arms touch the detail body, and they do not fare alike:

  (`detect_claim_vs_delivery` is *not* one of them: it takes the declared side from `_declared_footprint`, which does **zero file I/O**, and matches it against the plan body's `## Acceptance criteria` / `## Overview`. It opens no detail file at either grade, so it is grade-independent by construction and correctly carries no grade parameter — do not add one.)

  - **Deferral excuse (`_deliverable_deferred`, condition 4) — works once the axis exists.** `_deliverable_deferred` already reads `sections.get("deferred")` **and** `sections.get("out")`, and jira-grade's required `## Out of scope` yields exactly the `out` key. Nothing new is needed beyond pointing the read at the jira artifact.
  - **Claim prose (`build_plan_footprint`) — needs a key mapping.** The detail-side claim scan reads the `acceptance` and `overview` keys, and the five-section contract has neither; its acceptance surface is `## Done when`, which parses to `done`. Under jira grade that scan must read `done` (the plan-body claim scan is unchanged and stays grade-independent).
  - **Referenced side — grade-agnostic.** Whole-body path and symbol mentions work against either contract.

  **Do not restate the deferral arm as a safe degradation.** It is condition 4 of a four-part conjunction written `if not _deliverable_deferred(...): continue`, so it is a **required trip condition**, not a suppressor: lose the signal and `detect_orphaned_deliverable` emits *nothing*. A both-grades classification that leaves that check reading run-grade bodies therefore silently disables the very check it claims to preserve — the failure is total and silent, not conservative.
- **Jira-grade only**: `check_jira_grade_bundle`.

Two entries need care. `check_input_contract_references` is **one call with two branches in different classes** — split it into two registry entries in step 8's terms (a plan-level entry and a per-step-detail entry) rather than classifying the call as a whole; if step 8 did not split it, that is a step 8 gap to fix there, not to branch around here. And `check_detail_coverage` must stay run-grade-only for a specific reason: it emits `missing_on_disk` into the same bucket and under the same `kind` the jira coverage arm uses, so running it under jira grade would let a **run-grade pointer defect** flip `has_blocking_findings` on a jira-grade audit and put both grades' verdicts under one `### Detail coverage` heading.

**This step's guard** is narrow, because step 8's source-level guard already prevents unclassified detectors from running: a test asserting every registry entry has a grade class, with a negative case adding a classless entry and confirming the test fails. Combined with step 8's guard, "ran without a grade class" is unreachable.

### The jira bundle check

`check_jira_grade_bundle(plan, plan_path, repo_root)` in `plan_tool/review.py`: per step, resolve the jira artifact and emit (a) a coverage finding when missing and (b) contract findings from `validate_jira_grade_body` when the body fails. **`done` steps are exempt** from both arms, mirroring `check_detail_coverage`'s deliberate skip and step 2's "done steps stay skipped at every site" pin.

**A plan with *no* jira artifacts at all is bare, not blocked — arm (a) fires only on a partial bundle.** Step 7 already routes a missing jira artifact into the bare-plan machinery, which exists because a bare plan "is a valid early-pipeline audit target"; emitting a blocking `missing_on_disk` for the same state would give one plan two opposite verdicts under one grade. Match the run-grade precedent, which has no counterpart to a blanket coverage failure: `check_detail_coverage` emits `missing_on_disk` only when `step.detail` is *set* and the file is gone, so an un-authored run-grade plan audits clean on coverage. So arm (a) is scoped to a **partially authored** bundle — at least one non-`done` step has a jira artifact and at least one does not, which is the state that actually indicates a defect. Zero artifacts across every non-`done` step is bare: no coverage finding, and step 7's bare-plan grounding instruction carries the audit. This is not hypothetical ordering trivia — step 4 authors the first bundle only after this step lands, so **the very first `completeness-audit --grade jira` anyone runs hits the zero-artifact state**, and a blanket blocking finding would make the feature's first impression a false failure.

**How these block — by carrier and kind, not severity.** Given the HEAD facts above, a finding described as "medium severity" and shaped as a `DetailCoverageIssue` would be silently non-blocking, and a new coverage `kind` would fall outside the gate's `missing_on_disk` test. Shape the arms to block through the gate exactly as it stands, with **no edit to `_completeness_has_blocking_findings`**: the **missing** arm as a `DetailCoverageIssue` with `kind="missing_on_disk"`; the **mislabeled** arm as a `DetailBodyIssue` (the whole bucket is blocking). Pin both with tests asserting `has_blocking_findings` is true and `--fail-on-findings` flips the rc.

**Step 3's wrong-schema message needs a carrier slot.** `DetailBodyIssue` has no message field, and `### Detail file sections` renders `section` as "section `## X` missing|empty/placeholder" — so reusing the carrier as-is would silently drop the targeted message step 3 makes a first-class requirement. Add an **optional message field** to `DetailBodyIssue` (defaulting to `None`, so every existing construction and the run-grade rendering are unchanged) and have the renderer prefer it when present. That is a carrier shape change, so: confirm no persisted schema serializes `DetailBodyIssue` before adding the field, and pin run-grade rendering byte-for-byte.

**The renderers must describe the right defect.** `### Detail coverage` prints "step {id} detail `{path}` declared but missing on disk" — but a jira artifact is **never declared** (`Step.detail` stays run-grade-only; resolution is derivation plus `is_file()`). Word the jira case as a missing *derived* artifact naming the derived path. Run-grade wording for both buckets is unchanged, and that is part of the byte-for-byte fence.

### The suppressions — enumerate the surfaces, never argue from the sidecar

**"Every structured consumer reads `.json` sidecars, so contamination is structurally impossible" is false and must not appear in this step.** Two surfaces cross grades without touching a sidecar. Each gets its own named mechanism:

- **The findings sidecar** — call `write_completeness_report` **without `recommendations`**; the `.md` report is still saved (step 10 needs a committable record) but no `-completeness.json` is written. Reuse is separately rejected by step 7's guards.
- **The convergence diagnosis** — pass `suppress_convergence=True`. It is *not* covered by the sidecar omission: the diagnosis sits inside `if not skip_sidecar_write:` gated on `suppress_convergence` alone, and omitting `recommendations` leaves `skip_sidecar_write` false. Uncovered, a jira run mixes findings into the run-grade `kind="completeness"` history and can print `plan-tool convergence … --apply-split` into the committed report step 10 records. Do **not** use `skip_sidecar_write=True` instead — it short-circuits the whole block including `build_report_md`, so the `.md` would not be written.
- **The operator-guidance prose** — its own subsection below.
- **Sweep before implementing.** Re-grep `_persist_and_present_report` and its callees for anything else reading saved history, the reports directory, or a prior run's findings; give each a named mechanism or a recorded reason it is grade-safe. Prefer bringing a surface under a mechanical check over adding a bullet here.

**Provenance, on both output paths.** The report states its grounding: a grade line plus the artifact→digest fingerprint map from step 7, which pins exactly which bundle bytes the audit saw.

Because `finalize_completeness_run` returns from `if args.json:` **before** the report is written, the `--json` path must carry the same provenance itself: `detail_grade` and the fingerprint map, under jira selection only; the default payload is unchanged. Otherwise this step's provenance criterion is unsatisfiable under `--json` — a jira-grade `--json` run would report findings with nothing binding them to the bytes judged. (`DATA_CONTRACT.md`'s `### completeness-audit --json` table is these keys' documented home — step 10 owns the doc edit.)

**Announce the suppression on every jira-grade audit — including `--json`.** Bind the notice to the audit *completing*, not to the report write, for the same early-return reason. Emit on both paths, exactly once per run, naming what the run did not produce: no findings sidecar, so no audit history, no `--reuse-audit`, no `plan-tool convergence` for this grade. Route through the existing `warn` helper; one line. Documenting it in `docs/AUDIT_FLOW.md` (step 10) is not sufficient exposure — without the notice an operator sees a normal-looking audit that silently persists nothing.

### Operator guidance under jira grade

The next-steps prose advertises `completeness-apply`, which resolves its target through `resolve_reusable_audit` where the newest `-completeness.json` wins — after a jira run that is still the last **run-grade** save, so following the printed command silently walks the wrong grade. Two more lines are wrong: `completeness-audit <name> --iterate` (step 7 rejects it at rc 2) and `plan-tool detail <name>` (run-grade authoring, printed as the remedy for a missing **jira** artifact).

- `_render_grouped_report`'s `_next_steps` block — drop the `--iterate` and `completeness-apply` bullets; replace the `plan-tool detail <name>` bullet with guidance that is **permanently true and names no plan-internal step number** (it ships to operators and nothing owns editing it later): name the missing artifact and its documented contract (`DETAIL_FORMAT.md`), not a command that does not exist until step 4 lands.
- `suggested_next_steps` / `suggested_next_step_commands` — withhold both `completeness-apply` bullets and the `--iterate --max-iterations N` open-findings bullet; `diagnostic_remedies`' files-coherence remedy likewise.
- The per-finding `Address: … --anchor <slug>` lines and the two `completeness-apply` header blocks — replace with one line stating these gaps are read-and-fix-by-hand for this grade. Do not invent an `--anchor`-shaped substitute.
- **Default path unchanged**: keyword-only grade with a run default, so callers that don't pass it render byte-for-byte as today.

Bounded to prose: no finding, severity, source, bucket, blocking gate, or JSON key changes. The notice names what was not produced, so the next-steps block must not recommend a verb that reads it; both come from the same branch and cannot drift apart.

### The step 2 handoff (run-grade lane, independent of the flag)

In `_apply_files_coherence`, pass `plan_path` into the `check_files_coherence(plan, repo_root)` call so a canonical-only detail file is visible there too — `plan_path` is already the function's first parameter, a one-keyword edit. Do not widen it; the intentionally pointer-only callers in `bench.py` and `cli/inspect.py` stay untouched.

## Tests

Green-before-done gate: every test below passes and the existing suites pass **with zero edits to their existing cases**. All claude seams stay stubbed; no test may spawn a real backend.

`tests/cli/test_completeness_cmd.py`:
- `test_every_registry_entry_has_a_grade_class` — plus a negative case adding a classless entry and asserting failure.
- `test_grade_jira_selects_jira_battery` — the run-grade detail readers (`check_detail_body_completeness`, `check_files_coherence`, `check_detail_coverage`, `detect_suppression_shape`, the per-step Input loop) are not called; the jira bundle check is; the grade-independent set still runs.
- `test_grade_jira_still_runs_plan_altitude_deliverable_checks` — `detect_orphaned_deliverable` and `detect_claim_vs_delivery` **are** called under `--grade jira` *and still fire*. Build the fixture to satisfy the whole trip conjunction, or it cannot fire and the test proves nothing: a step that `creates:` a deliverable, no other in-scope step consuming it, no plan-body claim naming it, **and the deliverable named in the jira artifact's `## Out of scope`** — condition 4 is required, not incidental. Assert the finding is absent when that `## Out of scope` mention is removed, so the test pins that the deferral signal is being read from the *jira* artifact rather than from a run-grade body that happens to be on disk. If the fixture will not fire, suspect the grade axis, not the assertion.
- `test_grade_run_deterministic_battery_unchanged` — default grade calls exactly today's set with today's arguments.
- `test_grade_jira_run_grade_pointer_defect_does_not_block` — a plan with a set-but-missing `Step.detail` and a complete jira bundle produces no blocking finding under `--grade jira`.
- `test_grade_jira_suppresses_sidecar` / `test_grade_jira_suppresses_convergence_diagnosis` — the `.md` is written, no `.json`; no convergence section and no `--apply-split` / `--apply-scope-out` line even when saved run-grade history yields `spinning`; the default grade still renders it on the same fixture.
- `test_grade_jira_warns_sidecar_suppressed` / `…_under_json` — exactly one notice on each path; none under the default grade.
- `test_grade_jira_json_carries_grade_and_provenance` / `test_default_json_unchanged` — `detail_grade` and the fingerprint map present under jira only.
- `test_grade_jira_next_steps_omit_apply_and_iterate` / `test_grade_run_next_steps_unchanged`.
- `test_grade_jira_agrees_with_jira_export_on_done_step_exemption` — the cross-consumer assertion relocated from step 5.
- `test_apply_files_coherence_threads_plan_path` — the step 2 handoff.

`tests/test_review.py`:
- `test_check_jira_grade_bundle_coverage_and_contract` — missing → `DetailCoverageIssue(kind="missing_on_disk")`; wrong-schema → `DetailBodyIssue` carrying step 3's message and the jira path; conforming → none; `done` step → none.
- `test_check_jira_grade_bundle_findings_are_blocking` — both arms drive `has_blocking_findings` true through the **unmodified** gate and flip the rc under `--fail-on-findings`.
- `test_detail_body_issue_message_slot_defaults_none` — existing constructions and run-grade rendering are unchanged.

`tests/test_completeness_report.py`:
- `test_suggested_next_steps_grade_jira_withholds_apply_bullets`, `test_diagnostic_remedies_grade_jira_withholds_apply`, `test_report_grade_jira_address_lines_replaced`.
- `test_jira_coverage_issue_render_wording` — a jira coverage finding renders as a missing *derived* artifact naming the derived path, never "declared but missing on disk"; a jira body finding renders step 3's wrong-schema message.
- `test_report_default_grade_prose_unchanged` — identical guidance prose and coverage/body wording to today's.

### Test-creation order (feature step)

Unit tests land with the implementation, one surface at a time: grade classes on the registry → the jira bundle check and its carriers → the suppressions and provenance → the guidance prose. Keep each surface green before wiring the next.

## Acceptance criteria

- Every registry entry carries a grade class, and a test fails when one does not — demonstrated by a negative case. Combined with step 8's source-level guard, a detector cannot run without a grade class.
- `check_test_strategy_alignment` is absent from the registry and unclassified — it belongs to the reconcile/review lane.
- Under `--grade jira` the run-grade detail readers do not run, the grade-independent set still does, and a run-grade `Step.detail` pointer defect cannot flip `has_blocking_findings`.
- `check_jira_grade_bundle` emits `missing_on_disk` for a missing artifact and a body finding carrying step 3's wrong-schema message for a mislabeled one, exempts `done` steps, and both arms block through the **unmodified** gate and flip the rc under `--fail-on-findings`.
- Jira coverage findings render as a missing *derived* artifact, never "declared"; run-grade wording is byte-for-byte unchanged.
- A jira-grade audit writes no `-completeness.json` and no convergence diagnosis (no section, no `--apply-split` / `--apply-scope-out` line) even when saved run-grade history yields `spinning`, and contributes nothing to that history.
- Provenance appears on **both output paths**: the committed `.md` names the grade and the artifact→digest map, and the `--json` payload carries the same under jira selection, so no jira-grade run reports findings without binding them to the bytes judged.
- Exactly one stderr notice per jira-grade audit naming the suppressed sidecar and its three consequences, on the `--json` path as well as the normal one; none under the default grade on either.
- A jira-grade report and its console block name no verb the grade cannot serve, and the missing-artifact remedy is permanently true with no plan-internal step number.
- The allowed-mentions promotion in `_apply_files_coherence` passes `plan_path`.
- Every prose block this step ships reads as plain, concise English per the plan's prose contract — checked by reading, since these are hand-authored and carry no runtime gate.
- A default `plan-tool completeness-audit <name>` (and `--grade run`) is byte-for-byte today's behavior on every surface here — pinned by the existing suites passing with zero edits.
- `uv run pytest tests/ -q` is green.

## References

- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — stubbing the domain seams for classification and suppression tests.
- [CommonMark Spec 0.30 — ATX headings](https://spec.commonmark.org/0.30/) — the heading syntax behind the contract the bundle check validates.

## Deferred

- **Persisting a jira-grade findings sidecar** — needs a grade marker in the saved-review schema (`DATA_CONTRACT.md`, a new `kind` token, consumer filters in `resolve_reusable_audit` / `completeness-apply` / `convergence_diagnosis.load_report_history`): a plan-level persisted-schema decision. The stage-03 quality ledger owns landing it; BACKLOG #171 names it a hard prerequisite of canonical inversion.
- **`completeness-apply` for jira-grade audits** — structurally impossible while no jira sidecar exists.
- **Extending the grade policy to the reconcile/review lanes** — out of fence; propose via `BACKLOG.md` if the registry proves itself.
- **Reference-doc updates** (`docs/AUDIT_FLOW.md`, `DETAIL_FORMAT.md`, `JIRA_FORMAT.md`, `DATA_CONTRACT.md`) — owned by step 10.
