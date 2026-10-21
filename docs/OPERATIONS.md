# Day-to-day operations

*Back to [operating a run](../README.md#running-headlessly).*

This is everything that happens around plan-tool's pipeline, not inside it:
running the tool with nobody at the keyboard, picking up where a failed run
left off, reading the logs a run leaves behind, watching progress while a
call to Claude is in flight, running several plans side by side without them
tripping over each other, and keeping the lessons files plan-tool collects
along the way tidy.

## Choose an operational route

| If you need to… | First action | Then read |
| --- | --- | --- |
| Run without a terminal | Add `-y < /dev/null` to the command | [Running headlessly](#running-headlessly) |
| Resume after an interruption or failure | Inspect the saved checkpoint and printed resume command | [Resuming after a failure](#resuming-after-a-failure) |
| Inspect what a run did | `plan-tool runs list` | [Run logs](#run-logs) |
| Watch a long backend call | Keep the stderr progress stream visible | [Console progress reporting](#console-progress-reporting) |
| Work on plans in parallel | `plan-tool worktree add <plan>` | [Worktrees (parallel plans)](#worktrees-parallel-plans) |

## Running headlessly

Headless mode means running `plan-tool` non-interactively — chat agents, CI
jobs, cron. It takes two ingredients:

1. **`-y` / `--yes`** — skips confirmation gates and, for `create`,
   default-accepts free-text wizard prompts. See
   [Shared options](reference/commands.md#shared-options) for the full list.
2. **Close stdin** (`< /dev/null`) — guarantees the process can't
   block on terminal input.

**Don't** pipe an infinite empty-line source like `yes "" |`. It looks
harmless and isn't: `_ask(..., required=True)` re-prompts on empty
input and spins. Close stdin with `< /dev/null` instead: it raises
`EOFError`, which the wizard turns into a clear `CreateError` under
`--yes`.

### `plan-tool create` headlessly

```bash
plan-tool create my-plan-slug \
  --from-existing /path/to/seed.md \
  --output-dir docs/implementation-plans \
  -y < /dev/null
```

Notes:

- Prefer `--from-existing` over `--from "<inline-text>"` for scripted
  use: a real file is easier to write, easier to inspect later, and
  shell quoting can't mangle it.
- `--output-dir` is required once stdin is closed. Without it, the
  wizard would prompt for a directory and `--yes` would silently
  substitute the default for you — better to just say what you mean.
- Claude does its best to find steps in your seed, either by pulling a
  canonical `## Steps` list straight out of it or by proposing steps
  itself. If neither works, `--yes` mode raises
  `CreateError("--yes mode: no parseable steps from canonical or claude. Provide a richer --from-existing seed...")`
  and exits non-zero — the fix is a richer seed, not a retry. Without
  `--yes`, the wizard would fall back to interactive per-step prompts,
  which would block under closed stdin.
- Under `--yes`, collision handling defaults to N — the wizard does
  *not* auto-archive a colliding plan, it raises `FileExistsError`
  instead. Archive the old plan directly before you re-run.

### `plan-tool detail` headlessly

```bash
plan-tool detail my-plan-slug -y < /dev/null
# or, for a specific step:
plan-tool detail my-plan-slug --step 3 -y < /dev/null
```

Notes:

- `detail` is already mostly non-interactive. Per-step idempotency
  skips any step whose detail file already exists on disk, and the
  parser gets one retry (with a clarifying suffix) before it gives up.
  `-y` covers what's left: the Y/N gates around lessons capture and
  the optional re-run prompts.
- Lessons capture — a second Claude call per step — is **off by
  default**, so headless and cost-sensitive runs pay nothing extra
  for it. Pass `--lessons` to turn it on.
- Claude doesn't always give you something the parser can use. After
  two failed attempts on a step, `detail` records it as skipped with
  `"claude returned an unparseable response"` and moves on — the run
  still exits 0 overall, so check the per-step report at the end of
  stdout to see what actually got skipped.

### `plan-tool reconcile-plan` / `reconcile-plan-walk` headlessly

```bash
plan-tool reconcile-plan my-plan-slug -y < /dev/null
plan-tool reconcile-plan-walk my-plan-slug -y < /dev/null
```

`-y` at the per-recommendation prompt is the same as typing `aa`
(apply-all) at the first one: every recommendation gets auto-applied,
and every `apply-finding` "Keep these changes?" diff gets auto-kept.
Saved-review walks behave the same way when you re-invoke them.

### Streaming output back to a chat agent

Append `2>&1 | tee /tmp/plan-tool.log` to capture stdout and stderr
together. The tool flushes a header as it goes — each `[N/M]` step,
each `done in Xs` — so a chat agent watching the log file sees
progress arrive in real time instead of one dump at the end. See
[Console progress reporting](#console-progress-reporting) for the
exact line format.

### Iterating headlessly

`--iterate` and `-y` compose. Under `-y` (or closed stdin, or a
non-TTY), the walk inside every iteration defaults to `apply-all`, so
iteration N+1 never blocks on `input()`. The same
`WalkState(yes_to_all=True)` seed that drives the inner walks under
`-y` (per the step-4 wiring at
`plan_tool/cli/reconcile.py:_iterate_reconcile_loop`) also auto-keeps
every apply-finding diff. A completed loop exits 0 even when the
budget runs out with findings still open — a CI job should inspect
the printed report or the saved findings rather than the return code.
For the audit commands (`completeness-audit` / `verify-all` /
`validate`), pass `--fail-on-findings` instead, to gate the pipeline
on the exit code directly:

```bash
plan-tool detail my-plan --iterate -y < /dev/null
plan-tool detail my-plan --reconcile --step 3 --iterate -y < /dev/null
plan-tool run my-plan --reconcile --step 3 --iterate -y < /dev/null
```

See [Iterating to convergence](ITERATION.md)
for the loop semantics and the "When to use" decision tree.

## Resuming after a failure

Both `plan-tool create` and `plan-tool detail` remember every
successful Claude response — plan-tool writes each one to
`<repo>/.plan-tool/checkpoints/<plan-slug>/` as it comes back. So if a
run dies between a successful parse and the durable on-disk write — a
write error, a plan-update error, Ctrl-C, a killed shell, a model
timeout in the post-implementation phase — the next run reuses the
cached body instead of asking Claude all over again.

```bash
plan-tool detail my-plan -y < /dev/null # default: resume enabled
plan-tool detail my-plan --no-resume # force fresh Claude calls
```

#### What's cached

- **`detail`** caches per step. The hash covers the plan slug, step
  id, title, complexity, files list, depends_on, and the rendered
  confirmed project context. Edit the step's title, complexity,
  files, dependencies, or project profile and that step's cache
  invalidates; edit unrelated metadata or the plan body and it does
  **not**.
- **`create`** caches by authoring slot: `create-initial-steps` (slug
  + description + output dir + iteration index), `create-references`
  (title + description + slug + output dir + iteration index), and
  `create-body-sections` (slug + seed source bytes + output dir +
  iteration index). The initial-step and body-section slots also fold
  in the rendered confirmed project context; the reference-search
  slot doesn't. File-backed routing owns its own direct-assessment or
  preparation checkpoints separately. Edit the seed file, the
  relevant project profile, or the output dir and the affected slot
  invalidates; re-run interactively with the same answers and
  matching work gets reused.

#### Staleness

- Checkpoints older than **30 days** count as expired and get
  bypassed — see `DEFAULT_MAX_AGE_SECONDS` in `checkpoint.py`.
- A clean publication discards completed checkpoints. File-backed
  split and normalized iteration-incomplete outcomes keep their own
  route-owned recovery state instead — see
  [`docs/how-to/recovery/create.md`](how-to/recovery/create.md).
- `.plan-tool/checkpoints/` is gitignored.

#### Caveats

- **Concurrent runs against the same plan are undefined.** Each
  on-disk write is atomic per file, but two `plan-tool detail`
  invocations running at once against the same plan and step turn
  into a last-writer-wins race for the checkpoint, the detail file,
  *and* the plan frontmatter. There's no lockfile, so don't overlap
  them.
- **`--force` bypasses both the file-exists skip and the cache.**
  Reach for it when you want a fresh body without deleting any state.
- **The hash is intentionally narrow.** Editing source files, sibling
  detail files, lessons, or the plan body between runs does NOT
  invalidate a cached body. If you've changed something the hash
  doesn't cover and want a fresh call anyway, pass `--no-resume`.

### Managing checkpoints

```bash
plan-tool checkpoint list # show every cached checkpoint
plan-tool checkpoint show <slug>/<checkpoint> # print one (payload to stdout, meta to stderr)
plan-tool checkpoint clear <slug> # remove one plan's cache
plan-tool checkpoint clear --all # wipe everything
```

`show` sends metadata (created_at, input_hash, schema_version) to
stderr and the raw payload to stdout, so it pipes cleanly —
`plan-tool checkpoint show my-plan/detail-step-03 | bat`, for example.

## Run logs

Every subcommand that invokes a backend (`run`, `verify-all`,
`detail`, `jira`, `reconcile-plan`, `create --from*`) — plus roadmap
stage runs, seed-materialization, seed-refresh, and seed-apply runs —
writes two artifacts under `<repo>/.plan-tool/runs/<plan-slug>/`:

- `<run_id>.jsonl` — append-only structured event log.
- `in-flight.json` — an atomically-updated liveness snapshot. It
  refreshes on phase start, backend spawn, every heartbeat, backend
  termination, and backend recovery wait — see
  ["The in-flight snapshot"](#the-in-flight-snapshot) below.

It covers the same ground as the live stderr progress reporter —
start, heartbeat, done, plus per-Claude-call wall-clock time, tokens,
and cache hits — but in a form that's machine-readable and durable
past your terminal's scroll buffer.

#### What gets recorded

- `run_start` — schema version, command, plan slug, argv, pid, cwd.
- `phase_start` / `phase_end` — one pair per logical phase (e.g.
  `propose_steps`, `propose_references`, `fetch_reference_docs`,
  `propose_body_sections`, `per_step_body`, `prompt_build`,
  `claude_call`, `reconcile_walk`, `apply_finding_dispatch`).
- `claude_call_start` / `claude_call_end` — one pair per logged `claude -p`
  invocation. `claude_call_end` carries the wall-clock duration and,
  when `claude -p --output-format json` is supported, input/output
  tokens, cache-creation / cache-read tokens, request id, and cost.
  `claude_call_start` carries `prompt_bytes` and `prompt_sha256` (hex
  SHA-256 of the prompt, never its text; `null` when a caller supplied none).
  Events written before 2026-10-16 lack the `prompt_sha256` key.
  `claude_call_end` also carries `input_includes_cached`: `true` when
  `tokens_input` already counts cached tokens (codex), `false` when it
  excludes them (claude), `null` when not established (cursor, and events
  written before 2026-10-16). Non-cached input is `input - cache_read` when
  `true` and `input + cache_creation` when `false`.
- `audit_pass_end` — one per conceptual-audit sampling pass: `pass_number`,
  `cap`, `outcome` (`conforming`, `failed_or_malformed`, `skipped`,
  `terminal_plan_quota`, `errored`), the finding ids first seen this pass
  (`new_ids`, carried findings excluded), the `material_new_ids` subset,
  exact `new_count` / `material_new_count` (the id lists are capped at 40, so a
  count above the list length means truncated), and `unique_so_far`. It makes the yield of passes 2 and 3 over pass 1
  measurable; saved completeness reports keep only the final union. Runs
  before 2026-10-16 have no such events.
- `checkpoint_hit` / `checkpoint_save` / `checkpoint_discard` — every
  checkpoint cache interaction (the same cache `## Resuming after a
  failure` documents, above).
- `parse_failure` — a pointer to the existing
  `.plan-tool/parse-failures/<plan-slug>/<NN>-attemptK-<ts>.txt` body
  from `detail`'s parse-retry loop. The body itself isn't duplicated
  into the log.
- `gate_violations` — the gate messages that used up one failed
  attempt in the `roadmap` stage loop, so you can tell a stage that
  passed on its last try apart from one that passed clean the first
  time. Messages get dropped whole past a size budget, but
  `violation_count` always stays exact.
- `attempt_failed` — which of the four failure kinds (`invoke`,
  `parse`, `authored-review-rows`, `gates`) used up an attempt in the
  `roadmap` stage loop. It fires for every kind, so an attempt that
  fails and then **recovers** — the common case, and otherwise
  invisible since the stage goes on to write its artifact anyway —
  still gets its cause on record.
- `model_failure_receipt` — redacted evidence for a rejected reply from
  roadmap fresh-stage authoring, and for a failed `run` step (a `run` receipt
  has no `gate_violations` or `attempt_failed` partner; its `reason` is one of
  `invoke`, `no-edits-applied`, `test-authoring-gate`, `test-gate`, `gate`).
  Find the receipt in `plan-tool runs` by phase and
  attempt. Its safe fields are the producer-owned reason, response byte count
  and SHA-256 digest, plus sidecar disposition (`written`, `no-response`,
  `not-retained`, or `write-failed`) and an optional repository-relative
  `sidecar_path`. Use that path only when present: a missing, unavailable, or
  failed sidecar capture is a valid receipt outcome, not a command failure.
  JSONL stores none of the raw response, prompt, validation prose, provider
  transcript, or tool-input content.
- `gate_violations` remains the structured diagnosis for fresh and bounded
  stage gate failures, and `attempt_failed` remains the retry-spending
  classification. The receipt is correlated by phase and attempt; it neither
  replaces those events nor copies their diagnostics.
- `roadmap_preflight_failed` / `roadmap_stage_written` — a typed stage-run
  refusal before any stage is invoked (accepted head present, pre-head state,
  brief source or read, publication recovery, resume digest, or carried
  decisions), plus the path, digest, and always-false replacement status of
  every stage held for resume.
- `roadmap_seed_apply_result` — the aggregate target, promotion,
  collision, missing-draft, and provenance failure counts for
  `roadmap --apply`, which has the same run boundary even though it
  makes no Claude call.
- Roadmap seed actions (`--materialize` and `--refresh-seeds`) carry
  one redacted command record and liveness snapshot. Their
  source-ordered row phases, attempt counters, terminal outcomes, and
  redaction boundary are in
  [DATA_CONTRACT.md](../DATA_CONTRACT.md#roadmap-seed-action-context-and-lifecycle).
- `iteration_start` / `iteration_end` — per-step framing under
  `cmd_detail` so a multi-step `detail` call records each step's
  bounds.
- `run_end` — total duration, outcome (`ok` / `error` /
  `interrupted`), rc.

`.plan-tool/runs/` is gitignored alongside `.plan-tool/checkpoints/`
and `.plan-tool/parse-failures/`.

### Roadmap seed actions

`plan-tool roadmap <slug> --materialize [PLAN_ID]` and
`--refresh-seeds` each own one `command: "roadmap"` JSONL record and
the active `in-flight.json` snapshot. Both call the standalone seed
materializer, so they count as backend-backed even though they never
run a roadmap stage. The command record keeps `roadmap_action`,
`roadmap_slug`, the explicit `requested_plan_id` when one was
supplied, and whichever row is currently being prepared or
materialized. It runs through the same writer lifecycle as everything
else: `RunLogWriter.start()`, `phase_start()`, `phase_end()`, and
`run_end()`.

Each attempted row gets a `seed-materialize:<plan-id>` phase. The row
sequence follows `PlansArtifact.plans`, not its presentation
`ordering`: an explicitly selected materialization attempts just that
row, an unqualified `--materialize` attempts every eligible row, and
`--refresh-seeds` attempts every row. After a row's phase ends, the
writer publishes inactive row context before moving to the next phase
and before terminal cleanup. The snapshot gets removed by the
terminal writer path on completed, no-op, partial, exhausted,
preflight-refused, interrupted, and error outcomes.

The seed-action records keep lifecycle timing, retry counts, safe
failure kind, numeric return code, and aggregate counts. They never
keep prompts, seed bodies, replies or reply heads, validation prose,
`failure_detail`, provider transcripts, or tool-input summaries. The
seed-refresh report stays the human-facing comparison — it's not a
copy of what gets logged.

These boundaries stay separate from the other roadmap modes: `--apply`
stays backend-free but still writes its existing apply-specific run
record, while `--accept-seed` and `--view` stay both backend-free and
log-free. Roadmap views don't create a run record at all; `--view html`
only writes its derived output page.

### Inspecting recent runs

```bash
plan-tool runs list # every slug, run_id, command, duration, tokens
plan-tool runs list --slug my-plan # filter to one plan
```

Each row carries `slug`, `run_id`, `cmd`, `started_at`, `duration`
(or `in-flight` when no `run_end` is on disk yet), `events`, and
`tokens`. Symlinked slug directories get skipped.

### Reading one run

```bash
plan-tool runs show my-plan/<run_id>
plan-tool runs show my-plan/<run_id>.jsonl # trailing .jsonl is accepted
```

- **stdout** — event lines with phase / claude-call indentation.
- **stderr** — metadata (run_id, plan_slug, command, schema_version)
  as `# `-prefixed lines, so `runs show … | grep claude_call_end`
  works.
- **Exit 1** on schema_version mismatch on the first `run_start`,
  with `unsupported run-log schema_version` printed to stderr.

### Comparing two runs

```bash
plan-tool runs diff my-plan/<run_a> my-plan/<run_b>
```

Produces a per-phase wall-clock and token delta table:

- Phases present in both runs sort first (alphabetically), then
  `only-in-A`, then `only-in-B`.
- The closing line summarizes `total Δwall`, `total Δtokens`, and the
  `only-in-A` / `only-in-B` counts.
- Token columns render as `-` when both calls hit the older-CLI
  fallback, which returns no token metadata.

### The in-flight snapshot

```bash
cat .plan-tool/runs/<plan-slug>/in-flight.json | jq .
```

- Every refresh writes atomically (tempfile + `os.replace`), so `cat`
  always sees a complete snapshot, never a partial write.
- `RunLogWriter` refreshes it from five call sites, each merging its
  fields into the same held snapshot so one trigger's write never
  drops another trigger's fields: `phase_start` (`current_phase`),
  `backend_spawn` (`child_pid`, `transport`, `effective_timeout_ms`,
  `prompt_bytes`), `claude_call_progress` — the heartbeat —
  (`elapsed_ms`, `silent_ms`, `last_tool`), `backend_termination`
  (`termination_reason`), and `backend_recovery_wait`
  (`recovery_reason`, `recovery_delay_ms`, `recovery_next_attempt`).
- `status` is one of `running`, `awaiting_retry`, or
  `backend_terminated`. The heartbeat never writes `status` — a late
  heartbeat can only refresh the timing fields, never overwrite a
  termination or a recovery wait with a stale "running". The next
  `phase_start`/`backend_spawn` in a multi-phase run flips `status`
  back to `running`.
- Schema: `{schema_version, run_id, command, plan_slug, started_at,
  log_path, status, current_phase, last_event_ts, elapsed_ms,
  silent_ms, last_tool, child_pid, effective_timeout_ms, transport,
  prompt_bytes, termination_reason, recovery_reason,
  recovery_delay_ms, recovery_next_attempt, ...}` — each field appears
  only once its triggering event has fired at least once.
- Reach for this when `plan-tool run` looks frozen on stderr and you
  want to know which phase is actually in flight, whether the
  subprocess is still emitting activity, or whether it's
  intentionally sleeping in a rate-limit/transient recovery wait
  rather than hung.
- `annotate`, `jira`, and `create`'s slug-generation call open no
  `RunLogWriter`, so they produce no snapshot — same as they produce
  no JSONL trail.
- **Not removed by `runs clear --older-than`** (mtime would race the
  active writer). `runs clear --all` and `runs clear <slug>` do
  remove it.
- Teardown (`run_end`) skips the delete when a newer same-slug run has
  since claimed the file — its `run_id` no longer matches the ending
  writer's own — so a completing call can't erase a still-running
  sibling's only liveness signal.

### Cleanup

```bash
plan-tool runs clear --older-than 30d # evict everything older than 30d
plan-tool runs clear my-plan # remove one slug's runs (incl. in-flight.json)
plan-tool runs clear my-plan --older-than 7d # combine: only old runs under one slug
plan-tool runs clear --all # wipe every run log under .plan-tool/runs/
```

`--older-than` accepts `30d`, `48h`, `90m`, or a bare integer in
seconds. The recommended default — see `_DEFAULT_RUNS_TTL_SECONDS` in
`plan_tool/cli/runs.py` — is `30d`, the same cadence as
`.plan-tool/checkpoints/`'s auto-expiry.

See [`RUNBOOK.md`](../RUNBOOK.md#workflow-investigating-a-slow-run) for
a step-by-step walkthrough.

## Console progress reporting

Every subcommand that calls Claude (`run`, `verify-all`, `detail`,
`jira`, `reconcile-plan`, `create --from*`) prints status lines to
**stderr** while a call is in flight — so you're not left staring at
a silent terminal wondering if it's stuck. Stdout stays byte-identical
(or streams `claude --verbose` for `run` / `verify-all`).

```
[1/3] step 1: Wire up the renderer…
        15s elapsed
        30s elapsed
        done in 47s (4.2 KB response)
```

- **Start line** (`[N/M] <label>…`) — one per claude invocation.
  `run` and `verify-all` append `(mode=<mode>)`.
- **Heartbeat** (`Ns elapsed`) — every 15s while the call is in
  flight.
- **Close line** — `done in Xs (YKB response)` on success;
  `FAILED in Xs: <reason>` on failure.
- **`[N/M]` counts invocations**, not target steps. Idempotent skips
  and `--dry-run` paths emit nothing.
- **Stdout is preserved** — `plan-tool jira --format json | jq`
  works; `run` / `verify-all` continue to stream `claude --verbose`.

See [`RUNBOOK.md`](../RUNBOOK.md#progress-output-during-long-claude-calls)
for sample output, scripting implications, and how to suppress.
Implementation: `plan_tool/progress.py` (`ProgressReporter`,
`StderrReporter`, `NullReporter`). Roadmap does not use this heartbeat
contract: its ordinary stage run owns separate, transition-only stderr status;
see [0. `roadmap`](how-to/common-workflows.md#0-roadmap--stage-a-project-sized-concept-optional).

## Worktrees (parallel plans)

A long `create` / `detail` / `run` call on one plan ties up the
repo's single index, branch, and checkout. The `worktree` command
group fixes that: each plan gets its own **isolated working copy**,
so several plans' processes can run in parallel without stepping on
each other. Four verbs:

```bash
plan-tool worktree add <plan> [--branch B] [--clone]  # provision (or reuse) the plan's workspace
plan-tool worktree list                               # kind / branch / path / dirty for every plan's workspace
plan-tool worktree remove <plan> [--force]            # delete one plan's worktree (dirty needs --force)
plan-tool worktree prune                              # sweep dead (deregistered / path-gone) worktrees
```

**Where they land.** The default base is `<repo-parent>/<repo-name>.worktrees/<slug>`
— a **sibling** of the repo, never inside it (a worktree nested
inside the main tree corrupts git). Override the base with the
`worktree_base` key in the project's `.plan-tool/config.json`, falling
back to the user's `~/.plan-tool/config.json`. A value that resolves
inside the repo gets rejected with a warning, and the default is used
instead.

**The branch.** `add` provisions the workspace on the plan's branch,
and **the branch is born inside the add** — on the plan's
slug-derived name when branch-awareness is OFF (the default), or the
`derive_branch` name when it's ON, branching off the resolved start
point (the repo's default branch, or `HEAD` on a local-only repo with
no remote). Pass `--branch B` to override. Re-run `add` on a healthy
existing workspace of the expected kind and branch and it just reuses
it (idempotent); a foreign or wrong-branch directory at the path gets
refused, never overwritten.

**Worktree vs `--clone`.** The default, and the recommended path, is
a **git worktree** — it shares the repo's object store, remote, and
config, so it's cheap. `--clone` opts into a full standalone **clone**:
an independent repo with its own duplicated object store, remote, and
config. Reach for it only when a run needs total isolation from the
shared `.git`.

### Caveats (sharp edges)

- **Don't change `worktree_base` while workspaces exist.** The
  per-slug path gets re-derived from the base on every `list` /
  `remove` / `prune`, so moving the base points those verbs at a
  *different* location — they can no longer find workspaces you've
  already provisioned. Worktrees survive this (git's own registry
  still tracks them); clones don't. Rule of thumb: re-provision after
  any base change.
- **Clones are cleanup outside plan-tool — plan-tool never auto-deletes one.**
  `remove` deletes a *worktree*, but on a **clone** it just prints a
  cleanup-outside-plan-tool message and deletes nothing; `prune` (which only
  sweeps the git worktree registry) ignores clones entirely. A clone
  is an independent repo whose commits live only in its own `.git`
  — committed-but-unmerged work the uncommitted-only dirty gate can't
  see — and it carries no plan-tool provenance marker, so no scan can
  safely tell a dead plan-tool clone from an operator's unrelated
  repo. Delete a clone yourself: `rm -rf <path>`, after confirming
  there are no unmerged commits. `list` keeps it visible until you do.
- **Plans are per-branch; don't `gc` aggressively across parallel runs.**
  A plan resolves inside a worktree only if its `.md` and
  `plans.json` entry are committed on that worktree's base branch —
  otherwise you get "plan not found". Worktrees share
  `.git/objects`, so an aggressive `git gc` while parallel runs are
  live can disturb another run's objects; avoid it. `remove` /
  `prune` refuse a dirty *worktree* without `--force`, and `prune`
  **surfaces** (never silently deletes) a dead-but-dirty worktree
  even under `-y`.
- **Removal never deletes the branch.** `remove` / `prune` delete the
  *worktree directory* but **not** the branch born inside the `add`
  — branch cleanup (`git branch -d <branch>`) is still on you, the
  normal git flow. (Clones aren't deleted at all — see above.)

Operational walkthrough: [`RUNBOOK.md`](../RUNBOOK.md#workflow-run-plans-in-parallel-worktrees).

## Lessons log behavior

When frontmatter includes `lessons: <path>`, a successful `run`
appends a timestamped line to that file:

```
- 2026-04-22T15:30:45Z step 2: Build the parser
```

Review modes don't append — the log stays append-only. See
[Lessons consolidation](#lessons-consolidation) for the consolidate
subcommand and the opt-in write-path hooks that work on these same
files.

## Lessons consolidation

`plan-tool lessons consolidate` scans the lessons files plan-tool
maintains, looking for near-duplicate and conflicting bullets. By
default it just diffs the proposed cleanup; pass `--apply` to rewrite
the files in place.

It walks three discovery scopes, in a stable order:

- the per-user `~/.plan-tool/lessons/general.md`
- the per-repo `<repo-root>/.plan-tool/lessons/project.md`
- every per-plan `lessons.md` resolved through a plan's `lessons:`
  frontmatter field (`--plan <slug>` scopes the run to one plan's
  file)

The posture is fail-safe: it diffs by default and never touches disk;
`--apply` rewrites behind a Y/N confirmation; and a non-TTY caller
must pass `-y` to apply, or the command exits non-zero rather than
rewrite anything unattended. Only duplicates drive a removal —
conflicts get surfaced for a session-directed edit and are never auto-removed.

```bash
plan-tool lessons consolidate                       # diff the proposed cleanup; never writes
plan-tool lessons consolidate --apply               # rewrite in place (confirms on a TTY)
plan-tool lessons consolidate --min-confidence 0.9  # require higher equivalence confidence
```

**Opt-in write-path hooks.** `plan_tool.lessons.append_lessons`
carries two opt-in pre-write hooks, both defaulting to `False`.
`strict_check` runs `find_lesson_equivalences` against the substring
survivors and *refuses* to write a candidate the primitive flags as a
duplicate or conflict. `warn_check` is the audit-only sibling: it
keeps the write but records the finding. Either hook's findings get
appended to `.plan-tool/lessons-warnings.jsonl`, so the consolidate
pass can later rank repeat offenders. The defaults stay unchanged, so
existing callers see the same historical substring-dedupe behavior
they always have.

**Recurrence weighting.** The consolidate handler reads
`.plan-tool/lessons-warnings.jsonl` via `load_warnings` /
`recurrence_counts`, so findings flagged on prior sessions sort ahead
of first-time judgments and carry a `recurrence=N` annotation. The log
is rolling-cap trimmed (`DEFAULT_WARNINGS_CAP` records) and gitignored;
pass `--ignore-recurrence` to skip the read and see the raw primitive
order instead.

See [RUNBOOK.md → Workflow: consolidate lessons files](../RUNBOOK.md#workflow-consolidate-lessons-files)
for end-to-end recipes.
