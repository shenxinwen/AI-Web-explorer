from __future__ import annotations

import json
import socket
import tempfile
import time
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Iterable

from ai_web_explorer.grounded_web.capability_graph import Evidence, PageFrame
from ai_web_explorer.grounded_web.graph import (
    ReferenceObservation,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.controller import (
    WebKobeExplorationController,
)
from ai_web_explorer.grounded_web.business_profile import (
    BusinessFlowProfile,
    ecommerce_checkout_profile,
)
from ai_web_explorer.grounded_web.experiment_plan import (
    ExperimentPlan,
    ecommerce_checkout_experiment_plan,
)
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.frontier_replay import FrontierReplayRunner
from ai_web_explorer.grounded_web.resume import (
    ActionAttemptKey,
    ResumePolicy,
    select_resume_frontier,
    validate_resume_graph,
)
from ai_web_explorer.grounded_web.playwright_backend import (
    WebKobePlaywrightAdapter,
)
from ai_web_explorer.grounded_web.semantic_assistor import (
    DeterministicSemanticAssistor,
)
from ai_web_explorer.grounded_web.openai_visual_delta import (
    create_openai_visual_delta_provider_from_env,
)
from ai_web_explorer.grounded_web.embedding_provider import (
    create_embedding_provider_from_env,
)
from ai_web_explorer.grounded_web.stagehand_backend import (
    StagehandAutomationBackend,
)
from ai_web_explorer.grounded_web.stagehand_prompt import (
    BenchmarkTaskContext,
    ECOMMERCE_CHECKOUT_DOMAIN_GUIDANCE,
    build_generic_stagehand_exploration_goal,
    build_ecommerce_checkout_stagehand_goal,
)
from ai_web_explorer.grounded_web.stagehand_sdk_provider import (
    create_async_stagehand_provider_from_env,
)
from ai_web_explorer.grounded_web.state_embedding import (
    StateEmbeddingRecord,
    read_state_embedding_records,
    write_state_embedding_records,
)
from ai_web_explorer.safesym_bridge.graph_artifacts import (
    build_graph_artifact_payload,
)


ECOMMERCE_CHECKOUT_OVERVIEW_STAGEHAND_GOAL = build_ecommerce_checkout_stagehand_goal(
    allow_final_order=False,
)
ECOMMERCE_CHECKOUT_COMPLETE_STAGEHAND_GOAL = build_ecommerce_checkout_stagehand_goal(
    allow_final_order=True,
)
ECOMMERCE_CHECKOUT_OVERVIEW_EXPLORER_GOAL = (
    "Reach an e-commerce checkout overview without placing the order."
)
ECOMMERCE_CHECKOUT_COMPLETE_EXPLORER_GOAL = (
    "Complete an e-commerce test checkout flow through the confirmation page."
)
SAUCEDEMO_BENCHMARK_START_URL = "https://www.saucedemo.com/"


def _resolve_business_profile(
    profile: str | BusinessFlowProfile | None,
) -> BusinessFlowProfile | None:
    if profile is None or profile == "none":
        return None
    if isinstance(profile, BusinessFlowProfile):
        return profile
    if profile == "ecommerce_checkout":
        return ecommerce_checkout_profile()
    raise ValueError(f"Unsupported business profile: {profile}")


def build_saucedemo_stagehand_benchmark_context(
    *,
    test_username: str = "standard_user",
    test_password: str = "secret_sauce",
    checkout_first_name: str = "Test",
    checkout_last_name: str = "User",
    checkout_postal_code: str = "12345",
) -> BenchmarkTaskContext:
    return BenchmarkTaskContext(
        site_label="public demo e-commerce site",
        test_credentials={
            "username": test_username,
            "password": test_password,
        },
        checkout_data={
            "first_name": checkout_first_name,
            "last_name": checkout_last_name,
            "postal_code": checkout_postal_code,
        },
    )


def build_debug_web_kobe_graph() -> WebKobeGraph:
    evidence = [Evidence(source="debug_builder")]
    start_node = WebKobeNode(
        node_id="start",
        page_description="debug start page",
        page_frame=PageFrame(
            page_id="debug:start",
            page_type="start",
            url="about:blank",
            url_pattern="about:blank",
            title="Debug",
            evidence=evidence,
        ),
        state_schema={},
        last_state_snapshot={},
        reference_observation=ReferenceObservation(url="about:blank", title="Debug"),
        visit_count=1,
        evidence=evidence,
    )
    return WebKobeGraph(
        app="debug",
        start_node_id="start",
        total_steps_completed=0,
        nodes=[start_node],
        edges=[],
        meta={"source": "debug_builder"},
    )


def write_web_kobe_graph(
    graph: WebKobeGraph,
    output_path: Path,
    *,
    evidence_path: Path | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path = evidence_path or output_path.with_name("graph_evidence.json")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)

    payload = build_graph_artifact_payload(graph)
    payload.compact_graph.setdefault("meta", {})[
        "frontier_metrics"
    ] = _frontier_metrics_for_graph(graph)

    evidence_text = json.dumps(
        payload.evidence_sidecar, indent=2, ensure_ascii=False
    )
    graph_text = json.dumps(payload.compact_graph, indent=2, ensure_ascii=False)
    evidence_temp = _write_json_temp(evidence_path, evidence_text)
    graph_temp = None
    old_evidence = evidence_path.read_bytes() if evidence_path.exists() else None
    sidecar_replaced = False
    try:
        graph_temp = _write_json_temp(output_path, graph_text)
        evidence_temp.replace(evidence_path)
        sidecar_replaced = True
        graph_temp.replace(output_path)
    except Exception:
        if sidecar_replaced:
            if old_evidence is None:
                evidence_path.unlink(missing_ok=True)
            else:
                evidence_path.write_bytes(old_evidence)
        raise
    finally:
        evidence_temp.unlink(missing_ok=True)
        if graph_temp is not None:
            graph_temp.unlink(missing_ok=True)
    return output_path


def _write_json_temp(path: Path, text: str) -> Path:
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(text)
        return temp_path
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise


def _write_text_atomically(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _write_json_temp(path, text)
    try:
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)
    return path


def _write_stagehand_checkpoint(
    graph: WebKobeGraph,
    *,
    output_path: Path,
    embedding_path: Path | None,
    embedding_records: Iterable[StateEmbeddingRecord],
    stagehand_trace_path: Path | None,
) -> Path:
    if embedding_path is not None:
        write_state_embedding_records(embedding_path, embedding_records)
    if stagehand_trace_path is not None:
        trace_edges = graph.execution_events or graph.edges
        traces = [
            edge.execution_trace.metadata
            for edge in trace_edges
            if edge.execution_trace.metadata.get("action_source") == "stagehand"
        ]
        _write_text_atomically(
            stagehand_trace_path,
            json.dumps(traces, indent=2, ensure_ascii=False),
        )
    return write_web_kobe_graph(graph, output_path)


def _edge_action_id(edge) -> str:
    return edge.action.canonical_action_name or edge.action.semantic_id


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _frontier_metrics_for_graph(graph: WebKobeGraph) -> dict[str, object]:
    edge_action_ids_by_source: dict[str, list[str]] = {}
    no_op_action_ids_by_source: dict[str, list[str]] = {}
    failed_action_ids_by_source: dict[str, list[str]] = {}
    repeated_target_hit_count = 0
    seen_nodes = {graph.start_node_id}

    for edge in graph.edges:
        action_id = _edge_action_id(edge)
        edge_action_ids_by_source.setdefault(edge.source_node_id, []).append(action_id)
        if edge.status == "no_observed_change":
            no_op_action_ids_by_source.setdefault(edge.source_node_id, []).append(
                action_id
            )
        if edge.status == "failed_execution":
            failed_action_ids_by_source.setdefault(edge.source_node_id, []).append(
                action_id
            )
        if edge.target_node_id in seen_nodes:
            repeated_target_hit_count += 1
        seen_nodes.add(edge.target_node_id)

    nodes: dict[str, dict[str, object]] = {}
    frontier_node_count = 0
    exhausted_node_count = 0
    for node in graph.nodes:
        candidate_ids = _unique(
            [affordance.action_name for affordance in node.business_affordances]
        )
        tried_action_ids = _unique(edge_action_ids_by_source.get(node.node_id, []))
        no_op_action_ids = _unique(no_op_action_ids_by_source.get(node.node_id, []))
        failed_action_ids = _unique(failed_action_ids_by_source.get(node.node_id, []))
        tried_set = set(tried_action_ids)
        untried_action_ids = [
            action_id for action_id in candidate_ids if action_id not in tried_set
        ]

        if candidate_ids and untried_action_ids:
            frontier_node_count += 1
        elif candidate_ids:
            exhausted_node_count += 1

        nodes[node.node_id] = {
            "node_label": node.node_label,
            "candidate_count": len(candidate_ids),
            "tried_action_ids": tried_action_ids,
            "untried_action_ids": untried_action_ids,
            "no_op_action_ids": no_op_action_ids,
            "failed_action_ids": failed_action_ids,
        }

    return {
        "frontier_node_count": frontier_node_count,
        "exhausted_node_count": exhausted_node_count,
        "repeated_target_hit_count": repeated_target_hit_count,
        "backtrack_count": int(graph.meta.get("backtrack_count", 0)),
        "nodes": nodes,
    }


def _is_ecommerce_terminal_graph(graph: WebKobeGraph) -> bool:
    if not graph.edges:
        return False
    target_id = graph.edges[-1].target_node_id
    nodes_by_id = {node.node_id: node for node in graph.nodes}
    target = nodes_by_id.get(target_id)
    if target is None:
        return False
    active_facts = (
        set(target.planning_state.active_facts)
        if target.planning_state is not None
        else set()
    )
    if "order_completed" in active_facts:
        return True
    reference_url = (
        target.reference_observation.url
        if target.reference_observation is not None
        else ""
    )
    url = reference_url or target.page_frame.url
    normalized = url.lower().replace("_", "-")
    return "checkout-complete" in normalized or "order-complete" in normalized


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _read_cdp_websocket_url(port: int, *, timeout_seconds: float = 5.0) -> str:
    url = f"http://127.0.0.1:{port}/json/version"
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                data = json.loads(response.read().decode("utf-8"))
            websocket_url = data.get("webSocketDebuggerUrl")
            if websocket_url:
                return str(websocket_url)
        except Exception as error:
            last_error = error
        time.sleep(0.1)
    raise RuntimeError(
        f"Chromium CDP websocket URL was not available at {url}."
    ) from last_error


async def run_web_kobe_exploration(
    url: str,
    output_path: Path,
    *,
    app_name: str = "web",
    page_id: str | None = None,
    steps: int = 1,
    headless: bool = True,
    goal: str = "Explore the web task.",
    screenshot_dir: Path | None = None,
) -> Path:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless)
        page = await browser.new_page()
        try:
            await page.goto(url)
            adapter = WebKobePlaywrightAdapter(
                page,
                app_name=app_name,
                page_id=page_id,
                screenshot_dir=screenshot_dir,
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app=app_name),
                goal=goal,
                capture_screenshots=screenshot_dir is not None,
            )
            controller = WebKobeExplorationController(explorer)
            result = await controller.run(max_steps=max(steps, 1))
            write_web_kobe_graph(result.graph, output_path)
            return output_path
        finally:
            await browser.close()


