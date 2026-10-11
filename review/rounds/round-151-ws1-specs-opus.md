# 第 151 轮 WP-S1 实现报告：M8 / M9 端口规格（opus）

- worktree：`F:\workspace\kaoyan-ai-system\.claude\worktrees\agent-a8bebb7e33c02fdc4`
- 分支：`worktree-agent-a8bebb7e33c02fdc4`（基于 `b43eb1f`）
- 未提交（按 `AGENTS.md`，由决策者提交）。
- 行为改动：**无**。`ky/models.py`、`ky/schedule/budget.py`、`ky/schedule/review_clip.py` 变异后均按原字节还原，
  SHA-256 与改动前一致（`47e5fbf2…`、`3fdb3111…`、`b0c170bf…`），`git status` 只有下列新文件。

## 1. 改动文件

| 文件 | 说明 |
|---|---|
| `contracts/config.md`（新） | M8 规格：配置文件格式、逐字段类型与取值、拒绝规则与检查顺序、`load_config` 读取错误、`scale_minutes` 与三种复习上限、新学切分算法、`resolve_day_budget`、调用方组合顺序 |
| `contracts/review_clip.md`（新） | M9 规格：入口检查顺序、容量（软配额 / 硬上限 / 拆分门槛）、八级优先级、紧急项、无配额与 D10 两遍规则、五个桶与会计不变量、延期语义、`summary()` / `preflight_to_mapping()` JSON 形状、调用方组合 |
| `tests/contract/test_config_port.py`（新） | 24 条契约测试 |
| `tests/contract/test_review_clip_port.py`（新） | 13 条契约测试 |
| `review/rounds/round-151-ws1-specs-opus.md`（新） | 本报告 |

未改 `docs/模块地图.md`（替换行见 §7）。

## 2. 规格摘要

### `contracts/config.md`（M8）

- 根键恰为 7 个（`review_policy` 可省），科目键恰为 5 个（`min_daily_minutes` 可省，缺省 0）；未知键排序后报第一个。
- 整数字段拒绝布尔与浮点；"数"字段接受 int / float、拒绝布尔 / 字符串，`NaN` / `±inf` 显式拒绝，存为 `float`。
- 两个比例 `[0, 1]` **无容差**，`hard_max_ratio > 0` 且 `>= review_reserve_ratio`；权重区间与"在考权重和 = 1"带 `1e-6` 容差。
- `display_name` 接受整值数字并转字符串；`subject_id` 只允许 `isalnum()`（含 Unicode）与 `-` `_`；`review_policy: null` 被拒。
- 跨字段：ID 不重复（报后出现者）→ 至少一个在考 → 权重和 → 单科保底 ≤ 总时长 → 在考保底和 ≤ 总时长 − 配置硬上限。
- 只报第一处错误，检查顺序写成清单；`load_config` 的四种读取错误（不存在、读失败 / 非 UTF-8、重复键、YAML 语法）。
- `scale_minutes = floor(total × Fraction(str(ratio)))`；`hard_review_cap_minutes = min(scale, total)` 是 M8 / M9 共用的当天硬上限。
- 切分：保底先给（`strict` 不够即 `ValueError`，`drop_when_short` 当天全部放弃），余量按归一化的精确分数权重取整，差额给小数部分最大者，同值按 `subject_id` 升序。
- `resolve_day_budget`：阶段右开区间命中规则、三类路线错误路径、配额只取在考科目并按 ID 排序、超出当天硬上限时精确最大余数缩放。
- §7 写明 `ky preflight` 与 M19 的组合顺序（预算 → 冻结 → 覆盖值 / 配额 → 裁剪 → 切分策略 → JSON）。

### `contracts/review_clip.md`（M9）

- 入口检查顺序：复习项科目（`ContractError`）→ 负覆盖值（`ValueError`）→ 配额键必须是在考科目、值必须是真 `int` 且 ≥ 0 → 配额和 ≤ 当天硬上限。
- 容量：`hard_cap`、`soft_target`（无配额按比例，有配额为配额和）、拆分门槛 `max(配置硬上限, 当天硬上限)`。
- 八级优先级表（含第 5 级 `due_date` 与第 1 级等价的说明、类型与自评的缺省值 99 / 4）；落后率只读配置总时长、不读覆盖值。
- 无配额时"逐项能放就放"、紧急项不插队；有配额时两遍规则（先紧急后普通，紧急项只借剩余空闲）。
- 五个桶的内容与顺序（selected / deferred / unschedulable 按优先级，scheduled_ahead / unreachable 按输入顺序），`scheduled` 当天到期即 `unreachable`；会计不变量；延期只改 `defer_count`。
- JSON：`summary()` 的 12 个键（有配额再加 2 个）、每项 6 个键、`unschedulable` 只列 ID；`preflight_to_mapping` 加 `subject_allocation` 与 `config`；冻结时调用方再加 `freeze`，M19 去掉 `config`。

