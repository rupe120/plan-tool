"""Scope-out primitives: the carved-region forward-seed renderer and the
deterministic plan-narrow (drop one step + re-canonicalize the graph).

Two halves of scope-out live here:

- **The seed renderer** — :func:`render_carved_seed`, a pure deterministic
  string builder that serializes a carved-out step (its frontmatter, detail
  body, run state, and upstream deps) into a ``create --from-existing``
  re-plannable seed. No file IO, no git, no Claude, no ``invoker=`` seam;
  mirrors :mod:`plan_tool.annotate_render`'s ``render_create_seed`` design.
- **The narrow** — :func:`compute_narrow` (dry-run preview) and
  :func:`apply_narrow` (all-or-nothing commit with rollback): drop the carved
  step, renumber survivors to a contiguous ``1..N-1``, repair every
  ``depends_on`` edge, migrate/archive detail files, and re-establish the run
  cursor. The narrow is the IO half (it imports :mod:`plan_tool.detail` and
  :mod:`plan_tool.parser`); the no-IO contract applies to the seed renderer
  only. The narrow only *detects* structural blockers and refuses to corrupt.
- **The orchestrator** — :func:`scope_out_step` (returning a frozen
  :class:`ScopeOutResult`): the policy half composing the two above into one
  apply-or-recommend gate (re-parse → blocker gate → opt-in → confirm →
  seed-first apply). Spends **zero Claude** — both halves are deterministic —
  so unlike its sibling bridge :func:`launcher.escalate_to_split` it takes no
  ``invoker=`` seam.
"""

from __future__ import annotations

import copy
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from plan_tool import locator
from plan_tool.detail import (
    _DETAIL_ID_PREFIX_RE,
    _repo_relative,
)
from plan_tool.create import _remap_depends_on_notes, _summarize_step_graph_error
from plan_tool.detail_artifacts import (
    require_supported_detail_format_version,
    resolve_detail_artifact,
    strip_detail_format_version_marker,
)
from plan_tool.parser import (
    _frontmatter_hash,
    _split_frontmatter,
    parse_plan,
    refresh_plan_provenance,
    write_plan,
)
from pydantic import ValidationError as PydanticValidationError

from plan_tool.schema import Plan, PlanStatus, Step, StepScope, StepStatus
from plan_tool.scope_fence import (
    _fenced_code_spans,
    _strip_frontmatter,
    collapse_intent_to_one_line,
    extract_h2_sections,
    is_placeholder_intent,
    source_references_block,
)


def _source_plan_intent_framing(plan_intent: Optional[str]) -> list[str]:
    """One intro line naming the *source* plan's intent (never ``## Outcome``).

    Omits fence non-values (missing / blank / the six TODO/TBD spellings
    :func:`is_placeholder_intent` owns). Tells the re-plan to state its own
    Outcome rather than inherit this why.
    """
    if plan_intent is None:
        return []
    collapsed = collapse_intent_to_one_line(plan_intent)
    if not collapsed or is_placeholder_intent(collapsed):
        return []
    return [
        (
            f"Source plan intent: {collapsed}. State the re-plan's own Outcome; "
            "do not inherit this as the new plan's purpose."
        ),
        "",
    ]


def render_carved_seed(
    *,
    plan_title: str,
    carved_step: Step,
    detail_body: str | None,
    detail_missing: bool = False,
    upstream_context: Sequence[tuple[int, str, str, str | None]] = (),
    source_path: Path,
    plan_intent: Optional[str] = None,
    source_references: str | None = None,
) -> str:
    """Render the carved-region ``create --from-existing`` forward-seed.

    ``carved_step``'s detail/frontmatter is work to re-plan (``## Scope to
    re-plan``); its run state is carried as narrative prose, never as a live
    ``status`` round-trip or a non-existent ``progress`` field. Upstream deps
    split by status: DONE entries are assumed done-context, non-DONE entries
    render as explicit external prerequisites. ``source_path`` is injected
    (not derived) — used only for the provenance header, no filesystem access.
    ``plan_intent`` is the source plan's why (labeled as source context, never
    written as ``## Outcome``).
    """
    header = (
        "<!-- plan-tool scope-out carved-seed\n"
        f"source: {source_path}\n"
        f"carved_step: {carved_step.id}\n"
        "-->"
    )

    lines: list[str] = [
        header,
        "",
        f"# Plan seed: carved step {carved_step.id} from {plan_title}",
        "",
        (
            "This is a `plan-tool create --from-existing` input. It re-plans "
            "**only the carved region** in **Scope to re-plan** below. The "
            "**Done-context** and **Upstream prerequisites** sections are "
            "already-implemented context, not work to re-plan."
        ),
        "",
    ]
    lines.extend(_source_plan_intent_framing(plan_intent))

    lines.extend(_scope_block(carved_step, detail_body, detail_missing))
    lines.extend(_done_context_block(carved_step))
    lines.extend(_upstream_block(upstream_context))
    lines.extend(source_references_block(source_path, source_references))

    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- Source plan: {source_path}")
    lines.append(f"- Carved step: {carved_step.id}")
    lines.append("")

    return "\n".join(lines)


def render_carved_region_seed(
    *,
    plan_title: str,
    carved_steps: Sequence[Step],
    detail_bodies: Sequence[str | None],
    detail_missings: Sequence[bool],
    upstream_context: Sequence[tuple[int, str, str, str | None]] = (),
    source_path: Path,
    plan_intent: Optional[str] = None,
    source_references: str | None = None,
) -> str:
    """Render one forward-seed covering a whole carved *region* (≥2 steps).

    Reuses :func:`render_carved_seed`'s block helpers (``_scope_block`` /
    ``_done_context_block`` / ``_upstream_block``) so the region seed's prose is
    the single-step seed's vocabulary repeated once per carved step (ascending
    id order), plus one merged upstream block. ``detail_bodies`` and
    ``detail_missings`` are parallel to ``carved_steps``. ``upstream_context``
    already excludes in-region deps (an edge between two carved steps is
    re-planned together, not an external prerequisite). ``plan_intent`` is
    named once as source context (never as ``## Outcome``)."""
    ids = [s.id for s in carved_steps]
    id_list = ", ".join(str(i) for i in ids)
    header = (
        "<!-- plan-tool scope-out carved-seed\n"
        f"source: {source_path}\n"
        f"carved_steps: {id_list}\n"
        "-->"
    )

    lines: list[str] = [
        header,
        "",
        f"# Plan seed: carved steps {ids[0]}..{ids[-1]} from {plan_title}",
        "",
        (
            "This is a `plan-tool create --from-existing` input. It re-plans "
            "**only the carved region** in the **Scope to re-plan** sections "
            "below (one per carved step). The **Done-context**, **Upstream "
            "prerequisites**, and **External prerequisites** sections are "
            "already-implemented context, not work to re-plan."
        ),
        "",
    ]
    lines.extend(_source_plan_intent_framing(plan_intent))

    for carved_step, detail_body, detail_missing in zip(
        carved_steps, detail_bodies, detail_missings
    ):
        lines.extend(_scope_block(carved_step, detail_body, detail_missing))
        lines.extend(_done_context_block(carved_step))
    lines.extend(_upstream_block(upstream_context))
    lines.extend(source_references_block(source_path, source_references))

    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- Source plan: {source_path}")
    lines.append(f"- Carved steps: {id_list}")
    lines.append("")

    return "\n".join(lines)


