# Prompt-budget model window — code review ledger

| Field | Value |
| --- | --- |
| Change | BACKLOG #470: the pre-send prompt-budget advisory measures a prompt against the selected model's context window (Codex from its local catalog, Claude from a window an earlier call reported) instead of a fixed 200,000 tokens |
| Branch | `fix/prompt-budget-model-window` |
| Review range | pass 1: `0de1c91d..82e25576` (code `bdd899d9`; backlog status `82e25576`) |
| Checks run | Full suite `uv run pytest tests/ -q -n auto`: 13,702 passed, 67 skipped |
| Reviewer | headless `claude -p` with `CLAUDE_CONFIG_DIR=$HOME/.claude`, report-only, `high` effort (`.tmp/prompt-budget-model-window-code-review-N.stream.log`) |
| Disposition | pass 1 triaged (8 fixed, 1 declined); pass 2 triaged (9 fixed, 1 fixed in part); pass 3 triaged (8 fixed); pass 4 triaged (6 fixed); pass 5 triaged (5 fixed, 1 in part, 1 declined); pass 6 triaged (9 fixed, 1 declined); pass 7 triaged (6 fixed, 1 in part); converged (passes 6 and 7 against logic head `2916d970b`)  |

## Settled decisions (hand to each reviewer)

- The advisory stays advisory: nothing in this change adds a refusal, changes an exit code, or reads the
  network. The one existing refusal that uses a budget verdict (a selected run-reconcile prompt, `launcher.run_step`)
  passes `observed=False`, so only the Codex catalog, a file, can change its verdict, never a window learned
  mid-run. `prompt_budget.py` stays a leaf whose only first-party import is `plan_tool.style`
  (`tests/test_prompt_budget.py::test_leaf_imports_are_cycle_free` pins that), so the window is resolved by
  the callers through `plan_tool/context_window.py`.
- Window sources are local only. Codex: the usable share (`context_window` × `effective_context_window_percent`)
  of the model's entry in `$CODEX_HOME/models_cache.json` (default `~/.codex`), the model coming from the
  backend's resolved model or `config.toml`'s top-level `model`. Claude: no pre-call source exists, so the
  window is learned from the result envelope's `modelUsage[*].contextWindow` of an earlier call in the same
  process; the first call of a process uses the default. `model_specs`' network catalog is deliberately not used.
- `observe_context_window` / `observed_context_window` live in `backend.py` (a stdlib-only leaf), because
  `backend_runner.py`'s documented first-party imports are exactly `backend` and `run_log`.
- A window observed with no model selected is stored under the empty model key, so a default-model `claude -p`
  run benefits; a model-specific key is never borrowed by a different model.
- `PromptBudget.window_defaulted` and the `(default)` summary marker are in scope: BACKLOG #470's Outcome says
  the advisory must say when the default was used. The telemetry record's keys are unchanged.
- Eleven call sites pass `active_context_window()` (`shell.py` 1, `review.py` 3, `create.py` 1, `detail.py` 3,
  `launcher.py` 3; the refusal gate passes `observed=False`). `tests/test_context_window.py::
  test_every_budget_call_site_resolves_the_window_and_only_the_refusal_gate_excludes_observed` pins the exact
  per-module counts by AST.
- Deliberately not in this change: exact token counting, per-project window overrides, turning the advisory into
  a gate, changing `BYTES_PER_TOKEN` (3.5, which is more conservative than the measured 4.13 on Codex), and any
  roadmap ceiling work.

## Review pass 1 — /code-review (high, headless), 2026-10-09

Scope: `0de1c91d..82e25576`. The reviewer returned its report as the final message instead of writing `.tmp/prompt-budget-model-window-code-review-1.md` (it cited a standing instruction to return findings directly), so the text below is that returned report, copied from the stream log's `result` event (`.tmp/prompt-budget-model-window-code-review-1.result.md`). It could not list `~/.codex` or run a `python -I` probe; its findings rest on code reading, and each fix below was checked by mutation in the driving session. Nine findings; two are real defects (1, 2), none Critical.

### Method and result (reviewer's text)

I did not write `.tmp/prompt-budget-model-window-code-review-1.md`: the standing instruction for this agent is to return findings directly rather than write report files, so everything is below.

**Method.** Read the full diff `0de1c91d..82e25576`, the handoff ledger, `context_window.py`, the new pump-thread code in `backend_runner.py`, all call sites, `tests/test_context_window.py` and the conftest fixture. Two probes were denied: listing `~/.codex` was blocked (outside the allowed directory), and a `python -I` probe with `CODEX_HOME` set was refused, so the Codex catalog shape and the `TypeError` finding below rest on code reading only. Checked and found sound: the pump thread's contextvar copy keeps the scoped backend visible, `claude_invoke` takes its backend from `get_active_backend()` so the backstop and the call agree, telemetry records the measured window, per-test `HOME` pinning keeps the real `~/.codex` out of the suite, and no budget call site omits `context_window` (grep and the AST test agree).

### Findings

#### 1. `plan_tool/launcher.py:1711`

`plan_tool/launcher.py:1711`: The run-reconcile refusal gate (`reject_high_selected_reconcile_budget`) now takes its verdict from `active_context_window()`, so whether a send is refused depends on process history and a machine-local file; the changelog, ARCHITECTURE paragraph and ledger all say the budget "refuses nothing".

   Failure scenario: `reconcile --select` loops over several steps in one process (cli/reconcile.py:1670). Step 1's prompt of about 605 KB is measured against the 200,000 default (no call has run yet), so it is `high` and raises LauncherError('prompt budget is high'). Because the refusal happens before any call, the window is never learned and the process stays on the default. In a process where an earlier step's call already observed 1,000,000, the identical prompt is `ok` and proceeds. On Codex, an edited or stale `~/.codex/models_cache.json` flips the same refusal. The refusal text does not name the window used. `changelog.d/prompt-budget-model-window.md` ('still refuses nothing') and the handoff's 'nothing in this change refuses a send' are false for this gate. No test pins the gate's behavior under a known window.

- **Disposition:** fixed in `bb35fe3b`. `launcher.run_step`'s run-reconcile refusal gate calls `active_context_window(observed=False)`: only the Codex catalog, a file, can change its verdict, never a window learned mid-run. The changelog, `docs/ARCHITECTURE.md`, BACKLOG #470 and this ledger's settled decisions no longer say the budget "refuses nothing". `test_selected_reconcile_refusal_gate_uses_only_deterministic_window_sources` pins both lanes and fails when the gate takes the observed window (checked by mutation).

#### 2. `plan_tool/context_window.py:64`

`plan_tool/context_window.py:64`: `_codex_window` claims 'never an error' but a catalog whose `models` is null or not a list raises an uncaught TypeError (only OSError, ValueError, AttributeError are caught); two callers are not inside a try block.

   Failure scenario: `models_cache.json` contains `{"models": null}` or `{"models": 5}`. `catalog.get("models", [])` returns None or 5, and creating the generator expression for `next(...)` calls `iter(None)`, which raises TypeError. In launcher.py `run_step`, the dry-run branch at line 1695 and the reconcile gate at line 1711 call `active_context_window()` outside any try, so the run step crashes with a traceback from an advisory-only lookup. The new tests cover 'cache-is-a-list' but not a non-list `models` value. `Path.home()` raising RuntimeError, or RecursionError on pathologically nested JSON, is likewise uncaught.

- **Disposition:** fixed in `bb35fe3b`. `_codex_window` and `active_context_window` catch `Exception` and return `None`, including an unresolvable home. New tests cover `models` as null, a number, a string, a dict and a list of non-entries, a failing `Path.home`, and a failing `get_active_backend`; narrowing the catch turns them red (checked by mutation).

#### 3. `plan_tool/backend.py:959`

`plan_tool/backend.py:959`: `_reported_context_window` takes the largest `contextWindow` across every `modelUsage` entry, but the result is then stored under the selected model's key; the window of an auxiliary or other model can be attributed to the selected one.

   Failure scenario: A call selects `--model claude-opus-5-5` (200,000 window) and its result envelope also lists another model entry with a 1,000,000 window. `max()` returns 1,000,000, which is stored under ('claude', 'claude-opus-5-5'). Later prompts of about 600 KB are then measured as `ok` against a window the selected model does not have, silently suppressing a valid `warn`/`high`. Preferring the entry whose key equals `resolved_model` (falling back to max only when none is selected) avoids this.

- **Disposition:** fixed in `bb35fe3b`. `_reported_context_window` takes the window of the `modelUsage` entry with the most tokens (ties go to the larger window), so an auxiliary model's window is not attributed to the selected one. `test_the_reported_window_is_the_one_of_the_model_that_did_the_work` covers a light 1M entry beside a heavy 200K one and the reverse.

#### 4. `plan_tool/review.py:9159`

`plan_tool/review.py:9159`: `audit_base_level` is measured once before the first call, against the default window, and then gates every later pass; a spurious `high` from the default window permanently disables the growth re-arm and keeps the generic backstop suppressed even after the real window is known.

   Failure scenario: First `plan-tool completeness-audit` in a process with a 605 KB base prompt on Claude 1M: the base is measured against 200,000, the level is `high`, and `audit_base_level == 'high'` is recorded. After pass 1 the window 1,000,000 is observed. For passes 2 to N the `audit_base_level != 'high'` guard is false, so the growth check at line 9159 is skipped, and `suppress_prompt_budget_backstop(active=pass_covered)` stays active. If carried findings later push the prompt past the real window, no advisory fires on any pass.

- **Disposition:** fixed in `bb35fe3b`. The growth re-arm in `audit_plan_until_stable` re-measures the base against `active_context_window()` every pass instead of keeping the first verdict. `test_a_base_that_read_high_against_the_default_window_still_rearms_once_the_window_is_known` fails on the previous code (0 backstop warnings instead of 1, checked by running it against the earlier `review.py`). The older re-arm test's index assertion became `max(sized) > sized[0]` because the base is now measured on every pass.

#### 5. `plan_tool/context_window.py:46`

`plan_tool/context_window.py:46`: The Codex catalog is read and JSON-parsed on every `active_context_window()` call with no memoization, and the models cache embeds each model's full instructions, so it can be large.

   Failure scenario: `run_step` calls `active_context_window()` up to three times per step (lines 1695, 1711, 1742), `claude_invoke` calls it again for the backstop on every invoke, and `detail` adds one or two more per step. A 40-step detail or run on the Codex lane parses the same unchanged multi-hundred-KB file well over a hundred times. A small cache keyed on `(path, st_mtime_ns)` removes the repeated I/O.

- **Disposition:** fixed in `bb35fe3b`. `_codex_catalog` memoizes the parsed per-slug windows keyed on the cache file's path, `st_mtime_ns` and size; `test_the_codex_catalog_is_parsed_once_per_file_version` counts parses across five lookups and a file change.

#### 6. `plan_tool/context_window.py:56`

`plan_tool/context_window.py:56`: The Codex model is taken from `backend.resolved_model` or the top-level `model` in `config.toml` only, and a relative `$CODEX_HOME` is resolved against the process cwd, which can diverge from the model and home the spawned Codex actually uses.

   Failure scenario: `config.toml` sets `profile = "big"` with `[profiles.big] model = "gpt-6.1-sol"` and a top-level `model = "small-model"`, or the project's `extra_batch_argv` carries `-c model=...`. Codex runs the profile or override model, but the advisory measures against the top-level model's window and shows it as a known (non-'(default)') window. A relative `CODEX_HOME` is read relative to the process cwd, while Codex is spawned with `cwd=get_active_spawn_cwd()` and so resolves it elsewhere.

- **Disposition:** declined as a code change. A Codex profile, a `-c model=` entry in `extra_batch_argv`, and a relative `CODEX_HOME` resolved against another working directory are not seen; the result is a window for the top-level model, which is the same class of error the default window already made. `docs/ARCHITECTURE.md` now states the limit in the paragraph that describes the lookup.

#### 7. `docs/ARCHITECTURE.md:127`

`docs/ARCHITECTURE.md:127`: The new paragraph sits under the '## Rate-limit recovery loop' heading although it describes the prompt-budget leaf, is absent from the Module map, and says the model comes from `--model` or `config.toml` when the code uses `resolved_model`.

   Failure scenario: A reader looking for the prompt-budget window finds it only inside the rate-limit section. `context_window.py` and `prompt_budget.py` have no Module-map row. The text omits that `resolved_model` also comes from the project override and the manifest `default_model`, so a user with `default_model` set in the Codex manifest and no `--model` is told the wrong source. The paragraph also says the observed-window lane is for any call of the process while only the claude-parser lane ever populates it, and says nothing of the refusal gate (see the first finding).

- **Disposition:** fixed in `bb35fe3b`. The paragraph moved under "Backend abstraction" beside the `backend_runner.py` paragraph, `prompt_budget.py` and `context_window.py` have a Module-map row, the model source reads `resolved_model` (flag, project override or manifest default) before `config.toml`, and the gate behavior and the first-call-uses-default limit are stated.

#### 8. `tests/test_context_window.py:237`

`tests/test_context_window.py:237`: The call-site AST guard passes any `context_window=` value that is not the literal `None`, and `test_an_observed_window_outranks_the_codex_catalog` pins an observed-Codex-window path that no production parser can populate.

   Failure scenario: A site changed to `context_window=200_000`, `context_window=default_window`, or `context_window=None if x else y` stays green, so the guard does not prove the selected-model window is used. Only the Claude parser sets `ClaudeRunStats.context_window`, so the Codex-observed branch is dead in production while a test asserts its precedence. Nothing exercises the launcher refusal gate or the review per-pass re-measure under a known window, so a regression at either would stay green.

- **Disposition:** fixed in `bb35fe3b`. The call-site guard now requires the keyword to be a call to `active_context_window`, so a literal, a variable or a conditional fails it. The refusal gate and the audit re-measure now have tests under a known window. `test_an_observed_window_outranks_the_codex_catalog` is kept: it pins the registry's precedence rule, which is backend-agnostic, even though only the Claude parser populates it today.

#### 9. `plan_tool/backend_runner.py:623`

`plan_tool/backend_runner.py:623`: The new `observe_context_window` bookkeeping runs in the stdout pump thread outside any try/except, contrary to the surrounding convention that nothing in the pump may raise.

   Failure scenario: A parser that returns a non-`ClaudeRunStats` stats object (a third-party or test double) makes `parsed.stats.context_window` raise AttributeError. The exception escapes `_pump_stdout`, the thread dies, and the stdout pipe stops draining. The call then hangs until the silence-kill ladder fires, which is exactly the wedge the comments at lines 565-567 warn about. An advisory-only feature should not be able to take the pump down.

- **Disposition:** fixed in `bb35fe3b`. The bookkeeping in the pump is inside `try/except Exception`. `test_a_failing_window_bookkeeping_cannot_take_the_pump_down` installs a `threading.excepthook` collector and fails if the thread dies; the first version of this test passed against the unguarded code and was strengthened for that reason.

## Review pass 2 — /code-review (high, headless), 2026-10-09

Scope: `0de1c91d..13b57e00`, the whole change with attention on the pass-1 fixes `bb35fe3b`. The reviewer wrote its report to `.tmp/prompt-budget-model-window-code-review-2.md` (stream log `.tmp/prompt-budget-model-window-code-review-2.stream.log`), copied below with headings shifted. It could not run tests (`uv run pytest` was denied), so its claims rest on code reading; each fix was checked by mutation in the driving session. Ten findings, none Critical or High; finding 1 is Medium.


#### Method

