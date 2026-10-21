> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Update docs and close out the backlog: jira-grade contract in DETAIL_FORMAT.md/JIRA_FORMAT.md and the flow docs, mark BACKLOG #164 instrument-shipped/evaluation-pending, and re-scope #149 to alias the jira-grade tokens

## Summary

Document the jira-grade lane steps 3–9 shipped and close out the plan's bookkeeping: `DETAIL_FORMAT.md` becomes the single reference home for the five-section jira-grade detail contract, `JIRA_FORMAT.md` documents `jira --grade jira`, `DATA_CONTRACT.md` documents the one CLI-payload key step 9 mints, and the three flow docs (`docs/DETAIL_FLOW.md`, `docs/RUN_FLOW.md`, `docs/AUDIT_FLOW.md`) each gain their command's grade selector and its gates. In `BACKLOG.md`, #164's Status moves to instrument-shipped / evaluation-pending and #149 is re-scoped so its compact authoring schema aliases `plan_tool/jira_grade.py`'s tokens instead of defining its own; `CLAUDE.md`'s reference-docs lines are updated to name both grade contracts; `CAPABILITIES.md` and `USE_CASES.md` acknowledge the grade lane at their own altitudes (surface catalog and when-to-reach-for-it, respectively). The key design decision is a strict ownership split: every jira-grade fact class gets exactly one home document and every other document cross-links it, so the five-H2 token list appears verbatim in `DETAIL_FORMAT.md` only. On green, all ten files are edited, no production code changes, and every backticked path and cited symbol in the new prose exists at HEAD.

## Table of Contents

