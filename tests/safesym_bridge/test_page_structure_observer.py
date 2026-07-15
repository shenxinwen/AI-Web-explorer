import pytest

from ai_web_explorer.grounded_web.structure import (
    ControlObservation,
    IndicatorObservation,
    PageInfo,
    PageStructureObservation,
    RegionObservation,
    RepeatedGroupObservation,
    StructureEvidence,
    observe_page_structure,
    page_structure_from_snapshot,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


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
            "forms": [
                {
                    "id": "search-form",
                    "locator": "#search-form",
                    "fields": [
                        {
                            "id": "query",
                            "kind": "input",
                            "name": "Query",
                            "locator": "#query",
                            "value": "sample",
                            "metadata": {"type": "search"},
                        }
                    ],
                    "submit_controls": ["run-search"],
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
    assert observation.forms[0].fields[0].value == "sample"


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
