> **Auto-archived**: this plan was swept on 2026-07-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Document the direct verbs across README, CAPABILITIES, and USE_CASES, and remove BACKLOG #118

## Summary

This is a docs-only step that closes out the plan. It documents the `direct-jira` and `direct-run` verbs (registered in step 6) across the three human-facing docs — `README.md`, `CAPABILITIES.md`, `USE_CASES.md` — states the name disambiguation once (the `direct-*` CLI verbs are unrelated to the `Approach: direct` tag used in `BACKLOG.md` entries), and removes the now-shipped `BACKLOG.md #118` entry plus its one cross-reference. The key correctness point: both verbs are registered subcommands after step 6, so `CAPABILITIES.md` must give each an owning capability — otherwise `plan-tool validate`'s no-Claude honesty check reports an `orphan-subcommand` finding. On green, `plan-tool validate` shows no `orphan-subcommand` or `absent-surface` finding for the two verbs, the README and USE_CASES entries describe the verbs correctly with resolving links, and `rg '#118' BACKLOG.md` returns nothing.

## Table of Contents

- [Summary](#summary) — what the step ships and the result on green.
- [Why](#why) — why the docs and the backlog need this closure now.
- [Input](#input) — the capability honesty-check contract this step must satisfy.
- [Files (creates vs edits)](#files-creates-vs-edits) — the four docs edited, no new files.
- [Implementation](#implementation) — the per-file edits, the disambiguation, and the validate gotcha.
- [Tests](#tests) — the doc/validate checks that stand in for unit tests on this non-code step.
- [Acceptance criteria](#acceptance-criteria) — checkable facts about the docs and backlog.
- [References](#references) — the docs relevant to this step.
- [Deferred](#deferred) — the generated CLI reference and flow note owned by other steps.

## Why

The plan adds `direct-jira` and `direct-run` (steps 4–6), but the operator-facing docs still describe a pipeline that only runs `create`, `detail`, `jira`, and `run` as separate commands. A verb an operator can't find in `README.md` or `USE_CASES.md` may as well not exist, and `CAPABILITIES.md` has a hard reason to be updated: `plan_tool/capability_catalog.py:check_capabilities` walks every registered subcommand primary name and reports an `orphan-subcommand` finding for any name with no owning capability. Step 6 registers both verbs, so leaving `CAPABILITIES.md` untouched makes `plan-tool validate` start reporting two orphan findings. This step is also the plan's backlog-reconciliation-forward closure: `BACKLOG.md #118` is the entry that asked for this work, its seed required removing it when the work ships, and it is now fully delivered — so it gets deleted, not left as a shipped stub.

## Input

This step must satisfy one machine-checked contract it does not own:

- **The capability honesty check** — `plan_tool/capability_catalog.py:check_capabilities` (surfaced by `plan-tool validate`). It reports `orphan-subcommand` for a registered subcommand with no owning capability, and `absent-surface` for a capability that cites a surface not present at HEAD. Both `direct-jira` and `direct-run` become registered primaries in step 6, so `CAPABILITIES.md` must list each under some capability's `surfaces`, and any module path this step cites (e.g. `plan_tool/cli/direct_cmd.py`) must exist on disk. There is a `CAPABILITY_ALLOWLIST` escape hatch for deliberately-unowned subcommands, but it is empty today and adding to it would hide the verbs rather than document them — do not use it here.
- **Step 6's registration** — step 6 makes `direct-jira` and `direct-run` real subcommand primaries (in `CANONICAL_COMMAND_ORDER` and `COMMAND_MODULES`). This step's `depends_on: 6` is what guarantees the honesty check sees them as subcommands rather than typos when `plan-tool validate` runs.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `README.md` — add both verbs to the `## CLI usage` command list, add a short usage/workflow note, mention them among the off-spine verbs, and state the name disambiguation once.
  - `CAPABILITIES.md` — give `direct-jira` and `direct-run` an owning capability so the honesty check stays clean.
  - `USE_CASES.md` — add a situation entry (and/or a `## Pick your entry point` row) so an operator discovers the verbs.
  - `BACKLOG.md` — delete the `#118` entry and remove its cross-reference from the `gate-signal:` theme index.

## Implementation

This step changes only prose and one hand-maintained catalog. Keep every claim about the verbs true to what steps 4–6 actually shipped — read `plan_tool/cli/direct_cmd.py` at HEAD before describing behavior, since detail files were authored before implementation and can drift.

**`README.md` — make the verbs findable and reference-complete.**

- **Add both verbs to the `## CLI usage` command list.** The list groups commands under `#`-comment headers (`# Author …`, `# Execute …`, `# Export …`). One clean approach: add a short `# Direct pipeline — chain the stages in one process` group with two lines, e.g. `plan-tool direct-jira <slug> [--from-existing <path> | --from <desc>] …` and `plan-tool direct-run <slug> [--from-existing <path> | --from <desc>] …`. Keep each line's flag set true to the real subparser step 6 built; do not invent flags. State in one clause per line what the chain runs (`direct-jira` = create → detail → jira; `direct-run` = create → detail → run --commit → reconcile-code).
- **Mention them among the off-spine verbs.** The `## Core subcommand workflow` section has an "A few verbs sit off the main spine" bullet list (`annotate`, branch-awareness, worktrees). Add a bullet naming the two direct verbs as one-process chains over the existing stages, so a reader scanning the top of the README sees them.
- **State the name disambiguation exactly once.** Add a single short note where the verbs are introduced: the `direct-*` **CLI verbs** are unrelated to the `Approach: direct` **tag** used in `BACKLOG.md` entries — that tag marks work done by direct hand-editing instead of the plan-tool pipeline; the verbs are a pipeline. These are different namespaces. Put this in exactly one place (README is the natural home) so a later reviewer doesn't read a repeated note as drift.
- **Optional — keep the index and workflows current.** If you add a new section, add its anchor to `## Table of contents`. A short worked example under `## Common workflows` is welcome but not required; if the CLI-usage lines are self-explanatory, one line each is enough.

**`CAPABILITIES.md` — the key edit.** Every registered subcommand needs an owning capability or `check_capabilities` flags it. Two valid shapes:

- **Recommended: one new capability block.** Add a `## Direct pipeline` section following the exact field shape of the existing blocks (`- **id:**`, `- **surfaces:**`, `- **principles:**`, all backtick-wrapped and comma-separated — the parser reads `_CAP_FIELD_RE` / `_parse_values`). One way:
  - `id:` `direct-pipeline`
  - `surfaces:` `direct-jira`, `direct-run`, `plan_tool/cli/direct_cmd.py`
  - `principles:` pick valid MISSION principle ids — `converge-on-correct-plan` (the chain drives the gated authoring/exec stages to a correct plan and, for `direct-run`, reconciled code) and `deterministic-non-determinism` (deterministic composition plus the no-Claude size gate). The honesty check rejects an invalid id, so use ids that already appear in `MISSION.md`.
- **Alternative (rejected as the default): fold the verbs into existing capabilities** — `direct-jira` under `jira-export`, `direct-run` under `step-execution`. This also clears the orphan check, but it scatters one coherent feature across two blocks and buries the "these chain the whole pipeline" story. Prefer the single new block; note this alternative so a reviewer knows it was considered.
- **Gotcha:** the capability `id` is a diff-stable handle only — nothing tags against it — so its exact spelling is free to choose, but it must be a kebab slug and unique (a duplicate id surfaces as a `malformed-doc` finding otherwise). The `surfaces` entries are what the check actually resolves: subcommand names against the live parser, path-shaped entries against disk.

**`USE_CASES.md` — help an operator pick the verb.** The doc has a `## Use-case catalog` (situation → command → result) and a `## Pick your entry point` table.

- **Recommended:** add a catalog entry for the small-change situation — "You have a small change and want the whole pipeline in one command" — showing `plan-tool direct-jira <slug> --from-existing seed.md` (or `direct-run`) and what you get (Jira stories, or committed + reconciled code) without stringing the stages together by hand. Follow the shape of the sibling entries (### N. heading, a sentence of situation, a fenced command block, a result sentence, a README link).
- **Also fine:** add one or two rows to the `## Pick your entry point` table (e.g. "A small change you want straight to Jira stories" → `direct-jira <slug> --from-existing <path>`). These verbs are authoring/entry-point workflows, so the entry-point table is an appropriate home — unlike a read-only analysis command, which the catalog owns.
- Keep any new links resolving (README anchors, `docs/cli/…` pages step 6 generates).

**`BACKLOG.md` — close #118.** BACKLOG treats implementation plans as the historical record for completed work, so a fully shipped entry is deleted, not kept as a status stub.

- **Delete the whole `#118` entry** — the block headed `**#118 — direct-jira / direct-run: slimmed one-shot pipeline for small changes**` and all its bullets.
- **Remove the cross-reference in the `gate-signal:` theme index** — the `**#118** (direct-* size gate — …)` item in the priority/theme index list near the top of the file. Leaving it there would keep a shipped item listed as open work.
- **Sweep for any other live reference.** After the edits, `rg '#118' BACKLOG.md` should return nothing that still frames #118 as open (a substring match like `1189` in unrelated text is not a `#118` reference and needs no change). Read each hit before editing.

## Tests

This step changes no production code, so its tests are doc-accuracy and the validate honesty check rather than new unit tests. Enumerate in a scratch check (or by eye):

- `plan-tool validate` (any registered plan) reports no `orphan-subcommand` finding for `direct-jira` or `direct-run`, and no `absent-surface` finding for the new capability's surfaces.
- The `CAPABILITIES.md` block parses: run `plan-tool validate` and confirm no `malformed-doc` capability finding (a duplicate id surfaces as `malformed-doc`), and that each cited principle id resolves (`no-valid-principle` absent).
- `rg '#118' BACKLOG.md` returns no line that still presents #118 as open work.
- Every relative link added to `README.md` / `USE_CASES.md` points at a file or anchor that exists (link-check the new links).
- The prose describing each verb matches `plan_tool/cli/direct_cmd.py` at HEAD (chain order, `--from-existing`/`--from` seed inputs, `--commit` on `direct-run`).
- `uv run pytest -m "not integration" tests/ -q` still passes — no code changed, but confirm the doc edits broke no drift-guarded test (e.g. a doc-consistency test, if any).

## Acceptance criteria

- `plan-tool validate` emits no `orphan-subcommand` finding for `direct-jira` or `direct-run`.
- `CAPABILITIES.md` lists both `direct-jira` and `direct-run` under a capability whose `surfaces` resolve and whose `principles` are all valid MISSION ids (no `absent-surface` / `no-valid-principle` finding).
- `README.md`'s `## CLI usage` command list contains a `direct-jira` line and a `direct-run` line, each naming the chain it runs.
- `README.md` states the `direct-*` verb vs `Approach: direct` tag disambiguation exactly once.
- `USE_CASES.md` contains at least one operator-discoverable entry (catalog situation or `## Pick your entry point` row) naming `direct-jira` and/or `direct-run`.
- `BACKLOG.md` no longer contains the `#118` entry, and `rg '#118' BACKLOG.md` returns no line framing #118 as open work (including the `gate-signal:` theme index reference).
- `uv run pytest -m "not integration" tests/ -q` passes.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — confirms how subcommand primaries are enumerated, which is what `capability_catalog.py:enumerate_subcommands` walks when the honesty check decides a verb is an orphan.

## Deferred

- **The `docs/cli/direct-jira.md` / `docs/cli/direct-run.md` reference pages** — generated and drift-guarded, owned by step 6 (`python -m plan_tool.cli_reference --write`); this step does not hand-edit them.
- **`docs/DIRECT_PIPELINE_FLOW.md`** — the design-and-flow note is step 1's file; this step only links to it if useful, it does not author or change it.
- **Adding the size-gate threshold or a chain-level `--iterate` flag to the docs** — no such flag exists; the plan defers threshold tuning (`## Out of scope`), so the docs describe only what shipped.

