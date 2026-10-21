> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add `--apply-split` and `_actuate_split` to actuate a spinning `FORK_LOCALIZED` verdict

## Summary

Grow `plan-tool convergence` a companion actuator to `_actuate_scope_out`: a new `_actuate_split` in `plan_tool/cli/convergence_cmd.py`, reached only for a spinning `FORK_LOCALIZED` verdict, that dispatches the existing split executor (`plan_tool/detail.py:split_step`) instead of minting a new split path. A new `--apply-split` flag (mutually exclusive with `--apply-scope-out`) plus repeated `--into "TITLE"` values drive it; the operator supplies the two sub-step titles because the diagnosis knows the over-packed *step* but not the concern titles to split it into. Actuation stays behind the shared apply-or-recommend gate (recommend-only unless a TTY confirm or `-y`), reuses step 1's `classify_report_staleness` helper so a stale saved report short-circuits identically to scope-out, and calls `split_step` with `author_details=False` so the command stays zero-Claude. `docs/cli/convergence.md` is regenerated from the parser (not hand-edited). On green: `convergence <name> --apply-split -y` on a spinning `FORK_LOCALIZED` verdict restructures the plan deterministically and exits 0; every recommend-only / no-fork path exits 0 and mutates nothing; a mid-split failure exits non-zero.

## Table of Contents

