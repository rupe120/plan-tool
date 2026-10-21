> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add a thin Cursor router and accept `cursor` as an `install-skill --integration` value

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`plan_tool/cli/skill_cmd.py` today only knows two integrations (`choices=("claude", "codex")` on `--integration`), and `integrations/cursor/` ships a `backend.json` with no `SKILL.md`, so a Cursor session has no installable router even though `--backend cursor` already works end to end at the CLI level. This step ships `integrations/cursor/SKILL.md` — a thin router built on the same trimmed, `DIRECTIVES.md`-pointing shape steps 2 and 3 land for Claude and Codex — widens `--integration`'s choices to include `"cursor"`, and updates the handful of "Claude Code / Codex" phrases in `skill_cmd.py` that would otherwise misdescribe the command once Cursor is a real value. It also extends `tests/test_model_specs.py::TestProviderAndDefault::test_model_family_docs_cover_every_supported_prefix`'s closed `paths` set so the new router stays watched for model-family token coverage, and regenerates `docs/cli/install-skill.md` / `docs/cli/README.md` from the live parser. On green, `plan-tool install-skill --integration cursor` installs a router plus the shared `DIRECTIVES.md` sibling exactly as `claude`/`codex` already do, and the router itself documents Cursor's one real point of difference: it has no `--model`-inferable family, so it must always be selected explicitly.

## Table of Contents

