import json

from ai_web_explorer.grounded_web.business_profile import (
    PlanningDelta,
    PlanningState,
    PlanningTransition,
)
from ai_web_explorer.grounded_web.capability_graph import (
    Evidence,
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
    ReferenceObservation,
)
from ai_web_explorer.grounded_web.semantic_model import SemanticObservation
from ai_web_explorer.safesym_bridge.graph_artifacts import (
    build_graph_artifact_payload,
)


def _verbose_graph_fixture() -> WebKobeGraph:
    evidence = Evidence(
        source="playwright",
        selector="#search",
        text_sample="Search products",
        url="https://example.test/products",
    )
    product_list = WebKobeNode(
        node_id="product_list",
        page_description="Product list with a search control and product cards.",
        page_frame=PageFrame(
            page_id="shop:product_list",
            page_type="product_list",
            url="https://example.test/products",
            url_pattern="https://example.test/products",
            title="Products",
            heading="All products",
            signature_hints={"url_path": "/products", "product_count": 3},
            evidence=[evidence],
        ),
        state_schema={"url_path": ["/products"]},
        last_state_snapshot={"url_path": "/products", "product_count": 3},
        reference_observation=ReferenceObservation(
            url="https://example.test/products",
            title="Products",
            screenshot_path="screenshots/before.png",
            dom_summary="A long DOM summary that belongs in evidence.",
        ),
        visit_count=2,
        evidence=[evidence],
        node_label="product_list",
        state_summary="Product listing state",
        naming_provenance={"source": "deterministic"},
        planning_state=PlanningState(
            active_facts=["search_input_visible"],
            profile_fact_ids=["search_input_visible"],
            evidence=["structured signature"],
        ),
        business_affordances=[
            BusinessAffordance(
                action_name="search_items",
                label="Search",
                relevance_hint="core",
                target_hint="Search input",
                confidence=0.95,
                supporting_facts=["search_input_visible"],
            )
        ],
    )
    search_results = WebKobeNode(
        node_id="search_results",
        page_description="Search results",
        page_frame=PageFrame(
            page_id="shop:search_results",
            page_type="search_results",
            url="https://example.test/products?q=mouse",
            url_pattern="https://example.test/products",
            title="Search results",
        ),
        state_schema={"url_path": ["/products"]},
        last_state_snapshot={"url_path": "/products"},
        visit_count=1,
        node_label="search_results",
    )
    edge = WebKobeEdge(
        source_node_id="product_list",
        target_node_id="search_results",
        instruction="Enter mouse in the search field and submit the search.",
        action=BrowserAction(
            action_kind="fill_then_click",
            locator="#search-submit",
            semantic_id="search_items",
            input_values={"#search": "mouse"},
            description="A verbose action description duplicated by the affordance.",
            action_label="Search",
            canonical_action_name="search_items",
            naming_provenance={"source": "vlm"},
            supporting_facts=["search_input_visible"],
        ),
        capability=None,
        target_observation="Search results show a wireless mouse first.",
        observed_delta=[
            ObservedDelta(
                field="wireless_mouse_is_first_in_list",
                before=False,
                after=True,
                delta_type="added",
                evidence=[evidence],
            )
        ],
        schema_delta={"search_query": {"before": None, "after": "mouse"}},
        execution_trace=ExecutionTrace(
            concrete_action_kind="fill_then_click",
            concrete_locator="#search-submit",
            concrete_target_sample="Search",
            input_values_used={"#search": "mouse"},
            before_observation_id="product_list",
            after_observation_id="search_results",
            success=True,
            metadata={
                "action_source": "stagehand",
                "stagehand_result": {
                    "reasoning": "Used the visible search control.",
                    "aria_snapshot": "large diagnostic tree",
                },
                "visual_delta_trace": {
                    "candidate_added_facts": [
                        "wireless_mouse_is_first_in_list"
                    ],
                    "raw_response": "verbose visual response",
                },
            },
        ),
        pddl_hint=None,
        planning_delta=PlanningDelta(
            candidate_added_facts=["search_results_visible"],
            verified_added_facts=["search_results_visible"],
            profile_fact_ids=["search_results_visible"],
            evidence=["structured search signature"],
            confidence=1.0,
        ),
        planning_transition=PlanningTransition(
            pre_facts=["search_input_visible"],
            added_facts=["search_results_visible"],
            post_facts=["search_input_visible", "search_results_visible"],
            evidence=["structured search signature"],
        ),
        semantic_observation=SemanticObservation(
            action_role="presentation_capability",
            source_location="shopping",
            target_location="shopping",
            completion_facts=["products_sorted"],
            evidence=["Products visibly changed order."],
            confidence=0.9,
        ),
        visit_count=1,
        status="succeeded_with_observed_change",
        evidence=[evidence],
    )
    return WebKobeGraph(
        app="shop",
        start_node_id="product_list",
        total_steps_completed=1,
        nodes=[product_list, search_results],
        edges=[edge],
        meta={"experiment": "verbose fixture", "frontier": {"count": 1}},
    )


