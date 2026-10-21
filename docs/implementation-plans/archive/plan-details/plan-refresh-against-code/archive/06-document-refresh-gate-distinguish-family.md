> **Auto-archived**: this plan was swept on 2026-06-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Document the refresh gate and distinguish `reconcile-plan` / `reconcile-plan-walk` / `reconcile-plan --refresh` / `create --reprocess` across operator surfaces

## Summary

- **Docs-only step (`change_type: non-code`).** Document the step 1–5 refresh gate across the six operator surfaces and make the four crowded reconcile/refresh-family verbs distinguishable so a reader never conflates them.
- **Primary files:** `RUNBOOK.md` (new "refresh a stale plan" walkthrough + four-verb disambiguation table), `README.md` (audit-stage prose + synopsis line), `CLAUDE.md` (one-line family note), `integrations/claude/SKILL.md` + `integrations/codex/SKILL.md` (lockstep decision-tree + at-a-glance rows), `docs/AUDIT_RESUME_FLOW.md` (refresh resume posture).
- **Load-bearing decision:** the shipped surface is `reconcile-plan --refresh` (a **flag on the existing `reconcile-plan` subparser**, step 4) — **not** a new top-level verb and **not** `--pre-start`. Every doc must call it `reconcile-plan --refresh`, never imply a standalone `refresh` command.
- **Cross-step hazard:** steps 2–5 are **unimplemented at HEAD** — `plan_tool/grounding.py`, `plan_tool/refresh.py`, and the `--refresh` flag do not exist yet. Every cited code symbol below is pinned to its predecessor step's detail; **grep each against HEAD before writing** and adapt to the shipped shape if it diverged (per the captured docs-step freshness rule).
- **On green:** the four verbs are described with their distinguishing axis on every surface they appear; `--reprocess` reads as a placeholder-fill (no code involvement), not a code reconcile; RUNBOOK carries the stale-plan refresh walkthrough the plan's acceptance criteria mandate; no production code changed.

## Table of Contents

