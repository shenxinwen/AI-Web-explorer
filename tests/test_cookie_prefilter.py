from ai_web_explorer.cookies import _might_contain_cookie_banner


def test_cookie_prefilter_ignores_saucedemo_login_page_text():
    html_part = """
    <main>
      <h1>Swag Labs</h1>
      <input id="user-name" />
      <input id="password" />
      <input id="login-button" value="Login" />
      <p>Accepted usernames are: standard_user locked_out_user</p>
      <p>Password for all users: secret_sauce</p>
    </main>
    """

    assert not _might_contain_cookie_banner(html_part)


def test_cookie_prefilter_detects_cookie_consent_copy():
    html_part = """
    <section role="dialog">
      <p>We use cookies to improve your experience.</p>
      <button>Accept cookies</button>
    </section>
    """

    assert _might_contain_cookie_banner(html_part)
