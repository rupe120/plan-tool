> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Document local, exact-pair rewrite-only, evidence, generic, transaction, and broad roadmap paths

## Summary

Document the new exact-pair structural rewrite alongside the existing local, evidence-only, and broad roadmap routes. Update `ROADMAP_FORMAT.md` as the detailed contract source, then align the operator, architecture, capability, and agent-facing references. Keep the main decision clear: evidence route classes do not grant a wider write set, and the new command changes only one proved artifact. On green, operators can choose a route without mistaking a handoff, a generic request, or broad re-entry for the bounded structural writer.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected documentation.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the existing route guidance needs a bounded structural lane.
- [Input](#input) — Landed contracts from earlier steps that the documentation must read.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact documentation and drift-guard footprint.
- [Implementation](#implementation) — Route ownership, preservation rules, and documentation boundaries.
- [Tests](#tests) — Drift checks for the code-owned format reference.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation outcomes.
- [References](#references) — Primary references for the documented publication boundary.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that limit this documentation work.
- [Deferred](#deferred) — Writer paths this step must describe as unavailable.

## Why

Current operator guidance sends structural and prose requests to `--from-stage N`, while `ROADMAP_FORMAT.md:### Choose the revision route` describes only the narrower local command and broad re-entry. Steps 3, 5, 7, and 9 add a third mutation path: an explicit evidence pair can produce one proof-bound rewrite without turning a static route into write authority. Document that distinction now so an operator neither broad-rewrites an artifact that qualifies for the exact-pair path nor treats evidence publication, a generic request, or a cross-artifact handoff as an executable writer.

## Input

- **Step 3 operation contract:** Read the landed public schema, allowlists, and prose-region grammar in `plan_tool/roadmap_structural_operations.py`. The landed module, not this plan or its earlier detail, owns the names and closed values documented in `ROADMAP_FORMAT.md`.

- **Step 5 proof boundary:** Read `plan_tool/roadmap_structural_revision_proof.py` for the preservation inventory, full-roadmap gate result, and the limit that a structural proof does not decide semantic downstream adequacy.

- **Step 7 lifecycle contract:** Read the landed structural-rewrite event types and closed redaction vocabulary in `plan_tool/run_log.py`. Document only operator-relevant safe facts; never copy feedback, artifact, prompt, or backend text into a reference document.

- **Step 9 command surface:** Read `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` and the generated command reference for the accepted `--rewrite-structural` and `--rewrite-analysis` form, exclusivity behavior, output, and exit mapping.

- **Existing route contracts:** Preserve the distinction between `plan_tool/roadmap_revision_run.py:run_local_feedback_revision`, `plan_tool/roadmap_impact_run.py:run_roadmap_impact_analysis`, `plan_tool/roadmap_impact_analysis.py:SAME_ARTIFACT_WORKFLOW`, `plan_tool/roadmap_impact_analysis.py:CROSS_ARTIFACT_WORKFLOW`, and `plan_tool/roadmap.py:STAGES`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Add the code-owned exact-pair structural-rewrite reference, revise `### Choose the revision route`, and clarify how impact-analysis handoffs relate to the new writer.
  - `tests/test_roadmap_format.py` — Add drift guards that bind the new format-reference blocks and route boundaries to landed code and CLI contracts.
  - `README.md` — Add the exact-pair command to the roadmap command list and update `### 0. roadmap` with concise route-selection guidance.
  - `CLAUDE.md` — Update `## What this is` and `## Reference docs` with the new roadmap writer and `ROADMAP_FORMAT.md` ownership boundary, keeping both entries concise.
  - `CAPABILITIES.md` — Extend `## Architecture roadmap` with the structural-rewrite modules and its bounded, proof-first behavior.
  - `docs/ARCHITECTURE.md` — Add the structural writer layer under `## Roadmap`, adjacent to the existing immutable-evidence sections.
  - `docs/ROADMAP_WALKTHROUGH.md` — Extend `## 5. Ask for a revision with feedback` with the evidence-to-exact-pair sequence and its limits.
  - `RUNBOOK.md` — Add the command to `## Quick reference` and update `### Record structural feedback without revising the roadmap` with the operator decision path.
  - `integrations/claude/SKILL.md` — Update `## Decision tree for common user asks` and `## Subcommands at a glance` with the exclusive exact-pair route and no-fallback rule.

## Implementation

- **Foundational logic:** Document one route-selection rule that maps a request shape to its only supported roadmap command or handoff.

- **Make `ROADMAP_FORMAT.md` the detailed source.** Keep `ROADMAP_FORMAT.md:### Choose the revision route` as the short entry point, then add a dedicated exact-pair structural-rewrite section after the receipt and impact-analysis material. Use code-owned markers and a focused table or equivalent structured block so `tests/test_roadmap_format.py` can compare the documented command, operation vocabulary, and route rules with the landed contracts.

- **Keep the local route narrow.** `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` remains for one eligible same-artifact feedback row and its presentation-field response. State that decision-rationale work remains there; do not imply that the structural writer subsumes local revision.

- **Describe the exact-pair writer as rewrite-only.** Document the only command form as `plan-tool roadmap <slug> --rewrite-structural RECEIPT_FINAL --rewrite-analysis ANALYSIS_FINAL`. Both immutable names must be explicit and singular. The command must not select a receipt, analysis, or route from a scan, selector, timestamp, or inferred current state, and it must not fall back to local revision or `--from-stage N`.

- **State the source-span boundary in operator terms.** Derive the landed field allowlist and existing-region grammar from step 3. Explain that the writer changes only approved scalar fields on the selected existing target row, one existing marked prose-region interior when admitted, and the selected feedback response; everything else in the selected artifact and every other artifact stays unchanged. Do not advertise marker creation, migration, row or relation edits, decision changes, or a generic patch language.

- **Separate evidence from authority.** `--escalate-feedback`, `--analyze-escalation`, and their views create or inspect immutable evidence; they do not write a canonical artifact. For evidence creation, `requires-scope-review` is a successful no-writer result. For the exact-pair structural rewrite, that same route class refuses during preflight before seed invalidation or backend contact. A current `same-artifact` or `cross-artifact` analysis can inform the exact-pair preflight, but neither route class permits a wider write set.

- **Name the transaction boundary accurately.** Keep `plan_tool/roadmap_impact_analysis.py:CROSS_ARTIFACT_WORKFLOW` visible as a future handoff, not a command the user can run. A cross-artifact route must not make the exact-pair writer transactional or allow a second canonical artifact to change.

- **Keep generic and broad work distinct.** Explain that generic structural operations remain unavailable rather than becoming an undocumented extension of the exact-pair envelope. `--from-stage N` remains the deliberate broad authoring and recovery route through `plan_tool/roadmap.py:STAGES`; it re-gates lower stages and rewrites from the selected stage upward, so it does not provide the structural command’s source-span preservation or final proof.

- **Document the review and publication limits once, at the right depth.** In `ROADMAP_FORMAT.md`, state that the proof preserves declared structure and clears the captured gate context, while the reviewer still judges whether the response is acceptable. In `docs/ARCHITECTURE.md:## Roadmap`, describe the guarded final recheck and one-artifact atomic publication without presenting it as a multi-file recovery transaction. Keep `README.md`, `RUNBOOK.md`, `docs/ROADMAP_WALKTHROUGH.md`, and `integrations/claude/SKILL.md` command-focused and link to the format reference for schema detail.

- **Keep lifecycle documentation redacted.** Describe the one-shot, terminal nature of the rewrite and its safe outcome facts using step 7’s landed vocabulary. Do not reproduce feedback text, artifact prose, prompt text, or backend replies in logs, examples, command output descriptions, or capability prose.

- **State evaluator availability without weakening it.** Document that V1 runs
  only with the verified macOS host-isolated evaluator and refuses before
  evidence or seed invalidation when that provider is unavailable. Do not imply
  that an empty working directory, a prompt, or Codex read-only mode protects
  canonical workspace reads, and do not describe another platform as a fallback.

- **Sweep stale route wording across every listed document.** Replace statements that direct every structural, relationship, or prose rewrite to broad re-entry with qualified guidance that preserves the new bounded lane. Do not edit `docs/cli/roadmap.md`; step 9 owns the exhaustive command reference.

## Tests

- `test_structural_rewrite_reference_matches_landed_contract` — asserts that the marked `ROADMAP_FORMAT.md` reference uses the landed exact-pair CLI form, V1 operation schema, and allowlist rather than copied provisional values.

- `test_structural_rewrite_reference_preserves_source_spans_and_review_boundary` — asserts that the reference limits publication to the selected artifact and selected feedback response, preserves all unapproved content, and leaves semantic acceptance to review.

- `test_structural_rewrite_route_reference_separates_local_evidence_generic_transaction_and_broad_paths` — asserts that local revision, evidence-only escalation and analysis, rewrite-only structural work, unavailable generic work, the transaction handoff, and deliberate broad re-entry remain distinct with no fallback, including successful evidence-only versus refusing rewrite-preflight `requires-scope-review` results.

- `test_structural_rewrite_reference_keeps_redacted_one_shot_outcomes` — asserts that the documentation uses the landed safe lifecycle vocabulary, accurately states the fail-closed host-isolation availability rule, and does not describe retained reviewer, artifact, prompt, or backend content.

### Verification (non-code step)

1. Run `uv run pytest tests/test_roadmap_format.py -q` after the format-reference guard lands.

2. Run `uv run pytest tests/cli/test_roadmap_cmd.py -q` to confirm the documented command matches step 9’s exclusive surface.

3. Run `uv run pytest tests/test_capability_catalog.py -q` to confirm every added `CAPABILITIES.md` surface exists and the catalog remains valid.

4. Compare every listed documentation surface with `plan-tool roadmap --help` and `docs/cli/roadmap.md`; the concise docs must use the exact command form without duplicating the generated option reference.

5. Search the listed documentation files for the old broad-only structural guidance and confirm each remaining `--from-stage N` mention describes deliberate broad re-entry rather than an automatic structural-command fallback.

## Acceptance criteria

- `ROADMAP_FORMAT.md` maps local presentation revision, exact-pair rewrite-only revision, evidence-only escalation and analysis, unavailable generic operations, the cross-artifact transaction handoff, and broad stage re-entry to separate operator outcomes.

- The documented structural command requires one explicit receipt final and one explicit analysis final, accepts no companion mode, and never infers a replacement evidence record or fallback route.

- The format reference derives its V1 operation vocabulary, allowed field surface, existing-region rule, preservation inventory, and selected-feedback transition from landed code.

- The documentation states that route classification is evidence rather than write authority, that the structural proof is not semantic approval, and that successful publication remains reviewable.

- `README.md`, `RUNBOOK.md`, `docs/ROADMAP_WALKTHROUGH.md`, `integrations/claude/SKILL.md`, `CAPABILITIES.md`, `CLAUDE.md`, and `docs/ARCHITECTURE.md` point operators to the same bounded route without copying the full schema.

- `uv run pytest tests/test_roadmap_format.py -q`, `uv run pytest tests/cli/test_roadmap_cmd.py -q`, and `uv run pytest tests/test_capability_catalog.py -q` pass.

## References

- [RFC 8259 — JSON object-member rules](https://www.rfc-editor.org/rfc/rfc8259.html#section-4) — Use when documenting why the structural reply envelope rejects duplicate members.

- [Python `os.replace`](https://docs.python.org/3.13/library/os.html#os.replace) — Use when describing atomic replacement of the one proved artifact.

- [Python `fcntl.flock`](https://docs.python.org/3.13/library/fcntl.html#fcntl.flock) — Use when describing the participating-writer guard around final checks and publication.

- [Python `hashlib`](https://docs.python.org/3.13/library/hashlib.html#hashlib.file_digest) — Use when describing the digest-bound evidence and final snapshot checks.

## Applicable guardrails

- **The plan’s “## Plan intent”** — Document the one-artifact rewrite as bounded existing-content work with a reviewable selected feedback response; do not describe a broader writer.

- **The plan’s “## Out of scope”, allowed behavior changes** — Do not present excluded row, relation, decision, marker, or generic-patch changes as supported structural operations. Keep the local decision-rationale route distinct.

- **The plan’s “## Out of scope”, candidate-aware impact analysis** — Do not claim that the structural proof or static impact route judges downstream semantic obligations.

- **The plan’s “## Out of scope”, canonical write and recovery boundaries** — Describe one guarded artifact replacement only; do not imply multi-artifact publication, recovery, automatic escalation, or a document editor.

- **The plan’s “## Out of scope”, schema and seed boundaries** — Do not claim a roadmap schema or seed-materialization change merely because the structural route invalidates derived state.

## Deferred

- Generic structural operations — Remain with BACKLOG #289; this step documents their absence rather than inventing a command or envelope.

- Cross-artifact revision transaction — Remains a named impact-analysis handoff until a separately authorized transaction contract and real request exist.

- Prose-marker creation or migration — Requires separate evidence and scope; V1 only accepts an already eligible marked region.
