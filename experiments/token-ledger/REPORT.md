# Token ledger: experiments 1-4 (read-only analysis)

Data: 942 run logs `.plan-tool/runs/*/*.jsonl` (45 plan slugs, 2026-08-03 to 2026-10-10), 1,480 `claude_call_end` events; `.plan-tool/telemetry/decisions.jsonl` (2,079 records, 1,214 `prompt-budget`); 2,092 saved `*-completeness.json` reports under `docs/`. No model calls were made. Scripts: `.tmp/token-ledger.ledger2.py`, `.tmp/token-ledger.samples.py`, `.tmp/token-ledger.blocks.py`, `.tmp/token-ledger.check.py`. "Measured" = summed from those files. "Estimate" = chars/4 or inference.

## Exp 1. Per-call-site ledger

**Method.** `claude_call_end` is authoritative (scripts/analyze_run_log.py). Each event carries `tokens_input`, `tokens_output`, `cache_creation_tokens`, `cache_read_tokens`, `cost_usd`, `duration_ms` (all present as fields on all 1,480 events; source: `plan_tool/run_log.py:229` `ClaudeCallEnd`). Command comes from the run's `run_start`; backend from the first `backend_spawn`.

**Accounting caveat (measured, important).** Codex events have `tokens_input >= cache_read_tokens` on 765 of 765 events, so Codex input INCLUDES cached tokens; non-cached = input - cache_read. Claude events have input exclusive of cache (`ti < cr` on 193 of 201), so non-cached = input + cache_creation. 326 events (`unattributed`) have no `backend_spawn` in the log (older logs, 2026-08-07 to 08-13); their accounting is not determinable (131 of them have input < cache_read, 194 are all-zero or Claude-style). For those I report input as logged. 42 events overall report zero usage (29 unattributed, 7 claude, 6 codex).

Ranked by non-cached input + output tokens (all backends; `nc` normalized as above):

| rank | command / phase | calls | non-cached in | cached in | output | nc+out | wall h | mean nc+out/call | claude USD |
|---|---|---|---|---|---|---|---|---|---|
| 1 | completeness / plan_audit | 712 | 177,661,491 | 1,445,672,869 | 15,469,705 | 193,131,196 | 67.5 | 284,434 | 619 |
| 2 | run / claude_call (step execution) | 155 | 72,918,646 | 895,137,714 | 3,919,199 | 76,837,845 | 19.8 | 495,728 | 191 |
| 3 | detail / detail-step-NN (authoring + its re-audits) | 220 | 60,221,889 | 418,682,235 | 4,905,403 | 65,127,292 | 19.8 | 296,033 | 198 |
| 4 | run-reconcile / claude_call | 278 | 42,436,853 | 231,054,645 | 1,844,949 | 44,281,802 | 10.7 | 159,862 | 71 |
| 5 | create / propose_steps | 43 | 21,097,804 | 112,917,722 | 873,101 | 21,970,905 | 4.9 | 563,356 | 57 |
| 6 | create / propose_references | 29 | 3,543,453 | 8,611,717 | 78,630 | 3,622,083 | 0.5 | 124,899 | 7 |
| 7 | create / propose_distilled_seed | 24 | 656,038 | 414,199 | 69,400 | 725,438 | 0.3 | 36,271 | 4 |
| 8 | create / propose_body_sections | 11 | 432,975 | 235,573 | 22,412 | 455,387 | 0.1 | 41,398 | 1 |
| 9 | create / propose_intents | 7 | 134,455 | 70,058 | 894 | 135,349 | 0.0 | 19,335 | 1 |

Total across all events: 406,814,704 nc+out tokens; cached input is 89.1% of all input tokens (measured, normalized). Source: `.tmp/token-ledger.ledger2.py` over the run logs. The by-family split (claude / codex-inclusive / unattributed) is in `.tmp/token-ledger.ledger2.out.md`; per-phase numbers differ 3-10x per call between families, so mean-per-call mixes backends and should not be read across rows.

**Unlogged call sites (no `claude_call_end`).** Mechanism: `shell._emit_call_end` drops the event when no sink is installed and warns once per process (`plan_tool/shell.py:996-1026`, `_warn_unsinked_call` at :968). Sites are logged only if the caller wraps the invoke in `bind_shell_sink` / `install_call_end_sink` and a run logger exists.

