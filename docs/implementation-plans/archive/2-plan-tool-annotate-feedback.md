> **Auto-archived**: this plan was swept on 2026-07-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Plan Tool Annotate Feedback
status: completed
priority: medium
steps:
- id: 1
  title: Introduce backend prompt-transport seam for batch and streaming calls
  files:
  - plan_tool/backend.py
  - plan_tool/launcher.py
  - plan_tool/shell.py
  - tests/test_backend.py
  - tests/test_launcher.py
  - tests/test_shell.py
  complexity: high
  change_type: refactor
  status: done
- id: 2
  title: Route grounded prompt bytes through declared backend transports, not argv
  files:
  - plan_tool/backend.py
  - plan_tool/launcher.py
  - plan_tool/shell.py
  - tests/test_backend.py
  - tests/test_launcher.py
  - tests/test_shell.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  status: done
- id: 3
  title: Skip/report binary files during annotate grounding, record candidate/skipped
    counts, and convert raw ValueError to 'grounding skipped binary file'
  files:
  - plan_tool/annotate.py
  - tests/test_annotate.py
  complexity: medium
  change_type: feature
  status: done
- id: 4
  title: 'Degrade gracefully on a contradictory section: mark NEEDS-REVIEW instead
    of hard-aborting and exclude contradiction-derived NEEDS-REVIEW sections from
    the carryover seed'
  files:
  - plan_tool/annotate.py
  - plan_tool/annotate_render.py
  - tests/test_annotate.py
  - tests/test_annotate_render.py
  complexity: medium
  change_type: feature
  status: done
- id: 5
  title: 'Add grounding-floor guard: demote confident IMPLEMENTED below threshold
    and carry PARTIAL as review-required seed work, stamp a low-grounding report banner,
    and surface grounding counts'
  files:
  - plan_tool/annotate.py
  - plan_tool/annotate_render.py
  - plan_tool/cli/annotate_cmd.py
  - tests/test_annotate.py
  - tests/test_annotate_render.py
  - tests/cli/test_annotate_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 4
  status: done
- id: 6
  title: Finish archive-target collision handling by adding <stem>.replaced.N.md disambiguation
    and bundle-safe archive semantics
  files:
  - plan_tool/create.py
  - plan_tool/cli/annotate_cmd.py
  - tests/test_create.py
  - tests/cli/test_annotate_cmd.py
  complexity: medium
  change_type: feature
  status: done
- id: 7
  title: Reject --iterate on annotate with a clear error (currently accepted but inert)
  files:
  - plan_tool/cli/annotate_cmd.py
  - tests/cli/test_annotate_cmd.py
  complexity: low
  change_type: feature
  status: done
- id: 8
  title: 'Add batch form: annotate <path-or-glob>... --seed-dir/--report-dir that
    loops, continues past per-file failures, and prints a coverage + grounding summary
    table'
  files:
  - plan_tool/cli/annotate_cmd.py
  - tests/cli/test_annotate_cmd.py
  complexity: high
  change_type: feature
  gate:
  - uv run plan-tool annotate --help | grep -q -- --seed-dir && uv run plan-tool annotate
    --help | grep -q -- --report-dir
  depends_on:
  - 3
  - 4
  - 6
  status: done
- id: 9
  title: Add `list --status` rollup (counts including NEEDS-REVIEW, grounded_files,
    last annotated date, un-annotated flag) reading cached *.annotated.md from active
    plans and report dirs, with `--format md`
  files:
  - plan_tool/annotate_render.py
  - plan_tool/cli/inspect.py
  - tests/test_annotate_render.py
  - tests/cli/test_inspect_cmds.py
  complexity: high
  change_type: feature
  gate:
  - uv run plan-tool list --help | grep -q -- --status && uv run plan-tool list --help
    | grep -q -- --format
  depends_on:
  - 3
  - 4
  - 5
  status: done
- id: 10
  title: Extend jira AC lint (grep/call-count, import lists, file-size caps, infra
    literals, verification evidence) + add `jira --lint` flag
  files:
  - plan_tool/jira.py
  - plan_tool/cli/jira_cmd.py
  - tests/test_jira.py
  - tests/cli/test_jira_cmds.py
  complexity: medium
  change_type: feature
  status: done
