# Observation-to-State Pipeline v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Subagent-driven execution is intentionally not the default for this project because the user requested single-agent, token-saving work unless explicitly allowed.

**Goal:** Build a generic, evidence-backed pipeline from browser/DOM structure to typed state facts, state signatures, and typed deltas for Web-KOBE graph recording.

**Architecture:** Add focused `grounded_web` modules for structure observation, fact derivation, and typed deltas. Keep `StateSnapshot.signature` as the compatibility bridge for existing graph code, while adding typed fact/evidence machinery that can later feed LLM/VLM and PDDL projection. Do not move generic observation logic into `safesym_bridge`.

**Tech Stack:** Python 3.11+, dataclasses, pytest/anyio, Playwright async API, existing `grounded_web` models and Web-KOBE graph types.

## Global Constraints

- Do not introduce LLM/VLM action selection.
- Do not let any model invent selectors or decide observed fact truth.
- Do not introduce new runtime dependencies.
- Do not add generic observer rules for `cart`, `product`, `checkout`, `order`, `payment`, or other app-domain concepts.
- Preserve domain words only as page-provided hints or evidence.
- Validate on at least two fixtures from different domains.
- Keep SauceDemo-specific interpretation in `safesym_bridge` or app profiles.
- No new generic code in `grounded_web` may import `safesym_bridge`.
- Preserve existing `tests/safesym_bridge` regressions.
- Do not use subagents unless the user explicitly permits them.

---

## File Structure

- Create `src/ai_web_explorer/grounded_web/structure.py`
  - Owns generic page-structure dataclasses.
  - Owns pure conversion from raw DOM snapshot dictionaries to `PageStructureObservation`.
  - Owns Playwright-backed `observe_page_structure(page, page_id=None)`.

- Create `src/ai_web_explorer/grounded_web/state_facts.py`
  - Owns `AbstractStateFact`.
  - Derives typed facts from `PageStructureObservation`.
  - Builds a compatibility `dict[str, Any]` state signature from identity-relevant facts.

- Create `src/ai_web_explorer/grounded_web/typed_delta.py`
  - Owns typed delta inference from before/after fact lists or signatures.
  - Converts typed deltas to existing `ObservedDelta` records for Web-KOBE graph compatibility.

- Modify `src/ai_web_explorer/grounded_web/playwright_backend.py`
  - Use `observe_page_structure()` in generic `observe_state()`.
  - Derive typed facts and compatibility signature from the structure observation.
  - Store `last_structure_observation` and `last_state_facts` for debugging/future LLM use.
  - Remove generic hardcoded `#cart-count` / `cart_nonempty` fallback from the generic path.

- Modify `src/ai_web_explorer/grounded_web/explorer.py`
  - Use typed delta conversion where possible.
  - Keep existing `schema_delta` field for compatibility.

- Add `tests/fixtures/local_form_search/index.html`
  - Non-ecommerce fixture to guard against overfitting.

- Add/modify tests:
  - Create `tests/safesym_bridge/test_page_structure_observer.py`
  - Create `tests/safesym_bridge/test_state_facts.py`
  - Create `tests/safesym_bridge/test_typed_delta.py`
  - Modify `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`
  - Modify `tests/safesym_bridge/test_web_kobe_grounded_exploration.py`
  - Add `tests/safesym_bridge/test_observation_to_state_form_search.py`

---

## Execution Policy

Implement one task at a time. Each task ends with a focused test run and a commit.

Use this implementation skill when executing this plan:

```text
superpowers:executing-plans
```

At execution time, use `superpowers:using-git-worktrees` before implementation so the feature work is isolated from `main`.

---

### Task 1: Add generic page-structure data models

**Files:**
- Create: `src/ai_web_explorer/grounded_web/structure.py`
- Create: `tests/safesym_bridge/test_page_structure_observer.py`

**Interfaces:**
- Produces:
  - `StructureEvidence(source: str, selector: str | None = None, text_sample: str | None = None, url: str | None = None, confidence: float = 1.0)`
  - `PageInfo(url: str, title: str, page_id: str)`
  - `RegionObservation(id: str, role: str | None, label: str | None, visible: bool, locator: str | None, evidence: list[StructureEvidence])`
  - `ControlObservation(id: str, kind: str, role: str | None, name: str, locator: str, locator_strategy: str, enabled: bool, visible: bool, metadata: dict[str, str], evidence: list[StructureEvidence])`
  - `FormFieldObservation(id: str, kind: str, name: str, locator: str, value: str | bool | int | None, metadata: dict[str, str], evidence: list[StructureEvidence])`
  - `FormObservation(id: str, locator: str | None, fields: list[FormFieldObservation], submit_controls: list[str], evidence: list[StructureEvidence])`
  - `IndicatorObservation(id: str, indicator_type: str, key_hint: str, value: str | bool | int, visible: bool, locator: str | None, evidence: list[StructureEvidence])`
  - `RepeatedGroupObservation(id: str, pattern_hint: str, count: int, representative_locator: str | None, evidence: list[StructureEvidence])`
  - `PageStructureObservation(page: PageInfo, regions: list[RegionObservation], controls: list[ControlObservation], forms: list[FormObservation], indicators: list[IndicatorObservation], repeated_groups: list[RepeatedGroupObservation])`

