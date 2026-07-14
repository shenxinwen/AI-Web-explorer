import dataclasses
import json
import logging
import time
from urllib.parse import urlparse

import openai
import playwright.sync_api

from . import webstate
from . import describer
from . import executor
from . import config
from . import cookies
from . import html
from . import config
from ai_web_explorer.safesym_bridge.web_kobe_collector import NoOpWebKobeCollector
from ai_web_explorer.safesym_bridge.web_kobe_observer import observe_web_kobe_page
# from.表示引用同一目录下的包

@dataclasses.dataclass
class LoopConfig:
    iterations: int | None = dataclasses.field(default=None)
    confirm_titles: bool = dataclasses.field(default=False)
    store_titles: bool = dataclasses.field(default=False)
    username: str | None = dataclasses.field(default=None)
    password: str | None = dataclasses.field(default=None)
    additional_info: str | None = dataclasses.field(default=None)
    collector: object | None = dataclasses.field(default=None)


WebStateBacktrack = tuple[
    webstate.WebState, int | None, webstate.StateTransition | None
]


class ExploreLoop:

    def __init__(
        self,
        domain: str,
        url: str,
        openai_client: openai.OpenAI,
        config: LoopConfig,
    ):
        self._domain = domain
        self._url = url
        self._openai_client = openai_client
        self._config = config

        self._webstates: list[webstate.WebState] = []
        self._webstate_current: webstate.WebState | None = None
        self._action_current: webstate.Action | None = None
        self._collector = config.collector or NoOpWebKobeCollector()
        self._web_kobe_previous_observation = None
        self._pw, self._page = self._init_browser(self._url)
        # 初始化描述器和执行器
        self._describer = describer.Describer(
            self._page, openai_client, config.additional_info
        )
        self._executor = executor.Executor(
            self._page,
            openai_client,
            config.username,
            config.password,
            config.additional_info,
        )
    
    # 主循环
    def start(self):
        i = 0

        while self._config.iterations is None or i < self._config.iterations:
            logging.info(f"Iteration {i}")
            self._explore()
            i += 1

        self._explore(True)

    def set_webstates(self, webstates: list[webstate.WebState]):
        self._webstates = webstates

    def _explore(self, finish=False):
        logging.info(f"Current URL: {self._page.url}")
        ws = self._get_webstate()
        collector = getattr(
            self,
            "_collector",
            getattr(self._config, "collector", None) or NoOpWebKobeCollector(),
        )
        observation = observe_web_kobe_page(
            self._page,
            web_state_id=str(ws.ws_id),
            llm_title=ws.title,
        )
        collector.on_state_observed(
            page=self._page,
            web_state=ws,
            observation=observation,
        )

        if (
            self._webstate_current
            and self._action_current
            and self._action_current.status == "success"
        ):
            previous_observation = getattr(
                self,
                "_web_kobe_previous_observation",
                None,
            )
            if previous_observation is not None:
                collector.on_transition(
                    source_state=self._webstate_current,
                    action=self._action_current,
                    target_state=ws,
                    before_observation=previous_observation,
                    after_observation=observation,
                )
            self._webstate_current.transitions.append(
                webstate.StateTransition(action=self._action_current, state_new=ws)
            )

        if finish:
            return

        self._webstate_current = ws
        self._action_current = ws.random_action

        if not self._action_current:
            logging.info("No more actions to take on this page")
            self._action_current = self._search_next_available_action()
            if not self._action_current:
                logging.info("No more actions to take in the domain")
                return

        logging.info(f"Randomly selected action: {self._action_current.description}")
        collector.on_action_selected(
            source_state=ws,
            action=self._action_current,
        )
        action_result, tool_calls = self._executor.execute(self._action_current)
        self._action_current.function_calls = tool_calls

        url_parsed = urlparse(self._page.url)

        if self._domain not in url_parsed.netloc:
            self._back_to_domain()
            self._action_current.status = "failure"
        else:
            self._action_current.status = "success" if action_result else "failure"

        collector.on_action_executed(
            action=self._action_current,
            success=self._action_current.status == "success",
            tool_calls=tool_calls,
            error=None
            if self._action_current.status == "success"
            else "execution_failed",
        )
        self._web_kobe_previous_observation = observation
        logging.info(f"Action result: {self._action_current.status}")

    def _get_webstate(self) -> webstate.WebState:
        self._ensure_page_loaded()
        page_title = self._describer.get_title(
            self._config.confirm_titles, self._config.store_titles
        )
        embedding = self._describer.get_title_embedding(page_title)
        
        # 如果启用了标题存储或确认，则使用标题嵌入来查找相似状态，否则直接比较标题文本。
        # 这是因为启用存储或确认可能会导致标题文本的微小变化，而嵌入可以更好地捕捉语义上的相似性。
        if embedding:
            for ws in self._webstates:
                distance = ws.cosine_distance(embedding)
                if distance > config.TITLE_SIMILARITY_THRESHOLD:
                    logging.info(f"Found similar state: {ws.title}")
                    if self._url not in ws.urls:
                        ws.urls.append(self._url)
                    return ws
        else:
            for ws in self._webstates:
                if ws.title == page_title:
                    logging.info(f"Found similar state: {ws.title}")
                    if self._url not in ws.urls:
                        ws.urls.append(self._url)
                    return ws

        logging.info(f"Creating new state: {page_title}")
        ws = webstate.WebState(
            title=page_title,
            title_embedding=embedding,
            urls=[self._page.url],
            description=self._describer.get_description(),
            actions=[],
            transitions=[],
        )

        ws.actions = self._describer.get_actions(ws.title, ws.description)
        self._webstates.append(ws)
        return ws

    def print_graph(self):
        print("digraph G {")

        for ws in self._webstates:
            ws_id = str(ws.ws_id).replace("-", "")
            print(f'ws_{ws_id} [label="{ws.title}"]')

        for ws in self._webstates:
            ws_id = str(ws.ws_id).replace("-", "")
            for transition in ws.transitions:
                ws_new = transition.state_new
                ws_new_id = str(ws_new.ws_id).replace("-", "")
                print(
                    f'ws_{ws_id} -> ws_{ws_new_id} [label="{transition.action.description}"]'
                )

        print("}")

    def print_json(self, simple=True):
        outputs = [ws.dict(simple) for ws in self._webstates]
        print(json.dumps(outputs, indent=4))

    def stop(self):
        self._pw.stop()

    def _init_browser(
        self, url: str
    ) -> tuple[playwright.sync_api.Playwright, playwright.sync_api.Page]:
        pw = playwright.sync_api.sync_playwright().start()
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.add_init_script(html.JS_FUNCTIONS) # 注入js代码
        page.set_viewport_size(
            {"width": config.BROWSER_SIZE[0], "height": config.BROWSER_SIZE[1]}
        )
        page.goto(url, wait_until="domcontentloaded")
        time.sleep(5)
        cookies.accept_cookies_if_present(self._openai_client, page)
        return pw, page

    def _ensure_page_loaded(self):
        for _ in range(config.ENSURE_LOADED_MAX_TRIES):
            if not self._describer.is_loading():
                break
            logging.info("Page is still loading, waiting...")
            time.sleep(config.ENSURE_LOADED_SLEEP_TIME)

    def _back_to_domain(self):
        logging.info("Navigated away from domain, going back to domain")
        url_parsed = urlparse(self._page.url)
        max_attempts = 2
        attempts = 0
        while self._domain not in url_parsed.netloc and attempts < max_attempts:
            self._page.go_back()
            attempts += 1
        self._page.goto(f"https://{self._domain}")

    def _search_next_available_action(self) -> webstate.Action | None:
        states_visiting: list[WebStateBacktrack] = [(self._webstates[0], None, None)]
        states_visited = []

        while len(states_visiting) > 0:
            ws = states_visiting.pop()
            states_visited.append(ws)

            for action in ws[0].actions:
                if action.status == "none":
                    logging.info(
                        f"Found next available action: {action.description} in state: {ws[0].title}"
                    )
                    transitions = []
                    back: WebStateBacktrack = ws
                    while type(back[1]) == int:
                        transitions.append(back[2])
                        back = states_visited[back[1]]  # type: ignore
                    transitions.reverse()
                    logging.info(f"Transitions to get to state: {ws[0].title}")
                    for transition in transitions:
                        logging.info(f"{transition.action.description}")
                    self._perform_transitions(transitions)
                    return action

            for transition in ws[0].transitions:
                if transition.state_new not in [state[0] for state in states_visited]:
                    states_visiting.append(
                        (transition.state_new, len(states_visited) - 1, transition)
                    )

        return None

    def _perform_transitions(self, transitions: list[webstate.StateTransition]):
        self.stop()
        self._pw, self._page = self._init_browser(self._url)
        self._executor = executor.Executor(
            self._page,
            self._openai_client,
            self._config.username,
            self._config.password,
            self._config.additional_info,
        )
        self._describer = describer.Describer(
            self._page, self._openai_client, self._config.additional_info
        )
        self._page.goto(self._url)
        for transition in transitions:
            self._executor.replicate_tool_calls(transition.action.function_calls)
            self._webstate_current = transition.state_new
