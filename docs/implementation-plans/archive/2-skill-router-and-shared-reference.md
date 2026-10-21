> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Skill Router And Shared Reference
intent: Every supported assistant — Claude Code, Codex, and Cursor — installs a thin
  `SKILL.md` router plus the same shared driving reference beside it, so the rules
  for driving `plan-tool` live in exactly one tracked file and reach every backend
  identically.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
enforce_step_tests: true
source_seed: plan-seeds/archive/skill-router-and-shared-reference.replaced.md
steps:
- id: 1
  title: Add the Claude router's roadmap operational guidance to integrations/shared/DIRECTIVES.md
    and add DIRECTIVES.md to the roadmap guide-sweep tests
  intent: Makes the shared reference the complete home for the roadmap flag-semantics
    and table detail before any router is thinned -- the router keeps only a one-line
    pointer per ask -- so no roadmap content is lost when the Claude router drops
    its copy.
  files:
  - integrations/shared/DIRECTIVES.md
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: non-code
  detail: docs/implementation-plans/plan-details/skill-router-and-shared-reference/01-claude-router-roadmap-operational.md
  status: done
- id: 2
  title: 'Make install-skill install the router and the shared DIRECTIVES.md beside
    it as one set: check every path for a foreign file before writing any, skip paths
    that are already correct, and limit --force''s unlink to the paths that collide'
  intent: Lets every installed router cite the shared reference by bare sibling name
    under both symlink and --copy installs, which today's single-file installer cannot
    support.
  files:
  - plan_tool/cli/skill_cmd.py
  - tests/cli/test_skill_cmd.py
  - tests/test_backend.py
  - docs/cli/install-skill.md
  - docs/cli/README.md
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/skill-router-and-shared-reference/02-make-install-skill-install-router.md
  status: done
- id: 3
  title: 'Trim the Claude and Codex routers to the router half per the Architecture
    section''s symmetry rule: cite the sibling DIRECTIVES.md by bare name, remove
    the rules the reference already owns (the Claude convergence tail section and
    its roadmap operational prose) while leaving one pointer line per roadmap and
    convergence-discipline row -- giving Codex the same set Claude keeps, since Codex
    starts with none of it -- repoint (never delete) any link, cross-file or in-page,
    that can no longer resolve once trimming lands, using the plain-name-plus-repo-caveat
    form the Going deeper section already uses, move the roadmap guide-sweep pins
    off the Claude router, and fix any code comment that names a removed router section'
  intent: Makes the rules for driving plan-tool live in one tracked file while each
    router -- Codex included -- still answers which command to run, including which
    roadmap ask to reach for and when to drive the convergence tail, without reading
    the long reference and without leaving a link that cannot resolve once installed
    or that points at a section this step deletes.
  files:
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  - tests/test_roadmap_format.py
  - tests/cli/test_skill_cmd.py
  - plan_tool/cli/__init__.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/review_cmd.py
  - plan_tool/cli/inspect.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: DIRECTIVES.md already carries the roadmap guidance the Claude router is about
      to drop
    2: install-skill places DIRECTIVES.md beside the router, so the bare sibling citation
      resolves from the installed location
  detail: docs/implementation-plans/plan-details/skill-router-and-shared-reference/03-trim-claude-codex-routers-router-half.md
  status: done
- id: 4
  title: Add a thin Cursor router and accept cursor as an install-skill --integration
    value
  intent: Gives a Cursor session the same installable router and shared reference
    that Claude Code and Codex sessions get, including the same backend-selection/model-family
    paragraph the other two routers carry, extending tests/test_model_specs.py::TestProviderAndDefault::test_model_family_docs_cover_every_supported_prefix's
    closed doc set to the new router so the check keeps watching it.
  files:
  - plan_tool/cli/skill_cmd.py
  - tests/cli/test_skill_cmd.py
  - tests/test_model_specs.py
  - docs/cli/install-skill.md
  - docs/cli/README.md
  creates:
  - integrations/cursor/SKILL.md
  allowed_mentions:
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: the set installer that the cursor value plugs into
    3: the thin router shape the Cursor router copies
  detail: docs/implementation-plans/plan-details/skill-router-and-shared-reference/04-thin-cursor-router-accept-cursor.md
  status: done
