# E004 / C2 正式实验配置 v1

> 状态：已冻结并暂停。首条 Full run 暴露 replay reset 导航未计入 GUI 成本的问题；其余 runs 未启动，详见 `paper/experiments/results/E004/provenance/experiment_history.md`。
>
> Pilot v1/v2 产物不计入正式结果，且不得复制、续跑或替换为正式 run。

## 第一阶段矩阵

- 网站：SauceDemo、Practice Shopping。
- 方法：Random、Linear、Full。
- 第一阶段每个组合运行 1 次，共 6 runs；这些 run 直接作为正式 `run_01`，不得择优重跑。
- 每个 run 最多 25 个普通候选 action attempts；frontier 自然耗尽可提前结束。
- Random seeds：SauceDemo `5101`，Practice Shopping `5201`。Linear 与 Full 不使用随机 seed。
- 输出根目录：`outputs/paper/formal/E004_c2_v1/`。
- 冻结运行顺序：Practice Shopping Full、SauceDemo Random、Practice Shopping Linear、SauceDemo Full、Practice Shopping Random、SauceDemo Linear。

## 固定实现与参数

| 字段 | 值 |
| --- | --- |
| 冻结日期 | 2026-09-14 |
| 实现提交 | `72727ce985d25d023fc156da3f6070e0e7c18a7a` |
| Stagehand / candidate / outcome / risk 模型 | provider 上的 `gpt-4o` 部署别名 |
| OpenAI visual delta / outcome / risk temperature | `0` |
| Stagehand temperature | SDK 默认值；当前 CLI 不显式设置 |
| Stagehand execution mode | `observe_act` |
| business profile | `none` |
| viewport | `1440 × 1000` |
| max candidates per location | 12 |
| max action attempts per candidate | 2 |
| max VLM scan attempts | 2 |
| max replay attempts per frontier | 2 |
| max total replays | 4（仅 Full） |
| Candidate prompt SHA-256 | `583439613f0ce52cda8adaeb094d51aab4be6207c37b814e6ffc76b3e3b6566f` |
| Outcome prompt SHA-256 | `1cb2441d2ef6085553af70e5b3b726c0c1ca058946f939194e76c612a2d424f2` |
| Stagehand goal prompt SHA-256 | `7aafdaa0c85c4d79a1d5e22feab68fc35c1c14352e7f7a64008277f02c9406a4` |
| Location exploration SHA-256 | `7031ae07bd8680f9f89b3f5ea9f9245d4c019db6b57ca83088dec14354a96770` |
| Frontier replay SHA-256 | `d8648f10bd974ec4dbc4df8cf3a5510f2233d8e214f622c966c9eaeb50555f95` |
| 覆盖率分母 | `paper/experiments/core_functions/*.csv` |

三种方法仅保留以下有意差异：

| 方法 | 候选选择 | 依赖检查 | replay |
| --- | --- | --- | --- |
| Random | 固定 seed 随机选择 | 否 | 否 |
| Linear | 确定性顺序 | 是 | 否 |
| Full | 与 Linear 相同 | 是 | 是 |

## 预算和异常规则

- 普通候选 attempt 是共享的 25-step 预算单位。
- Replay GUI 动作不占普通候选预算；单列 attempted/completed/success/failure，并报告 total GUI actions。
- 失败、无变化、uncertain、evidence-incomplete attempts 全部保留。
- 每条 run 使用新浏览器上下文和独立目录；不从 pilot 或其他正式 run resume。
- 外部服务、浏览器或网站异常导致的原始 run 永久保留并标记 `environment_failure`。
- 只有明确的环境故障才允许追加 replacement；使用 `replacement_01` 等独立目录，不覆盖原 run，也不自动纳入主分析。是否纳入敏感性分析须在查看覆盖率结果前决定并记录。
- Risk detection 以相同 shadow-mode 运行，不拦截动作，也不作为 C2 成功条件。
- 每条 run 保存 `run_command.txt`、`run_status.json`、graph、evidence、trace、screenshots 和 attempt CSV。

## 第一阶段检查点

完成 6 条 `run_01` 后暂停并审计：

1. 功能覆盖率与覆盖增长曲线能否计算；
2. Full 是否发生 replay，GUI 成本和 post-replay attempt 能否关联；
3. 环境故障是否足以使某条 run 不可解释；
4. 三种条件是否除预注册差异外保持一致。

通过检查后，仍需再次确认才执行其余 12 条正式 runs。
