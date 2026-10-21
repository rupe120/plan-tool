> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Prompt Budget Advisory
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add prompt_budget.py leaf with the byte-to-token estimate and the color-gated
    advisory warning
  creates:
  - plan_tool/prompt_budget.py
  - tests/test_prompt_budget.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/prompt-budget-advisory/01-prompt-budget-py-leaf-byte-token.md
  status: done
- id: 2
  title: Add record_prompt_budget telemetry recorder and document its event shape
    in DATA_CONTRACT.md
  files:
  - plan_tool/telemetry.py
  - DATA_CONTRACT.md
  - tests/test_telemetry.py
  - tests/test_data_contract.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/prompt-budget-advisory/02-record-prompt-budget-telemetry-recorder.md
  status: done
- id: 3
  title: Warn on prompt budget in generate_detail and print the breakdown on detail
    --dry-run
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/prompt-budget-advisory/03-warn-on-prompt-budget-generate-detail.md
  status: done
- id: 4
  title: Warn on prompt budget in create_plan across the distill, steps, and synthesis
    phases
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/prompt-budget-advisory/04-warn-on-prompt-budget-create-plan.md
  status: done
- id: 5
  title: Warn on prompt budget in audit_plan_until_stable and render_plan_audit_prompt
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: low
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/prompt-budget-advisory/05-warn-on-prompt-budget-audit-plan-until.md
  status: done
- id: 6
  title: Warn on prompt budget in run_step, reusing _streaming_prompt_bytes for the
    total
  files:
  - plan_tool/launcher.py
  - tests/test_launcher.py
  complexity: low
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/prompt-budget-advisory/06-warn-on-prompt-budget-run-step-reusing.md
  status: done
- id: 7
  title: Add the total-bytes backstop in shell.claude_invoke
  files:
  - plan_tool/shell.py
  - tests/test_shell.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/prompt-budget-advisory/07-total-bytes-backstop-shell-claude.md
  status: done
- id: 8
  title: 'Document the prompt-budget advisory in RUNBOOK.md and reconcile BACKLOG.md
    #95'
  files:
  - RUNBOOK.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 3
  - 4
  - 5
  - 6
  - 7
  detail: docs/implementation-plans/plan-details/prompt-budget-advisory/08-document-prompt-budget-advisory-runbook.md
  status: done
---
# Prompt Budget Advisory

## Overview

Add a **pre-send, advisory-only** prompt-budget check. After each `render_*_prompt` assembles a prompt and *before* the invoker fires, estimate the total prompt size against a conservative model context-window budget and emit a warning when headroom is tight — with a per-block breakdown showing which sections dominate and runnable structural remedies (`--step`, distill/split, `scope-out`, lower audit `--max-passes`, etc.). It never hard-blocks the invoke, never changes rc, and warnings are `color_enabled`-gated. Same discipline as the `convergence` diagnostic and today's post-failure `CONTEXT_OVERFLOW` hints: surface unconditionally, mutate nothing. Sourced from BACKLOG.md #95, which the plan must reconcile when the work ships.

## Problem statement

The tool already classifies `CONTEXT_OVERFLOW` *after* a call fails (`claude_errors.py`, propagated through `backend.py` / `shell.py` / `launcher.py`) and caps individual chunks (4 KB/file embed, lessons-file cap, fetch caps), but there is **no pre-send check that the *assembled* prompt fits**. Consequences:

- Operators discover overflow only **after burning a call** — the failure is reactive, at the point where a structural remedy is most expensive to reach.
- `prompt_bytes` is already computed and logged on many paths (`shell.py`, `run_log.py`, `backend.py:prompt_bytes`, `launcher._streaming_prompt_bytes`), but it is **accounting, not a safeguard** — nothing compares it to a budget.
- `model_specs.py` already carries `context_window` (from models.dev, line ~70 / ~151) for synthesized backends but **does not use it for budgeting** — and this plan does not wire it in either: the advisory judges against a fixed default window and per-model window resolution is wholly deferred (see Deferred).

## Architecture

### New stdlib-only leaf `plan_tool/prompt_budget.py`

Cycle-free, first-party-import-free where possible (telemetry-style leaf posture so any module can call it). Public surface:

- `estimate_prompt_budget(total_bytes, *, context_window=None, blocks=None) -> PromptBudget` — conservative token estimate (`ceil(bytes / 3.5)`), headroom ratio against `context_window` (default a ~200K-class window when unknown), an advisory level (`ok` / `warn` / `high`), and the optional per-block breakdown.
- `maybe_warn_prompt_budget(...)` — formats and emits the advisory (to stderr, `color_enabled`-gated) when level is `warn`/`high`; returns the `PromptBudget` so callers can also record telemetry. No-op / returns `ok` silently otherwise.

Advisory thresholds (start conservative to avoid fatigue): **`warn`** below ~40% headroom, **`high`** below ~15%. Thresholds are named constants so #72 telemetry can retune them later. The warning body lists the dominant blocks and the runnable structural remedies relevant to the calling surface.

