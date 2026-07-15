from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_web_explorer.grounded_web.state_signature import (
    coerce_state_value,
    slug_identifier,
)


def _list_to_dict(items: list[Any]) -> list[dict[str, Any]]:
    return [
        item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in items
    ]


@dataclass(frozen=True)
class StructureEvidence:
    source: str
    selector: str | None = None
    text_sample: str | None = None
    url: str | None = None
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "selector": self.selector,
            "text_sample": self.text_sample,
            "url": self.url,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class PageInfo:
    url: str
    title: str
    page_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "page_id": self.page_id,
        }


@dataclass(frozen=True)
class RegionObservation:
    id: str
    role: str | None
    label: str | None
    visible: bool
    locator: str | None = None
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role,
            "label": self.label,
            "visible": self.visible,
            "locator": self.locator,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class ControlObservation:
    id: str
    kind: str
    role: str | None
    name: str
    locator: str
    locator_strategy: str
    enabled: bool
    visible: bool
    metadata: dict[str, str] = field(default_factory=dict)
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "role": self.role,
            "name": self.name,
            "locator": self.locator,
            "locator_strategy": self.locator_strategy,
            "enabled": self.enabled,
            "visible": self.visible,
            "metadata": dict(self.metadata),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class FormFieldObservation:
    id: str
    kind: str
    name: str
    locator: str
    value: str | bool | int | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "locator": self.locator,
            "value": self.value,
            "metadata": dict(self.metadata),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class FormObservation:
    id: str
    locator: str | None = None
    fields: list[FormFieldObservation] = field(default_factory=list)
    submit_controls: list[str] = field(default_factory=list)
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "locator": self.locator,
            "fields": _list_to_dict(self.fields),
            "submit_controls": list(self.submit_controls),
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class IndicatorObservation:
    id: str
    indicator_type: str
    key_hint: str
    value: str | bool | int
    visible: bool
    locator: str | None = None
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "indicator_type": self.indicator_type,
            "key_hint": self.key_hint,
            "value": self.value,
            "visible": self.visible,
            "locator": self.locator,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class RepeatedGroupObservation:
    id: str
    pattern_hint: str
    count: int
    representative_locator: str | None = None
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pattern_hint": self.pattern_hint,
            "count": self.count,
            "representative_locator": self.representative_locator,
            "evidence": _list_to_dict(self.evidence),
        }


@dataclass(frozen=True)
class PageStructureObservation:
    page: PageInfo
    regions: list[RegionObservation] = field(default_factory=list)
    controls: list[ControlObservation] = field(default_factory=list)
    forms: list[FormObservation] = field(default_factory=list)
    indicators: list[IndicatorObservation] = field(default_factory=list)
    repeated_groups: list[RepeatedGroupObservation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page.to_dict(),
            "regions": _list_to_dict(self.regions),
            "controls": _list_to_dict(self.controls),
            "forms": _list_to_dict(self.forms),
            "indicators": _list_to_dict(self.indicators),
            "repeated_groups": _list_to_dict(self.repeated_groups),
        }


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _evidence(
    *,
    source: str,
    selector: str | None,
    text_sample: object = None,
    url: str | None = None,
) -> list[StructureEvidence]:
    text = _clean(text_sample)
    return [
        StructureEvidence(
            source=source,
            selector=selector,
            text_sample=text[:120] if text else None,
            url=url,
        )
    ]


