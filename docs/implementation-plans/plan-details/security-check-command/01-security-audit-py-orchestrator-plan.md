# Step 1 — Add `security_audit.py` orchestrator, plan-level prompt, and `shell_security_invoker` seam

## Summary

Adds `plan_tool/security_audit.py` — a new Claude-invoking orchestrator modeled member-for-member on `plan_tool/review.py:review_plan_full()` and `plan_tool/detail.py` — plus its plan-level prompt `plan_tool/prompts/security-plan.md` and the `shell_security_invoker()` seam. `run_security_audit()` dispatches on a `target` of `"plan"` (audits the plan's design/decomposition for security gaps via the new prompt) or `"code"` (reuses the existing `plan_tool/prompts/security.md` per-step prompt), parses the `## Findings` block both prompts emit into the existing `Recommendation` shape (source-labeled `security-plan` / `security-code`), and returns a `SecurityAuditResult`. The load-bearing decision: the invoker seam and findings parser are reused/cloned from `review.py`, never re-authored, and the orchestrator stays a tree leaf (lazy-imports `review`/`launcher` symbols). On green, `import plan_tool.security_audit` succeeds, a stubbed invoker yields parsed severity-labeled findings with the right `source`, and the conftest real-backend gate never fires.

## Table of Contents

- [Why](#why) — what's missing and why a dedicated orchestrator now
- [Files (creates vs edits)](#files-creates-vs-edits) — the three new files plus the TESTING.md seam row
- [Implementation](#implementation) — orchestrator symbols, the new prompt, the invoker seam, the findings parser
- [Tests](#tests) — unit tests for the seam, prompt render, dispatch, and exit-code branches
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — headless-mode and OWASP/CWE grounding for the prompt
- [Deferred](#deferred) — persistence, reconcile, CLI, completeness, parser consolidation

## Why

`security` exists today only as a **per-step** review mode: `plan_tool/prompts/security.md` audits one step's detail/files, it's in `AVAILABLE_MODES` in `plan_tool/cli/app.py`, and `launcher.py` runs it per-step / sweeps done steps. There is **no plan-wide security review** and no orchestrator that produces a reusable, severity-labeled findings list over the whole plan's design. This step lays the foundation the rest of the plan builds on: an overridable invoker seam (so tests neutralize it), a plan-level prompt that judges the plan's *design* for security gaps (missing authz steps, secrets baked into the plan body, unsafe data flows), and a findings list in the existing `Recommendation` shape so steps 2–7 (persistence, reconcile, CLI, completeness, convergence) can compose with the rest of the tool instead of re-parsing prose.

## Files (creates vs edits)

**New files:**
- `plan_tool/security_audit.py` — the orchestrator: `SecurityInvoker` type alias, `shell_security_invoker`, `SecurityError`, `SecurityAuditResult`, `render_security_plan_prompt`, `run_security_audit`, and the `_security_recommendations` parser.
- `plan_tool/prompts/security-plan.md` — the plan-level security audit prompt (sibling of `plan_tool/prompts/plan-audit.md` and `plan_tool/prompts/security.md`).
- `tests/test_security_audit.py` — unit tests mirroring `plan_tool/security_audit.py` per the `plan_tool/X.py → tests/test_X.py` convention.

**Existing files (edits only):**
- `TESTING.md` — add one row to the **Backend fallback seams** table (the `| Production call site | Default invoker | How to neutralize in a test |` table) for `security_audit.py → run_security_audit(invoker=...)`.

## Implementation

### `plan_tool/security_audit.py` (new orchestrator)

Mirror `plan_tool/detail.py` / `plan_tool/review.py` member-for-member (the captured "canonical Claude-invoking-orchestrator template" rule):

- **`SecurityInvoker = Callable[[str], tuple[int, str]]`** — mirror `review.py`'s `Invoker` (returns `(exit_code, stdout)`), **not** detail's `Callable[[str], str]`. The orchestrator needs the exit code to distinguish `127` (backend not on PATH) from non-zero from empty, exactly like `review_plan_full`.
- **`shell_security_invoker(prompt: str) -> tuple[int, str]`** — production default, body is `return claude_invoke(prompt)`. Direct analog of `plan_tool/review.py:shell_review_invoker`. Top-import `from plan_tool.shell import claude_invoke`.
  - **Host it in `plan_tool/security_audit.py`, not `shell.py`.** The plan's `## Architecture` prose says "in `shell.py`", but `shell.py` is **not** in this step's `files:` list, and every sibling (`detail.py:shell_detail_invoker`, `review.py:shell_review_invoker`, `create.py:shell_claude_invoker`) co-locates its `shell_<X>_invoker` with the orchestrator that owns it. Follow the established pattern; placing it in `security_audit.py` keeps the step within footprint and the seam overridable as a module-level global tests monkeypatch.
- **`class SecurityError(Exception)`** — raised only on plan-level failure-to-complete (unparseable plan, unknown explicit `step_id`), matching `DetailError` / `ReviewError`. A clean audit that finds CRITICAL issues does **not** raise (exit-code convention — see `feedback_exit_code_convention`); the CLI in step 3 owns `--fail-on-findings`.
- **`@dataclass(frozen=True) class SecurityAuditResult`** — fields `report: str`, `findings: list["Recommendation"]`, `dry_run: bool = False`, `persisted_path: Optional[Path] = None`, `skipped_steps: int = 0`. Analog of `review.py:ReviewResult`. Under `TYPE_CHECKING`, `from plan_tool.review import Recommendation` (lazy at runtime — see parser below). The `persisted_path` field is defined here (always `None` in step 1 — this step persists nothing) so steps 3 and 4 can read `result.persisted_path` independent of merge order; step 4 is the first to populate it. The `skipped_steps` field (always `0` in step 1 — the single-target audits here never partially cover) makes partial coverage visible: step 4's best-effort `--reconcile` sweep skips a step on a launcher error / non-zero claude exit, so it sets `skipped_steps` to the count of steps it failed to audit, and step 3's `cmd_security` renders it so a sweep that covered 7 of 10 steps is reported as partial rather than read as a clean pass (false assurance, the worst failure mode for a security verb).
- **`render_security_plan_prompt(plan: Plan, plan_path: Path, *, repo_root: Path) -> Optional[str]`** — reads `prompts_dir() / "security-plan.md"`, wraps in `string.Template`, and applies `.safe_substitute(...)` (NOT `.substitute` — a stray `$` in plan prose or ingested code must never raise). Returns `None` when the plan has no body (caller skips the Claude call), mirroring `review.py:render_plan_audit_prompt`. Substitution vars: `plan_title`, `plan_body_block`, `detail_files_block`, `lessons_block`.
  - **Reuse review's bundle renderers** rather than re-authoring bounded reads: lazy-import `_collect_plan_body` and `_format_audit_detail_bundle` from `plan_tool.review` inside the function (keeps `security_audit` a load-graph leaf, mirroring how `detail.py` lazy-imports `review`). `_format_audit_detail_bundle(plan, plan_path, repo_root, *, max_file_bytes)` has a **required keyword-only `max_file_bytes`** param — pass `_AUDIT_DETAIL_FILE_BYTES` (the constant review supplies; lazy-import it alongside the helper) so the reuse is callable as written. Render `lessons_block` via `render_lessons_block(load_lessons(repo_root))` (top-import from `plan_tool.lessons` / `plan_tool.renderer.prompts_dir`).
- **`run_security_audit(plan_path, *, repo_root, plan_name, target="plan", step_id=None, invoker=shell_security_invoker, dry_run=False, reporter=None) -> SecurityAuditResult`** — the entry point, shaped after `review.py:review_plan_full`:
  - `plan = parse_plan(plan_path)`; if `step_id is not None`, call `plan.step_by_id(step_id)` and raise `SecurityError` on `KeyError` (mirror `review_plan_full`).
  - Build the prompt by `target`:
    - `target="plan"` → `render_security_plan_prompt(plan, plan_path, repo_root=repo_root)`; if it returns `None`, short-circuit to an empty-findings result with a "no plan body" note.
    - `target="code"` → reuse the **existing** per-step renderer `plan_tool/renderer.py:render_prompt(plan, step, repo_root=repo_root, mode="security")` over the in-scope step(s). For step 1, require `step_id` for the code target (single-step audit) — `raise SecurityError` when `step_id is None`; `--target code` requires `--step` here and in the CLI (step 3), and the plan-wide multi-step code sweep loop is out of scope — note this in `## Deferred`.
  - Validate `target` against a closed `_SECURITY_TARGETS = ("plan", "code")`; raise `SecurityError` on anything else (`"reconcile"` is **not** handled here — step 4).
  - `if dry_run:` return `SecurityAuditResult(report=prompt, findings=[], dry_run=True)` with **no** invoker call (mirror `review_plan_full`).
  - Call `exit_code, stdout = invoker(prompt)` and branch exactly like `review_plan_full`'s claude block: `127` → "backend not on PATH" note + `[]`; non-zero → "exited with code N" note + `[]`; empty `stdout.strip()` → "empty response" note + `[]`; else parse findings. Use `reporter`/`StderrReporter` for the progress line the same way.
  - On a parseable response, `findings = _security_recommendations(stdout, source=...)` where source is `"security-plan"` for the plan target and `"security-code"` for the code target. The `report` is the raw `stdout` (the `## Findings` block) for step 1 — a richer assembled report is not needed until the CLI renders it (step 3).
- **`_security_recommendations(stdout: str, *, source: str) -> list["Recommendation"]`** — the foundational logic: **parse a `## Findings` block of severity-prefixed bullets into source-labeled `Recommendation`s.** Clone `plan_tool/review.py:_claude_recommendations` but parametrize `source`:
  - Lazy-import inside the function (review→launcher→parser→schema is a load cycle if hoisted, per the detail.py precedent): `from plan_tool.launcher import parse_finding_bullets` and `from plan_tool.review import Recommendation, _CLAUDE_SEVERITY_MAP, _make_rec_id, _split_triage_tags, _split_audit_fix`.
  - For each bullet: map severity via `_CLAUDE_SEVERITY_MAP` (default `"info"`), split triage tags and the `→ fix:` remediation off the body, derive `title` from the first body line, and build `Recommendation(id=_make_rec_id(None, source, body), source=source, severity=sev, step_id=None, title=..., body=..., suggested_action=fix, impact=..., complexity=...)`.
  - **Severity-blocking policy:** `_CLAUDE_SEVERITY_MAP` folds `LOW`→`medium`, which `convergence.is_blocking` would treat as blocking; per the plan's non-blocking policy for security `LOW`/`NIT`, do **not** reuse that fold unchanged — map security `LOW`→`"nit"` (the canonical `Recommendation.severity` set is `{critical, high, medium, nit, info}` and has no `low`; `nit` is the nearest non-blocking level, keeping `NIT`→`"nit"`) so both stay outside `convergence.BLOCKING_SEVERITIES` (`{"medium", "high", "critical"}`) and never flip `--fail-on-findings` (step 3) or `has_blocking_findings` (step 5). Only `MEDIUM`/`HIGH`/`CRITICAL` security findings are blocking.
  - **Returning `[]` on a clean audit is correct here**, NOT a swallowed error: `parse_finding_bullets` returns `[]` for a `## Findings` / `_(none)_` block, which is the legitimate "no security issues" outcome (unlike the annotate clone, which had no interactive fallback and had to raise). A missing/garbled response is already handled upstream as a skipped-note branch, so `_security_recommendations` never needs to raise.

**Foundational-logic shared locations** (cited here, not under a new heading):
- `plan_tool/launcher.py:parse_finding_bullets` — the canonical `## Findings` bullet parser. **Reuse it** (don't re-author extraction); the existing `plan_tool/prompts/security.md` already emits the exact machine-parsed block it consumes.
- `plan_tool/review.py:_claude_recommendations` — the sibling bullet→`Recommendation` mapper, hardcoded to `source="claude"`. `_security_recommendations` is a deliberate near-clone with a `source` parameter; **consolidating the two into one source-parametrized helper is a refactor `detail` cannot mint** → routed to `## Deferred`.

### `plan_tool/prompts/security-plan.md` (new prompt)

- Model on `plan_tool/prompts/plan-audit.md` (plan-level, design-focused) crossed with `plan_tool/prompts/security.md` (the security category checklist). Substitution vars (must match `render_security_plan_prompt`): `${plan_title}`, `${plan_body_block}`, `${detail_files_block}`, `${lessons_block}`.
- Audit the plan's **design/decomposition** for security gaps: missing authorization/ownership steps, secrets or credentials present in the plan body, unsafe data flows the plan bakes in, missing input-validation/boundary steps, over-broad IAM the plan prescribes. Cover the OWASP Top 10 / CWE categories (injection, broken access control, secrets exposure, auth handling).
- Instruct **Read/Grep only — do not edit**, and "use only checked-in project documentation and the code itself — do not consult LLM-specific guidance files (CLAUDE.md, AGENTS.md, .cursor/rules, copilot-instructions.md)", matching `security.md` and `plan-audit.md`.
- **End with the exact `## Findings` contract** `security.md` uses (UPPERCASE severity-prefixed bullets, `_(none)_` when clean) so `parse_finding_bullets` parses it unchanged. This is the load-bearing cross-seam contract.

### `TESTING.md` (edit)

- Append one row to the **Backend fallback seams** table: `| security_audit.py → run_security_audit(invoker=...) | shell_security_invoker | Pass invoker=lambda p: (0, "## Findings\\n…") returning a canned (exit, stdout) tuple, OR monkeypatch security_audit.shell_security_invoker. |`. The table's closing instruction ("When you add a new orchestrator with a real-backend default, add a row here") makes this mandatory.

## Tests

All in `tests/test_security_audit.py`. Unmarked unit tests (no `main()`); drive `run_security_audit` / the helpers directly with stubbed invokers. None carries `@pytest.mark.allow_real_claude` — the conftest real-backend gate staying green is itself an assertion the seam is overridable.

### Test-creation order (feature step)

This is a **feature** step — write these tests alongside the implementation; every one must be green before the step is done.

- `test_import_security_audit_module` — `import plan_tool.security_audit` succeeds (matches the frontmatter gate `uv run python -c "import plan_tool.security_audit"`).
- `test_shell_security_invoker_delegates_to_claude_invoke` — monkeypatch `plan_tool.shell.claude_invoke` to a recorder returning `(0, "out")`; assert `shell_security_invoker("p")` returns that tuple and forwards the prompt.
- `test_render_security_plan_prompt_substitutes` — rendered prompt contains the plan title and body; the `## Findings` contract text is present.
- `test_render_security_plan_prompt_safe_substitute_tolerates_dollar` — a plan body containing a stray `$VAR` renders without raising (proves `safe_substitute`).
- `test_render_security_plan_prompt_none_on_empty_body` — a plan with no body returns `None`.
- `test_run_security_audit_plan_target_parses_findings` — stub invoker returns a canned `## Findings` block with CRITICAL/HIGH bullets; assert findings parsed, `source == "security-plan"`, severities mapped via `_CLAUDE_SEVERITY_MAP`.
- `test_run_security_audit_code_target_uses_security_md` — `target="code"`, `step_id` set; assert the prompt was rendered from `security.md` (step context present) and findings carry `source == "security-code"`.
- `test_run_security_audit_code_target_requires_step_id` — `target="code"` with `step_id=None` raises `SecurityError` (single-step audit requires an explicit step; `--target code` requires `--step` in the CLI too, and the plan-wide code sweep is out of scope).
- `test_run_security_audit_clean_findings_empty` — stub returns `## Findings` + `_(none)_`; result `findings == []`, no raise.
- `test_run_security_audit_critical_finding_does_not_raise` — CRITICAL present; `run_security_audit` returns normally (exit-code convention; rc is the CLI's concern).
- `test_run_security_audit_exit_127_skips` — invoker returns `(127, "")`; result has `findings == []` and a "not found" note, no raise.
- `test_run_security_audit_nonzero_exit_skips` — invoker returns `(2, "")`; `findings == []`, skipped note.
- `test_run_security_audit_empty_stdout_note` — invoker returns `(0, "")`; `findings == []`, empty-response note.
- `test_run_security_audit_dry_run_no_invoker_call` — `dry_run=True` with a recorder invoker that raises if called; `report` carries the prompt, `findings == []`, invoker never called.
- `test_run_security_audit_unknown_step_id_raises` — `step_id` absent from the plan raises `SecurityError`.
- `test_run_security_audit_invalid_target_raises` — `target="reconcile"` (or any non-member) raises `SecurityError` (reconcile is step 4).

## Acceptance criteria

- `import plan_tool.security_audit` succeeds (frontmatter gate passes).
- `plan_tool/prompts/security-plan.md` exists, substitutes `${plan_title}`/`${plan_body_block}`/`${detail_files_block}`/`${lessons_block}`, and ends with a `## Findings` block matching the `parse_finding_bullets` contract.
- `shell_security_invoker(prompt)` returns a `(int, str)` tuple from `claude_invoke`.
- `run_security_audit(..., target="plan")` over a stubbed invoker returns a `SecurityAuditResult` whose `findings` are `Recommendation`s with `source="security-plan"`; `target="code"` yields `source="security-code"`.
- A CRITICAL finding returns rc-normally (no raise); a clean `_(none)_` block yields `findings == []`.
- Exit codes 127 / non-zero / empty-stdout each produce `findings == []` with a skipped note, no raise.
- Every `tests/test_security_audit.py` test is green under `uv run pytest tests/test_security_audit.py -q`, with no `allow_real_claude` marker (conftest gate confirms no real backend spawn).
- `TESTING.md`'s Backend fallback seams table has a `security_audit.py` row.

## References

- [Claude Code Headless Mode (Anthropic docs)https: — `-p/--print`, `--output-format stream-json`, and the exit-code semantics `shell_security_invoker` relies on (127 = not on PATH) through the `claude`/`codex` backend abstraction.
- [OWASP Top 10 (2021)https: — the risk taxonomy (injection, broken access control, secrets exposure) the new `security-plan.md` prompt grounds its plan-design findings in.
- [CWE — Common Weakness Enumeration (MITRE)https: — the weakness catalog for labeling findings (e.g. CWE-798 hardcoded credentials) consistently with the per-step `security.md` prompt.

## Deferred

- **Reusable `<ts>-security-<target>.json` persistence + `resolve_reusable_security` + plan/code fingerprints** — step 2 (the target is encoded in the filename suffix so reuse is scoped per `--target`); `run_security_audit` returns findings in-memory only here.
- **`reconcile` target (`security-reconcile` ReconcileKind + `run_auto_reconcile_on_drift` hook)** — step 4; `_SECURITY_TARGETS` deliberately excludes `"reconcile"` and raises on it.
- **`security` CLI subcommand (`cli/security_cmd.py`, `--target`/`--reconcile`/`--fail-on-findings`, golden regen, registration seams)** — step 3; no CLI wiring in this step.
- **Completeness integration (security dimension in `completeness_phases.py` / `completeness_cmd.py`, grouped report section, JSON bucket)** — step 5.
- **`--iterate` auto-apply allowlist for mechanical security fixes** — step 7; findings are advisory/report-only here.
- **Plan-wide multi-step code sweep loop** — out of scope for this plan; `--target code` requires `--step` (single-step audit) in step 1 and in the CLI (step 3).
- **Consolidating `_security_recommendations` with `review.py:_claude_recommendations` into one source-parametrized helper** — a refactor step `detail` cannot mint; left for reconcile to surface rather than expanding this footprint.
