# Testing guide

This project ships tests across `tests/`. Some run in microseconds
(pure-function assertions); some take a meaningful fraction of a second
(full `main()` invocations with plan setup). We split the suite into
two tiers via a pytest marker:

- **Unit / component tests** — unmarked. Pure-function tests, helper
  isolation, single-module behavior. The default fast loop.
- **Integration tests** — marked `@pytest.mark.integration`. Drive
  `main()` or an orchestrator (`create_plan`, `generate_detail`,
  `cmd_completeness`, `_iterate_reconcile_loop`) and exercise multiple
  modules together through their real public API.

## Running

```bash
# Default: everything, serial. Use this to diagnose ordering or cleanup.
uv run pytest tests/ -q

# Preferred full-suite command — one worker per CPU core.
uv run pytest tests/ -q -n auto

# Profile the slowest focused tests before changing fixtures or coverage.
uv run pytest tests/path/to_test.py -q --durations=20

# Fast loop: unit/component only. Use this during development.
uv run pytest -m "not integration" tests/ -q

# Integration only. Use this when you've touched a conceptual area
# (see "When to run integration tests" below).
uv run pytest -m integration tests/ -q
```

### Suite-wide guardrails

- **Per-test timeout (30s default).** Configured in `pyproject.toml`
  via `pytest-timeout`. A test that exceeds the cap fails loudly
  instead of slowing the suite to a crawl. Genuinely long-running
  tests must opt in explicitly: `@pytest.mark.timeout(120)`.
- **Real-backend subprocess gate.** `tests/conftest.py` installs an
  autouse fixture that raises if any test tries to spawn a **registered
  backend binary** via `subprocess.run` / `subprocess.Popen`. The guard
  reads `backend.registered_binaries()`, so it blocks the real `claude`
  CLI *and* a real `codex` or `agent` shell-out (and any future backend) without
  editing the guard. The error message points to this section. To opt
  out for a test that legitimately exercises subprocess plumbing (with
  its own mocks): `@pytest.mark.allow_real_claude` (the existing marker —
  it gates every registered backend, not just claude).
- **Parallel safety.** Tests should be hermetic (each gets its own
  `tmp_path`); `-n auto` is a no-op for correctness. If a test fails
  only under `-n auto`, it has hidden shared state — fix the test,
  don't disable parallelism.
- **No inherited git repository.** `tests/conftest.py` unsets git's
  repo-local variables (`git rev-parse --local-env-vars`, e.g. `GIT_DIR`)
  when it loads. Started from a git hook or a worktree shell, they would
  aim every test's `git` call at the developer's real repository, which
  once registered test worktrees in this clone. It runs at import because
  session-scoped fixtures run `git init` / `git config` before any
  per-test fixture. The pre-push hook unsets the same variables before
  starting pytest; the conftest scrub covers every other way pytest starts.

## Backend fallback seams

Several production functions accept an `invoker=` kwarg that defaults
to a function shelling out to the **active backend's** CLI (the real
`claude` CLI by default, or `codex` when that backend is selected). A
test that forgets to override these defaults silently shells out to the
active backend — slow, non-deterministic, and tokens-burning. The
subprocess gate catches a leak to any registered binary, but the table
below is the seam-by-seam recipe so you know what to override. The rows
describe claude-defaulting orchestrators; they are unchanged by the
backend seam (the seam swaps argv/parsing under the same `invoker`):

