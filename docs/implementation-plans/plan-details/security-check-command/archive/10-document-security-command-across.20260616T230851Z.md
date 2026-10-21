# Step 10 — Document the `plan-tool security` command across operator docs and flow docs

## Summary

This **non-code** step documents the new plan-wide `plan-tool security` verb that steps 1–9 deliver, across nine markdown surfaces: the two operator docs (`RUNBOOK.md`, `README.md`), the two integration skills (`integrations/claude/SKILL.md`, `integrations/codex/SKILL.md`), `CLAUDE.md`, `BACKLOG.md`, and the three flow docs (`docs/AUDIT_FLOW.md`, `docs/RESUME_FLOW.md`, `docs/AUDIT_RESUME_FLOW.md`). The load-bearing decision: `security` is documented as a **standalone cross-target auditor** that spans the existing plan-audit (3) and code-audit (4) families — not as a new numbered family, not as a dimension inside `completeness`, and not as a replacement for the per-step `run --mode security` path, which is unchanged. `completeness` and `detail` only **point at** the verb via a relevance-gated next-step suggestion (steps 5–6); neither runs a Claude security pass, renders a Security section, or emits a `security` JSON bucket. The single recurring claim — the **verb is plan-wide, the `--mode` is per-step** — is single-sourced verbatim at every surface where either appears. On green, `grep -q 'plan-tool security' RUNBOOK.md` passes (the step gate), every new internal anchor link resolves, and no surface implies the per-step security mode was removed or that `completeness` runs a security pass.

## Table of Contents

