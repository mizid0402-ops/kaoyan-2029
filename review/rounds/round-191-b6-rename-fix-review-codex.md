# 第 191 轮评审：B6 改名返工

## 结论

**PASS。** 第 188 轮 M1 已修复，两条建议也已落实；未发现本轮改动引入的必须改问题。范围仅为 `docs/模块拆分与架构审查.md` 和四个指定的契约测试相对第 188 轮所见版本的变化，并核对 `ky/`、`contracts/` 未变。用 `git archive d692365` 加第 188 轮副本及本轮五个文件，在系统临时目录验证。全量：未跑（按 AGENTS.md）。

## 必须改

无。

## 建议改

无。`round-185-b6-rename-luna.md` 中把中文错误提示误抄为英文的问题，已由本轮实现报告说明并给出当前 `git grep` 输出；没有把旧报告文字当作运行时代码证据。

## 不改

- **M1 原文恢复。** `git diff d692365 -- docs/模块拆分与架构审查.md` 只显示在原 B6 条目后新增一个“已处理（2026-09-29，用户决定）”段落及空行；原条目与 `d692365` 逐字相同，文档其它文字未删。新增段落同时写明新键、旧键拒绝、M26 当天分钟决策及配置回落值。
- **建议 1：仅适配旧侧。** `test_models_split_baseline.py::_compare_config` 现在只在 `is_baseline` 时替换旧字段名、异常消息及路径；新版值和异常原样比较。临时把新版 `ky/models.py::_check_subject_minimums` 的消息从 `exceeds default_daily_minutes` 改回 `exceeds total_daily_minutes`，运行 `py -3.12 -m unittest tests.contract.test_models_split_baseline.ModelsSplitBaselineTests.test_fixed_baseline_matches_seed_and_generated_variants -q`，实测 `FAILED (failures=1)`，命中 `config-subject-minutes-exceeds-total`：旧侧归一化后期望 `default_daily_minutes (120)`，新版变异实际为 `total_daily_minutes (120)`。第 188 轮同一变异使该基线测试保持绿色；盲区现已关闭。恢复后 `ky/models.py` SHA-256 为 `D8FA33D31DEACA1E43FAD4D4498ED53F5B39CB41DC780C04B86B530283D26433`。
- **建议 2：旧版字段形状。** `test_availability_port.py`、`test_planner_port.py`、`test_freeze_port.py` 都在创建旧版数据类时排除 `default_daily_minutes` 字段，仅加入 `total_daily_minutes`。独立探针对三个实例逐一检查 `dataclasses.fields` 和 `dataclasses.asdict`：旧名均存在、新名均不存在，值均为 120。旧版规划者入口在固定提交中直接使用 `config.total_daily_minutes` 和 `asdict(config)`；新增 `default_daily_minutes` 属性是非字段访问器，返回同一个旧字段值，仅让旧入口调用到的**当前** `select_daily_reviews` / `resolve_day_budget` 等辅助函数继续执行。它使属性读取可见新名，但不会使旧入口的字段序列化悄悄包含新名；固定旧源码本身未使用新属性，因而没有削弱本轮要证明的旧字段数据形状。
- **旧版值确实参与字节比较。** 只在临时副本把 availability 旧视图中的 `values["total_daily_minutes"]` 改为当前值加 1，运行 `py -3.12 -m unittest tests.contract.test_availability_port.AvailabilityPortContractTests.test_input_package_null_bytes_match_baseline_when_unregistered -q`，实测 `FAILED (failures=1)`：当前包中归一化后的配置值为 120，旧版变异输出为 121。恢复后该文件 SHA-256 与工作区同为 `4AA1946CF6CE28436925925099085EB404B05D0DB8354D7AD870F382247CD406`。
- **范围与验收。** 将本轮工作区 `ky/` 四个改名文件、`contracts/` 四个改名规格逐一与第 188 轮临时副本比对 SHA-256，均相同。临时归档运行 `py -3.12 -m unittest tests.contract.test_models_split_baseline tests.contract.test_availability_port tests.contract.test_planner_port tests.contract.test_freeze_port tests.contract.test_config_port tests.test_contracts -q`，实测 `Ran 145 tests in 20.480s`、`OK`；设置 `PYTHONDONTWRITEBYTECODE=1`，没有运行全量。

## 安全登记

本轮没有发现需按恶意输入、手工篡改或精确竞态新增登记的问题。
