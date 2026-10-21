> **Withdrawn 2026-08-26** — Superseded by the user-directed smallest-proof seed after repeated granularity split signals were not acted on; its reusable benchmark scope exceeds position 01.
> Preserved here for history; do not edit.

---
title: Quality Bench 01 Corpus And Noise Floor
intent: '`plan-tool quality-bench run --corpus <dir> --label <name>` replays a fixed
  corpus of seeds through one authoring stage, stores every artifact it produced,
  and computes a predeclared set of **deterministic** metrics over them; `plan-tool
  quality-bench compare <label-a> <label-b>` prints each metric''s delta **beside
  that metric''s own measured rerun spread**, so a difference is reported as inside
  or outside the noise rather than as a bare number.'
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/quality-bench-01-corpus-and-noise-floor.md
steps:
- id: 1
  title: Parse and version the self-contained quality-bench corpus format, and add
    roadmap-stage-2 fixtures
  intent: Gives the replay engine a committed, versioned set of fixed-input corpus
    items. Every item manifest stores JSON-integer `format_version` 1; missing, non-integer,
    or unsupported values reject the corpus before a snapshot or replay. Each v1 item
    names a nonempty single-component roadmap slug and target stage 2, bundles its concept brief, admitted 01-domain
    artifact, and domain baseline, and uses only item-relative paths so `quality-bench
    run`/`floor` can materialize a complete isolated replay. The selected `--corpus`
    directory resolves to the corpus root. Its v1 item set is exactly the non-hidden
    immediate child directories, sorted by their UTF-8 names; each directory and its
    manifest must strictly resolve beneath that root. The canonical snapshot contains
    each enumerated manifest and its declared input files, sorted by lexical POSIX-relative
    path, and its digest is SHA-256 of the ASCII domain separator `quality-bench-corpus-v1\0`
    followed by every path and byte value, each framed by its unsigned 64-bit big-endian
    byte length. Every declared corpus-file reference is nonempty, relative without
    a `..` component, and resolves strictly beneath its resolved item directory, including
    its symlink target; an absolute, missing, traversal, or escaping reference is
    rejected before a replay. Its nonempty lower-case manifest item id matches `[a-z0-9][a-z0-9._-]{0,127}`
    and is unique within the corpus; invalid or duplicate ids are rejected before
    any replay and the key is stable for evidence and vector ordering.
  creates:
  - plan_tool/quality_bench_corpus.py
  - benchmarks/quality-bench/corpus/roadmap-constraints/item-1/brief.md
  - benchmarks/quality-bench/corpus/roadmap-constraints/item-1/01-domain.md
  - benchmarks/quality-bench/corpus/roadmap-constraints/item-1/.roadmap-baselines/domain.json
  - benchmarks/quality-bench/corpus/roadmap-constraints/item-1/manifest.json
  - benchmarks/quality-bench/corpus/roadmap-constraints/item-2/brief.md
  - benchmarks/quality-bench/corpus/roadmap-constraints/item-2/01-domain.md
  - benchmarks/quality-bench/corpus/roadmap-constraints/item-2/.roadmap-baselines/domain.json
  - benchmarks/quality-bench/corpus/roadmap-constraints/item-2/manifest.json
  - tests/test_quality_bench_corpus.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/quality-bench-01-corpus-and-noise-floor/01-parse-version-self-contained-quality.md
  status: current
- id: 2
  title: Build the deterministic quality-bench metric registry (counts, id resolution,
    section/fence presence, gate attempts, exit outcome, wall time, cost)
  intent: Gives the replay engine and `compare` a fixed, independently testable set
    of deterministic metrics computable from stored bytes alone. Registry v1 fixes
    the finite per-item vocabulary and every metric's encoded value and distance;
    the Architecture table owns the exact stored-evidence rules for anchors, collections,
    run-log events, retries, and unavailable values. The corpus value is its ordered
    manifest-item vector and its distance is the maximum item distance. The registry
    can recompute a selected version from raw stored evidence, so no rubric or model
    enters the measurement path.
  creates:
  - plan_tool/quality_bench_metrics.py
  - tests/test_quality_bench_metrics.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/quality-bench-01-corpus-and-noise-floor/02-build-deterministic-quality-bench.md
- id: 3
  title: Build the corpus replay engine and label-keyed artifact/run-log store under
    .plan-tool/quality-bench/ (refuses a label collision; --force publishes a recoverable
    replacement archive)
  intent: Before any scratch materialization, builds the step-1 canonical private,
    byte-exact snapshot of every enumerated item manifest and declared corpus input,
    and derives the label's corpus digest from that exact encoding. From the same
    clean preflight, it pins the loaded-root-matched full source execution identity
    and canonical backend profile digest, including the effective configured and silence
    termination timeouts. It freezes those timeout values for every replay attempt
    rather than rereading ambient configuration. It replays each item in an isolated
    scratch repo by materializing its brief, admitted upstream artifact, and trusted
    baseline only from that snapshot, never rereading `--corpus` during the item loop,
    then calls run_roadmap with the stage table truncated at the item's target and
    from_stage equal to that target inside backend.spawn_cwd(scratch). This selects
    stage 2 once, re-gates stage 1, and preserves the existing retry policy for its
    backend attempts; no later stage runs. Immediately before and after every item
    replay, and again before label publication, it requires the clean source execution
    identity and backend profile to equal that pin. A corpus edit cannot enter the
    snapshot; a source or backend mismatch discards every private capture artifact
    and leaves any old label/archive generation unchanged. Its quality-bench recovery
    seam keeps rate-limit retries on the pinned repo-root effective backend and records
    that actual profile on every attempt; every fallback or interactive switch selection,
    including one that would resolve to the same profile or from the scratch root,
    stops and discards the private capture before publication. A capture-specific recovery
    policy reaches `claude_invoke` before reinvocation, permits only a pinned-profile
    wait, and rejects a switch before it selects or runs another backend. It persists that label-owned
    input snapshot, every output artifact, run log, and serialized RoadmapResult facts
    with the actual source execution identity in a version-1 quality-bench `label`
    envelope. A `raw-sample` is one complete corpus rerun keyed by its floor id and
    sample ordinal, whose item map uses validated manifest ids, so floor/compare have
    durable, recomputable evidence. It validates each lower-case label with that same
    pattern and the quality-bench engine owns the one repo mutation lock across label
    lookup, recoverable replacement transaction, and atomic current-pointer publication.
    It calls `working_tree_dirty` before scratch
    materialization and again before publication; any tracked or unignored dirt rejects
    the capture and leaves the existing label unchanged. It adds the root-anchored
    `/.plan-tool/quality-bench/` ignore rule and verifies the same dirt predicate
    used by `run` and `floor` permits that exact ignored store but no neighboring
    untracked path, so an initially clean source checkout stays eligible for a following
    floor run. An existing label fails without --force; --force stages and validates
    a new immutable generation, journals the old/new capture ids and reserved numbered
    archive slot, preserves the old generation at that slot, and atomically changes
    the label's current pointer only after both generations are complete. Recovery
    under the mutation lock completes a valid journaled transition or retains the
    old current generation; lookup never observes the logical label absent or partial.
  files:
  - .gitignore
  creates:
  - plan_tool/quality_bench.py
  - tests/test_quality_bench.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: supplies the corpus loader and the fixture items to replay
    2: supplies the metric registry and the stored-run envelope shape the engine populates
      and calls
  detail: docs/implementation-plans/plan-details/quality-bench-01-corpus-and-noise-floor/03-build-corpus-replay-engine-label-keyed.md