- [Why](#why) — what's missing today and why it's cheap to add once steps 2 and 3 land
- [Input](#input) — what steps 2 and 3 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — the one new file and four edits
- [Implementation](#implementation) — the router's content shape and the `--integration` widening
- [Tests](#tests) — the new `tests/cli/test_skill_cmd.py` cases and the `tests/test_model_specs.py` extension
- [Acceptance criteria](#acceptance-criteria) — observable facts a reviewer can check
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step
- [Deferred](#deferred) — work this step explicitly does not do

## Why

`plan_tool/backend.py` already registers a real `CURSOR_BACKEND` (binary `agent`), `docs/BACKENDS.md` already documents `plan-tool --backend cursor run my-feature`, and both Claude's and Codex's `argument-hint` frontmatter already show `--backend claude|codex|cursor` — Cursor is a fully working execution backend today. What's missing is purely the *skill-installation* surface: `plan_tool/cli/skill_cmd.py:register()`'s `--integration` choices tuple has no `"cursor"` entry, and `integrations/cursor/` has no `SKILL.md` for `_bundled_skill_source` to resolve even if it did. Steps 2 and 3 do the generic work (a two-path install set that works for any integration, and a proven router/reference split), so this step's job is narrow: author the third router in that shape and flip the one switch that lets `install-skill` serve it.

The one place this step can't just copy-paste a sibling verbatim is the router's "Backend:" paragraph. `plan_tool/model_specs.py:_MODEL_FAMILY_PREFIXES` and the comment above `_BACKEND_PROVIDER_ALIASES` are explicit that Cursor is deliberately absent from model-family inference ("a multi-model CLI... there is no single right provider to default it to") — unlike Claude (`claude-*`) or Codex (`gpt-*`/`chatgpt-*`/`o1`/`o3`/`o4`/`codex-*`), there is no `--model` prefix that selects Cursor automatically. A Cursor router that silently reused Claude's or Codex's paragraph structure without saying this would misdescribe its own backend's selection rule.

## Input

This step depends on steps 2 and 3 landing first (`depends_on: 2, 3`), and reads their outcomes without restating their mechanics:

- **Step 2's outcome** — `cmd_install_skill` installs an ordered set of `(source, dest)` pairs per integration (the per-integration `SKILL.md` plus the shared `DIRECTIVES.md` sibling), classifying each destination as already-correct / missing / foreign-collision before writing anything. This step's `cursor` value plugs into that set mechanism unchanged — `_bundled_skill_source("cursor")` already works once `integrations/cursor/SKILL.md` exists on disk, since that resolver takes `integration` as a parameter. Read the actual landed function/helper names in `plan_tool/cli/skill_cmd.py` at implementation time rather than assuming names from step 2's detail, which describes the shape but leaves exact naming to that step's implementer.
- **Step 3's outcome** — `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` both end up in the trimmed router shape: a bare (`DIRECTIVES.md`, no path prefix) link to the shared reference, no restated roadmap or convergence-loop prose, the same seven roadmap pointer rows/groups and two convergence-discipline pointer rows (plus the "Audit · completeness" row's annotation), and every reference to a doc that can't travel with the install (`RUNBOOK.md`, `README.md`, `docs/OPERATIONS.md`, `SEED_FORMAT.md`, `PLAN_FORMAT.md`, `ROADMAP_FORMAT.md`) rewritten in the plain-name-plus-repo-caveat form the "Going deeper" section already uses. Per the plan's Architecture section ("Step 4's Cursor router inherits the same symmetric shape by copying whatever step 3 lands"), this step's router is built by opening the two actually-committed files at implementation time and copying their common structure — not by reconstructing that shape from this file's description.
- **What this step reads but does not touch:** `integrations/shared/DIRECTIVES.md`'s heading text (added by step 1) that the copied pointer rows cite — this step does not author or edit `DIRECTIVES.md`.
- **A known pre-existing asymmetry between the two templates, left unresolved by step 3:** its own Deferred section explicitly leaves Codex without a `--commit` paragraph in "Running from chat / automation" and without a "run several steps of X in a row" decision-tree row (real gaps versus Claude's router, not this plan's concern to close there). It also leaves Claude's `README.md#worktrees-parallel-plans` citation and Codex's `docs/OPERATIONS.md#worktrees-parallel-plans` citation un-harmonized. Since Cursor's router is new — nothing is being trimmed *from* it — this step is not bound to either template's gaps; see [Implementation](#implementation) for the call this step makes.

## Files (creates vs edits)

- **New file:**
  - `integrations/cursor/SKILL.md` — the thin Cursor router.
- **Existing files (edits only):**
  - `plan_tool/cli/skill_cmd.py` — widen `--integration`'s `choices` to `("claude", "codex", "cursor")`, and update the module docstring, `cmd_install_skill`'s docstring, and the `install-skill` subparser's `help=` string, each of which currently names only "Claude Code / Codex."
  - `tests/cli/test_skill_cmd.py` — add cases exercising `--integration cursor` against the real bundled file.
  - `tests/test_model_specs.py` — add `Path("integrations/cursor/SKILL.md")` to `test_model_family_docs_cover_every_supported_prefix`'s `paths` tuple.
  - `docs/cli/install-skill.md` — regenerated via `python -m plan_tool.cli_reference --write` once `--integration` gains the `cursor` choice.
  - `docs/cli/README.md` — regenerated by the same `--write` run; changes only if the subparser's `help=` string changes (see Implementation).

## Implementation

**Widen the `--integration` choice set.** In `plan_tool/cli/skill_cmd.py:register()`, change `choices=("claude", "codex")` to `choices=("claude", "codex", "cursor")` on the `--integration` argument. `default="claude"` stays unchanged. No other code needs to change: `_bundled_skill_source(integration)` and step 2's per-path install-set logic already take `integration` as a plain string parameter, so `cursor` flows through for free once the file exists on disk.

**Fix the now-stale "Claude Code / Codex" phrasing.** Three spots in `plan_tool/cli/skill_cmd.py` currently name only two integrations by product name:

- the module docstring ("so **Claude Code** / Codex can orchestrate plan-tool")
- `cmd_install_skill`'s docstring ("this verb is the opt-in path for letting **Claude Code** / Codex drive it")
- the `install-skill` subparser's `help=` string ("install the bundled Claude Code / Codex skill into a project...")

Once `cursor` is a real, working `--integration` value, leaving these unchanged makes the command's own self-description inaccurate. Add "Cursor" to each, keeping the existing `/`-separated style (e.g. "Claude Code / Codex / Cursor"). This is why `docs/cli/README.md` is declared for this step and not step 2: step 2's own Deferred section notes that file "regenerated... if the one-line `install-skill` row's source `help=` text changes; otherwise unaffected" — this step is the one that changes it. Regenerate both `docs/cli/install-skill.md` and `docs/cli/README.md` with `python -m plan_tool.cli_reference --write` after the code changes land; never hand-edit either file.

**`plan_tool/cli/__init__.py`'s command-catalog docstring is out of this step's declared files and stays untouched** — see [Deferred](#deferred).

**Author `integrations/cursor/SKILL.md` in the same trimmed router shape steps 2 and 3 produce, adapted for Cursor's own facts.** Frontmatter carries the same five keys the other two routers carry (`name`, `description`, `allowed-tools`, `model`, `argument-hint`) with the same static values except `description`, which needs Cursor's own subprocess wording:

```
---
name: plan-tool
description: Drive step-by-step execution of YAML-frontmatter implementation plans, spawning a fresh Cursor Agent CLI (`agent`) subprocess per step. Use to author (create / detail), audit (validate / reconcile-plan / completeness-audit / verify-all), execute (run), reconcile (detail --reconcile / reconcile-code), bind to a branch (attach-branch / detach-branch), or export to JIRA (jira) a plan whose markdown begins with `---` frontmatter. Plans are discovered per-project via <repo-root>/.plan-tool/plans.json. For freeform markdown plans with no frontmatter, route to a legacy plan runner instead.
allowed-tools: Bash Read Grep Glob Edit Write
model: opus
argument-hint: [--backend claude|codex|cursor] [--on-rate-limit wait|switch|stop|ask] [--fallback-backend BACKEND] <plan-name> [--step N] [--mode check|optimize|document|test|security|lint] [--reconcile] [--dry-run] [--iterate] [--max-iterations N] [--iteration-budget SECONDS]
---
```

`agent` is named as "Cursor Agent CLI (`agent`)" rather than the bare binary name, matching `docs/BACKENDS.md`'s own naming ("the Cursor Agent CLI (binary `agent`)"). The plan's Scope guardrails bar changing skill frontmatter trigger fields (`when_to_use`, `paths`, `model`) — none of those are being added here; `model: opus` is carried forward unchanged, the same static value the other two routers already have, not a new or different choice for this step to make.

The body sections, in order, mirror the two trimmed siblings:

- **Which tool** — copy verbatim (backend-agnostic frontmatter-routing logic).
- **Invocation** — copy the "Plan discovery" and "Repo root" paragraphs verbatim. Write a new "Backend:" paragraph — this is the one paragraph that cannot be copied, since Cursor's selection rule genuinely differs. One way to write it, containing every token `test_model_family_docs_cover_every_supported_prefix` requires (`claude-*`, `gemini-*`, `gpt-*`, `chatgpt-*`, `codex-*`, `o1`, `o3`, `o4`):

  > **Backend:** this skill targets the **cursor** backend — select it with the global `--backend cursor` flag (or `PLAN_TOOL_BACKEND=cursor` env var) so each step runs in a fresh Cursor Agent CLI (`agent`) subprocess; precedence is explicit backend flag > recognized model family > env > default `claude`. `gpt-*`, `chatgpt-*`, `o1`/`o3`/`o4`, and `codex-*` select Codex; `claude-*` selects Claude; and `gemini-*` selects the provisional Gemini backend. Cursor has no unambiguous `--model` family prefix of its own — it's a multi-model CLI, so plan-tool never infers it from `--model`; pass `--backend cursor` (or set `PLAN_TOOL_BACKEND=cursor`) explicitly every time. For ordinary recoverable short rate limits, rate-limit handling is separate: `--on-rate-limit wait|switch|stop|ask` (or `PLAN_TOOL_ON_RATE_LIMIT`) chooses whether to wait, switch, stop, or prompt; `switch` needs `--fallback-backend` or `PLAN_TOOL_FALLBACK_BACKEND`. Cursor's own monthly plan quota is different: a confirmed terminal plan-quota result bypasses those actions entirely — neither closed stdin, `-y`, nor an `--on-rate-limit` setting recovers it. Resolve the provider condition and begin a new command; see RUNBOOK.md's Recovery section and BACKENDS.md's "Cursor's monthly quota is different" section (both in the plan-tool repo).

  The reason this reads as a primary fact rather than a hedge (contrast Claude's and Codex's routers, which mention it defensively since it isn't *their* backend) is that it's Cursor's own router — ground it in `docs/BACKENDS.md`'s "Cursor's monthly quota is different" section and `RUNBOOK.md`'s "cursor agent backend prerequisites / auth" material, using the same plain-name-caveat form step 3 applies everywhere else, since neither doc travels with the install.
- **Running from chat / automation (no TTY)** — copy verbatim, including the `--commit` paragraph (present in Claude's router; absent from Codex's per step 3's Deferred). Basing this section on Claude's fuller template rather than Codex's narrower one follows the Architecture section's symmetry rule directly ("whatever pointer content one router keeps after trimming, the others keep too, even one starting from less... today") — Cursor starts from nothing, so there's no reason to inherit Codex's specific gap rather than Claude's fuller content.
- **Decision tree for common user asks** — copy the shared rows verbatim from whichever sibling is more structurally analogous (Codex's, since it's also a specific non-default backend requiring explicit selection, same as Cursor), including the seven roadmap pointer rows and the two convergence-discipline rows, plus the "run several steps of X in a row" row per the symmetry call above. Column/row text is copied unchanged; only the table's final "Calls cursor?" header (see next bullet) differs.
- **Subcommands at a glance** — same table shape and row groups; rename the "Calls codex?" / "Calls claude?" column header to **"Calls cursor?"**, keeping every `Yes`/`No` value unchanged (those describe whether the subcommand invokes *a* backend at all, not which one). Keep the "Audit · completeness" row's `DIRECTIVES.md`-pointing annotation.
- **Authoring conventions** — copy verbatim (backend-agnostic).
- **Going deeper** — open the two actually-landed sibling files at implementation time and use their common bullet list (`README.md`, `RUNBOOK.md`, `SEED_FORMAT.md`, `PLAN_FORMAT.md`, `plan_tool/cli/`, `plan_tool/prompts/*.md`); if they still differ on one bullet (e.g. a `ROADMAP_FORMAT.md` entry), read off both and pick the fuller set rather than guessing which one is "correct" — per the plan-tool convention that a later step reads landed names off the actual modules, not off an earlier plan/detail description.
- **Not yet implemented / out of scope** — copy verbatim.

**Cite `DIRECTIVES.md` by bare name**, exactly as step 3 does for the other two routers — a real, resolving `[DIRECTIVES.md](DIRECTIVES.md)` link (no `../` prefix), since step 2 places it as a literal sibling at the installed location. Do not write a source-tree-relative path (`../shared/DIRECTIVES.md`); that resolves in the wrong context, the same gotcha step 3's detail calls out.

**What does not change:** this step does not touch `plan_tool/backend.py`, `plan_tool/model_specs.py`, `integrations/cursor/backend.json`, or any runtime backend-selection behavior — the router's "Backend:" paragraph documents existing behavior, it does not implement anything new.

## Tests

### Tests for this step

All land in `tests/cli/test_skill_cmd.py::TestInstallSkill`, reusing (and, where noted, generalizing) the existing `_bundled()` helper and whichever `DIRECTIVES.md`-sibling helper step 2 adds. Every test below must be green before this step is considered finished, alongside the existing suite, with one bounded, deliberate exception: this step's `install-skill` subparser `help=` edit (adding "Cursor") necessarily changes `plan-tool --help`'s rendered output, which fails the already-passing `tests/cli/test_package_surface.py::TestHelpGoldenSnapshot::test_help_matches_golden` golden-snapshot pin. Do not regenerate that golden file here — step 5 owns it and needs a second regen anyway (it also edits `plan_tool/cli/__init__.py`'s docstring). The full suite is expected red on this one test between this step landing and step 5 landing; that window is this plan's one exception to "no existing test goes red in between," and it is bounded to those two steps.

- Generalize `_bundled()` to `_bundled(integration: str = "claude")`, resolving `root / integration / "SKILL.md"` — a default-preserving change, so every existing call site (`_bundled()`) keeps working unchanged.
- `test_cursor_integration_symlink_points_at_the_bundled_cursor_router` — `cli.main(tmp_repo.argv("install-skill", "--integration", "cursor"))` returns `0`; the destination `SKILL.md` is a symlink resolving to `_bundled("cursor")`; the `DIRECTIVES.md` sibling installs correctly alongside it (reuse step 2's sibling assertion).
- `test_cursor_integration_copy_embeds_the_bundled_cursor_router_bytes` — same invocation with `--copy`; asserts the destination is not a symlink and its bytes equal `_bundled("cursor")`'s bytes, and the `DIRECTIVES.md` sibling's bytes match too.

### `tests/test_model_specs.py`

- `test_model_family_docs_cover_every_supported_prefix` (existing, extended) — add `Path("integrations/cursor/SKILL.md")` to the `paths` tuple. Stays green once the new router's "Backend:" paragraph carries every token in `_MODEL_FAMILY_PREFIXES`.

### Verification (doc-content, not a new automated check)

The plan's Scope guardrails bar adding a new drift check, lint, or gate; these are hand checks, mirroring step 3's precedent:

1. Grep `integrations/cursor/SKILL.md` for `](../../` — zero hits (every cross-file reference uses the plain-name-caveat form).
2. Diff the seven roadmap pointer rows/groups and the two convergence-discipline rows plus the completeness-audit annotation against the landed `integrations/codex/SKILL.md` — identical text.
3. Confirm `integrations/cursor/SKILL.md` contains a bare `[DIRECTIVES.md](DIRECTIVES.md)` link (no path prefix).
4. Confirm the "Backend:" paragraph states, in plain language, that Cursor has no unambiguous `--model` family prefix and must be selected explicitly.
5. Build a wheel (the project's packaging tool), install it into an isolated environment, and run `plan-tool install-skill --integration <value>` for each of `claude`, `codex`, and `cursor` against that install — confirming the router-plus-`DIRECTIVES.md` sibling installs correctly from the wheel layout, not only from the editable/source checkout `TestInstallSkill` exercises. This is the plan's own `## Testing`/`## Acceptance criteria` wheel-layout claim; nothing before this step exercises it.

## Acceptance criteria

- `plan-tool install-skill --integration cursor` installs `<root>/skills/plan-tool/SKILL.md` (resolving to `integrations/cursor/SKILL.md`) and its `DIRECTIVES.md` sibling, symlink and `--copy`, exactly as `claude`/`codex` already do.
- `integrations/cursor/SKILL.md` parses as valid frontmatter, names Cursor's own `agent` subprocess in its `description`, and carries a bare `DIRECTIVES.md` link.
- `integrations/cursor/SKILL.md`'s "Backend:" paragraph contains every one of `claude-*`, `gemini-*`, `gpt-*`, `chatgpt-*`, `codex-*`, `o1`, `o3`, `o4`, plus an explicit statement that Cursor itself has no such prefix and must be selected with `--backend cursor` / `PLAN_TOOL_BACKEND=cursor`.
- `integrations/cursor/SKILL.md` carries the same seven roadmap pointer rows/groups, two convergence-discipline pointer rows, and completeness-audit annotation the trimmed Claude/Codex routers carry.
- No `../../`-style relative link to `RUNBOOK.md`, `README.md`, `docs/OPERATIONS.md`, `SEED_FORMAT.md`, `PLAN_FORMAT.md`, or `ROADMAP_FORMAT.md` appears anywhere in the file.
- `docs/cli/install-skill.md`'s Usage/Options table shows `--integration {claude,codex,cursor}`.
- `docs/cli/install-skill.md` and `docs/cli/README.md` match a fresh `python -m plan_tool.cli_reference --write` render (`tests/cli/test_cli_reference.py` passes).
- `uv run pytest tests/cli/test_skill_cmd.py tests/test_model_specs.py -q` passes in full.
- A wheel built from this checkout installs each of the three routers plus
  `DIRECTIVES.md` correctly (Verification item 5), so the plan's wheel-layout
  claim is exercised, not only asserted.

## Applicable guardrails

- The plan's "## Scope guardrails" first bullet (do not rewrite or re-derive `DIRECTIVES.md`'s content) — this step's router only carries pointer-shaped content copied from the landed Claude/Codex shape; it invents no new rule.
- The plan's "## Scope guardrails" second bullet (no drift check, lint, gate, or exit-code flip) — router-content correctness is verified by hand per [Tests](#tests), not by a new pytest assertion.
- The plan's "## Scope guardrails" third bullet (no skill frontmatter trigger-field changes) — the new frontmatter carries the same five keys the other two routers already carry, with the same static `model: opus` value; no `when_to_use`/`paths` field is added.
- The plan's "## Scope guardrails" fourth bullet (no backend-selection or runtime-behavior change) — the "Backend:" paragraph documents existing, already-shipped behavior; nothing in `plan_tool/backend.py` or `plan_tool/model_specs.py` changes.
- The plan's "## Out of scope" excludes the `model:` frontmatter value on any router — carried forward unchanged here.
- BACKLOG #371 (cited in the plan's Scope guardrails) owns skill frontmatter trigger fields as a separate effort — this step does not add any.

## Deferred

- `plan_tool/cli/__init__.py`'s command-catalog docstring — not updated; it's outside this step's declared `files:` list, the same boundary step 2's own Deferred section draws for the identical text. After this step, that catalog's one-line description for `install-skill` still names only "Claude Code / Codex" while the subparser's own `help=` text names all three — a minor prose gap for a follow-up.
- `tests/test_roadmap_format.py`'s guide-sweep dictionary coverage for `integrations/cursor/SKILL.md` — not added. The plan's Testing section scopes those dictionaries to migrating the Claude-router entry (steps 1 and 3); this file isn't declared for step 4 and the plan names no requirement to extend those dictionaries to a third router.
- The top-level `README.md`'s "Optional: the agent skill" section, including its `--integration codex` example — step 5, which the plan already scopes to cover Cursor there.
- `docs/ARCHITECTURE.md`, `integrations/shared/DIRECTIVES.md`'s wiring note, and removing `BACKLOG.md` #370 — step 5.
- This step's choice to base the new Cursor router on Claude's fuller "Running from chat / automation" template (the `--commit` paragraph) and Codex's decision-tree/table shape does not retroactively add the `--commit` paragraph to Codex's own router or otherwise change Claude's or Codex's already-landed content — those remain step 3's own explicitly-left gaps.
- Harmonizing which doc (`README.md` vs `docs/OPERATIONS.md`) the "Workspaces"/worktrees pointer names between Claude and Codex — step 3 leaves that difference in place; this step's new file cites its own single target (see Implementation) without changing either sibling's existing citation.
