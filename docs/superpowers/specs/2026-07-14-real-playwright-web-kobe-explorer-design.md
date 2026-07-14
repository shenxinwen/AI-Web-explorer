# Real Playwright Web-KOBE Explorer Design

## Purpose

This spec defines the next implementation step for the Web-KOBE/SafeSym path:
connect the current Web-KOBE graph skeleton to a real Playwright-controlled web
page.

The goal is not to build a fully intelligent web agent yet. The goal is to make
the first real browser-grounded exploration loop work:

```text
real Playwright page
  -> observe state
  -> extract DOM interactables
  -> execute one representative action
  -> observe after state
  -> record WebKobeEdge and observed delta
  -> write WebKobeGraph JSON
```

This moves the project from a fake-adapter graph skeleton to a real web
exploration slice.

## Current Context

The project already has:

- `WebKobeGraph`, `WebKobeNode`, and `WebKobeEdge`.
- `WebKobeGraphManager`.
- `DeterministicSemanticAssistor`.
- `browser_actions_from_candidates(...)`.
- `WebKobeExplorer.explore_one_step(...)`.
- `WebKobeGraph -> PDDL` projection.
- debug CLI commands for graph/PDDL generation.

The missing piece is a real adapter that satisfies the current
`WebKobeAdapter` protocol:

```python
class WebKobeAdapter(Protocol):
    app_name: str

    async def observe_state(self) -> StateSnapshot:
        ...

    async def list_interactables(
        self,
        state: StateSnapshot,
    ) -> list[dict[str, Any]]:
        ...

    async def execute(self, action: BrowserAction) -> bool:
        ...
```

## Design Decision

Add a new Playwright-backed adapter:

```text
web_kobe_playwright_adapter.py
```

The adapter should bridge real browser pages into the existing Web-KOBE
explorer. It should stay intentionally simple in v1.

Recommended chain:

```text
Playwright page
  -> WebKobePlaywrightAdapter
      observe_state()
      list_interactables()
      execute(BrowserAction)
  -> WebKobeExplorer
  -> WebKobeGraph
  -> optional WebKobeGraph -> PDDL projection
```

## Why Use a Local Fixture First?

The first real browser test should use a controlled local fixture website,
not an arbitrary public site.

The fixture should contain:

- a product list area.
- one `Add to cart` button.
- a visible cart count or status.
- JavaScript that updates the cart state without navigation.

This creates a stable self-loop transition:

```text
before:
  page_id = fixture_shop
  cart_nonempty = false

action:
  click add_to_cart

after:
  page_id = fixture_shop
  cart_nonempty = true

transition:
  fixture_shop --add_to_cart--> fixture_shop
  delta: cart_nonempty false -> true
```

This is exactly the kind of state-changing object interaction the project
cares about. It also avoids login, network flakiness, anti-bot behavior, and
irreversible real-world actions.

## Components

### WebKobePlaywrightAdapter

Create:

```text
src/ai_web_explorer/safesym_bridge/web_kobe_playwright_adapter.py
```

Responsibilities:

1. Observe current browser state.
2. Extract DOM interactables.
3. Convert DOM candidates into Web-KOBE interactable dictionaries.
4. Execute `BrowserAction` objects through Playwright.

Suggested constructor:

```python
class WebKobePlaywrightAdapter:
    def __init__(
        self,
        page,
        *,
        app_name: str = "web",
        page_id: str | None = None,
        state_extractors: list[StateExtractor] | None = None,
    ):
        ...
```

For v1, `page_id` may default to a normalized title/URL-derived ID. For the
fixture test, pass `page_id="fixture_shop"` explicitly.

### State Extraction

The adapter should build a `StateSnapshot`.

Minimum fields:

```python
StateSnapshot(
    page_id="fixture_shop",
    url=current_url,
    title=await page.title(),
    signature={
        "cart_nonempty": bool,
        "cart_count": int,
    },
)
```

For v1, use simple local state extraction rules:

- If an element with `[data-state="cart-count"]` or `#cart-count` exists, parse
  its integer text.
- Set `cart_nonempty = cart_count > 0`.
- If no known cart count element exists, keep the signature small and include
  no cart facts.

This is not meant to be final generic state understanding. It is the smallest
browser-grounded state extraction needed to prove the loop.

### Interactable Extraction

