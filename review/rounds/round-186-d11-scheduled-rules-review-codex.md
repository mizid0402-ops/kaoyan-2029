# 第 186 轮：D11 过期 `scheduled` 计入冻结积压——细则审查

范围仅为 R1–R6 的规则，不审实现、不改代码。已读题定文件及第 118 轮 B1；按 `AGENTS.md` 的个人本机威胁模型判严重度，未跑全量。用户选择“计入积压”是本轮前提；以下把当前代码事实与**若采纳 R1 后**的推论分开。

## 已核对的前提

- `git grep '"scheduled"' -- ky` 未找到把新状态**显式写成** `scheduled` 的现有生产者，只找到允许值和读取/分类；这项静态检索不能证明未来或动态导入绝不会产生它。队列 schema 允许此状态（`ky/models.py:51`）。
- M9 把 `scheduled && due_date > today` 放入 `scheduled_ahead`，把 `scheduled && due_date <= today` 放入 `unreachable`（`contracts/review_clip.md:120-121`、`ky/schedule/review_clip.py:399-410`）。它不会选中到期的 `scheduled`。第 118 轮 B1 指出的洞确实存在于现行口径。
- M27 当前只数过期 `queued`；M12 的 `in_review_queue` 已包含两种状态，但 `backlog_minutes` 只数过期 `queued`。月结不读复习队列，`ky/schedule/monthly_close.py:139-141` 累加的是**已存日计划自己声明的** `backlog_minutes`；任务书把“月结的逾期统计”与 M12 并列，是错误前提。

## 必须改（规则发给实现者前）

### M1｜R4 不能让同一当前队列积压在冻结与快照中相反

可复现输入：在 `tests/fixtures/config/config-minimal.yaml` 下，配置复习硬上限为 72 分钟，默认三天阈值为 216；取有效复习项复制成 27 个各 8 分钟、`state=scheduled`、`due_date=D-1` 的不同 `review_id`。现行 M9/M12 定点探针在 D 得到 `unreachable=27`、M9 `backlog_minutes=0`、M12 `backlog_minutes=0`、`in_review_queue=27`；**按拟议 R1**，M27 `overdue_minutes=216` 并冻结。这样日常导入的合法队列会出现“冻结因积压 216 分钟，状态快照积压 0 分钟”。这不是单纯显示喜好：两处都把数值称作当前复习积压，用户会据快照误判冻结原因。

**改法**：M12 公共计数端口的 `backlog_minutes` 同步改为 `state in {queued, scheduled} && due_date < D`；M15 日期状态查询复用该端口，随之同口径。保持 `due_today` 只数 `queued && due_date == D`，因为 R1 没把到期当天的 `scheduled` 算作“逾期”。更新 `contracts/state_snapshot.md` 与 `contracts/projection_status.md` 的字段说明。R5 的旧字节基线只要求**没有过期 scheduled 的有效输入**不变；有该类项时快照数值变化是本决议的预期效果。

M9 `ClipResult.backlog_minutes` 是**本次裁剪被延期的分钟**，不是队列中一切过期项；不要为了让它等于冻结值而改其会计定义。若同一 preflight 文本同时显示“冻结积压 216”和“deferred → backlog 0”，须把两种量明确标成“逾期积压”与“本次延期”，或在该新条件下说明 `unreachable` 已计入冻结。月结继续保持计划声明量，不改数值算法，说明它并非当前队列逾期统计即可。

### M2｜R3 的 revision 理由和“立即再冻结”反例不成立；R6 须说明比较对象

`ky/freeze/resume.py:105-121` 当前重排 `queued` 时改到期日、延期次数、可能改进度，**不递增 `revision`**；`contracts/freeze.md` 也写“其他 item 字段不变”。M25 在**知识点迁移或退役**时递增 revision（`contracts/syllabus_migration.md:25-33`），不是通用重排规则。因此 R3 的“`revision + 1` 与既有重排一致”是错误前提。用户只选了积压口径，没有选择改变 item 版本语义。

建议的最小定稿：过期 `scheduled` 经 `ky resume` 赋予新到期日时转为 `queued`，**revision 保持原值**；其他字段按既有 D11 重排处理。这样它在新到期日可被 M9 选中，不必改 M9。若决策者坚持 `revision + 1`，须明确写成新的状态转换版本规则，并同步修订“其他字段不变”及 M25 的版本说明，不能借用不存在的旧惯例。

“不转 `queued` 会恢复后**立即**再冻结”也不准确：新到期日 `>= D`，R1 用严格的 `due_date < D`，所以 D 当天不会仅因它再次达到阈值；真实风险是它在新到期日仍属 `unreachable`，如果以后再次逾期才可能再冻结。R6 的“只让复习提前或不变”也不能按绝对 `due_date` 理解：例如旧到期 D−1 的项重排到 D，日历日期必然变晚。应明确约束的是 `schedule.interval_days` **不增加**；恢复安排可把已过去的到期日移到 D 或之后。

### M3｜R1/R3 须规定已停用或配置外科目的失败边界

有效队列文件可含 `scheduled` 项，但用户后来停用该科目时，`ky.models.validate_items_against_config` 会拒绝它。定点输入：最小配置中 `politics.active=false`，一条 `subject_id=politics, state=scheduled, due_date=D-1` 得到 `ContractError: items[0].subject_id ... inactive subject`。若 R1 先用它写冻结锁存，而 R3 再把它改成 `queued`，M9 仍会拒绝该队列；有路线配额时恢复还可能在 366 天内找不到该科容量。用户无法靠这次 resume 正常恢复。

