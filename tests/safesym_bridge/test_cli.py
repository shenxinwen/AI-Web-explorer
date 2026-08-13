import json
from pathlib import Path

import pytest

from ai_web_explorer.grounded_web.capability_graph import (
    ExecutionTrace,
    ObservedDelta,
    PageFrame,
)
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    BusinessAffordance,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.business_profile import PlanningDelta
from ai_web_explorer.grounded_web.semantic_model import SemanticObservation
from ai_web_explorer.safesym_bridge import cli
from ai_web_explorer.safesym_bridge.cli import main


def _write_semantic_projection_graph(path: Path, *, with_semantics: bool = True) -> None:
    nodes = [
        WebKobeNode(
            node_id="shopping",
            page_description="shopping",
            page_frame=PageFrame(
                page_id="shopping",
                page_type="shopping",
                url="https://fixture.test/shopping",
                url_pattern="https://fixture.test/shopping",
                title="shopping",
            ),
            state_schema={},
            last_state_snapshot={},
            node_label="shopping",
        ),
        WebKobeNode(
            node_id="checkout",
            page_description="checkout",
            page_frame=PageFrame(
                page_id="checkout",
                page_type="checkout",
                url="https://fixture.test/shopping",
                url_pattern="https://fixture.test/shopping",
                title="checkout",
            ),
            state_schema={},
            last_state_snapshot={},
        ),
    ]
    semantic = SemanticObservation(
        action_role="state_mutation",
        source_location="shopping",
        target_location="shopping",
        evidence=["The cart count changed."],
        confidence=0.95,
    )
    checkout_semantic = SemanticObservation(
        action_role="guarded_navigation",
        source_location="shopping",
        target_location="checkout",
        candidate_required_facts=["cart_has_items"],
        evidence=["Checkout modal opened."],
        confidence=0.95,
    )
    edges = [
        WebKobeEdge(
            source_node_id="shopping",
            target_node_id="shopping",
            instruction="add to cart",
            action=BrowserAction("click", "#add", "add_to_cart_from_shopping"),
            capability=None,
            target_observation="shopping",
            observed_delta=[],
            schema_delta={},
            execution_trace=ExecutionTrace(
                "click", "#add", "add", {}, "shopping", "shopping", True
            ),
            planning_delta=PlanningDelta(verified_added_facts=["cart_has_items"]),
            semantic_observation=semantic if with_semantics else None,
            status="succeeded",
        ),
        WebKobeEdge(
            source_node_id="shopping",
            target_node_id="checkout",
            instruction="open checkout",
            action=BrowserAction("click", "#checkout", "open_checkout"),
            capability=None,
            target_observation="checkout",
            observed_delta=[],
            schema_delta={},
            execution_trace=ExecutionTrace(
                "click", "#checkout", "checkout", {}, "shopping", "checkout", True
            ),
            planning_delta=None,
            semantic_observation=checkout_semantic if with_semantics else None,
            status="succeeded_with_navigation",
        ),
    ]
    path.write_text(
        json.dumps(
            WebKobeGraph(
                app="fixture",
                start_node_id="shopping",
                total_steps_completed=2,
                nodes=nodes,
                edges=edges,
            ).to_dict()
        ),
        encoding="utf-8",
    )


def test_phase_a_semantic_projection_writes_semantic_artifacts(tmp_path):
    graph_path = tmp_path / "semantic_graph.json"
    output_dir = tmp_path / "semantic"
    _write_semantic_projection_graph(graph_path)

    assert (
        main(
            [
                "web-kobe-phase-a",
                "--graph",
                str(graph_path),
                "--projection",
                "semantic",
                "--goal-location",
                "checkout",
                "--output",
                str(output_dir),
            ]
        )
        == 0
    )
    assert (output_dir / "semantic_planning_graph.json").exists()
    assert (output_dir / "semantic_projection_report.json").exists()
    assert "(cart_has_items)" in (output_dir / "domain.pddl").read_text()
    assert "(:goal (and (at_checkout)))" in (output_dir / "problem.pddl").read_text()


def test_semantic_projection_falls_back_without_semantic_observations(tmp_path):
    graph_path = tmp_path / "historical_graph.json"
    output_dir = tmp_path / "fallback"
    _write_semantic_projection_graph(graph_path, with_semantics=False)

    assert (
        main(
            [
                "web-kobe-phase-a",
                "--graph",
                str(graph_path),
                "--projection",
                "semantic",
                "--output",
                str(output_dir),
            ]
        )
        == 0
    )
    report = json.loads(
        (output_dir / "semantic_projection_report.json").read_text(encoding="utf-8")
    )
    assert report["fallback_projection"] == "location"
    assert report["fallback_reason"] == "no_usable_semantic_actions"
    assert (output_dir / "domain.pddl").exists()


