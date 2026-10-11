# 任务书：WP-G3f — `ky/schedule/` 大函数拆分（窗口 `luna-b`）

你做过 WP-G2b（`tools/`）与 WP-F 相关包。本轮按 D7 拆 `ky/schedule/` 里剩下的超长函数。
另一个窗口（`luna-c`）在拆 `ky/ledger/`、`ky/storage/`、`ky/freeze/`；
第三个窗口（`luna-a`）刚交付了 `ky/__main__.py` 的拆分（**未提交**）。
**只改下面列出的 `ky/schedule/` 文件与 `tests/` 下对应测试**，不要碰别的目录。

先读仓库根 `AGENTS.md`（尤其"最高原则"、"迁移 / 重构不得改变输出"两节）、
`review/rounds/round-166-wp-g3c-remainder-task.md`（上一批拆分的写法与验收标准，照它做）。

## 目标：把下面这些函数拆到 ≤ 约 60 行，每个辅助函数做一件事

| 文件 | 函数 | 行数 |
|---|---|---|
| `ky/schedule/review_clip.py` | `select_daily_reviews` | 173 |
| `ky/schedule/monthly_close.py` | `close_month` | 120 |
| `ky/schedule/longitudinal.py` | `check_invariants` | 104 |
| `ky/schedule/state_snapshot.py` | `build_snapshot` | 93 |
| `ky/schedule/completion.py` | `parse_completion_event` | 68 |
| `ky/schedule/review_clip.py` | `_select_with_subject_quotas` | 62 |
| `ky/schedule/live_preview.py` 等其他 >60 行的函数（自己在 `ky/schedule/` 下扫一遍） | — | — |

命名照 `ky/__main__.py` 已经拆好的那批（`_preflight_*` / `_ledger_print_*`）：
用 `_<动作>_<对象>` 的私有名，函数名说清它做什么。
**不要**拆出只有一个调用点、只转发参数的函数。

重点提醒（这几处逻辑语义容易在拆开时走样，全部要保持原样）：
- `select_daily_reviews`：**先校验 `subject_review_quotas` 再做任何算术**（sol 114）；
  非配额路径与配额路径的两个选择循环要各自独立成函数；
  结尾的"会计不变量"断言（`expected - accounted`）必须保留在返回之前。
- `close_month`：**同一日期出现多份日计划时只算第一份、其余记为 violation**（不能求和）；
  去重后再按日期排序计算各总量。
- `check_invariants`：五条不变量逐条可读即可，**不要**合并成一个大循环里的 if 链；
  文档字符串里的条目编号与代码要对得上。
- `build_snapshot`：先是"数据源缺失"与"科目未在注册表登记"两道校验，再按科目循环取树/词库；
  显式 `tree_paths` / `vocab_db` 覆盖注册表的行为不变。
- `parse_completion_event`：字段校验顺序与错误路径不变（契约测试盯得很紧）。

## 输出必须逐字节不变

这是**纯重构**。拆完之后所有调用方的可观察结果必须与现在**逐字节相同**：
函数返回值、打印输出、错误消息与路径、异常类型。

- 基线：**固定 `24371ee`**（本批改动前的 master）。
  照 `tests/test_cli_split_baseline.py` 的写法用 `git show 24371ee:<文件>` 取旧版，
  **断言取到的确实是拆分前的长实现**（长度下界）。
  `AGENTS.md` 第 12a 条：**基线必须固定到提交哈希，不得用 `HEAD`**。
- 不需要为每个函数都写一个对照测试文件；但**你至少要为 `select_daily_reviews`、
  `close_month`、`check_invariants`、`build_snapshot` 各写一个固定基线对照测试**
  （新增 `tests/contract/test_schedule_split_baseline.py`，或按现有同名模块的组织方式），
  在同一组输入上比较返回值（对象用其 dataclass 字段 / `to_mapping()` 逐字节比较）。
- 已有测试**不许改断言**：`tests/test_review_scheduler.py`、`tests/test_monthly_close.py`、
  `tests/test_state_snapshot.py`、`tests/test_longitudinal.py`、`tests/test_completion.py`
  必须原样通过。如果某个测试因为拆分而失败，那是拆分错了，不是测试过时。

## 不做的

- 不改任何输出文字、字段名、错误消息、排序规则、数值口径。
- 不修 bug、不新增功能、不顺手改口径。
- 不动 `ky/schedule/` 以外的实现文件（除非某个测试文件必须跟着改，报告里说明）。
- 不跑全量测试。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_review_scheduler tests.test_monthly_close tests.test_state_snapshot tests.test_longitudinal tests.test_completion tests.contract.test_state_snapshot_counts_baseline tests.contract.test_state_snapshot_port tests.contract.test_review_clip_port
```

## 报告

`review/rounds/round-168-wp-g3f-schedule-luna.md`：每个函数拆出哪些辅助、各自职责一句话；
对照测试覆盖了什么；**撤实现验证实际跑了什么命令、实际结果**（把某个辅助函数改成返回常量或
调换两步顺序，确认对照测试变红，设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`）；
验收输出原文。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。
含中文的文件**只用 `apply_patch` 编辑**，写完查 `???`。