| Production call site | Default invoker | How to neutralize in a test |
|---|---|---|
| `concept_tree.py` → `emit_concept_tree(invoker=...)` | `shell_concept_invoker` | Pass `invoker=lambda p: '{"concepts": [...]}'` with literal evidence excerpts for canned enrichment, or `lambda p: '{"concepts": []}'` for no enrichment. |
| `create.py` → `create_plan(claude_invoker=...)` | `shell_claude_invoker` | Pass `claude_invoker=lambda p: ...` returning canned JSON, OR autouse-stub `create_module.propose_steps_from_claude` / `propose_references_from_claude` at module scope. Seed-fed single-plan creates add `_propose_risk_profile_from_seed`; return its closed risk JSON when branching on the prompt, or stub that helper. `_offer_missing_intents` → `intent_proposal.propose_intents` is a fourth entry point that, under `yes=True`, skips its non-TTY guard and calls `claude_invoker`; pass `claude_invoker=`, or stub `create_module.propose_intents`. |
| `create.py` → post-write convergence calls `apply_finding` | `shell_invoker` | `monkeypatch.setattr(create_module, "apply_finding", lambda *a, **kw: _stub_apply_result())`. See `test_create.py` `_stub_apply_result`. |
| `create.py` → foundational-logic sweep — A/B SPLIT arm (`create_plan(foundational_invoker=...)` → `propose_steps_from_claude(foundational_invoker=...)`) | `None` (off) | **COMBINED is default** (the sweep is inlined as item 9 in the proposal). The CLI wires this only when `PLAN_TOOL_PROMPT_MODE=split`. In tests omit `foundational_invoker` for combined; pass `foundational_invoker=lambda p: ...` (sweep JSON, see `foundational_logic.py`) to exercise split. |
| `detail.py` → `generate_detail(invoker=...)` | `shell_detail_invoker` | Pass `invoker=lambda p: ...` returning a parseable detail body. |
| `detail.py` → foundational-logic sweep — A/B SPLIT arm (`generate_detail(foundational_invoker=...)`) | `None` (off) | **COMBINED is default** (inline grep directive + always-on self-check; no sweep). CLI wires this only under `PLAN_TOOL_PROMPT_MODE=split`. Pass `foundational_invoker=lambda p: ...` (sweep JSON) to exercise split; `render_detail_prompt(split_mode=True)` renders the split prompt directly. |
| `detail.py` → lesson extraction (`lessons_invoker=None` falls back to `shell.claude_invoke`) | `None` (off) | **`extract_lessons=False` is the default** — the seam is only live when a test opts in. Pass `extract_lessons=False` explicitly (the file convention), OR rely on the autouse `_stub_lessons_extraction` fixture in `test_detail.py`. |
| `detail.py` → post-write convergence calls `apply_finding` | `shell_invoker` | Stub `detail_module.apply_finding` (same pattern as `create_module`). |
| `launcher.py` → `run_step(invoker=...)` / `apply_finding(invoker=...)` | `shell_invoker` | Pass `invoker=` explicitly, OR `monkeypatch.setattr(launcher, "apply_finding", ...)` at the call site's module. |
| `cli/completeness_apply_parallel.py` → `apply_finding_in_tree(invoker=...)` → `apply_finding` (`completeness-apply --jobs N`) | `shell_invoker` | `monkeypatch.setattr(launcher, "apply_finding", ...)`, OR stub `completeness_apply_parallel.run_parallel_apply` / `apply_finding_in_tree` to bypass the pool entirely. |
| `cli/completeness_phases.py` → `_collect_purity_split_findings` → `detail.collect_detail_quality_findings(invoker=...)` (the per-step MIXED-STEP purity pass in `completeness-audit`'s deterministic phase) | `shell_detail_invoker` | `monkeypatch.setattr(detail_module, "collect_detail_quality_findings", lambda *a, **k: [])`. Fires for **any detailed code step**, so any test driving `completeness-audit` / `completeness-audit` on a plan with a detailed code step must stub it (bare/undetailed/non-code/done steps spend nothing). See `test_review.py::TestCmdCompleteness._stub_plan_audit_invoker`. |
| `roadmap.py` → `run_roadmap(invoker=...)` | `shell_roadmap_invoker` | Pass `invoker=lambda p: (0, '<closed stage operations JSON>')` for an enrolled predecessor with open feedback; assert its prompt excludes unrelated artifact bytes. Use a fail-on-call invoker for a feedback-free re-gate, which must not invoke or write. Drive the loop with an injected `stages=` table and temporary prompt directory containing `roadmap-stage-feedback-revision.md` plus its shared `roadmap-revision.md` guidance. |
| `roadmap.py` → `materialize_plan_seed(invoker=...)` / `refresh_roadmap_seeds(invoker=...)` | `shell_roadmap_invoker` | Pass `invoker=lambda p: (0, "<draft seed text>")` beginning with valid provenance frontmatter. Test one candidate's retry and failure behavior through `materialize_plan_seed`; test source-order batch rows, outcomes, reports, and cleanup through `refresh_roadmap_seeds`, all under a temporary repository root. |
| `cli/roadmap_cmd.py` → `cmd_roadmap(..., invoker=...)` for `--materialize` / `--refresh-seeds` | `None` at dispatch (the materializer's shell default) | Pass the fake invoker to `cmd_roadmap`; it reaches only the standalone seed materializer and lets a CLI test assert command records, phases, terminal outcomes, and snapshot cleanup without a live backend. |
| `cli/roadmap_cmd.py` → `cmd_roadmap(..., invoker=...)` for `--propose-candidate`, `--review-candidate`, and `--answer-question` | `None` at dispatch (the candidate runners' shell defaults) | Pass one fake invoker to `cmd_roadmap`; proposal, question, and replacement requests receive it unchanged. Assert `--promote-review-seal` makes no backend call. |
| `roadmap_candidate_run.py` → `run_initial_candidate_proposal(invoker=...)` | `shell_candidate_proposal_invoker` | Pass `invoker=lambda p: (0, '<closed candidate response JSON>')` to test one delta or one expansion followed by one delta. Patch `plan_tool.shell.claude_invoke` for the production-wrapper test and assert phase `roadmap-candidate-proposal`, `wait_on_rate_limit=False`, and `max_transient_retries=1`. |
| `roadmap_candidate_review.py` → `generate_candidate_question(invoker=...)` / `answer_candidate_question(invoker=...)` | `shell_candidate_review_invoker` | Pass `invoker=lambda p: (0, '<closed question or candidate-delta JSON>')`; branch on the supplied prompt for one question and then one replacement delta, or return an exact compact-inventory expansion followed by a delta. Keep every reply canned so tests verify immutable bindings without a live backend. |
| `jira.py` → `render_jira_export(invoker=...)` (shared by `export_jira` and the CLI `--no-write` branch) | `shell_jira_invoker` | Pass `invoker=lambda p: ...` returning canned JSON. `jira_cmd.py`'s `--no-write` handler forwards its own `invoker=` parameter through to this call, so a CLI-level test can inject a fake invoker without monkeypatching `shell_jira_invoker` by module attribute. |
| `review.py` → `shell_review_invoker` | `shell_review_invoker` | `monkeypatch.setattr(review_module, "shell_review_invoker", fake_invoker)`. |
| `plan_tool/cli/review_cmd.py` → review/reformat handlers default to `shell_review_invoker` | `shell_review_invoker` | Same as `review.py`. |

When you add a new orchestrator with a real-backend default, add a row
here so the next contributor doesn't have to discover the seam the
hard way.

**Human-input seam.** Unit tests inject a terminal callback directly through
`make_human_input_provider(input_fn)`. To exercise remote mode, use
`monkeypatch` to set `PLAN_TOOL_HUMAN_IO=remote` and
`PLAN_TOOL_HUMAN_IO_DIR` to a `tmp_path`, then arrange the matching complete
`<request_id>.resolution.json` record before the provider waits for it.

**Roadmap seed-action tests.** Use `materialize_plan_seed(invoker=...)` for a
single seed candidate and `refresh_roadmap_seeds(invoker=...)` for a refresh
batch. For command boundaries, pass the same fake through
`cmd_roadmap(..., invoker=...)` with `--materialize` or `--refresh-seeds`.
Build the required roadmap artifacts and draft paths below a temporary
repository root, and return canned, valid seed text from the fake. Do not use a
live backend to prove run-log context, row phases, retry counters, terminal
outcomes, ordering, or snapshot cleanup.

**Roadmap immutable-candidate CLI tests.** Keep storage and lifecycle contracts
in their owning roadmap-version, candidate, review, and promotion test modules.
At the command boundary, use `cmd_roadmap(..., invoker=...)` with canned
proposal, question, and replacement replies; assert the lifecycle options reject
all companions before path resolution or backend work. Enrollment and promotion
must assert no backend call, and the representative happy path must finish with
an ordinary roadmap view reading the promoted accepted head.

**Roadmap shared-evidence helper tests.** The escalation, impact-analysis, and
structural-rewrite routes are retired; no test exercises a receipt or analysis
writer. Keep selected-row admission in `tests/test_roadmap_escalation_selection.py`,
the Git head-state helpers that decision-settlement receipts share in
`tests/test_roadmap_escalation_run.py`, current-state capture and recheck in
`tests/test_roadmap_impact_snapshot.py`, and declared-closure selection in
`tests/test_roadmap_impact_relations.py`. Use `tmp_path` and fake storage
boundaries; no real backend or evidence service is required. Keep
`tests/test_roadmap_format.py` as the independent schema and documentation
drift guard.

**Concurrently-exercised seams (`detail --jobs > 1`).** On the
concurrent authoring path (`plan-tool detail --jobs N`, `N > 1`),
`generate_detail` calls its `invoker=` seam (default `shell_detail_invoker`,
above) from several `ThreadPoolExecutor` worker threads at once, and — when
the foundational-logic sweep is wired — `run_foundational_logic_sweep` runs
inside each worker through the distinct `foundational_invoker` seam, so that
seam is driven concurrently too (it stays OFF by default, so the leak surface
is bounded to eval harnesses). A test that forgets to override either seam
therefore leaks *concurrent* real-backend shell-outs, but the autouse gate
still catches every leak — it fires per-spawn on `backend.registered_binaries()`
regardless of thread. The neutralization recipe is unchanged: override the one
`invoker=` seam (and `foundational_invoker` for a sweep-enabled test) and all
workers use the fake. See the `detail` command for the `--jobs > 1` mechanics.

`completeness-apply --jobs N` (`N > 1`) drives the *same* `apply_finding`
`shell_invoker` seam concurrently, one worker per isolated git worktree
(`cli/completeness_apply_parallel.py`). Neutralize it the same way — override
`launcher.apply_finding` — or stub the module's `run_parallel_apply` /
`apply_finding_in_tree` to skip worktree provisioning entirely in a unit test;
the real worktree pool is covered by `@pytest.mark.integration` tests in
`test_completeness_apply_parallel.py`.

**Prompt-mode A/B.** The `create`/`detail` SPLIT-arm rows above are the
opt-in side of a combined-vs-split A/B (`PLAN_TOOL_PROMPT_MODE`, default
`combined`). Scenario capture (`PLAN_TOOL_CAPTURE_SCENARIOS`) records
re-runnable inputs for the eval corpus. See `docs/explanations/prompt-ab-testing.md`.

**codex fixture set.** Backend-level tests (`tests/test_backend.py`)
never shell out to a real `codex`; they parse captured JSONL transcripts
under `tests/fixtures/codex/` — `exec-stream-sample.jsonl`,
`exec-result-envelope.jsonl`, `exec-command-execution.jsonl`,
`exec-auth-failed.jsonl`, and the `exec-turn-failed.jsonl` error transcript.
Those fixtures were captured
against the version-pinned contract in
[`docs/reference/contracts/codex-cli.md`](docs/reference/contracts/codex-cli.md) (`codex-cli
0.142.0`); re-capture both the fixtures and the contract when codex
upgrades, since codex's `--json` schema differs from claude's
`stream-json` and version drift is expected.

**cursor fixture set.** Same pattern for the Cursor Agent backend: parse
`tests/fixtures/cursor/agent-result-envelope.jsonl` and
`agent-command-execution.jsonl` against
[`docs/reference/contracts/cursor-agent-cli.md`](docs/reference/contracts/cursor-agent-cli.md).
No real `agent` subprocess in tests.

## What writing tests should look like

### Default to unit tests

When you're adding code, **start with unit tests**. They're cheap to
write, fast to run, and surface the most failures per second. A unit
test:

- Exercises a single function or class in isolation.
- Mocks external systems explicitly (no claude shell-out, no real
  filesystem ops beyond `tmp_path`).
- Lives in the `test_X.py` file mirroring the source module being
  tested (`plan_tool/X.py` → `tests/test_X.py`).
- **Stays unmarked.** The absence of `@pytest.mark.integration` is
  the convention.

Concretely: a new helper in `review.py` gets a `TestNewHelper` class in
`test_review.py` with `@pytest.mark.parametrize` cases for the happy
paths, edge cases, and skip conditions.

### Add an integration test when (and only when) a unit test can't prove what you need

Add `@pytest.mark.integration` at the **class level** when the test:

- Drives `main([...])` argparse → handler → orchestrator end-to-end.
- Invokes an orchestrator function (`create_plan`, `generate_detail`,
  `cmd_completeness`) and asserts cross-module behavior (e.g. that
  findings produced by one module flow through `apply_finding` and
  show up in another module's output).
- Exercises the iteration lock / drift detection / scope guard
  interaction across modules (these are coupled by design and unit
  tests on each individually don't catch wiring mistakes — see
  Lesson 7 in `docs/explanations/lessons-learned.md`).

If you can prove the behavior with a unit test, do that instead.
Integration tests are the second line of defense, not the first.

### Where each integration test type lives

| Type | File | Example class |
|---|---|---|
| CLI surface (`main()`) | `test_cli.py` | `TestCmdCompletenessConceptWiring` |
| `create_plan` orchestrator | `test_create.py` | `TestCreatePlanIterationLoop` |
| `generate_detail` orchestrator | `test_detail.py` | `TestGenerateDetailIterationLoop` |
| Reconcile iteration helper | `test_cli.py` | `TestIterateReconcileLoopDriftPhase` |

## When to run integration tests

Always run the full suite **before merging** — the CI gate runs every
test regardless of marker. During development, run the integration
tier when you've touched any of these **conceptual areas**:

| Conceptual area | Source files | Integration test classes to run |
|---|---|---|
| Iteration loop infrastructure | `convergence.py`, `iteration_lock.py`, `scope_guard.py`, `change_collision.py` | `TestIterateReconcileLoopDriftPhase`, `TestCreatePlanDriftHalt`, `TestGenerateDetailDriftHalt`, `TestCreatePlanIterationLoop`, `TestGenerateDetailIterationLoop`, `TestCmdRunReconcileIterationLoop`, `TestCrossCuttingIterationCLI`, `TestCmdCompletenessSigintRelease`, `TestCreatePlanSigintRelease`, `TestGenerateDetailSigintRelease`, `TestIterateReconcileLoopSigintRelease`, `TestIterateReconcileLoopTriage`, and the collision-sidecar / triage wiring tests `test_collision_sidecar_continue_breaks_for_rec_and_reiterates`, `test_collision_sidecar_continue_refreshes_lock_so_iter_2_runs`, `test_no_collision_sidecar_flag_preserves_legacy_halt`, `test_triage_short_circuits_when_all_remaining_are_deferred`, `test_no_triage_flag_force_applies_every_finding` in `TestCmdCompletenessConceptWiring` |
| Impact-weighted apply triage | `review.py:should_apply_by_triage`, `review.py:partition_findings_for_triage`, `review.py:emit_triage_summary`, `prompts/reconcile.md` (Impact/Complexity Decision-block fields) | `TestApplyTriage`, `TestDecisionImpactComplexity` (unit, in `test_review.py`); `TestIterateReconcileLoopTriage`, plus `test_triage_short_circuits_when_all_remaining_are_deferred` and `test_no_triage_flag_force_applies_every_finding` in `TestCmdCompletenessConceptWiring` (integration) |
| Conceptual audit (plan-only) | `review.py:check_plan_audit`, `prompts/plan-audit.md`, `plan_tool/cli/completeness_cmd.py:cmd_completeness` | `TestCheckPlanAudit` (unit, in `test_review.py`); `TestCmdCompletenessConceptWiring` (integration) |
| Concept decision records and scoped review | `plan_tool/concept_tree.py`, `plan_tool/concept_bootstrap.py`, `plan_tool/concept_review.py`, `plan_tool/concept_sync.py`, `plan_tool/parser.py`, `plan_tool/cli/scope_review_cmd.py` | Run the matching domain suites: `tests/test_concept_tree.py`, `tests/test_concept_bootstrap.py`, `tests/test_concept_review.py`, `tests/test_concept_sync.py`, and parser coverage in `tests/test_parser.py`; for command orchestration or cross-module persistence/synchronization changes, also run `tests/cli/test_scope_review_cmd.py` |
| Criteria fulfillment (code ⊇ plan) | `review.py:check_criteria_fulfillment`, `prompts/criteria-fulfillment.md` | `TestCheckCriteriaFulfillment` (unit, in `test_review.py`) |
| Apply-finding / intent gate | `launcher.py`, `review.py:Decision`, `plan_tool/cli/completeness_phases.py:_run_iterate_convergence_loop` (iterate branch) | `TestStrictIntentPlumbing`, `TestStrictIntentShortCircuit`, `TestCreatePlanIterationLoop`, `TestGenerateDetailIterationLoop` |
| CLI commands (any handler) | the owning per-intent module under `plan_tool/cli/` (e.g. `completeness_cmd.py:cmd_completeness`) | The integration class for that command (e.g. touching `cmd_completeness` → run `TestCmdCompletenessConceptWiring`) |
| Reformat → create pipeline | `reformat.py`, `create.py` | `TestReformat*` classes |
| Run-log persistence | `run_log.py` | `TestCmdRuns`, `TestCmdRunsRegression`, `TestCmdRunRunLogIntegration` |
| Checkpoint resume | `checkpoint.py`, `create.py`, `detail.py` | `TestCmdCheckpoint`, `TestCreatePlanIterationLoop`, `TestGenerateDetailIterationLoop` |

You don't need to run the full integration tier for every change
— target the area you touched. The marker exists precisely so you
can `pytest -m integration tests/test_cli.py::TestCmdCompletenessConceptWiring`
and get fast feedback on the affected wiring without paying for
unrelated `main()`-driving tests.

### The `tests/cli/` characterization-test convention

The CLI lives in the `plan_tool/cli/` package (one module per intent
group). Its tests under `tests/cli/` are **split-proof by convention**
— they survive a handler moving between modules:

- **Import only through the `plan_tool.cli` package** — never `setattr`
  a cli-module global. To stub claude, patch the **domain** module
  (`plan_tool.launcher`, `plan_tool.review`), or drive `main(argv)`
  against a tmp repo. (A `setattr` on a cli module's global breaks the
  next time that symbol is carved into a sibling module.)
- **`tests/cli/test_package_surface.py` is the surface contract** — it
  pins the import surface, the `package_surface_help.golden.txt` golden
  (the byte-exact `--help` sourced from the `plan_tool/cli/__init__.py`
  package docstring), and the parser↔dispatch correspondence. It defines
  what `plan_tool/cli/__init__.py` must re-export.
- **Per-command characterization nets live in
  `tests/cli/test_<area>_cmds.py`** (e.g. `test_inspect_cmds.py`,
  `test_authoring_cmds.py`, `test_completeness_cmd.py`) — add new command
  coverage there, mirroring the module it exercises.
- **Shared tmp-repo / manifest fixtures live in `tests/cli/conftest.py`.**

## Mocking conventions

- **Claude shell-outs**: monkey-patch `plan_tool.review.shell_review_invoker`
  or `plan_tool.shell.claude_invoke`. Never invoke real claude in
  tests — CI environments may lack it on PATH, and even where it's
  present, real calls are non-deterministic and expensive.
- **`apply_finding`**: monkey-patch at the call site's module, e.g.
  `monkeypatch.setattr(create_module, "apply_finding", fake_apply)`.
  This is per-caller because `from plan_tool.launcher import apply_finding`
  binds the name in the caller's namespace.
- **`Popen` doubles must let `git` through**: wrap any `subprocess.Popen`
  stand-in in `tests/subprocess_doubles.py::delegate_git_to_real_subprocess`
  (its factory form, `_make_popen_factory`, already does this). Patching
  `backend_runner.subprocess` patches the *global* `subprocess` module, and
  both backend callers now read git state on every invocation for the
  partial-mutation retry guard (`plan_tool/git_state.py`). An unwrapped
  double therefore intercepts that read — consuming a scripted backend
  response, answering the guard with backend output, or raising on a
  signature mismatch. To control the git read itself, patch
  `launcher._git_changed_paths_or_none`, which exists as that seam. The
  shared double is `tests/subprocess_doubles.py::_make_popen_factory`; see
  also `tests/test_launcher.py::_popen_factory_with_edits`.
- **`shell_invoker` and `claude_invoke`'s subprocess supervision** (Popen
  spawn, stream pumps, heartbeat, silence-kill ladder, and — for
  `claude_invoke` — the configured-timeout kill) both live in
  `plan_tool/backend_runner.py:run_streaming_once`. The streaming lane
  reaches it through `launcher._run_streaming_once`'s forwarding wrapper —
  the seam a test monkeypatches (`monkeypatch.setattr(launcher,
  "_run_streaming_once", fake)`) is unchanged — while the batch lane
  (`shell.claude_invoke`) calls it directly, passing the active backend's
  `batch_transport` rather than `streaming_transport`. A test that needs to
  intercept a `claude_invoke` spawn therefore patches
  `backend_runner.subprocess.Popen` (via `_make_popen_factory`), not
  `subprocess.run` — `shell.py` no longer imports `subprocess` at all. Patch
  the heartbeat/kill threshold constants on `backend_runner`, not `launcher`
  or `shell`.
- **File system**: prefer `tmp_path` fixtures. Don't write to the real
  repo root or `.plan-tool/` directories.
- **Git fixtures**: when several tests need the same empty repository or
  committed baseline, create it once with a session-scoped fixture and copy
  its `.git` directory or complete repository into each test's `tmp_path`.
  Keep every copied worktree and bare remote private to that test; never
  share a mutable repository, remote, branch, index, or worktree between
  tests. Reuse the immutable setup only after measuring repeated `git init`,
  configuration, seed-commit, or tag work as a meaningful cost.
- **Time**: when testing convergence deadlines, set `budget_seconds=0`
  to trip the deadline check on the first pass. Monkey-patching
  `time.monotonic` doesn't help — `ConvergenceState.started_at`
  captures a reference at class-definition time.

## Keeping tests fast

Profile before changing a test. Use pytest's duration report to identify a
suite's cumulative cost, then inspect whether the time belongs to the behavior
under test or to repeated fixture setup. Preserve the former; remove the
latter. Repeated Git initialization, configuration, seed commits, tags,
filesystem corpus construction, and repeated parsing are good candidates for
an immutable fixture baseline or cached read-only result.

Keep the proof at the level the test claims. A matrix or CLI-wiring test may
stub an expensive per-cell operation when another focused test drives that
operation's real entrypoint. Do not replace the only test of an end-to-end
contract with a synthetic result merely to reduce elapsed time.

Remove a test only when a surviving test proves the same property through an
equal or stronger boundary and will fail for the same regression. Record that
surviving test in the change review. Parameterize repeated inputs that assert
one rule, but retain distinct failure modes, compatibility paths, and one
end-to-end test for each public boundary. A slow test is evidence to inspect
its setup, not evidence that its behavior has low value.

Validate a fixture-performance change with the focused suite both serially
and under at least two xdist workers. Then run the required broader suite. A
parallel-only failure identifies shared mutable state or an incomplete cleanup
boundary; fix the fixture instead of
serializing or weakening the test. Treat one noisy full-suite wall-clock run as
an observation, not proof of a speedup; compare the focused setup and call
durations as well.

## What to mark as integration vs leave unmarked

Use this checklist:

| Test does this... | Marker |
|---|---|
| Calls `main([...])` | `@pytest.mark.integration` |
| Calls `create_plan` / `generate_detail` / `cmd_completeness` with real plan files in `tmp_path` | `@pytest.mark.integration` |
| Calls `_iterate_reconcile_loop` directly (crosses many modules) | `@pytest.mark.integration` |
| Tests one function or class in isolation, even when that function does I/O | unmarked |
| Smoke-tests argparse via `build_parser().parse_args(...)` | unmarked |
| Tests prompt rendering with substituted template variables | unmarked |
| Tests `apply_finding` with a fake invoker and checkpoints | depends — if it's exercising one launcher behavior, unmarked; if it's testing the cross-module flow with deltas, mark it |

When in doubt: if the test's failure would point to a multi-module
wiring bug (rather than a single function bug), mark it.

## Adding a new conceptual area

When you add a new orchestrator or cross-module pipeline:

1. Add unit tests for each helper in isolation (no marker).
2. Add 2-4 integration tests for the wiring (`@pytest.mark.integration`).
3. Add a row to the **"When to run integration tests"** table above
   so future contributors know to run yours when touching that area.

## Anti-patterns

- **Marking everything integration** defeats the purpose; the fast loop
  shrinks toward zero. Only mark when the test is genuinely multi-module.
- **Skipping unit tests "because there's an integration test"** —
  integration tests catch wiring; unit tests catch logic. You need both.
  An integration test that fails will point you at a region of code; a
  unit test that fails will point you at the specific function.
- **Sharing state between tests** (writing to a module-level variable,
  mutating fixtures across tests). Each test should be hermetic;
  pytest does not guarantee test order.
- **Real claude calls in any test**, marked or not. CI environments
  may lack claude on PATH, and real calls are non-deterministic.

## Reference

See also:
- `docs/explanations/lessons-learned.md` — Lesson 7 ("test the WIRING, not just the helper")
  is the rationale for the integration tier.
- `BACKLOG.md` — the forward-looking feature backlog with triage notes.
  Lesson-7 test-coverage follow-ups are tracked under Bucket D
  (process / hygiene) when they're worth doing.

### Run-grade detail retirement coverage

Run `tests/test_jira.py` to verify captured run-grade input, shared story/handoff
provenance, and rejection before publication. Run `tests/test_review_persistence.py`
to verify archived-source mismatches and sampler checkpoints cannot certify final
audit evidence. The full suite includes both integration paths; keep real backend
calls stubbed through the invoker seams above.
