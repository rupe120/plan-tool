# Step 3 — Register the `security` subcommand across all five registration seams

## Summary

Adds `plan_tool/cli/security_cmd.py` — a thin, no-prompt command module modeled on `plan_tool/cli/gates_cmd.py` — exposing `cmd_security(args, *, invoker=None) -> int` and `register(subparsers) -> dict[str, Handler]`. `cmd_security` dispatches on `--target {plan,code}` / `--reconcile`, calls step 1's `run_security_audit(...)`, renders the severity-labeled findings, persists the report via step 2's `write_security_report(...)`, and honors `--fail-on-findings` under the exit-code convention. Registering a new top-level verb touches **five coordinated seams**, not the three the `files:` array names: `plan_tool/cli/app.py` (dual import + `COMMAND_MODULES`), `plan_tool/cli/parser.py` (`CANONICAL_COMMAND_ORDER`), `plan_tool/cli/__init__.py` (docstring catalog + `__all__`), the regenerated `tests/cli/package_surface_help.golden.txt`, and the green `tests/cli/test_package_surface.py` correspondence tests. The load-bearing decision: `cmd_security` reuses step 1's `shell_security_invoker` seam (resolved `invoker=None → shell_security_invoker`), so tests neutralize it without a new TESTING.md row and the `conftest.py` real-backend gate never fires. On green, `plan-tool security --help` exits 0, `plan-tool --help` lists `security`, the golden matches, and a stubbed-invoker `cmd_security` run prints findings and exits 0 even with CRITICAL findings.

## Table of Contents

