"""Drift guard for ``ROADMAP_FORMAT.md``'s worked examples.

The doc is the schema contract an operator reads before hand-editing an
artifact, and its examples are the part they copy. Nothing else checks them:
``CAPABILITIES.md`` has ``capability_catalog``, ``DATA_CONTRACT.md`` has
``test_data_contract``, ``docs/cli/`` has ``test_cli_reference`` — this doc was
the one format doc with no guard, so an example could go stale the next time a
field or a gate lands and nothing would say so.

Crosses ``roadmap_artifacts`` and ``roadmap_gates`` deliberately: the doc
documents shape *and* relations, so a guard that only parsed would miss an
example that parses and violates. Neither module shells out, so this stays a
plain unit test.
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
from pathlib import Path
from typing import get_args, get_type_hints

import pytest

import plan_tool.cli.authoring as roadmap_authoring
import plan_tool.cli.roadmap_cmd as roadmap_cmd
from plan_tool import (
    create,
    roadmap,
)
from plan_tool.roadmap_artifacts import (
    ConstraintDisposition,
    DecisionStatus,
    DRAFT_SEED_ROADMAP_COMPONENTS_KEY,
    FeedbackState,
    FeedbackTargetKind,
    FieldType,
    HOSTING_FACETS,
    PlanDisposition,
    STACK_CONCERNS,
    parse_components_artifact,
    parse_constraints_artifact,
    parse_domain_artifact,
    parse_draft_seed_provenance,
    parse_plans_artifact,
    render_components_artifact,
    render_constraints_artifact,
    render_domain_artifact,
    render_plans_artifact,
)
from plan_tool import roadmap_gates
from plan_tool.roadmap_gates import (
    ArtifactEnvelope,
    HOSTING_FACET_VALUES,
    STORE_CATEGORIES,
    STORE_SHARING_MODELS,
    run_components_gates,
    run_constraints_gates,
    run_domain_gates,
    run_plans_gates,
)
from plan_tool.roadmap import STAGES
from plan_tool.roadmap_revision import (
    REVISION_OPERATION_EXAMPLE_JSON,
    TEXT_FIELDS_BY_ROW_TYPE,
)
from plan_tool.roadmap_candidate_context import (
    CANDIDATE_CONTEXT_MAX_BYTES,
    build_candidate_context,
    expand_candidate_context,
)
from plan_tool.roadmap_candidate import CandidateMaterializationResult, materialize_candidate
from plan_tool.roadmap_candidate_review import (
    answer_candidate_question,
    generate_candidate_question,
    request_replacement,
    seal_review,
)
from plan_tool.roadmap_candidate_run import run_initial_candidate_proposal
from plan_tool.roadmap_version_promotion import promote_review_seal
from plan_tool.roadmap_versions import AcceptedRoadmapHead, load_accepted_version
from plan_tool.roadmap_view import load_roadmap
from plan_tool.run_log import (
    RoadmapStructuralRevisionAttempt,
    RoadmapStructuralRevisionPreflight,
)

_DOC = Path(__file__).resolve().parents[1] / "ROADMAP_FORMAT.md"
_REPO_ROOT = _DOC.parent
_BACKLOG = _REPO_ROOT / "BACKLOG.md"
_ROADMAP_ARC = _REPO_ROOT / "docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md"
_CLAUDE_DOC = _REPO_ROOT / "CLAUDE.md"
_ROADMAP_COMPARISON_GUIDES = {
    "ROADMAP_FORMAT.md": _DOC,
    "CAPABILITIES.md": _REPO_ROOT / "CAPABILITIES.md",
    "README.md": _REPO_ROOT / "README.md",
    "docs/reference/commands.md": _REPO_ROOT / "docs/reference/commands.md",
    "docs/how-to/roadmap.md": _REPO_ROOT / "docs/how-to/roadmap.md",
}
# The heading the before/after pair lives under. Split there rather than
# indexing the block list: a new example inserted above would silently
# re-point positional indices at the wrong artifacts.
_REVISION_HEADING = "### A revision, with feedback"
_DRAFT_SEED_HEADING = "## Draft seeds"
_DRAFT_SEED_SECTION_END = "## The schema is open"

# A ```markdown fence opening on the frontmatter fence is a *runnable* example.
# The fence language is load-bearing and not incidental: ```yaml blocks that
# also open on ``---`` are annotated schema, carrying ``#`` commentary and
# placeholder values, so parsing them would fail on content that is correct for
# what it is. Retag a block ```markdown only if it is meant to round-trip.
_ARTIFACT_BLOCK = re.compile(r"```markdown\n(---\n.*?)```", re.S)

# Every fenced body, whatever its language — the vocabulary check below reads
# these, because the row fragments an operator copies most are not parseable
# standalone and would otherwise go unchecked.
_ANY_BLOCK = re.compile(r"```\w*\n(.*?)```", re.S)

# The closed vocabularies by the frontmatter key that carries them. A literal
# printed in this doc is a literal an operator will type, so a value outside its
# enum is a defect here even where no example parses.
_VOCAB_BY_KEY = {
    "state": FeedbackState,
    "kind": FeedbackTargetKind,
    "status": DecisionStatus,
    "type": FieldType,
}

_VOCAB_KEYS = (*_VOCAB_BY_KEY, "disposition")

_VOCAB_LINE = re.compile(
    rf"^\s*-?\s*({'|'.join(_VOCAB_KEYS)}):\s*(\S+)", re.M
)


def _artifact_blocks(text: str) -> list[str]:
    return _ARTIFACT_BLOCK.findall(text)


def _artifact_example_blocks(text: str) -> list[str]:
    """Runnable roadmap artifacts — excludes draft-seed provenance snippets."""
    return [
        block
        for block in _artifact_blocks(text)
        if f"\n{DRAFT_SEED_ROADMAP_COMPONENTS_KEY}:" not in block.split("---", 2)[1]
    ]


def _parse(block: str):
    """Parse one example, choosing the parser by a key only that shape has."""
    frontmatter = block.split("---", 2)[1]
    if "\nentities:" in frontmatter:
        return parse_domain_artifact(block), run_domain_gates
    if "\ndispositions:" in frontmatter:
        return parse_constraints_artifact(block), run_constraints_gates
    if "\nplans:" in frontmatter:
        return parse_plans_artifact(block), run_plans_gates
    if "\nsystem_patterns:" in frontmatter or "\ncomponents:" in frontmatter:
        return parse_components_artifact(block), run_components_gates
    raise AssertionError(
        "artifact example carries none of 'entities:', 'dispositions:', "
        "'plans:', 'system_patterns:', or 'components:'; the guard cannot "
        "tell which parser owns it"
    )


def _render(artifact, gates):
    if gates is run_domain_gates:
        return render_domain_artifact(artifact)
    if gates is run_constraints_gates:
        return render_constraints_artifact(artifact)
    if gates is run_components_gates:
        return render_components_artifact(artifact)
    if gates is run_plans_gates:
        return render_plans_artifact(artifact)
    raise AssertionError(f"no renderer for {gates!r}")


def _disposition_enum(block: str):
    """``disposition`` is plan or constraint vocabulary depending on artifact."""
    if "\nplans:" in block:
        return PlanDisposition
    if "\ndispositions:" in block:
        return ConstraintDisposition
    return None


@pytest.fixture(scope="module")
def doc() -> str:
    return _DOC.read_text(encoding="utf-8")


def test_the_doc_still_ships_artifact_examples(doc: str) -> None:
    """Deleting the examples must fail here, not quietly shrink coverage."""
    assert len(_artifact_example_blocks(doc)) >= 6


def test_every_artifact_example_parses(doc: str) -> None:
    for index, block in enumerate(_artifact_example_blocks(doc), 1):
        _parse(block)  # raises RoadmapArtifactError with the offending field


def test_standalone_examples_clear_their_own_gates(doc: str) -> None:
    """The first-run examples are what a fresh stage is asked to produce.

    The constraints and components examples are judged in the envelope they
    really run in — with upstream artifacts beside them — so this also pins
    that the doc's first-run artifacts agree: a constraint anchored to an
    entity id the domain example does not declare, or a component citing a
    constraint the constraints example does not declare, fails here rather
    than in a reader's own run.
    """
    blocks = _artifact_example_blocks(doc.split(_REVISION_HEADING)[0])
    assert blocks, "no artifact example precedes the revision section"
    parsed = [_parse(block) for block in blocks]

    domains = [art for art, gates in parsed if gates is run_domain_gates]
    assert domains, "no domain example to resolve constraints anchors against"
    domain = domains[0]

    constraints_list = [
        art for art, gates in parsed if gates is run_constraints_gates
    ]
    assert constraints_list, "no constraints example for components to resolve against"
    constraints = constraints_list[0]

    components_list = [
        art for art, gates in parsed if gates is run_components_gates
    ]
    assert components_list, "no components example for plans to resolve against"
    components = components_list[0]

    for artifact, gates in parsed:
        if gates is run_domain_gates:
            envelope = ArtifactEnvelope(domain=artifact)
        elif gates is run_constraints_gates:
            envelope = ArtifactEnvelope(domain=domain, constraints=artifact)
        elif gates is run_components_gates:
            envelope = ArtifactEnvelope(
                domain=domain, constraints=constraints, components=artifact
            )
        else:
            envelope = ArtifactEnvelope(
                domain=domain,
                constraints=constraints,
                components=components,
                plans=artifact,
            )
        violations = list(gates(envelope))
        assert violations == [], [v.message for v in violations]


def test_every_artifact_example_round_trips(doc: str) -> None:
    for index, block in enumerate(_artifact_example_blocks(doc), 1):
        artifact, gates = _parse(block)
        round_tripped = _parse(_render(artifact, gates))[0]
        assert round_tripped == artifact, f"example {index} changed after render"


def test_the_revision_example_clears_its_gates_against_its_predecessor(
    doc: str,
) -> None:
    """The pair is the doc's only demonstration that the loop works.

    The three revision gates are inert without a predecessor, so a
    feedback-bearing artifact judged alone proves nothing — this is the
    assertion that makes the example evidence rather than illustration.
    """
    sections = doc.split(_REVISION_HEADING)
    assert len(sections) == 2, f"{_REVISION_HEADING!r} not found exactly once"
    blocks = _artifact_blocks(sections[1])
    assert len(blocks) >= 2, "the revision section needs a before and an after"

    (predecessor, gates), (revision, _) = _parse(blocks[0]), _parse(blocks[1])
    key = "domain" if gates is run_domain_gates else "constraints"
    envelope = ArtifactEnvelope(**{key: revision}, predecessor=predecessor)

    violations = list(gates(envelope))
    assert violations == [], [v.message for v in violations]


def test_the_revision_example_actually_exercises_the_review_collections(
    doc: str,
) -> None:
    """A pair carrying no feedback would clear the gates and show nothing."""
    blocks = _artifact_blocks(doc.split(_REVISION_HEADING)[1])
    predecessor, _ = _parse(blocks[0])
    revision, _ = _parse(blocks[1])

    assert predecessor.feedback, "the 'before' artifact carries no feedback"
    assert revision.feedback, "the 'after' artifact carries no feedback"
    assert any(
        row.proposed_response for row in revision.feedback
    ), "no row in the revision carries a proposed_response"


def test_every_closed_vocabulary_literal_the_doc_prints_is_real(doc: str) -> None:
    """No example may print a lifecycle value the parser would reject.

    Covers the row fragments the artifact-example tests cannot reach: a
    ``feedback:`` snippet is not a parseable artifact, and it is the block an
    operator adding one row by hand actually copies.
    """
    bad: list[str] = []
    for block in _ANY_BLOCK.findall(doc):
        disposition_enum = _disposition_enum(block)
        for key, raw in _VOCAB_LINE.findall(block):
            value = raw.split("#")[0].strip().strip("'\"")
            if not value or value.startswith("<"):
                continue  # a placeholder, not a literal
            if key == "disposition":
                if disposition_enum is None:
                    continue
                allowed = {m.value for m in disposition_enum}
            else:
                allowed = {m.value for m in _VOCAB_BY_KEY[key]}
            if value not in allowed:
                bad.append(f"{key}: {value}")
    assert not bad, f"values outside their closed vocabulary: {sorted(set(bad))}"


def test_hosting_schema_documents_the_complete_gate_owned_vocabulary(doc: str) -> None:
    start = doc.index("**Hosting facets and values**")
    end = doc.index("**Store categories and sharing models**", start)
    section = doc[start:end]

    assert "hosting:" in doc
    assert all(facet in section for facet in HOSTING_FACETS)
    assert all(
        value in section
        for values in HOSTING_FACET_VALUES.values()
        for value in values
    )
    assert "no undecided member" in section
    assert "runtime/store compatibility" in section


def test_store_schema_documents_the_complete_gate_owned_vocabulary(doc: str) -> None:
    start = doc.index("**Store categories and sharing models**")
    end = doc.index("**Feedback state**", start)
    section = doc[start:end]

    assert "stores:" in doc
    assert all(value in section for value in STORE_CATEGORIES)
    assert all(value in section for value in STORE_SHARING_MODELS)
    assert "undecided member" in section
    assert "self-hosted" in section


def _test_feedback_lifecycle_documents_the_redacted_feedback_reopen_record(doc: str) -> None:
    start = doc.index("## The review collections")
    end = doc.index("## Local feedback revision contract", start)
    section = " ".join(doc[start:end].split())

    for field in ("feedback_reopen", "selector", "reason", "nonce", "recorded_at"):
        assert field in section
    assert "operator-confirmed-evidence-unavailable" in section
    assert "43-character URL-safe" in section
    assert "six fractional-second digits and trailing `Z`" in section
    for forbidden_content in (
        "response text",
        "evidence",
        "digest",
        "path",
        "attestation",
        "free-form operator statement",
    ):
        assert forbidden_content in section


def _test_feedback_lifecycle_keeps_reviewer_reopen_and_revise_feedback_boundaries(
    doc: str,
) -> None:
    lifecycle_start = doc.index("### The feedback lifecycle")
    local_revision_start = doc.index("## Local feedback revision contract", lifecycle_start)
    lifecycle = " ".join(doc[lifecycle_start:local_revision_start].split())
    local_revision = " ".join(doc[local_revision_start:].split())

    assert "Ordinary close, defer, and reopen moves remain the reviewer's edits" in lifecycle
    assert "explicitly confirmed operator `--reopen-feedback` action" in lifecycle
    assert "not a model revision path" in lifecycle
    assert "fresh normal stage response clears the record" in lifecycle
    assert "does not close, defer, reopen feedback, or author a `feedback_reopen` record" in local_revision
    assert "not an ordinary ledger route" in local_revision


def test_hosting_and_store_schema_document_optional_description_and_research_disclosure(
    doc: str,
) -> None:
    constraints_start = doc.index("## `02-constraints.md` — frontmatter schema")
    components_start = doc.index("## `03-components.md` — frontmatter schema")
    constraints_schema = doc[constraints_start:components_start]
    components_schema = doc[components_start:doc.index("## `04-roadmap.md`", components_start)]

    for schema in (constraints_schema, components_schema):
        normalized_schema = " ".join(schema.split())
        assert "description: string" in schema
        assert "optional operator text" in schema
        assert "no vocabulary or quality rule" in normalized_schema
        assert "distinct from `product`" in schema
        assert "research_disclosure: external | local" in schema
        assert (
            "only `research_disclosure: external` explicitly permits"
            in normalized_schema.lower()
        )
        assert "`local`, absence, and `null` keep it local" in normalized_schema


def test_draft_seed_provenance_examples_parse(doc: str) -> None:
    """Provenance snippets under the draft-seeds section parse without error."""
    sections = doc.split(_DRAFT_SEED_HEADING)
    assert len(sections) >= 2, f"{_DRAFT_SEED_HEADING!r} not found"
    draft_section = sections[1].split(_DRAFT_SEED_SECTION_END)[0]
    for block in _ARTIFACT_BLOCK.findall(draft_section):
        parse_draft_seed_provenance(block)


def test_data_contract_documents_no_retired_source_record_events() -> None:
    """Pin that DATA_CONTRACT.md no longer describes the removed source.json lifecycle events."""
    text = " ".join(
        (_REPO_ROOT / "DATA_CONTRACT.md").read_text(encoding="utf-8").lower().split()
    )
    for retired in (
        "roadmapsourceresolved",
        "roadmapsourcerecorded",
        "roadmapsourceadmission",
        "roadmaplocalrevisionpreflight",
        "roadmaplocalrevisionattempt",
    ):
        assert retired not in text, retired


def test_roadmap_arc_router_includes_all_untiered_roadmap_items() -> None:
    """Keep every untiered roadmap-arc item visible from the backlog router."""
    backlog = " ".join(_BACKLOG.read_text(encoding="utf-8").split())
    assert "#208, #366, the structured-upstream group #383–#384, and #385" in backlog


def _immutable_candidate_version_reference_block(doc: str) -> str:
    match = re.search(
        r"<!-- immutable-candidate-version-authority:start -->\n"
        r"(?P<content>.*?)\n"
        r"<!-- immutable-candidate-version-authority:end -->",
        doc,
        re.S,
    )
    assert match, "immutable candidate-version authority markers are missing"
    return match.group("content")


def test_roadmap_format_authority_block_matches_landed_ledger_candidate_lifecycle(doc: str) -> None:
    """Keep ordinary feedback bound to the ledger batch rather than an artifact selector."""
    section = _immutable_candidate_version_reference_block(doc)
    for anchor in (
        "plan_tool/roadmap_versions.py:AcceptedRoadmapHead",
        "plan_tool/roadmap_feedback_ledger.py",
        "plan_tool/roadmap_candidate_context.py:build_candidate_context",
        "plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal",
        "plan_tool/roadmap_candidate_review.py:seal_review",
        "plan_tool/roadmap_version_promotion.py:promote_review_seal",
    ):
        assert anchor in section
    assert "feedback selector" not in section


def test_ordinary_feedback_documentation_uses_selector_free_candidate_proposal() -> None:
    """Keep public ordinary workflow guides on the ledger-to-candidate route."""
    root = _DOC.parent
    for relative in (
        "ROADMAP_FORMAT.md", "README.md", "CAPABILITIES.md", "docs/ARCHITECTURE.md",
        "docs/how-to/roadmap.md",
    ):
        text = (root / relative).read_text(encoding="utf-8")
        assert "--propose-candidate" in text, relative
        assert "--revise-feedback" not in text, relative
    cli_reference = (root / "docs/cli/roadmap.md").read_text(encoding="utf-8")
    assert "--propose-candidate" in cli_reference
    assert "--revise-feedback" in cli_reference
    assert "Accepts no feedback selector" in cli_reference


def _backlog_328_block() -> str:
    backlog = _BACKLOG.read_text(encoding="utf-8")
    start = backlog.index("**Closed #328 — Immutable accepted-head roadmap versions**")
    end = backlog.index("\n\n**#327 — Intentional seed ingestion", start)
    return backlog[start:end]


def _test_immutable_candidate_version_reference_matches_landed_authority_contract(
    doc: str,
) -> None:
    """Keep authority at the accepted selector and its exact lifecycle bindings."""
    section = " ".join(_immutable_candidate_version_reference_block(doc).split())
    assert CANDIDATE_CONTEXT_MAX_BYTES == 384 * 1024

    owners = (
        AcceptedRoadmapHead,
        load_accepted_version,
        build_candidate_context,
        expand_candidate_context,
        run_initial_candidate_proposal,
        materialize_candidate,
        generate_candidate_question,
        answer_candidate_question,
        request_replacement,
        seal_review,
        promote_review_seal,
        load_roadmap,
    )
    for owner in owners:
        module = owner.__module__.replace(".", "/") + ".py"
        assert f"{module}:{owner.__name__}" in section

    for boundary in (
        "sole selector of canonical content",
        "stored candidate, review seal, model reply, version-directory order, and live top-level artifact paths cannot select canonical content",
        "one fixed feedback selector",
        "different feedback selector refuses before a model call, both before and after promotion",
        CandidateMaterializationResult.__name__,
        "hard `refusal`, then a `review_required` candidate, then a gate-clean `candidate`",
        "currently 384 KiB",
        "A capsule issued under an earlier ceiling (64 KiB or 192 KiB) keeps that ceiling and stays readable",
        "a stored selector capsule is also re-enterable, because it is reproduced at its recorded ceiling, never the current one",
        "a stored batch capsule is verified by its digest and receipts and never re-rendered",
        "The one caller-supplied ceiling is",
        "it accepts only a value the module has issued",
        "Each new context, including a new batch hop on a stored candidate, uses the current ceiling",
        "callers cannot override it, silently truncate it, summarize it, or widen the lineage",
        "stored question-and-answer pair, not answer text alone",
        "Exact proposal and answer re-entry",
        "Model output remains inert until exact review-seal promotion",
        "Promotion is terminal consumption of the exact review seal",
        "changes only the accepted head",
    ):
        assert boundary in section


def _test_candidate_policy_reference_orders_hard_refusal_review_required_and_gate_clean(
    doc: str,
) -> None:
    """Keep the materializer's three mutually exclusive outcomes in precedence order."""
    section = _immutable_candidate_version_reference_block(doc)
    hard_refusal = section.index("a hard `refusal`")
    review_required = section.index("a `review_required` candidate")
    gate_clean = section.index("a gate-clean `candidate`")

    assert hard_refusal < review_required < gate_clean
    assert "A hard refusal\npublishes no candidate." in section
    assert (
        "Review-required classification occurs only after\nordinary capsule authority, rendering, "
        "declared-relation, and complete-roadmap\nchecks pass" in section
    )
    assert "The gate-clean candidate applies only when no\nreview requirement remains." in section


