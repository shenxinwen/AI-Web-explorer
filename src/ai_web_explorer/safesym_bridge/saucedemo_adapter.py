from __future__ import annotations

from ai_web_explorer.safesym_bridge.graph_explorer import ExplorationAction
from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.state_observer import observe_saucedemo_state


class SauceDemoAdapter:
    app_name = "saucedemo"
    start_node = "login"
    start_url = "https://www.saucedemo.com/"

    async def observe_state(self, page) -> StateSnapshot:
        return await observe_saucedemo_state(page)

    async def list_actions(
        self,
        page,
        state: StateSnapshot,
    ) -> list[ExplorationAction]:
        actions_by_page = {
            "login": [
                ExplorationAction(
                    raw_description="Click the Login button",
                    semantic_id="login_submit",
                    page_id="login",
                    execution_kind="fill_then_click",
                    selector="#login-button",
                    values={
                        "#user-name": "standard_user",
                        "#password": "secret_sauce",
                    },
                    position="login form",
                )
            ],
            "inventory": [
                ExplorationAction(
                    raw_description="Click Add to cart",
                    semantic_id="product_add_to_cart",
                    page_id="inventory",
                    execution_kind="click",
                    selector='[data-test="add-to-cart-sauce-labs-backpack"]',
                    position="product list",
                ),
                ExplorationAction(
                    raw_description="Click the shopping cart link",
                    semantic_id="cart_open",
                    page_id="inventory",
                    execution_kind="click",
                    selector=".shopping_cart_link",
                    position="top right",
                ),
            ],
            "cart": [
                ExplorationAction(
                    raw_description="Click Checkout",
                    semantic_id="cart_checkout_start",
                    page_id="cart",
                    execution_kind="click",
                    selector="#checkout",
                    position="cart actions",
                )
            ],
            "checkout_info": [
                ExplorationAction(
                    raw_description="Click Continue on checkout information",
                    semantic_id="checkout_info_submit",
                    page_id="checkout_info",
                    execution_kind="fill_then_click",
                    selector="#continue",
                    values={
                        "#first-name": "Safe",
                        "#last-name": "Sym",
                        "#postal-code": "12345",
                    },
                    position="checkout form",
                )
            ],
            "checkout_overview": [
                ExplorationAction(
                    raw_description="Click Finish",
                    semantic_id="order_place_confirm",
                    page_id="checkout_overview",
                    execution_kind="click",
                    selector="#finish",
                    position="checkout summary",
                )
            ],
        }
        return actions_by_page.get(state.page_id, [])

    async def execute_action(self, page, action: ExplorationAction) -> None:
        for selector, value in action.values.items():
            await page.fill(selector, value)
        if action.selector is None:
            raise ValueError(f"Action has no selector: {action.semantic_id}")
        await page.click(action.selector)

    def is_goal_state(self, state: StateSnapshot) -> bool:
        return state.page_id == "checkout_complete" and bool(
            state.signature.get("$.order_created")
        )
