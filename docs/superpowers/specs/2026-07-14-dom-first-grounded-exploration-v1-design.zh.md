# DOM-first Grounded Exploration v1 设计说明（中文审阅版）

## 1. 项目目标

当前项目的核心目标不是做一个普通的网页自动化脚本，也不是让 agent 用 ReAct 的方式边猜边操作网页。

我们的目标是构建一个面向 SafeSym 的网页环境理解层：

```text
未知网页环境
  -> 探索网页可交互能力
  -> 记录动作与状态变化
  -> 构建 Web-KOBE / capability graph
  -> 后续投影给 SafeSym / PDDL 规划器使用
```

换句话说，项目真正关心的是：

- 这个网页/页面能做什么；
- 哪些对象会引发状态变化；
- 某个动作执行前后，页面状态发生了什么变化；
- 如何把这些观察结果组织成 SafeSym 能理解的结构。

我们暂时不把重点放在“这个网站里有什么具体内容”。例如商品网站中的不同商品、论坛中的不同帖子，可以先视为同一类能力结构下的不同实例；重要的是“商品可以加入购物车”“帖子可以打开/回复/点赞”，而不是某个商品的价格、图片或某个帖子正文。

## 2. 当前阶段目标

当前阶段的优先级是先跑通一个最小但真实的链路：

```text
打开页面
  -> 提取真实 DOM 中的可交互元素
  -> 生成 grounded action candidates
  -> 选择一个还没执行过的动作
  -> 用 Playwright 执行动作
  -> 观察执行前后的页面状态
  -> 记录状态变化 delta
  -> 写入 Web-KOBE graph
  -> 当所有候选动作都尝试过或达到步数上限后停止
```

这一阶段不追求复杂智能，也不追求非常漂亮的抽象图。首要标准是：

- agent 能准确操作网页；
- 执行动作必须来自真实 DOM 元素；
- 每一步能记录 before/after/delta；
- 能形成可检查的 graph 输出；
- 后续可以逐步替换选择策略、去重策略和状态抽象策略。

## 3. 为什么从 ReAct 转向 DOM-first

原始 `ai-web-explorer` 更接近传统 web agent 思路：让 LLM 根据页面信息决定下一步操作。这种方式灵活，但对我们当前目标有几个问题：

- LLM 可能生成页面上不存在或不稳定的选择器；
- 动作决策和信息收集混在一起，后续难以稳定复现；
- 成本较高，每一步都可能需要较多模型调用；
- 记录到的探索信息偏简单，不够贴近 SafeSym 需要的状态变化结构；
- 如果要构建知识库，最好先把“页面真实可做的动作”结构化出来，而不是让 LLM 每次重新推理。

因此当前方案采用 DOM-first：

```text
真实 DOM
  -> 本地代码提取可交互元素
  -> 本地代码生成可执行候选动作
  -> 策略模块只在候选动作中选择
  -> Playwright 使用真实 locator 执行
```

LLM/VLM 不是不用，而是放在更合适的位置：

- 可以帮助判断哪个候选动作更值得探索；
- 可以帮助给动作、页面状态、状态变化打语义标签；
- 可以帮助做抽象归纳；
- 但不应该凭空创造 selector 或直接决定不存在的动作。

## 4. 当前模块划分

### 4.1 Browser Runtime / Playwright Adapter

负责控制真实浏览器页面。

主要职责：

- 打开指定 URL；
- 等待页面加载；
- 执行 click/fill/select 等动作；
- 读取当前 URL、标题、DOM 状态；
- 向上层提供统一 adapter 接口。

当前实现重点在：

- `web_kobe_playwright_adapter.py`
- 用 Playwright 执行 `BrowserAction`
- 执行后等待页面进入相对稳定状态

### 4.2 DOM Observer

负责从当前页面 DOM 中提取可交互元素。

主要职责：

- 找到 button、link、input、select、textarea、带 role 的元素等；
- 为每个元素生成稳定 locator；
- 如果元素没有稳定 selector，自动注入 `data-web-kobe-id="dom_###"` 作为 fallback locator；
- 提取元素的文本、role、tag、可见性、disabled 状态等基础信息。

这是当前最重要的底座之一，因为后续所有动作都必须来自这里。

### 4.3 Action Candidate Builder

负责把 DOM interactable 转换成可执行动作候选。

主要职责：

- 根据元素类型生成 `BrowserAction`；
- click 类元素生成 click action；
- input/textarea/select 后续可以生成 fill/select action；
- 给动作生成语义 id；
- 保留 locator，确保动作能回到真实 DOM 元素。

当前 v1 中，重复结构暂时不急着去重。例如两个商品卡片里的 `Add to cart` 会作为两个具体候选动作分别执行。这样有助于先验证链路正确性。

### 4.4 Action Selector / Policy

