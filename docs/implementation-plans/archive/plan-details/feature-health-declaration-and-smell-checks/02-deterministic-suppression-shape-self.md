# Step 2 — Add deterministic suppression-shape and self-referential smell detectors in `review.py`, reading the validation-machinery path set from project config

## Summary

Add two **advisory, no-Claude** smell detectors to `plan_tool/review.py` plus one config accessor to `plan_tool/project_config.py`. `detect_suppression_shape` flags a step/feature whose stated purpose is to *suppress/downgrade/bypass an existing audit gate* — keying on a verb→gate-object proximity match gated by a **subject-attribution rule** (the suppress-verb's subject must be the plan unit itself, not a quantified/reported/meta subject), not a bare keyword, so this plan's own "suppression-shape detector" titles **and** its descriptive detail-body prose do not trip it. It scans **both** the step/feature title **and** the step's detail-body (`## Summary`/`## Why`), so the motivating `type_impure` shape — whose suppressing purpose lives in its rationale prose, not its anodyne title — is caught (a title-only check would have near-zero recall on that case). `detect_self_referential_features` flags a feature whose file footprint (its steps' `step.all_files`) overlaps a **configured** validation-machinery path set read from `.plan-tool/config.json`, and is **inert when that set is unconfigured** (never hardcodes plan-tool's own paths). Both are exposed through one public `collect_smell_findings` entry that steps 3/4 will wire into the completeness/`validate` surfaces. The load-bearing decision: step 2 only *adds* the detectors + their unit tests — it does **not** touch `collect_deterministic_findings`, so no existing flow surfaces the findings yet (surfacing is steps 3/4's owned scope). On green: calling the detectors directly yields `Recommendation`s at the lowest advisory severity, the self-referential check returns `[]` with no config, and the suppression check distinguishes a gate-suppression from a suppression-handler.

## Table of Contents

