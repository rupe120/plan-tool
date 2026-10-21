> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Update the install-skill docs, close out BACKLOG #370, and retire the roadmap primer

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Steps 1–4 ship the router/shared-reference architecture in code and content; nothing outside those files yet says so. This step brings the surrounding docs into agreement with that shipped state: `README.md`'s "Optional: the agent skill" section and `docs/ARCHITECTURE.md` gain an accurate description of the two-file, three-integration install, `integrations/shared/DIRECTIVES.md`'s own wiring note gets a third distribution path (the file now travels with every `install-skill` run, not only the machine-local symlink and the `CLAUDE.md` pointer), and `handoffs/2026-09-16-roadmap-orchestration-primer.md` is retired now that step 1 satisfies its own stated retirement condition — after checking the file's other sections, which that condition does not cover, for anything with no other recorded home. `BACKLOG.md` #370 is then removed outright (this repo's default closure — no re-open condition here is worth preserving in `docs/history/backlog-decisions.md`), and every citation of the identifier across `BACKLOG.md` and `backlog-arc-installed-skill.md` that currently describes it as a live, unshipped blocker is rewritten to the post-shipment reality, not merely stripped of the number. A confirmed, adjacent gap — `plan_tool/cli/__init__.py`'s command-catalog docstring and its pinned golden snapshot still describe a two-integration `install-skill` after step 4 ships a third — is closed here too, since no earlier step's declared files cover it. On green, every doc a reader would consult about the installed skill agrees with what steps 1–4 actually shipped, and no tracked file still argues that #370 needs to land.

## Table of Contents