## 3. 代码与旧文档不一致（规格以代码为准）

| # | 旧文档 / 注释 | 旧说法 | 代码实际 |
|---|---|---|---|
| 1 | `docs/评审结论与实施契约.md` §6.1、§7 交付物 1 | `ky/contracts/` 放 JSON Schema（`kaoyan_config.schema.json`、`review_item.schema.json`） | 没有 JSON Schema；形状与语义校验都在 `ky/models.py`（`ky/contracts/__init__.py` 是占位并如实说明） |
| 2 | 同上 §7 验收 | "与外层 120 分钟不一致 → 拒"；`review_minutes + new_learning_minutes = 120`；`review_minutes ≤ floor(120 × hard_max_ratio)` | 无"外层 120"检查；`review + new = 当天解析出的总时长`（覆盖值或配置值）；硬上限是 `min(floor(total × hard), total)`，`total` 按天解析。`阶段2决议` C2 / C3 / C6 已宣布作废，但旧文档未改 |
| 3 | `docs/阶段2决议-预算与词汇编排.md` C7 | "当日可用时间非法（≤0 或超上限）才拒" | 0 分钟合法（M26 接受 0；`daily_minutes_override=0` 是零复习日，冻结日即用 0）；只有负数被拒，且是 `ValueError`；没有上限 |
| 4 | 同上 §4 护栏 3 | 单项 30 分钟上限"需重新定基准" | 仍是固定 `MAX_SINGLE_PASS_MINUTES = 30`（M9 的拆分门槛另按 `max(配置硬上限, 当天硬上限)`） |
| 5 | 同上护栏 1；`docs/阶段1交付说明.md` §2 "四科预算切分" | "四科"活跃权重和必须 = 1 | 在考科目数任意（≥ 1），和在 `1 ± 1e-6` 内 |
| 6 | `docs/阶段1交付说明.md` §3.2 | `cost > 硬上限` → `unschedulable`；输出只列入选 / 延期 / unschedulable | 门槛是 `max(配置硬上限, 当天硬上限)`（sol 107 C2 / 109 N1）；输出为五个桶，另有 D10 配额模式 |
| 7 | `docs/模块拆分与架构审查.md` M8 B6；`KaoyanConfig` docstring | `total_daily_minutes` 是"唯一权威的每日预算"（B6 建议改名 `default_daily_minutes`） | 行为上它是回落值：当日手填可用时间优先（M26）。字段未改名，docstring 仍写 "single authoritative daily budget"，与行为不符 |
| 8 | `ky/schedule/review_clip.py` 模块 docstring | "fit inside one day's 120-minute budget" | 预算按天解析，不是固定 120 |
| 9 | `review_clip.py` `ITEM_TYPE_PRIORITY` 上方注释 | 类型优先级是"八级中的第五级" | 实为第六级（第五级是 `due_date`，且与第一级等价，从不单独起作用） |
| 10 | `ky/schedule/budget.py`、`review_clip.py` 模块 docstring | 规格指向 `contracts/route_plan.md` / `contracts/availability.md` | 现有专门规格 `contracts/config.md` / `contracts/review_clip.md`；未改 docstring（本包不动代码），建议下一包顺手更新（D7：模块头写明对应规格） |

## 4. 观察（不在本包修；由决策者裁定）

- **同名不同类**：`ky.models.ReviewPolicy`（`self_rating_mode`）与 `ky.schedule.review_clip.ReviewPolicy`（紧急阈值）；
  `ky.schedule.__init__` 导出的是后者。两份规格都写明了，建议日后改名其一（如 `UrgencyPolicy`）。
- `select_daily_reviews` 的 `daily_minutes_override` 只查 `< 0`，不查类型（布尔 `True` 会被当作 1）；负数抛 `ValueError` 而不是带路径的 `ContractError`。现有调用方只传 M26 解析出的整数，日常不会碰到。
- `allocate_new_content` 的参数错误同样是 `ValueError`；preflight 把它报为 `internal error`、退出 1（按注释是"合法配置不应走到这里"）。
- `load_config_mapping` 是公开名但不在 `ky.models.__all__` 里。

## 5. 安全登记（畸形输入，非日常问题）

- **现象**：配置根层（或某个科目映射）同时出现**非字符串键**和另一个未知键时，`_reject_unknown_keys` 对混合类型的键排序，抛
  `TypeError: '<' not supported between instances of 'str' and 'int'`（traceback，而非契约错误）；只有一个非字符串未知键时，
  `ContractError.path` 是整数而不是字符串。
