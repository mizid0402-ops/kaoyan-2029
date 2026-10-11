# 第三轮：Claude Code 自审报告（主实现者）

## 复现现状（实际运行，非声称）

```text
$ py -3.12 -m unittest -v tests.test_contracts tests.test_review_scheduler
Ran 49 tests in 0.298s
OK

$ py -3.12 -m ky preflight --config tests/fixtures/config/config-minimal.yaml \
      --items tests/fixtures/reviews/reviews-overloaded.yaml --date 2026-09-12
（结果与任务书一致：selected 6 -> 54 min，deferred 7 -> backlog 64 min，over capacity YES，exit 0）
```

修复前的基线与任务书描述一致，49 个测试全部通过，preflight 行为也一致。以下是我自己在读代码 + 跑代码过程中找到的问题（不是等 Codex 指出来的）。

---

## A. 自审：我自己找出的实现缺陷

### A1（已修复）CLI 在非原生控制台下把中文显示名输出成乱码

- **位置**：`ky/__main__.py`（修复前的 `main()` 全程未设置输出编码）。
- **触发条件**：`sys.stdout`/`sys.stderr` 不是 Windows 原生控制台时（管道、重定向到文件、或本机 GBK 区域设置下的非 UTF-8 codepage），Python 会退回 `locale.getpreferredencoding()`。
- **实际后果**：我在本机通过管道运行 `py -3.12 -m ky preflight ...` 时，`sys.stdout.encoding` 实测为 `gbk`，`新content budget` 一段的科目显示名（数学一/英语一/408）全部输出为乱码字节；这不是我的猜测，是我用
  `py -3.12 -c "import sys; print(sys.stdout.encoding, sys.getdefaultencoding())"` → `gbk utf-8`
  实测确认的，随后重新跑一遍完整 preflight 命令，乱码原样复现。
- **最小复现**：
  ```
  py -3.12 -m ky preflight --config ... --items ... --date 2026-09-12 | cat
  ```
  （或任何把 stdout 重定向到文件/管道的用法，在中文 Windows 默认 GBK codepage 下都会复现。）
- **修法**：在 `main()` 入口对 `sys.stdout`/`sys.stderr` 调用 `reconfigure(encoding="utf-8", errors="replace")`（仅在流对象支持 `reconfigure` 时才调用，避免影响非标准 stdout 场景）。修复后同一条命令重新跑，"数学一 / 英语一 / 408" 全部正确显示。
- **验证方式**：手工重跑同一条 preflight 命令，逐字节比对输出（见"修复"一节）。

### A2（已修复）`_deficit_ratio` 用 `except Exception` 吞掉所有异常，而不仅仅是"未知科目"

- **位置**：`ky/schedule/review_clip.py:134`（修复前）。
- **触发条件**：排序过程中任何时候 `config.subject(subject_id)` 抛出异常，不管是预期的"未知科目"（`ContractError`）还是排序键计算中其它意外的编程错误（比如未来重构引入的 `TypeError`/`AttributeError`），都会被这一行悄悄压成 `0.0` 继续排序，而不是让 bug 暴露出来。
- **实际后果**：这违反了整个代码库反复强调的"失败即拒绝"哲学——`ContractError` 到处都有精确路径，唯独这里选择性地静音了所有异常类型，是这份代码里唯一一处"捕获所有异常继续跑"的地方。
- **修法**：把 `except Exception` 收窄为 `except ContractError`（`config.subject()` 实际抛出的正是这个类型），语义完全不变，但不再掩盖其它编程错误。
- **验证方式**：新增 `test_an_item_with_an_unrecognised_subject_id_does_not_crash_selection`，确认收窄后"未知科目 → deficit_ratio=0.0 → 正常参与排序"这条路径仍然成立，不会因为收窄捕获类型而意外抛出。

### A3（已修复）复习条目的 `subject_id` 从未与配置里声明的科目做过交叉校验