- [Why](#why) — what's undocumented today and why it lands now
- [Files (creates vs edits)](#files-creates-vs-edits) — the nine doc surfaces and their named slots
- [Implementation](#implementation) — per-file slot-by-slot edits and the single-sourced disambiguation
- [Tests](#tests) — there are none; see Verification
- [Acceptance criteria](#acceptance-criteria) — checkable doc-state behaviors on green
- [References](#references) — argparse + OWASP grounding carried from the plan
- [Deferred](#deferred) — out-of-scope surfaces and follow-ups

## Why

- **The `security` verb is fully built by steps 1–9 but invisible to operators.** Steps 1–3 land `plan_tool/cli/security_cmd.py` (the `plan-tool security --target plan|code <name>` / `--reconcile` / `--fail-on-findings` verb), step 4 lands the `security-reconcile` direction, steps 5–6 land the relevance-gated next-step pointer (and its `--no-security-hint` suppression), and steps 7–9 land the auto-apply allowlist and the `security --iterate` apply loop. None of that appears in `RUNBOOK.md`, `README.md`, the skills, or the flow docs, so an operator has no way to discover the command, its pointer, or its reuse posture.
- **The new plan-wide verb is trivially confused with the existing per-step `--mode security`.** `run <name> --mode security` and `verify-all <name> --mode security` already exist and audit one step (or sweep done steps) via `plan_tool/prompts/security.md`. Without an explicit, repeated contrast, a reader lands on whichever surface mentions the mode and concludes the new verb is a redundant alias.
- **The flow docs assert caching/iteration invariants the security command must not silently break.** `docs/RESUME_FLOW.md` names exactly **four** iterative entry points and states only `create`/`detail` write checkpoints; `docs/AUDIT_RESUME_FLOW.md` documents the fingerprint-gated sidecar-reuse posture. `security` has its own opt-in `--iterate` apply loop and its own `<ts>-security-<target>.json` fingerprint-gated reuse — it must be placed on the reuse side without misstating the iteration-session set.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `RUNBOOK.md` — add a **Quick reference** row, a **Table of contents** line, a dedicated `## Workflow: plan-wide security audit` section, a note in `## Command families and ordering`, and a row in the `## Mutating vs. read-only modes` table.
- `README.md` — add a `plan-tool security` block under `## CLI usage`, a `## Table of contents` entry, an append on the `<name>` row of the `### Placeholders` table, and a sentence in `## Modes`. Document the relevance-gated next-step pointer emitted at the end of `detail`/`completeness` and the `--no-security-hint` flag.
- `CLAUDE.md` — add one line under the `Pipeline:` line in `## What this is`, and one clause in the `## Architecture` **Correctness gates** paragraph naming the plan-wide `security` auditor.
- `integrations/claude/SKILL.md` — extend the frontmatter `description`, add a row to the **Subcommands at a glance** table, and add a **Decision tree for common user asks** row.
- `integrations/codex/SKILL.md` — the identical edits as the claude skill (the two files mirror; keep them byte-parallel except the codex backend framing).
- `BACKLOG.md` — **verify-only no-op** at HEAD: grep for a security-check entry; none exists (see Implementation), so make no edit and surface the title/reality gap rather than invent one.
- `docs/AUDIT_FLOW.md` — note the standalone `plan-tool security` verb as an audit sibling and add `## Source map` rows.
- `docs/RESUME_FLOW.md` — extend the checkpoint-contract paragraph to place `security` on the fingerprint-reuse side, keeping the "four iterative entry points" count unchanged (a load-bearing non-edit).
- `docs/AUDIT_RESUME_FLOW.md` — add a security paragraph to `## What's reused vs re-derived` and `## Source map` rows.

## Implementation

### The single-sourced disambiguation (drop verbatim at every surface)

Write **one canonical sentence** and reuse it byte-for-byte wherever either the verb or the mode appears (`RUNBOOK.md` workflow + families + mutating-modes, `README.md` Modes, both `SKILL.md` decision trees):

> `plan-tool security <name>` audits the **whole plan** (`--target plan`) or all changed code (`--target code`) in one report; `run <name> --mode security` / `verify-all <name> --mode security` audit a **single step** (or sweep done steps) via `prompts/security.md`. The verb is plan-wide; the `--mode` is per-step — the per-step mode is unchanged.

Single-sourcing the wording stops the framing from drifting between surfaces (one saying "replaces", another "supplements").

### The command surface to document (from the sibling detail files — do not re-derive)

- **`plan-tool security --target plan <name>`** — audits the plan body/decomposition for security gaps; prints severity-labeled findings; **exits 0 even with CRITICAL findings** (the exit-code convention — pass `--fail-on-findings` to flip the rc).
- **`plan-tool security --target code <name> --step <id>`** — audits that step's changed code via `plan_tool/prompts/security.md`; reuses a saved `<ts>-security-code.json` report when the plan **and** code fingerprints are unchanged. (`--target code` requires `--step`.)
- **`plan-tool security --reconcile <name>`** — reports drift between the plan's stated security intent and the code's actual posture (the `security-reconcile` direction from step 4).
- **`plan-tool security --iterate <name>`** — runs the opt-in audit→apply→re-audit convergence loop (steps 8–9): an allowlisted `hardcoded-secret` finding is applied via `apply_finding`; every other security finding stays advisory/deferred and is reported, not applied. Without `--iterate` the command is a one-shot audit that applies nothing.
- **Positional is `<name>`, never `<path>`.** Per step 3, `cmd_security` resolves the registered plan via `resolve_plan_for_context` — document it on the `<name>` placeholder row in `README.md`, identically to `status` / `completeness`, **not** the `<path>` row used by `create --from-existing`.
- **Relevance-gated next-step pointer (steps 5–6) — NOT a completeness dimension.** At the end of `plan-tool detail <name>` and `plan-tool completeness <name>`, a one-line `→ plan-tool security --target plan <name>` suggestion (and `--reconcile` when code exists) is printed **when the cheap keyword relevance gate fires** (the plan touches security-relevant surface) and is absent on a non-relevant plan or when `--no-security-hint` is passed. `completeness` does **not** call `run_security_audit`, does **not** render a `### Security` section, and does **not** emit a `checks.security` JSON bucket — security stays a standalone command the pointer advertises. Document the pointer as a discoverability nudge that spends no Claude either way, not as an embedded audit pass.

### `RUNBOOK.md`

- **`## Quick reference`** — add a row to the **Plan audit** or a new minimal grouping: `| `plan-tool security <name> --target plan\|code` | Plan-wide / code security audit (severity-labeled findings) |`. Keep niche flags out of the table per the section's stated convention.
- **`## Table of contents`** — add `- [Workflow: plan-wide security audit](#workflow-plan-wide-security-audit)` in pipeline-adjacent order (after the reconcile/completeness workflow entries).
- **`## Workflow: plan-wide security audit`** (new `##` section) — one bullet per flag (`--target plan`, `--target code --step <id>`, `--reconcile`, `--iterate`, `--fail-on-findings`), the `<ts>-security-<target>.json` reuse-when-fresh behavior (the per-target suffix scopes reuse so a plan audit never replays a code report), the exit-0-with-CRITICAL note (cross-link the exit convention), and the single-sourced disambiguation sentence. Note that `detail`/`completeness` advertise the verb via a relevance-gated next-step pointer suppressible with `--no-security-hint`.
- **`## Command families and ordering`** — add a sentence noting `security` is a **cross-target auditor spanning plan audit (3) and code audit (4)** (`--target plan` reads like family 3, `--target code` like family 4, `--reconcile` straddles), with no new family number — mirror how the prose already treats reconcile as straddling 3 and 4.
- **`## Mutating vs. read-only modes`** — the existing table already lists `security` as a non-mutating **mode**; add a sentence below it clarifying that the plan-wide `plan-tool security` **verb** is likewise read-only by default (edits neither plan nor code on `--target plan|code`; `--iterate` applies only allowlisted findings; `--reconcile` follows the reconcile direction-of-truth rules), and reuse the disambiguation sentence.

### `README.md`

- **`## CLI usage`** — add under an Audit grouping: `plan-tool security <name> [--target plan|code] [--step <id>] [--reconcile] [--iterate] [--fail-on-findings]`. Add `[--no-security-hint]` to the existing `detail` and `completeness` usage lines (the flag that suppresses the next-step pointer).
- **`## Table of contents`** — no new top-level section is required; only add an entry if a dedicated `## Security audit` heading is introduced (not required — fold the prose into the existing Modes section to keep the ToC stable).
- **`### Placeholders`** — append `security` to the **`<name>`** row's "Where it appears" list (it audits an existing registered plan). Do **not** touch the `<path>` row.
- **`## Modes`** — under the read-only-modes bullet, append the single-sourced disambiguation sentence so a reader of the `security` mode learns the plan-wide verb exists. Add a sentence noting that `detail` and `completeness` print a relevance-gated `→ plan-tool security` next-step pointer (suppressible with `--no-security-hint`), and that `completeness` itself runs **no** security pass and emits **no** security section or JSON bucket.

### `CLAUDE.md`

- **`## What this is`** — after the `Pipeline:` line, add one terse line: a plan-wide `security` audit verb (`--target plan|code`, `--reconcile`, `--iterate`) sits beside the audit phase; `detail`/`completeness` advertise it via a relevance-gated next-step pointer rather than running it inline.
- **`## Architecture` (Correctness gates paragraph)** — add a clause naming `plan_tool/security_audit.py:run_security_audit` as the plan-wide security auditor, distinct from the per-step `--mode security` path. Keep it one clause — depth lives in `README.md` / the flow docs.

### `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md`

- **Frontmatter `description`** — extend the audit verb list to name plan-wide security: `… audit (validate / reconcile-plan / completeness / security / verify-all) …`. The `argument-hint` already carries `--mode … security …`; leave it (the per-step mode is unchanged) — add `--target plan|code` only if a top-level `security` hint is wanted; not required for the gate.
- **Subcommands at a glance** table — add a row under the audit grouping: `**Audit · security** (plan↔code) | `security <name> --target plan\|code`, `security <name> --reconcile` | Yes`.
- **Decision tree for common user asks** — add `| "security-audit the whole plan / changed code" | `plan-tool security X --target plan\|code` |` and keep the existing `--mode security` row, appending the disambiguation so the two rows read as distinct (verb vs per-step mode).
- **Keep the two skill files byte-parallel** except the codex-specific backend framing already present (`codex exec` subprocess wording). Make the same slot edits in both.

### `BACKLOG.md` (verify-only no-op at HEAD)

- **There is no security-check entry in `BACKLOG.md` at HEAD.** The feature was seeded from `plan-seeds/security-check-command.md` (now archived), not from a backlog entry — `grep -in security BACKLOG.md` returns nothing. The step title's "flip BACKLOG status" therefore has **no target**.
- **Do not invent an entry.** Run `grep -in 'security' BACKLOG.md` first; if a `**Status:**`-bearing entry exists at implementation time, flip it to shipped (and note that `BACKLOG.md`'s own `## Purpose` argues for *removing* a shipped entry — surface that tension explicitly rather than silently choosing). If none exists (the HEAD reality), the `BACKLOG.md` edit is a confirmed no-op.
- **Surface the title-vs-reality gap, don't mutate plan frontmatter.** This is a doc step; routing the discrepancy to a reconcile finding (the title names a BACKLOG flip the file can't satisfy) keeps the choice visible to a reviewer.

### `docs/AUDIT_FLOW.md`

- **Standalone verb, not a lifecycle phase** — note the `plan-tool security` verb in one sentence as a sibling audit verb spanning plan-audit and code-audit, with a pointer to `RUNBOOK.md`. AUDIT_FLOW maps the lifecycle audit verbs; `completeness` runs **no** security pass, so do **not** add a security dimension/section/bucket to the completeness flow description.
- **`## Source map`** — add rows: `Security audit orchestrator` → `plan_tool/security_audit.py` (`run_security_audit`); `Security-report reuse verdict` → `plan_tool/security_audit.py` (`resolve_reusable_security`, `ReusableSecurity`); `Security next-step pointer` → `plan_tool/cli/authoring.py` (`cmd_detail`) and `plan_tool/cli/completeness_phases.py` (`_persist_and_present_report`).

### `docs/RESUME_FLOW.md`

- **`## The checkpoint contract`** — extend the "Only `create` and `detail` write checkpoints; `completeness`/`reconcile` do not" paragraph: add `security` to the **fingerprint-reuse** side — its default path is single-pass (no checkpoints), and it reuses its `<ts>-security-<target>.json` sidecar gated on the saved plan **AND** code fingerprints matching disk, with a pointer to `AUDIT_RESUME_FLOW.md`.
- **Load-bearing non-edit:** leave the **"All four iterative entry points"** list in `## The iteration session` at four (`create_plan`, `generate_detail`, `cmd_completeness`, `_iterate_reconcile_loop`). The `security --iterate` apply loop (step 8) has its own loop on `cmd_security` and is **not** an `iteration_session` wrapper, so adding it would misstate the iteration set. State this absence explicitly in the prose so a later reader doesn't "fix" the count.

### `docs/AUDIT_RESUME_FLOW.md`

- **`## What's reused vs re-derived`** — add a security paragraph: `plan-tool security` reuse is **single-axis** (one save = one `--target`, one source, encoded in the `-security-<target>.json` filename suffix so a plan audit never replays a code report) and is gated by `plan_tool/security_audit.py:resolve_reusable_security` recomputing `compute_plan_fingerprint` (`review_persistence.py`) and `compute_code_fingerprint` (`plan_tool/fingerprint.py`). Document the reuse posture: the standalone `security` verb on the code/reconcile targets is `fresh` only when *both* fingerprints match, while a `target="plan"` save verdicts fresh on an unchanged plan fingerprint alone (per step 2). `completeness` does **not** participate in security reuse — it runs no security pass.
- **`## Source map`** — add rows: `Security-report reuse verdict` → `plan_tool/security_audit.py` (`resolve_reusable_security`, `ReusableSecurity`); `Security sidecar` → `<ts>-security-<target>.json` via `plan_tool/review_persistence.py` (`save_review(kind="security-<target>")`).
- **Correct the stale neighbor while here** — the pre-existing "Plan / code fingerprints" row (around line 104) cites `completeness_report.py` for `compute_code_fingerprint`; fix it to `plan_tool/fingerprint.py` for consistency with `AUDIT_FLOW.md:221`, so the new security row isn't left correct beside a stale neighbor.

## Tests

This step writes no code and no test files.

### Verification (non-code step)

Verify the doc artifacts directly — config/link/accuracy checks, not unit tests; no test-ordering directive applies:

- **Step gate passes** — `grep -q 'plan-tool security' RUNBOOK.md` exits 0.
- **Verb is documented in every operator surface** — `grep -l 'plan-tool security' RUNBOOK.md README.md CLAUDE.md integrations/claude/SKILL.md integrations/codex/SKILL.md` lists all five.
- **Disambiguation sentence is present at each verb/mode surface** — `grep -rn 'verb is plan-wide' RUNBOOK.md README.md integrations/claude/SKILL.md integrations/codex/SKILL.md` returns the byte-identical sentence at each.
- **New internal anchors resolve** — the `RUNBOOK.md` ToC link `#workflow-plan-wide-security-audit` matches the new `## Workflow: plan-wide security audit` heading slug; cross-links to `AUDIT_RESUME_FLOW.md` / `RESUME_FLOW.md` resolve.
- **Per-step `--mode security` is preserved, not removed** — the `RUNBOOK.md` `## Mutating vs. read-only modes` table still lists `security` and `README.md` `## Modes` still lists `security` among read-only modes.
- **No completeness-security claim** — no surface states that `completeness` runs a security Claude pass, renders a `### Security` section, or emits a `checks.security` JSON bucket; `completeness`/`detail` only advertise the verb via the relevance-gated next-step pointer (suppressible with `--no-security-hint`).
- **Iteration-session count unchanged** — `docs/RESUME_FLOW.md` still names exactly four iterative entry points; `security` is described as reuse-side, not added to that list.
- **Skill files stay parallel** — a diff of the two `SKILL.md` files shows only the pre-existing backend-framing differences, no divergence in the new security rows.
- **BACKLOG verified** — `grep -in security BACKLOG.md` confirms the no-op (no entry to flip at HEAD); the discrepancy is surfaced, not papered over.

## Acceptance criteria

- `grep -q 'plan-tool security' RUNBOOK.md` exits 0 (the step gate).
- `RUNBOOK.md` contains a `## Workflow: plan-wide security audit` section with one bullet per `security` flag and the disambiguation sentence; its ToC entry links to the matching anchor.
- `README.md`'s `### Placeholders` `<name>` row lists `security`; the `<path>` row does not.
- `README.md` documents the relevance-gated `→ plan-tool security` next-step pointer at the end of `detail`/`completeness` and the `--no-security-hint` suppression flag, and states that `completeness` runs no security pass and emits no security section or JSON bucket.
- Both `SKILL.md` files name `security` in the frontmatter `description`, the Subcommands-at-a-glance table, and the decision tree; a diff shows no non-backend divergence.
- `docs/AUDIT_FLOW.md`, `docs/RESUME_FLOW.md`, and `docs/AUDIT_RESUME_FLOW.md` each reference the standalone security verb with the symbols `run_security_audit`, `resolve_reusable_security`, and the `<ts>-security-<target>.json` sidecar.
- `docs/RESUME_FLOW.md` still lists exactly four `iteration_session` entry points; `security` appears only on the reuse side.
- No surface states or implies the per-step `--mode security` path was removed, and no surface describes a `completeness-audit --with-security` dimension, `### Security` section, or `checks.security` bucket.
- `BACKLOG.md` is unchanged (no security entry exists at HEAD) and the detail records the title-vs-reality no-op.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — confirms the `--target` / `--reconcile` / `--iterate` / `--fail-on-findings` / `--no-security-hint` flag spellings the docs describe match step 3/6/8's argparse registration.
- [OWASP Top 10 (2021)](https://owasp.org/Top10/2021/) — the risk taxonomy to reference when describing what `plan-tool security --target plan` audits (missing authz, secrets in the plan body, unsafe data flows), so the doc prose stays grounded.
- [CWE — Common Weakness Enumeration (MITRE)](https://cwe.mitre.org/) — the weakness catalog the severity-labeled findings cross-reference, worth a one-line mention where the docs explain finding labels.

## Deferred

- **`PLAN_FORMAT.md` and `docs/CODEX_CLI_CONTRACT.md`** — out of this step's `files:`; `security` adds no frontmatter field and no backend-contract change, so neither needs editing.
- **`TESTING.md` seam row for `security_audit.py`** — already owned by step 1's footprint; not re-touched here.
- **A dedicated `docs/SECURITY_FLOW.md`** — the verb is documented inline across the existing flow docs; minting a new per-flow diagram doc is a follow-up if the security surface grows.
- **In-report completeness security dimension** — decided against in the plan body (`## Deferred`); security is a standalone command surfaced via the next-step pointer, never a `completeness` dimension/section/bucket. Revisiting an embedded dimension is a possible future refinement, explicitly out of scope here.
- **Removing a shipped `BACKLOG.md` entry per its `## Purpose` convention** — moot at HEAD (no entry exists); if a future entry is added before this lands, the remove-vs-flip choice is surfaced as a reconcile finding, not silently decided here.
- **`README.md` Decision-flow table row** — deliberately not added; that table is scoped to `create` entry points, and `security` is an audit verb, not a create source.
