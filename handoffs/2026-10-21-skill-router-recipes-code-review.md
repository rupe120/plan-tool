# Skill-router recipe repairs

| Field | Record |
| --- | --- |
| Base | `94e259687968ad18dfc965799a45df93218acd30` |
| Source-fix snapshot | `8fcf1b1f7` on `fix/skill-router-recipes` |
| Scope | Claude, Codex and Cursor routers; resolved backlog and evidence links |
| Runtime changes | None |
| Validation | Eight parent parser checks; 33 affected tests pass; full suite at `8fcf1b1f7`: 14,698 passed, 66 skipped in 61.41s |
| Review state | Actual Claude Code passes 2–3 find no router correctness defect; record cleanup verified, see closure |

## Property and sites

The routers must agree with existing command behavior and the canonical
[shared directives](../integrations/shared/DIRECTIVES.md) about authoring order,
iteration, recovery, verification authority and exit status. This repair changes
instructions; it adds no workflow gate and changes no CLI behavior.

The pre-edit identifier search covers `detail --reconcile`, `reconcile-plan`,
`[REDIRECT]`, `--iterate`, manual done-state editing and budget exhaustion.
The vocabulary search covers the authoring pipeline, implemented work,
headless examples, defaults, recovery, read-only checks and CI gates. Sites are
the headless block, decision tree, pipeline summary, reconcile catalog and
iteration summary in all three routers. A resolved-record sweep also finds
two demo records linking the removed backlog heading; those links move here.

## Findings and dispositions

| Finding | Disposition and evidence |
| --- | --- |
| Completeness recipe and pipeline omit the bare audit | **fixed `31fdf2f22`** — seed/create → bare audit → one-shot detail → grounded audit, with committed judged corrections and user review boundaries. |
| Detail default and compatible iteration flags are misstated | **fixed `31fdf2f22`** — detail defaults off; actual parser checks reject `detail --reconcile --iterate` and standalone reconcile iteration flags. The examples use only valid combinations. |
| Test-defect recovery suggests hand-editing done status | **fixed `31fdf2f22`** — commit the tested code/test correction without the plan, use `run --accept --commit` to run gates and advance, and retain the canonical unsuitable-implementation/no-gate escape routes. |
| Verification/redirect recipes send produced work to plan mutation | **fixed `31fdf2f22`** — request report-only inspection with `run --step N --mode check`; qualify all plan-side recipes as pre-execution and judge post-run redirects without an automatic code-canonical plan rewrite. |
| Summary promises budget exhaustion exits nonzero | **fixed `31fdf2f22`** — completed loops can exit zero; inspect saved outcome/qualification and use only supported CI flags. Existing exhaustion coverage explicitly asserts zero. |
| Independent headless examples still resemble an unaudited sequence | **fixed `4c5b20e62`** — all three blocks are explicitly syntax examples, with sequential authoring routed to the staged recipe and canonical gates. |

