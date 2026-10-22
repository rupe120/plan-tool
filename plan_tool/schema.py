"""Pydantic models for plan-tool's YAML frontmatter schema.

See PLAN_FORMAT.md for the human-facing spec.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PlanStatus(str, Enum):
    PLANNING = "planning"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"


class StepStatus(str, Enum):
    PENDING = "pending"
    CURRENT = "current"
    DONE = "done"


class StepScope(str, Enum):
    """Commitment axis — orthogonal to ``StepStatus`` (the lifecycle axis).

    ``status`` says where a step is in ``pending → current → done``;
    ``scope`` says whether the step is on the plan's critical path at all.
    A gated step stays ``status: pending`` while ``scope: deferred``, with
    ``status_note`` carrying the gate condition. Default ``committed``;
    elided on rewrite via ``exclude_defaults``.
    """

    COMMITTED = "committed"  # on the plan's critical path (default)
    DEFERRED = "deferred"    # parked behind a gate; may be promoted later
    WONT_DO = "wont_do"      # decided against; kept for the record


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskProfile(str, Enum):
    LOW = "low"
    STANDARD = "standard"
    HIGH = "high"


class Complexity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ChangeType(str, Enum):
    REFACTOR = "refactor"
    FEATURE = "feature"
    NON_CODE = "non-code"


class Feature(BaseModel):
    """A named capability that findings cluster around.

    A plan's ``features`` registry maps ``id → title``; a step's ``features``
    tag lists the ids it implements (ownership runs step → feature, so a
    ``split``/``merge`` renumber never dangles a tag). Types only — all
    semantic checks (unique/kebab ids, refs resolving to the registry) are
    advisory and live in ``review.validate_feature_refs``, never at parse
    time, so ``run``/``jira``/``detail`` stay inert on a malformed block.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    id: str
    title: str


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    id: int
    title: str
    # One-line note on why this step exists — the positive half of its scope
    # fence. Presence is advisory and checked in ``review.py``, never at parse
    # time: empty, placeholder, and multi-line values all parse. Elided on
    # rewrite when ``None``.
    intent: Optional[str] = None
    files: list[str] = Field(default_factory=list)
    creates: list[str] = Field(default_factory=list)
    allowed_mentions: list[str] = Field(default_factory=list)
    # Ids of the plan-level features this step implements. Advisory only —
    # no parse-time check that they resolve to ``Plan.features``; that lives
    # in ``review.validate_feature_refs``. Elided on rewrite when empty.
    features: list[str] = Field(default_factory=list)
    # Stable ids from the signed-off concept record that this step owns.
    # Membership is intentionally validated only by callers holding that record.
    # Empty by default and therefore elided from rewritten frontmatter.
    concept_ids: list[str] = Field(default_factory=list)
    complexity: Optional[Complexity] = None
    change_type: Optional[ChangeType] = None
    # Per-step override of the plan-level ``enforce_step_tests`` switch. ``None``
    # inherits the plan default; ``False`` exempts this step from the
    # test-authoring directive + gate (a genuinely test-less feature/refactor
    # step — pure wiring, or one whose test lands in a later step); ``True``
    # forces enforcement on for this step even when the plan default is off.
    # Elided on rewrite when ``None``.
    enforce_test_authoring: Optional[bool] = None
    gate: list[str] = Field(default_factory=list)
    depends_on: list[int] = Field(default_factory=list)
    # Optional per-edge consumption notes keyed by antecedent step id. Structural
    # check only: every key must appear in ``depends_on``; note content is never
    # validated at parse time. Empty by default and therefore elided from rewritten
    # frontmatter. Authoring paths omit silent edges (never ``{id: ""}``).
    depends_on_notes: dict[int, str] = Field(default_factory=dict)
    detail: Optional[str] = None
    status: StepStatus = StepStatus.PENDING
    # Commitment axis, orthogonal to ``status``. Default ``committed``;
    # elided on rewrite. A non-committed (parked) step is excluded from
    # runnable-step selection and from the completion tally.
    scope: StepScope = StepScope.COMMITTED
    status_note: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _normalize_step_description(cls, data: object) -> object:
        if not isinstance(data, Mapping) or "description" not in data:
            return data
        for key in ("description", "title"):
            if key in data and not isinstance(data[key], str):
                raise ValueError(f"step {key} must be a string")
        if "title" in data and data["description"] != data["title"]:
            raise ValueError(
                "step description and title conflict; supply only one key "
                "or give both exactly equal strings"
            )
        normalized = dict(data)
        normalized["title"] = normalized.pop("description")
        return normalized

    @model_validator(mode="after")
    def _scope_status_coherent(self) -> "Step":
        """A parked step's lifecycle must not have started or finished.

        ``deferred`` / ``wont_do`` are pre-decisions about scope; a step
        carrying one cannot also be ``current`` or ``done``. Promote it to
        ``committed`` before advancing its lifecycle.
        """
        if self.scope is not StepScope.COMMITTED and self.status in (
            StepStatus.CURRENT,
            StepStatus.DONE,
        ):
            raise ValueError(
                f"step {self.id}: scope={self.scope.value} is incompatible "
                f"with status={self.status.value} — a non-committed step "
                f"cannot be current or done; promote it to committed first"
            )
        return self

    @model_validator(mode="after")
    def _depends_on_notes_keys_valid(self) -> "Step":
        dep_set = set(self.depends_on)
        bad = sorted(k for k in self.depends_on_notes if k not in dep_set)
        if bad:
            raise ValueError(
                f"step {self.id} depends_on_notes references id(s) not in "
                f"depends_on: {bad}"
            )
        return self

    @property
    def all_files(self) -> list[str]:
        """The step's full file footprint: existing files it modifies
        (``files``) plus files it brings into existence (``creates``).

        Order-preserving and de-duplicated (``files`` first). This is the
        set consumed by footprint logic — drift-watching, the scope-guard
        allow-list, snapshots, and renderer/jira display — so a created
        file is protected and shown exactly like a modified one. Only
        file-*existence* validation distinguishes the two (a ``creates``
        path is expected to be absent until the step runs); everything
        else treats them uniformly.
        """
        seen: set[str] = set()
        merged: list[str] = []
        for f in (*self.files, *self.creates):
            if f not in seen:
                seen.add(f)
                merged.append(f)
        return merged

    @field_validator("gate")
    @classmethod
    def _gate_entries_nonempty(cls, value: list[str]) -> list[str]:
        """Reject empty or whitespace-only gate commands (preserve the rest
        verbatim — a command may carry significant quoted whitespace)."""
        for cmd in value:
            if not cmd.strip():
                raise ValueError("gate entries must be non-empty shell commands")
        return value

    @field_validator("concept_ids")
    @classmethod
    def _concept_ids_valid_and_unique(cls, value: list[str]) -> list[str]:
        """Validate stable concept-id shape and per-step uniqueness."""
        seen: set[str] = set()
        for concept_id in value:
            if re.fullmatch(r"[0-9a-f]{64}", concept_id) is None:
                raise ValueError(
                    "concept_ids entries must be lowercase 64-character SHA-256 hex ids"
                )
            if concept_id in seen:
                raise ValueError(
                    f"concept_ids must not repeat an id within one step: {concept_id}"
                )
            seen.add(concept_id)
        return value


