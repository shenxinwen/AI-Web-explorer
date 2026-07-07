from ai_web_explorer.safesym_bridge import cli
from ai_web_explorer.safesym_bridge.cli import main


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


def test_main_without_subcommand_prints_help(capsys):
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "explore-graph" in captured.out
    assert "explore-pddl" in captured.out