- id: 4
  title: Wire `plan-tool quality-bench run` as a new CLI verb, kept separate from
    the existing `bench` verb
  intent: Gives operators `plan-tool quality-bench run --corpus <dir> --label <name>`
    as an entry point to the step-3 engine, registered as its own verb (module, dest,
    and storage root all named quality_bench/quality-bench) so it can never collide
    with the pre-existing bench (backend-quality-benchmark) verb group; includes an
    integration-marked end-to-end test driving the CLI dispatch with a stubbed invoker.
    `run` and `floor` are mutating subactions covered by the existing repo mutation
    lock, while `compare` remains read-only.
  files:
  - plan_tool/cli/parser.py
  - plan_tool/cli/app.py
  - CAPABILITIES.md
  creates:
  - plan_tool/cli/quality_bench_cmd.py
  - tests/cli/test_quality_bench_cmd.py
  - docs/cli/quality-bench.md
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: supplies the replay-and-store engine the run action calls
  detail: docs/implementation-plans/plan-details/quality-bench-01-corpus-and-noise-floor/04-wire-plan-tool-quality-bench-run-new.md
- id: 5
  title: Add `plan-tool quality-bench floor` — rerun the corpus R times at one source
    execution identity and persist each metric's measured noise floor
  intent: Answers what each metric does when nothing changes by rerunning the corpus
    from `--corpus <dir>` through the step-3 engine at one clean, loaded-source-matched
    revision and canonical backend-profile digest, including frozen configured and
    silence termination timeouts. That digest is the persisted canonical profile contract
    defined in Architecture, not only a backend name or model. `--reruns` defaults
    to 3 and rejects values below 2. Its floor is the maximum pairwise registered
    metric distance across those R values; identical values floor at zero. Each complete
    measurement persists one immutable full-corpus raw-sample envelope per sample ordinal
    under a floor id, whose item map is keyed by manifest id, and an entry for every
    registry-v1 metric, either its numeric floor or an explicit unfloored
    result when any required value is missing. It then atomically becomes the single
    current-floor record for its exact corpus/replay/source/profile identity. From
    one clean preflight before sample one, it pins that complete identity — resolved
    corpus digest, replay descriptor, full source execution identity, and canonical
    backend-profile digest. It recomputes and requires that identity immediately before
    and after every R capture and immediately before pointer publication; dirt or
    any mismatch discards every private sample and leaves the prior record and pointer
    unchanged. An interrupted capture with fewer than R completed samples also publishes
    no record and leaves the prior pointer unchanged. Every immutable floor record
    and current-floor pointer is a version-1 quality-bench envelope. Under the engine-owned
    mutation lock, final floor-id allocation reserves an absent immutable record path;
    a collision allocates a new generated safe id and never overwrites an existing
    record or retargets a pointer. The invoking operator manually reviews each identity's
    first complete floor table and records any noise-dominated defer outcome in BACKLOG
  files:
  - plan_tool/quality_bench.py
  - plan_tool/cli/quality_bench_cmd.py
  creates:
  - tests/test_quality_bench_floor.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 4
  depends_on_notes:
    3: supplies the replay engine floor's R reruns drive
    4: supplies the quality-bench subparser/dispatch skeleton this action extends
  detail: docs/implementation-plans/plan-details/quality-bench-01-corpus-and-noise-floor/05-plan-tool-quality-bench-floor-rerun.md
- id: 6
  title: Add `plan-tool quality-bench compare` — print each metric's delta against
    its recorded floor as inside noise, outside noise, or unfloored
  intent: Lets an operator compare a candidate label against a baseline label without
    treating a bare delta as signal. For each metric, `inside noise` means its registered
    distance is less than or equal to the baseline's matching floor and `outside noise`
    means it is greater. The labels must share their frozen label-owned corpus-snapshot
    digest, replay identity, and canonical backend-profile digest, and the floor must
    also match the baseline label's full source execution identity. Compare selects
    one deterministic metric-registry version, current by default or explicit with
    `--metric-version`, and recomputes that version from every label and retained
    floor sample's raw evidence. By default it reads that identity's one current-floor
    record; an optional floor id selects one immutable matching record. It takes no
    mutation lock but uses the Architecture's bounded optimistic read snapshot before
    it classifies. A metric's explicit unfloored entry, every mismatch, or a missing
    floor is `unfloored` and excluded from the summary without changing an exit code
    or any existing gate.
  files:
  - plan_tool/quality_bench.py
  - plan_tool/cli/quality_bench_cmd.py
  creates:
  - tests/test_quality_bench_compare.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 4
  - 5
  depends_on_notes:
    3: supplies the persisted per-label metric store compare reads
    4: supplies the quality-bench subparser/dispatch skeleton this action extends
    5: supplies the persisted floor record each delta is classified against
  detail: docs/implementation-plans/plan-details/quality-bench-01-corpus-and-noise-floor/06-plan-tool-quality-bench-compare-print.md
