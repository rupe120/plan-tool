# Backends

*Back to [backend setup in the README](../README.md#backends).*

A *backend* is the CLI subprocess plan-tool spawns to run and audit steps.
plan-tool registers three:

- **`claude`** — the default.
- **`codex`** — the OpenAI Codex CLI.
- **`cursor`** — the Cursor Agent CLI (binary `agent`).

Every claude-invoking subcommand (`run`, `detail`, `reconcile-plan`, `jira`,
…) routes through whichever backend is active. Switch to `codex`, for
example, and plan-tool swaps the executable, its argv, its `--json` event
parsing, and its failure classification — all in one place.

### How each backend talks back

- **Codex** — streaming and batch calls both use `codex exec --json`. The
  batch wrapper collapses the JSONL stream down to the final agent message
  before the authoring/audit parsers ever see it, so `create`, `detail`,
  `review`, and apply-style calls read the same final-message contract that
  `run` does.
- **Cursor Agent** — streaming and batch calls both use
  `agent -p --output-format stream-json --force --trust`. Batch
  normalization pulls the terminal `result.result` string out the same way.

Not sure which backend to reach for on a given kind of work — proposal,
detail, reconcile, implementation, apply? See
[`docs/evidence/backend-recommendations.md`](evidence/backend-recommendations.md). It's
regenerated from the synthetic backend-quality benchmark
([`docs/evidence/benchmark-design.md`](evidence/benchmark-design.md); re-run procedure in
[`RUNBOOK.md`](../RUNBOOK.md#which-backend-for-which-task-family)).

## Selecting a backend

plan-tool picks a backend in this order — first match wins:

1. The explicit `--backend` flag.
2. A recognized `--model` family.
3. The `PLAN_TOOL_BACKEND` environment variable.
4. The default, `claude`.

`gpt-*`, `chatgpt-*`, `o1`/`o3`/`o4`, and
`codex-*` select Codex; `claude-*` selects Claude; and `gemini-*` selects the provisional
`gemini` backend until a packaged Gemini integration is available. Other model
names stay on the configured backend.

An explicit `--backend` is your escape hatch for an intentional non-default
pairing.

```bash
plan-tool --backend codex run my-feature        # one run against codex
plan-tool --backend cursor run my-feature       # one run against Cursor Agent
PLAN_TOOL_BACKEND=codex plan-tool run my-feature # same, via the env var
plan-tool --model gpt-5.6-terra run my-feature  # infers the Codex backend
```

`--backend` is a global flag — a sibling of `--no-wait-on-rate-limit` —
applied once in `main()` before dispatch. Its argparse default is `None`,
so leaving it unset lets a recognized model family or the env var choose
the backend; a literal `--backend claude` wins over both. Internally, the
selection name maps to a registered backend via `resolve_backend(name)`.

## Rate-limit recovery

Rate-limit recovery is separate from backend selection. For an ordinary,
recoverable short rate limit, the default is `--on-rate-limit wait`:
plan-tool sleeps until the parsed reset time, then retries the same
backend.

Selection precedence:

1. `--on-rate-limit`.
2. The legacy `--no-wait-on-rate-limit` alias (`stop`).
3. `PLAN_TOOL_ON_RATE_LIMIT`.
4. `wait`.

```bash
plan-tool --on-rate-limit stop run my-feature
plan-tool --on-rate-limit switch --fallback-backend codex run my-feature
PLAN_TOOL_ON_RATE_LIMIT=ask plan-tool run my-feature
PLAN_TOOL_ON_RATE_LIMIT=switch PLAN_TOOL_FALLBACK_BACKEND=codex plan-tool run my-feature
```

For an ordinary short rate limit, here's what each action does:

- `wait`: sleep until reset and retry the same backend.
- `switch`: retry the current rate-limited call with the fallback backend,
  then restore the backend that was active before the call. The fallback
  comes from `--fallback-backend` or `PLAN_TOOL_FALLBACK_BACKEND` (the flag
  wins). Later calls, sibling parallel workers, and serial replay do not
  inherit the fallback backend.
- `stop`: return immediately so you can run the printed resume command
  later.
- `ask`: on an interactive stdin+stderr, show `rate limit [w/b/s]:` and let
  you pick wait, backend switch, or stop. In headless runs it stops instead
  of waiting for input.

#### Cursor's monthly quota is different

Cursor's provider-confirmed monthly plan-quota result is terminal for the
current call. It returns after the first failed attempt and does not wait,
prompt, select a fallback backend, back off, consult the retry guard, or
retry. Its displayed `monthly cycle ends on <date>` value is a calendar
date, not a local reset time or timer target.

Resolve the provider quota, or wait for Cursor's actual reset, then start a
new command invocation. Other short rate limits keep the policy above.

## codex prerequisites

Codex needs two things before plan-tool can use it:

- The `codex` executable installed and on `PATH`.
- Authentication: credentials live under `~/.codex` (`config.toml` +
  `auth.json`), populated by `codex login`.

When you **explicitly** select a backend (via the flag or the env var) and
its binary is absent, the run fails fast with an install/PATH hint and
exit code `127` (`EXEC_NOT_FOUND_EXIT`). The default-`claude` path keeps its
lazy per-call guard instead, so binary-less
read-only commands (`list`, `status`, `validate`) still work with nothing
installed.

A run against an unauthenticated codex surfaces an auth-failure message and
does **not** wait or retry — fix the credentials and re-run (see
[`RUNBOOK.md`](../RUNBOOK.md#codex-backend-prerequisites--auth)).

## cursor prerequisites

Same idea as Codex: the `agent` executable must be installed and on
`PATH`, and authenticated via `agent login` or the `CURSOR_API_KEY`
environment variable.

Explicit selection (`--backend cursor` or `PLAN_TOOL_BACKEND=cursor`) fails
fast with exit `127` when `agent` is absent, same as codex. Unauthenticated
runs surface an auth failure on stderr and do not retry — see
[`RUNBOOK.md`](../RUNBOOK.md#cursor-agent-backend-prerequisites--auth) and
[`docs/reference/contracts/cursor-agent-cli.md`](reference/contracts/cursor-agent-cli.md).

#### The exact Codex contract

See [`docs/reference/contracts/codex-cli.md`](reference/contracts/codex-cli.md) for the exact
flags and event schema. It's the version-pinned contract (captured against
`codex-cli 0.142.0`) to re-capture when codex upgrades, rather than
restating drift-prone flag spellings here.

## Sandbox-mode mapping

codex's workspace-write sandbox with never-prompt approval is the
equivalent of claude's `--permission-mode acceptEdits`: edits get applied
without per-action prompts.

The literal flag spelling — `-s workspace-write` plus
`--skip-git-repo-check` (so scratch contexts without `.git` still run) —
lives in the contract doc, where it's version-stamped and pinned by the
argv tests.

## Stats unavailable under codex

codex doesn't report per-call `cost_usd` or `cache_creation_tokens`. Those
fields stay `None`, and the `runs` profile renders them as `-`. (They're
`Optional` on `run_log.py:ClaudeCallEnd`, and `plan_tool/cli/runs.py`
degrades gracefully when they're missing.)

Everything else still works: token in/out, `cache_read_tokens` (sourced
from codex's `cached_input_tokens`), and wall-clock stay populated, so the
run-log surface and `runs diff` still function — just with empty
cost/cache-creation columns.
