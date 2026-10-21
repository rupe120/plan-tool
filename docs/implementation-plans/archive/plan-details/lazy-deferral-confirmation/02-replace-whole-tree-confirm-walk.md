# Step 2 — Replace the whole-tree concept walk with a deferral-only gate

## Summary

`create`'s concept step stops walking every concept node for an include/defer/wont_do decision. Instead, `plan_tool/create.py:_review_create_concepts` becomes a **deferral-only gate**: it confirms and signs off only the concepts whose proposed decision is `defer` or `wont_do`, leaves included concepts untouched (no owner assignment, no record entry), and under `-y` records a proposed deferral **unconfirmed** (`review_state="unreviewed"`) instead of silently signing it off. The two concept-persistence sites in `create_plan` then write `concepts.json` only when the reviewed tree carries at least one defer/wont_do node — so an un-deferred plan gets no concept record at all. On green: `create -y` on a normal plan (whose bootstrap nodes all carry `decision=""`) writes no `concepts.json` and calls neither `synchronize_concepts` nor `save_concepts`; a proposed deferral carried in (e.g. from a resumed/`--from-existing` record) is persisted unreviewed rather than approved.

## Table of Contents

- [Why](#why) — why the whole-tree walk is the wrong gate and what replaces it
- [Input](#input) — the record shape and step-1 output this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files and their edits
- [Implementation](#implementation) — reshape the gate, gate the writes on has-deferral
- [Tests](#tests) — unit gate tests plus the integration reconciliations
- [Acceptance criteria](#acceptance-criteria) — checkable observable behaviors
- [References](#references) — the docs relevant to this step
- [Deferred](#deferred) — what steps 3, 4, and the backlog own

## Why

Today `plan_tool/create.py:_review_create_concepts` walks **every** node in the bootstrap tree, prompting include/defer/wont_do per node and, for includes, resolving owner step ids — then calls `review_concept_scope` over the full id list with `sign_off=interactive`. Two problems this step fixes: it reviews the wrong thing (included concepts need no sign-off — a committed step is its own proof, and `check_concept_coverage` in `plan_tool/review.py` is already inert on unreviewed nodes), and it is skipped entirely when non-interactive, so under `-y` (how these plans are authored) the tool's suggestions are silently accepted — the exact founding incident (BACKLOG #121). Step 1 stopped eager enrichment but kept writing a thin bootstrap `concepts.json` for every plan, explicitly deferring the record-absence rework to this step's declared "persists only defer/wont_do decisions." This step delivers that: confirm and persist only deferrals, and leave un-deferred plans with no record — which also breaks the whole-bundle fingerprint staleness for the common case (no record means nothing to go stale).

## Input

- **Step 1's output** — step 1 removed the `emit_concept_tree` enrichment call so the create-path tree is now the deterministic `bootstrap_concepts` result, one node per body section. Those nodes carry `decision=""` and `review_state="unreviewed"` (`plan_tool/concept_bootstrap.py:bootstrap_concepts` sets neither, so both take their `ConceptNode` defaults). This means a normal `create` has **no** proposed deferral — every section node is `decision=""` — so the new gate is a silent no-op on the common path and writes no record.
- **The concept record shape** — `plan-details/<slug>/concepts.json` (`ConceptTree`/`ConceptNode` in `plan_tool/concept_tree.py`), whose `decision` ∈ `{"", "include", "defer", "wont_do"}` and `review_state` ∈ `{"unreviewed", "approved"}` fields this step reads and narrows. The writer stays unchanged.
- **`review_concept_scope`** (`plan_tool/concept_review.py`) — applies a decision set and, with `sign_off=True`, flips `review_state` to `"approved"` and stamps the sign-off metadata. This step keeps calling it, but scopes the id list and the `sign_off` flag to deferrals only.
- **The signed/unsigned persistence split** — `create_plan` decides `signed_concept_scope = any(node.review_state == "approved" ...)` at two sites: the post-write block (after `parsed_written_plan`) and the iterate-tail block (`if budget.enabled and signed_concept_scope:`). The signed arm routes through `synchronize_concepts`; the unsigned arm through `save_concepts`. Both call shapes are behavior-preserving contracts established by the concept-write-integrity plan and must not change beyond adding the has-deferral guard.

Verification limit: legacy plans with an empty or absent record must stay parseable, so record-absence is a valid state, not an error (`check_concept_coverage` returns `[]` when `concepts_path(...).is_file()` is False).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — reshape `_review_create_concepts` into the deferral-only gate; narrow the persisted tree to defer/wont_do nodes; guard both concept-persistence arms (post-write and iterate-tail) so `synchronize_concepts` / `save_concepts` run only when the tree carries a defer/wont_do node.
  - `tests/test_create.py` — reconcile the whole-tree-walk unit tests and the two integration tests coupled to per-concept confirmation / record-always-written; add the deferral-gate and record-absence tests.

## Implementation

**Reshape the gate (`plan_tool/create.py:_review_create_concepts`).** The behavior changes from "confirm every node + assign owners" to "confirm only proposed deferrals."

- **Select the deferrals, ignore the rest.** Walk `tree.concepts` but act only on nodes whose proposed decision (`node.decision`) is `defer` or `wont_do`. A node with `decision` `""` or `"include"` gets no prompt, no owner, and no place in the persisted record. Drop the owner-resolution walk (the `owners` / `accepted_owner_ids` dict machinery and the uncommitted-owner validation) — included concepts no longer produce `Step.concept_ids` at create time.
- **Confirm interactively; record unconfirmed under `-y`.** Keep the existing `interactive` derivation (`sys.stdin.isatty() and not yes`, threaded from the call site). When interactive, prompt to confirm each proposed deferral and, on confirm, sign it off. When not interactive, leave it `review_state="unreviewed"` with its `decision` intact — never approved. The cleanest way to keep this behavior is to keep calling `review_concept_scope` but pass only the deferral node ids and `sign_off=interactive` (the same flag semantics it has today: approve on interactive, leave unreviewed otherwise).
- **Narrow the returned tree to the deferral nodes.** The reviewed tree this function returns should contain only the defer/wont_do nodes — that is what "persists only defer/wont_do decisions" means, and it makes the empty-tree case (the common path) the record-absent signal downstream. `render_scope_decisions` (`plan_tool/concept_sync.py`) already renders only approved defer/wont_do nodes, so dropping the section include nodes changes nothing about the rendered `## Deferred` section.
- **Keep the signature frozen.** Return `(ConceptTree, list[Step])` as today. The steps come back unchanged (their `concept_ids` untouched — empty on the normal path), so the call site (`plan = plan.model_copy(update={"steps": reviewed_steps})`) needs no edit. One way to keep this minimal: return the caller's `steps` list straight through. Do **not** widen or shrink the signature — the single caller and the monkeypatch in `tests/test_create.py` both depend on the pair shape.

**Gate the two persistence writes on has-deferral (`plan_tool/create.py:create_plan`).** With the narrowed tree, `concept_tree.concepts` is empty on the common path. Both persistence sites must skip all concept I/O when it is empty:

- **Post-write block** (the `if signed_concept_scope:` / `else:` arms right after the first `parsed_written_plan = parse_plan(plan_path)`): when the tree has no nodes, write nothing — no `synchronize_concepts`, no `save_concepts`, no `concepts_path` touch. When it has approved deferrals, keep the signed arm exactly as-is (including the sync-failure cleanup that unlinks `concepts_path(plan_path)` and `plan_path` before raising). When it has only unreviewed deferrals, keep the unsigned `save_concepts` arm — but reach it only when the tree is non-empty.
- **Iterate-tail block** (`if budget.enabled and signed_concept_scope:` / `elif budget.enabled:` before `return CreateResult`): same guard — the `elif budget.enabled:` `save_concepts` arm must additionally require a non-empty tree, and the whole block is skipped when there are no deferral nodes.
- **Do not touch the failure/restore/manifest semantics.** The signed arm's post-sync reparse, the `contextlib.suppress(FileNotFoundError)` cleanup, and the manifest-commit window (the collision-replace restore machinery) are load-bearing and unrelated to this change. Add only the emptiness guard.

**Print a `create` run-summary line for a pending deferral (authoring-time surface).** When the gate recorded one or more **unreviewed** deferrals (the `-y` path), `create_plan` prints a run-summary line before returning, naming each pending deferral's **bare `node.id`** (the exact token `scope-review --concept` consumes — not the `concept-<id>` anchor form) and title, plus the remedy — e.g. `⚠ 1 concept deferral recorded pending review — confirm with: plan-tool scope-review <name> --concept <node.id> defer|wont_do`. This closes the founding incident at the moment it happens: an operator running only `create -y` sees the pending deferral immediately, not just on a later `status`/audit. It complements step 3's `status` and completeness-report surfaces (same bare-id token, three places). Print nothing when the gate recorded no deferral (the common path).

**Constraints and gotchas.**

- **`synchronize_concepts` / `save_concepts` call shapes stay unchanged.** The concept-write-integrity plan pinned these as the single sidecar-writer boundary; this step only adds a guard in front of them, never a new writer or a changed argument set.
- **A tree entering `synchronize_concepts` must keep its non-empty `plan_fingerprint`.** Narrowing the node list does not touch `ConceptTree.plan_fingerprint` (set from the source hash near `bootstrap_concepts`), so `_validate_tree` still passes. Don't clear or recompute it here.
- **Resume / `--from-existing` carries deferrals forward.** A prior `concepts.json` (loaded into `saved_concepts` and merged by `rederive_concepts`) can supply a `defer` node at create time. That is the realistic source of a `-y` proposed deferral, and the gate must record it unreviewed, not approved. Confirm the narrowed record round-trips through `load_concepts` + `rederive_concepts` on a resumed run (keep the resume test green).
- **Keep the `concept_invoker` parameter.** It no longer feeds enrichment, but the interactivity heuristic at the call site still reads `concept_invoker is not shell_concept_invoker`; removing it would churn every caller and test (per step 1's captured lesson).

Foundational logic this step owns: *the rule for when `create` materializes and signs off a concept — only a proposed `defer`/`wont_do` is confirmed and persisted, includes get nothing, and a plan with no deferral gets no record.* The parallel deferral producers live elsewhere and are **not** rewired here: detail's shared-find routing (`plan_tool/detail.py`) is step 4; the decomposition "defer a branch with no live scenario" instruction in `create.py` only omits from the step array and is not concept-wired; the `concept-unsigned-deferral` consumer (`plan_tool/review.py:check_concept_coverage`, its `node.decision in {"defer","wont_do"}` reminder branch) is what step 3 promotes from info to a surfaced (non-blocking) signal. Cited here so the reader sees the shared surface; each is deferred to its owning step below.

## Tests

Reference file: `tests/test_create.py`.

**Reconcile the existing whole-tree-walk unit tests** (`_review_create_concepts`, near the top of the file) to the deferral-only world:

- `test_review_create_concepts_unattended_keeps_proposals_unsigned` — keep; a `defer` node with `yes=True` stays `review_state="unreviewed"`, `decision="defer"`, and `input_fn` is never called. (Largely already true.)
- Replace the include-owner tests (`..._assigns_explicit_owner_interactively`, `..._allows_shared_explicit_ownership`, `..._rejects_uncommitted_owner`, `..._does_not_infer_owner_from_title`) with gate behavior: an `include`/`""` node yields no owner, no prompt, and no place in the returned tree; the returned steps' `concept_ids` stay empty.

**Add deferral-gate unit tests:**

- `test_deferral_gate_ignores_included_concepts` — a tree of only `include`/`""` nodes returns an empty (or node-free) tree, steps unchanged, and `input_fn` is never called.
- `test_deferral_gate_signs_off_confirmed_deferral` — interactive confirm of a proposed `defer` node returns it `review_state="approved"`, `decision="defer"`.
- `test_deferral_gate_records_unconfirmed_deferral_under_yes` — `yes=True` on a proposed `defer` node returns it `review_state="unreviewed"`, `decision="defer"`, no prompt.
- `test_deferral_gate_narrows_to_deferrals` — a mixed tree (some includes, one `wont_do`) returns only the `wont_do` node.

**Reconcile / add integration tests** (the `create_plan` end-to-end class):

- `test_undeferred_create_writes_no_concept_record` — `create -y` on a normal plan writes no `concepts.json` (`concepts_path(plan_path).is_file()` is False) and neither `synchronize_concepts` nor `save_concepts` is called (spy/monkeypatch to assert zero calls). This replaces the `concepts_path(...).is_file()` assertion in `test_retains_deterministic_concepts_and_uses_independent_invoker`.
- Replace `test_assigns_signed_concept_id_to_written_committed_step` — the create gate no longer signs off includes onto committed steps. New assertion: an interactive `create` of a normal plan assigns no `concept_ids` and writes no record.
- `test_carried_deferral_recorded_unconfirmed_under_yes` — seed a prior `concepts.json` (resume path) with a `defer` node, run `create -y`, and assert the persisted record contains that node `review_state="unreviewed"` (not approved).
- `test_create_yes_prints_pending_deferral_summary` — a `create -y` that records a pending deferral prints a run-summary line naming the node's **bare `node.id`** (the token `scope-review --concept` consumes) and `plan-tool scope-review`; an un-deferred `create -y` prints no such line.
- `test_resume_reuses_saved_concepts_without_enrichment` — keep green; confirm the narrowed record round-trips through resume.

### Test-creation order (feature step)

This is a **feature** step. Author each unit test above alongside the gate reshape, and the integration reconciliations alongside the persistence-guard edit. Green-before-done gate: every new and reconciled test must pass before the step is finished. Run `uv run pytest tests/test_create.py -q` and the concept suites (`tests/test_concept_review.py`, `tests/test_concept_sync.py`) to confirm no downstream regression.

## Acceptance criteria

- `_review_create_concepts` on a tree of only `include`/`""` nodes returns those steps with `concept_ids` unchanged and a tree carrying no defer/wont_do node, and never calls `input_fn`.
- `_review_create_concepts` interactive-confirming a proposed `defer` node returns it with `review_state="approved"`, `decision="defer"`.
- `_review_create_concepts` with `yes=True` on a proposed `defer` node returns it with `review_state="unreviewed"`, `decision="defer"`, and does not prompt.
- `create -y` on a plan with no proposed deferral leaves no `concepts.json` on disk and invokes neither `synchronize_concepts` nor `save_concepts`.
- `create -y` whose gate sees a proposed deferral (e.g. carried via a resumed record) persists a `concepts.json` containing that node with `review_state="unreviewed"`, and prints a run-summary line naming its **bare `node.id`** and `plan-tool scope-review`.
- Editing an un-deferred plan's prose raises no `StaleConceptTreeError`, because no record exists to invalidate.
- `uv run pytest tests/test_create.py -q` is green.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `ConceptTree`/`ConceptNode` are dataclasses; read for the field defaults (`decision=""`, `review_state="unreviewed"`) the gate narrows on.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — the `concepts.json` serialization the persistence guard decides whether to write.
- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — `tmp_path` fixture for the record-absence and resume integration tests.

## Deferred

- Promoting an unconfirmed proposed deferral from info-only to a surfaced (non-blocking) signal — owned by step 3 (`plan_tool/review.py`, `plan_tool/completeness_report.py`, `plan_tool/cli/inspect.py`). This step only records the deferral unreviewed; step 3 owns the surface.
- Materializing a **new** deferral at detail's shared-find routing via `review_concept_scope` + `synchronize_concepts` — owned by step 4 (`plan_tool/detail.py`). This step does not add a deferral producer.
- Wiring the decomposition "defer a branch with no live scenario" instruction (`plan_tool/create.py`) into a concept node — out of this plan's create scope; it currently only omits from the step array.
- Consolidating the two `detail_deferral_step_ids` readers and any concept-owner machinery cleanup — reconcile-owned, unaffected here.
