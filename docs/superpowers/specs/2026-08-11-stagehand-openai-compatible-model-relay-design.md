# Stagehand 独立 OpenAI-compatible 模型中转设计

## 背景

当前真实执行由 Stagehand Python SDK 负责，截图 VLM 与 embedding 分别使用自己的
OpenAI-compatible 配置。现有 Stagehand provider 只把模型名和模型密钥传给 SDK，无法
单独指定模型服务的 `baseURL` 和请求头。因此，把 Stagehand 切到 CUN.AI 中转时，如果
复用 `OPENAI_BASE_URL`，会误改截图 VLM；如果复用 `STAGEHAND_API_URL`，则会把模型地址
错当成 Stagehand 服务地址。

本次只解决这一处配置缺口，让 Stagehand 使用：

- `openai/gemini-3-flash-preview`
- `https://www.cun.ai/v1`
- `User-Agent: CUN.AI-Python/1.0`

截图 VLM 和 embedding 的模型、地址与密钥保持原样。

## 目标与非目标

### 目标

1. 为 Stagehand 执行模型增加独立的 OpenAI-compatible `baseURL`。
2. 可选地为 Stagehand 模型请求增加 `User-Agent`。
3. 继续兼容未配置中转的现有 DeepSeek、OpenAI 等配置。
4. 不把模型密钥、中转地址或请求头写入 Stagehand trace 和实验产物。
5. 用单元测试确认配置隔离，再由审查会话运行一轮一步真实实验。

### 非目标

- 不修改截图 VLM 的 `OPENAI_BASE_URL`、`OPENAI_API_KEY` 或视觉模型。
- 不修改 embedding 配置。
- 不处理 Visual Delta 分类、Planning Abstraction、target reuse 等其他问题。
- 不改变 Stagehand 动作成功判定、异常容错或动作后观察逻辑。
- 不引入新的中转 SDK、配置文件或 provider 模块。
- 不删除或改名既有 factory、provider 构造参数、`act_instruction()`、
  `execute_instruction()`；调用方不需要迁移。

## 配置契约

沿用已有变量：

```dotenv
STAGEHAND_SERVER=local
STAGEHAND_MODEL=openai/gemini-3-flash-preview
MODEL_API_KEY=<stagehand-model-key>
```

新增两个只属于 Stagehand 模型请求的可选变量：

```dotenv
STAGEHAND_MODEL_BASE_URL=https://www.cun.ai/v1
STAGEHAND_MODEL_USER_AGENT=CUN.AI-Python/1.0
```

边界说明：

- `STAGEHAND_API_URL` 仍只表示 Stagehand 服务地址。
- `OPENAI_BASE_URL` 仍只供截图 VLM 使用，Stagehand provider 不读取它。
- `EMBEDDING_BASE_URL` 仍只供 embedding 使用。
- 配置 `STAGEHAND_MODEL_BASE_URL` 时，`STAGEHAND_MODEL` 必须使用 `openai/` 前缀，明确
  表示通过 OpenAI-compatible 协议访问；否则启动时直接报清楚的配置错误。
- `STAGEHAND_MODEL_USER_AGENT` 只有在设置了 `STAGEHAND_MODEL_BASE_URL` 时才有意义；
  单独设置时启动报错，避免用户误以为请求头已生效。

## 实现方案

只改 `stagehand_sdk_provider.py` 中现有配置装配。

新增一个内部解析函数，把环境变量解析成可选的 Stagehand agent model 字典。中转未
配置时返回 `None`，保持当前 `agent_config={"mode": "dom"}` 行为不变；中转配置后，
生成：

```python
{
    "model_name": "openai/gemini-3-flash-preview",
    "provider": "openai",
    "api_key": "...",
    "base_url": "https://www.cun.ai/v1",
    "headers": {"User-Agent": "CUN.AI-Python/1.0"},
}
```

`StagehandSdkProvider` 私有保存该字典，在 `execute_instruction()` 中作为
`agent_config["model"]` 传给 SDK。当前业务 runner 使用的正是多步 `execute` 路径。
`act_instruction()` 是低层兼容接口，而 Stagehand 3.21 的 `session.act` 不接收同类模型
对象，所以本次不扩展它；session 创建时仍保留已有模型名与模型密钥配置。

SDK 3.21 的 `session_execute_params.AgentConfigModelGenericModelConfigObject` 已原生支持
`model_name`、`provider`、`api_key`、`base_url` 和 `headers`，因此不需要绕过类型或直接
发 HTTP 请求。

## 数据与安全边界

模型配置只存在于 provider 私有字段和发给 Stagehand SDK 的调用参数中。现有 trace 只
从 Stagehand 响应构造，不应加入请求配置。测试会使用假 session 捕获调用参数，同时
断言返回的 `StagehandActResult.raw` 不含 API key、base URL 和 User-Agent。

环境示例只写占位符，不写用户真实密钥。实现与测试不得读取或改写 `.env`。

## 兼容性与失败方式

- 未设置两个新变量：所有既有测试与调用形状保持不变。
- 旧调用 `StagehandSdkProvider(session=session, page=page)` 保持有效；新增构造参数必须有
  默认值且仅为 keyword-only 可选参数。
- 旧的 `act_instruction(instruction)` 和
  `execute_instruction(instruction, max_steps=...)` 签名与返回类型保持不变。
- 设置合法中转：只给 `session.execute` 的 agent model 增加独立配置。
- 中转 URL 为空不算配置；非 `http://`/`https://` URL 启动失败。
- 中转已设置但没有 `MODEL_API_KEY` 或 provider 别名可解析出的密钥：启动失败，而不是
  把无密钥请求拖到运行阶段。
- 中转已设置但模型不是 `openai/...`：启动失败并提示前缀要求。
- User-Agent 单独设置：启动失败并提示同时设置模型 base URL。

## 验证方式

1. provider 单元测试覆盖旧配置不变、合法 CUN.AI 配置、配置隔离和错误输入。
2. 运行完整非浏览器测试，确认基线仍为通过。
3. 审查会话使用用户已配置的 `.env` 运行一步新目录实验，确认：
   - 不再出现 `Thinking mode does not support this tool_choice`；
   - Stagehand 返回可解释的执行结果；
   - checkpoint、graph 与 evidence 仍完整；
   - 截图 VLM 配置没有变化。

真实实验失败时只保留并报告产物，不在同一轮顺手修改其他 pipeline 逻辑。
