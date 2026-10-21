> **Replaced**: this file has been superseded by `docs/implementation-plans/2-deferred-scan-digest.md`.
> Preserved here for history; do not edit.

## Overview

Add a read-only CLI command, `plan-tool deferred`, that sweeps every plan the tool can see (live and archived), harvests work that authors and the tool consciously parked, dedups it against the backlog files, classifies each remaining item `direct` (apply now) vs `plan-tool` (author a plan first), and prints a triage digest to stdout. It is strictly read-only: no plans, reports, or concept records are mutated and no files are written. A completed digest exits 0 regardless of how many items it surfaces. This is Plan A of a two-plan split — selection and promotion live in Plan B (`deferred-select-promote.md`), which builds on the `DeferredItem` model and the `plan-tool deferred` command this plan ships. It supersedes the read-only design in `plan-seeds/deferred-findings-digest.md` (this plan's final docs step retires that seed) and adds one harvest source over it: concept-deferral records.

## Problem statement

When a plan ships, the author and the tool routinely name work that was not done, in high-signal places: plan-body `## Out of scope` / `## Deferred` sections (`- **Title** — rationale` bullets in every plan `.md`, live and archived); completeness/reconcile report JSON under `docs/implementation-plans/plan-details/<slug>/reports/*.json` (the `open_deferred` bucket plus any `recommendations[]` entry whose `annotations[id].status == "skip"`); and concept-deferral records in `plan-details/<slug>/concepts.json` — flat `decision-record` nodes tagged `defer` / `wont_do`, the tool's own deferral ledger. The backlog files (`BACKLOG.md`, `BUG_BACKLOG.md`) are the canonical sink, and good entries cite their origin (`Origin: Deferred from <plan>.md`), but moving a deferral into the backlog is a manual, easily-skipped step. The completeness walk routes findings at emit time, so the live gap is the retrospective remainder in already-shipped plans where routing was skipped, plus archived plans the manifest no longer lists, plus confirmed concept deferrals. Nothing surveys that remainder today; the only way to find it is to read every plan.

## Architecture

One module plus a thin CLI seam. `plan_tool/deferred_digest.py` (orchestrator leaf): harvest → dedup → classify → render — pure logic plus an injectable `invoker=` for the single optional Claude classification call (per the invoker-seam rule, defaulting to the real shell-out and stubbed in tests). Keep it a leaf below the CLI; lazy-import report/concept parsing if it would close an import cycle. `plan_tool/cli/deferred_cmd.py` (thin handler, registered in `parser.py`, added to the CLI reference) ships the read-only command only, with no mutation flags.

Harvest runs three collectors, each yielding a `DeferredItem` dataclass: `title`, `summary`, `source_kind` (`plan-deferred | plan-out-of-scope | report-deferred | concept-deferral`), `source_path`, `archived: bool`, `origin_slug`, and any `severity` / `impact` / `complexity` carried from a report finding, plus (for concept records) `node_id`, `bucket`, and reviewed/pending state. The plan-body collector parses `## Out of scope` and `## Deferred` H2 blocks from every plan `.md`, splitting `- **Title** — body` bullets. The report-JSON collector reads each `reports/*.json`, emitting the `open_deferred` bucket and any `status == "skip"` recommendation, carrying severity/triage so the classifier has signal. The concept-deferral collector reads each `concepts.json`, emitting confirmed and pending `defer` / `wont_do` decision-record nodes and tagging pending ones so the digest shows they are not yet `scope-review`-signed; it only reads the records and never re-opens or mutates them (that is `scope-review`'s job).

Enumerate live AND archived plans: live via `locator.load_manifest_plan_paths(repo_root)`; archived by globbing `docs/implementation-plans/**/archive/**/*.md` (archived plans are deliberately absent from `.plan-tool/plans.json`, so a manifest-only sweep silently misses them). Mark `archived=True`; an archived source does not mean the deferral is moot — surface it, sorted below live sources.

Dedup against the backlog: build the already-triaged set from `BACKLOG.md` + `BUG_BACKLOG.md` (every entry title plus every `Origin:` backlink) and drop any item matching by origin-slug (exact) or normalized-title (fuzzy), so convergent re-runs trend toward the untriaged remainder.

Classify direct vs. plan by reusing BACKLOG.md's closed vocabulary — `direct`, `plan-tool`, or `direct unless <condition>` — applying its [Direct implementation vs. plan-tool plan] heuristic verbatim, so a digest line can be pasted straight into a backlog entry (and consumed by Plan B's promoter). A deterministic pre-score (no Claude) counts files/symbols named in the bullet, detects multi-module / multi-phase language ("first … then …", "open question", "design choice"), and reads any `complexity`/`impact` from a report finding: single-file + obvious criteria + no open decision leans `direct`; multi-module / open decision / 2+ phases leans `plan-tool`. An optional Claude refinement (`--classify`, default ON; `--no-classify` skips) makes one batched call that crisps each bullet into a one-line concept and confirms or overrides the pre-scored tag; on disagreement take the more cautious `plan-tool`, and `--no-classify` runs the whole sweep with zero Claude.

Output a digest to stdout, grouped by Approach (`direct` first), then live before archived. Assign each surfaced item a short stable id (`d1`, `d2`, … — Plan B consumes these as selection tokens). Each line carries the one-line summary, provenance (source path + kind + archived flag), and the tag. Preserve the exit-code convention: a completed digest exits 0 regardless of how many items it surfaces (no `--fail-on-findings`, deferred to Plan B/later).

Open question — subcommand vs. flag: this assumes a standalone `plan-tool deferred`, but the report-JSON collector and dedup logic lean on plumbing `completeness` already owns, so it could ship as `completeness --deferred-digest`. Lean standalone (Plan B's select/promote phases make it clearly its own verb); resolve during `create`/`detail`.

## Out of scope

- **Selection and promotion.** No `--select`, no `--apply`, no writing backlog entries or seed files — that is Plan B (`deferred-select-promote.md`).
- **Mutating any source.** Read-only over plans, reports, and concept records.
- **A new code audit.** This aggregates deferrals already recorded; it adds no new audit of the code.
- **Scope-guard `steps: []` stubs** as a harvest source (low-signal) and `--fail-on-findings` — both deferred.

## Risks

- **Dedup misses → re-listing triaged work.** Mitigation: dedup on the `Origin:` backlink first (exact), fall back to normalized-title.
- **Classifier over-tags `direct`.** Mitigation: on pre-score/Claude disagreement take the cautious `plan-tool`.
- **Import-cycle pressure.** Mitigation: keep `deferred_digest.py` a leaf below the CLI; lazy-import report/concept parsing if it would close a cycle.

## Testing

Follow the project's unit-first convention: default to unit tests exercising one function or class in isolation (`plan_tool/deferred_digest.py` → `tests/test_deferred_digest.py`), covering each of the three collectors (plan-body `## Out of scope` / `## Deferred` parsing, report-JSON `open_deferred` + `status: skip` extraction, `concepts.json` `defer`/`wont_do` decision-record reads), the live-plus-archived enumeration, backlog dedup by `Origin:` backlink and normalized-title, and the deterministic pre-score classifier. Use the `invoker=` seam to stub the optional Claude classification call so no real `claude` is spawned (per `tests/conftest.py`'s autouse gate); assert `--no-classify` runs with zero backend calls. Add an `@pytest.mark.integration` test only for driving the `plan-tool deferred` CLI entry point end-to-end (harvest → dedup → classify → render, exit 0). Verify the read-only invariant by asserting no plan, report, or concept file is mutated across a sweep, and that `deferred_digest.py` introduces no import cycle.

## Acceptance criteria

- `plan-tool deferred` harvests `## Out of scope` / `## Deferred` plan-body sections, report-JSON deferrals (`open_deferred` + `status: skip`), and `concepts.json` `defer`/`wont_do` decision records across both live (manifest) and archived (`**/archive/**`) plans.
- Items already in a backlog file (by `Origin:` backlink or normalized-title) are dropped, so a second run with no new deferrals prints an empty remainder.
- Each item carries a stable id, a one-line summary, provenance (path + kind + archived flag), and an `Approach` tag from `{direct, plan-tool, direct unless …}`.
- `--no-classify` runs the full sweep with zero Claude calls (pre-score tags only); `--classify` (default) refines via one batched call.
- Completion exits 0 regardless of count (exit-code convention).
- `deferred_digest.py` adds no import cycle and uses the `invoker=` seam so the classification call is stubbable in tests (no real `claude` spawn).
- No plan, report, or concept record is mutated (read-only).
- The final docs step removes `plan-seeds/deferred-findings-digest.md` (its read-only scope is absorbed here) and records the read-only digest capability in `CAPABILITIES.md` / `USE_CASES.md` / `README.md`. Because this seed is split from the shipped `2-scan-select-promote-deferred-work.md` plan, that plan is retired in favor of this Plan A + Plan B pair; note the split in `BACKLOG.md` if a tracking line helps.

## Deferred

- **Selection + promotion** (`--select`, `--apply`, backlog-entry / seed emitters, routing, idempotency) — the whole of `deferred-select-promote.md`.
- **Scope-guard `steps: []` out-of-scope stubs** as a fifth harvest source.
- **`--fail-on-findings`** — flip rc non-zero when the untriaged remainder is non-empty, for a CI "backlog has drifted from the plans" gate.
