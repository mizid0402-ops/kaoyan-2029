# 第 250 轮：WP-M28c 实现评审

结论：**FAIL，暂不可合并**。核心事务协议和设置接线方向正确，但变更摘要失真、
分流前的启用检查阻断既有意图恢复，恢复/失败文案缺项；指定测试覆盖和旧版身份断言也需补齐。
不要求重做意图协议，不重开已知 IO2 接线与 apply_pacing 拆分工作。

实际 worktree HEAD 为 `636bd093c855fbb17d531d4d6f348f8ef860bdca`，
该提交是 M28a 合入 8eca5be 后的 M28c 起点；任务书“基于 8eca5be”应理解为其祖先，
不是当前 HEAD。固定新增对照取 636bd09 与这一实际状态相符。
核对本 worktree 的 status/diff、新增文件、247 轮任务书/实施报告、M28 规格、233 轮细节及相关端口。
只新增主仓库本报告；未联网、未改实现/测试、未提交，未读取个人数据。
探针数据均自行合成；读取限于项目仓库及验证生成的临时数据。

## 一、必须改

### C1：变更摘要用新路线当旧路线，缺证据实值与边界说明；切段 label 不符规格

位置：`ky/pacing/submit.py` 的 `_print_change_summary`、`_submit_new`、待恢复分支；
`ky/pacing/port.py:476` 的切段 label。

**可复现输入**：当前 r1，阶段 [2026-10-01,2027-01-01)，基数 180，
配置全部在考科目各 10 分钟；设置 exam_date=2028-12-23。
保存 10-15 报告，10-16 生成输入包；合法方案 effective_from=10-17，基数 195，
各科 20，理由证据为 report.base.mean。运行 submit --dry-run --today 2026-10-16。

**实测**：成功退出 0，base 为 180 -> 195，但每科均显示 **20 -> 20**。
只打印 evidence 路径，不打印其值；没有明确的阶段失效说明、生效上限来源或课表缩放说明。
实际传给摘要函数的是 proposed_route，旧配额已经被覆盖。
正式提交还在发布意图和路线之后才打印摘要，与 §6“通过后打印摘要，再两步写入”的顺序不符。

**应有结果**：各科 **10 -> 20**，report.base.mean 的实际值 **180**；说明调整仅持续至
该阶段结束、生效日上限来自较早的路线 target_exam_date，而非 settings.exam_date，
以及课表降低总容量时 M8 还会缩放复习配额。新提交先打印摘要，再正式发布。
恢复摘要的旧配额与证据值应取保存输入包的 current_route/report，候选取意图，
不为展示读取当前设置，也不能用本次不同方案覆盖确认过的内容。

同一输入的切段 label 当前为 `phase 转复盘 2026-10-15`；§7 要求
`phase · 复盘 2026-10-15`。这是本轮新增用户可见输出差异，按约定修回并加实质断言。

### C2：pacing 登记检查在分流前，正常停用设置后已有事务不能收尾

位置：`pacing_submit_main` 在找到输入包和检查意图之前要求 workspace.pacing 非空。

**可复现输入**：上述合法提交在写意图之后、发布 r2 前因 I/O 失败中断；
保留方案、输入包、意图、state.plans/state.routes/staging 登记。
用户正常移除 settings.pacing 登记以停用周期复盘，然后重跑同一命令。

**实测**：退出 2，`settings.pacing: settings.pacing is not registered`；没有走恢复表。
这是启用检查挡住恢复，不是意图或路线损坏，也不要求篡改内部状态。

**应有结果**：先按保存输入包定位 D、查意图，再分流。当前路线仍为 base_revision 时，
正式运行发布保存候选，dry-run 预告恢复且不写；移除当前 pacing 设置不撤销已经确认的事务。
仅新提交分支要求当前设置登记并有效。§6.2 的“恢复只用意图内容与存储状态”优先于新提交启用条件。
当前代码确实没有在恢复分支加载设置文件，但分流前的登记门槛仍使恢复不完整。

### C3：恢复与发布失败输出没有落实 233 轮指定语义

**输入一（已应用后又有新修订）**：意图目标 r2 已成功发布，用户正常再提交 r3。
重跑原 submit --dry-run。独立探针确认退出 0、只读一次 manifest、不再发布，
但首行仍是“本报告已有提交；将不发布（dry-run）”，没有说明这是**历史应用**。
**应有结果**：说明 r2 是该报告的历史应用、当前已有更高修订，展示意图摘要且不发布；
正式运行亦须同样区分，避免把旧方案当作当前路线。

