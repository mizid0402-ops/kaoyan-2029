# 任务书：第 174 轮返工 —— sol 175 的 M1 / M2 / S1（窗口 `luna-c` 续做）

sol 第 175 轮判 **FAIL**，报告 `review/rounds/round-175-exam-index-synthetic-review-codex.md`，先读全文。
六个合成来源用例本身已确认正确；要改的只有新增的真实资料用例与两个缺题 / 多题用例的哈希同步。
仍然只改 `tests/contract/test_exam_index_port.py`；`luna-a` 在改 `tools/` 与 `tests/test_tools_split_baseline.py`，不要碰。

## 要改

1. **M1 恢复来源**：`test_real_raw_page_verifies_when_available` 缺资料时的 `require_path` 提示要写明恢复来源：
   被选登记记录的 `resource_id`，以及 `data/materials.yaml` 里该记录的 `storage.url`
   （或按 `tools/fetch_all_from_ledger.py` 从台账重取——去看这个工具的实际用法再写）。
   与同文件 `_copy_file(require_raw=True)` 的提示口径一致。
2. **M2 不写死年份**：去掉 `data/exam_questions/408_index_2026.json` 这一新增字面量。
   从工作区注册表（`reference.exam_indexes`）登记的索引里选：**每一个**答案来源在本地存在的登记索引都做一次
   `verify(...) == []`（`subTest` 按索引路径区分）；一个都没有时用 `require_path` 跳过，提示里列出被选记录与恢复来源。
   读注册表用 `ky.workspace` 的公开接口，不要自己解析 YAML 结构去猜键。
   已有的 `_clone_index` 等辅助里原本就有的字面量不在本轮范围，不动。
3. **S1**：`test_answer_reader_rejects_one_missing_question` / `..._extra_question` 在改合成页 DOM 之后，
   同步该临时来源的哈希及相关字段（台账、`provenance`、`locator`、`answer_sources`），使问题列表里
   **只剩**题号覆盖那一类错误；在测试里断言不再出现 `disk hash != index hash`。
   能复用 `_sync_synthetic_answer_source` 的哈希同步部分就复用（可以把它拆成"生成页"与"同步哈希"两个有名字的辅助）。

## 自证

- 主仓库跑验收命令；再在 `git archive HEAD`（不补原始资料）的系统临时目录里设 `GIT_DIR`、
  `PYTHONDONTWRITEBYTECODE=1` 跑同一模块，贴两次 `Ran …` 行与跳过原因原文；
  再设 `KY_REQUIRE_RESOURCES=1` 在归档里跑一次，确认真实资料用例变成失败。
- 撤实现验证：去掉第 3 条的哈希同步，确认新加的"不再出现 hash 错误"断言变红；报告写实际命令与结果，然后恢复。

## 不做的

不改被测代码、`tools/`、`ky/`、`data/`；不新增任务书未列的测试；不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_exam_index_port
```

## 报告

`review/rounds/round-176-exam-index-synthetic-fix-luna.md`：逐条写改了什么、两种环境的结果原文、撤实现验证的命令与结果。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文只用 `apply_patch`，写完查 `???`。
