from __future__ import annotations

from ai_web_explorer.safesym_bridge.dom_observer import (
    DomInteractableCandidate,
)
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.semantic_resolver import (
    ResolutionBatch,
    SemanticMatch,
)


Rule = tuple[str, dict[str, str]]

RULES: dict[str, list[Rule]] = {
    "login": [
        ("login_submit", {"id_": "login-button", "data_test": "login-button"}),
    ],
    "inventory": [
        (
            "product_add_to_cart",
            {"data_test": "add-to-cart-sauce-labs-backpack"},
        ),
        (
            "cart_open",
            {
                "data_test": "shopping-cart-link",
                "class_name": "shopping_cart_link",
            },
        ),
    ],
    "cart": [
        ("cart_checkout_start", {"id_": "checkout", "data_test": "checkout"}),
    ],
    "checkout_info": [
        (
            "checkout_info_submit",
            {"id_": "continue", "data_test": "continue"},
        ),
    ],
    "checkout_overview": [
        (
            "order_place_confirm",
            {"id_": "finish", "data_test": "finish"},
        ),
    ],
}


def _matches(
    candidate: DomInteractableCandidate,
    *,
    id_: str = "",
    data_test: str = "",
    class_name: str = "",
) -> bool:
    metadata = candidate.metadata
    if id_ and (metadata.get("id") == id_ or candidate.locator == f"#{id_}"):
        return True
    if data_test and (
        metadata.get("data-test") == data_test
        or candidate.locator == f'[data-test="{data_test}"]'
    ):
        return True
    return bool(
        class_name and class_name in metadata.get("class", "").split()
    )


class SauceDemoRuleResolver:
    async def resolve(
        self,
        state: StateSnapshot,
        candidates: list[DomInteractableCandidate],
    ) -> ResolutionBatch:
        matches: list[SemanticMatch] = []
        unmatched: list[str] = []
        rules = RULES.get(state.page_id, [])

        for candidate in candidates:
            semantic_id = next(
                (
                    semantic_id
                    for semantic_id, criteria in rules
                    if _matches(candidate, **criteria)
                ),
                None,
            )
            if semantic_id is None:
                unmatched.append(candidate.id)
                continue
            matches.append(
                SemanticMatch(
                    candidate_id=candidate.id,
                    semantic_id=semantic_id,
                    confidence=1.0,
                    resolver="saucedemo_rule",
                )
            )

        return ResolutionBatch(
            matches=matches,
            unmatched_candidate_ids=unmatched,
        )
