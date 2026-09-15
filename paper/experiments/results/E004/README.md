# E004 / C2 Pilot 运行记录

## Pilot v1

- 配置：`paper/experiments/configs/E004_c2_pilot_v1.md`
- 实现提交：`0c1f0c4479594eee3bb30b99ce1d00f07233df9c`
- 原始输出：`outputs/paper/pilot/E004_c2_v1/`（不进入正式论文结果）
- 状态：中止；4/6 runs 已启动，发现 checkpoint 写入阻塞，未启动 Practice Shopping Full。

| 网站 | 方法 | 状态 | 普通 attempts | evidence-complete | executor failed | replay | 停止/异常 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| SauceDemo | Random | 完成 | 10 | 10 | 3 | 0 | `max_exploration_steps_reached` |
| SauceDemo | Linear | 完成 | 10 | 10 | 4 | 0 | `max_exploration_steps_reached` |
| SauceDemo | Full | 完成但受外部异常影响 | 8 | 5 | 4 | 0 | 连续 TLS 失败后 Stagehand 会话失效；`no_recoverable_frontier` |
| Practice Shopping | Random | 完成 | 10 | 10 | 0 | 0 | `max_exploration_steps_reached` |
| Practice Shopping | Linear | 运行失败 | 1 个成功 attempt 已保存；第 2 个 attempt 开始时失败 | 待审计 | 待审计 | 0 | Windows checkpoint `os.replace` 返回 `PermissionError` |
| Practice Shopping | Full | 未运行 | — | — | — | — | 因 pilot 阻塞而停止后续运行 |

## 已确认事项

- Random、Linear、Full 条件名可以写入 graph metadata；Random seed 正确保存。
- 已完成的三条无外部异常 runs 均能导出 10/10 唯一 attempts，before/after screenshots 完整。
- 失败 attempts 会被保留，不因 executor failure 从导出表删除。
- Random 与 Linear 均未产生 replay，符合配置。

## Pilot 暴露的问题

1. Full 的首条运行没有触发 replay，尚不能用真实轨迹验证 replay GUI 成本和 replay-to-follow-up-attempt 关联。
2. Stagehand 上游 TLS 连续失败会使当前浏览器会话失效，并产生 evidence-incomplete attempts。
3. Windows 上 checkpoint 临时文件替换 `graph.json` 可能瞬时返回 `PermissionError`，当前没有 bounded retry，导致整个 run 退出。
4. 冻结配置要求保存 `run_command.txt` 与 `run_status.json`，当前 CLI 尚未自动生成，v1 只能由本记录追溯命令和状态。

## 处理决定

- 不删除、不覆盖、不选择性替换上述 v1 产物。
- 在修复 checkpoint bounded retry 和运行清单记录后创建 pilot v2。
- pilot v2 必须实际触发至少一次 replay，或明确证明两个网站在 pilot 预算下自然没有 recoverable frontier；否则不能进入正式 C2 runs。

## Pilot v2（进行中）

- 配置：`paper/experiments/configs/E004_c2_pilot_v2.md`
- 实现提交：`72727ce985d25d023fc156da3f6070e0e7c18a7a`
- 原始输出：`outputs/paper/pilot/E004_c2_v2/`
- 当前状态：2/6 runs 完成；尚未启动正式实验。

| 网站 | 方法 | 状态 | 普通 attempts | evidence-complete | executor success | replay GUI attempts | 停止原因 |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Practice Shopping | Linear | 完成 | 10 | 8 | 8 | 0 | `max_exploration_steps_reached` |
| Practice Shopping | Full | 完成 | 10 | 8 | 3 | 0 | `max_exploration_steps_reached` |

两条 run 均越过 v1 的 checkpoint 失败位置并正常结束，说明 bounded retry 修复有效。失败与 evidence-incomplete attempts 均保留，并生成了 `run_command.txt`、`run_status.json` 和 `c2_attempts.csv`。

Full 在 10-attempt 预算内仍未触发 replay。代码审查确认 replay 仅在当前状态返回 `current_state_exhausted` 后启动；本次 run 在预算结束前始终还有当前路径候选。因此当前只能验证 Full 条件可运行，尚不能完成 replay 成本与增量覆盖的 pilot 验收。继续完整矩阵前，应增加一条不计入条件比较结果的 replay activation smoke，或调整下一版 pilot 使其自然达到当前状态耗尽；不得把人为触发 smoke 混入 Random/Linear/Full 主比较。

## 正式实验 v1（暂停）

- 配置：`paper/experiments/configs/E004_c2_formal_v1.md`
- 原始输出：`outputs/paper/formal/E004_c2_v1/`
- 经用户确认采用分阶段运行；目前仅执行第一条 Practice Shopping / Full / `run_01`，其余 5 条尚未启动。

该 run 在 17 个普通 attempts 后因 `no_recoverable_frontier` 自然停止：14 次 executor success，16 次 evidence-complete；成功触发 1 次 replay，并关联到恢复后的首个普通 attempt。Replay 目标由入口 reset 直接到达，路径 action 为 0。

审计发现当前 `replay_gui_action_attempts` 只累计 replay path actions，没有累计 `reset_to(start_url)` 导航。因此本次 replay 虽然发生，成本却记为 0，不能满足“完整单列 replay GUI 成本”的实验口径。为避免系统性低估 Full 成本，正式 v1 在 1/6 条后暂停；原始 run 永久保留，不覆盖。修复前不继续其他正式 runs。

## 正式实验 v2（第一阶段完成）

