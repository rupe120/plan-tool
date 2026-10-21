"""Model catalog and family inference for CLI backend selection.

When ``--backend <x>`` names a CLI with no ``integrations/<x>/`` manifest yet,
:func:`plan_tool.backend.synthesize_backend` builds a provisional descriptor.
The one field it can fill *authoritatively* is the default model: this module
fetches the open, auth-free models.dev catalog, maps the CLI name to a
provider, and picks that provider's flagship. Everything else about an
unknown CLI (argv, stream schema, failure copy) has no upstream source and
stays a best-effort guess in ``synthesize_backend``.

``backend_for_model`` uses stable family names, so ``--model gpt-*`` selects
Codex without a network lookup.

Two seams mirror the rest of the codebase:

- **Injectable fetch** (``fetcher=``), like the ``invoker=`` seam on every
  Claude-shelling function. The default hits the network over stdlib
  ``urllib``; tests pass a fake returning a captured ``api.json`` so they
  never touch the wire. There is no autouse network guard the way there is
  for subprocesses, so wiring the seam is the only thing keeping the suite
  hermetic — always inject it (or patch :func:`fetch_catalog`).
- **Failure is never fatal** (cf. :mod:`plan_tool.fetch`). A dead network, a
  drifted schema, a bad cache file — each funnels into a :class:`Catalog`
  carrying ``error`` and no specs. ``pick_default_model`` then returns
  ``None`` and the synthesized backend simply runs with no model pair.

Schema note: the field paths (``models[id].cost.{input,output}``,
``.limit.{context,output}``, ``.knowledge``) are read from the documented
models.dev ``api.json`` shape, each ``.get`` + ``isinstance`` guarded — a
renamed field degrades that one spec, never crashes.
"""

from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from plan_tool.backend import CliBackend

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


CATALOG_URL = "https://models.dev/api.json"
DEFAULT_TIMEOUT_S = 10.0
DEFAULT_MAX_BYTES = 8_000_000  # api.json is a few MB; cap defends memory.
DEFAULT_CACHE_MAX_AGE_S = 24 * 60 * 60  # specs move on a day+ cadence.

_USER_AGENT = "plan-tool model-specs (+https://github.com/rupe120/plan-tool)"

# A fetcher takes a URL and returns the raw response body, or raises. The
# default is the only thing that touches the network; everything else takes
# it as a parameter so a fake can be injected.
Fetcher = Callable[[str], str]


@dataclass(frozen=True)
class ModelSpec:
    """The subset of a models.dev model entry the default-picker ranks on.

    ``provider`` is the catalog's top-level key (``"anthropic"`` /
    ``"openai"``); ``id`` is the within-provider model key. Numeric fields
    are ``None`` when absent or wrong-typed in the source. ``pick_default_model``
    ranks on ``context_window`` then ``output_cost``; the rest are carried for
    a caller that wants to annotate the chosen model.
    """

    id: str
    provider: str
    name: str = ""
    context_window: Optional[int] = None
    max_output: Optional[int] = None
    input_cost: Optional[float] = None
    output_cost: Optional[float] = None
    knowledge_cutoff: Optional[str] = None


@dataclass(frozen=True)
class Catalog:
    """A fetched models.dev catalog. Never constructed by raising.

    ``error`` is set (and ``specs`` empty) when the fetch / parse failed;
    ``pick_default_model`` then returns ``None``. ``from_cache`` records
    whether the bytes came off disk, for an operator-facing note.
    """

    specs: tuple[ModelSpec, ...] = ()
    error: Optional[str] = None
    from_cache: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.specs)


def _urllib_fetcher(url: str) -> str:
    """Default network fetch — stdlib ``urllib``, honest User-Agent.

    Raises (``HTTPError`` / ``URLError`` / ``socket.timeout``) on any
    failure; :func:`fetch_catalog` turns those into a non-fatal
    ``Catalog.error``. Reads at most :data:`DEFAULT_MAX_BYTES`.
    """
    req = Request(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
    )
    with urlopen(req, timeout=DEFAULT_TIMEOUT_S) as resp:
        return resp.read(DEFAULT_MAX_BYTES).decode("utf-8", errors="replace")


