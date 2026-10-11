# 任务书：WP-G3g — `ky/storage/`、`ky/ledger/`、`ky/freeze/` 大函数拆分（窗口 `luna-c`）

你做过 WP-F 全线（F-a / F-b / F-c）。本轮按 D7 拆存储、台账、冻结三处的超长函数。
另外两个窗口在改别的目录：`luna-a` 在 `ky/__main__.py`（**未提交，别碰**）、
`luna-b` 在 `ky/schedule/`（**别碰**）。

先读仓库根 `AGENTS.md`（"最高原则"、"迁移 / 重构不得改变输出"两节）、
`review/rounds/round-166-wp-g3c-remainder-task.md`（上一批拆分的写法与验收标准，照它做）。

## 目标：把下面这些函数拆到 ≤ 约 60 行，每个辅助函数做一件事

| 文件 | 函数 | 行数 |
|---|---|---|
| `ky/storage/review_shards.py` | `_commit` | 114 |
| `ky/storage/day_plan_store.py` | `write_day_plan` | 63 |
| `ky/ledger/material.py` | `validate_material` | 131 |
| `ky/ledger/material.py` | `_load_rights` | 72 |
| `ky/ledger/citations.py` | `check_knowledge_point_citations` | 102 |
| `ky/freeze/resume.py` | `plan_resume` | 62 |
| `ky/acquisition/ledger_restore.py` | `restore_materials` | 66 |

外加：自己在 `ky/storage/`、`ky/ledger/`、`ky/freeze/`、`ky/projection/` 下扫一遍，
把其余超过 60 行的函数一并列出并拆（报告里给完整表）。

命名照 `ky/__main__.py` 已拆好的那批：`_<动作>_<对象>` 私有名，函数名说清做什么。
**不要**拆出只有一个调用点、只转发参数的函数。

重点提醒（这几处拆错会改变行为）：
- `ky/storage/review_shards.py::_commit`：**只写一次 / 不覆盖**的发布（`os.link` 语义）、
  临时文件身份复核、失败回滚只删自己发布的文件（sol 99/102 那批修复）必须原样保留。
- `ky/storage/day_plan_store.py::write_day_plan`：写入护栏顺序（含冻结检查在内）不变。
- `ky/ledger/material.py::validate_material`：字段校验顺序与错误 `.path` 不变；
  `_load_rights` 拆开时保持"缺失 / 类型错 / 未知键"三类的先后与消息。
- `ky/ledger/citations.py::check_knowledge_point_citations`：拒绝理由的**枚举与顺序**不变。
- `ky/freeze/resume.py::plan_resume`：按"逾期天数 > 当前间隔"分层与摊开的规则不变（D11）。
- `ky/acquisition/ledger_restore.py::restore_materials`：每行的处理顺序与状态名不变；
  注意 `--check` 不建临时目录、畸形 URL 在单条内处理（sol 164 修的三项）。

## 输出必须逐字节不变

**纯重构**：调用方可观察结果逐字节相同——返回值、打印、错误消息与 `.path`、异常类型。

- 基线**固定 `24371ee`**，用 `git show 24371ee:<文件>` 取旧版并**断言取到的是拆分前的长实现**
  （长度下界）。`AGENTS.md` 第 12a 条：固定提交哈希，**不得用 `HEAD`**。
- 至少为 `_commit`（`ky/storage/review_shards.py`）、`write_day_plan`、`validate_material`、
  `check_knowledge_point_citations`、`restore_materials` 各写一个固定基线对照测试
  （新增 `tests/contract/test_storage_ledger_split_baseline.py` 或按现有同名模块的组织方式）。
  同一组输入下比较返回值 / `to_mapping()` / 逐项结果对象。
- **已有测试不许改断言**：`tests/test_ledger.py`、`tests/test_ledger_cli.py`、
  `tests/test_day_plan_store.py`、`tests/test_review_queue_advance.py`、
  `tests/contract/test_material_restore_port.py`、`tests/contract/test_ledger_port.py`、
  `tests/contract/test_citation_gate_port.py`、`tests/contract/test_day_plan_store_port.py`
  必须原样通过。某个测试因拆分而失败 = 拆分错了。

## 不做的

- 不改输出文字、字段名、错误消息、状态名、排序、数值口径。
- 不修 bug、不新增功能。
- 不动上面三处目录以外的实现文件；不动 `tools/`；不动 `ky/schedule/` 与 `ky/__main__.py`。
- 不跑全量测试。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_ledger tests.test_ledger_cli tests.test_day_plan_store tests.test_review_queue_advance tests.contract.test_material_restore_port tests.contract.test_ledger_port tests.contract.test_citation_gate_port tests.contract.test_day_plan_store_port tests.contract.test_state_sources_port
```

## 报告

`review/rounds/round-169-wp-g3g-storage-ledger-luna.md`：每个文件拆出哪些辅助、各自职责一句话；
扫出的其余超长函数清单；对照测试覆盖了什么；**撤实现验证实际跑了什么命令、实际结果**
（设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`）；验收输出原文。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。
含中文的文件**只用 `apply_patch` 编辑**，写完查 `???`。
