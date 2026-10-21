# Candidate anchor/gate correction — review ledger

| Range | Head | Checks | Reviewer | Disposition |
| --- | --- | --- | --- | --- |
| `f9d3d2c4~1..f9d3d2c4` | `f9d3d2c4` | Final full suite (`uv run pytest tests/ -q -n auto`): 14050 passed, 190 skipped, exit 0 under `pipefail` | `/code-review high`, 8 passes | Converged, low-yield, after eight passes (2026-09-27) |

## Change under review

`f9d3d2c4` — "Name the non-addable collection and gate violation in candidate
corrections". The add-row-on-relationless-type refusal and the gate-failed
refusal now name the specific collection or violation kind and its remediation,
derived from closed gate facts (`roadmap_gates.VIOLATION_*` kinds,
`outcome.stage`, a validated `row_id`) and never from a violation's free-form
message, so a retry prompt never echoes model-authored prose.

## Settled decisions for the reviewer

- `_gate_correction` must never surface a `Violation`'s own `message` field —
  that field can carry arbitrary prior model output, and echoing it into a
  correction/prompt is the injection surface this change closes. Only the
  closed `kind` (checked against `_KNOWN_GATE_KINDS`), the stage's
  `artifact_key`, and a shape-validated `row_id` may appear.
- An unrecognized `kind` (a future `VIOLATION_*` not yet in the
  `kind`→condition mapping, or any value not in `_KNOWN_GATE_KINDS`) must not
  raise or leak. **Superseded by P1.2 (pass 1):** the bullet originally said
  the whole call falls back to the generic refusal text; that discarded every
  specific correction already built for the violation's siblings. The current,
  tested rule is per-violation degradation, not a whole-call fallback.
- `NON_ADDABLE_ROW_TYPES` is the public, sorted mirror of the existing
  `_RELATIONLESS_ADD_ROW_TYPES` set; the prompt's non-addable-collections
  notice must stay in sync with the parser's own rejection rule, not a
  restated list.

## Findings

The source records no fix commit ids per finding; "fixed" means fixed on the
review branch, with the named test where one exists.

### Pass 1

- **P1.1 — `_gate_correction` named the checked stage, not the violation's artifact** (high, CONFIRMED): `artifact_key` is a bare stage name while `Violation.artifact` is the filename, so retries were sent to the wrong location. **Disposition:** fixed — uses `violation.artifact`; `test_gate_correction_names_the_violations_own_artifact_not_the_checked_stage`.
- **P1.2 — an unrecognized kind discarded every already-built sibling correction** (medium, CONFIRMED, defensive only). **Disposition:** fixed — appends a fallback line and continues; `test_gate_correction_keeps_specific_guidance_beside_an_unrecognized_violation`.
- **P1.3 — the row-id regex duplicated `RECEIPT_SAFE_ID_RE` with a wider set (allowed `:`)** (medium, CONFIRMED). **Disposition:** fixed — reuses the constant; `test_gate_correction_treats_a_colon_bearing_row_id_as_unsafe_to_echo`.
- **P1.4 — the legacy selector prompt lacked the non-addable warning** (medium, CONFIRMED, framing corrected: the selector path never had a retry loop, so nothing regressed). **Disposition:** fixed — `test_selector_prompt_also_warns_about_non_addable_collections`.
- **P1.5 — five same-shape kinds missed their buckets on vocabulary** (medium, CONFIRMED for 5 of ~20 cited): `unanchored-constraint`, `uncited-removal`, `unreasoned-alternative`, `redundant-disposition`, `redundant-hosting-facet`; the cited `no-entity-reference`/`undefined-entity-reference` pair is correct. **Disposition:** fixed for the five (`test_gate_correction_routes_zero_content_and_redundant_kinds_to_their_matching_condition`); declined for ~15 idiosyncratic kinds — forced bucketing gives worse guidance than the generic fallback.
- **P1.6 — the relationless-add-row check in `_parse_operation` was unreachable** (low, CONFIRMED). **Disposition:** fixed — removed.
- **P1.7 — a shape-mismatched, violation-free `outcomes` tuple gets generic text indistinguishable from an ordinary refusal** (low, PLAUSIBLE). **Disposition:** declined — pre-existing; distinguishing tool-broken from candidate-wrong is a new capability. Not tracked; `test_candidate_returns_no_candidate_when_the_complete_gate_bundle_fails` pins today's behavior.
- **P1.8 — no test covered the mixed known/unknown-kind path** (low, CONFIRMED). **Disposition:** fixed with P1.2.

### Pass 2

