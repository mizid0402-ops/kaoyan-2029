# 考试配置与预算切分端口（M8）

本规格描述 `ky/models.py` 的考试配置契约与 `ky/schedule/budget.py` 的预算切分，按
2026-09-27 的代码如实写出（WP-S1，不改行为）。与旧文档冲突时以本规格与代码为准；
冲突清单见 `review/rounds/round-151-ws1-specs-opus.md`。

M8 全部是纯函数：不读系统时钟、不取随机数；除 `load_config(path)` 读取调用方给出的那一个
文件外不做 IO。同样输入永远得到同样输出。

## 1. 对外接口

| 接口 | 所在 | 作用 |
|---|---|---|
| `load_config(path) -> KaoyanConfig` | `ky.models` | 读取 UTF-8 YAML 文件并校验 |
| `validate_config(raw, *, source="<mapping>") -> KaoyanConfig` | `ky.models` | 校验已解析的映射 |
| `load_config_mapping(mapping) -> KaoyanConfig` | `ky.models` | 等同 `validate_config(mapping)` |
| `KaoyanConfig`、`SubjectBudget`、`ReviewPolicy`（自评档位） | `ky.models` | 校验后的类型化配置 |
| `scale_minutes(total_minutes, ratio) -> int` | `ky.models` | 比例缩放的唯一算术（§4） |
| `WEIGHT_TOLERANCE` | `ky.models` | 权重容差 `1e-6` |
| `hard_review_cap_minutes(total_minutes, hard_max_ratio) -> int` | `ky.schedule.budget` | 当天复习硬上限，M8 / M9 / M27 共用 |
| `allocate_new_content(config, minutes, *, floor_policy="strict")` | `ky.schedule.budget` | 新学分钟按科切分（§5） |
| `SubjectAllocation` | `ky.schedule.budget` | 单科切分结果 |
| `idle_minutes(config, minutes) -> int` | `ky.schedule.budget` | 切分后剩余分钟，恒为 0 |
| `resolve_day_budget(day, config, availability, route) -> DayBudget` | `ky.schedule.budget` | 当天总时长与阶段复习配额（§6） |

`ky.models.ReviewPolicy`（`self_rating_mode`）与 `ky.schedule.review_clip.ReviewPolicy`
（紧急阈值，见 `contracts/review_clip.md`）是**两个不同的类**，同名但互不替代。

`KaoyanConfig` 与 `SubjectBudget` 是普通冻结数据类，直接构造不经过校验；只有
`load_config` / `validate_config` 的返回值保证满足本规格。

## 2. 文件格式

配置文件是 UTF-8 YAML，根是映射。工作区登记键为 `settings.exam_config`（可选登记）。

```yaml
schema_version: 1
project_id: kaoyan-2029
default_daily_minutes: 120
review_reserve_ratio: 0.45
hard_max_ratio: 0.60
review_policy:            # 可省略
  self_rating_mode: strict
subjects:
  - subject_id: math1
    display_name: 数学一
    weight: 0.40
    active: true
    min_daily_minutes: 0  # 可省略
```

### 2.1 根字段

根允许的键恰为下表七个；其他键一律拒绝。除 `review_policy` 外均必填，缺失时按该字段的
类型检查报错（例如 `expected an integer, got NoneType`），路径是字段名。

| 字段 | 类型 | 取值 | 含义 |
|---|---|---|---|
| `schema_version` | 整数 | 恰为 `1` | 先查整数且 `>= 1`，再查等于 1，否则 `unsupported schema_version` |
| `project_id` | 字符串 | 去空白后非空；不限字符集 | 项目标识，只用于展示与 JSON |
| `default_daily_minutes` | 整数 | `>= 1`，无上限 | 当天没有手填可用时间时的每日总分钟（回落值，见 §6） |
| `review_reserve_ratio` | 数 | 有限，闭区间 `[0, 1]`，无容差 | 复习软配额比例 |
| `hard_max_ratio` | 数 | 有限，`(0, 1]`，无容差，且 `>= review_reserve_ratio` | 复习硬上限比例 |
| `subjects` | 列表 | 非空 | 科目，见 §2.2 |
| `review_policy` | 映射 | 可省略；省略等于 `{}` | 见 §2.3 |

