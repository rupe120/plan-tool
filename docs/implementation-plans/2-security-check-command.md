---
title: Security Check Command
status: planning
priority: medium
steps:
- id: 1
  title: Add security_audit.py orchestrator + plan-level prompt + shell_security_invoker
    seam
  files:
  - TESTING.md
  creates:
  - plan_tool/security_audit.py
  - plan_tool/prompts/security-plan.md
  - tests/test_security_audit.py
  allowed_mentions:
  - plan_tool/prompts/security.md
  complexity: high
  change_type: feature
  gate:
  - uv run python -c "import plan_tool.security_audit"
  detail: docs/implementation-plans/plan-details/security-check-command/01-security-audit-py-orchestrator-plan.md
  status: current
- id: 2
  title: Add resolve_reusable_security + fingerprinted <ts>-security-<target>.json
    persistence (sibling of resolve_reusable_audit); scope reuse by target (plan vs
    code) via the filename suffix as well as fingerprint so a plan-axis caller never
    reuses a code-axis report or vice versa (per-target scoping lands here, not deferred);
    the target="code" axis additionally scopes its lookup by step_id (mirroring the
    reconcile family's per-step _find_saved_for_step, not the whole-plan resolve_reusable_audit
    shape) because the <ts>-security-code.json suffix encodes only the target and not
    the step, so two steps' code audits write same-suffix sidecars and a target-suffix-only
    resolver would serve one step's saved code audit to another step's caller;
    a target="plan" save verdicts fresh on an unchanged plan fingerprint alone — do
    NOT gate plan-target freshness on saved.code_fingerprint_present (that code-fingerprint
    staleness gate from resolve_reusable_audit applies only to the code/reconcile
    targets)
  files:
  - plan_tool/security_audit.py
  - tests/test_security_audit.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/security-check-command/02-resolve-reusable-security-fingerprinted.md
- id: 3
  title: 'Register security subcommand (cli/security_cmd.py: --target plan|code, --reconcile,
    --fail-on-findings) across all five registration seams; reuse-prompt wiring of
    resolve_reusable_security is deferred to a follow-up (see step 3 detail Deferred);
    --target code requires --step (single-step audit), and --step is rejected at
    parse time when combined with --reconcile (usage error, non-zero rc — the reconcile
    direction is whole-plan full-surface, so a single --step is meaningless against it);
    cmd_security renders
    result.skipped_steps alongside the findings so a partial reconcile sweep (step 4)
    is reported as partial, not as a clean pass'
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/__init__.py
  - tests/cli/package_surface_help.golden.txt
  creates:
  - plan_tool/cli/security_cmd.py
  - tests/cli/test_security_cmd.py
  complexity: high
  change_type: feature
  gate:
  - uv run plan-tool security --help >/dev/null
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/security-check-command/03-register-security-subcommand-cli.md
- id: 4
  title: Add a security-reconcile run_auto_reconcile_on_drift hook and
    teach run_security_audit the reconcile target (extend _SECURITY_TARGETS + add
    the dispatch branch) wired to it for plan⇆code security drift, and construct the
    standalone full plan⇄code surface drift scope (every step and its declared files
    in scope) so security --reconcile runs on a tree with no recorded file drift —
    synthesize that whole-plan drifted/file_to_step set via scope_guard.build_file_to_step_map
    over every step's declared files (not the in-run file-drift set), and adapt run_auto_reconcile_on_drift's
    in-memory int / per-step findings output (with its per-step security-reconcile.json
    persistence suppressed so write_security_report is the sole on-disk writer) back
    into a SecurityAuditResult so step 3's cmd_security can render result.findings
    and persist via write_security_report; because the generalized hook's best-effort loop
    skips a launcher-error/non-zero-exit step with only a stderr note, add a skip-count channel
    to run_auto_reconcile_on_drift (a return/out-param counting steps skipped or failed to audit)
    and thread that count into SecurityAuditResult.skipped_steps in the adapter — not the 0 default —
    so a partial sweep is surfaced as partial, not a clean pass. Reconcile reuse keys on resolve_reusable_security(...,
    target="reconcile") — security reuse does NOT key on resolve_reusable_reconcile;
    the reconcile family uses resolve_saved_review in review_persistence
  files:
  - plan_tool/auto_reconcile.py
  - plan_tool/security_audit.py
  - plan_tool/review.py
  - tests/test_auto_reconcile.py
  - tests/test_security_audit.py
  creates:
  - plan_tool/prompts/security-reconcile.md
  allowed_mentions:
  - plan_tool/prompts/detail-reconcile.md
  - plan_tool/prompts/security.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/security-check-command/04-security-reconcile-reconcilekind-run.md
- id: 5
  title: Emit a relevance-gated `plan-tool security` next-step pointer at the end
    of `detail` and `completeness` — NOT a security dimension inside completeness.
    Append a suggestion line via the existing _print_next_steps helper (cli/console.py)
    in cli/authoring.py:cmd_detail (after the existing review/run/jira Next-steps
    block) and in cli/completeness_phases.py:_persist_and_present_report (both the
    --iterate summary path and the audit-only path). Completeness does NOT invoke
    run_security_audit, render a Security section in _render_grouped_report, or add
    a security bucket to _render_completeness_json — security stays a standalone command
    the pointer advertises. Unconditional emission lands here; step 6 adds the relevance
    gate
  files:
  - plan_tool/cli/authoring.py
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_authoring.py
  - tests/cli/test_completeness_cmd.py
  allowed_mentions:
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/security-check-command/05-emit-relevance-gated-plan-tool-security.md
- id: 6
  title: Add a cheap, no-Claude relevance gate (exact-token, not substring, scan of
    plan title + step titles + declared file paths — each declared path first split
    into tokens on the path separators and word boundaries `/`, `_`, `.`, and `-`,
    so e.g. `plan_tool/cli/security_cmd.py` yields tokens {plan, tool, cli, security,
    cmd, py} and the bare path string is never matched whole) that decides whether
    the step-5 next-step pointer is shown, plus a --no-security-hint suppression flag.
    A wrong verdict only shows
    or hides a one-line suggestion (no Claude spend either way), so the gate is low-stakes
    — it gates the pointer, never an audit pass
  files:
  - plan_tool/cli/authoring.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/parser.py
  - plan_tool/security_audit.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/security-check-command/06-cheap-no-claude-relevance-gate-keyword.md
