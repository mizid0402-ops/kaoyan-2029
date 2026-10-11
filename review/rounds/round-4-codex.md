# 第四轮断链复核：Codex 裁决

## 裁决

- **断链是否已补上：否。** 本轮窄范围 Gate 为 **FAIL**：精确算术实现没有问题，新增的两项精确契约测试也有效，但上一轮的关条件只被部分关闭；`tests/test_contracts.py` 仍有两个超出获准兼容范围的测试把旧 float 乘积作为失败基准，两处 docstring 的承诺范围也未按任务书准确收窄。
- **扩展性结论：应该在阶段 2 之前改。** 推荐采用“确定性有界分片 + 清单索引”，继续保持生产调度 fail-closed；不建议一条一文件，也不能靠缓存解决写放大和审计哈希过粗的问题。
- 任务书所称“4 个文件”并不准确：改动清单有 4 行，但只涉及 3 个不同文件，即 `tests/test_contracts.py`、`ky/models.py`、`ky/schedule/budget.py`。

这不是对精确实现的否定，也不构成回退到 `int(total_minutes * ratio)` 的理由。

## 条件关闭逐项核实

### 已正确落实的部分

1. `tests/test_contracts.py:577-601` 的 `test_exact_contract_holds_for_repeating_decimals` 确实以 `Fraction(str(ratio))` 为基准，并同时检查：
   - `actual == floor(total × Fraction(str(ratio)))`；
   - `actual <= product < actual + 1`；
   - `0 <= actual <= total`。
2. `tests/test_contracts.py:645-679` 的 `test_exact_contract_holds_across_a_cross_product` 确实覆盖 15 个比例与 12 个预算，共 180 个组合；比较基准是精确有理乘积，不是旧 float 乘积。
3. `ky/schedule/budget.py:92-100` 已把 `leftover` 的 `assert` 改成显式 `RuntimeError`，在 `python -O` 下不会消失，错误类型也符合“内部不变量失败”而非业务输入错误的定位。
4. `tests/test_contracts.py:603-632` 中的 float 比较只是在固定已知反例，文字明确称其为旧舍入伪影；它不是把 float 当权威。

### M1 — PARTIALLY RESOLVED：旧 float 权威及过宽文案仍有残留

**严重性：MAJOR。** 这是本轮明确的关条件，而不是风格意见；未满足它就不能把原有条件 PASS 改为无条件 PASS。

**位置：**

- `tests/test_contracts.py:549-575`
- `tests/test_contracts.py:634-643`
- `ky/models.py:301-313`

**触发条件：**

1. 审查测试契约时，`test_matches_the_float_product_across_the_everyday_range` 和 `test_matches_the_float_product_at_realistic_daily_budgets` 对 8 个 `TERMINATING_RATIOS` 直接计算 `int(total * ratio)`；一旦精确结果与旧结果不同，就以 “exact scaling diverged from the float product” 判失败。上一轮获准保留的旧行为兼容范围只有 `ratio in {0.45, 0.60}` 且 `total=1..20000`，这里额外冻结了 `0.05/0.99/0.01/1.0/0.75/0.125`。
2. `test_the_projects_own_ratios_are_unaffected` 的 docstring 虽已限定两个比例，却只写 “the range that matters” 和 “this range”，没有明确写出断言实际执行的 `total=1..20000`；因此仍未达到任务书要求的“docstring 与断言范围一致”。
3. `_scale_minutes` 的 docstring 声称项目比例 `0.45/0.60` 与 float “agree everywhere a study budget can reach”。合同没有预算上界，这一全称措辞可被合同接受的整数预算推翻，并且与同一 docstring 前面写明的大预算 float 溢出相互矛盾。

**最小复现与实际输出：**

静态检索直接得到：

```text
tests/test_contracts.py:559: legacy = int(total * ratio)
tests/test_contracts.py:565: exact scaling diverged from the float product ...
tests/test_contracts.py:573: int(total * ratio)
tests/test_contracts.py:643: self.assertEqual(_scale_minutes(total, ratio), int(total * ratio))
```