- **位置**：`ky/models.py`（`validate_review_item` 与 `validate_config` 各自独立校验，两者之间没有交叉引用检查）；`ky/__main__.py`（`main()` 加载 config 和 items 后直接喂给 `select_daily_reviews`，没有校验二者的一致性）。
- **触发条件**：`reviews.yaml` 里某条目的 `subject_id` 拼错（比如把 `math1` 写成 `math2`），而 `config.yaml` 里恰好没有这个科目。
- **实际后果**：这不会报错，也不会崩溃——`_deficit_ratio` 捕获到"未知科目"直接返回 `0.0`，于是这条目被当成一个"零欠账"的条目正常参与排序、正常被选中、正常占用当天的复习分钟数。用户会看到一条针对根本不存在的科目的复习任务被正常排进当天计划，而契约层完全不会拒绝这份数据——这与任务书声称的"1. 失败即拒绝"直接冲突：这是一种能绕过契约的真实路径，只是绕过的位置在两份文件的"缝隆"里，不在任何一份文件的单独校验里。
- **最小复现**：构造一条 `subject_id: math2`（不存在于 `config-minimal.yaml`）的条目喂给 `preflight`，修复前会正常输出 exit 0；修复后：
  ```
  contract violation: items[0].subject_id: subject_id 'math2' is not declared in config.subjects
  exit=2
  ```
- **修法**：新增 `ky/models.py::validate_items_reference_known_subjects(config, items)`，在 `ky/__main__.py::main()` 里紧跟 `load_config`/`load_review_items` 之后调用，纳入同一个 `except ContractError` 分支（exit 2，带精确的 `items[N].subject_id` 路径）。
- **验证方式**：新增 `CrossContractTest`（`test_unknown_subject_id_in_review_item_is_rejected` / `test_known_subject_id_passes`），并手工跑了一遍上面的最小复现，exit code 与错误信息都符合预期。

### A4（已修复）非活跃科目可以声明一个永远不会被兑现的 `min_daily_minutes`

- **位置**：`ky/models.py::_load_subject`（修复前只检查了"非活跃科目权重必须为 0"，没有对称地检查 `min_daily_minutes`）。
- **触发条件**：一个 `active: false` 的科目声明了 `min_daily_minutes: 10`（比如政治提前占了个保底名额，但还没到激活时间）。
- **实际后果**：`allocate_new_content()`（`ky/schedule/budget.py:75`）只遍历 `config.active_subjects()`，非活跃科目的 `min_daily_minutes` 永远不会进入保底计算——这个值会被静默忽略，而契约层不会告诉用户这是个矛盾配置。已经存在的"非活跃科目权重必须为 0"检查证明作者本来就认可这个"声明了但用不到的字段应该被拒绝"的原则，只是没有对称应用到 `min_daily_minutes` 上。
- **修法**：在权重检查旁边加一条对称检查：`not active and min_daily_minutes != 0` → `ContractError`。
- **验证方式**：新增 `test_inactive_subject_min_daily_minutes_must_be_zero`，构造这种矛盾配置，确认被拒绝且路径指向 `subjects[3].min_daily_minutes`。

### A5（已修复，文档性缺陷）注释与实际的类型优先级表互相矛盾

- **位置**：`ky/schedule/review_clip.py:34-42`（修复前的注释）。
- **触发条件**：任何读代码的人（包括审查者）单看注释判断行为。
- **实际后果**：注释写"unreviewed error cases are the most expensive and most valuable"，暗示 `error_pattern` 应该排在前面；但实际的 `ITEM_TYPE_PRIORITY` 表里 `error_pattern` 是 `2`，只比 `vocabulary_batch`（`3`）靠前，排在 `concept`/`procedure`（`0`）和 `question_pattern`（`1`）之后。注释描述的优先级和代码实际实现的优先级方向不一致，这是会误导未来维护者的文档缺陷。我没有找到 `docs/评审结论与实施契约.md` 里对这张表的具体排序有明文规定（我只读取、未修改该文件），所以无法确定"代码错了"还是"注释错了"——这是一个需要产品/契约层面拍板的问题，我只改了注释使其准确描述当前代码的行为，没有改变排序本身（改变排序属于产品判断，不属于我可以单方面拍板的"缺陷修复"范畴，见 E 节）。
- **修法**：重写注释，如实描述当前实现（核心学习单元优先于错题订正与批量词汇），不再声称一个代码没有实现的优先级方向。
- **验证方式**：新增 `test_item_type_priority_breaks_ties_when_lapses_are_equal`，把这张表的行为锁进测试里，防止未来改动时无声改变语义。

### A6（已修复，清理）死代码 `SubjectBudget.target_minutes()`

- **位置**：`ky/models.py`（修复前 `SubjectBudget` 类里的 `target_minutes` 方法）。
- **触发条件**：全仓库 grep 确认这个方法从未被 `ky/` 或 `tests/` 里的任何地方调用过。
- **实际后果**：不是运行时缺陷，但它是一段没有测试覆盖、没有调用者的死代码，容易在未来被误用（因为签名看起来和 `KaoyanConfig.review_target_minutes()` 相似但语义不同：一个是单科目份额，一个是复习软配额）。按仓库准则"确定没人用就直接删掉"处理。
- **修法**：删除该方法。
- **验证方式**：删除后全量测试仍然 56/56 通过，说明确实没有隐藏依赖。