- id: 7
  title: Add a conservative, default-empty security auto-apply allowlist primitive
    (an empty SECURITY_AUTO_APPLY_ALLOWLIST frozenset + is_security_auto_apply_eligible
    pure predicate in convergence.py, plus a security_finding_is_auto_applicable adapter
    in security_audit.py) — inert by default, no loop wiring; the deliberate non-edit
    of review_walk._APPLY_AS_FINDING_SOURCES keeps every security finding advisory
  files:
  - plan_tool/convergence.py
  - plan_tool/security_audit.py
  - tests/test_convergence.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/security-check-command/07-conservative-default-empty-security.md
- id: 8
  title: 'Add an --iterate apply/convergence loop to the `security` command modeled
    on the completeness apply pattern (cli/completeness_cmd.py / completeness_phases.py
    + convergence.py + review_walk.apply_finding): under --iterate, cmd_security runs
    run_security_audit, routes apply-eligible findings through apply_finding, and
    re-audits until convergence — this is the host loop that auto-apply (step 9) plugs
    into. Default OFF (one-shot audit); --iterate opts in. The thin no-loop dispatch
    from step 3 stays the default path. `--iterate` is rejected at parse time when
    combined with `--reconcile` (a usage error, non-zero rc, never dispatching): the
    standalone reconcile sweep''s only named fan-out mitigation is plan+code-fingerprint
    reuse, whose consumer is deferred (resolve_reusable_security ships dormant), so an
    --iterate loop over the reconcile target would re-incur the unbounded per-step
    fan-out on every round — disallow the combination until the reuse short-circuit
    lands'
  files:
  - plan_tool/cli/security_cmd.py
  - plan_tool/cli/parser.py
  - plan_tool/security_audit.py
  - tests/cli/test_security_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 7
  detail: docs/implementation-plans/plan-details/security-check-command/08-iterate-apply-convergence-loop-security.md
- id: 9
  title: 'Deliver security auto-apply end-to-end: emit a [category-slug] from prompts/security-plan.md
    only (the per-step prompts/security.md is left unchanged so the --mode security
    per-step path is preserved), populate a per-finding-unique rec.anchor (the category
    slug composed with a per-body discriminator so same-category findings keep distinct
    ids) in _security_recommendations and key auto-apply on the bare category component,
    not the full id-bearing anchor, seed SECURITY_AUTO_APPLY_ALLOWLIST with hardcoded-secret
    so the step-8 `security --iterate` apply loop (NOT the completeness loop) — which
    filters via apply_eligible_security_findings → security_finding_is_auto_applicable
    and calls apply_finding directly, never should_apply_as_finding — applies for
    real; the security_finding_is_auto_applicable OR-branch (beside the existing review_walk
    source pre-filter) is scoped to that --iterate loop only and is NOT additionally
    wired into the interactive review/reconcile walk — step 4 registers no security kind
    in _RECONCILE_KINDS (security-plan/security-code/security-reconcile are all absent), so no walk loads a security-plan
    sidecar and the only allowlisted category (hardcoded-secret, plan-target only) is
    unreachable from that walk; update RUNBOOK.md to document the now-active allowlist
    and apply-loop wiring (auto-apply is no longer advisory-only) since step 10 documents
    only the inert step-7 primitive'
  files:
  - plan_tool/prompts/security-plan.md
  - plan_tool/security_audit.py
  - plan_tool/cli/security_cmd.py
  - plan_tool/review_walk.py
  - RUNBOOK.md
  - tests/test_security_audit.py
  - tests/cli/test_security_cmd.py
  - tests/test_review_walk.py
  allowed_mentions:
  - plan_tool/prompts/security.md
  - plan_tool/review.py
  complexity: high
  change_type: feature
  depends_on:
  - 7
  - 8
  detail: docs/implementation-plans/plan-details/security-check-command/09-deliver-security-auto-apply-end-end.md
- id: 10
  title: Document the security command across operator docs and flow docs; flip BACKLOG
    status
  files:
  - RUNBOOK.md
  - README.md
  - CLAUDE.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  - BACKLOG.md
  - docs/how-to/pipeline/audit.md
  - docs/how-to/recovery/README.md
  - docs/how-to/recovery/audit.md
  allowed_mentions:
  - docs/how-to/pipeline/run.md
  complexity: medium
  change_type: non-code
  gate:
  - grep -q 'plan-tool security' RUNBOOK.md
  depends_on:
  - 3
  - 4
  - 5
  - 6
  - 8
  - 9
  detail: docs/implementation-plans/plan-details/security-check-command/10-document-security-command-across.md
---
# Security Check Command

## Overview

