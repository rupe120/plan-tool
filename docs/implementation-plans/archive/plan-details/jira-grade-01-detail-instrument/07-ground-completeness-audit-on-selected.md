> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Ground the completeness audit on the selected grade's bundle: resolution, prompt framing, and the fingerprint grade axis

## Summary

Give `plan-tool completeness-audit` its grade axis and point the *conceptual* audit at the selected grade's bytes under that grade's contract: the `--grade {run,jira}` flag and its up-front guards, the grade thread down to `render_plan_audit_prompt`, a grade-selected bundle framing in `plan_tool/prompts/plan-audit.md`, and a grade axis on `compute_detail_bundle_fingerprint`. The main files are `plan_tool/cli/completeness_cmd.py` (flags, guards), `plan_tool/cli/completeness_phases.py` (grounding pass-through, banner), `plan_tool/review.py` (bundle formatter/status and the prompt renderer), `plan_tool/prompts/plan-audit.md` (the framing becomes a variable), and `plan_tool/fingerprint.py`. The key design decision: **the framing moves with the bundle.** Pointing run-grade framing at a compact bundle turns every implementation fact the jira contract sheds into an apparent gap, so resolving the right bytes is not enough on its own — the judge has to be told which contract applies. The deterministic battery, the jira bundle check, and every report surface belong to **step 9**; this step deliberately stops at grounding. On green, `plan-tool completeness-audit <name> --grade jira` grounds the audit prompt on the `jira/` artifacts, a default run is byte-for-byte unchanged, and approx. 16–18 new tests pass across `tests/cli/test_completeness_cmd.py`, `tests/test_review.py`, and `tests/test_fingerprint.py`.

## Table of Contents