- [ ] **Step 1: Write failing dataclass serialization tests**

Create `tests/safesym_bridge/test_page_structure_observer.py`:

```python
from ai_web_explorer.grounded_web.structure import (
    ControlObservation,
    IndicatorObservation,
    PageInfo,
    PageStructureObservation,
    RegionObservation,
    RepeatedGroupObservation,
    StructureEvidence,
)


def test_page_structure_observation_serializes_generic_structure():
    evidence = [
        StructureEvidence(
            source="dom",
            selector='[data-state="cart-count"]',
            text_sample="1",
            url="https://example.test/shop",
        )
    ]
    observation = PageStructureObservation(
        page=PageInfo(
            url="https://example.test/shop",
            title="Fixture Shop",
            page_id="fixture_shop",
        ),
        regions=[
            RegionObservation(
                id="region_cart_panel",
                role="region",
                label="Cart panel",
                visible=True,
                locator='[data-state="cart-panel"]',
                evidence=evidence,
            )
        ],
        controls=[
            ControlObservation(
                id="control_add",
                kind="button",
                role="button",
                name="Add to cart",
                locator='[data-action="add-to-cart"]',
                locator_strategy="data-action",
                enabled=True,
                visible=True,
                metadata={"data-action": "add-to-cart"},
                evidence=evidence,
            )
        ],
        indicators=[
            IndicatorObservation(
                id="indicator_cart_count",
                indicator_type="numeric",
                key_hint="cart-count",
                value=1,
                visible=True,
                locator='[data-state="cart-count"]',
                evidence=evidence,
            )
        ],
        repeated_groups=[
            RepeatedGroupObservation(
                id="group_product_card",
                pattern_hint="product-card",
                count=2,
                representative_locator='[data-entity-type="product"]',
                evidence=evidence,
            )
        ],
    )

    assert observation.to_dict()["page"]["page_id"] == "fixture_shop"
    assert observation.to_dict()["controls"][0]["kind"] == "button"
    assert observation.to_dict()["indicators"][0]["indicator_type"] == "numeric"
    assert observation.to_dict()["repeated_groups"][0]["count"] == 2
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_page_structure_observer.py::test_page_structure_observation_serializes_generic_structure -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.grounded_web.structure'`.

- [ ] **Step 3: Add structure dataclasses**

Create `src/ai_web_explorer/grounded_web/structure.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
```

- [ ] **Step 4: Run Task 1 test**

Run:

```bash
python -m pytest tests/safesym_bridge/test_page_structure_observer.py::test_page_structure_observation_serializes_generic_structure -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/ai_web_explorer/grounded_web/structure.py tests/safesym_bridge/test_page_structure_observer.py
git commit -m "feat: add page structure observation models"
```

---

### Task 2: Build PageStructureObservation from generic DOM snapshots

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/structure.py`
- Test: `tests/safesym_bridge/test_page_structure_observer.py`

**Interfaces:**
- Consumes:
  - Raw DOM snapshot dictionaries from Playwright evaluation.
  - Existing `slug_identifier(value: str, fallback: str = "unknown") -> str`.
  - Existing `coerce_state_value(value: str) -> Any`.
- Produces:
  - `page_structure_from_snapshot(page: PageInfo, snapshot: dict[str, Any]) -> PageStructureObservation`
  - `observe_page_structure(page, *, page_id: str | None = None) -> PageStructureObservation`

- [ ] **Step 1: Add failing pure snapshot conversion test**

Append this test to `tests/safesym_bridge/test_page_structure_observer.py`:

```python
from ai_web_explorer.grounded_web.structure import page_structure_from_snapshot


