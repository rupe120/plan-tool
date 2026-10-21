"""``--view html``: the four roadmap artifacts as one self-contained page.

A **content** projection, deliberately distinct from the five text views in
:mod:`plan_tool.roadmap_view`. Those answer *what state is the roadmap in*
(counts, decisions, citers, seed lifecycle) and each shows a slice of the
rows; this one renders every parsed row of all four artifacts, in artifact
order, with each resolvable forward reference linking to the row it names
and each dangling or ambiguous one visibly marked instead. It is what a
reviewer reads when the question is "what does this roadmap actually say".

The domain section opens with an ER-style picture of its entities, drawn by
:mod:`plan_tool.roadmap_er`. Resolution stays here — which reference names a
drawn entity, and how an unresolved one reads — so the diagram and the table
under it can never disagree about one field; the geometry is entirely that
module's.

Three deliberate carve-outs, so the boundary stays legible:

* **No reverse ("cited by") index.** ``--view index`` owns that projection;
  duplicating it here would give the same derived fact two renderers to
  drift apart. Forward references link, and the browser goes back.
* **No seed lifecycle.** ``--view seeds`` owns it. A plan's own
  ``draft_seed_path`` is artifact content and does render, as written; its
  freshness on disk does not.
* **Prose bodies render verbatim, inside ``<pre>``.** No markdown is
  interpreted. A half-parser would silently mangle a table or fenced block
  in a body written for a markdown reader, and the escaped-verbatim form
  cannot.

Output is a pure function of ``loaded`` — no timestamp, no host, no path —
so two renders of the same artifacts are byte-identical and the file diffs
cleanly.

A leaf: imports :mod:`plan_tool.roadmap_artifacts`,
:mod:`plan_tool.roadmap_er`, and :mod:`plan_tool.roadmap_view` and nothing
else first-party. ``roadmap_view`` never imports this module, and
``roadmap_er`` imports nothing first-party at all, which is what keeps both
edges one-way. See ``docs/ARCHITECTURE.md``.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence, Union

from plan_tool.roadmap_artifacts import (
    COMPONENTS_FILENAME,
    CONSTRAINTS_FILENAME,
    ComponentsArtifact,
    ConstraintsArtifact,
    DOMAIN_FILENAME,
    DecisionRow,
    DecisionStatus,
    DomainArtifact,
    FeedbackRow,
    FieldType,
    PLANS_FILENAME,
    PatternRow,
    PlanRow,
    PlansArtifact,
    RemovalRecord,
    roadmap_dir,
)
from plan_tool.roadmap_er import (
    DiagramEntity,
    DiagramField,
    ER_STYLE,
    render_entity_diagram,
)
from plan_tool.roadmap_view import (
    KIND_ENTITY,
    LoadedRoadmap,
    MODE_REVIEW,
    RESOLUTION_AMBIGUOUS,
    RESOLUTION_DANGLING,
    RESOLUTION_RESOLVED,
    Resolution,
    display_label,
    resolve_feedback_target,
    resolve_id,
    resolve_id_of_kind,
)

# Default, regenerated HTML output beside the staged artifacts.
REVIEW_FILENAME = "review.html"


def review_path(plans_dir: Path, slug: str) -> Path:
    """Return the default ``--view html`` output path."""
    return roadmap_dir(plans_dir, slug) / REVIEW_FILENAME

# One section per artifact. The table itself lives below the renderers it
# names; these are the anchors the nav targets.
SECTION_DOMAIN = "domain"
SECTION_CONSTRAINTS = "constraints"
SECTION_COMPONENTS = "components"
SECTION_PLANS = "plans"

# The four artifact types share no base class, so the union is written out.
# Named once here rather than repeated at each helper that takes "whichever
# artifact this section is".
_Artifact = Union[
    DomainArtifact, ConstraintsArtifact, ComponentsArtifact, PlansArtifact
]

# Every expandable block names its concept. Artifact accents identify the
# surrounding document; these accents let the reader scan its concepts.
_CONCEPT_ACCENTS = (
    "entity",
    "rule",
    "workflow",
    "hosting",
    "disposition",
    "constraint",
    "system-pattern",
    "component-pattern",
    "store",
    "component",
    "plan",
    "assumption",
    "decision",
    "feedback",
    "removal",
    "prose",
)

_ANCHOR_SAFE = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)


def _e(value: object) -> str:
    """Escape any value for HTML text or a quoted attribute."""
    return html.escape(str(value), quote=True)


def anchor_for(row_id: str) -> str:
    """The fragment id one row id gets, injectively.

    Every character outside the HTML-id-safe set becomes ``.`` plus its
    codepoint in **exactly six** hex digits, so two distinct row ids can
    never collide on one anchor the way a lossy slugifier's would — an id
    space the gates only require to be non-empty and unique makes that a
    real case, not a theoretical one.

    The width is load-bearing, not cosmetic: hex digits are themselves
    anchor-safe, so a variable-width escape has no boundary and
    ``"\\xab" + "cd"`` and ``"\\uabcd"`` both encode to ``.abcd``. Six digits
    cover the whole codepoint range (max ``0x10FFFF``) and make every escape
    self-delimiting.
    """
    return "row-" + "".join(
        char if char in _ANCHOR_SAFE else f".{ord(char):06x}" for char in row_id
    )


# --------------------------------------------------------------------------
# Cross-references
# --------------------------------------------------------------------------


def _marker(resolution: Resolution, *, prefix: str = "") -> str:
    """One unresolved reference, from an already-computed ``Resolution`` —
    so wording never drifts from ``roadmap_view``'s, and an ambiguous id's
    competing ``matches`` are never dropped, just shown.

    Warns only for :data:`RESOLUTION_DANGLING` / :data:`RESOLUTION_AMBIGUOUS`;
    every other status (resolved, artifact-scope) is ordinary and renders
    plain. A caller that always wants the warning treatment regardless of
    status (e.g. a duplicate ordering entry) should not route through here.
    """
    text = f"{prefix}{resolution.text}" if prefix else resolution.text
    if resolution.status not in (RESOLUTION_DANGLING, RESOLUTION_AMBIGUOUS):
        return _e(text)
    if not resolution.matches:
        return f'<span class="warn">{_e(text)}</span>'
    items = "".join(f"<li>{_e(match)}</li>" for match in resolution.matches)
    # A block wrapper, not a span: a <ul> is block-level, and a <span>
    # containing one is invalid HTML that a browser silently reflows.
    return f'<div class="warn">{_e(text)}</div><ul class="plain">{items}</ul>'


def _ref_from(row_id: Optional[str], resolution: Resolution) -> str:
    """The rendering half of :func:`_ref`, given a resolution the caller
    already computed — the seam :func:`_feedback_block` uses to avoid a
    third, redundant ``resolve_id`` call on top of its own explicit one and
    :func:`resolve_feedback_target`'s internal one. Those two remaining
    calls compute genuinely different things (one also consults removals),
    so collapsing them further needs a return-contract change to the
    shared ``roadmap_view`` function — out of scope for this seam."""
    if resolution.status != RESOLUTION_RESOLVED:
        return _marker(resolution)
    assert row_id is not None
    return (
        f'<a class="ref" href="#{_e(anchor_for(row_id))}">'
        f"<code>{_e(row_id)}</code> {_e(resolution.text)}</a>"
    )


def _ref(row_id: str, loaded: LoadedRoadmap) -> str:
    """One forward reference: a link when the id resolves, else the same
    marker text the text views print.

    Reuses :func:`resolve_id` rather than re-deciding, so a dangling or
    ambiguous id reads identically here and in ``--view walk``.
    """
    return _ref_from(row_id, resolve_id(row_id, loaded.design_row_index))


def _item_list(items: Sequence[str], render_item, *, css_class: str) -> str:
    """One ``<ul>`` of rendered items, or the explicit empty marker.

    ``(none)`` is written out rather than left blank: an empty cell reads as
    "not recorded" exactly as easily as "recorded as none". Shared by
    :func:`_ref_list` and :func:`_text_list`, which differ only in how one
    item renders and which class the list carries.
    """
    if not items:
        return '<span class="none">(none)</span>'
    rendered = "".join(f"<li>{render_item(item)}</li>" for item in items)
    return f'<ul class="{css_class}">{rendered}</ul>'


def _ref_list(ids: Sequence[str], loaded: LoadedRoadmap) -> str:
    """A reference list cell: each id resolved through :func:`_ref`."""
    return _item_list(ids, lambda row_id: _ref(row_id, loaded), css_class="refs")


def _ref_list_of_kind(
    ids: Sequence[str], loaded: LoadedRoadmap, *, kind: str
) -> str:
    """A reference list whose rows must have one expected ``kind``."""
    return _item_list(
        ids,
        lambda row_id: _ref_from(
            row_id, resolve_id_of_kind(row_id, loaded, kind=kind)
        ),
        css_class="refs",
    )


def _reference_field_resolution(
    field, loaded: LoadedRoadmap
) -> Optional[Resolution]:
    """Resolve one reference field for every domain renderer.

    The gate normally requires ``entity_id`` on every reference field; the
    view layer runs no gates, so a directly edited artifact can violate it. Keep
    that marker beside :func:`resolve_id` so the table and diagram agree.
    """
    if field.type is not FieldType.REFERENCE:
        return None
    if field.entity_id is None:
        return Resolution(
            status=RESOLUTION_DANGLING,
            text=f"⚠ missing entity_id: {field.name}",
        )
    return resolve_id_of_kind(field.entity_id, loaded, kind=KIND_ENTITY)


def _reference_field_suffix(field, resolution: Optional[Resolution]) -> str:
    """The `` → target`` an entity field row's type badge gets when the
    field is a reference."""
    if resolution is None:
        return ""
    return " → " + _ref_from(field.entity_id, resolution)


def _text_list(values: Sequence[str]) -> str:
    """A plain-text list cell: each value escaped, nothing resolved."""
    return _item_list(values, _e, css_class="plain")


def _optional(value: Optional[object]) -> str:
    """A nullable scalar cell: the value, or an explicit not-recorded mark."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return '<span class="none">—</span>'
    if hasattr(value, "value"):  # a closed-vocabulary enum member
        return _e(value.value)
    return _e(value)


