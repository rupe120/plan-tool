> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Wire `--settle-decision`/`--settlement-evidence`/`--confirm-decision-settlement` into `plan-tool roadmap` as one exclusive, lineage-routed action

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds three new flags to `plan_tool/cli/roadmap_cmd.py`'s `roadmap` verb — a decision selector, an evidence (feedback) selector, and a required confirm flag — and dispatches them, as one exclusive action, to step 4's un-enrolled runner or step 5's enrolled runner. The CLI never probes which lineage applies: it calls the un-enrolled runner first and falls back to the enrolled runner only on that runner's own `enrolled-roadmap-rejected` refusal, so lineage detection stays owned by the two runners that already implement and test it. Every other broad-mode `_*_has_conflict` predicate in the file gains a check for the new flags, and the new action's own predicate checks every other mode in return, so the exclusivity holds symmetrically — a combined command refuses rather than silently running one action and dropping the other. `docs/cli/roadmap.md` is regenerated from the live parser. On green, `plan-tool roadmap <slug> --settle-decision domain:decision-1 --settlement-evidence domain:feedback-1 --confirm-decision-settlement` settles one decision on whichever lineage the roadmap is actually on, both lineages produce the identical settled row for the same input, and a new `tests/test_roadmap_gates.py` case proves `check_settled_decisions` already refuses a later drift on a row this route settled.

## Table of Contents

