# Codex CLI contract

Reference contract for the `codex` CLI as a plan-tool execution backend, plus
the claude-side surfaces the codex backend (steps 2–3 of *"Support codex as an
alternative CLI backend to claude"*) must map onto field-for-field.

The codex backend normalizes codex's `--json` event stream onto the launcher's
existing event model. Because **codex's stream schema differs from claude's
`stream-json`** (different event-type names, different token/usage field paths,
a different terminal envelope) and **version drift is likely**, the codex half
of this contract is *captured ground truth*, not recollection: every
codex-specific value below comes from running the real installed binary, and the
raw transcripts under `tests/fixtures/codex/` are what the step-3 backend tests
parse.

---

## STATUS: CAPTURED — probed against the real binary 2026-06-23

The step's authoring claude could not run `codex` (the execution
environment's approval gate refused the binary), so it produced this
document with explicit `TODO(probe)` placeholders and the probe runbook
below. The operator session then executed that runbook against the real
installed binary (`codex-cli 0.142.0`) and filled every placeholder; the
raw transcripts live under `tests/fixtures/codex/` (five fixtures — the
two named ones plus command-execution, auth-failure, and turn-failed
error transcripts).

One contract fact discovered in probing that the runbook didn't
anticipate: **codex reads stdin when it is piped/inherited** (`Reading
additional input from stdin...` on stderr, with the content appended as
a `<stdin>` block). Backend subprocess calls MUST pass
`stdin=subprocess.DEVNULL` (or close stdin) or risk hangs and prompt
contamination.

---

## Probe runbook

Run in a disposable scratch directory (codex reads/writes the cwd). Do **not**
commit anything containing an auth token, API key, or account id from
`~/.codex/auth.json`, nor a real home/cwd path — see [Sanitization](#sanitization).

1. **Version stamp** (drift anchor for the fixtures):
   ```
   codex --version
   ```
   Paste the exact output into [Version stamp](#version-stamp) below.

2. **Batch/help surface** — enumerate the non-interactive flags:
   ```
   codex exec --help
   ```
   Identify the codex equivalents of claude's batch argv
   (`claude -p --permission-mode acceptEdits <prompt>`, see
   `plan_tool/shell.py:_run_once`): prompt-passing form (positional vs `-`/stdin),
   the sandbox/approval flag equivalent to `--permission-mode acceptEdits`,
   `--skip-git-repo-check` semantics, and how the final assistant message is
   obtained in non-streaming mode.

3. **Streaming run** — capture the full event stream verbatim:
   ```
   codex exec --json "print hello and stop"   # plus the sandbox/approval flag from step 2
   ```
   Save stdout, one JSON object per line, unreformatted, to
   `tests/fixtures/codex/exec-stream-sample.jsonl`. Keep the terminal
   result/usage line(s) as `tests/fixtures/codex/exec-result-envelope.jsonl`.

4. **Error shapes** (best-effort) — if a rate-limit/usage-limit, auth-failure, or
   context-overflow transcript can be reproduced, record the verbatim message
   strings in [Error shapes](#error-shapes). If a rate-limit transcript can be
   reproduced on demand, also save it as
   `tests/fixtures/codex/exec-error-rate-limit.jsonl` (the optional third
   fixture; flag the addition in the PR). Otherwise keep the strings inline here.

5. **Auth failure shape** — use an isolated empty Codex home, never the live
   `~/.codex` directory:
   ```
   mkdir -p /tmp/empty-codex-home
   CODEX_HOME=/tmp/empty-codex-home codex exec --json -s workspace-write --skip-git-repo-check --ephemeral "print auth probe and stop" < /dev/null
   ```
   Save stdout as `tests/fixtures/codex/exec-auth-failed.jsonl` when it is
   JSONL. Sanitize request ids, cf-ray values, and local paths.

To regenerate intentionally after a codex upgrade, re-run this sequence and
re-stamp the version; the fixtures are pinned by step-2/3 tests, so gratuitous
re-capture churns them.

---

## Version stamp

- **codex --version:** `codex-cli 0.142.0`
- **Capture date:** `2026-06-23`
- **Scratch-dir OS:** macOS (darwin 25.4.0)

## Structural evaluator capability profile

Structural revision uses a separate fixed evaluator profile. Current
`same-artifact` and `cross-artifact` analyses can admit its one-artifact
exact-pair writer. It accepts only `codex-cli 0.142.0` and only macOS
`/usr/bin/sandbox-exec`; with a matching recorded decoded-text baseline, the
structural route retains its existing behavior. An unavailable evaluator
rejects fact-free before evidence is read or a seed changes. After evaluator
admission and guarded recovery, structural preflight checks the current brief
baseline before rebuilding and validating the exact pair. `changed-brief` and `legacy-brief` refuse
redacted with status `1` and no artifact, baseline, or seed publication; every
other failure — a `requires-scope-review` route included — also refuses before
mutation, with
only an ineligible selected feedback row distinguished from the rest. The
evaluator receives no brief contents and does not bypass its availability check.
Cross-artifact
evidence grants no transaction, second artifact update, or relation change:
the writer publishes only the selected artifact and selected feedback row.
The profile runs this exact inner argv from a fresh empty non-repository root:

```
codex exec --json -C ISOLATED_EMPTY_DIR -s read-only --skip-git-repo-check --ephemeral --ignore-user-config --ignore-rules PROMPT
```

The direct Seatbelt parent denies `file-read*` beneath both the resolved
repository and plans roots after allowing system reads. `file-read*` covers
both file data and metadata access; `-C`, prompt wording, and Codex's
read-only policy are supplementary controls, never substitutes for that outer
denial. The evaluator never consumes normal backend selection, fallbacks, or
configured extra argv.

Before a supported Codex version changes, refresh the sanitized capability
probe and its fixture. The probe records only the JSON terminal-envelope
shape, confirms a deliberate write request is refused, confirms both a data
read and metadata read of a workspace-only sentinel are denied, and confirms
an isolated no-op child starts. It retains no protected path, prompt, reply,
stderr, executable path, configuration, or workspace content.

---

## Batch invocation

The non-streaming codex call, mirroring claude's batch argv in
`plan_tool/shell.py:_run_once`
(`["claude", "-p", "--permission-mode", "acceptEdits", prompt]`).

- **codex argv (captured working form, used by plan-tool batch):**
  `["codex", "exec", "--json", "-s", "workspace-write", "--skip-git-repo-check", "--ephemeral", prompt]`
  with `stdin=DEVNULL` (mandatory — see STATUS note). `--ephemeral` keeps
  automated runs from persisting session files; `-C <dir>` pins the working
  root when cwd differs.
- **Prompt-passing form:** positional argument (verified). `-` reads stdin;
  piped stdin is *appended* to a positional prompt as a `<stdin>` block —
  another reason for `DEVNULL`.
- **Sandbox/approval flag ≈ `--permission-mode acceptEdits`:**
  `-s workspace-write` (verified: file creation executed without any
  per-action prompt under `exec`). `read-only` for audit-flavor calls;
  `danger-full-access` exists but is not the analog.
- **`--skip-git-repo-check` semantics:** per `exec --help`, codex refuses to
  run outside a git repository; the flag relaxes that. Probes ran inside a
  git-inited scratch dir with the flag supplied; keep it in the backend argv
  since plan-tool scratch contexts (e.g. bench tempdirs) may lack `.git`.
- **How the final assistant message is obtained (batch):**
  `-o/--output-last-message <FILE>` writes exactly the final agent message
  (verified byte-exact: `backend probe ok`). Equivalently, under `--json` it
  is the `text` of the last `item.completed` with `item.type ==
  "agent_message"`. The backend uses `--json` + last-agent-message so batch
  and streaming share one parser.
- **Missing-binary exit convention:** keep `shell.py`'s existing
  `shutil.which(<binary>)` guard returning `EXEC_NOT_FOUND_EXIT` (127)
  before spawning — backend-agnostic, no codex-side convention needed.

**Claude correspondence (verified at HEAD):** `_run_once` runs
`subprocess.run(["claude", "-p", "--permission-mode", "acceptEdits", prompt], capture_output=True, text=True)`
and returns `(rc, stdout, stderr, duration_ms, prompt_bytes)`. The missing-binary
fast-path returns `(EXEC_NOT_FOUND_EXIT, "")` *before* spawning.

---

## Streaming invocation

The streaming codex call, mirroring `plan_tool/backend_runner.py:run_streaming_once`'s
Popen argv
(`["claude", "-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits", prompt]`).

- **codex argv (captured working form):**
  `["codex", "exec", "--json", "-s", "workspace-write", "--skip-git-repo-check", "--ephemeral", prompt]`
  with `stdin=DEVNULL`.
- **Output stream:** verified — NDJSON on stdout, one standalone JSON object
  per line, no banner/prefix lines; human-readable notices (e.g. the stdin
  warning) go to stderr.

**Claude correspondence (verified at HEAD):** `run_streaming_once`
(`plan_tool/backend_runner.py`) Popens the argv above with
`stdout=PIPE, stderr=PIPE, text=True`, pumps each stdout line
through the active backend's `parse_stream_line`, and returns
`(returncode, stdout_text, stderr_text, ClaudeRunStats)`. The classifier needs
*both* stdout and stderr because claude surfaces rate-limit copy on either.

---

## Stream event schema

One bullet per codex event type, with the JSON field path the step-3 author maps
onto the launcher's event model in `plan_tool/launcher.py:_parse_stream_line`.

Captured event taxonomy (every line has top-level `type`; work items ride a
nested `item` object with `item.type` and `item.id`):

- **Assistant text event:** `item.completed` with `item.type ==
  "agent_message"`, text at `item.text` → launcher `assistant_text`. The
  *last* such item is the final message.
- **Command-execution events:** `item.started` / `item.completed` with
  `item.type == "command_execution"`; fields `command` (full shell string),
  `aggregated_output`, `exit_code` (null while in_progress), `status`
  (`in_progress`/`completed`) → `item.started` maps to launcher `tool_use`
  (name = "command", input summary = `command`), `item.completed` maps to
  `tool_result`.
- **File-change events:** `item.started` / `item.completed` with
  `item.type == "file_change"`; fields `changes[]` (`{path, kind}` where
  kind ∈ add/…), `status` → `tool_use` (name = "edit", input summary =
  paths+kinds) / `tool_result`.
- **Terminal envelope:** `turn.completed` with `usage{}` → launcher `result`
  branch (success). On failure the stream ends with `error` +
  `turn.failed` instead — see [Terminal envelope](#terminal-envelope).
- **Other event types emitted:** `thread.started` (`thread_id` — the session
  id analog), `turn.started`, `error` (`message`), `turn.failed`
  (`error.message`) → launcher's else-branch except where mapped above.

**Claude correspondence (verified at HEAD).** `_parse_stream_line` keys off the
top-level `type` field of each NDJSON line:

| claude `type` | content handling | launcher event `kind` |
|---|---|---|
| `assistant` / `user` | walks `message.content[]` blocks | per block: `text`→`assistant_text`, `tool_use`→`tool_use`, `tool_result`→`tool_result`, else→block `type` |
| `result` | parses `usage` + `result` text | `result` (terminal; sets `ClaudeRunStats`) |
| anything else | — | `str(type)` or `"unknown"` |

The per-API `request_id` is read off `assistant` events (the `result` envelope
carries only `session_id`); the pump merges the last-seen `request_id` into the
final stats.

---

## Token / usage / cost fields

The exact field paths codex emits. **Mark every field codex does NOT report as
`None`-mapped** — step 3's stats mapping must stay None-safe.

| `ClaudeRunStats` field | claude source (in `result` envelope) | codex source |
|---|---|---|
| `tokens_input` | `usage.input_tokens` | `turn.completed` → `usage.input_tokens` |
| `tokens_output` | `usage.output_tokens` | `turn.completed` → `usage.output_tokens` (note: `usage.reasoning_output_tokens` reported separately; record raw, do not sum) |
| `cache_creation_tokens` | `usage.cache_creation_input_tokens` | **None** (not reported) |
| `cache_read_tokens` | `usage.cache_read_input_tokens` | `turn.completed` → `usage.cached_input_tokens` |
| `cost_usd` | `total_cost_usd` (falls back to `cost_usd`) | **None** (not reported) |
| `request_id` | `request_id` on `assistant` events | `thread.started` → `thread_id` (session-id analog; nearest stable correlator) |
| `final_text` | `result` (string) | `item.text` of the last `item.completed` with `item.type == "agent_message"` |
| `is_error` | `is_error` (bool) | presence of `turn.failed` (terminal) — `turn.completed` means success; process rc is 1 on failure |

These map onto the matching nullable fields on
`plan_tool.run_log.ClaudeCallEnd` (`tokens_input`, `tokens_output`,
`cache_creation_tokens`, `cache_read_tokens`, `request_id`, `cost_usd`) so step 3
can stamp them without coercing types.

---

## Terminal envelope

The single line that marks run completion (codex's equivalent of claude's
`{"type": "result"}`), including how success vs error is signalled.

- **codex terminal event (success):**
  `{"type":"turn.completed","usage":{"input_tokens":26844,"cached_input_tokens":24448,"output_tokens":7,"reasoning_output_tokens":0}}`
  (captured verbatim; see `exec-result-envelope.jsonl`).
- **codex terminal events (failure):** an `{"type":"error","message":...}`
  line followed by `{"type":"turn.failed","error":{"message":...}}`, process
  rc 1. The `message` payload can itself be a JSON-encoded provider envelope
  (captured: nested `{"type":"error","status":400,"error":{"type":
  "invalid_request_error","message":...}}`) — classifiers should match on the
  raw string, not assume a parseable inner structure. See
  `exec-turn-failed.jsonl`.
- **Success vs error signal:** which terminal event arrives —
  `turn.completed` (success, rc 0) vs `turn.failed` (error, rc 1). Mirror
  claude's convention by synthesizing rc 1 if `turn.failed` is seen with a
  zero process exit.

**Claude correspondence (verified at HEAD):** the `{"type": "result", …}`
envelope carries `usage`, `result` (final text), `total_cost_usd`/`cost_usd`,
and `is_error`. `run_streaming_once` (`plan_tool/backend_runner.py`) surfaces
`is_error` on the returned stats, and the launcher synthesizes rc `1` when it
is true and the process still exited 0.

---

## Error shapes

Verbatim codex message text per failure class, so step 3 can extend
`plan_tool/claude_errors.py:classify`. **Step 1 records the strings only; it
changes no regex** (that's step 3).

- **Invalid-request (captured on demand via a bogus `-m` model):**
  `The 'bogus-model-xyz' model is not supported when using Codex with a
  ChatGPT account.` — delivered inside the nested provider envelope on both
  the `error` and `turn.failed` events, rc 1. Classifies UNKNOWN_NONZERO
  (correct: not retryable).
- **Rate-limit / usage-limit:** *not reproducible on demand against a live
  account* — no verbatim capture. Per plan risk note, step 3's pattern set
  errs broad (`usage limit`, `rate limit`, `try again`, `Retry-After`,
  `429` stems — the existing `_RATE_LIMIT_PATTERN` already anticipates this
  flavor); an unmatched phrasing degrades to UNKNOWN_NONZERO (no wait/retry)
  rather than misclassifying. Re-capture opportunistically when one occurs
  in real use and pin it here + as a fixture.
- **Monthly plan quota:** no Codex-specific provider signal is confirmed.
  Codex's broad usage-limit wording remains on its existing rate-limit path
  unless separately evidenced; the Cursor `PLAN_QUOTA` detector does not apply
  to Codex or Claude.
- **Auth failure** (captured by running with an isolated empty `CODEX_HOME`,
  not by modifying the live `~/.codex`): `unexpected status 401 Unauthorized:
  Missing bearer or basic authentication in header` appears on `error` events
  and the terminal `turn.failed` event; the raw transcript is
  `exec-auth-failed.jsonl`. Classifies AUTH: fix credentials / re-run
  `codex login`; do not wait or retry.
- **Context overflow:** *not reproducible cheaply* (would require a
  >context-window prompt through a live call). `_CONTEXT_OVERFLOW_PATTERN`'s
  stems are generic enough to try first; same degrade-to-UNKNOWN policy.
- **Transient** (network/availability): *not captured on demand*;
  `_TRANSIENT_PATTERN`'s stems (timeouts, ECONNRESET, 429) are
  provider-neutral and apply as-is.

**Claude correspondence (verified at HEAD).** `classify(rc, stdout, stderr)`
buckets a non-zero exit through the active backend's patterns. A Cursor-only
confirmed monthly plan quota becomes `PLAN_QUOTA`; Codex's unconfirmed broad
usage wording remains in its rate-limit path. Other recognized outcomes retain
their existing priority order of RATE_LIMIT > CONTEXT_OVERFLOW > TRANSIENT >
UNKNOWN_NONZERO over the combined `f"{stdout}\n{stderr}"`:

- `_RATE_LIMIT_PATTERN`: `rate[- ]?limit|too many requests|usage limit|try again at|Retry-After` (plus the claude-only `You've hit your limit`).
- `_CONTEXT_OVERFLOW_PATTERN`: `prompt is too long|input too long|too many tokens|maximum (context|tokens)|context (length|window|size)…(exceed|limit)|exceed…max…(context|tokens)|reduc(e|ing)…token`.
- `_TRANSIENT_PATTERN`: `timed out|timeout|ECONNRESET|EAI_AGAIN|network error|temporarily unavailable|connection reset|connection was closed|socket hang ?up|\b429\b|overloaded|internal server error|bad gateway|service unavailable|\b5(0[023]|29)\b|response above may be incomplete` (the middle alternations cover Anthropic server-side overload / 5xx, which are retryable but carry no 429; the final one catches a mid-stream turn abort whose only tail is `…The response above may be incomplete.`).

---

## codex⇄claude mapping table

The lookup step 3 uses instead of re-deriving. Left column verified at HEAD;
right column awaits the probe. Covers every `ClaudeRunStats` field and every
`ClaudeFailureKind`.

### Stats / events

| launcher event or `ClaudeRunStats` field | claude source | codex source | notes |
|---|---|---|---|
| `assistant_text` | `assistant`/`user` → `message.content[].text` | `item.completed` / `item.type=="agent_message"` → `item.text` | |
| `tool_use` | `content[].type == "tool_use"` (`name`, `input`) | `item.started` / `item.type` ∈ {`command_execution`, `file_change`} → `item.command` / `item.changes[]` | |
| `tool_result` | `content[].type == "tool_result"` | `item.completed` of the same item types → `item.aggregated_output` / `item.exit_code` / `item.status` | |
| `result` (terminal) | `type == "result"` | `type == "turn.completed"` (or `turn.failed` on error) | sets stats |
| `tokens_input` | `usage.input_tokens` | `usage.input_tokens` | |
| `tokens_output` | `usage.output_tokens` | `usage.output_tokens` | `reasoning_output_tokens` separate |
| `cache_creation_tokens` | `usage.cache_creation_input_tokens` | **None** | not reported |
| `cache_read_tokens` | `usage.cache_read_input_tokens` | `usage.cached_input_tokens` | |
| `cost_usd` | `total_cost_usd` / `cost_usd` | **None** | not reported |
| `request_id` | `assistant` event `request_id` | `thread.started` → `thread_id` | session-id analog |
| `final_text` | `result` string | last `agent_message` item `text` | `-o FILE` equivalent |
| `is_error` | `is_error` bool | terminal event is `turn.failed` | rc 1 on failure |

### Failure kinds (`ClaudeFailureKind`)

| `ClaudeFailureKind` | claude pattern | codex string | notes |
|---|---|---|---|
| `SUCCESS` | `rc == 0` | `rc == 0` | identical |
| `RATE_LIMIT` | `_RATE_LIMIT_PATTERN` (+ `parse_reset_epoch`) | **not captured** — pattern errs broad (`usage limit` / `rate limit` / `try again` / `Retry-After` / `429` stems); unmatched degrades to UNKNOWN_NONZERO | re-pin verbatim when first observed live |
| `PLAN_QUOTA` | backend-specific confirmed monthly plan-quota matcher | no confirmed Codex signal; Cursor-only detector is not reused here | terminal when a provider-specific matcher confirms it; no policy wait/switch/ask action |
| `CONTEXT_OVERFLOW` | `_CONTEXT_OVERFLOW_PATTERN` | **not captured** — generic stems apply first | |
| `TRANSIENT` | `_TRANSIENT_PATTERN` | **not captured** — stems are provider-neutral, apply as-is | |
| `UNKNOWN_NONZERO` | fallthrough | fallthrough (incl. the captured invalid-request envelope — see `exec-turn-failed.jsonl`) | identical |
| `AUTH` | backend-specific `auth_pattern` | `401 Unauthorized: Missing bearer or basic authentication in header` (captured with isolated empty `CODEX_HOME`; see `exec-auth-failed.jsonl`) | no wait/retry; fix credentials |

---

## Sanitization

A committed fixture is published data. Before saving any `*.jsonl` or pasting a
transcript:

- Replace any auth token, API key, or account id (from `~/.codex/auth.json`) with
  a clearly-fake placeholder of the **same key/type/length class**.
- Replace absolute home/cwd paths with a stable placeholder (e.g. `/scratch`).
- Keep session/request ids only if they carry no secret; otherwise replace with
  a fixed fake.
- **Do not alter schema-bearing fields** (event types, token counts, envelope
  keys) — those are the contract under test.
- Capture verbatim and in emission order; do not pretty-print (step-3 tests parse
  line-by-line the way `_parse_stream_line` does).

---

## Verification checklist

Run after the probe fills the placeholders and saves the fixtures:

- [ ] `codex --version` recorded as a concrete string (not a placeholder).
- [ ] Every `TODO(probe)` replaced with a captured value (or an explicit "not
      reported by codex").
- [ ] `tests/fixtures/codex/exec-stream-sample.jsonl` and
      `exec-result-envelope.jsonl` exist; each line parses as standalone JSON
      (`python -c "import json,sys; [json.loads(l) for l in open(p) if l.strip()]"`).
- [ ] No auth token, API key, account id, or real home path in any committed
      artifact (`git diff --cached` review).
- [ ] Mapping tables cover every `ClaudeRunStats` field and every
      `ClaudeFailureKind` (mapped or explicitly unreported).
- [ ] `exec-result-envelope.jsonl` lets a reader extract token counts without the
      full stream.

---

## References

- [openai/codex (CLI repo)https: — `codex exec`, the
  `--json` event stream, sandbox/approval flags. Confirm flag names against the
  **installed version**, not the README.
- [Codex CLI config & sandbox docshttps:
  — `~/.codex/config.toml` keys and sandbox modes.
- `plan_tool/backend_runner.py` — `run_streaming_once`: the streaming
  supervisor the codex schema maps onto; the per-backend
  `parse_stream_line` parsers and `ClaudeRunStats` live in
  `plan_tool/backend.py`.
- `plan_tool/shell.py` — `_run_once`, `EXEC_NOT_FOUND_EXIT`: the batch argv and
  missing-binary convention.
- `plan_tool/claude_errors.py` — `classify`, `ClaudeFailureKind.PLAN_QUOTA`,
  `_RATE_LIMIT_PATTERN`, `_CONTEXT_OVERFLOW_PATTERN`, `_TRANSIENT_PATTERN`,
  `parse_reset_epoch`, `_RESET_PATTERNS`: the failure taxonomy; the confirmed
  plan-quota matcher remains Cursor-specific.
- `plan_tool/run_log.py` — `ClaudeCallEnd`: the nullable stats fields step 3
  stamps.
- `TESTING.md` "Real-claude fallback seams" — the subprocess guard step 2
  generalizes to block any registered backend binary; these fixtures exist so
  step-3 tests never shell out to real codex.