旧键 `total_daily_minutes`：拒绝并提示改名（B6，用户 2026-09-29）。配置中出现该键时，
无论是否同时出现 `default_daily_minutes`，均以路径 `total_daily_minutes` 报 `ContractError`，
提示在配置文件中改名为 `default_daily_minutes`；不会接受或自动转换旧键。

"整数"一律拒绝布尔值（`true` 不是 1）与浮点数（`120.0` 不是整数）。"数"接受整数或浮点、
拒绝布尔值与字符串，校验后以 `float` 保存（`0` 存为 `0.0`）；`NaN` 与 `±inf` 显式拒绝
（`expected a finite number`），不依赖区间比较碰巧拦下。

两个比例的区间检查**不带**权重容差：`-0.000001` 或 `1.000001` 都被拒（历史缺陷：带容差时
软配额会算出 -1 分钟）。

### 2.2 科目

每个科目映射允许的键恰为 `subject_id`、`display_name`、`weight`、`active`、
`min_daily_minutes`；前四个必填，`min_daily_minutes` 缺省为 0。路径形如
`subjects[<序号>].<字段>`。

| 字段 | 类型 | 规则 |
|---|---|---|
| `subject_id` | 字符串 | 去空白后非空；每个字符满足 `str.isalnum()` 或是 `-`、`_`（Unicode 字母数字也算） |
| `display_name` | 字符串 | 非空字符串；YAML 裸整数或整值浮点（`408`、`408.0`）按展示标签转成 `"408"`；布尔值与非整值浮点拒绝 |
| `weight` | 数 | 有限；区间 `[0, 1]` 两端各放宽 `WEIGHT_TOLERANCE` |
| `active` | 布尔 | 必须是真正的布尔值（`1` 被拒） |
| `min_daily_minutes` | 整数 | `>= 0`；每日新学保底分钟 |

科目内语义：

- 在考科目（`active: true`）的 `weight` 必须 `> 0`。
- 未启用科目的 `weight` 必须恰为 `0`，`min_daily_minutes` 必须恰为 `0`（切分只看在考科目，
  声明在未启用科目上的保底永远不会生效，所以直接拒绝而不是静默忽略）。

### 2.3 `review_policy`

只允许键 `self_rating_mode` 与 `algorithm`。`self_rating_mode` 取值 `strict`（缺省）或 `lenient`，其他值或非字符串以路径
`review_policy.self_rating_mode` 拒绝。`algorithm` 取值 `ladder`（缺省）或 `fsrs`（2026-10-01，`contracts/review_progress.md`"FSRS 算法"），其他值或非字符串以路径
`review_policy.algorithm` 拒绝；省略时行为与输出逐字节不变。`review_policy: null` 不等于省略：它不是映射，以路径
`review_policy` 拒绝。该档位由 M10 `LadderSm2Algorithm` 消费（`contracts/review_progress.md`）。

### 2.4 跨字段规则

全部单字段检查通过后依次检查：

1. `subject_id` 不重复；重复时路径指向**后出现**的那一项 `subjects[i].subject_id`。
2. 至少一个在考科目（路径 `subjects`）。
3. 在考科目权重之和与 1 的差不超过 `WEIGHT_TOLERANCE`（路径 `subjects`，消息带实际和）。
4. 每个科目的 `min_daily_minutes <= default_daily_minutes`（路径 `subjects[i].min_daily_minutes`）。
5. 保底与复习硬上限共用一天：在考科目保底之和 `<= default_daily_minutes -
   scale_minutes(default_daily_minutes, hard_max_ratio)`，否则以路径 `subjects` 拒绝。等号成立时接受。

## 3. 拒绝与错误路径

所有拒绝都抛 `ContractError(message, path)`（`ValueError` 子类），`str()` 为
`"<path>: <message>"`。只报告**第一处**错误，检查顺序固定：

1. 根是映射（否则路径为 `source`：文件时是其 POSIX 路径，映射时缺省 `<mapping>`）；
2. 旧键 `total_daily_minutes` 改名提示；
3. 根的未知键；
4. `schema_version`；
5. `review_policy`（先映射、再未知键、再档位值）；
6. `project_id`、`default_daily_minutes`、`review_reserve_ratio`、`hard_max_ratio`、
   `hard_max_ratio >= review_reserve_ratio`、`hard_max_ratio > 0`；