- [Why](#why) — the four-verb conflation risk and the undocumented refresh gate
- [Files (creates vs edits)](#files-creates-vs-edits) — the six docs and the specific edits per file
- [Implementation](#implementation) — the canonical four-verb framing and the per-file edits
- [Tests](#tests) — there are none; see Verification
- [Verification (non-code step)](#verification-non-code-step) — the grep/anchor/link/lockstep checks
- [Acceptance criteria](#acceptance-criteria) — observable doc states a reviewer can check
- [References](#references) — argparse + grounding/fingerprint surfaces this step describes
- [Deferred](#deferred) — surfaces and symbol-shape confirmations left to implementation time

## Why

The reconcile/refresh family is already four near-neighbors that share the word "reconcile" and a `plan-tool reconcile-plan*` prefix, and steps 1–5 add a fifth concept (the cheap fingerprint-gated refresh) plus a tracked grounding baseline that no doc mentions. Today `create --reprocess`'s help reads like a code reconcile though it only fills `_(TODO)_` placeholders from an archived predecessor (`plan_tool/reprocess.py` module docstring — "Fill `_(TODO)_` placeholders in an existing plan from its archive"), and there is no operator-facing description of "is this plan still grounded against current code, and re-ground it cheaply." A reader who hits any one surface first must be able to tell the four apart from that surface alone — the shared keyword makes the failure mode silent overlap, not an obvious gap.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `RUNBOOK.md` — add a `### Refresh a stale plan against code (`reconcile-plan --refresh`)` subsection under `## Workflow: per-subcommand reconcile` (the heading at `## Workflow: per-subcommand reconcile`), plus a four-verb disambiguation table; add the matching TOC anchor line under `## Table of contents` if a new H2 is introduced (a new H3 under an existing H2 needs no TOC line — the TOC lists H2s only).
  - `README.md` — extend audit stage **point 3** (the `reconcile-plan` is mainly for **older plans that may have gone stale** bullet) to name `reconcile-plan --refresh`; add `[--refresh]` to the `plan-tool reconcile-plan <name> …` synopsis line; clarify the `--reprocess` inline comment in the create synopsis block.
  - `CLAUDE.md` — add one line to the `## What this is` area (beside the existing `annotate` / `reconcile-plan` contrast sentence) distinguishing `reconcile-plan --refresh` from plain `reconcile-plan` and from `create --reprocess`.
  - `integrations/claude/SKILL.md` — add a decision-tree row, an at-a-glance reconcile-row clause, and a frontmatter `description:` audit-list mention; **lockstep** with the codex SKILL.
  - `integrations/codex/SKILL.md` — identical content to the claude SKILL, diverging only on backend prose (`codex exec` vs `claude` subprocess).
  - `docs/AUDIT_RESUME_FLOW.md` — add the refresh gate's resume posture (tracked grounding baseline; no-drift no-op spawns no Claude; the refresh path is **not** wrapped in `iteration_session`).

## Implementation

### The canonical four-verb framing (use verbatim across surfaces)

Single-source this distinction; every surface restates the relevant subset so no table lets two share the keyword without a distinguishing clause:

- **`reconcile-plan <name>`** — plan-vs-code **audit that mutates the plan** to match drifted code. One Claude call **every run** (no cheap gate). Best for older/stale plans or as a code-fit supplement to `completeness-audit`. Handler `plan_tool/cli/review_cmd.py:cmd_review`.
- **`reconcile-plan-walk <name>`** — **apply a *saved* reconcile's findings** interactively, **no Claude call**. Kind-agnostic walker over the newest saved sidecar (`plan_tool/cli/review_cmd.py:cmd_review_walk`). It runs *no* audit — it replays one already on disk.
- **`reconcile-plan --refresh`** (steps 3–4) — the **cheap fingerprint-gated refresh**: recompute the plan's code fingerprint, diff against the stored grounding baseline; **no drift → no-op, exit 0, no Claude call**; drift → reconcile **scoped to exactly the changed files**, then re-stamp the grounding baseline. Its axis is *"are the plan's premises still valid"* (pre-start framing), not *"does code satisfy a done step."* A flag on the `reconcile-plan` subparser (`plan_tool/cli/review_cmd.py`), entry point `plan_tool/refresh.py:refresh_plan`.
- **`create --reprocess`** — **fill `_(TODO)_` placeholders from an archived predecessor** under `<plan-dir>/archive/`. Deterministic merge, **no Claude call, nothing to do with code**. Handler `plan_tool/cli/authoring.py:_cmd_create_reprocess` → `plan_tool/reprocess.py:reprocess_plan`.

The one-sentence discriminator per verb: **reconcile-plan = audit now (Claude); reconcile-plan-walk = replay a saved audit (no Claude); reconcile-plan --refresh = audit only if code drifted (cheap gate); create --reprocess = fill placeholders from an archive (no code).**

### `RUNBOOK.md`

- **Add `### Refresh a stale plan against code (`reconcile-plan --refresh`)`** under `## Workflow: per-subcommand reconcile`, after the `### Reusing a saved reconcile (`--reuse`)` subsection. Cover:
  - The two outcomes: unchanged tree → "still grounded", exit 0, **no Claude call**; drifted watched file → reconcile scoped to the changed path(s) + re-stamp the grounding baseline, then point at `reconcile-plan-walk <name>` to apply the saved findings.
  - The **grounding baseline** is a tracked artifact stamped after `create`/`detail` (step 5) — a plan with none is treated as "needs grounding" and reconciles over its whole declared surface (never crashes). Pin the artifact name/path to step 2/5's shipped shape (`<plan-dir>/plan-details/<slug>/grounding.json`, per step 2's detail) — **confirm at HEAD**.
  - A copy-paste block mirroring the existing `### Reusing a saved reconcile` block's style:
    ```bash
    plan-tool reconcile-plan my-feature --refresh        # cheap gate: no Claude unless code drifted
    ```
- **Add a four-verb disambiguation table** at the top of `## Workflow: per-subcommand reconcile` (or immediately after its intro paragraph) so the reader sees all four side by side. Reuse the canonical framing's one-line discriminators. Distinguish this from the existing `## Workflow: completeness checks` four-verb table — that one covers `validate`/`reconcile-plan`/`completeness-audit`/`completeness-apply`; this one covers the reconcile/refresh/reprocess family.
- **TOC:** the new content is an H3 under the existing `## Workflow: per-subcommand reconcile` H2; the `## Table of contents` lists H2s only, so **no TOC line is added** unless a new H2 is introduced. If a reviewer prefers a standalone `## Workflow: refresh a stale plan` H2, add the matching `- [Workflow: refresh a stale plan](#workflow-refresh-a-stale-plan)` TOC line and the duplicate back-link near the doc tail (the doc repeats the per-subcommand-reconcile link at its end). Default to the H3-under-existing-H2 placement (no new TOC churn).

### `README.md`

- **Audit stage, point 3** (the bullet beginning `**audit** — `completeness-audit` is the primary authoring audit`): append a clause naming `reconcile-plan --refresh` as the **cheap, fingerprint-gated** variant of `reconcile-plan` that skips Claude when nothing drifted — distinct from plain `reconcile-plan` (always one Claude call) and from `annotate` (forward-seed, never mutates).
- **Synopsis line** `plan-tool reconcile-plan <name> [--step N] [--dry-run] [--no-heuristic] [--no-allow-missing-parent]`: add `[--refresh]` to the bracketed flag list. **Confirm step 4 shipped the flag on this subparser** before editing.
- **`--reprocess` clarification:** the create synopsis already carries `plan-tool create my-slug --reprocess  # fill _(TODO)_ from archive (no Claude)` and a `--reprocess` (deterministic, no Claude): lifts H2 section bodies… bullet. Verify both still read as placeholder-fill (not code reconcile); tighten only if step 4's help-text change (`plan_tool/cli/authoring.py` `--reprocess` `help=`) introduced new wording to mirror. No code-reconcile language anywhere near `--reprocess`.

### `CLAUDE.md`

- **Add one line** in the `## What this is` section beside the existing `annotate is a forward-seed bridge…` / `reconcile-plan, which mutates a live plan in place` sentence: state that **`reconcile-plan --refresh`** is the cheap fingerprint-gated form of `reconcile-plan` (no Claude on no-drift) and that **`create --reprocess`** is unrelated to code (fills `_(TODO)_` placeholders from an archive). Keep it to one sentence — CLAUDE.md is terse per the [[feedback_concise_docs]] rule.
- Do **not** restructure the pipeline diagram; refresh is a mode of `reconcile-plan`, not a new spine stage.

### `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` (lockstep)

Apply the **same three edits to both** files; diverge only on backend prose (`claude` subprocess in the claude SKILL, `codex exec` in the codex SKILL):

- **Decision tree** (`## Decision tree for common user asks`): add a row — `| "is plan X still current / refresh it against the code" | `plan-tool reconcile-plan X --refresh` (cheap: no Claude unless code drifted) |`. Place it near the existing `"make the plan match the code"` rows.
- **Subcommands at a glance** (`## Subcommands at a glance`): in the **Audit · reconcile** row, append `, reconcile-plan --refresh <name> (cheap fingerprint gate — reconcile only the drifted files, skip Claude on no drift)` after the existing `reconcile-plan-walk <name>` clause.
- **Frontmatter `description:`** audit-list: the current list reads `audit (validate / reconcile-plan / completeness-audit / verify-all)`. Leave the verb list as-is (refresh is a flag, not a verb) **or** append ` / reconcile-plan --refresh` only if the same token is added identically to both SKILLs. Default: leave the frontmatter list unchanged and carry the refresh mention in the body rows only — a flag does not belong in a verb catalog.
- **Do not touch** the per-step `--mode security` / `--mode check` tokens or the `argument-hint:` line — refresh is unrelated to `--mode`.

### `docs/AUDIT_RESUME_FLOW.md`

- **Add a short subsection** (e.g. `## Refresh resume posture`) or a TL;DR bullet recording:
  - The **grounding baseline is a tracked artifact** (`grounding.json` sidecar per step 2) — the durable state the refresh gate diffs against; it survives crash because it is on disk and committed.
  - **No-drift refresh is a zero-Claude no-op that does not rewrite the baseline** — its "resume" is trivial (nothing to continue). Mirror the `## What's reused vs re-derived` framing: the code-fingerprint diff is recomputed from disk every run.
  - **The refresh path is *not* wrapped in `iteration_session`.** Per the captured pattern, the security `--iterate` loop is already a documented `iteration_session`-excluded loop; refresh is a second non-`iteration_session` path (single scoped reconcile, no convergence loop, no in-run drift lock). Document it as an exception — do **not** bump any "N entry points wrap iteration_session" count without grepping the current count at HEAD first.
  - Optionally extend the `## Source map` table with a `Refresh entry point | plan_tool/refresh.py (refresh_plan)` row and a `Grounding baseline | plan_tool/grounding.py` row — **only if those modules exist at HEAD** when this step runs; if steps 2–3 are still unimplemented, cite them as the introducing steps in prose and omit the table rows to avoid a dead anchor.

## Tests

No unit tests — this step changes only documentation. See [Verification](#verification-non-code-step). No test-ordering directive applies and no production code changed.

### Verification (non-code step)

Each check is a greppable/inspectable assertion mirrored 1:1 into [Acceptance criteria](#acceptance-criteria):

- **Refresh documented in RUNBOOK** — `grep -n -- '--refresh' RUNBOOK.md` returns the new walkthrough; the block states "no Claude call" on the no-drift path.
- **Four-verb distinction present** — `RUNBOOK.md` contains all four of `reconcile-plan`, `reconcile-plan-walk`, `--refresh`, and `--reprocess` within the per-subcommand-reconcile section, each with a distinguishing clause.
- **README synopsis + prose** — `grep -n -- '--refresh' README.md` hits the `reconcile-plan` synopsis line and audit-stage point 3.
- **`--reprocess` reads as placeholder-fill** — `grep -n -- '--reprocess' README.md CLAUDE.md` shows no "code"/"reconcile-the-code" framing near it.
- **SKILL lockstep** — `diff <(grep -n -- '--refresh' integrations/claude/SKILL.md) <(grep -n -- '--refresh' integrations/codex/SKILL.md)` shows matching mentions (line numbers may differ; the mention set must match); the only intended divergence is backend prose.
- **No `--mode` conflation** — `grep -n 'mode.*refresh\|refresh.*mode' integrations/*/SKILL.md README.md RUNBOOK.md` is empty: nothing calls refresh a `--mode`.
- **TOC integrity** — every `## ` heading in `RUNBOOK.md` has a matching `## Table of contents` entry and every TOC anchor resolves to a heading slug (only relevant if a new H2 was added).
- **AUDIT_RESUME_FLOW accuracy** — the refresh subsection states the gate is zero-Claude on no-drift and is **not** wrapped in `iteration_session`; any `iteration_session` entry-point count cited there was re-verified against HEAD.
- **Per-symbol freshness** — every cited code symbol (`refresh_plan`, `grounding.json`, `reconcile-plan --refresh`, `_cmd_create_reprocess`, `cmd_review_walk`) was grepped against HEAD before writing; a symbol introduced by an unimplemented predecessor step (2–5) is attributed to that step rather than cited as already-present.

## Acceptance criteria

- `RUNBOOK.md` documents `reconcile-plan --refresh` with both outcomes (no-drift no-op / scoped reconcile + re-stamp) and explicitly states the no-drift path makes no Claude call.
- `RUNBOOK.md`'s per-subcommand-reconcile section distinguishes all four of `reconcile-plan`, `reconcile-plan-walk`, `reconcile-plan --refresh`, and `create --reprocess`.
- `README.md`'s `reconcile-plan` synopsis line includes `--refresh` and audit-stage point 3 names the cheap fingerprint-gated variant.
- No surface (`README.md`, `CLAUDE.md`, `RUNBOOK.md`, both SKILLs) describes `--reprocess` as a code reconcile; it reads as placeholder-fill from an archive.
- No surface calls `reconcile-plan --refresh` a `--mode`.
- `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` carry identical refresh content modulo backend prose.
- `docs/AUDIT_RESUME_FLOW.md` records the refresh gate's tracked grounding baseline and that the refresh path is excluded from `iteration_session`.
- `CLAUDE.md` distinguishes `reconcile-plan --refresh` from plain `reconcile-plan` and from `create --reprocess` in one sentence.
- All intra-doc links and TOC anchors in edited files resolve; no production code changed (`git diff --name-only` lists only the six in-scope docs).

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — confirms `--refresh` rides the existing `reconcile-plan` subparser (a flag, not a new subcommand) so the docs frame it as a mode, not a verb.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the sha256 code/plan fingerprints the refresh gate diffs; read to describe the "no Claude unless drift" gate accurately.

## Deferred

- **`--pre-start` naming** — the plan floats `reconcile-plan --refresh` / `--pre-start`; step 4 ships `--refresh`. Document `--refresh` only; do not introduce `--pre-start` in docs unless it shipped at HEAD.
- **`grounding.json` shape / path confirmation** — pinned to step 2's detail (`<plan-dir>/plan-details/<slug>/grounding.json`); confirm the filename and location at HEAD when steps 2/5 are implemented and adjust any cited path.
- **`AUDIT_RESUME_FLOW.md` source-map rows for `refresh.py` / `grounding.py`** — add only once those modules exist at HEAD; otherwise cite the introducing steps in prose to avoid a dead anchor.
- **Branch-awareness branch-creation hook surface** — `refresh_plan`'s second intended caller; documented by the branch-awareness plan, not here.
- **`PLAN_FORMAT.md` grounding-frontmatter rows** — only relevant if steps 2/5 chose frontmatter fields over the sidecar; out of this step's declared `files:` and routed to whichever step lands the chosen persistence shape.
