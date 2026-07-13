from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from ai_web_explorer.safesym_bridge.capability_graph import (
    AvailabilityCondition,
    Capability,
    CapabilityTransition,
    Evidence,
    ExecutionTrace,
    GroundingPattern,
    InputSlot,
    ObservedDelta,
    PageFrame,
    SemanticPageState,
    StateChangeHint,
    StateIndicator,
    WebCapabilityGraph,
)
from ai_web_explorer.safesym_bridge.models import ObservedTransition, StateSnapshot
from ai_web_explorer.safesym_bridge.observed_graph import _url_pattern_for

PAGE_TYPES = {
    "login": "login",
    "inventory": "product_listing",
    "cart": "cart",
    "checkout_info": "checkout_form",
    "checkout_overview": "checkout_review",
    "checkout_complete": "confirmation",
}

HEADINGS = {
    "login": None,
    "inventory": "Products",
    "cart": "Your Cart",
    "checkout_info": "Checkout: Your Information",
    "checkout_overview": "Checkout: Overview",
    "checkout_complete": "Checkout: Complete!",
}


@dataclass(frozen=True)
class CapabilityRule:
    capability_id: str
    semantic_action: str
    action_kind: str
    target_type: str | None
    target_role: str | None
    grounding: GroundingPattern
    availability: AvailabilityCondition
    input_schema: tuple[InputSlot, ...] = ()


CAPABILITY_RULES = {
    "login_submit": CapabilityRule(
        capability_id="submit_login_form",
        semantic_action="login_submit",
        action_kind="composite",
        target_type="form",
        target_role="login_form",
        input_schema=(
            InputSlot("username", "text", required=True),
            InputSlot("password", "password", required=True),
        ),
        grounding=GroundingPattern(
            locator_strategy="form_fields",
            locator_pattern=None,
            target_selection_policy="single",
            field_bindings={
                "username": "#user-name",
                "password": "#password",
                "submit": "#login-button",
            },
        ),
        availability=AvailabilityCondition(required_page_type="login"),
    ),
    "product_add_to_cart": CapabilityRule(
        capability_id="add_to_cart_product",
        semantic_action="add_to_cart",
        action_kind="click",
        target_type="product",
        target_role="listed_item",
        grounding=GroundingPattern(
            locator_strategy="css_pattern",
            locator_pattern='button[data-test^="add-to-cart"]',
            target_selection_policy="first_available",
        ),
        availability=AvailabilityCondition(
            required_page_type="product_listing",
            required_target_presence="product",
        ),
    ),
    "cart_open": CapabilityRule(
        capability_id="open_cart",
        semantic_action="open_cart",
        action_kind="click",
        target_type="cart",
        target_role="global_nav",
        grounding=GroundingPattern(
            locator_strategy="css",
            locator_pattern=".shopping_cart_link",
            target_selection_policy="single",
        ),
        availability=AvailabilityCondition(required_page_type="product_listing"),
    ),
    "cart_checkout_start": CapabilityRule(
        capability_id="checkout_start",
        semantic_action="checkout_start",
        action_kind="click",
        target_type="cart",
        target_role="current_cart",
        grounding=GroundingPattern(
            locator_strategy="css",
            locator_pattern='button[data-test="checkout"]',
            target_selection_policy="single",
        ),
        availability=AvailabilityCondition(
            required_page_type="cart",
            required_state_indicators={"cart_nonempty": True},
        ),
    ),
    "checkout_info_submit": CapabilityRule(
        capability_id="submit_checkout_info",
        semantic_action="submit_checkout_info",
        action_kind="composite",
        target_type="form",
        target_role="checkout_info_form",
        input_schema=(
            InputSlot("first_name", "text", required=True),
            InputSlot("last_name", "text", required=True),
            InputSlot("postal_code", "text", required=True),
        ),
        grounding=GroundingPattern(
            locator_strategy="form_fields",
            locator_pattern=None,
            target_selection_policy="single",
            field_bindings={
                "first_name": "#first-name",
                "last_name": "#last-name",
                "postal_code": "#postal-code",
                "submit": "#continue",
            },
        ),
        availability=AvailabilityCondition(
            required_page_type="checkout_form",
            required_state_indicators={"checkout_info_complete": True},
        ),
    ),
    "order_place_confirm": CapabilityRule(
        capability_id="place_order",
        semantic_action="place_order",
        action_kind="click",
        target_type="order",
        target_role="pending_order",
        grounding=GroundingPattern(
            locator_strategy="css",
            locator_pattern='button[data-test="finish"]',
            target_selection_policy="single",
        ),
        availability=AvailabilityCondition(
            required_page_type="checkout_review",
            required_state_indicators={"order_review_ready": True},
        ),
    ),
}


