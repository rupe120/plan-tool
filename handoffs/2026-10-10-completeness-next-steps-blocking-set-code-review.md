# Completeness next steps from one blocking verdict — review ledger and session handoff

| Field | Value |
| --- | --- |
| Change | BACKLOG #479: every completeness next-step reader (report prose, console list and summary, grouped report) and the `detail` / `split` / `merge` parents derive what to close and the one next command from the finalize gate's blocking verdict, so no surface says "no plan-level gaps remain" or offers a stage while a gate-blocking gap is open |
| Plan | `docs/implementation-plans/2-completeness-next-steps-blocking-set.md` (plan PR #70); seed archived under `plan-seeds/archive/` |
| Branch | `feat/completeness-next-steps-blocking-set`, merged as PR #71 (`1d6476e1a`) |
| Review range | `97ce3a261..23743e90e` |
| Checks run | Full suite `uv run pytest tests/ -q -n auto` after every fix batch; last: 14,330 passed, 67 skipped (`c1680dcde`); `reconcile-code --all`: 0 findings on steps 1–4 |
| Reviewer | `/code-review high` in-session (forked), report-only, four passes |
| Disposition | pass 1: 10 fixed; pass 2: 10 fixed by the centralization (`14499ac46`); pass 3: 3 design gaps fixed by amendment (`a9be29987`, `c1680dcde`) + 7 fixed; pass 4: 10 tracked as BACKLOG #480. Closed **non-converging by agreement**: each pass found a new class at the reader/verdict seam, so pass 4 was filed instead of a fifth pass |

## Settled decisions (hand to the #480 reviewer)

- The finalize gate's external contract is unchanged: `--json` `has_blocking_findings`, `--fail-on-findings`, exit codes. The gate's deterministic arms are collected once (`_blocking_deterministic_findings`) and read by both the gate's bool and the verdict.
- `BlockingVerdict` has three states (`set`, `incomplete`, `absent`). Only a completed empty `set` offers a stage. `incomplete` keeps every blocking id the audit established (amended 2026-10-10 after pass 3; before that it closed nothing by id and hid HIGH gaps as advisory). `absent` is the default for a caller that passes no verdict.
- Trust follows the gate (amended after pass 3): a non-empty set names its gaps whatever the stop, hand-apply included; an empty set offers a stage only when finalize is clean. `awaiting-human-action` with an empty set is untrusted (`persistent`) — accepted by the session as amendment 3's intent; a one-line change if the narrower reading is wanted.
- A `persistent` untrusted cause prescribes hand triage of the saved report, edit, commit, then re-audit the changed snapshot; a `transient` cause keeps the plain `--iterate` re-audit. (Pass 4 found `transient` unreachable — see #480.)
- Two shared functions decide everything: `next_step_gaps` (close vs advisory, from the verdict alone) and `next_stage_command` (the one next command; re-audit carries `--grade jira` at jira grade, `--iterate` at run grade). Readers and parents only format their output.
- The `detail` / `split` / `merge` parents offer a stage only for a completed empty set whose tail result still matches the current files; a bare bundle names `detail`.
- The absent default landed in two phases (step 1 kept legacy output for an unset verdict; step 2 flipped it once callers were wired) so each `run` step stayed green under the full-suite gate (resequenced `bce3a1319` after the first run failed six step-2 tests).

## Execution record

- Bare-plan audit (Gate 1): four rounds, 0/5 detailed, coverage confirmed each round, completeness apply withheld; 5 → 6 → 3 → 3 unique findings. Round 3 caught a false seed claim (the conceptual blocking ids include no deterministic findings); round 4 described only prior edits.
- Detail-grounded audit (Gate 2): three rounds, 5/5 detailed; round 1 `no-qualified-current-evidence`, rounds 2–3 confirmed; 4 → 3 → 2; last round applied without re-audit (low-yield).
- `run --all --commit`: steps 1, 3, 5 green under the tool. Step 2 hand-recovered per `DIRECTIVES.md`: 5 failures from a step-1 defect (`suggested_next_steps`' own fallback called `next_stage_command` without the verdict) plus a stray `# ` description prefix; fixed in `843f441d0`, suite green, status flipped in `8fadcca88`. Step 4 hand-recovered: one table row asserted the word "No gaps" absent while the correct absent-verdict text contains it; assertion narrowed to keys in `f151e42e8`, status flipped in `3b63f8069`.
- `reconcile-code` missed the jira-grade re-audit lacking `--grade jira`; fixed by hand in `50e08225d` (47 sibling tests pinned the grade-less form and were moved to prefix checks; the exact form is pinned once).

## Findings (one line each)

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

## Session handoff (2026-10-10)

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
