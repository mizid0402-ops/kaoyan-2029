# 第 208 轮：技术债包 B 再返工复审（sol61-main）

结论：**FAIL**。第 206 轮 R1、R3、m1、m2 已落实；workspace 必填顶层块和
revision=True 也已补齐。R2 的归并表仍把不同输入的测试当成等价保护，确有独立断言
尚未迁移。问题不是“每个原实例必须单独写一个方法”，而是部分输入类别没有当前直接保护。

范围为第 207 轮对 tests 的修改及其 R2 去向核对。已读 207 任务书、实现报告、206 评审、
AGENTS.md，并应用 code-review-gate。原输入从固定提交
`f52b8f6f2a6145e86970844278acf197184597d9` 取证；没有读取另一评审窗口报告。
没有修改实现或测试，没有提交；本报告是本轮唯一仓库写入。全量未跑。

## 必须改

### R2-a：配置类型和子字段缺失的去向不等价（MAJOR）

出处：原 `tests/contract/test_models_split_baseline.py::_config_variants`。
以下输入均以原 config-minimal.yaml 为合法底稿，未提及的字段保持不变。

| 具体原输入 / 原期望 | 映射核对与缺口 |
|---|---|
| `config-project-id-type`：project_id=12；ContractError | 报告指向 integer 字段测试和首错测试。前者不测 project_id；后者使用空字符串与 budget=0 的双错误组合。不是数字 project_id 的拒绝。 |
| `config-subject-id-type`、`config-subject-active-not-bool`：subject_id=True、active=1；ContractError | subject ID 方法使用非法字符串；首错方法里的 active='yes' 位于另一 subjects=[] 错误之后。没有这两种原字段类型输入的直接拒绝。 |
| `config-subjects-type`：subjects='not-a-list'；ContractError | 首错测试及 ConfigContractTest 测的是 subjects=[]，属于空合法容器，不是字符串类型。没有报告声称的 subjects 类型直接断言。 |
| `config-subject-{index}-missing-{subject_id,display_name,weight,active}`：逐项删除；ContractError | 所指 `test_each_subject_field_is_required_except_min_daily_minutes` 不存在。未知子键、非法字段值、根字段缺失不等于这里的必填子字段缺失；display_name=None 也不能保护“只在缺键时默认”的回归。 |

独立源码变异证明第一项不是纯文档笔误：在临时 ky/models.py 中，仅对整数
project_id 先 str() 再调用原 `_require_str`。原 project_id=12 从 ContractError 变成成功；
`ConfigFormatTests` 加 `ConfigContractTest` **34 条仍通过**。
缺键、空字符串等拒绝仍保留，所以不是以其他失败替代该类型行为。

修法：把上述缺项作为当前契约表驱动用例迁入；检查 ContractError，不依赖旧版。
subject 的可选 min_daily_minutes 缺失成功已有 base_config_mapping 等合法输入使用，
无需为每个科目索引重复写相同规则。

### R2-b：ReviewItem 类型 / feedback / schedule 的具体缺项仍在（MAJOR）

出处：同一原文件 `_review_variants`；合法底稿为原 reviews-normal.yaml 的第一项。
下表每次只替换指定字段，期望都是 **ContractError**。

| 抽查发现没有真等价的原变体 | 可复现输入与原因 |
|---|---|
| `review-type-review_id`、`review-type-subject_id`、`review-type-title` | review_id=1、subject_id=1、title=True。缺键测试不是现有值的类型拒绝；unknown subject ID 是合法字符串的跨配置语义拒绝。 |
| `review-type-granularity`、`review-type-state`、`review-type-self_rating` | 各字段=[]。现有 unknown_* 方法传入非法字符串，只检查枚举拒绝，不检查列表类型。 |
| `review-type-estimated_minutes`、`review-type-defer_count`、`review-type-last_quality` | 各字段=True。minutes 超上限、defer 优先级和 quality 映射都不是布尔值作为整数的输入。revision=True 的新测试只针对 revision。 |
| `review-type-introduced_on`、`review-type-due_date`、`review-type-last_reviewed_on` | 各字段='not-a-date'。due_date 在 introduced_on 之前的测试使用可解析日期，是不同拒绝类别。 |
| `review-type-schedule`、`review-root-not-mapping` | schedule=[]、整个 review=[]。报告对后者按首错脚手架退役，但原表是单错误输入，独立固定当前失败 / ContractError，不能这样退役。 |
| `review-last-quality-over-range`、`review-last-before-introduced` | last_quality=6；last_reviewed_on=introduced_on−1 天。progress port 检查正常推进的 quality / 日期结果，没有这两个原拒绝输入。 |
| `review-phase-bool-int`、`review-repetitions-bool-int`、`review-lapses-negative` | schedule.phase=True、repetitions=True、lapses=-1。现有 phase/mode 一致性用例不是这些类型 / 下界输入。 |
| `review-interval-lower-bound`、`review-ease-out-of-range`、`review-mode-invalid` | schedule.interval_days=0、ease_factor=1.0、mode='other'。ease=9.0 的上界拒绝不能替代下界；合法 mode 配合错误 phase 不能替代未知 mode。 |

