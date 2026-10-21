> **Auto-archived**: this plan was swept on 2026-07-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Direct Pipeline Commands
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Write the direct-pipeline design and flow note
  creates:
  - docs/DIRECT_PIPELINE_FLOW.md
  complexity: low
  change_type: non-code
  detail: docs/implementation-plans/plan-details/direct-pipeline-commands/01-write-direct-pipeline-design-flow-note.md
  status: done
- id: 2
  title: Let cmd_create hand its create result back to in-process callers via a namespace
    sink
  files:
  - plan_tool/cli/authoring.py
  - tests/cli/test_authoring_cmds.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/direct-pipeline-commands/02-let-cmd-create-hand-its-create-result.md
  status: done
- id: 3
  title: Add the size-gate helper that flags an over-large create result
  creates:
  - plan_tool/cli/direct_cmd.py
  - tests/cli/test_direct_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/direct-pipeline-commands/03-size-gate-helper-that-flags-over-large.md
  status: done
- id: 4
  title: Add the direct-jira verb that chains create, detail, and jira in one process
  files:
  - plan_tool/cli/direct_cmd.py
  - tests/cli/test_direct_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/direct-pipeline-commands/04-direct-jira-verb-that-chains-create.md
  status: done
- id: 5
  title: Add the direct-run verb that chains create, detail, run --commit, and the
    reconcile-code loop
  files:
  - plan_tool/cli/direct_cmd.py
  - tests/cli/test_direct_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/direct-pipeline-commands/05-direct-run-verb-that-chains-create.md
  status: done
- id: 6
  title: Register the two verbs and regenerate the CLI reference
  files:
  - plan_tool/cli/parser.py
  - plan_tool/cli/app.py
  - plan_tool/cli/direct_cmd.py
  - docs/cli/README.md
  - tests/cli/test_direct_cmd.py
  - tests/cli/test_cli_reference.py
  creates:
  - docs/cli/direct-jira.md
  - docs/cli/direct-run.md
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/direct-pipeline-commands/06-register-two-verbs-regenerate-cli.md
  status: done
- id: 7
  title: 'Update README, CAPABILITIES, USE_CASES, state the name disambiguation, and
    remove BACKLOG #118'
  files:
  - README.md
  - CAPABILITIES.md
  - USE_CASES.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/direct-pipeline-commands/07-update-readme-capabilities-use-cases.md
  status: done
---
# Direct Pipeline Commands

## Overview

This plan adds two direct pipeline verbs — `direct-jira` and `direct-run` — that chain the existing pipeline stages in one process instead of forcing the operator to run `create`, `detail`, and then `jira` or `run` as separate commands. `direct-jira` runs create → detail → **completeness-apply** → jira; `direct-run` runs create → detail → **completeness-apply** → run `--all --commit` → a single reconcile-code pass per code step. The "slim, don't weaken" speed model drops the standalone **`completeness-audit`** invocation — `detail`'s built-in completeness tail *is* that audit (it saves the conceptual gap map to the report sidecar) — but **keeps a `completeness-apply` stage**, because under the #85 read-only-audit split `detail`'s tail applies only *deterministic well-formedness* findings; the conceptual `plan-correctness`/`plan-completeness` gaps are persisted **unapplied**, and `completeness-apply` is their sole mutator. So the chain reuses detail's saved audit as `completeness-apply`'s input and applies the conceptual gaps **in a single replay pass** (no re-audit — a gap whose fix reveals a *new* gap is not re-caught, the same single-pass honesty the reconcile stage carries) — "don't weaken" holds relative to the manual workflow (which also applies once), at one fewer audit round-trip. `detail` runs in **`--detail-only`** mode (completeness tail audits + applies deterministic findings; the costlier per-step detail-quality loop skipped for leanness — see `## Architecture`). `direct-run`'s reconcile pass is one sweep per code step, not an iterate-to-convergence loop (`cmd_reconcile_code` has no drift-remaining signal today — BACKLOG #135), so the operator still owns the post-run reconcile convergence and `/code-review` tail. To hand each stage's result to the next without re-**discovering** the create result on disk, `cmd_create` learns to deposit its `CreateResult` to an in-process caller through a namespace sink, and a size-gate helper flags a create result too large to chain safely; each stage handler still re-resolves the plan by name and re-parses it from disk (the handlers own that read — reusing them keeps it). The verbs reuse the existing handlers and the invoker seam, so backend/model/rate-limit flags and exit-code conventions carry through each chained stage unchanged.

