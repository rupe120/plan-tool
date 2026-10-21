> **Auto-archived**: this plan was swept on 2026-06-01 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Route jira.py's acceptance-criteria / file-reference `warning:` diagnostics through `style.warn()` and pin them with `TestJiraStyleOutput`

## Summary

Replace the two hand-rolled `print(f"warning: …", file=sys.stderr)` diagnostic emitters in `plan_tool/jira.py` with calls to `plan_tool/style.py`'s `warn()` helper, so `jira`'s library-level lines share one owner for prefix wording, color gating, and target stream. Both sites live in `_emit_story_warnings`: the missing-documentation-file warning (per story/file) and the acceptance-criteria warnings (one `print(warning, …)` per string returned by `lint_acceptance_criteria`). The load-bearing decision: drop the literal `warning: ` head from the three `warnings.append(...)` sites inside `lint_acceptance_criteria` so it returns **bodies**, and route every body through `warn()` in `_emit_story_warnings` — `warn()` re-adds `warning: `, keeping plain-mode output **byte-identical** while making the prefix single-owned. `import sys` becomes unused and is removed. On green, a new `TestJiraStyleOutput` class in `tests/test_jira.py` asserts that byte-identity (capsys, plain mode) and prefix-only ANSI under `PLAN_TOOL_FORCE_COLOR`.

## Table of Contents