- [Summary](#summary) — what the step documents and the one design decision
- [Why](#why) — why the docs and backlog must land before the plan closes
- [Input](#input) — the shipped behaviors (steps 3–9) this step describes, and the verification limit
- [Files (creates vs edits)](#files-creates-vs-edits) — per-file edits; no new files
- [Implementation](#implementation) — the ownership split, per-document content, and the backlog fence
- [Tests](#tests) — referential-integrity verification for a non-code step
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the one spec relevant to documenting the H2 contract
- [Deferred](#deferred) — bookkeeping owned by other steps or later stages

## Why

Steps 3–9 added a second detail contract and threaded a grade selector through four commands, but every reference doc still describes a single-grade world: `DETAIL_FORMAT.md` documents only the seven-section run-grade schema, `JIRA_FORMAT.md`'s "What writes them" says the export reads `Step.detail`, and none of the three flow docs mention a grade flag (a grep for `--grade` under `docs/` returns nothing at HEAD). An undocumented opt-in lane is invisible to the next operator and to future plan authors, and the two backlog entries that motivated the plan still describe the pre-plan state: #164's Status ends at "re-seeded 2026-07-22" with the split into the seed group, and #149 still carries the schema-authority decision as a pending note ("Stage 01's final step re-scopes this entry") rather than as its actual scope. This step is that final step: it writes the docs, flips #164 to instrument-shipped/evaluation-pending, and performs the #149 re-scope the entry already promises.

## Input

- **Step 3's contract authority** (plan_tool/jira_grade.py, created by step 3): the five required H2 display names (`Intent`, `Change`, `Constraints`, `Done when`, `Out of scope`), first-token matching, the closed schema (unknown top-level H2s are blocking), the plain-English prose gate split by audience (blocking only in the authoring retry loop; read-time consumers validate structure only), and the artifact path convention `<plan_dir>/plan-details/<plan_slug>/jira/<NN>-<step_slug>.md` via `derive_jira_detail_path` in plan_tool/detail_artifacts.py (created by step 1).
- **Step 4's authoring mode** (`plan-tool detail <name> --grade jira`): its own prompt (`plan_tool/prompts/detail-jira.md`), response gate, `jira-detail-step-{NN}` checkpoint namespace, the bypassed run-grade machinery (quality findings, `--iterate` convergence, lessons, purity/split, the CLI completeness tail), the rejected-flag set, and the rule that `Step.detail` stays run-grade-only.
- **Step 5's export mode** (`plan-tool jira <name> --grade jira`): jira-grade bundle grounding threaded through prompt, both formatters, and append-mode refresh; the aggregated pre-backend hard failure; single output artifact regardless of grade; `direct-jira` staying on the run-grade default.
- **Step 6's run mode** (`plan-tool run <name> --detail-grade jira`): grade as a separate axis from `--mode`, the `run-jira` prompt, the aggregated preflight before the run log plus the render-time deep gate, the skipped permissive missing-detail helpers, and grade carried in the resume command and run-log flags.
- **Step 7's audit grounding** (`plan-tool completeness-audit <name> --grade jira`): which bytes the audit reads and which contract the judge is told to apply — the `--grade` flag and its rc-2 guards (`--iterate`/`--reuse-audit`/`--reuse-audit-id` rejected), purity forced off, the grade-selected bundle framing in the audit prompt, the bare-step treatment for a missing jira artifact and the note-instead-of-body rendering for a mislabeled one, and the grade axis on the detail-bundle fingerprint. 
- **Step 8's dispatch refactor** (behavior-preserving, no operator-visible surface): the completeness battery's detectors are dispatched through one registry, with a source-level guard failing the build if a detector is called outside it. Nothing to document as behaviour; mention it only if a flow doc's source map cites the battery's internals.
- **Step 9's grade-aware battery and report surfaces**: each registry entry classified on the grade axis (run-grade detail readers skipped under jira, grade-independent checks always run), the jira bundle check's coverage and contract findings and how they block through the unmodified gate, the suppressed `-completeness.json` sidecar and convergence diagnosis, the one-line stderr notice announcing both, the grade-correct next-steps prose (no `completeness-apply`, no `--iterate`), and the `detail_grade` key plus framing and fingerprint provenance emitted under jira selection on both the `.md` and `--json` paths.
- **The #169 stage-01 pointer and any #171 direction question**: previously owned by the falsification-check step, which stage 01 no longer carries — this step owns them now, alongside #164's Status line. Keep the fence below: no other entry is touched.
- **Verification limit:** step 1 is `done` — `plan_tool/detail_artifacts.py` is merged and ships `derive_step_slug`, `_plan_slug`, `derive_detail_path`, `find_unreferenced_detail_for_step`, `DetailArtifactResolution`, and `resolve_detail_artifact`; verify those against the module, not against this file. Steps 2–9 had not landed at authoring time, so every symbol above cited from them is a dependency contract from the sibling detail files. Before writing prose, grep the merged code for the final spellings (flag names, module names, path convention, rejected-flag sets) and describe what shipped, not what was planned; where the two diverge, the code wins.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `DETAIL_FORMAT.md` — add the jira-grade contract section (the sole home for the five-H2 token list, matching rule, closed-schema rule, `jira/` path convention, prose-gate audience split, and lifecycle non-interactions); extend the source-of-truth callout to name `plan_tool/jira_grade.py` for the jira grade beside `plan_tool/detail.py` for the run grade.
  - `JIRA_FORMAT.md` — document `--grade jira` in "What writes them" (grounding, hard-fail, links, append-refresh churn in **both** grade directions — alternating grades flip-flops the links; they always describe the most recent export's grounding); cross-link `DETAIL_FORMAT.md` for the contract; update "See also".
  - `DATA_CONTRACT.md` — add the `detail_grade` row to the `### completeness-audit --json` top-level table (step 9 mints it, emitted only under jira selection). The doc's Intentional exclusions section states no JSON key is intentionally undocumented, and the drift guard cannot catch this one: `tests/test_data_contract.py`'s doc↔code checks are parametrized over `contract.persisted_dataclass_contracts()`, so a hand-maintained CLI-payload table is outside their reach. This row is the only edit — the sidecar grade marker stays deferred (see Deferred).
  - `docs/DETAIL_FLOW.md` — add a jira-grade authoring-lane section: the `--grade jira` bundle (prompt, gate, target, checkpoint namespace), the bypassed machinery, and the skipped completeness tail.
  - `docs/RUN_FLOW.md` — add `--detail-grade jira`: the grade-vs-mode axis, the two gate placements, dry-run ordering, the skipped permissive helpers, and resume/run-log propagation.
  - `docs/AUDIT_FLOW.md` — add `completeness-audit --grade jira`: audit-and-report only, the rejected/forced-off surface, sidecar suppression, bare-step and mislabeled-body treatment, the report provenance block, and the grade-correct next-steps prose.
  - `CAPABILITIES.md` — extend the existing `detail`/`jira`/`run`/`completeness-audit` surface entries to name the opt-in grade lane (no new command surface, so the `plan-tool validate` catalog check is unaffected; a line or two per entry).
  - `USE_CASES.md` — add the when-to-reach-for-it guidance: authoring a jira-grade bundle beside run-grade and consuming it via `--grade`/`--detail-grade`, cross-linking `DETAIL_FORMAT.md` for the contract.
  - `BACKLOG.md` — update #164's Status (instrument-shipped / evaluation-pending), re-scope #149's What/Approach to alias the jira-grade tokens, and file one new entry: the jira-artifact renumber-staleness lifecycle gap (unpointed `jira/` artifacts go stale across any step renumber — split, merge, or scope-out; consumers fail loudly at read time; durable migration deferred until a real corpus exists — the route steps 3–6's Deferred sections promise). Touch no other entry.
  - `CLAUDE.md` — update the `DETAIL_FORMAT.md` reference-docs bullet (and, if the correctness-gates paragraph's "seven-section response gate" phrasing reads as the only detail gate, one clause there) to acknowledge both grades. Keep it to a line or two — depth lives in the docs.

## Implementation

### Ownership split (do this first)

Each fact class has exactly one home; every other document cross-links instead of restating. This is the step's main constraint — the copies are what drift.

- **The contract itself** — five H2 display names and tokens, first-token matching, closed schema (unknown H2s blocking), the `jira/<NN>-<step_slug>.md` path convention, prose-gate audience split, no `Step.detail` pointer → `DETAIL_FORMAT.md` only.
- **Export behavior** (`--grade jira` grounding, aggregated pre-backend failure, detail links, append-refresh churn, single output path, `direct-jira` default) → `JIRA_FORMAT.md` only.
- **Authoring flow** (mode bundle, bypassed machinery, checkpoint namespace, skipped tail) → `docs/DETAIL_FLOW.md` only.
- **Run gates** (axis split, preflight + deep gate, dry-run ordering, skipped helpers, resume/log propagation) → `docs/RUN_FLOW.md` only.
- **Audit grounding** (report-only shape, rejected flags, sidecar suppression, bare/mislabeled treatment, provenance block) → `docs/AUDIT_FLOW.md` only.
- **Serialized payload keys** (the `detail_grade` key in the `completeness-audit --json` payload) → `DATA_CONTRACT.md` only; `docs/AUDIT_FLOW.md` describes the behavior, never the payload table.
- **Surface catalog and when-to-use guidance** → `CAPABILITIES.md` (which commands carry the grade lane) and `USE_CASES.md` (when to reach for it) — both cross-link, never restate the contract.
- **Rollout status and scope decisions** → `BACKLOG.md` only. Keep entry numbers (#164, #149, #169, #171) inside `BACKLOG.md`; the reference docs describe shipped behavior without citing backlog ids, except that `docs/AUDIT_FLOW.md` may note the grade-marker sidecar decision is tracked in `BACKLOG.md` (no number needed).

Acceptance below makes this grep-checkable: the token list `Intent / Change / Constraints / Done when / Out of scope` appears as a contract listing in exactly one of the edited docs.

### `DETAIL_FORMAT.md`

- Add a **"Grades"** (or similar) section after the run-grade section schema: the run-grade seven-section contract is the default; the jira-grade five-section contract is the opt-in compact grade, authored by `plan-tool detail <name> --grade jira`.
- State the enforced-contract split in the source-of-truth callout: run grade → `_REQUIRED_H2_TOKENS` / `parse_detail_response` in `plan_tool/detail.py`; jira grade → the validator in `plan_tool/jira_grade.py` (use the shipped symbol names). Doc-vs-code disagreement: code wins, same as today.
- Cover, in the doc's existing style (schema block + field semantics): the five H2s with one-line semantics each, first-token matching (trailing words free — mirror the existing convention text), the closed-schema rule and why (a run-grade body must fail structurally, not politely), the `jira/` subdirectory path convention and why it is a subdirectory (structurally outside the run-grade orphan sweep, adoption, and renumber migration — one sentence, not the full mechanism), `Step.detail` staying run-grade-only, and the prose gate's audience split (blocking at authoring retry; read-time consumers check structure only, so hand edits never fail export/run on style).
- One consumer line pointing at the three consumers and their docs: `jira --grade jira` (`JIRA_FORMAT.md`), `run --detail-grade jira` (`docs/RUN_FLOW.md`), `completeness-audit --grade jira` (`docs/AUDIT_FLOW.md`).

### `JIRA_FORMAT.md`

- In "What writes them": add that `--grade jira` grounds the export on the jira-grade bundle — prompt bodies, `Plan details` links, and JSON `plan_detail_paths` all point at the `jira/` artifacts — and that a missing or wrong-schema artifact for any step is a hard failure before the backend call, aggregated across all broken steps. Cross-link `DETAIL_FORMAT.md` for the contract.
- Note the two intended behaviors an operator will otherwise report as bugs: the output path is the same regardless of grade (story ids stay stable), and the first `--grade jira` re-export over an existing run-grade export refreshes every non-done ticket's links (intended, not churn to suppress).
- Note `direct-jira` stays on the run-grade default (no grade selector there yet).

### Flow docs

Each gets a compact section (bullets + one flow-diagram touch-up at most), cross-linking `DETAIL_FORMAT.md` for the contract rather than restating it:

- `docs/DETAIL_FLOW.md` — the jira-grade lane shares the per-step loop, invoker seam, retry, dry-run/skip/force mechanics, but swaps the grade bundle: `plan_tool/prompts/detail-jira.md`, the jira-grade response gate (no stub synthesis), the `jira/` target, the distinct checkpoint namespace, and skips the quality/convergence loop, purity/split check, lessons capture, and the CLI completeness tail. Update the TL;DR only if it now over-claims ("every authored step gets a purity self-check" is run-grade-only once the lane exists).
- `docs/RUN_FLOW.md` — `--detail-grade jira` is a second axis, not a mode: `--mode run` and its lifecycle gates are unchanged; the grade selects the `run-jira` prompt and detail source. Document the gate placements in the doc's `[BLOCK]` idiom: the aggregated preflight before the run log (single and `--all`), and the render-time deep gate inside `prompt_build` (so the invoker is unreachable even under `--dry-run`). Note the permissive missing-detail warn/confirm helpers are skipped under the jira grade, and that resume commands and run-log flags carry the grade.
- `docs/AUDIT_FLOW.md` — `completeness-audit --grade jira` grounds every audit surface on the jira bundle under the five-H2 contract: audit-and-report only (`--iterate` and audit reuse rejected up front, purity forced off), the `.md` report saved but no JSON sidecar (so no reuse, no apply walk, no convergence-diagnosis entry for that run), missing artifact → bare-step treatment plus a coverage finding, mislabeled body → blocking finding with the body never embedded, the report's grounding line + artifact→digest provenance block, and that the report's next steps name no apply or iterate verb for this grade because there is no sidecar to walk — jira-grade gaps are read and fixed by hand.

### `BACKLOG.md` (fenced edits)

- **#164** — append/replace the Status tail: stage 01 (`jira-grade-01-detail-instrument`) shipped the instrument — both grades authorable, selectable, consumable (`jira`, `run`), and auditable at their own grade, run-grade still default and canonical — and evaluation remains pending on stage 03's quality ledger, which now owns the mechanism question end to end (stage 01 ships no evidence and makes no claim about churn). Keep the existing "Remove this entry only after the ledger stage ships" rule.
- **#149** — perform the promised re-scope in the entry body, not just the Status note: the compact authoring-schema layer must **alias** `plan_tool/jira_grade.py`'s tokens (dual-token read compatibility, no second token set); the read-only `--summary` review-card layer is unchanged; the WIP plan's schema steps need re-baselining against the alias contract before execution. Fold the 2026-07-22 decision note into the re-scoped What/Approach so the entry reads as its current scope, not as history plus a pending amendment.
- **Fence:** this step's `BACKLOG.md` diff touches only the #164 and #149 entries plus the one new renumber-staleness entry it files. #167 is unchanged by this diff; #169's stage-01 pointer and any #171 direction question are this step's to edit.

### `CLAUDE.md`

- Update the reference-docs bullet for `DETAIL_FORMAT.md` from "the seven-section contract" to name both contracts (e.g. "run-grade seven-section + jira-grade five-section contracts"). If the correctness-gates paragraph's "the `detail` seven-section response gate" now under-describes the gate surface, add a short clause rather than a paragraph — `CLAUDE.md` stays terse and points at the docs.

### Constraints

- **Describe shipped behavior, not the plan.** Every flag spelling, module name, and gate placement comes from the merged code of steps 3–9; re-grep before writing (see the Input verification limit).
- **No production code changes.** If writing the docs surfaces a code defect (a flag named differently than its help text, a gate in the wrong order), report it — file it in `BUG_BACKLOG.md` — rather than smoothing it over in prose.
- **Keep each doc's existing voice and structure**: `DETAIL_FORMAT.md`/`JIRA_FORMAT.md` are schema references with source-of-truth callouts; the flow docs are gate/sequence maps with `[BLOCK]`/`[WARN]` idioms and source maps. Update each doc's source map when new symbols are cited.
- **`docs/cli/` is generated** — if any generated flag-reference page is stale, regenerate with `python -m plan_tool.cli_reference --write`; never hand-edit it. (Steps 4–7 own their regens; this step only verifies no drift remains.)

## Tests

### Verification (non-code step)

This step changes no production code; verification is referential integrity over the edited documents.

- Ownership uniqueness — grep confirms the five jira-grade H2 display names appear as a contract listing in `DETAIL_FORMAT.md` only; the other five edited docs cross-link, not restate.
- Path existence — every backticked repo path in the new prose (`plan_tool/jira_grade.py`, `plan_tool/detail_artifacts.py`, `plan_tool/prompts/detail-jira.md`, `plan_tool/prompts/run-jira.md`, …) exists at HEAD.
- Symbol grounding — every symbol the new prose attributes to a file (validator name, `derive_jira_detail_path`, the checkpoint namespace string, the rejected-flag names) greps to that file.
- Link depth — every relative link resolves at the authoring file's own directory depth: `docs/*.md` → repo-root docs use `../` (e.g. `../DETAIL_FORMAT.md`); root docs → `docs/` use the `docs/` prefix; sibling links stay bare.
- Flag accuracy — every documented flag/value (`--grade jira`, `--detail-grade jira`, rejected combinations) matches `docs/cli/` (regenerated, not hand-edited) and `plan-tool <cmd> --help`.
- Payload accuracy — the `detail_grade` row's described shape and emit condition match what a real `completeness-audit --grade jira --json` run produces, and no other key in the `completeness-audit --json` table changed.
- Backlog fence — the `BACKLOG.md` diff touches only the #164 and #169-adjacent lines inside #164's entry, the #149 entry, and the one new renumber-staleness entry; `git diff` shows #169's stage-01 bullet, #171, and #167 unchanged.
- Existing suite — `uv run pytest tests/ -q` stays green (docs-only diff; the CLI-reference drift guard `tests/cli/test_cli_reference.py` confirms no generated-doc drift).

## Acceptance criteria

- `DETAIL_FORMAT.md` documents both grades: the run-grade schema unchanged, plus a jira-grade section carrying the five H2s, first-token matching, closed-schema rule, `jira/` path convention, `Step.detail` run-grade-only rule, and prose-gate audience split, with `plan_tool/jira_grade.py` named in the source-of-truth callout.
- `JIRA_FORMAT.md` documents `--grade jira`: jira-bundle grounding, aggregated pre-backend hard failure, `jira/` links in both formats, same output path across grades, the intended first-re-export link refresh, and `direct-jira`'s run-grade default.
- `DATA_CONTRACT.md`'s `### completeness-audit --json` table carries a `detail_grade` row naming its meaning and its jira-only emit condition, so the doc's "no JSON key is intentionally undocumented" claim holds; no other row in that table changed.
- Each of `docs/DETAIL_FLOW.md`, `docs/RUN_FLOW.md`, `docs/AUDIT_FLOW.md` documents its command's grade selector with the gates/bypasses listed in Implementation, cross-linking `DETAIL_FORMAT.md` for the contract.
- Grep for the five H2 display names as a listed contract matches exactly one of the edited docs (`DETAIL_FORMAT.md`) — the enforcing code/prompt homes (`plan_tool/jira_grade.py`, `plan_tool/prompts/detail-jira.md`) necessarily carry the list too and are out of this grep's scope.
- `CAPABILITIES.md`'s `detail`/`jira`/`run`/`completeness-audit` entries name the opt-in grade lane and `plan-tool validate`'s catalog check stays green.
- `USE_CASES.md` carries the jira-grade when-to-reach-for-it guidance, cross-linking `DETAIL_FORMAT.md` rather than restating the contract.
- `BACKLOG.md` contains the new renumber-staleness entry alongside the #164/#149 edits.
- `BACKLOG.md` #164's Status states instrument-shipped (stage 01) / evaluation-pending (stage 03 ledger) and retains the remove-only-after-ledger rule; #149's body requires the authoring-schema layer to alias the jira-grade tokens and leaves the `--summary` layer unchanged.
- The `BACKLOG.md` diff contains no hunks inside the #169, #171, or #167 entries.
- `CLAUDE.md`'s `DETAIL_FORMAT.md` reference bullet names both grade contracts.
- Every backticked path and attributed symbol in the new prose passes the grep checks above; every relative link resolves.
- `uv run pytest tests/ -q` passes with no test-file edits.

## References

- [CommonMark Spec 0.30 — ATX headings](https://spec.commonmark.org/0.30/) — the heading syntax ground truth behind the required-H2 matching rule `DETAIL_FORMAT.md`'s jira-grade section documents.

## Deferred

- Registering a grade selector for `direct-jira`/`direct-run` — a separate unattended-pipeline decision; step 5 routed it to `BACKLOG.md`. This step only documents the current run-grade default.
- The grade-marker field for the completeness JSON **sidecar** (a persisted-schema change plus consumer filters) — routed to `BACKLOG.md` by step 9; `docs/AUDIT_FLOW.md` notes the suppression, not a schema proposal. Distinct from the `detail_grade` row this step adds: that is a non-persisted CLI-payload key step 9 already ships, so documenting it records shipped behavior rather than proposing a schema.
- Re-baselining #149's WIP plan (`docs/implementation-plans/2-detail-verbosity-compact-summary.md`) against the alias contract — the re-scoped entry instructs it; executing that re-baseline is #149's own work, not this step's.
- Removing the #164 entry — happens only after stage 03's ledger ships, per the entry's own rule.
- Renumber-staleness of unpointed `jira/` artifacts after a split — step 3 deferred this loud gap to reconcile once a real corpus exists; the docs may note it as a known limit but this step ships no fix.
