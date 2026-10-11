# Round 126 Codex 定向复审：回填恢复日

基于 `git archive d8decae` 的系统临时归档，补入本机原始资料与空 `products/`。只审本提交与第 125 轮的阻断项；未跑全量。严重度依 `AGENTS.md` 的本机单用户威胁模型。

| 项目 | 意见 | 证据与可复现输入 |
| --- | --- | --- |
| 第 125 轮原复现 | **不改** | 空队列先写 `freeze(2026-09-15)`，再运行 `ky resume --date 2026-09-14 --workspace <注册表>`：现在退出 **2**，提示最晚可用恢复日期，队列 manifest 与所有冻结事件文件字节不变，锁存仍生效。`--dry-run` 同样退出 2。换成 9 月 12 日到期的逾期项后，正式与 dry-run 仍均退出 2、字节不变。判断在 `ky/__main__.py:482-491`，位于 `ReviewShardStore.write` / `write_resume_record` 之前（`ky/__main__.py:497-509`）。 |
| 多条未解除冻结 | **不改** | 写 `F1(2026-09-16)`、`F2(2026-09-19)`，运行 `ky resume --date 2026-09-15`：退出 2，错误提示 9 月 19 日。`unresolved_freezes` 对每条 F 按“之后的 R 且 R.day ≥ F.day”判定（`ky/freeze/port.py:50-65`）；CLI 再取未解除集合的最大日期（`ky/__main__.py:482-484`），逻辑正确。 |
| 日期等于冻结日 | **不改** | 空队列写 `freeze(2026-09-15)`，执行 `ky resume --date 2026-09-15`：退出 0，追加当日 resume 事件，`latch_active` 变为 false。比较运算是 `latest_freeze > day`，没有误拒等号（`ky/__main__.py:484`）。 |
| 已解除的较晚旧冻结 | **不改** | 依序写 `F(2026-09-19)`、`R(2026-09-19)`、`F(2026-09-14)`；运行 `ky resume --date 2026-09-15`：退出 0，追加第 4 条 R，锁存解除。调用前 `unresolved_freezes` 只含 9 月 14 日的 F；已解除的 9 月 19 日 F 不参与最大日期。 |
| 测试强度 | **建议改** | 归档内 `tests.contract.test_resume_port` 6 项、`tests.contract.test_freeze_port` 13 项均通过。新增 `test_resume_dated_before_an_unresolved_freeze_is_rejected` 覆盖空／逾期 × dry-run／正式四格；临时把保护条件改成恒假，这一条测试出现 **4 个失败**，撤修复会变红。其无写入断言只比对 queue manifest 字节与事件**文件名**（`tests/contract/test_resume_port.py:216-247`），没有比对 shard 与事件内容；建议快照受影响目录全部文件字节。等号与“已解除的较晚 F”也建议纳入同一契约测试，防止以后误收紧。当前实现经上述独立探针已验证，补测不作为合并阻断。 |
| 上轮两条建议 | **不改** | 同日 CLI 串联在本归档重跑：`record` 后事件为 `F,R,F`，第二次 `ky resume` 退出 0 后为 `F,R,F,R`、锁存 false。无注册表而显式 `--store` 的 `day-plan record --json` 退出 0，含 `freeze_latch_warning`。两条均未因本提交回退；直接断言仍有维护价值，但没有必须本轮补的理由。 |
| 规格与安全登记措辞 | **建议改** | `contracts/freeze.md:89-90` 写“before touching the queue or the events”，实现会先读取队列与事件、计算方案，之后才拒绝；建议明确写“before **writing** the queue or events”。`docs/安全风险登记.md` S9 已正确补入“不同文件名可双双发布并使读取失败”，但同一行“部分防护”栏仍笼统写“撞号时报序号已被占用”，应限定为“**同名目标**撞号”。均是文档精度问题。 |

## 安全登记

本提交没有引入新的安全问题。第 125 轮 S9 的并发探针仍成立：两个写者若同时取得同一序号、但事件类型或日期不同，`os.link` 的目标文件名不同，可双双发布；之后读取因重复序号失败，需人工修复。触发条件是两个进程在取序号与发布之间恰好交错；影响与跨进程锁或纯序号原子占位的修法已记录到 `docs/安全风险登记.md` S9。依本轮威胁模型不计入结论。S10 的无注册表锁存例外也仍按原决策保留。

## 结论

**PASS。** 第 125 轮唯一“必须改”已关闭；原输入与三个指定边界均按规格运行。上述补测及措辞均为建议，不阻断本次修复。
