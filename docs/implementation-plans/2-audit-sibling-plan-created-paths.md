---
format_version: 1
title: Audit Sibling Plan Created Paths
intent: A roadmap-derived plan's completeness audit is told which paths the other
  plans in the same roadmap will create, so the model-driven audit stops reporting
  those paths as missing. A multi-plan roadmap batch no longer re-raises the same
  false finding every round, and `integrations/shared/DIRECTIVES.md` § "T — tool artifacts"
  no longer needs to tell triagers to ignore it.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/audit-sibling-plan-created-paths.md
steps:
- id: 1
  intent: Give the audit one sibling-path set, picked by the deterministic check's
    own rule and pinned by the fingerprint and the public revision, so a sibling
    `creates:` change makes a prior conceptual result stale for reuse and for a
    saved report's freshness.
  files:
  - plan_tool/review.py
  - plan_tool/review_persistence.py
  - plan_tool/fingerprint.py
  - DATA_CONTRACT.md
  - tests/test_review.py
  - tests/test_review_persistence.py
  complexity: medium
  change_type: feature
  status: current
  description: 'Add one selection helper in `plan_tool/review.py` that returns the
    same-roadmap sibling `creates:` paths for a plan. It returns `_eligible_planned_paths(plan,
    plan_path, repo_root)` minus `_planned_paths(plan)` only when `_sibling_roadmap_identity`
    returns an identity. It returns an empty set when the identity is `None` (so the
    all-registered-plans set is not delivered) and when the identity raises `ValueError`
    (uncertain evidence, so no partial set). No second selection rule is written.
    Capture that set once in `plan_tool/review_persistence.py:AuditInputSnapshot.capture`
    as a new sorted-tuple field with an empty default. Use a lazy import of the review
    helper, matching the module''s existing lazy-import style, so no import-time cycle
    is added. Fold the set into `_audit_input_fingerprint` as its own framed label,
    added only when the set is non-empty (the same pattern as `project_context`),
    so fingerprints of plans with no siblings stay byte-identical. The fingerprint
    then governs reuse and freshness through `audit_input_fingerprint_matches_disk`
    (used by `plan_tool/completeness_report.py` and `plan_tool/cli/completeness_phases.py`)
    with no edit to those callers. The public `qualified_result.audit_revision` dict
    in `plan_tool/fingerprint.py:audit_input_revision` moves to version 4 with a
    `sibling_paths_digest` (`null` when no sibling paths apply), following the
    v2 `source_seed_digest` and v3 `project_context_digest` precedent, so a saved
    report''s `view_revision_status` turns `stale` after a sibling edit; historical
    decoding fills an absent v1–v3 `sibling_paths_digest` with `None`, and reads
    never rewrite archived sidecars. Update `DATA_CONTRACT.md`: the `AuditInputSnapshot`
    paragraph names the new captured input, the `qualified_result.audit_revision`
    paragraph names the v4 digest, and the run-grade evidence paragraph lists
    versions 1–4 as supported. Saved fingerprints and revisions of roadmap plans
    that have siblings change once on upgrade, deliberately; plans with no siblings
    keep both byte-identical. No destructive operations are touched. Unit tests
    in `tests/test_review.py` cover the helper with a two-plan roadmap fixture (the
    sibling path is present, own `creates:` are excluded), a no-identity plan with
    other registered plans that declare `creates:` (empty), a plan from a different
    roadmap (excluded), and uncertain identity (empty). Unit tests in `tests/test_review_persistence.py`
    show that changing a sibling''s `creates:` changes the snapshot fingerprint, that
    an unchanged sibling set leaves it unchanged, and that a plan with no siblings
    keeps its existing fingerprint. Tests in `tests/test_fingerprint.py` show the v4
    revision carries `sibling_paths_digest` (null with no siblings), that a sibling
    edit changes it, and that a v3 record decodes with `sibling_paths_digest` `None`.'
