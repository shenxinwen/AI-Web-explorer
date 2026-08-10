from __future__ import annotations

import hashlib
import json
from dataclasses import replace

from ai_web_explorer.grounded_web.business_profile import PlanningTransition
from ai_web_explorer.grounded_web.graph import BusinessTransition, WebKobeNode
from ai_web_explorer.grounded_web.state_signature import slug_identifier


BUSINESS_STATE_RELEVANCE = {"core", "supporting"}


def observation_change_node_id(
    *,
    source_node_id: str,
    action_name: str,
    after_signature: dict,
    added_facts: list[str],
    removed_facts: list[str],
) -> str:
    payload = {
        "source_node_id": source_node_id,
        "action_name": action_name,
        "after_signature": after_signature,
        "added_facts": sorted(set(added_facts)),
        "removed_facts": sorted(set(removed_facts)),
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:12]
    return f"{source_node_id}__observation_{digest}"


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
        return replace(
            candidate_node,
            node_id=_business_state_node_id(
                candidate_node=candidate_node,
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
    payload = {
        "page_id": candidate_node.page_frame.page_id,
    }
    if business_transition is not None and business_transition.action_name:
        payload["action_name"] = business_transition.action_name

    digest = hashlib.sha1(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:10]
    base_label = _label_from_business_action(business_transition) or (
        candidate_node.page_frame.page_type or candidate_node.page_frame.page_id
    )
    base = slug_identifier(base_label, fallback="state")
    return f"{base}__business_{digest}"
