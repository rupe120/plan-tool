> **Withdrawn 2026-08-28** — A disposable current-model observation must establish the need for a durable replay surface before a runner, persisted record, CLI, or documentation is authorized.
> Preserved here for history; do not edit.

---
title: Quality Bench 01 Corpus And Noise Floor
intent: 'Prove whether one fixed two-item `roadmap` corpus can yield a reviewable
  deterministic noise-floor table: run the corpus serially at least twice from one
  pinned execution identity, retain the raw evidence, and publish one version-1 floor
  record with each metric''s maximum same-item pairwise spread. This is the smallest
  proof of floor feasibility, not a reusable benchmark or an interpretation layer.'
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
  title: Define the fixed two-item stage-2 corpus and the version-1 floor record from
    canonical artifacts and run logs
  intent: Makes repeated runs comparable by freezing two inputs and defining byte
    length, constraint-id count, and a stage-2 invocation count before replay begins.
    That count is the number of retained `claude_call_start` records carrying
    a `stage` field equal to 2, whether their invocation succeeds or fails; a replay that cannot
    finish stage 2 remains an unpublished sample rather than a floor value. The floor
    for each metric is its maximum absolute difference across unordered completed-rerun
    pairs of the same corpus item.
  creates:
  - plan_tool/quality_bench_contract.py
  - benchmarks/quality-bench/corpus/roadmap-stage-2/corpus.json
  - benchmarks/quality-bench/corpus/roadmap-stage-2/item-1/brief.md
  - benchmarks/quality-bench/corpus/roadmap-stage-2/item-1/01-domain.md
  - benchmarks/quality-bench/corpus/roadmap-stage-2/item-1/.roadmap-baselines/domain.json
  - benchmarks/quality-bench/corpus/roadmap-stage-2/item-2/brief.md
  - benchmarks/quality-bench/corpus/roadmap-stage-2/item-2/01-domain.md
  - benchmarks/quality-bench/corpus/roadmap-stage-2/item-2/.roadmap-baselines/domain.json
  - tests/test_quality_bench_contract.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Replay only stage 2 serially in fresh staging, retain its artifact and run
    log, then remove staging and create the selected output without replacement
  intent: Produces one inspectable floor table from one frozen corpus snapshot while
    rejecting source-state, effective-backend, failed-replay, and interrupted-run
    mixtures. It reads the frozen stage-1 input but invokes only stage 2; it uses one
    captured transport with no fallback selection, and retains the raw event stream
    only in private staging until publication. It never rereads the external corpus
    after the snapshot, so a later corpus edit cannot enter a sample; it also rejects
    `--reruns` below 2 before staging or output-path access.
  files:
  - TESTING.md
  creates:
  - plan_tool/quality_bench.py
  - tests/test_quality_bench.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the validated corpus snapshot, raw-evidence shapes, fixed metric vocabulary,
      and version-1 record renderer.
- id: 3
  title: 'Add the separate quality-bench floor command, document its fixed proof contract,
    and reconcile BACKLOG #216'
  intent: Gives operators one factual floor command, keeps the existing bench command
    unchanged, and leaves position 02 unauthored until the evidence is reviewed.
  files:
  - BACKLOG.md
  - CAPABILITIES.md
  - CLAUDE.md
  - README.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  - plan_tool/cli/__init__.py
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - tests/cli/package_surface_help.golden.txt
  - docs/cli/README.md
  creates:
  - plan_tool/cli/quality_bench_cmd.py
  - tests/cli/test_quality_bench_cmd.py
  - docs/cli/quality-bench.md
  - QUALITY_BENCH_FORMAT.md
  - tests/test_quality_bench_format.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Supplies the landed schema and metric names that the format and command references
      document.
    2: Supplies the serial floor runner invoked by the new CLI handler.
---
# Quality Bench 01 Corpus And Noise Floor

## Overview

This is position 01 of BACKLOG #216's quality-bench arc. Its only question is whether repeated, unchanged `roadmap` inputs produce a small enough deterministic spread to justify later benchmark work. It measures bytes and recorded execution facts; it does not say whether an artifact is good or whether a later change helped.

## Problem statement

