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
from ai_web_explorer.grounded_web.location_exploration import ExplorationLimits
from ai_web_explorer.safesym_bridge import cli
from ai_web_explorer.safesym_bridge.cli import main


def _write_semantic_projection_graph(
    path: Path, *, with_semantics: bool = True
) -> None:
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


def test_semantic_pddl_writes_only_current_projection_artifacts(tmp_path):
    graph_path = tmp_path / "semantic_graph.json"
    output_dir = tmp_path / "semantic"
    _write_semantic_projection_graph(graph_path)

    assert (
        main(
            [
                "web-kobe-semantic-pddl",
                "--graph",
                str(graph_path),
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
    assert not (output_dir / "planning_graph.json").exists()
    assert not (output_dir / "planning_abstraction_report.json").exists()
    assert not (output_dir / "raw_graph.json").exists()
    assert "(cart_has_items)" in (output_dir / "domain.pddl").read_text()
    assert "(:goal (and (at_checkout)))" in (output_dir / "problem.pddl").read_text()


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
        business_affordances=[
            BusinessAffordance("retry_me" if failed else "new_action")
        ],
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
                    "click",
                    "#retry",
                    "retry_me",
                    {},
                    "start",
                    "start",
                    False,
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
    assert "web-kobe-stagehand-explore" in help_output
    assert "web-kobe-semantic-pddl" in help_output
    assert "web-kobe-safesym-smoke" in help_output
    for legacy_command in (
        "web-kobe-graph",
        "web-kobe-explore",
        "web-kobe-pddl",
        "web-kobe-pddl-from-graph",
        "web-kobe-domain-from-graph",
        "web-kobe-phase-a",
        "web-kobe-consolidate",
        "web-kobe-pddl-smoke",
    ):
        assert legacy_command not in help_output


@pytest.mark.parametrize(
    "legacy_command",
    [
        "graph",
        "pddl",
        "capability-graph",
        "web-kobe-graph",
        "web-kobe-explore",
        "web-kobe-pddl",
        "web-kobe-pddl-from-graph",
        "web-kobe-domain-from-graph",
        "web-kobe-phase-a",
        "web-kobe-consolidate",
        "web-kobe-pddl-smoke",
    ],
)
def test_main_rejects_legacy_fixed_graph_commands(legacy_command, tmp_path):
    with pytest.raises(SystemExit) as error:
        main([legacy_command, "--output", str(tmp_path / "out")])

    assert error.value.code == 2


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
        site_adapter=None,
        business_profile=None,
        use_openai_visual_delta=False,
        visual_delta_model=None,
        action_outcome_model=None,
        use_openai_risk_detection=False,
        risk_detection_model=None,
        stagehand_execution_mode="observed_action",
        max_candidates=5,
        limits=None,
            frontier_replay=False,
            exploration_condition="linear",
            random_seed=None,
            resume_graph=None,
        resume_policy=None,
        allow_test_site_final_order=True,
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
                site_adapter,
                business_profile,
                use_openai_visual_delta,
                visual_delta_model,
                action_outcome_model,
                use_openai_risk_detection,
                risk_detection_model,
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
            "--max-exploration-steps",
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
            "gpt-4o",
            "--action-outcome-model",
            "gpt-4o",
            "--openai-risk-detection",
            "--risk-detection-model",
            "gpt-4o-mini",
            "--stagehand-execution-mode",
            "observe_act",
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
            None,
            "ecommerce_checkout",
            True,
            "gpt-4o",
            "gpt-4o",
            True,
            "gpt-4o-mini",
            "observe_act",
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


def test_main_stagehand_explore_wires_realworld_site_adapter(monkeypatch, tmp_path):
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
                "https://demo.realworld.show/",
                "--output",
                str(tmp_path / "graph.json"),
                "--site-adapter",
                "realworld",
            ]
        )
        == 0
    )
    assert captured["site_adapter"] == "realworld"


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
    assert isinstance(calls[0]["limits"], ExplorationLimits)
    assert calls[0]["limits"].max_candidates_per_location == 5


def test_main_stagehand_explore_passes_e004_condition_and_seed(monkeypatch, tmp_path):
    calls = []

    async def fake_run(*args, **kwargs):
        calls.append(kwargs)
        args[0].write_text("{}", encoding="utf-8")
        return args[0]

    monkeypatch.setattr(cli, "run_stagehand_exploration", fake_run, raising=False)

    assert main([
        "web-kobe-stagehand-explore", "--url", "https://fixture.test/shop",
        "--output", str(tmp_path / "graph.json"),
        "--exploration-condition", "ungated_random", "--random-seed", "17",
    ]) == 0
    assert calls[0]["exploration_condition"] == "ungated_random"
    assert calls[0]["random_seed"] == 17


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
                "--max-exploration-steps",
                "20",
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
            ]
        )
        == 0
    )

    assert captured["limits"] == ExplorationLimits()
    assert captured["allow_test_site_final_order"] is True
    assert captured["vlm_request_timeout_seconds"] == 180
    assert captured["stagehand_action_timeout_seconds"] == 240


def test_main_stagehand_explore_rejects_legacy_steps(monkeypatch, capsys):
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
                "https://fixture.test/shop",
                "--steps",
                "2",
            ]
        )
    assert "unrecognized arguments: --steps 2" in capsys.readouterr().err


def test_main_stagehand_explore_allows_final_order_by_default_and_can_disable_it(
    monkeypatch, tmp_path
):
    calls = []

    async def fake_run(output_path, **kwargs):
        calls.append(kwargs)
        output_path.write_text("{}", encoding="utf-8")
        return output_path

    monkeypatch.setattr(cli, "run_stagehand_exploration", fake_run, raising=False)

    base_args = [
        "web-kobe-stagehand-explore",
        "--url",
        "https://fixture.test/shop",
        "--output",
        str(tmp_path / "graph.json"),
    ]
    assert main(base_args) == 0
    assert main([*base_args, "--disallow-final-order"]) == 0

    assert calls[0]["allow_test_site_final_order"] is True
    assert calls[1]["allow_test_site_final_order"] is False


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
    assert {
        (key.source_node_id, key.action_id)
        for key in calls[0]["resume_policy"].retry_keys
    } == {("start", "retry_me")}


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
        (
            ["--resume-retry-action", "retry_me"],
            "resume retry action requires --resume-graph",
        ),
        (
            [
                "--resume-graph",
                "graph.json",
                "--resume-retry-action",
                "retry_me",
                "--resume-action-max-attempts",
                "1",
            ],
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
        (
            lambda data: data["meta"].update({"app": "other"}),
            "resume_app_mismatch",
            None,
        ),
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
