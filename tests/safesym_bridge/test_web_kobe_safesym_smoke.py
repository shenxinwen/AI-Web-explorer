import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.safesym_bridge.surface_pddl import (
    compile_surface_domain,
    compile_surface_problem,
)
from ai_web_explorer.safesym_bridge.web_kobe_safesym_smoke import (
    _env_for_safesym,
    _parse_command,
    analyze_web_kobe_safesym_smoke,
    write_web_kobe_safesym_smoke,
)


def _write_base_pddl(task_dir: Path) -> None:
    task_dir.mkdir(parents=True)
    (task_dir / "domain.pddl").write_text(
        "\n".join(
            [
                "(define (domain web_kobe_trace)",
                "  (:requirements :strips)",
                "  (:predicates (state_initial) (state_goal))",
                "  (:action go_goal",
                "    :parameters ()",
                "    :precondition (state_initial)",
                "    :effect (and (not (state_initial)) (state_goal))",
                "  )",
                ")",
            ]
        ),
        encoding="utf-8",
    )
    (task_dir / "problem.pddl").write_text(
        "\n".join(
            [
                "(define (problem web_kobe_trace_problem)",
                "  (:domain web_kobe_trace)",
                "  (:init (state_initial))",
                "  (:goal (state_goal))",
                ")",
            ]
        ),
        encoding="utf-8",
    )