- id: 7
  title: Document the quality-bench corpus/store schema in DATA_CONTRACT.md and TESTING.md,
    and correct BACKLOG
  intent: 'Records the versioned stored-label, full-corpus raw-sample, floor-record,
    current-floor-pointer, current-label-pointer, and replacement-journal schemas plus
    missing/unknown/invalid-reference reader outcomes in DATA_CONTRACT.md, adds
    plan_tool/quality_bench.py''s invoker seam to TESTING.md''s fallback table, and
    corrects BACKLOG #216''s initial assumption that bench was unclaimed to name the
    actually-shipped quality-bench verb, modules, and .plan-tool/quality-bench/ storage
    root, so a future reader doesn''t re-propose the collision.'
  files:
  - BACKLOG.md
  - DATA_CONTRACT.md
  - TESTING.md
  creates:
  - docs/QUALITY_BENCH_CORPUS_FORMAT.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  depends_on_notes:
    1: supplies the corpus manifest fields this doc describes
    2: supplies the metric names/definitions this doc and DATA_CONTRACT.md describe
    3: supplies the stored-label record shape DATA_CONTRACT.md documents
    4: supplies the invoker seam TESTING.md's fallback table gets a row for
    5: supplies the floor-record shape DATA_CONTRACT.md documents
    6: supplies the compare output shape this doc references
  detail: docs/implementation-plans/plan-details/quality-bench-01-corpus-and-noise-floor/07-document-quality-bench-corpus-store.md
---
# Quality Bench 01 Corpus And Noise Floor

## Overview

Adds a new `quality-bench` verb group (`run`, `compare`, `floor`) that measures deterministic behavior of the existing `roadmap` stage-2 route across code changes. `plan-tool quality-bench run --corpus <dir> --label <name>` replays a fixed, versioned corpus of self-contained inputs through exactly that stage, stores a label-owned input snapshot, every produced artifact, and its run log under `.plan-tool/quality-bench/`, and computes a finite predeclared deterministic registry from that evidence. `plan-tool quality-bench floor --corpus <dir> [--reruns <R>]` repeats the same corpus (default `R=3`, minimum 2) at one clean source revision and canonical backend-profile digest. `plan-tool quality-bench compare <baseline-label> <candidate-label> [--metric-version <V>]` replays no backend call: it recomputes one deterministic registry version from stored evidence and classifies each metric's distance against the matching baseline floor as `inside noise`, `outside noise`, or `unfloored`. It is reporting only. This is position 01 of the `quality-bench-NN` arc. It authors no later position and ships no LLM judge, rubric, quality opinion, calibration, behavioral gate, confidence behavior, or decision path.

## Problem statement

Nobody currently knows what any of plan-tool's candidate quality metrics do when nothing changes at all. A 2026-08-01 measurement on `roadmap` stage 2 — three runs on byte-identical input (`prompt_bytes = 33942` in every run) — found wildly different rerun behavior per dimension: quality-attribute dispositions were 7 of 7 identical across all three runs, constraint row ids shared only 1 of 19 between two runs, and gate attempts consumed went 3, then 1, then 1. A benchmark that scored 'constraint set quality' across a code change would report a large delta caused by nothing; one that scored disposition ranking would be reading real signal — and the only way to tell which metric is which is to rerun the corpus against an unchanged tree and measure. This repo already paid for skipping that step: BACKLOG #164's one-off mechanism falsification check was cut on 2026-07-29 after roughly 29% of findings across ten audit rounds traced back to it or its `--bundle-framing` control, because at n=1 sampler variance swamped the signal and the check gated nothing. This plan is the missing prerequisite #164 lacked — establishing each metric's noise floor before any comparison is trusted.

## Architecture

The determinism ladder is climbed in stage order, not all at once: position 01 computes only registry-v1 metrics decidable from stored artifacts by code. No rubric, scoring prose, or model sits in the measurement path. This plan publishes no decision, gate, calibration, or confidence behavior.

Registry v1 has exactly these per-item metrics. Items are ordered by manifest item id; a label's corpus value is that ordered vector, and a corpus distance is the maximum of its item distances. Numeric-vector distance is the maximum absolute component delta, a set distance is the symmetric-difference count, and an enum/boolean distance is zero when equal and one when different. A value unavailable because the stage wrote no artifact or the run log lacks the field is explicit `unfloored`, not a substitute value.

| Metric | Per-item encoded value | Purposeful distance |
| --- | --- | --- |
| `artifact_bytes` | byte count of `02-constraints.md` | absolute byte-count delta |
| `row_counts` | `(dispositions, constraints, decisions)` row counts | numeric-vector distance |
| `constraint_ids` | sorted constraint-row id set | set distance |
| `domain_reference_counts` | `(resolved, declared)` over every constraint `anchor_ids` occurrence plus every decision `anchor`; repeats count, and `resolved` is membership in the stored domain's entity, business-rule, or workflow ids | numeric-vector distance |
| `required_section_presence` | booleans that the raw YAML frontmatter mapping contains list-valued `dispositions`, `constraints`, and `decisions` collections, not prose headings | boolean-vector distance |
| `frontmatter_present` | whether the selected output's first non-BOM line is the required `---` frontmatter fence | boolean distance |
| `roadmap_gate_attempts` | count of `claude_call_start` records for phase `stage-2-constraints` in the stored run log | absolute integer delta |
| `exit_outcome` | stored `RoadmapResult.outcome` enum | enum distance |
| `wall_time_ms` | `phase_end.duration_ms` for `stage-2-constraints` in the stored run log | absolute integer delta |
| `cost_usd` | sum of every non-null `claude_call_end.cost_usd` for phase `stage-2-constraints`; unavailable if no such end exists or any end has null cost | absolute numeric delta |

