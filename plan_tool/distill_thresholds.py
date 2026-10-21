"""Distill gating / advisory thresholds (bytes).

A stdlib-only leaf so any module — including the ``create`` orchestrator that
gates on these and read-only surfaces that render them — can import them
without pulling in heavy dependencies.

There is no hard cap on the seed. Direct-ready file-backed sources always take
a raw single-versus-split assessment, regardless of size. These thresholds
only govern the conventional inline distill path.

  * below ``DISTILL_SKIP_BELOW_BYTES``: an already-canonical seed has nothing to
    reorganize, so inline distillation is skipped for compatibility.
  * above ``DISTILL_ADVISE_ABOVE_BYTES``: print a one-line advisory that big
    inline seeds often describe multiple plans, then use conventional
    preparation anyway.
"""

from __future__ import annotations

DISTILL_SKIP_BELOW_BYTES = 16384
DISTILL_ADVISE_ABOVE_BYTES = 262144
