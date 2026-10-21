> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Bare Plan Correctness Apply Route
intent: On a bare or partially-detailed plan, conceptual-**correctness** gaps get
  an apply route they can actually use, the `BLOCKED` verdict that route newly exposes
  points the operator at `plan-tool detail` rather than at `plan-tool split`, and
  the bare audit stops raising edge-case gaps whose only remedy is the detail file
  the audit ran before.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Pull the shared bare/jira apply fence in completeness_report.py into one
    helper
  intent: Gives the two next-step renderers a single fence to change, so the report
    prose and the console block cannot drift apart when the next step splits it by
    axis.
  files:
  - plan_tool/completeness_report.py
  - tests/test_completeness_report.py
  complexity: low
  change_type: refactor
  gate:
  - test "$(grep -c 'bare_plan or jira_grade' plan_tool/completeness_report.py)" -le
    1
  detail: docs/implementation-plans/plan-details/bare-plan-correctness-apply-route/01-pull-shared-bare-jira-apply-fence.md
  status: done
- id: 2
  title: Let a bare plan's correctness gaps keep the completeness-apply route in the
    report and console next steps
  intent: A correctness gap targets the plan body and step titles, which exist on
    a bare plan, so the operator gets the apply verb for exactly the half that can
    use it — most valuable before N detail calls are spent on a decomposition a correctness
    finding would have corrected. Lands after step 4 so the verb is real before any
    surface names it, and covers all three surfaces this module owns — the report
    prose, the console command block, and `console_summary`'s completeness line.
  files:
  - plan_tool/completeness_report.py
  - tests/test_completeness_report.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 4
  detail: docs/implementation-plans/plan-details/bare-plan-correctness-apply-route/02-let-bare-plan-correctness-gaps-keep.md
  status: done
- id: 3
  title: Point the BLOCKED next step at plan-tool detail on a bare plan instead of
    split
  intent: Stops the tool telling an operator to restructure a step when the real remedy
    is to author its detail file — a defect already reachable today via bare-plan
    `--iterate` deterministic applies, and more so once the correctness route opens.
  files:
  - plan_tool/completeness_report.py
  - tests/test_completeness_report.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/bare-plan-correctness-apply-route/03-point-blocked-next-step-plan-tool.md
  status: done
- id: 4
  title: Let completeness-apply walk correctness gaps on a bare plan while still skipping
    completeness gaps
  intent: Makes the route real before any surface advertises it — this step lands
    first so no commit ever names a verb that warns and exits without applying anything.
    It owns the axis decision at the verb; steps 2 and 5 then describe what it already
    does.
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/launcher.py
  - tests/cli/test_completeness_cmd.py
  - tests/test_launcher.py
  - docs/cli/completeness-apply.md
  - docs/cli/README.md
  - tests/cli/package_surface_help.golden.txt
  allowed_mentions:
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_apply_parallel.py
  - plan_tool/review_walk.py
  - plan_tool/prompts/apply-finding.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/bare-plan-correctness-apply-route/04-let-completeness-apply-walk-correctness.md
  status: done
- id: 5
  title: Name completeness-apply for correctness gaps in the grouped report's bare-plan
    next steps
  intent: Keeps the third next-steps surface saying the same thing as the saved report
    and the console block, so one run does not describe its own remedies three different
    ways.
  files:
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  allowed_mentions:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/completeness_report.py
  - plan_tool/review_walk.py
  complexity: low
  change_type: feature
  depends_on:
  - 2
  - 4
  detail: docs/implementation-plans/plan-details/bare-plan-correctness-apply-route/05-name-completeness-apply-correctness.md
  status: done
- id: 6
  title: Narrow bare-step edge-case findings in the audit prompt's detail-coverage
    block
  intent: Admits a bare step's missing-edge-case finding only when its remedy is a
    step or an acceptance criterion, so a bare audit catches decomposition gaps instead
    of pre-empting the detail stage's job.
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/bare-plan-correctness-apply-route/06-narrow-bare-step-edge-case-findings.md
  status: done
- id: 7
  title: 'Update CLAUDE.md, AUDIT_FLOW.md, and BACKLOG #83 for the axis-split bare-plan
    fence'
  intent: 'CLAUDE.md:278 and BACKLOG #83 both assert the blanket ''detail-level actions
    unlock only once a complete detail bundle exists'' contract this plan replaces,
    and a stale claim in CLAUDE.md misleads every later session because it loads into
    all of them.'
  files:
  - CLAUDE.md
  - docs/AUDIT_FLOW.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  gate:
  - '! grep -q ''detail-level actions unlock only once a complete detail bundle exists''
    CLAUDE.md'
  depends_on:
  - 2
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/bare-plan-correctness-apply-route/07-update-claude-md-audit-flow-md-backlog.md
  status: done
