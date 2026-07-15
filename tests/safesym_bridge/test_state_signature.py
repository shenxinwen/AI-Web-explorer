from ai_web_explorer.safesym_bridge.state_signature import (
    coerce_state_value,
    schema_delta,
    slug_identifier,
)


def test_slug_identifier_normalizes_labels_with_fallback():
    assert slug_identifier("Cart Count") == "cart_count"
    assert slug_identifier("  ---  ", fallback="state") == "state"


def test_coerce_state_value_handles_booleans_numbers_and_text():
    assert coerce_state_value("true") is True
    assert coerce_state_value("False") is False
    assert coerce_state_value("-3") == -3
    assert coerce_state_value("Cart contains 1 item.") == "Cart contains 1 item."


def test_schema_delta_records_changed_added_and_removed_values():
    assert schema_delta(
        {"cart_count": 0, "panel_visible": False, "stale": "x"},
        {"cart_count": 1, "panel_visible": False, "new": True},
    ) == {
        "cart_count": {"before": 0, "after": 1},
        "new": {"before": None, "after": True},
        "stale": {"before": "x", "after": None},
    }
