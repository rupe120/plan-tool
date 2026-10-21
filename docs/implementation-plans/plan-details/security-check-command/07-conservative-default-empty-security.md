# Step 7 — Add a default-empty security auto-apply allowlist primitive (`SECURITY_AUTO_APPLY_ALLOWLIST` + `is_security_auto_apply_eligible` in `convergence.py`, `security_finding_is_auto_applicable` adapter in `security_audit.py`) — inert by default

## Summary

Adds the pure-logic apply-axis gate the `--iterate` convergence loop (step 9) will consult before ever mechanically applying a security finding — shipped **inert**. The primary edit lands in `plan_tool/convergence.py`: a default-**empty** `SECURITY_AUTO_APPLY_ALLOWLIST: frozenset[str]` constant plus an `is_security_auto_apply_eligible(category, *, allowlist=...)` pure predicate, sited beside the existing `BLOCKING_SEVERITIES` / `is_blocking()` finding-classification pair. A thin adapter pair in `plan_tool/security_audit.py` (created in step 1) — `security_auto_apply_category(rec)` + `security_finding_is_auto_applicable(rec, *, allowlist=...)` — derives a normalized category token from a security `Recommendation` and delegates to the pure predicate. **Load-bearing decision:** the allowlist ships empty, so the predicate returns `False` for every security finding, and the deliberate non-edit of both `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES` and `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` keeps `security-plan`/`security-code` findings advisory exactly as steps 4–6 established. On green, `is_security_auto_apply_eligible(any, allowlist=frozenset())` is `False`, a security `Recommendation` is never auto-applicable under the default allowlist, and the predicate returns `True` only for an explicitly allowlisted category.

## Table of Contents