def _scope_block(
    carved_step: Step, detail_body: str | None, detail_missing: bool
) -> list[str]:
    """Render the carved-region work for ``create --from-existing`` to decompose.

    The carved step's title, intent (when fence-usable), files, change type,
    feature tags, scope disposition, and detail body — the actual work to
    re-plan, never marked as already-implemented done-context.
    """
    out: list[str] = [
        f"## Scope to re-plan (source step {carved_step.id})",
        "",
        f"**{carved_step.title}**",
        "",
    ]

    raw_intent = carved_step.intent
    if raw_intent is not None:
        step_intent = collapse_intent_to_one_line(raw_intent)
        if step_intent and not is_placeholder_intent(step_intent):
            out.append(f"Intent: {step_intent}")
            out.append("")

    # Files — iterate ``all_files`` directly (ordered, de-duplicated) so the
    # bullet order is deterministic; never wrap it in ``set(...)``.
    files = carved_step.all_files
    if files:
        out.append("Files:")
        out.extend(f"- {path}" for path in files)
    else:
        out.append("Files: no files declared.")
    out.append("")

    change = carved_step.change_type.value if carved_step.change_type else "unspecified"
    out.append(f"Change type: {change}")
    out.append("")

    # Feature tags — the re-plan must re-register any tag the dropped step
    # solely implemented (step 2's narrow prunes the now-unimplemented entries).
    if carved_step.features:
        out.append(
            "Features to re-register (the carved step solely implemented these "
            "— the re-plan's successor must re-register any still needed):"
        )
        out.extend(f"- {tag}" for tag in carved_step.features)
        out.append("")

    if carved_step.concept_ids:
        out.append("Concept IDs owned by this carved step:")
        out.extend(f"- {concept_id}" for concept_id in carved_step.concept_ids)
        out.append("")

    # Scope disposition — a parked carve keeps its gated disposition so
    # ``create --from-existing`` does not resurrect it as committed work.
    if carved_step.scope is not StepScope.COMMITTED:
        out.append(
            f"_Disposition: this step was parked as `{carved_step.scope.value}` "
            "— re-plan only if intentionally resuming abandoned/deferred work._"
        )
        out.append("")

    if detail_body is not None:
        out.append(strip_detail_format_version_marker(detail_body))
    elif detail_missing:
        out.append(
            "_Missing detail: the carved step's `detail:` pointer was set but "
            "its file was absent (moved/deleted/slug-drifted), so the original "
            "body could not be carried. Re-plan scope falls back to the carved "
            "frontmatter only._"
        )
    else:
        out.append(
            "_The carved step was never detailed; re-plan scope comes from the "
            "carved frontmatter only._"
        )
    out.append("")

    return out


def _done_context_block(carved_step: Step) -> list[str]:
    """Render the carved step's own run state.

    A DONE carved step renders plainly as done-context under the explicit
    don't-re-plan framing. A non-DONE (in-progress/CURRENT) step's status is
    attempted/partial context to account for — **not** already-implemented
    done-context, since its detail/frontmatter stays work-to-re-plan above.
    """
    out: list[str] = [
        (
            "## Done-context (already done — do not re-plan; "
            f"source step {carved_step.id})"
        ),
        "",
        (
            "Everything in this section is **already implemented** done-context. "
            "Do **not** re-plan or re-implement it."
        ),
        "",
    ]

    status = carved_step.status
    note = carved_step.status_note
    if status is StepStatus.DONE:
        line = f"The carved step was left in status `{status.value}`."
        if note:
            line += f" Note: {note}"
        out.append(line)
    else:
        # Non-DONE — attempted/partial context, framed as half-done work the
        # re-plan must account for, NOT as already-implemented done-context.
        line = (
            f"The carved step was left **attempted/partial** (status "
            f"`{status.value}`) — account for this in the re-plan, but treat its "
            "work (in **Scope to re-plan** above) as not yet complete."
        )
        if note:
            line += f" Left half-done: {note}"
        out.append(line)
    out.append("")

    return out


def _upstream_block(
    upstream_context: Sequence[tuple[int, str, str, str | None]]
) -> list[str]:
    """Render upstream deps split by status into two optional sections.

    DONE deps → assumed-done prerequisites; non-DONE deps → explicit external
    prerequisites. Each empty bucket omits its heading entirely.
    """
    done = [
        (sid, title, note)
        for sid, title, status, note in upstream_context
        if status == "done"
    ]
    external = [
        (sid, title, status, note)
        for sid, title, status, note in upstream_context
        if status != "done"
    ]

    def _append_note(line: str, note: str | None) -> str:
        if note:
            return f"{line} — consumes: {note}"
        return line

    out: list[str] = []
    if done:
        out.append("## Upstream prerequisites (assumed already done)")
        out.append("")
        out.extend(
            _append_note(f"- step {sid}: {title}", note) for sid, title, note in done
        )
        out.append("")
    if external:
        out.append("## External prerequisites (not done yet)")
        out.append("")
        out.extend(
            _append_note(f"- step {sid} [{status}]: {title}", note)
            for sid, title, status, note in external
        )
        out.append("")

    return out


# --------------------------------------------------------------------------
# The narrow: drop an ordered set of steps + re-canonicalize the graph (IO half).
# --------------------------------------------------------------------------


class NarrowError(Exception):
    """Raised when :func:`apply_narrow` refuses to (or fails to) narrow.

    Refusal is the safe case: a blocker-bearing or stale preview never
    touches disk. A mid-apply failure rolls the journal back LIFO and
    re-raises this so the caller sees the pre-narrow state restored.
    """


def _reject_unmatched_plan_fence(plan_path: Path) -> None:
    text = plan_path.read_text(encoding="utf-8")
    if _fenced_code_spans(_strip_frontmatter(text)).unmatched_opening is not None:
        raise NarrowError(
            f"{plan_path}: unmatched opening code fence; add a matching closing fence "
            "before scoping out a step."
        )


@dataclass(frozen=True)
class NarrowBlocker:
    """One structural reason a carve cannot proceed — a fact about the plan
    graph, not a policy decision.

    ``kind`` is one of ``"step-missing"`` / ``"empty-plan"`` /
    ``"non-canonical-numbering"`` / ``"inbound-dependent"`` /
    ``"downstream-orphan"``. ``step_ids`` names the offending survivor ids
    (empty for the whole-plan kinds). Step 3 maps ``kind`` → its
    ``EscalateResult``-style ``outcome`` and owns the opt-in/TTY decision.
    """

    kind: str
    step_ids: list[int]
    message: str