# --------------------------------------------------------------------------
# Anchors
# --------------------------------------------------------------------------


class _Anchors:
    """Emits each row id's anchor exactly once per document.

    Nothing enforces row-id uniqueness across artifacts the way the gates
    enforce it within one, so a colliding id would otherwise emit a
    duplicate fragment id. The second occurrence is rendered without an
    anchor: links to that id already resolve to the ambiguity marker rather
    than to either row, so no link is left pointing at nothing.
    """

    def __init__(self) -> None:
        self._emitted: "set[str]" = set()

    def attr(self, row_id: str) -> str:
        if row_id in self._emitted:
            return ""
        self._emitted.add(row_id)
        return f' id="{_e(anchor_for(row_id))}"'


def _id_collision(row_id: str, loaded: LoadedRoadmap) -> Optional[Resolution]:
    """Whether ``row_id`` names more than one row anywhere in the roadmap.

    Nothing enforces id uniqueness *across* artifacts the way the gates
    enforce it within one, so any row kind can collide with any other's id.
    Every reference to a colliding id elsewhere on the page resolves through
    the full ``design_row_index`` and already renders "⚠ ambiguous" for it —
    the id's own defining row needs the same check, or the page
    contradicts itself: one row rendering cleanly while every citation of
    its id says otherwise.
    """
    resolution = resolve_id(row_id, loaded.design_row_index)
    return resolution if resolution.status == RESOLUTION_AMBIGUOUS else None


def _row_id_cell_from_collision(
    row_id: str, collision: Optional[Resolution], anchors: _Anchors
) -> str:
    """One row's own id cell: its anchor, the id itself, and — when the id
    also names a row elsewhere in the roadmap — the same ambiguity marker
    every reference to it already carries.

    The domain section supplies a shared lookup for its diagram and table;
    :func:`_row_id_cell` computes one for every other row kind.
    """
    marker = (
        f'<div class="warn-box">{_marker(collision)}</div>'
        if collision is not None
        else ""
    )
    return (
        f'<td{anchors.attr(row_id)} class="rowid">'
        f"<code>{_e(row_id)}</code>{marker}</td>"
    )


def _row_id_cell(row_id: str, loaded: LoadedRoadmap, anchors: _Anchors) -> str:
    """Render one row's id after checking its global id collision."""
    return _row_id_cell_from_collision(row_id, _id_collision(row_id, loaded), anchors)


# --------------------------------------------------------------------------
# Table and section scaffolding
# --------------------------------------------------------------------------


