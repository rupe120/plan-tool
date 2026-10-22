"""plan-tool command-line entry point.

Subcommands are organized by **intent** — what user problem each one
solves. New subcommands add a per-intent command module exposing
register(subparsers) and append it to COMMAND_MODULES in
plan_tool/cli/app.py; keep this catalog and the SKILL.md "Subcommands
at a glance" section in sync.

Discovery & inspection — read plan state; never call claude.
  plan-tool list                           Enumerate plan-tool-compatible plans.
  plan-tool status <name>                  Show step-by-step status for one plan.
  plan-tool validate <name>                Schema-check a plan's frontmatter.

Project setup — capture repo-owned metadata; never infer it or call claude.
  plan-tool init --intent "..." [--non-goal "..."] [--decision "..."]  Initialize a tracked project profile once; requires operator-supplied content and refuses to overwrite it.

Roadmap — turn a concept brief into staged architecture artifacts, one rung above `create`.
  plan-tool roadmap <slug> [--from-existing <concept.md>] Non-interactively stage a concept brief into the four gated architecture artifacts (domain, constraints, components, roadmap), plus draft seeds, and publish them as one immutable version under docs/implementation-plans/roadmaps/<slug>/; the accepted head is written last. A failed run holds its gate-clean stages and the next run with the same brief resumes from them; a changed brief is refused with its remedy, and a roadmap that already has an accepted head refuses a stage run. Deterministic gates retry each stage's claude call before writing; exits non-zero only when a stage exhausts its retry budget.
  plan-tool roadmap <slug> --apply [-y]    Apply-only: promote the draft seeds named by 04-roadmap.md into docs/implementation-plans/plan-seeds/ after a preview and confirm (-y skips the confirm). Runs no stage and invokes no backend.
  plan-tool roadmap <slug> --refresh-seeds  Reprocess invalidated derived seeds against the current codebase, restoring archived copies and writing a before/after difference report without rewriting roadmap artifacts.
  plan-tool roadmap <slug> --view {summary,walk,ledger,index,seeds,html} [--mode {current,review}] [--id ROW_ID] [--output PATH]   Inspect: render a compact review summary, traceability walk, decision ledger, reverse citation index, draft-seed state report, or a self-contained, print-formatted HTML page of every artifact row with its resolvable references linked and dangling or ambiguous ones marked, over the accepted roadmap version. --mode selects design-state (current, default) or the review channel (review); --id scopes --view index to one row's citers. Every view but html prints; html writes <roadmap-dir>/review.html by default (--output PATH chooses the destination, --output - prints instead). Runs no stage or backend and changes no canonical roadmap state.

Authoring — produce or restructure plan files on disk.
  plan-tool create [slug] [--no-iterate] [--no-synthesize-body] [--no-fetch-docs] [--no-distill]   Interactively author a new plan (slug optional: suggested from --from/--from-existing when omitted); resumable; a distill first-pass reorganizes a free-form seed (or proposes a multi-plan split); runs post-write convergence by default (--no-iterate to opt out); runs body-section synthesis by default (--no-synthesize-body to opt out), grounding it in fetched reference-doc content (--no-fetch-docs to opt out).
  plan-tool detail <name> [--iterate]   Draft developer-actionable per-step detail markdown; resumable; emits a one-shot write by default (--iterate to opt into the per-step convergence loop).
  plan-tool split <name> --step N --into "..." --into "..."   Split one step into named sub-steps on demand (renumbers + rewires the plan), author their detail files, then loop on the completeness audit; resolves a completeness BLOCKED finding end-to-end.
  plan-tool merge <name> --steps N --steps M [--title "..."]   Fold a contiguous set of steps into one on demand (renumbers + renames downstream detail files), re-author the merged step's detail file, then loop on the completeness audit; confirmed at the TTY (bypassed under --yes / non-TTY).
  plan-tool scope-out <name> --step N [--apply] [-y]   Carve an over-packed step out of a plan into a create --from-existing forward-seed and narrow the plan; recommend-only by default, --apply plus confirm or -y to mutate.
  plan-tool scope-review <name> --concept ID --decision ID=STATE   Review and sign off an explicit concept scope, then synchronize accepted decisions to the plan.

Plan decisions — record an explicit operator/session decomposition decision.
  plan-tool decide <name> --outcome {single,split,scope-out,reframe,withdraw,defer} --anchor {plan|step:N} --rationale "..."  Append one explicit decision record for a real plan or step. It never changes the plan, asks no model, and reports a failed telemetry append rather than claiming success.

Annotate — judge an existing plan against the code and emit a forward seed.
  plan-tool annotate <plan-file>           Classify each section IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED against the repo; write <name>.annotated.md (verbatim + status blocks) and a carryover <name>.seed.md for `create --from-existing`. --archive moves the original.

Audit — check the plan and code agree, or judge the plan's design; never advances step status.
  Reconcile (mutating) — bring the plan and code into agreement:
    plan-tool reconcile-plan <name> [--step N | --all]  Edit the PLAN to match the code — plan-wide drift audit (one claude call + deterministic checks) (aliases: reconcile, review).
    plan-tool detail <name> --reconcile [--step N | --all]  Per-step plan-side reconcile — edit a step's detail to match code; --all sweeps not-yet-done steps.
    plan-tool reconcile-code <name> [--step N | --all]  Edit the CODE to match the plan — lands edits inline (legacy form: run --reconcile).
    plan-tool reconcile-plan-walk <name>     Apply a saved reconcile's findings interactively, no claude call (aliases: reconcile-walk, review-walk).
  Verify (read-only) — judge finished (done) steps:
    plan-tool verify-all <name> --rollup     Per-step pass/warn/fail reconcile verdict over done steps (alias: verify; add --deep for per-criterion).
    plan-tool verify-all <name> --mode <m>   Sweep a read-only review mode across every done step (aliases: reconcile-all, review-all).
    plan-tool run <name> --mode <review>     Read-only review mode on a single step (check/optimize/document/test/security/lint).
  Completeness — judge the plan's own design (concepts, coverage):
    plan-tool completeness-audit <name>      Are the plan's concepts correct + complete + unambiguous? Deterministic checks + sampled claude audit, grounded in the detail bundle.
    plan-tool completeness-apply <name>      DEPRECATED, going away (BACKLOG #367) — close conceptual gaps with a session-directed edit instead. Still clears files-coherence drift deterministically (adds cited real-file paths to allowed_mentions:, no claude).
    plan-tool data-contract-apply <name>     Walk saved DATA_CONTRACT.md drift findings from the most recent completeness audit; verifies saved payload freshness before editing.
    plan-tool gate-status <name> --json      Read saved audit gate verdicts without running an audit.
    plan-tool convergence <name>             Is the audit/apply loop converging? Reads saved report history; no claude, exits 0.
    plan-tool split-criteria [<plan>]        Show the split-criteria legend, or (with a plan) why that plan is shaped the way it is; no claude; criterion results exit 0.

Execution — drive code edits by running plan steps.
  plan-tool run <name> [--iterate]         Execute a step via a fresh claude subprocess; default --mode advances plan state; --iterate loops reconcile.
  plan-tool run <name> --all [--max-steps N]  Sweep every runnable step in one invocation; halts on first failure; implies -y.

Integration — emit artifacts for external systems.
  plan-tool jira <name>                    Emit copy-paste-ready JIRA stories (writes under plan-details/).
  plan-tool jira config                    Manage epics + plan→epic assignments (interactive wizard).

State management — inspect or clear plan-tool's own caches.
  plan-tool checkpoint {list|show|clear}   Manage on-disk resume checkpoints under <repo>/.plan-tool/checkpoints/.
  plan-tool runs {list|show|diff|profile|clear}  Inspect / profile / manage on-disk run logs under .plan-tool/runs/.
  plan-tool lessons consolidate            Dedup/conflict reconciliation across lessons files; recurrence-aware ordering reads .plan-tool/lessons-warnings.jsonl (diff by default; --apply to rewrite).
  plan-tool register <path-or-slug>        Adopt an on-disk plan file into the structured-plans manifest.
  plan-tool deregister <path-or-slug>      Remove a plan from the manifest (leaves the file on disk).
  plan-tool sweep [--dry-run|--report-only] Archive completed plans (deregister + move), report on partial and unregistered plans.
  plan-tool withdraw <path-or-slug> --reason "..."  Archive a plan being abandoned (as distinct from completed/superseded): move to archive/<stem>.withdrawn.md, move its plan-details, prepend a dated reason header, deregister. --reason is required.
  plan-tool attach-branch <plan> <branch>  Attach a plan to an ad-hoc branch (untracked local git config; off unless branch awareness is enabled); re-homes the plan onto its own branch on a convention-name collision.
  plan-tool detach-branch <plan>           Clear a plan's ad-hoc branch override (leaves the branch on disk in place; off unless branch awareness is enabled).

Workspaces — provision and inspect isolated per-plan git worktrees / clones.
  plan-tool worktree add <plan> [--branch B] [--clone]   Provision (or reuse) the plan's isolated workspace at its deterministic per-slug path, on the plan's branch (born inside the add); prints a cd hint. No claude call.
  plan-tool worktree list                  Report every registered plan's workspace: kind (worktree/clone), branch, path, dirty/clean. No claude call.

Setup — opt-in integration wiring (the CLI is standalone; never required).
  plan-tool install-skill [--user|--copy]  Install the bundled Claude Code / Codex / Cursor skill so an agent can drive plan-tool; symlinks into <root>/skills/plan-tool/ by default (--root .claude|.agents, --user for ~/, --copy to commit); --integration codex defaults to .agents and copies. No claude call.
"""