def _empty_values(value, path=()):
    if isinstance(value, dict):
        found = []
        for key, child in value.items():
            if child in (None, "", [], {}):
                found.append(path + (key,))
            else:
                found.extend(_empty_values(child, path + (key,)))
        return found
    if isinstance(value, list):
        found = []
        for index, child in enumerate(value):
            if child in (None, "", [], {}):
                found.append(path + (index,))
            else:
                found.extend(_empty_values(child, path + (index,)))
        return found
    return []


def test_build_graph_artifact_payload_moves_verbose_evidence_out_of_graph():
    payload = build_graph_artifact_payload(_verbose_graph_fixture())

    edge = payload.compact_graph["edges"][0]
    assert edge["source_node_id"] == "product_list"
    assert edge["action"]["semantic_id"] == "search_items"
    assert edge["target_node_id"] == "search_results"
    assert edge["status"] == "succeeded_with_observed_change"
    assert edge["execution_trace"]["success"] is True
    assert "observed_delta" not in edge
    assert "metadata" not in edge["execution_trace"]
    assert "instruction" not in edge
    assert "description" not in edge["action"]
    assert (
        edge["evidence_ref"]
        == "edge-evidence:product_list__search_items__search_results"
    )

    evidence = payload.evidence_sidecar["edges"][edge["evidence_ref"]]
    assert evidence["observed_delta"]
    assert evidence["execution_trace"]["metadata"]["visual_delta_trace"]


def test_compact_payload_omits_empty_values_and_resolves_every_reference():
    graph = _verbose_graph_fixture()
    payload = build_graph_artifact_payload(graph)
    encoded_full = json.dumps(graph.to_dict(), ensure_ascii=False)
    encoded_compact = json.dumps(payload.compact_graph, ensure_ascii=False)
    encoded_evidence = json.dumps(payload.evidence_sidecar, ensure_ascii=False)

    assert len(encoded_compact) < len(encoded_full)
    assert _empty_values(payload.compact_graph) == []
    assert "wireless_mouse_is_first_in_list" not in encoded_compact
    assert "wireless_mouse_is_first_in_list" in encoded_evidence
    for node in payload.compact_graph["nodes"]:
        if "evidence_ref" in node:
            assert node["evidence_ref"] in payload.evidence_sidecar["nodes"]
    for edge in payload.compact_graph["edges"]:
        if "evidence_ref" in edge:
            assert edge["evidence_ref"] in payload.evidence_sidecar["edges"]


def test_compact_payload_preserves_semantic_observation_for_projection():
    payload = build_graph_artifact_payload(_verbose_graph_fixture())
    edge = payload.compact_graph["edges"][0]
    assert edge["semantic_observation"]["source_location"] == "shopping"
    assert edge["semantic_observation"]["completion_facts"] == ["products_sorted"]
