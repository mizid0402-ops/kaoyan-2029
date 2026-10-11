# WP-G2a CLI 小项实现报告

## 落点与实现

- `ky/__main__.py:232` 将原 preflight 主体保留为 `_preflight_main`；`ky/__main__.py:1337` 的 `SUBCOMMANDS` 为唯一入口表，键是命令名，值是入口函数和一行说明。顶层帮助与命令分派均读取该表。仅首参数是 `-h` / `--help` 时显示帮助；其他参数沿用既有 preflight 解析路径。
- `ky/projection/serve.py:67` 在数据库存在检查之后、调用 Datasette 之前打印数据库路径、访问 URL 和 Ctrl+C 提示。host 含冒号时用方括号包围。
- `ky/__main__.py:983` 的 record 分支区分 `find_workspace` 与 `load_workspace`：前者失败记录为“未找到”，后者失败保留原始契约错误。已解析的工作区对象或错误状态供冻结锁存和出题建议共用，不再为出题再次发现/加载。
- `tests/test_cli.py:298`、`:308`、`:1087`、`:1146` 覆盖动态命令表帮助、固定基线字节对照、注册表错误消息分类和单次查找/加载。
- `tests/test_projection_service.py:55`、`:78` patch Datasette 入口，检查 IPv4 地址行与 IPv6 方括号。
- README 中没有现存 `-h` / serve 用法行，因此未改 README。

## 固定基线对照覆盖

测试从固定提交 `0c3b3e54929a9b72aa740f410b7302e51b646f41` 运行 `git show`，并断言旧源码含 `workspace_not_found = (`，再将旧源码作为临时入口执行。新旧进程使用相同参数、同一临时工作目录和同一组输入文件，比较原始 stdout、stderr 字节及退出码。

- `preflight -h`、`--date 2026-09-15 -h`、无参数 preflight、未知子命令、未知参数。
- record 找不到注册表（当前目录向上搜索无结果、`--workspace` 指向缺失文件）和无效注册表（YAML 无效），分别比较文本与 JSON 输出。每次运行前重置可变队列和日计划存储。
- 另有错误消息本身包含 `not found` 的契约探针，断言按加载阶段归类为“出题查询失败”，并且查找/加载各调用一次。

## 撤回对应修改验证

每项均临时撤回实现片段，执行对应测试后立即恢复：

- 顶层帮助：将 `main` 的首参数帮助条件临时改为 `if False and ...`；运行 `py -3.12 -m unittest tests.test_cli.CliTopLevelHelpTest`。实测 `FAILED (failures=2)`，`-h` 和 `--help` 均因 `ledger` 未出现在输出中失败；随后恢复条件。
- serve 地址：临时删除打印地址代码；运行 `py -3.12 -m unittest tests.test_projection_service.ProjectionServiceTest.test_serve_prints_database_and_ipv4_address_before_starting tests.test_projection_service.ProjectionServiceTest.test_serve_brackets_ipv6_host_in_printed_address`。实测 `FAILED (failures=2)`，一项因 stdout 为空不等于地址行失败，另一项因找不到 `http://[::1]:8123/` 失败；随后恢复打印代码。
- record 分类与单次读取：临时恢复基线中的 `_discovered_workspace` 加重复查找/加载及错误文本判断；运行 `py -3.12 -m unittest tests.test_cli.DayPlanCliTest.test_record_classifies_registry_by_lookup_stage_not_error_text`。实测 `FAILED (failures=1)`，`find.call_count` 为 2（期望 1）；随后恢复新逻辑。

## 验收

命令：

```text
py -3.12 -m unittest tests.test_cli tests.test_projection_service tests.contract.test_freeze_port
```

结果：`Ran 63 tests in 33.665s`，`OK`。另 `git diff --check` 无输出；对本轮改动文件执行 `rg -n '\?\?\?' ...` 无命中。全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 建议

- 当前 argparse 本身没有为部分子命令设置 description；顶层表为这些命令提供了对应现有行为的英文短说明。以后若补齐各自 argparse description，可同步顶层表说明。
- 本轮未发现需要扩大到其他模块的验证范围。
