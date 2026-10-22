# Skill-router recipe repairs

| Field | Record |
| --- | --- |
| Base | `94e259687968ad18dfc965799a45df93218acd30` |
| Source-fix snapshot | `4c5b20e62` on `fix/skill-router-recipes` |
| Scope | Claude, Codex and Cursor routers; resolved backlog and evidence links |
| Runtime changes | None |
| Validation | Eight parent parser checks; 33 affected tests pass; full suite: 14,698 passed, 66 skipped in 63.02s |
| Review state | Review 3 is clean after the headless correction; final independent confirmation pending |

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
| Verification/redirect recipes send produced work to plan mutation | **fixed `31fdf2f22`** — inspect with read-only `run --step N --mode check`; qualify all plan-side recipes as pre-execution and judge post-run redirects without an automatic code-canonical plan rewrite. |
| Summary promises budget exhaustion exits nonzero | **fixed `31fdf2f22`** — completed loops can exit zero; inspect saved outcome/qualification and use only supported CI flags. Existing exhaustion coverage explicitly asserts zero. |
| Independent headless examples still resemble an unaudited sequence | **fixed `4c5b20e62`** — all three blocks are explicitly syntax examples, with sequential authoring routed to the staged recipe and canonical gates. |

The original three-issue backlog record is fulfilled and removed. The two
additional findings have provenance in local commit `c02aa3ff7`; that tracking
commit is not a remaining fix and should not be replayed as pending work after
this repair. The broader installed-skill portability and policy effort (#508)
remains separate. A nested sandbox initialization limitation observed during
the demo is resolved by parent access; it is not claimed as a skill runtime fix.

## Validation and reviews

- Real `build_parser().parse_args()` checks cover create, both audit gates,
  one-shot detail, read-only step inspection, both plan-side reconcile routes
  and gated acceptance without executing handlers.
- `uv run pytest tests/cli/test_skill_cmd.py
  tests/test_cli.py::TestCrossCuttingIterationCLI::test_budget_exhaustion_stderr_signal_create -q`:
  33 pass, including installer/copy behavior and the documented zero-exit case.
  After the headless correction the same affected set passes in 0.53s.
- `uv run pytest tests/ -q -n auto`: 14,698 pass and 66 skip in 63.02s.
  No tests matching prose are added.
- Review 1, `94e259687..31fdf2f22`: no material finding; independently checks
  parser variants, owning contracts, source and relevant existing tests.
- Review 2, the same source snapshot: one P2 at the headless syntax block,
  corrected class-wide in `4c5b20e62`; no other material finding. It validates
  17 representative parser cases and the implemented authority boundaries.
- Review 3, `94e259687..4c5b20e62`: no material finding after the correction;
  independently checks the full identifier/vocabulary class, canonical rules,
  source and tests, with 12 parser-only probes. Its final response is saved by
  the outer CLI despite its read-only workspace. The remaining deeper iteration
  guide contradiction is tracked in BUG_BACKLOG.md rather than expanded into
  this router repair. Final independent confirmation is pending. Saved artifacts
  use `.tmp/skill-router-recipes.review-N.md`; durable verdicts belong here
  because scratch paths may disappear.

No plan-tool execution plan or post-run code reconcile sweep is needed for this
direct documentation correction. The direct-change accuracy/completeness loop
applies; installation refresh and publication are recorded only when performed.