def test_semantic_fallback_does_not_silently_ignore_explicit_goal(tmp_path):
    graph_path = tmp_path / "historical_graph.json"
    output_dir = tmp_path / "fallback_goal"
    _write_semantic_projection_graph(graph_path, with_semantics=False)

    assert (
        main(
            [
                "web-kobe-phase-a",
                "--graph",
                str(graph_path),
                "--projection",
                "semantic",
                "--goal-location",
                "checkout",
                "--output",
                str(output_dir),
            ]
        )
        == 1
    )
    report = json.loads(
        (output_dir / "semantic_projection_report.json").read_text(encoding="utf-8")
    )
    assert report["fallback_goal_handled"] is False


def _write_resume_graph(path: Path, *, app: str = "demo", failed: bool = True) -> None:
    node = WebKobeNode(
        node_id="start",
        page_description="start",
        page_frame=PageFrame(
            page_id="start",
            page_type="start",
            url="https://fixture.test/",
            url_pattern="https://fixture.test/",
            title="Start",
        ),
        state_schema={},
        last_state_snapshot={},
        business_affordances=[BusinessAffordance("retry_me" if failed else "new_action")],
    )
    edges = []
    if failed:
        edges.append(
            WebKobeEdge(
                source_node_id="start",
                target_node_id="start",
                instruction="retry",
                action=BrowserAction("click", "#retry", "retry_me"),
                capability=None,
                target_observation="start",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "click", "#retry", "retry_me", {}, "start", "start", False,
                    error="failed",
                ),
                status="failed_execution",
            )
        )
    graph = WebKobeGraph(
        app=app,
        start_node_id="start",
        total_steps_completed=3,
        nodes=[node],
        edges=edges,
        meta={"replay_attempt_count": 2},
    )
    path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")


def test_main_without_subcommand_prints_help():
    assert main([]) == 2


def test_main_help_lists_only_web_kobe_mainline_commands(capsys):
    assert main([]) == 2

    help_output = capsys.readouterr().out
    assert "web-kobe-explore" in help_output
    assert "web-kobe-domain-from-graph" in help_output
    assert "web-kobe-pddl-from-graph" in help_output
    assert "web-kobe-pddl-smoke" in help_output
    assert "web-kobe-safesym-smoke" in help_output
    assert "web-kobe-openai-selector-smoke" not in help_output
    assert "web-kobe-ecommerce-stagehand-smoke" in help_output
    assert "web-kobe-saucedemo-llm-step-smoke" not in help_output
    assert "web-kobe-saucedemo-stagehand-smoke" not in help_output
    assert "capability-graph" not in help_output
    assert "explore-capability-graph" not in help_output
    assert "explore-graph" not in help_output
    assert "explore-pddl" not in help_output


@pytest.mark.parametrize(
    "option",
    ["--deepseek-semantic-naming", "--semantic-naming-model"],
)
def test_cli_no_longer_exposes_standalone_semantic_naming_options(
    option, monkeypatch
):
    async def fake_run(*args, **kwargs):
        return Path("fake-output.json")

    monkeypatch.setattr(
        cli,
        "run_ecommerce_stagehand_step",
        fake_run,
        raising=False,
    )
    argv = ["web-kobe-ecommerce-stagehand-smoke", option]
    if option == "--semantic-naming-model":
        argv.append("legacy-model")

    with pytest.raises(SystemExit) as error:
        main(argv)

    assert error.value.code == 2


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
        lambda graph, goal_node_id, goal_fact=None: FakeArtifacts(),
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
    assert "(:action edge_001_add_to_cart" in (output_dir / "domain.pddl").read_text(
        encoding="utf-8"
    )
    assert "(:goal (and (at_filled)))" in (output_dir / "problem.pddl").read_text(
        encoding="utf-8"
    )


