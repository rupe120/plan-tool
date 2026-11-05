# Completeness next-step verdict finish — review ledger and session handoff

| Field | Value |
| --- | --- |
| Change | BACKLOG #480: every untrusted completeness verdict names the gaps the audit established and prescribes the action that changes the result — `transient` / `persistent` / `stale-revision` cause values with a stated precedence, an incomplete audit keeping its blocking ids in the verdict, and the seven residual reader seams |
| Plan | `docs/implementation-plans/archive/2-completeness-next-step-verdict-finish.md` (plan PR #74); seed archived under `plan-seeds/archive/` |
| Branch | `feat/completeness-next-step-verdict-finish` |
| Review range | `e8ca455fc..HEAD` |
| Reviewer | `/code-review high` in-session (forked), report-only |
| Reader enumeration | `handoffs/2026-10-10-completeness-next-step-verdict-finish-reader-enumeration.md` (step 4's first deliverable) |

## Settled decisions (hand to the next reviewer)

- The finalize gate's external contract is unchanged: `--json` `has_blocking_findings`, `--fail-on-findings`, exit codes. The gate pair `_conceptual_bar_from_audit_recs` still returns `(), True` for an incomplete audit; only the verdict receives the stage bar's ids, computed separately.
- Three cause values only: `transient`, `persistent`, `stale-revision`. Precedence (first match wins): stale revision, incomplete / unqualified, non-empty blocking set (trusted), transient stop, hand-apply stop, `persistent` catch-all.
- A budget-limited audit that stopped on `max_iterations` is `persistent` (hand triage, ids named, no stage), not `transient`. **Decided in the plan's Architecture precedence rule (2); do not re-open.** The review's finding 5 disputes this and is declined for that reason.
- A `stale-revision` verdict's conceptual ids may describe other text: they are advisory and are not counted as gaps to close; deterministic blockers still close and still count. A synthetic deterministic-arm finding is a failing check, reported beside the gap count and never inside it.
- Legacy-unknown coverage (`QualifiedAuditResult.coverage == "unknown-legacy"`) on a current revision is `stale-revision`; budget-limited / unconfirmed coverage stays `persistent`.

## Execution record

- Bare-plan audit (Gate 1): three rounds, 0/5 detailed; 4 → 4 → 3 findings; rounds 2–3 were a self-seeded majority, so the loop stopped (exit 2).
- Detail-grounded audit (Gate 2): three rounds, 5/5 detailed; 5 → 6 → 0, ending `advisory-only` with coverage confirmed.
- `run --all --commit`: step 1 green under the tool; steps 2 and 3 hand-recovered (a test of the step's own asserted the wrong rc; two tests passed an incomplete `qualified_result` dict); steps 4–5 green under the tool.
- `reconcile-code --all`: 0 findings on steps 1–4 (step 5 is non-code).
- Hand-recovery incident: a `sed -i` status-note cleanup did not apply on macOS and left the plan frontmatter unparsable; the next `run` refused it before doing any work. Fixed with a checked Python edit (`29123a207`). BACKLOG #463 already covers marking a hand-fixed step done through the tool.
- Mutation note: restoring the removed fresh-audit splice did not turn any test red, because the splice was unreachable (the checkpoint site passes no verdict; an unqualified result with a gate verdict never takes that branch). The step-3 tests pin the surrounding behavior, not the removal.

## Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | Legacy or unobserved coverage on a current revision is `persistent`, not `stale-revision`; the how-to and the removed #480 entry both list "legacy coverage" | **Fixed.** `_verdict_untrusted_cause` takes `coverage_status`; `unknown-legacy` coverage is `stale-revision`; unconfirmed coverage pinned as `persistent` |
| 2 | A `stale-revision` verdict's re-audit reason and console line count ids as "N blocking gap(s)" while `next_step_gaps` demotes them | **Fixed.** `BlockingVerdict.blocking_count` excludes ids under `stale-revision`; the console names an incomplete verdict as such instead of "0 gap(s)" or "verdict unavailable"; the test that pinned "1 blocking gap(s) open" beside "has since changed" was rewritten |
| 3 | A `transient` / `persistent` tail verdict whose artifacts later changed keeps its original wording | **Deferred, filed as BACKLOG #481.** Valid but narrow: the verdict carries no bit that says its artifacts moved, and "not current" also arises from an unqualified headline, so an unconditional rewrite would print a false "text has since changed" |
| 4 | `bare_plan` label dropped for non-absent verdicts in `_fresh_completeness_audit_follow_up` | **Fixed.** The follow-up names `(bare-plan audit)` for every verdict state; pinned by a test |
| 5 | An incomplete audit stopped on `max_iterations` is `persistent`, though a re-audit would continue | **Declined.** Settled in the plan's precedence rule (2) and pinned by tests; see Settled decisions |
| 6 | The wiring test asserts literal substrings of `inspect.getsource(finalize_completeness_run)` | **Declined.** The existing test already used this form before the change (it pinned a different literal); the property is covered by behavioral tests. Replacing the style is its own change |
| 7 | Finalize recomputes the stage bar over `audit_recs` on an incomplete audit | **Declined.** The shape step 2's detail settled ("only the verdict's copy of the ids changes"); the cost is one pass on the incomplete path. A helper that returns both would change the gate pair's contract |

## Findings (round 2)

Round 2 found that the branch had closed fewer than the seven seams it claimed: step 4's enumeration marked the grouped report "already on the verdict" and `reconcile-code --all` reported 0 findings, but a probe render showed the auto-apply routing and the double re-audit still present. Four seams were reproduced open at HEAD before any fix.

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | Grouped report sends a blocking correctness gap on a detailed plan to the auto-apply / reconcile-walk bullet and names the re-audit twice | **Fixed.** A conceptual-correctness gap is no longer "structural" (no apply verb targets it, #85); the structural bullet does not repeat the re-audit command the closing line names. Pinned by `test_blocking_correctness_gap_on_a_detailed_plan_is_not_auto_apply` |
| 2 | #480 deleted while four seams were unshipped | **Resolved by fixing the seams** (findings 1, 3 and the two below); the entry stays removed |
| 3 | Console `blocking N` counts synthetic arms; `blocking_count` has two meanings | **Fixed.** `blocking_count` counts real gaps; failing checks are named separately (`BlockingVerdict.blocking_arm_count`, `SYNTHETIC_ARM_ID_PREFIX`); a lone arm never reads as a cleared set. Pinned by mutation |
| — | `_authoring_guidance` re-scans the bundle (seam) | **Fixed.** The audit hands its bundle status back through `_bundle_status_sink`; the stage row reads it |
| — | Finalize passes both raw arms and the collected tuple (seam) | **Fixed.** Finalize passes only the collected tuple |
| 4 | `no_progress` is classified `transient` | **Declined.** BACKLOG #480 and the plan name it as transient by decision |
| 5 | A not-current `set` verdict is called stale when the result was missing or capture failed | **Folded into BACKLOG #481** (same helper, same missing bit) |
| 6 | `not-sampled` reads "text has since changed" | **Fixed.** One neutral reason, "no current audit evidence for this text", for stale, legacy and never-sampled |
| 7 | Status strings re-declared in a second module | **Fixed.** The stale set derives from `review_persistence`'s status vocabulary minus `current` |
| 8 | `audit.md` `incomplete` row contradicts the stale-revision row | **Fixed** |
| 9 | Over-long `_verdict_untrusted_cause` docstring | **Fixed** (pointer to the how-to) |

Mutation record: restoring the removed fresh-audit splice did not turn a step-3 test red because that splice was unreachable; the synthetic-arm test goes red when the arm predicate is disabled.

Convergence note: round 2 found new unshipped work rather than a new class at the same seam; only findings 4 to 7 were design disputes about this branch's own choices. One more review round was agreed; if it finds anything beyond nits, stop and file it rather than run a fourth.

## Findings (round 3 — the last agreed round)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | `halted: …` stops read as `transient` | **Fixed.** Confirmed by calling the classifier. A halt is `persistent` (`HALTED_STOP_PREFIX`); cut-short budget stops (`time_budget_exceeded`, `marginal`, plan-quota) stay `transient` because a trusted cause on an unclean stop would offer a stage the finalize gate refuses. Pinned by `test_halted_stop_is_persistent_not_a_retry` |
| 2 | A synthetic arm is identified by an id prefix | **Fixed.** Marked by type (`DeterministicArmFinding`); a look-alike id stays a counted gap, asserted |
| 3 | The gate function's arm parameters became optional | **Fixed.** Omitting them is a `TypeError`, never "nothing blocks" |
| 4 | A rewritten not-current tail verdict keeps deterministic blockers computed on changed text | **Folded into BACKLOG #481** |
| 5 | Advisory line says "outside the blocking set" for stale-demoted ids | **Fixed.** Reads "not verified against the current text" (`NextStepGaps.demoted_stale`) |
| 6 | A private constant imported under an alias | **Fixed.** Public `STALE_REVISION_STATUSES` beside the vocabulary |
| 7 | The console prints enum names | **Fixed.** Plain reasons; a test asserts the enum names stay out |

Closure: three review rounds were run as agreed. Round 3 found one regression introduced by this branch (finding 1) and otherwise wording and structural-marking nits. Nothing was left unresolved except #481, which now carries findings 3 (round 1), 5 (round 2) and 4 (round 3) of the same helper.

## Findings (delta review of the round-3 fix commit)

A delta-only `/code-review high` of `82126b9f2` ran before the push, to honor the rule that every code change is reviewed.

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | Drift halts are not reproduced by a re-audit; classing all halts `persistent` was wrong | **Fixed, and the round-3 premise was wrong.** Verified: each run takes a fresh drift baseline (`iteration_session`). Drift halts are `transient`; parse, reverted-edit and unmatched-fence halts are `persistent`. Pinned by `test_halt_cause_follows_whether_a_reaudit_reproduces_it`, which goes red under mutation |
| 5 | Halt detection parsed the free-text stop reason | **Fixed.** The cause reads the outcome's `halt_reason`; drift reasons are the named `HALT_DRIFT_REASONS` |
| 2 | The omitted-arm guard covered 6 of 9 arms | **Fixed.** All nine raw arms. Six callers in two test files that relied on silent defaults now pass the arms explicitly (the first sweep covered one file; the second covered the tree) |
| 3 | No tests for the guard or the stale-demotion wording | **Fixed.** The guard test first passed for the wrong reason (a different `TypeError` from iterating the sentinel); it now matches the guard's message and goes red when the guard is disabled |
| 4 | `audit.md` did not describe the halt classification | **Fixed** |
| 6 | Dead import, orphaned comment | **Fixed** |
| 7 | Duplicated phrases, string-literal keys | **Partly fixed.** Phrase table keyed by the `UNTRUSTED_*` constants; the two advisory-scope literals stay duplicated (wording only) |
| 8 | Stale wording keyed on whether ids survived | **Fixed.** Keyed on the cause alone |

Process note: the two `# sweep` misses in this review loop (a one-file caller sweep, then a one-tree sweep) are the same defect class the repo's class-sweep rule names; enumerate callers across `tests/` before the first edit.

## Session handoff (2026-10-10)

Next, in order:

1. Push and open the PR for this branch (the owner approves the push). Three review rounds ran; the agreed stopping point is reached.
2. **#481** (route: direct) — the narrow stale-tail wording gap.
3. **Ready bugs from the earlier handoff:** `--refresh-seeds` / `--accept-seed` overwrite an unpublished seed's file (RISK); roadmap-derived plans cite stale `0N-*.md` copies; multi-line report bullets break the list; #474 (budget-limited audit's next step).

Process notes:

- Every code change gets `/code-review high` before push; this ledger is the single review doc for the branch — update it in place for later rounds.
- A claim that something is fixed is checked against the code before it is reported.
- Do not edit a plan's YAML with `sed -i` on macOS; use a checked scripted edit and validate the frontmatter before the next `run`.