- [Why](#why) — what's inconsistent about jira.py's diagnostics today
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — per-site conversion, the linter contract change, and the new test class
- [Tests](#tests) — cases in `TestJiraStyleOutput`
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — color/SGR/stream docs consulted
- [Deferred](#deferred) — sites and helpers intentionally left alone

## Why

- **`jira.py` still hand-rolls its `warning:` diagnostics.** It emits raw `print(f"warning: …", file=sys.stderr)` and has no `from plan_tool.style import …` line, so its lines miss the centralized `NO_COLOR` / `PLAN_TOOL_FORCE_COLOR` / TTY gate, and wording must be maintained in two places. After steps 1–3 routed `review.py`, `detail.py`, `auto_reconcile.py`, `change_collision.py`, and `iteration_lock.py` through `style`, `jira.py` is a remaining holdout.
- **One owner for prefix + color + stream is the project's stated direction.** `plan_tool/style.py`'s `warn()` exists precisely so `warning:` looks the same regardless of which subcommand emits it; `create.py`, `launcher.py`, and `cli.py` already import from it.
- **The risk is silent wording drift.** These strings are scanned by operators reading `plan-tool jira` run logs and are grepped by the existing integration tests (`TestExportJiraSoftWarnOnAcceptanceCriteria`, `TestExportJiraSoftWarnOnMissingFiles`). The byte-identity test locks plain-mode output so the refactor is provably presentation-only.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/jira.py` — add `from plan_tool.style import warn`; drop the literal `warning: ` head from the three `warnings.append(...)` sites in `lint_acceptance_criteria`; convert the two `print(... file=sys.stderr)` sites in `_emit_story_warnings` to `warn(...)`; remove the now-unused `import sys`; refresh the `lint_acceptance_criteria` docstring's "pre-formatted for stderr display" sentence.
  - `tests/test_jira.py` — add `from plan_tool import style`; extend the `from plan_tool.jira import (...)` block with `_emit_story_warnings`; add a `TestJiraStyleOutput` class.

## Implementation

### `plan_tool/jira.py`

- **Add the import.** Insert `from plan_tool.style import warn` into the first-party `from plan_tool.X import …` cluster (the block ending with `from plan_tool.shell import claude_invoke`). Place it after the `shell` line to keep the block sorted. Import only `warn` — no `plan-tool:`-prefixed lines exist in this module, so `tool()` is **not** imported (see Deferred).

- **Remove `import sys`.** It is referenced only by the two `file=sys.stderr` sites being converted (verified: no other `sys.` usage in the file). `warn()` defaults its `stream` to `sys.stderr` internally, so once both sites route through it `import sys` is dead and must be deleted to keep the module lint-clean.

- **Single-owner the `warning:` prefix in `lint_acceptance_criteria`.** Today its three `warnings.append(...)` calls each build a string that *starts with* the literal `warning: ` (the no-AC case, the vague-phrasing case, and the refactor-fragile-handle case). Drop **only** the leading `warning: ` from each appended f-string so the function returns **bodies**, not pre-prefixed lines. Preserve every other character verbatim (the em-dashes, the `{story.id}`, the `{flagged_vague!r}` / `{flagged_handle!r}` repr, the trailing guidance clause).
  - **Why change the producer rather than strip in the consumer:** `lint_acceptance_criteria` is consumed only by `_emit_story_warnings` (confirmed — no other call site in `plan_tool/`). Returning bodies lets `_emit_story_warnings` route every category through `warn()` uniformly with no string re-parsing, and makes `style` the sole owner of the `warning:` token. The alternative — keep the prefix and re-split it in the consumer — re-introduces a second place that "knows" the prefix word, defeating the consolidation.
  - **Refresh the docstring.** The closing sentence "The returned strings are pre-formatted for stderr display." no longer holds; replace it with a one-liner stating the returned strings are `warn()` bodies (no `warning:` prefix). Keep the rest of the docstring (the three failure categories, the one-warning-per-category rule) intact.

- **Convert the missing-documentation-file warning in `_emit_story_warnings`.** Replace the multi-fragment `print(f"warning: story {story.id} references file " … f"`{repo_root}`", file=sys.stderr)` with `warn(f"story {story.id} references file `{f}` that doesn't exist under repo root `{repo_root}`")`. Collapse the three f-string fragments into one body, dropping only the literal `warning: ` head and preserving the inter-fragment spaces exactly (the existing literals carry the joining spaces — `"… references file "` + `"`{f}` that doesn't exist under repo root "` + `"`{repo_root}`"`). `warn()` re-adds `warning: ` and defaults to `sys.stderr`, so plain-mode bytes are unchanged.

- **Convert the acceptance-criteria warning loop in `_emit_story_warnings`.** Replace `for warning in lint_acceptance_criteria(stories): print(warning, file=sys.stderr)` with `for body in lint_acceptance_criteria(stories): warn(body)`. Because the linter now returns bodies and `warn()` re-adds the head, each emitted line is byte-identical to today's `warning: <…>`.

- **Both sites share `_emit_story_warnings`.** It is called from both the fresh-export path (`export_jira`) and the append path (`_export_jira_append`), so a single conversion covers `plan-tool jira` and `plan-tool jira` re-runs. No stream kwarg is threaded through `_emit_story_warnings` — it writes to `sys.stderr` via `warn()`'s default — so the test capture seam is **capsys**, not a StringIO `file=` injection (this mirrors `detail.py`'s seam, not `review.py`'s).

### `tests/test_jira.py`

- **Add imports.** Add `from plan_tool import style` (for the ANSI constants in the color assertion). Extend the existing `from plan_tool.jira import (...)` block with `_emit_story_warnings` (the function the new class calls directly); `lint_acceptance_criteria` and `Story` are already imported. `io` is **not** needed — the seam is capsys, so there is no `_TTY` StringIO to construct.

- **Add `TestJiraStyleOutput`.** Drive `_emit_story_warnings(stories, repo_root)` directly with `tmp_path` as `repo_root`, capturing `capsys.readouterr().err`. Build `Story` objects inline (mirror the existing `_story` / `_mk_story` helpers' field set). For color cases, `monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")` so `style.color_enabled` forces ANSI on even though capsys's replacement stream is non-TTY; mirror `tests/test_style.py::TestDiagnosticHelpers::test_warn_colored_prefix_only` for the assertion shape.

## Tests

In `tests/test_jira.py`, class `TestJiraStyleOutput` (approx. 5 cases):

- `test_missing_doc_file_warning_plain` — story with a non-existent `.md` file under `repo_root`; `err` equals exactly `f"warning: story {sid} references file `{f}` that doesn't exist under repo root `{repo_root}`\n"` (full byte-identity, single line).
- `test_acceptance_criteria_warnings_plain` — story with a vague bullet (`"Code is clean"`) and empty `files`; `err` equals `"".join(f"warning: {b}\n" for b in lint_acceptance_criteria(stories))`, proving `_emit_story_warnings` re-adds exactly `warning: ` per linter body and nothing else.
- `test_no_acceptance_criteria_warning_plain` — story with `acceptance_criteria=[]`; the emitted line equals `f"warning: {lint_acceptance_criteria(stories)[0]}\n"` and contains `no acceptance criteria` (byte-identity for the empty-AC category).
- `test_multiple_warnings_each_prefixed_plain` — story with a missing doc file *and* both a vague and a refactor-fragile bullet; every non-empty `err` line independently starts with `warning: ` (no continuation/bare lines leak through), and the file warning precedes the AC warnings (the order `_emit_story_warnings` emits them).
- `test_warning_color_prefix_only` — with `PLAN_TOOL_FORCE_COLOR` set, a vague-AC story; each non-empty `err` line starts with `style.BOLD_YELLOW + "warning:" + style.RESET + " "` and the body text after the prefix carries no surrounding ANSI escapes (prefix-only color, `BOLD_YELLOW` — not `DIM`, which is `tool()`'s tag color).

Existing regression controls (must still pass unchanged): `TestLintAcceptanceCriteria` (asserts substrings `vague phrasing` / `refactor-fragile` / `no acceptance criteria` / the bullet / the story id — none assert the `warning:` head, so the body change is invisible to them), `TestExportJiraSoftWarnOnAcceptanceCriteria`, and `TestExportJiraSoftWarnOnMissingFiles` (grep `err` for `vague phrasing`, `Code is clean`, `missing-checklist.md`, `doesn't exist` — all still present after conversion).

## Acceptance criteria

- `plan_tool/jira.py` imports `from plan_tool.style import warn` and contains no `import sys` line.
- `grep -n 'f"warning:' plan_tool/jira.py` returns zero matches; `grep -n "sys.stderr" plan_tool/jira.py` returns zero matches.
- `lint_acceptance_criteria` returns strings that do **not** begin with `warning: ` (they are `warn()` bodies); each still contains its category phrase (`no acceptance criteria` / `vague phrasing` / `refactor-fragile`) and the offending story id / bullet.
- For a story referencing a missing doc file, `_emit_story_warnings` emits exactly `warning: story <id> references file `<f>` that doesn't exist under repo root `<root>`\n` on stderr in plain mode.
- Under `PLAN_TOOL_FORCE_COLOR`, every emitted warning line begins with `BOLD_YELLOW + "warning:" + RESET + " "` and the body after the prefix has no ANSI escapes.
- `tests/test_jira.py::TestJiraStyleOutput` passes; the full `tests/test_jira.py` and `tests/test_style.py` suites pass.

## References

- [NO_COLOR standard](https://no-color.org/) — the `NO_COLOR` convention `style.color_enabled` honors when gating ANSI on/off; relevant because the converted warnings now inherit that gate.
- [XTerm Control Sequences (invisible-island, Thomas Dickey)](https://invisible-island.net/xterm/ctlseqs/ctlseqs.html) — catalog of SGR escape sequences behind `BOLD_YELLOW` / `RESET` asserted in the color test.
- [ECMA-48: Control Functions for Coded Character Sets](https://ecma-international.org/publications-and-standards/standards/ecma-48/) — the standard specifying the SGR parameters (bold, yellow foreground, reset) `style.warn` emits.
- [sys — System-specific parameters and functions (Python docs)](https://docs.python.org/3/library/sys.html#sys.stdout) — the `sys.stderr` stream `warn()` defaults to once `jira.py`'s explicit `file=sys.stderr` is removed.

## Deferred

- **`tool()` and `plan-tool:`-prefixed lines** — not imported and not used here; `jira.py` has no `plan-tool:` diagnostic. If a future change adds a source-tagged library line, route it through `tool()` per the project's namespace convention, but that is out of this step's scope.
- **`style.error` / non-`warning` severities** — both converted lines are genuinely advisory (`lint_acceptance_criteria` and the missing-file check never reject; the docstrings say "soft-warned"), so `warn()` is the only correct helper. Do not map any of them onto `error()`/`info()`/`note()`, which would change the rendered prefix and break byte-identity.
- **The `JiraError` raise-site messages** — these are exception payloads surfaced by the CLI, not `print`/`warn` diagnostics, and stay as-is.
- **Append-path progress lines** — `reporter.start_step` / `handle.complete` / `handle.fail` go through `ProgressReporter`, not `style`, and are untouched.