- id: 2
  intent: Put the sibling paths in front of the conceptual auditor as planned work,
    so it stops reporting them as missing files.
  files:
  - plan_tool/prompts/plan-audit.md
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the selection helper and the captured snapshot field the renderer reads
  description: 'Add a sibling-planned-paths input block to `plan_tool/prompts/plan-audit.md`
    as a new `${sibling_planned_paths_block}` placeholder beside the existing input
    blocks. It lists each sibling `creates:` path one per line and tells the auditor
    that a listed path is a sibling plan''s planned work and is not reported as missing.
    When the set is empty, the block renders an explicit statement that no sibling
    plan paths apply, never an empty slot. Supply the block from `render_plan_audit_prompt`
    in `plan_tool/review.py`. Read the captured set from `audit_input_snapshot` when
    one is passed; when it is not, compute it through step 1''s helper. Add the block''s
    size to the `collect_blocks` budget list. Update the renderer docstring to describe
    the block. Sweep `plan-audit.md`''s own prose for any text that implies the auditor
    has no sibling footprints. Unit tests in `tests/test_review.py`: the rendered
    prompt for plan 2 of a two-plan roadmap fixture lists plan 1''s `creates:` path
    and not plan 2''s own; a no-identity plan and an uncertain-identity plan render
    the empty statement; a different roadmap''s path is absent; a snapshot-backed
    render uses the captured set; and every `${...}` placeholder in `plan-audit.md`
    is supplied by the renderer, so no `${` is left in the rendered prompt. No test
    asserts how a real model responds (deliver, don''t verify).'
- id: 3
  intent: Stop telling triagers to ignore a false positive the audit no longer produces,
    and close the backlog entry once the fix ships.
  files:
  - integrations/shared/DIRECTIVES.md
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  depends_on_notes:
    2: the shipped prompt block that makes the sibling-path T case obsolete
  description: 'Rewrite `integrations/shared/DIRECTIVES.md` § "T — tool artifacts"
    so the sibling-path case is described as handled by the audit, which now receives
    same-roadmap sibling `creates:` paths, while the stale roadmap or seed path case
    stays a T false positive. Sweep by vocabulary ("another plan in the same roadmap
    creates", "sibling", "footprint") across `DIRECTIVES.md` and `BUG_BACKLOG.md`
    for prose that still calls the case unhandled. After full shipment, remove the
    originating `BUG_BACKLOG.md` entry "The audit reports a path a sibling plan in
    the same roadmap creates as missing" (it has no Jira ticket, so there is no promotion
    stub). Leave the related unbuilt-sibling entry in place. The entry removal is
    the only destructive edit, and it happens only once steps 1 and 2 are green. Verification
    for this non-code step (the test-authoring gate does not apply to `non-code`):
    `rg` shows § T no longer lists the sibling-path case, the BUG entry heading is
    gone, the unbuilt-sibling entry is still present, and `uv run pytest tests/ -q
    -n auto` is green.'
---
# Audit Sibling Plan Created Paths

## Overview

A roadmap-derived plan's conceptual completeness audit receives the list of repo-relative paths that the other plans in the same roadmap declare in `creates:`. The audit is told to treat those paths as planned work, not as missing files. The list comes from the existing sibling selection in `plan_tool/review.py`, minus the audited plan's own `creates:`. It is captured in the `AuditInputSnapshot` and covered by its fingerprint. A plan with no roadmap identity, or with uncertain identity, gets an explicit statement that no sibling paths apply. Audit blocking, severity, convergence policy and exit codes stay as they are.

## Problem statement

In a multi-plan roadmap batch, the model-driven conceptual audit reports a path as missing when a sibling plan in the same roadmap will create it. The same false finding comes back every round. Today `integrations/shared/DIRECTIVES.md` § "T — tool artifacts" has to tell triagers to ignore it.

The deterministic missing-file check already merges sibling `creates:` paths (archived plan `2-sibling-planned-input-paths`), using `_sibling_roadmap_identity` and `_eligible_planned_paths` in `plan_tool/review.py`. The conceptual audit prompt, `plan_tool/prompts/plan-audit.md`, rendered by `render_plan_audit_prompt`, is never given those paths. So the model has no way to know the path is planned work.

Source: `BUG_BACKLOG.md` → BUG → "The audit reports a path a sibling plan in the same roadmap creates as missing" (Route: plan). It has no Jira ticket yet.

## Architecture

**Settled: deliver, don't verify.** The audit receives the sibling paths as facts. The only checked claim is binary: the rendered prompt contains the sibling paths for a roadmap-derived plan, and states that none apply for any other plan. No test asserts whether a real model then holds back the finding. Findings are deliberately not filtered or post-processed. Matching finding prose against paths is the vocabulary-matching shape that `CLAUDE.md` § "Validating a semantic property you cannot observe" refuses.