def test_page_structure_from_snapshot_extracts_generic_indicators_and_groups():
    observation = page_structure_from_snapshot(
        PageInfo(
            url="https://example.test/shop",
            title="Fixture Shop",
            page_id="fixture_shop",
        ),
        {
            "regions": [
                {
                    "id": "cart-panel",
                    "role": "region",
                    "label": "Cart panel",
                    "visible": False,
                    "locator": '[data-state="cart-panel"]',
                    "text": "Cart contains 0 items.",
                }
            ],
            "controls": [
                {
                    "id": "add-button",
                    "kind": "button",
                    "role": "button",
                    "name": "Add to cart",
                    "locator": '[data-action="add-to-cart"]',
                    "locator_strategy": "data-action",
                    "enabled": True,
                    "visible": True,
                    "metadata": {"data-action": "add-to-cart"},
                }
            ],
            "indicators": [
                {
                    "id": "cart-count",
                    "indicator_type": "numeric",
                    "key_hint": "cart-count",
                    "value": "1",
                    "visible": True,
                    "locator": '[data-state="cart-count"]',
                    "text": "1",
                }
            ],
            "repeated_groups": [
                {
                    "id": "product",
                    "pattern_hint": "product",
                    "count": 2,
                    "representative_locator": '[data-entity-type="product"]',
                }
            ],
        },
    )

    assert observation.indicators[0].value == 1
    assert observation.indicators[0].key_hint == "cart-count"
    assert observation.repeated_groups[0].count == 2
    assert observation.controls[0].metadata == {"data-action": "add-to-cart"}
```

- [ ] **Step 2: Run conversion test and verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_page_structure_observer.py::test_page_structure_from_snapshot_extracts_generic_indicators_and_groups -q
```

Expected: FAIL with `ImportError` for `page_structure_from_snapshot`.

- [ ] **Step 3: Implement snapshot conversion**

Append these helpers to `src/ai_web_explorer/grounded_web/structure.py`:

```python
from ai_web_explorer.grounded_web.state_signature import (
    coerce_state_value,
    slug_identifier,
)


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
            fields=[],
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
```

- [ ] **Step 4: Run conversion tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_page_structure_observer.py -q
```

Expected: PASS.

- [ ] **Step 5: Add failing async fake-page test**

Append this test to `tests/safesym_bridge/test_page_structure_observer.py`:

```python
from ai_web_explorer.grounded_web.structure import observe_page_structure


class FakeStructureLocator:
    async def evaluate(self, script):
        return {
            "regions": [
                {
                    "id": "status",
                    "role": "status",
                    "label": "Status",
                    "visible": True,
                    "locator": '[role="status"]',
                    "text": "Ready",
                }
            ],
            "controls": [],
            "forms": [],
            "indicators": [
                {
                    "id": "result-count",
                    "indicator_type": "numeric",
                    "key_hint": "result-count",
                    "value": "3",
                    "visible": True,
                    "locator": '[data-state="result-count"]',
                    "text": "3",
                }
            ],
            "repeated_groups": [],
        }


class FakeStructurePage:
    url = "https://example.test/search"

    async def title(self):
        return "Search Fixture"

    def locator(self, selector):
        assert selector == "body"
        return FakeStructureLocator()


@pytest.mark.anyio
async def test_observe_page_structure_uses_browser_snapshot():
    observation = await observe_page_structure(
        FakeStructurePage(),
        page_id="search_fixture",
    )

    assert observation.page.page_id == "search_fixture"
    assert observation.indicators[0].key_hint == "result-count"
    assert observation.indicators[0].value == 3
```

Add `import pytest` at the top of the file if it is not already present.

- [ ] **Step 6: Run async test and verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_page_structure_observer.py::test_observe_page_structure_uses_browser_snapshot -q
```

Expected: FAIL with `ImportError` for `observe_page_structure`.

- [ ] **Step 7: Implement Playwright-backed page structure observation**

Append this function to `src/ai_web_explorer/grounded_web/structure.py`:

```python
async def observe_page_structure(page, *, page_id: str | None = None) -> PageStructureObservation:
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
            return {regions, controls, forms: [], indicators, repeated_groups};
        }"""
    )
    return page_structure_from_snapshot(resolved_page, snapshot)
```

- [ ] **Step 8: Run page structure tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_page_structure_observer.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit Task 2**

Run:

```bash
git add src/ai_web_explorer/grounded_web/structure.py tests/safesym_bridge/test_page_structure_observer.py
git commit -m "feat: observe generic page structure"
```

---

### Task 3: Derive typed state facts and compatibility state signatures

**Files:**
- Create: `src/ai_web_explorer/grounded_web/state_facts.py`
- Create: `tests/safesym_bridge/test_state_facts.py`

**Interfaces:**
- Consumes:
  - `PageStructureObservation`
  - `StructureEvidence`
- Produces:
  - `AbstractStateFact`
  - `facts_from_structure(observation: PageStructureObservation) -> list[AbstractStateFact]`
  - `state_signature_from_facts(facts: list[AbstractStateFact]) -> dict[str, Any]`

- [ ] **Step 1: Write failing fact derivation tests**

Create `tests/safesym_bridge/test_state_facts.py`:

```python
from ai_web_explorer.grounded_web.state_facts import (
    facts_from_structure,
    state_signature_from_facts,
)
from ai_web_explorer.grounded_web.structure import (
    IndicatorObservation,
    PageInfo,
    PageStructureObservation,
    RegionObservation,
    RepeatedGroupObservation,
    StructureEvidence,
)


def test_facts_from_structure_derives_typed_identity_facts():
    evidence = [StructureEvidence(source="dom", selector='[data-state="count"]')]
    observation = PageStructureObservation(
        page=PageInfo(
            url="https://example.test/search?q=abc",
            title="Search",
            page_id="search",
        ),
        regions=[
            RegionObservation(
                id="results",
                role="status",
                label="Results",
                visible=True,
                locator='[role="status"]',
                evidence=evidence,
            )
        ],
        indicators=[
            IndicatorObservation(
                id="result-count",
                indicator_type="numeric",
                key_hint="result-count",
                value=3,
                visible=True,
                locator='[data-state="result-count"]',
                evidence=evidence,
            )
        ],
        repeated_groups=[
            RepeatedGroupObservation(
                id="result-row",
                pattern_hint="result-row",
                count=3,
                representative_locator='[data-entity-type="result-row"]',
                evidence=evidence,
            )
        ],
    )

    facts = facts_from_structure(observation)
    signature = state_signature_from_facts(facts)

    assert signature["url_path"] == "/search"
    assert signature["region_results_visible"] is True
    assert signature["result_count"] == 3
    assert signature["result_row_count"] == 3
    assert {fact.fact_type for fact in facts} >= {
        "navigation",
        "visibility",
        "numeric",
        "repeated_entity_count",
    }
```

- [ ] **Step 2: Run fact derivation test and verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_state_facts.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.grounded_web.state_facts'`.

- [ ] **Step 3: Implement state fact model and derivation**

Create `src/ai_web_explorer/grounded_web/state_facts.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from ai_web_explorer.grounded_web.state_signature import slug_identifier
from ai_web_explorer.grounded_web.structure import (
    PageStructureObservation,
    StructureEvidence,
)


@dataclass(frozen=True)
class AbstractStateFact:
    fact_id: str
    fact_type: str
    value: str | bool | int
    identity_role: str
    source_ref: str
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "fact_type": self.fact_type,
            "value": self.value,
            "identity_role": self.identity_role,
            "source_ref": self.source_ref,
            "evidence": [
                item.to_dict() if hasattr(item, "to_dict") else dict(item)
                for item in self.evidence
            ],
        }


def _fact_key(prefix: str, value: str) -> str:
    return f"{prefix}_{slug_identifier(value, fallback='unknown')}"


def facts_from_structure(
    observation: PageStructureObservation,
) -> list[AbstractStateFact]:
    facts: list[AbstractStateFact] = []
    path = urlparse(observation.page.url).path or "/"
    facts.append(
        AbstractStateFact(
            fact_id="url_path",
            fact_type="navigation",
            value=path,
            identity_role="identity",
            source_ref="page.url",
            evidence=[
                StructureEvidence(
                    source="browser_location",
                    url=observation.page.url,
                    text_sample=path,
                )
            ],
        )
    )

    for region in observation.regions:
        facts.append(
            AbstractStateFact(
                fact_id=slug_identifier(
                    f"{region.id}_visible",
                    fallback="region_visible",
                ),
                fact_type="visibility",
                value=region.visible,
                identity_role="identity",
                source_ref=region.id,
                evidence=region.evidence,
            )
        )

    for indicator in observation.indicators:
        key = slug_identifier(indicator.key_hint or indicator.id, fallback=indicator.id)
        facts.append(
            AbstractStateFact(
                fact_id=key,
                fact_type="numeric" if isinstance(indicator.value, int) else "visibility",
                value=indicator.value,
                identity_role="identity",
                source_ref=indicator.id,
                evidence=indicator.evidence,
            )
        )
        facts.append(
            AbstractStateFact(
                fact_id=f"{key}_visible",
                fact_type="visibility",
                value=indicator.visible,
                identity_role="identity",
                source_ref=indicator.id,
                evidence=indicator.evidence,
            )
        )

    for group in observation.repeated_groups:
        facts.append(
            AbstractStateFact(
                fact_id=_fact_key("", f"{group.pattern_hint}_count").strip("_"),
                fact_type="repeated_entity_count",
                value=group.count,
                identity_role="identity",
                source_ref=group.id,
                evidence=group.evidence,
            )
        )

    for control in observation.controls:
        if control.visible:
            facts.append(
                AbstractStateFact(
                    fact_id=_fact_key("control", f"{control.id}_enabled"),
                    fact_type="control_availability",
                    value=control.enabled,
                    identity_role="context",
                    source_ref=control.id,
                    evidence=control.evidence,
                )
            )

    return facts


def state_signature_from_facts(
    facts: list[AbstractStateFact],
) -> dict[str, Any]:
    return {
        fact.fact_id: fact.value
        for fact in facts
        if fact.identity_role == "identity"
    }
```

