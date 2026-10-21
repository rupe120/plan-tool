> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add a `BLOCKED-STRUCTURAL` verdict bucket to `parse_apply_verdict` + the apply-finding prompt

## Summary

- Widen `plan_tool/launcher.py: _APPLY_VERDICT_TOKEN_RE` to recognize a fourth apply-finding verdict, `BLOCKED-STRUCTURAL`, placing it **first** in the `|` alternation so leftmost-match doesn't collapse it into the existing `BLOCKED`.
- Teach the apply-finding Claude prompt (`plan_tool/prompts/apply-finding.md`) to emit `BLOCKED-STRUCTURAL` when the finding it was handed can only be fixed by splitting the step into two type-pure steps — something `apply_finding` cannot do with an edit. Offer it via a `structural_verdict_option` placeholder gated by a new `apply_finding(allow_structural_verdict=False)` parameter (**guard (a)**), so the shared prompt offers the verdict only to opt-in callers (`detail` / review / the bridge, in later steps) and **never** to `create` — which inherits the default and is not edited, keeping create-side trigger 2 deferred with no `create.py` change.
- `parse_apply_verdict` returns its matched token verbatim, and every behavior branch in `apply_finding` is already gated on `verdict == "APPLIED"`, so the new token flows through with **no function-body change and no new branch** — it inherits the empty-delta / no-follow-up path that `BLOCKED` / `NOT-APPLICABLE` already take.
- On green: `parse_apply_verdict("## Verdict\nBLOCKED-STRUCTURAL\n")` returns `"BLOCKED-STRUCTURAL"` (not `"BLOCKED"`), and `apply_finding` driven by a fake invoker returning that verdict yields `result.verdict == "BLOCKED-STRUCTURAL"` with empty `introduced_findings` / `resolved_findings`.

## Table of Contents