- id: 5
  title: 'Update the install-skill docs (including README.md''s "Optional: the agent
    skill" section, whose --integration codex example must cover cursor too) and DIRECTIVES.md''s
    wiring note; retire handoffs/2026-09-16-roadmap-orchestration-primer.md once step
    1 meets its own stated retirement condition, checking the file''s full content
    rather than only the section that condition names; then remove BACKLOG.md #370
    and update every BACKLOG.md and arc-doc citation of it to reflect the shipped
    state'
  intent: Keeps the docs true to the shipped installer and closes the source backlog
    entry, leaving BACKLOG.md and the arc doc accurate about number 370's shipped
    state rather than dangling on a removed identifier.
  files:
  - docs/ARCHITECTURE.md
  - README.md
  - integrations/shared/DIRECTIVES.md
  - BACKLOG.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-installed-skill.md
  - handoffs/2026-09-16-roadmap-orchestration-primer.md
  - plan_tool/cli/__init__.py
  - tests/cli/package_surface_help.golden.txt
  complexity: low
  change_type: refactor
  depends_on:
  - 1
  - 2
  - 3
  - 4
  depends_on_notes:
    4: cursor is a shipped --integration value that the README and ARCHITECTURE row
      now describe
  detail: docs/implementation-plans/plan-details/skill-router-and-shared-reference/05-update-install-skill-docs-including.md
  status: done
  status_note: 'Manually advanced: the test-authoring gate blocked on a known limitation
    (the checkpoint commit recovering an OOM-interrupted call already included the
    test-file edit, tests/cli/package_surface_help.golden.txt, so this call''s own
    delta was empty even though the step did author/modify a test file). Verified
    directly against every acceptance criterion and a full-suite run (12640 passed,
    1 pre-existing unrelated failure already tracked in BUG_BACKLOG.md, confirmed
    reproducing before this plan''s first commit) before advancing.'
---
# Skill Router And Shared Reference

## Overview

`plan-tool` ships an optional agent skill per backend so a chat session can
drive the pipeline. Today each backend's `SKILL.md` is a standalone document
that must restate the driving rules, because the installer can only place one
file. This effort inverts that: the installer places a thin router **and** the
canonical `DIRECTIVES.md` beside it, so the rules are written once and every
assistant — Claude Code, Codex, Cursor — reads the same copy.

## Problem statement

`install-skill` writes exactly one path
(`plan_tool/cli/skill_cmd.py:cmd_install_skill` — `dest = dest_dir /
"SKILL.md"`), so each backend's router has to restate the driving rules
itself. Three consequences, each verified at HEAD on 2026-09-16:

- `integrations/claude/SKILL.md` carries the session-directed convergence tail
  and nine roadmap references; `integrations/codex/SKILL.md` carries neither,
  so a Codex session driving the pipeline has no convergence discipline and no
  knowledge that the `roadmap` verb exists.
- `integrations/cursor/` ships `backend.json` with no `SKILL.md`, and
  `--integration` accepts only `("claude", "codex")`, so a Cursor session
  cannot install one even if it were written.
- Neither router names `integrations/shared/DIRECTIVES.md`. Their relative
  links (`../../RUNBOOK.md`) are written against `integrations/<backend>/`, so
  they break once installed under `<root>/skills/plan-tool/`.

## Architecture

Settled decisions. A later reader should not re-litigate these.

- **The shared reference is the existing `integrations/shared/DIRECTIVES.md`,
  not a new distilled copy.** It is already the tracked canonical source; a
  fourth copy would reintroduce the drift this effort removes.
- **The installer carries it into the skill directory as a sibling**, and the
  router cites it by bare relative name. A sibling resolves under both
  `--copy` and symlink installs; `../../`-style links never do.
- **Packaging already supports this.** Verified 2026-09-16 by building a
  wheel: `pyproject.toml`'s
  `[tool.hatch.build.targets.wheel.force-include]` maps the whole
  `integrations` tree, and the built wheel contains
  `plan_tool/integrations/shared/DIRECTIVES.md`.
  `plan_tool/backend.py:_packaged_integrations_dir` already resolves both the
  wheel and source-checkout layouts, so no packaging change is required.
- **Router and reference split by the question each answers.** The router
  answers *when to reach for the tool and how to invoke it* — which tool,
  invocation and headless form, backend selection, the decision tree, and
  pointers onward. The reference owns *the rules* — the two audit gates, the
  session-directed convergence loop and its three exits, reconcile
  directionality, `--iterate` / `--commit`, the post-run tail, and seed
  authoring.
