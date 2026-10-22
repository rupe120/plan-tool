# Architecture reference

Module-by-module description of what ships. This is the *descriptive* half of
the architecture: what each module is and how the pieces fit.

The **normative** half — the rules a change must not get wrong (the parallelism
directive, the invoker seam, CLI layering, the cycle-free import constraints,
the exit-code convention, per-project plan discovery) — stays in
[`CLAUDE.md`](../CLAUDE.md) § "Architecture", because it governs what you are
allowed to do rather than what exists.

Keep this file current when a module's shape changes; `CLAUDE.md` points here
rather than restating it, per its own § "Code comments" rule that depth belongs
in a maintained doc behind a one-line pointer.

For the high-level command authority and handoff map, see
[`PROCESS_CONTRACTS.md`](reference/contracts/process.md).

## Module map

Where to start reading. The sections after this one cover the subsystems in
depth; this map covers the core entry points and the command layer.

**Core (`plan_tool/`)**

| Module | What it is |
| --- | --- |
| `schema.py` | Pydantic models for the YAML frontmatter schema. |
| `parser.py` | Read, validate, and round-trip plan markdown files. |
| `locator.py` | Plan discovery and repo-root context. |
| `prompt_budget.py`, `context_window.py` | The pre-send prompt-budget advisory and the leaf that supplies the selected model's window. See [Backend abstraction](#backend-abstraction). |
| `renderer.py` | Prompt-template rendering for plan steps. |
| `launcher.py` | Step execution: resolve the step, render the prompt, invoke the backend, persist the result. |
| `progress.py` | Progress reporting for backend-invoking commands. |
| `canonical.py` | Deterministic read helpers for canonical-shape plan sources. |
| `prompts/` | The packaged prompt templates (`run.md`, `check.md`, …). |

**Command layer (`plan_tool/cli/`).** Thin handlers, one module per intent
group; the layering rules are in [`CLAUDE.md`](../CLAUDE.md) § "Architecture"
(CLI layering).

| Module | What it is |
| --- | --- |
| `__init__.py` | Package surface: the entry point and the intent-grouped subcommand catalog. |
| `app.py` | `main()`, dispatch assembly, and top-level error handling. |
| `parser.py` | argparse construction and the per-module subparser registration seam. |
| `annotate_cmd.py` | `annotate`. |
| `authoring.py` | The plan-writing verbs (`create`, `detail`, …). |
| `bench_cmd.py` | `bench run` / `bench report`. |
| `checkpoints.py` | `checkpoint`, the on-disk resume cache. |
| `completeness_cmd.py` | `completeness-audit` / `completeness-apply`. |
| `completeness_phases.py` | The `--iterate` loop and apply dispatch behind `completeness-audit` — an orchestrator, the one exception to thin handlers. |
| `completeness_apply_parallel.py` | The parallel `completeness-apply --jobs N` path. |
| `convergence_cmd.py` | `convergence`. |
| `data_contract_cmd.py` | `data-contract-apply`, the interactive walk over saved data-contract drift findings. |
| `decision_cmd.py` | `decide`, the explicit decomposition-decision recorder. |
| `direct_cmd.py` | `direct-jira` / `direct-run`. |
| `gate_status_cmd.py` | `gate-status`, saved final completeness verdicts via `gate_status.py`. |
| `gates_cmd.py` | `suggest-gates`. |
| `gitcommit.py` | Shared git-commit plumbing for the opt-in `--commit` flags. |
| `init_cmd.py` | `init`, which writes tracked project-level intent metadata. |
| `inspect.py` | The read-only plan verbs (`list`, `status`, `validate`, …). |
| `jira_cmd.py` | `jira`. |
| `lessons_cmd.py` | `lessons`. |
| `manifest.py` | `register` / `deregister` / `sweep`. |
| `review_cmd.py` | `reconcile-plan` / `reconcile-plan-walk` / `verify-all`. |
| `roadmap_cmd.py` | `roadmap`. |
| `run_cmd.py` | `run`. |
| `runs.py` | `runs`: inspect, profile, and manage run logs. |
| `scope_out_cmd.py` | `scope-out`. |
| `scope_review_cmd.py` | `scope-review`. |
| `skill_cmd.py` | `install-skill`. |
| `split_criteria_cmd.py` | `split-criteria`. |
| `telemetry_cmd.py` | `telemetry`. |
| `worktree_cmd.py` | `worktree`: provision, inspect, and tear down per-plan workspaces. |
| `console.py` | Presentation and path-formatting helpers (leaf). |
| `context.py` | Workspace and budget resolution helpers (leaf). |
| `reconcile.py` | Reconcile-engine internals shared by the run / detail / review verbs (leaf). |
| `review_actions.py` | The shared review-action builder (leaf). |

## Decision-outcome analysis

`plan_tool/telemetry_analysis.py:analyze_decisions` is the read-only
decision-outcome resolver behind `plan-tool telemetry`. It reads decision
telemetry together with existing run-log and report-history evidence, resolves
per-event outcomes, and aggregates by `(kind, decision)` into advisory
recommendations. The leaf may depend on established read-only sibling leaves
but must not import `plan_tool.cli`; `plan_tool/cli/telemetry_cmd.py:cmd_telemetry`
remains thin, read-only command wiring. Verdicts are computed on read rather
than persisted as a second telemetry store, and neither the leaf nor command
auto-tunes thresholds or mutates plans or configuration. Ownerless and legacy
rows remain counted but unresolved when their join keys cannot support
correlation.

## Concept sign-off and ownership

**Concept sign-off and ownership (`concept_tree.py`, `concept_bootstrap.py`, `concept_review.py`, `concept_sync.py`).** Concept materialization is **lazy**: a `plan-details/<slug>/concepts.json` record exists only when a plan actually defers something, so an un-deferred plan carries no record and `create`/`detail` write none. A deferral is a flat **decision record** (`record_kind: decision-record`) — a bucket-tagged `defer`/`wont_do` node with no hierarchy (empty `parent_path`) — that captures an operator/tool decision, not a cache of plan text; it carries `plan_fingerprint` for provenance only and is **not** fingerprint-validated on load, so it survives unrelated plan edits. Its sole validity check is whether its coarse `bucket` (a body section name) still exists: `check_concept_coverage` is total and inert on an absent record, and a confirmed flat decision is itself the accounting, so a flat record never emits a blocking `concept-coverage` finding. Pending (unreviewed) deferrals surface **non-blocking** — naming the bare `node.id` — in `status`, the completeness report (`concept-unsigned-deferral`, plus a missing-`bucket` re-review reminder), and the `create` run-summary; `plan-tool scope-review` confirms them (`include`/`defer`/`wont_do`), binding approval to the current plan source and resolving a missing-`bucket` record. The shipped hierarchical **full-tree** record (deterministic bootstrap/re-derivation, scoped three-state sign-off, `Step.concept_ids` ownership, blocking coverage) stays loadable and fingerprint-gated but is **dormant** — no create/detail path emits it, and a stale legacy tree surfaces one non-blocking re-sync advisory. Migrating any legacy full-tree record to the flat shape is tracked in `BACKLOG.md` #131.

## Lessons learned

**Lessons learned (`lessons.py`).** Accumulated lessons fed back into the `create`/`detail`/`review` prompts, split across two file scopes: **general.md** at `~/.plan-tool/lessons/general.md` (per-user, project-agnostic authoring rules, resolved against `$HOME` at call time) and a **project** file inside the repo (domain-specific rules). `append_lessons` and `append_pending_lessons` write new entries — the latter to a pending subsection later promoted or discarded — while `find_lesson_equivalences` runs a claude round-trip to catch a new entry that just restates an existing one before it's appended. `render_lessons_block` selects and formats the bundle a prompt actually sees; `discover_lessons_files` / `parse_existing_entries` / `render_consolidated_file` support hand-consolidating scattered entries. A separate `LessonsWarning` log (`append_warning` / `load_warnings` / `recurrence_counts`) tracks lessons whose citation rate suggests they're being ignored rather than applied.

