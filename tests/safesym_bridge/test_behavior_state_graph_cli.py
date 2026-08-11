import json
from dataclasses import replace

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import (
    BusinessAffordance,
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.safesym_bridge.cli import main
from ai_web_explorer.safesym_bridge import cli as cli_module
from ai_web_explorer.safesym_bridge.graph_artifacts import (
    build_graph_artifact_payload,
)


def _graph_fixture() -> WebKobeGraph:
    def node(node_id: str, affordances=()):
        return WebKobeNode(
            node_id=node_id,
            page_description=node_id,
            page_frame=PageFrame(
                page_id=node_id,
                page_type=node_id,
                url=f"https://example.test/{node_id}",
                url_pattern=f"https://example.test/{node_id}",
                title=node_id,
            ),
            state_schema={},
            last_state_snapshot={},
            node_label=node_id,
            business_affordances=list(affordances),
        )

    return WebKobeGraph(
        app="example",
        start_node_id="listing",
        total_steps_completed=1,
        nodes=[node("listing", [BusinessAffordance("view_details")]), node("details")],
        edges=[
            WebKobeEdge(
                source_node_id="listing",
                target_node_id="details",
                instruction="view_details",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "view_details",
                    canonical_action_name="view_details",
                    supporting_facts=["visible_control"],
                ),
                capability=None,
                target_observation="details",
                observed_delta=[],
                schema_delta=None,
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "view_details",
                    {},
                    "listing",
                    "details",
                    True,
                ),
            )
        ],
    )


def test_phase_a_cli_writes_raw_planning_report_and_domain_only(tmp_path, monkeypatch):
    graph = _graph_fixture()
    graph_path = tmp_path / "raw.json"
    graph_path.write_text(
        json.dumps(graph.to_dict(), ensure_ascii=False),
        encoding="utf-8",
    )
    output_dir = tmp_path / "phase_a"
    seen_texts = []

    def provider(text):
        seen_texts.append(text)
        return [1.0, 0.0]

    monkeypatch.setattr(cli_module, "create_embedding_provider_from_env", lambda: provider)

    assert main(
        [
            "web-kobe-phase-a",
            "--graph",
            str(graph_path),
            "--output",
            str(output_dir),
        ]
    ) == 0

    assert seen_texts
    assert any("view_details" in text for text in seen_texts)

    assert {
        path.name for path in output_dir.iterdir()
    } == {
        "raw_graph.json",
        "planning_graph.json",
        "planning_abstraction_report.json",
        "projection_report.json",
        "domain.pddl",
    }
    assert json.loads((output_dir / "raw_graph.json").read_text(encoding="utf-8")) == graph.to_dict()
    domain = (output_dir / "domain.pddl").read_text(encoding="utf-8")
    projection = json.loads(
        (output_dir / "projection_report.json").read_text(encoding="utf-8")
    )
    assert "(:types location)" in domain
    assert "(at ?location - location)" in domain
    assert projection["schema_version"] == "location-pddl-projection-v1"
    assert not (output_dir / "problem.pddl").exists()


def test_phase_a_compact_input_is_semantically_equivalent_and_raw_shape_is_preserved(
    tmp_path, monkeypatch
):
    graph = _graph_fixture()
    full_input = graph.to_dict()
    compact_input = build_graph_artifact_payload(graph).compact_graph
    full_path = tmp_path / "full.json"
    compact_path = tmp_path / "compact.json"
    full_path.write_text(json.dumps(full_input), encoding="utf-8")
    compact_path.write_text(json.dumps(compact_input), encoding="utf-8")
    full_output = tmp_path / "full_phase_a"
    compact_output = tmp_path / "compact_phase_a"

    monkeypatch.setattr(
        cli_module,
        "create_embedding_provider_from_env",
        lambda: (lambda text: [1.0, 0.0]),
    )

    for graph_path, output_dir in (
        (full_path, full_output),
        (compact_path, compact_output),
    ):
        assert main(
            [
                "web-kobe-phase-a",
                "--graph",
                str(graph_path),
                "--output",
                str(output_dir),
            ]
        ) == 0

    compact_raw = json.loads(
        (compact_output / "raw_graph.json").read_text(encoding="utf-8")
    )
    assert compact_raw == compact_input
    assert not (compact_output / "graph_evidence.json").exists()

    full_planning = json.loads(
        (full_output / "planning_graph.json").read_text(encoding="utf-8")
    )
    compact_planning = json.loads(
        (compact_output / "planning_graph.json").read_text(encoding="utf-8")
    )
    assert [node["node_id"] for node in full_planning["nodes"]] == [
        node["node_id"] for node in compact_planning["nodes"]
    ]
    assert [
        (edge["source_node_id"], edge["action"]["semantic_id"], edge["target_node_id"])
        for edge in full_planning["edges"]
    ] == [
        (edge["source_node_id"], edge["action"]["semantic_id"], edge["target_node_id"])
        for edge in compact_planning["edges"]
    ]
    assert (full_output / "domain.pddl").read_text(encoding="utf-8") == (
        compact_output / "domain.pddl"
    ).read_text(encoding="utf-8")
    assert json.loads(
        (full_output / "projection_report.json").read_text(encoding="utf-8")
    ) == json.loads(
        (compact_output / "projection_report.json").read_text(encoding="utf-8")
    )