其中最后一行是获准的项目比例兼容检查，但它的 docstring 没有写明数值范围；前两项测试则扩大了获准范围。

生产 docstring 的确定反例为：

```text
ratio=0.45, total=9007199254740973
exact  = 4053239664633437
legacy = 4053239664633438

ratio=0.60, total=9007199254740973
exact  = 5404319552844583
legacy = 5404319552844584
```

更大预算下两者差距继续扩大；`total=10**309` 时两个项目比例的旧乘法均抛出 `OverflowError`，精确实现正常返回整数。

**期望：**

- 通用测试只以 `floor(total × Fraction(str(ratio)))` 为权威。
- 旧 float 兼容只作为明确限定的产品回归：`ratio in {0.45, 0.60}`、`total=1..20000`。
- 所有 docstring 都精确写出该范围，不使用 “everywhere a study budget can reach” 之类没有数值边界的承诺。

**最小修法：**

1. 删除 `test_matches_the_float_product_across_the_everyday_range` 和 `test_matches_the_float_product_at_realistic_daily_budgets`，因为获准范围已由 `test_the_projects_own_ratios_are_unaffected` 覆盖；或者把二者改成精确有理契约测试，不能再让 float 差异本身导致失败。
2. 把 `test_the_projects_own_ratios_are_unaffected` 的 docstring 明写为 `ratio in {0.45, 0.60}, total in 1..20000`。
3. 把 `_scale_minutes` docstring 的项目比例句子同样限定到已验证范围，或直接删掉这句；保留 `1/53` 反例、大预算溢出警告和“不要回退”警告。

## 规定检查的真实结果

为避免测试生成或更新 `__pycache__`，命令增加了不改变测试语义的 `-B`；所有 Python 调用均为指定的 `py -3.12`。

```text
> py -3.12 -B -m unittest tests.test_contracts tests.test_review_scheduler tests.test_cli
........................................................................................
----------------------------------------------------------------------
Ran 88 tests in 2.168s

OK
exit code = 0
```

```text
> py -3.12 -B tools/verify_round3_findings.py
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

绿色检查证明当前实现通过现有测试，但不能推翻 M1 的静态契约残留。

## 变异测试及恢复

### 变异 1：回退到旧 float 乘法

临时把 `ky/models.py:318` 改成：

```python
return int(total_minutes * ratio)
```

只运行两项新增测试：

```text
py -3.12 -B -m unittest \
  tests.test_contracts.RatioScalingTest.test_exact_contract_holds_for_repeating_decimals \
  tests.test_contracts.RatioScalingTest.test_exact_contract_holds_across_a_cross_product

Ran 2 tests in 0.003s
FAILED (failures=5)
exit code = 1
```

代表性失败：`total=3, ratio=0.3333333333333333` 时 `actual=1`、精确期望 `0`；交叉积另记录 36 个错误组合。**变异被杀死，新测试不是空真。**

恢复后同两项测试为 `Ran 2 tests ... OK`，且：

```text
ky/models.py SHA-256 = 82552CAFECFAD1C4C2ABCE4A4E9DAA4E9903CFE73F3EA4BF0DB9F1B5E436AA90
```

### 变异 2：把 floor 改成 ceil

临时改成：

```python
return math.ceil(total_minutes * Fraction(str(ratio)))
```

同两项新增测试结果：

```text
Ran 2 tests in 0.006s
FAILED (failures=6)
exit code = 1
```

代表性失败：`total=3, ratio=0.3333333333333333` 时 `actual=1`、期望 `0`；交叉积记录 120 个错误组合。**变异被杀死。**

恢复后哈希再次为：

```text
ky/models.py SHA-256 = 82552CAFECFAD1C4C2ABCE4A4E9DAA4E9903CFE73F3EA4BF0DB9F1B5E436AA90
```

### 变异 3：删除 `leftover` 显式不变量检查

删除 `ky/schedule/budget.py:92-100` 的检查后，运行所有直接覆盖预算分配的测试：

```text
> py -3.12 -B -m unittest tests.test_contracts.BudgetAllocationTest
...........
----------------------------------------------------------------------
Ran 11 tests in 0.031s

