# 第五轮：跨模型独立高级审查（Claude Opus 5，high effort）

> 独立审查者：Claude Opus 5 · 与前四轮的 Codex / gpt-5.6-sol 无共享会话
> 全部数字为本机 `py -3.12` 实测，非引用上一轮
> 最终：`Ran 102 tests OK` · `13/13 checks passed` · 全仓 discovery `Ran 112 tests OK`

---

## 裁决（先给结论）

**有条件通过。** 条件：本报告 §C 的 **BLOCKER-1 / MAJOR-2 / MAJOR-3 已由我在本轮修复并验证**
（见 §B），条件视为当场关闭；剩余的 `MAJOR-4`（`state: scheduled` 语义未定义）需要你做一次
产品决定，但它**不阻塞**阶段 1 冻结，因为我已经把它从"静默"变成"有测试钉住"。

对上一轮（round-4 Codex）的总体判断：

- 它的 **三条最小修法方向全部成立**，但**理由部分不成立、remedy 之一是错的**（会丢覆盖）。
- 它把 M1 定级 **MAJOR 并据此 FAIL 整个 Gate，定级过重**。我给出的证据是：它所担心的两个测试在其断言域内
  **不存在任何可触发的失败**，首个分歧点在 `9.0e15` 量级，比测试域（`total ≤ 5000`）高 12 个数量级。
  这是**契约卫生（hygiene）问题，不是正确性问题**，应为 `MINOR`。
- **任务书转述 round-4 时把反例数字写错了**（见 §A.1），而 round-4 报告里的原始数字是**对的**。
- round-4 **漏掉了 1 个 BLOCKER 和 2 个 MAJOR**（`_deficit_ratio` 溢出、YAML 重复键静默吞掉、
  比例字段容差）——其中前两个恰好属于它自己宣称已经关闭的失败类别。
- 任务 D 上：它的**结论正确，但它给出的首要理由（性能）经我实测基本不成立**。真实理由只有两条，
  见 §D。

---

## A 独立复核上一轮的三条"最小修法"

### A.0 先纠正一处事实：任务书给的反例是错的，round-4 自己写的是对的

任务书 §任务 A 称 round-4 给出的反例是 `total = 9007199254740993`（即 `2**53 + 1`）。
**这个数字在 `ratio ∈ {0.45, 0.60}` 上不构成反例。** 实测：

```text
total = 9007199254740993   (= 2**53 + 1)
float(total) = 9007199254740992.0     可精确表示? False   ← 转 double 时已丢掉个位

  ratio=0.45 : exact = 4053239664633446   legacy = 4053239664633446   equal=True
  ratio=0.60 : exact = 5404319552844595   legacy = 5404319552844595   equal=True
```

原因：`2**53 + 1` 无法用 binary64 表示，`total * ratio` 先把 `total` 舍入回 `2**53`，
而 `2**53` 与 `2**53+1` 乘 `0.45` 后 floor 恰好落在同一整数上，**两边反而一致**。

round-4 报告正文（`round-4-codex.md:55-61`）写的是 `9007199254740973`（= `2**53 − 19`），
**这个数字是对的**，我逐位复现：

```text
total = 9007199254740973   (= 2**53 - 19)
float(total) = 9007199254740973       可精确表示? True

  ratio=0.45 : exact = 4053239664633437   legacy = 4053239664633438   diff = -1
  ratio=0.60 : exact = 5404319552844583   legacy = 5404319552844584   diff = -1
```

与 round-4 声称的四个数字**完全一致**。结论：**转述有误，被审查方（round-4）无责。**
后续任何引用请用 `9007199254740973`。

补充实测（round-4 没做，但它的主张依赖这个）：

```text
ratio=0.45, total = 1..200000 : 0 处不一致
ratio=0.60, total = 1..200000 : 0 处不一致
total = 10**309, ratio=0.45/0.60 : exact 正常返回；legacy 抛 OverflowError
```

所以"与旧 float 一致"的**实际安全边界远大于 `1..20000`**，至少到 `2e5` 为 0 分歧，
首个分歧在 `9.0e15` 量级。这个数字很重要，它直接决定了 A.1 的定级。

### A.1 第 1 条（删除/改写两个 float 对比测试）——**方向成立，理由部分不成立，remedy 错**

round-4 的技术主张分三层，我逐层核实：

| round-4 的主张 | 我的核实 | 判定 |
|---|---|---|
| 两测试以 `int(total*ratio)` 为失败基准，失败信息是"exact scaling diverged from the float product" | 属实，`test_contracts.py:559/565/573` 原文如此 | **成立** |
| 这"把旧 float 当权威" | 成立。契约写的是 `floor(total × ratio)`，float 乘法只是被替换掉的实现 | **成立** |
| 这些测试"额外冻结了 `0.05/0.99/0.01/1.0/0.75/0.125`"，构成风险 | **不成立/过重**。在 `total ≤ 5000` 上 8 个终止小数的 float 误差约 `1e-13`，首个分歧在 `9e15` 量级；这些断言在其域内**不可能变红** | **反驳** |

因此我**反驳 round-4 的定级**：这不是 MAJOR，更不构成 FAIL 整个 Gate 的理由。它是真实的、
应该修的**契约卫生问题**——错在**规范性信号**（告诉后来的读者"float 是真值"），
不错在**可触发的行为**。正确定级是 `MINOR`。

**更重要的是：round-4 首选的 remedy（"删除，因为获准范围已由 `test_the_projects_own_ratios_are_unaffected` 覆盖"）是错的。**
那句话在覆盖上不成立：

