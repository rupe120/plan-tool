---
format_version: 1
title: Installed Seed Authoring
intent: a Claude Code, Codex, or Cursor session using the installed skill can author
  and check a seed from a user request or backlog entry, then hand that seed to `create
  --from-existing` with its intent and scope intact.
status: completed
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
  detail: docs/implementation-plans/plan-details/installed-seed-authoring/01-start-one-first-task-consuming-repo.md
  status: done
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
    Send each router's authoring recipes to the same approved-input handoff. Explain
    the unmatched-fence refusal, the single usable References section, and the three
    required guardrail sections. Distinguish the full scope contract from binding
    limits carried in the named guardrails. Use None only where no boundary of that
    kind applies. Explain which canonical body headings make a seed eligible for direct
    assessment and when an otherwise valid seed goes through preparation. Link the
    same section from all three routers' authoring rows, update the existing phase-link
    unit tests, and keep SEED_FORMAT.md authoritative. Put the usable contract in
    the installed sibling because the current source-repo pointer cannot serve a standalone
    install and the existing two-file bundle already carries the shared reference.
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
  detail: docs/implementation-plans/plan-details/installed-seed-authoring/02-extend-existing-install-skill-coverage.md
  status: done
  description: Extend the existing install-skill coverage to follow the required authoring
    link from each installed router to the seed contract in its installed sibling.
    Use temporary consuming repos and exercise the default and explicit --copy modes
    for Claude, Codex, and Cursor, with Codex copying in both cases. Check the user-request
    and backlog-derived examples against the authoring contract and pass their text
    through validate_from_existing_seed to verify direct readiness and preparation
    without a model call. Check that the References point to usable evidence and each
    binding limit appears in the corresponding guardrail. In a separate acceptance
    run outside pytest, repeat the installed-link check with the actual CLI from an
    isolated wheel installation outside the source checkout. Confirm that the wheel
    is the source of the installed guidance and that both install modes expose the
    same contract without opening SEED_FORMAT.md from the checkout. Use fresh destinations
    for the proof so existing installs are left alone. Keep fixture writes, unlinks,
    and temporary cleanup confined to test-owned paths.
- id: 3
  intent: 'Keep #377 visible until the installed guidance ships and its acceptance
    checks pass.'
  files:
  - BACKLOG.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-installed-skill.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-operator-workflow.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-public-release.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  depends_on_notes:
    2: 'Provides the installation and seed-intake evidence required to remove #377.'
  detail: docs/implementation-plans/plan-details/installed-seed-authoring/03-when-this-plan-authored-mark-backlog-md.md
  status: done
  description: 'When this plan is authored, mark BACKLOG.md #377 as plan-authored
    and link the plan. After shipment and passing source and wheel checks, including
    explicit --copy, remove the #377 entry and reconcile active references that list
    it as selectable work or a pending dependency. Keep #510 and #378 open under their
    own scope and keep useful references to #377 as delivered provenance.'
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

- [Backlog before closure](https://bitbucket.org/protagona/plan-tool/src/f6e6a6f7e9a60925abb50570eb1dc6dbb75ad5b1/BACKLOG.md) records #377's scope and release bookkeeping.
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
requirement, or show a seed whose binding limit is missing from its guardrails.
Review the intake claims against SEED_FORMAT.md and file-backed intake.

## Testing

- Check installed links and default and `--copy` modes for every backend
  using the existing source-install tests. Build and install a wheel in a
  separate isolated acceptance run and repeat those checks outside the
  source checkout. Ordinary pytest runs use the source install.
- Review the user-request and backlog-derived examples for `Outcome`, the
  scope contract, guardrails, usable `References`, testing and acceptance
  evidence, and the order of review, commit and `create`. Check the
  examples' direct readiness and preparation route with intake preflight.

## Acceptance criteria

- Each installed router leads to the same guidance. The big-document
  shortcuts use the same canonical-shape routing rule.
- The guidance explains the evidence a preparation seed must provide and
  limits strict source step import to direct-ready seeds. It identifies
  which assessment outcome publishes a plan and when a preparation
  refusal warrants an unchanged retry or a seed correction. It shows how
  to continue an already registered plan when iteration is incomplete.
- Both examples ground the seed in local evidence and carry each binding
  limit in the appropriate guardrail. The examples show where `None` is
  appropriate.
- The installed walkthrough puts user approval of the seed and a commit of
  that approved input before `create --from-existing`. All authoring entry
  points follow the same handoff. CLI source selection reads the approved
  standalone seed itself.
- Source-install checks and the separate wheel verification pass, including
  copy mode, before the source entry closes.
- Upon closure, the working board and its active arcs reflect #377 delivery.

## Deferred

The onboarding walkthrough consumes this support under #510. Tracker capture
and stale-entry disposition belong to #378.