- **Scope:** `0de1c91d..13b57e00` on `fix/prompt-budget-model-window`, second independent pass, with extra attention to the pass-1 fixes (`bb35fe3b`).
- **Read:** the ledger `handoffs/2026-10-09-prompt-budget-model-window-code-review.md` (settled decisions and pass-1 dispositions honored, not re-reported); the full code diff (`context_window.py`, `backend.py`, `backend_runner.py`, `prompt_budget.py`, `launcher.py`, `review.py`, `shell.py`, `create.py`, `detail.py`); `tests/test_context_window.py`, the launcher and review test additions and the conftest fixture; the enclosing functions at each call site (`run_step`, `audit_plan_until_stable`, `_author_step_detail`, `claude_invoke`, `run_streaming_once`); the BACKLOG #470/#469 entries, RUNBOOK, ARCHITECTURE and DATA_CONTRACT passages that describe the advisory.
- **Searches:** by identifier (`estimate_prompt_budget`, `maybe_warn_prompt_budget`, `active_context_window`, `DEFAULT_CONTEXT_WINDOW`, `reject_high_selected_reconcile_budget`, `.level`, `headroom_ratio`, `suppress_prompt_budget_backstop`, `observe_context_window`) and by vocabulary (`refuses nothing`, `advisory only`, `never blocks`, `200K`, `oversize`, `too large`, `_MAX_*BYTES`, `context overflow`, `context window`).
- **Permission denials:** `uv run pytest ...` (with and without `set -o pipefail`) was denied, so no test was executed; every claim below rests on code reading. No source, test or doc file was edited.

### Answers to the specific questions

- **Is the `observed=False` gate the only refusal that depends on a budget verdict?** Yes. `launcher.py:1710-1721` is the only site where `.level`/`headroom_ratio` decides refuse/skip/truncate/retry. Every other consumer (shell backstop, create, detail, review base advisory, review growth re-arm) only warns, records telemetry, or toggles `suppress_prompt_budget_backstop` (which only chooses which warning prints). No `_MAX_*BYTES`/ceiling in the tree reads a budget level. `claude_errors.CONTEXT_OVERFLOW` is output-pattern classification, not a budget read.
- **Dominant-model choice:** see finding 3.
- **Catalog memo:** two homes cannot realistically thrash it (one process has one `CODEX_HOME`), and a deleted or unreadable file never serves a stale entry (the `stat` raises first). It does have a thread race (finding 2) and a same-size same-tick staleness window (finding 1).
- **Per-pass re-measure in review.py:** logic is sound for the growing-window case. See finding 5 for what its test does not pin.
- **Thread safety:** `_observed_context_windows` uses single dict get/set (atomic under the GIL, last write wins, benign). The memo is not safe (finding 2).
- **Would a test stay green if the feature were reverted?** The wholesale revert is caught (module deletion, AST guard, launcher gate test). Partial reversions are not (finding 5).


### 1. Memo test depends on mtime resolution; it is flaky on Linux filesystems

- **Category:** test-reliability
- **Severity:** Medium
- **File:line:** `tests/test_context_window.py:134-157`, `plan_tool/context_window.py:68-71`
- **Failure scenario:** `test_the_codex_catalog_is_parsed_once_per_file_version` rewrites `models_cache.json` after five lookups and expects `95_000`. The two JSON bodies are the same length (`"context_window": 272000` vs `100000`, both six digits), so the memo key `(path, st_mtime_ns, st_size)` can differ only by `st_mtime_ns`. APFS has nanosecond timestamps, so it passes on the developer machine. ext4/overlayfs/tmpfs stamp files from the coarse kernel clock (1-4 ms ticks), and the rewrite happens microseconds after the first write, so the key is identical, the memo serves `258_400`, and the assertion fails intermittently on Linux CI. The same gap is a production edge: a refreshed cache of identical size inside one timestamp tick (or on a 1-2 s granularity filesystem) keeps the old window for the life of the process.
- **Suggested fix:** make the test's second body differ in size (add a field or a longer slug) so it pins the size component deterministically, and add a separate case that bumps only the mtime with `os.utime(path, ns=(...))` to pin the mtime component without relying on the clock. Optionally add `st_ino` to the key (atomic-rename refreshes change it).

- **Disposition:** fixed in `ba9f8896`. The memo key is `(mtime_ns, size, inode)`. The old test now rewrites to a different size, a second test keeps the size and sets the mtime with `os.utime`, so each component is pinned without the clock. The inode covers a refresh by atomic rename inside one timestamp tick.


### 2. `_codex_catalog` memo is not thread-safe; a concurrent miss can raise `KeyError` and silently report "unknown"

- **Category:** concurrency
- **Severity:** Low-Medium
- **File:line:** `plan_tool/context_window.py:70-85`
- **Failure scenario:** `detail --jobs N` runs `_author_step_detail` (which calls `active_context_window()`) in a `ThreadPoolExecutor`. On a cold memo every worker misses at once (the `json.loads` of a large cache makes the miss window long). Thread A does `clear()` then `memo[key] = windows`; thread B does its own `clear()` before A executes `return _CODEX_CATALOG_MEMO[key]`; A's lookup raises `KeyError`, which `_codex_window`'s `except Exception` converts to `None`, so that step's advisory is measured and labeled against the 200,000 default (`(default)`, and recorded in telemetry as `context_window=200000`) although the catalog was readable. The window is narrow but the failure is silent, and it also means N threads parse the same multi-hundred-KB file (stampede).
- **Suggested fix:** return the locally built `windows` dict instead of re-indexing the shared memo, and replace the `clear()`+assign pair with one atomic swap (for example a module-level `(key, windows)` tuple that is rebound, or a `threading.Lock` around the miss path).

- **Disposition:** fixed in `ba9f8896`. A `threading.Lock` guards the miss path with a re-check inside it, and the lookup returns the value it parsed instead of re-indexing the shared memo, so a concurrent miss neither raises `KeyError` nor stampedes. `test_concurrent_cold_lookups_all_get_the_catalog_window_and_parse_once` runs eight threads on a barrier and requires one parse; removing the lock turns it red on every run (checked by mutation).


### 3. Dominant-model rule can still attribute a different model's window to the selected model, and ties pick the larger window

- **Category:** correctness
- **Severity:** Low-Medium
- **File:line:** `plan_tool/backend.py:959-982`, `plan_tool/backend_runner.py:623-631`
- **Failure scenario:** the registry key is the selected `resolved_model`, but the stored value is the window of whichever `modelUsage` entry has the most tokens. (a) A call whose heavy work ran in sub-agents on another model (plan-tool `run` steps routinely use Task/Explore agents): selected model Haiku (200K) with a heavy Opus sub-agent (1M) stores 1M under Haiku's key, and later 600 KB prompts read `ok` against a window the selected model does not have, suppressing a valid `warn`/`high`. The reverse flips a 1M model to 200K. (b) The key is last-write-wins, so alternating calls (heavy-main, then heavy-subagent) oscillate the verdict between prompts of the same size. (c) When entries carry no token fields (all zero), `max(ranked)` falls to the larger window, which is exactly the pass-1 finding-3 failure, and `test_the_result_envelope_reports_the_largest_context_window` pins that tie rule.
- **Suggested fix:** the pump knows `resolved_model`. Prefer the `modelUsage` entry whose key equals (or is prefixed by) `resolved_model` when a model was selected, and use the token-dominant entry only as the fallback for the unselected-model key. Prefer the smaller window on a tie (the advisory errs toward warning).

- **Disposition:** fixed in `ba9f8896`. The stream-line parse also keeps every `(model id, window)` pair, and `reported_window_for_model` prefers the entry matching the selected model (exact, or one id containing the other, taking the smaller on several matches); the dominant entry is the fallback and serves a run with no selected model. Ties between equal-usage entries go to the smaller window. Tests cover the match table and a streamed haiku-selected result beside a heavy opus entry.


### 4. The refusal message hides that the verdict used the default window, and it can contradict the advisory beside it

- **Category:** diagnostics
- **Severity:** Low-Medium
- **File:line:** `plan_tool/launcher.py:1713-1721`
- **Failure scenario:** on Claude the gate is deliberately measured against the 200,000 default (`observed=False`) even when an earlier call in the same process reported a 1,000,000 window, so a ~600 KB selected reconcile prompt is refused with only `selected run-reconcile prompt budget is high; reduce the selected scope and retry`. The estimate, the window and the `(default)` marker (the whole point of `window_defaulted`) are not in the message, and the advisory path for the same prompt would have been silent (`ok`) or would have printed a 1,000,000-token window. An operator cannot tell that a 1M-window model was judged against 200K, or that the Codex catalog was the source. Pass-1 finding 1 raised the missing window name; its disposition fixed determinism but not the message.
- **Suggested fix:** build the message from `render_budget_summary(selected_budget, surface="selected run-reconcile")` (it already carries tokens, window, `(default)` and the block breakdown) and say the window source in one clause.

- **Disposition:** fixed in `ba9f8896`. The refusal reads `... selected scope and retry ({summary})`, where the summary is `render_budget_summary(selected_budget)`: tokens, window, `(default)` and headroom. The gate test asserts it names the window and carries `(default)` exactly on the Claude lane.


### 5. No behavioral test pins the window source at the advisory call sites; the AST guard accepts any arguments

- **Category:** test-coverage
- **Severity:** Low-Medium
- **File:line:** `tests/test_context_window.py:296-330`, `tests/test_review.py:13443-13452`
- **Failure scenario:** the guard accepts any call to `active_context_window(...)` as resolving the window. Changing the shell backstop, create, detail or launcher advisory site to `active_context_window(observed=False)` (or any other argument) keeps every test green, and nothing asserts that a learned or catalog window changes the advisory's verdict at `shell._maybe_warn_shell_prompt_budget`, `create._maybe_warn_create_budget`, the three `detail.py` sites or the launcher advisory. In the review re-arm test, `fake_estimate(total_bytes, **kwargs)` ignores `context_window`, and `active_context_window` is replaced by a lambda, so the test proves the per-pass re-measure but not which window it uses. The one gate that refuses is pinned; the nine sites that warn are pinned only by shape.
- **Suggested fix:** require the AST guard to accept `active_context_window()` with no arguments everywhere except an explicit allowlist (the gate, `observed=False`), and add one behavioral test per module that observes a window (or sets a Codex catalog) and asserts the recorded `context_window` / printed `window` in the advisory. Make `fake_estimate` assert the `context_window` it receives.

- **Disposition:** fixed in `ba9f8896`. The call-site guard pins exact per-module counts (`shell` 1, `review` 3, `create` 1, `detail` 3, `launcher` 3), requires no arguments, and allows `observed=False` only on `launcher.py`. A behavioral test shows a learned 1M window silences the shell backstop for a 500 KB prompt; the audit re-arm test's fake estimator asserts it receives the 1,000,000 window. A per-module behavioral test for `create` and each `detail` site was not added: they pass the same call and the guard pins their shape.


### 6. Doc sweep miss: "advisory only / never blocks / refuses nothing" is still stated beside a shipped refusal

