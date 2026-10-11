# 任务书：技术债包 B 返工 —— sol61 第 204 轮 M1–M5 与 m1（窗口 `luna-a` 续做）

sol61 第 204 轮判 **FAIL**：`review/rounds/round-204-baseline-harness-review-sol61.md`，先读全文（每条都有复现输入与出处）。
harness、保留实例、四个契约模块的辅助收敛**已确认成立，不要动**。**不要恢复**已删除的 8 个对照文件；只把缺失的**现有行为断言**迁到正规模块，
写成不依赖旧版的直接断言（同样的输入、同样的期望，从 `git show f52b8f6:<已删文件>` 取原输入与原期望）。`ky/`、`tools/` 不改。

## 要补（去向由 sol 204 给出，按它的修法做）

1. **M1** → `tests/test_cli.py`：`record-question-partial-skip`（两条 fluent / unchecked 复习，第一科有登记索引、第二科无）的 JSON 四项直接断言
   （候选组恰一组、`review_id`、候选非空、同时含 `check_question_suggestions_skipped`）与文本"出题查询失败"提示。
2. **M2** → `tests/test_cli.py`：`record-freeze-write-failure`（冻结写入抛 `StorageError`：退出 2、**不写**完成事件、无 traceback）与
   `record-advance-failure`（队列推进抛 `ContractError`：退出 2、完成事件**已写入**、无 traceback）两种故障阶段。故障注入照旧 injector 的做法（替换对应函数）。
3. **M3** → `tests/test_round24_weighted_tree.py`、`tests/test_round29_tree_split.py`：两校验器 `main()` 的成功（退出 0）与错误（round24 第一节点
   `status='approved'`、round29 第一条 `source_support=0.42`：退出 1、stdout 含对应诊断）；以及 round24 双错误输入（`approved` + `sources=[]`）的
   `errors[0..3]` 固定期望与 CLI 退出 1、两条输出诊断。
4. **M4** → `tests/test_citation_gate.py`：六个知识点 / 五份台账材料、strict 模式下的**完整六项 reason 列表及其次序**。
5. **M5** → `tests/contract/test_material_restore_port.py`：原多行 check-only 输入的八行状态期望（already_verified、existing_mismatch、invalid_url、
   storage_not_permitted、missing_url、invalid_path、reference_only、needs_download）。
6. **m1**：`tests/contract/test_index_tree_verifiers.py` 两个方法改名，去掉 `fixed_baseline` / `fixed_cli` 字样，名字说明它验证的当前输入变体与诊断。

每条迁完后做一次定点变异证明它真能抓住（sol 204 已给出 M1 与 M3 的变异；M2、M4、M5 你自选一处），报告写命令与结果。
另外，请把 sol 204"不改与去向抽查"一节之外、你第 203 轮去向表里**其余标为"已有等价"的条目再自查一遍**：打开被指向的方法，确认同输入同期望；
不成立的照上面方式补迁，报告列出自查结果。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_cli tests.test_round24_weighted_tree tests.test_round29_tree_split tests.test_citation_gate tests.contract.test_material_restore_port tests.contract.test_index_tree_verifiers tests.test_baseline_harness tests.contract.test_state_snapshot_counts_baseline
```

## 报告

`review/rounds/round-205-baseline-harness-gaps-luna.md`：逐条迁移（从哪取的输入与期望 → 新测试名）、变异命令与结果、自查结果表、验收输出原文。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文只用 `apply_patch`，写完查 `???`。
