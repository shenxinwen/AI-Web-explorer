import json
from dataclasses import replace

from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.grounded_web.business_profile import PlanningState
from ai_web_explorer.grounded_web.business_profile import PlanningTransition
from ai_web_explorer.grounded_web.business_profile import ecommerce_checkout_profile
from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.graph_manager import WebKobeGraphManager
from ai_web_explorer.safesym_bridge.trace_pddl import compile_trace_domain
from ai_web_explorer.safesym_bridge.surface_pddl import compile_surface_domain
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    load_web_kobe_graph_json,
)


def _node(node_id: str, values: dict, interactables=None) -> WebKobeNode:
    evidence = [Evidence(source="unit_test")]
    return WebKobeNode(
        node_id=node_id,
        page_description="product listing",
        page_frame=PageFrame(
            page_id="example:inventory",
            page_type="product_listing",
            url="https://example.test/inventory",
            url_pattern="https://example.test/inventory",
            title="Inventory",
            evidence=evidence,
        ),
        state_schema={key: [value] for key, value in values.items()},
        last_state_snapshot=values,
        interactable_elements=interactables or [],
        reference_observation=ReferenceObservation(
            url="https://example.test/inventory",
            title="Inventory",
        ),
        evidence=evidence,
    )


def test_identify_or_add_node_merges_schema_and_visit_count():
    manager = WebKobeGraphManager(app="example")

    first = _node("product_listing", {"cart_has_items": False})
    second = _node("product_listing", {"cart_has_items": True, "filter_open": False})

    assert manager.identify_or_add_node(first) == "product_listing"
    assert manager.identify_or_add_node(second) == "product_listing"

    graph = manager.to_graph()
    node = graph.nodes[0]
    assert node.visit_count == 2
    assert node.state_schema["cart_has_items"] == [False, True]
    assert node.state_schema["filter_open"] == [False]
    assert node.last_state_snapshot == {"cart_has_items": True, "filter_open": False}


def test_graph_manager_from_graph_is_lossless_and_does_not_reappend_events():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(_node("page", {"ready": True}))
    edge = _trace_edge("open_item", success=True, status="succeeded")
    manager.add_edge(edge)
    manager.add_edge(replace(edge, visit_count=2))
    graph = manager.to_graph(start_node_id="page")

    restored_manager = WebKobeGraphManager.from_graph(graph)
    restored = restored_manager.to_graph(start_node_id=graph.start_node_id)

    assert restored.to_dict() == graph.to_dict()
    assert len(restored.execution_events) == 2

    graph.meta["mutated_after_restore"] = True
    graph.nodes[0].business_affordances.append(BusinessAffordance("late_action"))
    isolated = restored_manager.to_graph(start_node_id=graph.start_node_id)
    assert "mutated_after_restore" not in isolated.meta
    assert [item.action_name for item in isolated.nodes[0].business_affordances] != [
        "late_action"
    ]


def test_identify_or_add_node_keeps_existing_business_frontier_on_revisit():
    manager = WebKobeGraphManager(app="example")
    first = replace(
        _node("cart_with_items", {"cart_has_items": True}),
        business_affordances=[
            BusinessAffordance("view_cart"),
            BusinessAffordance("proceed_to_checkout"),
        ],
    )
    revisit = replace(
        _node("cart_with_items", {"cart_has_items": True}),
        business_affordances=[
            BusinessAffordance("add_to_cart"),
            BusinessAffordance("sort_products"),
        ],
    )

    manager.identify_or_add_node(first)
    manager.identify_or_add_node(revisit)

    graph = manager.to_graph()
    assert [
        affordance.action_name for affordance in graph.nodes[0].business_affordances
    ] == ["view_cart", "proceed_to_checkout"]


