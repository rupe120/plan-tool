---
title: Escalate Structural Findings To Split
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add review.is_structural(rec) classification predicate seeded with detail-purity
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/01-review-structural-rec-classification.md
  status: current
- id: 2
  title: Add BLOCKED-STRUCTURAL verdict bucket to parse_apply_verdict/ApplyFindingResult
    and teach prompts/apply-finding.md to emit it
  files:
  - plan_tool/launcher.py
  - plan_tool/prompts/apply-finding.md
  - tests/test_launcher.py
  complexity: low
  change_type: feature
  gate:
  - grep -q 'BLOCKED-STRUCTURAL' plan_tool/prompts/apply-finding.md
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/02-blocked-structural-verdict-bucket-parse.md
- id: 3
  title: Add launcher.escalate_to_split bridge (safe-gate, propose, interactive-opt-in
    apply vs unattended recommend) reusing the Phase-B split engine via body-local
    imports
  files:
  - plan_tool/launcher.py
  - tests/test_launcher.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/03-launcher-escalate-split-bridge-safe.md
- id: 4
  title: Re-point detail.py Phase B split sequence at escalate_to_split (behavior-preserving
    — interactive `detail --split` still splits in one pass)
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/04-re-point-detail-py-phase-split-sequence.md
- id: 5
  title: Route structural (detail-purity) findings to escalate_to_split in the create
    convergence loop — recommend always, auto-apply only under the allow_split opt-in;
    fold the returned recommendation into emit_triage_summary by appending it to the
    open_deferred list
  files:
  - plan_tool/create.py
  - plan_tool/detail.py
  - tests/test_create.py
  - tests/test_detail.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/05-route-structural-detail-purity-findings.md
- id: 6
  title: Handle BLOCKED-STRUCTURAL in cli/review_actions.py apply-walk verdict branch
    (escalate when interactive+opt-in, else surface recommendation) instead of the
    bare revert+report
  files:
  - plan_tool/cli/review_actions.py
  - tests/cli/test_review_actions.py
  allowed_mentions:
  - plan_tool/cli/review_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/06-handle-blocked-structural-cli-review.md
---
# Escalate Structural Findings To Split

## Overview

This plan builds a bridge that routes an already-classified **structural finding** (one whose only correct fix is to split a step into two) to the **already-existing split engine**, under the same safety gates used by `detail --split` Phase B. Today such a finding is recognized but dead-ended: the audit tags it `detail-purity` and the convergence loop skips it, or `apply_finding` returns a bare `BLOCKED` and the caller reverts and reports. This is routing and plumbing — no new split capability — so the apply/convergence path can finish what it starts instead of dead-ending. Two paired invariants govern this bridge. **(1) Always validate the more-correct plan:** *recommendation* emission is the unconditional part — for a recognized structural finding with a concrete target, wherever the bridge runs it is always detected, proposed, and (on any non-applying path with a usable proposal) recorded as a split recommendation, never silently deferred or skipped. The no-recommendation paths are exactly the cases that fall outside "a recognized structural finding with a concrete target," and each emits `recommendation=None`: (a) `proposal-unusable` — `_propose_step_split` cannot be parsed into titles/rationale, so there is no usable proposal to record and the original finding stays deferred-and-reported by its caller; (b) `step-missing` — the captured `step_id` no longer resolves to a step in the re-parsed plan (step 3), so there is no concrete target to split; (c) the plan-wide `step_id is None` guard (steps 5/6) — a finding with no target step is not a recognized structural target, so escalation is skipped entirely. In every other case a usable proposal exists and a recommendation is recorded. *In-place auto-apply* of the split is the conditional part, gated to interactive + the `allow_split` opt-in; the opt-in gates only whether the bridge auto-applies, never whether it detects and proposes. Scope: this unconditional-recommendation guarantee holds for the bridge's callers — the create convergence loop, the `detail` convergence loop, and the `apply_finding`/`review_actions` apply walk. Step 4 re-points the standalone `detail --split` Phase B at the bridge behavior-preservingly; step 5 then extends detail's unattended path to emit a split recommendation, dropping the Phase-B `allow_split and isatty()` warning-only guard so an unattended or no-opt-in `detail` run surfaces a recommendation instead of only logging a mixed-step warning. **(2) Never mutate structure unattended:** a structural plan edit happens only interactively, under the opt-in, with operator confirm; every unattended bridge path recommends only.

