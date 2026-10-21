> **Auto-archived**: this plan was swept on 2026-06-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Reuse Saved Completeness Audit
status: completed
priority: medium
steps:
- id: 1
  title: Add plan_fingerprint + code_fingerprint fields and compute_plan_fingerprint
    helper to review_persistence.py (round-trip + legacy tolerance; code_fingerprint
    is an opaque path→hash dict so the module stays a leaf)
  files:
  - plan_tool/review_persistence.py
  - tests/test_review_persistence.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/reuse-saved-completeness-audit/01-plan-fingerprint-code-fingerprint.md
  status: done
- id: 2
  title: Promote drift_detection._compute_content_hash to public compute_content_hash
    (behavior-preserving rename; repoint the three in-module call sites)
  files:
  - plan_tool/drift_detection.py
  - tests/test_drift_detection.py
  complexity: low
  change_type: refactor
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/reuse-saved-completeness-audit/02-promote-drift-detection-compute-content.md
  status: done
- id: 3
  title: Add compute_code_fingerprint(plan, plan_path, repo_root) in completeness_report.py
    (per-file sha256 map over scope_guard.compute_drift_watched_paths, sorted keys)
  files:
  - plan_tool/completeness_report.py
  - tests/test_completeness_report.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/reuse-saved-completeness-audit/03-compute-code-fingerprint-plan-plan-path.md
  status: done
- id: 4
  title: Widen write_completeness_report to accept plan_fingerprint + code_fingerprint
    and persist both correctness+completeness axes; have _persist_and_present_report
    compute both fingerprints and pass correctness_recs + conceptual_recs
  files:
  - plan_tool/completeness_report.py
  - plan_tool/cli/completeness_phases.py
  - tests/test_completeness_report.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/reuse-saved-completeness-audit/04-widen-write-completeness-report-accept.md
  status: done
- id: 5
  title: Add resolve_reusable_audit() — locate newest (or --reuse-audit-id) sidecar,
    recompute both fingerprints, return loaded SavedReview + axis-split recs + fresh
    bool (plan AND code match) + drifted code paths (repo-root-resolved to absolute
    Paths so they align with the absolute-keyed build_file_to_step_map for attribution)
    for the staleness warning; an unresolvable --reuse-audit-id stem deliberately
    warns-and-proceeds to a fresh audit (returns None + one-line note) even under
    an explicit --reuse-audit rather than erroring, so the precedence is intentional
  files:
  - plan_tool/completeness_report.py
  - tests/test_completeness_report.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/reuse-saved-completeness-audit/05-resolve-reusable-audit-locate-newest.md
  status: done
- id: 6
  title: Add --reuse-audit/--no-reuse-audit + --reuse-audit-id flags and reuse-decision
    helper to completeness-audit, wiring reuse into cmd_completeness and the --iterate
    up-front audit; the reuse-decision helper reads args.audit_samples so an explicitly
    passed --audit-samples N suppresses the --yes/non-TTY auto-accept and forces a
    fresh audit (default sample count does not), while an explicit --reuse-audit still
    overrides it; when --reuse-audit is explicit and no sidecar exists at all, emit
    the one-line fallback note before falling back to a fresh audit; on reuse-accept
    skip the _persist_and_present_report fresh-sidecar re-write so reuse is idempotent
    (newest pointer stays stable, reports dir does not grow); emit an attributed staleness
    warning naming drifted code files (reusing render_attributed_path_line + build_file_to_step_map)
    when code drifted
  files:
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - tests/cli/test_completeness_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/reuse-saved-completeness-audit/06-reuse-audit-no-reuse-audit-reuse-audit.md
  status: done
- id: 7
  title: 'Add end-to-end integration coverage in tests/test_cli.py: two main([''completeness-audit'',...])
    runs through stubbed invokers asserting zero conceptual calls on fresh reuse,
    stale re-audit on plan edit AND on code edit, deleted-in-scope-file flagged, --no-reuse-audit/--reuse-audit-id
    matrix, and the --iterate reuse path'
  files:
  - tests/test_cli.py
  complexity: medium
  change_type: feature
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/reuse-saved-completeness-audit/07-end-end-integration-coverage-tests-test.md
  status: done
