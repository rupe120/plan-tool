> **Auto-archived**: this plan was swept on 2026-06-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Surface refresh as `reconcile-plan --refresh` (skip Claude on no-drift) and clarify the `--reprocess` help text

## Summary

- **Add a `--refresh` flag to the `reconcile-plan` subparser** in `plan_tool/cli/review_cmd.py` and branch `cmd_review` on it: when set, the handler calls the step-3 entry point `plan_tool/refresh.py:refresh_plan(path, ctx.repo_root)` and returns its rendered outcome **before** the reuse prompt or the `review_plan_full` Claude call ever runs.
- **The flag rides the existing `reconcile-plan` subparser only** (single-subcommand reach), so `reconcile` / `review` aliases inherit it for free and the base parser is untouched. The plan's gate (`reconcile-plan --help | grep -- --refresh`) passes off this one `add_argument`.
- **Load-bearing decision:** `cmd_review` reads `refresh_plan` as a **module global** (top-level `from plan_tool.refresh import …`) so the test suite patches `plan_tool.cli.review_cmd.refresh_plan` to drive the branch network-free — and the no-Claude guarantee is structural because `refresh_plan` itself gates on `check_grounding_drift` before importing the reconcile seam (step 3).
- **Clarify the `--reprocess` help text** in `plan_tool/cli/authoring.py` so the four crowded verbs read distinctly — `reprocess` fills `_(TODO)_` placeholders from an archived predecessor (no code involvement), pointing code-staleness users at `reconcile-plan --refresh` instead. Copy-only; no behavior change.
- **On green:** `reconcile-plan demo --refresh` on a grounded, unchanged tree prints "still grounded" and exits 0 with no invoker spawned; on drift it reports the scoped reconcile's finding count and points at `reconcile-plan-walk`; the audit path (no `--refresh`) is byte-unchanged.

## Table of Contents

