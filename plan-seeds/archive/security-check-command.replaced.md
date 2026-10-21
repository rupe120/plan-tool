> **Replaced**: this file has been superseded by `docs/implementation-plans/2-security-check-command.md`.
> Preserved here for history; do not edit.

# Plan seed: a plan-wide security check command + completeness dimension

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/security-check-command.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose
below and proposes a step decomposition. The author then runs
`plan-tool detail` per step to flesh the plan out.

---

## Goal

Add a first-class **security** subcommand that reviews and reconciles
either the **plan** or the **code** for security concerns, and wire
its findings into the **plan-wide completeness** report as a new
security dimension. The command produces severity-labeled findings
(CRITICAL/HIGH/MEDIUM/LOW/NIT) in the same shape as `review` /
`completeness`, persists a reusable report, and participates in the
`--iterate` convergence loop where its findings are applicable.

## Context already in place (pre-this-plan)

Security is **already a per-step review mode** — this plan must build
on that, not duplicate it:

1. **`prompts/security.md` exists.** It audits a single step's
   detail/files for injection, authorization, data exposure, auth
   handling, input validation, secret handling, and IAM. Template
   vars: `${step_id}`, `${step_title}`, `${step_detail}`,
   `${step_files}`, `${plan_title}`, `${step_index}`,
   `${step_total}`, `${lessons_section}`. Output is a `## Findings`
   block with severity-prefixed bullets.
2. **`security` is in `AVAILABLE_MODES`** (`cli/app.py`):
   `("run", "check", "optimize", "document", "test", "security",
   "lint")`. It runs per-step via `run_step(..., mode="security")`
   and sweeps done steps via `verify-all --mode security`. It is a
   read-only (non-mutating) mode in `launcher.py`.

So the gap this plan fills is **plan-wide** security review +
**reconcile** (plan ⇆ code) + **completeness integration** — not the
per-step mode, which exists.

## Scope of work

1. **Decide the command surface (lock in step 1).** Pick one of:
   (a) a new top-level `security` subcommand with `--target plan|code`
   (and a `--reconcile` flag for plan⇆code drift), or
   (b) extend the existing `review` / `reconcile` families with a
   `--security` scope. Recommendation: **(a)** a dedicated
   `security` subcommand, mirroring `review_cmd.py`, because it gets
   its own help, its own reusable-report bucket, and a clean
   completeness hook. Downstream steps assume (a) unless the detail
   step pushes back to the user.

2. **Add the orchestrator `security_audit.py`.** Shape it after
   `review.py:review_plan_full()`. It:
   - takes plan path, repo_root, optional `step_id`, and a target
     (plan vs code vs reconcile);
   - reuses `prompts/security.md` for per-step code audit and adds a
     **plan-level** prompt (`prompts/security-plan.md`) that audits
     the plan's design/decomposition for security gaps (missing
     authz steps, secrets in plan body, unsafe data flows the plan
     bakes in);
   - returns a findings list of the existing `Recommendation` shape
     (id, source, severity, title, body, suggested_action,
     impact/complexity triage tags) so it composes with the rest of
     the tool;
   - persists a reusable report under
     `plan-details/<slug>/reports/<ts>-security.json` with a
     plan+code fingerprint, following the
     `resolve_reusable_audit` / `resolve_reusable_reconcile` reuse
     pattern.

3. **Declare the invoker seam.** Add `shell_security_invoker()` in
   `shell.py` (wrapping `claude_invoke`, returning
   `(exit_code, stdout)`, exit 127 = claude-not-on-PATH fallback).
   Read it as a module-level global in the orchestrator so tests can
   monkeypatch it. Update TESTING.md's neutralization table and the
   `conftest.py` real-backend gate so the new seam is covered.

4. **Add the security reconcile direction.** Extend the
   `ReconcileKind` descriptor family (`cli/reconcile.py`) with a
   `security-reconcile` kind that audits plan-stated security
   intent against the code's actual security posture and emits drift
   findings. Reuse `resolve_reusable_reconcile` fingerprinting and
   the `run_auto_reconcile_on_drift` hook so a code change since the
   last security audit re-triggers it.

5. **Register the CLI subcommand `cli/security_cmd.py`.** Follow the
   `review_cmd.py` pattern: a `register(subparsers) -> dict[str,
   Handler]` export and a `cmd_security(args) -> int` handler. Add it
   to the command-module registry and to
   `CANONICAL_COMMAND_ORDER` in `parser.py`. Honor the **exit-code
   convention**: exit non-zero only on failure-to-complete, never on
   findings; support `--fail-on-findings` to flip rc, mirroring the
   other audit commands.