负责从候选动作中选择下一步执行什么。

当前 v1 的策略可以非常简单：

```text
选择当前页面上第一个还没有执行过的候选动作
```

后续可替换为：

- coverage-based selector；
- BFS/DFS graph explorer；
- LLM selector；
- VLM selector；
- LLM + DOM 混合 selector。

关键原则是：selector 只能从已提取的候选动作中选，不能凭空创造动作。

### 4.5 Action Executor

负责执行选中的动作。

主要职责：

- 接收 `BrowserAction`；
- 使用 locator 定位真实元素；
- 执行 click/fill/select；
- 处理动作失败；
- 返回动作是否成功。

当前阶段主要验证 click 动作。fill/select 后续可以逐步加入。

### 4.6 State Observer / Delta Inferer

负责观察动作执行前后的页面状态，并计算变化。

当前 v1 的状态观察包括：

- 当前 URL；
- 页面标题；
- 页面 id；
- `[data-state]` 标记元素的文本和可见性；
- 一些测试 fixture 中的通用状态，例如 cart count、cart panel visibility。

delta 的目标是回答：

```text
执行这个动作之后，页面状态发生了什么变化？
```

例如：

```text
cart_count: 0 -> 1
cart_nonempty: false -> true
cart_panel_visible: false -> true
```

真实网站上不一定有 `[data-state]`，所以这部分后续还需要增强。可以结合 DOM diff、可见区域变化、URL 变化、表单状态变化、LLM 语义摘要等方法。

### 4.7 Exploration Controller

负责整体探索循环。

当前 v1 逻辑：

```text
for step in max_steps:
    observe current state
    list interactables
    build action candidates
    choose next unexplored candidate
    execute action
    observe new state
    record edge and delta
    stop if no candidate remains or action fails
```

后续如果引入 BFS/DFS，需要 controller 进一步负责：

- 状态队列；
- 回到历史状态；
- 页面路径 replay；
- 分支探索；
- 状态去重；
- 循环检测。

但这些不是当前最小链路的首要任务。

### 4.8 Web-KOBE Graph Recorder

负责把探索结果写入 graph。

主要记录：

- node：页面/状态节点；
- interactable：当前节点上的可交互对象；
- edge：执行某个动作造成的状态迁移；
- observed delta：动作前后的状态差异；
- action status：动作是否成功、是否 verified。

当前 graph 仍然偏“观察记录图”，不是最终抽象后的 capability graph。后续可以在它上面增加 normalizer，把多个具体动作和页面归纳成更抽象的能力结构。

### 4.9 Abstraction / Normalization（暂缓）

这是后续的重要模块，但当前可以先不做复杂版本。

它要解决的问题包括：

- 不同商品详情页是否应该归为同一类 `ProductDetailPage`；
- 不同帖子是否应该归为同一类 `ThreadPage`；
- 多个 `Add to cart` 是否抽象成一个 `add_product_to_cart(product)` 能力；
- URL 中的 id、slug、query 参数如何归一化；
- 页面 DOM 内容不同但结构相似时，如何判断它们是同一种页面状态。

这部分会直接影响最终 graph 的质量，但如果一开始就做太复杂，容易拖慢主链路验证。因此当前建议先保留原始观察数据，后续再做抽象层。

### 4.10 SafeSym / PDDL Exporter（后续）

最终要把探索得到的网页能力转换为 SafeSym 可以使用的信息。

可能输出：

- PDDL action schema；
- object/type 信息；
- precondition/effect；
- capability graph；
- 或 SafeSym 专用中间格式。

当前阶段只要保证记录的数据足够支撑后续投影即可，不急着把 PDDL 投影做到完美。

## 5. 当前 MVP Pipeline

当前最小可运行链路如下：

```text
Playwright Page
  -> DOM Observer
      提取真实可交互元素
      注入 fallback locator
  -> Action Candidate Builder
      生成 BrowserAction
  -> Selector
      选择尚未探索的候选动作
  -> Executor
      用真实 locator 执行动作
  -> State Observer
      观察 before/after
  -> Delta Inferer
      计算状态变化
  -> Web-KOBE Graph Recorder
      记录 node/interactable/edge/delta
  -> JSON Output
```

这条链路体现了当前项目的关键原则：

- 先 grounding，再决策；
- 先正确执行，再优化智能；
- 先保存原始观察，再做抽象归纳；
- LLM/VLM 用来增强判断，不替代真实 DOM grounding。

## 6. 当前本地测试 fixture

为了避免真实网站登录、重定向、网络变化等问题，当前使用本地测试网站：

```text
tests/fixtures/local_shop/index.html
```

这个页面模拟一个简单商品网站，包含：

- 购物车按钮；
- 两个商品卡片；
- 两个 `Add to cart` 按钮；
- 购物车面板；
- 页面状态标记。

