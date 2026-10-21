"""Small JSON-projection primitives shared by roadmap contracts."""

from __future__ import annotations

from enum import Enum
from typing import Any


def unwrap_enum_value(value: Any) -> Any:
    """Return an enum's wire value, leaving every other value unchanged."""
    return value.value if isinstance(value, Enum) else value
