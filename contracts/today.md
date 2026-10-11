# 端口规格：M33 今日视图（一天要做什么 + 记录这一天）

> 决议来源：用户 2026-10-02（路线图 ⑥：本机小服务，"看 + 少量表单"，首版只做"今天"页）。状态：sol 273 FAIL → 274 FAIL（R1、R2）→ 已改，待实现后初检。
> 2026-10-08 第二版（用户："⑥ 要做完"）：新增**只读**的 `load_queue_view`（§8），给 M16 `GET /queue` 用；`load_today` 与 CLI 输出不变。
> 实现：`ky/today/`；契约测试：`tests/contract/test_today_port.py`。消费者：M16 网页（`contracts/web.md`）与 M14 CLI。

## 1. 职责与边界

把现在散在 CLI 私有函数里的计算提成**公开端口**，让 CLI 与网页调用同一份代码：

1. **读**：某一天的预算、冻结、复习选择与每项的题、复盘提醒、当天是否已记录 → 一个映射（§3）。
2. **记**：把"这一天每个复习项的结果"写成完成事件并推进复习队列 → 与 `ky day-plan record --review-store` 同一条管线（§4）。
3. **补推进**：完成事件已写、队列没推进（中途失败）时，只按已存事件推进（§4.1）。
4. **改可用分钟**：M26 增加一个写入函数（§5）。

本模块**不新增任何业务规则**：预算（M8）、裁剪（M9）、冻结（M27）、出题（M31 / M24）、复盘（M28）、完成事件与推进（M13 / M10）全部沿用。

**分层（sol 273 M1）**：共享的是"**已加载上下文 → 结果**"的计算函数；读取哪些文件仍由各调用方决定。
- 从 `ky/__main__.py` / `ky/pacing/cli.py` 提出（放在非 CLI 模块，名字由实现定，规格只定职责）：
  (a) 预检计算：已加载的配置、队列、工作区（可为 `None`）、路线、课表、当日预算、用量与裁剪 / 冻结策略 → 预检结果与 `preflight --json` 映射；
  (b) 出题：已加载的队列、完成事件、题库、真题索引与 (a) 的结果 → `review-questions --json` 的 `reviews` 列表；
  (c) 复盘状态：已加载的复盘设置、预算、`state.plans` → `{base_minutes, base_source, next_review, unreported_cycles}`；
  (d) 记录管线：工作区（可为 `None`）、完成事件、存储路径、配置 → 现有 `day-plan record` 报告映射（冻结锁存 → 写事件 → 推进）。
- CLI 保留自己的参数、可选注册表、显式路径覆盖（`--config`、`--items`、`--usage`、`--store` 等）与打印，只把计算换成上述函数。
- `load_today(workspace, day)` 是给网页用的**装配**：只走"已登记工作区 + 各命令缺省参数"这一条路，读取后调用 (a)–(c)。
CLI 输出与固定基线 **`60a4fd2`** 逐字节一致（§6）。

## 2. 公开接口

```python
load_today(workspace: Workspace, day: date) -> Mapping          # §3；只读
load_queue_view(workspace: Workspace, day: date) -> Mapping      # §8；只读（第二版）
today_view_hash(view: Mapping) -> str                            # §3.2
record_day(workspace: Workspace, day: date, outcomes: Mapping[str, str],
           *, study_minutes: int | None, expected_view_hash: str,
           submitted_review_ids: Sequence[str] = ()) -> Mapping   # §4
advance_recorded_day(workspace: Workspace, day: date) -> Mapping                   # §4.1
```

M26 增加：`set_day_minutes(path, day: date, minutes: int | None) -> None`（§5）。

- 参数先校验再运算（`AGENTS.md` 已知缺陷 6）：非 `Workspace` / 非 `date` / 非字符串键等 → `ContractError`，带参数名路径。
- 读写所需路径一律来自注册表（`settings.exam_config`、`state.review_queue`、`state.plans`、`state.routes`、`state.availability`、`state.timetable`、
  `settings.pacing`、`state.question_bank`、知识树、真题索引）；未登记的可选键按各自规格处理（未登记 = 不启用），**必需键**（`settings.exam_config`、
  `state.review_queue`、`state.plans`）未登记 → `ContractError`。
- 同一次调用里每个来源**只读一次**（已知缺陷 2）；`record_day` 内部重新调用 `load_today` 一次，用这一份结果构造完成事件，不再另读。

## 3. 今日视图映射（`load_today`）