class FakeSafeSymRunner:
    def __init__(self, task_dir: Path):
        self.task_dir = task_dir
        self.commands: list[list[str]] = []

    def __call__(self, command, **kwargs):
        command = [str(item) for item in command]
        self.commands.append(command)
        if command[-1] == "parse":
            return subprocess.CompletedProcess(command, 0, "parse ok", "")
        if "safeww.cli.inject_safety" in command:
            (self.task_dir / "safe_domain.pddl").write_text(
                (self.task_dir / "domain.pddl").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            (self.task_dir / "safe_problem.pddl").write_text(
                (self.task_dir / "problem.pddl").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, "Processed 1/1 tasks", "")
        if "safeww.cli.solve" in command and "--safe" not in command:
            (self.task_dir / "sas_plan").write_text(
                "(go_goal )\n; cost = 1 (unit cost)\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, "Solved 1/1 tasks", "")
        if "safeww.cli.solve" in command and "--safe" in command:
            (self.task_dir / "safe_sas_plan").write_text(
                "(go_goal )\n; cost = 1 (unit cost)\n",
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, "Solved 1/1 tasks", "")
        raise AssertionError(f"Unexpected command: {command}")


def test_analyze_web_kobe_safesym_smoke_reports_success_without_inserted_checks(
    tmp_path,
):
    task_dir = tmp_path / "task"
    _write_base_pddl(task_dir)
    rules = tmp_path / "rules.json"
    rules.write_text("[]", encoding="utf-8")
    fast_downward = tmp_path / "fast-downward.py"
    fast_downward.write_text("# fake", encoding="utf-8")
    runner = FakeSafeSymRunner(task_dir)

    report = analyze_web_kobe_safesym_smoke(
        task_dir,
        safesym_root=tmp_path / "SafeSym",
        rules=rules,
        fast_downward=fast_downward,
        runner=runner,
        python_executable="python",
    )

    data = report.to_dict()
    assert data["task_dir"] == str(task_dir.resolve())
    assert data["safesym_parse_ready"] is True
    assert data["safety_injection_ready"] is True
    assert data["base_plan_ready"] is True
    assert data["safe_plan_ready"] is True
    assert data["safety_actions_inserted"] is False
    assert data["safety_action_names"] == []
    assert data["failure_reasons"] == []
    assert any("safeww.cli.inject_safety" in command for command in runner.commands)
    assert any(str(task_dir.resolve()) in command for command in runner.commands)
    assert any("safeww.cli.solve" in command for command in runner.commands)


def test_surface_pddl_safe_sym_smoke_handles_sibling_and_deep_edges(tmp_path):
    graph = WebKobeGraph(
        app="fixture",
        start_node_id="shopping",
        total_steps_completed=3,
        nodes=[
            WebKobeNode(
                node_id="shopping",
                page_description="shopping",
                page_frame=PageFrame(
                    page_id="shopping",
                    page_type="shopping",
                    url="https://fixture.test/shop",
                    url_pattern="https://fixture.test/shop",
                    title="shopping",
                ),
                state_schema={},
                last_state_snapshot={},
                node_label="shopping",
            ),
            WebKobeNode(
                node_id="deep",
                page_description="deep",
                page_frame=PageFrame(
                    page_id="deep",
                    page_type="deep",
                    url="https://fixture.test/shop",
                    url_pattern="https://fixture.test/shop",
                    title="deep",
                ),
                state_schema={},
                last_state_snapshot={},
                node_label="deep",
            ),
        ],
        edges=[],
    )
    for source, target, action in [
        ("shopping", "shopping", "filter"),
        ("shopping", "shopping", "sort"),
        ("shopping", "deep", "open_deep"),
    ]:
        graph.edges.append(
            WebKobeEdge(
                source_node_id=source,
                target_node_id=target,
                instruction=action,
                action=BrowserAction("click", f"#{action}", action),
                capability=None,
                target_observation=target,
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "click", f"#{action}", action, {}, source, target, True
                ),
                status="succeeded_with_navigation"
                if source != target
                else "succeeded_with_observed_change",
            )
        )
    domain_result = compile_surface_domain(graph)
    problem_result = compile_surface_problem(graph, goal_node_id="deep")
    task_dir = tmp_path / "surface_task"
    task_dir.mkdir()
    (task_dir / "domain.pddl").write_text(domain_result.domain, encoding="utf-8")
    (task_dir / "problem.pddl").write_text(problem_result.problem, encoding="utf-8")
    rules = tmp_path / "rules.json"
    rules.write_text("[]", encoding="utf-8")
    fast_downward = tmp_path / "fast-downward.py"
    fast_downward.write_text("# fake", encoding="utf-8")
    runner = FakeSafeSymRunner(task_dir)

    report = analyze_web_kobe_safesym_smoke(
        task_dir,
        safesym_root=tmp_path / "SafeSym",
        rules=rules,
        fast_downward=fast_downward,
        runner=runner,
        python_executable="python",
    )

    assert report.safesym_parse_ready is True
    assert report.safety_injection_ready is True
    assert report.base_plan_ready is True
    assert report.safe_plan_ready is True


def test_real_safesym_parser_accepts_surface_pddl(tmp_path):
    safesym_root = Path(
        os.environ.get("SAFESYM_ROOT", r"C:\Users\moon\Desktop\Projects\SafeSym")
    )
    if not safesym_root.exists():
        pytest.skip("SafeSym checkout is unavailable")

    graph = WebKobeGraph(
        app="fixture",
        start_node_id="start",
        total_steps_completed=0,
        nodes=[
            WebKobeNode(
                node_id="start",
                page_description="start",
                page_frame=PageFrame(
                    page_id="start",
                    page_type="start",
                    url="https://fixture.test/",
                    url_pattern="https://fixture.test/",
                    title="start",
                ),
                state_schema={},
                last_state_snapshot={},
                node_label="start",
            )
        ],
        edges=[],
    )
    task_dir = tmp_path / "surface_task"
    task_dir.mkdir()
    (task_dir / "domain.pddl").write_text(
        compile_surface_domain(graph, domain_name="Real Surface").domain,
        encoding="utf-8",
    )
    (task_dir / "problem.pddl").write_text(
        compile_surface_problem(
            graph,
            goal_node_id="start",
            domain_name="Real Surface",
        ).problem,
        encoding="utf-8",
    )

    result = subprocess.run(
        _parse_command(sys.executable, task_dir),
        cwd=str(task_dir),
        env=_env_for_safesym(safesym_root),
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr


def test_write_web_kobe_safesym_smoke_writes_report(tmp_path):
    task_dir = tmp_path / "task"
    _write_base_pddl(task_dir)
    rules = tmp_path / "rules.json"
    rules.write_text("[]", encoding="utf-8")
    runner = FakeSafeSymRunner(task_dir)

    result = write_web_kobe_safesym_smoke(
        task_dir,
        safesym_root=tmp_path / "SafeSym",
        rules=rules,
        runner=runner,
        python_executable="python",
    )

    report_path = task_dir / "safesym_smoke_report.json"
    assert report_path.exists()
    data = json.loads(report_path.read_text(encoding="utf-8"))
    assert data["safesym_parse_ready"] is True
    assert data["safety_injection_ready"] is True
    assert data["base_plan_ready"] is False
    assert data["safe_plan_ready"] is False
    assert result.report.safety_injection_ready is True


def test_analyze_web_kobe_safesym_smoke_resolves_relative_task_dir(
    monkeypatch,
    tmp_path,
):
    monkeypatch.chdir(tmp_path)
    task_dir = Path("task")
    _write_base_pddl(task_dir)
    rules = Path("rules.json")
    rules.write_text("[]", encoding="utf-8")
    runner = FakeSafeSymRunner(task_dir.resolve())

    report = analyze_web_kobe_safesym_smoke(
        task_dir,
        safesym_root=Path("SafeSym"),
        rules=rules,
        runner=runner,
        python_executable="python",
    )

    assert report.task_dir == str(task_dir.resolve())
    assert report.safesym_parse_ready is True
    assert any(str(task_dir.resolve()) in command for command in runner.commands)
