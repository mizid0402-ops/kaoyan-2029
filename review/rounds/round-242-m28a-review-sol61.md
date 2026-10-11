# 第 242 轮：WP-M28a 实现评审

结论：**FAIL**。确认决策者已有两项返工；另有两项日常路径缺陷：
参考容量没有使用已登记的手填/课表，状态来源路径没有按工作区真实登记位置生成。
完成事件 v3、周期主体、复习统计、冻结锁存与只写一次协议的方向正确。

评审范围：`F:/workspace/kaoyan-wt-m28a` 未提交改动，HEAD 为
`dcbb5b6c278203b1df2cf9f37bcd434fa26f9229`。
已核对 git status/diff、AGENTS.md、任务书、实现报告、指定规格和相关来源端口。
只新增主仓库本报告；未联网、未读仓库外文件或个人数据、未修改实现或测试、未提交。
下面的输入均为合成数据；注明“实测”的条目才是本轮执行结果。

## 一、必须改

### A1：确认已知 D7 问题，两个函数需要按职责拆分

AST 静态计数确认 `ky/pacing/port.py:225` 的 build_report 为 107 行，
`ky/pacing/storage.py:64` 的 _validate_report 为 79 行，与决策者记录一致。
前者混合参数、复习去重、统计、队列观测和输出组装，后者混合多组字段校验和摘要检查。
按 AGENTS.md 拆成有名辅助函数，保持报告字段与原字节行为；不需要借此重构其他模块。
作为已知返工项确认，不重复论证或另开验证轮。

### A2：确认已知配置回退问题，未登记应报契约错误

`ky/pacing/cli.py:84–85` 在 --config 缺省且 settings.exam_config 未登记时，
拼接 workspace.root / kaoyan_config.yaml。违反 workspace.md §1 的登记路径约束。

可复现输入：主表只登记有效 settings.pacing；既无 --config，也无 settings.exam_config；
根目录恰有一份合法 kaoyan_config.yaml。当前会采纳该约定文件，应退出 2，
提示显式 --config 或登记 settings.exam_config，不发布报告。
缺省文件不存在时也应报告“未登记”，不把约定文件找不到当成真正的数据源错误。
本轮按实际代码静态确认，不重复决策者已有问题的完整实测。

### A3：reference_minutes 直接求基数和，漏掉正常手填与课表容量

证据：`ky/pacing/port.py:255` 每天只取 daily_base_minutes(config)，
`:308` 把 reference_minutes 设为 sum(bases)；CLI 没有加载 availability/timetable 或传入逐日总分钟。
因此已登记文件的存在、格式与内容均没有参与报告。

**可复现输入**：半月周期 [2026-10-01,2026-10-16)，配置基数 120，
settings.pacing 有效；state.availability 登记到 data/availability.yaml，
文件中只有 2026-10-01: 0，其他十四天无手填，无课表。
调用 report --cycle-end 2026-10-15 --today 2026-10-16。

**实测结果**：reference_minutes=1800。
**应有结果**：0 + 14 × 120 = **1680**；base 仍为 120，不因手填而改变。
若课表一天把总分钟从 120 扣到 75，亦应少计 45，不把参考容量永远等同基数总和。

这还影响重复运行：只修改已登记手填/课表，sources 不变，命令不会输出规定的来源变化提示。
已登记 availability 文件缺失或无效，当前也可能照样发布配置容量报告，而非 fail-closed。

任务书允许本包的**基数解析**暂用现有配置签名，不要求先做 M28b 的路线/pacing 三级解析。
但 §3 的 reference_minutes 明文是逐日 M8 总分钟（手填 > 课表 > 基数），
M26/M18 接口在 dcbb5b6 已存在；暂用配置基数不等于授权忽略这两类总容量来源。
修法应保持范围：装配一次加载现有手填/课表对象及摘要，逐日使用现有 M8 总分钟端口，
把结果传给纯报告计算；冻结日照算参考容量。不要把已落盘 declared_minutes 当作代用品。
补本缺陷的合成验收及来源变化提示验收，不要求全量。

### A4：sources 的状态键是假路径，无法追溯实际被读文件

证据：`ky/pacing/cli.py:97–100` 使用 `state.plans/<name>`、
`state.review_queue/<name>`，其中前缀是注册表键名，不是登记目录。
state_sources.md 明确返回路径相对各自存储根；M28 §3 要求转换成工作区相对 POSIX 路径。

**可复现输入**：主表 state.plans=data/plans、state.review_queue=data/queue。
在 data/plans/2026-10/completion--2026-10-16.yaml 写一份合法完成事件，
队列由 ReviewShardStore 写到 data/queue，然后生成上述半月报告。

**实测结果**包含：

```text
state.plans/2026-10/completion--2026-10-16.yaml
state.review_queue/manifest.yaml
state.review_queue/shards/<科目分片名>.yaml
```

