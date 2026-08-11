# Stagehand OpenAI-compatible Model Relay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan.

**Goal:** 让 Stagehand 执行模型通过独立的 OpenAI-compatible 中转调用 `gemini-3-flash-preview`，不影响截图 VLM 和 embedding。

**Architecture:** 保留现有 Stagehand SDK provider，在环境解析阶段构造 SDK 原生支持的 agent model 对象，并仅注入多步 `session.execute` 的 `agent_config.model`。未配置中转时调用形状保持不变。

**Tech Stack:** Python 3.11、Stagehand Python SDK 3.21、pytest/anyio、dotenv。

## Global Constraints

- 只修改本文列出的 provider、测试和 `.env.example`；不要修改用户 `.env`。
- 不读取或复用 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`EMBEDDING_BASE_URL`。
- `STAGEHAND_API_URL` 的含义不能改变，它仍是 Stagehand 服务地址。
- 不修改 Visual Delta、Planning Abstraction、动作成功判定或探索逻辑。
- 不把 API key、base URL 或 headers 放进 trace、日志或实验 JSON。
- 所有新参数必须可选；不得删除、改名或改变既有公开调用签名和返回类型。
- 每个任务按红灯—最小实现—绿灯执行，不顺手重构无关代码。

## Task 1: 用测试固定中转配置契约

**Files:**

- Modify: `tests/safesym_bridge/test_stagehand_sdk_provider.py`
- Reference: `src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py`

### Step 1: 写合法中转配置的失败测试

新增测试，调用 `create_async_stagehand_provider_from_env()`，显式传入：

```python
{
    "STAGEHAND_SERVER": "local",
    "STAGEHAND_MODEL": "openai/gemini-3-flash-preview",
    "MODEL_API_KEY": "cun-test-key",
    "STAGEHAND_MODEL_BASE_URL": "https://www.cun.ai/v1",
    "STAGEHAND_MODEL_USER_AGENT": "CUN.AI-Python/1.0",
    "OPENAI_BASE_URL": "https://visual.example.test/v1",
}
```

用现有 `FakeSession` 或等价 fake 执行一次 `execute_instruction()`，断言：

```python
session.executed_agent_config == {
    "mode": "dom",
    "model": {
        "model_name": "openai/gemini-3-flash-preview",
        "provider": "openai",
        "api_key": "cun-test-key",
        "base_url": "https://www.cun.ai/v1",
        "headers": {"User-Agent": "CUN.AI-Python/1.0"},
    },
}
```

同时断言 model 配置没有使用 `https://visual.example.test/v1`，并断言返回结果的 `raw`
序列化文本不包含 `cun-test-key`、`www.cun.ai` 或 `CUN.AI-Python`。

### Step 2: 运行单测并确认红灯原因正确

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_stagehand_sdk_provider.py -q
```

Expected: 新测试失败，因为当前 provider 没有把 `model` 放进 `agent_config`；既有测试通过。

### Step 3: 写错误配置的失败测试

分别增加参数化或独立测试，断言以下情况抛出 `ValueError`，错误文本包含对应变量名：

- `STAGEHAND_MODEL_BASE_URL=ftp://relay.test`；
- 配了 base URL，但模型名为 `google/gemini-3-flash-preview`；
- 配了 base URL，但没有任何可解析的模型密钥；
- 只配 `STAGEHAND_MODEL_USER_AGENT`，没有 base URL。

确保测试的 `environ` 是显式字典，不受开发机真实 `.env` 污染。

同时补一个明确的旧接口兼容测试（即使现有测试已有部分覆盖，也要集中表达契约）：

1. 用 `StagehandSdkProvider(session=session, page=page)` 旧构造方式创建 provider；
2. 分别调用原签名 `act_instruction(instruction)` 和
   `execute_instruction(instruction, max_steps=5)`；
3. 断言返回值仍为 `StagehandActResult`；
4. 断言未配置两个新变量时，factory 的 client/session 参数与当前既有断言完全一致；
5. 断言 execute 的 `agent_config` 仍严格等于 `{"mode": "dom"}`，没有空的 `model`。

### Step 4: 再次运行并保存红灯证据

Run 同 Step 2。

Expected: 新错误配置测试失败，因为当前实现不校验这些变量。

### Step 5: Commit 测试

```powershell
git add tests/safesym_bridge/test_stagehand_sdk_provider.py
git commit -m "test: define Stagehand model relay contract"
```

## Task 2: 在现有 provider 中装配 agent model

**Files:**

- Modify: `src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py`
- Test: `tests/safesym_bridge/test_stagehand_sdk_provider.py`

### Step 1: 增加最小内部解析函数

在 `_resolve_model_api_key()` 附近增加私有函数，签名固定为：

