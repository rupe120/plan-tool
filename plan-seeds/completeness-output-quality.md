# Plan seed: completeness/convergence output quality — severity highlighting, re-audit recommendation, consistent next-steps, drop stale `--apply`

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/completeness-output-quality.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Scope: terminal-output quality for the completeness/convergence surface.**
> Four changes, all on the same surface (the iterate-loop progress lines, the
> disposition summary, and the "Next steps" block). No change to *what* the
> audit finds or applies — only how findings and next actions are **rendered**.

---

## Overview

Improve the terminal output of `completeness-audit` (and the shared convergence
loop) along four axes:

1. **Severity highlighting** — paint the high/medium/low/critical indication on
   correctness findings in the convergence output so the operator can scan
   severity at a glance, instead of reading `plan-correctness/high` as
   undifferentiated text.
2. **Re-audit-after-apply recommendation** — when the loop **applied** (or left
   open) any **high or critical** finding, in either correctness *or*
   completeness, surface a next-step recommending a fresh `completeness-audit`
   to confirm the applied edits actually converged. Applying a high-severity
   finding mutates the plan; only a re-audit confirms it converged rather than
   shifting the problem.
3. **Consistent "Next steps" format** — the per-process "Next steps" blocks
   (`completeness`, `create`, `detail`, the reconcile walks) render in
   divergent shapes today. Route them through **one shared renderer** so the
   block looks the same everywhere (same header, same indent, same
   command-then-comment alignment).
4. **Drop the stale `--apply` flag** — `completeness-apply` has **no `--apply`
   option** (it was removed; the deterministic files-coherence fix now runs
   unconditionally on every invocation), yet the tool still prints
   `plan-tool completeness-apply <plan> --apply` in several next-step/help
   strings. Every such hint emits a command that errors. Remove `--apply` from
   them.

## Problem statement

The completeness/convergence output is the operator's primary read on plan
health, and it has three rough edges plus one outright bug:

- **Severity is unhighlighted.** The iteration lines (`[1/3]
  plan-correctness/high: …`), the deterministic summary (`4 open finding(s):
  2 high, 1 medium, 1 nit`), and the per-finding enumeration all print severity
  as plain text. `style.py` already has `paint()` / `color_enabled()` and
  `BOLD_RED` / `BOLD_YELLOW` / `DIM` constants — the output just doesn't use
  them for severity.
- **A high-severity apply doesn't prompt re-verification.** The loop re-checks
  only *deterministic* gates after applying (`re-checking after applies …; no
  new claude audit`), then can stop at `no_blocking_findings`. So a run that
  auto-applied two HIGH correctness findings declares itself converged without
  ever re-sampling the conceptual audit against the now-mutated plan — exactly
  the case where a fresh audit is most warranted.
- **"Next steps" blocks are inconsistent.** `completeness_report.py` has
  `suggested_next_step_commands` / `_print_next_steps`; `create.py` and
  `detail.py` print their own `Next steps:` blocks in a different shape. Same
  concept, three renderings.
- **`--apply` is a removed flag still being recommended.** Stale references:
  `plan_tool/completeness_report.py:167`, `:324`, `:477`, and
  `plan_tool/cli/completeness_cmd.py:441`. Each tells the operator to run a
  command that argparse rejects.

## Design

### Severity highlighting (`style.py` + `cli/completeness_cmd.py`)

Add a small `style.severity(label, sev, *, enabled)` helper (or extend `paint`
call sites) mapping severity → color: `critical`/`high` → `BOLD_RED`, `medium`
→ `BOLD_YELLOW`/`YELLOW`, `low`/`nit`/`info` → `DIM`. Apply it in
`_finding_progress_label` (the `<source>/<severity>: <title>` line) and
`_fmt_finding_counts` (the `2 high, 1 medium` breakdown), honoring
`color_enabled(sys.stderr)` so piped/non-TTY output stays plain. Correctness
findings are the focus, but the same painter applies uniformly to completeness
counts.

### Re-audit recommendation (`completeness_report.py` console summary / next-steps)

`console_summary` already receives `applied` / `open_findings` and computes
`has_blocking_findings`. Thread the severity of applied findings through (the
`AppliedOutcome` carries the `Recommendation`, which has `.severity`) and, when
any applied-or-open finding is `high`/`critical` (correctness OR completeness),
emit a next-step:

```
⚠ N high/critical finding(s) were applied — re-run to confirm they converged:
    plan-tool completeness-audit <plan>
```

This is advisory (rc unaffected — exit-code convention). It is the per-run,
single-finding analogue of the cross-run non-convergence signal documented in
RUNBOOK ("when repeated audit/apply doesn't converge").

### One shared "Next steps" renderer

Extract the next-steps formatting (header line + `  command   # comment`
aligned rows) into a single helper — `style.next_steps(rows)` or a function in
`completeness_report.py` — and route `completeness`, `create`, `detail`, and
the reconcile/review walks through it. Behavior-preserving for *content*; it
unifies only the *shape*. Keep each process's actual command list; share the
rendering.

### Drop `--apply`

Remove `--apply` from the four cited strings. The accompanying prose should say
plainly that `plan-tool completeness-apply <plan>` runs the deterministic
files-coherence fix unconditionally (and walks conceptual gaps interactively on
a TTY) — no flag needed. Verify against the live parser that `completeness-apply`
exposes no `--apply` so the fix doesn't reintroduce a phantom flag.

## Step decomposition (apply the single-concern rule — BACKLOG #58)

Propose **pure, single-concern steps** (this plan should model the discipline it
lives next to). Suggested shape:

- **Bugfix step** — drop the stale `--apply` from the 4 cited strings; assert
  via the parser that no `--apply` option exists. One concern, isolated.
- **Refactor step** — extract the shared next-steps renderer and route all four
  processes through it; behavior-preserving except unified format. Existing
  next-steps tests stay green; add a shared-format test.
- **Feature step** — severity highlighting via `style.py`, applied in the
  completeness output (counts + per-finding label), gated on `color_enabled`.
- **Feature step** — the re-audit-after-apply recommendation when a
  high/critical finding was applied/open.

Keep severity-highlighting (output painting) and the re-audit recommendation
(a new conditional next-step) as **separate** steps — they share a file but are
distinct concerns (rendering vs. a new advisory action).

## Out of scope

- Changing what the audit finds, how it samples, or what it auto-applies — this
  is rendering + one advisory next-step only.
- Color for any surface other than the completeness/convergence output (no broad
  re-theming).
- Forcing the re-audit automatically — it is *recommended*, never auto-run
  (would spend Claude unattended against the minimize-Claude posture).

## Risks

- **Color leaking into pipes/CI.** Severity: medium (garbles logs / breaks
  string asserts). Mitigation: every painted string goes through
  `color_enabled(stream)`; tests assert plain output on a non-TTY.
- **Next-steps consolidation drops a process-specific hint.** Severity: medium.
  Mitigation: behavior-preserving refactor — keep each caller's command list,
  share only the renderer; pin existing per-process next-steps tests.
- **Re-audit nag fires too eagerly.** Severity: low (advisory noise).
  Mitigation: trigger only on `high`/`critical` (not medium), and only when
  such a finding was actually applied or left open.

## Acceptance criteria

- Correctness findings in the convergence output render severity with color
  (critical/high red, medium yellow, low/nit/info dim) on a TTY, and **plain**
  on a non-TTY / pipe (`color_enabled`-gated).
- When the loop applies or leaves open a `high`/`critical` finding (correctness
  or completeness), the output prints a next-step recommending a fresh
  `plan-tool completeness-audit <plan>`; rc stays 0 (exit-code convention).
- `completeness`, `create`, `detail`, and the reconcile/review walks render
  their "Next steps" block through one shared renderer (identical header /
  indent / alignment).
- No tool output prints `completeness-apply … --apply`; the 4 cited strings are
  fixed and a test asserts the parser exposes no `--apply` option.
- Existing `completeness_report` / `completeness_cmd` / `create` / `detail`
  output tests stay green; new tests cover the painter, the re-audit trigger,
  the shared renderer, and the `--apply` removal.

## Deferred

- Severity color in the persisted markdown report (the report is read in many
  renderers; keep it plain for now).
- A machine-readable `--json` severity/next-step surface for CI.
- Auto-running the recommended re-audit behind an explicit opt-in flag.

## References

- `plan_tool/completeness_report.py` — current completeness summaries and
  next-step rendering cited by this seed.
- `plan_tool/cli/completeness_cmd.py` — terminal progress and stale command
  hints in the completeness CLI surface.