- 配置：`paper/experiments/configs/E004_c2_formal_v2.md`
- 实现提交：`bab1318824a945ef13fbe9e521aa4fd862bd53f1`
- 原始输出：`outputs/paper/formal/E004_c2_v2/`

Replay reset 成本修复通过测试后，重新启动 Practice Shopping / Full / `run_01`。该 run 保存了 `before_0001`，但初始动作的外部模型/Stagehand 调用超过 150 秒没有返回，因配置未冻结请求超时而由操作者中断；未形成 graph checkpoint，状态标记为 `environment_failure`，原始目录永久保留。

经用户确认，在不修改 v2 配置的情况下执行一次独立 `replacement_01`。该 run 正常跑满 25 个普通 attempts：17 次 executor success、21 次 evidence-complete、8 次 executor failure，停止原因为 `max_exploration_steps_reached`；未触发 replay。该结果说明前一条初始挂起是偶发外部异常，而不是稳定配置错误。原失败 run 与 replacement 均保留；用户已在人工覆盖率标注前确认将 `replacement_01` 作为 Practice Shopping / Full 的有效 `run_01` 纳入主分析。

第一阶段的 6 条有效 `run_01` 已完成：

| 网站 | 方法 | 有效目录 | 普通 attempts | evidence-complete | executor success | executor failed | replay 次数 | replay GUI actions | 停止原因 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Practice Shopping | Random | `random/run_01` | 19 | 18 | 7 | 12 | 0 | 0 | `current_state_exhausted` |
| Practice Shopping | Linear | `linear/run_01` | 17 | 15 | 11 | 6 | 0 | 0 | `current_state_exhausted` |
| Practice Shopping | Full | `full/replacement_01` | 25 | 21 | 17 | 8 | 0 | 0 | `max_exploration_steps_reached` |
| SauceDemo | Random | `random/run_01` | 3 | 3 | 1 | 2 | 0 | 0 | `current_state_exhausted` |
| SauceDemo | Linear | `linear/run_01` | 10 | 10 | 10 | 0 | 0 | 0 | `current_state_exhausted` |
| SauceDemo | Full | `full/run_01` | 20 | 20 | 16 | 4 | 4 | 28 | `total_replay_limit_reached` |

这里的普通 attempts 是三种方法共享的 25-attempt 主预算。Full 的 replay reset 与路径执行不计入普通 attempts，而是单列为 replay GUI actions。SauceDemo / Full 提供了真实验证：它在 20 个普通 attempts 之外执行了 28 个 replay GUI actions；停止原因是独立的总 replay 上限，而不是普通 attempt 上限。

## 正式实验 v2（Full / run_02 已完成人工复核）

本阶段仅执行两个 Full 条件的 `run_02`；没有启动 Random、Linear 或任何 `run_03`，候选上限与探索提示词均未修改。AI 初标已经冻结 inventory 的逐项人工复核确认，可作为这两条 run 的正式覆盖率；其余条件仍未标注或复核。

| 网站 | 方法 | 有效目录 | 普通 attempts | evidence-complete | executor failed | replay 次数 | replay GUI actions | 停止原因 | 已复核覆盖率 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| Practice Shopping | Full | `practice_shopping/full/run_02_replacement_03` | 18 | 16 | 4 | 1 | 1 | `no_recoverable_frontier` | 9/16 (56.3%) |
| SauceDemo | Full | `saucedemo/full/run_02` | 21 | 21 | 0 | 3 | 20 | `no_recoverable_frontier` | 14/22 (63.6%) |

- 初始逐 attempt 标注分别保存在有效 run 目录的 `c2_attempts_ai_initial.csv`；人工复核接受该初标，且对应可重算摘要为 `c2_metrics_ai_initial.json`。
- Practice Shopping 的两条价格筛选 attempt 缺少 after 截图，标作 `incomplete`；其余 16 条 evidence complete。唯一 replay 为入口 reset，包含 1 个 GUI 动作，恢复后首个普通 attempt 是 `view_cart`。
- SauceDemo 的 3 条 replay 均成功，GUI 成本分别为 5、7、8 个动作。`generate_order_pdf` 被提出并执行两次，但 before/after 未呈现可见下载或其他结果，因此初标为 `proposed_only`，不计 SD22。
- 两个 run 都未产生商品详情候选；Practice Shopping 也未产生分页候选。这是候选生成覆盖的观察记录，不能由这两条 run 单独推广为随机性结论。

### 保留的无效 Practice Shopping Full / run_02 目录

下列目录永久保留供可追溯性使用，但不进入正式结果：

| 目录 | 排除原因 |
| --- | --- |
| `practice_shopping/full/run_02` | 浏览器启动前的 spawn `EPERM`。 |
| `practice_shopping/full/run_02_replacement_01` | 共享 `state_embeddings` 写入失败。 |
| `practice_shopping/full/run_02_replacement_02` | `stagehand_trace` 写入失败。 |

`run_02_replacement_03` 是唯一有效的 Practice Shopping Full / run_02。后续每条 run 必须使用显式、独立的 `--embedding-path`，以避免共享嵌入状态写入。

### Windows 原子写入修复

Windows 上 `os.replace` 偶发 `PermissionError` 的两个 checkpoint 写入点已加入有界重试：`browser_runner.py` 的运行产物写入，以及 `state_embedding.py` 的状态嵌入写入；相应回归测试已添加。上述两条有效 run 均在修复后完成。该修复不改变候选预算、选择策略或探索提示词。

目前只可报告运行与成本诊断，不能据此下覆盖率结论。`c2_attempts.csv` 已全部导出，但功能覆盖率仍需按冻结功能清单完成人工标注。按预注册阶段门，暂不启动 `run_02` 和 `run_03`。
