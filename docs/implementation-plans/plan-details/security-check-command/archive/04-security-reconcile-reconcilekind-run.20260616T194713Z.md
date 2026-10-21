# Step 4 — Add a `security-reconcile` ReconcileKind + a security-mode `run_auto_reconcile_on_drift` hook

## Summary

Extends the existing reconcile engine to recognize a third sidecar direction and teaches the drift-halt auto-reconcile hook to run a security pass. In `plan_tool/cli/reconcile.py`, add one `security-reconcile` row to `_RECONCILE_KINDS` so the already-kind-parametrized cores (`resolve_reusable_reconcile`, `_find_saved_for_step`, `_prompt_reuse_saved`, `_walk_saved`) locate, freshness-gate, and walk `<ts>-security-reconcile.json` saves with zero new core logic. In `plan_tool/auto_reconcile.py`, parameterize `run_auto_reconcile_on_drift` with `mode` and `save_kind` keyword args (defaulting to `"detail-reconcile"` so today's behavior and its byte-exact operator messages are preserved) so the same best-effort drift-halt hook can run `mode="security-reconcile"` per drifted step and persist `kind="security-reconcile"` findings. The load-bearing decision: deliver three **composable, in-footprint capabilities** (a descriptor row, a parameterized hook, and a dedicated `plan_tool/prompts/security-reconcile.md` drift prompt) without wiring any caller — `plan_tool/cli/security_cmd.py`, `plan_tool/cli/app.py`'s wrapper re-exports, and the iteration-loop call sites are all out of this step's `files:` and are left to the consuming step. On green: `resolve_reusable_reconcile(..., kind_filter="security-reconcile")` verdicts a seeded security sidecar, and `run_auto_reconcile_on_drift(..., mode="security-reconcile", save_kind="security-reconcile")` threads the mode through `run_step`, the source through `extract_reconcile_recommendations`, and the kind through `save_review`.

## Table of Contents

- [Why](#why) — what's missing and why the descriptor + hook land now
- [Files (creates vs edits)](#files-creates-vs-edits) — two production edits plus their two test files
- [Implementation](#implementation) — the `_RECONCILE_KINDS` row, the parameterized hook, and the deliberate non-edits
- [Tests](#tests) — descriptor/resolver cases and the mode/source/kind threading cases
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — OWASP/CWE + headless-mode grounding for the security mode
- [Deferred](#deferred) — caller wiring, named wrappers, apply-eligibility, a dedicated reconcile prompt

## Why

- **The reconcile engine knows two directions, security needs a third.** `plan_tool/cli/reconcile.py:_RECONCILE_KINDS` holds `detail-reconcile` and `run-reconcile`; its own comment states "Adding a direction is one `_RECONCILE_KINDS` row." There is no kind for the security sidecars step 1's `run_security_audit` / a security drift pass produce, so `resolve_reusable_reconcile` cannot freshness-gate them and `_find_saved_for_step` cannot locate them.
- **The drift-halt hook only ever runs `detail-reconcile`.** `plan_tool/auto_reconcile.py:run_auto_reconcile_on_drift` hardcodes `mode="detail-reconcile"`, `source="detail-reconcile"`, and `kind="detail-reconcile"`. The plan's Architecture calls for "a code change since the last security audit re-triggers it" — i.e. the same audit-beats-observe hook running a security pass on drifted steps — which the hardcoded mode can't express.
- **Both halves are pure capability, no caller in this step.** Per `depends_on: 1, 3`, step 1 establishes the security audit concept and step 3 the `security … --reconcile` command, but step 4's `files:` deliberately excludes `plan_tool/cli/security_cmd.py` and `plan_tool/cli/app.py`. This step adds the descriptor and the hook parameter so a later (consuming) step can wire `cmd_security --reconcile` and the iteration loops to them — exactly the degradeable-dependency posture (don't expand footprint to wire an upstream/downstream caller).
- **The already-implemented signal is a partial match, not a done step.** `ReconcileKind` (the class) and `run_auto_reconcile_on_drift` (the function) exist at HEAD, but neither carries any security support — this step extends both; it does not author them from scratch.

## Files (creates vs edits)

**New files:**

- `plan_tool/prompts/security-reconcile.md` — the dedicated plan-vs-code security drift prompt the reconcile direction renders (the architecture-mandated drift prompt; reusing the per-step `plan_tool/prompts/security.md` via `mode="security"` does **not** satisfy plan⇆code drift semantics).

**Existing files (edits only):**

- `plan_tool/cli/reconcile.py` — add one `"security-reconcile"` entry to the `_RECONCILE_KINDS` dict (the `@dataclass(frozen=True) ReconcileKind` family). No new functions: the cores `resolve_reusable_reconcile`, `_find_saved_for_step`, `_ask_reuse_saved`, `_prompt_reuse_saved`, and `_walk_saved` are already keyed on a `ReconcileKind`/`kind_filter` and pick up the new row for free.
- `plan_tool/auto_reconcile.py` — add `mode: str = "detail-reconcile"` and `save_kind: str = "detail-reconcile"` keyword params to `run_auto_reconcile_on_drift`; thread `mode` into the `run_step(..., mode=mode, ...)` call, and `save_kind` into both `extract_reconcile_recommendations(..., source=save_kind)` and `save_review(..., kind=save_kind)`. Update the module + function docstrings to state the hook is direction-parametrized.
- `plan_tool/security_audit.py` — teach `run_security_audit` the `target="reconcile"` branch: add `"reconcile"` to `_SECURITY_TARGETS` and dispatch it to `run_auto_reconcile_on_drift(..., mode="security-reconcile", save_kind="security-reconcile")`, wiring the orchestrator to this step's hook for plan⇆code security drift, then adapt the hook's `int`/self-persist result into the `SecurityAuditResult` step 3's `cmd_security` consumes (see [`run_security_audit` reconcile-result adaptation](#plan_toolsecurity_auditpy--run_security_audit-reconcile-result-adaptation)).
- `tests/cli/test_reconcile_engine.py` — add the `security-reconcile` descriptor + `resolve_reusable_reconcile` cases (new class, sibling of `TestResolveReusableReconcile`).
- `tests/test_auto_reconcile.py` — add the mode/source/kind threading cases (new class, sibling of `TestAutoReconcileStyleOutput`).
- `tests/test_security_audit.py` — add the `target="reconcile"` dispatch case asserting `run_security_audit` routes to the hook with `mode="security-reconcile"` / `save_kind="security-reconcile"`.

## Implementation

### `plan_tool/cli/reconcile.py` — the `security-reconcile` descriptor row

Add to `_RECONCILE_KINDS` alongside `detail-reconcile` / `run-reconcile`:

- `noun="security-reconcile"` — the operator-facing label substituted into all reuse/walk wording.
- `accepted_kinds=frozenset({"security-reconcile"})` — the `saved.kind` allow-set checked after the filename pre-filter in both `_find_saved_for_step` and `resolve_reusable_reconcile`.
- `name_includes="-security-reconcile"` — the substring filename pre-filter against `review_persistence.save_review`'s `<ts>-<kind>.json` output.
- `name_excludes=()` — **no exclusion needed.** `name_includes="-security-reconcile"` cannot match the sibling reconcile filenames `-detail-reconcile`/`-run-reconcile`; and step 2's target-scoped locators match via `endswith("-security-plan.json")` / `endswith("-security-code.json")` (not `_RECONCILE_KINDS`), neither of which a `-security-reconcile.json` name satisfies — so the three `-security-*` families (`-security-plan`, `-security-code`, `-security-reconcile`) are pairwise suffix-disjoint and never collide here. The `accepted_kinds` equality check (`saved.kind == "security-reconcile"`) is the second-line guard if a filename ever collides. This matches the empty `name_excludes` both existing rows carry.
- `honor_no_walk_no_save=False` — the reuse-prompt suppression policy. The security command (step 3, modeled on the thin `plan_tool/cli/gates_cmd.py`) defines neither `--no-walk` nor `--no-save`; `_prompt_reuse_saved` reads them via `getattr(args, …, False)`, so `False` (never suppress on those flags) is correct, mirroring `detail-reconcile`.
- `phase_kind="security-reconcile"` — the `saved_reconcile_reuse` run-log phase tag emitted by `_walk_saved`.
- `walk_verb="Walking"` — security findings are walked interactively (advisory), not redirect-replayed; mirrors `detail-reconcile`'s `"Walking"`, not `run-reconcile`'s `"Replaying"`.
- `empty_message="(saved security-reconcile has no recommendations to walk)"` — the no-recs line, parallel to `detail-reconcile`'s.
- `replay_redirects_only=False` — security findings carry no `## Redirect` block; they route through the interactive `_build_review_action_fn` walk, not the redirect-replay branch.

**No new named wrappers in this step.** The existing per-kind delegators (`_walk_saved_detail_reconcile`, `_prompt_reuse_saved_detail_reconcile`, etc.) exist only so by-name imports resolve, and each is re-exported through the `from plan_tool.cli.reconcile import (…)` block in `plan_tool/cli/app.py` — a file outside this step's `files:`. The kind-generic cores plus `resolve_reusable_reconcile` (already in that re-export block) fully deliver and test the security-reconcile capability without touching `plan_tool/cli/app.py`. Adding `_walk_saved_security_reconcile` / `_prompt_reuse_saved_security_reconcile` / `_find_saved_security_reconcile_for_step` / `_ask_reuse_saved_security_reconcile` belongs to the consuming step that also adds the `plan_tool/cli/app.py` re-export and the `cmd_security --reconcile` reuse-prompt call (see Deferred).

### `plan_tool/auto_reconcile.py` — direction-parametrized drift hook

- **Add two keyword params** to `run_auto_reconcile_on_drift`, both defaulting to `"detail-reconcile"`:
  - `mode: str = "detail-reconcile"` — passed to `run_step(plan_path, …, mode=mode, …)`.
  - `save_kind: str = "detail-reconcile"` — passed to **both** `extract_reconcile_recommendations(result.stdout, step_id=step_id, source=save_kind)` and `save_review(…, kind=save_kind, …)`.
- **Defaults preserve today's behavior byte-for-byte.** Every current call site (the four iteration entry points) omits both, so they keep running `detail-reconcile` and writing `*-detail-reconcile.json`. The three existing message assertions in `tests/test_auto_reconcile.py` stay green unchanged.
- **Security invocation:** a future caller passes `mode="security-reconcile"` (renders the new `plan_tool/prompts/security-reconcile.md` drift prompt via `renderer.render_prompt`'s `prompts/<mode>.md` resolution — authored in this step) and `save_kind="security-reconcile"`. Each drifted step then gets a per-step plan-vs-code security drift audit whose findings persist as `<ts>-security-reconcile.json`.
- **Operator-facing message strings are unchanged.** The "running auto-reconcile on N affected step(s)…", the per-step "K finding(s) raised (saved to …)", the skip-and-unmapped notes, and the `plan-tool detail <slug> --reconcile --step N` recovery hint all stay literal. The recovery hint stays the generic plan⇆code investigation entry point valid for any drift; mode-specific recovery wording (e.g. pointing at `plan-tool security … --reconcile`) is Deferred so the default tests' byte-exact pins don't churn.
- **Best-effort posture is unchanged.** The fingerprint capture (`compute_plan_fingerprint` + `compute_code_fingerprint` wrapped in the existing `try/except (ParseError, ValidationError)` falling back to `plan_fp=""` / `code_fp=None`), the `LauncherError` skip, the non-zero-exit skip, and the `OSError` save-failure fallback all apply identically to the security mode — the new params change only which prompt runs and which kind/source label the findings carry.
- **All params remain keyword-only.** The signature already opens with `*,`, so appending `mode` / `save_kind` cannot break any positional caller.

### `plan_tool/prompts/security-reconcile.md` — the plan-vs-code drift prompt

Author the dedicated drift prompt the reconcile direction renders (via `mode="security-reconcile"` → `renderer.render_prompt`'s `prompts/<mode>.md` resolution). Model it on the existing per-step `plan_tool/prompts/security.md` checklist, but reframe the task as **plan-stated security intent vs. the code's actual posture**: flag where the plan prescribes an authz/ownership/input-validation/secret-handling step the code lacks (or the reverse). Reuse `security.md`'s machine-parsed `## Findings` contract verbatim (UPPERCASE severity-prefixed bullets, `_(none)_` when clean) so `parse_finding_bullets` / `extract_reconcile_recommendations` consume it unchanged. Per the architecture, reusing the per-step `plan_tool/prompts/security.md` via `mode="security"` does **not** satisfy these drift semantics — this prompt is why the reconcile direction renders `security-reconcile.md`, not `security.md`.

### `plan_tool/security_audit.py` — `run_security_audit` reconcile-result adaptation

The reconcile branch bridges two otherwise-incompatible contracts: `run_auto_reconcile_on_drift` returns an **`int` finding count** and **self-persists** one `<ts>-security-reconcile.json` per drifted step (via `save_review`), whereas step 3's `cmd_security` consumes `run_security_audit`'s return as a `SecurityAuditResult`, reading `result.findings` / `result.report` and persisting via `write_security_report`. The branch adapts the hook's output so the consumer contract holds:

- **Reconstruct `findings` from the persisted sidecars, not the count.** After the hook returns, load the recs it just wrote — the freshest `<ts>-security-reconcile.json` per reconciled step, via the same load path `resolve_reusable_reconcile` / `_walk_saved` use — and aggregate them into `SecurityAuditResult.findings`. The hook's `int` return is used only as a count cross-check, never propagated to the caller.
- **Render `report` from the aggregated findings** the same way the `plan` / `code` branches render theirs, so `cmd_security` prints a consistent block regardless of target.
- **Suppress the double-write.** The hook already owns and persisted `<ts>-security-reconcile.json`, so the reconcile-target result is returned already-persisted: `run_security_audit` sets `SecurityAuditResult.persisted_path` (a new `Optional[Path] = None` field added to the step-1 dataclass here) to that sidecar, and step 3's `cmd_security` calls `write_security_report` only when `result.persisted_path is None` (the `plan` / `code` targets), skipping it for the reconcile target. Without this guard the adaptation would write the sidecar twice.

### Foundational logic + parallel locations (deliberate non-edits)

The core rule this step adds: **treat the reconcile direction (run-step mode + sidecar kind + recs source) as data, not a hardcode.** Parallel source-routing locations exercise the same "which source is this" rule and are left untouched on purpose:

- `plan_tool/review.py: _RECONCILE_FIX_SOURCES` (`{"detail-reconcile", "run-reconcile"}`) — `extract_reconcile_recommendations` derives `parse_fix = source in _RECONCILE_FIX_SOURCES`. `"security-reconcile"` is intentionally **absent**, so security findings are not `→ fix:`-split (the `prompts/security-reconcile.md` block emits severity bullets, not inline fix lines). No edit; `plan_tool/review.py` is out of footprint and the default is correct.
- `plan_tool/review_walk.py: _APPLY_AS_FINDING_SOURCES` (`{"detail-reconcile", "claude", "plan-completeness"}`) — `should_apply_as_finding` gates whether a walked rec dispatches to `apply_finding`. `"security-reconcile"` is intentionally **absent**, so saved security findings are surfaced **advisory** (walked/displayed, never auto-applied) — exactly the plan's "security findings are mostly advisory" stance. Promoting any mechanical security-fix subset to apply-eligible is step 7's conservative auto-apply allowlist (`plan_tool/convergence.py`), not this step. No edit; `plan_tool/review_walk.py` is out of footprint.
- `plan_tool/review_persistence.py: _timestamp_filename` templates any non-`"review"` kind verbatim into `<ts>-<kind>.json`, so `save_kind="security-reconcile"` produces `<ts>-security-reconcile.json` with **no** persistence-layer edit (the same generic-suffix property step 2 relies on for `-security-plan.json` / `-security-code.json`).

## Tests

This is a **feature** step — add the unit tests below **with** the implementation; every new test must be green before the step is done. Both files are hermetic (`tmp_path`, the `file=` seam, injected `argparse.Namespace`/`PlanToolContext`), and no test may spawn real `claude` (the `conftest.py` autouse backend gate must stay silent — the security path is exercised only through stubbed `launcher.run_step` and the `file=` seam, never a live invoker).

### `tests/cli/test_reconcile_engine.py` (new class, e.g. `TestSecurityReconcileKind`)

- `test_security_reconcile_kind_registered` — `plan_tool.cli.reconcile._RECONCILE_KINDS["security-reconcile"]` exists with `noun="security-reconcile"`, `name_includes="-security-reconcile"`, `accepted_kinds == frozenset({"security-reconcile"})`, `replay_redirects_only is False`, `walk_verb == "Walking"`. (Import `_RECONCILE_KINDS` from the `plan_tool.cli.reconcile` module — it is not surfaced on the package entry point.)
- `test_resolve_reusable_security_reconcile_fresh` — seed a `<ts>-security-reconcile.json` via `review_persistence.save_review(kind="security-reconcile", plan_fingerprint=…, code_fingerprint=…)` matching current disk; `resolve_reusable_reconcile(plan_name, repo, plan_path=…, kind_filter="security-reconcile")` returns a `ReusableReconcile` with `fresh is True`.
- `test_resolve_reusable_security_reconcile_stale_by_code` — edit an in-scope watched file after the save; resolver returns `fresh is False`, `code_match is False`, non-empty `drifted_code`.
- `test_security_reconcile_kind_isolation` — a `-security-reconcile.json` save is NOT returned for `kind_filter="detail-reconcile"` or `"run-reconcile"`, and a plain `-security.json` (step 2 kind) is NOT returned for `kind_filter="security-reconcile"` (substring-disjointness pin; mirrors the existing `test_kind_filter_isolation`).

### `tests/test_auto_reconcile.py` (new class, e.g. `TestAutoReconcileSecurityMode`)

Reuse the existing `_mapped(tmp_path)` + `_stub_run_loop` shape, but replace the lambda stubs with recorders that capture call kwargs:

- `test_security_mode_threads_mode_into_run_step` — call with `mode="security-reconcile", save_kind="security-reconcile"`; assert the recording `run_step` stub saw `mode == "security-reconcile"`.
- `test_security_mode_threads_save_kind_into_source_and_kind` — assert the `extract_reconcile_recommendations` stub saw `source == "security-reconcile"` and the `save_review` stub saw `kind == "security-reconcile"`.
- `test_default_call_still_runs_detail_reconcile` — regression guard: omit both new params; assert `run_step` saw `mode == "detail-reconcile"`, `extract` saw `source == "detail-reconcile"`, `save_review` saw `kind == "detail-reconcile"`.
- `test_security_mode_message_strings_unchanged` — with one mapped drifted file, the running-banner and per-step "finding(s) raised" lines emitted to the `file=` buffer are byte-identical to the `detail-reconcile` default (the wording is mode-agnostic).
- `test_security_mode_returns_total_findings` — the return value still equals the summed `len(recs)` across reconciled steps, independent of `mode`/`save_kind`.

## Acceptance criteria

- `plan_tool.cli.reconcile._RECONCILE_KINDS["security-reconcile"]` exists with the fields above and `name_excludes == ()`.
- `resolve_reusable_reconcile(plan_name, repo_root, plan_path=…, kind_filter="security-reconcile")` returns a `ReusableReconcile` for a fresh `<ts>-security-reconcile.json` and `None`/`fresh=False` for an absent/stale one, with **no** edit to `resolve_reusable_reconcile`'s body.
- `run_auto_reconcile_on_drift(..., mode="security-reconcile", save_kind="security-reconcile")` calls `launcher.run_step` with `mode="security-reconcile"`, `review.extract_reconcile_recommendations` with `source="security-reconcile"`, and `review_persistence.save_review` with `kind="security-reconcile"`.
- `run_security_audit(..., target="reconcile")` returns a `SecurityAuditResult` whose `findings` are reconstructed from the hook's persisted `<ts>-security-reconcile.json` sidecar(s) and whose `persisted_path` is set, so step 3's `cmd_security` renders `result.findings` and skips its own `write_security_report` (no double-write of the sidecar).
- `run_auto_reconcile_on_drift` called without the new params is byte-identical in output to HEAD (all three pre-existing message tests pass unchanged) and still runs `mode="detail-reconcile"` / `kind="detail-reconcile"`.
- `import plan_tool.cli.reconcile` and `import plan_tool.auto_reconcile` succeed; the full suite passes (`uv run pytest -m "not integration" tests/test_auto_reconcile.py tests/cli/test_reconcile_engine.py -q`) with the `conftest.py` real-backend gate never firing.
- No edits land in `plan_tool/cli/app.py`, `plan_tool/cli/security_cmd.py`, `plan_tool/review.py`, or `plan_tool/review_walk.py`.

## References

- [OWASP Top 10 (2021)](https://owasp.org/Top10/2021/) — The risk taxonomy (injection, broken access control, secrets exposure) the new `plan_tool/prompts/security-reconcile.md` drift prompt grounds its findings in, which `mode="security-reconcile"` renders here.
- [CWE — Common Weakness Enumeration (MITRE)](https://cwe.mitre.org/) — The weakness catalog (e.g. CWE-798 hardcoded credentials) for labeling the security findings the hook persists as `security-reconcile` recs.
- [Claude Code Headless Mode (Anthropic docs)](https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-headless) — Exit-code behavior the `run_step` → `shell_invoker` path relies on; the hook's best-effort skip on non-zero exit mirrors it.

## Deferred

- **`cmd_security --reconcile` → reconcile engine wiring** — `plan_tool/cli/security_cmd.py` is out of this step's `files:`; the consuming step calls `run_auto_reconcile_on_drift(..., mode="security-reconcile", save_kind="security-reconcile")` and/or the security reuse-prompt path. Step 3's `cmd_security --reconcile` and the `run_security_audit` (plan-wide) orchestrator it calls are deliverables of dependency steps 1/3 not yet landed at HEAD; once present, that command path stays distinct from this drift hook.
- **Named per-kind wrappers + `plan_tool/cli/app.py` re-export** — `_walk_saved_security_reconcile` / `_prompt_reuse_saved_security_reconcile` / `_find_saved_security_reconcile_for_step` / `_ask_reuse_saved_security_reconcile` and their `from plan_tool.cli.reconcile import (…)` re-export belong to the consuming step (it owns the `plan_tool/cli/app.py` edit); the kind-generic cores serve step 4's tests directly.
- **Apply-eligibility for security findings** — adding `"security-reconcile"` to `plan_tool/review_walk.py: _APPLY_AS_FINDING_SOURCES` is step 7's conservative auto-apply allowlist concern; step 4 keeps security findings advisory.
- **Iteration-loop triggers** — which of `cmd_completeness` / `_iterate_reconcile_loop` / `create_plan` / `generate_detail` should fire the security drift hook (vs the detail-reconcile default) is a wiring decision for the call-site step, not this capability step.
- **Mode-specific recovery wording** — the drift-halt skip/recovery hints keep referencing `plan-tool detail <slug> --reconcile`; pointing them at `plan-tool security … --reconcile` under `mode="security-reconcile"` is deferred to avoid churning the default tests' byte-exact pins.
