from __future__ import annotations

from ai_web_explorer.grounded_web.playwright_backend import (
    WebKobePlaywrightAdapter as _GroundedWebKobePlaywrightAdapter,
)


class WebKobePlaywrightAdapter(_GroundedWebKobePlaywrightAdapter):
    """Compatibility import wrapper for SafeSym bridge callers.

    Generic code should import `ai_web_explorer.grounded_web.playwright_backend`.
    This wrapper keeps existing SafeSym bridge imports working without injecting
    benchmark-specific observers or action providers.
    """


__all__ = ["WebKobePlaywrightAdapter"]
