import json

from ai_web_explorer.grounded_web.capability_graph import (
    ExecutionTrace,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.semantic_model import SemanticObservation
from ai_web_explorer.safesym_bridge.web_kobe_pddl_projector import (
    load_web_kobe_graph_json,
)


def _edge(semantic_observation=None):
    return WebKobeEdge(
        source_node_id="start",
        target_node_id="after",
        instruction="observe",
        action=BrowserAction("click", None, "observe"),
        capability=None,
        target_observation="after",
        observed_delta=[],
        schema_delta=None,
        execution_trace=ExecutionTrace(
            "click",
            None,
            None,
            {},
            "before",
            "after",
            True,
        ),
        semantic_observation=semantic_observation,
    )


def _graph_dict(edge=None):
    graph = WebKobeGraph(
        app="test",
        start_node_id="start",
        total_steps_completed=1,
        nodes=[
            WebKobeNode(
                node_id="start",
                page_description="start",
                page_frame=PageFrame(
                    page_id="start",
                    page_type="listing",
                    url="https://example.test/start",
                    url_pattern="https://example.test/start",
                    title="Start",
                ),
                state_schema={},
                last_state_snapshot={},
            ),
            WebKobeNode(
                node_id="after",
                page_description="after",
                page_frame=PageFrame(
                    page_id="after",
                    page_type="listing",
                    url="https://example.test/after",
                    url_pattern="https://example.test/after",
                    title="After",
                ),
                state_schema={},
                last_state_snapshot={},
            ),
        ],
        edges=[edge or _edge()],
    )
    return graph.to_dict()


def _write_graph(tmp_path, edge):
    path = tmp_path / "graph.json"
    path.write_text(json.dumps(_graph_dict(edge)), encoding="utf-8")
    return path


def test_semantic_observation_round_trips_through_edge_json(tmp_path):
    observation = SemanticObservation(
        action_role="presentation_capability",
        source_location="shopping",
        target_location="shopping",
        completion_facts=["products_sorted"],
        candidate_required_facts=[],
        preserved_facts=[],
        evidence=["Product order visibly changed."],
        confidence=0.93,
    )
    loaded = load_web_kobe_graph_json(_write_graph(tmp_path, _edge(observation)))
    assert loaded.edges[0].semantic_observation == observation


def test_historical_edge_without_semantic_observation_loads(tmp_path):
    data = _graph_dict()
    data["edges"][0].pop("semantic_observation", None)
    path = tmp_path / "historical.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = load_web_kobe_graph_json(path)
    assert loaded.edges[0].semantic_observation is None
