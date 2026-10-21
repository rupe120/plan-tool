"""Per-plan cache of MIXED-STEP purity verdicts, keyed by step id.

Reads and writes ``<repo_root>/.plan-tool/purity-cache/<slug>.json`` — a
gitignored, best-effort store the two purity call sites (``detail.py``'s
post-authoring loop and ``completeness_phases._collect_purity_split_findings``)
consult so an unchanged step skips the ~130-255s Claude MIXED-STEP call.

Each entry records, per step: the combined purity cache key (step 1's
``compute_purity_cache_key`` hex digest — the hit test), its individual
components (``detail_hash``, ``all_files_fingerprint``, ``change_type``,
``depends_on``, ``purity_verdict_logic_version``) persisted separately so
step 4 can compare them one at a time, the ``detail_relpath`` renumber-guard
token, the cached purity verdict (``list[Recommendation]``; ``[]`` = checked
and pure), and the concatenated ``## Implementation`` + ``## Tests`` section
text for step 4's BACKLOG #144 magnitude diff.

An entry's *presence* means "this step was **successfully** purity-checked" —
an empty finding list reads as "checked, pure," never as "never checked" and
never as "the call failed." A failed/empty invoke must therefore never produce
an entry; this module stores only what it is handed, and the success-gating
decision lives in step 3's helper.

**Verdict determinism (accepted tradeoff).** The MIXED-STEP verdict is a
*non-deterministic* Claude judgment: identical inputs can flag a step mixed on
one call and pure on another. Caching therefore freezes one sample — a step the
model happened to judge pure stays pure until its keyed inputs change, even if a
re-roll would flag it mixed. This is intrinsic to caching any noisy judgment and
is in fact the feature's *premise*: "unchanged inputs → don't re-check." So the
cache is a pure optimization in the sense that it removes only *redundant re-work
on unchanged inputs* — it deliberately trades away the incidental re-roll that
re-running an unchanged step used to provide, not any input-driven verdict. If
that re-roll turns out to matter, a sampled/TTL forced re-check is the future
lever (out of scope here).

The module is a narrow leaf: it imports only ``plan_tool.review.Recommendation``
(the verdict shape) and stdlib — the same import surface as
``review_persistence.py``, one-way and cycle-free. No ``detail`` /
``fingerprint`` / ``cli`` edge.

**Load posture.** A missing file loads as an empty cache without raising; a
malformed or newer-version file also degrades to an empty cache (miss-and-
empty), so a corrupt cache re-checks rather than crashing a ``detail`` run.

**Concurrency.** The store is a single whole-file JSON map written atomically
(``os.replace``). Its writers (``detail``, ``completeness-audit``) already hold
the repo mutation lock (``plan_tool/repo_lock.py``), which serializes mutating
commands on a repo, so the read-modify-write of the map is not internally locked
and does not need to be. A lost or clobbered entry degrades to a re-check (the
combined key gates correctness), never a stale verdict. Do not split into
per-step files or add per-worker locking.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from plan_tool.fileio import durable_write_text
from plan_tool.review import (
    Recommendation,
    recommendation_from_persisted_mapping,
)
from plan_tool.review_persistence import normalize_restated_property_axis


PURITY_CACHE_SCHEMA_VERSION = 1

PURITY_CACHE_REL = (".plan-tool", "purity-cache")


@dataclass(frozen=True)
class PurityCacheEntry:
    """One step's cached MIXED-STEP purity check.

    ``findings == []`` means the step was checked and found pure (from a
    *successful* call — step 3 owns the don't-save-on-failure gate); the
    entry's *presence*, not its finding count, is the "was checked" signal.
    """

    step_id: int
    cache_key: str  # combined key from step 1; opaque here, the hit test
    detail_hash: Optional[str]  # detail-file hash component; None if absent
    all_files_fingerprint: str  # all_files content-fingerprint component
    change_type: str  # step change_type at check time (component + #144 source)
    depends_on: list[int]  # step depends_on at check time (component + #144 source)
    purity_verdict_logic_version: int  # PURITY_VERDICT_LOGIC_VERSION component
    detail_relpath: str  # detail-file relpath at check time; step 4's renumber guard
    findings: list[Recommendation]  # cached verdict; [] = checked and pure
    impl_tests_text: str  # concatenated ## Implementation + ## Tests text (#144 diff)
    checked_at: str  # ISO-8601 UTC, e.g. "2026-07-18T12:34:56Z"
    # True iff the write-through call that produced this verdict rendered a
    # declared risk-profile advisory into the purity prompt. The read-through
    # audit path's own prompt never does (detail.py:_cached_purity_findings),
    # so it must treat such an entry as unusable — on both the strict hit
    # check and the below-floor graded-reuse path — rather than silently
    # serving a verdict Claude produced under risk-profile framing it must
    # stay unaffected by. ``False`` for every entry written before this field
    # existed (safe: none of them could have been risk-influenced).
    risk_context_rendered: bool = False


@dataclass
class PurityCache:
    """In-memory image of one plan's purity-cache file: slug + entries by step id."""

    plan_slug: str
    entries: dict[int, PurityCacheEntry] = field(default_factory=dict)


def purity_cache_root(repo_root: Path) -> Path:
    """Return ``<repo_root>/.plan-tool/purity-cache/``."""
    return repo_root.joinpath(*PURITY_CACHE_REL)


def purity_cache_path(repo_root: Path, slug: str) -> Path:
    """Return ``<repo_root>/.plan-tool/purity-cache/<slug>.json``."""
    return purity_cache_root(repo_root) / f"{slug}.json"


def _entry_to_json(entry: PurityCacheEntry) -> dict:
    """Serialize an entry to its JSON value shape (step_id lives in the map key)."""
    data = asdict(entry)  # recurses into findings → list[dict]
    data.pop("step_id", None)
    return data


def _entry_from_json(step_id: int, data: dict) -> PurityCacheEntry:
    """Reconstruct an entry from its JSON value; the map key is authoritative for id."""
    if not isinstance(data, dict):
        raise TypeError("cached entry must be an object")
    raw_findings = data.get("findings", [])
    if not isinstance(raw_findings, list):
        raise TypeError("cached findings must be a list")
    findings: list[Recommendation] = []
    for raw_finding in raw_findings:
        if not isinstance(raw_finding, dict):
            raise TypeError("cached finding must be an object")
        findings.append(
            normalize_restated_property_axis(
                recommendation_from_persisted_mapping(raw_finding)
            )
        )
    return PurityCacheEntry(
        step_id=step_id,
        cache_key=data["cache_key"],
        detail_hash=data.get("detail_hash"),
        all_files_fingerprint=data["all_files_fingerprint"],
        change_type=data["change_type"],
        depends_on=list(data.get("depends_on", [])),
        purity_verdict_logic_version=data["purity_verdict_logic_version"],
        detail_relpath=data["detail_relpath"],
        findings=findings,
        impl_tests_text=data.get("impl_tests_text", ""),
        checked_at=data.get("checked_at", ""),
        risk_context_rendered=data.get("risk_context_rendered", False),
    )


def load_purity_cache(
    path: Path,
    *,
    valid_step_ids: Optional[Iterable[int]] = None,
) -> PurityCache:
    """Load the purity cache at ``path``; a missing/malformed file → empty cache.

    JSON object keys are strings, so ``entries`` is keyed by the step id's
    string form on disk and converted back to ``int`` here.

    When ``valid_step_ids`` is given, entries whose step id isn't in it are
    pruned (a later split/merge/scope-out can orphan an entry). Orphans are
    *safe* — a renumbered id mismatches the key on next check → re-check — but
    would accrete unbounded. Pass ``None`` (a bare read with no plan in hand)
    to skip pruning rather than guess. Pruning is entry-granularity only; a
    whole orphaned ``<slug>.json`` is left, matching the un-pruned
    ``runs/``/``checkpoints/`` siblings.
    """
    slug = path.stem
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            return PurityCache(plan_slug=slug)
        if obj.get("version") != PURITY_CACHE_SCHEMA_VERSION:
            return PurityCache(plan_slug=slug)
        raw_entries = obj.get("entries", {})
        entries: dict[int, PurityCacheEntry] = {}
        for key, value in raw_entries.items():
            step_id = int(key)
            entries[step_id] = _entry_from_json(step_id, value)
        cache = PurityCache(plan_slug=obj.get("plan_slug", slug), entries=entries)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return PurityCache(plan_slug=slug)
    if valid_step_ids is not None:
        keep = set(valid_step_ids)
        cache.entries = {
            sid: entry for sid, entry in cache.entries.items() if sid in keep
        }
    return cache


def save_purity_cache(path: Path, cache: PurityCache) -> None:
    """Atomically write the whole entries map to ``path``, creating its dir."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": PURITY_CACHE_SCHEMA_VERSION,
        "plan_slug": cache.plan_slug,
        "entries": {
            str(step_id): _entry_to_json(entry)
            for step_id, entry in cache.entries.items()
        },
    }
    durable_write_text(path, json.dumps(payload, indent=2) + "\n")