- 被删的两个测试覆盖 **8 个比例 × `total 1..5000`** 和 **8 个比例 × 10 个现实预算**；
- `test_the_projects_own_ratios_are_unaffected` 只覆盖 **2 个比例**；
- `test_exact_contract_holds_across_a_cross_product` 只有 **12 个 total 采样点**。

按 round-4 的首选做法执行，`0.05 / 0.99 / 0.01 / 1.0 / 0.75 / 0.125` 在 `1..5000` 全域上的
**精确契约覆盖会直接归零**。这是净损失。

### A.2 "收窄"还是"彻底删掉"——我的判断

**都不对。正确做法是"改基准、保域"，并只保留一个被正确命名的迁移回归。**

推理，严格按契约走：

1. 契约是 `floor(total × Fraction(str(ratio)))`。**float 乘法不是这个契约的定义**，
   它是被替换掉的那个实现。因此任何**通用**测试都不能拿它当右手边。
2. 但"实现替换没有改变出货配置的任何一个数"是一个**有价值且不同的命题**——它是
   **迁移回归（migration regression）**，不是契约。这个项目自己写下的教训正是
   "替换实现时，行为不变必须被验证，不能靠断言"。彻底删掉这类测试，等于把那条教训的**证据**也删了。
3. 所以：**通用测试改为精确有理基准（域不变，因此覆盖只增不减）；迁移回归保留恰好一个，
   命名和 docstring 必须自己声明它是迁移回归而不是契约，并写死数值域和已知边界。**

改基准而非删除，还带来一个 round-4 没注意到的**增益**：原测试断言 `exact == legacy`，
如果两者**一起漂移**它不会红；改成 `exact == floor(total × Fraction(str(ratio)))` 之后会红。
**改完的测试严格强于改之前。**（§C 变异 R3/R8 实测证实：改写后的
`test_exact_contract_holds_across_the_everyday_range` 参与了对 ceil 变异的绞杀。）

### A.3 第 2 条（docstring 写明范围）——**成立**

`test_the_projects_own_ratios_are_unaffected` 的 docstring 原文只有 "the range that matters"
和 "this range"，而断言体是 `range(1, 20001)`。文档与断言不一致，成立，已修。

### A.4 第 3 条（`_scale_minutes` docstring 的全称断言）——**成立**

原文："For the ratios this project ships (`0.45`, `0.60`) the two agree **everywhere a study
budget can reach**."

这是全称命题，且被 §A.0 的实测反例证伪（`total = 9007199254740973`）。它还与**同一段 docstring
上一条**（"binary float multiplication raises OverflowError once total passes roughly 1e308"）
自相矛盾——既然合同接受 `1e308` 以上的预算，那就存在 float 根本算不出来的 budget，
"everywhere a study budget can reach"必然为假。成立，已修。

### A.5 它漏了什么（补充）

round-4 这一轮的**范围太窄**：它只复核了自己上一轮开的三个条件，没有重新审查实现。
结果是它在宣布"精确算术实现没有问题"的同时，漏掉了**同一个失败类别**的三个新实例：

1. **`_deficit_ratio` 仍会 `OverflowError`**（§C BLOCKER-1）——它在 round-4 里逐字引用了
   `_deficit_ratio` 的 docstring 关于"exact rational 避免 OverflowError"的说法，**但没有去跑**。
2. **YAML 重复键被静默丢弃**（§C MAJOR-2）——这是整条审查链的旗舰发现 M1
   （"未知键被静默忽略"）的**同类**，四轮无人发现。
3. **`WEIGHT_TOLERANCE` 泄漏到比例字段**（§C MAJOR-3），可产生 `-1` 分钟的软配额。

---

## B 执行修复

允许域内实际改动：`ky/models.py`、`ky/schedule/review_clip.py`、
`tests/test_contracts.py`、`tests/test_review_scheduler.py`、`tests/test_cli.py`。
未触碰 `review/**`、`docs/**`、`README.md`、`tools/**`、`F:\workspace\study`；未执行 git。
未触碰另一模型正在新建的 `ky/storage/**`、`ky/knowledge/**`、`tests/test_storage.py`、
`tests/test_knowledge_contract.py`。

### B.1 关闭 round-4 的三个条件

| # | 文件 | 改动 |
|---|---|---|
| 1 | `tests/test_contracts.py` | `test_matches_the_float_product_across_the_everyday_range` → `test_exact_contract_holds_across_the_everyday_range`：**域不变**（8 比例 × `1..5000`），基准改为 `floor(total × Fraction(str(ratio)))` + `0 <= actual <= total` |
| 1 | `tests/test_contracts.py` | `test_matches_the_float_product_at_realistic_daily_budgets` → `test_exact_contract_holds_at_realistic_daily_budgets`：同上，新增共享断言助手 `assert_exact_contract()`（含 `actual <= product < actual+1`） |
| 2 | `tests/test_contracts.py` | `test_the_projects_own_ratios_are_unaffected` → `test_migration_regression_shipped_ratios_match_the_old_float_product`。docstring 明写 `ratio in {0.45, 0.60}`、`total in 1..20000` inclusive，声明**它是迁移回归不是契约**，并写明"红了要查迁移，不是判定 `_scale_minutes` 错" |
| 2+ | `tests/test_contracts.py` | 新增 `test_the_shipped_ratios_float_agreement_is_bounded_not_universal`：把 `9007199254740973` 的四个数字和 `10**309` 的 `OverflowError` **钉死**，防止有人把迁移回归重新扩张成全称保证 |
| 3 | `ky/models.py` | `_scale_minutes` docstring：删掉 "agree everywhere a study budget can reach"，换成**实测边界**（`1..200000` 零分歧）+ 反例数值 + `1e308` 溢出说明 + "两者不一致时精确值为准" |

