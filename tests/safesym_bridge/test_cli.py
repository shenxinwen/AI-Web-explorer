import json

from ai_web_explorer.safesym_bridge import cli
from ai_web_explorer.safesym_bridge.cli import main


def test_main_without_subcommand_prints_help():
    assert main([]) == 2


def test_main_graph_subcommand_writes_observed_graph(tmp_path):
    output_path = tmp_path / "observed_graph.json"

    exit_code = main(["graph", "--output", str(output_path)])

    assert exit_code == 0
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["schema_version"] == "web-observed-graph-v1"
    assert data["meta"]["app"] == "saucedemo"


def test_main_pddl_subcommand_writes_domain_and_problem(tmp_path):
    output_dir = tmp_path / "graph_pddl"

    exit_code = main(["pddl", "--output", str(output_dir)])

    assert exit_code == 0
    domain = (output_dir / "domain.pddl").read_text(encoding="utf-8")
    problem = (output_dir / "problem.pddl").read_text(encoding="utf-8")
    assert "(define (domain saucedemo)" in domain
    assert "(:action order_place_confirm" in domain
    assert "(:domain saucedemo)" in problem
    assert "(at login)" in problem
    assert "(state_order_created)" in problem


def test_main_explore_graph_subcommand_runs_explorer(tmp_path, monkeypatch):
    output_path = tmp_path / "explored_graph.json"
    calls = []

    async def fake_run_saucedemo_explored_graph(path, *, headless=True):
        calls.append((path, headless))
        path.write_text('{"meta": {"app": "saucedemo"}}', encoding="utf-8")
        return path

    monkeypatch.setattr(
        cli,
        "run_saucedemo_explored_graph",
        fake_run_saucedemo_explored_graph,
    )

    exit_code = main(["explore-graph", "--output", str(output_path), "--headed"])

    assert exit_code == 0
    assert calls == [(output_path, False)]


def test_main_explore_pddl_subcommand_runs_explorer(tmp_path, monkeypatch):
    output_dir = tmp_path / "explored_pddl"
    calls = []

    async def fake_run_saucedemo_explored_pddl(path, *, headless=True):
        calls.append((path, headless))
        path.mkdir(parents=True, exist_ok=True)
        (path / "domain.pddl").write_text(
            "(define (domain saucedemo))",
            encoding="utf-8",
        )
        (path / "problem.pddl").write_text(
            "(define (problem saucedemo-problem))",
            encoding="utf-8",
        )
        return path

    monkeypatch.setattr(
        cli,
        "run_saucedemo_explored_pddl",
        fake_run_saucedemo_explored_pddl,
    )

    exit_code = main(["explore-pddl", "--output", str(output_dir)])

    assert exit_code == 0
    assert calls == [(output_dir, True)]


def test_main_capability_graph_subcommand_writes_capability_graph(tmp_path):
    output_path = tmp_path / "capability_graph.json"

    exit_code = main(["capability-graph", "--output", str(output_path)])

    assert exit_code == 0
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["schema_version"] == "web-capability-graph-v1"
    assert data["meta"]["app"] == "saucedemo"
    assert "states" in data
    assert "transitions" in data


def test_main_explore_capability_graph_subcommand_runs_explorer(tmp_path, monkeypatch):
    output_path = tmp_path / "explored_capability_graph.json"
    calls = []

    async def fake_run_saucedemo_explored_capability_graph(path, *, headless=True):
        calls.append((path, headless))
        path.write_text(
            '{"meta": {"schema_version": "web-capability-graph-v1"}}',
            encoding="utf-8",
        )
        return path

    monkeypatch.setattr(
        cli,
        "run_saucedemo_explored_capability_graph",
        fake_run_saucedemo_explored_capability_graph,
    )

    exit_code = main(
        ["explore-capability-graph", "--output", str(output_path), "--headed"]
    )

    assert exit_code == 0
    assert calls == [(output_path, False)]


def test_main_web_kobe_graph_subcommand_writes_graph(monkeypatch, tmp_path):
    output = tmp_path / "web_kobe_graph.json"

    from ai_web_explorer.safesym_bridge.web_kobe_graph import WebKobeGraph

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

    from ai_web_explorer.safesym_bridge.web_kobe_graph import WebKobeGraph

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
