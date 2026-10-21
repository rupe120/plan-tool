# `run --accept` (#463) — review ledger

| Field | Value |
| --- | --- |
| Change | BACKLOG #463: `plan-tool run <slug> --step N --accept` certifies a hand-fixed step with the plan's `test_command` and the step's `gate`, then applies the ordinary done-and-advance, with no backend call |
| Branch | `fix/mark-hand-fixed-step-done` |
| Reviewer | `/code-review high` in-session (forked), report-only |

## Settled decisions

- The per-call test-authoring gate is not re-run on accept: its observable is a per-call delta and there is no call. The green suite certifies. The accept path does not check that a test file was authored; the failure message says so and tells the operator to commit the test first.
- No run log is written. A run log records backend calls; the plan edit and its commit are the record. A new persisted field would be a `DATA_CONTRACT.md` change (the entry's own Stop clause).
- Only the `current`, `committed` step is accepted. A pending step runs normally.
- The tree must be clean apart from the plan file and its lessons log: a failed gate writes `status_note` into the plan, so the plan being dirty is the normal precondition, not a defect.
- `--commit` commits only the plan and lessons files, never build output the suite left behind.

## Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | The documented recovery could not succeed: the failed gate dirties the plan, and `--accept` refused any dirty tree | **Fixed.** `unexpected_dirty_paths` with the plan file and lessons log expected |
| 2 | No lessons entry for an accepted step | **Fixed.** Same completion write as a backend run (`_persist_step_completion`) |
| 3 | A mistyped step id could be certified by an unrelated green suite | **Fixed.** Only a `current` step is accepted |
| 4 | The test-authoring failure message advertised `--accept`, which skips that gate | **Reworded.** Names the precondition and that authorship is not re-checked |
| 5 | Stale plan snapshot written back after multi-minute gates | **Fixed.** Re-read before write-back. The first mutation check survived because the test edited the body, which `write_plan` preserves; the test now edits the frontmatter and goes red under mutation |
| 6 | Gate loop duplicated from `run_step` | **Declined.** The two copies carry different side effects; sharing means refactoring `run_step`, which is not this change |
| 7 | `--accept` validated after the picker and scope prompt | **Fixed.** `_accept_flag_error` runs first in `cmd_run`; a test goes through the real entry point |
| 8 | `--iterate`, `--max-steps`, `--detail-grade` silently ignored | **Fixed.** Refused |
| 9 | `git add -A` put build output in the accept commit | **Fixed.** `_commit_paths` commits only the plan and lessons files; mutation-checked |
| 10 | No run log or telemetry for an accept | **Declined.** See Settled decisions |

Process notes: the first fixture wrote `test_command: true`, which YAML parses as a boolean, so the red-gate tests passed on a parse error until they were made to assert the gate's own rc. A hand status edit via `sed -i` is the failure mode this feature removes.

## Findings (delta review of the fix commit)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | Accepting only `current` left a dead end for a step run out of order and failed on a gate (it stays `pending`, and a re-run hits the same gate) | **Fixed.** `pending` with a failed-gate `status_note` is accepted; the note separates it from a mistyped id. A pending step with no note is still refused |
| 2 | `git add -- <paths>` failed on a gitignored lessons file | **Fixed.** Ignored paths are skipped; mutation-checked |
| 3 | Build output left untracked blocks the next `run --commit` | **Documented, not reversed.** The accept commit stays plan and lessons only; run.md and DIRECTIVES say to ignore or remove the output first |
| 4 | The shared completion write's recovery hint named `run --step N`, and an `OSError` escaped as a traceback | **Fixed.** `rerun_command` parametrizes the hint; `OSError` is a clean rc 1; mutation-checked |
| 5 | Preconditions were checked only on the pre-gate snapshot | **Fixed.** `_check_acceptable` runs again on the re-read plan; mutation-checked |
| 6 | Refusing `--iterate` and `--max-steps` broke their documented tolerance | **Fixed.** `--iterate` warns and `--max-steps` is ignored; `--detail-grade` is still refused |
| 7 | `_commit_paths` duplicated `_commit_green_step` | **Fixed.** One helper with an optional `paths` scope |
| 8 | Lessons behaviors under-tested | **Fixed.** Tracked, dirty, and gitignored lessons file each covered |

Closure: one full review round plus one delta review, as for #480. The delta review found two defects the first round's fixes introduced (the `current`-only dead end and the gitignored-path failure), which is the case for running it.