报告提到的 ReviewItem “类型、日期、feedback 专项测试”没有相应方法或上述输入；
`test_review_progress_port.py` 的六个方法主要检查正常算法推进，而不是这组模型输入校验。
本轮检查了所指测试的正文，并搜索当前 tests 的相关字段引用；没有只按方法名推定等价。

独立源码变异：把 `_review_item_feedback` 中 last_quality 的 maximum=5 改成 6。
原 `review-last-quality-over-range` 从拒绝变成成功；报告指定的整个
`ReviewItemContractTest` 和整个 `test_review_progress_port` **19 条仍通过**。
这直接否定了该行“progress port 已有等价”的说法。

修法：按上述原单字段输入补当前拒绝表。已经有真等价的 unknown key、NaN、枚举、
cap 和 due-before-introduced 不要重复迁移；原多错误新旧全文 / 次序比较也不要求恢复。

### R2-c：workspace 表的几组结构去向也不成立（MAJOR）

新增顶层缺失表正确，但不等于原注册表所有单错误结构变体已有去向。
出处为原 `tests/contract/test_workspace_split_baseline.py::_registry_variants`。
以固定提交 kaoyan.workspace.yaml 为底稿，subject 使用其首个登记科目，每项只改所列位置；
原期望及当前实测均为 ContractError。

| 具体原变体 / 输入 | 所指测试实际保护 |
|---|---|
| `schema-version-type`：schema_version='2'；`reference-type`：reference=[]；`subject-profile-type`：subjects[subject]='profile' | `test_3_structure_rejections_report_contract_paths` 没有这三项；它有整数 / 布尔 schema 值、subjects 列表、缺 profile.name、未知 profile 字段等，属于其他类型或结构输入。 |
| `syllabus-versions-type`：reference.syllabus_versions=[]；`syllabus-record-type`：该科记录='record'；`syllabus-versions-empty`：versions={}；`syllabus-mappings-type`：mappings='mapping.yaml' | 指向的 syllabus 方法检查有效指针、整数年份标签、未知科目、重复路径、有效树不匹配，未传入这四种形状。 |
| `syllabus-invalid-label`：versions={'bad':'data/tree.yaml'} | 现存标签拒绝传入整数 2026；它不能保护“字符串但不是四位年份”的输入。 |
| `paper-shapes-type`：paper_shapes=[]；`paper-shapes-invalid-path`：{subject:'../paper.yaml'} | 现存结构测试检查未知科目的 paper shape；路径表主要检查 topic_weights 和 weight_batches，并未检查 paper_shapes 的已登记科目路径。 |
| `weight-batches-type`：weight_batches=[] | optional 方法只检查缺失成功；路径表检查 '../outside.yaml'。列表类型不是缺失或非法路径字符串。 |

这些是原表的单错误接受 / 拒绝保护，不是首错组合。请补进当前 workspace 契约表，
保持直接 ContractError 期望。无需保留旧异常全文，也无需为相同规则的所有科目重建实例。

## 建议改

### m1：去向表使用真实的类 / 方法名，并修正可选字段表的描述（MINOR）

ConfigPortTests 实际为 ConfigFormatTests；首错方法实际带 `_wins`；weight-batches 方法
实际为 `test_4b_weight_batches_registration_is_optional`。不少配置拒绝方法实际在
ConfigContractTest，不在报告所写位置。应使用可定位的完整限定名。

新 `test_required_review_and_schedule_fields_cannot_be_omitted` 使用的
base_review_mapping 原本不含 last_reviewed_on / self_rating，遇到它们就 continue。
因此不能描述为该方法“逐项删除三个可选字段后成功”。这两个缺键成功仍由当前
ReviewProgressPort 的 make_item 和现存合法 base mapping 调用实际覆盖；本项不单独阻断。
建议用含三个可选字段的原合法首项构造删除表，或如实写明这两项的现存去向。

## 不改：本轮修复与每类抽查

