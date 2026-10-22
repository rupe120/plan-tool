# Skill-led demo and example conversion review

| Field | Record |
| --- | --- |
| Plan | [Teach demos and examples through the plan-tool skill](../docs/implementation-plans/2-skill-led-demo-examples.md) |
| Base | `80dfaa78e8ff95d1528a581e4fb10fba6ecc0b27` |
| Reviewed implementation snapshot | `81a83f5bb0409e58150c703a0d6add8ef381d133` |
| Branch | `implement/skill-led-demo-examples` |
| Checks | Four full-suite step gates pass; final suite: 14,698 passed, 66 skipped in 71.48s; 290 local file targets and 201 fragment targets resolve; fixture parser/round-trip checks pass |
| Reviewers | Two independent Codex `gpt-6.1-sol` report-only sessions, read-only sandbox |
| Disposition | Documentation review converges: two consecutive independent passes report no material findings; implementation and bounded live rehearsal complete |

## Scope and settled boundaries

The change retains dark mode and TTRPG, keeps CLI procedures as supporting
references, and teaches assistant requests for grounded seeds, monitoring and
result review. Seeds, bare plans/audits and details/grounded audits receive
explicit user review before the next consuming stage unless explicit delegation
covers continuation. Silence is not approval. All four plan steps remain
non-code; tool, skill, schema and monitoring behavior do not change.

The live dark-mode rehearsal ends at local paired export. It does not implement
the feature, create remote issues, prove browser behavior, regenerate TTRPG or
replace remote presentation checkpoints. The
[verification record](../docs/evidence/skill-led-demo-examples-verification.md)
retains stage conclusions, qualification, artifact hashes and the distinction
between narrative user-review checkpoints and assistant-reviewed batch artifacts.

## Findings and dispositions

| Finding | Disposition and evidence |
| --- | --- |
| Seed excerpt uses `Verification` instead of the canonical `Testing` heading | **fixed `e9bf52e68`** — the excerpt now demonstrates the heading SEED_FORMAT.md requires for ingestion; identifier/vocabulary review finds no sibling seed instance in the changed guides. |
| Pre-existing RUNBOOK fragment does not resolve to the canonical step layout heading | **fixed `49311e1a1`** — the link now uses the actual heading slug. Final accuracy review checks the source heading and all 201 fragment targets; no workflow or logic changes. |
| Three quick-recipe contradictions repeat across all shipped skill routers | **fixed `31fdf2f22` in the [separate skill repair](2026-10-21-skill-router-recipes-code-review.md)** — bare audit omitted, detail iteration default misstated, manual done-state recovery suggested. Shared directives and command help establish the correct behavior; installer coverage does not pin the wrong claims. No router fix belongs to this conversion. |
| Nested backend probe cannot initialize in the restricted step context | **fixed `81a83f5bb`** — parent-session access completes the real rehearsal and replaces the global blocker claim with context-specific failure/recovery provenance. This is an execution-context recovery, not a change to backend implementation. |
| Rehearsal granularity heuristic calls three files unrelated | **declined** — one small feature owns initialization, browser wiring and markup. The INFO/limited-confidence advisory remains visible; both audit reports retain `advisory-only`, confirmed/current, zero conceptual findings. No split or clean-audit claim is made. |

## Review passes

1. Report-only review of `80dfaa78e..2aab4c878`: no material correctness or
   completeness finding. Method: accepted plan/details, entire implementation
   diff, owning contracts, source and existing tests; fixture round-trip and
   whitespace checks. The live retry is pending at this snapshot, and no success
   is inferred. Artifact: `.tmp/skill-led-demo-examples.review-1.md`.
2. Independent report-only review of `80dfaa78e..81a83f5bb`: no material finding.
   Method: full diff plus actual rehearsal files, report qualification, all six
   artifact hashes, companion fingerprints, command lifecycle records and
   unchanged application/test files. Artifact:
   `.tmp/skill-led-demo-examples.review-2.md`.

The saved final responses identify their reviewed ranges and methods. Their
conclusions are retained here because `.tmp/` paths may disappear. The second
pass reviews the final evidence update independently; it does not assume the
first pass's conclusion. No production logic changes in this range. The later one-line navigation
correction (`49311e1a1`) is checked against the actual heading and the full
changed-document fragment set; final closure metadata adds no behavioral claim.

## Reconciliation and closure

`plan-tool --backend codex --model gpt-6.1-sol reconcile-code
skill-led-demo-examples --all -y` exits 0 and reports no code steps to reconcile.
All four steps are explicitly non-code; there is no eligible code sweep to
repeat. Log: `.tmp/skill-led-demo-examples.reconcile-sweep-1.log`.

The launcher completes and commits all four steps. The parent corrects the seed
excerpt, files the skill observation separately, completes the bounded rehearsal,
and synchronizes evidence/status. The final `uv run pytest tests/ -q -n auto`
passes with 14,698 passed and 66 skipped. Local story lint checks one actual
story without warnings, and the rehearsal's single baseline Node test passes.
Neither suite result is described as proof of an unimplemented feature.

The review loop closes as converged for the implemented documentation scope.
The skill-router correction has its own repair and review record; it is separate
from this demo implementation. Remote demo ref
replacement, release publication, browser testing and any fresh TTRPG run retain
their explicit boundaries; no merge or publication is performed by this review.
