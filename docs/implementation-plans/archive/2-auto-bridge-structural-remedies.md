> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Auto Bridge Structural Remedies
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add --apply-scope-out to the convergence command to run the printed scope-out
    carve
  files:
  - plan_tool/cli/convergence_cmd.py
  - tests/cli/test_convergence_cmd.py
  - docs/cli/convergence.md
  - docs/cli/README.md
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/auto-bridge-structural-remedies/01-apply-scope-out-convergence-command-run.md
  status: done
- id: 2
  title: Add a gated merge bridge that wraps merge_steps and returns an applied/recommended/unsafe
    result
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/auto-bridge-structural-remedies/02-gated-merge-bridge-that-wraps-merge.md
  scope: deferred
  status_note: 'Deferred (re-scope 2026-07-06): the merge bridge is unreachable from
    any interactive walk without a walk-surfaced pairwise-merge producer, which is
    new detection this plan explicitly excludes (the pairwise producer fires only
    create-side / in completeness''s advisory bucket, never the reconcile/review walk).
    Rather than ship a bridge exercised only by patched tests, defer it to a follow-up
    that adds the producer. This plan now wires two reachable bridges: scope-out (step
    1) and re-ground (step 3).'
- id: 3
  title: Add reground.py with a deterministic mark-done actuator and a gated re-ground
    bridge
  creates:
  - plan_tool/reground.py
  - tests/test_reground.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/auto-bridge-structural-remedies/03-reground-py-deterministic-mark-done.md
  status: done
- id: 4
  title: Make the re-ground finding emit a distinct, parseable suggested action
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/auto-bridge-structural-remedies/04-make-granularity-merge-re-ground.md
  status: done
- id: 5
  title: Wire the walk to dispatch re-ground findings to the re-ground bridge by finding
    shape
  files:
  - plan_tool/review_walk.py
  - plan_tool/cli/review_actions.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/reconcile.py
  - tests/cli/test_review_actions.py
  complexity: high
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/auto-bridge-structural-remedies/05-wire-walk-dispatch-merge-re-ground.md
  status: done
  status_note: 'test-authoring gate exempted: step 5''s walk-dispatch implementation
    and its tests (tests/cli/test_review_actions.py) were authored in the interrupted
    run and committed as WIP; the resumed call found the work already done so touched
    no test file. Deliverable complete, full suite green (one over-strict merge-routing
    test in tests/test_reground.py relaxed). Marked done directly.'
- id: 6
  title: Update CLAUDE.md and RUNBOOK to describe the two new bridges and drop stale
    recommend-only wording
  files:
  - CLAUDE.md
  - RUNBOOK.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 5
  detail: docs/implementation-plans/plan-details/auto-bridge-structural-remedies/06-update-claude-md-runbook-describe-three.md
  status: done
---
# Auto Bridge Structural Remedies

## Overview

Builds the **auto-bridges arm** of BACKLOG **#70** (Structural-remedy vocabulary: remaining convenience arms). The detection and *recommendation* half of the split/merge/scope-out/re-seed vocabulary already ships, but several remedies today print a recommendation and stop short of running the actuator that already exists, forcing the operator to re-type the command by hand. This plan wires two of those bridges — scope-out (`convergence` → `scope_out_step`) and re-ground (reconcile's `_reground_already_built_recommendation` → mark-done / re-baseline) — each behind the tool's standard **apply-or-recommend gate** so the operator can actuate straight from the diagnosis. Both are reachable end-to-end. The **merge bridge (`granularity-merge` → `plan-tool merge`) is deferred** to a follow-up and is *not* built here: reaching it from an interactive walk needs a walk-surfaced pairwise-`granularity-merge` producer, which is **new detection this plan explicitly excludes** — the pairwise producer fires only in create's change-type review, detail's `split_criteria`, and `completeness_phases.py`'s advisory Smells bucket, none of which is the reconcile/review walk. Shipping a bridge exercised only by patched tests would be dead production code, so it waits for the producer follow-up (step 2 is parked `scope: deferred`). It adds the gated wiring between existing producers and executors plus exactly one new actuator — re-ground's deterministic, no-Claude `mark_steps_done` (step 3), whose re-baseline (`create --from-existing`) arm stays deferred and human-authored: no new detection, no other new actuator logic, no new `review.Recommendation` source token, and no new structural primitive.

