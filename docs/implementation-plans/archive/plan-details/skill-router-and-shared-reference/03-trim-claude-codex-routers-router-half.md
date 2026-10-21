> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Trim the Claude and Codex routers to the router half, pointing at `DIRECTIVES.md`

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`integrations/claude/SKILL.md` carries two things `integrations/shared/DIRECTIVES.md` now owns (once step 1 lands): the ~100-line `## Convergence tail in a Claude session` section, and the multi-sentence roadmap flag/refusal prose spread across four decision-tree rows and three Subcommands-at-a-glance rows. This step deletes that restated content from both routers, replacing each affected row with a one-line pointer (entry command plus a `DIRECTIVES.md` citation), and gives `integrations/codex/SKILL.md` — which starts with none of this today — the identical pointer set. It also repoints every link that can no longer resolve: the three in-page anchors to the deleted convergence-tail section, and the pre-existing `../../RUNBOOK.md`/`../../README.md`-style cross-file links in both routers, using the plain-name-plus-repo-caveat form the existing "Going deeper" section already uses. `tests/test_roadmap_format.py`'s guide-sweep dictionaries lose their now-false `"integrations/claude/SKILL.md"` entries (the equivalent `"integrations/shared/DIRECTIVES.md"` entries land with step 1 and keep sweeping the real content). On green, both routers answer "which command" without restating any rule `DIRECTIVES.md` owns, and every doc-to-doc reference in either file resolves or is honestly labeled as repo-only.

## Table of Contents

