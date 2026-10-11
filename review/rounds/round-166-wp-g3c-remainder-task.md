# 任务书：WP-G3c 余项 — `ky/__main__.py` 剩余大函数拆分（窗口 `luna-a`）

你做过 WP-G3c（第 144 轮 + 第 149 轮返工，都已提交；第 150 轮 sol 复审判 FAIL 一项 `G3c-M5`，
已在 `df9cd3b` 修好，`review/rounds/round-157-g3c-m5-opus.md` 是那次修复的报告）。
本轮拆剩下的六个大函数，**它们都还没被拆过**。

先读仓库根 `AGENTS.md`，再读 `review/rounds/round-150-review-sol-out.md` 的第二节（G3c 部分）
与 `review/rounds/round-149-wp-g3c-rework-task.md`（同样的拆分要求与验收写法）。
本轮只改 `ky/__main__.py` 和 `tests/test_cli_split_baseline.py`；另一个窗口（`luna-b`）在动
`tools/`，不要碰任何 `tools/` 下的文件。

## 背景：D7 的硬要求

`AGENTS.md` 最高原则：**一个函数做一件事**；超过约 60 行或需要三层以上嵌套时，拆成有名字的
辅助函数。现在 `ky/__main__.py`（1510 行）里超过 60 行的函数有六个，全部是"解析参数 → 读数据
→ 计算 → 打印"塞在一个函数里：

| 函数 | 行数 | 行号 |
|---|---|---|
| `ledger_main` | 115 | 613 |
| `month_close_main` | 95 | 1265 |
| `snapshot_main` | 90 | 745 |
| `route_main` | 83 | 860 |
| `resume_main` | 76 | 489 |
| `review_queue_main` | 74 | 1362 |

**本轮的产出就是把这六个拆开**，每个都按"参数解析 / 取数据 / 计算 / 打印"的边界切成有名字的
私有辅助，函数名说清它做什么（照 `_day_plan_record_preflight` / `_day_plan_record_freeze` /
`_day_plan_record_write` 那批已经拆好的写法命名）。

## 输出必须逐字节不变

这是**纯重构**：拆完之后，同样的输入下，六个子命令的 `(退出码, stdout, stderr)` 必须与现在
**逐字节相同**，唯一允许的差异是本任务书明文要求的（本轮没有要求任何输出变化）。

- 先取本轮改动前的提交做基线：**现在 `HEAD` 是 `24371ee`**，把 `BASELINE_COMMIT` 定成它
  （不是 `b867ae7`；那个基线已经被第 149 轮用掉了，且它是 G3c 拆分**之前**的版本，对不上）。
  照 `tests/test_cli_split_baseline.py:27,505` 现有写法：用
  `git show <commit>:ky/__main__.py` 取旧版文件，**断言取到的是旧版**（例如断言里面的旧函数
  确实是长实现），再在同一份输入上比较两版 CLI 的三元组。
- `AGENTS.md` 第 12a 条：**基线必须固定到提交哈希，不得用 `HEAD`**。测试通过、提交之后
  `HEAD` 变成新版，对照就变成"新版对新版"了。所以基线写死 `24371ee`。
- 不要用正则抹掉任何整段文字来"归一化"；按原始字节比较。

## 怎么拆

1. **`ledger_main`（115 行）**：注意它开头有一段自己写的 utf-8 重配置循环（`for stream in
   (sys.stdout, sys.stderr): reconfigure = getattr(...)`），而文件里已经有 `_reconfigure_streams_utf8()`
   （第 730 行）做同一件事。**不要**顺手改成调用那个函数——那是行为等价但 diff 变大的改动，
   本轮不做；保留原样搬进拆出的步骤里就行（可写进报告的"建议"一节）。
   拆分点：`_ledger_parser()` / 取源与读数（现有 `_ledger_sources` 已经拆出去了）/ 计算
   `integrity`、`structurable`、`evidence_capable`、`summary` / **JSON 分支单独一个函数** /
   文本分支按"头部汇总 / 权利与能力清单 / 字节完整性"再拆两三个函数。
