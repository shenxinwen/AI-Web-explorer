# 当前项目概览

## 项目价值

本项目把真实网页中的视觉交互自动转成可规划的语义模型。系统不依赖站点专用固定流程，而是观察页面、发现业务动作、执行并验证结果，最终生成可交给 SafeSym 的 Minimal Semantic PDDL。

## 当前唯一主线

```text
VLM 截图观察
  -> 生成候选业务动作及同位置 requires
  -> 按 semantic location 建立候选池
  -> 本地选择未完成且依赖满足的动作
  -> Stagehand 执行
  -> VLM 观察动作结果
  -> 更新 WebKobeGraph
  -> 必要时 replay 到其他 frontier
  -> 生成 Minimal Semantic PDDL
  -> SafeSym 验证或规划
```

正常探索负责发现、选择、执行和记录动作。replay 只负责从起始 URL 重放已有 semantic-action path，以恢复某个仍有未完成候选的上下文；它不扫描页面、不增加候选、不更新图，也不消耗正式动作尝试次数。动作都成功时，当前最小策略直接认为已恢复到目标位置；URL identity 只参与 replay frontier 的轻量匹配，不改变正常探索的 semantic-location 逻辑。

## 当前执行规则

- `observed_action`：Stagehand 直接执行观察到的动作。
- `observe_act/single_instance`：只执行 observe 返回的第一个原子动作。
- `observe_act/composite`：依次执行全部原子动作，全部成功后才观察高层 outcome。
- 每个候选最多尝试 2 次；失败后切换其他候选。
- 正式动作受最大探索步数限制。
- replay 每个 frontier 最多 2 次，总计最多 4 次。
- 当前不以全局连续无进展作为提前终止条件。
- `BusinessFlowProfile` 只用于本地事实验证和 planner projection，不控制探索流程。

## 当前完成情况

- 已形成 location-scoped 候选池、依赖过滤、有限重试和动作结果闭环。
- 已实现 frontier 选择、路径保存、reset + replay、失败诊断和次数上限。
- replay 能恢复到仍有候选的旧 frontier，并继续由正常 Explorer 探索。
- 已实现 WebKobeGraph 到 Minimal Semantic PDDL 的唯一投影路径。
- 已提供 Stagehand 探索、Semantic PDDL 投影和 SafeSym smoke 三个 CLI 入口。

## 仍有不足

- replay 当前信任动作执行成功，尚未做页面内容级 checkpoint 证明。
- semantic location 仍主要来自 VLM，跨站点稳定性需要更多实验。
- 候选依赖来自观察结果；遗漏依赖可能导致上下文恢复不完整。
- SafeSym 的端到端规划质量仍需在更多真实网站验证。

## 不再属于当前结构

旧 Trace/Location/Surface PDDL、旧 graph/debug exploration CLI、Behavior State Graph phase-a、旧 ecommerce smoke runner、`SemanticExperimentProfile`、`ActionContract` 和 `business_milestone` 已从生产路径移除。历史设计与实验文档仅作为演进记录，不代表当前接口。