def _test_candidate_policy_reference_requires_multiplicity_preserving_containment_for_every_replacement_arm(
    doc: str,
) -> None:
    """Keep every review-required replacement inside its initially disclosed impact facts."""
    section = _immutable_candidate_version_reference_block(doc)

    for boundary in (
        "For every review-required-lineage replacement, including a gate-clean result",
        "recomputes\ncandidate-impact atoms",
        "multiplicity-preserving containment\nby the initial disclosure",
        "Repeated declared-relation occurrences remain\nsource-ordered occurrence facts",
        "containment is not set membership,\nimpact-identity equality, or record-identity equality",
    ):
        assert boundary in section


def _test_candidate_policy_reference_keeps_review_inert_until_exact_promotion(doc: str) -> None:
    """Keep deterministic review disclosure separate from approval and canonical promotion."""
    section = _immutable_candidate_version_reference_block(doc)

    for boundary in (
        "stored deterministic review requirement beside its one opaque-question\nresponse",
        "selected feedback remains the user request",
        "opaque\nanswer is neither approval nor semantic validation",
        "reuses its initially admitted capsule and receipt",
        "cannot use\nthe gate-clean lineage's context-expansion route",
        "refuses before it writes\na replacement or a seal",
        "Two guarded writers change the accepted head, each only after its own\n"
        "verification: `plan_tool/roadmap_version_promotion.py:promote_review_seal()`\n"
        "changes it after verifying the exact sealed replacement and its current\n"
        "accepted predecessor, and\n"
        "`plan_tool/roadmap_decision_settlement_enrolled.py:run_enrolled_decision_settlement()`\n"
        "changes it after rechecking the current accepted predecessor and storing its\n"
        "one new immutable settled version. No other writer moves the selector.",
    ):
        assert boundary in section


