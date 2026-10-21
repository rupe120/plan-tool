> **Replaced**: this file has been superseded by `docs/implementation-plans/2-completeness-next-steps-blocking-set.md`.
> Preserved here for history; do not edit.

# Plan seed: derive every completeness next step from the audit's one blocking set

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/completeness-next-steps-blocking-set.md
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per
step.

Source: BACKLOG #479 (unpromoted). This seed carries that entry's scope
contract.

## Outcome

After any `completeness-audit`, every message that tells the operator what to
close and whether to move on agrees with the audit's own blocking verdict. A
blocking gap is named everywhere and ends the command list with the re-audit to
run after the session-directed edit, with no stage transition offered. An
advisory gap is listed but holds back no stage. No surface says "no plan-level
gaps remain" while a blocking gap is open.

## In scope

- One blocking set, computed once where the finalize gate already computes it
  (`compute_conceptual_bar_blocking_ids` with the sampled `audit_stage`,
  surfaced as `outcome.conceptual_bar_blocking_ids`), and passed to every
  reader. It includes blocking deterministic findings no apply verb closes
  (self-consistency such as a missing `intent:`, purity coverage, data
  contract, lessons coverage, detail body).
- The four readers that decide today on their own:
  `completeness_report.suggested_next_steps` (saved report prose),
  `suggested_next_step_commands` (console list, whose empty result every
  caller turns into `next_stage_command`), `console_summary`, and
  `_render_grouped_report`'s next-steps block in
  `cli/completeness_phases.py`.
- The jira lane: name `completeness-audit <plan> --grade jira` (no
  `--iterate`) while a blocking gap is open, not "no gaps left — export".
- The `detail` / `split` / `merge` parents in `cli/authoring.py`, which
  append `reconcile-plan` and `run` after the tail's commands: no `run`
  while the tail names a re-audit.

## Out of scope / Non-goals

- Changing what blocks: the stage bar stays in `is_blocking_finding`, and the
  stage stays `derive_audit_stage`'s.
- An apply command for conceptual gaps (#367 stays: they close by a
  session-directed edit).
- A second blocking predicate anywhere. Deliberately not: the parked direct
  fix's fourth review round failed exactly there, deriving the stage from
  `bundle_status.is_bare` and disagreeing with `derive_audit_stage` on
  step-less and partially detailed plans.
- Relabeling the loop-stop `open_findings=` banner beyond saying it counts
  deterministic findings.

## Allowed behavior changes

- Console, report, and summary next-step wording for audits with an open
  blocking gap, or with only advisory gaps.
- The `detail` / `split` / `merge` merged next-steps block omits `run` while
  a blocking gap is open.

## Allowed reorganization

Moving the blocking computation so the readers receive it rather than
re-deriving it. No change to the finalize gate's contract (`--json`
`has_blocking_findings`, `--fail-on-findings`, exit codes).

## Verification

- One table-driven test over audit stage (step-less, bare, partially
  detailed, detailed) × grade (run, jira) × finding kind (blocking and
  advisory correctness, completeness, deterministic) asserts the four readers
  agree, and that a stage transition appears only when the blocking set is
  empty.
- The Integration case — bare plan, one open high correctness gap — prints the
  re-audit and no `detail` transition.
- An info/nit-only tail offers the next stage.
- Each assertion verified red by mutation.

## Stop / defer

Stop and surface to the user if a reader cannot receive the canonical set
without changing the finalize gate's contract. Do not add a second predicate
to work around it.

## Risks

- The canonical set is unavailable on a budget-limited or unqualified audit
  (`audit_incomplete`). The readers need a defined answer for that case, not a
  re-derived one.
- Four parked review rounds found a new reader or edge case each time; a reader
  missed by the plan reintroduces the original "no gaps remain" message.

## References

- `docs/how-to/pipeline/audit.md` — the qualified-result contract and the
  renderer-agreement paragraph this work makes true.
- Unmerged branch `fix/audit-next-steps-open-correctness` — the parked direct
  fix and its four review rounds; read for the case list, not as a base.
- Integration `.tmp/bitbucket-deployment-pipelines.audit.log` (2026-10-10) — the
  originating console output.

## Backlog reconciliation

When this plan ships, remove BACKLOG #479 and its roll-up line under
`gate-signal`. Authoring the plan alone marks #479 plan-authored; it does not
remove it.
