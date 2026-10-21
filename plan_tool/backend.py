"""CLI-backend seam: one descriptor per subprocess CLI plan-tool drives.

A :class:`CliBackend` bundles everything that used to be inlined about
the ``claude`` CLI across three independent call sites — the batch argv
in :func:`plan_tool.shell._run_once`, the streaming argv + NDJSON event
model in :mod:`plan_tool.launcher`, and the failure-classification
regexes in :mod:`plan_tool.claude_errors`. Centralizing them here means
a second backend (codex, in a later step) is registered as data — one
more ``CliBackend(...)`` literal — without re-editing any call site.

Import topology is load-bearing: this module is the leaf below
``claude_errors`` / ``shell`` / ``launcher``, so it must import only
stdlib (never those three) to keep the dependency order acyclic. That
constraint is why :class:`ClaudeRunStats`, :class:`_StreamLineParse`,
and the stream-line parser live here rather than in ``launcher`` —
``launcher`` re-exports ``ClaudeRunStats`` so its callers are unchanged.

Public surface:

- :class:`CliBackend` — the frozen descriptor (binary, argv builders,
  stream-line parser, classification patterns).
- :data:`CLAUDE_BACKEND` — the default registered implementation.
- :func:`get_active_backend` / :func:`set_active_backend` /
  :func:`scoped_active_backend` — read / swap the process-wide active
  backend or install a scoped override; ``cli.main`` resolves flags,
  environment, and model-family selection before it calls this seam.
- :func:`resolve_backend` — map a selection name to its registered
  backend (raises on an unknown name).
- :func:`build_effective_backend` — splice per-project extra argv + a
  model pair before the prompt of a base backend's argv builders,
  producing a transient *effective* backend ``cli.main`` activates at
  selection (the registry seeds stay untouched).
- :func:`select_active_backend` / :func:`scoped_select_active_backend` —
  resolve a backend name, apply per-project overrides, build the
  effective backend, and activate it globally or for one scope.
- :func:`register_backend` — add a backend to the registry.
- :func:`registered_binaries` — every registered backend's executable
  name; consumed by the test-suite's real-subprocess guard so new
  backends are auto-blocked.
- :func:`observe_context_window` / :func:`observed_context_window` /
  :func:`reported_window_for_model` — the process-wide registry of context
  windows a call's result envelope reported; written by ``backend_runner``,
  read by ``plan_tool.context_window`` (docs/ARCHITECTURE.md § "Prompt-budget
  window").
- :func:`discover_and_register_backends` — iterate the packaged
  ``integrations/*/backend.json`` manifests and register each over the
  in-code seed; auto-called once at import.
"""

from __future__ import annotations

import functools
import importlib.resources
import inspect
import json
import re
import threading
import warnings
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Callable, Collection, Iterator, Optional, Sequence


class BackendManifestError(Exception):
    """Raised when a ``backend.json`` manifest is malformed or unresolvable.

    Surfaced verbatim by :func:`load_backend_from_dir` — the message
    names the offending manifest file and field. Modeled on
    :class:`plan_tool.jira_config.JiraConfigError`: malformed JSON, a
    missing required field, or a ``parser`` discriminator with no
    registered parse function each raise this rather than a raw
    ``KeyError`` / ``TypeError`` from deep in the loader.
    """


@dataclass(frozen=True)
class BackendSelection:
    """Result of selecting and activating an effective backend.

    ``selected`` is the registered or synthesized seed descriptor named by
    the caller. ``effective`` is the transient descriptor installed as the
    process-wide active backend after project argv/model overrides are
    applied. ``unknown_override_names`` lists config keys from
    ``.plan-tool/backends.json`` that do not name a registered or
    caller-approved backend; CLI code owns how to present those warnings.
    """

    selected: "CliBackend"
    effective: "CliBackend"
    unknown_override_names: tuple[str, ...] = ()


# Tool-input summary cap. ``run_log._MAX_LINE_BYTES`` is 4096; the
# string-level truncation in ``_append_jsonl_line`` would catch a long
# input on its own, but capping at the source keeps the event payload
# small *before* serialization and matches the field's docstring in
# ``run_log.ClaudeStreamEvent``.
_TOOL_INPUT_SUMMARY_CAP = 200

# Known secret-prefix shapes: an ``Authorization:``/``Bearer ``-carried
# token, or a bare token starting with one of the listed provider prefixes
# (``sk-`` OpenAI-style, ``ghp_``/``gho_`` GitHub, ``AKIA`` AWS access key,
# ``xox`` Slack). The whole match (prefix included) is replaced — over-
# redacting the label alongside the value is an accepted cost.
_SECRET_PREFIX_TOKEN_RE = re.compile(
    # ``Authorization:`` first, so it also swallows an immediately-following
    # ``Bearer `` rather than leaving the token after it unmatched; the
    # standalone ``Bearer\s+\S+`` alternative then covers a bare
    # ``Bearer <token>`` with no ``Authorization:`` label preceding it.
    r"(?:Authorization:\s*(?:Bearer\s+)?\S+"
    r"|Bearer\s+\S+"
    r"|\bsk-[A-Za-z0-9_-]+"
    r"|\bghp_[A-Za-z0-9_-]+"
    r"|\bgho_[A-Za-z0-9_-]+"
    r"|\bAKIA[A-Za-z0-9]+"
    r"|\bxox[A-Za-z0-9_-]+)"
)

# Any other contiguous run of 20+ alphanumeric/-/_ characters is a candidate
# for the length/character-class heuristic below — not true entropy scoring,
# so a long hash/UUID/commit SHA is accepted collateral (over-redaction is
# the accepted failure mode; under-redaction is not).
_HIGH_ENTROPY_RUN_RE = re.compile(r"[A-Za-z0-9_-]{20,}")


def _looks_high_entropy(run: str) -> bool:
    """True when ``run`` mixes at least two of upper/lower/digit."""
    classes = 0
    if any(c.isupper() for c in run):
        classes += 1
    if any(c.islower() for c in run):
        classes += 1
    if any(c.isdigit() for c in run):
        classes += 1
    return classes >= 2


def _redact_secrets(text: str) -> str:
    """Replace known secret shapes in ``text`` with ``[REDACTED]``.

    Two independent passes, in order: a known secret-prefix token first
    (``Authorization:``/``Bearer ``, or a bare ``sk-``/``ghp_``/``gho_``/
    ``AKIA``/``xox``-prefixed token), then any other 20+ character mixed-
    class run the first pass left untouched. Called on a branch's own
    untruncated candidate string *before* the ``_TOOL_INPUT_SUMMARY_CAP``
    slice — redacting an already-truncated string could leak a secret's
    leading bytes for anything long enough to straddle the cutoff.
    """
    if not text:
        return text
    text = _SECRET_PREFIX_TOKEN_RE.sub("[REDACTED]", text)
    return _HIGH_ENTROPY_RUN_RE.sub(
        lambda m: "[REDACTED]" if _looks_high_entropy(m.group(0)) else m.group(0),
        text,
    )


def redact_sensitive_text(text: str) -> str:
    """Return text with known secret shapes removed."""
    return _redact_secrets(text)


@dataclass(frozen=True)
class ClaudeRunStats:
    """Aggregate stats captured from one ``claude -p --output-format stream-json`` run.

    Populated by :func:`plan_tool.launcher._run_streaming_once` from the
    terminal ``{"type": "result"}`` envelope. Threaded back through
    :func:`plan_tool.launcher.shell_invoker` to ``run_step`` via the
    ``shell_invoker._last_stats`` sentinel attribute so the public
    ``Invoker`` shape (``Callable[[str], tuple[int, str]]``) — and the
    20+ fake invokers wired through the test suite — stays unchanged.

    ``final_text`` is the post-tool assistant response that
    ``extract_summary`` should prefer over the raw stdout buffer. The
    rest mirror the matching nullable fields on
    :class:`plan_tool.run_log.ClaudeCallEnd` so the structured event can
    be stamped without coercing types.
    """

    final_text: str = ""
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cache_creation_tokens: Optional[int] = None
    cache_read_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    request_id: Optional[str] = None
    is_error: bool = False
    # Whether ``tokens_input`` already counts the cached tokens. ``None`` =
    # the backend's accounting is not established (deliberately so for cursor).
    input_includes_cached: Optional[bool] = None
    # Every ``modelUsage`` entry's ``(model id, contextWindow)``; see ``reported_window_for_model``.
    model_windows: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class _StreamLineParse:
    """Outcome of parsing one NDJSON line from ``claude --output-format
    stream-json``. Bundled so the stdout pump can apply text /
    state-update / event-emit fan-out in one pass.
    """

    events: tuple[dict[str, object], ...]  # kwargs for ``claude_stream_event``
    text_chunks: tuple[str, ...]  # text to append to the stdout buffer
    stats: Optional[ClaudeRunStats]  # only set for the terminal result envelope
    last_tool: Optional[str]
    last_activity_kind: Optional[str]
    # ``request_id`` lives on ``assistant`` events in the claude
    # stream-json schema (the terminal ``result`` envelope only carries
    # ``session_id``). The pump tracks the most recent one across lines
    # and merges it into ``stats`` when the result envelope arrives so
    # ``ClaudeCallEnd`` records the per-API-request id, not the session.
    request_id_hint: Optional[str] = None