The current baseline lacks an observed floor for even a small representative set of deterministic roadmap measurements. Without that table, a later comparison, calibration, or judged metric would assign meaning to a delta without knowing whether unchanged inputs already produce it. A first proof needs evidence that a floor can be measured and inspected, not the product surfaces that might consume it later.

## Architecture

The corpus, execution identity, and metric vocabulary are fixed before replay. The runner captures one corpus-byte snapshot, materializes every rerun only from it, and records its digest; an external corpus edit after capture cannot enter the output. The source identity is the resolved `HEAD` SHA plus a clean working tree, and the runner rechecks both before every replay and before publication. The backend identity is a SHA-256 fingerprint of the canonical selected stage-2 command transport—its argv without the per-run prompt and its prompt channel—after its model and project arguments are applied. Every attempt runs within that captured transport; an attempted fallback or reselection fails the replay rather than mixing commands. A failed source check refuses the run before publication. `--reruns` is an integer of at least 2 and rejects before staging or output-path access.

Each serial replay passes `run_roadmap` a local two-row stage table and starts at stage 2: the frozen stage-1 artifact is admitted as input, stage 2 is the only invoked stage, and no stage-3-or-later call belongs to the floor run. The existing `invoker=` seam receives the captured transport; its optional fake remains the only test route, and no test calls a live backend. A private `RunLogWriter` rooted in replay staging receives the raw event stream; the completed record embeds the required raw stage-2 events, then staging is removed, so a floor run writes no log under the repository's `.plan-tool/runs` directory. All source checks, replay validation, and staging cleanup finish before publication. The runner writes the complete record to a fully fsynced sibling temporary and uses the existing no-clobber `os.link` publication pattern; an existing or late-created caller-selected path raises a refusal and remains byte-for-byte unchanged. That link is the completion boundary: interruption before it leaves no record, while an interrupt after it leaves the complete, self-contained record intact. The runner never selects a record by label, replaces it, recovers it, compares it, or reads it as a current generation.

The three measurements are deliberately a narrow proof set. Each metric's one floor is the maximum absolute difference between values from two completed reruns of the same corpus item, taken across every unordered rerun pair and both items. This covers retained artifact bytes, a structured artifact fact, and a recorded execution fact without adding a rubric, a statistics surface, or an extensible metric-registry product. A later proposal may add a metric only after this record exists and is manually reviewed; it does not join this position by implication.