- [ ] **Step 4: Run state fact tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_state_facts.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add src/ai_web_explorer/grounded_web/state_facts.py tests/safesym_bridge/test_state_facts.py
git commit -m "feat: derive typed state facts"
```

---

### Task 4: Add typed delta inference and Web-KOBE delta conversion

**Files:**
- Create: `src/ai_web_explorer/grounded_web/typed_delta.py`
- Create: `tests/safesym_bridge/test_typed_delta.py`
- Modify: `src/ai_web_explorer/grounded_web/explorer.py`
- Modify: `tests/safesym_bridge/test_web_kobe_explorer.py`

**Interfaces:**
- Consumes:
  - `AbstractStateFact`
  - Existing `ObservedDelta`
- Produces:
  - `TypedStateDelta`
  - `typed_deltas_from_facts(before: list[AbstractStateFact], after: list[AbstractStateFact]) -> list[TypedStateDelta]`
  - `observed_deltas_from_typed(deltas: list[TypedStateDelta], *, url: str) -> list[ObservedDelta]`

- [ ] **Step 1: Write failing typed delta tests**

Create `tests/safesym_bridge/test_typed_delta.py`:

```python
from ai_web_explorer.grounded_web.state_facts import AbstractStateFact
from ai_web_explorer.grounded_web.structure import StructureEvidence
from ai_web_explorer.grounded_web.typed_delta import (
    observed_deltas_from_typed,
    typed_deltas_from_facts,
)


def test_typed_deltas_from_facts_preserves_type_and_evidence():
    evidence = [StructureEvidence(source="dom_indicator", selector="#count")]
    before = [
        AbstractStateFact(
            fact_id="result_count",
            fact_type="numeric",
            value=0,
            identity_role="identity",
            source_ref="result-count",
            evidence=evidence,
        )
    ]
    after = [
        AbstractStateFact(
            fact_id="result_count",
            fact_type="numeric",
            value=3,
            identity_role="identity",
            source_ref="result-count",
            evidence=evidence,
        )
    ]

    deltas = typed_deltas_from_facts(before, after)
    observed = observed_deltas_from_typed(
        deltas,
        url="https://example.test/search",
    )

    assert deltas[0].delta_type == "numeric_changed"
    assert deltas[0].identity_relevant is True
    assert observed[0].field == "result_count"
    assert observed[0].delta_type == "numeric_changed"
    assert observed[0].evidence[0].selector == "#count"
```

- [ ] **Step 2: Run typed delta test and verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_typed_delta.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'ai_web_explorer.grounded_web.typed_delta'`.

- [ ] **Step 3: Implement typed delta module**

Create `src/ai_web_explorer/grounded_web/typed_delta.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_web_explorer.grounded_web.capability_graph import Evidence, ObservedDelta
from ai_web_explorer.grounded_web.state_facts import AbstractStateFact
from ai_web_explorer.grounded_web.structure import StructureEvidence


@dataclass(frozen=True)
class TypedStateDelta:
    fact_id: str
    fact_type: str
    delta_type: str
    before: Any
    after: Any
    source_ref: str
    identity_relevant: bool
    evidence: list[StructureEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "fact_type": self.fact_type,
            "delta_type": self.delta_type,
            "before": self.before,
            "after": self.after,
            "source_ref": self.source_ref,
            "identity_relevant": self.identity_relevant,
            "evidence": [item.to_dict() for item in self.evidence],
        }


def _delta_type_for(fact_type: str) -> str:
    return {
        "navigation": "navigation_changed",
        "visibility": "visibility_changed",
        "numeric": "numeric_changed",
        "form_value": "form_value_changed",
        "control_availability": "control_availability_changed",
        "selection": "selection_changed",
        "repeated_entity_count": "repeated_entity_count_changed",
    }.get(fact_type, "state_fact_changed")


def typed_deltas_from_facts(
    before: list[AbstractStateFact],
    after: list[AbstractStateFact],
) -> list[TypedStateDelta]:
    before_by_id = {fact.fact_id: fact for fact in before}
    after_by_id = {fact.fact_id: fact for fact in after}
    deltas: list[TypedStateDelta] = []
    for fact_id in sorted(set(before_by_id) | set(after_by_id)):
        before_fact = before_by_id.get(fact_id)
        after_fact = after_by_id.get(fact_id)
        before_value = before_fact.value if before_fact is not None else None
        after_value = after_fact.value if after_fact is not None else None
        if before_value == after_value:
            continue
        representative = after_fact or before_fact
        if representative is None:
            continue
        deltas.append(
            TypedStateDelta(
                fact_id=fact_id,
                fact_type=representative.fact_type,
                delta_type=_delta_type_for(representative.fact_type),
                before=before_value,
                after=after_value,
                source_ref=representative.source_ref,
                identity_relevant=representative.identity_role == "identity",
                evidence=representative.evidence,
            )
        )
    return deltas


def _evidence_to_graph(
    evidence: list[StructureEvidence],
    *,
    url: str,
) -> list[Evidence]:
    if not evidence:
        return [Evidence(source="typed_state_delta", url=url)]
    return [
        Evidence(
            source=item.source,
            selector=item.selector,
            text_sample=item.text_sample,
            url=item.url or url,
            confidence=item.confidence,
        )
        for item in evidence
    ]


def observed_deltas_from_typed(
    deltas: list[TypedStateDelta],
    *,
    url: str,
) -> list[ObservedDelta]:
    return [
        ObservedDelta(
            field=delta.fact_id,
            before=delta.before,
            after=delta.after,
            delta_type=delta.delta_type,
            evidence=_evidence_to_graph(delta.evidence, url=url),
        )
        for delta in deltas
    ]
```

