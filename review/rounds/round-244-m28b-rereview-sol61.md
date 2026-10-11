# 第 244 轮：WP-M28b 返工复审

结论：**PASS**。第 239 轮 B1–B3 均关闭，未发现返工引入的新日常阻断问题。
本工作包可以交决策者合并；真实 pacing 设置接线仍按原分工留 M28c，不代表整个 M28 已完成。

范围：复审 `F:/workspace/kaoyan-wt-m28b` 的实际未提交 diff、
第 240 轮任务书及实现报告返工节，结合本轮 AGENTS.md 与前轮结论。
本轮只写主仓库本报告，不修改实现或测试、不提交、不联网、不读取仓库外文件或个人数据。
测试及探针使用合成输入；内存变异在独立 Python 进程中进行，不写变异文件。

## 一、B1–B3 关闭证据

| 项目 | 状态 | 证据 |
|---|---|---|
| B1 新增基数字段为 null | 关闭 | `_availability_mapping` 参数为 DayBudget；登记时返回实际 base_minutes/base_source，未登记保留两键；单项覆盖 route=210、route=0、pacing_initial=180、config=120 |
| B2 展示忽略路线与目标日 | 关闭 | timetable_main 仅读一次已登记当前路线；日期视图按 --date 解析，周视图七个日期分别解析基数；不再调用 date.today；对应单项及禁止时钟探针通过 |
| B3 验收与旧版身份断言缺口 | 关闭 | 补 base 裁剪/冻结、跨阶段 resume、有效路线遇课表 None，以及旧 budget/planning 身份检查和归档源码相等断言；相关单项与实际变异验证通过 |

### B2：逐日基数及无时钟

`ky/__main__.py:1588–1594` 一次加载路线；`:1703–1709` 在周一至周日循环中
逐日调用 daily_base_minutes，再传给 timetable.day；`:1744` 用日期视图解析的 day。
没有使用系统日期替换目标日期，也没有用一个总容量代替扣课前基数。

合成 CLI 单项验证日期视图 cap=180、minutes=135，路线读一次；
跨阶段周视图收到基数 180、180、240、240、240、240、240，再次命令仍只读路线一次。
额外将应用模块的 date 换为 today() 一旦调用便抛异常的子类，重跑同一单项：**通过**。
测试夹具自身仍使用测试模块的日期类生成日期；此探针禁止的是应用读取系统时间。

### B3：身份断言确有区分，测试可以捕获退化

固定基线仍是 dcbb5b6。新断言检查旧 budget 的单参数
`daily_base_minutes(config: KaoyanConfig) -> int`，以及旧 planning 的 Phase
不存在 base_daily_minutes；随后断言这两份固定源码与同一提交归档文件逐字节相等。
独立探针分别把同一判据用于旧源码和当前工作区，结果均为：**旧 True，当前 False**。
不再拿两版相同的 M26 源码当作旧版身份。

内存中仅替换直接相关函数，运行已有指定单项，结果如下：

| 人为退化 | 验证结果 |
|---|---|
| 只从 preflight override 分支删去 base | 测试报错，捕获缺失 daily_minutes_override |
| 只从 preflight floor 分支删去 base | 测试报错，捕获缺失 floor_policy |
| 从 M19 `_day_clip_parameters` 来源集合删去 base | 测试断言失败 |
| resume 每次解析都改用搜索首日 | 跨阶段单项断言失败 |

preflight 测试使用替换后的 base 来源预算，足以隔离检查调用方分流，
完整来源改写另由 M8 测试覆盖；M19 抽出的函数确实由 `_build_input_data` 调用，未成为未接入的测试辅助。
resume 单项用阶段 180/240、120 分钟事项：首日硬容量不足，次日可容纳，
若复用首日基数则失败。有效路线与课表返回 None 的新增断言得到 210/210/base。
这些验证证明测试有针对性，不只是与当前实现一起返回成功。

## 二、必须改

**无。** 本轮限定返工范围没有剩余必须改项。

## 三、建议改

- 课表展示测试用 date.today() 两次构造周一。建议以后整理为固定合成周一，
  或至少只取一次日期，避免极端跨午夜时夹具日期不一致，也让无时钟条件更直观。
  应用当前无时钟行为已由独立探针验证，不因这一夹具写法阻止合并。
- 真正的 settings.pacing 登记、M19 对象启用条件及向所有调用方传真实设置仍需 M28c 接线。
  保留任务书的 None/False 占位分工，不把本包 PASS 写成整模块登记场景已完成。

## 四、不改与新问题核对

- 路线 v3 的按需输出、0 是带值、v2 拒绝新键及 `_check_phase_base` 保持前轮已接受逻辑；
  没有借返工改变存储发布协议或旧阶段字段。
- M8 仅在 M26 回落为 config 且基数来自 route/pacing_initial 时改写为 base；
  手填和课表来源仍保留，配额按实际 total_minutes 缩放。
- 冻结先于 override，config 旧路径保留；preflight/M19 的三步参数顺序没有被抽函数改变。
- PacingInitial 已列入公开接口与 __all__，用只读 property 声明；
  daily_base_minutes 在比较日期前拒绝非日期/datetime，检查 initial 非负整数并排除布尔。
  对应公开输入校验单项已在日预算模块中通过。
- 四份规格保留主规则；nullable 文案已修成实际值，route_plan 的旧 D10/v2 描述有明确覆盖关系，
  timetable 回落归属已改为 M8 改写。没有重新选择业务规则。
- M18、M26 与 M0 实现没有新增 diff，真实设置读取未越界。一次路线对象用于预算和映射的约束保留，
  未新增路径猜测、按错误消息分流、生产科目硬编码或旧防护删除。
- 基线夹具仍覆盖无路线／已登记未开始／进行中，原始输出与文件树比较不归一化，
  所列命令仍要求规定退出码；本轮固定基线实际通过。

## 五、本轮验证

```text
py -3.12 -B -m unittest tests.contract.test_day_budget_port
Ran 17 tests in 14.566s
OK
```

另只运行四个相关单项：

```text
tests.contract.test_planner_port.PlannerPortContractTests.test_pacing_registration_adds_resolved_base_to_availability_shape
tests.contract.test_planner_port.PlannerPortContractTests.test_base_source_uses_override_and_frozen_policy_wins
tests.contract.test_resume_port.ResumePortContractTests.test_route_phase_bases_are_resolved_for_each_resume_candidate_day
tests.test_cli.TimetableRouteBaseTests.test_show_uses_the_requested_day_base_and_each_weeks_phase_base
Ran 4 tests in 0.066s
OK
```

另外完成上述四种内存变异、禁止应用时钟探针与两份源码身份区分探针。
所有命令设 PYTHONDONTWRITEBYTECODE=1；git diff --check 无输出。
未重复实现者七模块验收，不把实现者报告的 160 项当作本轮实测。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

## 六、安全登记

无新增独立安全登记。内存变异只是验证正常行为退化能被测试捕获，
不是扩大恶意输入/并发威胁模型；已有安全防护保留。

合并判断：**WP-M28b 可合并**。由决策者按项目规则完成提交及整合验证，本轮未执行合并或提交。