def test_candidate_policy_retirement_reconciles_backlog_and_arcs() -> None:
    """Keep the delivered candidate policy out of active backlog ownership."""
    backlog = _BACKLOG.read_text(encoding="utf-8")
    roadmap_arc = _ROADMAP_ARC.read_text(encoding="utf-8")

    assert "#354" not in backlog
    assert "#354" not in roadmap_arc
    assert "until it ships" not in roadmap_arc.lower()


def test_version_authority_reference_lists_exactly_the_deferred_direct_readers() -> None:
    """Keep the one converted reader distinct from the deferred migration set."""
    record = _backlog_328_block()
    start = record.index("**Direct-reader migration boundary:**")
    end = record.index("**Real-backend observation", start)
    migration = record[start:end]
    readers = re.findall(r"`([^`]+)`", migration)
    assert readers == [
        "plan_tool/roadmap_view.py:load_roadmap()",
        "plan_tool/create.py:_load_roadmap_research_targets()",
        "plan_tool/cli/authoring.py:_confirm_invalidated_roadmap_seed()",
        "plan_tool/cli/roadmap_cmd.py:cmd_roadmap()",
    ]
    assert "completed proof" in migration
    assert "Defer accepted-head migration scope selection" in migration
    assert all(
        callable(symbol)
        for symbol in (
            create._load_roadmap_research_targets,
            roadmap_authoring._confirm_invalidated_roadmap_seed,
            roadmap_cmd.cmd_roadmap,
        )
    )


