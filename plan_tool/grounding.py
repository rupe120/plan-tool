"""Read / write the tracked grounding sidecar + a pure code-drift check.

A *grounding* records the code state a plan was last reconciled against,
so a later refresh can tell whether the code drifted underneath it. The
record is a single tracked JSON file —
``<plan-dir>/plan-details/<slug>/grounding.json`` — a sibling of the
``reports/`` subdir :func:`plan_tool.review_persistence.plan_reports_dir`
anchors to. It is deliberately tracked (it travels with the plan through
PR/merge and diffs cleanly in review), in contrast to the branch-awareness
feature's untracked per-clone binding.

The file is ``.json`` and overwritten in place on every grounding (one
fixed filename, never accumulated/timestamped). Because
:func:`plan_tool.review_persistence.compute_plan_fingerprint` globs the
bundle for ``*.md`` non-recursively, re-stamping this sidecar can never
perturb the very ``plan_fingerprint`` it stores.

It also owns the per-step **authoring fingerprint** (BACKLOG #165): a digest
of a step's declared shape plus the plan's scope-bearing sections, taken
whenever a detail file is written. A later command compares it and reports
the detail file as stale if the step, its files, or the plan's scope moved
on since — no Claude call needed.

The module is a stdlib-only leaf: it shells out to no backend, and pulls in
the diff machinery (:func:`plan_tool.fingerprint.diff_code_fingerprint`) and
the slug helper only function-locally, keeping the read/write path
import-light. ``plan_tool.parser`` and ``plan_tool.schema`` are the
exception — both are leaves themselves, so they're imported at module level
for the authoring-fingerprint helpers below.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from plan_tool.fingerprint import CodeFingerprintDiff

from plan_tool.fileio import durable_write_text
from plan_tool.parser import ParseError, _split_frontmatter, split_body_sections
from plan_tool.schema import Plan, Step
from plan_tool.scope_fence import _fenced_code_spans


GROUNDING_FILENAME = "grounding.json"
GROUNDING_SCHEMA_VERSION = 1

# Marks "caller didn't pass step_authoring_fingerprints" so we can tell it
# apart from an explicit ``{}`` ("clear it"). write_grounding's older callers
# know nothing about this field and must not wipe it on every restamp.
_PRESERVE_EXISTING = object()


@dataclass
class Grounding:
    """In-memory representation of one persisted grounding.

    Field naming mirrors :class:`plan_tool.review_persistence.SavedReview`
    so the two records read consistently.

    ``grounded_at`` is ISO-8601 UTC with trailing ``Z`` (e.g.
    ``"2026-06-16T12:34:56Z"``). ``plan_fingerprint`` is the digest from
    :func:`plan_tool.review_persistence.compute_plan_fingerprint`; ``""``
    is the unset sentinel. ``code_fingerprint`` is the
    :func:`plan_tool.fingerprint.compute_code_fingerprint`
    ``{repo-relative-posix-path: sha256-hex}`` map, stored verbatim and
    opaque — this module never recomputes or interprets it.

    Unlike ``SavedReview`` there is no ``code_fingerprint_present`` marker:
    an absent sidecar already means "never grounded" (``read_grounding``
    returns ``None``), so the ``{}``-is-ambiguous problem never arises.

    ``step_authoring_fingerprints`` maps ``str(step_id)`` to a digest of
    that step's shape at detail time (BACKLOG #165) — see
    ``DATA_CONTRACT.md``'s Grounding sidecar section for the field and how
    it's kept from being clobbered on restamp.
    """

    plan_slug: str
    grounded_at: str
    plan_fingerprint: str = ""
    code_fingerprint: dict[str, str] = field(default_factory=dict)
    step_authoring_fingerprints: dict[str, str] = field(default_factory=dict)
    schema_version: int = GROUNDING_SCHEMA_VERSION


def grounding_path(plan_path: Path) -> Path:
    """Return the grounding sidecar path for ``plan_path``.

    ``<plan_path.parent>/plan-details/<slug>/grounding.json`` — a sibling
    of the ``reports/`` directory
    :func:`plan_tool.review_persistence.plan_reports_dir` anchors to.
    ``slug`` strips a leading ``<digit>-`` from the plan filename's stem.
    """
    from plan_tool.locator import slug_from_filename

    slug = slug_from_filename(plan_path)  # default_to_stem=True → never None
    assert slug is not None
    return plan_path.parent / "plan-details" / slug / GROUNDING_FILENAME


def write_grounding(
    plan_path: Path,
    *,
    plan_fingerprint: str,
    code_fingerprint: dict[str, str],
    step_authoring_fingerprints: object = _PRESERVE_EXISTING,
    now: Optional[datetime] = None,
) -> Path:
    """Persist a grounding to its sidecar and return the file path.

    The ``plan_slug`` is derived internally from ``plan_path`` (single-
    sourced from the same place :func:`grounding_path` uses) so it can
    never disagree with the file location. ``code_fingerprint`` is stored
    verbatim and opaque. ``now`` is injectable for deterministic tests
    (matching ``save_review``); when omitted the current UTC time is used.

    ``step_authoring_fingerprints``, when omitted, carries forward whatever
    the sidecar already has (``{}`` if none) instead of clearing it — pass
    an explicit ``dict`` (even ``{}``) to actually replace it.

    Creates the sidecar's parent directory if missing and overwrites any
    prior grounding in place. Returns the absolute sidecar path.
    """
    from plan_tool.locator import slug_from_filename

    slug = slug_from_filename(plan_path)  # default_to_stem=True → never None
    assert slug is not None
    grounded_at = (now or datetime.now(timezone.utc)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    if step_authoring_fingerprints is _PRESERVE_EXISTING:
        existing = read_grounding(plan_path)
        step_authoring_fingerprints = (
            existing.step_authoring_fingerprints if existing is not None else {}
        )
    record = Grounding(
        plan_slug=slug,
        grounded_at=grounded_at,
        plan_fingerprint=plan_fingerprint,
        code_fingerprint=code_fingerprint,
        step_authoring_fingerprints=step_authoring_fingerprints,
    )
    path = grounding_path(plan_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    durable_write_text(path, json.dumps(asdict(record), indent=2) + "\n")
    return path


def read_grounding(plan_path: Path) -> Optional[Grounding]:
    """Load the grounding sidecar for ``plan_path``, or ``None``.

    Fail-soft — the deliberate divergence from
    :func:`plan_tool.review_persistence.load_review`, which raises. Every
    degenerate case (absent file, unreadable/malformed JSON, non-dict
    top-level, mismatched/absent ``schema_version``, or a missing/wrong-
    typed required field) returns ``None`` so a pre-feature or corrupt
    sidecar reads as "needs grounding" and never crashes the caller.
    """
    path = grounding_path(plan_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("schema_version") != GROUNDING_SCHEMA_VERSION:
        return None
    try:
        return Grounding(
            plan_slug=data["plan_slug"],
            grounded_at=data["grounded_at"],
            plan_fingerprint=data.get("plan_fingerprint", ""),
            code_fingerprint=data.get("code_fingerprint", {}),
            step_authoring_fingerprints=data.get(
                "step_authoring_fingerprints", {}
            ),
        )
    except (KeyError, TypeError):
        return None


def check_grounding_drift(
    grounding: Grounding,
    current_code_fp: dict[str, str],
    repo_root: Path,
) -> "CodeFingerprintDiff":
    """Diff the stored code map against ``current_code_fp``.

    Delegates entirely to
    :func:`plan_tool.fingerprint.diff_code_fingerprint`. Mints no
    diff logic of its own.

    Code axis only: ``grounding.plan_fingerprint`` travels with the sidecar
    but is *not* consulted here — the refresh gate asks "did the code drift
    since grounding," and the plan-side digest feeds the reconcile engine's
    own reuse machinery, not this gate.
    """
    from plan_tool.fingerprint import diff_code_fingerprint

    return diff_code_fingerprint(
        grounding.code_fingerprint, current_code_fp, repo_root
    )


def extract_scope_bearing_sections(plan_path: Path) -> tuple[str, str]:
    """Return ``(out_of_scope, deferred)`` body text from ``plan_path``.

    Empty string for either when the plan can't be read or the section is
    missing. These two headings are the plan body's only schema-recognized
    scope carriers (``docs/how-to/pipeline/audit.md``), and text comes back verbatim —
    not normalized — so a real edit always changes the digest.

    Raises :class:`ValueError` when the body has an unmatched opening code
    fence. Silently falling back to ``"", ""`` here (like the unreadable/
    malformed cases below) would fail the digest guarantee above rather than
    honor it: everything after the stray fence — real ``## Out of scope`` /
    ``## Deferred`` sections included — reads as fenced and vanishes, the
    *same* way before and after an edit to that text, so the digest would
    stop changing exactly when it most needs to. Callers already treat this
    computation as best-effort (``stale_detail_warning``, ``_stamp_grounding``
    both catch broadly), so raising surfaces the malformed plan instead of
    quietly certifying it as unchanged.
    """
    try:
        text = plan_path.read_text(encoding="utf-8")
        body = _split_frontmatter(text).body
    except (OSError, ParseError):
        # Unreadable or malformed frontmatter — not this function's job to
        # reject; treat as "no scope-bearing text found."
        return "", ""
    if _fenced_code_spans(body).unmatched_opening is not None:
        raise ValueError(
            f"{plan_path}: unmatched opening code fence in plan body; add a "
            "matching closing fence before scope-bearing sections can be "
            "read reliably."
        )
    sections = split_body_sections(body, ignore_fenced_code=True)
    return (
        sections.get("out of scope", ""),
        sections.get("deferred", ""),
    )


def compute_step_authoring_fingerprint(
    step: Step, *, out_of_scope: str, deferred: str
) -> str:
    """Digest a step's declared shape plus the plan's scope-bearing
    sections, taken when its detail file is written (BACKLOG #165).

    Hashes title/files/creates/change_type/depends_on plus the two scope
    sections, nothing else. Don't reuse
    :func:`plan_tool.detail._detail_step_input_hash` here — that one is a
    cache key for resuming ``detail`` and is deliberately blind to
    plan-level edits, the exact opposite of what this needs to catch.
    """
    from plan_tool.checkpoint import compute_input_hash

    return compute_input_hash(
        {
            "title": step.title,
            "files": list(step.files),
            "creates": list(step.creates),
            "change_type": step.change_type.value if step.change_type else None,
            "depends_on": list(step.depends_on),
            "out_of_scope": out_of_scope,
            "deferred": deferred,
        }
    )


def stale_detail_steps(grounding: Grounding, plan: Plan, plan_path: Path) -> list[int]:
    """Return step ids whose detail file is stale — the step, its files, or
    the plan's scope have changed since that detail was last authored.

    A step with no stored fingerprint (never detailed, or detailed before
    this existed) is skipped, not reported. Report-only: nothing here
    blocks or regenerates anything.
    """
    if not grounding.step_authoring_fingerprints:
        return []
    out_of_scope, deferred = extract_scope_bearing_sections(plan_path)
    stale: list[int] = []
    for step in plan.steps:
        stored = grounding.step_authoring_fingerprints.get(str(step.id))
        if stored is None:
            continue
        current = compute_step_authoring_fingerprint(
            step, out_of_scope=out_of_scope, deferred=deferred
        )
        if current != stored:
            stale.append(step.id)
    return stale


def stale_detail_warning(plan: Plan, plan_path: Path) -> Optional[str]:
    """One-line stale-detail warning for ``plan``, or ``None``.

    Shared by ``status`` and ``completeness-audit``'s pre-flight so the two
    don't carry their own copies of the read/compare/word-it logic. Never
    raises — a read or compute failure just means no warning.
    """
    try:
        grounding = read_grounding(plan_path)
        stale = stale_detail_steps(grounding, plan, plan_path) if grounding else []
    except Exception:  # noqa: BLE001 — advisory only, never break the caller
        return None
    if not stale:
        return None
    ids = ", ".join(str(step_id) for step_id in stale)
    return (
        f"stale detail: step(s) {ids} were authored against a different "
        "plan version — consider regenerating (plan-tool detail --force)"
    )