## Problem statement

The full pipeline stages (`create → detail → audit ── jira` and `── run`) exist only as
separate CLI invocations. To take a rough idea to Jira-sized stories or to an executed
plan, the operator must run `create`, then `detail`, then `jira` or `run --commit`, as
several discrete commands — each re-passing the same cross-cutting flags (`--backend`,
`--model`, `--on-rate-limit`), and each a manual hand-off point where a wrong path, stale
plan name, or forgotten flag breaks the chain. There is no single verb that expresses the
common end-to-end intent ("turn this idea into stories" / "turn this idea into shipped
code"), so the pipeline's own composition lives in the operator's memory and shell history
rather than in the tool. For a change small enough to be 1–2 tickets, running the full
six-command named workflow is disproportionate overhead, so it gets skipped or short-cut
for exactly the small work where the gated stages are cheapest to keep.

The symptom is friction and drift: multi-command sequences are easy to get out of order or
to run with mismatched flags, the create result has to be re-**discovered** on disk before
`detail`/`jira`/`run` can act on it, and there is no guard against chaining a create result
too large to size safely into the downstream stages. `BACKLOG.md #118` tracks the request
for these direct pipeline verbs. This work adds `direct-jira` and `direct-run` so the
chained intent is a first-class command that reuses the existing handlers and the invoker
seam, depositing the create result to the next stage in-process (removing the
re-*discovery*, not the per-stage plan disk read the handlers own) with the cross-cutting
flags and exit-code conventions preserved. Speed over the full workflow comes from *one process +
leaner authoring + one fewer audit round-trip* — the standalone `completeness-audit` is
folded into `detail`'s built-in tail, which then feeds the retained `completeness-apply`
stage its saved gap map — not from weakening any stage that runs.

## Architecture

The two verbs live in a new thin CLI leaf, `plan_tool/cli/direct_cmd.py`, that sits beside the existing intent-group handlers (`authoring.py`, `run_cmd.py`, `jira_cmd.py`) and holds no business logic of its own: it composes the existing orchestrators rather than reimplementing them. `direct-jira` chains `create → detail → completeness-apply → jira`; `direct-run` chains `create → detail → completeness-apply → run --all --commit → a single reconcile-code pass per code step`. Each verb builds the per-stage args namespace and calls the same handler the standalone subcommand calls, so the pipeline's composition moves out of the operator's shell history and into the tool while the stage behavior stays single-sourced.

**Drop the standalone `completeness-audit`, keep `completeness-apply` — the corrected speed model.** The full named workflows run a standalone `completeness-audit` **then** `completeness-apply` between `detail` and `jira`/`run`. The direct verbs drop the standalone **audit** — `detail`'s built-in completeness tail already *is* a `completeness-audit --iterate` (it saves the conceptual gap map to the report sidecar) — but they **keep `completeness-apply`**, because under the #85 read-only-audit split (`completeness_cmd.py:153-158`) `detail`'s tail applies **only deterministic well-formedness** findings and persists the conceptual `plan-correctness`/`plan-completeness` gaps **unapplied**; `completeness-apply` is their sole mutator. An earlier revision of this plan wrongly assumed `detail`'s tail (in `--detail-only`) converged conceptual completeness — it does not, so folding the audit into detail *without* a following apply would silently weaken conceptual coverage. The corrected chain therefore calls `completeness-apply` after `detail`, reusing detail's **saved** audit as input (`--jobs N` reuses the newest saved report; **no re-audit**), so conceptual gaps are applied in-chain in a **single replay pass** (not iterate-to-convergence — a fix that reveals a new gap is not re-caught, mirroring the reconcile stage). This preserves the real speed lever — one fewer *audit* round-trip and one process — while making "slim, **don't weaken**" honestly true. The verbs still **never** run `/code-review` (a Claude Code session activity, not a plan-tool surface) — that convergence tail stays the operator's.

**`completeness-apply` runs `--jobs N -y` on a clean tree — so both verbs commit authoring first.** `completeness-apply`'s conceptual walk is interactive at `--jobs 1`, and `-y` on a non-interactive stdin **skips the walk entirely** (a real gotcha); the only unattended path is `--jobs N` (N≥2), which applies each gap in an **isolated worktree off HEAD** and therefore requires a **clean working tree**. So each verb commits the create/detail authoring artifacts (via `commit_all`) **before** calling `completeness-apply`, then — **only if the apply actually changed files** (`working_tree_dirty`) — commits the applied conceptual gaps after it. That guard matters: on the happy path for small "1–2 ticket" work, detail's audit finds **no** conceptual gaps, `completeness-apply` changes nothing, and an unconditional `commit_all` would fail (`git commit` returns non-zero with nothing staged) and wrongly halt the chain. A clean tree after the apply means "no gaps to fix," not an error. This means **`direct-jira` now also commits** the plan it authors (it previously never did — see the Known-limits note on discarding it); both verbs consequently enforce the clean-tree precondition at chain start (see below), not just `direct-run`.

**`detail` is invoked in `--detail-only` mode — the tail audits (and saves the gap map), the per-step loop is skipped.** The namespaces are built by *copying* the create-flavored args (`argparse.Namespace(**vars(args))`), and `create` defaults `--iterate` **ON**, so a passive copy would run `detail`'s costly per-step detail-quality convergence loop. `--detail-only` (`cmd_detail`, `authoring.py:~1143`) pins the completeness tail's `--iterate` ON while keeping the per-step detail-quality loop **off** (`detail_budget.enabled = False`). What the pinned tail's `--iterate` buys is the **deterministic well-formedness** convergence plus a **saved conceptual gap map** in the report sidecar — *not* conceptual application (that's the #85 split). That saved map is exactly what the following `completeness-apply` stage consumes. So the verbs build the detail namespace with `detail_only = True` (letting `cmd_detail` pin `iterate` internally); this is the one stage the verbs deliberately re-mode rather than copy. The run stage and reconcile pass keep their own defaults.

**Both verbs guard a clean tree up front and commit mid-chain.** Because `completeness-apply --jobs N` needs a clean tree (worktree isolation off HEAD), *both* verbs commit the create/detail authoring artifacts (via `commit_all`, `git add -A`) before it — and `direct-run` additionally relies on a clean tree for `run --commit`. But `git add -A` would fold *any pre-existing, unrelated* working-tree change the operator had at chain start into that `plan(<slug>): author plan` commit — whereas the standalone stages these verbs compose (`cmd_detail`, `cmd_run --commit`, `completeness-apply`) *reject* a dirty tree up front instead. So **both** verbs apply a **clean-tree precondition at chain start** (before `create`): a dirty tree stops the verb with a verb-specific message (e.g. "`direct-run` requires a clean working tree…" — **not** the standalone "`--commit requires a clean working tree`" wording, since the operator never passed `--commit`), and the mid-chain commits then only ever capture the artifacts the chain itself authored/applied.

**An unconverged create does not chain silently forward.** `cmd_create` returns `0` even on its `iteration_incomplete` path — a plan whose post-write convergence loop aborted (`result.iteration_stage_failure is not None`). Chaining forward on rc-0 alone would carry an unconverged plan into detail/jira/run, eliding the decision point the standalone `create` surfaces via its FAILURE banner. So the verbs read `CreateResult.iteration_stage_failure` from the sink and, when it is set, **surface it and stop** rather than proceeding — the sink carries the field for exactly this (step 2 deposits it; steps 4–5 act on it). The stop is unconditional (no interactive continue-prompt): an unconverged create is a halt the operator resolves by re-running, matching the FAILURE banner the standalone flow shows.

The load-bearing new seam is the **in-process result hand-off**. Today each stage re-discovers the create result on disk before acting; chaining in one process needs `create`'s result threaded directly to the next stage. `cmd_create` (in `authoring.py`) learns to write its create result back to an in-process caller through a **namespace sink** — an optional attribute on the args `Namespace` that, when present, receives the result object; when absent, `cmd_create` behaves exactly as before. This keeps the CLI-entry path unchanged for standalone `create` and gives `direct_cmd.py` the create result without re-**discovering** it on disk (parsing the manifest, re-reading the plan file) and without a new return-value contract on the handler. It does **not** eliminate the per-stage plan read: the verbs derive a plan *name* from `CreateResult.plan_path.stem` and hand it to `cmd_detail`/`cmd_jira`/`cmd_run`/`cmd_reconcile_code`, each of which re-resolves via `resolve_plan_for_context` and re-parses the plan from disk. Reusing the handlers (required by `## Out of scope`) means each stage owns its own disk read; the sink removes the re-*discovery* round-trip, not that read.

A **size-gate helper** in `direct_cmd.py` flags a create result too large to chain safely into the downstream stages, converting an otherwise silent oversized-plan hand-off into an explicit stop. The gate is a deterministic check on the create result, spends no Claude, and is the one piece of new judgment the verbs add on top of the reused handlers. It is deliberately a **create-time pre-filter** — it measures step count on the `CreateResult` *before* `detail`'s tail and `completeness-apply` run, to fail fast and steer an obviously-too-big concept to the full pipeline before any expensive stage is spent. **Known limit:** `detail`'s tail and `completeness-apply` can *grow* the plan (escalate-to-split 1→2, add-step) to convergence, so a plan that starts just under the threshold can cross it mid-chain and reach `jira`/`run` unre-gated. Re-measuring after the growth stages is deferred (see `## Deferred`); the pre-filter catches the common oversized-seed case, not late growth.

The cross-cutting flags (`--backend`, `--model`, `--on-rate-limit`, rate-limit policy) and the exit-code convention (non-zero only on failure-to-complete) carry through each chained stage because the verbs thread the same args namespace into the same handlers and the same invoker seam every stage already uses — no stage sees a different backend or classifies findings differently when driven from a direct verb than when run standalone.

**Dependency placement.** `direct_cmd.py` imports the existing command handlers and orchestrators, so it sits *above* them in the CLI layer alongside the other intent-group modules; it introduces no new orchestrator and no import into `plan_tool.cli` from a leaf. The namespace-sink change to `cmd_create` is additive and keeps `authoring.py` thin.

**Trade-offs.** Reusing the handlers (rather than calling orchestrators directly) keeps flag parsing, gates, and exit codes identical to the standalone verbs at the cost of building each stage's args namespace by hand; the alternative — a shared orchestrator-level chain — would duplicate the CLI wiring the handlers already own. The namespace sink is chosen over changing `cmd_create`'s return type because it leaves the standalone CLI-entry contract byte-for-byte unchanged and is invisible to every caller that does not set it.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — Official Python reference for sub-parsers (add_subparsers) and the Namespace object, which the new direct-* verbs use to build and thread each stage's args namespace into the existing handlers.
- [subprocess — Subprocess management](https://docs.python.org/3/library/subprocess.html) — Official Python reference for subprocess.run/Popen, the mechanism behind the invoker seam that every stage handler uses to shell out to the Claude/codex/cursor backends.
- [git-worktree Documentation](https://git-scm.com/docs/git-worktree) — Canonical git reference for worktree add/remove/prune, relevant because the chained run --commit and reconcile-code loop and completeness parallel-apply rely on isolated worktrees and clean-tree gating.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — Official Claude Code CLI flag reference (headless/print mode, --model, backends), consulted when propagating --backend/--model/--on-rate-limit cross-cutting flags through each chained stage's subprocess invocation.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — pytest guide for stubbing module-level functions, needed to write the direct_cmd unit/integration tests that override invoker seams so tests never spawn a real backend.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **New orchestrator logic or altered stage behavior.** The verbs compose the existing `create`/`detail`/`jira`/`run`/reconcile-code handlers unchanged; any change to how a stage gates, audits, or classifies findings belongs to that stage's own plan, not here.
- **Running a standalone `completeness-audit`, or `/code-review`.** The direct verbs drop the standalone completeness-*audit* (detail's tail is that audit) but **do** run `completeness-apply` in-chain (the conceptual-gap mutator). They never run `/code-review` (a Claude Code session activity); the `Next steps:` output stays plan-tool-only, and the operator owns the post-run reconcile/review tail. A separate standalone audit invocation or a chain-level reconcile-to-convergence loop is out of scope.
- **A subprocess-based chain.** The verbs thread each stage in-process via the namespace sink; re-invoking the CLI (or `subprocess`) per stage is explicitly not the design, so shelling out to a fresh `plan-tool` per stage is out of scope.
- **A chain-level `--iterate` flag.** This plan adds no chain-level iterate flag. Each stage runs at its own standalone default, with two deliberate exceptions the verbs set explicitly: `detail` is invoked in `--detail-only` mode (completeness tail converges, per-step detail-quality loop skipped — see `## Architecture`), and the reconcile pass is one sweep per code step, not iterate-to-no-drift (deferred to BACKLOG #135). A general chain-level convergence loop over all stages is out of scope.
- **A single-verb superset that also runs `annotate`, `reconcile-plan`, or `verify`.** Only the `create → detail → completeness-apply → jira` and `create → detail → completeness-apply → run --all --commit → reconcile-code` chains are in scope; other pipeline compositions are left for follow-up.
- **Resuming or checkpointing a partially-completed chain.** A stage failure surfaces the standard non-zero exit; mid-chain resume/restart machinery is not added here.
- **Tuning the size-gate threshold.** The gate flags an over-large create result with a deterministic check; making its threshold configurable or model-driven is deferred.

## Risks

- **Namespace-sink hand-off diverges from disk state.** Threading `create`'s result in-process means the downstream stage acts on the in-memory object rather than re-reading the plan from disk; if `cmd_create` mutates the plan on disk after populating the sink, the chained stage could act on a stale result. Medium. Mitigation: the sink receives the same result object `cmd_create` finalizes, and the verbs perform no independent disk read between stages. Residual gap: any future `create` post-write step must keep the sink object and disk in sync.
- **Size-gate threshold is a fixed heuristic.** The deterministic over-large check uses a single non-configurable threshold, so it can false-positive (block a chain that would have sized fine) or false-negative (let an oversized plan through). Low-to-medium. Mitigation: the gate is an explicit stop with a clear message, so a false positive is recoverable by running the stages standalone. Residual gap: threshold tuning is explicitly deferred (see `## Out of scope`).
- **Hand-built per-stage args namespace drifts from the standalone parser.** The verbs assemble each stage's args namespace by hand rather than through argparse, so a new required flag or changed default on a downstream handler can silently break the chained path while the standalone path keeps working. Medium. Mitigation: the verbs call the same handlers, and tests exercise each chained stage; the CLI-reference drift guard catches added flags. Residual gap: no automated check that the hand-built namespace stays field-complete against the handler's expectations.
- **Mid-chain stage failure leaves partial state.** A failure in `detail`, `completeness-apply`, `jira`, or `run` surfaces the standard non-zero exit but leaves the already-committed authoring (and possibly a completeness-apply commit) on disk with no chain-level rollback. Low. Mitigation: partial artifacts are the same ones the standalone stages produce and are re-runnable by hand; resume/checkpoint machinery is explicitly out of scope.
- **An unconverged create chains forward silently.** `cmd_create` returns `0` on its `iteration_incomplete` path, so a rc-only gate would carry a plan whose convergence loop aborted into detail/jira/run. Medium. Mitigation: the verbs read `CreateResult.iteration_stage_failure` from the sink and **stop unconditionally** (no continue-prompt) instead of proceeding, surfacing the same decision point standalone `create` shows via its FAILURE banner.
- **`direct-run`'s per-step reconcile loop leaves a partial, unlabeled end state.** The reconcile pass iterates code steps landing edits **inline and uncommitted**; a mid-loop failure at step *k* leaves steps `1..k-1` reconciled (uncommitted) and `k..N` not, with no recorded marker of which completed. Medium. Mitigation: on a non-zero reconcile rc the verb stops and names the failed step id, and the reconcile edits are the same inline, re-runnable ones the standalone `reconcile-code --step N` produces — the operator resumes by re-running from the named step. A durable per-step reconcile marker is out of scope (ties to BACKLOG #135's drift-signal gap).
- **Mid-chain `commit_all` captures unrelated changes.** Both verbs commit mid-chain (`git add -A`, before `completeness-apply` and — for `direct-run` — before `run`), so a pre-existing dirty tree at chain start would fold the operator's unrelated edits into an authoring commit. Medium. Mitigation: **both** verbs apply a clean-tree precondition at chain start (mirroring standalone `cmd_detail`/`cmd_run --commit`/`completeness-apply`), so every mid-chain commit only captures the artifacts the chain itself authored or applied.
- **`completeness-apply` non-interactive footgun.** `completeness-apply -y` on a non-interactive stdin **silently skips** the conceptual walk (applies nothing); only `--jobs N` (N≥2) applies unattended, and it needs a clean tree. Medium. Mitigation: the verbs invoke `completeness-apply` with `--jobs N -y` on the freshly-committed clean tree, never bare `-y`; a test asserts the jobs value is >1 so a regression to bare `-y` (which would silently drop conceptual convergence) fails.
- **Cross-cutting flags silently misapplied to a stage.** `--backend`/`--model`/`--on-rate-limit` are threaded into every chained stage; a wiring error could apply a flag to a stage that ignores or misinterprets it. Low. Mitigation: the verbs thread the same namespace into the same handlers and invoker seam every stage already uses, so a stage sees the flags identically to standalone; tests assert flag propagation.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `docs/DIRECT_PIPELINE_FLOW.md` exists and documents the `create → detail → completeness-apply → jira` and `create → detail → completeness-apply → run --all --commit → reconcile-code` chains, why the standalone `completeness-audit` is dropped but `completeness-apply` is kept (the #85 split), and the namespace-sink hand-off (step 1).
- `plan-tool direct-jira --from-existing <seed>` exits 0 and produces a Jira-story export, having chained `create`, `detail`, `completeness-apply`, and `jira` in one process — depositing the create result in-process (no re-discovery on disk) while each stage still re-resolves the plan by name (`plan_tool/cli/direct_cmd.py`).
- `plan-tool direct-run --from-existing <seed>` exits 0 and drives `create`, `detail`, `completeness-apply`, `run --all --commit`, and a single reconcile-code pass per **code** step in one process; it runs no *standalone* completeness-audit (detail's tail is the audit) and never emits `/code-review`, and its `Next steps:` output is plan-tool-only (no slash command) (`plan_tool/cli/direct_cmd.py`).
- **Both** verbs refuse to start on a dirty working tree with a message that names the verb (not `--commit`, which the operator never passed), so their mid-chain commits only capture the artifacts the chain authored/applied (asserted in `tests/cli/test_direct_cmd.py`).
- Both verbs build the detail namespace with `detail_only = True`, so `cmd_detail` pins the completeness tail's `--iterate` ON — converging deterministic well-formedness and **saving the conceptual gap map** — while skipping the per-step detail-quality loop; conceptual gaps are *not* applied here (asserted in `tests/cli/test_direct_cmd.py`).
- Both verbs commit the authoring artifacts, then invoke `completeness-apply` with `--jobs N` (N>1) and `-y` on the resulting clean tree — never bare `-y` — so the conceptual `plan-correctness`/`plan-completeness` gaps from detail's saved audit are applied in a single replay pass (no re-audit), then commit the applied edits **only if the apply changed files** (a clean tree = no gaps, not an error) (asserted in `tests/cli/test_direct_cmd.py`, including the no-gaps happy path where the post-apply commit is skipped).
- `direct-run`'s reconcile loop calls `cmd_reconcile_code` only for **code** steps, skipping non-code (docs/test) steps by `change_type`, and on a non-zero reconcile rc stops and names the failed step id (asserted in `tests/cli/test_direct_cmd.py`).
- The run namespace does **not** carry `iterate = True` (it is reset, like `detail_only` on the detail namespace), so `cmd_run` emits no spurious "`--iterate only applies to … --reconcile`" warning for a flag the operator never passed (asserted in `tests/cli/test_direct_cmd.py`).
- On `create`'s multi-plan split short-circuit (`CreateResult.plan_path is None`, `split_proposal` set), both verbs stop cleanly at exit 0 with a message naming the split (no attempt to detail/apply/jira/run a non-existent single plan) (asserted in `tests/cli/test_direct_cmd.py`).
- When `cmd_create` returns with `iteration_stage_failure` set, both verbs surface it and stop **unconditionally** (no continue-prompt) instead of chaining forward into detail/jira/run (asserted in `tests/cli/test_direct_cmd.py`).
- `cmd_create` writes its create result to a caller-supplied namespace-sink attribute when present, and behaves byte-for-byte as before when the attribute is absent (asserted in `tests/cli/test_authoring_cmds.py` / `tests/test_create.py`).
- The size-gate helper in `direct_cmd.py` returns a non-zero / stop verdict for a create result exceeding the threshold and a pass verdict otherwise, spending no Claude invocation (asserted in `tests/cli/test_direct_cmd.py`).
- Passing `--backend`, `--model`, or `--on-rate-limit` to either verb threads the identical flag values into every chained stage's args namespace and invoker seam (asserted by flag-propagation tests in `tests/cli/test_direct_cmd.py`).
- A mid-chain stage failure surfaces the standard non-zero exit code from that stage without a chain-level exception (asserted in `tests/cli/test_direct_cmd.py`).
- `plan-tool direct-jira --help` and `plan-tool direct-run --help` exit 0, and `docs/cli/direct-jira.md` and `docs/cli/direct-run.md` exist with `tests/cli/test_cli_reference.py` passing (step 6).

## Deferred

- **Size-gate threshold tuning** — the gate ships with a single fixed, non-configurable threshold; making it configurable or model-driven is postponed until real usage shows the fixed value mis-fires (see the size-gate risk).
- **Field-completeness guard for the hand-built per-stage namespace** — no automated check asserts the hand-assembled args namespace stays complete against each handler's expected flags; postponed until a downstream handler gains a required flag that would break the chained path silently.
- **Re-gating plan size after `detail`/`completeness-apply` growth** — the size gate is a create-time pre-filter and does not re-measure after detail's tail or `completeness-apply` grow the plan (escalate-to-split, add-step), so a plan that crosses the threshold mid-chain reaches `jira`/`run` unre-gated; a post-growth re-check is postponed until usage shows late growth actually mis-fires.

### Known limits — decide/handle at implementation

These integration edges surfaced in review; they don't block the design but the implementer must handle each explicitly (some are only reproducible once `direct_cmd.py` exists, so they cannot be caught by the stubbed unit tests):

- **`direct-jira` durably commits the plan it authors.** Because `completeness-apply --jobs N` needs a clean tree, `direct-jira` now commits the create/detail plan even though the operator's intent was a Jira export, not landing a plan. Decide the disposition: keep the commit (the plan is a real artifact worth having) and say so in the help/output, or offer a `--no-keep-plan` that resets the authoring commit after export. At minimum, the output must tell the operator a plan was committed and how to discard it.
- **`detail`'s completeness tail is fail-soft.** `_run_completeness_tail` catches its own exception and `cmd_detail` still returns rc 0, so a failed tail leaves **no** saved `-completeness.json`; the next `completeness-apply` stage then errors rc 2 ("no saved completeness audit… run `completeness-audit` first"), halting the chain with a message pointing at a command the operator never needed. The verb should detect the missing saved audit after detail and surface the real cause (detail's tail failed), not the misleading downstream error.
- **`direct-run`'s reconcile stage auto-applies unattended.** `cmd_reconcile_code` auto-accepts every finding under non-TTY/`--yes`, so the chain lands reconcile code edits inline with no per-finding review — unlike the standalone TTY walk. This is the same non-interactive posture as `completeness-apply`; document it so an operator expecting recommend-only reconciliation isn't surprised.
- **`direct-run`'s reconcile drops plan-rooted `[REDIRECT]`s.** When `cmd_reconcile_code` finds drift whose root cause is the plan, it emits a `[REDIRECT]` to `detail --reconcile` instead of landing a code edit; in the unattended chain that redirect is dropped and no stage acts on it. Advisory only, but the merged `Next steps:` should carry the redirect so the operator knows a plan-rooted drift remains.
- **Sink/disk sync guard for future `create` post-write steps** — if `cmd_create` later mutates the plan on disk after populating the namespace sink, the chained stage could act on a stale result; a guard is postponed until such a post-write step exists.
- **A single unified `Next steps:` block across all stages** — the load-bearing guarantee is that the output is plan-tool-only (no `/code-review`); folding every stage's block into one merged list needs each handler (`cmd_create`/`cmd_run`/`cmd_jira`) to expose the `_next_steps_sink` collector that only the completeness tail fills today, so full unification is deferred. Until then the verbs may print more than one plan-tool-only block.
- **A durable per-step reconcile-completion marker** — the reconcile loop lands inline uncommitted edits with no record of which steps finished, so a mid-loop failure leaves a partial state the operator resumes by re-running from the named step; a persisted marker is deferred (ties to BACKLOG #135's drift-signal work).
