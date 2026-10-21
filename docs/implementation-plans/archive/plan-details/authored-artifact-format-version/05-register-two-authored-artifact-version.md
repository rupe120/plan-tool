> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Register the plan and detail format-version constants in `data_contract.py` and document their evolution rules in `DATA_CONTRACT.md`

## Summary

`plan_tool/data_contract.py` gains a new, deliberately narrow registry shape — `ArtifactFormatVersionContract` — that names each authored class's version constant and its supported-versions companion, reading their live values directly from `plan_tool/schema.py` (step 1) and `plan_tool/detail_artifacts.py` (step 3) rather than copying numbers by hand. `DATA_CONTRACT.md` gains a new section documenting, per class, the version constant, its current value, and four rules the plan's Architecture already settled: the class-specific break rule, writer eligibility, the support window, and retirement. The doc's top-of-file Scope paragraph is narrowed to say it now covers this version axis while `PLAN_FORMAT.md` and `DETAIL_FORMAT.md` keep owning the artifacts' actual structure. `tests/test_data_contract.py` gains tests that fail when the registry's recorded value stops matching the live constant, when either doc section stops naming its constants or its current value, or when any of the four rules disappears from the text. The new registry type carries no dataclass fields, JSON keys, or body-schema checks — it names constants and policy, nothing about what a plan or detail file's content must look like.

## Table of Contents

