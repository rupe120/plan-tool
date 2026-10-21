# Step 10 — Document the plan-wide `security` command across operator docs and flow docs; reconcile its BACKLOG status

## Summary

Documents the now-shipped plan-wide `plan-tool security` verb (steps 1–9) everywhere a reader looks for it, and reconciles its `BACKLOG.md` status. The load-bearing decision: every doc edit must draw a hard line between the **plan-wide `security` subcommand** (`plan-tool security <name> --target {plan,code}` / `--reconcile` / `--iterate`, this plan's deliverable) and the pre-existing **per-step `--mode security` review** (`run`/`verify-all --mode security`), which is untouched — conflating the two is the single most likely documentation error. Primary surfaces: `RUNBOOK.md` (quick-reference row + a new workflow section + TOC entry), `README.md` (CLI-usage block + Modes clarification + a Common-workflows subsection), `CLAUDE.md` (architecture pointer), both `integrations/*/SKILL.md` (description audit list + decision-tree row + at-a-glance table), and the three flow docs (`docs/how-to/pipeline/audit.md`, `docs/how-to/recovery/README.md`, `docs/how-to/recovery/audit.md`). On green, `grep -i 'plan-tool security' RUNBOOK.md README.md` and `grep -q 'hardcoded-secret' RUNBOOK.md` both pass, every cited code symbol still exists at HEAD, and no doc claims the plan-wide verb is a `--mode`.

## Table of Contents

- [Why](#why) — why the command needs documenting now and what the BACKLOG reconcile means
- [Files (creates vs edits)](#files-creates-vs-edits) — the nine doc surfaces, edits only
- [Implementation](#implementation) — per-file edits, the symbols to cite, and the per-step-vs-plan-wide distinction
- [Tests](#tests) — verification appropriate to a docs-only step
- [Acceptance criteria](#acceptance-criteria) — grep-checkable behaviors on green
- [References](#references) — argparse / OWASP grounding carried from the plan
- [Deferred](#deferred) — out-of-scope hygiene (findings-stub migration, doc consolidation)

## Why

- **The `plan-tool security` verb is discoverable only by reading `--help`.** Steps 1–9 land the orchestrator (`plan_tool/security_audit.py`), the CLI verb (`plan_tool/cli/security_cmd.py`), persistence/reuse, the `--reconcile` target, the relevance-gated next-step pointer, and the `hardcoded-secret` auto-apply channel — but no operator doc, SKILL router, or flow diagram mentions it. A developer who just ran `detail` or `completeness-audit` and saw the `plan-tool security --target plan <name>` pointer has nowhere to read what it does.
- **The per-step `--mode security` review already documented in every doc invites confusion.** `RUNBOOK.md`, `README.md`, and both SKILLs already describe `run`/`verify-all --mode security` (a single step's detail/files audit). The new verb is **plan-wide** for `--target plan` (audits the whole plan's design); `--target code --step N` audits a single step's code (requires `--step`). Each surface must distinguish them explicitly or readers will assume `plan-tool security` is just an alias for `--mode security`.
- **`depends_on: 3,4,5,6,8,9`** — this step documents the *complete* surface (CLI flags, the pointer, `--iterate` auto-apply, reuse), so it runs last. It changes **no production code**. **This is a terminal docs step — run it only after 3,4,5,6,8,9 are merged.** The Tests cited-symbol-freshness check and the load-bearing distinction both lean on those symbols existing at HEAD; running step 10 standalone (outside the `depends_on` run order) stalls on the grep gate. Non-blocking — the gate fails safe.
- **"Reconcile BACKLOG status" is a title claim to verify, not a directive to follow blindly.** At HEAD no section-A candidate entry for the plan-wide security command exists in `BACKLOG.md` (grep the `**#` titles for `security` — only #50/#51's *origin* lines and section-D process notes match). Treat the edit as conditional: if a tracking entry (or a `Status:` line citing `2-security-check-command`) exists at implementation time, flip/remove it per BACKLOG's "Remove a feature's entry when it ships" rule; otherwise record the no-op explicitly. The spun-off entries **#50** and **#51** (origin "regenerating `2-security-check-command` detail") are independent forward work and **stay**.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `RUNBOOK.md` — add a **Security audit** row group to the **Quick reference** section (after the **Plan audit** group); add a `## Workflow: plan-wide security audit (plan-tool security)` section and its **Table of contents** entry; add a one-line "distinct from `--mode security`" cross-reference where the per-step mode is listed (the `verify-all --mode <m>` mode list and the mutating-vs-read-only mode table).
- `README.md` — add the `plan-tool security …` invocation to the **CLI usage** block; clarify the **Modes** section's `security` bullet (per-step) vs the plan-wide verb; add `security` to the **Placeholders** `<name>`-consumers row; add a **Common workflows** subsection for the plan-wide audit.
- `CLAUDE.md` — add a one-line architecture pointer naming `plan_tool/security_audit.py` + `plan_tool/cli/security_cmd.py` and the `convergence.py` auto-apply allowlist; note the relevance-gated pointer + `--no-security-hint`.
- `integrations/claude/SKILL.md` — add `security` to the frontmatter `description:` audit list; add a decision-tree row; add a `security <name>` row to **Subcommands at a glance**.
- `integrations/codex/SKILL.md` — same three edits as the claude SKILL (keep the two files in lockstep; only the backend-specific prose differs).
- `BACKLOG.md` — reconcile the security command's status per the conditional rule in [Why](#why) (verify-then-remove/flip; no-op if absent).
- `docs/how-to/pipeline/audit.md` — add a note that `security` is a **separate plan-level audit verb** (not part of the `completeness → reconcile` spine) that `detail`/`completeness-audit` advertise via the relevance-gated pointer.
- `docs/how-to/recovery/README.md` — extend the iterative-entry-points list to account for the `security --iterate` loop (`plan_tool/cli/security_cmd.py:_run_security_iterate_loop`) and its `iteration_session` posture.
- `docs/how-to/recovery/audit.md` — add a one-line note on the security command's fingerprint-gated reuse (`plan_tool/security_audit.py:resolve_reusable_security`, target-scoped `-security-<target>.json` sidecar).

## Implementation

**Before writing any doc edit, grep each cited code symbol against HEAD.** This is a docs step citing live symbols (steps 1–9 land them); a renamed flag or helper ships a stale anchor. Confirm at minimum: the `plan-tool security` subparser flags (`--target` choices `{plan,code}`, `--reconcile`, `--fail-on-findings`, `--iterate`/`--max-iterations`/`--iteration-budget`/`--max-stall-rounds`), `--no-security-hint` on `plan_tool/cli/parser.py:make_base_parser`, `plan_tool/security_audit.py:run_security_audit` / `resolve_reusable_security`, `plan_tool/cli/security_cmd.py:cmd_security` / `_run_security_iterate_loop`, and `plan_tool/convergence.py:SECURITY_AUTO_APPLY_ALLOWLIST` (seeded `{"hardcoded-secret"}` by step 9).

### The load-bearing distinction every surface must encode

- **Plan-wide `security` subcommand** — `plan-tool security <name> --target plan` audits the plan's *design* for security gaps; `--target code --step N` audits a single step's code (requires `--step`; omitting it returns rc 2); `--reconcile` audits plan⇆code security drift. Persists a fingerprinted `<ts>-security-<target>.json` sidecar; honors `--fail-on-findings` and the exit-code convention (a completed audit exits 0 even with CRITICAL findings — the [[feedback_exit_code_convention]] rule). Under `--iterate` (opt-in, **default off** — like `run`, the opposite of `completeness`'s default-on), it mechanically applies only `hardcoded-secret`-category findings via `plan_tool/launcher.py:apply_finding` and re-audits; every other category stays advisory.
- **Per-step `--mode security` review** — `run <name> --mode security` / `verify-all <name> --mode security` audits **one step's** detail/files via `plan_tool/prompts/security.md`. Read-only, never advances plan state. **Unchanged by this plan.**
- **State both in one place per doc.** Don't let the plan-wide verb and the `--mode` collide silently in any table.

### `RUNBOOK.md`

- **Quick reference** — add a `**Security audit**` group immediately after the **Plan audit** group's table:
  - `plan-tool security <name> --target plan` → Audit the plan's design for security gaps (OWASP/CWE-grounded).
  - `plan-tool security <name> --target code --step <id>` → Audit a single step's code for security gaps (`--step` required).
  - `plan-tool security <name> --reconcile` → Audit plan⇆code security drift.
  - `plan-tool security <name> --target plan --iterate` → Converge: auto-apply `hardcoded-secret` findings, re-audit (every other finding advisory).
- **Table of contents** — add `- [Workflow: plan-wide security audit](#workflow-plan-wide-security-audit-plan-tool-security)` in pipeline order (after the completeness-checks workflow).
- **New workflow section** `## Workflow: plan-wide security audit (plan-tool security)` — cover: when to run it (after `detail`/`completeness-audit`, before `run`/`jira`; the relevance-gated pointer advertises it); the three targets; the `<ts>-security-<target>.json` sidecar + fingerprint reuse; `--fail-on-findings` + exit-code convention; `--iterate` auto-apply scoped to `hardcoded-secret`; one explicit sentence that this is **plan-wide**, distinct from `--mode security`.
- **`verify-all --mode <m>` mode list** (the `security` — security review. bullet) and the **mutating-vs-read-only mode table** (the `| security | no |` row) — leave the rows intact; add a one-line cross-reference under each pointing to the new workflow ("for a *plan-wide* security audit see [Workflow: plan-wide security audit]").

### `README.md`

- **CLI usage** block — add a line near `completeness-audit` / `verify-all`:
  `plan-tool security <name> [--target plan|code] [--step <id>] [--reconcile] [--fail-on-findings] [--iterate | --no-iterate] [--max-iterations N] [--iteration-budget SECONDS] [--max-stall-rounds N]` (`--step` required with `--target code`)
- **Modes** section — under the **Read-only modes** bullet that lists `security`, append: per-step `security` audits one step; for a plan-wide audit use the `plan-tool security` subcommand (link the new Common-workflows subsection).
- **Placeholders** table — add `security` to the comma list of subcommands that consume `<name>` (the `status`, `validate`, … `detail` row).
- **Common workflows** — add a numbered subsection `### N. security — plan-wide security audit` mirroring the `completeness-audit` / `verify-all` subsections: the three targets, the advisory-vs-auto-apply split, the sidecar, and the exit-code note.
- **Optional:** in the **Core subcommand workflow** narration, note `security` as an auxiliary plan-wide audit that `detail`/`completeness-audit` advertise — keep it off the `create → detail → audit → run/jira` spine ASCII (it is not a pipeline stage).

### `CLAUDE.md`

- **Architecture** — add one bullet (or extend the orchestrators paragraph): the plan-wide `security` verb lives in `plan_tool/cli/security_cmd.py` (thin) over `plan_tool/security_audit.py:run_security_audit` (orchestrator); its `--iterate` auto-apply consults the default-seeded `plan_tool/convergence.py:SECURITY_AUTO_APPLY_ALLOWLIST`; the relevance-gated next-step pointer (suppressible with the global `--no-security-hint`) fires from `detail`/`completeness-audit`.
- Keep it terse (the [[feedback_concise_docs]] rule) — one or two sentences, push depth to README/RUNBOOK.

### `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md`

- **Frontmatter `description:`** — add `security` to the parenthesized audit list (`audit (validate / reconcile-plan / completeness-audit / verify-all / security)`).
- **Decision tree for common user asks** — add a row: `"audit plan X for security gaps" | plan-tool security X --target plan` (and a single-step code-side variant `--target code --step <id>`).
- **Subcommands at a glance** — add `security <name>` to a new **Audit · security** line (Calls claude? Yes); state plan-wide, distinct from `run --mode security`. Honor the table's own **Maintenance note** (the catalog must match `cli/__init__.py`'s docstring + the golden) — but those code-side edits already landed in step 3; this is the doc-table mirror.
- **Lockstep:** apply identical edits to both SKILLs; the only legitimate divergence is the existing backend prose (`claude` subprocess vs `codex exec`). Do **not** touch the `argument-hint:` `--mode …security…` token — it documents the `run` mode, not the subcommand.

### `docs/how-to/pipeline/audit.md`

- Add a short note (TL;DR or a trailing paragraph): `security` is a **separate plan-level audit verb**, not a stage on the `completeness → reconcile` spine; `detail` and `completeness-audit` advertise it via the relevance-gated `plan-tool security --target plan <name>` pointer. Both `completeness`/`reconcile` and `security` edit plan/detail files only (security `--iterate` auto-applies only `hardcoded-secret`), never code.

### `docs/how-to/recovery/README.md`

- The TL;DR / **iteration session** section states **four** iterative entry points wrap their body in `iteration_session` (`create_plan`, `generate_detail`, `cmd_completeness`, `_iterate_reconcile_loop`). **Verify at HEAD** whether `plan_tool/cli/security_cmd.py:_run_security_iterate_loop` wraps `iteration_session` before writing — the loop is built (step 8) to drop the scope-guard/drift/lock machinery (plan/detail-only, no in-run code-drift set). Add a one-line note reflecting the verified state: the `security --iterate` loop is a fifth convergence loop but is **deliberately excluded** from `iteration_session` (no watched-file drift guard); its resume is implicit (plan/detail edits durable on disk, re-audit re-derives). Do not silently bump "four" to "five" without confirming the wrapper status.

### `docs/how-to/recovery/audit.md`

- Add a one-line note paralleling the conceptual-audit reuse: the `security` command reuses a saved `<ts>-security-<target>.json` sidecar via `plan_tool/security_audit.py:resolve_reusable_security` when **both** the plan and code fingerprints (`compute_plan_fingerprint` / `compute_code_fingerprint`) still match, scoped by `--target`; any mismatch re-samples claude.

### `BACKLOG.md`

- Grep for a candidate entry tracking the plan-wide security command (`**#` title containing `security`, or a `Status:` line referencing `2-security-check-command`). Per the conditional in [Why](#why): flip its `Status:` / remove it on ship if present; otherwise leave BACKLOG's section A unchanged and record the no-op in the commit message. Do **not** remove #50/#51.

## Tests

### Verification (non-code step)

This step changes no production code — verify the artifacts, not unit behavior. No test-ordering directive applies.

- `grep -i 'plan-tool security' RUNBOOK.md README.md` — the plan-wide verb appears in both operator docs.
- `grep -q 'hardcoded-secret' RUNBOOK.md` — the auto-apply category is documented (matches step 9's acceptance criterion).
- Cited-symbol freshness — one grep per cited symbol against HEAD: the `security` subparser flags, `--no-security-hint`, `run_security_audit`, `resolve_reusable_security`, `cmd_security`, `_run_security_iterate_loop`, `SECURITY_AUTO_APPLY_ALLOWLIST`. Every cited symbol must exist.
- No-conflation check — `grep -n 'mode security\|--mode security' RUNBOOK.md README.md integrations/*/SKILL.md` lines still describe the **per-step** review only; the plan-wide verb is never called a `--mode`.
- TOC integrity — the new `RUNBOOK.md` workflow heading has a matching Table-of-contents anchor (slug matches the H2).
- Markdown-link resolution — every intra-doc link added (`[Workflow: …](#…)`, README cross-links) resolves to a real anchor.
- SKILL lockstep — the three edited blocks in `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` differ only in backend prose.
- BACKLOG consistency — `grep '\*\*#' BACKLOG.md` shows #50/#51 retained; any security tracking entry handled per the rule.

## Acceptance criteria

- `grep -i 'plan-tool security' RUNBOOK.md` and `... README.md` each return ≥1 line.
- `grep -q 'hardcoded-secret' RUNBOOK.md` exits 0.
- `RUNBOOK.md` has a `## Workflow: plan-wide security audit (plan-tool security)` section with a matching Table-of-contents entry.
- `README.md`'s CLI-usage block contains a `plan-tool security <name>` line with the `--target {plan,code}` / `--reconcile` flags.
- Both `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` list `security` in the frontmatter `description:` audit list and in a decision-tree row.
- No doc describes the plan-wide `security` verb as a `--mode`; the per-step `--mode security` rows remain intact.
- Every code symbol cited in the edits exists at HEAD (per-symbol grep passes).
- `BACKLOG.md` retains entries #50 and #51; any plan-wide-security tracking entry is flipped/removed (or confirmed absent).

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)https: — confirms the exact flag spellings/choices to document for the `security` subparser (`--target`, `--reconcile`, `--fail-on-findings`, the iterate knobs).
- [OWASP Top 10 (2021)https: — the risk taxonomy the plan-level/code prompts emit findings against; ground the workflow prose's "what it checks" in these categories.
- [CWE — Common Weakness Enumeration (MITRE)https: — the weakness catalog (e.g. CWE-798 hardcoded credentials) backing the documented `hardcoded-secret` auto-apply category.

## Deferred

- **Out-of-scope findings-stub migration** — the untracked `docs/implementation-plans/3-out-of-scope-findings-from-2-security-check-command.md` stub should be migrated into `BACKLOG.md`/`BUG_BACKLOG.md` and archived per CLAUDE.md's findings-stub rule. Distinct hygiene task (concerns plan 3's findings, not the documentation of plan 2's command) — route to a separate backlog cleanup, not this step.
- **`docs/how-to/pipeline/run.md` / per-flow diagrams beyond the three in scope** — if the `security --iterate` apply loop warrants its own flow diagram, that is a new doc, not an edit to the three resume/audit flow docs this step touches.
- **Consolidating the three fingerprint-reuse resolvers** in the docs' architecture narration (`resolve_reusable_audit` / `resolve_reusable_reconcile` / `resolve_reusable_security`) — a standing code refactor; document them as they exist, don't pre-describe a merged resolver.
