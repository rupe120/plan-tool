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
   without the CLI** (`cli/app.py`). Disposition: **open — owner decision.**
   Current behavior follows the documented contract: `docs/BACKENDS.md`
   § prerequisites lists "project default" beside flag and environment as
   fail-fast sources. The cost: a committed `default_backend` makes `list`,
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
6. **Open preflight decision has no tracked home.** **Open — owner decision**;
   file in `BACKLOG.md` only if the owner keeps the current behavior.
7. **Test coupled to full preflight wording.** **Fixed** — asserts only the
   executable-not-found fragment.

### Convergence status

Four passes. Passes 2–4 re-seeded on the DIRECTIVES selection paragraph with a
different symptom each round, which is the non-converging signal for that
region: the policy is too intricate to state in one paragraph. Application is
complete; the loop stops here and the owner decides between keeping this
wording, collapsing it to one rule (for example "always pass explicit flags
unless the user says otherwise"), or carving the guidance into its own change.
Pass 1's material findings (docstrings, case normalization) have not recurred.
