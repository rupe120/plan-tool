> **Withdrawn 2026-09-01** — Redesigned as an inline addition to plan-audit.md's property-coverage rule (same call, same finding response) instead of a separate downstream Claude pass -- separate-pass restatement risks drifting from what the original audit call actually found/read, since it works with less grounding than the pass that traced the plan. See BACKLOG #337 and plan_tool/prompts/plan-audit.md's property-coverage section for where this lands instead.
> Preserved here for history; do not edit.

---
title: Bare Correctness Restatement
intent: 'Every bare-stage `plan-correctness` finding from `completeness-audit` that
  carries the mandatory quoted citation (`plan-audit.md`''s "Property coverage versus
  delivery mechanisms" rule) gains a second, independent Claude call''s restatement:
  the same claim, with implementation-specific vocabulary (a named field, comparison
  mechanic, carrier, or data-structure choice) generalized to the property/guarantee/outcome
  the finding is actually grounded in, while the finding''s concrete failure consequence
  is preserved. The restatement is delivered beside the original finding — in the
  persisted report and its JSON — as evidence for whoever triages it. It renders no
  verdict, changes no severity or axis, and never suppresses, defers, reorders, or
  auto-applies a finding. The binary observable this plan ships: does a qualifying
  finding carry a populated restatement field, yes or no — not whether the restatement
  is correct, redundant, or convincing.'
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/bare-correctness-restatement.md
steps:
- id: 1
  title: Add an optional `restated_property` field to `Recommendation` and document
    it in DATA_CONTRACT.md
  intent: Give a finding a place to carry its restatement so the producer and the
    renderer have one agreed carrier instead of a side channel.
  files:
  - plan_tool/review.py
  - DATA_CONTRACT.md
  - tests/test_review.py
  - tests/test_data_contract.py
  complexity: low
  change_type: feature
  status: current
- id: 2
  title: Render a populated restatement as a sub-bullet under its correctness finding,
    with a fixed evidence-not-a-verdict disclaimer
  intent: Put the restatement in front of whoever triages the finding, worded so it
    cannot be read as a pass/fail judgment on the finding.
  files:
  - plan_tool/completeness_report.py
  - tests/test_completeness_report.py
  complexity: low
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the `restated_property` field the renderer reads off each Recommendation
- id: 3
  title: Add a deterministic check for whether a `plan-correctness` finding carries
    a quoted plan citation
  intent: Decide which findings qualify for a restatement, so a finding with no citation
    to re-read is never sent and never gets a field value.
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: low
  change_type: feature
- id: 4
  title: 'Add the restatement pass module and its prompt: one batched Claude call
    per audit round, no call when nothing qualifies'
  intent: Get an independent second read of each cited finding that names the property
    the citation actually supports, without re-deciding whether the finding is valid.
  files:
  - TESTING.md
  creates:
  - plan_tool/audit_restatement.py
  - plan_tool/prompts/plan-audit-restatement.md
  - tests/test_audit_restatement.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 3
  depends_on_notes:
    1: the field the pass writes its per-finding restatement onto
    3: the qualifying-finding predicate that selects the batch and makes the zero-qualifying
      skip decidable
- id: 5
  title: Run the restatement pass once per bare-stage run-grade completeness audit,
    after the conceptual audit resolves and before the report and sidecar are written
  intent: Make the restatement actually reach a reader, on exactly the audits the
    seed scopes it to, without spending a call on any other stage or grade.
  files:
  - plan_tool/cli/completeness_cmd.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 4
  depends_on_notes:
    2: the report rendering that displays whatever this wiring populates
    4: the pass this call site invokes on the resolved finding set
---
# Bare Correctness Restatement

## Overview

`plan-audit.md`'s property-coverage rule already tells the auditor to name a
plan-level property and its route rather than an unselected delivery
mechanism, and a companion rule now requires quoting the exact plan sentence
treated as that property. Both rules constrain the same pass that produces
the finding, and that pass has no way to catch a citation that is real but
misread — a scope or non-goal sentence ("X stays unchanged", "regardless of
Y") cited as if it were an affirmative guarantee. This plan adds one
independent, narrowly-scoped second pass, run after the bare-stage conceptual
audit converges, that restates each qualifying finding at plan altitude and
hands the restatement to the reader. It does not re-decide whether the
finding is valid.

## Problem statement

A bare-stage Correctness finding can cite a real, verbatim plan sentence and
still over-read it — the citation exists, but its force does not match the
claim attached to it. Neither the property-coverage rule nor the verbatim-quote
requirement catches this: both guard against a missing or fabricated citation,
not a real one that is misread, which is a comprehension error rather than a
vocabulary or existence one. `classify_likely_bare_mechanism`
(`plan_tool/review.py:2526`) is a phrase-based, advisory-only detector for the
opposite failure — a finding that names mechanism vocabulary a bare plan
hasn't selected — and its own docstring calls it "text-only"; it has no way to
judge whether a citation, read in its surrounding plan context, actually
supports the claim it is attached to. Re-running the same pass to self-check
its own citation is unreliable in practice: a full re-read of one such
finding, prompted specifically to check its grounding, still initially
accepted the weaker of two available anchors and only found the stronger one
on a second, differently-framed pass.

## Architecture

A new function, run once per `completeness-audit` bare-stage invocation after
`audit_plan_until_stable` returns its final finding set, collects every
`plan-correctness` finding carrying the mandatory quoted citation and sends
them — batched into one Claude call per audit round, never one call per
finding — to a dedicated prompt (new file under `plan_tool/prompts/`) with the
finding text and the full plan body. The call's only output per finding is one
restated sentence: the same claim, with implementation-specific nouns
generalized to the underlying property/guarantee/outcome, while the finding's
stated concrete consequence (what fails, and how) is preserved rather than
generalized away. `Recommendation` gains one new optional field
(`restated_property`) carrying this text; `DATA_CONTRACT.md` documents it.

The pass is independent of, and runs after, the pass that produced the
findings — a fresh call with no memory of having authored the original claim
— because a self-check inside the same call that just produced the finding is
prone to defending it rather than re-examining it.

Skip the call entirely when there are zero qualifying findings, so a clean or
non-conceptual audit spends nothing extra. Scope the pass to `STAGE_BARE` +
`GRADE_RUN` only, mirroring `classify_bare_mechanism_advisory`'s existing
scoping (`plan_tool/convergence_diagnosis.py:1413`): the property-vs-mechanism
question the citation exists to answer is bare-stage-specific, and once detail
selects a mechanism, `plan-audit.md`'s own rule already allows the
detail-grounded audit to require it.

Rendering reuses the existing per-finding evidence pattern: `suggested_action`
renders as `- Fix: {action}` (`plan_tool/completeness_report.py:1306`); the
restatement renders alongside it, in the persisted Markdown report and its
JSON sidecar, as plain delivered text with a fixed one-line disclaimer that it
is evidence, not a verdict — no severity marker, no pass/fail language.

## References

- `plan_tool/prompts/plan-audit.md` (§ "Property coverage versus delivery
  mechanisms") — the bare-stage rule this restatement consumes, including its
  verbatim-quote requirement.
- `plan_tool/review.py:2526` (`classify_likely_bare_mechanism`) — the sibling
  deterministic, advisory-only, text-only classifier this pass complements
  rather than replaces.
- `plan_tool/convergence_diagnosis.py:1413` (`classify_bare_mechanism_advisory`)
  — the `STAGE_BARE`/`GRADE_RUN` scoping precedent this plan mirrors.
- `plan_tool/completeness_report.py:1305-1306` — the existing
  `suggested_action` → `- Fix:` render path this restatement's rendering
  follows.
- `plan_tool/review.py:7697` (`_parse_plan_audit_findings_with_evidence`) and
  `:7751` (`_split_audit_fix`) — where findings and their citation land on
  `Recommendation` today.
- `docs/NONDETERMINISM_PLAN_DESIGN.md` — Rules 1-3, which this seed's
  Architecture and Out-of-scope sections satisfy: deterministic assembly and
  rendering around one directed, narrowly-scoped generative call with no
  closed-vocabulary verdict, so no disposition-gate machinery is needed.
- `docs/AUDIT_FLOW.md` (§ "Bare-plan policy: properties before mechanisms") —
  the operator-facing mirror of the rule this restatement is evidence for.
- `DATA_CONTRACT.md` — schema this plan must update for the new
  `Recommendation` field.
- BACKLOG #262 — precedent explicitly declining to auto-reclassify or
  auto-suppress findings; this plan's non-goals match that precedent's
  reasoning.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Any verdict, disposition, classification, or confidence label on the
  restatement — it is delivered text, not a judgment. No closed vocabulary
  such as "supported" / "scope-statement" / "unrelated".
- Auto-suppressing, auto-deferring, reordering, re-severity-ing, or moving a
  finding between the Correctness/Completeness axes based on the restatement.
  A human or session reads both and decides; nothing here decides for them.
- Any gate, exit-code flip, or refusal-to-advance keyed on the restatement.
- Running at `STAGE_DETAIL` or on Completeness-axis findings.
- Modifying `plan-audit.md`'s property-coverage rule or its verbatim-quote
  requirement — this pass consumes that citation, it does not change how it
  is produced.
- The deterministic `classify_likely_bare_mechanism` phrase classifier —
  untouched; this is an independent, complementary pass.
- A cross-finding summary, batch verdict, or triage ordering UI — one
  restatement per qualifying finding, nothing else.

## Risks

- **Read as a verdict anyway.** Even with no disposition field, a
  weak-sounding restatement invites "therefore invalid." The fixed disclaimer
  in the render output must say plainly this is delivered evidence, not a
  conclusion.
- **Over-generalization loses the finding's substance.** Stripping
  implementation nouns too aggressively can make a real gap read as vague or
  trivial — relocating the exact misread this plan exists to prevent.
  Acceptance criteria require the concrete consequence to survive
  restatement.
- **Cost.** One additional batched Claude call per bare-stage audit round with
  qualifying findings, bounded by batching (one call, not N) and by skipping
  entirely when nothing qualifies.
- **Prompt drift.** The restatement prompt and `plan-audit.md`'s
  property-coverage rule describe the same concept from two files; an edit to
  one that is not mirrored in the other reintroduces restatement drift. Name
  the relationship in the new prompt file's own header.

## Testing

- A finding whose citation is a scope/non-goal sentence ("X stays unchanged …
  regardless of Y") attached to a claimed property: the restatement must not
  invent support the citation lacks, and its weakness must be visible in the
  delivered text itself — assert on the rendered text, not a semantic grade.
- A finding whose citation genuinely and directly states the claimed
  guarantee: the restatement preserves the same claim in more general
  language and still names the concrete consequence.
- Zero qualifying findings: assert the stub invoker records zero calls.
- N qualifying findings in one round: assert exactly one call, not N.
- `STAGE_DETAIL` or non-`GRADE_RUN` audits: assert the pass never runs.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- Every bare-stage `plan-correctness` finding carrying a citation gets a
  `restated_property` value in the persisted report and its JSON; findings
  without a citation, or at any other stage/grade, get none.
- The rendered restatement carries no severity marker, verdict token, or
  pass/fail language — plain text plus the fixed evidence disclaimer.
- No existing convergence, apply, exit-code, or triage behavior changes:
  `completeness-apply`, `--fail-on-findings`, `is_blocking_finding`, and every
  existing gate produce identical decisions whether or not the new field is
  present.
- A restated finding still names the concrete consequence its original body
  stated, verified against both fixture cases above.

## Deferred

- Any future closed-vocabulary disposition built on top of this restatement
  (e.g. supported / scope-statement / unrelated), should evidence later show
  operators want one — a separate, evidence-backed request, not this plan.
- Extending the pass to `STAGE_DETAIL` or to Completeness-axis findings.
- A CLI flag to opt out of the extra call, if the batched cost proves to
  matter in practice.
