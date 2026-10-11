# 任务书：WP-G3c 拆分 CLI 的两个超长函数（D7，M14 `ky/__main__.py`）

你是固定窗口 `luna-a`，做过 G3a（`load_workspace`）、G3b（`ky/models.py` 两个校验器）。本包同样是**行为逐字节不变**的拆分。
先读仓库根 `AGENTS.md`，再读 `ky/__main__.py` 的 `_preflight_main`（约 178 行）与 `day_plan_main`（约 240 行，含 submit / record 两个分支）、`tests/test_cli.py`、`contracts/planner_port.md`、`contracts/freeze.md`。
**吸取 G3b 的两条教训**：①测试辅助函数给嵌套路径赋值时，列表下标不能用 `key not in node` 判断（那是成员判断）；②做"调换顺序看测试是否变红"的变异时设 `PYTHONDONTWRITEBYTECODE=1`，否则可能复用旧 `.pyc`。

在主仓库 `F:\workspace\kaoyan-ai-system` 工作，**只改 `ky/__main__.py` 里这两个函数（拆出私有辅助函数），新增一个对照测试文件**。别的窗口可能同时在做评审，不碰其他文件。
不改任何子命令的参数、输出、退出码；不改公开接口；不改 `SUBCOMMANDS` 表以外的其他函数。

## 要做的

- `_preflight_main` 拆成：参数与日期解析、`--usage` 读取、配置 / 队列 / 注册表加载、冻结判定、裁剪与预算、输出（JSON / 文本）等有名字的步骤函数。
- `day_plan_main` 拆成：参数解析与分派、`submit` 分支（计划来源解析、注册表与 availability、冻结门、写入、输出）、`record` 分支（注册表一次加载、完成事件解析、队列预检、冻结锁存、写入、队列推进、出题建议、输出）。
- 每个函数一件事、不超过约 60 行、嵌套不超过三层；**首报错误顺序、退出码、stdout / stderr 字节全部不变**。

## 测试（只写这一个）

`tests/test_cli_split_baseline.py`：`git show b867ae7:ky/__main__.py` 取旧版（断言取到的是旧版，例如旧 `day_plan_main` 超过 200 行），照 `tests/test_cli.py` 里已有的 `_legacy_cli_path` / `run_raw_ky` 方式把旧版当入口运行。
在系统临时目录按规则构造输入，新旧各跑一遍，逐字节比较 `(退出码, stdout, stderr)`，至少覆盖：
- preflight：正常、满载、违规（退出 2）、`--usage` 缺失 / 非 JSON / 非法值、无注册表、找到但无效的注册表、冻结（锁存与达阈值）、`--json` 与文本；
- `day-plan submit`：`--plan` 与 `--from-staging` 成功、过期输入包、冻结拒绝、指向 staging 的 `--plan` 拒绝、超手填上限；
- `day-plan record`：带 / 不带 `--review-store`、带 / 不带 `--store`、注册表找不到 / 无效 / 有效、需要核对出题、队列未推进的失败分支、`--json` 与文本。
每次运行前重置会被写的临时存储。不写死科目或数据量。撤修改验证：对调某个步骤函数的两次调用 → 变红（设 `PYTHONDONTWRITEBYTECODE=1`），报告写实际命令与结果。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_cli tests.test_cli_split_baseline tests.contract.test_freeze_port tests.contract.test_planner_port
```

## 报告

`review/rounds/round-144-wp-g3c-luna.md`：拆出的函数清单（名字、行数、职责）、对照覆盖的调用类别与数目、撤修改验证、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
