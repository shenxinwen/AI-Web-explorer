from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.grounded_web.capability_graph import Evidence, ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.planning_abstraction import (
    build_planning_state_graph,
)


def _node(node_id: str, *actions: str) -> WebKobeNode:
    evidence = [Evidence(source="test")]
    return WebKobeNode(
        node_id=node_id,
        page_description=node_id,
        page_frame=PageFrame(
            page_id=node_id,
            page_type="page",
            url=f"https://example.test/{node_id}",
            url_pattern=f"https://example.test/{node_id}",
            title=node_id,
            evidence=evidence,
        ),
        state_schema={},
        last_state_snapshot={},
        business_affordances=[BusinessAffordance(action) for action in actions],
        reference_observation=ReferenceObservation(
            url=f"https://example.test/{node_id}", title=node_id
        ),
        evidence=evidence,
    )


def _edge(
    source: str,
    target: str,
    action_name: str,
    *,
    visual_change_kind: str = "unknown",
    planning_delta: PlanningDelta | None = None,
    success: bool = True,
    visit_count: int = 1,
) -> WebKobeEdge:
    return WebKobeEdge(
        source_node_id=source,
        target_node_id=target,
        instruction=action_name,
        action=BrowserAction("business_intent", None, action_name),
        capability=None,
        target_observation=target,
        observed_delta=[],
        schema_delta=None,
        execution_trace=ExecutionTrace(
            concrete_action_kind="business_intent",
            concrete_locator=None,
            concrete_target_sample=action_name,
            input_values_used={},
            before_observation_id=source,
            after_observation_id=target,
            success=success,
            error=None if success else "failed",
        ),
        planning_delta=planning_delta,
        visual_change_kind=visual_change_kind,
        visit_count=visit_count,
        status="verified" if success else "failed_execution",
    )


def _experiment_graph() -> WebKobeGraph:
    nodes = [
        _node("O0", "filter"),
        _node("O1", "clear"),
        _node("O2", "sort"),
        _node("O3", "add_to_cart"),
        _node("O4", "add_to_cart"),
        _node("O5", "open_unknown"),
        _node("O6"),
    ]
    edges = [
        _edge("O0", "O1", "filter", visual_change_kind="presentation"),
        _edge("O1", "O2", "clear", visual_change_kind="presentation"),
        _edge("O2", "O3", "sort", visual_change_kind="presentation"),
        _edge(
            "O3",
            "O4",
            "add_to_cart",
            planning_delta=PlanningDelta(verified_added_facts=["cart_has_items"]),
        ),
        _edge(
            "O4",
            "O5",
            "add_to_cart",
            visual_change_kind="state_indicator",
            planning_delta=PlanningDelta(preserved_profile_facts=["cart_has_items"]),
        ),
        _edge("O5", "O6", "open_unknown", visual_change_kind="surface"),
    ]
    return WebKobeGraph(
        app="example",
        start_node_id="O0",
        total_steps_completed=len(edges),
        nodes=nodes,
        edges=edges,
    )


def test_build_planning_state_graph_groups_only_observation_equivalent_states():
    graph = _experiment_graph()

    artifacts = build_planning_state_graph(graph)

    mapping = artifacts.report.raw_to_planning_node
    assert mapping["O0"] == mapping["O1"] == mapping["O2"] == mapping["O3"]
    assert mapping["O3"] != mapping["O4"]
    assert mapping["O4"] == mapping["O5"]
    assert mapping["O5"] != mapping["O6"]


def test_build_planning_state_graph_aggregates_observed_capabilities():
    artifacts = build_planning_state_graph(_experiment_graph())

    group_id = artifacts.report.raw_to_planning_node["O0"]
    planning_node = next(
        node for node in artifacts.planning_graph.nodes if node.node_id == group_id
    )
    assert [affordance.action_name for affordance in planning_node.business_affordances] == [
        "filter",
        "clear",
        "sort",
        "add_to_cart",
    ]
    capabilities = {
        item["action_name"]: item
        for item in artifacts.report.capabilities
        if item["planning_node_id"] == group_id
    }
    assert capabilities["filter"]["observed_node_ids"] == ["O0"]
    assert capabilities["clear"]["observed_node_ids"] == ["O1"]
    assert capabilities["sort"]["observed_node_ids"] == ["O2"]
    assert capabilities["add_to_cart"]["observed_node_ids"] == ["O3"]


def test_planning_abstraction_keeps_raw_graph_and_rejects_unsafe_grouping():
    graph = _experiment_graph()
    before = graph.to_dict()
    graph.edges[0]  # keep the fixture explicit for the raw identity assertion

    artifacts = build_planning_state_graph(graph)

    assert graph.to_dict() == before
    assert all(
        edge.source_node_id != edge.target_node_id
        or edge.source_node_id == artifacts.report.raw_to_planning_node["O0"]
        for edge in artifacts.raw_graph.edges
    )

    boundary_presentation = _edge(
        "A",
        "B",
        "toggle",
        visual_change_kind="presentation",
        planning_delta=PlanningDelta(verified_added_facts=["profile_fact"]),
    )
    surface = _edge("B", "C", "open", visual_change_kind="surface")
    unknown = _edge("C", "D", "unknown", visual_change_kind="unknown")
    failed = _edge(
        "D",
        "E",
        "failed",
        visual_change_kind="presentation",
        success=False,
    )
    unsafe = WebKobeGraph(
        app="example",
        start_node_id="A",
        total_steps_completed=4,
        nodes=[_node(name) for name in "ABCDE"],
        edges=[boundary_presentation, surface, unknown, failed],
    )

    mapping = build_planning_state_graph(unsafe).report.raw_to_planning_node
    assert mapping["A"] != mapping["B"]
    assert mapping["B"] != mapping["C"]
    assert mapping["C"] != mapping["D"]
    assert mapping["D"] != mapping["E"]


def test_ambiguous_action_embedding_does_not_choose_an_earliest_alias():
    graph = WebKobeGraph(
        app="example",
        start_node_id="A",
        total_steps_completed=0,
        nodes=[_node("A", "sort_by_name", "order_items_alphabetically")],
        edges=[],
    )

    vectors = {
        "intent: sort_by_name\nlabel: \ntarget_hint: ": [1.0, 0.0],
        "intent: order_items_alphabetically\nlabel: \ntarget_hint: ": [0.85, 0.526],
    }
    artifacts = build_planning_state_graph(graph, embedding_provider=vectors.get)

    assert artifacts.report.ambiguous_actions == [
        "sort_by_name",
        "order_items_alphabetically",
    ]
    assert [
        affordance.action_name
        for affordance in artifacts.planning_graph.nodes[0].business_affordances
    ] == ["sort_by_name", "order_items_alphabetically"]