- **Category:** documentation
- **Severity:** Low
- **File:line:** `RUNBOOK.md:3897`, `BACKLOG.md:12839` (the #469 Risks bullet), `BACKLOG.md:11675`
- **Failure scenario:** pass-1 finding 1 was fixed in the changelog, ARCHITECTURE, #470 and the ledger, but the same class of statement remains: RUNBOOK's prompt-budget section says it is "**advisory only** — it never blocks the call", while a selected run-reconcile prompt at `high` is refused before the backend runs. #469's Risks bullet still reads "The warning is advisory and refuses nothing" and describes the 200K assumption as current. A reader of the user-facing runbook is told a refusal cannot happen.
- **Suggested fix:** state the one exception in the RUNBOOK section (selected run-reconcile prompts are refused at `high`, judged against the Codex catalog window or the default, never a window learned mid-run), and update or remove the two BACKLOG sentences when #470 is removed.

- **Disposition:** fixed in `ba9f8896` for the RUNBOOK, which now names the selected run-reconcile refusal and its window sources. The two BACKLOG sentences sit in the #469 entry, which `origin/main` already removed in PR #59 (`6b036e8d`); they disappear when this branch takes that commit.


### 7. Stale counts and a floor that cannot detect a dropped site

- **Category:** documentation / test-coverage
- **Severity:** Low
- **File:line:** `BACKLOG.md:12921-12925` (#470 In scope), `handoffs/2026-10-09-prompt-budget-model-window-code-review.md` (Settled decisions), `tests/test_context_window.py:325`
- **Failure scenario:** #470 says "nine sites ... `review.py` 1", the ledger says "Ten call sites ... `review.py` 2". The code has eleven `context_window=active_context_window(...)` sites: shell 1, review 3 (`9077`, `9153`, `9160`), create 1, detail 3, launcher 3 (one passing `observed=False`). The guard asserts `seen >= 10`, so one site could be removed without failing it.
- **Suggested fix:** correct both counts, and pin the exact number (or enumerate `(module, count)` pairs) so a deleted site fails the test.

- **Disposition:** fixed in `ba9f8896`. BACKLOG #470 and the ledger say eleven sites with `review.py` 3, and the guard pins the exact counts so a deleted site fails.


### 8. Stale field comment and a test name that describe the superseded rule

- **Category:** documentation
- **Severity:** Low
- **File:line:** `plan_tool/backend.py:185`, `tests/test_context_window.py:195`
- **Failure scenario:** the `ClaudeRunStats.context_window` comment says "Largest `modelUsage[*].contextWindow` the result envelope reported", but pass-1's fix made it the window of the entry with the most tokens (largest only on a tie). `test_the_result_envelope_reports_the_largest_context_window` carries the same wording. A reader (or an audit) takes the stale comment as the contract and re-opens finding 3 of pass 1.
- **Suggested fix:** reword the comment to "the `contextWindow` of the `modelUsage` entry that did the most work (see `_reported_context_window`)" and rename the test to say it pins the tie rule.

- **Disposition:** fixed in `ba9f8896`. The `ClaudeRunStats.context_window` comment describes the most-work entry and points at `_reported_context_window`, and the test is renamed for the tie rule.


### 9. Repeated window resolution and an unmemoized `config.toml` parse on hot paths

- **Category:** efficiency
- **Severity:** Low
- **File:line:** `plan_tool/context_window.py:88-98`, `plan_tool/review.py:9152-9161`, `plan_tool/launcher.py:1696-1752`
- **Failure scenario:** with Codex and no model selected (`default_model=None` is the common case), every `active_context_window()` re-reads and re-parses `config.toml` (pass-1 memoized only the catalog). `run_step` resolves up to three times, `claude_invoke` once per invoke, and each audit pass resolves twice (`active_context_window()` appears in both `estimate_prompt_budget` calls). Under `detail --jobs N` this multiplies by the worker count.
- **Suggested fix:** hoist `window = active_context_window()` once per pass / per step, and memoize the parsed top-level `model` with the same `(path, mtime_ns, size)` key as the catalog.

- **Disposition:** fixed in part in `ba9f8896`: the `config.toml` model read is memoized with the catalog's mechanism. Hoisting one lookup per pass or step is declined, because the call-site guard needs `active_context_window()` inline and the memo makes a repeat a stat call.


### 10. `context_window.py` leaf claim is unpinned and `window_defaulted` duplicates the fallback logic

- **Category:** convention / simplification
- **Severity:** Low
- **File:line:** `plan_tool/context_window.py:20-22`, `plan_tool/prompt_budget.py:97-101`
- **Failure scenario:** the module docstring asserts it "adds no edge" to `shell`/`launcher` and sits below them, but unlike `prompt_budget` (`test_leaf_imports_are_cycle_free`) and `backend_runner`, no test pins its first-party imports; a later `from plan_tool.shell import ...` would create the cycle silently (CLAUDE.md: "A docstring saying 'deliberately not' is a claim to pin"). Separately, `estimate_prompt_budget` now derives `window` and `window_defaulted` through three overlapping expressions (`context_window or DEFAULT`, `context_window is None or <= 0`, then `if window <= 0`).
- **Suggested fix:** add an import-surface test for `context_window.py` (first-party imports exactly `plan_tool.backend`); compute `window_defaulted` once and derive `window` from it.

- **Disposition:** fixed in `ba9f8896`. `test_the_leaf_imports_only_the_backend_leaf` pins the module's first-party imports, and `estimate_prompt_budget` derives `window_defaulted` once and `window` from it.

### Result

No Critical or High defect found. The `observed=False` gate is the only refusal tied to a budget verdict, and the pass-1 fixes behave as dispositioned in the paths read. Material items are the Linux-flaky memo test (1), the memo race (2), the dominant-model attribution (3), the refusal message (4), and the partial-revert test gap (5); items 6-10 are documentation, count, efficiency and convention cleanups.

## Review pass 3 — /code-review (high, headless), 2026-10-09

Scope: `0de1c91d..203d575b` (the whole change at the head after the pass-2 fixes `ba9f8896`). The reviewer wrote its report to `.tmp/prompt-budget-model-window-code-review-3.md` (stream log `.tmp/prompt-budget-model-window-code-review-3.stream.log`), copied below with headings shifted. It could not run a probe (one `python3 -c` was denied), so its claims rest on code reading; each fix was checked by mutation in the driving session. Eight findings, none Critical or High; findings 1 and 2 are Low-Medium and are in the attribution rule, the site that drew a finding in all three passes (pass 1 finding 3, pass 2 finding 3, pass 3 findings 1 and 2). Each round's fix there was a heuristic with a new failure; `008a47c7b` replaces the heuristics with one rule checked against the whole case matrix instead of patching the newest cell.


### Method

- **Scope:** `0de1c91d..HEAD` (`203d575b4`) on `fix/prompt-budget-model-window`, third independent pass, concentrating on the pass-2 fixes (`ba9f8896`): the `_memoized_file` lock and re-check, `reported_window_for_model`'s containment match and tie rule, and the refusal message.
- **Read:** the ledger `handoffs/2026-10-09-prompt-budget-model-window-code-review.md` (Settled decisions and every pass-1/pass-2 disposition honoured, not re-reported); the full code diff (`context_window.py`, `backend.py`, `backend_runner.py`, `prompt_budget.py`, `launcher.py`, `review.py`, `shell.py`, `create.py`, `detail.py`); `tests/test_context_window.py` in full, the launcher and review test additions and the conftest fixture; the enclosing code of the `review.py` re-arm and the pump in `run_streaming_once`; the RUNBOOK, ARCHITECTURE, changelog and BACKLOG diffs.
- **Searches:** by identifier (`_FILE_MEMO`, `observe_context_window`, `reported_window_for_model`, `audit_base_level`, `window_defaulted`, `DEFAULT_CONTEXT_WINDOW`, `resolved_model`, `ClaudeRunStats(`) and by vocabulary (`200K`, `200,000`, `most work`, `largest`, `dominant`, `refuses`, `budget is high`).
- **Permission denials:** one ad-hoc `python3 -c` probe of `reported_window_for_model` was refused, so no code was executed; every claim below rests on code reading. No source, test or doc file was edited.

### Answers to the specific questions

- **Can a cached value for one file be served for another?** Not in practice. The key is `str(path)`, the two files the leaf reads have different names, and the version tuple includes the inode. The only theoretical route is a relative `CODEX_HOME` re-resolved after a cwd change onto a file with identical `(mtime_ns, size, ino)` on another device (finding 6).
- **Can the memo grow without bound?** No. One entry per distinct path, and a process has one `CODEX_HOME` (two paths). Stale versions are overwritten in place.
- **Can a parse failure leave a bad entry?** No. `parse` raises before the assignment, so the old entry (older version) stays and is never served because the version no longer matches. The cost is that a failure is never cached (finding 5).
- **Is the `(mtime_ns, size, inode)` comparison right where `st_ino` is 0?** Yes. A constant 0 degrades the key to the pass-1 key `(mtime_ns, size)`; it cannot cause a false mismatch. An unstable inode (some FUSE/network mounts) can only cause an extra reparse, never a stale serve. Python 3.13 on Windows fills `st_ino`.
- **Does the containment match choose a wrong window?** Yes, in two directions (findings 1 and 2).
- **What happens when the selection matches several entries?** `min(matches)` (finding 1; unpinned by any test, finding 3).
- **Does `render_budget_summary` on the gate's estimate raise or mislead?** It cannot raise (its inputs are an int-valued budget and blocks already normalised by `_normalize_blocks`). The text is truthful but unexplained (finding 7).
- **Would a test stay green if the feature were reverted?** A wholesale revert is caught (AST guard, launcher gate test, leaf import test). Two partial reversions stay green (finding 3).

### Findings


#### 1. An exact `modelUsage` match does not outrank the containment matches, and `min()` then understates the selected model's window

- **Category:** correctness
- **Severity:** Low-Medium
- **File:line:** `plan_tool/backend.py:1012-1014`
- **Failure scenario:** `matches = [w for name, w in model_windows if name == model or model in name or name in model]` collects an exact hit and every fuzzy hit in one list and returns the minimum. Selected `claude-sonnet-5-5[1m]` (1,000,000 window); the result lists `claude-sonnet-5-5[1m]` (heavy, 1,000,000) and a sub-agent or helper running the bare `claude-sonnet-5-5` (200,000). The bare id satisfies `name in model`, so both match and `min()` stores 200,000 under the selected model's key, although the exact entry says 1,000,000 and is also the dominant one. Every later prompt of that run is measured against 200,000 and warns `high` for a prompt that fits, which is the symptom #470 exists to remove. The rule's own docstring says "a match (exact, or one id containing the other) wins", but exactness is not given any precedence.
- **Related, no boundary or length guard:** a short or generic selection (`claude`, `o`, an empty `modelUsage` key via `name in model`) matches every entry, and `min()` always resolves such a false match toward the smallest window.
- **Suggested fix:** return the exact-name entry(ies) first; only when none exists fall back to the containment match, and require it to be on an id boundary (a `-` or `[` separator) rather than a raw substring.

- **Disposition:** fixed in `008a47c7b`. The containment match is gone. `reported_window_for_model` returns the entry whose id equals the selection exactly, else the smallest window in the envelope. The parametrized matrix test has the `claude-sonnet-5-5[1m]` / `claude-sonnet-5-5` pair in both directions and a short name (`claude`); restoring the containment match turns it red (checked by mutation).


#### 2. A selected model with no matching entry still adopts the dominant entry's window, which re-opens pass-2 finding 3 for every non-substring alias

- **Category:** correctness
- **Severity:** Low-Medium
- **File:line:** `plan_tool/backend.py:1015`, `plan_tool/backend_runner.py:628-634`
- **Failure scenario:** the fallback `return dominant` runs whenever a model was selected but no entry matched. Aliases that are not a substring of the reported id never match: `sonnet[1m]` (`"sonnet[1m]"` is not a substring of `claude-sonnet-5-5[1m]`, because the version sits between the family and the suffix), `opusplan`, `default`. For those, the run's heaviest entry decides, which is exactly the sub-agent attribution pass-2 finding 3 set out to remove: a Haiku-heavy Task sub-agent run under `--model sonnet[1m]` stores 200,000 under the 1M model's key (the reverse flips a 200K model to 1M and silences a real `high`). The `[1m]` alias is the case the feature most cares about, and it is the one that cannot match.
- **Suggested fix:** when a model is selected and nothing matches, either store nothing (keep the default, which `(default)` already labels honestly) or normalise the alias before matching (strip a `[1m]` suffix, compare the family token against the id). The dominant fallback should serve only the unselected-model key (`""`).

- **Disposition:** fixed in `008a47c7b`. There is no dominant-entry fallback for a selected model any more. An alias (`sonnet[1m]`, `opusplan`) takes the smallest window in the envelope: a single-entry envelope serves it, a mixed one errs toward warning. The matrix covers both.


#### 3. No test pins the several-matches rule or exact-over-fuzzy precedence, so `min()` could become `max()` or `matches[0]` unnoticed

- **Category:** test-coverage
- **Severity:** Low-Medium
- **File:line:** `tests/test_context_window.py:291-306`
- **Failure scenario:** `_WINDOWS` is `claude-haiku-4-5` and `claude-opus-5-5`. Every row of the table (`claude-haiku-4-5`, `haiku`, `claude-opus-5-5[1m]`) matches exactly one entry, and the other two rows match none. The docstring, the ledger ("taking the smaller on several matches") and ARCHITECTURE all assert a several-match rule that no test exercises: changing `min(matches)` to `max(matches)`, `matches[0]` or `sorted(matches)[-1]` keeps the suite green. The same table cannot tell an exact match from a containment match, so finding 1 is also invisible to it. The second partial reversion that stays green is the `reported_window_for_model` fallback condition (`if model:`): `None` and an unmatched model both return the dominant entry, and the expected value `777` is the same for both.
- **Suggested fix:** add rows with two matching entries (`("claude-sonnet-5-5", ...)` plus `("claude-sonnet-5-5[1m]", ...)`) and assert the chosen window and which of the two is preferred; assert the unmatched-selected case separately from `None` once finding 2 is decided.

- **Disposition:** fixed in `008a47c7b`. The matrix test exercises exact-over-lookalike in both directions, alias with one and with several entries, a short name, and no selected model with one and with several entries; two streamed-result tests cover the selected-exact and unselected-mixed cases.


#### 4. ARCHITECTURE and a code comment still describe the superseded dominant-entry rule

- **Category:** documentation
- **Severity:** Low
- **File:line:** `docs/ARCHITECTURE.md:116`, `plan_tool/backend.py:185-187`
- **Failure scenario:** ARCHITECTURE says the registry is "written by `backend_runner` from the Claude result envelope's `modelUsage`, using the entry of the model that did most of the work". After `ba9f8896` the stored window is the selected model's own matching entry, with the most-work entry only the fallback (and the smaller window on several matches). The `ClaudeRunStats.context_window` comment is accurate for the field, but the registry's behaviour is described nowhere except the `reported_window_for_model` docstring. A reader (or an audit) takes the ARCHITECTURE sentence as the contract and re-raises pass-1 finding 3 / pass-2 finding 3.
- **Suggested fix:** reword the ARCHITECTURE clause to "the entry matching the selected model, else the entry that did the most work", and name the smaller-window tie/multi-match rule once.

- **Disposition:** fixed in `008a47c7b`. `docs/ARCHITECTURE.md` says "the entry whose id equals the selected model, else the smallest window in the envelope, so no alias is guessed and a mixed result errs toward warning", and the `ClaudeRunStats.context_window` comment says smallest.


#### 5. A parse failure is never cached, so a persistently unreadable catalog is re-read and re-parsed on every lookup, under the global lock

- **Category:** efficiency
- **Severity:** Low
- **File:line:** `plan_tool/context_window.py:46-52`
- **Failure scenario:** `parse(path)` raises before the assignment, so nothing is stored for a malformed or wrong-shaped `models_cache.json` (a truncated refresh, a catalog whose top level is a list). Each of the roughly three-to-six lookups per `run`/`detail` step then re-reads and re-parses the whole multi-hundred-KB file, and with `detail --jobs N` the N workers serialise through the single module-wide `_FILE_MEMO_LOCK` while doing so; the lock is also shared by `config.toml`, whose reads are tiny. A second, harmless effect of computing `version` before taking the lock: a thread that waited long writes `(older version, current content)` over a newer entry, costing one extra parse on the next call.
- **Suggested fix:** cache the failure as `(version, None)`-style negative entries keyed on the same version so a bad file is parsed once per version, and take `stat` inside the lock (or per-path locks) so the stored tag is never older than the entry it replaces.

- **Disposition:** fixed in `008a47c7b`. A parse failure is remembered as unreadable for that file version (`test_an_unreadable_catalog_is_parsed_once_per_version_not_on_every_lookup`; removing it turns the test red), and the version is read inside the lock, so a stored tag is never older than the entry it replaces.


#### 6. The memo key omits the device and relies on the path string, and the test conftest isolates the sibling registry but not the memo

- **Category:** robustness / test-hygiene
- **Severity:** Low
- **File:line:** `plan_tool/context_window.py:42-43`, `tests/conftest.py:226-234`
- **Failure scenario:** `version = (st_mtime_ns, st_size, st_ino)` is not unique across filesystems, and the key is `str(path)`: a relative `CODEX_HOME` re-resolved after the process cwd changes onto a file on another device with the same size, mtime and inode serves the first file's windows. Practically unreachable, but adding `st_dev` is one more tuple element. Separately, `_isolate_context_window_sources` resets `_observed_context_windows` per test but leaves `_FILE_MEMO` process-global; the suite stays green today only because each test's `HOME`/`CODEX_HOME` is a unique tmp path (`tests/conftest.py:187` hashes the node id). A test that reuses a fixed relative home and rewrites a same-size file inside one timestamp tick would be served the previous test's value.
- **Suggested fix:** add `st_dev` to the version tuple and `monkeypatch.setattr("plan_tool.context_window._FILE_MEMO", {})` in the same autouse fixture.

- **Disposition:** fixed in `008a47c7b`. The version tuple is `(mtime_ns, size, inode, device)`, and the autouse fixture in `tests/conftest.py` resets `_FILE_MEMO` beside the observed windows.


#### 7. The refusal message embeds a summary that repeats itself and never says why a learned window was ignored

- **Category:** diagnostics
- **Severity:** Low
- **File:line:** `plan_tool/launcher.py:1717-1720`
- **Failure scenario:** the message renders as `selected run-reconcile prompt budget is high; reduce the selected scope and retry (prompt budget high: ~172,000 tokens vs 200,000 window (default) (14% headroom) — top blocks: …)`. It repeats "prompt budget ... high", carries double parentheses, and (on the Claude lane, where the same process may have printed advisories against a learned 1,000,000 window) states `(default)` without saying that the gate deliberately ignores a window learned earlier in the run. An operator who just saw the advisory report `ok` for a similar prompt still cannot tell why this one is refused. `render_budget_summary` itself cannot raise here (the budget's blocks are already normalised), so this is wording only.
- **Suggested fix:** build the message from the budget fields directly (`~N tokens vs W window[ (default)]`) and add one clause: "judged against the model catalog window or the default, not a window learned during this run".

- **Disposition:** fixed in `008a47c7b`. The message is built from the budget fields: `... retry (~N tokens vs W window[ (default)], judged against the model catalog window or the default, not a window learned during this run)`, with no repeated phrase and no nested parentheses.


#### 8. The audit growth re-arm no longer knows whether the base was ever warned, so a window learned to be smaller than the default suppresses both warnings

- **Category:** correctness
- **Severity:** Low
- **File:line:** `plan_tool/review.py:9147-9161`
- **Failure scenario:** the pass-1 fix replaced the recorded `audit_base_level` ("was the base advisory `high` and therefore already printed") with a re-measure each pass, and still uses "base reads `high` now" as the reason to skip the re-arm. That is only equivalent while the window can grow. Base prompt about 150K tokens, advisory at pass 1 against the 200,000 default: `ok`, nothing printed, `audit_budget_covered = True`, backstop suppressed for every pass. A later call reports a window below the default (a smaller model, or Codex with a catalog window learned only through a profile switch); the base now reads `high`, the `!= "high"` guard is false, the re-arm is skipped, and `suppress_prompt_budget_backstop(active=True)` remains: neither the base advisory nor the backstop ever warns about a prompt that is over the real window.
- **Suggested fix:** record at advisory time whether a `high` was actually printed and against which window; skip the re-arm only when a `high` was printed against the current window, and otherwise let a now-`high` base (not only a grown pass) drop the suppression once.

- **Disposition:** fixed in `008a47c7b`. The audit records at advisory time whether a `high` was printed (`audit_base_warned_high`); a base that is `high` now and was never warned drops the suppression once. `test_a_base_that_never_warned_but_reads_high_against_a_smaller_learned_window_rearms_at_once` covers it and fails when the check is disabled (checked by mutation).

### Result

No Critical or High defect. The pass-2 fixes behave as dispositioned for the memo (the lock, the re-check, the returned-value path and the version comparison are sound) and the refusal gate. The open items are the window-attribution rule in `reported_window_for_model` (findings 1 and 2, the only ones that can put a wrong window on a selected model), its missing tests (3), documentation drift (4) and four Low robustness, efficiency and diagnostics items (5 to 8).

Areas checked and found sound: the double-checked lock (a concurrent miss returns its own parsed value; a stale-tag overwrite costs one reparse and is never wrong); memo growth (bounded by distinct paths); failure handling (no entry written on a raise); `st_ino == 0` (degrades to the pass-1 key); the tie rule `(tokens, -window)` (smaller window wins on equal tokens); `observed=False` plumbing for Codex and Claude; pump-thread contextvar visibility and the `try/except` around the bookkeeping; `ClaudeRunStats` field additions (every construction site uses keywords, `replace()` preserves the new fields, no `asdict` over stats); the eleven call sites (AST guard exact counts); the review re-arm when the window grows (the common case); `window_defaulted` derivation; the leaf import surface.

## Review pass 4 — /code-review (high, headless), 2026-10-09

Scope: `0de1c91d..0c06447a` (the whole change at the head after the pass-3 fixes `008a47c7b`). The reviewer wrote its report to `.tmp/prompt-budget-model-window-code-review-4.md` (stream log `.tmp/prompt-budget-model-window-code-review-4.stream.log`), copied below with headings shifted. It could not run tests (four commands were denied), so its claims rest on code reading; each fix was checked by mutation in the driving session. Six findings, none Critical or High. The window-attribution rule held against a constructed case matrix (no input puts a larger window on a model that lacks it or silences a warning that should fire), so the stop condition set after pass 3 did not trigger.


### Method

- **Scope:** `0de1c91d..HEAD` (`0c06447a1`) on `fix/prompt-budget-model-window`, fourth independent pass against the head after `008a47c7b`.
- **Read:** the ledger `handoffs/2026-10-09-prompt-budget-model-window-code-review.md` (Settled decisions and every pass 1 to 3 disposition honoured, not re-reported, including the declined Codex profile / `-c model=` / relative `CODEX_HOME` limits and the declined per-pass hoisting); the whole code diff (`context_window.py`, `backend.py`, `backend_runner.py`, `prompt_budget.py`, `launcher.py`, `review.py`, `shell.py`, `create.py`, `detail.py`); `tests/test_context_window.py` in full, the launcher and review test additions and the conftest fixture; the enclosing `run_step`, `audit_plan_until_stable` pass loop, the pump in `run_streaming_once` (including the `copy_context` thread start), `_author_step_detail`'s measurement and `build_effective_backend` / `_select_effective_backend`; RUNBOOK, ARCHITECTURE, DATA_CONTRACT (prompt-budget telemetry keys), changelog and BACKLOG diffs.
- **Searches:** by identifier (`estimate_prompt_budget`, `maybe_warn_prompt_budget`, `active_context_window`, `observe_context_window`, `reported_window_for_model`, `_memoized_file`, `_FILE_MEMO`, `resolved_model`, `ClaudeRunStats(`) and by vocabulary (`200K`, `200,000`, `DEFAULT_CONTEXT_WINDOW`, `models_cache`, `debug models`).
- **Permission denials:** `uv run pytest tests/test_context_window.py` was denied (plain, and with a pipe or `timeout` prefix) and no `python` probe was allowed, so nothing was executed. Every claim below rests on code reading; mutation claims are traced, not run. No source, test or doc file was edited.

### Window-attribution rule: case matrix

Rule under test: `reported_window_for_model(model, model_windows, smallest)` returns the window of the entry whose id equals `model` (non-empty), else `smallest` (the minimum over the envelope's entries).

| Input | Result | Puts a window on a model that lacks it? | Silences a warning that should fire? |
| --- | --- | --- | --- |
| selected id present, other entries larger | that entry's window | no | no |
| selected id present, other entries smaller | that entry's window | no | no |
| selected id absent, one entry (alias such as `sonnet[1m]`, `opusplan`) | that entry's window | only if the CLI served a model other than the selected one (fallback model); not constructible from `--model` alone | only in that fallback case |
| selected id absent, several entries | smallest | no (a lower bound on the main model's window) | no; errs toward warning |
| `None` or `""` selected | smallest | no | no |
| selected id equals one id and is a prefix of or contained in another | exact entry only | no | no |
| entry id `""` with selected `""` | `model and` guard skips it, smallest | no | no |
| duplicate ids in the tuple with different windows | first wins | unreachable: `modelUsage` is a JSON object, so ids are unique | n/a |
| equal windows | that window | no | no |
| non-int, bool, zero or negative `contextWindow` | entry dropped by `_reported_model_windows` | no | no |

No input silences a warning that should fire. The only way to put a larger window on a selected model is a result envelope that omits the selected model while listing only larger ones (a CLI fallback model), which the rule cannot see and which is not reachable from a plain `--model` selection. The rule's remaining weakness is the opposite direction (finding 2: it is a lower bound that loses the benefit).

### Findings


#### 1. A transient read error is cached as a permanent "unreadable" verdict, and a permission fix cannot clear it

- **Category:** correctness / robustness
- **Severity:** Low-Medium
- **File:line:** `plan_tool/context_window.py:57-61` (key at `42-44`)
- **Failure scenario:** `_memoized_file` catches every `Exception` from `parse` and stores `_UNREADABLE` under `(mtime_ns, size, ino, dev)`. `parse` is `path.read_text(...)` followed by JSON/TOML parsing, so the catch also swallows `OSError` from the read itself: `EMFILE`/`ENFILE` (a `detail --jobs N` or `run` process holds many pipe descriptors), `EIO`, `EINTR`, `EACCES` from a root-owned or momentarily `chmod`ed file, `MemoryError`. The file did not change, so its version tuple is identical on every later lookup and the failure is served for the rest of the process: every later advisory on the Codex lane is measured and labelled against the 200,000 default and the refusal gate's catalog window is lost. A user who fixes the cause (`chmod 644`, `chown`) changes only `ctime`, which is not in the version, so the fix is invisible too. The test `test_an_unreadable_catalog_is_parsed_once_per_version_not_on_every_lookup` only pins a deterministic parse failure (`{not json`), which is the one class that is safe to cache.
- **Suggested fix:** cache only content failures (`ValueError` and its subclasses `JSONDecodeError`, `UnicodeDecodeError`, `tomllib.TOMLDecodeError`, plus the shape errors `TypeError`/`AttributeError` raised by `_parse_codex_catalog`). Let `OSError` and anything else return `None` for this lookup without writing a memo entry, so the next lookup reads again. Add a test whose `read_text` raises `OSError` once and then succeeds, asserting the second lookup returns the window.

- **Disposition:** fixed in `2a58b8545`. `_memoized_file` caches only content failures (`ValueError` and its subclasses, `TypeError`, `AttributeError`); any other exception, such as `OSError`, returns `None` for that lookup and writes nothing. `test_a_transient_read_error_is_not_cached_as_an_unreadable_file` fails the first read and requires the second lookup to return the window; caching every failure turns it red (checked by mutation).


#### 2. On the unselected-model and alias lanes the remembered window is last-write-wins over a lower bound, so it flips with the latest call's helper-model use and mostly cannot rise above 200,000

- **Category:** correctness / altitude
- **Severity:** Low-Medium
- **File:line:** `plan_tool/backend.py:987-1002`, `plan_tool/backend_runner.py:626-635`, `plan_tool/backend.py:949-959`
- **Failure scenario:** With no model selected (`resolved_model` None, the default configuration) or an alias, the stored value is the smallest window in that one call's envelope. A call whose envelope lists only the main model (1,000,000) stores 1,000,000. A later call that used a tool and therefore also lists a helper model (Claude Code's `modelUsage` commonly carries a small-model entry beside the main one, which this review could not observe in a real envelope) stores 200,000 under the same key, and a call after that stores 1,000,000 again. Two prompts of identical size are then judged `ok` and `high` depending only on what the previous call happened to touch; the audit re-arm re-measures every pass, so it can fire on that flip, consume its once-per-run flag and later miss real growth. For a run that always uses tools, the key never leaves 200,000, which is the default the feature exists to replace, and the summary no longer says `(default)` because the value is a "known" window. Single-entry envelopes carry the main model's exact window; multi-entry ones carry only a lower bound, and both write the same key with the same authority.
- **Suggested fix:** let only an exact-id match or a single-entry envelope write the key outright; let a multi-entry smallest write it only when the key has no value yet, so a lower bound never overwrites an exact observation. If the owner declines that, say in the ARCHITECTURE paragraph that the unselected and alias lanes are a per-call lower bound, so the "(default)"-free 200,000 is not read as a measured limit.

- **Disposition:** fixed in `2a58b8545`. The registry stores `(window, exact)`. An exact window (the selected model's own entry, or a lone entry) replaces anything; a lower bound (the smallest window of a mixed envelope) never replaces an exact one and only rises. `test_a_lower_bound_never_replaces_an_exact_window_and_only_rises` and a two-call streamed test cover it; letting a bound overwrite turns both red (checked by mutation). `docs/ARCHITECTURE.md` states it.


#### 3. No test pins that the pump passes the selected model into the rule; passing `None` there stays green

- **Category:** test-coverage
- **Severity:** Low-Medium
- **File:line:** `tests/test_context_window.py:335-352` (wiring at `plan_tool/backend_runner.py:628-634`)
- **Failure scenario:** `test_a_streamed_result_records_the_selected_models_window_not_a_sub_agents` selects `claude-haiku-4-5` (200,000) beside a heavy `claude-opus-5-5` (1,000,000). The selected model's window equals the smallest window, so the test passes under pure "smallest" and under a pump that passes `None` or any other string as the model. The exact-id branch is exercised only by the table test, which calls `reported_window_for_model` directly. Mutating the pump to `reported_window_for_model(None, ...)`, or to `reporting.name`, keeps every test green, and that is the wiring the two earlier attribution findings were about. The test name states a property it cannot distinguish.
- **Suggested fix:** stream an envelope where the selected model's window is the larger one (selected `claude-opus-5-5`, usage `claude-haiku-4-5` 200,000 and `claude-opus-5-5` 1,000,000) and assert `context_window_for("claude", "claude-opus-5-5") == 1_000_000`. Keep the haiku-selected case as the lower-bound row.

- **Disposition:** fixed in `2a58b8545`. `test_the_selected_model_is_what_the_pump_matches_on` selects `claude-opus-5-5` (the larger window) beside a light haiku entry and requires 1,000,000; a pump that passes `None` to the rule turns it red (checked by mutation).


#### 4. The inode and device components of the memo version are unpinned, although the ledger says each component is

- **Category:** test-coverage
- **Severity:** Low
- **File:line:** `tests/test_context_window.py:165-185`, `plan_tool/context_window.py:42-44`
- **Failure scenario:** pass 2 disposition 1 says "each component is pinned without the clock". Size is pinned by `test_the_codex_catalog_is_parsed_once_per_file_version` and mtime by the `os.utime` test. Nothing varies `st_ino` or `st_dev`. Reducing `_file_version` to `(mtime_ns, size)` keeps the suite green, so the case the inode exists for (a refresh by atomic rename inside one timestamp tick, same size) can regress without a failing test.
- **Suggested fix:** write the new body to a sibling file, set its mtime to the old file's with `os.utime(ns=...)`, `os.replace` it over the cache, assert the size and mtime are equal and the inode differs, then assert the new window is read. `st_dev` cannot be varied in a unit test; say so in the docstring instead of claiming it is pinned.

- **Disposition:** fixed in `2a58b8545`. `test_a_same_size_same_tick_replacement_by_rename_is_a_new_version` writes a sibling file, matches size and mtime with `os.utime`, `os.replace`s it over the cache and requires the new window; dropping the inode from the version turns it red (checked by mutation). The test says `st_dev` cannot be varied in a unit test.


#### 5. `smallest` and `ClaudeRunStats.context_window` are derivable from `model_windows`, and the rule's signature lets them disagree

- **Category:** simplification
- **Severity:** Low
- **File:line:** `plan_tool/backend.py:987-1002`, `plan_tool/backend.py:185-188`, `plan_tool/backend.py:962-971`
- **Failure scenario:** `ClaudeRunStats` carries `context_window` (the minimum) and `model_windows` (every pair), and `reported_window_for_model` takes both `model_windows` and `smallest`. The table test builds `smallest = min(...)` by hand, so the invariant "smallest is the minimum of model_windows" is enforced only by that test's arithmetic and by the parser. A parser or test double that fills `context_window` but not `model_windows` (or the reverse) makes the rule return a window not present in the envelope. The three-way redundancy also produced the stale-comment findings in passes 2 and 3.
- **Suggested fix:** drop the `smallest` parameter and compute `min(w for _n, w in model_windows)` inside the rule; keep a single stats field, `model_windows`, and derive the "is there a usable window" check from it in the pump (`if parsed.stats.model_windows`).

- **Disposition:** fixed in `2a58b8545`. `ClaudeRunStats.context_window` is removed. `model_windows` is the one field, and `reported_window_for_model(model, model_windows)` derives the bound and returns `(window, exact)`, so a parser cannot supply a bound the envelope lacks.


#### 6. New comments and docstrings are paragraph-length

- **Category:** conventions
- **Severity:** Low
- **File:line:** `plan_tool/context_window.py:1-18` and `31-36`, `plan_tool/review.py:9149-9154`, `plan_tool/backend.py:963-969` and `989-996`
- **Failure scenario:** repo `CLAUDE.md` § "Code comments" says: "Keep comments and docstrings terse — a line or two on the non-obvious *why*, not a paragraph. When a flow or contract needs more depth, put it in the relevant doc ... and cite it from the code". The `_FILE_MEMO` block (six lines), the re-arm comment in `review.py` (five lines), the two `backend.py` docstrings (five and six lines) and the 18-line module docstring each restate rationale that `docs/ARCHITECTURE.md` already carries in its "Prompt-budget window" paragraph. They are also where the superseded-rule wording drifted in passes 2 and 3.
- **Suggested fix:** cut each to one or two lines naming the invariant and point at `docs/ARCHITECTURE.md` § "Prompt-budget window".

- **Disposition:** fixed in `2a58b8545`. The module docstring of `context_window.py`, its memo comment, the registry comments in `backend.py` and the re-arm comment in `review.py` are one or two lines and point at `docs/ARCHITECTURE.md` § "Prompt-budget window".

### Areas checked and found sound

- **`_memoized_file` positive path:** the lock, the re-check and the in-lock `stat` give a stored tag never older than its entry; a stale-tag overwrite costs one reparse and is never wrong; a failed parse writes no entry of its own beyond `_UNREADABLE`; a file missing at lookup time raises from `stat` before any cache write, so a deleted-and-recreated cache is re-read and a stale good entry is not served; `{"models": ...}` of any wrong shape reaches `except` and reads as "not known"; a config without a top-level `model` caches `None` as a value, distinct from `_UNREADABLE`.
- **Partial in-place writes by the cache's writer:** a truncated or half-written file has a different size or mtime from the finished one, so a failure cached mid-write heals on the next lookup. Only a failure that leaves `(mtime_ns, size, ino, dev)` untouched sticks, which is finding 1.
- **`audit_base_warned_high` across passes:** warned-high then window grows (re-measured `ok`, growth re-arm can fire once); warned-high and still high (suppressed, as before); never warned and now high against a smaller window (suppression dropped once); warned `warn` only then growth to `high` (re-arm fires once). A base measurement that prints and then fails in `record_prompt_budget` leaves `audit_budget_covered` False, which is the older "keep the backstop" behaviour and not new. The class "a verdict computed once against the default and reused later" has no other site: `create`, each `detail` attempt and each `run_step` measure freshly before the send.
- **Refusal gate:** `observed=False` is the only deterministic-window site; the message reads only integer and bool fields of a normalised budget, so it cannot raise; the two existing stub tests construct full `PromptBudget`s.
- **Pump:** contextvar copy keeps the scoped backend visible, the bookkeeping is inside `try/except Exception`, and only the Claude result envelope populates stats. The Codex and Cursor parsers build `ClaudeRunStats` without the new fields.
- **Call sites:** eleven, matching the AST guard's exact counts (shell 1, review 3, create 1, detail 3, launcher 3); no aliased import of the budget functions exists outside the guard's name match.
- **Documentation:** RUNBOOK, ARCHITECTURE, changelog and BACKLOG #470 agree with the code on the single rule and the gate; DATA_CONTRACT's `context_window` key description ("window used for the headroom check") is still true, and the telemetry record's inability to tell a defaulted 200,000 from a known one is covered by the settled "telemetry keys unchanged" decision.

### Result

No Critical or High defect. The window-attribution rule held against every combination constructed (matrix above): no input puts a larger window on a model that lacks it or silences a warning that should fire, so it is not a fifth patch site. Findings 1 and 2 are Low-Medium and are about the memo's failure caching and the lower-bound write policy, not the rule's correctness; finding 3 is a wiring gap in the tests that the rule's three-pass history makes worth closing.

## Review pass 5 — /code-review (high, headless), 2026-10-09

Scope: `0de1c91d..f17befcf` (the whole change at the head after the pass-4 fixes `2a58b8545`). The reviewer wrote its report to `.tmp/prompt-budget-model-window-code-review-5.md` (stream log `.tmp/prompt-budget-model-window-code-review-5.stream.log`), copied below with headings shifted. It could not run a probe (three commands were denied), so its claims rest on code reading; each fix was checked by mutation in the driving session. Seven findings, none Critical or High; findings 1 and 2 are Low-Medium, and no finding concerned the attribution rule.


### Method

- **Scope:** `0de1c91d..HEAD` (`f17befcf4`) on `fix/prompt-budget-model-window`, fifth independent pass against the head after `2a58b8545`, concentrating on the `(window, exact)` registry in `backend.py` and the `_memoized_file` error classification in `context_window.py`.
- **Read:** the ledger `handoffs/2026-10-09-prompt-budget-model-window-code-review.md` in full (Settled decisions and every pass 1 to 4 disposition honoured, not re-reported); the whole code diff (`context_window.py`, `backend.py`, `backend_runner.py`, `prompt_budget.py`, `launcher.py`, `review.py`, `shell.py`, `create.py`, `detail.py`); `tests/test_context_window.py` in full, the `test_launcher.py` and `test_review.py` additions and the `conftest.py` fixture; the enclosing pump in `run_streaming_once`, `build_effective_backend` / `_select_effective_backend`, `shell._maybe_warn_shell_prompt_budget` and its call site; RUNBOOK, ARCHITECTURE, changelog fragment, changelog README, DATA_CONTRACT prompt-budget keys and BACKLOG #470.
- **Searches:** by identifier (`observe_context_window`, `observed_context_window`, `reported_window_for_model`, `_reported_model_windows`, `_memoized_file`, `_FILE_MEMO`, `active_context_window`, `resolved_model`, `modelUsage`, `model_windows`) and by vocabulary (`advisory`, `never fails`, `never blocks`, `refuses nothing`, `200,000`, `200K`, `(default)`, `lower bound`, `fallback`).
- **Permission denials:** a `python3 -I` probe (to confirm the exception classes `tomllib` and `json` raise on deeply nested input) was denied, so nothing was executed; the exception-class claims in finding 5 rest on knowledge of the stdlib (`TOMLDecodeError`, `JSONDecodeError` and `UnicodeDecodeError` are `ValueError` subclasses; the nested-input failure is a `RecursionError`). No source, test or doc file was edited; only this file was written.

### Questions put to this pass

| Question | Answer |
| --- | --- |
| Can a stale exact window outlive a model whose window changed within the process? | Yes in one direction: an exact entry is only replaced by another exact one, so a lower bound can never correct it (finding 4). The key is `resolved_model`, so a different selected model never reads it. |
| Can a lower bound that only rises exceed the true window? | Not from a single envelope that contains the main model: the smallest entry is at most the main model's window, and the held value is a max of such minimums for one key. It can exceed it only if a call's envelope omits the main model while listing larger ones (a CLI fallback via `--fallback-model` in `extra_batch_argv`, already noted in pass 4's matrix). No new route found. |
| How do two worker threads interleave `observe_context_window`? | Badly: the get / branch / set sequence is unlocked, so a lower bound computed from a stale read overwrites a concurrent exact write (finding 1). |
| What does a model switch mid-run do? | A new key, so no borrowing; the new model measures against the default until its own call reports. Switching back finds the older value. A rate-limit `SWITCH` scopes the fallback backend, and the pump reads `get_active_backend()` at pump time, so it records under the fallback backend's own name and model. Sound. |
| Can a persistently failing file be re-read under the global lock on every lookup? | Yes for a persistent `OSError` (unreadable file, a directory at the path) and for `RecursionError` on pathologically nested input; cost is small (finding 5). A `ValueError`-class content failure is cached per version. |
| Does `tomllib` raise anything outside `ValueError` for a malformed config? | Only `RecursionError` on pathologically nested arrays or tables (and `UnicodeDecodeError` is a `ValueError`). `TOMLDecodeError` is a `ValueError` subclass. |
| Would a test stay green if the feature were reverted? | A wholesale revert is caught (AST guard, launcher gate test, shell backstop test, re-arm tests). One partial mutation survives: the pump passing `exact=False` always (finding 6). |
| Do the changelog, RUNBOOK and ARCHITECTURE state anything the code does not do? | The changelog and RUNBOOK overstate the Claude lane (finding 2), and RUNBOOK still says the budget "never fails a run" beside the refusal (finding 3). ARCHITECTURE matches the code. |

### Findings


#### 1. `observe_context_window` is an unlocked read-modify-write, so a concurrent lower bound can overwrite an exact window

- **Category:** concurrency / correctness
- **Severity:** Low-Medium
- **File:line:** `plan_tool/backend.py:949-962` (called from the pump at `plan_tool/backend_runner.py:630-633`)
- **Failure scenario:** `detail --jobs N` (or any process with several in-flight Claude calls) runs one stdout pump thread per call. Key `("claude", "")` holds `(300_000, False)`. Thread A finishes a mixed envelope (lower bound 200_000) and executes `held = _observed_context_windows.get(key)`. Thread B finishes a single-entry envelope (exact 1_000_000) and writes `(1_000_000, True)`. Thread A resumes with its stale `held`, takes the `not held[1]` branch and writes `(max(300_000, 200_000), False)`, replacing the exact window with a bound. The documented rule "a lower bound never replaces an exact one" is violated, and the key reads 300_000 until another exact envelope arrives. On the default configuration (no selected model) most envelopes of a tool-using run are mixed, so no exact observation may ever follow: every later advisory in the process is measured against the stale bound and warns `high` for prompts that fit, which is the symptom #470 exists to remove. The same lost update happens from `held is None`: A reads `None`, B writes exact, A writes `(w, False)` over it. Nothing in the suite exercises two writers.
- **Suggested fix:** do the whole update under one module-level `threading.Lock` (the registry is written once per call, so contention is nil), or fold it into a single atomic `dict.setdefault` / compare-and-set loop. Add a test that interleaves an exact write between a bound's read and write (call the helper from two threads on a barrier, or split the function so the decision is a pure function of `(held, window, exact)` and test that).

- **Disposition:** fixed in `2916d970b`. `observe_context_window` updates under a module lock and the rule is the pure `_merged_observation(held, window, exact)`, tested over seven cases. A six-thread smoke test with an exact write in the mix requires an exact final state; the unlocked version fails it in three of four runs (the race is probabilistic, so the pure-function table is the deterministic pin).


#### 2. The changelog fragment and RUNBOOK state the Claude lane without its lower-bound limits

- **Category:** documentation
- **Severity:** Low-Medium
- **File:line:** `changelog.d/prompt-budget-model-window.md:3`, `RUNBOOK.md:3900-3904`
- **Failure scenario:** both say that for Claude the window is "the window the CLI reported on an earlier call", and the changelog adds "so a long run stops warning `high` about prompts that fit a 1,000,000-token window". The code stores the reported window only when the envelope has a single `modelUsage` entry or an entry whose id equals the selected model's `resolved_model` exactly. Otherwise (a mixed envelope with a helper model, no model selected, or an alias such as `opus` or `sonnet[1m]`) it stores the smallest window in that envelope, a lower bound that is typically 200,000. A user running `plan-tool run` with the default model or an alias, whose envelopes list a small helper beside the main model, reads the changelog, sees no change, and the summary line then says `200,000 window` with no `(default)` marker, so it reads as a measured limit although nothing was learned. RUNBOOK's "the warning says `(default)` when it fell back to 200,000" is likewise not true for a lower bound that equals the default. Only `docs/ARCHITECTURE.md` carries the rule.
- **Suggested fix:** one clause in each of the changelog and RUNBOOK: a reported window is used when the call used one model or the selected model's id appears in the result; a mixed result gives only its smallest window, which is shown without `(default)`. Alternatively mark a lower bound in the summary (for example `>= 200,000 window`), which also closes the "no marker" half.

- **Disposition:** fixed in `2916d970b`. The changelog fragment and RUNBOOK say a Claude window is used when the call used one model or listed the selected model's id, and that a mixed result gives only its smallest window, shown without `(default)`. The reviewer's alternative of marking a bound in the summary was not taken: it changes the summary text for a case the docs now describe.


#### 3. RUNBOOK still says the advisory "never fails a run" beside the shipped refusal

- **Category:** documentation
- **Severity:** Low
- **File:line:** `RUNBOOK.md:3912` (and `RUNBOOK.md:3897-3898`)
- **Failure scenario:** the "When it fires" bullet lists `reconcile` steps among the covered sends and ends "It stays advisory: it warns, it never fails a run." A selected `run-reconcile` prompt at `high` is refused with `LauncherError` before the backend runs (`launcher.run_step`), so a reader of this bullet is told a refusal cannot happen, in the same section whose lead paragraph now names one. The lead paragraph also still calls the same behaviour the "surface unconditionally, block never" stance immediately before naming the exception. This is the vocabulary half of the sweep pass 2 finding 6 asked for ("advisory", "never blocks", "never fails"); the lead paragraph was fixed and the bullet was not.
- **Suggested fix:** in the bullet, say "it warns; the one exception is the selected run-reconcile refusal above". Re-word the lead sentence so the "block never" stance is stated as the rule with the one named exception.

- **Disposition:** fixed in `2916d970b`. The RUNBOOK "When it fires" bullet says it warns and does not fail a run except the selected run-reconcile refusal; the lead paragraph names the exception as the one exception to the "block never" stance.


#### 4. An exact window has no expiry, so a lower bound can never correct it after the implicit default model changes

- **Category:** correctness
- **Severity:** Low
- **File:line:** `plan_tool/backend.py:949-962`, `plan_tool/backend.py:984-1000`
- **Failure scenario:** with no model selected the key is `("claude", "")`, which stands for "whatever model the CLI picks". That choice is not constant for a process: the CLI's own default can change underneath a long run (a plan-quota or availability fallback from a 1,000,000-window default to a 200,000-window one, or `settings.json` / `ANTHROPIC_MODEL` edited during a multi-hour `run`). One single-entry envelope from the first model stores `(1_000_000, True)`. After the switch every envelope lists the new main model beside a helper, so each is a lower bound, and "a lower bound never replaces an exact one". The key keeps 1_000_000 for the rest of the process and silences a real `warn` / `high` for a prompt between 200K and 1M tokens. Only a lone-entry envelope of the new model would correct it. The failure direction is the unsafe one (suppresses the warning), unlike a stale bound.
- **Suggested fix:** let a lower bound that is strictly below the held exact window by itself be kept as a second field (`bound`) and have the lookup return `min(exact, bound_of_latest_call)` only when the latest envelope omits the exact entry's model; or, smaller, let a lower bound replace an exact window when the exact one was recorded under the empty key (where the model identity is not pinned). If the owner declines, state in `docs/ARCHITECTURE.md` that the empty-key exact window is process-lifetime and is assumed to name one model.

- **Disposition:** declined as a code change, documented in `2916d970b`. Letting a lower bound replace an exact window under the empty key would bring back the flip between two calls of one size that pass 4 finding 2 removed, to cover a default model that changes mid-run. `docs/ARCHITECTURE.md` states that the no-model key holds one window for the process and assumes the CLI's default model does not change.


#### 5. Persistent read failures and `RecursionError` are not cached, so the file is re-read under the global lock on every lookup

- **Category:** efficiency
- **Severity:** Low
- **File:line:** `plan_tool/context_window.py:40-45`
- **Failure scenario:** `_memoized_file` caches only `ValueError`, `TypeError` and `AttributeError`; every other exception returns `None` and writes nothing. That is right for a transient `EMFILE` but also catches failures that are stable for the file version: `EACCES` on a `chmod 000` or root-owned `models_cache.json`, `EISDIR` when something created a directory at that path, and `RecursionError` from `json.loads` / `tomllib.loads` of pathologically nested content (not a `ValueError`). For those the lookup runs `stat`, then the failing `open` (or a full read and parse for `RecursionError`) while holding the module-wide `_FILE_MEMO_LOCK`, on each of the three to six lookups per `run` / `detail` step, and `detail --jobs N` workers serialise on that lock. For `OSError` the cost is a failed `open` per lookup, so the practical effect is small; for `RecursionError` it is a full re-parse. A named pipe at the path would block under the lock indefinitely (not a realistic input).
- **Suggested fix:** classify by whether the file version can change the outcome: cache `RecursionError` with the content failures, and cache a persistent `OSError` subclass (`PermissionError`, `IsADirectoryError`) per version while still not caching `EMFILE` / `ENFILE` / `EINTR`. Or keep the current rule and add a short negative cache (a monotonic timestamp) for the uncached branch.

- **Disposition:** fixed in part in `2916d970b`. `RecursionError` is cached per version with the content failures (`test_pathologically_nested_content_is_a_cached_content_failure`; uncaching it turns the test red). A persistent `OSError` stays uncached on purpose: a permission fix changes `ctime`, not the version tuple, so caching it would hide the fix (pass 4 finding 1). The cost is a failed `open` per lookup.


#### 6. No test pins the pump's `exact` argument: passing `exact=False` always stays green

- **Category:** test-coverage
- **Severity:** Low
- **File:line:** `plan_tool/backend_runner.py:630-633`, `tests/test_context_window.py:431-444`, `tests/test_context_window.py:411-428`
- **Failure scenario:** the pump forwards `exact=reported[1]`. Mutate it to `exact=False`. `test_a_helper_model_in_a_later_result_does_not_flip_an_earlier_exact_window` still passes (a bound of 1_000_000 followed by a bound of 200_000 keeps `max` = 1_000_000), `test_the_selected_model_is_what_the_pump_matches_on` still passes (the bound is the first write), and `test_a_streamed_result_teaches_later_estimates_the_models_window` still passes. The only tests that distinguish exact from bound run `observe_context_window` directly, and the rule table runs `reported_window_for_model` directly, so the wiring between them is unpinned: with `exact=False` always, a window can never fall (a later single-entry envelope of a smaller model is ignored) and an alias is never exact. The opposite mutation (always `True`) is caught.
- **Suggested fix:** stream two envelopes through `claude_invoke` for one key in which the second is a single-entry envelope with a smaller window (for example `1_000_000` then lone `200_000`) and assert the lookup returns `200_000`; that fails under `exact=False`.

- **Disposition:** fixed in `2916d970b`. `test_a_later_lone_entry_result_replaces_an_earlier_exact_window` streams a 1,000,000 window and then a lone 200,000 one and requires 200,000; forcing `exact=False` in the pump turns it red in every run (checked by mutation).


#### 7. The new ARCHITECTURE entry packs a lane-by-source mapping into one paragraph

- **Category:** conventions
- **Severity:** Low
- **File:line:** `docs/ARCHITECTURE.md:116`
- **Failure scenario:** repo `CLAUDE.md` § "Developer-facing documentation readability" says: "Developer-facing documentation supports scanning before deep reading. State a section's purpose first; represent mappings, state-dependent behavior, and ordered flows in their natural form". The "Prompt-budget window" entry is one paragraph of about 330 words that carries a mapping (backend lane by window source), a precedence order (observed over catalog, the gate excluding observed), four rules for the registry, and the failure/caching behaviour. A reader looking for "what does the Claude lane do with a mixed envelope" or "what does the gate use" has to read the whole block, and each later pass has had to re-derive which clause governs (the reason pass 3 finding 4 and several wording findings recurred).
- **Suggested fix:** keep the lead sentence as the purpose, then give the sources as a short table (lane / source / when it is used / what it is excluded from) and the registry rule as a three-row list (exact id, lone entry, mixed envelope), with the caching sentence as its own bullet.

- **Disposition:** fixed in `2916d970b`. The "Prompt-budget window" entry is a purpose paragraph, a lane / window-source / limits table, a four-item registry list and a three-item contracts list.

### Result

No Critical or High defect, and no defect in the window-attribution rule. The two Low-Medium items are a lost update in the registry under concurrent pumps (1) and the user-facing docs describing the Claude lane more strongly than the code delivers (2). The memo's error classification behaves as dispositioned for `ValueError`-class content failures and for transient `OSError`; the residual (5) is a cost, not a wrong answer.

Areas checked and found sound: the `_memoized_file` double-checked lock, in-lock `stat` and the returned-value path (a concurrent miss never reads as "unknown"); `tomllib.TOMLDecodeError`, `json.JSONDecodeError` and `UnicodeDecodeError` as `ValueError` subclasses (cached per version); `{"models": ...}` of any wrong shape reaching the cached-unreadable path; a missing file raising from `stat` before any cache write; the `(window, exact)` update ordering for a single thread (exact replaces, a bound only fills an empty key or rises over a bound); key isolation between models and backends (no borrowing, including across a rate-limit `SWITCH`); the pump's contextvar visibility and its `try/except Exception` around the bookkeeping; `ClaudeRunStats.model_windows` default on the Codex and Cursor parsers and `replace()` preserving it; `window_defaulted` for `0`, negative and `None`; the refusal gate's `observed=False` and its message (integer fields of a normalised budget); the audit re-arm across warned-high / never-warned / window-grows / window-shrinks cases; the eleven call sites and the AST guard's exact counts; the conftest fixture's isolation of both the registry and the memo; the leaf import surface (`plan_tool.backend` only).

## Review pass 6 — /code-review (high, headless), 2026-10-09

Scope: `0de1c91d..e058d8be` (the whole feature, code head `2916d970b`). The reviewer wrote its report to `.tmp/prompt-budget-model-window-code-review-6.md` (stream log `.tmp/prompt-budget-model-window-code-review-6.stream.log`), copied below with headings shifted. It could not run tests or read `~/.codex` (six commands were denied), so its claims rest on code reading; each fix was checked by mutation in the driving session. Ten findings and a stage-by-stage trace of one Claude call and one Codex call. **No Critical, High or correctness finding**: findings 1 and 2 are test gaps that let a one-line regression pass, and 3 to 10 are backlog, test-naming, contract, documentation and comment items.


### Method

- **Scope:** `0de1c91d..HEAD` (`e058d8be6`; code head `2916d970b`) on `fix/prompt-budget-model-window`, sixth
  independent pass, whole feature rather than the pass-5 delta.
- **Read:** the ledger `handoffs/2026-10-09-prompt-budget-model-window-code-review.md` in full (Settled decisions and
  every pass 1 to 5 disposition honoured, not re-reported, including the declined no-model-key expiry, the uncached
  persistent `OSError`, the Codex profile / `-c model=` / relative `CODEX_HOME` limit, the first-call-uses-default
  limit, the lower-bound-shown-without-`(default)` limit, and the unchanged telemetry keys). The whole code diff
  (`context_window.py`, `backend.py`, `backend_runner.py`, `prompt_budget.py`, `launcher.py`, `review.py`, `shell.py`,
  `create.py`, `detail.py`); the enclosing `run_step`, `claude_invoke_outcome`, `_run_once_seam`, the stdout pump in
  `run_streaming_once`, `build_effective_backend` / `_select_effective_backend`, `_author_step_detail`'s measurement,
  the audit re-arm in `audit_plan_until_stable`; `tests/test_context_window.py` in full, the `test_launcher.py`,
  `test_review.py` and `conftest.py` additions, `tests/test_shell.py::test_backstop_warns_on_large_prompt`; RUNBOOK,
  `docs/ARCHITECTURE.md`, the changelog fragment, BACKLOG #470, DATA_CONTRACT's prompt-budget keys, the changelog
  README, and the repo and user `CLAUDE.md` files.
- **Searches:** by identifier (`active_context_window`, `context_window_for`, `observe_context_window`,
  `observed_context_window`, `reported_window_for_model`, `_merged_observation`, `window_defaulted`,
  `estimate_prompt_budget`, `maybe_warn_prompt_budget`, `audit_base_level`, `audit_base_warned_high`, `CODEX_HOME`,
  `models_cache`, `modelUsage`) and by vocabulary (`200,000`, `200K`, `default`, `advisory`, `refuses`,
  `headroom`, `window`) across code, tests and every non-archived doc.
- **Permission denials:** `uv run pytest tests/test_context_window.py` (plain and with `set -o pipefail`), `codex debug
  --help`, and a read of `~/.codex/models_cache.json` were denied, so nothing was executed and the real Codex catalog
  shape was not observed. Every claim below rests on code reading; mutation claims are traced against the tests, not
  run. No source, test or doc file was edited; only this file was written.

### One Claude call and one Codex call, stage by stage

Claude (`--backend claude --model claude-opus-5-5`, no earlier call in the process):

| Stage | Window used | `(default)` printed | Matches the model's window? |
| --- | --- | --- | --- |
| Selection (`_select_effective_backend` → `build_effective_backend`) | none yet; `resolved_model = "claude-opus-5-5"` | n/a | n/a |
| `run --dry-run` printer (`launcher.py:1695`) | `active_context_window()` → no observation, no Claude file source → default 200,000 | yes | no, the model may have 1,000,000; settled first-call limit |
| Selected run-reconcile refusal gate (`launcher.py:1713`) | `observed=False` → default 200,000, always on Claude | yes, also in the refusal text | no on a 1M model; settled |
| Advisory (`launcher.py:1753`) and its telemetry record | 200,000 | yes in the warning; the record carries `context_window=200000` with no marker (settled) | no on a 1M model; settled |
| Pump after the call (`backend_runner.py:624-635`) | `reported_window_for_model` → `(window, exact)` stored under `("claude", "claude-opus-5-5")` | n/a | exact when the envelope lists the selected id or one entry; a lower bound otherwise |
| Next advisory, backstop, telemetry | the stored window | no | exact: yes. lower bound: a floor, shown without `(default)` (documented) |
| Batch lane (`claude_invoke` → `_maybe_warn_shell_prompt_budget`) | same lookup through `get_active_backend()`; the call also runs through `run_streaming_once`, so it feeds the same registry | same | same |

Codex (`--backend codex --model gpt-6.1-sol`):

| Stage | Window used | `(default)` printed | Matches the model's window? |
| --- | --- | --- | --- |
| Every stage including the refusal gate | `context_window_for("codex", "gpt-6.1-sol")`: the observed lookup always misses (the Codex parser sets no `model_windows`), then `$CODEX_HOME` or `~/.codex` `models_cache.json` → `272000 * 95 // 100 = 258,400` | no | yes, to the usable share |
| After the call | nothing recorded (no `model_windows`) | n/a | n/a |
| Model absent from the catalog, catalog unreadable, or no model resolvable | `None` → 200,000 | yes | n/a, the marker is right |

No stage was found where the window used differs from the model's window beyond the documented and settled limits,
and no stage was found where `(default)` is printed for a known window or omitted for a defaulted one (a bound equal
to 200,000 is the documented exception). The Codex `config.toml` keys `model_context_window` and
`model_auto_compact_token_limit` are not read; that is the same class as the declined profile / `-c` limit and is not
re-reported.

### Findings


#### 1. The default Codex home (`~/.codex`) is not pinned by any test

- **Category:** test-coverage (survives revert)
- **Severity:** Low-Medium
- **File:line:** `plan_tool/context_window.py:72-74`, `tests/conftest.py:226-236`, `tests/test_context_window.py:24-37`
- **Failure scenario:** the autouse fixture deletes `CODEX_HOME`, and every Codex test either sets `CODEX_HOME` through
  `_codex_home` or patches `Path.home` to raise (`test_the_lookup_never_raises_when_the_home_directory_cannot_be_resolved`,
  which asserts only that `None` comes back). No test creates `<HOME>/.codex/models_cache.json` and expects a window.
  Changing `Path.home() / ".codex"` to `".codex2"`, `".config/codex"`, or dropping the `Path.home()` join keeps the whole
  suite green, and that branch is the one almost every real Codex user takes (few set `CODEX_HOME`). The feature then
  silently degrades to `(default)` for them, which is the pre-change behaviour with a new label.
- **Suggested fix:** one test that leaves `CODEX_HOME` unset, writes `tmp_path / ".codex" / "models_cache.json"`, points
  `HOME` (and `Path.home`) at `tmp_path`, and asserts `context_window_for("codex", "gpt-6.1-sol") == 258_400`; a second
  assertion that a set-but-empty `CODEX_HOME` falls back to it.

- **Disposition:** fixed in `2c3ee57ea`. `test_the_default_codex_home_is_dot_codex_under_the_home_directory` leaves `CODEX_HOME` unset (and then empty) and reads `<home>/.codex/models_cache.json`; changing the default directory name turns it red (checked by mutation).


#### 2. An explicit model beating `config.toml`'s model is not pinned

- **Category:** test-coverage (survives mutation)
- **Severity:** Low-Medium
- **File:line:** `plan_tool/context_window.py:110`, `tests/test_context_window.py:24-37`, `tests/test_context_window.py:56-59`
- **Failure scenario:** `slug = model or _memoized_file(home / "config.toml", _parse_codex_model)` encodes that the
  backend's `resolved_model` outranks the config file's `model`. Every test that sets both uses the same slug:
  `_codex_home`'s default config is `model = "gpt-6.1-sol"` and the lookups ask for `"gpt-6.1-sol"`; the launcher gate
  test writes no `config.toml`. Swapping the operands (`_memoized_file(...) or model`) passes every test, yet it measures
  a `--model gpt-6.1-sol` run against whatever model the config names (a 128K model would turn a fitting prompt into a
  `high`, a 1M one would silence a real `warn`). This is the "assert the carve-out" case in the repo `CLAUDE.md` §
  "Tests": the precedence is stated in ARCHITECTURE and in code, and nothing asserts it.
- **Suggested fix:** a test with a config model `small` (window 100,000) and an explicit model `gpt-6.1-sol` (window
  272,000) asserting `context_window_for("codex", "gpt-6.1-sol") == 258_400` and `context_window_for("codex", None) ==
  95_000`. In the same test file, add the absent-`effective_context_window_percent` case (default 100) and a `100`
  case, which no test exercises today (`_SOL` always carries the key; only `0` is tested for the fallback).

- **Disposition:** fixed in `2c3ee57ea`. `test_an_explicit_model_outranks_the_one_in_the_codex_config` has two catalog models and a different config model, and `test_the_effective_percent_defaults_to_the_whole_window_when_absent_or_out_of_range` covers an absent, `100`, `101` and boolean percent. Swapping the operands turns both red (checked by mutation).


#### 3. The motivating case stays untracked once the #470 entry is removed

- **Category:** completeness / backlog bookkeeping
- **Severity:** Low
- **File:line:** `BACKLOG.md:12935`, `docs/ARCHITECTURE.md:121`, `plan_tool/launcher.py:1713`
- **Failure scenario:** #470's Evidence is a single 605 KB prompt on a 1,000,000-token Claude model that "prints `high`
  today", and #469's roadmap prompt is one send per process. After this change that prompt still prints `high` with
  `(default)` on its only call, and a selected run-reconcile prompt on Claude is still refused at the 200,000 default
  with no way around it, because a window learned mid-run is excluded from the gate and nothing is learned before the
  first call. The first-call limit is a settled decision and is not disputed here. The gap is that the Status line says
  "remove this entry when that branch merges", and the repo `CLAUDE.md` § "Backlog-derived seeds must carry backlog
  reconciliation forward" asks to leave or update "any deferred follow-up that remains": the follow-up (a pre-call
  Claude window source) will have no home. ARCHITECTURE also states "None exists before the first call", which is
  broader than the code supports: an explicit `[1m]` suffix on the selected model id is a local, deterministic
  declaration of a 1,000,000 window and is available before the call (and would be usable by the refusal gate, being
  a string rather than process history).
- **Suggested fix:** before removing #470, file a follow-up entry (pre-call Claude window from the model id suffix, or
  from `model_specs`' cached catalog without a network fetch) carrying the evidence above, or narrow ARCHITECTURE to
  "no reported window exists before the first call".

- **Disposition:** fixed in `2c3ee57ea`. BACKLOG #472 carries the pre-call Claude window follow-up (the `[1m]` suffix or the cached catalog, no network), evidence-gated on confirming the suffix against a real run, and `docs/ARCHITECTURE.md` now says "no reported window exists before the first call" with a pointer to #472.


#### 4. Two new tests pin less than their names and docstrings say

- **Category:** test-coverage / documentation (survives revert)
- **Severity:** Low
- **File:line:** `tests/test_context_window.py:557-575`, `tests/test_context_window.py:585-598`
- **Failure scenario:** `test_a_605kb_prompt_is_measured_against_each_lanes_own_window` passes `context_window=1_000_000`
  as a literal for the Claude lane and `None` for the default lane, so only its Codex row calls the new resolver; the
  other two rows would pass on the code before this branch (apart from the `window_defaulted` field). Reverting the
  Claude half of the feature leaves it green, and its name claims the lane resolves its own window. Separately,
  `test_a_learned_window_silences_the_shell_backstop_for_a_prompt_that_fits_it` says "500 KB reads `high` against the
  200K default"; 500,000 B is about 142,858 tokens, 28.6% headroom, which is `warn` (`HIGH_HEADROOM_RATIO` 0.15,
  `WARN_HEADROOM_RATIO` 0.40; `tests/test_shell.py::test_backstop_warns_on_large_prompt` says "crosses WARN"). The
  assertion itself (nothing printed) is correct.
- **Suggested fix:** drive the Claude row through `observe_context_window("claude", None, 1_000_000)` and
  `active_context_window()` so it uses the resolver, or rename it for what it pins; correct the docstring to `warn`.
  The `window_defaulted` field and the marker belong in `tests/test_prompt_budget.py` per the repo's one-module-one-test
  convention; that file is untouched by this branch.

- **Disposition:** fixed in `2c3ee57ea`. The lane test drives the Claude and Codex rows through `active_context_window()` and its docstring says `warn` for the 500 KB shell case; the two `window_defaulted` tests moved to `tests/test_prompt_budget.py`.


#### 5. The two external formats the feature reads are not captured or contracted anywhere in the repo

- **Category:** documentation / robustness
- **Severity:** Low
- **File:line:** `plan_tool/context_window.py:78-96`, `plan_tool/backend.py:980-992`, `docs/reference/contracts/codex-cli.md`
- **Failure scenario:** `models_cache.json`'s `models[].slug`, `context_window`, `effective_context_window_percent`, and
  the Claude envelope's `modelUsage[<id>].contextWindow` are read from files and streams the tool does not own. The
  repo keeps pinned CLI contracts for exactly this (`docs/reference/contracts/codex-cli.md`,
  `cursor-agent-cli.md`), and neither names these keys; BACKLOG #470 quotes values ("272,000 default, 872,000 maximum,
  95% effective") but not field names, and every fixture is hand-built by the same author who wrote the parser. A
  rename on either side makes every lookup return `None` and the advisory fall back to `(default)`: visible, but no
  test fails and nothing says which key to look at. No pass could observe the real file (the reviewer's reads of
  `~/.codex` were denied again here), so the key names are unverified by review.
- **Suggested fix:** add a short "window sources" section to `docs/reference/contracts/codex-cli.md` naming the keys
  and the CLI version they were observed on (client 0.162.0, per BACKLOG), and keep one trimmed real sample of each
  (one catalog entry, one `modelUsage` object) as a test fixture so a shape change is a failing test.

- **Disposition:** fixed in `2c3ee57ea`. `docs/reference/contracts/model-window-sources.md` names the keys read from the Codex catalog and the Claude result envelope with the versions observed, and `tests/test_context_window.py` keeps one trimmed real sample of each (`_REAL_CODEX_ENTRY`, `_REAL_CLAUDE_MODEL_USAGE`) with a test that parses it.


#### 6. Changelog says `~/.codex`; the code honours `$CODEX_HOME`

- **Category:** documentation
- **Severity:** Low
- **File:line:** `changelog.d/prompt-budget-model-window.md:3`
- **Failure scenario:** the fragment says Codex's window is read "from `~/.codex/models_cache.json`". With `CODEX_HOME`
  set the code reads `$CODEX_HOME/models_cache.json` and never the home-directory file (ARCHITECTURE and the code say
  so). A user who exports `CODEX_HOME` and follows the fragment refreshes or inspects the wrong file. The fragment is
  also one bullet of about 1,000 characters packing the Codex source, the Claude rule, the default marker, the
  refusal exception and the refresh command, against the changelog README's "write for someone who uses the tool".
- **Suggested fix:** "`models_cache.json` under `$CODEX_HOME` (default `~/.codex`)", and split the bullet into the
  warning change and the refusal-gate note.

- **Disposition:** fixed in `2c3ee57ea`. The fragment says `models_cache.json` under `$CODEX_HOME` (default `~/.codex`) and is two bullets: the warning change and the refusal-gate note.


#### 7. RUNBOOK's lead paragraph packs a mapping and an exception into prose

- **Category:** conventions
- **Severity:** Low
- **File:line:** `RUNBOOK.md:3894-3905`, `RUNBOOK.md:3914-3917`
- **Failure scenario:** repo `CLAUDE.md` § "Developer-facing documentation readability": "represent mappings,
  state-dependent behavior, and ordered flows in their natural form; and separate the normal path from its
  exceptions." The paragraph states the purpose, then the single refusal exception inside the first sentence, then a
  lane-to-source mapping inside a parenthetical (`Codex: ...; Claude: ...; a result that mixes models ...`), then the
  default marker. Pass 5 finding 7 got the same class fixed in ARCHITECTURE (table plus lists); this is the sibling
  site the sweep did not reach. The "When it fires" bullet also carries ragged wraps from the edit
  (`... described\n  above. It\n  does **not** fire ...`).
- **Suggested fix:** keep the one-sentence purpose, then a three-row table (lane, window source, shown as) and one
  separate "The one refusal" bullet that points at ARCHITECTURE § "Prompt-budget window".

- **Disposition:** fixed in `2c3ee57ea`. The RUNBOOK section keeps a one-sentence purpose, then a lane / window table and a separate "The one refusal" bullet; the "When it fires" bullet is re-wrapped.


#### 8. The shell backstop takes `backend` as a parameter but resolves the window from the active backend again

- **Category:** simplification / altitude
- **Severity:** Low
- **File:line:** `plan_tool/shell.py:458-466`
- **Failure scenario:** `_maybe_warn_shell_prompt_budget(prompt, backend)` measures bytes through `backend.batch_transport`
  and the window through `active_context_window()`, which re-reads `get_active_backend()`. Its only caller passes the
  active backend, so they agree today; a second caller (or a test) that passes another backend gets that backend's
  bytes measured against the active backend's window, with the telemetry record built from the mismatch. The
  repo-wide AST guard is what forces the zero-argument form here.
- **Suggested fix:** `context_window_for(backend.name, backend.resolved_model)` at this one site and allow it in the
  guard, or drop the parameter and read the active backend once so the two cannot diverge.

- **Disposition:** declined as a code change. `_maybe_warn_shell_prompt_budget(prompt, backend)` is a pre-existing signature with one caller, which passes the active backend; the AST guard exists to force the zero-argument form at this site. A comment at the site now says the two are the same backend.


#### 9. DATA_CONTRACT still describes `context_window` as the model's window

- **Category:** documentation
- **Severity:** Low
- **File:line:** `DATA_CONTRACT.md:1558`
- **Failure scenario:** the row says "model context window used for the headroom check". The recorded value is now one of
  three things (a reported window, a catalog window, or the 200,000 fallback) and the record carries no field that
  says which, so a reader tuning thresholds from the distribution (the section's stated purpose) cannot tell a
  defaulted 200,000 from a known one. The unchanged keys are a settled decision; the gap is only that the contract
  says nothing, and the user-level "prefer the explicit over the implicit" rule asks for the limit to be written
  down ("deliberately not recorded, because ...").
- **Suggested fix:** one sentence under the table: the value is the window used, which is the 200,000 fallback when no
  window was known; the record does not distinguish the two.

- **Disposition:** fixed in `2c3ee57ea`. `DATA_CONTRACT.md` says `context_window` is the window the check used, may be the 200,000 fallback, and that the record deliberately does not say which.


#### 10. The re-arm's explanatory comment describes only the old trigger

- **Category:** documentation (comment)
- **Severity:** Low
- **File:line:** `plan_tool/review.py:9142-9148`
- **Failure scenario:** the block comment says the re-arm fires on "the first pass whose carried block grows the prompt
  from a safe base into the `high` danger band" and is "skipped when the base was already `high` (already warned)".
  The code now also fires, with no carried growth at all, for a base that reads `high` against a window learned
  later and was never warned, and skips only a base that was actually warned `high`. The two-line comment inside the
  branch carries the new rule, so a reader of the block comment alone is told something narrower than the code does.
- **Suggested fix:** replace the block comment with the three cases (base warned high: skip; base high now and never
  warned: drop once; base not high: drop once when base plus carried reads high) and the pointer to ARCHITECTURE.

- **Disposition:** fixed in `2c3ee57ea`. The block comment in `audit_plan_until_stable` states the two trigger cases and the skip case and points at `docs/ARCHITECTURE.md` § "Prompt-budget window".

### Result

No Critical or High defect, and nothing material in the correctness path. The trace above found no stage where the
window used differs from the model's beyond the settled and documented limits, and no wrong `(default)` marker. The
registry rule, the merge function, the lock, the memo's error classes, the pump wiring and the audit re-arm behave as
the dispositions say in every path read.

The findings are test gaps that let a regression in the Codex default path or the explicit-model precedence pass
(1, 2), one untracked follow-up (3), and documentation, convention and comment drift (4 to 10). Findings 1 and 2 are
the two most worth closing, because each names a mutation of a one-line expression that leaves all 13,700+ tests
green and changes what most Codex users see.

Areas checked and found sound: `_merged_observation` over its seven-row table and the lock around it; the pump's
`try/except` and its use of the active backend at pump time (same object the lookup uses); `ClaudeRunStats.model_windows`
defaulting and `replace()`; `_reported_model_windows` rejecting bool, zero, non-dict and non-string keys; the memo's
fast path, in-lock re-stat and re-check, the `_UNREADABLE` sentinel and the `except` ordering (content failures cached,
`OSError` not); a missing file raising from `stat` before any write; `_parse_codex_catalog` on every wrong shape;
`window_defaulted` for `None`, `0` and negative; the refusal gate's `observed=False`, message and test; the eleven
call sites and the AST guard's exact counts (shell 1, review 3, create 1, detail 3, launcher 3); the conftest
isolation of the registry and the memo; the leaf's import surface (`plan_tool.backend` only) and the absence of any
other hard-coded 200,000 or 1,000,000 window in `plan_tool/`. Attribution: no trailer, tool name or credit in the
range's commit messages or non-ledger diff.

## Review pass 7 — /code-review (high, headless), 2026-10-09

Scope: `0de1c91d..bcb89a6a` (the whole feature, logic head `2916d970b`), with the instruction to look from outside the files the earlier passes concentrated on: user-visible wording, repository conventions, other readers of the same values, and test reliability. The reviewer wrote its report to `.tmp/prompt-budget-model-window-code-review-7.md` (stream log `.tmp/prompt-budget-model-window-code-review-7.stream.log`), copied below with headings shifted. It could not run tests or `codex debug --help` (five commands were denied), so its claims rest on code reading. Seven findings, all Low; **no correctness finding**.


### Method

- **Scope:** `0de1c91d..HEAD` (`bcb89a6af`; logic head `2916d970b`) on `fix/prompt-budget-model-window`, seventh
  independent pass, looking at the feature from outside the files passes 1 to 6 concentrated on.
- **Read:** the ledger `handoffs/2026-10-09-prompt-budget-model-window-code-review.md` in full (Settled decisions
  and every pass 1 to 6 disposition honoured, not re-reported); the whole code diff (`context_window.py`,
  `backend.py`, `backend_runner.py`, `prompt_budget.py`, `launcher.py`, `review.py`, `shell.py`, `create.py`,
  `detail.py`); `tests/test_context_window.py` in full plus the `conftest.py`, `test_launcher.py`,
  `test_prompt_budget.py` and `test_review.py` hunks; the RUNBOOK section, `docs/ARCHITECTURE.md` entry,
  `DATA_CONTRACT.md` sentence, changelog fragment, `docs/reference/contracts/model-window-sources.md`, BACKLOG
  #470 and #472; the repo `CLAUDE.md`, `docs/TRACKING.md` (entry format, quality roll-up),
  `docs/reference/README.md`, `docs/reference/documentation-style.md` and `changelog.d/README.md`.
- **Lenses and what each covered:**
  - (a) user-visible strings: `render_budget_summary` (`(default)` marker), the refusal text at
    `launcher.py:1717-1722`, RUNBOOK table and bullets, changelog bullets, DATA_CONTRACT sentence, the contract
    page.
  - (b) repo conventions: test mirroring, comment length, docs index reachability, BACKLOG entry format and
    roll-up, changelog fragment naming, scratch-file naming, commit trailers (none present), forward-looking
    wording, the explicit-over-implicit rule.
  - (c) readers of the same values: every `PromptBudget(` construction and equality use (all keyword-built;
    only `test_prompt_budget.py::test_maybe_warn_returns_budget` compares instances and it passes an explicit
    window on both sides), every `ClaudeRunStats(` construction (all keyword or no-arg; no `asdict`/`fields`
    over it; `bench._stats_to_fields` picks named fields), telemetry consumers of `context_window`
    (`telemetry.py` only writes it; no analysis reads it), `data_contract.py` (neither dataclass is
    registered), `bench.py` (no budget reader), the plan sweep (`sweep.py`: no budget input), `model_specs`
    (not used, settled), `CODEX_HOME` readers elsewhere in `plan_tool/` (none besides this leaf).
  - (d) tests: threads (`Barrier` tests), global monkeypatches (`json.loads`, `tomllib.loads`,
    `Path.read_text`, `threading.excepthook`), home-directory dependence (`_isolate_known_roots_cache` pins `HOME`
    and `Path.home` per test, and the new autouse fixture clears `CODEX_HOME`), clock dependence
    (`os.utime` with explicit nanoseconds, no sleeps), filesystem dependence (inode and mtime pinned by explicit
    `os.replace`/`os.utime`), run time of the AST guard (same shape as `tests/test_duplication.py`, which has no
    timeout marker either).
- **Permission denials:** `uv run pytest ...` (several forms), `python3 -I -c ...` (an `ast.parse` timing
  probe) and `codex debug --help` were each refused, and compound shell commands with pipes needed approval.
  Nothing was executed, so every claim rests on code reading. In particular `codex debug models` as the way to
  refresh `models_cache.json` (RUNBOOK, changelog, contract page, BACKLOG #470) was not verified here. No source,
  test or doc file was edited; only this file was written.

### Findings


#### 1. The new contract page is not indexed and nothing in the docs or code links to it

- **Category:** documentation / conventions
- **Severity:** Low
- **File:line:** `docs/reference/README.md:25-26` (the "Contracts" list), `docs/reference/contracts/model-window-sources.md:1`
- **Failure scenario:** `docs/reference/README.md` is the index of the contract pages: it lists
  `process.md`, `seed-ingestion.md`, `human-io.md`, `codex-cli.md` and `cursor-agent-cli.md`, and not the new
  page. A search for the new page's filename (`model-window-sources`) finds it only in a comment in
  `tests/test_context_window.py:96` and in the handoff. `docs/ARCHITECTURE.md` § "Prompt-budget window", the
  RUNBOOK section and `plan_tool/context_window.py`'s module docstring all describe the same two external
  shapes and do not link to it. The page exists so that "a rename on either side" sends a developer to the
  keys to check, and a developer who hits the `(default)` fallback after a Codex or Claude CLI upgrade is
  routed to `docs/reference/contracts/codex-cli.md` (listed, and which says nothing about these keys) instead.
  `docs/reference/documentation-style.md` says exact contracts belong in `docs/reference/` "as those documents
  are reviewed", which presumes they are reachable from the reference index.
- **Suggested fix:** add `- [Model window sources](contracts/model-window-sources.md)` to the Contracts list in
  `docs/reference/README.md`, and add one sentence with the link to `docs/ARCHITECTURE.md` § "Prompt-budget
  window" (the Limits column of the table is the natural place) and a one-line pointer in
  `context_window.py`'s docstring.

- **Disposition:** fixed in the docs commit after `4e7aaccb4`. `docs/reference/README.md` lists the contract page, `docs/ARCHITECTURE.md` § "Prompt-budget window" links it, and `context_window.py`'s docstring names it.


#### 2. BACKLOG #472 departs from the entry format in `docs/TRACKING.md`: it is missing from the quality roll-up and lacks most of the scope contract

- **Category:** conventions / backlog bookkeeping
- **Severity:** Low
- **File:line:** `BACKLOG.md:12965-12985` (#472), `BACKLOG.md:322-325` (the `gate-signal` roll-up), `docs/TRACKING.md:843-848` and `:850-880`
- **Failure scenario:** two quoted rules.
  1. `docs/TRACKING.md` § "Quality": "Omit the field entirely for pure ergonomics / perf / refactor / cosmetic
     work, **and add the item to the lens roll-up when you tag it**." #472 carries
     `**Quality:** gate-signal`, and the `gate-signal` bullet of the roll-up in `BACKLOG.md` (which names #469
     and #470 beside it, and says "keep it in sync as entries land or are added") does not name #472. A reader
     using the roll-up as the interim index of accuracy-impacting items (its stated purpose) will not find it.
  2. `docs/TRACKING.md` § "Scope contract": "required for substantial entries; omit only for a genuinely atomic
     one-liner with no plausible creep direction". #472 has `Out of scope / Non-goals` and `Verification`, and
     omits `Outcome`, `In scope`, `Allowed behavior changes` and `Stop / defer`. It is not an atomic one-liner:
     it names two candidate sources (the `[1m]` suffix, the cached `model_specs` catalog) and a gate, so it has
     a plausible creep direction. A seed derived from it "inherits this contract verbatim", and has no stated
     Outcome or In scope to inherit. (#470 itself also omits the last three fields; that is existing and not
     part of this finding.)
  Neither is enforced by a test (`tests/test_backlog_ids.py` and `tests/test_backlog_readability.py` check ids
  and openers only), so only review can catch it.
- **Suggested fix:** add `**#472**` with a short clause to the `gate-signal` bullet at `BACKLOG.md:324`, and add
  one-sentence `Outcome`, `In scope` (`plan_tool/context_window.py`, the refusal gate in
  `launcher.run_step`) and `Stop / defer` lines to #472, with `Allowed behavior changes` naming that an
  unsuffixed model is unchanged.

- **Disposition:** fixed in the same docs commit. BACKLOG #472 has Outcome, In scope, Allowed behavior changes and Stop / defer, and the `gate-signal` roll-up names it.


#### 3. Tests for `backend.py`, `backend_runner.py` and `shell.py` behavior were written into `tests/test_context_window.py`

- **Category:** conventions (test mirroring)
- **Severity:** Low
- **File:line:** `tests/test_context_window.py:411-461` (envelope parse, the exact/lower-bound rule, the merge
  rule), `:465-583` (concurrent registry writes and the streamed pump tests), `:586-632` (pump bookkeeping),
  `:657-672` (shell backstop)
- **Failure scenario:** repo `CLAUDE.md` § "Tests": "Mirror source modules: `plan_tool/X.py` →
  `tests/test_X.py`." Pass 6 finding 4 applied this rule to the `window_defaulted` tests (moved to
  `tests/test_prompt_budget.py`), but the same class remains. `ClaudeRunStats.model_windows` parsing,
  `_merged_observation`, `observe_context_window`, `reported_window_for_model` and `_reported_model_windows`
  are `plan_tool/backend.py` symbols; the `modelUsage` bookkeeping is `plan_tool/backend_runner.py`'s pump; the
  backstop-silencing test is `plan_tool/shell.py`. Their siblings already live in `tests/test_backend.py`
  (20 references to the parser and stats), `tests/test_backend_runner.py` (`test_result_envelope_populates_stats`,
  `test_observer_callback_exception_does_not_kill_the_pump_thread`) and
  `tests/test_shell.py::test_backstop_warns_on_large_prompt`. Someone changing the stats parser or the pump
  and running that module's file will not run the new tests, and someone reading the pump's tests for its
  "must not die" contract sees the pump's observer case and misses the bookkeeping case that pins the same
  property.
- **Suggested fix:** move the backend-level tests (`:411-461`, `:485-501`, `:610-617`) to
  `tests/test_backend.py`, the pump tests (`:502-607`, `:619-634`) to `tests/test_backend_runner.py`, and the
  backstop test (`:657-672`) to `tests/test_shell.py`. Keep the Codex catalog, memo and call-site AST guard in
  `test_context_window.py`. Moving them needs `_fake_popen_factory` imported from `tests.test_shell`, which
  `test_backend_runner.py` may already do through its own helper.

- **Disposition:** fixed in part in `4e7aaccb4`. The backend-level tests (envelope parsing, the exact-or-lower-bound rule, the merge rule, the registry, the real Claude sample) moved to `tests/test_backend.py`; the streamed-result and backstop tests moved to `tests/test_shell.py`, where `claude_invoke` and the fake `Popen` with git-argv delegation already live. They did not go to `tests/test_backend_runner.py` as suggested, because `test_shell.py` already imports from that file and the fake `Popen` is defined in `test_shell.py`. The Codex catalog, memo, lane and call-site tests stay in `tests/test_context_window.py`.


#### 4. The `backend.py` module docstring's "Public surface" list does not name the new public functions

- **Category:** documentation
- **Severity:** Low
- **File:line:** `plan_tool/backend.py:20-48` (module docstring), `plan_tool/backend.py:962-1003`
- **Failure scenario:** the module docstring enumerates the public surface as a closed list
  (`CliBackend`, `CLAUDE_BACKEND`, `get_active_backend`, ..., `discover_and_register_backends`). This change adds
  three public functions to the module (`observe_context_window`, `observed_context_window`,
  `reported_window_for_model`) that `backend_runner.py` and `context_window.py` import, and adds a
  `ClaudeRunStats` field. The list is how a reader decides what `backend.py` exports and what its import
  consumers are allowed to rely on; a reader who trusts it does not learn that the process-global window
  registry lives in this leaf, which is the one fact the ledger's Settled decisions call out as load-bearing
  ("`observe_context_window` / `observed_context_window` live in `backend.py`, because `backend_runner.py`'s
  documented first-party imports are exactly `backend` and `run_log`").
- **Suggested fix:** add one bullet to "Public surface": `observe_context_window` /
  `observed_context_window` / `reported_window_for_model` — the process-wide registry of windows a call's
  result envelope reported; read by `plan_tool.context_window` (see `docs/ARCHITECTURE.md` § "Prompt-budget
  window").

- **Disposition:** fixed in `4e7aaccb4`. The `backend.py` public-surface list has a bullet for `observe_context_window`, `observed_context_window` and `reported_window_for_model`.


#### 5. The window-count tests patch `json.loads` and `tomllib.loads` process-wide, so any other caller inflates the "parsed once" assertion

- **Category:** test reliability
- **Severity:** Low
- **File:line:** `tests/test_context_window.py:214-224` (`_count_parses`), `:261-279`, `:345-361`
- **Failure scenario:** `_count_parses` does `monkeypatch.setattr(context_window.json, "loads", counting_loads)`.
  `context_window.json` is the `json` module, so this replaces `json.loads` for every thread in the process
  while the test runs. `test_concurrent_cold_lookups_all_get_the_catalog_window_and_parse_once` then asserts
  `len(parses) == 1` over eight barrier-released threads; `test_the_codex_config_model_is_read_once_per_file_version`
  does the same with `tomllib.loads`. Any other `json.loads` caller alive in that process during the window (a
  run-log or telemetry writer, a heartbeat daemon from an earlier test in the same xdist worker that has not
  finished, a coverage or reporting plugin) adds a count and fails an assertion that is about this module's
  memo. The failure is rare and would present as an `-n auto`-only flake with no relation to the code under
  test, which the repo `CLAUDE.md` § "Tests" treats as "hidden shared state".
- **Suggested fix:** count parses at the module's own seam instead of the stdlib's:
  `monkeypatch.setattr(context_window, "_parse_codex_catalog", counting(real))` and the same for
  `_parse_codex_model`. `_memoized_file(path, parse)` receives the function by global name at call time, so the
  patch takes effect, and no foreign caller can be counted.

- **Disposition:** fixed in `4e7aaccb4`. `_count_calls` wraps `context_window._parse_codex_catalog` and `_parse_codex_model`, so a foreign `json.loads` caller cannot inflate a count.


#### 6. Two printed numbers and one dry-run behavior are worded in a way that reads as a different fact than the code states

- **Category:** wording / documentation
- **Severity:** Low
- **File:line:** `plan_tool/launcher.py:1717-1722` and `plan_tool/prompt_budget.py:139-141` (printed text),
  `RUNBOOK.md:3925-3931` and `:3918-3920`, `DATA_CONTRACT.md:1562-1565`
- **Failure scenario:**
  1. **The Codex number is the usable share but is printed as "window".** The summary and the refusal text
     print `258,400 window` for `gpt-6.1-sol`, and the refusal text calls it "the model catalog window". The
     catalog's own `context_window` is 272,000 and Codex's documentation names 272,000; 258,400 is
     `272000 * 95 // 100`. An operator who compares the printed line with the model's documented window sees a
     different number and no word saying it is the usable share (only the RUNBOOK table says so). The
     refusal text, which is the one place an operator is told why a send was refused, cannot be explained from
     its own contents.
  2. **`--dry-run` on Claude can never show a learned window, and the "Inspect before you spend" bullet says
     it is for seeing headroom.** `run --dry-run` and `detail --dry-run` send nothing, so the registry is empty
     and every Claude row prints `... window (default)`. The bullet at `RUNBOOK.md:3925-3931` presents the
     dry-run breakdown as how to "see headroom before burning a call", and its sibling bullet at `:3918-3920`
     still ends in a 125-character ragged line (pass 6 finding 7 said it was re-wrapped). A user inspecting a
     605 KB roadmap prompt on a 1,000,000-token Claude model sees `high ... (default)` and is not told that
     this is expected until a call has run. (Settled: the first call uses the default. Unsaid: that a dry run
     is always a first call.)
  3. **`DATA_CONTRACT.md:1562` lists two sources for `context_window` and the code has four.** "a known window
     of the selected model, or the 200,000 fallback" omits the Codex usable share (a scaled value, not the
     model's window) and the lower bound of a mixed Claude result (the smallest entry, which can be a helper
     model's window and is recorded unmarked). A reader tuning thresholds from the distribution, which is the
     sentence's stated reason, is told the recorded number is the selected model's window when for a mixed
     result it is not.
- **Suggested fix:** (1) say "usable window" in the refusal text, or print the share in the summary
  (`258,400 usable window`); (2) one sentence in the "Inspect before you spend" bullet: a dry run has made no
  call, so a Claude dry run is always measured against the default; and re-wrap the `:3918-3920` lines;
  (3) in the DATA_CONTRACT sentence enumerate all four sources (reported exact window, reported lower bound,
  Codex usable share, 200,000 fallback).

- **Disposition:** fixed in `4e7aaccb4` and the docs commit. The refusal text says "the model catalog's usable window"; the RUNBOOK dry-run bullet says a Claude dry run is always measured against the default; `DATA_CONTRACT.md` lists the four sources of `context_window`.


#### 7. A `PromptBudget` built without `window_defaulted` claims a known window

- **Category:** explicit over implicit
- **Severity:** Low
- **File:line:** `plan_tool/prompt_budget.py:67`
- **Failure scenario:** `window_defaulted: bool = False` makes the field's absence mean "the window was
  known". Every production value is built by `estimate_prompt_budget`, which always sets it, so no shipped
  path is wrong. The four test doubles that build `PromptBudget(...)` directly
  (`tests/test_launcher.py:778,959,997`, `tests/test_detail.py:16325`, `tests/test_cli.py:6595`) take the
  default, so a double that stands in for the default-window case silently reads as a measured one, and a
  future production site constructing the dataclass directly (rather than through the estimator) would print a
  default window without the `(default)` marker, which is the exact omission #470's Outcome ("say when the
  default was used") is about. The user-level `CLAUDE.md` § "Prefer the explicit over the implicit" asks that a
  load-bearing default be named; this one is a default whose absence reads as the *unsafe* answer.
- **Suggested fix:** make the field required (no default) so a direct construction must state it, updating the
  five doubles; or keep the default and add a one-line comment saying it is only for estimator-built values
  and that a hand-built budget must pass it.

- **Disposition:** fixed in `4e7aaccb4`. `PromptBudget.window_defaulted` is a required field (placed before `blocks`), and the five hand-built doubles state it.

### Result

No Critical, High or correctness finding. Seven Low findings: two reachability and bookkeeping items in the
docs and the backlog (1, 2), one convention miss that pass 6 fixed for one module and left for three (3), one
docstring drift (4), one test seam that counts too broadly (5), and two wording items (6, 7).

Checked and found sound, so the next pass need not repeat it:

- **Readers of the same values.** No code compares `PromptBudget` instances outside `test_prompt_budget.py`
  (both sides built with an explicit window); no code reads `ClaudeRunStats` positionally or serializes it
  whole; `bench.py` reads five named fields; the telemetry record's keys are unchanged and nothing in
  `plan_tool/` reads `context_window` back; the plan sweep and `model_specs` do not touch the budget;
  `CODEX_HOME` is read only by `context_window.py`, and no other code sets it for a child.
- **Parser failure mode.** `_reported_model_windows` cannot raise (type checks on every access), so adding it
  inside the `result` branch of `_claude_parse_stream_line` cannot turn a parse failure into lost token and
  cost stats.
- **Refusal exit path.** The refusal reaches `cli/reconcile.py:1670` through `LauncherError` and returns
  `rc = 2`, which is the documented "failure to complete" convention; the changed text is matched only by
  `tests/test_launcher.py` on the unchanged prefix `prompt budget is high`.
- **Test isolation.** `_isolate_known_roots_cache` pins `HOME` and `Path.home` per test, the new autouse
  fixture clears `CODEX_HOME`, resets the registry and the memo, so no test reads the developer's `~/.codex`.
  The timestamp tests set mtimes explicitly (no sleeps, no clock). The 6-thread, 3000-iteration registry test
  is bounded and deterministic for correct code (the exact write cannot be overwritten by a bound under the
  lock).
- **Commit hygiene.** No attribution trailer or tool name appears in the range's commit messages or the
  non-ledger diff; the changelog fragment is named by slug, as `changelog.d/README.md` says for a change
  without a ticket; `.tmp/` names in the ledger are task-specific; BACKLOG #472 does not collide with an id
  introduced on any local ref.


## Convergence status

**Converged, 2026-10-09.** The logic head is `2916d970b` (the registry lock and `RecursionError` caching) and its behavior has not changed since. Pass 6 (ten findings, none a code defect) and pass 7 (seven findings, all Low, none a correctness finding) are two independent consecutive low-yield passes against it, and every finding of passes 1 to 7 has a disposition. Between pass 7 and this record the only non-documentation edits are behavior-neutral and covered by tests: `PromptBudget.window_defaulted` became a required field (the estimator already set it, five test doubles now state it) and the reconcile refusal text says "usable window". They were judged not to reset the window; a pass 8 over them is available on request. The loop stops here.

Open follow-ups, none blocking: BACKLOG #472 (a Claude window before the first call), #471 (relation compaction), and the Linux per-argument limit noted under the closed ceiling work, which this change does not touch.
