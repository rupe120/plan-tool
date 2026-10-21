> **Replaced**: this file has been superseded by `docs/implementation-plans/2-plan-tool-annotate-feedback.md`.
> Preserved here for history; do not edit.

## Overview

Hardens the `plan-tool annotate` command so it can drain a stale backlog unattended, based on a real `annotate ... --archive` sweep across 30 untracked implementation plans (29 OK, 1 unrecoverable crash, 1 transient self-heal, 1 silent archive collision). Adds graceful per-section degradation, binary-file safety on the grounding path, a `--seed-dir`/`--report-dir` batch form, a grounding-floor trust signal, loud archive-collision handling, a `list --status` rollup, and outcome-based jira acceptance-criteria generation. The throughline: `annotate` is documented as *the* backlog-draining workflow, so it must be resilient to one bad section/file instead of all-or-nothing.

## Problem statement

`annotate` is framed as the backlog-draining workflow but fails in several ways during real sweeps. P1 (High): a single descriptive, non-actionable section (e.g. 'Bugs and Risks Surfaced During Analysis') is classified `NOT-IMPLEMENTED` while carrying `code_refs`; the validator treats that as a contradiction and hard-aborts the *entire* annotate, dropping the whole plan's analysis with no seed/report/archive — and a plain re-run of the same command succeeded, confirming this is LLM nondeterminism, not a structural plan property. P5 (High): grounding reads a binary repo asset (e.g. the `3-bundle-size-optimization` plan referencing `dist/`, minified JS, `.map`, ~14 MB images) and passes NUL-bearing bytes into argv, hard-crashing in `subprocess._execute_child` / `_fork_exec` with an opaque `ValueError: embedded null byte`; the plan file itself is clean. P2 (Medium): confident verdicts are emitted with near-zero grounding — reports with `grounded_files: 0` still claimed `IMPLEMENTED` sections, with prose-heavy docs (exec summaries, jira exports, diagram/vision docs) grounding poorly and either over-claiming or default-dumping to `NOT-IMPLEMENTED`. P3 (Medium): no `--batch`/glob/directory form, so a sweep requires a hand-rolled shell loop. P6 (Medium): on an archive-target name collision (a pre-existing `archive/<stem>.replaced.md`), `--archive` reports success and writes seed+report but leaves the original in the active dir — false success. P4 (UX): `--iterate` is accepted but inert on annotate, a footgun in a family where `create`/`detail` default it ON. P7 (Low/feature): no backlog status rollup, so people hand-maintain a snapshot (e.g. `implementation-plan-review.md`) that immediately rots. P8 (Low-Medium): `plan-tool jira` emits acceptance criteria needing a manual cleanup pass. First-pass failure rate was 2/30 (6.7%), with 1/30 (3.3%) unprocessable; P1 and P5 account for both first-pass failures.

## Architecture

P1 — degrade gracefully instead of aborting: on a contradictory verdict, emit a warning and still write report/seed, marking the offending section `NEEDS-REVIEW`; optionally add a `DESCRIPTIVE`/`NON-ACTIONABLE` classification so analysis sections may legitimately carry `code_refs` and are auto-excluded from the carryover seed; optionally relax the validator so `NOT-IMPLEMENTED + code_refs` is contradictory only for *actionable* sections (citing inspected code is normal evidence). A built-in retry (the authoring family already has checkpoint/resume) would let the transient case self-heal.

P5 — never feed file bytes into argv: pass grounded content via stdin or a temp file (argv has hard limits and is NUL-intolerant); skip/detect binary files during grounding by testing for NUL in the first N bytes or honoring `.gitignore` / a text-extension allowlist; sanitize defensively by stripping NUL and capping length on any string crossing the subprocess boundary, and convert the raw `ValueError` into 'grounding skipped binary file <path>'.

P2 — grounding-floor guard: when `grounded_files` is below a threshold (e.g. < 3), suppress confident `IMPLEMENTED`/`PARTIAL` verdicts and stamp a report-level banner ('Low grounding (N files) — verdicts are speculative, verify before trusting'); surface `grounded_files` in the console summary line, not just the report HTML comment; optionally detect non-plan doc types (exec summary / diagrams / jira export) and short-circuit with 'not a code-bearing plan — archive without seed'.