@dataclass(frozen=True)
class NarrowPreview:
    """The dry-run plan for a carve. ``blockers`` empty ⇒ safe to apply.

    Mirrors :class:`detail.MergeResult`'s ``renumber`` / ``new_plan`` preview
    fields so the two read alike. ``narrowed_plan`` is the complete ``Plan``
    to persist (``None`` when blockers prevent constructing a valid one);
    ``source_frontmatter_hash`` is the caller-supplied provenance from the
    parse snapshot that produced the ``Plan`` — :func:`apply_narrow` rejects a
    stale preview against it before touching disk. ``carved_ids`` is the sorted,
    de-duplicated ordered set of dropped ids (a single-id carve is ``[N]``);
    ``archive_details`` carries one entry per carved id that had a detail file.
    """

    carved_ids: list[int]
    source_plan_path: Path
    source_frontmatter_hash: str
    blockers: list[NarrowBlocker] = field(default_factory=list)
    new_steps: list[Step] = field(default_factory=list)
    narrowed_plan: Plan | None = None
    renumber: list[tuple[int, int]] = field(default_factory=list)
    new_plan: list[tuple[int, str, list[int]]] = field(default_factory=list)
    detail_renames: list[tuple[Path, Path]] = field(default_factory=list)
    archive_details: list[Path] = field(default_factory=list)
    new_current_id: int | None = None
    new_plan_status: PlanStatus = PlanStatus.PLANNING


@dataclass(frozen=True)
class NarrowResult:
    """What :func:`apply_narrow` actually committed — lets step 3 and tests
    assert the applied outcome without re-reading disk. ``carved_ids`` lists the
    dropped ids and ``archived`` the archived carved-detail files, one per id
    that had a detail (empty when none did)."""

    carved_ids: list[int]
    renumber: list[tuple[int, int]]
    new_current_id: int | None
    new_plan_status: PlanStatus
    archived: list[Path]
    migrated: list[Path]


# Body prose still names carved / renumbered work after a successful narrow —
# silence is the bug (CLAUDE.md structural-change sweep). Auto-rewrite is out
# of scope; :func:`find_scope_out_body_hits` only reports what to sweep.
_STEP_REF_RE = re.compile(r"(?i)\bsteps?\s+(\d+)\b")


@dataclass(frozen=True)
class BodySweepHit:
    """One leftover body reference a human should sweep after a carve."""

    kind: str  # "carved-id" | "shifted-id" | "carved-title"
    detail: str
    line_no: int
    line: str


def find_scope_out_body_hits(
    body: str,
    *,
    carved_ids: Sequence[int],
    carved_titles: Sequence[str],
    renumber: Sequence[tuple[int, int]],
) -> list[BodySweepHit]:
    """Scan plan-body prose for references the narrow did not rewrite.

    Flags ``step N`` / ``steps N`` mentions of carved ids and of old ids that
    shifted (``old→new``), plus case-insensitive word-boundary occurrences of
    carved step titles (length ≥ 4, to skip trivial labels). Substring stems
    ("Measure" vs "Measurement") do not match. Decision/frontmatter-only plans
    with an empty body yield ``[]``.
    """
    if not body or not body.strip():
        return []
    carved = set(carved_ids)
    shifted_old = {old for old, _new in renumber}
    title_res = [
        (t.strip(), re.compile(rf"(?i)\b{re.escape(t.strip())}\b"))
        for t in carved_titles
        if t and len(t.strip()) >= 4
    ]
    hits: list[BodySweepHit] = []
    seen: set[tuple[str, str, int]] = set()
    for line_no, line in enumerate(body.splitlines(), start=1):
        for m in _STEP_REF_RE.finditer(line):
            sid = int(m.group(1))
            if sid in carved:
                kind, detail = "carved-id", f"step {sid} (carved out)"
            elif sid in shifted_old:
                new = next(n for o, n in renumber if o == sid)
                kind, detail = (
                    "shifted-id",
                    f"step {sid} (now step {new} after renumber)",
                )
            else:
                continue
            key = (kind, detail, line_no)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                BodySweepHit(
                    kind=kind, detail=detail, line_no=line_no, line=line.strip(),
                )
            )
        for title, title_re in title_res:
            if not title_re.search(line):
                continue
            kind, detail = "carved-title", f"title {title!r}"
            key = (kind, detail, line_no)
            if key in seen:
                continue
            seen.add(key)
            hits.append(
                BodySweepHit(
                    kind=kind, detail=detail, line_no=line_no, line=line.strip(),
                )
            )
    return hits


@dataclass(frozen=True)
class _ConceptNarrowUpdate:
    """Validated concept mutation paired with the source plan snapshot.

    ``prepared_plan_fingerprint`` is the plan fingerprint read at *prepare*
    time, which is what :func:`apply_narrow` re-checks. Do not swap it for the
    loaded record's own ``plan_fingerprint``: the two coincide only for a
    full-tree record (whose load is fingerprint-gated). A flat decision record
    carries its authoring-time fingerprint as provenance and is deliberately
    not gated on load, so comparing against that rejects every plan edited
    since the deferral was recorded.
    """

    updated_tree: object
    original_sidecar_text: str
    prepared_plan_fingerprint: str


def ownerless_carved_concept_ids(
    carved_steps: Sequence[Step], preview: NarrowPreview
) -> list[str]:
    """Return carved concept IDs with no committed owner in ``preview``.

    IDs retain their first-authored order across the carved steps and appear
    at most once. Only explicit ``Step.concept_ids`` links count; parked
    survivors deliberately do not provide completeness coverage.
    """
    surviving = {
        concept_id
        for step in preview.new_steps
        if step.scope is StepScope.COMMITTED
        for concept_id in step.concept_ids
    }
    ownerless: list[str] = []
    seen: set[str] = set()
    for step in carved_steps:
        for concept_id in step.concept_ids:
            if concept_id not in seen and concept_id not in surviving:
                seen.add(concept_id)
                ownerless.append(concept_id)
    return ownerless


def _prepare_concept_narrow_update(
    plan_path: Path,
    carved_steps: Sequence[Step],
    preview: NarrowPreview,
) -> _ConceptNarrowUpdate | None:
    """Load, validate, and prepare required deferrals without writing."""
    from plan_tool.concept_review import ConceptReviewError, review_concept_scope
    from plan_tool.concept_tree import (
        InvalidConceptTreeError,
        StaleConceptTreeError,
        concepts_path,
        load_concepts,
    )
    from plan_tool.review_persistence import compute_plan_fingerprint

    carved_concept_ids = [
        concept_id for step in carved_steps for concept_id in step.concept_ids
    ]
    fingerprint = compute_plan_fingerprint(plan_path)
    try:
        tree = load_concepts(plan_path, fingerprint)
    except (InvalidConceptTreeError, StaleConceptTreeError) as exc:
        raise NarrowError(f"cannot use concept record for scope-out: {exc}") from exc
    if tree is None and not carved_concept_ids:
        return None
    if tree is None:
        raise NarrowError(
            "cannot scope out concept-owned work without a current concept record"
        )

    known_ids = {node.id for node in tree.concepts}
    unknown = list(
        dict.fromkeys(cid for cid in carved_concept_ids if cid not in known_ids)
    )
    if unknown:
        raise NarrowError(
            "cannot scope out concept ownership absent from the concept record: "
            + ", ".join(unknown)
        )

    ownerless = ownerless_carved_concept_ids(carved_steps, preview)
    updated = copy.deepcopy(tree)
    if ownerless:
        try:
            updated = review_concept_scope(
                tree,
                ownerless,
                {concept_id: "defer" for concept_id in ownerless},
                fingerprint,
                sign_off=True,
            )
        except ConceptReviewError as exc:
            raise NarrowError(f"cannot prepare concept deferrals: {exc}") from exc

    sidecar = concepts_path(plan_path)
    try:
        original_text = sidecar.read_text(encoding="utf-8")
    except OSError as exc:
        raise NarrowError(f"cannot snapshot concept record for scope-out: {exc}") from exc
    return _ConceptNarrowUpdate(updated, original_text, fingerprint)


