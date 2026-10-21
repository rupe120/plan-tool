> **Auto-archived**: this plan was swept on 2026-06-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Wire saved-audit reuse + `--reuse-audit` flags into `completeness-audit`, with an attributed code-drift staleness warning

## Summary

- Add `--reuse-audit` / `--no-reuse-audit` (a `BooleanOptionalAction` whose **unset default is `None` = prompt**) and `--reuse-audit-id STEM` to the `completeness-audit` subparser in `plan_tool/cli/completeness_cmd.py:register`, plus a reuse-decision helper `_resolve_audit_reuse(plan, path, ctx, args)` that calls step 5's `resolve_reusable_audit(...)`, applies the flag/freshness/prompt policy, and returns either the reused audit-rec union (`correctness_recs + conceptual_recs`) to substitute for a fresh `audit_plan_until_stable` sample or `None` ("audit fresh").
- Wire the decision once in `cmd_completeness` (after parse + banner, before the budget branch) and thread the result into **both** consumers: `_run_iterate_convergence_loop` (gain a `reused_audit_recs=` param that, when non-`None`, **skips** the single up-front `audit_plan_until_stable` call and seeds `_audit_recs` from the saved sidecar) and the audit-only fallback (substitute for `_sample_conceptual_audit`).
- **Load-bearing decision:** the deterministic well-formedness battery (`_run_deterministic_checks`) is **never** gated by reuse — only the conceptual axis is reused. Reuse is offered only when `ReusableAudit.fresh` (plan **AND** code fingerprints match); any staleness declines and falls back to a fresh audit, never a non-zero exit (exit-code convention: failure-to-complete only).
- **Code-drift warning:** when the decline is specifically code-side (`code_match is False`, `drifted_code` non-empty), emit a structured warning naming each drifted file with its owning step (`path (step N: title)`) by reusing `_print_attributed_files` (which wraps `render_attributed_path_line`) over `scope_guard.build_file_to_step_map(plan, ctx.repo_root)`, closed by the `detail --reconcile` recovery hint from `drift_detection.reconcile_drift_hint("completeness")`.
- **On green:** a second audit on an unchanged plan+code reuses saved findings (zero conceptual Claude calls) under `--yes`/non-TTY or on an accepted prompt; a plan edit declines with a one-line note; a code edit declines with the attributed per-file warning; `--no-reuse-audit` always re-audits; `--reuse-audit-id` pins a save.

## Table of Contents