- **P2.1 — `redundant-*` kinds got rename-shaped "keep unique" text; the fix is dropping extra rows** (medium, CONFIRMED). **Disposition:** fixed — own condition; `test_gate_correction_tells_a_redundant_kind_to_drop_the_extra_rows_not_rename_them`.
- **P2.2 — the docstring described the wrong branch of `check_duplicate_row_ids`** (medium, CONFIRMED). **Disposition:** fixed — states only the verified fact and points to the gate.
- **P2.3 — the unrecognized-kind fallback used the bare stage key as location** (low, CONFIRMED). **Disposition:** fixed — `test_gate_correction_uses_the_violations_own_artifact_for_an_unrecognized_kind_too`.
- **P2.4 — the docstring was a multi-line block against the terse-comment rule** (low, CONFIRMED). **Disposition:** fixed with P2.2.
- **P2.5 — the notice paragraph was duplicated into both templates with no equality test** (low, CONFIRMED). **Disposition:** fixed — shared fragment; `test_batch_and_selector_prompts_share_the_non_addable_collections_notice`. The fragment was later replaced (P5.x).
- **P2.6 — nothing tied the kind table to the `VIOLATION_*` set; `undisposed-attribute` still fell to generic** (medium, CONFIRMED). **Disposition:** fixed — `_INTENTIONALLY_GENERIC_GATE_KINDS` (15 kinds); `test_gate_correction_classifies_every_known_kind_by_name`. Full per-kind rewrite stays declined.

### Pass 3

- **P3.1 — four drop-shaped `duplicate-*` kinds still got rename-shaped guidance** (medium, CONFIRMED): `duplicate-inherited-decision`, `duplicate-feedback-id`, `duplicate-store-reference`, `ordering-plan-id-duplicate` — the P2.1 defect unswept on siblings. **Disposition:** fixed — `_DROP_EXTRA_ROWS_GATE_KINDS`; `test_gate_correction_tells_a_drop_shaped_duplicate_kind_to_drop_not_rename`.
- **P3.2 — a 6-line `_INTENTIONALLY_GENERIC_GATE_KINDS` comment** (low, CONFIRMED). **Disposition:** fixed — two lines.
- **P3.3 — the fragment read had no missing-file guard (bare `FileNotFoundError`)** (low, CONFIRMED). **Disposition:** fixed for both template reads via `_read_candidate_prompt_file`; `test_missing_candidate_prompt_file_is_a_domain_error_not_a_bare_file_not_found`. Caused P4.1.
- **P3.4 — the fragment is re-read on every call** (low, PLAUSIBLE). **Disposition:** declined — the main template is equally uncached and a module-level cache breaks `prompts_dir()` monkeypatching; superseded by P5.x.

### Pass 4

- **P4.1 — pass 3's guard let a missing template escape `request_replacement`** (high, CONFIRMED, self-inflicted): `CandidateProposalError` is a `ValueError`, not the `OSError` the old `except` caught; the only unswept caller of three. **Disposition:** fixed — except tuple `(OSError, CandidateProposalError)`; `test_request_replacement_surfaces_a_missing_prompt_template_as_failed_not_uncaught`. Changing an exception type is class-wide: sweep from "who catches the old type".
- **P4.2 — the fragment's `Template.substitute()` sat outside the domain-error mapping** (medium, CONFIRMED). **Disposition:** fixed — own try/except; `test_non_addable_collections_fragment_substitution_failure_is_a_domain_error` (removed with the fragment).
- **P4.3 — the `is_file()` guard missed permission/TOCTOU/encoding failures and reinvented `roadmap.read_roadmap_text`** (medium, CONFIRMED). **Disposition:** fixed — delegates to `read_roadmap_text`.
- **P4.4 — `render_candidate_question_prompt` uses a bare `read_text()`** (low, CONFIRMED). **Disposition:** declined — pre-existing, correctly handled by its caller's `except OSError`, outside scope. Re-raised as P5.5.

### Pass 5

- **P5.1 — the fragment's missing-file error was relabeled by pass 4's `except (KeyError, ValueError)`** (high, CONFIRMED, self-inflicted). **Disposition:** fixed by removing the mechanism (below).
- **P5.2 — `correction_reason`'s error sat inside the substitution try and was relabeled** (medium, CONFIRMED, pre-existing). **Disposition:** fixed — validation moved before the `try`; `test_correction_reason_on_a_non_batch_capsule_raises_its_own_specific_message`.
- **P5.3 — the kind→remedy classifier is a prefix matcher with hand-curated exceptions; no test catches a future kind in the wrong bucket** (medium, CONFIRMED). **Disposition:** tracked #431 — a `remedy_shape` field at ~90 `Violation(...)` sites is out of this diff's module scope; the current kind set is verified by execution.
- **P5.4 — the fragment re-templated a static string per call** (medium, CONFIRMED; reframes P3.4). **Disposition:** fixed by removing the mechanism (below).
- **P5.5 — `render_candidate_question_prompt`'s bare `read_text()` (raised twice, with P4.4)** (low, CONFIRMED). **Disposition:** tracked #432.
- **P5.6 — `_INTENTIONALLY_GENERIC_GATE_KINDS` was a production constant read only by a test** (low, CONFIRMED). **Disposition:** fixed — moved to `tests/test_roadmap_candidate.py`.