### B.2 我自己发现的缺陷的修复

| # | 文件 | 改动 |
|---|---|---|
| BLOCKER-1 | `ky/schedule/review_clip.py` | `_deficit_ratio` 返回类型 `float` → `Fraction`，删除 `float()` 转换。排序键只需要可比较，`Fraction` 全域可比且精确 |
| MAJOR-2 | `ky/models.py` | 新增 `_StrictSafeLoader`（`yaml.SafeLoader` 子类，重复映射键抛错）+ `_DuplicateKeyError`；`_read_yaml_file` 改用它并翻译为带路径和行号的 `ContractError` |
| MAJOR-3 | `ky/models.py` | `_require_float` 新增 `tolerance` 参数（默认仍为 `WEIGHT_TOLERANCE`，权重行为完全不变）；`review_reserve_ratio` / `hard_max_ratio` 显式传 `tolerance=0.0` |
| MAJOR-4 | `tests/test_review_scheduler.py` | **不改语义**（那是产品决定），改为新增 `test_a_scheduled_item_falls_out_of_every_output_bucket` 把当前行为钉死并在 docstring 标注为未决问题 |

新增回归测试 14 条（102 − 88）。

### B.3 规定检查的真实完整输出

```text
$ py -3.12 -m unittest tests.test_contracts tests.test_review_scheduler tests.test_cli
......................................................................................................
----------------------------------------------------------------------
Ran 102 tests in 2.332s

OK
exit code = 0
```

```text
$ py -3.12 tools/verify_round3_findings.py
[PASS] M1 unknown key in subject: subjects[0].min_daily_minute: unknown field 'min_daily_minute'
[PASS] M1 unknown key at root: totle_daily_minutes: unknown field 'totle_daily_minutes'
[PASS] M1 reviews root schema_version: F:/workspace/kaoyan-ai-system/tests/fixtures/reviews/reviews-unsupported-schema-version.yaml.schema_version: unsupported schema_version 99
[PASS] M1 reviews unknown root key: F:/workspace/kaoyan-ai-system/tests/fixtures/reviews/reviews-bad-schema-version.yaml.iten: unknown field 'iten'
[PASS] M2 unknown subject rejected: items[0].subject_id: subject_id 'ghost' is not declared in config.subjects
[PASS] M2 inactive subject rejected: items[0].subject_id: subject_id 'politics' refers to an inactive subject
[PASS] M3 floor-vs-hardcap conflict: rejected at contract stage: subjects: sum of active min_daily_minutes (60) leaves less than the review hard cap (72) of new-content room out of 120 total minutes; lower the floors or hard_max_ratio
[PASS] M4 weight=nan rejected: subjects[0].weight: expected a finite number, got nan
[PASS] M4 weight=inf rejected: subjects[0].weight: expected a finite number, got inf
[PASS] M4 weight=-inf rejected: subjects[0].weight: expected a finite number, got -inf
[PASS] M4 review_reserve_ratio=nan rejected: review_reserve_ratio: expected a finite number, got nan
[PASS] M4 review_reserve_ratio=inf rejected: review_reserve_ratio: expected a finite number, got inf
[PASS] B tolerance-sum overspend: allocated 2000000 for a 2000000 budget

13/13 checks passed
exit code = 0
```

另外两项（非任务书要求，用于证明没有殃及他人和 CLI）：

```text
$ py -3.12 -m unittest discover -s tests -t .
Ran 112 tests in 35.752s
OK                       # 含另一模型新建的 test_storage / test_knowledge_contract，未被我的改动破坏

$ py -3.12 -m ky preflight --config tests/fixtures/config/config-minimal.yaml \
      --items tests/fixtures/reviews/reviews-overloaded.yaml --date 2026-09-12
review soft / hard : 54 / 72 min (ratio 0.45 / 0.6)
selected           : 6  -> 54 min          # 与阶段 1 交付说明记录的输出一致
exit = 0
```

### B.4 最终文件哈希（SHA-256）

```text
ky/models.py                       3F7AA5A089471072D85E8BD897A28C65F33388741C2EE044739E3FED3B8592B5
ky/schedule/review_clip.py         DF137D18479D04604B8CA4C943B095A9A0A9F459633DFF6C4E1EDE12D7906C38
ky/schedule/budget.py              DA5D5F0935EF3BC87C2D7F732F675F214032493142585F5D130EA01A15C2364F   (未改动)
ky/__main__.py                     86DD4B9AD13821563A224F5420F5FF61B3EB6CCDF4F677DDC0919578F9F1EDA7   (未改动)
tests/test_contracts.py            77CDA16BB7AD237AAF2B241AEDEF82093AB16B6BFD819B7C677251BCF141A6C2
tests/test_review_scheduler.py     6B696FBC7B7CF2CAB9BA9B583D45A783ECD0A0C054B6EE87F21449CD43B91EAE
tests/test_cli.py                  C7EA43A386F2A3CE7ECC5F62D3FFEAB33E43D2329C4719EBD219F991B9AC3503
```

`ky/schedule/budget.py` 的哈希与 round-4 报告记录的 `DA5D5F09...2364F` 一致，可交叉验证。

---

## C 我的独立缺陷清单

### BLOCKER-1 — `_deficit_ratio` 在合同接受的输入上抛出未捕获的 `OverflowError`

