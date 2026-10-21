> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Escalate Structural Findings To Split
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Single-source the structural-finding predicate behind review.is_structural
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/01-single-source-structural-finding.md
  status: done
- id: 2
  title: Render structural-split recommendations in triage_reason + emit_triage_summary
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/02-render-structural-split-recommendations.md
  status: done
- id: 3
  title: Add BLOCKED-STRUCTURAL verdict bucket to parse_apply_verdict + apply-finding
    prompt
  files:
  - plan_tool/launcher.py
  - plan_tool/prompts/apply-finding.md
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  gate:
  - grep -q 'structural_verdict_option' plan_tool/prompts/apply-finding.md
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/03-blocked-structural-verdict-bucket-parse.md
  status: done
- id: 4
  title: Add the escalate_to_split bridge seam (safe-gate, single-proposal recover,
    apply-vs-recommend)
  files:
  - plan_tool/launcher.py
  - tests/test_launcher.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/04-escalate-split-bridge-seam-safe-gate.md
  status: done
- id: 5
  title: Re-point detail --split Phase B at escalate_to_split (behavior-preserving)
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/05-re-point-detail-split-phase-escalate.md
  status: done
- id: 6
  title: Add trigger-1 unattended split-recommendation surface in detail Phase B
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/06-trigger-unattended-split-recommendation.md
  status: done
- id: 7
  title: Isolate the in-loop renumbering contract for trigger-2 BLOCKED-STRUCTURAL
    in detail
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  - 5
  - 6
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/07-isolate-loop-renumbering-contract.md
  status: done
- id: 8
  title: Handle BLOCKED-STRUCTURAL in plan_tool/cli/review_actions.py apply walk
  files:
  - plan_tool/cli/review_actions.py
  - plan_tool/cli/review_cmd.py
  - plan_tool/cli/reconcile.py
  - tests/cli/test_review_actions.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/08-handle-blocked-structural-cli-review.md
  status: done
- id: 9
  title: Document the escalate-to-split bridge in RUNBOOK + CLAUDE.md architecture
  files:
  - RUNBOOK.md
  - CLAUDE.md
  complexity: low
  change_type: non-code
  depends_on:
  - 4
  - 7
  - 8
  detail: docs/implementation-plans/plan-details/escalate-structural-findings-to-split/09-document-escalate-split-bridge-runbook.md
  status: done
---
# Escalate Structural Findings To Split

## Overview

Build a bridge that routes an already-classified **structural finding** — one whose only correct fix is to split a step into two — to the **already-existing split engine**, under the same safety gates `detail --split` Phase B uses today. This is routing and plumbing: **no new split algorithm**. The split engine (`create._propose_step_split` / `create._apply_step_split`), the safety gate (`detail._split_is_safe`), the operator confirm (`detail._confirm_split`), and downstream-detail migration (`detail._migrate_downstream_details_after_split`) are reused verbatim — they are already wired to this exact trigger in `detail --split` Phase B, just nowhere else.

Two paired invariants govern the bridge:

1. **Always validate the more-correct plan.** For a recognized structural finding with a concrete target step, the bridge always surfaces *something* — never silently skipped. It *proposes* (one `_propose_step_split` Claude call) only on the apply-eligible path (interactive + opt-in); the proposed titles drive the in-place split, while a declined or failed proposal still records the **generic** `_structural_split_rec(step)` (a step-only rec — never a title-derived one; titles are not threaded into the rec). On the common recommend-only path (default `allow_split=False`) the ladder short-circuits before `_propose_step_split` and records the same generic `_structural_split_rec(step)` with zero Claude — a recommendation without a proposal. Two recognized-target outcomes carry `recommendation=None` by design but are **still surfaced, not skipped**: `unsafe` (when `_split_is_safe` fails because a downstream step has run, the bridge surfaces a blocking-ids warning — the recommended `plan-tool split` would itself be blocked) and `proposal-unusable` (an unparseable `_propose_step_split` reply, surfaced as a note; `plan-tool split` remains the valid manual remedy). A finding with **no** concrete target step — a plan-level source (`step_id is None`, e.g. `plan-correctness`) that the shared verdict prompt may still tag `BLOCKED-STRUCTURAL` — falls outside "concrete target": the split engine is step-scoped, so the caller does not call `escalate_to_split` (no `step_by_id(None)` crash) and instead surfaces a "no single target step — re-decompose by hand" signal. Only step 8's apply-walk needs this guard: detail's per-step convergence loop (step 7) always escalates with a concrete `step.id`, so a `None` target never arises there.
2. **Never mutate structure unattended.** An in-place split happens only interactively, behind an explicit opt-in flag, with a genuine operator confirm. Every unattended path (CI / `--yes` / `yes_to_all` / non-TTY) recommends only. `--yes`/`yes_to_all` is an *unattended* path — it must not satisfy the interactive-confirm gate.