Each corpus item is a complete replay input, not an ambient repository reference. The selected `--corpus` path must strict-resolve to a directory used as the corpus root; every discovered item directory and its `manifest.json` must in turn strict-resolve beneath that root, so neither an item nor its manifest can escape through a symlink. Its v1 manifest stores JSON-integer `format_version: 1`, a corpus-unique item id matching `[a-z0-9][a-z0-9._-]{0,127}`, roadmap slug, and target stage 2; a missing, non-integer, or unsupported format version and an empty, unsafe, or duplicate id are rejected before materialization. The unique id orders every metric vector and names its stored evidence. Item-relative files supply the concept brief, `01-domain.md`, and `.roadmap-baselines/domain.json`: every declared file reference is nonempty and relative with no `..` component, and its strict resolved target, including through a symlink, must remain beneath that resolved item directory. An absolute, missing, traversal, or escaping target invalidates the item before materialization or an invocation. The runner copies those files to the scratch roadmap tree, supplies the brief path to `run_roadmap`, passes the stage prefix through stage 2, and sets `from_stage=2`. The existing runner therefore admits and re-gates stage 1 before it selects stage 2, while no stage 3 or 4 is present to run. One replay is that one selected-stage run, not one backend attempt: the existing stage retry policy stays intact and the recorded attempt metric counts its actual attempts. Missing or invalid brief, artifact, or baseline data invalidates that corpus item rather than silently falling back to a full run.

`roadmap_slug` is validated before any scratch roadmap path is formed: it is a nonempty string with no `/`, `\\`, or `..` component and `Path(slug).parts == (slug,)`, the same single-component rule `roadmap_artifacts.roadmap_dir` enforces. Invalid slugs reject corpus preflight rather than relying on later `run_roadmap` validation.

Replay isolation is explicit at the production invoker boundary. The engine enters `backend.spawn_cwd(scratch)` around each `run_roadmap` call, so every backend attempt receives the materialized item tree as its working directory; it receives neither another item's files nor the live quality-bench store as declared context. Tests assert that scope at the invoker and subprocess boundary. This is a replay-context boundary, not a new operating-system sandbox or a change to the roadmap command.

Artifacts are the record, scores are recomputed: before a run starts any item, it validates the complete corpus and takes one private byte snapshot of every item manifest and declared input, then derives the corpus digest from that exact snapshot. From that same clean preflight it pins the full source execution identity and resolved backend profile. Every scratch item materializes only from those bytes; the engine never rereads the external `--corpus` path during the item loop, so a mid-capture corpus edit cannot mix into a label. Immediately before and after every scratch item replay, and again before label publication, it recomputes the source identity and backend profile and requires exact equality with that pin. A clean committed source or prompt update, loaded-root change, or backend-profile change therefore discards all private capture data and preserves an old label and archive generation instead of mixing identities. On successful publication, a run stores that label-owned complete corpus snapshot, every produced file, run log, and serialized `RoadmapResult` facts under `.plan-tool/quality-bench/`. That root is ignored runtime evidence, so it does not make a source checkout dirty; an initially clean source checkout can run and then floor without mutating its tracked source identity. Before every `run` scratch item, before each `floor` sample, and immediately before either command publishes evidence, `working_tree_dirty(repo_root)` must be false. Any tracked or unignored change, or an unreadable git state, refuses the operation; the command discards private temporary capture data and leaves an old label, archived generation, floor record, and current pointer unchanged. The ignored quality-bench store itself is the only allowed runtime dirt. Before `run` or `floor` does either, it resolves the requested repo root, the loaded `plan_tool` package root from `plan_tool.__file__`, and the loaded prompt root from `prompts_dir()`. Both loaded roots must resolve beneath that requested checkout exactly where its `plan_tool/` package and `plan_tool/prompts/` directory live; otherwise the command refuses before scratch materialization or store writes. A label therefore records the actual root, clean git commit, a SHA-256 code digest and prompt digest formed by hashing each allowed source file's UTF-8 relative path and bytes in lexical path order, its corpus digest, replay descriptor (including target stage and attempt configuration), captured registry-v1 projection, and resolved backend name, model configuration, and backend version. The code set is loaded `plan_tool/**/*.py`; the prompt set is loaded `plan_tool/prompts/**/*.md`. The actual root is provenance only: source equivalence uses the clean commit plus code and prompt digests, not an absolute checkout path. The throwaway scratch commit exists only to give the replay a clean working tree and is never recorded as the source revision. Metrics are computed from the label-owned evidence, and a compare selected registry version recomputes both labels and every retained floor sample from that immutable evidence. A later deterministic metric version can therefore analyze historical labels and floor samples without reading a changed corpus checkout; storing only scores would make the corpus un-reanalyzable.

V1 corpus enumeration and snapshot encoding are shared parser contracts, not caller choices. The resolved corpus root contributes its non-hidden immediate child directories only, sorted by UTF-8 name; every such directory must be a contained item with one contained `manifest.json`. The snapshot contains that ordered item set's manifests and declared resolved input files, sorted by lexical POSIX-relative path. Its digest is SHA-256 over the ASCII domain separator `quality-bench-corpus-v1\0`, then for each path/value record an unsigned 64-bit big-endian byte length, the UTF-8 POSIX-relative path bytes, an unsigned 64-bit big-endian byte length, and the raw value bytes. The implementation publishes a golden snapshot-to-digest vector. Validation, materialization, evidence storage, and floor recomputation all consume those same snapshot bytes.

The exact root-anchored `.gitignore` entry `/.plan-tool/quality-bench/` is part of this evidence contract. Every source-dirt preflight and recheck for `run` and `floor` uses the normal git-status predicate against that rule: the quality-bench store is clean runtime evidence, while any other tracked or untracked path is dirt. Tests exercise the actual predicate with the store and with a sibling under `.plan-tool/`, not an ad hoc test-only exclusion.