- **位置**：`ky/schedule/review_clip.py:150`（修复前）`return float((target - actual) / target)`
  调用链 `ky/schedule/review_clip.py:170` → `:212` `sorted(...)`；CLI 入口 `ky/__main__.py:147`
- **触发条件**：`seven_day_usage` 中任一数值大到使 `actual / target` 超出 binary64 范围。
  合同对 `seven_day_usage` **没有上界**，`ky/__main__.py:124` 只校验"非负整数"。
- **最小复现**：

  ```text
  usage.json = {"math1": 1e400 的整数形式}
  py -3.12 -m ky preflight --config tests/fixtures/config/config-minimal.yaml \
        --items tests/fixtures/reviews/reviews-overloaded.yaml \
        --date 2026-09-12 --usage usage.json
  ```

- **实际输出（修复前，实测）**：

  ```text
  returncode = 1
  stdout 行数 = 0
  Traceback (most recent call last):
    File "F:\workspace\kaoyan-ai-system\ky\__main__.py", line 147, in main
      result = select_daily_reviews(config, items, today, seven_day_usage=usage, policy=policy)
    File "...\review_clip.py", line 212, in select_daily_reviews
      ranked = sorted(due, key=lambda item: _sort_key(item, today, config, usage))
    File "...\review_clip.py", line 150, in _deficit_ratio
      return float((target - actual) / target)
    File "...\Lib\numbers.py", line 316, in __float__
      return int(self.numerator) / int(self.denominator)
  OverflowError: integer division result too large for a float
  ```

- **期望**：`ky/__main__.py` 的 docstring 明确只承诺四个退出码 `0/1/2/3`，且
  `tests/test_cli.py` 对正常路径断言 `assertNotIn("Traceback", result.stderr)`。
  合同有效的 config + 合同有效的 items + CLI 自己校验通过的 usage，**必须**落在文档化的干净路径上。
- **为什么是 BLOCKER**：这正是 round-3 为 `_scale_minutes` 修掉的那个失败类别
  （"float 溢出逃逸成 traceback 而不是文档化退出码"），并且 `_deficit_ratio` 的 docstring
  **明文声称**已经用精确有理算术解决了它。精确算术只挡住了 `target` 一侧，
  **`actual` 一侧的溢出被 `float()` 转换重新引入**。声明与行为不符，属于阶段 1 三条门槛里
  "算法确定"的直接违反。
- **修法（已实施）**：`_deficit_ratio` 返回 `Fraction`，彻底删除 `float()` 转换。
  排序键只要求元素可比较，`Fraction` 满足且精确。
- **副收益**：tie-break 同时变精确。修复前两个科目的落后率若相差小于 1 ulp 会被 float
  压成同一名次并掉到 `review_id` 兜底；修复后不会。已由
  `test_the_deficit_tiebreak_stays_exact_for_near_identical_subjects` 钉住。
- **验证**：变异 R5（把 `float()` 加回去）→ 3 个测试变红，见 §C.5。

### MAJOR-2 — YAML 重复键被静默丢弃（"last wins"），`_reject_unknown_keys` 结构上看不到

- **位置**：`ky/models.py:225`（修复前）`return yaml.safe_load(text)`
- **触发条件**：任意合同文件把同一个字段写两次。
- **最小复现 + 实际输出（修复前，实测）**：

  ```text
  复习条目写 estimated_minutes: 999 然后 estimated_minutes: 10
    -> ACCEPTED, estimated_minutes = 10        （999 被无声丢弃，单次上限校验被完全绕过）

  config 写 total_daily_minutes: 120 然后 total_daily_minutes: 30
    -> ACCEPTED, total_daily_minutes = 30      （声明的 120 被无声丢弃）
  ```

- **期望**：拒绝，并给出字段路径。
- **为什么是 MAJOR**：这与整条审查链的旗舰发现 **M1（"未知/拼错的键被静默忽略"）是同一个失败类别**
  ——作者真实写下的值被无声丢弃。而且 `_reject_unknown_keys` **结构上不可能**抓到它：
  YAML 在到达 Python 之前就已经把重复键塌缩掉了，等 mapping 交到校验层时那个值已经不存在了。
  四轮审查、两个模型、13 项独立验证脚本，全部漏掉。
  破坏面比 M1 更大：M1 只会让一个字段**回落到默认值**，这个会让它**回落到攻击者/笔误选定的另一个值**。
- **修法（已实施）**：`_StrictSafeLoader` 子类重写 `construct_mapping`，重复键抛
  `_DuplicateKeyError`，`_read_yaml_file` 翻译成带文件路径和**行号**的 `ContractError`。
  实测输出：

  ```text
  ContractError: <path>: duplicate field 'estimated_minutes' (line 11);
                 YAML would silently keep only the last one
  ```

- **回归风险已验证**：7 个出货 fixture 用 `SafeLoader` 与 `CSafeLoader` 解析结果逐一比对
  `identical=True`，且 `test_the_shipped_fixtures_still_load` 钉住了它们仍然正常加载。
- **验证**：变异 R6（改回 `yaml.safe_load`）→ 4 个测试变红。

### MAJOR-3 — `WEIGHT_TOLERANCE` 泄漏到比例字段，产生 **−1 分钟**的软配额

- **位置**：`ky/models.py:177-180`（修复前）`_require_float` 无条件用 `WEIGHT_TOLERANCE`
  松弛上下界；`ky/models.py:374-379` 的两个比例字段沿用了它。
