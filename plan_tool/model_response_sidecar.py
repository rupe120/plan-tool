"""Best-effort storage for rejected model-response sidecars."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from plan_tool.fileio import atomic_write_bytes


class ModelResponseSidecarOutcome(str, Enum):
    """The availability state of a rejected model response."""

    WRITTEN = "written"
    NO_RESPONSE = "no-response"
    NOT_RETAINED = "not-retained"
    WRITE_FAILED = "write-failed"


@dataclass(frozen=True)
class ModelResponseSidecarResult:
    """The outcome of one best-effort rejected-response sidecar write."""

    outcome: ModelResponseSidecarOutcome
    path: Path | None = None
    digest: str | None = None
    response_bytes: int | None = None


def store_model_response_sidecar(
    *,
    repo_root: Path,
    producer_slug: str,
    receipt_identity: str,
    raw_response: str | None,
    retain_response: bool = True,
) -> ModelResponseSidecarResult:
    """Store one retained response beneath the producer's sidecar directory.

    ``receipt_identity`` belongs to the producer and must be unique for each
    reply it retains. The leaf reports storage failures so producers can keep
    their own retry and receipt behavior best-effort. ``digest``/
    ``response_bytes`` are always populated once a response exists — even
    when it isn't retained or the write fails — so a caller never needs its
    own copy of this encode-then-hash to derive the receipt's response
    identity.
    """
    if raw_response is None:
        return ModelResponseSidecarResult(ModelResponseSidecarOutcome.NO_RESPONSE)

    payload = raw_response.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    response_bytes = len(payload)
    if not retain_response:
        return ModelResponseSidecarResult(
            ModelResponseSidecarOutcome.NOT_RETAINED,
            digest=digest,
            response_bytes=response_bytes,
        )

    destination = (
        repo_root
        / ".plan-tool"
        / "parse-failures"
        / producer_slug
        / f"{receipt_identity}.txt"
    )
    try:
        atomic_write_bytes(destination, payload)
    except OSError:
        return ModelResponseSidecarResult(
            ModelResponseSidecarOutcome.WRITE_FAILED,
            digest=digest,
            response_bytes=response_bytes,
        )
    return ModelResponseSidecarResult(
        ModelResponseSidecarOutcome.WRITTEN,
        path=destination,
        digest=digest,
        response_bytes=response_bytes,
    )
