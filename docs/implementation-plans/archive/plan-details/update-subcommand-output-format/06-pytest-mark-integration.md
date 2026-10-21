> **Auto-archived**: this plan was swept on 2026-06-01 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add `@pytest.mark.integration TestSubcommandStyleOutput` end-to-end style assertions to `tests/test_cli.py`

## Summary

- Add one `@pytest.mark.integration class TestSubcommandStyleOutput` to `tests/test_cli.py` that drives `plan_tool.cli.main([...])` end-to-end and asserts the unified diagnostic contract steps 1–5 establish: plain-mode bytes identical to the legacy `plan-tool:` / `warning:` / `error:` prefixes, prefix-only ANSI under `PLAN_TOOL_FORCE_COLOR`, and diagnostics on **stderr** vs results on **stdout** (captured per stream via `capsys`).
- **Test-only step.** It edits `tests/test_cli.py` exclusively — no `plan_tool/` source changes. Its assertions are only true once steps 1–5 (`depends_on: 1, 2, 3, 4, 5`) have routed every hand-rolled prefix print through `plan_tool/style.py`.
- **Load-bearing decision:** capture is `capsys.readouterr()` per stream, because the migrated library diagnostics hardcode `sys.stderr` (no injectable `file=`/`stream=` seam survives `main()`); `io.StringIO` injection is not reachable end-to-end.
- **Observable result on green:** `uv run pytest -m integration tests/test_cli.py -q` includes `TestSubcommandStyleOutput`, all cases pass, and a regression that drops a trailing space / re-cases a prefix / leaks color into a body fails one of them.

## Table of Contents