- id: 11
  title: Align the jira generation prompt and enable post-generation enforcement for
    step 10's new AC lint categories
  files:
  - plan_tool/prompts/jira.md
  - tests/test_jira.py
  complexity: low
  change_type: feature
  depends_on:
  - 10
  status: done
- id: 12
  title: Document annotate hardening across the six operator surfaces (batch sweep
    layout, grounding-floor banner, archive-collision behavior, --iterate rejection,
    list --status, jira --lint)
  files:
  - RUNBOOK.md
  - README.md
  - CLAUDE.md
  - BACKLOG.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  complexity: medium
  change_type: non-code
  gate:
  - uv run plan-tool jira --help | grep -q -- --lint && uv run plan-tool annotate
    --help | grep -q -- --report-dir
  depends_on:
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
  - 9
  - 10
  - 11
  status: done
---
# Plan Tool Annotate Feedback

## Overview

Hardens the `plan-tool annotate` command so it can drain a stale backlog unattended, based on a real `annotate ... --archive` sweep across 30 untracked implementation plans (29 OK, 1 unrecoverable crash, 1 transient self-heal, 1 silent archive collision). Adds graceful per-section degradation, binary-file safety on the grounding path, a `--seed-dir`/`--report-dir` batch form, a grounding-floor trust signal, loud archive-collision handling, a `list --status` rollup, and outcome-based jira acceptance-criteria generation. The throughline: `annotate` is documented as *the* backlog-draining workflow, so it must be resilient to one bad section/file instead of all-or-nothing.

## Problem statement

`annotate` is framed as the backlog-draining workflow but fails in several ways during real sweeps. P1 (High): a single descriptive, non-actionable section (e.g. 'Bugs and Risks Surfaced During Analysis') is classified `NOT-IMPLEMENTED` while carrying `code_refs`; the validator treats that as a contradiction and hard-aborts the *entire* annotate, dropping the whole plan's analysis with no seed/report/archive — and a plain re-run of the same command succeeded, confirming this is LLM nondeterminism, not a structural plan property. P5 (High): grounding reads a binary repo asset (e.g. the `3-bundle-size-optimization` plan referencing `dist/`, minified JS, `.map`, ~14 MB images) and passes NUL-bearing bytes into argv, hard-crashing in `subprocess._execute_child` / `_fork_exec` with an opaque `ValueError: embedded null byte`; the plan file itself is clean. P2 (Medium): confident verdicts are emitted with near-zero grounding — reports with `grounded_files: 0` still claimed `IMPLEMENTED` sections, with prose-heavy docs (exec summaries, jira exports, diagram/vision docs) grounding poorly and either over-claiming or default-dumping to `NOT-IMPLEMENTED`. P3 (Medium): no `--batch`/glob/directory form, so a sweep requires a hand-rolled shell loop. P6 (Medium): on an archive-target name collision (a pre-existing `archive/<stem>.replaced.md`), `--archive` reports success and writes seed+report but leaves the original in the active dir — false success. P4 (UX): `--iterate` is accepted but inert on annotate, a footgun in a family where `create`/`detail` default it ON. P7 (Low/feature): no backlog status rollup, so people hand-maintain a snapshot (e.g. `implementation-plan-review.md`) that immediately rots. P8 (Low-Medium): `plan-tool jira` emits acceptance criteria needing a manual cleanup pass. First-pass failure rate was 2/30 (6.7%), with 1/30 (3.3%) unprocessable; P1 and P5 account for both first-pass failures.

## Architecture

P1 — degrade gracefully instead of aborting: on a contradictory verdict, emit a warning and still write report/seed, marking the offending section `NEEDS-REVIEW`; exclude contradiction-derived `NEEDS-REVIEW` sections from the carryover seed so a speculative contradiction does not become unattended follow-up work. Step 5's low-grounding `NEEDS-REVIEW` entries use a different reason and stay visible as review-required carryover so potentially unfinished work is not dropped. New `DESCRIPTIVE`/`NON-ACTIONABLE` taxonomy, validator relaxation, and built-in retry stay deferred. The authoring family already has checkpoint/resume, and per-section degrade is the durable fix for the transient case.

