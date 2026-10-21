> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Document concept ownership integrations and update the backlog

## Summary

Document the shipped concept-ownership flow across `CLAUDE.md`, `RUNBOOK.md`, `CAPABILITIES.md`, and `docs/cli/README.md`, then reconcile `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree`. Treat explicit `Step.concept_ids` links and structured deferrals as the authoritative coverage contract; do not describe title, feature, or prose matching as an equivalent source. Verify the completed surfaces from steps 5–9 and the prerequisite concept-record core at HEAD before claiming they shipped. On green, maintainers, operators, capability validation, CLI readers, and backlog triage all describe the same implemented behavior.

## Table of Contents

- [Summary](#summary) — The documentation and backlog result.
- [Why](#why) — Why the completed ownership flow needs one consistent description.
- [Input](#input) — The shipped contracts and plan scope this step must verify.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation files and their expected edits.
- [Implementation](#implementation) — The verify-first documentation and backlog approach.
- [Tests](#tests) — Documentation checks for accuracy, navigation, and catalog validity.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Repository sources that define the documented behavior.
- [Deferred](#deferred) — Work intentionally left outside this docs-only step.

## Why

The concept-record core and steps 5–9 leave concept coverage spread across authoring, completeness, and structural-remedy surfaces, while the repository guides and `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree` still describe the earlier title-slug linkage gap and an unimplemented design. That stale description would send maintainers toward the wrong ownership rule and leave operators without a clear workflow for reviewing concepts or understanding missing-link findings. This step closes the documentation gap only after the shipped symbols are confirmed at HEAD.

## Input

- **Execution prerequisite — concept-record core:** verify the landed public concept-tree reader, writer, navigator, synchronization contract, and `scope-review` command before documenting their names. The prerequisite owns those mechanisms; this step only explains their supported use.
- **Step 5 — completeness:** verify that the implemented concept finding uses explicit ownership or structured deferral and follows the blocking, non-apply-eligible routing described by step 5.
- **Steps 6 and 7 — split and merge:** verify that split conserves the source concept-ID set and merge derives the ordered, deduplicated union.
- **Step 8 — re-grounding:** verify that mark-done and re-baseline behavior preserve each source step’s ownership.
- **Step 9 — scope-out:** verify that carved concepts with no committed surviving owner become structured deferrals and that forward-seeds retain concept IDs.
- **Plan scope:** use `docs/implementation-plans/2-concept-signoff-integrations.md:Out of scope` and `docs/implementation-plans/2-concept-signoff-integrations.md:Deferred` to avoid claiming prose inference, mandatory ownership on legacy plans, or post-signoff concept editing.
- **Backlog source:** treat `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree` as the entry to reconcile. Preserve accurate origin and design context while removing or rewriting claims that the explicit ownership maintainer is missing.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `CLAUDE.md` — add a sibling Architecture paragraph for the concept sign-off subsystem, naming its command, persisted ownership link, completeness sources, and structural-remedy invariants.
  - `RUNBOOK.md` — add an operator walkthrough for reviewing and changing concept decisions, interpreting ownership findings, and understanding how structural remedies preserve or defer concepts; add matching links under `RUNBOOK.md:Table of contents`.
  - `CAPABILITIES.md` — make the capability catalog own the shipped concept sign-off command and module surfaces with valid `MISSION.md` principle IDs.
  - `BACKLOG.md` — reconcile `#121 — Operator sign-off of a hierarchical deferred-concept tree` with the shipped core and ownership integrations, remove the resolved `coverage-linkage` gap, and update its status consistently with repository priority rules.
  - `docs/cli/README.md` — update the command index descriptions that summarize concept review and completeness so they agree with the generated per-command references and implemented explicit-link behavior.

## Implementation

- **Verify before writing.** Grep and read the landed implementation from the prerequisite and steps 5–9 before making any shipped claim. At minimum, confirm the concept-record public symbols, `plan_tool/schema.py:Step.concept_ids`, the concept completeness source in `plan_tool/review.py`, `plan_tool/create.py:_apply_step_split`, `plan_tool/create.py:_apply_step_merge`, `plan_tool/detail.py:split_step`, `plan_tool/detail.py:merge_steps`, `plan_tool/reground.py:mark_steps_done`, `plan_tool/reground.py:render_rebaseline_seed`, `plan_tool/scope_out.py:compute_narrow`, and `plan_tool/scope_out.py:scope_out_step`. If an expected surface is absent or differs materially, route the gap back to its owning implementation step instead of repairing production code here.

- **Use one foundational documentation rule.** Describe a signed-off concept as accounted for only when it has a valid explicit owner through `Step.concept_ids` or a valid structured deferral. Titles, `Step.features`, files, and detail prose may explain a concept but must not be documented as alternate ownership links.

- **Register the subsystem in `CLAUDE.md:Architecture`.** Add a paragraph modeled on the existing `CLAUDE.md:Granularity advisor`, `CLAUDE.md:Convergence diagnostic`, and `CLAUDE.md:Decision telemetry` entries. Name the landed concept leaf and `scope-review` surface, explain the signed-off sidecar and explicit step link, and state the key boundaries: legacy empty ownership remains parseable, missing coverage is reported rather than inferred, and structural remedies preserve ownership or record a deferral.

- **Write an operator workflow in `RUNBOOK.md`.** Place the concept-review walkthrough near `RUNBOOK.md:Workflow: completeness checks` and its structural-remedy guidance. Cover:

  - where create and detail present concept review;
  - how to reopen review with the landed `plan-tool scope-review <name>` form;
  - what unattended or non-TTY acceptance means compared with operator sign-off;
  - how `concept-coverage` and any landed unsigned-review finding appear during completeness;
  - why a missing explicit link requires ownership, sign-off, or a structured scope decision rather than `completeness-apply`;
  - how split, merge, re-ground, and scope-out affect concept ownership.

  Add the exact new heading to `RUNBOOK.md:Table of contents` using its GitHub-style anchor. Keep command examples aligned with the actual parser and generated command reference.

- **Keep capability ownership honest.** Update `CAPABILITIES.md` using its existing `id` / `surfaces` / `principles` format. Prefer extending the capability that owns the prerequisite concept sign-off feature if it already exists; add a new stable capability only if HEAD has no suitable owner. List only real command primary names and repo-root-relative module paths, and use only principle IDs declared in `MISSION.md`. The result must satisfy `plan_tool/capability_catalog.py:check_capabilities` without an `orphan-subcommand`, `absent-surface`, or `no-valid-principle` finding.

- **Keep the CLI index at summary level.** Update `docs/cli/README.md` only where its command descriptions need the new ownership contract. The `scope-review` row should point to the generated command page if the prerequisite command-registration step produced one. The completeness rows should say that signed-off coverage uses explicit owners or structured deferrals and that a blocking ownership gap is not mechanically applied. Do not hand-edit generated `docs/cli/<command>.md` files in this step.

- **Reconcile `BACKLOG.md:#121` as a completed capability.** Replace the stale “not implemented” and unresolved `coverage-linkage` language with a concise shipped-status account that credits both the prerequisite concept-record plan and `docs/implementation-plans/2-concept-signoff-integrations.md`. State that `Step.concept_ids` now has named maintainers across create, detail, completeness, split, merge, re-ground, and scope-out. Preserve still-true origin and risk context, but remove claims that title-slug matching is the coverage authority.

- **Apply backlog retirement rules only if nothing remains.** If HEAD confirms the core and all steps 1–9 are shipped and `#121` has no remaining work, retire it consistently: remove it from open-priority summaries and update any “highest open” or “next concrete pick” references that still point to it. If verified hardening remains, keep the entry open, label the remaining work by category rather than a shipped phase, and leave priority pointers on it. Do not invent a residual task merely to keep the entry open.

- **Check cross-document vocabulary.** Use the exact landed command names, finding sources, state names, and field names in all five files. In particular, do not alternate among “feature ownership,” “title coverage,” and “concept ownership” when referring to `Step.concept_ids`.

## Tests

- `verify_concept_surfaces_exist_at_head` — every shipped symbol, command, finding source, and module named by the edited docs exists and matches the described contract.
- `verify_claude_architecture_entry` — `CLAUDE.md:Architecture` names the concept subsystem, explicit ownership rule, completeness behavior, and structural-remedy invariants.
- `verify_runbook_concept_workflow` — `RUNBOOK.md` gives runnable review commands and explains interactive, unattended, completeness, and remedy behavior accurately.
- `verify_runbook_toc_anchor` — the new `RUNBOOK.md:Table of contents` link points to the exact concept-workflow heading.
- `verify_capability_catalog` — `plan_tool/capability_catalog.py:check_capabilities` reports no malformed capability, absent surface, invalid principle, or orphan command after the `CAPABILITIES.md` edit.
- `verify_cli_reference_index` — every concept-related row in `docs/cli/README.md` points to an existing generated command page and agrees with the live parser summary.
- `verify_backlog_121_status` — `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree` no longer says the verified ownership integration is missing or relies on title-slug coverage.
- `verify_backlog_priority_consistency` — open-item summaries and next-pick pointers agree with whether `#121` is retired or remains open.
- `verify_docs_use_explicit_links` — none of the five edited files describes titles, features, files, or prose as an authoritative substitute for `Step.concept_ids` or structured deferrals.
- `verify_declared_files_only` — the documentation diff changes only `CLAUDE.md`, `RUNBOOK.md`, `CAPABILITIES.md`, `BACKLOG.md`, and `docs/cli/README.md`.

### Verification (non-code step)

- Run the repository’s capability honesty check or its focused coverage in `tests/test_capability_catalog.py`.
- Run the CLI-reference drift coverage in `tests/cli/test_cli_reference.py`; do not regenerate or edit per-command pages unless verification proves an upstream command-registration step left them stale.
- Render or inspect every new Markdown link, with special attention to the hand-maintained `RUNBOOK.md:Table of contents` anchor.
- Compare all documented command forms with `plan-tool <command> --help`.
- Grep the edited files for stale phrases such as `title-slug`, `no maintainer`, `not implemented`, and the old `coverage-linkage` gap; retain them only when clearly labeled as historical origin rather than current behavior.
- Review the final diff against `docs/implementation-plans/2-concept-signoff-integrations.md:Out of scope` and `docs/implementation-plans/2-concept-signoff-integrations.md:Deferred`.

## Acceptance criteria

- `CLAUDE.md:Architecture` contains a concept sign-off subsystem entry grounded in the landed leaf, command, finding sources, and explicit ownership invariant.
- `RUNBOOK.md` contains an operator workflow for concept review and ownership findings, and its Table of Contents link reaches that heading.
- `CAPABILITIES.md` owns every shipped concept command named by the docs and passes `plan_tool/capability_catalog.py:check_capabilities`.
- `docs/cli/README.md` links every listed concept command to a real generated page and describes completeness coverage as explicit ownership or structured deferral.
- `BACKLOG.md:#121 — Operator sign-off of a hierarchical deferred-concept tree` records the verified shipped state, removes the resolved ownership-maintainer gap, and has priority pointers consistent with its open or retired status.
- All five edited documents use the same landed names for `Step.concept_ids`, structured deferrals, `scope-review`, and concept completeness findings.
- No edited document claims that title, feature, file, or prose similarity satisfies concept ownership.
- Verification changes no production code and no files outside the declared five-file scope.

## References

- [Concept Signoff Integrations plan](../2-concept-signoff-integrations.md) — Use its Architecture, Out of scope, Deferred, and Acceptance criteria as the scope authority for this documentation step.
- [Capability catalog implementation](../../../plan_tool/capability_catalog.py) — Use `check_capabilities` and its surface rules to validate the `CAPABILITIES.md` entry.
- [Plan schema](../../../plan_tool/schema.py) — Verify the landed `Step.concept_ids` contract before documenting explicit ownership.
- [Create integration](../../../plan_tool/create.py) — Verify create-time ownership and the shared split and merge transforms.
- [Detail integration](../../../plan_tool/detail.py) — Verify structured deferrals, regeneration, and the detail-level split and merge entry points.
- [Completeness review](../../../plan_tool/review.py) — Verify the exact concept finding sources, coverage rule, and apply-eligibility boundary.
- [Re-grounding](../../../plan_tool/reground.py) — Verify ownership preservation in mark-done and re-baseline paths.
- [Scope-out](../../../plan_tool/scope_out.py) — Verify last-owner deferral and forward-seed behavior.
- [CLI reference generator](../../../plan_tool/cli_reference.py) — Check which CLI files are generated and keep this step from hand-editing generated command pages.

## Deferred

- **Production-code fixes** — route any missing or mismatched implementation found during verification back to the owning prerequisite or step 5–9.
- **Generated per-command CLI pages and help goldens** — command-registration steps own those drift-guarded artifacts; this step updates only `docs/cli/README.md`.
- **New concept schemas, commands, findings, or lifecycle states** — they require plan-level implementation decisions and are outside this docs-only step.
- **Concept inference from prose or feature tags** — the plan explicitly rejects it as an ownership mechanism.
