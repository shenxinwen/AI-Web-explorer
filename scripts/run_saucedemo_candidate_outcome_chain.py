from __future__ import annotations

import json
from pathlib import Path

from ai_web_explorer.grounded_web.action_outcome import summarize_action_outcome
from ai_web_explorer.grounded_web.business_affordance import VisualAffordanceRequest, summarize_visual_affordances
from ai_web_explorer.grounded_web.openai_visual_delta import create_openai_action_outcome_provider_from_env, create_openai_visual_delta_provider_from_env

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "outputs/experiments/saucedemo/static_semantic_input_v1/action_pairs"
OUTPUT = ROOT / "outputs/experiments/saucedemo/candidate_outcome_chain_v2_gpt4o"
CASES = [
    ("enter_username", "Enter the username", "enter_username", ("enter_username",)),
    ("enter_password", "Enter the password", "enter_password", ("enter_password",)),
    ("submit_login", "Submit the login form", "submit_login", ("submit_login",)),
    ("sort_products", "Sort the product list", "sort_products", ("sort_products",)),
    ("add_to_cart", "Add one product to the cart", "add_to_cart", ("add_to_cart",)),
    ("open_cart", "Open the shopping cart", "open_cart", ("view_cart", "open_cart")),
    ("start_checkout", "Proceed to checkout", "start_checkout", ("proceed_to_checkout", "start_checkout")),
    ("fill_checkout_information", "Fill the checkout information fields", "fill_checkout_information", ("fill_checkout_information",)),
    ("submit_checkout_information", "Submit the checkout information form", "submit_checkout_information_candidate", ("submit_checkout_information", "submit_checkout_form")),
    ("finish_checkout", "Complete the checkout", "finish_checkout", ("complete_checkout", "finish_checkout")),
]

def main() -> None:
    if OUTPUT.exists() and any(OUTPUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    candidate_provider = create_openai_visual_delta_provider_from_env(model="gpt-4o", request_timeout_seconds=90)
    outcome_provider = create_openai_action_outcome_provider_from_env(model="gpt-4o", request_timeout_seconds=90)
    records = []
    for case_id, description, stem, aliases in CASES:
        before = IMAGES / f"{stem}_before.png"
        after = IMAGES / f"{stem}_after.png"
        candidates = summarize_visual_affordances(
            VisualAffordanceRequest(goal="Explore visible website functionality.", current_screenshot_path=str(before), max_actions=8),
            provider=candidate_provider,
        )
        by_id = {action.action_name: action for action in candidates.business_affordances}
        matched = next((alias for alias in aliases if alias in by_id), None)
        outcome = summarize_action_outcome(
            before_screenshot_path=str(before), after_screenshot_path=str(after),
            action_description=description, provider=outcome_provider,
        )
        records.append({
            "case_id": case_id, "before": str(before.relative_to(ROOT)), "after": str(after.relative_to(ROOT)),
            "location_id": candidates.location_id, "candidate_ids": list(by_id), "matched_candidate_id": matched,
            "requires": candidates.requires_by_action_id.get(matched, []) if matched else [],
            "candidate_status": candidates.trace.status, "outcome": outcome.outcome,
            "location_change": outcome.location_change, "evidence": list(outcome.evidence),
            "outcome_status": outcome.trace.status if outcome.trace else None,
        })
        print(case_id, matched, outcome.outcome, outcome.location_change)
    (OUTPUT / "chain_report.json").write_text(json.dumps({"sequence_assumed": True, "records": records}, indent=2, ensure_ascii=False), encoding="utf-8")

if __name__ == "__main__":
    main()