@dataclass(frozen=True)
class PromptTransport:
    """Concrete command + optional stdin payload for one backend prompt.

    Most shipped backends receive the prompt as their final argv element.
    Some CLI shapes are cleaner when the prompt travels on stdin. This
    small value object is the shared contract between backend descriptors
    and the two subprocess sites, so neither caller has to infer prompt
    placement from ``argv[-1]``.
    """

    argv: list[str]
    stdin_text: Optional[str] = None

    @property
    def prompt_bytes(self) -> int:
        """Bytes of the transported prompt payload for run-log accounting."""
        prompt_text = (
            self.stdin_text if self.stdin_text is not None else self.argv[-1]
        )
        return len(prompt_text.encode("utf-8"))

    def with_args_before_prompt(self, args: Sequence[str]) -> "PromptTransport":
        """Insert argv flags before the argv-carried prompt, or at argv tail.

        For stdin-carried prompts there is no argv prompt sentinel, so extra
        flags are appended to the command head. For argv-carried prompts the
        historical splice point remains immediately before ``argv[-1]``.
        """
        if not args:
            return self
        if self.stdin_text is not None:
            return PromptTransport([*self.argv, *args], self.stdin_text)
        return PromptTransport([*self.argv[:-1], *args, self.argv[-1]])


def _summarize_tool_input(tool_name: str, inp: object) -> str:
    """Render a 200-char preview of a ``tool_use`` block's ``input``.

    Tool-specific shortcuts match the ones called out in the canonical
    plan (``Edit``/``Write``/``Read`` → ``file_path``; ``Bash`` →
    ``command``; ``Grep``/``Glob`` → ``pattern in path``). Everything
    else falls back to a JSON-encoded preview so a future tool name we
    haven't enumerated still produces a recognizable summary.

    Each branch's own untruncated candidate string is redacted (see
    :func:`_redact_secrets`) before the ``_TOOL_INPUT_SUMMARY_CAP`` slice —
    redact-then-truncate, never the reverse.
    """
    if not isinstance(inp, dict):
        try:
            preview = json.dumps(inp, ensure_ascii=False)
        except (TypeError, ValueError):
            preview = str(inp)
        return _redact_secrets(preview)[:_TOOL_INPUT_SUMMARY_CAP]
    if tool_name in ("Edit", "Write", "Read", "NotebookEdit"):
        return _redact_secrets(
            str(inp.get("file_path", ""))
        )[:_TOOL_INPUT_SUMMARY_CAP]
    if tool_name == "Bash":
        return _redact_secrets(
            str(inp.get("command", ""))
        )[:_TOOL_INPUT_SUMMARY_CAP]
    if tool_name in ("Grep", "Glob"):
        pattern = str(inp.get("pattern", ""))
        path = str(inp.get("path", "") or "")
        if path:
            return _redact_secrets(f"{pattern} in {path}")[:_TOOL_INPUT_SUMMARY_CAP]
        return _redact_secrets(pattern)[:_TOOL_INPUT_SUMMARY_CAP]
    try:
        preview = json.dumps(inp, ensure_ascii=False)
    except (TypeError, ValueError):
        preview = str(inp)
    return _redact_secrets(preview)[:_TOOL_INPUT_SUMMARY_CAP]


def _claude_parse_stream_line(
    line: str, *, bytes_in: int
) -> Optional[_StreamLineParse]:
    """Parse one claude stream-json NDJSON line into a :class:`_StreamLineParse`.

    Returns ``None`` when the line isn't valid JSON or isn't a dict —
    callers fall back to treating the raw line as plain stdout so
    transport-layer errors / rate-limit copy that claude surfaces as
    non-JSON still reach the failure classifier.
    """
    stripped = line.strip()
    if not stripped:
        return None
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None

    events: list[dict[str, object]] = []
    text_chunks: list[str] = []
    stats: Optional[ClaudeRunStats] = None
    last_tool: Optional[str] = None
    last_activity_kind: Optional[str] = None
    request_id_hint: Optional[str] = None

    obj_type = obj.get("type")

    if obj_type == "result":
        usage_raw = obj.get("usage")
        usage = usage_raw if isinstance(usage_raw, dict) else {}
        final_text = obj.get("result")
        if isinstance(final_text, str) and final_text:
            text_chunks.append(final_text)
            if not final_text.endswith("\n"):
                text_chunks.append("\n")
        cost = obj.get("total_cost_usd")
        if cost is None:
            cost = obj.get("cost_usd")
        # ``request_id`` is intentionally NOT taken from the result
        # envelope: that field carries ``session_id`` (shared across
        # multi-turn calls), not the per-API-request id. The pump merges
        # in the request_id captured from the last ``assistant`` event.
        stats = ClaudeRunStats(
            final_text=final_text if isinstance(final_text, str) else "",
            tokens_input=usage.get("input_tokens"),
            tokens_output=usage.get("output_tokens"),
            cache_creation_tokens=usage.get("cache_creation_input_tokens"),
            cache_read_tokens=usage.get("cache_read_input_tokens"),
            cost_usd=cost if isinstance(cost, (int, float)) else None,
            request_id=None,
            is_error=bool(obj.get("is_error", False)),
            input_includes_cached=(
                False if usage.get("input_tokens") is not None else None
            ),
            model_windows=_reported_model_windows(obj.get("modelUsage")),
        )
        events.append({"kind": "result", "bytes_in_delta": bytes_in})
        last_activity_kind = "result"
    elif obj_type in ("assistant", "user"):
        # The assistant event is the only place the per-API-request id
        # appears in claude stream-json output; capture it so the pump
        # can attach it to the final ``ClaudeRunStats`` when the result
        # envelope arrives.
        if obj_type == "assistant":
            rid = obj.get("request_id")
            if isinstance(rid, str) and rid:
                request_id_hint = rid
        message = obj.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "text":
                    text = block.get("text") or ""
                    if isinstance(text, str) and text:
                        text_chunks.append(text)
                    text_bytes = (
                        len(text.encode("utf-8"))
                        if isinstance(text, str) else 0
                    )
                    events.append({
                        "kind": "assistant_text",
                        "bytes_in_delta": text_bytes,
                    })
                    last_activity_kind = "assistant_text"
                elif block_type == "tool_use":
                    name = str(block.get("name") or "")
                    inp = block.get("input") or {}
                    summary = _summarize_tool_input(name, inp)
                    events.append({
                        "kind": "tool_use",
                        "tool_name": name or None,
                        "tool_input_summary": summary or None,
                        "bytes_in_delta": bytes_in,
                    })
                    if name:
                        last_tool = name
                    last_activity_kind = "tool_use"
                elif block_type == "tool_result":
                    events.append({
                        "kind": "tool_result",
                        "bytes_in_delta": bytes_in,
                    })
                    last_activity_kind = "tool_result"
                else:
                    kind = str(block_type) if block_type else str(obj_type)
                    events.append({
                        "kind": kind,
                        "bytes_in_delta": bytes_in,
                    })
                    last_activity_kind = kind
        else:
            events.append({
                "kind": str(obj_type),
                "bytes_in_delta": bytes_in,
            })
            last_activity_kind = str(obj_type)
    else:
        kind = str(obj_type) if obj_type else "unknown"
        events.append({"kind": kind, "bytes_in_delta": bytes_in})
        last_activity_kind = kind

    return _StreamLineParse(
        events=tuple(events),
        text_chunks=tuple(text_chunks),
        stats=stats,
        last_tool=last_tool,
        last_activity_kind=last_activity_kind,
        request_id_hint=request_id_hint,
    )


# ---------------------------------------------------------------------------
# Classification patterns (relocated from ``claude_errors``).
#
# Ported from run-validation-dataset.sh:check_rate_limit and
# check_usage_or_token_limit. Kept as compiled re.Pattern objects so
# ``classify`` doesn't recompile per call.
# ---------------------------------------------------------------------------

# Claude-specific user-facing copy (Codex strings stay in the broader
# usage pattern below). Allow an optional qualifier between "your" and
# "limit" ("your session/usage/weekly limit"); the "You've" prefix is
# dropped so a curly-apostrophe variant still matches.
_CLAUDE_PROVIDER_LIMIT_PATTERN = re.compile(
    r"hit your (?:\w+\s+)?limit", re.IGNORECASE
)

# Generic rate / usage / quota patterns. Deliberately omits a bare "429"
# (no quota copy = more often a transient blip → TRANSIENT branch).
# ``session limit`` + ``resets <digit>`` catch Claude Code's "hit your
# session limit · resets 4:20pm" banner; the digit guard keeps "resets"
# off prose like "the loop resets state".
_CLAUDE_RATE_LIMIT_PATTERN = re.compile(
    r"(rate[- ]?limit|too many requests|usage limit|session limit"
    r"|try again at|Retry-After|resets?\s+\d)",
    re.IGNORECASE,
)

# Context-window overflow patterns. Distinct from rate-limit because
# waiting will not fix it; the caller must shrink the prompt.
_CLAUDE_CONTEXT_OVERFLOW_PATTERN = re.compile(
    r"("
    r"prompt is too long"
    r"|input too long"
    r"|too many tokens"
    r"|maximum[ \t]+(context|tokens)"
    r"|context[ \t]+(length|window|size).*(exceed|limit)"
    r"|exceed(ed)?[ \t]+(the[ \t]+)?max(imum)?[ \t]+(context|tokens)"
    r"|reduc(e|ing).*token"
    r")",
    re.IGNORECASE,
)