# The CLI implementation lives in :mod:`plan_tool.cli.app`. This package
# shell re-exports that module's public and test-touched surface so that
# ``from plan_tool.cli import X`` and the console entry point
# ``plan-tool = "plan_tool.cli:main"`` keep resolving after the former
# ``plan_tool/cli.py`` monolith became a package.
#
# Where dispatch reads its globals (load-bearing): every ``cmd_*`` handler
# resolves its collaborators (``run_step``, ``walk_recommendations``,
# ``create_plan``, ``generate_detail``, ``_build_run_budget``, …) as
# :mod:`plan_tool.cli.app` *module globals*. A name re-exported here points
# at the **same** function object as the one in ``app``, so rebinding it on
# this package does **not** affect dispatch — the handler still reads
# ``app``'s binding. Tests that ``monkeypatch.setattr`` a CLI global must
# therefore target ``plan_tool.cli.app``, not this package alias.

from __future__ import annotations

from plan_tool.cli import app as app

# Mirror every module-level name from ``app`` (public *and* private) into
# the package namespace. The test suite imports ~40 underscore-prefixed
# helpers via ``from plan_tool.cli import _x``; ``app`` defines no
# ``__all__``, so a ``from ... import *`` would skip exactly those
# privates and ship the surface broken. Copy them explicitly instead.
# Nested closures (e.g. ``_dispatch_apply_finding`` inside
# ``_build_review_action_fn``) are not module globals and are
# deliberately left unsurfaced — ``test_apply_finding_dispatch_reachable``
# asserts they stay reachable only through their builder.
_package_globals = globals()
for _name in dir(app):
    if _name.startswith("__") and _name.endswith("__"):
        continue
    _package_globals.setdefault(_name, getattr(app, _name))
