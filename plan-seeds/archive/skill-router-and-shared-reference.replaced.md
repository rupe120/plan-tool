> **Replaced**: this file has been superseded by `docs/implementation-plans/2-skill-router-and-shared-reference.md`.
> Preserved here for history; do not edit.

# Plan seed: thin skill routers over one installer-carried shared reference

```
plan-tool create skill-router-and-shared-reference --from-existing plan-seeds/skill-router-and-shared-reference.md
```

Source backlog entry: **`BACKLOG.md` #370**, whose scope contract this seed
inherits and elaborates. The resulting plan removes #370 from `BACKLOG.md` in
its final docs/status step, and only once the work ships.

## Outcome

Every supported assistant — Claude Code, Codex, and Cursor — installs a thin
`SKILL.md` router plus the same shared driving reference beside it, so the
rules for driving `plan-tool` live in exactly one tracked file and reach every
backend identically.

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
- **Roadmap guidance moves into the shared reference first.**
  `DIRECTIVES.md` has no operational roadmap content today — two mentions,
  both about model selection — while the Claude router carries it. Thinning
  routers before relocating it loses the content.

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

## Scope of work

1. Relocate roadmap operational guidance into
   `integrations/shared/DIRECTIVES.md`, so the shared reference is complete
   before any router is thinned.
2. Teach `install-skill` to install a set of paths rather than one, keeping
   its existing idempotency, collision, `--force`, `--copy`, `--user`, and
   `--root` semantics coherent per installed path — including when a partial
   install already exists.
3. Reduce each router to the router half and have it cite the sibling
   reference.
4. Add the Cursor router and make `cursor` an installable `--integration`
   value.
5. Regenerate the CLI reference, update `docs/ARCHITECTURE.md`'s `skill_cmd`
   row, and remove `BACKLOG.md` #370.

## Out of scope

- `plan-tool init` writing a `CLAUDE.md` / `AGENTS.md` pointer for Codex and
  Cursor, which have no skill auto-discovery at all. Its own entry.
- Retiring the machine-local `~/.claude/directives/plan-tool.md` symlink.
- Hooks, or any other invocation-time enforcement mechanism.
- The `model:` frontmatter value on any router.

## Testing

What would prove the Outcome:

- A built wheel and an editable/source checkout each install router plus
  reference, for every supported `--integration` value.
- A `--copy` install's reference link resolves from the installed location —
  the case that is broken today.
- Install stays idempotent across the whole installed set, and a foreign file
  at any installed path still refuses without `--force`.
- Coverage extends the existing seams rather than forking them:
  `tests/cli/test_skill_cmd.py` and `tests/test_backend.py:1592
  test_packaged_integrations_dir_finds_real_manifests`.

## Acceptance criteria

- Each of the three routers installs with the shared reference beside it, in
  both wheel and source layouts.
- `plan-tool install-skill --integration cursor` installs.
- No router restates a rule the shared reference owns.
- The shared reference carries roadmap operational guidance.
- `BACKLOG.md` #370 is removed when the work ships.

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

## Deferred

A drift guard that fails when a router restates a rule the shared reference
owns. Deferred deliberately: one shared file is already the anti-drift
mechanism, so a second mechanism for the same property is a remedy larger than
the defect until drift is actually observed.

## References

- `BACKLOG.md` #370 — source entry and scope contract.
- `BACKLOG.md` #371 — the sibling trigger-field effort this seed fences out.
- `plan_tool/cli/skill_cmd.py` — today's single-path installer.
- `plan_tool/backend.py:_packaged_integrations_dir` — dual-mode resolution.
- `pyproject.toml` `[tool.hatch.build.targets.wheel.force-include]` — the
  packaging remap that makes the shared reference shippable.
