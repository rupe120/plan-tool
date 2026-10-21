# Generate JIRA stories for plan "${plan_title}"

You are turning a multi-step implementation plan into a consolidated set of
JIRA-ready stories.

Plan: **${plan_title}** (status ${plan_status} · priority ${plan_priority}).

${epic_block}

${existing_tickets_block}

## All steps in the plan

${steps_block}

## What to produce

Respond with **only** a JSON array of story objects — no prose, no fenced
code block, no preamble, no closing remark. The first non-whitespace
character of your response must be `[`.

Each story is one object of shape:

    {
      "id": "${story_id_example}",
      "title": "<≤80-char imperative phrase suitable for the JIRA title field>",
      "plain_summary": "<1–2 plain-English sentences a PM can grasp at a glance — see Plain-English summary below>",
      "description": "<short context: what + why + where it sits in the plan — see Description style below>",
      "acceptance_criteria": ["<observable behavior or artifact>", ...],
      "files": ["<repo-relative path>", ...],
      "steps": [<plan step id>, ...],
      "depends_on": ["${story_id_example_dep}", ...],
      "estimate_hours": <positive integer; advisory size, target ~${max_hours}>,
      "layer": "<frontend | backend | full_stack | infra>",
      "ui_impact": "<short note on downstream UI impact, or \"none\">",
      "frontend_test_recommendation": ["<how to test the UI-facing behavior>", ...]
    }

Rules:

- **Plain-English summary (the preamble).** `plain_summary` is a
  jargon-free, 1–2 sentence description of the ticket written for a
  **product manager**; it renders as the `## In plain English` preamble
  at the very top of the ticket so a PM grasps it at a glance. State the
  user-visible outcome or the goal in everyday language — what changes
  for a user or the product, and why it matters. Use **no** code
  identifiers, file paths, function/class names, API routes, table
  names, or implementation detail: if you'd write `handleSubmit()` or
  `GET /admin/app-mode`, rephrase it as the behavior ("when a user
  submits the sign-up form", "loading the admin app-mode screen"). This
  is distinct from `description` (which carries the technical detail) —
  never copy one verbatim into the other. Always provide it; one or two
  sentences is enough, and a reader who knows nothing about the codebase
  should still understand what the ticket delivers.
- **Description style.** Keep `description` short and scannable — the
  reviewer should grasp the story in one screen, not read prose. Target
  roughly **40–90 words total** and stop at **120** even for the
  largest stories. Structure as:

    - **One short lead sentence** (≤ 25 words) stating *what* the story
      ships and *why* (the user-visible outcome, the constraint, or the
      step it unblocks). No throat-clearing like "This story will…" or
      "As part of the plan, we…".
    - **A short bullet list** (2–5 bullets, ≤ 15 words each) covering
      the concrete moving parts — files touched, components wired up,
      behavior toggled, env-specific deviations. Use bullets whenever
      you'd otherwise be listing things inside a sentence ("update X,
      then Y, then Z"). One-bullet lists are a smell — collapse into
      the lead sentence instead.
    - **Optional final sentence** only when there's a non-obvious
      caveat the AC can't capture (a sequencing constraint, a known
      footgun, why an obvious alternative was rejected). Skip it
      otherwise.

  Do **not** restate the acceptance criteria as prose, do **not**
  recap the plan or the epic, and do **not** explain the broader
  motivation already in the plan doc — the reader has it. A
  one-sentence description is fine for a small scaffolding story.
- **Atomicity is the primary rule — each story is one shippable PR.**
  Size every story so that, once its `depends_on` stories are merged,
  merging *this* story on its own leaves the repository building and the
  test suite green. A story must never be a fragment that breaks
  compilation, leaves a dangling reference or an unused-but-required
  symbol, half-wires a feature, or otherwise depends on a *later* story to
  become correct. This shippability constraint, **not** an hour count,
  decides where the boundaries fall.
- **Consolidate to reach an atomic unit.** When two or more adjacent or
  tightly-coupled steps only make sense together — scaffolding + its first
  real use, an interface + the implementation that satisfies it, a schema
  migration + the code that reads the new shape, a rename + every call
  site it touches — emit ONE story whose `steps` lists all the plan-step
  ids it covers. Prefer the coarser coherent slice over several fragments
  that each leave the build red in between.
- **Split a step only when every slice stands alone.** Split one plan step
  into multiple stories (sharing `steps: [N]`) *only* if each slice merges
  green by itself — e.g. an additive, valid-but-unused scaffold first, then
  the story that wires it in. If a slice would break the build or tests
  without its siblings, do **not** split: keep them a single story even if
  it runs large. Never cut a story boundary through the middle of a change
  that must land together.