## Create/detail sub-prompts

**Create/detail sub-prompts.** Three focused leaves, each a single claude round-trip lifted out of `create`'s or `detail`'s main authoring prompt so a *divergent* sub-task (open-ended repo search, drafting free text) doesn't compete with the main prompt's *convergent* emission. **Foundational-logic sweep (`foundational_logic.py`)** greps the repo for other locations sharing a plan's or step's core logic — duplicated blocks, parallel call sites, sibling implementations — via `run_foundational_logic_sweep`; `create` runs it over the proposed step list and `merge_sweep_into_steps` folds hits back into `files`/`creates`, while `detail` folds the same result into the acting step's body via `format_foundational_logic_block`. **Intent drafting (`intent_proposal.py`)** is the create-time remedy for `review.py`'s `intent-presence` finding: `propose_intents` drafts a one-line `intent` for the plan and any step lacking one, `review_intent_drafts` walks accept/edit/decline per draft (entirely in-memory — nothing is written until `apply_intent_drafts`). **Prompt excerpting (`prompt_excerpt.py`)** is a leaf-only symbol-aware source-preview builder (`build_prompt_excerpt`): given already-read text, a repo-relative path, and candidate symbols, it slices a Python definition, a markdown section, or a line-match window without touching the filesystem itself — callers (e.g. `annotate.py`) own the read.

## Reference-doc fetching

**Reference-doc fetching (`fetch.py`).** A stdlib-only leaf (`urllib` + `html.parser`, no third-party HTML parser dependency) that turns the URLs `create`'s web-research round-trip proposes (`create.propose_references_from_claude`) into content: `fetch_url` retrieves and strips a page to readable text, `fetch_reference_docs` does this for a batch, and `render_reference_docs_block` folds the results into the body-synthesis prompt so a generated plan is grounded in real documentation rather than the seed prose alone. `docs_to_json`/`docs_from_json` round-trip `FetchedDoc` records for caching between calls.

## Backend abstraction

**Backend abstraction (`backend.py`).** A `CliBackend` descriptor bundles binary name, argv builders, stream-line/NDJSON parser, and failure-classification regexes for one subprocess CLI. Three are registered: `claude` (default), `codex`, and `cursor` (binary `agent`). Selection precedence: explicit `--backend` flag → recognized `--model` family → `PLAN_TOOL_BACKEND` env → `claude`. `gpt-*`, `chatgpt-*`, `o1`/`o3`/`o4`, and `codex-*` select Codex; `claude-*` selects Claude; and `gemini-*` selects the provisional Gemini backend. An explicit backend intentionally overrides model inference. Ordinary recoverable short rate limits select policy separately before dispatch: `--on-rate-limit wait|switch|stop|ask` → legacy `--no-wait-on-rate-limit` (`stop`) → `PLAN_TOOL_ON_RATE_LIMIT` → `wait`; `switch` requires `--fallback-backend` or `PLAN_TOOL_FALLBACK_BACKEND`, and interactive `ask` offers wait / backend switch / stop. The fallback remains scoped to the current batch or streaming invoke; do not document or implement it as a lasting global backend switch. A confirmed Cursor monthly plan quota bypasses those policy actions and is terminal for the current call. `backend.py` is a stdlib-only leaf below `shell`/`launcher`/`claude_errors` — keep that import order acyclic. Each backend's stream schema is pinned by a contract doc and fixture set (`docs/reference/contracts/codex-cli.md` + `tests/fixtures/codex/`; `docs/reference/contracts/cursor-agent-cli.md` + `tests/fixtures/cursor/`).

**Streaming subprocess supervisor (`backend_runner.py`).** Owns `run_streaming_once`, the one Popen call every streaming backend invocation runs through: the spawn, the stdout/stderr pump threads, NDJSON-to-event parsing, the heartbeat daemon with its stall marker and silence-kill ladder, the console-verbosity state (`set_console_verbosity`/`get_console_verbosity`), and the dormant `sibling_log_dir` transcript writer. Its `transport` parameter is a `Callable[[str], PromptTransport]` selecting how the prompt reaches the backend: the run lane's `launcher._run_streaming_once` (a thin wrapper kept as the monkeypatch seam) passes the active backend's `streaming_transport`; a batch caller can pass `batch_transport` without any change to the runner — load-bearing because `.plan-tool/backends.json` can carry different `extra_batch_argv`/`extra_streaming_argv` per project. A leaf below `shell`/`launcher` whose only first-party imports are `plan_tool.backend` and `plan_tool.run_log`, the property that lets both lanes share the supervisor without a `shell`↔`launcher` cycle.

**Prompt-budget window (`context_window.py`).** A leaf above `backend.py` that tells the pre-send prompt-budget advisory (`prompt_budget.py`, itself a leaf) which window to measure against. It uses local sources only, never a network call, and returns `None` when nothing is known; every caller then falls back to `prompt_budget.DEFAULT_CONTEXT_WINDOW` and the summary says `(default)`. Refresh Codex's catalog with `codex debug models`; the two external shapes it reads are in [Model window sources](reference/contracts/model-window-sources.md).

| Lane | Window source | Limits |
| --- | --- | --- |
| Codex | The usable share (`context_window` × `effective_context_window_percent`) of the model's entry in `$CODEX_HOME/models_cache.json` (default `~/.codex`). | The model is the backend's `resolved_model` (the `--model` flag, a project override, or the manifest default), else `config.toml`'s top-level `model`; a Codex profile or a `-c model=` override is not seen. |
| Claude | A window an earlier call of this process reported: `backend_runner` records it from the result envelope's `modelUsage` through `backend.observe_context_window`. | No reported window exists before the first call, so the first call of a process measures against the default (a pre-call source is BACKLOG #472). |

The observed-window registry keeps `(window, exact)` per backend and model:

- **Exact:** the entry whose id equals the selected model, or the only entry in the result. It replaces any earlier value.
- **Lower bound:** a mixed result gives only its smallest window. It never replaces an exact window, only rises, and errs toward warning; no alias is guessed.
- **No model selected:** the key holds one window for the whole process and assumes the CLI's default model does not change underneath the run. A mid-run change is not corrected by a later lower bound (a deliberate limit, not an oversight).
- **Concurrency:** updates are lock-guarded, because each in-flight call has its own output pump thread.

Other contracts:

- **The one refusal.** The selected run-reconcile prompt in `launcher.run_step` is the only budget verdict that refuses a send. It passes `observed=False`, so only the Codex catalog, a file, can change its verdict, never a window learned mid-run.
- **Call sites.** Every `estimate_prompt_budget` / `maybe_warn_prompt_budget` call outside the leaf passes `context_window=active_context_window(...)`; `tests/test_context_window.py` pins the exact per-module counts by AST.
- **File memo.** The Codex catalog and config are parsed once per file version `(mtime_ns, size, inode, device)`, under a lock. A content failure (malformed or wrongly shaped, including pathological nesting) is remembered per version; a read error (a descriptor limit, a momentary permission error) is not cached.

## Progress reporting

**Progress reporting (`progress.py`).** The silent backend-invoking subcommands (`detail`, `jira`, `review`, `create --from*`) call `shell.claude_invoke`, which buffers stdout until the subprocess exits — without a separate channel the operator sees nothing for the call's duration (often minutes). `ProgressReporter` (and its `NullReporter`/`StderrReporter` implementations, selected per caller) gives each of those callers a thin reporter that emits human-readable status lines on **stderr** while the structured stdout parser receives byte-identical input; a daemon heartbeat thread emits a periodic `Ns elapsed` line so a long silent call still shows liveness.
Roadmap does not consume this heartbeat contract: its normal stage-run status is
a separate, transition-only stderr surface owned by the roadmap layer.

