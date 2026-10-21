> **Replaced**: this file has been superseded by `docs/implementation-plans/2-intent-required.md`.
> Preserved here for history; do not edit.

# Intent is authored, required, and proposed when absent (#206 follow-on)

Follow-on to the completed `2-intent-scope-fence.md`, which landed
`Plan.intent` / `Step.intent`, the shared fence renderer
(`plan_tool/scope_fence.py`), and an advisory presence check
(`review.py:check_intent_presence`, `info`).

**The field shipped structurally unreachable.** `create`'s step-proposal prompt
never asks for `intent` and `_parse_steps_json` never reads the key, so no
authoring path can produce one. Measured 2026-08-02 across this repo's 17
plans: **1 plan-level `intent:` (hand-written), 0 step-level**. The fence
renders a value the pipeline cannot create, and the advisory fires on 100% of
the corpus with no remedy attached.

This plan makes intent **authored** (the pipeline produces it), **required**
(its absence blocks), and **proposable** (the finding arrives with a fix).

## Outcome

A plan authored by `create` carries a plan intent and a per-step intent without
an extra Claude round-trip; a plan missing either gets a proposed one-liner the
operator accepts, edits, or declines; and once both hold, a missing intent
blocks convergence instead of nudging.

## Decisions this seed settles (the plan must not re-open them)

1. **Presence remains the entire contract.** The shipped plan's not-allowed
   enumeration is carried forward **verbatim and permanently refused** — no
   quality judgment, no comparison against `## Why` / plan body / detail /
   acceptance criteria / the diff, no length cap, no required shape or
   phrasing rule. `review.py:_is_usable_intent` already implements the whole
   observable (absent, empty after whitespace, bare placeholder) and needs no
   new predicate. **The binary observable:** the field is present and is not a
   placeholder. Nothing else is asserted, now or later.

2. **Exactly one refusal is lifted, and it is recorded, not silent.** The
   shipped plan's *"any gate, exit-code flip, or refusal-to-advance keyed on an
   intent"* is reversed on an explicit user decision (2026-08-02), and **only
   for presence**. Its stated reason for refusing — a check that fires on the
   whole corpus with no remedy trains operators to ignore the channel — is
   discharged by decisions 3 and 5, not overruled. The plan records this
   reversal the way `2-intent-scope-fence.md` recorded its own widening of
   #206 (`## Out of scope`, "Widened from BACKLOG #206 — recorded, not
   silent"), including the discharge argument. A later audit reading the
   shipped plan's "permanently refused" will otherwise correctly flag this
   plan as violating it.

3. **Produce before require — this is the step order, not a preference.**
   Authoring lands first, the proposer second, the severity flip **last**.
   Flipping severity while nothing authors an intent turns all 17 plans
   blocking-red simultaneously with no fix available, which is precisely the
   failure the shipped plan's Risks section predicted. The plan states this
   dependency in `depends_on`, not only in prose.

4. **Step intent rides the existing proposal call.** `create` already makes one
   step-proposal call; `intent` joins that JSON contract beside `title` /
   `files` / `change_type` / `rationale`. **No new Claude round-trip.** A
   proposal that omits it retries with the omission quoted back — the
   retry-the-same-stage shape `roadmap.py` uses for gate violations — rather
   than failing the run or silently accepting `None`.

5. **The proposer is a remedy on the existing finding, not a new verb.**
   Detection stays unconditional; mutation stays gated — the standing shape
   shared with `escalate_to_split` and `scope_out_step`. The operator sees a
   proposed one-liner and accepts, edits, or declines it. No bulk migration
   sweep, and no plan file is rewritten without that confirmation.

6. **The seed's `## Outcome` is the seed's intent.** `SEED_FORMAT.md` already
   requires `Outcome` — one measurable result. It is declared the seed's intent
   and mapped to `Plan.intent` **deterministically, with no Claude call**. No
   second why-section is added to the seed format: two prose fields at one
   altitude that can disagree is the duplication-vs-drift trap #206 named and
   #206's own duplication call (intent is a one-line seed the prompts consume,
   never re-checked) is kept. A seed reaching `create` with no usable
   `## Outcome`, and the `--from` one-liner and interactive paths, fall to the
   decision-5 proposer.

   **This seed conforms to that rule rather than describing it:** its
   `## Outcome` above *is* its intent, and it deliberately carries no
   `## Intent` section — adding one here would be the first instance of the
   duplication this decision forbids.

