# E002 / C3 实验设计 v1

> 冻结日期：2026-09-20
>
> 状态：待 pilot；不得在 readiness 通过前启动 106 样本正式矩阵。

## 1. 研究问题与主张边界

C3 评价 VERA 对开放探索过程中**已经选择、即将执行**的 high-level action 的执行前风险识别能力。它不评价页面上未被探索器提出的动作，也不评价页面级完整风险发现率。

C3 保持 shadow mode：风险判断只记录和审计，不拦截、不改变 C2 的动作选择、预算、执行或 replay。实验不主张风险动作被阻止、实际损害减少或端到端安全性提升。

## 2. 主数据

- 来源：C2 formal v2 中 Full 条件的六条有效运行，两个网站各三条；
- 网站：Practice Shopping、SauceDemo；
- 样本单位：普通探索中一个执行前已选 high-level action；
- 原始普通 attempts：130；
- run 内去重键：`site + run_id + semantic_location + action_id`；
- 同一键只保留首次样本，跨 run 的相同动作保留，不同语义位置的相同动作保留；
- 主数据：106 条；排除的 run 内重复 attempts：24 条；
- 人工确认 gold：32 个风险正例，其中 `financial_transaction` 14、`sensitive_data` 18；
- 失败执行仍保留，因为 C3 判断对象是执行前潜在风险，而不是执行结果。

主数据和排除账本位于 `outputs/paper/pilot/E002_c3_v1/primary_dataset/`。C2 原始工件保持只读，不在 C3 中改写。

Replay 不进入主准确率。Replay 仅用于辅助 logging coverage 与轨迹关联审计；浏览器 reset/navigation 不作为 high-level risk-classification 样本。

## 3. Gold 标注

标注者只查看执行前 screenshot 与 selected action，不查看 after screenshot 或运行时风险预测。标签为：

- `potential_risk`：二元标签；
- `risk_type`：风险正例的单一主要类型；
- `evidence`：支持判断的执行前界面证据；
- `notes`：边界说明。

AI 初标已由用户逐项复核并确认。当前自然数据只支持评价 `financial_transaction` 与 `sensitive_data`；不得据此声称 taxonomy 中其他类别已得到充分验证。

## 4. 四条件消融

四种条件消费完全相同的冻结样本和 action label：

1. `action_only`：action label；不提供 screenshot 或 taxonomy；
2. `action_taxonomy`：action label + taxonomy；不提供 screenshot；
3. `action_visual`：screenshot + action label；不提供 taxonomy；
4. `full`：screenshot + action label + taxonomy。

四条件全部重新离线运行，不复用 C2 运行时保存的 Full 风险输出。模型统一为 `gpt-4o`，temperature 为 0；每条原始响应、解析结果、错误、模型返回标识、时间、prompt version、taxonomy version 和样本 ID 均须保存。

关键比较：

- `full - action_taxonomy`：视觉上下文贡献；
- `full - action_visual`：taxonomy 贡献；
- `full - action_only`：完整上下文条件判断相对静态动作判断的差异。

## 5. 指标

主指标为二元风险识别 precision、recall 和 F1，其中 F1 是主汇总指标，但三者必须共同报告。另报告 TP、FP、FN、TN。

辅助效果指标：

- 人工风险正例上的 primary risk-type accuracy；
- 三项预先指定的 F1 消融差值；
- 相同或相似动作在不同 GUI 上下文中的定性对照；
- 误报、漏报和风险类型错误分析。

可追溯性指标：

- 普通探索 risk-record coverage；
- replay high-level action risk-record coverage；
- 风险记录与 source run、sample、action、semantic location 和轨迹的关联完整率；
- 解析失败率与原始失败目录保留率。

每个网站分别计算指标；总体结果为两个网站指标的 macro-average，同时给出 106 条样本的 pooled confusion counts。Bootstrap 以 run 为重采样单位，固定 seed `20260920`，报告 95% confidence interval；小样本不作显著性主张。

## 6. Pilot

Pilot 使用主数据中的 20 条冻结样本，两个网站各 10 条，并同时包含风险正例、非风险样本与 checkout/login 边界案例。抽样 seed 为 `20260920`。Pilot 只验证实验 readiness，不进入正式结果。

通过条件：

1. 四条件均能接收预期输入，且不存在条件间输入泄漏；
2. 每个输出能关联到唯一 sample、source run、action 和执行前 screenshot（适用条件）；
3. 原始响应、解析结果和失败均被保存；
4. precision、recall、F1、type accuracy、网站 macro-average 和混淆矩阵均可复算；
5. 模型错误不会改变或删除输入样本；
6. C2 冻结工件没有发生修改。

Pilot 未通过时只修复日志、协议、prompt 或解析阻塞项；修改后使用新 pilot 版本目录重跑，不覆盖失败目录。

## 7. 输出目录

- Pilot：`outputs/paper/pilot/E002_c3_v1/ablations/`；
- Formal：`outputs/paper/formal/E002_c3_v1/`；
- 论文级协议、配置、汇总和人工复核记录：`paper/experiments/results/E002/`。

所有运行按 `condition/sample_id/attempt_N/` 保存。失败 attempt 目录永久保留；重试写入新的 `attempt_N`。只有满足冻结配置且输出可解析的样本进入正式指标，失败和缺失仍计入覆盖率及失败率。
