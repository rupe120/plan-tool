# Model window sources

*Part of the plan-tool developer docs. Start at [Contributing](../../../CONTRIBUTING.md).*

**Purpose.** Names the two external shapes `plan_tool/context_window.py` and `plan_tool/backend.py` read to
learn a model's context window, and the CLI versions they were observed on. A rename on either side makes
every lookup return "not known" and the advisory fall back to `(default)`; this page says which keys to check.

| Source | Where | Keys read | Observed on |
| --- | --- | --- | --- |
| Codex model catalog | `models_cache.json` under `$CODEX_HOME` (default `~/.codex`), refreshed by `codex debug models` | `models[].slug`, `models[].context_window`, `models[].effective_context_window_percent` (default 100 when absent) | Codex CLI 0.162.0, 2026-10-09 |
| Claude result envelope | the terminal `{"type": "result"}` stream-json line | `modelUsage.<model id>.contextWindow` | Claude Code with `claude-sonnet-5-5`, 2026-10-09 |

The usable Codex window is `context_window` × `effective_context_window_percent` / 100; the catalog also
lists `max_context_window` (not read) and `supports_experimental_context`.

One trimmed real sample of each shape is kept as a test fixture so a shape change is a failing test:
`_REAL_CODEX_ENTRY` in `tests/test_context_window.py` and `_REAL_CLAUDE_MODEL_USAGE` in `tests/test_backend.py`. Neither CLI documents these keys as a
stable interface.