- id: 8
  title: Update AUDIT_RESUME_FLOW.md to describe fingerprinted conceptual-audit reuse
    (plan AND code fingerprints; the still-re-derived deterministic layer); add the
    new flags + code-drift staleness warning to RUNBOOK.md
  files:
  - docs/AUDIT_RESUME_FLOW.md
  - RUNBOOK.md
  complexity: low
  change_type: non-code
  gate:
  - '! grep -q ''nothing to checkpoint'' docs/AUDIT_RESUME_FLOW.md'
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/reuse-saved-completeness-audit/08-update-audit-resume-flow-md-describe.md
  status: done
---
# Reuse Saved Completeness Audit

## Overview

Adds cross-run reuse of the expensive Claude-driven conceptual completeness audit. `plan-tool completeness-audit` is commonly run twice — once to read the report, then again with `--iterate` to apply findings — and both runs re-run `audit_plan_until_stable` from scratch. This plan expands the existing JSON sidecar (`plan-details/<slug>/reports/<ts>-completeness.json`) to persist both conceptual axes (`plan-correctness` and `plan-completeness`) plus **two** fingerprints: a content-hash of the plan and its detail bundle (`plan_fingerprint`), and a per-file SHA-256 map of the codebase files the plan touches (`code_fingerprint`, keyed by repo-relative path over `step.all_files`). On the next run, reuse of the saved conceptual findings is offered only when **both** fingerprints still match — i.e. neither the plan text nor the code it was reasoned against has changed. A code-only change (the plan reloaded after the codebase moved underneath it) is detected per-file, so the operator gets a warning naming exactly which in-scope files drifted (and which step owns each) instead of silently reusing a stale audit. Deterministic well-formedness checks are always re-derived from disk; only the conceptual audit is reused; a stale fingerprint (plan *or* code) silently falls back to a fresh audit. New flags `--reuse-audit` / `--no-reuse-audit` (default: prompt interactively, auto-accept under `--yes` / non-TTY) and `--reuse-audit-id <stem>` control the behavior, on both the audit-only path and the `--iterate` loop's single up-front audit.

## Problem statement

`plan-tool completeness-audit` is commonly run twice: once on its own to read the report, then again with `--iterate` to apply findings. Both runs re-run the expensive conceptual audit from scratch — `audit_plan_until_stable` issues one or more Claude calls that each take minutes — even though the first run already computed and saved those findings. Today the audit-only run does persist artifacts: `write_completeness_report` writes a markdown report plus a JSON sidecar under `plan-details/<slug>/reports/<ts>-completeness.{md,json}`. But the sidecar only stores the `plan-completeness` (conceptual-completeness) subset — scoped for `completeness-apply` to walk — and nothing on a later run detects or reuses it. `docs/AUDIT_RESUME_FLOW.md` explicitly documents "no audit cache; findings re-derive from disk every run."

## Architecture

The sidecar becomes the reuse cache. `SavedReview` gains two optional fields: `plan_fingerprint: str = ""` and `code_fingerprint: dict[str, str] = field(default_factory=dict)`. `compute_plan_fingerprint(plan_path)` returns a stable content hash over the plan file plus every per-step detail file in its bundle (sorted by path for deterministic ordering). Enumeration globs every `*.md` under the `plan-details/<slug>/` directory, so it is deliberately broader than `detail.py`'s per-step `derive_detail_path` set: an orphan detail file (a `.md` whose owning step was deleted) or any extra `.md` in the bundle dir is folded into the hash too, and a step whose expected detail file is absent simply contributes nothing. The glob set is therefore a **superset** of the per-step set; only when the bundle is well-formed (every step's detail file present, no orphans) do the two coincide. `review_persistence.py` stays a leaf — the bundle enumeration re-derives the `plan-details/<slug>/` convention itself rather than importing `detail.py`'s `derive_detail_path`/`derive_step_slug`, so this is a deliberate duplication of that path convention (the two derivations must be kept in sync) and not reuse; `code_fingerprint` is stored and loaded as an **opaque `dict[str, str]` (path → sha256)** so the leaf module carries no knowledge of `Plan`, `scope_guard`, or `drift_detection`. `load_review` tolerates older sidecars lacking either field via a presence marker, not dict-emptiness: a never-computed `code_fingerprint` (absent in a legacy sidecar) is treated as stale, while a computed-but-empty map (a docs-only or all-`(new)` plan) stays reusable on a plan-only fingerprint match; an empty `plan_fingerprint` string is likewise treated as stale.

