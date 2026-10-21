# Step 7 — Harden _parse_emitted_concepts: provenance-check cited evidence and keep unpaired-surrogate and malformed output inside the fail-soft boundary

## Summary

Close the two remaining holes in the fail-soft boundary around model-emitted concept output in `plan_tool/concept_tree.py`. First, `_parse_emitted_concepts` must reject any emitted `title` or `evidence_rationale` containing an unpaired UTF-16 surrogate — `json.loads` accepts lone surrogates by design, and today such a title passes parsing and then crashes `concept_id`'s UTF-8 encode inside `emit_concept_tree`'s merge loop, outside the function's fail-soft try. Second, the existing evidence-membership check gets real substance: a rationale shorter than a new named minimum-excerpt constant is rejected, so a vacuous one-character "excerpt" can no longer satisfy the provenance gate. The parser also starts distinguishing a rejected response from a legitimately empty one, and `emit_concept_tree` prints a single stderr warning on rejection — silence keeps meaning "nothing to add", never "output was garbage". On green, invalid emitted output of every shape (provenance mismatch, unpaired surrogate, malformed or deeply nested JSON) returns `None` from `emit_concept_tree` without raising, leaves the caller's tree and any saved `concepts.json` unchanged, and is visible to the operator. Files: `plan_tool/concept_tree.py`, `tests/test_concept_tree.py`, plus `tests/test_concept_emit.py` (addition to the declared list — the emit test battery lives there).

## Table of Contents