- [ ] **Step 4: Run typed delta tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_typed_delta.py -q
```

Expected: PASS.

- [ ] **Step 5: Add failing explorer fallback test for typed deltas**

Append this test to `tests/safesym_bridge/test_web_kobe_explorer.py`:

```python
from ai_web_explorer.grounded_web.state_facts import AbstractStateFact
from ai_web_explorer.grounded_web.structure import StructureEvidence


class TypedFactsAdapter(FakeAdapter):
    def __init__(self):
        super().__init__()
        self.fact_sets = [
            [
                AbstractStateFact(
                    fact_id="result_count",
                    fact_type="numeric",
                    value=0,
                    identity_role="identity",
                    source_ref="result-count",
                    evidence=[
                        StructureEvidence(
                            source="dom_indicator",
                            selector="#result-count",
                        )
                    ],
                )
            ],
            [
                AbstractStateFact(
                    fact_id="result_count",
                    fact_type="numeric",
                    value=3,
                    identity_role="identity",
                    source_ref="result-count",
                    evidence=[
                        StructureEvidence(
                            source="dom_indicator",
                            selector="#result-count",
                        )
                    ],
                )
            ],
        ]

    async def observe_state(self):
        self.last_state_facts = self.fact_sets[min(len(self.executed), 1)]
        return await super().observe_state()


@pytest.mark.anyio
async def test_explore_one_step_uses_typed_delta_when_adapter_exposes_facts():
    explorer = WebKobeExplorer(
        adapter=TypedFactsAdapter(),
        semantic_assistor=DeterministicSemanticAssistor(app="fake"),
    )

    graph = await explorer.explore_one_step()

    assert graph.edges[0].observed_delta[0].field == "result_count"
    assert graph.edges[0].observed_delta[0].delta_type == "numeric_changed"
    assert graph.edges[0].observed_delta[0].evidence[0].selector == "#result-count"
```

- [ ] **Step 6: Run explorer typed delta test and verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_explorer.py::test_explore_one_step_uses_typed_delta_when_adapter_exposes_facts -q
```

Expected: FAIL because `WebKobeExplorer` still uses untyped signature diff.

- [ ] **Step 7: Integrate typed deltas in explorer**

In `src/ai_web_explorer/grounded_web/explorer.py`, import:

```python
from ai_web_explorer.grounded_web.typed_delta import (
    observed_deltas_from_typed,
    typed_deltas_from_facts,
)
```

Add this helper near `_observed_delta()`:

```python
def _observed_delta_from_adapter(
    adapter: AutomationBackend,
    *,
    before_facts,
    after_facts,
    before_signature: dict[str, Any],
    after_signature: dict[str, Any],
    url: str,
) -> list[ObservedDelta]:
    if before_facts is not None and after_facts is not None:
        typed = typed_deltas_from_facts(before_facts, after_facts)
        return observed_deltas_from_typed(typed, url=url)
    return _observed_delta(before_signature, after_signature, url)
```

Then in `explore_one_step()`, after `before = await self.adapter.observe_state()` add:

```python
        before_facts = getattr(self.adapter, "last_state_facts", None)
```

After `after = await self.adapter.observe_state()` add:

```python
        after_facts = getattr(self.adapter, "last_state_facts", None)
```

Replace the `observed_delta=` argument with:

```python
            observed_delta=_observed_delta_from_adapter(
                self.adapter,
                before_facts=before_facts,
                after_facts=after_facts,
                before_signature=before_draft.last_state_snapshot,
                after_signature=after_draft.last_state_snapshot,
                url=after.url,
            ),
```

- [ ] **Step 8: Run typed delta and explorer tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_typed_delta.py tests/safesym_bridge/test_web_kobe_explorer.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit Task 4**

Run:

```bash
git add src/ai_web_explorer/grounded_web/typed_delta.py src/ai_web_explorer/grounded_web/explorer.py tests/safesym_bridge/test_typed_delta.py tests/safesym_bridge/test_web_kobe_explorer.py
git commit -m "feat: infer typed state deltas"
```