```
{schema_version: 1,
 date: "YYYY-MM-DD",
 budget: {total_minutes, total_source, base_minutes, base_source},      # M8 resolve_day_budget
 timetable: null | {semester, week, weekday_used, no_class, blocks, free_minutes},  # M18 DaySchedule 同名字段（sol 273 M4）；
                                                                        # 未登记课表或当天不在任何学期 → null
 route_phase: null | {index, label, review_minutes},                    # 当天命中的路线阶段
 preflight: <与 `ky preflight --json` 完全相同的映射>,                    # 含冻结时的 freeze 键
 reviews: <与 `ky review-questions --json` 的 reviews 列表完全相同>,
 pacing: null | {base_minutes, base_source, next_review: "YYYY-MM-DD" | null,
                 unreported_cycles: ["<周期终日>", ...]},               # §1 (c)；未登记 settings.pacing 为 null
 recorded: null | {reviews: [{review_id, outcome, check, question_ref}], study_minutes,
                   advanced: bool},                                     # 当天已有完成事件时；advanced 见 §4.1
 availability_registered: bool,
 view_hash: "<64 位十六进制>"}
```

- `reviews` 只列 M9 当天**入选**的复习项（与 `review-questions` 现行口径相同，不改）。
- `route_phase.review_minutes` 只在当天命中阶段时给出；没有路线配额时整个键为 `null`，不写成 0。
- 冻结日：`preflight.freeze` 存在、`reviews` 为空（沿用现行行为）。
- `preflight` 与 `reviews` 是**原样嵌入**：它们与两个 CLI 的 `--json` 由§1 (a)(b) 的同一个映射构造器产生，形状只有一个来源；CLI **不调用** `load_today`（不扩大其读取依赖）。
- 计算层不暗中读文件：冻结事件、知识树与祖先关系、`state.plans` 下的完成事件与复盘报告都由装配层读取后传入。

### 3.2 `view_hash`

对 `{date, reviews: [{review_id, check, question_ref}]}`（按 `reviews` 顺序；缺题项 `check` 记为 `recall_vs_notes`、`question_ref` 记为 `null`，
与 §4 第 5 步写入的值相同）取 M19 规范 JSON 字节的 SHA-256。
它标识"这一天给出的是哪几项、各做哪道题"。网页把它放进记录表单；提交时不一致 → 拒绝（§4），避免照着已过期的题目记录。
只哈希这些身份字段、不哈希题库：给**别的**知识点补题不改变哈希；给页面上缺题的项补了题（该项改出改编题）会改变哈希，这时要求刷新是对的。

## 4. 记录这一天（`record_day`）

输入：`outcomes` 为 `review_id → outcome`，`outcome ∈ {correct, partial, incorrect}`；没做的项**不出现**。`study_minutes` 为可选非负整数。
网页可把所有已提交的 `outcome.<review_id>` 字段 ID 传入 `submitted_review_ids` 供本端口校验；
其中 `skip` 仍不进入 `outcomes`，未知 ID 由本端口拒绝。省略此参数时按 `outcomes` 的键校验。

1. 本端口不读系统时间；记哪一天由调用方决定（网页只记当天，见 `contracts/web.md` §4）。
2. 重新 `load_today(workspace, day)`；`view_hash` 与 `expected_view_hash` 不同 → `ContractError("页面已过期，请刷新后再记录", "view_hash")`，不写任何东西。
3. 当天已有完成事件 → `ContractError("这一天已经记录过", ...)`（完成事件只写一次，M13）。
4. `outcomes` 的键必须都在视图 `reviews` 里，否则 `ContractError`，路径 `outcomes.<review_id>`；值不在三档内 → `ContractError`。
5. 构造完成事件（schema 按 M13 规则：有 `study_minutes` 写 v3，否则 v2）：每个有结果的项按视图 `reviews` 顺序写
   `{review_id, completed_on: day, check, outcome, question_ref?}`。`check` / `question_ref` 取视图里该项的值；视图里该项没有题（缺题）时
   `check: recall_vs_notes`、不写 `question_ref`——这是用户声明"已默写并对照笔记"的结果（D3 / M10 信任该声明），网页必须在该项旁明示（`contracts/web.md` §4，sol 273 M3）。
   词汇照序列化器的空 `vocab`（首版网页不提供单词输入，持久格式不变）。
6. 交给 §1 (d) 的记录管线（与 `ky day-plan record --done <事件> --review-store <state.review_queue>` 同一个函数）：冻结锁存检查、写完成事件、推进队列，
   返回同一份报告映射。同一个 `Workspace` 对象贯穿全程（S15）。
7. 没有任何结果且没有 `study_minutes` → `ContractError("没有可记录的内容")`。