def _as_int(v: object) -> Optional[int]:
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _as_float(v: object) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _as_str(v: object) -> Optional[str]:
    return v if isinstance(v, str) and v else None


def _parse_catalog(raw: str) -> tuple[ModelSpec, ...]:
    """Flatten models.dev ``api.json`` into :class:`ModelSpec` rows.

    Shape: ``{provider: {"models": {id: {cost, limit, knowledge, ...}}}}``.
    Every level is type-guarded; a malformed provider / model entry is
    skipped, not fatal, so partial drift still yields the rows that parsed.
    Raises only on top-level non-JSON (the caller maps that to ``error``).
    """
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(f"catalog root must be an object, got {type(data).__name__}")

    specs: list[ModelSpec] = []
    for provider_id, provider in data.items():
        if not isinstance(provider, dict):
            continue
        models = provider.get("models")
        if not isinstance(models, dict):
            continue
        for model_id, model in models.items():
            if not isinstance(model, dict):
                continue
            cost = model.get("cost") if isinstance(model.get("cost"), dict) else {}
            limit = model.get("limit") if isinstance(model.get("limit"), dict) else {}
            specs.append(
                ModelSpec(
                    id=str(model_id),
                    provider=str(provider_id),
                    name=str(model.get("name", "") or ""),
                    context_window=_as_int(limit.get("context")),
                    max_output=_as_int(limit.get("output")),
                    input_cost=_as_float(cost.get("input")),
                    output_cost=_as_float(cost.get("output")),
                    knowledge_cutoff=_as_str(model.get("knowledge")),
                )
            )
    return tuple(specs)


def fetch_catalog(
    *,
    fetcher: Fetcher = _urllib_fetcher,
    cache_path: Optional[Path] = None,
    max_age_s: float = DEFAULT_CACHE_MAX_AGE_S,
    now: float | None = None,
) -> Catalog:
    """Fetch + parse the catalog. Never raises.

    With ``cache_path``, a file fresher than ``max_age_s`` short-circuits the
    fetch (and sets ``from_cache``); otherwise the fetched bytes are written
    back best-effort. ``now`` is injectable for deterministic cache tests.
    Any failure — network, JSON, unreadable cache — returns a
    :class:`Catalog` whose ``error`` names the cause and whose specs are empty.
    """
    clock = time.time if now is None else (lambda: now)

    if cache_path is not None and cache_path.is_file():
        try:
            age = clock() - cache_path.stat().st_mtime
            if age <= max_age_s:
                specs = _parse_catalog(cache_path.read_text(encoding="utf-8"))
                return Catalog(specs=specs, from_cache=True)
        except (OSError, ValueError, json.JSONDecodeError):
            pass  # stale/corrupt cache → fall through to a live fetch.

    try:
        raw = fetcher(CATALOG_URL)
    except HTTPError as exc:
        return Catalog(error=f"HTTP {exc.code}")
    except (URLError, socket.timeout, TimeoutError) as exc:
        return Catalog(error=f"fetch failed: {getattr(exc, 'reason', exc)}")
    except Exception as exc:  # a fetch bug must not abort selection
        return Catalog(error=f"fetch error: {exc}")

    try:
        specs = _parse_catalog(raw)
    except (ValueError, json.JSONDecodeError) as exc:
        return Catalog(error=f"parse failed: {exc}")

    if cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(raw, encoding="utf-8")
        except OSError:
            pass  # caching is an optimization; a read-only FS is fine.

    return Catalog(specs=specs)