**Settled: one selection rule.** The same-roadmap set is the existing `_eligible_planned_paths` result minus the audited plan's own `creates:`. It is used only when `_sibling_roadmap_identity` returns an identity. In two cases the block states that no sibling paths apply:
- identity is absent;
- identity evidence is uncertain: the function raises `ValueError`, which `_eligible_planned_paths` already treats as "own paths only".

This way the prompt never carries a set the deterministic check would not use. No second selection rule is written. The all-registered-plans set that `_eligible_planned_paths` uses for a plan with no roadmap identity is deliberately not delivered to the prompt.

**New prompt input block.** `plan_tool/prompts/plan-audit.md` gains one input block. It lists the sibling `creates:` paths, one per line, with an instruction that a listed path is a sibling plan's planned work and is not reported as missing. `render_plan_audit_prompt` in `plan_tool/review.py` supplies the block. The block is explicit when empty: to a model, an absent block and an empty one look the same, so the rendered text says plainly that no sibling plan paths apply.

**Settled: the sibling set is an audit input.** It is captured once in `plan_tool/review_persistence.py:AuditInputSnapshot`, alongside the other inputs, and folded into the snapshot fingerprint and the public revision (`audit_revision` v4, `sibling_paths_digest`), as the source seed (v2) and project context (v3) were. The snapshot is the exact input the model was shown; its fingerprint controls whether a conceptual call is reused, and the public revision controls whether a saved report reads as current. A change to a sibling's `creates:` therefore makes a prior conceptual result stale instead of letting it be reused. The prompt is rendered from the captured set, not re-read.

**Guarantee:** "a path a same-roadmap sibling plan declares in `creates:` is given to the auditor as planned work." Mechanism: the rendered prompt block. Owner: the prompt renderer in `plan_tool/review.py`.

**Docs and bookkeeping.** `integrations/shared/DIRECTIVES.md` § "T — tool artifacts" describes the sibling-path case as handled by the audit, while the stale roadmap or seed path case stays a T label. The final step removes the originating `BUG_BACKLOG.md` entry, but only after full shipment.

## Input

- The block's contents come from the existing selection in
  `plan_tool/review.py`: the same-roadmap identity
  (`_sibling_roadmap_identity`) and the eligible sibling promises
  (`_eligible_planned_paths`), minus the audited plan's own `creates:`. No
  second selection rule is written.

## Scope guardrails

- No filtering of model findings, and no new selection rule for siblings.
- No change to the deterministic missing-file check or its selection.

## Audit guardrails

- Plans outside the audited plan's roadmap and other T classes are out of
  scope.
- Stop and surface to the user if sibling footprints are not reliable at
  audit time (for example the roadmap identity is ambiguous), rather than
  widening the selection.

## Expected placement

None.

## References

