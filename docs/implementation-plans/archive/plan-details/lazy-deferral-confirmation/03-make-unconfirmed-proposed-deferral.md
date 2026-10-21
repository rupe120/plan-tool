# Step 3 — Make an unconfirmed proposed deferral a surfaced (non-blocking) signal instead of info-only

<!-- Decision (settled): surfaced, non-blocking — never blocking. Only an operator scope-review decision resolves an unsigned deferral, so a blocking finding would wedge the --iterate loop. -->


## Summary

An unreviewed proposed deferral in the concept record stops being a silent info advisory and becomes a signal an operator actually sees. The detector in `plan_tool/review.py:check_concept_coverage` already emits a `concept-unsigned-deferral` finding for a node whose `decision` is `defer`/`wont_do` but whose `review_state` is not `approved`; step 3 lifts that finding out of the swept "info" bucket and gives it a dedicated, visible home in two surfaces: the completeness report (`plan_tool/completeness_report.py`, a new disposition kind + heading) and the plan status view (`plan_tool/cli/inspect.py:_print_status`, a summary line). The key design decision: **surface, do not block** — the finding stays out of `plan_tool/review.py:SELF_CONSISTENCY_SOURCES` and never flips an exit code, because only an operator `scope-review` decision (not `apply_finding` or the `--iterate` loop) can resolve it. On green: a plan whose record carries an unreviewed `defer` node shows a "N unsigned concept deferral(s) pending review" line under `plan-tool status`, and the completeness report renders those findings under their own heading instead of burying them in the generic diagnostic/info list.

## Table of Contents