def test_claude_roadmap_reference_tracks_immutable_version_authority() -> None:
    """Point developers to the lifecycle reference without copying its inventory."""
    claude = _CLAUDE_DOC.read_text(encoding="utf-8")
    architecture_start = claude.index("**Cycle-free import constraints, in one place.**")
    architecture_end = claude.index("**Exit-code convention:**", architecture_start)
    architecture = claude[architecture_start:architecture_end]
    assert "immutable accepted-head versions" in architecture
    assert "`ROADMAP_FORMAT.md` owns that lifecycle" in architecture

    reference_docs = claude[claude.index("## Reference docs"):]
    roadmap_line = next(line for line in reference_docs.splitlines() if line.startswith("- `ROADMAP_FORMAT.md`"))
    assert "immutable accepted-head versions" in roadmap_line
    for detail in (
        "CANDIDATE_CONTEXT_MAX_BYTES",
        "run_initial_candidate_proposal",
        "plan_tool/create.py:_load_roadmap_research_targets()",
    ):
        assert detail not in claude


def test_backlog_328_closure_records_redacted_real_backend_observation() -> None:
    """Retain only the bounded operational observation that closes the item."""
    backlog = _BACKLOG.read_text(encoding="utf-8")
    active_table = re.search(r"\| Lane \| Item \| Why \|\n(?:\|.*\|\n)+", backlog)
    assert active_table, "active backlog table is missing"
    assert "#328" not in active_table.group(0)

    record = _backlog_328_block()
    match = re.search(
        r"\*\*Real-backend observation \((?P<date>\d{4}-\d{2}-\d{2}), redacted\):\*\*"
        r"(?P<facts>.*?)(?=\n- \*\*Status:)",
        record,
        re.S,
    )
    assert match, "#328 lacks a dated redacted backend observation"
    facts = " ".join(match.group("facts").split())
    assert match.group("date") == "2026-09-01"
    for fact in (
        "candidate phase",
        "13,212 prompt bytes",
        "2 full members and 19 inventory entries",
        "expansion is not used",
        "terminal outcome is `failed`",
        "no prompt, response, or model-quality claim",
    ):
        assert fact in facts
    assert re.findall(r"`(stored|response-rejected|failed|refused)`", facts) == ["failed"]
    for forbidden in (
        "Clarify the recorded decision.",
        "Recorded real-backend observation brief.",
        "attribute-maintainability",
    ):
        assert forbidden not in facts


