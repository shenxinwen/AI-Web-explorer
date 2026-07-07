import json

from ai_web_explorer.safesym_bridge import cli
from ai_web_explorer.safesym_bridge.cli import build_saucedemo_fsm, main


def test_build_saucedemo_fsm_contains_required_order_action():
    fsm = build_saucedemo_fsm()
    data = fsm.to_dict()
    actions = [action for page in data["pages"] for action in page["actions"]]

    assert any(action["id"] == "order_place_confirm" for action in actions)


def test_main_writes_json_file(tmp_path):
    output_path = tmp_path / "saucedemo_fsm.json"

    exit_code = main(["--output", str(output_path)])

    assert exit_code == 0
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["app"] == "saucedemo"
    assert data["meta"]["initial_page_id"] == "login"
    assert data["meta"]["terminal_pages"] == ["checkout_complete"]


def test_main_fixed_subcommand_writes_json_file(tmp_path):
    output_path = tmp_path / "fixed.json"

    exit_code = main(["fixed", "--output", str(output_path)])

    assert exit_code == 0
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["meta"]["app"] == "saucedemo"


def test_main_observed_subcommand_runs_browser_flow(tmp_path, monkeypatch):
    output_path = tmp_path / "observed.json"
    calls = []

    async def fake_run_saucedemo_observed_flow(path, *, headless=True):
        calls.append((path, headless))
        path.write_text('{"ok": true}', encoding="utf-8")
        return path

    monkeypatch.setattr(
        cli,
        "run_saucedemo_observed_flow",
        fake_run_saucedemo_observed_flow,
    )

    exit_code = main(["observed", "--output", str(output_path), "--headed"])

    assert exit_code == 0
    assert calls == [(output_path, False)]
    assert json.loads(output_path.read_text(encoding="utf-8")) == {"ok": True}


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