- [string — Template strings (Python standard library)](https://docs.python.org/3/library/string.html#template-strings) — Covers how `${...}` placeholders are filled by `substitute` and `safe_substitute`, which you need when adding the sibling-paths block to plan-audit.md and testing that every placeholder is supplied.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Python's hash API, useful when folding the sibling `creates:` set into the AuditInputSnapshot fingerprint in a stable way.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Covers frozen dataclass fields, defaults and `field()` options, which matter when adding a captured sibling-path field to AuditInputSnapshot.
- [pathlib — PurePosixPath](https://docs.python.org/3/library/pathlib.html#pure-paths) — Explains how pure paths are normalized and compared, which helps when removing the audited plan's own `creates:` paths from the eligible set.
- [How to parametrize fixtures and test functions (pytest)](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Shows how to use `@pytest.mark.parametrize` to cover the same-roadmap, no-identity, other-roadmap and uncertain-identity cases in one test.
- [How to use temporary directories and files in tests (pytest tmp_path)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — Explains the `tmp_path` fixture, which the hermetic two-plan roadmap fixtures and fingerprint-change tests rely on.
- [Prompt engineering: Use XML tags to structure your prompts (Anthropic)](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags) — Anthropic's guidance on giving a prompt input clear boundaries, relevant when designing the new sibling-paths block and its explicit empty statement in plan-audit.md.

- `BUG_BACKLOG.md` — the source entry named above.
- `plan_tool/review.py` — `_eligible_planned_paths`, `_sibling_roadmap_identity`,
  `_planned_paths`, and the `plan-audit.md` renderer.
- `plan_tool/prompts/plan-audit.md` — the conceptual audit prompt.
- `plan_tool/review_persistence.py:AuditInputSnapshot` — the captured audit
  inputs and their fingerprint.
- `integrations/shared/DIRECTIVES.md` § "T — tool artifacts".
- `docs/implementation-plans/archive/2-sibling-planned-input-paths.md` — the
  deterministic half, already shipped.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Filtering or post-processing the model's findings. Matching finding prose
  against paths is the vocabulary-matching shape `CLAUDE.md` § "Validating a
  semantic property you cannot observe" refuses; the fix delivers the facts
  to the auditor and checks only that they were delivered.
- Paths created by plans outside the audited plan's roadmap, including the
  all-registered-plans set `_eligible_planned_paths` uses for a plan with no
  roadmap identity. That deterministic behavior is unchanged.
- Any other T class, including stale roadmap or seed paths.
- The deterministic missing-file check, which already merges sibling
  `creates:` (archived plan `2-sibling-planned-input-paths`).
- How a plan may depend on an unbuilt sibling plan (the separate
  `BUG_BACKLOG.md` entry on `create`'s "record unbuilt upstreams and stop"
  step).
- Audit blocking predicates, convergence policy, severity, or exit codes.

## Risks

- A long sibling list adds prompt size on large roadmaps. The block lists
  paths only, one per line. Measured 2026-11-17 on the largest real roadmap,
  Loom's `loom-aidlc-mvp` (nine plans, 276 distinct `creates:` paths): at most
  about 270 sibling paths, roughly 10 KB, per audited plan.
- Fingerprints and revisions of existing roadmap plans with siblings change
  once on upgrade, so their saved sampler checkpoints, shape-advisory
  fingerprints and report revisions read as stale once. That is intended;
  plans without siblings are unaffected.
- The model may still raise the finding despite the block. That is not
  tested by the suite; the plan records it as a limit rather than adding a
  finding filter.
- Changing a prompt contract can leave its descriptions disagreeing. Sweep by
  vocabulary, not only by identifier: `plan-audit.md`, the renderer's
  docstring, `DIRECTIVES.md` § T, and the `BUG_BACKLOG.md` entry.

## Testing

- A two-plan roadmap fixture where plan 2 cites a file plan 1 declares in
  `creates:`: the rendered audit prompt for plan 2 lists that path in the
  sibling block, and does not list plan 2's own `creates:`.
- A plan with no roadmap identity renders the explicit empty statement, even
  when other registered plans declare `creates:`.
- A plan from a different roadmap's `creates:` does not appear in the block.
- Uncertain identity evidence renders the empty statement, not a partial set.
- Changing a sibling plan's `creates:` changes the audit input fingerprint, so
  a prior conceptual result is not reused; an unchanged sibling set leaves the
  fingerprint unchanged.
- The public `audit_revision` is version 4 with `sibling_paths_digest`: null
  with no siblings, changed by a sibling `creates:` edit (so a saved report's
  `view_revision_status` turns `stale`), and `None` when a v1–v3 record is
  decoded.
- Every `${...}` placeholder in `plan-audit.md` is supplied by the renderer.
- `uv run pytest tests/ -q -n auto` is green.

## Acceptance criteria

- For a roadmap-derived plan, the rendered conceptual audit prompt lists each
  same-roadmap sibling's `creates:` path and tells the auditor not to report
  those as missing; for any other plan it states that none apply.
- The block's set equals the deterministic check's eligible set minus the
  plan's own paths for a plan with a roadmap identity, and is empty otherwise.
- The sibling set is part of the audit input fingerprint and of the public
  `audit_revision` (version 4, `sibling_paths_digest`), so a sibling edit makes a
  prior result stale for reuse and for a saved report's freshness.
- `DIRECTIVES.md` § "T — tool artifacts" no longer lists the sibling-path case
  as a false positive to ignore.
- Backlog reconciliation: the final step removes the originating
  `BUG_BACKLOG.md` entry only after full shipment. Authoring this plan does not
  remove it.

## Deferred

- Measuring whether a real model stops raising the sibling-path finding once
  the block is delivered. Postponed because the suite checks only delivery
  (see Risks); a measured follow-up on a real multi-plan roadmap batch can
  come back if the false finding persists.
