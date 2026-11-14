---
title: Detail Verbosity Compact Summary
status: planning
priority: medium
enforce_step_tests: true
registered_by: sweep
steps:
- id: 1
  title: Add `plan-tool detail <name> --summary` review cards with dual-token section
    lookup
  files:
  - plan_tool/cli/authoring.py
  - plan_tool/detail.py
  - docs/cli/detail.md
  - docs/cli/README.md
  - tests/test_detail.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/detail-verbosity-compact-summary/01-plan-tool-detail-name-summary-review.md
  status: current
- id: 2
  title: Route detail-file section consumers through dual-token aliases so compact
    tokens read like legacy ones
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: refactor
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/detail-verbosity-compact-summary/02-route-detail-file-section-consumers.md
- id: 3
  title: Change the required detail H2 set to the compact Intent/Footprint/Approach/Done-when
    contract and rewrite the authoring + quality prompts
  files:
  - plan_tool/detail.py
  - plan_tool/prompts/detail.md
  - plan_tool/prompts/detail-quality.md
  - DETAIL_FORMAT.md
  - docs/how-to/pipeline/detail.md
  - tests/test_detail.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/detail-verbosity-compact-summary/03-change-required-detail-h2-set-compact.md
- id: 4
  title: Add a complexity gate that keeps `low` steps compact-only and lets `medium`/`high`
    expand only the Approach
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/detail-verbosity-compact-summary/04-complexity-gate-that-keeps-low-steps.md
- id: 5
  title: Filter sibling detail bodies fed into the authoring prompt to prefer compact
    siblings and strip ToC/Why from legacy ones
  files:
  - plan_tool/detail.py
  - plan_tool/prompts/detail.md
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/detail-verbosity-compact-summary/05-filter-sibling-detail-bodies-fed.md
- id: 6
  title: 'Update capability/use-case docs and reconcile BACKLOG #149/#49 for the compact-detail
    contract'
  files:
  - BACKLOG.md
  - CAPABILITIES.md
  - USE_CASES.md
  - RUNBOOK.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/detail-verbosity-compact-summary/06-update-capability-use-case-docs.md
---
# Detail Verbosity Compact Summary

## Overview

This plan makes `plan-tool detail` output less verbose in two reinforcing layers. First, a read-only **summary review surface** (`plan-tool detail <name> --summary`) prints one compact review card per step from existing detail files — Intent/Summary + Footprint/Files + Done-when/Acceptance + short Tests/Deferred — spending no Claude and always exiting 0. Second, a **compact required detail schema** changes what `detail` authors by default: merge Summary+Why into a single `Intent`, drop the Table of Contents, keep `Footprint` + a capped `Approach` + `Done when`, with optional `Input`/`References`/`Deferred`. A complexity gate keeps `low` steps always-compact while `medium`/`high` may expand only the Approach. Legacy seven-section files stay valid on read via dual-token lookup, so nothing is force-migrated.

## Problem statement

