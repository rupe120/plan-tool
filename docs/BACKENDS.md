# Backends

*Back to [backend setup in the README](../README.md#backends).*

A *backend* is the CLI subprocess plan-tool spawns to run and audit steps.
plan-tool registers three:

- **`claude`** — the default.
- **`codex`** — the OpenAI Codex CLI.
- **`cursor`** — the Cursor Agent CLI (binary `agent`).

Every backend-invoking subcommand (`run`, `detail`, `reconcile-plan`, `jira`,
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

Backend selection uses the first available value:

| Priority | Backend source |
| --- | --- |
| 1 | Explicit global `--backend` |
| 2 | Recognized family of explicit `--model` |
| 3 | `PLAN_TOOL_BACKEND` |
| 4 | Project `default_backend` |
| 5 | `claude` |

`gpt-*`, `chatgpt-*`, `o1`/`o3`/`o4`, and `codex-*` select Codex;
`claude-*` selects Claude; `gemini-*` selects provisional Gemini. Cursor has
no inferred model family. Other model names retain the selected backend.
Configured models never infer or change a backend.

Model selection uses the first available value for the selected backend:

| Priority | Model source |
| --- | --- |
| 1 | Explicit global `--model` |
| 2 | `backends.<name>.commands.<canonical-command>.model` |
| 3 | `backends.<name>.model` |
| 4 | Backend manifest `default_model` |
| 5 | Provider CLI default (no model argument) |

`--backend` selects the backend while retaining its configured model defaults.
`--model` overrides model defaults. Both are global flags before the subcommand.
An explicit backend wins over model-family inference, allowing intentional
non-default pairings. Selection applies to the whole command, including its
nested authoring/audit calls; it does not route individual phases or steps.

## Project configuration

Store project choices in `<repo-root>/.plan-tool/backends.json`:

```json
{
  "default_backend": "codex",
  "backends": {
    "codex": {
      "model": "gpt-6.1-sol",
      "commands": {
        "create": {"model": "gpt-6.1-sol"},
        "detail": {"model": "gpt-6.1-sol"}
      },
      "extra_batch_argv": [],
      "extra_streaming_argv": []
    }
  }
}
```

All fields are optional. An absent file preserves unconfigured behavior.
`default_backend` must be a non-empty string when present. Backend entries and
`commands` entries must be objects; model values are non-empty strings, with
absent or `null` models inheriting the next default. Null does not clear a
lower default. Model strings are opaque provider identifiers, not validated
quality tiers. Extra argv fields are lists of strings appended to the backend's
manifest arguments. Configuration cannot replace its binary or parser.

Malformed JSON, wrong field types, empty model strings, unknown command keys,
and duplicate aliases of one canonical command fail with a path-specific
configuration error. Unknown backend override names warn and are ignored;
an unusable selected backend fails selection/preflight (inspection commands
skip it for a project default; see the codex prerequisites). Use lowercase backend
keys. Unknown fields are inert, including the proposal's `default`, `aspects`,
and `failover`; none activates routing or failover.

### Supported command keys and aliases

Keys identify registered top-level commands, not modes, phases or nested
subcommands. Aliases normalize before lookup; specifying both an alias and its
canonical key in one backend is an error.

| Canonical key | Accepted aliases |
| --- | --- |
| `reconcile-plan` | `reconcile`, `review` |
| `verify-all` | `reconcile-all`, `review-all`, `verify` |
| `reconcile-plan-walk` | `reconcile-walk`, `review-walk` |

Other canonical keys (no aliases):

`list`, `root`, `status`, `validate`, `register`, `deregister`, `sweep`, `withdraw`, `attach-branch`, `detach-branch`, `checkpoint`, `runs`, `lessons`, `roadmap`, `create`, `detail`, `split`, `merge`, `jira`, `run`, `reconcile-code`, `completeness-audit`, `data-contract-apply`, `gate-status`, `convergence`, `telemetry`, `init`, `decide`, `suggest-gates`, `bench`, `annotate`, `scope-out`, `scope-review`, `split-criteria`, `worktree`, `install-skill`.

A setting for a deterministic command is accepted but causes no model call.

### Codex create/detail proof

With the example configuration, an authenticated `codex` CLI on PATH, no
`PLAN_TOOL_BACKEND`, and a reviewed seed at `docs/implementation-plans/plan-seeds/my-feature.md`:

```bash
plan-tool create my-feature --from-existing docs/implementation-plans/plan-seeds/my-feature.md --iterate -y < /dev/null
# Commit the generated plan; complete the bare audit and commit judged corrections.
plan-tool completeness-audit my-feature --iterate --commit -y < /dev/null
# From a clean committed tree after the bare gate:
plan-tool detail my-feature --commit -y < /dev/null
```

Without selection flags, `create` and `detail` use Codex with `gpt-6.1-sol`.
Nested calls retain their outer command's choice. The per-command entries show
where a different model would go; choose available models for your account. Complete the detail-grounded audit before implementation.
`plan-tool --backend codex detail my-feature --commit -y < /dev/null` retains
the configured detail model; adding global `--model <model>` overrides it.
These commands demonstrate configuration delivery, not model quality.

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
  inherit the fallback backend. The fallback call uses that backend's own
  `model`, not its `commands.<command>.model`.
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

When a backend is selected by flag, environment, or project default, or a
non-Claude backend is inferred from an explicit model, an absent binary fails
fast with an install/PATH hint and exit code `127` (`EXEC_NOT_FOUND_EXIT`).

For a project-default selection, `list`, `root`, `status`, and `validate` skip this
preflight and work without the backend installed. Explicit flag, environment,
and model selections retain their existing checks. The unconfigured
default-`claude` path retains its lazy per-call guard as well.

A run against an unauthenticated codex surfaces an auth-failure message and
does **not** wait or retry — fix the credentials and re-run (see
[`RUNBOOK.md`](../RUNBOOK.md#codex-backend-prerequisites--auth)).

## cursor prerequisites

Same idea as Codex: the `agent` executable must be installed and on
`PATH`, and authenticated via `agent login` or the `CURSOR_API_KEY`
environment variable.

Cursor selection (including project `default_backend: "cursor"`) fails
fast with exit `127` when `agent` is absent, same as codex; the
project-default exemption for `list`, `root`, `status`, and `validate`
(see codex prerequisites) applies equally. Unauthenticated
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
