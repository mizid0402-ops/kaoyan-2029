# 任务书：WP-G2a CLI 小项（C7 `ky -h` / serve 打印地址；record 不再按错误消息文字判断）

先读仓库根 `AGENTS.md`（全部规则都适用，尤其"迁移 / 重构不得改变输出"11–13、12a 与"已知缺陷清单"2、3），再读：
`docs/模块拆分与架构审查.md` 的 C7 一行、`docs/模块地图.md`（M14 CLI、M15 投影）、`ky/__main__.py`（`main` 的子命令分派、`day_plan_main` 的 record 分支）、
`ky/workspace.py`（`find_workspace` / `load_workspace`）、`ky/projection/serve.py`、`tests/test_cli.py`、`tests/test_projection_service.py`。

你在主仓库 `F:\workspace\kaoyan-ai-system` 工作，只改 `ky/__main__.py`、`ky/projection/serve.py`、`tests/test_cli.py`、`tests/test_projection_service.py`，
以及 `README.md` 里提到 `-h` / serve 的用法行（如有）。

## 要做的

1. **`py -3.12 -m ky -h` / `--help` 列出全部子命令**（C7）。现状：顶层 `-h` 落到 preflight 的解析器，看不到 `ledger`、`snapshot`、`planner-input`、`day-plan`、`month-close`、`route`、`review-queue`、`resume`。
   - 把 `main` 里逐个 `if args_in[0] == ...` 的分派改成**一张子命令表**（名字 → 入口函数 + 一行说明），分派与帮助都读这张表（D7：加子命令只改一处）。
   - 只有 `args_in[0]` 是 `-h` / `--help` 时打印顶层帮助（退出 0）：用法行、每个子命令一行说明、说明"不写子命令即 preflight"、提示 `py -3.12 -m ky <子命令> -h` 看各自参数。说明文字的语言照各子命令现有 argparse `description`。
   - **其他一切调用输出逐字节不变**：`py -m ky preflight -h`、`py -m ky --date ... -h`（仍是 preflight 帮助）、每个子命令、无参数、未知参数的输出与退出码都与基线相同。
2. **`py -3.12 -m ky.projection.serve` 启动前打印访问地址**（C7）：一行写明数据库路径与 `http://<host>:<port>/`（host 含 `:` 时加方括号），以及"Ctrl+C 停止"。数据库不存在、注册表错误等既有错误路径输出不变。
3. **record 不再按错误消息文字判断"找不到注册表"**（已知缺陷清单 3；`ky/__main__.py` 里 `workspace_not_found = ("not found" in ... or "workspace file does not exist" in ...)`）：
   - 在 record 开头**只查找、加载一次注册表**，分开调用：`find_workspace` 失败 = 找不到；找到后 `load_workspace` 失败 = 无效。出题建议一段复用这次的结果，不再第二次 `find_workspace` / `load_workspace`（已知缺陷清单 2）。
   - 输出逐字节不变：找不到（无注册表可发现、`--workspace` 指向不存在的文件）→ "未找到工作区注册表，跳过出题"；注册表无效、或出题查询本身的契约错误 → "出题查询失败，已跳过：<原消息>"；JSON 的 `check_question_suggestions_skipped` 与 `freeze_latch_warning` 键和值不变；冻结锁存的"找不到 / 无效都照常记录"宽容不变。

## 不做的

- 不改任何子命令的参数、行为与输出（除上面第 1 条的顶层帮助、第 2 条多出的一行）；不重排 preflight 解析器。
- 不动 `tools/`（那是 G2b）、不动 M5 卷面（G2c）；不加 `ky rebuild`。
- 不补任务书没列的测试。

## 测试（只写这些）

- 顶层 `-h` / `--help`：退出 0，输出里每个子命令名都出现；子命令名从上面那张表取，**不在测试里写死子命令清单或数量**。
- 对照测试（`AGENTS.md` 12 / 12a）：用 `git show 0c3b3e5:ky/__main__.py` 取旧版（测试里断言取到的确实是旧版，例如旧版含 `workspace_not_found = (`），在同一份临时输入上分别跑新旧版本，按原始字节比较 stdout / stderr / 退出码，至少覆盖：
  `preflight -h`、无参数 preflight、未知子命令 / 未知参数、record 的"找不到注册表"（文本与 JSON）、"注册表无效"（文本与 JSON）三类。
- serve：patch 掉 Datasette 的 `cli.main`（不真正起服务），断言打印的地址行；IPv6 host 加方括号。

每条都要在撤回对应修改时变红，报告里写**实际怎么撤、实际跑出的结果**（不要只写推理）。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.test_cli tests.test_projection_service tests.contract.test_freeze_port
```

## 报告

`review/rounds/round-127-wp-g2a-luna.md`：每项落点、子命令表的形状、对照测试覆盖了哪些调用、撤修改验证（实际命令与结果）、验收输出、建议。
写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。不提交。含中文的文件只用 `apply_patch` 编辑，写完查 `???`。