A backend profile is one canonical digest, not a label. Its canonical JSON body includes the already-recorded backend name, backend version, and resolved model; hashes of the effective batch and streaming argv templates generated with one fixed prompt sentinel after ordered project `extra_batch_argv` and `extra_streaming_argv` are applied; the resolved rate-limit action plus fallback-backend selection; and the effective configured call deadline and silence deadline, each stored as either `null` or the exact positive-float `hex()` seconds value. Before a capture, the engine resolves both deadline values once and scopes every replay attempt to those captured values, so a changed `PLAN_TOOL_CLAUDE_TIMEOUT` or ambient timeout scope cannot alter a capture midstream. The stored profile has safe display fields and this SHA-256 digest, never the raw potentially sensitive arguments. Every label, floor sample, floor pointer, and compare matching rule uses exact profile-digest equality; changing any of those behavior-affecting inputs invalidates a floor match rather than changing its meaning.

Recovery is part of a capture's backend identity. Although an ordinary `run_roadmap` attempt enters `backend.spawn_cwd(scratch)`, quality-bench passes a capture-specific recovery-policy seam through its roadmap invoker into `shell.claude_invoke` before the rate-limit loop chooses a reinvocation. The seam retains the selected effective backend and its project configuration from the pinned requested repo root for every allowed retry and permits only a wait on that profile. Its attempt record contains the actual backend-profile digest. Every fallback or interactive switch selection is refused by that seam before `_select_rate_limit_backend`, an interactive menu, or another backend invocation, including a selection that would resolve to the same digest or one selected through the scratch root; it never writes a mixed-profile label or floor. Waiting and retrying the same pinned profile remains allowed.

Every persisted quality-bench envelope has `schema_version: 1` and one closed `record_kind` — `label`, `raw-sample`, `floor-record`, `current-floor-pointer`, `current-label-pointer`, or `label-replacement-journal`. A `raw-sample` is one complete corpus rerun under `(floor_id, sample_ordinal)` with every item held in a manifest-id-keyed map; it is not one envelope per item. A current-label pointer carries its target `capture_id` and immutable capture digest, while a replacement journal carries old/new capture ids and digests plus its reserved archive slot. Readers verify those references before following or recovering them; missing, boolean, malformed, or unknown versions and kinds, an invalid pointer target, or an invalid journal are unsupported evidence, never inferred or upgraded. `compare` and registry recomputation refuse such selected evidence before a classification, while intact version-1 labels and raw samples remain re-analyzable by later deterministic registry versions.

Label names are evidence identities, not overwrite slots. A label must use the same lower-case safe-key pattern as an item id, and every key-derived path is resolved and asserted beneath `.plan-tool/quality-bench/` before use. Every complete label capture is an immutable `capture_id` generation, and the logical label resolves one atomically replaced versioned current-label-pointer to that generation; a current-floor pointer similarly includes its selected immutable `floor_id` and record digest. `floor_id` is generated by the tool with the same safe form, and an explicit `--floor-id` is validated before lookup. The mutable `run` and `floor` engine entrypoints own exactly one `repo_mutation_lock` for their full read-check/archive/publish lifecycle; CLI dispatch deliberately does not acquire a second lock, and `compare` never acquires one. Under that engine-owned lock, the floor writer reserves an absent final floor-record path when it publishes; an existing generated id makes it allocate another safe id, never replace an immutable record or retarget any pointer. A second `run` for an existing label fails without `--force`. With it, the engine validates and privately stages the new immutable generation, writes a versioned durable replacement journal with the old/new capture ids and digests plus the first free numbered `.replaced.N` archive slot, publishes that complete generation and a pointer to the complete old generation at the reserved archive slot, then atomically advances the integrity-checked current-label pointer. On a later engine lock acquisition, a valid journal whose current pointer has not advanced finishes that transition; an incomplete or invalid new generation leaves the old current pointer selected and only private data is discarded. A crash at any boundary therefore leaves the old complete generation selected, the new complete generation selected with the old archive readable, or a recoverable journal—never an absent or partial logical label. Incomplete captures remain private temporary data and never occupy a label. Both paths are reported and tested; `compare` is read-only.

`compare` takes no mutation lock, but it must read one coherent evidence snapshot. On at most three optimistic attempts, it reads and verifies the baseline and candidate current-label pointers, resolves their immutable capture generations and the current or explicit floor marker, loads only that retained evidence, then rereads every label pointer, generation marker, selected floor record, and current pointer when used. It classifies only if every marker and pointer is byte-identical across that attempt; otherwise it discards the read and retries. Exhaustion reports one concurrent-publication error with no partial classification or summary. A `run --force` archive/replacement or a floor-pointer replacement therefore yields either the generation set before it, the set after it, or no result — never a mixture.

Every metric ships with its noise floor or it does not ship. A metric definition supplies a deterministic encoded value and distance function; a floor is the maximum pairwise distance observed across R >= 2 complete reruns at one pinned capture identity. `floor --corpus <dir>` uses that exact manifest and defaults to three captures; `--reruns` must be at least two. A compare delta is evaluated by the same distance: a value less than or equal to the floor is `inside noise`, and one greater than the floor is `outside noise`. A missing value creates an explicit `unfloored` entry; an incomplete rerun set publishes no floor record.

