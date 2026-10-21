# Step 7 — Add a conservative, default-empty security auto-apply allowlist (security findings stay advisory)

## Summary

Adds the pure-logic primitive the `--iterate` convergence loop will consult before ever mechanically applying a security finding.

- **Pure predicate + constant** — a default-**empty** `SECURITY_AUTO_APPLY_ALLOWLIST` frozenset plus an `is_security_auto_apply_eligible(category, *, allowlist)` predicate in `plan_tool/convergence.py`, modeled on the existing `BLOCKING_SEVERITIES` / `is_blocking()` pair.
- **Recommendation adapter** — a thin pair in `plan_tool/security_audit.py` (`security_auto_apply_category` + `security_finding_is_auto_applicable`) that extracts a finding's category and delegates to the pure predicate.
- **Load-bearing decision** — the allowlist ships **empty**, so the predicate returns `False` for every security finding by default; security findings stay **advisory/deferred** exactly as steps 4–5 established.
- **Deliberate non-edits** — `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` and `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES` are **not** edited, since adding `security-plan`/`security-code` there would flip the advisory default.
- **On green** — `is_security_auto_apply_eligible(any, allowlist=frozenset())` is `False`, a security `Recommendation` is never auto-applicable under the default allowlist, and the predicate returns `True` only for an explicitly allowlisted category, proving the opt-in is the sole path off the advisory default.

## Table of Contents