## Problem statement

A finding whose only correct fix is "split this step into two" is recognized but dead-ended. The granularity MIXED-STEP purity check (`plan_tool/granularity.py:parse_mixed_step_findings`, surfaced through `detail`) tags an over-packed / mixed-concern step as `granularity-split`, which is excluded from `APPLY_ELIGIBLE_SOURCES`, and the convergence loop skips it. Separately, when Claude determines mid-apply that the only correct fix is a split, `apply_finding` returns a bare `BLOCKED` and the caller reverts and reports. Either way `apply_finding`/convergence cannot finish what they start.

There are two triggers, and they are **not symmetric** — keep them in separate steps:

1. **Pre-classified `granularity-split` (trigger 1).** Lives in `detail`'s Phase B, **outside** the per-step convergence apply loop. The split runs after the `for step in target_steps` loop closes, so it never renumbers ids out from under an in-flight iteration. This trigger is clean and self-contained. The granularity MIXED-STEP purity check (`granularity.py`, surfaced by `detail`) is the producer of the `granularity-split` findings this trigger consumes.
2. **Discovered mid-apply `BLOCKED-STRUCTURAL` (trigger 2).** A new verdict bucket on `apply_finding`, inspected **inside** the convergence apply loop. When Claude mid-apply decides the only correct fix is a split, it emits `## Verdict: BLOCKED-STRUCTURAL` instead of a bare `BLOCKED`. This is the hard trigger: applying a split renumbers step ids in the middle of a loop that iterates *by* step id, which breaks every assumption the loop makes (stale captured ids, re-collection re-deriving the same finding, the per-step summary having already emitted, partial prose edits needing revert-first).

The predecessor plan's recurring findings were *all* symptoms of trigger 2 being forced through the loops, stated twice (create's outer `while`, detail's nested `for step` → `for rec`) with different mechanics. Separating the triggers, and isolating the loop-renumbering contract into its own step, is the core of this re-decomposition.