- [Why](#why) — the doc gap this step closes and why it needs a new registry shape instead of the existing two
- [Input](#input) — the step 1 and step 3 constants this step reads, and how to treat their proposed names
- [Files (creates vs edits)](#files-creates-vs-edits) — the three declared files and the edits in each
- [Implementation](#implementation) — the new contract type, the registry function, and the doc changes
- [Tests](#tests) — the test cases this step adds
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — the plan-level docs this step's design follows
- [Applicable guardrails](#applicable-guardrails) — which plan-level fences bind this step
- [Deferred](#deferred) — what this step deliberately leaves for later steps or a future backlog entry

## Why

Steps 1 and 3 give the plan and run-grade detail classes a format-version constant, a supported-versions set, and a fail-closed reader each — but nothing in `plan_tool/data_contract.py` knows either constant exists, and `DATA_CONTRACT.md`'s own Scope paragraph explicitly excludes them ("It does **not** re-document the *authored-artifact* formats — `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and `JIRA_FORMAT.md` own those"). Every other durable schema in this codebase — `SavedReview`, `Grounding`, `ProjectProfile`, the purity cache — has a code-owned registry entry and a `DATA_CONTRACT.md` section that a test keeps in sync (`test_schema_constants_are_documented_from_registry` and its siblings). The two new version constants have neither, so a future rename, value bump, or rule change to either class can drift away from the doc with nothing to catch it.

The existing two registry shapes do not fit. `PersistedDataclassContract` discovers its fields from `dataclasses.fields(cls)`, and `Plan`/`Step` are `pydantic.BaseModel` subclasses, not `dataclasses.dataclass` — nothing to discover. `JsonObjectContract` documents a JSON file's keys, and a detail body is markdown with no JSON shape while a plan's `format_version` is one YAML key among many the doc deliberately doesn't re-document. Treating either class as a persisted dataclass or JSON object would mean either fabricating fields `Plan.model_fields` doesn't structure the way `dc.fields()` expects, or quietly taking over `PLAN_FORMAT.md`/`DETAIL_FORMAT.md`'s job of describing the artifacts' actual shape — both of which the plan's Architecture explicitly rules out: "It does not make `Plan` a dataclass, describe markdown as JSON, or take ownership of either format schema." A new, narrower shape that names only the version constant, its supported set, and the class's evolution rules is what lets this stay additive.

## Input

This step's registry entries name constants that steps 1 and 3 define, not ones that exist yet in this codebase — as of this writing neither `plan_tool/schema.py` nor `plan_tool/detail_artifacts.py` has landed `format_version`, `PLAN_FORMAT_VERSION`, `DETAIL_FORMAT_VERSION`, or their supported-versions companions; both live only in steps 1 and 3's own detail files as proposals. The plan's `depends_on: [1, 3]` on this step means those two steps run first, so by the time this step's code is written the constants exist in the module. What this step reads from each:

- **Step 1** (`plan_tool/schema.py`, with the raw-input injection in `plan_tool/parser.py`) — a `PLAN_FORMAT_VERSION` int constant and a `SUPPORTED_PLAN_FORMAT_VERSIONS` set/frozenset constant, plus `Plan.format_version` as a field defaulting to `PLAN_FORMAT_VERSION`. A raw absent key is nevertheless injected as effective legacy version `1` before model validation, so a later model default cannot relabel legacy raw input as current.
- **Step 3** (`plan_tool/detail_artifacts.py`) — a `DETAIL_FORMAT_VERSION` int constant and a `SUPPORTED_DETAIL_FORMAT_VERSIONS` set/frozenset constant.

Per this repo's own rule for a later step documenting names an earlier step mints: read the names off the landed modules when implementing, not off steps 1/3's detail-file prose — if either lands under a different spelling than proposed there, the landed name wins and this step's registry entry uses it.

This step does not read `Plan.model_validate`, `parse_plan_text`, the plan reader's `UnsupportedPlanFormatVersionError`, or the detail reader's `DetailFormatError` and `require_supported_detail_format_version` — those are steps 1/3's reader mechanics, out of this step's declared files, and this step's registry has no reader-verification role (see Applicable guardrails).

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/data_contract.py` — add the `ArtifactFormatVersionContract` dataclass and the `artifact_format_version_contracts()` function; add the two new module-level imports it needs; extend the module docstring by one clause naming the new registry kind.
- `DATA_CONTRACT.md` — narrow the top-of-file Scope paragraph; add a new section documenting both classes' version constants and rules; extend the top banner's one-line drift-guard description by one clause.
- `tests/test_data_contract.py` — add the test cases listed below.

## Implementation

**The new contract type is deliberately smaller than its two siblings.** Add a frozen dataclass next to `PersistedDataclassContract` and `JsonObjectContract`:

```python
@dataclass(frozen=True)
class ArtifactFormatVersionContract:
    owner: str
    section_title: str
    source_symbol: str
    version_constant: str
    supported_versions_constant: str
    current_version: int
    supported_versions: frozenset[int]
```

Unlike `PersistedDataclassContract`, this carries no `cls`, no `field_names`, no `json_key_aliases` — there is no dataclass or JSON shape to discover, only a name and a value pair per class. `owner` and `section_title` follow the existing convention of matching exactly (every current `JsonObjectContract` entry already does this — e.g. `owner="Plan manifest"`, `section_title="Plan manifest"`); `source_symbol` follows the established `path:Symbol` shape (e.g. `plan_tool/concept_tree.py:ConceptTree`).

**Read the live values, don't copy them.** Import the two owning modules at the top of `data_contract.py` (`from plan_tool import schema` and `from plan_tool import detail_artifacts`, alongside the existing `from plan_tool import ...` block) and build the registry by reading their constants directly:

```python
def artifact_format_version_contracts() -> tuple[ArtifactFormatVersionContract, ...]:
    return (
        ArtifactFormatVersionContract(
            owner="Plan format version",
            section_title="Plan format version",
            source_symbol="plan_tool/schema.py:PLAN_FORMAT_VERSION",
            version_constant="PLAN_FORMAT_VERSION",
            supported_versions_constant="SUPPORTED_PLAN_FORMAT_VERSIONS",
            current_version=schema.PLAN_FORMAT_VERSION,
            supported_versions=frozenset(schema.SUPPORTED_PLAN_FORMAT_VERSIONS),
        ),
        ArtifactFormatVersionContract(
            owner="Detail format version",
            section_title="Detail format version",
            source_symbol="plan_tool/detail_artifacts.py:DETAIL_FORMAT_VERSION",
            version_constant="DETAIL_FORMAT_VERSION",
            supported_versions_constant="SUPPORTED_DETAIL_FORMAT_VERSIONS",
            current_version=detail_artifacts.DETAIL_FORMAT_VERSION,
            supported_versions=frozenset(detail_artifacts.SUPPORTED_DETAIL_FORMAT_VERSIONS),
        ),
    )
```

This is what makes the drift guard genuine rather than cosmetic: `current_version` is read off the real constant every time the registry is built, so if a later change bumps `PLAN_FORMAT_VERSION` without updating `DATA_CONTRACT.md`'s stated number, the doc test (below) fails on its own — nobody has to remember to keep two copies of the number in sync. Check both modules' exact constant names before wiring this in, per the Input section above; wrap the supported-versions value in `frozenset(...)` even if steps 1/3 already typed it that way — cheap, and every other frozen field in this module is a frozenset for the same hashability reason.

There is no cycle risk in adding these two imports: `plan_tool/schema.py` has no first-party imports at all (pydantic + stdlib only), and `plan_tool/detail_artifacts.py` imports only `plan_tool.locator` and `plan_tool.schema` — neither imports `data_contract.py`, so a plain top-level `from plan_tool import schema` / `from plan_tool import detail_artifacts` needs none of `review.py`'s existing lazy-import workaround (`review.py` imports `data_contract` from inside two functions specifically because `data_contract.py` already imports `review` at module level — an unrelated existing cycle-avoidance this step doesn't touch).

**Don't wire this into `registry_fingerprint()` or `intentional_exclusions()`.** Both existing functions only ever iterate `persisted_dataclass_contracts()` and `json_object_contracts()`; leave them that way. `registry_fingerprint()`'s hash currently exists to invalidate `data-contract-apply`'s saved payloads when a *drift-detectable* registry entry changes, and nothing detects drift against `artifact_format_version_contracts()` yet (see Deferred) — folding it into the fingerprint now would just add spurious invalidations for a consumer that doesn't exist. `intentional_exclusions()` only makes sense for a contract with excludable fields; this one has none.

**`DATA_CONTRACT.md`: narrow the Scope paragraph.** It currently reads, in part: "It does **not** re-document the *authored-artifact* formats — `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and `JIRA_FORMAT.md` own those." Reword this to say the version axis is now in scope while the three format docs keep owning structure — one way to phrase it: "...plus the authored-artifact format-version constants and their evolution policy below. It does **not** re-document the *authored-artifact* content schemas — `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and `JIRA_FORMAT.md` retain ownership of field and section shape...". `JIRA_FORMAT.md` stays purely a schema owner here — this plan adds no jira-grade version constant.

**`DATA_CONTRACT.md`: add a new section next to "Version-evolution policy".** The plan's Architecture says this content belongs "alongside its existing transition and fail-closed rules," so place a new `## Authored-artifact format versions` section directly after `## Version-evolution policy` (ahead of "Authored plan concept ownership"). Give it a short intro sentence, then one `###` subsection per class — `### Plan format version (`plan_tool/schema.py`)` and `### Detail format version (`plan_tool/detail_artifacts.py`)` — each naming:

- the version constant and the supported-versions constant, by name, and the current value (so the doc test below can pin a live number, not a hand-typed one);
- where the declaration lives in the artifact (the plan's `format_version` frontmatter key; the detail body's fixed post-H1 marker comment) and a one-line pointer to the format doc that owns that placement — `PLAN_FORMAT.md` / `DETAIL_FORMAT.md` — rather than restating it;
- the **class-specific break rule** — for the plan, any new frontmatter key is a break because `Plan`/`Step` are `extra="forbid"`, so a writer bumps the version before ever emitting one; for detail, an optional section the established readers already ignore is additive and does not bump the version, while a carrier move or another reader-visible structural change does;
- **writer eligibility** — a plan writer (`write_plan`/`render_plan_text`) stamps the current declaration only when the plan's effective version is already current, and refuses to serialize an effective older plan (including a raw absent legacy plan, once a later version ships) until its explicit raw upgrade runs; version 1 exposes that upgrader as a library API only. The detail writer has no comparable refusal because `plan_tool/detail.py` always authors a fresh current-format body rather than rewriting an existing older one in place. The first release that makes either class's previously supported live on-disk artifact reach a reader or writer refusal ships an operator-invocable route for the affected class and a shared compatibility preflight before every affected mutating command's first state change in the same change;
- **support window** — a reader accepts the current version and current-minus-one for both classes; absent counts as legacy version 1 for a live plan or live run-grade detail. A detail with a valid H1 but no marker is raw-upgradable; a carrier-less detail is readable only while that legacy version remains supported and reaches current by forced re-authoring, not an H1-inventing transform. An archived detail bundle is a historical snapshot outside this window: its archive breadcrumb intentionally precedes the H1, and it carries no live reader or upgrade obligation;
- **retirement** — a version retires only by a dated, user-approved record, once every remaining live absent-or-older artifact has an explicit upgrade or archival path, before version N+2 ships.

Word these as the settled rules from the plan's Architecture section (`## Architecture`, the "Version evolution is class-specific" and surrounding paragraphs) — this step's job is registering and documenting them, not deciding them fresh. Keep the wording plain and match the surrounding doc's voice; the exact sentences are yours to write.

**Extend, don't rewrite, the top banner and module docstring.** `DATA_CONTRACT.md`'s opening banner already says a drift guard "fails when a registered persisted shape, sidecar key, durable config key, or schema constant drifts from this doc" — add "or authored-artifact format-version constant" to that list. `plan_tool/data_contract.py`'s module docstring already says the registry names "the set of classes, aliases, sidecar JSON objects, and durable config files" for drift checks — add a clause naming the version-only entries too, so the docstring stays an accurate index of what the file registers.

## Tests

For any invariant named above — the live-binding requirement, the version-only carve-out, the Scope narrowing — the test name states which one it pins, not just which function it calls.

### Tests for this step

- `test_artifact_format_version_contracts_registered` — `artifact_format_version_contracts()` returns exactly the two expected owners, `"Plan format version"` and `"Detail format version"`.
- `test_plan_format_version_binds_live_constant` — the plan entry's `current_version`/`supported_versions` equal `schema.PLAN_FORMAT_VERSION`/`schema.SUPPORTED_PLAN_FORMAT_VERSIONS` read directly from the module, so a miswired literal in the registry (not read from the constant) goes red.
- `test_detail_format_version_binds_live_constant` — same, for `detail_artifacts.DETAIL_FORMAT_VERSION`/`SUPPORTED_DETAIL_FORMAT_VERSIONS`.
- `test_artifact_format_version_contract_is_version_only` — the dataclass's field set is exactly the version-axis fields (no `cls`, `field_names`, `json_key_aliases`, or any other schema-shape field), pinning the deliberate carve-out that this record never grows into a third schema-describing contract type.
- `test_plan_format_version_documented_with_live_value` — the `DATA_CONTRACT.md` "Plan format version" section names both `` `PLAN_FORMAT_VERSION` `` and `` `SUPPORTED_PLAN_FORMAT_VERSIONS` `` and states the live current-version number read off the registry (not a number hand-typed into the test), so a future version bump with no doc update fails this test on its own.
- `test_detail_format_version_documented_with_live_value` — same, for the "Detail format version" section and its two constants.
- `test_plan_format_version_class_rules_documented` — the section names all four rules for the plan class: the `extra="forbid"`-driven break rule, the writer-eligibility refusal for an effective-older plan, the current/current-minus-one support window, and the dated user-approved retirement rule; it also states the same-release operator-route and before-first-mutation compatibility-preflight obligations for the first refusal of a previously supported live representation.
- `test_detail_format_version_class_rules_documented` — same four rules stated for the detail class, including that an ignored optional section does not bump the version while a carrier move does, that a carrier-less detail follows forced re-authoring rather than the raw upgrader, and that an archived breadcrumb-prepended bundle is outside the live run-grade support window and upgrade obligation.
- `test_data_contract_scope_names_authored_artifact_versions` — the Scope paragraph (the text before the first `##` heading) now names the format-version axis as covered, while still naming `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and `JIRA_FORMAT.md` as the schema owners.
- `test_artifact_format_version_owners_do_not_collide_with_existing_registries` — neither `"Plan format version"` nor `"Detail format version"` already appears as an owner in `persisted_dataclass_contracts()` or `json_object_contracts()`.

Green-before-done: every test above, plus the full existing `tests/test_data_contract.py` suite (all tests already reading `persisted_dataclass_contracts()`, `json_object_contracts()`, `registry_fingerprint()`, and `intentional_exclusions()` must stay green unmodified, since this step's registry function is additive and none of those existing tests iterate it).

## Acceptance criteria

- `plan_tool/data_contract.py` defines `ArtifactFormatVersionContract` (a frozen dataclass carrying only owner, doc-section name, code anchor, the two constant names, and the live current version and supported-versions set — no dataclass-field or JSON-key machinery) and `artifact_format_version_contracts()` returning exactly two entries.
- Both entries' `current_version` and `supported_versions` are read directly from `plan_tool/schema.py` and `plan_tool/detail_artifacts.py` at call time, not copied as literals into `data_contract.py`.
- `DATA_CONTRACT.md` has a new section documenting, per class, the version constant, the supported-versions constant, the live current value, and the class-specific break rule, writer eligibility, support window, and retirement rule from the plan's Architecture; the detail section distinguishes raw-upgradable and carrier-less live details from archived breadcrumb-prepended snapshots.
- `DATA_CONTRACT.md`'s Scope paragraph names the authored-artifact format-version axis as covered, while `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and `JIRA_FORMAT.md` remain named as the schema owners.
- `tests/test_data_contract.py` fails if the registry's recorded current version stops matching the live constant, if either doc section stops naming its two constants, if the doc's stated current-version number stops matching the live value, if any of the four rules or either first-legacy-refusal obligation (operator route and before-first-mutation compatibility preflight) disappears from a section, or if the Scope paragraph stops naming the version axis.
- Neither `registry_fingerprint()` nor `intentional_exclusions()` iterates the new registry function; both continue passing their existing tests unchanged.
- The full pre-existing `tests/test_data_contract.py` suite, `tests/test_review_persistence.py`, `tests/cli/test_completeness_cmd.py`, and `tests/cli/test_data_contract_cmd.py` all stay green with no edits to those three test files.

## References

- `BACKLOG.md` #356 — the source entry whose scope contract this plan inherits; its "Verification" bullet is what asks for a code-owned registry plus a `DATA_CONTRACT.md` drift guard for these two constants.
- `DATA_CONTRACT.md` § "Version-evolution policy" — the existing fail-closed reader rule this step's new section sits alongside, and § Scope, the paragraph this step narrows.
- `PLAN_FORMAT.md` § "Validation rules" — rule 8 (`extra="forbid"`), the reason the plan class's break rule is "any new key, even optional."
- `DETAIL_FORMAT.md` § Format — the pure-markdown, no-frontmatter contract that makes the detail carrier a body marker rather than a schema field, and the reason the detail class's break rule differs from the plan's.
- `plan_tool/data_contract.py` — the existing `PersistedDataclassContract`/`JsonObjectContract` shapes this step's new type deliberately does not reuse, and the module this step edits.

## Applicable guardrails

- **Plan intent** ("A plan file and a run-grade detail file each declare their format version in-band, and each reader refuses an unsupported declared version...") — this step documents and registers that contract; it does not add any new reader behavior, so nothing here may change how a plan or detail file is parsed or refused.
- **Step intent** ("...without pretending that either artifact has a persisted dataclass or JSON-object schema... A later constant change, class rule, support window, writer eligibility, or retirement rule cannot drift away from the doc silently") — bounds the whole Implementation section above: the new registry type stays version-only, and the tests exist specifically to make each of those four rule categories, plus the constants themselves, fail loudly on drift.
- **Scope guardrails** ("The check asserts exactly one binary observable: the artifact's declared format-version value is one this build supports... Checking whether an artifact's *content* conforms to the version it declares" is not allowed) — this step's registry and tests never open, parse, or judge an actual plan or detail file's bytes; they only read code constants and check `DATA_CONTRACT.md`'s text. Nothing added here performs or triggers a content-conformance check.
- **Out of scope** (no version 2 of any artifact; no migration engine; no change to `extra="forbid"`, `PURITY_VERDICT_LOGIC_VERSION`, or `audit_input_revision`'s `version`; no versioning of `BACKLOG.md`, `plan-seeds/`, or jira exports) — this step touches none of those; it registers exactly the two version-1 constants steps 1 and 3 define.

## Deferred

- Wiring `artifact_format_version_contracts()` into `plan_tool/cli/completeness_phases.py`'s `_collect_data_contract_drift` (the live completeness-audit finder that today loops over `persisted_dataclass_contracts()`/`json_object_contracts()` and turns a stale doc into a `source="data-contract"` recommendation) — `completeness_phases.py` is not in this step's declared files. A future step or backlog entry can add a third `source_type` branch there once an audit-time drift finding (rather than only a test failure) is wanted for this registry.
- Adding the new registry to `registry_fingerprint()`'s hashed payload — deferred until something actually detects drift against it (the item above); adding it now would only add spurious cache invalidation to `data-contract-apply`'s freshness check for a consumer that doesn't exist yet.
- Making `check_input_contract_references`'s registered-owner grammar (the `SavedReview.field`-style backtick references a plan/detail `## Input` section can cite) recognize `"Plan format version"`/`"Detail format version"` as citable owners — not needed: a bare code anchor like `` `plan_tool/schema.py:PLAN_FORMAT_VERSION` `` already resolves through the existing generic module-level-symbol check (`_code_anchor_resolves` → `_module_level_symbol_exists`), since both constants are plain top-level assignments.
- The raw-artifact upgrade entry point and its coverage test over the absent-plus-supported states — step 6's work, once it lands it may add its own field(s) to `DATA_CONTRACT.md`'s new section (or its own registry field) naming the upgrade entry point; that decision belongs to step 6.
- Removing `BACKLOG.md` #356 and updating `CLAUDE.md`'s format-doc bullets — step 7, which runs after every other step ships.
