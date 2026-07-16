from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence


Runner = Callable[..., subprocess.CompletedProcess]


@dataclass(frozen=True)
class WebKobeSafeSymSmokeReport:
    task_dir: str
    safesym_root: str
    rules_path: str
    fast_downward_path: str | None = None
    safesym_parse_ready: bool = False
    safety_injection_ready: bool = False
    base_plan_ready: bool = False
    safe_plan_ready: bool = False
    safety_actions_inserted: bool = False
    safety_action_names: list[str] = field(default_factory=list)
    failure_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "task_dir": self.task_dir,
            "safesym_root": self.safesym_root,
            "rules_path": self.rules_path,
            "fast_downward_path": self.fast_downward_path,
            "safesym_parse_ready": self.safesym_parse_ready,
            "safety_injection_ready": self.safety_injection_ready,
            "base_plan_ready": self.base_plan_ready,
            "safe_plan_ready": self.safe_plan_ready,
            "safety_actions_inserted": self.safety_actions_inserted,
            "safety_action_names": list(self.safety_action_names),
            "failure_reasons": list(self.failure_reasons),
        }


@dataclass(frozen=True)
class WebKobeSafeSymSmokeResult:
    report: WebKobeSafeSymSmokeReport
    report_path: Path


def _env_for_safesym(safesym_root: Path) -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(safesym_root) if not existing else f"{safesym_root}{os.pathsep}{existing}"
    )
    return env


def _run(
    command: Sequence[str],
    *,
    runner: Runner,
    safesym_root: Path,
    cwd: Path,
) -> subprocess.CompletedProcess:
    return runner(
        list(command),
        cwd=str(cwd),
        env=_env_for_safesym(safesym_root),
        text=True,
        capture_output=True,
    )


def _parse_command(python_executable: str, task_dir: Path) -> list[str]:
    script = (
        "from pathlib import Path; "
        "from safeww.pddl.parser import parse_domain, parse_problem; "
        f"task=Path({str(task_dir)!r}); "
        "parse_domain((task/'domain.pddl').read_text(encoding='utf-8')); "
        "parse_problem((task/'problem.pddl').read_text(encoding='utf-8')); "
        "print('parse ok')"
    )
    return [python_executable, "-c", script, "parse"]


def _inject_command(
    python_executable: str,
    *,
    task_dir: Path,
    rules: Path,
) -> list[str]:
    return [
        python_executable,
        "-m",
        "safeww.cli.inject_safety",
        "--task-dir",
        str(task_dir),
        "--rules",
        str(rules),
    ]


def _solve_command(
    python_executable: str,
    *,
    task_dir: Path,
    fast_downward: Path,
    safe: bool,
) -> list[str]:
    command = [
        python_executable,
        "-m",
        "safeww.cli.solve",
        "--task-dir",
        str(task_dir),
        "--fast-downward",
        str(fast_downward),
    ]
    if safe:
        command.append("--safe")
    return command


def _safety_actions(task_dir: Path) -> list[str]:
    safe_domain = task_dir / "safe_domain.pddl"
    if not safe_domain.exists():
        return []
    text = safe_domain.read_text(encoding="utf-8")
    return sorted(
        name
        for name in re.findall(r"\(:action\s+([^\s()]+)", text)
        if name.startswith("check_")
    )


def _command_failure(prefix: str, result: subprocess.CompletedProcess) -> str:
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    detail = stderr or stdout
    if detail:
        return f"{prefix}: {detail[-500:]}"
    return prefix


