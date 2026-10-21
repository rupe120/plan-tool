> **Replaced**: this file has been superseded by `docs/implementation-plans/2-security-check-command.md`.
> Preserved here for history; do not edit.

## Overview

Adds a first-class **security** subcommand that reviews and reconciles either the **plan** or the **code** for security concerns, and wires its findings into the **plan-wide completeness** report as a new security dimension. It produces severity-labeled findings (CRITICAL/HIGH/MEDIUM/LOW/NIT) in the same shape as `review`/`completeness`, persists a reusable report, and participates in the `--iterate` convergence loop where findings are applicable. It honors the exit-code convention (exit 0 even with CRITICAL findings; `--fail-on-findings` flips the rc) and runs through the existing `claude`/`codex` backend abstraction.

## Problem statement

Security is **already a per-step review mode**, but only at the per-step level: `prompts/security.md` exists and audits a single step's detail/files for injection, authorization, data exposure, auth handling, input validation, secret handling, and IAM (template vars `${step_id}`, `${step_title}`, `${step_detail}`, `${step_files}`, `${plan_title}`, `${step_index}`, `${step_total}`, `${lessons_section}`; output is a `## Findings` block with severity-prefixed bullets). `security` is in `AVAILABLE_MODES` (`cli/app.py`): `("run", "check", "optimize", "document", "test", "security", "lint")`, runs per-step via `run_step(..., mode="security")`, sweeps done steps via `verify-all --mode security`, and is a read-only (non-mutating) mode in `launcher.py`. The gap this plan fills is **plan-wide** security review + **reconcile** (plan ⇆ code) + **completeness integration** — not the per-step mode, which already exists.

## Architecture

A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean completeness hook; downstream steps assume this unless the detail step pushes back to the user.

A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security.json` with a plan+code fingerprint, following the `resolve_reusable_audit`/`resolve_reusable_reconcile` reuse pattern.

The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.

Reconcile is added by extending the `ReconcileKind` descriptor family (`cli/reconcile.py`) with a `security-reconcile` kind that audits plan-stated security intent against the code's actual security posture and emits drift findings, reusing `resolve_reusable_reconcile` fingerprinting and the `run_auto_reconcile_on_drift` hook so a code change since the last security audit re-triggers it.

The CLI subcommand lives in `cli/security_cmd.py` following the `review_cmd.py` pattern: a `register(subparsers) -> dict[str, Handler]` export and a `cmd_security(args) -> int` handler, added to the command-module registry and to `CANONICAL_COMMAND_ORDER` in `parser.py`, with `--fail-on-findings` support.

Completeness integration adds a deterministic pre-pass plus a claude security dimension to `completeness_phases.py`: the security audit call is added alongside `_run_deterministic_checks()` but joins the conceptual (claude-backed) layer rather than the deterministic one; security findings are grouped in `_render_grouped_report()` as their own labeled section; and a `security` bucket is added to `_render_completeness_json()`. Cost is gated — the security dimension runs only when the plan touches security-relevant files/areas, or behind an explicit `--with-security` flag if always-on is too expensive — with the default decided in the detail step.

For convergence/`--iterate`, security findings are mostly **advisory** (humans decide), like plan-completeness findings, so by default they are surfaced and **not** auto-applied; only clearly-mechanical fixes (e.g. a hardcoded secret the plan body itself contains) are apply-eligible via an explicit, conservative auto-apply allowlist, with everything else deferred and reported.

## Out of scope

- **No new per-step mode** — `--mode security` already exists; this plan does not re-implement it. The new command may *call* the same `prompts/security.md` for code audit, but the per-step run path is unchanged.
- **No SAST/dependency-scanner integration** — this is claude-backed semantic review of the plan and changed code, not a wrapper around `bandit`, `semgrep`, `pip-audit`, etc. (could be a future plan).
- **No new backend** — runs through the existing `claude`/`codex` backend abstraction; no security-specific subprocess CLI.
- **No auto-remediation of real vulnerabilities** — findings are advisory by default; the tool does not silently rewrite code to "fix" security issues beyond the conservative mechanical allowlist.
- **No change to the exit-code convention** — findings never force a non-zero rc except via `--fail-on-findings`.

## Risks

- **Cost/latency in completeness** (HIGH) — adding a claude security pass to every `completeness` run can be expensive. Mitigate with the relevance gate / `--with-security` flag (step 6); decide the default deliberately in detail, don't default to always-on without measuring.
- **Overlap with the existing `--mode security`** (MEDIUM) — two security entry points risk confusing users and drifting prompts. Keep `prompts/security.md` as the single source for *code* audit; the new plan-level prompt is additive. Document the split.
- **False-positive noise** (MEDIUM) — security findings skew toward "maybe", so aggressive rollup/severity discipline is needed so the completeness report doesn't drown in LOW/NIT. Reuse the existing findings-summarization/rollup gates rather than inventing new ones.
- **Auto-apply danger** (HIGH) — auto-applying a "security fix" can break behavior or give false assurance. Keep the apply-eligible allowlist tiny and explicit (step 7); default everything to deferred/advisory.
- **Seam coverage gaps** (HIGH) — a missed invoker neutralization means tests silently shell out to real claude. Update TESTING.md's table and the autouse gate in `conftest.py` in the same step that adds the seam (step 3).

## Testing

Mirror-module unit tests: `tests/test_security_audit.py` and `tests/cli/test_security_cmd.py`, plus completeness-integration coverage in the existing completeness tests. Cover: invoker-seam monkeypatching (no real claude via the `shell_security_invoker` seam, with the `conftest.py` gate passing); reusable-report fingerprint hit/miss; the plan-vs-code-vs-reconcile targets; severity parsing/rollup; the completeness security bucket (grouped report from `_render_grouped_report()` and JSON from `_render_completeness_json()`); and the exit-code convention (0 with CRITICAL findings; non-zero only on failure or `--fail-on-findings`). Update `package_surface_help.golden.txt` for the new subcommand.

## Acceptance criteria

- `plan-tool security --target plan <name>` audits the plan body and decomposition for security gaps and prints severity-labeled findings; exits 0 even with CRITICAL findings.
- `plan-tool security --target code <name>` audits the changed code via `prompts/security.md` and prints findings; reuses a saved report when plan+code fingerprints are unchanged.
- `plan-tool security --reconcile <name>` reports drift between the plan's stated security intent and the code's actual posture.
- `plan-tool completeness <name>` includes a **Security** section in both the grouped report and the JSON output (a `security` bucket), populated by the security dimension.
- `--fail-on-findings` flips the rc; without it, a completed audit exits 0 regardless of severity.
- No test spawns the real `claude` binary — the `shell_security_invoker` seam is monkeypatched and the `conftest.py` gate passes.
