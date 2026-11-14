# Installed-skill backlog arc

## File intent

This file is the execution guide for what an installed `plan-tool` skill
(Claude Code, Codex, or Cursor) gives a driving session before it needs to go
find the answer itself. It sequenced #370 — shipped 2026-09-16 as the
skill-router-and-shared-reference plan — ahead of the four items that
depended on it: #371, #377, #378, #379. #371 has since shipped too
(2026-09-17, direct: the routers' `when_to_use`/`paths` frontmatter and
situational `description`), leaving #377/#378/#379. `BACKLOG.md` owns each
item; this file owns only their working order. All three remaining items are
untiered in the priority (mission-grounded) sense — this arc is their sole
router, the same convention `backlog-arc-roadmap.md` uses for its own items.

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

Three separate, verified gaps remain — a driving session still doesn't
reliably get what it needs beyond the router/reference split alone:

- **#377** — `create --from-existing` consumes a seed; nothing installed
  teaches a driving session to *author* one first. `SEED_FORMAT.md`'s scope
  contract and canonical headings aren't reachable from an installed skill in
  a consuming repo.
- **#378** — nine sections of `DIRECTIVES.md` tell a session to defer an
  out-of-scope discovery without naming a destination, and the installed
  routers carry almost none of the capture discipline that already works in
  this repo (`TRACKING.md`, `CLAUDE.md`). Integration, the one real consumer, has no
  `BACKLOG.md` at all — a bare "file it in the backlog" has no correct target
  there.
- **#379** — the mirror problem: no installed rule tells a session what to do
  when it finds an *existing* entry already addressed, so entries drift stale
  or get deleted incorrectly (`5042c3ba` restored #337 after exactly this).

**#377 and #378 are each independently ready now that #370 has shipped;
neither depends on the other.** #378 additionally touches the same router
files #377 does and prefers to land after it if a session also takes #377,
purely to avoid double-editing (that concern no longer applies to #371,
which already shipped in its own commit). #379 depends only on #370 having
shipped (it has) and, when taken alongside #378, sequences after it
specifically — it reuses #378's convention-discovery and commit rhythm.

**Route differs across the three remaining items.** #377 and #378 are `plan`
(citation sweeps and an authority line each need a paper trail); #379 is
`direct` (it carries an explicit `Escalate to plan if:` for per-entry
confirmation). #371, also `direct`, shipped 2026-09-17.

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
3. **#377, #378 in any order.** No dependency runs between them. Prefer
   taking #378 after #377 if a session also selects it, since it edits the
   same router files.
4. **#379 last if taken alongside #378** — otherwise independent.
5. **#443 shipped 2026-10-06** (`DIRECTIVES.md` beside the tracked skill).
   **#444 shipped 2026-10-06** (quoted `argument-hint`, so the routers'
   frontmatter parses as YAML). #442 (AI-DLC coexistence) was closed as not
   reproducible, 2026-10-06 (`docs/history/backlog-decisions.md` § "#442").

## Decision gates

- **The shipped #370 plan's own Non-goals stay the boundary for that plan's
  content:** relocating roadmap operational guidance into `DIRECTIVES.md` was
  in scope for it; any *other* directive content addition (seed authoring,
  discovery capture, stale-entry handling) belongs to #377/#378/#379, not
  folded back into that shipped work.
- **No drift-detection machinery.** The shipped #370 plan deliberately
  deferred a lint or gate that fails when a router restates a rule the shared
  reference owns — one shared file is already the anti-drift mechanism. This
  holds for every remaining item in this arc: none of #377/#378/#379
  introduces a check, gate, or exit-code flip on guidance content (each
  states this in its own Non-goals; the shipped #371 introduced none either).
- **#378's capture rule stays incidental, never a proactive sweep** (its own
  default 1), and **#379's staleness rule stays the same** (its own default
  1) — neither becomes a background job that grooms the backlog on its own.

## Exit and handoff

**This arc's original handoff condition — #370 shipping — is satisfied**:
the skill-router-and-shared-reference plan shipped 2026-09-16, #371 shipped
2026-09-17, and #377/#378/#379 are each now independently selectable
single-item work, no longer needing this file's ordering beyond the
#378/#379-after-#377 preference above. This arc doc itself is not retired:
`BACKLOG.md`'s arc-index line still names it as the sole router for
#377/#378/#379 (and records #371 as shipped from it), so it keeps that role
even though its original sequencing job — getting #370 landed first — is
done. A future related gap gets its own item filed against this same theme
rather than a new arc. Full closure (all three remaining items shipped) is
not required to exit this arc's original job.

## Out of scope

The original #377/#378/#379 lane changes guidance content and installer
plumbing only; it does not change CLI runtime behavior. The public onboarding
extension below permits only #509’s bounded hosting-configuration reader. It does not add a seed-generating command (#377's own Non-goals),
a lint or gate on unrecorded discoveries (#378's), an automated backlog
staleness sweep (#379's), or a `.plan-tool/project.json` tracker-location key
(#378's, absent evidence the ask-once fallback falls short). It does not
decide a Cursor-specific product question beyond what the shipped #370 plan
already settled (one shared reference, not three).

## Public onboarding extension

Choose #508 for portable guidance versus local team policy, #509 for consuming
repository hosting configuration, #511 for installation/refresh clarity, and
#512 for model choice and rationale. The recipe-consistency prerequisite is
satisfied (skill-router repair). #377 remains the owner of
seed-authoring support; #378/#379 retain tracker convention discovery and
stale-entry handling. #509 is a bounded extension of this arc into runtime
configuration, limited to giving the installed session a verified hosting target;
it does not authorize a general hosting framework.

Public-content sanitization (#513) and distribution/history decisions (#514)
remain separate release prerequisites. README walkthrough #510 and fresh-user
verification #515 route through operator-workflow.