def page_structure_from_snapshot(
    page: PageInfo,
    snapshot: dict[str, Any],
) -> PageStructureObservation:
    regions = [
        RegionObservation(
            id=slug_identifier(_clean(item.get("id")), fallback=f"region_{index}"),
            role=_clean(item.get("role")) or None,
            label=_clean(item.get("label")) or None,
            visible=bool(item.get("visible")),
            locator=_clean(item.get("locator")) or None,
            evidence=_evidence(
                source="dom_region",
                selector=_clean(item.get("locator")) or None,
                text_sample=item.get("text"),
                url=page.url,
            ),
        )
        for index, item in enumerate(snapshot.get("regions") or [], start=1)
    ]

    controls = [
        ControlObservation(
            id=slug_identifier(_clean(item.get("id")), fallback=f"control_{index}"),
            kind=_clean(item.get("kind")) or "control",
            role=_clean(item.get("role")) or None,
            name=_clean(item.get("name")),
            locator=_clean(item.get("locator")),
            locator_strategy=_clean(item.get("locator_strategy")) or "unknown",
            enabled=bool(item.get("enabled")),
            visible=bool(item.get("visible")),
            metadata=dict(item.get("metadata") or {}),
            evidence=_evidence(
                source="dom_control",
                selector=_clean(item.get("locator")) or None,
                text_sample=item.get("name"),
                url=page.url,
            ),
        )
        for index, item in enumerate(snapshot.get("controls") or [], start=1)
        if _clean(item.get("locator"))
    ]

    forms = [
        FormObservation(
            id=slug_identifier(_clean(item.get("id")), fallback=f"form_{index}"),
            locator=_clean(item.get("locator")) or None,
            fields=[
                FormFieldObservation(
                    id=slug_identifier(
                        _clean(field.get("id")),
                        fallback=f"field_{field_index}",
                    ),
                    kind=_clean(field.get("kind")) or "input",
                    name=_clean(field.get("name")),
                    locator=_clean(field.get("locator")),
                    value=coerce_state_value(_clean(field.get("value"))),
                    metadata=dict(field.get("metadata") or {}),
                    evidence=_evidence(
                        source="dom_form_field",
                        selector=_clean(field.get("locator")) or None,
                        text_sample=field.get("name"),
                        url=page.url,
                    ),
                )
                for field_index, field in enumerate(
                    item.get("fields") or [],
                    start=1,
                )
                if _clean(field.get("locator"))
            ],
            submit_controls=list(item.get("submit_controls") or []),
            evidence=_evidence(
                source="dom_form",
                selector=_clean(item.get("locator")) or None,
                text_sample=item.get("id"),
                url=page.url,
            ),
        )
        for index, item in enumerate(snapshot.get("forms") or [], start=1)
    ]

    indicators = [
        IndicatorObservation(
            id=slug_identifier(_clean(item.get("id")), fallback=f"indicator_{index}"),
            indicator_type=_clean(item.get("indicator_type")) or "text",
            key_hint=_clean(item.get("key_hint")) or f"indicator_{index}",
            value=coerce_state_value(_clean(item.get("value"))),
            visible=bool(item.get("visible")),
            locator=_clean(item.get("locator")) or None,
            evidence=_evidence(
                source="dom_indicator",
                selector=_clean(item.get("locator")) or None,
                text_sample=item.get("text", item.get("value")),
                url=page.url,
            ),
        )
        for index, item in enumerate(snapshot.get("indicators") or [], start=1)
    ]

    repeated_groups = [
        RepeatedGroupObservation(
            id=slug_identifier(_clean(item.get("id")), fallback=f"group_{index}"),
            pattern_hint=_clean(item.get("pattern_hint")) or f"group_{index}",
            count=int(item.get("count") or 0),
            representative_locator=_clean(item.get("representative_locator")) or None,
            evidence=_evidence(
                source="dom_repeated_group",
                selector=_clean(item.get("representative_locator")) or None,
                text_sample=item.get("pattern_hint"),
                url=page.url,
            ),
        )
        for index, item in enumerate(snapshot.get("repeated_groups") or [], start=1)
    ]

    return PageStructureObservation(
        page=page,
        regions=regions,
        controls=controls,
        forms=forms,
        indicators=indicators,
        repeated_groups=repeated_groups,
    )


