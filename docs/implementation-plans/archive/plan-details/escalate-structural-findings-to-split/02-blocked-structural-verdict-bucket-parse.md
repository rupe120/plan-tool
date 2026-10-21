# Step 2 — Add `BLOCKED-STRUCTURAL` verdict bucket to `parse_apply_verdict`/`ApplyFindingResult` and teach `apply-finding.md` to emit it

## Summary

- **Adds one new verdict token, `BLOCKED-STRUCTURAL`**, to the apply-finding contract. `plan_tool/launcher.py:parse_apply_verdict` recognizes it (via the `_APPLY_VERDICT_TOKEN_RE` alternation), and `plan_tool/launcher.py:ApplyFindingResult` documents it as a fifth allowed `verdict` value beside `APPLIED` / `NOT-APPLICABLE` / `BLOCKED` / `UNKNOWN`.
- **Teaches `plan_tool/prompts/apply-finding.md`** to emit a `## Verdict` heading with `BLOCKED-STRUCTURAL` on the next line when Claude determines mid-apply that the only correct fix is to split the step into two — not a prose edit `apply_finding` can make.
- **Key design decision:** the new token must sort **before** `BLOCKED` in the regex alternation, because `\bBLOCKED\b` already matches the `BLOCKED` prefix of `BLOCKED-STRUCTURAL` (a hyphen is a word boundary). Leftmost-alternative matching means a wrongly-ordered alternation silently parses `BLOCKED-STRUCTURAL` as `BLOCKED`.
- **Forward contract only.** This step makes the verdict *parseable and emittable*; it does not route it anywhere. The `escalate_to_split` bridge (step 3), the convergence-loop wiring (step 5), and the `cli/review_actions.py` apply-walk branch (step 6) are the consumers. Until step 6 lands, a `BLOCKED-STRUCTURAL` from the review apply walk falls through to the existing empty-diff no-op arm — see `## Deferred`.
- **On green:** `parse_apply_verdict("## Verdict\nBLOCKED-STRUCTURAL\n")` returns `"BLOCKED-STRUCTURAL"` (not `"BLOCKED"`), `apply_finding` carries it through unchanged into `ApplyFindingResult.verdict` with an empty findings delta, and `grep -q 'BLOCKED-STRUCTURAL' plan_tool/prompts/apply-finding.md` (the step's `gate`) passes.

## Table of Contents

- [Why](#why) — what's dead-ended today and why the verdict comes first
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files this step touches
- [Implementation](#implementation) — the regex ordering, the docstring, the prompt text
- [Tests](#tests) — cases added to `TestParseApplyVerdict` and the apply-finding suites
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — Python `re` alternation semantics
- [Deferred](#deferred) — what steps 3–6 own (the escalation, the routing, the review-walk branch)

## Why

When Claude, mid-apply, determines the only correct fix is to split a step into two, today it can only emit a bare `BLOCKED` — indistinguishable from "applying would conflict with plan state" or "requires a new file." The caller reverts and reports, and the structural need the audit did not pre-classify is lost. The escalation bridge (steps 3–6) needs a **distinct verdict** so it can tell "split this step" apart from an ordinary block and route it to the split engine. This step mints that token and makes both ends of the seam speak it — the prompt emits it, the parser recognizes it — without yet changing any routing. It is the apply-side twin of step 1's `is_structural(rec)` predicate (which classifies the *pre-known* `detail-purity` source); together they define the escalation set, but each is introduced as an inert forward contract first.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/launcher.py` — add `BLOCKED-STRUCTURAL` to the `_APPLY_VERDICT_TOKEN_RE` alternation (ordered before `BLOCKED`); update the `parse_apply_verdict` docstring and the `ApplyFindingResult` class docstring to list the new value.
  - `plan_tool/prompts/apply-finding.md` — add a `BLOCKED-STRUCTURAL` bullet to the `### \`## Verdict\`` "Exactly one of" list, with one line telling Claude when to choose it over a bare `BLOCKED`.
  - `tests/test_launcher.py` — add cases to `TestParseApplyVerdict` and the apply-finding delta suite.

## Implementation

### `plan_tool/launcher.py`

**Extend `_APPLY_VERDICT_TOKEN_RE`** (the module-level compiled regex directly above `parse_apply_verdict`). Add `BLOCKED-STRUCTURAL` as the **first** alternative:

- Forward state: `re.compile(r"\b(BLOCKED-STRUCTURAL|APPLIED|NOT-APPLICABLE|BLOCKED)\b")`.
- **The order matters.** Python `re` alternation is leftmost-match: at the position of `B`, the engine tries each alternative left to right. `\bBLOCKED\b` matches the `BLOCKED` prefix of `BLOCKED-STRUCTURAL` because the `-` is a non-word char, so the trailing `\b` holds between `D` and `-`. If `BLOCKED` came first, `parse_apply_verdict` would return `"BLOCKED"` for a `BLOCKED-STRUCTURAL` response, silently collapsing the new bucket. Put `BLOCKED-STRUCTURAL` ahead of `BLOCKED` so the longer, more specific token wins.
- `APPLIED` and `NOT-APPLICABLE` cannot prefix-collide with `BLOCKED-STRUCTURAL`, so their relative order is free; keep them where they read naturally.
- Do **not** touch `_VERDICT_TOKEN_RE` (referenced only by `parse_deep_verdict`, serving the deep-reconcile / `verify --deep` contract) or `parse_deep_verdict` itself — those serve the deep-reconcile / `verify --deep` contract, not apply-finding.

**Update `parse_apply_verdict`'s docstring** — the first line currently reads "Extract APPLIED / NOT-APPLICABLE / BLOCKED…"; add `BLOCKED-STRUCTURAL`. The function body needs **no change** — it already returns `m.group(1)` verbatim, so a wider alternation flows through unchanged.

**Update `ApplyFindingResult`'s docstring** — the `verdict` field is documented as one of `"APPLIED"` / `"NOT-APPLICABLE"` / `"BLOCKED"` / `"UNKNOWN"`. Add `"BLOCKED-STRUCTURAL"` to that list with a half-line gloss: *Claude determined mid-apply that the only correct fix is a step split.* No field, type, or constructor change — `verdict: str` already holds any token.

**Confirm the findings-delta guard needs no edit.** In `apply_finding`, the pre/post delta is computed only under `if verdict == "APPLIED" and diff_text:`. A `BLOCKED-STRUCTURAL` verdict is `!= "APPLIED"`, so `introduced` / `resolved` stay empty by definition — the same path `BLOCKED` / `NOT-APPLICABLE` / `UNKNOWN` already take. The auto-fix follow-up block is likewise gated on `verdict == "APPLIED"`, so it never fires. This step adds no branch to `apply_finding`; it only widens what `parse_apply_verdict` can return.

### `plan_tool/prompts/apply-finding.md`

**Add a fourth bullet** to the `### \`## Verdict\`` → "Exactly one of:" list, after the existing `BLOCKED` bullet:

- `BLOCKED-STRUCTURAL` — applying cleanly is impossible because the finding's only correct fix is to **split this step into two** (a refactor step and a feature step); a prose edit can't resolve it. Emit this instead of a bare `BLOCKED` when the block is specifically a step-granularity / mixed-concern problem.
- Keep the wording tight and imperative to match the file's existing "(strict)" writing-style section. State the *trigger* (the only fix is a split) so Claude picks `BLOCKED-STRUCTURAL` over `BLOCKED` deliberately, not by guess.
- The step's `gate` is `grep -q 'BLOCKED-STRUCTURAL' plan_tool/prompts/apply-finding.md` — the literal token must appear in the file exactly as written.

**Leave the bare-`BLOCKED` bullet in place.** `BLOCKED` still covers its original cases (conflicts with plan state, requires a new file — the "use `plan-tool detail`" note in step 4 of `## What to do`). `BLOCKED-STRUCTURAL` is a narrower sibling, not a replacement.

## Tests

All cases go in `tests/test_launcher.py`. This is a **feature** step — write these tests alongside the implementation; every one must be green before the step is done.

### `TestParseApplyVerdict` (existing class)

- `test_recognizes_blocked_structural` — `parse_apply_verdict("## Verdict\nBLOCKED-STRUCTURAL\n")` returns `"BLOCKED-STRUCTURAL"`.
- `test_blocked_structural_not_misparsed_as_blocked` — the disambiguation guard: a `BLOCKED-STRUCTURAL` response returns `"BLOCKED-STRUCTURAL"`, **not** `"BLOCKED"`. This is the test that fails if the alternation is misordered; it pins the ordering as a checkable property, not a code-reading claim.
- `test_bare_blocked_still_parses` — `parse_apply_verdict("## Verdict\nBLOCKED — would create file\n")` still returns `"BLOCKED"` (mirrors the existing bare-`BLOCKED` case; proves the wider alternation didn't break the original token, including the trailing-prose form).

### Apply-finding delta suite (mirror `TestApplyFindingValidationDelta.test_blocked_verdict_skips_delta`)

- `test_blocked_structural_verdict_skips_delta` — drive `apply_finding` with a fake invoker returning `## Summary\n- …\n\n## Verdict\nBLOCKED-STRUCTURAL\n`; assert `result.verdict == "BLOCKED-STRUCTURAL"` and `result.introduced_findings == ()` / `result.resolved_findings == ()`. Confirms the new verdict takes the same empty-delta path as `BLOCKED`. Neutralize the invoker per `TESTING.md` (a fake callable; the autouse gate in `tests/conftest.py` raises if a real backend spawns).

### Prompt-token gate (optional, cheap)

- A one-line assertion that `plan_tool/prompts/apply-finding.md` contains the literal `BLOCKED-STRUCTURAL`, mirroring the step's `gate`, if the suite already has a prompt-content test to extend; otherwise the `gate` command covers it and no separate test is required.

## Acceptance criteria

- `parse_apply_verdict("## Verdict\nBLOCKED-STRUCTURAL\n")` returns `"BLOCKED-STRUCTURAL"`.
- A `BLOCKED-STRUCTURAL` response is **not** parsed as `"BLOCKED"`.
- `parse_apply_verdict("## Verdict\nBLOCKED — would create file\n")` still returns `"BLOCKED"`.
- `apply_finding` carries a `BLOCKED-STRUCTURAL` verdict into `ApplyFindingResult.verdict` with empty `introduced_findings` and `resolved_findings`.
- `grep -q 'BLOCKED-STRUCTURAL' plan_tool/prompts/apply-finding.md` exits 0 (the step's declared `gate`).
- The existing `TestParseApplyVerdict`, `TestApplyFindingValidationDelta`, and `TestApplyFinding*` cases still pass unchanged.

## References

- [`re` — Regular expression operations: alternation `A|B` (Python 3 docs)](https://docs.python.org/3/library/re.html#regular-expression-syntax) — Documents that `|` tries alternatives left to right and takes the first that matches, the exact rule that forces `BLOCKED-STRUCTURAL` ahead of `BLOCKED`.
- [`re` — `\b` word-boundary semantics (Python 3 docs)](https://docs.python.org/3/library/re.html#index-31) — Why `\bBLOCKED\b` matches inside `BLOCKED-STRUCTURAL` (the hyphen is a non-word char, so a boundary sits between `D` and `-`).
- [How to mark test functions with attributes — pytest](https://docs.pytest.org/en/stable/how-to/mark.html) — Reference for the unit tests added with this step (no integration marker needed; these are pure parser/struct unit tests).

## Deferred

- **Routing the verdict to the split engine** — step 3 (`launcher.escalate_to_split`) consumes `BLOCKED-STRUCTURAL`; this step only makes it parseable/emittable.
- **Convergence-loop wiring** — step 5 routes structural findings (the `detail-purity` source and this verdict) to escalation in the `create` / `detail` loops.
- **`cli/review_actions.py` apply-walk branch** — step 6 (`depends_on: [2, 3]`) adds the `BLOCKED-STRUCTURAL` arm to the verdict handling at `cli/review_actions.py` (currently `if result.verdict in ("BLOCKED", "NOT-APPLICABLE"):` → revert + report). **Transitional behavior between this step and step 6:** because `BLOCKED-STRUCTURAL` is not in that tuple and a blocked apply produces no diff, the review walk falls through to the existing `if not result.diff_text:` no-op arm and reports "reported APPLIED but the plan file didn't change." This is misleading messaging only — no edit is made and nothing is wrongly kept — and step 6 resolves it. This step deliberately does **not** edit `cli/review_actions.py` (out of scope).
- **Renaming `detail-purity` → `granularity-split`** — postponed per the plan's `## Deferred`; this step is verdict-side and touches no source classification.
