> **Auto-archived**: this plan was swept on 2026-07-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add the `direct-jira` verb that chains create, detail, and jira in one process

## Summary

This step adds the `cmd_direct_jira` verb to `plan_tool/cli/direct_cmd.py` (the leaf step 3 creates). The verb runs the whole `create → detail → completeness-apply → jira` chain in one process: it gates on a clean tree, calls `cmd_create`, catches the `CreateResult` through step 2's namespace sink, runs step 3's size-gate helper on it, builds a `--detail-only` detail namespace and calls `cmd_detail`, **commits the authoring artifacts, calls `cmd_completeness_apply` with `--jobs N -y` to apply the conceptual gaps from detail's saved audit, commits those**, then builds a jira namespace and calls `cmd_jira`. The key design decision is that the verb **reuses the existing stage handlers** (`cmd_create`, `cmd_detail`, `plan_tool/cli/completeness_apply*`/`cmd_completeness_apply`, `cmd_jira`) and threads one args namespace into each — it holds no stage logic of its own, and cross-cutting flags (`--backend`, `--model`, `--on-rate-limit`, `--fallback-backend`) ride through unchanged because they are copied into every stage's namespace. The `completeness-apply` stage is why the verb both requires a clean tree up front and commits mid-chain (its `--jobs N` worker isolates in a worktree off HEAD). On green, `plan-tool direct-jira --from-existing <seed>` (once step 6 wires the parser) chains the stages and produces a Jira-story export with conceptual completeness gaps converged in-chain, a stage's non-zero exit stops the chain and is returned as-is, and the new verb + flag-propagation + failure tests in `tests/cli/test_direct_cmd.py` pass.

## Table of Contents