- [Why](#why) — why the router's own convergence/roadmap prose becomes a liability once `DIRECTIVES.md` owns it
- [Input](#input) — what steps 1 and 2 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — the eight declared files and what each needs
- [Implementation](#implementation) — the row-by-row trim, the link repoints, and the Codex additions
- [Tests](#tests) — the guide-sweep dictionary edits and the regression checks that must stay green
- [Acceptance criteria](#acceptance-criteria) — observable facts a reviewer can check
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step
- [Deferred](#deferred) — work this step explicitly does not do

## Why

`integrations/claude/SKILL.md` today carries the *only* copy of the roadmap flag semantics and the *only* copy of the session-directed convergence procedure — the plan's Problem statement and Architecture section both name this as the reason a Codex session driving `plan-tool` has "no convergence discipline and no knowledge that the `roadmap` verb exists." Once step 1 relocates that content into `DIRECTIVES.md` and step 2 makes it install as a real sibling file, leaving the router's copy in place is no longer neutral: it is now duplicated prose two documents can drift apart on, which is exactly what the Architecture section's "the reference owns the rules" split exists to prevent. Trimming to a one-line pointer per row is what keeps the router answering "which command" without forcing every session to read the long reference first — the same section warns that over-moving invocation/decision-tree prose into the reference is the opposite failure.

The router's own `../../RUNBOOK.md`-style links were already broken before this step (per the plan's Problem statement — no relative depth from either the source or installed location resolves them), and the Architecture section explicitly folds fixing them into this step: "step 3 applies that same [plain-name-caveat] convention everywhere a link can no longer resolve — the remaining inline cross-file links, and any in-page anchor... that would otherwise point at nothing once trimming lands." So this step's link-hygiene work covers both categories: links broken by *this step's own deletions* (the convergence-tail anchor) and links that were *already* broken (the RUNBOOK/README worktree and recovery links), which this step happens to be the one touching this file to fix.

## Input

This step depends on steps 1 and 2 landing first (`depends_on: 1, 2`), and reads their outcomes without restating their mechanics:

- **Step 1's outcome** — `integrations/shared/DIRECTIVES.md` carries a new `# Roadmap` section with `## Roadmap non-stage routes` and `## Roadmap rewrite` subsections, holding the flag semantics, refusal states, and exit-code behavior this step is about to delete from the Claude router's prose. Step 1 also adds a `"integrations/shared/DIRECTIVES.md"` entry to each of `_SOURCE_ADMISSION_GUIDES`/`_SOURCE_ADMISSION_GUIDANCE`/`_SOURCE_ADMISSION_ISOLATION`, `_STRUCTURAL_ROUTE_GUIDES`/`_STRUCTURAL_ROUTE_GUIDE_BOUNDS` (bounded `("## roadmap rewrite", "# the two audit gates")`), and `_NON_STAGE_BRIEF_DRIFT_GUIDES` in `tests/test_roadmap_format.py` — these are the entries that keep sweeping the roadmap content once this step removes the router's own copy.
- **Step 2's outcome** — `install-skill` places `DIRECTIVES.md` as a literal sibling of the installed `SKILL.md` (same destination directory, both symlink and `--copy` modes). This is what makes a bare relative link (`DIRECTIVES.md`, no path prefix) resolve from the *installed* router — the fact this step's "cite by bare name" instruction depends on.
- **What this step reads but does not touch:** `DIRECTIVES.md`'s exact heading text (`# The session-directed convergence loop`, `# The two audit gates`, `# Roadmap`, `## Roadmap non-stage routes`, `## Roadmap rewrite`) — these are the anchor targets this step's pointer links cite, not content this step authors.

## Files (creates vs edits)

No new files.

- **`integrations/claude/SKILL.md`** — remove the `## Convergence tail in a Claude session` section; collapse its four roadmap decision-tree rows and three Subcommands-at-a-glance roadmap rows to one-line pointers; collapse the two convergence-discipline decision-tree rows and the completeness-audit row's annotation to one-line pointers; repoint all three now-dangling `#convergence-tail-in-a-claude-session` anchor links; repoint the four `../../RUNBOOK.md` / `../../README.md`-style cross-file links; add a bare-name citation to `DIRECTIVES.md`.
- **`integrations/codex/SKILL.md`** — add the same seven roadmap pointer rows/groups and the same two convergence-discipline pointer rows plus the completeness-audit annotation, in the same relative positions Claude's trimmed router uses; repoint the same three `../../`-style cross-file links; add the same bare-name citation to `DIRECTIVES.md`.
- **`tests/test_roadmap_format.py`** — remove the `"integrations/claude/SKILL.md"` key from `_SOURCE_ADMISSION_GUIDES`, `_SOURCE_ADMISSION_GUIDANCE`, `_SOURCE_ADMISSION_ISOLATION`, `_STRUCTURAL_ROUTE_GUIDES`, `_STRUCTURAL_ROUTE_GUIDE_BOUNDS`, and `_NON_STAGE_BRIEF_DRIFT_GUIDES`; drop it from the two hardcoded expected-name-set literals in `test_non_stage_brief_drift_guidance_sweep_matches_landed_contract` and `test_structural_rewrite_route_guidance_sweep_covers_every_named_public_guide`.
- **`tests/cli/test_skill_cmd.py`** — audited at HEAD: no case reads SKILL.md's roadmap or convergence-tail prose (every assertion is about install mechanics — symlink targets, byte equality, collisions). No edit anticipated; re-confirm once step 2's own edits to this file have landed (this step depends on step 2), since step 2 rewrites its helpers.
- **`plan_tool/cli/__init__.py`, `plan_tool/cli/parser.py`, `plan_tool/cli/review_cmd.py`, `plan_tool/cli/inspect.py`** — audited at HEAD: every comment/docstring naming a `SKILL.md` section cites `"Subcommands at a glance"`, the `"three audit verbs"` framing, or `"Not yet implemented / out of scope"` — none of which this step removes or renames. No edit anticipated unless the router edits below turn out to rename one of those three sections (they don't).

## Implementation

**Cite `DIRECTIVES.md` by bare name.** Add a real, resolving markdown link — `[DIRECTIVES.md](DIRECTIVES.md)`, no `../` prefix — to both routers, naming it as the shared reference for the rules the router no longer restates (the two audit gates, the convergence loop, roadmap operational detail, `--iterate`/`--commit`, reconcile directionality, seed authoring). One reasonable placement: a sentence appended to the existing "This file is the router..." intro paragraph, plus a bullet in "Going deeper" (see below). **Gotcha:** a bare `DIRECTIVES.md` link only resolves at the *installed* location, where step 2 places the two files as literal siblings — it does not resolve if someone browses `integrations/claude/SKILL.md` in the source tree on GitHub, since the source tree has no `integrations/claude/DIRECTIVES.md` (only `integrations/shared/DIRECTIVES.md`, one directory over). This is the deliberate tradeoff the plan's Architecture section makes ("a sibling resolves under both `--copy` and symlink installs; `../../`-style links never do") — do not "fix" it by writing a `../shared/DIRECTIVES.md` source-relative path, which resolves in the opposite (wrong) context.

**Delete `## Convergence tail in a Claude session` and repoint its three anchor links.** Remove the whole section from `integrations/claude/SKILL.md` (its numbered five-check procedure, the six-shape audit-shapes list, and the post-`run` reconcile/code-review loop description are now `DIRECTIVES.md`'s "The session-directed convergence loop" and "The two audit gates" sections). Three existing `](#convergence-tail-in-a-claude-session)` links then point at nothing and must repoint to `DIRECTIVES.md` (an anchored link into it, e.g. `DIRECTIVES.md#the-session-directed-convergence-loop`, is a reasonable choice since the file is a real installed sibling — no test asserts the exact slug, so this is a nice-to-have, not a blocking criterion):
- the decision-tree row "the plan finished running / every step is green"
- the decision-tree row "completeness flagged a plan-correctness/plan-completeness gap" (session-driven)
- the Subcommands-at-a-glance "Audit · completeness" row's parenthetical annotation

**Collapse the roadmap rows to one-line pointers.** Four decision-tree rows ("I have a project-sized concept, not a single feature," "rewrite one proved structural roadmap request," "analyze or inspect structural roadmap evidence," "enroll the immutable roadmap root") and three Subcommands-at-a-glance rows (`**Roadmap** (project-altitude, above the pipeline)`, `**Roadmap non-stage routes**`, `**Roadmap rewrite**`) currently carry multi-sentence flag/refusal prose. Per the Architecture section's split, each row keeps its entry command(s) and drops everything else behind a `DIRECTIVES.md` pointer. Illustrative shape (exact wording is the implementer's call):

```
| "I have a project-sized concept, not a single feature" | `plan-tool roadmap <slug> --from-existing <concept.md>` — see DIRECTIVES.md's Roadmap section for artifact layout, re-entry, and refusal semantics |
```

```
| **Roadmap** (project-altitude, above the pipeline) | `roadmap <slug> --from-existing <concept.md> [--from-stage N] [--confirm-brief-rebind]` [`--apply` [`-y`]] [`--view ...`] — see DIRECTIVES.md | Yes (`--apply`, `--view`: no) |
```

The same collapse applies to the two convergence-discipline decision-tree rows: keep the entry commands (`reconcile-code --all` then `/code-review`; the `completeness-apply` refusal), drop the multi-sentence procedure, add the `DIRECTIVES.md` pointer.

**Repoint the remaining cross-file links.** Both routers carry `../../RUNBOOK.md#recovery-common-failures` (rate-limit paragraph in "Invocation"), and Claude additionally carries `../../RUNBOOK.md` (the `--commit` paragraph in "Running from chat / automation") and `../../README.md#worktrees-parallel-plans` / `../../RUNBOOK.md#workflow-run-plans-in-parallel-worktrees` (the "run two plans at once" decision-tree row and the "Workspaces" Subcommands row); Codex's Workspaces-equivalent links point at `../../docs/OPERATIONS.md#worktrees-parallel-plans` instead of README.md — preserve that existing per-router difference rather than harmonizing it, since neither this step's title nor the plan's scope guardrails ask for it. **Codex's own link text is mismatched with its target today** (both its "run two plans at once" row and its "Workspaces" row render link text "README" while the href points at `docs/OPERATIONS.md`, a different file) — the converted plain-name form must name `docs/OPERATIONS.md`, the actual target, not "README", the current mismatched label; carrying the label forward verbatim would freeze a false, unlinked claim into prose with no way to ever catch it again. Convert each to the plain-name-plus-repo-caveat form the "Going deeper" section already uses (bold code-span name, no link, "in the plan-tool repo" framing) while keeping the specific pointed-to content in prose (e.g. "see RUNBOOK.md's Recovery section (in the plan-tool repo)" rather than dropping the "Recovery" specificity entirely). The `--commit` paragraph's link is a judgment call worth naming explicitly: `DIRECTIVES.md` now documents the same `--commit` mechanics this paragraph currently sends the reader to RUNBOOK.md for (its own `## --commit` section), so repointing it at `DIRECTIVES.md` instead is a defensible choice — but the step's title only names the convergence-tail/roadmap prose as content to relocate, so keeping this one paragraph's link on RUNBOOK.md (converted to the plain-name form) is equally acceptable.

**Bring `integrations/codex/SKILL.md` up to the same pointer set.** Codex has zero roadmap mentions and no convergence-tail row today. Add:
- the same four roadmap decision-tree rows, in the same relative position (between "I have a big doc — make a plan from it" and "author a plan and classify each step," matching Claude's order)
- a new `**Roadmap**` / `**Roadmap non-stage routes**` / `**Roadmap rewrite**` row group at the top of the Subcommands-at-a-glance table (before `**Discovery**`), matching Claude's group order and `Yes`/`No` "Calls codex?" values
- the two convergence-discipline decision-tree rows, appended after Codex's existing last row
- the same parenthetical annotation on Codex's existing `**Audit · completeness**` row (which today reads `| **Audit · completeness** (design) | \`completeness-audit <name>\`, \`completeness-apply <name>\` | Yes |` with no annotation at all)
- a `ROADMAP_FORMAT.md` bullet in Codex's own "Going deeper" list, matching Claude's existing one (the on-disk schema for `roadmap`'s four artifacts) — Codex's list has the same other six items today but is missing this one, and the plan's Architecture symmetry rule applies to this list exactly as it does to the two tables above

The lowest-risk order of operations: finish trimming Claude first, then copy its resulting pointer-line text into Codex verbatim (row text, not row position — Codex's table has no "Not yet implemented" analog gap to worry about), so the two routers end up textually identical on every row this step touches.

**What stays untouched.** The "Backend:" paragraph (model-family prefixes), the frontmatter block (`when_to_use`/`model`/`allowed-tools`/`argument-hint`), `## Authoring conventions`, and `## Not yet implemented / out of scope` are router-shaped content the Architecture section keeps in the router — none of this step's edits touch them. `tests/test_model_specs.py::TestProviderAndDefault::test_model_family_docs_cover_every_supported_prefix` reads both routers for the model-family tokens in that untouched paragraph; it must stay green as a regression check, not because this step edits it.

## Tests

### Tests for this step

- `test_source_admission_guidance_sweep_matches_landed_contract` (existing) — stays green once `"integrations/claude/SKILL.md"` is dropped from `_SOURCE_ADMISSION_GUIDES` and `_SOURCE_ADMISSION_GUIDANCE` together (the test's own `set(...) == set(...)` assertion is what requires dropping both, not just one).
- `test_source_admission_guidance_keeps_artifact_and_seed_isolation` (existing) — same pairing, for `_SOURCE_ADMISSION_ISOLATION`.
- `test_structural_rewrite_route_guidance_sweep_covers_every_named_public_guide` (existing) — asserts the trimmed `**Roadmap rewrite**` row no longer needs to satisfy the same-artifact/cross-artifact/ordering phrase checks, once `"integrations/claude/SKILL.md"` is removed from `_STRUCTURAL_ROUTE_GUIDES`/`_STRUCTURAL_ROUTE_GUIDE_BOUNDS` and from this test's hardcoded literal set.
- `test_non_stage_brief_drift_guidance_sweep_matches_landed_contract` (existing) — same removal from `_NON_STAGE_BRIEF_DRIFT_GUIDES` and its hardcoded literal set.
- `test_non_stage_brief_drift_guidance_keeps_analysis_creation_and_view_distinct`, `test_non_stage_brief_drift_structural_guidance_preserves_evaluator_first_ordering`, `test_non_stage_brief_drift_guidance_does_not_offer_stage_rebind_to_non_stage_routes`, `test_non_stage_brief_drift_guidance_uses_supported_creation_commands` (existing) — all iterate `_NON_STAGE_BRIEF_DRIFT_GUIDES` (or its `_NON_STAGE_REBIND_GUIDES` derivative), so removing the router's entry there is the only edit needed; no per-test change.
- `test_model_family_docs_cover_every_supported_prefix` (`tests/test_model_specs.py`, existing) — regression check confirming the untouched "Backend:" paragraph in both routers still carries every model-family token.
- The existing `tests/cli/test_skill_cmd.py::TestInstallSkill` suite (existing) — regression check; none of its assertions are content-sensitive to this step's edits.

### Verification (doc-content, not a new automated check)

The plan's own scope guardrails bar adding a drift check, lint, or gate of any kind, and the plan's Testing section frames the following as hand checks rather than new pytest assertions — do not add a new automated test for them:

1. Grep `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` for `convergence-tail-in-a-claude-session` — zero hits in either.
2. Grep both files for `](../../` — zero hits (every remaining cross-file reference uses the plain-name-caveat form).
3. Diff the seven roadmap pointer rows/groups and the two convergence-discipline rows plus the completeness-audit annotation between the two files — identical text.
4. Re-run the four `plan_tool/cli/*.py` files' section-name greps from the codebase audit above and confirm they still resolve to sections that exist post-trim.

All tests above must be green before this step is considered finished.

## Acceptance criteria

- `integrations/claude/SKILL.md` has no `## Convergence tail in a Claude session` heading and no `](#convergence-tail-in-a-claude-session)` link.
- Every one of the four roadmap decision-tree rows and three Subcommands-at-a-glance roadmap rows in `integrations/claude/SKILL.md` is a one-line pointer (entry command plus a `DIRECTIVES.md` citation), not multi-sentence flag/refusal prose.
- `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` both contain a bare (`DIRECTIVES.md`, no path prefix) link to the shared reference.
- `integrations/codex/SKILL.md` carries the same seven roadmap pointer rows/groups, the same two convergence-discipline decision-tree rows, and the same completeness-audit annotation Claude's trimmed router keeps.
- `integrations/codex/SKILL.md`'s "Going deeper" list carries a `ROADMAP_FORMAT.md` bullet matching Claude's.
- Neither router contains a `../../`-style relative link to `RUNBOOK.md`, `README.md`, or `docs/OPERATIONS.md`; each such reference reads as a plain name with the repo caveat.
- `_SOURCE_ADMISSION_GUIDES`, `_SOURCE_ADMISSION_GUIDANCE`, `_SOURCE_ADMISSION_ISOLATION`, `_STRUCTURAL_ROUTE_GUIDES`, `_STRUCTURAL_ROUTE_GUIDE_BOUNDS`, and `_NON_STAGE_BRIEF_DRIFT_GUIDES` no longer key `"integrations/claude/SKILL.md"`, and the two hardcoded expected-name-set literals no longer include it.
- `uv run pytest tests/test_roadmap_format.py tests/test_model_specs.py tests/cli/test_skill_cmd.py -q` passes in full.
- No comment or docstring in `plan_tool/cli/__init__.py`, `plan_tool/cli/parser.py`, `plan_tool/cli/review_cmd.py`, or `plan_tool/cli/inspect.py` names a `SKILL.md` section this step removes.

## Applicable guardrails

- The plan's "## Scope guardrails" first bullet binds the router edits to *moving* prose, not rewriting it: every pointer line's entry command and referenced flag must match what the router already documents today (now relocated into `DIRECTIVES.md` by step 1) — this step is not a chance to redesign roadmap or convergence behavior.
- The plan's "## Scope guardrails" second bullet (no new drift check, lint, gate, or exit-code flip) is why the link-hygiene fixes and the "no restated rule" property are verified by hand, per [Tests](#tests), not by a new pytest assertion.
- The plan's "## Scope guardrails" third bullet (no skill frontmatter trigger-field changes) means the YAML frontmatter block of either router is untouched by this step.
- The plan's "## Scope guardrails" fourth bullet (no backend-selection or runtime-behavior change) is why the "Backend:" paragraph and model-family content in both routers stay untouched.
- The plan's "## Out of scope" excludes the `model:` frontmatter value on any router — not touched here.

## Deferred

- Adding `integrations/cursor/SKILL.md` and the `cursor` `--integration` value — step 4, which copies whatever pointer shape this step lands.
- Updating `docs/ARCHITECTURE.md`, `README.md`, `integrations/shared/DIRECTIVES.md`'s wiring note, and removing `BACKLOG.md` #370 — step 5.
- A drift guard between the routers and `DIRECTIVES.md` — the plan's own top-level "## Deferred" section routes this out permanently; one shared file is the anti-drift mechanism.
- Codex's own pre-existing gaps the plan does not name as this step's concern: no `--commit` paragraph in "Running from chat / automation," and no "run several steps of X in a row" decision-tree row. Both are real differences from Claude's router, confirmed at HEAD, but the plan's Problem statement and Architecture section name only roadmap awareness and convergence discipline as the parity gap this step closes — widening it to every Claude/Codex content difference is a separate concern for whoever picks it up next.
- Reconciling Claude's `README.md`-targeted worktrees link against Codex's `docs/OPERATIONS.md`-targeted one — both docs carry the same `## Worktrees (parallel plans)` section (confirmed at HEAD), so each router keeps citing its own current target under the plain-name-caveat form; harmonizing which doc each backend points at is not this step's call.