def _table(headers: Sequence[str], rows: Sequence[str]) -> str:
    """A table, or the empty-collection marker in its place."""
    if not rows:
        return '<p class="none">(none)</p>'
    head = "".join(f"<th>{_e(header)}</th>" for header in headers)
    body = "".join(f"<tr>{row}</tr>" for row in rows)
    return (
        '<div class="scroll"><table>'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _block(title: str, count: Optional[int], content: str, *, accent: str) -> str:
    """One collapsible subsection. ``count`` renders beside the title so a
    collapsed block still reports how much it is hiding."""
    assert accent in _CONCEPT_ACCENTS
    tally = f' <span class="count">{count}</span>' if count is not None else ""
    return (
        f'<details open class="concept concept-{accent}"><summary>{_e(title)}{tally}</summary>'
        f'<div class="block">{content}</div></details>'
    )


def _body_block(body: str) -> str:
    """The artifact's prose, verbatim. See this module's docstring for why
    no markdown is interpreted."""
    if not body.strip():
        return _block("Prose", None, '<p class="none">(empty)</p>', accent="prose")
    return _block("Prose", None, f'<pre class="prose">{_e(body)}</pre>', accent="prose")


# --------------------------------------------------------------------------
# Shared row collections
# --------------------------------------------------------------------------


def _decisions_block(
    decisions: Sequence[DecisionRow], loaded: LoadedRoadmap, anchors: _Anchors
) -> str:
    rows = []
    for decision in decisions:
        settled = decision.status is DecisionStatus.SETTLED
        badge_class = "badge settled" if settled else "badge pending"
        rejected = (
            "".join(
                f"<li><b>{_e(alt.option)}</b> — {_e(alt.reason)}</li>"
                for alt in decision.rejected_alternatives
            )
            or "<li class='none'>(none)</li>"
        )
        rows.append(
            _row_id_cell(decision.id, loaded, anchors)
            + f"<td>{_e(decision.chosen_option)}</td>"
            + f'<td><span class="{badge_class}">{_e(decision.status.value)}</span></td>'
            + f"<td>{_optional(decision.source)}</td>"
            + f"<td>{_ref(decision.anchor, loaded)}</td>"
            + f"<td>{_e(decision.rationale if decision.rationale is not None else '(none)')}</td>"
            + f'<td><ul class="plain">{rejected}</ul></td>'
        )
    return _block(
        "Decisions",
        len(decisions),
        _table(
            ("id", "chosen option", "status", "source", "anchor", "rationale", "rejected"), rows
        ),
        accent="decision",
    )


def _patterns_block(
    title: str,
    patterns: Sequence[PatternRow],
    loaded: LoadedRoadmap,
    anchors: _Anchors,
    *,
    accent: str,
) -> str:
    rows = [
        _row_id_cell(pattern.id, loaded, anchors)
        + f"<td>{_e(pattern.name)}</td><td>{_e(pattern.statement)}</td>"
        for pattern in patterns
    ]
    return _block(
        title, len(patterns), _table(("id", "name", "statement"), rows), accent=accent
    )


def _plain_id_cell(row_id: str) -> str:
    """The bare ``<td class="rowid"><code>…</code></td>`` shell: no anchor,
    no cross-artifact collision check.

    Feedback ids and a removal's ``removed_id`` live in their own
    namespaces (``feedback_index`` / a tombstoned design-row id no longer in
    ``design_row_index``), never joining the live design-row id space the
    way an entity, plan, or decision id does. Unlike :func:`_row_id_cell`,
    this must not claim an anchor slot (a feedback id happening to match a
    design row's id would silently steal that row's fragment) or run
    :func:`_id_collision` against ``design_row_index`` (a comparison across
    two unrelated id spaces).
    """
    return f'<td class="rowid"><code>{_e(row_id)}</code></td>'


def _feedback_block(feedback: Sequence[FeedbackRow], loaded: LoadedRoadmap) -> str:
    """Review-channel feedback. Rendered only under ``--mode review``; the
    caller decides, matching every other view's mode contract."""
    rows = []
    for row in feedback:
        target = resolve_feedback_target(
            row.target, loaded.design_row_index, loaded.removal_index
        )
        # Link only when the id names a *live design row* — resolved here,
        # once, rather than a second time through ``_ref``. (``target``
        # above already resolved the same id once more, via a removals-aware
        # path that ``resolve_id`` alone can't take; the two calls are not
        # redundant with each other.) A target that resolves only through
        # the removal index has no row to link to — ``target``, not
        # ``row_resolution``, carries that deliberately-supported tombstone
        # answer.
        if row.target.row_id is None:
            target_cell = _marker(target)
        else:
            row_resolution = resolve_id(row.target.row_id, loaded.design_row_index)
            target_cell = (
                _ref_from(row.target.row_id, row_resolution)
                if row_resolution.status == RESOLUTION_RESOLVED
                else _marker(target)
            )
        rows.append(
            _plain_id_cell(row.id)
            + f"<td>{_e(row.state.value)}</td>"
            + f"<td>{target_cell}</td>"
            + f"<td>{_e(row.request)}</td>"
            + f"<td>{_optional(row.proposed_response)}</td>"
        )
    return _block(
        "Feedback",
        len(feedback),
        _table(("id", "state", "target", "request", "proposed response"), rows),
        accent="feedback",
    )


def _removals_block(removals: Sequence[RemovalRecord]) -> str:
    rows = [
        _plain_id_cell(record.removed_id)
        + f"<td>{_e(record.rationale)}</td>"
        + f"<td>{_text_list(record.feedback_ids)}</td>"
        for record in removals
    ]
    return _block(
        "Removals",
        len(removals),
        _table(("removed id", "rationale", "feedback"), rows),
        accent="removal",
    )


def _review_blocks(artifact: _Artifact, loaded: LoadedRoadmap) -> str:
    """The two review-channel collections every artifact carries, or nothing
    at all under ``current`` mode.

    Reads both fields directly rather than through ``getattr`` defaults: all
    four artifact types declare them, so a default would only ever mask a
    rename — and mask it by rendering an empty review section, which is
    indistinguishable from a roadmap that genuinely has no feedback.
    """
    if loaded.mode != MODE_REVIEW:
        return ""
    return _feedback_block(artifact.feedback, loaded) + _removals_block(
        artifact.removals
    )


# --------------------------------------------------------------------------
# Per-artifact sections
# --------------------------------------------------------------------------


def _common_tail(artifact: _Artifact, loaded: LoadedRoadmap, anchors: _Anchors) -> str:
    """The three blocks every artifact section ends with, in order:
    decisions, the review channel, and the prose body. Every artifact
    carries all three fields, so this is the one place their sequence is
    stated rather than four."""
    return (
        _decisions_block(artifact.decisions, loaded, anchors)
        + _review_blocks(artifact, loaded)
        + _body_block(artifact.body)
    )


def _diagram_field(
    field, resolution: Optional[Resolution], entity_index: "dict[str, int]"
) -> DiagramField:
    """Render one entity field from its precomputed resolution."""
    if field.type is not FieldType.REFERENCE:
        return DiagramField(name=field.name, detail=field.type.value)
    assert resolution is not None  # reference fields always produce a result
    if resolution.status != RESOLUTION_RESOLVED:
        note = (
            f"Matches: {'; '.join(resolution.matches)}"
            if resolution.matches
            else None
        )
        return DiagramField(
            name=field.name, detail=resolution.text, warn=True, note=note
        )
    assert field.entity_id is not None  # only an id can resolve successfully
    target = entity_index.get(field.entity_id)
    assert target is not None  # resolution rejects targets outside this diagram
    return DiagramField(
        name=field.name, detail=f"→ {resolution.text}", target=target
    )


def _collision_note(collision: Optional[Resolution]) -> Optional[str]:
    """The diagram box's hover note for an ambiguous entity id — the same
    competing rows the table's ``<ul>`` lists, so a reader working from the
    picture alone still sees what the id collides with."""
    if collision is None:
        return None
    if not collision.matches:
        return collision.text
    return f"{collision.text} — Matches: {'; '.join(collision.matches)}"


def _diagram_entities(
    artifact: DomainArtifact,
    entity_index: "dict[str, int]",
    collisions: Sequence[Optional[Resolution]],
    field_resolutions: Sequence[Sequence[Optional[Resolution]]],
) -> "list[DiagramEntity]":
    """Create the resolved entities for the diagram."""
    return [
        DiagramEntity(
            title=entity.name,
            subtitle=entity.id,
            fields=tuple(
                _diagram_field(field, resolution, entity_index)
                for field, resolution in zip(entity.fields, resolutions)
            ),
            href=None if collision is not None else f"#{anchor_for(entity.id)}",
            warn=collision is not None,
            note=_collision_note(collision),
        )
        for entity, collision, resolutions in zip(
            artifact.entities, collisions, field_resolutions
        )
    ]


def _diagram_block(
    artifact: DomainArtifact,
    entity_index: "dict[str, int]",
    collisions: Sequence[Optional[Resolution]],
    field_resolutions: Sequence[Sequence[Optional[Resolution]]],
) -> str:
    """Render the ER-style picture above the domain table."""
    if not artifact.entities:
        return _block(
            "Entity diagram", 0, '<p class="none">(none)</p>', accent="entity"
        )
    caption = (
        "Each box is an entity and each arrow a reference field, from the "
        "field that names an entity to the entity it names. Cardinality and "
        "optionality are deliberately not drawn — the domain artifact records "
        "neither. Business rules and workflows relate entities too, and are "
        "in the tables below rather than here."
    )
    diagram = render_entity_diagram(
        _diagram_entities(artifact, entity_index, collisions, field_resolutions)
    )
    return _block(
        "Entity diagram",
        len(artifact.entities),
        f'<p class="caption">{_e(caption)}</p>'
        f'<div class="scroll er">'
        f"{diagram}</div>",
        accent="entity",
    )


def _domain_section(
    artifact: DomainArtifact, loaded: LoadedRoadmap, anchors: _Anchors
) -> str:
    entity_index = {
        entity.id: position for position, entity in enumerate(artifact.entities)
    }
    entity_collisions = tuple(
        _id_collision(entity.id, loaded) for entity in artifact.entities
    )
    field_resolutions = tuple(
        tuple(
            _reference_field_resolution(field, loaded)
            for field in entity.fields
        )
        for entity in artifact.entities
    )
    entity_rows = []
    for entity, collision, resolutions in zip(
        artifact.entities, entity_collisions, field_resolutions
    ):
        if entity.fields:
            fields = "".join(
                "<li>"
                + f"<b>{_e(field.name)}</b> "
                + f'<span class="type">{_e(field.type.value)}</span>'
                + _reference_field_suffix(field, resolution)
                + "</li>"
                for field, resolution in zip(entity.fields, resolutions)
            )
            fields_cell = f'<ul class="plain">{fields}</ul>'
        else:
            fields_cell = '<span class="none">(none)</span>'
        entity_rows.append(
            _row_id_cell_from_collision(entity.id, collision, anchors)
            + f"<td>{_e(entity.name)}</td><td>{fields_cell}</td>"
        )

    rule_rows = [
        _row_id_cell(rule.id, loaded, anchors)
        + f"<td>{_e(rule.statement)}</td><td>{_ref_list_of_kind(rule.entity_ids, loaded, kind=KIND_ENTITY)}</td>"
        for rule in artifact.business_rules
    ]
    workflow_rows = [
        _row_id_cell(flow.id, loaded, anchors)
        + f"<td>{_e(flow.name)}</td><td>{_ref_list_of_kind(flow.entity_ids, loaded, kind=KIND_ENTITY)}</td>"
        for flow in artifact.workflows
    ]

    return (
        _diagram_block(artifact, entity_index, entity_collisions, field_resolutions)
        + _block(
            "Entities",
            len(artifact.entities),
            _table(("id", "name", "fields"), entity_rows),
            accent="entity",
        )
        + _block(
            "Business rules",
            len(artifact.business_rules),
            _table(("id", "statement", "entities"), rule_rows),
            accent="rule",
        )
        + _block(
            "Workflows",
            len(artifact.workflows),
            _table(("id", "name", "entities"), workflow_rows),
            accent="workflow",
        )
        + _common_tail(artifact, loaded, anchors)
    )


def _constraints_section(
    artifact: ConstraintsArtifact, loaded: LoadedRoadmap, anchors: _Anchors
) -> str:
    hosting_rows = [
        _row_id_cell(row.id, loaded, anchors)
        + f"<td>{_e(row.facet)}</td>"
        + f"<td>{_e(row.value)}</td>"
        + f"<td>{_optional(row.product)}</td>"
        + f"<td>{_optional(row.description)}</td>"
        + f"<td>{_optional(row.research_disclosure)}</td>"
        for row in artifact.hosting
    ]
    disposition_rows = [
        _row_id_cell(row.id, loaded, anchors)
        + f"<td>{_e(row.attribute)}</td>"
        + f'<td><span class="badge disp-{_e(row.disposition.value)}">'
        f"{_e(row.disposition.value)}</span></td>"
        for row in artifact.dispositions
    ]
    constraint_rows = [
        _row_id_cell(row.id, loaded, anchors)
        + f"<td>{_e(row.statement)}</td>"
        + f"<td>{_e(row.attribute)}</td>"
        + f"<td>{_ref_list(row.anchor_ids, loaded)}</td>"
        for row in artifact.constraints
    ]
    stack_rows = [
        _row_id_cell(row.id, loaded, anchors)
        + f"<td>{_e(row.concern)}</td>"
        + f"<td>{_e('open — not decided' if row.open else row.choice or 'no choice')}</td>"
        for row in artifact.stack or ()
    ]

    return (
        _block(
            "Hosting",
            len(artifact.hosting),
            _table(
                ("id", "facet", "value", "product", "description", "disclosure"),
                hosting_rows,
            ),
            accent="hosting",
        )
        + (
            # An unrecorded stack renders no block, so stack-less pages are unchanged.
            _block(
                "Stack",
                len(artifact.stack),
                _table(("id", "concern", "choice"), stack_rows),
                accent="hosting",
            )
            if artifact.stack is not None
            else ""
        )
        + _block(
            "Quality-attribute dispositions",
            len(artifact.dispositions),
            _table(("id", "attribute", "disposition"), disposition_rows),
            accent="disposition",
        )
        + _block(
            "Constraints",
            len(artifact.constraints),
            _table(("id", "statement", "attribute", "anchors"), constraint_rows),
            accent="constraint",
        )
        + _common_tail(artifact, loaded, anchors)
    )


def _components_section(
    artifact: ComponentsArtifact, loaded: LoadedRoadmap, anchors: _Anchors
) -> str:
    store_rows = [
        _row_id_cell(row.id, loaded, anchors)
        + f"<td>{_e(row.category)}</td>"
        + f"<td>{_e(row.sharing)}</td>"
        + f"<td>{_optional(row.product)}</td>"
        + f"<td>{_optional(row.description)}</td>"
        + f"<td>{_optional(row.research_disclosure)}</td>"
        for row in artifact.stores
    ]
    component_rows = [
        _row_id_cell(component.id, loaded, anchors)
        + f"<td>{_e(component.name)}</td>"
        + f"<td>{_ref_list_of_kind(component.entity_ids, loaded, kind=KIND_ENTITY)}</td>"
        + f"<td>{_ref_list(component.pattern_ids, loaded)}</td>"
        + f"<td>{_ref_list(component.constraint_ids, loaded)}</td>"
        + f"<td>{_ref_list(component.store_ids, loaded)}</td>"
        for component in artifact.components
    ]

    return (
        _patterns_block(
            "System patterns",
            artifact.system_patterns,
            loaded,
            anchors,
            accent="system-pattern",
        )
        + _patterns_block(
            "Component patterns",
            artifact.component_patterns,
            loaded,
            anchors,
            accent="component-pattern",
        )
        + _block(
            "Stores",
            len(artifact.stores),
            _table(
                ("id", "category", "sharing", "product", "description", "disclosure"),
                store_rows,
            ),
            accent="store",
        )
        + _block(
            "Components",
            len(artifact.components),
            _table(
                ("id", "name", "entities", "patterns", "constraints", "stores"),
                component_rows,
            ),
            accent="component",
        )
        + _common_tail(artifact, loaded, anchors)
    )


def _plan_card(
    plan: PlanRow,
    ordering,
    loaded: LoadedRoadmap,
    anchors: _Anchors,
    *,
    note: Optional[str] = None,
    id_collision: Optional[Resolution] = None,
) -> str:
    """One plan, with the ordering entry that placed it (``None`` when the
    plan row is absent from ``ordering``)."""
    fields = [
        ("intent", _optional(plan.intent)),
        ("delivery shape", _e(plan.disposition.value)),
        ("non-goals", _text_list(plan.non_goals)),
        ("components", _ref_list(plan.component_ids, loaded)),
        ("sizing rationale", _optional(plan.sizing_rationale)),
        ("draft seed", f"<code>{_e(plan.draft_seed_path)}</code>"),
        (
            "depends on",
            _ref_list(ordering.depends_on, loaded)
            if ordering is not None
            else '<span class="none">(not in ordering)</span>',
        ),
        (
            "assumption targets",
            _ref_list(ordering.assumption_targets, loaded)
            if ordering is not None
            else '<span class="none">(not in ordering)</span>',
        ),
    ]
    rows = "".join(f"<tr><th>{_e(label)}</th><td>{value}</td></tr>" for label, value in fields)
    warnings = []
    if note is not None:
        warnings.append(f'<div class="warn-box">{_e(note)}</div>')
    if id_collision is not None:
        warnings.append(f'<div class="warn-box">{_marker(id_collision)}</div>')
    warning = "".join(warnings)
    return (
        f'<article class="card"{anchors.attr(plan.id)}>'
        f'<h4><code>{_e(plan.id)}</code> {_e(plan.title)}</h4>'
        f"{warning}"
        f'<div class="scroll"><table class="kv"><tbody>{rows}</tbody></table></div>'
        "</article>"
    )


def _plans_block(artifact: PlansArtifact, loaded: LoadedRoadmap, anchors: _Anchors) -> str:
    """Plans in ``ordering`` sequence, carrying the same annotations
    ``render_traceability_walk`` renders for the same malformations — a
    dangling ordering entry, a repeated one (including a repeat of an id
    that resolves to a non-plan row), a plan row the ordering never names,
    and an id that resolves to a non-plan design row. The two views render
    identical wording for all of these; see ``BACKLOG.md`` #323 for sharing
    this rendering outright rather than keeping it duplicated per view.
    """
    groups: "dict[str, list[PlanRow]]" = {}
    for plan in artifact.plans:
        groups.setdefault(plan.id, []).append(plan)

    def render_group(matches: "list[PlanRow]", ordering, *, note=None) -> "list[str]":
        """Every ``PlanRow`` sharing one id, each carrying the same
        collision marker — a single element when the id is locally unique,
        more when it isn't.

        Nothing enforces plan-id uniqueness at this layer (see this
        function's docstring): more than one ``PlanRow`` can share an id.
        Rendering only a warning box for the collision would silently drop
        every colliding plan's full content — title, intent, non-goals,
        components — contradicting this view's own contract that every
        parsed row renders. Which one an ``ordering`` entry "really"
        describes is exactly the thing that's ambiguous, so every match
        shows the same ordering context.
        """
        collision = _id_collision(matches[0].id, loaded)
        return [
            _plan_card(plan, ordering, loaded, anchors, note=note, id_collision=collision)
            for plan in matches
        ]

    cards: "list[str]" = []
    rendered: "set[str]" = set()
    for entry in artifact.ordering:
        matches = groups.get(entry.plan_id, [])
        if entry.plan_id in rendered:
            # A repeated malformed id still gets its own diagnostic, not
            # just a generic "repeated" label with nothing said about what
            # is actually wrong with it — repeating the check costs nothing
            # since neither occurrence produces a card.
            if not matches:
                resolution = resolve_id(entry.plan_id, loaded.design_row_index)
                cards.append(
                    f'<div class="warn-box">{_marker(resolution, prefix="repeated, ")}</div>'
                    if resolution.status != RESOLUTION_RESOLVED
                    else f'<div class="warn-box">⚠ ordering entry does not name a '
                    f"plan (repeated): {_e(resolution.text)}</div>"
                )
                continue
            # The walk labels a repeat by the plan it names, falling back to
            # the bare id only when the id is itself ambiguous.
            label = display_label(matches[0]) if len(matches) == 1 else entry.plan_id
            cards.append(
                f'<div class="warn-box">⚠ duplicate ordering entry: {_e(label)}</div>'
            )
            continue
        rendered.add(entry.plan_id)
        if not matches:
            resolution = resolve_id(entry.plan_id, loaded.design_row_index)
            if resolution.status == RESOLUTION_RESOLVED:
                # The id exists, but not as a plan row's id — an ordering
                # entry naming an entity/decision/assumption id it was never
                # meant to hold (ordering entries mint no ids of their own).
                # Distinct from a genuinely dangling id: say what went wrong
                # rather than printing the other row's label with nothing to
                # explain why it showed up in a warning box.
                cards.append(
                    f'<div class="warn-box">⚠ ordering entry does not name a '
                    f"plan: {_e(resolution.text)}</div>"
                )
            else:
                cards.append(f'<div class="warn-box">{_marker(resolution)}</div>')
            continue
        cards.extend(render_group(matches, entry))

    for plan_id, matches in groups.items():
        if plan_id in rendered:
            continue
        cards.extend(render_group(matches, None, note="⚠ not in ordering"))

    return _block(
        "Plans",
        len(artifact.plans),
        "".join(cards) if cards else '<p class="none">(none)</p>',
        accent="plan",
    )


def _roadmap_section(
    artifact: PlansArtifact, loaded: LoadedRoadmap, anchors: _Anchors
) -> str:
    assumption_rows = [
        _row_id_cell(row.id, loaded, anchors)
        + f"<td>{_e(row.statement)}</td>"
        + f"<td>{_ref_list(row.consuming_plan_ids, loaded)}</td>"
        for row in artifact.assumptions
    ]
    return (
        _plans_block(artifact, loaded, anchors)
        + _block(
            "Assumptions",
            len(artifact.assumptions),
            _table(("id", "statement", "consuming plans"), assumption_rows),
            accent="assumption",
        )
        + _common_tail(artifact, loaded, anchors)
    )


# --------------------------------------------------------------------------
# Document
# --------------------------------------------------------------------------


def _artifact_status(loaded: LoadedRoadmap) -> str:
    """Absent and unparseable artifacts, named. Silence would leave a reader
    to infer an empty section from a missing one."""
    parts = []
    if loaded.absent:
        parts.append(f"absent: {_e(', '.join(loaded.absent))}")
    if loaded.unparseable:
        parts.append(
            "unparseable: "
            + _e(
                "; ".join(
                    f"{item.filename} ({item.reason})" for item in loaded.unparseable
                )
            )
        )
    if not parts:
        return ""
    return f'<p class="notice">artifact status — {" · ".join(parts)}</p>'


@dataclass(frozen=True)
class _Section:
    """One artifact's row in the page: where it anchors, what it is called,
    which file it came from, how to reach it on a
    :class:`~plan_tool.roadmap_view.LoadedRoadmap`, and what renders it.

    Carrying the accessor and renderer here rather than in parallel lookups
    keeps the section list to one encoding: adding a fifth artifact is one
    row, and cannot half-land as a section that renders the wrong type.
    """

    anchor: str
    title: str
    filename: str
    attribute: str
    render: "Callable[[object, LoadedRoadmap, _Anchors], str]"


_SECTIONS = (
    _Section(
        SECTION_DOMAIN, "01 · Domain", DOMAIN_FILENAME, "domain", _domain_section
    ),
    _Section(
        SECTION_CONSTRAINTS,
        "02 · Constraints",
        CONSTRAINTS_FILENAME,
        "constraints",
        _constraints_section,
    ),
    _Section(
        SECTION_COMPONENTS,
        "03 · Components",
        COMPONENTS_FILENAME,
        "components",
        _components_section,
    ),
    _Section(
        SECTION_PLANS, "04 · Roadmap", PLANS_FILENAME, "plans", _roadmap_section
    ),
)


def _accent_scope_rules() -> str:
    """Generate section and nav accent selectors from :data:`_SECTIONS`.

    Hues remain explicit in :data:`_STYLE` so a new family chooses its palette.
    """
    scoped = "".join(
        f"#{s.anchor}{{--acc:var(--acc-{s.anchor});--acc-bg:var(--acc-{s.anchor}-bg);"
        f"--artifact-acc:var(--acc-{s.anchor})}}\n"
        for s in _SECTIONS
    )
    nav = "".join(
        f'nav a[href="#{s.anchor}"]{{--acc:var(--acc-{s.anchor})}}\n' for s in _SECTIONS
    )
    return scoped + nav


def _concept_accent_scope_rules() -> str:
    """Generate block accent selectors from :data:`_CONCEPT_ACCENTS`."""
    return "".join(
        f"details.concept-{accent}{{--acc:var(--concept-{accent});"
        f"--acc-bg:var(--concept-{accent}-bg)}}\n"
        for accent in _CONCEPT_ACCENTS
    )


def _section_body(
    loaded: LoadedRoadmap, section: _Section, anchors: _Anchors
) -> str:
    """One artifact's rendered rows, or why there are none."""
    artifact = getattr(loaded, section.attribute)
    if artifact is None:
        reason = next(
            (
                item.reason
                for item in loaded.unparseable
                if item.filename == section.filename
            ),
            None,
        )
        text = (
            f"not parsed — {reason}" if reason is not None else "not present on disk"
        )
        return f'<p class="none">{_e(text)}</p>'
    return section.render(artifact, loaded, anchors)


def render_roadmap_html(loaded: LoadedRoadmap) -> str:
    """Render the whole roadmap as one standalone HTML document.

    Self-contained by construction: the stylesheet is inlined and the page
    loads no script, font, or image, so it opens from a file:// path with no
    network. Deterministic: same artifacts in, same bytes out.
    """
    anchors = _Anchors()
    nav = "".join(
        f'<a href="#{_e(section.anchor)}">{_e(section.title)}</a>'
        for section in _SECTIONS
    )
    sections = "".join(
        f'<section id="{_e(section.anchor)}"><h2>{_e(section.title)} '
        f'<span class="file">{_e(section.filename)}</span></h2>'
        f'<div class="artifact-content">'
        f"{_section_body(loaded, section, anchors)}</div></section>"
        for section in _SECTIONS
    )
    readable = len(_SECTIONS) - len(loaded.absent) - len(loaded.unparseable)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>Roadmap · {_e(loaded.slug)}</title>\n"
        f"<style>{_STYLE}</style>\n</head>\n<body>\n"
        f"<header><h1>Roadmap · {_e(loaded.slug)}</h1>"
        f'<p class="meta">mode: {_e(loaded.mode)} · '
        f"{readable}/{len(_SECTIONS)} artifacts readable</p>"
        f"{_artifact_status(loaded)}"
        f"</header>\n"
        # Keep the sticky nav outside the scrolling header.
        f"<nav>{nav}</nav>\n<main>{sections}</main>\n</body>\n</html>\n"
    )


