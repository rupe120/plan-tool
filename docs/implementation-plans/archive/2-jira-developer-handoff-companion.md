> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Jira Developer Handoff Companion
intent: '`jira` will optionally emit concise Jira stories and a provenance-stamped
  developer-handoff companion from one captured input snapshot. The companion will
  follow the implementation plan''s complete, ordered step path and explain its suggested
  implementation route, so a developer may choose a better mechanism that fulfills
  each step''s spirit and outcome.'
status: completed
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/jira-developer-handoff-companion.md
steps:
- id: 1
  title: Capture companion-mode Jira inputs once without changing story-only detail
    tolerance
  intent: Give each requested companion one immutable snapshot of every value that
    can change either rendered artifact, including the plan body's handoff context,
    normalized generated destinations, complete generated-source pair identity, prior
    target content-state proofs, and each prior story record's handoff state and key
    ownership. It keeps predecessor companion provenance out of render inputs while
    retaining current story-only export behavior when no companion is requested.
  files:
  - plan_tool/jira.py
  - tests/test_jira.py
  complexity: high
  change_type: refactor
  detail: docs/implementation-plans/plan-details/jira-developer-handoff-companion/01-capture-companion-mode-jira-inputs-once.md
  status: done
- id: 2
  title: Extract a companion-ready story renderer without changing story-only output
  intent: Give the later companion publisher a controlled story-side rendering boundary
    while preserving every current story-only and append-mode behavior.
  files:
  - plan_tool/jira.py
  - tests/test_jira.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/jira-developer-handoff-companion/02-extract-companion-ready-story-renderer.md
  status: done
- id: 3
  title: Regenerate companion-mode stories with provable Jira-key ownership and state
  intent: Make companion mode render stories only for committed plan work, visibly
    distinguish completed historical work from active work, preserve each valid existing
    record's handoff state and history, and carry a human Jira issue key only when
    a parseable existing source proves it belongs to this plan, owns that key uniquely,
    and maps one-to-one to a regenerated committed story; it reports a keyed created-to-dropped
    transition for manual Jira action, and later paired publication will serialize
    the shared provenance onto that source.
  files:
  - plan_tool/jira.py
  - tests/test_jira.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: The captured export snapshot supplies all current inputs, including the prior
      story source state, to the companion-only renderer.
    2: The behavior-preserving renderer boundary lets this feature add current-source
      regeneration without changing story-only behavior.
  detail: docs/implementation-plans/plan-details/jira-developer-handoff-companion/03-regenerate-companion-mode-stories.md
  status: done
- id: 4
  title: Define the generated Jira developer-handoff format and lifecycle
  intent: Give developers Jira-grade prose that follows committed plan work and outcomes
    in stable dependency order, visibly preserves declared dependency edges and status,
    retains parked steps as non-actionable history, carries present scope and placement
    constraints with captured plan-body context, makes those constraints prevail over
    implementation-route suggestions, and retains a visible historical fallback for
    a done step with no selected detail.
  creates:
  - plan_tool/jira_handoff.py
  - tests/test_jira_handoff.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: The captured plan and selected-detail snapshot supplies the structure and source
      material for the handoff.
  detail: docs/implementation-plans/plan-details/jira-developer-handoff-companion/04-define-generated-jira-developer-handoff.md
  status: done
- id: 5
  title: Publish synchronized story and handoff source files without overwriting human
    guidance
  intent: Ensure companion mode publishes both generated source files from one captured
    input snapshot, reports a transient write failure, protects independent Jira-grade
    authoring and every other human-owned target through final publication confirmation,
    and permits the next current-input run to replace only recognizable same-plan
    generated sources without allowing the terminal handoff into any plan-detail bundle.
  files:
  - plan_tool/jira.py
  - tests/test_jira.py
  - tests/test_detail.py
  - tests/test_review_persistence.py
  - tests/test_concept_sync.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  depends_on_notes:
    3: The companion-mode story renderer supplies a current story source file with
      safe human-key carry-forward.
    4: The handoff contract supplies rendering, provenance, and ownership decisions.
  detail: docs/implementation-plans/plan-details/jira-developer-handoff-companion/05-publish-synchronized-story-handoff.md
  status: done