7. `subjects` 为非空列表（字符串 / 字节串不算列表）；
8. 逐个科目：映射 → 未知键 → `subject_id` → `display_name` → `weight` → `active` →
   `min_daily_minutes` → 科目内语义；
9. §2.4 的 1–5。

未知键：该层若有非字符串键（YAML `1: x`），先按出现顺序报告第一个；否则把多余的键排序后报告
第一个。消息为 `unknown field <键 repr>`，路径为 `<层路径>.<键>`（根层直接是键名），一律是字符串
（WP-R3）。拼错的字段（`min_daily_minute`）因此报错，而不是被当成缺省值。

`load_config(path)` 额外的读取错误：

| 情况 | 错误 |
|---|---|
| 文件不存在或不是文件 | `ContractError("file does not exist: <path>")`，`path` 属性为空串 |
| 读取失败或不是 UTF-8 | `ContractError("cannot read YAML: ...", <POSIX 路径>)` |
| 任一层映射出现重复键 | `ContractError("duplicate field '<键>' (line N); ...", <POSIX 路径>)` |
| YAML 语法错误 | `ContractError("invalid YAML: ...", <POSIX 路径>)` |

重复键由 `ky.models.load_yaml_text()` 的严格加载器拒绝：YAML 默认"后写的覆盖先写的"，
会让作者写下的值无痕消失，与拒绝未知键是同一类问题。

M14 CLI 把 `ContractError` 报为 `contract violation: ...` 并退出 2。

## 4. 比例缩放与复习上限

`scale_minutes(total, ratio) = floor(total × Fraction(str(ratio)))`，精确有理数运算。
`Fraction(str(ratio))` 取的是能往返到该浮点数的最短十进制，即配置作者写下的 `0.45`。
不得改回 `int(total * ratio)`：浮点乘法在 `total` 超过约 `1e308` 时溢出，且对不能有限表示
的比例会多进一分钟（`total=53, ratio=1/53` 时浮点得 1，本函数得 0）。配置对
`default_daily_minutes` 不设上限，所以算术必须对任意整数精确。

由此派生：

- `KaoyanConfig.review_target_minutes() = scale_minutes(default_daily_minutes, review_reserve_ratio)`
  —— 按配置总时长的复习软配额；
- `KaoyanConfig.review_hard_cap_minutes() = scale_minutes(default_daily_minutes, hard_max_ratio)`
  —— 按配置总时长的复习硬上限（M27 冻结阈值以它为单位）；
- `hard_review_cap_minutes(total, hard_max_ratio) = min(scale_minutes(total, hard_max_ratio), total)`
  —— 按**当天**总时长的硬上限，M8 配额缩放与 M9 裁剪共用这一个函数。

`KaoyanConfig` 其他派生视图：`active_subjects()` 按配置顺序返回在考科目；`subject(id)` 在全部
科目（含未启用）中查找，找不到时抛 `ContractError("unknown subject_id ...", "subjects")`；
`weight_of(id)` 返回其权重。

## 5. 新学分钟切分

`allocate_new_content(config, new_content_minutes, *, floor_policy="strict")
-> tuple[SubjectAllocation, ...]`

参数检查（均抛 `ValueError`，不是 `ContractError`），按顺序：

1. `floor_policy` 只能是 `"strict"` 或 `"drop_when_short"`；
2. `new_content_minutes >= 0`；
3. 配置至少有一个在考科目。

算法：

1. **保底先给**。在考科目保底之和 `floor_total` 大于预算时：
   `strict` 抛 `ValueError`（消息含 `min_daily_minutes sum`）；`drop_when_short` 把当天全部保底
   视为 0 再切分。否则每科先拿到自己的 `min_daily_minutes`。
2. **余量按权重切**。余量 `remainder = new_content_minutes - floor_total`；为 0 时各科额外为 0。
   否则：每个权重写成 `Fraction(str(weight))`，除以在考权重之和归一化（容差内的权重漂移因此
   不会超分）；每科精确份额 `remainder × 归一化权重` 向下取整；剩下的
   `leftover` 分钟（恒在 `[0, 在考科目数)` 内）逐一加给小数部分最大的科目，小数部分相同时按
   `subject_id` 字符串升序。整个过程无浮点，任意大的预算都精确。