- **触发条件**：`review_reserve_ratio: -0.000001`（恰好落在容差边界上）。
- **最小复现与实际输出（修复前，实测）**：

  ```text
  review_reserve_ratio = -1e-06   -> ACCEPTED, review_target_minutes() = -1
  review_reserve_ratio = -1.1e-06 -> rejected
  hard_max_ratio       = 1.000001 -> ACCEPTED
  ```

  该 `-1` 会直接进入 preflight 的人读输出（`review soft / hard : -1 / 72 min`）
  和 `--json` 载荷的 `soft_target_minutes` 字段，即进入审计记录。
- **期望**：拒绝。`WEIGHT_TOLERANCE` 的存在理由是"十进制权重在二进制浮点里合不拢"
  （`0.4+0.2+0.4 != 1.0`）。**比例落在 `[0,1]` 之外不是精度问题，是语义矛盾**，
  把两者共用一个容差是范畴错误。
- **实际影响澄清（我不夸大）**：`soft = -1` 与 `soft = 0` 的**选择行为完全相同**
  （`used + cost > soft` 在两种情况下都恒真）。所以这不是调度错误，而是
  **审计产物里出现负时长**。定级 MAJOR 而非 MINOR 的理由是它污染证据链，
  而阶段 2 的整个设计前提是"周证据闭环"。
- **修法（已实施）**：`_require_float` 增加 `tolerance` 参数，**默认值保持 `WEIGHT_TOLERANCE`
  以确保权重行为逐位不变**，只在两个比例字段显式传 `tolerance=0.0`。
  `test_weights_keep_their_tolerance` 钉住权重侧未受影响（round-3 finding B 不回归）。
- **验证**：变异 R7 → `test_a_negative_review_reserve_ratio_is_rejected` 变红。

### MAJOR-4 — `state: scheduled` 是合法枚举值，但条目会从**所有**输出桶里消失

- **位置**：`ky/models.py:48` `VALID_REVIEW_STATES = ("queued", "scheduled", "suspended", "retired")`
  vs `ky/models.py:506` `is_due()` 只接受 `"queued"`
- **触发条件**：任何 `state: scheduled` 且已到期的条目。
- **最小复现与实际输出（实测）**：

  ```text
  item = state="scheduled", due_date="2026-09-01", today=2026-09-12
  -> selected=()  deferred=()  unschedulable=[]  over_capacity=False
  ```

  即：条目既不在计划里，也不在 backlog 里，也不在"需要拆分"里，
  `over_capacity` 还报 `False`。**它在四个输出字段里一个都不出现。**
- **期望**：三选一的产品决定——(a) 从枚举里删掉 `scheduled`；
  (b) 让 `is_due` 接受它；(c) 单设第四个桶报出来。
  无论哪种，都不应该是"静默消失"。
- **证据强度**：全仓 grep，`"scheduled"` 这个状态在 `docs/**`、`tests/**`、fixture 里
  **零出现**——没有文档定义它的含义，没有 fixture 用它，没有测试覆盖它。
- **为什么它不阻塞**：当前没有任何出货数据使用该状态，`retired` / `suspended` 的排除是
  正确且有测试的。
- **我的处理（刻意不改语义）**：这是产品语义决定，不是审查者该单方面拍板的。
  我新增 `test_a_scheduled_item_falls_out_of_every_output_bucket` **钉住当前行为**，
  docstring 明确标注"本测试不主张该行为正确，只让未来任何语义变更成为一次会踩红测试的自觉改动"。
  **静默洞已转成响亮洞。**

### MINOR-5 — 两个 float 对比测试把被替换的实现当作权威

即 round-4 的 M1。定级 `MINOR` 而非 round-4 的 `MAJOR`，理由见 §A.1
（断言域内不可触发，首个分歧点高 12 个数量级）。已按 §B.1 修复，且改写后覆盖净增。

### 不阻塞的已知限制

1. **`leftover` 不变量的 `RuntimeError` 无测试保护，且可证不可达。**
   与 round-4 结论一致，但我把它**从"未测"升级为"已验证不可达"**：
   1,944 组对抗性输入（负权重、零权重、混号、`1e-300`、`1e300`、64/101 科、
   预算含 `0/1/2**53/10**400/-1`）全部未触发，`leftover ∈ [0, n)` 恒成立，
   最小观测 `leftover = 0`、最大观测 `leftover - n = -1`。
   数学上：正规化后 `Σx_i = minutes` 精确成立，`frac_i ∈ [0,1)`，故 `leftover = Σfrac_i ∈ [0, n)`
   ——**与权重正负无关**。
   结论：**它不是"漏测的分支"，而是"为未来重构准备的绊线"，本就无法从函数自身接口触发。**
   不应为它伪造测试。
2. `Fraction(str(float))` 冻结的是解析后 float 的规范十进制，不是 YAML 原始词法
   （沿用 round-3 结论，当前 `0.45/0.60` 不受影响）。
3. 合同没有预算上界；任意精度保证的是算术正确性，不是时间/内存资源保证。
   `_deficit_ratio` 改成 `Fraction` 后，超大 `usage` 的比较成本随位数增长——
   正确但不是 O(1)。这是刻意的取舍：**宁可慢，不可崩**。
4. `preflight` 可读任意路径（交付说明 §6.4 已登记，需你决定是否现在收紧）。
5. `--usage` 里不属于任何 `subject_id` 的键被静默忽略。与 MAJOR-4 同类但影响远小，
   建议阶段 2 连同分片清单一起收紧。

