# 第 158 轮 · WP-R3：日常输入健壮性修复（Opus 实现报告）

执行者：Claude Opus 5.5（实现者）；日期：2026-09-27；基线提交：`c3641f2`；
worktree：`F:\workspace\kaoyan-ai-system\.claude\worktrees\agent-a88385073cf841b8d`，
分支 `worktree-agent-a88385073cf841b8d`。未提交。

来源：第 152 轮 S1 / S2（台账）、第 153 轮 D2 / D3（日计划）、第 151 轮 §5（配置非字符串键）。

## 1. 改动文件

| 文件 | 改动 |
|---|---|
| `ky/ledger/material.py` | 新增 `_read_ledger_yaml`：读文件失败（含非 UTF-8）→ `LedgerError`；解析改用 `ky.models.load_yaml_text`（严格加载器，拒绝重复键），其 `ContractError` 原样转为 `LedgerError(message, path)` |
| `ky/storage/day_plan_store.py` | `parse_day_plan` 拆出 `_plan_day` / `_plan_int` / `_plan_quantity` / `_plan_subject_minutes` 四个辅助 |
| `ky/models.py` | `_reject_unknown_keys`：非字符串键先报，路径一律为字符串 |
| `contracts/day_plan_store.md` | §1 末段、§3 `parse_day_plan` 三条、§10 D2 / D3 两行 |
| `tests/test_ledger.py` | 新类 `LedgerFileReadingTest`（2 条） |
| `tests/test_ledger_cli.py` | `test_a_non_utf8_ledger_exits_two_without_a_traceback` |
| `tests/test_day_plan_store.py` | 新类 `HandWrittenPlanInputTest`（5 条） |
| `tests/test_cli.py` | `DayPlanCliTest` 加 2 条 + `_submit` 辅助；模块顶部加 `from datetime import date` |
| `tests/test_contracts.py` | `test_non_string_keys_are_contract_errors_with_a_text_path` |

`ky/__main__.py` 未改：三处 CLI 已经捕获 `ContractError` / `LedgerError` 并退出 2，
只是之前异常没被转换成这两类。

## 2. 逐条修复（前 / 后）

### 2.1 台账非 UTF-8（S1，M2）

- **前**：`load_ledger` 直接 `read_text(encoding="utf-8")`，GBK 文件抛未包装的 `UnicodeDecodeError`；
  `ky ledger` 以 traceback 退出（退出码 1）。
- **后**：`LedgerError("cannot read YAML: <原因>", <文件 POSIX 路径>)`；`ky ledger` 输出
  `ledger violation: <路径>: cannot read YAML: ...`，stdout 空，退出 2。措辞与
  `ky.models._read_yaml_file`（配置 / 注册表）一致；同时捕获 `OSError`（与该函数相同）。
- `.path` 取文件路径而非第 152 轮建议的空串：任务书要求"带路径"，且与 YAML 语法错误同形。

### 2.2 台账重复键（S2，M2）

- **前**：`yaml.safe_load` 后者覆盖，手写两个 `review_index:` / `rights:` 时前一个静默丢失。
- **后**：`LedgerError("duplicate field 'review_index' (line N); YAML would silently keep only the
  last one", <文件路径>)`，与配置、注册表、知识点文件同一套严格加载器。
- 合法输入不变：真实 `data/materials.yaml` 用旧 `yaml.safe_load` 与新 `load_yaml_text` 解析结果
  相等（实测 `True`）。

**需决策者知悉（AGENTS 第 13 条相关）**：YAML **语法错误**的消息前缀 `invalid YAML: `、`.path`
不变，但冒号后的解析器原文会变——严格加载器用 libyaml（`CSafeLoader`），旧代码用纯 Python
`SafeLoader`，两者措辞不同，例如：

```
旧 invalid YAML: mapping values are not allowed here / in "<unicode string>", line 1, column 5: ...
新 invalid YAML: mapping values are not allowed in this context / in "<unicode string>", line 1, column 5
```

这是任务书"改用 `ky.models` 严格加载器"的直接后果，与仓库其他 YAML 文件的报错已经一致；
没有删掉任何提示语或表格。若要逐字保留旧措辞，只能给台账单独用纯 Python 严格加载器，不建议。

### 2.3 日计划日期（D2，M11 / M13）

决定：**接受**未加引号的 YAML 日期。理由：同一个存储里的完成事件（`ky.schedule.completion._parse_date`）、
M26 可用时间（`contracts/availability.md`）与路线计划都接受日期标量；M19 提案与 `day-plan submit --plan`
都经 `load_yaml_text` 读入，手写 `day: 2026-09-15` 必然得到 `date` 对象。

- **前**：`day: 2026-09-15` → `StorageError`（`expected an ISO date`，退出 2）；
  `day: "2026-13-01"` → `ValueError: month must be in 1..12`（traceback，退出 1）。