- **触发**：手写 YAML 出现 `1: x` 这类数字键再加一个拼错的字段。实测：`validate_config` 上加 `{1: "x", "zz": 1}` → `TypeError`。
- **影响**：CLI 以 traceback 退出而非退出码 2；不丢数据。
- **可能的修法**：同 M26 的做法（`contracts/availability.md`），排序前先把非字符串键作为契约错误报出。

## 6. 变异结果

每条新测试做一处针对性变异，`PYTHONDONTWRITEBYTECODE=1`，只跑该测试，随即按原字节还原并核对 SHA-256。37 / 37 变红，全部已还原。

| 测试 | 变异（文件：改动） | 结果 |
|---|---|---|
| `ConfigFormatTests.test_fixture_maps_field_by_field_with_documented_defaults` | models：`self_rating_mode` 缺省 `"strict"` → `"lenient"` | FAILED (failures=1) |
| `…test_each_missing_required_root_field_is_reported_at_its_path` | models：`subjects` 非列表错误路径 → `"subject_list"` | FAILED (failures=1) |
| `…test_integer_fields_reject_booleans_and_floats` | models：`_require_int` 去掉 `isinstance(value, bool)` | FAILED (failures=3) |
| `…test_number_fields_reject_booleans_and_strings_but_accept_integers` | models：`_require_float` 去掉布尔拒绝 | FAILED (failures=2) |
| `…test_weight_tolerance_applies_to_weights_only` | models：权重和容差放大 10 倍 | FAILED (failures=1) |
| `…test_hard_ratio_may_equal_reserve_but_must_be_positive` | models：`hard < reserve` → `<=` | FAILED (errors=1) |
| `…test_display_name_coerces_integral_numbers_only` | models：任意浮点都转整数字符串 | FAILED (failures=1) |
| `…test_subject_id_allows_letters_digits_dash_and_underscore_only` | models：字符集加入 `.` | FAILED (failures=1) |
| `…test_review_policy_mode_values_and_shape` | models：`review_policy: null` 当作 `{}` | FAILED (failures=1) |
| `…test_unknown_keys_report_the_first_in_sorted_order` | models：`unknown[0]` → `unknown[-1]` | FAILED (failures=1) |
| `…test_subject_level_semantics_report_documented_paths` | models：在考权重 `<= 0` → `< 0` | FAILED (failures=1) |
| `…test_the_first_failing_check_in_documented_order_wins` | models：`validate_config` 中 schema 与 policy 两步互换 | FAILED (failures=1) |
| `LoadConfigFileTests.test_file_read_errors_are_contract_errors_with_the_file_path` | models：`cannot read YAML` 消息改写 | FAILED (failures=1) |
| `…test_duplicate_key_inside_a_subject_is_rejected` | models：`duplicate = key in seen` → `False` | FAILED (failures=1) |
| `…test_file_and_mapping_validation_agree` | models：严格加载器基类改为 `yaml.BaseLoader` | FAILED (errors=1) |
| `ConfigViewTests.test_subject_lookup_covers_inactive_subjects_and_rejects_unknown` | models：`subject()` 错误路径 → `"subject"` | FAILED (failures=1) |
| `…test_day_hard_cap_is_the_scaled_ratio_bounded_by_the_total` | budget：去掉 `min(..., total)` | FAILED (failures=1) |
| `NewContentSplitTests.test_allocations_follow_active_config_order_and_carry_their_floors` | budget：`floor_minutes=0` | FAILED (failures=1) |
| `…test_each_weighted_share_is_the_floor_or_ceiling_of_its_exact_value` | budget：按总预算而非余量切分 | FAILED (failures=299) |
| `…test_largest_remainder_wins_and_only_ties_fall_back_to_subject_id` | budget：差额只按 ID 分配 | FAILED (failures=1) |
| `…test_argument_checks_and_waived_floors` | budget：`drop_when_short` 仍保留保底 | FAILED (failures=1) |
| `DayBudgetResolutionTests.test_without_a_phase_the_budget_carries_only_the_total` | budget：无阶段时来源固定为 `"config"` | FAILED (failures=1) |
| `…test_quotas_are_active_only_sorted_and_carry_phase_and_revision` | budget：配额按路线键顺序而非 ID 排序 | FAILED (failures=1) |
| `…test_oversized_quotas_scale_to_the_cap_by_exact_largest_remainder` | budget：缩放差额给排序末尾的科目 | FAILED (failures=1) |
| `ReviewClipPortTests.test_entry_checks_run_in_documented_order` | review_clip：负覆盖值改抛 `ContractError` | FAILED (failures=1) |
| `…test_quota_keys_must_be_active_and_values_plain_integers` | review_clip：`type(minutes) is not int` → `not isinstance(...)` | FAILED (failures=1) |
| `…test_a_miss_does_not_stop_smaller_lower_ranked_items` | review_clip：超硬上限后其余全部延期并 `break` | FAILED (failures=1) |
| `…test_urgent_items_do_not_jump_ahead_without_quotas` | review_clip：无配额循环先处理紧急项 | FAILED (failures=1) |
| `…test_overdue_threshold_is_inclusive` | review_clip：逾期阈值 `>=` → `>` | FAILED (failures=1) |
| `…test_type_and_self_rating_levels_including_their_defaults` | review_clip：无自评缺省名次 4 → -1 | FAILED (failures=1) |
| `…test_ranking_reads_the_configured_total_not_the_override` | review_clip：落后率目标乘 0（模拟读零覆盖值） | FAILED (failures=1) |
| `…test_new_learning_minutes_is_the_resolved_total_minus_review` | review_clip：新学分钟按配置总时长算 | FAILED (failures=1) |
| `…test_quota_mode_reports_every_quota_key_and_omitted_subjects_get_zero` | review_clip：`subject_used` 初始化为空 | FAILED (failures=1) |
| `…test_scheduled_item_due_today_is_unreachable` | review_clip：`due_date > today` → `>=` | FAILED (failures=1) |
| `…test_scheduled_buckets_keep_input_order` | review_clip：scheduled 分桶前按 ID 排序 | FAILED (failures=1) |
| `…test_deferral_changes_nothing_but_defer_count` | models：`with_deferral` 丢弃自评 | FAILED (failures=1) |
| `…test_summary_and_preflight_mapping_have_exactly_the_documented_keys` | review_clip：`unschedulable` 输出完整对象 | FAILED (failures=1) |

