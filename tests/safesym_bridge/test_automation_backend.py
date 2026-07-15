from __future__ import annotations

from typing import get_origin

from ai_web_explorer.safesym_bridge.automation_backend import (
    AutomationBackend,
    InteractableRecord,
)


def test_automation_backend_protocol_is_importable() -> None:
    assert AutomationBackend.__name__ == "AutomationBackend"
    assert get_origin(InteractableRecord) is dict