**失败按已持久化的阶段区分（sol 273 M2、274 R2）**。管线依次可能写下冻结锁存、完成事件、队列三样东西：

| 阶段码 | 情形 | 已写下 | 处理 |
|---|---|---|---|
| `rejected` | 第 2–4、7 步或管线自身的写前校验（未知 `review_id`、旧队列等）失败 | 无 | 改正后重交 |
| `freeze_written` | 冻结锁存已写（当天首次触发阈值），完成事件写入失败 | 冻结事件 | 冻结事件保留、不回滚（触发是真实的）；排除故障后**重新记录**即可（锁存已存在，不会再写一条） |
| `event_written` | 完成事件已写，推进失败 | 完成事件（及可能的冻结事件） | 事件保留（M13 只写一次，不回滚、不改写）；按 §4.1 补推进 |

部分失败抛出带 `stage` 属性（`freeze_written` / `event_written`）的异常类（`ContractError` 子类，名字由实现定）；调用方按 `stage` 区分，**不按消息文字判断**（已知缺陷 3）。

### 4.1 补推进 `advance_recorded_day`

- 共享恢复管线接收**已加载**的完成事件、配置（含 `review_policy.algorithm` / `self_rating_mode`）与目标队列存储，按 M13 既有推进入口推进；
  已计算过的 completion ID 记为 `replayed`、不重复推进（D8′），因此可以安全地重复调用。不写新的完成事件，不改已存事件。
  `advance_recorded_day(workspace, day)` 是网页用的装配：从登记的 `state.plans` 读事件、`settings.exam_config` 读配置、`state.review_queue` 为目标；没有事件 → `ContractError`。
- 视图 `recorded.advanced`：该事件全部 completion ID（缺省 ID 按解析器补齐的 `"<day>#<i>"`）都在队列的已计算集合中为真；`reviews` 为空时为真。
- CLI 同步提供（sol 274 R1）：
  `py -3.12 -m ky day-plan advance --date D [--store DIR] [--review-store DIR] [--config C] [--workspace W]`，
  三个路径的缺省与可选注册表规则和 `day-plan record` **完全相同**（显式给出时不要求注册表）；不得退回别的队列或缺省算法。
  唯一的差别（sol 277）：`record` 不给 `--review-store` 时只记录、不推进；`advance` 的职责就是推进，所以不给时用登记的 `state.review_queue`，
  两者都没有时报契约错误。
  `day-plan record` 在 `event_written` 失败时多打印一行恢复命令，**带齐本次实际使用的 `--store` / `--review-store` / `--config`**（只在该分支出现，其余输出不变）。

## 5. M26 写入 `set_day_minutes`

- `minutes` 为 0–1440 的整数（排除布尔）或 `None`（删除该日条目，回到课表 / 基数）；删除不存在的条目 → `ContractError`。
- 读当前文件一次并按 M26 规则校验；改一项；以规范形式序列化（`schema_version: 1`、`days` 按日期升序、ISO 字符串键）；
  `ky/storage/atomic.replace_bytes` 原子替换。**注释不保留**（规格写明）。文件不存在 → `ContractError`（登记即必须存在，同 M26）。
- 不限制日期范围；"只能改今天及以后"是网页的规则（`contracts/web.md` §4），CLI 不用这个函数。

## 6. 不变的部分与对照

- `ky preflight`（文本与 `--json`）、`ky review-questions`（文本与 `--json`）、`ky pacing status`、`ky day-plan record`（文本与 `--json`、写出的文件字节）
  在同一输入下与固定基线 `60a4fd2` 逐字节一致（退出码、stdout、stderr、写出文件）；对照测试固定该哈希并断言取到的确是旧版（`AGENTS.md` 12a）。
  必须覆盖的分支（sol 273 M1）：已登记工作区缺省参数；**无注册表**、显式 `--config` / `--items`；`--usage`；`--freeze-backlog-days` / `--urgent-*`；冻结日；
  `record` 显式 `--store` / `--review-store`；`review-questions --json` 与文本（含停用提示行）。**允许的差异只有两处**：
  §4.1 所述推进失败分支多出的提示行；以及停用提示行本身的原因占位符改成带引号形式（sol 282 M2，见 `contracts/question_bank.md` §5）。
  对照测试对后者只放过那一行，并断言该分支其余字节仍与 `60a4fd2` 相同。
- 不改任何数据文件格式；不改投影。

## 7. 决议记录（用户 2026-10-02）

| 问题 | 用户选择 |
|---|---|
| 网页能否写 | "看 + 少量表单"：改某天可用分钟、记录做题结果；其余写入仍经 AI 对话 |
| 运行方式 | 本机小服务（见 `contracts/web.md`） |
| 首版页面 | 只做"今天" |

