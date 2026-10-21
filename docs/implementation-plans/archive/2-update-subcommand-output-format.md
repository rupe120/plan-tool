> **Auto-archived**: this plan was swept on 2026-06-01 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Update Subcommand Output Format
status: completed
priority: medium
steps:
- id: 1
  title: 'Route review.py review/criteria-fulfillment diagnostics (deferred-triage
    summary at ~2730, plan-audit skip/summary at ~3284/3342, criteria-fulfillment
    lines, lesson-extraction error) through style.tool()/warn(); add TestReviewStyleOutput
    asserting plain-mode byte-identity to legacy plan-tool: prefixes and prefix-only
    color under PLAN_TOOL_FORCE_COLOR'
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  detail: docs/implementation-plans/plan-details/update-subcommand-output-format/01-route-review-py-review-criteria.md
  status: done
- id: 2
  title: 'Route detail.py diagnostics (checkpoint save/discard, archived-detail, detail-body-mentions
    warning, iteration-halt, lesson-extraction plan-tool:/warning: lines) through
    style helpers; add TestDetailStyleOutput for plain-mode byte-identity and prefix-only
    color'
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  detail: docs/implementation-plans/plan-details/update-subcommand-output-format/02-route-detail-py-diagnostics-checkpoint.md
  status: done
- id: 3
  title: 'Route run/reconcile-loop diagnostics (auto_reconcile, change_collision sidecar
    messaging, iteration_lock drift/SIGINT plan-tool: lines) through style helpers;
    add a TestStyleOutput class per module including a new tests/test_auto_reconcile.py'
  files:
  - plan_tool/auto_reconcile.py
  - plan_tool/change_collision.py
  - plan_tool/iteration_lock.py
  - tests/test_change_collision.py
  - tests/test_iteration_lock.py
  creates:
  - tests/test_auto_reconcile.py
  complexity: high
  detail: docs/implementation-plans/plan-details/update-subcommand-output-format/03-route-run-reconcile-loop-diagnostics.md
  status: done
- id: 4
  title: 'Route jira.py acceptance-criteria/file-reference warning: diagnostics through
    style.warn(); add TestJiraStyleOutput for plain-mode byte-identity and prefix-only
    color'
  files:
  - plan_tool/jira.py
  - tests/test_jira.py
  complexity: low
  detail: docs/implementation-plans/plan-details/update-subcommand-output-format/04-route-jira-py-acceptance-criteria-file.md
  status: done
- id: 5
  title: 'Route shared cross-command library diagnostics (claude_errors quota-wait,
    lessons migration/citation/equivalence, shell claude-exec failures) through style.tool()/warn()/error()
    instead of bare plan-tool:/warning: prints; add a TestStyleOutput class per module'
  files:
  - plan_tool/claude_errors.py
  - plan_tool/lessons.py
  - plan_tool/shell.py
  - tests/test_claude_errors.py
  - tests/test_lessons.py
  - tests/test_shell.py
  complexity: medium
  detail: docs/implementation-plans/plan-details/update-subcommand-output-format/05-route-shared-cross-command-library.md
  status: done
- id: 6
  title: Add @pytest.mark.integration TestSubcommandStyleOutput in tests/test_cli.py
    asserting main()-driven subcommand output is plain-mode byte-identical to legacy
    prefixes, colorizes only the prefix under PLAN_TOOL_FORCE_COLOR, and routes diagnostics
    to stderr vs results to stdout (capsys per stream)
  files:
  - tests/test_cli.py
  complexity: medium
  depends_on:
  - 1
  - 2
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/update-subcommand-output-format/06-pytest-mark-integration.md
  status: done
---
# Update Subcommand Output Format

## Overview

Update the output format of each `plan-tool` subcommand to improve readability.

## Problem statement

The current output format of the subcommands is hard to read; this work reformats each subcommand's output for easier readability.

## Architecture

`plan_tool/style.py` is the single owner of diagnostic wording, color, and target stream. It already exposes the helpers every subcommand routes through: `warn()`/`error()`/`info()`/`note()` for bare-prefixed lines, `tool()` for `plan-tool:`-namespaced library messages, and `success()`/`detail()` for stdout headlines. This plan introduces no new component — it migrates each subcommand and shared library off hand-rolled `print(f"plan-tool: ...")`/`print(f"warning: ...")` calls and onto these helpers, so the steps fan out by module (review/review-walk, detail, run/reconcile loop, jira, shared diagnostics) and converge on the same dependency: a single import of `style`.

