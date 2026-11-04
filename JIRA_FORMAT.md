# JIRA_FORMAT.md

> **Source of truth:** this doc is reference reading for humans and coding
> agents — the tool does **not** load it at runtime. The enforced contract
> lives in code: the `Story` dataclass and `parse_jira_response` /
> `_render_story_markdown` / `_render_story_json` in `plan_tool/jira.py` (and
> the prompt template in `plan_tool/prompts/jira.md`) for the story shape; the
> paired export documented below is `plan_tool/jira.py`'s
> `capture_companion_export_input` / `export_jira` plus
> `plan_tool/jira_handoff.py`'s renderer and provenance contract. If this doc
> and the code disagree, the code wins — fix the doc.

The on-disk schema for the **jira story export** that `plan-tool jira` writes —
a checked-in artifact pair that turns a plan into ticket-sized stories and a
**developer handoff**. The plan file
(`PLAN_FORMAT.md`) is the source of truth; both are derived, paste-ready views
sized for a tracker and a developer, respectively — see
[Paired developer handoff](#paired-developer-handoff)
below.

## What writes them

`plan-tool jira <plan>` (orchestrator `plan_tool/jira.py`, CLI
`plan_tool/cli/jira_cmd.py`). One Claude call over the **whole** plan asks for a
consolidated set of stories, each an **atomic PR** — self-contained work that,
once its `depends_on` are merged, merges on its own while keeping the build and
tests green, never a fragment that leaves the repo broken. `--max-hours`
(default 8) is an **advisory** size target that steers consolidation, **not** a
hard cap: a large-but-atomic story is preferred over splitting it into
build-breaking slices. A soft **4h decomposition floor** complements that
ceiling at the low end — stories under 4h are skeptically flagged (advisory
lint, never a gate) to discourage over-decomposition. Stories may consolidate adjacent plan steps, and split
one large step across several stories **only when each slice is independently
shippable**; every story declares the plan step ids it covers. The plan must be
assigned to an epic in `jira-config.json` (see `plan_tool/jira_config.py`).

### Which detail bundle grounds the export

The export always grounds stories and the developer handoff on declared
run-grade detail (`steps[].detail`; see `DETAIL_FORMAT.md`). The captured
bodies, Markdown `## Plan details` links, and JSON `plan_detail_paths` all
refer to that same input snapshot.

**It fails before the backend call, and it never falls back.** Every committed
step that is not `done` must have structurally valid run-grade
detail. A present detail is validated even for `done` steps; a missing `done`
detail is retained only as historical context. Parked (`deferred` and
`wont_do`) steps never require detail and stay handoff history rather than
story work. When more than one committed step is broken, capture reports every
broken step in one refusal so an operator can repair the set in one pass.


## Output pair

Two formats, selected by `--format` (default `markdown`):

```
<plan_dir>/plan-details/<plan_slug>/jira-stories.md     # markdown (default)
<plan_dir>/plan-details/<plan_slug>/jira-stories.json   # --format json
<plan_dir>/jira-handoffs/<plan_slug>/<normalized-story-stem>.developer-handoff.md
```

`plan_slug` strips a leading `<digit>-` priority prefix from the plan filename
stem — same convention as detail files. Path computed by
`derive_jira_output_path()`.

## Paired developer handoff

Every `plan-tool jira <plan>` invocation writes a Markdown developer handoff
with the story export. The paired export captures the plan, declared run-grade detail,
declared files, and both generated destinations exactly once
(`capture_companion_export_input()` in `plan_tool/jira.py`), so the story and
the handoff always describe one snapshot rather than two independent reads.

### Destinations

```
<story destination>                                                                 # unchanged: --output / --format default
<plan_dir>/jira-handoffs/<plan_slug>/<normalized-story-stem>.developer-handoff.md    # --handoff-output / default
```

`normalized-story-stem` is the resolved story destination's basename with
exactly one final suffix removed (`jira-stories.md` and `jira-stories.json`
both yield `jira-stories`; `release.v1.json` yields `release.v1`; a
suffix-free basename is unchanged). The story and handoff destinations must
differ from each other, from the plan source file, and from every run-grade
detail artifact (`derive_detail_path()` in `plan_tool/detail_artifacts.py`,
including absent artifacts for any step). `plan-tool jira` rejects a
destination that fails any of these checks before invoking a model or writing
anything (`_companion_target_preflight()`).

### Plan path vs. suggested route — the authority boundary

The companion's **Plan path** section is generated from the plan itself and is
not a suggestion: every `scope: committed` step appears, in stable
dependency-preserving order (a topological sort, ties broken by the plan's
own step order), with its id, title, `Status: pending|current|done`, and each
declared dependency as `Depends on: <id> — <title>` (or `Depends on: none`).
A committed step's `Step.title` is its binding stated outcome and its
`Step.intent` is its binding stated purpose; a non-`done` committed step with
no title or no meaningful intent refuses the whole companion rather than
inventing either. A `done` step renders as historical
(`Status: done — historical; no implementation action`) with no suggested
route, and a blank title on a `done` step renders `_(title not recorded)_`
rather than an invented one.

Beneath each active step, the companion labels the selected detail's likely
files, anchors, sequencing, risks, and mechanics as a **Suggested
implementation route** — explicitly non-binding: *"a developer may choose a
different compliant mechanism that still fulfills the plan path above."* When
the plan body has a present `Scope guardrails` or `Expected placement`
section, the companion also states that those sections win over the
suggested route whenever the two are in tension — there is no automatic
prose-conflict classifier, and the companion never refuses publication over
that tension; a developer applies the judgment. `Audit guardrails` is
deliberately never rendered into a companion — it stays audit-only. A roadmap
seed's tool-written `## Stack` section is likewise not carried into a companion;
the section list is a whitelist that omits it.

Deferred and `wont_do` steps never enter **Plan path**, never require
selected detail, and never block companion capture. They appear only in a
**Parked plan history** appendix (id, title, scope, status note) as
non-actionable record — promote a step to committed before it can appear in a
handoff's active path.

### Regeneration and legacy adoption

Every successful export captures the plan and its inputs fresh and republishes
**both** generated files from that current snapshot. It does not preserve
arbitrary old prose. Existing Jira state carries forward only when the source
proves it belongs to this exact plan and generated pair: a keyed `draft`
becomes `created`, `created` stays created, and `dropped` remains story-source
history. A Jira key carries forward only when it occurs once and its existing
canonical covered-step set matches exactly one regenerated story.

An existing story target without paired provenance fails closed by default.
`--adopt-existing` gives explicit authority to replace one readable legacy
story source, including a UTF-8 JSON file whose JSON syntax is invalid. Without
the flag, invalid JSON refuses before the backend call; with it, plan-tool
replaces the unparseable record set rather than carrying data forward. The flag
does not relax record validation for records that do parse: malformed coverage,
duplicate live keys, mixed committed/parked coverage, or a missing regenerated
canonical-set match still refuse publication. It never adopts a handoff, a
foreign/provenance-stamped source, or a source from the other output format.

Before any of that, target preflight (`_companion_target_preflight()`) rejects
an unsafe destination: the collisions above, plus — for an existing,
non-absent target — anything that isn't a **recognized** companion-generated
source bound by its own embedded provenance to this exact
(story path, handoff path, format) pair and this same plan. A first-time
target, or a target from an earlier paired run for this exact plan and pair,
is safe to replace. A human handoff, foreign plan's source, or same-stem target
using the other format is not. The shared default handoff destination therefore
makes a Markdown-to-JSON rerun fail closed; select a distinct
`--handoff-output` before changing format.

Immediately before either file is finally replaced, publication re-derives
each target's existence + SHA-256 digest and compares it to what target
preflight captured; a mismatch (an edit landed between capture and write)
aborts every replacement not yet started (`_confirm_target_unchanged()` /
`_publish_companion_pair()`). This is not an atomic two-file guarantee — a
write that lands in the narrow gap after that final check is outside what the
check can see — and a failed or partial write is not treated as a stable end
state: its error identifies that a sibling may already have landed and directs
the operator to rerun. The next invocation always recaptures current inputs and
regenerates both files.

### Provenance

Both generated files carry the same `CompanionProvenance` block (an HTML
comment in Markdown, one JSON key in JSON — see `plan_tool/jira_handoff.py`):
the provenance/story/handoff contract revisions, the `selected_grade` provenance field (always `run`), the
source plan's repo-relative path, the selected detail source path per step,
the (story path, handoff path, format) pair identity, and a SHA-256
fingerprint over every value that can change either rendered file — plan body
context, every committed step's selected detail and file excerpts,
parked-step history, and every carried existing story record's rendered
content, covered steps, key, and state. This block is the only ownership proof:
Markdown story provenance must occupy the generated trailing-story position,
and a matching header or top-level `source_plan_path` is informational only.
The fingerprint deliberately excludes prior-run ownership evidence (the raw
target digests above), so re-running the paired export with nothing changed
reproduces the same fingerprint rather than manufacturing a false "this
changed" signal.

### Manual Jira follow-ups

The paired export never posts to or synchronizes with Jira — every note below is
advisory, printed for a person to act on, and never changes the exit code
(mirrors [Changes to a created ticket](#changes-to-a-created-ticket)):

- A `created` story whose regenerated content differs from what its source
  record carried is named, with its Jira key, as needing a manual Jira
  update.
- A `created` story whose coverage becomes entirely dropped (parked or
  removed) is named, with its Jira key, as needing a manual Jira
  cancel/close/repurpose decision.

### Not a detail, audit, or reconciliation input

The handoff is a terminal, generated artifact — never an input to `detail`
authoring, `completeness-audit`, `reconcile-plan`/`reconcile-code`, or plan
mutation of any kind.
A developer who wants a specified, run-grade-consumable implementation
contract authors it with `plan-tool detail <plan>`; `plan-tool jira` generates
the handoff and never authors detail.

## Story schema

The logical record (`Story`, `plan_tool/jira.py`), shared by both renderers:

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | `^<EPIC_KEY>-S<N>$` (e.g. `AUTH-S1`). Claude-assigned, validated. |
| `title` | string | Required, non-empty. Rendered as `[<id>] [<plan-tag>] <layer-tag> <title>` (`[<KEY>-S1] [DCL] [BE] …`) in markdown and `[<id>] [<plan-tag>] <title>` in JSON; both tags are display-only decorations — the stored `Story.title` stays clean. Either bracket is dropped (not left as an empty pair) when its value is blank — no `plan_tag` yields plain `[<id>] <title>`. See [Plan tag](#plan-tag). |
| `plain_summary` | string | Jargon-free, PM-facing 1–2 sentence preamble, rendered as the `## In plain English` section at the top of each ticket (before `## Description`). Additive: empty on legacy exports (renders `_(no summary)_`). Distinct from `description` (which carries the technical detail). Default `""`. |
| `description` | string | Prose. May be empty (renders `_(no description)_`). |
| `acceptance_criteria` | list[string] | Checkable behaviors; lint-gated — a brittle/empty AC blocks the write (see [Lints](#lints)). |
| `files` | list[string] | Repo-relative paths in scope. |
| `steps` | list[int] | **Required, non-empty.** Plan step ids this story covers. |
| `depends_on` | list[string] | Story ids this depends on; each must resolve. |
| `estimate_hours` | int | Positive integer. Advisory size signal only — no upper cap (atomicity, not hours, bounds a story); `--max-hours` is a soft target in the prompt. A soft **4h decomposition floor** complements the ceiling: a story below 4h is skeptically flagged as an advisory lint (never blocks — see [Lints](#lints)). The export stores **hours only** and never converts to story points: the team's rule of thumb is 1 point ≈ 8h, but the actual conversion depends on who picks the story up, so a person makes that call at creation time. |
| `export_state` | `draft` \| `created` \| `dropped` | Which side of the Jira handoff the story is on. plan-tool owns this and never mirrors a Jira status. Default `draft`. See [Status](#status). |
| `layer` | string | One of `frontend` / `backend` / `full_stack` / `infra`. Defaults to `unspecified` when absent or out of vocabulary. Drives the title tag (`[FE]` / `[BE]` / `[FE+BE]` / `[INFRA]`; empty for `unspecified`). |
| `ui_impact` | string | Downstream-UI-impact note for `backend`/`full_stack` stories. The literal `none` is a real answer; empty means not provided. Default `""`. |
| `frontend_test_recommendation` | list[string] | Advisory what/how-to-test bullets for frontend-impacting stories — alongside `acceptance_criteria`, not a replacement. Default `[]`. |
| `jira_issue_key` | string | The real Jira key once the ticket exists (`PROJ-4412`). Empty until then. **Deliberately last** — it is the only field a person writes rather than the tool, so it sits apart from everything above it. Default `""`. |

**Epic** (`plan_tool/jira_config.py`): `key` (the `AUTH`/`PAY` pseudo-id),
`name`, and optional `jira_epic_id` (the real tracker id, emitted in JSON only).
`key` must differ from the real JIRA project key parsed out of `jira_epic_id`
— its own or a sibling epic's — reusing it would make plan-tool's own
`<KEY>-S<N>` pseudo ids visually indistinguishable from real `<PROJECT>-<N>`
JIRA issue keys. Config load and every place an epic can be created or
edited — the `jira config` wizard's add/edit flows and `jira`'s inline
new-epic prompt — reject the collision
(`validate_epic_key_distinct_from_jira_projects` /
`validate_new_epic_key_distinct_from_jira_projects`). `jira config`
(`--show` and the wizard) is the one exception: it loads leniently
(`load_jira_config(..., enforce_key_distinct_from_jira_project=False)`)
so a config that already violates this rule can still be opened and
repaired, printing a `WARNING:` line per offending epic
(`epic_key_collision_warnings`) rather than refusing to load. Every
other command keeps the strict default and points the user at
`jira config` to fix it.

## Status

Stories are written and reviewed here, then created in Jira. **Once a story
is in Jira, Jira is canonical** — every transition, assignment, and closure
happens there, outside plan-tool. plan-tool does not mirror any of it.

So `export_state` tracks one thing: which side of the handoff a story is
on.

| `export_state` | Meaning |
|----------------|---------|
| `draft` | Not in Jira yet. plan-tool owns it and rewrites it freely. |
| `created` | Handed off. Jira owns the ticket from here. |
| `dropped` | The plan no longer covers this story. |

That is the whole vocabulary. There is deliberately no `in-progress`,
`in-review`, or `done` here — those are Jira's, and a copy of them in this
file would be wrong the moment someone moves the ticket.

### `dropped` is a fact about the plan, not the ticket

`dropped` means the plan stopped covering the story — the steps behind it
were removed or folded into something else. It says nothing about what
should happen to the Jira ticket, because that isn't plan-tool's call.

What matters is whether it was handed off first:

- **No `jira_issue_key`** — it never left plan-tool. Nothing to do.
- **Has a key** — there is a live ticket the plan no longer backs.
  plan-tool names it in the run summary so you can decide in Jira. It does
  not guess whether that means cancel, repurpose, or leave alone.

### Recording a key

After you create the ticket in Jira, open the export and fill in
`jira_issue_key` by hand. There is no command for it.

That one edit is the handoff record, and it is how a re-run knows which
stories still need creating — without it, a story you created last week and
one nobody has touched look identical.

You only write the key. The next run sees a key on a `draft` story and
flips `export_state` to `created` itself, so the two never disagree.

### Legacy exports

Exports written before this change use `status: todo|done`, and still read:

- `done` → `created`. It meant the work shipped and was accepted, which
  means the ticket exists in Jira — and Jira holds the rest of that story.
- `todo` → `draft`.

Newly written stories only ever carry the new fields. An existing ticket
is preserved verbatim, though, so an old one keeps its `status` key until
something touches it — an appended-to export can hold both spellings at
once, and both read correctly.

Two things to fix up by hand, once per old export:

- **Keys are missing.** Nothing recorded them before, so every migrated
  story comes back with an empty `jira_issue_key`. Fill them in for the
  tickets that exist.
- **A few `done` tickets are really `dropped`.** The old code also wrote
  `done` when it dropped a story from the plan, so the word covers both
  outcomes. You can spot the dropped ones — they cover plan steps that no
  longer exist.

## Plan tag

A short, human-confirmed grouping token — distinct from the epic key —
rendered into every story title so tickets from the same plan stay
visually/searchably grouped even when several plans roll up to the same
epic (a plan's tickets otherwise look indistinguishable from a sibling
plan's under the same `<EPIC>-S<N>` numbering). Resolved and persisted by
the CLI, not a `Story` field or part of the Claude prompt:

- Stored in `jira-config.json`'s `plan_tags` map (repo-relative plan path →
  tag; parallel to, and independent of, `plan_assignments`). 1–24 chars,
  letters/digits/`-`/`_` only (`validate_plan_tag()`).
- The default suggestion is `derive_plan_tag_acronym()` over the plan's
  filename slug — first letters of each hyphenated word (`decomposition-
  convergence-loop` → `DCL`), or the word itself capped at 12 chars for a
  single-word slug (`auth` → `AUTH`) — deduplicated against every tag
  already recorded in the config (`_dedupe_plan_tag()` in
  `plan_tool/cli/jira_cmd.py` appends `2`, `3`, … on a collision).
- **Resolution, in `cmd_jira`:** an explicit `--jira-tag <tag>` is
  confirmed as-is (validated); otherwise a TTY prompts to confirm/edit the
  suggested default (empty accepts it) unless `-y`/`--yes` auto-accepts it;
  off a TTY the default is auto-derived and persisted without prompting.
  Unlike epic assignment, a not-yet-confirmed tag **never blocks the
  export** — cosmetic, not an id-uniqueness requirement — so a cancelled
  TTY prompt (Ctrl-C/EOF) or an underivable slug just falls back to no tag
  for that run rather than aborting it.
- **Regeneration applies the current plan tag.** Every generated story receives
  the plan's current tag. A carried Jira key is preserved only when its
  regenerated story has the same canonical covered-step set.

## Markdown format

```markdown
# JIRA stories — <plan title>

_Epic: **<KEY>** (<epic name>)_

_<N> stories · total estimate: <H>h_

================================================================
<KEY>-S1 — Plan steps: 1, 2   (estimate: 3h)   [state: created]   [jira: PROJ-4412]
================================================================

## Title
[<KEY>-S1] [<plan-tag>] [BE] <story title>

## In plain English
<jargon-free PM-facing preamble, or _(no summary)_>

## Description
<prose, or _(no description)_>

## Acceptance criteria
- <bullet>
…                              (or _(none specified)_)

## Files in scope
- `<path>`                     (or _(none)_)

## Plan details
- Step 1: `plan-details/<slug>/01-<step-slug>.md`
- Step 2 _(no detail file)_

## Depends on
- <KEY>-S0                     (or _(none)_)

## Layer
backend                        (or `unspecified` when not provided)

## UI impact
<note>                         (or `none`, or _(none)_ when empty)

## Testing recommendation
- <bullet>                     (or _(none specified)_; the section is omitted
                                unless the story is frontend-impacting OR
                                carries a populated recommendation)
```

- The `=`×64 rule (`_STORY_SEPARATOR`) brackets each story's header line.
- `## In plain English` is the PM-facing preamble — a jargon-free summary
  rendered first (right after `## Title`, before `## Description`) so a
  reader who doesn't know the codebase grasps the ticket at a glance. It
  renders `_(no summary)_` when empty and round-trips that sentinel back to
  empty.
- The header line carries `[state: draft|created|dropped]`, which a re-run
  reads back so it can update a ticket in place without re-synthesizing it.
  `[jira: <key>]` comes **last on the line**, after everything the tool
  generated, because it is the one token a person types — and it is dropped
  entirely while the key is blank.
- `## Plan details` links each covered step to its detail file
  (`DETAIL_FORMAT.md`) — the declared run-grade file.
- `## Layer` prints the raw `layer` value; the matching tag (`[BE]` above) rides
  on the `## Title` line, as does the plan tag (`[<plan-tag>]`, dropped
  entirely when blank) — see [Plan tag](#plan-tag). `## Testing recommendation` renders for a
  frontend-impacting story (a `frontend`/`full_stack` story, or a `backend` story
  with a non-empty `ui_impact` other than `none`) **or** for any story that
  carries a populated `frontend_test_recommendation` — so a recommendation set on
  a non-frontend story is never silently dropped.

## JSON format

```json
{
  "plan_title": "...",
  "epic": { "key": "...", "name": "...", "jira_epic_id": "..." },
  "total_estimate_hours": 12,
  "stories": [
    {
      "id": "<KEY>-S1",
      "title": "[<KEY>-S1] [<plan-tag>] ...",
      "plain_summary": "...",
      "description": "...",
      "acceptance_criteria": ["..."],
      "files": ["..."],
      "steps": [1, 2],
      "plan_detail_paths": ["plan-details/<slug>/01-....md"],
      "depends_on": ["<KEY>-S0"],
      "estimate_hours": 3,
      "export_state": "created",
      "layer": "backend",
      "ui_impact": "...",
      "frontend_test_recommendation": ["..."],
      "jira_issue_key": "PROJ-4412"
    }
  ]
}
```

`jira_epic_id` is present only when configured. `plan_detail_paths` is always
present (empty list when no covered step has a detail file) so consumers can
rely on its shape. `export_state` is always present. `jira_issue_key` is
always present too, but empty until someone fills it in, and it is emitted
**last in the object** — everything above it the tool wrote, and that one
key a person did. Keep it there; don't sort it in with the rest.
`plain_summary`, `layer`, `ui_impact`, and
`frontend_test_recommendation` are always present; the JSON `title` carries
**no** layer tag (it lives only on the markdown title) — `layer` is the
structured key here. The plan tag, unlike the layer tag, **is** folded into
the JSON `title` (there is no separate structured key for it): downstream
tooling that creates tickets straight from this JSON reads `title` as the
canonical, already-tagged summary — see [Plan tag](#plan-tag). The bracket
is simply omitted when no tag was confirmed.

## Validation rules

Enforced by `parse_jira_response()` — any violation **rejects the whole
response** (the parse returns `None` and `jira` errors rather than write a
partial export):

1. **Story id** matches `^<EPIC_KEY>-S\d+$`, with the integer suffix
   `>= min_number`. Ids are unique within the response and must not collide
   with an existing story record.
2. **`estimate_hours`** is a positive integer. It is **not** capped —
   `--max-hours` is an advisory size target the prompt asks Claude to aim for,
   not a reject gate, so a large-but-atomic story parses cleanly.
3. **`steps`** is a non-empty list of **distinct** ints, every id referencing
   a real plan step. A duplicate id rejects the whole response.
4. **`depends_on`** entries each match the story-id shape **and** resolve to a
   story elsewhere in the response.
5. **Full coverage** — every committed plan step appears in at least one
   story's `steps`. Parked steps stay handoff history and never enter stories.

`plain_summary`, `layer`, `ui_impact`, and `frontend_test_recommendation` are
**additive** — a missing or out-of-vocabulary value **defaults** (`""` /
`unspecified` / `""` / `[]`) rather than rejecting the response, so legacy
exports without them still parse. They are **not** part of the numbered
hard-reject list above.

## Re-running the paired export

Every run calls the model and rewrites both recognized pair members from one
captured snapshot. A carried `created` story whose content changes is reported
with its Jira key so an operator can update the live ticket. A carried created
story that becomes dropped is likewise reported for a cancel, close, or
repurpose decision. plan-tool never edits Jira itself.

## Lints

Two lint families run over the generated stories; they differ in severity.

### Acceptance-criteria lint — **blocks the write**

`lint_acceptance_criteria()` findings are surfaced via `warn()` **and** are a
**hard gate**: `_raise_for_acceptance_criteria_lint()` raises `JiraError`
*before* the export is written, so a story with a flagged bullet is **not
exported** until it's fixed (and the same finding fails `jira --lint`, exit 1).
The gate exists because an unverifiable acceptance criterion defeats the
export's purpose — a reviewer can't run "code is clean." Categories:

- **No acceptance criteria at all** on a story.
- **Vague phrasing** the reviewer can't run: `code is clean`, `well-tested`,
  bare `tests pass` / `no regressions` / `no errors`. (`_VAGUE_AC_PATTERNS`)
- **Refactor-fragile internal handles**: a specific test function name
  (`test_x passes`/`test_x()`), a Mocha/Jest `it('…')`, a `should_*` name, or a
  `file.ext:NN` line reference — each a contract handle the implementation can
  rename without changing behavior. (`_INTERNAL_HANDLE_PATTERNS`)

### Advisory warnings — **never block the write**

These are surfaced via `warn()` on a written export for the author to act on,
but are deliberately kept out of `_raise_for_acceptance_criteria_lint`, so the
export is still written and `jira --lint` stays exit 0:

- **Missing documentation** files referenced in `files` (missing *source*
  files are expected — a story often authors them — and are not flagged).
- `lint_layer_metadata()`: a `backend`/`full_stack` story with an **empty
  `ui_impact`** (the author never recorded whether the change is UI-visible;
  `none` is a real answer and does not fire), and a **frontend-impacting**
  story whose `frontend_test_recommendation` is empty or too thin to act on.
- `lint_story_size()`: a story whose **`estimate_hours` is below the 4h soft
  decomposition floor** (`_STORY_SIZE_SOFT_FLOOR_HOURS`). This is a skeptical
  nudge to consolidate over-decomposed work — it is subordinate to atomicity,
  so a genuinely-atomic small story that can't merge upward is a legitimate
  exception and the warning is advisory only.

So `jira --lint` fails (exit 1) only on acceptance-criteria findings; a freshly
written export never fails its own lint on the advisory warnings above.

## Verification

The `jira` pipeline has no dedicated verify step. To validate the exported
stories against the implementation, run `plan-tool verify` / `verify-all`
against the plan on the post-jira branch.

## See also

- `SEED_FORMAT.md` — authoring directives for the seed the source plan was
  created from.
- `PLAN_FORMAT.md` — the plan file these stories are derived from.
- `DETAIL_FORMAT.md` — the run-grade per-step detail contract linked in `## Plan details`.
- `RUNBOOK.md` — the operational jira workflow walkthrough.
- `docs/cli/jira.md` — the generated `plan-tool jira` flag reference,
  including `--handoff-output` and `--adopt-existing`.
- `docs/reference/contracts/process.md` — the `jira` row's authority and handoff
  summary, including the paired handoff.
