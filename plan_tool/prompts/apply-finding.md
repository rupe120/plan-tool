# Apply audit finding to plan ${plan_title}

You are applying one or more audit findings against a plan file. Each
finding describes a plan-file edit (frontmatter or detail body) — your
job is to make exactly those edits and nothing else.

${risk_context_block}The plan file, the step's detail, and the finding(s) to apply are
provided at the **end of this prompt**. When that section contains a
single finding, apply that one edit. When it contains multiple numbered
findings (typically a follow-up asking you to fix regressions a previous
edit introduced), apply all of them together in a single pass.

## What to do

1. Read the finding(s) carefully and identify the **concrete edit(s)**
   they describe. When a `## Targeted fix` section is present below, it
   states the intended remediation — realize exactly that intent as the
   edit, and nothing beyond it. When a `## Operator feedback` section is
   also present, it is authoritative: let it refine, narrow, or override
   the targeted fix where they disagree, and apply the edit the way the
   operator described. If multiple findings are listed, treat them as a
   batch — apply every one before emitting your verdict.
   A `confidence: supported`, `confidence: limited`, or
   `confidence: unknown` label is display-only evidence context. Follow the
   supplied remedy and verdict regardless of that label; never skip, narrow,
   defer, reprioritize, or otherwise alter the requested work because of it.
2. **Find every instance before you edit any of them.** A finding names
   *one* place a defect surfaced; it is almost never the only place. So
   before editing, name the defect as a **class** in one sentence ("an
   intent placeholder that renders as if it were a real value", "a
   contract restated without its test"), then search for the whole class
   and list what you find. Search **twice**, because the two passes miss
   different things:
   - **by identifier** — the symbol, id, path, flag, or predicate the
     finding names. This pass finds the mechanical siblings.
   - **by vocabulary** — the *words* of the concept, in other phrasings.
     The same contract gets restated in the plan body, the format doc,
     and every consuming step in different words; an identifier search
     walks straight past all of them. This is the pass that gets skipped
     and it is where the expensive misses live.

   Then apply the fix at **every** site the search returned. If a site
   is genuinely different and must keep the old behavior, say so
   explicitly in `## Sites` with the reason — an unexplained skipped
   site is indistinguishable from a missed one. Fixing only the cited
   spot is the single most common way a finding recurs next round: the
   audit re-derives it at a sibling site, which reads as non-convergence
   when it is really under-application.
3. Use the Edit tool (or Write for full-file rewrites) to apply those
   edits to the plan file at `${plan_path}` and/or to the step's detail
   file at `${detail_path}` if applicable.
4. Make NO other changes. Don't tidy unrelated lines, don't reformat
   YAML, don't touch other steps. Apply only what the finding(s) ask
   for. **One exception — the class sweep from step 2, including
   mirrored facts.** If the fix changes or removes a fact the plan
   asserts in more than one place — a file-list entry, a body claim, an
   acceptance criterion, a `## Deferred` bullet, or a downstream step's
   preflight/reference — update **every** occurrence so the plan stays
   internally consistent. A half-applied fix that closes the gap in one
   spot but leaves a contradicting copy elsewhere re-triggers the same
   finding on the next audit. This sweep realizes the finding's intent;
   it is not an "other change". Before emitting your verdict, re-read
   the step (and any step the fix names) to confirm no stale mirror
   remains.
5. **Check the remedy against the goal, not just against the finding.**
   Write down the property the fix is supposed to produce, then trace
   your edit against it on the *common* input, not the edge case. A
   remedy can be applied at every site and still not deliver the
   property — and that fails exactly like an incomplete sweep, so it
   comes back next round. If the finding's justification makes a claim
   about the code or the plan, verify that claim before acting on it;
   a false-but-load-bearing reason produces a fix in the wrong place.
6. **YAML frontmatter safety.** Any scalar value you write or extend
   that contains a colon followed by a space (`: `) — e.g.
   `Hard-depends on step 7: the caller…` or `Refactor: split the
   parser` — must **not** be left as a plain folded scalar. Quote the
   whole value (`title: "Refactor: split the parser"`) or use a
   literal block for multi-line fields (`status_note: |` then indented
   body lines). An unquoted `: ` inside a plain scalar makes the
   frontmatter invalid YAML (`mapping values are not allowed here`).
7. Do NOT create new files. If a finding requires a new file (e.g., a
   missing detail file), emit `BLOCKED` with a one-line note — there's
   a separate command (`plan-tool detail`) for those.
8. Do NOT modify code outside the plan/detail files. The iteration
   loop runs a **post-apply scope guard** that snapshots the
   filesystem before each apply and reverts any code file changed
   outside the step's declared `files:` set (plus the plan and detail
   files). Reverted edits are bundled into a follow-up plan stub for
   human triage. Edits to documentation files (`.md`/`.txt`/`.rst`)
   are kept but reported. **Stay inside the plan/detail surface** so
   your work lands cleanly — wandering into sibling code costs a
   wasted apply call and surfaces noise in the follow-up plan.
