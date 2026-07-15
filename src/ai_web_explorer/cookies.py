import openai
import playwright.sync_api
import json
import logging
import re

from . import promptrepo
from . import html


COOKIE_BANNER_HINTS = (
    "cookie",
    "cookies",
    "cookie consent",
    "consent",
    "gdpr",
    "privacy preferences",
    "privacy settings",
    "tracking preferences",
)


def _might_contain_cookie_banner(html_part: str) -> bool:
    text = re.sub(r"\s+", " ", html_part).lower()
    return any(hint in text for hint in COOKIE_BANNER_HINTS)


def accept_cookies_if_present(client: openai.Client, page: playwright.sync_api.Page):
    prompt_search_cookies = promptrepo.get_prompt("search_cookies")
    html_parts = list(html.iterate_html(page))
    if not any(_might_contain_cookie_banner(html_part) for html_part in html_parts):
        logging.info("No cookie banner hints found")
        return

    has_cookies = False
    for html_part in html_parts:
        response = prompt_search_cookies.execute_prompt(
            client, image_bytes=page.screenshot(), html_part=html_part
        )
        if response.message.content and "yes" in response.message.content.lower():
            has_cookies = True
            break

    if not has_cookies:
        logging.info("No cookie banner found")
        return

    prompt_accept_selector = promptrepo.get_prompt("accept_cookies_selector")
    response = prompt_accept_selector.execute_prompt(
        client, image_bytes=page.screenshot(), html_part=html_part
    )

    if not response.message.tool_calls or len(response.message.tool_calls) == 0:
        logging.error("No tool calls in response when accepting cookies")
        return

    args_str = response.message.tool_calls[0].function.arguments
    args = json.loads(args_str)
    selector = args["selector"]

    logging.info(f"Accepting cookies with selector `{selector}`")
    page.click(selector)
