# 第 188 轮评审：B6 配置键改名

## 结论

**FAIL。** 运行时代码的改名、旧键拒绝和定点输出对照均通过；`docs/模块拆分与架构审查.md` 却删掉 B6 原审查叙述，未按任务书在原条目后标注已处理，且实现报告未列出删除内容及理由。这违反本轮任务书与 `AGENTS.md` 第 13 条。

范围为 `git diff d692365` 的 `ky/`、`contracts/`、`docs/`、`tests/` 全部改动。用 `git archive d692365` 展开系统临时目录并复制本轮改动验证；`git show` 以仓库 `GIT_DIR` 读取固定基线。全量：未跑（按 AGENTS.md）。

## 必须改

### M1：B6 历史审查条目被替换而非标注

位置：`docs/模块拆分与架构审查.md:205`。复现：对比 `git show 'd692365:docs/模块拆分与架构审查.md'` 的 B6 行与当前第 205 行。旧版写明当时为何认为“唯一权威的每日预算”与阶段②决议冲突、当时由 `review_clip` 逐日覆盖缓解，以及改名建议；新版整句改为“配置字段已改名……已处理”，上述依据全部消失。任务书第 5 项要求在 B6 条目**后**注明“已处理”；`AGENTS.md` 第 13 条要求删用户可见文字前列出并说明理由、交决策者决定。实现报告只称“B6 原文条目标注为已处理”，未列出这些删除内容或理由。

应保留原审查依据，明确标为改名前的历史状态，再在其后补已处理日期与当前口径；如确需删除，先把原文与理由交决策者裁定。此项是任务和文档规则的直接违反，未发现由它引起的运行时计算错误。

## 建议改

- **固定基线错误文本仅归一化旧侧。** `tests/contract/test_models_split_baseline.py::_compare_config` 当前对旧版与新版异常都执行 `str(exc).replace("total_daily_minutes", "default_daily_minutes")`，路径也同样归一化。定点变异：只在临时副本把新版 `_check_subject_minimums` 的错误文字改回 `exceeds total_daily_minutes`，运行 `py -3.12 -m unittest tests.contract.test_models_split_baseline.ModelsSplitBaselineTests.test_fixed_baseline_matches_seed_and_generated_variants -q` 仍为 `OK`；`tests.test_contracts.ConfigContractTest.test_min_daily_minutes_cannot_exceed_total` 对同一变异则失败，实测新错误为 `subjects[1].min_daily_minutes: min_daily_minutes (200) exceeds total_daily_minutes (120)`。现有直接断言守住了这条具体路径，因此不另列必须改；但基线测试本身应只适配**旧侧**，使它也能发现新版重新输出旧名。
- **基线数据类视图只保留旧字段。** `test_availability_port.py`、`test_planner_port.py`、`test_freeze_port.py` 中的 `as_dataclass()` 在新版字段之外又加入旧字段，随后 `_rename_legacy_key` 会把两个同值字段折叠为一个。对当前给定输入，折叠没有改变比较结果；更直接的旧版视图应以旧字段**替换**新字段，便于证明固定基线实际收到的就是改名前的模型。
- **更正实现报告的旧键消息抄录。** `round-185-b6-rename-luna.md` 的 `git grep` 原始输出段把 `tests/contract/test_config_port.py` 的期望写作英文 `has been renamed to`；当前测试和 `ky/models.py` 都是中文 `已改名为`。实测是报告过时，不是代码与测试互相矛盾。

## 不改

- **旧键拒绝和校验顺序。** 只含旧键以及新旧键并存的配置，均在根未知键检查前抛 `ContractError`，路径 `total_daily_minutes`，消息为 `total_daily_minutes: total_daily_minutes 已改名为 default_daily_minutes，请在配置文件里改名`；代码不读取旧值、不提供兼容别名。临时副本把未知键检查提前后，运行 `py -3.12 -m unittest tests.contract.test_config_port.ConfigFormatTests.test_renamed_legacy_key_is_rejected_with_migration_message tests.contract.test_config_port.ConfigFormatTests.test_renamed_legacy_key_is_rejected_even_with_new_key -v`，两条均因得到 `unknown field 'total_daily_minutes'` 而失败；恢复源码后哈希与工作区一致。
- **错误语言判断。** `ky/models.py` 周围一般以英文书写 `ContractError`，但本轮任务书明确要求向用户提示“已改名为……请在配置文件里改名”，当前中文消息对旧配置更清楚，也被定点测试完整锁住。“跟周围代码长得一样”主要约束错误处理方式；此处的专门迁移提示无需为统一语言改成英文。实现报告中英文抄录不能当作实际代码证据。
- **计算与输入映射。** 代码 diff 里分钟缩放、比例范围、保底/硬上限不等式、七天目标的 `Fraction` 排序式及其调用顺序均只换字段名。定点运行 `py -3.12 -m unittest tests.contract.test_config_port tests.contract.test_models_split_baseline tests.contract.test_schedule_split_baseline tests.contract.test_availability_port tests.contract.test_planner_port tests.contract.test_freeze_port tests.contract.test_review_clip_port -q`，`Ran 98 tests ... OK`。旧版与新版在同一份 `config-minimal.yaml`、`reviews-normal.yaml`、`2026-09-15` 上运行 `py -3.12 -m ky preflight --json`，均 exit 0、stderr 空；硬上限 72、软配额 54、已选复习 22、新学 98 不变。旧版 JSON 的 `config.total_daily_minutes` 改为 `config.default_daily_minutes` 后按既有 `sort_keys=True` 重新序列化，得到与新版完全相同的原始字节；直接字符串替换不相等只是该键在排序后移动了位置。规划者输入包顶层及 `config` 中也仅改此键；规范 JSON 内容变化导致 `input_hash` 变化，旧 staging 提案按现有哈希规则过期。
- **固定基线与剩余旧名。** `test_models_split_baseline` 固定 `b97f3ac` 且断言旧 `validate_config` 的长度，`test_schedule_split_baseline` 固定 `24371ee` 并断言旧长函数；availability、planner、freeze 的基线也固定到提交哈希。`git show` 核实这些旧源码确含 `total_daily_minutes`。给旧版喂旧键、给新版喂新键的改法必要；availability 基线 CLI 只替换源码中的 `.total_daily_minutes` 属性访问，stdout 只对一个带引号 JSON 键执行一次字节替换。`git grep total_daily_minutes -- ky contracts tests docs README.md` 的剩余位置均属 `ky/models.py` 旧键拒绝、`contracts/config.md` 说明、旧键测试或固定基线适配；未发现其它活跃运行路径继续读取旧字段。此项不抵消 M1。

## 安全登记

本轮未发现需按恶意输入、手工篡改或精确竞态新增登记的问题。