async def observe_page_structure(
    page,
    *,
    page_id: str | None = None,
) -> PageStructureObservation:
    title = await page.title()
    resolved_page = PageInfo(
        url=page.url,
        title=title,
        page_id=page_id or slug_identifier(title or page.url, fallback="page"),
    )
    snapshot = await page.locator("body").evaluate(
        """body => {
            const visible = element => {
                const rect = element.getBoundingClientRect();
                const style = window.getComputedStyle(element);
                return !!(rect.width && rect.height) &&
                    style.visibility !== "hidden" &&
                    style.display !== "none";
            };
            const textOf = element => (element.innerText || element.textContent || "").trim();
            const locatorFor = element => {
                if (element.id) return `#${element.id}`;
                const dataState = element.getAttribute("data-state");
                if (dataState) return `[data-state="${dataState}"]`;
                const dataTest = element.getAttribute("data-test");
                if (dataTest) return `[data-test="${dataTest}"]`;
                const dataAction = element.getAttribute("data-action");
                if (dataAction) return `[data-action="${dataAction}"]`;
                const role = element.getAttribute("role");
                if (role) return `[role="${role}"]`;
                return element.tagName.toLowerCase();
            };
            const controls = Array.from(
                body.querySelectorAll("button,a[href],input,textarea,select,[role='button'],[role='link'],[onclick],[data-test]")
            ).map((element, index) => {
                const tag = element.tagName.toLowerCase();
                const role = element.getAttribute("role") || "";
                const type = element.getAttribute("type") || "";
                const locator = locatorFor(element);
                const disabled = element.disabled || element.getAttribute("aria-disabled") === "true";
                const metadata = {
                    tag,
                    role,
                    type,
                    id: element.id || "",
                    "data-test": element.getAttribute("data-test") || "",
                    "data-action": element.getAttribute("data-action") || "",
                    "data-state": element.getAttribute("data-state") || "",
                    placeholder: element.getAttribute("placeholder") || "",
                    "aria-label": element.getAttribute("aria-label") || "",
                    title: element.getAttribute("title") || "",
                    href: element.getAttribute("href") || "",
                };
                return {
                    id: element.id || metadata["data-test"] || metadata["data-action"] || `control-${index + 1}`,
                    kind: tag === "a" ? "link" : tag === "select" ? "select" : tag === "textarea" ? "textarea" : tag === "input" ? "input" : "button",
                    role: role || (tag === "a" ? "link" : tag === "button" ? "button" : ""),
                    name: textOf(element) || element.getAttribute("aria-label") || element.getAttribute("placeholder") || element.value || "",
                    locator,
                    locator_strategy: locator.startsWith("#") ? "id" : locator.startsWith("[data-") ? "data-attribute" : "css-fallback",
                    enabled: !disabled,
                    visible: visible(element),
                    metadata: Object.fromEntries(Object.entries(metadata).filter(([, value]) => value)),
                };
            }).filter(control => control.visible);
            const regions = Array.from(
                body.querySelectorAll("main,section,dialog,[role='dialog'],[role='status'],[role='region'],[aria-live],[data-state]")
            ).map((element, index) => ({
                id: element.id || element.getAttribute("data-state") || element.getAttribute("role") || `region-${index + 1}`,
                role: element.getAttribute("role") || element.tagName.toLowerCase(),
                label: element.getAttribute("aria-label") || element.getAttribute("data-state") || "",
                visible: visible(element),
                locator: locatorFor(element),
                text: textOf(element),
            }));
            const indicators = Array.from(body.querySelectorAll("[data-state]")).map((element, index) => {
                const text = textOf(element);
                const numeric = text.match(/-?\\d+/);
                return {
                    id: element.getAttribute("data-state") || `indicator-${index + 1}`,
                    indicator_type: numeric ? "numeric" : "text",
                    key_hint: element.getAttribute("data-state") || `indicator-${index + 1}`,
                    value: numeric ? numeric[0] : text,
                    visible: visible(element),
                    locator: locatorFor(element),
                    text,
                };
            });
            const groupMap = new Map();
            Array.from(body.querySelectorAll("[data-entity-type]")).forEach(element => {
                const key = element.getAttribute("data-entity-type");
                if (!groupMap.has(key)) groupMap.set(key, []);
                groupMap.get(key).push(element);
            });
            const repeated_groups = Array.from(groupMap.entries()).map(([key, elements]) => ({
                id: key,
                pattern_hint: key,
                count: elements.length,
                representative_locator: `[data-entity-type="${key}"]`,
            }));
            const forms = Array.from(body.querySelectorAll("form")).map((form, index) => ({
                id: form.id || `form-${index + 1}`,
                locator: locatorFor(form),
                fields: Array.from(form.querySelectorAll("input,textarea,select")).map((field, fieldIndex) => ({
                    id: field.id || field.name || `field-${fieldIndex + 1}`,
                    kind: field.tagName.toLowerCase(),
                    name: field.getAttribute("aria-label") || field.getAttribute("placeholder") || field.name || field.id || "",
                    locator: locatorFor(field),
                    value: field.type === "checkbox" || field.type === "radio" ? field.checked : field.value || "",
                    metadata: Object.fromEntries(Object.entries({
                        type: field.getAttribute("type") || "",
                        name: field.name || "",
                        placeholder: field.getAttribute("placeholder") || "",
                        "aria-label": field.getAttribute("aria-label") || "",
                    }).filter(([, value]) => value)),
                })),
                submit_controls: Array.from(form.querySelectorAll("button,input[type='submit']")).map(control =>
                    control.getAttribute("data-action") || control.id || control.name || textOf(control)
                ).filter(value => value),
            }));
            return {regions, controls, forms, indicators, repeated_groups};
        }"""
    )
    return page_structure_from_snapshot(resolved_page, snapshot)
