# 可复现性

## 环境

- Python 与依赖版本：待定。
- 模型、浏览器和外部服务版本：待定。
- 操作系统、浏览器配置与显示/viewport 设置：待定。
- Web 应用版本或访问日期、测试账号与隔离数据策略：待定。

## 可复现工件

| 工件 | 位置 | 生成命令 | 状态 |
| --- | --- | --- | --- |
| 功能模型 schema 与 verification state 定义 | 待定 | 待定 | 未开始 |
| 探索配置、提示词与冻结运行参数 | `experiments/configs/`、`experiments/protocol_v1.md` | 各实验配置内记录 | C1 已冻结；C2 formal v2 已冻结，18 条运行已完成 |
| 原始执行轨迹与 before/after observations | `../outputs/paper/formal/` | 各实验配置内记录 | C1 已有；C2 formal v2 的 run_01–run_03 已有；SauceDemo run_03 原失败件已归档 |
| 结果判断、证据链与人工标注 | `experiments/results/E003/`、`experiments/results/E004/` | `scripts/paper/analyze_c1.py`、`scripts/paper/analyze_c2.py` | C1 已归档；C2 覆盖账本 v1 已人工确认，最终报告为 `results/E004/c2_final_results.md` |
| 风险类别定义、风险知识库与版本 | `../src/ai_web_explorer/grounded_web/risk_taxonomy_v1.json` | 随代码版本冻结 | 已有 v1 |
| VLM 风险判断提示词与结构化输出 | `../src/ai_web_explorer/grounded_web/risk_detection.py` | 单元测试校验 | 已实现 |
| 候选功能、GUI 上下文与人工风险标签 | 待定 | 待定 | 未开始 |
| 风险识别评测脚本与原始输出 | `experiments/`（正式实验待登记） | CLI 支持 `--openai-risk-detection` 与 `--risk-detection-model` | 冒烟完成，正式实验未开始 |
| 保守投影及下游规划/验证输入 | 待定 | 待定 | 未开始 |
| 投稿图表与汇总数据 | `figures/`、`experiments/results/` | 待定 | 未开始 |

## 随机性与计算预算

- 记录模型采样参数、随机种子、每个应用的交互预算和重复次数。
- 报告模型调用量、浏览器交互步数、运行时间和失败/重试规则。
- 对外部网站状态变化和非确定性响应单独记录时间戳与异常。
- C2 pilot/formal 的普通候选 attempt 上限为 10/25；replay GUI 动作单独限额和报告。精确 seed 与运行命令在 pilot 配置中冻结。