- [Why](#why) — what's missing today and why the CLI carve lands now
- [Files (creates vs edits)](#files-creates-vs-edits) — two new files plus the five registration-seam edits
- [Implementation](#implementation) — the command module, the handler dispatch, and each registration seam
- [Tests](#tests) — parse-contract, dispatch, exit-code, and golden coverage
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse + headless-mode grounding
- [Deferred](#deferred) — reuse-prompt flag, completeness wiring, reconcile-kind, docs

## Why

- **No top-level `security` verb exists.** Step 1 landed `plan_tool/security_audit.py:run_security_audit` (plan-wide / code security audit returning a `SecurityAuditResult` of `Recommendation` findings) and step 2 landed `write_security_report` / `resolve_reusable_security` persistence — but nothing invokes them. This step is the user-facing entry point: `plan-tool security --target plan|code <name>` and `plan-tool security --reconcile <name>`.
- **The per-step `--mode security` path is unaffected.** `AVAILABLE_MODES` in `plan_tool/cli/app.py` keeps `security`, and `run`/`verify-all --mode security` still drive the per-step `plan_tool/prompts/security.md` audit. This step adds a **plan-wide** verb that composes step 1's orchestrator with the exit-code convention — it does not touch the per-step mode.
- **The carve must hit every registration seam or the verb is half-wired.** A `files:` array scoped to `app.py` + `parser.py` + the new module routinely omits `cli/__init__.py`'s docstring catalog (the curated `--help` description) and `__all__`; missing either leaves `security` absent from `--help` or unreachable through `plan_tool.cli.cmd_security`, surfacing only as a red `test_package_surface.py` correspondence test, never an import error.

## Files (creates vs edits)

**New files:**
- `plan_tool/cli/security_cmd.py` — the command module: `cmd_security(args, *, invoker=None) -> int` handler and `register(subparsers) -> dict[str, Handler]`. Mirrors `plan_tool/cli/gates_cmd.py` (thin, no convergence loop, `invoker=None → shell_security_invoker` default resolved first).
- `tests/cli/test_security_cmd.py` — unit tests driving `cmd_security(ns, invoker=stub)` directly (parse-contract, target dispatch, exit-code convention, persistence call) per the `plan_tool/cli/X.py → tests/cli/test_X.py` convention.

**Existing files (edits only):**
- `plan_tool/cli/app.py` — add **both** `from plan_tool.cli import security_cmd as _security_commands` and `from plan_tool.cli.security_cmd import cmd_security`, then append `_security_commands` to the `COMMAND_MODULES` tuple.
- `plan_tool/cli/parser.py` — **append** `"security"` to `CANONICAL_COMMAND_ORDER` (new verbs append, never insert-by-intent, per the tuple's own comment).
- `plan_tool/cli/__init__.py` — add a `security` entry to the module-docstring catalog (the `--help` description) **and** add `"cmd_security"` to `__all__`.
- `tests/cli/package_surface_help.golden.txt` — regenerate (a new verb perturbs the usage brace metavar, the per-command help block, and the catalog group).

## Implementation

### Foundational logic

The core behavior this step adds is a **single dispatch handler** (`cmd_security`) that maps `--target` / `--reconcile` to a `run_security_audit` call and applies the exit-code convention. There is no parallel call site to consolidate — `run_security_audit` (step 1) is the single security orchestrator and `is_blocking` (`plan_tool/convergence.py`) is the single blocking-severity predicate already used by the `--iterate` loops. The duplication this step *introduces* (a fourth `--fail-on-findings` parent declaration alongside `plan_tool/cli/inspect.py`, `plan_tool/cli/review_cmd.py`, `plan_tool/cli/completeness_cmd.py`) is the intentional argparse-subparser kind: subparsers do not inherit a sibling's flags, so each command re-declares its own `--fail-on-findings` parent until a shared `parents=` parser is minted — route that DRY to Deferred, do not expand this step.

### `plan_tool/cli/security_cmd.py` (new command module)

Mirror `plan_tool/cli/gates_cmd.py` member-for-member — the canonical **thin, no-prompt** command-module template (leaf-only imports, never `plan_tool.cli.app`):

- **Imports (leaf-safe):**
  - `from plan_tool.cli.context import _load_context`
  - `from plan_tool.cli.parser import Handler`
  - `from plan_tool.locator import resolve_plan_for_context`
  - `from plan_tool.security_audit import run_security_audit, shell_security_invoker, SecurityError, SecurityInvoker` (step 1's surface)
  - `from plan_tool.security_audit import write_security_report` (step 2's persistence — see the cross-step note below)
  - `from plan_tool.review_persistence import compute_plan_fingerprint` (the plan-digest producer `write_security_report` needs as `plan_fingerprint`)
  - `from plan_tool.fingerprint import compute_code_fingerprint` (the per-file code-digest producer `write_security_report` needs as `code_fingerprint`)
  - `from plan_tool.parser import parse_plan` (to build the `plan` arg `compute_code_fingerprint(plan, plan_path, repo_root)` requires)
  - `from plan_tool.convergence import is_blocking` (the ≥`medium` blocking predicate)
  - `from plan_tool.style import error, render_markdown_for_console`
  - `from plan_tool.run_log import RunLogWriter` (backend round-trip logging, matching `cmd_suggest_gates`)

- **`cmd_security(args, *, invoker: Optional[SecurityInvoker] = None) -> int`:**
  - **Resolve the seam first:** `inv = invoker if invoker is not None else shell_security_invoker`. This is the only production call site of `shell_security_invoker`; the `invoker=None` default keeps it overridable so `tests/cli/test_security_cmd.py` drives `cmd_security(ns, invoker=stub)` without a cli-global monkeypatch and the `conftest.py` autouse real-backend gate never fires.
  - **Load context + plan path:** `ctx = _load_context(args)`; `path = resolve_plan_for_context(ctx, args.name)` (a registered plan **name**, not an on-disk path — `security` audits an existing plan, so it routes through name resolution, unlike `annotate`/`create --from-existing`).
  - **Pick the target:** `target = "reconcile" if getattr(args, "reconcile", False) else args.target`. `--reconcile` wins over `--target`; document this precedence in the `--reconcile` help. Pass `target=target` into `run_security_audit`. **Note:** step 1's dispatch only accepts `"plan"` / `"code"` — `_SECURITY_TARGETS = ("plan","code")` raises `SecurityError` on `"reconcile"` (its plan⇆code branch is deferred to step 4). Until step 4 lands, `--reconcile` therefore returns rc 2 (failure-to-complete); wire the flag and its help now, but expect it to surface a `SecurityError` until the reconcile target exists.
  - **No reuse short-circuit (the resolver ships dormant):** this handler does **not** call `resolve_reusable_security` — per the plan body's Architecture/Acceptance/Risks/Deferred, the reuse-prompt consumer is deferred to a follow-up for all three targets, so `cmd_security` invokes `run_security_audit` unconditionally and every run re-spends its Claude call(s). Consequently this step does **not** satisfy a `--target code` reuse short-circuit (AC#2 records the resolver as dormant) and does **not** mitigate the HIGH standalone-`security --reconcile` fan-out (the plan accepts it as unmitigated within scope). Step 2 builds `resolve_reusable_security` write-ready; the follow-up adds the consumer here. The `--no-reuse` opt-out and interactive reuse prompt are likewise deferred (see `## Deferred`).
  - **Invoke:** call `run_security_audit(path, repo_root=ctx.repo_root, plan_name=args.name, target=target, step_id=args.step, dry_run=args.dry_run, invoker=inv)` → `SecurityAuditResult`. `run_security_audit` short-circuits `dry_run` **before** the invoker (per step 1), so `--dry-run` prints the rendered prompt and never spawns a backend. **Note:** step 1's `target="code"` path audits a single step's detail/files via `prompts/security.md` and **requires** `step_id`; pass `--step` for `--target code`. Omitting `--step` with `--target code` surfaces a `SecurityError` (rc 2). Step 1's contract assigns the plan-wide multi-step code sweep to **this** step (step 1's `## Deferred`: "the all-steps code sweep is wired with the CLI in step 3"); this step does **not** implement it — an explicit, agreed scope cut deferred to a follow-up (see `## Deferred`) — so `--step` stays required for `--target code` until that sweep lands.
  - **Dry-run:** print the result's rendered prompt as-is and `return 0` (mirror `cmd_review`'s dry-run pass-through — no console markdown reflow, no save).
  - **Render:** print `render_markdown_for_console(result.report)` so finding paths stay clickable (the `cmd_review` pattern).
  - **Persist:** unless `args.dry_run` or `args.no_save`, compute step 2's required inputs and call `write_security_report(...)` (step 2) to drop the `<ts>-security-<target>.json` sidecar. Step 2's signature is `write_security_report(plan_path, report_md, *, repo_root, recommendations, plan_rel_path, target="plan", plan_fingerprint="", code_fingerprint=None, step_id=None)` — the CLI owns supplying `recommendations`, `plan_rel_path`, `target`, and both fingerprints (the writer is naming-/fingerprint-agnostic):
    - `plan_rel_path = str(path.relative_to(ctx.repo_root))` — the repo-relative plan path.
    - `plan_fp = compute_plan_fingerprint(path)` — the plan digest.
    - `code_fp = compute_code_fingerprint(parse_plan(path), path, ctx.repo_root)` — the per-file code digest map (`parse_plan` builds the `Plan` the fingerprint walks).
    - Then: `write_security_report(path, result.report, repo_root=ctx.repo_root, recommendations=result.findings, plan_rel_path=plan_rel_path, target=target, plan_fingerprint=plan_fp, code_fingerprint=code_fp, step_id=args.step)`. `recommendations` is `result.findings` (the `SecurityAuditResult`'s `Recommendation` list); `target` is the audited `--target` (`"plan"`/`"code"`) so the sidecar lands in the target-scoped bucket; `step_id` mirrors the audit (set for `--target code`, `None` for plan-target). The `--reconcile` target **does** reach this branch — step 4 runs its hook with persistence suppressed (`persist=False`), writes no `-security-reconcile.json`, and leaves `result.persisted_path is None`, so the `if result.persisted_path is not None` guard falls through and `write_security_report(..., target="reconcile")` is the sole on-disk writer of the consolidated `-security-reconcile.json` sidecar.
    - Wrap the `run_security_audit` + persist body in a `RunLogWriter.start(...) / run_logger.run_end(...)` try/finally like `cmd_suggest_gates`, `command="security"`, `flags={"target": target, "fail_on_findings": getattr(args, "fail_on_findings", False)}`.
  - **Exit-code convention:** default `return 0` — a completed audit exits 0 **even with CRITICAL findings**. Only when `getattr(args, "fail_on_findings", False)` and `any(is_blocking(r.severity) for r in result.findings)` → `return 1`. A `SecurityError` (or a `run_security_audit` failure-to-complete) maps to `error(str(exc)); return 2` — non-zero signals the audit couldn't run, never findings.

- **Cross-step coupling note (load-bearing):** `write_security_report` and (optionally) `resolve_reusable_security` are **step 2's** deliverables, but this handler is their only caller — the step 2 detail states "the CLI (step 3) owns calling these two functions." The plan frontmatter declares `step 3 depends_on: [1, 2]`, so step 2 lands **before** this step. If step 2 has not landed when this is implemented, scope persistence to a one-line follow-up and keep the render + exit-code path (the title's three flags) intact.

- **`register(subparsers) -> dict[str, Handler]`:**
  - Build a **local** `fail_on_findings_parent` (`add_help=False`, `--fail-on-findings` `store_true` `dest="fail_on_findings"`) — copy the wording from `plan_tool/cli/review_cmd.py`'s `fail_on_findings_parent`, narrowed to security ("exit non-zero when a blocking (medium+) security finding is present"). A local `-y/--yes` parent only if the handler grows a confirm; the title's scope has no prompt, so `yes_parent` is optional — omit it unless the reuse-prompt (Deferred) is wired.
  - `p = subparsers.add_parser("security", help="audit the plan or the code for security concerns (plan-wide); --reconcile reports plan⇆code drift", parents=[fail_on_findings_parent])`.
  - `p.add_argument("name", help="plan name — slug, filename stem (e.g. 2-security-check-command), or filename.md")`.
  - `p.add_argument("--target", choices=("plan", "code"), default="plan", help="audit the plan's design/decomposition (plan) or the changed code (code); default plan")`.
  - `p.add_argument("--step", type=int, default=None, help="step id to audit; required with --target code (step 1's code path audits that step's detail/files via prompts/security.md); the plan-wide code sweep is deferred")`.
  - `p.add_argument("--reconcile", action="store_true", help="report drift between the plan's stated security intent and the code's actual posture; overrides --target")`.
  - `p.add_argument("--dry-run", action="store_true", help="render the claude prompt and print it; do not invoke")`.
  - `p.add_argument("--no-save", action="store_true", dest="no_save", help="skip persisting the <ts>-security-<target>.json report under plan-details/<slug>/reports/")`.
  - `return {"security": cmd_security}`.

### `plan_tool/cli/app.py` (dual import + registry)

- **Add both import forms** next to the `gates_cmd` block (`plan_tool/cli/app.py`'s `from plan_tool.cli import gates_cmd as _gates_commands` / `from plan_tool.cli.gates_cmd import cmd_suggest_gates`):
  - `from plan_tool.cli import security_cmd as _security_commands` — the **module-import form** (not dotted attribute access on a still-initializing `plan_tool.cli`), required during package init.
  - `from plan_tool.cli.security_cmd import cmd_security` — re-imports the handler into `app`'s namespace so `cli/__init__.py`'s `dir(app)` mirror loop surfaces it as `plan_tool.cli.cmd_security` (what `test_every_subcommand_has_a_dispatch_handler` resolves via `_handler_name_for("security") → "cmd_security"`).
- **Append `_security_commands`** to the `COMMAND_MODULES` tuple (order no longer help-order-bearing — `CANONICAL_COMMAND_ORDER` fixes display order after registration).

### `plan_tool/cli/parser.py` (canonical order)

- **Append `"security"`** to the end of `CANONICAL_COMMAND_ORDER` (after `"bench"`). The tuple's own comment mandates new commands append; this gives `security` a canonical index that sorts it before the deprecated-alias cluster in both the usage brace metavar and the per-command help lines that `_reorder_subcommands` rebuilds.

### `plan_tool/cli/__init__.py` (catalog + `__all__`)

- **Add a `security` line to the module-docstring catalog** — this docstring **is** the `--help` description (threaded via `build_parser` → `assemble(cli.__doc__, ...)`), so the entry lands in the regenerated golden. Place it under the **Audit** group (it reviews the plan/code and, with `--reconcile`, mutates), e.g. a `Security —` sub-row:
  ```
  Security — audit the plan or code for security concerns (plan-wide).
    plan-tool security <name> --target plan|code   Severity-labeled security findings over the plan's design or the changed code; exits 0 even with CRITICAL (--fail-on-findings flips the rc).
    plan-tool security <name> --reconcile          Report drift between the plan's stated security intent and the code's actual posture.
  ```
  Keep the `integrations/claude/SKILL.md` "Subcommands at a glance" section in sync — but that file is **step 8's** docs footprint, not this step's; note the forward dependency, do not edit it here.
- **Add `"cmd_security"` to `__all__`** so `from plan_tool.cli import cmd_security` resolves and the correspondence test passes.

### `tests/cli/package_surface_help.golden.txt` (regenerate)

- **Regenerate via `UPDATE_CLI_GOLDEN=1`** (the seeding path in `tests/cli/test_package_surface.py:test_help_matches_golden` writes the snapshot when `UPDATE_CLI_GOLDEN` is set). A new verb changes the golden in three places: the two usage brace metavar lists (`{...,bench,security,root,...}`), a new `security  …` per-command help block, and the new `Security —` catalog group in the rendered docstring. Run `UPDATE_CLI_GOLDEN=1 uv run pytest tests/cli/test_package_surface.py::...::test_help_matches_golden` then re-run without the env var to confirm a byte match.

## Tests

This is a **feature** step — enumerate the unit tests **with** the implementation; every new test must be green before the step is done.

`tests/cli/test_security_cmd.py` (drive `cmd_security(ns, invoker=stub)` directly; build `ns` with `argparse.Namespace` / `SimpleNamespace`, seed a plan + in-scope code file under `tmp_path` like the sibling cli unit tests):

- `test_security_help_exits_zero` — `main(["security", "--help"])` (or `register` → parse `--help`) raises `SystemExit(0)`; satisfies the step's gate `plan-tool security --help`.
- `test_target_default_is_plan` — parsing `security <name>` leaves `args.target == "plan"` and `args.reconcile is False`.
- `test_target_code_parses` — `security <name> --target code` sets `args.target == "code"`.
- `test_reconcile_overrides_target` — with `--reconcile`, the handler passes `target="reconcile"` to a recording `run_security_audit` stub regardless of `--target`.
- `test_invoker_seam_neutralized` — `cmd_security(ns, invoker=stub)` never calls `shell_security_invoker`; the `conftest.py` real-backend gate stays silent (assert the stub was the invoker `run_security_audit` received).
- `test_exit_zero_with_critical_findings` — a stubbed audit returning a CRITICAL `Recommendation` and `fail_on_findings=False` → `cmd_security` returns `0`.
- `test_fail_on_findings_flips_rc` — same CRITICAL finding with `fail_on_findings=True` → returns `1`; a NIT/INFO-only result with `fail_on_findings=True` → returns `0` (`is_blocking` is ≥`medium`).
- `test_dry_run_skips_invoker_and_save` — `dry_run=True` prints the prompt, returns 0, and calls neither the invoker nor `write_security_report` (patch/observe the persistence call).
- `test_persists_report_unless_no_save` — a normal run calls `write_security_report` once; `--no-save` calls it zero times (snapshot the call delta around the operation, not an absolute count).
- `test_security_error_returns_two` — a `run_security_audit` raising `SecurityError` → `error(...)` printed, returns `2` (failure-to-complete, distinct from findings).

`tests/cli/test_package_surface.py` (existing correspondence tests — assert they stay green, no new test needed beyond the regen):

- `test_register_returns_dispatch_for_every_subcommand` / `test_assemble_dispatch_values_are_callable` — `security` is in `dispatch` with a callable handler.
- `test_every_subcommand_has_a_dispatch_handler` — `plan_tool.cli.cmd_security` resolves (the `__all__` + dual-import seams).
- `test_help_matches_golden` — passes against the regenerated golden.

## Acceptance criteria

- `plan-tool security --help` exits 0 (the step's `gate`).
- `plan-tool --help` lists `security` in the usage brace metavar and shows a `security …` help line and the `Security —` catalog group.
- `tests/cli/package_surface_help.golden.txt` matches the rendered `--help` byte-for-byte.
- `cmd_security(ns, invoker=stub)` with a CRITICAL-finding stub returns `0`; with `fail_on_findings=True` returns `1`; with `dry_run=True` returns `0` and spawns no backend.
- `plan_tool.cli.cmd_security` is importable and in `plan_tool.cli.__all__`; `"security"` is the last entry of `CANONICAL_COMMAND_ORDER`; `_security_commands` is in `COMMAND_MODULES`.
- `tests/cli/test_package_surface.py` correspondence tests pass; no test spawns the real `claude` binary (the `conftest.py` autouse gate stays silent).

## References

- [argparse — add_subparsers / add_parser (Python docs)https: — the `subparsers.add_parser(...)` + `parents=[...]` API for declaring the `security` subparser, `--target` `choices`, and the shared `--fail-on-findings` parent.
- [argparse — BooleanOptionalAction / store_truehttps: — flag-action semantics for `--reconcile` / `--dry-run` / `--no-save`.
- [Claude Code Headless Mode (Anthropic docs)https: — `-p/--print` and exit-code behavior the `shell_security_invoker` seam relies on (127 = backend-not-on-PATH), grounding the exit-code mapping in `cmd_security`.

## Deferred

- **Reuse-prompt wiring (the `resolve_reusable_security` consumer) + `--no-reuse` flag + interactive reuse prompt** — the fingerprint-gated reuse short-circuit is **deferred to a follow-up for all three targets** (the resolver ships dormant; see the plan body's `## Deferred`); this handler does not read it. Also deferred: the opt-out `--no-reuse` flag and the interactive "reuse the saved report?" confirm (the `cmd_review` `_prompt_reuse_saved_review` analog, needing a `-y/--yes` parent).
- **Next-step security pointer** — emitting the relevance-gated `plan-tool security` suggestion at the end of `detail` / `completeness` is step 5; this step adds no `detail`/`completeness` coupling. (Security is **not** a dimension inside `completeness`.)
- **`security-reconcile` ReconcileKind + drift hook** — the `ReconcileKind` descriptor and `run_auto_reconcile_on_drift` hook for plan⇆code security drift are step 4; `cmd_security --reconcile` here calls `run_security_audit(target="reconcile")` directly, not the reconcile-family `_RECONCILE_KINDS` machinery.
- **Shared `--fail-on-findings` parent consolidation** — this is the fourth independent declaration (after `inspect.py` / `review_cmd.py` / `completeness_cmd.py`); a single shared `parents=` parser is a refactor `detail` cannot mint — route to reconcile.
- **Plan-wide multi-step code sweep** — step 1 assigns the all-steps code sweep to this step ("wired with the CLI in step 3"), but it is cut here to a follow-up: `--target code` requires `--step` (single-step audit) and the sweep that audits every in-scope step in one run is left unimplemented. An explicit, agreed scope cut, not step 1's deferral.
- **TESTING.md seam row / SKILL.md catalog** — `cmd_security` routes through step 1's `shell_security_invoker` seam (already in TESTING.md's table from step 1), so no new row is required; the `integrations/claude/SKILL.md` "Subcommands at a glance" sync is step 8's docs footprint.
