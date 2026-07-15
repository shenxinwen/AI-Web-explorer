from __future__ import annotations

from dataclasses import dataclass, field


INTERACTABLE_SELECTOR = ", ".join(
    [
        "button",
        "a[href]",
        "input",
        "textarea",
        "select",
        '[role="button"]',
        '[role="link"]',
        "[onclick]",
        "[data-test]",
    ]
)


@dataclass(frozen=True)
class DomInteractableCandidate:
    id: str
    kind: str
    locator: str
    locator_strategy: str
    name: str
    visible: bool
    enabled: bool
    metadata: dict[str, str] = field(default_factory=dict)


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _kind_for(tag: str, role: str, input_type: str) -> str:
    tag = tag.lower()
    role = role.lower()
    input_type = input_type.lower()
    if role == "button" or tag == "button" or input_type in {"button", "submit"}:
        return "button"
    if role == "link" or tag == "a":
        return "link"
    if tag == "select":
        return "select"
    if tag == "textarea":
        return "textarea"
    if tag == "input":
        return "input"
    return "other"


def _candidate_name(element: dict[str, object]) -> str:
    for key in ("text", "aria_label", "value", "placeholder", "title", "data_test"):
        value = _clean(element.get(key))
        if value:
            return value
    return ""


def _metadata(element: dict[str, object]) -> dict[str, str]:
    key_map = {
        "tag": "tag",
        "role": "role",
        "type": "type",
        "id": "id",
        "class": "class",
        "data_test": "data-test",
        "placeholder": "placeholder",
        "aria_label": "aria-label",
        "title": "title",
        "href": "href",
        "candidate_id": "data-web-kobe-id",
    }
    data: dict[str, str] = {}
    for source, target in key_map.items():
        value = _clean(element.get(source))
        if value:
            data[target] = value
    option_values = element.get("option_values")
    if isinstance(option_values, list):
        cleaned_options = [_clean(option) for option in option_values if _clean(option)]
        if cleaned_options:
            data["option-values"] = ",".join(cleaned_options)
    return data


def _locator_for(element: dict[str, object], name: str) -> tuple[str, str]:
    element_id = _clean(element.get("id"))
    if element_id:
        return f"#{element_id}", "id"
    data_test = _clean(element.get("data_test"))
    if data_test:
        return f'[data-test="{data_test}"]', "data-test"
    aria_label = _clean(element.get("aria_label"))
    if aria_label:
        return f'[aria-label="{aria_label}"]', "aria-label"
    candidate_id = _clean(element.get("candidate_id"))
    if candidate_id:
        return f'[data-web-kobe-id="{candidate_id}"]', "generated-id"
    tag = _clean(element.get("tag")) or "html"
    return tag.lower(), "css-fallback"


def candidate_from_element(
    index: int,
    element: dict[str, object],
) -> DomInteractableCandidate:
    tag = _clean(element.get("tag")).lower()
    role = _clean(element.get("role"))
    input_type = _clean(element.get("type"))
    name = _candidate_name(element)
    locator, locator_strategy = _locator_for(element, name)
    return DomInteractableCandidate(
        id=f"dom_{index:03d}",
        kind=_kind_for(tag, role, input_type),
        locator=locator,
        locator_strategy=locator_strategy,
        name=name,
        visible=bool(element.get("visible")),
        enabled=bool(element.get("enabled")),
        metadata=_metadata(element),
    )


async def extract_dom_interactables(page) -> list[DomInteractableCandidate]:
    elements = await page.locator(INTERACTABLE_SELECTOR).evaluate_all(
        """elements => elements.map((element, index) => {
            const candidateId = `dom_${String(index + 1).padStart(3, "0")}`;
            element.setAttribute("data-web-kobe-id", candidateId);
            const rect = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);
            const tag = element.tagName.toLowerCase();
            const inputType = element.getAttribute("type") || "";
            const disabled = element.disabled || element.getAttribute("aria-disabled") === "true";
            const className = typeof element.className === "string"
                ? element.className
                : element.getAttribute("class") || "";
            return {
                tag,
                role: element.getAttribute("role") || "",
                type: inputType,
                id: element.id || "",
                class: className,
                data_test: element.getAttribute("data-test") || "",
                aria_label: element.getAttribute("aria-label") || "",
                placeholder: element.getAttribute("placeholder") || "",
                title: element.getAttribute("title") || "",
                href: element.getAttribute("href") || "",
                candidate_id: candidateId,
                option_values: Array.from(element.options || [])
                    .map(option => option.value || "")
                    .filter(value => value.trim()),
                value: element.value || "",
                text: (element.innerText || element.textContent || "").trim(),
                visible: !!(rect.width && rect.height) &&
                    style.visibility !== "hidden" &&
                    style.display !== "none",
                enabled: !disabled,
            };
        })"""
    )
    candidates = [
        candidate_from_element(index, element)
        for index, element in enumerate(elements, start=1)
    ]
    return [
        candidate for candidate in candidates if candidate.visible and candidate.enabled
    ]
