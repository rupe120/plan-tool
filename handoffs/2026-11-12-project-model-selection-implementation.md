# Project model selection implementation

The implementation branch is `implement/project-model-selection`, based on
`d858703b1` (merged plan PR #193). All four steps are done. Project backend
defaults and backend-scoped command models ship through the existing reader,
selector, and CLI; documentation and bundled routers share that contract.
Backlog #254 is reconciled; copied-skill freshness remains #525.

## Execution and verification

- `plan-tool --backend codex --model gpt-6.1-sol run project-model-selection --all --commit -y`
  completes all four steps, with full-suite gates green after each step.
- `plan-tool --backend codex --model gpt-6.1-sol reconcile-code project-model-selection --all --no-walk --no-reuse -y`
  completes one full sweep of steps 1–3; non-code step 4 is excluded.
  Reports `20261113-033850`, `20261113-034025`, and `20261113-034201`
  remain in the plan's reports directory. Steps 2 and 3 are clean. Step 1
  identifies missing explicit `path=` compatibility coverage.
- `1b6ac78e0` closes that coverage finding for all three reader APIs.
  Identifier search (`path=`, reader symbols) and vocabulary search
  (`override`, configuration source) identify the shared reader and its
  wrappers; no existing test pins explicit-path precedence. The new test
  asserts that an explicit file wins over a conflicting conventional file.
  Disabling explicit-path selection makes all three parametrized cases fail.
- Final `uv run pytest tests/ -q -n auto`: **14824 passed, 67 skipped**.

## Independent code reviews

Both reviews inspect `d858703b148f78b3c27ddb1655ae9209f68091f5...1b6ac78e0b24cd3c6504dd8c2ca7a34ff99e7a44`.
Two fresh, read-only Codex processes independently compare the diff with the
plan, four details, and existing tests. Both return explicit clean verdicts
with no confirmed actionable correctness or completeness defects. They trace
configuration compatibility, command aliases, backend/model precedence,
repository resolution, read-only behavior, provisional backends, argv paths,
and fallback isolation/restoration. Read-only executable checks pass; the
full-suite result above comes from the writable execution session.

Local reports are `.tmp/project-model-selection.review-1.md` and
`.tmp/project-model-selection.review-2.md`; their process logs carry the
`project-model-selection.codex-review-` prefix. Claude `/code-review` cannot
start because its saved authentication expires; Codex supplies both reviews.

The branch remains local. Publication and pull-request review are the next
team checkpoint; no push, pull request, or merge is part of this execution.

## Review loop (PR 195)

Report-and-fix loop over `d858703b1..HEAD`, `/code-review` at `high`. Logs:
`.tmp/project-model-selection.review-loop-r*.test.log`.

### Review pass 1 — 9 findings

1. **Eager preflight for project `default_backend` breaks read-only commands
   without the CLI** (`cli/app.py`). Disposition: **fixed in `996afd895` (2026-11-13), follow-up #526.**
   At PR 195 review, behavior followed the documented contract: `docs/BACKENDS.md`
   § prerequisites lists "project default" beside flag and environment as
   fail-fast sources. At that snapshot, a committed `default_backend` made `list`,
   `status` and `validate` exit 127 for a teammate without that CLI.
2. **Rate-limit fallback ignores `commands.<cmd>.model`.** Disposition:
   **refuted as a defect; docs clarified.** `tests/test_shell.py` and
   `tests/test_launcher.py` pin `fallback-base` over `fallback-command` on
   purpose (fallback keeps its own selection). `docs/BACKENDS.md` now says so.
3. **Precedence chain re-derived in `app.py` for `model_supplied`.**
   Disposition: **deferred** — warning-text duplication only; no behavior
   difference today.
4. **Unguarded `command_names[args.command]`.** Disposition: **refuted.**
   The map is built from the same required-subparser choices that populate
   `args.command`, so every parsed command is a key.
5. **Command map cached as a private parser attribute.** Disposition:
   **deferred** — style only.
6. **Module docstring dropped the tuning-only guarantee; stale
   `_read_backend_config` docstring.** Disposition: **fixed** — guarantee
   restored tersely; reader docstring matches its 3-tuple return.
7. **`default_backend` case-sensitive in preflight/hint comparisons.**
   Disposition: **fixed** — comparisons use a stripped, lowercased key. The
   preflight result was already correct for mixed case; the fix removes a
   spurious "remove or change --model" hint.
8. **`backends.json` parsed twice per run.** Disposition: **deferred** —
   negligible cost; skew needs a concurrent edit mid-startup.
9. **DIRECTIVES.md gave contradictory flag advice.** Disposition: **fixed** —
   the assistant reads `.plan-tool/backends.json` to choose the regime;
   configured projects omit flags (global `--model` overrides command models).
   The three bundled routers only link to this section.

### Review pass 2 — 7 findings over `1b6ac78e0..3241029f3`

1. **No regression test for the pass-1 case normalization.** **Fixed** —
   `test_mixed_case_default_backend_does_not_raise_a_spurious_model_hint`;
   removing `.lower()` turns the `Codex` case red.
2. **Config backend keys not lowercased (`Codex` key misses).** **Declined** —
   `docs/BACKENDS.md` § configuration requires lowercase backend keys, and the
   unknown-key warning names the offending key; unchanged pre-existing contract.
3. **Whitespace-only `PLAN_TOOL_BACKEND` disagrees with `default_key`.**
   **Deferred** — `PLAN_TOOL_BACKEND=' '` selects the name `' '` while
   `default_key` is empty, so only the preflight-vs-hint text could differ;
   the selected backend is unaffected and the input is not a supported value.
4. **DIRECTIVES omit-flags rule wrongly sent command-model-only projects
   without `default_backend` to Claude.** **Fixed** — the rule now separates
   `--backend` (omit only with a top-level `default_backend`) from `--model`
   (omit when any configured model exists).
5. **Test pinned a hard-wrap newline.** **Fixed** — whitespace-normalized.
6. **DIRECTIVES named a top-level `commands` key.** **Fixed** with item 4 — it
   names `backends.<name>.commands.<command>.model`.
7. **Pass-1 item 1 disposition rested on the assistant's own reading.**
   **Fixed (record)** — now marked open pending the user's decision.

### Review pass 3 — 5 findings over `3241029f3..d9c3da09d`

1. **Omit-`--model` rule ignored which backend a model belongs to.** **Fixed**
   — scoped to the backend that will run.
2. **"Configures neither" fallback left one flag unguided.** **Fixed** — the
   directive decides `--backend` and `--model` separately.
3. **Handoff item 1 carried contradictory, session-narrated text.** **Fixed**
   — restated as an open owner decision with its cost.
4. **New test asserted only an absence.** **Fixed** — also asserts the
   preflight error text.
5. **Deferral of pass-2 item 3 lacked its observable effect.** **Fixed** —
   effect stated.

Passes 2 and 3 are majority self-seeded (4 of 7, then 5 of 5 findings describe
the previous round's own edits, mostly the DIRECTIVES paragraph): exit 2 of
CLAUDE.md § "Driving the convergence loops". The application is finished; one
confirming pass follows.

### Review pass 4 — 7 findings over `d9c3da09d..4442d6851`

1. **Backend rule ignored `PLAN_TOOL_BACKEND`.** **Fixed** — the backend counts
   as decided by flag, environment, or `default_backend`.
2. **Model rule was circular and ignored per-command scope.** **Fixed** —
   backend settled first; the model must be set for that backend and the
   command being run.
3. **Three bundled routers restated the old unconditional rule.** **Fixed** —
   all three reworded; no other restatement remains (`project defaults apply`
   search over `integrations/` and `docs/` is empty).
4. **Bold lead paragraph contradicted the per-flag paragraph.** **Fixed.**
5. **Test pinned the heading, not the carve-outs.** **Fixed** — pins
   backend-first ordering, backend-and-command scoping and the undecided-flag
   fallback.
6. **Open preflight decision has no tracked home.** **Fixed in `996afd895` (follow-up #526, 2026-11-13).**
7. **Test coupled to full preflight wording.** **Fixed** — asserts only the
   executable-not-found fragment.

### Review pass 5 — 7 findings over `bff5e3d78..e87406e44`

1. **Always-pass-flags rule overrode project configuration.** **Fixed** —
   file-existence rule (see Convergence status).
2. **Plan and step 4 detail still said "defer to project configuration".**
   **Refuted as stale text** — they were right and the shipped rule was wrong;
   no plan edit.
3. **Table gave no backend selector.** **Fixed** — "the backend appropriate to
   the work" restored for the no-file case.
4. **Deterministic commands conflicted with "pass `--backend`".** **Fixed** —
   named as needing neither flag, with the preflight reason.
5. **Handoff contradicted itself on the open decision.** **Fixed** — both items
   point to #526; the stale convergence text is replaced.
6. **Test did not pin the carve-out or superseded wording.** **Fixed.**
7. **Rule text hand-copied across three routers.** **Deferred** — one test
   asserts the same fragment in all three; a shared include has no mechanism in
   the router install path.

### Review pass 6 — `/code-review high` findings over `e87406e44..HEAD` (2026-11-13)

Scope: `d9f148a0e`, `996afd895`, `cfade9cc2` (file-existence selection rule,
project-default preflight exemption, #526 closure). Method: headless
`/code-review high`, report-only, `handoffs/` and `docs/evidence/` excluded from
bug hunting; the suite was not run. Log: `.tmp/project-model-selection.review-r6.log`.
Code and tests: no defects found. Five findings:

1. **[CONFIRMED, medium, docs-structure] `DIRECTIVES.md` ~487 — the new
   "## Explicit overengineering checkpoints" H2 sits in the middle of Gate 1.**
   The Gate 1 paragraphs after it (proportional-correction rule, `edit_drift`
   advisory, proceed-to-`detail` rule) now read as part of the checkpoint
   section; Gate 2 starts at ~535. Suggested fix: move the section before
   Gate 1 or after all of Gate 1, or demote it to an H3.
   **Disposition:** _(pending)_
2. **[CONFIRMED, low, docs-contradiction] `docs/BACKENDS.md` ~217 — the cursor
   paragraph still says project `default_backend: "cursor"` fails fast with exit
   127**, false now for `list`, `status`, `validate`. `RUNBOOK.md` ~3599 and
   `BACKENDS.md` ~100 are similarly unqualified. Suggested fix: qualify or
   point at the shared paragraph.
   **Disposition:** _(pending)_
3. **[PLAUSIBLE, low, altitude/consistency] `plan_tool/cli/app.py` ~628 — the
   hardcoded `{"list","status","validate"}` omits `root`**, another handler
   `inspect.py` documents as never calling a backend; `plan-tool root` still
   exits 127 with a missing project-default binary. The set is also a second
   source of truth. Suggested fix: add `root`, record `root` as a deliberate
   exclusion with its reason, or derive the set from the inspection group.
   **Disposition:** _(pending)_
4. **[CONFIRMED, low, test-hygiene] `tests/cli/test_app.py` ~330 — the
   rewritten parametrized test has `expected` always 0**, leaving a dead `127`
   branch, an unused `EXEC_NOT_FOUND_EXIT` import, and rows duplicating
   `test_only_project_defaults_skip_missing_binary_for_inspection_commands`.
   The unique row is `codex` + `--model claude-sonnet-4-5` (model-only Claude
   stays lazy). Suggested fix: drop `expected`, assert `== 0`, keep and name
   the model-inference row.
   **Disposition:** _(pending)_
5. **[PLAUSIBLE, low, guidance] `DIRECTIVES.md` ~279 — the omit-flags rule keys
   on `backends.json` existing, not on what it configures.** A file that only
   overrides one binary path leaves `create`/`roadmap` on the provider default
   instead of the recommended strongest tier. Pass 5 chose file-existence
   deliberately; the question is whether to record the residual case. Suggested
   fix: key the rule on `default_backend` or a command model, or document the
   limitation.
   **Disposition:** _(pending)_

### Convergence status

Five passes before pass 6 (pass 6 above awaits dispositions; the loop is not
converged — finding 1 is material). Passes 2–4 re-seeded on the per-flag selection paragraph, which was
removed; pass 5 then found its replacement ("always pass explicit flags")
overrode project configuration, contradicting the plan's requirement that
skill-driven invocations defer to it. The guidance is now one file-existence
rule (2026-11-12): with `.plan-tool/backends.json`, omit `--backend` and
`--model`; without it, pass the recommendations. The plan body and step 4
detail already say this and need no edit. Deterministic commands take neither
flag; `996afd895` exempts those commands from project-default eager preflight. Pass 1's material findings
(docstrings, case normalization) have not recurred. A sixth pass over the
file-existence rule has not run.


## Follow-up #526 — project-default inspection preflight

`996afd895` keeps `list`, `status`, and `validate` usable without the
project-default backend installed. Other commands and explicit backend/model
selection retain their existing preflight behavior. The backlog entry is
resolved and removed.

Verification (2026-11-13): affected CLI tests pass twice (116 tests); the full
suite passes (14,850 passed, 67 skipped). Removing the exception makes all six
project-default inspection cases fail while the other 18 matrix cases pass.
Two session self-review passes examine correctness and completeness with no
additional findings; no independent reviewer or `/code-review` invocation is
part of this follow-up. The change stays within #526's scope and uses a direct
exception rather than a command registry.