- **后**：日期标量按该日接受，结果与字符串 `"2026-09-15"` 完全相同；非法日期字符串 →
  `StorageError("expected an ISO date (YYYY-MM-DD), got '2026-13-01'", "<path>.day")`，退出 2。
- 不变：合法字符串仍原样交给 `date.fromisoformat`；`datetime`（`day: 2026-09-15 08:00`）、`null`、
  数字等非字符串仍是原消息 `expected an ISO date (YYYY-MM-DD)`（`datetime` 不是"某一天"，
  放行会让 `isoformat()` 带上时刻写进文件）。
- 存储自己写出的文件 `day` 仍是带引号的 ISO 字符串，读回路径不受影响。

### 2.4 日计划数值类型（D3，M11 / M13）

- **前**：`available_minutes: "120"` → `check_invariants` 抛 `TypeError`（traceback）；
  `True` / `30.0` / `30.5` 被当作数字接受并落盘。
- **后**：六个数值字段（`available_minutes`、`knowledge_minutes`、`vocab_minutes`、`vocab_new_items`、
  `phrase_minutes`、`backlog_minutes`）与 `subject_minutes` 的每个值必须是 `int`（布尔不算）；
  否则 `StorageError("expected an integer, got <类型>", "<path>.<字段>")` 或
  `"<path>.subject_minutes.<科目>"`，退出 2。措辞照抄 `ky.models._require_int`。
- 不变：缺省 0；负数仍由 `check_invariants` 报（解析只管类型）；报错顺序仍是
  未知键 → schema → `day` → `subject_minutes` 非映射，新检查排在其后。
- 影响面：`DayPlan` 在仓库内只由 `parse_day_plan` 构造；`write_day_plan` 写后重读也经此函数，
  所以浮点分钟也写不进去了。主仓库当前没有已存储的日计划文件（`*--v*.yaml` 为空），
  不存在"旧文件因新检查读不出"的问题。

### 2.5 配置非字符串键（第 151 轮 §5，M8）

- **前**：根层或科目映射同时有 `1: x` 与拼错的键 → 排序 int 与 str 抛 `TypeError`（traceback）；
  只有一个 `1: x` 时 `ContractError.path` 是整数 `1`。
- **后**：非字符串键先报（它不可能是合法字段），消息仍是原来的 `unknown field 1`，
  路径为字符串：根层 `"1"`，科目层 `"subjects[1].2"`。全是字符串键时逻辑与输出完全不变。
- `_reject_unknown_keys` 也用于复习条目、`schedule`、`review_policy` 与 reviews 根层，同样受益。

## 3. 回退验证（每条修复各自变红）

方法：scratchpad 脚本（不在仓库）对实现文件做一处替换（先断言替换点唯一），设
`PYTHONDONTWRITEBYTECODE=1`、去掉 `KY_WORKSPACE`，只跑对应测试；先确认基线绿、变异后红，
`finally` 写回原字节并核对 SHA-256。

| 修复 | 回退（文件：替换） | 目标测试 | 结果 | 还原 |
|---|---|---|---|---|
| S1 | material：`except (OSError, UnicodeError)` → `except OSError` | 台账 GBK 单测 + CLI 退出 2 | FAILED (failures=1, errors=1) | True |
| S2 | material：`load_yaml_text(...)` → `yaml.safe_load(text)` | `test_a_key_written_twice_is_rejected_not_last_wins` | FAILED (failures=1) | True |
| D2 日期标量 | store：删去 `date` 分支 | 存储单测 + CLI 提交 | FAILED (failures=1, errors=1) | True |
| D2 边界 | store：`date` 分支不再排除 `datetime` | `test_a_datetime_day_is_still_rejected` | FAILED (failures=1) | True |
| D2 非法日期 | store：`except ValueError` → `except TypeError` | 存储单测 + CLI 退出 2 | FAILED (failures=1, errors=1) | True |
| D3 类型 | store：`_plan_int` 判断改 `if False:` | 字符串 / 布尔浮点单测 + CLI | FAILED (failures=10) | True |
| D3 布尔 | store：去掉 `isinstance(value, bool) or` | `test_booleans_and_floats_are_not_stored_as_minutes` | FAILED (failures=2) | True |
| D3 分科值 | store：`subject_minutes` 值不再校验 | 同上 | FAILED (failures=3) | True |
| 配置排序 | models：`non_string or sorted(...)` → `sorted(...)` | `test_non_string_keys_are_contract_errors_with_a_text_path` | FAILED (errors=2) | True |
| 配置路径 | models：`str(key)` → `key` | 同上 | FAILED (failures=2) | True |

另做一次整体回退：三个实现文件换成 `git show c3641f2:<文件>`，只跑 11 条新测试 →
`FAILED (failures=15, errors=5)`；唯一通过的是 `test_a_datetime_day_is_still_rejected`（它钉的是
旧行为的保留，由上表"D2 边界"变异证明有效）。三个文件还原后 SHA-256 与改后一致。

## 4. 测试输出

命令（任务书点名，未跑其他模块）：

