# Cursor Agent CLI contract

Reference contract for the Cursor Agent CLI (`agent`) as a plan-tool execution
backend. The cursor backend normalizes the agent's `--output-format stream-json`
NDJSON onto the launcher's existing event model.

The agent stream shares claude-shaped `assistant` / `user` message blocks but
uses separate `tool_call` events (not embedded `tool_use` blocks) and camelCase
usage fields on the terminal `result` envelope. **Version drift is likely** — the
values below are captured ground truth from a real installed binary, and the
fixtures under `tests/fixtures/cursor/` are what the backend tests parse.

---

## STATUS: CAPTURED — probed against the real binary 2026-06-23

- **agent --version:** `2026.06.24-00-45-58-9f61de7`
- **Capture date:** `2026-06-23`
- **Scratch-dir OS:** macOS (darwin 25.5.0)

Fixtures:

| File | Contents |
| --- | --- |
| `tests/fixtures/cursor/agent-result-envelope.jsonl` | Simple reply + terminal `result` |
| `tests/fixtures/cursor/agent-command-execution.jsonl` | Shell tool call + final `result` |

---

## Batch invocation

Headless batch and streaming use the same argv — there is no separate batch
mode:

```
agent -p --output-format stream-json --force --trust <prompt>
```

| Flag | Role |
| --- | --- |
| `-p` / `--print` | Non-interactive mode; required for subprocess use |
| `--output-format stream-json` | NDJSON event stream on stdout |
| `--force` / `--yolo` | Auto-approve tool calls (equivalent to claude `acceptEdits`) |
| `--trust` | Trust the workspace without a prompt (required headless) |
| `--model <id>` | Optional model override (plan-tool splices via `model_flag`) |

**Stdin:** pass `stdin=subprocess.DEVNULL` — inherited stdin can block or
contaminate the prompt.

**Batch output:** `batch_output="json"`. `shell._normalize_batch_stdout`
parses the JSONL and returns the terminal `result.result` string (same contract
as codex batch normalization).

---

## Streaming event mapping

| Agent event | Launcher mapping |
| --- | --- |
| `type: system` | passthrough `kind=system` |
| `type: user` / `assistant` → `message.content[]` | `assistant_text` / embedded `tool_use` / `tool_result` (claude-shaped blocks) |
| `type: tool_call`, `subtype: started` | `tool_use` — `shellToolCall.args.command` → `("command", …)`; path-like args → `("edit", …)` |
| `type: tool_call`, `subtype: completed` | `tool_result` |
| `type: result` | terminal `result` + stats |

### Terminal `result` envelope

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "<final assistant text>",
  "request_id": "<per-request id>",
  "session_id": "<session id>",
  "usage": {
    "inputTokens": 48299,
    "outputTokens": 40,
    "cacheReadTokens": 1152,
    "cacheWriteTokens": 0
  }
}
```

| `ClaudeRunStats` field | Agent source |
| --- | --- |
| `final_text` | `result` (string) |
| `tokens_input` | `usage.inputTokens` |
| `tokens_output` | `usage.outputTokens` |
| `cache_read_tokens` | `usage.cacheReadTokens` |
| `cache_creation_tokens` | `usage.cacheWriteTokens` |
| `cost_usd` | not reported (`None`) |
| `request_id` | `request_id` on the result envelope |
| `is_error` | `is_error` or `subtype != "success"` |

---

## Error shapes

Auth failures observed on **stderr** with no JSONL (exit non-zero):

- `Authentication required. Please run 'agent login' first, or set CURSOR_API_KEY environment variable.`
- `Warning: The provided API key is invalid.` (when `CURSOR_API_KEY` is wrong)

Credentials: `agent login` (interactive) or `CURSOR_API_KEY` env var.

The confirmed Cursor monthly plan-quota shape requires all of these portions in
the same failure output:

> `ActionRequiredError: You've hit your usage limit for Opus. Switch to a different model or set a Spend Limit. Your usage limits will reset when your monthly cycle ends on 8/24/2026.`

`8/24/2026` exemplifies the provider's displayed **calendar date**, not a local
reset time or a retry timer. This Cursor-only match classifies as
`ClaudeFailureKind.PLAN_QUOTA` and is terminal for the current call: it returns
after the failed attempt without waiting, prompting, choosing a fallback
backend, backing off, consulting the retry guard, or retrying. Resolve the
provider quota or wait for Cursor's actual reset, then begin a new command
invocation.

Other Cursor rate-limit, context-overflow, and transient copy continues through
the shared classification patterns. An ordinary short rate limit therefore
keeps the existing policy-driven recovery behavior.

---

## Sandbox / approval mapping

| Claude | Cursor Agent |
| --- | --- |
| `--permission-mode acceptEdits` | `-p --force --trust` |

There is no git-repo guard flag — the agent uses the process/spawn cwd as its
workspace (`backend.spawn_cwd` scopes this for plan-tool entrypoints).

---

## Re-capture procedure

After an agent upgrade, re-run in a scratch directory:

```bash
agent --version
agent -p --output-format stream-json --force --trust "Reply with exactly: backend probe ok" \
  > tests/fixtures/cursor/agent-result-envelope.jsonl
agent -p --output-format stream-json --force --trust "Run: echo tool_probe_ok" \
  > tests/fixtures/cursor/agent-command-execution.jsonl
uv run pytest tests/test_backend.py -q -k cursor
```

Sanitize session/request ids if committing transcripts from a live account.
