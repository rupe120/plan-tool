# Step 8 — Add the `--iterate` apply/convergence loop to `security` (host loop for step 9's auto-apply)

## Summary

Adds an opt-in `--iterate` apply/convergence loop to `plan-tool security`, modeled on the `plan_tool/cli/completeness_phases.py:_run_iterate_convergence_loop` pattern. Under `--iterate`, `plan_tool/cli/security_cmd.py:cmd_security` runs `run_security_audit` once up front, filters the findings to the **apply-eligible** subset via step 7's `security_finding_is_auto_applicable`, routes each eligible finding through `plan_tool/launcher.py:apply_finding`, re-audits, and repeats until `plan_tool/convergence.py:should_continue` says stop. The primary edit is a new `_run_security_iterate_loop` helper plus an `--iterate` (BooleanOptionalAction, **default False**) and the iteration-knob flags on the `security` subparser; the thin no-loop dispatch from step 3 stays the default path (one-shot audit). **Load-bearing decision:** this is the *host* loop only — with step 7's `SECURITY_AUTO_APPLY_ALLOWLIST` empty, the apply-eligible set is empty, so the loop takes the explicit empty-eligible early-exit *before* it seeds `state`/`current_finding_ids` or enters `should_continue` (see the "Inert short-circuit" step below). Because that early-exit keys solely on the eligible set being empty — **not** on `has_blocking_findings` — it fires regardless of severity, so even an audit carrying blocking (`MEDIUM`/`HIGH`/`CRITICAL`) non-allowlisted findings short-circuits to a single audit pass (byte-equivalent claude spend to the one-shot path); the byte-equivalence does not rely on `should_continue`'s `no_blocking_findings` stop reason. Step 9 populates the allowlist; only then does the apply/re-audit cycle actually iterate. On green, `plan-tool security <name> --target plan --iterate` runs exactly one audit (nothing eligible), `apply_finding` is never called, rc stays 0, and the conftest real-backend gate never fires.

## Table of Contents