```
py -3.12 -m unittest tests.test_ledger tests.test_ledger_cli tests.test_day_plan_store tests.test_cli tests.test_contracts
----------------------------------------------------------------------
Ran 177 tests in 39.322s

OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

怀疑受影响、未点名的模块（请决策者在全量里留意）：
`tests.contract.test_day_plan_store_port`（`parse_day_plan` 缺省与路径；已读过，无与新行为冲突的断言）、
`tests.contract.test_planner_port`（M19 提案同经 `parse_day_plan`）、
`tests.contract.test_ledger_port` 与 `tests.contract.test_config_port`（只在主仓库、未跟踪；已读相关断言：
`test_file_errors_are_ledger_errors` 只查 `.path`，不受 2.2 措辞变化影响）、`tests.test_citation_gate`。

自检：新增 / 改动行无超过 100 字符；改动文件无连续三个问号；`tests/test_cli.py` 曾被 Python 文本模式
写成 CRLF，已改回 LF，`git diff --stat` 只剩实际新增的 35 行。数据量字面量：无；台账测试的科目取自
夹具 `local_material()["subjects"]`，CLI 测试沿用 `test_subjects()`（读真实台账）。

## 5. 规格更新

### 5.1 `contracts/day_plan_store.md`（已在本 worktree 修改）

§1 末段"类型不检查"改为指向 §3；§3 `day` 与数值字段两条按 2.3 / 2.4 重写；§10 D2 / D3 两行
改为"**WP-R3 已修**"并指向回归测试。

### 5.2 `contracts/ledger.md`（不在本 worktree，替换文本如下）

§2 第 38 行，把

```
（`<source>.items[i].resource_id`）。YAML 重复键**不**拒绝（`yaml.safe_load` 后者覆盖，见限制 §11）。
```

换成

```
（`<source>.items[i].resource_id`）。YAML 任一层映射的重复键以 `LedgerError` 拒绝
（`duplicate field '<键>' (line N); ...`，`.path` 为文件 POSIX 路径），与 `ky.models.load_yaml_text`
同一个严格加载器（WP-R3）。
```

§9 错误表，把

```
| 文件不是合法 UTF-8 | 当前抛 `UnicodeDecodeError`（未包装，见 §11） |
```

换成

```
| 文件读取失败或不是合法 UTF-8 | `LedgerError("cannot read YAML: ...")`，`.path` 为文件 POSIX 路径（WP-R3） |
| 任一层映射出现重复键 | `LedgerError("duplicate field '<键>' (line N); ...")`，`.path` 为文件 POSIX 路径（WP-R3） |
```

§11 已知限制，删去前两条：

```
- 台账文件非 UTF-8 时抛未包装的 `UnicodeDecodeError`，CLI 以 traceback 退出而非退出 2。
- YAML 重复键不拒绝（与工作区注册表、`ky.models.load_yaml_text` 的做法不同）。
```

换成一条：

```
- （WP-R3 已修）非 UTF-8 台账与 YAML 重复键原先分别抛 traceback / 后者覆盖，现为 `LedgerError`，
  `ky ledger` 退出 2。YAML 语法错误的解析器原文随 libyaml 措辞，前缀 `invalid YAML: ` 不变。
```

另：第 152 轮报告 §3 D6 行末"非 UTF-8 台账抛 traceback（退出 1）"已不成立，汇总时可注明"WP-R3 已修"。

### 5.3 `contracts/config.md`（不在本 worktree，替换文本如下）

§3 第 127–128 行，把

```
未知键：把该层多余的键排序后报告第一个，路径为 `<层路径>.<键>`（根层直接是键名）。拼错的
字段（`min_daily_minute`）因此报错，而不是被当成缺省值。
```

换成

```
未知键：该层若有非字符串键（YAML `1: x`），先按出现顺序报告第一个；否则把多余的键排序后报告
第一个。消息为 `unknown field <键 repr>`，路径为 `<层路径>.<键>`（根层直接是键名），一律是字符串
（WP-R3；原先混合类型排序抛 `TypeError`，单个非字符串键时路径是整数）。拼错的字段
（`min_daily_minute`）因此报错，而不是被当成缺省值。
```

config.md 没有"出入"一节；第 151 轮报告 §5 的安全登记条目汇入 `docs/安全风险登记.md` 时可标"WP-R3 已修"。

## 6. 建议（未做，由决策者裁定）

1. `ky/storage/day_plan_store.py` 的 `_unknown` 与 `ky/ledger/material.py` 的 `_unknown` 有同样的
   `sorted(set(node) - allowed)`：手写日计划 / 台账里出现 `1: x` 加一个拼错字段时仍会 `TypeError`。
   属同类畸形输入，本包只修了任务书点名的配置；如要统一，可照 2.5 的写法各改一行并补一条测试。
2. `parse_day_plan` 的 `notes` 不检查类型（`notes: 123` 会原样落盘为整数）；日常少见，登记即可。