2. **`snapshot_main`（90 行）**：`_snapshot_parser()` / 解析三个日期参数（现有的
   `_parse_iso_date` 返回 `None` 时由调用方返回 3，保持这个退出码约定）/ 载入配置与
   `_snapshot_items` / `_snapshot_build` / `_snapshot_print_text`。JSON 分支只有一行
   `print(json.dumps(...))`，可以留在主函数里，不要为一行单开函数。
3. **`route_main`（83 行）**：先看清它有几个子动作（`submit` / `show`），**按子动作拆**，
   每个子动作一个函数，参数解析也分开；不要拆出只有一个调用点、只转发参数的函数
   （第 150 轮 sol 明确不喜欢"只转发的辅助函数"）。
4. **`resume_main`（76 行）**：里面的"有锁存但没有积压"分支（`if not plan.entries:`）是一整块
   独立语义，挑出来命名（例如 `_resume_without_backlog`），并保留它现在的顺序与返回码；
   注意 `latest_freeze > day` 的拒绝写逻辑（sol 125 修的）**必须在任何写入之前**，拆函数时
   不要把它挪到 `write_resume_record` 之后。
5. **`month_close_main`（95 行）**：参数解析 / 取 store 与配置 / 计算 `close_month` /
   打印。JSON 分支的 payload 是一大块字面量，可以留在一个 `_month_close_to_mapping(mc)` 里，
   但**保证字段名与顺序和现在完全一致**。
6. **`review_queue_main`（74 行）**：`check` 与 `migrate` 两个子动作本来就是一个 `if` 分叉，
   按子动作拆成两个函数；`migrate` 里"先校验后写、空链时只跳过写入"的顺序（sol 77 N1）
   保持不动。

**行长 ≤ 100 字符**；注释写"为什么"不写"做了什么"；引用决议 / 评审编号（D7、sol 150 等）。

## 不做的

- 不改任何输出文字、退出码、参数名、缺省值、错误消息。
- 不改 `ky/__main__.py` 以外的实现文件；不动 `tools/`。
- 不拆本轮表格之外的函数（`build_parser` 48 行、`_preflight_print_review_lists` 44 行等不在此列）。
- 不新增功能、不修 bug、不顺手改上面的 utf-8 重配置。
- 不跑全量测试（`AGENTS.md` 验证范围：全量由决策者提交前统一跑一次）。

## 测试（只写这些）

在 `tests/test_cli_split_baseline.py` 里**新增一个测试类**（例如
`CliG3cRemainderSplitBaselineTests`），照现有类的写法：

- 基线固定 `24371ee`，断言 `git show 24371ee:ky/__main__.py` 取到的旧函数确实是拆分前的长实现
  （对六个函数各断言一次行数下界即可，照现有 `test_old_..._is_pre_split` 的写法）。
- 对六个子命令各覆盖**成功路径 + 至少一个失败路径**，比较 `(退出码, stdout, stderr)` 原始字节。
  失败路径挑各自最有代表性的：`ledger` 用无效台账、`snapshot` 用缺失配置、`route` 用非法
  `revision`、`resume` 用早于未解除冻结的 `--date`（sol 125 那条，必须断言**没有写入**恢复记录）、
  `month-close` 用 `--month 13`、`review-queue migrate` 用未注册版本。JSON 与文本两种输出
  至少各覆盖一次。
- **撤修复验证**：把新拆出的某个步骤函数临时改成返回常量 / 调换两个相邻步骤的调用顺序，
  确认对照测试变红。设 `PYTHONDONTWRITEBYTECODE=1` 并清 `__pycache__`。

数据来源一律走注册表与已有夹具，不写死科目 ID / 年份 / 数据量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_cli tests.test_cli_split_baseline tests.test_ledger_cli tests.test_day_plan_store
```

## 报告

`review/rounds/round-166-wp-g3c-remainder-luna.md`：六个函数各自的拆分落点（拆出哪些函数、各自
职责一句话）；对照测试覆盖了哪些子命令与哪条失败路径；撤修复验证**实际跑了什么命令、实际结果**
（不要写"未观察到差异"了事）；验收输出原文。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。
含中文的文件**只用 `apply_patch` 编辑**，写完查 `???`（`rg -n '\?\?\?' <文件>`）。