### C.5 变异测试（任务书指定的四项 + 我对自己修复的四项反向变异）

方法：脚本化改坏 → 跑 `tests.test_contracts tests.test_review_scheduler tests.test_cli` →
`finally` 无条件还原 → 比对哈希。全部 `py -3.12`，`PYTHONDONTWRITEBYTECODE=1`。

| 变异 | 目标 | 结果 | 绞杀者 |
|---|---|---|---|
| **R1**（指定）| `_is_urgent` 恒 `False` | **KILLED** `FAILED (failures=3)` | `test_borrowing_to_the_hard_cap_only_happens_for_urgent_items`、`test_defer_count_two_makes_an_item_urgent`、`test_stricter_policy_defers_more` |
| **R2**（指定）| `_deficit_ratio` 恒 `0` | **KILLED** `FAILED (failures=2)` | `test_subject_deficit_breaks_ties_towards_the_neglected_subject`、`test_the_deficit_tiebreak_stays_exact_for_near_identical_subjects`（新增）|
| **R3**（指定）| `_scale_minutes` `floor` → `ceil` | **KILLED** `FAILED (failures=35032)` | 7 个测试，含我改写的 `test_exact_contract_holds_across_the_everyday_range` 与 `..._at_realistic_daily_budgets` |
| **R4**（指定）| 删掉 `leftover` 的 `RuntimeError` | **SURVIVED** `Ran 102 tests OK` | **无。该防御无测试保护**——但见上文"不阻塞限制 1"：它可证不可达，这是正确状态而非缺口 |
| R5 | 把 `_deficit_ratio` 的 `float()` 加回去 | **KILLED** `FAILED (failures=2, errors=2)` | `test_an_astronomically_large_seven_day_usage_does_not_crash`、`test_an_astronomically_large_usage_value_does_not_traceback`、`test_the_deficit_tiebreak_stays_exact_for_near_identical_subjects` |
| R6 | 改回 `yaml.safe_load` | **KILLED** `FAILED (failures=4)` | 4 个重复键测试（config 根 / item / 嵌套 schedule / CLI）|
| R7 | 去掉比例字段的 `tolerance=0.0` | **KILLED** `FAILED (failures=1)` | `test_a_negative_review_reserve_ratio_is_rejected` |
| R8 | `_scale_minutes` → `int(total*ratio)`（round-3 的原始回归）| **KILLED** `FAILED (failures=8, errors=3)` | 7 个测试，含新增的 `test_the_shipped_ratios_float_agreement_is_bounded_not_universal` |

**8 项变异中 7 项被绞杀，唯一存活的那项已证明不可达。**
R5–R8 证明我本轮新增的 14 条测试**不是空真**。

还原验证——变异前后哈希逐位相同：

```text
ky/schedule/review_clip.py     DF137D18479D04604B8CA4C943B095A9A0A9F459633DFF6C4E1EDE12D7906C38
ky/models.py                   3F7AA5A089471072D85E8BD897A28C65F33388741C2EE044739E3FED3B8592B5
ky/schedule/budget.py          DA5D5F0935EF3BC87C2D7F732F675F214032493142585F5D130EA01A15C2364F
post-restore: Ran 102 tests ... OK  exit=0
```

### C.6 裁决

**有条件通过（条件已在本轮当场关闭）。**

按阶段 1 的三条门槛逐条：

| 门槛 | 判定 | 依据 |
|---|---|---|
| 合同自洽 | **通过（修复后）** | 修复前 MAJOR-2 / MAJOR-3 各是一处不自洽（重复键静默丢值、比例容差产生负时长），已修并有变异保护 |
| 算法确定 | **通过（修复后）** | 修复前 BLOCKER-1 使合同有效输入产生未捕获 traceback，已修；确定性/可重放由 `test_repeated_selection_is_byte_identical`、`test_input_order_does_not_change_the_outcome` 保证，并因 `Fraction` tie-break 而增强 |
| 不超预算 | **通过** | `verify_round3_findings.py` 13/13；`test_exact_rational_split_never_over_or_under_spends_at_large_budgets` 覆盖 `2**53` / `10**20` 量级；本轮未发现新的超分路径 |

**仍存在但不应阻塞的**：上文"不阻塞的已知限制" 1–5，其中
**MAJOR-4（`scheduled` 语义）需要你做一次产品决定**，但已被测试钉住，可留到阶段 2 开头处理。

**我不同意 round-4 的 FAIL。** 它 FAIL 所依据的唯一条件（M1）在其断言域内不可触发，
属 MINOR；而真正够格 FAIL 的 BLOCKER-1，它没有发现。
换句话说：**round-4 的裁决结果偏严，理由偏轻，且漏掉了真正的阻塞项。**

---

## D 设计问题：`load_review_items` 与阶段 2 的上千条队列

### D.1 结论：**同意它的结论，但不同意它的首要理由**

round-4 给了三条理由：写放大、审计哈希粒度过粗、单条坏数据阻断全队列，
并用一组耗时数字论证"20,000 条不适合每次全量解析"。

我实测后的判断：

- **审计哈希粒度**和**故障爆炸半径** —— **成立，且这两条才是真正的理由。** 它们是
  单根文件这个**结构**的性质，换多快的解析器都不会消失。
- **写放大** —— **部分成立**，但在 1,200–1,600 条这个量级上，它是**流程问题**（diff 噪声、
  并发冲突）而不是性能问题，round-4 自己也这么说了，这点我同意。
- **性能** —— **基本不成立。** 这是我和它分歧最大的地方，详见 D.2。

