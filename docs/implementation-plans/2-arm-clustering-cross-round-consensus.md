---
title: Arm Clustering Cross Round Consensus
intent: '`evaluate_arm_clustering`''s consensus requirement (`plan_tool/audit_shapes.py:194`,
  ≥2 samples per material finding, single agreeing target) becomes satisfiable from
  round-over-round `completeness-audit` history, not only from same-execution multi-pass
  observations — so the advisory stays available on `--audit-passes 1` runs, which
  CLAUDE.md''s stopping rule recommends for scope-contract-bound audits and which
  today disables the detector outright (the two settled conventions are currently
  mutually exclusive by construction).'
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Build arm-clustering consensus targets from saved audit history
  intent: Persist the plan-audit's existing `[audit-step:N]` per-finding target onto
    `Recommendation`/`RunFinding` (today it is parsed by `_split_audit_step_evidence`
    and then discarded into a transient in-call structure before a review is saved),
    then let a material finding earn a consensus step target from that persisted value
    across separate audit rounds, so arm-clustering has evidence to work with on the
    --audit-passes 1 runs that give it only one same-execution sample.
  files:
  - plan_tool/review.py
  - plan_tool/convergence_diagnosis.py
  - DATA_CONTRACT.md
  - tests/test_review.py
  - tests/test_convergence_diagnosis.py
  - tests/test_data_contract.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/01-build-arm-clustering-consensus-targets.md
  status: current
- id: 2
  title: Add the cross-round arm-clustering advisory to the convergence diagnosis
    and its render
  intent: Give the cross-round result a place to live on the diagnosis and a printed
    line an operator actually sees, matching how impact_recurrence and edit_drift
    already ride along without changing the verdict. Since this step adds the new
    `audit_shapes` import, also correct this module's own "cycle-free leaf" docstring
    paragraph in the same edit (it already omits `convergence` and `granularity`,
    which the module already imports today, independent of this plan) rather than
    leaving that self-description fix for a later, doc-only step to reach into a code
    file for.
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the classifier function and its advisory record, which diagnose_convergence
      calls and the render lines read fields off
  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/02-cross-round-arm-clustering-advisory.md
- id: 3
  title: Parse the plan once in cmd_convergence instead of inside _current_audit_stage
  intent: Make the parsed plan reachable from cmd_convergence so the next step can
    read its committed steps without parsing the file a second time or copying the
    best-effort try/except. The hoisted `parse_plan` call must keep degrading to `diagnose_convergence`'s
    pre-stage-bar blanket-blocking defaults on a parse failure or missing plan — the
    same outcome `_current_audit_stage`'s existing try/except gives today — so `cmd_convergence`'s
    documented "always exits 0, never surfaces an error" contract survives the move
    unchanged.
  files:
  - plan_tool/cli/convergence_cmd.py
  - tests/cli/test_convergence_cmd.py
  allowed_mentions:
  - plan_tool/convergence.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/03-parse-plan-once-cmd-convergence-instead.md
- id: 4
  title: Pass committed step ids to the diagnosis from the convergence and completeness
    surfaces
  intent: Turn the classifier on for real operators by threading real committed step
    ids *and* each step's current status (step 1's function signature accepts both
    as parameters — a bare id list alone carries no status, and step 1's done-step
    drop check needs it — but this step is what supplies real values from the plan's
    parsed `Step` objects, not step 1) into it from the two places the sibling advisories
    already print, so `plan-tool convergence` and completeness stderr both surface
    it. Also thread `cmd_convergence`'s existing `args.grade` into step 2's classifier
    as `detail_grade`, mirroring the grade threading `_current_audit_stage` already
    gets in the same command — otherwise the fingerprint capture defaults to run
    grade regardless of which grade the saved history was actually audited at.
  files:
  - plan_tool/cli/convergence_cmd.py
  - plan_tool/cli/completeness_cmd.py
  - tests/cli/test_convergence_cmd.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: the declared_step_ids keyword on diagnose_convergence and the render lines
      these two handlers print
    3: the parsed plan hoisted into cmd_convergence, so committed step ids come from
      the parse the stage lookup already did
  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/04-pass-committed-step-ids-diagnosis.md
