# Installed seed-authoring guidance

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

## References

- BACKLOG.md #377 owns the scope and release bookkeeping.
- SEED_FORMAT.md covers scope, canonical headings, preflight and source routing.
- plan_tool/cli/skill_cmd.py:cmd_install_skill selects the bundled router and
  shared reference for copy or symlink installation.
- pyproject.toml's wheel force-include table packages the integrations tree.
- plan_tool/create.py:validate_from_existing_seed classifies file-backed intake.
- integrations/shared/DIRECTIVES.md's Authoring hygiene section is the installed
  guidance to extend.

## Outcome

a Claude Code, Codex, or Cursor session using the installed skill
can author and check a seed from a user request or backlog entry, then hand
that seed to `create --from-existing` with its intent and scope intact.

## In scope

the shared installed guidance, a working installed path to the
authoritative seed format or a bounded authoring contract derived from it,
router entry points where needed, installation coverage for that path, and
focused documentation and tests.

## Out of scope

changing `create` ingestion or seed semantics;
making the CLI generate seeds; expanding the shipped router architecture
(formerly #370) or the shipped skill trigger fields (formerly #371);
requiring a fully canonical body when the documented preparation route is
appropriate; recording discoveries outside a plan's fence (#378) or
updating entries found already addressed (the former #379, now part of #378).

## Allowed behavior changes

the installed skills guide the orchestrating
assistant through seed authoring and validation before `create`. No CLI
command or artifact behavior changes.

## Allowed reorganization

only the guidance and packaging needed to give
every installed backend the same seed-authoring contract.

## Testing

install each backend's skill from a source checkout and a
wheel, including `--copy`; from the installed location, follow its seed
authoring and format links without relying on the source checkout. Check
example seeds from both a user request and a backlog item for `Outcome`,
scope fence, usable `References`, testing and acceptance evidence, and
documented direct-versus-preparation routing.

## Stop / defer

separate any proposed automatic seed generator, new seed
lint command, or change to file-backed ingestion into its own backlog item.

## Risks

An incomplete summary can imply a preparation-only heading is a hard preflight
requirement, or omit a guardrail that create actually checks. Review each claim
against SEED_FORMAT.md and file-backed intake.

## Acceptance criteria

From each installed router an assistant can reach the shared guidance, author
a user-request or backlog-derived seed against local evidence, check the required
headings and choose the correct create handoff. Verify source and wheel
installs, including copy mode, before closing the source entry.

## Deferred

The onboarding walkthrough consumes this support under #510. Tracker capture
and stale-entry disposition belong to #378.

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