P5.1/P5.2/P5.4 were closed together: three passes each patched the same ~10-line piece, so the fragment file, `Template`, and error mapping were replaced by `_non_addable_collections_notice()`, a plain string function (`plan_tool/prompts/roadmap-candidate-non-addable-collections.md` deleted). Pass 5 was a "the loop is auditing its own edits" signal, answered by removing the class rather than patching a fourth time.

### Pass 6 — zero correctness bugs; first low-yield round

- **P6.1 — a branch comment restated the module comment** (low, CONFIRMED). **Disposition:** fixed.
- **P6.2 — `_non_addable_collections_notice()`'s docstring cited an inapposite precedent** (low, CONFIRMED). **Disposition:** fixed — states its own reason; the Python-string decision is not reverted.
- **P6.3 — `_DROP_EXTRA_ROWS_GATE_KINDS` dispatches by two mechanisms in one `elif`** (low, CONFIRMED). **Disposition:** tracked #431 — no new item.
- **P6.4 — the ledger's settled-decision bullet was stale against P1.2** (low, CONFIRMED). **Disposition:** fixed — annotated as superseded.

### Pass 7 — zero correctness bugs; five advisory findings

- **P7.1 — `_read_candidate_prompt_file` was a single-use wrapper against the inline-closure idiom** (low, CONFIRMED). **Disposition:** fixed — inlined with `unreadable_template`; `BACKLOG.md` #432's suggested approach updated.
- **P7.2 / P7.4 / P7.5 — three paragraph-length comments/docstrings** (low, CONFIRMED). **Disposition:** fixed — trimmed; the `_DROP_EXTRA_ROWS_GATE_KINDS` comment points at #431.
- **P7.3 — `isinstance(capsule, CandidateContextBatchCapsule)` evaluated three times** (low, CONFIRMED). **Disposition:** fixed — cached as `is_batch`.

### Pass 8 — zero new correctness bugs; four low findings

Prior tracked/declined items (#431, P1.7, the load-bearing `getattr(violation, ...)` reads) were re-checked and not re-reported.

- **P8.1 — the `PatternRow` anchor diagnostic named only `system_patterns`** (low, CONFIRMED). **Disposition:** fixed — same two-collection substitution as `_invalid_row_type_diagnostic`; `test_candidate_delta_pattern_row_anchor_diagnostic_names_both_collections`.
- **P8.2 — `_gate_correction` inlined the safe-to-echo predicate** (low, CONFIRMED). **Disposition:** fixed — calls `roadmap_feedback.is_receipt_safe_id`; no import-cycle risk.
- **P8.3 — the notice string was rebuilt per call** (low, CONFIRMED). **Disposition:** fixed — module-level `_NON_ADDABLE_COLLECTIONS_NOTICE`.
- **P8.4 — three more over-long comments (the P7.2 class, unswept at siblings)** (low, CONFIRMED). **Disposition:** fixed.

## Out-of-range / recall-mode findings

_(none)_

## Convergence status

**Converged after eight passes (2026-09-27), low-yield.** Pass 6 was clean
(zero correctness findings). Pass 7 and pass 8 were each clean of correctness
bugs — 5 and 4 low-severity cleanup findings respectively, all fixed. Three
consecutive passes each added only low/advisory-severity findings, meeting the
stopping rule's low-yield exit. Passes 1–5 each found and fixed genuine,
material defects, including two self-inflicted regressions (P4.1 from pass 3's
fix; P5.1 from pass 4's fix); passes 6–8 found none. Pass 5 carried the
non-converging signal (three passes correcting the same fragment mechanism) and
was resolved by removing the mechanism. No further pass is warranted; the next
`/code-review` on this area treats this diff's baseline as converged and
reviews only its own new changes.

Open items: `tracked` #431 (P5.3, P6.3) and #432 (P5.5, P4.4). No `pending` findings.

Final full-suite result: 14050 passed, 190 skipped in 135.49s, exit 0 under
`pipefail`.
