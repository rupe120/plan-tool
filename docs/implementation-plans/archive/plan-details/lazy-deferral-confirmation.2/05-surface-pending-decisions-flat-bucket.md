> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Surface pending concept decisions as a flat, bucket-grouped, non-blocking list in status, the completeness report, and a create run-summary line

## Summary

Show the operator the concept deferrals that still need a human decision — in three read-only surfaces — without ever blocking a run. Filter `plan_tool/review.py:check_concept_coverage`'s output down to its **pending-decision** sources (`concept-unsigned-deferral`, step 3's `concept-bucket-missing`, and step 3's stale-legacy `concept-legacy-stale` advisory), group them into named groups, and render that flat list in `plan_tool/cli/inspect.py:_print_status`, the completeness report markdown (`plan_tool/completeness_report.py:build_report_md`), and a one-line advisory printed at the end of `plan_tool/create.py:create_plan`. The key design decision is that all three surfaces reuse the one detector and a single shared `PENDING_DECISION_SOURCES` filter defined in `completeness_report.py` — no surface re-implements the predicate, and none of this touches `plan_tool/review.py`. On green: `plan-tool status <name>` prints a pending-decisions summary, the completeness report grows a dedicated pending section instead of burying these findings under `## Smells (advisory)`, and a `create` that recorded deferrals ends with a line pointing at `plan-tool scope-review`.

## Table of Contents