- id: 5
  title: Update the docs for the cross-round advisory and settle the backlog entries
  intent: 'Keep the always-injected guidance honest once this ships, so the next session
    does not read `--audit-passes 1 disables it outright`, an open #264, or either
    external restatement of `convergence_diagnosis.py`''s import set as still true.
    CLAUDE.md''s "cycle-free leaf" bullet and `docs/ARCHITECTURE.md`''s "Convergence
    diagnostic" entry both restate that import set already inaccurately (CLAUDE.md
    omits `granularity`; both predate this plan and are wrong independent of it),
    so correct both to the module''s full current set (`review_persistence`, `review`,
    `locator`, `convergence`, `granularity`) plus the two new `audit_shapes` and
    `jira_grade` edges step 2 adds — not only append the new edges onto an
    already-wrong baseline. The
    module''s own docstring paragraph is step 2''s fix, made where the import lands,
    not this step''s.'
  files:
  - CLAUDE.md
  - docs/ARCHITECTURE.md
  - docs/how-to/pipeline/audit.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 4
  depends_on_notes:
    4: the shipped surfaces and the final import edge, so the docs describe what landed
      rather than what was proposed
  detail: docs/implementation-plans/plan-details/arm-clustering-cross-round-consensus/05-update-docs-cross-round-advisory-settle.md
---
# Arm Clustering Cross Round Consensus

## Overview

`arm-clustering` today only sees consensus built from ≥2 passes inside one
`completeness-audit` invocation, where the prompt's carried-findings mechanism
keeps a finding's `rec.id` stable across passes. `--audit-passes 1` — the
setting this repo's own stopping-rule convention steers scope-contract-bound
audits toward — collapses that to one sample, so the detector goes dark on
exactly the audits it is meant to help decide. A round-over-round version reads
persisted history across separate invocations instead, where finding ids are
not stable but step-focused matching already is (per `_matches`), and answers a
related question: does this arm keep surfacing across separate saved audits,
not just within one frozen snapshot. This mechanism checks recurrence only —
it does not check whether a fix was attempted between rounds, so a finding
that recurs because nothing changed reads the same as one that recurs despite
a genuine remediation attempt; narrowing that distinction is explicitly out of
scope (see Out of scope).

## Problem statement

`evaluate_arm_clustering` takes `consensus_targets: Mapping[str, int]` as a
plain input; nothing about its own logic is same-execution-specific. The
mutual exclusion is entirely in what the *caller* (`review.py:8040`) currently
feeds it, plus one persistence gap: the plan-audit prompt already emits an
optional `[audit-step:N]` per-finding target and `_split_audit_step_evidence`
already parses it (inside `_parse_plan_audit_findings_with_evidence`), but the
parsed value is diverted into the transient `_AuditTagObservation` there, and
into `observations_by_id` only across multiple passes inside
`audit_plan_until_stable` — and never reaches the saved
`Recommendation`/`RunFinding` — both hardcode `step_id=None` for these sources,
and `RunFinding`'s own docstring says the step a completeness finding is about
is resolved by parsing `anchor`, which only incidentally carries a step number
when the model's concept-slug happens to start with `stepN-`. Building a
cross-round mapping therefore needs one new persisted field, plus answering the
"same target" question round-over-round without inventing new *identity*
machinery: a step can be renumbered, split, or merged between rounds, and the
existing `_matches` tiering exists precisely to survive that — it is the
settled precedent, not a gap to redesign.

## Architecture

1. Persist the per-round step target. Add a new `audit_step_target: Optional[int]`
   field to **both** `Recommendation` and `RunFinding` — two separate edit
   sites, not one: `Recommendation.audit_step_target` is populated at the
   parse site that already computes the value
   (`_split_audit_step_evidence`'s `target`, currently diverted only into
   `_AuditTagObservation`); `RunFinding.audit_step_target` is populated
   separately in `_finding_from_recommendation`
   (`convergence_diagnosis.py:200`), which copies fields **one at a time**
   (its own docstring calls this a deliberate "persisted-field whitelist") and
   is never generic `asdict`/`Recommendation(**r)` — that generic round-trip
   applies only to `Recommendation`'s own JSON persistence via `save_review`.
   Every cross-round consumer this plan builds reads `RunFinding`, not
   `Recommendation`, so missing the second site leaves the field permanently
   `None` on everything this plan actually consumes. The two fields get two
   different kinds of documentation, landed in **this same step**, not
   deferred to step 5's docs pass: `Recommendation.audit_step_target` is
   persisted/serialized (round-trips via `save_review`), so it gets a row in
   `DATA_CONTRACT.md`'s existing `Recommendation` table, same as `anchor` or
   `impact`. `RunFinding` is not persisted on its own — its own docstring
   calls it a flattening "from a saved report's recommendation list," and
   `DATA_CONTRACT.md` documents only persisted/serialized schemas, which is
   why none of `convergence_diagnosis.py`'s other dataclasses have an entry
   there — so `RunFinding.audit_step_target` is documented inline in
   `RunFinding`'s own docstring instead, matching how `step_id`, `anchor`, and
   `impact` are already documented there, not as a new `DATA_CONTRACT.md`
   section. This is the one new piece of persisted state this plan adds;
   `evaluate_arm_clustering` and the same-execution consensus path are
   unaffected — they keep reading `observations_by_id` and the transient tag
   directly.
