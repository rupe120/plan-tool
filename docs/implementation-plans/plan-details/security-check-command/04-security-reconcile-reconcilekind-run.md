# Step 4 — Add the `security-reconcile` target: the `run_auto_reconcile_on_drift` mode/persist/sink hook and `run_security_audit`'s plan⇆code drift branch

## Summary

Wires the `plan-tool security --reconcile` path end-to-end. Two coordinated edits plus one new prompt: a generalized `plan_tool/auto_reconcile.py:run_auto_reconcile_on_drift` that takes `mode` / `persist` / `findings_sink` / `invoker` (defaults preserve every existing caller byte-for-byte), and a `target == "reconcile"` branch in `plan_tool/security_audit.py:run_security_audit` that synthesizes a whole-plan drift scope via `plan_tool/scope_guard.py:build_file_to_step_map`, runs the hook with persistence suppressed, and adapts the collected per-step `Recommendation`s back into a `SecurityAuditResult`. The load-bearing decision: the hook's per-step `save_review` is suppressed (`persist=False`) so `plan_tool/security_audit.py:write_security_report` is the **sole** on-disk writer of the single `<ts>-security-reconcile.json` sidecar — `cmd_security` persists it because `SecurityAuditResult.persisted_path` stays `None`. On green, `run_security_audit(..., target="reconcile")` over a stubbed `run_auto_reconcile_on_drift` returns a `SecurityAuditResult` whose `findings` carry `source="security-reconcile"`, the existing auto-reconcile callers see unchanged output, and the conftest real-backend gate never fires.

## Table of Contents