Developers reviewing plans report `plan-tool detail` output is too verbose — more than needed to sign off a step and denser than implementers need to start. The verbosity is structural, not incidental: `_REQUIRED_H2_TOKENS` in `plan_tool/detail.py` hard-requires seven sections (Summary, Table of Contents, Why, Files, Implementation, Tests, Acceptance), so even a one-line change authors ~70 lines (e.g. `direct-pipeline-repo-root-resolution` step 1, with Summary and Why retelling the same story) and denser steps land at ~120–170 lines. ToC is ceremony on short files, Why duplicates Summary, and Implementation expands into call-site inventories even when the constraint is a single assignment. Existing guidance is inert: `plan_tool/prompts/detail.md` already says "intent over mechanics" and `DETAIL_FORMAT.md` carries altitude guidance, but `detail-altitude` is advisory and not apply-eligible so over-prescription is never auto-slimmed; the authoring prompt also feeds sibling detail bodies as tone/structure reference, so one long file trains the next. Cost compounds because `plan_tool/renderer.py:_load_detail` injects the full detail body into the `run` implementer prompt, so review load and token cost both scale with length (BACKLOG #38 already treats detail length as a drift signal). Merely asking the model to "write shorter" while keeping seven required H2s fails — sibling tone-matching and the parse gate re-inflate bodies.

## Architecture

The work is staged in three phases that ship in dependency order.

**Phase A — Summary review cards (ship first).** Add a read-only surface, preferred shape `plan-tool detail <name> --summary` (an alternative `status`/`list` mode is acceptable if cleaner — pick exactly one surface at create time, do not invent two). It parses each step's detail via the existing `parse_detail_file_sections` and prints one card per step (honoring `--step N`): title/complexity/change_type from plan frontmatter; files from frontmatter `files:` and/or `## Files`/Footprint; the full Summary or Intent body (already short); full Acceptance criteria bullets (the validation checklist); Tests at most a short/truncated bullet list; and Deferred only if present. It omits Why, Table of Contents, Implementation/Approach, and References; spends no Claude; and exits 0 always. Cards must work for both legacy seven-section files and the new compact schema via dual-token lookup (`summary`|`intent`, `files`|`footprint`, `implementation`|`approach`, `acceptance`|`done`). This phase is a pure renderer with no prompt or schema change.

**Phase B — Compact authoring contract.** Change the required H2 set to approximately: `## Intent` (2–4 sentences merging today's Summary + Why — what changes, why it matters, primary design choice), `## Footprint` (Creates/Edits, one line per file naming the symbol or change), `## Approach` (≤8 bullets: invariants, real anchors, constraints/gotchas, load-bearing rejected alternatives — no call-site inventories unless they *are* the constraint), and `## Done when` (CI-checkable acceptance bullets plus representative-case `Tests:` lines). `## Input`, `## References`, `## Deferred` stay optional with unchanged semantics. The non-exhaustive touch set (discover call sites in create/detail): `plan_tool/detail.py` (`_REQUIRED_H2_TOKENS`, `_REQUIRED_H2_DISPLAY`, `parse_detail_response`, any section-token consumers), `plan_tool/prompts/detail.md` (required structure + hard length caps), `plan_tool/prompts/detail-quality.md` (flag over-prescription / Intent↔duplicate-Why / Approach exceeding caps; keep "open how is fine"), `DETAIL_FORMAT.md`, `docs/how-to/pipeline/detail.md`, CLI reference regen, and `tests/test_detail.py` plus any fixtures hardcoding seven sections. A **complexity gate** enforces compact-only when `step.complexity == low`; medium/high may allow a longer Approach but never reintroduce ToC or a separate Why. **Sibling prompt hygiene**: when feeding sibling details into the authoring prompt, prefer compact siblings; if only legacy verbose siblings exist, strip/truncate ToC/Why (or feed only Intent+Footprint+Done-when) so tone-matching does not re-inflate new files.

**Phase C — Migration / read compatibility.** Legacy seven-section files remain valid on the read path for `run`, reconcile, completeness, and `--summary` (map old tokens → card fields); the write path emits compact only; existing plans are not force-rewritten on upgrade; and `DETAIL_FORMAT.md` documents the dual schema (legacy accepted on read, compact is the authoring contract). Suggested single-concern decomposition (create may refine), keeping the summary view and schema change as separate steps: (1) summary view — CLI flag + pure renderer over `parse_detail_file_sections`, dual-token lookup, unit tests, no prompt/schema change; (2) compact schema gate + prompt — change required tokens, `detail.md` template, parse/retry wording, `DETAIL_FORMAT`, keeping run/reconcile consumers working via aliases; (3) quality/altitude tightening — detail-quality findings for over-prescription and section-cap violations as far as apply-eligibility safely allows without blind prose deletion; (4) sibling/complexity hygiene — compact sibling feed + low-complexity hard cap; (5) docs + backlog bookkeeping — CAPABILITIES/USE_CASES/RUNBOOK as needed, remove #149 from BACKLOG, update #49's seven-section language if still open, regenerate CLI reference.

## References

- [argparse — Parser for command-line options, arguments and subcommands — Python documentationhttps: — Primary reference for adding the `--summary` flag/subaction and its help/exit-code behavior on the `detail` subparser.
- [How to use temporary directories and files in tests — pytest documentationhttps: — Official guidance on the `tmp_path` fixture used for the project's hermetic unit tests over the card renderer and parse-gate changes.
- [Fixtures reference — pytest documentationhttps: — Reference for built-in fixtures and markers (e.g. integration marks) an implementer consults when adding the unit and end-to-end `detail --summary` tests.
- [PyYAML Documentationhttps: — Reference for `safe_load` parsing of plan/detail YAML frontmatter (complexity, change_type, files) that the summary cards and complexity gate read.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Auto-rewriting all historical detail files in the repo.
- Replacing detail with plan frontmatter alone (frontmatter lacks acceptance bullets and approach constraints).
- Making `detail-altitude` auto-apply mechanical deletions without judgment (slimming prose needs a careful apply path or human edit).
- The interactive detail wizard (#49) — only note the contract change it must follow; do not implement the wizard here.
- Purity-prompt size (#133) — a different problem (audit prompt bytes, not authored detail shape).

## Risks

- **Over-slim drops anchors.** Severity: correctness of downstream steps. Mitigation: Footprint + Approach must still name real files/symbols; acceptance stays CI-checkable; the "open how / closed what+where" rule stays.
- **Hidden consumers of old section tokens.** Mitigation: dual-token helpers; grep for `sections.get("summary"|"why"|"implementation"|"table")` and `_REQUIRED_H2` in tests; keep legacy read mapping until a later cleanup.
- **Sibling re-inflation.** Mitigation: Phase B sibling hygiene (prefer compact siblings; strip/truncate ToC/Why from legacy ones).
- **#49 / docs drift.** Mitigation: the final step updates the backlog + format docs.

## Testing

Follow the project's unit-first convention. Phase A's card renderer is a pure function over `parse_detail_file_sections` and should be covered by unit tests asserting dual-token lookup (`summary`|`intent`, `files`|`footprint`, `implementation`|`approach`, `acceptance`|`done`), `--step N` scoping, omission of Why/ToC/Implementation/References, and exit 0. Phase B parse/gate changes update `tests/test_detail.py` and any fixtures that hardcode the seven sections, asserting the new required H2 set (Intent/Footprint/Approach/Done when), the low-complexity compact enforcement, and that legacy seven-section files still parse for `run`/reconcile/completeness/summary. Add integration coverage only where CLI wiring or cross-module read compatibility would escape a unit test — e.g. driving `plan-tool detail <name> --summary` end-to-end and confirming legacy details still load through `run`/reconcile. Regenerate and re-check the CLI reference (`tests/cli/test_cli_reference.py`) if any flag changes.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (refactor) — tests covering the behavior it changes; green before it finishes.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool detail <name> --summary` (or the chosen equivalent) prints per-step review cards with no Claude, works on both legacy and compact files, and omits Why/ToC/full Implementation; it exits 0.
- New `detail` authoring requires the compact H2 set (Intent/Footprint/Approach/Done when — no ToC, no separate Why); low-complexity steps stay within the stated length caps in prompt guidance.
- Legacy seven-section details still load for `run`, reconcile, completeness, and `--summary`.
- Existing detail parse/quality tests are updated and green; the CLI reference is regenerated if flags change.
- BACKLOG #149 is removed or marked shipped, and #49's seven-section assumptions are updated if that entry remains open.

## Deferred

- Writing `REVIEW.md` to disk (stdout summary is v1).
- Auto-migrate / batch-regenerate historical details.
- Machine-readable `--json` summary for CI gates.
- Making over-prescription findings fully apply-eligible with a safe slim rewrite path.
