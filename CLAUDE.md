# CLAUDE.md

For roadmap feedback lifecycle work, start with `ROADMAP_FEEDBACK_FORMAT.md`
for mutable ledger ownership and `ROADMAP_FORMAT.md` for immutable artifacts.
Every roadmap is versioned from birth: one stored copy, read through the
accepted head. Ordinary feedback snapshots ledger items into an inert
candidate; `--reopen-ledger-feedback` and decision settlement remain separate
selector-shaped routes.

This file provides guidance to AI coding assistants **developing `plan-tool` itself**.

> **Driving `plan-tool` (any repo, any assistant) is a different document:**
> [`integrations/shared/DIRECTIVES.md`](integrations/shared/DIRECTIVES.md) is the
> canonical, tracked source for the two audit gates (bare-plan before `detail`,
> detail-grounded after), the session-directed convergence loop and its three exits,
> `--iterate` / `--commit`, reconcile directionality, the post-run tail, and seed
> authoring. Consuming repos reference it via a machine-local symlink
> (`~/.claude/directives/plan-tool.md`), so **edit it there, not in a copy** —
> and keep the sections below scoped to developing this codebase.

> **Changing the rules in this file requires `architect`-tier review**
> (owner decision, 2026-09-17), via the normal pull-request flow — see
> `docs/TRACKING.md` § "Choosing the tier". This file keeps each rule and a
> short verdict; the multi-paragraph dated measurements behind them live in
> [`docs/evidence/claude-md-measured-incidents.md`](docs/evidence/claude-md-measured-incidents.md).

## What this is

For the roadmap store, `ROADMAP_FORMAT.md` owns the contract and
`docs/ARCHITECTURE.md` owns the layer boundary. A roadmap has exactly one stored
copy, the immutable versions under its accepted head, and every command reads
the accepted version. The first stage run holds passed stages in a resume
directory and publishes the version and head only when all four pass; a stage
run refuses once a head exists. An older folder with no head is converted by
hand (`docs/how-to/roadmap.md` § 1); no tool migrates it.

`plan-tool` is a Python 3.13 CLI that turns a rough idea into a developer-ready implementation plan (ordered steps + per-step detail files, backed by YAML frontmatter) and then either **executes** it locally step-by-step via Claude subprocesses (`run`) or **exports** it as Jira-sized stories (`jira`). The frontmatter is the machine-readable source of truth; the markdown prose below it is for humans.

Pipeline: `create → detail → audit ──┬── run` / `└── jira ── verify`.

`annotate` is a forward-seed bridge, not a pipeline stage: it judges existing plans/notes against current code and emits `create --from-existing` seeds for the *next* iteration — never mutating its source except the opt-in `--archive` move (contrast `reconcile-plan`, which mutates a live plan in place). Batch annotate accepts multiple paths/globs and prints a coverage/grounding summary; low grounding becomes NEEDS-REVIEW / review-required carryover; archive collisions use numbered `.replaced.N` generations; `--iterate` is rejected, so iterate the follow-up `create`, not annotate. Use `list --status` to roll up cached reports and `jira --lint` to lint existing story exports without invoking a backend or assigning epics.

The project mission and grounding principles — the rules the codebase is built to obey, including *deterministically driven non-determinism* — live in `MISSION.md`. Resolve ambiguous design decisions toward those principles.

`reconcile-plan --refresh` is the cheap fingerprint-gated form of `reconcile-plan` (diffs a tracked grounding baseline against current code, spends no Claude on no-drift and reconciles only the changed files otherwise); `create --reprocess` is unrelated to code — it fills `_(TODO)_` placeholders from an archived predecessor.

## Code comments

Keep comments and docstrings terse — a line or two on the non-obvious *why*, not a paragraph. When a flow or contract needs more depth, put it in the relevant doc (`docs/how-to/pipeline/run.md`, `DATA_CONTRACT.md`, the FORMAT docs, …) and cite it from the code (`See docs/how-to/pipeline/run.md`) instead of inlining a long block — block comments rot and drift from the code; a one-line pointer to a maintained doc doesn't. Some modules predate this rule and carry long comments; match the terse style when you touch them rather than extending it.

## Documentation is forward-looking

**Write every document in the present and future tense — what the thing *is* and *will do*. Past-tense content must earn its place or be deleted.** This governs everything: `CLAUDE.md` and the reference docs, plan bodies and detail files, `plan-seeds/`, `BACKLOG.md` / `BUG_BACKLOG.md`, and code comments.

The failure mode is **not** that history exists. It is that **history gets written in the present tense and then never revisited, so it reads as current design.** A sentence that was true when written is indistinguishable from a sentence describing what ships today, and readers — human *and* audit — act on it. Stale rationale is worse than no rationale: it actively argues for the wrong thing.

**History is warranted only when a reader needs it to act correctly.** Four cases:

- **Don't-reopen decisions** — a settled choice an audit or a future session would otherwise re-litigate ("decided 2026-07-22, user-confirmed; do not re-open").
- **Don't-repeat failures** — an approach tried and abandoned, *with the reason* ("this spun for four rounds because each fix seeded the next finding").
- **Live legacy contracts** — former behavior that still ships and must keep working ("legacy bundles are always read as run-grade").
- **Provenance** — where a number or claim came from, so a reader can judge how much to trust it.

Anything else describing a former state is **deleted, not archived in place**.

**When history is warranted, mark it as history**: date it and frame it as past — "cut 2026-07-29", "superseded by #171", "was: churn floors". Never leave a former rationale in the present tense beside a current one.

**Delete on sight.** These are defects, never context:

- a rationale that depends on something cut, demoted, or reversed;
- a cross-reference to a renumbered, merged, carved-out, or deleted element;
- a gate, dependency, or acceptance criterion conditioned on something that no longer exists;
- a title, summary, or headline naming a concern that has been demoted;
- vocabulary from an abandoned approach ("the control", "both arms", "the experiment") sitting in prose that describes what ships.

**After any structural change — a cut, split, merge, scope-out, renumber, or reversed decision — sweep both halves:**

1. **Identifiers** — the numbers, ids, slugs, and paths the change invalidated.
2. **Vocabulary** — the *words* of the removed concept, across the plan body, every detail file, the seeds, and the backlog.

Half 2 is the one that gets skipped, and it is where the expensive errors live: an identifier sweep leaves prose that still argues for the thing you removed. **Grep for the concept's nouns, not only its numbers**, and check the *backlog* as well as the plan — entries describing an arc are exactly as perishable as the arc.

Evidence this is recurring rather than a style preference: a single 2026-07-29 session found ten cross-references to a step that no longer existed, four step rationales arguing for a comparison the plan had banned, three backlog entries describing a superseded arc (including a gate condition on a deleted check), a plan whose stated motivation was a claim nothing depended on, and a seed whose title named a demoted metric — every one of them "correct when written".

## Developer-facing documentation readability

Developer-facing documentation supports scanning before deep reading. State a
section's purpose first; represent mappings, state-dependent behavior, and
ordered flows in their natural form; and separate the normal path from its
exceptions. Top-level pages route by task; deeper procedure, settled rationale,
and exact contracts belong in their respective documentation layers. Follow
[`docs/reference/documentation-style.md`](docs/reference/documentation-style.md) when writing or
reviewing a live developer document. It preserves concrete technical facts
while directing the structure and review checklist.

## Commands

```bash
uv sync                                    # install deps (uv fetches its own Python)
uv run pytest tests/ -q                    # full suite (serial; >2 min — background it)
uv run pytest tests/ -q -n auto            # parallel (one worker/core) — ~28s, 7.6k tests; prefer this
uv run pytest -m "not integration" tests/ -q   # fast loop — unit/component only (use during dev)
uv run pytest -m integration tests/ -q     # integration only
uv run pytest tests/test_review.py::TestSomething -q   # single test/class
```

`uv tool install --editable .` puts `plan-tool` on PATH against this clone (no reinstall on `git pull`). There is no separate lint/build step beyond pytest.

## Model selection

**Use the strongest tier for conceptual work (Claude `claude-opus-5-5`) and the
working tier for audit, implementation, and validation (Claude
`claude-sonnet-5-5`). Codex uses `gpt-6.1-sol` for both (owner instruction,
2026-10-14, recorded in `integrations/shared/DIRECTIVES.md`). Cursor passes no
`--model` and uses Auto.** The general
rule and its rationale live in the owner's personal user-level `CLAUDE.md` (not in this repository) § "Spend the stronger model
where a mistake compounds"; the per-subcommand mapping lives in
[`integrations/shared/DIRECTIVES.md`](integrations/shared/DIRECTIVES.md) §
"Which model to run a subcommand with" (short version: strongest tier for `create` and
`roadmap`, working tier everywhere else, passed via `--model` since the project file's
override is per-backend, not per-subcommand). Only this repo's own measured
verdict belongs below; the full measurement is in the evidence page.

**The calibration, measured 2026-08-08 on the `audit-trajectory-instrumentation` withdrawal:** eight bare-plan audit rounds each found *real* defects and each was correctly applied, yet the sequence converged on nothing, because no round could ask whether the plan's motivating symptom was real. The completeness audit's frame — judge whether the plan's ideas are sound — structurally excludes "should this plan exist", so a stronger model there sharpens findings inside a frame that may already be the problem. Spend it at `create`, where the frame is still being chosen. This is the shape § "Audit the why, not the what" describes: validity is local, necessity is global. Record: [evidence](docs/evidence/claude-md-measured-incidents.md#1-completeness-audit-calibration-2026-08-08).

## Plan audit gate

Before implementing a new plan or clearing its backlog record, run `plan-tool completeness-audit <slug> --iterate`. `plan-tool validate` checks format, not design. Interpret the final audit result through [`docs/how-to/pipeline/audit.md`](docs/how-to/pipeline/audit.md)'s qualified-result contract: qualification governs whether the audit can certify convergence, not whether an agent may triage a completed report through a session. Read the saved audit, verify and correct actionable in-scope conceptual findings through a session-directed edit, then re-audit the changed committed snapshot until clean or low-yield. Do not resample unchanged plan text merely to obtain qualification. Record the audit command and outcome in the handoff.