**输入二（待恢复）**：意图存在，存储仍为 base_revision，运行 --dry-run。
当前打印“将恢复提交”及简略字段，但没有完整的将要发布路线映射；
§6.2 要求打印将要发布的路线与摘要。应显示意图里的完整候选、正确摘要及“不写”的预告，
退出 0，意图/manifest/版本文件原字节不变。第一、三行没有将要发布的路线，保持不发布。

**输入三（进程存活时路线写失败）**：在上述合法正式提交的第二步注入
StorageError（合成磁盘写失败）。实测意图保留、退出 2，只输出原契约错误，
没有“重跑同一命令完成提交”。应保留原错误并追加该恢复提示；恢复分支的发布失败也适用。
不删除意图、不自动清理遗留锁或孤儿版本文件，后两者继续按现有路线存储提示人工处理。

### C4：旧版身份断言接受新版；指定验收仍有未覆盖和弱断言

位置：`tests/contract/test_day_budget_port.py:429` 的新增固定基线测试，以及 pacing 新增用例。

**可复现输入**：把新增基线身份谓词用于当前未提交 `ky/__main__.py` 字节。
谓词只检查 `pacing_initial=None` 与 `def main`。独立执行结果为 **True**：
当前 show 函数的可选参数仍有 pacing_initial=None，所以它不能区分新旧。
应使用已知旧调用片段与新接线片段的正反断言，分别证明固定旧版通过、当前新版拒绝。
固定 636bd09 本身合理，不改成 HEAD，不扩大归一化。

现有测试不是空壳，但尚未兑现任务书点名的以下验收：

- 恢复第一行只有 helper 的 dry-run，缺正式重复与当前修订高于目标的历史应用断言；
  第二/三行已有正式与 dry-run 状态断言，可保留。
- 没有“无路线中断后修改 exam_date，恢复仍发布原终点”的测试；
  helper 直接调用绕开 CLI，不能证明设置改动后入口仍可恢复。
- 第 2 条护栏测试是找不到输入包，不是保存有效包后跨日或状态变化的**重算新鲜度拒绝**；
  应验证退出 2 且未写意图/路线。第 1、3、4、5、6 条已有部分实质拒绝断言，
  第 7 条有 apply_pacing 拒绝，但没有完整新提交拒绝后零写入断言。
- 五种 apply_pacing 情形只检查修订、起终日、合法性及部分阶段数量；
  不断言保留段原值、命中段新基数/配额、后续段原值、重编号、label 与元数据。
  即使把新基数/配额写成别的合法值，这些断言仍可能通过。
- timetable 与 resume 设置测试给 helper 显式传 settings，不能证明 CLI 从注册表接入；
  缺已登记设置的 preflight 调用方断言和提醒出现/不出现断言。

按原任务补这些指定项及 C1–C3 缺陷回归，不新增全量、冒烟或无关模块测试。
本轮独立探针已确认 preflight 取到 pacing_initial、提醒正常出现/消失，
所以这部分是验收证据缺口，不冒充已复现的接线实现错误。

### C5：新增公开接口没有同步模块头，需落实 D7

`ky/pacing/port.py` 的模块头仍只列 §2–§3 的旧公开接口，未列新增
apply_pacing/settings_for_workspace；submit 头只写章节号，未写对应的规格文件；
CLI 头也未列新增公开函数。AGENTS.md 明确要求模块头写明模块、规格和对外接口。
同步这些说明即可，不要求额外重构或测试；已知 apply_pacing 拆分仍按原分工处理。

## 二、通过的部分与不改

| 范围 | 已确认结果 |
|---|---|
| 输入包 | 只读已保存报告，校验当前周期终日与 D<T；规范 JSON 摘要不含额外自引用；base_at 按 T；staging/inputs 两步包含检查，写入走 replace_bytes |
| 新提交主体 | 证据可解、新包重算比较、区间/步长、在考科目/配额上限、日期、只读冻结、候选路线验证的主体均存在；b0 取 effective_from 旧基数；路线起点越界由候选转换拒绝 |
| 意图一次发布 | 临时 YAML、重读及映射比较、fsync、os.link 不覆盖；路线失败不删除意图。不存在 exists 后 replace 覆盖意图的问题 |
| 意图一致性 | 精确整数排除布尔、target=base+1、外层 actor/input_hash 与 proposal 一致、route.revision/stage1_input_hash、两个摘要均核对 |
| 两种摘要 | 恢复先由存储按 manifest 原始 YAML SHA 校验目标，再对解析路线的规范映射 SHA 与意图比较，没有把原始字节 SHA 当作规范 SHA |
| 恢复优先级 | 先判历史目标应用，再判 current=base，再冲突；已应用后当前 r3 仍退出 0且不发布，逻辑正确，文案有 C3 |
| manifest 快照 | read_revision_context 给当前修订、目标来源和验证路线；独立恢复探针实测 manifest 一次读取；没有 import 存储私有名；写端持锁后的重新读取保留 |
| 逐日设置接线 | preflight、M19 day、resume 候选日、timetable 日期/周、report base/reference、pacing input/status 均向现有 M8 传设置；未造第二 resolver |
| M19 条件字段 | pacing-only 时也有 availability 对象和 base_minutes/base_source；无 pacing 时保持旧形状；相关 pacing 模块用例通过 |
| status | 当前基数来源、当前周期终日、未出报告周期已有输出；模块用例验证提交后的 route 来源和无缺报告状态 |
| 旧路径字节 | 固定 636bd09 的 preflight 文本/JSON、day input、resume dry-run、timetable date 对照本轮实际通过；同时原 dcbb5b6 对照仍通过，不据此声称已覆盖全部 §9 历史矩阵 |