## Problem statement

The structural-remedy vocabulary detects mis-decompositions and prints runnable remedy commands, but the operator must copy and re-type them by hand — the diagnosis and the actuation are disconnected even though both the finding producer and the mutation executor already exist. Concretely: `plan-tool convergence` classifies `FORK_SCOPE_OUT` and prints `plan-tool scope-out <name> --step N` but never runs it; `granularity.py`'s `granularity-merge` finding is recommend-only (kept out of `APPLY_ELIGIBLE_SOURCES`) so re-combining is always hand-run via `plan-tool merge`; and reconcile's `_reground_already_built_recommendation` fires on already-built steps but its re-ground / re-baseline remedy has no bridged actuator. The user-visible symptom is friction and transcription error: a correct, already-computed remedy requires a manual round-trip to apply.

## Architecture

Three bridges, each reusing the **apply-or-recommend gate** shape already implemented twice — `launcher.py:escalate_to_split` and `scope_out.py:scope_out_step`. The gate: the default path spends no Claude and only *recommends*; it mutates **only** when all of (a) an explicit `--apply` opt-in, (b) an interactive TTY **confirm `yes`** (which `-y` deliberately bypasses), and (c) the relevant read-only **safety gate** hold. Every unattended / non-TTY / declined / unsafe path recommends only.

**Bridge 1 — Scope-out (`convergence` → `scope_out_step`).** `plan-tool convergence` is contractually read-only, no-mutation, always-exits-0, so the bridge must not silently break that. Resolve first between (a) keeping `convergence` pure and adding an explicit new opt-in flag (e.g. `--apply-scope-out`, gated exactly like `scope-out --apply`) that changes the contract only when passed, or (b) leaving `convergence` pure and adding the bridge on the `scope-out` side. Pick (a) or (b) and state why in the plan. Reuse `scope_out_step`'s `ScopeOutResult` outcomes verbatim (`applied` / `recommended` / `unsafe` / `empty-plan` / `step-missing`); only `applied` mutates.

**Bridge 2 — Merge (`granularity-merge` → `plan-tool merge`) — DEFERRED, not built in this plan (re-scope 2026-07-06; see Deferred).** Reaching it needs a walk-surfaced pairwise-merge producer (new detection this plan excludes), so the whole bridge — executor, step-4 directive, step-5 dispatch — moves to a follow-up rather than shipping test-only code. The design below is retained as that follow-up's starting point. From a surfaced `granularity-merge` finding (adjacent fragmented dependent steps), offer the gated `plan-tool merge --steps N --steps M`. Reuse the existing merge executor and its safety gate (`_merge_is_safe` — no non-`PENDING` step after the region). The bridge selects the flagged member set as the merge args; the operator confirms. Recommend-only unless `--apply` + confirm hold, same gate as bridges 1 and 3. **Dispatch is producer-deferred.** Step 5 builds the gated `merge_bridge` and wires a `merge`-kind dispatch branch into the reconcile/review walk, but no step in this plan surfaces a `merge`-kind `granularity-merge` finding *into that walk*: the pairwise producer (`granularity.py:_merge_rec` via `assess_granularity`) fires only in create's change-type review, detail's `split_criteria`, and `completeness_phases.py`'s advisory Smells bucket — none of which is the interactive apply walk `saved.recommendations` feeds. So the merge branch ships live in code but exercised by synthetic unit-test recs only, mirroring the explicit create-side deferral; wiring a walk-surfaced merge producer is the follow-up that makes it reachable end-to-end. **Gapped-pair resolution:** `granularity-merge`'s `depends_on`-adjacent signal can flag a pair whose ids are **non-contiguous** (e.g. refactor step 1 whose only dependent is feature step 4 → directive `(1, 4)`), but `merge_steps` → `create.py:_apply_step_merge` rejects any id run with gaps. The bridge must **not** assume the flagged pair is contiguous: it offers the executor only an already-**contiguous** flagged member set. A **gapped** pair is classified **un-actuatable** — the bridge recommends the manual path (the operator re-runs `plan-tool merge` by hand after deciding how to restructure) and never auto-widens the directive to the full `lo..hi` run, since widening would fold in the un-flagged intermediate steps and silently reshape the plan against the gate's recommend-first conservatism.