P3 — batch form `plan-tool annotate <dir-or-glob> --archive --seed-dir ... --report-dir ...` that loops, continues past per-file failures (see P1), and prints a coverage + grounding summary table; the `--seed-dir`/`--report-dir` pair (vs. per-file `--seed`/`--report`) is the missing primitive.

P6 — on target collision, fail loud or disambiguate (`<stem>.replaced.2.md`), never report 'archived' when no move occurred; make the archive move atomic with the success report.

P4 — reject `--iterate` outright on annotate (already documented as reserved/inert); document a 'sweep layout' recipe (seed→`plan-seeds/`, report+original→`archive/`) so the default report location beside the now-archived source isn't a trap.

P7 — `plan-tool list --status` (or extend `sweep --report-only`) emits a one-shot rollup across manifest + on-disk plans: name, IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED counts, `grounded_files`, last annotated date; reads cached `*.annotated.md` where present and flags un-annotated plans; optional `--format md` to emit the table on demand from ground truth (never checked in).

P8 — encode jira generation rules in `plan-tool jira` (and/or a `jira --lint`): state observable outcomes not implementation steps; no line numbers, import lists, call-site/grep counts, or file-size caps as AC; prefer automated tests over manual checks where CI can cover it; keep AWS resource names / path literals in the description not the AC unless the story is an infra contract; for verification-only stories separate 'done' (behavior verified) from 'evidence recorded'.

## Out of scope

- Per-issue / live Jira reconciliation — plan-tool emits exports *into the repo* and cannot read *live* Jira, so reconciling generated stories against the board stays a human/integration task; better generated AC only shrinks it.
- Checked-in status snapshots — the rollup (P7) is generated on demand from ground truth, deliberately never persisted as a file that would rot.

## Risks

- P1's contradiction is confirmed LLM nondeterminism (a re-run of the same command succeeded), so a retry mitigates but cannot guarantee; graceful per-section degrade is the durable fix and the validator should never hard-abort on a transient contradiction.
- The grounding-floor threshold (e.g. < 3 files) is a heuristic — risk of suppressing legitimate verdicts on small-but-real plans; mitigated by keeping the banner advisory and retaining existing per-section low-confidence flags.
- Binary detection via 'NUL in first N bytes' may misclassify some files; mitigated by also honoring `.gitignore` / a text-extension allowlist and by sanitizing (strip NUL, cap length) at the subprocess boundary as a backstop.
- Doc-type detection (exec summary / diagram / jira export short-circuit) risks misfiling a genuine code-bearing plan as non-plan; keep it conservative.

## Acceptance criteria

- A single contradictory section (`NOT-IMPLEMENTED` + `code_refs`) does not abort the run: `annotate` exits having written both the report and seed, with that section marked `NEEDS-REVIEW`.
- `annotate` on a plan whose repo contains binary assets (the `3-bundle-size-optimization` case) completes without raising `ValueError: embedded null byte`; binary files are skipped/reported during grounding rather than read into a subprocess argument.
- Grounded content reaches the Claude subprocess via stdin or a temp file — no grounded file bytes are placed in argv.
- `plan-tool annotate <dir-or-glob> --archive --seed-dir <d> --report-dir <d>` processes every matched plan, continues past a per-file failure, and prints a coverage + grounding summary table at the end.
- A report with `grounded_files` below the threshold emits no confident `IMPLEMENTED`/`PARTIAL` verdict and carries a report-level low-grounding banner.
- The console summary line for each plan includes its `grounded_files` count.
- `--archive` against an occupied `archive/<stem>.replaced.md` target either errors clearly or writes a non-colliding name (`<stem>.replaced.2.md`); it never reports 'archived' while the original remains in the active dir.
- `--iterate` passed to `annotate` is rejected with a clear error (not silently accepted).
- `plan-tool list --status` prints a rollup table (name, IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED counts, `grounded_files`, last annotated date) and flags un-annotated plans; `--format md` emits the equivalent markdown table.
- `plan-tool jira` output contains no line numbers, grep/call-site counts, import lists, or file-size-cap bullets in acceptance criteria; `jira --lint` flags any such bullet.