2. Materiality: treat a matched finding as material via
   `is_blocking_finding(finding, stage=window_audit_stage, classify_domain=…)`
   checked **only against the newest round's copy** of that finding —
   reusing only the stage-bar half of `classify_edit_drift`'s
   `_edit_drift_eligible` (`convergence_diagnosis.py:885`), and the same
   newest-round keying point 7 already uses for the output mapping.
   `_edit_drift_eligible` also runs a second check —
   `_is_resolved_in_run(annotations.get(finding.id))`, dropping a finding the
   operator already declined between rounds — that this plan deliberately
   does **not** reuse: Out of scope already refuses to gate cross-round
   consensus on "a resolved annotation," so a finding an operator explicitly
   declined in an earlier round can still feed a consensus arm here, unlike
   in `edit_drift`. A finding's severity/impact tag can differ across matched rounds;
   only the newest round's copy decides materiality, never a mix or an
   older round's. This is a different, deliberate choice from same-execution
   arm-clustering's `is_blocking_impact` +
   `build_low_impact_demotion_lookup(repo_root)` (`review.py:7929,7774`),
   which rebuilds a live per-run calibration lookup and was designed for a
   different consumer (the live-`Recommendation` apply loop). Reusing that
   calibration path against saved history is out of scope (see Out of scope);
   the two materiality rules are intentionally not required to agree.
3. Restrict to the newest passes of a purpose-built window sized to fire at the
   same 2-round minimum evidence bar as same-execution consensus
   (`len(sample_ids) < 2`) — a new, smaller window constant, not
   `classify_impact_recurrence` / `classify_edit_drift`'s shared
   `WINDOW_SIZE=3` (sized for an unrelated "recurs without shrinkage" claim
   that needs 3 points). Draw only same-`audit_stage` collapsed passes via
   `build_collapsed_completeness_passes`; never mix bare and detail-stage
   history in one window.
4. Match findings across that window via the existing tiered `_matches` (step
   focus → concept-slug anchor → fuzzy title) — no new identity scheme. A
   finding is consensus-eligible only when it matches in every pass of the
   window (for a 2-pass window this is the "≥2 passes" rule already stated).
5. A matched finding's target per round is its new persisted
   `audit_step_target` (point 1), never `RunFinding.step_id` (always `None`
   for these sources). Consensus holds only when every round in the match
   shares one non-`None` target — identical in spirit to today's
   `len(target_ids) != 1` fail-closed check.
