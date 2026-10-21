> **Auto-archived**: this plan was swept on 2026-06-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Advisory feature-ref validation + suppression-shape and self-referential smell detectors in `review.py`, plus a `validation_machinery_paths` config accessor in `project_config.py`, surfaced via a new `collect_smell_findings` collector

## Summary

- Adds the **advisory semantic layer** for the feature registry that step 1 declares as types-only. `plan_tool/review.py` gains `validate_feature_refs(plan)` (unique + kebab registry ids, every `step.features` id points to a registry id) and two no-Claude smell detectors — `detect_suppression_shape` (a step/feature whose own deliverable suppresses an existing audit gate) and `detect_self_referential_features` (a feature whose file set overlaps the tool's own audit machinery).
- All three return `list[Recommendation]` with `severity="info"` and sources (`feature-ref`, `suppression-shape`, `self-referential`) deliberately **kept out of** `APPLY_ELIGIBLE_SOURCES`, so they never reach `apply_finding` and never flip the exit code.
- A new public collector `collect_smell_findings(plan, repo_root, *, plan_name)` fans the three out. It is **not** wired into `collect_deterministic_findings` — steps 3 and 4 own where it surfaces (completeness post-loop report, `validate`).
- `plan_tool/project_config.py` gains `validation_machinery_paths(repo_root)` (resolves project → user, **no env axis**, warn-then-`[]` on a bad list), so `detect_self_referential_features` reads its comparison set from `.plan-tool/config.json` and is **inert when unconfigured** — the tool never hardcodes its own paths.
- On green: a plan with a duplicate/non-kebab feature id, a dangling `step.features` tag, a step that suppresses a gate, or a self-referential feature each yields one advisory finding; a clean plan (and any plan with no `features:` block, except the bare-step suppression case) yields none.

## Table of Contents

- [Why](#why) — what the advisory layer adds and why it sits above parse, not in it.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source files and their tests.
- [Implementation](#implementation) — the four detectors, the collector, and the config accessor.
- [Tests](#tests) — the new `tests/test_review.py` / `tests/test_project_config.py` cases.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — pydantic validator docs relevant to the advisory-not-parse-fatal choice.
- [Deferred](#deferred) — the unfalsifiable-feature check, surfacing, and a config-reader refactor.

## Why

Plans have no cheap, author-time check that catches the two known-brittle shapes the predecessor finding surfaced: a step whose purpose is to **silence an existing quality gate** (`type_impure` was literally "suppress the mixed-step finding"), and a feature that **modifies the very machinery the audit runs through**. Step 1 added the `features` registry and `step.features` tags as types only — no semantics — so `run`/`jira`/`detail` stay inert on a typo in metadata they ignore. This step adds the advisory layer those types were waiting for: a single `validate_feature_refs` for id hygiene plus two deterministic smell detectors, all emitting dismissible `info` findings and none affecting the exit code. Keeping every semantic check here (not in a `@model_validator`) is the whole point — a drifted feature block must never brick a command that doesn't read it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add `validate_feature_refs`, `detect_suppression_shape`, `detect_self_referential_features`, the `_SUPPRESSION_INTENT_RE` / `_SUPPRESSION_REASONING_RE` module constants, a `_FEATURE_ID_RE` kebab predicate, the `collect_smell_findings` collector, and a small helper to pull `## Summary` / `## Why` text from a step's detail file. Do **not** touch `collect_deterministic_findings` or `APPLY_ELIGIBLE_SOURCES`.
  - `plan_tool/project_config.py` — add `SMELL_CONFIG_BLOCK` / `VALIDATION_MACHINERY_PATHS_KEY` constants, a `_read_smell_block` reader (parallel to `_read_level`), an `_is_valid_path_list` validator, and the public `validation_machinery_paths(repo_root)` accessor.
  - `tests/test_review.py` — add `TestValidateFeatureRefs`, `TestSuppressionShape`, `TestSelfReferentialFeatures`, `TestCollectSmellFindings`.
  - `tests/test_project_config.py` — add `TestValidationMachineryPaths`.

This step depends on step 1 (`plan_tool/schema.py` must already expose `Feature`, `Plan.features: list[Feature]`, and `Step.features: list[str]`). If step 1 is not yet landed when this is implemented, land it first — every detector here reads those fields.

## Implementation

### `plan_tool/review.py`

Mirror `check_test_strategy_alignment` for shape — it is the sole existing template for a deterministic, advisory, no-Claude finding emitter: returns `list[Recommendation]`, `severity` is advisory, ids minted via `_make_rec_id` (which folds the source into the id), and its source is absent from `APPLY_ELIGIBLE_SOURCES` so `is_apply_eligible` returns `False` and `triage_reason` falls through to the generic "structural diagnostic" text with **no special-case branch needed**.

- **`validate_feature_refs(plan: Plan) -> list[Recommendation]`** — the advisory id-hygiene check.
  - Return `[]` only when `plan.features` is empty **and** no step carries a `step.features` tag (legacy plans declare neither). A plan that tags steps but declares no registry must **not** early-return — every tag dangles, and the dangling-tag check below is exactly what should flag the most common authoring mistake (tag a step, forget the registry).
  - Emit one `info` finding per violation, `source="feature-ref"`:
    - **duplicate registry id** — same `id` appears twice in `plan.features`.
    - **non-kebab id** — registry `id` fails `_FEATURE_ID_RE` (anchored `^[a-z0-9]+(-[a-z0-9]+)*$`). Write the predicate locally; do **not** reuse `plan_tool/locator.py:slug_from_filename` (a slug *producer*, not a *validator*, and importing `locator` into `review` is the wrong direction).
    - **dangling tag** — a `step.features` id that matches no registry `id`. Name the step id and the unresolved tag.
  - `step_id=None` for registry-level findings (duplicate/non-kebab); `step_id=<step>` for a dangling tag. Mint ids with `_make_rec_id(step_id, "feature-ref", fingerprint)` where the fingerprint encodes the specific violated value so two distinct violations get distinct ids.
  - **Never raises** — this is the advisory mirror of the parse-time validator the plan deliberately did not write.

- **`detect_suppression_shape(plan: Plan, repo_root: Path, *, plan_name: str, max_bytes: int = _MAX_DETAIL_PARSE_BYTES) -> list[Recommendation]`** — the suppression/escape-hatch detector.
  - **Scan the step title AND the step's detail-body** `## Summary` / `## Why` sections — the motivating `type_impure` stated its suppressing purpose in its rationale, not its anodyne title, so a title-only check has near-zero recall. Read the detail file the same way `check_test_strategy_alignment` does, but **short-circuit to title-only when `step.detail is None`** before composing any path — a freshly `create`d, not-yet-detailed plan carries `step.detail = None`, and `repo_root / None` raises `TypeError` before `is_file()` runs, so guarding only on `is_file()` would crash `validate` (step 4) on exactly the undetailed-plan case. Mirror `_filter_symbols_by_detail`'s `if step.detail is None: return` guard explicitly, then `repo_root / step.detail`, guard `is_file()`, `read_text(..., errors="replace")[:max_bytes]`. Factor the section-extraction into one small helper (`_summary_and_why_text(body) -> str`) used by tests too.
  - **Trip predicate** = `_SUPPRESSION_INTENT_RE`: a suppression **verb** (`suppress|downgrade|bypass|exempt|silence|disable`) governing a gate-**object** noun (`gate|check|finding|severity|audit`) within a short window (`{0,30}` chars). This is the verb→gate-object intent match, **not** a bare keyword — precision over recall matters most here, because the plan authoring this feature is itself in the scanned corpus.
  - **Non-trip guard** = `_SUPPRESSION_REASONING_RE`: suppress the finding when the suppression phrase is governed by **either** of two non-perform signals — (a) a *class-of-units* reference (`any step that…`, `a step that…`, `the detector that…`, `steps that suppress…`), reasoning over other units rather than declaring its own deliverable; **or** (b) a *detect/flag* verb (`detect|flag|catch|identify|surface|find`) governing the suppression phrase within a short window, marking a deliverable whose action is to *detect/flag* suppression rather than *perform* it — e.g. step 2's own `## Summary` "detect_suppression_shape (a step/feature whose own deliverable suppresses an existing audit gate)". The separating signal is "the suppressor is the unit's own concrete *suppressing* deliverable" vs "a class of other units the prose reasons over **or** a deliverable whose action is to detect/flag suppression."
  - **Pin both anchors in the docstring**: a trip example (`"downgrade the mixed-step finding"`) and the two non-trip families — a class-of-units reference ("any step that suppresses a gate") and a detect/flag deliverable (this step's own `## Summary` "detect_suppression_shape (… whose own deliverable suppresses an existing audit gate)").
  - Works on a **bare step with no `features:` block** — the one check useful before any feature is declared. Do not gate it on `plan.features` being non-empty.
  - `source="suppression-shape"`, `severity="info"`, `step_id=<step>`.

- **`detect_self_referential_features(plan: Plan, repo_root: Path, *, plan_name: str) -> list[Recommendation]`** — the audit-machinery-overlap detector.
  - **Read the comparison set from config**: `machinery = project_config.validation_machinery_paths(repo_root)`. **Return `[]` immediately when it is empty** — inert-when-unconfigured is the safe default and keeps a general-purpose tool from coupling to its own source tree. Never hardcode `plan_tool/review.py` etc. as the machinery set.
  - **Feature file set** = union of `step.all_files` (`files` + `creates`) over the steps whose `step.features` tag includes that feature id (ownership runs step → feature).
  - Emit one `info` finding per feature whose file set overlaps `machinery` (compare normalized `PurePosixPath` strings). Name the feature id, its title, and the overlapping path(s).
  - `source="self-referential"`, `severity="info"`, `step_id=None` (feature-level).
  - Requires the feature layer — returns `[]` when `plan.features` is empty.

- **`collect_smell_findings(plan: Plan, repo_root: Path, *, plan_name: str) -> list[Recommendation]`** — the new public collector.
  - Calls and concatenates `validate_feature_refs(plan)`, `detect_suppression_shape(...)`, and `detect_self_referential_features(...)`.
  - **Do NOT add this to `collect_deterministic_findings`.** That function is the broadcast fan-out wired into the `--iterate` convergence apply loop (`create`/`detail`/`launcher`/completeness `_collect_det_findings → apply_finding`); appending there would route advisory smells into `apply_finding`, a prose editor that cannot fix a brittle structural shape. This collector is exposed for steps 3 and 4 to wire into their narrower, report-only surfaces.

- **`_SUPPRESSION_INTENT_RE` / `_SUPPRESSION_REASONING_RE` / `_FEATURE_ID_RE`** — module-level compiled constants near the other `review.py` pattern constants. Keep the regexes single-sourced here.

### `plan_tool/project_config.py`

Add a new resolution accessor following the established composition (constants + fail-soft reader + list validator + public accessor). Mirror `branch_prefixes`, **not** `branch_awareness_enabled`:

- **Constants:** `SMELL_CONFIG_BLOCK = "smell_checks"` and `VALIDATION_MACHINERY_PATHS_KEY = "validation_machinery_paths"`.
- **`_read_smell_block(path: Path) -> Optional[dict]`** — a parallel of `_read_level` keyed on `SMELL_CONFIG_BLOCK` instead of `branch_awareness`. Write a second small reader; do **not** generalize `_read_level` into a shared `_read_block(path, name)` inline — that is a behavior-preserving refactor that would perturb the byte-pinned branch-awareness path. Route the consolidation to `## Deferred`.
- **`_is_valid_path_list(raw: object) -> bool`** — non-empty `list` of non-empty `str`. Do **not** reuse `_is_valid_branch_prefix` — it applies git-ref validation that wrongly rejects file paths.
- **`validation_machinery_paths(repo_root: Path) -> list[str]`** — resolves **project → user, no env axis** (the set is repo-structural, not an operator toggle, so it gets no `PLAN_TOOL_*` env override). Takes the first level whose `smell_checks.validation_machinery_paths` is present and valid; on a present-but-invalid list, warn once to stderr naming the offending file and return `[]`; **default `[]` when unconfigured** (not a `DEFAULT_*` constant — empty means "no check").

## Tests

### Test-creation order (feature step)

This is a feature step — write each test alongside the code it covers. **Green-before-done gate: every new test below must pass before this step is finished.** Run `uv run pytest -m "not integration" tests/test_review.py tests/test_project_config.py -q` during dev.

`tests/test_review.py` — build plans from inline plan-text constants fed through `parse_plan`/`parse_plan_text` (mirror the existing `_REVIEW_PLAN` fixtures); write step detail files into `tmp_path` for the suppression body cases.

- `TestValidateFeatureRefs`
  - `test_clean_registry_no_findings` — unique kebab ids + resolving tags → `[]`.
  - `test_no_features_block_no_findings` — empty `plan.features` → `[]`.
  - `test_duplicate_registry_id_flagged` — two same ids → one `feature-ref` finding, `step_id=None`.
  - `test_non_kebab_id_flagged` — `Feature_One` / `featureOne` → one finding.
  - `test_dangling_tag_flagged` — a `step.features` id absent from the registry → one finding naming the step.
  - `test_never_raises_on_malformed` — a plan with all three violations returns findings, never raises.
- `TestSuppressionShape`
  - `test_title_states_suppression_trips` — title "Bypass the purity gate" → one `suppression-shape` finding.
  - `test_body_states_suppression_trips` — anodyne title, `## Why` says "downgrade the mixed-step finding" → one finding (proves body is scanned).
  - `test_self_describing_detector_does_not_trip` — a suppression-*detector* step whose own `## Summary` uses own-deliverable wording that trips `_SUPPRESSION_INTENT_RE` ("detect_suppression_shape (a step/feature whose own deliverable suppresses an existing audit gate)") → `[]` (proves the detect/flag-vs-perform guard, not just class-of-units phrasing).
  - `test_class_of_units_reasoning_does_not_trip` — "any step that suppresses an audit gate" → `[]`.
  - `test_bare_step_no_features_block_still_checked` — suppression on a step with no `features:` → one finding.
  - `test_real_detail_bundle_self_flags_nothing` — the suppression self-flag regression: parse this plan's own on-disk file and run the landed `collect_smell_findings` over its real detail bundle (steps 2/3/4, whose bodies describe suppression-detection in own-deliverable terms); assert **zero** `suppression-shape` findings. Binds the shipped detector to the actual prose, so a regex-balance regression that self-flags the plan fails the suite (not a synthetic `tmp_path` fixture). **This is an intentionally-live corpus, not a frozen snapshot.** Two consequences the test must own deliberately so a reword/rename can't quietly invert the guarantee: (a) resolve the plan **by title** (`Plan.title == "Feature Health Declaration And Smell Checks"`, via the manifest/locator), **not** the renumber-prone plan-number path `docs/implementation-plans/2-…md`, so an archive/renumber `skip`s rather than silently passing on a missing file — `pytest.skip` if no plan resolves by that title; (b) the step-2/3/4 prose is allowed to move under an `apply_finding` reword (including a pass this audit triggers), so the assertion is **zero suppression-shape findings over whatever the current prose is**, never a hash/substring match against pinned wording — the guarantee is "the shipped detector self-flags none of its own live suppression-describing prose," and the synthetic `TestSuppressionShape` cases above (which *are* frozen) carry the regex trip/non-trip contract so a paraphrase here can't mask a genuine regression.
- `TestSelfReferentialFeatures`
  - `test_inert_when_unconfigured` — no `validation_machinery_paths` config → `[]` even with an overlapping file set.
  - `test_overlap_flagged` — config lists `plan_tool/review.py`; a feature file set includes it → one `self-referential` finding.
  - `test_no_overlap_no_findings` — configured set disjoint from the file set → `[]`.
- `TestCollectSmellFindings`
  - `test_aggregates_all_three` — a plan tripping all three detectors → findings from each source present.
  - `test_sources_not_apply_eligible` — every returned `rec.source` is **not** in `APPLY_ELIGIBLE_SOURCES` (guards the no-auto-apply guarantee).

`tests/test_project_config.py` — `TestValidationMachineryPaths` (resolve against `tmp_path` + pinned temp `$HOME`, assert warnings via `capsys`, mirror `test_prefixes_*`):

- `test_unconfigured_returns_empty` — no config → `[]`.
- `test_project_over_user` — both set → project wins.
- `test_user_when_no_project` — only user set → user value.
- `test_no_env_axis` — `PLAN_TOOL_*` env set has no effect (the set has no env override).
- `test_bad_list_warns_and_returns_empty` — non-list / empty / non-str element → warns to stderr naming the file, returns `[]`.
- `test_malformed_json_swallowed` — broken project JSON falls through to user (or `[]`), never raises.

## Acceptance criteria

- `validate_feature_refs(plan)` returns `[]` for an empty registry, and one `info`/`source="feature-ref"` finding each for a duplicate id, a non-kebab id, and a dangling `step.features` tag; it never raises.
- `parse_plan` on a semantically malformed feature block still returns a valid `Plan` (no `ValidationError`) — the semantic checks live only here.
- `detect_suppression_shape` flags a step whose **own deliverable** suppresses an existing gate (intent stated in title **or** `## Summary`/`## Why`), keys on a verb→gate-object match (not a bare keyword), does **not** trip on a step that describes/implements suppression handling or reasons over a class of units, and works on a bare step with no `features:` block.
- `detect_self_referential_features` returns `[]` when `validation_machinery_paths(repo_root)` is empty, and one `info`/`source="self-referential"` finding when a feature's file set overlaps the configured set.
- `validation_machinery_paths(repo_root)` resolves project → user with no env axis, warns once and returns `[]` on a bad list, and defaults to `[]` when unconfigured.
- Every source emitted by `collect_smell_findings` is absent from `APPLY_ELIGIBLE_SOURCES`; `collect_deterministic_findings` is byte-unchanged.
- `uv run pytest -m "not integration" tests/test_review.py tests/test_project_config.py -q` is green.

## References

- [Validators (model_validator / field_validator) — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Confirms `@model_validator(mode="after")` vs. plain-function semantics, central to keeping `validate_feature_refs` advisory rather than a parse-time validator that would raise.
- [Models — Pydantic Docs](https://docs.pydantic.dev/latest/concepts/models/) — Reference for the `Feature` / `Plan.features` / `Step.features` shapes this step reads from step 1.

## Deferred

- **Unfalsifiable-feature check** — a feature with no acceptance criterion bound to it. Needs a `[feature-id]` acceptance-bullet tagging convention that does not exist (criteria are free prose today). Defer to a follow-up; do not block parts A/B on standing it up.
- **Surfacing `collect_smell_findings`** — wiring it into the completeness post-loop report and `plan-tool validate` is steps 3 and 4. This step only exposes the collector.
- **Consolidating `_read_level` and `_read_smell_block`** into one `_read_block(path, name)` — a behavior-preserving refactor that would touch the byte-pinned branch-awareness path; route to `reconcile`.
- **`validate_feature_refs` invocation from `create`/`detail` write-back** — the plan lists author-time write-back as a future caller; this step defines the function and surfaces it only through `collect_smell_findings`.
