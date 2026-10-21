# CLAUDE.md measured incidents

*Part of the plan-tool developer docs. Start at [Contributing](../../CONTRIBUTING.md).*

**Purpose.** Holds the multi-paragraph dated measurements that back rules in the project
[`CLAUDE.md`](../../CLAUDE.md), so that file can carry each rule with a short verdict. Each section is
historical record, dated at the top of its own text, and was moved verbatim from the `CLAUDE.md`
section named under its heading on 2026-10-09. A section's wording may refer to "this file" or to a
rule "below"; read those as the `CLAUDE.md` rule it was moved from, not as this page.

**How to use it.** Read the rule and verdict in `CLAUDE.md` first. Open a section here when you need
the numbers, the sequence of rounds, or the reasoning that justifies a rule you intend to change.
These records gate nothing, and several are n=1.

| Section | Rule it supports |
| --- | --- |
| [1. Completeness-audit calibration, 2026-08-08](#1-completeness-audit-calibration-2026-08-08) | § Model selection |
| [2. Class-wide application versus cited-spot application, 2026-07-31](#2-class-wide-application-versus-cited-spot-application-2026-07-31) | § Driving the convergence loops (fix the class, not the cited spot) |
| [3. One-site fixes with a green suite, 2026-08-06](#3-one-site-fixes-with-a-green-suite-2026-08-06) | § Driving the convergence loops (check 0) |
| [4. A remedy that passed the sweep checks and was wrong, 2026-08-06](#4-a-remedy-that-passed-the-sweep-checks-and-was-wrong-2026-08-06) | § Driving the convergence loops (check 4) |
| [5. A remedy justified by a false claim about the code, 2026-08-04](#5-a-remedy-justified-by-a-false-claim-about-the-code-2026-08-04) | § Driving the convergence loops (check 4, second instance) |
| [6. A code-canonical audit pointed at a false plan claim, 2026-07-29](#6-a-code-canonical-audit-pointed-at-a-false-plan-claim-2026-07-29) | § Driving the convergence loops (reconcile-plan is pre-execution) |
| [7. A fix that regressed a sibling case, 2026-08-21](#7-a-fix-that-regressed-a-sibling-case-2026-08-21) | § Driving the convergence loops (close the invariant) |
| [8. False positives caught by existing tests, 2026-08-14](#8-false-positives-caught-by-existing-tests-2026-08-14) | § Driving the convergence loops (verify a bug finding against its tests) |
| [9. Consolidation claims checked by AST, BACKLOG 79](#9-consolidation-claims-checked-by-ast-backlog-79) | § Authoring hygiene and anti-creep |
| [10. A premise-conditioned design, 2026-08-05](#10-a-premise-conditioned-design-2026-08-05) | § Audit the why, not the what (premise-conditioned-design) |
| [11. The two intent reversals, 2026-07-31 and 2026-08-02](#11-the-two-intent-reversals-2026-07-31-and-2026-08-02) | § Validating a semantic property you cannot observe |
| [12. The test-ordering contract withdrawal, 2026-07-30](#12-the-test-ordering-contract-withdrawal-2026-07-30) | § Withdrawn: the per-`change_type` test-ordering contract |
| [13. Fence recognition for machine-parsed sub-blocks, rounds 4 and 5](#13-fence-recognition-for-machine-parsed-sub-blocks-rounds-4-and-5) | § Machine-parsed finding annotations |
| [14. An exemption nothing pinned, 2026-08-04](#14-an-exemption-nothing-pinned-2026-08-04) | § Tests (assert the carve-out) |

## 1. Completeness-audit calibration, 2026-08-08

*Moved from `CLAUDE.md` § Model selection.*

**The calibration, measured 2026-08-08 on the `audit-trajectory-instrumentation`
withdrawal.** Eight bare-plan audit rounds each found *real* defects and each was
correctly applied — and the sequence converged on nothing, because no round could
ask whether the plan's motivating symptom was real. One conceptual question
("does the `spinning` verdict actually reproduce?") plus a throwaway replay
script settled it in ~15 minutes: it never reproduces, and the plan's own remedy
*causes* it. Roughly 90 minutes of audit wall-clock and seven commits of design
sat downstream of a question nobody asked.

**The specific lesson for this codebase:** the completeness audit is *not* the
conceptual surface it resembles. Its frame — here is the plan, judge whether its
ideas are sound — structurally excludes "should this plan exist," so a stronger
model there sharpens findings inside the frame that was already the problem.
Spend it at `create`, where the frame is still being chosen. This is the same
shape § "Audit the why, not the what" describes: validity is local, necessity is
global.

## 2. Class-wide application versus cited-spot application, 2026-07-31

*Moved from `CLAUDE.md` § Driving the convergence loops (fix the class, not the cited spot).*

Measured 2026-07-31 on `roadmap-01-domain-constraints` across six audit rounds. Rounds 2–4 were each applied *at the cited spot only* and produced **13 findings, every one seeded by the previous round's own edits** rather than by the plan. Rounds 5 and 6 were applied at the defect class using the checks below, and the re-seed rate fell from **7 of 11 to 2 of 10** while the severity ceiling dropped from **three HIGH to none**. 

## 3. One-site fixes with a green suite, 2026-08-06

*Moved from `CLAUDE.md` § Driving the convergence loops (check 0).*

     **Why instinct is not enough, measured 2026-08-06 across one working tree of seven `direct` changes: six were applied at the first site only, and the full suite was green on all of them.** The scope-fence intent fix reached 1 of 7 intent consumers; the empty-response retry opt-out reached 1 of 2 backend callers; the `sweep` orphan carve swept 4 doc sites and missed 4 more plus a now-callerless function; a new severity table was added three hundred lines below one whose own comment says it is "the single source"; a churn advisory shipped without the suppression its sibling advisory six lines below already had. **The mechanism that hides this is the sibling sites' own tests**: each un-swept site had a test pinning the *old* behavior, so a one-site fix is green *because* the class is incomplete. Five such tests had to be rewritten when the sweep was finished. A green suite is therefore evidence about the site you changed and **no evidence at all** about the ones you didn't — do not read it as one.

Measured 2026-08-06 — finishing the scope-fence intent sweep across its seven consumers turned five previously-green tests red (`test_merged_step_keeps_unanimous_tbd`, `test_rebaseline_seed_keeps_tbd_intent`, `test_carved_seed_keeps_tbd_intent`, `test_intent_block_renders_tbd_as_written`, and the leaf's own `test_tbd_intent_still_renders`), each having pinned "`TBD` still renders" with a comment explaining why the divergence was deliberate. 

## 4. A remedy that passed the sweep checks and was wrong, 2026-08-06

*Moved from `CLAUDE.md` § Driving the convergence loops (check 4).*

Round 5 (2026-08-06) closed an overwrite-warning finding by specifying the pointer `--from-stage <lowest overwritten stage + 1>` and swept it into every site, with tests: complete by checks 1–3, and **wrong** under the retired full-rewrite route, because `--from-stage N` then rewrote every stage from N up, so the pointer preserved only the artifacts *below* it. On the ordinary two-stage re-run it told an operator to run a command that destroyed the same direct edit a second time. Round 6 returned it as `overwrite-pointer`, the only finding to recur. 

## 5. A remedy justified by a false claim about the code, 2026-08-04

*Moved from `CLAUDE.md` § Driving the convergence loops (check 4, second instance).*

     **Second instance, 2026-08-04 on `roadmap-02-feedback-channel`, and the tell generalizes: the *stated reason* was checkable and false.** A round-2 apply placed a refusal of model-authored feedback at step 6's write, justified as "the only place that knows the run produced the artifact". Round 3 returned it: `roadmap.py:_run_stage` has one call site inside the stage loop and only ever parses a model reply, while `_load_and_regate_below` bypasses it, so the *attempt loop* distinguishes the same two cases and already owns a correction channel — and a refusal after the loop returns matches no member of `FAILURE_INVOKE`/`FAILURE_PARSE`/`FAILURE_GATES` or of the `completed`/`stage-exhausted` outcomes. **When a remedy's justification is a claim about the code, verify it against the code before applying** — a one-command `grep` for the call sites would have caught this, and the false half was load-bearing for the placement.

## 6. A code-canonical audit pointed at a false plan claim, 2026-07-29

*Moved from `CLAUDE.md` § Driving the convergence loops (reconcile-plan is pre-execution).*

Observed 2026-07-29 on `jira-grade-01-detail-instrument` step 2: the detail asserted "`done` steps stay skipped at every site", which was never true at HEAD for two of the checks. The correct resolution was to delete the false claim; a code-canonical audit pointed at the same discrepancy would just as readily have proposed the inverse — carving a `done` exception into checks that never had one.

## 7. A fix that regressed a sibling case, 2026-08-21

*Moved from `CLAUDE.md` § Driving the convergence loops (close the invariant).*

**Measured 2026-08-21** on the `--model`-family backend-inference feature: a single 3-line `explicit` expression in `cli/app.py:main()` (gating the missing-binary preflight) drew a different confirmed bug on 3 consecutive `/code-review` rounds, each fix backed by a new passing test. Round 1's fix (`inferred_backend != "claude"`) closed its own case but left round 2's stale-env case open. Round 2's fix (`name != "claude"`) closed that case but silently regressed `PLAN_TOOL_BACKEND=claude` set explicitly with no `--model` override — working, and effectively pinned, since before this feature existed — back to skipping the preflight it used to trigger. Neither fix was checked against the case it broke because neither round stated the invariant (\"preflight fires iff the resolved backend was determined by something other than silent defaulting\") or enumerated the combination space it depends on (`--backend` set/unset × env set/unset × inferred set/unset, each possibly matching or not matching the default) before writing the patch. 

## 8. False positives caught by existing tests, 2026-08-14

*Moved from `CLAUDE.md` § Driving the convergence loops (verify a bug finding against its tests).*

Measured 2026-08-14 on a `/code-review` pass applying 15 findings through the session: 2 of 15 were false positives whose static trace read as correct but were contradicted by an already-existing test written in the same commit as the code being flagged; both were caught only because the standing full-suite re-run above ran before the pass was declared done, not because either was checked against its test file first. 

 Confirmed 2026-08-14: both false positives in the same `/code-review` pass this rule responds to were caught specifically because the tests already pinning the disputed behavior were named and asserted this way — the practice already paid for itself once; it is not a new, unproven ask.

## 9. Consolidation claims checked by AST, BACKLOG 79

*Moved from `CLAUDE.md` § Authoring hygiene and anti-creep.*

BACKLOG #79 sat for months listing five "duplicated helpers", and when the claims were finally checked with an AST pass that normalizes docstrings, function names, and parameter names, **four of them were wrong in the direction that breaks things** — it called for folding three different durability contracts into one atomic-write helper (dropping `fsync` from callers that need it), folding eleven confirm gates that share an idiom but no implementation, merging two timestamp helpers that emit *different strings* into a drift-guarded persisted format, and merging an archive-move pair whose whole point is opposite failure policies. 

## 10. A premise-conditioned design, 2026-08-05

*Moved from `CLAUDE.md` § Audit the why, not the what (premise-conditioned-design).*

Measured 2026-08-05 on
  `example-app-amplify`'s `assessment-service-dynamic-people-types`: a non-code step 1
  probed a vendor endpoint whose existence was inferred from two siblings'
  naming, and steps 2–6 — every one authored before it ran — consumed whatever
  it would find. Four audit rounds went 17 → 16 → 25 → 30 findings, correct
  every round, because a contradiction between two hypothetical arms is
  unfalsifiable: you satisfy the finding by elaborating either arm, and
  elaborating an arm adds surface for the next round. One throwaway script,
  three runs, ~10 minutes settled it, and deleted a mapping table, a local copy
  table, a cache-key branch, and an entire last-known-good persistence layer
  that had been authored, audited, and approved to defend a failure mode one
  HTTP call disproved. 

## 11. The two intent reversals, 2026-07-31 and 2026-08-02

*Moved from `CLAUDE.md` § Validating a semantic property you cannot observe.*

**The two intent reversals — settled history, recorded here because the entry
they cite is gone.** Both were explicit user decisions. **2026-07-31:**
`2-intent-scope-fence.md` widened BACKLOG **#206** — closed and deleted once
discharged, so cite this record rather than the id — shipping a plan-altitude
`Plan.intent`, which that entry non-goaled, and an advisory presence check,
which it did not scope. It did **not** widen the entry's *"required on existing
plans"* non-goal, and it kept its duplication call verbatim: intent is a
one-line seed the prompts consume, never re-checked against `## Why`.
**2026-08-02:** `2-intent-required.md` lifted exactly one bullet of that plan's
"Not allowed" list — *any gate, exit-code flip, or refusal-to-advance keyed on
an intent* — and **only for presence**: a missing intent is now a `medium`
self-consistency finding that blocks completeness convergence. The exit-code
convention is untouched (a completed audit still exits 0 unless
`--fail-on-findings`). That refusal's stated reason — a check firing on the
whole corpus with no remedy teaches operators to skim the channel — is
**discharged** by that plan's authoring and proposer work, not overruled. The
other four not-allowed bullets stay refused in the words they carry, and
everything past presence is permanently refused: a finding proposing one is
invalid, not deferrable. Long form:
`docs/implementation-plans/2-intent-scope-fence.md` (`## Scope guardrails`,
`## Out of scope`) and `docs/implementation-plans/2-intent-required.md`
(`## Architecture`).

## 12. The test-ordering contract withdrawal, 2026-07-30

*Moved from `CLAUDE.md` § Withdrawn: the per-`change_type` test-ordering contract.*

**What existed.** `refactor` steps were told to write characterization tests green **before** touching the code, which must then pass unchanged; `feature` steps to implement first, then test. It shipped as three things: a directive in the `run` prompt (`launcher.py`), a parallel directive in the `detail` authoring *and* reviewing prompts (`detail.py`), and `collect_change_type_test_order_findings` — a phrase-matcher over the detail's `## Tests` prose that fired when it said "after the refactor" without saying "characterization".

**Why it went — the measurement.** The 2026-07-30 study replayed every `refactor` step in its repository sample: it checked out the step's parent commit, copied that step's own post-change test files in **unmodified**, and ran them. **32 refactor steps of 313 executed (10.2%); 25 of 28 conclusive replays would have fired — 89%**, and still **81%** after excluding `cli-package-split`, a mass rename contributing 12. The dominant mode was **uncollectable (10 of 16 outside that plan), not failing**: the tests import symbols the refactor *created*. That is inherent to any refactor changing test-visible structure, not evidence anyone wrote tests late. Only 3 of 28 were clean.

**The lesson, which generalizes past this feature.** "Passes before *and* after" is satisfiable only for refactors that preserve the **test-visible interface**, and most real refactors do not. The directive asserted a property most steps *cannot have*; the matcher then enforced only that the document **used the right vocabulary** about it. A checker that validates prose conformance to an unsatisfiable contract reads as rigor and delivers none — and at an ~85% false-positive base rate an advisory becomes noise operators learn to ignore, which is the failure mode that kills the whole finding channel.

**Use this evidence.** The sample shows why test ordering is an unreliable gate for refactors that change the test-visible interface. It does not establish when anyone writes tests. Keep coverage requirements focused on changed behavior and observable test-file authorship; do not revive the withdrawn prose matcher.

## 13. Fence recognition for machine-parsed sub-blocks, rounds 4 and 5

*Moved from `CLAUDE.md` § Machine-parsed finding annotations.*

plan-audit.md's bare-step restatement (`### Restated` / `### Fix`, parsed by `_split_audit_restated_and_fix` in `review.py`) is the shipped example, and it replaced an inline `→ restated:`/`→ fix:` design that two code-review rounds broke in succession — first a marker-shaped phrase earlier in the finding's own (mandatory-verbatim) plan citation, then a case where that phrase was the *only* occurrence of its keyword, defeating a "last occurrence wins" hardening pass. Both breaks were possible because nothing in the inline syntax was distinguishable from ordinary prose except its position; a heading that must start its own line cannot be produced by *inline* quoted prose, closing that class.

**A round-4 review found the heading redesign's own closure claim overreached: a *multi-line* citation can still contain a genuine line-starting heading** (this file's own worked example does, in `plan-audit.md`), which is a different case than the inline-marker collision the redesign closed. Positional heuristics (first/last occurrence) provably cannot distinguish a citation's heading line from the real one, so round 4's fix required `plan-audit.md` to wrap a verbatim citation in a fenced ` ``` ` code block and had `_split_audit_restated_and_fix` exclude any heading match found inside a fenced span. An un-fenced citation containing such a line is a known, accepted residual risk (pinned by `tests/test_review.py::TestCheckPlanAudit::test_unfenced_citation_containing_a_real_heading_line_is_a_known_residual_risk`), not a bug to chase further.

**Round 4's fence-exclusion was itself only a regex over `re.MULTILINE`/`re.DOTALL`, and round 5 found it was still positional, not structural — the label was aspirational, not yet true.** Five distinct ways to defeat it: an unclosed citation fence paired with an unrelated *later* fence elsewhere in the same finding (e.g. a code sample in the real `### Fix` text) instead of spanning to end-of-text; a nested same-length triple-backtick sequence inside the citation closing the fence early; `~~~` tilde fences (equally valid CommonMark) not recognized at all; a fence indented 4+ spaces not recognized; and CRLF line endings hiding the fence entirely. A sixth, separate bug: even a correctly *excluded* fake heading match still leaked its fenced text into the *adjacent real* heading's captured value, since only the match was excluded from being a boundary, not the span's text from the surrounding value. The fix this time was not a sixth regex: `plan_tool/jira_grade.py` already had a correct, tested, line-based fence state machine (`_FENCE_RE`, used by `_scan_sections`/`_unterminated_fence`) that `review.py` already imports from — round 5's finding was that the round-4 regex reinvented this mechanism, with regressions. The actual fix added a general-purpose `fenced_spans()` to `jira_grade.py` (length-matching per CommonMark, tilde-aware, CRLF-safe via `str.splitlines`, an unclosed fence spans to end-of-text) and had `review.py` consume it, plus excising fenced spans from a captured value's text, not just from the boundary search. **The lesson: "we closed it with a fence" is a mechanism claim, not a structural guarantee — a regex fence-matcher is exactly as positional as the heading matcher it protects, unless it is actually correct.** A remaining, accepted residual: a same-length nested triple-backtick run inside a citation (e.g. quoting a fenced block using the *same* backtick count as its own outer fence) still closes early; `plan-audit.md` now instructs opening with 4+ backticks whenever the cited text contains its own triple-backtick sequence, which is prompt compliance, not code enforcement, same as the un-fenced-citation risk above.

## 14. An exemption nothing pinned, 2026-08-04

*Moved from `CLAUDE.md` § Tests (assert the carve-out).*

Measured 2026-08-04: `check_attribute_totality`'s "a constraint on a `traded-away` attribute is fine" was stated in the prompt, the gate docstring, *and* `ROADMAP_FORMAT.md`, and folding `TRADED_AWAY` into the rejecting arm passed the entire suite. 

Four instances of reading-instead failing — two prompt-key tests that stayed green with the whole inventory section deleted (`anchor` passed as a prefix of `anchor_id`), `test_roadmap_format.py`'s first version reading only ```markdown blocks when 7 of 14 were YAML, and the carve above.
