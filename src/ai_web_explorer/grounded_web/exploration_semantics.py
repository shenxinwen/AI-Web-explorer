"""Safety checks for the controlled test-site completion boundary."""

from __future__ import annotations

from urllib.parse import urlsplit


def validate_final_order_authorization(*, start_url: str, allowed: bool) -> bool:
    """Allow final confirmation only on the explicit controlled test URL."""

    if not allowed:
        return False
    parsed = urlsplit(str(start_url).strip())
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError(
            "final order authorization requires the controlled test URL"
        ) from error
    if (
        parsed.scheme.lower() != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() != "practiceautomatedtesting.com"
        or port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path != "/shopping"
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("final order authorization requires the controlled test URL")
    return True


__all__ = ["validate_final_order_authorization"]