# Transient network / availability failures that justify a backoff
# retry (separate from rate-limit because the recovery cadence is
# different — a few seconds, not minutes-to-an-hour).
_CLAUDE_TRANSIENT_PATTERN = re.compile(
    r"("
    r"timed out|timeout"
    r"|ECONNRESET|EAI_AGAIN"
    r"|network error"
    r"|temporarily unavailable"
    r"|connection reset"
    # Node-fetch's dropped-connection wordings: "The socket connection
    # was closed unexpectedly" and "socket hang up".
    r"|connection was closed"
    r"|socket hang ?up"
    r"|\b429\b"
    # Anthropic server-side overload / 5xx. These are retryable on a
    # short backoff but their wording carries no 429, so without these
    # alternations classify() falls through to UNKNOWN_NONZERO (no
    # retry) and a one-off overload aborts the call. Rate-limit
    # precedence is unaffected — classify() checks the rate-limit
    # pattern first, so a 429 that also says "overloaded" still
    # classifies as RATE_LIMIT.
    r"|overloaded"
    r"|internal server error"
    r"|bad gateway"
    r"|service unavailable"
    # 500/502/503 plus 529 (Anthropic's documented overload status).
    r"|\b5(0[023]|29)\b"
    # Mid-stream turn abort whose only tail is "…response above may be
    # incomplete." — an API-side transient with no other keyword, so it
    # would otherwise fall to UNKNOWN_NONZERO (no retry). Kept specific,
    # not a broad "api error", to avoid retrying deterministic 4xx.
    r"|response above may be incomplete"
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CliBackend:
    """Descriptor for one subprocess CLI plan-tool can drive.

    Carries callables (the argv builders + stream-line parser) and the
    failure-classification patterns rather than subclassing an ABC: the
    seam was extracted by *relocating* existing function bodies, and a
    second backend is a second ``CliBackend(...)`` literal pointing at
    its own module functions — no class hierarchy to maintain.

    Fields:

    - ``name`` — registry key / selection key (e.g. ``"claude"``).
    - ``binary`` — executable for ``shutil.which`` and the argv head.
    - ``batch_argv`` — prompt → the batch (capture-output) command line.
    - ``batch_prompt_transport`` — optional prompt → argv/stdin transport
      descriptor for batch calls; defaults to argv-carried prompt via
      ``batch_argv``.
    - ``batch_output`` — ``"stdout"`` or ``"json"``, persisted per backend and
      round-tripped through ``backend.json``. Unconsulted at runtime since the
      batch lane moved onto the shared streaming runner (``backend_runner.py``,
      ``batch-authoring-observability`` step 6): ``_pump_stdout`` always calls
      ``parse_stream_line`` regardless of this value. See ``BACKLOG.md`` for
      whether it should be wired back in or dropped from the schema.
    - ``streaming_argv`` — prompt → the streaming (NDJSON) command line.
    - ``streaming_prompt_transport`` — optional prompt → argv/stdin transport
      descriptor for streaming calls; defaults to argv-carried prompt via
      ``streaming_argv``.
    - ``parse_stream_line`` — one NDJSON line → normalized parse (or
      ``None`` for a non-JSON line).
    - ``rate_limit_pattern`` / ``provider_limit_pattern`` /
      ``context_overflow_pattern`` / ``transient_pattern`` — the
      compiled failure-classification regexes ``classify`` consults.
    - ``auth_pattern`` — optional compiled regex matching the backend's
      unauthenticated copy. ``None`` for backends with no distinct auth
      shape (claude today); set for codex. ``classify`` only emits
      ``ClaudeFailureKind.AUTH`` when this is non-``None`` and matches.
    - ``plan_quota_pattern`` — optional compiled regex for a provider's
      confirmed monthly plan-quota copy. ``None`` leaves generic rate-limit
      classification unchanged.
    - ``model_flag`` — the flag name (``"--model"`` / ``"-m"``) that
      pairs with a model value; inert until the ``--model`` step splices
      it into argv. ``None`` = the backend takes no model flag.
    - ``default_model`` — the manifest's default model, or ``None`` to
      inject no model pair (today's behavior).
    - ``resolved_model`` — the model selected for this active invocation,
      kept separate from the manifest default. ``None`` means no model was
      resolved for this invocation.

    The argv callables and the compiled patterns are ``field(compare=False)``:
    a loaded backend curries *fresh* argv closures (two closures never
    compare ``==``) and ``re.Pattern`` has no value equality, so leaving
    either in the generated ``__eq__`` would make the manifest round-trip
    golden impossible. Argv fidelity is verified by builder output and
    pattern fidelity by ``.pattern`` / ``.flags`` value, separately.
    """

    name: str
    binary: str
    batch_argv: Callable[[str], list[str]] = field(compare=False)
    streaming_argv: Callable[[str], list[str]] = field(compare=False)
    parse_stream_line: Callable[..., Optional[_StreamLineParse]]
    rate_limit_pattern: "re.Pattern[str]" = field(compare=False)
    provider_limit_pattern: "re.Pattern[str]" = field(compare=False)
    context_overflow_pattern: "re.Pattern[str]" = field(compare=False)
    transient_pattern: "re.Pattern[str]" = field(compare=False)
    auth_pattern: "Optional[re.Pattern[str]]" = field(compare=False, default=None)
    plan_quota_pattern: "Optional[re.Pattern[str]]" = field(
        compare=False, default=None
    )
    model_flag: Optional[str] = None
    default_model: Optional[str] = None
    resolved_model: Optional[str] = field(default=None, compare=False)
    batch_output: str = "stdout"
    batch_prompt_transport: Optional[Callable[[str], PromptTransport]] = field(
        compare=False, default=None
    )
    streaming_prompt_transport: Optional[
        Callable[[str], PromptTransport]
    ] = field(compare=False, default=None)

    def batch_transport(self, prompt: str) -> PromptTransport:
        """Return argv/stdin transport details for one batch prompt."""
        if self.batch_prompt_transport is not None:
            return self.batch_prompt_transport(prompt)
        return PromptTransport(self.batch_argv(prompt))

    def streaming_transport(self, prompt: str) -> PromptTransport:
        """Return argv/stdin transport details for one streaming prompt."""
        if self.streaming_prompt_transport is not None:
            return self.streaming_prompt_transport(prompt)
        return PromptTransport(self.streaming_argv(prompt))


def _claude_batch_argv(prompt: str) -> list[str]:
    """Batch command line for ``claude`` — ``stream-json`` (capture-output).

    Same NDJSON form as the streaming argv so the terminal ``result`` envelope
    carries usage/cache tokens; ``shell._run_once`` collapses the captured
    stream to the final message *and* the terminal stats for the run-log
    (batch authoring/audit paths were previously usage-blind). See BACKLOG #74.
    """
    return [
        "claude", "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", "acceptEdits",
        prompt,
    ]


def _claude_streaming_argv(prompt: str) -> list[str]:
    """Streaming command line for ``claude`` — NDJSON stream-json output."""
    return [
        "claude", "-p",
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", "acceptEdits",
        prompt,
    ]


CLAUDE_BACKEND = CliBackend(
    name="claude",
    binary="claude",
    batch_argv=_claude_batch_argv,
    streaming_argv=_claude_streaming_argv,
    parse_stream_line=_claude_parse_stream_line,
    rate_limit_pattern=_CLAUDE_RATE_LIMIT_PATTERN,
    provider_limit_pattern=_CLAUDE_PROVIDER_LIMIT_PATTERN,
    context_overflow_pattern=_CLAUDE_CONTEXT_OVERFLOW_PATTERN,
    transient_pattern=_CLAUDE_TRANSIENT_PATTERN,
    model_flag="--model",
    default_model=None,
    # stream-json batch output → shell._normalize_batch_stdout unwraps the
    # terminal envelope (final message + usage/cache stats). See BACKLOG #74.
    batch_output="json",
)


# ---------------------------------------------------------------------------
# Codex backend.
#
# Flags, event-type names, token field paths, and error strings below are
# read field-for-field from ``docs/reference/contracts/codex-cli.md`` and the captured
# transcripts under ``tests/fixtures/codex/`` (codex-cli 0.142.0), never
# from recollection — codex's ``--json`` schema differs from claude's
# ``stream-json`` and version drift is expected.
# ---------------------------------------------------------------------------

# Sandbox/approval pair equivalent to claude's ``--permission-mode
# acceptEdits``: ``-s workspace-write`` lets ``codex exec`` create/edit
# files in the workspace with no per-action prompt (verified in the
# contract). ``--skip-git-repo-check`` relaxes codex's refusal to run
# outside a git repo — kept unconditionally because plan-tool scratch
# contexts (bench tempdirs) may lack ``.git``. ``--ephemeral`` keeps
# automated runs from persisting session files.
_CODEX_COMMON_FLAGS = [
    "-s", "workspace-write",
    "--skip-git-repo-check",
    "--ephemeral",
]


def _codex_batch_argv(prompt: str) -> list[str]:
    """Batch command line for ``codex`` — JSONL captured and normalized.

    Codex's reliable final-message surface is its ``--json`` stream (or
    ``--output-last-message``). Use the same parser as streaming and let
    ``shell._run_once`` collapse the JSONL to the final agent message so
    existing batch callers still receive plain assistant text.
    """
    return ["codex", "exec", "--json", *_CODEX_COMMON_FLAGS, prompt]


def _codex_streaming_argv(prompt: str) -> list[str]:
    """Streaming command line for ``codex`` — NDJSON ``--json`` event stream."""
    return ["codex", "exec", "--json", *_CODEX_COMMON_FLAGS, prompt]


# Cross-line accumulator for codex's final agent message. Unlike claude
# (whose terminal ``result`` envelope carries the final text inline),
# codex emits the final message as an earlier ``agent_message`` item and
# a *separate* ``turn.completed`` envelope. This holder bridges the two
# so the terminal :class:`ClaudeRunStats` carries ``final_text``. It is
# reset on every ``thread.started`` (each codex turn opens with one), so
# a stale message never leaks across runs or tests. Safe as a module
# singleton because plan-tool drives one backend call at a time.
_codex_final_message: dict[str, str] = {"v": ""}


def _codex_tool_use_summary(item_type: str, item: dict) -> tuple[str, str]:
    """Map a codex work-item to a ``(tool_name, input_summary)`` pair.

    ``command_execution`` → ``("command", <shell string>)``;
    ``file_change`` → ``("edit", "<path> (<kind>), …")``. Each branch's own
    untruncated candidate is redacted (see :func:`_redact_secrets`) before
    the :data:`_TOOL_INPUT_SUMMARY_CAP` slice, matching the claude side.
    """
    if item_type == "command_execution":
        command = item.get("command")
        summary = command if isinstance(command, str) else ""
        return "command", _redact_secrets(summary)[:_TOOL_INPUT_SUMMARY_CAP]
    # file_change
    changes = item.get("changes")
    parts: list[str] = []
    if isinstance(changes, list):
        for change in changes:
            if not isinstance(change, dict):
                continue
            path = str(change.get("path", ""))
            kind = change.get("kind")
            parts.append(f"{path} ({kind})" if kind else path)
    joined = ", ".join(parts)
    return "edit", _redact_secrets(joined)[:_TOOL_INPUT_SUMMARY_CAP]


def _codex_parse_stream_line(
    line: str, *, bytes_in: int
) -> Optional[_StreamLineParse]:
    """Parse one codex ``--json`` NDJSON line into a :class:`_StreamLineParse`.

    Same ``None`` contract as :func:`_claude_parse_stream_line`: empty /
    non-JSON / non-dict lines return ``None`` so codex failure copy
    surfaced as raw text falls through to the stdout buffer and reaches
    :func:`plan_tool.claude_errors.classify` unchanged.

    Event mapping (per ``docs/reference/contracts/codex-cli.md``):

    - ``thread.started`` → reset the final-message accumulator; surface
      ``thread_id`` as the request-id correlator.
    - ``item.*`` with ``item.type == "agent_message"`` → ``assistant_text``
      (text → buffer + accumulator).
    - ``item.started`` with a ``command_execution`` / ``file_change`` item
      → ``tool_use``; the matching ``item.completed`` → ``tool_result``.
    - ``turn.completed`` / ``turn.failed`` → ``result`` + terminal stats;
      ``turn.failed`` sets ``is_error`` and pushes its error message into
      the buffer for the classifier.
    - ``error`` → push ``message`` into the buffer (precedes a
      ``turn.failed``); unrecognized types → passthrough ``kind=<type>``.
    """
    stripped = line.strip()
    if not stripped:
        return None
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None

    events: list[dict[str, object]] = []
    text_chunks: list[str] = []
    stats: Optional[ClaudeRunStats] = None
    last_tool: Optional[str] = None
    last_activity_kind: Optional[str] = None
    request_id_hint: Optional[str] = None

    obj_type = obj.get("type")

    if obj_type == "thread.started":
        _codex_final_message["v"] = ""
        tid = obj.get("thread_id")
        if isinstance(tid, str) and tid:
            request_id_hint = tid
        events.append({"kind": "thread.started", "bytes_in_delta": bytes_in})
        last_activity_kind = "thread.started"
    elif obj_type in ("item.started", "item.completed"):
        item_raw = obj.get("item")
        item = item_raw if isinstance(item_raw, dict) else {}
        item_type = item.get("type")
        if item_type == "agent_message":
            text = item.get("text")
            if isinstance(text, str) and text:
                _codex_final_message["v"] = text
                text_chunks.append(text)
                if not text.endswith("\n"):
                    text_chunks.append("\n")
                text_bytes = len(text.encode("utf-8"))
            else:
                text_bytes = bytes_in
            events.append({
                "kind": "assistant_text",
                "bytes_in_delta": text_bytes,
            })
            last_activity_kind = "assistant_text"
        elif item_type in ("command_execution", "file_change"):
            if obj_type == "item.started":
                name, summary = _codex_tool_use_summary(item_type, item)
                events.append({
                    "kind": "tool_use",
                    "tool_name": name or None,
                    "tool_input_summary": summary or None,
                    "bytes_in_delta": bytes_in,
                })
                if name:
                    last_tool = name
                last_activity_kind = "tool_use"
            else:
                events.append({"kind": "tool_result", "bytes_in_delta": bytes_in})
                last_activity_kind = "tool_result"
        else:
            kind = str(item_type) if item_type else str(obj_type)
            events.append({"kind": kind, "bytes_in_delta": bytes_in})
            last_activity_kind = kind
    elif obj_type in ("turn.completed", "turn.failed"):
        is_error = obj_type == "turn.failed"
        usage_raw = obj.get("usage")
        usage = usage_raw if isinstance(usage_raw, dict) else {}
        tokens_in = usage.get("input_tokens")
        tokens_out = usage.get("output_tokens")
        cached = usage.get("cached_input_tokens")
        if is_error:
            err = obj.get("error")
            msg = err.get("message") if isinstance(err, dict) else None
            if isinstance(msg, str) and msg:
                text_chunks.append(msg)
                if not msg.endswith("\n"):
                    text_chunks.append("\n")
        # cache_creation_tokens and cost_usd are not reported by codex —
        # pinned None so run-log aggregation (cli/runs.py) degrades to
        # n/a. request_id is None here; the pump merges in the
        # thread.started correlator.
        stats = ClaudeRunStats(
            final_text=_codex_final_message["v"],
            tokens_input=tokens_in if isinstance(tokens_in, (int, float)) else None,
            tokens_output=tokens_out if isinstance(tokens_out, (int, float)) else None,
            cache_creation_tokens=None,
            cache_read_tokens=cached if isinstance(cached, (int, float)) else None,
            cost_usd=None,
            request_id=None,
            is_error=is_error,
            input_includes_cached=(
                True if isinstance(tokens_in, (int, float)) else None
            ),
        )
        events.append({"kind": "result", "bytes_in_delta": bytes_in})
        last_activity_kind = "result"
    elif obj_type == "error":
        msg = obj.get("message")
        if isinstance(msg, str) and msg:
            text_chunks.append(msg)
            if not msg.endswith("\n"):
                text_chunks.append("\n")
        events.append({"kind": "error", "bytes_in_delta": bytes_in})
        last_activity_kind = "error"
    else:
        kind = str(obj_type) if obj_type else "unknown"
        events.append({"kind": kind, "bytes_in_delta": bytes_in})
        last_activity_kind = kind

    return _StreamLineParse(
        events=tuple(events),
        text_chunks=tuple(text_chunks),
        stats=stats,
        last_tool=last_tool,
        last_activity_kind=last_activity_kind,
        request_id_hint=request_id_hint,
    )


# Codex's unauthenticated copy (``~/.codex/auth.json`` missing/invalid).
# Not captured against the live binary (probing it would require
# corrupting real credentials), so the pattern errs broad across the
# observed shapes of a not-logged-in / unauthorized state; an unmatched
# phrasing degrades to UNKNOWN_NONZERO rather than mis-waiting. This is
# the one genuinely new failure class codex adds — no claude pattern
# covers it. Distinct recovery: surface a fix-credentials hint, no
# wait, no retry.
_CODEX_AUTH_PATTERN = re.compile(
    r"("
    r"not logged in"
    r"|not authenticated"
    r"|unauthorized"
    r"|\b401\b"
    r"|auth\.json"
    r"|codex login"
    r"|please (re-?)?login"
    r"|invalid api key"
    r"|authentication (failed|required)"
    r")",
    re.IGNORECASE,
)


# Rate-limit / provider-limit / context-overflow / transient detection is
# shared with claude: the contract confirms codex forwards the same copy
# (``usage limit``, ``try again at``, ``429`` stems, the generic overflow
# and network wordings), so reuse the compiled patterns rather than
# duplicate them. Only ``auth_pattern`` is codex-specific.
CODEX_BACKEND = CliBackend(
    name="codex",
    binary="codex",
    batch_argv=_codex_batch_argv,
    streaming_argv=_codex_streaming_argv,
    parse_stream_line=_codex_parse_stream_line,
    rate_limit_pattern=_CLAUDE_RATE_LIMIT_PATTERN,
    provider_limit_pattern=_CLAUDE_PROVIDER_LIMIT_PATTERN,
    context_overflow_pattern=_CLAUDE_CONTEXT_OVERFLOW_PATTERN,
    transient_pattern=_CLAUDE_TRANSIENT_PATTERN,
    auth_pattern=_CODEX_AUTH_PATTERN,
    model_flag="-m",
    default_model=None,
    batch_output="json",
)


# This descriptor bypasses normal backend selection. Structural revision must
# never inherit project argv, model, or fallback policy from a general caller.
STRUCTURAL_CODEX_VERSION = "codex-cli 0.142.0"


def structural_codex_backend(isolated_root: Path) -> CliBackend:
    """Return the fixed, read-only Codex descriptor for one isolated call."""
    root = Path(isolated_root).resolve()

    def structural_argv(prompt: str) -> list[str]:
        return [
            "codex",
            "exec",
            "--json",
            "-C",
            str(root),
            "-s",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            prompt,
        ]

    return replace(
        CODEX_BACKEND,
        name="codex-structural-read-only",
        batch_argv=structural_argv,
        streaming_argv=structural_argv,
        batch_prompt_transport=None,
        streaming_prompt_transport=None,
    )


_REGISTRY: dict[str, CliBackend] = {CLAUDE_BACKEND.name: CLAUDE_BACKEND}
_active_backend: CliBackend = CLAUDE_BACKEND
_scoped_active_backend: ContextVar[Optional[CliBackend]] = ContextVar(
    "plan_tool_active_backend", default=None
)


# (backend name, model or "") -> (window, exact). Written by the streaming runner, read by
# ``context_window``; see docs/ARCHITECTURE.md § "Prompt-budget window".
_observed_context_windows: dict[tuple[str, str], tuple[int, bool]] = {}
_observed_context_windows_lock = threading.Lock()  # one pump thread per in-flight call writes here


def _merged_observation(
    held: Optional[tuple[int, bool]], window: int, exact: bool
) -> tuple[int, bool]:
    """An exact window replaces anything; a lower bound never replaces an exact one and only rises."""
    if exact:
        return window, True
    if held is None:
        return window, False
    return held if held[1] else (max(held[0], window), False)


def observe_context_window(
    backend_name: str, model: Optional[str], window: object, *, exact: bool = True
) -> None:
    """Remember a reported window (see ``_merged_observation``)."""
    if type(window) is not int or window <= 0:
        return
    key = (backend_name, model or "")
    with _observed_context_windows_lock:
        _observed_context_windows[key] = _merged_observation(
            _observed_context_windows.get(key), window, exact
        )


def observed_context_window(backend_name: str, model: Optional[str]) -> Optional[int]:
    held = _observed_context_windows.get((backend_name, model or ""))
    return held[0] if held else None


def _reported_model_windows(model_usage: object) -> tuple[tuple[str, int], ...]:
    """Every ``(model id, contextWindow)`` pair in a result envelope's ``modelUsage``."""
    if not isinstance(model_usage, dict):
        return ()
    return tuple(
        (name, entry["contextWindow"])
        for name, entry in model_usage.items()
        if isinstance(name, str)
        and isinstance(entry, dict)
        and type(entry.get("contextWindow")) is int
        and entry["contextWindow"] > 0
    )


def reported_window_for_model(
    model: Optional[str], model_windows: tuple[tuple[str, int], ...]
) -> Optional[tuple[int, bool]]:
    """``(window, exact)`` to remember for ``model`` from one envelope, or ``None`` with no windows.

    The entry whose id equals the selected model is exact, and so is a single-entry envelope (any
    alias is served by it). Otherwise the smallest window is a lower bound that errs toward warning.
    """
    if not model_windows:
        return None
    for name, window in model_windows:
        if model and name == model:
            return window, True
    if len(model_windows) == 1:
        return model_windows[0][1], True
    return min(window for _name, window in model_windows), False


def get_active_backend() -> CliBackend:
    """Return the scoped active backend, or the process-wide fallback."""
    scoped = _scoped_active_backend.get()
    if scoped is not None:
        return scoped
    return _active_backend


# A ContextVar, not a module global: the bench's per-cell timeout
# abandons worker threads mid-entrypoint, and an abandoned thread still
# inside ``spawn_cwd`` must not leak its scratch path into (or race the
# restore against) every later trial. Each thread sees its own value;
# entrypoint and spawn always share a thread, so the scope still
# reaches its consumer.
_active_spawn_cwd: ContextVar[Optional[Path]] = ContextVar(
    "plan_tool_spawn_cwd", default=None
)


def get_active_spawn_cwd() -> Optional[Path]:
    """Working directory for backend subprocesses, or ``None`` (inherit).

    Read by the two spawn sites (``shell._run_once`` batch,
    ``launcher`` streaming ``Popen``) as their ``cwd=``. ``None`` — the
    default — inherits the process cwd, the historical behavior.

    The ``Invoker`` protocol (``Callable[[str], ...]``) carries only the
    prompt, so ``repo_root`` cannot reach the spawn sites as a
    parameter without rewriting every invoker signature; this mirrors
    the active-backend registry instead. Set via :func:`spawn_cwd` by
    the entrypoints that take ``repo_root`` — without it, a caller
    whose ``repo_root`` differs from the process cwd (the bench's
    scratch trials; a CLI invocation from a repo subdirectory) spawns
    backends that read and edit the wrong tree.
    """
    return _active_spawn_cwd.get()


@contextmanager
def spawn_cwd(path: Optional[Path]) -> Iterator[None]:
    """Scope backend-subprocess ``cwd`` to ``path`` for the block.

    Saves and restores the prior value, so nested entrypoints (e.g.
    ``review_plan_full`` reached from inside another wrapped call)
    compose correctly. ``path=None`` explicitly scopes back to
    inherit-from-process.
    """
    token = _active_spawn_cwd.set(path)
    try:
        yield
    finally:
        _active_spawn_cwd.reset(token)


def spawn_cwd_from_repo_root(fn: Callable) -> Callable:
    """Decorate an entrypoint so backend spawns run in its ``repo_root``.

    Reads the wrapped call's ``repo_root`` argument (positional or
    keyword) and enters :func:`spawn_cwd` around the body — one line at
    the definition instead of re-indenting a multi-hundred-line
    function. Entrypoints decorated with this are the producers of the
    spawn-cwd context; ``shell._run_once`` / the launcher ``Popen`` are
    the consumers. A call that omits ``repo_root`` (or passes ``None``)
    scopes to inherit-from-process, the historical behavior.
    """
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        bound = sig.bind_partial(*args, **kwargs)
        root = bound.arguments.get("repo_root")
        with spawn_cwd(Path(root) if root is not None else None):
            return fn(*args, **kwargs)

    return wrapper


def set_active_backend(name_or_backend: "str | CliBackend") -> None:
    """Swap the process-wide active backend.

    Accepts either a registered backend's ``name`` or a
    :class:`CliBackend` instance. Mutates the module global so every
    call site routed through :func:`get_active_backend` picks up the
    change. The CLI selection flag that calls this is a later step; the
    function ships now so that wiring is pure.
    """
    global _active_backend
    _active_backend = _resolve_active_backend_input(name_or_backend)


def _resolve_active_backend_input(name_or_backend: "str | CliBackend") -> CliBackend:
    """Resolve the input shapes accepted by active-backend setters."""
    if isinstance(name_or_backend, CliBackend):
        return name_or_backend
    try:
        return _REGISTRY[name_or_backend]
    except KeyError as exc:
        raise KeyError(
            f"unknown backend {name_or_backend!r}; "
            f"registered: {sorted(_REGISTRY)}"
        ) from exc


@contextmanager
def scoped_active_backend(
    name_or_backend: "str | CliBackend",
) -> Iterator[CliBackend]:
    """Install an active backend override for one block of work.

    Accepts the same input shapes as :func:`set_active_backend`, but stores the
    resolved descriptor in a :class:`ContextVar` so nested scopes and worker
    threads restore independently. The process-wide fallback remains whatever
    :func:`set_active_backend` last set.
    """
    scoped_backend = _resolve_active_backend_input(name_or_backend)
    token = _scoped_active_backend.set(scoped_backend)
    try:
        yield scoped_backend
    finally:
        _scoped_active_backend.reset(token)


def resolve_backend(name: str) -> CliBackend:
    """Return the registered backend whose ``name`` matches ``name``.

    The name→descriptor view ``cli.main`` uses to map the
    ``--backend`` / ``PLAN_TOOL_BACKEND`` selection string to a
    registered :class:`CliBackend`. Reads the same ``_REGISTRY``
    backing :func:`registered_binaries` / :func:`get_active_backend` —
    a lookup, not a second source of truth. Raises :class:`ValueError`
    listing the registered names on a miss so a bad
    ``PLAN_TOOL_BACKEND`` value is diagnosable.
    """
    try:
        return _REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"unknown backend {name!r}; registered: {sorted(_REGISTRY)}"
        ) from None