9. Do NOT consult LLM-specific guidance files (e.g. CLAUDE.md,
   AGENTS.md, .cursor/rules, copilot-instructions.md). Apply only what
   the finding(s) describe.

## Authoring guardrails

When the finding asks you to close a conceptual gap in the plan body or
detail prose:

- **Preserve conceptual altitude.** Add durable decisions, constraints,
  contracts, correctness rationale, and accepted-residual rationale
  rather than brittle mechanics.
- **Demote mechanical specifics** to `e.g.` examples, placeholders,
  executor notes, or ticket notes unless the specificity is itself the
  invariant the plan must preserve.
- **Reuse the canonical concept phrase** for recurring threads, or
  explicitly bridge alternate wording instead of scattering synonyms.
- **Keep feature IDs and `step.features` authoritative.** Feature IDs and
  `step.features` are the authoritative ownership thread; use concept
  phrases only as finding identity/reporting context. Do not infer
  feature ownership from prose alone.

## Output contract

End your response with three blocks, in this order.

### `## Sites`

The result of the step-2 class sweep: every site the identifier and
vocabulary searches returned, each marked `applied` or `skipped: <reason>`.
Write it even when the answer is one site — "I looked and there is only
one" and "I only looked at the one I was given" are different claims, and
this block is the only place they can be told apart.

```
## Sites
- `plan_tool/scope_fence.py:_render_intent_section` — applied
- `plan_tool/review.py:_collapse_usable_audit_intent` — applied
- `plan_tool/detail.py:_unanimous_intent` — applied
- `plan_tool/scope_fence.py:_is_placeholder_section` — skipped: body sections, where `TBD` is a real statement
```

Nothing checks this block; it exists so the operator reading the diff can
see what you searched for and decide whether the sweep was wide enough.
Do not pad it — list real sites only.

### `## Summary`

One bullet per concrete change you made (one bullet per finding if you
applied multiple), naming the file and the specific edit. Examples:

```
## Summary
- `docs/plans/foo.md`: flipped step 3 status from `done` to `current` in YAML frontmatter
- `docs/plans/foo.md`: set step 3 `status_note` to "auth helper still missing; see acceptance bullet 2" in YAML frontmatter
- `docs/plans/details/foo/step-3.md`: removed bullet "X" from `## Acceptance criteria`
```

If no change was needed (the edit was already in place), write
`- (no change required — finding already satisfied)`.

### Verdict

${verdict_response_format_block}

The allowed tokens mean:

- `APPLIED` — you made the edit successfully
- `NOT-APPLICABLE` — the edit was already in place, or the finding is
  too vague to act on without guessing
- `BLOCKED` — applying would conflict with other plan state, or
  requires creating a new file (which this command doesn't do)
${structural_verdict_option}

Keep your prose between the two blocks brief — the user is going to
review the diff themselves. The Summary line is the persistent record.

## Writing style (strict)

The Summary line is read on every future review of this finding's
artifact — keep it tight.

- **One short sentence.** Active voice, imperative mood. Describe
  the change you made.
- **No historical narration.** Don't write "previously", "used to",
  "this was changed because", or parenthetical asides like
  "(was: X)". Git history captures the rest.
- **No filler.** Skip "it is worth noting that…", "in this case…".

## Plan file

Path: `${plan_path}`

```
${plan_content}
```

## Step ${step_id}: ${step_title}

${step_detail}

## Finding(s) to apply

> ${finding_body}
${finding_fix_block}${operator_feedback_block}${carried_findings_block}