6. **Wire security into plan-wide completeness.** Add a deterministic
   pre-pass plus a claude security dimension to
   `completeness_phases.py`:
   - add the security audit call alongside `_run_deterministic_checks()`
     (it's claude-backed, so it joins the conceptual layer, not the
     deterministic one — keep that distinction);
   - group security findings in `_render_grouped_report()` as their
     own labeled section;
   - add a `security` bucket to `_render_completeness_json()`.
   Gate the cost: only run the security dimension when the plan
   touches security-relevant files/areas, or behind an explicit
   `--with-security` flag if always-on is too expensive. Decide the
   default in the detail step.

7. **Convergence / `--iterate` behavior.** Security findings are
   mostly **advisory** (humans decide), like plan-completeness
   findings — so by default they are surfaced and **not**
   auto-applied. Only clearly-mechanical fixes (e.g., a hardcoded
   secret the plan body itself contains) are apply-eligible. Make the
   auto-apply allowlist explicit and conservative; everything else is
   deferred and reported. Document this split.

8. **Tests.** Mirror-module unit tests:
   `tests/test_security_audit.py`, `tests/cli/test_security_cmd.py`,
   plus completeness-integration coverage in the existing
   completeness tests. Cover: invoker-seam monkeypatching (no real
   claude), reusable-report fingerprint hit/miss, the
   plan-vs-code-vs-reconcile targets, severity parsing/rollup, the
   completeness security bucket (grouped report + JSON), and the
   exit-code convention (0 with CRITICAL findings; non-zero only on
   failure or `--fail-on-findings`). Update
   `package_surface_help.golden.txt` for the new subcommand.

9. **Docs.** Update README/RUNBOOK with the new command and its
   targets; add the security dimension to the completeness docs; add
   a flow note (mirroring `docs/AUDIT_FLOW.md`) for the
   security/reconcile sequence. Note the relationship to the existing
   per-step `--mode security` so users know which to reach for.

## Non-goals

- **No new per-step mode.** `--mode security` already exists; this
  plan does not re-implement it. The new command may *call* the same
  `prompts/security.md` for code audit, but the per-step run path is
  unchanged.
- **No SAST/dependency-scanner integration.** This is claude-backed
  semantic review of the plan and the changed code, not a wrapper
  around `bandit`, `semgrep`, `pip-audit`, etc. (Could be a future
  plan; out of scope here.)
- **No new backend.** Runs through the existing `claude` / `codex`
  backend abstraction; no security-specific subprocess CLI.
- **No auto-remediation of real vulnerabilities.** Findings are
  advisory by default; the tool does not silently rewrite code to
  "fix" security issues beyond the conservative mechanical allowlist
  in step 7.
- **No change to the exit-code convention.** Findings never force a
  non-zero rc except via `--fail-on-findings`.

## Acceptance criteria (plan-level)

- `plan-tool security --target plan <name>` audits the plan body and
  decomposition for security gaps and prints severity-labeled
  findings; exits 0 even with CRITICAL findings.
- `plan-tool security --target code <name>` audits the changed code
  via `prompts/security.md` and prints findings; reuses a saved
  report when plan+code fingerprints are unchanged.
- `plan-tool security --reconcile <name>` reports drift between the
  plan's stated security intent and the code's actual posture.
- `plan-tool completeness <name>` includes a **Security** section in
  both the grouped report and the JSON output (a `security` bucket),
  populated by the security dimension.
- `--fail-on-findings` flips the rc; without it, a completed audit
  exits 0 regardless of severity.
- No test spawns the real `claude` binary — the
  `shell_security_invoker` seam is monkeypatched and the
  `conftest.py` gate passes.

## Risks

- **Cost/latency in completeness.** Adding a claude security pass to
  every `completeness` run can be expensive. Mitigate with the
  relevance gate / `--with-security` flag (step 6); decide the
  default deliberately in detail, don't default to always-on without
  measuring.
- **Overlap with the existing `--mode security`.** Two security
  entry points risk confusing users and drifting prompts. Keep
  `prompts/security.md` as the single source for *code* audit; the
  new plan-level prompt is additive. Document the split.
- **False-positive noise.** Security findings skew toward "maybe" —
  aggressive rollup/severity discipline is needed so the completeness
  report doesn't drown in LOW/NIT. Reuse the existing
  findings-summarization/rollup gates rather than inventing new ones.
- **Auto-apply danger.** Auto-applying a "security fix" can break
  behavior or give false assurance. Keep the apply-eligible allowlist
  tiny and explicit (step 7); default everything to deferred/advisory.
- **Seam coverage gaps.** A missed invoker neutralization means tests
  silently shell out to real claude. Update TESTING.md's table and
  the autouse gate in the same step that adds the seam (step 3).
