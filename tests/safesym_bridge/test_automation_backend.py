from __future__ import annotations

from typing import get_origin

from ai_web_explorer.safesym_bridge.automation_backend import (
    AutomationBackend,
    InteractableRecord,
)
from ai_web_explorer.safesym_bridge.web_kobe_playwright_adapter import (
    WebKobePlaywrightAdapter,
)


def test_automation_backend_protocol_is_importable() -> None:
    assert AutomationBackend.__name__ == "AutomationBackend"
    assert get_origin(InteractableRecord) is dict


class _FakePage:
    url = "http://example.test/"


def test_playwright_adapter_satisfies_automation_backend_protocol() -> None:
    adapter = WebKobePlaywrightAdapter(_FakePage(), app_name="fixture")

    assert isinstance(adapter, AutomationBackend)
