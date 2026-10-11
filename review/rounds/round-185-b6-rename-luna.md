# B6：`total_daily_minutes` 改名为 `default_daily_minutes`

日期：2026-09-29  
窗口：luna-b

## 修改范围

- `ky/models.py`：配置字段、校验局部变量和错误消息改为 `default_daily_minutes`；`KaoyanConfig`
  文档说明该字段是回落值，每日值由 M26 `resolve_daily_minutes` 决定。
- `ky/availability/port.py`、`ky/planner/port.py`、`ky/schedule/review_clip.py`：同步属性、局部变量和
  preflight / planner 输入映射键名。分钟计算、比例、保底和排序逻辑未改。
- 契约：`contracts/config.md`、`contracts/availability.md`、`contracts/planner_port.md`、
  `contracts/review_clip.md` 同步改名；配置规格增加旧键拒绝规则及顺序。`docs/模块拆分与架构审查.md`
  的 B6 原文条目标注为已处理（2026-09-29 改名）。
- 配置夹具：`config-minimal.yaml`、`config-ratio-inverted.yaml`、`config-weights-not-closed.yaml`。
- 其余测试：`tests/contract/test_config_port.py`、`test_availability_port.py`、`test_freeze_port.py`、
  `test_planner_port.py`、`test_resume_port.py`、`test_review_clip_port.py`、
  `test_review_progress_port.py`、`test_subject_onboarding.py`、`tests/test_cli.py`、
  `tests/test_contracts.py`、`tests/test_review_scheduler.py`。

## 旧键拒绝

仅旧键时，以及新旧键同时出现时，均在未知键检查之前拒绝，路径为 `total_daily_minutes`；不读取旧值，
也不自动迁移。实际异常文本：

```text
total_daily_minutes: total_daily_minutes 已改名为 default_daily_minutes，请在配置文件里改名
```

测试分别覆盖旧键单独出现和新旧键并存，并断言错误路径和提示。

## 对外输入映射

唯一预期的键名变化：

```text
preflight.config: {project_id, total_daily_minutes, review_reserve_ratio, hard_max_ratio}
             -> {project_id, default_daily_minutes, review_reserve_ratio, hard_max_ratio}

planner_input.config.total_daily_minutes -> planner_input.config.default_daily_minutes
planner_input.total_daily_minutes        -> planner_input.default_daily_minutes
```

数值和映射的其他内容不变。输入包字节随键名改变，`input_hash` 因而改变；已有 staging 提案会按现行
哈希校验规则判为过期。

## 固定基线测试调整

- `tests/contract/test_models_split_baseline.py`：固定旧模型收到旧键，新模型收到新键；比较前把旧数据类字段名及
  对应校验错误中的旧名映射到新名，其他字段、错误类型和路径顺序照常比较。输入种子仍来自改名后的新夹具。
- `tests/contract/test_schedule_split_baseline.py`：给固定旧 schedule 函数传一个旧字段视图，底层分钟值来自当前
  配置的 `default_daily_minutes`。
- `tests/contract/test_availability_port.py`：固定旧 planner 输入函数使用旧字段数据类；基线 CLI 源码只替换属性访问
  名以便它与当前模型配合。输入 JSON 对照只容许旧预算键改名。
- `tests/contract/test_planner_port.py`：固定旧 planner 输入函数使用旧字段数据类；序列化对照只重命名预算映射键。
- `tests/contract/test_freeze_port.py`：固定旧 freeze/planner 输入函数使用旧字段数据类；序列化对照只重命名预算映射键。

## `git grep` 证据

执行 `git grep -n total_daily_minutes -- ky contracts tests`。结果只剩：

- `ky/models.py` 的旧键改名拒绝分支；
- `contracts/config.md` 的拒绝规则及检查顺序；
- `tests/contract/test_config_port.py` 的旧键测试；
- `tests/contract/test_models_split_baseline.py`、`test_schedule_split_baseline.py`、
  `test_availability_port.py`、`test_planner_port.py`、`test_freeze_port.py` 中用于固定旧代码的旧字段适配，
  以及新旧键对照断言。

命令原始输出：