**改法**：在会写冻结事件或恢复队列/事件的入口，至少对本次新增纳入的**过期 scheduled 候选**使用既有公开校验器核对科目；配置外或已停用候选在任何写入前报契约错误，提示先修正/迁移队列。不能静默忽略，也不能先锁存后发现无法安排。不要因本轮检查而把本应排除的 retired/suspended 项纳入冻结；无过期 scheduled 的旧路径仍受 R5 字节保证约束。

## 建议改

- **R3 的审计表述**：`ResumeEntry` 现有字段只列旧/新到期日与遗忘层级，不列状态转换。若规格想让用户从 `ky resume --dry-run/--json` 单独看出“`scheduled → queued`”，可在实现包决定是否增加**只对新条件出现**的明确提示；但 R2 的“不新增输出字段”与 R5 字节要求目前允许从写后队列核对，不必为此阻断。不要让 JSON 暗示整个队列都已恢复为 `queued`。
- **解释阈值的限度**：一条 8 分钟的过期 `scheduled` 在上述 216 分钟阈值下仍属 `unreachable`，但不会冻结。用户选的是“计入积压阈值”，不是“任一 unreachable 都停排”；规格可写明低于阈值时仍需手工 `ky resume` 或后续独立修复规则，避免把本轮误述为消灭全部卡住项。

## 不改

- **R1 的日期和状态边界**与用户选项一致：`queued/scheduled` 且 `due_date < D` 计入；`scheduled` 当天到期虽在 M9 `unreachable`，但不是“已过期”；未来 `scheduled_ahead`、`suspended`、`retired` 不计。达到阈值取等号及“空积压即使阈值为 0 也不冻结”沿用 M27。
- **R2 的阈值、锁存和事件格式**无需改变，`overdue_count/minutes` 只因新候选自然增大；冻结仍由当前阈值或未解除事件决定，record 不能自动解锁。
- **R3 的分层、转 queued 方向**与 M10/M25 不冲突：`review_progress.md` 没有禁止 `scheduled → queued` 的状态机；M10 的 `reset_for_relearning` 只改 interval/repetitions，保留 phase/ease/lapses；M25 重命名会保留 scheduled，拆分源项/被合并项退役后按 R1 排除，新子项若继承 scheduled 且已过期则照新规则处理。进度已满的项仍按现有 `逾期天数 > interval_days` 判遗忘，不凭 repetitions 再造一档。
- **R5** 应保留固定提交哈希的旧版对照；无过期 `scheduled` 时，包括 `scheduled_ahead`、当日 `unreachable`、纯 queued/空队列，原有 preflight、record、submit、resume 的文本/JSON 与事件字节均应不变。
- **现在实现仍合理**：当前没有显式生产者不等于状态不可出现；schema 已允许手工导入，且用户已选“计入积压”。未来 ④ 若产生钉日 `scheduled`，还须独立解决“到期当天 M9 仍不可选”的既有语义，本包按 R4 不动 M9 是明确范围边界。

## 实现包必须覆盖的边界测试

1. 固定有效配置：`scheduled` 于 D−1/D/D+1、`queued` 于 D−1、`suspended/retired` 于 D−1；核对 M27 计数、M12/M15 积压同口径，以及 M9 两个 scheduled 桶不变。单项低于阈值、混合项恰等阈值、超过阈值、空积压零容量均覆盖。
2. 过期 `scheduled` 的遗忘分界 `overdue_days == interval_days` 与 `+1`；重排后状态 queued、到期日 `>=D`、interval 不增、defer 清零，phase/ease/lapses、revision 按定稿保持；`--dry-run` 不写队列或事件，正式执行核对写后队列与审计事件。
3. 只靠过期 `scheduled` 达阈值时，preflight 冻结、submit 拒绝、record 仍能记录且锁存不自动解除；resume 后在新到期日能被 M9 作为 queued 候选，未完成再次过期才可能重新触发冻结。无锁存但有少量过期 scheduled 时，`ky resume` 仍能重排。
4. 同日冻结→恢复→再冻结、旧锁存但队列积压已清空、恢复事件写入失败后重试；`unschedulable` 被放在 D 并转 queued，后续 M9 拆分提示仍可见。
5. M25 重命名、拆分、合并/退役后的 scheduled；配置外与已停用科目在写任何事件/队列前失败。未来 scheduled 项的容量占用与到期日选取不在本包改 M9，但回归测试须证明旧路径未变。
6. 以**固定提交哈希**而非 `HEAD` 对照：无过期 scheduled 的合法输入分别比较 preflight 文本/JSON、record、submit、resume 及事件原始字节；新条件下只放行规则明示的数值、状态和提示差异。

## 安全登记

未发现新的恶意输入、链接或竞态类问题；上述 M1–M3 都是有效本地输入或正常配置变化下的日常语义问题。

## 结论

**FAIL（细则暂不宜下发实现）。** R1/R2 的核心方向忠实于用户选项，R3 把过期 scheduled 转为 queued 也是最小可行恢复方向；须先修订 R4 的 M12/M15 当前积压口径、R3/R6 的版本与日期表述，并补上停用科目的写前失败边界。月结的计划声明量保持原义。