def provisional_backend_warning(name: str, detail: str = "") -> str:
    """Render the shared warning for a synthesized backend."""
    detail_suffix = f" {detail}" if detail else ""
    return (
        f"backend {name!r} is not a registered integration — using a "
        f"provisional descriptor (generic [{name} <prompt>] argv, "
        "claude-shaped stream parser + failure classification)."
        f"{detail_suffix} For correct streaming/classification, add "
        f"integrations/{name}/backend.json."
    )


def unknown_backend_override_warning(name: str, known_names: Collection[str]) -> str:
    """Render one diagnostic for an unrecognized project override key."""
    return (
        f"unknown backend {name!r} in .plan-tool/backends.json; "
        f"known: {sorted(known_names)}"
    )


def build_effective_backend(
    base: CliBackend,
    *,
    model: Optional[str],
    extra_batch_argv: Sequence[str],
    extra_streaming_argv: Sequence[str],
) -> CliBackend:
    """Return ``base`` with extra argv + a model pair spliced before the prompt.

    The active-backend argv = the base argv with ``[*project_extra_argv,
    model_flag, model]`` inserted just before the prompt. This is the one
    consumer of :attr:`CliBackend.model_flag` / ``default_model`` and the
    project file's ``extra_*_argv``; ``cli.main`` calls it at selection and
    ``set_active_backend``s the result, leaving the registry seeds untouched.

    The no-op case (no model, no extras) returns ``base`` unchanged, so the
    default selection path keeps the exact registry object and its
    byte-identical argv. Raises :class:`ValueError` when a ``model`` is
    requested against a backend whose ``model_flag`` is ``None`` (a
    misconfigured manifest) rather than silently dropping the model.
    """
    if model is None and not extra_batch_argv and not extra_streaming_argv:
        return base
    if model is not None and base.model_flag is None:
        raise ValueError(
            f"backend {base.name!r} declares no model_flag but a model "
            f"was requested"
        )
    model_pair = [base.model_flag, model] if model else []

    # Capture the base builders by value so the wrapped closures splice on
    # top of the seed argv rather than recursing into the effective object.
    base_batch_transport = base.batch_transport
    base_streaming_transport = base.streaming_transport
    extra_batch = list(extra_batch_argv)
    extra_streaming = list(extra_streaming_argv)

    def wrapped_batch_transport(prompt: str) -> PromptTransport:
        transport = base_batch_transport(prompt)
        return transport.with_args_before_prompt([*extra_batch, *model_pair])

    def wrapped_streaming_transport(prompt: str) -> PromptTransport:
        transport = base_streaming_transport(prompt)
        return transport.with_args_before_prompt([*extra_streaming, *model_pair])

    def wrapped_batch(prompt: str) -> list[str]:
        return wrapped_batch_transport(prompt).argv

    def wrapped_streaming(prompt: str) -> list[str]:
        return wrapped_streaming_transport(prompt).argv

    return replace(
        base,
        resolved_model=model,
        batch_argv=wrapped_batch,
        streaming_argv=wrapped_streaming,
        batch_prompt_transport=wrapped_batch_transport,
        streaming_prompt_transport=wrapped_streaming_transport,
    )


