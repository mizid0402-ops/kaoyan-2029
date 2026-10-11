# 任务书：B6 返工 —— sol 188 M1 与两条建议（窗口 `luna-b` 续做）

sol 第 188 轮判 **FAIL**，报告 `review/rounds/round-188-b6-rename-review-codex.md`，先读全文。运行时代码已确认正确，**不要改 `ky/`、`contracts/`**。

## 要改

1. **M1**：`docs/模块拆分与架构审查.md` 第 205 行 B6 条目——恢复 `git show d692365:docs/模块拆分与架构审查.md` 里的**原文一字不差**，
   在其**后面**另起一句注明："已处理（2026-09-29，用户决定）：配置键改名为 `default_daily_minutes`，旧键拒绝并提示改名；
   当天分钟由 M26 `resolve_daily_minutes` 决定，配置值只是回落值。"（措辞可微调，意思要全）。不删任何原有文字。
2. **建议 1**：`tests/contract/test_models_split_baseline.py::_compare_config` 的名字替换只作用于**旧版一侧**（异常文字与路径），
   新版一侧原样比较，使新版若重新输出 `total_daily_minutes` 能被发现。用 sol 188 的变异（新版 `_check_subject_minimums` 错误文字改回
   `exceeds total_daily_minutes`）确认该测试变红。
3. **建议 2**：`test_availability_port.py`、`test_planner_port.py`、`test_freeze_port.py` 的 `as_dataclass()` 给旧版的视图**用旧字段替换新字段**
   （不要新旧并存再折叠），证明固定基线收到的就是改名前的模型形状。
4. 更正 `review/rounds/round-185-b6-rename-luna.md` 里过时的 `git grep` 抄录（改为当前实际输出），或在本轮报告里说明。

## 撤实现验证

第 2 条的变异；第 3 条任选一个文件，让旧版视图漏掉旧字段，确认对应测试变红。报告写实际命令与结果，恢复后核对哈希。

## 不做的

不改 `ky/`、`contracts/`、其它文档；不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_models_split_baseline tests.contract.test_availability_port tests.contract.test_planner_port tests.contract.test_freeze_port tests.contract.test_config_port tests.test_contracts
```

## 报告

`review/rounds/round-190-b6-rename-fix-luna.md`。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。
不提交。含中文只用 `apply_patch`，写完查 `???`。