---

## B. 对第 1–7 条语义的逐条自证

| # | 语义 | 证明方式 | 结论 |
|---|------|---------|------|
| 1 | 失败即拒绝，精确字段路径，exit 2 | `test_error_messages_carry_the_field_path` 断言路径与消息；手工跑 `config-weights-not-closed.yaml` 确认 exit 2。**但**跨文件的引用一致性（科目引用）修复前完全没有测试覆盖，属于"看起来对但没测"的真实漏洞——已在 A3 里补上契约校验和测试。 | 有测试，且本轮补齐了一个真实漏洞 |
| 2 | 保底优先、余量按权重最大余数法分配、精确加总不丢分钟 | `test_allocation_sums_to_new_content_budget`（`range(15,121)` 全量扫描求和相等）、`test_floor_then_weight_split_when_the_floor_binds`、`test_exact_40_20_40_split_when_the_floor_stops_binding` 给出了具体数值断言，不是只判断"不报错"。 | 有测试，覆盖两种规则区间 |
| 3 | 全序排序 + 软配额任意条目可入选 + 超软配额只有 urgent 可借用到硬上限 | 原有测试覆盖了逾期天数、延期次数、科目落后率三个维度和"借用只对 urgent 生效"；但 `lapses`、条目类型优先级、`self_rating` 这三个 tie-break 维度修复前**完全没有专门测试**——只是"代码这么写了，看起来对"。本轮新增三条测试，用"总预算恰好只够一项"的极小配置分别单独锁定这三个维度，且刻意让 `review_id` 字母序与被测维度的期望结果相反，确保测试真的在验证该维度而不是巧合命中最后一级 tie-break。 | 修复前：4/8 个排序维度有直接测试；本轮后：7/8（`due_date` 本身作为 tie-break 层级尚未单独测试，见 E 节） |
| 4 | 延期保留 due_date，只加 defer_count，不静默改期 | `test_deferred_items_keep_due_date_and_advance_defer_count`、`test_deferral_does_not_mutate_the_input_items` 直接比对修改前后的字段。 | 有测试，且验证了不可变性（原始输入不被污染） |
| 5 | 超大条目进 unschedulable 而不是永久饥饿；导入时 >30 分钟已被拒绝 | `test_item_larger_than_the_hard_cap_is_flagged_not_starved`（同一条目在大预算下能选中、在小预算下变成 unschedulable）；`test_single_pass_cap_rejects_oversized_item` 验证导入时的 30 分钟上限。 | 有测试，两条路径都覆盖 |
| 6 | 自评只能做全序最后一级 tie-break，不能改 due_date/间隔/跳过复习 | 修复前**完全没有专门测试**——`self_rating` 字段在契约层有校验（合法值枚举），但排序里"它是否真的只在最后一级生效"从未被验证过，纯粹是读代码"看起来对"。本轮新增 `test_self_rating_is_the_final_tiebreak_only`，不仅验证了赢家/输家的选择结果，还额外断言被 defer 的条目 `due_date`、`schedule`（间隔/易记因子等）完全未被 `self_rating` 影响。 | 本轮之前：无测试；本轮后：有专门测试，且验证了"不改状态"这个更强的约束 |
| 7 | 零写入：整个包不读不写 `F:\workspace\study`，不创建生产项目，不调用 AI | 我读了 `ky/` 下所有源文件，没有任何文件路径字面量指向 `study`、没有任何网络调用、没有任何写文件操作（唯一的文件 I/O 是 `_read_yaml_file` 里的只读 `path.read_text()`，以及 `--usage` 参数的只读 JSON 读取）。这一条我用**代码审查**而不是自动化测试证明——目前没有测试断言"整个测试运行期间没有任何文件被创建/修改"，这是一个可以自动化但目前没有自动化的检查点。 | 通过代码审查确认，**没有**自动化测试兜底（见 E 节） |

---

## C. 修复（已直接改代码，见变更清单）

修复后重新跑：

```text
$ py -3.12 -m unittest -v tests.test_contracts tests.test_review_scheduler
Ran 56 tests in 0.280s
OK
```

（49 条原有测试 + 7 条本轮新增，全部通过；原有测试没有一条被弱化或删除。）

修复后重新跑 preflight 正常路径，中文显示名不再乱码：