- [Why](#why) — what end-to-end gap steps 1–5's unit tests leave open
- [Files (creates vs edits)](#files-creates-vs-edits) — the single test file touched
- [Implementation](#implementation) — the new class, its capture seam, the env gate, the subcommand matrix
- [Tests](#tests) — cases in `TestSubcommandStyleOutput`
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — stream/TTY/color/capsys docs consulted
- [Deferred](#deferred) — coverage intentionally left to the steps 1–5 unit suites

## Why

- **Steps 1–5 pin each diagnostic at the library/unit layer; nothing yet asserts the wiring end-to-end.** The unit `*StyleOutput` classes call `tool()`/`warn()` (or the producing function) directly with an injected `StringIO`. They cannot catch a regression where `main()` routes a diagnostic to the wrong stream, where the color gate misreads the real destination stream, or where a subcommand swallows/duplicates a line on the way through `cmd_*`. Step 6 is the only `@pytest.mark.integration` coverage that drives the real `argparse` dispatch + handler + library path.
- **The plan names this as the sole new integration surface** (`## Testing`): "for each migrated subcommand, `main([...])` output captured via `capsys` is byte-identical to the legacy prefix with color off, and colorizes the prefix (body unchanged) when `PLAN_TOOL_FORCE_COLOR` is set; diagnostics land on stderr and results on stdout." It sits at `depends_on: 1–5` because the unified assertion is only meaningful once every subcommand is on the helpers.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `tests/test_cli.py` — add `from plan_tool import style` to the import block (alongside the existing `from plan_tool.cli import build_parser, main`); add one `@pytest.mark.integration class TestSubcommandStyleOutput`. Reuse the in-file helpers `_iter_basic_plan`, `_iter_setup_manifest`, `_iter_force_tty` for the `run` cases. No production edits.

## Implementation

### `tests/test_cli.py` — `TestSubcommandStyleOutput`

- **Capture seam is `capsys` per stream — not `StringIO`.** Every migrated library diagnostic (review/detail/auto_reconcile/change_collision/iteration_lock/lessons/shell) defaults its stream to `sys.stderr` with no kwarg threaded through `main()`, and the `cli.py` handlers call `warn()`/`error()` (which also default to `sys.stderr`). Read `captured = capsys.readouterr()` and assert against `captured.err` (diagnostics) and `captured.out` (results) separately. This mirrors the seam-asymmetry already captured for `detail.py`/`jira.py`: there is no injectable `file=` seam at the `main()` boundary.

- **Color gate is honored automatically under `capsys`.** `plan_tool/style.py:color_enabled` calls `stream.isatty()`; the `capsys`-replaced stdout/stderr report non-TTY, so the default path is plain mode with no extra mocking. Force the two modes via env only:
  - **Plain case:** `monkeypatch.delenv("PLAN_TOOL_FORCE_COLOR", raising=False)` and `monkeypatch.delenv("NO_COLOR", raising=False)` so an inherited dev env can't flip the gate. Output must be byte-identical to the legacy bare-prefix line.
  - **Color case:** `monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")` (which `color_enabled` checks before `NO_COLOR`, so it wins). Only the prefix word carries ANSI.

- **Subcommand matrix — pick deterministic, claude-free paths so the integration tier stays hermetic** (the autouse `_no_real_claude_subprocess` gate in `tests/conftest.py` raises if any path shells out to real `claude`):
  - **`warn()` family / stderr** — `plan_tool/cli.py:cmd_run`'s non-reconcile iterate guard (`if getattr(args, "iterate", False) and args.mode != "reconcile":`). The guard does not short-circuit, so `--mode check` falls through to `run_step(...)`; stub `cli.run_step` to return a fake `RunResult` (replicating `test_iterate_with_non_reconcile_mode_warns_on_stderr`'s `self._patch_run_step` plus `_patch_walk`) so no real `claude` runs and the conftest `_no_real_claude_subprocess` gate stays satisfied. Those helpers are methods of a different test class (around `tests/test_cli.py:5824`) and are not callable via `self` from `TestSubcommandStyleOutput` — duplicate their stubbing logic inline rather than invoking them. Drive `main(["--manifest", str(manifest), "run", "plan", "--mode", "check", "--step", "1", "--iterate"])` over `_iter_basic_plan`/`_iter_setup_manifest` + `_iter_force_tty(monkeypatch, True)`. Emits `warning: --iterate only applies to ...` on stderr, `rc == 0`, no claude. (Existing `test_iterate_with_non_reconcile_mode_warns_on_stderr` already proves this path is reachable.)
  - **`error()` family / stderr** — `plan_tool/cli.py:cmd_register`'s invalid-plan branch (`error(f"{target} is not a valid structured plan: {exc}")`). Write a malformed `.md`, `monkeypatch.chdir(tmp_path)` with a `.git` dir, `main(["register", str(bad_md)])` → single-line stderr `error: <path> is not a valid structured plan: ...`, `rc == 1`, no claude. Construct the expected string at runtime, not hardcoded: `target` is the **resolved absolute path** (`_resolve_register_target` returns `candidate.resolve()`, cli.py:462), not the input arg, and `{exc}` is the live `ParseError`/`ValidationError` message — build the expectation as `f"error: {bad_md.resolve()} is not a valid structured plan: {exc}\n"`, deriving `exc` by calling the same parse that `cmd_register` invokes on `bad_md` and capturing its raised message. The resolved-path branch reaching `cli.py:426` is stderr-silent first: `_load_context`→`build_plan_tool_context` (`plan_tool/locator.py`) emits nothing, and `_resolve_register_target` is pure filesystem lookups, so no preceding line slips in — its stderr is exactly that one line and a `==` byte-identity assertion is clean.
  - **`tool()` / `plan-tool:` namespace via a migrated library line / stderr** — `plan_tool/review.py:check_plan_audit` emits `plan-tool: plan-audit: skipped (no invoker configured)` when the invoker is `None` (post-step-1 this goes through `style.tool()`). `cmd_completeness` calls `check_plan_audit(plan, path, repo_root=…, invoker=shell_review_invoker)` (cli.py:8437) in its audit-only path, so null the invoker at the seam without bypassing the real diagnostic:
    - `import plan_tool.review as review_module`, capture `_real_audit = review_module.check_plan_audit`, then `monkeypatch.setattr(review_module, "check_plan_audit", lambda *a, **k: _real_audit(*a, **{**k, "invoker": None}))`. `cmd_completeness` resolves `check_plan_audit` via a function-body `from plan_tool.review import check_plan_audit`, so patching the module attribute takes effect through `main()`.
    - Drive `main(["completeness", "<plan>"])` over a minimal valid plan (`_iter_basic_plan` shape) resolvable in the cwd, `monkeypatch.chdir(tmp_path)`. The deterministic primitives run with no claude call; the audit's invoker is forced to `None`, so its real skip line fires. Audit-only mode (no `--iterate`) avoids the convergence loop.
    - Assert the exact `plan-tool: plan-audit: skipped (no invoker configured)\n` line appears in `captured.err`.
  - **Stream split** — on the `completeness` case above, assert the grouped completeness report (printed to stdout in audit-only mode) lands on `captured.out` while the `plan-tool:` skip line lands on `captured.err`; assert the skip prefix is absent from `captured.out`. (`checkpoint show` is the canonical stdout-result/stderr-metadata split already covered by `TestCmdCheckpoint::test_show_prints_payload_to_stdout`; do not duplicate it here.)

- **Byte-identity assertion shape:**
  - Where the diagnostic stream is exactly one line (`register`), assert `captured.err == "error: <expected body>\n"`.
  - Where the stream carries other content (`run`, `completeness`), assert the exact prefixed line is a member (`"warning: --iterate only applies to ...\n" in captured.err` against the full f-string body) **and** assert plain-mode purity: `"\033[" not in captured.err`.

- **Prefix-only color assertion shape** (mirror `tests/test_style.py:TestDiagnosticHelpers`):
  - `warn()` line: `captured.err` contains `style.BOLD_YELLOW + "warning:" + style.RESET + " "` and the body after it carries no escape (`"\033[" not in body_after_prefix`).
  - `error()` line: `style.BOLD_RED + "error:" + style.RESET`.
  - `tool()` line: `style.DIM + "plan-tool:" + style.RESET` present, and the `plan-audit:` sub-tag stays a plain body token (no SGR around it — it is a domain sub-tag, not a `tool()` level).

- **No new production seams.** Do not add `stream=`/`file=` parameters to any `cmd_*` handler to make capture easier — `capsys` already captures both streams. The monkeypatches beyond env are the `run`-case `cli.run_step`/walk stubs (which keep the iterate-guard path hermetic without reaching real `claude`) and the `completeness`-case `check_plan_audit` invoker-null wrapper (which exercises the real diagnostic body rather than stubbing it).

## Tests

All cases live in `tests/test_cli.py::TestSubcommandStyleOutput` (`@pytest.mark.integration`):

- `test_run_iterate_warning_plain_matches_legacy` — `main(["--manifest", …, "run", "plan", "--mode", "check", "--step", "1", "--iterate"])` with color off: `captured.err` contains the exact `warning: --iterate only applies to …` line and no `\033[`.
- `test_run_iterate_warning_prefix_colorizes` — same drive with `PLAN_TOOL_FORCE_COLOR=1`: `captured.err` wraps only `warning:` in `BOLD_YELLOW`/`RESET`; the message body has no escapes.
- `test_register_invalid_plan_error_plain_matches_legacy` — `main(["register", <bad.md>])`: `captured.err == f"error: {bad_md.resolve()} is not a valid structured plan: {exc}\n"`, `rc == 1`. Build the expectation at runtime — `target` is the resolved absolute path (`candidate.resolve()`, cli.py:462) and `{exc}` is the live `ParseError`/`ValidationError` message; do not hardcode either.
- `test_register_error_prefix_colorizes` — same drive with forced color: `error:` wrapped in `BOLD_RED`/`RESET`, body plain.
- `test_completeness_skip_line_plain_matches_legacy` — `main(["completeness", <plan>])` with the invoker-null wrapper, color off: `captured.err` contains `plan-tool: plan-audit: skipped (no invoker configured)\n` byte-for-byte.
- `test_completeness_skip_prefix_colorizes` — same drive with forced color: `plan-tool:` dimmed (`DIM`/`RESET`); the `plan-audit:` sub-tag and body carry no SGR.
- `test_completeness_result_on_stdout_diagnostics_on_stderr` — same drive: the completeness report is in `captured.out`, the `plan-tool:` skip line is in `captured.err` and absent from `captured.out`.

## Acceptance criteria

- `uv run pytest -m integration tests/test_cli.py -q` collects and passes `TestSubcommandStyleOutput`.
- With `PLAN_TOOL_FORCE_COLOR`/`NO_COLOR` unset, each driven subcommand's captured stderr is byte-identical to its legacy `plan-tool:`/`warning:`/`error:` line (no ANSI bytes present).
- With `PLAN_TOOL_FORCE_COLOR=1`, each captured diagnostic wraps only the prefix word in SGR codes (`BOLD_YELLOW`/`BOLD_RED`/`DIM` + `RESET`) and the message body contains no `\033[`.
- The `completeness` case proves stream routing: report on `captured.out`, `plan-tool:` skip line on `captured.err`, skip prefix absent from `captured.out`.
- No `plan_tool/` source file is modified by this step (`git diff --stat` shows only `tests/test_cli.py`).
- `uv run pytest tests/test_style.py tests/test_review.py tests/test_review_walk.py tests/test_detail.py tests/test_change_collision.py tests/test_iteration_lock.py tests/test_jira.py tests/test_claude_errors.py tests/test_lessons.py tests/test_shell.py tests/test_cli.py` exits 0.

## References

- [sys — stdout/stderr and isatty() (Python docs)](https://docs.python.org/3/library/sys.html#sys.stdout) — the streams and TTY check that decide where results vs. diagnostics go and how `style.color_enabled` gates color per destination.
- [NO_COLOR standard](https://no-color.org/) — the `NO_COLOR` convention `style.py` honors; relevant to clearing it in the plain-mode case so the gate isn't flipped by an inherited env.
- [pytest — capsys / capturing stdout and stderr](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — `capsys.readouterr().out` / `.err` are the per-stream capture seam this step relies on.
- [XTerm Control Sequences (SGR codes)](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html) — catalog of the SGR escapes (`\033[…m`) the prefix-only-color assertions match against.

## Deferred

- **Exhaustive per-subcommand `plan-tool:` coverage** — stays in the steps 1–5 unit `*StyleOutput` suites, which pin every migrated line byte-for-byte. Most `tool()` lines sit behind a claude/seam boundary; step 6 is a representative end-to-end smoke (one `warn()`, one `error()`, one `tool()` line) proving the env gate + stream split + prefix-only color hold through `main()`.
- **The `run --mode reconcile` alias's `iteration_lock`/`auto_reconcile`/`change_collision` `tool()` lines** — reaching them through `main()` requires the deprecated/`@pytest.mark.skip`-gated reconcile-iteration path (`TestCmdRunReconcileIterationLoop`); their byte-identity is already asserted by `tests/test_iteration_lock.py`, `tests/test_auto_reconcile.py`, and `tests/test_change_collision.py`.
- **`detail`/`jira`/`create` `tool()`/`warn()` lines that require a real or stubbed claude call** — out of scope to re-drive end-to-end here; the conftest claude gate makes them non-hermetic without per-subcommand invoker stubbing the unit suites already cover.
- **stdout headline (`success()`/`detail()`) formatting** — out of plan scope (`## Out of scope`): only diagnostic prefix lines migrate; result/headline formatting is unchanged.
