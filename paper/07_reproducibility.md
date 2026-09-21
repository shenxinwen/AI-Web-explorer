# 可复现性

## 环境

- Python 与依赖版本：待定。
- 模型、浏览器和外部服务版本：待定。
- 操作系统、浏览器配置与显示/viewport 设置：待定。
- Web 应用版本或访问日期、测试账号与隔离数据策略：待定。

## 可复现工件

| 工件 | 位置 | 生成命令 | 状态 |
| --- | --- | --- | --- |
| 功能模型 schema、evidence judgment 与 admission indicator 定义 | 待定 | 待定 | 未开始 |
| 探索配置、提示词与冻结运行参数 | `experiments/configs/`、`experiments/protocol_v1.md` | 各实验配置内记录 | C1–C3 均已冻结；C2 formal v2 含 18 条运行 |
| 原始执行轨迹与 before/after observations | `../outputs/paper/formal/` | 各实验配置内记录 | C1、C2 已有；C3 探索关联与外部正式工件位于 `E002_c3_v1/` 和 `E002_c3_external_v1/` |
| 结果判断、证据链与人工标注 | `experiments/results/E002/`、`E003/`、`E004/` | `scripts/paper/analyze_c1.py`、`analyze_c2.py`、`analyze_c3.py`、`analyze_c3_external_pilot.py` | C1–C3 的人工确认 gold、可复算指标和最终报告均已归档 |
| 风险类别定义、风险知识库与版本 | `../src/ai_web_explorer/grounded_web/risk_taxonomy_v1.json` | 随代码版本冻结 | 已有 v1 |
| VLM 风险判断提示词与结构化输出 | `../src/ai_web_explorer/grounded_web/risk_detection.py` | 单元测试校验 | 已实现 |
| 候选功能、GUI 上下文与人工风险标签 | `../outputs/paper/formal/E002_c3_v1/`、`E002_c3_external_v1/` | E002 构建与标注脚本 | 106 条探索关联样本与 100 条外部样本已人工确认并冻结 |
| 风险识别评测脚本与原始输出 | `../scripts/paper/analyze_c3.py`、`analyze_c3_external_pilot.py`；`../outputs/paper/formal/E002_c3*/` | 冻结运行清单记录模型、temperature、prompt/taxonomy 版本 | 正式评测完成；探索关联 424 个、外部 200 个有效预测工件 |
| 保守投影及下游规划/验证输入 | 待定 | 待定 | 未开始 |
| 投稿图表与汇总数据 | `experiments/results/E002/`、`E003/`、`E004/` | 各实验分析/绘图脚本 | C1–C3 结果已归档；正式主稿选图待完成 |

## 随机性与计算预算

- 记录模型采样参数、随机种子、每个应用的交互预算和重复次数。
- 报告模型调用量、浏览器交互步数、运行时间和失败/重试规则。
- 对外部网站状态变化和非确定性响应单独记录时间戳与异常。
- C2 pilot/formal 的普通候选 attempt 上限为 10/25；replay GUI 动作单独限额和报告。精确 seed 与运行命令在 pilot 配置中冻结。
