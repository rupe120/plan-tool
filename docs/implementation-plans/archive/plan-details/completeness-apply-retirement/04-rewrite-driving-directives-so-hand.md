> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Make hand-editing the universal completeness workflow

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Align `CLAUDE.md`, `integrations/shared/DIRECTIVES.md`, and the three backend skills around one conceptual-finding workflow: read the saved report, judge the findings, edit, commit, and re-audit. Remove the operator-specific application branches and unattended-pipeline exceptions. Update command inventories and explanations that depend on the retired commands while preserving existing audit policy. On green, every driving instruction describes the same workflow without recommending a removed command.

## Table of Contents

- [Summary](#summary) — Result and main boundaries.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Why the driving instructions need alignment.
- [Input](#input) — Dependency outcomes and policy contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation edits.
- [Implementation](#implementation) — Universal workflow and preservation boundaries.
- [Tests](#tests) — Documentation verification.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Scope and documentation owners.
- [Applicable guardrails](#applicable-guardrails) — Limits on this rewrite.
- [Deferred](#deferred) — Work owned elsewhere.

## Why

The supplied driving instructions still describe `completeness-apply` as the conceptual findings’ sole mutator, offer its interactive walk to human operators, and permit unattended application through the direct pipelines. Steps 2 and 3 remove those commands, making those instructions unusable. Removing only command examples leaves explanations that still argue for the removed routes, including bare-stage withholding rationales and commit-surface inventories. The existing `CLAUDE.md` “Driving the convergence loops” heading identifies the work area; its presence does not establish that this rewrite is complete.

## Input

- **Step 2 outcome:** `direct-run` and `direct-jira` retire. Describe the surviving standalone workflow without recreating their orchestration.
- **Step 3 outcome:** `completeness-apply` and its exclusive application machinery retire. Check command and commit-surface claims against the resulting implementation rather than copying obsolete inventories.
- **Audit policy:** Preserve the distinction between deterministic repair and conceptual findings. Preserve report qualification, bare/detail audit gates, blocking policy, and convergence exits.
- **Tracked integration sources:** `plan_tool/cli/skill_cmd.py:_bundled_shared_directives_source()` locates the shared reference distributed with backend skills. Edit the declared tracked sources, leaving installation and packaging behavior unchanged.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `CLAUDE.md` — replace the completeness operator split, remove retired-command exceptions and inventories, and correct dependent explanations throughout the file.
  - `integrations/shared/DIRECTIVES.md` — make conceptual correction universal, remove unattended application exceptions, and align workflow and commit guidance.
  - `integrations/claude/SKILL.md` — align completeness recipes and supported `--commit` surfaces.
  - `integrations/codex/SKILL.md` — apply the same workflow correction while preserving backend-specific instructions.
  - `integrations/cursor/SKILL.md` — apply the same workflow correction while preserving backend-specific instructions.

## Implementation

- **Foundational logic: conceptual findings require judged hand-edits.** Both human operators and orchestrating sessions must read the completed saved report, verify its claims, make bounded corrections, commit, and re-audit the changed snapshot. Hand-editing includes an assistant editing files directly; it must not imply that only a human can make the correction.

- **Replace the completeness-specific operator split.** Rewrite `CLAUDE.md` under “Driving the convergence loops” and `integrations/shared/DIRECTIVES.md` under “Who is driving decides how conceptual gaps get closed” around that universal rule. Remove “sole mutator” claims, the human-at-a-TTY application branch, and the direct-pipeline third mode. Prefer one shared instruction over parallel human and assistant recipes.

- **Preserve the judgment surrounding edits.** Keep verification of cited claims, grouped finding triage, user-owned scope decisions, and the edit → commit → re-audit sequence. In `integrations/shared/DIRECTIVES.md`, retain the distinction between correcting hypotheses from a completed report and certifying convergence with qualified current evidence. Do not instruct readers to resample unchanged text merely to obtain qualification.

- **Separate completeness from surviving interactive routes.** The paragraphs beginning “The same … split governs” must stop extending the removed completeness workflow into other commands. They must retain existing instructions for review/reconcile walks and structural confirmations without implying that those routes retire or change behavior.

- **Update every commit inventory in the declared files.** Remove `completeness-apply` from the supported surfaces and correct dependent counts and explanations. The surviving inventory must name `run`, `detail`, `completeness-audit`, and `manifest sweep`/archive consistently with the landed parser. Preserve the per-green-step reason for `run --commit` in each backend’s “Running from chat / automation (no TTY)” section.

- **Remove explanations that depend on retired machinery.** Inspect `CLAUDE.md` under “Plan audit gate,” “Convergence policy boundary,” and “Architecture,” as well as completeness recipes in all declared files. Remove obsolete withholding, interactive-walk, parallel-apply, and replay descriptions where they describe the removed commands. Preserve bare-stage policy as policy: its conceptual-completeness treatment must not depend on an unavailable application command.

- **Keep useful correction checks.** Retain the class-wide search, suggested-action, implication, and goal checks in `CLAUDE.md`. Replace explanations that assume an application walk supplies those checks with direct responsibility for the person or session editing the files.

- **Sweep identifiers and concepts before and after editing.** Search the five declared files for command spellings and related phrases such as “sole mutator,” “human-review surface,” “third mode,” “withheld,” and “parallel apply.” Record each hit’s disposition. Do not delete a surviving `apply_finding`, `--jobs`, or interactive-route instruction solely because it resembles retired machinery.

- **Protect heading links.** Before renaming an operator-specific heading, search for inbound links to its current anchor and inspect its local table of contents. Prefer a rewrite that stays within the declared files; flag an external link dependency rather than silently breaking it or expanding this step.

## Tests

This is a `non-code` step. The test-authoring gate keys on `change_type` and does not require new test files here. Use the following numbered verification checks.

### Verification (non-code step)

1. **Universal conceptual-correction workflow** — Read the completeness guidance in all five declared files and confirm that operators and sessions follow report → judgment → edit → commit → re-audit.
2. **Retired-route absence** — Search the declared files for `completeness-apply`, `completeness_apply`, `direct-run`, `direct_run`, `direct-jira`, and `direct_jira`; review every remaining occurrence and reject any live recommendation, exception, or current-machinery claim.
3. **Dependent-rationale sweep** — Search the related vocabulary and confirm that no surviving explanation relies on the retired walk, unattended lane, or withholding mechanism.
4. **Commit inventory accuracy** — Compare each documented `--commit` inventory with surviving command registrations and confirm that counts agree.
5. **Policy preservation** — Review the diff for unchanged deterministic repair, audit qualification, bare/detail blocking policy, convergence exits, and surviving review/reconcile instructions.
6. **Links and document structure** — Check changed headings, inbound anchors, local contents links, and file links using `docs/reference/documentation-style.md`.
7. **Bundled-skill compatibility** — Run `uv run pytest tests/cli/test_skill_cmd.py -q`; this checks installation and skill-frontmatter compatibility, not the meaning of the workflow prose.
8. **Bounded diff** — Confirm that this implementation changes only the five declared files and preserves backend-specific setup instructions.

## Acceptance criteria

- All five declared files direct conceptual-finding correction through judged hand-edits and a committed re-audit.
- No declared file offers a human-only completeness application walk or unattended direct-pipeline exception.
- No supported `--commit` inventory includes the retired application command; associated counts match the surviving surfaces.
- Bare-stage explanations retain the existing policy without justifying it through a removed command.
- Deterministic repair and surviving review/reconcile guidance remain intact.
- Every remaining retired-command reference has an explicit review disposition and provides no live invocation guidance.
- Changed headings and links remain valid.
- `tests/cli/test_skill_cmd.py` passes, and the diff stays within the declared files.

## References

- [BACKLOG.md](BACKLOG.md) — Read entry #376 for the retirement decision and #369 for the separate shared-caller boundary.
- [Completeness Apply Retirement](docs/implementation-plans/2-completeness-apply-retirement.md) — Read step 4’s intent and the plan’s scope fence.
- [Documentation style](docs/reference/documentation-style.md) — Apply the structure and review checklist to the rewritten instructions.

## Applicable guardrails

- **The plan’s “Scope guardrails,” retirement boundary:** Limit edits to driving guidance for the retired surfaces and explanations that depend on them.
- **The plan’s “Out of scope,” surviving application routes:** Do not turn the universal completeness instruction into a prohibition on application behavior elsewhere.
- **The plan’s “Scope guardrails,” policy preservation:** Rewrite reasons and recipes without changing audit blocking, continuation, qualification, or exit-code rules.
- **The plan’s “Out of scope,” historical artifacts:** Do not rewrite saved reports or legacy evidence to satisfy a vocabulary sweep.
- **Repository rule governance:** Changes to `CLAUDE.md` require architect-tier review through the normal pull-request flow; this detail does not remove that requirement.

## Deferred

- Broader reader-documentation cleanup — Step 5 owns live documentation outside this step’s declared files, including `docs/how-to/pipeline/audit.md`.
- Backlog closure and final retirement bookkeeping — Step 6 owns shipment status; this rewrite must not declare the whole plan shipped.
- Shared application behavior — BACKLOG.md #369 tracks other callers; this step leaves their contracts unchanged.