**Bridge 3 — Re-ground (reconcile's `_reground_already_built_recommendation` → mark-done / re-baseline).** This finding fires on **≥2 distinct already-built steps** and reuses the `granularity-merge` literal, but its remedy is **re-ground / re-baseline (mark the already-built steps done, or re-decompose), NOT a blind `merge`** — so this bridge is deliberately different from bridge 2 and must **not** route to `plan-tool merge` (that would conflate re-ground with structural merge, the exact confusion the neutral-`triage_reason` routing already guards). Open design point: the actuator ('mark these steps done / re-baseline') may not have a first-class command yet; decide whether to (a) reuse an existing status-advance path behind the gate, or (b) add a small `--apply` mark-done actuator.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — Official reference for defining the new opt-in flags (e.g. --apply-scope-out, -y) and subparser wiring that each bridge adds to the plan-tool CLI.
- [dataclasses — Data Classes (frozen=True)](https://docs.python.org/3/library/dataclasses.html) — Documents frozen/immutable dataclasses, the pattern behind the ScopeOutResult/EscalateResult-style frozen outcome objects the bridges must reuse and report.
- [io — isatty() on stream objects](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — Reference for the interactive-TTY check underlying the apply-or-recommend gate's non-TTY vs interactive-confirm decision.
- [os.isatty — low-level file-descriptor TTY test](https://docs.python.org/3/library/os.html#os.isatty) — The file-descriptor-level TTY detector an implementer consults when deciding whether the confirm-yes path should run unattended.
- [pytest: How to mark test functions with attributes](https://docs.pytest.org/en/stable/how-to/mark.html) — Explains registering and using custom markers like @pytest.mark.integration used to gate the end-to-end CLI-wiring tests for each bridge.
- [pytest: How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Reference for overriding module-level seams (the invoker gate) so bridge unit tests stay deterministic and never spawn a real backend.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Structural re-seed limit** (split-everything / `create --from-existing`) — stays human-authored; an auto-re-decompose that guesses wrong silently reshapes the plan's spine.
- **Multi-step / multi-region carve** — `scope-out`'s single-`--step N` limitation and the multi-region `convergence` focus are a separate #70 arm.
- **Code-reveals-a-split detection** — the missing producer is the third #70 arm, not a bridge (nothing to bridge until it emits a finding).
- **Any change to how findings are detected** — this plan only actuates existing findings; it adds no new detection.

## Risks

- **Breaking `convergence`'s read-only / always-exits-0 contract** — bridge 1 must not silently mutate from a command defined as pure; mitigated by requiring the mutation path behind an explicit new opt-in flag (or moving the bridge to the `scope-out` side) so the contract changes only when the flag is passed.
- **Conflating re-ground with structural merge** — bridge 3 reuses the `granularity-merge` literal but has a different remedy; routing it to `plan-tool merge` would defeat the neutral-`triage_reason` guard. Mitigated by keeping bridge 3 on a mark-done / re-baseline actuator, never `merge`.
- **Double-building with #57** — bridge 1 overlaps the opt-in auto-execution lever tracked in BACKLOG #57; mitigated by stating the chosen split in the plan (fold bridge 1 into #57 if that's picked up first, otherwise carry it here).
- **Unattended mutation** — the reused gate must recommend-only on every unattended / non-TTY / declined / unsafe path; a gap would let a bridge mutate without confirmation.
- **Re-ground actuator may not exist yet** — the 'mark steps done / re-baseline' path may need a small new `--apply` actuator, an open design point that could widen scope if a first-class command has to be added.

## Testing

Follow the project's unit-first convention (TESTING.md): default to unit tests exercising one function/class in isolation, mirroring source modules (`plan_tool/X.py` → `tests/test_X.py`), and neutralize the invoker seam — though these bridges spend no Claude on the default path, so most coverage is deterministic. Unit-test each bridge's gate decision across the matrix: unattended, non-TTY, declined confirm, `-y` bypass, unsafe safety-gate, and the `--apply` + confirm success path — asserting only `applied` outcomes mutate and every other path recommends only and spends no Claude. Assert bridge 3 never routes to `plan-tool merge`. Add `@pytest.mark.integration` tests only for the CLI wiring — driving `plan-tool convergence` (or the chosen bridge-1 surface) and `plan-tool merge` entry points end-to-end to confirm the flag parses, the safety gate fires, and the frozen result object reports recommended-vs-applied. Existing suites for the reused surfaces must still pass (`tests/test_scope_out.py`, the merge executor tests, `tests/test_convergence*`, `tests/test_review.py`, `tests/test_granularity.py`).

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- The scope-out bridge mutates a plan **only** when `--apply` (or the chosen opt-in flag) + TTY confirm + safety gate all hold; every unattended / non-TTY / declined / unsafe invocation exits without mutation and spends no Claude.
- If bridge 1 keeps `convergence` pure, `plan-tool convergence <name>` with no bridge flag still exits 0, mutates nothing, and writes no run-log entry.
- The scope-out bridge reuses `ScopeOutResult`'s outcomes verbatim (`applied` / `recommended` / `unsafe` / `empty-plan` / `step-missing`) and only `applied` mutates.
- The re-ground bridge is reachable end-to-end from the reconcile/review walk: because `_reground_already_built_recommendation` is `info`-severity, the walk surfaces and dispatches it only when **both** `--apply-structural` **and** `--include-info` are passed — step 5 and this acceptance name the two-flag requirement; with either absent the finding is filtered out or stays recommend-only.
- Re-ground's confirm gate (`_confirm_reground`) surfaces the flagged step ids/files and the "confirm the steps really are built" caveat **before** `mark_steps_done` flips `PENDING → DONE`, so the operator can verify builtness at the one gate that guards the drop (a false positive on the low-confidence heuristic silently removes real work from the run queue).
- The re-ground bridge never routes to `plan-tool merge`; its actuator is the new deterministic `mark_steps_done` behind the same gate, while re-baseline (`create --from-existing`) stays deferred and human-authored.
- The merge bridge is **not** built in this plan (deferred — see Deferred); no acceptance criterion here depends on a reachable merge bridge.
- No new `review.Recommendation` source token and no new structural primitive are introduced.
- Each bridge reports its outcome so the caller can distinguish recommended-vs-applied.

## Deferred

- **Re-ground first-class mark-done actuator** — if the mark-done / re-baseline path has no existing status-advance command to reuse, adding a small `--apply` actuator may be deferred or scoped as its own step pending the open design decision.
- **Bridge 1 vs #57 ownership** — if BACKLOG #57 (opt-in auto-execution) is picked up first, bridge 1 folds into it rather than shipping here; the chosen split is stated in the plan so the two entries don't double-build.
- **The whole merge bridge — deferred, not built here (re-scope 2026-07-06).** Bridge 2 (the gated `merge_bridge` executor), its step-4 `merge` directive, and its step-5 merge dispatch all wait for a follow-up. Reaching a merge bridge from an interactive walk needs a walk-surfaced pairwise-`granularity-merge` producer, which is **new detection this plan excludes** (the pairwise producer fires only in create's change-type review, detail's `split_criteria`, and `completeness_phases.py`'s advisory Smells bucket — never the reconcile/review walk). Building the executor + dispatch without a producer would ship code exercised only by patched tests, so the whole bridge waits for the producer follow-up. Step 2 is parked `scope: deferred`; steps 4–5 scope down to re-ground only.
