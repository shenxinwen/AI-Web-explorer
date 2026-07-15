from ai_web_explorer import _build_start_url


def test_build_start_url_defaults_to_https_for_bare_domain():
    assert _build_start_url("www.saucedemo.com") == "https://www.saucedemo.com"


def test_build_start_url_preserves_explicit_scheme():
    assert _build_start_url("http://localhost:8000") == "http://localhost:8000"