# The only plan frontmatter version this build writes and accepts.
PLAN_FORMAT_VERSION = 1
SUPPORTED_PLAN_FORMAT_VERSIONS = frozenset({PLAN_FORMAT_VERSION})


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    # Raw parsing checks membership before model validation.
    format_version: int = PLAN_FORMAT_VERSION

    title: str
    # One-line note on why this plan exists — the positive half of its scope
    # fence. Presence is advisory and checked in ``review.py``, never at parse
    # time: empty, placeholder, and multi-line values all parse. Elided on
    # rewrite when ``None``.
    intent: Optional[str] = None
    status: PlanStatus
    priority: Priority
    # An explicit, reviewable declaration is a pair. Both fields remain
    # absent on legacy plans; use ``effective_risk_profile`` for policy.
    risk_profile: Optional[RiskProfile] = None
    risk_profile_rationale: Optional[str] = None
    lessons: Optional[str] = None
    test_command: Optional[str] = None
    # Opt-in switch for test enforcement on feature/refactor steps. When
    # true, ``run`` appends the test directive to those steps
    # *and* gates their advancement on a test file having been created or
    # modified during the step. Absent (``None``) means off — preserving
    # plans authored before the switch existed (backward compat); ``create``
    # writes it ``true`` on new plans so the feature is on by default.
    # Elided on rewrite when ``None`` (mirrors ``registered_by``).
    enforce_step_tests: Optional[bool] = None
    # Provenance marker for plans adopted into the manifest by an automated
    # pass rather than authored through ``create`` — e.g. ``sweep`` when the
    # sweep orphan-registration step finds an unregistered plan file on disk
    # and registers it. Lives in the plan file (not the manifest) so it
    # survives deregister/re-register cycles and is visible to any consumer
    # holding a parsed ``Plan``. Unset for plans registered the normal way;
    # elided on rewrite when ``None``.
    registered_by: Optional[str] = None
    # Repo-relative path to the seed file this plan was built from, set only
    # by ``create --from-existing`` when the input path resolves inside the
    # repo and stays readable at write time (BACKLOG #162). Lets a later
    # conceptual audit re-read the seed's scope contract; a plan created any
    # other way (blank skeleton, inline ``--from``, unresolvable path) leaves
    # this unset rather than record a guess. Elided on rewrite when ``None``.
    source_seed: Optional[str] = None
    # Optional registry mapping feature id → title. Types only — no
    # uniqueness/kebab/reference validation at parse time (see ``Feature``).
    # Empty default elides it on rewrite for plans that declare none.
    features: list[Feature] = Field(default_factory=list)
    steps: list[Step] = Field(min_length=1)

    @field_validator("risk_profile_rationale")
    @classmethod
    def _risk_profile_rationale_is_one_line(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("risk_profile_rationale must not be blank")
        if "\n" in value or "\r" in value:
            raise ValueError("risk_profile_rationale must be a single line")
        return value

    @model_validator(mode="after")
    def _risk_profile_declaration_is_complete(self) -> "Plan":
        profile_declared = "risk_profile" in self.model_fields_set
        rationale_declared = "risk_profile_rationale" in self.model_fields_set
        if profile_declared != rationale_declared:
            raise ValueError(
                "risk_profile and risk_profile_rationale must be declared together"
            )
        if profile_declared and (
            self.risk_profile is None or self.risk_profile_rationale is None
        ):
            raise ValueError(
                "risk_profile and risk_profile_rationale must not be explicitly null"
            )
        return self

    @property
    def effective_risk_profile(self) -> RiskProfile:
        """Return the declared tier or the standard policy for legacy plans."""
        return self.risk_profile or RiskProfile.STANDARD

    @property
    def done_count(self) -> int:
        """Number of steps with ``status: done`` (literal tally, for display)."""
        return sum(1 for s in self.steps if s.status == StepStatus.DONE)

    @property
    def committed_steps(self) -> list["Step"]:
        """Steps on the critical path (``scope: committed``).

        Deferred / wont_do steps are parked: they don't gate completion or
        surface as runnable work.
        """
        return [s for s in self.steps if s.scope is StepScope.COMMITTED]

    @property
    def all_steps_done(self) -> bool:
        """True when the plan has committed steps and every committed step is
        ``status: done``.

        Parked (``deferred`` / ``wont_do``) steps are ignored — a plan can
        complete with gated work parked.
        """
        committed = self.committed_steps
        return bool(committed) and all(
            s.status == StepStatus.DONE for s in committed
        )

    @model_validator(mode="after")
    def _validate_graph(self) -> "Plan":
        ids = [s.id for s in self.steps]
        seen: set[int] = set()
        dupes: set[int] = set()
        for i in ids:
            if i in seen:
                dupes.add(i)
            else:
                seen.add(i)
        if dupes:
            raise ValueError(f"duplicate step ids: {sorted(dupes)}")

        id_set = set(ids)
        for step in self.steps:
            unknown = [d for d in step.depends_on if d not in id_set]
            if unknown:
                raise ValueError(
                    f"step {step.id} depends_on references unknown id(s): {unknown}"
                )
            if step.id in step.depends_on:
                raise ValueError(f"step {step.id} cannot depend on itself")

        # A committed step that depends on a parked (deferred/wont_do) step can
        # never become runnable — its dependency will never reach ``done``.
        # Reject the deadlock: defer the dependent too, or promote the dep.
        scope_by_id = {s.id: s.scope for s in self.steps}
        for step in self.steps:
            if step.scope is not StepScope.COMMITTED:
                continue
            parked = [
                d
                for d in step.depends_on
                if scope_by_id[d] is not StepScope.COMMITTED
            ]
            if parked:
                raise ValueError(
                    f"committed step {step.id} depends_on parked "
                    f"(deferred/wont_do) step(s) {parked} — it can never become "
                    f"runnable; defer step {step.id} too, or promote its "
                    f"dependencies to committed"
                )

        self._check_cycles()

        current = [s.id for s in self.steps if s.status == StepStatus.CURRENT]
        if len(current) > 1:
            raise ValueError(
                f"more than one step has status=current: {current} "
                "(at most one step may be current at a time)"
            )

        return self

    def _check_cycles(self) -> None:
        graph: dict[int, list[int]] = {s.id: list(s.depends_on) for s in self.steps}
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[int, int] = {i: WHITE for i in graph}

        def visit(node: int, stack: list[int]) -> None:
            color[node] = GRAY
            stack.append(node)
            for nxt in graph[node]:
                if color[nxt] == GRAY:
                    cycle_start = stack.index(nxt)
                    cycle = stack[cycle_start:] + [nxt]
                    raise ValueError(
                        f"dependency cycle detected: {' -> '.join(map(str, cycle))}"
                    )
                if color[nxt] == WHITE:
                    visit(nxt, stack)
            stack.pop()
            color[node] = BLACK

        for node in graph:
            if color[node] == WHITE:
                visit(node, [])

    def step_by_id(self, step_id: int) -> Step:
        for s in self.steps:
            if s.id == step_id:
                return s
        raise KeyError(f"step {step_id} not in plan")

    def current_step(self) -> Optional[Step]:
        for s in self.steps:
            if s.status == StepStatus.CURRENT:
                return s
        return None

    def next_runnable_step(self) -> Optional[Step]:
        """Return the first committed, pending step whose dependencies are all
        done, or None.

        Parked (``deferred`` / ``wont_do``) steps are never runnable — the
        tool will not propose them until they're promoted to ``committed``.
        """
        done_ids = {s.id for s in self.steps if s.status == StepStatus.DONE}
        for s in self.steps:
            if s.scope is not StepScope.COMMITTED:
                continue
            if s.status != StepStatus.PENDING:
                continue
            if all(d in done_ids for d in s.depends_on):
                return s
        return None