def _select_effective_backend(
    name: str,
    *,
    repo_root: Path,
    model: Optional[str] = None,
    fallback_factory: Optional[Callable[[str], CliBackend]] = None,
    known_override_names: Sequence[str] = (),
) -> BackendSelection:
    """Resolve, configure, and build the effective backend for one selection."""
    from plan_tool.backend_config import load_backend_overrides

    try:
        selected = resolve_backend(name)
    except ValueError:
        if fallback_factory is None:
            raise
        selected = fallback_factory(name)

    overrides = load_backend_overrides(repo_root)
    known_names = set(registered_names()) | set(known_override_names)
    unknown_override_names = tuple(
        sorted(key for key in overrides if key not in known_names)
    )
    override = overrides.get(selected.name)
    resolved_model = (
        model or (override.model if override else None) or selected.default_model
    )
    effective = build_effective_backend(
        selected,
        model=resolved_model,
        extra_batch_argv=override.extra_batch_argv if override else [],
        extra_streaming_argv=override.extra_streaming_argv if override else [],
    )
    return BackendSelection(
        selected=selected,
        effective=effective,
        unknown_override_names=unknown_override_names,
    )


def select_active_backend(
    name: str,
    *,
    repo_root: Path,
    model: Optional[str] = None,
    fallback_factory: Optional[Callable[[str], CliBackend]] = None,
    known_override_names: Sequence[str] = (),
) -> BackendSelection:
    """Resolve, configure, build, and activate the backend for one CLI run.

    ``name`` is already selected; CLI flag/environment/model-family precedence
    stays above this stdlib-only backend layer.

    Selection precedence matches the CLI contract: caller-supplied ``model``
    (from ``--model``) wins over ``.plan-tool/backends.json``'s
    ``backends.<name>.model``, which wins over the backend manifest's
    ``default_model``. Project ``extra_batch_argv`` and
    ``extra_streaming_argv`` are spliced into the effective descriptor before
    activation.

    ``fallback_factory`` is used only when ``name`` is not registered; the CLI
    passes its provisional-backend synthesizer there. Without a fallback,
    unknown names raise the same :class:`ValueError` as
    :func:`resolve_backend`.

    ``known_override_names`` permits callers that can synthesize a bounded
    set of backends to accept matching project override keys without masking
    other typo warnings.
    """
    selection = _select_effective_backend(
        name,
        repo_root=repo_root,
        model=model,
        fallback_factory=fallback_factory,
        known_override_names=known_override_names,
    )
    set_active_backend(selection.effective)
    return selection


