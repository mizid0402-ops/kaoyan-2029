# 第 235 轮 WP-M28b 实现报告

## 改动与做法

- `Phase` 增加可选 `base_daily_minutes`。全阶段缺省时序列化仍为 v2；任一阶段带值（包括 0）时序列化为 v3，且只在提供值的阶段输出字段。解析器接受 v2/v3、拒绝 v2 携带字段，并排除布尔值。
- M8 增加只读 `PacingInitial` 协议，按匹配路线阶段 > `day >= start` 的 pacing initial > 配置解析 `(base_minutes, base_source)`。总时长回落到非配置基数时来源为 `base`，手填和课表来源不变。
- preflight、M19 与 resume 明确传入 `pacing_initial=None`。裁剪/分配遵从冻结、availability/timetable/base override、config 旧路径顺序。resume 仍在每个候选日重新解析预算。
- M19 availability 形状由 `_availability_mapping` 参数化；设置已登记时添加两个 nullable 字段，当前装配显式不登记/传设置。该参数行为由单元测试覆盖。
- 同步 `route_plan.md`、`availability.md`、`timetable.md` 与 `planner_port.md` 的 v3、基数来源和调用方规则。增加 `dcbb5b6` 固定源码身份检查及三种路线状态的字节对照：无路线、已登记未开始、进行中；覆盖 preflight 文本/JSON、day/route planner input、resume dry-run 和 route show。

## 验收

执行任务书指定命令，原文输出：

```text
----------------------------------------------------------------------
Ran 156 tests in 56.006s

OK
```

随后因补齐逐日基数例子及显式 resume 参数，重跑受影响模块，原文输出：

```text
----------------------------------------------------------------------
Ran 23 tests in 16.104s

OK
```

`git diff --check` 通过；本轮修改文件 `rg -n '\?\?\?' ...` 无匹配。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 歧义与选择

- 当前 M0 `Workspace` 尚无 `settings.pacing` 注册字段，而任务范围禁止改 `ky/workspace.py`。因此 M28b 不读取、不推断该注册；M19 通过布尔参数实现登记时的字段形状，现有装配传 `False`，pacing 值仍为 `None`，留待 M28c 接线。
- `ky timetable show` 没有调用日预算的目标日期（周视图会跨日），保留配置基数作为当前展示基数；本包的 preflight、M19 与 resume 均按实际目标日使用 M8。


## 第 240 轮返工

### 逐条做法

- **B1**：`_availability_mapping` 参数标注为 `DayBudget`；登记 pacing 时输出解析所得的 `base_minutes` / `base_source`，未登记时保留原两键形状。测试覆盖 route 基数 210、route 基数 0、pacing_initial 180、config 120，并断言登记与未登记两种映射。
- **B2**：`timetable_main` 在路线已登记时只读取一次当前路线。日期视图按 `--date` 解析基数；周视图按周一至周日分别调用 `daily_base_minutes`，再将逐日基数传给 `timetable.day`。复盘设置仍为 `None`，移除 `date.today()`。合成 CLI 测试验证日期视图得到 180 / 135 分钟，跨阶段周视图逐日传入 180、180、240、240、240、240、240，并断言每次命令仅读路线一次。
- **B3**：preflight 的 override 测试改用 `total_source=base`，同时检查冻结覆盖为 0；M19 把来源选择抽为 `_day_clip_parameters` 并覆盖 base 与冻结路径。resume 合成路线分两阶段设置基数 180 / 240，120 分钟事项必须跳过首阶段、分配至次日阶段。另测有效路线遇到课表 `None` 时得到基数 210、总分钟 210、来源 `base`。固定基线改为断言 `dcbb5b6` 的 `daily_base_minutes(config)` 单参数签名和不含 `base_daily_minutes` 的 `Phase`，并断言两文件与同一提交 `git archive` 内容逐字节相同。
- **规格与接口整理**：说明 v2/v3 的适用条件及对旧 D10 措辞的覆盖；planner 映射字段写为解析出的实际值；课表回落来源措辞改为 M8 改写；`PacingInitial` 加入公开接口并使用只读 property；基数解析先校验日期、设置起始日期和非负整数（排除布尔）。

### 验收

执行命令：

```text
py -3.12 -m unittest tests.contract.test_route_plan_port tests.contract.test_day_budget_port tests.contract.test_availability_port tests.contract.test_planner_port tests.contract.test_resume_port tests.test_planning tests.test_cli
```

最终测试输出原文：

```text
----------------------------------------------------------------------
Ran 160 tests in 56.424s

OK
```

首轮同命令曾因合成周视图缺少 `schools` 档案而失败；补齐测试 double 后上述最终运行通过。`git diff --check` 通过，报告及本轮修改的中文文件均未发现连续问号占位符。

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