- [Why](#why) — the surface gap between the step-3 entry point and the operator CLI
- [Files (creates vs edits)](#files-creates-vs-edits) — the subparser flag, the `cmd_review` branch, the help-text edit
- [Implementation](#implementation) — flag registration, the early-return branch, outcome rendering, the `--reprocess` clarification
- [Tests](#tests) — parse contract, the refresh branch (no-drift / drift / needs-grounding), no-Claude assertion, help-text guard
- [Acceptance criteria](#acceptance-criteria) — observable post-change behaviors
- [References](#references) — argparse / pytest-monkeypatch for this step's surfaces
- [Deferred](#deferred) — branch-hook caller, `--force`, audit-flag mutual-exclusion, reprocess test-file divergence

## Why

- **Step 3 shipped `refresh_plan` as a reusable importable entry point with no CLI surface** — the plan's *Architecture* point 3/4 split the engine (step 3) from the operator wrapper (this step). Today an operator can run `reconcile-plan` (always spends Claude) but has no way to ask "is this plan still grounded, and re-ground it only if it drifted, cheaply." This step is the thin argparse shim over the existing entry point.
- **The reconcile/refresh family is crowded and one member is mis-named.** Per the plan's *Naming — rationalize the family*, `create --reprocess` reads like a code-refresh but means "fill `_(TODO)_` placeholders from an archived predecessor." Adding `--refresh` without clarifying `--reprocess` in the same pass leaves four near-neighbors (`reconcile-plan`, `reconcile-plan-walk`, `--refresh`, `--reprocess`) indistinguishable from `--help`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/review_cmd.py`
    - Add a top-level import `from plan_tool.refresh import RefreshOutcome, refresh_plan` (a module global, mirroring how `review_plan_full` is imported and read).
    - In `register`, add `p_review.add_argument("--refresh", …)` to the `reconcile-plan` subparser (`p_review`).
    - In `cmd_review`, add an early `if getattr(args, "refresh", False):` branch — after `path = resolve_plan_for_context(...)`, before `_prompt_reuse_saved_review` — that calls `refresh_plan`, renders the `RefreshOutcome`, and returns.
  - `plan_tool/cli/authoring.py`
    - Edit the `--reprocess` `help=` string on `p_create_source.add_argument("--reprocess", …)` to distinguish it from `reconcile-plan --refresh`. Help-string copy only; no flag, dispatch, or `_cmd_create_reprocess` change.
  - `tests/cli/test_review_cmds.py`
    - Add a `--refresh` parse-contract class and a `cmd_review`-branch class (patching the module-global `refresh_plan`).

## Implementation

### `plan_tool/cli/review_cmd.py`

**Module-level import (the patchable seam).**
- **Add `from plan_tool.refresh import RefreshOutcome, refresh_plan` to the top-of-module imports**, beside `from plan_tool.review import (ReviewError, review_plan_full)`. `cmd_review` must call `refresh_plan` as a **bare module global** — the module's docstring already states each handler reads its Claude-driving collaborator (`review_plan_full` / `run_all_done_steps` / …) as its own module global so a monkeypatch targets `plan_tool.cli.review_cmd.<name>`. The refresh seam follows that exact convention so `tests/cli/test_review_cmds.py` patches `plan_tool.cli.review_cmd.refresh_plan`.
- **No cycle risk:** `plan_tool/refresh.py` (step 3) imports nothing from `plan_tool/cli/*`, and it imports the reconcile seam (`run_auto_reconcile_on_drift`) **body-locally inside its drift branch** — so a top-level import here does not pull the reconcile engine onto the no-drift path, and the no-Claude guarantee stays structural.

**Flag registration (`register`).**
- **Add to `p_review` only** (the `reconcile-plan` subparser, aliases `reconcile` / `review`), not to a shared parent — the flag reaches exactly one subcommand, matching the single-subcommand-reach rule (contrast `verify-all`'s `fail_on_findings_parent`, which is shared because two subparsers need it).
- **Shape:** `p_review.add_argument("--refresh", action="store_true", dest="refresh", help=(…))`. Help text states: gate the plan's grounding fingerprint against the current code; on no drift exit fast with **no Claude call**; on drift run a reconcile scoped to exactly the changed files, save findings for `reconcile-plan-walk`, and re-stamp the grounding sidecar; contrast with a plain audit (always spends Claude) and with `create --reprocess` (placeholder fill, no code).
- **Placement:** add the argument near `--dry-run` / `--reuse` on `p_review`; default is `False` (argparse `store_true`), so existing `reconcile-plan` invocations are byte-unchanged.

**The early-return branch (`cmd_review`).**
- **Branch right after `path = resolve_plan_for_context(ctx, args.name)` and before `_prompt_reuse_saved_review(...)`** — so the refresh path skips the reuse prompt, the `review_plan_full` Claude call, the `save_review` persistence, and the interactive walk entirely. Use `getattr(args, "refresh", False)` (defensive against partial-namespace `argparse.Namespace` test args, mirroring the existing `getattr` reads elsewhere in the CLI).
- **Call shape:** `outcome = refresh_plan(path, ctx.repo_root)` — defaults `run_logger=None, file=None` (`cmd_review` has no `RunLogWriter` in scope, unlike `run`). Let any `ParseError` / `ValidationError` from `refresh_plan`'s internal `parse_plan` propagate the same way the audit path's `parse_plan` already can; the surrounding dispatch in `plan_tool/cli/app.py` renders parse errors.
- **Render the `RefreshOutcome` and return 0** (a completed refresh is a completed command — exit-code convention: non-zero only on failure-to-complete, never on findings). Three render arms keyed off the dataclass fields:
  - **No drift (`outcome.drifted is False`):** print `✓ '<slug>' is still grounded against the current code — nothing to refresh (no Claude call).` Use `outcome.plan_slug`.
  - **Needs grounding (`outcome.needs_grounding is True`):** print that no grounding baseline existed, a whole-surface reconcile ran over `len(outcome.drifted_files)` declared file(s), `outcome.findings` finding(s) were surfaced, and a baseline sidecar was stamped at `outcome.grounding_path`.
  - **Drift (`outcome.drifted is True`, `needs_grounding is False`):** print that the plan drifted across `len(outcome.drifted_files)` file(s), a scoped reconcile surfaced `outcome.findings` finding(s), and the grounding sidecar was re-stamped at `outcome.grounding_path`.
- **Point drift/needs-grounding arms at the walk** via `plan_tool/cli/console.py:_print_next_steps("Apply refresh findings:", [("plan-tool reconcile-plan-walk " + args.name, "step through the saved reconcile findings")])` — the established next-command emitter (writes to stderr, keeps stdout clean). Skip the pointer when `outcome.findings == 0`. `_print_next_steps` is a cycle-free leaf already importable here.

**What does *not* change in `cmd_review`.**
- The reuse-prompt block, `review_plan_full` call, `save_review` persistence, and `_review_walk_environment_allows` walk are reached only on the non-`--refresh` path — they stay byte-identical so the existing `review` reuse/save/walk characterization tests in `tests/test_review.py` pass unmodified.

### `plan_tool/cli/authoring.py`

- **Edit only the `help=` string** on `p_create_source.add_argument("--reprocess", …)`. Keep the existing substance ("fill `_(TODO)_` placeholders … from its archived predecessor under `<plan-dir>/archive/`. Deterministic merge — no claude call, no manifest mutation … Mutually exclusive with --from / --from-existing.") and **append a disambiguator**: reprocess is about *placeholder text*, not code; for re-grounding a plan against changed code use `reconcile-plan --refresh`.
- **Do not touch** `_cmd_create_reprocess`, the `getattr(args, "reprocess", False)` dispatch in `cmd_create`, or `plan_tool/reprocess.py:reprocess_plan` — this is a help-copy edit, behavior-preserving.

### Shared-logic scan

- **Foundational logic:** a CLI dispatch branch that routes `reconcile-plan --refresh` to the step-3 `refresh_plan` entry point. The drift gate, scoped reconcile, and re-stamp all live in `plan_tool/refresh.py` (step 3) — this step mints **no** judgement, only the argparse flag + the branch + outcome rendering.
- **No duplicated branch elsewhere.** The only other caller the plan names for `refresh_plan` is the branch-awareness branch-creation hook, which is a separate plan/step — see [Deferred](#deferred). Grep for `refresh_plan(` across `plan_tool/` returns only `plan_tool/refresh.py`'s definition until this step adds the one CLI call site, so there is no parallel CLI shim to consolidate.
- **Outcome rendering reuses `_print_next_steps`** (the single "advertise the next command" emitter in `plan_tool/cli/console.py`) rather than minting a new pointer printer — same convention `cmd_detail` and `_render_grouped_report` use.

## Tests

All new cases live in `tests/cli/test_review_cmds.py` (the step's declared test module). Follow the file's existing pattern: parser-contract cases drive `build_parser()`; branch cases drive `cmd_review` directly with an `argparse.Namespace`, patching the module-global `refresh_plan` so **no real Claude or reconcile seam runs** (TESTING.md's seam discipline). Build the tmp plan with the file's existing `_write_review_plan` / `_review_ctx` / `_review_args` helpers (extend `_review_args`'s base dict with `refresh=False`).

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add every test below **with** the implementation; all must be green (`uv run pytest -m "not integration" tests/cli/test_review_cmds.py -q`) before the step is done.

- `test_reconcile_plan_refresh_default_is_false` — `build_parser().parse_args(["reconcile-plan", "demo"]).refresh is False` — the flag defaults off, audit path unchanged.
- `test_reconcile_plan_refresh_flag_parses` — `parse_args(["reconcile-plan", "demo", "--refresh"]).refresh is True` — the flag exists on the subparser (covers the plan's `--help | grep -- --refresh` gate).
- `test_reconcile_alias_inherits_refresh` — `parse_args(["reconcile", "demo", "--refresh"]).refresh is True` — the `reconcile` / `review` aliases share `p_review`, so the flag rides along.
- `test_refresh_no_drift_skips_claude_and_reuse` — patch `plan_tool.cli.review_cmd.refresh_plan` to return `RefreshOutcome(drifted=False, …)` and patch `plan_tool.cli.review_cmd.review_plan_full` + `_prompt_reuse_saved_review` to raise; `cmd_review(_review_args(refresh=True, name="fingerprint"))` returns 0 and prints "still grounded", proving the audit/reuse path is never entered.
- `test_refresh_no_drift_prints_grounded_message` — same no-drift outcome; stdout contains the plan slug and "still grounded"; no `reconcile-plan-walk` pointer is emitted (findings == 0).
- `test_refresh_drift_reports_findings_and_walk_pointer` — `refresh_plan` returns `RefreshOutcome(drifted=True, needs_grounding=False, findings=2, drifted_files=[…], grounding_path=…)`; output reports 2 finding(s) and the stderr pointer names `plan-tool reconcile-plan-walk fingerprint`; rc == 0.
- `test_refresh_needs_grounding_reports_baseline` — `refresh_plan` returns `RefreshOutcome(needs_grounding=True, drifted=True, …)`; output states no baseline existed and a baseline was stamped; rc == 0.
- `test_refresh_calls_entry_point_with_repo_root` — assert the patched `refresh_plan` spy was called once with `(plan_path, ctx.repo_root)` (positional), proving the shim forwards the resolved path + repo root and nothing else.
- `test_reprocess_help_mentions_refresh` — `build_parser()`'s `create --reprocess` help string contains "reconcile-plan --refresh" (regression guard that the disambiguation copy stays). Reach the help text via the parser action's `help` attribute (no subprocess). *(If the authoring help string is better asserted in `tests/cli/test_authoring_cmds.py`, see [Deferred](#deferred).)*

**Green-before-done gate:** every test above must pass, and the existing `TestReconcilePlanReuseFlags` / `TestPromptReuseSavedReviewFlags` / `TestVerifyAllAuditOnlyGate` classes must stay green unmodified (the audit path is untouched).

## Acceptance criteria

- `plan_tool reconcile-plan --help` lists `--refresh` (the plan's frontmatter gate `reconcile-plan --help 2>&1 | grep -q -- --refresh` passes).
- `build_parser().parse_args(["reconcile-plan", "demo"]).refresh` is `False`; with `--refresh` it is `True`; the `reconcile` / `review` aliases accept `--refresh` too.
- `cmd_review` with `args.refresh` true calls `plan_tool.refresh.refresh_plan(path, repo_root)` and returns 0 **without** calling `review_plan_full`, `_prompt_reuse_saved_review`, or `save_review`.
- A no-drift `RefreshOutcome` renders a "still grounded" line and emits no walk pointer; a drift / needs-grounding outcome renders the finding count and a `reconcile-plan-walk <name>` pointer.
- `create --reprocess` help text names `reconcile-plan --refresh` as the code-staleness alternative; `_cmd_create_reprocess` and `reprocess_plan` are byte-unchanged.
- `uv run pytest -m "not integration" tests/cli/test_review_cmds.py -q` is green; the existing `review` / `reconcile-plan` suites pass unmodified.

## References

- [argparse — add_parser / store_true / option flags](https://docs.python.org/3/library/argparse.html) — the `--refresh` `store_true` registration on the `reconcile-plan` subparser and reading the `--reprocess` action's `help` attribute in a test.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — `monkeypatch.setattr(plan_tool.cli.review_cmd, "refresh_plan", spy)` and the raising stub on `review_plan_full` proving the audit path is never reached on `--refresh`.

## Deferred

- **The branch-awareness branch-creation hook caller** — the other `refresh_plan` consumer the plan names; it lives in the branch-awareness plan, not here. This step adds only the `reconcile-plan` CLI surface.
- **A `--force` / re-ground-regardless knob** — bypassing the drift gate to reconcile the whole surface unconditionally is a step-3 deferral; add when a caller needs it.
- **Parse-time mutual exclusion of `--refresh` with `--step` / `--dry-run` / `--reuse`** — the early-return branch simply ignores the audit-only flags (it never reads them). A `mutually_exclusive_group` is a usability nicety, not a correctness need; deferred to keep the footprint to one `add_argument`.
- **Migrating the reprocess help-text regression test to `tests/cli/test_authoring_cmds.py`** — the `--reprocess` flag is an authoring-subparser action, so by the `X.py → test_X.py` convention its help-string guard belongs in the authoring test module; `test_reprocess_help_mentions_refresh` is placed in the declared `tests/cli/test_review_cmds.py` for footprint locality. Reconcile may relocate it.