def _page_type(page_id: str) -> str:
    return PAGE_TYPES.get(page_id, page_id)


def _indicator_values(snapshot: StateSnapshot) -> dict[str, bool | str | int]:
    signature = snapshot.signature
    values: dict[str, bool | str | int] = {}
    if "is_logged_in" in signature:
        values["logged_in"] = bool(signature["is_logged_in"])
    if "cart_count" in signature:
        values["cart_nonempty"] = int(signature["cart_count"]) > 0
    if "checkout_info_filled" in signature:
        values["checkout_info_complete"] = bool(signature["checkout_info_filled"])
    if "order_review_ready" in signature:
        values["order_review_ready"] = bool(signature["order_review_ready"])
    if "order_created" in signature:
        values["order_created"] = bool(signature["order_created"])
    if "username_filled" in signature and "password_filled" in signature:
        values["login_form_ready"] = bool(signature["username_filled"]) and bool(
            signature["password_filled"]
        )
    return values


def _state_id(snapshot: StateSnapshot) -> str:
    page_type = _page_type(snapshot.page_id)
    indicators = _indicator_values(snapshot)
    if page_type == "login":
        return "login_ready" if indicators.get("login_form_ready") else "login"
    if page_type == "product_listing":
        return (
            "product_listing_cart_nonempty"
            if indicators.get("cart_nonempty")
            else "product_listing_cart_empty"
        )
    if page_type == "cart":
        return "cart_nonempty" if indicators.get("cart_nonempty") else "cart_empty"
    if page_type == "checkout_form":
        return (
            "checkout_form_complete"
            if indicators.get("checkout_info_complete")
            else "checkout_form_incomplete"
        )
    if page_type == "checkout_review":
        return (
            "checkout_review_ready"
            if indicators.get("order_review_ready")
            else "checkout_review"
        )
    if page_type == "confirmation":
        return (
            "confirmation_order_created"
            if indicators.get("order_created")
            else "confirmation"
        )
    return page_type


def _evidence(
    source: str,
    snapshot: StateSnapshot,
    *,
    text_sample: str | None = None,
) -> Evidence:
    return Evidence(
        source=source,
        selector=None,
        text_sample=text_sample,
        url=snapshot.url,
        confidence=1.0,
    )


def _state_indicators(snapshot: StateSnapshot) -> list[StateIndicator]:
    evidence = [_evidence("state_signature", snapshot)]
    return [
        StateIndicator(name=name, value=value, role="planning_state", evidence=evidence)
        for name, value in sorted(_indicator_values(snapshot).items())
    ]


def _page_frame(snapshot: StateSnapshot) -> PageFrame:
    evidence = [_evidence("url", snapshot), _evidence("state_signature", snapshot)]
    indicators = _indicator_values(snapshot)
    return PageFrame(
        page_id=f"saucedemo:{snapshot.page_id}",
        page_type=_page_type(snapshot.page_id),
        url=snapshot.url,
        url_pattern=_url_pattern_for(snapshot.url),
        title=snapshot.title,
        heading=HEADINGS.get(snapshot.page_id),
        signature_hints=indicators,
        evidence=evidence,
    )


def _observed_delta(before: StateSnapshot, after: StateSnapshot) -> list[ObservedDelta]:
    deltas: list[ObservedDelta] = []
    before_page_type = _page_type(before.page_id)
    after_page_type = _page_type(after.page_id)
    if before_page_type != after_page_type:
        deltas.append(
            ObservedDelta(
                field="page_type",
                before=before_page_type,
                after=after_page_type,
                delta_type="page_frame_change",
                evidence=[_evidence("transition_diff", after)],
            )
        )
    before_values = _indicator_values(before)
    after_values = _indicator_values(after)
    for key in sorted(set(before_values) & set(after_values)):
        before_value = before_values.get(key)
        after_value = after_values.get(key)
        if before_value != after_value:
            deltas.append(
                ObservedDelta(
                    field=key,
                    before=before_value,
                    after=after_value,
                    delta_type="state_indicator_change",
                    evidence=[_evidence("transition_diff", after)],
                )
            )
    return deltas


def _transition_kind(before: StateSnapshot, after: StateSnapshot) -> str:
    if _page_type(before.page_id) != _page_type(after.page_id):
        return "navigation"
    return "state_delta"


def _capability_for_transition(transition: ObservedTransition) -> Capability:
    rule = CAPABILITY_RULES[transition.action.semantic_id]
    deltas = _observed_delta(transition.source, transition.target)
    return Capability(
        capability_id=rule.capability_id,
        semantic_action=rule.semantic_action,
        action_kind=rule.action_kind,
        target_type=rule.target_type,
        target_role=rule.target_role,
        input_schema=list(rule.input_schema),
        grounding=rule.grounding,
        availability=rule.availability,
        expected_delta=[
            StateChangeHint(delta.field, delta.before, delta.after)
            for delta in deltas
        ],
        evidence=[
            _evidence(
                "resolver_rule",
                transition.source,
                text_sample=transition.action.raw_description,
            )
        ],
    )


