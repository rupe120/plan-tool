# Re-verification record, 2026-10-14

This dated record gives the input verification, behavior checks and grader
limitations for the scored run. Use it with `RESULTS.md` and `scored-results.json`
to judge the measurement; it changes no production instruction policy.

## Inputs

All 12 paired input trees (T1–T6, A and B) were rebuilt from the pinned
commits with `build_replacement_inputs.py`. Every `A_input_sha256` and
`B_input_sha256` equals the value in
`replacement-inputs.json`, and
`verify_replacement_inputs.py` passes for all six pairs.

## Behavior and exemption checks

Run with `check_exemptions.py` against the committed
`replacement-tasks.json`. All 18 outcomes match the
expected pre-fix fail, reference pass, mutant fail.

| Task | Pre-fix | Reference | Exemption mutant |
| --- | --- | --- | --- |
| T1 | 3 fail, 8 pass | 11 pass | 1 fail |
| T2 | 7 fail, 15 pass | 22 pass | 1 fail |
| T3 | 1 fail, 4 pass | 5 pass | 1 fail |
| T4 | 2 fail, 11 pass | 13 pass | 4 fail |
| T5 | 2 fail, 1 pass | 3 pass | 1 fail |
| T6 | 7 fail, 6 pass | 13 pass | 1 fail |

`select_tasks.py` regenerates the manifest from its own specs and omits the
extra answer checks the committed manifest carries for T2 and T4; its counts
(T2 20, T4 3) are not the checks of record.

## Reference full suites

`pytest tests/ -q -n auto` in each reference tree; every run has 66 skips.

| Task | Result | Log SHA-256 (prefix) |
| --- | --- | --- |
| T1 | 13,620 pass | `2456840f302c7b7c` |
| T2 | 13,579 pass | `dfb13423c1e7eebe` |
| T3 | 13,592 pass | `9ff569cd22bb1ea3` |
| T4 | 13,666 pass | `f6865ee788632f48` |
| T5 | 13,401 pass | `5cb7788931578b48` |
| T6 | 13,434 pass | `eaf49e2c9d7390a7` |

T6's log is now retained, replacing the summary-only record.

## Startup capture

The frozen model is `gpt-6.1-sol` (owner decision, 2026-10-14; the preparation
used `gpt-5.6-terra`). The capture ran under it: offline Docker (image
`sha256:87bc0abe…`, `--network none`, fake credentials) against a scratch copy
of T1. A carries exactly one complete full-guide injection and no compact text;
B exactly one compact-guide injection and no full guide. One provider request
each, zero inferences, and the request's `model` is `gpt-6.1-sol`.

Advertised namespaces under this model are `functions`, `clock` and
`collaboration`; `clock` is new and is not an MCP namespace. Request hashes
differ from the earlier record (A `187d90e5…`, B `bf785be7…`) because the model
and environment details are embedded in the request.

The common brief changed only in naming the model; its hash and every task's
effective-prompt hash in `replacement-tasks.json` were
recomputed. Input-tree hashes are unaffected.

## Not re-run

The sandbox probes (workspace/Git/tmp writes, absent controller checkout, denied
sockets) and the controller suite were not repeated.

## Calibration approval, 2026-10-14

The owner approved the calibration envelope as proposed, under `gpt-6.1-sol`:
six serial A probes (one per task T1–T6), up to 500,000 provider
input-plus-output tokens and 25 minutes per probe, 3,000,000 tokens aggregate,
plus one 500,000-token / 25-minute in-flight allowance. Required review calls
count inside these limits. This is a scheduling bound, not a monetary cap.
The scored-run ceiling remains unapproved and is set after calibration.

### Limit basis, 2026-10-14

Two T1 probes used 1,307,371 and 1,647,363 input-plus-output tokens, of which
about 1.5M was cached input (non-cached roughly 90k). The owner chose to count
**non-cached input plus output** against the 500,000 / 3,000,000 token limits.
The headline measure in DESIGN.md is unchanged: input plus output, cached input
counted once. The runner records both. The limits remain scheduling bounds
checked after each session's `turn.completed`; a single-turn run cannot be
stopped mid-run from that stream.

## Scored-run limits approval, 2026-10-14

The owner approved these scheduling limits for the 36 scored trials, counted as
non-cached input plus output per `turn.completed`:

| Item | Value |
|---|---|
| Per-trial tokens | 500,000 |
| Per-trial time | 25 minutes |
| Aggregate ceiling | 6,000,000 |
| In-flight allowance | one trial (500,000 tokens / 25 minutes) |

Basis: calibration probes T1–T6 (condition A) peaked at 169,174 non-cached
tokens and 824 s (T2). A breach is recorded and pauses scheduling; the runner
does not stop a container. These are not a monetary cap. Not yet frozen: the
36-trial schedule, permitted verbatim scope answers, and review-usage
accounting.

## Probe grading and grader relaxation, 2026-10-14

Probes T1–T6 (condition A) were run against the reference checks. T2, T4, T5
and T6 passed. T1 and T3 failed on exact strings the prompt does not state:

- T1 required "drop this dependency, or another reference on the same cycle";
  the prompt says only that a cycle correction must say to drop a reference.
- T3 required the Stack row line indented two spaces; the prompt says only
  "plain grouped lines".

Both assertions were relaxed (T1: message contains "drop" and "reference";
T3: the row line matches after stripping indentation), in `select_tasks.py`,
with the manifest hashes for those two checks updated. After the change T1 is 3
failed before and 11 passed on the reference; T3 is 1 failed before and 5
passed on the reference; both probe outputs pass. The relaxation was made after
seeing probe outputs, applies equally to A and B, and is disclosed here.
Scope fence: no probe changed production paths outside its allowed set.

Review usage: every probe shows one `thread.started`, and the only collab item
is one `wait` in T1 probe 2. Agents report read-only reviews, but any reviewer
session usage is not separately observable. The trial total is the single
`turn.completed`, applied identically to A and B, and is a stated limitation.

## Schedule frozen, 2026-10-14

`schedule.json` is frozen as drafted (seed 20261013, 36 trials in 18 adjacent
A/B pairs, 9 A-first), with limits, per-trial prompt/input hashes and no
permitted scope answers. Scored trials run serially, starting with the first
pair (T1 A, T1 B) as a check that B starts and yields gradable output.

## First scored pair and T1 grader change, 2026-10-14

Ordinals 1–2 (T1 A, T1 B) ran clean: exit 0, no failed turn, no breach, clean
trees. A: 202 s, 80,961 non-cached tokens, 2 commits. B: 329 s, 97,661
non-cached tokens, 3 commits; B read `docs/` reference documents on demand and
spawned one `collab_tool_call`. Against the 2026-10-14 relaxed T1 check, A
passed and B failed on wording alone ("drop the dependency to break the
cycle" has no word "reference").

The owner approved a second relaxation: the T1 cycle-message assertion now
requires "drop" with "dependency" or "reference" (the unchanged assertion that
the message does not say "move" stays). Before: 3 failed; reference: 11 passed;
both calibration probes and both scored trials: 11 passed. The change was made
after seeing a scored B output, applies to A and B, and was committed before
ordinal 3 started. Ordinals 3–36 run through `run_schedule.py`, which declines
to start the next trial on any nonzero exit, failed turn, unknown usage,
per-trial breach, or aggregate non-cached tokens above 6,000,000.