@contextmanager
def scoped_select_active_backend(
    name: str,
    *,
    repo_root: Path,
    model: Optional[str] = None,
    fallback_factory: Optional[Callable[[str], CliBackend]] = None,
    known_override_names: Sequence[str] = (),
) -> Iterator[BackendSelection]:
    """Select an effective backend and activate it for one scope only.

    Uses the same project override and fallback selection path as
    :func:`select_active_backend`, then installs ``selection.effective`` through
    :func:`scoped_active_backend` so the process-wide active backend is left
    untouched.
    """
    selection = _select_effective_backend(
        name,
        repo_root=repo_root,
        model=model,
        fallback_factory=fallback_factory,
        known_override_names=known_override_names,
    )
    with scoped_active_backend(selection.effective):
        yield selection


def _generic_argv(binary: str) -> Callable[[str], list[str]]:
    """Curry ``prompt -> [binary, prompt]`` for a synthesized backend.

    The least-presumptuous shape: the bare binary plus the prompt as a
    single positional. An unregistered CLI's real flags are unknowable here;
    the project file's ``extra_*_argv`` splices them in via
    :func:`build_effective_backend` (``argv[:-1]`` stays ``[binary]``, so the
    splice point is uniform with the registered backends).
    """
    return lambda prompt: [binary, prompt]


def synthesize_backend(
    name: str, *, default_model: Optional[str] = None
) -> CliBackend:
    """Build a provisional :class:`CliBackend` for an unregistered CLI name.

    The escape hatch for ``--backend <x>`` when no ``integrations/<x>/`` ships
    yet: rather than hard-fail, construct a best-effort descriptor so the CLI
    is at least batch-invocable. What is *guessed* (and therefore wrong for
    some CLIs) versus *sourced*:

    - ``binary`` = ``name``; argv = ``[binary, prompt]`` (+ project
      ``extra_*_argv``) — a guess; correct streaming flags need a manifest.
    - ``parse_stream_line`` reuses the claude parser — best-effort: its
      ``None`` contract routes non-JSON stdout straight to the buffer, so a
      plain-text CLI's output is still captured in batch mode even though its
      streaming schema is unmodeled.
    - classification patterns reuse the shared claude set (rate-limit /
      overflow / transient copy is largely provider-agnostic).
    - ``model_flag`` defaults to ``--model`` (the common convention); the
      project file can override the argv if wrong.
    - ``default_model`` is *sourced* — the caller passes a value resolved from
      the models.dev catalog (see :func:`plan_tool.model_specs.pick_default_model`),
      the one field with an authoritative upstream. ``None`` when the catalog
      was unreachable or knows no model for the CLI's provider.

    Not registered into ``_REGISTRY`` — transient, like a ``build_effective_backend``
    result. The CLI layer warns loudly that the descriptor is provisional and
    points the user at writing an ``integrations/<name>/backend.json`` manifest.
    """
    return CliBackend(
        name=name,
        binary=name,
        batch_argv=_generic_argv(name),
        streaming_argv=_generic_argv(name),
        parse_stream_line=_claude_parse_stream_line,
        rate_limit_pattern=_CLAUDE_RATE_LIMIT_PATTERN,
        provider_limit_pattern=_CLAUDE_PROVIDER_LIMIT_PATTERN,
        context_overflow_pattern=_CLAUDE_CONTEXT_OVERFLOW_PATTERN,
        transient_pattern=_CLAUDE_TRANSIENT_PATTERN,
        auth_pattern=None,
        model_flag="--model",
        default_model=default_model,
    )


def register_backend(backend: CliBackend) -> None:
    """Insert ``backend`` into the registry under its ``name``."""
    _REGISTRY[backend.name] = backend


def registered_binaries() -> set[str]:
    """Every registered backend's executable name.

    Consumed by the test suite's real-subprocess guard so a newly
    registered backend's binary is blocked without editing the guard.
    """
    return {b.binary for b in _REGISTRY.values()}


def registered_names() -> set[str]:
    """Every registered backend's selection name.

    The name view ``cli.main`` diffs project-file ``backends.<name>`` keys
    against to warn on a key matching no registered backend (a likely typo).
    """
    return set(_REGISTRY)


# Register codex and cursor so ``registered_binaries()`` returns every
# shipped binary at import and the test-suite guard auto-blocks real
# subprocesses. The active backend stays ``CLAUDE_BACKEND`` until
# ``cli.main`` selects another via ``--backend`` / ``PLAN_TOOL_BACKEND``.
register_backend(CODEX_BACKEND)