def test_main_web_kobe_domain_from_graph_writes_only_domain(tmp_path):
    graph_path = tmp_path / "web_kobe_graph.json"
    output_dir = tmp_path / "web_kobe_domain"
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
                state_schema={},
                last_state_snapshot={},
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
                state_schema={},
                last_state_snapshot={},
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
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "click",
                    "button.add",
                    "add",
                    {},
                    "empty",
                    "filled",
                    True,
                ),
                status="succeeded_with_navigation",
            )
        ],
    )
    graph_path.write_text(json.dumps(graph.to_dict()), encoding="utf-8")

    exit_code = main(
        [
            "web-kobe-domain-from-graph",
            "--graph",
            str(graph_path),
            "--output",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    assert "(:action edge_001_add_to_cart" in (output_dir / "domain.pddl").read_text(
        encoding="utf-8"
    )
    assert not (output_dir / "problem.pddl").exists()


def test_main_web_kobe_pddl_from_graph_accepts_goal_fact(tmp_path):
    graph_path = tmp_path / "web_kobe_graph.json"
    output_dir = tmp_path / "web_kobe_pddl"
    graph = WebKobeGraph(
        app="example",
        start_node_id="review",
        total_steps_completed=1,
        nodes=[
            WebKobeNode(
                node_id="review",
                page_description="review page",
                page_frame=PageFrame(
                    page_id="review",
                    page_type="review",
                    url="https://example.test/review",
                    url_pattern="https://example.test/review",
                    title="review",
                ),
                state_schema={},
                last_state_snapshot={},
            ),
            WebKobeNode(
                node_id="complete",
                page_description="complete page",
                page_frame=PageFrame(
                    page_id="complete",
                    page_type="complete",
                    url="https://example.test/complete",
                    url_pattern="https://example.test/complete",
                    title="complete",
                ),
                state_schema={},
                last_state_snapshot={},
            ),
        ],
        edges=[
            WebKobeEdge(
                source_node_id="review",
                target_node_id="complete",
                instruction="complete order",
                action=BrowserAction(
                    "business_intent",
                    None,
                    "complete_order",
                    canonical_action_name="complete_order",
                ),
                capability=None,
                target_observation="complete",
                observed_delta=[],
                schema_delta={},
                execution_trace=ExecutionTrace(
                    "business_intent",
                    None,
                    "complete_order",
                    {},
                    "review",
                    "complete",
                    True,
                ),
                planning_delta=PlanningDelta(
                    candidate_added_facts=["order_completed"],
                    evidence=["confirmation page displayed"],
                ),
                status="succeeded_with_observed_change",
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
            "complete",
            "--goal-fact",
            "order_completed",
        ]
    )

    assert exit_code == 0
    assert "(:goal (and (order_completed)))" in (output_dir / "problem.pddl").read_text(
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


def test_main_web_kobe_ecommerce_stagehand_smoke_wires_benchmark_runner(
    monkeypatch,
    tmp_path,
):
    output = tmp_path / "graph.json"
    trace = tmp_path / "trace.json"
    calls = []

    async def fake_run_ecommerce_stagehand_step(
        output_path,
        *,
        start_url,
        app_name="ecommerce",
        stagehand_trace_path=None,
        headless=True,
        model=None,
        steps=8,
        screenshot_dir=None,
        use_openai_visual_delta=False,
        visual_delta_model=None,
        allow_final_order=False,
        benchmark_context=None,
    ):
        calls.append(
            (
                output_path,
                start_url,
                app_name,
                stagehand_trace_path,
                headless,
                model,
                steps,
                screenshot_dir,
                use_openai_visual_delta,
                visual_delta_model,
                allow_final_order,
                benchmark_context.site_label,
                benchmark_context.test_credentials,
                benchmark_context.checkout_data,
            )
        )
        output_path.write_text(
            json.dumps({"meta": {"app": app_name}}),
            encoding="utf-8",
        )
        return output_path

    monkeypatch.setattr(
        cli,
        "run_ecommerce_stagehand_step",
        fake_run_ecommerce_stagehand_step,
        raising=False,
    )

    exit_code = main(
        [
            "web-kobe-ecommerce-stagehand-smoke",
            "--benchmark",
            "saucedemo",
            "--output",
            str(output),
            "--stagehand-trace",
            str(trace),
            "--steps",
            "6",
            "--model",
            "deepseek/test",
            "--test-username",
            "fixture_user",
            "--test-password",
            "fixture_password",
            "--checkout-first-name",
            "Ada",
            "--checkout-last-name",
            "Lovelace",
            "--checkout-postal-code",
            "42424",
            "--allow-final-order",
        ]
    )

    assert exit_code == 0
    assert calls == [
        (
            output,
            "https://www.saucedemo.com/",
            "saucedemo",
            trace,
            True,
            "deepseek/test",
            6,
            Path("outputs/latest/screenshots"),
            False,
            None,
            True,
            "public demo e-commerce site",
            {"username": "fixture_user", "password": "fixture_password"},
            {
                "first_name": "Ada",
                "last_name": "Lovelace",
                "postal_code": "42424",
            },
        )
    ]


def test_main_web_kobe_ecommerce_stagehand_smoke_supports_custom_benchmark(
    monkeypatch,
    tmp_path,
):
    output = tmp_path / "graph.json"
    trace = tmp_path / "trace.json"
    calls = []

    async def fake_run_ecommerce_stagehand_step(
        output_path,
        *,
        start_url,
        app_name="ecommerce",
        stagehand_trace_path=None,
        benchmark_context=None,
        **kwargs,
    ):
        calls.append(
            (
                output_path,
                start_url,
                app_name,
                stagehand_trace_path,
                benchmark_context.site_label,
                benchmark_context.test_credentials,
                benchmark_context.checkout_data,
            )
        )
        output_path.write_text("{}", encoding="utf-8")
        return output_path

    monkeypatch.setattr(
        cli,
        "run_ecommerce_stagehand_step",
        fake_run_ecommerce_stagehand_step,
        raising=False,
    )

    exit_code = main(
        [
            "web-kobe-ecommerce-stagehand-smoke",
            "--benchmark",
            "custom",
            "--start-url",
            "https://example.test/shop",
            "--app-name",
            "example_shop",
            "--output",
            str(output),
            "--stagehand-trace",
            str(trace),
        ]
    )

    assert exit_code == 0
    assert calls == [
        (
            output,
            "https://example.test/shop",
            "example_shop",
            trace,
            "public demo e-commerce site",
            {},
            {
                "first_name": "Test",
                "last_name": "User",
                "postal_code": "12345",
            },
        )
    ]


def test_main_web_kobe_ecommerce_stagehand_smoke_requires_custom_start_url():
    assert (
        main(
            [
                "web-kobe-ecommerce-stagehand-smoke",
                "--benchmark",
                "custom",
            ]
        )
        == 1
    )


def test_main_web_kobe_ecommerce_stagehand_smoke_cleans_latest_output_dir(
    monkeypatch,
    tmp_path,
):
    output_dir = tmp_path / "latest"
    output_dir.mkdir()
    stale_file = output_dir / "stale.json"
    stale_file.write_text("old", encoding="utf-8")
    output = output_dir / "graph.json"
    trace = output_dir / "trace.json"
    screenshots = output_dir / "screenshots"
    calls = []

    async def fake_run_ecommerce_stagehand_step(
        output_path,
        *,
        start_url,
        app_name="ecommerce",
        stagehand_trace_path=None,
        screenshot_dir=None,
        **kwargs,
    ):
        calls.append((output_path, stagehand_trace_path, screenshot_dir))
        assert not stale_file.exists()
        output_path.write_text("{}", encoding="utf-8")
        stagehand_trace_path.write_text("[]", encoding="utf-8")
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        return output_path

    monkeypatch.setattr(
        cli,
        "run_ecommerce_stagehand_step",
        fake_run_ecommerce_stagehand_step,
        raising=False,
    )

    exit_code = main(
        [
            "web-kobe-ecommerce-stagehand-smoke",
            "--output",
            str(output),
            "--stagehand-trace",
            str(trace),
            "--screenshot-dir",
            str(screenshots),
            "--clean-output-dir",
        ]
    )

    assert exit_code == 0
    assert calls == [(output, trace, screenshots)]


def test_clean_output_dir_requires_shared_parent(tmp_path):
    output = tmp_path / "latest" / "graph.json"
    trace = tmp_path / "other" / "trace.json"

    with pytest.raises(ValueError):
        cli._clean_output_dir_for([output, trace])


def test_main_web_kobe_stagehand_explore_wires_runner(monkeypatch, tmp_path):
    output = tmp_path / "graph.json"
    trace = tmp_path / "trace.json"
    embeddings = tmp_path / "state_embeddings.json"
    calls = []

    async def fake_run_stagehand_exploration(
        output_path,
        *,
        start_url,
        app_name,
        stagehand_trace_path=None,
        model=None,
        steps=8,
        headless=True,
        screenshot_dir=None,
        embedding_path=None,
        use_state_embeddings=False,
        embedding_model=None,
        embedding_dimension=None,
        site_purpose=None,
        business_profile=None,
        use_openai_visual_delta=False,
        visual_delta_model=None,
        stagehand_execution_mode="business_milestone",
        max_candidates=5,
        frontier_replay=False,
        resume_graph=None,
        resume_policy=None,
    ):
        calls.append(
            (
                output_path,
                start_url,
                app_name,
                stagehand_trace_path,
                model,
                steps,
                headless,
                screenshot_dir,
                embedding_path,
                use_state_embeddings,
                embedding_model,
                embedding_dimension,
                site_purpose,
                business_profile,
                use_openai_visual_delta,
                visual_delta_model,
                stagehand_execution_mode,
                max_candidates,
            )
        )
        output_path.write_text("{}", encoding="utf-8")
        return output_path

    monkeypatch.setattr(
        cli,
        "run_stagehand_exploration",
        fake_run_stagehand_exploration,
        raising=False,
    )

    exit_code = main(
        [
            "web-kobe-stagehand-explore",
            "--url",
            "https://shop.test/",
            "--app-name",
            "demo",
            "--output",
            str(output),
            "--stagehand-trace",
            str(trace),
            "--steps",
            "4",
            "--model",
            "deepseek/test",
            "--screenshot-dir",
            str(tmp_path / "screenshots"),
            "--embedding-path",
            str(embeddings),
            "--state-embeddings",
            "--embedding-model",
            "text-embedding-test",
            "--embedding-dimension",
            "512",
            "--site-purpose",
            "demo store",
            "--business-profile",
            "ecommerce_checkout",
            "--openai-visual-delta",
            "--visual-delta-model",
            "gpt-4o-mini",
            "--stagehand-execution-mode",
            "observed_action",
            "--max-candidates",
            "2",
            "--headed",
        ]
    )

    assert exit_code == 0
    assert calls == [
        (
            output,
            "https://shop.test/",
            "demo",
            trace,
            "deepseek/test",
            4,
            False,
            tmp_path / "screenshots",
            embeddings,
            True,
            "text-embedding-test",
            512,
            "demo store",
            "ecommerce_checkout",
            True,
            "gpt-4o-mini",
            "observed_action",
            2,
        )
    ]


def test_main_web_kobe_stagehand_explore_rejects_invalid_max_candidates(
    monkeypatch,
    capsys,
):
    monkeypatch.setattr(
        cli,
        "run_stagehand_exploration",
        lambda *args, **kwargs: pytest.fail("runner should not be called"),
        raising=False,
    )

    with pytest.raises(SystemExit):
        main(
            [
                "web-kobe-stagehand-explore",
                "--url",
                "https://shop.test/",
                "--max-candidates",
                "-1",
            ]
        )

    assert "must be at least 1" in capsys.readouterr().err


def test_main_stagehand_explore_passes_viewport_dimensions(monkeypatch, tmp_path):
    captured = {}

    async def fake_run(output_path, **kwargs):
        captured.update(kwargs)
        output_path.write_text("{}", encoding="utf-8")
        return output_path

    monkeypatch.setattr(cli, "run_stagehand_exploration", fake_run, raising=False)

    assert (
        main(
            [
                "web-kobe-stagehand-explore",
                "--url",
                "https://fixture.test/shop",
                "--output",
                str(tmp_path / "graph.json"),
                "--viewport-width",
                "1920",
                "--viewport-height",
                "1080",
            ]
        )
        == 0
    )
    assert captured["viewport_width"] == 1920
    assert captured["viewport_height"] == 1080


def test_main_web_kobe_stagehand_explore_accepts_frontier_replay(monkeypatch, tmp_path):
    calls = []

    async def fake_run(*args, **kwargs):
        calls.append(kwargs)
        output_path = args[0]
        output_path.write_text("{}", encoding="utf-8")
        return output_path

    monkeypatch.setattr(cli, "run_stagehand_exploration", fake_run, raising=False)

    assert (
        main(
            [
                "web-kobe-stagehand-explore",
                "--url",
                "https://fixture.test/shop",
                "--output",
                str(tmp_path / "graph.json"),
                "--frontier-replay",
                "--max-candidates",
                "5",
                "--openai-visual-delta",
                "--screenshot-dir",
                str(tmp_path / "screenshots"),
                "--stagehand-execution-mode",
                "observed_action",
            ]
        )
        == 0
    )
    assert calls[0]["frontier_replay"] is True
    assert calls[0]["max_candidates"] == 5
    assert calls[0]["use_openai_visual_delta"] is True
    assert calls[0]["screenshot_dir"] == tmp_path / "screenshots"
    assert calls[0]["stagehand_execution_mode"] == "observed_action"


def test_main_stagehand_explore_accepts_location_feasibility_parameters(
    monkeypatch, tmp_path
):
    captured = {}

    async def fake_run(output_path, **kwargs):
        captured.update(kwargs)
        output_path.write_text("{}", encoding="utf-8")
        return output_path

    monkeypatch.setattr(cli, "run_stagehand_exploration", fake_run, raising=False)

    assert (
        main(
            [
                "web-kobe-stagehand-explore",
                "--url",
                "https://practiceautomatedtesting.com/shopping",
                "--output",
                str(tmp_path / "graph.json"),
                "--semantic-experiment-profile",
                "practice_shopping_feasibility",
                "--max-exploration-steps",
                "20",
                "--max-consecutive-no-progress",
                "3",
                "--max-action-attempts-per-candidate",
                "2",
                "--max-replay-attempts-per-frontier",
                "2",
                "--max-total-replays",
                "4",
                "--max-vlm-scan-attempts",
                "2",
                "--max-candidates",
                "8",
                "--vlm-request-timeout-seconds",
                "180",
                "--stagehand-action-timeout-seconds",
                "240",
                "--allow-test-site-final-order",
                "--test-data-seed",
                "practice-v1",
            ]
        )
        == 0
    )

    from ai_web_explorer.grounded_web.location_exploration import ExplorationLimits

    assert captured["limits"] == ExplorationLimits()
    assert captured["allow_test_site_final_order"] is True
    assert captured["semantic_experiment_profile"] == (
        "practice_shopping_feasibility"
    )
    assert captured["vlm_request_timeout_seconds"] == 180
    assert captured["stagehand_action_timeout_seconds"] == 240


def test_main_stagehand_explore_rejects_steps_and_max_exploration_steps(
    monkeypatch, capsys
):
    monkeypatch.setattr(
        cli,
        "run_stagehand_exploration",
        lambda *args, **kwargs: pytest.fail("runner should not be called"),
        raising=False,
    )

    assert (
        main(
            [
                "web-kobe-stagehand-explore",
                "--url",
                "https://fixture.test/shop",
                "--steps",
                "2",
                "--max-exploration-steps",
                "20",
            ]
        )
        == 1
    )
    assert "cannot be combined" in capsys.readouterr().out


def test_main_stagehand_explore_rejects_final_order_for_wrong_url(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(
        cli,
        "run_stagehand_exploration",
        lambda *args, **kwargs: pytest.fail("runner should not be called"),
        raising=False,
    )

    assert (
        main(
            [
                "web-kobe-stagehand-explore",
                "--url",
                "https://fixture.test/shop",
                "--output",
                str(tmp_path / "graph.json"),
                "--semantic-experiment-profile",
                "practice_shopping_feasibility",
                "--allow-test-site-final-order",
            ]
        )
        == 1
    )
    assert "controlled test URL" in capsys.readouterr().out


def test_main_stagehand_explore_rejects_final_order_without_profile(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(
        cli,
        "run_stagehand_exploration",
        lambda *args, **kwargs: pytest.fail("runner should not be called"),
        raising=False,
    )

    assert (
        main(
            [
                "web-kobe-stagehand-explore",
                "--url",
                "https://practiceautomatedtesting.com/shopping",
                "--output",
                str(tmp_path / "graph.json"),
                "--allow-test-site-final-order",
            ]
        )
        == 1
    )
    assert "semantic experiment profile" in capsys.readouterr().out


def test_main_web_kobe_stagehand_explore_passes_explicit_resume_defaults(
    monkeypatch, tmp_path
):
    calls = []

    async def fake_run(*args, **kwargs):
        calls.append(kwargs)
        output_path = args[0]
        output_path.write_text("{}", encoding="utf-8")
        return output_path

    monkeypatch.setattr(cli, "run_stagehand_exploration", fake_run, raising=False)

    assert (
        main(
            [
                "web-kobe-stagehand-explore",
                "--url",
                "https://fixture.test/shop",
                "--output",
                str(tmp_path / "graph.json"),
            ]
        )
        == 0
    )
    assert calls[0]["resume_graph"] is None
    assert calls[0]["resume_policy"] is None


def test_main_web_kobe_stagehand_explore_loads_resume_and_resolves_retry(
    monkeypatch, tmp_path
):
    graph_path = tmp_path / "graph.json"
    _write_resume_graph(graph_path)
    calls = []

    async def fake_run(*args, **kwargs):
        calls.append(kwargs)
        return args[0]

    monkeypatch.setattr(cli, "run_stagehand_exploration", fake_run, raising=False)

    assert (
        main(
            [
                "web-kobe-stagehand-explore",
                "--url",
                "https://fixture.test/shop",
                "--app-name",
                "demo",
                "--output",
                str(graph_path),
                "--resume-graph",
                str(graph_path),
                "--resume-retry-action",
                "retry_me",
                "--resume-action-max-attempts",
                "3",
            ]
        )
        == 0
    )
    assert calls[0]["resume_graph"].app == "demo"
    assert calls[0]["frontier_replay"] is True
    assert calls[0]["resume_policy"].max_attempts == 3
    assert {(key.source_node_id, key.action_id) for key in calls[0]["resume_policy"].retry_keys} == {
        ("start", "retry_me")
    }


def test_main_web_kobe_stagehand_explore_copies_baseline_to_different_output(
    monkeypatch, tmp_path
):
    input_path = tmp_path / "input" / "graph.json"
    output_path = tmp_path / "output" / "graph.json"
    input_path.parent.mkdir()
    _write_resume_graph(input_path)
    seen = []

    async def fake_run(output, **kwargs):
        seen.append(output)
        assert output.exists()
        assert json.loads(output.read_text(encoding="utf-8"))["meta"]["app"] == "demo"
        return output

    monkeypatch.setattr(cli, "run_stagehand_exploration", fake_run, raising=False)

    assert (
        main(
            [
                "web-kobe-stagehand-explore",
                "--url",
                "https://fixture.test/shop",
                "--app-name",
                "demo",
                "--output",
                str(output_path),
                "--resume-graph",
                str(input_path),
            ]
        )
        == 0
    )
    assert seen == [output_path]


@pytest.mark.parametrize(
    "extra_args, expected_error",
    [
        (["--resume-retry-action", "retry_me"], "resume retry action requires --resume-graph"),
        (
            ["--resume-graph", "graph.json", "--resume-retry-action", "retry_me", "--resume-action-max-attempts", "1"],
            "resume action max attempts must be at least 2",
        ),
    ],
)
def test_main_web_kobe_stagehand_explore_rejects_resume_argument_conflicts(
    monkeypatch, tmp_path, extra_args, expected_error, capsys
):
    monkeypatch.setattr(
        cli,
        "run_stagehand_exploration",
        lambda *args, **kwargs: pytest.fail("runner should not be called"),
        raising=False,
    )
    args = [
        "web-kobe-stagehand-explore",
        "--url",
        "https://fixture.test/shop",
        "--output",
        str(tmp_path / "graph.json"),
    ]
    for arg in extra_args:
        args.append(str(tmp_path / "graph.json") if arg == "graph.json" else arg)
    assert main(args) == 1
    assert expected_error in capsys.readouterr().out


def test_main_web_kobe_stagehand_explore_rejects_clean_with_resume_before_deleting(
    monkeypatch, tmp_path
):
    graph_path = tmp_path / "graph.json"
    _write_resume_graph(graph_path)
    stale_path = tmp_path / "stale.txt"
    stale_path.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "run_stagehand_exploration",
        lambda *args, **kwargs: pytest.fail("runner should not be called"),
        raising=False,
    )

    assert (
        main(
            [
                "web-kobe-stagehand-explore",
                "--url",
                "https://fixture.test/shop",
                "--app-name",
                "demo",
                "--output",
                str(graph_path),
                "--resume-graph",
                str(graph_path),
                "--clean-output-dir",
            ]
        )
        == 1
    )
    assert stale_path.exists()


@pytest.mark.parametrize(
    "mutation, expected_error, retry_action",
    [
        (lambda data: data["meta"].update({"app": "other"}), "resume_app_mismatch", None),
        (
            lambda data: data["meta"].update({"start_node_id": "missing"}),
            "resume_start_node_missing",
            None,
        ),
        (
            lambda data: data["edges"][0].update({"target_node_id": "missing"}),
            "resume_dangling_edge",
            None,
        ),
        (lambda data: None, "unknown_resume_retry_action", "unknown"),
    ],
)
def test_main_web_kobe_stagehand_explore_validates_resume_before_runner(
    monkeypatch, tmp_path, mutation, expected_error, retry_action, capsys
):
    graph_path = tmp_path / "graph.json"
    _write_resume_graph(graph_path)
    data = json.loads(graph_path.read_text(encoding="utf-8"))
    mutation(data)
    graph_path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "run_stagehand_exploration",
        lambda *args, **kwargs: pytest.fail("runner should not be called"),
        raising=False,
    )
    args = [
        "web-kobe-stagehand-explore",
        "--url",
        "https://fixture.test/shop",
        "--app-name",
        "demo",
        "--output",
        str(graph_path),
        "--resume-graph",
        str(graph_path),
    ]
    if retry_action:
        args.extend(["--resume-retry-action", retry_action])
    assert main(args) == 1
    assert expected_error in capsys.readouterr().out


def test_main_web_kobe_stagehand_explore_cleans_latest_output_dir(
    monkeypatch,
    tmp_path,
):
    output_dir = tmp_path / "latest"
    output_dir.mkdir()
    stale_file = output_dir / "stale.json"
    stale_file.write_text("old", encoding="utf-8")
    stale_screenshot_dir = output_dir / "screenshots"
    stale_screenshot_dir.mkdir()
    (stale_screenshot_dir / "after_0009.png").write_text("old", encoding="utf-8")
    output = output_dir / "graph.json"
    trace = output_dir / "stagehand_trace.json"
    embeddings = output_dir / "state_embeddings.json"
    calls = []

    async def fake_run_stagehand_exploration(
        output_path,
        *,
        start_url,
        app_name,
        stagehand_trace_path=None,
        screenshot_dir=None,
        embedding_path=None,
        **kwargs,
    ):
        calls.append(
            (output_path, stagehand_trace_path, screenshot_dir, embedding_path)
        )
        assert not stale_file.exists()
        assert not stale_screenshot_dir.exists()
        output_path.write_text("{}", encoding="utf-8")
        stagehand_trace_path.write_text("[]", encoding="utf-8")
        embedding_path.write_text('{"records":[]}', encoding="utf-8")
        return output_path

    monkeypatch.setattr(
        cli,
        "run_stagehand_exploration",
        fake_run_stagehand_exploration,
        raising=False,
    )

    exit_code = main(
        [
            "web-kobe-stagehand-explore",
            "--url",
            "https://shop.test/",
            "--app-name",
            "demo",
            "--output",
            str(output),
            "--stagehand-trace",
            str(trace),
            "--screenshot-dir",
            str(stale_screenshot_dir),
            "--embedding-path",
            str(embeddings),
            "--clean-output-dir",
        ]
    )

    assert exit_code == 0
    assert calls == [(output, trace, stale_screenshot_dir, embeddings)]


def test_main_web_kobe_phase_a_surface_projection_writes_problem(tmp_path):
    graph_path = tmp_path / "graph.json"
    output_dir = tmp_path / "surface"
    node = WebKobeNode(
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
    )
    edge = WebKobeEdge(
        source_node_id="shopping",
        target_node_id="shopping",
        instruction="filter",
        action=BrowserAction("click", "#filter", "filter"),
        capability=None,
        target_observation="shopping",
        observed_delta=[],
        schema_delta={},
        execution_trace=ExecutionTrace(
            "click", "#filter", "filter", {}, "shopping", "shopping", True
        ),
        status="succeeded_with_observed_change",
    )
    graph_path.write_text(
        json.dumps(
            WebKobeGraph(
                app="fixture",
                start_node_id="shopping",
                total_steps_completed=1,
                nodes=[node],
                edges=[edge],
            ).to_dict()
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "web-kobe-phase-a",
                "--graph",
                str(graph_path),
                "--output",
                str(output_dir),
                "--projection",
                "surface",
                "--goal-node",
                "shopping",
            ]
        )
        == 0
    )
    domain = (output_dir / "domain.pddl").read_text(encoding="utf-8")
    problem = (output_dir / "problem.pddl").read_text(encoding="utf-8")
    assert "(executed transition_filter_on_shopping)" in domain
    assert "(:domain web_kobe_surface)" in problem
    assert "checkpoint" not in domain


def _write_surface_graph(path: Path, *, include_isolated: bool = False) -> None:
    nodes = [
        WebKobeNode(
            node_id="start",
            page_description="start",
            page_frame=PageFrame(
                page_id="start",
                page_type="listing",
                url="https://fixture.test/",
                url_pattern="https://fixture.test/",
                title="start",
            ),
            state_schema={},
            last_state_snapshot={},
            node_label="start",
        )
    ]
    if include_isolated:
        nodes.append(
            WebKobeNode(
                node_id="isolated",
                page_description="isolated",
                page_frame=PageFrame(
                    page_id="isolated",
                    page_type="listing",
                    url="https://fixture.test/isolated",
                    url_pattern="https://fixture.test/isolated",
                    title="isolated",
                ),
                state_schema={},
                last_state_snapshot={},
                node_label="isolated",
            )
        )
    path.write_text(
        json.dumps(
            WebKobeGraph(
                app="fixture",
                start_node_id="start",
                total_steps_completed=0,
                nodes=nodes,
                edges=[],
            ).to_dict()
        ),
        encoding="utf-8",
    )


def test_main_web_kobe_phase_a_without_problem_query_removes_stale_problem(
    tmp_path,
):
    graph_path = tmp_path / "graph.json"
    output_dir = tmp_path / "surface"
    _write_surface_graph(graph_path)
    output_dir.mkdir()
    (output_dir / "problem.pddl").write_text("stale", encoding="utf-8")
    marker = output_dir / "unrelated.txt"
    marker.write_text("keep", encoding="utf-8")

    assert (
        main(
            [
                "web-kobe-phase-a",
                "--graph",
                str(graph_path),
                "--output",
                str(output_dir),
                "--projection",
                "surface",
            ]
        )
        == 0
    )
    assert not (output_dir / "problem.pddl").exists()
    assert marker.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("goal_node", ["missing", "isolated"])
def test_main_web_kobe_phase_a_failed_problem_query_removes_stale_problem(
    tmp_path,
    goal_node,
):
    graph_path = tmp_path / "graph.json"
    output_dir = tmp_path / "surface"
    _write_surface_graph(graph_path, include_isolated=True)
    output_dir.mkdir()
    (output_dir / "problem.pddl").write_text("stale", encoding="utf-8")
    marker = output_dir / "unrelated.txt"
    marker.write_text("keep", encoding="utf-8")

    assert (
        main(
            [
                "web-kobe-phase-a",
                "--graph",
                str(graph_path),
                "--output",
                str(output_dir),
                "--projection",
                "surface",
                "--goal-node",
                goal_node,
            ]
        )
        == 1
    )
    assert not (output_dir / "problem.pddl").exists()
    assert marker.read_text(encoding="utf-8") == "keep"