## Backend-quality benchmark

**Backend-quality benchmark (`bench.py`).** The engine behind the synthetic backend-quality benchmark (`docs/evidence/benchmark-design.md`): for every `(family, cell, backend, trial)` cell it materializes an isolated scratch workspace (fresh tempdir, `git init`, a baseline commit, the family's corpus fixtures) and drives the **production entrypoints** operators actually call (`create_plan`, `generate_detail`, `run_step`, `apply_finding`, …) — never a bespoke harness prompt — so the benchmark measures the real pipeline. `run_bench_matrix` drives trials and appends `BenchTrialRecord`s to a JSONL log; `score_trial`/`score_records` grade each family's artifact against a per-cell `*Answer` key (proposal/detail/reconcile/implementation/apply, each with its own `*Artifact`/`*AnswerKey`/`*Score` triad); `build_quality_report` and `recommend_per_family` aggregate scores into a `QualityCell`/`QualityReport` and a per-family backend recommendation, rendered by `render_report_markdown` / `render_recommendations_doc`.

## Rate-limit recovery loop

**Rate-limit recovery loop (`rate_limit_loop.py`).** `plan_tool/rate_limit_loop.py` owns the shared 429-detect / wait-or-switch / transient-backoff recovery loop (`run_with_rate_limit_recovery`) that `shell.claude_invoke` (batch) and `launcher.shell_invoker` (streaming) both route through, so a fix lands once instead of in two near-identical copies. It is a **stdlib-only leaf below `shell`/`launcher`** — no first-party imports, so it forms no `shell`↔`launcher` edge and no cycle through `backend`/`claude_errors`. Caller-specific concerns (the run-once closure, the sleep/clock seams, the `EXEC_NOT_FOUND` path guard, the two per-invoke backend-scope ContextVars) stay caller-side and are **injected**, not unified into the leaf. `claude_errors.KIND_TO_CATEGORY` maps the provider-specific `PLAN_QUOTA` classification to the leaf's neutral `AttemptCategory.TERMINAL`; the leaf gains neither a provider branch nor a new recovery action. The conceptual-audit caller consumes that typed terminal outcome locally in `review.audit_plan_until_stable`, where it ends later passes and records unconfirmed coverage.

**Working-tree state and the retry guard (`git_state.py`).** Owns the `git status --porcelain -z` read (`changed_paths_or_none` / `changed_paths`), the authorship gate’s commit reads (`head_revision` / `committed_changed_paths`), and `make_partial_mutation_retry_guard`, the `retry_guard` seam both backend callers hand the recovery loop. The guard snapshots the spawn-cwd changed-paths set **before attempt 1**, then refuses a re-invoke when the aborted turn left a new changed path (re-driving would double-apply it) and fails **closed** when git became unreadable mid-run. A leaf below `shell`/`launcher` whose only first-party import is `rate_limit_loop`. Both callers use it: `launcher.shell_invoker` always has, and `shell.claude_invoke` now does too — its batch turns run under `--permission-mode acceptEdits` and `detail`'s turn authors files, so the "batch proposals never edit the tree" premise it previously relied on was false. `launcher._git_changed_paths_or_none` remains as a thin module-level alias purely as a monkeypatch seam.

## Correctness gates

Validation primitives protect every Claude-invoking command. This section
names their owners and boundaries; [`GATES.md`](GATES.md) explains what each
operator-facing gate checks, and [`ITERATION.md`](ITERATION.md) explains the
convergence loop.

| Concern | Owner | Boundary |
| --- | --- | --- |
| Shared validation | `review.py`, `gates.py`, `scope_guard.py`, `drift_detection.py` | `run` pre/post-flight, review findings, Jira parsing, the run-grade seven-section `detail` response, and `create` re-parsing from disk. |
| Grade selection | The detail readers | Existing Jira-grade files retain their closed five-section validation only at explicit reader boundaries; `detail --grade jira` rejects before authoring. |
| Iterative repair | `convergence.py`, `auto_reconcile.py` | Under `--iterate`, `create`, `detail`, and `completeness-audit` loop their supported gates → `apply_finding` → re-audit. |
| Bundle-aware audit | `completeness_report.py` | `audit_detail_bundle_status` and `DetailBundleStatus.is_bare` feed `next_step_gaps`, which splits the gaps to close from the advisory ones by the blocking verdict. |

### Detail-bundle state guides the audit route

For a bare or partially detailed plan, the audit keeps only routes that can
operate on the existing artifact. A bare-plan BLOCKED result leads with
`plan-tool detail`; `_blocked_next_step` offers `plan-tool split` second.

| Finding or writer | Route on a bare or partial bundle | Reason |
| --- | --- | --- |
| Conceptual `plan-correctness` | Keeps the `completeness-apply` route for plan-body design gaps, including material ambiguity and target prose that has no detail file. | The plan body exists. |
| Conceptual `plan-completeness`, `DETAIL_LEVEL_FINDING_SOURCES`, and files coherence | Stays withheld. | A completeness action can only target what exists. |

### Audit discovers; apply mutates

`completeness-audit --iterate` applies only deterministic well-formedness
findings. It persists both conceptual sources, `plan-correctness` and
`plan-completeness`, to the sidecar without applying them. The audit spends no
mutation tokens on conceptual gaps while it discovers them; the apply phase
uses the persisted gap map deliberately.

`completeness-apply` is the sole mutator for those sources. Its
`review_walk.py` `_APPLY_AS_FINDING_SOURCES` dispatch walks correctness first,
then completeness. `plan-correctness` is dispatchable only there, passed as
`extra_apply_sources` after its detail-bundle gate; generic reconcile and
review walks must not auto-apply it.

### Parallel apply isolates then replays

`completeness-apply --jobs N` (`N > 1`) treats the saved gap map as static
input and uses `cli/completeness_apply_parallel.py` for wall-clock parallelism:

1. A plan-mutation-free worker runs `apply_finding` in its own isolated Git
   worktree off `HEAD`, so the route requires a clean tree.
2. A `ThreadPoolExecutor` dispatches workers with B1-style failure isolation.
3. `replay_results` writes captured content to the canonical tree in serial,
   deterministic `(source, severity, id)` order, re-running a finding when an
   earlier replay touched its file.

`--jobs > 1` is non-interactive and requires `-y`; `--jobs 1` remains the
default interactive walk.

### Completeness orchestration

`cli/completeness_phases.py` is the non-CLI logic layer behind
`completeness_cmd.py`'s two thin handlers, `cmd_completeness` and
`cmd_completeness_apply`. It is a cycle-free leaf that the command module
calls, never the reverse.

| Responsibility | Implementation boundary |
| --- | --- |
| Iteration | `_run_iterate_convergence_loop` and its 18 private helpers, including `_fmt_finding_counts`, `_sampled_bundle_status`, and `compute_conceptual_bar_blocking_ids`. `completeness_cmd.py` keeps its one qualified `completeness_phases._run_iterate_convergence_loop(...)` call because the test suite wholesale-monkeypatches that seam. |
| Apply dispatch | `_resolve_apply_walk_targets` → `_run_apply_walk`; the latter delegates `--jobs N > 1` work to `_apply_walk_recs_parallel`. |
| Rendering and saved inputs | `_render_completeness_json`, `_render_grouped_report`, `_persist_and_present_report`, `_resolve_saved_completeness_audit`, and `_load_saved_data_contract_payloads`. |

`completeness_cmd.py` re-imports every name needed by a surviving local caller
or external consumer, including `app.py`'s package-surface re-export and
direct test imports.

## Change-collision handling

**Change-collision handling (`change_collision.py`).** Handles drift detected *after* `apply_finding` has already written its edits to plan/detail — the "during apply" case `drift_detection.py`'s pre-flight check can't prevent. Rather than keeping claude's edits on disk and pointing the operator at a bare `git diff` (which forces a session-directed merge with no 3-way framing and risks clobbering the operator's own concurrent edits), `handle_drift_collision` saves both versions to a `CollisionSidecar`, restores the pre-apply original, and pauses for the operator to resolve the merge through a session-directed edit (`prompt_user_to_merge` / `emit_collision_summary`) — the tokens already spent on the apply are preserved in the sidecar rather than discarded.

