# 真实 Playwright Web-KOBE Explorer 设计

## 目标

这份设计定义 Web-KOBE/SafeSym 路线的下一步：把当前 Web-KOBE 图骨架接到真实 Playwright 网页上。

这一阶段不追求完整智能网页 agent，而是先跑通第一条真实浏览器探索链路：

```text
真实 Playwright 页面
  -> 观察状态
  -> 抽取 DOM 可交互元素
  -> 执行一个代表性动作
  -> 再次观察状态
  -> 记录 WebKobeEdge 和 observed delta
  -> 写出 WebKobeGraph JSON
```

这会把项目从 fake adapter 骨架推进到真实网页探索切片。

## 当前上下文

项目已经有：

- `WebKobeGraph`、`WebKobeNode`、`WebKobeEdge`
- `WebKobeGraphManager`
- `DeterministicSemanticAssistor`
- `browser_actions_from_candidates(...)`
- `WebKobeExplorer.explore_one_step(...)`
- `WebKobeGraph -> PDDL` 投影
- graph/PDDL debug CLI

现在缺的是一个真实 adapter，满足现有 `WebKobeAdapter` 协议：

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

## 设计决策

新增 Playwright-backed adapter：

```text
web_kobe_playwright_adapter.py
```

它负责把真实浏览器页面转换成当前 `WebKobeExplorer` 能消费的接口。v1 保持简单、可测试。

推荐链路：

```text
Playwright page
  -> WebKobePlaywrightAdapter
      observe_state()
      list_interactables()
      execute(BrowserAction)
  -> WebKobeExplorer
  -> WebKobeGraph
  -> 可选 WebKobeGraph -> PDDL 投影
```

## 为什么先用本地 fixture？

第一版真实浏览器测试应该用受控本地 fixture 页面，而不是任意公网网站。

fixture 页面包含：

- 商品列表区域
- 一个 `Add to cart` 按钮
- 可见购物车数量或状态
- 点击后用 JavaScript 更新购物车状态，但不跳转页面

这样可以稳定产生 self-loop transition：

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

这正是项目关心的“会引发状态变化的对象能力”。同时它避免了登录、外网波动、反爬和真实不可逆动作。

## 组件设计

### WebKobePlaywrightAdapter

新增：

```text
src/ai_web_explorer/safesym_bridge/web_kobe_playwright_adapter.py
```

职责：

1. 观察当前浏览器状态。
2. 抽取 DOM 可交互元素。
3. 把 DOM candidates 转成 Web-KOBE interactable dict。
4. 通过 Playwright 执行 `BrowserAction`。

建议构造函数：

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

v1 中，`page_id` 可以默认从 title/URL 归一化得到。fixture 测试里显式传入 `page_id="fixture_shop"`。

### 状态抽取

adapter 需要生成 `StateSnapshot`。

最小字段：

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

v1 使用简单本地规则：

- 如果存在 `[data-state="cart-count"]` 或 `#cart-count`，解析其中整数。
- 设置 `cart_nonempty = cart_count > 0`。
- 如果没有已知 cart count 元素，则保持 signature 很小，不加入 cart facts。

这不是最终通用状态理解，只是为了证明真实浏览器链路所需的最小状态抽取。

### 可交互元素抽取

复用现有 DOM observer：

```python
extract_dom_interactables(page)
```

再复用：

```python
browser_actions_from_candidates(candidates)
```

把每个 `BrowserAction` 转成 `WebKobeExplorer` 当前期望的 dict：

```python
{
    "semantic_id": action.semantic_id,
    "description": action.description,
    "locator": action.locator,
    "action_kind": action.action_kind,
    "explored": False,
}
```

v1 中 semantic id 仍然是本地 deterministic 名称，例如 `button_add_to_cart`。更好的语义归一化后续再做。

### 动作执行

第一版只支持基础 action kind：

```text
click
fill
select
```

执行行为：

