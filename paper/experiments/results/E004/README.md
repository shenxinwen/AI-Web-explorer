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
