> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Intent Required
intent: Make the intent field reachable end to end -- authored by create, proposed
  when absent, blocking once both hold -- so a stated why travels with the work instead
  of being re-inferred at every hop.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Make the usable-intent check in review.py public so create and the proposer
    share one predicate
  intent: One predicate defines the whole observable, so authoring, the proposer,
    and the finding can never disagree about what counts as an intent.
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: low
  change_type: refactor
  detail: docs/implementation-plans/plan-details/intent-required/01-make-usable-intent-check-review-py.md
  status: done
- id: 2
  title: Map the seed's `## Outcome` section to the plan's `intent` in create.py
  intent: The seed already states the why once; carry that value forward rather than
    asking a model to invent a second one that can drift from it.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/intent-required/02-map-seed-outcome-section-plan-intent.md
  status: done
- id: 3
  title: Ask for `intent` in the step-proposal JSON and retry once when a proposal
    leaves it out
  intent: Get a per-step why out of the call create already makes, so authoring an
    intent costs no extra Claude round-trip.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/intent-required/03-ask-intent-step-proposal-json-retry.md
  status: done
- id: 4
  title: Add an intent-proposal helper module that drafts a one-liner and takes accept,
    edit, or decline
  intent: Give an absent intent a fix the operator can accept, so the finding arrives
    with a remedy instead of a reprimand.
  creates:
  - plan_tool/intent_proposal.py
  - tests/test_intent_proposal.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/intent-required/04-intent-proposal-helper-module-that.md
  status: done
- id: 5
  title: Offer the proposed intent in the create wizard when the seed, `--from` text,
    or interactive path supplies none
  intent: Close the last authoring path that can still produce a plan carrying no
    intent at all.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 4
  detail: docs/implementation-plans/plan-details/intent-required/05-offer-proposed-intent-create-wizard.md
  status: done
- id: 6
  title: Raise the intent-presence finding to `medium` and move it onto the blocking
    self-consistency bucket
  intent: Make a missing intent actually stop the loop -- safe only now that every
    authoring path supplies one and the fix for an older plan is a single line.
  files:
  - plan_tool/review.py
  - plan_tool/cli/completeness_phases.py
  - tests/test_review.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 5
  detail: docs/implementation-plans/plan-details/intent-required/06-raise-intent-presence-finding-medium.md
  status: done
- id: 7
  title: Document both intent fields and the `## Outcome` mapping in the format and
    flow docs
  intent: A field that no format doc describes cannot be complied with, and neither
    field is documented today.
  files:
  - PLAN_FORMAT.md
  - SEED_FORMAT.md
  - docs/CREATE_FROM_EXISTING_FLOW.md
  - docs/AUDIT_FLOW.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/intent-required/07-document-both-intent-fields-outcome.md
  status: done
- id: 8
  title: 'Close out BACKLOG #206 and update CLAUDE.md, keeping both reversal records'
  intent: Preserve the two recorded reversals so a later audit reads settled history
    instead of re-litigating a refusal, and file every entry this plan routed out
    of scope.
  files:
  - BACKLOG.md
  - BUG_BACKLOG.md
  - CLAUDE.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 7
  detail: docs/implementation-plans/plan-details/intent-required/08-close-out-backlog-206-update-claude-md.md
  status: done
---
# Intent Required

## Overview

This plan makes `Plan.intent` / `Step.intent` reachable end-to-end. `create` authors both fields — the seed's `## Outcome` maps deterministically to `Plan.intent`, and `intent` joins the existing step-proposal JSON contract beside `title` / `files` / `change_type` / `rationale`, and an omitted intent rides `propose_steps_from_claude`'s existing single repair attempt — the proposal call's retry budget is unchanged at a ceiling of two calls, exactly as today. When a `create` run has no `## Outcome` and no proposed step intent to carry, the wizard offers a drafted one-liner the operator accepts, edits, or declines. Once authoring and that offer are both in place, `review.py:check_intent_presence` rises from `info` to `medium` and moves onto the blocking-capable `self_consistency_recs` bucket in `cli/completeness_phases.py`, so a missing intent blocks completeness convergence. Blocking means blocking convergence only: the exit-code convention is unchanged — a completed audit exits 0 however many intent findings it prints, and only `--fail-on-findings` flips the rc.

## Problem statement