The original three-issue backlog record is fulfilled and removed. The two additional findings are the produced-work verification/redirect
authority error and the budget-exhaustion exit-status claim listed above.
They have provenance in local branch `docs/skill-router-follow-up-findings` at `c02aa3ff7`; that tracking
commit is not a remaining fix and should not be replayed as pending work after
this repair. The broader installed-skill portability and policy effort (#508)
remains separate. A nested sandbox initialization limitation observed during
the demo is resolved by parent access; it is not claimed as a skill runtime fix.

## Validation and reviews

- Real `build_parser().parse_args()` checks cover create, both audit gates,
  one-shot detail, report-only step inspection, both plan-side reconcile routes
  and gated acceptance without executing handlers.
- `uv run pytest tests/cli/test_skill_cmd.py
  tests/test_cli.py::TestCrossCuttingIterationCLI::test_budget_exhaustion_stderr_signal_create -q`:
  33 pass, including installer/copy behavior and the documented zero-exit case.
  After the headless correction the same affected set passes in 0.53s.
- Initial full-suite run before the Claude corrections: `uv run pytest tests/ -q -n auto`,
  14,698 pass and 66 skip in 63.02s. The later snapshot/result is in the header.
  No tests matching prose are added.
- Review 1, `94e259687..31fdf2f22`: no material finding; independently checks
  parser variants, owning contracts, source and relevant existing tests.
- Review 2, the same source snapshot: one P2 at the headless syntax block,
  corrected class-wide in `4c5b20e62`; no other material finding. It validates
  17 representative parser cases and the implemented authority boundaries.
- Review 3, `94e259687..4c5b20e62`: no material finding after the correction;
  independently checks the full identifier/vocabulary class, canonical rules,
  source and tests, with 12 parser-only probes. The remaining deeper iteration
  guide contradiction is tracked in BUG_BACKLOG.md rather than expanded into
  this router repair.
- Review 4, `94e259687..49f663dc4`, independently checks all eight changed
  files, 19 parser probes, handlers, source/tests, resolved links and the
  retained full-suite result; it reports no material findings. Saved artifacts
  use `.tmp/skill-router-recipes.review-N.md`; these verdicts retain the
  conclusions when scratch paths disappear.

No plan-tool execution plan or post-run code reconcile sweep is needed for this
direct documentation correction. The direct-change accuracy/completeness loop
applies; installation refresh and publication are recorded only when performed.

## Installation and closure

Before refresh, the installed Codex `SKILL.md` and `DIRECTIVES.md` copies match
the pre-fix source, so no custom content is overwritten. The global
`plan-tool install-skill --integration codex --user --force` reports “already
installed,” but a byte comparison still finds the old router. Its bundled-source
resolution does not select this checkout's changed router; this is not evidence
that `--force` is broken.

The explicit checkout invocation succeeds:

```bash
.venv/bin/python -c 'from plan_tool.cli.app import main; raise SystemExit(main(["install-skill", "--integration", "codex", "--user", "--force"]))'
```

Post-install byte checks confirm both installed files match the verified source.
Existing Claude/Cursor installation links are not retargeted. The branch push's
required full-suite hook also passes.

Two consecutive independent post-correction Codex reviews are clean. They do not
constitute the directed Claude Code `/code-review` route; that omission is
identified on 2026-10-21 and the actual Claude loop follows below. The deeper
iteration-guide mismatch remains separately tracked. No CLI behavior changes,
new gates, default-branch pushes or pull-request merge are part of this repair.


## Claude Code review pass 1 — 2026-10-21

Scope: `94e259687..ef924797e`. Claude Sonnet 5.5 invokes the actual built-in
`code-review` Skill with `high` effort in session
`1b67de09-bf16-47ed-b385-4dc20c19831d`. The original CLI exits zero and writes
`.tmp/skill-router-recipes.claude-review-1.md`; its stream records the Skill
invocation. Local diff review only; no publication or code edits.

| Finding | Disposition |
| --- | --- |
| F1 medium-low: check mode does not assess implementation | **refuted in part / clarified** — `prompts/check.md` explicitly requests mismatches between the step and code and forbids rewriting. A clean model report cannot prove delivery; the routers now state that limitation instead of promising read-only enforcement. Mutating `reconcile-code` is inappropriate for an inspection request. |
| F2 medium-low: detail example lacks clean-tree precondition | **fixed** — all three detail syntax lines state the precondition and plan commit. |
| F3 low: reconcile auto-apply warning loses “every” | **fixed** — all three lines state every recommendation is auto-applied without judgment. |
| F4 low: local provenance is unreachable on this branch | **clarified** — the local branch is named beside the commit. The finding descriptions and dispositions are retained here without depending on that branch merging. |
| F5 low: review 4 is embedded in review 3 | **fixed** — separate review bullet; remove incidental CLI narration. |
| F6 nit: extra backlog separator | **fixed** — normalize heading separators. |
| F7 nit: long completeness recipe duplicates directives | **declined** — the router must expose both audit gates, commits and user boundaries; its explicit clean-baseline instruction already covers the scenario. No additional workflow is introduced. |

Pass-1 outcome: convergence remained pending fresh Claude Code reviews after
these corrections.


## Claude Code review pass 2 — 2026-10-21

Scope: `94e259687..8fcf1b1f7`. Actual built-in `code-review` Skill at high effort,
Claude Sonnet 5.5, fresh session `43e9f02a-db4b-48aa-9bc2-79190646a2a7`;
CLI exits zero with `.tmp/skill-router-recipes.claude-review-2.md`.

| Finding | Disposition |
| --- | --- |
| 1 medium-low: evidence page describes repaired recipes as current | **fixed** — date the observation and frame the former recipes as past; retain it as demo provenance. |
| 2 low: header names an earlier source/test snapshot | **fixed** — name `8fcf1b1f7` and its fresh full-suite result (14,698 pass, 66 skip, 61.41s); affected set is 33 pass in 0.54s. |
| 3 low: local provenance does not name its two findings | **fixed** — identify both defects explicitly beside the branch reference; their descriptions/dispositions remain in the finding table. |
| 4 low: check mode is model-judged | **declined, residual limitation** — the existing caveat states that a clean report cannot prove delivery; no deterministic semantic guarantee is claimed. |
| 5 nit: completeness recipe duplicates directives and omits output override | **declined** — retain both gates in the router; the independent syntax example's optional output override does not constrain the default-location recipe. |
| 6 nit: backlog should include run reconciliation iteration | **refuted as proposed** — canonical directives explicitly describe `run --iterate` as reconcile-loop control; the unsupported detail combination is independently proven by the parser. Do not widen the backlog from an unverified claim that run ignores reconciliation iteration. |

The router instructions receive no further change in this pass. These record
corrections do not reset their review window. Pass 2 reports no router correctness
defect; another independent pass is required before Claude convergence is claimed.


## Claude Code review pass 3 — 2026-10-21

Scope: `94e259687..a575487d5`. Actual built-in `code-review` Skill at high effort,
Claude Sonnet 5.5, session `a467cb5b-edf1-413e-aad8-c80585d634b4`, original CLI
exit zero. Report: `.tmp/skill-router-recipes.claude-review-3.md`. Its summary
count has a typo the reviewer could not edit after writing; the individual
findings below govern (one low-medium, four low, one nit).

| Finding | Disposition |
| --- | --- |
| A1 low-medium: four live gates reference the removed bug entry | **fixed** — BACKLOG #510/#515 and the installed-skill/public-release arcs link this repair as satisfying recipe consistency. Their independent unfinished prerequisites stay. Identifier and vocabulary searches enumerate all four sites before editing. |
| A2 low: iteration follow-up omits README sibling | **fixed tracking** — add README.md to the existing guide-accuracy backlog entry; leave actual guide changes to that bounded work. |
| A3 low: repair table overstates check-mode enforcement | **fixed** — use “request report-only inspection”; the prompt directs no rewriting but does not enforce filesystem isolation. |
| A4 low: index count differs from table rows | **clarified** — remove the count from the index; the finding table retains individual fixes and provenance. |
| A5 low: two full-suite timings lack separate attribution | **clarified** — label the original run separately from the fresh `8fcf1b1f7` run. |
| A6 nit: per-pass pending line reads as current | **fixed** — explicitly label the pass-1 outcome. |

Router convergence: passes 2 and 3 independently report no router correctness
defect, with residual advisory limitations dispositioned. At the pass-3 snapshot, supporting-record
verification remained pending; closure below records the completed sweep. This
is not represented as a wholly clean branch review. The latest findings predominantly
concern the repair's own record edits. Finish this bounded application and
verify the named properties rather than repeatedly elaborating review prose.


## Claude review closure

The actual Claude Code route comprises three completed high-effort Skill
invocations, with separate sessions, exact ranges and saved findings above.
Passes 2 and 3 independently find no router correctness defect after the final
router change (`8fcf1b1f7`); remaining model-judgment limitations and optional
wording suggestions have explicit dispositions. This is router convergence,
not a claim that those reports contain zero findings across every record.

The final supporting-record correction is committed as `59796a8ad`. Verification
confirms all four live prerequisite replacements resolve to this ledger, the
removed-entry heading/vocabulary has no remaining live gate in BACKLOG,
BUG_BACKLOG or the backlog arcs, and all three routers carry the clean-tree,
every-recommendation and delivery-evidence clarifications. `git diff --check`
is clean. The installed Codex skill and directives byte-match current sources.
The final record-only sweep changes no router or runtime behavior, so the fresh
33-test and 14,698-test results above remain the behavioral evidence.

Stop under the direct-change self-seeded-edit exit: later findings predominantly
concern these repair records; complete their bounded application and verify the
properties instead of resampling unchanged routers. No further full review is
claimed after `59796a8ad`, and no fully clean whole-branch Claude verdict is
claimed. All reported findings have dispositions. The omission in the earlier
execution is corrected; the skill already contains the Claude review requirement.