Adds a first-class **security** subcommand that reviews and reconciles either the **plan** or the **code** for security concerns. It produces severity-labeled findings (CRITICAL/HIGH/MEDIUM/LOW/NIT) in the same shape as `review`/`completeness`, persists a reusable report, and — under its own `--iterate` flag — participates in a convergence apply loop where findings are applicable. It honors the exit-code convention (exit 0 even with CRITICAL findings; `--fail-on-findings` flips the rc) and runs through the existing `claude`/`codex` backend abstraction. Rather than running automatically inside `completeness`, the command **surfaces itself as a relevance-gated next-step suggestion** at the end of `detail` and `completeness`, keeping each of those commands focused while still nudging the user to run a security pass when the plan touches security-relevant surface.

## Problem statement

Security is **already a per-step review mode**, but only at the per-step level: `prompts/security.md` exists and audits a single step's detail/files for injection, authorization, data exposure, auth handling, input validation, secret handling, and IAM (template vars `${step_id}`, `${step_title}`, `${step_detail}`, `${step_files}`, `${plan_title}`, `${step_index}`, `${step_total}`, `${lessons_section}`; output is a `## Findings` block with severity-prefixed bullets). `security` is in `AVAILABLE_MODES` (`cli/app.py`): `("run", "check", "optimize", "document", "test", "security", "lint")`, runs per-step via `run_step(..., mode="security")`, sweeps done steps via `verify-all --mode security`, and is a read-only (non-mutating) mode in `launcher.py`. The gap this plan fills is **plan-wide** security review + **reconcile** (plan ⇆ code) + a **discoverable entry point** — not the per-step mode, which already exists.

## Architecture

A new top-level `security` subcommand with `--target plan|code` and a `--reconcile` flag for plan⇆code drift (chosen over extending the `review`/`reconcile` families with a `--security` scope) so it gets its own help, its own reusable-report bucket, and a clean place to host the auto-apply loop; downstream steps assume this unless the detail step pushes back to the user. **`--reconcile` takes precedence over `--target`**: step 3 declares `--target` (default `plan`) and `--reconcile` as independent flags and resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the internal `target="reconcile"` direction and overrides any `--target` value — `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction (the `--reconcile` help documents this precedence), and the orchestrator only ever sees a single resolved `target`. **`--step` is rejected at parse time when combined with `--reconcile`** (a usage error, non-zero rc, never dispatching): the reconcile direction derives its scope from the full plan⇄code surface (every step and its declared files), so a single `--step` is meaningless against it — `plan-tool security --reconcile --step <id> <name>` is an error, not a one-step reconcile, keeping the whole-plan full-surface contract unambiguous. `--step` remains required for `--target code` (single-step audit) and unused for `--target plan`.

A new orchestrator `security_audit.py`, shaped after `review.py:review_plan_full()`, takes plan path, repo_root, optional `step_id`, and a target (plan vs code vs reconcile). It reuses `prompts/security.md` for per-step code audit and adds a **plan-level** prompt (`prompts/security-plan.md`) that audits the plan's design/decomposition for security gaps (missing authz steps, secrets in plan body, unsafe data flows the plan bakes in). It returns a findings list of the existing `Recommendation` shape (id, source, severity, title, body, suggested_action, impact/complexity triage tags) so it composes with the rest of the tool, and persists a reusable report under `plan-details/<slug>/reports/<ts>-security-<target>.json` with a plan+code fingerprint, following the `resolve_reusable_audit` reuse pattern. Because `target="plan"`, `target="code"`, and `target="reconcile"` audits are distinct directions, the **target is encoded in the filename suffix** (`-security-plan.json` vs `-security-code.json` vs `-security-reconcile.json`), and `resolve_reusable_security` takes a `target` parameter that scopes its lookup to the matching suffix. This makes cross-target reuse structurally impossible: a `--target code` caller can never resolve a `target="plan"` save, nor vice versa — the guard holds even for an *empty-recs* (clean-audit) sidecar, where a `source`-derived target would be unreadable. A plan-audit reuse must never serve a code-audit report or vice versa. Beyond the target suffix, the **`target="code"` axis must additionally scope its lookup by `step_id`**: the `-security-code.json` suffix encodes only the target, not the step, so two steps' code audits write same-suffix sidecars — `resolve_reusable_security` for the code target must therefore key on `step_id` (mirroring the reconcile family's per-step `_find_saved_for_step`), not return the newest target-suffix sidecar (the whole-plan `resolve_reusable_audit` shape it is otherwise cloned from), or it would serve one step's saved code audit to a different step's caller. **`resolve_reusable_security` ships dormant in this plan:** step 2 builds it and step 3 writes the `<ts>-security-<target>.json` sidecar, but **no in-plan step reads the resolver** — the reuse-prompt wiring that would short-circuit a Claude call on an unchanged fingerprint is deferred to a follow-up for all three targets (see `## Deferred`). The persistence/lookup machinery lands write-ready so the follow-up only adds the consumer; this plan does not claim a reuse short-circuit it does not deliver.

The invoker seam is `shell_security_invoker()` in `shell.py`, wrapping `claude_invoke`, returning `(exit_code, stdout)` with exit 127 = claude-not-on-PATH fallback; the orchestrator reads it as a module-level global so tests can monkeypatch it.