```python
def _resolve_agent_model_config(
    *,
    model_name: str,
    model_api_key: str | None,
    env: Mapping[str, str],
) -> dict[str, Any] | None:
```

行为：

1. 读取并 `strip()` `STAGEHAND_MODEL_BASE_URL` 和 `STAGEHAND_MODEL_USER_AGENT`。
2. 两者都未设置时返回 `None`，不改变旧路径。
3. User-Agent 单独存在时抛 `ValueError`。
4. base URL 必须以 `http://` 或 `https://` 开头。
5. 模型名必须以 `openai/` 开头。
6. `model_api_key` 必须非空。
7. 返回包含 `model_name`、`provider="openai"`、`api_key`、`base_url` 的字典；只在
   User-Agent 非空时增加 `headers`。

不要引入新模块或通用配置框架。

### Step 2: 把配置注入 provider

将构造函数扩展为：

```python
def __init__(
    self,
    *,
    session: Any,
    page: Any | None = None,
    agent_model_config: Mapping[str, Any] | None = None,
) -> None:
```

私有保存一份浅拷贝；不要增加会打印密钥的 `repr`、property 或日志。

`execute_instruction()` 先建立 `agent_config = {"mode": "dom"}`；私有配置存在时，将其
浅拷贝放到 `agent_config["model"]`。再用该对象构造 `execute_args`。

在 factory 中只解析一次模型密钥，同时用于 `AsyncStagehand(model_api_key=...)` 与
`_resolve_agent_model_config()`；把后者结果传给 `StagehandSdkProvider`。

不要修改 `session_options["model_name"]`、browser options 或 `act_instruction()`。
不要删除或改名 `create_async_stagehand_provider_from_env()`、`StagehandSdkProvider`、
`act_instruction()`、`execute_instruction()`；新增构造参数必须有 `None` 默认值。

### Step 3: 运行 provider 单测

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_stagehand_sdk_provider.py -q
```

Expected: 全部通过，包括未配置中转时仍严格等于 `{"mode": "dom"}` 的既有断言。

### Step 4: 运行相关 runner 回归

```powershell
.venv\Scripts\python.exe -m pytest tests/safesym_bridge/test_stagehand_actions.py tests/safesym_bridge/test_stagehand_sdk_provider.py tests/safesym_bridge/test_browser_runner.py -q
```

Expected: 全部通过；如果某个文件不存在，先用 `rg --files tests/safesym_bridge | rg "stagehand|browser_runner"` 核实并只移除不存在的路径，不扩大测试范围来掩盖失败。

### Step 5: Commit 实现

```powershell
git add src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py tests/safesym_bridge/test_stagehand_sdk_provider.py
git commit -m "feat: support independent Stagehand model relay"
```

## Task 3: 更新配置示例并做全量非浏览器验证

**Files:**

- Modify: `.env.example`
- Verify: `src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py`
- Verify: `tests/safesym_bridge/test_stagehand_sdk_provider.py`

### Step 1: 更新 `.env.example`

在 Stagehand 配置块加入注释示例：

```dotenv
# Optional OpenAI-compatible endpoint used only by the Stagehand execution model.
# STAGEHAND_MODEL_BASE_URL=https://www.cun.ai/v1
# STAGEHAND_MODEL_USER_AGENT=CUN.AI-Python/1.0
```

同时保留并强化已有注释：`STAGEHAND_API_URL` 不是 LLM provider 地址；不要改顶部截图
VLM 配置和底部 embedding 配置。

### Step 2: 运行完整非浏览器测试

```powershell
.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_local_shop_fixture.py
```

Expected: 至少保持交接基线 `319 passed, 2 skipped`，并加上本计划新增测试；不得减少原有
通过数。记录精确结果。

### Step 3: 做静态安全和格式检查

```powershell
rg -n "OPENAI_BASE_URL|EMBEDDING_BASE_URL" src/ai_web_explorer/grounded_web/stagehand_sdk_provider.py
git diff --check
git status --short
```

Expected:

- 第一条没有输出，证明 Stagehand provider 未耦合截图或 embedding 地址；
- `git diff --check` 无错误；
- 工作区只包含本计划预期文件，或在提交后为空。

再人工查看 diff，确认没有真实 API key。

### Step 4: Commit 文档示例

```powershell
git add .env.example
git commit -m "docs: document Stagehand model relay settings"
```

### Step 5: 向审查会话交付

报告：

- 各 commit SHA；
- provider 定向测试和全量非浏览器测试的精确结果；
- 静态检查结果；
- 未运行真实网络实验。

不要自行修改用户 `.env`，不要自行运行真实网页实验。真实一步实验由审查会话在代码
审查通过后执行；如果发现错误，保留证据并返回，不顺手修复其他 pipeline 问题。