**Open question to settle first — is create-side trigger 2 even reachable?** `create` dispatches to `apply_finding` only prose-fill sources (`APPLY_ELIGIBLE_SOURCES = {body-completeness, detail-body, plan-correctness, reconcile, …}` in `review.py`). For create's trigger 2 to ever fire, Claude would have to be mid-apply on a "fill in this prose" finding and decide the only correct fix is a *step split*. The predecessor plan asserted this is create's "live structural trigger" but never named a concrete scenario where it happens. Resolve this before decomposing the create side. Default: **defer create-side trigger-2** to Deferred as forward-only wiring unless a real scenario is named. Create-side trigger 2 is inert, but **not** because create never produces a structural source: `create.py:_granularity_split_hints` runs `assess_granularity(..., stage="create")` and *does* surface `granularity-split` recs (as `(s)plit` hints in the change-type review loop). The real reason it stays inert is that `granularity-split` is **absent from `review.collect_deterministic_findings`**, so it never enters create's `apply_finding` convergence loop — create dispatches only the prose-fill apply-eligible sources to `apply_finding`. With trigger 2 deferred the create side therefore carries no live structural trigger and needs no in-loop split handling at all. **But step 3 teaches the *shared* `prompts/apply-finding.md` to emit `BLOCKED-STRUCTURAL`, so create's `apply_finding` callers can now receive a verdict create's loop has no handler for — it branches only on `APPLIED`, so a create-side `BLOCKED-STRUCTURAL` dead-ends exactly like a bare `BLOCKED`, never escalated.** Deferring create-side trigger 2 therefore requires **guard (a): scope the shared prompt so create never emits the verdict.** Step 3 threads an opt-in `allow_structural_verdict` flag into `apply_finding`'s prompt render (`render_prompt(..., mode="apply-finding")` `extra_vars`), **defaulting OFF**; the `BLOCKED-STRUCTURAL` instruction is rendered only for a caller that opts in. The `detail` / review apply paths and the `escalate_to_split` bridge opt in; **create's `apply_finding` callers inherit the OFF default and are not edited**, so a create-side `apply_finding` never receives the instruction and cannot return `BLOCKED-STRUCTURAL`. No create-side surface, no `create.py` change — fully consistent with deferring create-side trigger 2. The missing caller identity that made guard (a) look impossible is supplied by that single flag (a trivial `extra_var` added alongside step 3's existing `launcher.py` / `apply-finding.md` edits — no `rec.source` discriminator needed), so step 3 stays scoped to `launcher.py` + `prompts/apply-finding.md` + tests and does **not** add `create.py`. With the verdict scoped off the create path, the Deferred rationale — `BLOCKED-STRUCTURAL` is "actively routed to the `escalate_to_split` bridge … so it never reaches the completeness summary as an unhandled split target" — holds, because create can no longer produce the verdict at all.

**Same test, applied to detail-side trigger 2 — it passes with a named scenario, so step 7 is live, not inert.** The "name a concrete scenario or Defer" test the create side fails is applied symmetrically here, and detail clears it: detail's convergence apply loop dispatches the apply-eligible prose-fill sources `detail-body` / `body-completeness` / `detail-reconcile` (per `review.APPLY_ELIGIBLE_SOURCES`) to `apply_finding`. The concrete scenario — **mid-apply on a `detail-body` finding (authoring/expanding a step's Implementation section), Claude finds the step as scoped mixes a refactor and a feature so the prose cannot be made type-pure within one step; the only correct fix is to split the step, and it emits `## Verdict: BLOCKED-STRUCTURAL` instead of writing the body.** This is reachable because those sources are apply-eligible and routed through `apply_finding` inside detail's loop, whereas create's prose-fill sources have no equivalent named path to a structural verdict. Step 7's machinery therefore backs a live trigger, not the live-but-inert wiring the acceptance criterion forbids — and a step-7 test must exercise the real apply path emitting `BLOCKED-STRUCTURAL` from a `detail-body` apply, not only stub `apply_finding` to return it.

## Architecture

The bridge must honor these constraints:

