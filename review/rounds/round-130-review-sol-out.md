# Round 130 Codex：WP-G2a CLI 小项评审

## 结论与验证范围

**FAIL：两项必须改。**审查固定提交 `2574199`，对照基线 `0c3b3e5`；命令和测试均在系统临时目录的两份 `git archive` 中运行。没有读取或改动主仓库工作区，除本报告外没有向仓库写文件；没有跑全量。

相关测试：`py -3.12 -m unittest tests.test_cli tests.test_projection_service` → **50 项 OK**；`py -3.12 -m unittest tests.contract.test_freeze_port` → **13 项 OK**（归档运行，`GIT_DIR` 指向固定仓库对象以供 `git show` 读取）。

| 项 | 意见 | 证据、复现与改法 |
| --- | --- | --- |
| G1 非新增入口的字节兼容 | **不改** | 在同一空临时工作目录，分别以两份归档作 `PYTHONPATH` 运行旧、新 `py -3.12 -m ky`，对比 `(退出码, stdout 原始字节, stderr 原始字节)`：无参数、未知命令、未知参数、`preflight -h`、`--date 2026-09-15 -h`，以及九个已登记子命令各自的 `-h` 和未知参数，共 **23 组调用，全部相同**。`tests/test_cli.py:31-45,314-337` 固定完整旧哈希 `0c3b3e54929a9b72aa740f410b7302e51b646f41`、断言旧源码含 `workspace_not_found = (`，然后比较三元组原始值，未作换行归一。测试只抽五组通用命令；本次另跑了全部子命令的帮助/错误探针。新顶层 `-h`/`--help` 由 `ky/__main__.py:1350-1365` 正确列出表内命令；仅首参数为帮助时拦截。 |
| G2 `record` 的输出、分类、冻结与出题 | **不改**（但受 M1 限制） | 在临时工作区构造有效、无效、缺失三种注册表，分别带/不带 `--store`、文本/JSON、带待核对复习；重置队列和完成事件后，用同一路径旧、新运行 **12 组，退出码与 stdout/stderr 原始字节均相同**。无效注册表按加载阶段报“出题查询失败”，缺失报“未找到工作区注册表”；冻结锁存和出题共用 `_optional_workspace` 返回的同一个对象（`ky/__main__.py:985,1027-1028,1054-1079`）。`tests/test_cli.py:1093-1188` 覆盖缺失/无效的文本与 JSON、以及错误文字恰含 `not found` 时仍按阶段分类。已撤回分类逻辑作定向验证：`test_record_classifies_registry_by_lookup_stage_not_error_text` 变红（1 failure）。该故意修正的畸形错误消息案例不应被解释为“所有可能的旧错误文字均逐字节不变”。 |
| M1 默认 `--store` 时注册表读两次 | **必须改** | 正常成功的 `day-plan record --workspace <有效注册表>` **省略** `--store` 时，`_plans_store_path` 经 `load_workspace` 取存储路径（`ky/__main__.py:180-184,977`），随后 `_optional_workspace` 经 `find_workspace`、`load_workspace` 再读一次（`:134-147,985`）。用 `unittest.mock.patch(..., wraps=...)` 在归档内运行一条有效、成功的带复习记录：无 `--store` 为 `exit 0 / load_workspace 2 次 / find_workspace 1 次`；有 `--store` 为 `exit 0 / load_workspace 1 次 / find_workspace 1 次`。这违背任务书“record 开头只查找、加载一次注册表”及 `AGENTS.md` 已知缺陷 2；现有单次读取测试只使用显式 `--store`（`tests/test_cli.py:1161-1188`），所以 63 项相关测试全绿仍漏掉它。最小修法：无 `--store` 分支继续用 `_load_workspace_for_default` 保留旧报错，从其返回的**同一 Workspace**取 `state.plans` 并传给冻结/出题；有 `--store` 分支沿用 `_optional_workspace`。补成功默认存储路径的调用次数断言及旧版字节对照。 |
| G3 `SUBCOMMANDS` 与默认 preflight | **建议改** | `ky/__main__.py:1329-1348` 的一张表确实同时用于显式分派与帮助；增加普通子命令只需登记一处。可是无子命令时 `:1368` 直接调用 `_preflight_main`，没有从 `SUBCOMMANDS["preflight"]` 取入口；日后替换表内 preflight 处理器会出现显式/缺省行为分叉。建议缺省分支也从表取入口，保留当前参数原样转交。当前实现与基线字节一致，故不阻断。帮助测试 `tests/test_cli.py:304-311` 只对整个输出做子串包含；例如删去 preflight 的表格行，尾部“不写子命令即 preflight”仍可能让该项通过，宜按行核对每个表项及用法提示。 |
| G4 `serve` 的地址格式和错误路径 | **不改**（但受 M2 限制） | `ky/projection/serve.py:59-69` 先确认数据库存在，再用 `host` 中有冒号则加方括号的规则输出地址。相关测试在 `tests/test_projection_service.py:55-95`：IPv4 断言整行，IPv6 断言 `http://[::1]:8123/`。独立执行 `--database <不存在文件>` 与 `--workspace <无效 YAML>`，均退出 2 且 stdout 为空。 |
| M2 `serve` 的地址行在重定向时不可见 | **必须改** | 在归档临时目录创建空 SQLite 文件、选择本机空闲端口，将 `py -3.12 -m ky.projection.serve --database <库> --port <端口>` 的 stdout/stderr 重定向至临时文件：确认 `127.0.0.1:<端口>` 已可连接且服务进程仍运行时，**stdout 文件为 0 字节**；终止进程后仍为 0 字节。`ky/projection/serve.py:66-69` 的 `print` 缺 `flush=True`，管道/日志文件为块缓冲，地址在常见的后台启动或日志捕获方式下没有出现。最小修法为 `print(..., flush=True)`；补一个子进程启动、端口就绪前后检查已能读到地址行的回归测试。现有 `StringIO` patch 测试只检查函数返回后的字符串，撤掉刷新仍绿，不能锁住该缺陷。 |
| G5 测试撤回检查及文档 | **建议改** | 在第三份临时归档逐项撤回顶层帮助判断、恢复按 `not found` 文字分类、抑制 serve 地址打印，再各跑对应单条测试，分别得到 **2、1、1 个 failure**，证明三条主要新测试能因对应回退变红。缺省 `--store` 双读与 stdout 缓冲则没有测试覆盖，应随 M1/M2 补。`docs/前端设计-范围与待定.md:145` 仍写“`serve.py` 不打印访问地址”，现与实际功能相反；建议同步说明。 |

## 安全登记

- **S1 注册表两次读取的交错窗口**：只有另一个进程恰在 M1 所述两次读取之间改写有效注册表时，默认 `--store` 可能把完成事件写到旧 `state.plans`，却按新注册表的位置写冻结事件。触发条件是精确并发交错，按本仓库个人本机威胁模型单列登记；复用同一个 `Workspace` 对象即可同时消除此窗口。此安全登记不单独影响 FAIL，M1 的阻断依据是当前正常无 `--store` 路径已违反明确的“一次读取”验收条款。

## 最终判断

**FAIL。**先修 M1 的默认存储路径双读和 M2 的 serve 输出刷新，并以定向测试锁住；其他已检查的 CLI 输出、注册表错误分类及 IPv4/IPv6 格式符合本轮范围。
