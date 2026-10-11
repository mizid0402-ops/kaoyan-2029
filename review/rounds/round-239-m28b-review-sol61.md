# 第 239 轮：WP-M28b 实现评审

结论：**FAIL**。路线 v3、M8 来源改写和三个主要调用方的实现方向正确，
固定基线对照也确实运行旧源码；但 M19 参数化字段输出错误，课表展示仍忽略路线基数，
任务书点名的部分验收没有落成测试，不能按当前报告直接接受。

范围：`F:/workspace/kaoyan-wt-m28b`，当前 HEAD 为
`dcbb5b6c278203b1df2cf9f37bcd434fa26f9229`，评审其未提交 diff，包含决策者的格式修正。
已读本 worktree 的 AGENTS.md、指定规格、代码、实现报告、主仓库第 235 轮任务书和第 233 轮报告。
没有联网、读取个人数据或仓库外文件；只写主仓库本报告，不修改实现或测试，不提交。
下述输入均为合成数据；实测与静态判断分别标明。

## 一、必须改

### B1：M19 新字段被固定写成 null，参数化功能未实现

证据：`ky/planner/port.py:97–102`、`tests/contract/test_planner_port.py:55–63`。
`_availability_mapping` 有已解析的 DayBudget，却在登记参数为 True 时把两个新字段写成 None。
新增测试也把这两个 None 当作期望值；contracts/planner_port.md 和 route_plan.md
新段落把字段称为 nullable，偏离 pacing_review.md §5 的解析来源语义。

**具体输入**：当日路线阶段基数 210，没有手填或课表；M8 返回
base_minutes=210、base_source=route、total_minutes=210、total_source=base。
调用映射函数并传 `settings_pacing_registered=True`，代表任务书要求本包先支持的登记参数路径。

**实测结果**：

```text
registered mapping: {'minutes': 210, 'source': 'base', 'base_minutes': None, 'base_source': None}
```

**应有结果**：

```text
{'minutes': 210, 'source': 'base', 'base_minutes': 210, 'base_source': 'route'}
```

传 False 仍只输出旧两键；传 True 输出 DayBudget 的实际值，包括基数 0、pacing_initial
和 config 来源。给函数参数补 DayBudget 类型，修正对应断言及新增的 nullable 规格措辞。
本包装配暂传 None/False 是任务书明文授权，不要求现在读取 settings.pacing 或改 M0；
但“暂不接真实设置”不能变成“参数化路径输出空值”，这项已经在本包范围内。

### B2：timetable show 用配置基数，和目标日解析规格冲突

证据：`ky/__main__.py:1593`、`:1684`、`:1723`；timetable.md §4 第 7 条、§8。
代码调用 `daily_base_minutes(date.today(), config, None, pacing_initial=None)`，
因此既不传目标日期，也不加载已登记路线；周视图随后把同一个配置基数用于七列。
规格明写 show 的基数经 M8 同一解析取得，且“不读当前时间”。

**具体输入**：配置基数 120；已登记合法路线，当日阶段 base_daily_minutes=210；
课表无显式 cap，有三个大节、每大节扣 15，空档充足。
在系统临时工作区写入合成路线，调用真实 timetable_main/show --date 2026-09-15；
只把课表提供者替换为记录传入基数、按 `base - 45` 输出的合成对象。

**实测结果**：同一输入经 M8 为 `210 route`，show 却打印：

```text
cap                : 120
minutes            : 75
show exit: 0
```

**应有结果**：show 使用目标日基数 210，cap=210、minutes=165。
周视图如一周跨两个阶段、基数依次 180/240，各列应取各自日期的基数，扣三大节后分别 135/195。
不需要修改 M18 或 M26；在 CLI 读一次当前路线，日期视图按传入日期解析，周视图按周一至周日逐日解析，
只把解析出的基数传给 timetable.day。不要用手填的 total_minutes 替代基数。
读取 pacing 设置仍可按本包范围传 None。

实现者称“周视图没有调用日预算的目标日期”，这个前提不成立：
`_timetable_show_week` 已计算 monday，并明确构造七个日期；日期视图更有 --date。
配置基数不变不是规格授权的展示策略，不能仅列为以后接线事项。
新加入的 date.today 当前因空路线而不改变数值，但本身违背此显式日期命令的无时钟规则，应一并移除。

