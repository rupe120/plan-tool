> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Document the escalate-to-split bridge in RUNBOOK + CLAUDE.md architecture

## Summary

- Document the `escalate_to_split` bridge (built by step 4, wired by steps 5–8) in the two human-facing guides: a new operational subsection in `RUNBOOK.md` and one architecture paragraph in `CLAUDE.md`.
- **This is a non-code step** — it adds no production code and changes no behavior. Its job is to make the bridge's apply-vs-recommend contract, its two invariants, and the `structural-split` / `BLOCKED-STRUCTURAL` vocabulary discoverable to operators and future agents.
- Key decision: place the RUNBOOK content as a `###` subsection under the existing `## Workflow: drive an authoring task to convergence (--iterate)` (no `## Table of contents` edit needed, since that TOC lists only `##` workflows), and place the CLAUDE.md content as one bolded paragraph beside the **Correctness gates** paragraph in `## Architecture` (the bridge is a cross-cutting seam, not a pipeline stage).
- On green: an operator reading `RUNBOOK.md` learns that a recognized mixed/structural step now auto-surfaces a `plan-tool split` recommendation on every `detail` authoring run and review/apply walk (the `create` path surfaces none until create-side trigger 2 lands) and auto-applies it only on a safe interactive opt-in; a future agent reading `CLAUDE.md` finds the bridge named beside its sibling validation seams; the existing re-decompose cross-reference points at the landed auto-bridge instead of describing it as future work.

## Table of Contents