The completed `2-intent-scope-fence.md` landed `Plan.intent` / `Step.intent`, the shared fence renderer (`plan_tool/scope_fence.py`), and an advisory presence check (`review.py:check_intent_presence`, `info`) — but **the field shipped structurally unreachable**. `create`'s step-proposal prompt never asks for `intent` and `_parse_steps_json` never reads the key, so no authoring path can produce one. Measured at HEAD 2026-08-03 (`parse_plan` plus the usable-intent predicate over `docs/implementation-plans/*.md`, not a grep — an earlier grep of this corpus keyed on the wrong indent and undercounted): of **18 plan files, 2 carry a plan-level `intent:` and 20 of 127 steps carry one**. Every one of those was **written by hand** — `2-roadmap-02-feedback-channel.md` and this plan. No `create` run has ever produced an intent, and none can. The fence renders a value the pipeline cannot create, and the advisory fires on every plan the pipeline authored, with no remedy attached — the shape that trains operators to ignore a finding channel. Both fields are also currently undocumented in `PLAN_FORMAT.md` despite shipping.

## Architecture

**Presence remains the entire contract.** The binary observable is: the field is present and is not a placeholder. `review.py`'s usable-intent predicate already implements the whole observable (absent, empty after whitespace, bare placeholder) and needs no new one — step 1 only publishes it (private `_is_usable_intent` today, `is_usable_intent` from step 1 on) so every consumer shares one definition instead of copying it. No quality judgment, no comparison against `## Why` / plan body / detail / acceptance criteria / the diff, no length cap, no required shape or phrasing rule.

**Exactly one refusal is lifted, and it is recorded, not silent.** The shipped plan's *"any gate, exit-code flip, or refusal-to-advance keyed on an intent"* is reversed on an explicit user decision (2026-08-02), and **only for presence**. Its stated reason for refusing — a check that fires on the whole corpus with no remedy trains operators to ignore the channel — is discharged by the authoring and proposer work below, not overruled. This plan records the reversal the way `2-intent-scope-fence.md` recorded its own widening of #206 (`## Out of scope`, "Widened from BACKLOG #206 — recorded, not silent"), including the discharge argument, so a later audit reading the shipped plan's "permanently refused" does not correctly flag this plan as violating it.

**Produce before require — this is the step order, not a preference.** Authoring lands first, the proposer second, the severity flip **last**. Flipping severity while nothing authors an intent turns every intent-less plan blocking-red simultaneously with no fix available (16 of 18 at HEAD, 2026-08-03), which is precisely the failure the shipped plan's Risks section predicted. This dependency is stated in `depends_on`, not only in prose.

**Step intent rides the existing proposal call.** `create` already makes one step-proposal call; `intent` joins that JSON contract. A proposal that omits it retries with the omission quoted back — the retry-the-same-stage shape `roadmap.py` uses for gate violations — rather than failing the run or silently accepting `None`. The retry spends `propose_steps_from_claude`'s **existing** single repair attempt rather than adding a round-trip, so the ceiling stays at two calls; a proposal that already carries `intent` still costs one, as today.

**The proposer is a remedy on the existing finding, not a new verb.** Detection stays unconditional; mutation stays gated — the standing shape shared with `escalate_to_split` and `scope_out_step`. The operator sees a proposed one-liner and accepts, edits, or declines it. No bulk migration sweep, and no plan file is rewritten without that confirmation. `intent-presence` stays out of `APPLY_ELIGIBLE_SOURCES`; this remedy is its only mutator.

**The remedy for an existing plan is a one-line frontmatter edit, and that is deliberately all it is.** `intent-presence` joins `SELF_CONSISTENCY_SOURCES`, whose standing rule is exactly right here: blocking, and not `apply_finding`-appliable, because the fix is a manual plan edit. For a single optional one-line field that rule needs no exception — an operator adds `intent:` and the finding clears. Wiring a gated apply path through the review/reconcile walk to write one line was tried in this plan's first decomposition and **carved back out 2026-08-03** (`plan-seeds/intent-required-carved-*`): it needed sidecar plumbing, a staleness guard, an explicit plan-vs-steps target, and a jira-grade carve-out, and produced most of that round's audit findings. The suggestion half of this plan lives at `create` time, where the plan is being authored anyway.

