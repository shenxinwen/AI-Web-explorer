import json

import pytest

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


def test_main_help_lists_only_web_kobe_mainline_commands(capsys):
    assert main([]) == 2

    help_output = capsys.readouterr().out
    assert "web-kobe-explore" in help_output
    assert "web-kobe-pddl-from-graph" in help_output
    assert "web-kobe-pddl-smoke" in help_output
    assert "web-kobe-safesym-smoke" in help_output
    assert "web-kobe-openai-selector-smoke" in help_output
    assert "web-kobe-saucedemo-llm-step-smoke" in help_output
    assert "web-kobe-saucedemo-stagehand-smoke" in help_output
    assert "capability-graph" not in help_output
    assert "explore-capability-graph" not in help_output
    assert "explore-graph" not in help_output
    assert "explore-pddl" not in help_output


@pytest.mark.parametrize("legacy_command", ["graph", "pddl", "capability-graph"])
def test_main_rejects_legacy_fixed_graph_commands(legacy_command, tmp_path):
    with pytest.raises(SystemExit) as error:
        main([legacy_command, "--output", str(tmp_path / "out")])

    assert error.value.code == 2


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

    monkeypatch.setattr(
        cli, "build_debug_web_kobe_graph", fake_build_debug_web_kobe_graph
    )

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

    monkeypatch.setattr(
        cli, "build_debug_web_kobe_graph", fake_build_debug_web_kobe_graph
    )
    monkeypatch.setattr(
        cli,
        "compile_web_kobe_graph_to_pddl",
        lambda graph, goal_node_id: FakeArtifacts(),
    )

    assert main(["web-kobe-pddl", "--output", str(output), "--goal-node", "start"]) == 0
    assert (output / "domain.pddl").read_text(encoding="utf-8") == FakeArtifacts.domain
    assert (output / "problem.pddl").read_text(
        encoding="utf-8"
    ) == FakeArtifacts.problem


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
        screenshot_dir=None,
    ):
        calls.append(
            (
                url,
                output_path_arg,
                app_name,
                page_id,
                steps,
                headless,
                screenshot_dir,
            )
        )
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
            "--screenshot-dir",
            str(tmp_path / "screenshots"),
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
            tmp_path / "screenshots",
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
    assert "(:action add_to_cart" in (output_dir / "domain.pddl").read_text(
        encoding="utf-8"
    )
    assert "(:goal (and (at_filled)))" in (output_dir / "problem.pddl").read_text(
        encoding="utf-8"
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


def test_main_web_kobe_safesym_smoke_writes_report(monkeypatch, tmp_path):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    rules = tmp_path / "rules.json"
    rules.write_text("[]", encoding="utf-8")
    safesym_root = tmp_path / "SafeSym"
    calls = []

    class FakeReport:
        safety_injection_ready = True

    class FakeResult:
        report = FakeReport()
        report_path = task_dir / "safesym_smoke_report.json"

    def fake_write_web_kobe_safesym_smoke(
        task_dir_arg,
        *,
        safesym_root,
        rules,
        fast_downward=None,
    ):
        calls.append((task_dir_arg, safesym_root, rules, fast_downward))
        FakeResult.report_path.write_text(
            json.dumps({"safety_injection_ready": True}),
            encoding="utf-8",
        )
        return FakeResult()

    monkeypatch.setattr(
        cli,
        "write_web_kobe_safesym_smoke",
        fake_write_web_kobe_safesym_smoke,
    )

    exit_code = main(
        [
            "web-kobe-safesym-smoke",
            "--task-dir",
            str(task_dir),
            "--safesym-root",
            str(safesym_root),
            "--rules",
            str(rules),
        ]
    )

    assert exit_code == 0
    assert calls == [(task_dir, safesym_root, rules, None)]
    assert FakeResult.report_path.exists()


def test_main_web_kobe_openai_selector_smoke_writes_report(monkeypatch, tmp_path):
    output = tmp_path / "openai_selector_smoke.json"
    calls = []

    class FakeResult:
        report_path = output

    def fake_write_openai_selector_smoke(output_path, *, model=None, provider=None):
        calls.append((output_path, model, provider))
        output_path.write_text(
            json.dumps({"selection_ready": True}),
            encoding="utf-8",
        )
        return FakeResult()

    monkeypatch.setattr(
        cli,
        "write_openai_selector_smoke",
        fake_write_openai_selector_smoke,
    )

    exit_code = main(
        [
            "web-kobe-openai-selector-smoke",
            "--output",
            str(output),
            "--model",
            "gpt-test",
        ]
    )

    assert exit_code == 0
    assert calls == [(output, "gpt-test", None)]
    assert output.exists()


def test_main_web_kobe_saucedemo_llm_step_smoke_runs_browser_step(
    monkeypatch,
    tmp_path,
):
    output = tmp_path / "saucedemo_step_graph.json"
    trace = tmp_path / "saucedemo_step_trace.json"
    calls = []

    async def fake_run_saucedemo_openai_selector_step(
        output_path,
        *,
        selector_trace_path=None,
        headless=True,
        model=None,
        steps=1,
    ):
        calls.append((output_path, selector_trace_path, headless, model, steps))
        output_path.write_text(
            json.dumps({"meta": {"app": "saucedemo"}}),
            encoding="utf-8",
        )
        selector_trace_path.write_text(
            json.dumps(
                [
                    {
                        "status": "selected",
                        "llm_response": {
                            "selected_action_id": "product_add_to_cart",
                        },
                    }
                ]
            ),
            encoding="utf-8",
        )
        return output_path

    monkeypatch.setattr(
        cli,
        "run_saucedemo_openai_selector_step",
        fake_run_saucedemo_openai_selector_step,
    )

    exit_code = main(
        [
            "web-kobe-saucedemo-llm-step-smoke",
            "--output",
            str(output),
            "--selector-trace",
            str(trace),
            "--model",
            "gpt-test",
            "--steps",
            "3",
            "--headed",
        ]
    )

    assert exit_code == 0
    assert calls == [(output, trace, False, "gpt-test", 3)]
    assert output.exists()
    assert trace.exists()


def test_main_web_kobe_saucedemo_stagehand_smoke_wires_runner(
    monkeypatch,
    tmp_path,
):
    output = tmp_path / "graph.json"
    trace = tmp_path / "trace.json"
    calls = []

    async def fake_run_saucedemo_stagehand_step(
        output_path,
        *,
        stagehand_trace_path=None,
        headless=True,
        model=None,
        steps=8,
        screenshot_dir=None,
        use_openai_visual_delta=False,
        visual_delta_model=None,
        allow_final_order=False,
    ):
        calls.append(
            (
                output_path,
                stagehand_trace_path,
                headless,
                model,
                steps,
                screenshot_dir,
                use_openai_visual_delta,
                visual_delta_model,
                allow_final_order,
            )
        )
        output_path.write_text(
            json.dumps({"meta": {"app": "saucedemo"}}),
            encoding="utf-8",
        )
        return output_path

    monkeypatch.setattr(
        cli,
        "run_saucedemo_stagehand_step",
        fake_run_saucedemo_stagehand_step,
        raising=False,
    )

    exit_code = main(
        [
            "web-kobe-saucedemo-stagehand-smoke",
            "--output",
            str(output),
            "--stagehand-trace",
            str(trace),
            "--steps",
            "6",
            "--model",
            "openai/gpt-5-nano",
            "--screenshot-dir",
            str(tmp_path / "shots"),
            "--openai-visual-delta",
            "--visual-delta-model",
            "gpt-4o-mini",
            "--allow-final-order",
        ]
    )

    assert exit_code == 0
    assert calls == [
        (
            output,
            trace,
            True,
            "openai/gpt-5-nano",
            6,
            tmp_path / "shots",
            True,
            "gpt-4o-mini",
            True,
        )
    ]