def compute_frontmatter_hash(plan_path: Path) -> str:
    """SHA-256 of ``plan_path``'s current frontmatter block.

    The caller captures this from the same parse snapshot that produced the
    ``Plan`` passed to :func:`compute_narrow` (read the file once, parse it,
    hash it here) so :func:`apply_narrow` can reject a stale preview. Uses the
    same primitives :mod:`plan_tool.parser` hashes provenance with, so the
    value matches what ``write_plan``'s compare-and-swap compares against.
    """
    text = Path(plan_path).read_text(encoding="utf-8")
    return _frontmatter_hash(_split_frontmatter(text).frontmatter_yaml)


def _normalize_carved_ids(
    carved_id: int | None, carved_ids: Sequence[int] | None
) -> list[int]:
    """Fold the back-compat scalar (``carved_id``) and the canonical set
    (``carved_ids``) entry points into one sorted, de-duplicated id list.

    Exactly one of the two must be supplied; ``carved_id=N`` normalizes to
    ``[N]`` so the single-id path stays the special case of the set path. The
    narrow accepts any subset (contiguous or not) — deterministic range
    validation is the CLI's concern, not this layer's."""
    if (carved_id is None) == (carved_ids is None):
        raise ValueError(
            "compute_narrow requires exactly one of carved_id= or carved_ids="
        )
    raw = [carved_id] if carved_id is not None else list(carved_ids)
    normalized = sorted(set(raw))
    if not normalized:
        raise ValueError("compute_narrow requires at least one carved id")
    return normalized