def test_identify_or_add_node_upgrades_fallback_naming_to_vlm():
    manager = WebKobeGraphManager(app="example")
    fallback = replace(
        _node("listing", {}),
        node_label="shopping",
        state_summary="Local fallback summary.",
        naming_provenance={"source": "deterministic_fallback"},
    )
    vlm_named = replace(
        _node("listing", {}),
        node_label="product_list",
        state_summary="Visible product list.",
        naming_provenance={"source": "visual_affordance_vlm"},
    )

    manager.identify_or_add_node(fallback)
    manager.identify_or_add_node(vlm_named)

    node = manager.node_for_id("listing")
    assert node.node_label == "product_list"
    assert node.state_summary == "Visible product list."
    assert node.naming_provenance == {"source": "visual_affordance_vlm"}


def _trace_edge(action_name: str, *, success: bool, status: str) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id="page",
        target_node_id="page",
        instruction=action_name,
        action=BrowserAction(
            "business_intent",
            None,
            action_name,
            canonical_action_name=action_name,
        ),
        capability=None,
        target_observation="page",
        observed_delta=[],
        schema_delta=None,
        execution_trace=ExecutionTrace(
            "business_intent",
            None,
            action_name,
            {},
            "page",
            "page",
            success,
        ),
        status=status,
    )


def test_execution_events_preserve_a_b_a_through_json_and_trace_compiler(
    tmp_path,
):
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(_node("page", {}))
    for action_name in ("action_a", "action_b", "action_a"):
        manager.add_edge(
            _trace_edge(action_name, success=True, status="no_observed_change")
        )

    frozen = manager.to_graph(start_node_id="page")
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(frozen.to_dict()), encoding="utf-8")
    loaded = load_web_kobe_graph_json(graph_path)
    result = compile_trace_domain(loaded)

    assert len(frozen.edges) == 2
    assert len(frozen.execution_events) == 3
    assert len(loaded.execution_events) == 3
    assert [item["original_action_identity"] for item in result.report["actions"]] == [
        "action_a",
        "action_b",
        "action_a",
    ]
    assert len(result.report["checkpoints"]) == 4

    legacy_data = frozen.to_dict()
    legacy_data.pop("execution_events")
    legacy_path = tmp_path / "legacy-graph.json"
    legacy_path.write_text(json.dumps(legacy_data), encoding="utf-8")
    legacy_loaded = load_web_kobe_graph_json(legacy_path)
    legacy_result = compile_trace_domain(legacy_loaded)

    assert legacy_loaded.execution_events == []
    assert [
        item["original_action_identity"] for item in legacy_result.report["actions"]
    ] == ["action_a", "action_b"]


def test_execution_events_preserve_failed_then_successful_retry():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(_node("page", {}))
    manager.add_edge(
        _trace_edge("action_a", success=False, status="failed_execution")
    )
    manager.add_edge(
        _trace_edge("action_a", success=True, status="no_observed_change")
    )

    graph = manager.to_graph(start_node_id="page")
    result = compile_trace_domain(graph)

    assert len(graph.edges) == 1
    assert len(graph.execution_events) == 2
    assert [item["reason"] for item in result.report["excluded_edges"]] == [
        "failed_execution"
    ]
    assert [item["original_action_identity"] for item in result.report["actions"]] == [
        "action_a"
    ]


def test_identify_or_add_node_preserves_first_vlm_naming_on_revisit():
    manager = WebKobeGraphManager(app="example")
    first_vlm = replace(
        _node("listing", {}),
        node_label="product_list",
        state_summary="Visible product list.",
        naming_provenance={"source": "visual_affordance_vlm"},
    )
    local_revisit = replace(
        _node("listing", {}),
        node_label="shopping",
        state_summary="Local fallback summary.",
        naming_provenance={"source": "deterministic_fallback"},
    )
    later_vlm = replace(
        _node("listing", {}),
        node_label="different_product_state",
        state_summary="Different VLM summary.",
        naming_provenance={"source": "visual_affordance_vlm"},
    )

    manager.identify_or_add_node(first_vlm)
    manager.identify_or_add_node(local_revisit)
    manager.identify_or_add_node(later_vlm)

    node = manager.node_for_id("listing")
    assert node.node_label == "product_list"
    assert node.state_summary == "Visible product list."
    assert node.naming_provenance == {"source": "visual_affordance_vlm"}