def test_draft_seed_fence_refusal_documentation_names_its_gate() -> None:
    document = _DOC.read_text(encoding="utf-8")

    assert (
        "An unmatched opening code fence in a draft body is a materialization refusal"
        in document
    )
    assert "validate_draft_seed_content" in document


def test_roadmap_comparison_guidance_sweep_matches_landed_contract() -> None:
    """Keep public comparison guides aligned with the parser and evidence boundary."""
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    roadmap_cmd.register(subparsers)
    roadmap_parser = subparsers.choices["roadmap"]
    option_strings = {
        option
        for action in roadmap_parser._actions
        for option in action.option_strings
    }
    assert {"--compare", "--comparison-base", "--comparison-target", "--comparison-output"} <= option_strings

    for name, path in _ROADMAP_COMPARISON_GUIDES.items():
        guide = path.read_text(encoding="utf-8")
        assert "--compare" in guide, name
        assert "read-only" in guide, name
        assert "Git" in guide, name
        assert "complete" in guide, name


def test_every_prose_amendment_outcome_is_named_in_each_comparison_guide() -> None:
    """A new outcome must reach every guide that lists them, or this fails loudly."""
    from plan_tool.roadmap_compare import ComparisonProseAmendmentEvidence

    outcomes = get_args(ComparisonProseAmendmentEvidence.model_fields["outcome"].annotation)
    assert len(outcomes) == 4
    guides = {
        "ROADMAP_FORMAT.md": _DOC,
        "CAPABILITIES.md": _REPO_ROOT / "CAPABILITIES.md",
        "docs/reference/commands.md": _REPO_ROOT / "docs/reference/commands.md",
        "docs/how-to/roadmap.md": _REPO_ROOT / "docs/how-to/roadmap.md",
        "docs/ARCHITECTURE.md": _REPO_ROOT / "docs/ARCHITECTURE.md",
    }
    for name, path in guides.items():
        text = path.read_text(encoding="utf-8")
        for outcome in outcomes:
            assert f"`{outcome}`" in text, (name, outcome)


