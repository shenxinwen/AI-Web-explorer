# 当前主线结构清理设计

## 目标

把生产代码收束到已经通过动态实验验证的唯一主线：

```text
Stagehand/VLM 开放探索
-> semantic location 候选池
-> WebKobeGraph
-> frontier replay
-> SemanticPlanningGraph
-> Minimal Semantic PDDL
-> SafeSym
```

清理只移除历史入口、旧投影和当前配置下不再使用的探索分支，不改变候选调度、动作执行、
replay、断点恢复、图格式或 Minimal Semantic PDDL 的现有行为。

## 保留结构

- `WebKobeExplorationController`、`WebKobeExplorer`、location candidate memory 和 replay；
- `initial` screenshot scan、同位置 `requires`、`single_instance`/`composite` 执行；
- ActionOutcome 动作后观察；
- compact graph、evidence sidecar、resume runtime state；
- `SemanticPlanningGraph`、Minimal Semantic domain/problem 和 SafeSym smoke；
- Stagehand adapter 所需的 DOM、page structure、state summary 和 evidence 基础模型；
- `BusinessFlowProfile` 的可选本地结构化事实验证与 planner projection 作用；
- 历史 graph 的必要只读反序列化兼容，除非确认没有现存 artifact 依赖。

## 删除结构

### 旧 PDDL 与 CLI

- Trace、Surface、Location 和旧 node-based PDDL 的 CLI 入口及生产模块；
- `web-kobe-phase-a`/`web-kobe-consolidate` 多投影入口；
- 旧 debug graph、旧 Playwright exploration 和 node-based PDDL smoke 命令；
- semantic projection 对旧 `PlanningGraph`/`planning_abstraction` 的前置依赖和自动 location fallback。

保留一个直接的 semantic projection 命令，以及独立 SafeSym smoke 命令。显式 goal 在 semantic graph
不可用时 fail closed，不降级为另一种语义模型。

### 旧探索分支

- `location_scoped_exploration=False` 的 legacy business-edge 分支；
- active runner 不使用的 targeted/supplement scan prompt、parser、状态和执行分支；
- replay 末端 legacy VLM checkpoint validator；
- 真实 runner 已不使用的全局连续无进展配置。

删除以调用链为单位进行；仍被当前 adapter、graph schema 或 resume artifact 使用的底层类型不因名称陈旧而删除。

### 历史实验结构

- 当前动态 SauceDemo 入口保留；
- 静态 probe/acceptance 脚本及其专用测试在证据已经固化后移出 active scripts，历史设计文档可保留为审计资料；
- 核心 README、结构文档和 bridge 文档只描述当前入口，历史决策仍可留在 decision log 并标注已取代。

## 实施顺序

1. 先用 CLI 行为测试规定唯一 semantic projection 接口，并验证旧命令被拒绝；
2. 删除旧 CLI 分支、投影模块和对应测试，让 semantic projection 直接消费 `WebKobeGraph`；
3. 用当前探索与 replay 测试保护 active loop，再删除 targeted/supplement、legacy mode 和 validator；
4. 删除只服务上述路径的模型字段、序列化状态和实验脚本；
5. 更新公开 API 和核心文档；
6. 运行分层测试及完整测试，保留已知 Playwright `spawn EPERM` 环境失败的独立说明。

## 验收标准

- 一个公开 Stagehand 探索入口；
- 一个 Minimal Semantic PDDL 投影入口；
- 一个 SafeSym smoke 入口；
- active CLI 不再导入 Trace/Surface/Location/node-based projector；
- semantic projection 不再生成旧 Planning Graph artifact，也不自动 fallback；
- Explorer 只运行 initial scan + ActionOutcome 主线；
- replay 仍只恢复上下文，限制、失败诊断和候选状态保持不变；
- SauceDemo runner、replay、resume、SemanticPlanningGraph、Minimal Semantic PDDL 和 SafeSym 相关测试通过；
- 核心文档与实际公开入口一致。

## 风险控制

- 不一次性按文件名删除底层模型；先删除入口和调用，再通过 import 搜索确认孤立模块；
- 每一组删除使用测试先定义保留行为，并先观察旧行为测试失败；
- graph 读取兼容与 runtime 行为分开处理，避免旧 checkpoint 无法恢复；
- 不引入新的 profile、ActionContract、business milestone、站点固定流程或 goal-directed exploration。
