from ai_web_explorer.grounded_web.business_profile import PlanningTransition
from ai_web_explorer.grounded_web.business_state_policy import (
    resolve_business_target_node,
)
from ai_web_explorer.grounded_web.capability_graph import Evidence, PageFrame
from ai_web_explorer.grounded_web.graph import BusinessTransition, WebKobeNode


def _node(node_id: str, *, node_label: str | None = None) -> WebKobeNode:
    evidence = [Evidence(source="unit_test")]
    return WebKobeNode(
        node_id=node_id,
        page_description="shopping page",
        page_frame=PageFrame(
            page_id="practice:shopping",
            page_type="shopping",
            url="https://example.test/shop",
            url_pattern="https://example.test/shop",
            title="Shop",
            evidence=evidence,
        ),
        state_schema={},
        last_state_snapshot={},
        node_label=node_label,
        evidence=evidence,
    )


def test_business_state_node_uses_added_planning_fact_for_readable_label():
    target = resolve_business_target_node(
        source_node=_node("shopping"),
        candidate_node=_node("shopping_after", node_label="shopping"),
        business_transition=BusinessTransition(
            action_name="open_cart",
            relevance="core",
            meaningful_change=True,
        ),
        planning_transition=PlanningTransition(
            pre_facts=["cart_has_items"],
            added_facts=["cart_page_visible"],
            removed_facts=[],
            post_facts=["cart_has_items", "cart_page_visible"],
        ),
        state_label_hints={"cart_page_visible": "cart"},
    )

    assert target.node_label == "cart"
    assert target.node_id.startswith("cart__business_")


def test_business_state_node_does_not_hardcode_profile_fact_labels():
    target = resolve_business_target_node(
        source_node=_node("shopping"),
        candidate_node=_node("shopping_after", node_label="shopping"),
        business_transition=BusinessTransition(
            action_name="open_cart",
            relevance="core",
            meaningful_change=True,
        ),
        planning_transition=PlanningTransition(
            added_facts=["cart_page_visible"],
            post_facts=["cart_page_visible"],
        ),
    )

    assert target.node_label == "cart_page"
    assert target.node_id.startswith("cart__business_")


def test_business_state_node_falls_back_to_business_action_name():
    target = resolve_business_target_node(
        source_node=_node("shopping"),
        candidate_node=_node("shopping_after", node_label="shopping"),
        business_transition=BusinessTransition(
            action_name="open_product_details",
            relevance="supporting",
            meaningful_change=True,
        ),
        planning_transition=PlanningTransition(),
    )

    assert target.node_label == "product_details"
    assert target.node_id.startswith("product_details__business_")


def test_business_state_identity_does_not_include_planning_facts():
    first = resolve_business_target_node(
        source_node=_node("shopping"),
        candidate_node=_node("shopping_after", node_label="shopping"),
        business_transition=BusinessTransition(
            action_name="open_cart",
            relevance="core",
            meaningful_change=True,
        ),
        planning_transition=PlanningTransition(post_facts=["cart_page_visible"]),
    )
    second = resolve_business_target_node(
        source_node=_node("shopping"),
        candidate_node=_node("shopping_after", node_label="shopping"),
        business_transition=BusinessTransition(
            action_name="open_cart",
            relevance="core",
            meaningful_change=True,
        ),
        planning_transition=PlanningTransition(
            post_facts=["cart_page_visible", "unstable_vlm_observation"]
        ),
    )

    assert first.node_id == second.node_id