def _expected_delta_for_rule(rule: CapabilityRule) -> list[StateChangeHint]:
    if rule.capability_id == "add_to_cart_product":
        return [StateChangeHint("cart_nonempty", False, True)]
    if rule.capability_id == "open_cart":
        return [StateChangeHint("page_type", "product_listing", "cart")]
    if rule.capability_id == "checkout_start":
        return [StateChangeHint("page_type", "cart", "checkout_form")]
    if rule.capability_id == "submit_checkout_info":
        return [StateChangeHint("page_type", "checkout_form", "checkout_review")]
    if rule.capability_id == "place_order":
        return [StateChangeHint("page_type", "checkout_review", "confirmation")]
    if rule.capability_id == "submit_login_form":
        return [
            StateChangeHint("logged_in", False, True),
            StateChangeHint("page_type", "login", "product_listing"),
        ]
    return []


def _capability_from_rule(rule: CapabilityRule, snapshot: StateSnapshot) -> Capability:
    return Capability(
        capability_id=rule.capability_id,
        semantic_action=rule.semantic_action,
        action_kind=rule.action_kind,
        target_type=rule.target_type,
        target_role=rule.target_role,
        input_schema=list(rule.input_schema),
        grounding=rule.grounding,
        availability=rule.availability,
        expected_delta=_expected_delta_for_rule(rule),
        evidence=[_evidence("resolver_rule", snapshot)],
    )


def _availability_matches(rule: CapabilityRule, snapshot: StateSnapshot) -> bool:
    if rule.availability.required_page_type != _page_type(snapshot.page_id):
        return False
    indicators = _indicator_values(snapshot)
    for name, value in rule.availability.required_state_indicators.items():
        if indicators.get(name) != value:
            return False
    return True


def _capabilities_for_state(
    snapshot: StateSnapshot,
    observed: OrderedDict[str, Capability],
) -> list[Capability]:
    capabilities: OrderedDict[str, Capability] = OrderedDict(observed)
    for rule in CAPABILITY_RULES.values():
        if _availability_matches(rule, snapshot):
            capabilities.setdefault(rule.capability_id, _capability_from_rule(rule, snapshot))
    return list(capabilities.values())


def build_capability_graph(
    *,
    app: str,
    start_node: str,
    transitions: list[ObservedTransition],
) -> WebCapabilityGraph:
    states_by_id: OrderedDict[str, StateSnapshot] = OrderedDict()
    capabilities_by_state: dict[str, OrderedDict[str, Capability]] = {}
    graph_transitions: list[CapabilityTransition] = []

    for transition in transitions:
        source_id = _state_id(transition.source)
        target_id = _state_id(transition.target)
        states_by_id.setdefault(source_id, transition.source)
        states_by_id.setdefault(target_id, transition.target)
        capability = _capability_for_transition(transition)
        capabilities_by_state.setdefault(source_id, OrderedDict())
        capabilities_by_state[source_id][capability.capability_id] = capability
        graph_transitions.append(
            CapabilityTransition(
                transition_id=f"{source_id}__{capability.capability_id}__{target_id}",
                source_state_id=source_id,
                capability_id=capability.capability_id,
                target_state_id=target_id,
                transition_kind=_transition_kind(transition.source, transition.target),
                observed_delta=_observed_delta(transition.source, transition.target),
                execution_trace=ExecutionTrace(
                    concrete_action_kind=capability.action_kind,
                    concrete_locator=capability.grounding.locator_pattern,
                    concrete_target_sample=capability.target_type,
                    input_values_used={},
                    before_observation_id=source_id,
                    after_observation_id=target_id,
                    success=True,
                    error=None,
                ),
                evidence=[
                    _evidence(
                        "observed_transition",
                        transition.source,
                        text_sample=transition.action.raw_description,
                    )
                ],
            )
        )

    states = [
        SemanticPageState(
            state_id=state_id,
            page_frame=_page_frame(snapshot),
            state_indicators=_state_indicators(snapshot),
            capabilities=_capabilities_for_state(
                snapshot,
                capabilities_by_state.get(state_id, OrderedDict()),
            ),
            evidence=[_evidence("state_signature", snapshot)],
        )
        for state_id, snapshot in states_by_id.items()
    ]
    start_state = _state_id(transitions[0].source) if transitions else start_node
    return WebCapabilityGraph(
        app=app,
        start_state=start_state,
        total_steps_completed=len(transitions),
        states=states,
        transitions=graph_transitions,
    )
