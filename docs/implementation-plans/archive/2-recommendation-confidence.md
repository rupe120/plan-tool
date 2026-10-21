> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Recommendation Confidence
intent: Give readers a visible, durable indication of the deterministic evidence support
  behind a recommendation without conflating confidence with severity or changing
  finding behavior.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
steps:
- id: 1
  title: Give every Recommendation a conservative confidence without losing legacy
    evidence
  intent: New findings are `limited` unless a directly verified predicate proves `supported`;
    legacy saved and cached findings retain unknown evidence before any reader sees
    them.
  files:
  - plan_tool/review.py
  - plan_tool/granularity.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/review_persistence.py
  - plan_tool/purity_cache.py
  - DATA_CONTRACT.md
  - tests/test_review.py
  - tests/test_granularity.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_review_persistence.py
  - tests/test_purity_cache.py
  - tests/test_data_contract.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/recommendation-confidence/01-give-every-new-recommendation.md
  status: done
- id: 2
  title: Render confidence in user and LLM finding contexts
  intent: A human reader or LLM follow-up prompt sees the same display-only evidence-support
    label in finding output without opening a JSON sidecar; an LLM still follows the
    finding's supplied remedy and verdict regardless of that label.
  files:
  - plan_tool/review.py
  - plan_tool/review_walk.py
  - plan_tool/create.py
  - plan_tool/cli/review_cmd.py
  - plan_tool/cli/review_actions.py
  - plan_tool/completeness_report.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_apply_parallel.py
  - plan_tool/cli/reconcile.py
  - plan_tool/detail.py
  - plan_tool/cli/inspect.py
  - plan_tool/cli/data_contract_cmd.py
  - plan_tool/convergence_diagnosis.py
  - plan_tool/launcher.py
  - plan_tool/prompts/apply-finding.md
  - plan_tool/prompts/extract-lessons-review.md
  - tests/test_review.py
  - tests/test_review_walk.py
  - tests/test_create.py
  - tests/test_lessons.py
  - tests/cli/test_review_actions.py
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_completeness_apply_parallel.py
  - tests/cli/test_reconcile_engine.py
  - tests/cli/test_inspect_cmds.py
  - tests/cli/test_data_contract_cmd.py
  - tests/test_convergence_diagnosis.py
  - tests/test_detail.py
  - tests/test_launcher.py
  - tests/cli/test_review_cmds.py
  - tests/test_cli.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: supplies the classified and legacy-safe stored confidence value.
  detail: docs/implementation-plans/plan-details/recommendation-confidence/02-render-confidence-in-finding-contexts.md
  status: done
---
# Recommendation Confidence

## Overview

Add an optional, visible confidence signal to Recommendation findings, separate from
severity. New findings receive the conservative deterministic `supported` or
`limited` label; a legacy absent value renders as `unknown`. The signal never comes
from LLM self-scoring or makes a calibration claim. Saved reviews preserve it, while
user-facing finding output and direct LLM finding prompts render it.

## Problem statement

Recommendation findings do not expose a confidence signal distinct from severity.
Readers therefore cannot distinguish a deterministically supported finding from a
model-originated or otherwise indirectly supported one across persisted and rendered
outputs.

## Architecture

Extend Recommendation findings with a confidence field whose new-value vocabulary is
`supported` or `limited`. New construction defaults to `limited`, so every current and
future producer is covered without source-name inference. The only initial
`supported` predicates are the direct file-state check (`file-check`), dependency-graph
check (`deps`), and data-contract validator (`data-contract`): each reproduces its
conclusion from the current repository or parsed plan. Every other producer, including
model-derived, heuristic, cached, structural, and unclassified findings, remains
`limited`. An anchor slug or a source name by itself is not evidence support. The
classification does not alter a finding's id, severity, selection, application,
blocking, or convergence behavior. It never asks a model to self-score or presents
either label as calibrated probability.

Carry the optional field through saved reviews, completeness reports, reconcile output,
and CLI output. A legacy saved finding without the field loads as `None` and renders as
`unknown`; on an ordinary sidecar rewrite it deliberately normalizes to JSON `null` and
remains unknown. The loader accepts only `supported`, `limited`, JSON `null`, or an
absent field; any other persisted value fails closed rather than reaching a reader.
The same normalization and validation applies to cached purity findings.
User-facing Recommendation renderings and direct LLM prompts that act on a
Recommendation preserve the stored value and never recompute it from a source name.
In a direct LLM prompt, confidence is display-only context: the model must retain the
finding's supplied remedy and verdict whether it is `supported`, `limited`, or
`unknown`, and cannot use the label to skip, narrow, defer, reprioritize, or otherwise
change the requested work. Lesson extraction may use the label only to describe the
evidence support of a synthesized lesson; it cannot weaken or reclassify the source
finding.

