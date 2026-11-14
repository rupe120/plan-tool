# Plan Format Specification

> **Source of truth:** this doc is reference reading for humans and coding agents — the tool does **not** load it at runtime. The enforced contract lives in code: the Pydantic `Plan`/`Step` models in `plan_tool/schema.py` and the parser/validator in `plan_tool/parser.py`. If this doc and the code disagree, the code wins — fix the doc.

Every plan driven by `plan-tool` is a markdown file whose YAML frontmatter is authoritative. The prose body is for human review and is never parsed by the schema validator (`parse_plan` in `parser.py`).

**Note on the body:** the schema parser still ignores the body, but `plan-tool reconcile-plan` and `plan-tool completeness-audit` *do* read the body to flag missing required H2 sections. See [Body sections](#body-sections-advisory-checked) below — those checks emit advisory warnings, not validation errors.

**Location:** plan markdown can live anywhere in the repository. Register each structured plan by adding a **repo-relative** path to the `"plans"` array in `.plan-tool/plans.json` at the host repo root (or pass **`--manifest <path>`** to use another file). Alternatively, point the CLI at a single directory of `*.md` files with **`--plans-dir`** or **`PLAN_TOOL_PLANS_DIR`** (no manifest). `<N>` in filenames is an optional priority prefix (`1-`, `2-`, `3-`).

## Frontmatter schema

```yaml
---
format_version: int # optional on read (absence means legacy version 1). Every
                    # write (`write_plan` / `render_plan_text`) stamps the
                    # current version explicitly and refuses to serialize a
                    # plan whose effective version isn't current.
title: string # required. Human-facing plan title.
intent: string # optional. One line on why this plan exists — the positive half
               # of its scope fence. Presence is checked at author time, never
               # by the parser.
status: planning | in-progress # required. Plan-level lifecycle state.
        | completed
priority: high | medium | low # required.
risk_profile: low | standard | high # optional only with risk_profile_rationale.
risk_profile_rationale: string # optional one-line rationale, required with risk_profile.
lessons: string # optional. Relative path to per-plan lessons log.
test_command: string # optional. Shell command run as a post-flight gate after each
                     # successful step. Refusal-to-advance on non-zero exit.
enforce_step_tests: bool # optional. When true, `run` appends the test-creation
                         # directive to feature/refactor steps AND gates their
                         # advancement on a test file having changed. Absent = off
                         # (legacy plans); `create` writes it true on new plans.
registered_by: string # optional. Legacy provenance marker. No shipped command
                      # writes it; it is read-only history on plans adopted by
                      # the sweep orphan pass removed 2026-08-06.
source_seed: string # optional. Repo-relative path to the seed file this plan
                    # was built from. Written only by `create --from-existing`
                    # when the input path resolves inside the repo and is
                    # readable at write time; unset otherwise. Lets
                    # `completeness-audit` re-read the seed's scope contract.
features: # optional. Registry of capability ids → titles the plan declares.
  - id: string    # required. kebab-case, unique within the plan (advisory).
    title: string # required. Human-facing capability name.
steps: # required. Non-empty list.
  - id: integer # required. Must be unique within the plan.
    description: string # preferred; legacy title accepted. At least one is required.
    intent: string # optional. One line on why this step exists — the positive
                   # half of its scope fence. Same author-time-only check.
    files: [string, ...] # default []. Existing repo-relative paths the step modifies.
    creates: [string, ...] # default []. Repo-relative paths the step brings into existence (exempt from missing-file validation).
    allowed_mentions: [string, ...] # default []. Paths the step cites for context but does NOT edit.
    features: [string, ...] # default []. Registry ids this step implements (advisory).
    complexity: low | medium | high # optional. null when unset.
    change_type: refactor | feature # optional. null when unset. Drives the test directive
                | non-code          # for code steps when `enforce_step_tests` is on; non-code
                                    # carries no test directive.
    enforce_test_authoring: bool # optional. Per-step override of plan `enforce_step_tests`:
                                 # false exempts this step, true forces it on. null = inherit.
    gate: [string, ...] # default []. Shell commands run as per-step post-flight
                        # gates after test_command, before advancement. Each must
                        # be a non-empty string. Non-zero exit refuses advancement.
    depends_on: [integer, ...] # default []. Each entry must match another step's id.
    depends_on_notes: # optional. int → str; each key must be in depends_on. default {}.
      <antecedent_step_id>: string
    detail: string # optional. Path to the step's detail markdown file.
    status: pending | current # default pending. Lifecycle axis.
            | done
    scope: committed | deferred # default committed. Commitment axis, orthogonal
           | wont_do            # to status. Parked (deferred/wont_do) steps are
                                # excluded from runnable selection and from the
                                # completion tally. Elided on rewrite when committed.
    status_note: string # optional. Short prose note explaining the current status
                        # (or, for a parked step, the gate condition).
---
```

### Field semantics

**`format_version`** — the plan format's in-band version declaration, carried as a top-level frontmatter key. A raw frontmatter mapping with no `format_version` key is treated as declaring legacy version `1` before model validation runs, rather than borrowing whatever the model's own default happens to be — the two coincide at version 1, but the injection is what keeps a future current-version bump from silently relabeling old, undeclared plans as current. `parse_plan_text` refuses to validate a plan that *declares* a version outside `SUPPORTED_PLAN_FORMAT_VERSIONS`, raising `UnsupportedPlanFormatVersionError` (a `ValidationError` subtype) before schema validation proceeds — see [Validation rules](#validation-rules) for that gate's ordering guarantee. On the write side, `write_plan` and `render_plan_text` always stamp the current `PLAN_FORMAT_VERSION` into every plan they serialize, and refuse (`ValidationError`, naming both the plan's actual value and the current version) to serialize a plan whose effective version isn't current — an older-but-still-supported plan must take its explicit raw-format upgrade before it can be rewritten, rather than being silently relabeled as current. One accepted consequence: a plan this build writes is not parseable by a plan-tool build that predates `format_version`, because that older `Plan` model has no such field and rejects unknown keys under strict mode — see [Validation rules](#validation-rules) rule 9.

**`title`** — shown in `plan list` output and in the default prompt header. No length limit but keep it under ~80 chars.

**`intent`** (plan-level) — one line on **why this plan exists**. It is the *positive* half of the plan's scope fence, threaded into the authoring and execution prompts beside the negative half — see [Scope fence](#scope-fence-reaches-the-detail-and-run-prompts). Optional, defaults to `null`, and is left out of rewritten frontmatter when unset.

**Presence is the entire contract.** `plan_tool/review.py`'s `is_usable_intent` recognizes exactly three non-values — absent, empty after whitespace, and a bare `_(TODO)_`/`TODO`/`TBD`-style placeholder — and nothing judges an intent's quality, shape, or length. The check runs at author time (`review.py`'s `check_intent_presence`), **never at parse time**: empty, placeholder, and multi-line values all parse, so a plan authored before the field existed stays valid and needs no backfill. A missing intent surfaces as a blocking-capable finding — see [Smell checks](#smell-checks-advisory).

Where the value comes from: `plan-tool create` maps the first non-empty paragraph of the seed's `## Outcome` onto this field, ignoring thematic-break-only lines, and its review wizard offers a drafted line wherever one is still missing. [`SEED_FORMAT.md`](SEED_FORMAT.md) owns the seed side of that map; [`docs/how-to/pipeline/create-from-existing.md`](docs/how-to/pipeline/create-from-existing.md) owns the flow.

**`status`** (plan-level) — what state the plan is in overall. `completed` means every committed step is `done` (parked steps are ignored — see `steps[].scope`).

**`priority`** — authoring-time metadata surfaced in listings; the tool treats it as an opaque string.

**`risk_profile`** and **`risk_profile_rationale`** — a paired, persisted declaration of the plan's work-risk tier and its one-line rationale. The tier is exactly `low`, `standard`, or `high`; the rationale must contain non-whitespace text and no line break. Both fields must be present with values or both omitted. Explicit YAML `null` is invalid in either field, including when both are null. An omitted pair is accepted only as a legacy declaration: it remains absent on rewrite, while policy readers use the effective `standard` tier. New plan authoring will record both fields, including an explicit `standard` decision, so that decision stays distinct from a legacy omission. Risk profile is independent of `priority`; the parser never derives one from the other.

**`lessons`** — optional. If set, points to `plan-details/<plan-slug>/lessons.md`, an append-only log the launcher writes to after each successful step.

**`test_command`** — optional. Shell command run by `plan-tool run` after a step's claude call exits 0 and, when enabled, the test-authoring gate passes, before the step is marked `done` and the plan advanced. Use it as the plan-wide suite-pass gate: choose a command that establishes the intended suite still passes. Executed via `subprocess.run(..., shell=True, cwd=repo_root)` with a 600s timeout. Non-zero exit blocks advancement: the step stays in its current status, `status_note` records the failure tail (~400 chars), and the plan file is rewritten with the note. **Security surface:** this field is executed as a shell command (`shell=True`), so the plan's frontmatter is a code-execution vector — treat a plan file from an untrusted source the same as an untrusted script, and review `test_command` before running the plan. (In normal use the operator authors their own plans under `--permission-mode acceptEdits`, where claude can already write files, so this widens nothing; the caution is for plans received from elsewhere.)

  The optional field has no universal default. During new-plan creation, `plan_tool/create.py:_prepare_create_plan` writes it only when the fixed candidate `uv run pytest tests/ -q -n auto` both qualifies from its local markers and passes its required preflight, or when an interactive operator supplies a concrete command for that invocation. An unknown unattended creation omits `test_command` from frontmatter. These paths do not retrofit existing plans, and an operator-supplied command is not a default.

**`enforce_step_tests`** — optional boolean, default off (absent reads as `false`). When `true`, `plan-tool run` does two things for steps whose `change_type` is `feature` or `refactor`: (1) it appends the test directive to the run prompt (one shared directive for both code types — the per-type *ordering* contract was withdrawn 2026-07-30, see `change_type` below); and (2) after the step's claude call exits 0 — before the `test_command` and `gate` checks — it gates advancement on a **test file having been created or modified during the step**. "Test file" matches the usual conventions of both ecosystems the tool targets: a path under a `tests`/`test`/`__tests__` directory, a `test_*.py` basename, `conftest.py`, or a colocated Vitest/Jest basename (`*.test.ts`, `*.spec.tsx`, `*.test.js`, … — the `.test.`/`.spec.` prefix on a `ts`/`tsx`/`js`/`jsx`/`mjs`/`cjs` extension). Change detection diffs `git status --porcelain -z --untracked-files=all` captured before vs. after the call; if no test file appears in the delta, the step stays `current`, `status_note` records the refusal, and the plan is rewritten. `non-code` and unclassified steps are never gated. Outside a git work tree the check can't tell what changed and never blocks (advisory-safe). Absent (the default) leaves both the directive and the gate off, so plans authored before this switch existed keep their original behavior; `create` writes `enforce_step_tests: true` on new plans so the feature is on by default. Elided on rewrite when unset. To opt out: per step, `steps[].enforce_test_authoring: false` (see below); plan-wide, remove the key or set it `false`. The gate only verifies that *a* test changed, not that tests are meaningful or pass — pair it with `test_command`, which supplies the plan-wide suite-pass check.

**`steps[].enforce_test_authoring`** — optional boolean, per-step override of the plan's `enforce_step_tests`. `false` exempts this step (a genuinely test-less feature/refactor step, or one whose test lands in a later step); `true` forces enforcement on for this step even when the plan default is off; `null`/absent inherits the plan default. Affects both the directive and the gate, so they never disagree about a step. Elided on rewrite when unset.

**`registered_by`** — optional, and **no shipped command writes it**. It is a live legacy contract: plans on disk still carry `registered_by: sweep` from the sweep orphan-registration pass **cut 2026-08-06** (sweep now only *reports* unregistered files; `plan-tool register <path>` is the sole adoption path and sets no marker), so the field must keep parsing and round-tripping. The marker lives in the plan file rather than the manifest, so it survives deregister/re-register cycles and is visible to any consumer holding the parsed plan. Unset — and elided on rewrite — everywhere else.

**`source_seed`** — optional, written only by `create --from-existing` when the seed path resolves inside the repo root and is still a readable file at plan-write time; unset for a blank-skeleton create, an inline `--from` string, an outside-repo path, or one that no longer exists. `completeness-audit`'s conceptual pass reads it to surface the seed's own `Outcome` / `In scope` / `Out of scope / Non-goals` / `Allowed behavior changes` / `Allowed reorganization` / `Verification` / `Stop / defer` fields (exact heading match) as informational scope context — the plan body still wins on conflict. A plan whose seed carries none of those headings, or with no `source_seed` at all, renders the audit prompt unchanged. Elided on rewrite when unset.

> **Per-plan `features:` ≠ app-level capabilities.** This registry is
> *transient* and *inward-pointing* — concepts scoped to one plan, consumed by
> convergence-gap analysis, many never shipped. It is **not** the durable,
> repo-wide [`CAPABILITIES.md`](CAPABILITIES.md) catalog, which maps the
> *implemented app's* capabilities (a code surface) to the `MISSION.md`
> grounding principles they serve. The two share **no id space and no
> cross-reference**; the only thing they ever shared was the word "feature", so
> the app-level concept is named *capability*.

**`features`** (plan-level) — optional registry of capability ids. It is a **registry only**: a list of `{id, title}` objects (the `Feature` model) mapping a stable kebab-case `id` to a human title. It declares no behavior on its own. **Ownership runs step → feature, not feature → step** — each step owns the ids it implements via `steps[].features`, and the registry just supplies the id→title map. There is deliberately **no** `Feature.steps` list: because a tag references a slug, a `split`/`merge` step renumber **cannot dangle it** (the tag rides with the step). The schema enforces only **types** (a list of `{id, title}` objects, `extra` forbidden inside each `Feature`). Uniqueness, kebab-case ids, and `steps[].features` reference resolution are **advisory** — see [Smell checks (advisory)](#smell-checks-advisory). A typo never breaks parsing, so `run`/`jira`/`detail` (which call `parse_plan` and ignore features) stay inert. Optional, defaults to an empty list, and is elided from frontmatter when empty.

**`steps[].id`** — integer unique within the plan. Not required to be sequential (gaps are allowed) but conventionally 1, 2, 3… The structural-edit commands `plan-tool split` and `plan-tool merge` keep ids contiguous: `split` replaces one step with its named sub-steps and `merge` folds a contiguous, dependency-connected set into one, each renumbering the surviving steps to a contiguous `1..N` and rewiring every `depends_on` edge to the new ids. (`plan-tool merge` is the plan-step fold, unrelated to a git merge.)

**`steps[].description`** — preferred step text; legacy `steps[].title` remains accepted. Supply either spelling alone, or both with exactly equal strings (no trimming or normalization). Conflicting values or any supplied non-string value are rejected; neither spelling can conceal an invalid value under the other. Empty strings remain valid. These are two distinct field names; this alias adds no policy for repeated occurrences of the same YAML key.

The internal attribute and model dumps remain `plan_tool/schema.py:Step.title`. Both `write_plan` and `render_plan_text` emit only `description`, including ordinary rewrites of legacy-title plans, while retaining format version 1 without an explicit upgrade. Plan and feature `title` fields retain their meanings. Older installations that do not recognize step `description` reject this output even at version 1; see the [named version-1 exception](DATA_CONTRACT.md#plan-format-version-plan_toolschemapy).

**`steps[].intent`** — one line on **why this step exists**, the step-altitude twin of plan-level `intent` above: same type, same `null` default, same elision on rewrite, same presence-is-the-whole-contract rule, and the same author-time-only check. It is not a second `description`: the description names what the step changes, the intent names why the step is in the plan at all. `create` reads it off each proposed step in the step-proposal JSON, and its review wizard offers a drafted line for any step still without one.

**Intent under structural edits and the conceptual audit.** After a structural mutation or a conceptual-audit call, every surviving step's `intent` is either true of that step or absent — prefer absent over a quietly false carry-over. Presence (above) and the [Scope fence](#scope-fence-reaches-the-detail-and-run-prompts) / [Intent-presence](#smell-checks-advisory) prose stay the authoring contract; this subsection is the mutation and audit-consumer contract only. All four surfaces collapse multi-line values through `plan_tool/scope_fence.py:collapse_intent_to_one_line` — do not invent a third normalizer. Merge, forward-seed, and conceptual-audit omit use the **fence** placeholder set (`TODO` / `_(TODO)_`); bare `TBD` is outside that named set (it still clears under `is_usable_intent` for the advisory presence smell — the two predicates are not unified).

| Verb / surface | Rule | Enforced by |
|---|---|---|
| split | never copy the target's intent onto either half | `plan_tool/detail.py:split_step` |
| merge | keep intent only when every member shares the same usable value (fence placeholders count as absent); else clear | `plan_tool/detail.py:merge_steps` |
| scope-out / reground seeds | attach intent to its owner; source plan intent is not the new `## Outcome`; drop absent / blank / whitespace / fence placeholders and collapse newlines before embed | `plan_tool/scope_out.py:render_carved_seed` / `render_carved_region_seed`, `plan_tool/reground.py:render_rebaseline_seed` |
| conceptual audit | dynamic `${intent_block}` only; empty (including fence placeholders) → same prompt as an intent-free plan | `plan_tool/review.py:render_plan_audit_prompt`, `plan_tool/prompts/plan-audit.md` |

**`steps[].files`** — paths to **existing** files the step modifies, relative to the repository root. Used by `plan run --mode check` and by future verify/advance logic. Empty when the step is pure analysis. Because these are expected to already be on disk, a `files:` entry whose **parent directory** doesn't exist resolves to `MISSING_PARENT` and surfaces as a medium-severity "declared file path doesn't resolve" finding (a likely typo or wrong repo root). Applying it in `reconcile-plan-walk` prompts `(c)reate / (f)ix`: `c` moves the path into the step's `creates:`; `f` records a skip so you fix the typo. For files the step is *supposed* to create, use `creates:` instead.

**`steps[].creates`** — paths the step brings into existence, relative to the repository root. Semantically the "new file" half of the step's footprint, separated from `files:` so that validation does **not** flag them as missing: a `creates:` entry is *expected* to be absent (its parent directory may not exist yet either) until the step runs, so it never produces the `MISSING_PARENT`/`NEW` "doesn't resolve" finding and is excluded from the plan-wide path-style mismatch ratio. The one residual check is on a **done** step — if a `creates:` file still isn't on disk after the step is marked `done`, that surfaces as a "created file missing despite step marked done" finding (the work didn't land). In every other respect `creates:` files share the full footprint of `files:`: they're watched for live-edit drift, allowed by the scope-guard, snapshotted for the modify-after check, and shown in the `run`/`detail`/`jira` step views (annotated `(new)`). The per-step structural alternative to the global `--allow-missing-parent` flag. Overlap with `files:` is harmless (the merged `Step.all_files` footprint de-duplicates).

**`steps[].allowed_mentions`** — paths the step legitimately cites in its detail body for context but does *not* edit. The **explanatory-reference vs edit-target distinction**: `files:` is the edit set (consumed by `plan run --mode check` pre-flight, modify-after detection in `run` post-flight, and `jira` story scoping); `allowed_mentions:` is the citation set the *reviewer* honors. `check_files_coherence` (in `review.py`) unions `step.files | step.allowed_mentions` to build the recognized set, so a detail body that backtick-cites a path under `allowed_mentions` produces no `detail_only` finding. Use this for sibling-test references, lines-this-step-builds-on citations, or downstream-caller mentions. Overlap with `files:` is harmless (the union deduplicates); the parser does not enforce disjointness. Unrecognized citations only surface when they're a **near-miss of a declared path** (same basename in a different directory, or a near-identical full path — a likely typo or stale/moved path); these appear at `info` severity. Citations bearing no resemblance to a declared path are treated as context references and produce no finding, so in practice `allowed_mentions` is only needed to silence a residual near-miss false alarm, not every context citation. See the RUNBOOK "Near-miss filtering" section for the exact rule.

**`steps[].features`** — a list of plan-level registry `id`s this step implements. A step may tag zero, one, or several; a feature may be tagged by several steps. **Total coverage is not required** — small plans owe no busywork mapping every step to a feature. Each id should point to a `features:` registry `id`; a dangling tag (a tag with no matching registry entry) is an **advisory** finding, never a parse error — see [Smell checks (advisory)](#smell-checks-advisory). Elided on rewrite when empty (inherited from `write_plan`'s `exclude_defaults`, same as `files`/`gate`).

**`steps[].complexity`** — single-word tier. Set at plan authoring time. May be omitted; the tool does not infer it.

**`steps[].change_type`** — classifies a step so the tool knows whether it owes tests at all, and whether its footprint should contain production code. The first distinction is **code vs non-code**:

- **`non-code`** — the step changes no production code (documentation, configuration, CI wiring, deploy specs). It is asked for verification appropriate to its artifacts, not unit tests, and is never gated on test authoring. The exemplar is shopping-list-builder's `docs/implementation-plans/2-setup-digitalocean-deploy-actions.md`.
- **`refactor`** and **`feature`** (code steps) — both owe tests covering the behavior the step changes, green before the step completes. **The two share one directive; the tool does not distinguish their test *ordering*.**

> **Withdrawn 2026-07-30: the per-type test-*ordering* contract. Do not reintroduce it.**
>
> `refactor` steps used to be told to write characterization tests that pass **before** the change and unchanged after; `feature` steps to implement first, then test. The tool shipped that as prompt prose plus a phrase-matcher over the detail's `## Tests` section.
>
> **It was measured before removal:** every `refactor` step in this repo's history (32 of 313 executed steps) was replayed by checking out its parent commit, copying that step's own post-change test files in unmodified, and running them. **81–89% could not pass pre-change**, overwhelmingly for legitimate reasons — a refactor that renames, moves, or re-shapes what the tests name leaves those tests unable to *import*, let alone pass, against pre-change source. Only 3 of 28 were clean.
>
> So the directive asserted a property most refactor steps **cannot have**, and the matcher enforced only that the *document used the right vocabulary* about it. It was withdrawn rather than mechanized, because the contract — not the checker — was wrong. "Passes before and after" is satisfiable only for refactors that preserve the test-visible interface, and most real ones do not.
>
> What survives is the claim the tool can actually check: **`enforce_step_tests` verifies a test file really was created or modified.** Full record and evidence: see `CLAUDE.md` § "Withdrawn: the per-`change_type` test-ordering contract".

**Purity** applies to the step's *code*: a code step may also carry non-code elements (doc/config updates) without becoming "mixed". Optional; `null` when unset — the tool does not infer it.

**`steps[].gate`** — optional list of **shell commands** run by `plan-tool run` after the step's claude call exits 0 **and** after the plan-level `test_command` gate passes, before the step is marked `done` and the plan advanced. The step-scoped sibling of `test_command`: each entry executes via the same primitive (`subprocess.run(..., shell=True, cwd=repo_root)`, 600s timeout). The **first non-zero exit short-circuits** the remaining gate commands and blocks advancement — the step stays in its current status, `status_note` records the failing command + rc + failure tail, and the plan file is rewritten with the note. Empty (the default) is a no-op. **Validation:** the parser rejects a `gate` entry that is empty or whitespace-only (the error names `gate`). **Security surface:** like `test_command`, these entries are executed as shell commands (`shell=True`), so the plan's frontmatter is a code-execution vector — treat a plan file from an untrusted source the same as an untrusted script, and review `gate` before running the plan. (Unlike `files`/`creates`, `gate` holds commands, not paths, and is excluded from the step's `all_files` footprint.)

  **When to use `gate` vs a unit test vs `test_command`** — three layers that compose, not overlap:
  - A **durable, behavioral** invariant ("`slugify('A B')` returns `a-b`") → a **unit test**, authored for any code step (`refactor` or `feature`) and run by `test_command`. It lives in the suite permanently.
  - The **suite run itself** (or a scoped subset) → `test_command`. One plan-wide post-flight gate.
  - A **step-specific acceptance or structural check that would rot or be wrong as a permanent test** → `gate`. Examples from real plans: a `--help` golden diff captured at a phase boundary, a `grep` that a removed identifier is gone repo-wide, a per-milestone module line-cap, a `plan-tool verify-all --rollup` rollup. These belong to one step and shouldn't accumulate in the suite.

  Rule of thumb: *durable + behavioral* → unit test; *ephemeral / structural / cross-artifact / per-milestone* → `gate`. Don't use `gate` as a dumping ground for checks that should be real tests.

  **Authoring a gate.** Gates stay operator-controlled — the executable commands encode *your* judgment about what must hold before a step advances. `plan-tool suggest-gates <plan>` proposes gates *grounded in the plan's already-built steps* (or, with `--all-steps`, speculatively from a not-yet-built step's detail) and attaches the ones you keep to the remaining steps; it surfaces each suggestion for keep/edit/drop and never writes an unvetted command under `-y` (it reports without writing instead). `plan-tool create` does not propose gates. You can also just edit the `gate:` list in the frontmatter directly.

**`steps[].depends_on`** — list of step ids that must be `done` before this step can run. Validation rejects a dependency on a non-existent step id. Cycles are rejected.

**`steps[].depends_on_notes`** — optional map from antecedent step id (integer key) to a short free-form string naming what this step consumes from that antecedent. A lookup pointer for readers and downstream grounding — not a claim the tool scores. Sibling to `depends_on`: it does not replace, reorder, or reinterpret the id list; keys are antecedent ids and values are unconstrained strings.

**Structural membership is the only parse-time check.** Every key must appear in that same step's `depends_on` list, enforced by the step-level `@model_validator(mode="after")` `Step._depends_on_notes_keys_valid` in `plan_tool/schema.py`. `Plan._validate_graph` does not inspect notes — it checks id existence, self-reference, parked-step deadlocks, and cycles on `depends_on` only.

**Content is never checked.** Wording, length, plausibility, truth, and placeholder text all parse. No edge is required to carry a note — partial coverage is valid; a silent edge omits its antecedent key from the map (never `{id: ""}` from authoring paths).

**Not checked at parse time:** note presence on any edge, completeness across all edges, semantic correctness of the text, or whether the note matches what the antecedent actually delivers.

**Serialization:** defaults to `{}` and is elided from rewritten frontmatter when empty via `plan_tool/parser.py:write_plan` / `render_plan_text` with `exclude_defaults=True` (same elision story as other empty collections).

**Purity cache:** excluded from `plan_tool/fingerprint.py:compute_purity_cache_key` — metadata about an edge's rationale, not a verdict input (same class as `title`/`complexity`).

**Authoring surfaces:** `plan-tool create`'s Claude step-proposal path and manual step wizard may populate notes per edge; interactive review displays them read-only via `plan_tool/create.py:_format_depends_on_review_lines`. **`plan_tool/canonical.py:extract_canonical_steps`**, **`plan_tool/create.py:extract_steps_from_canonical`**, **`plan_tool/foundational_logic.py:merge_sweep_into_steps`**, and **`plan_tool/reground.py:render_rebaseline_seed`** stay note-less by design — do not expect backfill from those paths.

**Distinction from `SoftEdge`:** `plan_tool/completeness_report.py`'s soft-edge heuristic scans a step's detail-body prose for ordering-only markers on a `depends_on` edge; it is separate, reporting-only, and does not read `depends_on_notes`.

**`depends_on_notes` under structural edits.** After a structural mutation, every surviving step's notes are either true of that step's edges or absent — prefer absent over a quietly false carry-over (same spirit as the intent mutation prose above).

| Verb / surface | Rule | Enforced by |
|---|---|---|
| split | never copy a note onto the surviving repointed edge; always set `depends_on_notes={}` on both replacement halves; forbid the field in `_propose_step_split`'s JSON contract | `plan_tool/create.py:_apply_step_split`, `_propose_step_split` |
| merge (outbound) | keep a note only when every merging member that depended on that antecedent had identical text; members without that edge are out of the vote; else clear | `plan_tool/create.py:_apply_step_merge` |
| merge (inbound collapse) | same identical-text rule when external dependents collapse multiple edges onto one survivor | `plan_tool/create.py:_apply_step_merge` |
| scope-out narrow | remap note keys through the same old-id→new-id map as `depends_on` | `plan_tool/scope_out.py:compute_narrow` |
| carved-seed upstream | render each upstream prerequisite's note when present (done and external sections); when several carved steps share one dep, first-seen carved step wins for title and note | `plan_tool/scope_out.py:_resolve_upstream_context`, `_upstream_block` |

**Explicit exclusions:** the carved region's own internal graph (re-synthesized); **canonical extraction** (`extract_canonical_steps` / `extract_steps_from_canonical` — note-less by construction); foundational-logic consolidation steps (`merge_sweep_into_steps`); `reground` rebaseline seeds (no `depends_on` edges rendered today).

**`steps[].detail`** — path (repo-relative) to a per-step detail markdown file. Convention: `plan-details/<plan-slug>/NN-<step-name>.md` with a zero-padded numeric prefix matching the step id. The launcher loads this file into the step's subprocess prompt and nothing else from the plan's body. The detail file's own schema (the required seven-section markdown contract) is documented in **`DETAIL_FORMAT.md`**.

**`steps[].status`** — per-step lifecycle (`pending → current → done`). Exactly one step may be `current` at a time, enforced by the parser. `done` steps are skipped on `plan run` unless explicitly rerun via `--step N`. This axis carries *progress only*; whether a step is in scope at all is the orthogonal `scope` field.

**`steps[].scope`** — the commitment axis, orthogonal to `status`. `committed` (default) means the step is on the plan's critical path. `deferred` means it's parked behind a gate — kept in the plan with its `files`/`depends_on`/`detail` intact, but excluded from `next_runnable_step` selection and from the completion tally, so a plan can reach `completed` with deferred work still parked. `wont_do` records a step the author decided against but wants to keep visible for history. Put the gate/decision rationale in `status_note`. A parked step must stay `pending` (it can't be `current`/`done` — promote it to `committed` first), and a `committed` step may not `depends_on` a parked step (an unrunnable deadlock — the parser rejects both). Promote a deferred step by setting `scope: committed` when its gate opens; it re-enters the runnable set unchanged. Elided on rewrite when `committed`.

**`steps[].status_note`** — optional free-form prose explaining *why* the step is in its current status. Intended for the residual gap when a step is flipped from `done` back to `current` during reconcile, or for the gate/decision rationale on a `deferred`/`wont_do` step. Semantics are **ephemeral and scoped to the current status** — when the status changes, the note should be rewritten or cleared, not appended to. For append-only history across status transitions, use the per-plan `lessons:` log instead. The field is opt-in; the parser does not require it for any status value. YAML literal-block style (`|`) is supported for multi-line notes, though `safe_dump` may reflow whitespace on round-trip.

### Defaults

| Field | Default |
|---|---|
| `steps[].intent` | `null` |
| `steps[].files` | `[]` |
| `steps[].creates` | `[]` |
| `steps[].allowed_mentions` | `[]` |
| `steps[].features` | `[]` |
| `steps[].complexity` | `null` |
| `steps[].change_type` | `null` |
| `steps[].gate` | `[]` |
| `steps[].depends_on` | `[]` |
| `steps[].depends_on_notes` | `{}` (elided on rewrite when empty) |
| `steps[].detail` | `null` |
| `steps[].status` | `pending` |
| `steps[].scope` | `committed` |
| `steps[].status_note` | `null` |

No defaults are applied to plan-level `title`, `status`, `priority`, or `steps`. They are required. `intent`, `lessons`, `test_command`, `enforce_step_tests`, `registered_by`, and `source_seed` are optional and default to `null` when absent (and `enforce_step_tests: null` reads as off). `risk_profile` and `risk_profile_rationale` are optional only as an omitted legacy pair: that pair has effective `standard` behavior without a stored declaration, while explicit null is invalid. `create` may conditionally write a new plan's `test_command` as described in [Field semantics](#field-semantics); that creation-time emission is not a field default. Plan-level `features` is optional, defaults to an empty list, and is left out of frontmatter when empty (it is not in the table above, which is per-step `steps[].X` fields). `format_version` is optional in raw frontmatter, but — unlike every other field in this paragraph — the parser assigns a missing key the explicit legacy value `1` before model validation, rather than letting a later current-version model default relabel that raw absence as current; version 1 is current in this release, so the two happen to coincide today.

### Validation rules

The parser rejects the plan when:

1. A required field is missing.
2. A field value is not one of the allowed literals (e.g. `priority: urgent`).
3. Two steps share the same `id`.
4. A step's `depends_on` references an id that does not exist in the plan.
5. A step's `depends_on_notes` key is not a member of that step's `depends_on` (structural error — same class as an unknown id in `depends_on`).
6. The dependency graph contains a cycle.
7. More than one step has `status: current`.
8. The plan declares a `format_version` outside `SUPPORTED_PLAN_FORMAT_VERSIONS` — checked before rule 9's unknown-field rejection, so a plan carrying both an unsupported version and an unknown key is refused for the version, not the key.
9. An unknown field appears at plan level, inside a step, or inside a feature registry entry (strict mode — prevents silent typos).
10. Step `description` and legacy `title` conflict or contain an invalid supplied value (see [Field semantics](#field-semantics)).
11. A risk-profile declaration omits either paired field, uses explicit `null`, uses a tier outside `low` / `standard` / `high`, or supplies a blank or multi-line rationale.

The feature fields are an exception worth stating: the parser enforces only the **types** of `features` / `steps[].features` (a list of `{id, title}` objects and a list of strings respectively, with rule 9's unknown-key rejection still applying inside a `Feature`). Uniqueness, kebab-case ids, and `steps[].features` reference resolution are **not** in the reject set above — they are **advisory** checks that run at author time and emit findings, never a parse error. See [Smell checks (advisory)](#smell-checks-advisory).

## Example

```markdown
---
title: Example Plan
intent: Make plan frontmatter machine-checkable so drift surfaces before a run, not during one.
status: in-progress
priority: medium
risk_profile: standard
risk_profile_rationale: Routine parser work with a bounded compatibility contract.
lessons: plan-details/example-plan/lessons.md
steps:
  - id: 1
    description: Add YAML schema validator
    intent: Nothing downstream can trust the frontmatter until one place defines its shape.
    files: [plan_tool/schema.py]
    complexity: low
    status: done
  - id: 2
    description: Write structured parser
    intent: The schema is inert until a reader turns a plan file into it.
    files: [plan_tool/parser.py]
    allowed_mentions: [plan_tool/schema.py]
    complexity: medium
    depends_on: [1]
    depends_on_notes: {1: "consumes the schema types from step 1"}
    detail: plan-details/example-plan/02-structured-parser.md
    status: current
  - id: 3
    description: Build the launcher CLI
    complexity: high
    depends_on: [2]
    status: pending
---

# Example Plan

## Overview
...
```

## Body sections (advisory-checked)

The schema parser ignores the body entirely. But `plan-tool completeness-audit <name>` (and `plan-tool reconcile-plan <name>`) parse H2 headings out of the body and flag missing or `_(TODO)_`-placeholder sections. The required set matches the skeleton seeded by `plan-tool create`:

- `## Overview`
- `## Problem statement`
- `## Architecture`
- `## Steps`
- `## Out of scope`
- `## Risks`
- `## Testing`
- `## Acceptance criteria`
- `## Deferred`

`## Input` is a recognized conditional body section, not part of the ordinary
required skeleton. Include it when the plan consumes an existing data
structure, persisted schema, API surface, saved audit, output format, or
dependency-step output whose shape affects correctness. Put it near the design
context, conventionally after `## Architecture` and before `## References`, and
state what contract is read, which fields or code locations are relied on, and
what limits apply to verifying that input. Omit the section entirely for plans
that do not consume an existing contract. For persisted contracts, name the
upstream artifact and the concrete field or sidecar shape the plan consumes,
then pair explicit registered-owner references with a HEAD code-location
anchor. For example, a reference such as `SavedReview.recommendations` should
also cite an anchor such as `plan_tool/review_persistence.py:SavedReview`.
Both the field reference and the code anchor are checked against HEAD by the
data-contract audit. Ordinary shell commands, file paths, and backticked prose
are not treated as contract references unless they use a registered
owner/field form.

### Scope fence (reaches the `detail` and `run` prompts)

The fence has **two halves**, and `plan_tool/scope_fence.py:render_scope_fence`
renders both into the `${scope_fence_block}` slot the `detail` and `run`
templates carry at each grade — in `prompts/detail.md` under **"Plan-level
guardrails and scope fence"**. Order is contract, widest fence first:

1. **The intent half (positive)** — the plan's `intent`, then the step's
   `intent`, each under its own heading.
2. **The guardrail half (negative)** — five body sections, in this order:
   - `## Scope guardrails`
   - `## Audit guardrails`
   - `## Expected placement`
   - `## Stack`
   - `## Out of scope`

`extract_plan_guardrails` renders the guardrail half on its own, and the intent
half is a pure prefix, so a plan carrying no intent renders exactly the block it
always did.

The first four guardrail sections are author-supplied: `create` captures them
from the seed verbatim and they override synthesized prose (they are absent from
the plan unless the seed carried the literal heading). `## Stack` carries the
settled hosting and store choices of a roadmap-derived seed (see
`ROADMAP_FORMAT.md` § "Stack section"); the plan audit treats it as
authoritative. `## Out of scope` is part
of the ordinary skeleton, so every plan contributes a fence whether or not its
author wrote guardrails by hand.

**What the guardrail half excludes, and why an intent is not an exception.** The
guardrail channel carries fence content only — what the step must *not* build.
It deliberately excludes the plan's **delivery claims**: body sections asserting
what the plan builds, so `detail` states the step's own claims independently and
the audit can still detect a contradiction between the two. An `intent` states
**why** a unit exists, not what it delivers, so threading it leaves that
property intact — `detail` still authors its own claims, and the audit still has
two independently-written artifacts to compare.

Empty and `_(TODO)_`-placeholder guardrail sections are dropped rather than
threaded, and an intent follows the same rule: an empty, whitespace-only, or
placeholder value renders nothing at all, because an unfilled value inside a
block the prompt labels authoritative reads as a directive. A rendered intent's
whitespace collapses to single spaces — a real newline could otherwise open a
line with `##` and forge a heading inside that block — but nothing is truncated
or reshaped. `plan_tool/detail.py` imports the renderer for the `detail` prompt
and substitutes `_no plan-level guardrails or scope fence_` when a plan supplies
neither half; the `run` prompt renders the slot empty instead.

A step's detail **references** whichever entries bind it under its optional
`## Applicable guardrails` section — plan section plus a short label — and
names the boundary each imposes on that step. It does **not** reproduce the
plan's wording, nor carry over its counts or enumerations: a copy goes stale on
the next plan edit, inside a file unrelated to that edit, while a reference
cannot. Where a constraint enumerates, the detail points at the plan's list
("only the templates the fence names") rather than restating it.
`prompts/detail-quality.md` flags a detail that relaxes, contradicts, or omits
an entry, and one that reproduces a constraint instead of citing it.

Findings are advisory (`medium` severity in completeness reports; never failures of `validate`). To suppress a finding for a section that legitimately doesn't apply to a particular plan, embed an HTML comment marker inside the section body:

```markdown
## Risks

<!-- completeness:skip Risks -->
```

The marker is matched case-insensitively against the section name and suppresses both `missing` and `placeholder` findings. Other completeness checks (detail coverage, lessons, files coherence) don't honor this marker — fix the underlying condition or accept the warning.

## Smell checks (advisory)

A layer of cheap, no-Claude heuristics runs over the plan plus its `features` registry. **Most** emit a **lowest-severity (`info`), dismissible** finding. The exceptions are the sources listed in `plan_tool/review.py`'s `SELF_CONSISTENCY_SOURCES` — `suppression-shape` and `intent-presence` among them — which emit `medium`, and which the completeness battery partitions off the advisory bucket onto its blocking-capable one. **None flips the exit code** — the exit code reflects completion, and `--fail-on-findings` remains the only opt-in to turn findings into a non-zero rc; a `medium` source blocks *convergence*, not the return code.

**Where they run.** They are the deterministic layer that front-runs the conceptual completeness audit (surfaced in `plan-tool completeness-audit`'s report under a dedicated *Smells (advisory)* section, or under *Self-consistency* for the blocking-capable sources) and `plan-tool validate` (printed under `smells (advisory):`), so they fire before any Claude spend. `validate` calls the smell fan-out directly and has no gate, so it prints every one of these as an advisory smell and never acts on it, while `completeness-audit` routes the blocking-capable sources to their own bucket.

**Surfaced, never auto-applied.** Every smell is structurally kept **out** of the `--iterate` apply loop — `collect_smell_findings` is deliberately *not* wired into the deterministic fan-out that feeds `apply_finding`, because `apply_finding` is a prose editor that can fix neither a brittle structural shape nor a frontmatter field. The `SELF_CONSISTENCY_SOURCES` members differ on the *gate* half only: the completeness battery partitions them onto its blocking bucket, so they gate convergence while staying just as un-appliable. Every other smell is out of both.

**Feature-ref checks** (`review.validate_feature_refs`) — id hygiene over the feature layer: every registry `id` must be unique and kebab-case (`^[a-z0-9]+(-[a-z0-9]+)*$`), and every `steps[].features` id must point to a registry `id`. A violation (duplicate id, non-kebab id, or a dangling step tag) is an advisory finding, not a `ValidationError`. A legacy plan that declares neither a registry nor any `steps[].features` tag is skipped entirely.

**Suppression-shape check** (`review.detect_suppression_shape`) — flags a step whose **own deliverable's** stated purpose is to *suppress / downgrade / bypass / exempt / silence / disable* an existing audit gate, check, finding, or severity. It keys on a **verb → gate-object intent** within a short window, not a bare keyword, and scans both the step title and its detail body's `## Summary` / `## Why` sections. It does **not** trip on a unit that merely *describes or implements* suppression handling (a suppression-detector step, or rejected-alternative prose) — those are excused as reasoned-over rather than performed. Works on a bare step even with no `features:` block.

**Self-referential-feature check** (`review.detect_self_referential_features`) — flags a feature whose **file footprint** overlaps the validation/convergence machinery the audit itself runs through. A feature's footprint is the union of each tagged step's **full footprint** (`Step.all_files` = `files` + `creates`, **not** the literal `step.files`, which excludes `creates`) over the steps whose `step.features` tag includes that feature id. The machinery path set is **read from project config** — `validation_machinery_paths()` resolves the `smell_checks.validation_machinery_paths` key from `.plan-tool/config.json` (project, then user). The tool never hardcodes its own paths, so the check is **inert (a no-op) in any repo that has not configured the set**, and also a no-op when the plan declares no `features`.

  **Populating the key to make the check live.** Add a repo-local `.plan-tool/config.json` with the path list — this key is the only switch that activates the self-referential check:

  ```json
  {
    "smell_checks": {
      "validation_machinery_paths": ["plan_tool/review.py", "plan_tool/cli/completeness_cmd.py"]
    }
  }
  ```

  Entries must be **full repo-relative paths matching `step.all_files`** (e.g. `plan_tool/cli/completeness_cmd.py`), **not basenames** — a basename (`completeness_cmd.py`) yields zero normalized-path overlap and a silently inert check. A present-but-malformed list warns once to stderr and is treated as empty.

**Intent-presence check** (`review.check_intent_presence`) — flags a plan or step whose `intent` is absent, empty, or a placeholder. `review.is_usable_intent` is the sole judge, and it judges nothing past presence — no quality, shape, or length rule exists anywhere. At most **two** findings per plan, both `medium`: one for the plan-level field, and one **roll-up** naming every step id that lacks one (a per-step finding would scale blocking volume with step count on a corpus where most plans predate the field). It never echoes the value it read. The remedy is the one-line frontmatter edit the field semantics above describe — the source is deliberately not apply-eligible, so no apply pass writes it. Frontmatter-only, so it asks the same question at both detail grades.

**Deferred — unfalsifiable-feature check.** A declared feature with no acceptance criterion bound to it. It is **deferred**, not implemented: it needs a feature-tagged acceptance-criteria convention (a `[feature-id]` acceptance-bullet tagging scheme) that does not exist today, since acceptance criteria are free prose. This spec is the standing record of that deferral; the check unblocks once that tagging convention lands.

## Canonical step layout (input shape for `create --from-existing`)

When a `--from-existing` source is already in the strict markdown
shape below, `plan-tool create` extracts the step graph
deterministically (no Claude call for step decomposition). The
canonical document is a **content body** — no YAML frontmatter.
`create --from-existing` wraps it in the proper frontmatter when it
writes the new plan. See `SEED_FORMAT.md` for the authoring
directives that produce a seed in (or close to) this shape.

```markdown
# <Plan title>

## Overview

<paragraph(s) lifted from the source's Overview / Goal section>

## Steps

### 1. <Step title>

Type: refactor

Files:
- `path/one.ts`
- `path/two.ts`

### 2. <Next step title>

Files:
- `path/three.ts`

Depends on: 1

## Acceptance criteria

<bullets lifted from the source, when present>
```

### Layout rules

- **H1** is the plan title. Optional but conventional.
- **`## Overview`** holds a paragraph (or paragraphs) describing the
  plan. Empty section is elided rather than written as an empty block.
- **`## Steps`** is required when there are steps. Each step is an
  H3 in the form `### <N>. <Title>` where `<N>` is a positive integer
  (1-indexed, contiguous). Other heading forms (`## Phase N`,
  `### Step N`) are NOT accepted — the canonical extractor
  (`plan_tool.canonical.extract_canonical_steps`) is strict; sources
  that use other heading forms fall through to the Claude step-
  proposal path.
- **`Type:`** is an optional single line `Type: refactor|feature|non-code`
  placed directly under the `### N. Title` heading, before the `Files:`
  block. Omitted when unset; any other value (or a mis-positioned line)
  falls the source back to the Claude path.
- **`Files:` block** under each step lists repo-relative file paths
  in inline-code backticks, one per bullet. Omitted when the step has
  no declared files.
- **`Depends on:`** is a single line listing step ids the step
  depends on (comma-separated integers). Omitted when the step has no
  dependencies — typically the first step.
- **`## Acceptance criteria`** is optional. When present, holds
  bullets lifted from the source's Acceptance / Success Criteria
  section.
- Strict spacing: exactly one blank line between top-level sections
  and around `Files:` blocks. No trailing whitespace. Single newline
  at EOF.
- Commands that rewrite an existing plan (`write_plan`, which `scope-out`
  uses, and concept synchronization) preserve the
  body's bytes, including LF, CRLF and CR line endings and any unowned H1/H2
  section. A replaced owned section ends at the next H1 or H2, as the reader
  does. The frontmatter is reserialized with LF line endings, so a
  newline-only frontmatter change alters the frontmatter hash that a stale
  `scope-out` preview is checked against.

### Why strict shape matters

`create --from-existing` reads the canonical file with a strict
extractor (`extract_steps_from_canonical` → wraps
`plan_tool.canonical.extract_canonical_steps`) — anything that
drifts (extra blank lines, alternate heading forms, missing EOF
newline) is treated as non-canonical and the file falls back to the
Claude step-proposal path. Hand-editing the canonical sibling is
supported, but stay within the shape the extractor's round-trip
equality check accepts. The fallback is non-silent: when a source
body contains `## Steps` but doesn't match the strict shape,
`create --from-existing` warns to stderr before invoking Claude.

## Migration from unstructured plans

Existing plans in `docs/implementation-plans/` without YAML frontmatter continue to work with the legacy `.agents/skills/implement-plan/implement-plan.sh` and are ignored by `plan-tool`. Opting in is a two-step process:

1. Prepend a `---` YAML frontmatter block with the required fields.
2. Add the plan's repo-relative path to the `"plans"` array in `.plan-tool/plans.json` (or a file selected via `--manifest`).

Validate the result with `plan-tool validate <plan-slug>`. A `plan-tool migrate` subcommand that scripts both steps is tracked as v0.2 step 7; see `implementation-plans/archive/1-plan-tool-v0.2.md`.

**If the prepend goes wrong, it surfaces loudly.** A registered plan whose frontmatter can't be parsed at all — broken YAML, a missing or unbalanced `---` fence, or non-mapping frontmatter (`parse_plan` raises `ParseError` before schema validation even runs) — appears as a `MALFORMED` row in `plan-tool list` carrying the parse error, and `plan-tool validate <plan-slug>` resolves it and prints `INVALID:` with that error. It is surfaced for repair, not dropped from the index.

**Most common cause: the YAML colon-in-title trap.** An unquoted colon-space (`: `) inside a plain scalar — `title: Refactor: split the parser` or the minimal `title: a: b` — makes the frontmatter invalid YAML (`mapping values are not allowed here`). Quote any title containing a colon-space: `title: "Refactor: split the parser"`.
