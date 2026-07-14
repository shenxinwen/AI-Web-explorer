from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ai_web_explorer.safesym_bridge.capability_graph import Evidence


@dataclass(frozen=True)
class WebKobeObservation:
    url: str
    url_pattern: str
    browser_title: str
    heading: str | None = None
    web_state_id: str | None = None
    llm_title: str | None = None
    state_indicators: dict[str, Any] = field(default_factory=dict)
    interactables: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)


def _url_pattern(url: str) -> str:
    parts = urlsplit(url)
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def async_or_sync_title(page) -> str:
    title = page.title
    return title() if callable(title) else str(title)


def _optional_inner_text(page, selector: str) -> str | None:
    try:
        locator = page.locator(selector)
        if locator.count() == 0:
            return None
        return locator.first.inner_text().strip()
    except Exception:
        return None


def observe_web_kobe_page(
    page,
    *,
    web_state_id: str | None = None,
    llm_title: str | None = None,
) -> WebKobeObservation:
    url = str(page.url)
    heading = _optional_inner_text(page, "h1")
    return WebKobeObservation(
        url=url,
        url_pattern=_url_pattern(url),
        browser_title=async_or_sync_title(page),
        heading=heading,
        web_state_id=web_state_id,
        llm_title=llm_title,
        evidence=[Evidence(source="browser", url=url, confidence=1.0)],
    )