def compute_narrow(
    plan: Plan,
    *,
    carved_id: int | None = None,
    carved_ids: Sequence[int] | None = None,
    plan_path: Path,
    repo_root: Path,
    source_frontmatter_hash: str,
) -> NarrowPreview:
    """Build the dry-run :class:`NarrowPreview` for dropping ``carved_ids``.

    Accepts either the back-compat scalar ``carved_id=N`` or the canonical
    ordered set ``carved_ids=[...]`` (exactly one); both normalize to a sorted,
    de-duplicated id list, so a single-id carve is the special case of a set
    carve. Pure computation — no plan/detail mutation; the only filesystem touch
    is testing whether a detail file exists (to decide renames / archive). ``plan``
    and ``source_frontmatter_hash`` must come from the *same* parse snapshot; this
    stores the hash as provenance and never re-reads the plan frontmatter. See
    ``docs/implementation-plans``' scope-out plan for the blocker semantics.
    """
    carved = _normalize_carved_ids(carved_id, carved_ids)
    carved_set = set(carved)
    ids = [s.id for s in plan.steps]
    id_set = set(ids)

    # 1. Missing carved id — fatal to construction.
    missing = [c for c in carved if c not in id_set]
    if missing:
        return _blocked_preview(
            carved,
            plan_path,
            source_frontmatter_hash,
            plan.status,
            [
                NarrowBlocker(
                    kind="step-missing",
                    step_ids=[],
                    message=f"step(s) {missing} are not in the plan",
                )
            ],
        )

    # 2. Non-canonical numbering — the drop arithmetic (each survivor shifts
    #    down by the count of carved ids below it) is valid only on contiguous,
    #    position-ordered ids; refuse rather than emit a corruptible preview.
    canonical = list(range(1, len(plan.steps) + 1))
    if ids != canonical:
        return _blocked_preview(
            carved,
            plan_path,
            source_frontmatter_hash,
            plan.status,
            [
                NarrowBlocker(
                    kind="non-canonical-numbering",
                    step_ids=[],
                    message=(
                        "step ids are not canonical (expected contiguous "
                        f"{canonical[0]}..{canonical[-1]} in order); restore "
                        "canonical numbering (re-plan) before scope-out"
                    ),
                )
            ],
        )

    carved_steps = [plan.step_by_id(c) for c in carved]
    survivors = [s for s in plan.steps if s.id not in carved_set]
    # Single old→new id map — the one source for both the step renumber and the
    # ``depends_on`` remap (do NOT re-derive the shift in two places). Each
    # survivor shifts down by the number of carved ids strictly below it.
    old_to_new = {
        s.id: s.id - sum(1 for c in carved if c < s.id) for s in survivors
    }

    # 3. Graph-unsafe blockers (fatal to construction): a *kept* inbound
    #    dependent on any carved step has no survivor to repoint to (a
    #    carved-on-carved edge is fine — both drop), and a downstream DONE
    #    step that shifts would renumber while carrying id-keyed run state.
    #    Gate on DONE only (mirrors ``split_is_safe``/``_merge_is_safe``): a
    #    downstream CURRENT step is "next runnable", not mid-execution, and
    #    renumbers cleanly — only a green (DONE) commit subject is
    #    renumber-orphanable. Accepted residual risk (same as
    #    ``split_safety.split_is_safe``): a CURRENT step's landed-but-unflipped
    #    lesson is renumber-orphaned in the narrow SIGKILL window; the fallout
    #    is soft (advisory) and a lesson/run-log scan to catch it is unsound, so
    #    the gate stays DONE-only.
    inbound = sorted(
        s.id for s in survivors if any(d in carved_set for d in s.depends_on)
    )
    downstream_orphans = sorted(
        s.id
        for s in survivors
        if s.status == StepStatus.DONE and any(c < s.id for c in carved)
    )
    graph_blockers: list[NarrowBlocker] = []
    if inbound:
        graph_blockers.append(
            NarrowBlocker(
                kind="inbound-dependent",
                step_ids=inbound,
                message=(
                    f"step(s) {inbound} depend_on carved step(s) {carved}; "
                    "a drop has no survivor to repoint them to"
                ),
            )
        )
    if downstream_orphans:
        graph_blockers.append(
            NarrowBlocker(
                kind="downstream-orphan",
                step_ids=downstream_orphans,
                message=(
                    f"step(s) {downstream_orphans} after a carved step are "
                    "done; renumbering them would orphan their "
                    "id-keyed run state"
                ),
            )
        )
    if graph_blockers:
        return _blocked_preview(
            carved, plan_path, source_frontmatter_hash, plan.status, graph_blockers
        )

    # Build the renumbered survivors with repaired edges + repointed detail.
    new_steps: list[Step] = []
    detail_renames: list[tuple[Path, Path]] = []
    for s in survivors:
        new_id = old_to_new[s.id]
        # Map each dep through ``old_to_new`` (carved deps are impossible —
        # inbound was a blocker above); drop the self-edge (structurally
        # impossible, but mirror ``_apply_step_merge``'s hygiene) and dedupe.
        new_deps = list(
            dict.fromkeys(
                old_to_new[d] for d in s.depends_on if old_to_new[d] != new_id
            )
        )
        new_detail = s.detail
        if new_id != s.id:
            src = _resolve_detail_source(plan_path, plan, s, repo_root)
            if src is not None and src.is_file():
                m = _DETAIL_ID_PREFIX_RE.match(src.name)
                if m:
                    dst = src.with_name(f"{new_id:02d}-{m.group(2)}")
                    if src != dst:
                        detail_renames.append((src, dst))
                        new_detail = _repo_relative(dst, repo_root)
        new_steps.append(
            s.model_copy(
                update={
                    "id": new_id,
                    "depends_on": new_deps,
                    "depends_on_notes": _remap_depends_on_notes(
                        s.depends_on_notes,
                        new_deps,
                        id_map=old_to_new,
                    ),
                    "detail": new_detail,
                }
            )
        )

    renumber = [
        (s.id, old_to_new[s.id]) for s in survivors if s.id != old_to_new[s.id]
    ]

    # 4. Empty-plan guard keys on the *committed* survivors, not the total
    #    count: carving the last committed step while only parked steps remain
    #    leaves a permanently dead plan (no CURRENT promotable, never complete).
    if not any(s.scope is StepScope.COMMITTED for s in new_steps):
        return NarrowPreview(
            carved_ids=carved,
            source_plan_path=plan_path,
            source_frontmatter_hash=source_frontmatter_hash,
            blockers=[
                NarrowBlocker(
                    kind="empty-plan",
                    step_ids=[],
                    message=(
                        "carving the last committed step leaves no committed "
                        "survivor — the narrowed plan would be permanently dead"
                    ),
                )
            ],
            new_steps=new_steps,
            narrowed_plan=None,
            renumber=renumber,
            new_plan=[(s.id, s.title, list(s.depends_on)) for s in new_steps],
            new_plan_status=plan.status,
        )

    # 5. Re-establish the run cursor — only when dropping the plan's sole
    #    CURRENT step (schema guarantees ≤1 current, so at most one carved step
    #    is CURRENT). Promote the first committed PENDING survivor whose deps
    #    are all DONE (the ``next_runnable_step`` rule), else promote none.
    new_current_id: int | None = None
    if any(cs.status is StepStatus.CURRENT for cs in carved_steps):
        done_ids = {s.id for s in new_steps if s.status is StepStatus.DONE}
        for idx, s in enumerate(new_steps):
            if (
                s.scope is StepScope.COMMITTED
                and s.status is StepStatus.PENDING
                and all(d in done_ids for d in s.depends_on)
            ):
                new_steps[idx] = s.model_copy(
                    update={"status": StepStatus.CURRENT}
                )
                new_current_id = s.id
                break

    # 6. Top-level status: a no-cursor plan whose committed survivors are all
    #    DONE is complete; otherwise preserve the source status.
    has_current = any(s.status is StepStatus.CURRENT for s in new_steps)
    committed_after = [s for s in new_steps if s.scope is StepScope.COMMITTED]
    if not has_current and committed_after and all(
        s.status is StepStatus.DONE for s in committed_after
    ):
        new_plan_status = PlanStatus.COMPLETED
    else:
        new_plan_status = plan.status

    # 7. Prune the features registry — a drop has no survivor to fold a carved
    #    step's solely-owned tags onto, so shed any now-unimplemented entry (the
    #    step→feature ownership invariant: no dangling registry tag).
    surviving_tags = {tag for s in new_steps for tag in s.features}
    new_features = [f for f in plan.features if f.id in surviving_tags]

    # Each carved step's own detail → archive (resolved pointer-first), one
    # entry per carved id that actually has a file on disk.
    archive_details: list[Path] = []
    for cs in carved_steps:
        src = _resolve_detail_source(plan_path, plan, cs, repo_root)
        if src is not None and src.is_file():
            archive_details.append(src)

    try:
        narrowed_plan = Plan.model_validate(
            plan.model_copy(
                update={
                    "steps": new_steps,
                    "status": new_plan_status,
                    "features": new_features,
                }
            ).model_dump(exclude_none=True)
        )
    except PydanticValidationError as exc:
        raise NarrowError(
            f"narrow produced an invalid step graph: {_summarize_step_graph_error(exc)}"
        ) from exc

    return NarrowPreview(
        carved_ids=carved,
        source_plan_path=plan_path,
        source_frontmatter_hash=source_frontmatter_hash,
        blockers=[],
        new_steps=new_steps,
        narrowed_plan=narrowed_plan,
        renumber=renumber,
        new_plan=[(s.id, s.title, list(s.depends_on)) for s in new_steps],
        detail_renames=detail_renames,
        archive_details=archive_details,
        new_current_id=new_current_id,
        new_plan_status=new_plan_status,
    )


def _blocked_preview(
    carved_ids: list[int],
    plan_path: Path,
    source_frontmatter_hash: str,
    status: PlanStatus,
    blockers: list[NarrowBlocker],
) -> NarrowPreview:
    """A preview carrying only blockers — no graph/file preview to apply."""
    return NarrowPreview(
        carved_ids=carved_ids,
        source_plan_path=plan_path,
        source_frontmatter_hash=source_frontmatter_hash,
        blockers=blockers,
        new_steps=[],
        narrowed_plan=None,
        new_plan_status=status,
    )


def _resolve_detail_source(
    plan_path: Path, plan: Plan, step: Step, repo_root: Path
) -> Path | None:
    """Resolve a step's detail file: ``Step.detail`` pointer first (preserving
    noncanonical-but-authoritative paths after slug drift), the canonical
    existing file second. ``None`` when the step was never detailed."""
    resolution = resolve_detail_artifact(plan_path, plan, step, repo_root)
    if resolution.pointer_set:
        return resolution.path  # authoritative even when absent on disk
    return resolution.path if resolution.on_disk else None