A floor run has an immutable `floor_id`, owns its R complete full-corpus raw-sample captures keyed by sample ordinal, and binds them to the corpus digest, replay descriptor, source execution identity, canonical backend-profile digest, and R. Before sample one, from a clean source preflight, it records those four identity components as the expected identity. Immediately before and after each capture, and again before it publishes a raw-sample record or current pointer, it recomputes the current corpus digest, replay descriptor, full source execution identity, and backend-profile digest and requires exact equality with that expected identity and with the sample's recorded metadata. Any mismatch discards all unpublished samples and changes neither an earlier immutable record nor the current pointer. After all R captures complete, the registry-v1 coverage map contains either each measured floor or an explicit `unfloored` reason for a missing value; that complete record atomically becomes the exact identity's one current-floor pointer. A run interrupted before R captures completes does not publish a record or change that pointer; a replacement leaves the earlier immutable floor and samples readable. `plan-tool quality-bench compare <baseline-label> <candidate-label> [--metric-version <V>]` requires matching corpus and replay identities plus canonical backend-profile digest between labels and, by default, selects the current deterministic registry version and the current pointer whose source identity matches the baseline label. An optional `--floor-id` selects one immutable matching record instead. It recomputes the chosen version from both label evidence and the selected floor's full-corpus raw samples; a version that cannot compute a metric has an explicit `unfloored` result, never a fallback to an older projection. The candidate may represent a different source revision and prompt/code digest. Incompatible labels, an unmatched explicit floor, or a missing pointer also yield `unfloored` for that metric. The command prints the chosen registry version and floor id, never refreshes a floor, chooses a winner, blocks execution, or changes an existing gate.

The corpus is fixed, versioned, and small: seeds live in the corpus directory and change only by an explicit, committed edit, since a corpus that drifts silently makes every historical label incomparable. Each label freezes the complete input snapshot it actually used before replaying an item, rather than trusting a mutable external corpus path. It stays small because each item costs a real Claude run (the roadmap smoke run was ~$2.50 and ~6 minutes for two stages), so the corpus is sized to the floor it can afford to measure (R reruns × N items) rather than to coverage.

Replay isolation: each corpus item runs against its own empty scratch repo, so items cannot see each other's output and no metric reflects the order items ran in.

