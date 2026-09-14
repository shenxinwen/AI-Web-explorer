from __future__ import annotations

import json
import socket
import tempfile
import time
import urllib.request
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from ai_web_explorer.grounded_web.capability_graph import Evidence, PageFrame
from ai_web_explorer.grounded_web.graph import (
    ReferenceObservation,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.controller import (
    RUNTIME_BUDGET_META_KEY,
    WebKobeExplorationController,
)
from ai_web_explorer.grounded_web.business_profile import (
    BusinessFlowProfile,
    ecommerce_checkout_profile,
)
from ai_web_explorer.grounded_web.explorer import WebKobeExplorer
from ai_web_explorer.grounded_web.frontier_replay import (
    FrontierReplayRunner,
    is_replay_mismatch_reason,
)
from ai_web_explorer.grounded_web.location_exploration import (
    LOCATION_EXPLORATION_META_KEY,
    ExplorationLimits,
    LocationExplorationCoordinator,
)
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
    create_openai_action_outcome_provider_from_env,
    create_openai_visual_delta_provider_from_env,
)
from ai_web_explorer.grounded_web.openai_risk_detection import (
    create_openai_risk_detection_provider_from_env,
)
from ai_web_explorer.grounded_web.embedding_provider import (
    create_embedding_provider_from_env,
)
from ai_web_explorer.grounded_web.stagehand_backend import (
    StagehandAutomationBackend,
)
from ai_web_explorer.grounded_web.stagehand_prompt import (
    build_generic_stagehand_exploration_goal,
    build_site_input_context,
)
from ai_web_explorer.grounded_web.exploration_semantics import (
    validate_final_order_authorization,
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


_RUNTIME_STATE_KEYS = (
    "formal_action_attempts",
    "consecutive_no_progress",
    "semantic_progress_count",
    "replay_attempt_count",
    "replay_success_count",
    "replay_failure_count",
    "replay_mismatch_count",
    "frontier_replay_attempts",
    "blocked_replay_node_ids",
)


def _runtime_state_from_graph(graph: WebKobeGraph) -> dict[str, Any]:
    payload = graph.meta.get(RUNTIME_BUDGET_META_KEY)
    if isinstance(payload, dict):
        return dict(payload)
    return {key: graph.meta[key] for key in _RUNTIME_STATE_KEYS if key in graph.meta}


def _mirror_runtime_state(graph: WebKobeGraph, state: dict[str, Any]) -> None:
    graph.meta[RUNTIME_BUDGET_META_KEY] = dict(state)
    graph.meta.update(state)


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
    payload.compact_graph.setdefault("meta", {})["frontier_metrics"] = (
        _frontier_metrics_for_graph(graph)
    )

    evidence_text = json.dumps(payload.evidence_sidecar, indent=2, ensure_ascii=False)
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


async def run_stagehand_exploration(
    output_path: Path,
    *,
    start_url: str,
    app_name: str = "web",
    stagehand_trace_path: Path | None = None,
    headless: bool = True,
    steps: int | None = None,
    provider=None,
    model: str | None = None,
    screenshot_dir: Path | None = None,
    visual_delta_provider=None,
    action_outcome_provider=None,
    risk_detection_provider=None,
    use_openai_visual_delta: bool = False,
    use_openai_risk_detection: bool = False,
    visual_delta_model: str | None = None,
    action_outcome_model: str | None = None,
    risk_detection_model: str | None = None,
    state_embedding_provider=None,
    embedding_path: Path | None = None,
    use_state_embeddings: bool = False,
    embedding_model: str | None = None,
    embedding_dimension: int | None = None,
    site_purpose: str | None = None,
    site_adapter: str | None = None,
    business_profile: str | BusinessFlowProfile | None = None,
    stagehand_execution_mode: str = "observed_action",
    max_candidates: int = 5,
    frontier_replay: bool = False,
    exploration_condition: str = "linear",
    random_seed: int | None = None,
    resume_graph: WebKobeGraph | None = None,
    resume_policy: ResumePolicy | None = None,
    limits: ExplorationLimits | None = None,
    allow_test_site_final_order: bool = True,
    viewport_width: int = 1440,
    viewport_height: int = 1000,
    vlm_request_timeout_seconds: float | None = None,
    stagehand_action_timeout_seconds: float | None = None,
) -> Path:
    from playwright.async_api import async_playwright

    if exploration_condition not in {"ungated_random", "linear", "full"}:
        raise ValueError(f"invalid exploration condition: {exploration_condition}")
    if exploration_condition == "ungated_random" and frontier_replay:
        raise ValueError("ungated_random cannot enable frontier replay")
    if exploration_condition == "full":
        frontier_replay = True
    if exploration_condition != "ungated_random" and random_seed is not None:
        raise ValueError("random seed is only valid for ungated_random")

    final_order_allowed = validate_final_order_authorization(
        start_url=start_url,
        allowed=allow_test_site_final_order,
    )
    if resume_graph is not None and limits is None:
        persisted_memory = resume_graph.meta.get(LOCATION_EXPLORATION_META_KEY)
        if isinstance(persisted_memory, dict):
            limits = ExplorationLimits.from_dict(persisted_memory.get("limits"))
    if limits is None:
        limits = ExplorationLimits(max_candidates_per_location=max_candidates)
    location_scoped = True

    if (
        visual_delta_provider is not None
        or action_outcome_provider is not None
        or risk_detection_provider is not None
        or use_openai_visual_delta
        or use_openai_risk_detection
    ) and (screenshot_dir is None):
        raise ValueError("screenshot_dir is required for visual delta analysis.")
    resolved_visual_delta_provider = visual_delta_provider
    if resolved_visual_delta_provider is None and use_openai_visual_delta:
        resolved_visual_delta_provider = create_openai_visual_delta_provider_from_env(
            model=visual_delta_model,
            request_timeout_seconds=vlm_request_timeout_seconds,
        )
    resolved_action_outcome_provider = action_outcome_provider
    if resolved_action_outcome_provider is None and (
        use_openai_visual_delta or action_outcome_model is not None
    ):
        resolved_action_outcome_provider = (
            create_openai_action_outcome_provider_from_env(
                model=action_outcome_model,
                request_timeout_seconds=vlm_request_timeout_seconds,
            )
        )
    if resolved_action_outcome_provider is None:
        resolved_action_outcome_provider = resolved_visual_delta_provider
    resolved_risk_detection_provider = risk_detection_provider
    if resolved_risk_detection_provider is None and use_openai_risk_detection:
        resolved_risk_detection_provider = (
            create_openai_risk_detection_provider_from_env(
                model=risk_detection_model,
                request_timeout_seconds=vlm_request_timeout_seconds,
            )
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
        allow_final_order=final_order_allowed,
    )
    site_input_context = build_site_input_context(
        site_adapter,
        run_token=str(time.time_ns())[-8:],
    )
    resolved_business_profile = _resolve_business_profile(business_profile)
    if resume_policy is not None and resume_graph is None:
        raise ValueError("resume_policy_requires_resume_graph")
    if resume_graph is not None:
        validate_resume_graph(resume_graph, app_name=app_name)
        resume_policy = resume_policy or ResumePolicy()
        if not location_scoped:
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
        page = await browser.new_page(
            viewport={"width": viewport_width, "height": viewport_height}
        )
        try:
            await page.goto(start_url)
            resolved_provider = provider
            if resolved_provider is None:
                resolved_provider = await create_async_stagehand_provider_from_env(
                    model_name=model,
                    page=page,
                    local_cdp_url=local_cdp_url,
                )
            base_adapter_kwargs = {
                "app_name": app_name,
                "screenshot_dir": screenshot_dir,
            }
            if site_adapter is not None:
                base_adapter_kwargs["site_adapter"] = site_adapter
            base_adapter = WebKobePlaywrightAdapter(page, **base_adapter_kwargs)
            adapter = StagehandAutomationBackend(
                base_backend=base_adapter,
                provider=resolved_provider,
                goal=stagehand_goal,
                execution_mode=stagehand_execution_mode,
                action_timeout_seconds=stagehand_action_timeout_seconds,
                site_input_context=site_input_context,
                post_action_settle_ms=3000 if site_adapter == "realworld" else None,
            )
            candidate_selection_policy = (
                "ungated_random"
                if exploration_condition == "ungated_random"
                else "deterministic"
            )
            explorer = WebKobeExplorer(
                adapter=adapter,
                semantic_assistor=DeterministicSemanticAssistor(app=app_name),
                goal="Explore useful website functionality.",
                capture_screenshots=screenshot_dir is not None,
                business_profile=resolved_business_profile,
                visual_delta_provider=resolved_visual_delta_provider,
                action_outcome_provider=resolved_action_outcome_provider,
                risk_detection_provider=resolved_risk_detection_provider,
                enable_exploration_memory=resolved_embedding_provider is not None,
                state_embedding_provider=resolved_embedding_provider,
                action_embedding_provider=resolved_embedding_provider,
                state_embedding_records=embedding_records,
                max_candidates=max_candidates,
                resume_policy=resume_policy,
                exploration_limits=limits,
                location_exploration_coordinator=LocationExplorationCoordinator(
                    limits=limits,
                    selection_policy=candidate_selection_policy,
                    random_seed=random_seed,
                ),
            )

            def checkpoint(graph: WebKobeGraph) -> None:
                graph.meta["exploration_condition"] = exploration_condition
                graph.meta["candidate_selection_policy"] = candidate_selection_policy
                graph.meta["random_seed"] = random_seed
                if location_scoped and limits is not None:
                    graph.meta["exploration_limits"] = limits.to_dict()
                _write_stagehand_checkpoint(
                    graph,
                    output_path=output_path,
                    embedding_path=embedding_path,
                    embedding_records=explorer.state_embedding_records,
                    stagehand_trace_path=stagehand_trace_path,
                )

            explorer.attempt_checkpoint = checkpoint

            historical_steps = resume_graph.total_steps_completed if resume_graph else 0
            resolved_steps = (
                steps
                if steps is not None
                else (
                    limits.max_exploration_steps
                    if location_scoped and limits is not None
                    else 8
                )
            )
            resume_runtime_state = (
                _runtime_state_from_graph(resume_graph)
                if resume_graph is not None
                else {}
            )
            replay_metric_baseline = (
                {
                    key: int(resume_runtime_state.get(key, 0))
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
                    "blocked_replay_node_ids": (
                        list(resume_runtime_state.get("blocked_replay_node_ids", []))
                        if location_scoped
                        else []
                    ),
                }
                policy = resume_policy or ResumePolicy()
                resume_replay_runner = FrontierReplayRunner(explorer)
                blocked_resume_node_ids: set[str] = set(
                    bootstrap_metrics["blocked_replay_node_ids"]
                )
                bootstrap_frontier_attempts = {
                    str(key): int(value)
                    for key, value in (
                        resume_runtime_state.get("frontier_replay_attempts", {})
                        if location_scoped
                        and isinstance(
                            resume_runtime_state.get("frontier_replay_attempts", {}),
                            dict,
                        )
                        else {}
                    ).items()
                }

                def persist_bootstrap_runtime(graph: WebKobeGraph) -> dict[str, Any]:
                    state = _runtime_state_from_graph(graph)
                    for key in (
                        "replay_attempt_count",
                        "replay_success_count",
                        "replay_failure_count",
                        "replay_mismatch_count",
                    ):
                        state[key] = int(bootstrap_metrics[key])
                    state["frontier_replay_attempts"] = dict(
                        sorted(bootstrap_frontier_attempts.items())
                    )
                    state["blocked_replay_node_ids"] = sorted(blocked_resume_node_ids)
                    _mirror_runtime_state(graph, state)
                    graph.meta.update(bootstrap_metrics)
                    return state

                replay_attempted = False
                while True:
                    current_graph = explorer.manager.to_graph(
                        start_node_id=explorer.start_node_id,
                    )
                    if (
                        location_scoped
                        and limits is not None
                        and bootstrap_metrics["replay_attempt_count"]
                        >= limits.max_total_replays
                    ):
                        state = persist_bootstrap_runtime(current_graph)
                        current_graph.meta["exploration_summary"] = {
                            "requested_steps": max(resolved_steps, 0),
                            "steps_completed": 0,
                            "stop_reason": "total_replay_limit_reached",
                            "formal_action_attempts": int(
                                state.get("formal_action_attempts", 0)
                            ),
                            "semantic_progress_count": int(
                                state.get("semantic_progress_count", 0)
                            ),
                            "consecutive_no_progress": int(
                                state.get("consecutive_no_progress", 0)
                            ),
                            "replay_attempt_count": bootstrap_metrics[
                                "replay_attempt_count"
                            ],
                            "frontier_replay_attempts": dict(
                                sorted(bootstrap_frontier_attempts.items())
                            ),
                            "limits": limits.to_dict(),
                            "historical_steps": historical_steps,
                            "total_steps_completed": historical_steps,
                        }
                        checkpoint(current_graph)
                        return output_path
                    resume_target = select_resume_frontier(
                        current_graph,
                        policy=policy,
                        blocked_node_ids=blocked_resume_node_ids,
                    )
                    if resume_target is None:
                        stop_reason = (
                            "no_recoverable_frontier"
                            if location_scoped and replay_attempted
                            else (
                                "frontier_exhausted"
                                if location_scoped
                                else (
                                    "resume_replay_failed"
                                    if replay_attempted
                                    else "resume_frontier_exhausted"
                                )
                            )
                        )
                        state = persist_bootstrap_runtime(current_graph)
                        if location_scoped and limits is not None:
                            current_graph.meta["exploration_summary"] = {
                                "requested_steps": max(resolved_steps, 0),
                                "steps_completed": 0,
                                "stop_reason": stop_reason,
                                "formal_action_attempts": int(
                                    state.get("formal_action_attempts", 0)
                                ),
                                "semantic_progress_count": int(
                                    state.get("semantic_progress_count", 0)
                                ),
                                "consecutive_no_progress": int(
                                    state.get("consecutive_no_progress", 0)
                                ),
                                "replay_attempt_count": bootstrap_metrics[
                                    "replay_attempt_count"
                                ],
                                "frontier_replay_attempts": dict(
                                    sorted(bootstrap_frontier_attempts.items())
                                ),
                                "limits": limits.to_dict(),
                                "historical_steps": historical_steps,
                                "total_steps_completed": historical_steps,
                            }
                        else:
                            current_graph.meta["exploration_summary"] = {
                                "requested_steps": max(resolved_steps, 0),
                                "steps_completed": 0,
                                "stop_reason": stop_reason,
                                "historical_steps": historical_steps,
                                "total_steps_completed": historical_steps,
                            }
                        checkpoint(current_graph)
                        return output_path
                    replay_attempted = True
                    if location_scoped and limits is not None:
                        target_key = str(resume_target.node_id)
                        if (
                            bootstrap_frontier_attempts.get(target_key, 0)
                            >= limits.max_replay_attempts_per_frontier
                        ):
                            blocked_resume_node_ids.add(target_key)
                            continue
                        bootstrap_frontier_attempts[target_key] = (
                            bootstrap_frontier_attempts.get(target_key, 0) + 1
                        )
                    bootstrap_metrics["replay_attempt_count"] += 1
                    replay_result = await resume_replay_runner.replay(
                        resume_target,
                        start_url=start_url,
                    )
                    bootstrap_metrics["last_replay_reason"] = replay_result.reason
                    if not replay_result.success:
                        bootstrap_metrics["replay_failure_count"] += 1
                        if is_replay_mismatch_reason(replay_result.reason):
                            bootstrap_metrics["replay_mismatch_count"] += 1
                        if not location_scoped or (
                            limits is not None
                            and bootstrap_frontier_attempts[str(resume_target.node_id)]
                            >= limits.max_replay_attempts_per_frontier
                        ):
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
                    if location_scoped:
                        bootstrap_metrics["frontier_replay_attempts"] = dict(
                            sorted(bootstrap_frontier_attempts.items())
                        )
                    break
                replay_metric_baseline = bootstrap_metrics

            controller_kwargs = {
                # Candidate retries and location exhaustion now bound the
                # location-scoped path; a global no-progress counter could
                # stop it before other candidates or replay frontiers run.
                "max_consecutive_unproductive_steps": None,
                "step_checkpoint": checkpoint,
            }
            if location_scoped and limits is not None:
                controller_kwargs["limits"] = limits
                if resume_graph is not None:
                    runtime_state_for_controller = dict(resume_runtime_state)
                    for key in (
                        "replay_attempt_count",
                        "replay_success_count",
                        "replay_failure_count",
                        "replay_mismatch_count",
                    ):
                        runtime_state_for_controller[key] = max(
                            int(runtime_state_for_controller.get(key, 0)),
                            int(bootstrap_metrics[key]),
                        )
                    existing_frontier_attempts = runtime_state_for_controller.get(
                        "frontier_replay_attempts", {}
                    )
                    if not isinstance(existing_frontier_attempts, dict):
                        existing_frontier_attempts = {}
                    runtime_state_for_controller["frontier_replay_attempts"] = {
                        key: max(
                            int(existing_frontier_attempts.get(key, 0)),
                            int(bootstrap_frontier_attempts.get(key, 0)),
                        )
                        for key in set(existing_frontier_attempts)
                        | set(bootstrap_frontier_attempts)
                    }
                    runtime_state_for_controller["blocked_replay_node_ids"] = sorted(
                        set(
                            runtime_state_for_controller.get(
                                "blocked_replay_node_ids", []
                            )
                        )
                        | blocked_resume_node_ids
                    )
                    controller_kwargs["runtime_budget_state"] = (
                        runtime_state_for_controller
                    )
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
            result = await controller.run(max_steps=max(resolved_steps, 1))
            runtime_state = _runtime_state_from_graph(result.graph)
            if resume_graph is not None:
                for key in (
                    "replay_attempt_count",
                    "replay_success_count",
                    "replay_failure_count",
                    "replay_mismatch_count",
                ):
                    runtime_state[key] = max(
                        int(runtime_state.get(key, 0)),
                        int(bootstrap_metrics[key]),
                    )
                blocked_after_controller = set(
                    runtime_state.get("blocked_replay_node_ids", [])
                )
                runtime_state["blocked_replay_node_ids"] = sorted(
                    blocked_after_controller | blocked_resume_node_ids
                )
                controller_frontier_attempts = runtime_state.get(
                    "frontier_replay_attempts", {}
                )
                if not isinstance(controller_frontier_attempts, dict):
                    controller_frontier_attempts = {}
                runtime_state["frontier_replay_attempts"] = {
                    key: max(
                        int(controller_frontier_attempts.get(key, 0)),
                        int(value),
                    )
                    for key, value in {
                        **controller_frontier_attempts,
                        **bootstrap_frontier_attempts,
                    }.items()
                }
            _mirror_runtime_state(result.graph, runtime_state)
            if location_scoped and limits is not None:
                formal_action_attempts = int(
                    runtime_state.get(
                        "formal_action_attempts",
                        result.graph.meta.get("formal_action_attempts", 0),
                    )
                )
                semantic_progress_count = int(
                    runtime_state.get("semantic_progress_count", 0)
                )
                consecutive_no_progress = int(
                    runtime_state.get("consecutive_no_progress", 0)
                )
                frontier_replay_attempts = runtime_state.get(
                    "frontier_replay_attempts", {}
                )
                if not isinstance(frontier_replay_attempts, dict):
                    frontier_replay_attempts = {}
                runtime_state["frontier_replay_attempts"] = dict(
                    sorted(frontier_replay_attempts.items())
                )
                _mirror_runtime_state(result.graph, runtime_state)
            exploration_summary = {
                "requested_steps": result.summary.requested_steps,
                "steps_completed": result.summary.steps_completed,
                "stop_reason": result.summary.stop_reason,
            }
            if location_scoped and limits is not None:
                exploration_summary.update(
                    {
                        "formal_action_attempts": formal_action_attempts,
                        "semantic_progress_count": semantic_progress_count,
                        "consecutive_no_progress": consecutive_no_progress,
                        "replay_attempt_count": int(
                            runtime_state.get("replay_attempt_count", 0)
                        ),
                        "frontier_replay_attempts": dict(
                            sorted(runtime_state["frontier_replay_attempts"].items())
                        ),
                        "limits": limits.to_dict(),
                    }
                )
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