def apply_narrow(
    plan_path: Path,
    preview: NarrowPreview,
    *,
    repo_root: Path,
    concept_update: _ConceptNarrowUpdate | None = None,
) -> NarrowResult:
    """Commit ``preview`` all-or-nothing via a reversible journal.

    Refuses (writes nothing) when ``preview.blockers`` is non-empty, when
    ``preview.narrowed_plan is None``, or when the on-disk frontmatter no
    longer matches ``preview.source_frontmatter_hash`` — the hard invariant
    that the graph is never corrupted, independent of step 3's policy gate.
    The all-or-nothing guarantee comes solely from the LIFO journal rollback,
    not from an atomic write (``write_plan``'s ``write_text`` is not atomic).
    """
    plan_path = Path(plan_path)
    if preview.blockers:
        kinds = ", ".join(b.kind for b in preview.blockers)
        raise NarrowError(
            f"refusing to narrow {plan_path.name}: blocker(s) present: {kinds}"
        )
    if preview.narrowed_plan is None:
        raise NarrowError(
            f"refusing to narrow {plan_path.name}: preview has no narrowed plan"
        )
    if compute_frontmatter_hash(plan_path) != preview.source_frontmatter_hash:
        raise NarrowError(
            f"refusing to narrow {plan_path.name}: frontmatter changed since "
            "the preview snapshot (stale preview); re-read the plan and recompute"
        )

    sidecar_path: Path | None = None
    if concept_update is not None:
        from plan_tool.concept_tree import concepts_path
        from plan_tool.review_persistence import compute_plan_fingerprint

        sidecar_path = concepts_path(plan_path)
        try:
            current_sidecar_text = sidecar_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise NarrowError(f"cannot revalidate concept record: {exc}") from exc
        if current_sidecar_text != concept_update.original_sidecar_text:
            raise NarrowError(
                "refusing to narrow: concept record changed since preparation"
            )
        if (
            compute_plan_fingerprint(plan_path)
            != concept_update.prepared_plan_fingerprint
        ):
            raise NarrowError(
                "refusing to narrow: the plan changed since the concept "
                "record was prepared"
            )

    # A carved detail is archived *first* only when its path is also a
    # downstream rename destination, so that expected slot is freed under the
    # same journal before the downstream move needs it; the rest are archived
    # after the renames. Unrelated destination collisions still refuse before
    # any move.
    rename_dests = {dst for _src, dst in preview.detail_renames}
    archive_first = [p for p in preview.archive_details if p in rename_dests]
    archive_after = [p for p in preview.archive_details if p not in rename_dests]

    journal: list[tuple] = []  # (inverse-op-tag, *paths) replayed LIFO
    archived: list[Path] = []
    migrated: list[Path] = []
    original_plan_text = plan_path.read_text(encoding="utf-8")
    try:
        for path in archive_first:
            dest = _archive_file_strict(path)
            journal.append(("restore", dest, path))
            archived.append(dest)

        # Ascending old-id order (the preview is already ascending) so each
        # source frees its destination before the next move needs it.
        for src, dst in preview.detail_renames:
            if dst.exists():
                raise NarrowError(
                    f"refusing to narrow {plan_path.name}: detail destination "
                    f"{dst.name} already exists; will not overwrite it"
                )
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            journal.append(("rename", src, dst))
            migrated.append(dst)

        for path in archive_after:
            dest = _archive_file_strict(path)
            journal.append(("restore", dest, path))
            archived.append(dest)

        # Write the plan last — preserves ``write_plan``'s compare-and-swap
        # provenance (a temp-write + ``os.replace`` would bypass it).
        write_plan(plan_path, preview.narrowed_plan)
        if concept_update is not None:
            from plan_tool.concept_tree import save_concepts
            from plan_tool.review_persistence import compute_plan_fingerprint

            final_tree = copy.deepcopy(concept_update.updated_tree)
            final_tree.plan_fingerprint = compute_plan_fingerprint(plan_path)
            save_concepts(plan_path, final_tree)
    except Exception:
        _rollback(journal)
        # ``write_plan`` and the atomic concept saver are outside the rename
        # journal. Restore both snapshots even when a publisher replaced its
        # target and then raised.
        try:
            plan_path.write_text(original_plan_text, encoding="utf-8")
            refresh_plan_provenance(plan_path, original_plan_text)
        except OSError:
            pass
        if concept_update is not None and sidecar_path is not None:
            try:
                sidecar_path.write_text(
                    concept_update.original_sidecar_text, encoding="utf-8"
                )
            except OSError:
                pass
        raise

    return NarrowResult(
        carved_ids=list(preview.carved_ids),
        renumber=list(preview.renumber),
        new_current_id=preview.new_current_id,
        new_plan_status=preview.new_plan_status,
        archived=archived,
        migrated=migrated,
    )


def _rollback(journal: list[tuple]) -> None:
    """Replay the apply journal LIFO, restoring the pre-narrow file layout.

    Best-effort per inverse op — a single failed undo must not abort the rest
    of the rollback (the original exception is what the caller re-raises)."""
    for entry in reversed(journal):
        tag, a, b = entry
        try:
            if tag == "rename":
                # forward was a→b; undo by moving b back to a.
                b.rename(a)
            elif tag == "restore":
                # forward archived b→a; undo by moving a back to b.
                a.rename(b)
        except OSError:
            continue


def _archive_file_strict(path: Path) -> Path:
    """Move ``path`` into a sibling ``archive/`` with a UTC-timestamp suffix,
    verifying the move succeeded. Strict (unlike detail's best-effort archive):
    any failure raises so the apply journal rolls back."""
    archive_dir = path.parent / "archive"
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = archive_dir / f"{path.stem}.{ts}.md"
    archive_dir.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        ts_us = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        dest = archive_dir / f"{path.stem}.{ts_us}.md"
    path.rename(dest)
    if not dest.is_file() or path.exists():
        raise NarrowError(f"failed to archive carved detail {path.name}")
    return dest


# --------------------------------------------------------------------------
# The orchestrator: seed-first apply-or-recommend gate (policy half).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ScopeOutResult:
    """Disposition of one :func:`scope_out_step` call — the carve's
    ``EscalateResult`` analog (see :class:`launcher.EscalateResult`).

    ``outcome`` is exactly one of five strings:
      - ``"applied"`` — the forward-seed was written and the plan narrowed;
        ``seed_path`` and ``narrow`` are populated.
      - ``"recommended"`` — safe but not actuated (``allow_scope_out=False``,
        a declined/non-TTY confirm); ``preview`` shows the would-be carve, no
        seed/narrow.
      - ``"unsafe"`` — a graph blocker (``non-canonical-numbering`` /
        ``inbound-dependent`` / ``downstream-orphan``) refused the carve.
      - ``"empty-plan"`` — carving the last committed step.
      - ``"step-missing"`` — ``carved_id`` is not in the plan.

    A post-seed :func:`apply_narrow` failure is an **exception path**, not a
    sixth outcome: it propagates, no ``ScopeOutResult`` is returned, and the
    already-written seed stays on disk as a durable orphan artifact.

    ``carved_ids`` holds the full carved region (a single-step carve is
    ``[N]``); ``carved_id`` is the region's first (N) id, kept scalar for the
    ``convergence_cmd`` caller and the recommend-hint.
    """

    outcome: str
    carved_id: int
    carved_ids: list[int] = field(default_factory=list)
    seed_path: Optional[Path] = None
    narrow: Optional[NarrowResult] = None
    preview: Optional[NarrowPreview] = None
    blockers: list[NarrowBlocker] = field(default_factory=list)
    body_sweep_hits: list[BodySweepHit] = field(default_factory=list)


def _outcome_for_blockers(blockers: list[NarrowBlocker]) -> str:
    """Map a blocked preview's ``NarrowBlocker.kind`` values to the result
    ``outcome``, most-fundamental first: ``step-missing`` → ``"step-missing"``,
    else ``empty-plan`` → ``"empty-plan"``, else any graph blocker → ``"unsafe"``."""
    kinds = {b.kind for b in blockers}
    if "step-missing" in kinds:
        return "step-missing"
    if "empty-plan" in kinds:
        return "empty-plan"
    return "unsafe"