Reconcile is added by generalizing the `run_auto_reconcile_on_drift` hook (`auto_reconcile.py`) to audit plan-stated security intent against the code's actual security posture under a `mode="security-reconcile"` prompt and emit drift findings, so a code change since the last security audit re-triggers it. **No `security-reconcile` row is added to `cli/reconcile.py:_RECONCILE_KINDS`** — it would be dead config: the existing `detail-reconcile` / `run-reconcile` `name_includes` suffixes are substring-disjoint from `-security-reconcile`, so they already cannot mis-grab a security sidecar, and no production caller queries `resolve_reusable_reconcile` / `_find_saved_for_step` with a `security-reconcile` kind. **Reconcile reuse keys on `resolve_reusable_security(..., target="reconcile")`** — the `-security-reconcile` suffix is its own bucket; security reuse does **not** key on `resolve_reusable_reconcile` (the existing reconcile family persists via `resolve_saved_review` in `review_persistence`, which this plan does **not** consult for the security verb). The standalone `plan-tool security --reconcile <name>` does **not** depend on in-run file drift: it derives its drift scope from the full plan⇄code surface — treating every plan step (and the files each step declares) as in scope — so it runs the intent-vs-posture comparison across the whole plan even on a tree with no recorded file drift, synthesizing that whole-plan `drifted`/`file_to_step` set via `scope_guard.build_file_to_step_map`. This requires a **dedicated drift prompt** (`prompts/security-reconcile.md`) that compares the plan's stated security intent against the code's actual posture (e.g. detecting a plan that *states* an authz step the code lacks); reusing the per-step `prompts/security.md` code audit via `mode="security"` does **not** satisfy these drift semantics — it only re-runs a code-only audit and cannot detect plan-vs-code divergence. Step 4 must author this drift prompt rather than relabeling the per-step code audit. **One canonical sidecar and one writer for the reconcile direction:** the single consolidated `<ts>-security-reconcile.json` written by `write_security_report(..., target="reconcile")` (step 3's `cmd_security`) and resolved by `resolve_reusable_security(..., target="reconcile")` is the **only** on-disk reconcile sidecar. To eliminate a double-write, step 4 invokes `run_auto_reconcile_on_drift` with its per-step `save_review(kind="security-reconcile")` persistence **suppressed** (e.g. a `persist=False`/no-op-save path) for the security verb, so no per-step `security-reconcile.json` is written and `write_security_report` is the sole writer. `run_auto_reconcile_on_drift`'s `int` count and per-step findings stay in-memory step-4-internal scratch, **not** a reuse surface. Step 4 aggregates the per-step drift findings into a single `SecurityAuditResult` (concatenating each step's findings, with `step_id` preserved on each `Recommendation`) and returns it; step 3's `cmd_security` renders `result.findings` and persists exactly that one consolidated report. **`run_auto_reconcile_on_drift` is best-effort per step** — a launcher error or non-zero claude exit on a step is skipped with only a stderr note — so without a coverage count a sweep that audited 7 of 10 steps would report a clean-looking findings set that reads as a clean pass (false assurance, the worst failure mode for a security verb). To make partial coverage visible, step 4 **counts the steps it skipped or failed to audit and surfaces that count on the returned `SecurityAuditResult`** (the `skipped_steps` field defined in step 1). The generalized `run_auto_reconcile_on_drift` exposes only `mode`/`persist`/`findings_sink`/`invoker` and its best-effort loop `continue`s past a launcher-error/non-zero-exit step with only a stderr note, so step 4 must **add a skip-count channel to `run_auto_reconcile_on_drift`** (a return value / out-param tallying steps skipped or failed to audit) and **thread that count into `SecurityAuditResult.skipped_steps`** in its adapter — not leave it at the `0` default — since a clean step (0 findings) is otherwise indistinguishable from a skipped one in `findings_sink`. Step 3's `cmd_security` then renders `skipped_steps` alongside the findings so a partial sweep is reported as partial rather than as a clean pass. **The reconcile target threads `cmd_security`'s resolved `shell_security_invoker` into `run_step`.** `launcher.Invoker`, `review.Invoker`, and `SecurityInvoker` are all the same `Callable[[str], tuple[int, str]]` signature, so step 4 adds an `invoker` param to `run_auto_reconcile_on_drift` and passes `run_security_audit`'s invoker straight through to `run_step(invoker=…)` — no contract mismatch. **The hook generalization must also parameterize (or the findings sink must restamp) the finding `source` to `"security-reconcile"`, not only the `mode`/`persist`/`findings_sink`/`invoker` knobs:** `run_auto_reconcile_on_drift` hardcodes `extract_reconcile_recommendations(..., source="detail-reconcile")`, and `detail-reconcile` is in `_APPLY_AS_FINDING_SOURCES`/`APPLY_ELIGIBLE_SOURCES`, so leaving `source` unstamped would silently flip every `security --reconcile` finding from advisory to apply-eligible and break the criterion that reconcile findings carry `source="security-reconcile"`. The seam is consumed on all three targets: `target in {"plan","code"}` calls the resolved invoker directly; `target="reconcile"` routes it through `run_auto_reconcile_on_drift → run_step`. Reconcile-target tests stub `run_auto_reconcile_on_drift`/`run_step` for determinism (the `conftest.py` gate blocks a real shell-out but does not neutralize the un-stubbed run-mode call), as the Testing section notes.

The CLI subcommand lives in `cli/security_cmd.py` following the `review_cmd.py`/`gates_cmd.py` pattern: a `register(subparsers) -> dict[str, Handler]` export and a `cmd_security(args, *, invoker=None) -> int` handler, added to the command-module registry and to `CANONICAL_COMMAND_ORDER` in `parser.py`, with `--fail-on-findings` support. Step 3 ships it **thin (one-shot, no convergence loop)**; step 8 adds the opt-in `--iterate` apply loop on top.

### Discoverability via a next-step pointer (not a completeness dimension)

Security is **not** wired as a dimension inside `completeness`. Security findings are advisory by nature ("humans decide"), and folding a Claude security pass into every `completeness` run would (a) add cost/latency to a command that's about plan *completeness*, (b) require fragile plan-fingerprint-vs-code-staleness reuse carve-outs to stay affordable, and (c) bury security findings in a report the user didn't ask security questions of. Instead, **step 5 emits a one-line next-step pointer** — `→ plan-tool security --target plan <name>` — at the end of two commands, reusing the existing `_print_next_steps` helper (`cli/console.py`):

