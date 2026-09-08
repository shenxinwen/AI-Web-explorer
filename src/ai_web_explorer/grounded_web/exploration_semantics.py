"""Completion-boundary configuration for web exploration."""

from __future__ import annotations

def validate_final_order_authorization(*, start_url: str, allowed: bool) -> bool:
    """Return whether final confirmation is enabled for this run."""

    del start_url
    return allowed


__all__ = ["validate_final_order_authorization"]
