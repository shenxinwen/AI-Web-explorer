from ai_web_explorer.grounded_web.business_profile import PlanningTransition
from ai_web_explorer.grounded_web.business_state_policy import (
    observation_change_node_id,
    resolve_business_target_node,
)
from ai_web_explorer.grounded_web.capability_graph import Evidence, PageFrame
from ai_web_explorer.grounded_web.graph import BusinessTransition, WebKobeNode


def test_observation_change_node_id_is_stable_and_order_independent():
    first = observation_change_node_id(
        source_node_id="listing__source",
        action_name="add_to_cart",
        after_signature={"cart_count": 1},
        added_facts=["cart_has_items", "product_selected"],
        removed_facts=["cart_empty"],
    )
    second = observation_change_node_id(
        source_node_id="listing__source",
        action_name="add_to_cart",
        after_signature={"cart_count": 1},
        added_facts=["product_selected", "cart_has_items"],
        removed_facts=["cart_empty"],
    )

    assert first == second
    assert first != "listing__source"


def test_observation_change_node_id_uses_after_signature():
    first = observation_change_node_id(
        source_node_id="listing",
        action_name="add_to_cart",
        after_signature={"cart_count": 1},
        added_facts=["cart_count_increased"],
        removed_facts=[],
    )
    second = observation_change_node_id(
        source_node_id="listing",
        action_name="add_to_cart",
        after_signature={"cart_count": 2},
        added_facts=["cart_count_increased"],
        removed_facts=[],
    )

    assert first != second


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


def test_business_state_node_preserves_candidate_visible_state_label():
    target = resolve_business_target_node(
        source_node=_node("shopping"),
        candidate_node=_node(
            "shopping_after",
            node_label="product_list_sorted",
        ),
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
    )

    assert target.node_label == "product_list_sorted"
    assert target.node_id.startswith("cart__business_")


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