- [Why](#why) — why an info-only reminder is effectively invisible and must be surfaced
- [Input](#input) — the concept record shape and step-2 output this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the three source files and their edits
- [Implementation](#implementation) — reuse the one detector, add a report disposition, add a status line, keep it non-blocking
- [Tests](#tests) — the coupled test to flip and the new surface tests
- [Acceptance criteria](#acceptance-criteria) — checkable observable behaviors
- [References](#references) — the docs relevant to this step
- [Deferred](#deferred) — what this step leaves for the backlog and later work

## Why

Step 2 stopped `create -y` from silently signing off its own proposed deferrals — it now records them `review_state="unreviewed"` so an operator can review them later. But "later" never comes if the reminder is invisible. Today `plan_tool/review.py:check_concept_coverage` emits the unreviewed deferral as a `Recommendation` at `severity="info"`, and info is the silent floor: in `plan_tool/completeness_report.py:deferred_kind` the finding falls through to the generic `"diagnostic"` bucket (it is not apply-eligible, so it returns before the info branch is even reached), and `plan-tool status` shows nothing about concepts at all. So the exact behavior step 2 was built to fix — a proposed deferral the operator never actually saw — comes back through the reporting layer. This step makes the pending review a signal an operator running the ordinary health commands (`status`, a completeness audit) cannot miss, while keeping it non-blocking so the automated convergence loop — which has no way to approve a concept decision — still converges.

## Input

- **Step 2's output** — step 2 reshaped `create`'s concept gate so a proposed `defer`/`wont_do` under `-y` is persisted with `review_state="unreviewed"` (decision intact) rather than signed off, and writes `concepts.json` only when the record carries at least one such node. So the record this step reads either is absent (the common, un-deferred plan → nothing to surface) or carries one or more unreviewed deferral nodes.
- **The `concept-unsigned-deferral` finding** — `plan_tool/review.py:check_concept_coverage` already produces one `Recommendation` per unreviewed `defer`/`wont_do` node: `source=CONCEPT_UNSIGNED_DEFERRAL_SOURCE`, `severity="info"`, `step_id=None`, `anchor=f"concept-{node.id}"`. This step reads that finding as the single source of truth for "which deferrals need review" — the detection predicate (`node.review_state != "approved" and node.decision in {"defer","wont_do"}`) stays owned by this function and is not re-implemented anywhere.
- **The completeness disposition ladder** — `plan_tool/completeness_report.py:deferred_kind` maps a `Recommendation` to a disposition string; `_HEADINGS` and `WHY` map that string to a section heading and rationale; the `by_kind` count dicts (the report summary line, the "Other deferred buckets" render loop, and the terminal summary) enumerate the known kinds. This step adds one new kind and must touch every place that enumerates the set.

Verification limit: an absent record is a valid, common state (no `concepts.json`), so the status surface and the report must both treat "no finding" as normal, not an error.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — keep `check_concept_coverage` emitting the `concept-unsigned-deferral` finding, but raise it above the silent info floor (recommend `severity="low"`) and enrich its `body`/`suggested_action` to name the operator remedy (`plan-tool scope-review`). Confirm the source stays **out** of `SELF_CONSISTENCY_SOURCES` (it already is) — that is the non-blocking invariant this step must not break. No new detector, no predicate change.
  - `plan_tool/completeness_report.py` — add a dedicated `"unsigned-deferral"` disposition: a new branch in `deferred_kind` keyed on `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` (placed **before** the `is_apply_eligible` check so it wins over the generic `"diagnostic"` fallthrough), a `_HEADINGS` entry, a `WHY` entry, and the new kind added to every `by_kind` enumeration (the summary count line, the `for kind in (...)` render loop, and the terminal summary dict).
  - `plan_tool/cli/inspect.py` — in `_print_status`, after the step list, print a summary line when the plan's record carries unreviewed deferrals, by reusing `check_concept_coverage` and filtering for `CONCEPT_UNSIGNED_DEFERRAL_SOURCE`. Nothing new to `cmd_status`'s signature.
  - `tests/test_review.py` — flip the existing `test_unsigned_concept_is_advisory_only` assertion to the new severity and rename it to reflect "surfaced, non-blocking"; add the new-behavior tests below.

## Implementation

**What changes.** The finding already exists and fires correctly. This step changes only its *disposition and visibility*, on the rule **surface, never block**.

- **Keep the detector single-sourced.** `plan_tool/review.py:check_concept_coverage` stays the only place that decides "this deferral is unreviewed." Every surface that wants to show pending deferrals calls this function and filters on `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` — do **not** re-derive the `review_state != "approved" and decision in {"defer","wont_do"}` predicate in `inspect.py` or `completeness_report.py`. Duplicating it is the side-effect risk here: two copies drift, and a status line that disagrees with the audit is worse than no line.

- **Non-blocking is the invariant that must hold.** An unreviewed deferral is resolved only by an operator decision through `plan-tool scope-review`; `apply_finding` (a prose editor) and the `--iterate` convergence loop cannot approve or reject a concept decision. So the source must **not** enter `plan_tool/review.py:SELF_CONSISTENCY_SOURCES` (which gates at medium+) — it already isn't, and this step keeps it that way. If it became blocking, the audit loop would spin forever on something no automated pass can fix. This matches the project's convergence-blocking rule: block only on real correctness gaps, not on a reminder.

- **Raise it off the silent info floor (review.py).** In `check_concept_coverage`, change the `concept-unsigned-deferral` `Recommendation`'s `severity` from `"info"` to a value that is surfaced but still below the blocking threshold — one way: `"low"`. The point of the title's "instead of info-only" is that the finding should no longer be swept into the same invisible bucket as ordinary info advisories. The real visibility comes from the dedicated surfaces below, so treat the severity choice as latitude, but the finding must not stay `"info"`. While here, make the `body`/`suggested_action` name the concrete remedy (`plan-tool scope-review`) so the surfaced message is actionable rather than just descriptive.

- **Give it a home in the report (completeness_report.py).** Add a `"unsigned-deferral"` disposition:
  - In `deferred_kind`, add `if rec.source == CONCEPT_UNSIGNED_DEFERRAL_SOURCE: return "unsigned-deferral"` **above** the `if not is_apply_eligible(rec): return "diagnostic"` line — otherwise the finding keeps falling through to `"diagnostic"` and the new heading never renders. Import `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` from `plan_tool.review` (the module already imports `Recommendation`/`is_apply_eligible`/`should_apply_by_triage` from there).
  - Add a `_HEADINGS["unsigned-deferral"]` (e.g. "Unsigned concept deferrals — review before relying on them") and a `WHY["unsigned-deferral"]` rationale that names `plan-tool scope-review` as the remedy and states plainly that the audit loop leaves it alone on purpose.
  - Add `"unsigned-deferral"` to **every** place that enumerates the disposition kinds: the `by_kind` dict that feeds the "Deferred: … (…)" summary count line, the `for kind in ("concept-link", "diagnostic", "triage", "info")` render loop (so the section actually prints), and the terminal-summary `by_kind` dict. Missing any one leaves the finding counted in one place and invisible in another.

- **Tolerate a stale record when surfacing (do not raise).** A plan that has deferred keeps a bundle-wide `plan_fingerprint`, so an unrelated prose/detail edit before the operator confirms makes the record stale, and `check_concept_coverage` → `load_concepts` raises `StaleConceptTreeError`. The surfacing path exists precisely to keep a pending deferral visible, so it must **not** propagate that raise: catch `StaleConceptTreeError` in both the `status` line and the completeness-report contribution and still surface the pending deferrals (a stale fingerprint means "re-derive," not "error"), appending a brief "record may be stale — re-run after `scope-review`" note. A stale record raising here would blank the very signal the step guarantees. (`completeness_phases.py:1497` and `_print_status` are the two call sites to guard.)
- **Surface it in status (inspect.py) — with the concept ids, not just a count.** In `_print_status`, after the step-marker loop, compute the pending unreviewed deferrals and, when there are any, print the count line **plus the exact id each one needs** so the surface is actionable, not seen-but-stuck. For example:
  ```
  ⚠ 2 unsigned concept deferral(s) pending review — confirm with:
      plan-tool scope-review <name> --concept concept-<id> defer|wont_do
    · concept-1a2b… — "Rate limiter back-off"
    · concept-9f0e… — "Legacy CSV import"
  ```
  **Print the bare `node.id`, not the anchor.** The finding's `anchor` is `f"concept-{node.id}"`, but `scope-review --concept` matches the **bare `node.id`** (see `scope_review_cmd.py`'s `--concept` parsing) — printing the `concept-`-prefixed anchor gives a token that fails to match, leaving the operator seen-but-stuck. Emit the bare id in the copyable command (a `concept-` label for display is fine, but the token after `--concept` must be the bare id). Confirm the exact token against `scope_review_cmd.py` when wiring this. The remedy offers `defer`/`wont_do` (confirm the deferral), **not `include`**: an `include` decision on a lazy plan produces an `approved` node with no committed owner, which trips a blocking `concept-coverage` finding — so `include`-ing a pending deferral is not a resolution here (deciding a concept should be implemented instead is a re-plan, out of MVP; dismissing a wrong pending deferral is a deferred verb). Recommended shape:
  - Call `check_concept_coverage(plan, path, plan_name=plan.title)` and keep only recs whose `source == CONCEPT_UNSIGNED_DEFERRAL_SOURCE`; render one bullet per finding using its `anchor` (the id) and title.
  - Print nothing when the list is empty (absent record → `check_concept_coverage` returns `[]`, the common case).
  - One way to keep imports clean: do the `from plan_tool.review import check_concept_coverage, CONCEPT_UNSIGNED_DEFERRAL_SOURCE` **inside** `_print_status` (or a small private helper it calls), mirroring how `plan_tool/cli/completeness_phases.py` imports `check_concept_coverage` function-local. A module-top import also works (`review.py` does not import `cli.inspect`, so there is no cycle), but the function-local form matches the sibling precedent and keeps the read-only inspection module's import surface small.

**Alternative rejected.** Making the finding blocking (bump to `medium` and add to `SELF_CONSISTENCY_SOURCES`) was rejected: it reads well as "the operator must act," but the `--iterate`/apply machinery has no path to resolve a concept decision, so a blocking unsigned deferral would stop every audit from ever converging. Surfacing keeps the operator informed without wedging the automated loop.

## Tests

Add these with the implementation. Every new test must be green before this step is done (green-before-done gate).

In `tests/test_review.py`:
- `test_unsigned_concept_deferral_is_surfaced_not_info` — (renamed from `test_unsigned_concept_is_advisory_only`) `check_concept_coverage` on a record with an unreviewed `defer` node returns exactly one `concept-unsigned-deferral` finding whose severity is the new non-info value (e.g. `"low"`), and the source is still **not** in `SELF_CONSISTENCY_SOURCES`.
- `test_unsigned_deferral_body_names_scope_review` — the finding's `body`/`suggested_action` names `plan-tool scope-review` (the actionable remedy).
- `test_signed_deferral_emits_no_unsigned_finding` — an approved deferral node emits no `concept-unsigned-deferral` finding (guards that the predicate is unchanged).

In `tests/test_completeness_report.py` (the sibling test module for `plan_tool/completeness_report.py`):
- `test_unsigned_deferral_gets_dedicated_disposition` — `deferred_kind` returns `"unsigned-deferral"` for a `concept-unsigned-deferral` rec (not `"diagnostic"`).
- `test_report_renders_unsigned_deferral_section` — a report built with an unsigned-deferral finding contains the `_HEADINGS["unsigned-deferral"]` heading and the finding, and the "Deferred" summary count includes it.

In `tests/test_inspect.py` (the sibling test module for `plan_tool/cli/inspect.py`):
- `test_status_surfaces_pending_unsigned_deferrals` — `_print_status` on a plan whose record carries an unreviewed `defer` node prints the pending-review summary line naming `scope-review` **and a bullet containing the bare `node.id`** (the exact token `scope-review --concept` consumes, asserted to match what `scope_review_cmd.py` parses) and its title.
- `test_status_silent_when_no_concept_record` — `_print_status` on a plan with no `concepts.json` prints no deferral line (absent record is normal).
- `test_status_surfaces_pending_on_stale_record` — with a `concepts.json` whose `plan_fingerprint` no longer matches (stale), `_print_status` still surfaces the pending deferral (with a staleness note) and does **not** raise `StaleConceptTreeError`; the same holds for the completeness-report contribution.

## Acceptance criteria

- `check_concept_coverage` on an unreviewed `defer`/`wont_do` node returns one `concept-unsigned-deferral` finding whose severity is not `"info"`.
- `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` is not a member of `plan_tool/review.py:SELF_CONSISTENCY_SOURCES`, and the finding never flips a subcommand exit code.
- `plan_tool/completeness_report.py:deferred_kind` returns `"unsigned-deferral"` for a `concept-unsigned-deferral` rec.
- `_HEADINGS` and `WHY` both have an `"unsigned-deferral"` key, and the report's "Deferred" summary count and section render loop include the new kind.
- `plan-tool status` on a plan with one or more unreviewed deferrals prints the count line **and one bullet per pending deferral naming the bare `node.id`** (the exact token `scope-review --concept` consumes, not the `concept-<id>` anchor) and title; on a plan with no record it prints no such line.
- The `create` run-summary line (owned by step 2) and the completeness report both name that same bare id, so an operator sees the actionable token at authoring time from any of the three surfaces without a separate lookup.
- A **stale** concept record does not make the surfacing raise: `plan-tool status` and the completeness report catch `StaleConceptTreeError` and still surface the pending deferrals (best-effort) with a staleness note, instead of erroring.
- The renamed `test_unsigned_concept_deferral_is_surfaced_not_info` and every new test listed above pass; the full suite stays green.

## References

- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture pattern the new `check_concept_coverage` / `_print_status` / report tests use to stage a plan plus its `concepts.json` record on disk.

## Deferred

- Making the unsigned deferral **blocking** (a medium+ gate) — deliberately out of scope; it cannot be auto-resolved, so blocking would break convergence. Revisit only if `apply_finding` ever gains a concept-decision path.
- Surfacing pending deferrals in the multi-plan `list --status` rollup (`plan_tool/cli/inspect.py:_print_annotation_status_rollup`) — that rollup is annotation-report-based, a different data source; folding concept-deferral state into it is a separate, larger surface change. If wanted, file it in `BACKLOG.md` rather than expanding this step.
- Consolidating the second raw parse of the deferral metadata in `plan_tool/review.py:_structured_concept_deferral_is_valid` onto a shared reader — a pre-existing reconcile-owned follow-up, unrelated to this step's visibility change.