| call site | file:line | sink status | evidence |
|---|---|---|---|
| `launcher.apply_finding` (first + follow-up apply) | plan_tool/launcher.py:3073, :3224 | sink bound, but **0 `claude_call_end` in logs**: 26 `claude_call_start`/`phase_end` for `apply_finding_dispatch`, no end and no `backend_spawn` | measured; cause not determined. Wall-clock only: 26 phases, 0.43 h from `phase_end` |
| `create.assess_direct_source_split_from_claude` | plan_tool/create.py:4887 | start and phase_end logged, no end | measured: 7 starts, 0 ends, 0.02 h |
| `review.check_criteria_fulfillment` | plan_tool/review.py:6810 | no sink binding in function | static (no phase in logs) |
| `review.review_plan_full` | plan_tool/review.py:9645 | no sink binding | static |
| `review.extract_and_append_review_lessons` | plan_tool/review.py:9796 | no sink binding | static |
| `create.suggest_slug` | plan_tool/create.py:1451 | no sink binding | static |
| `create._propose_risk_profile_from_seed` | plan_tool/create.py:5865 | no sink binding found in function | static; verify |
| `jira.render_jira_export` | plan_tool/jira.py:3664 | no sink binding | static |
| `annotate.classify_plan_implementation` | plan_tool/annotate.py:751 | no sink binding | static |
| `lessons.find_lesson_equivalences` | plan_tool/lessons.py:1428 | no sink binding | static |
| `concept_tree.emit_concept_tree` | plan_tool/concept_tree.py:388 | no sink binding | static |
| `launcher._run_deep_for_step`, `run_all_done_steps` | plan_tool/launcher.py:3530, :3614 | no sink binding seen near the call | static; verify |
| `detail.extract_and_append_detail_lessons` | plan_tool/detail.py:7604 | bound (`distill_lessons`) but that phase never appears in logs | measured absence; likely lessons extraction not enabled in logged runs |

Logged and confirmed in the logs: plan_audit, run `claude_call`, `detail-step-NN`, `propose_steps`, `propose_references`, `propose_distilled_seed`, `propose_body_sections`, `propose_intents`. `suggest_gates` (plan_tool/gates.py:377) and `foundational_logic` are bound in code but do not appear in the logs. Roadmap verbs bind sinks (plan_tool/roadmap.py:1675) but no roadmap run is in the logs. Static classification is by reading binding calls in each function, not by running the code.

**What this cannot tell us.** (a) Whether the apply_finding gap is real loss or a sink-routing quirk; its tokens are invisible, only 0.43 h wall-clock is known. (b) 326 events have unknown cached/non-cached accounting. (c) No per-call identity inside `plan_audit` or `detail-step-NN` (re-audit vs first author vs retry share one phase name). (d) Runs from 2026-08 to 10 only; Codex and Claude mixed with different models, so per-call means are not comparable across rows. (e) Claude `cost_usd` exists only for Claude events (USD 1,150 total); Codex cost is null.

## Exp 2. Identical-input detector

**Method.** Searched all event types for prompt text or hashes.