- **End of `detail`** (`cli/authoring.py:cmd_detail`, after the existing review/run/jira Next-steps block) — the plan design has just solidified, the best moment for a plan-target audit.
- **End of `completeness`** (`cli/completeness_phases.py:_persist_and_present_report`, in both the `--iterate` summary path and the audit-only path) — the convergence gate.

Completeness does **not** call `run_security_audit`, does **not** add a Security section to `_render_grouped_report`, and does **not** add a `security` bucket to `_render_completeness_json`. The cheap keyword **relevance gate** (step 6 — a no-Claude scan of plan title + step titles + declared file paths) decides only whether the pointer is *shown*, so a wrong verdict costs nothing but a shown/hidden suggestion line; `--no-security-hint` suppresses it outright. This is deliberately lower-stakes than gating an expensive audit pass: the gate never spends or skips Claude, it just decides whether to nudge.

### Auto-apply (opt-in, hosted on the `security` command)

For convergence/`--iterate`, security findings are mostly **advisory** (humans decide), like plan-completeness findings, so by default they are surfaced and **not** auto-applied. The apply loop lives on the `security` command itself (step 8), modeled on the completeness apply pattern, since completeness no longer hosts security findings. Step 7 ships the inert primitive — an **empty** `SECURITY_AUTO_APPLY_ALLOWLIST` and the gating helper — with no seed and no apply-loop wiring, so no finding is apply-eligible yet. Step 8 adds the `security --iterate` convergence loop (audit → apply eligible → re-audit). Step 9 activates auto-apply end-to-end across four concrete edits, so a developer can implement against it without a separate detail file:

1. **Slug emission (`prompts/security-plan.md` only).** The plan-level prompt gains a `[category-slug]` token on each `## Findings` bullet (e.g. `[hardcoded-secret]`, `[broken-access-control]`), drawn from the OWASP/CWE category the finding belongs to, placed **after** the `SEVERITY:` prefix (mirroring `plan-audit.md`) so the slug lands in the parsed body rather than before the severity token — `parse_finding_bullets`'s `_FINDING_BULLET_RE` requires the severity token immediately after the bullet marker, so a bullet led by `[slug]` would parse as `UNSPECIFIED`, not a finding. The per-step `prompts/security.md` is **left unchanged**: it backs the existing `--mode security` per-step run path, whose output `launcher.parse_finding_bullets` parses without stripping a `[slug]`, so emitting the token there would leak it into every per-step finding body — violating the Out-of-scope "per-step run path is unchanged" guarantee. Auto-apply only needs anchors on the plan-target `hardcoded-secret` case, which the plan-level prompt covers; `target="code"` findings keep `rec.anchor=None` and stay advisory. **The prompt confines `[hardcoded-secret]` to the plan-body-literal case:** it emits that slug only when the secret is a literal value present in the plan prose itself (where removal is unambiguous), and must emit a distinct, non-allowlisted slug (e.g. `[secret-in-generated-code]`) for a finding that the plan's *design* prescribes embedding a credential in generated code — that case needs human judgment, not a prose mutation. This keeps the auto-apply allowlist key (`hardcoded-secret`) matched to the "unambiguous removal" rationale, so a design-level credential finding can never pass `security_finding_is_auto_applicable` and route through `apply_finding`.
2. **Anchor population (`security_audit.py:_security_recommendations`).** Security finding **ids are body-keyed**: `_security_recommendations` is cloned from `review.py:_claude_recommendations`, which builds `id=_make_rec_id(None, source, body)` from the finding **body**, not the anchor — so two distinct `hardcoded-secret` findings in one plan already mint distinct ids regardless of what `rec.anchor` holds, and id collapse is not a risk on this path (that risk lives only on `review.py:_parse_plan_audit_findings`, which keys its id on the slug; the security parser does not use it). The parser still composes a **per-finding-unique** anchor — the `[category-slug]` joined with the same per-body discriminator the id derives from — but its purpose is **not** to prevent id collapse: it exists only to keep the bare `[category-slug]` recoverable as the anchor's leading component for the auto-apply key, while keeping each finding's anchor distinct. The allowlist key is the **category**, never the whole id-bearing anchor. No new field — `Recommendation.anchor` already exists.
3. **Allowlist seed (`security_audit.py`).** `SECURITY_AUTO_APPLY_ALLOWLIST` (shipped empty in step 7) is seeded with exactly `{"hardcoded-secret"}` — the single mechanical case where the secret lives in the plan body itself and removal is unambiguous. The slug-emission constraint above (point 1) guarantees this category only ever tags a plan-body-literal secret; a design that prescribes embedding a credential in generated code carries the distinct `secret-in-generated-code` slug, stays out of the allowlist, and remains advisory. `security_finding_is_auto_applicable(rec)` (the step-7 gating helper) returns `True` only when the finding's **category** — the slug component of the composed anchor, not the full id-bearing `rec.anchor` — is in the allowlist.
4. **Apply-loop wiring (`cli/security_cmd.py`, `review_walk.py`).** The step-8 `security --iterate` apply loop filters the audit result via `apply_eligible_security_findings → security_finding_is_auto_applicable` and routes each surviving finding through `apply_finding` **directly** — it **never** calls `review_walk.should_apply_as_finding`. So only a finding whose **category** is in `SECURITY_AUTO_APPLY_ALLOWLIST` is applied (its distinct anchor keeping each same-category finding individually tracked); every other security finding stays deferred/advisory and is reported, not applied. **Separately and orthogonally**, `review_walk.should_apply_as_finding` gains an **OR-branch beside the existing source-membership pre-filter** — `rec.source in _APPLY_AS_FINDING_SOURCES` **or** `security_finding_is_auto_applicable(rec)` — but that extends the **interactive** review/reconcile walk only, not the `--iterate` channel, and `security-plan`/`security-code` stay out of `_APPLY_AS_FINDING_SOURCES` (adding them would flip every security finding from advisory to apply-eligible). Within this plan no walk loads a `security-plan`/`security-code` sidecar, so that OR-branch ships inert/forward-looking; the `--iterate` apply decision rides entirely on the allowlist filter above.

