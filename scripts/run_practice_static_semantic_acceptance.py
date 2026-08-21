from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ai_web_explorer.grounded_web.action_outcome import (
    semantic_observation_from_action_outcome,
    summarize_action_outcome,
)
from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import (
    BrowserAction,
    ReferenceObservation,
    WebKobeEdge,
    WebKobeGraph,
    WebKobeNode,
)
from ai_web_explorer.grounded_web.location_exploration import (
    ExplorationLimits,
    LocationExplorationCoordinator,
    LocationExplorationMemory,
)
from ai_web_explorer.grounded_web.openai_visual_delta import (
    create_openai_action_outcome_provider_from_env,
    create_openai_visual_delta_provider_from_env,
)
from ai_web_explorer.grounded_web.semantic_planning import build_semantic_planning_graph
from ai_web_explorer.safesym_bridge.minimal_semantic_pddl import (
    compile_minimal_semantic_domain,
    compile_minimal_semantic_problem,
)
from ai_web_explorer.safesym_bridge.web_kobe_safesym_smoke import (
    write_web_kobe_safesym_smoke,
)


ROOT = Path(__file__).resolve().parents[1]
SCREENSHOTS = ROOT / "outputs/experiments/practice_automated_testing/latest/screenshots"
OUTPUT = (
    ROOT
    / "outputs/experiments/practice_automated_testing/static_semantic_acceptance_v4_gpt4o"
)
SAFESYM_ROOT = Path(r"C:\Users\moon\Desktop\Projects\SafeSym")
RULES = SAFESYM_ROOT / "configs/constraint_rules.json"
FAST_DOWNWARD = Path(
    r"C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py"
)


@dataclass(frozen=True)
class StaticActionCase:
    case_id: str
    description: str
    before_index: int
    after_index: int
    candidate_aliases: tuple[str, ...]


CASES = (
    StaticActionCase(
        "add_product_to_cart",
        "Add one visible product to the shopping cart",
        1,
        1,
        (
            "add_product_to_cart",
            "add_item_to_cart",
            "add_to_cart",
            "add_bluetooth_headphones_to_cart",
            "add_to_cart_bluetooth_headphones",
        ),
    ),
    StaticActionCase(
        "filter_products",
        "Filter the visible products by category",
        2,
        2,
        ("filter_products", "filter_results", "filter_by_category", "filter_category"),
    ),
    StaticActionCase(
        "open_cart",
        "Open the shopping cart or checkout surface",
        3,
        3,
        ("open_cart", "view_cart", "open_checkout"),
    ),
    StaticActionCase(
        "complete_checkout_information",
        "Complete the required billing information",
        4,
        4,
        (
            "complete_checkout_information",
            "complete_billing_information",
            "fill_billing_information",
        ),
    ),
    StaticActionCase(
        "complete_payment_information",
        "Complete the required payment information",
        5,
        5,
        (
            "complete_payment_information",
            "complete_payment_details",
            "enter_payment_details",
        ),
    ),
    StaticActionCase(
        "place_order",
        "Place the order using the completed checkout form",
        6,
        6,
        ("place_order", "submit_order"),
    ),
)


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def _node(node_id: str, location_id: str, screenshot: Path) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id,
        page_description="Externally supplied screenshot observation",
        page_frame=PageFrame(
            page_id=node_id,
            page_type=location_id,
            url="",
            url_pattern="",
            title="",
        ),
        state_schema={},
        last_state_snapshot={},
        reference_observation=ReferenceObservation(
            url="",
            title="",
            screenshot_path=str(screenshot),
        ),
        node_label=location_id,
        naming_provenance={"source": "initial_screenshot_vlm"},
        semantic_location_hint=location_id,
    )


def _candidate_id(
    coordinator: LocationExplorationCoordinator,
    location_id: str,
    aliases: tuple[str, ...],
) -> tuple[str, object | None]:
    candidates = coordinator.memory.pool_for(location_id).candidates
    for alias in aliases:
        if alias in candidates:
            return alias, candidates[alias]
    return aliases[0], None