- [Why](#why) — what the CLI needs to stop re-running the expensive conceptual audit.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files and the edits per file.
- [Implementation](#implementation) — the flags, the decision helper, the warning, and the two wiring seams.
- [Tests](#tests) — flag parsing, decision-policy matrix, and the attributed warning.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — argparse `BooleanOptionalAction` and the in-repo producers/renderers this step consumes.
- [Deferred](#deferred) — end-to-end `main()` coverage and non-completeness reload paths.

## Why

`plan-tool completeness-audit` is commonly run twice — once to read the report, then again with `--iterate` to apply findings — and both runs re-run `audit_plan_until_stable` (one or more Claude calls, minutes each) from scratch. Steps 1–5 built the substrate: the sidecar now persists both conceptual axes plus `plan_fingerprint` + `code_fingerprint` (steps 1–4), and `resolve_reusable_audit(...)` (step 5) reads the newest sidecar back, recomputes both fingerprints, and returns a `fresh` verdict plus a `drifted_code` path set. Nothing yet **consumes** that verdict at the CLI: `cmd_completeness` always samples fresh and `_run_iterate_convergence_loop` always calls `audit_plan_until_stable`. This step is the thin wiring that turns the verdict into reuse — substituting saved findings when fresh, declining (with a code-drift warning) when stale — gated by operator-facing flags.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` —
    - `register`: add `--reuse-audit`/`--no-reuse-audit` (`BooleanOptionalAction`, `default=None`, `dest="reuse_audit"`) and `--reuse-audit-id` (`default=None`, `dest="reuse_audit_id"`, `metavar="STEM"`) to `p_completeness` (the `completeness-audit` subparser only — `completeness-apply` keeps its own `--id`).
    - add the reuse-decision helper `_resolve_audit_reuse(plan, path, ctx, args)` and the warning emitter `_warn_code_drift(drifted_code, plan, ctx)`.
    - `cmd_completeness`: compute the reuse decision once (after the banner, before the budget branch); thread it into `_run_iterate_convergence_loop` and the audit-only fallback; pass `skip_sidecar_write=True` to the final `_persist_and_present_report` call when reuse was accepted on the audit-only path.
    - `_run_iterate_convergence_loop`: add a `reused_audit_recs=None` keyword param; gate the up-front `audit_plan_until_stable` call on it.
  - `plan_tool/cli/completeness_phases.py` — `_persist_and_present_report`: add a `skip_sidecar_write=False` keyword param that, when `True`, short-circuits the `write_completeness_report` → `save_review` persistence step only, leaving report rendering/presentation unchanged.
  - `tests/cli/test_completeness_cmd.py` — add flag-parsing cases (via `register`) and a `_resolve_audit_reuse` / `_warn_code_drift` policy matrix (patching `plan_tool.completeness_report.resolve_reusable_audit`). Approx. 13 tests.

## Implementation

### `plan_tool/cli/completeness_cmd.py`

**Flags on `p_completeness` (in `register`).** Add after the existing `--audit-dry-rounds` block:
- `--reuse-audit` / `--no-reuse-audit` via `action=argparse.BooleanOptionalAction, default=None, dest="reuse_audit"`. The **`None` default is load-bearing** — it is the third state the decision helper reads as "prompt interactively"; `True` = reuse-when-fresh, `False` = never reuse. Mirrors the `--iterate` precedent already on this subparser (`BooleanOptionalAction`), but with a `None` (not `False`) default so the unset case is distinguishable from explicit `--no-reuse-audit`.
- `--reuse-audit-id` with `default=None, dest="reuse_audit_id", metavar="STEM"`, help naming the `<ts>-completeness` stem form. This is the `review_id` step 5's `resolve_reusable_audit` accepts (bare `<ts>` or full `<ts>-completeness` stem).
- These two flags land **only** on `p_completeness`, not on a shared parent, so `--help` for sibling subcommands is unchanged.

**`_resolve_audit_reuse(plan, path, ctx, args) -> Optional[list]`** — the foundational logic this step adds: *map (flag state, freshness verdict, TTY) → reuse-or-fresh*. Returns the reused audit-rec union to substitute, or `None` to audit fresh. Policy, in order:
1. **Hard opt-out.** When `getattr(args, "reuse_audit", None) is False` (`--no-reuse-audit`), return `None` immediately — do not even look up a sidecar.
2. **Look up the saved audit.** Body-local `from plan_tool.completeness_report import resolve_reusable_audit` (the body-local seam keeps the test monkeypatch on `plan_tool.completeness_report.resolve_reusable_audit` intercepting, matching this module's documented domain-seam convention). Call `resolve_reusable_audit(args.name, ctx.repo_root, plan_path=path, review_id=getattr(args, "reuse_audit_id", None))`. **Before wiring, confirm against step 5's actual landed surface** — `resolve_reusable_audit` does not exist at HEAD (step 5 is a dependency). Read `plan_tool/completeness_report.py` to verify the exported name, the call arity (positional `plan_slug`/`repo_root` + keyword `plan_path`/`review_id`), and the `ReusableAudit` field set (`saved`, `correctness_recs`, `conceptual_recs`, `fresh`, `plan_match`, `code_match`, `drifted_code`) this helper reads, rather than coding against the assumed shape documented here and in References; reconcile any divergence (a renamed field or changed arity) before writing the call.
3. **Miss.** When it returns `None`:
   - If `reuse_audit_id` was explicitly passed, `error(...)` a one-line "no saved completeness audit matched `--reuse-audit-id <stem>`; running a fresh audit" note (user-facing miss per step 5's deferral) and return `None`.
   - Otherwise return `None` silently (no sidecar → fresh audit is the normal first-run path).
4. **Stale.** When `not ru.fresh`:
   - **Code-side** (`not ru.code_match` and `ru.drifted_code`): call `_warn_code_drift(ru.drifted_code, plan, ctx)`.
   - **Plan-side** (`not ru.plan_match`, empty `drifted_code`): `warn(...)` a one-line "saved conceptual audit is stale (plan changed since <ts>); re-running" note.
   - Return `None` (decline → fresh). This is identical under explicit `--reuse-audit` (reuse-when-fresh, warn-then-re-audit when stale) and under the default prompt — a stale audit is never offered for reuse.
5. **Fresh.** When `ru.fresh`, decide by flag:
   - `reuse_audit is True` → reuse. An explicit `--reuse-audit` always wins, even over an explicit `--audit-samples N`.
   - `reuse_audit is None` (prompt): first apply the **explicit-`--audit-samples` override** — when the operator passed `--audit-samples N` explicitly (detected via a sentinel default on the flag, distinguishing an explicit value from the default sample count, which does **not** trigger this), suppress the `--yes`/non-TTY auto-accept and return `None` to force a fresh audit (the operator asked for a fresh sample). This override is subordinate to an explicit `--reuse-audit` (handled above) but takes precedence over auto-accept. Otherwise, force non-interactive — auto-accept — when `getattr(args, "yes", False) or getattr(args, "json", False) or not sys.stdin.isatty()` (any machine-output `--json` mode is forced non-interactive so the prompt never corrupts the stdout report); otherwise prompt `Reuse saved conceptual audit from <ts>? [Y/n] ` (default **Yes** — empty/`y`/`yes` accept; anything else declines). Look up `builtins.input` at call time so tests can monkeypatch it (same pattern as `plan_tool/cli/reconcile.py:_ask_reuse_saved`). `<ts>` is `ru.saved.created_at`.
   - On accept: print a concise `plan-tool: reusing saved conceptual audit (<N> finding(s)) — skipping the conceptual Claude call` line to stderr and return `list(ru.correctness_recs) + list(ru.conceptual_recs)` (**correctness first** to match `cmd_completeness`'s existing `audit_recs` axis split downstream).
   - On decline: return `None`.

**`_warn_code_drift(drifted_code, plan, ctx)`** — the attributed staleness warning:
- Body-local `from plan_tool.scope_guard import build_file_to_step_map`; `file_to_step = build_file_to_step_map(plan, ctx.repo_root)`.
- `warn(...)` a header naming the count, then reuse the already-imported `_print_attributed_files(drifted_code, ctx.repo_root, file_to_step)` (it wraps `render_attributed_path_line`, so each line renders `path (step N: title)` exactly like the live-edit drift warnings).
- Close with the recovery hint: body-local `from plan_tool.drift_detection import reconcile_drift_hint` and `from plan_tool.style import tool`; `tool(reconcile_drift_hint("completeness"), stream=sys.stderr)`. Passing a non-`None` `loop_name` ("completeness", a plan-authoring loop) yields the `detail --reconcile` recovery line.
- No revert, no rc change — informational only.

**`cmd_completeness` wiring.** After the existing banner `print(...)` and before `try: budget = _resolve_iterative_budget(args)`:
- `reused_audit_recs = _resolve_audit_reuse(plan, path, ctx, args)` — compute once so the prompt fires at most once regardless of the iterate/audit-only branch.
- In the `if budget.enabled:` branch, pass it through: `outcome = _run_iterate_convergence_loop(plan, path, ctx, args, budget, reused_audit_recs=reused_audit_recs)`.
- In the audit-only fallback (the existing `if outcome.audit_recs is not None: ... else:` block), insert reuse ahead of the fresh sample:
  ```
  if outcome.audit_recs is not None:
      audit_recs = outcome.audit_recs
  elif reused_audit_recs is not None:
      audit_recs = reused_audit_recs
  else:
      audit_recs = _sample_conceptual_audit(...)
  ```
- Leave the `correctness_recs` / `conceptual_recs` re-split below untouched — it keys on `r.source`, so reused recs (carrying their original `plan-correctness` / `plan-completeness` source) partition identically to freshly-sampled ones.
- **Idempotent reuse (audit-only path).** When reuse was accepted on the no-mutation audit-only run (`reused_audit_recs is not None` and the iterate branch did not run), suppress **only** the end-of-run sidecar JSON write so the existing newest-pointer stays stable and the un-GC'd reports dir does not grow. Thread a `skip_sidecar_write=True` flag into the final `_persist_and_present_report(...)` call (gated on `reused_audit_recs is not None`); inside, it short-circuits the `write_completeness_report` → `save_review` persistence step **only** — `grouped_md` is still rendered and presented unchanged. Report presentation is never suppressed. This idempotent skip applies to the audit-only path alone; the `--iterate` path mutates the plan via correctness-apply and intentionally rewrites a fresh post-apply fingerprinted sidecar (handled in `_run_iterate_convergence_loop`, not here).

**`_run_iterate_convergence_loop` gating.** Add `reused_audit_recs=None` to the signature. Inside the `if budget.enabled:` body, where the up-front `_audit_recs = audit_plan_until_stable(...)` call lives:
- When `reused_audit_recs is not None`, **skip** the `audit_plan_until_stable` call entirely and set `_audit_recs = reused_audit_recs` (print a `plan-tool: reusing saved conceptual audit (skipping the up-front audit call)` line in place of the existing "auditing plan concepts…" line). The downstream `_audit_correctness = [r for r in _audit_recs if r.source == "plan-correctness"]` and the apply loop operate unchanged against the reused `Recommendation` shapes (stable ids make the applied-fingerprint dedupe work identically).
- When `reused_audit_recs is None`, keep the existing behavior verbatim.

**Import topology.** `_resolve_audit_reuse` and `_warn_code_drift` consume `resolve_reusable_audit` / `build_file_to_step_map` / `reconcile_drift_hint` / `tool` via body-local imports; `_print_attributed_files`, `error`, `warn`, `sys` are already imported at module top. No new top-level import is required, preserving the one-directional import edge documented in the module docstring (never imports `app`).

**Foundational-logic scan.** The reuse-decision predicate (flag-state × freshness × TTY) is new and single-sited here; the closest sibling is `plan_tool/cli/reconcile.py:_prompt_reuse_saved` / `_ask_reuse_saved` (the saved-reconcile reuse prompt). That family keys off `step_id` and a different `ReconcileKind` shape and persists nothing fingerprint-based, so it is a **structural sibling, not shared logic** — do not consolidate. The `path (step N: title)` rendering is already single-sourced in `drift_detection.render_attributed_path_line` (via `_print_attributed_files`); this step reuses it rather than re-implementing, so no duplication is introduced.

## Tests

All in `tests/cli/test_completeness_cmd.py`, hermetic, no real Claude (patch `plan_tool.completeness_report.resolve_reusable_audit`; build `ReusableAudit` instances directly via the step-4 dataclass with hand-built `Recommendation`s from the existing `_rec` helper). Use `SimpleNamespace` for `args` (fields: `name`, `reuse_audit`, `reuse_audit_id`, `yes`) and `ctx` (`repo_root`), mirroring this file's existing per-phase test style. Monkeypatch `sys.stdin.isatty` and `builtins.input` for prompt cases.

**Flag parsing** (build subparsers via `register` against a throwaway `argparse.ArgumentParser`):
- `test_reuse_audit_default_is_none` — no flag → `args.reuse_audit is None`.
- `test_no_reuse_audit_sets_false` — `--no-reuse-audit` → `args.reuse_audit is False`.
- `test_reuse_audit_sets_true` — `--reuse-audit` → `args.reuse_audit is True`.
- `test_reuse_audit_id_captures_stem` — `--reuse-audit-id 20260505-120000-completeness` → `args.reuse_audit_id == "20260505-120000-completeness"`.

**Decision policy** (`_resolve_audit_reuse`):
- `test_no_reuse_flag_skips_lookup` — `reuse_audit=False` → returns `None` and `resolve_reusable_audit` is **not** called (assert via a sentinel patch that records calls).
- `test_no_sidecar_returns_none` — patched lookup returns `None`, no id → returns `None`, no output.
- `test_reuse_audit_id_miss_errors_and_audits_fresh` — `reuse_audit_id` set, lookup returns `None` → returns `None` and an error note names the stem.
- `test_fresh_reused_under_yes` — fresh `ReusableAudit`, `args.yes=True` → returns `correctness_recs + conceptual_recs` (correctness first), `input` never called.
- `test_fresh_reused_non_tty` — `reuse_audit=None`, `isatty()` False → auto-accept, returns the union.
- `test_fresh_prompt_accept` — TTY, empty/`y` input → returns the union.
- `test_fresh_prompt_decline` — TTY, `n` input → returns `None`.
- `test_reuse_flag_true_reuses_fresh` — `reuse_audit=True`, fresh → returns the union without prompting.
- `test_stale_by_plan_declines_with_note` — `fresh=False, plan_match=False, code_match=True, drifted_code=[]` → returns `None`; stderr carries the plan-changed note and **no** attributed file list.

**Code-drift warning** (`_warn_code_drift` via the stale-by-code path):
- `test_stale_by_code_emits_attributed_warning` — `code_match=False`, `drifted_code=[<abs path of a step.files file>]` over a plan whose step owns that file → returns `None`; stderr contains `(step N: <title>)` for the drifted file and the `detail --reconcile` recovery hint.

State the green-before-done gate: every test above must pass under `uv run pytest tests/cli/test_completeness_cmd.py -q` before the step is complete. The full end-to-end `main(["completeness-audit", ...])` reuse matrix (zero conceptual calls on fresh reuse, stale re-audit on plan/code edit, the `--iterate` reuse path) is **step 7** in `tests/test_cli.py`, not duplicated here.

### Test-creation order (feature step)

Feature step — author every test above **with** the implementation: add the flags + `_resolve_audit_reuse` + `_warn_code_drift`, then the wiring in `cmd_completeness` / `_run_iterate_convergence_loop`. Each new unit test must be green before the step is considered finished.

## Acceptance criteria

- `completeness-audit --no-reuse-audit <plan>` never reads a sidecar (`resolve_reusable_audit` not called) and always audits fresh.
- With a fresh saved sidecar and `--yes` (or non-TTY stdin), `_resolve_audit_reuse` returns the saved `correctness_recs + conceptual_recs` union (correctness first) and prints no prompt.
- In an interactive TTY with no reuse flag, the operator is prompted `Reuse saved conceptual audit from <ts>? [Y/n]`, defaulting to Yes; `n` declines and returns `None`.
- A plan-side stale verdict (`plan_match is False`, empty `drifted_code`) declines reuse with a one-line note and **no** per-file list.
- A code-side stale verdict (`code_match is False`, non-empty `drifted_code`) declines reuse and prints each drifted file as `path (step N: title)` plus the `detail --reconcile` recovery hint, with rc unaffected (still 0).
- `--reuse-audit-id <stem>` threads `review_id=<stem>` into `resolve_reusable_audit`; an unresolved explicit id prints an error note and falls back to a fresh audit (returns `None`).
- `cmd_completeness` substitutes the reused recs for `_sample_conceptual_audit` (audit-only) and `_run_iterate_convergence_loop` skips `audit_plan_until_stable` when `reused_audit_recs` is non-`None`; the deterministic battery runs in both cases regardless of reuse.
- A reuse-accepted audit-only run passes `skip_sidecar_write=True`, so `write_completeness_report` / `save_review` are not called (no new timestamped sidecar) while the grouped report is still rendered and presented; the existing newest sidecar pointer is unchanged.
- All ~13 new tests in `tests/cli/test_completeness_cmd.py` pass; the existing per-phase and helper tests stay green. No golden regen is expected: `tests/cli/package_surface_help.golden.txt` snapshots only top-level `plan-tool --help`, which lists `completeness-audit <name>` (line 36) without enumerating its subflags, so adding `--reuse-audit`/`--reuse-audit-id` to `p_completeness` does not perturb it.

## References

- [argparse — `BooleanOptionalAction`](https://docs.python.org/3/library/argparse.html#argparse.BooleanOptionalAction) — wiring `--reuse-audit` / `--no-reuse-audit` as one action with a `None` default so unset (prompt) is distinguishable from explicit `--no-reuse-audit`.
- `plan_tool/completeness_report.py` (in-repo) — step 5's `resolve_reusable_audit(plan_slug, repo_root, *, plan_path, review_id=None) -> Optional[ReusableAudit]` and the `ReusableAudit` fields (`saved`, `correctness_recs`, `conceptual_recs`, `fresh`, `plan_match`, `code_match`, `drifted_code`) this step consumes.
- `plan_tool/drift_detection.py` (in-repo) — `render_attributed_path_line` (via `_print_attributed_files`) for the `path (step N: title)` lines and `reconcile_drift_hint("completeness")` for the `detail --reconcile` recovery hint.
- `plan_tool/scope_guard.py` (in-repo) — `build_file_to_step_map(plan, repo_root) -> dict[Path, tuple[int, str]]` supplying the per-step attribution for the drift warning.
- `plan_tool/cli/reconcile.py` (in-repo) — `_ask_reuse_saved` as the prompt pattern to mirror (look up `builtins.input` at call time; accept `y`/`yes`).

## Deferred

- End-to-end `main(["completeness-audit", ...])` reuse coverage (zero conceptual calls on fresh reuse, stale re-audit on plan/code edit, deleted-in-scope flagging, the full flag matrix, the `--iterate` reuse path) — step 7 in `tests/test_cli.py`.
- Updating `docs/AUDIT_RESUME_FLOW.md` / `RUNBOOK.md` for the new flags + code-drift warning — step 8.
- Surfacing code-fingerprint staleness on non-completeness reload paths (`run` / `review` / `jira`) — out of scope per the plan's "Out of scope" (the fingerprint lives in the completeness sidecar; a plan-level manifest is a broader follow-up).
- A shared "diff two code-fingerprint maps" helper — step 5 owns the diff; promotion waits for a second consumer.
