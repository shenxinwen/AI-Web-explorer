from __future__ import annotations

from collections.abc import Awaitable, Callable

from ai_web_explorer.safesym_bridge.action_semantics import semantic_id_for
from ai_web_explorer.safesym_bridge.effect_inferer import (
    infer_effects,
    preconditions_for,
)
from ai_web_explorer.safesym_bridge.models import (
    ObservedAction,
    ObservedTransition,
    StateSnapshot,
)
from ai_web_explorer.safesym_bridge.state_observer import observe_saucedemo_state

Observer = Callable[[object], Awaitable[StateSnapshot]]
ActionCoroutineFactory = Callable[[], Awaitable[None]]


async def record_transition(
    page,
    raw_description: str,
    action_coro: ActionCoroutineFactory,
    observer: Observer = observe_saucedemo_state,
) -> ObservedTransition:
    before = await observer(page)
    action_id = semantic_id_for(raw_description)
    await action_coro()
    after = await observer(page)

    return ObservedTransition(
        source=before,
        target=after,
        action=ObservedAction(
            raw_description=raw_description,
            semantic_id=action_id,
            playwright_calls=[],
        ),
        # 根据动作检索预设的前提条件，并推断状态变化的效果
        preconditions=preconditions_for(action_id),
        effects=infer_effects(before, after),
    )