---

### Task 5: Wire generic observation-to-state into Playwright backend and add non-ecommerce fixture

**Files:**
- Modify: `src/ai_web_explorer/grounded_web/playwright_backend.py`
- Create: `tests/fixtures/local_form_search/index.html`
- Modify: `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`
- Create: `tests/safesym_bridge/test_observation_to_state_form_search.py`
- Modify: `tests/safesym_bridge/test_web_kobe_grounded_exploration.py`

**Interfaces:**
- Consumes:
  - `observe_page_structure(page, page_id=None) -> PageStructureObservation`
  - `facts_from_structure(observation) -> list[AbstractStateFact]`
  - `state_signature_from_facts(facts) -> dict[str, Any]`
- Produces:
  - `WebKobePlaywrightAdapter.last_structure_observation`
  - `WebKobePlaywrightAdapter.last_state_facts`
  - Generic `observe_state()` signature derived from typed facts.

- [ ] **Step 1: Add failing backend observation test**

In `tests/safesym_bridge/test_web_kobe_playwright_adapter.py`, add this test:

```python
@pytest.mark.anyio
async def test_observe_state_uses_generic_structure_pipeline(monkeypatch):
    from ai_web_explorer.grounded_web.structure import (
        IndicatorObservation,
        PageInfo,
        PageStructureObservation,
        StructureEvidence,
    )

    async def fake_observe_page_structure(page, *, page_id=None):
        evidence = [StructureEvidence(source="dom_indicator", selector="#count")]
        return PageStructureObservation(
            page=PageInfo(
                url=page.url,
                title="Fixture Shop",
                page_id=page_id or "fixture_shop",
            ),
            indicators=[
                IndicatorObservation(
                    id="cart-count",
                    indicator_type="numeric",
                    key_hint="cart-count",
                    value=1,
                    visible=True,
                    locator="#count",
                    evidence=evidence,
                )
            ],
        )

    monkeypatch.setattr(
        "ai_web_explorer.grounded_web.playwright_backend.observe_page_structure",
        fake_observe_page_structure,
    )
    adapter = WebKobePlaywrightAdapter(FakePage(), page_id="fixture_shop")

    snapshot = await adapter.observe_state()

    assert snapshot.signature["cart_count"] == 1
    assert adapter.last_structure_observation.page.page_id == "fixture_shop"
    assert adapter.last_state_facts[0].fact_type == "navigation"
```

- [ ] **Step 2: Run backend observation test and verify it fails**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_playwright_adapter.py::test_observe_state_uses_generic_structure_pipeline -q
```

Expected: FAIL because `playwright_backend` does not yet import/use `observe_page_structure`.

- [ ] **Step 3: Wire generic structure pipeline into backend**

In `src/ai_web_explorer/grounded_web/playwright_backend.py`, add imports:

```python
from ai_web_explorer.grounded_web.state_facts import (
    facts_from_structure,
    state_signature_from_facts,
)
from ai_web_explorer.grounded_web.structure import observe_page_structure
```

In `WebKobePlaywrightAdapter.__init__()`, add:

```python
        self.last_structure_observation = None
        self.last_state_facts = None
```

In generic `observe_state()`, replace the current `_data_state_signature()` plus
hardcoded `cart_count` fallback block with:

```python
        structure = await observe_page_structure(self.page, page_id=page_id)
        facts = facts_from_structure(structure)
        signature = state_signature_from_facts(facts)
        self.last_structure_observation = structure
        self.last_state_facts = facts
```

Keep the returned `StateSnapshot` as:

```python
        return StateSnapshot(
            page_id=page_id,
            url=self.page.url,
            title=title,
            signature=signature,
        )
```

Do not remove `_data_state_signature()` yet in this task if other code still imports it. If no code imports it, it can be removed in a follow-up cleanup after regression tests pass.

- [ ] **Step 4: Run backend adapter tests**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_playwright_adapter.py -q
```

Expected: PASS after updating any old fake expectations to use the generic structure path.

- [ ] **Step 5: Add non-ecommerce fixture**