**The `~200K-class default window is a coarse stand-in, and this plan accepts it as the operating point.** Judging every prompt against a fixed 200K window systematically mis-verdicts any backend whose real window differs: a ~1M-window large-context Claude makes a comfortably-fitting 250K-token prompt show negative headroom and fire a false `high` (feeding the advisory-fatigue risk in Risks), while a sub-200K window under-warns and misses real overflow — a real gap for the `codex` and `cursor` backends whose windows can differ from 200K. This plan accepts that residual for now: every hook leaves `context_window` unresolved, so the advisory always judges against `DEFAULT_CONTEXT_WINDOW`, and **per-model window resolution — including reading the `context_window` `model_specs.py` already carries — is wholly deferred** (see Deferred). The leaf takes a `context_window` parameter so a later plan can resolve and pass the real window without reshaping the leaf, but no wiring step in this plan does so.

### Orchestrator hooks (named-block breakdown where available)

Wire the check at the assembly points, passing named blocks so the breakdown is useful:

- `detail.py:generate_detail` — the authoring prompt (`render_detail_prompt`) only. `render_detail_quality_prompt` is a separate assembly point **not** hooked in this plan; it receives only the step-7 total-bytes backstop (see step 3's Deferred).
- `create.py:create_plan` (distill / steps / synthesis phases).
- `review.py:audit_plan_until_stable` (+ `render_plan_audit_prompt`).
- `launcher.py:run_step` (the streaming `run` path; reuse `_streaming_prompt_bytes`).

Each hook passes the assembled total (and named blocks where available) to the leaf **without resolving a per-model `context_window`** — it leaves `context_window` unset, so the leaf judges against `DEFAULT_CONTEXT_WINDOW`. Resolving `model_specs.ModelSpec.context_window` for the active backend/model is deferred (see Deferred).

**Generic backstop** in `shell.py:claude_invoke` (total bytes only) so a call that doesn't pass named blocks still gets the overflow-headroom check. The backstop **always fires**: because `shell.claude_invoke` is the single seam all backends flow through (via `get_active_backend()`), the named-block senders (`generate_detail`, `create_plan`, `audit_plan_until_stable`) also hit it, so a named-block send emits the backstop advisory (and a `shell-backstop` telemetry event) **in addition to** its named-block one. This double-fire is an **accepted residual** of this plan; suppressing it needs real design and is deferred to **BACKLOG #99** (see Risks and Deferred).

### Dry-run visibility

`detail --dry-run` (and any sibling dry-run path that renders without invoking) prints the budget breakdown so an operator can inspect headroom before spending a call.

### #72 telemetry extension

Add a `record_prompt_budget` recorder to `telemetry.py` (mirroring the existing `record_*` seams) capturing `phase`, `total_bytes`, `advisory`, and optional `blocks`. Best-effort / swallow-all-errors like the rest of `telemetry.py`. This lets a later analysis pass link the advisory to actual `CONTEXT_OVERFLOW` outcomes for threshold tuning. Document the event shape in `DATA_CONTRACT.md` if it stabilizes (the drift guard covers it).

## References

- [Anthropic — Token counting](https://docs.anthropic.com/en/docs/build-with-claude/token-counting) — Official guide to how Claude counts prompt tokens, which grounds the plan's byte/token heuristic and its comparison against a context-window budget.
- [Anthropic API — Count Message tokens](https://docs.anthropic.com/en/api/messages-count-tokens) — Primary API reference for the count-tokens endpoint, useful for calibrating the conservative ceil(bytes / 3.5) estimate against real token counts.
- [Anthropic — Models overview (context windows)](https://docs.anthropic.com/en/docs/about-claude/models/overview) — Authoritative per-model context-window sizes, the basis for the ~200K-class default window and headroom-ratio thresholds.
- [models.dev](https://models.dev/) — The open model-spec catalog that model_specs.py already sources context_window from, so the budget check stays consistent with existing synthesized-backend data.
- [Python — math.ceil / math module](https://docs.python.org/3/library/math.html) — Stdlib reference for math.ceil, used directly in the ceil(bytes / 3.5) token estimate in the new prompt_budget leaf.
- [Python — io.IOBase.isatty / sys streams](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — Reference for TTY detection behind color_enabled gating, ensuring the advisory prints plain output on a pipe/non-TTY.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Tokenizer dependency** — the estimate stays a byte/char heuristic, no new dependency.
- **Hard pre-send refusal** — never block the invoke; advisory only.
- **New truncation caps / raising the 4 KB embed** — that is #97 (symbol-aware excerpts); this plan only *measures and warns*, it does not change what gets embedded.
- **Capping `run`'s uncapped full-detail embed** — noted as a possible follow-up in #95; file it to `BACKLOG.md` if the advisory surfaces it often, do not fold it in here.

## Risks

- **False-positive warnings** if the byte/token heuristic is too aggressive. Severity: medium (advisory fatigue → operators ignore it). Mitigation: start conservative (`warn` below ~40% headroom, `high` below ~15%); make thresholds named constants so #72 telemetry can retune them later. **Caveat — one false-positive driver no threshold can fix:** judging every prompt against the fixed `DEFAULT_CONTEXT_WINDOW` (200K) makes a large-context (~1M) Claude fire `high` on a prompt that fits comfortably, and no threshold value corrects a 200K yardstick measuring a 1M-window prompt. That residual's only real fix is per-model window resolution, which this plan leaves **wholly deferred** (see Architecture and Deferred); it is accepted for now.
- **Advisory fatigue from an over-low `ok` threshold.** Severity: medium. Mitigation: only `warn`/`high` emit; `ok` is silent.
- **Breakdown only as good as the blocks passed.** Severity: low. Mitigation: the generic backstop still gives a total-bytes headroom check when named blocks are absent; wiring steps pass blocks where the assembly is structured.
- **Double-warning + double telemetry on the shared seam** (a named-block send also hits the step-7 backstop). Severity: low (one extra advisory line per send, no crash, no rc change) — but the backstop also records a second, blockless `phase="shell-backstop"` telemetry event per named-block send, double-counting the #72 distribution. This plan **accepts** the double-fire rather than shipping a suppressor: a correct suppressor needs per-pass (not per-invoke) scoping for the audit loop and a per-invoke correlation id so #72 can dedupe the backstop record against its named-phase record — real design deferred to **BACKLOG #99**.

## Testing

Unit-test the `plan_tool/prompt_budget.py` leaf in isolation: cover the `ok` / `warn` / `high` boundaries and the token/headroom heuristic (`ceil(bytes / 3.5)`, headroom ratio against `context_window`, default-window fallback). Verify `maybe_warn_prompt_budget` emits only at `warn`/`high`, stays silent at `ok`, and is `color_enabled`-gated (plain on a pipe/non-TTY). Test that the advisory never changes rc and never blocks the invoke. Confirm `telemetry.record_prompt_budget` records `phase` / `total_bytes` / `advisory` (+ optional `blocks`) and swallows all errors. If the telemetry event shape stabilizes, ensure the `DATA_CONTRACT.md` drift guard passes.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- A new `plan_tool/prompt_budget.py` leaf exposes `estimate_prompt_budget` and `maybe_warn_prompt_budget`, is import-cycle-free, and is unit-tested for the `ok` / `warn` / `high` boundaries and the token/headroom heuristic.
- `generate_detail`, `create_plan`, `audit_plan_until_stable`, and `run_step` emit the advisory (with a per-block breakdown) when headroom is tight; the `shell.claude_invoke` backstop always fires and covers callers that pass no blocks. Because it is the shared seam, the named-block senders also hit the backstop — an accepted double-fire; suppression is deferred to **BACKLOG #99** (see Deferred).
- The advisory **never changes rc** and **never blocks the invoke** (exit-code convention; surface-unconditionally-mutate-nothing discipline). Warnings are `color_enabled`-gated (plain on a pipe/non-TTY).
- `detail --dry-run` prints the budget breakdown without invoking.
- `telemetry.record_prompt_budget` records `phase` / `total_bytes` / `advisory` (+ optional `blocks`), swallows all errors, and — if the event shape is stable — is documented in `DATA_CONTRACT.md` and passes the drift guard.
- **BACKLOG.md #95 is reconciled** (removed, or marked plan-authored with any deferred remainder split out) as the plan's final step; `RUNBOOK.md` documents the advisory.

## Deferred

- Outcome-linkage of the advisory to actual `CONTEXT_OVERFLOW` failures and a recommend-tuning surface — belongs with #72 phases 2–3, not here.
- Per-model window resolution — including reading `model_specs.ModelSpec.context_window` for the active backend/model, and any richer per-`--backend` catalog lookup beyond it. Every hook in this plan leaves `context_window` unresolved, so the advisory always judges against `DEFAULT_CONTEXT_WINDOW`; resolving the real window (and passing it into the leaf, which already accepts it) is a follow-up. The headroom verdict is therefore coarse for backends whose real window differs from 200K (e.g. `codex`, `cursor`).
- Capping `run`'s full-detail embed (route to `BACKLOG.md` if it recurs).
- Symbol-aware / budget-bounded *excerpting* of embedded files — that is #97.
- **Double-warn / double-telemetry suppression on the shared seam** — the step-7 backstop and the named-block hooks both fire on a named-block send (one extra advisory line + a blockless `shell-backstop` telemetry record per send). This plan accepts that residual; a correct suppressor needs per-pass scoping for the audit loop plus a per-invoke correlation id for #72 dedup, so it is filed as **BACKLOG #99** to be designed separately.
