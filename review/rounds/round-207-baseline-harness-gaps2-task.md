# 任务书：技术债包 B 再返工 —— sol61 第 206 轮 R1–R3 与 m1 / m2（窗口 `luna-a` 续做）

报告 `review/rounds/round-206-baseline-harness-gaps-review-sol61.md`，先读全文（每条都有原输入出处与复现）。其余已确认的部分不要动；不恢复已删文件；`ky/`、`tools/` 不改。
所有新断言照 `git show f52b8f6:<已删文件>` 的原输入与原期望，写成不依赖旧版的直接断言。

## 要改

1. **R1**：`tests/test_cli.py::SnapshotCliTest.test_review_queue_migration_rejects_unregistered_source_version` 先按原输入建**合法空队列**
   （`ReviewShardStore(queue).write([])`），再运行 migrate；除退出码外断言诊断指向未登记来源版本 / mapping 路径拒绝（目标版本从注册表取，不写死年份）。
   顺带检查你第 205 轮自查新增的其它 3 个 CLI 用例有没有同类"被前置错误提前挡住"的假通过（各断言一次实际诊断）。
2. **R2**：对原 `test_models_split_baseline.py::_review_variants` / 配置变体、`test_workspace_split_baseline.py::_registry_variants` 两张变体表，
   **逐行**映射到现存直接断言（配置部分先对照 `tests/contract/test_config_port.py`，已有真等价的写明不迁）；没有等价的迁到对应正规契约模块
   （`tests/test_contracts.py` 的 ReviewItem 部分或 `tests/contract/test_review_progress_port.py`，workspace 进 `tests/contract/test_workspace.py`），保留原"成功 / ContractError"期望。
   至少包括 `review-type-revision`（`revision=True` 必须拒绝）与 workspace 逐必填顶层块缺失（`supplementary` / `products` / `settings` 可选，其余拒绝）。
   可以用表驱动 + `subTest` 写，别一行一个方法。报告给出逐行映射表。
3. **R3** → `tests/test_ledger.py`（或 `tests/contract/test_ledger_port.py`，照模块地图）：合法 local-file 材料分别把 `rights` 换成 `None`、`'wrong-type'`、`{}`，
   `validate_material(...)` 必须抛 `ValueError`；`{'unknown_right': True}` 已有同类保护，写明等价不迁。
4. **m1**：M4 的引用聚合测试改用原来的小型 raw 夹具字段（point 的 raw / manual、材料 unreviewed、unclear 材料 `may_be_structured=True`），或在报告写明差异与等价理由——优先前者。
5. **m2**：M2 两个故障测试再断言 stderr 含强制注入的错误标记（`forced freeze write error` / `forced advance failure`），防止夹具提前失败时假通过。

每条补上的断言做一次定点变异证明（R2 至少用 sol 206 的 `revision=True` 变异；R1 用"不建队列"反证），报告写命令与结果。
临时探针一律放系统临时目录，**不要**放进仓库（上一轮放在 `review/rounds/` 下再删）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_cli tests.test_contracts tests.contract.test_config_port tests.contract.test_review_progress_port tests.contract.test_workspace tests.test_ledger tests.contract.test_ledger_port tests.test_citation_gate
```

## 报告

`review/rounds/round-207-baseline-harness-gaps2-luna.md`：逐条改动、R2 逐行映射表、变异命令与结果、验收输出原文。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文只用 `apply_patch`，写完查 `???`。