恢复三状态的既有 helper 测试通过，不表示新提交入口和全部恢复展示均合格。
路线转换总体保持 route_id、旧终点与后续阶段；主要数据结构逻辑未观察到错误，
上述弱断言需补强，不要求重写算法。

## 三、实施者四处自选：判断

- **submit 无 --config，使用登记 exam_config：合理。** 与既定命令接口一致；缺登记报契约错误。
  如果输入包生成时用了不同显式配置，提交重算拒绝是合理结果，用户应登记相同配置或重出包。
- **缺 manifest 视为修订 0：合理。** 正常首次事务可能尚未发布路线；无效已有 manifest 不降级。
  孤儿版本或锁仍由写端拒绝并提示，不把缺 manifest 当成授权覆盖孤儿文件。
- **JSON 提醒写 stderr：合理。** 独立 preflight 命令验证 stdout 可完整 json.loads，
  stderr 有提醒；当前周期未结束无提醒，补存缺报告后无提醒。
- **不另造 resolver：合理。** 本 worktree尚无后续 IO2 base_resolver，
  使用现有 M8；决策者合并时接 IO2 属已知分工，不在本轮开返工项。

## 四、建议改与 D7

- 新 input/submit/cli 函数 AST 检查均不超过 60 行；apply_pacing 的已知 64 行按决策者合并拆分。
  不因这项已分工的拆分另判失败。
- settings 映射目前是内部 dataclass 展平形状（minimum/maximum/initial），不同于设置 YAML。
  §4 没固定此表示，因此不判业务错误；建议明确输入包 settings 的形状，避免 AI 指引或后续解析器猜测。
- 可复用一处未出报告周期计算，避免 _pacing_reminder 与 missing_report_cycles 两份遍历逻辑漂移；
  不要求借返工扩大重构。当前两者正常例子结果一致。
- 用户可见报告来源变化提示本轮有措辞变化，可恢复规格原句以减少无关输出改动。

## 五、安全登记（不阻断当前工作包）

1. 保存输入包定位只检查规范哈希、report/cycle/end 和文件名，没有完整检查 kind/schema/外层形状；
   意图里的 proposal 校验也只复核部分外形，未完整复用所有方案字段类型检查。
   人工伪造包或篡改内部意图并重算摘要，可能让错误 kind 或非法内层进入后续代码。
   正常生成器不产生这些输入，按既定威胁模型登记；可能修法为共享的纯映射格式验证器。
2. 已有路径/原子保护保留；恶意 junction/链接、两行之间另一进程插手等不扩展本轮防护。
   正常写失败和用户停用设置后的事务恢复仍属 C2/C3 日常问题，不挪到安全登记。

## 六、本轮执行证据与验收界限

```text
py -3.12 -B -m unittest tests.contract.test_pacing_port
Ran 11 tests in 12.559s
OK

py -3.12 -B -m unittest tests.contract.test_day_budget_port.DayBudgetPortContractTests.test_unregistered_pacing_outputs_match_post_merge_fixed_baseline
Ran 1 test in 6.487s
OK
```

另只跑直接相关单项：

```text
tests.contract.test_resume_port.ResumePortContractTests.test_registered_pacing_initial_is_passed_to_future_day_budgets
tests.contract.test_route_plan_port.TestRoutePlanStore.test_versions_keep_bytes_sources_and_sha256
Ran 2 tests in 0.026s
OK
```

独立合成探针验证 C1–C3、旧身份谓词接受新版、历史目标恢复 manifest 一次读，
以及 preflight 基数与提醒/JSON 流；AST 检查新模块函数长度。均在内存/系统临时目录执行，
设置 PYTHONDONTWRITEBYTECODE=1，没有写仓库实现或测试。
git diff --check 无输出；未复跑实施者七模块组合，没有全量或冒烟测试。
全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。

接受条件：修 C1–C3，补 C4 指定的有效验收与 C5 模块头，按受影响单模块/单项验证后复审。