**The seed's `## Outcome` is the seed's intent — but the proposer, not the map, is the ordinary plan-level producer.** `SEED_FORMAT.md` already requires `Outcome` — one measurable result. It is declared the seed's intent and mapped to `Plan.intent` **deterministically, with no Claude call**. Measured 2026-08-03 over `plan-seeds/` (12 hand-authored seeds, excluding distilled copies): **6 carry a `## Outcome` H2**. Both *live* seeds do; the six that do not are archived, five of them one family. The requirement is real and compliance is improving, but the deterministic map covers roughly half of the historical corpus, so **step 5's proposer is a co-equal producer rather than a fall-through** — and step 5's silent non-TTY skip is a tradeoff chosen against that frequency, not an edge case. Step 7 documents the `## Outcome` requirement in `SEED_FORMAT.md` so the map's coverage rises going forward. No second why-section is added to the seed format: two prose fields at one altitude that can disagree is the duplication-vs-drift trap #206 named, and #206's own duplication call (intent is a one-line seed the prompts consume, never re-checked) is kept. A seed reaching `create` with no usable `## Outcome`, and the `--from` one-liner and interactive paths, fall to the proposer.

**`--yes` accepts a drafted intent at `create` time.** Every other field on a new plan is model-drafted — title, files, `change_type` — and the operator reviews the whole plan before anything consumes it, so a drafted intent is no less reviewed than a drafted title. This is the only fast-forward question the plan has, now that nothing writes an intent into an already-reviewed plan.

**Two consequences, named rather than discovered.** A non-TTY `create` without `--yes`, from a source carrying no usable `## Outcome`, still writes a plan with no intent — step 5's ladder skips silently rather than blocking a headless author. And a plan **already on disk** with no intent stays blocked in a headless audit until someone adds the line, since `intent-presence` is not `apply_finding`-appliable. That is the accepted cost of shipping no bulk migration, and the fix is one line rather than a new unattended write path.

**The schema field stays `Optional`; no plan is migrated.** Every plan on disk keeps parsing byte-for-byte. "Required" is enforced at authoring and at audit, never at parse time — preserving #206's *"making `intent` required on existing plans"* non-goal and the shipped plan's no-migration fence.

**This plan is the feature's live fixture, not merely its subject.** Its own plan intent and its eight step intents were authored **by hand at creation** (2026-08-02, ten before the 2026-08-03 carve), because the tool cannot yet author them — that absence is what step 3 and step 5 exist to close. Two reasons this is a decision rather than housekeeping. A plan that makes intent required while carrying none argues against its own thesis. And because `detail.py` passes `plan.intent` / `step.intent` into the shared fence, these values are the only end-to-end proof that a *real* intent reaches a detail prompt — every other plan in the repo renders the empty half. Any step added, split, or renumbered here gets its intent written by hand for the plan's **whole execution** — not only until step 3 lands. Step 3 fixes the *initial* proposal, but three producers still hand back a step with no intent: `split` / `merge` / `scope-out` / `reground` are permanently carved out of this plan's scope, the re-split proposal prompt asks for `title` / `change_type` / `files` / `creates` / `concept_ids` / `rationale` and never `intent`, and `create --iterate`'s post-write re-proposal carries an intent forward only when the step's title is unchanged. The plan is expected to emit zero `intent-presence` findings against itself at every point in its own execution, and after step 6 that expectation is enforced rather than hoped for.

**The roll-up shape survives the promotion.** `check_intent_presence` emits at most two findings per plan (one plan-level, one step roll-up naming the missing ids) and never echoes the value it read. Promotion to `medium` must not fan it out per-step: on a corpus where every plan predates the field, per-step volume is the documented way to kill a finding channel.

**In scope:** `plan_tool/create.py` (the step-proposal prompt and its JSON parse gain `intent`, with the omission retry; the seed `## Outcome` → `Plan.intent` map; the proposal path for a seed/`--from`/interactive source that supplies no usable Outcome); `plan_tool/review.py` (`check_intent_presence` severity, and whatever the finding must carry for the remedy to act on it); the completeness partition that makes the finding blocking-capable (`cli/completeness_phases.py`), following the `suppression-shape` precedent; the apply/confirm seam the proposer is dispatched from; `SEED_FORMAT.md`; `PLAN_FORMAT.md`; `CLAUDE.md` and `BACKLOG.md` closeout; and tests for each.