---
# Bare Plan Correctness Apply Route

## Overview

A completeness audit already computes `is_bare` per run and conditions the
audit prompt on it. It then uses that same flag for a second purpose it does
not fit: withholding the `completeness-apply` route from **both** conceptual
axes at once. The two axes do not have the same grounding needs. A correctness
gap — unsound design, internal contradiction, conceptual ordering hazard —
targets the plan body, step titles, and acceptance criteria, all of which exist
on a bare plan. A completeness gap leans on the detail bundle that has not been
authored. Splitting the fence by axis restores the route to the half that can
use it, and is most valuable exactly where it is currently refused: before N
detail calls are spent on a decomposition that a correctness finding would have
corrected.

**Three decisions ship together, and each one is about the same operator.** The
axis split opens the route; the BLOCKED remedy stops the newly-opened route
handing out a structural fix for a detailing problem; and the edge-case
narrowing stops the bare audit filling that route with gaps whose only remedy is
the detail file the audit ran before. Split them apart and a bare-plan audit
still hands its operator a pile of findings the new route cannot usefully close.

## Problem statement

**The fence is one flag doing two jobs.** `unappliable = bare_plan or jira_grade`
collapses "there is no sidecar to replay" (jira grade) with "some steps lack
detail files" (bare). The second reason does not apply to correctness gaps.
`prompts/apply-finding.md` edits the plan file "and/or the step's detail file
**if applicable**" and emits `BLOCKED` only when a finding genuinely needs a
missing detail file — so the apply path already handles a plan-body-only edit,
and the fence refuses it anyway. The operator is routed to a hand-fix for
findings the machinery would have applied.

**The BLOCKED renderer contradicts the apply prompt, and the defect is already
live.** When apply cannot proceed for want of a detail file, the prompt
instructs the model to say so and name `plan-tool detail`. The tool's own
rendering ignores that: `_blocked_next_step` frames *every* BLOCKED as "apply
can't add or restructure steps" and emits a `plan-tool split --step N` command
per flagged step. So a finding whose real remedy is "author the detail file"
prints as "split this step" — a structural remedy for a plan that simply has not
been detailed. `suggested_next_steps` appends that block whenever `applied`
carries a BLOCKED outcome, with **no bare gate**, and `--iterate` on a bare plan
already runs deterministic applies (only `DETAIL_LEVEL_FINDING_SOURCES` are
filtered out of `open_findings`), so a bare `--iterate` run can reach it at
HEAD. Opening the correctness route is **additional exposure, not the first
one**: it adds the conceptual applies to a path that already fires.

**A bare audit reports edge cases only `detail` can close.** `plan-audit.md`
lists **Missing edge-case concept** as a first-class completeness gap kind and
nothing narrows it for a step with no detail file, so a bare run reliably
returns gaps whose `→ fix:` is "specify the retry behavior" or "state what
happens on an empty batch". The operator's only way to close one is to write the
detail file the audit ran *before* — so the finding is not actionable where it
was raised, and opening an apply route makes that more visible, not
less: the route now names a verb for gaps the verb cannot resolve. This is why
decision 3 ships here rather than as its own effort.

## Architecture

Three decisions. Two of them are refusals with measurements behind them; those
live under `## Out of scope`.

**1. Split the fence by axis, at plan level.** On a bare plan,
conceptual-correctness gaps keep the `completeness-apply` route; conceptual-
completeness gaps stay unappliable. Jira grade keeps its current behavior for
its own, unrelated reason — it writes no sidecar, so nothing can replay there.
The split is by **axis**, never by per-finding detail coverage; see the refusal
below for why the finer version is not available.

**2. The BLOCKED remedy becomes coverage-aware — at plan level, for the same
reason.** When the plan is bare, the BLOCKED bullet leads with
`plan-tool detail <name>` and keeps the `split` command as the secondary
option; on a fully-detailed plan the bullet is unchanged. Deliberately *not*
keyed on whether the individual finding targets a bare step: that requires
resolving a finding to a step, which the data does not support.

**When `plan-tool detail` may be named on a bare plan.** The verb appears only
as the **unblock for a specific BLOCKED or withheld finding** — the BLOCKED
bullet's lead remedy (step 3) and the apply verb's withheld-gaps notice
(step 4). It is never named as a detail-coverage remedy or a blanket "author
details to unlock apply" instruction: the deterministic detail-level sources
(`DETAIL_LEVEL_DIAGNOSTIC_SOURCES`) stay filtered out of a bare plan's next
steps, and the grouped block (step 5) emits no `plan-tool detail` at all
because it names no per-finding blocker. Steps 3, 4, and 5 each cite this rule.
The distinction is what stops the plan re-creating the "you must detail before
you may apply" contract it exists to replace.