```text
contracts/config.md:67:旧键 `total_daily_minutes`：拒绝并提示改名（B6，用户 2026-09-29）。配置中出现该键时，
contracts/config.md:68:无论是否同时出现 `default_daily_minutes`，均以路径 `total_daily_minutes` 报 `ContractError`，
contracts/config.md:121:2. 旧键 `total_daily_minutes` 改名提示；
ky/models.py:471:    if "total_daily_minutes" in root:
ky/models.py:473:            "total_daily_minutes 已改名为 default_daily_minutes，请在配置文件里改名",
ky/models.py:474:            "total_daily_minutes",
tests/contract/test_availability_port.py:47:        if name == "total_daily_minutes":
tests/contract/test_availability_port.py:54:        values["total_daily_minutes"] = self._config.default_daily_minutes
tests/contract/test_availability_port.py:57:            [(field.name, Any) for field in fields] + [("total_daily_minutes", int)],
tests/contract/test_availability_port.py:71:            ("default_daily_minutes" if key == "total_daily_minutes" else key):
tests/contract/test_availability_port.py:211:            ".total_daily_minutes", ".default_daily_minutes"
tests/contract/test_availability_port.py:221:            baseline.stdout.replace(b'"total_daily_minutes"', b'"default_daily_minutes"', 1),
tests/contract/test_availability_port.py:237:            baseline.stdout.replace(b'"total_daily_minutes"', b'"default_daily_minutes"', 1),
tests/contract/test_config_port.py:99:        document["total_daily_minutes"] = document.pop("default_daily_minutes")
tests/contract/test_config_port.py:101:        self.assertEqual(error.path, "total_daily_minutes")
tests/contract/test_config_port.py:104:            "total_daily_minutes: total_daily_minutes has been renamed to "
tests/contract/test_config_port.py:110:        document["total_daily_minutes"] = document["default_daily_minutes"]
tests/contract/test_config_port.py:112:        self.assertEqual(error.path, "total_daily_minutes")
tests/contract/test_freeze_port.py:41:        if name == "total_daily_minutes":
tests/contract/test_freeze_port.py:48:        values["total_daily_minutes"] = self._config.default_daily_minutes
tests/contract/test_freeze_port.py:51:            [(field.name, Any) for field in fields] + [("total_daily_minutes", int)],
tests/contract/test_freeze_port.py:65:            ("default_daily_minutes" if key == "total_daily_minutes" else key):
tests/contract/test_models_split_baseline.py:326:                    if field.name == "total_daily_minutes" else field.name,
tests/contract/test_models_split_baseline.py:386:            baseline_document["total_daily_minutes"] = baseline_document.pop(
tests/contract/test_models_split_baseline.py:400:                        str(exc).replace("total_daily_minutes", "default_daily_minutes"),
tests/contract/test_models_split_baseline.py:402:                        if getattr(exc, "path", None) == "total_daily_minutes"
tests/contract/test_planner_port.py:45:        if name == "total_daily_minutes":
tests/contract/test_planner_port.py:52:        values["total_daily_minutes"] = self._config.default_daily_minutes
tests/contract/test_planner_port.py:55:            [(field.name, Any) for field in fields] + [("total_daily_minutes", int)],
tests/contract/test_planner_port.py:69:            ("default_daily_minutes" if key == "total_daily_minutes" else key):
tests/contract/test_planner_port.py:476:        self.assertNotIn("total_daily_minutes", data)
tests/contract/test_planner_port.py:478:        self.assertNotIn("total_daily_minutes", data["config"])
tests/contract/test_schedule_split_baseline.py:44:        if name == "total_daily_minutes":
```

另行执行 `git grep -l total_daily_minutes -- tests`，结果为：

```text
tests/contract/test_availability_port.py
tests/contract/test_config_port.py
tests/contract/test_freeze_port.py
tests/contract/test_models_split_baseline.py
tests/contract/test_planner_port.py
tests/contract/test_schedule_split_baseline.py
```

以上文件均在任务指定的验收模块中。

## 验收

执行命令：

```text
py -3.12 -m unittest tests.contract.test_config_port tests.contract.test_availability_port tests.contract.test_planner_port tests.contract.test_review_clip_port tests.contract.test_models_split_baseline tests.contract.test_schedule_split_baseline tests.contract.test_freeze_port tests.contract.test_resume_port tests.contract.test_review_progress_port tests.contract.test_subject_onboarding tests.test_cli
```

输出：

```text
Ran 160 tests in 42.507s

OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。未提交。
