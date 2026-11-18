---
format_version: 1
title: Installed Seed Authoring
intent: a Claude Code, Codex, or Cursor session using the installed skill can author
  and check a seed from a user request or backlog entry, then hand that seed to `create
  --from-existing` with its intent and scope intact.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/installed-seed-authoring.md
steps:
- id: 1
  intent: Give each installed assistant a local path from a request to a reviewed,
    committed seed with its intent and scope intact.
  files:
  - integrations/shared/DIRECTIVES.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  - integrations/cursor/SKILL.md
  - tests/test_skill_router_phase_rules.py
  complexity: medium
  change_type: non-code
  status: current
  description: Start with one first task in a consuming repo. Follow the installed
    router to Authoring hygiene in its sibling DIRECTIVES.md, turn a user request
    into a single grounded seed, check it, ask the user to review it, then commit
    the reviewed seed before handing it to plan-tool create <slug> --from-existing
    <path>. Add that example and a short backlog-derived variation to the shared reference.
    Show how to check claims against the request or backlog entry and live code, write
    the Outcome that becomes plan intent, keep the full scope fence, and include usable
    References, Testing, and acceptance evidence. For backlog work, carry the source
    contract, entry ID, any promoted ticket key, and the eventual backlog update into
    the seed. Replace the stale size and heading advice with the actual intake rules.
    Explain the unmatched-fence refusal, the single usable References section, and
    the three required guardrail sections with their explicit None option. Explain
    which canonical body headings make a seed eligible for direct assessment and when
    an otherwise valid seed goes through preparation. Link the same section from all
    three routers' authoring rows, update the existing phase-link unit tests, and
    keep SEED_FORMAT.md authoritative. Put the usable contract in the installed sibling
    because the current source-repo pointer cannot serve a standalone install and
    the existing two-file bundle already carries the shared reference.
- id: 2
  intent: Prove that every supported install exposes seed guidance that agrees with
    the intake code.
  files:
  - tests/cli/test_skill_cmd.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the shared authoring contract, examples, and router links to verify.
  description: Extend the existing install-skill coverage with a class-level integration
    test that follows the required authoring link from each installed router to the
    seed contract in its installed sibling. Use temporary consuming repos and exercise
    the default and explicit --copy modes for Claude, Codex, and Cursor, with Codex
    copying in both cases. Check the user-request and backlog-derived examples against
    the authoring contract and pass their text through validate_from_existing_seed
    to verify direct readiness and preparation without a model call. Confirm that
    the References point to usable evidence in the example repo. Repeat the installed-link
    check using the actual CLI from a wheel built and installed with the existing
    build tools in an isolated environment outside the source checkout. Confirm that
    the wheel is the source of the installed guidance and that both install modes
    expose the same contract without opening SEED_FORMAT.md from the checkout. Use
    fresh destinations for the proof so existing installs are left alone. Keep fixture
    writes, unlinks, and temporary cleanup confined to test-owned paths.
- id: 3
  intent: 'Keep #377 visible until the installed guidance ships and its acceptance
    checks pass.'
  files:
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  depends_on_notes:
    2: 'Provides the installation and seed-intake evidence required to remove #377.'
  description: 'When this plan is authored, mark BACKLOG.md #377 as plan-authored
    and link the plan. Remove only the #377 entry after the guidance ships and the
    required source and wheel checks pass, including explicit --copy. Keep the entry
    open if any required check is pending, and leave the #510 and #378 work in their
    own entries.'
---
# Installed Seed Authoring

## Overview

Give a consuming repository's driving assistant a short first-task example and
the seed contract it needs to turn a request into a reviewed, committed seed.

## Problem statement

The installed router links to its sibling reference, but its full seed-format
pointer assumes access to the tool source repository. The file-backed create
entry consumes an authored input and checks its preflight shape.

## Architecture

Use the existing installed shared reference for the bounded authoring contract
and the worked intake example. Link to it from the three routers. Keep
SEED_FORMAT.md authoritative and keep the existing packaging and installation
behavior. The assistant inspects the consuming repository, grounds the claims,
checks the finished brief and requests review before committing it for creation.

This plan comes from BACKLOG.md #377. Update the originating entry when the
plan is authored, then remove it after the installed guidance ships and the
required verification is complete.

## Scope guardrails

Limit changes to installed seed-authoring guidance, its router links,
verification and #377 tracking. Preserve the existing two-file install and
file-backed create behavior.

## Audit guardrails

Judge the installed authoring path and its agreement with seed intake. Keep
public onboarding sign-off and tracker-discovery policy outside this effort.

## Expected placement

The procedure and bounded rules live in the shared installed reference.
The router entry points link to them and SEED_FORMAT.md remains the source
contract.

## References

- BACKLOG.md #377 owns the scope and release bookkeeping.
- SEED_FORMAT.md covers scope, canonical headings, preflight and source routing.
- plan_tool/cli/skill_cmd.py:cmd_install_skill selects the bundled router and
  shared reference for copy or symlink installation.
- pyproject.toml's wheel force-include table packages the integrations tree.
- plan_tool/create.py:validate_from_existing_seed classifies file-backed intake.
- integrations/shared/DIRECTIVES.md's Authoring hygiene section is the installed
  guidance to extend.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

changing `create` ingestion or seed semantics;
making the CLI generate seeds; expanding the shipped router architecture
(formerly #370) or the shipped skill trigger fields (formerly #371);
requiring a fully canonical body when the documented preparation route is
appropriate; recording discoveries outside a plan's fence (#378) or
updating entries found already addressed (the former #379, now part of #378).

## Risks

An incomplete summary can imply a preparation-only heading is a hard preflight
requirement, or omit a guardrail that create actually checks. Review each claim
against SEED_FORMAT.md and file-backed intake.

## Testing

install each backend's skill from a source checkout and a
wheel, including `--copy`; from the installed location, follow its seed
authoring and format links without relying on the source checkout. Check
example seeds from both a user request and a backlog item for `Outcome`,
scope fence, usable `References`, testing and acceptance evidence, and
documented direct-versus-preparation routing.

## Acceptance criteria

From each installed router an assistant can reach the shared guidance, author
a user-request or backlog-derived seed against local evidence, check the required
headings and choose the correct create handoff. Verify source and wheel
installs, including copy mode, before closing the source entry.

## Deferred

The onboarding walkthrough consumes this support under #510. Tracker capture
and stale-entry disposition belong to #378.