async def run_ecommerce_stagehand_step(
    output_path: Path,
    *,
    start_url: str,
    app_name: str = "ecommerce",
    stagehand_trace_path: Path | None = None,
    headless: bool = True,
    steps: int = 8,
    provider=None,
    model: str | None = None,
    screenshot_dir: Path | None = None,
    visual_delta_provider=None,
    use_openai_visual_delta: bool = False,
    visual_delta_model: str | None = None,
    allow_final_order: bool = False,
    benchmark_context: BenchmarkTaskContext | None = None,
    experiment_plan: ExperimentPlan | None = None,
) -> Path:
    from playwright.async_api import async_playwright

    if (visual_delta_provider is not None or use_openai_visual_delta) and (
        screenshot_dir is None
    ):
        raise ValueError("screenshot_dir is required for visual delta analysis.")
    resolved_visual_delta_provider = visual_delta_provider
    if resolved_visual_delta_provider is None and use_openai_visual_delta:
        resolved_visual_delta_provider = create_openai_visual_delta_provider_from_env(
            model=visual_delta_model,
        )
    resolved_experiment_plan = experiment_plan or ecommerce_checkout_experiment_plan(
        allow_final_order=allow_final_order,
    )

    def _experiment_step_for(step_number: int):
        return resolved_experiment_plan.step_for_number(step_number)

    stagehand_goal = build_ecommerce_checkout_stagehand_goal(
        allow_final_order=allow_final_order,
        benchmark_context=benchmark_context,
        current_step=None,
        experiment_plan=resolved_experiment_plan,
    )

    def _stagehand_goal_for(step_number: int) -> str:
        return stagehand_goal

    def _experiment_metadata_for(step_number: int) -> dict[str, object]:
        step = _experiment_step_for(step_number)
        if step is None:
            return {"experiment_plan_id": resolved_experiment_plan.plan_id}
        return {
            "experiment_plan_id": resolved_experiment_plan.plan_id,
            **step.to_metadata(),
        }

    cdp_port = _pick_free_port() if provider is None else None
    launch_args = (
        [f"--remote-debugging-port={cdp_port}"] if cdp_port is not None else None
    )
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless,
            args=launch_args,
        )
        local_cdp_url = (
            _read_cdp_websocket_url(cdp_port) if cdp_port is not None else None
        )
        page = await browser.new_page()
        try:
            await page.goto(start_url)
            resolved_provider = provider
            if resolved_provider is None:
                resolved_provider = await create_async_stagehand_provider_from_env(
                    model_name=model,
                    page=page,
                    local_cdp_url=local_cdp_url,
                )
            base_adapter = WebKobePlaywrightAdapter(
                page,
                app_name=app_name,
                screenshot_dir=screenshot_dir,
            )
            adapter = StagehandAutomationBackend(
                base_backend=base_adapter,
                provider=resolved_provider,
                goal=stagehand_goal,
                execution_mode="business_milestone",
                goal_provider=_stagehand_goal_for,
                business_step_metadata_provider=_experiment_metadata_for,
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app=app_name),
                goal=(
                    ECOMMERCE_CHECKOUT_COMPLETE_EXPLORER_GOAL
                    if allow_final_order
                    else ECOMMERCE_CHECKOUT_OVERVIEW_EXPLORER_GOAL
                ),
                capture_screenshots=screenshot_dir is not None,
                business_profile=(
                    ecommerce_checkout_profile()
                    if resolved_visual_delta_provider is not None
                    else None
                ),
                visual_delta_provider=resolved_visual_delta_provider,
            )
            controller = WebKobeExplorationController(explorer)
            if allow_final_order:
                controller.terminal_condition = _is_ecommerce_terminal_graph
            result = await controller.run(max_steps=max(steps, 1))
            graph = result.graph
            write_web_kobe_graph(graph, output_path)
            if stagehand_trace_path is not None:
                traces = graph.meta.get("stagehand_traces")
                if traces is None:
                    traces = [
                        edge.execution_trace.metadata
                        for edge in graph.edges
                        if edge.execution_trace.metadata.get("action_source")
                        == "stagehand"
                    ]
                stagehand_trace_path.parent.mkdir(parents=True, exist_ok=True)
                stagehand_trace_path.write_text(
                    json.dumps(traces, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            return output_path
        finally:
            await browser.close()


async def run_stagehand_exploration(
    output_path: Path,
    *,
    start_url: str,
    app_name: str = "web",
    stagehand_trace_path: Path | None = None,
    headless: bool = True,
    steps: int = 8,
    provider=None,
    model: str | None = None,
    screenshot_dir: Path | None = None,
    visual_delta_provider=None,
    use_openai_visual_delta: bool = False,
    visual_delta_model: str | None = None,
    state_embedding_provider=None,
    embedding_path: Path | None = None,
    use_state_embeddings: bool = False,
    embedding_model: str | None = None,
    embedding_dimension: int | None = None,
    site_purpose: str | None = None,
    business_profile: str | BusinessFlowProfile | None = None,
    stagehand_execution_mode: str = "observed_action",
    max_candidates: int = 5,
    frontier_replay: bool = False,
    resume_graph: WebKobeGraph | None = None,
    resume_policy: ResumePolicy | None = None,
) -> Path:
    from playwright.async_api import async_playwright

    if (visual_delta_provider is not None or use_openai_visual_delta) and (
        screenshot_dir is None
    ):
        raise ValueError("screenshot_dir is required for visual delta analysis.")
    resolved_visual_delta_provider = visual_delta_provider
    if resolved_visual_delta_provider is None and use_openai_visual_delta:
        resolved_visual_delta_provider = create_openai_visual_delta_provider_from_env(
            model=visual_delta_model,
        )
    resolved_embedding_provider = state_embedding_provider
    if resolved_embedding_provider is None and use_state_embeddings:
        resolved_embedding_provider = create_embedding_provider_from_env(
            model=embedding_model,
            dimension=embedding_dimension,
        )
    embedding_records = (
        read_state_embedding_records(embedding_path)
        if embedding_path is not None
        else []
    )
    stagehand_goal = build_generic_stagehand_exploration_goal(
        site_purpose=site_purpose,
    )
    resolved_business_profile = _resolve_business_profile(business_profile)
    if resume_policy is not None and resume_graph is None:
        raise ValueError("resume_policy_requires_resume_graph")
    if resume_graph is not None:
        validate_resume_graph(resume_graph, app_name=app_name)
        resume_policy = resume_policy or ResumePolicy()
        resume_graph = replace(
            resume_graph,
            meta={
                key: value
                for key, value in resume_graph.meta.items()
                if key
                not in {
                    "blocked_replay_node_ids",
                    "consecutive_unproductive_steps",
                    "max_consecutive_unproductive_steps",
                }
            },
        )
    cdp_port = _pick_free_port() if provider is None else None
    launch_args = (
        [f"--remote-debugging-port={cdp_port}"] if cdp_port is not None else None
    )
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=headless,
            args=launch_args,
        )
        local_cdp_url = (
            _read_cdp_websocket_url(cdp_port) if cdp_port is not None else None
        )
        page = await browser.new_page()
        try:
            await page.goto(start_url)
            resolved_provider = provider
            if resolved_provider is None:
                resolved_provider = await create_async_stagehand_provider_from_env(
                    model_name=model,
                    page=page,
                    local_cdp_url=local_cdp_url,
                )
            base_adapter = WebKobePlaywrightAdapter(
                page,
                app_name=app_name,
                screenshot_dir=screenshot_dir,
            )
            adapter = StagehandAutomationBackend(
                base_backend=base_adapter,
                provider=resolved_provider,
                goal=stagehand_goal,
                execution_mode=stagehand_execution_mode,
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app=app_name),
                goal="Explore useful website functionality.",
                capture_screenshots=screenshot_dir is not None,
                business_profile=resolved_business_profile,
                visual_delta_provider=resolved_visual_delta_provider,
                enable_exploration_memory=resolved_embedding_provider is not None,
                state_embedding_provider=resolved_embedding_provider,
                action_embedding_provider=resolved_embedding_provider,
                state_embedding_records=embedding_records,
                max_candidates=max_candidates,
                resume_policy=resume_policy,
            )
            def checkpoint(graph: WebKobeGraph) -> None:
                _write_stagehand_checkpoint(
                    graph,
                    output_path=output_path,
                    embedding_path=embedding_path,
                    embedding_records=explorer.state_embedding_records,
                    stagehand_trace_path=stagehand_trace_path,
                )

            explorer.attempt_checkpoint = checkpoint

            historical_steps = resume_graph.total_steps_completed if resume_graph else 0
            replay_metric_baseline = (
                {
                    key: int(resume_graph.meta.get(key, 0))
                    for key in (
                        "replay_attempt_count",
                        "replay_success_count",
                        "replay_failure_count",
                        "replay_mismatch_count",
                    )
                }
                if resume_graph is not None
                else None
            )
            if resume_graph is not None:
                explorer.restore_graph(resume_graph)
                bootstrap_metrics = {
                    "replay_attempt_count": int(
                        (replay_metric_baseline or {}).get("replay_attempt_count", 0)
                    ),
                    "replay_success_count": int(
                        (replay_metric_baseline or {}).get("replay_success_count", 0)
                    ),
                    "replay_failure_count": int(
                        (replay_metric_baseline or {}).get("replay_failure_count", 0)
                    ),
                    "replay_mismatch_count": int(
                        (replay_metric_baseline or {}).get("replay_mismatch_count", 0)
                    ),
                    "last_replay_reason": None,
                    "blocked_replay_node_ids": [],
                }
                policy = resume_policy or ResumePolicy()
                resume_replay_runner = FrontierReplayRunner(explorer)
                blocked_resume_node_ids: set[str] = set()
                replay_attempted = False
                while True:
                    current_graph = explorer.manager.to_graph(
                        start_node_id=explorer.start_node_id,
                    )
                    resume_target = select_resume_frontier(
                        current_graph,
                        policy=policy,
                        blocked_node_ids=blocked_resume_node_ids,
                    )
                    if resume_target is None:
                        stop_reason = (
                            "resume_replay_failed"
                            if replay_attempted
                            else "resume_frontier_exhausted"
                        )
                        current_graph.meta.update(bootstrap_metrics)
                        current_graph.meta["blocked_replay_node_ids"] = sorted(
                            blocked_resume_node_ids
                        )
                        current_graph.meta["exploration_summary"] = {
                            "requested_steps": max(steps, 0),
                            "steps_completed": 0,
                            "stop_reason": stop_reason,
                            "historical_steps": historical_steps,
                            "total_steps_completed": historical_steps,
                        }
                        checkpoint(current_graph)
                        return output_path
                    replay_attempted = True
                    bootstrap_metrics["replay_attempt_count"] += 1
                    replay_result = await resume_replay_runner.replay(
                        resume_target,
                        start_url=start_url,
                    )
                    bootstrap_metrics["last_replay_reason"] = replay_result.reason
                    if not replay_result.success:
                        bootstrap_metrics["replay_failure_count"] += 1
                        if replay_result.reason in {
                            "entry_state_mismatch",
                            "target_state_mismatch",
                        }:
                            bootstrap_metrics["replay_mismatch_count"] += 1
                        blocked_resume_node_ids.add(resume_target.node_id)
                        continue
                    bootstrap_metrics["replay_success_count"] += 1
                    for action_id in resume_target.untried_action_ids:
                        key = ActionAttemptKey(resume_target.node_id, action_id)
                        if key in policy.retry_keys:
                            explorer.prefer_resume_action(key)
                            break
                    bootstrap_metrics["blocked_replay_node_ids"] = sorted(
                        blocked_resume_node_ids
                    )
                    break
                replay_metric_baseline = bootstrap_metrics

            controller_kwargs = {
                "max_consecutive_unproductive_steps": None,
                "step_checkpoint": checkpoint,
            }
            if frontier_replay or resume_graph is not None:
                controller_kwargs.update(
                    {
                        "frontier_replay_runner": FrontierReplayRunner(explorer),
                        "start_url": start_url,
                    }
                )
            if resume_graph is not None:
                controller_kwargs.update(
                    {
                        "replay_metric_baseline": replay_metric_baseline,
                        "historical_steps": historical_steps,
                    }
                )
            controller = WebKobeExplorationController(explorer, **controller_kwargs)
            result = await controller.run(max_steps=max(steps, 1))
            if resume_graph is not None:
                blocked_after_controller = set(
                    result.graph.meta.get("blocked_replay_node_ids", [])
                )
                result.graph.meta["blocked_replay_node_ids"] = sorted(
                    blocked_after_controller | blocked_resume_node_ids
                )
            exploration_summary = {
                "requested_steps": result.summary.requested_steps,
                "steps_completed": result.summary.steps_completed,
                "stop_reason": result.summary.stop_reason,
            }
            if resume_graph is not None:
                exploration_summary.update(
                    {
                        "historical_steps": result.summary.historical_steps,
                        "total_steps_completed": result.summary.total_steps_completed,
                    }
                )
            result.graph.meta["exploration_summary"] = exploration_summary
            checkpoint(result.graph)
            return output_path
        finally:
            await browser.close()