- [Why](#why) — what's missing and why these two shapes are detectable at author time
- [Files (creates vs edits)](#files-creates-vs-edits) — the three declared files and their edits
- [Implementation](#implementation) — the config accessor, the two detectors, the public collector
- [Tests](#tests) — detector + accessor cases in `tests/test_review.py` and `tests/test_project_config.py`
- [Test-creation order (feature step)](#test-creation-order-feature-step) — author tests with the code; green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — pydantic / config / stdlib docs relevant to this step
- [Deferred](#deferred) — out-of-footprint items (surfacing, reader consolidation)

## Why

The `merge-steps-executor` plan burned four completeness audits on a `type_impure` flag whose only job was to *suppress* the mixed-step finding the merge produced, and which *modified the very completeness/convergence machinery auditing it* — so the audit could never stabilize. Both shapes are detectable deterministically at author time, before any Claude spend, but nothing surfaces them today. This step adds the two cheap heuristics: a **suppression/escape-hatch** detector (a verb→gate-object intent) and a **self-referential** detector (a feature whose footprint overlaps the audit machinery). The self-referential set is repo-specific, so it is read from project config and stays inert otherwise — shipping plan-tool's own paths hardcoded would couple the tool to its own source tree. Step 1's `features:` layer (the `Feature` model + `Plan.features`, **not yet on disk at HEAD**) is the hard prerequisite for the self-referential check, which keys on a feature's file footprint.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/project_config.py` — add a `validation_machinery_paths(repo_root) -> list[str]` accessor (block `smell_checks`, key `validation_machinery_paths`; project → user → `[]`), a private `_read_smell_block` reader, a `_is_valid_path_list` validator, and the `SMELL_CONFIG_BLOCK` / `VALIDATION_MACHINERY_PATHS_KEY` constants.
  - `plan_tool/review.py` — add the suppression intent regex + verb/object constants, two advisory severity constants, `detect_suppression_shape` (scans step/feature titles **and** the step detail-body `## Summary`/`## Why`, read from `step.detail` under `repo_root`), `detect_self_referential_features`, and the public `collect_smell_findings` entry. **No edit to** `collect_deterministic_findings` or `APPLY_ELIGIBLE_SOURCES`.
  - `tests/test_review.py` — add `TestDetectSuppressionShape`, `TestDetectSelfReferentialFeatures`, `TestCollectSmellFindings` classes (inline plan-text fixtures, mirroring `TestCheckTestStrategyAlignment`).
  - `tests/test_project_config.py` — add `validation_machinery_paths` resolution/validation cases.

## Implementation

### `plan_tool/project_config.py`

**Add module-level constants** beside `BRANCH_AWARENESS_ENV` / `PROJECT_CONFIG_SUBPATH`:

- `SMELL_CONFIG_BLOCK = "smell_checks"` — the new top-level config block name.
- `VALIDATION_MACHINERY_PATHS_KEY = "validation_machinery_paths"` — the key inside it.

**Add `_read_smell_block(path: Path) -> Optional[dict]`** — a parallel to the existing `_read_level` (the `branch_awareness`-specific reader), returning the `smell_checks` mapping or `None` on any malformed shape (absent file, `json.JSONDecodeError`, non-dict top level, block missing / not a dict). **Never raises** — same per-level tolerance posture as `_read_level`.

- **Do not generalize `_read_level` into a block-name-parametrized reader in this step.** Rewiring `branch_awareness_enabled` / `branch_prefixes` onto a shared reader is a behavior-preserving refactor outside this feature's scope; adding a second small reader keeps the branch-awareness path byte-identical. Record the consolidation (one `_read_block(path, name)` feeding both) as deferred — see [Deferred](#deferred).

**Add `_is_valid_path_list(raw: object) -> bool`** — mirror `_is_valid_prefix_list`: `True` only when `raw` is a non-empty `list` whose every element is a non-empty `str`. No git-ref validation (these are repo-relative file/dir paths, not branch prefixes), so do **not** reuse `_is_valid_branch_prefix`.

**Add `validation_machinery_paths(repo_root: Path) -> list[str]`** — modeled on `branch_prefixes`:

- Resolution order **project → user**, **no env axis** (mirrors `branch_prefixes`; the path set is repo-structural, not an operator toggle).
- Take the first level whose `smell_checks.validation_machinery_paths` key is present. If `_is_valid_path_list(raw)` → return `list(raw)` (a fresh copy). If present-but-invalid → warn once to stderr naming the offending file (mirror `branch_prefixes`' bad-list warning) and return `[]`.
- **Default `[]` ("inert") when no level configures it** — the self-referential check returns no findings on an empty set. This is the "inert when unconfigured" guarantee at the config layer.
- Stays a stdlib-only leaf (no new imports beyond what `project_config.py` already uses).

### `plan_tool/review.py`

**Add advisory severity constants** beside the existing `_TEST_STRATEGY_*_SEV` block:

- `_SUPPRESSION_SHAPE_SEV = "info"` — the **lowest** advisory level (per the plan body: pin suppression to lowest, emit a dismissible rationale; legitimate cases exist).
- `_SELF_REFERENTIAL_SEV = "info"` — advisory; lands outside the medium/high/critical blocking band (`convergence.py:BLOCKING_SEVERITIES`) so step 3's blocking-gate exclusion is structural, not a special case.

**Add suppression-intent matching constants + regex** near the other module-level pattern constants (e.g. by `_PATTERN_TEMPLATES`):

- `_SUPPRESSION_VERBS` — frozenset of suppression verb stems: `suppress`, `downgrade`, `bypass`, `exempt`, `silence`, `disable`, `mute`, `skip`, `whitelist`. The noun `suppression` is **not** treated as a verb (see precision note).
- `_GATE_OBJECT_NOUNS` — frozenset of the gate/check vocabulary: `gate`, `check`, `finding`, `audit`, `severity`, `warning`, `validation`, `lint`, `rule`, `smell`.
- `_SUPPRESSION_INTENT_RE` — a compiled, case-insensitive regex matching **a suppression verb (optionally inflected `-s/-es/-ed/-ing`) governing a gate-object noun within a short window**, e.g. `\b(suppress|downgrade|bypass|…)(?:e?s|ed|ing)?\b[\w\s\-'`/]{0,30}?\b(gate|check|finding|…)s?\b`. The bounded `{0,30}` gap captures "downgrade the mixed-step **finding**", "bypass the purity **gate**", "silence the duplicate-notification **warning**". This regex is **necessary but not sufficient**: it is the verb→object pre-filter, and a hit must then pass the subject-attribution rule below before it counts as a match.
- **The match is a subject-attribution rule, not bare verb→object proximity** — this is the load-bearing precision decision (plan body). Verb→object adjacency alone cannot separate "this step **downgrades** the mixed-step **finding**" (trip) from "**flags** a step that **suppresses** the **finding**" (must-not-trip): both carry the verb→gate-object adjacency the proximity regex keys on. So a `_SUPPRESSION_INTENT_RE` hit only counts when the suppress-verb's **grammatical subject is the plan unit itself as the actor** — a first-person self-declaration of suppressing purpose (subject is this step/feature: "this step downgrades…", "suppress the mixed-step finding" stated as the unit's own job). A hit whose suppress-verb is governed by a **quantified, reported, or meta subject** — "flags a step *that* suppresses…", "any step whose purpose is to bypass…", "the detector/check that downgrades…" — does **not** count: there the suppress-verb describes a hypothetical *other* unit, which is the shape of every detector/audit-machinery description. Implement this as a post-regex **clause-level** subject test, not an immediate-preceding-token reject list (which is mechanically wrong: in "whose stated purpose is **to** suppress…" the token right before `suppress` is `to`, not the relativizer; and "this **step** downgrades…" vs "a **step** that suppresses…" share the adjacent noun `step`, so adjacency can't tell trip from non-trip). Instead: locate the clause governing the suppress-verb — recognizing the "[subject] whose **purpose/job is to** <suppress-verb>…" construction and binding the verb to the noun the `purpose`/`job` attaches to — then classify by the **determiner of that subject noun**. A demonstrative (`this step`/`this feature`) or a named concrete artifact the unit introduces = **trip** (the unit declares its own deliverable's suppressing purpose). A quantifier or relativizer governing the clause (`a`/`an`/`any`/`that`/`which`/`whose` heading a described/hypothetical unit — "a step that suppresses…", "any step whose purpose is to bypass…", "the detector/check that downgrades…") = **non-trip** (the subject is a class of units the prose reasons over, the shape of every detector/audit-machinery description). Key on the subject's determiner at the clause level, not the token adjacent to the verb, and do not widen the regex.
- **Precision is the load-bearing decision, not recall** (plan body). A bare keyword match is wrong: it false-positives on any step that merely *describes/implements* suppression handling — including **this plan's own** step-2 title ("Add … **suppression-shape** … smell detectors", where `suppression` is a noun modifier with verb `add` and object `detectors`), **this plan's own step-2 `## Summary` detail-body** ("flags a step/feature whose stated purpose is to suppress/bypass an existing audit gate" — a quantified/meta subject, the exact verb→gate-object adjacency the regex catches but the subject-attribution rule rejects), and the merge plan's rejected-alternative prose. State this in the docstring with a trip ("this step downgrades the mixed-step finding"), a title non-trip ("add suppression-shape detectors"), and a detail-body self-description non-trip (step 2's own Summary, "flags a step that suppresses the gate").

**Add `detect_suppression_shape(plan: Plan, repo_root: Path, *, plan_name: str) -> list[Recommendation]`:**

- Scan **`step.title` for every step**, **the step's detail-body** (its `## Summary` and `## Why` sections, read from `step.detail` resolved under `repo_root`), and **`feature.title` for every feature** (when `plan.features` is non-empty). Title is one "stated purpose" signal, but title-only has near-zero recall on the motivating shape: the `type_impure` case stated its suppressing purpose in its rationale/detail, not its title (a real step title reads "Add a persisted `change_type` flag," never "suppress the mixed-step finding"). So detail-body scanning is **in-scope, not deferred** — read the detail markdown, extract the `## Summary`/`## Why` body text, and run the same verb→gate-object **plus subject-attribution** match over it. The subject-attribution rule is what keeps detail-body scanning precise over multi-sentence prose: step 2's own `## Summary` carries the verb→gate-object adjacency ("flags a step/feature whose stated purpose is to suppress/bypass an existing audit gate") yet must **not** trip, because the suppress-verb's subject there is a quantified/reported unit, not the plan unit declaring its own purpose. Apply the same post-regex subject test to body sentences as to titles. Resolve `step.detail` defensively: a missing or unreadable detail file contributes no body text (the title scan still runs); reading is bounded to those two sections, keeping the detector cheap.
- Emit one finding per matching step (`step_id=step.id`) or feature (`step_id=None`), `source="suppression-shape"`, `severity=_SUPPRESSION_SHAPE_SEV`, a short `title` (the non-default `Recommendation.title` field — e.g. `"Suppression-shape smell"`, set explicitly as `check_test_strategy_alignment` does), and a `body` carrying a plain-language **dismissible** rationale naming the matched phrase, noting whether it matched the title or the detail-body (`## Summary`/`## Why`), and stating that legitimate suppression exists (e.g. "suppress duplicate notifications"). A step matching in both title and body emits a single finding.
- Mint ids via `_make_rec_id` (folds source into the id): fingerprint `f"suppression-shape:{step.id}"` for steps (one per step regardless of where the phrase matched), `f"suppression-shape:feat:{feature.id}"` for features.
- **Works on a bare step with no `features:` block** — the step loop runs regardless; this is the one check useful before any feature is declared.
- **Co-occurring signal (rationale enrichment, not a gate):** when a matching step's `step.all_files` includes a schema/config file (`plan_tool/schema.py`, any `*.json`/`*.toml`), note "also adds a flag/field that could silence a check" in the rationale to raise operator confidence. Do not require it to emit.

**Add `detect_self_referential_features(plan: Plan, repo_root: Path, *, plan_name: str) -> list[Recommendation]`:**

- Read the configured set: `machinery = project_config.validation_machinery_paths(repo_root)`. **Return `[]` immediately when empty** (inert-when-unconfigured) and when `plan.features` is empty (the check keys on a feature footprint).
- For each feature, build its footprint = union of `step.all_files` over the steps in `feature.steps`, resolved via a `{s.id: s for s in plan.steps}` dict (skip an id not present — benign; step 1's `Plan._validate_features` already guarantees resolution, but the detector stays defensive).
- **Overlap predicate:** a footprint path `f` overlaps a configured path `c` when `PurePosixPath(f) == PurePosixPath(c)` **or** either is `relative_to` the other (so a configured directory entry matches files under it, and vice-versa). Collect the overlapping footprint paths.
- Emit one finding per overlapping feature, `step_id=None`, `source="self-referential"`, `severity=_SELF_REFERENTIAL_SEV`, a short `title` (the non-default `Recommendation.title` field — e.g. `"Self-referential feature smell"`, set explicitly as `check_test_strategy_alignment` does), and a `body` naming the feature id, the overlapping footprint paths, and the matched machinery paths, with a rationale that a feature modifying the audit machinery cannot be cleanly audited by it. Fingerprint `f"self-referential:{feature.id}:" + ",".join(sorted(overlap))`.
- Use `step.all_files` (the order-preserving, de-duplicated accessor at `plan_tool/schema.py:Step.all_files`), **never** `step.files + step.creates` by hand.

**Add `collect_smell_findings(plan: Plan, repo_root: Path, *, plan_name: str) -> list[Recommendation]`** — concatenate `detect_suppression_shape(plan, repo_root, plan_name=...)` + `detect_self_referential_features(plan, repo_root, plan_name=...)` (both take `repo_root` — suppression to resolve `step.detail`, self-referential to read config). This is the single public entry steps 3 (completeness) and 4 (`validate`) import; keeping the surface to one function means the surfaces don't enumerate detectors.

**Load-bearing non-edits (state in the docstrings):**

- **Do not add `"suppression-shape"` / `"self-referential"` to `APPLY_ELIGIBLE_SOURCES`** (`plan_tool/review.py: APPLY_ELIGIBLE_SOURCES` constant). They are structural diagnostics — `apply_finding` (a prose editor) can't fix a brittle shape; the remedy is to split/cut/extract the feature. Their absence routes them to `is_apply_eligible(rec) == False` and the generic `triage_reason` "structural diagnostic" branch automatically — no `triage_reason` special-case needed (contrast the `detail-purity` branch at `plan_tool/review.py:triage_reason`).
- **Do not edit `collect_deterministic_findings`.** It feeds create/detail/launcher/completeness (`plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/launcher.py`, `plan_tool/cli/completeness_cmd.py` all call it); wiring the detectors there would auto-surface them through every flow and pre-empt step 3's "surface through the completeness-audit deterministic layer" + step 4's `validate` work. Step 2 ships the detectors + the `collect_smell_findings` seam only.

**Foundational logic / shared-location audit.** The core rule is *deterministic, advisory, no-Claude finding emission keyed on plan shape* — the exact pattern of `plan_tool/review.py:check_test_strategy_alignment` (returns `list[Recommendation]`, `source` absent from `APPLY_ELIGIBLE_SOURCES`, advisory severity, ids via `_make_rec_id`). Mirror that function for **shape**; the detection logic is net-new. The only sibling that emits deterministic findings is `check_test_strategy_alignment` (appended inside `collect_deterministic_findings`); there is no duplicated suppression/self-referential logic elsewhere to consolidate. Keep the new detectors as standalone functions beside it rather than folding into `check_test_strategy_alignment` — different inputs (config + features vs `change_type`) and a different surfacing path (steps 3/4 via `collect_smell_findings`, not `collect_deterministic_findings`).

## Tests

### `tests/test_review.py` (new classes; mirror `TestCheckTestStrategyAlignment`, inline plan-text fixtures)

`class TestDetectSuppressionShape`:
- `test_gate_suppression_step_flagged` — a step titled "downgrade the mixed-step finding" emits one `source="suppression-shape"`, `severity="info"` finding.
- `test_bypass_gate_flagged` — "bypass the purity gate" trips.
- `test_suppression_handler_step_not_flagged` — this plan's own step-2-style title ("Add deterministic suppression-shape and self-referential smell detectors") emits `[]` (noun-adjunct, no verb→gate-object).
- `test_bare_keyword_without_gate_object_not_flagged` — "disable the cache" (no gate-object noun) emits `[]`.
- `test_works_without_features_block` — a plan with no `features:` still scans step titles and flags a gate-suppression step.
- `test_detail_body_suppression_flagged` — a step with an anodyne title ("Add a persisted `change_type` flag") whose detail-body `## Summary`/`## Why` states a **first-person** verb→gate-object intent ("this step suppresses the mixed-step finding") is flagged (the motivating `type_impure` shape); the finding body notes the match came from the detail-body.
- `test_detail_body_self_description_not_flagged` — a step whose detail-body `## Summary` *describes* a detector with a quantified/meta subject (this plan's own step-2 Summary verbatim: "flags a step/feature whose stated purpose is to suppress/bypass an existing audit gate") emits `[]` even though it carries the verb→gate-object adjacency — the must-not-trip detail-body fixture that pins the meta-plan false positive the plan body names. This is the detail-body counterpart to `test_suppression_handler_step_not_flagged`; both trip/non-trip contracts are pinned with detail-body fixtures, not titles alone.
- `test_missing_detail_file_falls_back_to_title` — a step whose `step.detail` path is absent/unreadable still has its title scanned and contributes no body text (no crash).
- `test_feature_title_suppression_flagged` — a feature titled "silence the lint check" emits a `step_id is None` finding.
- `test_schema_footprint_enriches_rationale` — a matching step whose `files` include `plan_tool/schema.py` mentions the flag/field co-signal in the body (still emits exactly one finding).
- `test_severity_is_lowest_advisory` — emitted severity is `"info"` and `is_apply_eligible(rec) is False`.

`class TestDetectSelfReferentialFeatures`:
- `test_inert_without_config` — no `.plan-tool/config.json` → `[]` even when a feature footprint clearly overlaps plan-tool paths.
- `test_inert_without_features` — config set but `plan.features == []` → `[]`.
- `test_overlapping_feature_flagged` — config lists `plan_tool/review.py`; a feature whose step `files` include `plan_tool/review.py` emits one `source="self-referential"` finding naming the overlap.
- `test_directory_config_matches_files_under_it` — config entry `plan_tool/cli` matches a footprint `plan_tool/cli/completeness_cmd.py` (ancestor overlap).
- `test_non_overlapping_feature_not_flagged` — a feature footprint disjoint from the configured set emits `[]`.
- `test_uses_all_files_not_just_files` — a path in a step's `creates:` (not `files:`) still counts toward the footprint.

`class TestCollectSmellFindings`:
- `test_concatenates_both_detectors` — a plan that trips both yields both sources.
- `test_empty_plan_returns_empty` — no smells → `[]`.

### `tests/test_project_config.py` (new cases, mirror the `branch_prefixes` block)

- `test_validation_machinery_default_empty` — no config → `validation_machinery_paths(tmp_path) == []`.
- `test_validation_machinery_project_over_user` — project value wins over user.
- `test_validation_machinery_user_when_no_project` — user value used when project absent.
- `test_validation_machinery_bad_list_warns_and_empties` — a non-list / list-with-empty-string warns to stderr (asserted via `capsys`) and returns `[]`.
- `test_validation_machinery_malformed_json_swallowed` — broken project JSON falls through to user/default, never raises.
- `test_validation_machinery_no_env_axis` — no env key affects this accessor (there is no env axis for it).

### Test-creation order (feature step)

This is a **feature** step. Author every test above **in the same change** as the `review.py` / `project_config.py` edits — write the failing test, implement the detector/accessor, watch it pass. Behaviors covered: verb→gate-object + subject-attribution precision (first-person trip vs quantified/meta non-trip, pinned with **both** title and detail-body fixtures), bare-step operation, feature-title scanning, detail-body scanning (incl. the title-anodyne `type_impure` shape, the detail-body self-description non-trip, and the missing-detail fallback), config resolution/validation/inertness, the overlap predicate (exact + ancestor), `all_files` footprint, and the public collector. **Green-before-done gate:** every new case must pass (`uv run pytest -m "not integration" tests/test_review.py tests/test_project_config.py -q`) and the pre-existing `tests/test_review.py` / `tests/test_project_config.py` suites must stay green before this step is considered finished.

## Acceptance criteria

- `plan_tool/project_config.py` exposes `validation_machinery_paths(repo_root) -> list[str]`: returns `[]` with no config, resolves project-over-user, and warns-then-returns-`[]` on a present-but-invalid list (never raises).
- `detect_suppression_shape` flags a step whose title **or** detail-body (`## Summary`/`## Why`) is a **first-person** verb→gate-object suppression intent attributed to the plan unit itself ("this step downgrades the mixed-step finding"); it catches the motivating `type_impure` shape whose anodyne title hides a suppressing rationale in its detail-body (a title-only check would not), does **not** flag a suppression-handler/detector title, a bare keyword without a gate-object, **nor a detail-body that merely *describes* a suppressing unit with a quantified/meta subject** (e.g. this plan's own step-2 Summary "flags a step … whose purpose is to suppress …") — both the title and detail-body non-trip cases are pinned by fixtures — works on a plan with no `features:` block, and emits `source="suppression-shape"` at `severity="info"`.
- `detect_self_referential_features` returns `[]` when the machinery set is unconfigured **and** when `plan.features` is empty; flags a feature whose `step.all_files` footprint overlaps the configured set (exact or ancestor), emitting `source="self-referential"` naming the overlap.
- `collect_smell_findings` returns the concatenation of both detectors.
- Neither new source is in `APPLY_ELIGIBLE_SOURCES`; `is_apply_eligible(rec) is False` for both, and `triage_reason` returns the generic structural-diagnostic text (no special-case added).
- `collect_deterministic_findings` is unchanged (the smell findings reach no flow until steps 3/4).
- No new import cycle: `project_config.py` stays stdlib-only; `review.py`'s reference to `project_config.validation_machinery_paths` adds no cycle (`project_config` imports nothing from `review`).
- All new test classes pass; existing `tests/test_review.py` and `tests/test_project_config.py` suites stay green.

## References

- [Validators — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — confirms `Plan._validate_features` (step 1) guarantees `feature.steps` resolve, so this detector can treat a missing id as benign defensiveness.
- [Models — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/models/) — the `Feature` / `Plan.features` shape (step 1) this step consumes; pin field names (`Feature.id`/`.title`/`.steps`, `Plan.features`) to step 1's detail until it lands at HEAD.
- [Python `re` — Regular expression operations](https://docs.python.org/3/library/re.html) — for the verb→gate-object proximity regex (`re.compile`, `re.IGNORECASE`, bounded `{0,n}` gaps).
- [`pathlib.PurePosixPath`](https://docs.python.org/3/library/pathlib.html#pathlib.PurePosixPath) — `==` and `relative_to` semantics underpinning the footprint-overlap predicate.

## Deferred

- **Surfacing the findings** — wiring `collect_smell_findings` into the completeness deterministic layer + JSON (step 3: `plan_tool/cli/completeness_phases.py` / `plan_tool/cli/completeness_cmd.py` / `plan_tool/completeness_report.py`) and into `validate` (step 4: `plan_tool/cli/inspect.py`). Step 2 ships only the detectors + seam.
- **Consolidating `_read_level` + `_read_smell_block`** into one `_read_block(path, block_name)` and rewiring `branch_awareness_enabled`/`branch_prefixes` onto it — a behavior-preserving refactor outside this feature's scope; route to reconcile.
- **Unfalsifiable-feature check** — deferred plan-wide (needs an acceptance-criteria→feature `[feature-id]` tagging convention that does not exist); recorded in the plan's Deferred section.
- **Custom `triage_reason` text for smell sources** — the generic structural-diagnostic message is serviceable; a smell-specific "split/cut/extract the feature" message is a cosmetic follow-up.