**3. Narrow the edge-case recast, and claim only what it is.** For a bare step,
a "missing edge-case concept" finding is admissible when its remedy is a step or
an acceptance criterion — a decomposition gap, which is what a bare-plan audit
should catch — and inadmissible when the remedy is "specify it in the detail",
which is the `detail` stage's job. This is a **small** delta: the shipped
conditioning block already says to judge bare steps "solely on the plan body's
concepts and the code at HEAD". Bare audits average **8.7** conceptual findings
per run against **5.1** for detailed audits (n=19 bare of 370 completeness
reports, measured 2026-08-03) — a real elevation, **not** saturation. Do not
restate it as saturation.

Decision 3 stays in this plan rather than being carved into its own effort
(decided 2026-08-03, user-confirmed; do not re-open). Its harm is stated in
`## Problem statement` and its scope is carried in the frontmatter `intent:` and
`## Overview`, so it is no longer an arm that appears only here. It is one
prompt-text step and it is about the same run as decisions 1 and 2: the route
those decisions open is worth less when the findings filling it can only be
closed by the stage that has not run.

**The binary observable, and nothing beyond it:** `is_bare`, already computed
deterministically per run. This effort routes on that existing fact. It asserts
no new measurement, judges no artifact's quality, and compares no two prose
artifacts.

## References

- `plan_tool/completeness_report.py` — owns the `bare_plan or jira_grade` apply
  fence (duplicated across the report and console next-step renderers) and
  `_blocked_next_step`; steps 1–3 land entirely here.
- `plan_tool/review.py` — `is_bare` / `audit_detail_bundle_status` compute the
  binary observable this effort routes on, and carry the bare-step conditioning
  block step 6 narrows.
- `plan_tool/prompts/apply-finding.md` — the apply contract that already edits
  the plan file "and/or the step's detail file **if applicable**" and reserves
  `BLOCKED` for a genuinely missing detail file; the evidence that a
  plan-body-only correctness edit needs no detail bundle.
- `plan_tool/prompts/plan-audit.md` — directs the auditor to anchor findings on
  the **concept**, not the step; the reason per-finding coverage routing is
  refused under `## Out of scope`.
- `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/completeness_phases.py` —
  the `completeness-apply` verb's own bare-plan gate (step 4, which lands first
  so the route is real before anything names it) and the grouped report's
  next-steps surface (step 5, the last surface to be brought into line).
- `plan_tool/fingerprint.py` — `compute_detail_bundle_fingerprint` persists the
  bare-state signal already, which is why a new detail-coverage field is refused.
- `CLAUDE.md` § "Correctness gates" — states the blanket "detail-level actions
  unlock only once a complete detail bundle exists" contract this plan replaces
  with an axis split; loaded into every later session, so step 7 must correct it.
- `docs/AUDIT_FLOW.md` — the audit flow's gate/sequence reference, which
  restates the same fence and is updated alongside CLAUDE.md.
- `BACKLOG.md` **#83** — proposes a harness asserting the bare-plan operator
  surface stays structural-only across every renderer; its premise narrows to the
  completeness axis once this plan ships.
- BACKLOG **#85** (read-only-audit split) — makes `completeness-apply` the sole
  mutator of conceptual gaps; it defines the route being opened here and is
  itself out of scope.
- `DATA_CONTRACT.md` — the drift-guarded saved-sidecar and `Recommendation`
  schema; the refusal above is a promise this effort leaves it unchanged.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

Three refusals, each with the evidence that produced it. Treat these as settled
(2026-08-03); a finding proposing one is invalid unless it brings new data.

- **Per-finding coverage routing — refused as unbuildable.** Only **6.0%** of
  conceptual findings resolve to a step (116 of 1,933 across the saved corpus;
  `plan-completeness` 4.5%, `plan-correctness` 8.1%). They carry `step_id=None`
  and a step is recoverable only from a `step<N>` anchor prefix, while
  `prompts/plan-audit.md` directs the auditor to anchor on the **concept**
  (`[cache-invalidation]`), not the step. A conservative fallback classifies 94%
  as ungrounded, so the "graded" fence collapses to the binary it was meant to
  replace while adding machinery that does nothing. Rule 5: a high false-positive
  rate means kill, not tune.