P5 — never feed file bytes into argv: step 1 extends the backend seam so `CliBackend` no longer models prompt transport as `prompt -> argv` only, but does so behavior-preservingly: the first pass introduces a prompt-transport object/helper used by both `plan_tool/shell.py` batch calls and `plan_tool/launcher.py` streaming calls while still rendering the current argv shape under tests. Step 2 switches grounded prompt bytes to the declared transport for every backend and owns the subprocess-boundary sanitizer in `plan_tool/shell.py` / `plan_tool/launcher.py`: every prompt/model/project/backend-manifest string that reaches `batch_argv`, `streaming_argv`, or extra argv is NUL-stripped and length-capped before process spawn. Backends declare one of the supported transports: stdin payload, temp-file consumed through an explicit backend command template, or another backend-specific prompt handle; a temp path is never passed as a positional prompt unless that backend declaration says the CLI reads prompt content from that path. Closed-stdin backends keep `stdin=subprocess.DEVNULL` and must use a declared file-read or handle transport. Manifest-loaded Claude/Codex/Cursor backends must declare which transport they use, and compatibility tests assert grounded content is absent from `batch_argv` and `streaming_argv` output. Step 3 then skip/detects binary files during grounding by testing for NUL in the first N bytes or honoring `.gitignore` / a text-extension allowlist, and records `candidate_text_files`, `grounded_files`, `skipped_binary_files`, and `unreadable_files` on the annotation/report contract so step 5 can distinguish a fully grounded small plan from incomplete grounding. The raw `ValueError` becomes 'grounding skipped binary file <path>'. The `subprocess` docs confirm the safe primitives: `run(..., input=...)` pipes bytes/str to the child's stdin (auto-creating the `PIPE`), while temp/file-handle transports keep grounded bytes off argv when stdin must remain closed.

P2 — grounding-floor guard: step 4 introduces `NEEDS-REVIEW` as the explicit uncertainty status, and step 5 reuses it when grounding is genuinely incomplete. Low-grounding sections that the model labeled `IMPLEMENTED` are demoted to `NEEDS-REVIEW` with reason `low-grounding`; low-grounding `IMPLEMENTED` sections render into the carryover seed as review-required verification work so they do not disappear from unattended follow-up. Low-grounding `PARTIAL` sections keep their remaining-work text and are rendered into the carryover seed as review-required follow-up rather than being excluded. Demotion fires when `grounded_files == 0` regardless of candidate counts, or when `grounded_files` is below the threshold (e.g. < 3) and step 3's candidate accounting shows either at least that many candidate text files or skipped/unreadable candidates. Small plans with one or two candidate text files keep their verdicts only when every candidate was grounded; they still show the grounding counts. `NOT-IMPLEMENTED` remains `NOT-IMPLEMENTED` because it is already conservative carryover work. The report gets a banner ('Low grounding (N files) — verdicts are speculative, verify before trusting'), and the console summary line surfaces `grounded_files`, `candidate_text_files`, and skipped/unreadable counts, not just the report HTML comment. Step 9 counts `NEEDS-REVIEW` separately so these sections do not disappear from operator rollups. Optional non-plan doc detection (exec summary / diagrams / jira export) stays deferred.

P3 — batch form `plan-tool annotate <path-or-glob>... --archive --seed-dir ... --report-dir ...` that loops, continues past per-file failures (see P1), and prints a coverage + grounding summary table; accepting one or more positional inputs covers both quoted internal globs and shell-expanded unquoted globs. The `--seed-dir`/`--report-dir` pair (vs. per-file `--seed`/`--report`) is the missing primitive; legacy single-output `--seed` and `--report` remain valid only for exactly one resolved input and are rejected with multiple inputs, directories, or globs that resolve to more than one plan. Directory/glob expansion uses the stdlib `glob`/`pathlib` matchers (`glob.glob`, `Path.glob`) — note results come back in no particular order, so sort before reporting for stable output. Batch expansion only treats active plan markdown files as inputs: exclude `archive/`, `plan-details/`, generated `*.annotated.md`, generated seed files, and report artifacts. A zero-match batch exits 2 with a clear "no plans matched" error. All-success exits 0, partial-success exits 1 after printing the summary, and total-failure exits 1. An archive collision, detail-bundle move failure, or rollback failure is a per-file failure even if report/seed writing succeeded; the archive code must either roll back to source-retained state or report the row as `archive failed/partial move requires manual recovery`, never as a successful drain. Derived output names include enough path context to avoid collisions when two inputs share a stem (for example a sanitized relative-parent prefix plus stem); if a collision still remains, fail that input loudly rather than overwriting a seed/report.

