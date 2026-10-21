> **Replaced**: this file has been superseded by `docs/implementation-plans/2-direct-pipeline-commands.md`.
> Preserved here for history; do not edit.

## Overview

Adds two thin CLI verbs — `plan-tool direct-jira <slug>` and `plan-tool direct-run <slug>` — that chain the existing pipeline stages back-to-back in **one process** for **small changes** (expected 1–2 Jira stories / a handful of steps). `direct-jira` chains `create → detail (→ its built-in completeness tail) → jira`; `direct-run` chains `create → detail → run --commit → reconcile-code` to convergence, after which the operator proceeds to code review themselves. Both are thin orchestrators over the existing stage handlers (`cmd_create` / `cmd_detail` / `cmd_run` / `cmd_jira`) — **no new engine** — modeled on how `detail` already calls `_run_completeness_tail` in-process. A deterministic **size gate** detects when the concept is too big for a one-shot and steers the operator to the full pipeline (warn + require confirm). Source: **BACKLOG.md #118**.

## Problem statement

For a change small enough to be 1–2 tickets, running the six-subcommand named workflows (`create-detail-audit-jira` and `create-detail-audit-run-review-audit`) by hand is disproportionate overhead — so today those workflows get skipped or short-cut for small work, which erodes the gated-stage guarantees exactly where they'd be cheapest to keep. `direct-*` collapses the round-trips into one command so small changes reach **Jira** (the primary goal) or get **built** quickly, still through the real gated stages. It is named `direct`, not `fast`, because it is **faster, not fast** — the pipeline still runs full-rigor stages; speed comes from *fewer stages + leaner authoring*, never from weaker convergence.