def test_roadmap_comparison_guidance_keeps_comparison_and_acceptance_separate() -> None:
    """Keep comparison review separate from all snapshot lifecycle actions."""
    walkthrough = (_REPO_ROOT / "docs/how-to/roadmap.md").read_text(encoding="utf-8")
    start = walkthrough.index("### Compare two snapshots before choosing a separate action")
    end = walkthrough.index("\n---", start)
    comparison = " ".join(walkthrough[start:end].split())

    assert "After review, choose any acceptance or lifecycle action separately" in comparison
    assert "comparison output is not an acceptance action" in comparison
    assert "It does not accept, promote, settle, repair" in comparison


def test_roadmap_comparison_backlog_retirement_removes_402() -> None:
    """Retire the shipped comparison feature instead of leaving a pending record."""
    backlog = _BACKLOG.read_text(encoding="utf-8")

    assert "#402" not in backlog
    assert "Compare roadmap revisions as concepts" not in backlog


def test_roadmap_format_preserves_accepted_head_as_sole_selector() -> None:
    """Keep immutable candidate evidence from becoming canonical artifact authority."""
    document = _DOC.read_text(encoding="utf-8")
    start = document.index("## Reviewer feedback and candidate lifecycle")
    end = document.index("## Narrative review evidence", start)
    lifecycle = document[start:end]

    assert "are the sole canonical-content selector" in lifecycle
    assert "Candidate creation, review, replacement, rejection, and staleness never" in lifecycle
    assert "Every later feedback proposal uses the promoted accepted version as its predecessor" in lifecycle