def scope_out_step(
    plan_path: Path,
    *,
    carved_id: int | None = None,
    carved_ids: Sequence[int] | None = None,
    repo_root: Path,
    allow_scope_out: bool,
    yes: bool = False,
    prompt_fn: Optional[Callable[[str], str]] = None,
) -> ScopeOutResult:
    """Apply-or-recommend the scope-out (carve) of one over-packed step or a
    contiguous/ordered *region* of steps.

    Accepts either the back-compat scalar ``carved_id=N`` (the
    ``convergence_cmd`` caller's contract) or the canonical ordered set
    ``carved_ids=[...]`` (exactly one); both normalize to a sorted,
    de-duplicated id list, so a single-step carve is the special case of a
    region carve. Contiguity is a CLI concern — the narrow accepts any subset —
    so this layer never validates the range.

    The second instance of the apply-or-recommend gate shape (the first is
    :func:`launcher.escalate_to_split`): re-parse from disk → blocker gate →
    opt-in gate → confirm gate → seed-first apply. The one structural
    contrast with ``escalate_to_split`` is that scope-out spends **zero
    Claude** — both halves (:func:`render_carved_seed` /
    :func:`render_carved_region_seed` and
    :func:`compute_narrow`/:func:`apply_narrow`) are fully deterministic, so
    there is no ``invoker=`` seam to override.

    On a safe, opted-in, confirmed carve **one** forward-seed covering the
    whole region is written to disk **first**, then the plan is narrowed —
    seed-first so the durable re-plannable artifact survives even if the narrow
    is rolled back. A post-seed :func:`apply_narrow` exception propagates
    outside the returned ``ScopeOutResult`` outcomes (see :class:`ScopeOutResult`).
    A pre-seed ``DetailFormatError`` likewise refuses a selected detail this
    build cannot interpret instead of becoming a structured carve outcome.

    ``allow_scope_out`` is the programmatic opt-in (the ``allow_split``
    analog): ``False`` → ``recommended`` with no prompt and no mutation.
    ``yes`` bypasses the interactive confirm; ``prompt_fn`` defaults to
    :func:`input` so tests inject a stub. A non-TTY caller without ``yes``
    auto-declines to ``recommended``.
    """
    plan_path = Path(plan_path)
    _reject_unmatched_plan_fence(plan_path)
    # Fold the back-compat scalar and the ordered-set entry points into one
    # sorted, de-duplicated id list (mirrors ``compute_narrow``'s normalize).
    carved = _normalize_carved_ids(carved_id, carved_ids)
    # Re-parse from disk and hash the same snapshot — never trust an in-memory
    # Plan the caller passed (mirrors ``escalate_to_split``).
    plan = parse_plan(plan_path)
    source_frontmatter_hash = compute_frontmatter_hash(plan_path)

    preview = compute_narrow(
        plan,
        carved_ids=carved,
        plan_path=plan_path,
        repo_root=repo_root,
        source_frontmatter_hash=source_frontmatter_hash,
    )

    # Blocker gate — deterministic refusal that holds regardless of opt-in/yes.
    if preview.blockers:
        return ScopeOutResult(
            outcome=_outcome_for_blockers(preview.blockers),
            carved_id=carved[0],
            carved_ids=carved,
            blockers=preview.blockers,
            preview=preview,
        )

    carved_steps = [plan.step_by_id(c) for c in carved]

    # Opt-in gate.
    if not allow_scope_out:
        return ScopeOutResult(
            outcome="recommended",
            carved_id=carved[0],
            carved_ids=carved,
            preview=preview,
        )

    # Confirm gate. ``schema.Plan`` has no ``slug`` field, so derive it from
    # the filename (mirrors completeness_report / convergence_diagnosis).
    plan_slug = locator.slug_from_filename(plan_path)
    if not _confirm_scope_out(
        prompt_fn, plan_slug=plan_slug, carved_ids=carved, yes=yes
    ):
        return ScopeOutResult(
            outcome="recommended",
            carved_id=carved[0],
            carved_ids=carved,
            preview=preview,
        )

    _reject_unmatched_plan_fence(plan_path)

    # Apply branch — seed-first, then narrow. One seed covers the whole region;
    # its upstream context spans every carved step and excludes in-region deps.
    #
    # Concept preparation and the detail-format gates below may refuse before
    # the seed write; other non-mutating paths return a structured outcome.
    concept_update = _prepare_concept_narrow_update(
        plan_path, carved_steps, preview
    )
    source_body = _split_frontmatter(
        plan_path.read_text(encoding="utf-8")
    ).body
    source_references = extract_h2_sections(
        source_body, ignore_fenced_code=True
    ).get("references")

    upstream_context = _resolve_upstream_context(plan, carved_steps, preview)

    if len(carved_steps) == 1:
        carved_step = carved_steps[0]
        detail_path, detail_missing = _resolve_carved_detail_path(
            plan_path, plan, carved_step, repo_root
        )
        detail_body = None
        if detail_path is not None:
            detail_body = detail_path.read_text(encoding="utf-8")
            require_supported_detail_format_version(detail_body, path=detail_path)
        seed = render_carved_seed(
            plan_title=plan.title,
            carved_step=carved_step,
            detail_body=detail_body,
            detail_missing=detail_missing,
            upstream_context=upstream_context,
            source_path=plan_path,
            plan_intent=plan.intent,
            source_references=source_references,
        )
        seed_path = _carved_seed_path(plan_path, carved_step, repo_root)
    else:
        detail_bodies: list[str | None] = []
        detail_missings: list[bool] = []
        for cs in carved_steps:
            dp, dm = _resolve_carved_detail_path(plan_path, plan, cs, repo_root)
            body = None
            if dp is not None:
                body = dp.read_text(encoding="utf-8")
                require_supported_detail_format_version(body, path=dp)
            detail_bodies.append(body)
            detail_missings.append(dm)
        seed = render_carved_region_seed(
            plan_title=plan.title,
            carved_steps=carved_steps,
            detail_bodies=detail_bodies,
            detail_missings=detail_missings,
            upstream_context=upstream_context,
            source_path=plan_path,
            plan_intent=plan.intent,
            source_references=source_references,
        )
        seed_path = _carved_region_seed_path(plan_path, carved_steps, repo_root)

    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text(seed, encoding="utf-8")

    # apply_narrow's only raise here is a mid-apply IO error (the blocker/stale
    # checks already passed); it rolls the plan back and re-raises. Let that
    # propagate — no ScopeOutResult, seed stays as a harmless durable artifact.
    narrow = apply_narrow(
        plan_path,
        preview,
        repo_root=repo_root,
        concept_update=concept_update,
    )
    # Frontmatter narrow leaves the prose body untouched — surface leftover
    # carved/shifted references so silence isn't the operator's only signal.
    body = _split_frontmatter(
        plan_path.read_text(encoding="utf-8")
    ).body
    body_hits = find_scope_out_body_hits(
        body,
        carved_ids=carved,
        carved_titles=[s.title for s in carved_steps],
        renumber=narrow.renumber,
    )
    return ScopeOutResult(
        outcome="applied",
        carved_id=carved[0],
        carved_ids=carved,
        seed_path=seed_path,
        narrow=narrow,
        preview=preview,
        body_sweep_hits=body_hits,
    )