del _package_globals, _name

# The curated public + entry-point surface. Re-exporting more (the
# private helpers above) is intentional but kept out of ``__all__`` so
# ``import *`` stays lean.
__all__ = [
    "app",
    "main",
    "build_parser",
    "AVAILABLE_MODES",
    "walk_recommendations",
    # Dispatch handlers (one per registered subcommand, plus sub-actions).
    "cmd_list",
    "cmd_root",
    "cmd_status",
    "cmd_validate",
    "cmd_roadmap",
    "cmd_create",
    "cmd_detail",
    "cmd_split",
    "cmd_merge",
    "cmd_annotate",
    "cmd_run",
    "cmd_reconcile_code",
    "cmd_review",
    "cmd_review_all",
    "cmd_review_walk",
    "cmd_verify",
    "cmd_verify_all",
    "cmd_completeness",
    "cmd_completeness_apply",
    "cmd_data_contract_apply",
    "cmd_convergence",
    "cmd_gate_status",
    "cmd_init",
    "cmd_decide",
    "cmd_scope_out",
    "cmd_scope_review",
    "cmd_split_criteria",
    "cmd_jira",
    "cmd_jira_config",
    "cmd_checkpoint",
    "cmd_runs",
    "cmd_lessons",
    "cmd_lessons_consolidate",
    "cmd_register",
    "cmd_deregister",
    "cmd_sweep",
    "cmd_withdraw",
    "cmd_attach_branch",
    "cmd_detach_branch",
    "cmd_worktree",
    "cmd_install_skill",
]
