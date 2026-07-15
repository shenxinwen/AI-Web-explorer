"""Public API for the DOM-grounded web exploration mainline.

This package is the stable import surface for the current generic exploration
direction. The underlying implementation still lives in `safesym_bridge`
during the migration, but new code should import grounded exploration building
blocks from here.
"""

from ai_web_explorer.grounded_web.automation_backend import AutomationBackend
from ai_web_explorer.grounded_web.controller import (
    WebKobeExplorationController,
    WebKobeExplorationResult,
    WebKobeExplorationSummary,
)
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.graph import BrowserAction, WebKobeGraph
from ai_web_explorer.grounded_web.playwright_backend import WebKobePlaywrightAdapter
from ai_web_explorer.grounded_web.simple_agent import SimpleGroundedWebAgent

__all__ = [
    "AutomationBackend",
    "BrowserAction",
    "SimpleGroundedWebAgent",
    "WebKobeExplorationController",
    "WebKobeExplorationResult",
    "WebKobeExplorationSummary",
    "WebKobeExplorer",
    "WebKobeGraph",
    "WebKobePlaywrightAdapter",
]
