> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Give each artifact class an explicit raw-artifact upgrade entry point, and a coverage test over plan absence or detail valid-carrier absence plus every supported version

## Summary

`plan_tool/parser.py` and `plan_tool/detail_artifacts.py` each gain one public upgrade entry point — a pure function that takes a **raw** artifact (an unparsed frontmatter mapping, or a detail body's text), decides which state it is in, and returns the raw counterpart declaring the current format version. The key design decision is that each entry point asks its own class's existing reader gate first and then dispatches on the **raw** state (`None` for no declaration, otherwise the declared integer), never on a reader's defaulted effective version — that is what keeps absent-to-1 a real change instead of an identity, and it makes the upgrader and the reader agree about which declared values are acceptable by construction. `DATA_CONTRACT.md`'s authored-artifact version section (step 5's home) gains the upgrade obligation as a fifth per-class rule. The obligation itself is held by a coverage test per class in `tests/test_parser.py` and `tests/test_detail_artifacts.py`: it walks `{absent} ∪ supported` for plans and `{absent with valid carrier} ∪ supported` for details, runs the entry point on a raw artifact built in each state, and goes red when a version is added to the supported set with no path behind it. Version 1 exposes these library entry points only; the first release that makes a previously supported on-disk plan or detail representation reach a reader or writer refusal must ship an operator-invocable route for the affected class in the same bump. On green, every upgradable state reaches current; a raw detail body with no valid carrier H1 refuses rather than gaining an invented H1 and follows step 4's forced re-authoring route instead.

## Table of Contents

- [Why](#why) — what "always upgradable" means today, and why prose cannot hold it
- [Input](#input) — the step 1–5 contracts this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the six declared files and the edits in each
- [Implementation](#implementation) — the two entry points, the raw-state rule, the fallback raise, and the doc edit
- [Tests](#tests) — the cases this step adds, by file, including the mutation that proves the coverage test bites
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — the plan-level docs and in-repo precedents this step follows
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step
- [Deferred](#deferred) — what this step deliberately leaves out

## Why

Steps 1–4 ship two readers that refuse a version they do not support, and two writers that stamp the current one. Nothing yet carries an artifact that is *behind* to current. Today that gap costs nothing — the supported set is `{1}` and the only pre-declaration state is `absent` — which is exactly why it has to be closed now: the moment version 2 ships, "we will always provide an upgrade path" is a sentence in a document that nothing checks, and the version that skips its path is the one nobody notices. The plan's Risks section names this directly: the obligation "degrades into prose if nothing fails when a version is added without a path."

So this step's real deliverable is a **failing test on a future change**, and the entry points exist to give that test something real to walk. Version 1 is what makes the test honest rather than always-true: `absent → 1` genuinely inserts a declaration that was not there, so the coverage walk proves a transition instead of proving that a no-op returns its input.

The second thing this step settles is where the version is read from. A reader normalizes — step 1's gate treats a missing `format_version` as effective legacy version 1, and step 3's gate treats a marker-free body the same way. An upgrader that read the artifact through a reader would see an already-current value while version 1 is current for every legacy artifact and quietly become an identity function, passing every test anyone thought to write. Reading the raw state is the whole mechanism.

## Input

This step consumes five sibling contracts. Read the landed code for the exact spellings — where a name below disagrees with what is on disk, the landed name wins.

- **Step 1** ships the plan class's version constants (in `plan_tool/schema.py`), the named refusal `UnsupportedPlanFormatVersionError`, and the private gate in `plan_tool/parser.py` that refuses an unsupported or non-integer declared value. This step's plan entry point calls that gate rather than re-deriving its accepted-state set or its message.
- **Step 2** ships the plan writer's stamp and its writer-eligibility refusal. This step supplies the library upgrade entry point that a future version's operator route will invoke; version 1 adds no command surface and adds no writer behavior of its own.
- **Step 3** ships `plan_tool/detail_artifacts.py`'s detail constants, `DetailFormatError`, the marker renderer, the reader gate, and `locate_detail_format_carrier` for the fixed post-H1 carrier slot. This step's detail entry point reuses all of them.
  - **One shape dependency worth checking first:** the coverage test needs to render a marker for an arbitrary version, so step 3's marker renderer must accept a version argument. If it landed without one, add the parameter with the current version as its default here — an additive, keyword-defaulted change inside a file this step already edits — rather than spelling a second marker string in the test.
- **Step 4** ships the detail writer and the parser rule that guarantees an authored body starts with a real H1. This step does not touch the writer; it only relies on the fact that a body written by this build already carries the current marker, so upgrading one is a no-op.
- **Step 5** ships `DATA_CONTRACT.md`'s `## Authored-artifact format versions` section and its two per-class subsections carrying four rules each. This step adds a fifth rule to each subsection. Step 5's rule-presence tests check that its four rules are named, not that exactly four exist, so the addition leaves them green with no edit.

**What this step cannot verify:** that a *future* version's transform is correct. The coverage test proves a path is declared and that it produces a current-declaring artifact from the state it claims to handle. Whether a hypothetical version-2 transform preserves the right content is that version's problem, checked by that version's own tests.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/parser.py` — add the plan class's upgrade entry point and its absent-state transform; no change to `parse_plan_text`, `write_plan`, `render_plan_text`, `_split_frontmatter`, or the compare-and-swap guard.
- `plan_tool/detail_artifacts.py` — add the detail class's upgrade entry point and its absent-state transform; extend the module docstring by one clause (the module now owns an upgrade entry point as well as paths and the reader gate); widen `DetailFormatError`'s docstring by one clause to cover the missing-H1 refusal. Add the version parameter to step 3's marker renderer only if step 3 landed it without one.
- `DATA_CONTRACT.md` — add the upgrade-obligation rule to each of step 5's two per-class subsections under `## Authored-artifact format versions`.
- `tests/test_parser.py` — new test class for the plan entry point and its coverage walk.
- `tests/test_detail_artifacts.py` — new test class for the detail entry point and its coverage walk.
- `tests/test_duplication.py` — if the separately owned detail stamp and raw upgrader cross the exact-duplicate threshold, add their narrowly named `ALLOWED_DUPLICATE_GROUPS` entry and its reason here; otherwise leave its source unchanged and let its existing test prove no entry is needed.

## Implementation

### 1. What both entry points must do

Each class gets one public function. Names are the implementer's; directional names that say the input class and the direction read best — one way is `upgrade_plan_frontmatter_to_current(raw)` in `plan_tool/parser.py` and `upgrade_detail_body_to_current(text)` in `plan_tool/detail_artifacts.py`. The properties are not the implementer's:

- **Take the raw artifact, return the raw counterpart.** The plan side takes the mapping `yaml.safe_load` produced and returns a mapping; the detail side takes the body text and returns text. No file I/O, no `Plan` model, no path argument. Reading and writing files belongs to callers that do not exist yet.
- **Ask the class's existing reader gate first, then dispatch.** Call step 1's private plan gate / step 3's `require_supported_detail_format_version` at the top. An unsupported or malformed declaration then refuses through the class's already-shipped named error, with the already-shipped message shape. This is the constraint that matters most: the upgrader and the reader can never disagree about which declared values are acceptable, because there is only one place that decides.
- **Dispatch on the raw state, never on an effective version.** The state is `None` when the artifact carries no declaration at all, and the declared integer otherwise. On the plan side that is `raw.get("format_version")` with no default. On the detail side it is what step 3's slot locator reports for the fixed post-H1 slot. Do not route the state read through anything that substitutes the current version for a missing declaration — that substitution is a reader behavior, and inheriting it turns absent-to-1 into a no-op.
- **Be pure.** Return a new artifact; leave the caller's input untouched. On the plan side a shallow copy is enough, because the transform only adds one top-level key and never reaches into `steps` or any other nested value — say so rather than reaching for `deepcopy`.
- **Carry content forward; invent nothing.** The plan transform adds `format_version` and changes no other key. The detail transform inserts one line and leaves every other byte, including line endings and the trailing newline, exactly as it found them. `str.splitlines(keepends=True)` is the repo's idiom for this and keeps CRLF bodies intact.
- **Handle exactly one hop.** Each state maps straight to current. Do not build a chain that walks 1 → 2 → 3; the plan's "## Out of scope" rules out a migration engine, and the first version that genuinely needs two hops can add chaining then.

**Rejected alternative: a dispatch table of `state → callable`.** It reads well and makes the enumeration directly assertable, but with two states it is a registry standing in for an `if`. Explicit branches plus the fallback below (§3) go red on an unpathed state just as reliably, and are the smaller thing. Escalate to a table only if chaining arrives.

**Deliberate non-check:** neither entry point re-validates that its input is the right *type* (a mapping, a string). `parse_plan_text` already rejects non-mapping frontmatter, and the annotation states the contract. Adding a second guard would duplicate a check that is not this step's to own.

### 2. The plan side, in `plan_tool/parser.py`

- The absent transform returns a copy of the mapping carrying `format_version` set to the current version constant. Putting the new key first — `{"format_version": PLAN_FORMAT_VERSION, **raw}` — matches the key position step 2's writer produces, so an upgraded mapping and a written one render the same way. Position has no parsing effect; this is for a human reading the file.
- The already-current state returns the mapping unchanged (a copy is fine and keeps the return contract uniform).
- No new import is expected: step 1 already brings the constants and the named error into this module. Confirm before adding one.
- `parse_plan_text`, `parse_plan`, `write_plan`, `render_plan_text`, and `refresh_plan_provenance` are not edited. Reading must not upgrade, and the writers author current artifacts directly.

### 3. The fallback raise, and why it is what the coverage test bites

After the branches, raise on any state that reached the function with no path. A `NotImplementedError` naming the state and saying what to add reads correctly — the state is one the *reader* supports, so this is not an unsupported-version refusal, it is a missing implementation. The message should say plainly: no upgrade path is declared for this format version; add one before adding the version to the supported set.

This line is unreachable at version 1, which is precisely why it needs a test that reaches it by mutation (see [Tests](#tests)). An unreachable guard that nobody has ever seen fire is not evidence of anything.

### 4. The detail side, in `plan_tool/detail_artifacts.py`

- **Refuse a body with no valid carrier H1, and say so by name.** The plan's acceptance criterion is explicit: the upgrader refuses rather than synthesizing a carrier slot. Leading blank lines before an unindented H1 are valid; a nonblank preamble, an indented H1, or no H1 is not. This is a carrier-less representation, not a member of the detail raw-upgrade enumeration: the transform cannot carry content forward without inventing an H1. Raise `DetailFormatError` with a message saying the body has no valid carrier H1 and therefore no place for the declaration, and widen that class's docstring by one clause so it covers this second reason. Its declared path to current is step 4's `detail --step N --force --recover-refused --commit --no-completeness` re-authoring route. A new exception type is the rejected alternative — nothing distinguishes the two cases for any caller, and `plan_tool/cli/app.py`'s typed handler (step 3) already covers `DetailFormatError` if this ever reaches a command.
- **The refusal condition is exactly "`locate_detail_format_carrier` reports no valid carrier H1."** The named step-3 locator skips leading blank lines, requires the document's first nonblank line to be an unindented H1 matching the shared recognizer, and returns the position after it even when no later nonblank line exists. Do not write a second rule about what has to follow the H1. Reusing that delivered helper is what keeps the upgrader's idea of "where the carrier goes" identical to the reader's idea of "where the carrier is."
- **One implementation of the slot locator, not two.** Call step 3's delivered `locate_detail_format_carrier`; do not extract, rename, or duplicate it here. A second slot scanner is the exact drift this plan exists to prevent.
- **An H1 with nothing after it still upgrades.** The marker is inserted directly after the H1 line. Step 3's reader calls that shape an absent declaration; the upgrader adds the line rather than refusing, because refusing would mean the upgrader rejects a body the reader accepts. The refusal is about a missing valid carrier H1, nothing else.
- **Marker-shaped prose outside the slot is prose.** The transform locates the slot and stops. It never scans the body for markers, so a marker-shaped line inside `## Implementation` or a fenced block survives byte-for-byte and is not read as a declaration.
- **The module stays a leaf.** Everything here uses the module's existing stdlib imports and step 3's own constants. No first-party import is added, and `tests/test_detail_artifacts.py::TestLeafAndReexports::test_leaf_does_not_import_detail` stays green unmodified.

### 5. `DATA_CONTRACT.md`

Add one rule to each of step 5's two per-class subsections under `## Authored-artifact format versions`, beside the break rule, writer eligibility, support window, and retirement rule already there. Each states:

- the class's upgrade entry point by symbol and module, and that it takes the raw artifact rather than a parsed one;
- that the enumerated plan states are absent plus every supported version, while the detail states are absent-with-valid-carrier plus every supported version, and that each has a raw path to current before the version joins the supported set; a carrier-less detail takes the separately documented forced re-authoring path;
- that the coverage test in the class's test file is what enforces this, so a version added without a path fails the suite;
- that reading never upgrades — the path is reached only by explicit invocation; version 1 exposes the entry point as a library API only, and the first release making a previously supported live on-disk artifact reach a reader or writer refusal ships an operator-invocable route for the affected class in the same change;
- that retirement removes a version from the supported set and therefore from this obligation, which is how a version can leave without ever gaining a transform.

Keep it plain and match the surrounding voice. This step adds no test to `tests/test_data_contract.py` — that file is not in scope, and the obligation's mechanism is the coverage test, not the prose.

### 6. Constraints and gotchas

- **Version-1 library surface only.** Neither entry point is called from `plan_tool/` outside its own definition in version 1, so the tests are the only callers. The first release that makes a previously supported live on-disk artifact reach a reader or writer refusal must add an operator-invocable route for the affected class in that same version bump; it must not leave the refusal as a library-only dead end.
- **No package re-export.** `plan_tool/__init__.py` is not in scope; the tests import from the owning modules.
- **`plan_tool/roadmap_source_identity.py`'s `format_version` and `BASELINE_FORMAT_VERSION` are a different concept** — the semantic-projection version used for baseline identity — and the roadmap staged artifacts are carved out to `BACKLOG.md` #362. Do not touch either, and do not fold them into this step's enumeration.
- **`EVIDENCE_SCHEMA_VERSIONS` in the same roadmap module is a useful read, not a site to change.** It is the one place in the repo that already exercised the retirement branch of `DATA_CONTRACT.md`'s version-evolution policy (version 1 retired rather than upgraded), which is why the obligation is phrased as "a declared path for every *supported* state."

## Tests

Every case below must be green before this step is finished. Each name states the invariant it pins, so a later reader can tell a deliberate refusal from a bug without re-deriving the reasoning.

### Tests for this step

`tests/test_parser.py` — new class alongside step 1's `TestFormatVersion`, styled like the existing `TestRiskProfile` and `TestRoundTrip`:

- `test_absent_declaration_upgrades_to_the_current_version` — a raw mapping with no `format_version` key comes back declaring the current version; the real transition version 1 exists to prove.
- `test_upgrade_reads_the_raw_state_not_a_readers_defaulted_version` — the absent case is fed as a raw mapping (never a parsed `Plan`, whose field already defaults to current) and the result differs from the input; states why the transition cannot be an identity.
- `test_upgrade_preserves_every_other_frontmatter_key_unchanged` — title, status, priority, and the full `steps` list come back equal; pins "carries content forward, invents nothing."
- `test_upgrade_does_not_mutate_the_caller_mapping` — the input mapping still has no `format_version` after the call; pins purity.
- `test_current_declaration_upgrades_to_an_equal_mapping` — a mapping already declaring the current version comes back equal.
- `test_upgrade_refuses_an_unsupported_declared_version_by_name` — an unsupported integer raises `UnsupportedPlanFormatVersionError` naming the declared value and the supported set.
- `test_upgrade_refuses_a_malformed_declaration_rather_than_treating_it_as_absent` — parametrized over a quoted string, a boolean, a float, and explicit `null`; each refuses instead of falling back to the absent path.
- `test_upgrade_refuses_exactly_what_the_reader_gate_refuses` — for each of those malformed and unsupported inputs, both the reader gate and the entry point raise; pins the "one place decides" invariant rather than letting the two drift.
- `test_upgraded_mapping_still_validates_as_a_plan` — the returned mapping passes `Plan.model_validate`; the output is a usable plan mapping, not just a dict with an extra key.
- `test_every_plan_state_has_a_declared_upgrade_path_to_current` — the coverage test: walk `{None} ∪ SUPPORTED_PLAN_FORMAT_VERSIONS`, build a raw mapping in each state, run the entry point, assert the result declares the current version.
- `test_adding_a_supported_plan_version_without_a_path_fails_closed` — the mutation that proves the coverage test bites: patch the supported-versions binding **that `plan_tool/parser.py` actually reads** (a `from ... import` binds a name in `parser`, so patching `schema` alone would do nothing) to include an extra version, then assert the entry point raises the unhandled-state error for it. Without this case the fallback raise ships untested and the whole obligation rests on an unexercised line.

`tests/test_detail_artifacts.py` — new class alongside `TestSharedResolver` and `TestLeafAndReexports`:

- `test_marker_free_body_gains_the_current_marker_after_its_h1` — the first non-blank line after the H1 is the current marker.
- `test_upgrade_changes_only_the_inserted_line` — every other line, the line endings, and the trailing newline are unchanged; pins "carries content forward, invents nothing."
- `test_body_already_declaring_the_current_version_is_returned_unchanged`.
- `test_upgrade_refuses_a_body_with_no_valid_carrier_h1_rather_than_synthesizing_one` — a body starting at `## Summary` raises `DetailFormatError` naming the missing carrier H1; the deliberate refusal the plan calls for, so a later reader does not "fix" it into a synthesized H1. Step 4's recovery test owns the distinct proof that this carrier-less shape is re-authored to current.
- `test_upgrade_accepts_leading_blank_lines_before_the_carrier_h1` — blank lines before an H1 do not become a preamble; the marker lands after that H1.
- `test_h1_with_no_following_content_gains_the_marker` — the decided edge: a missing H1 is the only refusal condition, so a bare H1 upgrades rather than refusing.
- `test_upgrade_refuses_an_unsupported_marker_by_name` — a marker declaring an unsupported version raises `DetailFormatError` naming the declared value and the supported set.
- `test_upgrade_refuses_a_malformed_marker_rather_than_treating_it_as_absent` — a non-integer payload in the slot refuses instead of taking the absent path.
- `test_upgrade_refuses_exactly_what_the_reader_gate_refuses` — the detail-side twin of the plan case above.
- `test_marker_shaped_prose_outside_the_slot_stays_prose_and_is_not_a_declaration` — a marker-shaped line inside `## Implementation` survives byte-for-byte while the body still upgrades as absent.
- `test_upgraded_body_passes_the_reader_gate` — feed the result to `require_supported_detail_format_version`; it returns without raising, closing the loop between the two halves.
- `test_every_detail_upgradable_state_has_a_declared_upgrade_path_to_current` — the coverage test: walk `{None} ∪ SUPPORTED_DETAIL_FORMAT_VERSIONS` using a valid H1-bearing body in each state (and step 3's marker renderer for declared ones), run the entry point, and assert the result declares the current version. The carrier-less shape is deliberately outside this raw-transform walk and follows step 4's tested re-authoring route.
- `test_adding_a_supported_detail_version_without_a_path_fails_closed` — patch the supported-versions constant in `plan_tool/detail_artifacts.py` to include an extra version and assert the unhandled-state error fires.

`tests/test_duplication.py`:

- `test_no_exact_duplicate_functions` remains the guard. If the new raw upgrader and step 4's writer stamp have identical bodies at the four-line threshold, add only their `ALLOWED_DUPLICATE_GROUPS` entry with the stated reason that the writer must not call the upgrader; do not merge the two paths. If they do not collide, make no source change and retain the green control.

**Unchanged and must stay green with no edits:** step 3's reader-gate cases in this file, `TestLeafAndReexports::test_leaf_does_not_import_detail`, and step 5's four-rule doc assertions in `tests/test_data_contract.py`.

## Acceptance criteria

- `plan_tool/parser.py` exposes one public function that takes a raw plan frontmatter mapping and returns a mapping declaring the current plan format version.
- `plan_tool/detail_artifacts.py` exposes one public function that takes a raw run-grade detail body and returns a body whose first non-blank line after the H1 is the current marker.
- Both functions leave their input untouched and change nothing outside the declaration: every other plan key, and every other detail line including line endings and the trailing newline, comes back unchanged.
- Both functions refuse an unsupported or malformed declared value through their class's existing named error, with the same message the reader gate produces — proven by a test that feeds the same inputs to both and asserts both raise.
- The detail function refuses a carrier-less body with `DetailFormatError` and returns no body; it never adds an H1. That representation reaches current only through step 4's tested `--recover-refused` re-authoring route.
- Both functions dispatch on the raw declared state, so the absent case produces a changed artifact rather than returning its input.
- A plan test walks its absent state plus every supported version, while a detail test walks its valid-carrier absent state plus every supported version; each runs the entry point on a raw artifact and asserts the result declares the current version. Step 4 separately proves carrier-less detail re-authoring.
- For each class, a test that adds a version to the supported binding the code reads, without a matching path, fails — proven by asserting the unhandled-state error rather than by inspection.
- No production code calls either entry point: `rg -n "<plan entry point>|<detail entry point>" plan_tool/` returns only the two definitions.
- `plan_tool/detail_artifacts.py` gains no first-party import, and its existing leaf-discipline test passes unmodified.
- `DATA_CONTRACT.md`'s two per-class subsections each name their class's upgrade entry point, the enumerated raw states, the coverage test as the enforcing mechanism, that reading never upgrades, and that retirement removes a version from the obligation; the detail section distinguishes the carrier-less re-authoring route from the raw upgrader.
- Step 5's rule-presence tests in `tests/test_data_contract.py` and step 3's reader-gate tests stay green with no edits. `tests/test_duplication.py` either stays unchanged or receives only the narrowly named, separately-owned stamp/upgrader allowlist entry when its guard proves one is needed.

## References

- `DATA_CONTRACT.md` § "Version-evolution policy" — the fail-closed reader rule and the three transition paths this step's obligation implements for the authored-artifact layer; read it for why a retired version leaves the obligation rather than needing a transform.
- `PLAN_FORMAT.md` § "Validation rules" — rule 8, the unknown-field rejection that makes the plan carrier a frontmatter key and the plan class's break rule stricter than the detail class's.
- `DETAIL_FORMAT.md` § Format — the pure-markdown, no-frontmatter contract that makes the detail carrier a body marker, and the reason the upgrader has to find an H1 before it has anywhere to write.
- `plan_tool/roadmap_source_identity.py` — `EVIDENCE_SCHEMA_VERSIONS` (a supported set whose version 1 was retired rather than upgraded) and `BASELINE_FORMAT_VERSION` / `CanonicalSourceIdentity.format_version` (an unrelated concept in a carved-out subsystem). Read the first as precedent; leave both alone.
- `BACKLOG.md` #356 — the source entry whose scope contract this plan inherits, and whose "always upgradable" requirement this step discharges.

## Applicable guardrails

- **The plan's "## Scope guardrails", upgrade-obligation observable** — this step's binary observable is that every enumerated state has a declared path, held by a coverage test. It must not grow into a check of whether an upgraded artifact's content matches the version it now declares.
- **The plan's "## Scope guardrails", not-allowed list, "upgrading at read time"** — nothing this step adds may be called from a parse, a reader gate, or a writer. The entry points are reached only by explicit invocation.
- **The plan's "## Out of scope", migration engine and version 2** — this step ships one hop per state and no chaining, no version-2 conversion, and no version-1 CLI verb. The first release making refusal of a previously supported live representation reachable from disk must provide its operator route without becoming a migration engine.
- **The plan's "## Out of scope", roadmap staged artifacts** — this step must not enumerate, upgrade, or touch the roadmap artifact class or its version-adjacent constants; that work is `BACKLOG.md` #362's.
- **The plan's "## Architecture", "A transform carries existing content forward but never invents missing content"** — the detail refusal on a missing H1 and the plan transform's single-key change are both instances of this fence, not local preferences.

## Deferred

- **A version-1 `plan-tool` upgrade verb, or any command surface for either entry point** — this step ships the library entry points and the obligation only. The first release that makes a previously supported live on-disk artifact reach a reader or writer refusal must ship an operator-invocable route for the affected class in the same change.
- **A concrete v1-to-v2 transform and multi-hop chaining** — there is no version 2 to convert to. The coverage test is what will force the transform to exist when there is.
- **Naming the upgrade entry points in `PLAN_FORMAT.md` and `DETAIL_FORMAT.md`** — those documents belong to steps 2 and 4; `DATA_CONTRACT.md` § "Authored-artifact format versions" is this step's documentation home.
- **A drift test in `tests/test_data_contract.py` for the new doc rule** — that file is not in this step's scope, and the obligation is held by the coverage test rather than by the prose. Route a doc-presence assertion for the upgrade rule to `BACKLOG.md` if it is later wanted.
- **A preservation check for an artifact whose declaration a direct model edit removed** — the plan's "## Out of scope" accepts that as residual risk. A later plan write re-stamps incidentally, while an undeclared detail persists until deliberate re-authoring.
- **Upgrade paths for the roadmap staged artifacts, draft seeds, plan seeds, and jira exports** — carved out by the plan; the roadmap half is tracked at `BACKLOG.md` #362.