- [Summary](#summary) — what this step adds and the observable result
- [Why](#why) — the missing verdict the escalation path needs to read
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files touched
- [Implementation](#implementation) — the regex widen, the prompt bullet, the no-op `apply_finding` inheritance
- [Tests](#tests) — the parser, ordering-guard, and delta-skip cases
- [Test-creation order (feature step)](#test-creation-order-feature-step) — green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable conditions
- [References](#references) — relevant authoritative docs
- [Deferred](#deferred) — the downstream consumer and producer left to later steps

## Why

The escalate-structural-findings-to-split plan needs a verdict that says "the finding I was asked to apply is structural — its only correct fix is to split the step, which this command can't do." Today `apply_finding` can only answer `APPLIED` / `NOT-APPLICABLE` / `BLOCKED` / `UNKNOWN`, so a structural finding that reaches the apply path either gets force-fit into `BLOCKED` (indistinguishable from a file-conflict block) or, worse, the Claude tries to fake an edit. A dedicated `BLOCKED-STRUCTURAL` token lets the apply Claude name the structural case precisely, lets `parse_apply_verdict` carry it back in `ApplyFindingResult.verdict`, and gives step 5's `cli/review_actions.py` dispatcher a token to route to the split escalation. This step is the cheap, two-file (plus tests) foundation: the parser and prompt learn the token; the producer wiring and the downstream consumer arm land in later steps.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/launcher.py` — add `BLOCKED-STRUCTURAL` as the first alternative of `_APPLY_VERDICT_TOKEN_RE`; refresh the docstrings/comments that enumerate the apply verdicts (`parse_apply_verdict`, the `ApplyFindingResult.verdict` field comment, `apply_finding`'s step-6 docstring line, and the pre-delta comment). The only code-flow edit is the **guard-(a)** seam: a new `allow_structural_verdict: bool = False` parameter on `apply_finding` passed into the prompt render (no verdict-handling branch).
  - `plan_tool/prompts/apply-finding.md` — add the `BLOCKED-STRUCTURAL` option to the `### `## Verdict`` "Exactly one of:" list via a `structural_verdict_option` placeholder (rendered only when the caller opts in), describing when to emit it.
  - `tests/test_launcher.py` — add parser, ordering-guard, and delta-skip tests beside the existing `TestParseApplyVerdict` and `TestApplyFindingValidationDelta` classes.

## Implementation

### `plan_tool/launcher.py`

- **Widen `_APPLY_VERDICT_TOKEN_RE`, new token first.** Change the alternation from `r"\b(APPLIED|NOT-APPLICABLE|BLOCKED)\b"` to `r"\b(BLOCKED-STRUCTURAL|APPLIED|NOT-APPLICABLE|BLOCKED)\b"`.
  - **Ordering is required.** Python `re` alternation is leftmost-match, and `\bBLOCKED\b` already matches inside `BLOCKED-STRUCTURAL` (the `-` is a non-word char, so the trailing `\b` sits between `D` and `-`). If `BLOCKED` came first, a `BLOCKED-STRUCTURAL` response would silently parse as `BLOCKED` — a no-error bucket collapse invisible to any test feeding only the bare token. Put `BLOCKED-STRUCTURAL` first so the longer, more-specific token wins.
- **No change to `parse_apply_verdict`'s body.** It returns `m.group(1)` verbatim, so the wider alternation flows straight through. Update only its docstring's verdict enumeration to mention `BLOCKED-STRUCTURAL`.
- **No new branch in `apply_finding`.** Every disposition that depends on the verdict is gated on `verdict == "APPLIED"`:
  - the missing-`## Summary` warning (`if verdict == "APPLIED" and not summary:`),
  - the findings-delta computation (`if verdict == "APPLIED" and diff_text:`),
  - the auto-fix follow-up call (the `and verdict == "APPLIED"` clause in the `if (auto_fix_introduced ...)` guard).
  - So `BLOCKED-STRUCTURAL`, like every non-`APPLIED` verdict, short-circuits to empty `introduced` / `resolved` tuples and no follow-up Claude call by definition. Do **not** add a defensive `BLOCKED-STRUCTURAL` arm here — that would be dead code.
- **Guard (a) — scope the verdict to opt-in callers so `create` never emits it (the deferred create-side trigger 2).** Add an `allow_structural_verdict: bool = False` parameter to `apply_finding`, and pass it into the prompt render as an `extra_var` (e.g. `structural_verdict_option`) that carries the `BLOCKED-STRUCTURAL` bullet text when `True` and an empty string when `False`. `create`'s `apply_finding` callers inherit the `False` default and are **not** edited, so the create-side prompt never offers the verdict and a create-side `apply_finding` cannot return it — closing the leak without any `create.py` change. The `detail` / review apply paths and the `escalate_to_split` bridge pass `True` in their later steps (5–8); until then the option is inert (see Deferred). This is the **prompt-render seam only** — it does *not* reintroduce the post-parse verdict branch ruled out just above, and it keeps step 3 scoped to `plan_tool/launcher.py` + `plan_tool/prompts/apply-finding.md` + tests.
- **Refresh the verdict enumerations in prose only** so a future reader sees the fourth token: the `parse_apply_verdict` docstring, the `ApplyFindingResult` class docstring (which enumerates `"APPLIED"` / `"NOT-APPLICABLE"` / `"BLOCKED"` / `"UNKNOWN"`), the `ApplyFindingResult` docstring's empty-delta line ("Both lists are empty for dry-run, BLOCKED/NOT-APPLICABLE/UNKNOWN, and clean APPLIED runs" — add `BLOCKED-STRUCTURAL` since it also yields an empty introduced/resolved delta), `apply_finding`'s step-6 docstring line that lists `(APPLIED / NOT-APPLICABLE / BLOCKED)`, and the pre-delta comment naming `BLOCKED / NOT-APPLICABLE / UNKNOWN`.
- **Leave the two sibling verdict seams untouched.** `_VERDICT_TOKEN_RE` (`PASS|FAIL|UNKNOWN`, the run-step / deep-reconcile contract) and `parse_deep_verdict` are different subcommand contracts that merely share the "parse a `## Verdict` token" shape. Widening `_APPLY_VERDICT_TOKEN_RE` must not touch them.

### `plan_tool/prompts/apply-finding.md`

- **Add the `BLOCKED-STRUCTURAL` option via the `structural_verdict_option` placeholder, not a static bullet** — so it appears in the `## Verdict` "Exactly one of:" list only for opt-in callers (guard (a) above) and is absent for `create`. Place the placeholder right after the existing `BLOCKED` bullet; `render_prompt` fills it with the bullet text when `allow_structural_verdict=True`, empty otherwise. Wording in the same terse style as its neighbors, e.g.:
  - `` `BLOCKED-STRUCTURAL` — the finding's only correct fix is to split this step into two type-pure steps (e.g. a mixed refactor + feature). An apply edit can't do that; a separate split/escalation path handles it. Emit this instead of `BLOCKED` when splitting is the remedy. ``
- **Keep the existing `BLOCKED` bullet's meaning intact** (file-conflict / new-file-required) so the apply Claude has a clear split between "can't apply because of plan-state conflict" (`BLOCKED`) and "can't apply because the right fix is a split" (`BLOCKED-STRUCTURAL`).
- **The frontmatter gate checks for the `structural_verdict_option` *placeholder*, not the literal `BLOCKED-STRUCTURAL` text** (`grep -q 'structural_verdict_option' plan_tool/prompts/apply-finding.md`). This is required by guard (a): the verdict's bullet text is the extra_var *value* supplied from `launcher.py` only when `allow_structural_verdict=True`, so the literal must **not** appear statically in the `.md` (a static occurrence would render for `create`'s unedited callers via `safe_substitute`, defeating guard (a)). A gate on the literal would therefore fail a correct implementation and pass a guard-(a)-breaking one — so it gates on the injection placeholder instead.
- **Do not touch rule 4** (the "emit `BLOCKED` … for a missing detail file" instruction) — that case is still a plain `BLOCKED`, not structural.

## Tests

All in `tests/test_launcher.py`. No real Claude subprocess is spawned; the delta test uses a fake invoker.

- `test_extracts_blocked_structural` — `parse_apply_verdict("## Verdict\nBLOCKED-STRUCTURAL\n")` returns `"BLOCKED-STRUCTURAL"`. (Add to `TestParseApplyVerdict`.)
- `test_blocked_structural_not_misparsed_as_blocked` — a response whose verdict block is `BLOCKED-STRUCTURAL` returns `"BLOCKED-STRUCTURAL"`, **not** `"BLOCKED"`; this is the ordering guard that fails the moment the alternation is mis-ordered. (Add to `TestParseApplyVerdict`.)
- `test_blocked_structural_verdict_skips_delta` — drive `apply_finding` with a fake invoker returning `## Summary\n- nothing\n\n## Verdict\nBLOCKED-STRUCTURAL\n`; assert `result.verdict == "BLOCKED-STRUCTURAL"`, `result.introduced_findings == ()`, `result.resolved_findings == ()`. Mirrors `TestApplyFindingValidationDelta.test_blocked_verdict_skips_delta`. (Add to `TestApplyFindingValidationDelta`.)
- `test_structural_verdict_option_gated` — render the apply-finding prompt with `allow_structural_verdict=False` and assert the `BLOCKED-STRUCTURAL` bullet is **absent**; render with `True` and assert it is **present**. This pins guard (a): create's callers (inheriting the `False` default) never get the verdict offered. (Add beside the prompt-render tests.)
- **Regression coverage already present:** the existing `test_extracts_blocked` / `test_extracts_not_applicable` / `test_anchors_on_last_verdict_block` cases must stay green unchanged — proof the widen didn't perturb the three original tokens.

### Test-creation order (feature step)

This is a **feature** step — a new verdict value the parser and prompt recognize. Add the three new tests **with** the implementation:

1. Write `test_extracts_blocked_structural` and `test_blocked_structural_not_misparsed_as_blocked` against the widened regex; the ordering-guard test must be red against the old `BLOCKED`-first alternation and green after the widen.
2. Write `test_blocked_structural_verdict_skips_delta` to pin that `apply_finding` needs no new branch.
3. **Green-before-done gate:** all three new tests plus every pre-existing `TestParseApplyVerdict` and `TestApplyFindingValidationDelta` case pass before this step is considered finished.

## Acceptance criteria

- `parse_apply_verdict("## Verdict\nBLOCKED-STRUCTURAL\n") == "BLOCKED-STRUCTURAL"`.
- A `BLOCKED-STRUCTURAL` verdict block does **not** parse as `"BLOCKED"`.
- `_APPLY_VERDICT_TOKEN_RE`'s alternation lists `BLOCKED-STRUCTURAL` before `BLOCKED`.
- `_VERDICT_TOKEN_RE` and `parse_deep_verdict` are unchanged.
- `apply_finding` driven to a `BLOCKED-STRUCTURAL` verdict returns `verdict == "BLOCKED-STRUCTURAL"` with empty `introduced_findings` / `resolved_findings` and makes no auto-fix follow-up call — with no new `BLOCKED-STRUCTURAL` branch added to `apply_finding`.
- `plan_tool/prompts/apply-finding.md` lists `BLOCKED-STRUCTURAL` as a fourth `## Verdict` option with split-specific semantics, rendered via the `structural_verdict_option` placeholder.
- **Guard (a):** the `BLOCKED-STRUCTURAL` option appears in the rendered apply-finding prompt **only** when `apply_finding` is called with `allow_structural_verdict=True`; the parameter defaults `False`, so `create`'s callers (unedited) never offer the verdict and a create-side `apply_finding` cannot return it — no `create.py` change.
- The three new tests and all pre-existing apply-verdict tests pass.

## References

- [`re` — Regular expression operations (Python 3.13)](https://docs.python.org/3/library/re.html) — confirms alternation is leftmost-match and `\b` word-boundary semantics, the basis for ordering `BLOCKED-STRUCTURAL` ahead of `BLOCKED`.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — the fake-invoker pattern the delta-skip test uses so the autouse gate never spawns a real `claude` binary.

## Deferred

- **The downstream consumer arm** — `plan_tool/cli/review_actions.py: _dispatch_apply_finding` checks `if result.verdict in ("BLOCKED", "NOT-APPLICABLE"):` and has an empty-diff no-op fall-through. Until a later step adds a `BLOCKED-STRUCTURAL` arm there (placed **before** that tuple branch and the empty-diff arm), a `BLOCKED-STRUCTURAL` verdict falls through to the existing "reported APPLIED but the plan file didn't change; nothing to keep" no-op. Confirmed harmless: no edit was made, nothing is wrongly kept — the only defect is misleading messaging — so this is safe to defer.
- **The producer wiring** — nothing emits `BLOCKED-STRUCTURAL` on a real run until the apply Claude is actually handed a structural finding through the convergence loops / review walk (later steps' `escalate_to_split` routing). This step only makes the parser and prompt able to *recognize* the token.
- **`plan_tool/completeness_report.py` blocked counts** — the `verdict == "BLOCKED"` filters there (the `blocked` / `blocked_ct` rollups) will not count `BLOCKED-STRUCTURAL`. Out of scope for this step; revisit if structural verdicts need a distinct rollup line.
