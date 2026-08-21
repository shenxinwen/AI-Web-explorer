from __future__ import annotations

import sys
from dataclasses import replace

from ai_web_explorer.grounded_web.stagehand_sdk_provider import StagehandSdkProvider
from ai_web_explorer.safesym_bridge.cli import main


_original_observe_action = StagehandSdkProvider.observe_action


async def _observe_action_with_saucedemo_username(
    self: StagehandSdkProvider,
    instruction: str,
):
    actions = await _original_observe_action(self, instruction)
    if "business action: enter_username" not in instruction:
        return actions
    return [
        replace(action, arguments=("standard_user",))
        if action.method == "fill" and not any(action.arguments)
        else action
        for action in actions
    ]


if __name__ == "__main__":
    StagehandSdkProvider.observe_action = _observe_action_with_saucedemo_username
    raise SystemExit(main(sys.argv[1:]))