**Audit bare plans before detail authoring, then audit again after it.** A plan is bare when one or more steps have no detail file. `completeness-audit --iterate` supports that state: it judges the plan body and code at HEAD at the plan/concept level, labels the report with the exact detail coverage, and does **not** treat missing detail files as a defect or claim that its conceptual calls were detail-grounded. Use this early audit after `create` and after material plan-body changes; it can catch a missing plan-level contract, ordering rule, risk, or acceptance criterion before detail prose multiplies it.

Read a bare-plan result by axis. `plan-correctness` findings remain actionable plan-body defects. `plan-completeness` findings are recorded; medium findings on that axis do not block at bare stage. Detail-level remedies belong in `detail`; do not use a missing detail file as a reason to invent detail content in the plan. A bare-plan audit is therefore an early design gate, not the final detail-grounded gate: author the detail bundle, then run the same iterative audit again before implementation. In the handoff, record the report path, `N of M` detail coverage, the audit-coverage verdict (including a budget-limited result), and which remedies remain detail-owned.

**At bare stage, test named properties rather than unselected mechanisms.** An uncovered route for a named safety, ordering, ownership, compatibility, bypass, or acceptance property remains an actionable correctness gap; state the missing property and route. Leave an internal delivery choice to `detail` unless the plan explicitly makes that mechanism the observable contract for a named property. The run-grade mechanism / same-finding `edit_drift` advice is recommend-only: it neither automatically defers a finding nor changes blocking, continuation, failure, or exit behavior. The detail-grounded audit still judges the selected contract.

**Correct material plan-level gaps through judged hand-edits before `detail`.** The bare-stage bar does not put an explicit plan-level contract, ordering, risk, acceptance criterion, or reader-selection decision in a `plan-completeness` finding off limits. When the suggested fix changes the plan body, step graph, or acceptance criteria, make one bounded, judged hand-edit, commit, and re-audit before authoring details. Leave a finding for `detail` only when its remedy genuinely specifies implementation mechanics, a per-step detail contract, or fixture-level coverage; never copy those mechanics into the plan just to satisfy the early audit. A confirmed-dry re-audit plus a fresh unchanged snapshot is enough evidence to proceed to `detail`; record the before/after finding set and conceptual-call reuse in the handoff.

Bare and detail gates use different conceptual bars via `is_blocking_finding` — see `integrations/shared/DIRECTIVES.md` and `docs/how-to/pipeline/audit.md`.

## Driving the convergence loops

