from ai_web_explorer.grounded_web.models import StateSnapshot


def test_state_snapshot_stores_signature():
    snapshot = StateSnapshot(
        page_id="inventory",
        url="https://www.saucedemo.com/inventory.html",
        title="Swag Labs",
        signature={"cart_count": 1, "is_logged_in": True},
    )

    assert snapshot.page_id == "inventory"
    assert snapshot.signature["cart_count"] == 1
    assert snapshot.signature["is_logged_in"] is True