- **The three routers stay as symmetric as possible — whatever pointer
  content one router keeps after trimming, the others keep too, even one
  starting from less (or none) of it today.** `DIRECTIVES.md` has no
  operational roadmap or convergence-loop content of its own today, while
  the Claude router carries both today — roadmap awareness (its decision-tree
  and Subcommands-table rows) and convergence discipline (the "plan finished
  running" / "completeness flagged a gap" rows and the Audit-completeness
  annotation), per the Problem statement's two named Codex harms. Codex
  carries neither (confirmed at HEAD: zero mentions of "roadmap", no
  convergence-tail row) — trimming can only shrink what already exists, so
  parity for Codex means *adding* whatever pointer content Claude's router
  keeps after trimming, not just removing what's redundant. The split for
  every such row: a **one-line pointer** stays in the router (the entry
  command plus a "see `DIRECTIVES.md`" phrase), while the flag semantics,
  gate/refusal behavior, and multi-sentence prose relocate to `DIRECTIVES.md`.
  Step 4's Cursor router inherits the same symmetric shape by copying
  whatever step 3 lands. This is the concrete form of the router/reference
  split above, applied to the places today's routers carry reference-shaped
  detail unevenly.
- **A link that can no longer resolve — to another file, or to an in-page
  section this effort removes — gets repointed, never left dangling, and
  consistently across routers.** Only `DIRECTIVES.md` travels with the
  install (per the sibling-install decision above); `RUNBOOK.md`, `README.md`,
  `docs/OPERATIONS.md`, `SEED_FORMAT.md`, `PLAN_FORMAT.md`, and
  `ROADMAP_FORMAT.md` do not, and no relative depth resolves them for a
  `--copy` install into a foreign repo — the router's own source and installed
  locations do not even share one correct depth (two levels up from
  `integrations/claude/SKILL.md`, three from the installed
  `<root>/skills/plan-tool/SKILL.md`). The "Going deeper" section already
  states a convention for this (bold plain names plus "these live in the
  plan-tool repo"); step 3 applies that same convention everywhere a link can
  no longer resolve — the remaining inline cross-file links, and any in-page
  anchor (e.g. to the deleted convergence-tail section) that would otherwise
  point at nothing once trimming lands.

## Scope guardrails

- Do not rewrite, re-argue, or re-derive the content of `DIRECTIVES.md`
  beyond relocating roadmap guidance into it and moving router-shaped prose
  out of the routers.
- Do not add a drift check, lint, gate, or exit-code flip of any kind. One
  shared file is the anti-drift mechanism; see `## Deferred`.
- Do not add or change skill frontmatter trigger fields (`when_to_use`,
  `paths`, `model`) — that is `BACKLOG.md` #371, a separate direct effort on
  the same files.
- Do not change backend selection, `backend.json`, or the runtime behavior of
  any command the routers describe.

## References

- `BACKLOG.md` #370 — source entry and scope contract.
- `BACKLOG.md` #371 — the sibling trigger-field effort this seed fences out.
- `plan_tool/cli/skill_cmd.py` — today's single-path installer.
- `plan_tool/backend.py:_packaged_integrations_dir` — dual-mode resolution.
- `pyproject.toml` `[tool.hatch.build.targets.wheel.force-include]` — the
  packaging remap that makes the shared reference shippable.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- `plan-tool init` writing a `CLAUDE.md` / `AGENTS.md` pointer for Codex and
  Cursor, which have no skill auto-discovery at all. Its own entry.
- Retiring the machine-local `~/.claude/directives/plan-tool.md` symlink.
- Hooks, or any other invocation-time enforcement mechanism.
- The `model:` frontmatter value on any router.

## Risks

- Thinning a router before the reference is complete loses roadmap guidance
  that exists only in the Claude router today. Step 1 exists to prevent this
  and must stay first.
- Over-moving: pushing invocation and decision-tree prose into the reference
  forces every assistant to read a long document to answer "which command",
  which is the failure the router exists to prevent.
- `install-skill`'s per-path semantics multiply. Idempotency, collision
  detection, and `--force` are currently reasoned about for a single file and
  must stay coherent once a partial install is possible.
- Step 4's `--integration cursor` help-text edit changes `plan-tool --help`'s
  rendered output, failing `tests/cli/test_package_surface.py`'s golden
  snapshot until step 5 regenerates it — the one deliberate, bounded
  exception to this plan's otherwise-green-between-every-step sequencing,
  named in step 4's own detail Tests section.

## Testing

What would prove the Outcome:

- A built wheel and an editable/source checkout each install router plus
  reference, for every supported `--integration` value.
- A `--copy` install's reference link resolves from the installed location —
  the case that is broken today.
- Install stays idempotent across the whole installed set, and a foreign file
  at any installed path still refuses without `--force`.
- Coverage extends the existing seams rather than forking them:
  `tests/cli/test_skill_cmd.py`, `tests/test_backend.py:1592
  test_packaged_integrations_dir_finds_real_manifests`, and every
  `tests/test_roadmap_format.py` guide-sweep dictionary keyed on
  `integrations/claude/SKILL.md` — not only `_STRUCTURAL_ROUTE_GUIDES`/
  `_STRUCTURAL_ROUTE_GUIDE_BOUNDS` (today's bounds start at `"| **roadmap
  rewrite** |"` and never watch the decision tree at all), but also
  `_SOURCE_ADMISSION_GUIDES`/`_SOURCE_ADMISSION_GUIDANCE`/
  `_SOURCE_ADMISSION_ISOLATION` and `_NON_STAGE_BRIEF_DRIFT_GUIDES` (whose
  derived `_NON_STAGE_REBIND_GUIDES` inherits the same entry) — each of
  which asserts an exact phrase from today's decision-tree row prose (e.g.
  "without `--confirm-brief-rebind`", "replace only the accepted
  decoded-text baseline") is present verbatim in the router text. Trimming
  the router to one-line pointers makes these assertions **false, not
  merely stale** — each dictionary's Claude-router entry gets migrated to
  wherever that content now lives (`DIRECTIVES.md`, mostly) rather than left
  pointed at text step 3 removes. `_STAGE_FEEDBACK_GUIDES` is not keyed on
  `integrations/claude/SKILL.md` at all (verified at HEAD) and needs no
  change.
- `docs/cli/install-skill.md` is regenerated (`python -m plan_tool.cli_reference
  --write`) once `--integration` gains the `cursor` choice, so
  `tests/cli/test_cli_reference.py`'s drift guard stays green.
- `tests/test_model_specs.py::TestProviderAndDefault::test_model_family_docs_cover_every_supported_prefix`
  gets a third `paths` entry for `integrations/cursor/SKILL.md`, so the
  closed-set check keeps watching every installed router.
- A hand check that every router-to-doc reference which cannot travel with
  the install (`RUNBOOK.md`, `README.md`, `docs/OPERATIONS.md`,
  `SEED_FORMAT.md`, `PLAN_FORMAT.md`, `ROADMAP_FORMAT.md`) reads as a plain
  name with the repo-caveat, not a relative link — the same convention the
  "Going deeper" section already uses.
- A hand check that `integrations/codex/SKILL.md` ends with the same seven
  roadmap pointer rows and two convergence-tail pointer rows (plus the
  "Audit · completeness" annotation) that Claude's trimmed router keeps, and
  that none of Claude's three former convergence-tail anchor links still
  point at the deleted section.

## Acceptance criteria

- Each of the three routers installs with the shared reference beside it, in
  both wheel and source layouts.
- `plan-tool install-skill --integration cursor` installs.
- No router restates a rule the shared reference owns.
- The shared reference carries roadmap operational guidance.
- Every router — Claude, Codex, and Cursor — keeps one pointer line per
  roadmap ask, and no router-to-doc reference that cannot travel with the
  install remains a relative link.
- `BACKLOG.md` #370 is removed when the work ships.
- `tests/test_roadmap_format.py`'s guide-sweep dictionaries that assert exact
  phrases against `integrations/claude/SKILL.md` pass against the trimmed
  router (migrated to point at the router's new pointer-line text or at
  `DIRECTIVES.md`, whichever now carries the asserted phrase).
- Codex's router carries the same roadmap and convergence-tail pointer rows
  Claude's keeps, and no router-internal link points at content step 3
  removes.

## Deferred

A drift guard that fails when a router restates a rule the shared reference
owns. Deferred deliberately: one shared file is already the anti-drift
mechanism, so a second mechanism for the same property is a remedy larger than
the defect until drift is actually observed.