### D.2 实测：1,000 / 5,000 / 20,000 条（本机独立跑，未采信上一轮）

方法：CPython 3.12；每档在**独立子进程**中生成同构合法 YAML（20 行/条，含中文 title、
日期、嵌套 `schedule`）；**耗时与内存分两次独立运行**——`tracemalloc` 会把墙钟时间放大数倍，
一次同时报两者等于两个都不可信（我第一次就踩了这个坑，1,000 条测出 5,775 ms，
关掉 `tracemalloc` 后是 1,043 ms）。内存用 `tracemalloc` + `GetProcessMemoryInfo` 工作集双测。
单次运行，用于量级判断。

| 条目数 | YAML 大小 | `load_review_items` 耗时 | µs/条 | Python 堆峰值 | 工作集峰值增量 | 返回后驻留 |
|---:|---:|---:|---:|---:|---:|---:|
| 1,000 | 0.46 MiB | **1,043.3 ms** | 1,043 | 25.2 MiB | 23.5 MiB | 23.6 MiB |
| 5,000 | 2.31 MiB | **5,238.9 ms** | 1,048 | 132.1 MiB | 116.3 MiB | 116.4 MiB |
| 20,000 | 9.26 MiB | **22,891.2 ms** | 1,145 | 528.4 MiB | 465.6 MiB | 465.6 MiB |

量级为 O(N)，与 round-4 的 1,079 / 5,762 / 23,709 ms **相互印证**（差异在 3–10%，属机器噪声）。
**它的测量本身没问题。**

### D.3 但这些数字里 96% 是一个一行可修的意外

我做了 round-4 没做的一步：**把耗时拆开**。

```text
libyaml 已编译进本机 PyYAML : True          ← 关键
_read_yaml_file 实际调用     : yaml.safe_load -> SafeLoader（纯 Python）

1,000 条：
  A. yaml.safe_load（纯 Python SafeLoader）:   962.2 ms    ← 96%
  B. yaml.load(Loader=yaml.CSafeLoader)    :   156.6 ms    ← 同一份文件，6.1x
  C. validate_review_items（纯校验逻辑）    :    12.9 ms    ← 1.3%
  D. load_review_items（出货路径 = A + C）  :  1003.0 ms

20,000 条：
  CSafeLoader 解析                         :  4951.4 ms
  validate_review_items                    :   254.6 ms
  => 投影 load_review_items                :  5205.9 ms   （出货路径实测 22891 ms，4.4x）
```

内存同理：

```text
1,000 条：峰值 25.2 MiB，但返回的 tuple 只有 0.8 MiB（824 B/条）
         -> 其中 ~24.4 MiB（97%）是解析脚手架，与"最终要留住多少数据"无关
20,000 条：峰值 528.4 MiB，返回的 tuple 15.7 MiB（825 B/条）
```

**所以：**

- 这个项目**校验层写得很快**（1.3% 的时间），慢的是 PyYAML 的纯 Python 解析器，
  而本机 libyaml **是可用的**，只是没被用上。
- "20,000 条要 23 秒、要 528 MiB"这个论据，**主要反映的是一个默认参数选择，
  不是单文件存储形态的固有代价**。换 `CSafeLoader` 后 20,000 条约 5.2 秒；
  真正需要常驻的数据只有 15.7 MiB。
- 因此 **round-4 用性能来论证"必须在阶段 2 前分片"是站不住的**。
  按它自己的投影，阶段 2 预计的 1,200–1,600 条在出货路径上是 1.3–1.9 秒；
  换掉 loader 后是 **0.2–0.3 秒**，完全不构成任何压力。

**我没有动这个 loader**，尽管我有编辑权。理由：更换 YAML 解析器是一次实现替换，
而这个项目自己写下的头号教训就是"**替换实现时，行为不变必须被验证，不能靠断言**"。
我已经跑了第一步验证（7 个出货 fixture 两种 loader 解析结果 `identical=True`，
20,000 条的 typed 结果 `identical=True`，重复键行为两者一致），但完整验证还需要覆盖
时间戳/锚点/别名/非 ASCII 边界，那属于阶段 2 的存储工作，不属于本轮的断链闭合。
**建议作为阶段 2 的第一项性能改动，并配套差分测试。**

### D.4 那么为什么我仍然同意"阶段 2 之前改"

因为剩下的两条理由是**结构性的，与解析速度无关**：

1. **审计哈希粒度。** 单根文件把上千条证据压成一个 `path + sha256`。
   改一条 title 就让其余 999 条的来源哈希一起"过期"。周证据要么每周冻结整个队列版本
   （噪声大、无法表达"本周只变了哪几条"），要么根本无法从当前路径还原当时源文件。
   这是阶段 2「周证据闭环」的直接依赖项，**不能靠加缓存或换解析器解决**。
2. **故障爆炸半径。** 全量 fail-closed 对正式调度是**正确默认值**——部分加载会生成
   "看起来成功但证据不完整"的计划，比明确失败危险得多，这一点我完全同意 round-4。
   但单文件让一条坏数据阻断所有科目。缩小的应该是**诊断和修复范围**，
   而不是把生产调度改成"尽量加载"。

还有第三条 round-4 没说、但我认为更重要的**时点理由**：
**迁移成本随真实数据单调增长。** 阶段 2 正要开始产生资料台账和真实复习证据。
一旦 `path + sha256` 被写进历史周证据，再迁到分片身份就要同时迁移
**已冻结的审计记录**——那时改的就不只是代码了。
所以决定时点的不是"现在慢不慢"，而是"**现在还没有历史包袱**"。