- **Excluding bare runs from the convergence spinning series — refused as
  unmotivated.** The premise was that bare conceptual findings cannot shrink
  because no apply route is offered. That is false: they are closed **by hand**,
  which is the documented Claude-session workflow. Measured on the two plans in
  this repo with the heaviest bare history — `plan-tool-annotate-feedback`
  (7 of 8 completeness runs fully bare) trends 15→14→11→9→9→5→5→5 and diagnoses
  `converging` with fork `none`; `parallel-plan-worktrees` (3 of 6 bare) also
  `converging`. The harm is undemonstrated and the best natural experiments
  available point the other way.
- **A new persisted detail-coverage field — refused as unnecessary.**
  `compute_detail_bundle_fingerprint` already records the state: a bare step
  "contributes none — its absence *is* the bare-state signal", so
  empty-and-`present` is an unambiguous fully-bare marker and all 370 reports
  were classified with zero schema change. A `(detailed, total)` pair would buy
  only the partial gradient, which the 6% measurement shows no consumer can use.

Also out: any new gate, blocking severity, or refusal-to-advance;
`convergence.is_blocking_impact` and the calibrated policy (CLAUDE.md
§ "Convergence policy boundary" scopes that separately); jira-grade fence,
sidecar, and next-step behavior; `#85`'s read-only-audit split; and anything
`detail` itself does. BACKLOG **#224** is a sibling with a live plan
(`docs/implementation-plans/2-audit-shape-registry.md`) — do not reach into it.

**No new exit code, with one scoped exception.** Opening the walk moves a bare
plan with a correctness gap and non-interactive stdin from rc 0 (today's
whole-walk skip) to rc 2 — the *existing* `isatty()` guard that a detailed plan
already hits. That is not a new code and not a new gate; it is the bare path
joining the detailed path's behavior at a guard that predates this plan. Step 4
documents it. Every other rc is unchanged: the bare withheld path stays 0, the
empty-sidecar path stays 0, and `--fail-on-findings` is untouched.

**Walk-time BLOCKED surfaces stay as they are.** Decision 2 covers the *audit's*
next-step renderers. A BLOCKED verdict returned during the walk step 4 opens
surfaces through `plan_tool/cli/review_actions.py` as
`apply-finding BLOCKED: <note>`, where the note comes from the apply prompt —
which already tells the model to name `plan-tool detail` for a missing detail
file. That is sufficient and it is out of scope here; step 3 is not widened to
reach it.

**No plan-body staleness warning for bare apply.** The apply walk's only
freshness gate is `_detail_bundle_staleness`, whose map is empty on a fully bare
plan, so a bare correctness apply against a plan body edited since the audit is
not warned about. This effort **accepts** that rather than building a
`SavedReview.plan_fingerprint` comparison — a new gate on a new lane, which the
refusal above forbids and which the detailed lane does not have either. Step 4's
`## Deferred` files it forward.

## Risks

- Opening the apply route raises BLOCKED volume on bare plans. If decision 2 is
  incomplete, the operator is pointed at `split` for a detailing problem — the
  defect this seed exists to prevent, which is why decision 2 is not optional and
  not deferrable.
- **A bare-plan apply could create the detail file it was supposed to work
  without.** `apply_finding` tracks a step's declared `detail:` path with no
  on-disk check, so a model that writes there produces a file the diff accepts;
  keeping it flips `is_bare` and routes around `detail`'s own contract. Only
  `apply-finding.md`'s rule 5 forbids creation today, and under `--jobs N -y`
  there is no operator to decline. Step 4 owns one post-apply cleanup in
  `apply_finding` that both the serial walk and `--jobs N` rely on (the parallel
  capture path does **not** ignore created detail files on its own), and the
  acceptance criteria pin the outcome.
- **A bare-plan correctness apply must not restructure via the split bridge.**
  `BLOCKED-STRUCTURAL` from a correctness gap still routes to `escalate_to_split`
  when `--apply-structural` is set, and `-y` bypasses the TTY confirm. Opening
  the correctness walk without withholding that bridge lets unattended apply
  mutate a plan that still has no detail bodies. Step 4 keeps the bridge
  recommend-only on bare plans — same fence as withholding saved
  `granularity-split`.
- Decision 3 is a prompt directive, so it is **delivered, not verified**; nothing
  machine-checks that the auditor honored it. That is the intended line. The
  acceptance criteria must not grow a conformance check for it — they assert only
  that the rule's text is present in a bare plan's rendered prompt and absent
  from a detailed one.
