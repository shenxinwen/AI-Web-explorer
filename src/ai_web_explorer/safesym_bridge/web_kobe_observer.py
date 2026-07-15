from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ai_web_explorer.grounded_web.capability_graph import Evidence
from ai_web_explorer.grounded_web.state_signature import (
    coerce_state_value,
    slug_identifier,
)


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


def _data_state_indicators(page) -> dict[str, Any]:
    indicators: dict[str, Any] = {}
    try:
        locator = page.locator("[data-state]")
        count = locator.count()
    except Exception:
        return indicators

    for index in range(count):
        element = locator.nth(index)
        try:
            raw_key = element.get_attribute("data-state")
        except Exception:
            raw_key = None
        if not raw_key:
            continue

        key = slug_identifier(raw_key, fallback="state")
        try:
            text = element.inner_text().strip()
        except Exception:
            text = ""
        if text:
            indicators[key] = coerce_state_value(text)

        try:
            indicators[f"{key}_visible"] = element.is_visible()
        except Exception:
            pass

    return indicators


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
        state_indicators=_data_state_indicators(page),
        evidence=[Evidence(source="browser", url=url, confidence=1.0)],
    )