- [Summary](#summary) — what the verb ships and the result on green.
- [Why](#why) — why the chain needs a first-class verb now.
- [Input](#input) — the `CreateResult`, size-gate, and handler args contracts this verb reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — two edits, no new files.
- [Implementation](#implementation) — the chain order, the sink hand-off, and the namespace-building gotchas.
- [Tests](#tests) — chain, flag-propagation, split, and mid-chain-failure cases.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — argparse, Claude CLI flags, pytest monkeypatch.
- [Deferred](#deferred) — the second verb, parser registration, and threshold tuning left to other steps.

## Why

The three pipeline stages exist only as separate CLI runs today: an operator runs `create`, then `detail`, then `jira`, each re-reading the plan from disk, each re-passing the same `--backend`/`--model`/`--on-rate-limit` flags, and each a manual hand-off where a wrong path or forgotten flag breaks the chain. `BACKLOG.md #118` asks for a single verb that expresses the common "turn this idea into Jira-sized stories" intent. Steps 2 and 3 have landed the two seams this needs — step 2's namespace sink lets `cmd_create` hand its `CreateResult` back in-process, and step 3 landed the size-gate helper in `plan_tool/cli/direct_cmd.py` plus the leaf itself. This step spends those two seams: it adds the first of the two direct verbs, `direct-jira`, wiring the three handlers into one process. Step 5 adds the sibling `direct-run` verb into the same file; step 6 registers both with the parser.

## Input

This verb reads three contracts it does not own:

- **`plan_tool/create.py:CreateResult`** — delivered in-process through step 2's `_create_result_sink` list attribute on the create args namespace. The verb depends on three fields: `plan_path: Optional[Path]` (the created plan to chain into `detail`/`jira`), `split_proposal`, and `iteration_stage_failure`. `plan_path` is `None` **only** on the multi-plan split short-circuit (`split_proposal` set, no plan written); every normal create sets it. `iteration_stage_failure` is set when `create`'s post-write convergence loop aborted — `cmd_create` still returns `0` on that path, so the verb must read this field, not the rc, to detect an unconverged plan. The verb must branch on `plan_path is None` and on `iteration_stage_failure is not None` before chaining forward.
- **Step 3's size-gate helper and its `SizeGateResult`** — the frozen result (flag + measured step count + threshold + human reason) step 3 landed in `plan_tool/cli/direct_cmd.py`. The verb calls the helper on the `CreateResult` and acts on the returned verdict; it does not re-measure the plan itself. Step 3 owns how the gate treats the `plan_path is None` split case — the verb consumes the verdict, not the internals.
- **The downstream handlers' args contracts** — `cmd_detail` reads `args.name`, `args.step`, `args.force`, `args.dry_run`, `args.detail_only`, `args.reconcile`, `args.all`, `args.commit`, `args.jobs` (some direct, some via `getattr`); `cmd_completeness_apply` reads `args.name`, `args.jobs`, `args.yes`, `args.anchor`, `args.id`, `args.rewalk`, `args.include_info`, `args.apply_structural`, `args.commit`; `cmd_jira` reads `args.name`, `args.lint`, `args.output`, `args.epic`, `args.max_hours`, `args.format`, `args.dry_run`, `args.no_write`, `args.stdout`. Several are direct attribute reads that raise `AttributeError` if missing, so the built namespaces must carry them.
- **`commit_all` / `working_tree_dirty`** (`plan_tool/cli/gitcommit.py`) — the clean-tree gate at chain start and the two mid-chain commits (authoring, then applied gaps). `commit_all` returns `(rc, tail)`; unpack the rc, don't truthiness-test the tuple.

**Verification limit:** step 6 owns the actual `direct-jira` subparser and its flag defaults, so at HEAD there is no parser feeding this verb an args namespace. Tests for this step construct the args namespace by hand (see [Tests](#tests)); the field-completeness of the real parser namespace is verified end-to-end in step 6.

## Files (creates vs edits)

- **New files:** none. `plan_tool/cli/direct_cmd.py` and `tests/cli/test_direct_cmd.py` are both created by step 3.
- **Existing files (edits only):**
  - `plan_tool/cli/direct_cmd.py` — add the `cmd_direct_jira(args)` verb function (and any small private helper it needs to build a stage's args namespace). Do not touch step 3's size-gate helper, `SizeGateResult`, or the threshold constant beyond calling them.
  - `tests/cli/test_direct_cmd.py` — add the chain, flag-propagation, split-short-circuit, and mid-chain-failure tests for the new verb.

## Implementation

**What the verb does, in order.** `cmd_direct_jira(args)` runs the stages in one process and returns an `int` exit code:

0. **Clean-tree precondition.** Before `create`, check `plan_tool/cli/gitcommit.py:working_tree_dirty(repo_root)`. If dirty, stop with rc 2 and a `direct-jira`-specific message ("`direct-jira` requires a clean working tree (it commits the plan it authors before applying completeness gaps; commit or stash first)") — do **not** name `--commit`. This is needed because step 5.5 below runs `completeness-apply --jobs N`, which isolates in a worktree off HEAD and so requires a clean tree; committing mid-chain with `git add -A` is only safe if the tree started clean. (`direct-jira` gained this precondition when the chain added `completeness-apply`.)
1. **Create.** Set a fresh `list` on the create args namespace under step 2's `_create_result_sink` attribute, then call `plan_tool/cli/authoring.py:cmd_create`. Read the deposited `CreateResult` back out of the list afterward. If `cmd_create` returns non-zero, return that rc immediately (the chain stops at the first failing stage).
2. **Guard the hand-off.** If the create surfaced a multi-plan split (`result.split_proposal is not None` / `result.plan_path is None`), the chain cannot continue — there is no single plan to detail or export. `cmd_create` has already printed the split proposal and returned 0, so stop the chain here (exit 0) with a message naming the split, without treating it as a hard failure. Next, if `result.iteration_stage_failure is not None` — an unconverged create (`cmd_create` returned 0 but its convergence loop aborted) — surface it and stop **unconditionally** (no interactive continue-prompt) rather than chaining an unconverged plan forward; do not rely on the rc, which is 0 here. Then run step 3's size-gate helper on the `CreateResult`; if it flags the plan over-large, print the gate's human reason (pointing the operator at running the stages standalone) and stop.
3. **Detail.** Build a detail args namespace (see below) with `detail_only = True`, set its plan name to the created plan, and call `cmd_detail`. This audits completeness and **saves the conceptual gap map** to the report sidecar (it does not apply conceptual gaps — #85). Return its rc if non-zero.
4. **Commit authoring.** Commit the create/detail artifacts with `commit_all(repo_root, subject)` so the tree is clean for `completeness-apply`'s worktree isolation. Unpack the `(rc, tail)`; a non-zero commit rc stops the chain.
5. **Completeness-apply.** Build a completeness-apply namespace with `jobs = N` (N>1), `yes = True` (**never** bare `-y`, which silently skips the walk on non-interactive stdin), plus the direct-read fields `id`/`anchor`/`rewalk`/`include_info`/`apply_structural` (see the namespace bullet). This reuses detail's newest **saved** audit (no re-audit) and applies the conceptual `plan-correctness`/`plan-completeness` gaps in a single replay pass. Return its rc if non-zero. Then commit the applied gaps — but **only if the tree is now dirty** (`working_tree_dirty`): a no-op apply (detail's audit found no conceptual gaps — the common small-work case) leaves nothing staged, and an unconditional `commit_all` would fail (non-zero on empty commit) and wrongly halt the chain.
6. **Jira.** Build a jira args namespace the same way and call `cmd_jira`. Return its rc.

**Reuse handlers, not orchestrators — this is the key choice.** Call `cmd_create`/`cmd_detail`/`cmd_jira`, not `create_plan`/`generate_detail`/`export_jira`. The handlers own flag parsing, the run-log lifecycle, the gates, and the exit-code convention; calling them keeps every chained stage behaving exactly as its standalone verb. The rejected alternative — a shared orchestrator-level chain calling the `*_plan` functions directly — would duplicate the CLI wiring the handlers already own and is called out in the plan's `## Architecture` **Trade-offs.** paragraph and framed as out-of-scope under `## Out of scope` ("New orchestrator logic").

**Build each stage's namespace by copying, then overriding.** Follow the idiom already in `plan_tool/cli/authoring.py` where the completeness tail does `argparse.Namespace(**vars(args))` and then sets the fields that stage needs. For each downstream stage:
- Start from `argparse.Namespace(**vars(args))` so every cross-cutting flag (`backend`, `model`, `on_rate_limit`, `fallback_backend`, `yes`, `no_wait_on_rate_limit`) copies through unchanged. This is what makes flag propagation free — no stage sees a different backend or rate-limit policy than it would standalone.
- Set the plan name the handler resolves against. `cmd_detail` and `cmd_jira` both resolve their target through `resolve_plan_for_context(ctx, args.name)`, so set `name` to the created plan's handle. Derive it from `CreateResult.plan_path` (the authoritative handle from the sink — e.g. its stem) rather than re-deriving from the seed; `cmd_create` has already registered the plan in the manifest so the lookup resolves.
- Set the stage-specific attributes that handler reads **directly** (not via `getattr`), or it raises `AttributeError`. For `cmd_detail`: at least `step` (None → all steps), `force`, `dry_run`, `detail_only` (True). For `cmd_completeness_apply`: `jobs` (N>1), `yes` (True), and the direct reads `id` (None), `anchor` (None), `rewalk` (False), `include_info` (False), `apply_structural` (False) — these are **not** global base-parser flags, so the copied namespace lacks them and the handler crashes mid-chain without them (the stubbed tests can't catch this — only a real chained run does, so set them explicitly). For `cmd_jira`: at least `lint` (False), `output` (None), `epic` (None → the handler prompts/assigns), `max_hours`, `format`, `dry_run`, `no_write`, `stdout`. This hand-built namespace is the plan's stated "namespace drifts from the standalone parser" risk — keep it field-complete against what each handler touches.

**Invoke `detail` in `--detail-only` mode — set `detail_only = True` on the detail namespace.** The namespace is *copied* from the create-flavored args, and `create` defaults `--iterate` **ON**, so a passive copy would run `detail`'s costly per-step detail-quality loop. `--detail-only` (`cmd_detail`, `authoring.py:~1143`) pins the completeness tail's `--iterate` ON while keeping the per-step detail-quality loop off (`detail_budget.enabled = False`). What the pinned tail buys is **deterministic well-formedness convergence + a saved conceptual gap map** — *not* conceptual application: under the #85 read-only-audit split (`completeness_cmd.py:153-158`) the tail leaves `plan-correctness`/`plan-completeness` gaps unapplied. That saved map is exactly what step 5's `completeness-apply` consumes. So set `detail_only = True` on the copied detail namespace and let `cmd_detail` own the internal pin; do **not** also set `iterate`. Assert `detail_only is True` on the detail namespace in the tests. Do **not** claim detail's tail converges conceptual completeness — it does not; the following `completeness-apply` stage does.

**Exit codes follow the standard convention.** Non-zero means a stage failed to complete; return the first non-zero stage rc and stop. A clean full chain returns 0. The size-gate stop and the split short-circuit are deliberate halts on a plan that *did* get created and is usable on disk — recommend returning 0 with a clear message there (the plan is written and re-runnable by hand), consistent with `plan-tool`'s "exit non-zero only on failure-to-complete" rule. Pin whichever code you choose with a test so the two direct verbs stay consistent with each other.

**Keep the leaf thin and the writer single-sourced.** `cmd_direct_jira` composes handlers and holds no create/detail/jira logic. `cmd_create` remains the only writer of new plan frontmatter — do not duplicate any create-side work in the verb.

## Tests

Add these to `tests/cli/test_direct_cmd.py`. Build the args namespaces by hand (`argparse.Namespace(...)`) and stub the handlers at the module level (`monkeypatch.setattr` on `plan_tool.cli.direct_cmd.cmd_create` / `cmd_detail` / `cmd_completeness_apply` / `cmd_jira`, plus `commit_all` / `working_tree_dirty`) so no stage runs for real and no backend spawns — the `tests/cli/conftest.py` autouse gate already fails the test if a real backend is invoked. Each new test must be green before the step is done.

- `test_direct_jira_chains_all_stages` — with stubbed handlers all returning 0, the verb calls `cmd_create`, `cmd_detail`, `cmd_completeness_apply`, then `cmd_jira` in that order and returns 0.
- `test_direct_jira_rejects_dirty_tree_at_start` — stub `working_tree_dirty` true; assert the verb stops rc 2 before `cmd_create`, message names `direct-jira` not `--commit`.
- `test_direct_jira_completeness_apply_uses_jobs_gt_1` — assert the completeness-apply namespace has `jobs > 1` and `yes is True` (never bare `-y`, which would silently skip the conceptual walk).
- `test_direct_jira_commits_before_completeness_apply` — assert `commit_all` is called after `cmd_detail` and before `cmd_completeness_apply` (so its worktree isolation has a clean HEAD).
- `test_direct_jira_reads_create_result_from_sink` — the stub `cmd_create` deposits a `CreateResult` into `args._create_result_sink`; assert the verb reads it and passes the derived plan name into the detail/jira namespaces (no disk round-trip).
- `test_direct_jira_threads_cross_cutting_flags` — set `backend`/`model`/`on_rate_limit`/`fallback_backend` on the input args; assert the namespaces passed to `cmd_detail` and `cmd_jira` carry the identical values.
- `test_direct_jira_stops_on_create_failure` — stub `cmd_create` returns a non-zero rc; assert the verb returns it and never calls `cmd_detail`/`cmd_jira`.
- `test_direct_jira_stops_on_detail_failure` — stub `cmd_detail` returns non-zero; assert the verb returns it and never calls `cmd_jira`.
- `test_direct_jira_stops_on_split_proposal` — `CreateResult` has `split_proposal` set and `plan_path is None`; assert the verb does not call `cmd_detail`/`cmd_jira` and returns the agreed no-hard-failure code.
- `test_direct_jira_stops_on_oversize_gate` — the size gate flags the create result over-large; assert the verb prints the gate reason and stops before `cmd_detail`.
- `test_direct_jira_builds_detail_namespace_fields` — assert the detail namespace carries the attributes `cmd_detail` reads directly (`name`, `step`, `force`, `dry_run`) so no `AttributeError` escapes.
- `test_direct_jira_builds_jira_namespace_fields` — assert the jira namespace carries `name`, `lint`, `output`, `epic`, `max_hours`, `format`, `dry_run`, `no_write`, `stdout`.
- `test_direct_jira_sets_detail_only` — assert the detail namespace passed to `cmd_detail` has `detail_only is True` (so the completeness tail converges while the per-step loop is skipped), regardless of the input args' `iterate` value.
- `test_direct_jira_stops_on_iteration_incomplete` — stub `cmd_create` returns 0 but deposits a `CreateResult` with `iteration_stage_failure` set; assert the verb stops before `cmd_detail`/`cmd_jira` and does not treat rc-0 as convergence.

## Acceptance criteria

- `plan_tool/cli/direct_cmd.py` defines `cmd_direct_jira(args)` returning `int`.
- With all handlers stubbed to return 0, `cmd_direct_jira` calls `cmd_create`, `cmd_detail`, `cmd_completeness_apply`, `cmd_jira` in that order and returns 0.
- The verb rejects a dirty working tree at chain start (rc 2, message names `direct-jira` not `--commit`) before `cmd_create`.
- The completeness-apply namespace has `jobs > 1` and `yes is True`; `commit_all` is called after `cmd_detail` and before `cmd_completeness_apply`.
- The verb sets a `list` on the create args' `_create_result_sink` before calling `cmd_create` and reads the `CreateResult` back from it after.
- A non-zero rc from any stage is returned unchanged and stops the chain before the next stage runs.
- A `CreateResult` with `plan_path is None` (split short-circuit) stops the chain without proceeding to `detail`.
- A `CreateResult` with `iteration_stage_failure` set stops the chain before `detail` even though `cmd_create` returned 0 (the verb reads the field, not the rc).
- The detail namespace passed to `cmd_detail` carries `detail_only is True` (completeness tail converges, per-step loop skipped), regardless of the input args' `iterate` value.
- An over-large create result flagged by step 3's size-gate helper stops the chain before `detail` with the gate's reason printed.
- The `backend`, `model`, `on_rate_limit`, and `fallback_backend` values on the input args appear unchanged on the detail and jira namespaces.
- All new tests in `tests/cli/test_direct_cmd.py` pass, and no backend binary is spawned (enforced by the `tests/cli/conftest.py` autouse gate).

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — the `Namespace` object and `vars(namespace)`, used to copy cross-cutting flags into each stage's args namespace.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — the `--model`/backend flags whose values thread unchanged through each chained stage's invoker seam.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — stubbing the module-level `cmd_create`/`cmd_detail`/`cmd_jira` so the chain tests never run a real stage or spawn a backend.

## Deferred

- **The `direct-run` verb** — the sibling `create → detail → run --commit → reconcile-code` chain is step 5, in the same file.
- **Parser registration and CLI-reference docs** — wiring `direct-jira`/`direct-run` into `plan_tool/cli/parser.py` and `plan_tool/cli/app.py`, and generating `docs/cli/direct-jira.md`, is step 6. Until then the verb is reachable only in tests via a hand-built namespace.
- **Size-gate threshold tuning** — the fixed `MAX_CHAINABLE_STEPS` value ships as-is; making it configurable is deferred by the plan's `## Out of scope`.
- **Field-completeness guard for the hand-built namespace** — no automated check asserts the assembled args namespace stays complete against each handler's expected flags; deferred per the plan's `## Deferred`.
- **Mid-chain resume/checkpoint** — a stage failure surfaces the standard non-zero exit with the create (and possibly detail) artifacts left on disk; chain-level rollback/resume is out of scope.