# ---------------------------------------------------------------------------
# Cursor Agent backend.
#
# Flags, event-type names, token field paths, and error strings below are
# read field-for-field from ``docs/reference/contracts/cursor-agent-cli.md`` and the
# captured transcripts under ``tests/fixtures/cursor/`` (agent
# 2026.06.24-00-45-58-9f61de7), never from recollection — the agent
# ``stream-json`` schema shares assistant/user shapes with claude but uses
# separate ``tool_call`` events and camelCase usage fields.
# ---------------------------------------------------------------------------

# Headless flags equivalent to claude's ``--permission-mode acceptEdits``:
# ``-p`` non-interactive print mode, ``--force`` auto-approves tools,
# ``--trust`` skips workspace-trust prompts. ``stream-json`` matches the
# launcher NDJSON pump; batch uses the same argv and normalizes via
# ``batch_output="json"``.
_CURSOR_COMMON_FLAGS = [
    "-p",
    "--output-format", "stream-json",
    "--force",
    "--trust",
]


def _cursor_batch_argv(prompt: str) -> list[str]:
    return ["agent", *_CURSOR_COMMON_FLAGS, prompt]


def _cursor_streaming_argv(prompt: str) -> list[str]:
    return ["agent", *_CURSOR_COMMON_FLAGS, prompt]


def _cursor_tool_use_summary(tool_call: dict) -> tuple[str, str]:
    """Map a cursor ``tool_call`` block to ``(tool_name, input_summary)``.

    Each candidate is redacted (see :func:`_redact_secrets`) before its
    :data:`_TOOL_INPUT_SUMMARY_CAP` slice, matching the claude side.
    """
    for key, value in tool_call.items():
        if not key.endswith("ToolCall") or not isinstance(value, dict):
            continue
        args = value.get("args")
        if not isinstance(args, dict):
            continue
        command = args.get("command")
        if isinstance(command, str) and command:
            return "command", _redact_secrets(command)[:_TOOL_INPUT_SUMMARY_CAP]
        path = args.get("path")
        if isinstance(path, str) and path:
            return "edit", _redact_secrets(path)[:_TOOL_INPUT_SUMMARY_CAP]
        target = args.get("target")
        if isinstance(target, str) and target:
            return "edit", _redact_secrets(target)[:_TOOL_INPUT_SUMMARY_CAP]
    return "tool", ""


def _cursor_parse_assistant_blocks(
    content: object,
    *,
    bytes_in: int,
    events: list[dict[str, object]],
    text_chunks: list[str],
) -> tuple[Optional[str], Optional[str]]:
    """Parse claude-shaped ``message.content`` blocks on assistant/user lines."""
    last_tool: Optional[str] = None
    last_activity_kind: Optional[str] = None
    if not isinstance(content, list):
        return last_tool, last_activity_kind
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text") or ""
            if isinstance(text, str) and text:
                text_chunks.append(text)
            text_bytes = (
                len(text.encode("utf-8")) if isinstance(text, str) else 0
            )
            events.append({
                "kind": "assistant_text",
                "bytes_in_delta": text_bytes,
            })
            last_activity_kind = "assistant_text"
        elif block_type == "tool_use":
            name = str(block.get("name") or "")
            inp = block.get("input") or {}
            summary = _summarize_tool_input(name, inp)
            events.append({
                "kind": "tool_use",
                "tool_name": name or None,
                "tool_input_summary": summary or None,
                "bytes_in_delta": bytes_in,
            })
            if name:
                last_tool = name
            last_activity_kind = "tool_use"
        elif block_type == "tool_result":
            events.append({"kind": "tool_result", "bytes_in_delta": bytes_in})
            last_activity_kind = "tool_result"
        else:
            kind = str(block_type) if block_type else "unknown"
            events.append({"kind": kind, "bytes_in_delta": bytes_in})
            last_activity_kind = kind
    return last_tool, last_activity_kind


def _cursor_parse_stream_line(
    line: str, *, bytes_in: int
) -> Optional[_StreamLineParse]:
    """Parse one Cursor Agent ``stream-json`` NDJSON line."""
    stripped = line.strip()
    if not stripped:
        return None
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None

    events: list[dict[str, object]] = []
    text_chunks: list[str] = []
    stats: Optional[ClaudeRunStats] = None
    last_tool: Optional[str] = None
    last_activity_kind: Optional[str] = None
    request_id_hint: Optional[str] = None

    obj_type = obj.get("type")

    if obj_type in ("assistant", "user"):
        message = obj.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        lt, lk = _cursor_parse_assistant_blocks(
            content, bytes_in=bytes_in, events=events, text_chunks=text_chunks
        )
        if lt:
            last_tool = lt
        if lk:
            last_activity_kind = lk
        if obj_type == "assistant":
            rid = obj.get("request_id")
            if isinstance(rid, str) and rid:
                request_id_hint = rid
    elif obj_type == "tool_call":
        subtype = obj.get("subtype")
        tool_call_raw = obj.get("tool_call")
        tool_call = tool_call_raw if isinstance(tool_call_raw, dict) else {}
        if subtype == "started":
            name, summary = _cursor_tool_use_summary(tool_call)
            events.append({
                "kind": "tool_use",
                "tool_name": name or None,
                "tool_input_summary": summary or None,
                "bytes_in_delta": bytes_in,
            })
            if name:
                last_tool = name
            last_activity_kind = "tool_use"
        elif subtype == "completed":
            events.append({"kind": "tool_result", "bytes_in_delta": bytes_in})
            last_activity_kind = "tool_result"
        else:
            kind = f"tool_call.{subtype}" if subtype else "tool_call"
            events.append({"kind": kind, "bytes_in_delta": bytes_in})
            last_activity_kind = kind
    elif obj_type == "result":
        usage_raw = obj.get("usage")
        usage = usage_raw if isinstance(usage_raw, dict) else {}
        final_text = obj.get("result")
        if isinstance(final_text, str) and final_text:
            text_chunks.append(final_text)
            if not final_text.endswith("\n"):
                text_chunks.append("\n")
        subtype = obj.get("subtype")
        is_error = bool(obj.get("is_error", False)) or subtype not in (
            None, "success"
        )
        rid = obj.get("request_id")
        if isinstance(rid, str) and rid:
            request_id_hint = rid
        stats = ClaudeRunStats(
            final_text=final_text if isinstance(final_text, str) else "",
            tokens_input=usage.get("inputTokens"),
            tokens_output=usage.get("outputTokens"),
            cache_creation_tokens=usage.get("cacheWriteTokens"),
            cache_read_tokens=usage.get("cacheReadTokens"),
            cost_usd=None,
            request_id=rid if isinstance(rid, str) else None,
            is_error=is_error,
        )
        events.append({"kind": "result", "bytes_in_delta": bytes_in})
        last_activity_kind = "result"
    elif obj_type == "system":
        events.append({"kind": "system", "bytes_in_delta": bytes_in})
        last_activity_kind = "system"
    else:
        kind = str(obj_type) if obj_type else "unknown"
        events.append({"kind": kind, "bytes_in_delta": bytes_in})
        last_activity_kind = kind

    return _StreamLineParse(
        events=tuple(events),
        text_chunks=tuple(text_chunks),
        stats=stats,
        last_tool=last_tool,
        last_activity_kind=last_activity_kind,
        request_id_hint=request_id_hint,
    )


# Cursor auth copy (stderr-only in probes; pattern errs broad).
_CURSOR_AUTH_PATTERN = re.compile(
    r"("
    r"authentication required"
    r"|not authenticated"
    r"|invalid api key"
    r"|CURSOR_API_KEY"
    r"|agent login"
    r"|please (re-?)?login"
    r"|unauthorized"
    r"|\b401\b"
    r")",
    re.IGNORECASE,
)

# Match Cursor's observed quota banner as one ordered phrase, rather than
# treating unrelated transcript fragments as provider-confirmed evidence.
_CURSOR_PLAN_QUOTA_PATTERN = re.compile(
    r"\bActionRequiredError\b(?:\s*:\s*|\.\s*)"
    r"(?:You've hit your usage limit(?: for [^.]+)?\.\s*)?"
    r"Switch to a different model or set a Spend Limit\.\s*"
    r"(?:Your usage limits will reset when\s+|Details:\s*)?"
    r"(?:your\s+)?monthly cycle ends on\b",
    re.IGNORECASE,
)


CURSOR_BACKEND = CliBackend(
    name="cursor",
    binary="agent",
    batch_argv=_cursor_batch_argv,
    streaming_argv=_cursor_streaming_argv,
    parse_stream_line=_cursor_parse_stream_line,
    rate_limit_pattern=_CLAUDE_RATE_LIMIT_PATTERN,
    provider_limit_pattern=_CLAUDE_PROVIDER_LIMIT_PATTERN,
    context_overflow_pattern=_CLAUDE_CONTEXT_OVERFLOW_PATTERN,
    transient_pattern=_CLAUDE_TRANSIENT_PATTERN,
    auth_pattern=_CURSOR_AUTH_PATTERN,
    plan_quota_pattern=_CURSOR_PLAN_QUOTA_PATTERN,
    model_flag="--model",
    default_model=None,
    batch_output="json",
)

register_backend(CURSOR_BACKEND)