Reuse the existing DOM observer:

```python
extract_dom_interactables(page)
```

Then reuse:

```python
browser_actions_from_candidates(candidates)
```

Convert each `BrowserAction` into the dictionary shape expected by
`WebKobeExplorer`:

```python
{
    "semantic_id": action.semantic_id,
    "description": action.description,
    "locator": action.locator,
    "action_kind": action.action_kind,
    "explored": False,
}
```

For v1, this means semantic IDs will still be local deterministic names such as
`button_add_to_cart`. Better semantic normalization can come later.

### Action Execution

Support only the basic action kinds first:

```text
click
fill
select
```

Execution behavior:

- `click`: `await page.locator(action.locator).first.click()`
- `fill`: fill the locator with the first available `input_values` value, or
  an empty deterministic fallback such as `"test"`.
- `select`: select the first available `input_values` value. If no value is
  provided, return `False` rather than guessing.

After execution, wait briefly for UI updates:

```python
await page.wait_for_timeout(100)
```

Return:

```python
True
```

when execution succeeds, otherwise:

```python
False
```

The explorer already records failed execution status.

### Browser Runner

Extend `browser_runner.py` with:

```python
async def run_web_kobe_exploration(
    url: str,
    output_path: Path,
    *,
    app_name: str = "web",
    page_id: str | None = None,
    steps: int = 1,
    headless: bool = True,
) -> Path:
    ...
```

For v1:

- open the URL.
- create `WebKobePlaywrightAdapter`.
- create `WebKobeExplorer`.
- call `explore_one_step()` up to `steps` times.
- write the resulting graph JSON to `output_path`.

The first implementation can support `steps=1` well and allow small values
such as `2` or `3` without advanced coverage logic.

### CLI

Add:

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:PORT/index.html \
  --output outputs/web_kobe_explored_graph.json \
  --page-id fixture_shop \
  --steps 1
```

Options:

- `--url`: required.
- `--output`: default `outputs/web_kobe_explored_graph.json`.
- `--page-id`: optional override for stable node identity.
- `--app-name`: default `web`.
- `--steps`: default `1`.
- `--headed`: show browser window.

## Testing Strategy

### Unit Tests

Add tests for `WebKobePlaywrightAdapter` using a Playwright page loaded with
fixture HTML:

1. `observe_state()` reads URL/title and cart count.
2. `list_interactables()` returns an add-to-cart action candidate.
3. `execute(click)` changes cart state.

### Integration Test

Add a browser-level test:

```text
fixture page
  -> WebKobePlaywrightAdapter
  -> WebKobeExplorer.explore_one_step()
  -> WebKobeGraph with one self-loop edge
  -> observed_delta cart_nonempty false -> true
```

Use the existing test style for Playwright smoke tests:

- skip when browser dependencies are unavailable.
- keep fixture deterministic.
- avoid external network.

### CLI Test

Add a CLI test that monkeypatches the runner:

```text
web-kobe-explore --url ... --output ...
```

The test should verify:

- command parses.
- runner receives URL/output/page_id/steps/headless correctly.
- output path is reported.

### Regression

Run:

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge -v
```

## Non-Goals for v1

Do not implement these yet:

- LLM/VLM page understanding.
- automatic repeated-group `ActionTarget` inference.
- generic state matching with embeddings.
- graph audit.
- coverage checkpoint/replay.
- multi-step intelligent exploration policy.
- parameterized PDDL from the explored graph.
- unsafe real-world action handling.

This phase is about getting the real browser loop alive.

## Success Criteria

The phase is complete when:

1. A real Playwright page can be observed through `WebKobePlaywrightAdapter`.
2. DOM interactables become Web-KOBE action candidates.
3. `WebKobeExplorer.explore_one_step()` can execute a real click.
4. The graph records a real self-loop edge and semantic delta.
5. CLI can run `web-kobe-explore` against a fixture/local URL.
6. Existing SafeSym bridge tests still pass.

## Future Follow-Up

After this works, the next useful step is to add semantic intelligence:

```text
local browser extraction
  -> LLM/VLM semantic proposal
  -> browser execution verification
  -> WebKobeGraph
  -> PDDL/SafeSym
```

That later phase should make the system infer page types, ActionTargets, and
Capabilities more like UI-KOBE, while keeping browser execution as the source
of verified effects.