- id: 6
  title: Add an opt-in Jira companion CLI mode with explicit output behavior
  intent: Let operators request and locate the developer companion with explicit flag
    precedence, an exactly normalized derived path, complete generated-source pair
    identity and ownership checks for every generated path, stable input-fingerprint
    provenance, and visible created-ticket update and created-to-dropped lifecycle
    notices, without changing story-only or Jira-config workflows.
  files:
  - plan_tool/cli/jira_cmd.py
  - tests/cli/test_jira_cmds.py
  - tests/cli/test_direct_cmd.py
  - tests/test_jira.py
  - docs/cli/jira.md
  - tests/cli/package_surface_help.golden.txt
  complexity: medium
  change_type: feature
  depends_on:
  - 5
  depends_on_notes:
    5: The completed companion-export API gives the CLI a stable mode, result, and
      failure contract.
  detail: docs/implementation-plans/plan-details/jira-developer-handoff-companion/06-opt-jira-companion-cli-mode-explicit.md
  status: done
- id: 7
  title: 'Finish the Jira companion docs and mark BACKLOG #293 delivered'
  intent: Make the companion's authority and scope/placement boundaries, safe regeneration
    rules, usage, and delivery status discoverable without duplicating the existing
    process contract.
  files:
  - JIRA_FORMAT.md
  - docs/reference/contracts/process.md
  - docs/cli/jira.md
  - BACKLOG.md
  - docs/implementation-plans/backlog-arcs/archive/backlog-arc-jira-grade.md
  complexity: high
  change_type: non-code
  depends_on:
  - 6
  depends_on_notes:
    6: The landed CLI and output contracts provide the final names and behavior the
      documentation records.
  detail: docs/implementation-plans/plan-details/jira-developer-handoff-companion/07-finish-jira-companion-docs-mark-backlog.md
  status: done
---
# Jira Developer Handoff Companion