- [Why](#why) — why a separate, default-off auto-apply gate lands now
- [Files (creates vs edits)](#files-creates-vs-edits) — two production edits plus the convergence test file
- [Implementation](#implementation) — the pure predicate, the allowlist constant, the security adapter, and the deliberate non-edits
- [Tests](#tests) — pure-predicate cases plus the security-adapter cases
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — convergence-module + OWASP/CWE grounding
- [Deferred](#deferred) — loop wiring, allowlist population, prompt-emitted category slugs

## Why

- **Security findings are advisory today, with no opt-in remediation path.** Steps 4–5 deliberately kept `security-plan` / `security-code` out of `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` and `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES`, so the `--iterate` loop never mechanically applies a security finding (it can still flip the blocking/CI gate via `_completeness_has_blocking_findings`). That advisory default is correct, but it is currently **absolute** — there is no narrow, conservative channel by which a genuinely mechanical security fix could be auto-applied.
- **The apply axis and the blocking axis are independent.** A security finding can be blocking (gates CI) *and* never auto-applied at the same time. This step adds the missing apply-axis primitive without touching the blocking axis — and ships it inert so the default behavior is unchanged.
- **The gate must default toward NOT applying.** A false-positive auto-apply mutates a plan/detail artifact on a finding that needed human judgment — the worst outcome for a security remediation. An empty allowlist makes the default `False` for every finding, so opting a category in is a deliberate, reviewable act.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/convergence.py` — add the module-level `SECURITY_AUTO_APPLY_ALLOWLIST: frozenset[str] = frozenset()` constant and the pure `is_security_auto_apply_eligible(category, *, allowlist=SECURITY_AUTO_APPLY_ALLOWLIST) -> bool` predicate, sited next to the existing `BLOCKING_SEVERITIES` / `is_blocking` finding-classification pair. No imports added (stays stdlib-only, no `plan_tool.*` imports).
- `plan_tool/security_audit.py` (created in step 1, extended in step 2) — add `security_auto_apply_category(rec) -> str | None` (derive a normalized category token from a security `Recommendation`) and `security_finding_is_auto_applicable(rec, *, allowlist=SECURITY_AUTO_APPLY_ALLOWLIST) -> bool` (guard on security source, then delegate to the convergence predicate). Add a top-import of the two new convergence symbols (`convergence.py` is a stdlib-only leaf below `security_audit.py`, so the import is acyclic).
- `tests/test_convergence.py` — add the pure-predicate unit cases below.

**Deliberate non-edits (load-bearing absence):**

- `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` and `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES` — **not** edited. Security sources stay absent so the existing apply walkers keep treating security findings as advisory. The new predicate is a *separate*, opt-in gate, never a membership add to these enumerated allowlists.

## Implementation

### `plan_tool/convergence.py`

Mirror the existing `BLOCKING_SEVERITIES` + `is_blocking` finding-classification pair (the precedent for a pure, severity/category-classification primitive living in this module). Place the new constant and predicate immediately after `is_blocking`.

- **`SECURITY_AUTO_APPLY_ALLOWLIST: frozenset[str] = frozenset()`**
  - **Empty by default** — the inert/advisory state. Each member is a lowercase **category token** naming a class of *mechanical* security fix that an operator has judged safe to auto-apply (the tokens `security_auto_apply_category` produces).
  - Document in the constant's comment that the empty default is the load-bearing "default advisory/deferred" decision and that membership is the *only* way a security finding becomes auto-applicable.

- **`def is_security_auto_apply_eligible(category: str | None, *, allowlist: frozenset[str] = SECURITY_AUTO_APPLY_ALLOWLIST) -> bool`**
  - **Pure, stdlib-only, no `Recommendation` parameter** — `convergence.py`'s tree-leaf contract forbids `plan_tool.*` imports, so the predicate takes the already-extracted category string, exactly as `is_blocking` takes a bare `severity` string.
  - Rules (conservative, toward NOT applying):
    - `if not category: return False` — `None` or empty string → no mechanical category → advisory.
    - `return category.strip().lower() in allowlist` — normalize then test membership.
  - **Do not gate on severity here.** Severity drives the *blocking* axis (`is_blocking`); folding it into the apply predicate would conflate the two independent axes. A critical-severity finding is auto-applicable iff its *category* is allowlisted, no more.
  - With the default empty allowlist this returns `False` for every input — the feature is inert until both a category-bearing finding and a populated allowlist exist.

### `plan_tool/security_audit.py`

Add the `Recommendation`-aware adapter that `convergence.py` cannot host. Top-import the two new symbols:
- `from plan_tool.convergence import SECURITY_AUTO_APPLY_ALLOWLIST, is_security_auto_apply_eligible`

- **`def security_auto_apply_category(rec) -> str | None`**
  - **Source of the category: `rec.anchor`** — the human-readable concept-key slug field on `plan_tool/review.py:Recommendation` (the same field plan-audit findings use as a stable concept key). Return `rec.anchor.strip().lower()` when set, else `None`.
  - Today step 1's `_security_recommendations` (the `_claude_recommendations` clone) does **not** populate `anchor` for security findings, so this returns `None` for every current security finding — a second, belt-and-suspenders layer of the inert default (no category *and* empty allowlist). Note this explicitly: emitting a category slug from the security prompts is a step-1/prompt concern, deferred.
  - Keep it pure and total — never raise; a malformed/absent `anchor` yields `None`.

- **`def security_finding_is_auto_applicable(rec, *, allowlist: frozenset[str] = SECURITY_AUTO_APPLY_ALLOWLIST) -> bool`**
  - **Guard on security source first:** `if rec.source not in {"security-plan", "security-code"}: return False`. Reuse any existing security-source constant step 1/2 introduced if present; otherwise inline the two literals. This stops a non-security rec accidentally routed here from ever being judged auto-applicable. The guard deliberately omits any `"security-reconcile"` source: reconcile-drift findings are judgment calls, not mechanical fixes, so they stay advisory — not an oversight.
  - Delegate: `return is_security_auto_apply_eligible(security_auto_apply_category(rec), allowlist=allowlist)`.
  - This is the single function a future loop-wiring step calls per security finding before choosing apply-vs-defer.

### Foundational logic and its sibling apply-gates

- **Foundational logic of this step:** a finding-apply-eligibility predicate (category-allowlist membership), the apply-axis analog of the existing `is_blocking` severity predicate.
- **Sibling apply-gates exercising the same "may this finding be auto-applied?" rule** — surfaced here, not consolidated:
  - `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` / `is_apply_eligible` — source-membership gate for `apply_finding`. Security sources absent (advisory). **Not edited.**
  - `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES` / `should_apply_as_finding` — source-membership gate for the walk's auto-dispatch. Security sources absent (advisory). **Not edited.**
  - These are **source**-keyed allowlists; the new predicate is a **category**-keyed gate layered *after* a source check. Merging the new category gate into the source allowlists (or unifying all three into one apply-eligibility seam) is a refactor `detail` cannot mint → **Deferred** for reconcile. Editing them now would silently flip security findings from advisory to auto-applied — the exact regression the empty-allowlist default exists to prevent.

## Tests

### Test-creation order (feature step)

This is a **feature** step (new predicate + constant + adapter). Write each test alongside the symbol it covers. **Green-before-done gate:** every test below must pass before the step is complete; run `uv run pytest -m "not integration" tests/test_convergence.py tests/test_security_audit.py -q`.

**`tests/test_convergence.py` (in footprint, pure):**
- `test_security_allowlist_empty_by_default` — `SECURITY_AUTO_APPLY_ALLOWLIST == frozenset()`.
- `test_security_eligible_false_for_none_category` — `is_security_auto_apply_eligible(None)` is `False`.
- `test_security_eligible_false_for_empty_category` — `is_security_auto_apply_eligible("")` is `False`.
- `test_security_eligible_false_under_default_allowlist` — any non-empty category with the default allowlist returns `False` (the advisory default).
- `test_security_eligible_false_for_unlisted_category` — category absent from a custom non-empty allowlist returns `False`.
- `test_security_eligible_true_for_listed_category` — `is_security_auto_apply_eligible("hardcoded-secret", allowlist=frozenset({"hardcoded-secret"}))` is `True`.
- `test_security_eligible_normalizes_case_and_whitespace` — `" Hardcoded-Secret "` matches allowlist `{"hardcoded-secret"}`.

**`tests/test_security_audit.py` (out of declared footprint — explicit addition, per the `plan_tool/X.py → tests/test_X.py` convention):**
- `test_security_auto_apply_category_reads_anchor` — a rec with `anchor="CWE-798"` yields `"cwe-798"`.
- `test_security_auto_apply_category_none_when_anchor_absent` — `anchor=None` yields `None`.
- `test_security_finding_not_auto_applicable_by_default` — a `security-plan` rec (any anchor) is not auto-applicable under the default empty allowlist.
- `test_security_finding_auto_applicable_when_category_allowlisted` — same rec with `allowlist=frozenset({"cwe-798"})` is auto-applicable.
- `test_non_security_source_never_auto_applicable` — a `claude`-source rec with an allowlisted anchor returns `False` (source guard).

## Acceptance criteria

- `plan_tool.convergence.SECURITY_AUTO_APPLY_ALLOWLIST` exists and equals `frozenset()`.
- `is_security_auto_apply_eligible(c, allowlist=frozenset())` returns `False` for every `c` (including `None`, `""`, and any non-empty token).
- `is_security_auto_apply_eligible("x", allowlist=frozenset({"x"}))` returns `True`; `is_security_auto_apply_eligible("X ", allowlist=frozenset({"x"}))` returns `True`.
- `plan_tool.security_audit.security_finding_is_auto_applicable(rec)` returns `False` for any security-source rec under the default allowlist, and `False` for any non-security-source rec regardless of allowlist.
- `security_auto_apply_category(rec)` returns the lowercased/stripped `rec.anchor`, or `None` when `anchor` is unset; it never raises.
- `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` and `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES` are byte-unchanged (still contain no `security-*` source).
- `convergence.py` adds no new imports and remains free of `plan_tool.*` imports.
- `uv run pytest -m "not integration" tests/test_convergence.py tests/test_security_audit.py -q` is green; the `tests/conftest.py` real-backend gate never fires (no symbol added here spawns a backend).

## References

- [CWE — Common Weakness Enumeration (MITRE)](https://cwe.mitre.org/) — the catalog whose entries (e.g. CWE-798 hardcoded credentials) shape the category-token vocabulary an operator would later add to `SECURITY_AUTO_APPLY_ALLOWLIST`.
- [OWASP Top 10 (2021)](https://owasp.org/Top10/2021/) — the risk taxonomy distinguishing genuinely mechanical fixes (secret removal) from judgment-heavy ones (broken access control), informing which categories are conservative enough to allowlist.

## Deferred

- **Wiring the predicate into the `--iterate` loop** — calling `security_finding_is_auto_applicable` from the convergence loop's apply step (`plan_tool/cli/completeness_cmd.py` / `plan_tool/review_walk.py`) is out of this step's `files:`; left to the consuming step that owns those modules. The primitive lands and tests in-footprint now.
- **Populating `SECURITY_AUTO_APPLY_ALLOWLIST`** — ships empty (advisory), **deliberately deviating** from the plan's Architecture ("a hardcoded secret the plan body itself contains ... apply-eligible via an explicit, conservative auto-apply allowlist") and Deferred ("start with only the hardcoded-secret-in-plan-body case"), which direct seeding one `hardcoded-secret` entry. The deviation is sound because the seed would be inert regardless: step 1's `_security_recommendations` emits no category slug, so `security_auto_apply_category` returns `None` and no finding matches any allowlist entry. Seeding a category that nothing can currently produce would be dead config that misleads readers into thinking auto-apply is live. Choosing which mechanical categories are safe to auto-apply — and seeding `hardcoded-secret` once the prompts emit a matching slug — is a deliberate, separately-reviewed decision, not a `detail` call.
- **Emitting category slugs from the security prompts** — `_security_recommendations` does not set `rec.anchor` for security findings today, so `security_auto_apply_category` returns `None`; teaching `plan_tool/prompts/security-plan.md` / `security.md` to emit a `[category-slug]` and the parser to populate `anchor` is a step-1/prompt enhancement.
- **Consolidating the three apply-eligibility gates** — `APPLY_ELIGIBLE_SOURCES`, `_APPLY_AS_FINDING_SOURCES`, and this category predicate exercise the same "may this finding be auto-applied?" rule from different keys; unifying them into one seam is a refactor for reconcile, not this step.
- **A severity ceiling on auto-apply** — intentionally omitted; severity is the blocking axis (`is_blocking`), kept independent from the apply axis here.
