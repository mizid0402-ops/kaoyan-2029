# 第 190 轮：B6 改名返工

窗口：luna-b 续做  
日期：2026-09-29

## 修改

- `docs/模块拆分与架构审查.md`：第 205 行恢复 `d692365` 中 B6 审查原文；在其后另起一句记载已改名及当前回落值口径。原有历史叙述未删改。
- `tests/contract/test_models_split_baseline.py`：异常消息与错误路径的旧名归一化只用于固定旧版一侧；`_normalized` 的数据类字段名适配也只在旧版一侧启用。新版异常文字、路径和数据类字段名原样比较。
- `tests/contract/test_availability_port.py`、`test_planner_port.py`、`test_freeze_port.py`：旧视图构造时过滤 `default_daily_minutes`，再加入 `total_daily_minutes`。数据类字段与 `asdict()` 输出只保留旧字段；另提供非字段属性访问器，是因为被执行的固定旧入口会调用当前 availability/review_clip 辅助函数。
- 未修改 `ky/`、`contracts/` 或其它文档。

## 撤实现验证

### 新版错误文字变异

临时将 `ky/models.py::_check_subject_minimums` 的 `default_daily_minutes` 错误文字改回 `total_daily_minutes`，执行：

```text
py -3.12 -m unittest tests.contract.test_models_split_baseline.ModelsSplitBaselineTests.test_fixed_baseline_matches_seed_and_generated_variants -q
```

结果：失败，命中 `config-subject-minutes-exceeds-total`。基线期望 `exceeds default_daily_minutes (120)`，新版变异实际输出 `exceeds total_daily_minutes (120)`，新版一侧未被归一化。随即恢复源码。

### 旧版字段视图变异

临时从 availability 的 `as_dataclass()` 删除旧字段 `total_daily_minutes` 的值赋入，执行：

```text
py -3.12 -m unittest tests.contract.test_availability_port.AvailabilityPortContractTests.test_input_package_null_bytes_match_baseline_when_unregistered -q
```

结果：失败，构造旧视图时报告 `TypeError: LegacyConfig.__init__() missing 1 required positional argument: 'total_daily_minutes'`。这表明固定基线调用确实要求旧模型字段。随即恢复赋值。

两次变异恢复后的 SHA-256 与变异前一致：

```text
ky/models.py
D8FA33D31DEACA1E43FAD4D4498ED53F5B39CB41DC780C04B86B530283D26433

tests/contract/test_availability_port.py
E34AAC46627A077CF787AE4FE76DDFCE77B11077792161BDB316D197EA53BDBC
```

之后为当前辅助函数补入非字段 `default_daily_minutes` 访问器，availability 测试文件随之有预期修改；当前文件 SHA-256 为 `4AA1946CF6CE28436925925099085EB404B05D0DB8354D7AD870F382247CD406`。`ky/models.py` 当前哈希仍为 `D8FA33D31DEACA1E43FAD4D4498ED53F5B39CB41DC780C04B86B530283D26433`。

## round-185 报告抄录

`round-185-b6-rename-luna.md` 的旧 `git grep` 代码片段曾把中文提示误抄成英文。本轮未改该旧报告；以下是本轮重新执行的当前输出，提示为中文，且各条旧名命中均限于拒绝规则、测试或固定旧版适配：

```text
contracts/config.md:67:旧键 `total_daily_minutes`：拒绝并提示改名（B6，用户 2026-09-29）。配置中出现该键时，
contracts/config.md:68:无论是否同时出现 `default_daily_minutes`，均以路径 `total_daily_minutes` 报 `ContractError`，
contracts/config.md:121:2. 旧键 `total_daily_minutes` 改名提示；
ky/models.py:471:    if "total_daily_minutes" in root:
ky/models.py:473:            "total_daily_minutes 已改名为 default_daily_minutes，请在配置文件里改名",
ky/models.py:474:            "total_daily_minutes",
tests/contract/test_availability_port.py:47:        if name == "total_daily_minutes":
tests/contract/test_availability_port.py:59:        values["total_daily_minutes"] = self._config.default_daily_minutes
tests/contract/test_availability_port.py:63:            + [("total_daily_minutes", int)],
tests/contract/test_availability_port.py:66:            lambda instance: instance.total_daily_minutes
tests/contract/test_availability_port.py:82:            ("default_daily_minutes" if key == "total_daily_minutes" else key):
tests/contract/test_availability_port.py:222:            ".total_daily_minutes", ".default_daily_minutes"
tests/contract/test_availability_port.py:232:            baseline.stdout.replace(b'"total_daily_minutes"', b'"default_daily_minutes"', 1),
tests/contract/test_availability_port.py:248:            baseline.stdout.replace(b'"total_daily_minutes"', b'"default_daily_minutes"', 1),
tests/contract/test_config_port.py:99:        document["total_daily_minutes"] = document.pop("default_daily_minutes")
tests/contract/test_config_port.py:101:        self.assertEqual(error.path, "total_daily_minutes")
tests/contract/test_config_port.py:104:            "total_daily_minutes: total_daily_minutes 已改名为 "
tests/contract/test_config_port.py:110:        document["total_daily_minutes"] = document["default_daily_minutes"]
tests/contract/test_config_port.py:112:        self.assertEqual(error.path, "total_daily_minutes")
tests/contract/test_freeze_port.py:41:        if name == "total_daily_minutes":
tests/contract/test_freeze_port.py:53:        values["total_daily_minutes"] = self._config.default_daily_minutes
tests/contract/test_freeze_port.py:57:            + [("total_daily_minutes", int)],
tests/contract/test_freeze_port.py:60:            lambda instance: instance.total_daily_minutes
tests/contract/test_freeze_port.py:76:            ("default_daily_minutes" if key == "total_daily_minutes" else key):
tests/contract/test_models_split_baseline.py:327:                        if legacy_config and field.name == "total_daily_minutes"
tests/contract/test_models_split_baseline.py:394:            baseline_document["total_daily_minutes"] = baseline_document.pop(
tests/contract/test_models_split_baseline.py:411:                        "total_daily_minutes", "default_daily_minutes"
tests/contract/test_models_split_baseline.py:413:                    if path == "total_daily_minutes":
tests/contract/test_planner_port.py:45:        if name == "total_daily_minutes":
tests/contract/test_planner_port.py:57:        values["total_daily_minutes"] = self._config.default_daily_minutes
tests/contract/test_planner_port.py:61:            + [("total_daily_minutes", int)],
tests/contract/test_planner_port.py:64:            lambda instance: instance.total_daily_minutes
tests/contract/test_planner_port.py:80:            ("default_daily_minutes" if key == "total_daily_minutes" else key):
tests/contract/test_planner_port.py:487:        self.assertNotIn("total_daily_minutes", data)
tests/contract/test_planner_port.py:489:        self.assertNotIn("total_daily_minutes", data["config"])
tests/contract/test_schedule_split_baseline.py:44:        if name == "total_daily_minutes":
```

`git grep -l total_daily_minutes -- tests` 当前结果：

```text
tests/contract/test_availability_port.py
tests/contract/test_config_port.py
tests/contract/test_freeze_port.py
tests/contract/test_models_split_baseline.py
tests/contract/test_planner_port.py
tests/contract/test_schedule_split_baseline.py
```

## 验收

执行命令：

```text
py -3.12 -m unittest tests.contract.test_models_split_baseline tests.contract.test_availability_port tests.contract.test_planner_port tests.contract.test_freeze_port tests.contract.test_config_port tests.test_contracts
```

验收输出：

```text
Ran 145 tests in 16.430s

OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。