def test_identify_or_add_node_keeps_existing_non_vlm_merge_behavior():
    manager = WebKobeGraphManager(app="example")
    first = replace(
        _node("listing", {}),
        node_label="first_fallback",
        naming_provenance={"source": "deterministic_fallback"},
    )
    incoming = replace(
        _node("listing", {}),
        node_label="latest_fallback",
        naming_provenance={"source": "deterministic_fallback"},
    )

    manager.identify_or_add_node(first)
    manager.identify_or_add_node(incoming)

    node = manager.node_for_id("listing")
    assert node.node_label == "latest_fallback"
    assert node.naming_provenance == {"source": "deterministic_fallback"}


def test_add_edge_merges_planning_transition_for_repeated_edge():
    manager = WebKobeGraphManager(app="example")
    edge = WebKobeEdge(
        source_node_id="inventory",
        target_node_id="cart",
        instruction="open cart",
        action=BrowserAction("business_intent", None, "open_cart"),
        capability=None,
        target_observation="cart page",
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "business_intent",
            None,
            "open_cart",
            {},
            "inventory",
            "cart",
            True,
        ),
    )

    manager.add_edge(edge)
    manager.add_edge(
        WebKobeEdge(
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            instruction=edge.instruction,
            action=edge.action,
            capability=edge.capability,
            target_observation=edge.target_observation,
            observed_delta=[],
            schema_delta={},
            execution_trace=edge.execution_trace,
            planning_transition=PlanningTransition(
                pre_facts=["cart_has_items"],
                added_facts=["checkout_started"],
                removed_facts=[],
                post_facts=["cart_has_items", "checkout_started"],
            ),
        )
    )

    graph = manager.to_graph(start_node_id="inventory")

    assert graph.edges[0].visit_count == 2
    assert graph.edges[0].planning_transition is not None
    assert graph.edges[0].planning_transition.pre_facts == ["cart_has_items"]


def test_propagate_planning_state_records_profile_and_generated_facts():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(
        _node("inventory", {}, interactables=[]),
    )
    manager.identify_or_add_node(_node("cart", {}, interactables=[]))
    edge = WebKobeEdge(
        source_node_id="inventory",
        target_node_id="cart",
        instruction="open cart",
        action=BrowserAction("business_intent", None, "open_cart"),
        capability=None,
        target_observation="cart page",
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "business_intent",
            None,
            "open_cart",
            {},
            "inventory",
            "cart",
            True,
        ),
        planning_delta=PlanningDelta(
            candidate_added_facts=["cart_page_visible", "made_up_fact"],
            profile_fact_ids=["cart_page_visible"],
            generated_fact_ids=["made_up_fact"],
        ),
    )

    updated_edge = manager.propagate_planning_state(
        edge,
        profile=ecommerce_checkout_profile(),
    )

    graph = manager.to_graph(start_node_id="inventory")
    cart = next(node for node in graph.nodes if node.node_id == "cart")
    assert cart.planning_state is not None
    assert cart.planning_state.active_facts == ["cart_page_visible", "made_up_fact"]
    assert cart.planning_state.profile_fact_ids == ["cart_page_visible"]
    assert cart.planning_state.generated_fact_ids == ["made_up_fact"]
    assert updated_edge.planning_transition is not None
    assert updated_edge.planning_transition.pre_facts == []
    assert updated_edge.planning_transition.added_facts == [
        "cart_page_visible",
        "made_up_fact",
    ]
    assert updated_edge.planning_transition.removed_facts == []
    assert updated_edge.planning_transition.post_facts == [
        "cart_page_visible",
        "made_up_fact",
    ]


