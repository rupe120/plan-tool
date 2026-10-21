> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add `--apply-scope-out` to the `convergence` command to run the printed carve

## Summary

`plan-tool convergence <name>` already prints a runnable `plan-tool scope-out <name> --step N` line when it forks a spinning plan to `FORK_SCOPE_OUT`, but it never runs it — the operator re-types the command by hand. This step adds one opt-in flag, `--apply-scope-out`, to `plan_tool/cli/convergence_cmd.py` that actuates that printed carve by calling the existing deterministic `plan_tool/scope_out.py:scope_out_step` with the step the diagnosis already resolved. Convergence stays read-only, no-mutation, and always-exits-0 on the default (no-flag) path; the flag changes the contract only when passed. On green: `convergence <name> --apply-scope-out -y` on a spinning-scope-out plan writes the forward-seed and narrows the plan, and the four files touched are the command module, its tests, and the two generated CLI-reference docs.

## Table of Contents

- [Summary](#summary) — what the flag does and the observable result on green.
- [Table of Contents](#table-of-contents) — this list.
- [Why](#why) — the diagnosis-vs-actuation gap this closes.
- [Files (creates vs edits)](#files-creates-vs-edits) — the four in-scope files and their edits.
- [Implementation](#implementation) — the dispatch branch, the reused actuator, and the contract gotchas.
- [Tests](#tests) — the gate-matrix and regression cases to add.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — argparse, frozen dataclasses, TTY checks.
- [Deferred](#deferred) — out-of-scope follow-ups.

## Why

`plan-tool convergence` classifies a spinning plan and, on the `FORK_SCOPE_OUT` arm, prints the fully runnable `plan-tool scope-out <name> --step N` (see `plan_tool/convergence_diagnosis.py:_scope_out_command` and `_spinning_body`). The executor it names — `scope_out.py:scope_out_step` — already ships and spends no Claude. But the diagnosis and the actuation are disconnected: a correct, already-computed remedy still forces a manual copy-and-retype round trip. This step bridges the two so the operator can carve straight from the diagnosis, behind the tool's standard apply-or-recommend gate.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/convergence_cmd.py` — add the `--apply-scope-out` argument to `register()`; add a scope-out actuation branch to `cmd_convergence` guarded by that flag; import `classify_fork` / `FORK_SCOPE_OUT` from `plan_tool.convergence_diagnosis`, `scope_out_step` (and `ScopeOutResult` for typing) from `plan_tool.scope_out`, and the `info` / `success` / `warn` helpers from `plan_tool.style`; soften the module + handler docstrings so the *no-mutation* claim reads as a default-path guarantee (mutation only when `--apply-scope-out` is passed) and the *always-exits-0* claim covers every `ScopeOutResult` outcome (all five still return 0) **except** the post-seed `NarrowError` exception path (see the edge-case bullet in Implementation), which the bridge catches, reports, and exits non-zero on.
  - `tests/cli/test_convergence_cmd.py` — add the gate-matrix and regression cases below.
  - `docs/cli/convergence.md` — regenerated (adds the `--apply-scope-out` Options row).
  - `docs/cli/README.md` — regenerated (idempotent; the convergence summary row is unchanged since the subparser `help=` is untouched).

## Implementation

- **What changes:** add a single opt-in flag that turns the read-only diagnostic into an actuator only when passed. Default behavior stays unchanged. This step chose option (a) from the plan's Architecture — a new flag on `convergence` — over option (b) (moving the bridge to the `scope-out` side); the flag keeps the whole flow (diagnose → decide → carve) in one command so the operator never re-derives the `--step N`, and `convergence` stays pure whenever the flag is absent.

- **Guard the new branch on the flag.** Read `getattr(args, "apply_scope_out", False)` and enter the actuation branch only when it is true. Everything the handler does today — `_load_context`, `resolve_plan_for_context`, `load_report_history`, `diagnose_convergence`, `print(render_diagnosis(...))`, and the `record_convergence` telemetry call — must run first and unchanged, so the no-flag path is a pure read exactly as before. Append the actuation block just before `return 0`.

- **Reuse the fork the render already computed — don't re-derive the step.** Call `classify_fork(diagnosis)` (from `plan_tool/convergence_diagnosis.py`) and actuate only when `rec.fork == FORK_SCOPE_OUT` and `rec.step_focus is not None`. `classify_fork` is a pure function over the diagnosis; on the `FORK_SCOPE_OUT` arm it always carries a concrete `step_focus`, which is the same step number the printed `_scope_out_command` used. Pass `rec.step_focus` straight through as the carve target so the flag applies exactly the carve the operator saw printed.

- **Guard against a stale diagnosis before actuating.** `rec.step_focus` is derived from the plan's *saved report history* (`load_report_history` → `diagnose_convergence`), which can lag the plan on disk; if the plan was edited or renumbered since the last saved run, the resolved step number now points at a different step. `scope_out_step`'s safety gate only rejects a missing or unsafe target, not a wrong-but-present one, and `-y` bypasses the confirm — so an unguarded actuation can silently carve the wrong step. Before calling the actuator, compare the newest saved run's `plan_fingerprint` (from the report history) against the current plan's fingerprint; on mismatch, skip actuation, downgrade to recommend-only (print the same `plan-tool scope-out <name> --step N` line plus a hint to re-run `plan-tool convergence <name>` to refresh the diagnosis before applying), and return 0. Only actuate when the fingerprints match.

- **Call the actuator with the opt-in gate.** Invoke `scope_out_step(path, carved_id=rec.step_focus, repo_root=ctx.repo_root, allow_scope_out=True, yes=args.yes)`. `--apply-scope-out` *is* the opt-in (the `allow_scope_out=True` analog of `scope-out --apply`), and the existing `-y/--yes` parent flag on `convergence` now gains meaning: it is forwarded as `yes=` to bypass the interactive confirm. `scope_out_step` owns the rest of the gate — its `_confirm_scope_out` prompts on a TTY, auto-declines on a non-TTY without `yes` (printing a `-y` hint to stderr and returning `recommended`), and refuses any unsafe carve deterministically. The bridge adds no gate logic of its own; it only supplies `allow_scope_out=True`.

- **Render the frozen `ScopeOutResult` and keep exit 0.** Branch on `result.outcome` — `applied` / `recommended` / `unsafe` / `empty-plan` / `step-missing` — and print a short line per outcome via `style.success` / `info` / `warn`, mirroring the messages `plan_tool/cli/scope_out_cmd.py:cmd_scope_out` already emits (seed path + renumber + cursor on `applied`; the blocker list on `unsafe`). Return 0 for every outcome: a deliberate refusal or recommendation is not a failure-to-complete, matching `cmd_scope_out`'s convention and convergence's always-exits-0 contract.

- **Edge case — the post-seed `NarrowError` raise / orphan seed.** `scope_out_step` is seed-first: `render_carved_seed` writes the forward-seed *before* `apply_narrow` narrows the plan, and a `apply_narrow` IO failure raises `NarrowError` — a documented **sixth, non-`ScopeOutResult` exception path** (`scope_out.py:scope_out_step` docstring) that leaves the already-written seed on disk as a durable orphan artifact. The five-outcome render only covers the returned `ScopeOutResult`; it does not see this raise. Wrap the `scope_out_step` call in a `try` that catches `NarrowError`, prints a `warn` line naming the **orphan seed left on disk** (so the operator can delete or reuse it) plus the failure detail, and **exits non-zero** — a genuine mutation failure-to-complete is not a completed diagnosis, so per the project exit-code convention it must surface as a failure, and the always-exits-0 contract holds only for completed (`ScopeOutResult`-returning) actuation. Let any non-`NarrowError` exception propagate unchanged.

- **Handle "flag passed but nothing to carve."** When `--apply-scope-out` is set but the fork is not `FORK_SCOPE_OUT` (a non-spinning verdict, `FORK_LOCALIZED`, or `FORK_STRUCTURAL`), print one `info` line saying no scope-out carve was recommended for this verdict/fork, so the flag is never a silent no-op, and return 0. Do **not** actuate `FORK_LOCALIZED` (its remedy is `plan-tool split`, a different structural remedy) — `--apply-scope-out` names the carve only.

- **Do not add scope-out telemetry.** `scope_out_step` records no decision event and `cmd_scope_out` records none either, so the bridge must not add one — the existing `record_convergence` call already logs the diagnosis. Adding a second recorder here would be an unmatched, out-of-family event.

- **Do not write a run-log entry.** Neither `convergence` nor `scope-out` writes a run-log entry today; the bridge keeps that — the mutation is journaled inside `apply_narrow`, not logged as a run.

- **Shared location — outcome rendering.** The five-outcome render already lives in `plan_tool/cli/scope_out_cmd.py:cmd_scope_out`. That module is out of this step's `files:` list, so reproduce a compact render inline in `convergence_cmd.py` rather than editing `scope_out_cmd.py`. Consolidating both into one shared `_render_scope_out_result` helper is a refactor that would touch `scope_out_cmd.py` and belongs to a later step — see Deferred.

- **Regenerate the docs, don't hand-edit them.** `docs/cli/convergence.md` and `docs/cli/README.md` are generated by `python -m plan_tool.cli_reference --write` and byte-matched by `tests/cli/test_cli_reference.py`. After the `--apply-scope-out` argument exists on the subparser, run the generator; that is the deliverable for the two doc files, not a hand-written diff.

## Tests

Every test drives the real parse → dispatch path through `main(argv)` against a crafted repo, following the existing `tests/cli/test_convergence_cmd.py` style (real report sidecars via `save_review`). `scope_out_step` spends no Claude and is fully deterministic, so these tests need no invoker stub — the autouse backend gate stays satisfied. Add a high-severity, non-improving recurring-region helper (the existing `_correctness_rec` is `medium`, which forks to `FORK_LOCALIZED`, not scope-out) plus a small helper that writes a real multi-step plan with a carvable edge step.

### Test-creation order (feature step)

This is a feature step — new behavior. Add these unit tests **with** the implementation; every one must be green before the step is done.

- `test_no_flag_is_unchanged_read_only` — `convergence 1-demo` (no flag) on a spinning-scope-out history still exits 0, prints the diagnosis, and mutates no plan file; the regression guard that the default path is untouched.
- `test_apply_scope_out_carves_on_scope_out_fork` — a real multi-step plan whose spinning history resolves `FORK_SCOPE_OUT` to a carvable step; `convergence <name> --apply-scope-out -y` exits 0, prints `applied`, narrows the plan (a survivor renumber or the carved step gone), and writes a forward-seed under `plan-seeds/`.
- `test_apply_scope_out_non_tty_recommends_only` — `--apply-scope-out` without `-y` on a non-TTY (patched `sys.stdin.isatty` → False) exits 0, prints `recommended`, and mutates nothing.
- `test_apply_scope_out_step_missing_reports_and_exits_zero` — the minimal 1-step `registered_plan` with a `step5-…` FORK_SCOPE_OUT history: `--apply-scope-out -y` reaches the actuator, gets `step-missing`, prints it, exits 0, mutates nothing.
- `test_apply_scope_out_last_committed_reports_empty_plan` — a plan whose carve target is the last committed step yields `empty-plan`, reported, rc 0, no mutation.
- `test_apply_scope_out_noop_on_non_scope_out_fork` — a converging (or `FORK_LOCALIZED`, medium-severity) history with `--apply-scope-out` prints a "no scope-out carve recommended" note, calls no actuator mutation, exits 0.
- `test_apply_scope_out_forwards_yes_bypasses_confirm` — with `--apply-scope-out -y` on a TTY (patched `isatty` → True), no interactive prompt is read (the confirm is bypassed) and the carve applies.
- `test_apply_scope_out_stale_fingerprint_recommends_only` — the newest saved run's `plan_fingerprint` no longer matches the current plan (plan edited/renumbered since); `--apply-scope-out -y` skips the actuator, prints a recommend-only line with a re-run-`convergence` hint, exits 0, and mutates nothing.
- `test_apply_scope_out_narrow_error_reports_orphan_seed_and_exits_nonzero` — patch `scope_out_step` (or `apply_narrow`) to raise `NarrowError` after the seed is written; `--apply-scope-out -y` catches it, prints a `warn` line naming the orphan seed on disk, and returns non-zero (not 0).
- `test_apply_scope_out_spends_no_backend` — no `@allow_real_claude` marker; a green run proves the flag path shells out to no backend process.
- `tests/cli/test_cli_reference.py` — its existing drift check stays green after regenerating `docs/cli/convergence.md` / `README.md`.

## Acceptance criteria

- `convergence <name>` with no flag exits 0, mutates nothing, writes no run-log entry, and prints the same diagnosis as before.
- `convergence <name> --apply-scope-out -y` on a spinning `FORK_SCOPE_OUT` plan with a carvable step returns 0 with outcome `applied`, narrows the plan on disk, and writes a `plan-seeds/…` forward-seed.
- The bridge passes `allow_scope_out=True` and `yes=args.yes` to `scope_out_step`, carving exactly `classify_fork(diagnosis).step_focus`.
- Every unattended / non-TTY / declined / unsafe / `empty-plan` / `step-missing` path exits 0, reports the outcome, and mutates nothing.
- A post-seed `NarrowError` (the non-`ScopeOutResult` exception path) is caught, reported with the orphan seed path left on disk, and exits non-zero — the always-exits-0 contract holds only for completed `ScopeOutResult`-returning actuation.
- When the newest saved run's `plan_fingerprint` does not match the current plan, `--apply-scope-out` skips the actuator, downgrades to recommend-only with a re-run-`convergence` hint, exits 0, and mutates nothing.
- `--apply-scope-out` on a non-scope-out fork prints a clear no-op note and exits 0; it never actuates a `FORK_LOCALIZED` split.
- `docs/cli/convergence.md` shows an `--apply-scope-out` Options row and `tests/cli/test_cli_reference.py` passes.
- No new `review.Recommendation` source token and no new structural primitive are introduced; `scope_out_step` and `ScopeOutResult` are reused verbatim.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — defining the `--apply-scope-out` `store_true` flag and wiring it into the `convergence` subparser.
- [dataclasses — Data Classes (frozen=True)](https://docs.python.org/3/library/dataclasses.html) — the frozen `ScopeOutResult` whose `outcome` this branch reads and reports.
- [io — isatty() on stream objects](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — the TTY check `scope_out_step._confirm_scope_out` uses, relevant to the non-TTY-recommends-only test.

## Deferred

- **Shared `_render_scope_out_result` helper** — consolidating the five-outcome render shared with `plan_tool/cli/scope_out_cmd.py:cmd_scope_out` into one helper would touch `scope_out_cmd.py` (outside this step's `files:`); route to reconcile as a follow-up refactor. This step reproduces a compact render inline.
- **Actuating `FORK_LOCALIZED` (split) or `FORK_STRUCTURAL` (re-seed) from convergence** — out of scope; `--apply-scope-out` names the carve only. Bridging those remedies is separate #70 work.
- **Multi-step / multi-region carve** — `scope_out_step`'s single-`--step N` limit stands; a multi-region convergence carve is a separate #70 arm (plan Out-of-scope).
- **Bridge 1 vs BACKLOG #57 ownership** — if #57 (opt-in auto-execution) lands first, this bridge folds into it; option (a) is chosen and stated here so the two don't double-build.
