> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Add a CLI action to accept a hand-edited draft as current

## Summary

Adds `accept_roadmap_seed(slug, plan_id, *, repo_root, plans_dir)` to `plan_tool/roadmap.py` and wires it to a new `--accept-seed PLAN_ID` flag on `plan-tool roadmap`. The call never invokes the backend and never rewrites the draft file: on a draft step 3's `classify_draft_seeds` calls `digest-mismatched`, it runs the live bytes through step 1's `validate_draft_seed_content`, and on a clean result records that digest as the entry's `current` digest in `seed-state.json`. It refuses every other classification, and refuses a `digest-mismatched` draft whose content fails validation, reporting why in both cases. When the plan's sidecar entry is already `published`, it also re-syncs `plan-seeds/<id>.md` with the accepted content, using the same `_promoted_seed_body`/`render_seed_state_marker`/`atomic_write_text` primitives `refresh_roadmap_seeds` already uses for that. On green, a reviewer who hand-edits a draft has one command that keeps the edit and clears the `digest-mismatched` state, instead of the edit being overwritten by the only two remedies that existed before this step.

## Table of Contents

- [Why](#why) — the gap left once `--apply` refuses on the classifier's word
- [Input](#input) — the validator, the classifier, and the sidecar/promoted-copy contracts this step writes to
- [Files (creates vs edits)](#files-creates-vs-edits) — the four declared files, no additions
- [Implementation](#implementation) — the new orchestrator call, the CLI wiring, and what must not change
- [Tests](#tests) — new orchestrator- and CLI-level coverage
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Step 6 makes `--apply`'s preflight refuse any draft that step 3's `classify_draft_seeds` calls anything but `current`. Because the classifier's precedence checks `digest-mismatched` ahead of every other state, a reviewer's hand edit to a draft always lands there, well-formed or not, the moment its bytes stop matching the digest `seed-state.json` recorded at generation. Before this step, the only ways to move a plan id off that state are step 4's `--refresh-seeds` and step 5's `--materialize`, and both regenerate the draft through a fresh backend call — the one outcome a reviewer who just finished editing the file does not want. There is no command that says "I reviewed this edit myself, keep it" without routing the file back through generation and losing the edit. This step adds that command: it writes only the sidecar (and, when the plan is already promoted, the `plan-seeds/` copy), never the draft, so the accepted bytes are exactly the bytes the reviewer left on disk.

## Input

This step is grounded in two upstream contracts it consumes as-is, one existing sidecar contract it writes into without widening, and one existing write pattern it mirrors:

- **Step 1's `validate_draft_seed_content(text: str, *, plan: PlanRow) -> list[Violation]`** (`plan_tool/roadmap_gates.py`). Never raises: an unparseable frontmatter block folds into a `VIOLATION_DRAFT_SEED_PROVENANCE` violation, and a `roadmap_components` entry that resolves to neither `plan.component_ids` nor the cross-cutting carve becomes a `VIOLATION_UNDEFINED_SEED_COMPONENT_REFERENCE` violation. This is the only content check this step runs — no prose-quality, length, or style check belongs here (see Applicable guardrails). Read the landed module for the exact signature; it wins over this description on any disagreement.
- **Step 3's `classify_draft_seeds(artifact: PlansArtifact, *, plans_dir: Path, slug: str) -> dict[str, DraftSeedClassification]`** (the new `plan_tool/roadmap_seed_manifest.py` leaf), the seven `DRAFT_SEED_STATE_*` constants, and the precedence order the plan's Architecture section fixes (`duplicate` → `path-escaping` → `missing` → `digest-mismatched` → `stale` → `malformed` → `current`). Each `DraftSeedClassification` carries `plan_id`, `state`, and a human-readable `detail` written to be surfaced directly. This step accepts only the row named `plan_id`; every other row in the map is untouched. Read the landed module for the exact constant spellings; they win over this file's guess (`DRAFT_SEED_STATE_DIGEST_MISMATCHED` below is illustrative, not a citation). **This step's own refusal is unaffected by the stale/malformed accuracy window step 3's detail describes** (only fully resolved once step 9 lands): accept refuses on any state but `digest-mismatched`, so whether a non-`digest-mismatched` refusal is correctly `stale` or misreported as `malformed` in that window changes only the refusal's `detail` text, never whether this step accepts or refuses.
- **The `seed-state.json` sidecar** (`plan_tool/roadmap_seed_state.py`): `load_seed_state`/`write_seed_state`/`validate_seed_state` enforce a two-member stored `status` vocabulary (`"current"` / `"invalidated"`) per entry, plus `draft_seed_path`, `digest`, and `published`. The classifier's seven states are a *derived* read over this sidecar plus the live file and the artifact — never a widening of what gets stored. This step writes exactly one stored value, `status="current"`, with `digest` set to the live file's own hash; it never writes `"invalidated"` or any of the five derived-only state names into the sidecar.
- **The promoted-copy resync pattern `refresh_roadmap_seeds` already runs** (`plan_tool/roadmap.py`, confirmed at HEAD: `if published or promoted.exists() or _latest_seed_archive(promoted) is not None:`): for a plan whose sidecar entry is `published`, whose `plan-seeds/<id>.md` already exists, or whose most recent archived generation (`_latest_seed_archive(promoted)`) exists, it rebuilds the promoted body with `_promoted_seed_body(candidate, marker=render_seed_state_marker(...))` and writes it with `atomic_write_text`. This step reuses those same three calls — `_promoted_seed_body`, `render_seed_state_marker`, `atomic_write_text` — for its own, narrower resync (one plan, no backend-produced `candidate`, the live draft's own text instead), and the same three-way OR: it must not skip resyncing a plan whose `plan-seeds/` copy or archive exists but whose `published` flag happens to be false or absent.
- **`roadmap_dir(plans_dir, slug)` raises a bare `ValueError` on a malformed slug**, not `RoadmapError`. `apply_roadmap_seeds` wraps that first call in `try/except ValueError as exc: raise RoadmapError(str(exc)) from exc` before touching anything else, specifically so the CLI's `except (RoadmapError, RoadmapArtifactError)` catches it instead of an unhandled traceback. Nothing else this step calls validates the slug up front, so it needs the same wrap.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/roadmap.py` — add `ACCEPT_OUTCOME_ACCEPTED` / `ACCEPT_OUTCOME_REFUSED`, a `RoadmapSeedAcceptResult` dataclass, and `accept_roadmap_seed`. Extend the existing `plan_tool.roadmap_gates` import with `validate_draft_seed_content` (landed by step 1). Extend the `plan_tool.roadmap_seed_manifest` import step 6 already adds to this file with `classify_draft_seeds` and the digest-mismatched state constant, if either is not already present there.
- `plan_tool/cli/roadmap_cmd.py` — add `--accept-seed PLAN_ID` to `run_mode_group`; add the `accept_seed` dispatch branch in `cmd_roadmap`; add `_cmd_roadmap_accept_seed` and `_render_accept_result`; extend the `plan_tool.roadmap` import with `ACCEPT_OUTCOME_ACCEPTED`, `ACCEPT_OUTCOME_REFUSED`, `RoadmapSeedAcceptResult`, `accept_roadmap_seed`; update the module docstring's mode inventory and `cmd_roadmap`'s rc-mapping paragraph.
- `tests/test_roadmap.py` — add coverage for `accept_roadmap_seed`, reusing the `_ApplyEnv` / `_apply_env` / `_standard_apply_setup` / `write_draft` / `_seed_text` fixtures already built for `TestApplyRoadmapSeeds` (post step 1's `plan-seed-drafts/` rename).
- `tests/cli/test_roadmap_cmd.py` — add `accept_seed=None` to `_ns()`'s defaults; add CLI-layer coverage for the new mode; extend `TestArgparseWiring` with the flag's parsing, mutual exclusivity, and help-text cases.

## Implementation

### The new orchestrator call

`accept_roadmap_seed(slug: str, plan_id: str, *, repo_root: Path, plans_dir: Path) -> RoadmapSeedAcceptResult` in `plan_tool/roadmap.py`, placed beside `apply_roadmap_seeds`/`refresh_roadmap_seeds` in the "apply-only" region of the file. Unlike those two, it takes no `invoker` — it must never be able to call the backend, which is the whole point of the command (see Applicable guardrails).

What it must do, in order:

1. **Validate the slug first**, the same `try: roadmap_dir(...) except ValueError as exc: raise RoadmapError(...) from exc` wrap `apply_roadmap_seeds` opens with (see Input) — every later call in this function builds a path from `slug` and none of them re-checks it.
2. **Load `04-roadmap.md`** via `load_plans_artifact(plans_path(plans_dir, slug))`. Let `RoadmapArtifactError` propagate uncaught — the CLI layer already catches it alongside `RoadmapError`, matching `apply_roadmap_seeds`/`refresh_roadmap_seeds`.
3. **Find the plan row** whose `id == plan_id` in `artifact.plans`. When none matches, return a refused result rather than raising — an unknown plan id is a data mismatch between the CLI argument and the roadmap, the same shape as `--apply`'s collision/missing-draft refusals, not a malformed-input error.
4. **Classify** via `classify_draft_seeds(artifact, plans_dir=plans_dir, slug=slug)`, wrapped in the same `try/except RoadmapSeedStateError as exc: raise RoadmapError(str(exc)) from exc` conversion step 6's `_apply_roadmap_seeds` already applies to this call (see step 6's Input/Implementation) — a corrupt sidecar is a roadmap-level failure here too, and the CLI layer below already catches `RoadmapError` alongside `RoadmapArtifactError`, so letting the raw `RoadmapSeedStateError` escape would crash `_cmd_roadmap_accept_seed` instead of reporting it. Then look up `plan_id` in the classification map. When the state is anything but the digest-mismatched constant, return a refused result carrying that state and its `detail` — this is the six-way refusal the step's whole reason for existing depends on (accepting a `missing` or `malformed` draft as current would record a broken or absent file as trustworthy).
5. **Read the live draft's bytes** via `resolve_draft_seed_path(plans_dir, slug, plan.draft_seed_path)` and run them through `validate_draft_seed_content(text, plan=plan)`. A non-empty result is a refusal carrying those violations — this is what stops a broken hand edit (bad YAML, an unresolved component id) from being accepted just because it happens to be `digest-mismatched`.
6. **Write the sidecar.** Load the existing entry (`_load_roadmap_seed_state`/`entries.get(plan_id, {})`), and write back `{"draft_seed_path": plan.draft_seed_path, "status": "current", "digest": digest_text(text), "published": <preserved from the old entry>}` — the same four-key shape `_mark_roadmap_seeds_current`, `_register_roadmap_seed_promotions`, and `refresh_roadmap_seeds` already write. Persist with `_write_roadmap_seed_state`.
7. **Resync the promoted copy whenever any of three conditions hold.** Let `promoted = resolve_plan_seed_dest(repo_root / "plan-seeds", plan_id)`. If the preserved `published` flag is true, **or** `promoted` exists on disk, **or** `_latest_seed_archive(promoted) is not None`, rebuild its body with `_promoted_seed_body(text, marker=render_seed_state_marker(state_path=seed_state_path(roadmap_dir(plans_dir, slug)), repo_root=repo_root, roadmap_slug=slug, plan_id=plan_id))` and write it with `atomic_write_text`. Do nothing further only when none of the three hold — first promotion stays `--apply`'s job. This mirrors `refresh_roadmap_seeds`'s own condition exactly (`plan_tool/roadmap.py`): a plan whose `published` flag is false or absent but whose `plan-seeds/` copy or archive still exists on disk must still be resynced.
8. **Return** `RoadmapSeedAcceptResult(outcome=ACCEPT_OUTCOME_ACCEPTED, plan_id=plan_id, target=source, promoted_target=<the resynced path or None>)`.

`RoadmapSeedAcceptResult` is a frozen dataclass carrying facts only, no exit code — the established shape (`RoadmapApplyResult`, `RoadmapSeedRefreshResult`). One reasonable field set: `outcome`, `plan_id`, `target: Path | None`, `promoted_target: Path | None`, `state: str | None` (the classifier's state when the id resolved but wasn't digest-mismatched; `None` for both an unknown id and a successful accept), and `violations: tuple[Violation, ...]` (non-empty only on a failed-validation refusal). Three refusal shapes fall out of those two fields without a separate reason enum: `state is None` means an unknown plan id, a set `state` means the wrong classification, and a non-empty `violations` means the digest-mismatched draft failed content validation.

### The CLI action

In `plan_tool/cli/roadmap_cmd.py`:

- Add `--accept-seed`, `metavar="PLAN_ID"`, default `None`, to the existing `run_mode_group` — mutually exclusive with `--apply`, `--refresh-seeds`, `--from-stage`, and `--view` (and, once step 5 lands in the same group, `--materialize`). Argparse's default hyphen-to-underscore conversion gives `args.accept_seed`; no explicit `dest=` needed.
- In `cmd_roadmap`, add a dispatch branch reading `args.accept_seed` — placed after the `--refresh-seeds` branch and before the `--view` branch, matching the module's existing ordering of "explicit action modes" before the read-only mode and the stage-run fallback.
- `_cmd_roadmap_accept_seed(args, *, repo_root, plans_dir) -> int` — calls `accept_roadmap_seed(args.slug, args.accept_seed, repo_root=repo_root, plans_dir=plans_dir)`, catches `(RoadmapError, RoadmapArtifactError)` and reports via `error()` at rc `_RC_USAGE`, otherwise renders the result and returns `0` for `ACCEPT_OUTCOME_ACCEPTED` or `_RC_USAGE` for `ACCEPT_OUTCOME_REFUSED` — the same accepted/refused-is-a-usage-code mapping `_cmd_roadmap_apply` uses for `APPLY_OUTCOME_REFUSED`.
- `_render_accept_result(result, *, slug, repo_root)` — on acceptance, a `success()` line naming the plan id, a `detail()` line for the accepted draft path, and, when `promoted_target` is set, a line naming the resynced path plus a `plan-tool create {plan_id} --from-existing {short_path(promoted_target)}` handoff line in the style of `_promoted_create_handoff_lines`. On refusal, an `error()` line naming the plan id and, depending on which of the three shapes fired, either the unresolved-id detail, the wrong-classification state and detail, or each violation's message (mirroring `_render_apply_result`'s per-reason error blocks). **The wrong-classification refusal branch adds one trailing remedy hint line, mirroring step 6's identical `--materialize` pointer for `_render_apply_result`'s own refusal (see step 6's Implementation, "Rendering").** Step 3 leaves `detail` empty for `stale` and `current`, so without this line an operator refused on either state sees only the bare state word — nothing to act on. For `missing`, `stale`, `malformed`, or `path-escaping` (the four states step 5's `--materialize <plan_id>` can regenerate), print `plan-tool roadmap {slug} --materialize {plan_id}` as the hint. For `duplicate`, the remedy is not `--materialize` — a basename collision is a plan-row property only a roadmap revision (or hand-editing `04-roadmap.md`) can fix — so print no `--materialize` hint for that state; naming the colliding sibling (already in `detail`) is the whole remedy. `current` is not reachable as a *refusal an operator needs to act on* in practice (nothing is wrong), but it is still a valid refusal state per the classifier — no hint line for it either. Keep the hint to one line, per step 6's own precedent that "the per-state remedy catalog belongs to the step 8 view, not here."
- Update the module docstring's mode inventory (it currently lists `--apply`, `--refresh-seeds`, `--view`) and `cmd_roadmap`'s docstring paragraph enumerating rc-2 causes, adding the new refusal alongside "a refused apply preflight".

### What must not change

- The draft file at `resolve_draft_seed_path(...)` is **read**, never written, by this call — the digest recorded is the hash of whatever is already on disk. A test asserting the file's bytes are unchanged before and after `accept_roadmap_seed` is not optional polish; it is the property the whole step exists to guarantee (see Applicable guardrails).
- No `invoker` parameter, no call into `shell_roadmap_invoker`/`claude_invoke`, and no `_run_stage` — this function never shells out.
- `--apply`'s own preflight and commit path (`_apply_roadmap_seeds`) is untouched. Accept never performs a *first* promotion — it resyncs a copy that a prior `--apply` already created, so it writes with a plain `atomic_write_text`, not the two-phase `os.link` commit `_apply_roadmap_seeds` uses to guard against a destination that appears mid-confirm. There is no confirm window here to guard.

## Tests

### Tests for this step

`tests/test_roadmap.py` (a new section/class beside `TestApplyRoadmapSeeds`, reusing `_ApplyEnv`/`_apply_env`/`_standard_apply_setup`/`write_draft`/`_seed_text`; construct a digest-mismatched fixture the same way the existing refresh test does — write a sidecar entry with `status="current"` and a recorded digest via `write_seed_state`/`load_seed_state`, then hand-edit the draft file's bytes without updating that digest):

- `test_accept_records_live_digest_as_current` — accepting a digest-mismatched draft returns `ACCEPT_OUTCOME_ACCEPTED`, and the sidecar entry afterward has `status == "current"` and `digest == digest_text(<the file's live bytes>)`.
- `test_accept_leaves_the_draft_file_bytes_unchanged` — the draft file's content before and after the call is identical.
- `test_accept_resyncs_an_already_promoted_copy` — with `published: true` and a `plan-seeds/<id>.md` on disk from a prior fixture write, `promoted_target` is set and the file's new content equals `_promoted_seed_body` of the accepted text with a freshly rendered marker.
- `test_accept_does_not_touch_plan_seeds_when_not_published` — with `published: false` (or no entry at all) and no `plan-seeds/<id>.md` and no archived generation on disk, `plan-seeds/<id>.md` stays absent and `promoted_target` is `None`.
- `test_accept_resyncs_an_unpublished_plan_whose_promoted_copy_already_exists` — with `published: false` but `plan-seeds/<id>.md` already on disk (a plan promoted before its sidecar entry's `published` flag was set, or set by an unrelated path), `promoted_target` is still set and the file is still rewritten — proving the resync condition is a three-way OR (`published or promoted.exists() or _latest_seed_archive(promoted) is not None`), not an AND gated on `published` alone.
- `test_accept_refuses_each_non_digest_mismatched_classification` (parametrized or one case per state) — `current`, `missing`, `stale`, `malformed`, `path-escaping`, and `duplicate` drafts each return `ACCEPT_OUTCOME_REFUSED` with `state` set to that classification, `violations == ()`, and neither the sidecar nor `plan-seeds/` written.
- `test_accept_refuses_a_digest_mismatched_draft_that_fails_content_validation` — a hand edit that references an undefined component id (or breaks the frontmatter) returns `ACCEPT_OUTCOME_REFUSED` with a non-empty `violations` and no sidecar or `plan-seeds/` write.
- `test_accept_refuses_an_unknown_plan_id` — a `plan_id` absent from `artifact.plans` returns `ACCEPT_OUTCOME_REFUSED` with `state is None`.
- `test_accept_wraps_an_invalid_slug_as_roadmap_error` — a path-escaping or otherwise invalid slug raises `RoadmapError`, not a bare `ValueError`.
- `test_accept_propagates_a_malformed_predecessor_as_roadmap_artifact_error` — an unparseable `04-roadmap.md` on disk raises `RoadmapArtifactError` from `load_plans_artifact`, uncaught.
- `test_accept_wraps_a_corrupt_sidecar_as_roadmap_error` — a corrupt `seed-state.json` raises `RoadmapError` (not `RoadmapSeedStateError`) from the `classify_draft_seeds` call, matching step 6's conversion for the identical failure.

`tests/cli/test_roadmap_cmd.py`:

- Extend `_ns()`'s defaults with `accept_seed=None`.
- `test_cmd_accept_seed_delegates_to_accept_roadmap_seed` — stubs `accept_roadmap_seed`, asserts `run_roadmap`, `apply_roadmap_seeds`, and `refresh_roadmap_seeds` are never called, and that `slug`/`plan_id` reach the stub.
- `test_accept_seed_accepted_prints_success_and_target` — a stubbed accepted result prints the plan id and target path; rc is `0`.
- `test_accept_seed_prints_resync_and_create_handoff_when_promoted` — a stubbed accepted result with `promoted_target` set prints the resync line and a `plan-tool create ... --from-existing` line naming that path.
- `test_accept_seed_refused_prints_the_matching_detail_and_returns_rc_two` — three stubbed refused results (unknown id, wrong state, validation violations) each print their own detail and return rc `2`.
- `test_accept_seed_refusal_names_a_materialize_remedy_for_regenerable_states` (parametrized over `missing`, `stale`, `malformed`, `path-escaping`) — a stubbed refused result for each state prints a `plan-tool roadmap {slug} --materialize {plan_id}` line; `stale`'s case in particular (empty `detail`) proves the operator sees an actionable line, not just the bare state word.
- `test_accept_seed_refusal_names_no_materialize_remedy_for_duplicate_or_current` — stubbed refused results for `duplicate` and `current` print no `--materialize` line.
- Extend `TestArgparseWiring`: `test_accept_seed_argparse_default_is_none`; `test_accept_seed_mutually_exclusive_with_apply`; `test_accept_seed_mutually_exclusive_with_refresh_seeds`; `test_accept_seed_mutually_exclusive_with_materialize`; `test_accept_seed_mutually_exclusive_with_view`; `test_accept_seed_mutually_exclusive_with_from_stage`; `test_help_documents_accept_seed`.

Every test above must be green before this step is considered finished.

## Acceptance criteria

- `accept_roadmap_seed` returns `ACCEPT_OUTCOME_ACCEPTED` for a `digest-mismatched` draft that passes `validate_draft_seed_content`, and the sidecar entry it leaves behind has `status == "current"` and `digest` equal to the live file's own hash.
- The draft file's bytes are identical before and after every call to `accept_roadmap_seed`, accepted or refused.
- `accept_roadmap_seed` returns `ACCEPT_OUTCOME_REFUSED` (never raises) for each of the six non-digest-mismatched classifications, for a digest-mismatched draft that fails content validation, and for an unknown plan id — and none of those three refusal paths writes the sidecar or `plan-seeds/`.
- When the sidecar entry's `published` flag is true, or `plan-seeds/<id>.md` exists, or that path's most recent archived generation exists, a successful accept rewrites `plan-seeds/<id>.md` to match the accepted content's promoted body; only when none of the three hold is that file left untouched.
- `accept_roadmap_seed` never calls a backend invoker — `plan_tool/roadmap.py`'s diff for this step adds no new call to `shell_roadmap_invoker`, `claude_invoke`, or `_run_stage` inside the function.
- `plan-tool roadmap <slug> --accept-seed <PLAN_ID>` exits `0` on acceptance and `2` on refusal or on a caught `RoadmapError`/`RoadmapArtifactError`.
- `--accept-seed` is mutually exclusive with `--apply`, `--refresh-seeds`, `--materialize`, `--from-stage`, and `--view` at the argparse layer (`SystemExit` on any pair).
- `cmd_roadmap` never calls `run_roadmap` or `apply_roadmap_seeds` when `--accept-seed` is supplied.
- A refusal on `missing`, `stale`, `malformed`, or `path-escaping` prints a `plan-tool roadmap {slug} --materialize {plan_id}` remedy line, even when step 3's `detail` is empty (the `stale` case); a refusal on `duplicate` or `current` prints no such line.
- `plan-tool roadmap --help` documents `--accept-seed`.
- Every test enumerated in Tests passes.

## References

- [ROADMAP_FORMAT.md](../../../../ROADMAP_FORMAT.md) — the `seed-state.json` sidecar contract and the `draft_seed_path` rule this step's writes must keep satisfying; step 3 documents the classifier's seven states and precedence here.
- [DATA_CONTRACT.md](../../../../DATA_CONTRACT.md) — persisted-schema conventions for the roadmap directory sidecar; consult before deciding whether `RoadmapSeedAcceptResult` needs an entry (it is an in-memory result, not a persisted/serialized event, so it should not).

## Applicable guardrails

- **Step intent.** This step's own stated intent is the primary fence: accept records a reviewed hand edit's live digest as `current` and, when already promoted, re-syncs the `plan-seeds/` copy — nothing more. It calls neither step 2's generation primitive nor step 4's refresh, and it refuses on every classification but `digest-mismatched`.
- **Out of scope — "Auto-promoting drafts, auto-accepting roadmap feedback, or treating draft materialization as user approval."** Accept stays an explicit, single-`plan_id`, human-invoked CLI action; nothing else in the roadmap flow may call `accept_roadmap_seed` on a reviewer's behalf.
- **Out of scope — "Regenerating every seed on a roadmap revision, deleting a stale seed to hide it, or writing a replacement without the explicit materialization/refresh action."** The explicit carve-out for this step's accept action confirms it is a mechanical identity/content sync, not an approval gate — this is why no interactive TTY confirmation (mirroring `--apply`'s `-y`/prompt gate) belongs here: the classification plus a passed content validation already stand in for the review `--apply`'s confirm exists to force before a *first* promotion.
- **Out of scope — "A correctness gate on seed style, length, or model agreement... the binary observable is whether each manifest plan ID has exactly one valid draft with the recorded identity, and whether promotion refuses every other state."** The content check this step runs is exactly `validate_draft_seed_content`'s existing provenance/component checks — no new prose-quality, length, or style rule belongs in this step.

## Deferred

- Batch or `--accept-seed all`-style acceptance across every digest-mismatched plan — declined by design: accepting a hand edit is inherently a per-draft, reviewed decision, and a batch form would accept edits nobody looked at, defeating the reason the command exists.
- A dedicated run-log telemetry event for accept (mirroring `RoadmapSeedApplyResult`) — not added; `refresh_roadmap_seeds` itself opens no dedicated run-log event today, so accept matches its closest sibling rather than introducing new telemetry surface this plan's Architecture does not call for.
- Changes to `plan_tool/cli/authoring.py`'s `_confirm_invalidated_roadmap_seed` — not needed. After a successful accept, the plan id's classification is `current` on the next `classify_draft_seeds` call, so step 3's existing routing already stops prompting `create` with no further change here.
- Updating `ROADMAP_WALKTHROUGH.md`'s narrative — routed to step 11, which already owns describing the full per-plan materialization surface once every step in this plan has landed.
