---
source: from-existing-body-synthesis.md
---
# Synthesize plan body from --from-existing seed via a Claude round-trip

## Overview

`plan-tool create --from-existing` is meant to take an existing seed, conceptualize it via Claude, and develop a plan from it. Today the step decomposition and references round-trips do that — but the body sections (Overview, Problem statement, Architecture, Out of scope, Risks, Testing, Acceptance criteria, Deferred) are populated by a mechanical regex H2-name match, falling back to `_(TODO)_` when names don't line up.

This plan adds a third Claude round-trip (`create-body-sections`) that synthesizes each canonical body section from the full seed prose regardless of how the seed is structured. H2-extraction stays as a deterministic fallback so canonical seeds keep working. Precedence at render time: synthesized (non-null) → H2-extracted → `_(TODO)_`. Empty-section semantics: synthesis returns `null` rather than inventing content. A canonical-seed optimization detects when every section already has a matching non-empty H2 and skips the synthesis call entirely.

## Steps

### 1. Lock design decisions and write the synthesis prompt

Files:
- `prompts/synthesize-body.md`

### 2. Add propose_body_sections helper in create.py

Files:
- `plan_tool/create.py`

Depends on: 1

### 3. Wire the third round-trip into create_plan() with canonical-seed optimization

Files:
- `plan_tool/create.py`

Depends on: 2

### 4. Update _render_plan_body precedence to prefer synthesized over H2-extracted

Files:
- `plan_tool/create.py`

Depends on: 3

### 5. Add --no-synthesize-body CLI flag

Files:
- `plan_tool/cli.py`
- `plan_tool/create.py`

Depends on: 4

### 6. Update _MAX_EXISTING_BYTES comment with plan and cache-TTL motivation

Files:
- `plan_tool/create.py`

Depends on: 5

### 7. Add unit tests for propose_body_sections

Files:
- `tests/test_create.py`

Depends on: 6

### 8. Add integration tests for free-form, canonical, and --no-synthesize-body flows

Files:
- `tests/test_create.py`

Depends on: 7

### 9. Update README and RUNBOOK to describe seed conceptualization and escape hatch

Files:
- `README.md`
- `RUNBOOK.md`

Depends on: 8

### 10. Capture lessons entry about non-canonical seed names and canonical-skip optimization

Files:
- `lessons/general.md`

Depends on: 9

## Acceptance criteria

- A seed with non-canonical H2 names drives `plan-tool create --from-existing` to produce a plan whose canonical body sections are populated with content synthesized from the seed prose — no `_(TODO)_` for sections that had derivable source content.
- A canonical seed (every `PLAN_BODY_SECTIONS` H2 present and non-empty) drives `create --from-existing` without invoking the synthesis round-trip; the resulting plan body is byte-identical to a run on the same seed with `--no-synthesize-body`.
- `--no-synthesize-body` skips the synthesis round-trip and falls back to H2-extraction-only behavior — regression test pins this against current pre-this-plan output bytes.
- When the seed has no risk-shaped content, synthesis returns `null` for `## Risks` and the plan renders `_(TODO)_` — unit test asserts Claude is not asked to invent.
- A malformed-JSON response from Claude triggers exactly one retry; if both attempts fail, the plan still writes with `_(TODO)_` body sections and exits 0.
- A `runs` log entry records the synthesis-retry event; `plan-tool runs show <slug>` surfaces synthesis quality regressions across runs.
- The `_MAX_EXISTING_BYTES = 16384` site at create.py:192 carries a code comment naming this plan and the prompt-cache TTL motivation.
- Integration tests pass for both fixture shapes (canonical, free-form) and the `--no-synthesize-body` combination, end-to-end through `create_plan()`.