```text
new content budget : 66 min
  - 数学一         20 min (weight 0.40)
  - 英语一         25 min (weight 0.20)
  - 408         21 min (weight 0.40)

over capacity      : YES
```

修复后重新跑"合同违规"路径（新增的跨文件校验）：

```text
$ py -3.12 -m ky preflight --config tests/fixtures/config/config-minimal.yaml --items <bad_subject_item.yaml> --date 2026-09-12
contract violation: items[0].subject_id: subject_id 'math2' is not declared in config.subjects
exit=2
```

原有"权重不闭合"违规路径依旧正常：

```text
$ py -3.12 -m ky preflight --config tests/fixtures/config/config-weights-not-closed.yaml --items tests/fixtures/reviews/reviews-normal.yaml --date 2026-09-12
contract violation: subjects: active subject weights must sum to 1.0 (got 0.9)
exit=2
```

---

## D. 变更清单

| 文件 | 改了什么 | 为什么 | 验证方式 |
|------|---------|--------|---------|
| `ky/__main__.py` | `main()` 入口对 `sys.stdout`/`sys.stderr` 调用 `reconfigure(encoding="utf-8", errors="replace")` | 修复本机（GBK codepage）下管道/重定向输出时中文显示名乱码（A1） | 手工重跑 preflight，中文正确显示（对比修复前后的实际输出） |
| `ky/__main__.py` | 加载 config/items 后，在同一个 `try/except ContractError` 里调用 `validate_items_reference_known_subjects(config, items)` | 让"未知 subject_id"和其它契约违规一样 exit 2、带精确路径，而不是静默通过（A3） | 手工构造未知科目条目，确认 `contract violation: items[0].subject_id: ...`，exit 2 |
| `ky/models.py` | 新增 `validate_items_reference_known_subjects(config, items)`，加入 `__all__` | 提供 A3 所需的跨文件校验函数 | `tests/test_contracts.py::CrossContractTest` 两条新测试 |
| `ky/models.py` | `_load_subject` 增加"非活跃科目 `min_daily_minutes` 必须为 0"的对称检查 | 与"非活跃科目权重必须为 0"对称，堵住 A4 描述的死配置漏洞 | `test_inactive_subject_min_daily_minutes_must_be_zero` |
| `ky/models.py` | 删除未被任何代码调用的 `SubjectBudget.target_minutes()` | 死代码清理（A6） | 全量测试仍 56/56 通过 |
| `ky/schedule/review_clip.py` | `_deficit_ratio` 里 `except Exception` 收窄为 `except ContractError` | 避免掩盖排序过程中真实的编程错误（A2） | `test_an_item_with_an_unrecognised_subject_id_does_not_crash_selection` |
| `ky/schedule/review_clip.py` | 从 `ky.models` 额外导入 `ContractError` | 支撑上一条改动 | 同上 |
| `ky/schedule/review_clip.py` | 重写 `ITEM_TYPE_PRIORITY` 上方注释，使其如实描述代码行为 | 修正与代码矛盾的文档（A5） | 人工比对注释与 `ITEM_TYPE_PRIORITY` 字典 |
| `tests/test_contracts.py` | import 增加 `validate_items_reference_known_subjects`、`validate_review_items`；删除一处函数内的重复 inline import | 支撑新测试；顺手清理冗余 import | 全量测试通过 |
| `tests/test_contracts.py` | 新增 `test_inactive_subject_min_daily_minutes_must_be_zero`（`ConfigContractTest`） | 覆盖 A4 | 通过 |
| `tests/test_contracts.py` | 新增 `CrossContractTest`（`test_unknown_subject_id_in_review_item_is_rejected`、`test_known_subject_id_passes`） | 覆盖 A3 | 通过 |
| `tests/test_review_scheduler.py` | import 增加 `KaoyanConfig`、`SubjectBudget`；删除两处函数内重复 inline import | 支撑新测试；顺手清理冗余 import | 全量测试通过 |
| `tests/test_review_scheduler.py` | 新增 `_tiny_single_subject_config` 辅助函数 | 构造"当天预算恰好只够一项"的极端配置，用来单独锁定某一级 tie-break | 被下面四条新测试复用 |
| `tests/test_review_scheduler.py` | 新增 `test_lapses_break_ties_when_overdue_defer_and_deficit_are_equal` | 补上语义 3 里 `lapses` 维度此前完全没有的直接测试 | 通过 |
| `tests/test_review_scheduler.py` | 新增 `test_item_type_priority_breaks_ties_when_lapses_are_equal` | 补上语义 3 里条目类型维度此前完全没有的直接测试，同时把 A5 的行为锁进测试 | 通过 |
| `tests/test_review_scheduler.py` | 新增 `test_self_rating_is_the_final_tiebreak_only` | 补上语义 6（自评只做最后一级 tie-break、不改状态）此前完全没有的直接测试 | 通过 |
| `tests/test_review_scheduler.py` | 新增 `test_an_item_with_an_unrecognised_subject_id_does_not_crash_selection` | 覆盖 A2 收窄异常类型后的回归风险 | 通过 |

