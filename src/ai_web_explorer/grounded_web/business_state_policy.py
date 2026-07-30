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
