> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Point the BLOCKED next step at `plan-tool detail` on a bare plan instead of `split`

## Summary

Make the BLOCKED remedy in `plan_tool/completeness_report.py` aware of whether the plan is bare. Today both next-step renderers turn every BLOCKED apply verdict into a `plan-tool split` recommendation; on a bare plan the real remedy is almost always "author the step's detail file". After this step, a bare-plan BLOCKED bullet leads with `plan-tool detail <name>` in the report prose (`_blocked_next_step`) and in the console command block (the BLOCKED branch of `suggested_next_step_commands`), keeping `split` as the second option; a fully-detailed plan's output is unchanged. The key decision: the branch keys on the plan-level bare flag only — never on which step an individual finding sits on, and never on the jira-grade half of the fence. On green, an operator who hits BLOCKED on a bare plan is told to write the missing detail file rather than to restructure a step.

## Table of Contents

- [Summary](#summary) — what changes and what stays the same.
- [Why](#why) — the renderer that contradicts the apply prompt, and why the defect is already live.
- [Input](#input) — the contracts this step reads: the bare flag, the BLOCKED verdict, the apply prompt's rule.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches.
- [Implementation](#implementation) — where the branch goes, the wording it must carry, the rules that are not free to vary, and the sites left alone.
- [Tests](#tests) — the new cases and the regression net that must stay green untouched.
- [Acceptance criteria](#acceptance-criteria) — checkable facts.
- [References](#references) — what to read before starting.
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step.
- [Deferred](#deferred) — nearby work this step does not take, and who owns it.

## Why

`plan_tool/prompts/apply-finding.md` tells the model two things about BLOCKED: don't create new files, and *"If a finding requires a new file (e.g., a missing detail file), emit `BLOCKED` with a one-line note — there's a separate command (`plan-tool detail`) for those."* The report renderer ignores that. `_blocked_next_step` opens with "`apply` can't add or restructure steps" and then prints one `plan-tool split <name> --step N --into … --into …` per flagged step; `suggested_next_step_commands` prints the same commands with the description "BLOCKED — split into sub-steps (apply can't; see report)". So the one case the prompt explicitly routes to `plan-tool detail` renders as "split this step".

**This already fires at HEAD.** `suggested_next_steps` appends `_blocked_next_step` whenever `applied` carries a BLOCKED outcome, with no bare gate on that append, and a bare plan under `--iterate` still runs the deterministic applies — only `DETAIL_LEVEL_FINDING_SOURCES` are filtered out of `open_findings`, not the whole set. So a bare `--iterate` run whose deterministic apply comes back BLOCKED gets the split-first bullet today. Do not write this step as fixing a latent defect; it fixes a live one, and the tests must cover the iterate path that reaches it rather than assuming the conceptual route is the only trigger.

Step 4 and step 2 make it *more* reachable, not reachable for the first time: they add the conceptual-correctness applies to a bare plan, and a bare plan is exactly where "the finding needs a detail file that doesn't exist" is the most likely reason apply gives up. Without this step, the route those steps open leads with a structural remedy for a plan that simply hasn't been detailed yet — restructuring a step that was fine. That is why the three ship together.

## Input

- **The renderers' bare flag.** Both `suggested_next_steps` and `suggested_next_step_commands` derive bareness from the `bundle_status` parameter via a defensive `getattr(bundle_status, "is_bare", False)` — the parameter defaults to `None` and the suites pass a `SimpleNamespace`. Step 1 pulled the apply fence into one helper and step 2 split that helper by axis, so **read the landed code before editing**: if the helper now owns the `is_bare` read, take the flag from there rather than adding a second read. One bare fact per renderer, used by both the fence and the BLOCKED branch — two reads that could disagree is the defect to avoid.
- **`DetailBundleStatus`** (`plan_tool/review.py`, built by `audit_detail_bundle_status`). `is_bare` is `True` when at least one step has no detail file. It also carries `bare_step_ids` and `is_fully_bare`; this step reads **neither** (see Implementation).
- **`AppliedOutcome.verdict`** — the `"BLOCKED"` string this step's branch triggers on. Findings reach it as `AppliedOutcome` records, filtered at the top of each renderer.
- **`_blocked_split_targets`** — resolves the distinct `(step_id, step_title)` pairs a BLOCKED set points at, using `plan` for titles. Unchanged by this step; the bare branch still uses it for the secondary `split` lines.
- **`plan_tool/prompts/apply-finding.md`** — the contract the new wording must agree with: rule 5 in its edit rules (don't create files; `plan-tool detail` owns those) and the `BLOCKED` bullet in its `## Verdict` section.
- **What this step cannot check.** Nothing tells the renderer *why* a given finding came back BLOCKED — the verdict carries a free-text summary, not a reason code. The bare branch is a plan-level guess about the likely cause, which is why `split` stays available rather than being replaced.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — add a bare-plan branch to `_blocked_next_step` (new keyword-only parameter, defaulting to the current behavior) and pass the flag from `suggested_next_steps`; add the matching branch to the BLOCKED block inside `suggested_next_step_commands`.
  - `tests/test_completeness_report.py` — new cases under the existing `# ---------- suggested_next_steps ----------` and `# ---------- suggested_next_step_commands ----------` banners.

## Implementation

**What must be true when this is done**

- On a bare plan, both renderers name `plan-tool detail <name>` as the first remedy for BLOCKED findings, and neither describes `split` as *the* fix.
- On a plan that is not bare (including `bundle_status=None`), both renderers emit exactly what they emit today — same text, same commands, same order.
- The two renderers name the same remedies in the same order. They describe one audit run; any difference between them is a reporting defect (the plan's Risks section says so).

**Recommended shape**

- **Give `_blocked_next_step` a keyword-only `bare_plan: bool = False`.** It is module-private with one caller, so the default keeps every other path untouched and makes the diff small. `suggested_next_steps` passes the flag it already computes.
- **On the bare branch, restructure the block, don't append to it.** The headline currently blames "apply can't add or restructure steps"; on a bare plan the honest headline is that apply never creates files and the step's detail file doesn't exist yet. Then:
  - first sub-line: author the missing detail file(s) — `plan-tool detail <name>`;
  - then the existing per-step `split` sub-lines, reworded so they read as the *other* possibility rather than the fix;
  - then the existing new-step fallback line.
- **In `suggested_next_step_commands`, the BLOCKED block gains the same two-arm shape.** Bare: emit `("plan-tool detail <name>", "…")` first, then the per-step `plan-tool split <name> --step <id>` tuples with a description that no longer claims splitting is the remedy. Not bare: unchanged.
- **Keep the command plan-level — no `--step N` on the detail command.** `plan-tool detail <name>` already covers every step lacking detail and skips steps whose file exists (`diagnostic_remedies` states this in its `detail-coverage` remedy; keep the two claims consistent). Adding `--step N` would mean deciding which step a finding belongs to, which the plan refuses.
- **This is the one shape in which the verb may appear.** The plan's `## Architecture` rule: `plan-tool detail` is named on a bare plan only as the unblock for a **specific** BLOCKED or withheld finding. Here it is the remedy for a concrete BLOCKED verdict, which is exactly that shape. It must not read as "author details to unlock apply" — a blanket detail-coverage instruction is the contract this plan exists to replace, and step 5's block deliberately names the verb nowhere because it has no per-finding blocker to unblock. Word the bullet so the reader sees the blocked finding, not a precondition.

**Rules that are not free to vary**

- **Key on the bare flag alone, never on the fence result.** After step 2 the tempting variable in scope is whatever the fence helper returns, and the old `unappliable` folded jira grade in. Jira grade's reason (no sidecar to replay) says nothing about which remedy a BLOCKED wants, so mixing them would change jira-grade output — which the plan puts out of scope.
- **Do not read `bare_step_ids` or `is_fully_bare`.** `bare_step_ids` appears zero times in `plan_tool/completeness_report.py` today and must stay that way. Routing per finding is refused at plan level with a measurement behind it; a partially-detailed plan takes the same bare branch as a fully-bare one.
- **Emit `plan-tool detail <name>` at most once per console block.** It holds today for a non-obvious reason: on a bare plan the renderer already filters `DETAIL_LEVEL_DIAGNOSTIC_SOURCES` (which includes `detail-coverage`) out of `diagnostic`, so the existing `detail-coverage` command branch cannot fire there. Preserve that — a second, differently-worded `plan-tool detail p` line in one block reads as two different actions.
- **The code-drift `reconcile-plan` command/bullet stays first.** It is emitted before the BLOCKED block in both renderers and that ordering is pinned by existing tests.
- **Every command string must parse against the live CLI parser.** `plan-tool detail <name>` does; the existing parse guard in the suite exercises this and should be extended to the bare path.
- **Don't extract shared wording between the two renderers.** Step 1 already spent its extraction on the fence; folding a second one in here would make this step a refactor plus a feature.

**Sites checked and deliberately left alone**

- `console_summary`'s blocked count line — it already says "needs a new step/detail file apply can't create — see next steps" and recommends nothing structural, so it needs no change. Its *conceptual-completeness* line does need an axis split, but that is **step 2's** edit in the same module, not this step's; leave the whole function alone here.
- `_blocked_split_targets` — the step-resolution helper is correct for both arms; only its callers' framing changes.
- The `plan-tool split` recommendations produced elsewhere (`plan_tool/review.py`'s structural-split remedy prose, `plan_tool/convergence_diagnosis.py`'s localized fork, `plan_tool/launcher.py:escalate_to_split`) — those fire on structural findings, not on a BLOCKED apply verdict, and a genuinely over-packed step wants a split whether or not the plan is bare. See Deferred.

**Rejected alternative:** dropping the `split` lines entirely on a bare plan. It reads cleaner, but a bare plan can still hold an over-packed step, and losing the option means the operator has to re-derive it. The plan's Architecture decision 2 asks for demotion, not removal.

## Tests

All cases live in `tests/test_completeness_report.py` and use the existing `_steps(**kw)` / `_cmds(**kw)` helpers plus `SimpleNamespace(is_bare=…)` for `bundle_status`, matching the bare cases already in the file.

### Tests for this step

Report prose (`suggested_next_steps`):

- `test_next_steps_blocked_leads_with_detail_on_bare_plan` — with a BLOCKED outcome and `is_bare=True`, the blocked block names `plan-tool detail p` before any `plan-tool split`.
- `test_next_steps_blocked_headline_names_the_missing_detail_file_on_bare_plan` — the headline explains apply is blocked on a file it can't create, not on "can't restructure steps".
- `test_next_steps_blocked_keeps_split_as_secondary_on_bare_plan` — the per-step `split` sub-line is still present, after the detail line.
- `test_next_steps_blocked_bare_plan_still_names_the_specific_step_for_split` — with a `plan` in hand, the secondary split sub-line still carries `--step <id>` and the step title.
- `test_next_steps_blocked_unchanged_on_detailed_plan` — `is_bare=False` produces the same blocked block as `bundle_status=None`, and `split` leads.
- `test_next_steps_blocked_from_a_deterministic_apply_leads_with_detail_on_bare_plan` — the BLOCKED outcome carries a deterministic finding's source rather than a conceptual one. Pins that the bare branch keys on the verdict and the bare flag, not on which source produced the apply — the path a bare `--iterate` run already reaches at HEAD.

Console commands (`suggested_next_step_commands`):

- `test_next_step_commands_blocked_bare_plan_emits_detail_first` — `plan-tool detail p` is the first command.
- `test_next_step_commands_blocked_bare_plan_keeps_split_after_detail` — the `plan-tool split p --step <id>` tuples still follow, with a description that doesn't call splitting the fix.
- `test_next_step_commands_blocked_bare_plan_emits_detail_once` — two BLOCKED findings on different steps still produce exactly one `plan-tool detail p` line.
- `test_next_step_commands_blocked_detailed_plan_unchanged` — `is_bare=False` keeps `split` first and emits no detail line.
- `test_next_step_commands_code_drift_precedes_bare_blocked_detail` — with drift plus a high-severity finding, `plan-tool reconcile-plan p` still comes before the bare-plan detail command.
- `test_next_step_commands_bare_blocked_parse_against_live_parser` — every command emitted on the bare BLOCKED path parses through `plan_tool.cli.build_parser()` (the bare-plan companion to the existing parse guard, which sets no `bundle_status`).

**Green-before-done gate:** every case above must pass, and the whole of `tests/test_completeness_report.py` must be green — including the cases this step must *not* disturb: `test_next_steps_blocked_points_at_new_step_workflow`, `test_next_steps_blocked_names_specific_step_when_plan_given`, `test_next_steps_blocked_falls_back_to_placeholder_without_step`, `test_next_step_commands_order_urgent_first`, `test_next_step_commands_parse_against_live_parser`, `test_next_step_commands_code_drift_reconcile_precedes_blocked`, and the bare-plan suppression cases. None of them passes `bundle_status`, or passes `is_bare=False`, so this step should add tests without rewriting any.

## Acceptance criteria

- `suggested_next_steps(..., applied=[<BLOCKED>], bundle_status=SimpleNamespace(is_bare=True))` returns a blocked block whose index of `plan-tool detail p` is lower than its index of `plan-tool split p`.
- The same call with `is_bare=False` returns a blocked block equal to the one returned with `bundle_status=None`.
- `suggested_next_step_commands(..., applied=[<BLOCKED>], bundle_status=SimpleNamespace(is_bare=True))` returns `plan-tool detail p` as its first command (or first after the drift command), and contains exactly one command equal to `plan-tool detail p`.
- The same call with `is_bare=False` returns `plan-tool split p --step …` first and no `plan-tool detail p`.
- Every command string produced on the bare BLOCKED path parses via `plan_tool.cli.build_parser()`.
- `grep -c "bare_step_ids\|is_fully_bare" plan_tool/completeness_report.py` is `0`.
- No emitted `plan-tool detail` command carries `--step`.
- `uv run pytest tests/test_completeness_report.py -q` is green.

## References

- `plan_tool/completeness_report.py` — `_blocked_next_step`, `_blocked_split_targets`, the BLOCKED block in `suggested_next_step_commands`, and `diagnostic_remedies`' `detail-coverage` wording to stay consistent with.
- `plan_tool/prompts/apply-finding.md` — the BLOCKED contract this step's wording must agree with: the don't-create-files rule that routes a missing detail file to `plan-tool detail`, and the `BLOCKED` bullet under `## Verdict`.
- `plan_tool/review.py` — `DetailBundleStatus` and `audit_detail_bundle_status`, which compute the bare flag this step routes on.
- `plan_tool/cli/completeness_phases.py` — the caller that passes `bundle_status` into both renderers; also the grouped report's own next-steps list, which step 5 owns.
- `docs/AUDIT_FLOW.md` — the audit flow's gate/sequence reference for where these renderers sit; updated by step 7, not here.

## Applicable guardrails

- **The plan's "## Out of scope", per-finding coverage routing refusal** — this step's branch reads the plan-level bare flag only. It may not resolve a finding to a step to decide the remedy, and may not read the per-step bare id list.
- **The plan's "## Out of scope", jira-grade behavior** — the new branch must not change any output at jira grade, which means keying on bareness alone rather than on the combined fence.
- **The plan's "## Out of scope", no new gate / exit-code flip / blocking severity** — this step changes rendered text and command order only. Nothing it adds may affect an exit code or a finding's severity.
- **The plan's "## Risks", the surfaces describing one run must stay in step** — apply the change to both `suggested_next_steps` and `suggested_next_step_commands` in this step; leaving one behind is the drift the plan names as a defect in itself. These are two of the six surfaces that bullet lists.
- **The plan's "## Architecture", decision 2** — `split` is demoted on a bare plan, not removed.
- **The plan's "## Architecture", when `plan-tool detail` may be named on a bare plan** — as the unblock for this specific BLOCKED finding, never as a detail-coverage remedy. The wording must not read as a precondition on applying anything.
- **The plan's "## Out of scope", walk-time BLOCKED** — a BLOCKED verdict returned *during* the apply walk surfaces through `plan_tool/cli/review_actions.py` with the apply prompt's own note, which already names `plan-tool detail`. That surface is out of scope; this step covers the audit's next-step renderers only, and must not grow to reach it.
- **The step's intent** — stop the tool recommending a restructure when the remedy is to author a detail file. Anything past that framing change belongs to another step.

## Deferred

- **Making `completeness-apply` actually walk correctness gaps on a bare plan** — step 4 owns it in `plan_tool/cli/completeness_cmd.py`, and it has already landed by the time this step runs.
- **Walk-time BLOCKED verdicts** — a BLOCKED returned inside step 4's walk renders through `plan_tool/cli/review_actions.py` as `apply-finding BLOCKED: <note>`, carrying the apply prompt's own note. The plan's `## Out of scope` accepts that as sufficient; this step does not widen to cover it.
- **`console_summary`'s conceptual-completeness line** — the same module, but step 2's edit. This step leaves the whole function alone.
- **The grouped report's bare-plan next-steps list** — step 5 owns it in `plan_tool/cli/completeness_phases.py`; this step touches neither file.
- **Narrowing bare-step edge-case findings in the audit prompt** — step 6, in `plan_tool/review.py`.
- **Updating `CLAUDE.md`, `docs/AUDIT_FLOW.md`, and `BACKLOG.md` #83** — step 7's docs sweep.
- **The other `plan-tool split` producers** (`plan_tool/review.py`'s structural-split remedy, `plan_tool/convergence_diagnosis.py`'s localized fork, `plan_tool/launcher.py:escalate_to_split`) — they fire on structural findings rather than a BLOCKED apply verdict, and their advice stays correct on a bare plan. Unchanged here; no follow-up implied.
- **The per-finding `Address:` line and the conceptual-completeness bare wording in `build_report_md`** — that is the apply fence's surface, settled by step 2.
- **Naming a specific `--step N` on the emitted detail command** — refused at plan level (it needs per-finding step resolution the data doesn't support), not follow-up work.
- **Extracting shared BLOCKED wording between the two renderers** — a refactor, and folding it in would make this step mixed. If it looks worth doing after the branch lands, file it in `BACKLOG.md`.