- [Summary](#summary) — what the step does and the main design decision
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — the surrogate crash path and the vacuous-excerpt weakness, and which halves already hold
- [Input](#input) — the emit response contract, invoker seam, and stdlib facts this hardening rests on
- [Files (creates vs edits)](#files-creates-vs-edits) — the files touched and the edits per file
- [Implementation](#implementation) — the rejection predicates, the rejected-vs-empty split, and the parts that must not vary
- [Tests](#tests) — new unit tests, one fixture touch-up, and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — stdlib docs for the surrogate and JSON behavior the boundary guards against
- [Deferred](#deferred) — neighboring reporting, salvage, and consolidation work left out on purpose

## Why

This is gap 4 in the plan's problem statement ("fail-soft concept parse"). Two of the step title's guarantees already hold at HEAD and need only pinning where coverage is thin: the whole-rationale evidence-membership check (the `rationale.casefold() not in evidence.casefold()` rejection in `_parse_emitted_concepts`) and malformed-JSON rejection (the `json.JSONDecodeError` catch) shipped with the emit producer, and `tests/test_concept_emit.py` already pins both at the `emit_concept_tree` level (`test_emit_rejects_unsupported_claim_without_evidence`, `test_emit_returns_none_on_empty_or_invalid_output`). What does not hold is the surrogate half: `json.loads` explicitly accepts unpaired UTF-16 surrogates, `visit()` checks a title only with `isinstance` plus non-empty-after-strip, and `emit_concept_tree`'s fail-soft `try` wraps only the `invoker(prompt)` call and the parse — so an emitted title like `"bad \ud800 title"` sails through parsing and then raises `UnicodeEncodeError` when the merge loop calls `concept_id(title, parent_path)` (its `component.encode("utf-8")` step). That exception escapes `emit_concept_tree` entirely and lands mid-create in `plan_tool/create.py:create_plan`'s concept gate — "malformed text escapes as an exception mid-mutation", exactly what the plan's acceptance criterion forbids. Separately, the membership check has a vacuous pass: a rationale of `"a"` or `"."` is a substring of nearly any evidence, so a model can satisfy the provenance gate with a meaningless token and the junk lands in the new node's `source` field. Finally, a rejected response and a valid `{"concepts":[]}` both return `[]` today, so the caller cannot report rejections — the plan's criterion says rejection is reported, and silence must keep meaning "looks fine, nothing to add".

## Input

- **Emit response contract** (`plan_tool/prompts/concept-emit.md`, rendered by `plan_tool/concept_tree.py:render_concept_emit_prompt`): the response is JSON of shape `{"concepts":[{title, suggested_state, evidence_rationale, children?}]}`, with `evidence_rationale` specified as "a short, literal excerpt from EVIDENCE … so support can be checked locally", bounded by `CONCEPT_EMIT_MAX_DEPTH` (3) and `CONCEPT_EMIT_MAX_BREADTH` (12). The minimum-excerpt threshold this step adds is the deterministic teeth behind that "so support can be checked locally" promise.
- **Invoker seam** (`plan_tool/shell.py:shell_concept_invoker`): returns the backend's raw stdout string regardless of exit code — `tests/test_concept_emit.py:test_shell_concept_invoker_returns_stdout` pins that rc 9 still yields stdout. The parser is therefore the only defense between arbitrary backend text and `concept_id`.
- **Caller contract** (`plan_tool/create.py:create_plan`, the `enriched = emit_concept_tree(...)` arm followed by `concept_tree = enriched or fresh_concepts`): `None` is the single no-enrichment signal and the fallback to the deterministic tree is silent. The public signature and `Optional[ConceptTree]` return of `emit_concept_tree` are frozen; this step may not add parameters or new return shapes.
- **Stdlib facts** (see References): `json.loads` accepts lone-surrogate escapes (`"\ud800"`) and `json.dumps` re-emits them, so a test fixture can carry the surrogate in a plain Python string; `str.encode("utf-8")` on a lone surrogate raises `UnicodeEncodeError` (a `ValueError` subclass); `unicodedata.normalize("NFKC", …)` passes lone surrogates through unchanged, so normalization never masks them. Note `_validate_node`'s `except ValueError` around its own `concept_id` call already converts the encode error to `InvalidConceptTreeError` on the save/load path — the emit merge loop is the one unguarded `concept_id` caller.
- **No-persistence property** (`tests/test_concept_emit.py:test_emit_does_not_persist`): `emit_concept_tree` never writes; "rejected output leaves `concepts.json` unchanged on disk" is a property of the whole emit path that this step pins explicitly for the rejection shapes.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — harden `_parse_emitted_concepts` (surrogate rejection, minimum-excerpt threshold, rejected-vs-empty return split, wider malformed-input catch around `json.loads`); add the named minimum-excerpt module constant and a small surrogate-detection helper; teach `emit_concept_tree` to print one stderr warning when the parser rejects output, and update its docstring's "invalid model output … normal no-enrichment outcomes" line to mention the warning.
  - `tests/test_concept_tree.py` — one new test pinning that rejected emitted output leaves a previously saved `concepts.json` unchanged on disk (fits this file's persistence battery).
  - `tests/test_concept_emit.py` — declared in the step's `files:` list because the emit/parse test battery lives here and the new boundary tests belong beside it (the single new persistence test still lands in `tests/test_concept_tree.py`). New parser-boundary tests plus one fixture touch-up: the nested-chain candidates in `test_emit_enforces_depth_and_breadth_limits` use one-to-three-character rationales (`"one"`, `"2"`, …), which the new minimum-excerpt threshold would reject before the depth cap fires — lengthen those rationales so the depth limit stays the behavior under test.

## Implementation

The foundational logic is one rule: **everything the model emitted is rejected inside `_parse_emitted_concepts`, so nothing downstream of the parser ever sees a string `concept_id` cannot hash.** The emit path is the only place model output reaches `concept_id` (`plan_tool/concept_bootstrap.py`'s caller hashes section names from trusted plan text; `_validate_node` guards its own call) — so the fix lands entirely in this module.

- **Surrogate rejection (the crash fix).** In `visit()`, reject any node whose `title` or `evidence_rationale` contains a code point in U+D800–U+DFFF, before the node is appended. One way: a small helper (something like `_contains_unpaired_surrogate(text)`) scanning `'\ud800' <= ch <= '\udfff'`; an encode-probe (`text.encode("utf-8")` under `try`) is equally valid. Rejecting in the parser — rather than widening `emit_concept_tree`'s `except Exception` to cover the merge loop — is the key design decision: a broad catch around the merge would also swallow genuine bugs in `rederive_concepts` and the occupied-position bookkeeping, which is the rejected alternative. Checking `title` covers `parent_path` transitively (parents are prior validated titles), and checking the rationale directly is cheap insurance even though the membership check would usually catch it (trusted evidence text cannot contain lone surrogates).
- **Minimum-substance excerpt (the provenance teeth).** Add a module constant next to the existing emit caps — a directional name like `CONCEPT_EVIDENCE_MIN_EXCERPT_CHARS` — and reject a node whose stripped rationale is shorter than it. Recommended value: 8 characters — small enough for genuine short quotes, large enough that single tokens and punctuation can't vacuously pass; the implementer may tune the number, but it must be a named constant, not an inline literal. The existing whole-rationale membership check (`rationale.casefold() not in evidence.casefold()`) stays exactly as is — the threshold is additive, not a replacement.
- **Rejected vs. legitimately empty (the reporting split).** Change `_parse_emitted_concepts`'s return contract to distinguish the two: recommended shape is `Optional[list[...]]` — `None` for rejected/unusable output (every current `return []` rejection site, including a failed `visit`), `[]` only for a valid response with no candidates (`{"concepts":[]}`). It is a private helper with exactly one caller, so the signature change is free. In `emit_concept_tree`, a `None` parse result prints one warning line to stderr (e.g. via `print(..., file=sys.stderr)`; `sys` needs importing) and returns `None`; an empty list returns `None` silently, unchanged. The invoker-exception arm (`except Exception` around the invoke+parse) stays silent as today — it signals backend failure, not rejected output, and create already treats enrichment as best-effort.
- **Wider malformed-input catch.** Extend the catch around `json.loads` from `(json.JSONDecodeError, TypeError, InvalidConceptTreeError)` to also cover `RecursionError` (deeply nested JSON overflows the C scanner) and plain `ValueError` (which subsumes `JSONDecodeError`). Today `emit_concept_tree`'s outer `except Exception` happens to contain these, but the parser's own contract should be self-sufficient — a future caller must not inherit the hole.
- **Parts that must not vary:**
  - `emit_concept_tree`'s public signature, its `Optional[ConceptTree]` return, and the never-mutate-the-caller's-tree property are frozen — `create_plan`'s `enriched or fresh_concepts` fallback depends on all three.
  - Rejection stays all-or-nothing per response (the `visit()` False-propagation shape): a response containing one garbage node is untrustworthy wholesale; never salvage the valid siblings.
  - No Claude call is added anywhere (plan-level constraint); every new check is deterministic.
  - The existing depth/breadth caps, duplicate-key rejection (`_reject_duplicate_keys`), field-set validation, and the model-ids-are-ignored rule are untouched — the existing battery in `tests/test_concept_emit.py` must stay green with only the one sanctioned fixture touch-up named above.

## Tests

New tests in `tests/test_concept_emit.py` (using its `_response`/`_candidate` helpers; `json.dumps` round-trips lone surrogates, so fixtures can carry them in plain Python strings):

- `test_emit_rejects_lone_surrogate_title_without_raising` — a candidate whose title contains `"\ud800"` makes `emit_concept_tree` return `None`; no `UnicodeEncodeError` escapes.
- `test_emit_rejects_lone_surrogate_rationale` — a lone surrogate in `evidence_rationale` is rejected the same way.
- `test_emit_rejects_vacuous_short_excerpt` — a one-character rationale that is genuinely a substring of the evidence is still rejected (below the minimum-excerpt constant).
- `test_emit_accepts_excerpt_at_minimum_length` — an evidence-quoted rationale exactly `CONCEPT_EVIDENCE_MIN_EXCERPT_CHARS` long enriches successfully (boundary pin).
- `test_rejected_output_warns_but_valid_empty_is_silent` — rejected non-empty stdout produces exactly one stderr warning (capsys); `{"concepts":[]}` returns `None` with no output at all.
- `test_deeply_nested_output_is_rejected_not_raised` — a deeply nested JSON array bomb returns `None` instead of raising `RecursionError`.
- `test_rejection_leaves_input_tree_unchanged_per_category` — parametrized over provenance mismatch, surrogate, and malformed JSON: the caller's tree equals its pre-call deep copy (extends the existing `test_emit_failure_leaves_input_unchanged`).
- Fixture touch-up (sanctioned edit): lengthen the nested-chain rationales in `test_emit_enforces_depth_and_breadth_limits` so depth, not excerpt length, remains what that test rejects.

New test in `tests/test_concept_tree.py`:

- `test_rejected_emitted_output_leaves_saved_sidecar_bytes_unchanged` — save a tree via `save_concepts`, run `emit_concept_tree` once per rejection category, and assert `concepts.json`'s bytes are unchanged (the plan's on-disk acceptance criterion, pinned at the persistence boundary).

Existing pins that must stay green unmodified: `test_emit_rejects_unsupported_claim_without_evidence` (the already-true provenance-membership half), `test_emit_returns_none_on_empty_or_invalid_output`, `test_emit_does_not_persist`, `test_emit_failure_leaves_input_unchanged`, and `test_default_invoker_uses_real_backend_gate` (conftest's real-backend gate — no new test may spawn a backend; all use lambda invokers).

### Test-creation order (feature step)

This is a feature step: add the nine tests above with the implementation. Gate: every new test and the full existing `tests/test_concept_emit.py` + `tests/test_concept_tree.py` batteries are green (`uv run pytest tests/test_concept_emit.py tests/test_concept_tree.py -q`) before this step is finished.

## Acceptance criteria

- `emit_concept_tree` returns `None` — and raises nothing — for emitted output containing an unpaired surrogate in a title or rationale; no `UnicodeEncodeError` reaches the caller.
- `plan_tool/concept_tree.py` defines a named minimum-excerpt constant, and `_parse_emitted_concepts` rejects a stripped rationale shorter than it while keeping the whole-rationale evidence-membership check.
- `_parse_emitted_concepts` returns a distinct rejected signal (recommended: `None`) for unusable output and `[]` only for a valid empty candidate set; `emit_concept_tree` prints exactly one stderr warning on rejection and stays silent on a valid empty set and on invoker exceptions.
- A deeply nested JSON response is rejected by the parser itself, not converted to a `RecursionError` escape.
- Every rejection category leaves the caller's `ConceptTree` equal to its pre-call state and a previously saved `concepts.json` unchanged on disk.
- All nine new tests pass, and the pre-existing tests in `tests/test_concept_emit.py` pass with only the depth-fixture rationale lengthening as a diff.
- `emit_concept_tree`'s signature and return type are unchanged (`plan_tool/create.py` compiles and its concept-gate tests pass untouched).

## References

- [json — JSON encoder and decoder (Python 3 standard library)](https://docs.python.org/3/library/json.html) — documents `json.loads`/`JSONDecodeError` and the module's explicit acceptance of unpaired UTF-16 surrogates — the exact input this parser must reject rather than pass through.
- [codecs — Codec registry, error handlers (Python 3 standard library)](https://docs.python.org/3/library/codecs.html) — explains why UTF-8 encoding of lone surrogates raises `UnicodeEncodeError`, the crash `concept_id` hits today when a surrogate escapes the parser.

## Deferred

- Structured rejection telemetry or run-log entries — the stderr warning satisfies the plan's "reports the rejection" criterion; anything richer adds schema surface the plan forbids (BACKLOG #126–#128 territory).
- Per-node salvage of partially valid responses — deliberately out: all-or-nothing rejection is this step's pinned shape, and salvage is a design decision for a future enrichment iteration.
- Whitespace-tolerant excerpt matching — a rationale quoting evidence across a line wrap fails the membership check today (a safe false negative); loosening matching is not hardening and stays as a known limit.
- create.py-side messaging or fallback changes — the `enriched or fresh_concepts` arm in `create_plan` is untouched; `create.py` is outside this step's files.
- Consolidating the split emit/persistence test batteries (`tests/test_concept_emit.py` vs `tests/test_concept_tree.py`) — reconcile-owned housekeeping, not step work.
- `suggested_state` vocabulary enforcement — any string still maps to the safe `unreviewed` default (pinned by `test_emit_maps_unknown_state_to_safe_visible_default`); tightening it changes the emit contract, which no gap requires.