- [Summary](#summary) — what this half ships and the one design decision
- [Why](#why) — why grounding is its own step, and the split-brain shape it must not create alone
- [Input](#input) — the step 1 / 3 contracts consumed here, and what can't be verified at HEAD
- [Files (creates vs edits)](#files-creates-vs-edits) — per-file edits; no new files
- [Implementation](#implementation) — the flag and guards, the grounding thread, the framing variable, the fingerprint axis
- [Tests](#tests) — CLI, review, and fingerprint cases, with the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the plan-level references relevant to this step
- [Deferred](#deferred) — everything step 9 owns, plus the sidecar decision

## Why

This step answers the inherited `audit-churn` blocker: the completeness audit grounds on the run-grade `Step.detail` bundle, so a jira-grade bundle is invisible to it — no coverage check, no coherence check, no way to judge a jira artifact at all. That gap is why the plan's "validator lands before the producer" rule gates step 4 behind step 9. Making the audit grade-aware turns out to be two different jobs with different risk profiles, which is why it is two steps:

- **Grounding (this step)** — which bytes the audit reads, and which contract the judge is told to apply. Bounded, and independently useful: an operator can audit a jira bundle at its own level of detail the moment this lands.
- **Battery and report surfaces (step 9)** — which deterministic checks may run per grade, what the jira bundle check emits, and every report surface that would otherwise mix grades. That job is an *enumeration over a large, implicitly-coupled pipeline*, and enumerating it in prose is what four rounds of this plan's own completeness audit kept finding holes in. Step 9 closes it with a registration test instead of a list.

The failure shape both halves exist to prevent is a split brain: the audit prompt switching bundles while other surfaces keep reading run-grade state, so one report mixes judgments of two artifacts under one heading — the defect step 2 closed for canonical-only files. **This step alone does not prevent it**; it creates the axis that step 9 then makes total. Nothing in this step may claim the split brain is solved, and `--grade jira` is not a supported operator surface until step 9 lands (see Deferred). The plan's fence bounds the diff: resolution and format-contract selection only — finding machinery, severities, sources, blocking gates, and convergence logic are untouched, and the default (no `--grade`, or `--grade run`) path produces byte-for-byte today's behavior.

## Input

- **Step 1's leaf + step 3's path derivation** (plan_tool/detail_artifacts.py — **step 1 is `done` and the leaf is merged**; step 3's `derive_jira_detail_path` is not): `derive_jira_detail_path(plan_path, plan, step)` returns `<plan_dir>/plan-details/<plan_slug>/jira/<NN>-<step_slug>.md`. There is no pointer axis — `Step.detail` stays run-grade-only — so jira-grade resolution is canonical derivation plus an `is_file()` check.
- **Step 3's contract authority** (plan_tool/jira_grade.py, created by step 3 — not at HEAD): the five required H2 tokens (`intent`, `change`, `constraints`, `done`, `out`, first-token matching) and the closed-schema read-time validator (planned name `validate_jira_grade_body`). This step consumes the token set for the jira framing block's wording and the grade constants for `choices=`; the validator itself is step 9's consumer.
- **Grade token vocabulary**: step 3 (the schema authority) mints the `run` / `jira` axis values; import them from there. Do not mint a third spelling and do not describe any sibling consumer's flag as already shipped.
- **Verification limit**: step 1 is `done` — `plan_tool/detail_artifacts.py` is merged, so verify its symbols against the module. Step 3's additions are not: `plan_tool/jira_grade.py` and `derive_jira_detail_path` do not exist at HEAD, and every symbol cited from them is a dependency contract to re-verify against the merged code before implementing. Symbols cited from `plan_tool/review.py`, `plan_tool/fingerprint.py`, `plan_tool/prompts/plan-audit.md`, `plan_tool/cli/completeness_cmd.py`, and `plan_tool/cli/completeness_phases.py` are verified at HEAD.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` — add `--grade {run,jira}` (default `run`) in `register`; read it via `getattr(args, "grade", "run")` in `cmd_completeness` (hand-built-namespace idiom; the default is what keeps any packaged caller on run-grade); reject incompatible flags up front; skip audit reuse under jira grade; thread the grade through `finalize_completeness_run`.
  - `plan_tool/cli/completeness_phases.py` — grade parameter on `_sample_conceptual_audit` (prompt grounding pass-through) and `emit_bare_plan_banner`; the stderr banner's grounding line. **Battery selection and `_persist_and_present_report` are step 9's.**
  - `plan_tool/review.py` — grade axis on `_format_audit_detail_bundle`, `audit_detail_bundle_status`, `render_plan_audit_prompt`, `check_plan_audit`, `audit_plan_until_stable` (all keyword-only, defaulting to today's behavior), plus the framing substitution. **The jira bundle check is step 9's.**
  - `plan_tool/prompts/plan-audit.md` — turn the bundle's hard-coded framing line into a template variable; the run-grade substitution must reproduce today's text byte for byte.
  - `plan_tool/fingerprint.py` — keyword-only grade parameter on `compute_detail_bundle_fingerprint`; jira path resolves via `derive_jira_detail_path`, default path unchanged.
  - `docs/cli/completeness-audit.md` — regenerate with `python -m plan_tool.cli_reference --write`; never hand-edit (generated, drift-guarded).
  - `tests/cli/test_completeness_cmd.py` — flag routing and guard cases.
  - `tests/test_review.py` — bundle formatter/status grade branch and prompt-framing cases.
  - `tests/test_fingerprint.py` — grade-axis cases for the bundle fingerprint.

## Implementation

### The grade selector and its guards

- **Flag**: `--grade {run,jira}` on `completeness-audit` only (not `completeness-apply`), default `run`, read with `getattr(args, "grade", "run")`. The values are taken from step 3's grade constants — a second flag name or a re-declared token set for the same axis is the confusion this plan exists to remove.
- **Reject, before any claude call, run log, or reuse lookup** (rc 2, in `cmd_completeness` right after parse — mirroring where the existing `--commit`-requires-`--iterate` gate sits):
  - `--grade jira` + `--iterate` — the iterate loop applies deterministic findings via `apply_finding` and runs the pre-apply checkpoint, drift watch, and commit machinery, all built on run-grade grounding; converging the jira bundle is a separate decision (see Deferred). `--commit` is transitively covered (it already requires `--iterate`).
  - `--grade jira` + `--reuse-audit` or `--reuse-audit-id` — every saved sidecar at HEAD is run-grade-grounded and carries no grade marker; `resolve_reusable_audit`'s freshness verdict checks plan and code fingerprints only, both grade-independent, so a run-grade save would look "fresh" to a jira-grade run. An explicit reuse request must fail loudly, not silently audit the wrong grounding.
- **Silent-skip under jira grade** (documented + tested, not rejected): the unprompted reuse lookup (`_resolve_audit_reuse` is not called; `reused_audit_recs` stays `None` → fresh audit), and the per-step MIXED-STEP purity pass (`run_purity` forced `False` — the purity prompt and its cache key in `compute_purity_cache_key` read the run-grade detail; judging run-grade purity inside a jira-grade report is exactly the mixed-judgment shape to avoid). `--no-purity` becomes a no-op under jira grade.
- **Sweep the rest of the flag surface** and classify each flag as works-scoped (`-y`, `--json`, `--fail-on-findings`, `--audit-passes`/`--audit-samples`, `--audit-dry-rounds`), iterate-only-and-therefore-unreachable (`--max-iterations`, `--iteration-budget`, `--time-budget`, `--max-stall-rounds`, `--allow-drift`, `--no-auto-reconcile-on-drift`, `--no-triage`, and the other iterate-parent flags — already inert without `--iterate` today), or no-op-with-note (`--no-purity`). No unclassified flag.

### Grounding thread (conceptual audit)

Thread a keyword-only grade parameter (recommend `detail_grade: str = "run"`, matching step 6's naming) down the existing call chain, default preserving today's behavior at every hop:

- `finalize_completeness_run` → `_sample_conceptual_audit` → `plan_tool/review.py:audit_plan_until_stable` → `check_plan_audit` → `render_plan_audit_prompt` → `_format_audit_detail_bundle` + `audit_detail_bundle_status`.
- In `_format_audit_detail_bundle` and `audit_detail_bundle_status`, the jira branch resolves each step's artifact by `derive_jira_detail_path` + `is_file()` and never reads `Step.detail`. The run branch is untouched — same resolution, same output.
- A **missing** jira artifact makes the step *bare* for this grade: the existing bare-step treatment applies (`DetailBundleStatus.bare_step_ids`, the concept-level-only grounding instruction in `_format_detail_bundle_status_block`, the `emit_bare_plan_banner` line). The bare-plan machinery is grade-generic; reuse it, don't fork it. The **coverage finding** that accompanies it is step 9's.
- A **mislabeled** artifact (a body that fails step 3's contract) renders a one-line note *instead of the body*, so invalid content is never embedded as jira-grade grounding. There is **no fallback to the run-grade body** in either case — the no-silent-fallback rule steps 5/6 established holds here. The blocking *finding* for the mislabeled body is step 9's; this step only controls what reaches the prompt.
- Callers that must pass the value: `_sample_conceptual_audit` (from `finalize_completeness_run`), the `finalize_completeness_run` bundle-status call that feeds the grouped report, and `emit_bare_plan_banner`'s status call. Callers that stay on the default, compiling unchanged: the iterate-loop's `audit_plan_until_stable` call in `_run_iterate_convergence_loop` (unreachable under jira grade), and `review.py`'s reconcile-lane uses of the bundle functions. None of the threaded functions is re-exported in `plan_tool/__init__.py`, so no public-surface constraint beyond keyword-only defaults.
- **Preserve the monkeypatch seams**: the suites patch `plan_tool.review.audit_plan_until_stable` and `plan_tool.review.shell_review_invoker` as module globals; the grade branch must keep those module-global call forms — no aliasing, no re-binding.
- The stderr banner states the grounding: add a grade line (e.g. `grounding: jira-grade detail bundle (plan-details/<slug>/jira/)`) to the banner in `cmd_completeness`, rendered only under jira grade.

### Swapping the bundle's framing, not just its bytes

Resolution alone is not grounding. `plan_tool/prompts/plan-audit.md` hard-codes the bundle's framing at HEAD — "These are the per-step detail files a developer will implement against" — and its Completeness rule reads "check whether a detail file in the implementation bundle … already specifies it … Only flag gaps that are unresolved anywhere in the bundle." Both sentences describe the *run-grade* contract. Point them at a five-section bundle and every implementation fact that contract deliberately sheds — files, approach, test rosters, mechanics — reads as an unresolved gap, so the jira arm inflates **by construction**. Applying the selected grade's format contract to the prompt is what Architecture commits the amendment to; it changes no finding source, severity, or sampling, so the judgment fence holds.

- The jira substitution states the altitude: the bundle is a compact five-section contract (`Intent`, `Change`, `Constraints`, `Done when`, `Out of scope`) carrying outcomes and boundaries, not implementation specs — a missing file list, approach, or test roster is the contract working as designed and is **not** a completeness gap. Judge coverage against what the five sections are *for*: whether the intent, the change, its constraints, its acceptance surface, and its fence are each resolved somewhere in the bundle or the plan body.
- Reach the Completeness rule's "unresolved anywhere in the bundle" sentence too, not just the heading. If that rule cannot be made grade-aware without restructuring the prompt, say so in the jira framing block instead — the framing is read before the bundle, so it can qualify the earlier rule. Do not weaken the rule for run grade.
- Everything else in the prompt is unchanged under both grades. The plan body, the finding taxonomy, and the severity guidance are grade-independent; only the bundle's framing moves.

### The fingerprint grade axis

`compute_detail_bundle_fingerprint` gains the keyword-only grade parameter (jira: hash the on-disk `jira/` artifacts, missing ones omitted, keys repo-relative posix, default path unchanged). Its consumer is step 9's report provenance block — the artifact→digest map pins exactly which bundle bytes the audit saw, so every finding traces back to the artifact that produced it — and it is the producer the deferred sidecar decision will need. `compute_purity_cache_key` and `_detail_bundle_staleness` stay run-grade (defaults).

## Tests

New tests land with the implementation. Green-before-done gate: every test below must pass, and the existing suites (`tests/test_cli.py`'s completeness contract tests, `tests/cli/test_completeness_cmd.py`'s per-phase classes, `tests/test_review.py`, `tests/test_fingerprint.py`) must pass **with zero edits to their existing cases** — they are the byte-for-byte fence for the default path. All claude seams stay stubbed at the domain modules (`plan_tool.review.audit_plan_until_stable`, `plan_tool.review.shell_review_invoker`); no test may spawn a real backend (the conftest gate enforces this).

`tests/cli/test_completeness_cmd.py`:
- `test_grade_defaults_run_for_legacy_namespace` — a hand-built namespace without a `grade` attribute takes the run path (getattr default).
- `test_grade_jira_rejects_iterate` — `--grade jira --iterate` exits 2 before any invoker call or reuse lookup.
- `test_grade_jira_rejects_reuse_flags` — `--reuse-audit` and `--reuse-audit-id` with jira grade exit 2 with a message naming why (saved audits are run-grade-grounded).
- `test_grade_jira_skips_reuse_lookup` — a fresh, matching run-grade sidecar on disk is not offered or reused under jira grade.
- `test_grade_jira_forces_purity_off` — `run_purity` is `False` even without `--no-purity`.
- `test_grade_jira_banner_names_grounding` — stderr banner carries the jira grounding line; default banner unchanged.

`tests/test_review.py`:
- `test_format_audit_detail_bundle_grade_jira_resolves_jira_paths` — jira artifacts embedded under their repo-relative `jira/` paths; `Step.detail` never read.
- `test_format_audit_detail_bundle_grade_jira_missing_is_bare_note` — missing artifact renders the no-detail note; no run-grade fallback even when `Step.detail` points at a real file.
- `test_format_audit_detail_bundle_grade_jira_mislabeled_not_embedded` — a run-grade body at the jira path renders a note, not the body.
- `test_audit_detail_bundle_status_grade_jira` — detailed/bare classification follows jira artifacts, matching what the formatter embeds.
- `test_render_plan_audit_prompt_default_grade_unchanged` — default-grade prompt output identical to today's for the same inputs (the byte-for-byte pin for the framing-variable edit).
- `test_render_plan_audit_prompt_grade_jira_framing` — the jira-grade prompt frames the bundle as the compact five-section contract and states that a missing implementation fact is not a gap; the run-grade framing literal is absent.

`tests/test_fingerprint.py`:
- `test_detail_bundle_fingerprint_grade_jira_keys` — keys are the on-disk `jira/` artifact paths, hashed; missing artifacts omitted.
- `test_detail_bundle_fingerprint_grade_jira_ignores_pointer` — `Step.detail` plays no part under jira grade.
- `test_detail_bundle_fingerprint_default_unchanged` — default call returns today's map for the same plan.

### Test-creation order (feature step)

This is a feature step: add the unit tests above together with the implementation, one surface at a time (fingerprint grade axis → review bundle functions and prompt framing → CLI wiring and guards), keeping each surface's tests green before wiring the next. The step is not finished until every new test and the untouched existing suites are green (`uv run pytest tests/ -q`).

## Acceptance criteria

- `plan-tool completeness-audit <name> --grade jira` completes with exit 0 and grounds the audit prompt on the `jira/` artifacts, verified via the stubbed invoker's received prompt; `Step.detail` is never read on that path.
- The jira-grade audit prompt frames the bundle as the compact five-section contract — a missing implementation fact is stated not to be a completeness gap — while the run-grade prompt is byte-for-byte today's for the same inputs.
- A missing jira artifact makes the step bare for this grade (concept-level grounding instruction present) and is never silently grounded on its run-grade detail file; a mislabeled body renders a note and its content never reaches the prompt.
- `--grade jira` with `--iterate`, `--reuse-audit`, or `--reuse-audit-id` exits 2 before any claude call, reuse lookup, or run-log write.
- `compute_detail_bundle_fingerprint(..., detail_grade="jira")` returns the `jira/` artifact map; the default call is unchanged.
- A default `plan-tool completeness-audit <name>` (and `--grade run`) produces byte-for-byte today's behavior on every surface this step touches — pinned by the existing suites passing with zero edits to their existing cases.
- `docs/cli/completeness-audit.md` is regenerated and `tests/cli/test_cli_reference.py` passes.
- `uv run pytest tests/ -q` is green.

## References

- [pytest — How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — stubbing `plan_tool.review.audit_plan_until_stable` / `shell_review_invoker` at the domain seam for the grounding and guard tests.
- [CommonMark Spec 0.30 — ATX headings](https://spec.commonmark.org/0.30/) — the heading syntax the required-H2 contract validation matches against.
- [Claude Code — Headless / programmatic mode](https://code.claude.com/docs/en/headless) — the non-interactive invocation contract behind the audit's invoker seam.

## Deferred

- **Everything step 9 owns**, and `--grade jira` is not a supported operator surface until it lands: the deterministic battery's grade classification and its registration test, the jira bundle check and its carriers/renderers, the blocking-gate interaction, the no-sidecar and convergence suppressions, the operator-guidance prose, the sidecar-suppression notice, the `detail_grade` JSON key, and the step 2 `_apply_files_coherence` handoff. This step ships the axis; step 9 makes it total. Do not partially implement step 9's surfaces here — a half-classified battery is the split brain, and the whole reason these are two steps is that the enumeration needs its own closure check.
- **Persisting a jira-grade findings sidecar** — needs a grade marker in the saved-review schema (a new `kind` token or field, `DATA_CONTRACT.md`, and exclusion filters in `resolve_reusable_audit` / `completeness-apply` / `convergence_diagnosis.load_report_history`): a plan-level persisted-schema decision neither this step nor step 9 takes. The stage-03 quality ledger owns landing it (`plan-seeds/jira-grade-03-quality-ledger.md`), and BACKLOG #171 names it a hard prerequisite of canonical inversion.
- **`--iterate` convergence for the jira bundle** — the apply loop, drift watch, checkpoint, and commit machinery are run-grade-grounded; rejected loudly here. Revisit with the sidecar decision above.
- **MIXED-STEP purity judgment over jira artifacts** — the purity verdict is defined on run-grade implementation detail (`compute_purity_cache_key` hashes the run-grade body); not meaningful for the five-section contract.
- **Reference-doc updates** (`docs/AUDIT_FLOW.md`, `DETAIL_FORMAT.md`, `JIRA_FORMAT.md`, `DATA_CONTRACT.md`) — owned by step 10.
- **Consolidating the four required-H2 matchers** — pre-existing cross-module refactor; routed to reconcile per step 3's decision.