> **Historical delivery evidence — superseded 2026-08-23.** This completed
> plan records the opt-in companion feature as it shipped on 2026-08-22. Its
> story-only, `--developer-handoff`, append, and Jira dry-run claims do not
> govern current behavior. The unified paired-export contract is in
> [`JIRA_FORMAT.md`.

## Overview

The current export produces concise stories from the selected detail bundle;
`plan_tool.jira:export_jira` owns that read, prompt, and story write, while
`derive_jira_output_path` owns the conventional `jira-stories` destination. A
developer also needs a readable map that retains the why, guardrails, likely
route, and code anchors behind a ticket without treating its implementation
mechanics as the only permitted solution.

## Problem statement

Concise stories alone do not carry enough context for a developer to understand
why the work exists or what outcome each plan step must achieve. Copying or
promoting the detail bundle would make an
implementation suggestion look authoritative and could collide with the
independent Jira-grade authoring artifacts under `plan-details/<slug>/jira/`.

## Architecture

The implementation plan fixes the companion's binding active plan path: every
`scope: committed` step, its dependency edges, stable dependency order, status,
and stated spirit and outcome. For every committed non-done step, the required
`Step.title` is the binding stated outcome and its own meaningful `Step.intent`
is the binding stated purpose; an empty intent or an existing placeholder is
missing. Selected detail may enrich that pair but cannot supply or replace either
member. Each exported story keeps its concise grouping and labels the captured
status of every covered committed step; a story made entirely of done steps is
historical, and a mixed story identifies its done step(s) as already complete.
The companion contains an ordered prose section for every committed step and
never omits, reorders, or collapses that active path. A stable topological sort
supplies the section order; the plan's listed step order breaks ties among
independently runnable steps. Each section first renders **Plan path** and
explains the step's spirit and outcome. **Plan path** names the step id, title,
and `Status: <pending|current|done>`, then lists each declared dependency as
`Depends on: <step id> — <step title>` in stable order, or `Depends on: none`
when the step has no declared dependency. It then
labels the implementation plan's likely files, anchors, non-dependency
sequencing, risks, and technical route as a
**Suggested implementation route**. Those mechanics are not requirements: a
developer may use another mechanism that fulfills the stated spirit and outcome
while preserving the binding plan path. Selected detail may enrich that
explanation, but cannot add, remove, reorder, or replace the plan path. When
Scope guardrails or Expected placement are present, they are binding constraints
on every suggested route: the rendered route carries a visible statement that a
developer must choose a compliant alternative wherever the prose is in tension.
Companion mode does not classify that prose or refuse publication on its own.
A committed done step is visible as `Status: done — historical; no implementation
action` in both generated sources. Its selected detail and excerpt can provide
historical context, but it has no **Suggested implementation route**. A deferred
or `wont_do` step never enters a current story or the binding **Plan path**, does
not require selected detail, and cannot block companion input validation. The
handoff instead lists every parked step in a visible **Parked plan history**
appendix with its id, title, scope, and status note, but no dependency edge,
outcome, detail, excerpt, or route: `deferred` is non-actionable until promoted
to committed, and `wont_do` is non-delivery history.

After capture and before any companion model invocation or handoff/story render,
companion mode performs target preflight. It resolves both destinations and
rejects a collision, either target equal to the plan source or to *any* run- or
Jira-grade detail artifact, any target in a Jira-grade authoring lane, and every
existing target that cannot prove same-plan ownership of the complete pair. This
preflight captures the target content-state proof that final publication will
recheck; it makes no write. Only companion mode requires a complete, structurally valid selected detail
input, a `Step.title`, and a meaningful `Step.intent` for every committed
non-done step. A missing selected detail remains allowed only for a committed
done step; any selected detail that is present for a committed step but malformed
refuses companion publication. Parked-step detail is not selected or validated.
Story-only run-grade export keeps its current tolerance for an absent detail
file, and selected Jira-grade export keeps its existing no-fallback contract.
Before invoking either renderer, companion mode
captures every input that can change either terminal artifact: the full plan
document (parsed frontmatter plus exact Markdown body and source path); the
selected detail grade, paths, validation result, and exact contents; each
declared in-scope file's rendered excerpt or its missing/unreadable state; the
resolved epic, plan tag, format, maximum-hours, and first story number; and the
story-prompt and handoff-format revisions that select their rendering contracts.
The snapshot also captures both normalized generated destinations before either
renderer derives provenance from them. The pair identity is the tuple of the
resolved story destination, resolved handoff destination, and selected format,
plus the source-plan identity that both generated sources must name. A recognizable
same-plan target can be replaced only when its provenance binds it to that exact
pair. Therefore a Markdown-to-JSON or JSON-to-Markdown switch, a changed story
destination, or a changed handoff destination is a distinct pair and refuses
takeover before either final write; the command performs no automatic pair
migration.
That predecessor provenance is ownership-validation data only: it is excluded from
the newly captured render inputs and their fingerprint, so an unchanged rerun
retains identical provenance and does not create a false created-ticket update.
When an existing story destination is present, the snapshot also captures its
source-plan identity and every record's full rendered source representation,
covered-step/key/state mapping, or its absence. For each story and handoff target,
it separately records an existence marker and SHA-256 digest of the complete raw
content as a final-write content-state proof; this proof is ownership-validation
data, not a replacement for parsed provenance.
When the story destination is absent, it has no prior Jira handoff metadata.
When it exists, companion mode requires a parseable story export before either
final write. Its canonical covered-step set is a nonempty sorted tuple of unique
step ids; a record with missing, repeated, or unparseable step ids is malformed.
Every existing keyed source record must also prove it belongs to the selected
plan. The captured state applies before companion matching: a keyed `draft`
becomes `created`, a `created` record stays `created`, and a `dropped` record
stays a historical dropped record even when it has a key. A dropped record never
re-enters a regenerated committed story or companion plan path; a dropped record
that names any committed plan step refuses publication. A valid dropped record
has no committed plan step and is re-emitted unchanged in the story source as
visible history, never as a companion plan-path section. A source record covering
only parked steps becomes visible dropped history; one that mixes parked and
committed coverage refuses rather than silently narrowing a live Jira story. A
non-dropped `created` record
without a nonempty Jira key is unproven and also refuses. The companion reserves
every retained historical story id before response parsing, so a regenerated
story cannot reuse a dropped record's `<EPIC>-S<N>` identity. For every remaining
non-dropped record with a nonempty `jira_issue_key`, exactly one keyed source
record and exactly one regenerated story must have that canonical set, and that
key must occur in no other existing source record. The key is reattached only
through that one-to-one, same-plan mapping. A malformed or legacy-unproven
existing export, missing plan identity or set, repeated key, duplicate keyed
source, changed set, duplicate regenerated set, or other ambiguity refuses both
final writes rather than silently dropping or misassigning human Jira handoff
data. When regenerating a created record changes its story source, the result and
CLI name its story id and Jira key so the operator updates the live Jira ticket.
When a keyed created record becomes dropped history because its coverage is parked
or removed, the result and CLI instead name its story id and Jira key and say that
the operator must cancel, close, or repurpose the live ticket; companion mode does
not post that lifecycle action.
Story prose and grouping still render from the current captured plan inputs.
The handoff renders its captured plan-body **context** from the Overview,
Problem statement, Architecture, Out of scope, Risks, and Acceptance criteria
sections, plus present Scope guardrails and Expected placement sections. It
retains why, implementation constraints, and risks without letting that context
reorder or replace the binding step path. Audit guardrails remain audit-only and
do not enter the developer handoff. The shared fingerprint covers that complete
captured render-input representation, rather than only frontmatter and detail
bytes: it includes every carried story record, its complete rendered source
representation, covered-step set, Jira key, and normalized lifecycle state, as
well as every other value that can change either generated source. It excludes
only predecessor output ownership evidence, including the raw target content-state
proofs, so an unchanged render rerun keeps the same fingerprint. Both outputs
identify the selected source paths, normalized destinations, complete pair
identity, full input fingerprint, rendering-contract revisions, and generation
mode. The feature does not add a
semantic source-conflict classifier: its plan-driven structure and separate
suggestion label keep it from inventing a resolution.

Every committed step still receives its ordered section when it is already `done`
and has no selected detail. That section uses the step title and any meaningful
`Step.intent` recorded for that step, visibly says when no meaningful step intent
or selected detail source was recorded, and omits an invented purpose or suggested
route. A missing `Step.title`, selected detail, or meaningful `Step.intent` on a
non-done step remains a companion-mode refusal. A done step with a blank title
instead renders the visible historical fallback `_(title not recorded)_`, uses no
invented outcome, and otherwise follows the same missing-detail/intent fallback.

The companion is a terminal, generated source file with a distinct destination
from independently authored Jira-grade detail. The story destination remains
`--output` or the conventional `jira-stories.<ext>` path; the companion is
`--handoff-output` or the default
`<plan-dir>/jira-handoffs/<plan-slug>/<normalized-story-stem>.developer-handoff.md`.
First normalize the story destination with `Path.resolve()`. Its
`normalized-story-stem` is that resolved basename with exactly one final suffix
removed when present: `jira-stories.md` and `jira-stories.json` both yield
`jira-stories`, while `release.v1.json` yields `release.v1`; a suffix-free
basename remains unchanged. The default uses this rule for default and explicit
story destinations. An explicit companion path must stay outside
every `<plan-dir>/plan-details/<any-plan-slug>/` detail bundle; either generated
path is forbidden in every
`<plan-dir>/plan-details/<any-plan-slug>/jira/` independent Jira-grade authoring lane.
Before invoking or staging, companion mode resolves both normalized paths and
rejects a collision, any generated target equal to the plan source or a detail
artifact from either grade, and every existing target unless it is a recognizable
same-plan generated source artifact. After staging but before either final
replace, it confirms each target's captured ownership, complete pair identity,
and raw-content existence/digest proof. A detected mismatch, including a human
edit outside parsed ticket fields, aborts every final write not yet begun and
names the target; an unchanged recognizable same-plan generated source may still
be replaced. The confirmation
cannot observe an uncoordinated external write after that check, so the contract
makes no atomic two-file ownership claim beyond detected changes. The command
never overwrites other human-owned files observed by its ownership checks, in
addition to the prohibited locations.

For one companion-mode invocation, the staged story and companion both describe
the same captured inputs and carry the same provenance fingerprint. The files
themselves remain the current source handoff: a successful later invocation
captures current inputs and replaces both generated files. It does not preserve
arbitrary older stories or append a prior export, but it re-emits a valid dropped
story record as the existing Jira lifecycle's visible historical source. Staging
limits a partially rendered output;
if either final replace fails, the command reports the write failure and the
next invocation regenerates both source files from its current snapshot. The
companion never overwrites independently authored Jira-grade detail and is never
an audit, reconciliation, detail-authoring, or plan-mutation input. The default
`jira-handoffs/<slug>/` root sits outside the detail bundle, and explicit output
validation preserves that exclusion boundary for every plan's detail bundle.

The opt-in `--developer-handoff` mode keeps `--format` and `--output` as the
story artifact's selectors and writes the Markdown companion to an explicit
`--handoff-output` path or the default
`<plan-dir>/jira-handoffs/<plan-slug>/<normalized-story-stem>.developer-handoff.md`;
the normalized story and companion destinations must differ. The companion path
must stay outside every `<plan-dir>/plan-details/<any-plan-slug>/` detail bundle,
and both generated paths must stay outside every
`<plan-dir>/plan-details/<any-plan-slug>/jira/` authoring lane. Both also must
differ from the plan source and every selected detail source before rendering,
staging, or final output writes.
An existing companion bound by provenance to a different story-source path or
format refuses rather than being taken over, including the two default story
formats that share a normalized stem. When a regenerated created story changes,
the successful result and CLI output name its story id and Jira key as a required
manual Jira-update notice.
Companion mode rejects `jira config` and `--lint`. `--dry-run` validates
inputs and shows generation prompts and both destinations without invoking or
writing; its epic and plan-tag resolution remains read-only, requiring an
existing assignment or explicit values rather than creating config.
`--no-write` invokes and prints both labeled artifacts without publishing them;
`--stdout` additionally prints both labeled artifacts after a successful write;
`--dry-run` takes precedence over `--no-write` and `--stdout`; and `--no-write`
takes precedence over `--stdout`. These flag rules apply only in companion
mode; `--handoff-output` without `--developer-handoff` rejects before config
resolution, invocation, or writing; current story-only behavior remains
unchanged.

## References

- [argparse — Parser for command-line options, arguments and subcommandshttps: — Covers adding the opt-in companion CLI mode while preserving existing command defaults.
- [pathlib — Object-oriented filesystem pathshttps: — Documents path construction, UTF-8 file access, existence checks, and replacement behavior for generated artifacts.
- [tempfile — Generate temporary files and directorieshttps: — Covers staging outputs securely before publishing both artifacts at a controlled boundary.
- [hashlib — Secure hashes and message digestshttps: — Documents deterministic SHA-256 fingerprints for shared provenance.
- [Pydantic BaseModel APIhttps: — Covers validating captured plan and detail data before either final artifact is written.
- [PyYAML Documentationhttps: — Documents safe loading and serialization of the YAML frontmatter that supplies the plan contract.
- [How to use temporary directories and files in testshttps: — Covers isolated filesystem fixtures for testing paired writes, failures, regeneration, and authoring-lane protection.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

Changing the run/Jira detail-grade defaults or schemas; making Jira-grade detail
authoring derived rather than independently authored; external Jira posting or
sync; plan mutation; new audit, reconcile, or classification behavior; and the
withdrawn #169–#171 probe, ledger, materiality, or inversion route are out of
scope. The companion does not decide whether sources agree semantically beyond
preserving the complete plan path and labeling its route as a suggestion. It
does not prescribe a developer's implementation mechanism: a rendered Scope
guardrail or Expected placement constraint always prevails over that suggestion,
without a prose-conflict classifier or publication refusal.

## Risks

A companion that merely repeats stories adds noise, while one that presents
mechanics as requirements narrows legitimate engineering judgment. A second
output can drift if its story and companion read different inputs or an earlier
write failure is mistaken for a successful regeneration. One invocation must
therefore stage from one snapshot, report any failed final replace, and let the
next invocation regenerate both source files from current inputs. The
implementation must keep existing story-only export behavior intact for callers
that do not request the companion.

## Testing

Use stubbed export fixtures to prove that both terminal artifacts describe one
complete captured render-input snapshot and carry matching provenance on both
sources. Mutating
the plan frontmatter or captured body context, selected-detail contents,
declared-file excerpt state, renderer contract revision, epic, tag, format,
max-hours, or first story number changes both regenerated source files on the
next companion-mode invocation; changing only either normalized destination does
the same. A carried record's rendered text, Jira key, or lifecycle state also
changes that shared fingerprint. A rerun with unchanged render inputs proves
predecessor ownership evidence neither changes the fingerprint nor creates a
created-ticket update.
Fixtures prove that the captured body context renders why, present
scope and placement constraints, and risks, while audit-only guardrails stay out.
Missing or malformed companion-mode input
fixtures fail before either output write, while existing story-only missing-detail
behavior remains valid. Fixtures cover a final write failure between the two
generated files, a visible error, and a later current-input invocation that
regenerates both without retaining failure state.
They also prove companion mode replaces an existing generated story output rather
than appending to it, carries matching complete-pair provenance on both sources,
captures existing source-plan identity and each record's rendered representation
and covered-step/key/state mapping in the shared snapshot, promotes a keyed `draft`
to `created`, preserves a keyed `created` record while reporting its changed Jira
ticket, and retains a valid dropped record only in the story source as historical
rather than reintroducing it into the committed plan path. Fixtures refuse a
dropped record that names a committed step, normalize a record covering only
parked steps to visible dropped history, refuse a mixed parked/committed record,
and reject a keyless `created` record. They reserve retained historical story IDs
before response parsing, refusing an ID collision, and report each keyed created
record that becomes dropped history as a distinct manual Jira lifecycle follow-up.
They
retain a `jira_issue_key` only through one parseable same-plan non-dropped keyed
source and one regenerated story for a nonempty canonical covered-step set, and
refuse before either write for malformed, legacy-unproven, missing, repeated-key,
duplicate, changed, or ambiguous mappings. A focused
consumer fixture proves the implementation plan
controls complete committed-step coverage, dependency order, visible per-step
status and dependency edges (including `Depends on: none`), and the rendered
explanation of each active step's purpose and outcome from its `Step.intent` and
title, while the route remains a suggestion that a developer may improve. It
covers a missing committed non-done title or `Step.intent` as a refusal, a done
step without selected detail or step intent as a visible historical fallback
rather than invented guidance, a done step with a blank title as
`_(title not recorded)_`, a malformed present committed done detail as a refusal,
and a parked-step appendix with no actionable route or detail requirement.
Fixtures with present Scope guardrails or
Expected placement prove the visible scope-priority statement without requiring a
prose-conflict classifier or publication refusal. CLI
fixtures prove the exact derived
handoff path under `jira-handoffs/<slug>/` for default, JSON, and explicit story
destinations, including a multi-suffix and suffix-free explicit path;
story/companion destination collision; rejection of a changed explicit handoff
destination as a distinct generated-source pair; and target preflight before a
model invocation or renderer runs. Fixtures reject a companion path in the current
or another plan's detail bundle, and reject either generated path in the independent
Jira-grade authoring lane, any run- or Jira-grade detail artifact including the
unselected grade, the plan source, or an unrecognized human-owned target. Fixtures
also prove that an established companion cannot be
taken over by a different story format sharing its default normalized stem, and
that a target changed before its final confirmation, including an edit outside a
parsed record, aborts every final write not yet begun. Detail-
sibling discovery, review fingerprinting, and concept synchronization fixtures
prove that the generated default companion never becomes an upstream input. CLI
fixtures also prove
companion-plus-lint/config combinations fail before publication, dry-run shows
prompts and both destinations only, including no config write when an assignment
or tag is missing, `--handoff-output` without companion mode rejects before any
config or output effect, and no-write wins over stdout otherwise. Existing
story-only fixtures continue to prove unchanged behavior when the companion mode
is absent.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (refactor) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- An opt-in Jira export produces concise stories and a developer map
  grounded in one complete captured render-input snapshot, with readable
  provenance on both sources, normalized destinations, captured plan-body context
  including present scope and placement constraints, a binding,
  dependency-preserving plan path, and a fingerprint that includes every
  render-affecting carried story record while excluding predecessor-output
  ownership evidence.
- Each map gives every committed plan step ordered Jira-grade prose that explains
  its spirit and outcome, then presents the implementation plan's route as a
  suggestion a developer may improve. The committed coverage, status, dependency
  edges, stable topological order, and step spirit/outcome remain binding. Each
  Plan path section visibly lists `Status: <pending|current|done>` and its
  declared dependency edges or `Depends on: none`; likely files, anchors,
  non-dependency sequencing, risks, and mechanisms do not. A committed non-done
  step with no title or meaningful `Step.intent` refuses companion publication. A
  committed done step is visibly historical with no implementation action and,
  when sources are incomplete, carries a visible historical fallback instead of
  invented guidance; a blank done title renders `_(title not recorded)_` rather
  than an invented outcome. Deferred and `wont_do` steps appear only in the
  handoff's non-actionable parked-history appendix and require no detail. Suggested
  routes visibly state that rendered Scope guardrails and Expected placement
  prevail; where the prose is in tension, the developer uses a compliant
  alternative without companion-mode conflict classification or refusal.
- Invalid companion-mode input prevents both final output writes; target preflight
  refuses an unsafe destination before companion model invocation or rendering; an unchanged
  story-only mode keeps its current missing-detail behavior; a malformed present
  selected detail refuses even when its step is done; and the feature does not
  classify prose-level source conflicts.
- Each successful companion-mode invocation stages and replaces both generated
  source files from its current captured inputs. A write failure reports an error;
  a later invocation regenerates both files from current inputs. A target mismatch
  detected at its final ownership confirmation aborts every unstarted replacement;
  an uncoordinated post-check external write remains outside that detection
  guarantee.
- Existing source-plan identity and each record's covered-step/key/state mapping
  are captured in the shared input snapshot. A keyed `draft` becomes `created`, a
  keyed `created` record stays created and reports its changed live Jira ticket,
  and a valid `dropped` record stays historical in the story source rather than
  re-entering a committed story or companion path. A dropped record naming a
  committed step, a mixed parked/committed source record, a reused retained
  historical story ID, or a keyless non-dropped `created` record refuses
  publication. A record covering only parked steps becomes historical dropped
  source, and a keyed created record that becomes dropped produces a distinct
  manual Jira cancel/close/repurpose notice. A
  non-dropped `jira_issue_key` stays attached to a regenerated story only through
  one parseable same-plan keyed source record and one regenerated story for a
  nonempty canonical covered-step set. A nonempty key occurs in only one existing
  source record. A malformed, legacy-unproven, missing, repeated-key, duplicate,
  changed, or ambiguous mapping refuses publication without discarding the key.
- The default companion destination is
  `<plan-dir>/jira-handoffs/<plan-slug>/<normalized-story-stem>.developer-handoff.md`.
  `normalized-story-stem` removes exactly one final suffix from the resolved
  story basename and otherwise retains it. The companion never enters the detail
  bundle of any plan or an upstream audit/reconciliation input. Companion mode rejects a
  story/companion path collision, an explicit companion path in any plan-detail bundle,
  either generated path in the independent Jira-grade authoring lane, a detail
  artifact from either grade, including the unselected detail grade, either generated path equal to the plan source, or
  any existing target that is not a recognizable same-plan generated source, an
  existing generated source bound to a different story destination, handoff
  destination, or format, or a target whose raw-content mismatch is detected at
  final ownership confirmation. It also rejects
  unsupported lint/config combinations and `--handoff-output` without
  `--developer-handoff` before config resolution, invocation, or publication. Its
  dry-run, no-write, and stdout behavior follows the stated precedence, with
  dry-run first; dry-run never creates an epic or plan-tag assignment.
- The normal story-only export and the independent Jira-grade authoring lane
  retain their current behavior.
- The documented command, locations, structure-versus-suggestion boundary,
  safe regeneration rule, scope/placement constraint treatment, and BACKLOG #293
  delivery status are verified before #293 is closed.

## Deferred

Feedback from actual developers on whether the companion's structure is useful,
and any later Jira-native attachment or synchronization workflow, remain
separate work. If this export uncovers broader disagreement about which detail
grade should be canonical, record that decision separately rather than widening
this terminal-handoff effort.