## Input

The plan consumes `plan_tool/review.py:Recommendation`, whose default covers every
constructor in `plan_tool/review.py`, `plan_tool/granularity.py`,
`plan_tool/detail.py`, `plan_tool/launcher.py`, and CLI producers. The sidecar loader
in `plan_tool/review_persistence.py` and cache loader in `plan_tool/purity_cache.py`
are the exceptions to the new-construction default: they preserve the semantic
distinction between current `limited` and legacy unknown. `DATA_CONTRACT.md` owns the
persisted shape; existing sidecars and cache entries without the field and with JSON
`null` are the compatibility input.

## References

- [dataclasses — Data Classes — Python 3.13 documentationhttps: — Documents field defaults, generated constructors, and asdict serialization needed for an additive backward-compatible Recommendation field.
- [typing — Support for type hints — Python 3.13 documentationhttps: — Clarifies Optional and None semantics so absent legacy confidence is modeled separately from a required constructor argument.
- [json — JSON encoder and decoder — Python 3.13 documentationhttps: — Covers encoding, decoding, and null conversion for saved reviews, completeness sidecars, and JSON CLI output.
- [RFC 8259 — The JavaScript Object Notation Data Interchange Formathttps: — Defines interoperable JSON objects and null values relevant to evolving persisted finding records.
- [How to parametrize fixtures and test functions — pytest documentationhttps: — Shows how to exercise confidence-present, confidence-absent, and legacy-record cases through parametrized tests.
- [How to capture stdout/stderr output — pytest documentationhttps: — Documents capsys and related fixtures for asserting confidence rendering across CLI and reconcile output.
- [How to use temporary directories and files in tests — pytest documentationhttps: — Documents tmp_path fixtures for isolated persistence, round-trip, and legacy-loading tests.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Confidence-based gates, exit codes, apply behavior, blocking behavior, or convergence behavior; confidence remains informational.

## Risks

- Legacy saved findings could appear falsely certain if absence is interpreted as a confidence value; they must load as unknown or absent.
- An invalid persisted label could be rendered as authority it never earned; the loader
  must reject it before any reader sees it.

## Testing

Add focused unit tests covering the default `limited` path; the three named
`supported` predicates; model, heuristic, cached, and structural `limited` paths;
persistence, purity-cache, and legacy normalization; invalid-value rejection; and
stored-value preservation and rendering in user-facing finding output and direct LLM
finding prompts, including the display-only rule that preserves each supplied remedy
and verdict. Use
integration tests only where cross-module or CLI wiring cannot be verified through one
component in isolation. Existing finding identity, selection, and severity behavior
must continue to pass unchanged.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- Recommendation findings carry a visible confidence signal distinct from severity.
- Every new finding defaults to `limited`; only the direct `file-check`, `deps`, and
  `data-contract` predicates explicitly emit `supported`. An anchor or source name
  alone never produces `supported`.
- Saved reviews, completeness reports, reconcile output, detail progress, validation,
  convergence history, review CLI output, and direct LLM finding prompts render the
  same confidence label.
- Direct LLM prompts treat the label as display-only context: they preserve the
  finding's supplied remedy and verdict and do not skip, narrow, defer, reprioritize,
  or otherwise change requested work because of confidence.
- Legacy saved findings without confidence load as `None`, render as `unknown`, and
  normalize to JSON `null` if a sidecar or purity-cache rewrite persists them; invalid
  persisted labels are rejected.
- Carried findings and convergence-history projections preserve and render the stored
  confidence label without recomputing it.
- Existing finding id, selection, severity, application, blocking, and convergence
  behavior remains unchanged.
- The data contract documents the optional confidence field.

## Deferred

- Unifying annotate Section confidence — defer to separate work because annotate uses a distinct confidence contract.
- Benchmark calibration — defer to `quality-bench-01` (BACKLOG #216), which
  first records deterministic corpus noise floors. A later proposal may use
  those floors only if they make its claimed effect measurable; this plan makes
  no calibration, judgment, gate, or behavior claim.
- Scope-guard handoffs and split-criteria diagnostics — defer unless a future consumer
  needs to compare confidence on those derived internal records; they are not
  Recommendation finding output or direct LLM finding prompts.