**Use `--iterate` on every command that supports it (except `detail`); never pass `--no-iterate` by default.** Where the convergence loop is available, it must run so gates → `apply_finding` → re-audit converge; a one-shot pass leaves findings unresolved. Availability and default differ by command: `create` defaults `--iterate` ON (pass `--no-iterate` only to opt out); `completeness-audit` defaults it OFF, so pass it explicitly; `detail` defaults `--iterate` **OFF** (a one-shot write — don't opt it back in unless explicitly asked); `run` has no iteration loop. Both `detail --reconcile` and `run --reconcile` reject `--iterate`; standalone reconcile verbs do not accept iteration flags. Read saved reports, judge corrections, commit, and invoke the appropriate reconciliation direction again. Don't tack `--iterate` onto commands that don't accept it or where it's a no-op (e.g. `run`, `review`, `verify`, `jira`) — it may warn or reject the combination. This mandate overrides any older recipe (including BACKLOG.md's "author phase with `--no-iterate`"). Drop `--iterate` only when the user explicitly asks for a single non-converging pass.

**Close conceptual findings through judged hand-edits, whoever is driving.** The `completeness-audit` loop applies only its **deterministic well-formedness** findings and persists conceptual `plan-correctness`/`plan-completeness` gaps **unapplied**; material ambiguity is part of `plan-correctness`. Human operators and assistant sessions read the completed saved report, verify its claims, judge related findings together, edit the plan/detail prose directly, commit the bounded correction batch, and re-run `completeness-audit --iterate --commit` against the changed snapshot. Surface scope/design decisions to the user. Qualification governs certification of convergence, not whether a completed report can inform corrections; do not resample unchanged text merely to obtain qualification.

**Before applying anything, clear § "Audit the why, not the what".** That section is a **precondition on this whole apply loop**, not background reading: if one of its six shapes has fired, applying findings without first surfacing it to the user is the defect, and the four checks below will faithfully help you elaborate work that should not exist. Ask *whether the arm belongs* before asking *how to satisfy its findings*.

**Fix the class, not the cited spot — a finding names one instance of a defect that usually has siblings.** Applied at the cited spot only, rounds 2–4 produced findings seeded by the previous round's own edits; applied at the defect class, the re-seed rate fell from **7 of 11 to 2 of 10** and the severity ceiling from **three HIGH to none** (measured 2026-07-31, `roadmap-01-domain-constraints`; [evidence](docs/evidence/claude-md-measured-incidents.md#2-class-wide-application-versus-cited-spot-application-2026-07-31)). The checks work; they are also not sufficient on their own — see check 4. Run all five — they are mechanical, and none needs another Claude call. **Check 0 runs *before* you edit; 1–4 before you call the gap closed:**

0. **Enumerate the sites before editing any of them — as an explicit step, not as an instinct.** Name the defect as a *class* in one sentence, then run two searches and write down what they return: **by identifier** (the symbol, id, path, flag, predicate the finding names) and **by vocabulary** (the concept's *words*, in other phrasings). Apply at every site the searches return, or state per site why it stays. The person or session editing the files owns this enumeration; it is a required deliverable, not an implicit check. Checks 2 and 3 are the same two searches run as a *post-hoc audit*; doing them up front is what makes the edit itself class-wide, and it is markedly cheaper than re-deriving the class after a partial sweep has already shipped.

   **Why instinct is not enough — measured 2026-08-06: six of seven `direct` changes were applied at the first site only, with the full suite green on all of them.** The sibling sites' own tests pin the *old* behavior, so a one-site fix is green *because* the class is incomplete. A green suite is evidence about the site you changed and **no evidence at all** about the ones you didn't — do not read it as one. Itemized record: [evidence](docs/evidence/claude-md-measured-incidents.md#3-one-site-fixes-with-a-green-suite-2026-08-06).
1. **Read `suggested_action`, not just the body.** The auditor already computes the remedy's scope and it is now rendered as a `- Fix:` sub-bullet under each conceptual finding. Two of the three round-3-seeded findings were spelled out there verbatim ("then add a test proving the chosen behavior") and were missed because the persisted report used to withhold the field.
2. **Restatement:** grep the changed *phrase*, not the changed identifier. The same contract is restated in the plan body, the format doc, and every consuming step; an identifier sweep misses prose that says the same thing in other words. This is the vocabulary half of the sweep rule above.
3. **Set completeness and implication:** if the change touches one member of a set, do all N (converting 3 of 7 gates is what produced the round-4 finding); and if it adds a rule, add what the rule obliges — a test, an acceptance criterion, a result field, an error message. A rule with no test is the single most common re-seed.
4. **Check the remedy against the *goal*, not just against the finding — state the property, then verify the mechanic delivers it.** Checks 1–3 all ask "did I apply this everywhere?" and none asks "does what I applied actually work?" A remedy can pass all three and still be wrong, and that failure re-seeds exactly like an incomplete one. Example, 2026-08-06: an overwrite-warning remedy passed checks 1–3 yet was **wrong** on the ordinary two-stage re-run, where it told an operator to run a command that destroyed the same direct edit a second time ([evidence](docs/evidence/claude-md-measured-incidents.md#4-a-remedy-that-passed-the-sweep-checks-and-was-wrong-2026-08-06)). Write down the property the fix is supposed to produce ("the operator keeps the artifact they edited"), then trace the mechanic against it on the *common* input, not the edge case — the two-overwrite case here carried most of the traffic and was the one that broke.

   **Second instance, 2026-08-04 on `roadmap-02-feedback-channel`: the *stated reason* was checkable and false.** **When a remedy's justification is a claim about the code, verify it against the code before applying** — a one-command `grep` for the call sites would have caught this, and the false half was load-bearing for the placement. Detail: [evidence](docs/evidence/claude-md-measured-incidents.md#5-a-remedy-justified-by-a-false-claim-about-the-code-2026-08-04).

**Before spending a `plan-tool split`, `plan-tool scope-out`, or a re-seed on a recurring finding, trace its provenance first.** A finding that recurs because *your own last edit was wrong* is not evidence of a mis-decomposition — BACKLOG #125's stopping rule counts severities but not provenance. Compare retained reports (or their retained conclusion summaries), documented decisions, current code and existing tests to distinguish an original defect from an incorrect prior fix. Use `git log -S` on the finding's subject when relevant revisions are available. If retained evidence cannot establish why the finding recurs, report that uncertainty to the user before proposing structural rework; do not infer a structural defect or invent provenance. (History, 2026-07 / retired 2026-08-08 with BACKLOG #251: the old region-trending `spinning`/`FORK_*` layer once printed a re-seed for an 8-step plan whose "recurrence" was a bad fix from the previous round; the layer is gone, the judgment rule remains.)

**Stop auditing when findings stop describing the plan and start describing your last edit.** That is the real convergence signal; the count is a lagging proxy. Do not stop *applying* — leaving a known contradiction in is worse than the churn — but once the loop is auditing your edits, finish the application completely and go execute, where a mismatch becomes a failing test instead of a finding.
**Use three completed audit snapshots as the minimum trajectory window for session-directed convergence work.** One audit establishes a baseline; the second shows whether the applied correction moved the finding set; the third distinguishes a real trend from one-off reviewer variation. Compare stable finding identities and material severities across all three reports, not only their raw counts. A falling count is evidence to continue only when the remaining findings are becoming less material or narrower; a recurring high-impact finding, a flat material set, or a newly exposed architecture contradiction means stop patching and propose a scoped redesign or backlog direction. Three snapshots are a decision threshold, not automatic proof of convergence: finish only after the latest audit is clean/confirmed-low-yield under the applicable policy.

**Surviving interactive routes retain their own workflow.** For review/reconcile walks and structural-escalation confirmations, a human uses the interactive walk; an orchestrating session supplies judgment where the interactive path would skip or blind-apply.

**Commit before every `plan-tool` invocation, and prefer `--commit` where the verb accepts it.** Before launching `create`, `detail`, `completeness-audit`, `run`, or any other long-running plan-tool command, land a git commit of the working tree so the pre-call baseline is clean and the next call has a durable checkpoint to roll back to. Session-directed audit fixes use the same rhythm: apply batch → commit → re-audit (never audit against an uncommitted apply). Prefer the tool’s `--commit` flag on every surface that supports it rather than relying only on separate mid-command commits. `--commit` is **not** universal — only four surfaces accept it (`run`, `detail`, `completeness-audit`, and `manifest sweep`/archive); like `--iterate`, don’t tack it onto a command that doesn’t take it (`create`, `review`, `jira`, `verify`, `annotate`, …). On those four, pass it by default when you drive the pipeline. On `run` specifically, `--commit` commits each **green step**: that is load-bearing for the **test-authoring gate**, which isolates a step’s test coverage as the *post-call git-changed delta against a pre-call baseline* (`launcher.py`’s gate). Run steps back-to-back **without** committing and an earlier step’s files stay dirty, so a later step’s edits to a **file already dirty** (especially a shared test module like `tests/test_detail.py`) fall inside the baseline, get masked out of the delta, and the gate **wrongly blocks advancement** even though the step did author a test — the gate’s documented “known limit.” `--commit` clears the tree between steps and avoids it, and makes each step independently reviewable (see “Make commits meaningfully bounded”). This standing mandate authorizes those commits while you drive the pipeline; only when the user wants to withhold commits (e.g. to inspect first) do you omit `--commit` — and then advance **one step at a time**, committing separately under the bounded-commits rule before the next step or audit, so you never re-enter the masking trap. (`detail --commit` is also **per-step** — it commits each converged step as it lands, keeping an interrupted batch’s completed steps durable, BACKLOG #122; the remaining two verbs’ `--commit` — `completeness-audit`, `manifest sweep` — commit that verb’s own authoring/manifest edits, not per-step green commits.)

**Treat every `plan-tool` execution as long-running.** Do not interrupt, kill, or terminate a running `plan-tool` process because it is quiet or exceeds an expected duration. Continue monitoring and report progress; ask the user for explicit permission before stopping it.

**After a `plan-tool run` finishes a plan, drive plan-canonical code reconciliation and code review to convergence — green steps are not the finish line.** Once the last step is green (and committed — see the `--commit` mandate above), run a complete `plan-tool reconcile-code <name> --all` sweep (including `done` steps and excluding explicit `non-code` steps), save every report, then run a `/code-review` loop. `--dry-run` only renders prompts; its output is not a drift signal. Do **not** insert `completeness-audit` into this tail: it audits the plan's design and detail bundle, not the implementation. After three complete sweeps, apply the post-run reconcile-tail stop rule in `integrations/shared/DIRECTIVES.md`: verify the remaining property against code and existing tests, use focused fixes/tests or an explicit fail-closed capability deferral, and do not launch another full sweep on a model label alone. `/code-review` is a **Claude Code session activity, not a plan-tool surface**, so tool `Next steps:` blocks must only suggest `plan-tool …` commands.

**`reconcile-plan` is a *pre-execution* verb: never run it against work a `run` or `jira` execution already produced.** The two reconcile verbs are not interchangeable halves of one audit — they differ in **which side is canonical**, and that makes each one correct in exactly one direction of time:

- **`reconcile-plan` — code is canonical, and it mutates the plan.** Its legitimate use is **before** the plan is executed: the plan was authored against a codebase that has since moved on (a file renamed, a helper already built, a sibling plan landed), so the plan is re-grounded against what is actually there. `--refresh` is its cheap fingerprint-gated form for exactly this. Once the plan has been executed, use `annotate` (which never mutates its source) to judge it and seed the next iteration instead.
- **`reconcile-code` — plan is canonical, and it mutates the code.** This is the **post-execution** direction, and it is the one the post-run tail above names.

**Why the misuse is a hazard, not a style preference.** After a step runs, the code exists *because of* the plan. Point a code-canonical audit at it and the implementation is handed authority over the intent that produced it: whatever was built becomes, by definition, what the plan "should" have said. Under-delivery reads as an over-promising plan, and the audit's proposed remedy is to edit the plan toward the code. `prompts/reconcile.md` fences the worst of this — it refuses scope-narrowing and criterion-softening edits and routes a shortfall to a `status`/`status_note` flip instead — but the fence is a guardrail on a verb pointed the wrong way, not a licence to point it that way. The `status`-flip escape also does nothing for a step already marked `done` by a green run.

The sharp case: a plan/detail claim that is **false about the code** is *not* evidence for running `reconcile-plan` post-execution, even though it is superficially the matching direction. Correct it through a session-directed edit — read the code, correct the claim, and say in the text which way the discrepancy resolved. Example, 2026-07-29: [evidence](docs/evidence/claude-md-measured-incidents.md#6-a-code-canonical-audit-pointed-at-a-false-plan-claim-2026-07-29).

**Direct changes get the same convergence loop — don't one-shot them.** The `--iterate` pipeline gives plan-authored work an automatic correctness→completeness convergence loop; a change you implement *directly* (Edit/Write, outside the pipeline — e.g. building or fixing the tool itself) gets none unless you drive it through the session. After a direct apply, **loop: audit the change for correctness *and* completeness, fix what surfaces, re-audit until it converges** (no new findings). Each round re-run the affected tests and a review pass (`/code-review`) — correctness = sound + no bugs/edge-cases missed; completeness = every call site, case, doc, and test the change implies is covered. A one-shot direct edit is the same unconverged hazard `--no-iterate` is. Applies to any direct change landing in the codebase, including features added without going through `create`/`detail`/`run`. **Close the fix with the smallest change that makes the finding true, not the most general, complete, or reusable version of it.** `synthesize-body.md`, `detail.md`, and `plan-audit.md` apply the identical bias to an authored plan — a fixed check over a rule engine, one direct call over a pluggable interface, a literal over a config knob, even when the general version stays on-topic. Broaden the fix only when the finding itself cannot be closed without it, not because the broader version would be more complete or future-proof. Exit 3 below applies here too: stop patching and file the structural issue.

**A fix must close the invariant the finding is pointing at, not just the reported scenario — closing only the scenario can regress a case the original code got right.** A `/code-review` finding names one failing input, but the code usually encodes a small combinatorial space of precedence/config inputs (a flag, an env var, an inferred value — each present-or-absent and matching-or-not-matching some default). A fix that special-cases the reported input, instead of deriving the actual property the code must satisfy, passes its own new regression test while quietly breaking a sibling combination nobody re-tested — and because a `/code-review` convergence loop re-audits the *whole* diff each round rather than replaying the fix against a stated case matrix, that sibling regression surfaces as a fresh finding next round instead of at fix time. This is the same failure mode as this file's "check the remedy against the *goal*, not just against the finding" rule below (written for the conceptual-correction prose loop) generalized to session-directed code fixes, where it is more acute: each round's fix is verified only against the literal repro in its own finding. **Measured 2026-08-21:** one 3-line expression drew a different confirmed bug on 3 consecutive `/code-review` rounds, each fix backed by a new passing test, because no round stated the invariant or enumerated the combination space it depends on ([evidence](docs/evidence/claude-md-measured-incidents.md#7-a-fix-that-regressed-a-sibling-case-2026-08-21)). **A finding recurring at the same site with a *different* symptom each round is a stronger non-converging signal than the same symptom recurring** — it means the previous round's fix was the wrong shape, not merely incomplete, and the next round should enumerate the case matrix and pick a fix that is verified against all of it, not patch the newest reported cell.

**Verify a "this is a bug" finding against its existing tests before applying the fix — not only by tracing.** Static verification (reading the diff, checking commit history, tracing call graphs) can be internally consistent and still wrong, because it cannot see that an already-passing test pins the exact behavior the finding calls a regression. Before folding a `/code-review` (or session-directed completeness) finding into a batch apply, check whether the test file covering the claimed-buggy code (`plan_tool/X.py` → `tests/test_X.py`, per the Tests section's mirroring convention) already asserts the behavior the finding disputes; a passing test that pins it outranks a plausible static trace. This is the review-time form of the Tests section's "verify by mutation, never by reading" — same failure mode, checked at finding-confirmation time instead of test-authoring time. Measured 2026-08-14: 2 of 15 findings in one `/code-review` pass were false positives contradicted by an existing test ([evidence](docs/evidence/claude-md-measured-incidents.md#8-false-positives-caught-by-existing-tests-2026-08-14)). The full-suite re-run stays mandatory as the backstop for whatever this earlier check misses — this is a cheaper, earlier check layered on top of it, not a replacement.

**Severity-aware conceptual-audit stopping rule (BACKLOG #125).** Treat **two consecutive diminishing-return passes** as operational convergence when each pass adds either at most one new `low`/`info`/`nit` finding or adds only findings in those advisory severities. Report this as **low-yield convergence**, not a clean audit, and retain the advisory findings for later review. Any new in-scope correctness or completeness finding that remains material resets the streak; deterministic/data-integrity failures never qualify. Findings tagged `[out-of-scope-deferred]` must not reset the streak and must not justify raising the pass cap (prompt/operator convention until the sampler keys on the tag). Prefer `--audit-passes 1` for scope-contract-bound audits (CLI default remains `3`). Do not keep raising the pass cap merely to chase an unbounded tail of advisory prose precision after this two-pass condition is met. Conversely, a singleton tail is **not** converged merely because its count is one — severity is load-bearing. Label exits using the emitted coverage fields: `confirmation_kind=confirmed-dry` / `confirmed-low-yield`, `budget_limited=true`, or `recommendation_kind=non-converging`. The durable implementation, coverage metadata, and tests are tracked in BACKLOG #125. The audit loop uses the shipped calibrated impact-aware predicate: high-impact recommendations and high/critical severities remain blocking, while only evidence-qualified low-impact, medium-severity classes can be demoted.

**Keep driving audit rounds until one of exactly three exits fires — a falling
count is not one of them.** Each rule lives elsewhere in this file; this is the
index, so that a session driving the loop has one place to check rather than
four. Absent a different direction from the user, run the next round.

1. **Converged** — a clean audit, or the low-yield condition immediately above.
   Go execute.
2. **The loop is auditing your own edits** — new findings predominantly
   describe your last round's applications rather than the plan. Rule and
   rationale in § "Authoring plans with plan-tool" ("Stop auditing when findings
   stop describing the plan…"): do **not** stop applying, finish the
   application completely, then go execute, where a mismatch becomes a failing
   test instead of a finding.
3. **Non-converging** — the same finding or region resurfaces across rounds, or
   a fix needs structural rework you cannot land inline. Stop and surface it to
   the user, or file it in `BACKLOG.md` / `BUG_BACKLOG.md`. Before spending a
   re-decomposition on exit 3, trace the recurring finding's provenance
   (using the retained-evidence route above, with history optional): a finding that recurs because *your own last fix was wrong*
   is exit 2, not exit 3.

Distinguishing 2 from 3 is the judgment call, and it is made per finding, not
per round: classify each new finding as plan-defect or self-seeded before
reading the round. A round that is mostly self-seeded still contains real gaps
worth applying — measured 2026-08-04 on `roadmap-02-feedback-channel`, whose
round 3 was 3 of 7 self-seeded and whose remaining four included a `high`
third deadlock in the one gate no earlier round had touched.

## Convergence policy boundary

Three blocking predicates — keep them separate:

- `is_blocking(severity)` — pure severity floor (`medium`+); unchanged callers
  (e.g. `ConvergenceState.has_blocking_findings` on deterministic iterate state).
- `is_blocking_finding(rec, *, stage, classify_domain=...)` — **completeness-audit**
  conceptual bar only (`STAGE_BARE` / `STAGE_DETAIL`). At both stages, medium
  demotes only when `classify_finding_domain` resolves `"docs"`
  (`"code-logic"`/`"unit-test"`/`"unknown"` all block — only documentation is
  supporting information). Bare-stage `plan-completeness` medium is a
  separate, unconditional non-block; detail-grounded completeness is judged
  after the bundle is complete. Deliberately the same domain rule at both
  stages: a bare-stage `"unknown"` carve-out was rejected because bare-stage
  `plan-correctness` findings mostly describe plan-body soundness rather than
  files and would land in `"unknown"`, eroding its always-actionable
  invariant rather than filtering noise.
- `is_blocking_impact(rec)` — reconcile-loop blocking-state refreshes and
  conceptual-audit `material_new` only. `material_new` also accepts an
  optional `classify_domain` for the same `"docs"`-only demotion, kept
  stage-agnostic (that call site has no stage concept). Reconcile-loop
  callers deliberately omit it — they evaluate plan-vs-code drift findings,
  not conceptual audit findings, and doc-vs-code drift is that loop's job.
  **Out of scope** to widen the reconcile-loop calls for domain.

**`has_blocking_findings` dual use:** `ConvergenceState.has_blocking_findings`
is deterministic-only during iterate. Finalize, `--json`, and `--fail-on-findings`
use `_completeness_has_blocking_findings` with the hoisted audit stage and
`is_blocking_finding` on conceptual recs.

Use `convergence.is_blocking_impact(rec)` only for the shipped calibrated
impact-aware policy above. Historical calibration can demote only
evidence-qualified low-impact, medium-severity recommendation classes.
High-impact recommendations and `high`/`critical` severities remain blocking.
Completeness callers that use the `material_new` audit loop inherit that
deliberately narrow materiality rule — distinct from the completeness stage bar.

`arm-clustering` may use the settled material conceptual evidence from this
existing policy only to explain its non-blocking advisory. That use adds no
caller class, convergence gate, continuation rule, or dispatch path; it does
not alter completeness continuation, deterministic or reporting gates, prompts,
schemas, `Recommendation`, or `convergence_diagnosis.py` without separately
scoped work.

**Recommend-only convergence advisories** — same stance as `finding_churn` and
`structural_recurrence` on `ConvergenceDiagnosis`; diagnosis signals only:

- **`impact_recurrence`** — `classify_impact_recurrence` over collapsed
  completeness history; fires when the same still-open seam carries explicit
  `impact=high` across compatible passes without shrinkage; rendered via
  `_impact_recurrence_lines` on `plan-tool convergence` and completeness stderr
  when history qualifies.
- **`edit_drift`** — `classify_edit_drift` with `is_blocking_finding` at the
  window's persisted `audit_stage`; strict-majority of new edit-drift-eligible
  findings match the window-local prior-apply set; rendered via `_edit_drift_lines`
  on the same surfaces.
- **`bare_mechanism_findings`** — `classify_bare_mechanism_advisory` over the
  newest collapsed bare, run-grade completeness pass; identifies open
  mechanism-only `plan-correctness` findings that detail can own; rendered via
  `compose_mechanism_edit_drift_advisory_lines` on the same surfaces.

None of these advisories feed `should_continue`, `ConvergenceState.has_blocking_findings`,
`_completeness_has_blocking_findings`, `--fail-on-findings`, or exit codes;
none revive `spinning` / `FORK_*` / `recurring_regions`; `self-seeded-finding`
in `audit_shapes.py` stays `judgment_only` (edit-drift complements it, does not
gate on it); impact-recurrence does not use `is_blocking_impact` for eligibility.

Keep `partition_findings_for_triage` separate from convergence: a deferred
finding does not by itself require another reconcile iteration.

## Authoring hygiene and anti-creep

**Feed `create` a seed file via `--from-existing <path>`, not an inline `--from` string.** Write new plan briefs under `docs/implementation-plans/plan-seeds/` (existing root-level `plan-seeds/` files stay in place) and pass it with `--from-existing`. Reserve `--from` for short, throwaway one-liners. A seed file is reviewable, diffable, and re-runnable; a long inline `--from` is none of those and gets truncated in shell history. **`SEED_FORMAT.md` is the authoring directive doc for seed content** — maximize semantics per token, one seed per effort, name destinations rather than turn-by-turn construction, and always state an explicit scope-contract fence. Follow it when writing or editing seeds in either directory.

**Audit a seed at seed altitude before `create`; do not demand a finished plan from it.** Review its claims against the live code and source backlog, fix every material correctness problem, and re-review until the correctness set converges (or explicitly record a low-yield/advisory tail). Completeness is deliberately narrower here: raise only a **HIGH** or **CRITICAL** omission that contradicts the seed's Outcome or scope fence, leaves a settled decision without a necessary counterpart, or makes a coherent plan impossible to derive. Do not expand a seed with ordinary implementation edge cases, per-step mechanics, fixture matrices, file lists, or wording polish just because a later plan/detail audit would eventually examine them. Those are absent by design and belong to `create`, `detail`, or their grounded audits. A seed is ready when its intent and constraints are correct and no serious conceptual hole prevents decomposition — not when it has exhausted the completeness vocabulary of a finished plan.

**Backlog-derived seeds must carry backlog reconciliation forward.** When a seed is produced from a `BACKLOG.md` or `BUG_BACKLOG.md` item, name the source entry (and, once the lead has promoted it, its Jira ticket key) in the seed and include an explicit requirement that the resulting plan updates the originating backlog file when the work ships. The plan should usually put that bookkeeping in its final docs/status step and acceptance criteria: remove the shipped entry (for a promoted item, its promotion stub — `docs/TRACKING.md` § "Promotion stubs") only after full shipment, mark an unpromoted entry as plan-authored while execution remains pending, or leave/update any deferred follow-up that remains. Authoring the plan alone does not remove the entry. This requirement belongs in the seed/plan content, not in an operator's memory, so it applies the same way through the `claude`, `codex`, and `cursor`/`agent` backends. A backlog-derived seed also **inherits the source entry's full scope contract** (Outcome, In scope, Out of scope / Non-goals, Allowed behavior changes, Allowed reorganization, Verification, Stop / defer — see the [Scope contract and anti-creep](docs/TRACKING.md#scope-contract-and-anti-creep) in `docs/TRACKING.md`); for a promoted item its ticket holds that contract and the seed carries a copy. The seed elaborates that contract rather than inventing a different fence. Completeness audits must stay inside that contract; valid out-of-scope findings are deferred to the backlog files, never auto-applied as plan expansion.

**Route out-of-scope findings to the backlog files, not standalone findings docs.** When the iteration/scope-guard loop surfaces a finding outside the plan's declared scope, file it in `BUG_BACKLOG.md` (things the code does wrong) or `BACKLOG.md` (forward-looking work) per the decision rule in `docs/TRACKING.md` — do **not** drop a one-off `docs/implementation-plans/N-out-of-scope-findings-*.md` stub (`steps: []`). Those stubs fall outside plan discovery, never converge, and rot; a backlog entry is triaged top-down and removed when fixed. If a findings stub already exists, resolve or migrate its findings into the backlog and archive the stub.

**A consolidation opportunity you notice while doing something else is an out-of-scope finding — file it, don't take it.** Duplication is discovered *incidentally*, almost always mid-task: you open two modules for unrelated reasons and see the same helper twice. Folding it in on the spot is scope creep with an unusually good disguise, because "while I'm here" feels cheaper than it is — the merge needs a home decision, a call-site sweep, a leaf/cycle check, and its own tests, none of which the current task's Outcome covers. Write a `BACKLOG.md` entry instead and keep going. A scratch note is **not** filing it: `.tmp/` is transient by definition, so a consolidation recorded only in a handoff doc is lost at the end of the session.

**A consolidation entry must carry machine-verified evidence, never a resemblance.** This is the expensive failure mode, and it is measured: when BACKLOG #79's five claimed duplicates were finally checked with an AST pass that normalizes docstrings, function names, and parameter names, **four of them were wrong in the direction that breaks things** ([evidence](docs/evidence/claude-md-measured-incidents.md#9-consolidation-claims-checked-by-ast-backlog-79)). Prose like "byte-identical" and "verbatim copy" in an existing entry is a **claim to re-verify, not a fact to act on**. So every consolidation entry states:

- **how identity was established** — the normalization used, and the count it produced. Name-and-eyeball is not evidence; a pair whose bodies differ only in parameter names will not group under a naive comparison, and one that differs only in *placement* of a local `import` also will not.
- **the do-not-merge look-alikes it deliberately excludes, each with its reason.** This half is load-bearing and is the half that gets skipped: the excluded set is what stops the *next* reader from "finishing the job". Say why each is separate — a test seam (`shell_*_invoker`, six identical bodies that are the invoker seam `tests/conftest.py` overrides per orchestrator), a pinned external contract (`backend.py`'s batch/streaming argv pairs), a differing durability or failure policy, or a flag whose name matches while its meaning does not (`suggest-gates -y` selects report-instead-of-prompt, so the shared help text would be a false claim).

Two identical bodies tell you where to look; they never tell you the remedy. Landed 2026-08-02 across three same-file duplicates, each needing a *different* fix: one was a genuine helper pair, one was two nested closures wanting a factory, and one was a subclass redundantly overriding a concrete base method — where the correct action was to delete the override, not extract anything.

**How this squares with `tests/test_duplication.py`, which fails on a new duplicate.** The two govern different things and the line is clean: **this rule is about duplication you *find*; the test is about duplication you *add*.** The guard's baseline is zero and it is enforced on every run, so a failure is necessarily duplication introduced by the change under test — never a pre-existing pair you walked past. Declining to add a second copy of a helper that already exists is not scope creep; it is not creating the debt. And the test **never requires the merge**: `ALLOWED_DUPLICATE_GROUPS` is the supported answer when consolidating would pull an unrelated change out of shape — record the reason there, file the consolidation, keep going. The one case that genuinely rubs is a change that makes two *pre-existing* helpers coincidentally identical; the allowlist is the intended exit there too, not a merge.

**Name `.tmp/` scratch files specifically — never generic.** `.tmp/` (gitignored) holds transient scratch: session handoffs, notes, captured command logs, staged copies. Prefix every file with the feature/plan slug or task it belongs to (e.g. `decomposition-convergence-loop.schema-contract.md`, `decomposition-convergence-loop.create-run.log`), not bare names like `notes.md`, `output.log`, or `tmp.json`. Specific names make collisions across concurrent tasks impossible and let cleanup target one feature's leftovers (`rm .tmp/<slug>.*`) without guessing what a generic file was for.

**Commit completed atomic actions.** After a user-directed atomic action is implemented and verified, commit its focused change before reporting completion — no separate "commit" request is needed. Preserve unrelated working-tree changes, do not combine independent concerns, and leave the work uncommitted only when the user explicitly asks to inspect or defer it. A commit does not authorize a push, PR, or other publication.

**Make commits meaningfully bounded.** Split each commit into one logical, self-contained concern, independently reviewable and, where practical, green on its own. Separate distinct concerns even when they ship together: e.g. a plan/doc/backlog change in one commit and the code change it motivates in another, or a refactor apart from the feature built on it. Prefer several scoped commits over one sprawling commit; group by intent, not by file type, and write a subject that names the one concern. A commit that touches many areas for unrelated reasons is the smell to avoid.

## Audit the why, not the what — and a fired shape is a scope decision, not a nag

**Read this before applying any audit finding.** Every expensive audit mistake in this repo has one shape: **the mechanism stays correct while the purpose goes unserved.** Findings get *applied* instead of *interpreted*.

**This section is one half of a two-sided test: true to intent, and proportional to intent.** A mechanism has to be checked against the plan's stated intent from both directions, and neither bound makes sense stated alone. *True to intent* — this section's whole subject — means the mechanism actually makes the intent hold; a finding can be applied everywhere and still leave the purpose unserved, which is what the rest of this section is about. *Proportional to intent* is the other bound: the mechanism is no bigger, no more general, no more configurable than that same intent requires. That half lives in `synthesize-body.md`, `detail.md`, and `plan-audit.md`'s paired proportionality/mechanism-axis rules, and in this file's own session-directed-change rule above. A correct-but-disproportionate mechanism is scope creep with a clean audit trail; a proportionate-but-untrue one is exactly the failure this section names — check both, not whichever one the finding in front of you happens to raise.

**Why it recurs, and why it is structural rather than carelessness: validity is local, necessity is global, and only validity is visible from inside the loop.** A finding is judged against the artifact in front of it, so it can be entirely right about a thing that should not exist. No lens asks whether the step it names belongs. If the session does not ask, nothing does.

**The override rule — this is the load-bearing part.** When one of the shapes below fires, it is a **scope decision**, and the standing rule for scope decisions applies: **surface it to the user rather than self-adjudicating it.** Concretely, you may not proceed to apply findings until you have, *in the user-facing response*:

1. named which arm/step the findings cluster in, with the count;
2. stated why that arm belongs — or proposed carving it;
3. said plainly that you are overriding the signal, if you are.

A silent override is the defect. "I noted the warning and continued" is exactly what happened the one time this was measured, and it cost six rounds. Treat a fired shape the way you would treat a failing test you intend to skip: allowed, but never quietly.

**The six shapes.** Each means *stop and re-ask*, not *fix and continue*.
The following is the complete, ordered, tool-owned representation of the
registry; only this marked table is checked for documentation drift.

<!-- plan-tool:audit-shapes -->
| id | tell | classification |
| --- | --- | --- |
| `arm-clustering` | Material conceptual findings form a strict-majority, contiguous proper arm of committed plan steps | `checked` |
| `check-saturation` | Every part is correct but no producer delivers the intended value | `judgment_only` |
| `measurement-instrument-adequacy` | A measurement instrument cannot see the data on which a decision relies | `judgment_only` |
| `self-seeded-finding` | Findings describe the prior audit edit rather than the artifact | `judgment_only` |
| `remedy-proportionality` | The proposed remedy outgrows the defect | `judgment_only` |
| `premise-conditioned-design` | A step's design differs by the outcome of an investigation the same plan contains | `judgment_only` |

`arm-clustering` is the only shipped **audit-shape** advisory. Recommend-only
`impact_recurrence` and `edit_drift` signals live on `ConvergenceDiagnosis` (see
**Convergence policy boundary**). `arm-clustering` uses already-settled
material conceptual-finding evidence to present the concentrated proper arm
and ask whether it belongs or should be carved. The advisory is not a software
gate, does not select an apply target, and does not change ordinary finding
dispatch. The override rule above remains separate: an operator who elects to
apply conceptual findings must still surface the scope decision to the user.

**What the shipped advisory cannot see — do the count yourself.**
`evaluate_arm_clustering` returns an advisory only when *all* of: ≥3 material
findings; every one carrying a **single consensus target across ≥2 audit
samples**; and a gap-free **proper** arm covering a strict majority of
**committed steps** *and* of material findings. Three consequences, each
observed 2026-08-04 on `roadmap-02-feedback-channel`:

- **`--audit-passes 1` disables it outright** — one sample can never yield a
  consensus target, so `advisory_invalid` is set and nothing is computed. That
  is the pass count § "Severity-aware conceptual-audit stopping rule" *prefers*
  for scope-contract-bound audits, so the recommended setting and the only
  shipped detector are mutually exclusive by construction.
- **A one-step concentration can never fire it**, because the arm must also be
  a step majority: 9 of 15 correctness findings — and all five HIGHs — naming a
  single step of ten returns `None`, not an advisory.
- **A `detail` completeness tail computes none either**, having no multi-sample
  evidence.

Silence from the detector is not evidence the tell is absent, and a single
over-packed step is the *common* shape. Attribute the findings explicitly — the
persisted recommendations carry no `step_id`, so read which step each finding
names as the side to fix — before you apply anything.

**Present plan gaps before making a scope decision.** Use this format for
in-scope, plan-level audit gaps: findings whose remedy could change the plan
body, step graph, acceptance criteria, or stated contract. The raw audit list is
ordered by source and severity, which can hide that several plan gaps describe
one contract or one contiguous arm. Before applying those gaps or asking the
user to override a shape signal, group them by the responsibility they describe.
Start with `Plan intent:` and one short, faithful restatement of the plan's
stated intent. Then present a compact map with these columns:

| Related findings | Relevant steps and intent | What happened | Possible next step |
| --- | --- | --- | --- |
| source, severity, stable anchors, and a short neutral finding label | named step ids/titles plus each step's intended outcome in short plain language | a direct conversational summary of the relationship between the findings and the plan | a suggestion to review, clarify, apply, defer, carve, or otherwise investigate — not a decision for the user |

- **Keep non-plan output separate.** Do not force deterministic diagnostics,
  detail-only implementation mechanics, out-of-scope suggestions, or audit
  telemetry into the plan-gap map. Present them separately when they matter,
  with the context needed to understand them.
- **Group by responsibility, not phrasing.** Findings with different anchors or
  sources can still describe one shared result contract; conversely, repeated
  wording can name independent responsibilities. State that connection plainly.
- **Attribute plan-level findings explicitly.** Saved recommendations can have no
  `step_id`; map them from their cited step title, file, acceptance criterion, or
  architecture concept. Mark an uncertain target rather than silently assigning
  it.
- **Restate intent as a scope anchor.** Quote or faithfully summarize the plan
  intent before the map, then state the intended outcome of every step named in a
  row. This gives the reader enough context to see whether a finding serves the
  plan or has drifted into adjacent work. Do not infer an intent the plan does not
  state; say that it is not stated. This is presentation and scope context, not
  permission to re-audit or weaken the plan's settled intent.
- **Add an arm assessment under the table.** Give the contiguous affected steps
  as `N of M`, the material findings in that arm as `N of K`, and say whether the
  group is one coherent contract with its consumers or an accidental feature arm
  that should be carved.
- **Explain what happened, not what it means.** Preserve the auditor's source,
  severity, and anchors, but do not add role labels, status labels, blocking
  declarations, or a verdict such as “ready” or “not ready.” Explain the facts
  in short conversational language, then offer a possible next step.
  The user decides its priority, meaning, and disposition.
- **Keep this advisory.** The map improves the human scope discussion; it is not
  a new gate, does not force a split, and does not choose an apply target. If it
  reveals a credible arm, use the override rule above and surface the choice to
  the user even when the shipped detector was silent.

**Measured 2026-08-02/03 on `intent-required`.** Round 2 returned 17 findings and **12 of them, including both HIGHs, named one arm** — a gated apply path to write an intent into an existing plan through the review/reconcile walk. Every one was individually valid, which is what made it insidious: applying them felt exactly like converging. Carving that arm (10 → 8 steps) removed most of the finding surface. The user ended it with one sentence — *"this should be a very simple thing"* — which is the question the audit loop structurally cannot ask.

**The remaining five shapes are judgment-only and must stay judgment.** In
particular, a detector for "this remedy seems too big" is the ~85%-false-positive
prose-conformance trap in § "Withdrawn: the per-`change_type` test-ordering
contract", where the governing rule is *a high false-positive rate means kill,
not tune*. Raising the *stance* on these shapes means raising the cost of a
silent override — **never** converting them into gates or exit-code flips.

**Four readings the table's one-line tells do not carry.** Each is how the
shape behaved in practice; none changes the registry.

- **`self-seeded-finding` is a *rate sustained over rounds*, not a per-finding
  fact.** Read literally, the tell is true of one or two findings in nearly
  every round — that is ordinary application debt, and the response is to
  finish the sweep. The signal is a **majority, held for two or more
  consecutive rounds**: measured 2026-08-04 on `roadmap-02-feedback-channel`
  at roughly 3 of 7, 4 of 5, then 8 of 10 across rounds 3–5, which is exit 2
  in § "Severity-aware conceptual-audit stopping rule" — stop auditing,
  finish applying, go execute. One instance and a sustained majority call for
  opposite actions, and the tell alone cannot tell them apart.
- **`remedy-proportionality` fires on a *verdict*, not only on a finding — and
  that is the more dangerous producer.** Both measured instances (2026-07) were
  a deterministic diagnostic's remedy rather than an auditor's: the since-retired
  region-trending layer (BACKLOG #251, cut 2026-08-08) printing
  `FORK_STRUCTURAL` (re-seed and re-decompose) for `roadmap-01` at round 6, and
  again for `roadmap-02-feedback-channel` at rounds 4–5 against a 10-step plan
  whose decomposition five rounds had never challenged. Both times the true
  cause was bookkeeping misses in the previous round's own fixes. A tool
  verdict reads as authoritative and arrives with a runnable command, which is
  exactly why the provenance rule above exists — that rule is an instance of
  this shape, not a separate precaution.
- **`check-saturation` firing does not imply carving.** "No producer delivers
  the intended value" reads as though the arm should go, and sometimes it
  should — but *specifying the interaction* is an equally valid answer. On
  `roadmap-02-feedback-channel` round 1 the shape fired correctly (three
  findings showed the revision stage with no legal move, every gate rule
  individually correct), the interactions were specified rather than carved,
  and five further rounds never challenged the decomposition. The shape means
  *stop and re-ask*, which is what the section head already says; it does not
  name the remedy.
- **`premise-conditioned-design` turns on what the investigation's outcome is
  allowed to *change*, not on whether the plan contains one.** Front-loading a
  risk check is healthy and must not trip this. The line: a gate whose arms
  differ only in **verdict** — halt or proceed, downstream design identical
  either way — is fine; a gate whose arms name different **artifacts or
  mechanisms** is the shape, and its dependents are unauthorable until it runs.
  The one-line rule is *an investigation belongs inside a plan only when its
  result cannot change what the plan builds*. Measured 2026-08-05 on `example-app-amplify`'s `assessment-service-dynamic-people-types`: four audit rounds went 17 → 16 → 25 → 30 findings, correct every round, because a contradiction between two hypothetical arms is unfalsifiable — you satisfy the finding by elaborating either arm — while one ~10-minute throwaway script settled the premise ([evidence](docs/evidence/claude-md-measured-incidents.md#10-a-premise-conditioned-design-2026-08-05)). **Do not build a detector for this** — a healthy go/
  no-go gate and a design-determining one use identical words, so any matcher
  over conditional prose measures vocabulary (§ "Withdrawn: the
  per-`change_type` test-ordering contract"). Expect no help from
  `plan-tool convergence` either; on this shape it reported `converging` while
  findings rose 25 → 30 (BUG_BACKLOG, "`convergence` reads `converging` when
  findings churn without recurring").

## Validating a semantic property you cannot observe

**When a feature's value is semantic — "the tests really cover this", "the work
has a real why", "the doc is accurate" — assert only a binary fact about state,
deliver the rest, and enumerate what may *not* be checked.** This class has
produced two expensive efforts here. Treat a third proposal as guilty until it
names its observable.

**Why the class inflates, where ordinary features don't.** A normal feature's
scope is bounded by *the thing working* — a parser stops when it parses. A
validation feature's "working" is unfalsifiable, so **no test fails when you
have done too much**. Two multipliers ride on that. Every surface that cannot
see the new signal reads as a gap, and the consumer set is *open*
(detail → run → jira → audit), not closed like a bug fix's. And because the
artifact is prose, each added rule gets restated across N documents where every
restatement can drift — so finding-churn grows superlinearly in rules, and the
audit thrash is a symptom of the domain, not of the workflow.

**What survived, both times, is a binary fact a machine can see:** the withdrawn
test-ordering contract (below) kept `enforce_step_tests` — *a test file was
created or modified*; the intent scope fence kept *the `intent` field is
present*. Neither claims anything about meaning.

**The rules.**

1. **Name the binary observable; ship only that.** If you cannot state it in one
   sentence, there is no feature yet.
2. **Deliver, don't verify.** Put the information in front of the human or model
   and stop. Threading is the guard; checking is not.
3. **Enumerate what may *not* be checked** in the seed's scope fence — quality
   judgments, agreement checks between two prose artifacts, shape or length
   caps, any gate or exit-code flip (one carve, below). A principle stated in
   the prose does not hold. Observed 2026-08-01: `2-intent-scope-fence.md` said
   *"the guard is threading, not checking"* in its own Architecture and still
   grew to eleven steps, three consumers, five templates, and a length cap.
   Only the enumerated not-allowed list stopped it.
4. **"Consumer X cannot see it" is out of scope by default.** The burden is on
   including a consumer, never on excluding one.
5. **A high false-positive rate means kill, not tune.** A proxy that fires on
   cases which are legitimately fine is measuring vocabulary, not the property.

**The two intent reversals — settled, explicit user decisions; do not reopen.** 2026-07-31: `2-intent-scope-fence.md` shipped a plan-altitude `Plan.intent` and an advisory presence check (BACKLOG #206, since deleted — cite this record). 2026-08-02: `2-intent-required.md` lifted exactly one "Not allowed" bullet — a gate keyed on an intent — **only for presence**: a missing intent is a `medium` self-consistency finding that blocks completeness convergence, and the exit-code convention is untouched. The other four bullets stay refused, and everything past presence is permanently refused: a finding proposing one is invalid, not deferrable. Full record: [evidence](docs/evidence/claude-md-measured-incidents.md#11-the-two-intent-reversals-2026-07-31-and-2026-08-02); long form in `docs/implementation-plans/2-intent-scope-fence.md` and `docs/implementation-plans/2-intent-required.md`.

**The carve those reversals earn, stated once rather than hedged into each
rule:** gating the **binary observable** is allowed once the finding carries a
remedy an operator can actually run; gating the **semantic property** stays
refused. Rules 2 and 3 narrow that far and no further.

**Provenance.** Two instances: the per-`change_type` test-ordering contract
(2026-07-30, below) and the intent scope fence (2026-08-01), carved from eleven
steps back to five once the Outcome was restated as "make sure the intent is
part of the conversation; we cannot validate more than that it is there."

## Withdrawn: the per-`change_type` test-ordering contract (2026-07-30)

**Do not reintroduce a test-*ordering* contract keyed on `change_type`, and do not "fix" the tool to check one.** This was tried, measured, and removed; the removal is the settled answer, not an oversight.

**Why it went.** Replaying every `refactor` step in this repo's history showed the contract is satisfiable only for refactors that preserve the test-visible interface, and most do not: 25 of 28 conclusive replays (89%) would have fired. A checker that validates prose conformance to an unsatisfiable contract reads as rigor and delivers none, and at that false-positive rate the finding channel becomes noise operators ignore. What existed, the replay method, and the full numbers: [evidence](docs/evidence/claude-md-measured-incidents.md#12-the-test-ordering-contract-withdrawal-2026-07-30).

**What is enforced now, and it is the honest line.** Both code types share one directive — cover the behavior the step changes, green before it finishes — and the only *checked* claim is `enforce_step_tests`' gate: a test file really was created or modified (`_step_requires_test_authoring` + the post-call git delta). Ordering is unobservable after the fact; test-file authorship is observable, so that is what the tool asserts.

**Deliberately kept.** `change_type` itself is load-bearing elsewhere and was **not** touched: the test-authoring gate keys on it, `granularity.py` uses REFACTOR-with-dependent-FEATURE for MIXED-STEP split advice, and `review.py`'s test-strategy check keeps its classification-consistency nudge and its non-code-footprint contradiction. Only the ordering directive and its prose matcher were removed.

**Evidence.** The [measurement record](docs/evidence/claude-md-measured-incidents.md#12-the-test-ordering-contract-withdrawal-2026-07-30) gives the replay method, sample limits and result supporting this settled withdrawal. Cite that record when evaluating a proposal to restore test-order enforcement.

## Machine-parsed finding annotations are heading-anchored sub-blocks, not inline trailing markers

**When a `Recommendation`-producing prompt needs an optional annotation on a finding (a targeted fix, a restatement, a redirect), give it its own heading-anchored sub-block — `### <Name>`, immediately after the bullet, mirroring the existing `## Redirect` convention (`parse_redirect_block`) — never an inline trailing marker (`→ label: …`) parsed by position.** This is the project-local record of the owner's personal user-level `CLAUDE.md`'s general "mark the boundary structurally, not positionally" rule; that file carries the principle and the measurement, this entry carries the local specifics.

plan-audit.md's bare-step restatement (`### Restated` / `### Fix`, parsed by `_split_audit_restated_and_fix` in `review.py`) is the shipped example. It replaced an inline `→ restated:`/`→ fix:` design that two code-review rounds broke in succession, because nothing in an inline marker is distinguishable from ordinary prose except its position; a heading that must start its own line cannot be produced by *inline* quoted prose.

**Fence handling.** A verbatim multi-line citation can still contain a genuine line-starting heading, so `plan-audit.md` wraps a verbatim citation in a fenced code block (4+ backticks when the cited text contains its own triple-backtick sequence) and `_split_audit_restated_and_fix` excludes any heading match inside a fenced span, and excises fenced text from a captured value, using `plan_tool/review.py:fenced_spans()` — the repo's one line-based fence scanner (length-matching per CommonMark, tilde-aware, CRLF-safe, an unclosed fence spans to end-of-text). **Do not write a second fence recognizer:** a regex fence-matcher is exactly as positional as the heading matcher it protects unless it is actually correct. Accepted residual risks, both prompt compliance rather than code enforcement: an un-fenced citation containing a real heading line (pinned by `tests/test_review.py::TestCheckPlanAudit::test_unfenced_citation_containing_a_real_heading_line_is_a_known_residual_risk`), and a same-length nested backtick run closing a citation fence early. Rounds 4 and 5, and the five ways the round-4 regex was defeated: [evidence](docs/evidence/claude-md-measured-incidents.md#13-fence-recognition-for-machine-parsed-sub-blocks-rounds-4-and-5).

`_split_audit_fix`/`_PLAN_AUDIT_FIX_MARKER_RE` (the original inline `→ fix:` marker) remains live for the reconcile-family prompts (`detail-reconcile` / `run-reconcile`), untouched by the sub-block redesign. The same round 4 also found its "single marker, so order-safety doesn't matter" rationale was wrong on two counts, both fixed directly in the marker function rather than by migrating reconcile to sub-blocks: it used `.search()` (leftmost match) despite the marker being trailing by contract, so an earlier fix-shaped occurrence — plausible in this self-hosting repo, since a reconcile finding can legitimately discuss `review.py`'s own marker syntax — won over the real trailing one; and it now also excludes matches inside a fenced span, as cheap defense-in-depth, even though reconcile prompts carry no mandatory-verbatim-citation requirement and so are not asked to fence. Do not migrate reconcile to sub-blocks preemptively beyond this; if a reconcile prompt ever gains a second marker, re-apply this same rule then, not before.

## Architecture

**Do not reach for parallel processing to optimize this tool — with one carve-out (below).** The real axis is **not** serial-vs-parallel; it is **shared mutable state + concurrent merge-back** (the expensive, discouraged shape) vs. **fully-segregated process-level parallelism with no shared store and no live merge** (the acceptable shape). Judge every parallelism proposal on that axis, not on whether it's "concurrent."

*The discouraged shape — in-process fan-out over a shared substrate.* Concurrency here is the single heaviest source of accidental complexity in an already dense codebase, and the app is deliberately **serial by default**. Every such surface that exists (`detail --jobs N` / `parallel-detail-authoring`) drags in a stack of machinery that has to be kept correct forever, and nearly all of it exists to make concurrent workers safe against **one shared substrate**: a `ThreadPoolExecutor` dispatch, per-worker **isolated git worktrees** off HEAD sharing one object store/index (→ the clean-tree gate, the "can't check out the same branch twice" rule), a process-global rate-limit prompt lock, B1-style per-worker **failure isolation**, and a **serial deterministic-order replay tail** merging workers back onto one canonical plan/manifest/run-log. That is a large, permanent tax for a **pure wall-clock** win that buys **no token savings and no correctness** — the calls were already independent, they just finish sooner. **This is discouraged, not forbidden — treat it as a last resort, not a first reach.** When something is too slow, exhaust **cutting work** first: skip unchanged units (fingerprint/cache gates), spend no Claude on the no-drift path, tighten prompts, or remove redundant re-parses/re-builds — a deterministic serial speedup, not a concurrent one. Only once those are genuinely spent, and a hotspot is still serial-bound and hurting, does in-process fan-out come back onto the table — as a deliberate, justified exception. Treat the existing `--jobs`/shared-worktree machinery as **maintain-by-default, extend-only-as-a-last-resort**: keep it working, prefer not to add new concurrency, new `--jobs` surfaces, or new parallel fan-outs, and don't port the `ThreadPoolExecutor`/replay-tail pattern to another phase on a whim — but the door stays open when the case is real and made explicitly.

*The acceptable carve-out — coarse-grained parallelism across fully-isolated clones.* A **full repo clone** (the `--clone` full-isolation opt-in, contrast the shared-store worktree) removes the entire substrate the tax pays for: independent `.git`, independent index, independent `.plan-tool/` state, independent branch namespace. Orchestrating several plans' `create`/`detail`/`run` **across independent clones** is not the discouraged shape — there is no canonical tree to merge onto (so no replay tail), no shared index (so no clean-tree gymnastics), only coordination at the **spawn/collect boundary**, not per-unit. This is acceptable — it is the process-level analog of running N terminals — **provided the isolation stays total**: no shared `.plan-tool` state dir, no shared manifest, and results are merged back through a **separate deterministic (or human) step, never a live concurrent merge**. The moment a design reaches back for shared mutable state or a concurrent merge-back, it collapses into the discouraged shape and the "but they're clones" framing must not paper over it. Two resources remain genuinely shared even across clones and are coordinated **at the orchestrator edge, not as per-worker machinery**: the **token / rate-limit budget** (N clones multiply peak 429 pressure like `--jobs N` does) and any **shared push remote** (branch/push collisions).

A genuinely serial-resistant in-process hotspot is the rare exception where fan-out *is* warranted — the door is open, but going through it is a **structural decision that needs explicit user sign-off** (name the complexity cost, the measured wall-clock win, and why cutting work can't get there), never a default optimization you reach for on your own. This directive sets the **burden of proof** on any backlog item proposing in-process parallelism as a speedup — re-triage such items against it (cut-work first, then justify), rather than implementing them by reflex; it is a high bar, not a veto.

**CLI layering (`plan_tool/cli/`).** Handlers here are *thin*: `app.py` is the entry (`main()` + dispatch + error UX), `parser.py` assembles argparse, and one module per intent group (`authoring.py`, `run_cmd.py`, `review_cmd.py`, `completeness_cmd.py`, `jira_cmd.py`, `gates_cmd.py`, `inspect.py`, `manifest.py`, …) wires args to orchestrators. The real work lives in the top-level orchestrators: `create.py`, `detail.py`, `launcher.py` (run), `review.py`, `completeness_report.py`, `jira.py`. One exception to "the CLI layer stays thin": `cli/completeness_phases.py` is itself an orchestrator (not a thin handler) that `completeness_cmd.py` calls into — it owns the `--iterate` convergence loop specifically to keep `completeness_cmd.py` thin; see `docs/ARCHITECTURE.md`'s "Completeness orchestration" entry. Leaf helpers (`console.py`, `context.py`, `reconcile.py`, `review_actions.py`) hold no business logic.

**The invoker seam (most important thing to know).** Every function that shells out to Claude takes an `invoker=`/`claude_invoker=` kwarg defaulting to a real-CLI shell-out (`shell.py`, e.g. `shell_claude_invoker`, `shell_detail_invoker`, `shell_review_invoker`). Tests MUST override these or stub the module-level proposal functions — otherwise they silently spawn the real `claude` binary (slow, non-deterministic, burns tokens). `tests/conftest.py` installs an autouse gate that *raises* if any registered backend binary is spawned; opt out only with `@pytest.mark.allow_real_claude`. TESTING.md has the seam-by-seam neutralization table — keep it current when you add an orchestrator with a real-backend default.

**Cycle-free import constraints, in one place.** These are the edges a change must not add; the modules themselves are described in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

- `backend.py`, `rate_limit_loop.py`, `telemetry.py` — **stdlib-only leaves** below `shell`/`launcher`; no first-party imports, so they form no `shell`↔`launcher` edge.
- `git_state.py` — a leaf below `shell`/`launcher` whose only first-party import is `rate_limit_loop` (itself stdlib-only). It owns the working-tree read **and** the partial-mutation retry guard both backend callers pass to the recovery loop; neither may re-implement either half locally, which is how the batch path drifted onto an unconditional always-retry.
- `backend_runner.py` — a leaf below `shell`/`launcher` whose only first-party imports are `plan_tool.backend` and `plan_tool.run_log` (both stdlib-only at module level). It owns the streaming Popen supervisor (`run_streaming_once`: spawn, stream pumps, heartbeat, silence-kill ladder) and the console-verbosity state; `launcher._run_streaming_once` is a thin wrapper that supplies the active backend's `streaming_transport`, kept for the monkeypatch seam and `cli/app.py`'s verbosity re-exports.
- `granularity.py` — imports only `schema.py` and `review.py`'s finding primitives; `review` never imports `granularity` (the one-way edge is what keeps it acyclic).
- `convergence_diagnosis.py` — imports only `review_persistence`, `review`,
  `locator`, `convergence`, `granularity`; never `plan_tool.cli`.
- `telemetry_analysis.py` — may depend on established read-only sibling leaves but must not import `plan_tool.cli`.
- `audit_shapes.py` — a leaf; audit-flow and persistence consumers import it, never the reverse.
- Roadmap's artifact leaves — `roadmap_artifacts.py` → `roadmap_gates.py`, with `roadmap_seed_state.py` as the stdlib lifecycle leaf and `roadmap_seed_manifest.py` importing artifacts, gates, and seed state to classify drafts. `roadmap.py` (stage execution) and `roadmap_view.py` (read-only rendering) remain independent branches above those leaves; `roadmap_html.py` (the `--view html` page) sits above `roadmap_view.py`, importing it, `roadmap_artifacts.py`, and `roadmap_er.py` and nothing else first-party; `roadmap_er.py` (the domain section's ER diagram) is a stdlib-only leaf with **no** first-party imports at all, taking a resolved description of what to draw rather than roadmap types, so resolution stays in one place and geometry in another; `cli/authoring.py` consumes the manifest classifier. Roadmap content resolves only through immutable accepted-head versions, and `ROADMAP_FORMAT.md` owns that lifecycle; `roadmap_stage_resume.py` (the first-run resume directory) and `roadmap_index.py` (the generated `INDEX.md`) are leaves below `roadmap.py`, which imports them. No edge runs `roadmap.py` ↔ `roadmap_view.py`, and none runs `roadmap_view.py` → `roadmap_html.py` or `roadmap_er.py` → anything first-party — those edges are one-way by design, so the text views never depend on the HTML one and the diagram never depends on the roadmap schema.
- `roadmap_decision_settlement.py` — a leaf whose first-party imports are exactly `checkpoint` (stdlib-only canonical hash), `roadmap_artifacts`, `roadmap_escalation_selection`, `roadmap_feedback`, `roadmap_feedback_ledger`, `roadmap_source_identity`, and `roadmap_versions`; it never imports `roadmap` (the backend seam) or the writer layer (`roadmap_revision_publish`) above it.
- `worktree.py` and the branch-awareness leaves (`project_config.py`, `branch_binding.py`, `branch_ownership.py`) — pure path/config leaves below their command groups.

**Exit-code convention:** subcommands exit non-zero only on failure-to-complete, never on findings/verdicts. A completed audit/run exits 0 even with CRITICAL/`[FAIL]` lines — CI parses the lines, or passes `--fail-on-findings` to flip the rc.

**Plan discovery is per-project.** Each repo keeps its own manifest at `<repo-root>/.plan-tool/plans.json` (`{"plans": [...]}` of repo-relative `.md` paths); the package ships none. `locator.py` scopes resolution to the cwd's git tree — no cross-project cache leakage. Override with `--plans-dir` or `PLAN_TOOL_PLANS_DIR`.

**Everything else — what each module *is* — lives in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md):** the correctness gates, the escalate-to-split bridge, the granularity advisor, the convergence diagnostic, the structural remedy vocabulary, decision telemetry, concept sign-off, the backend and rate-limit leaves, branch-awareness, parallel plan worktrees, and the roadmap verb. That split is this file's own § "Code comments" rule applied to itself: depth belongs in a maintained doc behind a pointer, because inlined module detail drifts — the roadmap paragraph alone carried two counts that `roadmap-02-feedback-channel` has to sweep.

## Tests

Mirror source modules: `plan_tool/X.py` → `tests/test_X.py`. Default to **unit tests** (unmarked, isolated, fast).

**Assert the carve-out, not only the rule — and verify by mutation, never by reading.** A suite naturally pins what a check *rejects*; the deliberate exemption beside it gets prose and no assertion, so widening the rule to swallow it stays green. Measured 2026-08-04: folding `TRADED_AWAY` into the rejecting arm of `check_attribute_totality` passed the entire suite, although its exemption was stated in the prompt, the gate docstring, and `ROADMAP_FORMAT.md` ([evidence](docs/evidence/claude-md-measured-incidents.md#14-an-exemption-nothing-pinned-2026-08-04)). **A docstring saying "deliberately not" is a claim to pin, not a fact to trust.** The same move settles any new or tightened test: break the code it names and watch it go red. Three other cases of reading-instead failing are recorded in the evidence page. Corollary for anything annotating rendered output: **assert keys, not words** — a substring check breaks the next time a comment legitimately uses the word, which has now happened twice.

**Name a test for the invariant it pins, not just the code path it exercises — especially when the behavior is deliberate but reads like it could be a bug.** A test name and assertion that state *what* is guaranteed and *why* (`test_context_is_copied_and_cannot_override_event_identity`, not `test_emit_extra`) are what let a later reader — human or audit — tell a corrected precedence or a closed contract apart from a regression, without re-deriving the reasoning from scratch. This is the authoring half of the "verify a bug finding against its existing tests" rule above (§ "Driving the convergence loops"): that check only has something to find when the test it goes looking for states its own intent. Write it this way for any invariant or gotcha a step's design calls out — a corrected precedence, a guarantee that looks avoidable, a contract requiring an absent key rather than a null value — not only for the property under test but for the *reason* it must hold.

**A green suite says nothing about the sites you didn't change — when a fix is class-wide, expect to rewrite the tests that pinned the old behavior at the siblings.** Each site of a shared contract carries tests asserting *its* current behavior, so fixing one site leaves the others green **because** they still encode the defect. Green is then read as "the change is complete", which is precisely backwards: it is confirmation the sweep stopped early. Measured 2026-08-06: finishing the scope-fence intent sweep across its seven consumers turned five previously-green tests red ([evidence](docs/evidence/claude-md-measured-incidents.md#3-one-site-fixes-with-a-green-suite-2026-08-06)). **A red sibling test during a class sweep is the expected outcome, not a reason to narrow the fix**; read each one to decide whether the site is a genuine carve-out (then assert it as one, per the rule above) or a missed instance (then update it). Prefer one parametrized test over the whole consumer set — see `TestIntentPredicateConsumers` — so the next site added to the class fails loudly instead of silently inheriting the old predicate.

**`tests/test_duplication.py` is a repo-wide guard, not a mirror.** It fails two ways: when a *new* exact-duplicate function body (≥4 lines, normalized past docstrings, function names, and parameter names) appears in `plan_tool/`, and when one of BACKLOG #79's deliberately-duplicated helpers *disappears* — the second catches the cleanup that folds a seam it should not, which a duplicate count can never see. Baseline is **0** duplicate groups. It does **not** demand a merge: `ALLOWED_DUPLICATE_GROUPS` with a stated reason is a first-class answer, and is the right one whenever consolidating would pull an unrelated change out of shape (see the anti-creep section above for how the two fit together). An allowlist entry with no rationale is a disabled test. Add `@pytest.mark.integration` at class level only when you must drive `main([...])` or an orchestrator end-to-end across modules. 30s per-test timeout (opt out with `@pytest.mark.timeout(N)`). Tests are hermetic (own `tmp_path`); a `-n auto`-only failure means hidden shared state — fix the test.

## Reference docs

- `MISSION.md` — project mission + the grounding principles the codebase is built to obey (each carries a stable `<!-- principle-id: … -->` kebab slug)
- `CAPABILITIES.md` — app-level catalog mapping each CLI/orchestrator surface to the MISSION principle(s) it serves; kept honest by a no-Claude check in `plan-tool validate` (`plan_tool/capability_catalog.py`). **Distinct** from the per-plan `features:` registry (durable + outward vs transient + inward; no shared id space)
- `docs/how-to/use-cases.md` — situation-first guide: is your work a good fit, which use case you're in, and which commands to reach for (the *when*, complementing CAPABILITIES' *what* and the command guides' *how*)
- `docs/reference/commands.md`, `docs/how-to/common-workflows.md`, `docs/ITERATION.md`, `docs/OPERATIONS.md`, `docs/BACKENDS.md`, `docs/GATES.md` — the command reference, pipeline procedure, `--iterate`, day-to-day operations, backends, and gates behind the README
- `CONTRIBUTING.md` — the developer entry point for changing the tool: setup, which `plan-tool` build is running, picking work, direct vs plan routes, the convergence exits, code-review habits, and three reading paths
- `docs/TRACKING.md` — the rules for tracking work: which backlog file, the route / readiness / tier labels, the entry format and scope contract, and direct vs plan
- `docs/explanations/development-model.md` — the working model: the developer as guardian and mentor of the assistants, a field guide to assistant behavior with dated examples from this repo, and the review stories behind the habits
- `SEED_FORMAT.md` — plan-seed authoring directives (density, single-effort focus, destinations-not-turn-by-turn, required scope-contract fence)
- `PLAN_FORMAT.md` — plan-file frontmatter schema and step conventions, including the `format_version` declaration every plan carries and the refusal an unsupported value gets
- `DETAIL_FORMAT.md` — the sole per-step run-grade seven-section detail contract, selected by `steps[].detail`, with a format-version marker that rejects unsupported values
- `ROADMAP_FORMAT.md` — the frontmatter schema for the `roadmap` verb's four staged artifacts (`01-domain.md` through `04-roadmap.md`) and the route contract for read-only two-snapshot comparison, candidate review, immutable evidence, and immutable accepted-head versions
- [`docs/how-to/roadmap.md`](docs/how-to/roadmap.md) — the `roadmap` verb end to end on one real run through automated plan derivation (stage 4) and printed `create --from-existing` lines; § 1 owns the hand conversion of an older folder, and § 7 keeps a direct fallback procedure; position **04** is shipped; position **05** (framework lenses) is not
- [`docs/demos/roadmap-demo.md`](docs/demos/roadmap-demo.md) — the runbook for producing the `roadmap` → `create` → `detail` demo on the TTRPG world-builder brief ([`docs/concepts/ttrpg-world-builder.md`](docs/concepts/ttrpg-world-builder.md)), executed in a throwaway repo. § 5a is the load-bearing part: the **refused** feedback row, gate-backed by `check_settled_decisions`, showing a prior settled decision beating the model's current opinion
- [`docs/evidence/roadmap-layering-measurement.md`](docs/evidence/roadmap-layering-measurement.md) — the 2026-08-01 three-arm test of #208's premise, whose raw artifacts are gitignored. All three plans reached the same architecture; the layering bought provenance and finality, not better design. **Read its "How to read this result" before citing it** — the null was misread as the premise failing and acted on, and that reversal is settled
- [`docs/evidence/claude-md-measured-incidents.md`](docs/evidence/claude-md-measured-incidents.md) — the dated measurements behind this file's rules, moved verbatim: audit calibration, class-wide application, the withdrawn test-ordering contract, fence recognition. **Read the rule and verdict here first**; the evidence page records how each was established
- [`docs/evidence/roadmap-run-measurements.md`](docs/evidence/roadmap-run-measurements.md) — what the `roadmap` verb actually did on two real briefs while positions 01–04 were built: id stability under regeneration vs. revision (and the entity-id anchoring rule that falls out of it), the first feedback loop's per-id outcomes, the decision-record rule's four confirmed branches, and the first stage-3/stage-4 runs. **Every block is n=1 or n=2 and gates nothing** — read its "How to read every record here" first. The raw artifacts and run logs are gitignored, so this file is the record
- `JIRA_FORMAT.md` — exported jira-story schema (markdown + JSON, story fields, validation)
- `docs/reference/contracts/human-io.md` — filesystem record protocol for the bounded review-walk human-input proof
- `DATA_CONTRACT.md` — persisted/serialized runtime schemas (saved-review sidecar, `Recommendation`/`Annotation`, fingerprints, manifest), plus the plan and run-grade detail format-version constants and their evolution policy — `PLAN_FORMAT.md` and `DETAIL_FORMAT.md` keep ownership of those artifacts' content schemas; drift-guarded by `tests/test_data_contract.py`
- `RUNBOOK.md` — operational walkthroughs and recovery recipes
- `docs/explanations/nondeterministic-plan-design.md` — designing plans that add Claude-judged (non-deterministic) features so their completeness audits converge: the fold taxonomy, deterministic-core/judged-edge layering, the determinism ladder, gate and fence rules
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module-by-module description of what ships (the descriptive half; the normative rules stay in § "Architecture" above)
- `TESTING.md` — full testing guide + invoker neutralization table
- `docs/how-to/pipeline/run.md`, `docs/how-to/pipeline/create-from-existing.md`, `docs/how-to/pipeline/audit.md`, `docs/*_RESUME_FLOW.md` — per-flow gate/sequence diagrams; `docs/how-to/pipeline/audit.md` is the detailed operator contract for qualified completeness results, plan/detail revision freshness, and grade-aware handoff
- `docs/evidence/backend-recommendations.md`, `docs/reference/contracts/codex-cli.md`, `docs/reference/contracts/cursor-agent-cli.md` — backend guidance and pinned CLI contracts
- `docs/cli/` — generated per-subcommand flag reference (every flag/default/subaction). Source of truth is the argparse parser; regenerate with `python -m plan_tool.cli_reference --write` (drift-guarded by `tests/cli/test_cli_reference.py`)