10. **The plan this seed produces carries intent on the plan and every step.**
    The tool cannot yet author it (that is decision 3's whole point), so it is
    written by hand at creation and maintained by hand until authoring lands.
    A plan that makes intent required while carrying none is the strongest
    possible argument against its own thesis, and it is also the only live
    fixture proving the fence renders a real value end to end.

7. **Blocking means blocking *convergence*, never a non-zero exit.** The
   exit-code convention holds unchanged: a completed audit exits 0 however many
   intent findings it prints, and only `--fail-on-findings` flips the rc. The
   named mechanism is the one `suppression-shape` already uses — emit `medium`
   and partition out of the advisory `smell_recs` bucket onto the
   blocking-capable `self_consistency_recs` bucket
   (`cli/completeness_phases.py`). `intent-presence` stays out of
   `APPLY_ELIGIBLE_SOURCES`; the decision-5 remedy is its only mutator.

8. **The schema field stays `Optional`; no plan is migrated.** Every plan on
   disk keeps parsing byte-for-byte. "Required" is enforced at authoring and at
   audit, never at parse time. This preserves #206's *"making `intent` required
   on existing plans"* non-goal and the shipped plan's no-migration fence.

9. **The roll-up shape survives the promotion.** `check_intent_presence` emits
   at most two findings per plan (one plan-level, one step roll-up naming the
   missing ids) and never echoes the value it read. Promotion to `medium` must
   not fan it out per-step: on a corpus where every plan predates the field,
   per-step volume is the documented way to kill a finding channel.

## In scope

- `plan_tool/create.py` — the step-proposal prompt and its JSON parse gain
  `intent`, with the omission retry; the seed `## Outcome` → `Plan.intent`
  map; the proposal path for a seed/`--from`/interactive source that supplies
  no usable Outcome.
- `plan_tool/review.py` — `check_intent_presence` severity, and whatever the
  finding must carry for the decision-5 remedy to act on it.
- The completeness partition that makes the finding blocking-capable
  (`cli/completeness_phases.py`), following the `suppression-shape` precedent.
- The apply/confirm seam the proposer is dispatched from.
- `SEED_FORMAT.md` — Outcome declared the seed's intent and its requirement
  stated as such.
- `PLAN_FORMAT.md` — **both fields are currently undocumented despite
  shipping**; document them and the authoring requirement.
- `CLAUDE.md` and `BACKLOG.md` closeout.
- Tests for each of the above.

## Out of scope / non-goals

- **Any validation past presence.** Decision 1's enumeration, carried verbatim
  from `2-intent-scope-fence.md`. **Permanently refused — not deferred to a
  follow-up entry.** A finding proposing one is invalid, not deferrable.
- Making `intent` required at parse time; migrating, backfilling, or sweeping
  the 17 existing plans.
- **Clearing a stale intent when `apply_finding` rewrites a step** — BACKLOG
  **#212**, now unblocked by the shipped field. Adjacent and easily conflated:
  this plan fills an **absent** intent, #212 clears a **stale** one on an
  unrelated rewrite path. Do not absorb it.
- Propagation through `split` / `merge` / `scope-out` / `reground` — carved out
  by the shipped plan and still carved.
- Delivery to any consumer past the four templates already rendering the fence
  (`detail.md`, `detail-jira.md`, `run.md`, `run-jira.md`); threading intent
  into the jira export (`plain_summary` covers it).
- Changing the required detail sections at either grade.
- An intent field at roadmap altitude, or on any `roadmap` artifact.
- New `--jobs` / parallel surfaces.

## Allowed behavior changes

Only these: `create` emits two frontmatter fields it does not emit today and
retries a proposal that omits the step field; one existing advisory finding
class rises to `medium` and becomes blocking-capable in the completeness
battery; one gated remedy can write an intent after operator confirmation.
Every plan already on disk parses unchanged, and a plan carrying intents
renders the same prompt bytes it does today.

## Allowed reorganization

None. No module moves and no renderer changes — `scope_fence.py` is consumed
exactly as shipped.

## Verification

- A `create` run from a seed with an `## Outcome` produces a plan whose
  frontmatter carries a plan intent and an intent on every step, with no
  additional Claude call versus today's proposal count.
- A step proposal omitting `intent` retries rather than yielding a step with
  `intent: None` or failing the run.
- A seed with no usable `## Outcome` reaches the proposer instead of producing
  a plan with no intent.
- A plan missing an intent blocks completeness convergence, while the command
  still exits 0 without `--fail-on-findings`.
- The proposer writes an intent only after confirmation; declining leaves the
  plan byte-identical.
- All 17 existing plans still parse, and none is rewritten by this work.
- A plan whose steps all carry intents produces no `intent-presence` finding.
- The finding stays at most two per plan after promotion, and still never
  echoes the value it read.
- **This plan itself carries a plan intent and an intent on every step**, and
  so emits no `intent-presence` finding against itself at any point during its
  own execution — including after any step is split, renumbered, or rewritten.
  It is the feature's live fixture, not merely its subject.

## Stop / defer

Out-of-scope discoveries go to `BACKLOG.md` / `BUG_BACKLOG.md`, never plan
expansion. Specifically: a finding arguing for any check past presence is
**refused, not filed** (decision 1); a finding about a *stale* intent on a
rewrite path is already filed as #212 and must not reopen here. If the
authoring retry (decision 4) proves unable to get an intent out of the proposal
call without a second round-trip, stop and surface that as a scope decision
rather than adding the extra call.

## Backlog reconciliation

**#206** is the source entry. Its status (`not started`) is stale — the field,
fence, and advisory shipped in `2-intent-scope-fence.md`, and this plan closes
the remainder. The final documentation step removes #206 only after this work
ships, and in doing so must **preserve the shipped plan's "Widened from BACKLOG
#206 — recorded, not silent" record** plus this plan's own decision-2 reversal,
relocating both to `CLAUDE.md` if #206 is deleted — the two reversals are the
don't-reopen history, and deleting the entry must not delete them.

**#212** stays open and is explicitly *not* discharged here; the plan notes its
blocker (the shipped field) is now clear.