def test_roadmap_format_documents_structural_failure_preservation() -> None:
    """Keep all nonpublication exits outside accepted-head and artifact writes."""
    document = _DOC.read_text(encoding="utf-8")
    start = document.index("## Reviewer feedback and candidate lifecycle")
    end = document.index("## Narrative review evidence", start)
    lifecycle = document[start:end]

    assert "Invalid output, failed gates, interruption, rejection, edit, and stale bindings" in lifecycle
    assert "preserve canonical artifacts, seeds, and `AcceptedRoadmapHead`" in lifecycle


_REMOVED_ROUTE_TOKENS = (
    "--from-stage",
    "--confirm-brief-rebind",
    "--enroll-version",
    "--enroll-baselines",
    "--migrate-feedback-ledger",
    "--restore-revision",
    "--confirm-restore-revision",
    "--reopen-feedback",
    "--confirm-feedback-reopen",
    "--escalate-feedback",
    "--escalation-reason",
    "--analyze-escalation",
    "--rewrite-structural",
    "--rewrite-analysis",
    "source.json",
    "migration-pending",
)
_REMOVED_ROUTE_DOC_FILES = (
    "ROADMAP_FORMAT.md",
    "ROADMAP_FEEDBACK_FORMAT.md",
    "docs/how-to/roadmap.md",
    "docs/demos/roadmap-demo.md",
    "docs/ARCHITECTURE.md",
    "integrations/shared/DIRECTIVES.md",
    "integrations/claude/SKILL.md",
    "integrations/codex/SKILL.md",
    "integrations/cursor/SKILL.md",
    "README.md",
    "RUNBOOK.md",
    "DATA_CONTRACT.md",
    "CLAUDE.md",
    "docs/cli/roadmap.md",
    "docs/how-to/use-cases.md",
    "docs/how-to/common-workflows.md",
    "docs/reference/commands.md",
    "BUG_BACKLOG.md",
)
# A removed token may appear only on a dated, past-framed line, in the
# replacement note for `--reopen-feedback`, or in the hand-conversion procedure.
_REMOVED_ROUTE_EXEMPT_MARKERS = ("removed `--reopen-feedback`", "leftover top-level")
_DATE_PATTERN = re.compile(r"\b20\d\d-\d\d-\d\d\b")


def _roadmap_parser_option_strings() -> set[str]:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    roadmap_cmd.register(subparsers)
    return {
        option
        for action in subparsers.choices["roadmap"]._actions
        for option in action.option_strings
    }


@pytest.mark.parametrize("relative_path", _REMOVED_ROUTE_DOC_FILES)
def test_live_roadmap_docs_name_no_removed_route(relative_path: str) -> None:
    """Keep live docs free of a removed flag token unless the line is dated history, the replacement note, or hand conversion."""
    text = (_REPO_ROOT / relative_path).read_text(encoding="utf-8")
    offenders = [
        f"{number}: {line.strip()[:120]}"
        for number, line in enumerate(text.splitlines(), start=1)
        if any(token in line for token in _REMOVED_ROUTE_TOKENS)
        and not _DATE_PATTERN.search(line)
        and not any(marker in line for marker in _REMOVED_ROUTE_EXEMPT_MARKERS)
    ]
    assert offenders == [], f"{relative_path} names a removed roadmap route:\n" + "\n".join(offenders)


def test_removed_route_guard_covers_every_flag_the_parser_dropped() -> None:
    """The guard's flag tokens stay disjoint from the live parser, so it can neither flag a live flag nor go stale."""
    option_strings = _roadmap_parser_option_strings()
    flag_tokens = [token for token in _REMOVED_ROUTE_TOKENS if token.startswith("--")]

    assert [token for token in flag_tokens if token in option_strings] == []
    assert "--reopen-ledger-feedback" in option_strings
    assert "--reopen-ledger-feedback" not in _REMOVED_ROUTE_TOKENS


