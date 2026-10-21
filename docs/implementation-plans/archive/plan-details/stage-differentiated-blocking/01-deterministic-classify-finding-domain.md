> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add deterministic `classify_finding_domain` in `review.py`

## Summary

Ship a pure, no-Claude domain classifier in `plan_tool/review.py` that reads conceptual-audit `Recommendation` prose and returns one of four closed labels: `code-logic`, `docs`, `unit-test`, or `unknown`. Matched signals follow fixed precedence (`code-logic` beats `unit-test` beats `docs`; `unknown` only when nothing matches). Step 2 will pass this function as `classify_domain` into `is_blocking_finding`; this step does not touch convergence predicates, completeness blocking arms, or `Recommendation` persistence. Tests in `tests/test_review.py` pin BACKLOG #91’s two conceptual shapes (plan-level code-behavior medium vs docs-shaped detail-listing medium) plus precedence and default cases.

## Table of Contents

- [Why](#why) — why severity-only blocking mislabels domains today and what this step adds.
- [Input](#input) — `Recommendation` fields the classifier reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — touched paths only.
- [Implementation](#implementation) — vocabulary, signals, precedence, fixtures, and boundaries.
- [Tests](#tests) — new cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes for reviewers and CI.
- [References](#references) — typing and pytest parametrize docs.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — follow-ups explicitly not in this step.

## Why

`completeness-audit` will apply different blocking bars at bare vs detail-grounded stages. The detail bar demotes medium **docs** and **unit-test** findings while keeping medium **code-logic** blocking. That needs a deterministic domain label derived from finding prose, not from severity alone. `Recommendation` often has no single target file (plan-level gaps, behavioral critiques), so a path-only rule misclassifies real findings — BACKLOG #91’s `merge-bridge-reauthor-context` medium is plan-level code behavior with no `.md` or test path. This step delivers the classifier and pins both #91 shapes as conceptual `Recommendation` fixtures; wiring it into `is_blocking_finding` and loop stops is step 2.

## Input

The classifier consumes `plan_tool/review.py:Recommendation` as its input envelope:

- **Primary text:** `title` and `body` (conceptual audit bullets land here).
- **Optional path hints:** `file_path` when set (e.g. MISSING_PARENT apply targets); backtick path tokens extracted from title/body/suggested_action.
- **Source hint:** `source` is a weak signal only (`test-strategy` → unit-test); conceptual sources are `plan-correctness` and `plan-completeness` — the classifier does not require either, but tests and #91 fixtures use them.
- **Not read for domain:** `severity`, `impact`, `complexity`, `anchor`, `id`, `redirect`, `target_signature` — severity stays on the blocking predicate in step 2.

Do not add a `domain` field to `Recommendation` or persist labels on saved reviews.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — closed domain constants, `classify_finding_domain(rec: Recommendation) -> str`, and any small private helpers for path/token scanning (keep helpers module-local).
  - `tests/test_review.py` — `TestClassifyFindingDomain` (or equivalent) with parametrized precedence cases and two named #91 fixture `Recommendation` builders.

## Implementation

### Closed vocabulary

Mint four module-level string constants (spellings are load-bearing for step 2 and JSON):

- `FINDING_DOMAIN_CODE_LOGIC` → `"code-logic"`
- `FINDING_DOMAIN_DOCS` → `"docs"`
- `FINDING_DOMAIN_UNIT_TEST` → `"unit-test"`
- `FINDING_DOMAIN_UNKNOWN` → `"unknown"`

Return only those four values from `classify_finding_domain`. A `frozenset` of allowed values is useful for tests and later callers.

### What the function does

- **Pure and deterministic** — no filesystem, no `Invoker`, no plan parse.
- **Matched-signal precedence** — collect independent signals, then return the highest-priority match:
  1. `code-logic`
  2. `unit-test`
  3. `docs`
  4. `unknown` (only when no signal fired)
- Do not return `unknown` when a lower-priority signal matched; do not “average” conflicting signals.

### Signal design (recommended approach)

Use layered heuristics over the text union `title + body + suggested_action` (and `file_path` when present). One workable split:

- **Path-shaped signals** — extract backtick paths similarly to `plan_tool/detail.py:extract_path_mentions` / `extract_filename_mentions` (lazy import from `detail` matches `check_files_coherence`; a local regex is fine if it stays aligned with detail path extensions). Classify each path with existing review helpers:
  - `review.py:_is_test_code_path` → unit-test signal
  - extension in `review.py:_PROSE_EXTS` (`.md`) or path under `docs/` → docs signal
  - extension in `review.py:_CODE_EXTS` and not test code → code-logic signal
- **Source token** — `source == "test-strategy"` → unit-test signal (even without a path).
- **Prose-shaped signals** — keyword/phrase lists for findings with no path (the #91 crux). Keep lists short and grep-friendly; document them beside the helper:
  - **Docs-shaped** — detail-body / authoring surface: e.g. “detail body”, “declared files cited”, “wording”, “FORMAT.md”, “section heading”, stale doc cross-reference patterns. The files-coherence nit string `(no declared files cited in detail body)` from `check_files_coherence` is the **wording model** for the docs fixture, not a producer to hook.
  - **Code-logic-shaped** — runtime behavior without a file anchor: e.g. “passthrough”, “call site”, “invoker”, “runtime”, “implementation”, “parameter”, “repo_root”, shell-out / subprocess behavior. Enough to classify `merge_bridge` / `repo_root` plan-level mediums.

When both docs paths and production code paths appear in the same finding, precedence must yield `code-logic` (parametrize this).

**Rejected alternative:** domain = f(path only) — fails #91’s plan-level code-logic pin and would demote behavioral mediums when prose cites a `.md` example.

### BACKLOG #91 fixture pins (conceptual `Recommendation`, not live diagnostics)

Build two stable test fixtures (constants or small factory functions in the test module):

1. **Code-logic pin** (`merge-bridge-reauthor-context` shape) — `source="plan-completeness"` (or `plan-correctness`), `severity="medium"`, `step_id=None`, `file_path=None`, title/body about `merge_bridge` runtime Claude cost and missing `repo_root` passthrough — behavioral, no target file. `classify_finding_domain` → `code-logic`.
2. **Docs pin** — `source="plan-completeness"`, `severity="medium"`, prose-shaped medium about the detail body not citing declared step files (use phrasing aligned with the files-coherence note, e.g. no declared files cited in the detail body / detail omits `files:` footprint). `classify_finding_domain` → `docs`. This is a **conceptual** finding for classifier tests; it is not `source="files-coherence"` and not emitted by `check_files_coherence` in production.

Step 2 will use the docs fixture to prove detail-bar demotion; this step only proves the classifier labels it `docs`.

### Call sites and wiring (this step)

- **Do not** call `classify_finding_domain` from `plan_tool/convergence.py`, `plan_tool/cli/completeness_cmd.py`, or `_completeness_has_blocking_findings` yet.
- **Do not** change `is_blocking`, `is_blocking_impact`, `BLOCKING_SEVERITIES`, or unconditional `files_coh_issues` arms.
- Export `classify_finding_domain` and the four constants from `review.py` for step 2 import (`convergence.py` will import review — existing pattern for `Recommendation`).

### Gotchas

- **Conceptual-only consumer** — downstream detail bar calls the classifier only for `plan-correctness` / `plan-completeness` mediums; the function can accept any `Recommendation`, but do not wire it to `files-coherence` or other deterministic buckets in this step.
- **Fail-safe default** — `unknown` means “no signal matched”, not “low confidence”; step 2 treats `unknown` medium as blocking at detail stage.
- **No severity reassignment** — do not remap audit severities here.
- **Orchestrator module** — keep new helpers private; avoid growing `review.py` imports beyond what path extraction needs.

## Tests

Green-before-done: every test listed here must pass before the step is finished.

### Tests for this step

- `test_classify_finding_domain_code_logic_fixture` — #91 `merge-bridge-reauthor-context`-shaped conceptual medium → `code-logic`.
- `test_classify_finding_domain_docs_fixture` — #91 docs-shaped conceptual medium (prose pin, not `files-coherence` source) → `docs`.
- `test_classify_finding_domain_test_path_in_body` — body cites `tests/test_foo.py` → `unit-test`.
- `test_classify_finding_domain_docs_md_path` — body cites `docs/AUDIT_FLOW.md` without production code paths → `docs`.
- `test_classify_finding_domain_code_py_path` — body cites `plan_tool/convergence.py` → `code-logic`.
- `test_classify_finding_domain_precedence_code_over_docs` — parametrized case with both `.md` and production `.py` paths → `code-logic`.
- `test_classify_finding_domain_precedence_code_over_unit_test` — production path plus test path in same finding → `code-logic`.
- `test_classify_finding_domain_precedence_unit_test_over_docs` — test path plus `.md` path, no production code path → `unit-test`.
- `test_classify_finding_domain_unknown_generic_prose` — generic plan wording with no path or keyword signal → `unknown`.
- `test_classify_finding_domain_test_strategy_source` — `source="test-strategy"` with otherwise bland prose → `unit-test`.
- `test_classify_finding_domain_returns_only_closed_vocab` — parametrized sweep over fixture set; every return value ∈ allowed constant set.

## Acceptance criteria

- `classify_finding_domain` exists in `plan_tool/review.py` and returns only `code-logic`, `docs`, `unit-test`, or `unknown`.
- Matched-signal precedence is `code-logic` > `unit-test` > `docs`; `unknown` only when no signal matches.
- #91 code-logic conceptual fixture (`merge-bridge-reauthor-context` shape, no `file_path`) classifies as `code-logic`.
- #91 docs conceptual fixture (prose-shaped medium about detail body vs declared files, not `files-coherence` diagnostic) classifies as `docs`.
- `Recommendation` has no new `domain` field; saved-review JSON shape unchanged.
- `is_blocking`, `is_blocking_impact`, and `_completeness_has_blocking_findings` are unchanged (no edits in `plan_tool/convergence.py` or `plan_tool/cli/completeness_cmd.py` for this step).
- `uv run pytest tests/test_review.py -k classify_finding_domain -q` is green.
- `rg 'classify_finding_domain' plan_tool/review.py tests/test_review.py` shows the public symbol and tests only (no premature convergence wiring).

## References

- [typing](https://docs.python.org/3/library/typing.html) — annotate `classify_finding_domain` and any small helper return types.
- [PEP 3102](https://peps.python.org/pep-3102/) — if helpers use keyword-only options later; step 2 may add `*` kwargs on siblings in `convergence.py`.
- [pytest parametrize](https://docs.pytest.org/en/stable/how-to/parametrize.html) — precedence matrix and closed-vocabulary sweep.

## Applicable guardrails

- **Plan Out of scope — reporting polish** — no CLI help, JSON fields, or report copy changes.
- **Plan Out of scope — stage bar in other loops** — do not wire the classifier into reconcile, create, or detail iteration loops.
- **Plan Out of scope — persisted `Recommendation.domain`** — no schema or sidecar field; classifier output stays ephemeral.
- **Plan Out of scope — `is_blocking_impact`** — do not fold domain into reconcile/convergence diagnosis materiality.
- **Plan Out of scope — classifier live-rate accuracy gate** — no corpus measurement or hit-rate CI in this step.
- **Plan Out of scope — `_completeness_has_blocking_findings` arms** — leave `files_coh_issues` and other non-conceptual arms as they are.
- **Step intent** — classifier only; #91 pins are conceptual `Recommendation` fixtures; docs pin is prose-shaped medium, not the live files-coherence diagnostic.

## Deferred

- `is_blocking_finding(..., classify_domain=classify_finding_domain)` and all caller wiring — step 2 (`plan_tool/convergence.py`, `tests/test_convergence.py`).
- Detail-bar demotion behavior (medium docs/unit-test advisory at finalize) — steps 2–6; classifier tests only label the docs fixture here.
- Live classifier accuracy corpus and hit-rate measurement — plan Deferred.
- Consolidating path mention extraction with `plan_tool/detail.py` into a shared leaf — optional reconcile/BACKLOG refactor; lazy import or local regex is enough for this step.
- Persisted domain on `Recommendation` or saved audits — plan Out of scope.