- [Why](#why) — what `--reconcile` lacks today and why the hook is reused, not re-authored
- [Files (creates vs edits)](#files-creates-vs-edits) — one new prompt, two production edits, two test files
- [Implementation](#implementation) — reuse/display routing, the hook generalization, the dispatch branch, the prompt
- [Tests](#tests) — kind isolation, hook mode/persist/sink, reconcile dispatch, prompt render
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — reconcile-mode and OWASP/CWE grounding
- [Deferred](#deferred) — reuse-prompt wiring, stdout aggregation, multi-resolver consolidation

## Why

- **`plan-tool security --reconcile` raises today.** Step 3 wired the `--reconcile` flag to `run_security_audit(target="reconcile")`, but step 1's `_SECURITY_TARGETS = ("plan", "code")` raises `SecurityError` on `"reconcile"` (its plan⇆code branch is deferred here). The flag returns rc 2 (failure-to-complete) until this step lands the target.
- **Plan⇆code security drift is exactly what `run_auto_reconcile_on_drift` already does** — run a focused reconcile against the step(s) owning drifted files, parse `Recommendation` findings, surface them inline. The reconcile direction-of-truth (code is canonical, findings edit the plan/detail) is the right shape for "the plan's stated security intent no longer matches the code." Reuse the hook instead of re-authoring a security-specific reconcile loop.
- **The standalone command has no in-run file-drift set to react to.** `run_auto_reconcile_on_drift` is normally fired from an iteration loop's drift halt with a live `drifted` set. `security --reconcile` runs on a clean tree with nothing recorded as drifted, so the branch must **synthesize** the scope: treat every step's declared file as in-scope and let claude judge each step's security posture against its code.

## Files (creates vs edits)

**New files:**
- `plan_tool/prompts/security-reconcile.md` — the `mode="security-reconcile"` prompt template `plan_tool/renderer.py:render_prompt` loads as `prompts/security-reconcile.md`. Mirrors `plan_tool/prompts/detail-reconcile.md`'s structure and **its exact `## Findings` block contract** (severity-prefixed bullets, `_(none)_` when clean) so `plan_tool/review.py:extract_reconcile_recommendations` parses it with no new parser. The prompt's lens is security (the `plan_tool/prompts/security.md` checklist), not general drift.

**Existing files (edits only):**
- `plan_tool/auto_reconcile.py` — generalize `run_auto_reconcile_on_drift`: add keyword-only `mode="detail-reconcile"`, `persist=True`, `findings_sink=None`, `invoker=None`; thread `mode` into `run_step` + `extract_reconcile_recommendations(source=mode)`; extend `findings_sink` with each step's recs; gate `save_review` (and its fingerprint capture) on `persist`; pass `invoker` to `run_step` when set. Return stays `int`.
- `plan_tool/security_audit.py` — add the `persisted_path: Optional[Path] = None` field to the step-1 `SecurityAuditResult` dataclass (steps 1–3 read it but none defines it, so `result.persisted_path` raises `AttributeError` without this edit); extend `_SECURITY_TARGETS` to `("plan", "code", "reconcile")`; add the `target == "reconcile"` branch to `run_security_audit`; single-source `write_security_report`'s (and `resolve_reusable_security`'s, if it guards `target`) `target` check against `_SECURITY_TARGETS` so the `-security-reconcile.json` sidecar can be written and resolved.
- `plan_tool/review.py` — read-only reuse, no edit in the chosen approach: the reconcile branch calls `extract_reconcile_recommendations` to parse the new prompt's `## Findings` block and re-maps its `_CLAUDE_SEVERITY_MAP` `LOW`→`medium` fold to `nit` after extraction (security_audit.py-side, per the severity-normalization note below). Declared in `files:` because the alternative normalization — threading a security-specific severity map through `extract_reconcile_recommendations` itself — would edit this file; surface the choice as a reconcile finding rather than silently editing review.py.

## Implementation

### Reconcile reuse and display routing — no `_RECONCILE_KINDS` row

- **No `security-reconcile` row is added to `plan_tool/cli/reconcile.py:_RECONCILE_KINDS`** — it would be dead config. Nothing in production reads such a row: the existing `detail-reconcile` / `run-reconcile` `name_includes` filters (`-detail-reconcile` / `-run-reconcile`) are substring-disjoint from `-security-reconcile`, so they already cannot mis-grab a `-security-reconcile.json` sidecar, and no production caller queries `resolve_reusable_reconcile` / `_find_saved_for_step` with a `security-reconcile` kind (every call site indexes the literal `"detail-reconcile"` / `"run-reconcile"` keys). There is no recognition path the row would protect.
- **Audit-command freshness reuse keys on step 2's `plan_tool/security_audit.py:resolve_reusable_security(..., target="reconcile")`** (the `-security-reconcile.json` suffix filter, fingerprint-gated) — security never calls `resolve_reusable_reconcile`, which stays the detail/run-reconcile fingerprint resolver. The `-security-reconcile.json` save is **loadable and displayable** through the existing kind-agnostic `plan_tool/cli/review_cmd.py:cmd_review_walk` (which loads via `plan_tool/review_persistence.py:resolve_saved_review`, by id or newest, regardless of kind) — no `_RECONCILE_KINDS` registration and no new walk-load wiring are needed for display. This is **display-only**: `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES == {"detail-reconcile", "claude", "plan-completeness"}` omits `security-reconcile`, so `should_apply_as_finding` returns `False` for these recs — a walked save loads and shows its findings but does **not** dispatch them through `apply_finding`. Registering `security-reconcile` in `_APPLY_AS_FINDING_SOURCES` (to make walked findings applicable) belongs with the deferred reuse-prompt/walk wiring → Deferred, not this step.

### `plan_tool/auto_reconcile.py` — generalize `run_auto_reconcile_on_drift`

- **New keyword-only params (all defaulted to preserve current behavior):**
  - `mode: str = "detail-reconcile"` — replaces the hardcoded `"detail-reconcile"` literals at the `run_step(..., mode=...)` call and at `extract_reconcile_recommendations(..., source=mode)`. The security path passes `mode="security-reconcile"`, so `run_step` renders `prompts/security-reconcile.md` and findings carry `source="security-reconcile"`.
  - `persist: bool = True` — when `False`, skip the per-step `save_review` call **and** the pre-loop `compute_plan_fingerprint` / `compute_code_fingerprint` capture that feeds only it. Findings are still parsed, counted, and pushed to `findings_sink`. The `save_review(kind="detail-reconcile")` call keeps its hardcoded `kind` deliberately — `mode` is **not** threaded into it — because the only `persist=True` caller is the detail-reconcile path; the security path uses `persist=False`, so `save_review` is never reached and never mints a mis-kinded sidecar. A future `persist=True` caller with a non-default `mode` must thread `mode` into `kind` before relying on persistence.
  - `findings_sink: Optional[list] = None` — when provided, `findings_sink.extend(recs)` after each step's `extract_reconcile_recommendations`. This is the in-memory channel by which the security branch recovers per-step `Recommendation`s; the `int` return is unchanged for every other caller.
  - `invoker: Optional[Invoker] = None` — passed to `run_step(invoker=...)` only when set (else `run_step` uses its `shell_invoker` default). `plan_tool/launcher.py:Invoker`, `plan_tool/review.py:Invoker`, and step 1's `SecurityInvoker` are all `Callable[[str], tuple[int, str]]`, so threading `run_security_audit`'s invoker straight through is type-compatible and keeps the invoker seam intact (tests neutralize one seam, no real backend).
- **Persistence-suppression is the load-bearing decision.** `write_security_report` (called once by `cmd_security`) is the sole writer of the single `<ts>-security-reconcile.json`. If the hook also persisted, it would mint one `-security-reconcile.json` **per step**, fragmenting reuse and racing the command-level writer. With `persist=False` the hook emits no sidecar and `SecurityAuditResult.persisted_path` stays `None`, so `cmd_security`'s `if result.persisted_path is not None` guard (step 3) falls through to `write_security_report`.
- **Output wording under `persist=False`:** replace the per-step `"... finding(s) raised (saved to {path})"` line with a no-save variant (`"... finding(s) raised"`); the existing default-`persist` callers keep the `(saved to ...)` wording byte-for-byte (their tests in `tests/test_auto_reconcile.py` assert it). The "no drifted file maps to a plan step" skip line and the closing "walk findings interactively with `plan-tool reconcile-plan-walk {plan_slug}`" line stay generic and still apply.
- **No change to the bucketing / unmapped / launcher-error / non-zero-exit best-effort paths** — those are mode-agnostic.

### `plan_tool/security_audit.py` — the `reconcile` target

- **Define `persisted_path` on the result first:** add `persisted_path: Optional[Path] = None` to the step-1 `@dataclass(frozen=True) class SecurityAuditResult` (which has only `report`/`findings`/`dry_run` at HEAD). Every `result.persisted_path` reader — this branch's `return SecurityAuditResult(..., persisted_path` default and step 3's `cmd_security` `if result.persisted_path is not None` guard — depends on the field existing; without it `result.persisted_path` raises `AttributeError` and the reconcile persistence path ships broken.
- **Extend the target set:** `_SECURITY_TARGETS = ("plan", "code", "reconcile")`. `run_security_audit`'s existing `if target not in _SECURITY_TARGETS: raise SecurityError(...)` validation then admits `"reconcile"`.
- **Single-source the writer/resolver guard:** change `write_security_report`'s `assert target in ("plan", "code")` to `assert target in _SECURITY_TARGETS` so `cmd_security` can persist `<ts>-security-reconcile.json` via `kind=f"security-{target}"` (→ `security-reconcile`). Apply the same single-sourcing to `resolve_reusable_security` if it carries a `target` guard; its `endswith(f"-security-{target}.json")` suffix filter already resolves `-security-reconcile.json` generically.
- **Add the dispatch branch** to `run_security_audit`, alongside the `"plan"` / `"code"` branches:
  - `plan = parse_plan(plan_path)` then `file_to_step = build_file_to_step_map(plan, repo_root)` (lazy `from plan_tool.scope_guard import build_file_to_step_map`). This is the **synthesized whole-plan drift scope** — every step's `all_files` (modified + created), resolved-absolute, keyed to `(step_id, title)` — **not** any in-run file-drift set.
  - `drifted = sorted(file_to_step)` — pass every declared file as "drifted" so the hook buckets all steps and reconciles each step's security posture against its code.
  - **Honor `dry_run` before any backend call** (mirror the plan/code branches): return `SecurityAuditResult(report="<security-reconcile dry-run: per-step prompts not rendered>", findings=[], dry_run=True)` without invoking the hook. The reconcile path renders one prompt per step inside `run_step`, so there is no single prompt to echo — the dry-run note states that.
  - Otherwise build `sink: list[Recommendation] = []` and call (lazy `from plan_tool.auto_reconcile import run_auto_reconcile_on_drift`):
    ```
    run_auto_reconcile_on_drift(
        drifted=drifted,
        file_to_step=file_to_step,
        plan_path=plan_path,
        plan_slug=plan_name,
        repo_root=repo_root,
        mode="security-reconcile",
        persist=False,
        findings_sink=sink,
        invoker=invoker,
    )
    ```
  - **Re-map reconcile-target `LOW`→`nit` after extraction (mirror step 1's `_security_recommendations` normalization).** `findings_sink` is populated via `extract_reconcile_recommendations`, which applies `review.py:_CLAUDE_SEVERITY_MAP`'s `LOW`→`medium` fold unchanged — so a `LOW` `security-reconcile` finding lands at `medium`, which `convergence.is_blocking` treats as blocking and `--fail-on-findings` flips to non-zero, contradicting the plan's `LOW`/`NIT`-non-blocking policy that step 1 honors for the plan/code targets. Before adapting `sink` into the result, re-map each reconcile finding's `severity` `LOW`→`"nit"` (keeping `NIT`→`"nit"`) so security `LOW`/`NIT` reconcile findings stay outside `convergence.BLOCKING_SEVERITIES` (`{"medium", "high", "critical"}`); only `MEDIUM`/`HIGH`/`CRITICAL` reconcile findings are blocking. This holds the non-blocking policy across all three targets.
  - **Adapt back to a `SecurityAuditResult`:** `return SecurityAuditResult(report=<synthesized summary>, findings=sink, dry_run=False)`. The summary is a short markdown header (e.g. `f"# Security reconcile — {plan.title}\n\n{len(sink)} finding(s) across {len(file_to_step)} declared file(s)."`); per-step claude stdout is streamed live by `run_step`'s invoker, not aggregated into `report` (see Deferred). `persisted_path` is left at its default `None`.
- **Test seam:** the branch lazy-imports `run_auto_reconcile_on_drift`, so `tests/test_security_audit.py` stubs `plan_tool.auto_reconcile.run_auto_reconcile_on_drift` (populate `findings_sink`, return a count) — no `run_step`, no backend, conftest gate green. `run_security_audit`'s `invoker` is threaded through but unused when the hook is stubbed.

### `plan_tool/prompts/security-reconcile.md` (new)

- **Mirror `plan_tool/prompts/detail-reconcile.md`** for the variable surface (`${step_id}`, `${step_title}`, `${plan_title}`, `${step_index}`, `${step_total}`, `${step_detail}`, `${step_files}`, `${lessons_section}` — exactly what `plan_tool/renderer.py:_build_variables` supplies) and for the **strict `## Findings` block contract**: severity-prefixed bullets (`- CRITICAL: …`), `## Findings` + `_(none)_` when plan and code already agree. This is load-bearing — `extract_reconcile_recommendations` parses that block; a divergent shape yields zero findings silently.
- **Swap the lens to security:** code on disk is canonical; findings propose **plan/detail edits** that close the gap between the plan's stated security intent and the code's actual posture. Carry the `plan_tool/prompts/security.md` checklist (injection, authorization/ownership, data exposure, auth handling, input validation, secret handling, IAM) as the dimensions to judge. **Do not modify code** — plan/detail edits only.
- **`mode="security-reconcile"` is non-mutating:** `plan_tool/launcher.py:MUTATING_MODES = frozenset({"run"})`, so `run_step` neither marks steps done nor appends the test-order directive — the same posture as `detail-reconcile`.

### Foundational logic and shared call sites

- **The core behavior** is a parametrized reconcile dispatch: "run the reconcile hook over a synthesized whole-plan scope under a security prompt, collect findings in memory, write once." The reconcile-run primitive is single-sourced at `plan_tool/auto_reconcile.py:run_auto_reconcile_on_drift` — this step generalizes it rather than cloning it.
- **`build_file_to_step_map`** (`plan_tool/scope_guard.py`) is the one producer of the resolved-absolute `dict[Path, (step_id, title)]` map; `run_auto_reconcile_on_drift`'s docstring already names it as the expected `file_to_step` shape, and `resolve_reusable_reconcile`'s `drifted_code` is sorted-resolved to align with it. The branch reuses it verbatim — no parallel map builder.
- **Three fingerprint-reuse resolvers now coexist** — `plan_tool/completeness_report.py:resolve_reusable_audit`, `plan_tool/cli/reconcile.py:resolve_reusable_reconcile`, `plan_tool/security_audit.py:resolve_reusable_security`. Merging them into one `kind`-parametrized resolver is a refactor `detail` cannot mint → Deferred (carried from step 2).
- **Confirm the depends_on-1/3 symbol contract before coding, not from this body.** `plan_tool/security_audit.py` and its symbol cluster (`run_security_audit`, `SecurityAuditResult` with `report`/`findings`/`dry_run`, `_SECURITY_TARGETS`, `write_security_report`, `resolve_reusable_security`, `SecurityInvoker`, and `cmd_security`'s `if result.persisted_path is not None` guard) do **not** exist at HEAD — steps 1–3 build them. Step 1 ships `SecurityAuditResult` with only `report`/`findings`/`dry_run`; the `persisted_path` field that `cmd_security`'s guard and this branch both read is **not** built by steps 1–3 — **this step adds it** (see the `security_audit.py` edit above). The field names, arity, and `run_security_audit`'s `invoker` param used throughout this step are this body's expectation, not a settled contract. At implementation time, re-read steps 1–3 as landed and reconcile any divergence (a renamed field, a changed signature, a different invoker keyword) against what they actually export before writing the reconcile branch; surface a mismatch as a reconcile finding rather than assuming this body's names.

## Tests

### Test-creation order (feature step)

New behavior — author each unit test **with** the implementation; every test below must be green before this step is done. No `main()` and no `@pytest.mark.allow_real_claude`; the conftest real-backend gate staying green is itself an assertion.

**`tests/test_auto_reconcile.py`** (drives the hook through its `file=` seam, stubbing `launcher.run_step` / `review.extract_reconcile_recommendations` / `review_persistence.save_review`):
- `test_mode_threads_to_run_step_and_source` — `mode="security-reconcile"` calls `run_step(mode="security-reconcile")` and `extract_reconcile_recommendations(source="security-reconcile")`.
- `test_persist_false_skips_save_review` — with `persist=False`, a `save_review` stub that raises is **never** called; the function still returns the finding count.
- `test_findings_sink_collects_recs` — a passed `findings_sink` list is extended with the parsed recs across all bucketed steps; `len(findings_sink)` equals the return value when one step is affected.
- `test_invoker_threaded_when_set` — a sentinel `invoker` is forwarded to `run_step(invoker=...)`; omitted from the `run_step` call when `invoker=None`.
- `test_default_call_unchanged` — the existing default invocation (no new kwargs) still prints `"... finding(s) raised (saved to {path})"` and calls `save_review(kind="detail-reconcile")` (regression guard for the four existing callers).

**`tests/test_security_audit.py`** (drives `run_security_audit` directly, stubbing `plan_tool.auto_reconcile.run_auto_reconcile_on_drift`):
- `test_reconcile_target_accepted` — `target="reconcile"` no longer raises `SecurityError` (the `_SECURITY_TARGETS` extension).
- `test_reconcile_builds_whole_plan_scope` — the stubbed hook receives a `drifted` / `file_to_step` covering **every** step's declared files (assert against `build_file_to_step_map` over a two-step fixture plan), not an empty/in-run set.
- `test_reconcile_collects_findings_into_result` — the stub populates `findings_sink`; the returned `SecurityAuditResult.findings` are exactly those recs, `source="security-reconcile"`, `dry_run is False`, `persisted_path is None`.
- `test_reconcile_dry_run_skips_hook` — `dry_run=True` returns `SecurityAuditResult(dry_run=True, findings=[])` without calling the hook stub.
- `test_reconcile_suppresses_hook_persistence` — the stub asserts it was called with `persist=False` (so `write_security_report` remains the sole writer).
- `test_write_security_report_accepts_reconcile_target` — `write_security_report(..., target="reconcile")` no longer trips the `assert target in _SECURITY_TARGETS` guard and lands a `-security-reconcile.json`.

## Acceptance criteria

- `run_auto_reconcile_on_drift(..., persist=False, findings_sink=sink)` parses and collects recs into `sink`, returns the `int` count, and calls no `save_review`.
- `run_auto_reconcile_on_drift(...)` with no new kwargs is byte-identical in output to before (default callers unaffected).
- `run_security_audit(..., target="reconcile")` returns a `SecurityAuditResult` with `findings` of `source="security-reconcile"` and `persisted_path is None`; `dry_run=True` invokes no hook/backend.
- `_SECURITY_TARGETS == ("plan", "code", "reconcile")`; `write_security_report(..., target="reconcile")` writes `<ts>-security-reconcile.json`.
- `plan_tool/prompts/security-reconcile.md` exists, renders under `render_prompt(mode="security-reconcile")`, and ends with a `## Findings` block `extract_reconcile_recommendations` parses.
- The full suite passes; the conftest real-backend gate does not fire.

## References

- [OWASP Top 10 (2021)https: — the risk taxonomy the `security-reconcile.md` prompt judges plan⇆code drift against (injection, broken access control, secrets exposure).
- [CWE — Common Weakness Enumeration (MITRE)https: — weakness catalog for labeling findings consistently with the per-step `security.md` prompt.
- [Claude Code Headless Mode (Anthropic docs)https: — `-p` / `--output-format stream-json` / exit-code behavior `run_step`'s invoker relies on when the hook spawns per-step claude calls.
- [Python `string.Template`https: — `safe_substitute` semantics `render_prompt` uses, so the new prompt's `${…}` placeholders resolve against `_build_variables`.

## Deferred

- **Interactive reuse-prompt wiring for `security --reconcile`** — offering "reuse the saved `-security-reconcile.json`?" via `resolve_reusable_security(target="reconcile")` at the CLI is a `cmd_security` concern (step 3's `## Deferred` reuse-prompt flag), not in this step's footprint.
- **Registering `security-reconcile` in `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES`** — making a walked `-security-reconcile.json` save's findings dispatch through `apply_finding` (rather than display-only) is part of the reuse-prompt/walk wiring above, not this step. Until then `should_apply_as_finding` returns `False` for `security-reconcile` recs and a walk shows them without applying.
- **Aggregating per-step claude stdout into `SecurityAuditResult.report`** — the hook streams each step's stdout live and returns only the count + sink; `report` is a synthesized summary. A full-transcript capture would need the hook to return stdout per step → follow-up.
- **Consolidating `resolve_reusable_security` / `resolve_reusable_audit` / `resolve_reusable_reconcile`** into one `kind`-parametrized resolver (and a shared `changed|deleted|new` diff helper) — a refactor `detail` cannot mint; left for reconcile (carried from steps 1–2).
- **`depends_on: 2` frontmatter edge** — this step's `write_security_report` guard edit and the `cmd_security` persistence path both lean on step 2's writer/resolver; surface any missing ordering edge as a reconcile finding rather than editing the frontmatter here.
- **Plan-wide multi-step `--target code` sweep** — unrelated to reconcile; remains step 3's deferred follow-up.