**Finding: the logs carry no prompt text and no prompt hash.** `claude_call_start` and `backend_spawn` carry only `prompt_bytes`. The only `input_hash` fields are on `checkpoint_save`/`checkpoint_hit` (hash of a checkpoint's identity inputs, `plan_tool/checkpoint.py:102 compute_input_hash`), which covers checkpointed stages only (534 saves: detail-step 217, in-progress sampler 182, create-* 135). Stream transcripts (`*.streams/*.ndjson`) do not exist on disk (0 files).

What the available proxies show (measured):

| proxy | result |
|---|---|
| Same-run, same-phase calls with identical `prompt_bytes` | 0 repeat groups (so no exact-size repeats among 803 `claude_call_start` events) |
| Checkpoint saves with the same `input_hash` twice inside one run | 108 extra saves, all `in-progress-sampler-checkpoint` |
| Cross-run same (plan, checkpoint name, input_hash) | 12 of 409 keys appear in more than one run |
| `checkpoint_hit` (a stage skipped because inputs matched) | 23 events |
| `checkpoint_discard` | 423 (durable_write 217, success 133, terminal 73) |

The 108 sampler repeats are not waste: they are the intended multi-sample audit (same plan snapshot re-sampled; e.g. run `roadmap-terminal-error-contract/2026-09-21T15-47-08...` shows 3 `plan_audit` calls, each followed by a save with the same hash and payload growing 7,022 to 9,226 to 9,333 bytes). The June "same input re-rolled" pattern (create re-proposal) is already removed by default.

**Instrumentation needed (not guessed beyond the code):** add a `prompt_sha256` field to `ClaudeCallStart` (plan_tool/run_log.py:213) and to `RunLogWriter.claude_call_start` (plan_tool/run_log.py:2053), populated by the callers that already compute `prompt_bytes` (e.g. launcher.py:1781 area, detail.py:3043, create.py:3767, review.py:9136 path). Plan_audit has no `claude_call_start` at all today (0 starts vs 712 ends), so it needs the start event or a hash on `ClaudeCallEnd`. Add the same hash to the apply_finding path.

**What this cannot tell us.** Whether any call repeated an identical prompt. Exp 2 is not answerable from existing data; the proxies above only rule out exact-size repeats and show checkpoint reuse is rare (23 hits).

## Exp 3. Audit sample yield

**Method.** Parsed 879 final (non-pre-apply) completeness reports that carry `audit_coverage`, plus per-sample records from run logs.

**Finding: saved reports do not store per-sample findings.** Report keys are `recommendations` (flat list; fields id, source, severity, step_id, title, body, suggested_action, impact, complexity, redirect, anchor, target_signature, confidence, restated_property), `audit_coverage` (`passes_used`, `cap`, `conforming_pass_count`, `confirmation_kind`, `budget_limited`, ...). No field records which pass first found a finding. The in-flight sampler state does track per-finding observations (`plan_tool/review.py:8398 observations_by_id`) but the checkpoint is discarded at terminal (`checkpoint_discard reason=terminal`), so it is not on disk. The marginal findings of samples 2 and 3 over sample 1 therefore cannot be measured directly.

What can be measured:

| passes_used | confirmation | budget_limited | final reports |
|---|---|---|---|
| 1 | confirmed-dry | no | 144 |
| 1 | none | no | 132 |
| 2 | confirmed-dry | no | 251 |
| 2 | confirmed-low-yield | no | 14 |
| 3 | confirmed-dry | no | 115 |
| 3 | confirmed-low-yield | no | 1 |
| 3 | none (cap reached, still discovering) | yes | 218 |
| 5 | confirmed-dry / none | no / yes | 2 / 2 |

- 218 of 879 reports (24.8%) hit the 3-pass cap still discovering, i.e. a third pass was still productive there; 115 confirmed dry at pass 3; 541 ended after 1 or 2 passes (265 of them at pass 2 with the second pass dry or low-yield). Source: `docs/**/*-completeness.json`, `audit_coverage`.
- Run logs, 72 runs with at least 2 checkpointed plan_audit samples: sample 1 output 1.94M tokens, sample 2 1.53M, sample 3 (36 runs) 0.83M; samples 2+ are 55% of those runs' audit output tokens. The sampler checkpoint payload grows from sample 1 to 2 in 69 of 72 runs (median +254 bytes) and sample 2 to 3 in 36 of 36 (median +343 bytes). Payload bytes are a proxy for accumulated state, not a finding count.

**What this cannot tell us.** Per-plan material findings added by samples 2 and 3 (not stored). The 72-run subset is only runs whose logs retain checkpoint saves. "Pass N dry" shows the last pass added nothing new, not how many findings earlier passes added. Answering this needs per-pass finding ids persisted (or a replay of `observations_by_id` at checkpoint save).

## Exp 4. Prompt composition

**Method.** Static size = `len(file)` for each `plan_tool/prompts/*.md` (43 templates, 265,254 chars total, ~66,300 tokens at chars/4, an estimate). Injected sizes are MEASURED from `prompt-budget` telemetry records (`.plan-tool/telemetry/decisions.jsonl`, 1,214 records, bytes per named block; script `.tmp/token-ledger.blocks.py`) and from logged `prompt_bytes`. Tokens below use bytes/4 (estimate).

Median full-prompt size per call site (measured `prompt_bytes`, then ~tokens):

| call site | calls | median bytes | ~tokens | static template | injected remainder (bytes, derived) |
|---|---|---|---|---|---|
| detail-step-NN | 228 | 152,498 | 38,100 | detail.md 20,538 | ~132,000 |
| create propose_steps | 42 | 115,238 | 28,800 | (template not in prompts/ dir; inline in create.py, not verified) | n/a |
| create propose_body_sections | 11 | 80,157 | 20,000 | synthesize-body.md 17,233 | ~63,000 |
| plan_audit (completeness) | 445 | 57,461 | 14,400 | plan-audit.md 30,022 | ~27,000 |
| run-reconcile | 279 | 29,029 | 7,300 | run-reconcile.md 11,717 | ~17,000 |
| run step | 157 | 21,336 | 5,300 | run.md 3,232 | ~18,000 |
| propose_distilled_seed | 23 | 17,992 | 4,500 | distill-seed.md 9,285 | ~8,700 |

Injected blocks by prompt (measured medians from `prompt-budget`, per call):

| prompt (telemetry phase) | block | median bytes | max bytes | share of mean prompt | code-stated cap |
|---|---|---|---|---|---|
| detail (n=225) | **lessons** | 96,770 | 96,796 | 62% | `_MAX_INJECT_BYTES = 49152` (plan_tool/lessons.py:252, per lessons file; general + project at cap = ~96.8 KB, so truncation is biting; inference) |
| detail | file-contents | 12,674 | 117,544 | 11% | 4,096 B per file (`_MAX_PROMPT_FILE_BYTES`, plan_tool/detail.py:229); no cap on file count found |
| detail | sibling-details | 12,599 | 50,348 | 9% | none found |
| detail | scope-fence / concept-scope / plan-references / project-context / risk-context | 1,542 / 1,439 / 1,280 / 1,195 / 469 | 8,928 / 1,508 / 2,234 / 1,195 / 472 | ~3% total | none found |
| create-steps (n=46) | **lessons** | 97,676 | 97,702 | 74% | same 49,152 B cap per file |
| create-steps | description | 8,197 | 26,609 | 6% | none |
| create-steps | rejected-response (4 of 46) | 60,089 | 111,973 | 4% | none |
| create-synthesis (n=11) | **reference-docs** | 60,779 | 61,000 | 55% (6 of 11 records) | fetch caps 20,000 chars per URL, 60,000 total (plan_tool/fetch.py:54-55) |
| create-synthesis | seed / repository-code | 4,630 / 524 | 9,007 / 16,080 | 8% / 4% | code excerpt 3,000 B (`_LOCAL_CODE_EXCERPT_BYTES`, plan_tool/create.py:3028) |
| plan-audit (n=408) | plan body | 16,293 | 76,287 | 31% | none |
| plan-audit | detail bundle | 1,825 | 50,712 | 20% (large when detail is complete) | none |
| plan-audit | scope contract / project-context / bundle status | 1,296 / 1,195 / 802 | 3,947 / 1,195 / 1,746 | ~3% | none; carried findings: 30 max, 280-char excerpts (plan_tool/review.py:638-639) |
| run-step (n=436) | step detail | 15,215 | 60,444 | 61% | none |
| run-step | scope fence / completed-sibling context | 2,040 / 2,118 | 9,435 / 4,633 | 9% / 5% | none |
| run-step | lessons | 0 | 0 | 0% | n/a (run injects no lessons) |

Notes. (1) `plan-audit` percentages sum to ~53% of mean prompt; the rest is the static template (30 KB) and unblocked text. (2) The project context block is the small confirmed profile from `.plan-tool/project.json` (`plan_tool/project_profile.py:100`), 1,195 B, not CLAUDE.md. Whether the Claude/Codex subprocess also auto-loads the 106,151-byte CLAUDE.md from its cwd is not visible in these logs and is unverified. (3) `plan_tool/detail.py:225` shows detail injects lessons from surfaces `detail-authoring`, `cross-step`, `domain-shape`, which conflicts with the retro's statement (section 3) that `domain-shape` is injected by no prompt; this should be checked before experiment 5(a). (4) Apply-finding prompts (apply-finding.md) are 2,372 tokens static; logged apply prompts median 20,236-29,695 B.

Static template sizes (chars, ~tokens = chars/4, estimate):

| template | chars | ~tokens (chars/4) |
|---|---|---|
| plan-audit.md | 30,022 | 7,505 |
| detail.md | 20,538 | 5,134 |
| synthesize-body.md | 17,233 | 4,308 |
| jira.md | 15,770 | 3,942 |
| roadmap-constraints.md | 15,002 | 3,750 |
| roadmap-components.md | 13,816 | 3,454 |
| detail-quality.md | 12,601 | 3,150 |
| run-reconcile.md | 11,717 | 2,929 |
| roadmap-domain.md | 10,337 | 2,584 |
| detail-reconcile.md | 9,847 | 2,461 |
| apply-finding.md | 9,490 | 2,372 |
| distill-seed.md | 9,285 | 2,321 |
| roadmap-plans.md | 9,177 | 2,294 |
| review.md | 7,359 | 1,839 |
| extract-lessons-detail.md | 7,257 | 1,814 |
| extract-lessons-review.md | 6,901 | 1,725 |
| roadmap-candidate-delta.md | 4,898 | 1,224 |
| criteria-fulfillment.md | 4,188 | 1,047 |
| foundational-logic-sweep.md | 4,085 | 1,021 |
| detail-jira.md | 3,549 | 887 |
| annotate.md | 3,417 | 854 |
| run.md | 3,232 | 808 |
| roadmap-candidate-delta-selector.md | 3,074 | 768 |
| run-jira.md | 3,012 | 753 |
| roadmap-seed.md | 3,011 | 752 |
| roadmap-candidate-questions.md | 2,662 | 665 |
| optimize.md | 2,460 | 615 |
| security.md | 2,190 | 547 |
| check.md | 2,190 | 547 |
| document.md | 2,129 | 532 |
| test.md | 2,096 | 524 |
| reconcile-deep.md | 2,001 | 500 |
| lint.md | 1,897 | 474 |
| lessons-equivalence.md | 1,847 | 461 |
| roadmap-structural-feedback-revision.md | 1,229 | 307 |
| classify-risk-profile.md | 1,147 | 286 |
| roadmap-feedback-revision.md | 1,071 | 267 |
| roadmap-revision.md | 968 | 242 |
| roadmap-stage-feedback-revision.md | 857 | 214 |
| concept-emit.md | 781 | 195 |
| roadmap-revision-update-judgment.md | 515 | 128 |
| roadmap-smallest-proof-boundary-footer.md | 245 | 61 |
| roadmap-smallest-proof-boundary-header.md | 151 | 37 |

**What this cannot tell us.** Block sizes come only from sites that pass `collect_blocks` (detail, plan-audit, run-step, create); reconcile (`run-reconcile`), review, apply-finding, jira, annotate and roadmap prompts have no per-block telemetry. Bytes are not tokens (chars/4 is a rough estimate; `plan_tool/prompt_budget.py:31` uses 3.5 bytes/token). A large block is not necessarily a costly one: the lessons block is nearly constant across calls (median 96,770, max 96,796), so most of it likely lands in the cache-read column; this analysis does not measure that directly.

## Top 5

By call site (non-cached input + output tokens, Exp 1):
1. completeness / plan_audit: 193.1M (47.5% of 406.8M), 712 calls, 67.5 h.
2. run / claude_call: 76.8M, 155 calls, mean ~496K per call.
3. detail / detail-step-NN: 65.1M, 220 calls (authoring and re-audits share the phase).
4. run-reconcile / claude_call: 44.3M, 278 calls.
5. create / propose_steps: 22.0M, 43 calls, highest mean per call among create phases (563K).

By prompt block (Exp 4, bytes per call):
1. Lessons in detail: ~96.8 KB/call (~24K tokens est), 62% of the detail prompt.
2. Lessons in create-steps: ~97.7 KB/call, 74% of that prompt.
3. Reference docs in create-synthesis: ~60.8 KB/call, 55%.
4. Plan body in plan-audit: 16.3 KB median, up to 76 KB; with the detail bundle (up to 50 KB) about half of the audit prompt.
5. Step detail in run-step: 15.2 KB median, 61% of that prompt (file-contents in detail is 12.7 KB median but up to 117 KB).

## Recommendation (which of retro experiments 5-9 the data supports)

Pursue 5(a) (surface filtering of lessons) first: the largest injected block anywhere is the lessons block, a near-constant ~97 KB in both detail and create-steps (62-74% of those prompts), already pinned at its 49,152-byte per-file cap, and it is absent from run-step prompts, so filtering is a cheap, measurable ablation (and check the `domain-shape` surface discrepancy in `plan_tool/detail.py:225` before building it). Pursue 7 (per-block ablation) narrowly on plan-audit, since plan_audit is 47.5% of all non-cached+output tokens and its blocks are plan body and detail bundle, not lessons; the sample count (`--audit-samples`) is the real lever there but Exp 3 is not measurable from saved reports, so first persist per-pass finding ids (or accept the budget-limited rate: 24.8% of reports end still discovering at the 3-pass cap, which argues against dropping the default). Experiment 6 (prefix stability) has support only partially: cached input is 89% of input, but Codex and unattributed events show far more non-cached input than Claude events (89.7M and 226.9M vs 63.0M tokens; family table in token-ledger.ledger2.out.md), so verify the Codex cached-token accounting first and compare on replayed inputs, not across mixed-backend history. Experiment 2 and the identical-input idea need new instrumentation (prompt hash) before they can be judged; experiment 8 (tier downshift) has no data here beyond the fact that apply_finding is unlogged, so fix that logging gap before testing it; experiment 9 is not supported by anything in this data. Fix the apply_finding sink gap and the unsinked sites above first, since they bound how much of the ledger is invisible.
