> **Auto-archived**: this plan was swept on 2026-06-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Document branch-awareness across the six operator surfaces

## Summary

Documents the opt-in branch-awareness feature (steps 1–7) across the six operator-facing surfaces — `RUNBOOK.md`, `README.md`, `CLAUDE.md`, `BACKLOG.md`, `integrations/claude/SKILL.md`, `integrations/codex/SKILL.md` — with **zero production-code change**. The load-bearing decision is **single-sourcing one canonical OFF-by-default sentence** verbatim at every surface that first introduces the feature, so an operator landing on any one doc reads the same "ships OFF; enable per-repo via `.plan-tool/config.json` or `PLAN_TOOL_BRANCH_AWARENESS`; off = byte-for-byte today's behavior" framing. Each documented command/flag is attributed to the upstream step that registers it (`attach-branch`/`detach-branch` → step 6, `run --switch-branch` → step 5, the create-time collision warning → step 7, the config flag → step 1) and must be cross-checked against the live parser surface — `plan-tool --help` and each subparser — once those steps land, never trusted from plan prose. On green: every surface carries the canonical sentence and the new commands/flag; the two `SKILL.md` files stay byte-parallel except their pre-existing backend framing; no doc names a flag the parser does not carry.

## Table of Contents

- [Why](#why) — what's undocumented today and why every surface must carry it
- [Files (creates vs edits)](#files-creates-vs-edits) — the six edited docs
- [Implementation](#implementation) — the canonical sentence, per-surface placement, flag→step attribution, the two load-bearing non-edits
- [Tests](#tests) — N/A (non-code); see Verification
- [Verification (non-code step)](#verification-non-code-step) — link/accuracy/parity checks against the live parser
- [Acceptance criteria](#acceptance-criteria) — observable, reviewer-checkable facts
- [References](#references) — git docs the feature's config/derivation rest on
- [Deferred](#deferred) — surfaces deliberately out of footprint

## Why

Branch-awareness (steps 1–7) ships an entirely new operator vocabulary — the `attach-branch`/`detach-branch` verbs, the `run --switch-branch` flag, the create-time namespace-collision warning, and the `branch_awareness.enabled` config flag (`.plan-tool/config.json` + `PLAN_TOOL_BRANCH_AWARENESS`) — yet a grep of the six operator surfaces returns **zero** mentions of any of it. Until these are documented, the new commands are invisible to the Claude/Codex skills (whose frontmatter `description` and decision-tree drive how an agent routes a user ask) and an operator reading any one surface has no signal that the feature exists, is off by default, or how to turn it on. The feature is intentionally inert in every repo today, which makes the **OFF-by-default framing itself the most important thing to document** — without it, a reader who finds only the enable-path on one surface could conclude existing repos changed behavior.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `RUNBOOK.md` — add a **Branch-awareness** entry to the Table of contents and Quick reference, and a new `## Workflow: run a plan on its own branch (branch-awareness)` section carrying the canonical sentence, the enable step, and the `attach-branch`/`detach-branch`/`run --switch-branch` recipes.
  - `README.md` — add a branch-awareness concept paragraph (sibling to the `annotate` forward-seed paragraph) carrying the canonical sentence and the derive-vs-override model.
  - `CLAUDE.md` — add a one-paragraph **Architecture** note pointing at the cycle-free leaves (`plan_tool/project_config.py`, `plan_tool/branch_binding.py`, `plan_tool/branch_ownership.py`) and the OFF-by-default flag.
  - `BACKLOG.md` — grep for a branch-awareness entry first; remove it if present (the feature shipped). If absent, this is a **verified no-op** (see Implementation).
  - `integrations/claude/SKILL.md` — three named slots: extend the frontmatter `description` audit-verb list, add a **Subcommands at a glance** row, add a **Decision tree for common user asks** row.
  - `integrations/codex/SKILL.md` — the identical three-slot edits, mirrored byte-for-byte except the pre-existing `codex exec` / "Calls codex?" framing.

## Implementation

### The canonical OFF-by-default sentence (single-source verbatim)

- **Compose ONE sentence and drop it verbatim at every surface that first introduces the feature.** Recommended wording:

  > **Branch-awareness ships OFF.** Enable it per-repo in `.plan-tool/config.json` as `{"branch_awareness": {"enabled": true}}` (or set `PLAN_TOOL_BRANCH_AWARENESS=1`); with it off — every repo today — `run` and `create` behave exactly as before.

- **Carry it at:** RUNBOOK's Quick reference + the new workflow section, README's concept paragraph, CLAUDE's Architecture note, and both SKILL.md decision-tree rows (or the row's adjoining note). Single-sourcing also pins the enable-path/precedence wording so it cannot drift between surfaces.
- **Precedence wording (from step 1):** `PLAN_TOOL_BRANCH_AWARENESS` env → project `.plan-tool/config.json` → user `~/.plan-tool/config.json` → `false`. State this only where the doc already goes into config depth (README concept paragraph, CLAUDE Architecture note); the SKILL rows and RUNBOOK quick-ref need only the canonical sentence.
- **Default-branch detection (`PLAN_TOOL_DEFAULT_BRANCH`, from step 2):** document the `PLAN_TOOL_DEFAULT_BRANCH` env override and its undeterminable-default skip behavior alongside the config flag at the config-depth surfaces (README concept paragraph, CLAUDE Architecture note, and the RUNBOOK create-collision recipe). State that the create-time collision disambiguation cuts the new branch from the default branch, that the default is resolved via `origin/HEAD` (or `PLAN_TOOL_DEFAULT_BRANCH` when set), and that when the default is undeterminable — a local-only repo with no `origin/HEAD` and no `PLAN_TOOL_DEFAULT_BRANCH` — disambiguation is **skipped with an info note**, so a local-only operator knows why the collision warning didn't disambiguate and that setting `PLAN_TOOL_DEFAULT_BRANCH` restores it.

### Flag/verb → registering-step attribution (verify against the live parser)

- **`attach-branch <plan> <branch>` / `detach-branch <plan>` → step 6** (`plan_tool/cli/manifest.py:cmd_attach_branch` / `cmd_detach_branch`). Both **refuse non-zero when branch-awareness is off**. `attach-branch` records the ad-hoc override; binding to another registered plan's convention name strong-warns and re-homes. `detach-branch` clears the override (quiet no-op when nothing was bound).
- **`run --switch-branch` → step 5** (`plan_tool/cli/run_cmd.py`, the `run` subparser). Surfaced only by `run --help`, so the top-level `plan-tool --help` catalog is unchanged. On a Tier-4 unowned branch with a clean tree it creates-if-missing + switches to the plan's expected branch.
- **Create-time namespace-collision warning → step 7** (`plan_tool/cli/authoring.py:_create_branch_collision_gate`). This is **behavioral, not a flag** — `cmd_create` gains no new CLI option. Do **not** document `--force` or `--allow-non-default-branch`: those belong to a superseded deflect-to-seed design and are **absent** from `cmd_create`'s subparser. Verify their absence before writing.
- **Config flag → step 1** (`plan_tool/project_config.py:branch_awareness_enabled` / `branch_prefixes`).
- **`depends_on` reconciliation:** this step's frontmatter declares `depends_on: [5, 6, 7]`, so step 7's edge (which the create-collision content above presumes) is already covered, alongside the steps 1/5/6 the other attributions lean on.
- **Mandatory verification:** a documented flag name is an authoring-time claim that decays if an upstream step renamed or dropped it. Once steps 5–7 land, grep each documented surface's command/flag against `plan-tool --help`, `plan-tool run --help`, `plan-tool attach-branch --help`, `plan-tool detach-branch --help`. **No doc may name a flag the parser doesn't carry.**

### `RUNBOOK.md`

- **Table of contents:** add a list item linking the new workflow section (between the existing per-subcommand reconcile / completeness entries and the Recovery block).
- **Quick reference:** add a **Branch-awareness (opt-in)** mini-block or table rows for `attach-branch`/`detach-branch`/`run --switch-branch`, prefixed by the canonical sentence so a reader sees OFF-by-default before any recipe.
- **New `## Workflow: run a plan on its own branch (branch-awareness)`:** enable step (config or env), `attach-branch`/`detach-branch` round-trip, the run guard's tier behavior in one sentence each (block on owned, warn on orphan, nudge/`--switch-branch` on unowned), and the create-collision warning. Keep it bulleted per the writing-style rules.

### `README.md`

- **Add a concept paragraph** as a sibling to the `annotate` forward-seed paragraph (after the core-workflow diagram block). Cover: a registered plan's branch is **derived from its slug** (`<primary-prefix><slug>`, default `plan/<slug>`), the configurable `branch_prefixes` list (default `["plan/"]`, project-over-user precedence; the primary/first prefix names the branch `create` makes, while all configured prefixes are accepted when matching/enforcing so a dev who used `feature/<slug>` is still recognized), the optional untracked ad-hoc override (`attach-branch`), and the canonical OFF-by-default sentence with the full precedence chain. No CLI flag tables — README is conceptual.

### `CLAUDE.md`

- **Add one Architecture bullet/paragraph** naming the three cycle-free homes — `plan_tool/project_config.py` (config leaf), `plan_tool/branch_binding.py` (git-config override store), `plan_tool/branch_ownership.py` (the two lookups + 4-tier classifier) — and the run-guard seam `plan_tool/cli/run_cmd.py:_preflight_branch_guard`. State the OFF-by-default flag so an agent reading CLAUDE.md knows the feature is inert unless enabled. Keep it terse (Concise-docs preference).

### `BACKLOG.md`

- **Grep `BACKLOG.md` for a branch-awareness / attach-branch entry first.** Current grep finds none — the feature was seeded from `plan-seeds/` and the consolidated branch-awareness seed, **not** a BACKLOG row.
- **If absent (expected): the BACKLOG edit is a verified no-op.** Do not invent an entry to satisfy the file's presence in scope; surface the title-vs-reality gap to reconcile rather than fabricating a row.
- **If present:** remove it (shipped work leaves BACKLOG per the file's own "Remove a feature's entry when it ships" rule).

### `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` (three slots each, byte-parallel)

- **Frontmatter `description`:** extend the audit/author verb list to mention the branch verbs — e.g. add `attach-branch / detach-branch` to the parenthetical so the skill router surfaces them.
- **Subcommands at a glance:** add a **State** group entry (beside `register`/`deregister`/`sweep`) listing `attach-branch <plan> <branch>` / `detach-branch <plan>` with "No" in the Calls-claude/Calls-codex column (pure git-config writes, no backend).
- **Decision tree for common user asks:** add a row — e.g. `"run plan X on its own branch" / "bind X to branch B"` → `plan-tool attach-branch X B` (and `run X --switch-branch` for the nudge path) — with the canonical OFF-by-default note inline or adjacent.
- **Byte-parallel constraint:** make the identical slot edits in both files. The only legitimate differences are the pre-existing backend framing (`claude` vs `codex exec`, "Calls claude?" vs "Calls codex?", the codex-targeted Backend paragraph, and the Annotate-row presence already differing). A `diff` of the two after editing must show **only** those pre-existing lines plus your new rows in identical form.

### Foundational logic & shared locations

- **Foundational logic of this step:** the single canonical OFF-by-default sentence replicated across surfaces (a documentation invariant, not code).
- **Parallel surface set:** the six-surface documentation footprint is itself the shared pattern — the project lesson records that documenting a plan-tool subcommand touches RUNBOOK + README + CLAUDE + BACKLOG + both SKILL.md. No code call sites are exercised by this step.

### Two load-bearing non-edits (do NOT touch)

- **`PLAN_FORMAT.md` — out of footprint.** The ad-hoc binding lives in untracked **git config** (`plan-tool.binding.<slug>`), not plan frontmatter; `PLAN_FORMAT.md` documents only frontmatter, so it has nothing to add. Editing it would mis-locate the binding.
- **`docs/*_FLOW.md` flow docs (`RUN_FLOW.md`, `AUDIT_FLOW.md`, `*_RESUME_FLOW.md`) — out of footprint.** The run guard and create-collision gate are **not** reuse/caching/memoization features, so the "reuse feature revises the three flow-doc homes" lesson does not trigger — there is no fingerprint-reuse axis to document. Route any flow-doc gap a later audit finds to reconcile rather than expanding this step.

## Tests

N/A — non-code step. See [Verification](#verification-non-code-step).

### Verification (non-code step)

This step changes no production code; verify the artifacts directly:

- `plan-tool --help` lists `attach-branch` and `detach-branch` — every documented verb resolves at top level.
- `plan-tool run --help | grep -- --switch-branch` succeeds — the documented `run` flag exists.
- `plan-tool create --help` does **not** list `--force` or `--allow-non-default-branch` on **`create`'s own subparser** (the sibling `detail` subparser does carry `--force` — scope the check to `create`, don't conflate the two) — confirms no doc names a flag `create` lacks.
- `diff integrations/claude/SKILL.md integrations/codex/SKILL.md` shows only the pre-existing differences (the backend-framing lines and the claude-only Annotate row) plus the new branch rows in identical form — byte-parallel preserved.
- Every internal markdown link added (RUNBOOK ToC anchor → new workflow heading; README/CLAUDE cross-links) resolves to a real heading slug.
- The canonical OFF-by-default sentence appears verbatim at RUNBOOK quick-ref, the new RUNBOOK workflow, the README concept paragraph, the CLAUDE Architecture note, and both SKILL.md surfaces — grep one distinctive substring (e.g. `branch_awareness`) across all six files and confirm presence.
- `grep -i branch BACKLOG.md` confirms the no-op (no fabricated entry) or that the shipped entry was removed.

## Acceptance criteria

- All six surfaces (`RUNBOOK.md`, `README.md`, `CLAUDE.md`, `BACKLOG.md`, `integrations/claude/SKILL.md`, `integrations/codex/SKILL.md`) reflect the step's intent — branch verbs documented, BACKLOG reconciled (entry removed or verified-no-op).
- The canonical OFF-by-default sentence is present verbatim at RUNBOOK, README, CLAUDE, and both SKILL.md surfaces.
- `plan-tool --help` carries `attach-branch`/`detach-branch`; `run --help` carries `--switch-branch`; `create --help` carries no `--force`/`--allow-non-default-branch`.
- `diff` of the two SKILL.md files shows only pre-existing differences (backend framing and the claude-only Annotate row) plus the identical new branch rows.
- `PLAN_FORMAT.md` and all `docs/*_FLOW.md` files are byte-unchanged.
- No added internal markdown link is broken.

## References

- [Git - git-config Documentation](https://git-scm.com/docs/git-config) — the `git config --local plan-tool.binding.<slug>` store the docs describe as the ad-hoc override's home; cite for the "untracked, machine-local" framing.
- [Git - git-check-ref-format Documentation](https://git-scm.com/docs/git-check-ref-format) — the ref-validity rules behind `branch_prefixes`/derived names; cite when documenting that `<prefix><slug>` must be a valid branch name.
- [Git - git-symbolic-ref Documentation](https://git-scm.com/docs/git-symbolic-ref) — default-branch detection underpinning the create-collision warning's "from the default branch" behavior the RUNBOOK/README describe.

## Deferred

- `PLAN_FORMAT.md` — out of footprint; the binding lives in git config, not frontmatter. No edit.
- `docs/RUN_FLOW.md` / `docs/AUDIT_FLOW.md` / `docs/*_RESUME_FLOW.md` — out of footprint; the run guard and create gate are not reuse/caching features. Route any later-found gap to reconcile.
- Consolidating the duplicated canonical sentence into a single included snippet — the repo has no doc-include mechanism; verbatim replication is the intended technique. Not a follow-up.
- A dedicated `docs/BRANCH_AWARENESS.md` deep-dive — not requested by this plan; the six surfaces plus the per-step detail files cover the feature. Candidate for a future docs backlog item if the surface area grows.