- [Why](#why) — why the loop lands now, inert, ahead of step 9's auto-apply
- [Files (creates vs edits)](#files-creates-vs-edits) — the security_cmd loop + the eligibility filter; parser.py is a declared non-edit
- [Implementation](#implementation) — the dispatch wrap, the loop helper, the eligibility filter, the apply seam
- [Tests](#tests) — flag parse, one-shot default, inert short-circuit, apply/re-audit cycle, stop reasons
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse + headless grounding
- [Deferred](#deferred) — allowlist population, --commit, per-target apply semantics, reconcile composition

## Why

- **`plan-tool security` is one-shot today.** Steps 1–4 land `run_security_audit` + the CLI verb; steps 5–7 land the next-step pointer, its relevance gate, and the default-empty auto-apply allowlist primitive. Nothing yet *loops* — a security audit produces findings once and exits. There is no host loop for the auto-apply channel step 7 opened.
- **Step 9 needs a loop to plug into.** Step 7 shipped `is_security_auto_apply_eligible` / `security_finding_is_auto_applicable` **inert** (empty allowlist → always `False`). Auto-apply is meaningless without a convergence loop that consults that gate, applies the eligible findings, and re-audits. This step is that loop — wired end-to-end, but inert until step 9 fills the allowlist.
- **Land the host loop before the apply channel opens.** Shipping the loop now (with nothing eligible) keeps the step single-axis and lets step 9 be a one-line frozenset edit that flips the loop from "audits once" to "applies + re-audits", rather than wiring the loop and opening the channel in one pass. This mirrors the captured rule: step N lands a disabled-by-default host, the named successor enables it.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/cli/security_cmd.py` (created in step 3) — add `_run_security_iterate_loop(...)`; add the `budget.enabled` branch to `cmd_security` that calls it (the `not budget.enabled` path is step 3's unchanged one-shot dispatch); add a local `iterate_parent` with `--iterate` (BooleanOptionalAction, default False), `--max-iterations`, `--iteration-budget`, `--max-stall-rounds` in `register()` and attach it to the `security` subparser via `parents=[...]`.
- `plan_tool/security_audit.py` (created in step 1, extended in 2/4/6/7) — add the pure `apply_eligible_security_findings(result, *, allowlist=SECURITY_AUTO_APPLY_ALLOWLIST) -> list` filter that selects the findings the loop may apply, delegating to step 7's `security_finding_is_auto_applicable`. Single-sources eligibility selection beside step 7's adapter; no new claude call, no new imports beyond the step-7 symbols already present.
- `plan_tool/cli/parser.py` — **declared in scope but no edit required.** The `--iterate` family reaches only the `security` subcommand, so the flags live in `security_cmd.py:register()`'s local `iterate_parent` (the `run_cmd.py:register` / `completeness_cmd.py:register` convention), **not** `make_base_parser`. Contrast step 6's `--no-security-hint`, which *did* go in `make_base_parser` precisely because it reaches **multiple** subcommands. `CANONICAL_COMMAND_ORDER` already lists `security` (step 3). Confirm no parser.py change is needed rather than forcing one.

**Test files (edits):**

- `tests/cli/test_security_cmd.py` (created in step 3) — the loop's parse-contract, dispatch, convergence, and exit-code cases (below).
- `tests/test_security_audit.py` (created in step 1) — unit cases for `apply_eligible_security_findings` (beyond the step's declared `tests/cli/test_security_cmd.py`; required by the `plan_tool/X.py → tests/test_X.py` convention since the filter lives in `security_audit.py`).

## Implementation

### `plan_tool/security_audit.py` — `apply_eligible_security_findings`

- **Signature:** `apply_eligible_security_findings(result: SecurityAuditResult, *, allowlist: frozenset[str] = SECURITY_AUTO_APPLY_ALLOWLIST) -> list[Recommendation]`.
- **Body:** return `[rec for rec in result.findings if security_finding_is_auto_applicable(rec, allowlist=allowlist)]`. Pure, order-preserving, no I/O.
- **Why here, not inline in the loop:** keeps the apply-eligibility selection single-sourced beside step 7's `security_finding_is_auto_applicable` / `security_auto_apply_category` adapter, so the loop never re-derives the eligibility rule. The keyword-only `allowlist` param (defaulting to the module constant) is the test seam — a test passes a non-empty allowlist to exercise the apply path without editing step 7's constant.
- **Inert default:** with the step-7 default (empty `SECURITY_AUTO_APPLY_ALLOWLIST`), this returns `[]` for every `SecurityAuditResult` — the load-bearing fact the loop's short-circuit below relies on.

### `plan_tool/cli/security_cmd.py` — dispatch wrap in `cmd_security`

- **Resolve the budget once,** mirroring `completeness_cmd.py:cmd_completeness`: `budget = _resolve_iterative_budget(args)` (import from `plan_tool.cli.context`). It reads `args.iterate` → `IterativeBudget.enabled`. Catch `CreateError` and `return 2` (the `--max-iterations 0` etc. path), exactly as `cmd_completeness` does.
- **Branch on `budget.enabled`:**
  - `not budget.enabled` → step 3's existing one-shot path verbatim (call `run_security_audit`, render, `write_security_report`, honor `--fail-on-findings`). Unchanged.
  - `budget.enabled` → `result = _run_security_iterate_loop(args, path, ctx, budget, invoker=invoker)`; if the loop returns an early-exit rc (parse failure after an apply), return it; otherwise render/persist/`--fail-on-findings` the **final** `SecurityAuditResult` through the same step-3 tail (single writer — `write_security_report` persists once).
- **`--iterate` is not a no-op here** (contrast `run`), so it must *not* warn — it drives a real apply loop.

### `plan_tool/cli/security_cmd.py` — `_run_security_iterate_loop`

Model member-for-member on `plan_tool/cli/completeness_phases.py:_run_iterate_convergence_loop`, minus the scope-guard/drift/iteration-lock machinery (defer — see Deferred), keeping only the audit → triage → apply → re-audit → `should_continue` core:

- **Body-local import the claude seams** inside the function (mirroring `completeness_cmd`'s body-local `from plan_tool.launcher import apply_finding`): `from plan_tool.launcher import apply_finding`. This keeps the domain suites' monkeypatch seam (`plan_tool.launcher.apply_finding`) intercepting through `main()` with zero retarget.
- **Round 0 — up-front audit:** `result = run_security_audit(target=..., invoker=invoker, ...)` (the same call the one-shot path makes). Construct `state = ConvergenceState(budget=budget)`. **Call `touch(state)` immediately after** the audit — round-0 audit can take minutes, and `last_activity_at` is stamped at construction; without the touch the deadline can fire at iteration 0 (the captured `ConvergenceState` NOTE).
- **Inert short-circuit (load-bearing):** `eligible = apply_eligible_security_findings(result)`; **if `not eligible`, return `result` unchanged** — no second audit, no `apply_finding`. With step 7's empty allowlist this is *always* the taken branch, so `--iterate` spends exactly one claude audit. Step 9's allowlist edit is what makes `eligible` non-empty and reaches the loop below.
- **Convergence loop** (`eligible` non-empty — step 9+):
  - Seed `state.current_finding_ids = frozenset(r.id for r in eligible)`; `state.has_blocking_findings = any(is_blocking(r.severity) for r in eligible)`.
  - `while True: cont, reason = should_continue(state); if not cont: break`.
  - For each `rec` in `eligible`: `apply_finding(path, repo_root=ctx.repo_root, finding_body=rec.body, step_id=rec.step_id, targeted_fix=audit_targeted_fix(rec), plan_name=args.name, invoker=...)` — derive the fix via `review.audit_targeted_fix(rec)` (`Recommendation` has no `targeted_fix` field; the remediation lives in `suggested_action`, which `audit_targeted_fix` reads, matching every other apply site). `touch(state)` between applies (each call is 10–15 min; debounce the deadline).
  - After applying the round's findings, **re-audit**: `result = run_security_audit(...)`; recompute `eligible = apply_eligible_security_findings(result)`; `record_iteration(state, (r.id for r in eligible))`; refresh `state.has_blocking_findings`.
  - **Re-parse guard:** if the plan fails to parse after an apply (`ParseError`/`ValidationError` from the re-audit's `parse_plan`), emit a warning and return an early-exit rc 2 (mirror `_run_iterate_convergence_loop`'s `early_exit_code=2`).
- **Return** the final `SecurityAuditResult` (its `persisted_path` stays `None` so `cmd_security`'s tail persists once — the step-2/step-4 single-writer contract).
- **Stop reasons** come straight from `should_continue`: `converged` (eligible set empty after a round), `no_blocking_findings`, `max_iterations`, `deadline_exceeded`, `no_progress` (stall). Log the one-line stop reason like `completeness_cmd` does.

### `plan_tool/cli/security_cmd.py` — `register()`

- **Add a local `iterate_parent`** (`argparse.ArgumentParser(add_help=False)`) mirroring `run_cmd.py:register`'s, carrying `--iterate` (`action=argparse.BooleanOptionalAction, default=False`), `--max-iterations`, `--iteration-budget`, `--max-stall-rounds`. Attach via `parents=[..., iterate_parent]` on the `security` `add_parser(...)`.
- **`--iterate` default False** is the step's contract (one-shot by default; `--iterate` opts in) — the same default `run` uses, the opposite of `completeness`'s default-ON.
- **No `COMMAND_MODULES` / `CANONICAL_COMMAND_ORDER` edit** — `security` is already registered (step 3); this only adds flags to its existing subparser.

### Foundational logic & shared call sites

- **Foundational logic:** an apply/convergence loop keyed on `should_continue` + `record_iteration` + per-finding `apply_finding`.
- **Parallel call sites (do not consolidate here):** `plan_tool/cli/completeness_phases.py:_run_iterate_convergence_loop`, `plan_tool/cli/run_cmd.py` (reconcile iterate), and `plan_tool/cli/authoring.py:cmd_create`/`cmd_detail` post-write loops all run the same `should_continue`/`apply_finding`/`record_iteration` shape. Each is bespoke (different finding sources, drift posture, persistence). Extracting one shared loop driver is a cross-command refactor `detail` cannot mint → **Deferred**.
- **Apply-eligibility gates (the three, per the captured fact):** `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES`, `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES`, and `plan_tool/convergence.py:SECURITY_AUTO_APPLY_ALLOWLIST`. This step consults **only** the third (via `apply_eligible_security_findings` → `security_finding_is_auto_applicable`). It is a **load-bearing non-edit** to leave `security-plan`/`security-code` out of the first two — adding them would flip every security finding from advisory to mechanically-applied, bypassing the allowlist channel.

## Tests

### Test-creation order (feature step)

This is a **feature** step (new loop behavior). Write each test alongside the code it covers; every new test must be green before the step is done.

In `tests/test_security_audit.py` (the filter):

- `test_apply_eligible_empty_under_default_allowlist` — `apply_eligible_security_findings(result)` returns `[]` for a result of mixed-category findings under the default empty allowlist.
- `test_apply_eligible_selects_allowlisted_category` — with an injected non-empty allowlist matching one finding's category, only that finding is returned, order preserved.
- `test_apply_eligible_excludes_anchorless_finding` — a finding whose `anchor` is absent (step 7's `security_auto_apply_category` → `None`) is never eligible, even under a non-empty allowlist.

In `tests/cli/test_security_cmd.py` (the loop; stub `run_security_audit` and patch `plan_tool.launcher.apply_finding` so neither spawns claude):

- `test_iterate_flag_parses_default_false` — `security <name> --target plan` parses `args.iterate is False`; `--iterate` sets it `True`; `--no-iterate` sets it `False`.
- `test_iterate_disabled_runs_one_shot` — without `--iterate`, `run_security_audit` is called exactly once and `apply_finding` (stubbed to raise) is never called.
- `test_iterate_empty_allowlist_short_circuits` — with `--iterate` and the default empty allowlist, `run_security_audit` is called exactly **once** (no re-audit), `apply_finding` never called, rc 0. Pins the host-loop-inert contract.
- `test_iterate_applies_eligible_then_reaudits` — inject a non-empty allowlist; `run_security_audit` returns one eligible finding round 1 then a clean result; assert `apply_finding` called once with `finding_body`/`step_id` from the finding, `run_security_audit` called twice, loop converges, rc 0.
- `test_iterate_stops_at_max_iterations` — eligible finding never clears (stub returns it every round); `--max-iterations 2`; `apply_finding` called twice, stop reason `max_iterations`, rc 0.
- `test_iterate_parse_failure_halts_rc2` — `apply_finding` leaves the plan unparseable; the post-apply re-audit's `parse_plan` raises; loop returns rc 2.
- `test_iterate_fail_on_findings_flips_rc` — surviving findings + `--fail-on-findings` → non-zero rc; without the flag → rc 0 (exit-code convention).
- `test_iterate_persists_final_report_once` — `write_security_report` called exactly once, with the loop's final `SecurityAuditResult`.
- `test_iterate_no_real_backend` — drive `main(["security", ...])` with `run_security_audit`/`apply_finding` stubbed; the conftest real-backend gate never fires (no `@pytest.mark.allow_real_claude`).

## Acceptance criteria

- `plan-tool security <name> --target plan --iterate` exits 0 and (under step 7's empty allowlist) calls `run_security_audit` exactly once and `apply_finding` zero times.
- `apply_eligible_security_findings(result)` returns `[]` for any result under the default allowlist; returns only the allowlisted-category findings under a non-empty injected allowlist.
- Without `--iterate`, `cmd_security` behaves byte-identically to step 3 (one-shot audit, single `write_security_report`).
- With a non-empty allowlist (test-injected), the loop applies each eligible finding via `apply_finding`, re-audits, and stops on a `should_continue` reason; rc 0 on clean completion, rc 2 on post-apply parse failure.
- `--iterate` does **not** emit a no-op warning (contrast `run`).
- `tests/cli/test_security_cmd.py` and `tests/test_security_audit.py` new cases pass under `uv run pytest -m "not integration"`; the conftest real-backend gate stays green.
- No edit to `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` or `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES`; `plan_tool/cli/parser.py` unchanged.

## References

- [argparse — `add_subparsers()` / `BooleanOptionalAction` (Python docs)https: — the `--iterate` BooleanOptionalAction (default False) + the `parents=[iterate_parent]` wiring on the `security` subparser.
- [Claude Code Headless Mode (Anthropic docs)https: — exit-code behavior the loop relies on when re-auditing through `shell_security_invoker` and applying through `apply_finding`'s invoker.

## Deferred

- **Allowlist population** — `SECURITY_AUTO_APPLY_ALLOWLIST` stays empty here; step 9 opens the apply channel by adding categories, at which point this loop's apply/re-audit cycle becomes live.
- **Scope-guard / drift / iteration-lock machinery** — `_run_iterate_convergence_loop`'s `ScopeGuardBuffer`, `iteration_session`, and `_run_auto_reconcile_on_drift` are omitted; the security loop edits the plan/detail only (no in-run code-drift set). Add when/if the loop is shown to need drift protection.
- **`--commit`** — `completeness-audit --iterate --commit` commits loop edits; the security loop ships without it. Follow-up.
- **Per-target apply semantics** — what `apply_finding` does for a `--target code` vs `--target plan` security finding is finalized in step 9 when the allowlist opens; the loop is target-agnostic in structure (filters by category, not target).
- **`--iterate` × `--reconcile` composition** — `--reconcile` already mutates the plan inline (step 4); whether `--iterate` loops the reconcile path is left to step 9. The loop here drives the `--target plan|code` audit findings.
- **Shared loop-driver extraction** — consolidating the four `should_continue`/`apply_finding` loop sites into one driver is a cross-command refactor for reconcile.