---

## E. 仍未解决（需要用户或审查者拍板）

1. **`ITEM_TYPE_PRIORITY` 的排序方向本身是否正确**（A5 相关）：我只修正了与代码矛盾的注释，没有改变 `error_pattern` 排在 `concept`/`procedure`/`question_pattern` 之后这一实际行为，因为这是一个产品判断（"错题订正到底该不该比普通概念复习优先"），不属于我能单方面拍板的范围，也没在 `docs/评审结论与实施契约.md` 里找到明文规定。需要用户明确这张表的排序意图，我再据此调整代码或补充文档。

2. **`due_date` 本身作为 tie-break 层级未被单独测试**：全序的第 5 层是 `item.due_date`（用于两个日期不同但其它维度都相同的条目）。本轮补齐了 `lapses`、条目类型、`self_rating` 三层，但 `due_date` 这一层严格来说仍然只是"看起来对"，没有专门锁定它的测试。之所以本轮没有补——构造一个"前四层严格相等但 due_date 不同"的用例，同时还要保证不触发 `is_due()` 的边界（`due_date <= today`），需要更仔细的日期设计，为了不引入仓促、可能有边界漏洞的新测试，我选择留给下一轮或由审查者决定优先级。

3. **`state: "scheduled"` 的语义完全没有测试、也没有实现路径覆盖**：`VALID_REVIEW_STATES` 包含 `queued`/`scheduled`/`suspended`/`retired`，但 `ReviewItem.is_due()` 只把 `queued` 当作可能到期，`scheduled` 状态的条目无论 `due_date` 是什么，永远不会出现在 `selected`/`deferred`/`unschedulable` 里的任何一个列表中——它对调度器来说完全隐形。这可能是有意设计（"scheduled 表示已经安排好但还不到可操作阶段"），也可能是一个被遗漏的状态。我没有足够的上下文去猜测正确语义并替它拍板实现，五个测试 fixture 里也没有一条使用 `scheduled` 状态。这个问题需要用户明确：`scheduled` 状态的条目应该何时、如何进入调度器的视野。

4. **`allocate_new_content` 的最大余数法在极端权重 + 超大预算下理论上可能丢分钟**：`validate_config` 允许活跃权重之和在 `1.0 ± 1e-6` 的容差内通过校验；`_proportional_split` 里"余量分配后的 `leftover`"理论上在**极端**情况下（权重之和达到容差上界、且预算达到数亿分钟量级）可能变成负数，导致该函数跳过"补分配"分支、静默返回一个总和略微偏离预算的结果，与语义 2 声称的"精确加总到预算，不丢分钟"这一绝对表述冲突。但我验证过：以本系统实际会出现的预算量级（`total_daily_minutes` 是"一天可用分钟数"，现实中不会超过 1440），`1e-6` 的权重容差乘以这个量级产生的偏差远小于 1 分钟的取整误差，实际不可能触发这条路径——我因此没有为一个在本系统真实输入范围内不可达的场景添加防御性代码（这与仓库准则"不要为不可能发生的场景加校验"一致）。写在这里是为了让审查者知道这个理论边界存在，且我是主动选择不修的，而不是没看到。

5. **没有自动化测试断言"整个测试运行期间没有写入 `F:\workspace\study`"**（语义 7）：我通过代码审查确认了这一点（`ky/` 下唯一的文件 I/O 是只读的 YAML/JSON 读取），但这是人工审查的结论，不是测试断言的结论。如果需要更强的保证，可以加一条测试在 `setUp`/`tearDown` 里快照 `F:\workspace\study` 的 mtime 或文件列表，跑完整个套件后比对无变化——我没有加，因为这依赖于 `F:\workspace\study` 这个外部目录的真实存在和结构，而任务书明确禁止我触碰这个目录，为了不冒任何误写风险我选择不做这个自动化检查，留给用户决定是否需要。

---

*本报告涉及的代码改动全部在 `ky/**` 与 `tests/**` 范围内；未修改 `review/**`、`docs/**`，未触碰 `F:\workspace\study`，未执行任何 git 操作。*