After step 9, only clearly-mechanical fixes (e.g. a hardcoded secret the plan body itself contains) become apply-eligible under `security --iterate`; everything else is deferred and reported. Step 9 also updates `RUNBOOK.md` to document the now-active allowlist and apply-loop wiring (auto-apply is no longer advisory-only), since step 10 documents only the inert step-7 primitive.

**Severity-blocking policy:** security `LOW`/`NIT` findings are **non-blocking** — surfaced as advisory noise, they never flip `--fail-on-findings` (step 3). Because `review.py:_CLAUDE_SEVERITY_MAP` folds `LOW`→`medium` and `convergence.is_blocking` treats `medium/high/critical` as blocking, `_security_recommendations` (step 1) must keep `LOW`/`NIT` security findings out of the blocking band rather than reusing that fold unchanged; only `MEDIUM`/`HIGH`/`CRITICAL` security findings are blocking. This `LOW`/`NIT`-non-blocking normalization must hold across **all three targets**, not only step 1's `_security_recommendations`: the `--reconcile` target (step 4) builds its findings through `review.py:extract_reconcile_recommendations`, which applies the same `_CLAUDE_SEVERITY_MAP` `LOW`→`medium` fold inline while constructing each `Recommendation` and never preserves the original `LOW` token — so a post-extraction re-map is impossible (a folded-from-`LOW` finding is indistinguishable from an authored-`MEDIUM` one, and no `low` severity survives to rewrite). Step 4 must instead normalize `LOW`→`"nit"` (keeping `NIT`→`"nit"`) **at parse time** — extracting the reconcile bullets without the `LOW`→`medium` fold, or threading a security-specific severity map through the extractor — so the `LOW` token maps to `nit` before the `Recommendation` is built; otherwise a `LOW` `security-reconcile` finding lands at `medium`, which `convergence.is_blocking` treats as blocking and `--fail-on-findings` flips to non-zero, contradicting this policy on the reconcile target.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)https: — Authoritative reference for add_subparsers()/add_parser() needed to register the new top-level `security` subcommand and its `--target`/`--reconcile`/`--fail-on-findings`/`--iterate`/`--no-security-hint` flags in parser.py.
- [Claude Code Headless Mode (Anthropic docs)https: — Documents `-p/--print`, `--output-format stream-json`, and exit-code behavior an implementer relies on when shelling out through shell_security_invoker() and the claude backend abstraction.
- [OWASP Top 10 (2021)https: — The canonical web-application risk taxonomy (injection, broken access control, secrets exposure) to ground the plan-level and code security prompts and the categories of findings they emit.
- [CWE — Common Weakness Enumeration (MITRE)https: — The standard catalog of software weaknesses for labeling and cross-referencing findings (e.g. CWE-798 hardcoded credentials) consistently in the severity-labeled security report.
- [OWASP Application Security Verification Standard (ASVS)https: — A structured verification checklist (authz, input validation, secret/IAM handling) useful for defining the plan-vs-code audit dimensions and disciplined severity rollup.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **No new per-step mode** — `--mode security` already exists; this plan does not re-implement it. The new command may *call* the same `prompts/security.md` for code audit, but the per-step run path is unchanged.
- **No security dimension inside `completeness`** — completeness does not run a Claude security pass, render a Security section, or add a JSON security bucket. Security is a standalone command that `completeness` (and `detail`) merely *point at* via a next-step suggestion.
- **No SAST/dependency-scanner integration** — this is claude-backed semantic review of the plan and changed code, not a wrapper around `bandit`, `semgrep`, `pip-audit`, etc. (could be a future plan).
- **No new backend** — runs through the existing `claude`/`codex` backend abstraction; no security-specific subprocess CLI.
- **No auto-remediation of real vulnerabilities** — findings are advisory by default; the tool does not silently rewrite code to "fix" security issues beyond the conservative mechanical allowlist, and only under the opt-in `security --iterate`.
- **No change to the exit-code convention** — findings never force a non-zero rc except via `--fail-on-findings`.

## Risks

- **Standalone `security --reconcile` fan-out cost** (HIGH, **accepted as unmitigated within this plan's scope**) — the standalone full-surface sweep (step 4) synthesizes a whole-plan `drifted`/`file_to_step` set via `build_file_to_step_map` and runs `run_auto_reconcile_on_drift` per step, i.e. one Claude call per plan step even on a clean tree, so a large plan triggers an unbounded fan-out. **This plan ships no bound for it.** The eventual bound is **plan+code-fingerprint-gated reuse** — a `resolve_reusable_security(..., target="reconcile")` hit short-circuiting the whole sweep when neither the plan nor the code has changed since the last reconcile report — but that consumer is **deferred to a follow-up** (the resolver ships dormant; see `## Deferred`), so it is **not** a mitigation this plan delivers. The fan-out is therefore accepted as-is here: step 2 persists the reconcile sidecar so the deferred follow-up that reads it lands cheaply, but within this plan a clean tree re-running `security --reconcile` re-spends a Claude call per step. To keep the unmitigated fan-out from being multiplied by an apply loop, **`security --iterate --reconcile` is rejected at parse time** (step 8) — running the reuse short-circuit in the loop's round-0 is not an option while the resolver consumer is deferred — so the per-step fan-out is at most a single one-shot reconcile sweep, never one per convergence round.
- **Overlap with the existing `--mode security`** (MEDIUM) — two security entry points risk confusing users and drifting prompts. Keep `prompts/security.md` as the single source for *code* audit; the new plan-level prompt is additive. Document the split.
- **Pointer-as-noise** (LOW) — a next-step suggestion shown on every `detail`/`completeness` run can become wallpaper. Mitigated by the relevance gate (step 6 — only shown when the plan touches security surface) and the `--no-security-hint` escape hatch. Because the gate decides only whether to *show a line* (never whether to spend Claude), a false positive/negative is cheap.
- **Auto-apply danger** (HIGH) — auto-applying a "security fix" can break behavior or give false assurance. Keep the apply-eligible allowlist tiny and explicit (step 7 ships it empty; step 9 seeds it with only the hardcoded-secret case and wires the apply loop); default everything to deferred/advisory; auto-apply only fires under the opt-in `security --iterate` (step 8).
- **Mis-slug auto-apply residual** (MEDIUM, **accepted as unmitigated within this plan's scope**) — step 9's auto-apply safety rests on the plan-level prompt (`prompts/security-plan.md`) emitting `[hardcoded-secret]` only for a plan-body-literal secret and the distinct, non-allowlisted `[secret-in-generated-code]` for a design that *prescribes* embedding a credential. That discriminator is a **prompt instruction, not a structural gate**: no deterministic backstop catches a mis-slug, so a design-credential finding the model mistakenly tags `hardcoded-secret` passes `security_finding_is_auto_applicable` and routes through `apply_finding`, mutating plan prose on exactly the human-judgment case the slug split exists to protect. **This plan ships no deterministic guard for it** — a confirmation/eligibility check beyond the slug is out of scope. The residual is accepted as-is, bounded by the same controls that contain the broader Auto-apply danger above: the allowlist holds exactly one category, auto-apply fires only under the opt-in `security --iterate`, and the mutation is to plan prose (reviewable in the diff), not code.
- **Seam coverage gaps** (HIGH) — a missed invoker neutralization means tests silently shell out to real claude. Add the `shell_security_invoker` seam's TESTING.md table row in the same step that adds the seam (step 1); no `conftest.py` edit is needed — the existing autouse gate already covers it via `claude_invoke`.

## Open design issues (from scope-guard audit)

Surfaced by the iterative correctness loop while authoring this plan and migrated here from two now-archived `out-of-scope-findings` stubs (the findings are about *this plan's* design, so they live with the plan they correct). **Resolve each before executing the affected step.**

- **Severity-blocking is specified for only one of three targets** (step 1 vs step 4). The "only `MEDIUM`/`HIGH`/`CRITICAL` block; `LOW`/`NIT` stay advisory" policy is pinned to step 1's `_security_recommendations`, but step 4's `--reconcile` findings flow through `review.py:extract_reconcile_recommendations`, whose `_CLAUDE_SEVERITY_MAP` folds `LOW→medium` — so a `LOW` reconcile finding lands at `medium`, which `convergence.is_blocking` treats as blocking and `--fail-on-findings` flips. **Fix:** apply the carve-out uniformly across plan/code/reconcile, or stop the `LOW→medium` fold for security-reconcile.
- **`[category-slug]` collides with `anchor`'s id role** (step 9 + Architecture "Auto-apply" #2). Carrying the coarse category slug in `rec.anchor` clashes with `anchor`'s existing role as the concept **id fingerprint** the convergence loop keys off: two distinct `hardcoded-secret` findings both get `anchor="hardcoded-secret"`, collapse to one id, and `security --iterate` tracks/applies only one — silently dropping the rest. **Fix:** carry the category slug in a separate field; keep `anchor` a per-finding unique id.
- **`--iterate × --reconcile` reuse-bypass vs. the parse-time rejection** (steps 8/9). The finding: `_run_security_iterate_loop`'s round-0 calls `run_security_audit` *before* the one-shot `resolve_reusable_security` skip, so `security --reconcile --iterate` re-incurs the fan-out reuse is meant to bound; step 8 defers the semantics to step 9, which never defines them. The Risks section now says `security --iterate --reconcile` is **rejected at parse time** — **reconcile the two:** either drop the step-9 deferral (the rejection settles it) or define the in-loop reuse short-circuit.
- **`source` stamping silently flips reconcile findings to apply-eligible** (step 4). Step 4 generalizes `run_auto_reconcile_on_drift` (mode/persist/findings_sink/invoker) but omits `source`, which the hook hardcodes to `"detail-reconcile"` — a member of `_APPLY_AS_FINDING_SOURCES`/`APPLY_ELIGIBLE_SOURCES`. Without an override, every `security --reconcile` finding inherits `detail-reconcile` and flips from advisory to apply-eligible, contradicting the acceptance criterion that they carry `source="security-reconcile"`. **Fix:** add a `source` param to the generalized hook and stamp `"security-reconcile"`.

## Testing

Mirror-module unit tests: `tests/test_security_audit.py` and `tests/cli/test_security_cmd.py`, plus next-step-pointer coverage in `tests/cli/test_authoring.py` and `tests/cli/test_completeness_cmd.py`. Cover: invoker-seam monkeypatching — the plan and code targets stub the `shell_security_invoker` seam, but the reconcile target routes its Claude calls through `run_auto_reconcile_on_drift → run_step` (the launcher run-mode invoker), **not** `shell_security_invoker`, so `--target reconcile` / `security --reconcile` tests must stub `run_auto_reconcile_on_drift`/`run_step` for determinism (the `conftest.py` gate blocks a real shell-out but does not neutralize the un-stubbed call); reusable-report fingerprint hit/miss across the plan/code/reconcile suffixes; severity parsing/rollup; the **relevance gate** (pointer shown on a security-relevant plan, hidden on an irrelevant one, suppressed by `--no-security-hint`) asserted against `detail` and `completeness` output with no Claude pass spent either way; the **`security --iterate` apply loop** (an allowlisted `hardcoded-secret` finding routes through `apply_finding`; every other finding stays advisory); and the exit-code convention (0 with CRITICAL findings; non-zero only on failure or `--fail-on-findings`). Update `package_surface_help.golden.txt` for the new subcommand.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (feature) — unit tests added with the implementation; green before completion.
- step 9 (feature) — unit tests added with the implementation; green before completion.
- step 10 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool security --target plan <name>` audits the plan body and decomposition for security gaps and prints severity-labeled findings; exits 0 even with CRITICAL findings.
- `plan-tool security --target code <name> --step <id>` audits that step's changed code via `prompts/security.md` and prints findings; it persists a saved report under the `target="code"` suffix (reuse short-circuit on unchanged plan+code fingerprints is deferred — the resolver ships dormant; see `## Deferred`).
- `plan-tool security --target code <name>` with no `--step` fails cleanly with rc 2, rejected before any backend call (`run_security_audit` raises `SecurityError` and `cmd_security` maps it via `error(str(exc)); return 2`) — distinct from a completed audit's exit 0; `--target code` requires `--step` (single-step audit).
- `plan-tool security --reconcile <name>` reports drift between the plan's stated security intent and the code's actual posture and persists to the `target="reconcile"` sidecar (reuse short-circuit deferred; see `## Deferred`).
- `--reconcile` takes precedence over `--target`: step 3 resolves the direction by precedence (`target = "reconcile" if args.reconcile else args.target`), so `--reconcile` selects the reconcile direction and overrides any `--target` value (e.g. `plan-tool security --target code --reconcile <name>` dispatches the reconcile direction, as the `--reconcile` help documents); `--reconcile` alone also selects the reconcile direction, and the orchestrator only ever sees a single resolved `target`.
- `--step` combined with `--reconcile` is rejected at parse time (usage error, non-zero rc, never dispatching): the reconcile direction is whole-plan full-surface and a single `--step` is meaningless against it, so `plan-tool security --reconcile --step <id> <name>` errors rather than scoping the reconcile to one step. `--step` stays required for `--target code` and unused for `--target plan`.
- At the end of `plan-tool detail <name>` and `plan-tool completeness <name>`, a `→ plan-tool security ...` next-step pointer is printed **when the relevance gate fires** (the plan touches security-relevant surface) and is absent on a non-relevant plan or when `--no-security-hint` is passed. Neither command runs a Claude security pass, and `completeness` output contains no Security section or JSON `security` bucket.
- `plan-tool security --iterate <name>` runs the audit→apply→re-audit convergence loop; an allowlisted `hardcoded-secret` finding is applied via `apply_finding`, while every non-allowlisted security finding stays advisory/deferred and is reported, not applied. Without `--iterate`, the command is a one-shot audit that applies nothing.
- `--fail-on-findings` flips the rc only on blocking (`MEDIUM`/`HIGH`/`CRITICAL`) findings — `LOW`/`NIT` security findings are non-blocking and never flip it; without the flag, a completed audit exits 0 regardless of severity.
- The per-step `--mode security` (`run` / `verify-all`) path renders findings with no leading `[category-slug]` in the body: step 9 adds the slug token to `prompts/security-plan.md` only and leaves `prompts/security.md` unchanged, so the shared prompt contract holds on both the new `security` verb and the unchanged per-step path.
- No test spawns the real `claude` binary — the `shell_security_invoker` seam is monkeypatched and the `conftest.py` gate passes.

## Deferred

- **Completeness security integration** — **decided against.** Security is a standalone command surfaced via a relevance-gated next-step pointer (steps 5–6), not a dimension folded into `completeness`. Folding it in was rejected because it adds cost/latency to a completeness run, needs fragile plan-fingerprint-vs-code-staleness reuse carve-outs to stay affordable, and buries advisory security findings in an unrelated report. Revisiting an in-report security dimension (with timing measurement) remains a possible future refinement but is explicitly out of this plan.
- **Auto-apply allowlist scope** — step 7 ships the allowlist empty (inert primitive); step 9 seeds it with only the hardcoded-secret-in-plan-body case and wires the `security --iterate` apply loop. Widening to other mechanical fixes is deferred until the conservative seed proves safe in practice.
- **Completeness-loop drift-hook wiring** — firing `run_auto_reconcile_on_drift`'s file-drift-gated path from a `completeness --iterate` loop with `mode="security"` is out of scope: completeness no longer runs security at all. Step 4 builds the hook for the standalone `security --reconcile` command; operationalizing a code-drift re-trigger inside any iteration loop beyond the security command's own is left for a future plan.
- **Reuse-prompt wiring (the `resolve_reusable_security` consumer)** — across all three targets (plan/code/reconcile), reading the resolver to short-circuit a Claude call on an unchanged plan+code fingerprint is deferred to a follow-up. Step 2 builds `resolve_reusable_security` and step 3 writes the `<ts>-security-<target>.json` sidecar, but **no in-plan step consumes the resolver** — it ships dormant/write-only. The follow-up adds the consumer at each call site (step 3's `cmd_security` for plan/code, step 4's reconcile sweep); until then every run re-spends its Claude call(s).
- **SAST/dependency-scanner integration** (`bandit`, `semgrep`, `pip-audit`) — postponed to a separate future plan; this one stays claude-backed semantic review.