- [Why](#why) — why a separate, default-off apply gate lands now
- [Files (creates vs edits)](#files-creates-vs-edits) — two production edits plus the convergence test file
- [Implementation](#implementation) — the pure predicate, the allowlist constant, the security adapter, and the deliberate non-edits
- [Tests](#tests) — pure-predicate cases plus the security-adapter cases
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — convergence-module + OWASP/CWE grounding
- [Deferred](#deferred) — loop wiring, allowlist population, prompt-emitted category slugs

## Why

- **Security findings are advisory today, with no opt-in remediation path.** Steps 4–6 deliberately kept `security-plan` / `security-code` out of `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` (`{"body-completeness", "detail-body", "plan-correctness", "reconcile", "detail-reconcile", "run-reconcile", "claude"}`) and `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES` (`{"detail-reconcile", "claude", "plan-completeness"}`), so the `--iterate` loop never mechanically applies a security finding. That advisory default is correct, but **absolute** — no narrow channel exists by which a genuinely mechanical security fix could ever be auto-applied.
- **The apply axis and the blocking axis are independent.** A security finding can be blocking (gate CI via `is_blocking`) *and* never auto-applied at the same time. This step adds the missing apply-axis primitive without touching the blocking axis — and ships it inert so the default behavior is byte-unchanged.
- **The gate must default toward NOT applying.** A false-positive auto-apply mutates a plan/detail artifact on a finding that needed human judgment — the worst outcome for a security remediation. An empty allowlist makes the default `False` for every finding, so opting a category in is a deliberate, reviewable act (a one-line frozenset edit), never an accident.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/convergence.py` — add the module-level `SECURITY_AUTO_APPLY_ALLOWLIST: frozenset[str] = frozenset()` constant and the pure `is_security_auto_apply_eligible(category, *, allowlist=SECURITY_AUTO_APPLY_ALLOWLIST) -> bool` predicate, sited immediately after the existing `BLOCKING_SEVERITIES` / `is_blocking` pair. No imports added — stays stdlib-only, no `plan_tool.*` imports (preserves the module's tree-leaf docstring contract).
- `plan_tool/security_audit.py` (created in step 1, extended in steps 2/4/6) — add `security_auto_apply_category(rec) -> str | None` (derive a normalized category token from a security `Recommendation`) and `security_finding_is_auto_applicable(rec, *, allowlist=...) -> bool` (delegate to the pure predicate). Imports `is_security_auto_apply_eligible` + `SECURITY_AUTO_APPLY_ALLOWLIST` from `plan_tool.convergence` (a stdlib-only leaf — no cycle; `security_audit.py` already top-imports leaf modules per step 2).
- `tests/test_convergence.py` — add the pure-predicate unit cases (see Tests). The security-adapter cases land in `tests/test_security_audit.py` (created in step 1).

## Implementation

### `plan_tool/convergence.py` — the pure apply-axis primitive

- **Add `SECURITY_AUTO_APPLY_ALLOWLIST: frozenset[str] = frozenset()`** directly below the `BLOCKING_SEVERITIES` constant. Empty by construction — this is the load-bearing default. Document inline that an empty set means "no security category is mechanically auto-applicable; security findings are advisory" and that populating it is a deliberate opt-in.
- **Add `is_security_auto_apply_eligible(category: str | None, *, allowlist: frozenset[str] = SECURITY_AUTO_APPLY_ALLOWLIST) -> bool`** modeled member-for-member on `is_blocking`:
  - Return `False` when `category` is `None` or empty/whitespace-only (no category → never eligible).
  - Otherwise return `category.strip().lower() in allowlist`.
  - Normalize with `.strip().lower()` so the membership test matches the lowercased tokens callers populate the allowlist with — mirrors `is_blocking`'s `severity.lower() in BLOCKING_SEVERITIES`.
  - Keyword-only `allowlist` param defaulting to the module constant lets tests pass an explicit non-empty set to prove the opt-in path without mutating the shipped default (the frozen-constant analog of injecting a budget).
- **No loop wiring.** This module stays a pure-logic primitive with no claude shell-out and no CLI surface, consistent with its module docstring. The step-9 `--iterate` loop is the only intended caller and it is out of scope here.

### `plan_tool/security_audit.py` — the Recommendation adapter

- **Add `security_auto_apply_category(rec) -> str | None`** — extract the normalized category token from a security `Recommendation` (`plan_tool/review.py:Recommendation`):
  - Read `rec.anchor` (the `[anchor-slug]` concept key — `category-token`-shaped, e.g. `hardcoded-credentials`) as the category source; the security prompts emit findings through the same `## Findings` contract the plan-audit/reconcile prompts use, so the anchor slug is the readable concept key.
  - Return the slug normalized (`.strip().lower()`), or `None` when `rec.anchor` is absent/empty. Do **not** invent a category from the title — an absent anchor must read as "no category" so the predicate returns `False`, never a guessed match.
- **Add `security_finding_is_auto_applicable(rec, *, allowlist=SECURITY_AUTO_APPLY_ALLOWLIST) -> bool`** — call `is_security_auto_apply_eligible(security_auto_apply_category(rec), allowlist=allowlist)`. Thread the same keyword-only `allowlist` through so the adapter is testable with an explicit opt-in set. This is the only function the step-9 loop calls per security finding.
- **Import the primitive at module level**: `from plan_tool.convergence import is_security_auto_apply_eligible, SECURITY_AUTO_APPLY_ALLOWLIST`. `convergence.py` is stdlib-only and imports no `plan_tool.*`, so this adds no cycle.

### Deliberate non-edits (load-bearing)

- **Do NOT add `security-plan` / `security-code` to `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES`.** Adding them would let `apply_finding` act on security findings during any review/reconcile walk, flipping the advisory default.
- **Do NOT add them to `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES`** either. That set drives `should_apply_as_finding`; adding a security source there would mark security findings auto-dispatchable on apply. Both non-edits together are what keep every security finding advisory — the new allowlist primitive is the *sole* channel to apply axis, and it ships empty.
- State both non-edits explicitly in the code comment beside the new allowlist so a future reader doesn't "complete" the wiring by editing the review-side sets.

## Tests

### Test-creation order (feature step)

This is a **feature** step — new pure-logic behavior. Author each test alongside the symbol it covers; every new test must be green before the step is done.

**`tests/test_convergence.py`** (extend the existing finding-classification block, sibling to the `is_blocking` cases):

- `test_security_auto_apply_allowlist_is_empty_by_default` — `SECURITY_AUTO_APPLY_ALLOWLIST == frozenset()`.
- `test_eligible_false_for_any_category_under_empty_allowlist` — `is_security_auto_apply_eligible("hardcoded-credentials")` is `False` with the shipped default.
- `test_eligible_false_for_none_category` — `is_security_auto_apply_eligible(None, allowlist=frozenset({"x"}))` is `False`.
- `test_eligible_false_for_empty_or_whitespace_category` — `""` and `"   "` return `False` even against a non-empty allowlist.
- `test_eligible_true_only_for_allowlisted_category` — `is_security_auto_apply_eligible("hardcoded-credentials", allowlist=frozenset({"hardcoded-credentials"}))` is `True`.
- `test_eligible_normalizes_case_and_whitespace` — `"  Hardcoded-Credentials  "` matches an allowlist of `{"hardcoded-credentials"}`.
- `test_eligible_non_member_false` — a category not in a non-empty allowlist returns `False`.

**`tests/test_security_audit.py`** (created in step 1; add the adapter cases):

- `test_category_reads_anchor_normalized` — `security_auto_apply_category(rec)` returns the lowercased/stripped `rec.anchor`.
- `test_category_none_when_anchor_absent` — a `Recommendation` with `anchor=None` yields `None`.
- `test_security_finding_not_auto_applicable_by_default` — a `source="security-code"` rec with any anchor is not auto-applicable under the empty default allowlist.
- `test_security_finding_auto_applicable_only_when_category_allowlisted` — same rec returns `True` only when its category is passed in an explicit `allowlist`.

**Green-before-done gate:** all new `tests/test_convergence.py` and `tests/test_security_audit.py` cases pass under `uv run pytest -m "not integration" tests/test_convergence.py tests/test_security_audit.py -q` before the step is considered finished.

## Acceptance criteria

- `plan_tool.convergence.SECURITY_AUTO_APPLY_ALLOWLIST` exists and equals `frozenset()`.
- `is_security_auto_apply_eligible(c, allowlist=frozenset())` returns `False` for every `c` (including `None`, `""`, and any token).
- `is_security_auto_apply_eligible(c)` (default allowlist) returns `False` for every `c`.
- `is_security_auto_apply_eligible("x", allowlist=frozenset({"x"}))` returns `True`; case/whitespace variants of `"x"` also return `True`.
- `plan_tool.security_audit.security_finding_is_auto_applicable(rec)` returns `False` for a security `Recommendation` under the default allowlist, and `True` only when the rec's category is in an explicitly passed allowlist.
- `grep` confirms neither `security-plan` nor `security-code` appears in `plan_tool/review.py:APPLY_ELIGIBLE_SOURCES` or `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES`.
- `import plan_tool.convergence` and `import plan_tool.security_audit` succeed with no new import cycle; the conftest real-backend gate never fires (the primitive and adapter make no claude call).
- The new `tests/test_convergence.py` and `tests/test_security_audit.py` cases pass.

## References

- [OWASP Top 10 (2021)https: — the risk taxonomy the security prompts ground their findings (and anchor slugs) in; useful when later choosing which categories are safe to allowlist.
- [CWE — Common Weakness Enumeration (MITRE)https: — the weakness catalog (e.g. CWE-798 hardcoded credentials) that anchor-slug category tokens map to.

## Deferred

- **`--iterate` loop wiring** — consulting `security_finding_is_auto_applicable` inside the convergence loop's apply pass is step 9; this step ships the primitive inert.
- **Populating `SECURITY_AUTO_APPLY_ALLOWLIST`** — choosing any genuinely-mechanical security category to opt in is a separate, deliberate decision out of scope here; the set ships empty.
- **Prompt-emitted category slug contract** — guaranteeing `prompts/security.md` / `prompts/security-plan.md` always emit a stable `[anchor-slug]` per finding (so `security_auto_apply_category` has a reliable source) is a prompt-side follow-up; today the adapter returns `None` when the anchor is absent, keeping the finding advisory.
- **Consolidating the three apply-axis gates** — `APPLY_ELIGIBLE_SOURCES`, `_APPLY_AS_FINDING_SOURCES`, and the new security allowlist now express related "may this be auto-applied?" judgments across modules; unifying them is a cross-module refactor `detail` cannot mint → route to reconcile.
