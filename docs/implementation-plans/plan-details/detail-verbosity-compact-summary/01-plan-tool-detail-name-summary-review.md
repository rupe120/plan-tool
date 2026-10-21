# Step 1 — Add `plan-tool detail <name> --summary` review cards with dual-token section lookup

## Summary

Add a read-only `plan-tool detail <name> --summary` mode that prints one compact review card per step from the detail files already on disk — no Claude, always exit 0. Each card shows the step's title/complexity/change_type (from plan frontmatter) plus the Summary, Files, Acceptance, and a short Tests/Deferred slice pulled from the step's detail body, and deliberately drops Why, Table of Contents, Implementation, and References. The key design decision is a **dual-token section lookup**: each card field resolves from either its legacy heading token or its compact alias (`summary`|`intent`, `files`|`footprint`, `implementation`|`approach`, `acceptance`|`done`), so the cards work today on legacy seven-section files and keep working when step 3 introduces the compact schema. The renderer is a pure function in `plan_tool/detail.py`; the flag and dispatch live in `plan_tool/cli/authoring.py`. On green: `plan-tool detail 2-detail-verbosity-compact-summary --summary` prints per-step cards, honors `--step N`, spends no Claude, and returns 0.

## Table of Contents

- [Summary](#summary) — what the step ships and the observable result
- [Why](#why) — the verbosity problem this first phase chips at
- [Input](#input) — the detail-file section contract the cards read
- [Files (creates vs edits)](#files-creates-vs-edits) — the four code/doc/test files touched
- [Implementation](#implementation) — the flag, the dispatch branch, the pure renderer, the alias table
- [Tests](#tests) — unit renderer tests plus end-to-end CLI tests
- [Acceptance criteria](#acceptance-criteria) — CI-checkable behaviors
- [References](#references) — argparse + pytest docs for this step
- [Deferred](#deferred) — what later steps own (schema change, consumer rerouting)

## Why

Reviewers say `plan-tool detail` output is too long to sign off a step quickly, and the whole detail body gets injected into the `run` implementer prompt (`plan_tool/renderer.py:_load_detail`), so review load and token cost both scale with length. This step ships the cheapest half of the fix first: a read-only surface that distills each already-written detail file down to the parts a reviewer actually needs — Summary, Files, Acceptance, a short Tests slice — without touching the authoring prompt or the required-section schema (those are steps 2–5). It is pure upside: no existing file changes shape, nothing is force-migrated, and the dual-token lookup means the same renderer keeps working once the compact schema lands. It is also the natural place to introduce the alias vocabulary that step 2 then routes the rest of the read path through.

## Input

This step reads the **detail-file section contract** — the `{token: section_body}` map produced by `plan_tool/detail.py:parse_detail_file_sections`. Relevant facts:

- **Section tokens are the lowercased first word of each `## Heading`.** `## Acceptance criteria` → `acceptance`, `## Table of Contents` → `table`, `## Done when` → `done`, `## Footprint` → `footprint`. This is what makes a dual-token alias table possible without a schema change.
- **Legacy required tokens are fixed at seven** — `_REQUIRED_H2_TOKENS` in `plan_tool/detail.py` = `summary, table, why, files, implementation, tests, acceptance`. Cards read a subset of these today; the compact aliases (`intent`, `footprint`, `approach`, `done`) do not exist on disk yet but must resolve once step 3 emits them.
- **Per-step detail location** is `step.detail` (repo-relative), loaded as `repo_root / step.detail`, mirroring `plan_tool/renderer.py:_load_detail`. A step may have `step.detail is None` or a declared-but-missing file — the card must degrade gracefully, not crash.
- **Acceptance bullets** already have a parser: `plan_tool/detail.py:parse_acceptance_bullets` (reads the `acceptance` token). The card's acceptance slice can reuse it, but note it is single-token today — for a compact `## Done when` file the card needs the `done` alias, so pull the acceptance section through the new alias resolver rather than calling `parse_acceptance_bullets` directly (or extend it — see Implementation).

The plan frontmatter (`Plan`/`Step` from `plan_tool/schema.py`) supplies `title`, `complexity`, `change_type`, and `files` for the card header; parse it with the same `parse_plan` path every other read-only command uses.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — add the pure renderer (build a card string from a step + its parsed sections), the dual-token alias resolver, and an alias-table constant. No change to `parse_detail_file_sections` or `_REQUIRED_H2_TOKENS`.
  - `plan_tool/cli/authoring.py` — add the `--summary` flag to the `detail` subparser's mutually-exclusive mode group in `register`, and an early read-only branch in `cmd_detail` that renders cards and returns 0.
  - `docs/cli/detail.md`, `docs/cli/README.md` — regenerated (not hand-edited) by `python -m plan_tool.cli_reference --write` after the flag lands; drift-guarded by `tests/cli/test_cli_reference.py`.
  - `tests/test_detail.py` — unit tests for the renderer and alias resolver.
  - `tests/cli/test_authoring_cmds.py` — end-to-end tests driving `main(["detail", …, "--summary"])`.

## Implementation

**Add `--summary` as a read-only mode on the `detail` subparser.** In `plan_tool/cli/authoring.py:register`, add a `store_true` `--summary` argument to the existing `p_detail_mode` mutually-exclusive group (the group that already holds `--iterate`/`--no-iterate`, `--detail-only`, and `--reconcile`). Putting it in that group is the design decision: argparse then rejects `--summary --reconcile`, `--summary --iterate`, etc. for free, which is correct — summary is a read-only view, not an authoring or audit mode. Keep the help line one sentence (it becomes the `docs/cli/detail.md` row and, indirectly, the `--help` text). `--step` already exists on the subparser and needs no change; the summary branch just honors `args.step`.

**Branch early in `cmd_detail`.** Right after `path = resolve_plan_for_context(ctx, args.name)` (before the `--reconcile` branch and before any run log opens), add: `if getattr(args, "summary", False): <render + print>; return 0`. Constraints that must hold:
- **No run log, no checkpoint, no Claude.** This is a pure read like `cmd_status` — it must not open a run-log JSONL or invoke any invoker. Placing the branch before the run-log open is what guarantees no ghost log under `.plan-tool/runs/`.
- **Always exit 0.** Per the project's exit-code convention, a completed read exits 0 even if a step has no detail file. Do not return non-zero for a missing detail file — render a "no detail yet" card line instead.
- **Honor `--step N`.** When set, render only that step's card; an unknown step id should print a clear message and still exit 0 (match how the reconcile/authoring paths treat an out-of-range `--step`, but without their error rc — this is a read).

**Put the renderer in `plan_tool/detail.py` as a pure function.** Recommended shape: a top-level `render_detail_summary(plan, *, repo_root, step_filter=None) -> str` that loops steps (filtered), resolves each `step.detail` to a body the same way `plan_tool/renderer.py:_load_detail` does (`repo_root / step.detail`, tolerating `None`/missing), parses it via `parse_detail_file_sections`, and calls a per-card helper `render_step_summary_card(step, sections) -> str`. Returning a string (not printing) keeps it unit-testable in `tests/test_detail.py` without capturing stdout; the CLI handler owns the actual `print`/console styling. One way to style the print: reuse `plan_tool/style.py:render_markdown_for_console`, but plain text is acceptable — leave that to the implementer.

**The dual-token alias resolver is the foundational logic.** Add a small resolver — e.g. `resolve_detail_section(sections, *tokens) -> str` returning the first non-empty section body among the given tokens — plus an alias-table constant naming the four pairs:
- `summary` | `intent`
- `files` | `footprint`
- `implementation` | `approach`
- `acceptance` | `done`

The card uses the resolver for its Summary field (`summary`|`intent`), its Files field (frontmatter `files:` and/or the `files`|`footprint` section), and its Acceptance field (`acceptance`|`done`). Include the `implementation`|`approach` pair in the constant even though the card does not display it — step 2 reuses the same table to reroute the read-path consumers, and keeping one source for the pairs avoids a second divergent copy. Constraint: **legacy files must resolve unchanged** — a seven-section file has `summary`/`files`/`acceptance` tokens, so the resolver must return those when the compact alias is absent, and vice versa. Do not require both.

**Card contents** (what each card shows, grounded in the plan's Phase A spec):
- header: step id, title, complexity, change_type (from frontmatter `Step`).
- Summary/Intent body (already short — show in full).
- Files: frontmatter `files:` list and/or the resolved Files/Footprint section.
- Acceptance/Done: the bullet list (reuse `parse_acceptance_bullets` for the legacy `acceptance` token, or pull the section through the resolver so a compact `## Done when` file also works — the resolver route is preferred so both schemas hit the same path).
- Tests: at most a short/truncated bullet slice from the `tests` section (pick a small cap, e.g. first ~5 bullets, and mark truncation; state the number you choose).
- Deferred: only when the `deferred` section is present and non-empty.
- **Omit** Why, Table of Contents (`table`), Implementation/Approach, and References — never render these.

**Foundational-logic sweep — do not widen this step to fix them.** The single-token reads that will need the alias table are in `plan_tool/review.py` (e.g. the detail-quality dedup reading `sections.get("summary")`/`sections.get("why")`, and the acceptance read that already falls back `sections.get("acceptance criteria") or sections.get("acceptance")`). Rerouting those through the alias resolver is step 2's declared job (refactor). Leave them untouched here and note them in Deferred — touching them now would fuse this feature step with step 2's refactor.

## Tests

### Test-creation order (feature step)

This is a **feature** step. Add every unit test below **with** the implementation; each must be green before the step is considered done. `enforce_step_tests: true` is set on the plan, so the step must author real test coverage.

**Unit — renderer + alias resolver (`tests/test_detail.py`, approx. 8 tests):**
- `resolve_detail_section_prefers_first_present` — returns the legacy token body when the compact alias is absent.
- `resolve_detail_section_reads_compact_alias` — returns the `intent`/`footprint`/`done` body when only the compact token exists.
- `card_renders_legacy_seven_section_file` — a Summary/Files/Acceptance-bearing legacy body produces a card with those fields.
- `card_renders_compact_file` — an Intent/Footprint/Done-when body produces a card with the same fields via aliases.
- `card_omits_why_toc_implementation_references` — none of those section bodies appear in the card text.
- `card_truncates_tests_section` — a long Tests section is capped to the chosen bullet count with a truncation marker.
- `card_includes_deferred_only_when_present` — Deferred appears when the section exists, is absent otherwise.
- `render_handles_missing_detail_file` — a step with `step.detail is None` or a declared-but-missing path renders a "no detail" card without raising.
- `render_step_filter_scopes_to_one_step` — `step_filter=N` returns only that step's card.

**End-to-end — CLI wiring (`tests/cli/test_authoring_cmds.py`, approx. 4 tests):**
- `detail_summary_exits_zero_and_prints_cards` — `main(["detail", <name>, "--summary", "--repo-root", …])` returns 0 and stdout contains the step titles/acceptance text. The `tests/cli/conftest.py` autouse backend gate already proves no Claude is spawned — no invoker stub needed.
- `detail_summary_step_scopes_output` — `--summary --step 1` prints only step 1's card.
- `detail_summary_rejects_reconcile` — `--summary --reconcile` errors with argparse rc 2 (mutually exclusive).
- `detail_summary_rejects_iterate` — `--summary --iterate` errors with argparse rc 2.

**Regen check:** re-run `python -m plan_tool.cli_reference --write` and let `tests/cli/test_cli_reference.py` confirm `docs/cli/detail.md` / `docs/cli/README.md` match the live parser.

## Acceptance criteria

- `plan-tool detail <name> --summary` exits 0 and prints one review card per step, spending no Claude.
- `--summary --step N` prints only step N's card and exits 0.
- A card built from a legacy seven-section detail file and one built from a compact Intent/Footprint/Done-when file both show Summary, Files, and Acceptance content (dual-token lookup).
- Cards never contain the Why, Table of Contents, Implementation/Approach, or References section bodies.
- A step with no detail file (or a missing declared file) renders a "no detail" card and still exits 0 — no crash, no non-zero rc.
- `--summary` combined with `--reconcile` or `--iterate` fails with argparse rc 2.
- `docs/cli/detail.md` and `docs/cli/README.md` are regenerated and `tests/cli/test_cli_reference.py` passes.
- All new tests in `tests/test_detail.py` and `tests/cli/test_authoring_cmds.py` are green.

## References

- [argparse — Parser for command-line options, arguments and subcommandshttps: — for adding `--summary` to the mutually-exclusive mode group and its exit-code behavior.
- [pytest — tmp_path fixturehttps: — hermetic temp plans/detail files for the renderer and CLI tests.
- [pytest — Fixtures referencehttps: — built-in fixtures and markers for the unit + end-to-end tests.

## Deferred

- Rerouting the existing single-token section reads in `plan_tool/review.py` (the detail-quality dedup's `sections.get("summary")`/`sections.get("why")` and the acceptance read) through the dual-token alias resolver — step 2 (refactor, depends_on 1) owns this; step 1 only introduces the resolver and uses it in the new card path.
- Changing the required detail H2 set to Intent/Footprint/Approach/Done-when and rewriting the authoring + quality prompts — step 3 owns this; step 1 makes no schema or prompt change.
- The low-complexity compact-only gate — step 4.
- Sibling-body prompt hygiene (preferring compact siblings) — step 5.
- Docs/backlog reconciliation (CAPABILITIES/USE_CASES/RUNBOOK, BACKLOG #149/#49) — step 6.
- Writing `REVIEW.md` to disk, a `--json` summary mode, and auto-migrating historical detail files — all listed under the plan's own Deferred section (v1 is stdout-only).