def test_how_to_documents_the_version_only_refusals_and_defaults() -> None:
    """The operator page keeps the refusals, defaults, and hand-conversion steps a reader hits after the store change."""
    guide = (_REPO_ROOT / "docs/how-to/roadmap.md").read_text(encoding="utf-8")

    for anchor in (
        "INDEX.md",
        "--reopen-ledger-feedback",
        "--comparison-target",
        "roadmap-stage-resume",
        "has no published version",
        "already has an accepted head",
        "Convert an older roadmap folder by hand",
    ):
        assert anchor in guide, anchor


def test_skill_roadmap_route_content_is_identical_across_backends() -> None:
    """The three SKILL.md roadmap rows stay textually parallel; only backend-specific words may differ."""
    rows_by_backend = {
        backend: [
            line
            for line in (_REPO_ROOT / f"integrations/{backend}/SKILL.md")
            .read_text(encoding="utf-8")
            .splitlines()
            if "roadmap <slug>" in line
        ]
        for backend in ("claude", "codex", "cursor")
    }

    assert rows_by_backend["claude"], "the roadmap routing rows disappeared"
    assert rows_by_backend["claude"] == rows_by_backend["codex"] == rows_by_backend["cursor"]


def test_removed_backlog_441_entry_is_absent_and_not_cross_referenced_as_open() -> None:
    """#441 shipped, so BACKLOG.md carries neither its heading nor a reference that treats it as pending."""
    backlog = _BACKLOG.read_text(encoding="utf-8")

    assert "**#441 —" not in backlog
    assert "#441" not in backlog


def _stack_section(doc: str) -> str:
    start = doc.index("### Stack rows")
    return doc[start : doc.index("## `03-components.md`", start)]


def _constraints_example(doc: str):
    return next(
        art
        for art, gates in (_parse(b) for b in _artifact_example_blocks(doc))
        if gates is run_constraints_gates
    )


def test_stack_example_records_a_chosen_and_an_open_concern(doc: str) -> None:
    stack = _constraints_example(doc).stack
    assert stack is not None
    assert any(row.choice and not row.open for row in stack), "no chosen stack row"
    assert any(row.open and row.choice is None for row in stack), "no open stack row"


def test_stack_schema_documents_the_complete_concern_vocabulary(doc: str) -> None:
    start = doc.index("**Stack concerns**")
    section = doc[start : doc.index("**Store categories and sharing models**", start)]
    printed = set(re.findall(r"^\| `([a-z-]+)` \|", section, re.M))
    assert printed == set(STACK_CONCERNS), "doc vocabulary differs from STACK_CONCERNS"
    assert all(concern in _stack_section(doc) for concern in STACK_CONCERNS)


def test_every_stack_gate_the_code_ships_is_named_in_the_doc(doc: str) -> None:
    kinds = {
        value
        for name, value in vars(roadmap_gates).items()
        if name.startswith("VIOLATION_") and "STACK" in name
    }
    gates = {
        name for name in vars(roadmap_gates) if name.startswith("check_") and "stack" in name
    }
    assert kinds and gates, "no stack gate found in roadmap_gates; the guard would pass vacuously"
    section = _stack_section(doc)
    assert all(f"`{kind}`" in section for kind in kinds), sorted(kinds)
    assert all(f"`{gate}`" in section for gate in gates), sorted(gates)
    named = set(re.findall(r"`(check_\w*stack\w*)`", doc))
    assert named <= gates, f"doc names a stack gate the code lacks: {sorted(named - gates)}"


def test_doc_states_absent_stack_is_not_recorded_and_empty_stack_is_recorded(
    doc: str,
) -> None:
    section = _stack_section(doc)
    assert "Stack not recorded" in section
    assert "Recorded, and empty" in section

    example = next(
        b for b in _artifact_example_blocks(doc) if "\nstack:" in b.split("---", 2)[1]
    )
    _, frontmatter, rest = example.split("---", 2)
    keyless = re.sub(r"\nstack:\n(?:[- ] .*\n)+", "\n", frontmatter)
    assert keyless != frontmatter, "the example's stack block was not removed"
    assert parse_constraints_artifact(f"---{keyless}---{rest}").stack is None
    emptied = f"---{keyless}stack: []\n---{rest}"
    assert parse_constraints_artifact(emptied).stack == ()


def test_backlog_461_stays_plan_authored_until_full_shipment() -> None:
    """Removal of #461 belongs to full shipment; update this test when that lands."""
    backlog = _BACKLOG.read_text(encoding="utf-8")
    heading = next(
        (line for line in backlog.splitlines() if line.startswith("**#461 ")), None
    )
    assert heading is not None and "PLAN-AUTHORED" in heading, heading
    assert (_REPO_ROOT / "docs/implementation-plans/archive/2-roadmap-stack-layer.md").is_file()
    assert (_REPO_ROOT / "plan-seeds/archive/roadmap-stack-layer.replaced.md").is_file()