期望探索结果：

| 动作 | 预期状态变化 |
| --- | --- |
| 点击购物车按钮 | `cart_panel_visible: false -> true` |
| 点击第一个 Add to cart | `cart_count: 0 -> 1`, `cart_nonempty: false -> true` |
| 点击第二个 Add to cart | `cart_count: 1 -> 2` |

这说明当前链路已经可以：

- 找到真实按钮；
- 区分两个结构相似但具体不同的按钮；
- 执行动作；
- 记录状态变化；
- 输出 graph edge。

## 7. 当前已经验证的结果

已运行的测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\safesym_bridge tests\test_local_shop_fixture.py tests\test_cli_start_url.py tests\test_cookie_prefilter.py tests\test_html_helpers.py tests\test_cli_collector_output.py tests\test_loop_task_guidance.py -q
```

结果：

```text
111 passed, 4 skipped
```

已运行的本地 smoke 测试：

```powershell
.\.venv\Scripts\python.exe -m ai_web_explorer.safesym_bridge.cli web-kobe-explore `
  --url http://127.0.0.1:8767/index.html `
  --output outputs/local_shop_dom_first_web_kobe.json `
  --app-name local_shop `
  --page-id local_shop `
  --steps 3
```

观察结果：

```text
steps: 3
nodes: 1
edges: 3
```

三条边分别对应：

- 打开购物车；
- 添加第一个商品；
- 添加第二个商品。

每条边都有 verified action 和 observed delta。

## 8. 当前不足

### 8.1 状态恢复还很弱

当前可以在一个页面上连续探索动作，但还没有完整解决：

- 如何回到某个历史节点；
- 如何 replay 路径；
- 如何从页面 A 回到页面 B；
- 如何处理登录态、购物车态、弹窗态等复杂上下文。

这会影响未来 BFS/DFS 的完整性。

### 8.2 去重和抽象还没真正做

目前两个 `Add to cart` 会作为两个具体动作记录。

这是当前阶段可接受的，因为我们优先验证真实执行链路。但后续需要把它们抽象为类似：

```text
add_to_cart(product)
```

否则 graph 会随着内容实例数量快速膨胀。

### 8.3 状态观察依赖还比较简单

本地 fixture 有 `[data-state]`，真实网站通常没有这么友好。

后续需要增强：

- DOM diff；
- URL/template diff；
- visible text summary；
- accessibility tree；
- form value changes；
- network/navigation signals；
- LLM 辅助状态摘要。

### 8.4 输入类动作还没有成为重点

当前最先验证 click。

真实网页还需要：

- 输入框填值；
- 下拉框选择；
- checkbox/radio；
- 文件上传；
- 滚动；
- hover；
- modal/dialog 操作。

这些动作普通 web agent 确实已有不少成熟经验，我们应该复用 Playwright 和现有项目的执行结构，而不是从零造轮子。

### 8.5 LLM/VLM 的使用位置还要继续设计

当前结论是：

- 不让 LLM 凭空控制网页；
- 让 LLM/VLM 在候选动作集合上做判断；
- 让 LLM/VLM 帮助做语义标注和抽象。

但具体 prompt、输入格式、缓存策略、失败回退还需要后续设计。

## 9. 和最初设想的关系

最初设想是：

```text
预先探索网站
  -> 构建知识库
  -> 减少 SafeSym/agent 在线 ReAct 成本
```

当前方案没有偏离这个初衷，只是把实现路径收敛得更工程化：

```text
不是先做一个很聪明的 ReAct agent，
而是先做一个可靠的网页能力采集器。
```

两者关系可以理解为：

- 预探索仍然是核心；
- 知识库/graph 仍然是核心产物；
- SafeSym 对接仍然是最终目标；
- 只是探索方式从“LLM 直接决定下一步”变成了“DOM-grounded candidate + 可替换 selector”。

这更符合我们目前的优先级：先保证网页操作正确，再提高探索智能。

## 10. 下一步建议

建议下一步继续沿着“能正确操作网页并记录变化”推进。

优先级可以是：

1. 固化 DOM-first exploration CLI 和输出格式；
2. 增强 interactable 提取，覆盖 link/input/select/dialog 等元素；
3. 增强状态观察，从 `[data-state]` 扩展到通用 DOM/URL/可见文本变化；
4. 做一个简单 BFS/DFS controller，但先不做复杂去重；
5. 引入 LLM selector，只允许它从候选动作中选择；
6. 后续再做页面/动作/实体抽象归一化；
7. 最后再推进 SafeSym/PDDL 投影质量。

如果只选一个最重要的下一步，我建议是：

```text
把当前 local_shop 的成功链路泛化成一个稳定的 DOM-first exploration runner。
```

这样我们就能在更多受控页面上测试，而不是每次都被真实网站的不稳定因素打断。