- [Why](#why) — the localized-split arm has detection but no one-command actuation
- [Input](#input) — the fork recommendation, report history, and step-1 staleness helper this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — one module edit, the generated CLI doc, and the test file
- [Implementation](#implementation) — the flags, the actuator, the gate, and how it dispatches `split_step`
- [Tests](#tests) — the feature cases to add and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — argparse mutually-exclusive groups, isatty, pytest monkeypatch
- [Deferred](#deferred) — authoring the halves, the report surface (step 3/4), and the prose docs (step 5)

## Why

`plan-tool convergence` can already *detect* a spinning `FORK_LOCALIZED` verdict — one over-packed step re-found across runs with no shrinkage — and prints the pre-filled `plan-tool split … --into "<first sub-step>" --into "<second sub-step>"` recommendation (`plan_tool/convergence_diagnosis.py:_split_command`). But the operator can only *act* on the scope-out arm: `--apply-scope-out` actuates `FORK_SCOPE_OUT` through `_actuate_scope_out`, and there is no companion flag for the localized re-split. A loop stuck on an over-packed step leaves the operator to copy the recommendation string, fill in the placeholder titles, and run `plan-tool split` by hand. This step closes that gap with a sibling actuator so the diagnosis and its localized remedy live in one command — matching the shape `--apply-scope-out` already established.

## Input

This step consumes three existing contracts; it defines no new schema.

- **`ForkRecommendation` from `classify_fork(diagnosis)`** (`plan_tool/convergence_diagnosis.py`) — read `rec.fork`, `rec.step_focus`, and `rec.command`. This step actuates only when `rec.fork == FORK_LOCALIZED` and `rec.step_focus is not None`; `rec.step_focus` is the over-packed step id to split, and `rec.command` is the placeholder split line to print on recommend-only paths.
- **`ReportHistory` from `load_report_history(path)`**, already held by `cmd_convergence` — passed through to the staleness helper so the split arm short-circuits on a saved report whose `plan_fingerprint` no longer matches the plan on disk.
- **Step 1's staleness verdict.** Step 1 extracts `classify_report_staleness(path, history) -> str` and the constants `STALENESS_FRESH` / `STALENESS_MISMATCH` / `STALENESS_UNVERIFIABLE` into `plan_tool/cli/convergence_cmd.py`. This step reuses that helper verbatim; it does not re-derive the fingerprint comparison. (owned by step 1)
- **`split_step` from `plan_tool/detail.py`** — the executor. It requires `new_titles` (≥2 distinct non-empty), raises `DetailError` when the target step is missing, the plan is not canonically numbered (`1..N`), or the split is unsafe (a step at/after the target already ran/started), and — with `author_details=False` — spends no Claude and never touches the invoker seam.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/convergence_cmd.py` — add module-top imports of `split_step` and `DetailError` from `plan_tool.detail`, `FORK_LOCALIZED` from `plan_tool.convergence_diagnosis`, and `success` from `plan_tool.style` (the module imports only `info, warn` today); add `_actuate_split`; route it from `cmd_convergence` on `args.apply_split`; in `register`, move `--apply-scope-out` and the new `--apply-split` into one mutually-exclusive group and add the `--into` append flag.
  - `docs/cli/convergence.md` — regenerated from the parser (do **not** hand-edit) once the new flags land, via `python -m plan_tool.cli_reference --write`.
  - `tests/cli/test_convergence_cmd.py` — add the `--apply-split` feature cases (see Tests).

## Implementation

**Add the flags in `register`, with the two actuation flags mutually exclusive.**

- Replace the standalone `--apply-scope-out` add with a mutually-exclusive group: `apply_group = p.add_mutually_exclusive_group()`, then add both `--apply-scope-out` and `--apply-split` (`action="store_true"`) to it. This makes passing both a parse error before dispatch, matching the diagnostic's single-verdict classification. Keep `--apply-scope-out`'s help text unchanged.
- Add a separate `--into` flag with `action="append"` (repeatable), a `metavar` like `"TITLE"`, and help that says it names each replacement sub-step title and is used only with `--apply-split`. `--into` is **not** in the exclusive group and is **not** required at parse time — a spinning-localized verdict is only known at runtime, so title validation is dynamic in `_actuate_split`, not argparse-enforced.
- `--apply-split`'s help should state it actuates the localized re-split for a spinning `FORK_LOCALIZED` verdict, is recommend-only unless paired with a TTY confirm or `-y`, and needs `--into` titles.

**Route from `cmd_convergence`.** Beside the existing `if getattr(args, "apply_scope_out", False): return _actuate_scope_out(...)`, add `if getattr(args, "apply_split", False): return _actuate_split(args, ctx, path, diagnosis, history)`. Order does not matter since the flags are mutually exclusive, but keep both behind the same "opt-in actuation" comment. The default no-flag path stays a pure read.

**Add `_actuate_split(args, ctx, path, diagnosis, history) -> int`**, modeled closely on `_actuate_scope_out`. The gate ordering below is what must hold; the exact strings are yours to write (use split wording, not carve wording).

1. **Fork check.** `rec = classify_fork(diagnosis)`. If `rec.fork != FORK_LOCALIZED or rec.step_focus is None`, `info(...)` that no localized split is recommended for this diagnosis (name `diagnosis.verdict` and `rec.fork`) — the flag re-splits a localized fork only, never a scope-out carve or a structural re-seed — and `return 0`.
2. **Staleness gate**, via `classify_report_staleness(path, history)`. Map each verdict to the same disposition `_actuate_scope_out` uses, with split wording:
   - `STALENESS_MISMATCH` → `info(...)` that the saved diagnosis predates the current plan on disk (edited/renumbered since its last audit), so step `rec.step_focus` may no longer be the over-packed step; skip the split and print the refresh hint (`reconcile-plan` / `completeness-audit` then re-run). `return 0`.
   - `STALENESS_UNVERIFIABLE` **and** `args.yes` → `info(...)` refusing to split blind under `-y` (freshness unverifiable — a legacy run predating fingerprint capture); point at an interactive confirm or a refresh. `return 0`.
   - `STALENESS_UNVERIFIABLE` **and not** `args.yes` → `warn(...)` that freshness can't be proven, so confirm below that step `rec.step_focus` is still the over-packed one; fall through to the gate.
   - `STALENESS_FRESH` → fall through, no warning.
3. **Title check.** `titles = list(getattr(args, "into", None) or [])`. If fewer than two distinct non-empty titles, this is recommend-only: `info(...)` that the diagnosis knows the over-packed step but not the two concern titles, so re-run with `--into "…" --into "…"`, and print `rec.command` (the placeholder split line) so the operator sees the exact recipe. `return 0`. Rationale: unlike scope-out (fully deterministic, no titles), a split needs operator-supplied titles — the diagnosis cannot invent them.
4. **Feasibility gate (before the confirm).** Validate with `split_step(..., dry_run=True)` — it runs every pre-mutation check (missing target, non-canonical numbering, unsafe target) and computes the preview without mutating. Catch `DetailError` here → recommend-only: `info(...)`/`warn(...)` naming the reason (unsafe / step-missing / non-canonical) and `return 0`. This ordering is load-bearing: the feasibility validation and its recommend-only short-circuit must run **before** the apply-or-recommend TTY confirm, so the operator is never prompted to confirm a split the executor will refuse. (`_actuate_scope_out` gets this for free because `scope_out_step` validates safety internally before its own confirm; `split_step` has no such internal confirm, so `_actuate_split` sequences the checks itself.)
5. **Apply-or-recommend gate.** Only after the dry run passes: recommend-only on a non-TTY without `-y` — actuate only when `-y` is passed or an interactive confirm returns yes (the exact expression is the implementer's, per the codebase idiom `yes or (sys.stdin.isatty() and <confirm returns yes>)`, as in `scope_out._confirm_scope_out` / `detail._confirm_split`). On a non-TTY without `-y`, or a declined confirm, this is recommend-only: `info(...)` naming the step and titles it *would* split into, print the actuation hint (`convergence <name> --apply-split --into … -y`), and `return 0` with no mutation. `split_step` has **no** built-in TTY gate (unlike `scope_out_step`), so `_actuate_split` owns the confirm — do not rely on the executor for it.
6. **Dispatch the split executor** once the gate passes. Call `split_step(path, target_id=rec.step_focus, new_titles=titles, repo_root=ctx.repo_root, author_details=False)`. `author_details=False` is the key decision: it keeps the deterministic restructure (renumber + rewire + downstream detail-file migration) and never calls the Claude invoker, so the whole convergence command stays zero-Claude and always-exit-0 for a completed outcome — mirroring `--apply-scope-out`. On success, `success(...)` that step `rec.step_focus` was split into the new ids, and print a next-step hint to author the new halves (`plan-tool detail <name>`). `return 0`.

**Exit codes and the refusal-vs-failure split.** The command's convention is 0 on every completed outcome (applied, recommend-only, no-fork), non-zero only on a mid-actuation failure. `split_step` raises `DetailError` only for its *pre-mutation* refusals (missing target, non-canonical numbering, unsafe target — all of which run before its `dry_run` return); once it begins mutating, the real work (`_migrate_downstream_details_after_split`, `write_plan`) surfaces I/O failures as `OSError`, **not** `DetailError`. Distinguish the refusal from the mid-mutation failure so an unsafe target surfaces as recommend-only (exit 0), per the plan's risk note that the split arm inherits the executor's safety limits.

- **One clean way:** this is the feasibility gate (Implementation step 4), which runs **before** the apply-or-recommend confirm (step 5). Validate first with `split_step(..., dry_run=True)` (it runs every pre-mutation check and computes the preview without mutating). Catch `DetailError` there → recommend-only: `info(...)`/`warn(...)` naming the reason (unsafe / step-missing / non-canonical) and `return 0` — so no confirm is ever prompted for a split the executor will refuse. If the dry run succeeds and the confirm gate then passes, run the real `split_step(..., author_details=False)`; any exception from *that* call is a genuine mid-actuation failure → catch the executor's actual mid-mutation surface (`OSError` and `DetailError` — not just `DetailError`), `warn(...)`, and `return 1`. Because the dry run already exhausted the `DetailError` refusals, a broad `except Exception` is also acceptable here.
- You have latitude on the mechanism, but the binding constraints are: refusals (no fork, stale, missing titles, non-TTY-no-`-y`, unsafe/missing/non-canonical target) exit 0 and mutate nothing; a failure after the split began mutating exits non-zero; and the split itself is dispatched to `split_step` (no second split path).

**Constraints and gotchas:**

- **Single-source the split.** Dispatch `split_step` — the same executor `plan-tool split` (`plan_tool/cli/authoring.py:cmd_split`) and the `escalate_to_split` bridge use. Do not reimplement the renumber/rewire. This is the plan's "no new split executor" invariant.
- **Import at module top for the spy convention.** Import `split_step` / `DetailError` into `convergence_cmd.py` at module top so tests can monkeypatch `plan_tool.cli.convergence_cmd.split_step`. `plan_tool.detail` imports cleanly here (the same edge `cmd_split` uses); the module stays a per-intent command module importing only leaves and domain packages — never `plan_tool.cli.app`.
- **Reuse step 1's helper, not a copy.** `_actuate_split` and `_actuate_scope_out` must call the identical `classify_report_staleness`; the only per-actuator difference is the wording and the `-y` message. (owned by step 1)
- **Regenerate, don't edit, `docs/cli/convergence.md`.** The page is generated from the argparse parser and drift-guarded by `tests/cli/test_cli_reference.py`. Put all help wording in `register`, then run `python -m plan_tool.cli_reference --write`. Hand-editing the page fails the drift test.
- **`--into` is a companion, not exclusive.** Only `--apply-split` and `--apply-scope-out` share the mutually-exclusive group. `--into` sits outside it and is ignored on non-split paths.

## Tests

Test file: `tests/cli/test_convergence_cmd.py`. Follow the existing pattern: drive `main(argv)` against the `registered_plan` fixture, seed real sidecars with `save_review`. Add a spinning-**localized** seed helper (mirror `_seed_scope_out`, but with a **medium** `_correctness_rec` so the region forks to `FORK_LOCALIZED`, not scope-out) anchored at a step that exists in a multi-step plan, with `plan_fingerprint=compute_plan_fingerprint(path)`. Reuse `_write_multistep_plan` (canonical `1,2` numbering, all PENDING → splittable).

### Test-creation order (feature step)

This is a **feature** step. Add these unit tests with the implementation; every one must be green before the step is done.

- `test_apply_split_actuates_localized_fork` — a 2-step plan, spinning-localized seed on step 2 (fresh fingerprint), `--apply-split --into "A" --into "B" -y` → exit 0, the plan now has 3 steps (step 2 split in place), and the success line names the split.
- `test_apply_split_invokes_split_step_once` — monkeypatch `plan_tool.cli.convergence_cmd.split_step` with a spy → asserts the **mutating** invocation (`author_details=False`) happens exactly once with `target_id == rec.step_focus` and the supplied titles (pins "no new split executor"). The "One clean way" mechanism dispatches the same symbol twice — a `dry_run=True` validation call then the real `author_details=False` call — so count only the mutating call (filter the spy's recorded calls to the `dry_run` default / `author_details=False` one), not the raw `call_count`, which is 2.
- `test_apply_split_spends_no_backend` — no `@allow_real_claude` marker: a green applied split proves the path shells out to no backend (autouse conftest gate) — pins `author_details=False`.
- `test_apply_split_and_scope_out_mutually_exclusive` — `--apply-split --apply-scope-out` → `pytest.raises(SystemExit)` (argparse rejects before dispatch).
- `test_apply_split_missing_into_recommends_only` — `--apply-split -y` with no `--into` on a spinning-localized verdict → exit 0, mutates nothing, prints the placeholder `plan-tool split` recommendation.
- `test_apply_split_non_tty_recommends_only` — monkeypatch `sys.stdin.isatty` → False; `--apply-split --into "A" --into "B"` (no `-y`) → exit 0, recommend-only, plan unchanged.
- `test_apply_split_yes_bypasses_confirm` — TTY True but `input()` raising if called; `-y` → the split still proceeds (confirm skipped).
- `test_apply_split_noop_on_non_localized_fork` — a scope-out (high-severity) history → `--apply-split -y` → exit 0, "no localized split is recommended", plan unchanged.
- `test_apply_split_stale_fingerprint_recommends_only` — mismatched saved fingerprint → exit 0, "predates the current" + refresh hint, plan unchanged.
- `test_apply_split_empty_fingerprint_refuses_blind_under_yes` — empty newest fingerprint + `-y` → exit 0, refuses to split blind, plan unchanged.
- `test_apply_split_unsafe_target_recommends_only` — a plan where the target/downstream step already ran (non-PENDING) so `split_step` refuses → exit 0, recommend-only naming the unsafe reason, plan unchanged.
- `test_no_flag_still_read_only_on_localized_history` — the default no-flag path on a spinning-localized history mutates nothing and prints the split recommendation (extends the existing read-only coverage).

Green-before-done gate: `uv run pytest tests/cli/test_convergence_cmd.py -q` is green, and `uv run pytest tests/cli/test_cli_reference.py -q` passes after regenerating `docs/cli/convergence.md`.

## Acceptance criteria

- `plan-tool convergence <name> --apply-split --into "A" --into "B" -y` on a spinning `FORK_LOCALIZED` verdict dispatches the mutating `split_step` (`author_details=False`) exactly once and exits 0; a test asserts that mutating call fires once — separate from the `dry_run=True` validation call of the same symbol — and that no new split executor is introduced.
- `_actuate_split` calls `split_step` with `author_details=False`; the applied-split test passes with no `@allow_real_claude` marker (spends no Claude / no backend spawned).
- Passing both `--apply-split` and `--apply-scope-out` raises a parse error (argparse mutually-exclusive group) before dispatch.
- `--apply-split` is recommend-only without a TTY confirm and without `-y` (mutates nothing); with `-y` it actuates. Both branches asserted.
- `--apply-split` with no `--into` (or fewer than two distinct titles) is recommend-only (exit 0, no mutation) and prints the placeholder split command.
- `_actuate_split` short-circuits on a stale (`STALENESS_MISMATCH`) or unverifiable-under-`-y` saved report using the shared step-1 helper, declining to mutate and exiting 0.
- `--apply-split` exits 0 on every completed outcome (applied, recommend-only, no-fork, unsafe target) and non-zero only when the split fails mid-actuation.
- `docs/cli/convergence.md` documents `--apply-split` and `--into`, regenerated from the parser; `tests/cli/test_cli_reference.py` passes.
- The default no-flag `plan-tool convergence <name>` path is unchanged and mutates nothing.

## References

- [argparse — mutually exclusive groups and the append action (Python docs)](https://docs.python.org/3/library/argparse.html#mutual-exclusion) — `add_mutually_exclusive_group()` for `--apply-split` vs `--apply-scope-out`, and `action="append"` for repeated `--into` titles.
- [io — IOBase.isatty (Python docs)](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — the primitive behind `_actuate_split`'s TTY-confirm gate that makes it recommend-only on non-interactive invocations unless `-y`.
- [How to monkeypatch/mock modules and environments (pytest docs)](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — for the spy on `plan_tool.cli.convergence_cmd.split_step` and the `sys.stdin.isatty` / `builtins.input` overrides in the gate tests.

## Deferred

- **Authoring the new halves' detail bodies** — `_actuate_split` runs the split with `author_details=False` to stay zero-Claude; the operator authors the halves with a follow-up `plan-tool detail <name>`. Inline authoring would spend Claude and break the command's zero-Claude contract.
- **The in-report convergence section** — surfacing the diagnosis inside the completeness report is steps 3–4 (`completeness_report.py` renderer, `completeness_phases.py` wiring), not this command. (owned by steps 3–4)
- **Prose docs and BACKLOG #57 reconciliation** — CLAUDE.md / RUNBOOK.md / AUDIT_FLOW.md / BACKLOG.md updates for `--apply-split` are step 5; this step only regenerates the machine-generated `docs/cli/convergence.md`. (owned by step 5)
- **Actuating `FORK_STRUCTURAL`** — re-seed/re-decompose stays recommend-only per `## Out of scope`; there is no `--apply` for it.
- **Consolidating the `plan_match` freshness rule across `review_cmd.py` / `reconcile.py`** — left for a dedicated cross-module change, per step 1's Deferred.
