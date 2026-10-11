# 评审：第 124 轮冻结 / 恢复有序事件 + WP-R2 `ky resume`（从未审过）

遵守 `AGENTS.md`（不跑全量；严重度按"评审严重度与威胁模型"一节：只有日常正常使用会碰到的问题算"必须改"，
安全类写进报告单独一节"安全登记"，不算必须改）。运行用 `git archive <提交>`（照前几轮补原始资料与 `products` 空目录）。

## 范围

1. **第 124 轮修复**：合并提交 `08d416a`（实现提交 `794a079`，luna）。
   依据：你第 123 轮报告 `review/rounds/round-123-review-sol-out.md` 的两个"必须改"；任务书
   `review/rounds/round-124-freeze-records-task.md`；实现者报告 `review/rounds/round-124-freeze-records-luna.md`；
   规格 `contracts/freeze.md`；`docs/阶段2.5-接缝收口.md` D11（已改为序号事件）。
   决策者合并时改了：**删掉实现者自加的跨进程序号锁 `.sequence.lock`（`msvcrt` / `fcntl`）与发布后的身份复查**——
   按新威胁模型，两个写者同时取到同一序号属安全登记，`os.link` 不覆盖发布已保证不丢数据、后者报"序号已被占用，请重试"。可以反驳。
2. **WP-R2 `ky resume`**：实现提交 `61e1a5c`、合并 `a1ba242`（luna 第 119 轮，报告 `review/rounds/round-119-wp-r2-luna.md`）。
   决策者审查时改了：有锁存但无逾期项时，真实运行也写恢复事件（否则追上积压后锁存永远解不开；也覆盖"队列已写、恢复记录写失败"后重跑）。

## 请查

1. 你第 123 轮的同日复现：冻结 → 同日 resume → 再达阈值 → `day-plan record` 写出第二条冻结事件、preflight `latched: true`、submit 拒绝 → 再 `ky resume` 解除。
   另查多轮交替、R 序号在后但日期早于 F、事件文件名与内容不一致 / 放错目录 / 重复序号。
2. `latch_active(events)` 的规则（序号在后且日期 ≥ 冻结日）是否与 D11 用户选项"手动重启"一致；有没有正常使用下会误解冻或永远解不开的序列
   （例如 `--date` 回填较早日期的 `record` / `resume`）。
3. `ky resume`（D11 细则）：遗忘分层（逾期天数 > 当前间隔）、`reset_for_relearning` 不计 lapse 不改 ease、按每日常规配额摊开（阶段配额 / 软配额、当天已到期项先占）、
   366 天放不下的处理、不拉长任何间隔、`--dry-run` 不写、队列先写后写恢复事件、同日重复运行。
4. `day-plan record` 在找不到可用注册表时的提示（文本与 JSON 的 `freeze_latch_warning`）；有注册表时输出不变。
5. 新测试撤实现是否变红（决策者已验：锁存忽略序号、`os.link` 改回 `os.replace` 两处均变红）。

## 产物

`review/rounds/round-125-review-sol-out.md`：每项"必须改 / 建议改 / 不改"附可复现输入；单独一节"安全登记"（现象、触发条件、影响、可能的修法）；
最后 PASS / FAIL（安全登记不影响结论）。只写这一个文件。
