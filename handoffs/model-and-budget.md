# Models, budgets and token ledger

Project model selection, prompt budgets and token-ledger logging. Each section below is one change or route in this workstream, ordered by the date it was opened; new work in the workstream appends a section here instead of creating a file (`README.md` § "Naming").

| Section | Opened |
| --- | --- |
| [Prompt-budget model window — code review ledger](#prompt-budget-model-window--code-review-ledger) | 2026-10-09 |
| [Token-ledger logging recovery](#token-ledger-logging-recovery) | 2026-10-16 |
| [Project model selection implementation](#project-model-selection-implementation) | 2026-11-12 |

## Prompt-budget model window — code review ledger

*Opened 2026-10-09.*

| Field | Value |
| --- | --- |
| Change | BACKLOG #470: the pre-send prompt-budget advisory measures a prompt against the selected model's context window (Codex from its local catalog, Claude from a window an earlier call reported) instead of a fixed 200,000 tokens |
| Branch | `fix/prompt-budget-model-window` |
| Review range | pass 1: `0de1c91d..82e25576` (code `bdd899d9`; backlog status `82e25576`); later passes review the whole change from `0de1c91d` at the head named in each pass heading |
| Checks run | Full suite `uv run pytest tests/ -q -n auto`: 13,702 passed, 67 skipped (pass 1 head) |
| Reviewer | headless `claude -p` with `CLAUDE_CONFIG_DIR=$HOME/.claude`, report-only, `high` effort (`.tmp/prompt-budget-model-window-code-review-N.stream.log`); reviewers could not run tests or probes, so their claims rest on code reading and each fix was checked by mutation in the driving session |
| Disposition | pass 1 triaged (8 fixed, 1 declined); pass 2 triaged (9 fixed, 1 fixed in part); pass 3 triaged (8 fixed); pass 4 triaged (6 fixed); pass 5 triaged (5 fixed, 1 in part, 1 declined); pass 6 triaged (9 fixed, 1 declined); pass 7 triaged (6 fixed, 1 in part); converged (passes 6 and 7 against logic head `2916d970b`) |

### Settled decisions (hand to each reviewer)

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

Decisions that emerged from the review (settled; do not reopen):

- Claude window attribution is one rule after three passes of heuristic patches (2026-10-09, `008a47c7b`): the entry whose id equals the selected model exactly, else the smallest window in the envelope (a lower bound that errs toward warning). No containment match, no dominant-entry fallback. Pass 4 checked the rule against a constructed case matrix and found no input that puts a larger window on a model lacking it or silences a warning that should fire.
- The registry stores `(window, exact)`: an exact window (selected model's own entry, or a lone entry) replaces anything; a lower bound never replaces an exact one and only rises. The no-model key holds one window for the process and assumes the CLI's default model does not change (pass 5 finding 4, declined).
- Codex profiles, `-c model=` in `extra_batch_argv`, and a relative `CODEX_HOME` resolved against another working directory are not seen; the window is that of the top-level model (pass 1 finding 6, declined; stated in `docs/ARCHITECTURE.md`).
- A persistent `OSError` reading a catalog or config file is not cached: a permission fix changes `ctime`, not the version tuple, so caching it would hide the fix. Content failures (`ValueError` family, `TypeError`, `AttributeError`, `RecursionError`) are cached per file version.

### Findings by pass

Each finding line: finding, disposition. Fixes were checked by mutation (the named test goes red when the fix is reverted) unless stated otherwise.

#### Pass 1 — scope `0de1c91d..82e25576`; fixes `bb35fe3b`

The reviewer returned its report as the final message; two real defects (1, 2), none Critical.

1. `launcher.py:1711`, the run-reconcile refusal gate took its verdict from process history and a machine-local file, contradicting "refuses nothing": **fixed** `bb35fe3b`. The gate calls `active_context_window(observed=False)`; changelog, `docs/ARCHITECTURE.md`, BACKLOG #470 and the settled decisions no longer say the budget "refuses nothing". `test_selected_reconcile_refusal_gate_uses_only_deterministic_window_sources` pins both lanes.
2. `context_window.py:64`, a catalog whose `models` is null or not a list raised an uncaught `TypeError` from an advisory-only lookup: **fixed** `bb35fe3b`. `_codex_window` and `active_context_window` catch `Exception` and return `None`, including an unresolvable home; tests cover `models` as null, number, string, dict, non-entry list, failing `Path.home` and failing `get_active_backend`.
3. `backend.py:959`, `max()` over every `modelUsage` entry attributed an auxiliary model's window to the selected one: **fixed** `bb35fe3b` (interim rule: entry with the most tokens; superseded by the pass 3 rule). `test_the_reported_window_is_the_one_of_the_model_that_did_the_work`.
4. `review.py:9159`, `audit_base_level` measured once against the default window permanently disabled the growth re-arm after a spurious `high`: **fixed** `bb35fe3b`. `audit_plan_until_stable` re-measures the base against `active_context_window()` every pass; `test_a_base_that_read_high_against_the_default_window_still_rearms_once_the_window_is_known` fails on the previous code (0 backstop warnings instead of 1, run against the earlier `review.py`).
5. `context_window.py:46`, the Codex catalog was parsed on every lookup: **fixed** `bb35fe3b`. `_codex_catalog` memoizes per-slug windows on path, `st_mtime_ns` and size; `test_the_codex_catalog_is_parsed_once_per_file_version`.
6. `context_window.py:56`, Codex profile, `-c model=` override and relative `CODEX_HOME` are not seen: **declined** as a code change (same class of error the default window already made); limit stated in `docs/ARCHITECTURE.md`.
7. `docs/ARCHITECTURE.md:127`, the paragraph sat under the rate-limit heading, lacked a Module-map row and named the wrong model source: **fixed** `bb35fe3b`. Moved under "Backend abstraction", Module-map row added for `prompt_budget.py` and `context_window.py`, source reads `resolved_model` (flag, project override or manifest default) before `config.toml`, gate behavior and first-call limit stated.
8. `tests/test_context_window.py:237`, the AST guard passed any non-`None` value and a dead Codex-observed path was asserted: **fixed** `bb35fe3b`. The guard requires a call to `active_context_window`; the refusal gate and audit re-measure have known-window tests. `test_an_observed_window_outranks_the_codex_catalog` is kept because it pins the registry's backend-agnostic precedence.
9. `backend_runner.py:623`, `observe_context_window` bookkeeping in the stdout pump sat outside any try: **fixed** `bb35fe3b`. Inside `try/except Exception`; `test_a_failing_window_bookkeeping_cannot_take_the_pump_down` installs a `threading.excepthook` collector (its first version passed against the unguarded code and was strengthened).

#### Pass 2 — scope `0de1c91d..13b57e00`; fixes `ba9f8896`

Ten findings, none Critical or High. Answered the reviewer's questions: the `observed=False` gate is the only refusal tied to a budget verdict; every other consumer warns, records telemetry or toggles which warning prints.

1. Medium, `tests/test_context_window.py:134-157`, the memo test depended on mtime resolution (same-length rewrite; coarse timestamps on Linux filesystems), and a same-size refresh inside one tick kept the old window in production: **fixed** `ba9f8896`. Memo key is `(mtime_ns, size, inode)`; the test rewrites to a different size and a second test keeps the size and sets mtime with `os.utime`.
2. `context_window.py:70-85`, `_codex_catalog` memo not thread-safe (a concurrent miss raised `KeyError`, read as "unknown", and stampeded the parse): **fixed** `ba9f8896`. `threading.Lock` on the miss path with an in-lock re-check, returning the locally parsed value; `test_concurrent_cold_lookups_all_get_the_catalog_window_and_parse_once` (eight threads on a barrier, one parse).
3. `backend.py:959-982`, the dominant-model rule could attribute a sub-agent model's window to the selected model and a tie picked the larger window: **fixed** `ba9f8896` (interim rule: prefer the selected model's entry, smaller on ties; superseded by the pass 3 rule). Tests cover the match table and a streamed haiku-selected result beside a heavy opus entry.
4. `launcher.py:1713-1721`, the refusal message hid the window and the `(default)` marker: **fixed** `ba9f8896`. The message carries the budget summary (tokens, window, `(default)`, headroom); the gate test asserts it names the window and carries `(default)` exactly on the Claude lane. Wording refined in pass 3 finding 7.
5. `tests/test_context_window.py:296-330`, no behavioral test pinned the window source at the advisory sites and the AST guard accepted any arguments: **fixed** `ba9f8896`. The guard pins exact per-module counts (`shell` 1, `review` 3, `create` 1, `detail` 3, `launcher` 3), requires no arguments and allows `observed=False` only on `launcher.py`; a behavioral test shows a learned 1M window silences the shell backstop for a 500 KB prompt; the audit re-arm test's fake estimator asserts the 1,000,000 window. A per-module behavioral test for `create` and each `detail` site was not added because they pass the same call and the guard pins their shape.
6. `RUNBOOK.md:3897`, `BACKLOG.md:12839`, `BACKLOG.md:11675`, "advisory only / never blocks / refuses nothing" stated beside a shipped refusal: **fixed** `ba9f8896` for the RUNBOOK (names the selected run-reconcile refusal and its window sources). The two BACKLOG sentences sit in the #469 entry, which `origin/main` already removed in PR #59 (`6b036e8d`); they disappear when this branch takes that commit.
7. Stale counts (#470 said nine sites, ledger said ten, code has eleven) and an `seen >= 10` floor that could not detect a dropped site: **fixed** `ba9f8896`. BACKLOG #470 and the ledger say eleven (`review.py` 3); the guard pins exact counts.
8. `backend.py:185`, the `ClaudeRunStats.context_window` comment and a test name described the superseded rule: **fixed** `ba9f8896`.
9. Repeated window resolution and an unmemoized `config.toml` parse on hot paths: **fixed in part** `ba9f8896`. The `config.toml` model read is memoized with the catalog's mechanism. Hoisting one lookup per pass or step is **declined**: the call-site guard needs `active_context_window()` inline and the memo makes a repeat a stat call.
10. `context_window.py` leaf claim unpinned and `window_defaulted` duplicated the fallback logic: **fixed** `ba9f8896`. `test_the_leaf_imports_only_the_backend_leaf`; `estimate_prompt_budget` derives `window_defaulted` once and `window` from it.

#### Pass 3 — scope `0de1c91d..203d575b`; fixes `008a47c7b`

Eight findings, none Critical or High. Findings 1 and 2 sat in the attribution rule, the site that drew a finding in all three passes (each earlier fix was a heuristic with a new failure). `008a47c7b` replaced the heuristics with one rule checked against the whole case matrix (see Settled decisions above).

1. `backend.py:1012-1014`, an exact `modelUsage` match did not outrank containment matches and `min()` understated the selected model's window (`claude-sonnet-5-5[1m]` beside bare `claude-sonnet-5-5`; short names matched everything): **fixed** `008a47c7b`. Containment match removed; the parametrized matrix test has the pair in both directions and a short name (`claude`).
2. `backend.py:1015`, a selected alias with no matching entry (`sonnet[1m]`, `opusplan`) adopted the dominant entry's window, re-opening pass 2 finding 3: **fixed** `008a47c7b`. No dominant fallback for a selected model; an alias takes the smallest window in the envelope.
3. `tests/test_context_window.py:291-306`, no test pinned the several-matches rule, exact-over-fuzzy precedence, or the unmatched-selected vs `None` case: **fixed** `008a47c7b`. Matrix test plus two streamed-result tests.
4. `docs/ARCHITECTURE.md:116` and a `backend.py` comment still described the dominant-entry rule: **fixed** `008a47c7b`; both say smallest.
5. Parse failures were never cached (re-parse on every lookup under the global lock; stored tag could be older than the entry): **fixed** `008a47c7b`. Failure remembered per file version (`test_an_unreadable_catalog_is_parsed_once_per_version_not_on_every_lookup`); version read inside the lock. Refined in pass 4 finding 1.
6. Memo version omitted the device and the conftest fixture did not reset the memo: **fixed** `008a47c7b`. Version is `(mtime_ns, size, inode, device)`; the autouse fixture in `tests/conftest.py` resets `_FILE_MEMO`.
7. The refusal message repeated itself and never said why a learned window was ignored: **fixed** `008a47c7b`. Built from budget fields: `... retry (~N tokens vs W window[ (default)], judged against the model catalog window or the default, not a window learned during this run)`.
8. `review.py:9147-9161`, the re-arm no longer knew whether the base was ever warned, so a window learned smaller than the default suppressed both warnings: **fixed** `008a47c7b`. The audit records `audit_base_warned_high`; a base that is `high` now and never warned drops the suppression once. `test_a_base_that_never_warned_but_reads_high_against_a_smaller_learned_window_rearms_at_once`.

#### Pass 4 — scope `0de1c91d..0c06447a`; fixes `2a58b8545`

Six findings, none Critical or High. The attribution rule held against the constructed case matrix, so the stop condition set after pass 3 did not trigger.

1. `context_window.py:57-61`, a transient read error (`EMFILE`, `EIO`, `EACCES`) was cached as a permanent "unreadable" verdict: **fixed** `2a58b8545`. Only content failures are cached; any other exception returns `None` for that lookup and writes nothing. `test_a_transient_read_error_is_not_cached_as_an_unreadable_file`.
2. `backend.py:987-1002`, on the unselected-model and alias lanes the remembered window was last-write-wins over a lower bound and flipped with the latest call's helper-model use: **fixed** `2a58b8545`. `(window, exact)` registry (see Settled decisions); `test_a_lower_bound_never_replaces_an_exact_window_and_only_rises` and a two-call streamed test; `docs/ARCHITECTURE.md` states it.
3. `tests/test_context_window.py:335-352`, no test pinned that the pump passes the selected model into the rule: **fixed** `2a58b8545`. `test_the_selected_model_is_what_the_pump_matches_on` selects `claude-opus-5-5` (the larger window) beside a light haiku entry.
4. Inode and device components of the memo version unpinned: **fixed** `2a58b8545`. `test_a_same_size_same_tick_replacement_by_rename_is_a_new_version`; the test says `st_dev` cannot be varied in a unit test.
5. `smallest` and `ClaudeRunStats.context_window` were derivable from `model_windows` and could disagree: **fixed** `2a58b8545`. `context_window` removed; `reported_window_for_model(model, model_windows)` returns `(window, exact)`.
6. Paragraph-length comments and docstrings against repo `CLAUDE.md` § "Code comments": **fixed** `2a58b8545`; one or two lines each, pointing at `docs/ARCHITECTURE.md` § "Prompt-budget window".

#### Pass 5 — scope `0de1c91d..f17befcf`; fixes `2916d970b`

Seven findings, none Critical or High; none concerned the attribution rule.

1. Low-Medium, `backend.py:949-962`, `observe_context_window` was an unlocked read-modify-write, so a concurrent lower bound could overwrite an exact window under `detail --jobs N`: **fixed** `2916d970b`. Update under a module lock; the rule is the pure `_merged_observation(held, window, exact)`, tested over seven cases; a six-thread smoke test requires an exact final state (fails in three of four runs on the unlocked version, so the pure-function table is the deterministic pin).
2. Low-Medium, changelog fragment and RUNBOOK stated the Claude lane without its lower-bound limits: **fixed** `2916d970b`. Both say a Claude window is used when the call used one model or listed the selected model's id, and a mixed result gives only its smallest window, shown without `(default)`. The reviewer's alternative (mark a bound in the summary) was not taken: it changes summary text for a case the docs now describe.
3. `RUNBOOK.md:3912`, "it never fails a run" beside the shipped refusal: **fixed** `2916d970b`; the bullet and lead paragraph name the refusal as the one exception to the "block never" stance.
4. `backend.py:949-962`, an exact window has no expiry, so a lower bound cannot correct it after the implicit default model changes mid-run: **declined** as a code change, documented in `2916d970b`. Letting a bound replace an exact window under the empty key would bring back the flip pass 4 finding 2 removed, to cover a mid-run default-model change; `docs/ARCHITECTURE.md` states the no-model key holds one window for the process.
5. `context_window.py:40-45`, persistent read failures and `RecursionError` not cached: **fixed in part** `2916d970b`. `RecursionError` is cached per version (`test_pathologically_nested_content_is_a_cached_content_failure`). A persistent `OSError` stays uncached on purpose (see Settled decisions); the cost is a failed `open` per lookup.
6. No test pinned the pump's `exact` argument (`exact=False` always stayed green): **fixed** `2916d970b`. `test_a_later_lone_entry_result_replaces_an_earlier_exact_window` streams 1,000,000 then a lone 200,000 and requires 200,000.
7. `docs/ARCHITECTURE.md:116`, the "Prompt-budget window" entry packed a lane-by-source mapping into one paragraph: **fixed** `2916d970b`. Purpose paragraph, lane / window-source / limits table, four-item registry list, three-item contracts list.

#### Pass 6 — scope `0de1c91d..e058d8be` (logic head `2916d970b`); fixes `2c3ee57ea`

Ten findings and a stage-by-stage trace of one Claude call and one Codex call; no Critical, High or correctness finding. The trace found no stage where the window used differs from the model's beyond the settled limits, and no wrong `(default)` marker (a lower bound equal to 200,000 is the documented exception). The Codex `config.toml` keys `model_context_window` and `model_auto_compact_token_limit` are not read; same class as the declined profile limit.

1. Low-Medium, the default Codex home `~/.codex` was not pinned by any test: **fixed** `2c3ee57ea`. `test_the_default_codex_home_is_dot_codex_under_the_home_directory` (unset and empty `CODEX_HOME`).
2. Low-Medium, an explicit model beating `config.toml`'s model was not pinned: **fixed** `2c3ee57ea`. `test_an_explicit_model_outranks_the_one_in_the_codex_config` and `test_the_effective_percent_defaults_to_the_whole_window_when_absent_or_out_of_range` (absent, `100`, `101`, boolean).
3. The motivating case (a first-call prompt on a 1M Claude model) stays untracked once #470 is removed: **fixed** `2c3ee57ea`. BACKLOG #472 carries the pre-call Claude window follow-up (the `[1m]` suffix or the cached catalog, no network), evidence-gated on confirming the suffix against a real run; ARCHITECTURE says "no reported window exists before the first call" and points at #472.
4. Two new tests pinned less than their names said (a literal `1_000_000` for the Claude row; docstring said `high` for a `warn` case): **fixed** `2c3ee57ea`. Lane test drives Claude and Codex through `active_context_window()`; the two `window_defaulted` tests moved to `tests/test_prompt_budget.py`.
5. The two external formats read (Codex `models_cache.json`, Claude `modelUsage`) were not contracted anywhere: **fixed** `2c3ee57ea`. `docs/reference/contracts/model-window-sources.md` names the keys and versions observed; `tests/test_context_window.py` keeps one trimmed real sample of each (`_REAL_CODEX_ENTRY`, `_REAL_CLAUDE_MODEL_USAGE`) with a parse test.
6. Changelog said `~/.codex` while the code honours `$CODEX_HOME`: **fixed** `2c3ee57ea`; fragment names `models_cache.json` under `$CODEX_HOME` (default `~/.codex`) and is two bullets.
7. RUNBOOK lead paragraph packed a mapping and an exception into prose: **fixed** `2c3ee57ea`. One-sentence purpose, a lane / window table, a separate "The one refusal" bullet, re-wrapped "When it fires" bullet.
8. `shell.py:458-466`, `_maybe_warn_shell_prompt_budget(prompt, backend)` resolves the window from the active backend again: **declined** as a code change. Pre-existing signature with one caller, which passes the active backend; the AST guard forces the zero-argument form here; a comment at the site now says the two are the same backend.
9. `DATA_CONTRACT.md:1558`, `context_window` described as the model's window: **fixed** `2c3ee57ea`. It is the window the check used, may be the 200,000 fallback, and the record deliberately does not say which.
10. `review.py:9142-9148`, the re-arm block comment described only the old trigger: **fixed** `2c3ee57ea`; states the two trigger cases and the skip case and points at `docs/ARCHITECTURE.md` § "Prompt-budget window".

#### Pass 7 — scope `0de1c91d..bcb89a6a` (logic head `2916d970b`); fixes `4e7aaccb4` and the docs commit after it

Seven findings, all Low, no correctness finding; the reviewer looked from outside the files earlier passes concentrated on (user-visible wording, repository conventions, other readers of the same values, test reliability). Checked and found sound, not to be repeated: every `PromptBudget(` and `ClaudeRunStats(` construction and reader (no positional or whole-object serialization; `bench.py` reads five named fields; nothing reads `context_window` back from telemetry); `_reported_model_windows` cannot raise inside the stream parser; the refusal reaches `cli/reconcile.py:1670` through `LauncherError` with `rc = 2` (the "failure to complete" convention); per-test isolation of `HOME`, `CODEX_HOME`, the registry and the memo; the 6-thread registry test is deterministic for correct code; no attribution trailer or tool name in the range.

1. `docs/reference/README.md:25-26`, the new contract page was not indexed or linked: **fixed** in the docs commit after `4e7aaccb4`. Listed in `docs/reference/README.md`, linked from `docs/ARCHITECTURE.md` § "Prompt-budget window", named in `context_window.py`'s docstring.
2. BACKLOG #472 missed the `gate-signal` quality roll-up and most of the scope contract (`docs/TRACKING.md`): **fixed** in the same docs commit. #472 has Outcome, In scope, Allowed behavior changes and Stop / defer; the roll-up names it.
3. Tests for `backend.py`, `backend_runner.py` and `shell.py` behavior sat in `tests/test_context_window.py` (repo mirroring rule): **fixed in part** `4e7aaccb4`. Backend-level tests (envelope parsing, exact-or-lower-bound rule, merge rule, registry, real Claude sample) moved to `tests/test_backend.py`; streamed-result and backstop tests moved to `tests/test_shell.py`, not `tests/test_backend_runner.py` as suggested, because `test_shell.py` already imports from that file and defines the fake `Popen` with git-argv delegation. Codex catalog, memo, lane and call-site tests stay in `tests/test_context_window.py`.
4. The `backend.py` public-surface docstring omitted the new registry functions: **fixed** `4e7aaccb4`.
5. Window-count tests patched `json.loads` and `tomllib.loads` process-wide (an `-n auto` flake risk): **fixed** `4e7aaccb4`. `_count_calls` wraps `context_window._parse_codex_catalog` and `_parse_codex_model`.
6. Printed wording: the Codex usable share printed as "window", a Claude dry run is always measured against the default, and `DATA_CONTRACT.md` listed two sources for `context_window` where the code has four (reported exact window, reported lower bound, Codex usable share, 200,000 fallback): **fixed** `4e7aaccb4` and the docs commit. The refusal text says "the model catalog's usable window"; the RUNBOOK dry-run bullet states the default measurement; `DATA_CONTRACT.md` lists the four sources.
7. `prompt_budget.py:67`, a `PromptBudget` built without `window_defaulted` claimed a known window: **fixed** `4e7aaccb4`. `window_defaulted` is a required field (before `blocks`); the five hand-built doubles state it.

### Convergence status

**Converged, 2026-10-09.** The logic head is `2916d970b` (the registry lock and `RecursionError` caching) and its behavior has not changed since. Pass 6 (ten findings, none a code defect) and pass 7 (seven findings, all Low, none a correctness finding) are two independent consecutive low-yield passes against it, and every finding of passes 1 to 7 has a disposition. Between pass 7 and this record the only non-documentation edits are behavior-neutral and covered by tests: `PromptBudget.window_defaulted` became a required field (the estimator already set it, five test doubles now state it) and the reconcile refusal text says "usable window". They were judged not to reset the window; a pass 8 over them is available on request. The loop stops here.

Open follow-ups, none blocking: BACKLOG #472 (a Claude window before the first call), #471 (relation compaction), and the Linux per-argument limit noted under the closed ceiling work, which this change does not touch.

## Token-ledger logging recovery

*Opened 2026-10-16.*

### Scope and site decisions

The invariant is that calls with an existing run logger retain their exact prompt
identity and completed model-call telemetry, without changing model behavior.
This recovery lives in `plan-tool-2`; the source analysis remains in
`plan-tool-1/experiments/token-ledger/REPORT.md`. No other clone is edited.

Identifier search: `claude_call_start`, `prompt_bytes`, `apply_finding`,
`assess_direct_source_split_from_claude`, `install_call_end_sink` and
`bind_shell_sink`. Vocabulary search: `invoker`, `run_logger`, `start_step`,
`begin_seed_attempt`, `call_end` across the source and mirrored tests.

| Sites | Decision |
| --- | --- |
| launcher `apply_finding`, primary and follow-up | Emit streaming completion inside the existing sink; retain restoration and verdict behavior. |
| create `assess_direct_source_split_from_claude` | Bind/unbind the existing writer around the actual invocation; cached assessment emits no call. |
| create `_propose_risk_profile_from_seed` | Add start and sink to its existing optional logger; preserve fallback and checkpoint behavior. |
| create steps, references, synthesis, seed distillation, including repairs | Hash the actual prompt; add missing repair starts where a sink already exists. |
| intent proposal and gate suggestion | Add the missing start/hash to existing sink-bearing direct calls; retain no-target skips. |
| detail authoring, repair, lesson extraction | Hash actual prompts at existing starts. |
| review conceptual audit | Emit start from the actual reporting-independent invocation wrapper, including response-shape retries. |
| launcher run step | Hash the final execution prompt, leaving transport byte accounting unchanged. |
| foundational-logic sweep | Hash at existing start, preserving its no-run-log-import contract. |
| roadmap stages, feedback revisions, seed attempts, candidate run/review | Hash actual prompts and forward through the existing seed observer. |
| review criteria fulfillment, full review, review lesson extraction | Remain unchanged: functions have no run-logger parameter; command-to-function lifecycle plumbing is separate work. |
| create slug suggestion | Remain unchanged: no logger in scope. |
| jira export, annotate classification, lesson equivalence, concept-tree emission | Remain unchanged: no logger in scope; do not add command logging lifecycles here. |
| launcher deep validation and all-done review | Remain unchanged: no logger in scope. |

The follow-up sink inventory contains four functions without a start in their
body: `intent_proposal.propose_intents`, `gates.suggest_gates`,
`cli.completeness_cmd.finalize_completeness_run`, and
`cli.review_cmd._audit_sink`. The first two invoke directly and receive starts.
The last two only wrap/delegate calls; their no-prompt helper boundary stays.
Known command-lifecycle and slug deferrals remain BACKLOG #176 and #177.

### Verification contract

The final record identifies the reviewed range, focused and full-suite results,
mutation checks, and completed reviews. Existing tests outrank speculative
logging diagnoses. Older events lack `prompt_sha256`; a new event without an
available prompt uses null. This recovery adds no raw prompt text to the run log.

### Use of the recent analysis

Use prompt hashes to measure repeated explicit prompts in future captured runs.
Hash equality establishes equal rendered UTF-8 prompts, not equal model settings,
auto-loaded instructions, repository state, or tool reads; it does not alone
prove that a repeated call wastes tokens.
Keep backend-specific cached-token normalization in analysis, not production
logging. Lessons surface ablation and per-pass finding instrumentation remain
separate efforts; do not reduce audit samples from this repair or claim token
savings before a controlled comparison. The Integration replay retains its current
pipeline and scope boundaries.


### Review triage (2026-10-16 provenance)

| Review | Finding | Disposition |
| --- | --- | --- |
| 1 | No actionable findings in the initial recovery. | Candidate only. |
| 2 | Runtime hash import moves under `TYPE_CHECKING` during import cleanup. | Confirmed and corrected; concept-tree imports remain type-only. |
| 3 | No actionable findings after import correction. | Candidate only. |
| 4 | Intent proposals have a sink but no start/hash. | Confirmed and corrected; the class sweep also repairs gate suggestions. |
| 5 | No actionable findings in the complete final code. | First clean final pass. |
| 6 | No actionable findings in `a8119e1e6..d02362927`. | Second consecutive clean final pass; review converges. |

The sink inventory guard checks direct `invoker` calls in functions that bind
a sink, including a completely missing start event. The prompt-bearing start
guard separately checks hash forwarding. Neither claims semantic coverage of
arbitrary callback names or model-call paths without a run logger.

The parametrized behavioral checks cover apply, apply follow-up, source
assessment, risk classification, intent proposals and gate suggestions. Separate
skip cases pin zero calls for no-target intent/gate requests. The audit sampler
check pins exact hashes with no progress reporter. Historical reverted-attempt
notes remain provenance; this record owns the current recovery status.


### Verification evidence (2026-10-16 provenance)

Reviewed production/test range: `a8119e1e6..d02362927`.

| Commit | Concern |
| --- | --- |
| `83cfdf9aa` | Optional prompt-hash schema, reporter forwarding, and compatibility tests. |
| `4d80e5fba` | Invocation prompt identities, repaired completion sinks/events, and audit starts. |
| `d02362927` | Missing intent/gate starts, skip cases, and sink-bearing direct-call guard. |

- Final full suite: `.venv/bin/python -m pytest tests/ -q -n auto` —
  **14,570 passed, 67 skipped**, 82.65 seconds.
- Final focused writer/intent/gate suite: **267 passed**.
- Assessment-sink mutation: removing the sink makes the parametrized assessment
  case fail; restoration passes.
- Prompt-hash mutation: dropping the writer's forwarded hash makes the exact
  UTF-8/null regression fail; restoration passes.
- Intent-start mutation: removing the start makes both the functional intent
  case and the missing-start guard fail; restoration passes.
- Final reviews 5 and 6: independent `codex exec --model gpt-6.1-sol`,
  read-only, complete diff; two consecutive no-actionable-finding results on
  the final code. Static reviews, no test claims.

Raw logs and reports use `.tmp/token-ledger-recovery.*`; the durable assertions
and summarized results above remain useful without those transient files.
The global editable install still points at the older checkout. Replay calls
must keep explicitly selecting this clone through `PYTHONPATH`; this recovery
does not change another checkout or the global installation.


### Pickup

The logging recovery is implemented, tested, and review-converged in this clone.
Publication uses `fix/token-ledger-logging-recovery` from `origin/main`,
with the unrelated extensionless-file backlog note excluded. The owner
authorizes publication on 2026-10-16; merge remains an owner action. The original untracked
reverted-attempt handoff remains untouched. The isolated Integration replay remains
at its separate observation-index design decision; logging recovery does not
approve that pending scope choice or mutate the application repository.


### Publication mapping (2026-10-16 provenance)

The dedicated branch preserves the reviewed production and test files exactly.
The reviewed source commits map to publication commits as follows:

| Reviewed source | Publication |
| --- | --- |
| `83cfdf9aa` | `419bb93e0` |
| `4d80e5fba` | `25fae15f8` |
| `d02362927` | `5f977dfac` |

`changelog.d/token-ledger-logging-recovery.md` describes the visible log changes.
This owner-tracked repair has no Jira ticket; BACKLOG #176/#177 remain separate.

## Project model selection implementation

*Opened 2026-11-12.*

The implementation branch is `implement/project-model-selection`, based on
`d858703b1` (merged plan PR #193). All four steps are done. Project backend
defaults and backend-scoped command models ship through the existing reader,
selector, and CLI; documentation and bundled routers share that contract.
Backlog #254 is reconciled; copied-skill freshness remains #525.

### Execution and verification

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

### Independent code reviews

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

### Review loop (PR 195)

Report-and-fix loop over `d858703b1..HEAD`, `/code-review` at `high`. Logs:
`.tmp/project-model-selection.review-loop-r*.test.log`.

#### Review pass 1 — 9 findings

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

#### Review pass 2 — 7 findings over `1b6ac78e0..3241029f3`

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

#### Review pass 3 — 5 findings over `3241029f3..d9c3da09d`

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

#### Review pass 4 — 7 findings over `d9c3da09d..4442d6851`

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

#### Review pass 5 — 7 findings over `bff5e3d78..e87406e44`

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

#### Review pass 6 — `/code-review high` findings over `e87406e44..HEAD` (2026-11-13)

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
   **Disposition:** **Fixed** — the checkpoints section now sits after all of Gate 1 and before Gate 2; Gate 1's remaining paragraphs are back under its heading.
2. **[CONFIRMED, low, docs-contradiction] `docs/BACKENDS.md` ~217 — the cursor
   paragraph still says project `default_backend: "cursor"` fails fast with exit
   127**, false now for `list`, `status`, `validate`. `RUNBOOK.md` ~3599 and
   `BACKENDS.md` ~100 are similarly unqualified. Suggested fix: qualify or
   point at the shared paragraph.
   **Disposition:** **Fixed** — the cursor paragraph and `BACKENDS.md` ~100 qualify the exemption; `RUNBOOK.md` carries the same qualifier.
3. **[PLAUSIBLE, low, altitude/consistency] `plan_tool/cli/app.py` ~628 — the
   hardcoded `{"list","status","validate"}` omits `root`**, another handler
   `inspect.py` documents as never calling a backend; `plan-tool root` still
   exits 127 with a missing project-default binary. The set is also a second
   source of truth. Suggested fix: add `root`, record `root` as a deliberate
   exclusion with its reason, or derive the set from the inspection group.
   **Disposition:** **Fixed** — `root` joins the exemption set (same defect, same never-calls-a-backend property); the matrix test gains a `root` row. The set stays a literal, not derived from the inspection group.
4. **[CONFIRMED, low, test-hygiene] `tests/cli/test_app.py` ~330 — the
   rewritten parametrized test has `expected` always 0**, leaving a dead `127`
   branch, an unused `EXEC_NOT_FOUND_EXIT` import, and rows duplicating
   `test_only_project_defaults_skip_missing_binary_for_inspection_commands`.
   The unique row is `codex` + `--model claude-sonnet-4-5` (model-only Claude
   stays lazy). Suggested fix: drop `expected`, assert `== 0`, keep and name
   the model-inference row.
   **Disposition:** **Fixed** — the dead `expected`/`127` branch and `EXEC_NOT_FOUND_EXIT` import are gone; the one unique row is kept and named for model-only Claude inference.
5. **[PLAUSIBLE, low, guidance] `DIRECTIVES.md` ~279 — the omit-flags rule keys
   on `backends.json` existing, not on what it configures.** A file that only
   overrides one binary path leaves `create`/`roadmap` on the provider default
   instead of the recommended strongest tier. Pass 5 chose file-existence
   deliberately; the question is whether to record the residual case. Suggested
   fix: key the rule on `default_backend` or a command model, or document the
   limitation.
   **Disposition:** **Fixed by documenting** — the rule stays keyed on file existence (the pass-5 decision); the directive now states the residual case and tells the operator to pass `--model` explicitly there.

#### Convergence status

Six passes. Pass 6's medium finding (misplaced DIRECTIVES section) and four low
findings are dispositioned above. No pass 7 has run: pass 6 carried a material
finding, so the two-consecutive-low-yield condition is unmet; the user chose to
stop after applying the fixes (2026-11-13). Passes 2–4 re-seeded on the per-flag selection paragraph, which was
removed; pass 5 then found its replacement ("always pass explicit flags")
overrode project configuration, contradicting the plan's requirement that
skill-driven invocations defer to it. The guidance is now one file-existence
rule (2026-11-12): with `.plan-tool/backends.json`, omit `--backend` and
`--model`; without it, pass the recommendations. The plan body and step 4
detail already say this and need no edit. Deterministic commands take neither
flag; `996afd895` exempts those commands from project-default eager preflight. Pass 1's material findings
(docstrings, case normalization) have not recurred. A sixth pass over the
file-existence rule has not run.


### Follow-up #526 — project-default inspection preflight

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
