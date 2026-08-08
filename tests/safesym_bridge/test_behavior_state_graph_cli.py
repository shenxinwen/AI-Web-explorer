import json

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
