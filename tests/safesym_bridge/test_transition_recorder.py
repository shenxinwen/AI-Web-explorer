import pytest

from ai_web_explorer.safesym_bridge.models import StateSnapshot
from ai_web_explorer.safesym_bridge.transition_recorder import record_transition


@pytest.fixture
def anyio_backend():
    return "asyncio"


def snapshot(page_id, signature):
    return StateSnapshot(
        page_id=page_id,
        url=f"https://www.saucedemo.com/{page_id}",
        title="Swag Labs",
        signature=signature,
    )


@pytest.mark.anyio
async def test_record_transition_observes_before_and_after():
    calls = []
    snapshots = [
        snapshot("inventory", {"$.cart_count": 0, "$.is_logged_in": True}),
        snapshot("inventory", {"$.cart_count": 1, "$.is_logged_in": True}),
    ]

    async def observer(page):
        return snapshots.pop(0)

    async def action():
        calls.append("clicked")

    transition = await record_transition(
        page=object(),
        raw_description="Click Add to cart",
        action_coro=action,
        observer=observer,
    )

    assert calls == ["clicked"]
    assert transition.action.semantic_id == "product_add_to_cart"
    assert transition.source.page_id == "inventory"
    assert transition.target.page_id == "inventory"
    assert transition.preconditions == [
        {"path": "$.is_logged_in", "cond": "eq", "value": True}
    ]
    assert transition.effects == [{"path": "$.cart_count", "op": "set", "value": 1}]