**决策者拟定、可被用户推翻**：记录表单一天只交一次（沿用完成事件只写一次）；缺题项按"默写后对照"记，且页面明示要先对照笔记；网页首版不记单词；
`view_hash` 防止照着过期题目记录；可用分钟写入不保留注释（网页保存处提示）。

sol 第 273 轮初检 FAIL（M1 分层、M2 部分完成与补推进、M3 缺题声明、M4 大节数）→ 已改，见 §1、§3、§4、§4.1、§6。
sol 第 274 轮复审 FAIL（R1 恢复命令须保留显式路径、R2 冻结已写而事件未写）→ 已改，见 §4 阶段表、§4.1。

## 8. 复习队列视图（用户 2026-10-08，第二版；只读）

`load_queue_view(workspace: Workspace, day: date) -> Mapping`，给 M16 `GET /queue` 用（见 `contracts/web.md` §8.2）。

**装配**：复用 §1 的已加载上下文与**同一个 M9 预检计算**，保留 `ClipResult`；不另外读取队列、不重新实现裁剪
（sol 291 M2）。**一次调用内每个来源只读一次**（`AGENTS.md` 已知缺陷 #2）。

返回键固定为 `schema_version=1`、`date`、`budget`、`caps`、`freeze`、`queue_registered`、`buckets`、`selected`、`backlog`、`ahead`：

| 字段 | 内容（口径由本节固定，sol 291 M1/M2） |
|---|---|
| `date` / `budget` | `date` 为 ISO；`budget` 与 §3 同日同输入时**同值**（总分钟与来源、基数与来源） |
| `caps` | `{soft_target_minutes, hard_cap_minutes, soft_source, hard_source, subject_review_quotas}`。两个分钟值直接取 `ClipResult`；冻结时均为 0、来源均为 `freeze`、配额为 `null`；否则 `soft_source` 为 `route_quota`（有经 M8 缩放的配额）或 `config_ratio`，`hard_source` 为 `config_ratio`；配额取 `ClipResult.subject_review_quotas`，无配额为 `null`（硬上限不等于路线配额之和） |
| `freeze` | `preflight.get('freeze')`；无冻结为 `null` |
| `queue_registered` | 合法 `Workspace` 中**恒为 true**（`state.review_queue` 仍是必需键；未登记按 §2 抛 `ContractError`、不构造视图；目录 / manifest 尚不存在按既有 M13 空库处理） |
| `buckets` | 固定五键 `selected` / `deferred` / `unschedulable` / `scheduled_ahead` / `unreachable`，各值 `{count, minutes}`，按 `ClipResult` 对应元组长度与 `estimated_minutes` 求和；**沿用 M9 的成员与顺序，不补未来 `queued`**，不含 `suspended` / `retired` |
| `selected` | 保持 M9 入选顺序，仅含 `{review_id, knowledge_point_id, title, subject_id, subject_name, level, due_date, overdue_days, defer_count, lapses, estimated_minutes}`；名称取配置 `display_name`，`level` 沿用 M31 的已加载完成事件判定，日期为 ISO，`overdue_days` 用 `ReviewItem.overdue_days(day)`，`lapses` 取 `schedule.lapses`；**不加载题目**作为展示前提 |
| `backlog` | `{count, minutes, by_subject, details, remaining_count}`：成员为 `deferred` + `unschedulable` + `unreachable`，**不等同 M9 的 `backlog_minutes`**（后者只含 `deferred`）；`by_subject` 是按科目 ID 键控的 `{count, minutes}` 稀疏映射；`details` 按上述三桶顺序拼接取前 20 项，用与 `selected` 同形的明细；`deferred` 的 `defer_count` 是本次预检 +1 后的值（标注"本次预检延期后计数"，不写回）；`remaining_count = count - len(details)` |
| `ahead` | `{count, due_dates}`：取原队列 `state ∈ {queued, scheduled}` 且 `due_date > day` 的全部项；`count` 为项数，`due_dates` 为升序去重的 ISO 日期前 3 个；**不等同 `scheduled_ahead` 桶** |

- 空集合保持全部键在：数字 0、列表空、`by_subject` 空。不读投影、不缓存。
- 参数先校验再运算（`AGENTS.md` 已知缺陷 6）：非 `Workspace` / 非 `date` → `ContractError`，带参数名路径。
- **不改 `load_today` 的输出、不改 CLI 的任何一行输出**（§6 的固定基线对照继续覆盖 CLI）。