## 7. 测试输出

```text
$ py -3.12 -m unittest tests.contract.test_config_port tests.contract.test_review_clip_port tests.test_contracts tests.test_review_scheduler
Ran 139 tests in 1.109s
OK
```

全量：未跑（按 AGENTS.md，由决策者提交前统一跑）。新测试的期望值全部从 `tests/fixtures/` 推导，未写科目 ID、年份或数据条数字面量；
与 `tests/test_contracts.py`、`tests/test_review_scheduler.py` 已有断言不重复（例如权重不闭合、比例倒置、NaN、1e-6 比例边界、
逐级 tie-break 的相邻两级、紧急借用、未来 / 过期 scheduled 项已由旧测试覆盖，新测试只补规格里新写明、旧测试没钉住的规则）。

## 8. 建议的模块地图替换行

```markdown
| **M8 预算切分** | 考试配置契约（字段、校验顺序、错误路径）；科目权重 → 每科每日新学分钟（保底先给、余量精确最大余数）；合并 M26 总时长与 D10 路线阶段复习配额 | `contracts/config.md`（另见 `contracts/availability.md`、`contracts/route_plan.md`） | `ky/models.py`（`load_config()`、`validate_config()`、`scale_minutes()`）、`ky/schedule/budget.py`（`allocate_new_content()`、`resolve_day_budget()`、`hard_review_cap_minutes()`） | —（配置路径由调用方从 `settings.exam_config` 解析） | **A**（纯函数） | `py -3.12 -m unittest tests.contract.test_config_port tests.test_contracts tests.contract.test_day_budget_port` |
| **M9 复习裁剪** | 按八级优先级与软配额 / 硬上限（或 D10 分科配额两遍规则）确定性选出今天复习什么；五个输出桶与会计不变量；提供 CLI / M19 共用的预检 JSON 映射 | `contracts/review_clip.md`（配额来源见 `contracts/route_plan.md`） | `ky/schedule/review_clip.py`（`select_daily_reviews()`、`preflight_to_mapping()`） | — | **A**（纯函数） | `py -3.12 -m unittest tests.contract.test_review_clip_port tests.test_review_scheduler tests.contract.test_planner_port` |
```

块名加粗表示"端口已定型"（与 M0 / M7 / M12 等同样的约定）；如决策者认为 M8 / M9 还需评审后再加粗，可去掉 `**`。

## 9. 建议

- 下一包顺手把 `budget.py` / `review_clip.py` 模块 docstring 的规格引用改为新规格，并更正第 §3 表 7–9 行的过时注释（纯注释改动）。
- `docs/评审结论与实施契约.md` §6.1 / §7 与 `docs/阶段1交付说明.md` §3.2 可加一行"已被 `contracts/config.md` / `contracts/review_clip.md` 取代"的指引，避免新读者按旧验收标准判断。
