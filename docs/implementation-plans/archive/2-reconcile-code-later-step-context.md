> **Archived:** this completed plan moved here on 2026-08-20 after all steps reached `done`.

---
title: Reconcile Code Later Step Context
intent: '`reconcile-code --step N` reconciles only a selected DONE step with readable
  detail from one verified plan snapshot. Other DONE steps provide normalized-path
  ownership context, never a reason to remove sibling work.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add completed-step context to selected code reconciliations
  intent: Keeps completed sibling work from being treated as removable drift while
    still saving clear findings for real mismatches in the selected step.
  files:
  - plan_tool/cli/reconcile.py
  - plan_tool/launcher.py
  - plan_tool/prompts/run-reconcile.md
  - plan_tool/scope_guard.py
  - tests/test_launcher.py
  - tests/test_cli.py
  - tests/test_scope_guard.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/reconcile-code-later-step-context/01-completed-step-context-selected-code.md
  status: done
---
# Reconcile Code Later Step Context

## Overview

Update `reconcile-code --step N` so it reconciles a selected DONE step only after reading its detail from a single verified plan snapshot. Other DONE steps supply normalized-path ownership context. The command refuses before backend invocation if its target, detail, snapshot, or selected prompt size cannot establish that boundary.

## Problem statement

The selected-step reconciliation path can surface later completed work as drift for an earlier selected step. This produces removal recommendations for code owned by sibling completed steps rather than findings about the selected step itself.

## Architecture

Harden the existing selected-run context path from one parsed plan snapshot: require the selected step to be `DONE` and its detail readable, then revise its sibling ownership to use declared normalized paths outside the selected footprint. Sibling ownership has priority over the prompt's broad cross-cutting guidance. The saved report keeps its existing clean, scoped, and selected-step-drift classifications and states when sibling context informed that classification. The existing prompt-budget estimator refuses this selected call before a backend request at its existing high threshold; it does not create a global budget policy.

## Input

The selected-step path consumes one completed plan snapshot, the selected step's readable detail, and each completed step's declared paths. Path identity follows the existing scope-guard normalization rule, so equivalent raw, dotted, and creation-annotated spellings share ownership.

## References

- [Template strings — Python documentation](https://docs.python.org/3/library/string.html#template-strings) — Covers `string.Template` and `safe_substitute`, which the prompt renderer uses to inject completed-step context.
- [Models — Pydantic Documentation](https://pydantic.dev/docs/validation/latest/concepts/models/) — Explains Pydantic model field access and validation for filtering completed `Step` records safely.
- [Prompt engineering overview — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview) — Guides structured, scoped instructions for distinguishing sibling context from selected-step drift in the reconciliation prompt.
- [How to monkeypatch/mock modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Documents reversible dependency patching for focused CLI and prompt-composition tests without invoking the backend.
- [How to use temporary directories and files in tests — pytest documentation](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Covers `tmp_path` fixtures for multi-step plan, saved-report, and persistence test setups.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Weakening plan-canonical reconciliation or hiding genuine drift in the selected step.
- Changing plan steps or details to omit delivered work.
- Generic review-walk routing or unrelated reconcile behavior.
- New persistence schema, sibling-detail loading protocol, or global prompt-budget policy.

## Risks

- **Sibling context is over-broad** — High severity: completed work could suppress a genuine selected-step mismatch; scope it to sibling-owned normalized paths outside the selected footprint and retain selected-step findings.
- **Unreliable selected grounding** — High severity: a non-DONE target, unreadable selected detail, stale snapshot, or high prompt budget could make the model's boundary unreliable; refuse before backend invocation.
- **Report wording obscures ownership** — Medium severity: saved output could still imply sibling work is removable; test report language that distinguishes sibling context from selected-step drift.

## Testing

- Use focused prompt, CLI, path-normalization, and persistence/report tests with a multi-step completed-plan fixture.
- Reconcile every step of the fixture and verify later-step-only code produces no recommendation for an earlier selected step.
- Verify a deliberate mismatch in the selected step still produces a reconciliation finding.
- Verify saved report wording distinguishes sibling context from real selected-step drift.
- Verify current/pending targets, unreadable selected detail, changed plan snapshots, and high selected prompt budgets refuse before backend invocation.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- `reconcile-code --step N` accepts only a selected `DONE` step with readable detail from one verified plan snapshot.
- Sibling ownership uses normalized declared paths; equivalent path spellings do not create false selected-step drift.
- Later-step-only code produces no removal recommendation when an earlier completed step is selected.
- A deliberate mismatch in the selected step produces a reconciliation finding.
- Saved report wording distinguishes sibling context from real selected-step drift.
- Saved report wording states when sibling context informed a clean, scoped, or code-drift classification without using the plan-rooted redirect protocol.
- A changed snapshot or high selected prompt budget refuses before a backend call.
- When no selected-step drift remains, the selected-step path emits a clear clean or scoped diagnostic.

## Deferred

- Altering completed-plan semantics beyond the selected run-reconcile path is deferred.