- [Why](#why) — pending deferrals are produced but never shown to the operator
- [Input](#input) — the finding sources this step reads from steps 2/3
- [Files (creates vs edits)](#files-creates-vs-edits) — three code files, three test files
- [Implementation](#implementation) — one shared filter, three surfaces, no review.py edit
- [Tests](#tests) — status line, report section split, create summary line
- [Acceptance criteria](#acceptance-criteria) — observable behaviors on green
- [References](#references) — argparse / dataclasses docs for the surfaces
- [Deferred](#deferred) — the terminal `console_summary` line and the sidecar JSON grouping

## Why

The lazy model records a deferral and confirms it *later*, so between record and confirm the operator needs a standing reminder of what is waiting. Today `check_concept_coverage` already emits a `concept-unsigned-deferral` finding per unreviewed `defer`/`wont_do` node (see `plan_tool/review.py:check_concept_coverage`), and step 3 adds a `concept-bucket-missing` finding for a confirmed decision whose section was deleted. But nothing shows either to a person at the moment they'd act. The findings ride the advisory `smell_recs` bucket into the completeness audit (`plan_tool/review.py:collect_smell_findings` calls `check_concept_coverage`), where they render as generic, ungrouped smell lines — and `status` and `create` never surface them at all. This step fans those pending decisions into a clear, grouped, non-blocking list on the three surfaces a user actually reads, so a parked decision can't silently sit forever.

## Input

This step reads two sibling steps' outcomes; depend on the outcome, not the mechanism.

- **The pending-decision detector — steps 2/3.** `plan_tool/review.py:check_concept_coverage` is the single detector. It returns `Recommendation`s whose `source` is one of **three** constants: `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` (`"concept-unsigned-deferral"`, exists at HEAD) and, after step 3, `CONCEPT_BUCKET_MISSING_SOURCE` (`"concept-bucket-missing"`) and `CONCEPT_LEGACY_STALE_SOURCE` (`"concept-legacy-stale"`, the stale-legacy re-sync advisory). All three are `severity="info"`, `step_id=None`, and kept **out** of `SELF_CONSISTENCY_SOURCES` (never blocking). The first two carry a per-node `anchor=f"concept-{node.id}"`; the legacy-stale advisory is **record-wide** — its `anchor` is the literal `"concept-legacy-stale"` and it has no `node.id`, so the "strip `concept-` to get the bare id" and section-bucket grouping do **not** apply to it (step 5's surfaces fold it in via `PENDING_DECISION_SOURCES` but render it as a plain re-sync line). Read those three source constants; do not restate step 3's detector logic.
- **The decision-record shape — step 1.** The nodes these findings describe are flat `record_kind="decision-record"` nodes (a coarse `bucket` string, a `defer`/`wont_do` decision, `review_state`). The **completeness-report and `create` surfaces** never load `concepts.json` — they render purely from the finding set the detector produced (`build_report_md` has no path). The **`status` surface is the exception**: it holds `path` and *does* load the record (a guarded `load_concepts`, see Implementation) to group by section `bucket` and render the lazy-context excerpt — the finding anchor alone doesn't carry the bucket string. So "no disk load" is a report/create invariant, not a status one.
- **Absent/malformed record is inert; a stale legacy record surfaces one advisory.** After step 3 `check_concept_coverage` is total: an absent or malformed record yields `[]`, and a stale legacy full-tree record yields exactly one non-blocking `concept-legacy-stale` re-sync advisory (not `[]`, so a drifted legacy record is not silently hidden). So every surface here is safe to call it unconditionally and gets an empty list (nothing to show) in the common lazy case, or at most the single re-sync line for a drifted legacy record.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — add a `PENDING_DECISION_SOURCES` constant (the three source tokens, imported from `plan_tool.review`) plus a small `group_pending_decisions(recs)` helper that returns the pending-decision groups in a fixed order; in `build_report_md`, split those sources out of the `smells` list into a dedicated `## Pending concept decisions` section and add a count line to the disposition summary.
  - `plan_tool/cli/inspect.py` — in `_print_status`, after the step-marker loop, call `check_concept_coverage` and render the grouped pending-decisions summary (function-local import).
  - `plan_tool/create.py` — near the end of `create_plan` (after the concept-persistence block that writes `concepts.json`), print one advisory run-summary line naming the pending-deferral count and the `plan-tool scope-review` command.
  - `tests/cli/test_inspect_cmds.py` — status-surface cases.
  - `tests/test_completeness_report.py` — report split/grouping cases.
  - `tests/test_create.py` — create run-summary line cases.

## Implementation

**Foundational logic:** filter `check_concept_coverage`'s pending-decision findings by source, group them into two named buckets, and render that flat list non-blocking across three read-only surfaces — reusing the one detector, never re-deriving the predicate.

**Define the filter and grouping once, in `completeness_report.py`.** This is the anti-drift move. `completeness_report.py` already imports names from `plan_tool.review` (`Recommendation`, `is_apply_eligible`, `should_apply_by_triage`), so pull the three source constants in beside them:

- `PENDING_DECISION_SOURCES` — a `frozenset` of `CONCEPT_UNSIGNED_DEFERRAL_SOURCE`, `CONCEPT_BUCKET_MISSING_SOURCE`, **and `CONCEPT_LEGACY_STALE_SOURCE`** (step 3's stale-legacy re-sync advisory). Include the legacy-stale source so its "needs re-sync" remediation prompt reaches the operator on `status` and in the report's dedicated `## Pending concept decisions` section — otherwise it is filtered into the generic `## Smells (advisory)` bucket and effectively buried (`[legacy-stale-resync-surfacing]`). `group_pending_decisions` renders it under its own "legacy record — needs re-sync" group (distinct from the flat bucket groups and the empty-`bucket` legacy-pending group). Key on the constants, not the string literals, so a later rename can't silently break the filter.
- `group_pending_decisions(recs)` — take any `Recommendation` list, keep only the three pending sources, and return them split into ordered groups (recommend a small dataclass or an ordered `dict[source, list]`; unsigned-deferrals first, then missing-bucket re-reviews, then the legacy-stale re-sync advisory). Every group carries a short human label and the shared resolver hint (`plan-tool scope-review <name>`). Keep the helper pure — it takes a rec list and returns groups, no disk access — so all three surfaces feed it the same way.

The three groups, all **non-blocking**:
- **Unsigned deferrals** (`concept-unsigned-deferral`) — a proposed `defer`/`wont_do` not yet reviewed. Resolve with `plan-tool scope-review`.
- **Missing-bucket re-reviews** (`concept-bucket-missing`) — a decision whose section was renamed/deleted. Resolve with `plan-tool scope-review`.
- **Legacy record — needs re-sync** (`concept-legacy-stale`) — a drifted legacy full-tree record whose coverage can't be re-checked until it is re-synced. This one is **record-wide** (no `node.id`/bucket), so it renders as a single plain re-sync line, not a per-node entry. Resolve with `plan-tool scope-review`.

**Status surface — `plan_tool/cli/inspect.py:_print_status`.** `_print_status(plan, path)` holds both the parsed plan and its path, so it can call the detector directly. After the step-marker loop:
- Import function-local: `from plan_tool.review import check_concept_coverage` (matches the sibling precedent in `plan_tool/cli/completeness_phases.py`, which imports the detector function-local, and keeps this read-only inspection module's top-level import surface small).
- Call `check_concept_coverage(plan, path, plan_name=slug_from_filename(path.name))` — `slug_from_filename` is already imported in `inspect.py`. `_print_status` also holds `path`, so it loads the record to read each pending node's `bucket`/`id`. **Guard this load against `StaleConceptTreeError` / `InvalidConceptTreeError`** exactly as step 3 does (a *stale legacy* full-tree record still raises — step 1 skips the guard only for the flat kind — so an unguarded second load here would crash `status`, re-introducing the very crash step 3's totality prevents and violating the plan's "no `StaleConceptTreeError` on any read/confirm path" criterion). On a load failure, fall back to rendering the findings' bare ids without bucket grouping (the finding list from `check_concept_coverage` is already stale-tolerant per step 3). Print a compact block **grouped by section `bucket`** (the flat MVP's navigation — Architecture E), and under each bucket **one line per pending decision naming its bare `node.id`** (the exact token `scope-review --concept` consumes — the anchor with `concept-` stripped, or `node.id`) and its title, plus the `plan-tool scope-review <name> --concept <id> defer|wont_do` hint. Print nothing when there are no pending decisions (the common case).
- **Legacy full-tree pending nodes group separately.** `check_concept_coverage` also emits `concept-unsigned-deferral` for a **legacy full-tree** record's unreviewed defer nodes (a supported carried-in/dual-mode source), and those nodes carry **no `bucket`** (`ConceptNode.bucket` defaults `""` — step 1). Do **not** group an empty-bucket legacy node under "section no longer exists" (which would falsely brand a valid legacy deferral as missing) — render legacy (empty-`bucket`) pending nodes under their own group heading (e.g. "legacy record — run `scope-review` to confirm"), distinct from the flat section-bucket groups. Only a *flat* node whose non-empty bucket no longer resolves gets the missing-section note.
- **Lazy context — the bucket's section excerpt (Architecture G).** Under each **flat, still-resolving** bucket group, render a **short excerpt of that bucket's current body-section text**, read on demand from the plan (`parse_body_sections(split_plan_document(path.read_text()).body)`, keyed on the same normalized `BodySection.name` the bucket tag uses), so the operator sees *what the deferral relates to* without a stored concept catalog; truncate to a few lines / N chars. Three groups have **no excerpt** and each shows a defined note instead: a **missing-bucket** group (flat node whose non-empty bucket no longer names a section — step 3's `concept-bucket-missing`) shows `"section no longer exists — re-review: scope-review … wont_do (or defer)"` (this is the record that most needs a clear next-step, so name the remedy, not just the absence); a **legacy** group (empty-`bucket` full-tree node) shows `"legacy record — confirm via scope-review"`; and the missing/legacy groups never attempt a section read. This is the flat MVP's contextualization; it deliberately does **not** derive sub-concepts (BACKLOG #130). Display-only, no Claude, no disk write beyond the record read.
- **Constraint:** `status` spends no Claude and never changes its exit code; this is display only. The `check_concept_coverage` *finding* call is stale-tolerant (step 3), but the **separate `load_concepts` for bucket/id reading is not** unless guarded — so wrap it (above); `status` must never raise on a stale legacy record.

**Report surface — `plan_tool/completeness_report.py:build_report_md`.** These findings already arrive in `build_report_md` via its `smells` parameter (the caller in `completeness_phases.py` passes `smells=list(smell_recs)`, and `smell_recs` includes the pending sources because `collect_smell_findings` folds in `check_concept_coverage` and `_self_consistency_from_smells` only partitions off `SELF_CONSISTENCY_SOURCES`). So the report needs **no signature change** — do the split inside the function:
- Before the `## Smells (advisory)` loop, split `smells` into pending-decision recs (via `group_pending_decisions`) and the rest. Render the rest under `## Smells (advisory)` exactly as today; render the pending recs under a new `## Pending concept decisions` section. Group by pending **kind** (unsigned, missing-bucket, and legacy-stale) here — `build_report_md` has only the recs, not disk access, so it cannot group by section-bucket (the status surface is the bucket-grouped navigation; see the plan's Architecture E note). Render each rec with its **bare `node.id`** — derive it from the `anchor` by stripping the `concept-` prefix (the anchor is `concept-{node.id}`) so the operator sees the exact `scope-review --concept` token, not the anchor form.
- **Constraint — render once, not twice.** The pending recs must be pulled *out* of the list that feeds `## Smells (advisory)`, or they render in both sections. This mirrors how the module already keeps concept findings from double-listing.
- Add one count line to the `## Disposition summary` block (e.g. `- **Pending concept decisions (advisory, not blocking):** N`) so the headline summary names them.
- **Constraint — `build_report_md` has no plan path or disk access.** It renders purely from the finding sets passed in. Everything it shows must come off the recs it already holds; do not try to load `concepts.json` here. That's why grouping keys on `rec.source`, which the recs already carry.

**Create surface — `plan_tool/create.py:create_plan`.** Add the run-summary line near the end of `create_plan`, **after** the concept-persistence block (the `if budget.enabled and signed_concept_scope: … elif budget.enabled:` arms that write `concepts.json`) and before `return CreateResult(...)`:
- `create_plan` already imports from `plan_tool.review`; add `check_concept_coverage` to that import (or import it function-local). Parse the written plan (`parse_plan(plan_path)` is already done in that tail) and call `check_concept_coverage(plan, plan_path, plan_name=slug)`, filter through `group_pending_decisions`, and if there are any pending decisions print one advisory line that **names each pending decision's bare `node.id`** (the `--concept` token — derive it from the rec anchor by stripping `concept-`, or read the loaded record) — not just a count — plus `plan-tool scope-review <slug> --concept <id> defer|wont_do`.
- **Constraint — one line, non-blocking, plan-tool-only.** This is the "run-summary line", not a full block; keep it to a single advisory line. It must not change `create`'s exit code. The resolver command is `plan-tool scope-review`, which satisfies the CLAUDE.md rule that tool next-step hints only ever name `plan-tool …` commands.
- At create time only `concept-unsigned-deferral` can fire (buckets are freshly derived from the current body, so none is missing); still route through the shared helper so the line stays correct if that ever changes.
- **Note on the operator "Next steps:" block.** The styled `Next steps:` block a user sees after create is printed by `plan_tool/cli/authoring.py:cmd_create`, which is **not** in this step's files. This step adds its line inside `create_plan` itself (in scope) rather than widening `cmd_create`.

**No `plan_tool/review.py` edit.** The detector and its three source constants are owned by steps 2/3. This step only reads their output. If a future need arises to carry the section `bucket` string onto the finding for per-section grouping, that enriches the detector in `review.py` and is out of this step's scope (see Deferred).

## Tests

### Test-creation order (feature step)

This is a **feature** step. Add each unit test alongside the surface it covers; every new test must be green before the step is done.

`tests/cli/test_inspect_cmds.py` (drive through `main(["status", …])` against a temp repo; write a `decision-record` `concepts.json` fixture with an unreviewed `defer` node, or patch `plan_tool.review.check_concept_coverage` to return canned pending recs):
- `test_status_lists_unsigned_pending_deferral` — a status run with one unreviewed deferral prints the pending-decisions summary naming the count and `plan-tool scope-review`.
- `test_status_lists_missing_bucket_rereview` — a `concept-bucket-missing` finding renders under the re-review bucket.
- `test_status_no_pending_prints_nothing` — a plan with no pending findings (or no record) prints no pending block and exits 0.
- `test_status_shows_bucket_section_context` — under a bucket group, `_print_status` renders a short excerpt of that bucket's current body-section text (read via `parse_body_sections`), truncated; a pending decision whose bucket section was deleted shows the "section no longer exists" note instead of raising (Architecture G / lazy context).
- `test_status_no_crash_on_stale_legacy_record` — `_print_status` on a plan with a **stale legacy full-tree** `concepts.json` (fingerprint drifted) renders without raising `StaleConceptTreeError` (the guarded second load), falling back to id-only rendering.
- `test_status_legacy_pending_groups_separately` — a legacy full-tree unreviewed `defer` node (empty `bucket`) renders under the distinct "legacy record" group, **not** under a "section no longer exists" missing-bucket note.

`tests/test_completeness_report.py` (build recs with the existing `_rec(rec_id, source, …)` helper):
- `test_report_splits_pending_decisions_into_own_section` — `build_report_md` with a `concept-unsigned-deferral` rec in `smells` renders a `## Pending concept decisions` section.
- `test_pending_decisions_not_double_rendered_under_smells` — the same rec does **not** also appear under `## Smells (advisory)`; a genuine smell rec still does.
- `test_pending_decisions_grouped_by_bucket` — unsigned and missing-bucket recs render under their two distinct labels.
- `test_disposition_summary_counts_pending_decisions` — the disposition summary reports the pending count.
- `test_group_pending_decisions_filters_by_source` — `group_pending_decisions` keeps only the three pending sources and drops others.

`tests/test_create.py` (inject fakes as the suite already does):
- `test_create_prints_pending_deferral_summary_line` — a create that recorded an unreviewed deferral ends with the advisory line naming the count and `plan-tool scope-review <slug>`.
- `test_create_no_deferral_prints_no_pending_line` — an ordinary create (no record) prints no pending line and the create still succeeds.

## Acceptance criteria

- `plan-tool status <name>` on a plan with one unreviewed decision-record deferral prints a pending-decisions summary line naming the count and `plan-tool scope-review`, and exits 0.
- `plan-tool status <name>` on a plan with no pending findings prints no pending block and exits 0.
- `build_report_md` given a `concept-unsigned-deferral` rec in `smells` renders a `## Pending concept decisions` section and does **not** list that rec under `## Smells (advisory)`.
- `build_report_md` groups `concept-unsigned-deferral` and `concept-bucket-missing` recs under two distinct bucket labels, and the disposition summary reports their combined count.
- `group_pending_decisions` returns only recs whose `source` is in `PENDING_DECISION_SOURCES` (unsigned-deferral, bucket-missing, legacy-stale), split into ordered groups; a `concept-legacy-stale` advisory is surfaced (in `status` and the report's pending section), not buried in generic smells (add a test asserting it appears).
- `create_plan` prints exactly one advisory run-summary line (naming the count and `plan-tool scope-review <slug>`) when it recorded an unreviewed deferral, and prints none otherwise; neither path changes `create`'s exit code.
- No edit to `plan_tool/review.py`; `PENDING_DECISION_SOURCES` and `group_pending_decisions` are defined in `plan_tool/completeness_report.py`.
- All new tests above pass: `uv run pytest tests/cli/test_inspect_cmds.py tests/test_completeness_report.py tests/test_create.py -q`.

## References

- [argparse — Parser for command-line options (Python 3.13)](https://docs.python.org/3/library/argparse.html) — for the `status` / `create` command surfaces whose handlers print the new lines.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — for the small grouping container `group_pending_decisions` may return.
- [pytest — full documentation](https://docs.pytest.org/en/stable/) — for authoring the status, report-split, and create-summary cases.

## Deferred

- **Per-section (`bucket`) grouping.** This step groups by the two finding sources (the two decision kinds), not by each node's `bucket` section string, because the section name isn't carried on the finding and `build_report_md` can't reach `concepts.json` to look it up. Carrying the `bucket` onto the finding would edit `plan_tool/review.py:check_concept_coverage` (out of this step's files) — route to reconcile/BACKLOG if per-section grouping is wanted later.
- **Terminal `console_summary` pending line.** `plan_tool/completeness_report.py:console_summary` doesn't receive `smells`, and wiring a pending count into it means changing its call site in `plan_tool/cli/completeness_phases.py` (not in this step's files). This step surfaces the pending list in the durable markdown report (`build_report_md`); the terminal digest line is left for a step that includes `completeness_phases.py`.
- **Sidecar JSON grouping.** The saved report JSON keeps these recs under its existing `smells` array (owned by `completeness_phases.py`); this step's split is markdown-only. Re-keying the JSON is out of scope.
