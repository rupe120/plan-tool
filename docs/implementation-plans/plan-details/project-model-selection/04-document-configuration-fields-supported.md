# Step 4 — Document project choices and align bundled skills

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Document the shipped selection contract and let bundled skill invocations honor project defaults. Keep recommendations for projects without configuration and explicit user overrides.

## Table of Contents

- [Why](#why) — Purpose.
- [Files](#files) — Edit footprint.
- [Implementation](#implementation) — Smallest delivery path.
- [Tests](#tests) — Evidence.
- [Acceptance criteria](#acceptance-criteria) — Completion checks.

## Why

Unconditional backend/model flags in current skill guidance bypass project choices. The operator guide and bundled routers must describe the same contract as the code.

## Files

Edit `docs/BACKENDS.md`, `docs/reference/commands.md`, `README.md`, `docs/design-plans/BACKEND_SELECTION.md`, `integrations/shared/DIRECTIVES.md`, the three bundled integration `SKILL.md` files, `tests/cli/test_skill_cmd.py`, and `BACKLOG.md`. Create no files.

## Implementation

Make `docs/BACKENDS.md` the detailed reference: show the new JSON fields, inheritance/error behavior, supported command keys/aliases from registrations, separate backend/model precedence tables, and a create/detail example without selection flags. Explain that `--backend` retains that backend's configured model defaults while `--model` overrides them. Keep top-level docs to short routes into this reference.

Keep selection policy in shared `DIRECTIVES.md`. Explicit user requests win; ordinary invocations allow project configuration to apply. Retain current model/backend recommendations as fallback guidance for unconfigured projects. Routers point to that policy instead of forcing their host integration's execution backend. Keep headless usage, commits, audit gates, and provider prerequisites intact. Sweep identifiers and wording across all declared guidance sites, including introductory claims and examples.

Update the older backend-selection proposal only where needed to distinguish shipped `default_backend`/command models from inert `default`, `aspects`, and `failover` proposals. Do not implement its routing or failover mechanisms.

After implementation and full-suite verification, reconcile overlapping backlog #254 with the shipped explicit-command design under `docs/TRACKING.md`. Do not remove it merely because this plan exists. Preserve independent copied-skill validation #525 and broader doctor spike #403. Leave governance files, installation implementation, and real installed skill copies untouched. Regenerate CLI references only if help text changes.

## Tests

Use the existing temporary-install tests to confirm all three routers and shared directives ship together, including Codex's copy default. Add only focused content assertions for the selection rule; preserve existing copy/symlink replacement tests rather than restating them here.

Check the JSON example with the real reader, compare precedence and aliases to the landed code, and verify changed links. Run affected skill/CLI tests and `uv run pytest tests/ -q -n auto`. Review the guidance for correctness and completeness after edits, then repeat the identifier/vocabulary sweep. These checks establish shipped instruction contents, not whether an assistant follows prose.

## Acceptance criteria

- One operator reference accurately documents the configuration, precedence, and working example.
- Bundled routers allow project choices and explicit requests; unconfigured guidance remains available.
- Temporary-install coverage and the full suite pass, with no changes to installation behavior or real installed copies.
- Tracking reflects shipment only after verification; #525 remains independent.
- Governance files remain unchanged.