def _scan_location(
    coordinator: LocationExplorationCoordinator,
    provider,
    provisional_location: str,
    screenshot: Path,
) -> tuple[str, dict[str, object]]:
    location_id, result, added = coordinator.ensure_candidates(
        provisional_location,
        goal="Explore visible website functionality.",
        screenshot_path=str(screenshot),
        current_signature=None,
        provider=provider,
        max_actions=12,
        scan_kind="initial",
    )
    if result is None or result.trace.status != "summarized":
        raise RuntimeError(f"initial scan failed for {screenshot}: {result}")
    if not result.location_id:
        raise RuntimeError(f"initial scan did not name the location for {screenshot}")
    return location_id, {
        "screenshot": str(screenshot.relative_to(ROOT)),
        "location_id": location_id,
        "added_action_ids": list(added),
        "actions": [
            {
                "action_id": action.action_name,
                "description": action.label,
                "target": action.target_hint,
                "requires": result.requires_by_action_id.get(action.action_name, []),
            }
            for action in result.business_affordances
        ],
        "trace": result.trace.to_dict(),
    }


def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(
            f"refusing to overwrite existing experiment directory: {OUTPUT}"
        )
    OUTPUT.mkdir(parents=True, exist_ok=True)

    candidate_provider = create_openai_visual_delta_provider_from_env(
        model="gpt-4o",
        request_timeout_seconds=90,
    )
    outcome_provider = create_openai_action_outcome_provider_from_env(
        model="gpt-4o",
        request_timeout_seconds=90,
    )
    coordinator = LocationExplorationCoordinator(
        memory=LocationExplorationMemory(
            limits=ExplorationLimits(
                max_vlm_scan_attempts=1,
                max_candidates_per_location=12,
                max_action_attempts_per_candidate=1,
            )
        )
    )

    candidate_observations: list[dict[str, object]] = []
    action_observations: list[dict[str, object]] = []
    external_records: list[dict[str, object]] = []
    nodes: list[WebKobeNode] = []
    edges: list[WebKobeEdge] = []

    current_location, scan = _scan_location(
        coordinator,
        candidate_provider,
        "initial_surface",
        SCREENSHOTS / "before_0001.png",
    )
    candidate_observations.append(scan)
    current_node_id = "observation_0000"
    nodes.append(
        _node(current_node_id, current_location, SCREENSHOTS / "before_0001.png")
    )

    for sequence, case in enumerate(CASES, start=1):
        before = SCREENSHOTS / f"before_{case.before_index:04d}.png"
        after = SCREENSHOTS / f"after_{case.after_index:04d}.png"
        if not before.is_file() or not after.is_file():
            raise FileNotFoundError(f"missing real screenshot pair: {before}, {after}")

        action_id, candidate_record = _candidate_id(
            coordinator,
            current_location,
            case.candidate_aliases,
        )
        result = summarize_action_outcome(
            before_screenshot_path=str(before),
            after_screenshot_path=str(after),
            action_description=case.description,
            provider=outcome_provider,
        )
        if result.trace is None or result.trace.status != "summarized":
            raise RuntimeError(f"action outcome scan failed: {case.case_id}")
        if result.outcome != "success":
            raise RuntimeError(
                f"action did not produce a successful visible outcome: "
                f"{case.case_id}={result.outcome}"
            )

        target_location = current_location
        if result.location_change:
            target_location, target_scan = _scan_location(
                coordinator,
                candidate_provider,
                f"surface_after_{sequence:04d}",
                after,
            )
            candidate_observations.append(target_scan)

        target_node_id = f"observation_{sequence:04d}"
        semantic_observation = semantic_observation_from_action_outcome(
            result,
            source_location=current_location,
            target_location_hint=target_location,
            target_node_id=target_node_id,
        )
        if semantic_observation is None:
            raise RuntimeError(f"missing semantic observation: {case.case_id}")

        update = coordinator.record_action_outcome(
            location_before=current_location,
            location_after=target_location,
            action_id=action_id,
            observable_change=True,
        )
        if update.attempt is not None and update.attempt.status != "success":
            raise RuntimeError(
                f"candidate completion was not recorded: {case.case_id}"
            )

        nodes.append(_node(target_node_id, target_location, after))
        edge = WebKobeEdge(
            source_node_id=current_node_id,
            target_node_id=target_node_id,
            instruction=case.description,
            action=BrowserAction(
                action_kind="external_executed_action",
                locator=None,
                semantic_id=action_id,
                description=case.description,
                action_label=(
                    candidate_record.affordance.label
                    if candidate_record is not None
                    else case.description
                ),
                canonical_action_name=action_id,
                naming_provenance={"source": "initial_screenshot_vlm"},
            ),
            capability=None,
            target_observation=target_node_id,
            observed_delta=[],
            schema_delta=None,
            execution_trace=ExecutionTrace(
                concrete_action_kind="external_executed_action",
                concrete_locator=None,
                concrete_target_sample=(
                    candidate_record.affordance.target_hint
                    if candidate_record is not None
                    else None
                ),
                input_values_used={},
                before_observation_id=current_node_id,
                after_observation_id=target_node_id,
                success=True,
                metadata={
                    "before_screenshot_path": str(before.relative_to(ROOT)),
                    "after_screenshot_path": str(after.relative_to(ROOT)),
                    "action_outcome": {
                        "outcome": result.outcome,
                        "location_change": result.location_change,
                        "evidence": list(result.evidence),
                    },
                },
            ),
            semantic_observation=semantic_observation,
            required_action_ids=(
                list(candidate_record.requires)
                if candidate_record is not None
                else []
            ),
            visual_change_kind=(
                "navigation" if result.location_change else "state_indicator"
            ),
            status=(
                "succeeded_with_navigation"
                if result.location_change
                else "succeeded_with_observed_change"
            ),
        )
        edges.append(edge)
        action_observations.append(
            {
                "sequence": sequence,
                "case_id": case.case_id,
                "candidate_action_id": action_id,
                "candidate_discovered": candidate_record is not None,
                "source_location": current_location,
                "target_location": target_location,
                "required_action_ids": (
                    list(candidate_record.requires)
                    if candidate_record is not None
                    else []
                ),
                "outcome": result.outcome,
                "location_change": result.location_change,
                "evidence": list(result.evidence),
                "trace": result.trace.to_dict(),
            }
        )
        external_records.append(
            {
                "sequence": sequence,
                "case_id": case.case_id,
                "action_description": case.description,
                "before_screenshot": str(before.relative_to(ROOT)),
                "after_screenshot": str(after.relative_to(ROOT)),
                "claim": "The action was executed by an external executor.",
            }
        )
        current_location = target_location
        current_node_id = target_node_id

        _write_json(OUTPUT / "candidate_observations.json", candidate_observations)
        _write_json(OUTPUT / "action_outcomes.json", action_observations)
        _write_json(OUTPUT / "external_execution_records.json", external_records)
        _write_json(OUTPUT / "location_memory.json", coordinator.memory.to_dict())

    graph = WebKobeGraph(
        app="practice_shopping_static_semantic_acceptance_v3_gpt4o",
        start_node_id="observation_0000",
        total_steps_completed=len(edges),
        nodes=nodes,
        edges=edges,
        execution_events=list(edges),
        meta={
            "experiment_kind": "static_external_execution_observations",
            "candidate_model": candidate_provider.model,
            "action_outcome_model": outcome_provider.model,
            "fixed_action_order": [case.case_id for case in CASES],
            "stagehand_called": False,
            "location_exploration": coordinator.memory.to_dict(),
        },
    )
    _write_json(OUTPUT / "graph.json", graph.to_dict())

    semantic_graph, projection_report = build_semantic_planning_graph(graph)
    _write_json(OUTPUT / "semantic_planning_graph.json", semantic_graph.to_dict())
    _write_json(
        OUTPUT / "semantic_projection_report.json", projection_report.to_dict()
    )

    domain = compile_minimal_semantic_domain(semantic_graph)
    problem = compile_minimal_semantic_problem(
        semantic_graph,
        goal_location=current_location,
    )
    (OUTPUT / "domain.pddl").write_text(domain.domain or "", encoding="utf-8")
    (OUTPUT / "problem.pddl").write_text(problem.problem or "", encoding="utf-8")

    smoke = write_web_kobe_safesym_smoke(
        OUTPUT,
        safesym_root=SAFESYM_ROOT,
        rules=RULES,
        fast_downward=FAST_DOWNWARD,
    )
    acceptance = {
        "fixed_sequence_only": True,
        "candidate_scheduling_tested": False,
        "stagehand_called": False,
        "six_actions_projected": len(semantic_graph.actions) == 6,
        "all_edges_included": len(projection_report.included_raw_edge_ids) == 6,
        "undiscovered_external_actions": [
            item["case_id"]
            for item in action_observations
            if not item["candidate_discovered"]
        ],
        "excluded_edges": projection_report.excluded_edges,
        "goal_location": current_location,
        "safesym": smoke.report.to_dict(),
    }
    _write_json(OUTPUT / "acceptance_report.json", acceptance)
    print(json.dumps(acceptance, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