The source entry is BACKLOG #216. The resulting plan must update that entry on shipment so its position-01 description matches this proof boundary while preserving the arc anchor and the unauthored position-02 fence.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Covers nested subparsers and argument validation for implementing the quality-bench floor command.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Documents SHA-256 and file hashing for freezing and rechecking the corpus digest.
- [tempfile — Generate temporary files and directories](https://docs.python.org/3.13/library/tempfile.html) — Covers secure temporary directories and files for isolated replay staging and cleanup.
- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Documents link and fsync operations used for no-clobber, no-partial-record publication.
- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Covers deterministic serialization and validation of the self-contained versioned floor record.
- [Git — git-rev-parse Documentation](https://git-scm.com/docs/git-rev-parse) — Documents resolving and verifying `HEAD` for the clean source identity.
- [How to monkeypatch/mock modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Covers substituting fake invokers and failure seams so tests never call a live backend.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A separate `run` command, labelled captures, label replacement, archives, current pointers, recovery journals, or concurrent-reader protocol.
- A `compare` command, `inside noise` / `outside noise` classification, score, recommendation, winner, trend, or any automatic interpretation of the floor table.
- More than the fixed three metrics, a metric-registry evolution mechanism, or recomputation of historical records under later metric versions.
- A model judge, rubric, calibration, confidence behavior, quality opinion, prose-agreement check, gate, CI policy, exit-code change, control arm, auto-tuning, parallel fan-out, or any position-02 seed or plan.
- Changes to the existing `bench` command or to existing `create`, `detail`, `run`, and `roadmap` behavior outside the isolated replay invocation.

## Risks

- The table may show that the three measurements are too noisy, or that the corpus is too costly, to support a useful floor. That is a completed proof with a negative result: record the evidence and defer further benchmark work rather than widening the corpus or adding interpretation.
- A changed source state during a floor run would make its samples incomparable. The runner requires the captured clean `HEAD` before each replay and before final publication; a mismatch discards private staging and reports the refusal. Each replay uses its captured command transport; a requested fallback is a failed replay, not a second backend. A corpus edit after the initial byte snapshot does not widen this contract: every replay reads the captured bytes rather than the mutable corpus path.
- The shared roadmap route would otherwise continue through later stages and write a normal run log. The local two-row stage table and private staging logger limit the proof to stage 2 and leave its raw events only inside the output record.
- An interrupt can arrive on either side of no-clobber publication. The `os.link` commit is the explicit completion boundary, so cleanup occurs first and the published record is never classified as an incomplete private run.
- The raw record may be too large for the two-item, R-rerun proof to remain practical. The fixed corpus and explicit output path make that cost visible; compacting or generalizing storage is deferred rather than added here.

## Testing

The bare-plan stage retains the smallest-proof boundary: it covers one corpus, three measurements, one serial floor route, and one immutable output record; any product-shaped lifecycle or comparison request is deferred. Detail may require the exact replay and atomic-publication mechanism only when it demonstrates the pinned-identity and no-partial-record properties.

With a fake `invoker=`, two corpus items and R >= 2 reruns produce one output record with all raw evidence and all three floors. The stage-2 invocation metric counts every `claude_call_start` record with `stage: 2`, including a failed invocation that consumes an attempt; a replay without a finished stage-2 artifact is not published as a sample. For each metric, the expected floor is the largest absolute difference for the same item across every unordered completed-rerun pair. Constant fixture responses yield zero for every floor; a deliberately changed artifact, structured-id set, and stage-2 invocation count widens only their respective floors. The record includes the clean-`HEAD` identity and selected-command fingerprint, and every fake replay receives the same captured command transport; a fallback request fails that replay. The fixture proves that the stage-1 artifact is admitted, only stage-2 calls occur, and no stage-3-or-later event is retained. It also proves that raw floor-run events are embedded from the private staging log while the repository `.plan-tool/runs` set is unchanged. An external corpus edit after snapshot capture cannot affect any materialized input or retained evidence. A dirty or changed source state, failed replay, `R < 2`, or an existing or late-created selected output leaves no completed record; an existing path remains byte-for-byte unchanged. An interruption before the no-clobber link leaves no output; one injected after the link leaves the completed record intact. No test spawns a live backend.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- The only shipped quality-bench operation is the serial floor proof, and it remains separate from the existing `bench` command.
- A complete floor run writes one version-1 self-contained record with the corpus snapshot digest, clean-`HEAD` identity, selected-command fingerprint, raw stage-2 rerun events, and exactly three deterministic floors: artifact byte length, constraint-id count, and the count of `claude_call_start` records with `stage: 2`.
- Every replay admits the frozen stage-1 input and invokes only stage 2 through the captured command transport. A later external corpus edit, backend reselection, fallback request, or stage-3-or-later call cannot enter the record.
- The private staging log is embedded as raw evidence then removed; a floor run leaves no new repository `.plan-tool/runs` log. A dirty or changed source state, incomplete run, or `R < 2` produces no completed record. The runner publishes a fully fsynced sibling temporary with the existing no-clobber `os.link` pattern, so an existing or late-created selected output is refused and preserved byte-for-byte. That link is the completion boundary: interruption before it leaves no output, while a record already linked remains complete.
- For each metric, its floor is the maximum absolute difference across unordered pairs of completed reruns of the same corpus item. An unchanged constant fixture produces zero floors and a deliberately varied artifact, constraint-id set, or stage-2 invocation count widens only the relevant measurement.
- The command reports factual floor data only and changes no existing exit behavior, gate, confidence behavior, or decision path.
- BACKLOG #216 identifies position 01 as this smallest proof and leaves position 02 unauthored.

## Deferred

Comparison and any interpretation of a floor table, reusable label/store lifecycle, additional or versioned metrics, historical recomputation, corpus expansion, calibration, confidence work, and judged metrics are separate follow-up decisions. If this proof is not usable at an affordable R, record that result against BACKLOG #216; do not author a replacement position or broaden the experiment.