## Problem statement

A finding whose only correct fix is "split this step into two" is recognized but dead-ended. The purity self-check tags a step that mixes refactor + feature as `detail-purity` (`review.py`), excludes it from `APPLY_ELIGIBLE_SOURCES`, and the convergence loop skips it with the triage reason *"the fix is to split it into type-pure steps, not an apply edit."* Separately, when Claude determines mid-apply that the only correct fix is a split, `apply_finding` returns a bare `BLOCKED` and the caller reverts and reports. The split engine that would resolve these (`create._propose_step_split` / `create._apply_step_split`, gated by `detail._split_is_safe`, confirmed by `detail._confirm_split`, with downstream migration via `detail._migrate_downstream_details_after_split`) already exists and is already wired to this exact trigger in `detail --split` Phase B — just nowhere else. The result is that `apply_finding`/convergence cannot finish what they start.

## Architecture

A new seam — `escalate_to_split(plan_path, *, step_id, repo_root, invoker, ...)` — given a structural finding and its target step, behaves as follows:

- **Always first:** re-parse the plan and run `_split_is_safe(plan, step_id)`. If a downstream step has already run/started, do **not** split — surface a recommendation to re-plan instead. (Mirrors `detail.py` Phase B; honors the non-PENDING-run-state gate.)
- **Propose:** recover the replacement `--into` titles **and** their per-step rationale from a *single* Claude proposal. `_propose_step_split` does one internal `invoker(prompt)` call, captures rationale into a discarded local dict, and returns only `Optional[list[Step]]` (titles; `Step` has no `rationale` field), so its raw response and rationale never leave the function. `escalate_to_split` must therefore recover both from one proposal by either (a) running the proposal itself with one `invoker` call and parsing the raw response via `_parse_steps_json(..., rationales_out=...)` (not calling `_propose_step_split`), so titles and rationale come from the same response, or (b) extending `_propose_step_split` to surface its `rationales_out`/raw alongside the returned titles. It must **never** make a second `invoker` call to fetch the rationale — a second proposal is non-deterministic and could describe a different split than the titles already chosen.
- **Proposal failed (`proposal-unusable`):** if `_propose_step_split` returns `None` (parse failure — no titles/rationale to carry), do **not** split and do **not** emit an empty/invalid recommendation. With no usable proposal there is nothing to record, so the bridge returns `recommendation=None` and the original structural finding stays deferred-and-reported by its caller — the operator sees the unresolved finding and must re-plan the step by hand.
- **Interactive + opt-in (TTY and the split opt-in flag set, and *not* `--yes`/`yes_to_all`):** run `_confirm_split` → `_apply_step_split` → `_migrate_downstream_details_after_split` — the exact Phase-B sequence. The convergence loop then finishes in one pass. The gate requires a genuine interactive confirm; `--yes`/`yes_to_all` is **not** an interactive auto-confirm here and must not satisfy this branch.
- **Apply failed (`split-failed`):** if `_apply_step_split` raises `CreateError` mid-apply (mirroring Phase B's `try/except CreateError` log-and-continue at `detail.py:2684`), catch it, mutate nothing, and surface a re-plan recommendation instead of letting the exception propagate. Without this catch an interactive `detail --split` or convergence pass would crash on a mid-apply failure rather than degrading to a recommendation.
- **Unattended (CI / `--yes` / `yes_to_all` / non-TTY):** never mutate structure. `--yes`/`yes_to_all` is an unattended path — auto-confirm must not bypass the never-mutate-unattended rule — so it recommends only. Emit a structured split *recommendation* (proposed titles + rationale) into the findings report so the operator runs `plan-tool split` later.

**What "structural finding" means — two triggers, both in scope:**

1. **Pre-classified — `detail-purity`.** The skip in the **`detail`** convergence loop becomes an escalation (the `detail` self-check is the only producer of `detail-purity`; create never emits it).
2. **Discovered mid-apply — `BLOCKED-STRUCTURAL`.** A new verdict bucket on `apply_finding`. When Claude, mid-apply, determines the only correct fix is a split (not a prose edit), it emits `## Verdict: BLOCKED-STRUCTURAL` rather than a bare `BLOCKED`. This catches structural needs the audit did not pre-classify.

A single predicate `review.is_structural(rec)` (seeded with `detail-purity`) and the new verdict together define the escalation set.

The split engine (`create._propose_step_split` / `create._apply_step_split`), the safety gate (`detail._split_is_safe`), the operator confirm (`detail._confirm_split`), and downstream-detail migration (`detail._migrate_downstream_details_after_split`) are all reused verbatim.

**Composes with the granularity advisor.** `step-granularity-advisor.md` *produces* `granularity-split` (formerly `detail-purity`) findings; this bridge *executes* them. This work stands alone on today's classification, but the two are designed to pair.

**Touch points (for step decomposition):**

- `review.py` — add `is_structural(rec)`; keep `detail-purity` out of `APPLY_ELIGIBLE_SOURCES` but route it to escalation instead of skip.
- `launcher.py` — extend `parse_apply_verdict` / `ApplyFindingResult` with `BLOCKED-STRUCTURAL`; add the `escalate_to_split` helper (reusing the lazy `create` imports already used in `detail.py` Phase B).
- the `apply-finding` prompt template — teach it to emit `BLOCKED-STRUCTURAL`.
- the `create`/`detail` convergence loop — call the bridge to escalate structural findings instead of dead-ending them. The live `detail-purity` skip is in the **`detail`** loop (whose self-check, `detail.py:_parse_purity_findings`, is the sole producer of `detail-purity`), so that's where the skip becomes an escalation. **`create`'s loop sources findings only from `review.collect_deterministic_findings`, which never emits `detail-purity`** — so the create-side `detail-purity` route is forward-safe-but-inert wiring; create's live structural trigger is the mid-apply `BLOCKED-STRUCTURAL` verdict. When `detail`'s Phase B routes multiple structural findings in a single convergence pass, process them highest-id-first (mirroring Phase B's reverse-sort over `mixed_steps`) so an earlier split's renumbering of ids 1..N can't invalidate a later finding's captured `step_id`. This ordering rule is Phase-B-specific; `create` instead re-collects-and-`continue`s after the first applied split (one apply per pass), so it never processes a second split against renumbered ids in one pass and needs no reverse-sort. In both loops, a trigger-2 `BLOCKED-STRUCTURAL` apply that returns `outcome="applied"` must **break out of the inner `for rec in open_apply` apply loop** before re-collecting and re-iterating the outer `while` (mirroring the existing `if drift_halted: break`), so no remaining queued `open_apply` rec is dispatched to `apply_finding` against the now-stale, renumbered `step_id`s the split produced. In `detail` specifically, that inner apply loop is itself nested inside the `for step in target_steps` loop (`detail.py:1662`), not a standalone outer `while` as in `create` — so after breaking out of the inner `for rec in open_apply`, the applied split must **also exit the enclosing `for step in target_steps` iteration**: re-parse the plan and re-collect `target_steps` from the renumbered plan, then `break` out of the `for step` loop, so no remaining `step` (a stale pre-split `Step`) is processed and no subsequent `apply_finding(step_id=step.id)` call (nor the `mixed_steps` ids captured at `detail.py:2107`) references a renumbered id. In `detail`, the per-step `emit_detail_findings_summary` calls (`detail.py:2253`, `2551`) run inside the `for step in target_steps` loop, but Phase B (`detail.py:2643`) and the bridge's `structural-split` `Recommendation`s are produced *after* that loop closes — so those recommendations cannot fold into the pre-Phase-B per-step calls. Step 5 must add a **post-Phase-B emission surface**: a final `emit_detail_findings_summary` (or report) call after Phase B that collects and surfaces the bridge's accumulated `structural-split` recommendations before `return results`, so an unattended `detail` run actually prints the split recommendation. In `create`, `emit_triage_summary` consumes the `open_deferred` finding list, so the bridge's returned `structural-split` `Recommendation` must reach the create findings report by being appended to that `open_deferred` list (not via a separate report path). But create's only live structural trigger is the mid-apply `BLOCKED-STRUCTURAL` verdict inspected inside the `for rec in open_apply` apply loop (`create.py:5477+`), which runs *after* the iteration's sole `emit_triage_summary(open_deferred, ...)` call (`create.py:5460`) has already fired, and the next iteration re-collects via `collect_deterministic_findings` (`create.py:5639`) which drops the synthetic `structural-split` rec — so appending alone would silently lose the recommendation on create's live path. Step 5 must therefore **surface the trigger-2 `Recommendation` after the apply loop** — a second `emit_triage_summary` over the appended recs (or an explicit print) before the iteration ends — rather than relying on the pre-loop emit that has already run. When `escalate_to_split` returns `recommendation=None` (`proposal-unusable`/`step-missing`), there is no synthetic rec to append, so create's trigger-2 branch must instead append the **original `BLOCKED-STRUCTURAL` finding** (which originated from `open_apply`, never `open_deferred`, and so was absent from the pre-loop emit) to that same post-apply-loop emit, so the unresolved structural finding is reported rather than silently dropped — honoring invariant (1)(a)'s "stays deferred-and-reported by its caller." A recommend-only trigger-2 `BLOCKED-STRUCTURAL` finding (one whose escalation produced a recommendation rather than an applied split on an unattended pass) must be **remembered/deduped** in a per-run seen-set keyed by the finding's identity (e.g. `step_id` + source/finding id), so that subsequent unattended iterations of **both** loops (`create.py:create_plan` and `detail.py:generate_detail`) skip re-dispatching it to `apply_finding`. Without this, each pass re-collects the same apply-eligible rec (`collect_deterministic_findings` in create), re-partitions it into `open_apply`, re-hits the `BLOCKED-STRUCTURAL` verdict, and spends another `_propose_step_split` Claude call to rebuild and re-emit a duplicate recommendation it only prints — repeating every iteration until the no-progress halt. The recommendation is surfaced once; thereafter the remembered finding is recognized as already-recommended and skipped, so no `apply_finding`/`escalate_to_split` re-propose runs for it again this run.
- `cli/review_actions.py` — handle `BLOCKED-STRUCTURAL` in the apply walk's verdict branch (currently reverts + reports at the `BLOCKED` / `NOT-APPLICABLE` arm). Its `auto_confirm` design must treat `yes_to_all` as an unattended (recommend-only) path, not an interactive auto-confirm — `yes_to_all` must not produce an auto-confirm that drives `escalate_to_split` to mutate structure.

## References

- [sys — System-specific parameters and functions (Python 3 docs)](https://docs.python.org/3/library/sys.html) — Defines sys.stdin/stdout/stderr and the isatty() stream check used to distinguish interactive (TTY) from unattended runs — the exact gate that decides apply-the-split vs. emit-a-recommendation.
- [io — Core tools for working with streams: IOBase.isatty (Python 3 docs)](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — Authoritative semantics of isatty() on stream objects, needed to implement and stub the TTY detection that drives the interactive-vs-CI branch.
- [argparse — Parser for command-line options, arguments and subcommands (Python 3 docs)](https://docs.python.org/3/library/argparse.html) — Reference for adding the split opt-in flag/--yes handling and subparser wiring, since the project's argparse parser is the source of truth for CLI flags and defaults.
- [How to mark test functions with attributes — pytest](https://docs.pytest.org/en/stable/how-to/mark.html) — Explains @pytest.mark usage and selecting marked tests, relevant to the new unit tests and the @pytest.mark.integration convergence-loop tests this plan adds.
- [Working with custom markers — pytest](https://docs.pytest.org/en/stable/example/markers.html) — Covers registering custom markers (e.g. integration) and running subsets, matching the repo's marker-based fast/integration test split the plan must keep green.
- [How to use fixtures — pytest](https://docs.pytest.org/en/stable/how-to/fixtures.html) — Reference for tmp_path and fixture overrides used to neutralize the Claude invoker seam so escalate_to_split tests never spawn the real binary.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- New split *algorithm* or any change to renumbering / dependency rewiring — reuse `_apply_step_split` as-is.
- Auto-splitting in unattended mode — the repo invariant is that a structural plan edit never happens unattended.
- Restructuring beyond a single-step split (e.g. merging steps, N-way re-plan).

## Risks

- **Unattended structural mutation.** Failure shape: a split executes in CI / `--yes` / `yes_to_all` / non-TTY, violating the repo invariant. Severity: high. Mitigation: callers gate on TTY + the split opt-in flag and treat `--yes`/`yes_to_all` as unattended (recommend-only) — an auto-confirm must never bypass the never-mutate-unattended rule; unattended paths emit a recommendation only, never mutate structure.
- **Splitting a step whose downstream work already started.** Failure shape: structure is mutated after a downstream step has run/started, corrupting run state. Mitigation: `_split_is_safe(plan, step_id)` runs before any split; on failure, surface a re-plan recommendation instead. Unresolved gap: relies on the non-PENDING-run-state gate being correctly honored, mirroring `detail.py` Phase B.
- **Invoker seam not neutralized in tests.** Failure shape: tests spawn the real `claude` binary because the bridge shells out via `_propose_step_split`. Mitigation: neutralize the invoker seams per `TESTING.md`.
- **Unattended proposal cost.** Failure shape: step 5 drops detail's `allow_split and isatty()` guard, so `mixed_steps` are iterated whenever non-empty. Because `escalate_to_split` proposes **always-on (ungated)** — it calls `_propose_step_split` before deciding apply-vs-recommend — every `detail` run with a flagged mixed step now spends one Claude `_propose_step_split` call per mixed step, **including the default, non-`--split`, non-TTY path** that today spends zero Claude on Phase B (the dropped guard skipped it). The result is one Claude round-trip per mixed step to build a recommendation it only prints, a per-mixed-step cost increase against the project's minimize-Claude posture. Severity: low. Mitigation: accepted as the cost of invariant (1) (always validate the more-correct plan, even unattended). No title-free recommend variant is possible: the recommendation's `suggested_action` is `plan-tool split --step N --into '<title-a>' --into '<title-b>'`, whose titles come only from the propose call, so a usable split recommendation cannot skip propose. Separately, a recurring trigger-2 `BLOCKED-STRUCTURAL` finding from an apply-eligible source would be re-collected, re-dispatched to `apply_finding`, and re-proposed *once per unattended iteration* until the no-progress halt — a per-iteration (not just per-mixed-step) re-propose cost. Mitigation: step 5 remembers/dedupes a recommend-only trigger-2 finding in a per-run seen-set so it is not re-dispatched (and not re-proposed) on subsequent unattended iterations of either loop, bounding it to a single propose call per finding per run.

## Testing

Mirror source modules per `TESTING.md` (`plan_tool/X.py` → `tests/test_X.py`), defaulting to unit tests. Neutralize the invoker seams — the bridge shells out to Claude via `_propose_step_split`, so any test driving `escalate_to_split` must override the invoker or the autouse gate in `tests/conftest.py` will raise.

- `tests/test_review.py` — cover `review.is_structural(rec)` returning true for `detail-purity` and false otherwise; confirm `detail-purity` stays excluded from `APPLY_ELIGIBLE_SOURCES`.
- `tests/test_launcher.py` — cover `parse_apply_verdict` / `ApplyFindingResult` recognizing `BLOCKED-STRUCTURAL`; unit-test `escalate_to_split` for the safe-split, unsafe-split (re-plan recommendation), interactive-opt-in (apply sequence runs), and unattended (recommendation only, no mutation) paths.
- `tests/cli/test_review_actions.py` (or the mirror of `cli/review_actions.py`) — cover the `BLOCKED-STRUCTURAL` branch in the apply walk's verdict handling.
- Integration (`@pytest.mark.integration`): exercise the `create`/`detail` convergence loop end-to-end so a `detail-purity` finding routes to escalation instead of being skipped, and converges in one interactive pass. Run these when modifying the convergence loop, `launcher.py`, or `review.py`.

Existing suites for `review.py`, `launcher.py`, and `cli/review_actions.py` must still pass.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (refactor) — behavior-preserving re-point of detail Phase B at the bridge; existing `detail --split` tests stay green and a delegation test is added; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- `review.is_structural(rec)` returns true for a `detail-purity` finding and false for non-structural findings.
- `detail-purity` remains excluded from `APPLY_ELIGIBLE_SOURCES` and is routed to `escalate_to_split` rather than skipped by the convergence loop.
- `apply_finding` emits `## Verdict: BLOCKED-STRUCTURAL` (parsed by `parse_apply_verdict` into `ApplyFindingResult`) when Claude determines mid-apply that the only correct fix is a split.
- `escalate_to_split` runs `_split_is_safe(plan, step_id)` before any split; when a downstream step has run/started it does not split and surfaces a re-plan recommendation.
- In interactive mode with the split opt-in flag set, `escalate_to_split` runs `_confirm_split` → `_apply_step_split` → `_migrate_downstream_details_after_split` and the convergence loop finishes in one pass.
- In unattended mode (CI / `--yes` / non-TTY), `escalate_to_split` never mutates plan structure and emits a structured split recommendation (proposed titles + rationale) into the findings report.
- Under `allow_split=True` with `yes_to_all` set, `escalate_to_split` recommends only and never splits — the confirm must be a genuine fresh interactive assent, not satisfied by `yes_to_all`; callers must not supply a `prompt_fn` that auto-answers under `yes_to_all`.
- In the `create` convergence loop, the bridge's returned `structural-split` `Recommendation` reaches the reported findings by being appended to the `open_deferred` list and surfaced by a post-apply-loop `emit_triage_summary` (or explicit print) over the appended recs — not by the pre-loop `emit_triage_summary` that has already fired this iteration.
- When `escalate_to_split` returns `recommendation=None` (`proposal-unusable`/`step-missing`) on create's trigger-2 path, the original `BLOCKED-STRUCTURAL` finding is appended to the `open_deferred` list and surfaced by the same post-apply-loop emit, so the unresolved structural finding is reported rather than silently dropped (invariant (1)(a)).
- A surfaced split recommendation keeps rc 0 unless `--fail-on-findings` is passed (exit-code convention).
- Auto-execution of a split occurs only behind the explicit opt-in flag (aligned with `detail --split`'s `allow_split`), never default-on in the convergence loop.

## Deferred

- Pairing with the granularity advisor (`step-granularity-advisor.md`) that *produces* `granularity-split` findings — this bridge executes today's `detail-purity` classification and stands alone; wiring the advisor as the upstream producer is a separate follow-up.
- Renaming the `detail-purity` source to `granularity-split` across the classifier and call sites — postponed to avoid churning the classification surface mid-bridge; revisit when the advisor lands.
- Persisting the `create` `structural-split` recommendation as a saved finding and exposing a create apply-findings option (mirroring how the completeness audit stores conceptual findings for a later apply) — `create.py` has no `save_review`/sidecar machinery today, so the create path folds the recommendation into `emit_triage_summary`/`open_deferred` only; persistence is a separate follow-up.