# Map a coding-assistant CLI / backend name to its models.dev provider key.
# Only the unambiguous single-provider CLIs are listed; a multi-model CLI
# (aider / opencode / cursor) is deliberately absent — there is no single
# right provider to default it to. An unmapped name falls through to trying
# the name itself as a provider id (models.dev keys like "google" / "mistral"
# / "deepseek" are already CLI-shaped), so a new single-provider CLI often
# resolves with no alias entry at all.
_BACKEND_PROVIDER_ALIASES = {
    "claude": "anthropic",
    "codex": "openai",
    "gemini": "google",
    "gemini-cli": "google",
}

# Canonical backend names and their unambiguous model-family prefixes. Gemini
# remains provisional until it has a packaged integration.
_MODEL_FAMILY_PREFIXES = {
    "claude": ("claude",),
    "gemini": ("gemini",),
    "codex": ("gpt", "chatgpt", "codex", "o1", "o3", "o4"),
}

# Provider-qualified model ids use the same canonical backend set.
_MODEL_BACKEND_ALIASES = {
    _BACKEND_PROVIDER_ALIASES[backend]: backend
    for backend in _MODEL_FAMILY_PREFIXES
}


def _has_model_prefix(model: str, prefix: str) -> bool:
    """Whether ``model`` is exactly ``prefix`` or starts its common boundary."""
    return model == prefix or model.startswith((f"{prefix}-", f"{prefix}_"))


def backend_for_model(model: str) -> Optional[str]:
    """Return the backend for an unambiguous model family, else ``None``."""
    normalized = model.strip().lower()
    if not normalized:
        return None

    parts = tuple(
        part
        for part in normalized.replace("/", ":").replace(".", ":").split(":")
        if part
    )
    for part in parts:
        if part in _MODEL_BACKEND_ALIASES:
            return _MODEL_BACKEND_ALIASES[part]
        for backend, families in _MODEL_FAMILY_PREFIXES.items():
            if any(_has_model_prefix(part, family) for family in families):
                return backend
    return None


def model_family_backend_names() -> frozenset[str]:
    """Return backend names eligible for model-family inference."""
    return frozenset(_MODEL_FAMILY_PREFIXES)


def synthesize_model_family_backend(name: str) -> "CliBackend":
    """Resolve a case/whitespace-normalized model family to its real backend.

    Retries the registry with the normalized name first, so a case mismatch
    against an already-registered family (``Claude`` -> ``claude``) returns
    the real backend's argv instead of a generic, broken stand-in. Only a
    family with no registered integration yet (e.g. ``gemini``) falls
    through to a provisional descriptor.
    """
    normalized = name.strip().lower()
    if normalized not in _MODEL_FAMILY_PREFIXES:
        raise ValueError(f"unknown model-family backend {name!r}")
    from plan_tool.backend import resolve_backend, synthesize_backend

    try:
        return resolve_backend(normalized)
    except ValueError:
        return synthesize_backend(normalized)


def provider_for_backend(name: str) -> str:
    """Best-effort map a backend/CLI name to a models.dev provider key.

    Returns the alias when known, else the lowercased name verbatim (many
    providers are already named like their CLI). A passthrough miss is
    harmless — ``pick_default_model`` just finds no candidates and returns
    ``None``.
    """
    key = name.lower()
    return _BACKEND_PROVIDER_ALIASES.get(key, key)


def pick_default_model(catalog: Catalog, provider: str) -> Optional[ModelSpec]:
    """Pick a provider's flagship as a provisional default, or ``None``.

    Heuristic — there is no "flagship" flag in the source: rank that
    provider's models by ``(context_window, output_cost, id)`` and take the
    max, on the premise that a flagship pairs the largest context with the
    top price (mini/flash variants undercut both). Deterministic and
    catalog-only; ``None`` when the catalog failed to load or lists no model
    for ``provider``. A guess, never authoritative — the caller surfaces it
    as provisional and tells the user to pin ``--model`` explicitly.
    """
    if not catalog.ok:
        return None
    candidates = [s for s in catalog.specs if s.provider == provider]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda s: (s.context_window or 0, s.output_cost or 0.0, s.id),
    )
