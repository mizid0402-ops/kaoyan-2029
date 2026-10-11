# 第 243 轮任务书：WP-M28a 返工（gpt-6-luna，续 luna-a，同一 worktree `F:\workspace\kaoyan-wt-m28a`）

sol 第 242 轮评审 FAIL，报告：`F:\workspace\kaoyan-ai-system\review\rounds\round-242-m28a-review-sol61.md`。决策者已核实 A1–A4 都成立。

## 要改的

1. **A1**：`ky/pacing/port.py` 的 `build_report`、`ky/pacing/storage.py` 的 `_validate_report` 按职责拆成有名字的辅助函数（每个 ≤ 约 60 行），
   报告字段与字节行为不变（先用现有测试与一份拆分前生成的报告映射做对照）。
2. **A2**：既无 `--config` 也未登记 `settings.exam_config` → 契约错误退出 2（提示显式 `--config` 或登记该键），不拼接任何约定路径。
3. **A3**：`reference_minutes` 按规格 §3 = 周期内逐日 **M8 总分钟**（手填 > 课表 > 基数）之和，冻结日照算。
   装配层一次加载 `availability_for_workspace`、`timetable_for_workspace`、当前路线（`state.routes` 已登记时）及它们的原始字节摘要，传给纯计算；
   纯计算逐日调用 `ky.schedule.budget.resolve_day_budget`（本 worktree 的现有签名；复盘设置参数本包不存在，不要自己加）取总分钟。
   已登记的手填 / 课表文件缺失或无效 → 契约错误（fail-closed）。这些文件进入 `sources`，因此修改它们后重复运行会给出来源变化提示。
   `base` 字段仍按任务书暂用配置基数；在 `base.source_note` 里写清"基数按生成时的配置；路线与复盘设置的基数解析在 M28c 接上"。
4. **A4**：`sources` 的键一律是**工作区根相对的 POSIX 路径**：`state.plans` / `state.review_queue` / `state.routes` 端口返回的相对路径先拼上各自登记目录，再转成相对工作区根；
   摘要仍取同一次读取的原始字节，不重读文件。显式参数指向工作区外的文件（例如 `--config`）记为 `external:<绝对 POSIX 路径>`，不得伪装成根内同名文件。
5. 建议改里便宜的一并做：`report_to_mapping` 的 docstring 写准（浅拷贝）；`contracts/pacing_review.md` §3 报告字段表登记 `base.source_note`、`reference_source_note` 的确切形状，
   并写明 `reviews` / `due_next` 是**稀疏映射**（只列出现过的科目，缺行不等于 0）。

## 测试（只写这些）

A1 拆分前后同一输入的报告映射相同；A2 未登记配置退出 2 且不发布报告；A3 sol 报告的例子（半月周期、只有 10-01 手填 0 → 1680；课表一天 120→75 少计 45；
修改手填后重复运行出现来源变化提示；已登记手填文件缺失 → 退出 2）；A4 sol 报告的例子（`data/plans/...`、`data/queue/manifest.yaml` 与实际分片路径；工作区外 `--config` 记为 `external:`）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_pacing_port tests.contract.test_workspace tests.test_completion tests.test_cli
```

报告追加到同一 worktree 的 `review/rounds/round-234-m28a-report-luna.md` 末尾一节"第 243 轮返工"：逐条做法、测试输出原文、"全量：未跑"。不提交。
