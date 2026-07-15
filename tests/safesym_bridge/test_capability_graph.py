from ai_web_explorer.grounded_web.capability_graph import (
    AvailabilityCondition,
    Capability,
    CapabilityTransition,
    Evidence,
    ExecutionTrace,
    GroundingPattern,
    ObservedDelta,
    PageFrame,
    SemanticPageState,
    StateChangeHint,
    StateIndicator,
    WebCapabilityGraph,
)


def test_web_capability_graph_to_dict_uses_expected_shape():
    evidence = Evidence(
        source="dom",
        selector='button[data-test="checkout"]',
        text_sample="Checkout",
        url="https://www.saucedemo.com/cart.html",
        confidence=1.0,
    )
    capability = Capability(
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
        expected_delta=[
            StateChangeHint(field="page_type", before="cart", after="checkout_info")
        ],
        evidence=[evidence],
    )
    graph = WebCapabilityGraph(
        app="saucedemo",
        start_state="cart_nonempty",
        total_steps_completed=1,
        states=[
            SemanticPageState(
                state_id="cart_nonempty",
                page_frame=PageFrame(
                    page_id="saucedemo:cart",
                    page_type="cart",
                    url="https://www.saucedemo.com/cart.html",
                    url_pattern="/cart.html",
                    title="Swag Labs",
                    heading="Your Cart",
                    signature_hints={"cart_nonempty": True},
                    evidence=[evidence],
                ),
                state_indicators=[
                    StateIndicator(
                        name="cart_nonempty",
                        value=True,
                        role="capability_precondition",
                        evidence=[evidence],
                    )
                ],
                capabilities=[capability],
                evidence=[evidence],
            )
        ],
        transitions=[
            CapabilityTransition(
                transition_id="cart_nonempty__checkout_start__checkout_info",
                source_state_id="cart_nonempty",
                capability_id="checkout_start",
                target_state_id="checkout_info",
                transition_kind="navigation",
                observed_delta=[
                    ObservedDelta(
                        field="page_type",
                        before="cart",
                        after="checkout_info",
                        delta_type="page_frame_change",
                        confidence=1.0,
                        evidence=[evidence],
                    )
                ],
                execution_trace=ExecutionTrace(
                    concrete_action_kind="click",
                    concrete_locator='button[data-test="checkout"]',
                    concrete_target_sample=None,
                    input_values_used={},
                    before_observation_id="cart_nonempty",
                    after_observation_id="checkout_info",
                    success=True,
                    error=None,
                ),
                evidence=[evidence],
            )
        ],
    )

    assert graph.to_dict() == {
        "meta": {
            "schema_version": "web-capability-graph-v1",
            "app": "saucedemo",
            "start_state": "cart_nonempty",
            "total_steps_completed": 1,
        },
        "states": [
            {
                "state_id": "cart_nonempty",
                "page_frame": {
                    "page_id": "saucedemo:cart",
                    "page_type": "cart",
                    "url": "https://www.saucedemo.com/cart.html",
                    "url_pattern": "/cart.html",
                    "title": "Swag Labs",
                    "heading": "Your Cart",
                    "signature_hints": {"cart_nonempty": True},
                    "evidence": [
                        {
                            "source": "dom",
                            "selector": 'button[data-test="checkout"]',
                            "text_sample": "Checkout",
                            "url": "https://www.saucedemo.com/cart.html",
                            "confidence": 1.0,
                        }
                    ],
                },
                "state_indicators": [
                    {
                        "name": "cart_nonempty",
                        "value": True,
                        "role": "capability_precondition",
                        "evidence": [
                            {
                                "source": "dom",
                                "selector": 'button[data-test="checkout"]',
                                "text_sample": "Checkout",
                                "url": "https://www.saucedemo.com/cart.html",
                                "confidence": 1.0,
                            }
                        ],
                    }
                ],
                "capabilities": [
                    {
                        "capability_id": "checkout_start",
                        "semantic_action": "checkout_start",
                        "action_kind": "click",
                        "target_type": "cart",
                        "target_role": "current_cart",
                        "input_schema": [],
                        "grounding": {
                            "locator_strategy": "css",
                            "locator_pattern": 'button[data-test="checkout"]',
                            "target_selection_policy": "single",
                            "field_bindings": {},
                        },
                        "availability": {
                            "required_page_type": "cart",
                            "required_state_indicators": {"cart_nonempty": True},
                            "required_target_presence": None,
                        },
                        "expected_delta": [
                            {
                                "field": "page_type",
                                "before": "cart",
                                "after": "checkout_info",
                            }
                        ],
                        "evidence": [
                            {
                                "source": "dom",
                                "selector": 'button[data-test="checkout"]',
                                "text_sample": "Checkout",
                                "url": "https://www.saucedemo.com/cart.html",
                                "confidence": 1.0,
                            }
                        ],
                    }
                ],
                "evidence": [
                    {
                        "source": "dom",
                        "selector": 'button[data-test="checkout"]',
                        "text_sample": "Checkout",
                        "url": "https://www.saucedemo.com/cart.html",
                        "confidence": 1.0,
                    }
                ],
            }
        ],
        "transitions": [
            {
                "transition_id": "cart_nonempty__checkout_start__checkout_info",
                "source_state_id": "cart_nonempty",
                "capability_id": "checkout_start",
                "target_state_id": "checkout_info",
                "transition_kind": "navigation",
                "observed_delta": [
                    {
                        "field": "page_type",
                        "before": "cart",
                        "after": "checkout_info",
                        "delta_type": "page_frame_change",
                        "confidence": 1.0,
                        "evidence": [
                            {
                                "source": "dom",
                                "selector": 'button[data-test="checkout"]',
                                "text_sample": "Checkout",
                                "url": "https://www.saucedemo.com/cart.html",
                                "confidence": 1.0,
                            }
                        ],
                    }
                ],
                "execution_trace": {
                    "concrete_action_kind": "click",
                    "concrete_locator": 'button[data-test="checkout"]',
                    "concrete_target_sample": None,
                    "input_values_used": {},
                    "before_observation_id": "cart_nonempty",
                    "after_observation_id": "checkout_info",
                    "success": True,
                    "error": None,
                },
                "evidence": [
                    {
                        "source": "dom",
                        "selector": 'button[data-test="checkout"]',
                        "text_sample": "Checkout",
                        "url": "https://www.saucedemo.com/cart.html",
                        "confidence": 1.0,
                    }
                ],
            }
        ],
    }
