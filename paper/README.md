# ICLR 2027 投稿工作区

本目录承载论文从选题、实验到匿名投稿的长期工作状态；工程设计文档继续保留在 `docs/`。

## 使用顺序

1. 每次开始论文相关工作，先阅读 `STATUS.md`。
2. 新的论点、实验或结果分别写入对应主题文件，并在 `STATUS.md` 更新摘要与下一步。
3. 实验必须先在 `experiments/registry.md` 登记，再将可投稿的汇总结果归档到 `experiments/results/`。
4. 每张图必须登记在 `figures/figure_manifest.md`，说明它支撑的论点和可复现来源。
5. 投稿前使用 `10_submission_checklist.md` 进行逐项检查。

## 目录导航

- `00_scope.md`：研究范围与投稿定位。
- `01_contributions.md`：可检验的核心贡献和证据链。
- `02_outline.md`：论文大纲；当前参考仓库根目录的 `大纲v3.md`。
- `03_related_work.md`：相关工作与差异化定位。
- `04_method.md`：方法、算法及其代码映射。
- `05_experiments.md`：实验协议。
- `06_results.md`：已确认的结果与论文级结论。
- `07_reproducibility.md`：复现材料与运行环境。
- `08_ethics_and_limitations.md`：伦理、局限和负面结果。
- `09_anonymity_and_ai.md`：匿名性和 AI 使用披露。
- `10_submission_checklist.md`：投稿检查清单。
- `manuscript/`：LaTex 主稿与章节源文件。
- `experiments/`：实验注册表、冻结配置和投稿级结果。
- `figures/`：论文图及其清单。
