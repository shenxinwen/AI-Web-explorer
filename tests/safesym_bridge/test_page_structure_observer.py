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