3. 每科结果 = 实际给出的保底 + 权重份额，总和恰等于 `new_content_minutes`。

输出按配置中在考科目的顺序；未启用科目不出现。`SubjectAllocation` 字段：

| 字段 | 含义 |
|---|---|
| `subject_id`、`display_name`、`weight` | 抄自配置 |
| `minutes` | 当天该科新学分钟 |
| `floor_minutes` | 实际给出的保底；`drop_when_short` 放弃保底时为 0 |
| `floor_binding`（属性） | `floor_minutes > 0` 且 `minutes == floor_minutes` |

政策含义：保底是承诺、权重是偏好。保底整额先给、只切余量，所以有保底的科目总是高于
名义权重份额，预算再大也一样。

`idle_minutes(config, m) = m - sum(allocate_new_content(config, m).minutes)`（`strict`），
合法输入下恒为 0；非零表示切分漏分钟，调用方必须报告而不是吞掉。

## 6. 当天预算解析（D10 / M26）

`resolve_day_budget(day, config, availability, route) -> DayBudget`

| `DayBudget` 字段 | 含义 |
|---|---|
| `total_minutes` | 当天总分钟：M26 `resolve_daily_minutes` 的结果（有当日手填值取手填，否则取 `config.default_daily_minutes`） |
| `total_source` | `"availability"` 或 `"config"` |
| `subject_review_quotas` | 各在考科目当天常规复习配额；不在阶段内时为 `None` |
| `phase_index` | 命中的阶段序号或 `None` |
| `route_revision` | 命中阶段时为 `route.revision`，否则 `None` |

规则：

1. `route` 为 `None`，或没有阶段满足 `start <= day < end_exclusive`（右开）时，返回
   `(total_minutes, total_source, None, None, None)`，M9 按配置比例裁剪。
2. 命中阶段 i 时逐项校验 `phase.review_minutes`，错误路径均为
   `route.phases[i].review_minutes.<科目>`：
   - 键不是配置里的科目 → `未知的配置科目 ID`；
   - 键是未启用科目且分钟 `> 0` → `请先在配置中启用该科目，再设置复习分钟`（0 分钟接受）；
   - 在考科目（按 ID 排序）缺键 → `时间线阶段 i 缺少在考科目 <id> 的复习分钟`。
3. 配额只取在考科目，按 `subject_id` 升序成映射；未启用科目的 0 分钟不进入配额。
4. 当天硬上限 `cap = hard_review_cap_minutes(total_minutes, config.hard_max_ratio)`。配额之和
   `<= cap` 时原样使用；超过时按精确有理数最大余数法缩到恰好 `cap`：每科精确份额
   `cap × 配额 / 配额和` 向下取整，差额逐一给小数部分最大的科目，相同时按 `subject_id` 升序。

缩放后的配额之和 `<= cap`，满足 M9 对 `subject_review_quotas` 的前置条件。

## 7. 调用方如何组合（M14 `ky preflight` / M19 输入包）

两处用同一顺序，保证 M19 `review_clip` 与同配置的 `ky preflight --json` 去掉 `config` 后一致：

1. `resolve_day_budget(day, config, availability, route)`；路线只读一次，同一对象也用于 M19 的
   `route_plan` 字段。
2. M27 `assess_freeze` 判断是否冻结（`contracts/freeze.md`）。
3. 裁剪参数：冻结时 `daily_minutes_override=0` 且不传配额；否则总时长来源为
   `availability` 时传 `daily_minutes_override=total_minutes`；未冻结且有配额时传
   `subject_review_quotas`。来源为 `config` 时不传覆盖值，保持旧输出逐字节不变。
4. `select_daily_reviews(...)`（M9）。
5. `allocate_new_content(config, result.new_learning_minutes, ...)`：冻结或来源为
   `availability` 时用 `floor_policy="drop_when_short"`，否则用缺省 `strict`。配置的保底余量
   规则（§2.4-5）保证 `strict` 下按配置总时长永远不会因保底不够而失败。
6. `preflight_to_mapping(config, result, allocations)` 生成共享 JSON（`contracts/review_clip.md`）。

## 8. 验收

`py -3.12 -m unittest tests.contract.test_config_port tests.test_contracts
tests.contract.test_day_budget_port`