## Audit-shape registry

**Audit-shape registry (`audit_shapes.py`).** The canonical, code-owned table backing CLAUDE.md's six audit shapes (`arm-clustering`, `check-saturation`, `measurement-instrument-adequacy`, `self-seeded-finding`, `remedy-proportionality`, `premise-conditioned-design`) — a deliberate leaf that audit-flow and persistence consumers import but which itself depends on nothing else in `plan_tool`. `AuditShape` records each shape's id, tell, and classification (`checked` vs `judgment_only`); `evaluate_arm_clustering` is the one shape with a shipped detector, returning an `AuditShapeAdvisory` only when material findings form a consensus, gap-free, strict-majority arm across ≥2 audit samples (`is_advisory_emitter_eligible` / `is_well_formed_audit_shape_advisory` gate its output). The other five shapes are intentionally judgment-only — no detector — per CLAUDE.md's warning against building a matcher over conditional prose.

## Escalate-to-split bridge

**Escalate-to-split bridge (`launcher.py:escalate_to_split`).** The single seam from a recognized mixed/structural step (a behavior-preserving refactor fused with new behavior — the one shape `apply_finding` can't fix) to either an *applied* refactor+feature 1→2 split or a `structural-split` *recommendation*; a sibling of the validation primitives above, not a pipeline stage. Decision rule: it applies only when all of **safe** (no downstream `DONE` step blocks the split — a `CURRENT` step is "next runnable" and renumbers cleanly) + caller **`allow_split`** + an interactive **confirm `yes`** hold; every other path (unattended, unsafe, non-TTY, declined) recommends only, and the default path spends no Claude — encoding the two invariants *always surface the more-correct plan* and *never mutate structure unattended*. Its contract is a frozen `EscalateResult` whose `outcome` is one of `applied` / `recommended` / `unsafe` / `proposal-unusable` / `step-missing` (only `applied` mutates), and the seam re-parses the plan from disk on every call. Three callers wire it: the `detail` Phase-B purity check plus convergence loop (`detail.py:generate_detail`), the interactive review/reconcile apply walk (`cli/review_actions.py:_dispatch_structural_escalation`, the arm `_dispatch_apply_finding` delegates to on a `BLOCKED-STRUCTURAL` verdict), and the `completeness-apply` serial walk, where a persisted `medium` `granularity-split` MIXED-STEP finding dispatches through that same `_dispatch_structural_escalation`, gated by `--apply-structural` (recommend-only otherwise); the `create` convergence loop (`create.py:create_plan`) does not yet route through it (create-side trigger deferred). The four structural dispatchers built by `cli/review_actions.py`'s `_build_review_action_fn` single-source their `WalkState` side-effect tail through `review_walk.py:apply_structural_outcome` / `StructuralOutcomeEffects`, and the three bridge dispatchers share its `structural_apply_allowed` gate (file-check stays out of the gate — it inverts the `yes_to_all` rule; escalation's drift `refresh_snapshot` stays inline). Two routing tokens steer it: the `structural-split` recommendation source in `review.py` (classified by `STRUCTURAL_SOURCES` / `is_structural`, deliberately kept out of `APPLY_ELIGIBLE_SOURCES`) and the `BLOCKED-STRUCTURAL` apply verdict parsed by `launcher.py:parse_apply_verdict`.

## Granularity advisor

**Granularity advisor (`granularity.py`).** A cycle-free advisory leaf importing only `schema.py` (`Plan`, `Step`, `ChangeType`) and `review.py`'s finding primitives (`Recommendation`, `_make_rec_id`, `Invoker`) — no CLI, no orchestrator imports — so it sits *below* `create`/`detail`/`completeness`, which import it; `review` never imports `granularity` (the one-way edge keeps it acyclic). Contract: `assess_granularity(plan, *, stage, evidence, invoker=None) -> list[Recommendation]`, where `stage` is `create`/`detail`/`completeness` and `evidence` is a `GranularityEvidence` envelope. The deterministic split/merge detectors read only plan structure and never shell out; `invoker` is consumed only by `detail`'s relocated prose (MIXED-STEP) purity judgment. Two sources: `granularity-split` (a step too big / mixing concerns — generalizes the former `detail-purity` finding, folded in, not forked) and `granularity-merge` (adjacent dependent steps fragmented). Both are advisory and kept **out** of `review.py`'s `APPLY_ELIGIBLE_SOURCES`, so they route through the generic structural-diagnostic `triage_reason` and can never reach `apply_finding` or flip an exit code. Per-stage surfaces: `create`'s change-type review loop shows `granularity-split` hints beside its `(s)plit` action (deterministic, no Claude); `detail`'s MIXED-STEP purity check emits through this source; `completeness-audit` folds both sources into its advisory `Smells (advisory)` bucket. The advisor only advises — it never mutates plan structure. `granularity-split` now has a **second producer** outside `granularity.py` too: reconcile's code-grounded **split finding** (`review.py:_code_reveals_split_recommendations`, the inverse of re-ground), which fires on a **single non-`DONE` step** whose `heuristic_already_done` hits reveal a built part fused with an un-built non-test part, is scoped to the reconcile lane (`reconcile_lane and step_filter is None`), reuses the `granularity-split` **literal** at `severity="info"`, and stays **recommend-only** — `info` (not `medium`) keeps `review_walk.py:split_escalation_target` (which gates auto-dispatch on `severity == "medium"` **and** the source being in `extra_apply_sources`) from ever routing it to `escalate_to_split`, it never flips an exit code, and it stays **out** of `APPLY_ELIGIBLE_SOURCES`. A `granularity-merge` **merge** finding carries a `merge` directive (recovered by `review.parse_merge_action`) that the review/reconcile walk can actuate: behind `--apply-structural`, `_dispatch_merge_remedy` folds the flagged pair through `plan_tool/detail.py:merge_bridge` — which owns the merge safety + TTY-confirm gate and is blocked on a **stale saved directive** — while without the flag it recommends only (the operator can still use the direct `plan-tool merge` form). `granularity-merge` now has a **second producer** outside `granularity.py`: reconcile's code-grounded **re-ground finding** (`review.py:_reground_already_built_recommendation`, fired on **≥2 distinct already-built steps**, scoped to the reconcile lane), which reuses the `granularity-merge` **literal** so it routes through the neutral `triage_reason` branch — never the split bridge. It introduces **no new source token**; the remedy is re-ground / re-baseline (mark done or re-decompose), not a blind `merge`. Re-ground has its own actuator — `plan_tool/reground.py:reground_bridge` marks the already-built steps `done` (and, under the re-baseline disposition, also writes a `create --from-existing` seed) — which the review/reconcile walk dispatches behind the same `--apply-structural` gate, **split from merge by directive kind** (`MERGE_ACTION_MERGE` vs `MERGE_ACTION_REGROUND`) so a merge is never conflated with a re-ground. The umbrella `--apply-structural` is now narrowable: per-remedy `--merge` / `--reground` each enable only their own bridge (`--apply-structural` stays the enable-all superset), and `--reground-rebaseline` makes an applied re-ground additionally write the re-baseline seed. Both stay **out** of `APPLY_ELIGIBLE_SOURCES` (they route through the merge-directive dispatch, not `apply_finding`) and neither flips an exit code.

## Convergence diagnostic

**Convergence diagnostic (`convergence_diagnosis.py`).** A **cycle-free leaf** whose only `plan_tool` imports are `review_persistence`, `review`, `locator`, and `convergence` — no `plan_tool.cli`. It reads a plan's **saved completeness/reconcile report sidecars** (cross-run history) and diagnoses audit/apply loop health: a three-state verdict (`no-history` / `insufficient-history` / `converging`) rolled worst-of across series, plus three newest-run advisories that never alter the headline — `latest_blocking` (unresolved critical/high in the newest audit), `code_drift` (code fingerprint moved since the prior run), and `finding_churn` (same-kind open count and severity ceiling both rose, under the same stage-differentiated conceptual bar `completeness-audit` uses — see docs/how-to/pipeline/audit.md § "Stage bar and mid-run steering" — not a blanket medium+ floor). The decision chain stays `load_report_history` → `diagnose_convergence` → `render_diagnosis`. In parallel, `load_audit_evidence_ledger` → `render_audit_evidence_ledger` provides a read-only completeness-artifact inventory; `cmd_convergence` renders it after the diagnosis without making it input to that decision. Surfaced by `plan-tool convergence <name>` (`plan_tool/cli/convergence_cmd.py`), modeled on `cmd_status`: spends **no Claude**, writes **no run-log entry**, mutates nothing, and **always exits 0** (no `--fail-on-findings`). It consumes only the persisted report subset (recommendations, walk annotations, and the per-run `plan_fingerprint` / `code_fingerprint`). Structural remedies (`split`, `scope-out`, re-seed) stay on their own commands; this diagnostic does not recommend or actuate them.

## Structural remedy vocabulary

**Structural remedy vocabulary.** The tool's four structural remedies are not four primitives but **one `split`/`merge` axis parameterized by two things**: **altitude** — a *step* (→ two siblings) vs the *plan's scope* (→ a narrowed plan + a carved-out remainder) — and **disposition of the carved side** — kept as a sibling step vs carved out to a **forward-seed**. The remedies tie together the escalate-to-split bridge and the granularity advisor above; operators choose among them by judgment when a loop stalls (see `RUNBOOK.md`):

- **re-split** = step-altitude split, both halves kept (`granularity-split` → `escalate_to_split` / `plan-tool split`; also reconcile's code-grounded split finding `review.py:_code_reveals_split_recommendations`, which recommends the same `plan-tool split` at advisory `info` — recommend-only, never through the bridge).
- **scope-out** = plan-scope split, carved side deferred to a forward-seed. Triggered local (one over-packed step, or a contiguous `--step N --through M` band) but acts at plan scope. The executor lives in `plan_tool/scope_out.py`: `render_carved_seed` (deterministic `create --from-existing` seed renderer), `compute_narrow`/`apply_narrow` (carve an ordered id set via drop-renumber + `depends_on` repair + detail migrate/archive, all-or-nothing with rollback), and `scope_out_step` (the apply-or-recommend orchestrator returning a frozen `ScopeOutResult` whose `outcome` ∈ `applied` / `recommended` / `unsafe` / `empty-plan` / `step-missing` — only `applied` mutates). `plan-tool scope-out <name> --step N [--through M]` is wired by `plan_tool/cli/scope_out_cmd.py` (`cmd_scope_out` + `register`), which rejects an out-of-order range. It is **seed-first** and **recommend-only unless `--apply` + a TTY confirm hold** (`-y` is the deliberate second opt-in that bypasses the confirm) — the second instance of the apply-or-recommend gate shape after `launcher.py:escalate_to_split`. It spends **no Claude**: both halves are deterministic, so there is no `invoker=` seam. Mutation is gated only through that one command (`plan-tool scope-out … --apply`).
- **merge / re-ground** = the inverse of split. A pairwise `granularity-merge` **merge** finding now has a bridge: the review/reconcile walk folds the flagged pair through `plan_tool/detail.py:merge_bridge` behind `--apply-structural` (recommend-only without it; `plan-tool merge` remains a direct CLI form). Reconcile's code-grounded already-built re-ground finding re-baselines a ≥2-step set, and the walk actuates it through `plan_tool/reground.py:reground_bridge` behind the same flag — merge and re-ground are split by directive *kind* (`MERGE_ACTION_MERGE` vs `MERGE_ACTION_REGROUND`), keeping re-ground distinct from `merge`. `reground_bridge` now carries **two dispositions** (`DISPOSITION_MARK_DONE` / `DISPOSITION_REBASELINE`): mark-done (the default) just flips the flagged steps `done`; re-baseline additionally writes a `create --from-existing` seed (`render_rebaseline_seed`). The walk's `--apply-structural` umbrella is now narrowable by the per-remedy `--merge` / `--reground` opt-ins (each enables only its own bridge), and `--reground-rebaseline` selects the re-baseline disposition on an applied re-ground. Both stay **out** of `APPLY_ELIGIBLE_SOURCES` (they route through the merge-directive dispatch, not `apply_finding`) and neither flips an exit code.
- **re-seed** = the limit — split everything / restart by operator judgment via `create --from-existing` (not a convergence fork).

Operator-facing walkthrough lives in `RUNBOOK.md`.

## Split-criteria catalog

**Split-criteria catalog (`split_criteria.py`).** A read-only leaf that declares every structural-split criterion the tool already applies — across create-time, detail-time, and completeness-time — as one catalog of frozen `SplitCriterion` descriptors, and renders the plan-independent **legend** (`render_split_criteria`) from that single catalog rather than re-describing each criterion at its call site. The criteria themselves stay owned by their deciders (`granularity.py`, `distill_thresholds.py`, `review.py`, `launcher.py`); this module only catalogs and reports. `evaluate_split_criteria` / `render_plan_breakdown` produce the **per-plan** mode — which criteria actually fired for a given plan — and `compute_criteria_drift` tracks whether that breakdown moved between two fingerprinted runs.

## Decision telemetry

**Decision telemetry (`plan_tool/telemetry.py`).** A **stdlib-only leaf** (imports nothing first-party, so any module — including cycle-sensitive leaves — can record without a cycle) and tolerant reader. `record_decision` appends one locked `DecisionEvent` per line to `.plan-tool/telemetry/decisions.jsonl` (gitignored, local); recording is best-effort and must never break the observed command. Telemetry stores code state as a compact equality digest, while grounding and saved-review flows retain full path/hash maps where they need per-path comparison. A create assessment owns its shared code-state snapshot and its child outcomes join through one assessment occurrence ID. `plan_tool/launcher.py:apply_finding` classifies apply results, including unusable primary and auto-fix follow-up responses. Speculative parallel workers suppress durable writes and `plan_tool/cli/completeness_apply_parallel.py:replay_results` records only the canonical landed result; interactive review defers successful verdicts until the operator keeps the edit but records invocation failures on early failure paths. `plan_tool/telemetry_analysis.py:analyze_decisions` then computes advisory outcomes on read. Schema in `DATA_CONTRACT.md` (drift-guarded).

## Data contract registry

**Data contract registry (`data_contract.py`).** The code-owned registry backing `DATA_CONTRACT.md`'s drift guard (`tests/test_data_contract.py`): `persisted_dataclass_contracts` / `json_object_contracts` name every persisted dataclass, sidecar JSON object, and durable config file, discovering their fields from the live runtime classes rather than hand-copying them, so the registry can't silently drift from the code it describes. `intentional_exclusions` records fields deliberately left out of a contract (with a reason, mirroring the `ALLOWED_DUPLICATE_GROUPS` pattern elsewhere); `check_input_contract_references` verifies a contract's cited code anchors (`file:symbol`) actually resolve; `registry_fingerprint` / `contract_fingerprint` / `make_drift_record` support the fingerprint-gated drift check itself.

## Branch-awareness

**Branch-awareness (opt-in; OFF by default).** Three cycle-free leaves carry it: `plan_tool/project_config.py` (the `branch_awareness.enabled` flag + `branch_prefixes`, resolved `PLAN_TOOL_BRANCH_AWARENESS` env → project `.plan-tool/config.json` → user `~/.plan-tool/config.json` → `false`), `plan_tool/branch_binding.py` (the untracked git-config ad-hoc override store), and `plan_tool/branch_ownership.py` (the two lookups + the 4-tier classifier). The run guard wires them at `plan_tool/cli/run_cmd.py:_preflight_branch_guard`. The feature is **inert unless enabled** — callers gate on `branch_awareness_enabled` first and short-circuit; with the flag off every repo behaves byte-for-byte as before.

**Merged-plan preflight (on by default).** `plan_tool/plan_merge_guard.py` is a read-only, git-only module: `check_plan_merged` reports whether the plan and a detail file for every committed step are on `origin`'s default branch, and whether they differ from it beyond the fields `run` writes. `plan_tool/cli/run_cmd.py:_preflight_merged_plan_guard` maps the result to a refusal (on the default branch, or files missing there), a warning (drift or an unverifiable ref), or silence (no `origin`). `project_config.require_merged_plan` (env `PLAN_TOOL_REQUIRE_MERGED_PLAN` → project → user → `true`) and `run --skip-merge-check` turn it off. It is independent of the opt-in branch-awareness flag above. See [`docs/how-to/pipeline/run.md`](how-to/pipeline/run.md#the-merged-plan-preflight).

## Annotate bridge

**Annotate bridge (`annotate.py`, `annotate_render.py`).** The forward-seed bridge described in the repo's top-level CLAUDE.md: `classify_plan_implementation` (`annotate.py`) ingests an arbitrary plan or notes file, code-grounds each section against the current repo (reusing the verified `--from-existing` grounding anchors), and asks claude for a per-section IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED / NEEDS-REVIEW verdict backed by concrete code references — the `PlanAnnotation` contract this module produces and renders nothing itself. `annotate_render.py` turns that result into the two operator artifacts: `render_annotated_report` (the lossless audit — the original file verbatim with a status block inserted after each matched heading, a strictly-additive guarantee its own tests lock down) and `render_create_seed` (the compact NOT-IMPLEMENTED/actionable carryover brief for the next `create --from-existing`). Never mutates its source except the opt-in `--archive` move.

## Parallel plan worktrees

**Parallel plan worktrees.** An off-spine provisioning verb group that gives each plan its own isolated working copy so several plans' long `create`/`detail`/`run` processes run in parallel without sharing one index/branch/checkout. Three layers: the policy-free git primitives in `plan_tool/cli/gitcommit.py` (`worktree_add`, `worktree_list`, `worktree_remove`, `worktree_prune`, `clone_repo` — `(rc, tail)` style, never raise); the pure path/config leaf `plan_tool/worktree.py` (`worktree_base`, `derive_worktree_path`, `classify_target`, reusing `project_config.py`'s tolerant layered reader; default base a **sibling** of the repo, never inside it); and the command group `plan_tool/cli/worktree_cmd.py` (`cmd_worktree` dispatching `add`/`list`/`remove`/`prune`), which owns branch + start-point resolution, the reuse-vs-fail tiebreak, kind dispatch, and the clean-tree gate. Key rules: the branch is **born inside the add** (never a main-tree `switch -c` — git refuses to check the same branch out twice); `--clone` is the full-isolation opt-in (an independent repo, not a shared-store worktree); the dirty gate protects *worktree* deletion while a **clone is never auto-deleted** (cleanup outside the tool — its committed-but-unmerged work is invisible to the uncommitted-only gate, and it carries no plan-tool provenance marker); and neither `remove` nor `prune` deletes the branch or leaves extra state.

## Plan sweep

**Plan sweep (`sweep.py`).** Backs `plan-tool sweep`: pure deterministic logic (no claude call, no network) that archives completed plans and reports on the rest. `classify_plan` auto-archives only when *both* the plan's top-level `status` is `completed` *and* every committed step's `status` is `done` (parked `deferred`/`wont_do` steps don't block archival) — a deliberately strict AND, chosen to minimize false-positive archival over a looser either-or. `archive_completed_plan` / `withdraw_plan` perform the move (with a `_dedupe_archive_path` collision-numbering scheme) and `_archive_plan_details` carries the plan's detail files along with it; `discover_orphan_plans` separately surfaces plans present on disk but missing from the manifest.

## Installed skill

**Installed skill (`plan_tool/cli/skill_cmd.py`).** Backs `plan-tool
install-skill`, the opt-in verb that lets Claude Code, Codex, or Cursor
drive `plan-tool` for an operator — the CLI itself is standalone and needs
no skill. Installs two files as one set under `<root>/skills/plan-tool/`
(or `~/<root>` with `--user`): the bundled `integrations/<integration>/SKILL.md`
router for the chosen `--integration` (`claude`, `codex`, or `cursor`), and a
`DIRECTIVES.md` sibling copied or symlinked from the single shared
`integrations/shared/DIRECTIVES.md`. The split is deliberate — each router
answers "which command for this situation" and stays thin, while
`DIRECTIVES.md` owns the driving rules themselves (the audit gates,
`--iterate`/`--commit`, the convergence loop, roadmap operation) in exactly
one tracked file every backend cites identically, so there is one place to
keep those rules current rather than one copy per integration. Every
destination in the set is classified (`missing` / `already` / `mode-switch` /
`collision`) against the requested mode before any write. A destination
already correct **for the requested mode** is left untouched; one correct
for the *other* mode (e.g. a matching symlink found while `--copy` is
requested) still needs `--force` to switch, exactly like a real collision —
content- or target-matching can't prove the file is plan-tool's own prior
install rather than a coincidence, so `mode-switch` only sharpens the
refusal message, it doesn't skip the confirmation. A collision (foreign or
mode-switch) at either path refuses the whole set rather than leaving it
half-installed, and `--force` unlinks only the paths that actually need it
(a directory
occupying a destination refuses regardless of `--force`, since it can't be
cleared by `unlink()`). `--integration codex` is the one
variant with fixed defaults: Codex scans `.agents/skills` and skips a symlinked
`SKILL.md` without logging, so it defaults `--root` to `.agents` and always
copies (an explicit `--root .claude` is still honored).

## Jira export

**Jira export (`jira_grade.py`, `jira_config.py`).** `jira_grade.py` is the single authority for the legacy **jira-grade** detail contract — the five-section alternative (`Intent`, `Change`, `Constraints`, `Done when`, `Out of scope`) to the default run-grade seven-section body. `detail --grade jira` is disabled; existing artifacts remain selected through `jira --grade jira`, `run --detail-grade jira`, and `completeness-audit --grade`. `parse_jira_grade_sections` / `validate_jira_grade_body` / `load_jira_grade_detail` give those readers one shared, loudly-rejecting contract rather than each re-deriving the schema; `check_plain_english` is the deterministic prose gate applied to the text between code anchors. `jira_config.py` reads/writes the export-time config at `docs/implementation-plans/jira-config.json` — the epic catalog (`Epic`: uppercase `key`, name, optional real JIRA id) and the plan→epic assignment map `jira` export consults to pick which epic prefixes a plan's exported story ids (`AUTH-S1`, …). Schema for both in `JIRA_FORMAT.md`.

## Roadmap

### Read-only snapshot comparison

`roadmap_compare_run.py` resolves the accepted-head or explicitly selected
stored base and the active-candidate or explicitly selected stored target through
`roadmap_versions.py:VERSION_ARTIFACT_INVENTORY`. An omitted target is the
active candidate; with none active the route refuses and asks for an explicit
target, and an omitted base is the accepted head. It captures the complete Git
patch for that fixed inventory, then passes parsed comparison facts to
`roadmap_compare.py`, `roadmap_diff.py`, and `roadmap_compare_render.py`.
Renderers reuse `roadmap_view.py:display_label` for reader wording. This is a
read-only branch: it owns no lifecycle transition and never invokes a roadmap
writer. **Its import graph does not yet match that**: `roadmap_diff.py` and
`roadmap_compare_run.py` import `RoadmapStage`/`STAGES` from `roadmap.py` —
the stage-execution module — purely for that pure-data shape, not for
anything it invokes; BACKLOG #406 tracks extracting them into a leaf module
so the import graph is read-only too. A second edge: `roadmap_compare_run.py`
imports `load_stored_candidate_proposal` from `roadmap_candidate_run.py`, which
in turn imports writer-layer modules; the comparison route only reads through
it (BACKLOG #406 also tracks moving that loader into a read-only leaf). The
route binds a candidate target's row-linked prose amendments only when the
selected base is its stored direct predecessor, reporting `bound`,
`not-applicable`, `not-directly-bound`, or `no-operation-evidence` and never inferring a binding from
changed bytes. The CLI dispatch keeps `--compare`
exclusive so existing one-snapshot `--view` routes and lifecycle actions
retain their boundaries.

`roadmap_diff.py:ordered_stage_collections` delegates its per-artifact-type
collection lookup to `roadmap_artifacts.stage_row_collections` rather than
hand-maintaining a second isinstance dispatch (that function's own docstring
warns two such copies would drift), but keeps its own fail-closed `TypeError`
guard for an unsupported artifact type rather than relying on
`stage_row_collections`'s permissive fallback, which has none (BACKLOG #416
tracks closing that gap at the source for every caller, not just this one).

`roadmap_compare.py:_stripped_for_comparison` ignores a REFERENCE field's
`entity_id` only where `roadmap_relations.py:_row_relation_specs` treats it
as a relation, but does not replicate that function's additional `entity_id
is not None` condition: stripping a field whose `entity_id` is already
`None` is a no-op either way, so a REFERENCE field transitioning to/from
`None` is a relation-only change like any other retarget — verified by
`tests/test_roadmap_compare.py::test_reference_field_entity_id_from_none_is_also_a_relation_only_change`.

### Immutable roadmap evidence

**Immutable roadmap evidence (`roadmap_evidence_store.py`).** A stdlib leaf
for noncanonical opaque evidence. `publish_evidence` accepts only the
code-owned `EvidenceNamespace` token, a 64-lowercase-hex final name, and
complete `bytes`; it returns `created`, `existing`, `invalid-input`, or
`write-failed`. The decision-settlement namespace is fixed at
`<roadmap-dir>/.plan-tool/evidence/decision-settlements`; the existing roadmap
root is the caller's only path input. Each call synchronizes the fixed namespace
ancestry it observes, publishes a uniquely and exclusively created private
temporary through an exclusive final hard link, synchronizes its bytes before
the link (including macOS `F_FULLFSYNC`), and synchronizes the final namespace
before returning created or existing bytes. An exact raw directory-entry name
is required before an `EEXIST` result becomes `existing`, so a case-folded
nonmatching collision is a write failure rather than evidence. The creator
best-effort removes only its own dot-prefixed temporary; old dot files are
ignored. `scan_evidence` validates the same namespace, synchronizes its entry
snapshot, and returns only matching opaque final records in raw-name order. A
missing fixed namespace returns an empty listing without creating a directory,
so pure evidence inspection remains read-only.
Neither operation parses evidence, exposes a CLI, chooses a route, invokes a
backend, writes canonical roadmap artifacts, acquires a lock, probes platform
capability, proves ownership/link counts, recovers temporary state, or assigns
an unsafe-entry status.

**Decision-settlement receipts (`roadmap_decision_settlement.py`,
`roadmap_decision_settlement_receipt.py`, `roadmap_decision_settlement_run.py`,
`roadmap_decision_settlement_enrolled.py`, `cli/roadmap_cmd.py`).** The
settlement layer moves one selected Roadmap-derived `pending` decision to
`settled`, bound to named reviewer evidence. A read-only leaf
(`roadmap_decision_settlement.py`) proves the transition is legal before any
writer runs. Its evidence is a ledger item that is still eligible for the
accepted version (a closed, deferred, awaiting-review, or stale item refuses
`feedback-not-eligible`), and the evidence digest binds only the
reviewer-authored fields, never a model proposal. A receipt builder and
publisher (`roadmap_decision_settlement_receipt.py`) builds a redacted,
hash-named receipt from that proof and publishes it once into its own
`EvidenceNamespace.DECISION_SETTLEMENTS` namespace, fully determined by its
inputs (no timestamp), so a retry with the same inputs resolves to the same
final bytes. The receipt commits to `HEAD` before any canonical write.
`roadmap_decision_settlement_enrolled.py` is the only runner: it stores the
settled artifact as a new immutable version and advances the accepted head
through its own `"decision-settlement"` `PendingGeneration` kind, calling
`roadmap_writer_guard`/`publish_roadmap_generation`/
`recover_roadmap_publication` directly — the same general-purpose
writer-token/journal/selector-swap primitives `promote_review_seal` also
consumes, never that writer's model-authored admission/review/seal chain;
`roadmap_decision_settlement_run.py` holds its result types. A receipt proves
completion for as long as the settled version stays in the accepted head's
predecessor chain. `ROADMAP_FORMAT.md` owns the operator-visible command
contract and refusal set.

**First-run resume (`roadmap_stage_resume.py`).** A leaf whose only
first-party imports are `fileio`, `roadmap_artifacts` (slug validation), and
`run_log` (the run directory). It is the sole owner of the resume directory
`.plan-tool/runs/<slug>/roadmap-stage-resume/`: one `stage-<N>.md` per
gate-clean stage plus `brief.digest`. Stage text is stored unparsed, so
re-gating belongs to the stage run. A damaged held stage costs only its own
regeneration (warned, never raised, never deleted by a read); only a
brief-digest mismatch raises. `roadmap.py:_run_roadmap` publishes the version,
ledger, and accepted head only after all four stages pass, writing the head
last, then deletes the directory. The run refuses once an accepted head exists,
and refuses a folder with no head that holds pre-head state. The directory is
not user-editable input. `ROADMAP_FORMAT.md` owns the operator-visible
contract.

**Version index (`roadmap_index.py`).** A leaf over the version store that
renders the roadmap folder's `INDEX.md`: the accepted head and every stored
version's status, with the accepted version's stack summary. It imports only
`fileio`, `roadmap_artifacts`, `roadmap_stack_summary`, and `roadmap_versions`,
and must not import the roadmap orchestrator or the
candidate-run module, because the orchestrator imports it; the candidate record
names it needs are mirrored and pinned by `tests/test_roadmap_index.py`.
`INDEX.md` is generated for people; no command reads it.

**Stack summary (`roadmap_stack_summary.py`).** The one producer of stack
summary lines for the first-run completion output, `INDEX.md`, and candidate
review (the candidate callout adds the stack delta by row id and the listed
hosting and store products). It is read-only: plain text lines over parsed
values, with no I/O, no backend call, and no judgment of a choice. Its only
first-party import is `roadmap_artifacts`. `roadmap_index.py` and
`cli/roadmap_cmd.py` import it, never the reverse, and it must not import
`roadmap.py`, `roadmap_index.py`, or `cli`. The `## Stack` seed section is
rendered separately by `_render_stack_section` in `roadmap.py`, from the same
accepted rows. `ROADMAP_FORMAT.md` § "Stack rows" owns the contract.

**Roadmap (`plan_tool/roadmap.py`, `roadmap_artifacts.py`, `roadmap_gates.py`, `roadmap_versions.py`, `roadmap_index.py`, `roadmap_stack_summary.py`, `roadmap_stage_resume.py`, `roadmap_seed_manifest.py`, `roadmap_view.py`, `roadmap_html.py`, `roadmap_er.py`, `roadmap_candidate_narrative.py`, `cli/roadmap_cmd.py`).** A project-altitude authoring verb one rung above `create`: `plan-tool roadmap <slug> --from-existing <concept.md>` runs the four gated stages once and publishes the `01-domain`, `02-constraints`, `03-components`, and `04-roadmap` artifacts as one immutable version under `<plans_dir>/roadmaps/<slug>/`. Every roadmap is versioned from birth: the immutable version under the accepted head is the only stored copy of its content, and every command reads it. A stage-4 write publishes the plan mapping but does not materialize a draft seed; `--materialize` and `--refresh-seeds` generate drafts separately, while `--accept-seed` records a reviewed direct edit as current without a backend call.

The shared leaves form a one-way import chain that forks below the gates: `roadmap_artifacts.py` has no first-party imports and owns paths, parse/rendering, closed vocabularies, and immutable feedback ceilings; `roadmap_gates.py` imports that leaf plus `scope_fence.py` (itself stdlib-only, for canonical frontmatter-stripping and fence-aware H2 extraction) and returns `Violation` values; `roadmap_seed_manifest.py` classifies on-disk drafts from the accepted version and sidecar. `roadmap.py` owns the stage table, the authoring loop, brief admission, and run log, including shared redacted failure-receipt emission for rejected replies from stage authoring. `roadmap_view.py` is read-only and renders the accepted version's parsed artifacts without running gates; `roadmap_html.py` is a leaf above it holding the sixth view, `--view html`, and the edge is one-way (`roadmap_view.py` never imports it). `roadmap_er.py` sits under `roadmap_html.py` and owns that page's ER-style entity diagram — a stdlib-only leaf with no first-party imports, taking an already-resolved description of boxes and edges rather than roadmap types, so reference resolution stays in `roadmap_html.py` beside the table's and the two renderings of one field cannot drift apart. `roadmap_candidate_narrative.py` is a pure function over candidate bytes with no model call or filesystem write; its first-party imports are `roadmap_artifacts.py`, `roadmap_gates.py`, and `roadmap_versions.py`. `cli/roadmap_cmd.py` resolves paths, enforces exclusive modes, maps exits, and renders summaries.

**Direct stage-run status.** `roadmap.py:_run_roadmap` decides when a stage run
has confirmed a stage start, retry or stop, write, and returned-result
transition. In the ordinary `run_roadmap` dispatch,
`cli/roadmap_cmd.py:cmd_roadmap` supplies the direct stderr sink; `style.note`
is presentation-only and does not decide that a transition exists. These
bounded lines report the last confirmed transition, not timing or backend
liveness, and leave stdout summaries and result payloads unchanged. Views, seed
operations, candidate operations, and other non-stage routes do not receive this
surface.

**A stage is a row of data, not a branch:** `RoadmapStage` is `(prompt file, artifact path, parser, renderer, gate set)`. A later stage is a table entry and prompt file rather than an orchestrator branch. **Each stage consumes the previous stage's gate-clean text:** a stage that passes is held in the resume directory, and a resumed run re-gates each held stage before it runs the next one.

The reviewer ledger remains mutable input outside artifact versions. `--propose-candidate` snapshots eligible items and derived context into one exact root/source batch, then validated typed operations classify an inert bounded or structural candidate; users never choose that route. Candidate evidence and `CandidateReviewSeal` are immutable review records. `--propose-candidate` sources a new batch from the active candidate, so batches stack. `roadmap_candidate_run.candidate_stack_route` derives the unpromoted stack above the recorded root from stored candidate records at use, and calls it structural when any hop stores a STRUCTURAL route; nothing about the stack is persisted. The stack-aware guards — answered-route entry, decision eligibility and edit acceptance, the promotion boundary, and recovery's seed predicate — all ask that one derivation. A structural approve/edit/reject decision acts on the active top candidate and covers the whole stack: `roadmap_candidate_review.build_candidate_stack_view` describes it and computes a stateless digest, approve is two invocations, and only the invocation whose `--confirm-stack-digest` matches the recomputed digest creates the `structural-approval` seal. Edit stores a replacement requiring a fresh decision and rejection releases only the active pointer, dropping the unpromoted hops. `promote_review_seal` alone turns an approved seal into journaled publication after accepted-root, active-candidate, stored-binding, and gate rechecks; it is the `AcceptedRoadmapHead` boundary and applies the seed-state effect when any hop above the recorded root stores a structural route. All other outcomes preserve canonical artifacts, seeds, and the accepted head. `roadmap_candidate_review.seal_review` and the structural approve path recompute narrative evidence from the stored candidate bytes through `roadmap_candidate_narrative`, refuse only the blocking class, and store nothing; `cli/roadmap_cmd.py` displays the same finding list (contract: `ROADMAP_FORMAT.md` § "Narrative review evidence").
A failing stage gate retries the stage with its violations; an exhausted stage stops the arc. A preflight failure stops before an invocation. The verb is non-interactive: a load-bearing unanswered choice becomes a `pending` decision for review, not an implicit model decision. Roadmap artifacts are not plans, so nested roadmap files are not plan-discoverable and a run adds no plan manifest entry. `04-roadmap.md` is the final stage artifact; a successful replacement invalidates existing derived drafts without regenerating them. `--apply` is the separate confirm-gated seed mutation route. `roadmap_view.py` provides deterministic read-only traceability, decision-ledger, and reverse-citation views over the accepted version's artifacts, and `roadmap_html.py` adds the full-content, print-formatted `--view html` page for reading a roadmap rather than auditing its state — written to `<roadmap-dir>/review.html` by default (`--output PATH` chooses the destination; `--output -` prints to stdout instead). That page opens its domain section with an inline-SVG ER diagram of the entities and their reference fields; it draws no cardinality, because the domain artifact records none. `ROADMAP_FORMAT.md` owns the schema and route contract; `docs/how-to/roadmap.md` covers the end-to-end workflow.

## CLI reference generation

**CLI reference generation (`cli_reference.py`).** A leaf doc-generation module backing `docs/cli/`: it imports the assembled parser (`plan_tool.cli.build_parser`) and walks argparse's own introspection surface to render one Markdown file per subcommand plus an index, so the reference set can never drift from the actual CLI surface — the argparse parser is the single source of truth for flags, defaults, choices, and help text. Generated, not directly edited; regenerate with `python -m plan_tool.cli_reference --write`, drift-guarded by `tests/cli/test_cli_reference.py`.


### Seed output paths

`seed_paths.py` is a stdlib-only leaf shared by seed writers. New default seeds
use `docs/implementation-plans/plan-seeds/`. Existing roadmap publications use
their recorded root/nested layout rather than directory-existence guessing.
Explicit annotate destinations remain authoritative. No file migration runs.