| 类别 / 修复 | 本轮结论 |
|---|---|
| R1 migrate | 先写合法空队列；stderr 同时检查 unregistered-version / mappings，退出 2，无 traceback。正式方法实跑通过，前轮“缺队列”假通过已堵住。 |
| 其他新增 CLI 诊断 | missing config 检查 file does not exist 和文件名；revision=0 检查 revision；empty queue 检查 OK；empty route 检查 stdout 非空。五个方法实际通过。 |
| R3 rights | None / 字符串 / {} 各断言 ValueError；unknown_right 由现有未知 rights 子键拒绝等价覆盖。新方法实际通过。 |
| m1 citation fixture | raw/manual、空 transition_history、unreviewed 与 unclear.may_be_structured=True 已恢复。六项完整 reason 列表和顺序保留，实跑通过。 |
| m2 freeze / advance | 两条强制错误标记均正式断言。冻结失败仍无完成事件；推进失败仍已有一份完成事件。真实子进程测试通过。 |
| config 类型 | schema_version=True、default_daily_minutes=True、ratio=True、min_daily_minutes=False 有直接类型表；display_name=True 有直接拒绝。接受这些归并，不要求重复实例。数字 project_id 等缺口见 R2-a。 |
| config 范围 | 负 reserve、hard ratio>1、hard=0、hard<reserve、非有限 weight/reserve、总权重不闭合和 floor overflow 均有同类当前保护。路径不同但只是原首错比较的部分不恢复。 |
| config 结构 | 根必填缺失、review_policy 缺失默认、未知根 / subject 子键、空 subjects 与非 mapping 文件根有直接保护。部分子字段 / 字符串 subjects 缺口见 R2-a。 |
| review 必填 | 新表覆盖必填 review 字段及全部 schedule 必填字段；revision=True 专项通过。knowledge_point_id=None 与已有该字段缺失后传给同一校验的 None 拒绝相符，不重复要求。 |
| review 值 | state / granularity / self_rating 非法枚举、超 cap、vocabulary 太长、due-before-introduced 有真等价；feedback 范围和 last-review 日期缺口见 R2-b。 |
| review 未知键 / schedule NaN | 实际去向是 ConfigContractTest.test_unknown_review_item_field_rejected、test_unknown_schedule_field_rejected、test_non_finite_ease_factor_rejected；报告所指 reviews 文件根 / unknown state 不等价，但保护本身没有丢。 |
| workspace 顶层块 | 新方法实际逐项删除，三个可选块成功、其余 ContractError，无恒 skip；临时源码放过缺 state 后变红。 |
| 首错组合 | config cross-section pairs、review identity/category/date order probes、workspace double-error / paired order probes 的新旧文字与先后比较接受退役。原 root-not-mapping 单输入不属于这一类。 |

## 独立变异与复现

实现者测试侧 patch 的结论应限定为“所选断言会检测该故障”：
revision wrapper 把 True 转为 1、rights wrapper 把 None 换成合法 rights 后，
assertRaises 应变红；no-op 队列写入使 CLI 落入缺文件路径，诊断断言应变红。
它们不是恒假测试，也足以证明这些断言对指定错误结果敏感，**不证明真实源码分支已变异**。
本轮不因采用 patch 方式另开返工；未完成的两处由独立源码探针补验。

探针均在系统临时目录：

```powershell
$env:PYTHONIOENCODING='utf-8'
py -3.12 -B $env:TEMP\round208_probe.py
py -3.12 -B $env:TEMP\round208_inputs.py
```

最终证据目录：`C:\Users\Lenovo\AppData\Local\Temp\round208-sol61-jkf7muh5`。
保存每次 stdout、stderr、runner 及临时 ky 副本。临时 runner 断言 ky.__file__ 来自指定
checkout；M2 的真实 CLI 子进程另外断言 cli.__file__ 来自同一副本，避免测回工作区源码。
正式测试源码仍从当前仓库读取，未修改正式断言。

| 源码探针 | 结果 |
|---|---|
| workspace `_parse_state` 把必填读取改成缺 state 时补合法默认块 | 未变异 1 条通过；变异 1 条失败，missing='state' 子测试报 ContractError not raised。 |
| CLI `_day_plan_record_preflight` 提前打印 earlier unrelated failure 并抛 _CliExit(2) | 未变异 freeze 方法通过，stderr 为 forced freeze write error；变异退出仍为 2、无完成事件，但在错误标记断言处失败。旧的 2+无事件条件会假通过，新增诊断确实防住。 |
| feedback maximum 5→6 | last_quality=6 变成 ACCEPT；ReviewItem 与 progress 指定 19 条仍通过，见 R2-b。 |
| 整数 project_id 先转换字符串 | project_id=12 变成 ACCEPT；配置两组指定 34 条仍通过，见 R2-a。 |

复核两个存活变异的原输入：

```powershell
py -3.12 -B $env:TEMP\round208_inputs.py $env:TEMP\round208-sol61-jkf7muh5\quality
py -3.12 -B $env:TEMP\round208_inputs.py $env:TEMP\round208-sol61-jkf7muh5\config
```

输入探针从固定提交读取原三份 YAML，并按原生成规则单项替换。
正确源码输出 `review-last_quality-6 ContractError <item>.last_quality` /
`config-project_id ContractError project_id`；对应副本输出 ACCEPT。
workspace 结构表及 review 类型 / 下界表也分别实测为 ContractError。

此外直接运行本轮十个相关正式方法：五个 SnapshotCliTest 新场景、advance 故障方法、
两个 ReviewItem 新方法、rights 方法、citation 聚合方法，结果 **10 tests，1.645s，OK**，
无 skip。workspace / freeze 的正常验证单独各 1 条通过。
探针迭代仅重跑其直接相关方法 / 类；没有全量或冒烟测试。

## 临时文件与安全登记

检查 git status、`rg --files review tests` 中 probe / mutant / mutation / temp 文件名：
没有第 207 轮探针或变异源码遗留，命中的 probe-root 文件均为既有 D11 任务书 / 报告。
`git diff --check -- tests` 通过；本轮 ky 的工作区 diff 为空。

没有新增安全登记。上述必须改均为已删契约保护的真实缺口，未要求扩展恶意输入、
链接攻击或竞态防护。R2 修复应只迁入缺失的当前断言，保留“收敛并退役”的既定方向。
