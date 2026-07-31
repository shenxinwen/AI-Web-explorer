from __future__ import annotations

import hashlib
import json
from dataclasses import replace

from ai_web_explorer.grounded_web.business_profile import PlanningTransition
from ai_web_explorer.grounded_web.graph import BusinessTransition, WebKobeNode
from ai_web_explorer.grounded_web.state_signature import slug_identifier


BUSINESS_STATE_RELEVANCE = {"core", "supporting"}


def should_materialize_business_state(
    business_transition: BusinessTransition | None,
) -> bool:
    if business_transition is None:
        return False
    return (
        business_transition.meaningful_change is True
        and business_transition.relevance in BUSINESS_STATE_RELEVANCE
    )


def should_collapse_same_page_change(
    *,
    source_node: WebKobeNode,
    candidate_node: WebKobeNode,
    business_transition: BusinessTransition | None,
) -> bool:
    if business_transition is None:
        return False
    if business_transition.relevance != "low_value":
        return False
    return (
        source_node.page_frame.page_id == candidate_node.page_frame.page_id
        and source_node.page_frame.url_pattern == candidate_node.page_frame.url_pattern
    )


def resolve_business_target_node(
    *,
    source_node: WebKobeNode,
    candidate_node: WebKobeNode,
    business_transition: BusinessTransition | None,
    planning_transition: PlanningTransition | None,
) -> WebKobeNode:
    if should_materialize_business_state(business_transition):
        semantic_node = replace(
            candidate_node,
            node_label=_business_state_node_label(
                candidate_node=candidate_node,
                business_transition=business_transition,
                planning_transition=planning_transition,
            ),
        )
        return replace(
            semantic_node,
            node_id=_business_state_node_id(
                candidate_node=semantic_node,
                business_transition=business_transition,
                planning_transition=planning_transition,
            ),
        )

    if should_collapse_same_page_change(
        source_node=source_node,
        candidate_node=candidate_node,
        business_transition=business_transition,
    ):
        return replace(
            candidate_node,
            node_id=source_node.node_id,
            planning_state=source_node.planning_state,
        )

    return candidate_node


PROFILE_FACT_STATE_LABELS = {
    "cart_page_visible": "cart",
    "cart_has_items": "cart_with_items",
    "checkout_started": "checkout",
    "checkout_user_info_complete": "checkout_user_info",
    "payment_info_complete": "payment_info",
    "checkout_info_complete": "checkout_info",
    "order_review_ready": "order_review",
    "order_place_pending_sensitive": "order_review",
    "order_completed": "order_complete",
    "product_list_visible": "product_list",
}

ACTION_PREFIXES = (
    "open_",
    "view_",
    "show_",
    "display_",
    "start_",
    "continue_to_",
    "proceed_to_",
    "go_to_",
    "navigate_to_",
)


def _business_state_node_label(
    *,
    candidate_node: WebKobeNode,
    business_transition: BusinessTransition | None,
    planning_transition: PlanningTransition | None,
) -> str:
    fact_label = _label_from_planning_transition(planning_transition)
    if fact_label:
        return fact_label
    action_label = _label_from_business_action(business_transition)
    if action_label:
        return action_label
    base_label = (
        candidate_node.node_label
        or candidate_node.page_frame.page_type
        or candidate_node.page_frame.page_id
    )
    return slug_identifier(base_label, fallback="state")


def _label_from_planning_transition(
    planning_transition: PlanningTransition | None,
) -> str | None:
    if planning_transition is None:
        return None
    for fact in planning_transition.added_facts + planning_transition.post_facts:
        if fact in PROFILE_FACT_STATE_LABELS:
            return PROFILE_FACT_STATE_LABELS[fact]
    for fact in planning_transition.added_facts + planning_transition.post_facts:
        label = _generic_fact_label(fact)
        if label:
            return label
    return None


def _generic_fact_label(fact: str) -> str | None:
    label = slug_identifier(fact, fallback="")
    for suffix in ("_visible", "_ready", "_started", "_complete", "_completed"):
        if label.endswith(suffix):
            label = label[: -len(suffix)]
            break
    return label or None


def _label_from_business_action(
    business_transition: BusinessTransition | None,
) -> str | None:
    if business_transition is None or not business_transition.action_name:
        return None
    label = slug_identifier(business_transition.action_name, fallback="")
    for prefix in ACTION_PREFIXES:
        if label.startswith(prefix):
            label = label[len(prefix) :]
            break
    if label in {"place_order", "submit_order", "complete_order"}:
        return "order_complete"
    return label or None


def _business_state_node_id(
    *,
    candidate_node: WebKobeNode,
    business_transition: BusinessTransition | None,
    planning_transition: PlanningTransition | None,
) -> str:
    post_facts = (
        list(planning_transition.post_facts) if planning_transition is not None else []
    )
    payload = {
        "page_id": candidate_node.page_frame.page_id,
        "post_facts": sorted(post_facts),
    }
    if not post_facts and business_transition is not None:
        payload["action_name"] = business_transition.action_name

    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:10]
    base_label = (
        candidate_node.node_label
        or candidate_node.page_frame.page_type
        or candidate_node.page_frame.page_id
    )
    base = slug_identifier(base_label, fallback="state")
    return f"{base}__business_{digest}"
