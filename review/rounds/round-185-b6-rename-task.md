# 任务书：B6 —— 配置键 `total_daily_minutes` 改名为 `default_daily_minutes`（窗口 `luna-b`）

**用户 2026-09-29 决定做这次改名。** 先读 `AGENTS.md`（最高原则、"不留兼容别名"、"迁移 / 重构不得改变输出"第 11–13 条与 12a）、
`docs/模块拆分与架构审查.md` 第 205 行（B6 原文）、`contracts/config.md`。

## 为什么

这个键名说它是"每日总分钟"，`KaoyanConfig` 的 docstring 还写着"唯一权威的每日预算"。实际上自 WP-E4 / M26 起，
当天分钟先取 `data/availability.yaml` 的手填值，配置里的数只是**当天没有手填时的回落值**。名字与 docstring 都误导读者。

## 要改

1. **配置契约**：配置文件键、`KaoyanConfig` 字段一律改为 `default_daily_minutes`；取值规则（整数、`>= 1`、无上限）、
   所有派生计算（`review_target_minutes`、`review_hard_cap_minutes`、保底与硬上限共存检查、7 天份额排序）**不变**。
   `KaoyanConfig` docstring 改为说明它是回落值、当天分钟由 M26 `resolve_daily_minutes` 决定。
2. **旧键给明确错误**（不是兼容别名）：配置里出现 `total_daily_minutes` 时，报 `ContractError`，路径 `total_daily_minutes`，
   消息写明"已改名为 `default_daily_minutes`，请在配置文件里改名"。不接受旧键、不自动换算。
   同时有新旧两键时同样报这个错。参照 D10 对旧路线格式给提示的做法与现有未知键拒绝的位置，放在未知键检查之前或合并进去，
   保证用户看到的是改名提示而不是泛泛的"未知键"。
3. **对外输出**：preflight / 规划者输入包里的 `config` 映射（`ky/schedule/review_clip.py` 的 `preflight_to_mapping` 等、
   `ky/planner/port.py`）键名同步改为 `default_daily_minutes`——这是本轮**唯一允许**的输出差异。输入包内容变了，
   `input_hash` 随之变化，已有 staging 提案会按既有规则判为过期，这是预期的，在报告里写一句。
4. **代码**：`ky/models.py`、`ky/availability/port.py`、`ky/planner/port.py`、`ky/schedule/review_clip.py` 里的名字、
   局部变量、错误消息、注释同步改名（错误消息里引用这个键的文字一并更新）。
5. **规格**：`contracts/config.md`、`contracts/availability.md`、`contracts/planner_port.md`、`contracts/review_clip.md`
   全部同步；`contracts/config.md` 加一段"旧键 `total_daily_minutes`：拒绝并提示改名（B6，用户 2026-09-29）"。
   `docs/模块拆分与架构审查.md` 第 205 行 B6 条目后注明"已处理（2026-09-29 改名）"。
6. **测试与夹具**：`tests/` 下所有用到旧键的配置夹具（含 `tests/fixtures/config/*.yaml`）与断言同步改名。
   新增测试只覆盖第 2 条（旧键单独出现、新旧同时出现）与第 3 条（输出映射键名）。

## 固定基线对照测试的处理

`tests/contract/test_models_split_baseline.py`、`tests/contract/test_schedule_split_baseline.py` 等把同一份配置
喂给固定提交的旧代码与当前代码。旧代码只认旧键：**给旧版喂旧键配置、给新版喂新键配置**，其余比较照旧。
若输出字节里含这个键名（例如 preflight JSON 的 `config` 映射），只允许**恰好这一个键名**的差异——在比较前把旧版输出里的
`"total_daily_minutes"` 这一个 JSON 键替换为新名，按原始字节比较，**不要用正则抹掉更多内容**（第 12a 条）。
报告里逐个列出你动过的基线测试和每处改动的理由。

## 不做的

- 不改任何计算、默认值、校验范围；不改其它配置键。
- 不动 `tools/archive/`（`verify_round3_findings.py` 是归档脚本，保持原样）、`logs/`、`review/`。
- 不改 `ky/freeze/` 的冻结口径（另一轮会做"过期 scheduled 计入积压"，不要提前做）。
- 不跑全量。

## 验收（只跑这些）

```
py -3.12 -m unittest tests.contract.test_config_port tests.contract.test_availability_port tests.contract.test_planner_port tests.contract.test_review_clip_port tests.contract.test_models_split_baseline tests.contract.test_schedule_split_baseline tests.contract.test_freeze_port tests.contract.test_resume_port tests.contract.test_review_progress_port tests.contract.test_subject_onboarding tests.test_cli
```

再加上你用 `git grep -l total_daily_minutes -- tests` 找到的其它模块（报告里列出实际命令）。
改完后 `git grep -n total_daily_minutes -- ky contracts tests` 只应剩下第 2 条的改名提示及其测试、第 5 条的规格说明、
以及基线测试里喂给旧版的配置与那一处键名替换；把输出贴进报告。

## 报告

`review/rounds/round-185-b6-rename-luna.md`：改了哪些文件、旧键报错的实际输出原文、输入包键名变化的前后对照、
基线测试的处理清单、`git grep` 结果、验收输出原文。写"全量：未跑（按 AGENTS.md，由决策者提交前统一跑）"。
不提交。含中文只用 `apply_patch`，写完查 `???`。