### B3：任务书已点名的验收缺口，且旧版身份断言没有区分新旧

**具体输入／现有测试结果**：

- `test_preflight_floor_and_override_follow_resolved_source_and_freeze` 使用 timetable 来源的预算，
  然后验证冻结和 config。没有以 total_source=base 验证 override/drop_when_short。
  若误删 preflight 的 base 分支，该测试仍通过；M19 的新测试也只验证映射，不验证 base 裁剪。
- tests/contract/test_resume_port.py 没有新增跨阶段 base_daily_minutes 用例；
  既有 provider 复用测试 route=None、各日基数相同，不能证明跨阶段逐日取基数。
  实现报告所说“补齐逐日基数例子”不能当作这项验收已覆盖。
- 新 M8 测试的“学期外”例子把路线也放到范围外，结果 180/config；
  没有验证“路线仍有效、课表当日返回 None → 210/base”这一任务书点名输入。
- 基线身份断言只检查未修改的 availability/port.py 含
  `def resolve_daily_minutes(` 和 `base_minutes: int`。
  实测当前文件与固定提交该文件完全相同，旧/新两边 identity 都为 True，
  所以这不是区分 M28b 前后版本的身份断言。

**应有结果**：补任务书已有验收，不另造冒烟或全链路全集：
base 来源的调用方 override/floor 及冻结优先；resume 至少两个阶段的不同基数；
路线有效但课表不覆盖当日的回落；基线源码身份固定检查旧 budget/planning
确实没有 M28b 新端口或字段，并与实际归档源码关联。
例如固定旧 budget 仍是单参数 daily_base_minutes，旧 Phase 没有 base_daily_minutes，
不能把一个两版完全相同的 M26 文件作为唯一旧版身份证据。
修正后的 B1、B2 缺陷验收同属 AGENTS.md 允许覆盖的已发现缺陷，不要求跑全量。

这项属于验收完成度问题：当前 resume 实现的独立探针已显示正确逐日行为，
并不是声称它已算错。若把首日基数套后续日期，现有已提交的测试集合不能有效捕获该退化。

## 二、符合规格／不改

1. **路线 v3 主逻辑正确。** Phase 可选值缺省 None，0 作为带值输出；任何阶段带值则 v3，
   只写该阶段的键，否则保留 v2。解析拒绝 v2 携带新键；整数排除布尔，负值由路线校验拒绝。
   `_check_phase_base` 拆出后职责清楚，保持现有 RoutePlanError 风格。
   本轮运行新增格式单项通过；未要求修改存储版本发布规则。
2. **M8 三级顺序与来源改写正确。** 阶段值以 is not None 判断，不丢基数 0；
   无阶段值再检查 pacing 的 start，最后配置。
   只有 M26 返回 config 且选中非配置基数时才改为 base；手填和 timetable 来源保留。
   配额硬上限仍按实际 total_minutes 缩放，不用扣课前基数掩盖容量不足。
3. **主要调用方的 base 分支已实现。** preflight/M19 都把 base 纳入 override 和
   drop_when_short，冻结分支优先且不传阶段配额；config 留旧路径。
   M19 一次加载路线对象，用同一对象生成预算和 route_plan.phase，没有新增路线二次读取。
4. **resume 确实逐日调用 M8。** `_first_fit_day` 按候选日期建立容量缓存，
   `_capacity_for_day` 传入该日期。独立合成探针：两阶段基数 180/240，同科两项各 100 分钟，
   provider 记录收到 `(2026-09-15,180)`、`(2026-09-16,240)`，两项分别安排在这两天。
   这支持实现正确，但仍应按 B3 保存任务书指定的可重复验收。
5. **M18/M26 边界保留。** diff 未修改 ky/timetable、ky/availability/port.py 或 ky/workspace.py。
   M8 传入当日基数，M26 来源仍保持原三值，M8 自己映射 base。
   不要求为 B2 修改课表计算内部，也不要求提前接真实 pacing 设置。

## 三、固定基线对照判断

