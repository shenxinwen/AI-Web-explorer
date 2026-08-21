from __future__ import annotations

import json
from pathlib import Path

from ai_web_explorer.grounded_web.capability_graph import ExecutionTrace, PageFrame
from ai_web_explorer.grounded_web.graph import BrowserAction, ReferenceObservation, WebKobeEdge, WebKobeGraph, WebKobeNode
from ai_web_explorer.grounded_web.semantic_model import SemanticObservation
from ai_web_explorer.grounded_web.semantic_planning import build_semantic_planning_graph
from ai_web_explorer.safesym_bridge.minimal_semantic_pddl import compile_minimal_semantic_domain, compile_minimal_semantic_problem
from ai_web_explorer.safesym_bridge.web_kobe_safesym_smoke import write_web_kobe_safesym_smoke

ROOT = Path(__file__).resolve().parents[1]
CHAIN = ROOT / "outputs/experiments/saucedemo/candidate_outcome_chain_v2_gpt4o/chain_report.json"
OUTPUT = ROOT / "outputs/experiments/saucedemo/semantic_projection_v1_gpt4o"
SAFESYM = Path(r"C:\Users\moon\Desktop\Projects\SafeSym")
RULES = SAFESYM / "configs/constraint_rules.json"
DOWNWARD = Path(r"C:\Users\moon\Desktop\Projects\AutoWebWorld\downward\fast-downward.py")
TARGETS = {
    "enter_username": "login_page", "enter_password": "login_page",
    "submit_login": "product_listing_page", "sort_products": "product_listing_page",
    "add_to_cart": "product_listing_page", "open_cart": "cart_page",
    "start_checkout": "checkout_information_form",
    "fill_checkout_information": "checkout_information_form",
    "submit_checkout_information": "checkout_overview",
    "finish_checkout": "checkout_complete_page",
}

def _node(node_id: str, location_id: str, screenshot: Path) -> WebKobeNode:
    return WebKobeNode(
        node_id=node_id, page_description="Externally supplied screenshot observation",
        page_frame=PageFrame(page_id=node_id, page_type=location_id, url="", url_pattern="", title=""),
        state_schema={}, last_state_snapshot={},
        reference_observation=ReferenceObservation(url="", title="", screenshot_path=str(screenshot)),
        node_label=location_id, naming_provenance={"source": "screenshot_vlm"},
        semantic_location_hint=location_id,
    )

def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    records = json.loads(CHAIN.read_text(encoding="utf-8"))["records"]
    nodes, edges = [], []
    first = records[0]
    nodes.append(_node("state_000", first["location_id"], ROOT / first["before"]))
    for index, record in enumerate(records, 1):
        action_id = record["matched_candidate_id"] or record["case_id"]
        source = record["location_id"]
        target = TARGETS[record["case_id"]]
        after = ROOT / record["after"]
        node_id = f"state_{index:03d}"
        nodes.append(_node(node_id, target, after))
        changed = source != target
        edges.append(WebKobeEdge(
            source_node_id=f"state_{index-1:03d}", target_node_id=node_id,
            instruction=record["case_id"],
            action=BrowserAction("external_executed_action", None, action_id, canonical_action_name=action_id),
            capability=None, target_observation=node_id, observed_delta=[], schema_delta=None,
            execution_trace=ExecutionTrace(
                concrete_action_kind="external_executed_action", concrete_locator=None,
                concrete_target_sample=None, input_values_used={},
                before_observation_id=f"state_{index-1:03d}", after_observation_id=node_id,
                success=True, metadata={"static_screenshot_pair": True},
            ),
            semantic_observation=SemanticObservation(
                action_role="navigation" if changed else "presentation_capability",
                source_location=source, target_location=target,
                evidence=list(record["evidence"]), confidence=1.0,
            ),
            required_action_ids=list(record["requires"]),
            status="succeeded_with_navigation" if changed else "succeeded_with_observed_change",
        ))
    raw = WebKobeGraph(app="saucedemo_static_chain", start_node_id="state_000", total_steps_completed=len(edges), nodes=nodes, edges=edges, execution_events=list(edges), meta={"stagehand_called": False})
    (OUTPUT / "raw_graph.json").write_text(json.dumps(raw.to_dict(), indent=2), encoding="utf-8")
    semantic, report = build_semantic_planning_graph(raw)
    (OUTPUT / "semantic_planning_graph.json").write_text(json.dumps(semantic.to_dict(), indent=2), encoding="utf-8")
    (OUTPUT / "projection_report.json").write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    domain = compile_minimal_semantic_domain(semantic)
    problem = compile_minimal_semantic_problem(semantic, goal_location="checkout_complete_page")
    (OUTPUT / "domain.pddl").write_text(domain.domain, encoding="utf-8")
    (OUTPUT / "problem.pddl").write_text(problem.problem, encoding="utf-8")
    smoke = write_web_kobe_safesym_smoke(OUTPUT, safesym_root=SAFESYM, rules=RULES, fast_downward=DOWNWARD)
    result = {"actions": len(semantic.actions), "excluded": report.excluded_edges, "safesym": smoke.report.to_dict()}
    (OUTPUT / "acceptance_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__": main()
