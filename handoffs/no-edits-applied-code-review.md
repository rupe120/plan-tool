# `run` no-edits-applied block and failure receipts — review ledger

| Field | Value |
| --- | --- |
| Change | A mutating `run` step whose declared files all stayed unchanged is not advanced and reports "no edits applied"; every failed mutating step stores its final reply in a sidecar and logs a `model_failure_receipt` |
| Branch | `feat/456-no-edits-applied` |
| Reviewer | `/code-review high`, headless, report-only |

## Settled decisions

- The block applies whether or not test enforcement is on (owner decision, 2026-10-13).
- A step that declares no files is exempt: with no declared set there is nothing to compare.
- The run log carries no reply text; the reply lives in the sidecar and the receipt carries its digest and path.

## Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | The "no edits applied" message advertises `--accept`, which refuses when the plan has no `test_command` and the step has no `gate`; a docs-only step with no gate has no way forward (medium, CONFIRMED) | **Fixed.** The failure names `--accept` only when a `test_command` or `gate` exists; otherwise it says what closes the step. Mirrored in run.md and RUNBOOK; mutation-checked | |
| 2 | A non-file `files:` entry stamps as `(mtime, size, None)`, so work inside it reads as "no edits applied", now a hard failure (low, PLAUSIBLE) | **Fixed, fail-open.** `PLAN_FORMAT.md` defines `files:` as existing files, but the parser does not enforce it; an entry with no content digest now counts as modified; mutation-checked |
| 3 | The sidecar identity hard-codes `attempt1`, so a second failure of one step under one logger would overwrite the first sidecar (low, PLAUSIBLE) | **Fixed.** The identity carries `time.time_ns()`. Not reachable today (`run --all` halts on the first failure), so this is cheap hardening, not a live defect; mutation-checked |
| 4 | Only the `no-edits-applied` receipt is tested; the other four reasons `DATA_CONTRACT.md` lists have no test (low, CONFIRMED) | **Fixed.** One parametrized test over `invoke`, `test-authoring-gate`, `test-gate`, `gate`; each emit site mutation-checked |

Checked, no finding: block ordering, plan write-back, content-hash comparison, receipt contents.

## Findings (round 2)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | The comparison included mtime, so an identical-bytes rewrite read as modified and the step advanced; the "content-compared" docs overstated it (medium, CONFIRMED) | **Fixed.** Size and digest decide; mtime is ignored. Mutation-checked |
| 2 | A path missing before and after counts as unchanged, so a step whose entries never resolve (a glob) is blocked (medium, PLAUSIBLE) | **Declined, carve-out asserted.** A `creates:` path nothing wrote is the exact case this change exists to catch; the block needs *every* declared entry unchanged, so a step with any real edit advances. `PLAN_FORMAT.md` defines `files:` as existing files, not globs. A test pins it; mutation-checked |
| 3 | `GATES.md`, `run.md` (advisory list) and `common-workflows.md` still called the check a warning (low, CONFIRMED) | **Fixed.** All three swept |
| 4 | The IPPT-16 seed and `BUG_BACKLOG.md` stub still scope the gate to `non-code` steps only (low, PLAUSIBLE) | **Fixed by owner decision, 2026-10-13.** This change ships the gate for every step type, which the IPPT-16 seed listed as out of scope. The seed is deleted (git keeps it), the `BUG_BACKLOG.md` promotion stub is removed, and the arc ledger row is marked superseded. The Jira ticket itself is the owner's to close or re-scope |
| 5 | `DATA_CONTRACT.md` said "every failed mutating step" but exception and no-logger paths emit nothing (low, PLAUSIBLE) | **Fixed.** The contract names the covered paths and the uncovered ones |
| 6 | `_record_step_failure_receipt` repeats the sidecar-then-receipt sequence in `roadmap.py` (low, CONFIRMED) | **Declined.** Not an exact duplicate (`tests/test_duplication.py` is green); the shared helper lives in `roadmap.py`, above `launcher.py` in the layering, so calling it would add an upward edge. A consolidation would be its own change with an AST-checked entry |
| 7 | `read_bytes()` loaded each declared file twice per step (low, PLAUSIBLE) | **Fixed.** Chunked `hashlib.file_digest`, and no second hash when the size already differs |

## Findings (round 3)

Zero findings. Checked and clean: every `_files_unchanged_since` branch, non-mutating modes unreachable by the block, write-back contract, receipt emission on a failed sidecar write, empty reply, invoke-failure reply source.

| # | Observation (below threshold) | Disposition |
| --- | --- | --- |
| 1 | A re-run after a failed gate, where the files already hold the fix, is blocked as "no edits applied" | **Documented, not reversed.** The block applies to every step (owner decision, 2026-10-13); the failure names `--accept` as the route, and RUNBOOK says so |
| 2 | A named pipe declared as a file would block on open for hashing | **Not reachable.** `PLAN_FORMAT.md` defines `files:` as existing regular files |

## Findings (round 4, tests-and-docs lens)

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

## Findings (round 5)

Zero correctness findings in `launcher.py`. The round 4 fixes were re-verified by grep (no remaining statement that the check warns, no roadmap-only receipt description, no pending reference to the shipped item or the retired seed, and the `--accept` claims match the code). Three low docs findings:

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | `RUNBOOK.md:812` and `:950` link to `docs/RUN_FLOW.md`, which does not exist (low, CONFIRMED) | **Declined, out of scope.** The dangling link predates this branch; the repoint to `docs/how-to/pipeline/run.md` is unrelated to the change. Left for a separate docs fix |
| 2 | #87's open question still read as if a no-edit retry reaches the test-authoring gate (low, PLAUSIBLE) | **Fixed.** A dated line narrows the question to steps that declare no files |
| 3 | The `producer_slug` collision entry omitted the new `_run/<slug>` producer (low, PLAUSIBLE) | **Fixed.** `launcher.py:_record_step_failure_receipt` added to the entry's Files list |

## Findings (round 6)

Zero findings. Interactions checked clean: `--all` sweeps and halts, single-step `--commit` (gated on `done`), plan status and `status_note` write-back, `--accept` against the note the block writes, every non-`run` caller of `run_step`, `bench.py`'s caller (a no-edit run now reads as a failure, the correct direction), the lessons log, receipt emission once per failure.

| # | Observation (below threshold) | Disposition |
| --- | --- | --- |
| 1 | A sweep halt's lesson text reads "run failed (exit code 1)", as for every gate refusal | **Not changed.** Matches the sibling gates; the specific reason is in the `status_note` and receipt |
| 2 | An untracked sidecar could make `--accept` refuse a dirty tree in a repo that does not ignore `.plan-tool/parse-failures/` | **Not a new defect.** The path is in this repo's `.gitignore` and the README's documented ignore list, and `detail` already writes there |

## Convergence status

**Converged after 6 rounds** under the project's low-yield rule: round 5 added only low findings (two applied, one declined as pre-existing) and round 6 was clean. Rounds 1, 2 and 4 carried the material findings (a message advertising an unusable route, an mtime comparison that missed identical rewrites, stale wording across eleven docs, a missing pin on `final_text`); every one is fixed and mutation-checked. Round 3 was clean in between.

Open outside this change: the IPPT-16 Jira ticket still describes work that has shipped; `RUNBOOK.md` links to a `docs/RUN_FLOW.md` that no longer exists.