**Allowed behavior changes — only these:** `create` emits two frontmatter fields it does not emit today and retries a proposal that omits the step field; one existing advisory finding class rises to `medium` and becomes blocking-capable in the completeness battery; one gated remedy can write an intent after operator confirmation. Every plan already on disk parses unchanged, and a plan carrying intents renders the same prompt bytes it does today.

**Allowed reorganization: none.** No module moves and no renderer changes — `scope_fence.py` is consumed exactly as shipped.

**Backlog reconciliation.** **#206** is the source entry; its status (`not started`) is stale — the field, fence, and advisory shipped in `2-intent-scope-fence.md`, and this plan closes the remainder. The final documentation step removes #206 only after this work ships, and in doing so must **preserve the shipped plan's "Widened from BACKLOG #206 — recorded, not silent" record** plus this plan's own reversal record, relocating both to `CLAUDE.md` if #206 is deleted — the two reversals are the don't-reopen history, and deleting the entry must not delete them. **#212** stays open and is explicitly *not* discharged here; the plan notes that its blocker (the shipped field) is now clear.

## Input

This plan reads three existing contracts before it writes.

**The `create` step-proposal JSON contract** (`plan_tool/create.py`, parsed by `_parse_steps_json`): today each proposed step carries `title` / `files` / `change_type` / `rationale`. `intent` joins that object as a sibling key on the same single call, so the depended-on shape is the existing per-step object and its parse path — not a new response format.

**The `Plan.intent` / `Step.intent` schema fields and `review.py`'s usable-intent predicate**, both shipped by `2-intent-scope-fence.md`. The fields are `Optional` and stay `Optional`; the predicate (private `_is_usable_intent` today, published as `is_usable_intent` by step 1) already defines the entire observable (absent, empty after whitespace, bare placeholder) and its behavior is consumed as-is rather than re-implemented. `plan_tool/scope_fence.py` is likewise consumed exactly as shipped.

**The seed's `## Outcome` heading**, required by `SEED_FORMAT.md` — one measurable result. It is read deterministically (no Claude call) and mapped to `Plan.intent`.

**Limits on verifying these contracts.** The mapped value is checked only for presence and non-placeholder-ness; nothing verifies that an `## Outcome` is a *good* intent, and nothing compares it against the plan body, `## Why`, detail files, or acceptance criteria. A seed with no usable `## Outcome`, plus the `--from` one-liner and interactive sources, supply no contract to read and fall through to the proposer instead.

## References