**Name disambiguation (state once in the plan's docs):** this `direct` is a **CLI verb**; it is unrelated to the `Approach: direct` backlog tag in `BACKLOG.md` — different namespaces.

## Architecture

**Two thin verbs, no new engine.** A new command module `plan_tool/cli/direct_cmd.py` exposes `cmd_direct_jira` + `cmd_direct_run` + a `register` returning both, wired into `parser.py`'s `CANONICAL_COMMAND_ORDER` and `app.py`'s `COMMAND_MODULES` (both verbs added), and into `app.py`'s `_LOCKED_MUTATING_COMMANDS` (both are repo-mutating). Each verb builds each stage's `args` namespace and calls the existing handlers in sequence — the chaining precedent is `_run_completeness_tail` and the `split`/`merge` orchestrators, so most logic is orchestration, not new mechanics.

**Speed model — slim, don't weaken (decided).** Faster comes from two levers only: **(a)** fold the standalone `completeness-audit` stage — rely solely on `detail`'s built-in completeness tail (one fewer Claude round-trip); **(b)** leaner create/detail prompts/templates tuned for small changes (tighter step budget, fewer sections). What must **stay**: each remaining stage keeps its **full `--iterate` loop** (no capped-round / single-pass downgrade), and `direct-run` keeps the **post-run plan-canonical reconcile-code loop**. The design step must verify that folding the standalone completeness stage does **not** drop coverage that `detail`'s tail doesn't already provide for small plans.

**Single-log / single-commit / merged Next-steps (reuse the `_run_completeness_tail` posture).** The orchestrator emits **one run-log**, **suppresses the per-stage second commit/log**, and **merges every stage's "Next steps" into a single final block**. Lift the exact `_run_completeness_tail` suppression pattern rather than re-deriving it, so there is no double run-log / double-commit emission. On the first stage that fails (non-zero rc), **stop-and-report**: name the failed stage, leave already-written artifacts in place, and exit non-zero — mid-chain artifacts must be recoverable.

**Never `/code-review`.** `/code-review` is a session activity, not a plan-tool surface. `direct-run`'s tail runs `run --commit` then the plan-tool reconcile-code loop and stops; it must **never** emit or run `/code-review`. The merged `Next steps:` block stays **plan-tool-only** — it may remind the operator they still own the `/code-review` loop, but must not print the slash command. It must also never run the authoring-only `completeness-audit`/`completeness-apply` pair (those are plan-authoring audits, not implementation review).

**Size gate — warn + require confirm (decided).** After `create` (and keyed off the distilled seed), a shared helper both verbs call detects an over-large concept from **existing deterministic signals** — step count above a small cap (a handful), `granularity.assess_granularity` `granularity-split` findings, and `create`'s multi-plan `SplitProposal` detection (`cli/authoring.py:_emit_split_proposal`). On a trip, print a warning naming the full `create → detail → completeness → run|jira` pipeline and **stop unless a TTY confirm (`yes`) / `-y` / `--force` is given**; otherwise exit non-zero with the suggestion. Precision over recall — the gate must not false-trip on a legitimately small multi-file change (same posture as the advisory `granularity-split` detectors). This **replaces** any "does not refuse a larger plan" posture.

**Cross-cutting flags thread to every stage.** `--from-existing` / `--from`, `-y` / non-TTY, `--backend` / `--model` / `--on-rate-limit`, and `--commit` on `direct-run` (per the run `--commit` mandate) must propagate to every chained stage — a flag honored by the first stage but dropped by a later one is a bug the tests must catch.

**Spike before implementation.** The design step spikes/validates two things before the build steps: the `_run_completeness_tail`-style single-log/single-commit/merged-Next-steps suppression, and the size-gate signal wiring (`assess_granularity` + `SplitProposal`).

## Out of scope

- **A new engine or new stage mechanics** — `direct-*` only sequences existing handlers.
- **Weakening any stage's convergence** — no capped-round / single-pass downgrade; `--iterate` loops stay intact on every stage that runs.
- **Running `/code-review`** or the authoring-only `completeness-audit`/`completeness-apply` pair inside `direct-run`.
- **A large-plan one-shot** — the size gate deliberately steers big concepts to the full pipeline rather than silently one-shotting them.

## Risks

- **Double run-log / double-commit emission** if the single-log/single-commit suppression isn't reused faithfully — mitigate by lifting the exact `_run_completeness_tail` pattern.
- **Coverage regression** from folding the completeness stage — verify `detail`'s tail actually audits what the standalone pass did for small plans before relying on it.
- **Size-gate false-trip** on a legitimately small multi-file change — precision-over-recall, mirror the advisory `granularity-split` posture.
- **Mid-chain failure** leaving unrecoverable state — must stop, report the failed stage, and leave artifacts in place.
- **Flag drop** — `-y`/non-TTY, `--force`, and backend/rate-limit flags must reach every stage.
- **Accidental `/code-review` emission** in the `direct-run` tail — guard with the existing plan-tool-only Next-steps rule plus a test asserting no slash command appears in output.

## Testing

Unit-first, mirroring `plan_tool/cli/direct_cmd.py` → `tests/cli/test_direct_cmd.py` (and the size-gate helper wherever it lands). Integration tests drive `main(["direct-jira", ...])` / `main(["direct-run", ...])` with **stubbed invokers** (per the invoker-seam rule — never spawn a real backend). Cover: the chained sequence for each verb runs the right stages in order; **one** run-log and **one** commit per green step (no double emission); the merged `Next steps:` block is emitted once and contains **no** `/code-review` slash command; `direct-run` never invokes the authoring-only completeness audit/apply pair; a mid-chain stage failure stops the chain, names the failed stage, exits non-zero, and leaves prior artifacts; the size gate trips on an over-large `create` result (step count over the cap, a `granularity-split` finding, or a `SplitProposal`) and stops unless `-y`/`--force`/TTY-`yes`, and does **not** trip on a small multi-file change; every cross-cutting flag (`--from-existing`/`--from`, `-y`, `--backend`/`--model`/`--on-rate-limit`, `--commit`) reaches each stage.

## Acceptance criteria

- `plan-tool direct-jira <slug> --from-existing <seed>` runs `create → detail (+ its completeness tail) → jira` in one process and produces the Jira export, with one run-log, one merged `Next steps:` block, and no standalone `completeness-audit` stage.
- `plan-tool direct-run <slug> --from-existing <seed> --commit` runs `create → detail → run --commit → reconcile-code` to convergence, keeps the post-run plan-canonical reconcile loop, and **never** emits or runs `/code-review` or the authoring-only completeness audit/apply pair; the merged `Next steps:` block is plan-tool-only.
- Each remaining stage keeps its full `--iterate` convergence loop; speed comes only from folding the completeness stage and leaner small-change authoring, not from weaker convergence.
- The size gate detects an over-large concept after `create` (step count over a small cap, a `granularity-split` finding, or a `SplitProposal`), warns naming the full pipeline, and stops unless a TTY `yes` / `-y` / `--force` is given — otherwise exits non-zero; it does not false-trip on a legitimately small multi-file change.
- A mid-chain stage failure stops the chain, names the failed stage, exits non-zero, and leaves already-written artifacts recoverable.
- `--from-existing`/`--from`, `-y`/non-TTY, `--backend`/`--model`/`--on-rate-limit`, and `--commit` (on `direct-run`) propagate to every chained stage.
- The plan's docs state the `direct-*`-verb vs `Approach: direct`-tag disambiguation once.
- **Backlog reconciliation:** the plan's final docs/status step removes **#118** from `BACKLOG.md` when the work ships (or marks it plan-authored while build is pending), and updates `README` / `CAPABILITIES.md` / `USE_CASES.md` and the generated `docs/cli/` reference for the two new verbs.

## Deferred

- **A `fast`/aggressive mode** that downgrades convergence — explicitly rejected; `direct` stays full-rigor.
- **Auto-running `/code-review`** from `direct-run` — the operator owns the review loop; the tool only reminds.
- **Larger-than-small one-shots** — the size gate steers these to the full pipeline rather than growing `direct-*` to handle them.

## Backlog reconciliation (required)

This seed derives from **BACKLOG.md #118 — `direct-jira` / `direct-run`: slimmed one-shot pipeline for small changes**. The resulting plan must, in its final docs/status step and acceptance criteria, **remove the #118 entry from `BACKLOG.md`** when the work ships (or mark it plan-authored if build is still pending), per the backlog-reconciliation-forward rule.