- **Six operator surfaces describe one run and must stay in step.** The report
  prose (`suggested_next_steps`), the console command block
  (`suggested_next_step_commands`), the grouped report's `### Suggested next
  steps` block, the apply verb's withheld-gaps notice, `console_summary`'s
  conceptual count lines on the `--iterate` path, and the `--iterate` halt
  stderr that names `completeness-apply` for deferred conceptual findings.
  Drift between any two of them is itself a reporting defect; steps 2, 4, and 5
  divide them and the Testing section covers all six.
- Bare apply has no plan-body staleness warning (see `## Out of scope`). An
  operator who edits the plan between the audit and the apply gets no signal, the
  same as on the detailed lane.

## Testing

What would prove the Outcome:

- A bare-plan audit names `completeness-apply` for its correctness gaps and does
  not name it for its completeness gaps — on **all six** surfaces the Risks
  section lists: the report prose, the console command block, the grouped
  report's next-steps block, the apply verb's withheld-gaps notice,
  `console_summary`'s conceptual lines, and the `--iterate` halt stderr.
- `plan-tool completeness-apply` on a bare plan really walks the
  `plan-correctness` gaps and reports every other saved source as withheld —
  naming the verb is not the same as the verb working.
- A BLOCKED finding on a bare plan leads with `plan-tool detail`; the same
  finding on a fully-detailed plan still leads with `plan-tool split`.
- A bare-plan apply run leaves no newly-created detail file behind, on the serial
  walk and under `--jobs N`.
- The rendered audit prompt carries the bare-step edge-case rule on a plan with
  at least one bare step and carries none of that text on a fully-detailed plan.
- A fully-detailed plan's next-steps output is unchanged, and a jira-grade
  audit's fence, sidecar, and next-step output are unchanged.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A bare plan's conceptual-correctness gaps have a named apply route; its
  conceptual-completeness gaps do not.
- `plan-tool completeness-apply` on a bare plan whose saved audit carries a
  `plan-correctness` finding walks that finding, and names every other saved
  source as withheld rather than dropping it.
- A bare-plan apply leaves no detail file on disk that was absent before it ran —
  on the serial walk and under `--jobs N`, including after any auto-fix follow-up
  the apply path may run.
- On a bare plan, a `BLOCKED-STRUCTURAL` verdict from a correctness gap stays
  recommend-only — it does not reach `escalate_to_split`, even under
  `--apply-structural -y`.
- Every bare-plan operator surface that names `completeness-apply` does so only
  for the correctness axis: report prose (`suggested_next_steps`), console
  command block, grouped next-steps block, apply withheld notice,
  `console_summary`, the `--iterate` halt stderr, and the `build_report_md`
  report-body intros (`CORRECTNESS_INTRO` and the bare conceptual-completeness
  withheld paragraph).
- Step 4's help-string edit lands with its three rebaselined artifacts committed:
  `docs/cli/completeness-apply.md`, `docs/cli/README.md`, and
  `tests/cli/package_surface_help.golden.txt`.
- No BLOCKED bullet recommends `split` as the lead remedy on a bare plan.
- The rule narrowing bare-step edge-case findings is present in the audit prompt
  rendered for a plan with at least one bare step, and absent from the prompt
  rendered for a fully-detailed plan.
- No repo document describes the bare-plan conceptual apply fence as one blanket
  rule.
- Fully-detailed plans behave exactly as before. At jira grade the apply fence,
  the sidecar, and every next-step surface are unchanged; the shared bare-step
  prompt text (decision 3) is the one thing that changes at both grades, by
  design.

## Deferred

- **Where out-of-scope discoveries go.** Things the code does wrong go to
  `BUG_BACKLOG.md`, forward-looking work to `BACKLOG.md`, per BACKLOG.md's
  decision rule. Anything touching audit-shape detection or `insufficient-history`
  routing is appended to **#224** rather than filed fresh.
- **`CORRECTNESS_INTRO`'s stale `reconcile-plan-walk` claim.** That intro names
  `plan-tool reconcile-plan-walk` as an alternative apply route for correctness
  gaps, but the generic walk cannot apply `plan-correctness`
  (`_APPLY_AS_FINDING_SOURCES` excludes it and `cmd_review_walk` passes no
  `extra_apply_sources`). It is a code defect independent of this plan's axis
  split and is filed in `BUG_BACKLOG.md`. Step 2 **may** axis-scope the intro's
  correctness/completeness joint-walk wording for bare plans; it must **not**
  change or remove the stale `reconcile-plan-walk` line — that fix belongs to
  the backlog entry.
- The three refusals above are deferred permanently, not pending — reopening one
  requires new measurement, not a new argument.
