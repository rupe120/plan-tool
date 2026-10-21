> **Replaced**: this file has been superseded by `docs/implementation-plans/2-symbol-aware-prompt-excerpts.md`.
> Preserved here for history; do not edit.

# Plan seed: symbol-aware prompt file excerpts + per-step embed budget

This file is a `plan-tool create` input. Use it via:

```
plan-tool create symbol-aware-prompt-excerpts --from-existing plan-seeds/symbol-aware-prompt-excerpts.md --iterate
```

It is **not** itself a plan. `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Scope:** replace head-only prompt file previews with deterministic,
> symbol-aware excerpts and a per-step byte budget. This is the design-first
> follow-up after the review/reconcile Read/Grep grounding contract shipped.

---

## Overview

Build a shared excerpting layer for prompt file embeddings so the inline source
context shown to `detail`, `detail-quality`, `review`/reconcile, Jira export,
annotate, and audit bundles is relevant and bounded. The current pattern clips
each declared file to the first few kilobytes. That prevents prompt blowups, but
it often embeds imports and headers while missing the functions, classes, or
constants the step actually touches.

The replacement should:

- Use one stdlib-only prompt excerpt helper instead of repeated head-slicing
  code in each surface.
- Allocate a per-step byte budget across all declared files.
- Prefer header/import context plus windows around symbols likely relevant to
  the step.
- Preserve explicit truncation markers and instructions to Read/Grep the full
  file when inline context is incomplete.
- Keep surface-specific policy where needed: authoring/audit surfaces can use
  richer excerpts, while Jira/export stays conservative.

## Problem Statement

Prompt file embedding currently relies on blind head clipping in multiple
places:

- `plan_tool/detail.py:_format_files_contents_block`
- `plan_tool/review.py:render_review_prompt`
- `plan_tool/jira.py:_render_step_files_contents`
- `plan_tool/annotate.py:_bound_for_block`
- `plan_tool/review.py:_format_audit_detail_bundle` and related audit-detail
  byte caps

The cap exists for a good reason: full contents of N declared files can exceed
the model context window. But head-only previews have a serious grounding
failure mode. Large files often place the important implementation below the
first 4 KB, so the inline context can look substantial while hiding the code a
step actually needs. The tool now tells review/reconcile to Read/Grep at HEAD,
and detail/audit prompts already have similar grounding rules, but the inline
preview should still be a useful orientation layer, not a misleading header
dump.

## Architecture

### Shared Excerpt Helper

Add a stdlib-only leaf module, likely `plan_tool/prompt_excerpt.py`, with a
small contract such as:

```python
ExcerptResult = dataclass(text: str, truncated: bool, strategy: str)