OK
exit code = 0
```

测试源码中也没有直接构造不变量失败或检查该 `RuntimeError` 的案例。结论必须明说：**该防御无测试保护。** 这不是当前可达业务错误；合法输入下该不变量由精确正规化与最大余数法的数学性质保证，所以它不阻塞本轮 Gate，但若未来重构内部计算，现有测试只能检查最终加总，不能证明显式防御仍存在。

恢复后：

```text
ky/schedule/budget.py SHA-256 = DA5D5F0935EF3BC87C2D7F732F675F214032493142585F5D130EA01A15C2364F
```

全部恢复后的最小回归为 13 项，结果 `OK`；最终相关文件哈希如下：

```text
ky/models.py             82552CAFECFAD1C4C2ABCE4A4E9DAA4E9903CFE73F3EA4BF0DB9F1B5E436AA90
ky/schedule/budget.py    DA5D5F0935EF3BC87C2D7F732F675F214032493142585F5D130EA01A15C2364F
tests/test_contracts.py  E70D97DD3AA1CB17BC04DA9002465CDB64ABFC0B3FE4718CAA83E3D967AD0E06
```

## `load_review_items` 扩展性评估

### 已确认的当前行为

`ky/models.py:658-691` 接受一个文件路径；`_read_yaml_file` 先把全文读入内存并调用 `yaml.safe_load`，随后 `load_review_items` 把所有条目验证并构造成一个 tuple，最后再做全局 `review_id` 去重。当前 `ky/**` 与 `tools/**` 没有复习队列写入 API。因此需要准确区分：

- **事实：** `load_review_items` 自身只读，不会重写文件。
- **设计推论：** 在“一个根 YAML 保存全部队列”的持久化约束下，安全的程序化新增/更新通常要读入、修改并重新序列化整个根文件；手工做原地文本替换虽然可能少写字节，却难以保证 YAML 结构、原子性、确定性序列化和哈希审计，不应成为受控生成流程的写入协议。

### 解析与校验实测

方法：CPython 3.12；每档在独立 Python 进程和自动删除的临时目录中生成同构合法 YAML；基线在文件写完并 GC 后记录；加载期间以 1 ms 间隔采样 Windows Working Set。每档单次运行，数字用于量级判断，不应冒充跨机器基准或统计置信区间。

| 条目数 | YAML 大小 | `load_review_items` 耗时 | Working Set 峰值增量 | 返回后驻留增量 |
|---:|---:|---:|---:|---:|
| 1,000 | 0.46 MiB | 1,079.5 ms | 27.68 MiB | 25.75 MiB |
| 5,000 | 2.30 MiB | 5,762.4 ms | 142.16 MiB | 127.41 MiB |
| 20,000 | 9.21 MiB | 23,708.8 ms | 567.61 MiB | 508.68 MiB |

时间与内存都近似线性，算法量级是 O(N)，但 PyYAML 映射、日期和 dataclass 的常数不小。按本机结果线性估算，阶段 2 预计的 1,200–1,600 条约为 1.3–1.9 秒、约 34–45 MiB 峰值增量：偶发 preflight 尚可接受，频繁 CLI 调用已有明显延迟；5,000 条以上成为实质性成本，20,000 条则不适合每次全量解析。

### 写放大与受控生成

在 1,200–1,600 条时，单次重写的绝对字节数还不大，性能不是首要危险；真正的问题是更新粒度：每天更新到期日、阶段、质量或新增条目，都会制造整份队列的重写和大 diff。并发生成、人工修订与调度状态回写也会集中竞争同一路径，增加冲突和失败后恢复的复杂度。若采用“写临时文件 + 校验 + 原子替换”，原子性可以保证，但写放大和全文件版本 churn 仍在。

### 审计与哈希粒度

单根文件把所有条目的证据身份压缩成同一个 `path + sha256`。临时探针仅修改 1,000 条中的一个 title，文件字节数保持 44,025 不变，但 SHA-256 从：

```text
A2D26399BB686E08D1C1EA55A4C4C66EA8426B9A6E98CAD12D68B8CDED28AF6E
```

变为：

```text
D890F16EED6825A1E15F04FE5C0EF8DEE4722846E6ECBB73977A5005FF0654D2
```

这符合哈希的预期，却说明单文件证据粒度过粗：改一条后，其他 999 条的来源哈希也一起“过期”。如果旧内容没有按哈希归档，历史周证据只有旧 `path + sha256`，无法从当前路径还原当时源文件；即便有归档，每周也要把整个队列版本作为一个大证据对象冻结，难以表达“本周只变更了哪几条”。这会让周证据闭环变得噪声大、重算范围大、人工复核困难。

### 失败模式

当前设计是全量 fail-closed。三条队列中第二条令 `estimated_minutes=31` 的实测输出为：

```text
ContractError
path=items[1].estimated_minutes
message=items[1].estimated_minutes: estimated_minutes (31) exceeds the 30 minute single-pass cap; split the item before importing it
result_assigned=False
```

也就是不会返回前一条或后一条的部分结果；重复 ID 检查还要等全部条目构造完成后才运行。

对正式调度而言这是正确默认值：部分加载会静默漏掉应复习条目，生成一个看似成功但证据不完整的计划，比明确失败更危险。但单文件让一条坏数据阻断所有科目，故故障爆炸半径过大。应通过分片缩小诊断和修复范围，而不是让生产调度默认“尽量加载”。可以另设只用于修复的诊断命令，枚举每个分片的错误；正式计划仍要求清单和全部分片通过。

### 替代形态与代价

1. **按科目分文件：** 实现最简单，能把多数写入和哈希变化隔离到一个科目；但 408 单科仍可能有 800–1,200 条，全局重复 ID 与跨科迁移需要聚合校验，粒度仍偏粗。
2. **一条一文件：** 写放大和来源哈希最细；代价是上千小文件的目录遍历、打开文件、清单维护、跨条目原子更新和人工管理成本，Windows 上尤其容易被小文件 I/O 放大，不推荐作为主格式。
3. **确定性有界分片 + 清单索引：推荐。** 例如先按科目，再按稳定 ID 桶或固定上限分成每片约 100–500 条；清单记录 schema version、分片路径、SHA-256、条目数、科目/桶范围，并做全局重复 ID 校验。一次更新只重写一个分片和小清单；周证据可精确冻结受影响分片；清单最后原子替换可形成提交点。代价是要定义稳定分片规则、清单一致性和跨分片事务恢复。
4. **保持单文件但加缓存：** 能改善重复读取，但需要严格按源哈希失效并维护缓存格式；它不解决全文件重写、哈希过粗、冲突和单条错误阻断全队列，因此只能作为后续性能优化，不能作为本问题的结构性修法。

### 为什么应在阶段 2 之前改

预计的 1,200–1,600 条本身还没有把本机内存或耗时推到不可用，所以“解析太慢”单独不足以要求立即重构；真正决定时点的是阶段 2 正要开始产生资料台账、结构化知识点和真实复习证据。若等阶段 3 再迁移，已经冻结的 `path + sha256`、历史周证据和更新工具都要从单根文件身份迁到分片身份，迁移成本和审计解释成本会随真实数据一起增长。

因此阶段 2 前应先冻结存储接口：保留旧单文件作为兼容输入，新增清单/分片加载；正式调度仍全局校验、全量 fail-closed；先不引入数据库，也不必提前做复杂缓存。这样改的是证据与写入边界，而不是过度优化当前 24 条 fixture。

## 最终 Gate

**Gate：FAIL。断链未补上。** M1 仍是部分修复：实现和新增精确测试通过，变异覆盖有效，但验收测试及 docstring 尚残留旧 float 权威与过宽承诺；按上面的三个最小文本/测试修正后，才可重新确认无条件 PASS。