Create `tests/fixtures/local_form_search/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Local Form Search</title>
    <style>
      body { font-family: Arial, sans-serif; margin: 24px; }
      .result-row { border: 1px solid #d9e2ec; margin: 8px 0; padding: 8px; }
      [hidden] { display: none; }
    </style>
  </head>
  <body>
    <main>
      <h1>Local Form Search</h1>
      <form id="search-form">
        <label>
          Query
          <input id="query" name="query" type="search" placeholder="Search records">
        </label>
        <label>
          Type
          <select id="type-filter" name="type">
            <option value="all">All</option>
            <option value="open">Open</option>
          </select>
        </label>
        <button data-action="run-search" type="button">Search</button>
      </form>

      <section role="status" data-state="status-panel">No search yet.</section>
      <p>Results: <span data-state="result-count">0</span></p>
      <section id="results" aria-label="Results"></section>
    </main>

    <script>
      const query = document.querySelector("#query");
      const statusPanel = document.querySelector("[data-state='status-panel']");
      const resultCount = document.querySelector("[data-state='result-count']");
      const results = document.querySelector("#results");

      document.querySelector("[data-action='run-search']").addEventListener("click", () => {
        const count = query.value.trim() ? 3 : 1;
        statusPanel.textContent = `Search complete for ${query.value || "empty query"}.`;
        resultCount.textContent = String(count);
        results.innerHTML = "";
        for (let index = 0; index < count; index += 1) {
          const row = document.createElement("article");
          row.className = "result-row";
          row.setAttribute("data-entity-type", "result-row");
          row.textContent = `Result ${index + 1}`;
          results.appendChild(row);
        }
      });
    </script>
  </body>
</html>
```

- [ ] **Step 6: Add form-search browser smoke test**

Create `tests/safesym_bridge/test_observation_to_state_form_search.py`:

```python
from pathlib import Path

import pytest

from ai_web_explorer.grounded_web.controller import WebKobeExplorationController
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.playwright_backend import WebKobePlaywrightAdapter
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_form_search_records_typed_numeric_and_group_deltas():
    from playwright.async_api import async_playwright

    fixture_url = Path("tests/fixtures/local_form_search/index.html").resolve().as_uri()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(fixture_url)
            adapter = WebKobePlaywrightAdapter(
                page,
                app_name="local_form_search",
                page_id="local_form_search",
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(
                    app="local_form_search"
                ),
            )
            controller = WebKobeExplorationController(explorer)

            result = await controller.run(max_steps=2)

            delta_types = {
                delta.delta_type
                for edge in result.graph.edges
                for delta in edge.observed_delta
            }
            fields = {
                delta.field
                for edge in result.graph.edges
                for delta in edge.observed_delta
            }
            assert "numeric_changed" in delta_types
            assert "repeated_entity_count_changed" in delta_types
            assert "result_count" in fields
            assert "result_row_count" in fields
        finally:
            await browser.close()
```

- [ ] **Step 7: Run form-search smoke test**

Run:

```bash
python -m pytest tests/safesym_bridge/test_observation_to_state_form_search.py -q
```

Expected: PASS. If the browser launch is sandbox-blocked, rerun with the approved elevated pytest command.

- [ ] **Step 8: Update local shop smoke expectations if needed**

Run:

```bash
python -m pytest tests/safesym_bridge/test_web_kobe_grounded_exploration.py -q
```

Expected: PASS. If it fails only because `observed_delta.delta_type` changed from `state_indicator_change` to typed names, update the test to assert the semantic field changes still exist and now use typed delta names:

```python
assert ("cart_count", 0, 1, "numeric_changed") in deltas
assert ("cart_panel_visible", False, True, "visibility_changed") in deltas
```

- [ ] **Step 9: Run focused observation-to-state regression**

Run:

```bash
python -m pytest tests/safesym_bridge/test_page_structure_observer.py tests/safesym_bridge/test_state_facts.py tests/safesym_bridge/test_typed_delta.py tests/safesym_bridge/test_web_kobe_playwright_adapter.py tests/safesym_bridge/test_web_kobe_grounded_exploration.py tests/safesym_bridge/test_observation_to_state_form_search.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit Task 5**

Run:

```bash
git add src/ai_web_explorer/grounded_web/playwright_backend.py tests/fixtures/local_form_search/index.html tests/safesym_bridge/test_web_kobe_playwright_adapter.py tests/safesym_bridge/test_observation_to_state_form_search.py tests/safesym_bridge/test_web_kobe_grounded_exploration.py
git commit -m "feat: wire observation to state pipeline"
```

---

## Final Verification

After all tasks are complete, run:

```bash
python -m pytest tests/safesym_bridge -q
```

Expected: PASS with existing browser-gated skips preserved.

Then verify the architectural boundary:

```bash
rg "safesym_bridge" src/ai_web_explorer/grounded_web
```

Expected: no Python import from `grounded_web` to `safesym_bridge`. Documentation strings mentioning `safesym_bridge` are acceptable.

Check git state:

```bash
git status --short
git log -6 --oneline
```

Expected: clean worktree and task commits present.

## Post-Implementation Notes

This plan intentionally keeps `StateSnapshot.signature` as a compatibility
surface. Typed facts and typed deltas are added alongside it rather than forcing
all graph consumers to change at once.

The next module after this should be semantic assistance:

```text
PageStructureObservation + AbstractStateFact[] + BrowserAction[] + Delta[]
-> LLM-assisted action ranking / state naming / sensitive-action hints
```

That future module must consume the structured observation layer. It must not
fall back to raw HTML as its primary interface.