The code fingerprint is computed one layer up, where the `Plan` is already parsed and `scope_guard` is importable. `drift_detection._compute_content_hash` is promoted to a public `compute_content_hash(path)` (it already streams a SHA-256 digest and returns `None` for missing/unreadable files — exactly the semantics needed). A new `compute_code_fingerprint(plan, plan_path, repo_root)` in `completeness_report.py` enumerates the code surface via `scope_guard.compute_drift_watched_paths` (which deliberately **excludes** the plan + detail files already covered by `plan_fingerprint`), hashes each existing file, and returns a `{repo_rel_path: sha256}` dict with sorted keys. Files declared `(new)` that don't exist yet are skipped at capture (matching the acquire-time "skip None" convention), so an unborn file isn't a phantom hash.

`write_completeness_report` is widened to accept both fingerprints and persist the union of correctness and completeness conceptual findings (not just completeness); `_persist_and_present_report` computes both fingerprints and passes `correctness_recs + conceptual_recs`. Because `completeness-apply` already filters to `source == "plan-completeness"` on load, widening the saved set is backward-compatible for that consumer.

A new `resolve_reusable_audit(plan_name, repo_root, *, plan_path, review_id=None)` locates the newest `-completeness.json` sidecar (or a specific one by `--reuse-audit-id` stem), loads it, recomputes **both** the current plan fingerprint and the current code fingerprint, and returns a result carrying the loaded `SavedReview`, its saved conceptual recommendations split by axis, `fresh: bool` (`plan_fingerprint` match **AND** `code_fingerprint` match), and a `drifted_code: list[Path]` diff of the code map (changed = hash differs, **deleted** = was present and is now gone, **new** = a `(new)` entry that has since landed). Unlike the live-edit `check_drift`, deletions are reported here — a vanished in-scope file is a genuine staleness signal across a save/reload boundary, not a non-event. `resolve_reusable_audit` returns `None` when no sidecar exists, locating saves via `list_saved_reviews` and a `-completeness.json` name filter rather than re-globbing. An unresolvable `--reuse-audit-id <stem>` (a typo'd or deleted pin) finds no matching name in that filtered list — `resolve_reusable_audit` returns `None` with a one-line note rather than surfacing a traceback, so a bad pin falls back cleanly to a fresh audit.

The CLI gains `--reuse-audit` / `--no-reuse-audit` (a `BooleanOptionalAction` whose unset default means "prompt interactively") and `--reuse-audit-id STEM` on the `completeness-audit` subparser. A reuse-decision helper honors `--no-reuse-audit` (never), `--reuse-audit` (reuse when fresh, warn-and-skip when stale), and the default interactive prompt (`Reuse saved conceptual audit from <ts>? [Y/n]`) following the `_confirm_repo_root` pattern — auto-accepting under `--yes` or a non-TTY stdin; a stale fingerprint always declines and prints a one-line note. An explicit `--reuse-audit` when no saved sidecar exists at all (distinct from a bad `--reuse-audit-id` pin) falls back to a fresh audit with a one-line note rather than erroring. Under `--json` (or any machine-output mode) the reuse decision is forced non-interactive — the prompt is never emitted and the decision follows the `--reuse-audit` / `--no-reuse-audit` / auto-accept rules directly — and the prompt string, decline note, and multi-line code-drift staleness warning are all routed to stderr so they never corrupt the machine-readable report on stdout. When the staleness is specifically a **code** drift (`code_fingerprint` mismatch with `drifted_code` non-empty), the decline note is upgraded to a structured warning that names each drifted file with its owning step — reusing `drift_detection.render_attributed_path_line` + `scope_guard.build_file_to_step_map` (the same `path (step N: title)` rendering the live-edit drift warnings use) and closing with the `detail --reconcile` recovery hint. The warning is informational, never a non-zero exit (per the exit-code convention: failure-to-complete only). Reuse is wired into `cmd_completeness` (before `_sample_conceptual_audit`, substituting saved findings for the fresh sample while leaving the deterministic battery untouched) and into `_run_iterate_convergence_loop` (gating the single up-front `audit_plan_until_stable` call, seeding `_audit_recs` from the saved sidecar so the correctness-apply and deferred/advisory accounting work identically against reused `Recommendation` shapes with stable ids). An explicitly passed `--audit-samples N` takes precedence over auto-accepted reuse: it signals the operator wants a fresh sample, so it suppresses the `--yes` / non-TTY auto-accept and forces a fresh audit (the default sample count does not), while an explicit `--reuse-audit` still wins over it. A reuse-accepted **audit-only** run still renders and presents the grouped report to the console, but skips the whole `write_completeness_report` call — persisting no new `.md` report and no new `.json` sidecar (no new timestamp, no recomputed fingerprints), so reuse is idempotent. An operator who relies on the saved markdown should therefore expect no new dated `.md` on a reuse-accepted run; the prior run's report and sidecar remain the on-disk artifacts. The "newest" sidecar pointer stays stable across repeated reuse runs and the un-GC'd reports dir does not grow on reuse. This idempotent-skip applies only to the no-mutation audit-only path. A reuse-accepted `--iterate` run is *not* idempotent: correctness-apply edits the plan, so after that mutation it rewrites a fresh fingerprinted sidecar capturing the post-apply plan and code state. This rewrite re-fingerprints without re-deriving the findings — `_audit_recs` is seeded from the reused pre-apply audit and is not re-audited after correctness-apply — so the rewritten sidecar deliberately pairs post-apply `plan_fingerprint`/`code_fingerprint` with pre-apply-derived findings. This is a known provenance limit: the next run treats those findings as fresh against the post-apply plan though they were never audited against it. Closing it (a post-apply re-audit before the rewrite) is out of scope here.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — Official reference for add_argument and BooleanOptionalAction, needed to wire the --reuse-audit/--no-reuse-audit toggle and --reuse-audit-id STEM flags with an unset-default sentinel.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Defines the hash constructors and update/hexdigest interface used to build the deterministic content-hash fingerprint over the plan file and its detail bundle.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Documents adding a field with a default value (plan_fingerprint: str = "") to SavedReview so legacy sidecars deserialize without error.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Reference for serializing/deserializing the widened JSON sidecar that persists both conceptual axes plus the fingerprint, and for tolerating missing keys on load.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — Covers path globbing, sorting, and resolution used to enumerate the per-step detail bundle deterministically and locate the newest -completeness.json sidecar.
- [os.path — Common pathname manipulations / sorted()](https://docs.python.org/3/library/functions.html#sorted) — Built-in sorted() reference for the deterministic path ordering that guarantees a stable fingerprint regardless of filesystem enumeration order.
- `plan_tool/drift_detection.py` (in-repo) — source of `compute_content_hash` (the streamed SHA-256 helper promoted from `_compute_content_hash`) and the `render_attributed_path_line` warning renderer reused by the code-drift staleness warning.
- `plan_tool/scope_guard.py` (in-repo) — `compute_drift_watched_paths` enumerates the `step.all_files` code surface (minus plan/detail) for the code fingerprint, and `build_file_to_step_map` supplies the per-step attribution in the warning.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Caching or reusing the deterministic well-formedness battery — these checks are cheap and must reflect current disk state, so they always re-derive.
- Changing `completeness-apply`'s consumption — it continues to load and walk only the `plan-completeness` subset from the widened sidecar.
- Surfacing the `code_fingerprint` staleness warning outside `completeness-audit` (e.g. on `run` / `review` / `jira` reload). The fingerprint lives in the completeness sidecar for this plan; promoting it to a plan-level manifest that every reload path consults is a worthwhile follow-up but a separate, broader change.
- Git-aware drift shortcuts (recording `git rev-parse HEAD` at capture and pre-filtering with `git diff --name-only`). Per-file hashing is the source of truth here (it catches uncommitted edits a diff-against-HEAD would miss); a git fast-path is a later optimization.
- Auditor/prompt-version invalidation. The freshness verdict keys only on plan and code content, not on the `plan-tool` or audit-prompt version that produced the saved findings — so a sidecar persisted before a tool/prompt upgrade can be reused with conceptual findings from the prior auditor version. Because sidecars are never GC'd (deferred), operators must manually delete stale sidecars (or pass `--no-reuse-audit`) after an upgrade; folding an auditor/prompt-version component into the fingerprint is a separate follow-up.
- Persisting a sidecar under `--json`. `cmd_completeness` returns inside the `if args.json:` branch before `_persist_and_present_report`, so a `--json` run reads reuse but never writes or refreshes the sidecar — sidecars persist only on the non-`--json` path. `--json` reuse therefore depends on a prior interactive (non-`--json`) run having bootstrapped the cache, and a `--json` re-audit never supersedes a stale sidecar. Persisting under `--json` is a separate change.

## Risks

- A reused audit could mask plan changes if the fingerprint is too coarse; mitigated by hashing the plan file plus every per-step detail file in the bundle, so any edit invalidates the cache.
- A reused audit could mask **code** changes the audit was reasoned against, since `plan_fingerprint` alone is blind to a codebase that moved under an unchanged plan; mitigated by the per-file `code_fingerprint` over `step.all_files`, folded into the `fresh` verdict (reuse requires plan AND code match) and surfaced as a per-file drift warning when it mismatches.
- Legacy fingerprint-less sidecars could break loading; mitigated by `load_review` defaulting `plan_fingerprint` to empty string (treated as stale) and distinguishing a never-computed `code_fingerprint` (absent in a legacy sidecar, stale) from a computed-but-empty map (a docs-only / all-`(new)` plan, reusable on a plan-only match) via a presence marker rather than dict-emptiness (forces a fresh audit only when the marker is absent).
- A deleted in-scope file could be silently dropped (the live-edit `check_drift` ignores deletions); mitigated by `resolve_reusable_audit` diffing the saved map's keys against current disk and reporting a missing key as drift, so a reload after a file is removed declines reuse.
- Widening the saved set to both axes could regress `completeness-apply`; mitigated because that consumer already filters to `source == "plan-completeness"` on load.
- Reuse on the `--iterate` path could diverge from a fresh audit if reused recs differ in shape; mitigated by seeding `_audit_recs` with the same `Recommendation` shape and stable ids the fresh audit produces.

## Testing

Unit tests cover `compute_plan_fingerprint` stability (same inputs → same hash; a changed detail file → different hash), the bundle-derivation sync guard (for a well-formed bundle the set of detail files `compute_plan_fingerprint` globs equals the set `detail.py`'s `derive_detail_path` produces for the plan's steps; in general the glob set is a superset, so the guard asserts the per-step set is a subset of what the fingerprint hashes — pinning the deliberate duplication of the `plan-details/<slug>/` convention so neither derivation can silently drop a step's detail file, while orphan/extra `.md` files are tolerated as extra hashed inputs), `compute_code_fingerprint` (per-file map over `step.all_files`; a changed code file → different value at that key; a `(new)` file absent at capture → skipped, then present on recompute → reported as new; a deleted in-scope file → reported as drift; sorted-key determinism), the promoted `compute_content_hash` (round-trips the old `_compute_content_hash` behavior), the both-axes + both-fingerprints sidecar write/read round-trip, `load_review` tolerance of fingerprint-less legacy sidecars (empty string + empty dict → stale), and `resolve_reusable_audit` freshness verdicts (fresh, stale-by-plan, stale-by-code, missing, pinned-by-id, with the correct `drifted_code` set) — in `tests/test_review_persistence.py`, `tests/test_drift_detection.py`, and `tests/test_completeness_report.py`, using `tmp_path` and stubbing no Claude.

Integration tests in `tests/cli/test_completeness_cmd.py` drive `main(["completeness-audit", ...])` twice through stubbed invokers: the first run saves a both-axes + both-fingerprints sidecar; the second run with reuse accepted issues zero conceptual-audit invocations and still emits a complete report; an edited plan between runs makes the second run re-audit (stale-by-plan); **editing a `step.files` code file between runs makes the second run re-audit (stale-by-code) and print the attributed per-file drift warning; deleting an in-scope file is likewise flagged**; `--no-reuse-audit` always re-audits and `--reuse-audit-id` pins a specific save. The same reuse is exercised on the `--iterate` path. Per CLAUDE.md, these are integration-tier because they drive the CLI entry point end to end across modules; stub the invokers so no real `claude` binary is spawned.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — integration tests added with the implementation; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- After an audit-only `completeness-audit` run, the JSON sidecar under `plan-details/<slug>/reports/<ts>-completeness.json` contains both `plan-correctness` and `plan-completeness` findings, a non-empty `plan_fingerprint`, and a `code_fingerprint` map keyed by the repo-relative `step.all_files` paths that exist on disk.
- Every per-step detail file `detail.py`'s `derive_detail_path` produces for the plan's steps is a member of the set `compute_plan_fingerprint` globs for its hash (equality holds for a well-formed bundle; the glob set is otherwise a superset that also folds in orphan/extra `.md` files), pinning the deliberate duplication of the `plan-details/<slug>/` convention so a drift in either derivation can't silently omit a step's detail file from the fingerprint.
- A second `completeness-audit` run on an unchanged plan AND unchanged code detects the saved sidecar and, when reuse is accepted, completes its conceptual layer with zero new Claude audit calls while still running the full deterministic battery from disk.
- Editing the plan body or any per-step detail file between runs changes `plan_fingerprint`, so the second run reports the saved audit as stale and re-runs the conceptual audit; a one-line note explains the plan changed.
- Editing (or deleting) any in-scope code file from `step.all_files` between runs changes `code_fingerprint`, so the second run reports the saved audit as stale, re-runs the conceptual audit, and prints a structured warning naming each drifted file with its owning step (`path (step N: title)`) and the `detail --reconcile` recovery hint — without a non-zero exit.
- Reuse requires BOTH fingerprints to match: a plan-only change, a code-only change, or both decline reuse.
- `--no-reuse-audit` always re-runs the conceptual audit; `--reuse-audit` reuses when fresh and warns-then-re-audits when stale; `--reuse-audit-id <stem>` pins a specific saved sidecar.
- Under `--yes` or a non-TTY stdin, a fresh detected sidecar is reused without prompting; in an interactive TTY the operator is prompted `Reuse saved conceptual audit from <ts>? [Y/n]`.
- Under `--json` (or any machine-output mode) the reuse decision is forced non-interactive (no prompt emitted), and the prompt string, decline note, and code-drift staleness warning are routed to stderr so stdout carries only the machine-readable report.
- Reuse works identically on the `--iterate` path: the single up-front audit is seeded from the saved sidecar, and the correctness-apply loop runs against the reused findings.
- `completeness-apply` still loads and walks only the `plan-completeness` subset from the widened sidecar with no behavior change.
- `load_review` reads a legacy sidecar lacking `plan_fingerprint`/`code_fingerprint` without error and treats it as stale (empty string + empty dict → forces a fresh audit).
- Deterministic well-formedness findings are never loaded from a sidecar — they are always recomputed from the on-disk plan.
- `docs/AUDIT_RESUME_FLOW.md` no longer states unconditionally that there is no audit cache; it describes the plan-and-code fingerprinted conceptual-audit reuse and the still-re-derived deterministic layer.

## Deferred

- Partial / section-level reuse — the fingerprint is whole-bundle, so any edit invalidates the entire cache; reusing the unaffected subset of a stale audit is a separate, larger effort.
- Garbage-collection of old `-completeness.json` sidecars — accumulation is left to manual cleanup for now; automatic pruning is a separate concern.
- Sharing a reuse cache across plans or repos — the sidecar stays per-plan to preserve per-project scoping; cross-plan reuse is postponed.
