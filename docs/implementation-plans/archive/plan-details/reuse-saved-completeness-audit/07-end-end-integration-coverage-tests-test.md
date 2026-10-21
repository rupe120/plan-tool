> **Auto-archived**: this plan was swept on 2026-06-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — End-to-end `main(['completeness-audit', …])` reuse coverage in `tests/test_cli.py`

## Summary

- Add one integration test class (`TestCompletenessAuditReuseEndToEnd`) to `tests/test_cli.py` that drives the reuse feature through `main(['completeness-audit', …])` twice per scenario — a first run that persists a fingerprinted `-completeness.json` sidecar, then a second run that consumes it — with the **real** `resolve_reusable_audit` (steps 5–6) reading the real sidecar, only the conceptual Claude seam stubbed.
- **Foundational test predicate:** count conceptual Claude calls by wrapping `plan_tool.review.shell_review_invoker` in a call-recording stub. Fresh reuse must add **zero** new conceptual calls; every staleness/decline path must add **≥1** (a fresh re-audit). Both `_sample_conceptual_audit` (`plan_tool/cli/completeness_phases.py`) and `_run_iterate_convergence_loop` (`plan_tool/cli/completeness_cmd.py`) body-local-import that seam from `plan_tool.review`, so one patch covers audit-only and `--iterate` paths.
- **Load-bearing decision:** these tests do **not** patch `resolve_reusable_audit` — that is step 6's unit-test seam; step 7 exercises the producer/consumer end to end across the save→reload fingerprint boundary, which is the only place the real sidecar persistence (steps 1–4) and the real verdict (step 5) are proven together.
- **Scope:** `tests/test_cli.py` only — no production code. Mirrors the existing `TestCmdCompletenessConceptWiring` seed/stub conventions in the same file.
- **On green:** ~9 new integration tests cover fresh-reuse (zero conceptual calls), stale-re-audit on plan edit and on code edit, deleted-in-scope-file flagging, the `--no-reuse-audit` / `--reuse-audit-id` matrix, and the `--iterate` reuse path — each asserting the conceptual-call delta and the operator-facing output.

## Table of Contents

