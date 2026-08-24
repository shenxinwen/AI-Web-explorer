import json
import subprocess
from pathlib import Path

import pytest

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