6. Drop a finding from **both** the `consensus_targets` mapping **and** the
   `material_finding_ids` set passed to the classifier whenever: its per-round
   targets disagree; a target is missing on some round; a step's renumbering
   breaks target continuity even though the finding still matches by
   anchor/title; the single agreed target is not among the *current* round's
   `declared_step_ids` (the step was deferred, marked `wont_do`, deleted, or
   renumbered since the last matched round); **or** the target step's current
   `status` is `done` — which requires each committed step's live `status` on
   hand, not only its id. The function built in this step therefore takes a
   second parameter carrying status alongside `declared_step_ids` (e.g. the
   plan's parsed `Step` objects, or an id→status map) — `declared_step_ids`
   itself (a bare `Sequence[int]`, matching `evaluate_arm_clustering`'s own
   parameter at point 7) carries no status and this check must never assume
   it does. Step 1/2 test this with fixture status data; step 4 is what
   later supplies the real value at the CLI layer — this function does not
   depend on step 4 to exist or be tested.
   `declared_step_ids` / `committed_step_ids` is built
   from `StepScope.COMMITTED` (`completeness_report.py:122`,
   `review.py:8059`), which is the commitment axis, not the lifecycle axis
   (`schema.py:StepScope`) — a shipped step stays `scope: committed` and so
   stays in that list, so list membership alone cannot detect a target that
   shipped between the matched rounds and a later `plan-tool convergence`
   read. Check the target step's `status` directly; this plan's own
   governing rule (a `done` step is "shipped: context, never a target") is
   how a stale-but-shipped target must be treated here too. Never guess a
   target and never pass an unresolved or stale one through.
   `evaluate_arm_clustering` returns `None` for the *entire* advisory the
   moment any id in `material_finding_ids` lacks a target inside the
   `step_positions` built from `declared_step_ids`
   (`plan_tool/audit_shapes.py:238-242`), so the caller must pre-filter every
   one of these cases before calling it — not just cross-round disagreement.
7. Feed the resulting `consensus_targets` (keyed by the newest round's finding
   ids), that same resolved-subset `material_finding_ids`, and the newest
   round's committed `declared_step_ids` into `evaluate_arm_clustering`
   unchanged. Two more of the leaf's parameters are not optional in practice
   and must be supplied, matching same-execution's own call
   (`review.py:8064-8076`): `material_finding_evidence` — built from the
   newest round's own `RunFinding.anchor`/`.source` for each resolved id
   (already-persisted fields, no new plumbing); and `source_plan_fingerprint`
   — specifically `AuditInputSnapshot.capture(plan_path, repo_root).fingerprint`
   (`review_persistence.py:235`), the "dedicated exact audit-input
   fingerprint" `DATA_CONTRACT.md` says presentation must use for this exact
   field, **not** the cheaper `compute_plan_fingerprint(plan_path)`
   (`review_persistence.py:358`) — the tempting choice, since
   `cmd_convergence` already computes that one for its own telemetry
   (`convergence_cmd.py:105`); the two are documented as non-interchangeable
   here. The capture call must also thread `detail_grade` (the same
   `run`/`jira` grade `cmd_convergence`'s existing `args.grade` already
   supplies `_current_audit_stage` for the same command,
   `convergence_cmd.py:86`) — `AuditInputSnapshot.capture` defaults to run
   grade otherwise, so a jira-grade-audited plan's fingerprint would be
   captured against the wrong bundle, one this plan's own reasoning for
   using `AuditInputSnapshot.capture` over the cheaper hash exists precisely
   to avoid. Leaving either parameter at its signature default (`()` / `""`) is a
   caller bug, not a valid choice — but **nothing on this code path catches
   it at runtime**: `evaluate_arm_clustering` itself only type-checks
   `source_plan_fingerprint` (`audit_shapes.py:216`, no non-empty check), this
   classifier deliberately never calls `is_well_formed_audit_shape_advisory`
   (point 8 below — that validator is for a saved, reloaded sidecar, not this
   fresh-computed one), and the render this plan adds (point 8's
   `_arm_clustering_lines`) never reads `material_finding_evidence` or
   `source_plan_fingerprint` at all — `completeness_report.py`'s
   anchor-skip rendering belongs to the separate same-execution saved-sidecar
   advisory's own renderer. A caller bug here produces an `AuditShapeAdvisory`
   that looks normal and renders identically, silently wrong forever; the
   **only** protection is the explicit test asserting both arguments are
   real (Testing, Acceptance criteria). The leaf's own gap-free
   proper-majority-arm math is not touched.
8. When the classifier has nothing to report — including when a previously-
   firing arm's cross-round consensus becomes unresolvable — the render emits
   nothing, the same silence `impact_recurrence` / `edit_drift` already use
   for their own non-firing precondition. This is a stated decision, not an
   open question (see Acceptance criteria): no separate "insufficient
   evidence" line is added. The cross-round advisory is computed fresh and
   rendered immediately each `plan-tool convergence` run, exactly like
   `impact_recurrence` / `edit_drift` — never persisted as its own object and
   reloaded later. It therefore does **not** call
   `is_well_formed_audit_shape_advisory`: that validator exists to fail
   closed on a *saved, user-editable* sidecar's advisory (its own docstring:
   "saved sidecars are user-editable input"), a scenario that doesn't apply
   here since nothing round-trips this value through disk. Since the
   pre-existing same-execution advisory can also fire independently in the
   same `plan-tool convergence` / completeness-audit output, the cross-round
   line names its evidence source (e.g. "across N saved rounds") so the two
   are never ambiguous to the reader.