- **Single proposal, never two.** `_propose_step_split` does one internal `invoker(prompt)` call and returns only `Optional[list[Step]]` (titles); rationale is captured into a discarded local. `escalate_to_split` reuses `_propose_step_split` as-is for titles and surfaces a generic structural-split rec via `_structural_split_rec(step)` — it does not recover or thread the proposal's rationale (the rec is generic, and recommend-only paths short-circuit before proposing). Never a second `invoker` call (a divergent proposal could describe a different split than the titles already chosen).
- **Safe-gate always first.** Re-parse the plan and run `_split_is_safe(plan, step_id)`; if a downstream step has run/started, do not split — recommend a re-plan instead.
- **Apply-failure degrades, never crashes.** Mirror Phase B's `try/except CreateError` log-and-continue: catch a mid-apply `CreateError`, mutate nothing, surface a re-plan recommendation.
- **Design the seam to be caller-agnostic (forward-design for BACKLOG #57).** `escalate_to_split` ships wired to two live callers (detail loop, review walk) — the create loop is deferred (no named trigger-2 scenario; see the Open question) — but the completeness *authoring* audit is the planned successor (BACKLOG #57: a decomposition convergence loop, with this bridge as its *localized executor*). Keep the seam's signature free of create/detail-specific coupling: take `plan_path` / `step_id` / `repo_root` / `invoker` / the opt-in + TTY flags as plain parameters, return a structured `EscalateResult` the caller interprets, and do **not** reach into create's or detail's loop state. This costs nothing now and lets #57 reuse the executor without a refactor. Do **not** build the authoring-audit wiring here — that is #57's scope; only avoid foreclosing it.

**Step decomposition (the reason for this seed).** Each step is one `change_type` and one coherent surface:

- **Refactor — single-source the structural predicate.** Add `review.is_structural(rec)` + `STRUCTURAL_SOURCES` (seeded with the one live source, `granularity-split`) as a new predicate with **no consumer** — `triage_reason` is left untouched, so the step is genuinely behavior-preserving (the predicate is dead until step 2 wires it in). `review.py` keeps the source as a string literal, not an import of `granularity.GRANULARITY_SPLIT_SOURCE` (that import would cycle). Keep `granularity-split` excluded from `APPLY_ELIGIBLE_SOURCES`.
- **Feature — render structural recommendations in the triage summary.** Add the `is_structural` `triage_reason` branch (points the operator at `plan-tool split`, not `plan-tool detail`) for **both** `structural-split` and the live `granularity-split` — routing `granularity-split` here is itself the behavior change (at HEAD it falls through to the generic "structural diagnostic" text) — plus `emit_triage_summary` rendering of `rec.body`/`rec.suggested_action`. This is the new *output* behavior the predecessor plan illegally bundled into the refactor step (the audit BLOCKED it for exactly this refactor+feature impurity — do not repeat it).
- **Feature — `BLOCKED-STRUCTURAL` verdict bucket.** Extend `parse_apply_verdict` / `ApplyFindingResult`, and teach the shared `apply-finding` prompt to emit `## Verdict: BLOCKED-STRUCTURAL`. Scope it with guard (a): thread an opt-in `allow_structural_verdict` flag (default OFF) through `apply_finding`'s prompt render so the `BLOCKED-STRUCTURAL` instruction reaches only callers that handle it (`detail` / review / the bridge); create's callers inherit OFF and never emit it — no `create.py` change, consistent with deferring create-side trigger 2.
- **Feature — the `escalate_to_split` bridge seam itself.** Safe-gate → single-proposal recover (titles from one `invoker` call — never a second proposal) → interactive-opt-in apply vs. unattended recommend. Enumerate **all** outcomes including the `_apply_step_split` `CreateError` failure path (catch, mutate nothing, recommend) and `proposal-unusable` / `step-missing` (`recommendation=None`). Reuse the Phase-B lazy `create` imports.
- **Refactor — re-point `detail --split` Phase B at the bridge.** Behavior-preserving; existing `detail --split` tests stay green; add a delegation test. This is trigger 1, the clean path.
- **Feature — trigger 1 unattended recommendation surface in `detail`.** Drop the Phase-B `allow_split and isatty()` warning-only guard and add the **post-Phase-B emission surface** (Phase B runs after the per-step loop, so the in-loop `emit_detail_findings_summary` calls cannot carry its recommendation).
- **Feature — the loop-renumbering contract (trigger 2 in `detail`).** Isolate everything that makes an in-loop split safe as its own step: break out of the inner `for rec in open_apply`, re-parse, re-collect `target_steps` from the renumbered plan, break the enclosing `for step in target_steps`, revert partial prose edits via `_restore_text_files` before escalating, and a per-run seen-set so a recommend-only trigger-2 finding is not re-dispatched (and re-proposed) every unattended iteration. This step also flips `allow_structural_verdict=True` on the detail convergence-loop `apply_finding(...)` call site — without it step 3's flag stays OFF on this path, real Claude never emits `BLOCKED-STRUCTURAL`, and this contract is dead. This contract is what the predecessor plan scattered across five plan-body sentences — that scattering *was* the bug.
- **Feature — handle `BLOCKED-STRUCTURAL` in `cli/review_actions.py`.** The apply-walk verdict branch (escalate when interactive + opt-in, else surface recommendation), treating `yes_to_all` as unattended (recommend-only). This step also flips `allow_structural_verdict=True` at the `review`/reconcile walk's `_build_review_action_fn(...)` call site (a per-call-site builder flag, since review and completeness-apply share the one `apply_finding` call at `review_actions.py:387`) so the rendered prompt offers the verdict this branch routes — `cmd_completeness_apply` constructs its action fn leaving the flag OFF. Without this flip step 3's flag stays OFF on this path and the dispatch arm is dead.

Create-side trigger 2 gets a step **only if** the open question above names a real scenario; otherwise it is Deferred, not a step.

## References

- [CLI reference - Claude Code Docs](https://docs.anthropic.com/en/docs/claude-code/cli-reference) — Authoritative reference for the `claude` CLI flags and `--output-format stream-json` NDJSON contract the invoker seam shells out to and parses.
- [argparse — Parser for command-line options, arguments and subcommands (Python 3.13)](https://docs.python.org/3/library/argparse.html) — Official docs for subparsers, set_defaults, and flag/default wiring needed to add the new `--split` opt-in and structural-split routing in the CLI parser layer.
- [subprocess — Subprocess management (Python 3.13)](https://docs.python.org/3/library/subprocess.html) — Reference for `run`/`Popen`, return codes, and streaming stdout — the basis of the shell invoker seam and the exit-code convention the bridge must preserve.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — Defines field defaults, default_factory, and Optional typing used to extend `ApplyFindingResult` and design the new structured `EscalateResult` return type.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Shows safe attribute/function patching that tests use to override the `invoker=` seams so the autouse gate never spawns a real `claude` binary.
- [API Reference (markers, fixtures) — pytest](https://docs.pytest.org/en/stable/reference/reference.html) — Canonical reference for `@pytest.mark.integration`, `timeout`, and fixtures governing the unit-vs-integration split the plan's testing section prescribes.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- New split *algorithm* or any change to renumbering / dependency rewiring — reuse `_apply_step_split` as-is.
- Auto-splitting in unattended mode.
- Restructuring beyond a single-step split (merge steps, N-way re-plan).
- **Wiring the bridge into the completeness *authoring* audit / `completeness-apply` walk.** This bridge serves the create/detail content-generation loops and the apply/review execution walk. Letting the authoring audit escalate a mis-decomposed plan to a re-plan (rather than only patching prose) is the generalized follow-up — see BACKLOG #57.

## Risks

- **Unattended structural mutation.** Severity: high. Mitigation: callers gate on TTY + the opt-in flag and treat `--yes`/`yes_to_all` as unattended.
- **Splitting a step whose downstream work already started.** Mitigation: `_split_is_safe` before any split; recommend re-plan on failure.
- **Invoker seam not neutralized in tests.** Mitigation: override the invoker seams per `TESTING.md`; the autouse gate raises on a real `claude` spawn.
- **Unattended propose cost.** On a `detail --split` run on a non-TTY (`allow_split=True`, auto-decline), dropping the Phase-B `isatty()` guard means one `_propose_step_split` Claude call per flagged mixed step; on a default run (`allow_split=False`) `escalate_to_split`'s ladder short-circuits to recommend-only before `_propose_step_split` and spends zero Claude. The seen-set bounds the trigger-2 path to one propose per finding per run. Severity: low; accepted as the cost of invariant (1).

## Testing

Override the invoker seams per `TESTING.md` for every test that exercises a Claude-shelling path — the autouse gate raises on a real `claude` spawn. Default to unit tests over the new leaves (`review.is_structural`, `parse_apply_verdict`'s `BLOCKED-STRUCTURAL` bucket, `escalate_to_split`'s outcome enumeration with a stubbed invoker). Add `@pytest.mark.integration` only for the cross-module wiring that a unit test would miss: the `detail --split` Phase-B re-point delegating to the bridge (existing `detail --split` tests must stay green; add a delegation test), the in-loop trigger-2 contract in `detail` (an applied split breaks both loop levels, re-parses, re-collects `target_steps`, and the seen-set suppresses re-proposal across unattended iterations), and the `cli/review_actions.py` apply-walk verdict branch. When modifying those source files, run the integration tier covering `detail` and the review/apply walk.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (feature) — unit tests added with the implementation; green before completion.
- step 9 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `review.is_structural(rec)` is the single source for the structural-split guard, seeded with the live `granularity-split` source (string literal, not a `granularity` import); the refactor step adds the predicate with no consumer and changes no output, the feature step adds the `triage_reason` routing (for `granularity-split` and `structural-split`) and `emit_triage_summary` rendering.
- `apply_finding` emits `## Verdict: BLOCKED-STRUCTURAL`, parsed into `ApplyFindingResult`.
- `escalate_to_split` runs `_split_is_safe` first; recovers titles from one proposal (no rationale recovery — the rec is generic); enumerates `applied` / `recommended` / `unsafe` / `proposal-unusable` / `step-missing` — a mid-apply `CreateError` folds into `recommended` (catch, mutate nothing, recommend), not a separate outcome.
- The `unsafe` outcome's durability contract is **transient-warning-only**: it surfaces a blocking-ids warning (steps 7/8) and carries `recommendation=None` by design — it emits **no** durable structural note, because the recommended `plan-tool split` would itself be blocked while a downstream step has run. An operator on a non-TTY CI run gets only the scrolling warning, not a persisted record; re-detection on the next `detail`/apply pass (once the downstream blocker clears) is the discoverability path, not a saved artifact. Persisting an unsafe-path note is explicitly out of scope.
- Interactive + opt-in runs `_confirm_split` → `_apply_step_split` → `_migrate_downstream_details_after_split` and converges in one pass; unattended recommends only and never mutates structure.
- An in-loop (trigger 2) applied split in `detail` breaks both loop levels, re-parses, re-collects `target_steps`, and processes no stale pre-split `Step`. The post-loop re-author forwards `budget`, so under `--iterate` the split **re-enters convergence** over the renumbered plan — the two new type-pure halves are driven through their own convergence apply loop in the same run, not deferred to a later `--iterate` invocation.
- A recommend-only trigger-2 finding is remembered in a per-run seen-set and not re-proposed on later unattended iterations.
- A surfaced split recommendation keeps rc 0 by default. The `--fail-on-findings` flip governs only the surfaces that expose that flag — the `review` / `completeness` apply walks. The flip is driven by the **original unresolved apply finding** that returned `BLOCKED-STRUCTURAL` (already counted in the walk's tally), not by registering the escalate-produced `structural-split` rec: step 8's `_dispatch_structural_escalation` only maps each `EscalateResult.outcome` to a walk status string and surfaces the recommendation — it does **not** add a new entry to the tally. So when `--fail-on-findings` is set, the rc flips because the source finding was left unresolved (escalated, not applied), exactly as any other unresolved finding flips it. On the `detail` surface (no `--fail-on-findings` flag; steps 6–7 emit via `_emit_split_recommendations`) a surfaced split recommendation keeps rc 0 unconditionally.
- Create-side trigger 2 is either backed by a named scenario *or* Deferred — not shipped as live-but-inert wiring.
- Detail-side trigger 2 is backed by the named `detail-body`-apply-turns-structural scenario (see the Open question), and a step-7 test exercises the real apply path emitting `BLOCKED-STRUCTURAL` — not only a stubbed `apply_finding` return. The test asserts the prompt the apply call rendered contains the `BLOCKED-STRUCTURAL` bullet (the fake invoker emits the verdict only when that bullet is present), so it fails if `allow_structural_verdict` is not set on the detail call — proving step 7's machinery is live end-to-end, not inert.
- Step 7 passes `allow_structural_verdict=True` on the detail convergence-loop `apply_finding(...)` call site and step 8 passes it at the `review`/reconcile walk's `_build_review_action_fn(...)` builder call site (a per-call-site flag — `cmd_completeness_apply` leaves it OFF despite sharing the dispatcher), so step 3's flag is flipped ON where the verdict is routed; neither leaves it at the OFF default on a path that reads `BLOCKED-STRUCTURAL`.

## Deferred

- **Create-side trigger 2** unless the open question names a real scenario.
- A deeper actuating pairing with the granularity advisor. The advisor already *produces* `granularity-split` findings (`plan_tool/granularity.py`), and this plan consumes them — `is_structural` keys on that source and `triage_reason` points the operator at `plan-tool split`. What stays deferred is **auto-wiring a `granularity-split` finding to an actuating split command** (a bridge from detection straight to the split engine, beyond rendering the recommendation). The source rename `detail-purity` → `granularity-split` already landed in the codebase (the granularity fold), so this plan consumes `granularity-split` directly rather than renaming anything.
- Persisting the create `structural-split` recommendation as a saved finding.
- Widening `completeness_report.py`'s blocked rollups (`_blocked_split_targets`, the `blocked = [...]` lists, `blocked_ct`, and the "blocked N (needs a new step/detail file (split into sub-steps))" headline) to count `BLOCKED-STRUCTURAL`. **Rationale for the temporary exclusion:** on the two paths this plan wires the bridge into — the `detail` loop and the `review`/apply walk (steps 7/8) — `BLOCKED-STRUCTURAL` is actively routed to the `escalate_to_split` bridge, which resolves or recommends it in-loop, so it never reaches the completeness summary as an unhandled split target. Routing is **not** universal, though: two completeness surfaces touch `apply_finding`. The authoring-audit walk (`completeness_cmd.py:cmd_completeness`) calls `apply_finding` directly, and the completeness-apply walk (`completeness_cmd.py:cmd_completeness_apply`, ~line 293) builds the standard `_build_review_action_fn` and dispatches through the *same* `_dispatch_apply_finding` / `apply_finding` (`review_actions.py:387`) that step 8 edits and that the `review`/reconcile walk opts into — both using the shared `prompts/apply-finding.md` step 3 teaches to emit `BLOCKED-STRUCTURAL`. Neither is wired to the bridge (Out of scope: "the completeness-apply walk"). **Guard (a) (step 3) closes both paths because the opt-in is gated at the `_build_review_action_fn` call site, not by the shared dispatcher:** `apply_finding` defaults `allow_structural_verdict=False`, and step 8 threads `allow_structural_verdict` (and the bridge arm) through `_build_review_action_fn` as a per-call-site builder flag that **only the `review`/reconcile call site sets ON** — `cmd_completeness_apply` constructs its action fn leaving the flag at the OFF default, and `cmd_completeness` never opts in either. So although `cmd_completeness_apply` shares the dispatcher with the review walk, it does **not** inherit the verdict: the shared prompt never offers `BLOCKED-STRUCTURAL` on either completeness surface and a completeness-side `apply_finding` cannot emit it — the verdict simply cannot arise on those paths, so there is nothing for the `verdict == "BLOCKED"` rollup to silently miss. Folding `BLOCKED-STRUCTURAL` into the rollup is therefore still deferred and **safe**: it becomes relevant only when BACKLOG #57 wires the completeness authoring-audit into the bridge and opts it in (`allow_structural_verdict=True`), at which point the rollup becomes that audit's convergence signal and the bridge gains its completeness-side caller. Widening the rollup here, ahead of that consumer, would double-count a verdict the bridge already handles on the detail/review paths.
- Wiring the bridge into the completeness authoring audit (the generalized "escalate to re-plan instead of patching prose" capability).
- **CLI surface that sets `allow_split=True` for the `review` / `completeness` apply walks.** Step 8 threads `allow_split` through `_build_review_action_fn` and ships the "escalate when interactive + opt-in, else recommend" branch, but only `detail` feeds `allow_split` from a CLI flag (`args.split` → `cli/authoring.py`); no flag wires it for the review/completeness walks. So step 8's in-place auto-apply branch is **inert (recommend-only) in production** until that flag lands — reachable only via the builder kwarg and exercised via unit tests. This is a *conscious* deferral (same shape as create-side trigger 2), not a silent gap: the escalate apply path is still proven live through `detail` + step 8's unit tests; only the review/completeness CLI opt-in is postponed.