`test_unregistered_m28_commands_match_dcbb5b6_bytes` 固定字符串 dcbb5b6，
`git archive dcbb5b6 ky` 从提交对象提取源码，而非当前未提交工作区；没有用 HEAD。
三个主注册表夹具分别无路线、已登记但尚未开始、进行中，路线存储目录按夹具区分，
不会互相覆盖。每个命令运行前从同一 seed 恢复工作区，旧/新执行隔离到各自 PYTHONPATH。

覆盖 preflight 文本和 JSON、day/route planner-input、resume --dry-run、route show --json。
compare_runs 比较退出码、原始 stdout/stderr 及工作区文件树字节，没有对结果作正则归一化。
正常命令要求退出 0；无路线登记的 route show 单独按既定错误退出 2，不把其他相同失败算通过。
本轮运行整个日预算模块时，此对照实际通过。

不足分别是 B3 的身份检查，以及覆盖边界：夹具没有登记课表或手填，route show 只测 JSON。
这不否认已覆盖三种路线状态与主要命令；但不能把其结论扩大成“所有 M18 日常路径均已做字节对照”。
任务书未明要求的额外课表旧字节场景列建议，交决策者决定，不自行扩大验证集。
§9 的 e381792/4816a14 全模块兼容验收属于后续整合，本包按指定 dcbb5b6 验证，不据此要求全量。

## 四、建议改

- **规格整理**：四份规格多数只在末尾或 CLI 节追加新段，原先“固定 v2”“不从路线读取总分钟”
  等规范语句仍保留。timetable 新段还写“M26 fallback reports total_source: base”，
  实际是 M8 改写。建议直接修订旧规范或明确覆盖关系，并改正归属，避免下个实现者选错权威段落。
- **D7 端口声明**：PacingInitial 没列入 budget.__all__/模块头公开接口，协议字段是可写属性声明，
  与文案“只读”不完全一致；可用只读 property 定义并补公开接口说明。
  `_availability_mapping` 的 DayBudget 类型应随 B1 补齐。
- **验证建议**：若决策者要扩大旧字节保证，可在现有固定基线用例中增加已登记课表的正常日与学期外日，
  及 route show 文本；不是本轮另跑的测试，也不要求增加独立冒烟集合。
- **公开参数校验边界**：新 daily_base_minutes 直接比较 day/start，或直接返回 initial。
  当前文件加载路径提供已验证对象，未观察到正常 CLI 崩溃；但协议未声明参数已校验的前置条件。
  按已知缺陷第 6 条，建议明确并落实新公开参数的类型/非负整数契约，避免之后接线把 TypeError 或 bool 传下去。
  本轮不以手工畸形对象为正常数据路径的阻断反例。

AGENTS.md 清单核对：本包没有新增发布文件路径，不改变原子存储；正常来源缺失/无效的原有
fail-closed 和路径边界未被削弱；新代码没有根据错误消息分流、没有硬编码生产科目/学校。
已有一次读来源约束保留，固定源码对照没有宽泛归一化。D7 的主要新增函数较短、模块边界可替换；
需要修的是上述声明与规格一致性，不要求重构其他模块或删历史防护。

## 五、实测验证与限制

在被评审 worktree 运行：

```text
py -3.12 -B -m unittest tests.contract.test_day_budget_port
Ran 16 tests in 13.663s
OK
```

另仅运行两个直接相关单项：

```text
tests.contract.test_route_plan_port.TestRoutePlanFormat.test_optional_base_uses_v3_and_v2_rejects_the_field
tests.contract.test_planner_port.PlannerPortContractTests.test_pacing_registration_adds_nullable_base_fields_to_availability_shape
Ran 2 tests in 0.031s
OK
```

第二个通过表示当前断言吻合当前错误输出，不能推翻 B1。
三条独立只读探针分别确认 B1/B2 输出、resume 跨阶段传值、基线身份断言不能区分新旧。
探针的工作区及路线是系统临时目录中的合成数据；未写任何仓库实现文件。
`git diff --check` 无输出。未重复实现者的七模块验收，未跑全量或冒烟。

## 六、安全登记

无新增独立安全登记。B1/B2 属正常设置和正常展示路径的规格偏差；B3 属明列验收缺口，
均不降为攻击风险。既有恶意链接、并发插手和手工篡改存储的威胁模型不扩展，不为此要求返工。

接受条件：修 B1、B2，补 B3 的点名验收与旧版身份断言，重跑受影响的最小模块/单项后复审。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