- [Summary](#summary) — what this docs step adds and the result on green
- [Why](#why) — the undocumented bridge this surfaces
- [Files (creates vs edits)](#files-creates-vs-edits) — the two docs touched
- [Implementation](#implementation) — the RUNBOOK subsection and the CLAUDE.md paragraph, with the exact contract to state
- [Tests](#tests) — verification appropriate to a docs step
- [Acceptance criteria](#acceptance-criteria) — checkable conditions
- [References](#references) — relevant authoritative docs
- [Deferred](#deferred) — docs surfaces left to other steps

## Why

The escalate-to-split bridge (`plan_tool/launcher.py:escalate_to_split`, added by step 4 and consumed by steps 5–8) introduces operator-visible behavior that is currently undocumented: a recognized mixed/structural step now emits a `structural-split` recommendation pointing at `plan-tool split` on every `detail` authoring run and review/apply walk (the `create` path surfaces no escalate-bridge `structural-split` recommendation until create-side trigger 2 lands — create *does* surface its own pre-existing `granularity-split` `(s)plit` hints in the change-type review loop, but those never reach `apply_finding`, so the bridge is not wired into create and create-side trigger 2 is Deferred), and auto-applies the split only on a safe, interactive, opted-in path. Three new vocabulary items leak into operator output — the `structural-split` recommendation source, the `BLOCKED-STRUCTURAL` apply verdict, and the "always recommend, never mutate unattended" pair of invariants — with no entry in `RUNBOOK.md` or `CLAUDE.md` explaining them. `RUNBOOK.md`'s re-decompose section even ends by calling the auto-escalation "the manual version of what BACKLOG #57 proposes to surface automatically" — a forward-looking note that is now stale because the auto-bridge has landed. This step closes the documentation gap so operators understand what they're seeing and future agents find the bridge in the architecture map next to its sibling seams.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `RUNBOOK.md` — add one `###` subsection (the escalate-to-split bridge) under `## Workflow: drive an authoring task to convergence (--iterate)`; update the stale BACKLOG #57 cross-reference at the end of `### When repeated audit/apply doesn't converge — re-decompose, don't keep patching` to point at the landed bridge.
  - `CLAUDE.md` — add one bolded paragraph in `## Architecture`, placed after the **Correctness gates** paragraph, describing the bridge seam.

## Implementation

### `RUNBOOK.md`

- **Add a `###` subsection** under `## Workflow: drive an authoring task to convergence (--iterate)` (e.g. `### The escalate-to-split bridge (auto split-or-recommend)`), after `### Completeness with iteration` and before `### How the loop terminates`. A `###` does not appear in the `## Table of contents` list (which carries only `##` workflows), so leave that TOC untouched.
- **State the bridge's two invariants up front** (the plan's framing): always surface the more-correct plan (recommend a split even when declining to auto-edit), and never mutate plan structure unattended.
- **Describe the apply-vs-recommend decision.** The bridge auto-applies the split only when all hold: the split is safe (no downstream non-PENDING/run-started step blocks it), the caller opted in (`allow_split`, set by interactive `detail --split`), and an interactive confirm answers yes. Every other path recommends only — no plan mutation, and on the default path no Claude is spent.
- **Name the two `detail` triggers** so an operator can map output to cause:
  - Trigger 1 — the granularity MIXED-STEP purity check flags an over-packed/mixed step before the apply loop (the `granularity-split` finding from `plan_tool/granularity.py`, surfaced through detail), handled in `plan_tool/detail.py:generate_detail`'s Phase B.
  - Trigger 2 — Claude, mid-apply on an ordinary finding, returns the `BLOCKED-STRUCTURAL` verdict, handled inside the convergence apply loop.
- **List the recommendation surfaces** the operator will see: the `structural-split` recommendation rendered by `plan_tool/review.py:triage_reason` and `plan_tool/review.py:emit_triage_summary` (with the split rationale and the concrete `plan-tool split` invocation on sub-lines), and the post-loop `plan_tool/detail.py:_emit_split_recommendations` emitter on default (non-`--split`) runs.
- **Name the third surface** — the interactive review/reconcile apply walk: a `BLOCKED-STRUCTURAL` verdict there routes through `plan_tool/cli/review_actions.py:_dispatch_apply_finding` to the same bridge (recommend-only unless the walk opts in via `allow_split`).
- **Cross-link** to the existing `### When repeated audit/apply doesn't converge — re-decompose, don't keep patching` subsection: the bridge is the automatic front-end to the manual re-split fork that section describes (its path 2a, `plan-tool split` / interactive `detail --split`).
- **Update the stale cross-reference** at the end of `### When repeated audit/apply doesn't converge — re-decompose, don't keep patching` — the sentence reading "(This fork — re-split vs. re-seed — is the manual version of what BACKLOG #57 proposes to surface automatically.)". Reframe it to state the escalate-to-split bridge now surfaces the localized split case automatically (recommend always, apply on safe interactive opt-in), while the cross-step re-seed fork remains manual. Do not claim the bridge re-seeds — it only handles the one-step 1→2 split.
- **Keep the `plan-tool split` quick-reference row unchanged** (`## Quick reference`, the Authoring table) — `split` is still the manual verb; the bridge is its automatic trigger, documented in the new subsection, not a new command.

### `CLAUDE.md`

- **Add one bolded paragraph** in `## Architecture`, immediately after the **Correctness gates (`review.py`, `gates.py`, `scope_guard.py`, `drift_detection.py`).** paragraph and before **Exit-code convention:**. The bridge is a cross-cutting seam (a sibling of the validation primitives), so it belongs in the architecture map's one-paragraph-per-concern convention — not in `## What this is`, which describes only the `create → detail → audit → run/jira` pipeline.
- **The paragraph should state, densely:**
  - The seam: `plan_tool/launcher.py:escalate_to_split` is the single path from a recognized mixed/structural step to either an applied refactor+feature split or a `structural-split` recommendation.
  - The decision rule: apply only on safe + `allow_split` + interactive confirm; recommend on every other path (unattended, unsafe, non-TTY) — encoding the two invariants (always surface the more-correct plan; never mutate structure unattended).
  - The contract shape: a frozen `EscalateResult` whose `outcome` is one of `applied` / `recommended` / `unsafe` / `proposal-unusable` / `step-missing`; only `applied` mutates; the seam re-parses the plan from disk each call.
  - The three callers: the `create` convergence loop (`plan_tool/create.py:create_plan`), the `detail` Phase B + convergence loop (`plan_tool/detail.py:generate_detail`), and the review/reconcile apply walk (`plan_tool/cli/review_actions.py:_dispatch_structural_escalation`, the arm `_dispatch_apply_finding` delegates to).
  - The two routing tokens: the `structural-split` recommendation source in `plan_tool/review.py` (classified by `STRUCTURAL_SOURCES` / `is_structural`, kept out of the apply-eligible set) and the `BLOCKED-STRUCTURAL` apply verdict parsed by `plan_tool/launcher.py:parse_apply_verdict`.
- **Do not edit the `## What this is` pipeline line.** The bridge is not a pipeline stage; adding it there mis-frames it and breaks the section's scope.
- **Optional, low-risk:** the `## Reference docs` `RUNBOOK.md` bullet already reads "operational walkthroughs and recovery recipes" — no edit required; the new subsection lands under that umbrella.

## Tests

### Verification (non-code step)

This step changes no production code, so verification is doc-accuracy and link integrity, not unit tests:

- **Symbol accuracy** — every symbol the new docs name (`escalate_to_split`, `EscalateResult`, the five `outcome` values, `structural-split`, `BLOCKED-STRUCTURAL`, `STRUCTURAL_SOURCES`, `is_structural`, `triage_reason`, `emit_triage_summary`, `_emit_split_recommendations`, `_dispatch_structural_escalation`, `create_plan`, `generate_detail`, `parse_apply_verdict`) resolves to a real symbol at HEAD after steps 1–8 land. Grep each before merge.
- **Invariant fidelity** — the documented apply-vs-recommend rule matches `escalate_to_split`'s landed outcome ladder (apply only on safe + `allow_split` + interactive confirm; recommend otherwise; default path spends no Claude).
- **No broken intra-doc anchors** — the new RUNBOOK subsection's cross-link to `### When repeated audit/apply doesn't converge — re-decompose, don't keep patching` uses that heading's exact GitHub slug; the reframed sentence reads correctly in place.
- **CLAUDE.md placement** — the new paragraph sits after **Correctness gates** and before **Exit-code convention:**, and `## What this is` is unchanged.
- **No stale forward-looking claim** — `RUNBOOK.md` no longer describes the auto-escalation as unimplemented future work (the BACKLOG #57 "proposes to surface automatically" phrasing is gone or reframed to "has landed").
- **Full suite stays green** — `uv run pytest -m "not integration" tests/ -q` is unaffected (no code touched); run it once to confirm no doc-fixture or doc-drift guard trips.

## Acceptance criteria

- `RUNBOOK.md` contains a new `###` subsection under `## Workflow: drive an authoring task to convergence (--iterate)` that names `escalate_to_split`, states the two invariants, lists the apply-vs-recommend conditions, and names the `structural-split` recommendation and `BLOCKED-STRUCTURAL` verdict.
- `RUNBOOK.md`'s `### When repeated audit/apply doesn't converge — re-decompose, don't keep patching` no longer calls the auto-escalation future/proposed; it points at the landed bridge for the localized one-step split.
- `CLAUDE.md`'s `## Architecture` gains exactly one bolded paragraph for the bridge, placed after **Correctness gates** and before **Exit-code convention:**; `## What this is` is unchanged.
- Every code symbol cited in the new docs exists at HEAD (grep-verifiable) once steps 1–8 are merged.
- `uv run pytest -m "not integration" tests/ -q` passes (no production code changed).
- No `## Table of contents` edit in `RUNBOOK.md` (the new content is a `###`, not a `##` workflow).

## References

- `plan_tool/cli/authoring.py` (the `--split` flag wiring) — confirm the `--split` opt-in flag wording the RUNBOOK subsection references matches the parser's actual flag/default; `docs/cli/` carries the generated reference.
- `CLAUDE.md` (the **Exit-code convention** line) — the in-repo source for the exit-code convention the docs restate (the bridge surfaces recommendations without flipping the rc).

## Deferred

- Updating `README.md` / `integrations/claude/SKILL.md` to mention the bridge — out of this step's `files:` scope; route to a follow-up docs step or reconcile if those surfaces need it.
- Regenerating `docs/cli/` flag reference for any new `--split` wiring — owned by the CLI-flag steps and the `python -m plan_tool.cli_reference --write` drift guard, not this docs step.
- `PLAN_FORMAT.md` / `DETAIL_FORMAT.md` edits — the bridge adds no frontmatter or detail-schema field, so neither needs changes here.
- Documenting the known mid-walk stale-rec gap in the interactive review walk (the walk does not re-collect after a bridge-applied split) — tracked in step 8's Deferred; mention it in the RUNBOOK subsection only if it proves noisy in practice.