这些键拼到工作区根后均没有对应文件。
**应有结果**分别是 data/plans/2026-10/completion--2026-10-16.yaml、
data/queue/manifest.yaml 和实际分片路径；摘要仍取同一次读取的原始字节。

按 workspace.plans / workspace.review_queue 与端口返回相对路径组装，再转换为工作区相对路径，
不重新读文件计算哈希。上一份报告已有实际相对路径的做法可以保留。
当前 `_relative_path` 对工作区外显式配置直接回退 basename，也不能证明是工作区内路径；
任务书需明确这种显式覆盖的来源表示/拒绝规则，不能静默伪装成同名根内文件。
本轮没有读取或构造仓库外配置，后一句是静态接口边界提醒，不是额外攻击复现。

## 二、字段口径复核与不改

| 字段／行为 | 判断 |
|---|---|
| 设置与周期 | 字段闭合、布尔整数拒绝、日期严格解析、首项起点、until 月初且递增、右开周期及闰年规则实现正确；start 前返回 None |
| cycle / generated_on | CLI 检查合法终日、D<T，生成日传入纯函数；cycle.days 由日期差取得 |
| base | 本包按任务书暂取配置，min/max/mean 公式正确；完整三级解析留整合，不要求本包做路线字段 |
| reference_minutes | A3，不能以配置基数总和代替已有 M8 总容量 |
| declared_minutes | 读取 current 日计划对象，按 plan.day 归期，天数去重、分钟求和，保留与参考容量不同的含义 |
| recorded_event_days | 按周期内不同 event.day，空事件计入；不误用可选实际分钟来判活动天数 |
| study_minutes | 缺失不计，0 计入填报天数；按 event.day 归期，分钟求和 |
| reviews | 从全部完成事件按 completed_on 归期，不按文件事件日预过滤；按 completion_id 去重选最早 event.day |
| reviews_unattributed | 生成时队列找不到 review_id 则计数，不猜科目、不静默删除完成证据 |
| miss_ratio | partial+incorrect 为分子，排除 none；分母 0 为 null；Decimal 三位半偶舍入 |
| duplicate_completion_ids | 实现按全部读取事件累计额外次数；与规格当前未限定此计数归期范围的文字一致，不在本轮另选周期过滤规则 |
| backlog_observed | queued/scheduled 且 due_date<T，observed_on=T；不是周期末历史快照 |
| freeze | 周期内事件计数；latched_at_end 先过滤 day≤终日，再调用既有按 sequence 与日期解除条件的 latch_active，不回算历史阈值 |
| due_next | 下一周期右开区间、queued/scheduled、每项当前 estimated_minutes 一次；不把后续全部复习轮次作为可观测值 |
| previous | CLI 只找 cycle.start 前一天所在周期的报告；缺文件为 null，不回找更早报告；保存要求的五个指标字段 |
| report_hash | 新报告在字段尚无 report_hash 时按 M19 规范 JSON 求摘要；读回剔除自身重新验证，未发现自引用 |
| sources | 一次读字节后传摘要正确；路径转换有 A4，遗漏容量来源有 A3 |

独立实测补录输入：event.day=2026-10-16，completed_on=2026-10-10，check=none。
1–15 日报告 recorded_event_days=0，reviews 对应科目 completed=1、none=1、miss_ratio=null。
这证明跨周期补录可计复习而不计周期内事件天数，口径合理。

只写一次存储正确采用临时文件、重读校验、os.link；目标已存在时读回保存版本，
不覆盖、不向旧硬链接写穿。正式重复 CLI 读取保存报告，sources 不同才额外提示，返回 0。
独立重复运行得到同一保存映射且 changed=False；模块现有用例也验证了设置变化提示与目标原字节不变。
不要求为恶意并发替换扩大锁机制，也不删除已有原子存储保护。

## 三、实现者三处自选歧义

- **source_note 字段名：合理。** 规格要求明示重算口径，没有固定说明字段名称；
  base.source_note 与 reference_source_note 保持数值本身类型。建议在规格字段表登记确切形状，
  不让后续 M28c 另起一个名称。base 说明最好明确“路线与设置”也是生成时当前值。
- **sources 包含上一报告：合理。** 本次确实读了它，摘要来自同一字节串，属于实际来源。
  不含当前报告自己，不造成 report_hash 自引用；补存更早报告也不会改写后来的保存报告。
  这项不修，A4 修的是其他状态来源键。
- **仅列出现过的科目：可接受。** reviews/due_next 当前契约只要求按科目映射，
  没要求全注册科目补零；缺科目不构造 miss_ratio 观测值。后续 AI 输入应区分缺行与已观测值，
  不能因此声称缺行科目“没有错题”。建议明确稀疏映射约定，不要求本轮新增零行。