This answers a monitoring question, not a decision question (`docs/NONDETERMINISM_PLAN_DESIGN.md` Rule 6's fork): is the chosen path healthy, and did this commit move it — floors and trends over the corpus — not a controlled-arm choice between two futures, which is the shape that was cut and would need its own separate justification.

## References

- [json — JSON encoder and decoder — Python documentation](https://docs.python.org/3/library/json.html) — Standard-library reference for parsing each corpus item's `manifest.json` (step 1) and for encoding/decoding the label-keyed stored-run envelope the replay engine persists under `.plan-tool/quality-bench/` (step 3).
- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Covers the frozen-record shape the deterministic metric registry (step 2) mirrors from `plan_tool/roadmap_gates.py`'s `check_*` functions, and the floor/compare result records steps 5 and 6 add.
- [tempfile — Generate temporary files and directories — Python documentation](https://docs.python.org/3/library/tempfile.html) — Covers the isolated per-item scratch-directory creation the replay engine uses so each corpus item runs against its own empty scratch repo (step 3), mirroring `plan_tool/bench.py`'s existing scratch-repo-init shape.
- [argparse — Parser for command-line options, arguments and sub-commands — Python documentation](https://docs.python.org/3/library/argparse.html) — Reference for wiring `quality-bench run`/`floor`/`compare` as their own subparser group (step 4), kept namespaced separately from the existing `bench` verb group.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- No LLM judge, rubric, or model-scored metric of any kind. No position-02 plan or seed is authored here.
- No quality opinion — no metric may assert that an artifact is good, better, well-grounded, or well-reasoned; every metric is a count, a ratio, a resolution check, or a stability measure over bytes.
- No agreement check between two prose artifacts — not seed-vs-plan, not plan-vs-detail, not artifact-vs-brief; this is the specific shape CLAUDE.md's rule 5 says to kill rather than tune.
- No gate, no exit-code flip, no CI blocking — `quality-bench` reports; a completed run exits 0 whatever the numbers say, per the exit-code convention.
- No control arms, matched baselines, or A/B comparison of two prompt variants — that is the cut #164 mechanism; re-proposing it is separate work that must first show it has the power this position's floors would reveal.
- No auto-tuning — nothing reads a metric and adjusts a threshold, prompt, or default.
- No expansion of the corpus to every verb — one verb, one corpus, this position.
- No shape or length caps on any artifact, as a metric or otherwise.
- No parallel fan-out to make the corpus faster (CLAUDE.md's anti-parallelism directive) — if a corpus is too slow, it is too big.

## Risks

- Metrics may be dominated by noise rather than signal: after each first complete floor for a corpus/source/profile identity, the operator who invoked `floor` reviews that floor id's per-metric table and raw samples. If they conclude that most registry-v1 floors are too wide to distinguish the intended change effects, they record the dated evidence and smaller-claim/defer conclusion in BACKLOG #216 rather than widen the corpus or author a later position. This is a manual review obligation, not an automatic threshold, warning, exit-code change, or gate.
- A specific verb's own rerun variance (e.g. the `roadmap` retry budget question, closed 2026-08-05 with no action per `docs/HISTORICAL_BACKLOG_DECISIONS.md`) is out of this plan's remit; surfacing such a gap here rather than routing it to that verb's own backlog entry risks misattributing a verb-specific issue to the benchmark itself.

## Testing

A corpus of two self-contained stage-2 items, replayed R >= 2 times at one clean source revision with a stubbed invoker, proves that each scratch replay supplies its brief, stage-1 artifact, and baseline, selects stage 2 once while preserving its existing retry attempts, and never selects stages 3 or 4. Each item manifest must contain JSON-integer `format_version: 1`; missing, boolean, non-integer, or unsupported values fail during corpus preflight before any replay. Empty, upper-case, path-like, overlong, and duplicate manifest item ids fail before any replay, while distinct safe ids give vector ordering and root-contained per-item evidence paths. The selected corpus root, every discovered item directory, and every item manifest must strict-resolve beneath that root; symlinked items or manifests that escape reject before an invocation. Every declared corpus-file reference rejects an absolute path, `..` traversal, missing target, or symlink whose resolved target escapes its item directory before an invocation. A test mutates the external corpus after the first item begins and proves that every item still materializes from the pre-loop byte snapshot, whose digest and retained label input remain one coherent corpus. Missing or malformed context fails the item before an invocation. Tests assert `backend.spawn_cwd` gives each production-equivalent invoker and subprocess the scratch root, not the live checkout or another item. A tracked edit, unignored untracked file, or unreadable git state makes `run` and `floor` refuse before an invoker, archive, label, sample, or pointer mutation; dirt introduced during capture also prevents publication and preserves earlier evidence. A clean committed code or prompt change, an imported-root change, or a resolved backend-profile change between label items likewise fails the pinned identity recheck, discards the private label, and preserves an earlier label/archive generation. Floor tests independently vary the corpus digest, replay descriptor, source execution identity, and resolved backend profile between R samples, and prove that every mismatch discards the unpublished sample set and preserves the earlier immutable record and current pointer. The ignored runtime store permits an end-to-end `run` then `floor --corpus <dir>` sequence from one initially clean checkout; `--reruns` defaults to three and rejects one. A mismatched `--repo-root`, imported package root, or prompt root refuses before a capture, while a matching checkout records its actual code and prompt digests and two matching clones have equal source identity despite different absolute paths. Registry-v1 fixtures cover every named metric's exact stored-evidence value and distance, including repeated anchors, YAML-collection presence rather than prose headings, retry-call cost aggregation, and max-per-item corpus aggregation. A metric that is constant across reruns floors at zero; deliberately varying one stub item produces its registered maximum pairwise distance. Tests prove the exact boundary: a delta equal to the floor is `inside noise`, and a greater delta is `outside noise`. Unsafe labels or an unsafe explicit floor id fail before any store access; the same label cannot race because `run` and `floor` hold the repo mutation lock through collision check, numbered `--force` archive, and atomic replacement, while `compare` takes no mutation lock. A label preserves a byte snapshot of its input plus the output, run log, serialized result facts, source execution identity, and recomputable metrics; collision fails without `--force`, while `--force` creates the next preserved replaced generation. A complete R-capture floor record atomically becomes the identity's current pointer and records every metric as either a numeric floor or explicit `unfloored`; an interrupted capture leaves that pointer unchanged, and default compare never falls through from a current explicit `unfloored` metric to an earlier floor. A synthetic registry-v2 metric recomputes both old labels and a retained floor's raw samples without a backend call; compare selected with that version prints it and uses its rederived floor. `plan-tool quality-bench compare` on labels with matching corpus/replay and backend profile plus a matching baseline floor reports every metric `inside noise` and prints its registry version and floor id; corpus/replay identity mismatch, backend-profile mismatch, absent floor, explicit nonmatching floor id, and a metric the selected version cannot compute are `unfloored` and absent from any summary. After the first complete floor, its invoking operator reviews its raw evidence and files a dated #216 outcome only when most registry-v1 floors cannot distinguish intended effects; this review has no code gate or changed exit behavior. Hermetic per TESTING.md — the harness takes the same `invoker=` seam every orchestrator does, and no test spawns a real backend.

Corpus tests prove direct-child enumeration is independent of filesystem traversal order, nested directories are not items, and the stored snapshot list plus the exact domain separator and unsigned-64-bit big-endian framing produce the golden digest. They exercise `/.plan-tool/quality-bench/` through the actual source-dirt predicate and prove a sibling untracked path still fails it. Profile fixtures independently vary an ordered batch or streaming extra argument, resolved model, rate-limit action, fallback backend, configured call deadline, and silence deadline; each changes the canonical profile digest and prevents label/floor/compare identity matching. They also change `PLAN_TOOL_CLAUDE_TIMEOUT` or an outer timeout scope during a replay and prove the preflight-frozen captured deadline still governs every attempt. Compare tests interleave its marker-read seam with `run --force` label replacement and current-floor-pointer replacement: it either retries to one coherent marker set or emits the single concurrent-publication error, never a mixed classification or summary.

Recovery tests force a rate-limit switch selection while the scratch root carries different project backend settings and prove the capture recovery seam refuses it before `_select_rate_limit_backend`, an interactive selection, or another backend invocation; they also force a switch that resolves to the same profile and prove it stops. A same-profile wait/retry records the same actual digest on every attempt. Every label, full-corpus raw sample, floor record, current-floor pointer, current-label pointer, and replacement journal is tested with `schema_version: 1`, its closed kind, and valid referenced digest; missing, boolean, malformed, future, or invalid-reference evidence fails closed before recomputation/classification while intact v1 evidence re-analyzes under registry v2. Raw-sample tests retain exactly R `(floor_id, sample_ordinal)` envelopes, each with the whole manifest-id-keyed item map. Corpus tests reject an empty, separator-bearing, or `..`-bearing roadmap slug before a scratch path exists. Engine-lock tests prove direct and CLI `run`/`floor` acquire exactly one lock while `compare` acquires none. A forced generated floor-id collision leaves the existing record and pointer digest intact, assigns another safe id to the new complete record, and never permits an overwrite. Forced-label-replacement fault injection at private staging, journal creation, new-generation publication, archive-pointer publication, current-pointer advance, and journal cleanup proves recovery either keeps the complete old generation selected or completes the valid transition with its archived old generation readable; no lookup observes an absent or partial label.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- The v1 corpus item set is exactly the resolved root's non-hidden immediate child directories sorted by UTF-8 name. A label's canonical snapshot is exactly the manifests and declared input files from that set, sorted by lexical POSIX-relative path. Its corpus digest is SHA-256 over ASCII `quality-bench-corpus-v1\0`, then each UTF-8 relative path and raw byte value framed by its unsigned 64-bit big-endian byte length; a golden vector locks that result. `/.plan-tool/quality-bench/` is the sole ignored runtime-evidence root across the `run`/`floor` dirt checks; a sibling untracked path remains a rejection.
- Every quality-bench retry remains on the effective backend profile pinned from the requested repo root and records that actual profile digest, including frozen configured and silence termination deadlines. Every fallback or interactive switch selection, including one with the same eventual profile or one resolved from `backend.spawn_cwd(scratch)`, discards the private capture before a label, sample, record, or pointer publication; only an unchanged-profile wait/retry remains valid.
- Every label, full-corpus raw-sample, floor-record, current-floor-pointer, current-label-pointer, and label-replacement-journal envelope has exact `schema_version: 1` and its closed record kind. A raw sample is keyed by floor id and sample ordinal and holds a manifest-id-keyed item map; a label pointer and journal carry their capture targets and integrity digests. Missing, malformed, boolean, unknown, or invalid-reference evidence fails before recomputation, recovery, or classification; retained v1 evidence remains readable for later deterministic registry versions.
- `--force` replacement stages and validates an immutable new capture before it can change a logical label. Under the engine-owned mutation lock it journals old/new capture ids and digests plus a first-free `.replaced.N` archive slot, makes both complete generations reachable, and atomically advances the integrity-checked current-label pointer last. Recovery resumes a valid journal or keeps the prior current capture selected; every lookup sees a complete old or new generation, never an absent or partial label.
- A manifest `roadmap_slug` is a nonempty single path component with no separator or `..` component, validated before a scratch roadmap path or invocation. `run` and `floor` acquire exactly one engine-owned repository mutation lock; CLI dispatch does not acquire another and `compare` remains unlocked and read-only.
- `plan-tool quality-bench run --corpus <dir> --label <name>` rejects an empty, unsafe, or duplicate manifest item id and an unsafe label before replay or store access, then strict-resolves the selected directory as the corpus root and validates every discovered item directory and item manifest remains beneath it. Each manifest requires JSON-integer `format_version: 1`; a missing, boolean, non-integer, or unsupported version rejects during corpus preflight. The command then validates and freezes one complete byte snapshot of every manifest and declared corpus file. Every declared corpus-file reference must be nonempty, relative with no `..` component, and resolve strictly beneath that item directory, including through symlinks; absolute, missing, traversal, or escaping references reject before replay. The command materializes every uniquely keyed item in an isolated scratch repo only from that snapshot, so an external corpus edit during the item loop cannot enter the label. From the same clean preflight it pins the loaded-root-matched full source execution identity and canonical backend-profile digest. Immediately before and after every item replay and before label publication, those source and backend values must still equal the pin; a clean committed source or prompt change, loaded-root change, or backend-profile change discards private capture output and preserves the old label/archive generation. It supplies the brief and admitted upstream context, selects only the named roadmap stage while preserving its existing retry behavior, scopes every backend invocation to that scratch root, and stores that label-owned input snapshot, every produced artifact, run log, and serialized result facts under `.plan-tool/quality-bench/`. Every derived path remains beneath that root. A dirty or unreadable selected source tree refuses before materialization and again before publication, discards temporary output, and preserves the old label/archive generation. It also refuses when the selected checkout differs from the actual imported package or prompt roots; otherwise the label records the actual root, clean commit, code/prompt digests, corpus/replay identity, canonical backend-profile digest, and recomputable deterministic metrics. `run` holds the repo mutation lock through collision check, `--force` archive, and atomic replacement; collision fails unless `--force` first preserves the old generation under a numbered replaced path.
- `plan-tool quality-bench floor --corpus <dir> [--reruns <R>]` selects exactly that versioned corpus, defaults `R` to 3, rejects values below 2, and requires R complete reruns at one clean, loaded-source-matched execution identity. From a clean preflight before sample one it pins the corpus digest, replay descriptor, full source execution identity, and canonical backend-profile digest; it verifies those components immediately before and after every capture and before publication. Dirt, an unreadable git state, or any identity mismatch discards every unpublished sample and leaves the immutable record and current pointer unchanged. It holds the repo mutation lock through raw-sample and pointer publication, and persists an immutable raw-sample floor record with the corpus/replay identity, actual source identity, canonical backend-profile digest, and R. Its registry-v1 coverage map has one entry per named metric: the maximum pairwise registered distance, or an explicit `unfloored` reason when a required value is missing. Only that complete R-capture record atomically updates one current-floor pointer; an interrupted capture leaves it unchanged. Final floor-id reservation is collision-safe under that lock: a generated collision selects another safe id and preserves all existing immutable records and pointer targets.
- `plan-tool quality-bench compare <baseline-label> <candidate-label> [--metric-version <V>] [--floor-id <id>]` validates label and explicit floor keys before lookup, remains read-only, and uses the matching current or explicit immutable baseline floor to recompute the selected deterministic registry version from both labels and the floor's raw samples. It reports each metric's distance to label equality with the floor `inside noise` and a larger distance `outside noise`, and prints the selected registry version and floor id. It reports `unfloored` when the frozen label-owned corpus-snapshot digest, replay identity, canonical backend-profile digest, or selected floor is absent or incompatible, when the selected version cannot compute the metric, or when that record explicitly marks it unfloored; it never falls back to an older metric projection. It uses at most three marker-verified optimistic reads; a concurrent replacement that cannot stabilize uses ordinary command-error handling with no partial classification or summary. A candidate source revision may differ from its baseline. A completed comparison changes no exit code or existing gate.
- Deleting a label's computed metrics and recomputing them from the stored artifacts reproduces the original values exactly.
- After the first complete floor for one corpus/source/profile identity, the invoking operator reviews that floor id's raw evidence and per-metric table. If most registry-v1 floors cannot distinguish intended effects, the operator records a dated smaller-claim/defer outcome in BACKLOG #216. This is a manual review, never an automatic gate, warning, exit-code change, or basis for a later position.
- The harness is hermetic: it takes the same `invoker=` seam as every other orchestrator, and no test spawns a real backend (per TESTING.md).
- `BACKLOG.md` updates the existing BACKLOG #216 anchor when this plan ships; that bookkeeping authors no future position.

## Deferred

- Any future model-scored metric, rubric, calibration, decision rule, or confidence behavior — outside this plan. No position-02 seed or plan is authored until a separately selected effort uses this floor table.
- Corpus coverage of verbs other than `roadmap` — postponed to a later position in the arc; this position's corpus is sized to what R reruns can afford for one verb, so widening coverage needs its own affordability check first.