build_prompt_excerpt(
    path: Path,
    body: str,
    *,
    step_context: PromptExcerptContext,
    budget_bytes: int,
) -> ExcerptResult
```

The exact names are flexible, but the helper should not import CLI modules,
orchestrators, or prompt renderers. Prompt renderers depend on it; it does not
depend on them.

### Excerpt Strategy

Use deterministic selection only:

- Always include a small header region: module docstring/imports/first logical
  section, bounded to roughly 512-1024 bytes.
- Derive cheap candidate symbols from the step title, declared file basenames,
  existing review heuristics such as `_derive_symbols`, and tokens already used
  by `heuristic_already_done`.
- Search the file body for candidate symbols with standard string/regex logic.
- Add windows around matching lines, with enough context to identify the
  surrounding function/class/constant when possible.
- Fill remaining budget with head or tail context only after symbol windows are
  selected.
- Never exceed the per-file budget slice or the total per-step budget.

Avoid Claude in excerpt selection. This is a deterministic prompt construction
primitive, not a semantic audit.

### Budget Policy

Introduce a per-step embed budget across all declared files. A reasonable first
default is 32-48 KB per step, but the plan should choose a value and explain it.
Each file should get a floor so one large file does not starve smaller siblings,
and a ceiling so one file cannot consume the entire prompt.

Keep per-surface behavior explicit:

| Surface | Tools mandated? | Inline embed role |
| --- | --- | --- |
| `detail` / `detail-quality` | yes | orient + symbol anchors |
| `plan-audit` / completeness | yes | bundle summary |
| `review` / reconcile | yes | preview until Read |
| `jira` | no | structural preview; keep conservative |
| `annotate` | partial | grounding preview; preserve low-confidence label |
| `run` detail loading | N/A | currently full detail; document separately |

### Truncation and Operator Signal

Every excerpt that omits content must say so in the prompt. Prefer a marker such
as:

```
_(truncated; Read/Grep for full file)_
```

If excerpting drops most of a declared file or a symbol hit lies outside the
kept text, preserve an explicit signal. This should compose with the future
prompt-budget advisory work rather than hiding clipping.

## Suggested Step Decomposition

Use small, single-concern steps. Suggested shape:

1. **Design and test the excerpt helper contract.** Add `prompt_excerpt.py`,
   `PromptExcerptContext`, and fixture tests for header inclusion, deep symbol
   hits, no-hit fallback, truncation markers, and byte-budget enforcement.
2. **Migrate review/reconcile embedding first.** Replace the file/detail preview
   construction in `render_review_prompt` with the helper. Keep the newly shipped
   Read/Grep contract intact and add tests for a symbol below the old head cut.
3. **Migrate detail and detail-quality file embeddings.** Route
   `_format_files_contents_block` through the helper without weakening existing
   grounding, path, and detail-quality tests.
4. **Migrate audit detail bundles.** Apply the same excerpt policy to
   completeness/plan-audit bundles, with tests for multi-step budget allocation
   and repeated files.
5. **Migrate Jira and annotate conservatively.** Keep Jira/export output bounded
   and structural; preserve annotate's explicit low-confidence/truncation
   posture.
6. **Document the policy and clean up duplicated caps.** Add the surface policy
   table to `RUNBOOK.md` or an appropriate module docstring, remove dead
   head-slicing helpers, and ensure constants are named by role rather than
   copied magic values.

## Out of Scope

- Removing all prompt caps or embedding whole files by default.
- Tokenizer dependencies; byte-based budgeting is acceptable for this slice.
- Hard-blocking invocation when a prompt is large. That belongs to the
  prompt-budget advisory work.
- Changing the semantic review prompts beyond the truncation/excerpt wording
  needed to describe the new preview.
- Altering `run` execution semantics for full detail loading, except to document
  the asymmetry or leave a follow-up.

## Risks

- **Excerpt misses the relevant code.** Mitigate with symbol-window tests using
  real-shaped large files and by preserving Read/Grep guidance on tool-using
  surfaces.
- **Budget policy grows prompts too much.** Mitigate with per-step totals,
  per-file ceilings, and conservative defaults. Coordinate with prompt-budget
  advisory work if it lands first.
- **One surface needs a different policy.** Mitigate with an explicit
  surface-policy enum/config rather than ad hoc call-site conditionals.
- **Shared helper creates import cycles.** Keep `prompt_excerpt.py` a leaf below
  renderers and avoid imports from `review.py`, `detail.py`, or CLI modules.
- **Snapshot tests churn.** Prefer behavior-focused assertions around markers,
  symbol inclusion, and omitted deep filler instead of pinning whole prompts.

## Testing

Add focused tests before broad migration:

- A large file with imports at the top and the relevant symbol well past the old
  4 KB cut includes the symbol window.
- A file with no candidate symbols falls back deterministically and marks
  truncation when clipped.
- Multiple declared files share a total per-step budget; a huge file cannot
  starve a small sibling.
- Repeated files in multi-step/audit bundles are deduplicated or bounded
  according to the chosen policy.
- Review/reconcile prompt rendering still includes the Read/Grep grounding
  contract and no longer relies on head-only content.
- Existing `detail`, `review`, `jira`, `annotate`, and completeness prompt tests
  stay green after migration.

## Acceptance Criteria

- A shared prompt excerpt helper exists and is used by at least the migrated
  prompt surfaces instead of direct `body[:N]` head clipping.
- Excerpts include header context plus symbol-centered windows when candidate
  symbols are present beyond the old head cut.
- Prompt embedding is bounded by a per-step budget and per-file floor/ceiling
  policy documented in code or `RUNBOOK.md`.
- Truncated excerpts include an explicit "Read/Grep for full file" style marker.
- `review`/reconcile, `detail`/`detail-quality`, plan-audit/completeness bundles,
  Jira, and annotate either use the shared helper or document a deliberate
  exception.
- Tests cover deep-symbol inclusion, budget starvation, no-hit fallback,
  truncation markers, and at least one migrated real prompt renderer.

## Deferred

- Full prompt-budget advisory integration and telemetry for clipping rates.
- Direct model-token accounting or tokenizer-backed budgets.
- A richer parser for language-specific symbol boundaries.
- Capping or excerpting `run`'s full detail loading.