def analyze_web_kobe_safesym_smoke(
    task_dir: Path | str,
    *,
    safesym_root: Path | str,
    rules: Path | str,
    fast_downward: Path | str | None = None,
    runner: Runner = subprocess.run,
    python_executable: str = sys.executable,
) -> WebKobeSafeSymSmokeReport:
    task_dir = Path(task_dir).resolve()
    safesym_root = Path(safesym_root).resolve()
    rules = Path(rules).resolve()
    fast_downward_path = (
        Path(fast_downward).resolve() if fast_downward is not None else None
    )
    reasons: list[str] = []

    domain = task_dir / "domain.pddl"
    problem = task_dir / "problem.pddl"
    if not domain.exists() or not problem.exists():
        reasons.append("task directory is missing domain.pddl or problem.pddl")
        return WebKobeSafeSymSmokeReport(
            task_dir=str(task_dir),
            safesym_root=str(safesym_root),
            rules_path=str(rules),
            fast_downward_path=str(fast_downward_path) if fast_downward_path else None,
            failure_reasons=reasons,
        )
    if not rules.exists():
        reasons.append("SafeSym rules file does not exist")
        return WebKobeSafeSymSmokeReport(
            task_dir=str(task_dir),
            safesym_root=str(safesym_root),
            rules_path=str(rules),
            fast_downward_path=str(fast_downward_path) if fast_downward_path else None,
            failure_reasons=reasons,
        )

    parse_result = _run(
        _parse_command(python_executable, task_dir),
        runner=runner,
        safesym_root=safesym_root,
        cwd=task_dir,
    )
    parse_ready = parse_result.returncode == 0
    if not parse_ready:
        reasons.append(_command_failure("SafeSym parser rejected PDDL", parse_result))

    injection_ready = False
    base_plan_ready = False
    safe_plan_ready = False
    if parse_ready:
        inject_result = _run(
            _inject_command(
                python_executable,
                task_dir=task_dir,
                rules=rules,
            ),
            runner=runner,
            safesym_root=safesym_root,
            cwd=task_dir,
        )
        injection_ready = (
            inject_result.returncode == 0
            and (task_dir / "safe_domain.pddl").exists()
            and (task_dir / "safe_problem.pddl").exists()
        )
        if not injection_ready:
            reasons.append(
                _command_failure("SafeSym safety injection failed", inject_result)
            )

    if fast_downward_path is not None and injection_ready:
        if not fast_downward_path.exists():
            reasons.append("Fast Downward executable does not exist")
        else:
            base_result = _run(
                _solve_command(
                    python_executable,
                    task_dir=task_dir,
                    fast_downward=fast_downward_path,
                    safe=False,
                ),
                runner=runner,
                safesym_root=safesym_root,
                cwd=task_dir,
            )
            base_plan_ready = (
                base_result.returncode == 0 and (task_dir / "sas_plan").exists()
            )
            if not base_plan_ready:
                reasons.append(_command_failure("SafeSym base solve failed", base_result))

            safe_result = _run(
                _solve_command(
                    python_executable,
                    task_dir=task_dir,
                    fast_downward=fast_downward_path,
                    safe=True,
                ),
                runner=runner,
                safesym_root=safesym_root,
                cwd=task_dir,
            )
            safe_plan_ready = (
                safe_result.returncode == 0 and (task_dir / "safe_sas_plan").exists()
            )
            if not safe_plan_ready:
                reasons.append(_command_failure("SafeSym safe solve failed", safe_result))

    safety_action_names = _safety_actions(task_dir)
    return WebKobeSafeSymSmokeReport(
        task_dir=str(task_dir),
        safesym_root=str(safesym_root),
        rules_path=str(rules),
        fast_downward_path=str(fast_downward_path) if fast_downward_path else None,
        safesym_parse_ready=parse_ready,
        safety_injection_ready=injection_ready,
        base_plan_ready=base_plan_ready,
        safe_plan_ready=safe_plan_ready,
        safety_actions_inserted=bool(safety_action_names),
        safety_action_names=safety_action_names,
        failure_reasons=reasons,
    )


def write_web_kobe_safesym_smoke(
    task_dir: Path | str,
    *,
    safesym_root: Path | str,
    rules: Path | str,
    fast_downward: Path | str | None = None,
    runner: Runner = subprocess.run,
    python_executable: str = sys.executable,
) -> WebKobeSafeSymSmokeResult:
    task_dir = Path(task_dir)
    report = analyze_web_kobe_safesym_smoke(
        task_dir,
        safesym_root=safesym_root,
        rules=rules,
        fast_downward=fast_downward,
        runner=runner,
        python_executable=python_executable,
    )
    report_path = task_dir / "safesym_smoke_report.json"
    report_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return WebKobeSafeSymSmokeResult(report=report, report_path=report_path)
