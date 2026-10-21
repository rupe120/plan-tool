# Step 7 — Surface pending guide posts as a drillable bucket + title + bare-id list in status, the completeness report, and a create run-summary line, non-blocking

## Summary

Show the operator every **pending guide post** (a proposed `defer`/`wont_do` concept that isn't signed off yet) in three read surfaces — `plan-tool status`, the written completeness report, and a `create` run-summary line — each rendering the guide post's **bucket + title + bare `node.id`** plus a copy-paste `plan-tool scope-review` command, so the operator can drill straight to a specific concept and confirm it. The single detector stays `plan_tool/review.py:check_concept_coverage` (from step 6); the only new behavior in `review.py` is that its `concept-unsigned-deferral` recommendation now also names the guide post's `bucket`, because the completeness report renderer only has the recs to work from. The surfaces live in `plan_tool/cli/inspect.py` (`_print_status`), `plan_tool/completeness_report.py` (`build_report_md`), and `plan_tool/create.py` (tail of `create_plan`). Everything here is display-only and **non-blocking** — `concept-unsigned-deferral` stays `info` severity and out of the blocking set, so surfacing a pending guide post never flips an exit code or wedges the `--iterate` loop. On green, `create -y` that proposes a deferral leaves that concept's bare id visible in all three surfaces, and none of the three raises or blocks when a plan was edited after the deferral was recorded (step 6 made the detector crash-safe).

## Table of Contents

- [Why](#why) — what's missing today and why the operator can't act on a pending deferral
- [Input](#input) — the detector, the guide-post fields, and the report renderer this consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the files this step touches, including two additions
- [Implementation](#implementation) — the rec enrichment and the three render surfaces
- [Tests](#tests) — unit cases added with the code
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse, dataclasses
- [Deferred](#deferred) — what this step leaves to later steps or the backlog

## Why

Step 4 makes `create` record proposed deferrals as pending guide posts, and step 6 makes `check_concept_coverage` account for them and never crash on a stale bucket. But nothing yet **shows** the operator that a pending guide post exists or gives them the token they need to confirm it. `plan-tool scope-review` consumes the bare `node.id` (`--concept <id>`), and today that id is buried inside a `concept-unsigned-deferral` finding that only appears — as a generic bullet — in the completeness report's advisory "Smells" dump. `plan-tool status` shows nothing about pending concepts, and a fresh `create -y` that quietly parks a deferral gives the operator no on-screen hint at all. This is design point **E** of the plan: present the pending guide posts as a drillable list (bucket + title + bare id) in `status`, the completeness report, and a `create` run-summary line, so the operator can go from "a deferral is pending" to "run this exact `scope-review` command" without hunting. It must stay non-blocking — only an operator `scope-review` decision resolves a pending guide post, so making it block would wedge the automated `--iterate` convergence loop forever (the same "surface, never block" rule already applied to `concept-unsigned-deferral` in steps 3/6).

## Input

This step consumes three upstream contracts; correctness rests on each staying shaped as expected:

- **Step 6's `plan_tool/review.py:check_concept_coverage`** — the single detector for pending guide posts. It emits one `concept-unsigned-deferral` `Recommendation` per node where `review_state != "approved"` and `decision in {"defer", "wont_do"}`, with `source == CONCEPT_UNSIGNED_DEFERRAL_SOURCE`, `severity == "info"`, `step_id == None`, and `anchor == f"concept-{node.id}"`. After step 6 it never raises on any on-disk record shape or plan-body state, and returns `[]` when no record exists. Every surface in this step reuses this detector and filters on the `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` constant — the predicate (`review_state != "approved" and decision in {defer,wont_do}`) is not re-implemented anywhere.
- **Step 2's guide-post fields on `plan_tool/concept_tree.py:ConceptNode`** — `bucket` (the coarse body-section tag) and `title`. The rec already carries the concept id (via `anchor`) and title (via `body`); the one field it doesn't expose is `bucket`. `bucket` may be empty (`""`) on some records, so rendering must degrade gracefully when it is.
- **The completeness report renderer** — `plan_tool/completeness_report.py:build_report_md` receives the advisory finding set through its existing `smells` parameter (threaded from `plan_tool/cli/completeness_phases.py`, which passes `smells=list(smell_recs)`; `concept-unsigned-deferral` rides `smell_recs` because it is not in `SELF_CONSISTENCY_SOURCES`, so it is not filtered out there). `build_report_md` has the recs but **not** the plan path, so the recs are the only source of the bucket for that surface — this is why the rec must carry the bucket rather than each surface re-loading `concepts.json`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/inspect.py` — in `_print_status`, after the step-marker loop, render the pending-guide-posts bucket (bucket + title + bare id + a `scope-review` command). Function-local import of `check_concept_coverage` / `CONCEPT_UNSIGNED_DEFERRAL_SOURCE`.
  - `plan_tool/completeness_report.py` — in `build_report_md`, split the `concept-unsigned-deferral` recs out of the generic `smells` set into a dedicated drillable section; keep them out of the `## Smells (advisory)` section.
  - `plan_tool/create.py` — at the tail of `create_plan`, before `return CreateResult`, print a non-blocking run-summary line for any pending guide posts on the just-written plan.
  - `plan_tool/review.py` — **added to scope** (its test file `tests/test_review.py` is already listed; the source file was omitted). Enrich `check_concept_coverage`'s `concept-unsigned-deferral` rec so it names the guide post's `bucket` in a render-ready field. No new `Recommendation` field (that would be an out-of-scope persisted-schema change touching `DATA_CONTRACT.md` / `tests/test_data_contract.py`); reuse existing fields. No change to the predicate, `source`, `severity`, `step_id`, or `anchor`.
  - `tests/test_review.py` — cases for the enriched rec.
  - `tests/test_completeness_report.py` — cases for the dedicated report section.
  - `tests/test_create.py` — cases for the run-summary line.
  - `tests/cli/test_inspect_cmds.py` — **added to scope**. The `status` surface (`_print_status`) is exercised here (see the existing `TestCmdStatus`-style cases such as `test_registered_plan_prints_header_and_steps`); the new status line needs a unit test and this is its home.

## Implementation

**Foundational logic of this step:** "render the set of pending guide posts (bucket + title + bare id) as a non-blocking drillable list." The detection is owned by step 6's `check_concept_coverage`; this step is disposition/visibility plumbing over that already-firing detector, fanned out to three surfaces. The risk is fan-out consistency, not detection — so every surface reuses the one detector's output and never re-derives the predicate.

- **Enrich the `concept-unsigned-deferral` rec to name the bucket — `plan_tool/review.py:check_concept_coverage`.** The rec is built while iterating `concept_tree.concepts`, so `node.bucket` is in hand at emit time. Add it to the rec in a field a renderer can show without parsing free prose. One clean way: set the rec `title` to a compact render-ready form like `f"[{node.bucket}] {node.title}"` (falling back to just `node.title` when `bucket` is `""`), and keep the fuller sentence in `body`. The exact field placement is your call; the requirement is that the rec exposes **bucket + title + bare id** in fields the three surfaces read directly.
  - **Do not change** `source`, `severity` (`"info"`), `step_id` (`None`), or `anchor` (`f"concept-{node.id}"`). `anchor` is the single stable source of the bare id — surfaces recover it by stripping the `concept-` prefix. The rec `id` is content-addressed from `node.id` (`_make_rec_id(None, CONCEPT_UNSIGNED_DEFERRAL_SOURCE, node.id)`), not the title, so a title change does not move the id.
  - **Why the rec, not a per-surface re-load:** the completeness report renderer (`build_report_md`) has the recs but not the plan path, so it cannot look up `node.bucket` itself. Making the rec the single carrier lets all three surfaces render identically off one source.
- **Status surface — `plan_tool/cli/inspect.py:_print_status`.** After the `for s in plan.steps:` marker loop, call `check_concept_coverage(plan, path, plan_name=<derived>)`, filter recs to `source == CONCEPT_UNSIGNED_DEFERRAL_SOURCE`, and when non-empty print a small drillable bucket: a header line naming the count, one line per pending post (its bucket + title + bare id), and a ready-to-run `plan-tool scope-review <name> --concept <id> [--concept <id> …]` line built from the bare ids. Import `check_concept_coverage` / `CONCEPT_UNSIGNED_DEFERRAL_SOURCE` function-local (matches the sibling precedent in `plan_tool/cli/completeness_phases.py` and keeps the read-only inspection module's import surface small). `_print_status` returns `None` and `cmd_status` already always exits 0 — do not change that; the line is advisory.
  - `plan_name` for the detector call can be derived cheaply from `path` (e.g. its stem) — it only affects finding text, not detection.
- **Completeness-report surface — `plan_tool/completeness_report.py:build_report_md`.** Split the incoming `smells` list into the pending guide posts (`source == CONCEPT_UNSIGNED_DEFERRAL_SOURCE`) and the rest. Render a **dedicated** section for the pending guide posts — a drillable heading, a one-line-per-post list (bucket + title + bare id), and the `plan-tool scope-review` command — and render the existing `## Smells (advisory)` section from the **rest only**, so a pending guide post appears once, in its own section, not buried among brittle-ref/granularity smells. Use the existing `smells` parameter; **do not** change `build_report_md`'s signature, because its caller lives in `plan_tool/cli/completeness_phases.py`, which is out of this step's scope. Keep the section non-blocking and out of the disposition-count math (it is advisory, like the smells it came from).
- **Create run-summary surface — `plan_tool/create.py`, tail of `create_plan`.** After the plan and its guide-post `concepts.json` are on disk (step 4's deferral-only gate) and before `return CreateResult(...)`, call `check_concept_coverage(parse_plan(plan_path), plan_path, plan_name=slug)`, filter on the source constant, and when non-empty print a non-blocking run-summary line naming the pending guide posts (bucket + title + bare id) and the `scope-review` command. Place it near the existing closing hints (the block that already suggests `plan-tool detail {slug}` / `plan-tool status {slug}`). Only the main success tail needs it — the early-return paths (collision/error, e.g. the `return CreateResult(...)` near the manifest-collision guard) write no guide posts and need no line. Re-parse the plan from disk for this read: by the tail of `create_plan`, the top-of-run parse is stale (the authoring/iterate loop round-tripped the file).
- **Shared shape across the three surfaces.** Keep the rendered line format the same across all three (bucket + title + bare id + the `scope-review` command) so the operator sees one consistent presentation. A tiny shared render helper is fine if it stays within these files; do not add a new cross-module module for it.

**Constraints that must hold:**

- **Non-blocking everywhere.** No surface may flip an exit code or add `concept-unsigned-deferral` to any blocking set. It stays `info` and out of `SELF_CONSISTENCY_SOURCES`. The `--iterate` completeness loop must still converge with a pending guide post present.
- **Single detector, single predicate.** Every surface calls `check_concept_coverage` and filters on `CONCEPT_UNSIGNED_DEFERRAL_SOURCE`. Do not re-implement `review_state != "approved" and decision in {defer,wont_do}` in any surface.
- **Bare id via `anchor`.** Recover the bare `node.id` by stripping `concept-` from `rec.anchor`; do not parse it out of prose.
- **Degrade when `bucket` is empty.** Render title-only (no empty `[]`) when `node.bucket == ""`.

## Tests

Every new test must be green before this step is done (feature step: tests added with the implementation).

`tests/test_review.py` (uses `_write_concept_coverage_fixture`, extended to set a `bucket`):
- `test_unsigned_deferral_rec_names_bucket` — a pending (`review_state="unreviewed"`, `decision="defer"`) node with a non-empty `bucket` yields a `concept-unsigned-deferral` rec whose render field contains the bucket and the concept title, with `anchor == f"concept-{node.id}"`.
- `test_unsigned_deferral_rec_degrades_when_bucket_empty` — same node with `bucket == ""` renders the title with no empty bracket artifact.
- `test_unsigned_concept_is_advisory_only` — keep green: `source`/`severity` stay `("concept-unsigned-deferral", "info")` and the source stays out of `SELF_CONSISTENCY_SOURCES`.

`tests/test_completeness_report.py`:
- `test_report_renders_pending_guide_posts_section` — `build_report_md` with a `concept-unsigned-deferral` rec in `smells` renders a dedicated pending-guide-posts section carrying the bucket, title, bare id, and a `plan-tool scope-review` command.
- `test_pending_guide_posts_excluded_from_generic_smells` — that rec does **not** appear under `## Smells (advisory)`; a non-concept smell still renders there.
- `test_report_omits_pending_section_when_no_pending` — no `concept-unsigned-deferral` recs → no pending section.

`tests/test_create.py`:
- `test_create_y_deferral_prints_pending_guide_post_summary_line` — `create -y` that records a pending guide post prints a run-summary line containing the bare `node.id` and the `scope-review` command.
- `test_create_without_deferral_prints_no_pending_line` — a plain create (no deferral, no `concepts.json`) prints no pending line and raises nothing.

`tests/cli/test_inspect_cmds.py`:
- `test_status_lists_pending_guide_posts_with_bare_ids` — `status` on a plan with a pending guide post prints the bucket + title + bare id and the `scope-review` command; exits 0.
- `test_status_no_pending_line_when_record_absent` — `status` on a plan with no `concepts.json` prints no pending line and exits 0.

## Acceptance criteria

- `check_concept_coverage`'s `concept-unsigned-deferral` rec exposes the guide post's `bucket` alongside its title, with `anchor == f"concept-{node.id}"`, `source == "concept-unsigned-deferral"`, and `severity == "info"` unchanged.
- `plan-tool status` on a plan carrying a pending guide post prints a bucket + title + bare-id line and a runnable `plan-tool scope-review <name> --concept <id> …` command, and exits 0.
- `build_report_md` renders pending guide posts in their own dedicated section (bucket + title + bare-id list + `scope-review` command) and does **not** list them under `## Smells (advisory)`.
- `create -y` that records a pending guide post prints a run-summary line containing the bare `node.id`; a create with no deferral prints no such line.
- All three surfaces raise nothing when the plan was edited after the deferral was recorded (they inherit step 6's crash-safe detector), and none flips an exit code.
- The new unit tests in `tests/test_review.py`, `tests/test_completeness_report.py`, `tests/test_create.py`, and `tests/cli/test_inspect_cmds.py` pass; `test_unsigned_concept_is_advisory_only` stays green.

## References

- [argparse — Parser for command-line options (Python docs)](https://docs.python.org/3/library/argparse.html) — the `status` subparser and how `_print_status` is reached; relevant to the status surface.
- [dataclasses — Data Classes (Python docs)](https://docs.python.org/3/library/dataclasses.html) — `Recommendation` is a dataclass; reference for reusing existing fields rather than adding one (which would trip the drift guard).

## Deferred

- A per-item source-`bucket` display in the terminal `console_summary` completeness line — adding it needs a new parameter on `console_summary` whose caller lives in `plan_tool/cli/completeness_phases.py` (out of this step's scope). The written report (`build_report_md`) is the completeness-report surface this step delivers; a terminal-summary line is a follow-up if wanted.
- A dismiss/remove verb for a wrong pending guide post — plan-level out-of-scope (a wrong pending guide post is inert until confirmed).
- Consolidating the shared render helper into one cross-module home if a fourth surface ever needs it — a reconcile-owned refactor, not needed for three in-file callers.
