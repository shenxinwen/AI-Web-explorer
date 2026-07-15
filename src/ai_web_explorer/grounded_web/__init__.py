"""Public API for the DOM-grounded web exploration mainline.

This package is the stable import surface for the current generic exploration
direction. It owns browser-grounded observation, action extraction, execution
adapters, exploration control, and the Web-KOBE exploration graph. SafeSym/PDDL
conversion should consume this package's graph outputs from `safesym_bridge`,
not the other way around.
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
