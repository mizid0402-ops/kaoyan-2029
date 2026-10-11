# 返工：WP-G3c（窗口 `luna-a` 续做）

你上一轮（`review/rounds/round-144-wp-g3c-luna.md`，已提交 `8c86fbf`）的拆分没有观察到输出差异，但 sol 第 146 轮（`review/rounds/round-146-review-sol-out.md`，**全文照读，复现输入都在里面**）判 FAIL。
只改 `ky/__main__.py` 与 `tests/test_cli_split_baseline.py`；基线仍固定 `b867ae7`。做调换 / 替换变异时设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`。另一个窗口（`luna-b`）在改 `tools/`，不要碰。

## 必须改（sol 146 M1–M4）

1. **M1**：测试夹具的 `data/weights.json`、`indexes/questions.json` 要写成真正的 JSON；断言 `record-needs-question` 确实拿到候选（JSON 的候选非空、无 skip；文本模式确实打印了建议行），再与旧版逐字节对照。
2. **M2**：
   - 加"事件已写、队列推进失败"场景（新旧两版同样替换 `advance_review_queue` 使其抛契约错误），对照三元组并断言完成事件**已写入**；
   - 加"冻结锁存写入失败"场景（同样替换 `_latch_freeze_if_needed` 抛 `StorageError`），对照三元组并断言完成事件**未写入**；
   - 所有失败场景都断言完成事件文件是否存在，**冻结检查必须先于事件写入**（对调这两步 → 测试变红）。
3. **M3**：补 sol 列出的双错误组合（preflight：usage + 配置；submit：注册表 + 配置；record：配置 + 缺 done 文件，以及队列预检 + 冻结、完成事件解析 + review-store 等按主流程里**可独立调换的相邻步骤**逐对构造），和一个**冻结时的 JSON** preflight 场景。
   报告里列出主流程每一对可调换的相邻步骤，及抓住它的场景名（照 sol 146 M3 的表格）。
4. **M4**：把 `_day_plan_record_advance` 拆成"推进队列"（失败 → 退出 2）与"查询出题候选"（失败 → 记 skip 原因、继续）两个命名步骤，错误顺序与输出不变。

## 建议改（决策者要求一并做）

5. **S1**：步骤函数不要再"成功返回值 / 失败返回整数退出码"混用。用一个显式的小结构（例如私有 `dataclass` 携带 `exit_code` 或结果，或在步骤内抛一个私有异常、由 `day_plan_main` / `_preflight_main` 统一转成退出码与既有错误文字），去掉调用方的 `isinstance(..., int)` 分派。
   **输出与退出码逐字节不变**，由对照测试证明。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_cli tests.test_cli_split_baseline tests.contract.test_freeze_port tests.contract.test_planner_port
```

## 报告

`review/rounds/round-149-wp-g3c-rework-luna.md`：每项落点；相邻步骤调换表（每对 → 抓住它的场景，实际跑的结果）；新增场景清单；S1 的形状；验收输出。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