def _resolve_upstream_context(
    plan: Plan, carved_steps: Sequence[Step], preview: NarrowPreview
) -> list[tuple[int, str, str, str | None]]:
    """Resolve the carved region's external ``depends_on`` to post-narrow
    ``(id, title, status_value, note)`` tuples for the seed renderers.

    Gathers the deps of **every** carved step, drops any dep that points at
    another carved id (an in-region edge is re-planned together, not an
    external prerequisite), de-duplicates, and maps each surviving dep through
    ``preview.renumber`` (defaulting unchanged ids to themselves) so a
    prerequisite whose id shifts during the drop is reported by its post-narrow
    id. A dependency on a later survivor is permitted (``schema.Plan`` allows
    any non-self edge), so do not assume dep ids are lower than a carved step.
    Missing ids are skipped defensively — ``compute_narrow`` already validated
    graph shape."""
    old_to_new = {old: new for old, new in preview.renumber}
    carved_set = {s.id for s in carved_steps}
    seen: set[int] = set()
    out: list[tuple[int, str, str, str | None]] = []
    for carved_step in carved_steps:
        for dep_id in carved_step.depends_on:
            if dep_id in carved_set or dep_id in seen:
                continue
            try:
                dep = plan.step_by_id(dep_id)
            except KeyError:
                continue
            seen.add(dep_id)
            new_id = old_to_new.get(dep_id, dep_id)
            note = carved_step.depends_on_notes.get(dep_id)
            out.append((new_id, dep.title, dep.status.value, note))
    return out


def _resolve_carved_detail_path(
    plan_path: Path, plan: Plan, carved_step: Step, repo_root: Path
) -> tuple[Path | None, bool]:
    """Resolve the carved step's detail file + a ``detail_missing`` flag.

    Resolves identically to ``compute_narrow``'s ``_resolve_detail_source``
    (pointer first, canonical fallback second) so the body the seed captures
    and the file the narrow archives are the **same** file — but also carries
    the missing flag ``archive_details`` alone cannot (an absent entry covers
    both never-detailed and set-but-missing). Three cases:

    - pointer set **and** its file exists → ``(that path, False)``.
    - pointer set **but** its file is absent (moved/deleted/slug-drifted) →
      ``(None, True)``: a lost body, **not** a refusal and **not** an
      apply-failure. No canonical fallback — a set pointer is authoritative.
    - pointer unset → the canonical file when it exists ``(canonical, False)``,
      else ``(None, False)``: the never-detailed step.
    """
    resolution = resolve_detail_artifact(plan_path, plan, carved_step, repo_root)
    if resolution.on_disk:
        return resolution.path, False
    # Absent on disk: a set pointer is a lost body; unset is never-detailed.
    return None, resolution.pointer_set


def _carved_seed_path(plan_path: Path, carved_step: Step, repo_root: Path) -> Path:
    """Derive a collision-safe ``plan-seeds/<plan-slug>-carved-<step-slug>.md``
    path under ``repo_root``.

    ``<plan-slug>`` comes from the filename (``schema.Plan`` has no ``slug``);
    ``<step-slug>`` from ``create.slugify`` over the carved title (lazy import
    to dodge the import cycle, mirroring ``escalate_to_split``), falling back
    to ``step-<id>`` when slugify yields ``""``. **Never overwrites** an
    existing seed — a prior carve's seed is a durable artifact — so a taken
    base path gets a ``-2``, ``-3``, … suffix until a free path is found."""
    from plan_tool.create import slugify

    plan_slug = locator.slug_from_filename(plan_path)
    step_slug = slugify(carved_step.title) or f"step-{carved_step.id}"
    seeds_dir = repo_root / "plan-seeds"
    base = seeds_dir / f"{plan_slug}-carved-{step_slug}.md"
    candidate = base
    n = 2
    while candidate.exists():
        candidate = seeds_dir / f"{plan_slug}-carved-{step_slug}-{n}.md"
        n += 1
    return candidate


def _carved_region_seed_path(
    plan_path: Path, carved_steps: Sequence[Step], repo_root: Path
) -> Path:
    """Derive a collision-safe region seed path
    ``plan-seeds/<plan-slug>-carved-<first-step-slug>-through-<M>.md``.

    Names the seed after the ``N..M`` range (first carved step's slug + last
    carved id) so a region seed is distinguishable from a single-step carve and
    from a sibling region, still under the ``<plan-slug>-carved-*`` glob the
    convergence caller watches. **Never overwrites** — a taken base path gets a
    ``-2``, ``-3``, … suffix, exactly like :func:`_carved_seed_path`."""
    from plan_tool.create import slugify

    plan_slug = locator.slug_from_filename(plan_path)
    first = carved_steps[0]
    first_slug = slugify(first.title) or f"step-{first.id}"
    last_id = carved_steps[-1].id
    seeds_dir = repo_root / "plan-seeds"
    base = seeds_dir / f"{plan_slug}-carved-{first_slug}-through-{last_id}.md"
    candidate = base
    n = 2
    while candidate.exists():
        candidate = (
            seeds_dir
            / f"{plan_slug}-carved-{first_slug}-through-{last_id}-{n}.md"
        )
        n += 1
    return candidate


def _carve_target_label(carved_ids: Sequence[int]) -> str:
    """Human label for a carve target: ``step N`` for one id, ``steps N..M``
    for a region (first..last of the sorted set)."""
    ids = list(carved_ids)
    if len(ids) > 1:
        return f"steps {ids[0]}..{ids[-1]}"
    return f"step {ids[0]}"


def _confirm_scope_out(
    prompt_fn: Optional[Callable[[str], str]],
    *,
    plan_slug: str,
    carved_ids: Sequence[int],
    yes: bool,
) -> bool:
    """Interactive carve confirm — the repo's destructive-verb idiom (mirrors
    ``cli/manifest.py:_prompt_remove_missing``).

    ``yes`` → no prompt. A non-TTY run without ``yes`` prints a ``-y`` hint and
    declines, so an unattended caller never silently mutates a plan. On a TTY,
    prompt ``[y/N]`` and return ``True`` only on ``y``/``yes``; an EOF/interrupt
    cancels. A shared confirm helper is a standing reconcile item, not minted
    here (``manifest``/``detail._confirm_split`` each have their own)."""
    label = _carve_target_label(carved_ids)
    if yes:
        return True
    if not sys.stdin.isatty():
        print(
            f"  scope-out of {label} from {plan_slug} needs confirmation; "
            "re-run with -y to carve unattended.",
            file=sys.stderr,
        )
        return False
    confirm_fn = prompt_fn if prompt_fn is not None else input
    try:
        answer = (
            confirm_fn(f"Carve {label} out of {plan_slug}? [y/N]: ")
            .strip()
            .lower()
        )
    except (EOFError, KeyboardInterrupt):
        print("\n  cancelled — plan left unchanged.", file=sys.stderr)
        return False
    return answer in ("y", "yes")
