# Step 9 — Deliver security auto-apply end-to-end: per-finding-unique `[category-slug]` anchors, bare-category allowlist keying (`hardcoded-secret`), and the live `security --iterate` apply loop (filter + seeded allowlist, not the review_walk OR-branch)

## Summary

Flips the security auto-apply channel from inert (step 7) to live. The load-bearing edits for the `security --iterate` channel are the allowlist seed plus the anchor handling: `plan_tool/convergence.py:SECURITY_AUTO_APPLY_ALLOWLIST` is seeded with `"hardcoded-secret"`; `plan_tool/security_audit.py:_security_recommendations` parses the bare category but stores a **per-finding-unique** `rec.anchor` (the category composed with a per-body discriminator) so two same-category findings mint distinct `_make_rec_id` ids instead of collapsing; `plan_tool/security_audit.py:security_auto_apply_category` extracts the **bare category component** back off that composed anchor before matching the allowlist; and `plan_tool/prompts/security-plan.md` emits a leading `[category-slug]` on each finding (mirroring `plan_tool/prompts/plan-audit.md`'s `[anchor-slug]` contract). With the allowlist seeded, the step-8 `_run_security_iterate_loop` filters via `apply_eligible_security_findings(result)` → `security_finding_is_auto_applicable` to a non-empty set and applies each through `plan_tool/launcher.py:apply_finding` directly — it never calls `should_apply_as_finding`. Separately, `plan_tool/review_walk.py:should_apply_as_finding` gains an **OR-branch** (`… or security_finding_is_auto_applicable(rec)`) beside the unchanged `_APPLY_AS_FINDING_SOURCES` membership test (the frozenset stays byte-identical); this extends the **interactive** review/reconcile walk only and is orthogonal to the `--iterate` channel. The per-step `plan_tool/prompts/security.md` path and the `--mode security` per-step review are untouched. On green, `plan-tool security <name> --target plan --iterate` mechanically applies a `hardcoded-secret` finding through `plan_tool/launcher.py:apply_finding`, re-audits, converges, and exits 0; every non-allowlisted security finding stays advisory; and `grep -q 'hardcoded-secret' RUNBOOK.md` passes.

## Table of Contents

- [Why](#why) — what was inert after step 8 and why it lands now
- [Files (creates vs edits)](#files-creates-vs-edits) — in-scope edits plus the one required out-of-footprint `convergence.py` seed
- [Implementation](#implementation) — the prompt slug, the composed-anchor parser, the bare-category extractor, the allowlist seed, the walk OR-branch
- [Tests](#tests) — anchor uniqueness, bare-category extraction, eligibility, the live apply/re-audit cycle, the walk pre-filter
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — OWASP/CWE grounding for the seeded category and the prompt slug
- [Deferred](#deferred) — broader allowlist categories, resolver/loop consolidation

## Why

- **Steps 7–8 shipped the auto-apply machinery inert.** Step 7 added `SECURITY_AUTO_APPLY_ALLOWLIST = frozenset()` + `is_security_auto_apply_eligible` to `plan_tool/convergence.py` and the `security_auto_apply_category` / `security_finding_is_auto_applicable` adapter pair to `plan_tool/security_audit.py`; step 8 added `_run_security_iterate_loop` + `apply_eligible_security_findings`. With the allowlist empty, the eligible set is always empty, so `plan-tool security --iterate` runs exactly one audit and never applies. This step seeds one safe category and opens the channel.
- **Naive bare-category keying would collapse distinct findings.** At HEAD-of-step-1, `plan_tool/security_audit.py:_security_recommendations` is cloned from `plan_tool/review.py:_claude_recommendations`: it builds `Recommendation(id=_make_rec_id(None, source, body), …)` keyed on the **raw body**, with no `_split_audit_key` import, no slug parse, and `anchor` defaulting to `None` (per 01-…-plan.md:53-55). It does **not** key the fingerprint on a parsed slug like the plan-audit loop, so two same-category findings with different bodies already mint distinct ids — the collapse does not exist in current code. This step *adds* slug parsing + anchor composition to a parser that has neither (not "modify" existing slug handling). The hazard to avoid: if step 9 keyed the new slug parsing on the **bare category**, two `hardcoded-secret` findings would share the slug `hardcoded-secret`, hash to the same id, and one would silently overwrite the other in the convergence union and `save_review` map. The fix: parse the bare category for the allowlist axis, but store a per-finding-unique `rec.anchor` for the id axis.
- **Auto-apply must stay a deliberate, advisory-by-default channel.** The seeded category is `hardcoded-secret` only — a `CWE-798` mechanical class where the remediation (remove the literal, route to env/secret store) is the lowest-judgment security fix. Every other category remains advisory because it isn't on the allowlist, and the `review.py:APPLY_ELIGIBLE_SOURCES` / `review_walk.py:_APPLY_AS_FINDING_SOURCES` frozensets stay byte-unchanged (the load-bearing non-edits established in steps 4–7).

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/prompts/security-plan.md` (created step 1) — prepend a `[category-slug]` to each `## Findings` bullet's text, immediately after the `SEVERITY:` token. Add the slug-contract paragraph (kebab-case, names the **weakness category** not the prose, deterministic across re-audits). The per-step `plan_tool/prompts/security.md` is **not** edited — its `## Findings` block keeps no slug, preserving the `--mode security` per-step path.
- `plan_tool/security_audit.py` (created step 1, extended 2/4/6/7/8):
  - `_security_recommendations` — parse the leading bracket slug via the reused `plan_tool/review.py:_split_audit_key`; set `rec.anchor` to the **composed** `f"{category}:{discriminator}"` (discriminator = truncated hash of `plan_tool/review.py:_normalize_audit_fingerprint(body)`); pass that composed anchor as the `_make_rec_id` fingerprint so ids stay unique per finding.
  - `security_auto_apply_category(rec)` (added step 7) — change the body to strip the discriminator: take `rec.anchor.split(":", 1)[0]`, normalize (`.strip().lower()`), return `None` when `rec.anchor` is absent/empty. Do **not** read `rec.title`.
- `plan_tool/review_walk.py` — `should_apply_as_finding(rec)` gains the OR-branch: `return rec.source in _APPLY_AS_FINDING_SOURCES or _security_auto_applicable(rec)`, where `_security_auto_applicable` is a **body-local** import of `security_finding_is_auto_applicable` from `plan_tool.security_audit` (avoids any import cycle; matches the module's lazy-import discipline). `_APPLY_AS_FINDING_SOURCES` is **not** modified.
- `RUNBOOK.md` — add the note under `## Mutating vs. read-only modes` (RUNBOOK.md:2432), which exists at step-9 runtime. (The `## Workflow: plan-wide security audit` section does **not** exist yet — it is created by the successor step 10 (`10-document-security-command-across.md`); if that section is already present when this step runs, place the note there instead.) Document that `security --iterate` now mechanically applies findings whose category is on `SECURITY_AUTO_APPLY_ALLOWLIST` (currently `hardcoded-secret`) and re-audits to convergence; auto-apply is **no longer advisory-only**. State that every other category stays advisory.

**Required edit beyond declared `files:` (flag explicitly):**

- `plan_tool/convergence.py` — seed `SECURITY_AUTO_APPLY_ALLOWLIST: frozenset[str] = frozenset({"hardcoded-secret"})` (step 7 shipped it empty). This is the one-line frozenset edit step 7's detail anticipated as step 9's job. `convergence.py` is not in the declared `files:` list, but seeding the allowlist is the load-bearing act of this step and lives nowhere else (the constant is the single-sourced apply-axis registry). Its mirror test `tests/test_convergence.py` is likewise a required-but-undeclared edit.

## Implementation

### `plan_tool/prompts/security-plan.md` — emit `[category-slug]`

- **Mirror `plan_tool/prompts/plan-audit.md`'s slug contract** exactly so the existing `plan_tool/review.py:_PLAN_AUDIT_KEY_RE` (`^\s*(?:\*\*)?\[([a-z0-9][a-z0-9-]*)\]\s*`) parses it with no new regex. Each bullet under `## Findings` becomes `- CRITICAL: [hardcoded-secret] <issue with file:symbol and one-line remediation>`.
- **Instruct the slug to name the weakness CATEGORY, not the instance** — e.g. `[hardcoded-secret]`, `[missing-authz]`, `[sql-injection]`. The category is what the allowlist gates on; multiple distinct findings legitimately share a category (two hardcoded secrets → two bullets both `[hardcoded-secret]`).
- **Keep the slug deterministic across re-audits** (same wording guidance as plan-audit) so the convergence loop's id dedup stays reliable on re-phrasing.
- **Leave `plan_tool/prompts/security.md` untouched** — the per-step prompt's `## Findings` block emits no slug, and the `--mode security` per-step review path never reaches the allowlist.

### `plan_tool/security_audit.py:_security_recommendations` — composed unique anchor

- **Parse the bare category** with the reused `plan_tool/review.py:_split_audit_key(bullet.body)` → `(category, body)`; `category` is `None` when the bullet omits the slug.
- **Compose a per-finding-unique anchor** so same-category findings never collide on `_make_rec_id`:
  - discriminator = first 8 hex of `sha256(_normalize_audit_fingerprint(body))`, computed over the **fully-stripped** body — after the `_split_triage_tags` and `_split_audit_fix` strips, not just after `_split_audit_key` — so the discriminator (and thus the id) stays stable when a re-audit re-phrases the triage tag or suggested-fix tail (reuse `plan_tool/review.py:_normalize_audit_fingerprint` so trivial re-wordings still map to the same id across re-audits — the convergence-dedup property).
  - `composed = f"{category}:{discriminator}"` when `category` is present; fall back to the existing slugless fingerprint path (`_normalize_audit_fingerprint(body) or body`) when absent, with `rec.anchor = None`.
- **Key the id on the composed anchor**: `id=_make_rec_id(step_id, source, composed)` and `anchor=composed`. Two `hardcoded-secret` bullets with different bodies → different discriminators → distinct ids and anchors; the same finding re-audited → identical discriminator → stable id.
- **Separator choice `":"` is safe** — category slugs are kebab `[a-z0-9-]+` (no colon), so `split(":", 1)` cleanly recovers the bare category. The composed anchor is internal (never re-fed to `_PLAN_AUDIT_KEY_RE`), so the colon never breaks slug parsing.

### `plan_tool/security_audit.py:security_auto_apply_category` — extract bare category

- **Strip the discriminator before matching**: `bare = rec.anchor.split(":", 1)[0]` then `.strip().lower()`; return `None` when `rec.anchor` is falsy.
- **Never synthesize a category from `rec.title`** (the step-7 rule) — an absent anchor reads as "no category" → `security_finding_is_auto_applicable` returns `False` (the safe default).
- `security_finding_is_auto_applicable(rec, *, allowlist=...)` (step 7) is unchanged structurally — it now returns `True` for a `hardcoded-secret`-categoried rec because the seeded allowlist contains that bare token.

### `plan_tool/convergence.py:SECURITY_AUTO_APPLY_ALLOWLIST` — seed one category

- **Replace `frozenset()` with `frozenset({"hardcoded-secret"})`.** `is_security_auto_apply_eligible(category, *, allowlist=SECURITY_AUTO_APPLY_ALLOWLIST)` (step 7, the `.strip().lower()`-membership predicate beside `is_blocking`) now returns `True` for `"hardcoded-secret"` and `False` for every other category. No other line in `convergence.py` changes; it stays a stdlib-only leaf with no `plan_tool.*` imports.

### The live `security --iterate` channel — allowlist seed + filter (no `should_apply_as_finding` involvement)

- **`plan_tool/cli/security_cmd.py:_run_security_iterate_loop` (step 8) needs no new gate.** It already filters the audit result via `apply_eligible_security_findings(result)` → `security_finding_is_auto_applicable`, then applies each surviving finding through `plan_tool/launcher.py:apply_finding` **directly**. With the allowlist now seeded, the eligible set is non-empty and the loop applies + re-audits for real. The loop does **not** call `should_apply_as_finding`, and `apply_finding` does not consult it either — so the `--iterate` apply decision rides entirely on the allowlist seed and the `_security_recommendations`/`security_auto_apply_category` anchor handling above. No behavioral edit to `security_cmd.py`; the step-8 dispatch is unchanged.

### `plan_tool/review_walk.py:should_apply_as_finding` — the OR-branch (interactive walk only, orthogonal to `--iterate`)

- **`should_apply_as_finding` gates the *interactive* review/reconcile walk** (`is_dispatchable` in `review_walk.py`, `review_actions.py`), **not** the `security --iterate` loop. This edit extends that interactive path so a manually-walked allowlisted security finding is dispatchable; it has no bearing on the `--iterate` acceptance criteria, which the allowlist seed + anchor handling satisfy on their own.
- **The OR-branch is forward-looking — no current interactive walk surfaces slug-bearing security findings.** This plan wires no `security-plan`/`security-code` sidecar into any walk's load path: only `security-reconcile` is registered in `_RECONCILE_KINDS` (step 4), and its findings are slugless (`rec.anchor = None`), so `security_finding_is_auto_applicable` always returns `False` for them. The slug-bearing `security-plan` findings the OR-branch is meant to admit are never loaded by `reconcile-plan-walk` or the review walk, so within this plan the branch has no live consumer beyond the `tests/test_review_walk.py` unit fixtures. It ships ready for a follow-up that adds the walk load path (e.g. a `security-plan` reconcile kind) without re-touching `should_apply_as_finding`.
- **Add the allowlist channel as an OR beside the source pre-filter:**
  - body-local `from plan_tool.security_audit import security_finding_is_auto_applicable as _security_auto_applicable` (lazy, mirroring `security_audit.py`'s own lazy `review`/`launcher` imports — keeps `review_walk` ↔ `security_audit` acyclic).
  - `return rec.source in _APPLY_AS_FINDING_SOURCES or _security_auto_applicable(rec)`.
- **`_APPLY_AS_FINDING_SOURCES` stays byte-identical** — adding `security-plan`/`security-code` to it is the deliberate non-edit from step 7. The allowlist (keyed on category, not source) is the sole channel, so a `security-code` finding whose category is *not* `hardcoded-secret` still returns `False`.
- **No live path mints a slug-bearing `security-code` finding, so `--target code` does not participate in auto-apply.** Per 01-…-plan.md:47-52 the `--target code` audit reuses `plan_tool/prompts/security.md`, which this step deliberately leaves slug-less — its findings parse to `rec.anchor = None`, so `security_auto_apply_category` returns `None` and the gate's safe default rejects them. Live `security --target code --iterate` therefore always short-circuits (nothing auto-applies); only `--target plan` (slug-bearing `plan_tool/prompts/security-plan.md`) feeds the channel. The OR-branch and the `tests/test_review_walk.py` cases use a `security-code` rec carrying a `hardcoded-secret:…` anchor only as a **directly-constructed unit fixture** — valid because the gate is correctly category-keyed and source-agnostic — not because any live `security-code` audit emits that anchor.

### Foundational logic and shared sites

- **Foundational logic:** "derive a stable-but-unique key from a security finding and gate auto-apply on its bare category." It composes existing primitives — `_split_audit_key` (anchor parse), `_normalize_audit_fingerprint` + `_make_rec_id` (stable id), `is_security_auto_apply_eligible` (allowlist membership) — rather than re-authoring any.
- **Parallel auto-apply-eligibility sites** (`plan_tool/review.py:APPLY_ELIGIBLE_SOURCES`, `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES`, `plan_tool/convergence.py:SECURITY_AUTO_APPLY_ALLOWLIST`): all three coexist; only the allowlist is touched (seeded), and only `should_apply_as_finding` gains the OR. Unifying the three into one kind-parametrized gate is a standing cross-module refactor → **Deferred**.
- **Anchor-keyed id minting** also lives in `plan_tool/review.py` (the plan-audit bullet loop) and `plan_tool/review.py:extract_reconcile_recommendations`. This step does **not** change those — the composed-anchor scheme is security-local. Consolidating "compose a unique anchor off a category slug" into a shared `review.py` helper is **Deferred** (it would change the plan-audit/reconcile id-stability contract, out of this step's footprint).

## Tests

### Test-creation order (feature step)

Author each test **with** the implementation it covers. Green-before-done gate: every new test below must pass before this step is finished.

**`tests/test_security_audit.py`:**
- `test_same_category_findings_get_distinct_ids` — two `## Findings` bullets both `[hardcoded-secret]` with different bodies parse to two recs with different `id` and different `anchor` (no collapse).
- `test_same_finding_reaudit_stable_id` — the same bullet body parsed twice yields the same `id`/`anchor` (discriminator is deterministic; convergence dedup holds).
- `test_anchor_is_composed_category_plus_discriminator` — `rec.anchor` for a `[hardcoded-secret]` bullet matches `^hardcoded-secret:[0-9a-f]{8}$`.
- `test_slugless_finding_anchor_none` — a bullet with no `[slug]` yields `rec.anchor is None` and a body-fingerprint id (unchanged fallback).
- `test_auto_apply_category_strips_discriminator` — `security_auto_apply_category(rec)` returns `"hardcoded-secret"` for a composed anchor `hardcoded-secret:deadbeef`.
- `test_auto_apply_category_none_when_anchor_absent` — returns `None` when `rec.anchor` is `None`/empty (never reads `rec.title`).
- `test_finding_applicable_only_for_allowlisted_category` — `security_finding_is_auto_applicable` is `True` for a `hardcoded-secret` rec, `False` for a `missing-authz` rec, under the seeded default allowlist.
- `test_apply_eligible_filters_to_hardcoded_secret` — `apply_eligible_security_findings(result)` over a mixed result returns only the `hardcoded-secret` findings.

**`tests/test_convergence.py` (required-but-undeclared):**
- `test_security_allowlist_seeded_with_hardcoded_secret` — `"hardcoded-secret" in SECURITY_AUTO_APPLY_ALLOWLIST` and `is_security_auto_apply_eligible("hardcoded-secret")` is `True`; `is_security_auto_apply_eligible("missing-authz")` is `False`.
- **Replace the now-false step-7 empty-allowlist assertions.** Seeding the frozenset breaks step 7's `test_security_auto_apply_allowlist_is_empty_by_default` (asserts `SECURITY_AUTO_APPLY_ALLOWLIST == frozenset()`, per 07-…-security.md:67) — delete/retitle it (e.g. to `test_security_auto_apply_allowlist_contains_only_hardcoded_secret`, asserting `SECURITY_AUTO_APPLY_ALLOWLIST == frozenset({"hardcoded-secret"})`) so the suite is green. Likewise retitle/repoint step 7's `test_eligible_false_for_any_category_under_empty_allowlist` (now misnamed — it passes only because `"hardcoded-credentials" ≠ "hardcoded-secret"`) to assert eligibility against the seeded allowlist (`True` for `"hardcoded-secret"`, `False` for any other category). The green-before-done gate requires the whole `tests/test_convergence.py` suite pass after the seed, not just the new test.

**`tests/test_review_walk.py`:**
- `test_should_apply_as_finding_admits_allowlisted_security` — `should_apply_as_finding` returns `True` for a `security-code` rec with anchor `hardcoded-secret:abc12345`.
- `test_should_apply_as_finding_rejects_non_allowlisted_security` — returns `False` for a `security-code` rec with anchor `missing-authz:abc12345`.
- `test_should_apply_as_finding_existing_sources_unchanged` — a `detail-reconcile` rec still returns `True` and a `deps` rec still `False` (the `_APPLY_AS_FINDING_SOURCES` membership path is byte-unchanged).

**`tests/cli/test_security_cmd.py`:**
- `test_iterate_applies_hardcoded_secret_then_reaudits` — `main(["security", <name>, "--target", "plan", "--iterate"])` over a stubbed invoker whose first audit returns one `[hardcoded-secret]` finding and whose re-audit returns clean: `plan_tool.launcher.apply_finding` is called once, rc is 0, the real-backend gate never fires.
- `test_iterate_skips_non_allowlisted_security` — a stubbed audit returning only a `[missing-authz]` finding: `apply_finding` is never called, the loop short-circuits to a single audit, rc 0.
- `test_one_shot_default_unchanged` — `security --target plan` (no `--iterate`) applies nothing regardless of category (step 3's one-shot dispatch), rc 0.

## Acceptance criteria

- `SECURITY_AUTO_APPLY_ALLOWLIST == frozenset({"hardcoded-secret"})` in `plan_tool/convergence.py`.
- `_security_recommendations` over two same-category bullets returns recs with distinct `id` and distinct `anchor`; over the same bullet twice returns identical `id`.
- `security_auto_apply_category(rec)` returns the bare category (`"hardcoded-secret"`) from a composed anchor, and `None` when `rec.anchor` is absent.
- `security_finding_is_auto_applicable` returns `True` only for `hardcoded-secret`-categoried recs under the default allowlist.
- `should_apply_as_finding` returns `True` for an allowlisted security rec and `False` for a non-allowlisted one, with all pre-existing source verdicts unchanged.
- `plan-tool security <name> --target plan --iterate` calls `apply_finding` on a `hardcoded-secret` finding, re-audits, and exits 0; a non-allowlisted finding triggers no apply.
- `plan_tool/prompts/security.md` is byte-unchanged (the `--mode security` per-step path is preserved).
- `grep -q 'hardcoded-secret' RUNBOOK.md` passes; the doc states auto-apply is no longer advisory-only.
- All new tests are green; the conftest real-backend gate never fires.

## References

- [CWE-798: Use of Hard-coded Credentials (MITRE)https: — grounds the single seeded `hardcoded-secret` category as the lowest-judgment mechanical remediation class.
- [OWASP Top 10 (2021)https: — A07 (identification/auth) and A05 (misconfiguration/secrets) taxonomy backing the prompt's category slugs.
- [Claude Code Headless Mode (Anthropic docs)https: — exit-code/stream behavior the `--iterate` apply loop relies on when shelling through `apply_finding`.

## Deferred

- **Broadening the allowlist beyond `hardcoded-secret`** — each new mechanical category (e.g. `insecure-tls-default`) is a separate one-line `frozenset` edit plus its own apply/re-audit test; left for a follow-up once the channel proves out.
- **Consolidating the three apply-eligibility gates** (`APPLY_ELIGIBLE_SOURCES`, `_APPLY_AS_FINDING_SOURCES`, `SECURITY_AUTO_APPLY_ALLOWLIST`) into one kind-parametrized registry — a cross-module refactor `detail` cannot mint.
- **Hoisting the composed-anchor scheme into a shared `review.py` helper** — would alter the plan-audit/reconcile id-stability contract; out of this step's footprint.
- **`--commit` and per-target apply semantics for `security --iterate`** — deferred by step 8; unchanged here.
