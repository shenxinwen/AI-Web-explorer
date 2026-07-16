import json

from ai_web_explorer.grounded_web.capability_graph import (
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.safesym_bridge import cli
from ai_web_explorer.safesym_bridge.cli import main


def test_main_without_subcommand_prints_help():
    assert main([]) == 2


def test_main_web_kobe_graph_subcommand_writes_graph(monkeypatch, tmp_path):
    output = tmp_path / "web_kobe_graph.json"

    from ai_web_explorer.grounded_web.graph import WebKobeGraph

    def fake_build_debug_web_kobe_graph():
        return WebKobeGraph(
            app="debug",
            start_node_id="start",
            total_steps_completed=0,
            nodes=[],
            edges=[],
        )

    monkeypatch.setattr(cli, "build_debug_web_kobe_graph", fake_build_debug_web_kobe_graph)

    assert main(["web-kobe-graph", "--output", str(output)]) == 0
    assert output.exists()
    assert "web-kobe-graph-v1" in output.read_text(encoding="utf-8")


def test_main_web_kobe_pddl_subcommand_writes_domain_and_problem(
    monkeypatch,
    tmp_path,
):
    output = tmp_path / "web_kobe_pddl"

    from ai_web_explorer.grounded_web.graph import WebKobeGraph

    def fake_build_debug_web_kobe_graph():
        return WebKobeGraph(
            app="debug",
            start_node_id="start",
            total_steps_completed=0,
            nodes=[],
            edges=[],
        )

    class FakeArtifacts:
        domain = "(define (domain web-kobe))"
        problem = "(define (problem web-kobe-problem))"

    monkeypatch.setattr(cli, "build_debug_web_kobe_graph", fake_build_debug_web_kobe_graph)
    monkeypatch.setattr(
        cli,
        "compile_web_kobe_graph_to_pddl",
        lambda graph, goal_node_id: FakeArtifacts(),
    )

    assert (
        main(["web-kobe-pddl", "--output", str(output), "--goal-node", "start"])
        == 0
    )
    assert (output / "domain.pddl").read_text(encoding="utf-8") == FakeArtifacts.domain
    assert (output / "problem.pddl").read_text(encoding="utf-8") == FakeArtifacts.problem


def test_main_web_kobe_explore_subcommand_runs_playwright_runner(
    tmp_path,
    monkeypatch,
):
    output_path = tmp_path / "web_kobe_explored_graph.json"
    calls = []

    async def fake_run_web_kobe_exploration(
        url,
        output_path_arg,
        *,
        app_name="web",
        page_id=None,
        steps=1,
        headless=True,
    ):
        calls.append((url, output_path_arg, app_name, page_id, steps, headless))
        output_path_arg.write_text(
            '{"meta": {"schema_version": "web-kobe-graph-v1"}}',
            encoding="utf-8",
        )
        return output_path_arg

    monkeypatch.setattr(
        cli,
        "run_web_kobe_exploration",
        fake_run_web_kobe_exploration,
    )

    exit_code = main(
        [
            "web-kobe-explore",
            "--url",
            "http://127.0.0.1:8000/index.html",
            "--output",
            str(output_path),
            "--app-name",
            "fixture",
            "--page-id",
            "fixture_shop",
            "--steps",
            "2",
            "--headed",
        ]
    )

    assert exit_code == 0
    assert calls == [
        (
            "http://127.0.0.1:8000/index.html",
            output_path,
            "fixture",
            "fixture_shop",
            2,
            False,
        )
    ]


def test_main_web_kobe_pddl_from_graph_writes_domain_and_problem(tmp_path):
    graph_path = tmp_path / "web_kobe_graph.json"
    output_dir = tmp_path / "web_kobe_pddl"
    graph = WebKobeGraph(
        app="example",
        start_node_id="empty",
        total_steps_completed=1,
        nodes=[
            WebKobeNode(
                node_id="empty",
                page_description="empty page",
                page_frame=PageFrame(
                    page_id="empty",
                    page_type="listing",
                    url="https://example.test",
                    url_pattern="https://example.test",
                    title="empty",
                ),
                state_schema={"cart_count": [0]},
                last_state_snapshot={"cart_count": 0},
            ),
            WebKobeNode(
                node_id="filled",
                page_description="filled page",
                page_frame=PageFrame(
                    page_id="filled",
                    page_type="listing",
                    url="https://example.test",
                    url_pattern="https://example.test",
                    title="filled",
                ),
                state_schema={"cart_count": [1]},
                last_state_snapshot={"cart_count": 1},
            ),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="empty",
                target_node_id="filled",
                instruction="add to cart",
                action=BrowserAction("click", "button.add", "add_to_cart"),
                capability=None,
                target_observation="filled cart",
                observed_delta=[
                    ObservedDelta("cart_count", 0, 1, "state_indicator_change")
                ],
                schema_delta={"cart_count": {"before": 0, "after": 1}},
                execution_trace=ExecutionTrace(
                    "click",
                    "button.add",
                    "add",
                    {},
                    "empty",
                    "filled",
                    True,
                ),
            )
        ],
    )
    graph_path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    exit_code = main(
        [
            "web-kobe-pddl-from-graph",
            "--graph",
            str(graph_path),
            "--output",
            str(output_dir),
            "--goal-node",
            "filled",
        ]
    )

    assert exit_code == 0
    assert (
        "(:action add_to_cart"
        in (output_dir / "domain.pddl").read_text(encoding="utf-8")
    )
    assert (
        "(:goal (and (at_filled)))"
        in (output_dir / "problem.pddl").read_text(encoding="utf-8")
    )