def test_propagate_planning_state_does_not_infer_profile_from_fact_name():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(_node("products", {}, interactables=[]))
    manager.identify_or_add_node(_node("products_after", {}, interactables=[]))
    edge = WebKobeEdge(
        source_node_id="products",
        target_node_id="products_after",
        instruction="observe product details",
        action=BrowserAction("business_intent", None, "view_product_details"),
        capability=None,
        target_observation="product details",
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "business_intent",
            None,
            "view_product_details",
            {},
            "products",
            "products_after",
            True,
        ),
        planning_delta=PlanningDelta(
            candidate_added_facts=["product_details_visible"],
            generated_fact_ids=["product_details_visible"],
        ),
        planning_transition=PlanningTransition(
            pre_facts=[],
            added_facts=["product_details_visible"],
            removed_facts=[],
            post_facts=["product_details_visible"],
        ),
    )

    manager.apply_planning_transition(
        edge,
        profile=ecommerce_checkout_profile(),
    )

    product_details = manager.node_for_id("products_after")
    assert product_details.planning_state is not None
    assert product_details.planning_state.profile_fact_ids == []
    assert product_details.planning_state.generated_fact_ids == [
        "product_details_visible"
    ]


def test_propagate_planning_state_omits_already_active_added_facts():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(_node("products", {}, interactables=[]))
    manager.identify_or_add_node(_node("products_after", {}, interactables=[]))
    manager._nodes["products"] = replace(
        manager._nodes["products"],
        planning_state=PlanningState(active_facts=["cart_has_items"]),
    )
    edge = WebKobeEdge(
        source_node_id="products",
        target_node_id="products_after",
        instruction="add another item",
        action=BrowserAction("business_intent", None, "add_item_to_cart"),
        capability=None,
        target_observation="products page",
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "business_intent",
            None,
            "add_item_to_cart",
            {},
            "products",
            "products_after",
            True,
        ),
        planning_delta=PlanningDelta(candidate_added_facts=["cart_has_items"]),
    )

    updated_edge = manager.propagate_planning_state(
        edge,
        profile=ecommerce_checkout_profile(),
    )

    assert updated_edge.planning_transition is not None
    assert updated_edge.planning_transition.pre_facts == ["cart_has_items"]
    assert updated_edge.planning_transition.added_facts == []
    assert updated_edge.planning_transition.post_facts == ["cart_has_items"]


def test_duplicate_edge_cannot_clear_unstable_replay_validation_after_roundtrip(
    tmp_path,
):
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(_node("page", {}))
    edge = _trace_edge("action_a", success=True, status="no_observed_change")
    manager.add_edge(edge)
    manager.update_edge_replay_validation(edge.edge_id, "unstable")

    duplicate = replace(
        edge,
        execution_trace=replace(
            edge.execution_trace,
            metadata={"latest_observation": "new"},
        ),
    )
    manager.add_edge(duplicate)

    frozen = manager.to_graph(start_node_id="page")
    merged_edge = frozen.edges[0]
    assert merged_edge.execution_trace.metadata == {
        "latest_observation": "new",
        "replay_validation_status": "unstable",
    }

    graph_path = tmp_path / "graph.json"
    graph_path.write_text(json.dumps(frozen.to_dict()), encoding="utf-8")
    loaded = load_web_kobe_graph_json(graph_path)
    assert "action_a" not in compile_surface_domain(loaded).domain
    assert "action_a" in compile_trace_domain(loaded).domain


def test_duplicate_edge_preserves_verified_replay_validation():
    manager = WebKobeGraphManager(app="example")
    manager.identify_or_add_node(_node("page", {}))
    edge = _trace_edge("action_a", success=True, status="no_observed_change")
    manager.add_edge(edge)
    manager.update_edge_replay_validation(edge.edge_id, "verified")

    duplicate = replace(
        edge,
        execution_trace=replace(
            edge.execution_trace,
            metadata={"latest_observation": "new"},
        ),
    )
    manager.add_edge(duplicate)

    assert manager.to_graph().edges[0].execution_trace.metadata == {
        "latest_observation": "new",
        "replay_validation_status": "verified",
    }