- **`estimate_hours` is an advisory size signal, not a gate.** Aim for
  **≤ ${max_hours} hours** where it's natural, and round up if unsure — but
  never fragment an atomic PR just to fit the target. A coherent story that
  runs longer than ${max_hours}h is better than two stories that each break
  the build. There is no upper limit that rejects a story.
- **Keep a soft decomposition floor of ~4 hours.** Default to stories of
  **roughly 4 hours or more**: prefer consolidating small, adjacent, or
  tightly-coupled work up toward that floor rather than shipping a swarm of
  tiny tickets. Be skeptical of any story you'd estimate **below 4h** — it
  usually means fine-grained plan steps that should have been consolidated.
  Emit a sub-4h story **only when** it is genuinely atomic and cannot be
  coherently merged into an adjacent story without breaking the build or
  crossing a real boundary. This floor is subordinate to atomicity: it never
  justifies cutting a boundary through work that must land together, and a
  legitimately-atomic small story is fine — just don't leave work *fragmented*
  into sub-4h slices that could have been one coherent story. If the
  `≤ ${max_hours}h` target above is itself below 4h, that target wins — the
  floor never pushes a story past the ceiling.
- **Don't pad and don't over-merge.** A genuinely self-contained sub-4h step
  that can't be coherently consolidated upward is fine as its own small story
  — but don't leave it split when it could merge into an adjacent story, and
  don't pad it to reach the floor. Conversely, don't merge unrelated work just
  because both are small. Atomicity, not list length, is the target.
- **Cover every step at least once.** ${coverage_scope} must appear in
  the `steps` field of at least one story. A step appears in more than
  one story only when you've split it; consolidated steps share a single
  story whose `steps` lists all of them.
- **`id`** is `${story_id_prefix}` followed by an integer starting at
  `${start_number}` (`${story_id_example}`, `${story_id_example_2}`,
  ...). Number stories sequentially in the order they should be worked
  starting at `${start_number}`. Do not skip numbers and do not start
  below `${start_number}` — earlier integers are already in use by
  other plans under this epic and would collide when pasted into JIRA.
- **`steps`** is a non-empty list of plan step ids (integers from the plan
  above). Every id must reference a real plan step.
- **`estimate_hours`** is a positive integer — an advisory size estimate
  (target ~`${max_hours}`h, no hard upper bound; see the sizing rule above).
- **`layer`** is one of `frontend` / `backend` / `full_stack` / `infra` —
  the layer the story's work lands in. Choose from full plan context:
  UI-only → `frontend`, service/data/API-only → `backend`, both →
  `full_stack`, build/deploy/config/tooling → `infra`. Only fall back to
  `unspecified` when the story genuinely spans no clear layer. Emit the
  bare value — never a bracket tag like `[FE]`; the renderer adds any tag.
- **`ui_impact`** is a short note on user-visible impact. Write the
  literal `none` when the story changes no user-visible behavior (typical
  for a `backend` or `infra` story) — `none` means "checked, no UI
  change", which is different from leaving the field blank. Write a
  one-line note when a `backend` or `full_stack` change surfaces a
  downstream UI follow-up a reviewer should know about.
- **`frontend_test_recommendation`** is a JSON array of short strings,
  each a concrete way to test the UI-facing behavior (component test,
  interaction/e2e check, visual/state assertion). Provide it whenever the
  story touches the frontend (`frontend` or `full_stack`, or a `backend`
  story whose `ui_impact` flags real UI follow-up); an empty list is
  correct for a story with no frontend surface. Keep each bullet short,
  one idea each — same shape as `acceptance_criteria`.