- `click`: `await page.locator(action.locator).first.click()`
- `fill`: 用 `input_values` 中第一个值填入；没有输入值时使用确定性 fallback，例如 `"test"`。
- `select`: 选择 `input_values` 中第一个值；没有值时返回 `False`，不猜。

执行后短暂等待 UI 更新：

```python
await page.wait_for_timeout(100)
```

成功返回：

```python
True
```

失败返回：

```python
False
```

explorer 已经会记录失败执行状态。

### Browser Runner

扩展 `browser_runner.py`：

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

v1 行为：

- 打开 URL。
- 创建 `WebKobePlaywrightAdapter`。
- 创建 `WebKobeExplorer`。
- 调用 `explore_one_step()`，最多执行 `steps` 次。
- 把 graph JSON 写到 `output_path`。

第一版重点保证 `steps=1` 跑稳；允许 `2` 或 `3` 这种小步数，但不做复杂覆盖率策略。

### CLI

新增：

```bash
python -m ai_web_explorer.safesym_bridge.cli web-kobe-explore \
  --url http://127.0.0.1:PORT/index.html \
  --output outputs/web_kobe_explored_graph.json \
  --page-id fixture_shop \
  --steps 1
```

参数：

- `--url`：必填。
- `--output`：默认 `outputs/web_kobe_explored_graph.json`。
- `--page-id`：可选，用于稳定 node identity。
- `--app-name`：默认 `web`。
- `--steps`：默认 `1`。
- `--headed`：显示浏览器窗口。

## 测试策略

### 单元测试

用 Playwright page 加载 fixture HTML，测试 `WebKobePlaywrightAdapter`：

1. `observe_state()` 能读取 URL/title/cart count。
2. `list_interactables()` 能返回 add-to-cart action candidate。
3. `execute(click)` 后 cart state 变化。

### 集成测试

新增浏览器级测试：

```text
fixture page
  -> WebKobePlaywrightAdapter
  -> WebKobeExplorer.explore_one_step()
  -> WebKobeGraph with one self-loop edge
  -> observed_delta cart_nonempty false -> true
```

沿用现有 Playwright smoke test 风格：

- 浏览器依赖不可用时 skip。
- fixture 保持确定性。
- 不依赖外网。

### CLI 测试

新增 CLI monkeypatch 测试：

```text
web-kobe-explore --url ... --output ...
```

验证：

- 命令能解析。
- runner 收到正确的 URL/output/page_id/steps/headless。
- 输出路径被报告。

### 回归

运行：

```bash
.\.venv\Scripts\python.exe -m pytest tests/safesym_bridge -v
```

## v1 非目标

暂时不做：

- LLM/VLM 页面理解。
- 自动 repeated-group `ActionTarget` 推断。
- embedding state matching。
- graph audit。
- coverage checkpoint/replay。
- 多步智能探索策略。
- 从探索图生成参数化 PDDL。
- 真实高风险动作处理。

这个阶段的重点是让真实浏览器探索链路活起来。

## 成功标准

阶段完成时应满足：

1. 真实 Playwright 页面可以通过 `WebKobePlaywrightAdapter` 观察。
2. DOM interactables 可以变成 Web-KOBE action candidates。
3. `WebKobeExplorer.explore_one_step()` 可以执行真实 click。
4. graph 记录真实 self-loop edge 和 semantic delta。
5. CLI 可以对 fixture/local URL 运行 `web-kobe-explore`。
6. 现有 SafeSym bridge 测试仍然通过。

## 后续方向

这一步跑通后，下一个有价值的方向是加入语义智能：

```text
本地浏览器抽取
  -> LLM/VLM 语义提议
  -> 浏览器执行验证
  -> WebKobeGraph
  -> PDDL/SafeSym
```

后续阶段应该让系统更像 UI-KOBE 一样推断 page type、ActionTarget 和 Capability，同时继续让浏览器执行结果作为 verified effects 的来源。