## References

- [difflib — Helpers for computing deltas (Python 3 Standard Library)https: — Documents SequenceMatcher.ratio()'s [0, 1] similarity semantics and the 0.6 close-match convention behind the tier-3 fuzzy-title leg of _matches, which cross-round consensus reuses unchanged.
- [collections.abc — Abstract Base Classes for Containershttps: — Defines the Mapping ABC and its mixin contract, which the new caller must satisfy when it builds the consensus_targets: Mapping[str, int] argument evaluate_arm_clustering already accepts.
- [collections — Container datatypes (Counter, defaultdict, deque)https: — Reference for Counter and defaultdict, the natural structures for tallying per-round audit_step_target values and enforcing the 2-sample / single-agreeing-target consensus guard.
- [itertools — Functions creating iterators for efficient loopinghttps: — Documents islice and pairwise for taking the newest N same-audit_stage collapsed passes for the new 2-pass consensus window.
- [dataclasses — Data Classeshttps: — Covers field defaults for the new `audit_step_target` field on `Recommendation` / `RunFinding` and for any new advisory result type this work returns.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Any change to `evaluate_arm_clustering`'s own signature or arm math in
  `audit_shapes.py` — it already accepts a plain mapping; this seed supplies a
  second way to build one.
- Any change to the existing same-execution (`--audit-passes N > 1`) consensus
  path in `review.py` — both paths coexist.
- Any new blocking gate, exit-code flip, or apply-dispatch keyed on the
  advisory. `arm-clustering` stays recommend-only, exactly as
  `impact_recurrence` / `edit_drift` are — this seed adds an evidence source,
  not a gate.
- Reviving the retired `spinning` / `FORK_*` region-trending diagnostic
  (BACKLOG #251, cut 2026-08-08) or any of its vocabulary — this works over
  adjacent territory (cross-round finding history) and must not resemble it.
- Modifying `classify_impact_recurrence` / `classify_edit_drift`'s own logic;
  their exposed helpers (`build_collapsed_completeness_passes`, `_matches`) are
  consumed read-only.
- Changing `--audit-passes 1`'s behavior, the stopping-rule recommendation, or
  any other convergence-policy-boundary caller class.
- Backfilling consensus for history predating this change, or for rounds run
  at a different `audit_stage` than the newest one.
- Repurposing `Recommendation.step_id` / `RunFinding.step_id` (which stay
  `None` for these sources) to carry the new per-round target — it is a new,
  separate field, not a reuse of `step_id`.
- Rendering an explicit "insufficient evidence" signal when a previously-
  firing arm's cross-round consensus becomes unresolvable — the render stays
  silent (Architecture point 8).
- Reusing `is_blocking_impact` / `build_low_impact_demotion_lookup`'s live
  per-run calibration path against saved history, or otherwise making
  cross-round materiality agree with same-execution materiality — they are
  deliberately different rules for different consumers (Architecture point 2).
- Gating cross-round consensus on any evidence that a fix was attempted
  between matched rounds (a changed fingerprint, a resolved annotation) — the
  mechanism checks recurrence only (see Overview).

## Risks

- A naive per-round target could silently misattribute a finding across a
  renumbered step if `_matches` is bypassed instead of reused — this is why
  reuse, not reinvention, is the settled decision above.
- `_matches` itself can misattribute even when used exactly as specified:
  tier 1 ("step focus") matches purely on a leading `step<N>`/`step-<N>`
  anchor token, with no check that the rest of the anchor or title agree.
  Two genuinely different findings that both happen to be anchored
  `step5-...` in different rounds would match at tier 1, letting the newer
  one inherit an older, unrelated finding's `audit_step_target` as though it
  were the same finding recurring — fabricating the two-round evidence this
  plan exists to require, for a finding that is really new. This is an
  inherent property of the reused precedent, not a defect this plan
  introduces, but it is now load-bearing in a way it wasn't for
  `impact_recurrence`/`edit_drift` (a false match there dilutes a count; here
  it manufactures a consensus target).
- Only `Recommendation`'s new field round-trips through generic `asdict` /
  `Recommendation(**r)` serialization; `RunFinding`'s copy does not — it is a
  field-by-field whitelist (`_finding_from_recommendation`) that silently
  stays `None` forever if that site is missed, even though `Recommendation`'s
  half works fine. This is why Architecture point 1 names both sites
  explicitly rather than treating them as one edit.
- `tests/test_data_contract.py`'s drift guard checks the *documented* schema,
  but it only fails on a documented field that no longer exists — never on a
  real field the doc simply omits — so nothing in the suite would catch
  `Recommendation.audit_step_target` landing in step 1 while its
  `DATA_CONTRACT.md` row waited for step 5. Architecture point 1 now pins
  both fields' documentation to step 1 itself for exactly this reason: the
  test suite cannot be trusted to catch a deferred-doc split on its own.
- A silent non-fire (Architecture point 8) is easy to misread from the outside
  as "the arm resolved" rather than "evidence became unavailable." Acceptance
  criteria settle this as accepted, explicitly-decided behavior rather than a
  gap, and step 5's docs must state the decision in those words rather than
  leaving it to be inferred from the absence of a line.
- Windowing on the wrong `audit_stage` (mixing bare and detail history) would
  manufacture a consensus target that never coexisted in one coherent audit.
- `evaluate_arm_clustering`'s `material_finding_evidence` and
  `source_plan_fingerprint` both default to empty/falsy values that are easy
  to leave unset by omission rather than by decision — and neither default
  is caught by anything at runtime on this code path (Architecture point 7):
  no validator call, no render read. A caller bug here ships a normal-looking
  but silently-wrong advisory forever. Both are named explicitly in
  Architecture point 7 so they are supplied by decision, and the explicit
  test asserting real values is the only actual protection.

## Testing

Prove: (1) the plan-audit's parsed `[audit-step:N]` tag round-trips onto a
saved `Recommendation` via `save_review`/`resolve_saved_review`, documented in
`DATA_CONTRACT.md`, and separately onto `RunFinding` via
`_finding_from_recommendation`, documented in `RunFinding`'s own docstring;
(2) materiality for cross-round consensus is computed via `is_blocking_finding`
against **only the newest round's copy** of a matched finding (reusing only
`_edit_drift_eligible`'s stage-bar half, never its annotation-based exclusion
— a finding declined between rounds is not excluded here), independent of and
not required to agree with same-execution's `is_blocking_impact` +
calibration-lookup materiality — a finding whose severity/impact tag differs
between an older and the newest matched round is decided by the newest
round's tag alone; (3) a finding with a
stable `_matches` identity and one agreeing persisted `audit_step_target`
across the 2-round window produces a resolved consensus target; (4) a finding
whose matched target disagrees, is missing on one round, agrees across the
window but is absent from the *current* `declared_step_ids`
(deferred/`wont_do`/deleted/renumbered since the match), **or** agrees on a
target whose step `status` is now `done`, is dropped from **both**
`consensus_targets` and the `material_finding_ids` passed to
`evaluate_arm_clustering`, never causing the whole advisory to return `None`;
(5) a renumbered step that breaks target continuity but still matches by
anchor/title is dropped the same way, not read as a broken arm; (6)
mixed-`audit_stage` history is never combined into one window; (7)
`--audit-passes 1` with 2 qualifying prior rounds now produces an
`arm-clustering` advisory where it previously produced none, while the
same-execution multi-pass path and the leaf are both unchanged by this work;
(8) when a previously-consensus arm loses agreement, the render is silent, not
an explicit "insufficient evidence" line; (9) the call to
`evaluate_arm_clustering` always passes non-default `material_finding_evidence`
(anchor/source per resolved id, from the newest round's `RunFinding`) and a
non-empty `source_plan_fingerprint` built from
`AuditInputSnapshot.capture(plan_path, repo_root).fingerprint`, never from the
cheaper `compute_plan_fingerprint` `cmd_convergence` already has on hand for
its own telemetry — nothing on this code path fails or renders differently
if either is left at its signature default (`is_well_formed_audit_shape_advisory`
is never called here, and the render never reads either field), so this exact
test is the *only* thing that would ever catch getting it wrong; (10) two
differently-worded findings that happen to share a leading `step<N>` anchor
token across two rounds are never treated as one recurring finding for
consensus purposes — `_matches` tier 1 alone is not sufficient grounds to
inherit a target; (11) `cmd_convergence`'s `--grade` flag reaches the
fingerprint capture as `detail_grade`, so a plan whose saved history was
audited at jira grade gets a jira-grade fingerprint, not the run-grade
default `AuditInputSnapshot.capture` would otherwise silently use.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (refactor) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- The plan-audit's existing `[audit-step:N]` tag is persisted onto
  `Recommendation`/`RunFinding` (new `audit_step_target` field on each) — no
  existing field carries it today. Both fields' documentation
  (`Recommendation`'s new `DATA_CONTRACT.md` row; `RunFinding`'s own
  docstring, since it isn't a persisted schema) lands in step 1 itself, not
  deferred to step 5.
- `evaluate_arm_clustering` fires from round-over-round history alone under
  `--audit-passes 1` once 2 qualifying same-stage rounds exist, using that new
  persisted target plus existing cross-round identity machinery (`_matches`,
  `build_collapsed_completeness_passes`) — no invented second identity scheme.
- Cross-round materiality is `is_blocking_finding`-based (matching
  `classify_edit_drift`'s existing use on `RunFinding`s), stated explicitly as
  a deliberately different rule from same-execution's calibration-lookup
  materiality — not an attempt at equivalence.
- The `material_finding_ids` passed to the classifier is always exactly the
  subset with a resolved, **current, still-open** consensus target —
  disagreeing, missing, renumbering-broken, stale-vs-current-`declared_step_ids`,
  and shipped-(`status: done`)-target findings are all dropped the same way; a
  finding without one is never passed through unchanged and never silently
  voids the whole advisory.
- Cross-round materiality is decided from the newest matched round's copy of a
  finding only, never an older round's or a mix, matching the newest-round
  keying already used for the output mapping.
- The same-execution consensus path and `evaluate_arm_clustering`'s own
  signature/math are unmodified.
- `arm-clustering` remains recommend-only: no gate, dispatch path, or
  continuation rule reads the cross-round result any differently than the
  same-execution one does today.
- When a previously-eligible arm's cross-round consensus becomes unresolvable,
  the render stays silent — the same behavior as any other non-firing
  classifier check — rather than an explicit "insufficient evidence" signal;
  this is documented as a stated decision, not left to be inferred.
- CLAUDE.md's Cycle-free import constraints list, `convergence_diagnosis.py`'s
  own "cycle-free leaf" module-docstring paragraph, *and*
  `docs/ARCHITECTURE.md`'s "Convergence diagnostic" entry all name the
  module's true current import set (`review_persistence`, `review`,
  `locator`, `convergence`, `granularity`) plus the two new `audit_shapes` and
  `jira_grade` edges — not just the new edges appended onto whatever each
  already said, since all
  three are already wrong today independent of this plan (CLAUDE.md and
  `docs/ARCHITECTURE.md` both omit `granularity`; the module's own docstring
  omits both `convergence` and `granularity`).
- The call into `evaluate_arm_clustering` always supplies real
  `material_finding_evidence` and a real `source_plan_fingerprint` built from
  `AuditInputSnapshot.capture(...).fingerprint` (never the cheaper
  `compute_plan_fingerprint` `cmd_convergence` already has lying around, and
  never the signature's `()` / `""` defaults) — not because a runtime check
  would catch the default (nothing on this code path does), but because the
  dedicated test is the only thing that ever would, and a caller bug here
  otherwise ships a silently-wrong advisory that looks and renders normally.
- The cross-round advisory's printed line names its evidence source (e.g.
  "across N saved rounds") so an operator seeing `arm-clustering` fire can
  tell it apart from the pre-existing same-execution advisory, which can fire
  independently in the same output.
- The fingerprint capture is grade-aware: `cmd_convergence`'s `args.grade`
  reaches `AuditInputSnapshot.capture` as `detail_grade`, the same threading
  `_current_audit_stage` already gets in the same command, so a jira-graded
  plan's fingerprint reflects the jira-grade bundle, not a silent run-grade
  default.
- BACKLOG.md's #264 entry is removed (or updated to note partial delivery, if
  scope is deliberately trimmed during execution) once this ships.

## Deferred

Any generalization of cross-round `_matches`-based consensus to a signal beyond
`arm-clustering` is a separate, separately scoped effort. The retired region-
trending diagnostic (BACKLOG #251) stays retired; this seed does not reopen it.