- [Why](#why) — why the runner pair needs a CLI action, and why the exclusivity must run in both directions
- [Input](#input) — the step 4/5 runner surfaces, the `--reopen-feedback` precedent this mirrors, and the receipt committer's repo-root gotcha
- [Files (creates vs edits)](#files-creates-vs-edits) — the four declared files and what changes in each
- [Implementation](#implementation) — flags, predicates, dispatch, the lineage-fallback decision, rendering, docs regeneration
- [Tests](#tests) — the named cases, which file each lands in, and the breaks each case must catch
- [Acceptance criteria](#acceptance-criteria) — checks a reviewer can run
- [References](#references) — plan-level references that bear on this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step, and where breaking them is tempting
- [Deferred](#deferred) — work this step does not do

## Why

Steps 4 and 5 each build a complete, independently tested settlement runner, but nothing at HEAD lets an operator reach either one. Two things are still missing, and both belong in this file because both are CLI-layer decisions, not runner decisions:

- **A confirmed CLI action.** Every other mutation this file exposes through a confirm-gated selector — `--reopen-feedback`/`--confirm-feedback-reopen` — has its flags, its `_has_*`/`_*_has_conflict` predicate pair, and its dispatch branch defined here, in `plan_tool/cli/roadmap_cmd.py`, not in the runner module. `plan_tool/roadmap_decision_settlement_run.py:run_unenrolled_decision_settlement` and `plan_tool/roadmap_decision_settlement_enrolled.py:run_enrolled_decision_settlement` (per steps 4 and 5's own Deferred sections) explicitly leave "the CLI flags, the confirm flag, two-way exclusivity, and `docs/cli/roadmap.md`" to this step.
- **A lineage choice.** Step 4's runner refuses `enrolled-roadmap-rejected` on an enrolled roadmap; step 5's runner refuses `unenrolled-roadmap-rejected` on an un-enrolled one. Something has to pick which one to call — both runners' own Deferred sections name this as step 6's decision, not theirs.

The exclusivity has to run in both directions because every existing broad-mode predicate in this file already follows that shape: `_feedback_reopen_has_conflict` checks `_has_receipt_creation`, `_has_impact_analysis_creation`, `_has_structural_rewrite`, and so on, and each of *those* functions already checks `_has_feedback_reopen` back. A new exclusive action that only refuses when it sees a companion, without every sibling refusing when it sees this new one, lets a combined command like `--settle-decision domain:decision-1 --settlement-evidence domain:feedback-1 --confirm-decision-settlement --escalate-feedback domain:feedback-2` silently run the escalation and drop the settlement request — the exact failure mode the step's own intent names.

## Input

- **Step 4's runner** (`plan_tool/roadmap_decision_settlement_run.py`, not yet landed — read the names off the module once it exists; the landed names win over this file):
  - `run_unenrolled_decision_settlement(slug, decision_value, evidence_value, confirmation, *, plans_dir, stages=STAGES, mode_rejected=False, receipt_committer=None) -> DecisionSettlementRunResult`.
  - `DecisionSettlementRunResult` carries exactly `outcome`, `status`, `refusal`, `receipt_id` — no row text.
  - Outcomes: `settled` (status 0), `preflight-rejected` (status 2, `refusal` one of `confirmation-required`, `mode-rejected`, `enrolled-roadmap-rejected`, `journal-unrecoverable`, or a step 2 verdict including `source-changed`), `receipt-rejected` (status 1), `write-failed` (status 1), `interrupted` (status 130).
  - Run order: `confirmation is not True` → `confirmation-required` runs *before* the `mode_rejected` check. This step must preserve that ordering by passing both values straight through and never short-circuiting one in front of the other.
- **Step 5's runner** (`plan_tool/roadmap_decision_settlement_enrolled.py`, not yet landed): `run_enrolled_decision_settlement(slug, decision_value, evidence_value, confirmation, *, plans_dir, stages=STAGES, mode_rejected=False, receipt_committer=None) -> DecisionSettlementRunResult`. Same signature shape and same shared result type as step 4's runner "so step 6 can pick a runner by lineage and call both the same way" (step 5's own words). Its extra refusals (`unenrolled-roadmap-rejected`, `unpromoted-candidate-lineage`, `settled-content-fails-gates`) never need special-casing here — they render through the same generic `refusal` field.
- **The `--reopen-feedback`/`--confirm-feedback-reopen` precedent, in this same file:**
  - `_has_feedback_reopen` (`plan_tool/cli/roadmap_cmd.py:_has_feedback_reopen`) — presence check.
  - `_feedback_reopen_has_conflict` — the `len(_option_occurrences(...)) != 1` shape for each half of a confirm-gated pair, plus every sibling `_has_*`/`view`/broad-mode check.
  - `_cmd_roadmap_feedback_reopen` and its dispatch branch in `cmd_roadmap` — the "resolve `plans_dir`, call the runner once, render, return `result.status`" shape.
  - `_render_feedback_reopen_result` — the redacted two-line render shape (`outcome`, then `reason` only if `refusal is not None`).
  - This step's action differs in exactly one way reopen's does not: it may call a runner twice (see Implementation → lineage fallback), and it renders one extra field (`receipt_id`).
- **`_option_occurrences`, `_view_occurrences`, `_broad_mode_companions_present`, `_TrackExclusiveOption`** (all in this file) — the exact machinery every sibling exclusive-mode flag already uses; this step reuses them unchanged.
- **The receipt committer's repo-root gotcha.** `plan_tool/cli/gitcommit.py:commit_receipt(repo_root, receipt_path, subject)` needs a `repo_root`, but neither step 4/5's runner signature nor step 3's `publish_decision_settlement_receipt(receipt, *, plans_dir, slug, receipt_committer)` takes one. The receipt publisher resolves it itself through `plan_tool/roadmap_escalation_run.py:receipt_worktree_for_plans_dir(plans_dir)`, which runs `git rev-parse --show-toplevel` and returns the worktree root — the same value `repo_root` would have held. This is unlike the `--escalate-feedback`/`--rewrite-structural` dispatch branches in this file, which *do* resolve and pass `repo_root` to their runners. Do not resolve or thread a `repo_root` into either settlement runner call; only use the locally resolved `repo_root` the way `_cmd_roadmap_feedback_reopen`'s branch already does, to compute `plans_dir` when `--plans-dir`/`PLAN_TOOL_PLANS_DIR` was not supplied.
- **`check_settled_decisions`** (`plan_tool/roadmap_gates.py`) and **`settle_pending_decision`** (`plan_tool/roadmap_artifacts.py`, step 1, landed but read the name off the module). `settle_pending_decision` is the exact function every lineage's writer calls to build `DecisionSettlementCandidate.settled_artifact` — it is "the route's" own content-building primitive, independent of the CLI plumbing this step adds.
- **`plan_tool/cli_reference.py`** — the generator `docs/cli/roadmap.md` is produced from (`python -m plan_tool.cli_reference --write`), and `tests/cli/test_cli_reference.py`'s `TestCliReferenceDrift` — the drift guard that fails if the committed doc and the live parser disagree.
- **`tests/cli/test_roadmap_cmd.py:_FROZEN_BROAD_MODE_USAGE`** — a literal, wrapped `argparse` usage string pinned against `capsys` output in `test_nonreceipt_broad_mode_conflicts_keep_current_usage_output_and_status`. Registering any new `add_argument` call changes `format_usage()`'s output and reddens this test; it is not evidence of a real defect, only of an un-updated literal (see Implementation → docs and the frozen usage string).

## Files (creates vs edits)

- **`plan_tool/cli/roadmap_cmd.py`** (edits only):
  - `register()`: three new `add_argument` calls.
  - Three new module-level functions: `_has_decision_settlement`, `_decision_settlement_has_conflict`, `_cmd_roadmap_decision_settlement`.
  - One new render helper: `_render_decision_settlement_result`.
  - `cmd_roadmap`: one new `has_decision_settlement` local, one new dispatch branch.
  - `_selects_non_stage_roadmap_route`: one new entry.
  - Every existing `_*_has_conflict` predicate that currently checks `_has_feedback_reopen` gains a matching `_has_decision_settlement` check: `_candidate_lifecycle_has_conflict`, `_enrollment_has_conflict`, `_escalation_creation_has_conflict`, `_escalation_view_has_conflict`, `_impact_analysis_creation_has_conflict`, `_impact_analysis_view_has_conflict`, `_structural_rewrite_has_conflict`, `_feedback_reopen_has_conflict`, `_revise_feedback_has_conflict`.
  - New imports from `plan_tool.roadmap_decision_settlement_run` and `plan_tool.roadmap_decision_settlement_enrolled`.
  - One new module-docstring paragraph (optional but recommended — see Implementation).
- **`tests/cli/test_roadmap_cmd.py`** (edits only):
  - `_ns`: six new default namespace fields (three flags, three `_..._occurrences` tuples).
  - New parsing-level cases inside `TestArgparseWiring`, mirroring the existing `--reopen-feedback`/`--confirm-feedback-reopen` cases.
  - New dispatch-level cases at module scope, mirroring `test_feedback_reopen_dispatches_only_the_confirmed_operation` and its siblings, including the lineage-fallback cases this step is the first to need.
  - A new two-way exclusivity case extending `test_existing_exclusive_mode_predicates_reject_the_feedback_reopen_pair`'s pattern.
  - `_FROZEN_BROAD_MODE_USAGE`: updated to the new `format_usage()` output.
  - One new test class exercising the real runners over both lineages (see Tests).
- **`tests/test_roadmap_gates.py`** (edits only):
  - One new import (`settle_pending_decision`).
  - One new test proving `check_settled_decisions` refuses drift on a `settle_pending_decision` output, not only on a hand-authored `SETTLED_DOMAIN_DECISION`.
- **`docs/cli/roadmap.md`** (regenerated, not hand-edited): `python -m plan_tool.cli_reference --write`.
- **Unchanged:** `plan_tool/roadmap_decision_settlement_run.py`, `plan_tool/roadmap_decision_settlement_enrolled.py`, `plan_tool/roadmap_decision_settlement.py`, `plan_tool/roadmap_decision_settlement_receipt.py` (steps 2–5's own files), and every non-`roadmap_cmd.py` production module.

## Implementation

### The three flags

Register them with `_TrackExclusiveOption`, matching `--reopen-feedback`/`--confirm-feedback-reopen` exactly:

- `--settle-decision SELECTOR` — the decision selector (`<artifact-key>:<decision-id>`), default `None`.
- `--settlement-evidence SELECTOR` — the evidence/feedback selector, default `None`.
- `--confirm-decision-settlement` — `nargs=0`, `const=True`, default `None`, matching `--confirm-feedback-reopen`'s shape exactly.

A reasonable placement is immediately after `--confirm-feedback-reopen` and before `--escalate-feedback`, grouping the writer-guard-based confirm-gated mutations together — but placement is free; only the frozen usage-string test (see Tests) has to track wherever they land. Argument names, help text, and exact wording are this step's to choose; keep the help text's shape consistent with the sibling flags' style (state the pairing requirement, the exclusivity, and that no backend is invoked), the way `--reopen-feedback`'s help text already does.

### Presence and conflict predicates

- **`_has_decision_settlement(args)`** — `bool` of any occurrence of any of the three flags, mirroring `_has_feedback_reopen`'s shape exactly (an `or` over three `_option_occurrences` calls instead of two).
- **`_decision_settlement_has_conflict(args)`** — mirror `_feedback_reopen_has_conflict`'s `any(...)` tuple:
  - `len(_option_occurrences(args, "settle_decision")) != 1`
  - `len(_option_occurrences(args, "settlement_evidence")) != 1`
  - `len(_option_occurrences(args, "confirm_decision_settlement")) != 1`
  - `bool(_view_occurrences(args))` (covers every `--view` flavor, including `escalations`/`impact-analyses`, the same way `_feedback_reopen_has_conflict` uses one check for all of them)
  - `_has_receipt_creation(args)`
  - `_has_impact_analysis_creation(args)`
  - `_has_structural_rewrite(args)`
  - `_has_feedback_reopen(args)`
  - `_has_candidate_lifecycle_action(args)`
  - `getattr(args, "revise_feedback", None) is not None`
  - `*_broad_mode_companions_present(args)`

### The other direction: sweep every sibling predicate

Add `_has_decision_settlement(args)` to the `any(...)` tuple of every predicate that currently checks `_has_feedback_reopen(args)`: `_candidate_lifecycle_has_conflict`, `_enrollment_has_conflict`, `_escalation_creation_has_conflict`, `_escalation_view_has_conflict`, `_impact_analysis_creation_has_conflict`, `_impact_analysis_view_has_conflict`, `_structural_rewrite_has_conflict`, `_feedback_reopen_has_conflict` (add the *new* action's presence check here, symmetric to how `_decision_settlement_has_conflict` above checks `_has_feedback_reopen`), and `_revise_feedback_has_conflict`. This is the identifier half of the sweep — grep `_has_feedback_reopen(args)` across the file and add a sibling line beside every hit outside `_has_feedback_reopen`'s own definition. `_enrollment_has_conflict`'s outer call site (the `getattr(args, "enroll_baselines", False) and any(...)` block in `cmd_roadmap`) does not need `_has_decision_settlement` added directly — by construction, `has_decision_settlement` is always `False` there once the new dispatch branch (below) has already returned, the same reason that tuple omits `has_feedback_reopen` and `_has_candidate_lifecycle_action` today.

### Dispatch

Add `has_decision_settlement = _has_decision_settlement(args)` alongside the existing `has_*` locals near the top of `cmd_roadmap`, and add `_has_decision_settlement(args)` to `_selects_non_stage_roadmap_route`'s tuple. Insert a new branch shaped exactly like the existing `has_feedback_reopen` branch — resolve `repo_root`/`plans_dir`, call the handler inside a `try`/`except KeyboardInterrupt: error("interrupted"); return 130`, and return its result:

```
if has_decision_settlement:
    repo_root = _resolve_cmd_repo_root(args)
    plans_dir = resolve_explicit_plans_dir(args.plans_dir)
    if plans_dir is None:
        plans_dir = resolve_output_dir(repo_root)
    try:
        return _cmd_roadmap_decision_settlement(args, plans_dir=plans_dir)
    except KeyboardInterrupt:
        error("interrupted")
        return 130
```

Place it next to the `has_feedback_reopen` branch (either order relative to it is fine; both are early, both are confirm-gated, neither runs stages).

### The lineage-fallback design decision

`_cmd_roadmap_decision_settlement(args, *, plans_dir: Path) -> int` reads the three flags' occurrences once (`decision_value`, `evidence_value`, `confirmation`, using the last occurrence of each, matching `_cmd_roadmap_feedback_reopen`'s `selectors[-1] if selectors else None` idiom) and computes `mode_rejected = _decision_settlement_has_conflict(args)` once. It then:

1. Calls `run_unenrolled_decision_settlement(args.slug, decision_value, evidence_value, confirmation, plans_dir=plans_dir, mode_rejected=mode_rejected)`.
2. If, and only if, that result's `outcome == "preflight-rejected"` and `refusal == "enrolled-roadmap-rejected"`, calls `run_enrolled_decision_settlement` with the identical arguments and uses *that* result instead.
3. Renders whichever result is final and returns its `status`.

This is safe to try unconditionally: step 4's run order checks `require_unenrolled_roadmap_writer` (step 6 of its own order) *before* running journal recovery, the preflight, or any write, so an enrolled roadmap's first call is a clean no-side-effect refusal, not a wasted attempt. On a genuinely un-enrolled roadmap the first call *is* the real settlement — no wasted work either way.

**Rejected alternative: probing lineage directly with `plan_tool.roadmap_versions.load_accepted_version(plans_dir=, slug=)` before choosing a runner.** This would need a new import into a CLI module that currently imports nothing from `roadmap_versions`, and it would need its own `RoadmapVersionError` handling for a corrupt store — a case step 4/5's runners already map to `write-failed` internally. Probing directly duplicates a check the runners already own and tests, and it leaves a second place that answer can drift from the runners' own logic. Call-then-fallback keeps lineage detection owned in exactly one place per lineage (each runner's own run order), matching this plan's stated preference (see steps 2–5's own "Rejected alternatives" sections) for reusing an existing, tested answer over re-deriving it.

### Rendering

`_render_decision_settlement_result(result: DecisionSettlementRunResult) -> None`, matching `_render_feedback_reopen_result`'s redacted shape plus the one extra field:

```
print(f"decision settlement: {result.outcome}")
if result.refusal is not None:
    print(f"reason: {result.refusal}")
if result.receipt_id is not None:
    print(f"receipt: {result.receipt_id}")
```

Never print `decision_value`, `evidence_value`, or anything read from the artifact — the result type is already redacted, and the render function should not reintroduce anything it left out.

### Module docstring

The module docstring (`plan_tool/cli/roadmap_cmd.py`'s top-of-file block) carries one paragraph per broad mode, including the existing `--reopen-feedback`/`--confirm-feedback-reopen` paragraph. Add a matching paragraph for `--settle-decision`/`--settlement-evidence`/`--confirm-decision-settlement`, stating the same facts documented elsewhere in this step: one exclusive action, no backend call, routed to whichever lineage the roadmap is actually on. This keeps the file's own top-of-file documentation in sync with its own dispatch logic the same way every other broad mode already is; it is not a substitute for `docs/how-to/roadmap.md`'s operator-facing procedure, which step 7 owns.

### Docs regeneration

Run `python -m plan_tool.cli_reference --write` after the flags land, and commit the regenerated `docs/cli/roadmap.md`. Do not hand-edit the file — `tests/cli/test_cli_reference.py`'s `TestCliReferenceDrift` checks it against the live parser's output, and a hand-edit that drifts from the generator fails that suite.

### The frozen usage string

`tests/cli/test_roadmap_cmd.py:_FROZEN_BROAD_MODE_USAGE` is a literal, line-wrapped copy of `format_usage()`'s current output. It will fail immediately after the three flags are registered, in three tests already listed under Files → edits. This is expected, not a signal to change dispatch behavior: run the reddened test, read the actual `capsys` output it prints, and replace the literal with the new wrapped text. Because `argparse`'s wrapping depends on the terminal width `shutil.get_terminal_size()` reports at test time, do not hand-compute the new wrapped lines — copy them from a real failing-test run.

## Tests

### Tests for this step

**`tests/cli/test_roadmap_cmd.py`, inside `TestArgparseWiring`:**

- `test_decision_settlement_options_preserve_absent_single_and_repeated_occurrences` — mirrors `test_feedback_reopen_options_preserve_absent_single_and_repeated_occurrences`: absent, single, and repeated occurrences of all three flags round-trip through `_option_occurrences` and the `_..._occurrences` namespace attributes the same way.
- `test_decision_settlement_triple_is_not_a_broad_mode` — mirrors `test_feedback_reopen_pair_is_not_a_broad_mode`: after parsing all three flags, `args._roadmap_mode_occurrences == ()`.
- `test_decision_settlement_help_documents_the_exact_confirmed_triple` — mirrors `test_feedback_reopen_help_documents_the_exact_confirmed_pair`: `--settle-decision`, `--settlement-evidence`, and `--confirm-decision-settlement` all appear in `_roadmap_help()`'s output, alongside whatever "required exactly once" phrase this step's help text uses.

**`tests/cli/test_roadmap_cmd.py`, module scope, alongside the existing `test_feedback_reopen_*` dispatch tests:**

- `test_decision_settlement_dispatches_the_unenrolled_runner_first` — stub both `run_unenrolled_decision_settlement` (returns `settled`) and `run_enrolled_decision_settlement` (an `unexpected` stub that fails the test if called), plus every other orchestrator the way `test_feedback_reopen_dispatches_only_the_confirmed_operation` does. Assert the un-enrolled stub received `(args.slug, decision_value, evidence_value, True)` and `mode_rejected=False`, and the printed output matches `_render_decision_settlement_result`'s shape.
- `test_decision_settlement_falls_back_to_the_enrolled_runner_on_enrolled_roadmap_rejected` — stub `run_unenrolled_decision_settlement` to return `DecisionSettlementRunResult("preflight-rejected", 2, "enrolled-roadmap-rejected")`, and `run_enrolled_decision_settlement` to return `DecisionSettlementRunResult("settled", 0, None, "receipt-final-id")`. Assert both stubs were called, in that order, with identical `(slug, decision_value, evidence_value, confirmation)` positional arguments and the same `mode_rejected`, and that the final printed result and return code come from the enrolled call, including the `receipt:` line.
- `test_decision_settlement_never_falls_back_on_any_other_refusal` (parametrized over a representative sample of step 4's non-lineage refusals, e.g. `missing-decision`, `decision-not-pending`, `source-changed`, `write-failed`/`receipt-rejected` outcomes) — `run_enrolled_decision_settlement` is an `unexpected` stub; the un-enrolled result is rendered and returned unchanged.
- `test_decision_settlement_incomplete_or_repeated_triple_reaches_only_settlement_preflight` — mirrors `test_feedback_reopen_incomplete_or_repeated_pair_reaches_only_reopen_preflight`, parametrized over each of the three flags missing or repeated; asserts `mode_rejected=True` reaches the (stubbed) un-enrolled runner and no other orchestrator is called.
- `test_decision_settlement_confirmation_required_takes_precedence_over_mode_rejected` — drives the real un-enrolled preflight (no stub) with `--settle-decision` and `--confirm-decision-settlement` both absent at once (a decision selector missing *and* the confirm flag missing, in the same invocation); asserts the printed and returned `refusal` is `confirmation-required`, never `mode-rejected`, pinning that confirmation-required fires whenever the confirm flag is absent regardless of what else is also missing or repeated.
- `test_decision_settlement_rejects_every_companion_mode_without_other_dispatch` — mirrors `test_feedback_reopen_rejects_every_companion_mode_without_other_dispatch`, parametrized over every sibling mode's own flags as companions (local revision, receipt creation, impact analysis, structural rewrite, feedback reopen, every view, enrollment, `-y`, `--from-existing`, `--from-stage`, `--apply`, `--mode`, `--id`) — `mode_rejected=True` and no other orchestrator dispatches.
- `test_existing_exclusive_mode_predicates_reject_the_decision_settlement_triple` — mirrors `test_existing_exclusive_mode_predicates_reject_the_feedback_reopen_pair`: for a namespace carrying the three settlement flags, assert `True` from `_enrollment_has_conflict`, `_escalation_creation_has_conflict`, `_escalation_view_has_conflict`, `_impact_analysis_creation_has_conflict`, `_impact_analysis_view_has_conflict`, `_structural_rewrite_has_conflict`, `_feedback_reopen_has_conflict`, `_revise_feedback_has_conflict`, and `_candidate_lifecycle_has_conflict` (this step's sweep is the first to cover all nine; the existing reopen-feedback test does not exercise the candidate-lifecycle predicate, and there is no reason for this new test to repeat that gap).
- `test_decision_settlement_does_not_treat_yes_as_confirmation` — mirrors `test_feedback_reopen_does_not_treat_yes_as_confirmation`: `-y` with no `--confirm-decision-settlement` still reaches the runner with `confirmation=None`.

**`tests/cli/test_roadmap_cmd.py`, new class — a third deliberate real-orchestrator exception, alongside `TestOverwriteAdviceIsPrintedExactlyOnce` and `TestFeedbackSummaryOverTheRealOrchestrator`:**

- `TestDecisionSettlementProducesTheSameRowOnBothLineages` — builds the same domain content (one Roadmap-derived pending decision anchored on an entity, one `ROW`-targeted feedback row citing it with a non-blank `request`) twice: once as an un-enrolled stage file plus baseline (real renderers, `baseline_record`/`render_baseline_record`, matching step 4's own fixture style), once as an enrolled root version (`create_root_version`, `stored_version_members`, `render_accepted_head`, matching `tests/test_roadmap_view.py:_store_version`'s style). Calls `cmd_roadmap` with the identical `--settle-decision`/`--settlement-evidence`/`--confirm-decision-settlement` arguments against each fixture (no invoker needed — neither runner calls a backend), reads the settled decision row back from each (the parsed stage file for the un-enrolled case, the parsed accepted-version member for the enrolled case), and asserts the two `DecisionRow` values are equal field-for-field.
  - Build this fixture locally in the test file; do not import a fixture helper from `tests/test_roadmap_decision_settlement_run.py` or `tests/test_roadmap_decision_settlement_enrolled.py` (those are step 4/5's own test-only helpers in different modules, not a shared fixture library this step should couple to).
  - `test_git_repo_state_after_settlement_shows_only_the_lineage_appropriate_paths_changed` (optional, same class) — a lightweight sanity check that the un-enrolled call touched the stage file/baseline/seed-state and the enrolled call touched only the new version directory and the selector, reusing whatever byte-snapshot idiom step 4/5's own tests already use.

**`tests/test_roadmap_gates.py`:**

- `test_check_settled_decisions_refuses_drift_on_a_row_the_settlement_route_settled` — builds a `pending` `DOMAIN_DECISION` via `make_domain()`, calls `settle_pending_decision(make_domain(), decision_id=DOMAIN_DECISION.id)` to get the settled artifact (the same builder `DecisionSettlementCandidate.settled_artifact` uses), then builds a further revision that alters the settled row (e.g. `status=DecisionStatus.PENDING`, mirroring `test_settled_becoming_pending_violates`'s shape) with the settled artifact as `predecessor`. Asserts `check_settled_decisions` returns exactly one `VIOLATION_ALTERED_SETTLED_DECISION`. This is additional, not redundant, to the existing `_settled_revision()`-based cases: those pin the gate against a hand-authored `SETTLED_DOMAIN_DECISION` constant; this case pins it against the actual output of the function every settlement lineage's writer calls, proving the protection reaches the route's own product rather than only a row an author happened to construct as already settled.

**Verify by breaking the code, not by reading it.** Each break below must turn at least one case red:

| Deliberate break | Case that must go red |
| --- | --- |
| Drop `_has_decision_settlement` from any one sibling `_*_has_conflict` predicate | `test_existing_exclusive_mode_predicates_reject_the_decision_settlement_triple` |
| Drop any one sibling `_has_*` check from `_decision_settlement_has_conflict` | `test_decision_settlement_rejects_every_companion_mode_without_other_dispatch` |
| Call the enrolled runner unconditionally, or on any refusal other than `enrolled-roadmap-rejected` | `test_decision_settlement_never_falls_back_on_any_other_refusal` |
| Never call the enrolled runner at all | `test_decision_settlement_falls_back_to_the_enrolled_runner_on_enrolled_roadmap_rejected` |
| Thread a resolved `repo_root` into either runner call | a signature/argument-shape assertion in the dispatch tests above (an unexpected keyword raises `TypeError` against the real runner's signature once steps 4/5 land) |
| Treat `-y` as `confirmation=True` | `test_decision_settlement_does_not_treat_yes_as_confirmation` |
| Echo `decision_value`/`evidence_value` in the rendered output | the redaction assertions in the dispatch tests |

### Tests for this step (summary)

Approximately 15 new cases across the three declared test files (about 10 in `tests/cli/test_roadmap_cmd.py`'s parsing/dispatch/exclusivity group, 2 in the new lineage class, and 1 in `tests/test_roadmap_gates.py`), plus the three tests that need `_FROZEN_BROAD_MODE_USAGE` re-baselined. Every one must be green before this step counts as finished, and so must the full suite (`uv run pytest tests/ -q -n auto`), which by this point in the plan includes steps 1–5's own suites.

## Acceptance criteria

- `plan-tool roadmap <slug> --settle-decision <SELECTOR> --settlement-evidence <SELECTOR> --confirm-decision-settlement` settles the selected decision on whichever lineage the roadmap is on, with no other option.
- Supplying only one or two of the three flags, or repeating any one of them, returns status 2 with `refusal` reported as `confirmation-required` whenever the confirm flag is absent — regardless of whether a decision or evidence selector is also missing or repeated at the same time — and `mode-rejected` only for every other incomplete-or-repeated combination, matching the runner's own unconditional confirm-first precedence.
- Combining any one settlement flag with any other broad-mode flag or exclusive action returns status 2 from *both* sides: the settlement predicate refuses, and the other mode's own predicate also refuses when given the settlement flags.
- The un-enrolled runner is always tried first; the enrolled runner is called only when the first result is `preflight-rejected` with `refusal == "enrolled-roadmap-rejected"`.
- Neither runner call ever receives a `repo_root` keyword argument.
- The rendered output never contains the decision selector, evidence selector, or any artifact row text.
- The same decision, settled through each lineage with the same selectors, produces field-for-field identical `DecisionRow` content.
- `check_settled_decisions` reports `VIOLATION_ALTERED_SETTLED_DECISION` for a further revision that alters a row built by `settle_pending_decision`.
- `docs/cli/roadmap.md` matches `python -m plan_tool.cli_reference --write`'s output exactly (`tests/cli/test_cli_reference.py` passes).
- `uv run pytest tests/cli/test_roadmap_cmd.py tests/test_roadmap_gates.py tests/cli/test_cli_reference.py -q` passes, and so does `uv run pytest tests/ -q -n auto`.

## References

- `plan_tool/roadmap_feedback_reopen.py` and this file's own `--reopen-feedback`/`--confirm-feedback-reopen` wiring — the confirm-gated-pair CLI shape this step extends to a confirm-gated triple.
- `plan_tool/cli/roadmap_cmd.py` (`_option_occurrences`, `_view_occurrences`, `_broad_mode_companions_present`, `_TrackExclusiveOption`) — the shared machinery every exclusive flag, including this step's three, is built on.
- `plan_tool/roadmap_escalation_run.py` (`receipt_worktree_for_plans_dir`) — resolves the same repo-root value `commit_receipt` needs, without a CLI-level `repo_root` parameter.
- `docs/how-to/roadmap.md` §4 — the hand-edit procedure this action gives operators an alternative to; step 7 updates its prose, not this step.
- `ROADMAP_FORMAT.md` "Decision status" — the existing `settled`/`pending` vocabulary and the standing hand-edit note this action supplements.

## Applicable guardrails

- **The plan's "## Scope guardrails": the route accepts exactly one decision selector per invocation, never a batch.**
  - The `len(...) != 1` checks in `_decision_settlement_has_conflict` are what keep a repeated `--settle-decision` from silently picking "the last one" without refusing — matching `_feedback_reopen_has_conflict`'s identical stance on `--reopen-feedback`.
- **The step's own intent: exclusivity holds no matter which side names the conflicting option.**
  - This is the reason every sibling `_*_has_conflict` predicate is swept, not only the new one. The tempting shortcut is to add the new companion check only to `_decision_settlement_has_conflict` and assume that is enough — it is not, because a companion mode's own predicate is what actually stops a combined command from routing to *that* mode instead.
- **The step's own intent: don't claim anything about the enrolled lineage's drift protection.**
  - The `check_settled_decisions` proof case in `tests/test_roadmap_gates.py` targets only the un-enrolled lineage (a `predecessor` built the ordinary way). The plan-level references and `BUG_BACKLOG.md` already record that `_evaluate_full_roadmap_gates` always passes `predecessor=None` for enrolled candidate promotion, so `check_settled_decisions` is a structural no-op there — do not write a test asserting otherwise, and do not word the acceptance criteria or docstrings to imply the enrolled lineage has the same protection.
- **The plan's "## Out of scope": no judgment of whether cited feedback is genuine approval, and no batch/bulk form.**
  - This step's CLI layer makes no judgment calls of its own; it only threads the operator's selectors and confirm flag to whichever runner applies, and refuses at the same one-decision-per-call granularity the runners already enforce.

## Deferred

- **`docs/how-to/roadmap.md`'s hand-edit procedure, `ROADMAP_FORMAT.md`'s decision-status prose, `docs/ARCHITECTURE.md`'s module entries, and CLAUDE.md's import list** — step 7. This step regenerates only `docs/cli/roadmap.md`, the generated flag reference.
- **A route to abandon or override an unpromoted candidate lineage, and a route to record post-enrollment feedback** — `BACKLOG.md` #395 and #394, per step 5's own Deferred. This step's CLI wiring neither adds nor works around either.
- **Repairing an interrupted settlement journal, on either lineage** — the `BUG_BACKLOG.md` "Incomplete immutable lifecycle journals" entry, per steps 4 and 5's own Deferred. This step's CLI surface reports `journal-unrecoverable` verbatim and does not attempt recovery.
- **Fixing `_evaluate_full_roadmap_gates`'s `predecessor=None` gap so `check_settled_decisions` also protects the enrolled lineage** — its own tracked `BUG_BACKLOG.md` entry, outside this plan.
- **A `--settle-decision` batch/multi-selector form** — explicitly out of the plan's scope guardrails; not a gap this step leaves open by omission.