The central design constraint is plain-mode byte-compatibility. `style.color_enabled()` gates ANSI on TTY/`NO_COLOR`/`PLAN_TOOL_FORCE_COLOR`, and the prefix helpers are built so that with color off the output is identical to the legacy bare-prefix prints, on the same stream. The legacy diagnostic prints already targeted stderr (`print(..., file=out)` with `out` defaulting to `sys.stderr`, or `file=sys.stderr` directly), which is also the prefix helpers' default — so both the bytes and the destination stream are preserved. That keeps existing stderr-reading greps and tests passing and lets the migration land module-by-module without a coordinated cutover. Color, when enabled, is scoped to the prefix word only — bodies stay plain so paths and identifiers remain legible.

Stream routing is the other deliberate split: progress/diagnostics stay on stderr (the legacy prints' stream and the helpers' default) while results go to stdout, so the TTY check matches the real destination and piping results stays clean. This is no reroute for the migrated diagnostics — they were already on stderr — so the byte-identity claim holds on the same stream greps and tests read. Step 6 sits downstream of all migration steps (`depends_on: 1–5`) because its integration coverage can only assert the unified behavior — plain-mode byte-identity to legacy prefixes plus colorization under `PLAN_TOOL_FORCE_COLOR` — once every subcommand is on the helpers.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — Official reference for subparsers, usage/help formatting, and HelpFormatter classes — consulted when reshaping each subcommand's output structure.
- [textwrap — Text wrapping and filling (Python docs)](https://docs.python.org/3/library/textwrap.html) — Documents wrap/fill/indent/dedent used to align and reflow multi-line diagnostic blocks for readability.
- [shutil.get_terminal_size (Python docs)](https://docs.python.org/3/library/shutil.html#shutil.get_terminal_size) — Canonical way to detect terminal width for wrapping and column alignment when reformatting output.
- [sys — System-specific parameters and functions (Python docs)](https://docs.python.org/3/library/sys.html#sys.stdout) — Reference for the stdout/stderr streams and isatty()-based TTY detection that decide where formatted results vs. diagnostics are written.
- [NO_COLOR standard](https://no-color.org/) — Defines the NO_COLOR convention that style.py honors when gating ANSI color on or off.
- [XTerm Control Sequences (invisible-island, Thomas Dickey)](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html) — Authoritative catalog of terminal control and SGR (color/bold/dim) escape sequences underlying the raw ANSI codes in style.py.
- [ECMA-48: Control Functions for Coded Character Sets](https://ecma-international.org/publications-and-standards/standards/ecma-48/) — Primary standard specifying SGR parameters (bold, dim, foreground colors, reset) emitted directly by the styling helpers.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- New `style.py` helpers or color/stream semantics — the helpers already exist; this plan only routes callers through them.
- Changing the wording, prefixes, or stream of any diagnostic — plain-mode output stays byte-identical to legacy prints.
- stdout result/headline formatting beyond what `success()`/`detail()` already cover — only diagnostic (`plan-tool:`/`warning:`) lines migrate.
- Subcommands with no hand-rolled prefix prints — modules already free of `print(f"plan-tool: ...")`/`print(f"warning: ...")` need no migration.
- Restructuring argparse help/usage text — reference material is included for context, but help reformatting is a separate concern.

## Risks

- A migrated print drifts from its legacy bytes (trailing space, prefix casing, newline) — high severity, since it breaks existing greps/tests silently; mitigated by step 6's plain-mode byte-identity assertions, but only after steps 1–5 land.
- Diagnostics rerouted to stderr break tests that captured them on stdout — medium severity; mitigated by updating each module's tests in-step, though a missed assertion surfaces as a flaky failure rather than a clear one.
- A hand-rolled `plan-tool:`/`warning:` print is missed during the per-module sweep — medium severity; partially mitigated by grep, but no guarantee every variant (f-string, concatenation, multi-line) is caught.
- Color leaks into a body or escapes prefix scope when `PLAN_TOOL_FORCE_COLOR` is set — low severity; mitigated by scoping ANSI to the prefix word, but untested bodies with embedded paths remain an unresolved gap.
- Step 6 asserts unified behavior on an incomplete migration if any of steps 1–5 lands partial, giving false confidence — medium severity; the `depends_on: 1–5` gate orders but does not verify completeness of each upstream step.

## Testing

Unit-first, per `TESTING.md`: each migration step (1–5) gets unmarked unit tests in the `test_X.py` mirroring its source module, asserting that with color disabled the migrated diagnostic is byte-identical to its legacy prefix and that the prefix word colorizes under `PLAN_TOOL_FORCE_COLOR` while the body stays plain. Step 6 adds the only new integration coverage (`@pytest.mark.integration`), driving `main()` end-to-end.

- `tests/test_review.py` (step 1, unmarked): `TestReviewStyleOutput` — `test_deferred_triage_summary_plain_matches_legacy`, `test_plan_audit_skip_line_plain_matches_legacy`, `test_prefix_colorizes_under_force_color`, `test_body_stays_plain_under_force_color`.
- `tests/test_review_walk.py` (step 1, unmarked): `TestReviewWalkStyleOutput` — `test_walk_diagnostic_plain_matches_legacy`, `test_walk_prefix_colorizes_under_force_color`.
- `tests/test_detail.py` (step 2, unmarked): `TestDetailStyleOutput` — `test_checkpoint_line_plain_matches_legacy`, `test_archive_line_plain_matches_legacy`, `test_convergence_warning_plain_matches_legacy`, `test_prefix_colorizes_under_force_color`.
- `tests/test_change_collision.py`, `tests/test_iteration_lock.py`, and new `tests/test_auto_reconcile.py` (step 3, unmarked): a `TestStyleOutput` class per module asserting sidecar / lock / reconcile diagnostics are plain-mode byte-identical to legacy and colorize the prefix only under `PLAN_TOOL_FORCE_COLOR`.
- `tests/test_jira.py` (step 4, unmarked): `TestJiraStyleOutput` — `test_diagnostic_plain_matches_legacy`, `test_prefix_colorizes_under_force_color`.
- `tests/test_claude_errors.py`, `tests/test_lessons.py`, `tests/test_shell.py` (step 5, unmarked): a `TestStyleOutput` class per module asserting each shared-library `plan-tool:` line routes through `style.tool()`/`warn()`/`error()` with plain-mode byte-identity and prefix-only color.
- `tests/test_cli.py` (step 6, `@pytest.mark.integration`): `TestSubcommandStyleOutput` — for each migrated subcommand, `main([...])` output captured via `capsys` is byte-identical to the legacy prefix with color off, and colorizes the prefix (body unchanged) when `PLAN_TOOL_FORCE_COLOR` is set; diagnostics land on stderr and results on stdout.

Existing suites that must still pass: `tests/test_style.py` (the helpers' own contract), and the full diagnostic-asserting suites for each migrated module — `tests/test_review.py`, `tests/test_review_walk.py`, `tests/test_detail.py`, `tests/test_change_collision.py`, `tests/test_iteration_lock.py`, `tests/test_jira.py`, `tests/test_claude_errors.py`, `tests/test_lessons.py`, `tests/test_shell.py`, `tests/test_cli.py`.

When modifying any migrated source module, run the CLI integration tier per `TESTING.md`: `uv run pytest -m integration tests/test_cli.py -q` (the `cmd_*` handler classes plus the new `TestSubcommandStyleOutput`).

## Acceptance criteria

- With color disabled, every migrated diagnostic in `plan_tool/review.py`, `plan_tool/review_walk.py`, `plan_tool/detail.py`, `plan_tool/auto_reconcile.py`, `plan_tool/change_collision.py`, `plan_tool/iteration_lock.py`, `plan_tool/jira.py`, `plan_tool/claude_errors.py`, `plan_tool/lessons.py`, and `plan_tool/shell.py` is byte-identical to its legacy `plan-tool:`/`warning:` prefix line (asserted by the per-module `TestStyleOutput`/`TestReviewStyleOutput`/etc. classes).
- `rg "print\(f?\"(plan-tool|warning):" plan_tool/review.py plan_tool/review_walk.py plan_tool/detail.py plan_tool/auto_reconcile.py plan_tool/change_collision.py plan_tool/iteration_lock.py plan_tool/jira.py plan_tool/claude_errors.py plan_tool/lessons.py plan_tool/shell.py` returns no matches — every hand-rolled prefix print in the modules listed in steps 1–5 routes through `style.tool()`/`warn()`/`error()`/`info()`/`note()`.
- With `PLAN_TOOL_FORCE_COLOR` set, each migrated line wraps only the prefix word (`plan-tool:`/`warning:`) in ANSI SGR codes and the message body contains no escape sequences (asserted by `test_prefix_colorizes_under_force_color` and `test_body_stays_plain_under_force_color`).
- Migrated diagnostics are written to stderr and command results to stdout, verified by `tests/test_cli.py::TestSubcommandStyleOutput` capturing each stream separately via `capsys`.
- `main([...])` output for each migrated subcommand is byte-identical to the legacy prefix with color off and colorizes the prefix (body unchanged) with `PLAN_TOOL_FORCE_COLOR` set (`tests/test_cli.py::TestSubcommandStyleOutput`, `@pytest.mark.integration`).
- `uv run pytest tests/test_style.py tests/test_review.py tests/test_review_walk.py tests/test_detail.py tests/test_change_collision.py tests/test_iteration_lock.py tests/test_jira.py tests/test_claude_errors.py tests/test_lessons.py tests/test_shell.py tests/test_cli.py` exits 0.

## Deferred

- Nothing deferred yet — populate as implementation drops or postpones work, one bullet per item with a one-line reason (too large, blocked, separate concern).