# ---------------------------------------------------------------------------
# Manifest loader.
#
# Turns an ``integrations/<backend>/backend.json`` directory into a
# :class:`CliBackend`. The round-trip golden pins byte-fidelity:
# ``load_backend_from_dir("integrations/claude") == CLAUDE_BACKEND``.
# Packaged-resource discovery (iterating ``integrations/*``) and model /
# project-override wiring are later steps; this loader takes a plain
# directory path and emits no model pair.
# ---------------------------------------------------------------------------

# The single code↔manifest link: a manifest's ``parser`` discriminator
# resolves through this map to a real stream-line parse function. A
# custom-shaped backend registers its parser via ``register_parser``
# instead of editing the loader — mirrors ``register_backend``'s shape.
_PARSER_REGISTRY: dict[str, Callable[..., Optional[_StreamLineParse]]] = {
    "claude": _claude_parse_stream_line,
    "codex": _codex_parse_stream_line,
    "cursor": _cursor_parse_stream_line,
}

# Required top-level manifest keys; absence of any raises a typed error
# naming the field rather than a deep ``KeyError``.
_REQUIRED_MANIFEST_KEYS = (
    "name",
    "binary",
    "parser",
    "batch_argv",
    "streaming_argv",
    "classification",
)

# Required ``classification`` sub-keys (each maps to a non-optional
# pattern field). ``auth`` and ``plan_quota`` stay optional — ``null``/absent
# means no pattern.
_REQUIRED_CLASSIFICATION_KEYS = (
    "rate_limit",
    "provider_limit",
    "context_overflow",
    "transient",
)


def register_parser(name: str, fn: Callable[..., Optional[_StreamLineParse]]) -> None:
    """Register a stream-line parser under ``name`` for manifest resolution.

    Lets a future custom-shaped backend add its parser without editing
    :func:`load_backend_from_dir`. Mirrors :func:`register_backend`.
    """
    _PARSER_REGISTRY[name] = fn


def _resolve_parser(name: str) -> Callable[..., Optional[_StreamLineParse]]:
    """Map a manifest ``parser`` discriminator to its parse function.

    Raises :class:`BackendManifestError` listing the registered names on
    a miss (the registered-names list is part of the error contract).
    """
    try:
        return _PARSER_REGISTRY[name]
    except KeyError:
        raise BackendManifestError(
            f"unknown parser {name!r}; registered: {sorted(_PARSER_REGISTRY)}"
        ) from None


def _argv_closure(binary: str, flags: list[str]) -> Callable[[str], list[str]]:
    """Curry a prompt → ``[binary, *flags, prompt]`` argv builder.

    The closure leaves ``argv[:-1]`` exactly ``[binary, *flags]`` — model
    injection is the ``--model`` step's job (it splices ``[model_flag,
    model]`` via ``base_argv[:-1]``), so this emits no model pair.
    """
    head = [binary, *flags]
    return lambda prompt: [*head, prompt]


def load_backend_from_dir(path: Path) -> CliBackend:
    """Load the ``backend.json`` manifest under ``path`` into a :class:`CliBackend`.

    Reads ``path / "backend.json"``, resolves the ``parser`` discriminator
    through :data:`_PARSER_REGISTRY`, compiles the ``classification``
    regexes with ``re.IGNORECASE`` (the uniform flag the in-code literals
    use, so a loaded pattern matches the literal by ``.pattern`` /
    ``.flags`` value), and curries the ``batch_argv`` / ``streaming_argv``
    flag lists into argv closures.

    Raises :class:`BackendManifestError` — naming the offending file /
    field — on a missing manifest, malformed JSON, a missing required
    field or ``classification`` sub-key, or an unknown ``parser``.

    The round-trip golden holds: ``load_backend_from_dir(<repo>/
    integrations/claude) == CLAUDE_BACKEND`` (argv closures and patterns
    are ``compare=False``; their fidelity is asserted by output / value).
    """
    manifest_file = Path(path) / "backend.json"
    try:
        raw = manifest_file.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BackendManifestError(
            f"missing backend manifest {manifest_file}"
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BackendManifestError(
            f"invalid JSON in {manifest_file}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise BackendManifestError(
            f"{manifest_file} top-level must be a JSON object, "
            f"got {type(data).__name__}"
        )

    for key in _REQUIRED_MANIFEST_KEYS:
        if key not in data:
            raise BackendManifestError(
                f"missing required field {key!r} in {manifest_file}"
            )

    classification = data["classification"]
    if not isinstance(classification, dict):
        raise BackendManifestError(
            f"'classification' in {manifest_file} must be a JSON object, "
            f"got {type(classification).__name__}"
        )
    for key in _REQUIRED_CLASSIFICATION_KEYS:
        if key not in classification:
            raise BackendManifestError(
                f"missing required field 'classification.{key}' in {manifest_file}"
            )

    parse_stream_line = _resolve_parser(data["parser"])

    def _compile(value: str) -> "re.Pattern[str]":
        return re.compile(value, re.IGNORECASE)

    auth_raw = classification.get("auth")
    auth_pattern = _compile(auth_raw) if isinstance(auth_raw, str) else None
    plan_quota_raw = classification.get("plan_quota")
    plan_quota_pattern = (
        _compile(plan_quota_raw) if isinstance(plan_quota_raw, str) else None
    )

    return CliBackend(
        name=data["name"],
        binary=data["binary"],
        batch_argv=_argv_closure(data["binary"], data["batch_argv"]),
        streaming_argv=_argv_closure(data["binary"], data["streaming_argv"]),
        parse_stream_line=parse_stream_line,
        rate_limit_pattern=_compile(classification["rate_limit"]),
        provider_limit_pattern=_compile(classification["provider_limit"]),
        context_overflow_pattern=_compile(classification["context_overflow"]),
        transient_pattern=_compile(classification["transient"]),
        auth_pattern=auth_pattern,
        plan_quota_pattern=plan_quota_pattern,
        model_flag=data.get("model_flag"),
        default_model=data.get("default_model"),
        batch_output=data.get("batch_output", "stdout"),
    )


# ---------------------------------------------------------------------------
# Startup discovery.
#
# Wires the loader to import: locate the bundled ``integrations/`` tree,
# iterate each ``integrations/<name>/backend.json``, and register the
# loaded backend *over* the in-code seed (manifests are authoritative —
# they externalize argv flags). A broken manifest is warned-and-skipped
# per directory, so the seed for that name survives. ``_active_backend``
# is left untouched, so ``get_active_backend()`` still defaults to
# ``CLAUDE_BACKEND``; ``cli.main`` reaches the manifest-loaded descriptor
# through ``set_active_backend(resolve_backend(name))``.
# ---------------------------------------------------------------------------


def _packaged_integrations_dir() -> Optional[Path]:
    """Locate the bundled ``integrations/`` tree, or ``None`` if absent.

    Dual-mode, to cover both install shapes:

    - **Built wheel** — step 1's ``force-include`` maps repo-root
      ``integrations`` under the package, so
      ``importlib.resources.files("plan_tool") / "integrations"`` finds
      it.
    - **Editable / source checkout** — the force-include never runs, so
      the manifests stay at repo root. ``backend.py`` is
      ``plan_tool/backend.py``, so ``parent.parent`` is the repo root.

    Anchored on ``__file__`` (not ``locator.find_repo_root_from_cwd``):
    plan-tool installed editable normally drives a *different* repo whose
    root has no ``integrations/``, and ``__file__`` keeps this module
    stdlib-only (no ``locator`` import, preserving the leaf topology).
    """
    wheel_candidate = Path(str(importlib.resources.files("plan_tool"))) / "integrations"
    if wheel_candidate.is_dir():
        return wheel_candidate
    source_candidate = Path(__file__).resolve().parent.parent / "integrations"
    if source_candidate.is_dir():
        return source_candidate
    return None


def discover_and_register_backends(
    integrations_root: Optional[Path] = None,
) -> None:
    """Register every ``<root>/<name>/backend.json`` manifest over the seed.

    Resolves ``integrations_root`` (or :func:`_packaged_integrations_dir`
    in production), iterates each child directory in sorted order, and
    registers the loaded :class:`CliBackend` over the in-code seed —
    manifests are authoritative because :class:`CliBackend.__eq__`
    excludes the argv flags, so a flag-only manifest edit is otherwise
    silently dropped.

    A malformed manifest (bad JSON / unknown parser / missing field →
    :class:`BackendManifestError`; bad classification regex → ``re.error``;
    wrong-typed field → ``TypeError`` / ``ValueError``) is warned-and-skipped
    per directory, so the seed for that name survives and one bad directory
    never aborts discovery (or, since this is auto-called at import,
    ``import plan_tool.backend``). The injectable ``integrations_root``
    keeps the discovery tests hermetic against ``tmp_path``.
    """
    root = integrations_root or _packaged_integrations_dir()
    if root is None or not root.is_dir():
        return
    for child in sorted(root.iterdir()):
        if not (child / "backend.json").is_file():
            continue
        try:
            register_backend(load_backend_from_dir(child))
        except (BackendManifestError, re.error, TypeError, ValueError) as exc:
            warnings.warn(
                f"plan-tool: skipping backend manifest in {child}: {exc}",
                stacklevel=2,
            )
            continue


# Layer the packaged manifests over the seed: literals register first
# (fallback), then the committed ``integrations/<backend>/backend.json``
# files (authoritative). claude/codex stay byte-faithful because their
# manifests reproduce the in-code literals.
discover_and_register_backends()