## 四、完成事件 v3、M0 与固定基线

M0 增加 settings.pacing 和 Workspace.pacing，并加入 require 路径表；
主表/本地表解析沿既有严格规则，重复登记错误为 local.settings.pacing，local_sha256 流程保留。
主表能力用于合成夹具或非个人示例；真实个人设置按 §8 放本地登记与忽略路径。
CLI 已登记 pacing 不存在/格式无效会退出 2，不被当作未登记。

完成事件 None 写 v2、不输出 study_minutes；0 或正值写 v3；v1/v2 读取 None，
v3 有值才接受，排除布尔、负值、字符串。旧质量记录与 v2 的 check/outcome 解析保持原逻辑。
没有把缺失分钟默认为 0，也没有修改既存文件。

固定对照使用 dcbb5b6，fixed_source 的旧 workspace 身份检查明确要求无 pacing 字段，
与当前源码能够区分；git archive 提取同一固定提交，不用 HEAD。
主注册表合成夹具无本地补充，旧/新以独立 PYTHONPATH 运行，各命令恢复同一 seed。
compare_runs 比较原始退出码/stdout/stderr 和文件树字节，要求成功退出 0，无宽泛归一化。
覆盖 day-plan record、preflight 文本/JSON、planner-input --kind day，符合本任务所列命令。
本轮 pacing 模块中的该测试实际通过。

它的 record 输入是空 reviews/vocab 的无分钟事件，文件树对照确实包含写出的完成事件。
另做固定提交旧 `_completion_event_mapping` 的独立字节探针：合成事件含 exercise/partial、
completion_id 与非空词汇，study_minutes=None；旧固定函数按旧常量 2 执行，
经既有 YAML 字节函数与当前结果比较，结果 **True**。
因此本轮没有观察到无分钟的非空完成事件字节变化。

## 五、建议改与验证范围

- 公开 build_report 虽校验 settings/config/cycle/date 类型和区间，未校验 cycle 确实是设置下周期、
  或 end<today；CLI 已负责这些正常入口检查。建议声明纯函数前置条件，或补契约检查，
  不据未经 CLI 的手工畸形参数扩大日常缺陷判定。
- _validate_report 对 backlog.by_subject、previous 的内层只作部分检查，
  对 min≤mean≤max、计数和等也不作语义交叉验证。当前生成器产生合法形状，
  恶意重算 hash 后手改报告属安全登记范围；拆函数时可整理完整格式规则，
  不要求为人工篡改增加单独返工轮。
- report_to_mapping 返回浅拷贝，docstring 的“detached”不代表深层字典也已分离；
  公开说明应准确，不鼓励调用方修改共享嵌套对象。
- 任务书称 M28b 改签名后报告“自动跟上”并不准确：当前仍调用 daily_base_minutes(config)，
  M28b 是按日期、路线、pacing 参数返回二元组。后续 M28c/整合任务必须明确此装配接线，
  不能直接合并后认为已完成；本轮不要求 M28a 越界实现 M28b。
- 返工验收只覆盖 A1 保持字段/字节、A2 未登记配置、A3 容量来源与变化提示、A4 真实相对路径。
  已知缺陷清单的一次读、先校验、不按错误文字分流、原子不覆盖等按上述范围核对，
  不跑或建议另加全量/冒烟集合。模块头已有 M28/规格/公开接口；模块地图本包明文禁止改，保持不改。

## 六、本轮执行证据

```text
py -3.12 -B -m unittest tests.contract.test_pacing_port
Ran 7 tests in 4.364s
OK
```

另只跑新增完成事件的两个相关单项：

```text
tests.test_completion.ParseCompletionEventTest.test_study_minutes_distinguishes_v1_v2_v3_and_zero
tests.test_completion.ParseCompletionEventTest.test_study_minutes_rejects_bool_negative_and_old_schema
Ran 2 tests in 0.000s
OK
```

独立探针在系统临时工作区验证 A3/A4、跨周期补录、重复返回；
内存中固定源码探针确认非空无分钟事件字节不变；AST 确认 A1 函数长度。
命令设置 PYTHONDONTWRITEBYTECODE=1；没有写仓库实现或测试文件。
git diff --check 无输出。未重复实现者的六模块验收，未跑全量。

## 七、安全登记

没有新增需要扩大当前工作包的独立攻击防护。
记录一项格式验证边界：手工修改已保存报告的 previous 内层或 backlog.by_subject，
并自行重算 report_hash，可绕过现有部分内层格式检查，后续消费方可能遇到非法值。
触发须篡改内部报告及摘要，属既定安全登记范围；可能修法是完整递归格式校验，
不算本轮必须改，不为此开返工轮。恶意链接、并发插手沿原风险范围保留。

接受条件：随既定返工处理 A1/A2，同时修 A3/A4，按受影响的最小模块/单项验收后复审。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。
