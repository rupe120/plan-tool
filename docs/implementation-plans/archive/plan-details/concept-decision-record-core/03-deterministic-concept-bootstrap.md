> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add deterministic concept bootstrap and conflict-aware re-derivation

## Summary

This step adds `plan_tool/concept_bootstrap.py`, which deterministically derives concept records from the shared plan-section representation delivered by step 2. It uses the concept model and integrity contract from step 1, preserves stable source-derived identities, and reports conflicts when re-derivation would overwrite reviewed or independently edited state. Small supporting changes in `plan_tool/parser.py` and `plan_tool/schema.py` expose the shared section and validation rules needed by bootstrap and the later synchronizer. On green, identical plan input always produces the same concept tree, safe source-only changes can be re-derived, and divergent human changes remain untouched behind an explicit conflict result.

## Table of Contents

- [Summary](#summary) — Overview of the deterministic bootstrap and conflict contract.
- [Why](#why) — Why plan prose cannot safely serve as the concept decision record.
- [Input](#input) — Contracts consumed from steps 1 and 2.
- [Files (creates vs edits)](#files-creates-vs-edits) — New modules and supporting edits.
- [Implementation](#implementation) — Required identity, derivation, and conflict rules.
- [Tests](#tests) — Unit coverage for stable bootstrap and safe re-derivation.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary UUID and hashing specifications.
- [Deferred](#deferred) — Reconciliation and persistence work owned by later steps.

## Why

`plan_tool/parser.py:parse_plan()` currently returns frontmatter state while concept decisions remain embedded in mutable Markdown. Without a deterministic bridge from the shared body-section parser to the persisted concept model, repeated runs can mint different identities, and a later source change can overwrite review decisions without showing that both sides changed. This step establishes that bridge now because concept review in step 4 and synchronization in step 5 both need one source-to-concept rule and one conflict predicate.

## Input

- **Step 1 concept record:** Consume the landed public models from `plan_tool/concept_tree.py`, including their stable identity, source-link, decision-content, review-state, and source-baseline fields. Construct those models through their public contract; do not create a second concept record or persistence format in `plan_tool/concept_bootstrap.py`.
- **Step 1 integrity contract:** Preserve the plan fingerprint and other integrity metadata required by the step 1 record. Bootstrap may populate the record, but persistence remains owned by the step 1 writer.
- **Step 2 parsed sections:** Consume the public body-section representation moved into `plan_tool/parser.py` from `plan_tool/review.py:split_body_sections()`. Preserve its heading normalization, section boundaries, source order, and handling of empty or missing sections instead of parsing Markdown again.
- **Plan schema:** Use `plan_tool/schema.py:Plan` and `plan_tool/schema.py:Step` only for validated frontmatter facts needed by derivation. Do not add new plan-frontmatter fields in this step.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/concept_bootstrap.py` — Own deterministic bootstrap, source-derived identity, safe re-derivation, and typed conflict results.
  - `tests/test_concept_bootstrap.py` — Cover deterministic output, identity boundaries, preservation rules, and conflict cases.

- **Existing files (edits only):**
  - `plan_tool/parser.py` — Expose any small public section/source helpers that bootstrap and the later synchronizer need beyond the step 2 parser output. Keep `_split_frontmatter()` and `write_plan()` behavior unchanged.
  - `plan_tool/schema.py` — Add only shared validation or canonical vocabulary required by both bootstrap and later concept synchronization. Do not add persisted plan fields or duplicate the concept model owned by step 1.

## Implementation

The foundational logic is a deterministic source-to-concept derivation with a three-way conflict check: compare the prior derived baseline, the current concept record, and a fresh derivation before deciding whether an update is safe.

- **Keep derivation pure.** Add a public bootstrap operation in `plan_tool/concept_bootstrap.py` that accepts an already validated `plan_tool/schema.py:Plan`, the parsed body sections from step 2, and the step 1 integrity inputs. It should return the step 1 concept-tree type and must not read or write the sidecar itself.

- **Use one parsed-section authority.** Call the public parser surface introduced by step 2 rather than copying the regular expressions from `plan_tool/review.py:split_body_sections()`. If bootstrap needs source metadata that the shared result does not expose, extend that result in `plan_tool/parser.py` narrowly so step 5 can consume the same representation.

- **Make ordering deterministic.** Derive nodes in parsed source order and use explicit, stable ordering for any child or collection whose source has no meaningful order. Never depend on set iteration, dictionary construction from unordered input, filesystem traversal order, timestamps, or random UUID generation.

- **Derive IDs from position identity.** Use a fixed UUID namespace and `uuid.uuid5()` over a canonical source key built from the node’s source section and stable parent path. Include the concept’s source identity, but exclude mutable fields such as review state, decision text, rationale, display order, sign-off data, and fingerprints. This keeps an ID stable when only annotations or review decisions change while still separating the same label under different parents.

- **Centralize canonicalization.** Keep source-key normalization in one named helper in `plan_tool/concept_bootstrap.py`. Normalize only distinctions the parser contract declares insignificant; do not broadly case-fold or rewrite punctuation if that could merge distinct plan concepts. The same canonicalization must be used by initial bootstrap and re-derivation.

- **Seed safe defaults.** Populate review and decision fields with the default values defined by the step 1 concept model. Do not infer operator approval, sign-off, or reviewed decisions from prose. Bootstrap represents derived source state, not a completed review.

- **Return a typed re-derivation outcome.** A public re-derivation operation should return either an updated tree with no conflicts or a result containing explicit conflict records. Each conflict should identify the stable concept/source key and retain enough prior, current, and newly derived values for later CLI reporting without requiring another derivation pass.

- **Use three-way comparison.** Treat the stored source baseline from step 1 as the common ancestor:
  - When the fresh derivation matches the baseline, preserve the current concept unchanged.
  - When only the source-derived side changed, update the derived fields while preserving stable identity and compatible review metadata.
  - When only the current record changed, preserve that record.
  - When both changed to the same value, accept the shared value.
  - When both changed differently, return a conflict and leave the current record unchanged.

- **Protect reviewed state.** Any update that would discard or reinterpret a reviewed decision must become a conflict unless the three-way comparison proves that the reviewed value itself is unchanged. Do not choose plan prose or the current record as an automatic winner.

- **Handle additions and removals explicitly.** New source concepts may be added with deterministic default state. A source removal must become a conflict when the matching current concept has reviewed or independently changed state; safe removal is allowed only when the current node still matches its derived baseline. Preserve unaffected siblings and their order.

- **Keep conflicts all-or-nothing.** The recommended public contract returns the complete candidate plus all conflicts, but callers must not treat a conflicted candidate as publishable. At minimum, the current tree passed to re-derivation must remain unmodified when any conflict is reported.

- **Preserve schema boundaries.** `plan_tool/schema.py:Plan._validate_graph()` and `plan_tool/schema.py:Step._scope_status_coherent()` remain plan-frontmatter rules. Concept validation belongs to the step 1 model or narrow shared source vocabulary; do not mix concept review state into `Plan` or `Step`.

- **Avoid a second writer.** Do not call the step 1 save function inside bootstrap or re-derivation. Steps 5 and 6 will coordinate persistence and Markdown updates through their canonical synchronization and command boundaries.

## Tests

- `test_bootstrap_is_deterministic` — repeated bootstrap from the same validated plan and parsed sections produces equal trees and equal IDs.
- `test_bootstrap_preserves_parser_section_order` — node order follows the shared `plan_tool/parser.py` section representation.
- `test_ids_ignore_mutable_review_fields` — review state, rationale, sign-off data, and other annotations do not affect source-derived identity.
- `test_ids_differ_for_different_source_positions` — the same label under different source sections or parent paths receives different IDs.
- `test_bootstrap_uses_safe_unreviewed_defaults` — derived nodes do not claim review or sign-off.
- `test_rederive_no_source_change_preserves_current_record` — unchanged source leaves current decisions and metadata untouched.
- `test_rederive_source_only_change_updates_derived_fields` — a source-only edit updates the derivation without reporting a conflict.
- `test_rederive_current_only_change_preserves_human_edit` — an independently edited current value survives when its source baseline is unchanged.
- `test_rederive_same_change_on_both_sides_is_not_conflict` — matching source and current edits converge safely.
- `test_rederive_divergent_change_reports_conflict` — different edits from the same baseline produce a conflict and do not overwrite current state.
- `test_rederive_reviewed_node_removal_reports_conflict` — removing reviewed source content cannot silently delete its concept.
- `test_rederive_unchanged_unreviewed_node_removal_is_safe` — an unmodified derived node may be removed when its source disappears.
- `test_rederive_adds_new_source_concept_deterministically` — new source content receives stable identity and default review state.
- `test_rederive_collects_all_conflicts` — one run reports every divergent node rather than stopping at the first.
- `test_rederive_does_not_mutate_input_on_conflict` — the supplied current tree remains unchanged after a conflicted result.
- `test_bootstrap_does_not_persist` — deriving a tree performs no filesystem write.

### Test-creation order (feature step)

Add the identity and unchanged-input tests with the first bootstrap implementation. Add the three-way branch tests as re-derivation is introduced, followed by addition, removal, multi-conflict, and no-mutation cases. Every new test in `tests/test_concept_bootstrap.py`, plus affected parser and schema tests, must be green before this step is considered finished.

## Acceptance criteria

- Calling the bootstrap operation twice with the same `Plan`, parsed sections, and integrity inputs returns the same concept values, order, and UUIDs.
- Changing review state, rationale, sign-off metadata, display order, or fingerprints does not change a concept’s source-derived ID.
- Concepts with the same label but different source sections or parent paths receive different IDs.
- Bootstrap consumes the shared `plan_tool/parser.py` body-section representation and contains no separate Markdown heading parser.
- A source-only change can produce an updated candidate while preserving compatible identity and review metadata.
- Divergent source and current-record edits produce explicit conflicts and leave the supplied current tree unchanged.
- Removing a reviewed or independently changed concept produces a conflict rather than silently dropping it.
- Bootstrap and re-derivation do not persist the concept record or modify plan Markdown.
- `tests/test_concept_bootstrap.py` and all affected `tests/test_parser.py` tests pass.

## References

- [Python uuid — UUID Objects](https://docs.python.org/3/library/uuid.html) — Use the UUID namespace and `uuid5()` rules for repeatable source-derived identifiers.
- [RFC 9562 — Universally Unique IDentifiers](https://www.rfc-editor.org/rfc/rfc9562.html) — Read the name-based UUID semantics and identity guarantees.
- [Python hashlib — Secure Hashes and Message Digests](https://docs.python.org/3/library/hashlib.html) — Use deterministic digests only where the step 1 integrity contract requires them.

## Deferred

- **Automatic conflict resolution** — Preserve and report conflicts for explicit reconciliation; the plan deliberately does not choose a winner.
- **Concept-record persistence** — Use the writer delivered by step 1; caller-owned persistence is wired by steps 5 and 6.
- **Plan-body synchronization** — Step 5 owns coordinated changes between accepted concept state and Markdown.
- **Three-state review and scoped sign-off** — Step 4 owns operator decisions and sign-off rules.
- **Semantic concept dependency detection** — The plan defers relationships that cannot be derived from explicit source structure.
