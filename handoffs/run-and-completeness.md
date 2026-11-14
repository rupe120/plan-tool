# Run and completeness

`run` gates and receipts, completeness next steps and verdicts, loop behavior, hints and maintenance fixes. Each section below is one change or route in this workstream, ordered by the date it was opened; new work in the workstream appends a section here instead of creating a file (`README.md` § "Naming").

| Section | Opened |
| --- | --- |
| [Completeness next-step verdict finish — review ledger and session handoff](#completeness-next-step-verdict-finish--review-ledger-and-session-handoff) | 2026-10-10 |
| [Completeness next steps from one blocking verdict — review ledger and session handoff](#completeness-next-steps-from-one-blocking-verdict--review-ledger-and-session-handoff) | 2026-10-10 |
| [`run` no-edits-applied block and failure receipts — review ledger](#run-no-edits-applied-block-and-failure-receipts--review-ledger) | 2026-10-13 |
| [Completeness apply retirement implementation](#completeness-apply-retirement-implementation) | 2026-11-04 |

## Completeness next-step verdict finish — review ledger and session handoff

*Opened 2026-10-10.*

| Field | Value |
| --- | --- |
| Change | BACKLOG #480: every untrusted completeness verdict names the gaps the audit established and prescribes the action that changes the result — `transient` / `persistent` / `stale-revision` cause values with a stated precedence, an incomplete audit keeping its blocking ids in the verdict, and the seven residual reader seams |
| Plan | `docs/implementation-plans/archive/2-completeness-next-step-verdict-finish.md` (plan PR #74); seed archived under `plan-seeds/archive/` |
| Branch | `feat/completeness-next-step-verdict-finish` |
| Review range | `e8ca455fc..HEAD` |
| Reviewer | `/code-review high` in-session (forked), report-only |

### Settled decisions (hand to the next reviewer)

- The finalize gate's external contract is unchanged: `--json` `has_blocking_findings`, `--fail-on-findings`, exit codes. The gate pair `_conceptual_bar_from_audit_recs` still returns `(), True` for an incomplete audit; only the verdict receives the stage bar's ids, computed separately.
- Three cause values only: `transient`, `persistent`, `stale-revision`. Precedence (first match wins): stale revision, incomplete / unqualified, non-empty blocking set (trusted), transient stop, hand-apply stop, `persistent` catch-all.
- A budget-limited audit that stopped on `max_iterations` is `persistent` (hand triage, ids named, no stage), not `transient`. **Decided in the plan's Architecture precedence rule (2); do not re-open.** The review's finding 5 disputes this and is declined for that reason.
- A `stale-revision` verdict's conceptual ids may describe other text: they are advisory and are not counted as gaps to close; deterministic blockers still close and still count. A synthetic deterministic-arm finding is a failing check, reported beside the gap count and never inside it.
- Legacy-unknown coverage (`QualifiedAuditResult.coverage == "unknown-legacy"`) on a current revision is `stale-revision`; budget-limited / unconfirmed coverage stays `persistent`.

### Execution record

- Bare-plan audit (Gate 1): three rounds, 0/5 detailed; 4 → 4 → 3 findings; rounds 2–3 were a self-seeded majority, so the loop stopped (exit 2).
- Detail-grounded audit (Gate 2): three rounds, 5/5 detailed; 5 → 6 → 0, ending `advisory-only` with coverage confirmed.
- `run --all --commit`: step 1 green under the tool; steps 2 and 3 hand-recovered (a test of the step's own asserted the wrong rc; two tests passed an incomplete `qualified_result` dict); steps 4–5 green under the tool.
- `reconcile-code --all`: 0 findings on steps 1–4 (step 5 is non-code).
- Hand-recovery incident: a `sed -i` status-note cleanup did not apply on macOS and left the plan frontmatter unparsable; the next `run` refused it before doing any work. Fixed with a checked Python edit (`29123a207`). BACKLOG #463 already covers marking a hand-fixed step done through the tool.
- Mutation note: restoring the removed fresh-audit splice did not turn any test red, because the splice was unreachable (the checkpoint site passes no verdict; an unqualified result with a gate verdict never takes that branch). The step-3 tests pin the surrounding behavior, not the removal.

### Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | Legacy or unobserved coverage on a current revision is `persistent`, not `stale-revision`; the how-to and the removed #480 entry both list "legacy coverage" | **Fixed.** `_verdict_untrusted_cause` takes `coverage_status`; `unknown-legacy` coverage is `stale-revision`; unconfirmed coverage pinned as `persistent` |
| 2 | A `stale-revision` verdict's re-audit reason and console line count ids as "N blocking gap(s)" while `next_step_gaps` demotes them | **Fixed.** `BlockingVerdict.blocking_count` excludes ids under `stale-revision`; the console names an incomplete verdict as such instead of "0 gap(s)" or "verdict unavailable"; the test that pinned "1 blocking gap(s) open" beside "has since changed" was rewritten |
| 3 | A `transient` / `persistent` tail verdict whose artifacts later changed keeps its original wording | **Deferred, filed as BACKLOG #481.** Valid but narrow: the verdict carries no bit that says its artifacts moved, and "not current" also arises from an unqualified headline, so an unconditional rewrite would print a false "text has since changed" |
| 4 | `bare_plan` label dropped for non-absent verdicts in `_fresh_completeness_audit_follow_up` | **Fixed.** The follow-up names `(bare-plan audit)` for every verdict state; pinned by a test |
| 5 | An incomplete audit stopped on `max_iterations` is `persistent`, though a re-audit would continue | **Declined.** Settled in the plan's precedence rule (2) and pinned by tests; see Settled decisions |
| 6 | The wiring test asserts literal substrings of `inspect.getsource(finalize_completeness_run)` | **Declined.** The existing test already used this form before the change (it pinned a different literal); the property is covered by behavioral tests. Replacing the style is its own change |
| 7 | Finalize recomputes the stage bar over `audit_recs` on an incomplete audit | **Declined.** The shape step 2's detail settled ("only the verdict's copy of the ids changes"); the cost is one pass on the incomplete path. A helper that returns both would change the gate pair's contract |

### Findings (round 2)

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

### Findings (round 3 — the last agreed round)

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

### Findings (delta review of the round-3 fix commit)

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

### Session handoff (2026-10-10)

Next, in order:

1. Push and open the PR for this branch (the owner approves the push). Three review rounds ran; the agreed stopping point is reached.
2. **#481** (route: direct) — the narrow stale-tail wording gap.
3. **Ready bugs from the earlier handoff:** `--refresh-seeds` / `--accept-seed` overwrite an unpublished seed's file (RISK); roadmap-derived plans cite stale `0N-*.md` copies; multi-line report bullets break the list; #474 (budget-limited audit's next step).

Process notes:

- Every code change gets `/code-review high` before push; this ledger is the single review doc for the branch — update it in place for later rounds.
- A claim that something is fixed is checked against the code before it is reported.
- Do not edit a plan's YAML with `sed -i` on macOS; use a checked scripted edit and validate the frontmatter before the next `run`.

## Completeness next steps from one blocking verdict — review ledger and session handoff

*Opened 2026-10-10.*

| Field | Value |
| --- | --- |
| Change | BACKLOG #479: every completeness next-step reader (report prose, console list and summary, grouped report) and the `detail` / `split` / `merge` parents derive what to close and the one next command from the finalize gate's blocking verdict, so no surface says "no plan-level gaps remain" or offers a stage while a gate-blocking gap is open |
| Plan | `docs/implementation-plans/archive/2-completeness-next-steps-blocking-set.md` (plan PR #70); seed archived under `plan-seeds/archive/` |
| Branch | `feat/completeness-next-steps-blocking-set`, merged as PR #71 (`1d6476e1a`) |
| Review range | `97ce3a261..23743e90e` |
| Checks run | Full suite `uv run pytest tests/ -q -n auto` after every fix batch; last: 14,330 passed, 67 skipped (`c1680dcde`); `reconcile-code --all`: 0 findings on steps 1–4 |
| Reviewer | `/code-review high` in-session (forked), report-only, four passes |
| Disposition | pass 1: 10 fixed; pass 2: 10 fixed by the centralization (`14499ac46`); pass 3: 3 design gaps fixed by amendment (`a9be29987`, `c1680dcde`) + 7 fixed; pass 4: 10 tracked as BACKLOG #480. Closed **non-converging by agreement**: each pass found a new class at the reader/verdict seam, so pass 4 was filed instead of a fifth pass |

### Settled decisions (hand to the #480 reviewer)

- The finalize gate's external contract is unchanged: `--json` `has_blocking_findings`, `--fail-on-findings`, exit codes. The gate's deterministic arms are collected once (`_blocking_deterministic_findings`) and read by both the gate's bool and the verdict.
- `BlockingVerdict` has three states (`set`, `incomplete`, `absent`). Only a completed empty `set` offers a stage. `incomplete` keeps every blocking id the audit established (amended 2026-10-10 after pass 3; before that it closed nothing by id and hid HIGH gaps as advisory). `absent` is the default for a caller that passes no verdict.
- Trust follows the gate (amended after pass 3): a non-empty set names its gaps whatever the stop, hand-apply included; an empty set offers a stage only when finalize is clean. `awaiting-human-action` with an empty set is untrusted (`persistent`) — accepted by the session as amendment 3's intent; a one-line change if the narrower reading is wanted.
- A `persistent` untrusted cause prescribes hand triage of the saved report, edit, commit, then re-audit the changed snapshot; a `transient` cause keeps the plain `--iterate` re-audit. (Pass 4 found `transient` unreachable — see #480.)
- Two shared functions decide everything: `next_step_gaps` (close vs advisory, from the verdict alone) and `next_stage_command` (the one next command; re-audit carries `--grade jira` at jira grade, `--iterate` at run grade). Readers and parents only format their output.
- The `detail` / `split` / `merge` parents offer a stage only for a completed empty set whose tail result still matches the current files; a bare bundle names `detail`.
- The absent default landed in two phases (step 1 kept legacy output for an unset verdict; step 2 flipped it once callers were wired) so each `run` step stayed green under the full-suite gate (resequenced `bce3a1319` after the first run failed six step-2 tests).

### Execution record

- Bare-plan audit (Gate 1): four rounds, 0/5 detailed, coverage confirmed each round, completeness apply withheld; 5 → 6 → 3 → 3 unique findings. Round 3 caught a false seed claim (the conceptual blocking ids include no deterministic findings); round 4 described only prior edits.
- Detail-grounded audit (Gate 2): three rounds, 5/5 detailed; round 1 `no-qualified-current-evidence`, rounds 2–3 confirmed; 4 → 3 → 2; last round applied without re-audit (low-yield).
- `run --all --commit`: steps 1, 3, 5 green under the tool. Step 2 hand-recovered per `DIRECTIVES.md`: 5 failures from a step-1 defect (`suggested_next_steps`' own fallback called `next_stage_command` without the verdict) plus a stray `# ` description prefix; fixed in `843f441d0`, suite green, status flipped in `8fadcca88`. Step 4 hand-recovered: one table row asserted the word "No gaps" absent while the correct absent-verdict text contains it; assertion narrowed to keys in `f151e42e8`, status flipped in `3b63f8069`.
- `reconcile-code` missed the jira-grade re-audit lacking `--grade jira`; fixed by hand in `50e08225d` (47 sibling tests pinned the grade-less form and were moved to prefix checks; the exact form is pinned once).

### Findings (one line each)

Pass 1:
- Readers disagree on an advisory-only clear verdict — fixed `da40b889b`
- Console summary counts advisory correctness as "fix these first" — fixed `da40b889b`
- Parents offer `run` next to an unqualified tail — fixed `0dfab4669` (verdict untrusted on unqualified result)
- Unqualified early return drops the jira grade — fixed `da40b889b`
- Incomplete deterministic blockers unreachable behind the unqualified return — fixed `da40b889b`
- Verdict ignores the stop reason — fixed `0dfab4669`
- Duplicate re-audit rows — fixed `14499ac46`
- Two "Close N" counts in prose — fixed `da40b889b`
- Deterministic collection computed twice — fixed `0dfab4669`
- Grouped report duck-types the verdict — fixed `da40b889b`

Pass 2 (all fixed by centralizing in `14499ac46`): stale-tail parents offer `run`; `awaiting-human-action` reads clear; disagreeing re-audit rows; console omits the stage beside another row; run-grade re-audit lacks `--iterate`; parents hard-code `run`/`jira`; double "Close N" counts; "close … re-audit" next to "advisory"; incomplete with nothing listed says "close"; wrapper and repeated imports.

Pass 3:
- Incomplete verdict hides HIGH gaps as advisory — fixed `c1680dcde` (design amendment 1)
- Hand-apply exemption offers a stage on an empty recomputed set — fixed `c1680dcde` (amendment 2)
- Persistent untrusted cause loops on re-audit — fixed `c1680dcde` (amendment 3)
- "Advisory" wording after required steps; deterministic blockers listed twice; jira double bullet; authoring re-audit lacks `--iterate`; contradictory bare-plan "informational" wording; after-the-fact re-audit dedupe; parents re-hash the bundle — fixed `c1680dcde`

Pass 4 (all `tracked #480`):
- `transient` cause unreachable: the classifier marks every cut-short stop `awaiting-human-action`
- Budget-limited audit carries no ids (`_conceptual_bar_from_audit_recs` returns `()` when incomplete), so HIGH gaps read advisory
- Stale-revision `no-qualified-current-evidence` labelled persistent ("unchanged text reproduces this")
- Grouped report routes blocking correctness on a detailed plan to the auto-apply bullet
- Prose can name the re-audit twice
- `docs/how-to/pipeline/audit.md` cites the deleted `_actionable_conceptual_gaps`
- `_authoring_guidance` re-derives the stage from a second bundle scan
- Console `blocking N` counts synthetic arms; says "verdict unavailable" for `incomplete`
- Dead deterministic splice in the fresh-audit early return
- Finalize passes both the raw arms and the collected tuple

### Session handoff (2026-10-10)

Shipped this session besides #479:

| PR | What |
| --- | --- |
| #61 | Filed #473 and two Integration seed bugs |
| #62 | Landed prompt-budget review passes 5–7 that #60 missed; corrected #472; removed #470 |
| #63, #65 | Filed and fixed the test git-environment leak (conftest scrub at import) |
| #64 | Filed Integration audit gaps (#474, four bugs) and tracking gaps (#475–#478) |
| #66 | Roadmap seeds require a sourced `## Risks`; refusal names its remedy |
| #67 | `roadmap --apply` skips published seeds; stale published drafts warn |
| #68 | Post-merge review fixes for #65 and #66 |
| #69 | Parked the direct "no plan-level gaps" fix; filed #479 and its seed |
| #72 | TRACKING.md recipe runs the bare-plan audit before `detail` (#475) |

Next, in order:

1. **#480** (route: plan) — the pass-4 model gaps upstream of the readers.
2. **Ready bugs:** `--refresh-seeds` / `--accept-seed` overwrite an unpublished seed's file (RISK); roadmap-derived plans cite stale `0N-*.md` copies; multi-line report bullets break the list; #474 (budget-limited audit's next step).

Decisions waiting on the owner:

- Whether roadmap seed drafts must carry `## Risks` — **decided 2026-10-10: they must.** The gate (`missing-draft-seed-risks`, presence only) shipped with `fix/roadmap-seed-risks-required`; the `BUG_BACKLOG.md` entry is removed. Existing drafts without `Risks` classify `malformed` until refreshed or hand-edited and accepted.
- #473: the endorsed way to watch a run another session launched.
- Whether TRACKING.md phase 2's "skip the detail-grounded audit when the source was already canonical" clause still stands.
- Whether to delete the parked remote branch `fix/audit-next-steps-open-correctness` (superseded by #71).

Process notes for the next session:

- Every code change gets `/code-review high` before push (three code PRs went out unreviewed until the owner flagged it; #68 reviewed #65 and #66 after merge).
- Long commands run in the background; full-suite runs were twice started in the foreground this session.
- A claim that something is fixed is checked against the code before it is reported (a pass-1 "dedupe landed" claim was false).

## `run` no-edits-applied block and failure receipts — review ledger

*Opened 2026-10-13.*

| Field | Value |
| --- | --- |
| Change | A mutating `run` step whose declared files all stayed unchanged is not advanced and reports "no edits applied"; every failed mutating step stores its final reply in a sidecar and logs a `model_failure_receipt` |
| Branch | `feat/456-no-edits-applied` |
| Reviewer | `/code-review high`, headless, report-only |

### Settled decisions

- The block applies whether or not test enforcement is on (owner decision, 2026-10-13).
- A step that declares no files is exempt: with no declared set there is nothing to compare.
- The run log carries no reply text; the reply lives in the sidecar and the receipt carries its digest and path.

### Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | The "no edits applied" message advertises `--accept`, which refuses when the plan has no `test_command` and the step has no `gate`; a docs-only step with no gate has no way forward (medium, CONFIRMED) | **Fixed.** The failure names `--accept` only when a `test_command` or `gate` exists; otherwise it says what closes the step. Mirrored in run.md and RUNBOOK; mutation-checked | |
| 2 | A non-file `files:` entry stamps as `(mtime, size, None)`, so work inside it reads as "no edits applied", now a hard failure (low, PLAUSIBLE) | **Fixed, fail-open.** `PLAN_FORMAT.md` defines `files:` as existing files, but the parser does not enforce it; an entry with no content digest now counts as modified; mutation-checked |
| 3 | The sidecar identity hard-codes `attempt1`, so a second failure of one step under one logger would overwrite the first sidecar (low, PLAUSIBLE) | **Fixed.** The identity carries `time.time_ns()`. Not reachable today (`run --all` halts on the first failure), so this is cheap hardening, not a live defect; mutation-checked |
| 4 | Only the `no-edits-applied` receipt is tested; the other four reasons `DATA_CONTRACT.md` lists have no test (low, CONFIRMED) | **Fixed.** One parametrized test over `invoke`, `test-authoring-gate`, `test-gate`, `gate`; each emit site mutation-checked |

Checked, no finding: block ordering, plan write-back, content-hash comparison, receipt contents.

### Findings (round 2)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | The comparison included mtime, so an identical-bytes rewrite read as modified and the step advanced; the "content-compared" docs overstated it (medium, CONFIRMED) | **Fixed.** Size and digest decide; mtime is ignored. Mutation-checked |
| 2 | A path missing before and after counts as unchanged, so a step whose entries never resolve (a glob) is blocked (medium, PLAUSIBLE) | **Declined, carve-out asserted.** A `creates:` path nothing wrote is the exact case this change exists to catch; the block needs *every* declared entry unchanged, so a step with any real edit advances. `PLAN_FORMAT.md` defines `files:` as existing files, not globs. A test pins it; mutation-checked |
| 3 | `GATES.md`, `run.md` (advisory list) and `common-workflows.md` still called the check a warning (low, CONFIRMED) | **Fixed.** All three swept |
| 4 | The IPPT-16 seed and `BUG_BACKLOG.md` stub still scope the gate to `non-code` steps only (low, PLAUSIBLE) | **Fixed by owner decision, 2026-10-13.** This change ships the gate for every step type, which the IPPT-16 seed listed as out of scope. The seed is deleted (git keeps it), the `BUG_BACKLOG.md` promotion stub is removed, and the arc ledger row is marked superseded. The Jira ticket itself is the owner's to close or re-scope |
| 5 | `DATA_CONTRACT.md` said "every failed mutating step" but exception and no-logger paths emit nothing (low, PLAUSIBLE) | **Fixed.** The contract names the covered paths and the uncovered ones |
| 6 | `_record_step_failure_receipt` repeats the sidecar-then-receipt sequence in `roadmap.py` (low, CONFIRMED) | **Declined.** Not an exact duplicate (`tests/test_duplication.py` is green); the shared helper lives in `roadmap.py`, above `launcher.py` in the layering, so calling it would add an upward edge. A consolidation would be its own change with an AST-checked entry |
| 7 | `read_bytes()` loaded each declared file twice per step (low, PLAUSIBLE) | **Fixed.** Chunked `hashlib.file_digest`, and no second hash when the size already differs |

### Findings (round 3)

Zero findings. Checked and clean: every `_files_unchanged_since` branch, non-mutating modes unreachable by the block, write-back contract, receipt emission on a failed sidecar write, empty reply, invoke-failure reply source.

| # | Observation (below threshold) | Disposition |
| --- | --- | --- |
| 1 | A re-run after a failed gate, where the files already hold the fix, is blocked as "no edits applied" | **Documented, not reversed.** The block applies to every step (owner decision, 2026-10-13); the failure names `--accept` as the route, and RUNBOOK says so |
| 2 | A named pipe declared as a file would block on open for hashing | **Not reachable.** `PLAN_FORMAT.md` defines `files:` as existing regular files |

### Findings (round 4, tests-and-docs lens)

No code-level defect in `launcher.py`. Ten tests-and-docs findings, all applied after sweeping the class by vocabulary (the warning wording, the roadmap-only receipt description, the shipped item's identifiers) rather than only the cited lines.

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | `README.md` still said a no-files-modified step only warns (medium, CONFIRMED) | **Fixed.** Rewritten to match `GATES.md` |
| 2 | The no-edits hint omitted that `--accept` needs the hand fix committed first (medium, CONFIRMED) | **Fixed.** Message, `run.md`, and RUNBOOK say commit first |
| 3 | RUNBOOK sent the operator to update `files:`, which re-trips the same block, and named the wrong gate (medium, PLAUSIBLE) | **Fixed.** Says a re-run that edits nothing is blocked again, then commit and `--accept` |
| 4 | `run.md`'s accept section blamed the test-authoring gate for the re-run block (low, CONFIRMED) | **Fixed.** Names the no-edits block first |
| 5 | `README.md` and `OPERATIONS.md` called `model_failure_receipt` roadmap-only (medium, CONFIRMED) | **Fixed.** Both list the `run` reasons and sidecar location |
| 6 | Post-flight tests asserted the absence of a string no code emits; no test distinguished `final_text` from the raw stream (medium, PLAUSIBLE) | **Fixed.** Positive assertions on exit and `done`; a new test pins `final_text`; mutation-checked |
| 7 | The run-gates arc and the Integration arc still listed #456 as pending (low, CONFIRMED) | **Fixed.** Arc header, details, and ordering updated; the Integration row points at the shipped outcome |
| 8 | The sidecar directory was keyed by file stem while the contract said slug (low, PLAUSIBLE) | **Fixed.** Keyed by the run log's own slug, as documented |
| 9 | The unfiltered-reply caveat disappeared with the deleted entry (medium, PLAUSIBLE) | **Fixed.** Carried into `DATA_CONTRACT.md` |
| 10 | `_FileStamp` carried an mtime nothing read (low, cleanup) | **Fixed.** Stamp is `(size, sha256)` |

### Findings (round 5)

Zero correctness findings in `launcher.py`. The round 4 fixes were re-verified by grep (no remaining statement that the check warns, no roadmap-only receipt description, no pending reference to the shipped item or the retired seed, and the `--accept` claims match the code). Three low docs findings:

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | `RUNBOOK.md:812` and `:950` link to `docs/RUN_FLOW.md`, which does not exist (low, CONFIRMED) | **Declined, out of scope.** The dangling link predates this branch; the repoint to `docs/how-to/pipeline/run.md` is unrelated to the change. Left for a separate docs fix |
| 2 | #87's open question still read as if a no-edit retry reaches the test-authoring gate (low, PLAUSIBLE) | **Fixed.** A dated line narrows the question to steps that declare no files |
| 3 | The `producer_slug` collision entry omitted the new `_run/<slug>` producer (low, PLAUSIBLE) | **Fixed.** `launcher.py:_record_step_failure_receipt` added to the entry's Files list |

### Findings (round 6)

Zero findings. Interactions checked clean: `--all` sweeps and halts, single-step `--commit` (gated on `done`), plan status and `status_note` write-back, `--accept` against the note the block writes, every non-`run` caller of `run_step`, `bench.py`'s caller (a no-edit run now reads as a failure, the correct direction), the lessons log, receipt emission once per failure.

| # | Observation (below threshold) | Disposition |
| --- | --- | --- |
| 1 | A sweep halt's lesson text reads "run failed (exit code 1)", as for every gate refusal | **Not changed.** Matches the sibling gates; the specific reason is in the `status_note` and receipt |
| 2 | An untracked sidecar could make `--accept` refuse a dirty tree in a repo that does not ignore `.plan-tool/parse-failures/` | **Not a new defect.** The path is in this repo's `.gitignore` and the README's documented ignore list, and `detail` already writes there |

### Convergence status

**Converged after 6 rounds** under the project's low-yield rule: round 5 added only low findings (two applied, one declined as pre-existing) and round 6 was clean. Rounds 1, 2 and 4 carried the material findings (a message advertising an unusable route, an mtime comparison that missed identical rewrites, stale wording across eleven docs, a missing pin on `final_text`); every one is fixed and mutation-checked. Round 3 was clean in between.

Open outside this change: the IPPT-16 Jira ticket still describes work that has shipped; `RUNBOOK.md` links to a `docs/RUN_FLOW.md` that no longer exists.

## Completeness apply retirement implementation

*Opened 2026-11-04.*

All six steps are shipped on `origin/main` at `cf303fe29`. Plan PR #162,
implementation PR #163, and plan-status PR #164 are verified merged on
2026-11-04; the code and plan snapshots match their fetched remote paths.
This closed review ledger retains implementation and validation provenance.
Independent completed fixes retain their dispositions in the
maintenance review ledger (retired 2026-11-13; its tracked items live in `BUG_BACKLOG.md`);
remaining work belongs to `BACKLOG.md` and `BUG_BACKLOG.md`.

### Delivered scope

The CLI rejects `completeness-apply`, `direct-run`, and `direct-jira`. Their
exclusive handlers, serial/parallel apply machinery, direct pipelines, generated
references, help, and capability entries are removed. Live guidance directs
conceptual findings to judged edits. Create/detail deterministic repair,
generic review/reconcile authority, benchmark fixtures, persisted schemas,
legacy readers, blocking policy, and exit codes retain their contracts.

BACKLOG #376 and removed-command-only requests are removed; mixed requests keep
surviving work. #519 owns the unreachable structural opt-in disposition; #520
owns stale lesson maintenance. A machine comparison with `origin/main` confirms
the complete #369 block is byte-for-byte unchanged. The changelog fragment
`changelog.d/completeness-apply-retirement.md` marks the CLI removal as breaking
and gives the replacement workflow.

### Pre-execution audit provenance

Historical evidence, 2026-11-04. The archived bundle is
`docs/implementation-plans/archive/plan-details/completeness-apply-retirement/`.
`reconcile-plan --all --no-walk -y` saved `reports/20261104-130427.json`; its
semantic review found obsolete step-5 paths, wrong #367 ownership, and removed
Jira-grade wording. Its already-built suggestions were token matches
contradicted by that review, so no step status changes follow. The correction
also aligned seed, backlog, and documentation paths and added Cursor guidance
and the glossary. The bounded correction keeps retirement from widening into
unrelated application authority: generic application and deterministic repair
authority stay, and #369's scope stays independent. The seed remains archived
and inert, not a competing scope owner.

Both audit gates use `completeness-audit completeness-apply-retirement
--iterate --commit --audit-passes 1 -y` with backend Codex, model `gpt-6.1-sol`,
and closed stdin.

- Bare report `reports/20261104-130709-completeness.md`: 0/6 details, zero
  conceptual findings, confirmed coverage, current revision, fresh conceptual
  call. The sole heuristic `plan-claim-vs-delivery-caca4275` names deliberately
  preserved `apply_finding` and does not justify plan expansion.
- One-shot `detail --commit -y` authored all six details; its tail saved
  `reports/20261104-132734-completeness.md` with zero findings.
- Detail-grounded gate (adds `--reuse-audit`) saved
  `reports/20261104-140106-completeness.md`: 6/6 details, zero open findings,
  confirmed coverage, current revision, explicit conceptual-call reuse,
  advisory-only. No conceptual correction loop ran, so no three-snapshot
  trajectory applies.

These records certify the authored bundle, not implementation delivery. Do not
rerun pre-execution plan-mutating audits on executed work.

### Execution and recovery

Commands use `uv run plan-tool --backend codex --model gpt-6.1-sol` with closed
stdin and `-y`. `run completeness-apply-retirement --all --commit` advanced
steps 1 and 2 through green full-suite gates, then stopped step 3 at its test
gate. The implementation subprocess committed at `b25c6f5dc`; eight tests in
`tests/test_review_walk.py::TestCliCompletenessApplySubcommand` still invoked the
removed command or monkeypatched its deleted walk seam (focused reproduction
confirmed all eight). The class and its two exclusively used fixtures are
removed at `1d3aa6401`; shared walk coverage remains. Full suite: 14,705 passed,
67 skipped. `run completeness-apply-retirement --step 3 --accept --commit` reran
acceptance and advanced the step without a backend call; the resumed
`run --all --commit` finished steps 4-6 with green full-suite gates. No status
was edited by hand.

### Reconciliation and code review

Both sweeps used `uv run plan-tool --backend codex --model gpt-6.1-sol
reconcile-code completeness-apply-retirement --all --no-walk -y < /dev/null`,
covering the three code steps and skipping the three explicit non-code steps.
Reports are retained under the plan's `reports/` directory.

| Evidence | Result and disposition |
| --- | --- |
| `20261104-144231-run-reconcile.json`, step 1 | One nit: stale command/automatic-conceptual-repair explanations, confirmed by identifier and vocabulary searches across report, tail, split, merge, and invoker docstrings. Fixed `bf5ead546` (documentation class only, no runtime change). |
| `20261104-144415-run-reconcile.json` (step 2), `20261104-144608-run-reconcile.json` (step 3) | Zero findings. |
| Confirmation reports `20261104-144955`, `20261104-145334`, `20261104-145531` | Zero findings across all three code steps after the correction. |
| `codex review -c 'model="gpt-6.1-sol"' --base origin/main`, head `bf5ead546` | No actionable regressions across correctness, completeness, command wiring, surviving audit paths and compatibility; 1,337 focused tests reported passing. Conclusion: "No actionable regressions were identified in the command retirements or remaining audit paths." Transcript `.tmp/completeness-apply-retirement.review-1.log` (transient). |

### Final validation

- `uv run pytest tests/ -q -n auto` passes independently: 14,705 passed, 67
  skipped in 61.74 seconds (`.tmp/completeness-apply-retirement.isolated-tests.log`).
- A concurrent validation attempt recorded two worker crashes in unchanged
  data-contract path-reference tests, and the reviewer recorded a
  filesystem-traversal timeout. Neither is an established regression; the
  standalone green rerun is the evidence, and no timeout, worker-policy or
  data-contract change follows.
- `git diff --check` passes; the #369 exact comparison passes. No
  post-execution plan-mutating reconciliation or design audit runs.

### Publication

[Implementation PR #163](https://bitbucket.org/protagona/plan-tool/pull-requests/163)
and [plan-status PR #164](https://bitbucket.org/protagona/plan-tool/pull-requests/164)
are verified merged, in that order. `git fetch origin main` resolves to
`cf303fe29`; path-scoped diffs against `BACKLOG-376-code` and `BACKLOG-376-plan`
are empty. The item has no promoted Jira key; BACKLOG #376 is the source record.
No publication is pending.

Claude review uses the `claude-personal` alias; the ordinary CLI's expired login
prevented two review starts, which establish no review evidence. The five
completed rounds below establish the convergence result.

### Review ledger

Reviewer provenance: `/code-review` at `high`, report-only, local-diff form,
`claude-personal` (pass 1 by the driving session). Reviewers made no edits and
none claimed a clean sweep beyond the coverage they state.

#### Pass 1 (2026-11-04, `a5ac60bca71e9609ffe624322cfb4cb3839ad3f2`, 73 files)

The reviewer ran `uv run pytest tests/ -q -n auto -m "not integration"` (13841
passed, 66 skipped; integration not run). Its pyflakes claims were re-checked by
`uvx pyflakes` and grep; its line numbers were off, so cited lines are verified
ones. No correctness bugs and no regressions to create/detail repair,
review/reconcile routes, persisted schemas, legacy readers, blocking policy or
exit codes; seven low/nit findings, all dead code or stale prose.

1. Nit, unused imports left by the deletions (`DetailFormatError`, `GRANULARITY_SPLIT_SOURCE`, `UnsupportedPlanFormatVersionError`, `success` in `plan_tool/cli/completeness_phases.py`; `warn` in `completeness_cmd.py`). Disposition: fixed `3a200d72b` (five imports removed; function-local imports and the documented re-exports `_finding_progress_label`/`_fmt_finding_counts` at `completeness_cmd.py:55-56`, identical on `origin/main`, stay).
2. Nit, stale "direct pipelines" comment at `plan_tool/create.py:10571`. Disposition: fixed `3a200d72b` (names the surviving `cli/authoring.py` consumer; `iteration_stage_failure` call sites unchanged).
3. Nit, stale apply-walk rationale on `open_findings` in `completeness_phases.py` (~3876-3884) for a value always `[]`. Disposition: fixed `3a200d72b` (one-line note; report input and runtime behavior unchanged).
4. Low/nit, apply-walk wording in `convergence_diagnosis.py` (~1544). Disposition: fixed `3a200d72b`; the cited text is in `_open_medium_plus`, not `_latest_blocking_findings`, and now describes legacy sidecar annotations. `test_saved_apply_annotations_keep_their_history_meaning` pins the preserved behavior.
- A1, medium `granularity-split` replay persisted with no consumer (`mixed_split_recs`, `split_escalation_target`, `halt_on_applied`, `guard_saved_directive`, `extra_apply_sources` in `completeness_phases.py` ~3896-3911). Disposition: tracked #519, the unreachable structural opt-in; its "replayable" comment wording is updated there, not here.
- A2, CLAUDE.md rule edits require `architect`-tier review. Disposition: pending (process requirement, kept open): route CLAUDE changes to Architect review in the code PR; no session approval or merge is authorized.
- A3, `docs/evidence/public-release-final-selection-verification-20261021.json` (and the distribution-verification JSON) list now-deleted files (`docs/cli/completeness-apply.md`, `docs/cli/direct-run.md`, `docs/how-to/pipeline/direct-pipeline.md`). Disposition: declined; dated historical evidence stays unchanged under the plan's no-migration boundary and no active consumer exists.

Application: defect class is deletion leftovers (unused dependencies and explanations describing retired consumers as live); identifier and vocabulary searches covered the five imports, `stage_failure`, `open_findings`, direct pipelines, fruitless iteration, apply walks and applied/declined annotations. All sites corrected at `3a200d72b`. Full suite 14,705 passed, 67 skipped (`.tmp/completeness-apply-retirement.pass-1-fixes-tests.log`); no runtime predicate, annotation handling or schema changed.

#### Pass 2 (2026-11-04, `e6e1f32af`)

Eight findings, none above low/medium; no functional regression, exit-code, schema or legacy-reader break.

- F1, low, bare-plan audit output said "apply is withheld until a detail bundle exists" (`completeness_phases.py:3720`; `completeness_report.py:855`, ~2146, ~2300). Disposition: fixed `139283de5` (output distinguishes plan-level edits now from detail-only remedies later; stage predicates and exit codes unchanged; three tests pinning old prose updated, and restoring the pre-fix report and grouped renderer makes both targeted assertions fail, `.tmp/completeness-apply-retirement.pass-2-mutation.log`).
- F2, low, `docs/how-to/pipeline/audit.md:710, 822, 825` cited deleted `cmd_completeness_apply()`, `completeness_apply_parallel.py`/`run_parallel_apply` and a module-map row. Disposition: fixed `139283de5` (references and row removed; data-contract reader contract kept).
- F3, medium if consumed, `.claude/skills/plan-tool/DIRECTIVES.md` and `SKILL.md` (tracked copies, 13 and 3 matches) still documented the retired commands. Disposition: fixed `139283de5`; `cli/skill_cmd.py:cmd_install_skill` shows the canonical owners are `integrations/claude/SKILL.md` and `integrations/shared/DIRECTIVES.md`, and the copies were refreshed from them (bytes match).
- F4, low, `mixed_split_recs` persisted "for saved readers" with a "replayable" comment (`completeness_phases.py:3881`). Disposition: tracked #519 (see A1).
- F5, low, unreachable `granularity-split` dispatch comments in `cli/review_actions.py`. Disposition: refuted; no `completeness-apply` or deleted-lane comment remains there and the comments describe preserved dispatch semantics. Route disposition stays #519.
- F6, nit, `_APPLY_AS_FINDING_SOURCES` comment (`review_walk.py:~290`) dropped why `plan-correctness` is excluded. Disposition: declined; the detail-gate command it would cite is retired. The comment correctly requires caller opt-in, and existing dispatch tests pin the exclusion and the explicit-opt-in carve-out.
- F7, nit, `suggested_next_step_commands` comment (`completeness_report.py:~1409`) said BLOCKED findings need a manual edit because "`apply` can't add or restructure steps". Disposition: fixed `139283de5` (BLOCKED command descriptions also drop the retired rationale; `by_source` is live in detail-coverage guidance and stays).
- G1, governance, `CLAUDE.md` changed (22 additions, 42 deletions). Disposition: pending (same item as A2).

Application: defect class is live guidance naming removed application authority; searches covered retired commands/modules/handler, `CORRECTNESS_INTRO_BARE`, `by_source`, tracked `.claude` copies, and "apply withheld/verb/walk" across production, integrations, local skills and live audit docs. Post-fix no retired reference remains in production, integrations, `.claude` or the live audit guide. Full suite 14,705 passed, 67 skipped (`.tmp/completeness-apply-retirement.pass-2-tests.log`); generic reconcile/data-contract walks, #519's route and historical evidence excluded.

#### Pass 3 (2026-11-04, `7d0d7c0ce`, 76 files)

Three low/nit findings; no functional regression. The reviewer read this ledger first and repeated no earlier disposition.

- H1, low, dead opt-in hook `_create_result_sink` in `cmd_create` (`plan_tool/cli/authoring.py:959-966`) whose only setters (`direct_cmd.py:331`, `:527`) are gone; `TestCmdCreateResultSink` (`tests/test_create.py:13508`) and `tests/cli/test_authoring_cmds.py:1165` still pinned it. Disposition: fixed `2c4a3f518` (block and four command-hook tests removed; no-sink test retargeted to ordinary create with its backend assertions kept).
- H2, low, removed test `TestCarriedFindingsWiring::test_high_impact_advisory_audit_finding_is_reported_but_not_in_completeness_open_set` covered surviving #85 behavior (no conceptual finding reaches `apply_finding`, both axes persist unapplied to the `-completeness.json` sidecar, `impact="high"` survives). Disposition: fixed `8aa3a5319` (restored as `TestConceptualAuditReportPersistence::test_iterate_keeps_conceptual_axes_unapplied_and_preserves_high_impact`; removing conceptual-completeness persistence makes it fail, `.tmp/completeness-apply-retirement.pass-3-mutation.log`).
- H3, nit, test names/docstrings in `tests/test_review_walk.py`, `tests/test_review.py:9096`, `tests/test_launcher.py:4935` describing a live `completeness-apply` walker or lane. Disposition: fixed `e261e7356` (wording only, assertions unchanged; structural-route commentary stays #519's).
- Out of scope: #519 comment rewording (`review_walk.py:367`, `test_review_walk.py:4029`); #369 and #520 untouched; launcher restoration-safety plumbing (`launcher.py:~3152`) may now serve only `detail --jobs` and the review walk, untraced, backlog only if the owner wants it recorded; pre-existing pyflakes warnings (`completeness_report.py:58`, `authoring.py:32`) identical on `origin/main`. Advisory `DATA_CONTRACT.md` blank lines: declined as non-actionable at this pass (normalized after pass 5).

Application: invariant is that removing dedicated command authority leaves no exclusive handoff hook while keeping regression coverage of surviving audit behavior; no result-sink symbol remains. Full suite 14,702 passed, 67 skipped (`.tmp/completeness-apply-retirement.pass-3-tests.log`); four exclusive hook tests retired and one regression restored account for the three-test reduction.

#### Pass 4 (2026-11-04, `aad6f78d2`, 81 files)

No material defects or functional regressions; one nit.

- J1, nit, unused `import argparse` at `tests/test_create.py:9`, left by pass 3's removal of `TestCmdCreateResultSink` (same class as pass 1 finding 1; `uvx pyflakes` confirms). Disposition: fixed `9236fea4e` (sole import removed after verifying no other reference). Full suite 14,702 passed, 67 skipped (`.tmp/completeness-apply-retirement.pass-4-tests.log`).
- Advisory, none actioned: #519 and #369 fences hold; `experiments/minimize-claude/LESSONS.md:367` is #520 territory; `docs/history/backlog-decisions.md:363` is dated history; `MISSION.md:36` and `docs/ARCHITECTURE.md:205` read as generic or historical and were untraced; over-long comment lines from rewording are style only; G1 stays pending.

#### Pass 5 (2026-11-04, merge-base `465e493fc` to `d7f33ecbb`, 30 commits, 81 files)

**No actionable findings; verdict Approve.** Coverage limits: the roughly 6,000-line `tests/cli/test_completeness_cmd.py` rewrite and the deleted modules were not read line by line; the rest of the diff was read, searched by identifier and vocabulary, and checked with ruff `F` against `origin/main` (no new unused or undefined names).

- Suggestion 1, `BACKLOG.md` #256 still named the retired verb in its render target and acceptance criterion (g). Disposition: fixed (documentation-only follow-through: #256 now names the surviving finding anchors, saved readers and `apply_finding` caller context, with no new application authority or scope).
- Suggestion 2, blank lines left in `DATA_CONTRACT.md` (~1766-1785) after the parallel-replay paragraphs and a missing blank line before `#### Escalate-to-split outcome`. Disposition: fixed (spacing normalized).
- Out of scope: `.plan-tool/lessons/project.md` and `project-citations.jsonl` still carry `completeness_apply_parallel.py`/`WorktreePool` bullets, owned by #520; `_correctness_apply` keeps an "apply" name but is live (gates bare-plan wording at `completeness_phases.py` 3621, 3666, 3682) and is not renamed; launcher restoration-safety consolidation recorded as declined, with no speculative cleanup filed without verified evidence.
- Verified clean: retired-surface searches over `plan_tool/`, `prompts/`, `integrations/`, `.claude/`, `RUNBOOK.md`, `README.md`, `CAPABILITIES.md`, `docs/cli`, `docs/how-to`, `docs/reference`; parser tests assert exit 2 and `invalid choice` for the three retired commands; `--commit` is accepted on exactly `run`, `detail`, `completeness-audit` and `manifest`; `apply_finding(record_verdict=False, verdict_observer=...)` at `review_actions.py:594` is unchanged; `test_files_coherence_findings_do_not_promote_allowed_mentions` pins the one deliberate behavior change; `test_saved_apply_annotations_remain_readable_without_apply_command` covers legacy annotations.

### Convergence status

**Low-yield convergence, 2026-11-04.** Five completed Claude skill reviews are retained above. Pass 4 has one nit and no material defects (its unused import is fixed at `9236fea4e`). Pass 5 independently reviews the full updated diff at `d7f33ecbb` and reports **no actionable findings**. These are two consecutive low-yield rounds after the substantive pass-3 corrections. All findings have explicit dispositions. The loop stops under the repository's severity-aware policy; this is low-yield convergence, not a claim that every round is clean or every diff line is independently re-read.

Final regression evidence after optional documentation follow-through: 14,702 passed, 67 skipped in 64.61 seconds (`.tmp/completeness-apply-retirement.final-claude-tests.log`). No runtime source changes follow pass 5. The restored persistence test is mutation-verified; tracked skill copies match their canonical sources. Prepared local code and plan-status branches are refreshed from the final committed work through the repository split script; pre-Claude snapshots are retained under suffixed branch names. Publication is verified in the Publication section above.

Open items: #519 (unreachable structural opt-in and its comment wording), #520 (stale lessons), #369 (untouched, independent), and the pending Architect-tier review of the `CLAUDE.md` rule edits (A2/G1).








