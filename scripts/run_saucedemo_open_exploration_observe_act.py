from __future__ import annotations

import sys
from dataclasses import replace
from types import MethodType

from ai_web_explorer.grounded_web.stagehand_actions import StagehandObservedAction
from ai_web_explorer.grounded_web.stagehand_sdk_provider import StagehandSdkProvider
from ai_web_explorer.safesym_bridge import browser_runner
from ai_web_explorer.safesym_bridge.cli import main


_original_observe_action = StagehandSdkProvider.observe_action
_original_create_provider = browser_runner.create_async_stagehand_provider_from_env


async def _observe_action_with_saucedemo_overrides(
    self: StagehandSdkProvider,
    instruction: str,
):
    normalized_instruction = instruction.casefold()
    if "shopping cart" in normalized_instruction:
        return [
            StagehandObservedAction(
                description="SauceDemo shopping cart link",
                selector='[data-test="shopping-cart-link"]',
                method="click",
            )
        ]
    actions = await _original_observe_action(self, instruction)
    if "password" in normalized_instruction:
        return [
            replace(action, arguments=("secret_sauce",))
            if action.method == "fill"
            else action
            for action in actions
        ]
    if "username" not in normalized_instruction:
        return actions
    return [
        replace(action, arguments=("standard_user",))
        if action.method == "fill"
        else action
        for action in actions
    ]


async def _create_saucedemo_provider(**kwargs):
    provider = await _original_create_provider(**kwargs)
    provider.observe_action = MethodType(
        _observe_action_with_saucedemo_overrides,
        provider,
    )
    return provider


if __name__ == "__main__":
    browser_runner.create_async_stagehand_provider_from_env = (
        _create_saucedemo_provider
    )
    raise SystemExit(main(sys.argv[1:]))