_STYLE = """
:root{--bg:#fbfbfa;--fg:#1c1c1a;--muted:#6b6b66;--line:#e2e1dc;--card:#fff;
--accent:#2f5d8c;--warn:#a4531b;--warn-bg:#fdf3e8;--ok:#2c6e49;--pend:#8a6d1f;
--code:#f2f1ec;
--acc-domain:#6d28d9;--acc-domain-bg:#f3effc;
--acc-constraints:#0e7490;--acc-constraints-bg:#e8f6f8;
--acc-components:#be185d;--acc-components-bg:#fbeaf1;
--acc-plans:#991b1b;--acc-plans-bg:#fbeaea;
--concept-entity:#1d4ed8;--concept-entity-bg:#eff6ff;
--concept-rule:#7e22ce;--concept-rule-bg:#faf5ff;
--concept-workflow:#c2410c;--concept-workflow-bg:#fff7ed;
--concept-hosting:#0369a1;--concept-hosting-bg:#f0f9ff;
--concept-disposition:#6d28d9;--concept-disposition-bg:#f5f3ff;
--concept-constraint:#a16207;--concept-constraint-bg:#fffbeb;
--concept-system-pattern:#a21caf;--concept-system-pattern-bg:#fdf4ff;
--concept-component-pattern:#4338ca;--concept-component-pattern-bg:#eef2ff;
--concept-store:#047857;--concept-store-bg:#ecfdf5;
--concept-component:#0f766e;--concept-component-bg:#f0fdfa;
--concept-plan:#b91c1c;--concept-plan-bg:#fef2f2;
--concept-assumption:#92400e;--concept-assumption-bg:#fff7ed;
--concept-decision:#166534;--concept-decision-bg:#f0fdf4;
--concept-feedback:#b45309;--concept-feedback-bg:#fffbeb;
--concept-removal:#9f1239;--concept-removal-bg:#fff1f2;
--concept-prose:#475569;--concept-prose-bg:#f8fafc}
@media (prefers-color-scheme:dark){:root{--bg:#16171a;--fg:#e8e7e3;--muted:#9a998f;
--line:#2e3034;--card:#1d1f23;--accent:#8ab4e0;--warn:#e0a468;--warn-bg:#2a2119;
--ok:#7fc4a0;--pend:#d6bd6a;--code:#24262b;
--acc-domain:#c4b5fd;--acc-domain-bg:#2a2140;
--acc-constraints:#67e8f9;--acc-constraints-bg:#163238;
--acc-components:#f9a8d4;--acc-components-bg:#3a1c2a;
--acc-plans:#fca5a5;--acc-plans-bg:#3a1414;
--concept-entity:#93c5fd;--concept-entity-bg:#172554;
--concept-rule:#d8b4fe;--concept-rule-bg:#3b1b5a;
--concept-workflow:#fdba74;--concept-workflow-bg:#431f0f;
--concept-hosting:#7dd3fc;--concept-hosting-bg:#17364a;
--concept-disposition:#c4b5fd;--concept-disposition-bg:#2e1e55;
--concept-constraint:#fde047;--concept-constraint-bg:#442f0d;
--concept-system-pattern:#f0abfc;--concept-system-pattern-bg:#44123f;
--concept-component-pattern:#a5b4fc;--concept-component-pattern-bg:#272357;
--concept-store:#6ee7b7;--concept-store-bg:#123b2c;
--concept-component:#5eead4;--concept-component-bg:#123b39;
--concept-plan:#f87171;--concept-plan-bg:#46151a;
--concept-assumption:#fdba74;--concept-assumption-bg:#43230d;
--concept-decision:#86efac;--concept-decision-bg:#15351f;
--concept-feedback:#fcd34d;--concept-feedback-bg:#3b2c0d;
--concept-removal:#fda4af;--concept-removal-bg:#49141f;
--concept-prose:#cbd5e1;--concept-prose-bg:#273041}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
header{padding:2rem 1.5rem .6rem;max-width:78rem;margin:0 auto}
h1{font-size:1.6rem;margin:0 0 .2rem}
.meta{color:var(--muted);margin:0 0 .9rem;font-size:.9rem}
nav{display:flex;flex-wrap:wrap;gap:.4rem;position:sticky;top:0;z-index:2;
padding:.6rem 1.5rem;background:var(--bg);border-bottom:1px solid var(--line);
max-width:78rem;margin:0 auto}
/* Artifact accents frame sections; concept accents distinguish their blocks. */
/*ACCENT_SCOPE*/
/*CONCEPT_ACCENT_SCOPE*/
nav a{color:var(--acc,var(--accent));text-decoration:none;font-weight:600;font-size:.88rem;
padding:.3rem .7rem;border:1px solid var(--line);border-radius:999px}
nav a:hover{border-color:var(--acc,var(--accent))}
main{max-width:78rem;margin:0 auto;padding:0 1.5rem 4rem}
section{margin-top:2.4rem;scroll-margin-top:4rem}
h2{font-size:1.25rem;margin:0 0 .8rem;padding:0 0 .4rem .7rem;
margin-left:-.7rem;border-bottom:2px solid var(--line);
border-left:.3rem solid var(--acc,var(--line))}
.file{font:600 .74rem/1 ui-monospace,SFMono-Regular,Menlo,monospace;
color:var(--acc,var(--muted));background:var(--acc-bg,transparent);
padding:.2rem .5rem;border-radius:999px;margin-left:.5rem}
.artifact-content{border:1px solid var(--line);border-left:.3rem solid var(--artifact-acc,var(--line));
border-radius:8px;padding:.1rem .85rem .85rem;background:var(--card)}
details{border:1px solid var(--line);border-left:.25rem solid var(--acc,var(--line));
border-radius:8px;margin:.6rem 0;background:var(--card)}
summary{cursor:pointer;padding:.6rem .85rem;font-weight:600;font-size:.95rem}
summary::marker{color:var(--muted)}
.count{color:var(--muted);font-weight:400;font-size:.85rem}
.block{padding:0 .85rem .85rem}
.scroll{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;vertical-align:top;padding:.45rem .6rem;
border-top:1px solid var(--line)}
thead th{color:var(--acc,var(--muted));background:var(--acc-bg,transparent);
font-size:.76rem;font-weight:700;text-transform:uppercase;
letter-spacing:.05em;border-top:0}
table.kv th{width:11rem;color:var(--muted);font-weight:600}
td.rowid{scroll-margin-top:4rem}
td.rowid>code{white-space:nowrap}
code{font:.85em/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;
background:var(--code);padding:.1em .35em;border-radius:4px}
a.ref{color:var(--accent);text-decoration:none}
a.ref:hover{text-decoration:underline}
ul.refs,ul.plain{margin:0;padding-left:1.1rem}
ul.refs li,ul.plain li{margin:.12rem 0}
.type{color:var(--muted);font-size:.85em}
.none{color:var(--muted)}
.caption{color:var(--muted);font-size:.85rem;margin:.1rem 0 .55rem;max-width:62rem}
.warn{color:var(--warn);font-weight:600}
.warn-box{background:var(--warn-bg);border-left:3px solid var(--warn);
padding:.4rem .6rem;border-radius:0 4px 4px 0;margin:.4rem 0}
.warn-box .warn{display:block}
.warn-box ul.plain{margin-top:.3rem}
.notice{background:var(--warn-bg);border-left:3px solid var(--warn);
padding:.5rem .7rem;border-radius:0 4px 4px 0;font-size:.9rem}
.badge{display:inline-block;padding:.1rem .5rem;border-radius:999px;
font-size:.78rem;font-weight:600;border:1px solid var(--line)}
.badge.settled{color:var(--ok)}
.badge.pending{color:var(--pend)}
.badge.disp-prioritized{color:var(--ok)}
.badge.disp-traded-away{color:var(--warn)}
.badge.disp-not-load-bearing{color:var(--muted)}
.card{border:1px solid var(--line);border-left:.25rem solid var(--acc,var(--line));
border-radius:8px;padding:.7rem .85rem;
margin:.6rem 0;background:var(--bg);scroll-margin-top:4rem}
.card h4{margin:0 0 .5rem;font-size:1rem}
pre.prose{white-space:pre-wrap;word-wrap:break-word;margin:0;
font:.86rem/1.6 ui-monospace,SFMono-Regular,Menlo,monospace;
background:var(--code);padding:.8rem;border-radius:6px;overflow-x:auto}

/* Print a readable light document without screen-only navigation. */
@media print{
  :root{--bg:#fff;--fg:#111;--muted:#555;--line:#ccc;--card:#fff;--code:#f3f3f3;
  --accent:#2f5d8c;--warn:#8a3d0f;--warn-bg:#fbeee1;--ok:#1d5c37;--pend:#6b5514;
  --acc-domain:#5b21b6;--acc-domain-bg:#f2eefb;
  --acc-constraints:#0c5a6b;--acc-constraints-bg:#e9f4f5;
  --acc-components:#9d174d;--acc-components-bg:#faeaf1;
  --acc-plans:#7f1d1d;--acc-plans-bg:#f8ecec;
  --concept-entity:#1e40af;--concept-entity-bg:#eff6ff;
  --concept-rule:#6b21a8;--concept-rule-bg:#faf5ff;
  --concept-workflow:#9a3412;--concept-workflow-bg:#fff7ed;
  --concept-hosting:#075985;--concept-hosting-bg:#f0f9ff;
  --concept-disposition:#4338ca;--concept-disposition-bg:#eef2ff;
  --concept-constraint:#854d0e;--concept-constraint-bg:#fffbeb;
  --concept-system-pattern:#86198f;--concept-system-pattern-bg:#fdf4ff;
  --concept-component-pattern:#3730a3;--concept-component-pattern-bg:#eef2ff;
  --concept-store:#065f46;--concept-store-bg:#ecfdf5;
  --concept-component:#0f766e;--concept-component-bg:#f0fdfa;
  --concept-plan:#991b1b;--concept-plan-bg:#fef2f2;
  --concept-assumption:#78350f;--concept-assumption-bg:#fff7ed;
  --concept-decision:#166534;--concept-decision-bg:#f0fdf4;
  --concept-feedback:#92400e;--concept-feedback-bg:#fffbeb;
  --concept-removal:#9f1239;--concept-removal-bg:#fff1f2;
  --concept-prose:#334155;--concept-prose-bg:#f8fafc}
  body{font-size:11pt}
  nav{display:none}
  header{padding:0 0 .5rem}
  main{padding:0}
  /* The first follows the header; each later artifact starts on a new page. */
  section{margin-top:0;break-before:page}
  section:first-of-type{break-before:avoid}
  h2,summary,.card h4{break-after:avoid-page}
  /* Print every generated section, even if a viewer collapsed it on screen. */
  details>*:not(summary){display:block!important}
  tr,.card,.warn-box,table.kv{break-inside:avoid}
  thead{display:table-header-group}
  table{font-size:9pt}
  .scroll{overflow:visible}
  a.ref{text-decoration:underline}
  pre.prose{overflow:visible;font-size:8.5pt}
  @page{margin:1.8cm 1.5cm}
}
"""
_STYLE = _STYLE.replace("/*ACCENT_SCOPE*/", _accent_scope_rules())
_STYLE = _STYLE.replace("/*CONCEPT_ACCENT_SCOPE*/", _concept_accent_scope_rules())
# The diagram's rules ship with the module that emits the classes they name,
# rather than being restated here where the two could drift apart.
_STYLE += ER_STYLE
