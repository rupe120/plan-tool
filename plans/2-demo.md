---
format_version: 1
title: Demo
intent: Provide an isolated minimal plan fixture for inspecting plan structure.
status: planning
priority: medium
steps:
- id: 1
  title: first
  intent: Provide a stable placeholder target for fixture inspection.
  complexity: low
  change_type: non-code
  status: current
---
# Demo

## Overview

This is a minimal plan fixture at `plans/2-demo.md`, separate from the
[dark-mode reading example](../docs/demos/dark-mode-example.md). It provides a
stable single-step structure for inspection, not a feature implementation plan.

## Problem statement

Contributors need a small plan they can parse and round-trip without changing
in-flight work. This fixture supplies that isolated input.

## Architecture

The YAML frontmatter declares one low-complexity step, `first`, with status
`current`. The plan remains `planning`. The parser reads the frontmatter;
the body explains the fixture's boundaries. No detail file or runtime component
belongs to this fixture.

## References

- [Plan format](../PLAN_FORMAT.md) — frontmatter and body contract.
- [Parser](../plan_tool/parser.py) — `parse_plan`, `parse_plan_text` and `render_plan_text`.
- [CLI entry point](../plan_tool/cli/app.py) — command dispatch.
- [Testing guide](../TESTING.md) — repository test conventions.
- [Planning demo](../docs/demos/planning-demo.md) — assistant-led dark-mode walkthrough.

## Steps

See the single placeholder in the frontmatter. Inspect it; do not execute it.

## Out of scope

- Feature implementation, application code, infrastructure and deployment.
- Detail authoring or execution of the placeholder step.
- Additional steps or promotion beyond `planning`; real work needs a separate plan.
- Live model authoring, audit convergence evidence and remote publication.

## Risks

- Readers may mistake this fixture for runnable work. Keep its placeholder
  identity and planning status explicit; use a separately scoped plan for execution.
- A parser round-trip can confirm structure but cannot establish design quality
  or audit convergence. Review those properties in a real plan's saved reports.

## Testing

Use `plan_tool/parser.py:parse_plan` to load this file, then `render_plan_text`
and `parse_plan_text` to verify serialization preserves its identity and body.
Existing parser coverage lives in `tests/test_parser.py`; run it with
`uv run pytest tests/test_parser.py -q` when checking parser behavior.
No feature tests, backend calls or new detail files are required for inspection.

## Acceptance criteria

- The file parses and its rendered form reparses with the same plan fields and body.
- The plan declares `format_version: 1`, title `Demo` and status `planning`.
- Exactly one step has id `1`, title `first`, complexity `low` and status `current`.
- The step declares no files, creates or detail artifact; inspection adds none.
- References resolve within this repository and the body describes only fixture work.

## Deferred

No follow-up workload is assigned to this fixture. Author a separate seed for real work.
