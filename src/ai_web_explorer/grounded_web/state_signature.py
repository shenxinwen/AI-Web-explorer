from __future__ import annotations

import re
from typing import Any


def slug_identifier(value: str, *, fallback: str = "unknown") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or fallback


def coerce_state_value(value: str) -> Any:
    stripped = value.strip()
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    if re.fullmatch(r"-?\d+", stripped):
        return int(stripped)
    return stripped


def schema_delta(
    before: dict[str, Any],
    after: dict[str, Any],
) -> dict[str, Any] | None:
    delta: dict[str, Any] = {}
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value != after_value:
            delta[key] = {"before": before_value, "after": after_value}
    return delta or None
