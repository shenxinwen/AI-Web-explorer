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


def test_phase_a_cli_writes_raw_canonical_report_and_domain_only(tmp_path, monkeypatch):
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
        "canonical_graph.json",
        "consolidation_report.json",
        "domain.pddl",
    }
    assert json.loads((output_dir / "raw_graph.json").read_text(encoding="utf-8")) == graph.to_dict()
    assert "view_details__from_listing" in (
        output_dir / "domain.pddl"
    ).read_text(encoding="utf-8")
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

    full_canonical = json.loads(
        (full_output / "canonical_graph.json").read_text(encoding="utf-8")
    )
    compact_canonical = json.loads(
        (compact_output / "canonical_graph.json").read_text(encoding="utf-8")
    )
    assert [node["node_id"] for node in full_canonical["nodes"]] == [
        node["node_id"] for node in compact_canonical["nodes"]
    ]
    assert [
        (edge["source_node_id"], edge["action"]["semantic_id"], edge["target_node_id"])
        for edge in full_canonical["edges"]
    ] == [
        (edge["source_node_id"], edge["action"]["semantic_id"], edge["target_node_id"])
        for edge in compact_canonical["edges"]
    ]
    assert (full_output / "domain.pddl").read_text(encoding="utf-8") == (
        compact_output / "domain.pddl"
    ).read_text(encoding="utf-8")


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
        (output_dir / "consolidation_report.json").read_text(encoding="utf-8")
    )
    assert report["action_normalizations"] == []


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
    canonical = json.loads(
        (output_dir / "canonical_graph.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (output_dir / "consolidation_report.json").read_text(encoding="utf-8")
    )
    domain = (output_dir / "domain.pddl").read_text(encoding="utf-8")

    assert rejected_edge.to_dict() in raw["edges"]
    assert any(
        edge["source_node_id"] == "incomplete" for edge in canonical["edges"]
    )
    assert "incomplete" not in report["rejected_nodes"]
    assert "different_action__from_incomplete" in domain
