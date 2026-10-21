> **Auto-archived**: this plan was swept on 2026-06-14 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — End-to-end reconcile-reuse coverage in `tests/test_cli.py`

## Summary

- **Adds `main([...])`-level integration coverage** for fingerprint-gated reconcile reuse across all three reconcile-family commands — `reconcile-plan`, `reconcile-code`, and `detail --reconcile` — each driven **twice** (seed sidecar, then reuse run) through a stubbed conceptual-Claude seam.
- **Primary (and only) file:** `tests/test_cli.py`. Three new `@pytest.mark.integration` classes mirror `tests/test_cli.py:TestCompletenessAuditReuseEndToEnd` member-for-member, swapping its `shell_review_invoker` counter for the two reconcile-family seams.
- **Load-bearing decision:** run steps 1–5's producers (`compute_plan_fingerprint`, `compute_code_fingerprint`, `resolve_reusable_reconcile`, the `_prompt_reuse_saved` freshness gate, `_warn_reuse_code_drift`, the inline `_prompt_reuse_saved_review` gate) **unpatched** across the real save→reload boundary; stub **only** the conceptual seam — `plan_tool.cli.review_cmd.review_plan_full` (reconcile-plan) and the injected `invoker` inside `plan_tool.cli.reconcile.run_step` (reconcile-code / detail --reconcile). Re-patching `resolve_reusable_reconcile` (steps 3–4's unit seam) would re-hide exactly the boundary this step exists to prove.
- **The single asserted predicate is the DELTA in conceptual calls between run 1 and run 2:** fresh reuse adds **0**, every staleness/decline/`--no-reuse`/`--reuse-id`-miss path adds **≥1**.
- **On green:** unchanged plan+code reuses with zero new Claude calls; a plan edit, an in-scope code edit, or a deleted in-scope file each re-audits (the latter two emitting the attributed `path (step N: title)` warning on stderr); `--no-reuse` always re-audits; `--reuse-id STEM` reuses a pinned fresh save and re-audits on a miss.

## Table of Contents

