# Installed-skill backlog arc

## File intent

This file is the execution guide for what an installed `plan-tool` skill
(Claude Code, Codex, or Cursor) gives a driving session before it needs to go
find the answer itself. The router split (#370), trigger fields (#371), and
seed authoring (#377) have shipped. This arc routes untiered #378, which
includes the former #379, and the public onboarding work listed below.
`BACKLOG.md` owns each open item's scope. This file owns the working order.

## Details

**#370 shipped 2026-09-16** as the skill-router-and-shared-reference plan
(`docs/implementation-plans/2-skill-router-and-shared-reference.md`): each of
the three routers (`integrations/claude/SKILL.md`,
`integrations/codex/SKILL.md`, `integrations/cursor/SKILL.md`) is now a thin
router citing the single shared `integrations/shared/DIRECTIVES.md`, and
`plan-tool install-skill --integration {claude,codex,cursor}`
(`plan_tool/cli/skill_cmd.py:cmd_install_skill`) installs both files as one
set. That was the root of this arc: nothing else here could land correctly
until the installer carried more than one file.

**#371 shipped 2026-09-17**: all three routers now declare `when_to_use` and
a `paths` glob (`docs/implementation-plans/**`, `plan-seeds/**`,
`.plan-tool/plans.json`) scoped to plan-tool artifacts, and `description` is
rewritten as a situational trigger (mentioning `roadmap`) instead of a
capability catalog — the subcommand-name and discovery-mechanics prose it
removed already lived in the routers' bodies, so no body content changed.
Carved out of #371 as a separate decision: #390, decided 2026-10-06 — the
routers leave `model:` unset so the session's own model drives the skill
(`docs/history/backlog-decisions.md` § "#390").

**#377 shipped in PR #275.** The installed routers lead to shared guidance
for authoring and checking a seed before `create --from-existing`. Source
and isolated wheel checks cover Claude, Codex, and Cursor in default and
explicit `--copy` modes. [Installed Seed Authoring](../2-installed-seed-authoring.md)

- **#378** — nine sections of `DIRECTIVES.md` tell a session to defer an
  out-of-scope discovery without naming a destination, and the installed
  routers carry almost none of the capture discipline that already works in
  this repo (`TRACKING.md`, `CLAUDE.md`). Integration, the one real consumer, has no
  `BACKLOG.md` at all — a bare "file it in the backlog" has no correct target
  there.
- **#379 (merged into #378, 2026-11-14)** — the mirror problem: no installed rule tells a session what to do
  when it finds an *existing* entry already addressed, so entries drift stale
  or get deleted incorrectly (`5042c3ba` restored #337 after exactly this).

**#378 is ready and uses the `direct` route.** It adds one section in
`DIRECTIVES.md` with citations. The former #379 shares its convention
discovery and commit rules and retains its escalation condition for
per-entry confirmation.

## Choose this arc when

A session is already committed to improving what an installed skill gives a
driving session — not merely because a gap surfaced while doing something
else (file it per #378's own rule instead). Do not choose this arc for
`roadmap`-verb capability or evidence work (`backlog-arc-roadmap.md`'s
territory, even though #383/#384 are exactly the kind of content the shipped
`DIRECTIVES.md` roadmap relocation — formerly #370's step 1 — now carries) or
for a delivery decision specific to an external consuming application.

## Delivery cadence

Commit each resolved item before starting the next one. Plan-tool work uses
committed green-step checkpoints and the two audit gates; direct changes
include their regression coverage and backlog retirement in one bounded
commit. Do not push automatically; push only when the user explicitly
requests it.

## Ordered route

1. **#370 shipped 2026-09-16** (skill-router-and-shared-reference plan) — the
   installer now carries more than one file, which unblocks everything below.
2. **#371 shipped 2026-09-17** (skill frontmatter trigger fields).
3. **#443 shipped 2026-10-06** (`DIRECTIVES.md` beside the tracked skill).
   **#444 shipped 2026-10-06** (quoted `argument-hint`, so the routers'
   frontmatter parses as YAML). #442 (AI-DLC coexistence) was closed as not
   reproducible, 2026-10-06 (`docs/history/backlog-decisions.md` § "#442").
4. **#377 shipped in PR #275** (installed seed-authoring guidance).
5. **Pick up #378** for tracker discovery, out-of-scope capture, and
   stale-entry handling.

## Decision gates

- **The shipped #370 plan's own Non-goals stay the boundary for that plan's
  content:** relocating roadmap operational guidance into `DIRECTIVES.md` was
  in scope for it. Seed authoring shipped separately as #377. Discovery
  capture and stale-entry handling belong to #378.
- **No drift-detection machinery.** The shipped #370 plan deliberately
  deferred a lint or gate that fails when a router restates a rule the shared
  reference owns — one shared file is already the anti-drift mechanism. This
  constraint applies to #378. The shipped #371 and #377 introduced no
  runtime gate or exit-code change on guidance content.
- **#378's capture rule stays incidental, never a proactive sweep** (its own
  default 1), and **the staleness rule absorbed from #379 stays the same** (its own
  closing default C1) — neither becomes a background job that grooms the backlog on its own.

## Exit and handoff

The #370 shipment satisfies the original handoff condition. This arc remains
the sole router for #378 and routes the public onboarding work below. File
future related gaps as separate entries under the same theme.

## Out of scope

The arc covers guidance content and installer plumbing. The shipped #377
plan excludes a seed-generating command. #378 excludes a lint or gate on
unrecorded discoveries, an automated stale-entry sweep, and a
`.plan-tool/project.json` tracker-location key absent evidence that its
ask-once fallback falls short. #509 covers router guidance. The installed
skill uses the single shared reference established by #370.

## Public onboarding extension

Choose #508 for portable guidance versus local team policy, #509 for consuming
repository hosting-provider guidance in the router, #511 for installation/refresh clarity, and
#512 for model choice and rationale. The recipe-consistency prerequisite is
satisfied (skill-router repair). Seed-authoring support (#377) is complete.
#378 retains tracker convention discovery and stale-entry handling.
#509 is router guidance telling the installed session to
detect the hosting provider from the remote and confirm it with the user; it adds
no configuration surface and does not authorize a hosting framework.

Public-content sanitization (#513) and distribution/history decisions (#514)
remain separate release prerequisites. README walkthrough #510 and fresh-user
verification #515 route through operator-workflow.