P6 — on target collision, finish the remaining disambiguation path and make markdown + detail-bundle moves succeed or fail together. The disambiguation helper allocates a single archive suffix for the source markdown and its sibling detail bundle: `<stem>.replaced.N.md` for the markdown and `archive/plan-details/<slug>.replaced.N/` for the bundle, with `N` omitted for the first free target only when both targets are free. If either target cannot be reserved or moved, neither success message is emitted; partial moves are rolled back when possible, and otherwise returned as an explicit manual-recovery failure that batch mode cannot summarize as source-retained success. The already-shipped loud-collision behavior must not regress, and the existing `create --from-existing` source-archival flow must receive the same collision semantics as annotate; this plan does not add a new `create --archive` flag.

P4 — reject `--iterate` outright on annotate (already documented as reserved/inert); document a 'sweep layout' recipe (seed→`plan-seeds/`, report+original→`archive/`) so the default report location beside the now-archived source isn't a trap.

P7 — `plan-tool list --status` (or extend `sweep --report-only`) emits a one-shot rollup across manifest + on-disk plans: name, IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED/NEEDS-REVIEW counts, `grounded_files`, last annotated date; reads cached `*.annotated.md` where present and flags un-annotated plans; optional `--format md` to emit the table on demand from ground truth (never checked in). Step 5 adds stable `annotated_at` and source-plan metadata to `render_annotated_report`, and `list --status` reads that metadata instead of filesystem mtime so copies, archive moves, and checkout changes do not rewrite the reported date. Discovery checks the default sibling reports plus any explicit `--report-dir <d>` supplied to `list --status`; reports are mapped back to plans by the embedded source-plan metadata, so a sweep layout with reports outside the active plan directory does not look un-annotated. When multiple reports map to the same source plan, choose the report with the newest `annotated_at`; if two reports tie on `annotated_at` but disagree on counts, print a duplicate-report warning and choose the lexicographically last path for deterministic output.

P8 — extend `plan-tool jira` with `jira --lint` and keep the generation prompt/tests aligned with the lint categories: no line numbers, import lists, call-site/grep counts, file-size caps, raw infra literals/path names in non-infra stories, or verification-only AC that records evidence without asserting behavior. Prefer automated tests over manual checks where CI can cover it; keep AWS resource names / path literals in the description not the AC unless the story is an infra contract; for verification-only stories separate 'done' (behavior verified) from 'evidence recorded'. Normal `plan-tool jira <plan>` runs the deterministic AC linter on generated stories before writing output; lint failures exit nonzero and print the offending bullets instead of silently producing an invalid export. In append mode, lint covers the full merged export so the command never writes an output file that still contains invalid AC; legacy invalid tickets must be fixed or filtered before append succeeds. `jira --lint <plan>` validates generated stories for that plan without writing the export and without prompting for or persisting epic assignment; for plans that lack an epic, lint mode uses an in-memory placeholder epic key/title sufficient for rendering and never calls the epic assignment writer. `jira --lint --input <path>` validates an existing markdown or JSON export; stdin is out of scope. The existing prompt already covers broad outcome-based AC guidance, so this plan only owns the new lint categories, the post-generation enforcement gate, and their prompt/test alignment.

## References