- [Why](#why) — what unit-patched steps 1–5 never exercise
- [Files (creates vs edits)](#files-creates-vs-edits) — the one test file, three new classes
- [Implementation](#implementation) — the seams, the recorders, the matrix per command
- [Tests](#tests) — the per-command scenario list
- [Test-creation order (feature step)](#test-creation-order-feature-step) — author-with-green-gate
- [Acceptance criteria](#acceptance-criteria) — observable delta/stream checks
- [References](#references) — the completeness template and the seam docs
- [Deferred](#deferred) — what this step deliberately does not cover

## Why

Steps 1–5 each unit-test their layer by **patching the adjacent seam**: step 2 patches `save_review`, step 3 drives `resolve_reusable_reconcile` directly, step 4 patches the resolver, step 5 asserts parse contracts. No prior step runs the whole chain — a code fingerprint that fails to reproduce across a save/reload, a reconcile sidecar written without `code_fingerprint` at one of the six seams (step 2), or a stale-detection miss across the save→reload boundary all survive every unit test. This step's whole value is running steps 1–5's producers **against the real on-disk persistence**, stubbing only the single expensive/non-deterministic leaf (the conceptual Claude call), so the real `compute_plan_fingerprint`/`compute_code_fingerprint` recompute and the deletion-aware `changed|deleted|new` diff fire end-to-end. It is the reconcile-family analog of `tests/test_cli.py:TestCompletenessAuditReuseEndToEnd`, which proved the same boundary for `completeness-audit`.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `tests/test_cli.py` — add three `@pytest.mark.integration` classes, placed after `tests/test_cli.py:TestCompletenessAuditReuseEndToEnd` (the canonical reuse-end-to-end home; per the captured convention, `main([...])`-level reconcile-reuse cases belong here, **not** in `tests/cli/test_reconcile_engine.py`, which is the helper-altitude unit home):
    - `TestReconcilePlanReuseEndToEnd` — drives `main(['--repo-root', …, 'reconcile-plan', <slug>, …])`; conceptual seam `plan_tool.cli.review_cmd.review_plan_full`.
    - `TestReconcileCodeReuseEndToEnd` — drives `main([…, 'reconcile-code', <slug>, '--step', '1', …])`; conceptual seam the injected `invoker` inside `plan_tool.cli.reconcile.run_step`.
    - `TestDetailReconcileReuseEndToEnd` — drives `main([…, 'detail', <slug>, '--reconcile', '--step', '1', …])`; same `run_step` seam as reconcile-code.

## Implementation

### Shared scaffolding (module-level helpers near the new classes)

- **`_seed_reconcile_plan(tmp_path)`** — mirror `TestCompletenessAuditReuseEndToEnd._seed_plan`: a plan `plans/1-reconcile-test.md` whose step 1 declares `files: [foo.py]` plus the on-disk `foo.py` (the code-fingerprint lever), the full nine-H2 body `_seed_plan` writes (Overview, Problem statement, Architecture, Steps, Out of scope, Risks, Testing, Acceptance criteria, Deferred), `status: done` on the step so the reconcile audit is eligible. `foo.py` is the single in-scope code surface that `compute_code_fingerprint` hashes via `scope_guard.compute_drift_watched_paths`.
- **`_reports_dir(tmp_path)`** — `tmp_path / "plans" / "plan-details" / "reconcile-test" / "reports"` (the `plan_reports_dir` location from `plan_tool/review_persistence.py:plan_reports_dir`).
- **`_argv(tmp_path, plans_dir, command, *extra)`** — assemble `["--repo-root", str(tmp_path), "--plans-dir", str(plans_dir), command, "reconcile-test", *extra]`. For reconcile-code the per-command extras carry `--step 1`; only the `detail` class adds `--reconcile` (the `reconcile-code` subparser defines no `--reconcile` flag).

### Conceptual-seam recorders (the only stub per command)

- **reconcile-plan → patch `plan_tool.cli.review_cmd.review_plan_full`.** `plan_tool/cli/review_cmd.py:cmd_review` calls it directly only **after** `_prompt_reuse_saved_review` declines reuse, so a recorder that appends to a `calls` list and returns a minimal `ReviewResult` (`from plan_tool.review import ReviewResult` — `report=`, `recommendations=[]`, `dry_run=False`) makes run 1 persist a fingerprinted `<ts>.json` (kind `"review"`, no suffix) and run 2's delta reveal reuse-vs-re-audit. Fresh reuse → `review_plan_full` never called → delta 0.
- **reconcile-code / detail --reconcile → patch `plan_tool.cli.reconcile.run_step`** with the established inject-a-fake-invoker pattern from `tests/test_cli.py:TestCmdRunAll.test_happy_path_sweeps_until_plan_complete`: wrap `launcher_module.run_step`, set `kwargs["invoker"] = recorder` (recorder appends the prompt and returns the `(exit_code, stdout)` tuple `Invoker` produces — `(0, <stdout>)`, where `<stdout>` reuses the `## Summary` + `## Validation` shape from `tests/test_cli.py:_run_all_ok_stdout` — enough for a completing rc-0 run, though it carries no `## Findings` block so `summarize_findings` returns `parsed=False`; mirrors the `lambda prompt: (0, _run_all_ok_stdout())` form in the cited `TestCmdRunAll` pattern), then call the original. Both `plan_tool/cli/reconcile.py:_cmd_run_reconcile` and `:_run_detail_reconcile_path` skip `run_step` when their reuse prompt (`_prompt_reuse_saved_run_reconcile` / `_prompt_reuse_saved_detail_reconcile`, both delegating to `_prompt_reuse_saved`) returns a path — so fresh reuse → zero recorder calls.

### Per-command matrix (each class)

Each class repeats the same six-to-seven scenario shape, all using **delta counting** (`before = len(calls)` immediately before run 2, then `> before` or `== before`) — never absolute counts, since the stub's per-call convergence is irrelevant and same-second saves overwrite at an identical stem:

1. **`test_fresh_reuse_makes_zero_conceptual_calls`** — seed sidecar, edit nothing, run 2 with `--reuse` `--yes`. Delta `== before`; assert the reuse note (`"walking saved"` — emitted by `review_cmd.py:_prompt_reuse_saved_review` ("(--yes) walking saved review") for `TestReconcilePlanReuseEndToEnd`, and by the `--yes` core path in `reconcile.py:_prompt_reuse_saved` for the other two classes; the substring holds for all three) on **stdout** per the stream split (reuse-acceptance notes print to stdout; `.err` is reserved for the stale/drift notes in scenarios 2/3/4).
2. **`test_reuse_re_audits_on_plan_edit`** — append prose to the plan after run 1 (changes `compute_plan_fingerprint`), run 2 `--reuse --yes`. Delta `> before`; assert the plan-stale note and **no** `(step 1:` attribution (drift is plan-side).
3. **`test_reuse_re_audits_on_code_edit`** — rewrite `foo.py` body after run 1 (changes `compute_code_fingerprint`), run 2 `--reuse --yes`. Delta `> before`; assert `"foo.py (step 1:"` and the `--reconcile` hint on stderr (the `_warn_reuse_code_drift` / `_print_attributed_files` + `reconcile_drift_hint` output for reconcile-code/detail; the inline `_prompt_reuse_saved_review` warning for reconcile-plan).
4. **`test_reuse_flags_deleted_in_scope_file`** — `(tmp_path / "foo.py").unlink()` after run 1, run 2 `--reuse --yes`. Delta `> before`; assert `"foo.py (step 1:"` on stderr — proving the `changed|deleted|new` save→reload diff treats deletion as genuine staleness (opposite of the same-process live differ).
5. **`test_no_reuse_always_re_audits`** — run 2 with `--no-reuse` over a fresh sidecar. Delta `> before`; assert the reuse note is **absent**.
6. **`test_reuse_id_pins_saved_sidecar`** — capture the sidecar stem **before run 2** (timestamp collision: same-second saves overwrite), run 2 `--reuse-id <stem> --yes` on unchanged state. Delta `== before` (pinned fresh save reused).
7. **`test_reuse_id_miss_audits_fresh`** — run 2 `--reuse-id 20000101-000000-… --yes` matching no save. Delta `> before`; assert the unmatched stem string appears on stderr; rc stays 0 (a decline is not a failure-to-complete).

- **Force the tri-state flag explicit values, never the unset/prompt default.** Drive `--reuse` / `--no-reuse` / `--reuse-id` (plus `--yes`) — under pytest, `sys.stdin.isatty()` is false, so the unset default silently takes the non-interactive decline branch in `_prompt_reuse_saved`; an integration test relying on it would test the capture environment, not the feature. The interactive `_ask_reuse_saved` / `builtins.input` path stays in the step-3/4 unit tests.
- **Per-command sidecar suffix differs** — reconcile-plan writes `<ts>.json` (bare), reconcile-code writes `<ts>-run-reconcile.json`, detail --reconcile writes `<ts>-detail-reconcile.json` (per `plan_tool/review_persistence.py:_timestamp_filename`). Each class's seed-assert globs its own suffix; never assert on file **count** across the two runs.
- **rc is 0 on every run** (seed and reuse) — the exit-code convention: reconcile subcommands exit non-zero only on failure-to-complete, never on findings/decline.

## Tests

All cases live in `tests/test_cli.py` (the three new classes). Each line is one test:

`TestReconcilePlanReuseEndToEnd`
- `test_fresh_reuse_makes_zero_conceptual_calls` — unchanged → `review_plan_full` delta 0, reuse note on stdout, rc 0.
- `test_reuse_re_audits_on_plan_edit` — plan-body append → delta ≥1, plan-stale note, no `(step 1:`.
- `test_reuse_re_audits_on_code_edit` — `foo.py` rewrite → delta ≥1, `foo.py (step 1:` + `--reconcile` hint on stderr.
- `test_reuse_flags_deleted_in_scope_file` — `foo.py` deleted → delta ≥1, `foo.py (step 1:` on stderr.
- `test_no_reuse_always_re_audits` — `--no-reuse` → delta ≥1, no reuse note.
- `test_reuse_id_pins_saved_sidecar` — pinned stem, unchanged → delta 0.
- `test_reuse_id_miss_audits_fresh` — unmatched stem → delta ≥1, stem named on stderr, rc 0.

`TestReconcileCodeReuseEndToEnd` — same seven cases, command `reconcile-code … --step 1`, seam `run_step` injected invoker, sidecar `*-run-reconcile.json`.

`TestDetailReconcileReuseEndToEnd` — same seven cases, command `detail … --reconcile --step 1`, seam `run_step` injected invoker, sidecar `*-detail-reconcile.json`.

### Test-creation order (feature step)

This is a **feature** step — new end-to-end behavior coverage. Author all 21 cases **with** the test scaffolding (the three `_seed_*`/`_reports_dir`/`_argv` helpers and the two recorder styles), one command class at a time:

1. **`TestReconcilePlanReuseEndToEnd`** first — its `review_plan_full` recorder is the simplest seam (canned `ReviewResult`, no invoker injection). Covers fresh-reuse delta 0 and the four staleness/decline deltas.
2. **`TestReconcileCodeReuseEndToEnd`** — introduce the `run_step` inject-a-fake-invoker recorder; covers the same matrix through the step-scoped `resolve_reusable_reconcile` path.
3. **`TestDetailReconcileReuseEndToEnd`** — reuse the `run_step` recorder; proves the detail-side wrapper shares the gate.

**Green-before-done gate:** every one of the 21 new tests must pass under `uv run pytest -m integration tests/test_cli.py -q` (and the full `uv run pytest tests/ -q`) before this step is finished. A red case means a real gap in steps 1–5's chain (a save seam missing the fingerprint, a non-reproducing digest, a deletion the diff ignored) — fix the producer, not the test.

## Acceptance criteria

- All three new classes are collected under `@pytest.mark.integration` and pass: `uv run pytest -m integration tests/test_cli.py -q` is green.
- For each of the three commands: the fresh-reuse case asserts **zero** new conceptual-seam calls (delta `== before`) and the reuse note on `capsys.readouterr().out`.
- For each command: the code-edit and deleted-file cases assert `"foo.py (step 1:"` on stderr and a conceptual-call delta `≥1`.
- For each command: the plan-edit case asserts a plan-stale note, no `(step 1:` attribution, and delta `≥1`.
- For each command: `--no-reuse` yields delta `≥1` and no reuse note; `--reuse-id <fresh-stem>` yields delta `0`; `--reuse-id <missing-stem>` yields delta `≥1`, names the stem on stderr, and rc 0.
- No test patches `resolve_reusable_reconcile`, `compute_plan_fingerprint`, `compute_code_fingerprint`, or `save_review`/`load_review` — only the conceptual seam (`review_plan_full` or the `run_step` invoker) is stubbed.
- The full suite stays green serially and under `-n auto`: `uv run pytest tests/ -q` and `uv run pytest tests/ -q -n auto`.

## References

- `docs/implementation-plans/2-reuse-saved-completeness-audit.md` (in-repo) — the template plan; `tests/test_cli.py:TestCompletenessAuditReuseEndToEnd` is the structural model these three classes mirror.
- `plan_tool/review_persistence.py` (in-repo) — `plan_reports_dir`, `_timestamp_filename` (the per-kind sidecar suffixes), and `save_review`/`load_review`, the real save→reload boundary the tests exercise unpatched.
- [pytest — monkeypatch fixture](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — `setattr` of the conceptual seams and `capsys` for the stderr/stdout stream-split assertions.

## Deferred

- **The interactive prompt / TTY accept-decline path** (`_ask_reuse_saved`, `builtins.input`) — stays in the step-3/4 unit tests under `tests/cli/test_reconcile_engine.py`; the integration cases force `--reuse`/`--no-reuse`/`--reuse-id` to keep the branch deterministic under pytest's non-tty stdin.
- **The `--iterate` reconcile convergence loop** (`plan_tool/cli/reconcile.py:_iterate_reconcile_loop`) reuse interaction — out of scope here; this step covers the single-pass reuse decision. An iterate-reuse end-to-end case is a follow-up if step 5 wires reuse into the iterate path.
- **Parse-contract / default-is-None coverage for the three flags** — owned by step 5 across `tests/cli/test_run_cmd.py`, `tests/cli/test_authoring_cmds.py`, and `tests/cli/test_review_cmds.py`; not re-asserted here.
- **`reconcile-plan-walk` standalone apply surface** — a walk-of-saved entry point, distinct from the reuse decision under test; left to its existing `tests/test_review_walk.py` coverage.