def test_main_web_kobe_pddl_smoke_writes_report(tmp_path):
    graph_path = tmp_path / "web_kobe_graph.json"
    output_dir = tmp_path / "web_kobe_smoke"
    graph = WebKobeGraph(
        app="example",
        start_node_id="empty",
        total_steps_completed=1,
        nodes=[
            WebKobeNode(
                node_id="empty",
                page_description="empty page",
                page_frame=PageFrame(
                    page_id="empty",
                    page_type="listing",
                    url="https://example.test",
                    url_pattern="https://example.test",
                    title="empty",
                ),
                state_schema={"cart_count": [0]},
                last_state_snapshot={"cart_count": 0},
            ),
            WebKobeNode(
                node_id="filled",
                page_description="filled page",
                page_frame=PageFrame(
                    page_id="filled",
                    page_type="listing",
                    url="https://example.test",
                    url_pattern="https://example.test",
                    title="filled",
                ),
                state_schema={"cart_count": [1]},
                last_state_snapshot={"cart_count": 1},
            ),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="empty",
                target_node_id="filled",
                instruction="add to cart",
                action=BrowserAction("click", "button.add", "add_to_cart"),
                capability=None,
                target_observation="filled cart",
                observed_delta=[
                    ObservedDelta("cart_count", 0, 1, "state_indicator_change")
                ],
                schema_delta={"cart_count": {"before": 0, "after": 1}},
                execution_trace=ExecutionTrace(
                    "click",
                    "button.add",
                    "add",
                    {},
                    "empty",
                    "filled",
                    True,
                ),
                status="succeeded_with_observed_change",
            )
        ],
    )
    graph_path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    exit_code = main(
        [
            "web-kobe-pddl-smoke",
            "--graph",
            str(graph_path),
            "--output",
            str(output_dir),
            "--goal-node",
            "filled",
        ]
    )

    assert exit_code == 0
    assert (output_dir / "domain.pddl").exists()
    assert (output_dir / "problem.pddl").exists()
    report = json.loads((output_dir / "smoke_report.json").read_text(encoding="utf-8"))
    assert report["planning_ready"] is True
    assert report["safety_trigger_expected"] is False