def test_phase_a_cli_without_embedding_configuration_is_conservative(tmp_path, monkeypatch):
    graph = _graph_fixture()
    graph_path = tmp_path / "raw.json"
    graph_path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")
    output_dir = tmp_path / "phase_a"

    def missing_provider():
        raise ValueError("EMBEDDING_API_KEY is required")

    monkeypatch.setattr(cli_module, "create_embedding_provider_from_env", missing_provider)

    assert main(
        [
            "web-kobe-phase-a",
            "--graph",
            str(graph_path),
            "--output",
            str(output_dir),
        ]
    ) == 0
    report = json.loads(
        (output_dir / "planning_abstraction_report.json").read_text(encoding="utf-8")
    )
    assert report["ambiguous_actions"] == []


def test_phase_a_projects_only_cross_group_edges_and_keeps_capability_self_loop(
    tmp_path,
    monkeypatch,
):
    graph = _graph_fixture()
    cart = replace(graph.nodes[1], node_id="cart", page_description="cart")
    boundary = WebKobeEdge(
        source_node_id="details",
        target_node_id="cart",
        instruction="add_to_cart",
        action=BrowserAction("business_intent", None, "add_to_cart"),
        capability=None,
        target_observation="cart",
        observed_delta=[],
        schema_delta=None,
        execution_trace=ExecutionTrace(
            "business_intent",
            None,
            "add_to_cart",
            {},
            "details",
            "cart",
            True,
        ),
        planning_delta=PlanningDelta(verified_added_facts=["cart_has_items"]),
    )
    graph = replace(
        graph,
        nodes=[graph.nodes[0], graph.nodes[1], cart],
        edges=[replace(graph.edges[0], visual_change_kind="presentation"), boundary],
    )
    graph_path = tmp_path / "raw.json"
    graph_path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")
    output_dir = tmp_path / "phase_a"
    monkeypatch.setattr(
        cli_module,
        "create_embedding_provider_from_env",
        lambda: (_ for _ in ()).throw(ValueError("missing embedding config")),
    )

    assert main(
        ["web-kobe-phase-a", "--graph", str(graph_path), "--output", str(output_dir)]
    ) == 0

    planning = json.loads((output_dir / "planning_graph.json").read_text())
    domain = (output_dir / "domain.pddl").read_text(encoding="utf-8")
    assert any(
        edge["source_node_id"] == edge["target_node_id"]
        and edge["action"]["semantic_id"] == "view_details"
        for edge in planning["edges"]
    )
    assert "(:action add_to_cart" in domain
    assert "(:action view_details" not in domain
    assert "cart_has_items" not in domain
    assert "visible_control" not in domain


def test_phase_a_cli_keeps_rejected_source_edges_only_in_raw_artifacts(
    tmp_path,
    monkeypatch,
):
    graph = _graph_fixture()
    incomplete_source = WebKobeNode(
        node_id="incomplete",
        page_description="incomplete",
        page_frame=PageFrame(
            page_id="incomplete",
            page_type="incomplete",
            url="https://example.test/incomplete",
            url_pattern="https://example.test/incomplete",
            title="incomplete",
        ),
        state_schema={},
        last_state_snapshot={},
        node_label="incomplete",
        business_affordances=[BusinessAffordance("unexecuted_action")],
    )
    rejected_edge = WebKobeEdge(
        source_node_id="incomplete",
        target_node_id="details",
        instruction="different_action",
        action=BrowserAction(
            "business_intent",
            None,
            "different_action",
            canonical_action_name="different_action",
        ),
        capability=None,
        target_observation="details",
        observed_delta=[],
        schema_delta=None,
        execution_trace=ExecutionTrace(
            "business_intent",
            None,
            "different_action",
            {},
            "incomplete",
            "details",
            True,
        ),
    )
    graph = replace(
        graph,
        total_steps_completed=2,
        nodes=[*graph.nodes, incomplete_source],
        edges=[*graph.edges, rejected_edge],
    )
    graph_path = tmp_path / "raw.json"
    graph_path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")
    output_dir = tmp_path / "phase_a"

    monkeypatch.setattr(
        cli_module,
        "create_embedding_provider_from_env",
        lambda: (_ for _ in ()).throw(ValueError("missing embedding config")),
    )

    assert main(
        [
            "web-kobe-phase-a",
            "--graph",
            str(graph_path),
            "--output",
            str(output_dir),
        ]
    ) == 0

    raw = json.loads((output_dir / "raw_graph.json").read_text(encoding="utf-8"))
    planning = json.loads(
        (output_dir / "planning_graph.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (output_dir / "planning_abstraction_report.json").read_text(encoding="utf-8")
    )
    domain = (output_dir / "domain.pddl").read_text(encoding="utf-8")

    assert rejected_edge.to_dict() in raw["edges"]
    assert any(
        edge["source_node_id"] == "incomplete" for edge in planning["edges"]
    )
    assert report["raw_to_planning_node"]["incomplete"] == "incomplete"
    assert "(:action different_action" in domain