- [subprocess — Subprocess management (Python 3.13)](https://docs.python.org/3/library/subprocess.html) — Canonical reference for Popen args/stdin/communicate semantics, needed to route grounded content through stdin or input= instead of argv and to understand the NUL-intolerant, length-limited argument vector behind the 'embedded null byte' crash (P5).
- [glob — Unix style pathname pattern expansion (Python 3.13)](https://docs.python.org/3/library/glob.html) — Defines recursive `**` matching, `recursive=`, and hidden-file handling — the primitive for resolving the new `annotate <dir-or-glob>` batch form (P3).
- [pathlib — Object-oriented filesystem paths (Python 3.13)](https://docs.python.org/3/library/pathlib.html) — Documents Path.glob/rglob, case sensitivity, and read_bytes for directory expansion and reading the first N bytes to detect binary/NUL-bearing assets during grounding (P3, P5).
- [shutil — High-level file operations (Python 3.13)](https://docs.python.org/3/library/shutil.html) — Explains shutil.move semantics (os.rename vs copy fallback, existing-destination overwrite behavior) that the archive step must reason about to make the move atomic and detect target-name collisions rather than report false success (P6).
- [tempfile — Generate temporary files and directories (Python 3.13)](https://docs.python.org/3/library/tempfile.html) — Reference for NamedTemporaryFile/mkstemp, the alternative to stdin for handing large grounded content to the Claude subprocess without placing file bytes in argv (P5).
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — Authoritative list of `claude` flags (`-p`, `--output-format`, `--input-format stream-json`, `--verbose`) the invoker seam shells out to, needed when adjusting how grounded content is fed to and parsed back from the subprocess.
- [Claude Code headless / programmatic mode](https://docs.claude.com/en/docs/claude-code/headless) — Documents non-interactive stream-json input/output and structured-output fields for scripted, unattended invocation — the contract underpinning a batch sweep that must continue past per-file failures (P1, P3).

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Per-issue / live Jira reconciliation — plan-tool emits exports *into the repo* and cannot read *live* Jira, so reconciling generated stories against the board stays a human/integration task; better generated AC only shrinks it.
- Checked-in status snapshots — the rollup (P7) is generated on demand from ground truth, deliberately never persisted as a file that would rot.

## Risks

- P1's contradiction is confirmed LLM nondeterminism (a re-run of the same command succeeded), so a retry mitigates but cannot guarantee; graceful per-section degrade is the durable fix and the validator should never hard-abort on a transient contradiction.
- The grounding-floor threshold (e.g. < 3 files) is a heuristic — risk of suppressing legitimate verdicts on small-but-real plans; mitigated by demoting only when enough candidate text files existed or candidates were skipped/unreadable, while one- or two-file plans with every candidate grounded keep their verdicts.
- Binary detection via 'NUL in first N bytes' may misclassify some files; mitigated by also honoring `.gitignore` / a text-extension allowlist and by sanitizing (strip NUL, cap length) at the subprocess boundary as a backstop.
- Doc-type detection (exec summary / diagram / jira export short-circuit) risks misfiling a genuine code-bearing plan as non-plan; keep it conservative.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — behavior-preserving tests pinned before the change and pass unchanged after; includes the prompt-transport seam and `plan_tool/launcher.py` streaming paths while still rendering current argv bytes.
- step 2 (feature) — unit tests added with the implementation; green before completion, including backend declarations that do not treat a temp path as prompt text, absence of grounded bytes from batch/streaming argv, and strip-NUL/length-cap sanitization for prompt/model/project/backend-manifest strings crossing the subprocess boundary.
- step 3 (feature) — unit tests added with the implementation; green before completion, including candidate/skipped/unreadable grounding counts on the annotation/report contract.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion, including zero-grounding demotion, low-grounding IMPLEMENTED demotion to NEEDS-REVIEW, low-grounding PARTIAL review-required seed carryover, contradiction-derived NEEDS-REVIEW exclusion, banner rendering, `annotated_at` metadata, candidate/skipped summary output, and small fully-grounded plan exemption.
- step 6 (feature) — unit tests added with the implementation; green before completion, including paired markdown/detail-bundle disambiguation and no false archived success on partial failure.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (feature) — new CLI behavior tests added with the implementation; cover quoted glob, shell-expanded multi-path input, directory expansion, rejection of `--seed`/`--report` with multi-input batches, archive/detail/seed/report exclusion, zero-match exit 2, per-file failure continuation, archive failure/source-retained and manual-recovery row classification, aggregate exit status, duplicate-stem output collision policy, summary rows, and output/archive paths.
- step 9 (feature) — unit tests added with the implementation; green before completion, including NEEDS-REVIEW counts, `--report-dir` discovery, source metadata mapping, newest-report selection, duplicate-report warning ties, and stable date extraction from report metadata rather than mtime.
- step 10 (feature) — unit tests added with the implementation; green before completion, including generated-plan lint mode with placeholder epic context and without epic side effects, `--input` lint mode for existing markdown/JSON exports, infra/path literal linting outside infra contracts, and verification-evidence-only AC linting.
- step 11 (feature) — unit tests added with the implementation; green before completion, including post-generation lint enforcement and append-mode full-merged-output linting after the prompt is aligned to the new categories.
- step 12 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- A single contradictory section (`NOT-IMPLEMENTED` + `code_refs`) does not abort the run: `annotate` exits having written both the report and seed, with that section marked `NEEDS-REVIEW` and excluded from the carryover seed.
- `annotate` on a plan whose repo contains binary assets (the `3-bundle-size-optimization` case) completes without raising `ValueError: embedded null byte`; binary files are skipped/reported during grounding rather than read into a subprocess argument.
- Grounded content reaches backend subprocesses through the declared backend prompt-transport seam; no grounded file bytes are placed in `batch_argv` or `streaming_argv` for Claude, Codex, Cursor, or manifest-loaded backends, and temp-file transports use backend-declared file-read syntax rather than passing the temp path as the prompt text.
- Prompt/model/project/backend-manifest strings crossing `plan_tool/shell.py` or `plan_tool/launcher.py` subprocess boundaries are NUL-stripped and length-capped before process spawn.
- Annotate reports record `candidate_text_files`, `grounded_files`, `skipped_binary_files`, and `unreadable_files` so low-grounding decisions are auditable.
- Strings crossing the subprocess boundary are sanitized with NUL stripping and length caps even after binary files are skipped.
- `plan-tool annotate <path-or-glob>... --archive --seed-dir <d> --report-dir <d>` processes every matched active plan from quoted globs, unquoted shell-expanded multi-path input, or directories; rejects legacy `--seed`/`--report` single-output flags when more than one input resolves; excludes `archive/`, `plan-details/`, generated `*.annotated.md`, seed files, and report artifacts; continues past a per-file failure; and prints a coverage + grounding summary table at the end.
- Batch annotate exits 0 when every matched plan succeeds, 1 when at least one matched plan fails, and 2 when no plan matches.
- Archive collision or detail-bundle move failure marks that annotate invocation, and its batch row, failed even if report/seed writing succeeded; the row distinguishes source-retained rollback from partial-move manual recovery.
- Batch output names do not overwrite when two matched plans share a stem; they include sanitized relative path context or fail the colliding input loudly.
- A report with `grounded_files == 0` or otherwise incomplete grounding demotes confident `IMPLEMENTED` sections to `NEEDS-REVIEW` and carries them into the seed as review-required verification work, carries low-grounding `PARTIAL` remaining-work into the seed as review-required follow-up, and carries a report-level low-grounding banner; contradiction-derived `NEEDS-REVIEW` sections are excluded from the seed, and one- or two-file plans with every candidate text file grounded are not demoted solely for being small.
- The console summary line for each plan includes its `grounded_files` count.
- `--archive` against an occupied `archive/<stem>.replaced.md` target either errors clearly or writes a paired non-colliding markdown/bundle name (`<stem>.replaced.2.md` and `archive/plan-details/<slug>.replaced.2/`); it never reports 'archived' while the original remains in the active dir or while its detail bundle failed to move.
- `--iterate` passed to `annotate` is rejected with a clear error (not silently accepted).
- `plan-tool list --status --report-dir <d>` prints a rollup table (name, IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED/NEEDS-REVIEW counts, `grounded_files`, last annotated date from report metadata) and flags un-annotated plans; reports outside the active plan directory map back by embedded source metadata; duplicate reports for the same source use newest `annotated_at` with deterministic tie handling; `--format md` emits the equivalent markdown table.
- `plan-tool jira` output contains no line numbers, grep/call-site counts, import lists, file-size-cap bullets, raw infra/path literals in non-infra story AC, or verification-evidence-only AC; normal generation and append mode fail before writing invalid output when the deterministic linter catches those bullets in the full would-be output; `jira --lint <plan>` uses in-memory placeholder epic context when needed and `jira --lint --input <path>` flags any such bullet without epic prompt/persistence side effects.

## Deferred

- `DESCRIPTIVE`/`NON-ACTIONABLE` section classification (P1) — separate concern; step 4's `NEEDS-REVIEW` degrade resolves the hard-abort without a new verdict taxonomy.
- Validator relaxation so `NOT-IMPLEMENTED` + `code_refs` is contradictory only for *actionable* sections (P1) — postponed; the graceful degrade path supersedes reclassifying the contradiction rule.
- Built-in annotate retry for the transient-nondeterminism case (P1) — separate concern; checkpoint/resume already exists and per-section degrade is the durable fix.
- Non-plan doc-type detection / short-circuit for exec summaries, diagrams, and jira exports (P2) — postponed; risks misfiling a genuine code-bearing plan, kept out until the grounding-floor banner proves insufficient.