- [Why](#why) — what end-to-end reuse coverage the unit tests leave unproven.
- [Files (creates vs edits)](#files-creates-vs-edits) — the single test file edited.
- [Implementation](#implementation) — the test class, the conceptual-call counter, the two-run harness, and each scenario.
- [Tests](#tests) — the enumerated cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — pytest/argparse docs and the in-repo seams these tests drive.
- [Deferred](#deferred) — docs updates and non-completeness reload paths left to later steps.

## Why

Steps 1–6 built and unit-tested every layer of completeness-audit reuse in isolation: `tests/test_review_persistence.py` round-trips the fingerprints, `tests/test_completeness_report.py` covers `resolve_reusable_audit`'s verdict, and `tests/cli/test_completeness_cmd.py` covers `_resolve_audit_reuse` / `_warn_code_drift` with `resolve_reusable_audit` **patched**. No test yet drives the real chain — `_persist_and_present_report` writing a fingerprinted sidecar (steps 1–4), then a second `main()` invocation's `resolve_reusable_audit` reading it back, recomputing fingerprints off real disk state, and `cmd_completeness` substituting the saved recs for a fresh `audit_plan_until_stable` call. The seam most likely to silently break — fingerprint *equality across a save/reload boundary* (a digest that doesn't reproduce, a sidecar written without fingerprints, a stale-detection miss) — is exactly the seam unit patching hides. This step closes that gap with `main()`-level integration tests that count conceptual Claude calls to prove reuse actually skips the expensive axis while the deterministic battery still runs.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `tests/test_cli.py` — add one `@pytest.mark.integration` class `TestCompletenessAuditReuseEndToEnd` with a `_seed_plan` helper, a conceptual-call-counting `shell_review_invoker` stub fixture, and the ~9 two-run scenario tests. Place it after the existing `TestCmdCompletenessConceptWiring` class (the seed/stub conventions it mirrors).

## Implementation

### `tests/test_cli.py`

**Class `TestCompletenessAuditReuseEndToEnd` (`@pytest.mark.integration`).** Mirror the existing `tests/test_cli.py:TestCmdCompletenessConceptWiring` class for plan seeding and invoker stubbing. All cases hermetic on `tmp_path`; no real Claude (the autouse gate in `tests/conftest.py` raises if a real backend binary spawns). When mirroring the neighbor, do not copy its docstring's stale `.plan-tool/reviews/<slug>/` sidecar path; the real location is `plan-details/<slug>/reports/`.

**`_seed_plan(tmp_path)` helper.** Copy `TestCmdCompletenessConceptWiring._seed_plan` verbatim in shape:
- Write `tmp_path/plans/1-concept-test.md` — one step whose `files:` lists `foo.py`, full required H2 body (`## Overview` … `## Deferred`) plus a concrete `## Acceptance criteria` so the conceptual audit has both inputs.
- Write `tmp_path/foo.py` (`def bar(): return 41`) — the in-scope `step.files` code file whose bytes the **code fingerprint** (`compute_code_fingerprint` over `scope_guard.compute_drift_watched_paths`) covers. Editing/deleting it is the code-drift lever.
- Return the `plans_dir` `Path`.

**Conceptual-call counter fixture.** Add a helper that installs a recording stub and hands back the call list:
- `monkeypatch.setattr(plan_tool.review, "shell_review_invoker", recorder)` where `recorder(prompt)` appends to a `calls` list and returns a **stable** two-section block (`## Correctness findings\n\n_(none)_\n\n## Completeness findings\n\n_(none)_\n`) so `plan_tool/review.py:audit_plan_until_stable` converges in its minimum rounds. Stability matters only for the absolute first-run count; assertions compare **deltas**, never absolute counts.
- Snapshot `before = len(calls)` immediately before the *second* `main()` call; assert `len(calls) == before` (reuse) or `len(calls) > before` (re-audit) after it.
- Patch the canonical module attribute `plan_tool.review.shell_review_invoker` (both consumers import it body-local from `plan_tool.review`, per `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit` and `plan_tool/cli/completeness_cmd.py:_run_iterate_convergence_loop`), so the single patch intercepts both the audit-only and `--iterate` paths.

**Two-run harness (the shared shape of every scenario).**
1. **Run 1 — seed the sidecar.** `main(['--repo-root', str(tmp_path), '--plans-dir', str(plans_dir), 'completeness-audit', 'concept-test'])` (audit-only; persists the grouped report **and** the JSON sidecar with both fingerprints via `plan_tool/cli/completeness_phases.py:_persist_and_present_report` → `write_completeness_report` → `save_review`). Assert a `-completeness.json` sidecar now exists under `tmp_path/plans/plan-details/concept-test/reports/`.
2. **Mutate (scenario-specific):** edit the plan body, rewrite `foo.py`, delete `foo.py`, or leave untouched.
3. **Run 2 — exercise reuse:** `main([… , 'completeness-audit', 'concept-test', '--reuse-audit', '--yes', …])`; assert the conceptual-call delta and the operator output.

**Why `--reuse-audit` (True), not the unset default.** `--reuse-audit` sets `args.reuse_audit=True` → reuse-when-fresh **without** prompting (`plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse` policy: `reuse_audit is True → reuse`). Avoids depending on the `not sys.stdin.isatty()` auto-accept branch under pytest capture. `--yes` is still passed where the `--iterate` apply loop needs non-interactive consent.

**Sidecar-stem capture (for `--reuse-audit-id`).** After run 1, `stem = next(reports_dir.glob('*-completeness.json')).stem` (form `<ts>-completeness`). Step 5's `resolve_reusable_audit` accepts both the bare `<ts>` and the full `<ts>-completeness` stem as `review_id`, so pass `stem` directly to `--reuse-audit-id`.

**Reading operator output.** Use `capsys.readouterr()` after run 2. The reuse line, the plan-stale note, and the code-drift warning are expected on **stderr** (`plan_tool/cli/completeness_cmd.py:_resolve_audit_reuse` / `_warn_code_drift` write via `error`/`warn`/`tool(..., stream=sys.stderr)`); the grouped/concise report goes to stdout. Assert against the correct stream. **Confirm the exact emitted substrings and stream routing against step 6's `_resolve_audit_reuse` / `_warn_code_drift` as implemented** — the strings named throughout this step (`reusing saved conceptual audit`, the plan-stale note, the attributed `(step 1: …)` drift line, the unmatched-`--reuse-audit-id` error note) and the stderr-vs-stdout split are this step's predicted phrasing of step 6's output, not a contract. Read the real implementation before pinning each assertion and substitute the actual wording/stream where it differs; assert on the smallest stable fragment that proves the behavior (presence/absence of reuse, staleness re-audit, per-file attribution) rather than a brittle full-line match. Assert `rc == 0` exactly (not the looser `rc in (0, 1)` hedge at `tests/test_cli.py:5808`/`5852`): a completed audit always exits 0 per the exit-code convention documented in `test_human_report_renders_audit_sections` ("a completed audit exits 0; the medium+ finding is surfaced in the report, not the exit code").

**Determinism note — same-second saves.** Run 2 also calls `_persist_and_present_report`, re-writing a sidecar. `_timestamp_filename` is second-precision, so a same-second run 2 overwrites run 1's file at the identical stem (harmless — fingerprints unchanged on reuse). Capture run 1's stem *before* run 2 for the id test; never assert on sidecar file *count* across runs.

## Tests

All in `tests/test_cli.py::TestCompletenessAuditReuseEndToEnd`. Each is one two-run scenario; the conceptual-call delta is the load-bearing assertion.

- `test_fresh_reuse_makes_zero_conceptual_calls` — run 1 persists the sidecar; unchanged plan+code; run 2 `--reuse-audit --yes` → conceptual-call delta `== 0`, rc `0`, and a `reusing saved conceptual audit` line on stderr.
- `test_reuse_re_audits_on_plan_edit` — between runs, append text to the plan body (changes `compute_plan_fingerprint`) → run 2 conceptual-call delta `>= 1`; stderr carries the one-line plan-changed/stale note and **no** `(step` attributed file line.
- `test_reuse_re_audits_on_code_edit` — between runs, rewrite `foo.py` (changes `compute_code_fingerprint`) → run 2 conceptual-call delta `>= 1`; stderr names `foo.py` as `… (step 1: …)` and includes the `detail --reconcile` recovery hint (`drift_detection.reconcile_drift_hint("completeness")`).
- `test_reuse_flags_deleted_in_scope_file` — between runs, delete `foo.py` (key present in saved `code_fingerprint`, absent now) → run 2 lists `foo.py` in the attributed code-drift warning and re-audits (delta `>= 1`), proving the deletion-aware saved-vs-current diff (step 5) fires across the boundary, unlike live `check_drift`.
- `test_no_reuse_audit_always_re_audits` — unchanged plan+code; run 2 `--no-reuse-audit` → conceptual-call delta `>= 1` (fresh audit despite a fresh sidecar); no `reusing saved conceptual audit` line.
- `test_reuse_audit_id_pins_saved_sidecar` — capture run 1's `<ts>-completeness` stem; run 2 `--reuse-audit-id <stem> --yes` on unchanged state → delta `== 0` (the pinned save is reused).
- `test_reuse_audit_id_miss_audits_fresh` — run 2 `--reuse-audit-id 20000101-000000-completeness` (no such save) → conceptual-call delta `>= 1` and an error note on stderr naming the unmatched stem; rc `0` (decline ≠ failure-to-complete).
- `test_iterate_reuse_skips_audit_call` — run 1 `--iterate --yes` persists the sidecar; unchanged state; run 2 `--iterate --yes --reuse-audit` → conceptual-call delta `== 0` (the up-front `audit_plan_until_stable` is skipped), rc `0`.
- `test_deterministic_battery_runs_on_reuse` — seed the plan with a guaranteed deterministic finding (e.g. a `_(TODO)_` section per `test_iterate_continues_partial_plan_without_round0_rewrite`); on the fresh-reuse run (delta `== 0`), assert that specific deterministic finding appears in the run's output, proving `_run_deterministic_checks` (`plan_tool/cli/completeness_phases.py`) is **never** gated by reuse (only the conceptual Claude axis is). A report-file-exists check alone is insufficient — `_persist_and_present_report` writes the report regardless, and the clean `_seed_plan` surfaces no deterministic findings to observe.

### Test-creation order (feature step)

This is a **feature** step — it adds new end-to-end behavior coverage that lands with steps 1–6's implementation. Author all ~9 tests above and run them against the implemented stack. **Green-before-done gate:** every new test must pass under `uv run pytest tests/test_cli.py::TestCompletenessAuditReuseEndToEnd -q` (and the whole suite stay green) before this step is considered finished. Because the class is `@pytest.mark.integration`, it is also exercised by `uv run pytest -m integration tests/ -q`.

## Acceptance criteria

- A second `main(['completeness-audit', 'concept-test', '--reuse-audit', '--yes'])` on an unchanged plan+code adds **zero** calls to the stubbed `plan_tool.review.shell_review_invoker` and prints a `reusing saved conceptual audit` line to stderr, exiting `0`.
- Editing the plan body between runs makes run 2 add `>= 1` conceptual call and emit the plan-stale note with no per-file attribution.
- Editing **or deleting** the in-scope `foo.py` between runs makes run 2 add `>= 1` conceptual call and emit an attributed `(step 1: …)` warning closed by the `detail --reconcile` hint.
- `--no-reuse-audit` adds `>= 1` conceptual call on an otherwise-fresh sidecar and prints no reuse line.
- `--reuse-audit-id <captured-stem>` reuses (zero added calls); a non-matching `--reuse-audit-id` adds `>= 1` call and prints an error note naming the stem, rc `0`.
- The `--iterate --reuse-audit` second run adds zero conceptual calls (skips `audit_plan_until_stable`) yet still runs the deterministic battery and writes a report.
- All ~9 tests pass under `uv run pytest tests/test_cli.py::TestCompletenessAuditReuseEndToEnd -q`; the existing `TestCmdCompletenessConceptWiring` cases stay green.

## References

- [pytest — monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — `monkeypatch.setattr(plan_tool.review, "shell_review_invoker", …)` to install the conceptual-call counter and `monkeypatch.setattr` for `sys.stdin.isatty` if a prompt-path case is added.
- [pytest — capsys](https://docs.pytest.org/en/stable/how-to/capture-stdout-stderr.html) — splitting the stdout grouped report from the stderr reuse/stale/drift notes.
- `plan_tool/cli/completeness_cmd.py` (in-repo) — `cmd_completeness`, `_resolve_audit_reuse`, `_warn_code_drift`, and `_run_iterate_convergence_loop`'s `reused_audit_recs=` gate (step 6); the flags `--reuse-audit`/`--no-reuse-audit`/`--reuse-audit-id` registered on `p_completeness`.
- `plan_tool/cli/completeness_phases.py` (in-repo) — `_persist_and_present_report` (writes the fingerprinted sidecar), `_sample_conceptual_audit` (audit-only conceptual call), and `_run_deterministic_checks` (the never-gated battery) driven end-to-end here.
- `plan_tool/completeness_report.py` (in-repo) — `resolve_reusable_audit` and `compute_plan_fingerprint`/`compute_code_fingerprint`, run **unpatched** so the real save→reload fingerprint comparison is exercised.

## Deferred

- `docs/AUDIT_RESUME_FLOW.md` / `RUNBOOK.md` updates for the new flags + code-drift warning — step 8 (docs), not this test step.
- Interactive prompt-path coverage (TTY, `builtins.input` accept/decline) — already unit-tested in `tests/cli/test_completeness_cmd.py` (step 6); these end-to-end tests force the non-prompt `--reuse-audit`/`--yes` branches to stay deterministic under pytest capture.
- Code-fingerprint staleness on non-completeness reload paths (`run` / `review` / `jira`) — out of scope per the plan's "Out of scope"; the fingerprint lives only in the completeness sidecar.
- `--json`-mode reuse assertions — the JSON envelope shape is covered by `TestCmdCompletenessConceptWiring.test_json_output_includes_plan_audit_key`; reuse behavior is axis-agnostic to output format, so it is not re-tested per format here.