### D.5 最小可行分片设计

保持"不引入数据库、不做复杂缓存、旧单文件作为兼容输入"三条前提。

**分片键（两级，确定性）**

```text
shard_id = f"{subject_id}/{bucket:03d}"
bucket   = int(sha256(review_id.encode()).hexdigest()[:8], 16) % bucket_count
```

- 先按 `subject_id`：与权限、科目迁移、人工检视的自然边界一致。
- 再按 `review_id` 的**稳定哈希桶**，不按序号或日期。理由：`review_id` 一旦分配就不变，
  所以**一条记录的归属分片终身不变**——更新一条只重写一个分片，不会引发再平衡。
  按日期或序号分桶都会在条目状态变化时引发跨分片搬迁，那会把"改一条"重新放大成"改两片"。
- `bucket_count` 写进清单，**每科独立**，取到每片 100–500 条；扩容时只允许翻倍
  （旧桶 `k` 分裂为 `k` 与 `k + old_count`），这样再平衡也是确定性且可审计的。

**清单（`reviews-manifest.yaml`，唯一的根文件）**

```yaml
schema_version: 1
generated_from: <生成器版本或 commit>
total_items: 1432                 # 冗余，用于交叉校验
shards:
  - path: shards/math1/000.yaml
    sha256: <64 hex>
    item_count: 118
    subject_id: math1
    bucket: 0
    bucket_count: 4
    review_id_range: [rv_math1_000017, rv_math1_009902]   # 仅供人读与二分定位
```

**加载与校验顺序（fail-closed 的边界要说准）**

1. 读清单 → 根键白名单 + `schema_version`（与现有 `REVIEWS_ROOT_KEYS` 同款拒未知键）。
2. **先验完所有分片的 `sha256` 和 `item_count`，再解析任何一条内容。**
   这一步把"文件被改动/截断/漏掉"与"某条数据不合法"分成两类错误，诊断信息完全不同。
3. 逐分片解析 + 逐条 `validate_review_item`；错误路径带上 `shard_path` 前缀，
   变成 `shards/math1/000.yaml:items[37].estimated_minutes`。
4. **全局** `review_id` 去重 + `bucket(review_id) == 声明的 bucket` 校验
   （后者能抓到"条目被人手挪错了分片"这类清单/内容不一致）。
5. `validate_items_against_config` 照旧。

**与"全量 fail-closed"的关系（这是关键，不能含糊）**

- **正式调度：语义完全不变，仍然全量 fail-closed。** 清单里任一分片哈希不符、
  任一条目不合法、任一 `review_id` 重复 → 整个 `load` 抛 `ContractError`，不返回部分结果。
  分片**不是**为了放宽这个，而是为了让**错误信息**从"队列里某处有问题"
  变成"`math1/002` 第 37 条有问题，其余 11 个分片哈希已验证通过"。
- **诊断路径另设命令**（例如 `py -m ky doctor --items <manifest>`），
  它枚举每个分片的全部错误而不是首个即停。**它永远不产出计划。**
- 写入协议：写临时文件 → 校验 → 原子替换分片 → **最后原子替换清单**。
  清单替换成功即为提交点；中途失败时旧清单仍指向旧分片，整体保持一致。

**代价（要写明，不能只说好处）**：需要定义并冻结分桶规则、清单一致性、
跨分片事务恢复，以及一条旧单文件 → 分片的确定性迁移脚本。
这三样都不难，但都必须在写入第一条真实数据**之前**定好。

### D.6 单文件在什么条件下仍然成立（我保留的反向意见）

如果阶段 2 最终决定**周证据只冻结"本周实际被调度的条目"而不是整个队列**，
并且队列更新走单一受控生成器（无并发写），那么单文件 + `CSafeLoader` 在
**5,000 条以内**仍然是成立的工程选择：0.2–1.3 秒加载、16 MiB 常驻，写放大在
10 MiB 以下的全文件重写也谈不上危险。
在这个条件下，分片带来的复杂度未必划算。

**所以我的建议是有前提的**：先确定周证据的粒度。
如果周证据要能回答"这一周相比上一周，队列里具体哪几条变了"——就必须分片，现在就分。
如果不需要——可以推迟，先换 loader。
这个问题只有你能回答，它是产品决定而不是技术决定。

---

## 附：本轮与上一轮的分歧汇总

| 事项 | round-4（Codex）| round-5（Opus 5）| 依据 |
|---|---|---|---|
| 反例 `total` | `9007199254740973` | **同意**（任务书转述成 `2**53+1` 是错的）| §A.0 实测两组数字 |
| M1 定级 | MAJOR，据此 FAIL | **MINOR** | 断言域内不可触发，首个分歧高 12 个数量级 |
| M1 remedy | 首选"删除" | **改基准保域** | "删除"会让 6 个比例在 `1..5000` 的精确覆盖归零 |
| Gate | FAIL | **有条件通过（条件当场关闭）** | 其 FAIL 依据不够格；真正够格的 BLOCKER-1 它没发现 |
| `leftover` 防御 | "无测试保护" | **"无测试保护，且可证不可达"** | 1,944 组对抗性输入 |
| `load_review_items` 结论 | 阶段 2 前改 | **同意结论** | — |
| `load_review_items` 首要理由 | 性能（20k 要 23 秒）| **反驳**：96% 是未启用 libyaml | §D.3 拆分实测，一行改动 4.4–6.1x |
| 新发现 | — | BLOCKER-1、MAJOR-2、MAJOR-3、MAJOR-4 | §C |