- [Why](#why) — why doc accuracy has to wait for steps 1–4 and land in one place
- [Input](#input) — what steps 1–4 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — the six declared files, two confirmed additions, and one conditional one
- [Implementation](#implementation) — the doc-by-doc edits and the BACKLOG/arc-doc sweep
- [Tests](#tests) — the golden-snapshot regen and the hand/grep checks
- [Acceptance criteria](#acceptance-criteria) — observable facts a reviewer can check
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step
- [Deferred](#deferred) — work this step explicitly does not do

## Why

Steps 1–4 each declare, in their own `## Deferred` sections, that `docs/ARCHITECTURE.md`, `README.md`, `integrations/shared/DIRECTIVES.md`'s wiring note, and `BACKLOG.md` #370's removal belong to "step 5" — none of them touch those files. Until this step lands, a reader following `README.md` or `docs/ARCHITECTURE.md` sees the old single-file, two-integration installer, and `integrations/shared/DIRECTIVES.md`'s own note about how it reaches an assistant doesn't mention the distribution path this whole plan builds. `BACKLOG.md` #370's five-item arc (`backlog-arc-installed-skill.md`) is written entirely in terms of #370 as a live, unshipped gate — sequencing language ("#370 first — mandatory", "this arc hands off once #370 ships") that becomes actively misleading, not merely stale, once the work ships: it argues the just-landed step 1 is still pending, which is the same failure this repo's own forward-looking-docs convention (`CLAUDE.md` § "Documentation is forward-looking") warns against for exactly this reason — a claim that was true when written and never revisited reads as current design to the next reader.

## Input

This step depends on steps 1–4 landing first (`depends_on: 1, 2, 3, 4`) and documents their outcomes without re-deriving them:

- **Step 1's outcome** — `integrations/shared/DIRECTIVES.md` carries a new `# Roadmap` section (with `## Roadmap non-stage routes` and `## Roadmap rewrite` subsections) between the front-matter block and `# The two audit gates`. This step's own edit to the file's wiring note sits earlier in the document, before `## Invocation and discovery` — it does not touch, reorder, or insert content inside the `# Roadmap` … `# The two audit gates` span, which step 1's `tests/test_roadmap_format.py` guide-sweep tests bound by heading text.
- **Step 2's outcome** — `plan-tool install-skill` installs an ordered, pre-checked set of `(router, DIRECTIVES.md)` pairs: both files land together under the resolved destination root (default `<root>/skills/plan-tool/`, or the `--user`/`--root .agents` variants), a foreign file at either path blocks the whole set without `--force`, and an already-correct path is never rewritten. This is the concrete behavior this step's `README.md` and `docs/ARCHITECTURE.md` edits describe.
- **Step 3's outcome** — `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` both carry a bare (`DIRECTIVES.md`, no path prefix) link to the shared reference, no restated roadmap or convergence-loop prose, and every reference to a doc that can't travel with the install rewritten in the plain-name-plus-repo-caveat form.
- **Step 4's outcome** — `integrations/cursor/SKILL.md` exists, `install-skill --integration` accepts `("claude", "codex", "cursor")`, and `docs/cli/install-skill.md` / `docs/cli/README.md` are already regenerated to show the third choice — this step does not re-touch either generated file. Step 4 also fixes three "Claude Code / Codex" phrases inside `plan_tool/cli/skill_cmd.py` itself (module docstring, `cmd_install_skill`'s docstring, the `install-skill` subparser's `help=` string) but explicitly leaves `plan_tool/cli/__init__.py`'s separate command-catalog docstring untouched, naming it "outside this step's declared `files:` list" and "a minor prose gap for a follow-up" — see [Implementation](#implementation)'s CLI help-text bullet for why this step is that follow-up.

## Files (creates vs edits)

- **New files:** none.
- **Deleted files:**
  - `handoffs/2026-09-16-roadmap-orchestration-primer.md` — retired via `git rm` once its own retirement condition is met and its other content is checked (see Implementation). This repo has no `handoffs/archive/` directory; retired handoffs are deleted outright (confirmed by `git log --diff-filter=D -- handoffs/`), and `handoffs/README.md`'s "## Current handoffs" index never listed this file, so no index edit follows from the deletion.
- **Existing files (edits only):**
  - `docs/ARCHITECTURE.md` — a short new subsection describing the installed-skill architecture.
  - `README.md` — the "### Optional: the agent skill" section: three-backend parity and the `--integration` example.
  - `integrations/shared/DIRECTIVES.md` — the "Who reads this, and how it is wired" lead-in only; no other content in this file changes in this step.
  - `BACKLOG.md` — remove the `#370` entry; sweep every citation of it that describes it as open or blocking.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-installed-skill.md` — full pass over the sections narrating #370 as unshipped.
- **Confirmed additions beyond the declared list (needed to close a real, verified gap no other step covers):**
  - `plan_tool/cli/__init__.py` — the command-catalog docstring's `install-skill` line still names only "Claude Code / Codex" after step 4 ships Cursor; add it.
  - `tests/cli/package_surface_help.golden.txt` — the self-seeding golden snapshot of `plan-tool --help` embeds both that docstring and (once step 4 lands) `skill_cmd.py`'s already-updated subparser help text; regenerate it, never hand-edit it.
- **Conditional addition:** if the own-HEAD check of the retiring primer handoff (see Implementation) finds *any* content with no other recorded home — Integration/AI-DLC status or otherwise (e.g. `## Model selection`) — it gets a stated destination, not only Integration/AI-DLC content. Integration/AI-DLC status content's destination is most likely `docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md`, the file the primer's own content maps to; a non-Integration observation with no other home (per `docs/TRACKING.md`'s "life of an item" convention that anything found along the way gets filed) becomes a new `BACKLOG.md` entry instead. Whether either file needs touching is a fact to establish at implementation time, not assumed here.

## Implementation

### `README.md` — "### Optional: the agent skill"

- Replace "The bundled skill is only for letting **Claude Code** (or Codex) orchestrate it *for* you" with all three supported backends, matching the plan's own parity principle (its Architecture section: "Every supported assistant — Claude Code, Codex, Cursor").
- The prose line "`--root .agents` and `--integration codex` switch the destination root and the bundled variant" is the step title's named target: widen it so the `--integration` example covers `cursor` too (e.g. `--integration codex|cursor`), not just `codex`.
- Worth a line for accuracy, since it's now materially true: install now places two files (the router and the `DIRECTIVES.md` sibling) as one set, not one file — a reader running the existing bash block would otherwise be surprised by the second file appearing. Keep it to one sentence; the mechanism is step 2's, not this step's to re-explain.

### `docs/ARCHITECTURE.md`

- The `skill_cmd.py` | `install-skill`. module-map row stays a one-line pointer, matching every sibling row in that table — don't expand it in place.
- Add a short new `##`-level subsection (the file's existing pattern for a subsystem that needs more than a one-line row — see `## Rate-limit recovery loop`, `## Jira export`) describing what ships: the two-phase check-then-write install of a router plus its `DIRECTIVES.md` sibling as one set (step 2), the router/reference split rule itself (router answers "which command", reference owns "the rules" — the plan's own Architecture section states this split; restate it briefly, don't re-derive it), and the three supported `--integration` values. Cite `plan_tool/cli/skill_cmd.py`, `integrations/shared/DIRECTIVES.md`, and the per-integration `integrations/<name>/SKILL.md` files as the real symbols/paths, not this plan's step numbers. Placement is a judgment call — near the other CLI-verb-scoped sections (`## Jira export`, `## Roadmap`) reads naturally, but nothing pins an exact position.

### `integrations/shared/DIRECTIVES.md` — the wiring note

- The bolded "**Who reads this, and how it is wired.**" lead-in (before `## Invocation and discovery`) names two distribution paths today: the machine-local `~/.claude/directives/plan-tool.md` symlink, and a project `CLAUDE.md` pointer. Neither mentions that `plan-tool install-skill` — once step 2 lands — places this exact file as a literal sibling of the installed router in *any* consuming repo, for all three backends, without depending on either existing path.
- Add this as a third path (or a lead sentence ahead of the existing two, since it's now the primary way most consuming repos get the file): name `plan-tool install-skill`, that it installs the file beside the chosen backend's router at the resolved destination, and that this reaches Claude Code, Codex, and Cursor sessions directly. Keep the existing symlink and `CLAUDE.md`-pointer bullets — they still matter (the symlink is specific to this repo's own workstation; the `CLAUDE.md` pointer covers a session before `install-skill` has been run).
- This is a wiring-mechanics addition, not new driving-rule content — the plan's Scope guardrails bar rewriting or re-deriving `DIRECTIVES.md`'s content beyond relocating roadmap guidance and moving router-shaped prose; describing how the file itself gets distributed is the one thing this step's title explicitly assigns to it and is outside that bar's subject (the driving rules the file states), not a violation of it.
- Do not touch anything else in the file — no other section is in this step's declared edit.

### Retire `handoffs/2026-09-16-roadmap-orchestration-primer.md`

- The file's own `## Status` section states its retirement condition precisely: "Retire this file once #370's step 1 lands (relocating roadmap operational guidance into `integrations/shared/DIRECTIVES.md`)." Step 1 is exactly that relocation. That condition covers the file's router/how-to-use content — `## How to use it` and `## Reading order, and why each matters` exist only because `DIRECTIVES.md` was thin on roadmap guidance, which step 1 fixes.
- That condition does **not** cover the rest of the file. Read the whole file at its actual state when this step runs (not this detail's 2026-09-16 snapshot — time will have passed and other work may have landed) before deleting it. At minimum, check `## Model selection`, `## Repository discipline`, `## Current state for the Integration / AI-DLC exercise specifically` (the file's own text marks this "Integration-specific and goes stale independently of the rest of this file"), `## Backlog identifiers`, and `## References` against `BACKLOG.md`'s current #383/#384/#385/#367 entries and the roadmap/Integration arc docs (`docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md`, `docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md`). For each piece: if it's already recorded there, it's safe to drop with the rest of the file; if nothing else records it, migrate it — state the destination explicitly rather than leaving the migration to inference (`backlog-arc-integration-mvp.md` is the more likely home, since it's the file this repo already routes Integration-specific status into).
- One concrete example of "already resolved, confirmed safe to drop": the duplicate-`BACKLOG.md`-id caution this file's Integration-status section once needed cross-referencing (`#362`/`#363`/`#364`) is no longer live — `BACKLOG.md` currently lists all three as distinct, non-duplicate entries, and `git log -- handoffs/2026-09-16-roadmap-orchestration-primer.md` shows a later commit ("Archive settled backlog decisions and resolve duplicate IDs") already resolved it. This is one data point demonstrating the check, not a substitute for running it fresh against whatever the file and `BACKLOG.md` actually say when this step executes.
- Grep the repo for `roadmap-orchestration-primer` before deleting to confirm nothing besides this plan's own step text and its saved completeness reports (historical audit snapshots under this plan's `plan-details/.../reports/`, not live docs) references it by filename. If a new live reference has appeared since this detail was authored, resolve it before deleting.
- Delete with `git rm`, matching this repo's existing convention for every other retired handoff (no archive directory).

### `BACKLOG.md` — remove #370, sweep every citation that treats it as open

- Remove the whole `**#370 — Thin skill routers over one installer-carried shared reference**` entry. This is plain removal, not a "Closed —" conversion: `docs/TRACKING.md`'s "The life of an item" step 5 default is "Remove the entry when the work ships," moving it to `docs/history/backlog-decisions.md` only "when a re-open condition is worth keeping" — #370 is a settled architecture decision fully superseded by the shipped code and this plan's own commit history, with nothing worth preserving as a reopen trigger, and the plan's own Acceptance criteria already say "removed," not "closed."
- Sweeping means fixing every citation that currently reads #370 as a live, open, or blocking item — not deleting the numeral and leaving the surrounding sentence broken. At minimum:
  - The `backlog-arc-installed-skill.md` arc-index bullet's item list in `BACKLOG.md`'s own arc-index section — drop `#370` from the enumerated `(#370, #371, #377, #378, #379)`.
  - `#371`'s `Dependencies` field ("sequence after #370 if both are taken — #370 rewrites the same files..."), its `Out of scope / Non-goals` bullet ("the router/reference architecture (#370)"), and its `Origin` field ("same disk audit as #370").
  - `#377`'s `Dependencies` field ("sequence after #370, which establishes..."), its `Out of scope / Non-goals` bullet ("expanding #370's router architecture..."), and its `Origin` field ("...#370 should stay focused on the router").
  - `#378`'s `Why` bullet ("Cursor has no router (#370)" — now false), its `Dependencies` field, and its `Readiness` field (`blocked-on #370` → `ready`, since the blocker shipped) — plus its `Risks` bullet ("touching the Claude router's lines twice if this lands before #370 thins it"), its `In scope` bullet ("the router pointers as #370 leaves them"), and its `Verification` bullet ("extends #370's install test"), each of which also cites #370 and needs the same shipped-and-dated correction.
  - `#379`'s `Dependencies` field ("#370, for the installed reference...") and its `Readiness` field (`blocked-on #370` → `ready`).
  - For each, name the fact as shipped (e.g. "the skill-router-and-shared-reference plan, shipped 2026-09-16") rather than only deleting the digits — a `Readiness: blocked-on` with nothing after it, or a `Dependencies:` note that no longer explains why the item was ever sequenced, is not an acceptable result.
- Leave `#386`'s `Why`/`Origin` citations of #370 (e.g. "measured directly on 2026-09-16 while driving `BACKLOG.md` #370...") unchanged — they already read as dated, past-tense provenance for an event that happened, which is exactly the warranted-history case `CLAUDE.md` § "Documentation is forward-looking" describes; they don't dangle because nothing in them claims #370 is still open.
- `docs/implementation-plans/archive/2-orchestrator-owned-convergence-eval.md` and `handoffs/2026-09-14-developer-docs-and-tracking.md` both contain "#370" strings, but confirmed at authoring time to name a different, already-retired id range ("#368 and #370–#375," evaluator-adapter governance work retired as moot before the current #370 was assigned to this effort). Both are frozen historical records outside this step's declared files; leave them untouched.

### `docs/implementation-plans/backlog-arcs/backlog-arc-installed-skill.md`

- This needs a full pass over the sections that narrate #370 as a live, unshipped gate — `## File intent`, `## Details`, `## Choose this arc when`, `## Ordered route`, `## Decision gates`, and `## Exit and handoff` — not a search-and-replace of the digits. `## Choose this arc when` (line 64) reads "even though #383/#384 are exactly the kind of content #370's future DIRECTIVES.md relocation could eventually carry" — a live claim that the relocation hasn't happened yet, false the moment step 1 lands it. Most of the staleness here is in present/future-tense narrative that doesn't contain the string "#370" at all (e.g. "Root of this arc: nothing else here can land correctly until the installer carries more than one file," which describes step 1's outcome as not-yet-true), so grep for the identifier alone will not find every sentence that needs rewriting.
- The target state: every sentence currently arguing #370 still has to land — "#370 is the one hard dependency," "1. #370 first — mandatory," "This arc hands off once #370 ships," "#370 alone unblocks everything downstream" among them — reads as shipped and dated (e.g. "shipped 2026-09-16," citing `docs/implementation-plans/2-skill-router-and-shared-reference.md`). The sequencing relationships that don't depend on #370's identifier at all — #378 preferring to land after whichever of #371/#377 a session also takes, #379 sequencing after #378 — stay as-is, since those are real orderings between the four still-open items.
- The arc's own `## Exit and handoff` condition ("hands off once #370 ships") is now satisfied by this plan's shipment — say so explicitly, and clarify that the arc doc itself isn't retired: `BACKLOG.md`'s arc-index line still calls it "the sole router" for #371/#377/#378/#379, so it keeps that role even though its original sequencing job (getting #370 landed first) is done.
- `## Out of scope`'s "beyond what #370 already settled" clause needs the same shipped-and-dated framing as the rest.

### CLI help-text integration coverage

- `plan_tool/cli/__init__.py`'s command-catalog docstring line for `install-skill` ("Install the bundled Claude Code / Codex skill...") is confirmed at HEAD to still read this way, and step 4's own Deferred section confirms it's untouched by any earlier step. Update it to name all three integrations, matching whatever phrasing step 4 lands in `plan_tool/cli/skill_cmd.py`'s own docstrings and `help=` string (e.g. "Claude Code / Codex / Cursor").
- `tests/cli/package_surface_help.golden.txt` is a self-seeding snapshot of `cli.build_parser().format_help()` (`tests/cli/test_package_surface.py::TestHelpGoldenSnapshot::test_help_matches_golden`) — it embeds both this docstring's text and `skill_cmd.py`'s subparser `help=` string (already updated by step 4). Both sources change across steps 4 and this step, so the golden file goes stale the moment they land; regenerate it with `UPDATE_CLI_GOLDEN=1 uv run pytest tests/cli/test_package_surface.py -q` and commit the result. Never hand-edit it.

## Tests

This step's `change_type` is `refactor` (the plan touches `plan_tool/cli/__init__.py`, a production Python file, so `non-code` would misclassify it). Since this plan sets `enforce_step_tests: true`, `run`'s automatic test-authorship gate applies and is satisfied because this step modifies `tests/cli/package_surface_help.golden.txt`, a path under `tests/` — not because the gate is skipped. Verification is the concrete checks below.

### Tests for this step

- `tests/cli/test_package_surface.py::TestHelpGoldenSnapshot::test_help_matches_golden` — passes once `tests/cli/package_surface_help.golden.txt` is regenerated (`UPDATE_CLI_GOLDEN=1 uv run pytest tests/cli/test_package_surface.py -q`, then a normal re-run with no env var to confirm the committed file matches) — pins that the CLI's own `--help` text and its golden snapshot agree on naming all three integrations.
- `uv run pytest tests/test_roadmap_format.py tests/cli/test_skill_cmd.py tests/test_model_specs.py -q` — regression check that this step's `DIRECTIVES.md` wiring-note edit (which sits before the `# Roadmap` section step 1 adds) does not disturb the heading-bounded guide-sweep assertions those steps' tests depend on.

### Verification (hand checks beyond the gated test file)

1. `grep -rn '#370' BACKLOG.md` — every remaining hit is a dated, past-tense provenance citation (`#386`'s `Why`/`Origin`), never a present-tense claim that #370 is open, pending, or a dependency.
2. `grep -n '#370' docs/implementation-plans/backlog-arcs/backlog-arc-installed-skill.md` — any surviving hit reads as shipped and dated, not as a live blocker.
3. `test ! -f handoffs/2026-09-16-roadmap-orchestration-primer.md` — the file is gone; `git log --follow -- handoffs/2026-09-16-roadmap-orchestration-primer.md` still shows its history.
4. `grep -rln 'roadmap-orchestration-primer' . --include='*.md'` (outside `.git`) — no hits besides this plan's own step text and its pre-existing saved completeness reports.
5. Read `#371`'s, `#377`'s, `#378`'s, and `#379`'s `Readiness`/`Dependencies` fields end-to-end and confirm each reads as a complete, accurate sentence — not a field with the identifier deleted and nothing put in its place.
6. Read `README.md`'s "Optional: the agent skill" section and confirm the `--integration` example names `cursor`, and the backend list names all three.
7. Read `docs/ARCHITECTURE.md`'s new subsection and confirm every cited symbol/path (`plan_tool/cli/skill_cmd.py`, `integrations/shared/DIRECTIVES.md`, the per-integration `SKILL.md` files) resolves against the actual landed tree, not a paraphrase of steps 1–4's detail files.
8. Read `integrations/shared/DIRECTIVES.md`'s wiring note end-to-end and confirm the new install-skill path is additive — it doesn't contradict, duplicate, or redesign the existing symlink/`CLAUDE.md`-pointer bullets.
9. `uv run pytest tests/cli/test_package_surface.py -q` (no env var set) passes against the committed golden file.

## Acceptance criteria

- `handoffs/2026-09-16-roadmap-orchestration-primer.md` no longer exists in the working tree; any content it carried with no other recorded home — Integration/AI-DLC status or otherwise (e.g. `## Model selection`) — has a stated new home, either the Integration arc doc or a new `BACKLOG.md` entry.
- `BACKLOG.md` has no `#370` entry, and no remaining citation of the identifier describes it as open, pending, or blocking.
- `#371`, `#377`, `#378`, and `#379`'s `Dependencies`/`Readiness`/`Out of scope`/`Origin` fields read as complete, accurate sentences reflecting #370's shipped state; `#378` and `#379`'s `Readiness` reads `ready`, not `blocked-on #370`; `#378`'s `Risks`, `In scope`, and `Verification` bullets also no longer cite #370 as unshipped.
- `docs/implementation-plans/backlog-arcs/backlog-arc-installed-skill.md`'s `## File intent`, `## Details`, `## Choose this arc when`, `## Ordered route`, `## Decision gates`, and `## Exit and handoff` sections describe #370 as shipped and dated, not as a live gate.
- `README.md`'s "Optional: the agent skill" section names Claude Code, Codex, and Cursor, and its `--integration` example covers `cursor`.
- `docs/ARCHITECTURE.md` describes the two-file, three-integration installed-skill architecture.
- `integrations/shared/DIRECTIVES.md`'s wiring note names `plan-tool install-skill` as a distribution path for the file itself.
- `plan_tool/cli/__init__.py`'s command-catalog docstring names all three integrations for `install-skill`.
- `tests/cli/package_surface_help.golden.txt` matches a fresh render of `plan-tool --help`; `uv run pytest tests/cli/test_package_surface.py tests/test_roadmap_format.py tests/cli/test_skill_cmd.py tests/test_model_specs.py -q` passes in full.

## Applicable guardrails

- The plan's "## Scope guardrails" first bullet (do not rewrite, re-argue, or re-derive `DIRECTIVES.md`'s content beyond relocating roadmap guidance and moving router-shaped prose out of the routers) bounds this step's only `DIRECTIVES.md` edit to the wiring note's distribution-path description — no other content in that file changes here, and the wiring note's subject (how the file reaches an assistant) is distinct from the driving rules the guardrail protects.
- The plan's "## Scope guardrails" second bullet (no drift check, lint, gate, or exit-code flip) means every check in [Tests](#tests) beyond the golden-snapshot regen is a hand check, not a new automated assertion.
- The plan's "## Scope guardrails" third and fourth bullets (no skill frontmatter trigger-field changes; no backend-selection or runtime-behavior change) are not implicated by this step — nothing here touches `SKILL.md` frontmatter, `backend.json`, or command behavior.
- The plan's "## Out of scope" excludes retiring the machine-local `~/.claude/directives/plan-tool.md` symlink and any `plan-tool init` pointer-writing work — this step's wiring-note edit adds a path alongside the symlink, it does not touch or retire it.
- BACKLOG #371 (cited in the plan's Scope guardrails as a separate effort) owns skill frontmatter trigger fields — untouched here, including in the CLI help-text fix, which only changes descriptive prose.

## Deferred

- BACKLOG #371 (skill frontmatter trigger fields), #377 (seed authoring), #378 (out-of-scope discovery capture), and #379 (stale-entry updates) — this step corrects their `#370`-dependency bookkeeping only; their own `What`/`Outcome`/`Route`/`Tier` content is untouched.
- A drift guard or lint between the shipped docs and the installed skill's actual content — the plan's own top-level `## Deferred` section routes this out permanently; one shared reference file is the anti-drift mechanism.
- Implementing any Integration/AI-DLC roadmap capability (#383, #384, #385) the retiring primer handoff described — this step preserves the pointer/record if one is missing elsewhere, not the underlying work.
- Editing `docs/implementation-plans/archive/2-orchestrator-owned-convergence-eval.md` or `handoffs/2026-09-14-developer-docs-and-tracking.md` — their "#370–#375" mentions name a different, already-retired id range and are frozen historical records outside this step's declared files.
- Editing `handoffs/README.md` — confirmed the primer handoff was never listed in its "## Current handoffs" index, so its deletion leaves no dangling entry there.
- `docs/cli/install-skill.md` and `docs/cli/README.md` — already regenerated by step 4 to show the `cursor` choice; this step does not re-touch either generated file.