- **`acceptance_criteria`** are 2–5 short bullets a reviewer can check
  *without reading the implementation*. Each bullet must be both
  **easily attainable** (satisfied by this story's work alone — never
  forward-references other stories or future polish) AND **stable to
  refactors** (still true after a rename, file move, or test
  reorganization that doesn't change behavior).

  Prefer mechanical, scriptable checks visible at the system boundary:

    - **Behavior at the boundary:** "`GET /foo` returns 200 with a
      `cursor` field", "the dashboard shows a row per active mentor",
      "submitting the form with an empty `email` shows the inline
      `Required` error".
    - **Data / artifact invariants:** "`Setting` table contains a row
      with `settingKey=APP_MODE` and a JSON `value`", "`cdk synth`
      template diff against `main` is empty for stack X", "the generated
      settings page contains no `TODO(step-3)` marker", "`git diff
      packages/shared/src/types/vendor.ts` against `main` is empty".
    - **Observable failure / gating modes the story explicitly
      handles:** "an unauthorized user receives 403 on `POST
      /admin/app-mode`", "retrying after a partial-failure delete
      succeeds without a `User not found` error", "an ineligible user
      hits the gating page instead of the data view".
    - **Test guarantees stated as the regression they pin** (when the
      story adds tests): "a test fails if the cache-key hash drops
      `step.title` from its inputs" — *not* "`test_cache_miss` passes",
      which silently becomes false the moment the test is renamed.

  Avoid these brittleness anti-patterns — the parser will soft-warn on
  the obvious ones, but they are all bad even when not flagged:

    - **Vague quality claims** the reviewer can't run: "code is clean",
      "well-tested", "looks correct", "works as expected", "no
      regressions". State the *specific* observable instead.
    - **Brittle handles to internals:** a specific test function name
      (`test_foo`, `it('renders')`, `should_render_*`), an internal
      class / private function name that callers don't see, or a
      `file:line` pointer (`handler.ts:42`). All three break on
      harmless refactors while the behavior is unchanged.
    - **Forward references** to other stories' work: "step N+1 consumes
      this contract" — that's the *next* story's AC, not this one's.
    - **Coverage demands this story doesn't fund:** "100% branch
      coverage", "all edge cases tested". Enumerate the *specific*
      cases this story owns instead.
    - **Exact grep / call-count gates:** "`git grep old_helper`
      returns no matches", "there are zero call-sites", "the helper
      occurs exactly once". State the observable behavior or regression
      the count was trying to protect.
    - **Import-list contracts:** "`from package import A, B, C` exists",
      "the module imports X and Y". Assert the public module boundary or
      behavior instead of exact implementation wiring.
    - **File-size caps:** "file stays under 400 lines", "helper remains
      below 8 KB". Name the maintainability or behavior signal directly.
    - **Infrastructure literals outside infrastructure contracts:** exact
      AWS ARNs, IAM role names, Lambda/S3/DynamoDB resource names, or
      deployment path literals belong in descriptions unless the story's
      contract is infrastructure.
    - **Verification evidence without a done condition:** "screenshot is
      attached", "manual verification notes are recorded". Evidence can
      support the review, but the AC must assert the behavior verified.

  Cover **at least the positive case AND one failure / gating case**;
  for read-only UI surfaces also include a data-freshness criterion
  (focus-refetch, manual refresh, pull-to-refresh — whichever the
  story ships). Don't pad: a small story may have only two bullets
  if those two are enough to verify the work was done.
- **`files`** lists repo-relative paths the story will touch. Use the
  declared files-in-scope from the steps it covers; only add others if the
  story genuinely needs them.
- **`depends_on`** uses other story ids from this same response (e.g.
  `["${story_id_example}", "${story_id_example_dep}"]`). Use it to express
  ordering between stories — typically scaffolding before consumers, or a
  split story's earlier slice before its later slice. Keep it empty when
  ordering doesn't matter. Never reference an id that isn't elsewhere in
  the response.
- **Title style:** imperative, short — "Add X", "Wire Y to Z" — not
  "Adding X" or "Story for X". Do **not** prepend the story id (e.g.
  `[${story_id_example}] Add X`) to the `title` field — the renderer
  adds that prefix automatically so the markdown and the JIRA ticket
  share one canonical shape. Likewise, do **not** prepend a layer tag
  (`[FE]`, `[BE]`, …) to `title` — the renderer derives it from `layer`,
  so the markdown and the JIRA ticket keep one canonical title.
- **Cross-story references in text:** whenever `description` or
  `acceptance_criteria` mentions another story in this response, use
  the full story id (`${story_id_example}`, `${story_id_example_dep}`),
  never bare `S1` / `S2`. Bare-`S<N>` references in JIRA prose are
  ambiguous across epics and break linkbacks; full ids stay valid
  whenever the ticket is quoted.

If the plan is too vague to plan stories without more context, return a
single story whose `acceptance_criteria` is `["needs requirements
clarification"]` and whose `steps` lists every plan step id, rather than
fabricating detail.

## Writing style (strict)

Stories land in JIRA and are re-read by every assignee, reviewer, and
sprint planner — keep them tight.

- **`description` defaults to bullets, not paragraphs.** Use prose
  only for genuine narrative; everything enumerable (subtasks,
  affected files, constraints, dependencies) is a bullet.
- **`acceptance_criteria` is one observable per bullet, one short
  sentence each.** "Function X returns Y for input Z" / "a test fails
  if condition Y regresses" / "DB column W exists with type V". Never
  "code is clean" or "docs are good".
- **Active voice, imperative mood.** "Add validation in
  `handleSubmit()`" not "Validation will be added".
- **No historical narration.** Drop "previously", "used to", "the
  previous version", "this was changed because", and parenthetical
  asides like "(was: X)". State the current state and the desired
  forward state.
- **Strip filler.** Cut "it is worth noting that…", "in this case…",
  "this means that…". Get to substance.