- [Structured outputs — Claude API Docs](https://docs.claude.com/en/docs/build-with-claude/structured-outputs) — Covers strict JSON-schema-validated model output, the mechanism for making `intent` a required key in the step-proposal contract rather than a hoped-for one.
- [Increase output consistency (JSON mode) — Claude Platform Docs](https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency) — Official guidance on pinning response shape, prefilling, and re-prompting on malformed output — the reference for the retry-with-the-omission-quoted-back loop when a proposal drops `intent`.
- [Tool use with Claude — Claude Platform Docs](https://docs.anthropic.com/en/docs/build-with-claude/tool-use) — Defines `input_schema` and required-field semantics for tool definitions, the fallback path if the proposal call needs a schema-enforced contract instead of free-form JSON.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — Authoritative flag list for the `claude` binary that plan-tool's invoker seam shells out to, including `--output-format` and schema options that shape the proposal response.
- [Run Claude Code programmatically (headless mode)](https://docs.claude.com/en/docs/claude-code/headless) — Documents `-p`/`--print` non-interactive invocation and the JSON/stream-JSON result envelope, needed to parse and re-issue the step-proposal call from a subprocess.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Loader/dumper reference for the frontmatter round-trip, relevant because every existing plan must keep parsing byte-for-byte once `intent` is emitted.
- [dataclasses — Data Classes — Python 3 documentation](https://docs.python.org/3/library/dataclasses.html) — Field defaults and ordering rules for adding an `Optional[str] = None` `intent` field to `Plan`/`Step` without breaking existing construction sites.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Any validation past presence** — no quality judgment, no comparison against `## Why` / plan body / detail / acceptance criteria / the diff, no length cap, **no truncation**, no required shape or phrasing rule. Carried verbatim from `2-intent-scope-fence.md`. **Permanently refused — not deferred to a follow-up entry.** A finding proposing one is invalid, not deferrable.
- Making `intent` required at parse time; migrating, backfilling, or sweeping the plans already on disk.
- **A gated apply path that writes an intent into an existing plan** — carved out to `plan-seeds/intent-required-carved-*` on 2026-08-03. For a one-line optional field the remedy is a hand edit; the machinery it needed (sidecar plumbing, a staleness guard, a plan-vs-steps target, a jira-grade carve-out) cost more than the field it wrote.
- **Clearing a stale intent when `apply_finding` rewrites a step** — BACKLOG **#212**, now unblocked by the shipped field. Adjacent and easily conflated: this plan fills an **absent** intent, #212 clears a **stale** one on an unrelated rewrite path. Do not absorb it.
- Propagation through `split` / `merge` / `scope-out` / `reground` — carved out by the shipped plan and still carved.
- Delivery to any consumer past the four templates already rendering the fence (`detail.md`, `detail-jira.md`, `run.md`, `run-jira.md`); threading intent into the jira export (`plain_summary` covers it).
- Changing the required detail sections at either grade.
- An intent field at roadmap altitude, or on any `roadmap` artifact.
- New `--jobs` / parallel surfaces.

## Risks

- **Flipping severity before authoring exists** turns every intent-less plan blocking-red simultaneously with no fix available (16 of 18 at HEAD, 2026-08-03) — precisely the failure `2-intent-scope-fence.md`'s Risks section predicted. Mitigated by the produce-before-require step order, expressed in `depends_on` rather than prose alone.
- **Per-step fan-out on promotion.** If the promoted `check_intent_presence` emits one finding per missing step instead of the roll-up, the volume on a corpus where every plan predates the field is the documented way to kill a finding channel. Mitigated by holding the at-most-two-findings-per-plan shape through the severity change.
- **A later audit reading `2-intent-scope-fence.md`'s "permanently refused"** will correctly flag this plan as violating it unless the reversal is recorded with its discharge argument. Mitigated by recording it the way the shipped plan recorded its own #206 widening.
- **The authoring retry needing a second round-trip — resolved during detail, recorded here so nobody re-opens it.** The intent shortfall rides `propose_steps_from_claude`'s existing single repair attempt, so the call ceiling is unchanged and no extra round-trip is added. No scope decision is outstanding; an implementer meeting this should not stop.
- **Conflation with BACKLOG #212** (stale intent on a rewrite path) — adjacent enough to be absorbed by accident. Mitigated by naming the absent-vs-stale distinction explicitly in the out-of-scope fence.
- **Deleting #206 at closeout could delete the two reversal records with it.** Mitigated by requiring both be relocated to `CLAUDE.md` if the entry is removed.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.
- step 8 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A `create` run from a seed with an `## Outcome` produces a plan whose frontmatter carries a plan intent and an intent on every step, within the proposal call's existing retry budget — a ceiling of two calls, unchanged from today.
- A step proposal omitting `intent` retries rather than yielding a step with `intent: None` or failing the run.
- On the TTY and `--yes` paths, a seed with no usable `## Outcome` reaches the proposer instead of producing a plan with no intent. A non-TTY run without `--yes` skips silently and writes an intent-less plan, which the finding then flags.
- A plan missing an intent blocks completeness convergence, while the command still exits 0 without `--fail-on-findings`.
- The finding names the plan and the exact step ids that lack an intent, so the one-line fix needs no further diagnosis.
- The proposer writes an intent only after confirmation; declining leaves the plan byte-identical.
- Every plan already on disk still parses, and none is rewritten by this work.
- A plan whose steps all carry intents produces no `intent-presence` finding.
- The finding stays at most two per plan after promotion, and still never echoes the value it read.
- **This plan itself carries a plan intent and an intent on every step**, and so emits no `intent-presence` finding against itself at any point during its own execution — including after any step is split, renumbered, or rewritten. It is the feature's live fixture, not merely its subject.

## Deferred

- **BACKLOG #212** — clearing a stale intent when `apply_finding` rewrites a step. Already filed and now unblocked by the shipped field; stays open and is explicitly not discharged here.
- The backlog entries steps 1, 5 and 6 route out of scope — filed by step 8, which declares both backlog files for the purpose.
